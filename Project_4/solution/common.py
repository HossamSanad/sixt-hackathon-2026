"""Shared pieces: data, Level 0, forecasts, noise model, revenue buckets, local scorer.

Arrays are indexed [station, category, day] with day 0..13 = day 1..14 of the plan.
"""

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

P4 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(P4))
from fleetkit import load_instance  # noqa: E402

T = 14
CATS = ["economy", "compact", "midsize", "premium"]
SHARES = np.array([0.0, 0.6, 0.7, 0.8, 0.9, 1.0])
HISTORY_DAYS = 56  # history covers day -55 .. day 0
WEEKS = 6  # full Monday-to-Sunday weeks used from the history (the first 2 are warm-up:
#            rentals picked up before the history window are missing there)


class Data:
    """Everything the model and the scorer need, as plain numpy arrays and dicts."""


def load(forecast_method: str = "pooled", shrink: float = 1.0) -> Data:
    inst = load_instance(data_dir=P4 / "data")
    D = Data()
    D.inst = inst
    D.first = pd.Timestamp(inst.horizon.first_date.iloc[0])
    D.dates = [D.first + pd.Timedelta(days=t) for t in range(T)]
    D.stations = inst.stations.station_id.tolist()
    D.sidx = {s: i for i, s in enumerate(D.stations)}
    D.kidx = {k: i for i, k in enumerate(CATS)}
    D.mu = inst.stations.max_utilization.to_numpy()
    D.stype = inst.stations.station_type.tolist()
    cats = inst.categories.set_index("category").loc[CATS]
    D.hold = cats.holding_cost_per_day.to_numpy(dtype=float)
    D.add_cost = cats.addition_cost_per_car.to_numpy(dtype=float)
    D.add_cap = cats.addition_cap.to_numpy(dtype=int)
    D.rem_cap = cats.removal_cap.to_numpy(dtype=int)
    D.arcs = {
        (r.from_station_id, r.to_station_id): (float(r.distance_km), int(r.lead_time_days))
        for r in inst.distances.itertuples()
    }
    tc = inst.transfer_costs.set_index("mode")
    D.driver = (float(tc.loc["driver", "fixed_cost"]), float(tc.loc["driver", "cost_per_km"]))
    D.truck = (float(tc.loc["truck", "fixed_cost"]), float(tc.loc["truck", "cost_per_km"]))
    D.truck_cap = int(tc.loc["truck", "capacity"])

    r = inst.reservations.copy()
    r["pd"] = (r.pickup_date - D.first).dt.days + 1  # day number, 1 = first plan day
    r["rd"] = (r.return_date - D.first).dt.days + 1
    D.res = r
    level0(D)
    history(D)
    forecast(D, method=forecast_method, shrink=shrink)
    price_curves(D)
    return D


# ---------------------------------------------------------------- Level 0
def level0(D: Data) -> None:
    S, K = len(D.stations), len(CATS)
    c = np.zeros((S, K, T))
    arr = np.zeros((S, K, T))
    dep = np.zeros((S, K, T))
    committed_revenue = 0.0
    active = D.res[D.res.status.isin(["open", "booked"])]
    for row in active.itertuples():
        s, k = D.sidx[row.pickup_station_id], D.kidx[row.category]
        lo, hi = max(row.pd, 1), min(row.rd, T)
        if lo <= hi:
            c[s, k, lo - 1 : hi] += 1  # R1
            committed_revenue += row.revenue * (hi - lo + 1) / (row.rd - row.pd + 1)  # R9
        if row.return_station_id != row.pickup_station_id:  # R2: moves the day after return
            day = row.rd + 1
            if 1 <= day <= T:
                dep[s, k, day - 1] += 1
                arr[D.sidx[row.return_station_id], k, day - 1] += 1

    snap = D.inst.fleet_snapshot
    idle = snap[snap.status == "idle"][["station_id", "category"]]
    on_rent = snap[snap.status == "on_rent"].merge(
        D.res[["reservation_id", "pickup_station_id"]], on="reservation_id"
    )[["pickup_station_id", "category"]].rename(columns={"pickup_station_id": "station_id"})
    f0 = np.zeros((S, K))
    for row in pd.concat([idle, on_rent]).itertuples():
        f0[D.sidx[row.station_id], D.kidx[row.category]] += 1

    D.c, D.arr, D.dep, D.f0 = c, arr, dep, f0
    D.f_dn = f0[:, :, None] + np.cumsum(arr - dep, axis=2)  # R3 with the do-nothing plan
    D.committed_revenue = committed_revenue


