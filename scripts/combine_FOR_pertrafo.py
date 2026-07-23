"""Minkowski combination of per-transformer rolling FORs.

Each per-TR run k (TRk detailed, others lumped passive) yields, for every step
'now' and sweep direction theta, the support point v_k(now,theta) of the reachable
PCC set. Support points are additive under Minkowski sums, but every per-TR region
contains the same all-idle passive background B(target), so the whole-feeder region
is

    V(now,theta) = sum_k v_k(now,theta) - (N-1) * B(target),   target = mod(now,48)+1

with B from FOR_rolling_baseline.csv (RunFOR_Rolling_Baseline). A combined direction
exists only where ALL contributing transformers returned Optimal.

Usage:
  python combine_FOR_pertrafo.py --tags TR1,TR2,...,TR9 [--dir model_clean]
        [--baseline path] [--out FOR_rolling_combined.csv]
        [--compare FOR_rolling_TR3TR4.csv]   # coupling-gap metrics vs a coupled run

--tags is REQUIRED and explicit (the old auto-glob wrongly swallowed *_bak/micro
archives). With a single tag the result is that region unchanged (B cancels), which
doubles as a plumbing test. The output keeps the FOR_rolling column convention, so
plot_FOR_dailywalk.py renders it directly.
"""
import argparse, os, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = str(Path(__file__).resolve().parents[1])

def load(path):
    d = pd.read_csv(path, skipinitialspace=True)
    d.columns = [c.strip() for c in d.columns]
    for c in d.columns:
        if d[c].dtype == object or pd.api.types.is_string_dtype(d[c]):
            d[c] = d[c].astype(str).str.strip()
    return d

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags", required=True, help="comma list, e.g. TR1,TR2,TR9")
    ap.add_argument("--dir", default=ROOT)
    ap.add_argument("--baseline", default=None, help="FOR_rolling_baseline.csv (needed for >1 tag)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--compare", default=None, help="coupled-run CSV to validate against")
    ap.add_argument("--tol", type=float, default=1e-4, help="outer-bound tolerance (p.u.)")
    a = ap.parse_args()

    tags = [t.strip() for t in a.tags.split(",") if t.strip()]
    N = len(tags)
    regs = {}
    for t in tags:
        p = os.path.join(a.dir, f"FOR_rolling_{t}.csv")
        d = load(p)
        d = d[d.status == "Optimal"][["now", "target", "angle_deg", "P", "Q"]]
        regs[t] = d
        print(f"  {t}: {d['now'].nunique()} steps, {len(d)} Optimal vertices")

    # baseline B(target); with N=1 its coefficient is 0 and it is not required
    if N > 1:
        bpath = a.baseline or os.path.join(a.dir, "FOR_rolling_baseline.csv")
        if not os.path.exists(bpath):
            sys.exit(f"ERROR: {N} tags need the baseline anchor; {bpath} not found. "
                     "Run RunFOR_Rolling_Baseline first.")
        b = load(bpath)
        if (b.status != "Optimal").any():
            print(f"  WARNING: baseline has {(b.status != 'Optimal').sum()}/48 non-Optimal periods")
        B = b.set_index("period")[["P", "Q"]]
    else:
        B = None

    # inner-join all regions on (now, angle)
    m = None
    for t in tags:
        d = regs[t].rename(columns={"P": f"P_{t}", "Q": f"Q_{t}"})
        m = d if m is None else m.merge(d.drop(columns="target"), on=["now", "angle_deg"], how="inner")
    Pcols = [f"P_{t}" for t in tags]; Qcols = [f"Q_{t}" for t in tags]
    m["P"] = m[Pcols].sum(axis=1)
    m["Q"] = m[Qcols].sum(axis=1)
    if N > 1:
        m["P"] -= (N - 1) * m["target"].map(B["P"])
        m["Q"] -= (N - 1) * m["target"].map(B["Q"])
    m["status"] = "Optimal"

    out = a.out or os.path.join(a.dir, "FOR_rolling_combined.csv" if N > 1
                                else f"FOR_rolling_combined_{tags[0]}.csv")
    m[["now", "target", "angle_deg", "P", "Q", "status"]].to_csv(out, index=False)
    cov = m.groupby("now").size()
    print(f"\ncombined ({'+'.join(tags)}): {len(m)} vertices over {m['now'].nunique()} steps -> {out}")
    print(f"  coverage: {cov.min()}-{cov.max()} of 12 directions per step "
          f"(full 12 in {(cov == 12).sum()}/{m['now'].nunique()} steps)")
    print(f"  extent P[{m.P.min():.3f},{m.P.max():.3f}] Q[{m.Q.min():.3f},{m.Q.max():.3f}] p.u.")

    if a.compare:
        c = load(a.compare)
        c = c[c.status == "Optimal"][["now", "angle_deg", "P", "Q"]]
        j = m.merge(c, on=["now", "angle_deg"], suffixes=("_dec", "_cpl"))
        th = np.deg2rad(j.angle_deg.values)
        gap = (j.P_dec - j.P_cpl) * np.cos(th) + (j.Q_dec - j.Q_cpl) * np.sin(th)
        scale = max(j.P_cpl.max() - j.P_cpl.min(), j.Q_cpl.max() - j.Q_cpl.min())
        cen = j.groupby("now").agg(dP=("P_dec", "mean"), cP=("P_cpl", "mean"),
                                   dQ=("Q_dec", "mean"), cQ=("Q_cpl", "mean"))
        off = np.hypot(cen.dP - cen.cP, cen.dQ - cen.cQ)
        print(f"\nCOUPLING GAP vs {os.path.basename(a.compare)} ({len(j)} common vertices):")
        print(f"  support gap (decomposed - coupled): mean {gap.mean():+.4f}  max {gap.max():.4f} p.u."
              f"  ({100 * gap.max() / scale:.1f}% of region scale {scale:.2f})")
        print(f"  outer bound holds (gap >= -{a.tol}): {(gap >= -a.tol).mean() * 100:.1f}% of directions")
        print(f"  centroid offset: mean {off.mean():.4f}  max {off.max():.4f} p.u.")

if __name__ == "__main__":
    main()
