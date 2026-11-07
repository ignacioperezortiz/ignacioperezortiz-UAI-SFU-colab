"""Build chart-ready JSON (muf.json, fair.json, service_T5.json) for the fairness deck from lane N2.

Reuses analyze_fair.py (corners, area, read, info_lines), analyze_t7.py conventions (mixing, t5 service metrics)
and scripts/paper1/analyze_paper1.py (days, clock, read). Read-only on the lane; writes only into <out>/data.
Run:  python -B build.py [--runs DIR] [--out DIR]
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))     # package root: paths.py
import paths  # noqa: E402

paths.cli(__doc__, runs=True)                                     # before analyze_fair, which takes the lane from it
sys.path.append(str(paths.PAPER1))                                # scripts/paper1/analyze_paper1.py, after this folder
import analyze_fair as F  # noqa: E402
import analyze_paper1 as A  # noqa: E402

OUT = paths.data_out()
L, SW = F.LANE, F.SW                      # lane N2, "_REF_SWEEP_free_today_a2x4p8fin_TR4"
D2 = "_free_today_a2x4p8fin2_TR4"         # two-day service runs
E1 = "_FairEffHead1"
OK = F.OK
CYC_W = 1e-3                              # kW: a BESS counts as charging and discharging at once above 1 W (n_cyc in the log)
MIX = 1e-3                                # threshold on the HP factors for a mixed allocation
REF_TAG = SW + E1                         # reference FOR for the fairness ratios


def r(x, n=2):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return None
    return round(float(x), n)


def rl(a, n=2):
    return [r(v, n) for v in a]


# ------------------------------------------------------------------ common: steps, clock, all-idle exchange
ref = F.corners(REF_TAG)
steps = sorted(ref.now.unique())
target = ref.groupby("now").target.first()
TIME = [A.clock(int(target[n])) for n in steps]          # HH:MM of the start of flexibility slot k+1

soc = A.read(L / f"FOR_rolling_soc{REF_TAG}.csv")
g = soc.groupby("now").agg(P=("P_PCC1", "first"), Q=("Q_PCC1", "first"), sP=("Pexec", "sum"), sQ=("Qinv1", "sum"))
IDLE = {int(n): (1000 * (x.P - x.sP), 1000 * (x.Q - x.sQ)) for n, x in g.iterrows()}   # keyed by period = slot 1 of step n


def idle_for_step(now):
    return IDLE[int(target[now])]


def per_step_area(d):
    a = F.area(d)
    return a.reindex(steps)


def polygon(d, now):
    bp, bq = idle_for_step(now)
    x = d[(d.now == now)].sort_values("angle")
    assert len(x) == 12 and x.ok.all(), (now, len(x))
    return [[r(p - bp), r(q - bq)] for p, q in zip(x.P_kW, x.Q_kW)]


# cross-check of the all-idle exchange against the sweep itself (P - sum of BESS P, mean over the 12 directions)
fa = F.read(L / f"FOR_rolling_fair{REF_TAG}.csv")
sb = fa.groupby(["now", "angle_deg"]).sumP_pu.sum().mul(1000).rename("Pb").reset_index().rename(columns={"angle_deg": "angle"})
mm = ref.merge(sb, on=["now", "angle"])
chk = {}
for n, x in mm.groupby("now"):          # y = P_interface - sum P^b = P_idle + loss change; fit y = c0 + c1 x + c2 x^2, x = sum P^b
    y, xb = (x.P_kW - x.Pb).to_numpy(), x.Pb.to_numpy()
    chk[n] = np.linalg.lstsq(np.c_[np.ones(len(xb)), xb, xb ** 2], y, rcond=None)[0][0]
idle_chk_max = max(abs(chk[n] - idle_for_step(n)[0]) for n in steps)
q_mid = []
for n in steps:
    x = ref[ref.now == n].set_index("angle")
    q_mid.append(abs((x.loc[90, "Q_kW"] + x.loc[270, "Q_kW"]) / 2 - idle_for_step(n)[1]))
COORD = {
    "convention": "Deviation (ΔP, ΔQ) of the TSO–DSO interface exchange from the exchange with all BESS idle, "
                  "in the same flexibility slot k+1. Positive = import (ΔP in kW, ΔQ in kvar).",
    "idle_exchange_estimate": "P_idle(t) = P_PCC(t) − Σ_s P^b_s(t) and Q_idle(t) = Q_PCC(t) − Σ_s Q^b_s(t), taken from the "
                              "committed operation of the rolling step whose slot k is period t (Σ_s Q^b_s = 0 there). "
                              "It omits the change in network losses caused by the committed BESS power (|Σ P^b| ≤ 54 kW).",
    "idle_exchange_accuracy_kW": r(idle_chk_max, 2),
    "idle_exchange_accuracy_note": "Independent check from the 12 directional solves of the step before: fitting "
                                   "(P_interface − Σ_s P^b_s) as a quadratic in Σ_s P^b_s and taking the value at Σ_s P^b_s = 0 "
                                   "differs from P_idle by at most this value; ΔQ at 90° and 270° is symmetric about 0 within "
                                   f"{max(q_mid):.2f} kvar.",
    "absolute_from_deviation": "absolute interface exchange = deviation + idle_exchange (same step)",
}


# ------------------------------------------------------------------ 1) muf.json
MUF = [
    ("muf_0.2", "μ^f = 0.2", 0.2, True, "_FairBox1"),
    ("muf_0.1", "μ^f = 0.1", 0.1, True, "_P2SlotPen0.1"),
    ("muf_0", "μ^f = 0", 0.0, True, "_P2SlotPen0"),
    ("muf_0.2_nolimits", "μ^f = 0.2, without limits", 0.2, False, "_FairBox0"),
    ("muf_0_nolimits", "μ^f = 0, without limits", 0.0, False, "_FairBox0_P2SlotPen0"),
]
muf_ref = F.corners(SW + "_FairBox1")
muf_ref_area = per_step_area(muf_ref)
muf = {"title": "Role of μ^f and of the limits −D_s ≤ ΔP^b_s ≤ U_s on F_{k+1}",
       "network": "TR4, 46 PV–BESS prosumers, one day: 48 rolling steps × 12 directional solves = 576 directional solves of P2",
       "time_note": "time = HH:MM of the start of flexibility slot k+1",
       "definitions": {
           "simultaneous": "a BESS charges and discharges simultaneously in slot k+1 when min(P^ch_s, P^dis_s) > 1 W; "
                           "a directional solve counts when at least one BESS does",
           "simultaneous_kW": "Σ_s min(P^ch_s, P^dis_s) over the fleet in one directional solve, slot k+1",
           "throughput_kW": "Σ_s (P^ch_s + P^dis_s) over the fleet in slot k+1 (the term μ^f multiplies in the P2 objective)",
           "FOR_area": "area of F_{k+1} = conv of the 12 boundary points (shoelace), kW·kvar",
           "area_ratio": "area(case) / area(μ^f = 0.2 with limits), per step",
           "dP_0deg": "ΔP of the 0° boundary point (maximum import) minus the same point for μ^f = 0.2 with limits, kW",
       },
       "time": TIME, "cases": [], "per_step": {}, "summary": {}}
for cid, lab, mu, lim, suf in MUF:
    d = F.corners(SW + suf)
    s = d[d.ok]
    grp = s.groupby("now")
    a = per_step_area(d)
    ratio = a / muf_ref_area
    z = d[d.angle == 0].set_index("now").P_kW - muf_ref[muf_ref.angle == 0].set_index("now").P_kW
    exceed = (s.box_up > CYC_W) | (s.box_dn > CYC_W)
    muf["cases"].append({"id": cid, "label": lab + ("" if not lim else ", with limits"), "mu_f": mu, "limits": lim,
                         "source_tag": SW + suf})
    muf["per_step"][cid] = {
        "simultaneous_solves": [int(grp.apply(lambda x: (x.n_cyc > 0).sum())[n]) for n in steps],
        "simultaneous_kW_max": rl(grp.cyc_kW.max().reindex(steps)),
        "simultaneous_kW_sum": rl(grp.cyc_kW.sum().reindex(steps)),
        "throughput_kW_mean": rl(grp.thr_kW.mean().reindex(steps)),
        "throughput_kW_max": rl(grp.thr_kW.max().reindex(steps)),
        "FOR_area_kWkvar": rl(a, 0),
        "area_ratio": rl(ratio, 4),
        "dP_0deg_vs_ref_kW": rl(z.reindex(steps)),
    }
    muf["summary"][cid] = {
        "directional_solves": int(len(d)), "optimal": int(d.ok.sum()),
        "simultaneous_solves": int((s.n_cyc > 0).sum()),
        "simultaneous_kW_max": r(s.cyc_kW.max()),
        "simultaneous_kW_total": r(s.cyc_kW.sum(), 1),
        "throughput_kW_mean": r(s.thr_kW.mean()),
        "throughput_kW_max": r(s.thr_kW.max()),
        "FOR_area_mean_kWkvar": r(a.mean(), 0),
        "area_ratio_mean": r(ratio.mean(), 4), "area_ratio_max": r(ratio.max(), 4), "area_ratio_min": r(ratio.min(), 4),
        "area_ratio_max_time": TIME[steps.index(ratio.idxmax())],
        "dP_0deg_vs_ref_kW_mean": r(z.mean()), "dP_0deg_vs_ref_kW_max": r(z.max()),
        "solves_exceeding_limits_by_1W": int(exceed.sum()),
        "max_exceedance_per_BESS_kW": r(max(s.box_up.max(), s.box_dn.max()), 3),
    }
# the energy-floor reference against the μ^f = 0.2 reference used above (same FOR expected)
eref = F.corners(REF_TAG)
mm2 = eref.merge(muf_ref, on=["now", "angle"], suffixes=("", "_o"))
muf["note_reference"] = (f"μ^f = 0.2 with limits is run {SW}_FairBox1 (old floor in U_s, D_s, same commit as μ^f = 0.1 and 0). "
                         f"The energy-floor reference {REF_TAG} gives the same F_{{k+1}}: area ratio "
                         f"{(per_step_area(eref) / muf_ref_area).min():.4f}–{(per_step_area(eref) / muf_ref_area).max():.4f}, "
                         f"max per-point |ΔP| {(mm2.P_kW - mm2.P_kW_o).abs().max():.3f} kW, |ΔQ| {(mm2.Q_kW - mm2.Q_kW_o).abs().max():.3f} kvar, "
                         f"same throughput mean {eref[eref.ok].thr_kW.mean():.2f} kW and 0 simultaneous.")
(OUT / "muf.json").write_text(json.dumps(muf, ensure_ascii=False, indent=1), encoding="utf-8")


# ------------------------------------------------------------------ 2) fair.json
CRIT = {"CP": ("_FairCrit1", ""), "HP": ("_FairCrit2", ""), "HB": ("_FairCrit3", "_FairEps0.1")}
SCOPE = {"intra-aggregator": 1, "network-wide": 2}
FLOOR = {"energy floor": E1, "old floor": ""}
ref_area = per_step_area(ref)
old_ref_area = muf_ref_area
fair = {"title": "Cost of the fairness criteria: area of F_{k+1} relative to the FOR without fairness",
        "network": muf["network"],
        "reference": "F_{k+1} without fairness constraints (μ^f = 0.2, limits on, energy floor)",
        "reference_tag": REF_TAG,
        "floors": {"energy floor": "U_s, D_s measured to the energy floor (current method)",
                   "old floor": "U_s, D_s measured to the floor (1 − DOD_s)Ē_s (earlier version)"},
        "criteria": {"CP": "capacity-proportional", "HP": "headroom-proportional", "HB": "headroom band, ε = 0.1"},
        "time_note": muf["time_note"], "coordinates": COORD, "time": TIME,
        "reference_FOR_area_kWkvar": rl(ref_area, 0),
        "area_ratio": {}, "summary": {}, "sources": {}}
max_ref_diff = 0.0
for fl, fsuf in FLOOR.items():
    fair["area_ratio"][fl], fair["summary"][fl] = {}, {}
    for c, (cs, eps) in CRIT.items():
        fair["area_ratio"][fl][c], fair["summary"][fl][c] = {}, {}
        for sc, si in SCOPE.items():
            tag = SW + f"{cs}_FairScope{si}{eps}{fsuf}"
            d = F.corners(tag)
            assert d.ok.all() and len(d) == 576, tag
            a = per_step_area(d)
            ratio = a / ref_area
            max_ref_diff = max(max_ref_diff, float((ratio - a / old_ref_area).abs().max()))
            fair["area_ratio"][fl][c][sc] = rl(ratio, 4)
            fair["sources"][f"{c}, {sc}, {fl}"] = tag
            fair["summary"][fl][c][sc] = {
                "mean": r(ratio.mean(), 4), "min": r(ratio.min(), 4), "min_time": TIME[steps.index(ratio.idxmin())],
                "max": r(ratio.max(), 4), "max_time": TIME[steps.index(ratio.idxmax())],
                "times_below_1pct": [TIME[steps.index(n)] for n in steps if ratio[n] < 0.01],
            }
fair["note_ratio_reference"] = (f"Ratios use the energy-floor reference for both floors; against the old-floor reference "
                                f"({SW}_FairBox1) every per-step ratio changes by at most {max_ref_diff:.1e}.")
fair["note_ratio_above_1"] = ("A ratio can exceed 1 slightly (HB up to "
                              f"{max(fair['summary']['energy floor']['HB'][s]['max'] for s in SCOPE):.4f}, above 1.0005 at 18:00–22:00). It does not "
                              "mean a larger region: F_{k+1} is the hull of 12 boundary points, which can slide along flat faces, and "
                              "each point maximises the projection minus μ^f × throughput. HB reaches up to 0.25 kW farther in "
                              "projection with more throughput, while its objective never exceeds the reference's by more than 1 W.")

# ΔP range of F_{k+1} per step (deviation from the all-idle exchange)
rng = {}
for lab, tag in (("reference", REF_TAG), ("HB", SW + "_FairCrit3_FairScope1_FairEps0.1" + E1),
                 ("HP", SW + "_FairCrit2_FairScope1" + E1), ("CP", SW + "_FairCrit1_FairScope1" + E1)):
    d = F.corners(tag)
    bp = pd.Series({n: idle_for_step(n)[0] for n in steps})
    dp = d.assign(dP=d.P_kW - d.now.map(bp)).groupby("now").dP
    rng[lab] = {"dP_max_kW": rl(dp.max().reindex(steps)), "dP_min_kW": rl(dp.min().reindex(steps))}
fair["dP_range_intra_energy_floor"] = rng
fair["idle_exchange_per_step"] = {"P_kW": rl([idle_for_step(n)[0] for n in steps]),
                                  "Q_kvar": rl([idle_for_step(n)[1] for n in steps])}

# polygons
POLY_TIMES = {"07:30": "morning: CP already shrinks F_{k+1} to 40 %, HP and HB close to the reference",
              "12:30": "midday, BESS full (no import side): lowest HP ratio of the day, all criteria visible on the export side",
              "18:00": "late afternoon: CP collapses to a vertical segment (only ΔQ left); HP with the old floor keeps ~20 %"}
PTAGS = {"reference": REF_TAG, "HB": SW + "_FairCrit3_FairScope1_FairEps0.1" + E1, "HP": SW + "_FairCrit2_FairScope1" + E1,
         "CP": SW + "_FairCrit1_FairScope1" + E1, "HP, old floor": SW + "_FairCrit2_FairScope1"}
PD = {k: F.corners(v) for k, v in PTAGS.items()}
polys = []
for tm, why in POLY_TIMES.items():
    now = steps[TIME.index(tm)]
    bp, bq = idle_for_step(now)
    item = {"time": tm, "step": int(now), "why": why, "idle_exchange": {"P_kW": r(bp), "Q_kvar": r(bq)},
            "area_kWkvar": {}, "area_ratio": {}, "FOR": {}}
    for k, d in PD.items():
        item["FOR"][k] = polygon(d, now)
        a = per_step_area(d)[now]
        item["area_kWkvar"][k] = r(a, 0)
        item["area_ratio"][k] = r(a / ref_area[now], 4)
    polys.append(item)
fair["polygons"] = {"scope": "intra-aggregator", "angles_deg": list(range(0, 360, 30)),
                    "note": "12 boundary points per FOR, ordered by search direction θ = 0°, 30°, …, 330° "
                            "(0° = +ΔP, 90° = +ΔQ); consecutive points can coincide. Each list is [ΔP kW, ΔQ kvar]. "
                            "'HP, old floor' is included for comparison (not part of the requested set).",
                    "sources": PTAGS, "steps": polys}
(OUT / "fair.json").write_text(json.dumps(fair, ensure_ascii=False, indent=1), encoding="utf-8")


# ------------------------------------------------------------------ 3) service.json
SVC = [("no_fairness", "No fairness", "_FairBox1"),
       ("HP_old_floor", "HP, intra-aggregator, old floor (1 − DOD_s)Ē_s", "_FairCrit2_FairScope1"),
       ("HP_energy_floor", "HP, intra-aggregator, energy floor", "_FairCrit2_FairScope1" + E1)]
svc = {"title": "Delivery over two days: export requests every half-hour 06:00–20:00 on day 1, none on day 2",
       "network": "TR4, 46 PV–BESS prosumers, two days",
       "request": "at each requested flexibility slot (06:00–19:30 starts, 28 slots) the TSO requests the boundary point of "
                  "F_{k+1} with the most export (θ = 180°)",
       "definitions": {
           "export_served_kWh": "Σ over requests of 0.5 h × max(0, −ΔP_req), ΔP_req = requested point − no-request point of the same step",
           "extra_purchase_inside": "per prosumer, grid purchase inside the requested half-hours minus the same quantity in the run "
                                    "without requests (same settings), summed over the two days; counted when > 1 Wh",
           "extra_purchase_outside": "the same outside the requested half-hours",
       },
       "cases": [], "summary": {}, "per_request": {}, "extra_purchase_inside_by_prosumer_kWh": {}}
for cid, lab, suf in SVC:
    ex, rf = f"_WC_EXPORT{D2}{suf}", f"_REF{D2}{suf}"
    assert F.done(ex) and F.done(rf), (ex, rf)
    fq = A.read(L / f"FRQ{ex}.csv")
    e, b = A.days(L, ex, True), A.days(L, rf, True)
    assert e is not None and b is not None and e.now.max() == 96 and b.now.max() == 96
    m = e.merge(b, on=["now", "battery"], suffixes=("", "_r"))
    assert len(m) == len(e) == len(b)
    m["dimp"] = m.imp1_kWh - m.imp1_kWh_r
    w = m[m.svc == 1].groupby("battery").dimp.sum()
    o = m[m.svc != 1].groupby("battery").dimp.sum()
    nreq_plan = len(json.loads((Path(A.SCEN) / "WC_EXPORT.json").read_text())["requests"])
    svc["cases"].append({"id": cid, "label": lab, "source_tag": ex, "no_request_tag": rf})
    svc["summary"][cid] = {
        "requests_served": int(len(fq)), "requests_planned": nreq_plan,
        "requested_halfhours_in_exec_log": int(m[m.svc == 1].now.nunique()),
        "export_served_kWh": r(A.DT * (-fq.dP_kW).clip(lower=0).sum(), 1),
        "export_reduced_kWh": r(A.DT * fq.dP_kW.clip(lower=0).sum(), 1),
        "prosumers_buying_more_inside": int((w > 1e-3).sum()),
        "worst_prosumer_inside_kWh": r(max(w.max(), 0.0), 3),
        "worst_prosumer_inside_id": str(w.idxmax()) if w.max() > 1e-3 else None,
        "prosumers_buying_more_inside_by_10Wh": int((w > 1e-2).sum()),
        "fleet_extra_purchase_inside_kWh": r(w.sum(), 2),
        "worst_prosumer_outside_Wh": r(1000 * o.max(), 2), "worst_prosumer_outside_id": str(o.idxmax()),
        "fleet_extra_purchase_outside_kWh": r(o.sum(), 3),
    }
    fq = fq.sort_values("target")
    svc["per_request"][cid] = {"time": [A.clock(int(t)) for t in fq.target], "dP_kW": rl(fq.dP_kW), "dQ_kvar": rl(fq.dQ_kvar)}
    ww = w[w > 1e-3].sort_values(ascending=False)
    svc["extra_purchase_inside_by_prosumer_kWh"][cid] = [{"prosumer": str(k), "kWh": r(v, 3)} for k, v in ww.items()]


def mixed(tag, thr):
    c = F.read(L / f"FOR_rolling_crit{tag}.csv")
    c = c[c.status.isin(OK)]
    a180 = c.angle_deg.round() == 180
    mx = (c.zu > thr) & (c.zd > thr)
    return {"mixed": int((mx & a180).sum()), "of": int(a180.sum())}


svc["mixing_180deg"] = {
    "definition": "group-direction pairs at θ = 180° with both HP factors ζ↑ > 1e-3 and ζ↓ > 1e-3 (HP, intra-aggregator, "
                  "3 aggregators); also given with a 1e-6 threshold",
    "one_day_FOR": {fl: {**mixed(SW + "_FairCrit2_FairScope1" + s, MIX), "count_at_1e-6": mixed(SW + "_FairCrit2_FairScope1" + s, 1e-6)["mixed"],
                         "source_tag": SW + "_FairCrit2_FairScope1" + s} for fl, s in FLOOR.items()},
    "two_day_service": {fl: {**mixed(f"_WC_EXPORT{D2}_FairCrit2_FairScope1{s}", MIX),
                             "count_at_1e-6": mixed(f"_WC_EXPORT{D2}_FairCrit2_FairScope1{s}", 1e-6)["mixed"],
                             "source_tag": f"_WC_EXPORT{D2}_FairCrit2_FairScope1{s}"} for fl, s in FLOOR.items()},
}
(OUT / "service_T5.json").write_text(json.dumps(svc, ensure_ascii=False, indent=1), encoding="utf-8")

# ------------------------------------------------------------------ console summary for the README table
print("idle exchange check: max |sweep mean - P_idle| kW", round(idle_chk_max, 3), "| max |Q mid| kvar", round(max(q_mid), 3))
print(json.dumps(muf["summary"], ensure_ascii=False, indent=0))
print(muf["note_reference"])
for fl in FLOOR:
    for c in CRIT:
        print(fl, c, {sc: (v["mean"], v["min"], v["min_time"], v["max"]) for sc, v in fair["summary"][fl][c].items()},
              fair["summary"][fl][c]["intra-aggregator"]["times_below_1pct"], fair["summary"][fl][c]["network-wide"]["times_below_1pct"])
print(fair["note_ratio_reference"])
print(json.dumps(svc["summary"], ensure_ascii=False, indent=0))
print(json.dumps(svc["mixing_180deg"], ensure_ascii=False, indent=0))
for p in polys:
    print(p["time"], p["area_ratio"])
