"""Can the real connectome brain be one fly's on-board brain, with Qdrant as the only thing that learns?

The brain is the Shiu et al. 2024 whole-brain leaky integrate-and-fire model
(github.com/philshiu/Drosophila_brain_model, cloned into ./brain, FlyWire v630:
127,400 neurons, 14.7 M connections). We use its own model.py unchanged and never
touch a synapse. The only thing we change between trials is which taste neurons
receive input, which is how a real fly's brain gets information too.

The loop, per contact with an object:
  1. smell it (odor vector, same odor space as sim.py)
  2. ask the fleet memory in Qdrant: has anyone been hurt by something that smells like this?
  3. taste it: sugar GRNs fire because the object is sweet. If the fleet said "danger",
     bitter GRNs fire too (recalled bitterness, delivered on the real bitter channel)
  4. run the brain for 1 s and read MN9, the proboscis motor neuron. MN9 firing = eat.
  5. if eating it hurt and the fly did not expect that, escalate the experience to Qdrant

Story:
  case 1  fly 0, empty fleet memory, meets a baited trap (sweet, smells partly like food) -> eats, gets stung, uploads
  case 2  fly 1 meets a *different* trap of the same type, fleet now holds fly 0's memory -> recall -> bitter -> no MN9
  case 3  fly 1 meets real food the trap was built from (type cosine 0.42)    -> no recall -> eats

Neuron IDs (FlyWire v630), all from the repo's own notebooks:
  sugar GRNs, 21 right labellar  example.ipynb (neu_sugar), figures.ipynb Fig 1D / 3A
  bitter GRNs, 21                 figures.ipynb Fig 3A (neu_bitter)
  MN9 left  720575940660219265    example.ipynb (id_mn9), figures.ipynb Fig 1E / 3A
  MN9 right 720575940645521262    figures.ipynb Fig 2 (ids_mn9)

Run from fly-memory/ (./brian_preferences selects Brian2's numpy target; this
machine has no C compiler, so Cython codegen is unavailable):
    .venv-brain/Scripts/python brain_demo.py [trials_per_case] [--sweep]
--sweep adds a bitter dose-response (50, 100, 200 Hz, half as many trials each), so the
curve is visible and not just the one preset point.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE / 'brain'))
import model as shiu  # noqa: E402  (the repo's model.py, unchanged)
from brian2 import Network, PoissonInput, Hz, seed as brian_seed  # noqa: E402

from sim import Config, World, FleetMemory, unit  # noqa: E402

PATH_COMP = HERE / 'brain' / '2023_03_23_completeness_630_final.csv'
PATH_CON = HERE / 'brain' / '2023_03_23_connectivity_630_final.parquet'

NEU_SUGAR = [
    720575940624963786, 720575940630233916, 720575940637568838, 720575940638202345, 720575940617000768,
    720575940630797113, 720575940632889389, 720575940621754367, 720575940621502051, 720575940640649691,
    720575940639332736, 720575940616885538, 720575940639198653, 720575940620900446, 720575940617937543,
    720575940632425919, 720575940633143833, 720575940612670570, 720575940628853239, 720575940629176663,
    720575940611875570,
]
NEU_BITTER = [
    720575940621778381, 720575940602353632, 720575940617094208, 720575940619197093, 720575940626287336,
    720575940618600651, 720575940627692048, 720575940630195909, 720575940646212996, 720575940610483162,
    720575940645743412, 720575940627578156, 720575940622298631, 720575940621008895, 720575940629146711,
    720575940610259370, 720575940610481370, 720575940619028208, 720575940614281266, 720575940613061118,
    720575940604027168,
]
MN9_L, MN9_R = 720575940660219265, 720575940645521262

SUGAR_HZ = 150.0   # the repo's default r_poi
BITTER_HZ = 150.0  # recalled danger drives bitter GRNs at the same rate; not tuned
EAT_HZ = 10.0      # decision rule fixed before running: MN9 above 10 Hz = proboscis extends


class Brain:
    """One fly's brain: the Shiu model built once, then only its inputs change."""

    def __init__(self, params=shiu.default_params):
        import pandas as pd
        self.p = params
        ids = pd.read_csv(PATH_COMP, index_col=0).index
        f2i = {f: i for i, f in enumerate(ids)}
        self.sugar = [f2i[n] for n in NEU_SUGAR]
        self.bitter = [f2i[n] for n in NEU_BITTER]
        self.mn9_l, self.mn9_r = f2i[MN9_L], f2i[MN9_R]
        self.neu, syn, self.mon = shiu.create_model(PATH_COMP, PATH_CON, params)
        for i in self.sugar + self.bitter:   # what shiu.poi() does to every Poisson target
            self.neu[i].rfc = 0 * shiu.ms
        self.net = Network(self.neu, syn, self.mon)
        self.net.store('naive')
        self.n_neurons, self.n_syn = len(ids), len(syn)
        self.sim_s = 0.0
        self.sim_wall = 0.0

    def taste(self, sugar_hz, bitter_hz, trials, seed0=0):
        """Run `trials` independent 1 s trials. Returns per-trial MN9 rates (Hz), left and right."""
        w = self.p['w_syn'] * self.p['f_poi']
        left, right = [], []
        for k in range(trials):
            self.net.restore('naive')         # same brain, same initial state, every trial
            brian_seed(seed0 + k)
            inputs = [PoissonInput(self.neu[i], 'v', 1, sugar_hz * Hz, w) for i in self.sugar]
            if bitter_hz > 0:
                inputs += [PoissonInput(self.neu[i], 'v', 1, bitter_hz * Hz, w) for i in self.bitter]
            self.net.add(inputs)
            t = time.time()
            self.net.run(self.p['t_run'])
            self.sim_wall += time.time() - t
            self.sim_s += float(self.p['t_run'])
            spk = np.asarray(self.mon.i[:])
            dur = float(self.p['t_run'])
            left.append(np.sum(spk == self.mn9_l) / dur)
            right.append(np.sum(spk == self.mn9_r) / dur)
            self.net.remove(inputs)
        return np.array(left), np.array(right)


