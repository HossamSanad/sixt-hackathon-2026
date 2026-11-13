# Submission: Project 4, The Bugfather

## Authors
**Team name:** The Bugfather (solo)

**Project:** Project 4: Right car, right station, next 14 days (Fleet Allocation Challenge)

## Problem and approach
Our logic in seven steps. Each step says what we wanted and how we did it. A "cell" is one station, one category,
one day (10 x 4 x 14 = 560 cells). The running example is Marlow Central on day 6. All code is in `solution/`.

1. **We wanted to know where the money is before optimising, so we compared need with fleet.**
   Need per cell = committed bookings plus forecast demand, divided by the station's utilisation limit. Premium has
   667 cars for an average need of 252 (300 at peak) and may remove only 66. Marlow Airport holds 690 cars and
   Fairgrounds 359, far more than they use, while the downtown stations 3 km away are short. Midsize is short and
   may add only 18. So the plan's shape was clear before any solver ran: move cars out of the two full stations
   into downtown, and give the surplus premium cars a job.

2. **We wanted a forecast we could defend, so we tested four on past fortnights and kept the simplest.**
   (`common.py`; all 10 Level 0 check values match.) Demand to come = expected cars on rent on that weekday minus
   committed car-days. The weekday shape is shared per station type (airports peak Thursday, downtown peaks
   Saturday), the level is per station. We forecast two past fortnights from the weeks before them and compared
   with what happened: error 5.69 cars per cell and day, against 5.85 for per-station weekday means and 5.70-5.72
   for two versions that use the bookings on file. A forecast that knew the true average would still be off by
   5.03, because demand is random. So there was little left to gain in the forecast, and we put the effort into
   the decision.

3. **We wanted the plan to cope with demand we cannot know, so we made 1,000 random versions of the fortnight.**
   (`make_scenarios`.) For each cell, two random steps: first move the forecast up or down by a random factor
   (typically within +-10 %), then draw a whole number of customers around that level (Poisson). Example, compact at
   Marlow Central on day 6, forecast 70.3: the first five futures give 77, 80, 70, 58, 68. Over 1,000 futures the
   average is 70.4, eight in ten fall between 57 and 85, and the extremes are 41 and 115.

4. **We wanted to know what each extra car is worth, so we tried every fleet size against all 1,000 futures.**
   (`buckets_expected`.) For a capacity x, revenue in each future is that of serving min(x, demand) with the
   organisers' price factors; we average over the futures. The gain from one capacity step to the next is the
   value of those cars. Same cell, in units of the base price: cars 1-42 are worth 1.03-1.07 each (used in every
   future), cars 53-63 0.80, cars 64-73 0.50, cars 74-84 0.21, cars 85-94 0.05. The optimiser gets these falling
   values (5,759 in total) instead of one forecast. It then holds back by itself exactly where the last cars do
   not pay for their holding cost. The model does not grow. Planning for 80-90 % of the forecast instead, the same
   everywhere, lost 25-40 k.

5. **We wanted the surplus premium cars to earn money, so we let them serve midsize demand, and we counted each
   upgrade only by the chance that the spare car is really there.** (`upgrade_values`.) On day 6 at Marlow Central
   the plan has 43 midsize cars, all 43 committed, and 39.5 expected new midsize customers; it has 116 premium cars
   (56 before the plan) with 62 free for 18.6 expected premium customers. The spare premium cars serve the midsize
   customers at the midsize price. But premium demand is random too, so per cell we compute the probability that
   the higher category has a free car, and the model counts the upgrade revenue times that probability: 1.0 in
   this example, 0.0 for midsize -> compact in the same cell because midsize has nothing free. Counting upgrades
   in full made the model move about 980 cars and scored 3.99 M; not counting them scored 3.95 M; a flat 50 %
   4.03 M; the per-cell probability 4.08 M. The final plan buys none of the 18 midsize cars it could.

6. **We wanted the best set of moves under all the rules at once, so we wrote Appendix A as one model and let a
   solver choose.** (`solve_joint` in `solve.py`, PuLP + CBC.) Decisions: adds, removals and transfers per station,
   category and day, trucks per route and day. Rules: fleet >= committed bookings, category caps, lead times, free
   capacity = max(0, utilisation x fleet - committed), upgrades from the next higher category, trucks with 8
   places shared by all categories. Objective: the car values from step 4, minus holding, addition and transfer
   costs. Four per-category models give a starting plan; the joint model improves it for 10 minutes. Downtown
   midsize price factors are not concave, so the model uses their upper concave envelope; the scorer keeps them
   as given.

