# Submission: Project 4, The Bugfather

## Authors
**Team name:** The Bugfather (solo)

**Project:** Project 4: Right car, right station, next 14 days (Fleet Allocation Challenge)

## Problem and approach
Ten stations, four car categories, 14 days. Decide additions, removals and transfers so that the fleet is where the
demand is, at the highest profit, when the demand itself has to be estimated from 8 weeks of history and the
final score is the mean over 30 hidden demand scenarios.

Three steps, all in `solution/`:

1. **Level 0 and forecast** (`common.py`). Committed car-days, one-way moves and the station fleet per station,
   category and day; all 10 cells in `check_values.csv` match. Demand to come = expected cars on rent on that
   weekday minus committed car-days. The weekday shape is pooled per station type (airports peak Thursday, downtown
   peaks Saturday at 1.44x the weekly mean); every station follows its type's shape within 0.01. No trend in the
   history (-0.3 % per week), so none is modelled.
2. **Uncertainty priced into the revenue** (`buckets_expected`). Week-to-week noise is Poisson-like (variance /
   mean = 1.15), independent across stations and categories, day-correlated within a cell (rentals last 2.9 days).
   Instead of optimising for one forecast, the expected revenue of each extra car is averaged over 1,000 random
   futures. The result is still a concave set of revenue buckets, so the model does not grow, but the optimiser
   values the last cars at a station only by the chance that they are used. This is Level 4 built into Level 1-3.
3. **One mixed-integer model for all categories** (`solve_joint` in `solve.py`, PuLP + CBC). Decisions: adds,
   removals, transfers per station, category and day, trucks per route and day. Appendix A as constraints: fleet >=
   committed, caps, free capacity = max(0, utilisation x fleet - committed) (exact, one binary per cell), upgrades
   from the next higher category at the lower category's price, trucks with 8 places shared by all categories.
   Warm-started in two phases (so CBC starts from a complete solution) from four per-category models; 10 minutes.

**What the data says about this instance, and what it changed.**
- *The problem is mostly a premium problem.* 667 premium cars for an average daily need of about 252, 300 on the
  peak day (379 at Marlow Airport, which needs 69 on an average day and 81 at peak), with a removal cap of 66. The
  only way to earn from the rest is to let them serve midsize demand as upgrades (midsize is short: every
  per-category plan buys the full 18 midsize cars the cap allows; the final joint plan buys none and uses premium
  upgrades instead). So the value the model puts on upgrades decides the
  plan: trusting them fully makes the model move ~980 cars to exploit "free" premium cars that are not always free;
  ignoring them throws revenue away. The final model values each upgrade by the **probability that the higher
  category really has a free car** at that station and day (`upgrade_values`: ~1.0 for premium -> midsize where
  premium is plentiful and 0.85 on average, about 0.3 for midsize -> compact, 0.45 for compact -> economy; averages
  over cells with demand, from the fleet of the warm-start plan).
- *Bookings on file as a leading indicator.* Replaying pretend fortnights inside the history gives the usual share of
  a fortnight that is booked before it starts (about 90-97 % of day 1 down to 6-10 % of day 14). Against that pace
  the real bookings say airports run 8-11 % above their usual level (depending on whether late horizon days, with few
  bookings and small shares, get equal or booking-proportional weight), downtown on pace. This signal did not improve a
  backtest on the pretend fortnights, so it is not trusted as a forecast. It was used as the build forecast of the
  final candidate and as a stress world; the resulting plan scores higher at the historical demand level too, and the
  plan is unchanged when rebuilt on the historical forecast, so it costs nothing if the signal is noise.
- Price factors of downtown midsize are not concave (the marginal revenue between 60 % and 80 % served is lower
  than between 80 % and 100 %); the model uses their upper concave envelope, the scorer keeps the factors exactly as
  given.

## Models and why
No LLM is used; the "models" are optimisation variants. All are scored on the same 100 random futures at the
historical demand level, never used to build a plan (common random numbers, so differences are paired).
Mean profit +- standard error.

