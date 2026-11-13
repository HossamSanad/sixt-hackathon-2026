"""Optimisation models and evaluation.

solve_category: one MILP per category (adds, removals, driver transfers), trucks added afterwards.
solve_joint:    all categories in one MILP, with upgrades between categories and trucks (Level 3).
Both take revenue buckets from common.buckets_deterministic (one forecast) or
common.buckets_expected (averaged over random futures, Level 4).

Run from Project_4/:  . .venv/bin/activate && python solution/solve.py
Writes solution/sample_plan.csv. It does NOT submit anything.
"""

import math
import time

import numpy as np
import pandas as pd
import pulp

from common import CATS, P4, T, buckets_expected, check_level0, load, make_scenarios, plan_arrays, score
from fleetkit import baseline_plan, write_plan

COLS = ["action", "date", "category", "station_id", "to_station_id", "mode", "cars"]
OUT = P4 / "solution" / "sample_plan.csv"


def _solver(time_limit: int, gap: float, warm_start: bool = False):
    # Single-threaded on purpose: with threads>1 this CBC build reports one solution and returns
    # the variable values of another (checked: objective -8,642 read back vs 806,226 in CBC's log).
    return pulp.COIN_CMD(msg=False, timeLimit=time_limit, gapRel=gap, warmStart=warm_start)


def transfer_cost(D, o: str, d: str, cars: int) -> tuple[float, int]:
    """Cheapest mix of trucks and drivers for `cars` on one route and day: (cost, trucks used)."""
    km = D.arcs[o, d][0]
    per_driver = D.driver[0] + D.driver[1] * km
    per_truck = D.truck[0] + D.truck[1] * km
    best = (cars * per_driver, 0)
    for j in range(1, math.ceil(cars / D.truck_cap) + 1):
        cost = j * per_truck + max(0, cars - j * D.truck_cap) * per_driver
        if cost < best[0]:
            best = (cost, j)
    return best


def _capacity_constraints(m, D, s, k, t, f, served_cars, dem_cap: float):
    """served_cars <= max(0, mu*f - c): exact with one binary when c > 0 (R6)."""
    c = float(D.c[s, k, t])
    mu = float(D.mu[s])
    if c == 0:
        m += served_cars <= mu * f
    else:
        z = m.add_variable(f"z_{s}_{k}_{t}", cat="Binary")
        m += served_cars <= mu * f - c + c * (1 - z)
        m += served_cars <= dem_cap * z


def _rows(D, add, rem, tr, k_of=None):
    rows = []
    for key, v in add.items():
        if (n := round(v.value() or 0)) > 0:
            s, t = key[0], key[-1]
            k = key[1] if k_of is None else k_of
            rows.append(dict(action="add", date=D.dates[t], category=CATS[k], station_id=D.stations[s],
                             to_station_id=None, mode=None, cars=n))
    for key, v in rem.items():
        if (n := round(v.value() or 0)) > 0:
            s, t = key[0], key[-1]
            k = key[1] if k_of is None else k_of
            rows.append(dict(action="remove", date=D.dates[t], category=CATS[k], station_id=D.stations[s],
                             to_station_id=None, mode=None, cars=n))
    for key, v in tr.items():
        if (n := round(v.value() or 0)) > 0:
            o, d, t = key[0], key[1], key[2]
            k = key[3] if k_of is None else k_of
            mode = key[4] if len(key) > 4 else "driver"
            rows.append(dict(action="transfer", date=D.dates[t], category=CATS[k], station_id=o,
                             to_station_id=d, mode=mode, cars=n))
    return rows


