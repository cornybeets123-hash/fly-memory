"""Can 1,000 simulated flies share one memory?

Each fly lives in its own arena (objects are placed differently for every fly),
so sharing *where* something happened is useless. What transfers is *what it
smelled like*: every object has an odor vector, and similar odors mean similar
outcomes. That is the only reason a vector database belongs here.

The fly's behaviour is fixed (approach odors, flee what it believes is
dangerous). We never change the controller. We only give it an external memory:

  local   : the fly's own experiences, checked first, on the fly
  fleet   : one shared Qdrant collection, asked only when local memory is unsure
  escalate: a fly uploads an experience only when it was surprised by it

Conditions (same seeds, same worlds):
  naive     no memory at all
  private   local memory only, nothing shared
  shared    local memory + shared fleet memory in Qdrant
  shuffled  shared, but uploaded outcomes are coin flips   (control: must not help)
  location  shared, but memories are keyed by position      (control: must not help)
"""
import json
import sys
import time
from dataclasses import dataclass, asdict

import numpy as np
from qdrant_client import QdrantClient, models


@dataclass
class Config:
    flies: int = 1000
    steps: int = 400
    novel_step: int = 200        # a hazard type nobody has seen appears here
    arena: float = 60.0
    objects: int = 10            # per fly
    dim: int = 64                # odor vector size
    food_types: int = 4
    hazard_types: int = 4        # plus one novel type introduced at novel_step
    instance_noise: float = 0.5  # norm of per-object noise around its type
    sensor_noise: float = 0.15   # norm of per-sniff noise
    sense_radius: float = 8.0
    contact_radius: float = 1.5
    speed: float = 1.0
    stings_to_die: int = 3
    match_threshold: float = 0.6  # cosine needed to trust a memory
    top_k: int = 5
    seed: int = 0


def unit(v):
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


