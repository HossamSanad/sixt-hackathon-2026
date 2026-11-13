"""Build the final plan in one go: forecast -> expected-revenue buckets -> per-category models
-> joint model (upgrades + trucks) warm-started from them -> local check -> plans/final_candidate.csv.

Run from Project_4/:
  . .venv/bin/activate && python solution/make_plan.py [--minutes 10] [--forecast blend|pooled]
                                                              [--upgrade cell|<0..1>] [--futures 1000] [--warm file.csv]
Defaults are the recipe of the submitted plan (plans/final_candidate.csv); the solver is time-limited, so another
machine can return a slightly different plan. It writes a file; copying it to the shared folder is a manual step on purpose.
"""

import sys
import time

import pandas as pd

from common import P4, buckets_expected, check_level0, load, make_scenarios
from fleetkit import baseline_plan, write_plan
from solve import COLS, build_plan, evaluate, solve_joint, upgrade_values

OUT = P4 / "plans" / "final_candidate.csv"


def arg(argv, name, default):
    return argv[argv.index(name) + 1] if name in argv else default


def main(argv: list[str]) -> None:
    minutes = float(arg(argv, "--minutes", 10))
    forecast = arg(argv, "--forecast", "blend")  # booking-level forecast for building; evaluation uses the historical level
    upgrade = arg(argv, "--upgrade", "cell")  # per-cell probability that the higher category has a free car
    futures = int(arg(argv, "--futures", 1000))
    warm_file = arg(argv, "--warm", None)
    t0 = time.time()

    print(f"1. data, Level 0, forecast ({forecast})")
    D = load(forecast)
    assert check_level0(D), "Level 0 does not match check_values.csv"
    print("   level multiplier per station type from the bookings on file:",
          {st: round(float(D.level_mult[D.stype.index(st)]), 3) for st in sorted(set(D.stype))})

    print(f"2. revenue buckets averaged over {futures} random futures")
    buckets = buckets_expected(D, make_scenarios(D, futures, seed=1))

    if warm_file:
        print(f"3. warm start from {warm_file}")
        warm = pd.read_csv(warm_file)
    else:
        print("3. per-category models (warm start for the joint model)")
        warm = build_plan(D, buckets, time_limit=90)

    uv = upgrade_values(D, warm) if upgrade == "cell" else float(upgrade)
    print(f"4. joint model with upgrades (valued: {upgrade}) and trucks, {minutes:g} min")
    plan = solve_joint(D, buckets, time_limit=int(minutes * 60), warm=warm, upgrade_value=uv)

    print("5. local check on 100 fresh random futures at the historical demand level")
    D_eval = load("pooled")
    df = evaluate(D_eval, {"final": plan, "warm start": warm, "baseline": baseline_plan(instance=D.inst),
                           "do-nothing": pd.DataFrame(columns=COLS)}, make_scenarios(D_eval, 100, seed=123))
    assert bool(df.set_index("plan").loc["final", "valid"]), "final plan is not valid"
    if df.iloc[0].plan != "final":
        print("   note: the warm start scored higher; keeping the warm start")
        plan = warm

    write_plan(df_plan=plan, path=OUT)
    print(f"\nWrote {OUT.relative_to(P4)} ({len(plan)} rows) in {time.time() - t0:.0f}s. Not submitted.")


if __name__ == "__main__":
    main(sys.argv[1:])