# ---------------------------------------------------------------- per-category model
def solve_category(D, k: int, buckets: dict, time_limit: int = 45, gap: float = 0.005, verbose=True) -> list[dict]:
    """Max profit of one category: bucket revenue - holding - additions - driver transfers."""
    S = len(D.stations)
    m = pulp.LpProblem(f"fleet_{CATS[k]}", pulp.LpMaximize)
    add = {(s, t): m.add_variable(f"add_{s}_{t}", lowBound=0, cat="Integer") for s in range(S) for t in range(T)}
    rem = {(s, t): m.add_variable(f"rem_{s}_{t}", lowBound=0, cat="Integer") for s in range(S) for t in range(T)}
    tr = {(o, d, t): m.add_variable(f"tr_{o}_{d}_{t}", lowBound=0, cat="Integer")
          for (o, d), (km, lt) in D.arcs.items() for t in range(T - lt)}  # must arrive inside the horizon

    net = {(s, t): [add[s, t], -rem[s, t]] for s in range(S) for t in range(T)}
    for (o, d, t), v in tr.items():
        net[D.sidx[o], t].append(-v)
        net[D.sidx[d], t + D.arcs[o, d][1]].append(v)

    obj = []
    for s in range(S):
        running = []
        for t in range(T):
            running += net[s, t]
            f = float(D.f_dn[s, k, t]) + pulp.lpSum(running)
            m += f >= float(D.c[s, k, t])  # validity R5
            bk = buckets.get((s, k, t))
            if not bk:
                continue
            xs = []
            for b, (size, marg) in enumerate(bk):
                x = m.add_variable(f"x_{s}_{t}_{b}", lowBound=0, upBound=float(size))
                xs.append(x)
                obj.append(float(D.base[s, k] * marg) * x)
            _capacity_constraints(m, D, s, k, t, f, pulp.lpSum(xs), float(sum(sz for sz, _ in bk)))

    hold = float(D.hold[k])
    obj += [-(hold * (T - t) + float(D.add_cost[k])) * add[s, t] + hold * (T - t) * rem[s, t] for (s, t) in add]
    obj += [-(D.driver[0] + D.driver[1] * D.arcs[o, d][0]) * v for (o, d, _), v in tr.items()]
    m += pulp.lpSum(obj)
    m += pulp.lpSum(add.values()) <= int(D.add_cap[k])
    m += pulp.lpSum(rem.values()) <= int(D.rem_cap[k])

    stats = m.solve(_solver(time_limit, gap))
    if not stats.has_solution:
        raise RuntimeError(f"{CATS[k]}: no solution ({stats.status})")
    if verbose:
        print(f"    {CATS[k]:8} status={stats.status.name:10} model objective={stats.objective:,.0f}")
    return _rows(D, add, rem, tr, k_of=k)


def use_trucks(D, plan: pd.DataFrame) -> pd.DataFrame:
    """Same route and day, all categories together: fill the cheapest number of trucks (8 places each)
    and send the rest by driver (R10). Rows with the same key add up, so a category may get two rows."""
    other = plan[plan.action != "transfer"]
    out = [other]
    tr = plan[plan.action == "transfer"]
    for (o, d, date), grp in tr.groupby(["station_id", "to_station_id", "date"]):
        _, trucks = transfer_cost(D, o, d, int(grp.cars.sum()))
        places = trucks * D.truck_cap
        for row in grp.itertuples():
            by_truck = min(int(row.cars), places)
            places -= by_truck
            for mode, n in (("truck", by_truck), ("driver", int(row.cars) - by_truck)):
                if n > 0:
                    out.append(pd.DataFrame([dict(action="transfer", date=row.date, category=row.category,
                                                  station_id=o, to_station_id=d, mode=mode, cars=n)]))
    return pd.concat(out, ignore_index=True)[COLS] if len(out) > 1 else plan.copy()


def build_plan(D, buckets: dict, time_limit: int = 45, verbose=True) -> pd.DataFrame:
    rows = [r for k in range(len(CATS)) for r in solve_category(D, k, buckets, time_limit, verbose=verbose)]
    return use_trucks(D, pd.DataFrame(rows, columns=COLS))


