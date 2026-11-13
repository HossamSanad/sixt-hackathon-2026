"""Build one joint-model candidate and score it against the current best.

python run_candidate.py <name> <upgrade: float|cell> <forecast: pooled|blend> [minutes=10] [futures=200] [warm=stoch_joint_up0.5] [disp]
  upgrade   value of upgrade revenue in the model (0..1) or "cell" for the per-cell probability (solve.upgrade_values)
  futures   number of random futures the revenue buckets are averaged over
  warm      variant name in variants/ to start the solver from
Writes variants/<name>.csv. It does NOT submit anything.
"""

import sys
import time

import pandas as pd

from common import P4, buckets_expected, load, make_scenarios
from fleetkit import write_plan
from solve import evaluate, solve_joint, upgrade_values

VAR = P4 / "solution" / "variants"

name, up, fc = sys.argv[1], sys.argv[2], sys.argv[3]
minutes = float(sys.argv[4]) if len(sys.argv) > 4 else 10
futures = int(sys.argv[5]) if len(sys.argv) > 5 else 200
warm_name = sys.argv[6] if len(sys.argv) > 6 else "stoch_joint_up0.5"
disp = float(sys.argv[7]) if len(sys.argv) > 7 else None  # variance/mean of the bucket futures (gamma-Poisson)

D = load(fc)
eb = buckets_expected(D, make_scenarios(D, futures, seed=1, disp=disp))
warm = pd.read_csv(VAR / f"{warm_name}.csv")
uv = upgrade_values(D, warm) if up == "cell" else float(up)
t = time.time()
plan = solve_joint(D, eb, time_limit=int(minutes * 60), warm=warm, upgrade_value=uv)
print(f"{name}: upgrade={up} forecast={fc} futures={futures} disp={disp} warm={warm_name} {time.time() - t:.0f}s, {len(plan)} rows")
write_plan(df_plan=plan, path=VAR / f"{name}.csv")
D_eval = load("pooled")
evaluate(D_eval, {name: plan, warm_name: warm}, make_scenarios(D_eval, 100, seed=123))
