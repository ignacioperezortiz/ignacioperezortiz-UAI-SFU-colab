"""Whole feeder vs the Minkowski sum of the transformer FORs (meeting 22 Oct 2026, section 7).

Interface convention (proposed, to confirm with Nacho): every FOR is expressed as a DEVIATION from the run's own
scheduled exchange at the interface for the same slot (the executed exchange of that slot in Run A, which has no
service: fleet_by_step.csv, pcc_P_kW / pcc_Q_kvar at now = target). This removes the passive load of the other
transformers that every transformer-level run carries at the feeder head. Each corner maximises cos(theta) P +
sin(theta) Q (up to the small throughput penalty), so the sum of the nine transformers' corners in each direction is
the corner of their Minkowski sum in that direction. Upstream (MV) losses and MV limits are what the comparison measures.

Fairness: a fairness rule applied transformer by transformer is NOT the same rule over the whole feeder (e.g. HP
network-wide inside each transformer is not HP over the feeder), so the sum of fair transformer FORs is a different,
looser region. Compare the reference FORs first.

Writes results/case-study/analysis/minkowski_<variant>.csv (per step: areas, directional differences, solve times).
Usage: python scripts/paper1/case_study/analysis/minkowski.py --variant REF [--repeat r1] [--summary DIR]
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

RES = Path(__file__).resolve().parents[4] / "results" / "case-study"
TRAFOS = [f"TR{i}" for i in range(1, 10)]

ap = argparse.ArgumentParser()
ap.add_argument("--variant", default="REF")
ap.add_argument("--repeat", default="r1")
ap.add_argument("--run", default="A")
ap.add_argument("--summary", default=str(RES / "summary"), help="folder with one sub-folder per run id")
a = ap.parse_args()
S = Path(a.summary)


def load(net):
    d = S / f"CS-{a.run}-{net}-{a.variant}-{a.repeat}"
    if not (d / "for_corners.csv").exists():
        return None
    c = pd.read_csv(d / "for_corners.csv", skipinitialspace=True)
    f = pd.read_csv(d / "fleet_by_step.csv")
    c.columns = [x.strip() for x in c.columns]
    s0 = f.set_index("now")[["pcc_P_kW", "pcc_Q_kvar"]]
    c = c[(c.target == c.now + 1) & c.target.isin(s0.index)].copy()   # the step-48 FOR (slot 1 of the next day) has no S0 here
    c["dP"] = 1000 * c.P - c.target.map(s0.pcc_P_kW)
    c["dQ"] = 1000 * c.Q - c.target.map(s0.pcc_Q_kvar)
    return c


def area(x, y):
    return 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


tr = {t: load(t) for t in TRAFOS}
have = [t for t, c in tr.items() if c is not None]
feeder = load("ALL")
print(f"transformers found: {have or 'none'}; whole feeder: {'yes' if feeder is not None else 'no'}")
if not have:
    raise SystemExit("no transformer runs for this variant")
rows = []
targets = sorted(set.intersection(*[set(tr[t].target) for t in have]))
for tgt in targets:
    parts = [tr[t][tr[t].target == tgt].sort_values("angle_deg") for t in have]
    if any(len(p) != len(parts[0]) for p in parts):
        continue
    ang = parts[0].angle_deg.to_numpy()
    sP = sum(p.dP.to_numpy() for p in parts)
    sQ = sum(p.dQ.to_numpy() for p in parts)
    row = {"target": tgt, "transformers": len(have), "area_sum_kVA2": area(sP, sQ),
           "solve_s_sum": sum(p.time.sum() for p in parts if "time" in p)}
    if feeder is not None and tgt in set(feeder.target):
        g = feeder[feeder.target == tgt].sort_values("angle_deg")
        if len(g) == len(ang):
            th = np.radians(ang)
            supp_sum = np.cos(th) * sP + np.sin(th) * sQ          # support values of the Minkowski sum
            supp_wf = np.cos(th) * g.dP.to_numpy() + np.sin(th) * g.dQ.to_numpy()
            row.update(area_feeder_kVA2=area(g.dP.to_numpy(), g.dQ.to_numpy()),
                       support_diff_max_kW=float(np.max(supp_sum - supp_wf)),
                       support_diff_min_kW=float(np.min(supp_sum - supp_wf)),
                       solve_s_feeder=float(g.time.sum()) if "time" in g else np.nan)
            row["area_ratio_feeder_over_sum"] = row["area_feeder_kVA2"] / row["area_sum_kVA2"] if row["area_sum_kVA2"] else np.nan
    rows.append(row)
out = pd.DataFrame(rows)
(RES / "analysis").mkdir(parents=True, exist_ok=True)
fn = RES / "analysis" / f"minkowski_{a.run}_{a.variant}_{a.repeat}.csv"
out.to_csv(fn, index=False, float_format="%.4f")
pd.set_option("display.width", 200)
print(out.describe().T[["mean", "min", "max"]].to_string())
print("wrote", fn)