class World:
    def __init__(self, cfg: Config, rng: np.random.Generator):
        self.cfg, self.rng = cfg, rng
        c = cfg
        n_types = c.food_types + c.hazard_types + 1
        self.type_vec = unit(rng.standard_normal((n_types, c.dim)))
        # one hazard deliberately smells a bit like a food (a baited trap)
        f0, h0 = 0, c.food_types
        self.type_vec[h0] = unit(0.5 * self.type_vec[f0] + 0.87 * self.type_vec[h0])
        self.is_hazard = np.zeros(n_types, bool)
        self.is_hazard[c.food_types:] = True
        self.novel_type = n_types - 1
        self.active_types = np.arange(n_types - 1)  # novel type locked until novel_step

        F, M = c.flies, c.objects
        self.obj_pos = rng.uniform(0, c.arena, (F, M, 2))
        # half food, half hazard to start
        self.obj_type = np.empty((F, M), int)
        self.obj_type[:, : M // 2] = rng.integers(0, c.food_types, (F, M // 2))
        self.obj_type[:, M // 2 :] = rng.integers(c.food_types, c.food_types + c.hazard_types, (F, M - M // 2))
        self.obj_vec = self._instances(self.obj_type)

    def _instances(self, types):
        c = self.cfg
        noise = self.rng.standard_normal(types.shape + (c.dim,)) * (c.instance_noise / np.sqrt(c.dim))
        return unit(self.type_vec[types] + noise)

    def respawn(self, f, m):
        c = self.cfg
        self.obj_pos[f, m] = self.rng.uniform(0, c.arena, 2)
        # keep the food/hazard balance: a hazard respawns as a hazard type
        if self.is_hazard[self.obj_type[f, m]]:
            pool = [t for t in self.active_types if self.is_hazard[t]]
        else:
            pool = [t for t in self.active_types if not self.is_hazard[t]]
        t = self.rng.choice(pool)
        self.obj_type[f, m] = t
        self.obj_vec[f, m] = self._instances(np.array(t))

    def introduce_novel(self):
        """Every fly gets one object of a hazard type nobody has met."""
        self.active_types = np.append(self.active_types, self.novel_type)
        F, M = self.obj_type.shape
        for f in range(F):
            m = self.rng.integers(M // 2, M)  # replace one hazard slot
            self.obj_type[f, m] = self.novel_type
            self.obj_vec[f, m] = self._instances(np.array(self.novel_type))
            self.obj_pos[f, m] = self.rng.uniform(0, self.cfg.arena, 2)


class FleetMemory:
    """The shared cloud memory. Qdrant local mode stands in for a cluster."""

    def __init__(self, cfg: Config, keyed_by: str):
        self.cfg, self.keyed_by = cfg, keyed_by
        self.client = QdrantClient(":memory:")
        size = cfg.dim if keyed_by == "odor" else 2
        dist = models.Distance.COSINE if keyed_by == "odor" else models.Distance.EUCLID
        self.client.create_collection("fleet", vectors_config=models.VectorParams(size=size, distance=dist))
        self.next_id = 0
        self.pending = []
        self.writes = 0
        self.bytes_up = 0
        self.queries = 0
        self.query_bytes_up = 0
        self.query_seconds = 0.0
        self.log = []  # (step, fly, vector) of every upload, for the replay

    def remember(self, vec, danger, fly, step, kind=-1):
        # kind (what the object really was) is for the replay only; no decision ever reads it
        self.pending.append(models.PointStruct(
            id=self.next_id, vector=vec.tolist(),
            payload={"danger": bool(danger), "fly": int(fly), "step": int(step), "kind": int(kind)}))
        self.log.append((int(step), int(fly), vec))
        self.next_id += 1
        self.writes += 1
        self.bytes_up += len(vec) * 4 + 24  # float32 vector + small payload

    def flush(self):
        if self.pending:
            self.client.upsert("fleet", self.pending, wait=True)
            self.pending = []

    def recall(self, vecs):
        """Batch query. Returns per query: (danger_score, food_score, best_score, hits)."""
        if not vecs:
            return []
        c = self.cfg
        if self.keyed_by == "odor":
            reqs = [models.QueryRequest(query=v.tolist(), limit=c.top_k, score_threshold=c.match_threshold,
                                        with_payload=True) for v in vecs]
        else:  # location: anything that happened within 3 units of here
            reqs = [models.QueryRequest(query=v.tolist(), limit=c.top_k, score_threshold=3.0,
                                        with_payload=True) for v in vecs]
        t0 = time.perf_counter()
        res = self.client.query_batch_points("fleet", reqs)
        self.query_seconds += time.perf_counter() - t0
        self.queries += len(vecs)
        self.query_bytes_up += sum(len(v) * 4 for v in vecs)  # a question sends its vector up too
        out = []
        for r in res:
            d = sum(1.0 for p in r.points if p.payload["danger"])
            fd = sum(1.0 for p in r.points if not p.payload["danger"])
            best = r.points[0].score if r.points else None
            hits = [(p.payload["kind"], round(float(p.score), 3), p.payload["danger"], p.payload["fly"], p.payload["step"], p.id)
                    for p in r.points]
            out.append((d, fd, best, hits))
        return out


def run(cfg: Config, condition: str, trace=()):
    """trace: fly ids to record step by step for the replay page. Recording never changes the run."""
    rng = np.random.default_rng(cfg.seed)
    world = World(cfg, rng)
    beh = np.random.default_rng(cfg.seed + 1000)  # behaviour noise, separate stream
    F, M = cfg.flies, cfg.objects

    use_local = condition != "naive"
    fleet = None
    if condition in ("shared", "shuffled"):
        fleet = FleetMemory(cfg, "odor")
    elif condition == "location":
        fleet = FleetMemory(cfg, "location")

    pos = beh.uniform(0, cfg.arena, (F, 2))
    heading = beh.uniform(0, 2 * np.pi, F)
    alive = np.ones(F, bool)
    stings = np.zeros(F, int)
    food = np.zeros(F, int)
    decision = np.zeros((F, M), int)      # 0 undecided, 1 approach, -1 avoid
    decided_by = np.zeros((F, M), int)    # 0 innate, 1 local, 2 fleet
    expected = np.zeros((F, M), int)      # what memory predicted: 1 danger, -1 safe, 0 no idea
    local_vecs = [[] for _ in range(F)]
    local_lab = [[] for _ in range(F)]
    met_type = np.zeros((F, cfg.food_types + cfg.hazard_types + 1), bool)

    first_meet = {"avoided": 0, "total": 0, "food_avoided": 0, "food_total": 0}
    novel_first_meet = []                            # (step, avoided) for the novel hazard
    novel_first_contact_step = None
    per_step = {k: [] for k in ("stings", "food", "alive", "writes", "queries", "local_hits", "fleet_hits")}
    local_hits_total = 0
    fleet_hits_total = 0
    sniffs_total = 0
    t_start = time.perf_counter()

    traced = set(int(f) for f in trace)
    tr = {"flies": sorted(traced), "events": [], "pos": [], "alive": [],
          "obj_pos": world.obj_pos[sorted(traced)].round(2).tolist(),
          "obj_type": world.obj_type[sorted(traced)].tolist()}

    def ev(step, f, kind, **kw):
        if f in traced:
            tr["events"].append({"s": step, "f": int(f), "k": kind, **kw})

    def spawn_ev(step, f, m, kind="spawn"):
        if f in traced:
            ev(step, f, kind, m=int(m), x=round(float(world.obj_pos[f, m, 0]), 2),
               y=round(float(world.obj_pos[f, m, 1]), 2), t=int(world.obj_type[f, m]))

    for step in range(cfg.steps):
        if step == cfg.novel_step:
            before = world.obj_type.copy()
            world.introduce_novel()
            decision[:] = 0
            for f in traced:
                for m in np.flatnonzero(world.obj_type[f] != before[f]):
                    spawn_ev(step, f, m, "novel")
        writes0 = fleet.writes if fleet else 0
        queries0 = fleet.queries if fleet else 0
        lh0, fh0 = local_hits_total, fleet_hits_total

        diff = world.obj_pos - pos[:, None, :]
        dist = np.linalg.norm(diff, axis=-1)
        in_range = (dist < cfg.sense_radius) & alive[:, None]
        decision[~in_range & (dist > cfg.sense_radius * 1.5)] = 0

        # --- 1. decide about newly sensed objects: local first, fleet if unsure
        need = np.argwhere(in_range & (decision == 0))
        sniffs_total += len(need)
        sniffs = {}
        to_fleet = []
        for f, m in need:
            sniff = unit(world.obj_vec[f, m] + beh.standard_normal(cfg.dim) * (cfg.sensor_noise / np.sqrt(cfg.dim)))
            sniffs[(f, m)] = sniff
            decision[f, m], decided_by[f, m], expected[f, m] = 1, 0, 0
            if use_local and local_vecs[f] and condition != "location":
                sims = np.array(local_vecs[f]) @ sniff
                i = int(np.argmax(sims))
                if sims[i] >= cfg.match_threshold:
                    danger = local_lab[f][i]
                    decision[f, m] = -1 if danger else 1
                    decided_by[f, m] = 1
                    expected[f, m] = 1 if danger else -1
                    local_hits_total += 1
                    ev(step, f, "local", m=int(m), t=int(world.obj_type[f, m]), danger=bool(danger))
                    continue
            if fleet is not None:
                to_fleet.append((f, m))

        if to_fleet:
            keys = [sniffs[k] if fleet.keyed_by == "odor" else world.obj_pos[k] for k in to_fleet]
            for (f, m), (d, fd, best, hits) in zip(to_fleet, fleet.recall(keys)):
                if best is None:
                    ev(step, f, "ask", m=int(m), t=int(world.obj_type[f, m]), answer="nothing", hits=[],
                   vec=sniffs[(f, m)].round(4).tolist() if f in traced else None)
                    continue
                danger = d > fd
                ev(step, f, "ask", m=int(m), t=int(world.obj_type[f, m]), answer="danger" if danger else "safe",
                   score=round(float(best), 2), hits=hits, vec=sniffs[(f, m)].round(4).tolist() if f in traced else None)
                decision[f, m] = -1 if danger else 1
                decided_by[f, m] = 2
                expected[f, m] = 1 if danger else -1
                fleet_hits_total += 1
                if fleet.keyed_by == "odor":   # cache what the cloud said
                    local_vecs[f].append(sniffs[(f, m)])
                    local_lab[f].append(danger)

        # first-meeting bookkeeping: the first time this fly meets each odor type
        for f, m in need:
            t = world.obj_type[f, m]
            if met_type[f, t]:
                continue
            met_type[f, t] = True
            av = decision[f, m] == -1
            if t == world.novel_type:
                novel_first_meet.append((step, bool(av)))
            elif world.is_hazard[t]:
                first_meet["total"] += 1
                first_meet["avoided"] += int(av)
            else:
                first_meet["food_total"] += 1
                first_meet["food_avoided"] += int(av)

        # --- 2. move: flee the nearest avoided object, else chase the nearest approached one, else wander
        d_avoid = np.where(in_range & (decision == -1), dist, np.inf)
        d_go = np.where(in_range & (decision == 1), dist, np.inf)
        ia, ig = d_avoid.argmin(1), d_go.argmin(1)
        flee = np.isfinite(d_avoid[np.arange(F), ia]) & (d_avoid[np.arange(F), ia] < 5.0)
        chase = ~flee & np.isfinite(d_go[np.arange(F), ig])
        heading += beh.normal(0, 0.4, F)
        v = np.stack([np.cos(heading), np.sin(heading)], 1)
        away = -diff[np.arange(F), ia]
        toward = diff[np.arange(F), ig]
        v[flee] = unit(away[flee] + 1e-9)
        v[chase] = unit(toward[chase] + 1e-9)
        heading[flee | chase] = np.arctan2(v[flee | chase, 1], v[flee | chase, 0])
        pos = np.where(alive[:, None], pos + cfg.speed * v, pos)
        out = (pos < 0) | (pos > cfg.arena)
        pos = np.clip(pos, 0, cfg.arena)
        heading[out.any(1)] += np.pi

        # --- 3. contact: learn locally, escalate to the fleet only if surprised
        dist = np.linalg.norm(world.obj_pos - pos[:, None, :], axis=-1)
        hits = np.argwhere((dist < cfg.contact_radius) & alive[:, None])
        s_step = f_step = 0
        for f, m in hits:
            t = world.obj_type[f, m]
            danger = bool(world.is_hazard[t])
            if danger:
                stings[f] += 1
                s_step += 1
                if stings[f] >= cfg.stings_to_die:
                    alive[f] = False
                if t == world.novel_type and novel_first_contact_step is None:
                    novel_first_contact_step = step
            else:
                food[f] += 1
                f_step += 1
            vec = sniffs.get((f, m))
            if vec is None:
                vec = unit(world.obj_vec[f, m] + beh.standard_normal(cfg.dim) * (cfg.sensor_noise / np.sqrt(cfg.dim)))
            if use_local and condition != "location":
                local_vecs[f].append(vec)
                local_lab[f].append(danger)
            surprised = expected[f, m] != (1 if danger else -1)
            ev(step, f, "sting" if danger else "eat", m=int(m), t=int(t), dead=bool(not alive[f]))
            if fleet is not None and surprised:
                label = bool(beh.integers(2)) if condition == "shuffled" else danger
                key = vec if fleet.keyed_by == "odor" else pos[f].copy()
                fleet.remember(key, label, f, step, kind=t)
                tr.setdefault("uploads", []).append((int(step), int(f), int(t), bool(label)))
                ev(step, f, "upload", m=int(m))
            world.respawn(f, m)
            spawn_ev(step, f, m)
            decision[f, m] = 0
        if fleet:
            fleet.flush()

        if traced:
            tr["pos"].append(pos[tr["flies"]].round(2).tolist())
            tr["alive"].append(alive[tr["flies"]].astype(int).tolist())
        per_step["stings"].append(s_step)
        per_step["food"].append(f_step)
        per_step["alive"].append(int(alive.sum()))
        per_step["writes"].append((fleet.writes - writes0) if fleet else 0)
        per_step["queries"].append((fleet.queries - queries0) if fleet else 0)
        per_step["local_hits"].append(local_hits_total - lh0)
        per_step["fleet_hits"].append(fleet_hits_total - fh0)

    nf = np.array([a for _, a in novel_first_meet], bool)
    firehose_bytes = F * cfg.steps * (cfg.dim * 4 + 8)  # every fly streams every sniff + position
    return {
        "condition": condition,
        "seed": cfg.seed,
        "flies": F,
        "stings_per_fly": float(stings.mean()),
        "food_per_fly": float(food.mean()),
        "survival": float(alive.mean()),
        "first_meeting_avoided": first_meet["avoided"] / max(first_meet["total"], 1),
        "first_meeting_food_avoided": first_meet["food_avoided"] / max(first_meet["food_total"], 1),
        # right call on first meeting = avoid the hazard, go for the food (0.5 = coin flip at best)
        "first_meeting_right_call": (first_meet["avoided"] + first_meet["food_total"] - first_meet["food_avoided"])
                                    / max(first_meet["total"] + first_meet["food_total"], 1),
        "novel_first_meeting_avoided": float(nf.mean()) if len(nf) else None,
        "novel_first_contact_step": novel_first_contact_step,
        "fleet_writes": fleet.writes if fleet else 0,
        "fleet_queries": fleet.queries if fleet else 0,
        "bytes_up": fleet.bytes_up if fleet else 0,                 # memories uploaded
        "query_bytes_up": fleet.query_bytes_up if fleet else 0,     # questions asked
        "total_upstream_bytes": (fleet.bytes_up + fleet.query_bytes_up) if fleet else 0,
        "sniffs": sniffs_total,
        "every_sniff_to_cloud_bytes": sniffs_total * cfg.dim * 4,   # no on-board memory: cloud decides everything
        "firehose_bytes": firehose_bytes,
        "query_ms_per_query": (1000 * fleet.query_seconds / fleet.queries) if fleet and fleet.queries else None,
        "local_hits": local_hits_total,
        "fleet_hits": fleet_hits_total,
        "wall_seconds": time.perf_counter() - t_start,
        "novel_first_meet": novel_first_meet,
        "per_step": per_step,
        "trace": tr,
        "fleet_log": fleet.log if fleet else [],
    }


if __name__ == "__main__":
    cond = sys.argv[1] if len(sys.argv) > 1 else "shared"
    flies = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    r = run(Config(flies=flies, seed=seed), cond)
    for k in ("per_step", "novel_first_meet", "trace", "fleet_log"):
        r.pop(k)
    print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()})
