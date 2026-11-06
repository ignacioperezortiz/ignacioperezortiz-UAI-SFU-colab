"""Chart data for the "with vs without TSO service" slides (R7, R8, R9 of the Tulio deck).

Writes service_requests.json (the deck's data_tulio\\service.json) into <out>/data, and checks it against for_time.json,
guarantee.json and service_T5.json there (run build.py, build_for_time.py and guarantee_metrics.py first).
Read-only on the run lanes.

Runs (two days; TSO export requests on day 1 at every flexibility slot 13-40 = 06:00-19:30 start; none on day 2):
  no_request                N2 _REF_free_today_a2x4p8fin2_TR4_FairBox1 (trajectory, SOC) and its FOR at every day-1
                            step from the one-day run N2 _REF_SWEEP_free_today_a2x4p8fin_TR4_FairBox1 (the executed
                            day-1 trajectory of both runs is checked to be identical, as in data/build_for_time.py)
  export_guarantee_on       N3 _WC_EXPORT..._FairBox1_RollOfferLog1_SCAlpha0   (no fairness, current commit)
  export_guarantee_relaxed  N3 _WC_EXPORT..._FairBox1_RollOfferLog1_SCAlpha99  (no fairness, current commit)
  hp_energy_floor           N2 _WC_EXPORT..._FairCrit2_FairScope1_FairEffHead1 (HP intra-aggregator, energy floor)
  hp_old_floor              N2 _WC_EXPORT..._FairCrit2_FairScope1              (HP intra-aggregator, (1-DOD)E floor)
  no_fairness_older         N2 _WC_EXPORT..._FairBox1                          (no fairness, older commit 866c053)

Conventions (same as data/build_for_time.py and data/guarantee_metrics.py):
  * FOR_rolling<tag>.csv P, Q = absolute interface exchange, MW / Mvar, + import. Converted to deviation (dP, dQ) in
    kW / kvar from the all-idle exchange B(t) = P_PCC1 - sum Pexec (Q_PCC1 - sum Qinv1) of the executed slot t of the
    no-request run. One B(t) for all cases (it depends on load/PV, not on the case).
  * step k (CSV now) builds F_{k+1} for flexibility slot k+1 (CSV target); time label = start of the slot.
  * export served = dt * sum over requested slots of max(0, -(req_P - S0_P)) (FRQ dP_kW), measured from the P1-baseline
    point S0 of the same step.
  * extra import = per prosumer, SCT_exec imp1_kWh of the run minus that of the no-request run WITH THE SAME SETTINGS,
    both days, split by the run's svc flag (inside = the requested half-hours).

Usage: python -B build_service.py [--runs DIR] [--out DIR]
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))     # package root: paths.py
import paths  # noqa: E402

RUNS = None                                   # folder of the lanes (--runs), set below __main__
DATA = None                                   # <out>/data, set below __main__
D2 = "_free_today_a2x4p8fin2_TR4"
DT = 0.5
OK = ("Optimal", "LocallyOptimal")
SLOTS = list(range(13, 41))
SAME_TOL = 1e-6

NOREQ = ("N2", "_REF" + D2 + "_FairBox1")
NOREQ_FOR = ("N2", "_REF_SWEEP_free_today_a2x4p8fin_TR4_FairBox1")
CASES = {
    # key: (lane, tag, no-request run with the same settings, label, note)
    "export_guarantee_on": ("N3", "_WC_EXPORT" + D2 + "_FairBox1_RollOfferLog1_SCAlpha0", NOREQ,
                            "TSO export requests, self-consumption guarantee (no fairness criterion)",
                            "current commit 2f68674 + N3 diagnostic patch (scenario.txt sets SCAlpha)"),
    "export_guarantee_relaxed": ("N3", "_WC_EXPORT" + D2 + "_FairBox1_RollOfferLog1_SCAlpha99", NOREQ,
                                 "TSO export requests, guarantee relaxed (no fairness criterion)",
                                 "same commit; SCAlpha = 99"),
    "hp_energy_floor": ("N2", "_WC_EXPORT" + D2 + "_FairCrit2_FairScope1_FairEffHead1",
                        ("N2", "_REF" + D2 + "_FairCrit2_FairScope1_FairEffHead1"),
                        "TSO export requests, guarantee on, HP intra-aggregator, energy floor", "commit 2f68674"),
    "hp_old_floor": ("N2", "_WC_EXPORT" + D2 + "_FairCrit2_FairScope1",
                     ("N2", "_REF" + D2 + "_FairCrit2_FairScope1"),
                     "TSO export requests, guarantee on, HP intra-aggregator, previous floor (1-DOD)E", "commit 866c053"),
    "no_fairness_older": ("N2", "_WC_EXPORT" + D2 + "_FairBox1", NOREQ,
                          "TSO export requests, guarantee on, no fairness criterion (older commit)", "commit 866c053"),
}


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
    if b is None:
        return a
    b = b.copy()
    b["now"] = b["now"] + 48
    return pd.concat([a, b], ignore_index=True)


def r(x, n=1):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), n)


def area(P, Q):
    P, Q = np.asarray(P, float), np.asarray(Q, float)
    return 0.5 * abs(np.dot(P, np.roll(Q, -1)) - np.dot(Q, np.roll(P, -1)))


def idle_reference():
    s = two(*NOREQ, "FOR_rolling_soc")
    g = s.groupby("now").agg(P=("P_PCC1", "first"), Q=("Q_PCC1", "first"), sb=("Pexec", "sum"), sq=("Qinv1", "sum"))
    return pd.DataFrame({"BP": 1000 * (g.P - g.sb), "BQ": 1000 * (g.Q - g.sq)}), s


def idle_check(lane, tag, B):
    s = two(lane, tag, "FOR_rolling_soc")
    g = s.groupby("now").agg(P=("P_PCC1", "first"), Q=("Q_PCC1", "first"), sb=("Pexec", "sum"), sq=("Qinv1", "sum"))
    bp = (1000 * (g.P - g.sb) - B.BP).abs().max()
    bq = (1000 * (g.Q - g.sq) - B.BQ).abs().max()
    return {"max_abs_dP_kW": r(bp, 2), "max_abs_dQ_kvar": r(bq, 2)}


def polygons(lane, tag, B):
    f = read(RUNS / lane / f"FOR_rolling{tag}.csv")
    out = {}
    f["slot"] = np.where(f["target"] < f["now"], f["target"] + 48, f["target"])
    for slot, g in f.groupby("slot"):
        slot = int(slot)
        if slot not in SLOTS:
            continue
        g = g.sort_values("angle_deg")
        if len(g) != 12:
            raise SystemExit(f"{tag}: slot {slot} has {len(g)} directions")
        bad = int((~g["status"].isin(OK)).sum())
        dP = 1000 * g["P"].values - B.loc[slot, "BP"]
        dQ = 1000 * g["Q"].values - B.loc[slot, "BQ"]
        out[slot] = {"dP": dP, "dQ": dQ, "angles": [int(a) for a in g["angle_deg"]], "non_optimal": bad,
                     "built_at_step": int(g["now"].iloc[0])}
    return out


def soc_mean_day1(lane, tag):
    s = read(RUNS / lane / f"FOR_rolling_soc{tag}.csv")
    m = s.groupby("now")["SOC_start"].mean()
    return [r(100 * m.loc[t], 2) for t in range(1, 49)], s


def import_metrics(lane, tag, ref):
    ex, rf = two(lane, tag, "SCT_exec"), two(*ref, "SCT_exec")
    m = ex.merge(rf[["now", "battery", "imp1_kWh"]], on=["now", "battery"], suffixes=("", "_ref"), validate="one_to_one")
    if len(m) != len(ex) or len(m) != len(rf):
        raise SystemExit(f"SCT_exec rows do not match for {tag}")
    m["dimp"] = m["imp1_kWh"] - m["imp1_kWh_ref"]
    bats = sorted(m["battery"].unique())
    w = m[m["svc"] == 1].groupby("battery")["dimp"].sum().reindex(bats).fillna(0.0)
    o = m[m["svc"] != 1].groupby("battery")["dimp"].sum().reindex(bats).fillna(0.0)

    def block(s):
        return {"prosumers_above_1Wh": int((s > 1e-3).sum()), "prosumers_above_10Wh": int((s > 1e-2).sum()),
                "fleet_total_kWh": r(s.sum(), 3), "worst_kWh": r(s.max(), 4), "worst_Wh": r(1000 * s.max(), 2), "worst_prosumer": str(s.idxmax()),
                "n_prosumers": len(s)}
    req = sorted(int(x) for x in m.loc[m["svc"] == 1, "now"].unique())
    return {"no_request_run": f"{ref[0]}/{ref[1]}", "inside_requested_halfhours": block(w),
            "outside_requested_halfhours": block(o)}, req


def main():
    for lane, tag in [NOREQ, NOREQ_FOR] + [(c[0], c[1]) for c in CASES.values()] + [c[2] for c in CASES.values()]:
        if not done(lane, tag):
            raise SystemExit(f"run {lane}/{tag} not finished")

    B, ref_soc = idle_reference()

    # the one-day FOR-at-every-step run must follow the same day-1 trajectory as the two-day no-request run
    sw = read(RUNS / NOREQ_FOR[0] / f"FOR_rolling_soc{NOREQ_FOR[1]}.csv")
    mm = ref_soc[ref_soc["now"] <= 48].merge(sw, on=["now", "battery"], suffixes=("", "_sw"))
    traj_diff = float(max((mm.SOC_start - mm.SOC_start_sw).abs().max(), (mm.Pexec - mm.Pexec_sw).abs().max(),
                          (mm.P_PCC1 - mm.P_PCC1_sw).abs().max()))
    if traj_diff > SAME_TOL or len(mm) != 48 * 46:
        raise SystemExit(f"one-day run differs from the two-day no-request run on day 1 ({traj_diff})")

    out_cases = {}
    polys_all = {}
    socs = {}

    # ---- no request
    P0 = polygons(*NOREQ_FOR, B)
    soc0, s0 = soc_mean_day1(*NOREQ)
    socs["no_request"] = s0
    polys_all["no_request"] = P0
    out_cases["no_request"] = {
        "label": "No TSO request (P1 baselines only), no fairness criterion",
        "trajectory_run": f"{NOREQ[0]}/{NOREQ[1]}", "for_run": f"{NOREQ_FOR[0]}/{NOREQ_FOR[1]}",
        "for_run_check": f"executed day-1 trajectory identical to the two-day no-request run (max |diff| {traj_diff:.1e} "
                         "over SOC_start, Pexec, P_PCC1; 48 x 46 rows)",
    }

    # ---- export runs
    meta_idle = {}
    for key, (lane, tag, ref, label, note) in CASES.items():
        P = polygons(lane, tag, B)
        if sorted(P) != SLOTS:
            raise SystemExit(f"{key}: FOR slots {sorted(P)}")
        polys_all[key] = P
        soc, s = soc_mean_day1(lane, tag)
        socs[key] = s
        fq = read(RUNS / lane / f"FRQ{tag}.csv")
        frq = {int(x.target): x for x in fq.itertuples()}
        sv = read(RUNS / lane / f"FOR_rolling_svc{tag}.csv")
        exe = {int(x.target): x for x in sv[sv["event"] == "execute"].itertuples()}
        imp, req_slots = import_metrics(lane, tag, ref)
        if req_slots != SLOTS:
            raise SystemExit(f"{key}: requested slots {req_slots}")
        served = DT * float((-fq["dP_kW"]).clip(lower=0).sum())
        meta_idle[key] = idle_check(lane, tag, B)
        reqp, delp, s0p, svc = [], [], [], []
        for t in SLOTS:
            f = frq[t]
            reqp.append([r(f.req_P_kW - B.loc[t, "BP"]), r(f.req_Q_kvar - B.loc[t, "BQ"])])
            s0p.append([r(f.S0_P_kW - B.loc[t, "BP"]), r(f.S0_Q_kvar - B.loc[t, "BQ"])])
            svc.append([r(f.dP_kW, 2), r(f.dQ_kvar, 2)])
            e = exe.get(t)
            delp.append(None if e is None else [r(1000 * e.real_P - B.loc[t, "BP"]), r(1000 * e.real_Q - B.loc[t, "BQ"])])
        dev = max(abs(a[0] - b[0]) for a, b in zip(reqp, delp) if b is not None)
        # pre-request trajectory equals that run's own no-request run
        rs = two(*ref, "FOR_rolling_soc")
        pre = s[s["now"] < SLOTS[0]].set_index(["now", "battery"])["SOC_start"]
        pre_ref = rs[rs["now"] < SLOTS[0]].set_index(["now", "battery"])["SOC_start"].reindex(pre.index)
        out_cases[key] = {
            "label": label, "lane": lane, "tag": tag, "note": note,
            "requests": len(fq), "requests_executed": len(exe),
            "export_served_kWh": r(served, 1),
            "export_served_definition": "dt * sum over requested slots of max(0, -(requested P - P1-baseline P of the same step))",
            "extra_import": imp,
            "requested_point": reqp, "delivered_point": delp, "p1_baseline_point": s0p,
            "service_vs_p1_baseline": svc,
            "max_abs_requested_minus_delivered_dP_kW": r(dev, 3),
            "pre_request_max_soc_gap_vs_own_no_request": float((pre - pre_ref).abs().max()),
            "soc_mean_pct_day1": soc,
        }
    out_cases["no_request"]["soc_mean_pct_day1"] = soc0

    # ---- per-slot geometry for every case
    for key, P in polys_all.items():
        c = out_cases[key]
        c["polygons"] = [[[r(x), r(y)] for x, y in zip(P[t]["dP"], P[t]["dQ"])] for t in SLOTS]
        c["area"] = [r(area(P[t]["dP"], P[t]["dQ"]), 0) for t in SLOTS]
        c["dP_min"] = [r(P[t]["dP"].min()) for t in SLOTS]
        c["dP_max"] = [r(P[t]["dP"].max()) for t in SLOTS]
        c["dQ_min"] = [r(P[t]["dQ"].min()) for t in SLOTS]
        c["dQ_max"] = [r(P[t]["dQ"].max()) for t in SLOTS]
        c["export_capability_kW"] = [r(-P[t]["dP"].min()) for t in SLOTS]
        c["import_capability_kW"] = [r(P[t]["dP"].max()) for t in SLOTS]
        c["non_optimal_solves"] = sum(P[t]["non_optimal"] for t in SLOTS)
        c["built_at_step"] = [P[t]["built_at_step"] for t in SLOTS]

    # ---- area ratios (unrounded areas)
    A = {k: np.array([area(P[t]["dP"], P[t]["dQ"]) for t in SLOTS]) for k, P in polys_all.items()}
    times = [clock(t) for t in SLOTS]

    def ratio(num, den):
        x = 100 * A[num] / A[den]
        i, j = int(np.argmin(x)), int(np.argmax(x))
        return {"numerator": num, "denominator": den, "pct": [r(v, 2) for v in x],
                "mean_pct": r(x.mean(), 2), "min_pct": r(x[i], 2), "min_at": times[i],
                "min_areas_kWkvar": [r(A[num][i], 0), r(A[den][i], 0)],
                "max_pct": r(x[j], 2), "max_at": times[j],
                "volume_ratio_pct": r(100 * A[num].sum() / A[den].sum(), 2),
                "slots_at_or_above_99pct": int((x >= 99).sum())}

    ratios = {
        "hp_energy_floor_vs_export_guarantee_on": ratio("hp_energy_floor", "export_guarantee_on"),
        "hp_energy_floor_vs_no_fairness_older": ratio("hp_energy_floor", "no_fairness_older"),
        "hp_old_floor_vs_export_guarantee_on": ratio("hp_old_floor", "export_guarantee_on"),
        "hp_old_floor_vs_no_fairness_older": ratio("hp_old_floor", "no_fairness_older"),
        "export_guarantee_on_vs_no_request": ratio("export_guarantee_on", "no_request"),
        "export_guarantee_relaxed_vs_no_request": ratio("export_guarantee_relaxed", "no_request"),
        "no_fairness_older_vs_export_guarantee_on": ratio("no_fairness_older", "export_guarantee_on"),
    }

    # ---- same-state check for the area ratios: SOC gap of each HP run vs the no-fairness run at each step
    def soc_gap(a, b):
        pa = socs[a].pivot(index="now", columns="battery", values="SOC_start")
        pb = socs[b].pivot(index="now", columns="battery", values="SOC_start")
        g = (pa - pb).abs().loc[SLOTS[0] - 1:SLOTS[-1] - 1]          # state at the step that builds slot t
        mg = (pa.mean(axis=1) - pb.mean(axis=1)).abs().loc[SLOTS[0] - 1:SLOTS[-1] - 1]
        return {"max_per_prosumer_soc_gap_pp": r(100 * g.values.max(), 2), "max_fleet_mean_soc_gap_pp": r(100 * mg.max(), 2)}
    # SOC at the START of each requested slot t (now = t): difference vs a reference case, over slots 13-40
    def soc_diff(a, b):
        pa_all = socs[a].pivot(index="now", columns="battery", values="SOC_start")
        pb_all = socs[b].pivot(index="now", columns="battery", values="SOC_start")
        out = {"definition": f"mean SOC of the 46 BESS at the start of each slot, {a} minus {b} (pp); single BESS = max "
                             "over the 46 of |SOC_a - SOC_b|. Window 'requested' = slots 13-40 (06:00-19:30, the slots "
                             "whose FORs are compared); 'building_steps' = steps 12-39 that build them; 'day1' = slots 1-48."}
        for win, idx in (("requested", SLOTS), ("building_steps", [t - 1 for t in SLOTS]), ("day1", list(range(1, 49)))):
            pa, pb = pa_all.loc[idx], pb_all.loc[idx]
            fm = 100 * (pa.mean(axis=1) - pb.mean(axis=1))
            pp = 100 * (pa - pb).abs().max(axis=1)
            i, j = int(np.argmax(fm.abs().values)), int(np.argmax(pp.values))
            out[win] = {"fleet_mean_abs_diff_mean_pp": r(fm.abs().mean(), 3),
                        "fleet_mean_abs_diff_max_pp": r(fm.abs().max(), 3), "fleet_mean_abs_diff_max_at": clock(idx[i]),
                        "single_bess_abs_diff_max_pp": r(pp.max(), 2), "single_bess_abs_diff_max_at": clock(idx[j]),
                        "single_bess_abs_diff_mean_pp": r(pp.mean(), 3)}
            if win == "requested":
                out[win]["fleet_mean_soc_diff_pp_per_slot"] = [r(v, 3) for v in fm.values]
        return out
    soc_vs_no_fairness = {"hp_energy_floor_vs_export_guarantee_on": soc_diff("hp_energy_floor", "export_guarantee_on"),
                          "hp_old_floor_vs_export_guarantee_on": soc_diff("hp_old_floor", "export_guarantee_on"),
                          "hp_energy_floor_vs_no_fairness_older": soc_diff("hp_energy_floor", "no_fairness_older"),
                          "hp_old_floor_vs_no_fairness_older": soc_diff("hp_old_floor", "no_fairness_older")}

    # stored energy above the DOD floor at given slots (start of slot), vs the no-request run
    E_BAT, SOC_MIN = 4.2, 0.1

    def e_up(key, t):
        s = socs[key] if key != "no_request" else ref_soc
        if t > 48:
            s = two(*((NOREQ) if key == "no_request" else (CASES[key][0], CASES[key][1])), "FOR_rolling_soc")
        x = s.loc[s["now"] == t, "SOC_start"]
        return float(((x - SOC_MIN).clip(lower=0) * E_BAT).sum())
    stored = {}
    for key in ("export_guarantee_on", "export_guarantee_relaxed", "hp_energy_floor", "hp_old_floor", "no_fairness_older"):
        stored[key] = {f"d1 {clock(t)}" if t <= 48 else f"d2 {clock(t)}":
                       {"case_kWh": r(e_up(key, t)), "no_request_kWh": r(e_up("no_request", t)),
                        "change_kWh": r(e_up(key, t) - e_up("no_request", t))} for t in (41, 48, 49)}

    state = {"hp_energy_floor_vs_export_guarantee_on": soc_gap("hp_energy_floor", "export_guarantee_on"),
             "hp_old_floor_vs_export_guarantee_on": soc_gap("hp_old_floor", "export_guarantee_on"),
             "no_fairness_older_vs_export_guarantee_on": soc_gap("no_fairness_older", "export_guarantee_on"),
             "hp_energy_floor_vs_no_fairness_older": soc_gap("hp_energy_floor", "no_fairness_older")}

    # ---- aggregate FOR agreement N3 vs N2 no-fairness runs
    dmax = max(float(np.abs(polys_all["export_guarantee_on"][t]["dP"] - polys_all["no_fairness_older"][t]["dP"]).max()) for t in SLOTS)
    qmax = max(float(np.abs(polys_all["export_guarantee_on"][t]["dQ"] - polys_all["no_fairness_older"][t]["dQ"]).max()) for t in SLOTS)

    # ---- validation against data/
    val = []

    def add(item, expected, got, tol):
        ok = expected is not None and got is not None and abs(float(expected) - float(got)) <= tol
        val.append({"item": item, "expected": expected, "reproduced": got, "ok": bool(ok)})

    ft = json.loads((DATA / "for_time.json").read_text(encoding="utf-8"))
    gj = json.loads((DATA / "guarantee.json").read_text(encoding="utf-8"))
    sj = json.loads((DATA / "service_T5.json").read_text(encoding="utf-8"))
    i1230, i1630 = SLOTS.index(26), SLOTS.index(34)
    on, nr, rl = out_cases["export_guarantee_on"], out_cases["no_request"], out_cases["export_guarantee_relaxed"]
    add("12:30 dP_min, guarantee on (kW)", -0.9, on["dP_min"][i1230], 0.05)
    add("12:30 dP_max, guarantee on (kW)", 161.3, on["dP_max"][i1230], 0.05)
    add("12:30 dP_min, no request (kW)", -154.2, nr["dP_min"][i1230], 0.05)
    add("12:30 dP_max, no request (kW)", 4.9, nr["dP_max"][i1230], 0.05)
    add("16:30 most-export point needs charging, guarantee on (dP_min, kW)", 34.9, on["dP_min"][i1630], 0.05)
    # every slot vs for_time.json series
    for key, fk in (("no_request", "no_request"), ("export_guarantee_on", "export_guarantee_on"),
                    ("export_guarantee_relaxed", "export_guarantee_relaxed")):
        fs = ft["cases"][fk]["series"]
        for fld in ("dP_min", "dP_max", "dQ_min", "dQ_max"):
            d = max(abs(out_cases[key][fld][i] - fs[fld][t - 1]) for i, t in enumerate(SLOTS))
            add(f"max |{fld} - for_time.json| over slots 13-40, {key}", 0.0, r(d, 2), 0.051)
        d = max(abs(out_cases[key]["area"][i] - fs["area"][t - 1]) for i, t in enumerate(SLOTS))
        add(f"max |area - for_time.json| over slots 13-40, {key} (kW*kvar)", 0.0, r(d, 0), 1.0)
        d = max(abs(out_cases[key]["soc_mean_pct_day1"][t - 1] - fs["soc_mean_pct"][t - 1]) for t in range(1, 49))
        add(f"max |mean SOC - for_time.json| day 1, {key} (pp)", 0.0, r(d, 3), 0.006)
    for key in ("export_guarantee_on", "export_guarantee_relaxed"):
        fs = ft["cases"][key]["series"]
        d = max(abs(out_cases[key]["requested_point"][i][0] - fs["requested_point"][t - 1][0]) for i, t in enumerate(SLOTS))
        add(f"max |requested dP - for_time.json|, {key} (kW)", 0.0, r(d, 2), 0.051)
    add("export served, guarantee on (kWh) [guarantee.json]", gj["guarantee_on"]["export_served_kWh"], on["export_served_kWh"], 0.05)
    add("export served, guarantee relaxed (kWh) [guarantee.json]", gj["guarantee_relaxed"]["export_served_kWh"], rl["export_served_kWh"], 0.05)
    for key, sid in (("no_fairness_older", "no_fairness"), ("hp_old_floor", "HP_old_floor"), ("hp_energy_floor", "HP_energy_floor")):
        sm = sj["summary"][sid]
        add(f"export served, {key} (kWh) [data/service.json]", sm["export_served_kWh"], out_cases[key]["export_served_kWh"], 0.05)
        add(f"prosumers > 1 Wh more inside, {key} [data/service.json]", sm["prosumers_buying_more_inside"],
            out_cases[key]["extra_import"]["inside_requested_halfhours"]["prosumers_above_1Wh"], 0)
        add(f"prosumers > 10 Wh more inside, {key} [data/service.json]", sm["prosumers_buying_more_inside_by_10Wh"],
            out_cases[key]["extra_import"]["inside_requested_halfhours"]["prosumers_above_10Wh"], 0)
        add(f"worst prosumer outside, {key} (Wh) [data/service.json]", sm["worst_prosumer_outside_Wh"],
            out_cases[key]["extra_import"]["outside_requested_halfhours"]["worst_Wh"], 0.005)
    add("worst prosumer inside, hp_old_floor (kWh) [data/service.json]", sj["summary"]["HP_old_floor"]["worst_prosumer_inside_kWh"],
        r(out_cases["hp_old_floor"]["extra_import"]["inside_requested_halfhours"]["worst_kWh"], 3), 0.0005)
    for key, gk in (("export_guarantee_on", "guarantee_on"), ("export_guarantee_relaxed", "guarantee_relaxed")):
        for side, gside in (("inside_requested_halfhours", "extra_import_inside_requested"),
                            ("outside_requested_halfhours", "extra_import_outside_requested")):
            add(f"prosumers > 1 Wh more {side.split('_')[0]}, {key} [guarantee.json]", gj[gk][gside]["prosumers_above_1Wh"],
                out_cases[key]["extra_import"][side]["prosumers_above_1Wh"], 0)
    for key, gk in (("export_guarantee_on", "export_guarantee_on"), ("export_guarantee_relaxed", "export_guarantee_relaxed")):
        add(f"stored energy vs no request at d1 20:00, {key} (kWh) [for_time.json]",
            ft["comparison_vs_no_request"][gk]["stored_energy_change_kWh"][40], stored[key]["d1 20:00"]["change_kWh"], 0.05)
    add("coordinator: stored energy vs no request at 20:00, guarantee on (kWh)", -46.5, stored["export_guarantee_on"]["d1 20:00"]["change_kWh"], 0.05)
    add("coordinator: stored energy vs no request at 20:00, relaxed (kWh)", -150.6, stored["export_guarantee_relaxed"]["d1 20:00"]["change_kWh"], 0.05)
    sd = soc_vs_no_fairness["hp_energy_floor_vs_export_guarantee_on"]
    add("amendment 4: HP energy floor within 0.5 pp mean SOC, day 1 (max fleet-mean gap, pp)", 0.5, sd["day1"]["fleet_mean_abs_diff_max_pp"], 0.05)
    add("amendment 4: single BESS up to 19.6 pp, day 1", 19.6, sd["day1"]["single_bess_abs_diff_max_pp"], 0.05)
    add("amendment 4 restricted to requested slots 13-40: single BESS max (pp)", 19.6, sd["requested"]["single_bess_abs_diff_max_pp"], 0.05)
    # planners' claim
    rr =ratios["hp_energy_floor_vs_export_guarantee_on"]
    add("planners: HP energy floor / no fairness, mean area ratio (%)", 99.36, rr["mean_pct"], 0.005)
    add("planners: HP energy floor / no fairness, min area ratio (%) at 17:30", 97.8, rr["min_pct"], 0.05)
    add("planners: min at 17:30 -> HP area (kW*kvar)", 23044, rr["min_areas_kWkvar"][0], 1)
    add("planners: min at 17:30 -> no-fairness area (kW*kvar)", 23564, rr["min_areas_kWkvar"][1], 1)
    add("planners: HP energy floor ratio max (claim '97.8-100 %')", 100.0, rr["max_pct"], 0.05)
    ro = ratios["hp_old_floor_vs_export_guarantee_on"]
    add("planners (plan A): HP old floor / no fairness, mean (%)", 72.5, ro["mean_pct"], 0.05)
    add("planners (plan A): HP old floor / no fairness, min (%)", 26.0, ro["min_pct"], 0.05)

    # R8 cut hours
    cuts = {}
    for hhmm in ("07:30", "12:30", "16:30", "19:30"):
        i = times.index(hhmm)
        rec = {"slot": SLOTS[i], "index": i}
        for key in ("no_request", "export_guarantee_on", "export_guarantee_relaxed"):
            c = out_cases[key]
            rec[key] = {"polygon": c["polygons"][i], "area": c["area"][i],
                        "area_pct_of_no_request": r(100 * A[key][i] / A["no_request"][i], 1),
                        "dP_range": [c["dP_min"][i], c["dP_max"][i]], "dQ_range": [c["dQ_min"][i], c["dQ_max"][i]],
                        "soc_mean_pct": c["soc_mean_pct_day1"][SLOTS[i] - 1]}
            if key != "no_request":
                rec[key].update(requested_point=c["requested_point"][i], delivered_point=c["delivered_point"][i],
                                p1_baseline_point=c["p1_baseline_point"][i])
        cuts[hhmm] = rec

    res = {
        "meta": {
            "generated": datetime.now().isoformat(timespec="seconds"),
            "script": str(Path(__file__).name),
            "network": "TR4 LV network, 46 PV-BESS prosumers, 3 aggregators; aggregate converter rating 165.6 kW / 165.6 kVA",
            "scenario": "two days; TSO export request at every flexibility slot 13-40 of day 1 (start 06:00-19:30): the "
                        "boundary point of F_{k+1} with the most export (search direction 180 deg); no request on day 2",
            "coordinates": "deviation (dP, dQ) from the interface exchange with all BESS idle, kW / kvar, positive = import",
            "idle_reference": "B(t) = P_PCC1 - sum Pexec, Q_PCC1 - sum Qinv1 of executed slot t of the no-request run "
                              f"{NOREQ[0]}/{NOREQ[1]}; same B(t) for every case",
            "idle_reference_check_vs_each_run": meta_idle,
            "polygon_order": "12 boundary points v_theta ordered by search direction theta = 0, 30, ..., 330 deg",
            "slot_mapping": "polygon i is F_{k+1} for flexibility slot SLOTS[i], built at rolling step SLOTS[i]-1; "
                            "time label = start of the flexibility slot",
            "availability": "export runs build F_{k+1} only when a request is due (slots 13-40); no FOR after 19:30 in them",
            "no_fairness_runs_agreement": {"max_abs_dP_kW": r(dmax, 3), "max_abs_dQ_kvar": r(qmax, 3),
                                           "between": ["export_guarantee_on (N3, current commit)", "no_fairness_older (N2, 866c053)"]},
            "state_gap_at_building_steps": state,
            "area": "shoelace area of the 12-point polygon, kW*kvar (independent of the idle reference)",
        },
        "slots": SLOTS,
        "times": times,
        "cases": out_cases,
        "area_ratios": ratios,
        "soc_vs_no_fairness_export_run": soc_vs_no_fairness,
        "stored_energy_above_floor_vs_no_request": stored,
        "cuts": cuts,
        "validation": val,
    }
    (DATA / "service_requests.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")

    print("written", DATA / "service_requests.json")
    for v in val:
        print(("OK  " if v["ok"] else "FAIL"), v["item"], "| expected", v["expected"], "| got", v["reproduced"])
    for k, v in ratios.items():
        print(k, {kk: v[kk] for kk in ("mean_pct", "min_pct", "min_at", "min_areas_kWkvar", "max_pct", "max_at", "volume_ratio_pct", "slots_at_or_above_99pct")})
    print(json.dumps(state, indent=0))
    print("N3 vs N2 no-fairness FOR", dmax, qmax)
    for k, c in out_cases.items():
        if k == "no_request":
            continue
        print(k, c["export_served_kWh"], json.dumps(c["extra_import"]), c["max_abs_requested_minus_delivered_dP_kW"],
              c["pre_request_max_soc_gap_vs_own_no_request"], c["non_optimal_solves"])
    print(json.dumps(meta_idle))


if __name__ == "__main__":
    paths.cli(__doc__, runs=True)
    RUNS, DATA = paths.runs_dir(), paths.data_out()
    need = [f for f in ("for_time.json", "guarantee.json", "service_T5.json") if not (DATA / f).is_file()]
    if need:
        raise SystemExit(f"build_service.py checks its output against for_time.json, guarantee.json and service_T5.json "
                         f"of the same rebuild; missing in {DATA}: {', '.join(need)}. Run build.py, build_for_time.py "
                         "and guarantee_metrics.py with the same --out first (or make_all.py).")
    main()