7. **We wanted to pick the plan by real profit, not by the solver's own number, so we scored every candidate
   ourselves.** (`common.score`.) The model is an approximation, so each candidate is scored with our own copy of
   the Appendix A scoring on 100 fresh random futures, and that mean chooses the plan. This caught a real trap:
   25 more solver minutes on the model that counted upgrades in full gave a higher model objective and a lower
   profit, which led to step 5. We then changed the way the futures are generated in ten ways
   (`stress_test.py`); the plan stayed first in all of them.

8. **We wanted the last few thousand that the model's approximations leave on the table, so we polished the plan
   on the real rules.** (`polish.py`.) The model sees a concave price envelope, upgrade probabilities and a free
   upgrade order; the scorer does not. A local search edits the plan directly (a few cars more or less on an add,
   removal or transfer, a transfer shifted by a day, a new add, removal or truck-load on any route) and keeps a
   move only if its paired gain on 200 training futures beats two standard errors; the result is then judged on
   three sets of futures the search never saw. Two passes accepted 28 + 6 edits: +23 k on the referee set, +22 k
   on a fresh seed, +22 k at the measured dispersion. They trim additions (48 -> 28), push economy, midsize and
   premium removals to their caps (200 -> 220) and add a few truck-loads (674 -> 751 transfers). The organisers'
   feedback round scored the polished plan 4,112,935.46 against 4,096,593.74 for the model plan on the same public
   scenario (+16 k), all cost lines matching ours to the cent. The polished plan is `plans/final.csv`.

**Two smaller findings.**
- *Bookings on file.* Against the usual booking pace, airports run 8-11 % above their usual level (depending on how
  late days are weighted), downtown is on pace. This did not improve the backtest, so we do not trust it as a
  forecast. It is the build forecast of the final plan and one of the stress worlds; the plan comes out the same
  when rebuilt on the historical forecast.
- *What step 3 leaves out.* Each cell is randomised on its own, so no future has the whole network high or low
  together. That case is tested in the stress worlds (shared +-10 %, demand -15 % and +15 %), not built into the
  values.

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
| same, with buckets from futures at the measured dispersion 1.38 | does the spread change the plan? | plan unchanged (`variants/log_disp138.txt`) | (same plan) |
| same recipe run from scratch by `make_plan.py` (1,000-future buckets) | reproducibility; the model plan, uploaded as v1 | 4,084,408 +- 4,177 | superseded by the polish |
| model plan + referee polish, pass 1 (`polish.py`, 28 edits) | the real rules on unseen futures | 4,105,457 +- 4,106 | superseded by pass 2 |
| **model plan + referee polish, pass 2 (6 more edits)** | second pass, different training futures | **4,107,424 +- 4,077** | **yes: `plans/final.csv`** |

## Results
Measured with a local re-implementation of the Appendix A scoring rules (`common.score`), not the official scorer.

- Submitted plan (`plans/final.csv` = `solution/best_plan.csv` = `variants/stoch_polish2.csv`: the `make_plan.py`
  plan after two passes of `polish.py`): **4,107,424 mean profit on 100 random futures (4,154,803 on the forecast),
  +967 k (+31 %) over the baseline plan and +1.08 M over do-nothing.** It adds 28 cars (21 economy, 7 compact, no
  midsize or premium), removes 220 (economy 66, compact 51, midsize 37, premium 66: midsize and premium at their
  caps, economy one below) and transfers 751, 99 % by truck (transfer cost 90.5 k). The official feedback-round
  result (one public scenario, copy in `plans/v3.result.md`) gives profit 4,112,935.46 with committed revenue
  2,851,079.81, new revenue 3,883,571.65, holding 2,518,432.00, addition 12,740.00, transfer 90,544.00, 28 added,
  220 removed, 751 transferred. The four demand-independent lines match the local scorer to the cent and the profit
  is 0.1 % above the local 100-future mean. Marlow Airport goes from 690 cars to 234 by day 14, Dunmere Airport from
  298 to 126 and Fairgrounds from 359 to 100; the short downtown stations grow (Marlow Central +173, Old Quarter
  +153, Quayside +133, Lakeside +89, Highvale Spa +88). The moves are one way and early: 634 of the 751 transferred
  cars leave in days 1-4 (452 airport -> downtown, 298 between downtown stations, 1 back to an airport), and 99 cars
  go out on days 10-12 ahead of the second Saturday. The airports keep enough cars for their own Monday-Thursday
  demand, so nothing shuttles back (a truck place on the 3 km Marlow Airport -> Marlow Central route costs about 87,
  against a car-day worth 240-540 on average by category). Downtown is left short on the two Saturdays (67 % and
  80 % of its demand served, 90-100 % on other days): by the price factors the last third of a peak day earns only
  0.4-0.5 of the base price per car-day, less than holding and moving a car for a one-day peak. Midsize demand is
  served largely by surplus premium cars instead of 18 bought midsize cars.