| Variant | What it tests | Mean profit | Chosen? |
| --- | --- | --- | --- |
| do-nothing | reference | 3,025,408 +- 3,094 | no |
| baseline (organisers' rule) | reference | 3,140,007 +- 3,297 | no |
| one forecast, per category | plain Level 1-2 model | 3,864,902 +- 3,610 | no |
| forecast x 0.9 / x 0.8 | naive robustness by shading demand | 3,837,421 / 3,822,484 | no, loses money |
| expected revenue, per category | uncertainty in the model | 3,881,842 +- 3,619 | no |
| expected revenue, joint, upgrades at 100 % | Level 3 on top | 3,989,811 +- 3,922 | no, over-moves cars |
| same, 25 more solver minutes | more search | 3,966,078 +- 3,756 | no: better for the model, worse for the scorer |
| joint, upgrades at 0 % | are upgrades worth anything? | 3,947,852 +- 3,790 | no |
| joint, upgrades at 50 % | a global discount | 4,026,317 +- 4,083 | no |
| joint, upgrades at 25 % / 75 % / per-cell (historical forecast) | bracket the discount | plan unchanged from 50 % | no |
| joint, per-cell upgrade probability, booking-level forecast | the final recipe, first run | 4,077,025 +- 4,244 | no, superseded by the run below |
| same, rebuilt with 1,000-future buckets, either forecast | polish | plan unchanged | (same plan) |
| final plan re-solved from itself with upgrade probabilities re-estimated from its own fleet | is the recipe at a fixed point? | plan unchanged (`variants/log_iter2.txt`) | (same plan) |
| **same recipe run from scratch by `make_plan.py` (1,000-future buckets)** | reproducibility | **4,084,408 +- 4,177** | **yes** |

## Results
Measured with a local re-implementation of the Appendix A scoring rules (`common.score`), not the official scorer.

- Final plan (`solution/best_plan.csv` = `plans/final_candidate.csv`, the output of `make_plan.py`):
  **4,084,408 mean profit on 100 random futures (4,128,191 on the forecast), +944 k (+30 %) over the baseline plan
  and +1.06 M over do-nothing.** It adds 48 cars (21 economy, 27 compact, no midsize or premium), removes 200
  (midsize 37 and premium 66 at their caps, economy 62, compact 35) and transfers 674, 99 % by truck (transfer cost
  85 k). The official feedback-round result (one public scenario, copy in `plans/v1.result.md`) gives profit 4,096,593.74 with committed revenue
  2,851,079.81, new revenue 3,896,218.23, holding 2,544,352.00, addition 21,840.00, transfer 84,512.30, 48 added,
  200 removed, 674 transferred. The four demand-independent lines match the local scorer to the cent, the profit is
  0.3 % above the local 100-future mean, and the official baseline (3,111,408) and do-nothing (3,008,620) profits are
  within 1 % of the local means, so the local scorer applies the same rules as the official one. Marlow Airport goes from 690 cars to 264 by day 14 and Fairgrounds from 359 to 101; the short downtown
  stations grow (Marlow Central +179, Old Quarter +147, Quayside +124, Highvale Spa +89, Lakeside +93). The moves
  are one way and early: 598 of the 674 transferred cars leave in days 1-4 (414 airport -> downtown, 257 between
  downtown stations, 3 back to an airport), and a 48-car top-up goes out on days 11-12 ahead of the second Saturday.
  The airports keep enough cars for their own Monday-Thursday demand, so nothing shuttles back (a truck place on the
  3 km Marlow Airport -> Marlow Central route costs about 87, against a car-day worth 240-540 on average by
  category). Downtown is left short on the two Saturdays (67 % and 79 % of its demand served, 90-100 % on other
  days): by the price factors the last third of a peak day earns only 0.4-0.5 of the base price per car-day, less
  than holding and moving a car for a one-day peak. Midsize demand is
  served largely by surplus premium cars instead of 18 bought midsize cars.
- Stress test (`stress_test.py`, seven ways of generating the hidden scenarios: pure Poisson, a shared +-10 %
  fortnight, demand -15 % and +15 % everywhere, the booking-implied level with airports +11 %, and simulated rentals
  with day-correlated noise at both levels, plus a fresh 300-future seed): **the final plan is first in every
  world**, ahead of the previous best plan (the same recipe's first run) in all of them (within the organisers'
  2-standard-error tie rule the two tie in six of the seven worlds) and 47-73 k ahead of the 50 %-upgrade plan.
  Full tables in `solution/results.md`. At the booking-implied demand level the airports still serve 98 % of their
  demand (48 car-days short out of about 3,000, all economy and compact; the do-nothing fleet is 10 short).
- What did not work: planning for 80-90 % of the forecast lost 25-40 k (the price buckets already make the last
  cars low-value); the booking signal did not backtest better than the plain weekday mean; a 25-minute solve of the
  100 %-upgrade model scored lower than the 10-minute one (the model was over-optimistic about upgrades and a longer
  search exploits that), which is what led to the per-cell upgrade probability; CBC with `threads>1` returned
  variable values that did not match its reported solution, so the code runs single-threaded; passing only the
  integer decisions as a warm start made CBC begin from a hollow solution, hence the two-phase warm start.
- Limits: the joint model stops at a time limit with a gap; the model's upgrade order may differ slightly from the
  scorer's own-category-first rule; the forecast has no booking dynamics beyond the level signal.

## How to run
Python 3.14, no API keys, no environment variables. From a fresh clone:

```bash
cd Project_4
PYTHON=python3.14 bash setup.sh          # creates .venv, installs pandas, pandera, pulp (CBC included)
. .venv/bin/activate
python solution/make_plan.py                # -> plans/final_candidate.csv, the submitted recipe (about 20 min)
python solution/experiments.py              # all variants + comparison table (about 10 min)
python solution/stress_test.py              # ranking under seven noise assumptions (about 3 min)
python solution/run_candidate.py <name> <upgrade value|cell> <pooled|blend> [minutes] [futures] [warm variant]
```

`make_plan.py` defaults: booking-level forecast for building, per-cell upgrade values, 1,000-future buckets,
10 minutes; evaluation always at the historical demand level. Data is read from `Project_4/data/` as shipped.
The solver runs against a time limit, so another machine can return a slightly different plan from the same recipe;
the plan that was submitted is `plans/final_candidate.csv`. Nothing is copied to the shared folder automatically.

## Demo
`submission/slides.pdf` (5 slides; source `submission/slides.html`); 3-minute pitch script with Q&A in `submission/pitch.md`

## Next steps
- Model the upgrade capacity as a random quantity in the optimisation (free higher-category cars depend on that
  category's demand) instead of a probability weight; use a faster solver (HiGHS) to close the gap.
- Validate the booking-pace signal on more history and, if it holds, use it as a live level adjustment.
- For SIXT: the same model can run every morning on the live snapshot; the expected-revenue buckets are the piece
  that makes it safe to act on a forecast that is known to be noisy.