# ---------------------------------------------------------------- joint model (Level 3)
def solve_joint(D, buckets: dict, time_limit: int = 240, gap: float = 0.003, warm: pd.DataFrame | None = None,
                upgrade_value: float = 1.0, fix: pd.DataFrame | None = None, verbose=True) -> pd.DataFrame:
    """All categories together: upgrades (free cars of k+1 serve demand of k at k's price) and trucks
    (one truck per route and day carries up to 8 cars of any category).

    Transfers: one integer variable per route, day and category; `in_truck` (continuous) is how many of
    the cars on that route and day ride in the `trucks` (integer) and the rest pay the driver price.
    `warm` is a plan (for example from build_plan) used as the starting solution.
    `upgrade_value` < 1 discounts the revenue of upgraded car-days: the model sees free higher-category cars
    as certain, but whether they are free depends on that category's own random demand.
    """
    S, K = len(D.stations), len(CATS)
    m = pulp.LpProblem("fleet_joint", pulp.LpMaximize)
    cells = [(s, k, t) for s in range(S) for k in range(K) for t in range(T)]
    add = {c: m.add_variable("add_%d_%d_%d" % c, lowBound=0, cat="Integer") for c in cells}
    rem = {c: m.add_variable("rem_%d_%d_%d" % c, lowBound=0, cat="Integer") for c in cells}
    tr, trucks, in_truck = {}, {}, {}
    for (o, d), (km, lt) in D.arcs.items():
        for t in range(T - lt):
            trucks[o, d, t] = m.add_variable(f"truck_{o}_{d}_{t}", lowBound=0, cat="Integer")
            in_truck[o, d, t] = m.add_variable(f"intruck_{o}_{d}_{t}", lowBound=0)
            for k in range(K):
                tr[o, d, t, k] = m.add_variable(f"tr_{o}_{d}_{t}_{k}", lowBound=0, cat="Integer")
    for (o, d, t), v in trucks.items():
        m += in_truck[o, d, t] <= D.truck_cap * v
        m += in_truck[o, d, t] <= pulp.lpSum(tr[o, d, t, k] for k in range(K))

    net = {c: [add[c], -rem[c]] for c in cells}
    for (o, d, t, k), v in tr.items():
        net[D.sidx[o], k, t].append(-v)
        net[D.sidx[d], k, t + D.arcs[o, d][1]].append(v)

    fleet = {}
    for s in range(S):
        for k in range(K):
            running = []
            for t in range(T):
                running += net[s, k, t]
                fleet[s, k, t] = float(D.f_dn[s, k, t]) + pulp.lpSum(running)
                m += fleet[s, k, t] >= float(D.c[s, k, t])  # validity R5

    # own[s,k,t]: demand of k served by cars of k;  up[s,k,t]: demand of k served by cars of k+1 (R7)
    obj = []
    own = {c: m.add_variable("own_%d_%d_%d" % c, lowBound=0) for c in cells}
    up = {c: m.add_variable("up_%d_%d_%d" % c, lowBound=0) for c in cells if c[1] < K - 1}
    size_of = {key: float(sum(sz for sz, _ in bk)) for key, bk in buckets.items()}
    for s, k, t in cells:
        bk = buckets.get((s, k, t))
        served = own[s, k, t] + (up[s, k, t] if k < K - 1 else 0)
        if bk:
            xs = []
            for b, (size, marg) in enumerate(bk):
                x = m.add_variable(f"x_{s}_{k}_{t}_{b}", lowBound=0, upBound=float(size))
                xs.append(x)
                obj.append(float(D.base[s, k] * marg) * x)
            m += pulp.lpSum(xs) == served
        else:
            m += served == 0
        uv = float(upgrade_value[s, k, t]) if isinstance(upgrade_value, np.ndarray) else float(upgrade_value)
        if k < K - 1 and uv < 1.0 and bk:
            obj.append(-(1.0 - uv) * float(D.base[s, k] * bk[0][1]) * up[s, k, t])
        cars_used = own[s, k, t] + (up[s, k - 1, t] if k > 0 else 0)  # own demand + upgrades given down
        cap_dem = size_of.get((s, k, t), 0.0) + (size_of.get((s, k - 1, t), 0.0) if k > 0 else 0.0)
        if cap_dem > 0:
            _capacity_constraints(m, D, s, k, t, fleet[s, k, t], cars_used, cap_dem)
        else:
            m += cars_used == 0

    for (s, k, t) in cells:
        hold = float(D.hold[k])
        obj.append(-(hold * (T - t) + float(D.add_cost[k])) * add[s, k, t] + hold * (T - t) * rem[s, k, t])
    for (o, d, t), v in trucks.items():
        km = D.arcs[o, d][0]
        per_driver, per_truck = D.driver[0] + D.driver[1] * km, D.truck[0] + D.truck[1] * km
        obj.append(-per_driver * (pulp.lpSum(tr[o, d, t, k] for k in range(K)) - in_truck[o, d, t]))
        obj.append(-per_truck * v)
    m += pulp.lpSum(obj)
    for k in range(K):
        m += pulp.lpSum(add[s, k, t] for s in range(S) for t in range(T)) <= int(D.add_cap[k])
        m += pulp.lpSum(rem[s, k, t] for s in range(S) for t in range(T)) <= int(D.rem_cap[k])

    int_vars = list(add.values()) + list(rem.values()) + list(tr.values()) + list(trucks.values())
    if fix is not None:  # diagnostic: fix the integer decisions to a plan, solve only the rest
        for v, val in _plan_values(D, fix, add, rem, tr, trucks, int_vars).items():
            v.lowBound = v.upBound = val
    elif warm is not None:
        # Two-phase warm start. Passing only the integer decisions makes CBC start from a solution with all
        # continuous variables at 0 (checked in its log: "MIPStart provided solution with cost 967992" for a
        # plan worth 3.9M). So first solve with the decisions fixed, which fills in every variable, then free
        # the decisions and start CBC from that complete solution.
        for v, val in _plan_values(D, warm, add, rem, tr, trucks, int_vars).items():
            v.lowBound = v.upBound = val
        st0 = m.solve(_solver(60, 1e-4))
        if verbose:
            print(f"    joint    warm start is worth {st0.objective:,.0f} to the model")
        for v in m.variables():
            v.setInitialValue(v.varValue if v.varValue is not None else 0)
        for v in int_vars:
            v.lowBound, v.upBound = 0, None

    stats = m.solve(_solver(time_limit, gap, warm_start=warm is not None))
    solve_joint.last_stats = stats
    if not stats.has_solution:
        raise RuntimeError(f"joint: no solution ({stats.status})")
    if verbose:
        print(f"    joint    status={stats.status.name:10} model objective={stats.objective:,.0f}"
              f"  bound={stats.best_bound:,.0f}")
    return use_trucks(D, pd.DataFrame(_rows(D, add, rem, tr), columns=COLS))


