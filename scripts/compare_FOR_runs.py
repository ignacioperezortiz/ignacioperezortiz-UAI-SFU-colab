r"""Compare two rolling-FOR runs row by row, to check a refactor changed nothing.

Aligns the two CSVs on (now, angle_deg) and reports where they differ. The
acceptance criterion is deliberately NOT "P and Q are equal":

    The sweep maximises a LINEAR objective over a convex QCP feasible set, so the
    optimal VALUE  proj = cos(theta)*P + sin(theta)*Q  is unique, but the argmax
    need not be. Where the FOR boundary has a flat face perpendicular to the
    sweep direction the optimal point is a whole segment, and any solver change
    (a different starting point, a different tolerance, a different CPLEX build)
    may legitimately return a different point on that same face.

    So: proj is the invariant to test. P and Q are diagnostics.

Measured on the committed TR9 run, the realised objective inaccuracy of the
production settings is ~2e-6 p.u., which is where the default --tol comes from.

Usage (from a normal terminal, anywhere):
    py -3 compare_FOR_runs.py OLD.csv NEW.csv
    py -3 compare_FOR_runs.py FOR_rolling_micro_baseline_preE.csv FOR_rolling.csv
    py -3 compare_FOR_runs.py OLD.csv NEW.csv --tol 1e-5

Bare file names are looked up in the repo root. Exit code is 0 when every
direction agrees on proj within --tol and no solve status changed, 1 otherwise.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

KEY = ["now", "angle_deg"]
OK_STATUS = ("Optimal", "LocallyOptimal")


def _resolve(p):
    """Allow bare names; look in the repo root."""
    p = Path(p)
    if p.is_absolute() or p.exists():
        return p
    return ROOT / p.name


def _load(path):
    df = pd.read_csv(path, skipinitialspace=True)
    df.columns = [c.strip() for c in df.columns]
    df["status"] = df["status"].astype(str).str.strip()
    missing = [c for c in KEY + ["P", "Q", "proj", "status", "time"] if c not in df.columns]
    if missing:
        sys.exit("%s: missing column(s) %s" % (path, ", ".join(missing)))
    return df


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("old", help="baseline CSV (the run you are comparing against)")
    ap.add_argument("new", help="new CSV (the run produced by the change)")
    ap.add_argument("--tol", type=float, default=2e-6,
                    help="max allowed |delta proj| in p.u. (default 2e-6)")
    ap.add_argument("--top", type=int, default=10,
                    help="how many worst rows to list (default 10)")
    args = ap.parse_args()

    old_p, new_p = _resolve(args.old), _resolve(args.new)
    for p in (old_p, new_p):
        if not p.exists():
            sys.exit("not found: %s" % p)

    old, new = _load(old_p), _load(new_p)
    print("baseline : %s   (%d rows)" % (old_p, len(old)))
    print("new      : %s   (%d rows)" % (new_p, len(new)))

    m = old.merge(new, on=KEY, suffixes=("_old", "_new"), how="outer", indicator=True)
    only_old = (m["_merge"] == "left_only").sum()
    only_new = (m["_merge"] == "right_only").sum()
    if only_old or only_new:
        print("\n!! row sets differ: %d only in baseline, %d only in new" % (only_old, only_new))
    m = m[m["_merge"] == "both"].copy()
    if m.empty:
        sys.exit("no rows in common - are these the same study case?")

    for c in ("P", "Q", "proj"):
        m["d" + c] = (m[c + "_new"] - m[c + "_old"]).abs()

    # ---- solve status ------------------------------------------------------
    bad_old = ~m["status_old"].isin(OK_STATUS)
    bad_new = ~m["status_new"].isin(OK_STATUS)
    flipped = m[bad_old != bad_new]
    print("\nstatus     : baseline %d/%d optimal, new %d/%d optimal"
          % ((~bad_old).sum(), len(m), (~bad_new).sum(), len(m)))
    if len(flipped):
        print("             %d direction(s) changed solvability:" % len(flipped))
        for _, r in flipped.head(args.top).iterrows():
            print("               now=%-3d angle=%-6.1f  %s -> %s"
                  % (r["now"], r["angle_deg"], r["status_old"], r["status_new"]))

    # Rows that failed in either run carry 0,0,0 and would pollute the deltas.
    cmp_rows = m[~bad_old & ~bad_new]
    skipped = len(m) - len(cmp_rows)
    if skipped:
        print("             (%d row(s) excluded from the numeric comparison)" % skipped)

    # ---- the invariant: proj ----------------------------------------------
    dproj = cmp_rows["dproj"]
    print("\nproj       : max |delta| = %.3e p.u.   (tolerance %.1e)" % (dproj.max(), args.tol))
    print("             median %.3e, %d/%d rows over tolerance"
          % (dproj.median(), (dproj > args.tol).sum(), len(cmp_rows)))

    over = cmp_rows[cmp_rows["dproj"] > args.tol].nlargest(args.top, "dproj")
    if len(over):
        print("\n  worst directions by |delta proj|:")
        print("    now  angle   proj_old      proj_new      |dproj|     |dP| kW   |dQ| kW")
        for _, r in over.iterrows():
            print("    %-4d %-6.1f %13.6f %13.6f  %.3e %9.2f %9.2f"
                  % (r["now"], r["angle_deg"], r["proj_old"], r["proj_new"],
                     r["dproj"], r["dP"] * 1000, r["dQ"] * 1000))

    # ---- diagnostics: P/Q sliding along a flat face ------------------------
    dpq = (cmp_rows["dP"] ** 2 + cmp_rows["dQ"] ** 2) ** 0.5
    print("\nP,Q slide  : max %.2f kW, median %.2f kW  (informational - a legitimate"
          % (dpq.max() * 1000, dpq.median() * 1000))
    print("             flat-face slide does NOT fail this check)")
    slid = cmp_rows.assign(dpq=dpq)
    slid = slid[(slid["dpq"] * 1000 > 1.0) & (slid["dproj"] <= args.tol)]
    if len(slid):
        print("             %d direction(s) moved >1 kW while proj held within tolerance"
              % len(slid))
        for _, r in slid.nlargest(min(args.top, len(slid)), "dpq").iterrows():
            print("               now=%-3d angle=%-6.1f  slide %7.2f kW  (dproj %.1e)"
                  % (r["now"], r["angle_deg"], r["dpq"] * 1000, r["dproj"]))

    # ---- what this was really about: wall-clock ---------------------------
    t_old, t_new = old["time"].sum(), new["time"].sum()
    print("\nsolve time : baseline %8.1f s   new %8.1f s   (%+.1f%%)"
          % (t_old, t_new, (t_new - t_old) / t_old * 100 if t_old else 0))
    print("             per solve: %.2f s -> %.2f s over %d directions"
          % (t_old / max(len(old), 1), t_new / max(len(new), 1), len(new)))
    print("             NOTE: this column is FOR_VertexCont.SolutionTime only. It does")
    print("             not include the MainExecution solve or any scaffolding, so it")
    print("             will barely move for a data-loading change - time the run itself.")

    failed = (dproj > args.tol).any() or len(flipped) > 0 or only_old or only_new
    print("\n%s" % ("FAIL - see above" if failed else "PASS - proj reproduces within tolerance, no status change"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