def ci95(x):
    return 1.96 * np.std(x, ddof=1) / np.sqrt(len(x)) if len(x) > 1 else float('nan')


def main(trials=10, sweep=False):
    t_start = time.time()
    cfg = Config(flies=2)
    rng = np.random.default_rng(cfg.seed)
    world = World(cfg, rng)                   # same odor space as the toy sim
    sniff_rng = np.random.default_rng(1)
    trap_t, food_t = cfg.food_types, 0         # hazard 0 is the baited trap, built from food 0

    def sniff(t):
        inst = world._instances(np.array(t))
        return unit(inst + sniff_rng.standard_normal(cfg.dim) * (cfg.sensor_noise / np.sqrt(cfg.dim)))

    fleet = FleetMemory(cfg, 'odor')           # QdrantClient(":memory:"), cosine
    print('building brain (Shiu et al. 2024, FlyWire v630) ...', flush=True)
    brain = Brain()
    print(f'  {brain.n_neurons:,} neurons, {brain.n_syn:,} connections', flush=True)

    cache = {}
    results = []

    def encounter(case, fly, t, label):
        odor = sniff(t)
        d, fd, best, _ = fleet.recall([odor])[0]
        recalled_danger = d > fd
        bitter = BITTER_HZ if recalled_danger else 0.0
        key = (SUGAR_HZ, bitter)
        reused = key in cache
        if not reused:
            print(f'  case {case}: running {trials} x 1 s trials (sugar {SUGAR_HZ:.0f} Hz, bitter {bitter:.0f} Hz) ...',
                  flush=True)
            cache[key] = brain.taste(SUGAR_HZ, bitter, trials, seed0=100 * len(cache))
        left, right = cache[key]
        eats = left.mean() > EAT_HZ
        stung = eats and world.is_hazard[t]
        escalated = bool(stung and not recalled_danger)   # surprise: it hurt and nobody warned me
        if escalated:
            fleet.remember(odor, True, fly, case)
            fleet.flush()
        sims = [float(odor @ world.type_vec[x]) for x in (trap_t, food_t)]
        r = dict(case=case, fly=fly, object=label, best_fleet_score=best, recalled_danger=bool(recalled_danger),
                 sugar_hz=SUGAR_HZ, bitter_hz=bitter, mn9_left_hz=float(left.mean()), mn9_left_ci95=float(ci95(left)),
                 mn9_right_hz=float(right.mean()), trials=trials, reused_trials_of_identical_input=reused,
                 eats=bool(eats), stung=bool(stung), escalated=escalated,
                 cos_to_trap_type=sims[0], cos_to_food_type=sims[1])
        results.append(r)
        score = 'none' if best is None else f'{best:.2f}'
        print(f'case {case}  fly {fly}  {label:<28} fleet match {score:>5}  bitter {bitter:>3.0f} Hz  '
              f'MN9 {left.mean():5.1f} +/- {ci95(left):4.1f} Hz  -> {"EATS" if eats else "refuses"}'
              f'{"  (stung, escalates to Qdrant)" if escalated else ""}'
              f'{"  [same input as above, trials reused]" if reused else ""}', flush=True)

    encounter(1, 0, trap_t, 'baited trap, empty memory')
    encounter(2, 1, trap_t, 'another trap, same type')
    encounter(3, 1, food_t, 'real food (trap is built from it)')

    dose = []
    if sweep:
        n = max(2, trials // 2)
        print(f'\nbitter dose-response, sugar {SUGAR_HZ:.0f} Hz, {n} trials each:', flush=True)
        for b in (50.0, 100.0, 200.0):
            left, _ = brain.taste(SUGAR_HZ, b, n, seed0=1000 + int(b))
            dose.append(dict(bitter_hz=b, mn9_left_hz=float(left.mean()), mn9_left_ci95=float(ci95(left)), trials=n))
            print(f'  bitter {b:>3.0f} Hz  MN9 {left.mean():5.1f} +/- {ci95(left):4.1f} Hz', flush=True)

    per_sim_s = brain.sim_wall / brain.sim_s
    total_s = time.time() - t_start
    print(f'\nruntime: {per_sim_s:.1f} s wall per simulated second (one core, Brian2 numpy target; '
          f'Brian2 setup lands in the first run); whole script {total_s:.0f} s for {brain.sim_s:.0f} simulated s')
    out = dict(trials_per_case=trials, sugar_hz=SUGAR_HZ, bitter_hz=BITTER_HZ, eat_threshold_hz=EAT_HZ,
               neurons=brain.n_neurons, connections=brain.n_syn, total_wall_s=total_s, simulated_s=brain.sim_s,
               wall_s_per_simulated_s=per_sim_s, cases=results, bitter_dose_response=dose)
    (HERE / 'brain_results.json').write_text(json.dumps(out, indent=2))
    print('wrote brain_results.json')


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    main(int(args[0]) if args else 10, sweep='--sweep' in sys.argv)
