"""Serialize verified simulation records for the room display."""

import base64
import binascii
import struct
import zlib

from .vision import image_hash, snapshot


def image_url(image):
    def chunk(kind, data):
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)
        )

    height, width = image.shape[:2]
    rows = b"".join(b"\0" + row.tobytes() for row in image)
    png = b"\x89PNG\r\n\x1a\n" + chunk(
        b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    )
    png += chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")
    return "data:image/png;base64," + base64.b64encode(png).decode()


def record(episode):
    return {
        "id": str(episode.point.id),
        "payload": episode.point.payload,
        "image_url": image_url(episode.image),
    }


def pack(result, world):
    packed = {key: value for key, value in result.items() if key != "episodes"}
    packed["observations"] = [record(e) for e in result["episodes"]]
    frames = {f["ms"]: f for f in result["frames"]}
    decisions = []
    for decision in result["decisions"]:
        frame = frames[decision["time"]]
        views = []
        for view in decision["views"]:
            bearing = view.get("camera_bearing", frame["heading"] + view["bearing"])
            image = (
                snapshot(world, frame["x"], frame["y"], bearing)
                if bearing is not None
                else None
            )
            if image is not None and image_hash(image) != view["snapshot"]:
                raise ValueError(
                    "The displayed view differs from its captured observation."
                )
            item = {
                **view,
                "image_url": image_url(image) if image is not None else None,
            }
            item["hits"] = [{**hit, "id": str(hit["id"])} for hit in view["hits"]]
            item["selected"] = (
                {**view["selected"], "id": str(view["selected"]["id"])}
                if view["selected"]
                else None
            )
            views.append(item)
        decisions.append({**decision, "views": views})
    packed["decisions"] = decisions
    # Events share the same decisions; keep one copy of their image arrays.
    packed["events"] = [e for e in result["events"] if e["kind"] != "junction"]
    return packed


def scene(world):
    return {
        "rectangles": world.rectangles,
        "walls": world.walls.tolist(),
        "landmarks": world.landmarks,
        "start": getattr(world, "launch", (40, 0, 0)),
        "exit": getattr(world, "exit_marker", (610, 260)),
        "bounds": [
            min(r[0] for r in world.rectangles),
            min(r[2] for r in world.rectangles),
            max(r[1] for r in world.rectangles),
            max(r[3] for r in world.rectangles),
        ],
    }
