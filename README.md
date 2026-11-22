# Fleet Allocation Optimiser — SIXT Hackathon 2026

**Right car, right station, next 14 days.** My solo solution (team *The Bugfather*) to Project 4 of the SIXT Hackathon 2026 (Munich, 13 Nov 2026): decide how many cars of each category every station should hold for the next fortnight — which cars to add, remove and move between stations — to maximise expected profit under uncertain demand.

| | Mean profit (100 random futures) | vs. baseline |
| --- | --- | --- |
| Do nothing | 3,025,408 | −114 k |
| Organisers' baseline rule | 3,140,007 | — |
| **This solution** (`plans/final.csv`) | **4,107,424** | **+967 k (+31 %)** |

Official feedback-round score (one public scenario): **4,112,935** profit.

---

## The problem

10 stations × 4 car categories × 14 days = 560 decision cells. For each cell the plan sets the fleet size, subject to category add/remove caps, utilisation limits, transfer costs (truck vs. driver) and holding costs. Revenue depends on how many customers actually show up — which is random.

## Approach

1. **Diagnose before optimising.** Comparing need (bookings + forecast ÷ utilisation limit) with the current fleet showed the shape of the answer up front: the airport and fairgrounds stations hold far more cars than they use, downtown stations 3 km away are short, and premium has a large surplus.
2. **A forecast that can be defended.** Four forecasting methods were back-tested on past fortnights; the simplest (station level × shared weekday shape by station type) had the lowest error (5.69 cars/cell/day vs. a 5.03 noise floor), so effort went into the decision, not the forecast.
3. **Plan for uncertainty, not for one number.** 1,000 simulated fortnights (random level shift + Poisson arrivals per cell).
4. **Value every extra car.** For each cell, the expected revenue of the *n*-th car is computed across all futures (e.g. cars 1–42 worth ~1.05× base price, cars 85–94 only 0.05×). A mixed-integer program (PuLP/CBC) receives these 5,759 piecewise values and stops adding cars exactly where they no longer pay for their holding cost. Simply shading the forecast to 80–90 % instead lost 25–40 k.
5. **Make surplus premium cars earn.** Premium cars may serve midsize demand; each upgrade is valued only by the probability that the spare car is really free.
6. **Polish and stress-test.** A local-search "referee polish" improves the plan against fresh futures, and a stress test re-ranks all variants under ten different noise assumptions so the chosen plan is robust, not lucky.

All variants are compared on the same 100 held-out futures (common random numbers), with standard errors — see [`Project_4/SUBMISSION.md`](Project_4/SUBMISSION.md) for the full table and reasoning.

**Final plan:** adds 28 cars, removes 220 (midsize and premium at their caps), and makes 751 transfers, 99 % by truck.

## Tech

Python · pandas · pandera (data validation) · PuLP / CBC (mixed-integer programming) · Monte-Carlo simulation

## Repository layout

| Path | Contents | Author |
| --- | --- | --- |
| `Project_4/solution/` | Forecasting, scenario generation, optimisation model, polish, experiments, stress test | **me** |
| `Project_4/plans/`, `Project_4/submission/` | Final plans, official results, pitch and slides | **me** |
| `Project_4/SUBMISSION.md` | Full write-up: approach, model comparison, results, next steps | **me** |
| `Project_4/data/`, `Project_4/fleetkit/` | Challenge data and starter package | SIXT hackathon organisers |
| `CodeRabbit_Python/` | AI code-review config provided for all teams | SIXT hackathon organisers |

## Run it

Python 3.14, no API keys needed.

```bash
cd Project_4
PYTHON=python3.14 bash setup.sh      # creates .venv, installs pandas, pandera, pulp (CBC included)
. .venv/bin/activate
python solution/make_plan.py         # builds the model plan (~20 min)
python solution/experiments.py       # scores all variants and prints the comparison table (~10 min)
python solution/stress_test.py       # ranking under ten noise assumptions (~5 min)
```

The exact commands to reproduce the submitted plan (including both polish passes) are in [`Project_4/SUBMISSION.md`](Project_4/SUBMISSION.md#how-to-run).

## Notes

Scores in the table were measured with my local re-implementation of the official scoring rules, except where marked as the official feedback-round result. The challenge, data and starter code belong to the SIXT Hackathon 2026 organisers.
