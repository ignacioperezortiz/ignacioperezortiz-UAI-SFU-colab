"""Analysis of the paper-1 fairness tests T2-T6 (docs/paper1-fairness.md section 5), lane N2.
Imported by build.py and build_sweeps.py; on its own:  python -B analyze_fair.py [--runs DIR]"""
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))     # package root: paths.py
import paths  # noqa: E402

if __name__ == "__main__":
    paths.cli(__doc__, runs=True)                                 # imported, the caller has parsed --runs already
LANE = paths.lane("N2")
SW = "_REF_SWEEP_free_today_a2x4p8fin_TR4"
OK = ("Optimal", "LocallyOptimal")


def read(p):
    if not p.exists() or p.stat().st_size == 0:
        return None
    d = pd.read_csv(p, skipinitialspace=True, keep_default_na=False, dtype=str)
    d.columns = [c.strip() for c in d.columns]
    d = d.apply(lambda s: s.str.strip())
    for c in d.columns:
        if c not in ("status", "group"):
            d[c] = pd.to_numeric(d[c], errors="coerce")
    return d


def done(tag):
    f = LANE / f"done{tag}.txt"
    return f.exists() and "Return value = 0" in f.read_text(errors="ignore")


def corners(tag):
    """FOR corners (kW) joined with the summed group columns of the crit CSV, per (now, angle)."""
    f = read(LANE / f"FOR_rolling{tag}.csv")
    c = read(LANE / f"FOR_rolling_crit{tag}.csv")
    if f is None:
        return None
    f = f.rename(columns={"angle_deg": "angle"})
    f["P_kW"], f["Q_kW"], f["proj_kW"] = 1000 * f["P"], 1000 * f["Q"], 1000 * f["proj"]
    f["ok"] = f["status"].isin(OK)
    if c is not None:
        c = c.rename(columns={"angle_deg": "angle"})
        agg = c.groupby(["now", "angle"]).agg(
            thr_kW=("thr_kW", "sum"), n_cyc=("n_cyc", "sum"), cyc_kW=("cyc_kW", "sum"),
            box_up=("box_up_viol_kW", "max"), box_dn=("box_dn_viol_kW", "max"),
            cp_dev=("cp_dev_max", "max"), rule_res=("rule_res_max_kW", "max"), hb_viol=("hb_viol_max_kW", "max"),
            cp_spread=("cp_spread", "max"), kappa=("kappa", "max")).reset_index()
        f = f.merge(agg, on=["now", "angle"], how="left")
        f["obj_kW"] = f["proj_kW"] - f["kappa"] * f["thr_kW"]   # directional objective (to maximise)
    return f


def area(df):
    out = {}
    for now, g in df[df["ok"]].groupby("now"):
        g = g.sort_values("angle")
        P, Q = g["P_kW"].to_numpy(), g["Q_kW"].to_numpy()
        out[now] = 0.5 * abs(np.dot(P, np.roll(Q, -1)) - np.dot(Q, np.roll(P, -1))) if len(P) >= 3 else 0.0
    return pd.Series(out)


def info_lines(tag, key):
    f = LANE / f"SCT_info{tag}.txt"
    return [l for l in f.read_text(errors="ignore").splitlines() if l.startswith(key)] if f.exists() else []


def summary(tag, label):
    d = corners(tag)
    if d is None:
        print(f"{label}: not available")
        return None
    n, nok = len(d), int(d["ok"].sum())
    s = d[d["ok"]]
    line = f"{label}: corners {nok}/{n} optimal"
    if "thr_kW" in s:
        line += (f" | n_cyc>0 corners {int((s['n_cyc'] > 0).sum())}, cyc max {s['cyc_kW'].max():.4f} kW"
                 f" | box viol up/dn max {s['box_up'].max():.4f}/{s['box_dn'].max():.4f} kW")
        for col, nm in (("cp_dev", "cp_dev_max"), ("rule_res", "rule_res kW"), ("hb_viol", "hb_viol kW")):
            if s[col].notna().any():
                line += f" | {nm} max {s[col].max():.2e}"
    clip = info_lines(tag, "FAIRCLIP")
    base = info_lines(tag, "FAIRBASE")
    line += f" | FAIRCLIP lines {len(clip)}, FAIRBASE lines {len(base)}"
    print(line)
    return d


def pair(ta, tb, la, lb):
    a, b = corners(ta), corners(tb)
    if a is None or b is None:
        print(f"  {la} vs {lb}: not available")
        return
    m = a.merge(b, on=["now", "angle"], suffixes=("_a", "_b"))
    both = m[m["ok_a"] & m["ok_b"]]
    dP, dQ = both["P_kW_a"] - both["P_kW_b"], both["Q_kW_a"] - both["Q_kW_b"]
    dproj = both["proj_kW_a"] - both["proj_kW_b"]
    print(f"  {la} - {lb}: {len(both)} corners solved in both | max|dP| {dP.abs().max():.3f} kW, max|dQ| {dQ.abs().max():.3f} kW,"
          f" proj diff min {dproj.min():.3f} max {dproj.max():.3f} kW, {int((dproj.abs() > 1e-3).sum())} corners differ > 1 W")
    if "obj_kW_a" in both:
        dobj = both["obj_kW_a"] - both["obj_kW_b"]
        print(f"     objective (proj - kappa thr) diff min {dobj.min():.4f} max {dobj.max():.4f} kW")
    big = both.assign(dproj=dproj).loc[dproj.abs() > 1e-3].sort_values("dproj")
    if len(big):
        print("     largest |dproj| corners (now, angle, dproj kW):",
              [(int(r.now), int(r.angle), round(r.dproj, 3)) for r in big.head(4).itertuples()],
              [(int(r.now), int(r.angle), round(r.dproj, 3)) for r in big.tail(4).itertuples()])
    ar_a, ar_b = area(a), area(b)
    common = ar_a.index.intersection(ar_b.index)
    if len(common):
        rel = (ar_a[common] / ar_b[common].replace(0, np.nan))
        print(f"     FOR area {la}/{lb}: mean {rel.mean():.4f}, min {rel.min():.4f}, max {rel.max():.4f} (over {len(common)} steps)")


