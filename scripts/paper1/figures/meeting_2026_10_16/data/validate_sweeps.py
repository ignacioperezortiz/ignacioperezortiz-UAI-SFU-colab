"""Validate sweeps.json against fair.json, muf.json and the planners' quoted values. Writes <out>/data/validation_sweeps.json.
Run:  python -B validate_sweeps.py [--data DIR] [--out DIR]     (--data: the JSONs to check, default the committed ones)"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))     # package root: paths.py
import paths  # noqa: E402

paths.cli(__doc__, data=True)
S = json.loads(paths.deck_json("data_tulio", "sweeps.json").read_text(encoding="utf-8"))
FA = json.loads(paths.deck_json("data", "fair.json").read_text(encoding="utf-8"))
MU = json.loads(paths.deck_json("data", "muf.json").read_text(encoding="utf-8"))
T = S["time"]
ti = {t: i for i, t in enumerate(T)}
PC, CR, SM = S["per_case"], S["crit"], S["summary"]
rows = []


def chk(item, expected, got, tol, src):
    if isinstance(expected, (list, tuple)):
        e, g = np.array(expected, float), np.array(got, float)
        ok = e.shape == g.shape and bool(np.all(np.abs(e - g) <= tol + 1e-12))
        diff = float(np.max(np.abs(e - g))) if e.shape == g.shape else None
        rows.append({"item": item, "expected": f"{len(e)} values", "got": f"max |diff| {diff}", "ok": ok, "src": src})
    else:
        ok = abs(float(expected) - float(got)) <= tol + 1e-12
        rows.append({"item": item, "expected": expected, "got": got, "ok": ok, "src": src})


# ---------------------------------------------------------------- 1. fair.json (built by deck\data\scripts\build.py)
MAP = {"CP": "CP", "HP": "HP", "HB": "HB"}
for fl, suf in (("energy floor", ""), ("old floor", "_oldfloor")):
    for c in MAP:
        for sc, s2 in (("intra-aggregator", "intra"), ("network-wide", "nw")):
            cid = f"{c}_{s2}{suf}"
            chk(f"fair.json area_ratio[{fl}][{c}][{sc}] (48 values, 4 dp)", FA["area_ratio"][fl][c][sc],
                [round(x, 4) for x in PC[cid]["area_ratio"]], 0.0, "fair.json")
            fs, ss = FA["summary"][fl][c][sc], SM["area_ratio_stats"][cid]
            chk(f"fair.json mean {c} {s2} {fl}", fs["mean"], ss["mean"], 0.0, "fair.json")
            chk(f"fair.json min {c} {s2} {fl}", fs["min"], ss["min"], 0.0, "fair.json")
            rows.append({"item": f"fair.json min_time / <1% times {c} {s2} {fl}", "expected": f'{fs["min_time"]} {fs["times_below_1pct"]}',
                         "got": f'{ss["min_time"]} {ss["times_below_1pct"]}',
                         "ok": fs["min_time"] == ss["min_time"] and fs["times_below_1pct"] == ss["times_below_1pct"], "src": "fair.json"})
chk("fair.json reference area (48, 0 dp)", FA["reference_FOR_area_kWkvar"], [round(x) for x in PC["ref"]["area_kWkvar"]], 1.0, "fair.json")
chk("fair.json idle P (48)", FA["idle_exchange_per_step"]["P_kW"], S["idle_exchange"]["P_kW"], 0.0, "fair.json")
chk("fair.json idle Q (48)", FA["idle_exchange_per_step"]["Q_kvar"], S["idle_exchange"]["Q_kvar"], 0.0, "fair.json")
for lab, cid in (("reference", "ref"), ("HB", "HB_intra"), ("HP", "HP_intra"), ("CP", "CP_intra")):
    chk(f"fair.json dP_max {lab} intra (48)", FA["dP_range_intra_energy_floor"][lab]["dP_max_kW"], PC[cid]["dP_max_kW"], 0.0, "fair.json")
    chk(f"fair.json dP_min {lab} intra (48)", FA["dP_range_intra_energy_floor"][lab]["dP_min_kW"], PC[cid]["dP_min_kW"], 0.0, "fair.json")
PMAP = {"reference": "ref", "HB": "HB_intra", "HP": "HP_intra", "CP": "CP_intra", "HP, old floor": "HP_intra_oldfloor"}
for st in FA["polygons"]["steps"]:
    i = ti[st["time"]]
    for k, cid in PMAP.items():
        chk(f"fair.json polygon {st['time']} {k} (12×2, 2 dp)", np.array(st["FOR"][k]).ravel().tolist(),
            np.array(PC[cid]["polygons"][i]).ravel().tolist(), 0.0, "fair.json")

# ---------------------------------------------------------------- 2. muf.json
MM = {"muf_0.2": "ref_oldfloor", "muf_0.1": "muf01", "muf_0": "muf0", "muf_0.2_nolimits": "ref_nolimits", "muf_0_nolimits": "muf0_nolimits"}
for k, cid in MM.items():
    chk(f"muf.json area_ratio {k} (48, 4 dp)", MU["per_step"][k]["area_ratio"],
        [round(x, 4) for x in PC[cid]["area_ratio_vs_ref_oldfloor"]], 0.0, "muf.json")
    chk(f"muf.json FOR area {k} (48, 0 dp)", MU["per_step"][k]["FOR_area_kWkvar"], [round(x) for x in PC[cid]["area_kWkvar"]], 1.0, "muf.json")
    ms, ss = MU["summary"][k], SM["muf_limits"][cid]
    for a, b, tol in (("simultaneous_solves", "simultaneous_solves", 0), ("simultaneous_kW_max", "simultaneous_kW_max", 0),
                      ("throughput_kW_mean", "throughput_kW_mean", 0), ("area_ratio_mean", "area_ratio_vs_ref_oldfloor_mean", 0),
                      ("area_ratio_max", "area_ratio_vs_ref_oldfloor_max", 0), ("dP_0deg_vs_ref_kW_mean", "dP_0deg_vs_ref_oldfloor_mean_kW", 0),
                      ("dP_0deg_vs_ref_kW_max", "dP_0deg_vs_ref_oldfloor_max_kW", 0),
                      ("solves_exceeding_limits_by_1W", "solves_exceeding_limits_by_1W", 0),
                      ("max_exceedance_per_BESS_kW", "max_exceedance_per_BESS_kW", 0.0005)):
        chk(f"muf.json {k} {a}", ms[a], ss[b], tol, "muf.json")
    rows.append({"item": f"muf.json {k} area_ratio_max_time", "expected": ms["area_ratio_max_time"],
                 "got": ss["area_ratio_vs_ref_oldfloor_max_time"], "ok": ms["area_ratio_max_time"] == ss["area_ratio_vs_ref_oldfloor_max_time"], "src": "muf.json"})

# ---------------------------------------------------------------- 3. stated means (task brief)
for cid, e in (("CP_intra", 51.48), ("CP_nw", 40.27), ("HP_intra", 98.71), ("HP_nw", 98.58), ("HB_intra", 99.83), ("HB_nw", 99.77),
               ("HP_intra_oldfloor", 73.83), ("HP_nw_oldfloor", 63.42), ("HB_intra_oldfloor", 82.20), ("HB_nw_oldfloor", 73.72)):
    chk(f"brief: mean area ratio {cid} (%)", e, round(100 * SM["area_ratio_stats"][cid]["mean"], 2), 0.005, "brief")


# ---------------------------------------------------------------- 4. planners' quoted values
def cg(cid, ang, g, k, t):
    return CR[cid][f"deg{ang}"][g][k][ti[t]]


def fl(cid, ang, k, t):
    return CR[cid][f"deg{ang}"]["fleet"][k][ti[t]]


def ar(cid, t):
    return 100 * PC[cid]["area_ratio"][ti[t]]


def dmin(cid, t):
    return PC[cid]["dP_min_kW"][ti[t]]


def dmax(cid, t):
    return PC[cid]["dP_max_kW"][ti[t]]


Q = []   # (item, expected, got, tol, plan)
for g, e in zip(("Agg1", "Agg2", "Agg3"), (0.694, 0.993, 1.000)):
    Q.append((f"HP intra ζ↓ 12:30 {g}", e, cg("HP_intra", 180, g, "zd", "12:30"), 0.0005, "A/B/consensus"))
Q.append(("HP nw ζ↓ 12:30", 0.865, cg("HP_nw", 180, "ALL", "zd", "12:30"), 0.0005, "A/B"))
Q.append(("ref max shortfall at 180° (kW)", 7.1, SM["R1"]["max_shortfall_180deg_kW"], 0.05, "A/B/consensus"))
Q.append(("old-floor ΣD at 19:00 (kW)", 156.6, SM["R1"]["sumD_at"]["19:00"]["old_floor"], 0.05, "A/consensus"))
Q.append(("energy-floor ΣD at 19:00 (kW)", 77.4, SM["R1"]["sumD_at"]["19:00"]["energy_floor"], 0.05, "A/consensus"))
Q.append(("ref Σ ΔP^b 180° at 19:00 (kW)", -77.4, SM["R1"]["sumD_at"]["19:00"]["ref_sum_dP_180"], 0.05, "A"))
Q.append(("ΣD at 12:00 (kW)", 169.6, SM["R1"]["sumD_at"]["12:00"]["energy_floor"], 0.05, "A"))
Q.append(("ref Σ ΔP^b 180° at 12:00 (kW)", -162.5, SM["R1"]["sumD_at"]["12:00"]["ref_sum_dP_180"], 0.05, "A"))
Q.append(("ΣU at 12:30 (kW)", 1.6, SM["R1"]["sumU_at"]["12:30"]["sumU"], 0.05, "A"))
Q.append(("ref Σ ΔP^b 0° at 12:30 (kW)", 1.6, SM["R1"]["sumU_at"]["12:30"]["ref_sum_dP_0"], 0.05, "A"))
Q.append(("ΣU at 00:30 (kW)", 174.6, SM["R1"]["sumU_at"]["00:30"]["sumU"], 0.05, "B"))
Q.append(("ΣD at 00:30 (kW)", 48.1, fl("ref", 180, "sum_D_kW", "00:30"), 0.05, "B"))
Q.append(("ΣD at 07:30 (kW)", 180.4, SM["R1"]["sumD_at"]["07:30"]["energy_floor"], 0.05, "B"))
Q.append(("ΣD at 06:00 energy floor (kW)", 107.6, fl("ref", 180, "sum_D_kW", "06:00"), 0.05, "C"))
Q.append(("ΣD at 06:00 old floor (kW)", 111.3, fl("ref_oldfloor", 180, "sum_D_kW", "06:00"), 0.05, "C"))
for cid, e in (("ref", 108.3), ("HP_intra", 106.8), ("HB_intra", 108.2), ("CP_intra", 49.7), ("CP_nw", 31.8)):
    Q.append((f"mean export capability {cid} (kW)", e, SM["capability_mean_kW"][cid]["export_mean_kW"], 0.05, "B/consensus"))
for cid, e in (("ref", 79.8), ("HP_intra", 79.8), ("HB_intra", 79.8), ("CP_intra", 51.2)):
    Q.append((f"mean import capability {cid} (kW)", e, SM["capability_mean_kW"][cid]["import_mean_kW"], 0.05, "B"))
Q.append(("HP intra largest export loss (kW)", 12.6, SM["R5"]["HP_intra"]["max_export_loss_kW"], 0.05, "B/consensus"))
Q.append(("HP nw largest export loss (kW)", 15.4, SM["R5"]["HP_nw"]["max_export_loss_kW"], 0.05, "coordinator"))
Q.append(("ref dP_min 12:00 (kW)", -153.8, dmin("ref", "12:00"), 0.05, "B"))
Q.append(("HP intra dP_min 12:00 (kW)", -141.2, dmin("HP_intra", "12:00"), 0.05, "B"))
for g, e in zip(("Agg1", "Agg2", "Agg3"), ((-59.1, 61.5), (-54.3, 57.1), (-45.1, 46.8))):
    Q.append((f"ref 12:30 180° Σ ΔP^b {g}", e[0], cg("ref", 180, g, "sum_dP_kW", "12:30"), 0.05, "A/B"))
    Q.append((f"ref 12:30 ΣD {g}", e[1], cg("ref", 180, g, "sum_D_kW", "12:30"), 0.05, "A/B"))
for g, e in zip(("Agg1", "Agg2", "Agg3"), (96.1, 95.2, 96.3)):
    Q.append((f"ref 12:30 share180 {g} (%)", e, 100 * SM["R6"]["ref"]["12:30"][g]["share180"], 0.05, "C"))
for g, e in zip(("Agg1", "Agg2", "Agg3"), (89.0, 96.3, 97.7)):
    Q.append((f"HB intra 12:30 share180 {g} (%)", e, 100 * SM["R6"]["HB_intra"]["12:30"][g]["share180"], 0.05, "C"))
Q.append(("HB intra 12:30 Agg3 ζ↓", 0.90, cg("HB_intra", 180, "Agg3", "zd", "12:30"), 0.005, "B"))
Q.append(("HB intra 12:30 Agg3 ζ↑", 0.05, cg("HB_intra", 180, "Agg3", "zu", "12:30"), 0.005, "B"))
for g, e in zip(("Agg1", "Agg2", "Agg3"), (-67.8, -58.4, -54.2)):
    Q.append((f"ref 07:30 180° Σ ΔP^b {g}", e, cg("ref", 180, g, "sum_dP_kW", "07:30"), 0.05, "C"))
for g, e in zip(("Agg1", "Agg2", "Agg3"), (-0.208, -0.258, -0.074)):
    Q.append((f"CP intra 06:00 180° ζ {g}", e, cg("CP_intra", 180, g, "zcp", "06:00"), 0.0005, "A"))
for g in ("Agg1", "Agg2", "Agg3"):
    Q.append((f"CP intra 18:00 180° |ζ| {g} < 2e-5", 0.0, abs(cg("CP_intra", 180, g, "zcp", "18:00")), 2e-5, "A/B"))
    Q.append((f"CP intra 18:00 0° |ζ| {g} ≈ 0", 0.0, abs(cg("CP_intra", 0, g, "zcp", "18:00")), 5e-5, "B"))
for g, e in zip(("Agg1", "Agg2", "Agg3"), (-0.808, -0.856, -1.000)):
    Q.append((f"CP intra 12:30 ζ {g}", e, cg("CP_intra", 180, g, "zcp", "12:30"), 0.0005, "B"))
for g, e in zip(("Agg1", "Agg2", "Agg3"), (-0.672, -0.082, -1.000)):
    Q.append((f"CP intra 15:00 ζ {g}", e, cg("CP_intra", 180, g, "zcp", "15:00"), 0.0005, "B"))
Q.append(("CP nw 15:00 ζ", -0.082, cg("CP_nw", 180, "ALL", "zcp", "15:00"), 0.0005, "B/consensus"))
Q.append(("CP nw 12:30 ζ", -0.856, cg("CP_nw", 180, "ALL", "zcp", "12:30"), 0.0005, "B"))
Q.append(("CP intra dP_min 15:00 (kW)", -92.6, dmin("CP_intra", "15:00"), 0.05, "B/consensus"))
Q.append(("CP nw dP_min 15:00 (kW)", -16.0, dmin("CP_nw", "15:00"), 0.05, "B/consensus"))
for g, e in zip(("Agg1", "Agg2", "Agg3"), (36.4, 28.0, 20.3)):
    Q.append((f"18:00 ΣD energy floor {g}", e, cg("ref", 180, g, "sum_D_kW", "18:00"), 0.05, "B"))
    Q.append((f"18:00 ref-without-limits Σ ΔP^b 180° {g}", -e, cg("ref_nolimits", 180, g, "sum_dP_kW", "18:00"), 0.05, "B"))
    Q.append((f"18:00 HP intra ζ↓ {g}", 1.0, cg("HP_intra", 180, g, "zd", "18:00"), 0.0005, "B"))
for g, e in zip(("Agg1", "Agg2", "Agg3"), (60.8, 54.3, 43.5)):
    Q.append((f"18:00 ΣD old floor {g}", e, cg("ref_oldfloor", 180, g, "sum_D_kW", "18:00"), 0.05, "B"))
Q.append(("HP old floor 18:00 Agg1 ζ↓", 0.0, cg("HP_intra_oldfloor", 180, "Agg1", "zd", "18:00"), 0.0005, "B"))
Q.append(("HP old floor 18:00 Agg2 ζ↑", 0.205, cg("HP_intra_oldfloor", 180, "Agg2", "zu", "18:00"), 0.0005, "B"))
Q.append(("HP old floor 18:00 Agg2 ζ↓", 0.078, cg("HP_intra_oldfloor", 180, "Agg2", "zd", "18:00"), 0.0005, "B"))
Q.append(("HP old floor dP_min 18:00 (kW)", -10.1, dmin("HP_intra_oldfloor", "18:00"), 0.05, "B"))
for t, cid, lo, hi, p in (("06:00", "ref", -77.0, 164.4, "A"), ("06:00", "CP_intra", -1.2, 150.0, "A"), ("22:00", "ref", -97.4, 115.9, "A"),
                          ("22:00", "CP_intra", -21.5, 6.7, "A"), ("12:30", "ref", -154.2, 4.9, "A"), ("12:30", "HP_intra", -142.6, 4.9, "A"),
                          ("12:30", "HP_nw", -139.9, 4.9, "A"), ("06:00", "CP_nw", 17.4, 148.6, "A"), ("12:30", "CP_nw", -138.9, 3.3, "A"),
                          ("18:00", "CP_nw", -7.2, -6.6, "A"), ("22:00", "CP_nw", -21.5, 2.3, "A"), ("18:00", "ref", -91.4, 8.9, "A/B"),
                          ("18:00", "CP_intra", -7.2, -6.6, "B"), ("15:00", "ref", -153.8, 2.5, "B"), ("15:00", "CP_intra", -92.6, 1.8, "B"),
                          ("21:30", "ref", -97.2, 101.6, "B"), ("21:30", "CP_intra", -21.7, 4.0, "B"), ("07:30", "ref", -143.1, 134.3, "B"),
                          ("07:30", "CP_intra", -29.9, 64.0, "B")):
    Q.append((f"{cid} dP_min {t}", lo, dmin(cid, t), 0.05, p))
    Q.append((f"{cid} dP_max {t}", hi, dmax(cid, t), 0.05, p))
Q.append(("HB intra dP_min 12:30", -151.4, dmin("HB_intra", "12:30"), 0.05, "A/B"))
Q.append(("CP intra dP_max 20:00 (import capability)", -15.9, dmax("CP_intra", "20:00"), 0.05, "B"))
Q.append(("HP intra export 10:00 (kW)", 151, -dmin("HP_intra", "10:00"), 0.5, "C"))
Q.append(("ref export 10:00 (kW)", 157, -dmin("ref", "10:00"), 0.5, "C"))
for cid, e in (("CP_intra", 50.7), ("CP_nw", 39.9), ("HP_intra", 99.1), ("HP_nw", 98.9), ("HB_intra", 99.9), ("HB_nw", 99.9)):
    Q.append((f"mean width ratio {cid} (%)", e, 100 * SM["width_ratio_mean"][cid], 0.05, "A"))
for t, cid, e, p in (("07:30", "CP_intra", 39.5, "B/C"), ("07:30", "HP_intra", 98.3, "C"), ("07:30", "HB_intra", 99.9, "C"),
                     ("12:30", "CP_intra", 92.3, "C"), ("12:30", "HP_intra", 93.7, "C"), ("12:30", "HB_intra", 97.5, "C"),
                     ("18:00", "CP_intra", 0.0, "C"), ("18:00", "HP_intra", 99.0, "C"), ("18:00", "HB_intra", 100.2, "C"),
                     ("06:00", "CP_intra", 60.3, "A"), ("06:00", "CP_nw", 50.7, "A"), ("22:00", "CP_intra", 13.7, "A"), ("22:00", "CP_nw", 11.2, "A"),
                     ("22:00", "HP_intra", 98.8, "A"), ("22:00", "HP_nw", 98.7, "A"), ("06:00", "HP_intra_oldfloor", 75.4, "A"),
                     ("18:00", "HP_intra_oldfloor", 20.5, "A/C"), ("22:00", "HP_intra_oldfloor", 71.2, "A"), ("17:00", "HP_intra_oldfloor", 6.2, "A"),
                     ("21:30", "CP_intra", 12.8, "C"), ("07:30", "CP_nw", 17.7, "C"), ("15:00", "CP_intra", 67.7, "B"), ("15:00", "CP_nw", 11.4, "B"),
                     ("18:30", "HP_intra_oldfloor", 22.4, "C"), ("18:30", "HP_intra", 99.1, "C"), ("17:00", "HP_intra", 98.6, "A")):
    Q.append((f"area ratio {cid} {t} (%)", e, ar(cid, t), 0.05, p))
for cid, e in (("CP_intra", 53.4), ("HP_intra", 98.8), ("HB_intra", 99.85)):
    Q.append((f"volume ratio {cid} (%)", e, 100 * SM["volume_ratio"][cid], 0.05 if cid != "HB_intra" else 0.005, "C"))
Q.append(("CP intra no limits mean (%)", 53.27, 100 * SM["area_ratio_stats"]["CP_intra_nolimits"]["mean"], 0.005, "A/C"))
Q.append(("HB intra no limits mean (%)", 82.20, 100 * SM["area_ratio_stats"]["HB_intra_nolimits"]["mean"], 0.005, "A/C"))
Q.append(("CP intra no limits max exceedance (kW)", 0.361, SM["muf_limits"]["CP_intra_nolimits"]["max_exceedance_per_BESS_kW"], 0.0005, "A"))
Q.append(("HB intra no limits max exceedance (kW)", 0.0009, SM["muf_limits"]["HB_intra_nolimits"]["max_exceedance_per_BESS_kW"], 0.00005, "A"))
Q.append(("HP intra old floor μ^f 0.1 mean (%)", 74.45, 100 * SM["area_ratio_stats"]["HP_intra_oldfloor_muf01"]["mean"], 0.005, "A/C"))
Q.append(("ref no limits export capability (kW)", 108.3, SM["capability_mean_kW"]["ref_nolimits"]["export_mean_kW"], 0.05, "B"))
Q.append(("CP intra no limits export capability (kW)", 49.7, SM["capability_mean_kW"]["CP_intra_nolimits"]["export_mean_kW"], 0.05, "B"))
Q.append(("HB intra old floor export capability (kW)", 81.3, SM["capability_mean_kW"]["HB_intra_oldfloor"]["export_mean_kW"], 0.05, "B"))
Q.append(("HB intra no limits export capability (kW)", 81.3, SM["capability_mean_kW"]["HB_intra_nolimits"]["export_mean_kW"], 0.05, "B"))
Q.append(("mixed 180° HP intra old floor", 72, SM["mixed_180deg_HP_intra"]["old_floor"]["mixed"], 0, "consensus"))
Q.append(("mixed 180° HP intra energy floor", 6, SM["mixed_180deg_HP_intra"]["energy_floor"]["mixed"], 0, "consensus"))
Q.append(("reference area max (kW·kvar)", 75543, SM["reference_area"]["max"], 1, "C"))
Q.append(("reference area min (kW·kvar)", 28494, SM["reference_area"]["min"], 1, "C"))
Q.append(("reference area 07:30 (kW·kvar)", 74122, PC["ref"]["area_kWkvar"][ti["07:30"]], 1, "C"))
Q.append(("HP intra min ratio (%)", 93.70, 100 * SM["area_ratio_stats"]["HP_intra"]["min"], 0.005, "consensus R3"))
Q.append(("HP nw min ratio (%)", 92.52, 100 * SM["area_ratio_stats"]["HP_nw"]["min"], 0.005, "consensus R3"))
Q.append(("HB max ratio intra", 1.0054, SM["area_ratio_stats"]["HB_intra"]["max"], 0.00005, "consensus"))
Q.append(("HB max ratio nw", 1.0062, SM["area_ratio_stats"]["HB_nw"]["max"], 0.00005, "consensus"))
for item, e, g, tol, p in Q:
    chk(item, e, g, tol, "plan " + p)
rows.append({"item": "R1 shortfall > 0.1 kW window", "expected": "10:00–14:30",
             "got": list(SM["R1"]["shortfall_180deg_gt_0.1kW"].keys()), "ok": None, "src": "plan A/B/consensus"})
rows.append({"item": "R1 shortfall > 1 kW window", "expected": "10:00–14:30",
             "got": list(SM["R1"]["shortfall_180deg_gt_1kW"].keys()), "ok": None, "src": "consensus amendment 6"})
rows.append({"item": "R1 max shortfall time", "expected": "12:00", "got": SM["R1"]["max_shortfall_180deg_time"],
             "ok": SM["R1"]["max_shortfall_180deg_time"] == "12:00", "src": "plan A"})
rows.append({"item": "R1 steps reaching ΣU at 0°", "expected": 48, "got": SM["R1"]["steps_reaching_sumU_at_0deg_within_0.1kW"],
             "ok": SM["R1"]["steps_reaching_sumU_at_0deg_within_0.1kW"] == 48, "src": "plan A/B"})
for cid, e in (("HP_intra", "12:00"), ("HP_nw", "12:00")):
    rows.append({"item": f"R5 {cid} largest export loss time", "expected": e, "got": SM["R5"][cid]["max_export_loss_time"],
                 "ok": SM["R5"][cid]["max_export_loss_time"] == e, "src": "plan B/coordinator"})
for cid in ("HP_intra", "HP_nw"):
    rows.append({"item": f"R5 {cid} never loses import (> 0.1 kW)", "expected": "[]", "got": SM["R5"][cid]["import_loss_gt_0.1kW_times"],
                 "ok": SM["R5"][cid]["import_loss_gt_0.1kW_times"] == [], "src": "consensus R5"})

bad = [x for x in rows if x["ok"] is False]
(paths.data_out() / "validation_sweeps.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(f"{len(rows)} checks, {sum(1 for x in rows if x['ok'])} ok, {len(bad)} mismatch, {sum(1 for x in rows if x['ok'] is None)} info")
for x in bad:
    print("MISMATCH", x)
for x in rows:
    if x["ok"] is None:
        print("INFO", x)
