"""Reproduce the published whole-brain model recording protocol used by the workshop."""

import argparse
import ast
import hashlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
parser = argparse.ArgumentParser(
    description="Regenerate 48 actual Shiu neural trials. Takes about eight minutes."
)
parser.add_argument("--output", type=Path, default=ROOT / "artifacts/new-brain-bank")
args = parser.parse_args()
from workshop.__main__ import setup_brain

setup_brain()
OUT = args.output
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "spikes").mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT / "brain"))
import brian2 as b

b.prefs.codegen.target = "numpy"
import model as shiu

# Read constants without importing the demo application.
tree = ast.parse((ROOT / "brain_demo.py").read_text())
constants = {}
for node in tree.body:
    if isinstance(node, ast.Assign):
        try:
            value = ast.literal_eval(node.value)
        except (ValueError, TypeError):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                constants[target.id] = value
            elif isinstance(target, ast.Tuple):
                for name, val in zip(target.elts, value):
                    constants[name.id] = val
pairs = {
    "MN9": [constants["MN9_L"], constants["MN9_R"]],
    "P9-oDN1": [720575940620300308, 720575940626730883],
    "FG": [720575940611160930, 720575940628755815],
    "P9": [720575940627652358, 720575940635872101],
}
neurons = {"sugar": constants["NEU_SUGAR"], "bitter": constants["NEU_BITTER"], **pairs}
comp = ROOT / "brain/2023_03_23_completeness_630_final.csv"
con = ROOT / "brain/2023_03_23_connectivity_630_final.parquet"


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


