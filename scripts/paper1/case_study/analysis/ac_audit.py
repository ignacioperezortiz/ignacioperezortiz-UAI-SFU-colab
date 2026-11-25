"""AC audit of the FOR corners, per recorded run (ACAudit=1): results/case-study/summary/<run_id>/ac_audit_corners.csv.

Per run: corners checked; corners that break a limit in AC as built (by cause: transformer, line, over- and
under-voltage; a corner can break several); corners the audit would move toward S0 (lambda < 1) and how far; corners
pulled all the way back (lambda = 0); SOC trimming; FOR area with the audited corners as a share of the FOR as built
(median and worst period); time spent in the audit's load flows. The audit never changes a result unless ACAuditApply=1.

Writes <summary folder>/../analysis/ac_audit.csv and ac_audit_by_step.csv.
Usage: python scripts/paper1/case_study/analysis/ac_audit.py [run_id ...] [--summary DIR]
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

RES = Path(__file__).resolve().parents[4] / "results" / "case-study"
ap = argparse.ArgumentParser()
ap.add_argument("runs", nargs="*")
ap.add_argument("--summary", default=str(RES / "summary"))
a = ap.parse_args()
S = Path(a.summary)
OUT = S.parent / "analysis"
runs = a.runs or sorted(p.name for p in S.iterdir() if (p / "ac_audit_corners.csv").exists())


def area(x, y):
    return 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


rows, steps = [], []
for rid in runs:
    c = pd.read_csv(S / rid / "ac_audit_corners.csv", skipinitialspace=True)
    c.columns = [x.strip() for x in c.columns]
    tol = 1e-6
    fail = c.ok0 == 0
    moved = c["lambda"] < 1 - 1e-9
    shift = np.hypot(c.P_new_kW - c.P_kW, c.Q_new_kvar - c.Q_kvar)
    for (now, tgt), g in c.groupby(["now", "target"]):
        g = g.sort_values("angle_deg")
        a0, a1 = area(g.P_kW.to_numpy(), g.Q_kvar.to_numpy()), area(g.P_new_kW.to_numpy(), g.Q_new_kvar.to_numpy())
        steps.append({"run_id": rid, "now": now, "target": tgt, "corners": len(g), "failed": int((g.ok0 == 0).sum()),
                      "area_built_kVA2": a0, "area_audited_kVA2": a1, "area_kept": a1 / a0 if a0 > 0 else np.nan})
    st = pd.DataFrame([s for s in steps if s["run_id"] == rid])
    rows.append({"run_id": rid, "periods": int(c.target.nunique()), "corners": len(c), "failed_in_AC": int(fail.sum()),
                 "failed_transformer": int((fail & (c.trafo0 > 1 + tol)).sum()), "failed_line": int((fail & (c.line0 > 1 + tol)).sum()),
                 "failed_overvoltage": int((fail & (c.ov0_pu > tol)).sum()), "failed_undervoltage": int((fail & (c.uv0_pu > tol)).sum()),
                 "moved": int(moved.sum()), "back_to_S0": int((c["lambda"] < 1e-9).sum()),
                 "shift_median_kVA": float(shift[moved].median()) if moved.any() else 0.0, "shift_max_kVA": float(shift.max()),
                 "trimmed": int((c.trim_kW.abs() > 1e-6).sum()), "trim_max_kW": float(c.trim_kW.abs().max()),
                 "area_kept_median": float(st.area_kept.median()), "area_kept_min": float(st.area_kept.min()),
                 "audit_lf_seconds": float(c.lf_sec.sum()) if "lf_sec" in c else np.nan})
t = pd.DataFrame(rows)
OUT.mkdir(parents=True, exist_ok=True)
t.to_csv(OUT / "ac_audit.csv", index=False, float_format="%.5f")
pd.DataFrame(steps).to_csv(OUT / "ac_audit_by_step.csv", index=False, float_format="%.5f")
pd.set_option("display.width", 220)
print(t.T.to_string(header=False) if len(t) else "no run with ac_audit_corners.csv")
