"""Build sweeps.json (the deck's data_tulio\\sweeps.json) from the one-day REF_SWEEP runs (lane N2, TR4).

Reuses the conventions of build.py:
  - analyze_fair.corners / area / read (FOR_rolling joined with summed crit columns), shoelace on the 12 points;
  - all-idle exchange P_idle(t) = P_PCC1 - sum Pexec, Q_idle(t) = Q_PCC1 - sum Qinv1 from FOR_rolling_soc of the
    reference at now = t, used for step `now` at t = target (= now mod 48 + 1);
  - time label = analyze_paper1.clock(target) = start of flexibility slot k+1.
Read-only on the lane; writes only into <out>/data.
Run:  python -B build_sweeps.py [--runs DIR] [--out DIR]
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
L, SW = F.LANE, F.SW
E1 = "_FairEffHead1"

# id -> (suffix, label, floor, limits, mu_f, criterion, scope)
CASES = {
    "ref":               (E1, "reference (no fairness)", "energy", True, 0.2, None, None),
    "CP_intra":          ("_FairCrit1_FairScope1" + E1, "CP, intra-aggregator", "energy", True, 0.2, "CP", "intra"),
    "CP_nw":             ("_FairCrit1_FairScope2" + E1, "CP, network-wide", "energy", True, 0.2, "CP", "nw"),
    "HP_intra":          ("_FairCrit2_FairScope1" + E1, "HP, intra-aggregator", "energy", True, 0.2, "HP", "intra"),
    "HP_nw":             ("_FairCrit2_FairScope2" + E1, "HP, network-wide", "energy", True, 0.2, "HP", "nw"),
    "HB_intra":          ("_FairCrit3_FairScope1_FairEps0.1" + E1, "HB (ε = 0.1), intra-aggregator", "energy", True, 0.2, "HB", "intra"),
    "HB_nw":             ("_FairCrit3_FairScope2_FairEps0.1" + E1, "HB (ε = 0.1), network-wide", "energy", True, 0.2, "HB", "nw"),
    "CP_intra_oldfloor": ("_FairCrit1_FairScope1", "CP, intra-aggregator, old floor", "old", True, 0.2, "CP", "intra"),
    "CP_nw_oldfloor":    ("_FairCrit1_FairScope2", "CP, network-wide, old floor", "old", True, 0.2, "CP", "nw"),
    "HP_intra_oldfloor": ("_FairCrit2_FairScope1", "HP, intra-aggregator, old floor", "old", True, 0.2, "HP", "intra"),
    "HP_nw_oldfloor":    ("_FairCrit2_FairScope2", "HP, network-wide, old floor", "old", True, 0.2, "HP", "nw"),
    "HB_intra_oldfloor": ("_FairCrit3_FairScope1_FairEps0.1", "HB (ε = 0.1), intra-aggregator, old floor", "old", True, 0.2, "HB", "intra"),
    "HB_nw_oldfloor":    ("_FairCrit3_FairScope2_FairEps0.1", "HB (ε = 0.1), network-wide, old floor", "old", True, 0.2, "HB", "nw"),
    "ref_oldfloor":      ("_FairBox1", "reference, old floor", "old", True, 0.2, None, None),
    "ref_nolimits":      ("_FairBox0", "reference, without headroom limits", "old", False, 0.2, None, None),
    "CP_intra_nolimits": ("_FairCrit1_FairScope1_FairBox0_FairAllowNoBox1", "CP, intra-aggregator, without headroom limits (old floor)", "old", False, 0.2, "CP", "intra"),
    "HB_intra_nolimits": ("_FairCrit3_FairScope1_FairEps0.1_FairBox0_FairAllowNoBox1", "HB (ε = 0.1), intra-aggregator, without headroom limits (old floor)", "old", False, 0.2, "HB", "intra"),
    "muf0":              ("_P2SlotPen0", "reference, μ^f = 0 (old floor)", "old", True, 0.0, None, None),
    "muf01":             ("_P2SlotPen0.1", "reference, μ^f = 0.1 (old floor)", "old", True, 0.1, None, None),
    "muf0_nolimits":     ("_FairBox0_P2SlotPen0", "reference, μ^f = 0, without headroom limits", "old", False, 0.0, None, None),
    # extra (not requested; logged for the notes)
    "HP_intra_oldfloor_muf01": ("_FairCrit2_FairScope1_P2SlotPen0.1", "HP, intra-aggregator, old floor, μ^f = 0.1 (extra)", "old", True, 0.1, "HP", "intra"),
}
CUT = ["07:30", "12:30", "15:00", "18:00", "21:30"]
GROUPS = ["Agg1", "Agg2", "Agg3"]


def r(x, n=2):
    if x is None:
        return None
    x = float(x)
    return round(x, n) if np.isfinite(x) else None


def rl(a, n=2):
    return [r(v, n) for v in a]


# ------------------------------------------------------------------ steps, clock, idle exchange (as build.py)
REF_TAG = SW + E1
ref0 = F.corners(REF_TAG)
steps = sorted(ref0.now.unique())
assert steps == list(range(1, 49))
target = ref0.groupby("now").target.first()
TIME = [A.clock(int(target[n])) for n in steps]
HOUR = [0.5 * n for n in steps]                                      # z coordinate: 00:30 -> 0.5 ... 00:00 -> 24
soc = A.read(L / f"FOR_rolling_soc{REF_TAG}.csv")
g = soc.groupby("now").agg(P=("P_PCC1", "first"), Q=("Q_PCC1", "first"), sP=("Pexec", "sum"), sQ=("Qinv1", "sum"))
IDLE = {int(n): (1000 * (x.P - x.sP), 1000 * (x.Q - x.sQ)) for n, x in g.iterrows()}
BP = pd.Series({n: IDLE[int(target[n])][0] for n in steps})
BQ = pd.Series({n: IDLE[int(target[n])][1] for n in steps})
ti = {t: i for i, t in enumerate(TIME)}


def tm(now):
    return TIME[steps.index(now)]


# ------------------------------------------------------------------ per case: FOR polygons, area, ΔP range, crit
cases, raw, crit_raw, fairp = {}, {}, {}, {}
for cid, (suf, lab, fl, lim, mu, cr, sc) in CASES.items():
    tag = SW + suf
    assert F.done(tag), tag
    d = F.corners(tag)
    assert len(d) == 576 and d.ok.all(), (tag, len(d))
    d = d.sort_values(["now", "angle"])
    d["dP"] = d.P_kW - d.now.map(BP)
    d["dQ"] = d.Q_kW - d.now.map(BQ)
    raw[cid] = d
    c = F.read(L / f"FOR_rolling_crit{tag}.csv")
    c["group"] = c.group.str.strip()
    assert c.status.isin(F.OK).all()
    crit_raw[cid] = c
    fp = A.read(L / f"FOR_rolling_fair{tag}.csv")
    fp["aggregator"] = fp.aggregator.str.strip()
    fairp[cid] = fp
    info = F.info_lines(tag, "FAIR settings")
    cases[cid] = {"label": lab, "source_tag": tag, "floor": fl, "headroom_limits": lim, "mu_f": mu,
                  "criterion": cr, "scope": sc, "commit": "2f68674" if "FairEffHead  1" in (info[0] if info else "") else "866c053",
                  "FAIR_settings_line": info[0] if info else None}

area = {cid: F.area(raw[cid]).reindex(steps) for cid in CASES}
ref_area = area["ref"]
oldref_area = area["ref_oldfloor"]

per_case = {}
for cid in CASES:
    d = raw[cid]
    polys = [[[r(p), r(q)] for p, q in zip(x.dP, x.dQ)] for _, x in d.groupby("now")]
    gp = d.groupby("now").dP
    per_case[cid] = {
        "polygons": polys,
        "area_kWkvar": rl(area[cid], 1),
        "dP_min_kW": rl(gp.min().reindex(steps)),
        "dP_max_kW": rl(gp.max().reindex(steps)),
        "area_ratio": rl(area[cid] / ref_area, 10),
    }
    if cases[cid]["floor"] == "old" or cid.startswith("muf"):
        per_case[cid]["area_ratio_vs_ref_oldfloor"] = rl(area[cid] / oldref_area, 10)


# ------------------------------------------------------------------ baseline per aggregator (P^{b,SC}_{k+1} sums) and per-aggregator ΣΔP^b
def s0_from(cid):
    """per (now, group) Σ P^{b,SC} = Σ sumP_pu*1000 - sum_dP_kW, checked constant over the 12 directions"""
    c, fp = crit_raw[cid], fairp[cid].copy()
    fp["P_kW"] = 1000 * fp.sumP_pu
    if cases[cid]["scope"] == "nw":
        fp = fp.groupby(["now", "angle_deg"]).P_kW.sum().reset_index().assign(group="ALL")
    else:
        fp = fp.rename(columns={"aggregator": "group"})
    m = c.merge(fp[["now", "angle_deg", "group", "P_kW"]], on=["now", "angle_deg", "group"])
    m["s0"] = m.P_kW - m.sum_dP_kW
    spread = m.groupby(["now", "group"]).s0.agg(lambda s: s.max() - s.min()).max()
    return m.groupby(["now", "group"]).s0.mean(), float(spread)


S0, S0_spread = {}, {}
for cid in CASES:
    S0[cid], S0_spread[cid] = s0_from(cid)
S0_ref = S0["ref"].unstack()                                           # now x Agg1..3
s0_cross = {}
for cid in CASES:
    if cases[cid]["scope"] == "nw":
        s0_cross[cid] = float((S0[cid].unstack()["ALL"] - S0_ref.sum(axis=1)).abs().max())
    else:
        s0_cross[cid] = float((S0[cid].unstack()[GROUPS] - S0_ref).abs().max().max())

crit = {}
for cid in CASES:
    c = crit_raw[cid]
    grp_names = sorted(c.group.unique())
    out = {"groups": grp_names}
    fp = fairp[cid]
    for ang in (0, 180):
        x = c[c.angle_deg.round() == ang]
        blk = {}
        for gname in grp_names:
            y = x[x.group == gname].set_index("now").reindex(steps)
            blk[gname] = {k: rl(y[k], 3 if k.startswith("sum") else 4) for k in
                          ("sum_dP_kW", "sum_U_kW", "sum_D_kW", "zcp", "zu", "zd")}
        fl = x.groupby("now")[["sum_dP_kW", "sum_U_kW", "sum_D_kW"]].sum().reindex(steps)
        blk["fleet"] = {k: rl(fl[k], 3) for k in fl.columns}
        # per-aggregator ΣΔP^b from FOR_rolling_fair (sumP_pu) minus the reference's per-aggregator baseline
        f = fp[fp.angle_deg.round() == ang].pivot(index="now", columns="aggregator", values="sumP_pu").reindex(steps) * 1000
        blk["per_aggregator_dP_from_fair_kW"] = {gname: rl(f[gname] - S0_ref[gname], 3) for gname in GROUPS}
        out[f"deg{ang}"] = blk
    crit[cid] = out

# U, D per aggregator are the same in every run with the same floor (baseline is identical) -> check
UD = {}
for fl in ("energy", "old"):
    base = "ref" if fl == "energy" else "ref_oldfloor"
    b = crit_raw[base][crit_raw[base].angle_deg.round() == 0].set_index(["now", "group"])[["sum_U_kW", "sum_D_kW"]]
    UD[fl] = b
ud_check = {}
for cid in CASES:
    if cases[cid]["scope"] != "intra" and cid not in ("ref", "ref_oldfloor", "ref_nolimits", "muf0", "muf01", "muf0_nolimits"):
        b = UD[cases[cid]["floor"]].groupby("now").sum()
        x = crit_raw[cid].groupby("now")[["sum_U_kW", "sum_D_kW"]].first()
        ud_check[cid] = float((x - b).abs().max().max())
    else:
        b = UD[cases[cid]["floor"]]
        x = crit_raw[cid].groupby(["now", "group"])[["sum_U_kW", "sum_D_kW"]].first()
        ud_check[cid] = float((x - b.reindex(x.index)).abs().max().max())

# ------------------------------------------------------------------ reference: voltage per step (max VmaxTrue over 12 directions)
fr = F.read(L / f"FOR_rolling{REF_TAG}.csv")
vm = fr.loc[fr.groupby("now").VmaxTrue.idxmax()].set_index("now").reindex(steps)
vmax_ref = {"VmaxTrue_max_pu": rl(vm.VmaxTrue, 5), "angle_deg": [int(a) for a in vm.angle_deg],
            "VmaxTrue_180deg_pu": rl(fr[fr.angle_deg.round() == 180].set_index("now").VmaxTrue.reindex(steps), 5),
            "OVviol_max": rl(fr.groupby("now").OVviol.max().reindex(steps), 6),
            "note": "FOR_rolling<ref>.csv VmaxTrue (pu, AC check of each directional solve); max over the 12 directions per step"}
vmax_ref["times_at_or_above_1.0995_pu"] = [TIME[i] for i, v in enumerate(vmax_ref["VmaxTrue_max_pu"]) if v >= 1.0995]


# ------------------------------------------------------------------ summaries
def stats(series):
    s = series.reindex(steps)
    return {"mean": r(s.mean(), 4), "min": r(s.min(), 4), "min_time": tm(s.idxmin()), "max": r(s.max(), 4),
            "max_time": tm(s.idxmax()), "times_below_1pct": [tm(n) for n in steps if s[n] < 0.01],
            "times_above_1.0005": [tm(n) for n in steps if s[n] > 1.0005]}


summary = {"capability_mean_kW": {}, "area_ratio_stats": {}, "area_ratio_stats_vs_ref_oldfloor": {}, "volume_ratio": {},
           "width_ratio_mean": {}}
ref_w = raw["ref"].groupby("now").dP.agg(lambda s: s.max() - s.min())
for cid in CASES:
    d = raw[cid].groupby("now").dP
    summary["capability_mean_kW"][cid] = {"export_mean_kW": r(-d.min().mean(), 2), "import_mean_kW": r(d.max().mean(), 2)}
    summary["area_ratio_stats"][cid] = stats(area[cid] / ref_area)
    summary["volume_ratio"][cid] = r(area[cid].sum() / ref_area.sum(), 4)
    summary["width_ratio_mean"][cid] = r((d.agg(lambda s: s.max() - s.min()) / ref_w).mean(), 4)
    if "area_ratio_vs_ref_oldfloor" in per_case[cid]:
        summary["area_ratio_stats_vs_ref_oldfloor"][cid] = stats(area[cid] / oldref_area)

# R1
cr = crit["ref"]
U0 = pd.Series(cr["deg0"]["fleet"]["sum_U_kW"], index=steps)
dP0 = pd.Series(cr["deg0"]["fleet"]["sum_dP_kW"], index=steps)
D180 = pd.Series(cr["deg180"]["fleet"]["sum_D_kW"], index=steps)
dP180 = pd.Series(cr["deg180"]["fleet"]["sum_dP_kW"], index=steps)
Dold = pd.Series(crit["ref_oldfloor"]["deg180"]["fleet"]["sum_D_kW"], index=steps)
short = D180 + dP180                    # > 0: the reference delivers less export than ΣD_s
reach0 = U0 - dP0
over = Dold - D180
summary["R1"] = {
    "definition": "BESS level, fleet sums of FOR_rolling_crit (3 aggregator rows). shortfall(180°) = ΣD_s + Σ ΔP^b_s at θ = 180°; "
                  "gap(0°) = ΣU_s − Σ ΔP^b_s at θ = 0°",
    "steps_reaching_sumU_at_0deg_within_0.1kW": int((reach0 < 0.1).sum()),
    "max_gap_0deg_kW": r(reach0.max(), 3), "max_gap_0deg_time": tm(reach0.idxmax()),
    "shortfall_180deg_gt_0.1kW": {tm(n): r(short[n], 2) for n in steps if short[n] > 0.1},
    "shortfall_180deg_gt_1kW": {tm(n): r(short[n], 2) for n in steps if short[n] > 1.0},
    "max_shortfall_180deg_kW": r(short.max(), 2), "max_shortfall_180deg_time": tm(short.idxmax()),
    "old_floor_sumD_minus_energy_floor_sumD_max_kW": r(over.max(), 2), "old_floor_overstatement_max_time": tm(over.idxmax()),
    "sumD_at": {t: {"energy_floor": r(D180[steps[ti[t]]], 1), "old_floor": r(Dold[steps[ti[t]]], 1),
                    "ref_sum_dP_180": r(dP180[steps[ti[t]]], 1)} for t in ("07:30", "12:00", "12:30", "18:00", "19:00", "21:30")},
    "sumU_at": {t: {"sumU": r(U0[steps[ti[t]]], 1), "ref_sum_dP_0": r(dP0[steps[ti[t]]], 1)} for t in ("00:30", "07:30", "12:30", "18:00")},
}

# R5 export/import loss vs reference (same step, idle cancels)
summary["R5"] = {}
for cid in ("HP_intra", "HP_nw", "HB_intra", "HB_nw", "CP_intra", "CP_nw"):
    a, b = raw["ref"].groupby("now").dP, raw[cid].groupby("now").dP
    exl = (b.min() - a.min())          # >0 : less export than the reference
    iml = (a.max() - b.max())          # >0 : less import
    summary["R5"][cid] = {"max_export_loss_kW": r(exl.max(), 2), "max_export_loss_time": tm(exl.idxmax()),
                          "export_loss_gt_0.1kW_times": [tm(n) for n in steps if exl[n] > 0.1],
                          "max_import_loss_kW": r(iml.max(), 2), "max_import_loss_time": tm(iml.idxmax()),
                          "import_loss_gt_0.1kW_times": [tm(n) for n in steps if iml[n] > 0.1]}
    if cid.startswith(("HP", "HB")):
        win = [n for n in steps if exl[n] > 0.5]
        rat = (area[cid] / ref_area)
        outside = [n for n in steps if n not in win]
        summary["R5"][cid]["export_loss_kW_by_time_gt_0.05"] = {tm(n): r(exl[n], 2) for n in steps if exl[n] > 0.05}
        summary["R5"][cid]["export_loss_gt_0.5kW_window"] = [tm(n) for n in win]
        summary["R5"][cid]["min_area_ratio_outside_that_window"] = r(rat[outside].min(), 4)
        summary["R5"][cid]["min_area_ratio_outside_that_window_time"] = tm(rat[outside].idxmin())

# 15:00 scope contrast (consensus amendment 10)
i15 = ti["15:00"]
summary["scope_contrast_15:00"] = {
    "CP_intra_dP_min_kW": per_case["CP_intra"]["dP_min_kW"][i15], "CP_nw_dP_min_kW": per_case["CP_nw"]["dP_min_kW"][i15],
    "ref_dP_min_kW": per_case["ref"]["dP_min_kW"][i15],
    "CP_intra_zeta_180": {gname: crit["CP_intra"]["deg180"][gname]["zcp"][i15] for gname in GROUPS},
    "CP_nw_zeta_180": crit["CP_nw"]["deg180"]["ALL"]["zcp"][i15],
    "CP_area_ratio_intra": r(area["CP_intra"][steps[i15]] / ref_area[steps[i15]], 4),
    "CP_area_ratio_nw": r(area["CP_nw"][steps[i15]] / ref_area[steps[i15]], 4)}

# R6 shares at the cut hours
summary["R6"] = {"definition": "share180 = −Σ ΔP^b / ΣD_s at θ = 180°; share0 = Σ ΔP^b / ΣU_s at θ = 0° (per aggregator, BESS level). "
                               "For network-wide runs the crit file has one group 'ALL'; per-aggregator values come from "
                               "FOR_rolling_fair sumP_pu minus the reference's per-aggregator baseline.", "times": CUT}
for cid in ("ref", "CP_intra", "CP_nw", "HP_intra", "HP_nw", "HB_intra", "HB_nw", "HP_intra_oldfloor"):
    res = {}
    for t in CUT:
        i = ti[t]
        e = {}
        for gname in crit[cid]["groups"]:
            a0, a1 = crit[cid]["deg0"][gname], crit[cid]["deg180"][gname]
            e[gname] = {"share180": r(-a1["sum_dP_kW"][i] / a1["sum_D_kW"][i], 4) if a1["sum_D_kW"][i] else None,
                        "share0": r(a0["sum_dP_kW"][i] / a0["sum_U_kW"][i], 4) if a0["sum_U_kW"][i] else None,
                        "sum_dP_180": a1["sum_dP_kW"][i], "sum_D": a1["sum_D_kW"][i],
                        "sum_dP_0": a0["sum_dP_kW"][i], "sum_U": a0["sum_U_kW"][i],
                        "zcp_0": a0["zcp"][i], "zcp_180": a1["zcp"][i], "zu_180": a1["zu"][i], "zd_180": a1["zd"][i],
                        "zu_0": a0["zu"][i], "zd_0": a0["zd"][i]}
        if cases[cid]["scope"] == "nw":
            for gname in GROUPS:
                d1 = crit[cid]["deg180"]["per_aggregator_dP_from_fair_kW"][gname][i]
                d0 = crit[cid]["deg0"]["per_aggregator_dP_from_fair_kW"][gname][i]
                Dg = crit["ref"]["deg180"][gname]["sum_D_kW"][i]
                Ug = crit["ref"]["deg0"][gname]["sum_U_kW"][i]
                e[gname + "_from_fair"] = {"share180": r(-d1 / Dg, 4) if Dg else None, "share0": r(d0 / Ug, 4) if Ug else None,
                                           "sum_dP_180": d1, "sum_dP_0": d0}
        ip = raw[cid][raw[cid].now == steps[i]]
        e["dP_min_kW"], e["dP_max_kW"] = r(ip.dP.min()), r(ip.dP.max())
        e["area_ratio"] = r(area[cid][steps[i]] / ref_area[steps[i]], 4)
        res[t] = e
    summary["R6"][cid] = res

# mixed allocations (HP intra, 180°)
def mixed(cid, thr=1e-3):
    c = crit_raw[cid]
    a = c[c.angle_deg.round() == 180]
    return {"mixed": int(((a.zu > thr) & (a.zd > thr)).sum()), "of": int(len(a))}


summary["mixed_180deg_HP_intra"] = {"energy_floor": mixed("HP_intra"), "old_floor": mixed("HP_intra_oldfloor")}

# μ^f / limits table (as muf.json, re-derived)
summary["muf_limits"] = {}
for cid in ("ref_oldfloor", "muf01", "muf0", "ref_nolimits", "muf0_nolimits", "ref", "CP_intra_nolimits", "HB_intra_nolimits"):
    s = raw[cid]
    z = s[s.angle == 0].set_index("now").P_kW - raw["ref_oldfloor"][raw["ref_oldfloor"].angle == 0].set_index("now").P_kW
    summary["muf_limits"][cid] = {
        "simultaneous_solves": int((s.n_cyc > 0).sum()), "simultaneous_kW_max": r(s.cyc_kW.max()),
        "throughput_kW_mean": r(s.thr_kW.mean()), "area_ratio_vs_ref_oldfloor_mean": r((area[cid] / oldref_area).mean(), 4),
        "area_ratio_vs_ref_oldfloor_max": r((area[cid] / oldref_area).max(), 4),
        "area_ratio_vs_ref_oldfloor_max_time": tm((area[cid] / oldref_area).idxmax()),
        "dP_0deg_vs_ref_oldfloor_mean_kW": r(z.mean()), "dP_0deg_vs_ref_oldfloor_max_kW": r(z.max()),
        "solves_exceeding_limits_by_1W": int(((s.box_up > 1e-3) | (s.box_dn > 1e-3)).sum()),
        "max_exceedance_per_BESS_kW": r(max(s.box_up.max(), s.box_dn.max()), 4)}

# energy-floor vs old-floor reference
mm = raw["ref"].merge(raw["ref_oldfloor"], on=["now", "angle"], suffixes=("", "_o"))
summary["ref_vs_ref_oldfloor"] = {"area_ratio_min": r((ref_area / oldref_area).min(), 5), "area_ratio_max": r((ref_area / oldref_area).max(), 5),
                                  "max_abs_dP_kW": r((mm.P_kW - mm.P_kW_o).abs().max(), 3),
                                  "max_abs_dQ_kvar": r((mm.Q_kW - mm.Q_kW_o).abs().max(), 3)}
summary["reference_area"] = {"max": r(ref_area.max(), 0), "max_time": tm(ref_area.idxmax()),
                             "min": r(ref_area.min(), 0), "min_time": tm(ref_area.idxmin())}

checks = {"baseline_S0_spread_over_directions_kW": {k: r(v, 4) for k, v in S0_spread.items()},
          "baseline_S0_vs_reference_kW": {k: r(v, 4) for k, v in s0_cross.items()},
          "U_D_vs_same_floor_reference_kW": {k: r(v, 4) for k, v in ud_check.items()}}

# per-aggregator from fair vs crit for intra runs
pa = 0.0
for cid in CASES:
    if cases[cid]["scope"] != "nw":
        for ang in ("deg0", "deg180"):
            for gname in GROUPS:
                a = np.array(crit[cid][ang][gname]["sum_dP_kW"], float)
                b = np.array(crit[cid][ang]["per_aggregator_dP_from_fair_kW"][gname], float)
                pa = max(pa, float(np.nanmax(np.abs(a - b))))
checks["per_aggregator_dP_fair_vs_crit_intra_kW"] = r(pa, 4)

out = {
    "title": "One-day REF_SWEEP runs (TR4): FOR polygons, areas, ΔP range, headroom sums and factors",
    "lane": L.name, "tag_prefix": SW,
    "time_note": "time = HH:MM at the start of flexibility slot k+1; index i ↔ rolling step now = i+1 (step 48 = 00:00)",
    "hour": HOUR,
    "time": TIME,
    "coordinates": "polygon points = [ΔP kW, ΔQ kvar], deviation of the interface exchange from the estimated all-idle exchange "
                   "(same as deck\\data\\fair.json), + import; 12 points ordered θ = 0°, 30°, …, 330° (0° = +ΔP, 90° = +ΔQ)",
    "idle_exchange": {"P_kW": rl(BP), "Q_kvar": rl(BQ)},
    "cases": cases,
    "per_case": per_case,
    "crit": crit,
    "reference_voltage": vmax_ref,
    "summary": summary,
    "checks": checks,
}
OUT.mkdir(exist_ok=True)
(OUT / "sweeps.json").write_text(json.dumps(out, ensure_ascii=False, indent=None, separators=(",", ":")), encoding="utf-8")
print("written", OUT / "sweeps.json", (OUT / "sweeps.json").stat().st_size, "bytes")
print(json.dumps(checks, indent=0))
