"""Referee polish: local search on a plan, judged only by the local re-implementation of the scoring rules
(Appendix A) on random futures the model never saw. The optimiser works on an approximation (concave price
envelope, upgrade probability weights, free upgrade order); this step edits the plan directly and keeps a
change only if the real rules say it pays.

python solution/polish.py <start variant> <out name> [minutes=20] [train futures=200] [train seed=555]

Moves: +-1/2/4 cars on existing adds, removes and transfers; new adds/removes on day 1 and day 8; new
transfers (2/4/8 cars) on any route for a set of departure days; a transfer shifted by one day.
Accept the best move of a sweep if its paired mean gain on the training futures exceeds 2 paired standard
errors and 250. The result is then checked on the referee set (seed 123) and a fresh seed, never on the
training futures. Writes variants/<out name>.csv. It does NOT submit anything.
"""

import sys
import time

import numpy as np
import pandas as pd

from common import CATS, P4, SHARES, T, load, make_scenarios, plan_arrays, score
from fleetkit import write_plan
from solve import COLS, evaluate, transfer_cost, use_trucks

VAR = P4 / "solution" / "variants"


class Referee:
    """Vectorised Appendix A scorer over many futures at once."""

    def __init__(self, D, scenarios):
        self.D = D
        self.dems = np.stack([d for d, _ in scenarios])      # [n, S, K, T]
        self.bases = np.stack([b for _, b in scenarios])     # [n, S, K]
        self.n, self.S, self.K = self.dems.shape[0], self.dems.shape[1], self.dems.shape[2]
        self.cars0 = D.f0.sum(axis=0)[:, None]
        self.g = {(s, k): D.g[D.stype[s], CATS[k]] for s in range(self.S) for k in range(self.K)}

    def profits(self, add, rem, flow, tcost):
        D = self.D
        f = D.f_dn + np.cumsum(add - rem + flow, axis=2)
        if (f < D.c - 1e-9).any():
            return None
        a = np.maximum(0.0, D.mu[:, None, None] * f - D.c)
        own = np.minimum(self.dems, a[None])
        served = own.copy()
        for k in range(1, self.K):
            up = np.minimum(a[None, :, k] - own[:, :, k], self.dems[:, :, k - 1] - own[:, :, k - 1])
            served[:, :, k - 1] += up
        rev = np.zeros(self.n)
        for (s, k), g in self.g.items():
            srv, dem = served[:, s, k, :], self.dems[:, s, k, :]
            q = np.divide(srv, dem, out=np.zeros_like(srv), where=dem > 0)
            rev += (np.interp(q, SHARES, g) * dem).sum(axis=1) * self.bases[:, s, k]
        cars_total = self.cars0 + np.cumsum((add - rem).sum(axis=0), axis=1)
        holding = float((D.hold[:, None] * cars_total).sum())
        addition = float((D.add_cost * add.sum(axis=(0, 2))).sum())
        return D.committed_revenue + rev - holding - addition - tcost


class State:
    def __init__(self, D, plan):
        self.D = D
        self.add, self.rem, _, _ = plan_arrays(D, plan)
        self.tr = {}
        for row in plan[plan.action == "transfer"].itertuples():
            key = (D.sidx[row.station_id], D.sidx[row.to_station_id], (pd.Timestamp(row.date) - D.first).days,
                   D.kidx[row.category])
            self.tr[key] = self.tr.get(key, 0) + int(row.cars)
        self.arc = {(D.sidx[o], D.sidx[d]): (o, d, lt) for (o, d), (_, lt) in D.arcs.items()}

    def flow_and_cost(self, tr):
        D = self.D
        flow = np.zeros_like(self.add)
        per_route = {}
        for (o, d, t, k), n in tr.items():
            if n <= 0:
                continue
            lt = self.arc[o, d][2]
            flow[o, k, t] -= n
            flow[d, k, t + lt] += n
            per_route[o, d, t] = per_route.get((o, d, t), 0) + n
        cost = sum(transfer_cost(D, self.arc[o, d][0], self.arc[o, d][1], n)[0] for (o, d, t), n in per_route.items())
        return flow, cost

    def to_plan(self):
        D = self.D
        rows = []
        for (s, k, t), n in np.ndenumerate(self.add):
            if n > 0:
                rows.append(dict(action="add", date=D.dates[t], category=CATS[k], station_id=D.stations[s],
                                 to_station_id=None, mode=None, cars=int(n)))
        for (s, k, t), n in np.ndenumerate(self.rem):
            if n > 0:
                rows.append(dict(action="remove", date=D.dates[t], category=CATS[k], station_id=D.stations[s],
                                 to_station_id=None, mode=None, cars=int(n)))
        for (o, d, t, k), n in self.tr.items():
            if n > 0:
                rows.append(dict(action="transfer", date=D.dates[t], category=CATS[k], station_id=D.stations[o],
                                 to_station_id=D.stations[d], mode="truck", cars=int(n)))
        return use_trucks(D, pd.DataFrame(rows, columns=COLS))


