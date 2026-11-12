r"""Compare a TR4 CP run with the reference made in Chile (reference_TR4_CP): FOR vertices (P, Q, status) per step and direction, and the
executed BESS dispatch. Usage: python compare_with_reference.py <your lane folder, e.g. C:\work\L1>"""
import sys, glob, os
import pandas as pd
TAG = "_CS_A_free_today_a0x4p8fin_TR4_CaseAggMap1_ACAudit0_FairCrit1_FairScope1"
HERE = os.path.dirname(os.path.abspath(__file__))


def rd(p):
    d = pd.read_csv(p, encoding="utf-8-sig", skipinitialspace=True); d.columns = [c.strip() for c in d.columns]
    for c in d.columns:
        if d[c].dtype == object:
            d[c] = d[c].astype(str).str.strip()
    return d


mine = sys.argv[1]
for kind, keys, vals in (("FOR_rolling", ["now", "angle_deg"], ["P", "Q"]), ("SCT_exec", ["now", "battery"], ["soc_start", "imp1_kWh", "batt1_kWh"])):
    a = rd(os.path.join(HERE, "reference_TR4_CP", f"{kind}{TAG}.csv")); b = rd(os.path.join(mine, f"{kind}{TAG}.csv"))
    m = a.merge(b, on=keys, suffixes=("_ref", "_new"), how="outer", indicator=True)
    print(f"{kind}: rows reference {len(a)}, yours {len(b)}, only in one of them {int((m._merge != 'both').sum())}")
    if "status_ref" in m:
        print("  status differs in", int((m.status_ref != m.status_new).sum()), "rows")
    for v in vals:
        d = (m[v + "_ref"] - m[v + "_new"]).abs()
        print(f"  {v}: max |difference| {d.max():.3e} (at {m.loc[d.idxmax(), keys].to_dict() if d.notna().any() else '-'})")
