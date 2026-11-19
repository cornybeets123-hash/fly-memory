"""Measure how closely each recorded memory condition behaves like a hive.

Reads a prepared recording directory (default: _internal/artifacts/webinar-hive) and
prints Markdown tables. It only reads saved evidence; it never simulates.

    uv run python _maintainer/hive_fidelity.py [DIRECTORY]

A hive is many flies writing to, and reading from, one memory while they run. The
measures below ask, per condition: does memory grow during the run, do flies use
evidence written by others, do they read their own writes, and how soon does shared
evidence start changing decisions.
"""

import gzip
import json
import sys
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
CONDITIONS = ("none", "personal", "inherited", "shared")
LABELS = {
    "none": "No memory",
    "personal": "Personal",
    "inherited": "Inherited",
    "shared": "Shared hive",
}
BIN_MS = 30_000


def read_json(path):
    return json.loads(Path(path).read_text())


def read_gzip(path):
    with gzip.open(path, "rt") as source:
        return json.load(source)


def fly_runs(directory, condition, count):
    for index in range(count):
        yield read_gzip(directory / f"{condition}-{index}.json.gz")


def measure(directory, condition, status):
    """One pass over every fly of a condition."""
    count = status["count"]
    queries = applied = hits = self_hits = 0
    uses = own = 0
    sources = set()
    first_use, bins = [], {}
    causal_violations = 0
    for index, run in enumerate(fly_runs(directory, condition, count)):
        owner, first = run["owner"], None
        for d in run["decisions"]:
            for view in d["views"]:
                if view["vector"] is not None and view["search_ms"] is not None:
                    queries += 1
                    bin_ = d["time"] // BIN_MS
                    q, a = bins.get(bin_, (0, 0))
                    bins[bin_] = (q + 1, a + bool(view["applied"]))
                for hit in view["hits"]:
                    hits += 1
                    self_hits += hit["payload"]["source_fly"] == owner
                    if condition == "shared":
                        written = hit["payload"]["observed_at_ms"] - 100
                        causal_violations += written > d["time"]
                if view["applied"]:
                    applied += 1
                    source = view["selected"]["payload"]["source_fly"]
                    sources.add(source)
                    uses += 1
                    own += source == owner
                    first = d["time"] if first is None else min(first, d["time"])
        if first is not None:
            first_use.append(first)
    return {
        "queries": queries,
        "applied": applied,
        "hits": hits,
        "self_hits": self_hits,
        "uses": uses,
        "own": own,
        "sources": len(sources),
        "first_use": first_use,
        "bins": bins,
        "violations": causal_violations,
    }


def memory_size(status, summary_file, condition, at_ms):
    if condition == "shared":
        return sum(t <= at_ms for t in summary_file["memory_times"])
    if condition == "inherited":
        return status.get("inherited_memory_count")
    return None


def percent(part, whole):
    return f"{100 * part / whole:.0f}%" if whole else "n/a"


def report(directory):
    directory = Path(directory)
    status = read_json(directory / "status.json")
    count = status["count"]
    ready = [c for c in CONDITIONS if c in status["ready"]]
    summaries = {c: read_json(directory / f"{c}.json") for c in ready}
    stats = {c: measure(directory, c, status) for c in ready}
    out = [
        f"# Hive fidelity ({count} flies per condition, seeds {status['seed']}+)",
        "",
    ]

    out += ["## Outcomes", "", "| Condition | Exits | Mean time (s) | Memory uses |"]
    out += ["| --- | --- | --- | --- |"]
    for c in ready:
        s = status["summary"][c]
        out.append(
            f"| {LABELS[c]} | {s['exited']}/{s['count']} | "
            f"{s['mean_time_ms'] / 1000:.1f} | {s['memory_uses']} |"
        )

    out += ["", "## Memory during the run", ""]
    out += [
        "| Condition | Stored at 0 s | at 60 s | at end |",
        "| --- | --- | --- | --- |",
    ]
    for c in ("inherited", "shared"):
        if c not in ready:
            continue
        end = status["deadline_seconds"] * 1000
        sizes = [memory_size(status, summaries[c], c, t) for t in (0, 60_000, end)]
        out.append(f"| {LABELS[c]} | " + " | ".join(str(s) for s in sizes) + " |")
    out.append("| Personal | 0 (per fly) | grows per fly | grows per fly |")

    out += ["", "## Who supplies the evidence", ""]
    out += [
        "| Condition | Retrieved hits | Hits from the fly itself | Applied evidence | "
    ]
    out[-1] += "From its own writes | Distinct source flies |"
    out += ["| --- | --- | --- | --- | --- | --- |"]
    for c in ready:
        if c == "none":
            continue
        m = stats[c]
        out.append(
            f"| {LABELS[c]} | {m['hits']} | {percent(m['self_hits'], m['hits'])} | "
            f"{m['uses']} | {percent(m['own'], m['uses'])} | {m['sources']} |"
        )

    out += ["", "## When shared evidence starts to matter", ""]
    out += ["| Condition | Median first applied (s) | Flies that used memory |"]
    out += ["| --- | --- | --- |"]
    for c in ready:
        if c == "none":
            continue
        first = stats[c]["first_use"]
        when = f"{median(first) / 1000:.1f}" if first else "never"
        out.append(f"| {LABELS[c]} | {when} | {len(first)}/{count} |")

    out += ["", "## Share of searches that changed a decision, by simulated time", ""]
    top = max((max(stats[c]["bins"], default=0) for c in ready), default=0)
    out += [
        "| Condition | "
        + " | ".join(f"{b * 30}-{b * 30 + 30} s" for b in range(top + 1))
        + " |"
    ]
    out += ["| --- | " + " | ".join("---" for _ in range(top + 1)) + " |"]
    for c in ready:
        if c == "none":
            continue
        cells = []
        for b in range(top + 1):
            asked, used = stats[c]["bins"].get(b, (0, 0))
            cells.append(percent(used, asked))
        out.append(f"| {LABELS[c]} | " + " | ".join(cells) + " |")

    if "shared" in ready:
        out += [
            "",
            f"Hive reads of observations written after the decision: {stats['shared']['violations']} (must be 0).",
        ]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    target = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else ROOT / "_internal/artifacts/webinar-hive"
    )
    sys.stdout.write(report(target))