def candidates(st):
    """Yield (label, add, rem, tr) for every neighbour of the current state."""
    D, S, K = st.D, st.add.shape[0], st.add.shape[1]
    add_used, rem_used = st.add.sum(axis=(0, 2)), st.rem.sum(axis=(0, 2))
    deltas = (1, -1, 2, -2, 4, -4)
    # existing adds / removes
    for arr, used, cap, name in ((st.add, add_used, D.add_cap, "add"), (st.rem, rem_used, D.rem_cap, "rem")):
        for (s, k, t), n in np.ndenumerate(arr):
            if n == 0:
                continue
            for dl in deltas:
                if n + dl < 0 or (dl > 0 and used[k] + dl > cap[k]):
                    continue
                a2 = arr.copy(); a2[s, k, t] = n + dl
                yield (f"{name} {D.stations[s]} {CATS[k]} d{t+1} {dl:+d}",
                       a2 if name == "add" else st.add, a2 if name == "rem" else st.rem, st.tr)
    # new adds / removes on day 1 and day 8
    for s in range(S):
        for k in range(K):
            for t in (0, 7):
                for dl in (1, 2, 4):
                    if st.add[s, k, t] == 0 and add_used[k] + dl <= D.add_cap[k]:
                        a2 = st.add.copy(); a2[s, k, t] = dl
                        yield (f"new add {D.stations[s]} {CATS[k]} d{t+1} +{dl}", a2, st.rem, st.tr)
                    if st.rem[s, k, t] == 0 and rem_used[k] + dl <= D.rem_cap[k]:
                        r2 = st.rem.copy(); r2[s, k, t] = dl
                        yield (f"new rem {D.stations[s]} {CATS[k]} d{t+1} +{dl}", st.add, r2, st.tr)
    # existing transfers: size and date
    for key, n in list(st.tr.items()):
        o, d, t, k = key
        lt = st.arc[o, d][2]
        for dl in deltas:
            if n + dl < 0:
                continue
            tr2 = dict(st.tr); tr2[key] = n + dl
            yield (f"tr {D.stations[o]}->{D.stations[d]} {CATS[k]} d{t+1} {dl:+d}", st.add, st.rem, tr2)
        for dt in (-1, 1):
            t2 = t + dt
            if 0 <= t2 and t2 + lt < T:
                tr2 = dict(st.tr); tr2[key] = 0; k2 = (o, d, t2, k); tr2[k2] = tr2.get(k2, 0) + n
                yield (f"tr {D.stations[o]}->{D.stations[d]} {CATS[k]} d{t+1}->d{t2+1}", st.add, st.rem, tr2)
    # new transfers
    for (o, d), (_, _, lt) in st.arc.items():
        for k in range(K):
            for t in (0, 1, 2, 3, 4, 9, 10, 11):
                if t + lt >= T or st.tr.get((o, d, t, k), 0) > 0:
                    continue
                for n in (2, 4, 8):
                    tr2 = dict(st.tr); tr2[o, d, t, k] = n
                    yield (f"new tr {D.stations[o]}->{D.stations[d]} {CATS[k]} d{t+1} +{n}", st.add, st.rem, tr2)


def main(argv):
    start, out_name = argv[0], argv[1]
    minutes = float(argv[2]) if len(argv) > 2 else 20
    n_train = int(argv[3]) if len(argv) > 3 else 200
    seed = int(argv[4]) if len(argv) > 4 else 555
    t0 = time.time()
    D = load("pooled")
    plan0 = pd.read_csv(VAR / f"{start}.csv")
    ref = Referee(D, make_scenarios(D, n_train, seed=seed))
    st = State(D, plan0)
    flow, cost = st.flow_and_cost(st.tr)
    base = ref.profits(st.add, st.rem, flow, cost)
    # sanity: the vectorised referee must agree with common.score on the first future
    chk = score(D, plan0, ref.dems[0], ref.bases[0])["profit"]
    assert abs(chk - base[0]) < 1.0, (chk, base[0])
    print(f"start {start}: training mean {base.mean():,.0f} on {n_train} futures (seed {seed}); referee check OK")
    sweep = 0
    while time.time() - t0 < minutes * 60:
        sweep += 1
        best = None
        n_cand = 0
        for label, add, rem, tr in candidates(st):
            n_cand += 1
            flow, cost = st.flow_and_cost(tr)
            p = ref.profits(add, rem, flow, cost)
            if p is None:
                continue
            diff = p - base
            gain, se = diff.mean(), diff.std(ddof=1) / np.sqrt(len(diff))
            if gain > max(2 * se, 250) and (best is None or gain > best[0]):
                best = (gain, se, label, add, rem, tr, p)
        if best is None:
            print(f"sweep {sweep}: {n_cand} candidates, no move passes the test; stop")
            break
        gain, se, label, st.add, st.rem, st.tr, base = best
        print(f"sweep {sweep}: {n_cand} candidates, accept '{label}'  gain {gain:+,.0f} (se {se:,.0f})  "
              f"training mean {base.mean():,.0f}  [{time.time() - t0:.0f}s]")
    plan = st.to_plan()
    write_plan(df_plan=plan, path=VAR / f"{out_name}.csv")
    print(f"\nwrote variants/{out_name}.csv ({len(plan)} rows). Independent checks (never used in the search):")
    for name, sc in (("referee seed 123", make_scenarios(D, 100, seed=123)),
                     ("fresh seed 2026", make_scenarios(D, 300, seed=2026)),
                     ("dispersion 1.38, seed 11", make_scenarios(D, 100, seed=11, disp=1.38))):
        print(f"-- {name}")
        evaluate(D, {out_name: plan, start: plan0}, sc)


if __name__ == "__main__":
    main(sys.argv[1:])