def check_level0(D: Data) -> bool:
    ok = True
    for row in D.inst.check_values.itertuples():
        s, k, t = D.sidx[row.station_id], D.kidx[row.category], (row.date - D.first).days
        mine = (D.c[s, k, t], D.arr[s, k, t], D.dep[s, k, t], D.f_dn[s, k, t])
        want = (row.committed_car_days, row.oneway_arrivals, row.oneway_departures, row.station_fleet)
        match = all(abs(a - b) < 1e-9 for a, b in zip(mine, want))
        ok &= match
        print(f"  {row.station_id} {row.category:8} {row.date.date()}  mine={tuple(int(v) for v in mine)}"
              f"  expected={want}  {'OK' if match else 'MISMATCH'}")
    return ok


# ---------------------------------------------------------------- history and forecasts
def history(D: Data) -> None:
    """Cars on rent per station, category and history day, then per full week: pw[s, k, week, weekday]."""
    S, K = len(D.stations), len(CATS)
    h0 = 1 - HISTORY_DAYS
    load_hist = np.zeros((S, K, HISTORY_DAYS))
    hist = D.res[D.res.status.isin(["completed", "open"])]  # everything picked up in the history
    for row in hist.itertuples():
        lo, hi = max(row.pd, h0), min(row.rd, 0)
        if lo <= hi:
            load_hist[D.sidx[row.pickup_station_id], D.kidx[row.category], lo - h0 : hi - h0 + 1] += 1
    days = np.arange(h0, 1)
    use = days >= 1 - 7 * WEEKS  # last WEEKS full weeks; day 1 is a Monday, so these start on Mondays
    D.load_hist = load_hist
    D.pw = load_hist[:, :, use].reshape(S, K, WEEKS, 7)  # weekday 0 = Monday

    comp = D.res[D.res.status == "completed"].assign(days=lambda d: d.rd - d.pd + 1)
    agg = comp.groupby(["pickup_station_id", "category"])[["revenue", "days"]].sum()
    cat_rate = comp.groupby("category").revenue.sum() / comp.groupby("category").days.sum()
    base = np.zeros((S, K))
    for s in D.stations:
        for k in CATS:
            base[D.sidx[s], D.kidx[k]] = (
                agg.loc[(s, k), "revenue"] / agg.loc[(s, k), "days"] if (s, k) in agg.index else cat_rate[k]
            )
    D.base = base


def expected_load(D: Data, pw: np.ndarray, method: str) -> np.ndarray:
    """Expected cars on rent per station, category and weekday, from per-week data pw[s, k, w, wd].

    raw:    mean per cell and weekday (7 numbers per cell, each from len(weeks) observations).
    pooled: level per cell x weekday profile shared by all stations of the same type and category.
            Fewer parameters, so less noise, if the weekday pattern really is shared (backtest() checks).
    """
    if method == "raw":
        return pw.mean(axis=2)
    level = pw.mean(axis=(2, 3))  # [s, k]
    out = np.zeros_like(level[:, :, None].repeat(7, axis=2))
    for st in set(D.stype):
        idx = [i for i, t in enumerate(D.stype) if t == st]
        prof = pw[idx].sum(axis=(0, 2))  # [k, wd]
        prof = prof / prof.mean(axis=1, keepdims=True)
        out[idx] = level[idx][:, :, None] * prof[None]
    return out


