"""Closed-loop integration gate. No UI, global pathfinder, or direct heading command."""

import hashlib
import math
from collections import deque
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter_ns

import numpy as np
from qdrant_edge import Distance, EdgeConfig, EdgeShard, EdgeVectorParams, Point

from fly_brain import FlyBrain

from . import memory
from .observer import CornerGuard, Observer
from .vision import camera_axes, encode, image_hash, relative, snapshot
from .world import LOOK, SPEED, STEP, YAW, choose


@dataclass
class Episode:
    point: object
    image: object


def serialize(hit):
    return {"id": hit.id, "score": hit.score, "payload": hit.payload}


def steps(
    kernel,
    world,
    seed=2000,
    mode="none",
    history=(),
    duration=65,
    control="normal",
    pose_variant=0,
    trace=False,
    backend=None,
    shard=None,
    owner=None,
    publish=True,
    writes=None,
    history_loaded=False,
):
    if mode not in {"none", "personal", "shared", "hive"}:
        raise ValueError("Unknown memory mode")
    if control not in {
        "normal",
        "no_memory",
        "mute",
        "reverse",
        "mute_choice",
        "reverse_choice",
    }:
        raise ValueError("Unknown control")
    owner = owner or {"shared": "B", "hive": "H"}.get(mode, "A")
    session = f"{owner}:{mode}:{seed}:{control}:{pose_variant}"
    kernel.drop(session)
    brain = FlyBrain(kernel, session, seed)
    active_memory = backend or memory
    # Initial pose varies independently of memory. Paired counterfactuals use this same value.
    noise = np.random.default_rng(seed + pose_variant * 7919)
    launch_x, launch_y, launch_heading = getattr(world, "launch", (40, 0, 0))
    lateral = float(noise.uniform(-2, 2))
    x = launch_x - math.sin(launch_heading) * lateral
    y = launch_y + math.cos(launch_heading) * lateral
    h = launch_heading + float(noise.uniform(-0.01, 0.01))
    protocol = getattr(world, "protocol", memory.PROTOCOL)
    target = None
    pending = None
    choice = None
    no_decision = False
    scanning = False
    observer = Observer()
    reading = observer.update(world, x, y, h)
    positions = deque([(x, y)], maxlen=21)
    corner_scans = 0
    padded_opening_gaps = 0
    minimum_wall_clearance = world.wall_clearance(x, y)
    collisions = 0
    path = 0.0
    detours = 0
    longest_stall = 0.0
    stall = 0.0
    spikes = 0
    motor_spikes = 0
    events = []
    frames = []
    episodes = []
    selected = []
    all_excluded_count = 0
    offset = max((e.point.payload["observed_at_ms"] for e in history), default=0) + 100
    with ExitStack() as stack:
        stack.callback(kernel.drop, session)
        if shard is None:
            temporary = stack.enter_context(TemporaryDirectory(prefix="maze-gate-"))
            location = Path(temporary) / "memory"
            location.mkdir()
            shard = EdgeShard.create(
                str(location),
                EdgeConfig(
                    vectors={
                        "view": EdgeVectorParams(size=192, distance=Distance.Cosine)
                    }
                ),
            )
            stack.callback(shard.close)
        if mode != "none" and not history_loaded:
            for episode in history:
                active_memory.remember(shard, episode.point)
        for tick in range(round(duration / STEP)):
            now = round(tick * STEP * 1000)
            openings = world.openings(x, y, h)
            if not openings and not scanning and world.openings(x, y, h, clearance=0):
                padded_opening_gaps += 1
            forward = world.forward(x, y, h)
            if reading.entered:
                # Query once before entering the selected branch, even with a stem target.
                target = None
            if target is not None and math.hypot(x - target[0], y - target[1]) < 18:
                target = None
            if choice is None and not scanning and not openings and forward < 35:
                scanning = True
                target = None
                guard = CornerGuard.start(
                    reading.ranges, (x - positions[0][0], y - positions[0][1])
                )
                corner_scans += guard is not None
                events.append(
                    {"kind": "scan", "time": now, "corner": guard is not None}
                )
                if pending is not None:
                    previous_guard = pending.get("guard")
                    if previous_guard is not None and all(
                        reading.ranges[i] is None
                        for i in (previous_guard.incoming, previous_guard.continuation)
                    ):
                        pass  # Preserve the original axes while still inside that corner.
                    elif guard is not None and previous_guard is None:
                        pending["guard"] = guard
                    else:
                        events.append(
                            {
                                "kind": "inconclusive",
                                "time": now,
                                "captured_at_ms": offset + pending["ms"],
                                "reason": "scan_without_outcome",
                            }
                        )
                        pending = None
            if (
                scanning
                and forward >= 90
                and any(abs(o.bearing) < math.radians(10) for o in openings)
            ):
                scanning = False
                target = None
            if target is None and openings and not scanning and choice is None:
                results = []
                images = []
                vectors = []
                excluded = []
                searches = []
                is_new = reading.entered
                cameras, ambiguous = (
                    camera_axes(openings, reading.ranges, h)
                    if is_new
                    else ([None] * len(openings), [])
                )
                for index in ambiguous:
                    events.append(
                        {"kind": "ambiguous_view", "time": now, "opening": index}
                    )
                for i, opening in enumerate(openings):
                    image = (
                        snapshot(world, x, y, cameras[i])
                        if cameras[i] is not None
                        else None
                    )
                    vector = encode(image) if image is not None else None
                    started = perf_counter_ns()
                    searched = mode != "none" and is_new and vector is not None
                    hits = (
                        active_memory.recall(
                            shard,
                            vector,
                            world.id,
                            exclude_fly=owner if mode == "shared" else None,
                            protocol=protocol,
                            owner=owner,
                            # Hive: one memory for every fly, including its own entries.
                            **({"everyone": True} if mode == "hive" else {}),
                        )
                        if searched
                        else []
                    )
                    searches.append(
                        (perf_counter_ns() - started) / 1_000_000 if searched else None
                    )
                    decided = active_memory.decide(hits)
                    applied = decided is not None and control != "no_memory"
                    results.append((hits, decided))
                    images.append(image)
                    vectors.append(vector)
                    excluded.append(applied)
                incoming = (
                    relative(reading.incoming - h) if reading.junction else math.pi
                )
                pick, all_excluded = choose(openings, excluded, incoming=incoming)
                if is_new and getattr(world, "neural_choice", False):
                    candidates = sorted(
                        [
                            i
                            for i, o in enumerate(openings)
                            if abs(relative(o.bearing - incoming)) > 0.55
                        ],
                        key=lambda i: openings[i].bearing,
                    )
                    if len(candidates) != 2:
                        events.append(
                            {
                                "kind": "no_decision",
                                "time": now,
                                "reason": "ambiguous_options",
                                "count": len(candidates),
                            }
                        )
                        no_decision = True
                        break
                    if all(excluded[i] for i in candidates):
                        excluded = [False] * len(openings)
                    choice = {
                        "capture_time": now,
                        "ticks": 0,
                        "heading": h,
                        "x": x,
                        "y": y,
                        "path": path,
                        "openings": openings,
                        "candidates": candidates,
                        "images": images,
                        "vectors": vectors,
                        "results": results,
                        "searches": searches,
                        "excluded": excluded,
                        "cameras": cameras,
                        "incoming": incoming,
                        "all_excluded": all_excluded,
                        "rates": tuple(
                            0.0 if excluded[i] else 30.0 for i in candidates
                        ),
                    }
                    pick = None
                all_excluded_count += all_excluded
                if pick is not None:
                    opening = openings[pick]
                    angle = h + opening.bearing
                    target = (x + LOOK * math.cos(angle), y + LOOK * math.sin(angle))
                    if is_new:
                        decision = {
                            "time": now,
                            "views": [
                                {
                                    "vector": v,
                                    "snapshot": image_hash(im)
                                    if im is not None
                                    else None,
                                    "camera_bearing": camera,
                                    "hits": [serialize(r) for r in rs[0]],
                                    "selected": serialize(rs[1]) if rs[1] else None,
                                    "applied": ex,
                                    "search_ms": search_ms,
                                    "bearing": op.bearing,
                                }
                                for v, im, rs, ex, op, camera, search_ms in zip(
                                    vectors,
                                    images,
                                    results,
                                    excluded,
                                    openings,
                                    cameras,
                                    searches,
                                )
                            ],
                            "choice": pick,
                            "all_excluded": all_excluded,
                            "incoming": incoming,
                        }
                        selected.append(decision)
                        events.append({"kind": "junction", **decision})
                        if pending is None and vectors[pick] is not None:
                            pending = {
                                "vector": vectors[pick],
                                "image": images[pick],
                                "ms": now,
                                "path": path,
                                "released_path": None,
                                "camera_bearing": cameras[pick],
                            }
            if target is not None:
                error = relative(math.atan2(target[1] - y, target[0] - x) - h)
            else:
                error = 0.0
            deliberating = choice is not None
            left, right, neural = brain.step(
                error,
                scan=scanning,
                trace=trace,
                options=choice["rates"] if deliberating else None,
            )
            spikes += neural["spikes"]
            motor_spikes += neural["left"] + neural["right"]
            yaw = neural["steer"] if control != "mute" else 0.0
            if control == "reverse":
                yaw = -yaw
            h += yaw * YAW * STEP
            if deliberating:
                choice["ticks"] += 1
                if choice["ticks"] % 10 == 0:
                    pick = brain.select(
                        neural,
                        choice["candidates"],
                        mute=control in {"mute", "mute_choice"},
                        reverse=control == "reverse_choice",
                    )
                    if pick is not None:
                        angle = choice["heading"] + choice["openings"][pick].bearing
                        target = (
                            x + LOOK * math.cos(angle),
                            y + LOOK * math.sin(angle),
                        )
                        decision = {
                            "time": now + round(STEP * 1000),
                            "capture_time": choice["capture_time"],
                            "views": [
                                {
                                    "vector": v,
                                    "snapshot": image_hash(im)
                                    if im is not None
                                    else None,
                                    "camera_bearing": camera,
                                    "hits": [serialize(r) for r in rs[0]],
                                    "selected": serialize(rs[1]) if rs[1] else None,
                                    "applied": ex,
                                    "search_ms": search_ms,
                                    "bearing": op.bearing,
                                }
                                for v, im, rs, ex, op, camera, search_ms in zip(
                                    choice["vectors"],
                                    choice["images"],
                                    choice["results"],
                                    choice["excluded"],
                                    choice["openings"],
                                    choice["cameras"],
                                    choice["searches"],
                                )
                            ],
                            "choice": pick,
                            "candidates": choice["candidates"],
                            "all_excluded": choice["all_excluded"],
                            "incoming": choice["incoming"],
                            "decision_readout": neural["steer"],
                            "decision_input": choice["rates"],
                        }
                        selected.append(decision)
                        events.append({"kind": "junction", **decision})
                        if pending is None and choice["vectors"][pick] is not None:
                            pending = {
                                "vector": choice["vectors"][pick],
                                "image": choice["images"][pick],
                                "ms": choice["capture_time"],
                                "path": choice["path"],
                                "released_path": None,
                                "camera_bearing": choice["cameras"][pick],
                            }
                        choice = None
                    elif choice["ticks"] >= 50:
                        events.append(
                            {
                                "kind": "no_decision",
                                "time": now,
                                "reason": "zero_readout",
                            }
                        )
                        no_decision = True
            forward = world.motion_forward(x, y, h)
            speed = (
                0.0
                if scanning or deliberating
                else SPEED * max(0.0, min(1.0, (forward - 10) / 35))
            )
            nx = x + math.cos(h) * speed * STEP
            ny = y + math.sin(h) * speed * STEP
            moved = math.hypot(nx - x, ny - y)
            if world.fits(nx, ny):
                x, y = nx, ny
                path += moved
            else:
                collisions += 1
                moved = 0.0
            stall = (
                stall + STEP
                if moved < 0.02 and not scanning and not deliberating
                else 0.0
            )
            longest_stall = max(longest_stall, stall)
            minimum_wall_clearance = min(
                minimum_wall_clearance, world.wall_clearance(x, y)
            )
            after = observer.update(world, x, y, h)
            positions.append((x, y))
            now += round(STEP * 1000)
            exited = world.exit_reached(x, y)
            if after.terminal and not reading.terminal:
                detours += 1
                events.append({"kind": "terminal", "time": now})
            if (
                after.released
                and pending is not None
                and pending["released_path"] is None
            ):
                pending["released_path"] = path
            completed = None
            if pending is not None and pending.get("guard") is not None:
                continuation = pending["guard"].check(after.ranges)
                if continuation is False:
                    events.append(
                        {
                            "kind": "inconclusive",
                            "time": now,
                            "captured_at_ms": offset + pending["ms"],
                            "reason": "reversal",
                        }
                    )
                    pending = None
                elif continuation is True:
                    pending["guard"] = None
                elif after.entered:
                    events.append(
                        {
                            "kind": "inconclusive",
                            "time": now,
                            "captured_at_ms": offset + pending["ms"],
                            "reason": "junction_before_corner_exit",
                        }
                    )
                    pending = None
            if pending is not None and pending.get("guard") is None:
                if exited:
                    completed = "open"
                elif (
                    hasattr(world, "returned_to_start")
                    and path - pending["path"] >= 100
                    and world.returned_to_start(x, y)
                ):
                    completed = "returned"
                elif after.terminal and path - pending["path"] >= 75:
                    completed = "dead_end"
                elif (
                    after.entered
                    and pending["released_path"] is not None
                    and path - pending["released_path"] >= 100
                ):
                    completed = "open"
            if completed:
                identifier = int.from_bytes(
                    hashlib.sha256(f"{session}:{len(episodes)}".encode()).digest()[:8],
                    "little",
                )
                payload = {
                    "outcome": completed,
                    "source_fly": owner,
                    "world": world.id,
                    "protocol": protocol,
                    "captured_at_ms": offset + pending["ms"],
                    "observed_at_ms": offset + now,
                    "snapshot": image_hash(pending["image"]),
                    "camera_bearing": pending["camera_bearing"],
                    "trial": session,
                }
                episode = Episode(
                    Point(identifier, {"view": pending["vector"]}, payload),
                    pending["image"],
                )
                episodes.append(episode)
                events.append({"kind": "observed", "time": now, **payload})
                if mode != "none" and publish:
                    if writes is None:
                        active_memory.remember(shard, episode.point)
                    else:
                        writes.append((active_memory, shard, episode.point))
                pending = None
            reading = after
            if trace or tick % 5 == 0 or exited:
                frames.append(
                    {
                        "ms": now,
                        "x": x,
                        "y": y,
                        "heading": h,
                        "left_input": left,
                        "right_input": right,
                        "neural": neural,
                        "applied_yaw": yaw,
                        "scan": scanning,
                        "deliberating": deliberating,
                        "junction": reading.junction,
                        "terminal": reading.terminal,
                        "ranges": reading.ranges,
                    }
                )
            yield {
                "ms": now,
                "mode": mode,
                "owner": owner,
                "seed": seed,
                "frames": frames,
                "decisions": selected,
                "events": events,
                "episodes": episodes,
            }
            if exited or no_decision:
                break
        if pending is not None:
            events.append(
                {
                    "kind": "inconclusive",
                    "time": now,
                    "captured_at_ms": offset + pending["ms"],
                    "reason": "run_ended",
                }
            )
    return {
        "mode": mode,
        "owner": owner,
        "seed": seed,
        "control": control,
        "pose_variant": pose_variant,
        "summary": {
            "exit": world.exit_reached(x, y),
            "time_ms": now,
            "path": path,
            "detours": detours,
            "returns": sum(e.get("outcome") == "returned" for e in events),
            "no_decision": no_decision,
            "left_choices": sum(d.get("decision_readout", 0) < 0 for d in selected),
            "right_choices": sum(d.get("decision_readout", 0) > 0 for d in selected),
            "collisions": collisions,
            "longest_stall_s": longest_stall,
            "spikes": spikes,
            "motor_spikes": motor_spikes,
            "all_excluded": all_excluded_count,
            "corner_scans": corner_scans,
            "reversals": sum(e.get("reason") == "reversal" for e in events),
            "padded_opening_gaps": padded_opening_gaps,
            "minimum_wall_clearance": minimum_wall_clearance,
            "ambiguous_views": sum(e["kind"] == "ambiguous_view" for e in events),
        },
        "episodes": episodes,
        "decisions": selected,
        "frames": frames,
        "events": events,
    }


def run(*args, **kwargs):
    """Drain the same simulation used by the live group."""
    simulation = steps(*args, **kwargs)
    try:
        while True:
            next(simulation)
    except StopIteration as finished:
        return finished.value
    finally:
        simulation.close()


def compact(result):
    return {k: v for k, v in result.items() if k not in {"episodes", "frames"}}