def main():
    print("== T2: reference FOR, box on vs off")
    t2a, t2b = SW + "_FairBox1", SW + "_FairBox0"
    summary(t2a, "box on  (paper flow)")
    summary(t2b, "box off (Tulio 9-Oct)")
    pair(t2a, t2b, "box on", "box off")

    print("\n== T3: role of kappa (diagnostic)")
    t3a, t3b = SW + "_P2SlotPen0", SW + "_FairBox0_P2SlotPen0"
    summary(t3a, "box on,  kappa 0")
    summary(t3b, "box off, kappa 0")
    pair(t3a, t2a, "box+k0", "box+k0.2")
    pair(t3b, t2b, "nobox+k0", "nobox+k0.2")
    pair(t3a, t3b, "box+k0", "nobox+k0")

    print("\n== T4: criteria (box on, kappa 0.2)")
    crit = {"CP intra": "_FairCrit1_FairScope1", "CP nw": "_FairCrit1_FairScope2", "HP intra": "_FairCrit2_FairScope1",
            "HP nw": "_FairCrit2_FairScope2", "HB0.1 intra": "_FairCrit3_FairScope1_FairEps0.1",
            "HB0.1 nw": "_FairCrit3_FairScope2_FairEps0.1"}
    for k, v in crit.items():
        summary(SW + v, k)
        pair(SW + v, t2a, k, "ref")
    for c in ("CP", "HP", "HB0.1"):
        ta, tb = SW + crit[f"{c} nw"], SW + crit[f"{c} intra"]
        a, b = corners(ta), corners(tb)
        if a is None or b is None:
            continue
        m = a.merge(b, on=["now", "angle"], suffixes=("_nw", "_in"))
        both = m[m["ok_nw"] & m["ok_in"]]
        viol = both["obj_kW_nw"] - both["obj_kW_in"]
        print(f"  nesting {c}: network-wide objective - intra objective, max {viol.max():.4f} kW "
              f"({int((viol > 1e-3).sum())} corners above 1 W; must be <= 0 up to tolerance); "
              f"failed corners nw {int((~m['ok_nw']).sum())}, intra {int((~m['ok_in']).sum())}")
    for c in ("intra", "nw"):
        hp, hb, ref = corners(SW + crit[f"HP {c}"]), corners(SW + crit[f"HB0.1 {c}"]), corners(t2a)
        if hp is None or hb is None or ref is None:
            continue
        m = hp.merge(hb, on=["now", "angle"], suffixes=("_hp", "_hb")).merge(ref[["now", "angle", "obj_kW", "ok"]], on=["now", "angle"])
        both = m[m["ok_hp"] & m["ok_hb"] & m["ok"]]
        print(f"  HB(0.1) between HP and ref ({c}): HP<=HB violations {int((both['obj_kW_hp'] - both['obj_kW_hb'] > 1e-3).sum())}, "
              f"HB<=ref violations {int((both['obj_kW_hb'] - both['obj_kW'] > 1e-3).sum())} of {len(both)}")

    print("\n== T6: kappa 0.1 (optional)")
    for v, l in (("_P2SlotPen0.1", "ref kappa0.1"), ("_FairCrit2_FairScope1_P2SlotPen0.1", "HP intra kappa0.1")):
        summary(SW + v, l)
    pair(SW + "_P2SlotPen0.1", t2a, "k0.1", "k0.2")

    print("\n== T5: delivery (two days)")
    for tag in ["_WC_EXPORT_free_today_a2x4p8fin2_TR4_FairCrit2_FairScope1", "_WC_IMPORT_free_today_a2x4p8fin2_TR4_FairCrit2_FairScope1",
                "_WC_EXPORT_free_today_a2x4p8fin2_TR4_FairBox1", "_WC_IMPORT_free_today_a2x4p8fin2_TR4_FairBox1"]:
        dl = info_lines(tag, "FAIRDELIV")
        ex = info_lines(tag, "EXECFAIL")
        vals = {k: [] for k in ("res_pre_kW", "res_post_kW", "box_pre_kW", "box_post_kW", "shave_kWh")}
        for l in dl:
            for k in vals:
                m = re.search(k + r"\s+([-0-9.eE+]+)", l)
                if m:
                    vals[k].append(float(m.group(1)))
        stats = ", ".join(f"{k} max {max(v):.2e}" for k, v in vals.items() if v)
        print(f"{tag}: done={done(tag)} FAIRDELIV lines {len(dl)} ({stats}) EXECFAIL lines {len(ex)}")


if __name__ == "__main__":
    main()