PSEUDO_STARTS = [-41, -34, -27, -20, -13]  # Mondays inside the history used as pretend "day 1"s


def committed_share_curve(D: Data, exclude: int | None = None) -> dict:
    """How much of a fortnight is normally booked before it starts, per station type and horizon day.

    Replays pretend fortnights starting on history Mondays: r[type][j] = rentals covering pretend day j that
    were booked before pretend day 1, divided by all rentals covering that day. On the real horizon the same
    ratio tells us how the bookings on file compare with the usual pace.
    """
    hist = D.res[D.res.status.isin(["completed", "open"])]
    bd = ((hist.booking_date - D.first).dt.days + 1).to_numpy()
    pd_, rd_ = hist.pd.to_numpy(), hist.rd.to_numpy()
    types = hist.pickup_station_id.map(dict(zip(D.stations, D.stype))).to_numpy()
    out = {}
    for st in sorted(set(D.stype)):
        com, tot = np.zeros(T), np.zeros(T)
        sel = types == st
        for h1 in PSEUDO_STARTS:
            if h1 == exclude:
                continue
            for j in range(T):
                cover = sel & (pd_ <= h1 + j) & (rd_ >= h1 + j)
                tot[j] += cover.sum()
                com[j] += (cover & (bd < h1)).sum()
        out[st] = np.clip(com / np.maximum(tot, 1), 0.02, 0.99)
    return out


def level_multiplier(D: Data, c: np.ndarray, load_wd: np.ndarray, share: dict, shrink: float = 1.0) -> np.ndarray:
    """Per station type: bookings on file / (usual booked share x historical load), pooled over all cells and
    days of the fortnight. 1.0 = this fortnight is booking at the historical pace. `shrink` pulls the
    multiplier toward 1 (0 = ignore the signal, 1 = trust it fully)."""
    mult = np.ones(len(D.stations))
    L_hist = load_wd[:, :, np.arange(T) % 7]
    for st in set(D.stype):
        idx = [i for i, t in enumerate(D.stype) if t == st]
        implied = (c[idx].sum(axis=(0, 1)) / share[st]).sum()
        m = implied / L_hist[idx].sum()
        mult[idx] = 1.0 + shrink * (m - 1.0)
    return mult


def forecast(D: Data, method: str = "pooled", shrink: float = 1.0) -> None:
    """Demand to come = expected cars on rent on that weekday minus committed car-days (README section 3).

    pooled: historical level per cell x weekday shape per station type.
    blend:  the same, scaled per station type by the booking signal (level_multiplier): if a station type has
            more bookings on file than its usual share of a fortnight, its whole demand level is raised.
    """
    D.forecast_method = method
    D.load_wd = expected_load(D, D.pw, "pooled")
    D.share = committed_share_curve(D)
    D.level_mult = level_multiplier(D, D.c, D.load_wd, D.share, shrink)
    L_hist = D.load_wd[:, :, np.arange(T) % 7]
    D.demand_pooled = np.maximum(0.0, L_hist - D.c)
    D.demand_blend = np.maximum(0.0, D.level_mult[:, None, None] * L_hist - D.c)
    D.demand = D.demand_blend if method == "blend" else D.demand_pooled


