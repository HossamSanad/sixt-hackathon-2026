"""Build model variants, then compare every plan in solution/variants/ on fresh random futures.

Run from Project_4/:  . .venv/bin/activate && python solution/experiments.py [--only a,b,...] [--eval]
  --only  build only these variants (default: all except stoch_joint)
  --eval  skip building, only evaluate the CSVs already in variants/
Writes one CSV per variant into solution/variants/ and the winner to solution/best_plan.csv.
It does NOT submit anything.
"""

import sys
import time

import pandas as pd

from common import P4, backtest, buckets_deterministic, buckets_expected, load, make_scenarios, noise_stats
from fleetkit import baseline_plan, write_plan
from solve import COLS, build_plan, evaluate, solve_joint

VAR_DIR = P4 / "solution" / "variants"
VAR_DIR.mkdir(exist_ok=True)
TIME_LIMIT = 90  # seconds per category model


def variants(D):
    """name -> function that builds the plan. Each answers one question."""
    D_raw = load(forecast_method="raw")
    build_scen = make_scenarios(D, 200, seed=1)  # futures the model is built on
    exp_buckets = buckets_expected(D, build_scen)
    return {
        # A. one forecast, raw weekday means (the first sample solution)
        "det_raw": lambda: build_plan(D_raw, buckets_deterministic(D_raw, D_raw.demand), TIME_LIMIT),
        # B. one forecast, pooled weekday profile (better backtest)
        "det_pooled": lambda: build_plan(D, buckets_deterministic(D, D.demand), TIME_LIMIT),
        # C. shaded forecasts: plan for less than expected, scored against the unshaded futures
        "det_pooled_x0.9": lambda: build_plan(D, buckets_deterministic(D, D.demand * 0.9), TIME_LIMIT),
        "det_pooled_x0.8": lambda: build_plan(D, buckets_deterministic(D, D.demand * 0.8), TIME_LIMIT),
        # D. expected revenue over random futures (Level 4), one model per category
        "stoch_pooled": lambda: build_plan(D, exp_buckets, TIME_LIMIT),
        # E. same revenue model, all categories together with upgrades and trucks (Level 3),
        #    warm-started from the per-category plan
        "stoch_joint": lambda: solve_joint(D, exp_buckets, time_limit=600,
                                           warm=pd.read_csv(VAR_DIR / "stoch_pooled.csv")),
    }


def main(argv: list[str]) -> None:
    t0 = time.time()
    D = load()
    print("Noise in the history:", noise_stats(D))
    print("Backtest, mean abs error forecasting a held-out week (lower is better):", backtest(D))

    if "--eval" not in argv:
        only = argv[argv.index("--only") + 1].split(",") if "--only" in argv else None
        for name, fn in variants(D).items():
            if (only is None and name == "stoch_joint") or (only is not None and name not in only):
                continue
            t = time.time()
            print(f"\n== {name}")
            plan = fn()
            write_plan(df_plan=plan, path=VAR_DIR / f"{name}.csv")
            print(f"   {len(plan)} rows, {time.time() - t:.0f}s")

    print("\n== Evaluation on 100 fresh random futures (mean profit; plans within 2 SE are a tie)")
    plans = {"do-nothing": pd.DataFrame(columns=COLS), "baseline": baseline_plan(instance=D.inst)}
    for path in sorted(VAR_DIR.glob("*.csv")):
        plans[path.stem] = pd.read_csv(path)
    df = evaluate(D, plans, make_scenarios(D, 100, seed=123))  # seed 123 is never used for building
    best = df.iloc[0]
    write_plan(df_plan=plans[best.plan], path=P4 / "solution" / "best_plan.csv")
    print(f"\nBest: {best.plan}  (mean {best['mean']:,.0f} +- {best.se:,.0f}) -> solution/best_plan.csv")
    print(f"Total {time.time() - t0:.0f}s. Nothing was submitted.")


if __name__ == "__main__":
    main(sys.argv[1:])