- Model plan before the polish (`plans/final_candidate.csv`, the output of `make_plan.py`, uploaded as v1):
  4,084,408 mean profit (4,128,191 on the forecast); 48 added, 200 removed, 674 transferred. Its official result
  (`plans/v1.result.md`) is 4,096,593.74 with all four cost lines matching the local scorer to the cent, and the
  official baseline (3,111,408) and do-nothing (3,008,620) profits are within 1 % of the local means, so the local
  scorer applies the same rules as the official one.
- Stress test (`stress_test.py`, ten ways of generating the hidden scenarios: pure Poisson, a shared +-10 %
  fortnight, demand -15 % and +15 % everywhere, the booking-implied level with airports +11 %, and simulated rentals
  with day-correlated noise at both levels, plus a fresh 300-future seed, plus gamma-Poisson worlds at the measured
  dispersion 1.38 and at harsher 1.8 and 2.5): **the submitted plan is first in every world** (mean 4,109 k at dispersion 1.38, 4,085 k at 1.8, 4,062 k at 2.5,
  so the measured extra spread costs it about 20 k and changes no ranking), 7-29 k ahead of the model plan and
  76-86 k ahead of the 50 %-upgrade plan in every world; under the organisers' 2-standard-error tie rule only the
  two polish passes tie for first. Scored draw by draw on 600 futures in four worlds, it is ahead of the model
  plan, the 50 %-upgrade plan, the baseline and do-nothing in every single draw (worst draw 3,971 k on the fresh
  seed). Full tables in `solution/results.md`. At the booking-implied demand level the airports still serve 95 %
  of their demand (149 car-days short out of about 3,000, mostly economy; the do-nothing fleet is 10 short).
- What did not work: planning for 80-90 % of the forecast lost 25-40 k (the price buckets already make the last
  cars low-value); the booking signal did not backtest better than the plain weekday mean; a 25-minute solve of the
  100 %-upgrade model scored lower than the 10-minute one (the model was over-optimistic about upgrades and a longer
  search exploits that), which is what led to the per-cell upgrade probability; CBC with `threads>1` returned
  variable values that did not match its reported solution, so the code runs single-threaded; passing only the
  integer decisions as a warm start made CBC begin from a hollow solution, hence the two-phase warm start.
- Limits: the joint model stops at a time limit with a gap; the model's upgrade order may differ slightly from the
  scorer's own-category-first rule; the forecast has no booking dynamics beyond the level signal; the simulated
  futures are slightly less dispersed than the history (variance / mean 1.25 against 1.38), so the last cars are
  discounted a little less than they should be. On held-out fortnights the forecast error is 5.69 cars per cell
  and day against a noise floor of 5.03 at the measured dispersion (the error of a forecast that knows the true
  mean), which is why no learned forecaster was pursued.

## How to run
Python 3.14, no API keys, no environment variables. From a fresh clone:

```bash
cd Project_4
PYTHON=python3.14 bash setup.sh          # creates .venv, installs pandas, pandera, pulp (CBC included)
. .venv/bin/activate
python solution/make_plan.py                # -> plans/final_candidate.csv, the model plan (about 20 min)
cp plans/final_candidate.csv solution/variants/stoch_make_plan.csv
python solution/polish.py stoch_make_plan stoch_polish 20 200 555     # referee polish, pass 1 (about 5 min)
python solution/polish.py stoch_polish stoch_polish2 10 300 777       # pass 2 -> variants/stoch_polish2.csv = plans/final.csv
python solution/experiments.py              # all variants + comparison table (about 10 min)
python solution/stress_test.py              # ranking under ten noise assumptions (about 5 min)
python solution/run_candidate.py <name> <upgrade value|cell> <pooled|blend> [minutes] [futures] [warm variant] [dispersion]
```

`make_plan.py` defaults: booking-level forecast for building, per-cell upgrade values, 1,000-future buckets,
10 minutes; evaluation always at the historical demand level. Data is read from `Project_4/data/` as shipped.
The solver runs against a time limit, so another machine can return a slightly different plan from the same recipe;
the plan that was submitted is `plans/final.csv` (the polish is deterministic given its start plan and seeds).
Nothing is copied to the shared folder automatically.

## Demo
`submission/slides.pdf` (5 slides; source `submission/slides.html`); 3-minute pitch script with Q&A in `submission/pitch.md`

## Next steps
- Model the upgrade capacity as a random quantity in the optimisation (free higher-category cars depend on that
  category's demand) instead of a probability weight; use a faster solver (HiGHS) to close the gap. The polish
  moves (fewer additions, removals at the caps, a few more truck-loads) say where the model is still too
  optimistic; fold that back into the model rather than fixing it afterwards.
- Validate the booking-pace signal on more history and, if it holds, use it as a live level adjustment.
- For SIXT: the same model can run every morning on the live snapshot; the expected-revenue buckets are the piece
  that makes it safe to act on a forecast that is known to be noisy.