def backtest(D: Data) -> dict:
    """Forecast pretend fortnights inside the history (starting on history days -20 and -13) from the weeks
    before them, and compare with what happened. Mean absolute error per cell and day, in cars, for the
    demand to come (what the model actually uses). Lower is better."""
    S, K = len(D.stations), len(CATS)
    h0 = 1 - HISTORY_DAYS
    hist = D.res[D.res.status.isin(["completed", "open"])]
    bd = ((hist.booking_date - D.first).dt.days + 1).to_numpy()
    pd_, rd_ = hist.pd.to_numpy(), hist.rd.to_numpy()
    si = hist.pickup_station_id.map(D.sidx).to_numpy()
    ki = hist.category.map(D.kidx).to_numpy()
    errs = {name: [] for name in ["raw", "pooled", "blend_half", "blend_full"]}
    for h1 in [-20, -13]:
        train_days = np.arange(1 - 7 * WEEKS, h1)  # whole weeks before the pretend fortnight
        pw = D.load_hist[:, :, train_days - h0].reshape(S, K, -1, 7)
        truth = D.load_hist[:, :, np.arange(h1, h1 + T) - h0]
        c = np.zeros((S, K, T))
        for j in range(T):
            cover = (pd_ <= h1 + j) & (rd_ >= h1 + j) & (bd < h1)
            np.add.at(c[:, :, j], (si[cover], ki[cover]), 1)
        truth_to_come = np.maximum(0.0, truth - c)
        share = committed_share_curve(D, exclude=h1)
        for name in errs:
            if name == "raw":
                L = expected_load(D, pw, "raw")[:, :, np.arange(T) % 7]
            else:
                L_wd = expected_load(D, pw, "pooled")
                L = L_wd[:, :, np.arange(T) % 7]
                if name.startswith("blend"):
                    mult = level_multiplier(D, c, L_wd, share, shrink=0.5 if name == "blend_half" else 1.0)
                    L = mult[:, None, None] * L
            pred = np.maximum(0.0, L - c)
            errs[name].append(np.abs(pred - truth_to_come).mean())
    return {k: round(float(np.mean(v)), 3) for k, v in errs.items()}


def noise_stats(D: Data) -> dict:
    """How the history varies from week to week, for cells with enough cars to say anything."""
    mean, var = D.pw.mean(axis=2), D.pw.var(axis=2, ddof=1)
    big = mean >= 5
    disp = var[big] / mean[big]
    return dict(dispersion_median=float(np.median(disp)),
                rel_std_median=float(np.median(np.sqrt(var[big]) / mean[big])),
                cells=int(big.sum()))


def make_scenarios(D: Data, n: int, seed: int, level_sigma: float = 0.1, base_sigma: float = 0.025,
                   demand: np.ndarray | None = None) -> list[tuple[np.ndarray, np.ndarray]]:
    """Random futures: Poisson car counts around the forecast, with a little extra level noise so the
    variance-to-mean ratio matches the history (about 1.15), and a small wobble on base revenue."""
    rng = np.random.default_rng(seed)
    mean = D.demand if demand is None else demand
    out = []
    for _ in range(n):
        rate = mean * rng.lognormal(-level_sigma**2 / 2, level_sigma, mean.shape)
        dem = rng.poisson(rate).astype(float)
        base = D.base * rng.lognormal(-base_sigma**2 / 2, base_sigma, D.base.shape)
        out.append((dem, base))
    return out


def make_rental_scenarios(D: Data, n: int, seed: int, level: np.ndarray | None = None,
                          base_sigma: float = 0.025) -> list[tuple[np.ndarray, np.ndarray]]:
    """Random futures built from simulated rentals instead of independent daily counts.

    Pickups per cell and day ~ Poisson(historical pickup rate for that weekday x share not yet booked),
    rental length drawn from the category's historical lengths. A rental occupies its car on consecutive days,
    so the noise is day-correlated like the history (+0.73 day to day). Means match the pooled forecast
    (optionally scaled per station by `level`). Used as a stress world, not for building plans.
    """
    rng = np.random.default_rng(seed)
    S, K = len(D.stations), len(CATS)
    hist = D.res[(D.res.status.isin(["completed", "open"])) & (D.res.pd >= 1 - 7 * WEEKS)]
    pick = np.zeros((S, K, 7))
    for row in hist.itertuples():
        pick[D.sidx[row.pickup_station_id], D.kidx[row.category], (row.pd - 1) % 7] += 1
    pick /= WEEKS
    if level is not None:
        pick *= level[:, None, None]
    comp = D.res[D.res.status == "completed"]
    lengths = {k: (comp[comp.category == k].rd - comp[comp.category == k].pd + 1).to_numpy() for k in CATS}
    lead = (comp.pickup_date - comp.booking_date).dt.days.to_numpy()
    p_to_come = np.array([(lead <= j - 1).mean() for j in range(1, T + 1)])  # booked on/after day 1
    out = []
    for _ in range(n):
        dem = np.zeros((S, K, T))
        for s in range(S):
            for k in range(K):
                for j in range(T):
                    m = rng.poisson(pick[s, k, j % 7] * p_to_come[j])
                    if m == 0:
                        continue
                    for ln in rng.choice(lengths[CATS[k]], size=m):
                        dem[s, k, j : min(T, j + ln)] += 1
        base = D.base * rng.lognormal(-base_sigma**2 / 2, base_sigma, D.base.shape)
        out.append((dem, base))
    return out


