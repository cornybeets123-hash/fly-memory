"""Run every condition across seeds, plus a fleet-size sweep. Writes results.json and charts/."""
import json
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sim import Config, run

SEEDS = range(5)
CONDITIONS = ["naive", "private", "shared", "shuffled", "location"]
SIZES = [1, 10, 100, 1000]
SCALARS = ["stings_per_fly", "food_per_fly", "survival", "first_meeting_avoided", "first_meeting_food_avoided",
           "first_meeting_right_call", "novel_first_meeting_avoided", "fleet_writes", "fleet_queries",
           "bytes_up", "query_bytes_up", "total_upstream_bytes", "sniffs", "every_sniff_to_cloud_bytes", "firehose_bytes", "query_ms_per_query", "local_hits", "fleet_hits", "wall_seconds"]


def ci(xs):
    xs = np.array([x for x in xs if x is not None], float)
    if len(xs) == 0:
        return None
    half = 1.96 * xs.std(ddof=1) / np.sqrt(len(xs)) if len(xs) > 1 else 0.0
    return {"mean": float(xs.mean()), "ci95": float(half), "n": int(len(xs))}


def summarize(runs):
    return {k: ci([r[k] for r in runs]) for k in SCALARS}


def main():
    os.makedirs("charts", exist_ok=True)
    out = {"config": Config().__dict__, "conditions": {}, "sizes": {}}
    raw = {}
    for c in CONDITIONS:
        runs = [run(Config(seed=s), c) for s in SEEDS]
        raw[c] = runs
        out["conditions"][c] = summarize(runs)
        print(c, {k: round(v["mean"], 3) for k, v in out["conditions"][c].items() if v})

    # fleet size: does a bigger fleet teach each fly faster? (more seeds for tiny fleets)
    for n in SIZES:
        seeds = range(200) if n == 1 else range(40) if n == 10 else range(10) if n == 100 else SEEDS
        runs = raw["shared"] if n == 1000 else [run(Config(flies=n, seed=s), "shared") for s in seeds]
        out["sizes"][n] = summarize(runs)
        print("size", n, round(out["sizes"][n]["first_meeting_right_call"]["mean"], 3))

    # novel hazard: share of first meetings avoided, by steps since it appeared
    bins = np.arange(0, 201, 10)
    novel = {}
    for c in ["private", "shared"]:
        meets = [(st - Config().novel_step, a) for r in raw[c] for st, a in r["novel_first_meet"]]
        rate = []
        for lo, hi in zip(bins[:-1], bins[1:]):
            sel = [a for d, a in meets if lo <= d < hi]
            rate.append(float(np.mean(sel)) if sel else None)
        novel[c] = rate
    out["novel_curve"] = {"bin_start": bins[:-1].tolist(), **novel}

    # writes per step, shared fleet: escalation tapers off as the fleet learns
    out["writes_per_step"] = np.mean([r["per_step"]["writes"] for r in raw["shared"]], 0).tolist()
    out["queries_per_step"] = np.mean([r["per_step"]["queries"] for r in raw["shared"]], 0).tolist()

    with open("results.json", "w") as f:
        json.dump(out, f, indent=1)
    charts(out)


COLORS = {"naive": "#9aa3ad", "private": "#6b7c93", "shared": "#dc244c", "shuffled": "#c9b98f", "location": "#b7c4a7"}


def bar(ax, out, key, title, pct=True):
    cs = CONDITIONS
    m = [out["conditions"][c][key]["mean"] for c in cs]
    e = [out["conditions"][c][key]["ci95"] for c in cs]
    ax.bar(cs, m, yerr=e, color=[COLORS[c] for c in cs], capsize=4)
    ax.set_title(title, loc="left", fontsize=11)
    if pct:
        ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.spines[["top", "right"]].set_visible(False)


def charts(out):
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    bar(axes[0], out, "first_meeting_right_call", "Right call the first time a fly meets an odor")
    axes[0].axhline(0.5, color="#333", lw=0.8, ls="--")
    bar(axes[1], out, "food_per_fly", "Food found per fly", pct=False)
    bar(axes[2], out, "survival", "Flies alive at the end")
    fig.tight_layout()
    fig.savefig("charts/conditions.png", dpi=160)

    fig, ax = plt.subplots(figsize=(6, 4))
    xs = SIZES
    m = [out["sizes"][n]["first_meeting_right_call"]["mean"] for n in xs]
    e = [out["sizes"][n]["first_meeting_right_call"]["ci95"] for n in xs]
    ax.errorbar(xs, m, yerr=e, marker="o", color=COLORS["shared"], capsize=4)
    ax.set_xscale("log")
    ax.set_xticks(xs, [str(x) for x in xs])
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_xlabel("flies sharing one memory")
    ax.set_title("Right call on first meeting, by fleet size", loc="left", fontsize=11)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig("charts/fleet_size.png", dpi=160)

    fig, ax = plt.subplots(figsize=(6, 4))
    b = out["novel_curve"]["bin_start"]
    for c in ["private", "shared"]:
        ys = [y if y is not None else np.nan for y in out["novel_curve"][c]]
        ax.plot(b, ys, marker="o", ms=3, color=COLORS[c], label=c)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_xlabel("steps since a brand-new hazard appeared")
    ax.set_title("Avoided the new hazard the first time they met it", loc="left", fontsize=11)
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig("charts/novel_hazard.png", dpi=160)

    fig, ax = plt.subplots(figsize=(6, 4))
    w = np.array(out["writes_per_step"])
    q = np.array(out["queries_per_step"])
    ax.plot(q, color="#6b7c93", lw=1, label="questions to the fleet")
    ax.plot(w, color=COLORS["shared"], lw=1.5, label="memories uploaded")
    ax.axvline(out["config"]["novel_step"], color="#333", lw=0.8, ls="--")
    ax.set_xlabel("step")
    ax.set_title("Cloud traffic per step, 1,000 flies", loc="left", fontsize=11)
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig("charts/traffic.png", dpi=160)


if __name__ == "__main__":
    main()
