"""Step 1: run the repo's own example (example.ipynb) unchanged and time it.

Activates the 21 right-hemisphere labellar sugar GRNs (IDs from example.ipynb)
with the default 150 Hz Poisson input, 30 trials x 1 s, and reads MN9
(720575940660219265, the proboscis-extension motor neuron from example.ipynb).

Run from fly-memory/ (so ./brian_preferences forces Brian2's numpy target):
    .venv-brain/Scripts/python brain_example.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'brain'))
from model import run_exp, default_params as params  # noqa: E402
import utils as utl  # noqa: E402

B = Path(__file__).parent / 'brain'
OUT = Path(__file__).parent / 'brain_out' / 'example'
N_PROC = int(sys.argv[1]) if len(sys.argv) > 1 else 2   # RAM-bound on this laptop

neu_sugar = [
    720575940624963786, 720575940630233916, 720575940637568838, 720575940638202345,
    720575940617000768, 720575940630797113, 720575940632889389, 720575940621754367,
    720575940621502051, 720575940640649691, 720575940639332736, 720575940616885538,
    720575940639198653, 720575940620900446, 720575940617937543, 720575940632425919,
    720575940633143833, 720575940612670570, 720575940628853239, 720575940629176663,
    720575940611875570,
]
id_mn9 = 720575940660219265

if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    t = time.time()
    run_exp(exp_name='sugarR', neu_exc=neu_sugar, path_res=OUT,
            path_comp=B / '2023_03_23_completeness_630_final.csv',
            path_con=B / '2023_03_23_connectivity_630_final.parquet',
            n_proc=N_PROC, force_overwrite=True)
    wall = time.time() - t
    df = utl.load_exps([OUT / 'sugarR.parquet'])
    rate, std = utl.get_rate(df, t_run=params['t_run'], n_run=params['n_run'])
    n_sim_s = params['n_run'] * float(params['t_run'])
    print(f'MN9 rate: {rate.loc[id_mn9, "sugarR"]:.1f} +/- {std.loc[id_mn9, "sugarR"]:.1f} Hz')
    print(f'active neurons: {len(rate)}')
    print(f'wall {wall:.0f} s for {n_sim_s:.0f} simulated s on {N_PROC} workers '
          f'= {wall * N_PROC / n_sim_s:.1f} core-s per simulated s (incl. per-trial build)')
