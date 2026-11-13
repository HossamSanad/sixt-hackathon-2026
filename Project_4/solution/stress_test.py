"""Is the ranking of the plans stable when the random futures are generated differently?

All plans were built and ranked with independent Poisson noise per station, category and day.
Here every plan in variants/ is re-scored under other assumptions about the hidden scenarios:
  poisson_only   pure Poisson, no extra level noise
  shared_shift   one random +-10 % shift for the whole network per scenario (a good or bad fortnight)
  demand_-15%    demand to come 15 % below the forecast everywhere
  demand_+15%    demand to come 15 % above the forecast everywhere
  booking_level  demand at the level implied by the bookings on file (airports ~+11 %)
  rental_sim     simulated rentals (day-correlated noise), historical level
  rental_sim_booking  simulated rentals at the booking-implied level
  overdispersed_X  gamma-Poisson counts with variance / mean = X (1.38 is the value measured in the history
                   with the index-of-dispersion test; 1.8 and 2.5 are harsher than anything observed)
A plan that is first or tied-first everywhere is a safe choice. Run from Project_4/ after experiments.py.
"""

import numpy as np
import pandas as pd

from common import P4, load, make_rental_scenarios, make_scenarios
from fleetkit import baseline_plan
from solve import COLS, evaluate

VAR_DIR = P4 / "solution" / "variants"


def shared_shift_scenarios(D, n, seed, sigma=0.10):
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        shift = rng.lognormal(-sigma**2 / 2, sigma)
        dem, base = make_scenarios(D, 1, seed + 1000 + i, level_sigma=0.0, demand=D.demand * shift)[0]
        out.append((dem, base))
    return out


def overdispersed_scenarios(D, n, seed, disp, base_sigma=0.025):
    """Gamma-Poisson (negative binomial) counts around the forecast with variance / mean = disp."""
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        rate = rng.gamma(np.maximum(D.demand / (disp - 1), 1e-9), disp - 1) if disp > 1 else D.demand
        base = D.base * rng.lognormal(-base_sigma**2 / 2, base_sigma, D.base.shape)
        out.append((rng.poisson(rate).astype(float), base))
    return out


def main():
    D = load()
    plans = {"do-nothing": pd.DataFrame(columns=COLS), "baseline": baseline_plan(instance=D.inst)}
    for path in sorted(VAR_DIR.glob("*.csv")):
        plans[path.stem] = pd.read_csv(path)
    worlds = {
        "poisson_only": make_scenarios(D, 100, seed=7, level_sigma=0.0),
        "shared_shift": shared_shift_scenarios(D, 100, seed=11),
        "demand_-15%": make_scenarios(D, 100, seed=13, demand=D.demand_pooled * 0.85),
        "demand_+15%": make_scenarios(D, 100, seed=17, demand=D.demand_pooled * 1.15),
        # the bookings on file say airports run ~11 % above their usual pace: a world where that is true
        "booking_level": make_scenarios(D, 100, seed=19, demand=D.demand_blend),
        # simulated rentals: day-correlated noise like the history, historical level
        "rental_sim": make_rental_scenarios(D, 100, seed=23),
        "rental_sim_booking": make_rental_scenarios(D, 100, seed=29, level=D.level_mult),
        # the measured spread of the history and two harsher ones
        "overdispersed_1.38": overdispersed_scenarios(D, 100, seed=11, disp=1.38),
        "overdispersed_1.8": overdispersed_scenarios(D, 100, seed=11, disp=1.8),
        "overdispersed_2.5": overdispersed_scenarios(D, 100, seed=11, disp=2.5),
    }
    summary = {}
    for name, scen in worlds.items():
        print(f"\n== world: {name}")
        df = evaluate(D, plans, scen)
        top = df.iloc[0]
        tied = df[df["mean"] >= top["mean"] - 2 * top.se].plan.tolist()
        summary[name] = tied
    print("\nFirst place (plans within 2 SE of the top) per world:")
    for name, tied in summary.items():
        print(f"  {name:14} {tied}")


if __name__ == "__main__":
    main()