def upgrade_values(D, plan: pd.DataFrame, demand: np.ndarray | None = None) -> np.ndarray:
    """Per cell: probability that the next higher category has at least one free car there, given the fleet
    of `plan` and Poisson demand. Used as the upgrade value: where premium cars are plentiful (Marlow Airport)
    upgrades to midsize are nearly certain; where the higher category is tight they are worth little."""
    demand = D.demand if demand is None else demand
    S, K = len(D.stations), len(CATS)
    add, rem, flow, _ = plan_arrays(D, plan)
    f = D.f_dn + np.cumsum(add - rem + flow, axis=2)
    a = np.maximum(0.0, D.mu[:, None, None] * f - D.c)  # free capacity for new demand (R6)
    val = np.zeros((S, K, T))
    for k in range(K - 1):
        cap = np.floor(a[:, k + 1] - 1)  # free cars exist if D[k+1] <= cap
        lam = demand[:, k + 1]
        kk = np.arange(0, int(max(1, cap.max())) + 1)
        pmf = np.exp(-lam[..., None] + kk * np.log(np.maximum(lam[..., None], 1e-12)) - np.cumsum(np.log(np.maximum(kk, 1))))
        pmf[..., 0] = np.exp(-lam)
        cdf = np.where(kk <= cap[..., None], pmf, 0.0).sum(axis=-1)
        val[:, k] = np.where(cap < 0, 0.0, np.clip(cdf, 0.0, 1.0))
    val[:, K - 1] = 0.0
    return val


def _plan_values(D, plan: pd.DataFrame, add, rem, tr, trucks, int_vars) -> dict:
    """Integer variable values that reproduce a plan (0 for everything the plan does not use)."""
    vals = {v: 0 for v in int_vars}
    by_truck = {}
    for row in plan.itertuples():
        s, k, t = D.sidx[row.station_id], D.kidx[row.category], (pd.Timestamp(row.date) - D.first).days
        if row.action == "add":
            vals[add[s, k, t]] += int(row.cars)
        elif row.action == "remove":
            vals[rem[s, k, t]] += int(row.cars)
        else:
            key = (row.station_id, row.to_station_id, t)
            vals[tr[key + (k,)]] += int(row.cars)
            if row.mode == "truck":
                by_truck[key] = by_truck.get(key, 0) + int(row.cars)
    for key, n in by_truck.items():
        vals[trucks[key]] = math.ceil(n / D.truck_cap)
    return vals


# ---------------------------------------------------------------- evaluation
def evaluate(D, plans: dict[str, pd.DataFrame], scenarios: list, verbose=True) -> pd.DataFrame:
    """Profit on the forecast and mean +- standard error over random futures (the final ranking is a mean
    over 30 hidden scenarios; two plans within 2 SE of each other count as a tie)."""
    rows = []
    for name, plan in plans.items():
        arrays = plan_arrays(D, plan)
        r = score(D, plan, D.demand, D.base, arrays)
        profits = np.array([score(D, plan, dem, base, arrays)["profit"] for dem, base in scenarios])
        rows.append(dict(plan=name, valid=r["valid"], on_forecast=r["profit"], mean=profits.mean(),
                         se=profits.std(ddof=1) / np.sqrt(len(profits)), added=r["added"], removed=r["removed"],
                         transferred=r["transferred"], transfer_cost=r["transfer"]))
    df = pd.DataFrame(rows).sort_values("mean", ascending=False)
    if verbose:
        with pd.option_context("display.float_format", "{:,.0f}".format, "display.width", 200):
            print(df.to_string(index=False))
    return df


def main() -> None:
    t0 = time.time()
    print("Step 1  load data + Level 0 + forecast")
    D = load()
    print("Step 2  Level 0 check against data/check_values.csv")
    print("  ALL MATCH" if check_level0(D) else "  SOME MISMATCH, fix Level 0 first")
    print("Step 3  revenue buckets averaged over random futures")
    buckets = buckets_expected(D, make_scenarios(D, 200, seed=1))
    print("Step 4  optimise each category")
    plan = build_plan(D, buckets)
    write_plan(df_plan=plan, path=OUT)
    print(f"  wrote {OUT.relative_to(P4)}: {len(plan)} rows")
    print("Step 5  compare on 100 fresh random futures")
    evaluate(D, {"do-nothing": pd.DataFrame(columns=COLS), "baseline": baseline_plan(instance=D.inst),
                 "sample": plan}, make_scenarios(D, 100, seed=123))
    print(f"\nDone in {time.time() - t0:.0f}s. Nothing was submitted.")


if __name__ == "__main__":
    main()