# ---------------------------------------------------------------- price factors and revenue buckets
def price_curves(D: Data) -> None:
    """True revenue curve g(q) = q * price_factor(q) per station type and category (R8)."""
    pf = D.inst.price_factors
    D.g = {}
    for (st, k), grp in pf.groupby(["station_type", "category"]):
        q = grp.served_share.to_numpy()
        D.g[st, k] = np.concatenate([[0.0], q * grp.price_factor.to_numpy()])


def upper_concave_envelope(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    hull = [0]
    for i in range(1, len(x)):
        while len(hull) >= 2:
            a, b = hull[-2], hull[-1]
            if (y[b] - y[a]) * (x[i] - x[a]) <= (y[i] - y[a]) * (x[b] - x[a]):
                hull.pop()
            else:
                break
        hull.append(i)
    return np.interp(x, x[hull], y[hull])


def revenue_curve(D: Data, s: int, k: int, served: np.ndarray, dem: np.ndarray) -> np.ndarray:
    """Revenue (in units of base revenue) of serving `served` car-days when the demand is `dem` (R8)."""
    q = np.divide(served, dem, out=np.zeros_like(served, dtype=float), where=dem > 0)
    return np.interp(q, SHARES, D.g[D.stype[s], CATS[k]]) * dem


def buckets_deterministic(D: Data, demand: np.ndarray) -> dict:
    """LP revenue buckets for one known demand per cell: (car-days in the bucket, marginal revenue / base).

    If the marginal revenue rises somewhere (downtown midsize dips at 80 %), an LP would fill a later bucket
    before an earlier one and overstate revenue (Appendix C). The upper concave envelope removes the dip.
    """
    out = {}
    S, K = demand.shape[:2]
    for s in range(S):
        for k in range(K):
            g = D.g[D.stype[s], CATS[k]]
            hull = upper_concave_envelope(SHARES, g)
            marg = np.diff(hull) / np.diff(SHARES)
            for t in range(T):
                dem = demand[s, k, t]
                if dem > 0:
                    out[s, k, t] = list(zip(dem * np.diff(SHARES), marg))
    return out


def buckets_expected(D: Data, scenarios: list, n_points: int = 12) -> dict:
    """LP revenue buckets for *uncertain* demand.

    For each cell, the expected revenue of having capacity x for demand to come is
        R(x) = mean over scenarios of revenue(min(x, D_n), D_n).
    R is concave, so its piecewise-linear version is a set of buckets with falling marginal revenue.
    The optimiser then sees that the last cars are only used when demand turns out high, and values
    them less. Same model size as the deterministic version; this is Level 4 built into Level 1-3.
    """
    dems = np.stack([d for d, _ in scenarios])  # [n, S, K, T]
    out = {}
    S, K = D.demand.shape[:2]
    for s in range(S):
        for k in range(K):
            for t in range(T):
                dn = dems[:, s, k, t]
                if dn.max() <= 0:
                    continue
                xs = np.unique(np.round(np.linspace(0, dn.max(), n_points)))
                R = np.array([revenue_curve(D, s, k, np.minimum(x, dn), dn).mean() for x in xs])
                R = upper_concave_envelope(xs, R)  # numerical safety, R is concave already
                sizes, marg = np.diff(xs), np.diff(R) / np.diff(xs)
                keep = marg > 1e-9
                out[s, k, t] = list(zip(sizes[keep], marg[keep]))
    return out


# ---------------------------------------------------------------- local scorer (Appendix A)
def plan_arrays(D: Data, plan: pd.DataFrame):
    """Turn a plan table into add/remove/flow arrays and the transfer cost."""
    S, K = len(D.stations), len(CATS)
    add, rem, flow = np.zeros((S, K, T)), np.zeros((S, K, T)), np.zeros((S, K, T))
    driver_cost, trucks = 0.0, {}
    for row in plan.itertuples():
        s, k = D.sidx[row.station_id], D.kidx[row.category]
        t, n = (pd.Timestamp(row.date) - D.first).days, int(row.cars)
        if row.action == "add":
            add[s, k, t] += n
        elif row.action == "remove":
            rem[s, k, t] += n
        else:
            km, lt = D.arcs[row.station_id, row.to_station_id]
            flow[s, k, t] -= n
            if t + lt < T:
                flow[D.sidx[row.to_station_id], k, t + lt] += n
            if row.mode == "driver":
                driver_cost += n * (D.driver[0] + D.driver[1] * km)
            else:
                key = (row.station_id, row.to_station_id, t)
                trucks[key] = trucks.get(key, 0) + n
    truck_cost = sum(
        math.ceil(n / D.truck_cap) * (D.truck[0] + D.truck[1] * D.arcs[o, d][0]) for (o, d, _), n in trucks.items()
    )
    return add, rem, flow, driver_cost + truck_cost


def score(D: Data, plan: pd.DataFrame, demand: np.ndarray, base: np.ndarray, arrays=None) -> dict:
    """Re-implementation of the scoring rules, to compare plans offline. Not the official scorer."""
    S, K = len(D.stations), len(CATS)
    add, rem, flow, transfer_cost = plan_arrays(D, plan) if arrays is None else arrays
    f = D.f_dn + np.cumsum(add - rem + flow, axis=2)
    violations = int((f < D.c - 1e-9).sum())
    cap_ok = bool(np.all(add.sum(axis=(0, 2)) <= D.add_cap) and np.all(rem.sum(axis=(0, 2)) <= D.rem_cap))

    a = np.maximum(0.0, D.mu[:, None, None] * f - D.c)  # R6
    own = np.minimum(demand, a)  # R7
    served = own.copy()
    for k in range(1, K):
        up = np.minimum(a[:, k] - own[:, k], demand[:, k - 1] - own[:, k - 1])
        served[:, k - 1] += up
    new_revenue = 0.0  # R8 with the price factors exactly as given
    for s in range(S):
        for k in range(K):
            new_revenue += float(revenue_curve(D, s, k, served[s, k], demand[s, k]).sum() * base[s, k])

    cars_total = D.f0.sum(axis=0)[:, None] + np.cumsum((add - rem).sum(axis=0), axis=1)  # incl. in transit
    holding = float((D.hold[:, None] * cars_total).sum())
    addition = float((D.add_cost * add.sum(axis=(0, 2))).sum())
    profit = D.committed_revenue + new_revenue - holding - addition - transfer_cost
    return dict(valid=violations == 0 and cap_ok, violations=violations, profit=profit,
                new_revenue=new_revenue, holding=holding, addition=addition,
                transfer=transfer_cost, added=int(add.sum()), removed=int(rem.sum()),
                transferred=int(plan.loc[plan.action == "transfer", "cars"].sum()))  # gross, as the official result