files = [
    {"path": str(p.relative_to(ROOT)), "sha256": sha(p)}
    for p in [
        ROOT / "brain/model.py",
        comp,
        con,
        ROOT / "brain_demo.py",
        Path(__file__).resolve(),
    ]
]
ids = pd.read_csv(comp, index_col=0).index
f2i = {int(f): i for i, f in enumerate(ids)}
groups = {k: [f2i[n] for n in ns] for k, ns in neurons.items()}
t0 = time.time()
p = shiu.default_params
neu, syn, mon = shiu.create_model(comp, con, p)
net = b.Network(neu, syn, mon)
net.store("naive")
params = {
    k: (
        {"si_value": float(v), "representation": str(v)}
        if isinstance(v, b.Quantity)
        else v
    )
    for k, v in p.items()
}
protocol = {
    "duration_s": float(p["t_run"]),
    "bin_hz": 40,
    "bin_edges_s": np.linspace(0, 1, 41).tolist(),
    "gate": {"readout": "MN9_L", "operator": ">", "threshold_hz": 10},
    "neuron_ids": {k: [str(n) for n in ns] for k, ns in neurons.items()},
    "neuron_indices": groups,
    "trace_unit": "spike_count_per_bin",
    "reset": "restore identical naive network state before each trial; seed Brian2 with the stated seed; zero refractory period on stimulated neurons only, as upstream poi() does",
    "conditions": "P9 bilateral 150 Hz plus sugar 150 Hz and bitter 0,50,100,150,200 Hz; P9-only baseline 150 Hz",
    "seeds": list(range(100, 108)),
}
bank = {
    "schema_version": 1,
    "provenance": {
        "upstream_url": "https://github.com/philshiu/Drosophila_brain_model",
        "upstream_sha": subprocess.check_output(
            ["git", "-C", str(ROOT / "brain"), "rev-parse", "HEAD"], text=True
        ).strip(),
        "upstream_worktree_clean": not bool(
            subprocess.check_output(
                ["git", "-C", str(ROOT / "brain"), "status", "--porcelain"], text=True
            ).strip()
        ),
        "files": files,
        "neuron_count": len(neu),
        "synapse_count": len(syn),
        "backend": "numpy",
        "versions": {
            "python": platform.python_version(),
            "brian2": b.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "parameters": params,
        "dt_s": float(b.defaultclock.dt),
        "build_s": round(time.time() - t0, 3),
    },
    "protocol": protocol,
    "trials": [],
    "summary": [],
}


def save():
    (OUT / "brain-bank.json").write_text(json.dumps(bank, separators=(",", ":")) + "\n")


save()
print("BUILT", len(neu), len(syn), flush=True)
conditions = [
    (f"p9-sugar-bitter-{rate}", {"P9": 150.0, "sugar": 150.0, "bitter": float(rate)})
    for rate in [0, 50, 100, 150, 200]
] + [("p9-only", {"P9": 150.0, "sugar": 0.0, "bitter": 0.0})]
for cond, rates in conditions:
    for seed in range(100, 108):
        net.restore("naive")
        b.seed(seed)
        inputs = []
        for group, rate in rates.items():
            if not rate:
                continue
            for i in groups[group]:
                neu[i].rfc = 0 * b.ms
                inputs.append(
                    b.PoissonInput(neu[i], "v", 1, rate * b.Hz, p["w_syn"] * p["f_poi"])
                )
        net.add(inputs)
        t = time.time()
        net.run(p["t_run"])
        wall = time.time() - t
        ix = np.asarray(mon.i[:], dtype=np.int32)
        ts = np.asarray(mon.t[:] / b.second, dtype=np.float64)
        net.remove(inputs)
        counts = np.bincount(ix, minlength=len(neu))
        trial_id = f"{cond}-seed-{seed}"
        path = OUT / "spikes" / f"{trial_id}.npz"
        np.savez_compressed(path, neuron_index=ix, time_s=ts)
        traces = {}
        readouts = {}
        for group, indices in groups.items():
            hist = [
                np.histogram(ts[ix == i], bins=protocol["bin_edges_s"])[0]
                .astype(int)
                .tolist()
                for i in indices
            ]
            traces[group] = (
                np.sum(hist, axis=0).tolist() if group in ["sugar", "bitter"] else hist
            )
            if group in ["MN9", "P9-oDN1", "FG"]:
                readouts[group] = [
                    float(counts[i]) / protocol["duration_s"] for i in indices
                ]
        row = {
            "id": trial_id,
            "condition": cond,
            "seed": seed,
            "stimulation_hz": rates,
            "duration_s": protocol["duration_s"],
            "wall_s": round(wall, 3),
            "readouts_hz": readouts,
            "feeding": bool(readouts["MN9"][0] > 10),
            "traces": traces,
            "active_neurons": int(np.count_nonzero(counts)),
            "total_spikes": len(ix),
            "raw_spikes_file": "spikes/" + path.name,
            "raw_spikes_sha256": sha(path),
        }
        bank["trials"].append(row)
        save()
        print(
            json.dumps(
                {
                    k: row[k]
                    for k in ["id", "wall_s", "readouts_hz", "feeding", "total_spikes"]
                }
            ),
            flush=True,
        )
for cond, rates in conditions:
    rows = [r for r in bank["trials"] if r["condition"] == cond]
    bank["summary"].append(
        {
            "condition": cond,
            "trials": len(rows),
            "feeding_trials": sum(r["feeding"] for r in rows),
            "mn9_left_mean_hz": float(
                np.mean([r["readouts_hz"]["MN9"][0] for r in rows])
            ),
        }
    )
bank["total_wall_s"] = round(time.time() - t0, 3)
save()
# Full integrity audit from the recorded raw spikes.
for row in bank["trials"]:
    path = OUT / row["raw_spikes_file"]
    assert sha(path) == row["raw_spikes_sha256"]
    raw = np.load(path)
    ix = raw["neuron_index"]
    ts = raw["time_s"]
    assert len(ix) == row["total_spikes"]
    assert np.all((ts >= 0) & (ts < 1))
    assert np.all((ix >= 0) & (ix < len(neu)))
    for group in ["MN9", "P9-oDN1", "FG"]:
        for side, i in enumerate(groups[group]):
            assert (
                int(np.sum(ix == i))
                == sum(row["traces"][group][side])
                == row["readouts_hz"][group][side]
            )
    assert row["feeding"] == (row["readouts_hz"]["MN9"][0] > 10)
assert len(bank["trials"]) == 48
assert all(sha(ROOT / f["path"]) == f["sha256"] for f in files)
checks = {
    str(p.relative_to(OUT)): sha(p)
    for p in sorted(OUT.rglob("*"))
    if p.is_file() and p.name != "checksums.json"
}
(OUT / "checksums.json").write_text(json.dumps(checks, indent=2) + "\n")
print("COMPLETE", json.dumps(bank["summary"]), flush=True)
