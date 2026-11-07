"""Chart data: how F_{k+1} (FOR at the TSO-DSO interface) changes over two days, with and without TSO export requests.

Writes for_time.json and for_time.csv into <out>/data.

Coordinates. The FOR CSVs (FOR_rolling<tag>.csv, columns P, Q) hold the ABSOLUTE interface exchange of each boundary
point, in MW / Mvar, positive = import. Here every point is shifted to the paper's Fig. 6 convention: deviation
(dP, dQ) from the interface exchange with all BESS idle, in kW / kvar, positive = import. The all-idle exchange of
slot t is not written by the model; it is computed from the executed slot of the no-request run:
    B_P(t) = P_PCC1(now=t) - sum_b Pexec_b(now=t),   B_Q(t) = Q_PCC1(now=t) - sum_b Qinv1_b(now=t)
(FOR_rolling_soc<tag>.csv). This neglects the change of network losses when the batteries go idle; the same estimate
from the export run differs by at most a few kW/kvar (reported in meta.idle_reference_check).

Slot mapping. Rolling step k (CSV column now) builds F_{k+1} for flexibility slot k+1 (CSV column target).
Slot index 1..96 runs over the two days (day 2: now + 48); the clock label is the START of the flexibility slot,
(slot - 1) * 30 min modulo 24 h. Step 48 of day 1 (target 1) is slot 49 = day 2, 00:00.

Where F_{k+1} comes from:
  computed   the 12 directional solves exist for that slot in the run (no-request: the FOR-at-every-step run, day 1,
             whose executed trajectory is checked to be identical to the no-request run; export runs: the requested
             slots 13-40 of day 1 only - the model builds F_{k+1} only when a request is due).
  same-state F_{k+1} is built at step k from the per-prosumer SOC at the start of step k and the frozen plan of slot k.
             When both (all 46 BESS, within 1e-6) equal those of the no-request run at the step that built a computed
             no-request FOR (same clock time; load/PV profiles are identical on both days), that FOR is used.
             This fills slots before the first request (2-12) and the day-2 slots after the SOC has re-converged.
  null       no FOR for that slot. The SOC-based bounds (soc_bound_*) are given for every slot instead.

Usage: python build_for_time.py [--runs DIR] [--out DIR] [--no-default] [--case KEY=LANE/TAG ...]
  default cases: no_request; export_guarantee_on = N3 ..._FairBox1_RollOfferLog1_SCAlpha0 if finished, else N2
  _WC_EXPORT_free_today_a2x4p8fin2_TR4_FairBox1; export_guarantee_relaxed = N3 ..._SCAlpha99 if finished.
  e.g. --case export_guarantee_on_older=N2/_WC_EXPORT_free_today_a2x4p8fin2_TR4_FairBox1
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))     # package root: paths.py
import paths  # noqa: E402

RUNS = None                                   # folder of the lanes (--runs), set in main()
OUT = None                                    # <out>/data, set in main()
D2 = "_free_today_a2x4p8fin2_TR4"
NOREQ = ("N2", "_REF" + D2 + "_FairBox1")                                  # trajectory, both days
NOREQ_FOR = ("N2", "_REF_SWEEP_free_today_a2x4p8fin_TR4_FairBox1")        # F_{k+1} at every step of day 1
N3T = "_WC_EXPORT" + D2 + "_FairBox1_RollOfferLog1_SCAlpha"
# default export cases: the current-commit pair on N3 (guarantee on = SCAlpha0, relaxed = SCAlpha99) when finished;
# otherwise the older-commit guarantee-on run on N2 (same aggregate F_{k+1} within 0.02 kW / 0.04 kvar)
DEFAULT_CASES = {"export_guarantee_on": [("N3", N3T + "0"), ("N2", "_WC_EXPORT" + D2 + "_FairBox1")],
                 "export_guarantee_relaxed": [("N3", N3T + "99")]}
LABELS = {
    "no_request": "No TSO request",
    "export_guarantee_on": "TSO export requests, self-consumption guarantee",
    "export_guarantee_on_current": "TSO export requests, self-consumption guarantee",
    "export_guarantee_relaxed": "TSO export requests, guarantee relaxed",
}
OK = ("Optimal", "LocallyOptimal")
DT = 0.5
E_BAT, P_BAT, ETA, SOC_MIN = 4.2, 3.6, 0.949, 0.1        # kWh, kW, -, - (Table: E=4.2 kWh, P=3.6 kW, DOD 0.9, eta 0.949)
N_SLOTS = 96
REP_TIMES = {1: ["06:00", "07:00", "12:30", "17:00", "19:30", "21:30"], 2: ["07:00", "12:30", "15:00", "17:00", "21:30"]}
SAME_TOL = 1e-6


def clock(slot):
    m = ((slot - 1) % 48) * 30
    return f"{m // 60:02d}:{m % 60:02d}"


def read(p):
    if not p.exists() or p.stat().st_size == 0:
        return None
    d = pd.read_csv(p, skipinitialspace=True, encoding="utf-8-sig")
    d.columns = [c.strip() for c in d.columns]
    for c in d.columns:
        if pd.api.types.is_object_dtype(d[c]) or pd.api.types.is_string_dtype(d[c]):
            d[c] = d[c].astype(str).str.strip()
    return d


def done(lane, tag):
    f = RUNS / lane / f"done{tag}.txt"
    return f.exists() and "Return value = 0" in f.read_text(errors="ignore")


def two(lane, tag, stem):
    a, b = read(RUNS / lane / f"{stem}{tag}.csv"), read(RUNS / lane / f"{stem}{tag}_d2.csv")
    b = b.copy()
    b["now"] = b["now"] + 48
    return pd.concat([a, b], ignore_index=True)


def r1(x, n=1):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), n)


def for_points(lane, tag, B):
    """slot -> DataFrame of the 12 boundary points (deviation, kW/kvar), only where all 12 solves are optimal."""
    f = read(RUNS / lane / f"FOR_rolling{tag}.csv")
    out = {}
    if f is None or not len(f):
        return out
    f["slot"] = np.where(f["target"] < f["now"], f["target"] + 48, f["target"])
    for slot, g in f.groupby("slot"):
        g = g.sort_values("angle_deg")
        if len(g) != 12 or not g["status"].isin(OK).all():
            continue
        g = g.assign(dP=1000 * g["P"] - B.loc[slot, "BP"], dQ=1000 * g["Q"] - B.loc[slot, "BQ"])
        out[int(slot)] = g[["angle_deg", "dP", "dQ", "P", "Q", "VmaxTrue"]].reset_index(drop=True)
    return out


def area(P, Q):
    P, Q = np.asarray(P, float), np.asarray(Q, float)
    return 0.5 * abs(np.dot(P, np.roll(Q, -1)) - np.dot(Q, np.roll(P, -1)))


def soc_table(lane, tag):
    s = two(lane, tag, "FOR_rolling_soc")
    s = s.sort_values(["now", "battery"])
    return s


def bounds(s):
    s = s.assign(
        xe=np.minimum(P_BAT, (s["SOC_start"] - SOC_MIN).clip(lower=0) * E_BAT * ETA / DT),
        xi=np.minimum(P_BAT, (1 - s["SOC_start"]).clip(lower=0) * E_BAT / ETA / DT),
        e_up=(s["SOC_start"] - SOC_MIN).clip(lower=0) * E_BAT,
    )
    return s.groupby("now").agg(soc=("SOC_start", "mean"), xe=("xe", "sum"), xi=("xi", "sum"), e_up=("e_up", "sum"),
                                P=("P_PCC1", "first"), Q=("Q_PCC1", "first"), sb=("Pexec", "sum"), sq=("Qinv1", "sum"))


def same_state_map(run_soc, ref_soc, ref_for, exclude):
    """slot t -> slot u of the no-request FOR (ref_for) built from an identical state, or absent.
    F_t is built at step k = t-1 from the per-prosumer SOC at the start of step k and the frozen plan of slot k
    (executed battery power Pexec at now = k). Candidates: u = t (day 1, or slot 49) and u = t - 48 (day 2, same clock
    of day 1). Both SOC_start and Pexec of all 46 BESS must agree within SAME_TOL (pu / MW)."""
    rs = run_soc.pivot(index="now", columns="battery", values="SOC_start")
    re_ = run_soc.pivot(index="now", columns="battery", values="Pexec")
    qs = ref_soc.pivot(index="now", columns="battery", values="SOC_start")
    qe = ref_soc.pivot(index="now", columns="battery", values="Pexec")
    out = {}
    for t in range(2, N_SLOTS + 1):
        if t in exclude:
            continue
        for u in (t, t - 48):
            if u not in ref_for or (u == t and run_soc is ref_soc):
                continue
            k, ku = t - 1, u - 1
            if np.abs(rs.loc[k].values - qs.loc[ku].values).max() < SAME_TOL and                np.abs(re_.loc[k].values - qe.loc[ku].values).max() < SAME_TOL:
                out[t] = u
                break
    return out


def first_identical_slot(run_soc, ref_soc):
    pr = run_soc.pivot(index="now", columns="battery", values="SOC_start")
    qr = ref_soc.pivot(index="now", columns="battery", values="SOC_start")
    diff = (pr - qr).abs().max(axis=1)
    for t in range(1, N_SLOTS + 1):
        if (diff.loc[t:] < SAME_TOL).all():
            return t, diff
    return None, diff


def case_series(key, lane, tag, B, ref_soc, ref_for, is_ref=False):
    soc = soc_table(lane, tag)
    bd = bounds(soc)
    svc = two(lane, tag, "SCT_exec")
    req_slots = sorted(int(x) for x in svc.loc[svc["svc"] == 1, "now"].unique())
    own_for = for_points(lane, tag, B) if not is_ref else ref_for
    same = same_state_map(ref_soc if is_ref else soc, ref_soc, ref_for, exclude=set(own_for))
    fq = read(RUNS / lane / f"FRQ{tag}.csv")
    sv = read(RUNS / lane / f"FOR_rolling_svc{tag}.csv")
    frq = {} if fq is None else {int(r.target): r for r in fq.itertuples()}
    exe = {} if sv is None else {int(r.target): r for r in sv[sv["event"] == "execute"].itertuples()}

    cols = {k: [] for k in ("for_source", "dP_min", "dP_max", "dQ_min", "dQ_max", "area", "export_capability_kW",
                            "import_capability_kW", "operating_point", "p1_baseline_point", "requested_point",
                            "delivered_point", "service_vs_p1_baseline", "requested", "soc_mean_pct", "stored_energy_above_floor_kWh",
                            "soc_bound_export_kW", "soc_bound_import_kW")}
    polys = {}
    for t in range(1, N_SLOTS + 1):
        if t in own_for:
            g, src = own_for[t], "computed"
        elif t in same:
            g, src = ref_for[same[t]], f"same-state: no-request FOR of slot {same[t]} ({'d1' if same[t] <= 48 else 'd2'} {clock(same[t])})"
        else:
            g, src = None, None
        cols["for_source"].append(src)
        if g is not None:
            polys[t] = (g, src)
            cols["dP_min"].append(r1(g.dP.min())); cols["dP_max"].append(r1(g.dP.max()))
            cols["dQ_min"].append(r1(g.dQ.min())); cols["dQ_max"].append(r1(g.dQ.max()))
            cols["area"].append(r1(area(g.dP, g.dQ), 0))
            cols["export_capability_kW"].append(r1(-g.dP.min())); cols["import_capability_kW"].append(r1(g.dP.max()))
        else:
            for k in ("dP_min", "dP_max", "dQ_min", "dQ_max", "area", "export_capability_kW", "import_capability_kW"):
                cols[k].append(None)
        b = bd.loc[t]
        cols["operating_point"].append([r1(1000 * b.P - B.loc[t, "BP"]), r1(1000 * b.Q - B.loc[t, "BQ"])])
        cols["requested"].append(t in req_slots)
        if t in frq:
            f = frq[t]
            cols["p1_baseline_point"].append([r1(f.S0_P_kW - B.loc[t, "BP"]), r1(f.S0_Q_kvar - B.loc[t, "BQ"])])
            cols["service_vs_p1_baseline"].append([r1(f.dP_kW), r1(f.dQ_kvar)])
            cols["requested_point"].append([r1(f.req_P_kW - B.loc[t, "BP"]), r1(f.req_Q_kvar - B.loc[t, "BQ"])])
        else:
            cols["p1_baseline_point"].append(None); cols["requested_point"].append(None)
            cols["service_vs_p1_baseline"].append(None)
        if t in exe:
            e = exe[t]
            cols["delivered_point"].append([r1(1000 * e.real_P - B.loc[t, "BP"]), r1(1000 * e.real_Q - B.loc[t, "BQ"])])
        else:
            cols["delivered_point"].append(None)
        cols["soc_mean_pct"].append(r1(100 * b.soc, 2))
        cols["stored_energy_above_floor_kWh"].append(r1(b.e_up))
        cols["soc_bound_export_kW"].append(r1(b.xe)); cols["soc_bound_import_kW"].append(r1(b.xi))
    return {"label": LABELS.get(key, key), "lane": lane, "tag": tag, "requested_slots": req_slots,
            "series": cols}, polys, soc, bd


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--case", action="append", default=[], help="KEY=LANE/TAG (export runs)")
    ap.add_argument("--no-default", action="store_true", help="drop the default export case")
    paths.add_args(ap, runs=True)
    a = ap.parse_args()
    global RUNS, OUT
    paths.use(a)
    RUNS, OUT = paths.runs_dir(), paths.data_out()
    cases = {}
    if not a.no_default:
        for k, cands in DEFAULT_CASES.items():
            ok = [c for c in cands if done(*c)]
            if ok:
                cases[k] = ok[0]
                if ok[0] != cands[0]:
                    print(f"WARNING {k}: {cands[0][0]}/{cands[0][1]} is not finished; using {ok[0][0]}/{ok[0][1]} "
                          "instead (the deck used the first)")
            else:
                print(f"{k}: no finished run among {cands}, skipped")
    for c in a.case:
        k, v = c.split("=", 1)
        lane, tag = v.split("/", 1)
        cases[k] = (lane, tag)
    for k, (lane, tag) in [("no_request", NOREQ), ("no_request_for", NOREQ_FOR)] + list(cases.items()):
        if not done(lane, tag):
            raise SystemExit(f"{k}: run {lane}/{tag} is not finished")

    # all-idle exchange from the no-request run
    ref_soc = soc_table(*NOREQ)
    rb = bounds(ref_soc)
    B = pd.DataFrame({"BP": 1000 * (rb.P - rb.sb), "BQ": 1000 * (rb.Q - rb.sq)})

    # the FOR-at-every-step run must have the same executed trajectory as the no-request run on day 1
    sw = soc_table(NOREQ_FOR[0], NOREQ_FOR[1]) if (RUNS / NOREQ_FOR[0] / f"FOR_rolling_soc{NOREQ_FOR[1]}_d2.csv").exists() else None
    swd1 = read(RUNS / NOREQ_FOR[0] / f"FOR_rolling_soc{NOREQ_FOR[1]}.csv")
    m = ref_soc[ref_soc["now"] <= 48].merge(swd1, on=["now", "battery"], suffixes=("", "_sw"))
    traj_diff = float(max((m.SOC_start - m.SOC_start_sw).abs().max(), (m.Pexec - m.Pexec_sw).abs().max(),
                          (m.P_PCC1 - m.P_PCC1_sw).abs().max()))
    if traj_diff > SAME_TOL or len(m) != 48 * 46:
        raise SystemExit(f"FOR-at-every-step run differs from the no-request run on day 1 ({traj_diff})")
    ref_for = for_points(*NOREQ_FOR, B)

    out_cases, polys_all, socs, bds = {}, {}, {}, {}
    c, p, s, b = case_series("no_request", *NOREQ, B, ref_soc, ref_for, is_ref=True)
    c["for_from"] = f"{NOREQ_FOR[0]}/{NOREQ_FOR[1]} (day 1; executed trajectory identical to the no-request run, max diff {traj_diff:.1e})"
    out_cases["no_request"], polys_all["no_request"], socs["no_request"], bds["no_request"] = c, p, s, b
    idle_check = {}
    for k, (lane, tag) in cases.items():
        c, p, s, b = case_series(k, lane, tag, B, ref_soc, ref_for)
        out_cases[k], polys_all[k], socs[k], bds[k] = c, p, s, b
        bp = 1000 * (b.P - b.sb) - B.BP
        bq = 1000 * (b.Q - b.sq) - B.BQ
        idle_check[k] = {"max_abs_dP_kW": r1(bp.abs().max(), 2), "max_abs_dQ_kvar": r1(bq.abs().max(), 2)}

    # comparison against the no-request case, per slot
    comp = {}
    n = out_cases["no_request"]["series"]
    for k in cases:
        e = out_cases[k]["series"]
        d_exp = [None if x is None or y is None else r1(x - y) for x, y in zip(e["export_capability_kW"], n["export_capability_kW"])]
        d_imp = [None if x is None or y is None else r1(x - y) for x, y in zip(e["import_capability_kW"], n["import_capability_kW"])]
        d_area = [None if x is None or y is None or y == 0 else r1(100 * x / y, 1) for x, y in zip(e["area"], n["area"])]
        d_soc = [r1(x - y, 2) for x, y in zip(e["soc_mean_pct"], n["soc_mean_pct"])]
        d_e = [r1(x - y) for x, y in zip(e["stored_energy_above_floor_kWh"], n["stored_energy_above_floor_kWh"])]
        d_bi = [r1(x - y) for x, y in zip(e["soc_bound_import_kW"], n["soc_bound_import_kW"])]
        d_be = [r1(x - y) for x, y in zip(e["soc_bound_export_kW"], n["soc_bound_export_kW"])]
        t_id, diff = first_identical_slot(socs[k], socs["no_request"])
        # key numbers
        rq = out_cases[k]["requested_slots"]
        first = rq[0] if rq else None
        after = [t for t in rq[1:] if d_exp[t - 1] is not None]

        def mean(series, ts):
            v = [series[t - 1] for t in ts if series[t - 1] is not None]
            return r1(np.mean(v)) if v else None

        def window(ts):
            return {"slots": [ts[0], ts[-1]], "times": f"{clock(ts[0])}-{clock(ts[-1])}",
                    "export_capability_mean_kW": {"with": mean(e["export_capability_kW"], ts), "without": mean(n["export_capability_kW"], ts)},
                    "import_capability_mean_kW": {"with": mean(e["import_capability_kW"], ts), "without": mean(n["import_capability_kW"], ts)},
                    "area_mean_pct_of_no_request": mean(d_area, ts)}

        neg = [t for t in range(1, N_SLOTS + 1) if e["dP_min"][t - 1] is not None and e["dP_min"][t - 1] > 0]
        tmax = max(neg, key=lambda t: e["dP_min"][t - 1]) if neg else None
        same_d2 = [t for t in range(49, N_SLOTS + 1) if e["for_source"][t - 1] not in (None, "computed")]
        key = {
            "first_request": None if first is None else {
                "slot": first, "time": clock(first),
                "export_capability_kW": {"with": e["export_capability_kW"][first - 1], "without": n["export_capability_kW"][first - 1]},
                "requested_point": e["requested_point"][first - 1], "delivered_point": e["delivered_point"][first - 1]},
            "requested_slots_after_first": window(after) if after else None,
            "morning_window": window([t for t in after if t <= 26]) if after else None,
            "afternoon_window": window([t for t in after if t > 26]) if after else None,
            "FOR_excludes_idle_on_export_side": {
                "slots": neg, "times": f"{clock(neg[0])}-{clock(neg[-1])}" if neg else None,
                "max_required_charging_kW": r1(e["dP_min"][tmax - 1]) if neg else 0.0,
                "at": clock(tmax) if neg else None},
            "stored_energy_change_kWh": {("d1 " if t <= 48 else "d2 ") + clock(t): d_e[t - 1] for t in (41, 49, 61, 67, 73, 77)},
            "soc_identical_from": None if t_id is None else {"slot": t_id, "time": ("d2 " if t_id > 48 else "d1 ") + clock(t_id)},
            "FOR_identical_from": None if not same_d2 else {"slot": same_d2[0], "time": "d2 " + clock(same_d2[0])},
            "max_per_prosumer_soc_gap_pp": r1(100 * diff.max(), 1),
            "import_bound_change_day2_kW": {("d2 " + clock(t)): d_bi[t - 1] for t in (49, 61, 63, 67, 73)},
        }
        comp[k] = {"export_capability_change_kW": d_exp, "import_capability_change_kW": d_imp,
                   "area_pct_of_no_request": d_area, "soc_mean_change_pct": d_soc,
                   "stored_energy_change_kWh": d_e, "soc_bound_import_change_kW": d_bi,
                   "soc_bound_export_change_kW": d_be, "key_numbers": key}

    # SOC-bound check against computed FORs (how well the BESS-only bounds track the FOR)
    chk = {}
    for k, c in out_cases.items():
        s = c["series"]
        idx = [i for i in range(N_SLOTS) if s["for_source"][i] == "computed"]
        if idx:
            chk[k] = {
                "import_side_max_abs_err_kW": r1(max(abs(s["import_capability_kW"][i] - s["soc_bound_import_kW"][i]) for i in idx)),
                "export_side_bound_minus_FOR_kW": {"min": r1(min(s["soc_bound_export_kW"][i] - s["export_capability_kW"][i] for i in idx)),
                                                   "max": r1(max(s["soc_bound_export_kW"][i] - s["export_capability_kW"][i] for i in idx))},
                "n_slots": len(idx)}

    # representative polygons
    polys = []
    for k, P in polys_all.items():
        for day in (1, 2):
            for hhmm in REP_TIMES[day]:
                h, mi = map(int, hhmm.split(":"))
                t = (h * 60 + mi) // 30 + 1 + 48 * (day - 1)
                s = out_cases[k]["series"]
                rec = {"case": k, "slot": t, "day": day, "time": hhmm, "requested": s["requested"][t - 1]}
                if t in P:
                    g, src = P[t]
                    rec.update(source=src, angles_deg=[int(x) for x in g.angle_deg],
                               points=[[r1(x), r1(y)] for x, y in zip(g.dP, g.dQ)],
                               area=r1(area(g.dP, g.dQ), 0))
                else:
                    rec.update(source=None, angles_deg=None, points=None, area=None,
                               reason="F_{k+1} not built for this slot in this run (see meta.availability)")
                rec.update(operating_point=s["operating_point"][t - 1], p1_baseline_point=s["p1_baseline_point"][t - 1],
                           requested_point=s["requested_point"][t - 1], delivered_point=s["delivered_point"][t - 1],
                           soc_mean_pct=s["soc_mean_pct"][t - 1])
                polys.append(rec)

    slots = [{"slot": t, "day": 1 if t <= 48 else 2, "time": clock(t), "label": f"{'d1' if t <= 48 else 'd2'} {clock(t)}",
              "idle_exchange_kW": r1(B.loc[t, "BP"]), "idle_exchange_kvar": r1(B.loc[t, "BQ"])} for t in range(1, N_SLOTS + 1)]
    meta = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "network": "TR4 LV network, 46 PV-BESS prosumers in 3 aggregators; aggregate converter rating 165.6 kW / 165.6 kVA",
        "coordinates": "deviation (dP, dQ) from the interface exchange with all BESS idle; kW / kvar; positive = import",
        "csv_content": "FOR_rolling<tag>.csv P,Q = absolute interface exchange in MW/Mvar (positive = import); converted here",
        "idle_reference": "B(t) = executed interface exchange of the no-request run minus the fleet BESS P (Pexec) and Q (Qinv1) of that slot",
        "idle_reference_check": {"same estimate from each export run vs no-request run": idle_check,
                                 "day 2 vs day 1 (no-request), max |dP| kW": r1((B.BP.values[48:] - B.BP.values[:48]).__abs__().max(), 2)},
        "slot_mapping": "rolling step k (CSV now) -> flexibility slot k+1 (CSV target) -> clock = start of slot = (slot-1)*30 min; "
                        "slots 1-48 day 1, 49-96 day 2 (day-2 now + 48); day-1 step 48 builds slot 49 (day 2 00:00)",
        "requested_slots_definition": "TSO export request every half-hour 06:00-20:00 of day 1 (flexibility slots 13-40, "
                                      "the FOR boundary point with the most export); none on day 2",
        "availability": "F_{k+1} is only built when the run needs it: no-request run at every step of day 1 (separate run, same "
                        "trajectory); export runs only at the requested slots 13-40 of day 1. Day-2 FORs exist only as "
                        "same-state copies (slots whose building step has the same per-prosumer SOC and frozen slot-1 plan as the "
                        "no-request step at the same clock time). soc_bound_* are given for every slot.",
        "fields": {
            "dP_min/dP_max/dQ_min/dQ_max": "range of F_{k+1} (kW, kvar)",
            "export_capability_kW": "-dP_min: largest extra export vs all-idle (negative = the FOR does not reach the idle point: "
                                    "the fleet must charge at least that much)",
            "import_capability_kW": "dP_max",
            "area": "area of conv{v_theta}, kW*kvar",
            "operating_point": "executed interface exchange of the slot, as deviation (P1 baseline when there is no request)",
            "p1_baseline_point": "P1-baseline point of the step (S0) at requested slots",
            "service_vs_p1_baseline": "requested point minus P1-baseline point [dP kW, dQ kvar]; dt * sum(max(0,-dP)) = export served",
            "requested_point": "point requested by the TSO", "delivered_point": "realised interface point at execution",
            "soc_mean_pct": "mean SOC of the 46 BESS at the start of the slot",
            "stored_energy_above_floor_kWh": "sum over BESS of (SOC - (1-DOD)) * E, at the start of the slot",
            "soc_bound_export_kW": "BESS-only bound sum min(P, (SOC-SOCmin) E eta / dt); ignores the self-consumption guarantee and network",
            "soc_bound_import_kW": "BESS-only bound sum min(P, (1-SOC) E / (eta dt)); tracks dP_max closely (see soc_bound_check)",
        },
        "soc_bound_check": chk,
        "battery_parameters": {"E_kWh": E_BAT, "P_kW": P_BAT, "eta": ETA, "SOC_min": SOC_MIN, "n": 46},
    }
    res = {"meta": meta, "slots": slots, "cases": out_cases, "comparison_vs_no_request": comp, "polygons": polys}
    (OUT / "for_time.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")

    rows = []
    for k, c in out_cases.items():
        s = c["series"]
        for i in range(N_SLOTS):
            rows.append({"case": k, "slot": i + 1, "day": 1 if i < 48 else 2, "time": clock(i + 1), "requested": int(s["requested"][i]),
                         "for_source": "" if s["for_source"][i] is None else ("computed" if s["for_source"][i] == "computed" else "same-state"),
                         **{f: s[f][i] for f in ("dP_min", "dP_max", "dQ_min", "dQ_max", "area", "export_capability_kW",
                                                  "import_capability_kW", "soc_mean_pct", "stored_energy_above_floor_kWh",
                                                  "soc_bound_export_kW", "soc_bound_import_kW")},
                         "op_dP": s["operating_point"][i][0], "op_dQ": s["operating_point"][i][1],
                         "req_dP": None if s["requested_point"][i] is None else s["requested_point"][i][0],
                         "req_dQ": None if s["requested_point"][i] is None else s["requested_point"][i][1],
                         "del_dP": None if s["delivered_point"][i] is None else s["delivered_point"][i][0],
                         "del_dQ": None if s["delivered_point"][i] is None else s["delivered_point"][i][1],
                         "service_dP_vs_p1": None if s["service_vs_p1_baseline"][i] is None else s["service_vs_p1_baseline"][i][0]})
    pd.DataFrame(rows).to_csv(OUT / "for_time.csv", index=False)
    print("written", OUT / "for_time.json", OUT / "for_time.csv")
    print(json.dumps({k: v["key_numbers"] for k, v in comp.items()}, indent=1))
    print(json.dumps(chk, indent=1))
    print(json.dumps(meta["idle_reference_check"], indent=1))


if __name__ == "__main__":
    main()
