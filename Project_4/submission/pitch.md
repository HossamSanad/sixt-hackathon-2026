# Pitch script, 3 minutes (The Bugfather, Project 4)

Slide numbers refer to `slides.pdf`. Speak slowly; ~420 words is 3 minutes.

## 0:00 Slide 1, the problem (30 s)
Ten stations, four car categories, fourteen days. Where should every car be, each day, so SIXT earns the most?
Demand has to be estimated from eight weeks of history, and the score is the average profit over thirty random
demand scenarios. So the plan must be right on average, not just for one forecast.

## 0:30 Slide 2, the method (60 s)
Three steps.
First, know: rebuild the starting position from the data (committed bookings, one-way returns, the fleet per day).
All ten check values match. Forecast with a weekday pattern pooled per station type; on held-out fortnights it was
within 0.7 of a car of the theoretical noise floor, so we kept it simple.
Second, price the uncertainty: for every station and day we simulate a thousand random futures and compute what
the first car, the second car, the twentieth car would earn on average. The last cars are only used when demand turns
out high, so the optimiser values them less. That is robustness built into the objective instead of a safety margin.
Third, decide with one mixed-integer model: adds, removes, transfers, trucks, upgrades. The key insight of this
instance: 667 premium cars for a need of 250 and a removal cap of 66. The money is in letting premium cars serve
midsize customers. We value each upgrade by the probability the higher category really has a spare car that day.
Trusting upgrades fully moved 980 cars and lost money; the probability version is the winner.

## 1:30 Slide 3, results (40 s)
4.11 million mean profit on a hundred random futures. Plus 967 thousand, plus 31 percent over the baseline plan,
plus 1.08 million over doing nothing. Every variant in the table was scored by our own re-implementation of the
scoring rules, never by the solver's objective. The organisers' feedback round scored the submitted plan at 4.11 million
with every cost line matching to the cent. A final polish on the real scoring rules, where each edit had to be
confirmed on futures it never saw, added 23 thousand on top of the model's plan.

## 2:10 Slide 4, what the plan does and does it hold (30 s)
Drain the two over-stocked stations into the short downtown ones in the first four days by truck, top up before the
second Saturday, serve midsize demand with surplus premium cars. We tested the plan in ten different noise
models, including the extra spread we measured in the history, and on 600 individual random draws: it was ahead
of every alternative in every single draw.

## 2:40 Slide 5, honesty and next steps (20 s)
What did not work: shading the forecast, the booking-pace signal, more solver time on an over-optimistic model.
Next: model the upgrade capacity as random, swap in an ML forecaster at SIXT scale, run it every morning on the
live snapshot. Two scripts rebuild the plan from the raw data.

## Likely questions, short answers
- Why no machine learning? Eight weeks, forty series. Our forecast error is 5.7 cars per cell-day against a noise
  floor of 5.0 (the error of a forecast that knows the true mean, at the measured spread). No model can beat the floor; the profit is in handling the noise, which the buckets do. The forecast
  is a plug-in; at SIXT scale you would put gradient boosting there and keep the optimiser.
- How do you know it holds on the hidden scenarios? They are random draws from the same process as the public one.
  On 600 draws in four noise models the plan was never beaten. Worst draw 3.97 million, still far above the next team.
- Why trucks on day 1 with 342 cars? The rules allow it and the cost is 90 thousand against 1 million of gain. In
  production a per-day truck limit is one constraint away.
- Is it reproducible? Two scripts, no API keys. The solver is time-limited, so another machine may land on a
  slightly different plan; the submitted file is in the repo.
- Why single-threaded CBC? Multi-threaded CBC returned variable values that did not match its reported objective.
  We caught it because we never trust the solver's number, only the referee's.
- Biggest limitation? Upgrade capacity is a probability weight, not a random quantity inside the model. That is the
  first thing to fix with more time.
