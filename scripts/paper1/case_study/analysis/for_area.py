"""FOR area over the day, per recorded case-study run, and the fairness area ratio (meeting 22 Oct 2026, section 9).

Reads results/case-study/summary/<run_id>/for_corners.csv (12 corners per step; P, Q absolute at the interface, MW /
Mvar, positive = import). Area of the 12-corner polygon (corners ordered by direction), kVA^2 (= kW x kvar).

Fairness ratio = (sum over the day of the fairness-constrained areas) / (sum over the same steps of the reference areas),
for the same network and run; steps where the reference area is zero are left out of both sums and counted.

Writes results/case-study/analysis/for_area_by_step.csv and for_area_daily.csv; prints the daily table.
Usage: python scripts/paper1/case_study/analysis/for_area.py [run_id ...] [--summary DIR]   (default: every recorded run)
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

RES = Path(__file__).resolve().parents[4] / "results" / "case-study"
OUT = RES / "analysis"


def area(g):
    g = g.sort_values("angle_deg")
    x, y = 1000 * g.P.to_numpy(float), 1000 * g.Q.to_numpy(float)
    return 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def parse(run_id):   # CS-A-TR4-HPi-r1 -> (A, TR4, HPi, r1)
    p = run_id.split("-")
    return p[1], p[2], "-".join(p[3:-1]), p[-1]


ap = argparse.ArgumentParser()
ap.add_argument("runs", nargs="*")
ap.add_argument("--summary", default=str(RES / "summary"))
a = ap.parse_args()
SUMDIR = Path(a.summary)
runs = a.runs or sorted(p.name for p in SUMDIR.iterdir() if (p / "for_corners.csv").exists())
rows = []
for rid in runs:
    c = pd.read_csv(SUMDIR / rid / "for_corners.csv", skipinitialspace=True)
    c.columns = [x.strip() for x in c.columns]
    ok = c.status.astype(str).str.strip().isin(["Optimal", "LocallyOptimal"])
    run, net, var, rep = parse(rid)
    for (now, tgt), g in c.groupby(["now", "target"]):
        rows.append({"run_id": rid, "run": run, "network": net, "variant": var, "repeat": rep, "now": now, "target": tgt,
                     "area_kVA2": area(g), "P_min_kW": 1000 * g.P.min(), "P_max_kW": 1000 * g.P.max(),
                     "Q_min_kvar": 1000 * g.Q.min(), "Q_max_kvar": 1000 * g.Q.max(),
                     "corners_optimal": int(ok[g.index].sum()), "solve_s": float(g.time.sum()) if "time" in g else np.nan})
s = pd.DataFrame(rows)
OUT.mkdir(parents=True, exist_ok=True)
s.to_csv(OUT / "for_area_by_step.csv", index=False, float_format="%.4f")
daily = s.groupby(["run_id", "run", "network", "variant"]).agg(steps=("target", "size"), area_sum_kVA2=("area_kVA2", "sum"),
                                                              corners_optimal=("corners_optimal", "sum"),
                                                              solve_s=("solve_s", "sum")).reset_index()
ratios = []
for (run, net), d in s.groupby(["run", "network"]):
    ref = d[d.variant == "REF"]
    if ref.empty:
        continue
    ref = ref[ref.repeat == ref.repeat.max()].set_index("target").area_kVA2
    for var, v in d[d.variant != "REF"].groupby("variant"):
        v = v[v.repeat == v.repeat.max()].set_index("target").area_kVA2
        common = ref.index.intersection(v.index)
        use = [t for t in common if ref[t] > 0]
        ratios.append({"run": run, "network": net, "variant": var, "steps_used": len(use),
                       "steps_zero_reference": len(common) - len(use),
                       "area_ratio": v[use].sum() / ref[use].sum() if use else np.nan})
daily.to_csv(OUT / "for_area_daily.csv", index=False, float_format="%.4f")
pd.DataFrame(ratios).to_csv(OUT / "fairness_area_ratio.csv", index=False, float_format="%.5f")
pd.set_option("display.width", 200)
print(daily.to_string(index=False))
if ratios:
    print("\nfairness area ratio (sum of fair areas / sum of reference areas, same steps):")
    print(pd.DataFrame(ratios).to_string(index=False))
