"""Check the Stage 0 fairness runs against case A.

Usage (from the repo root):
    py -3 scripts/check_fairness.py                # micro: A vs L1 vs L2
    py -3 scripts/check_fairness.py --suffix _TR9  # TR9

Verifies three things:
  1. Nesting  proj_L1 <= proj_L2 <= proj_A  at every vertex (a defect if it fails).
  2. That the constraint holds: util == zeta in every aggregator.
  3. How much the FOR contracted, and whether that matches what case A predicted.
"""
import argparse
import csv
import os
import statistics as st
import sys

# Contraction counting: how far apart two projections must be before the vertex counts as
# "affected". Same value as compare_FOR_runs.py.
TOL_PROJ = 2e-6

# Nesting. This is a CROSS-FORMULATION comparison -- two different programs, each solved
# independently -- not a rerun of the same one, so it needs its own tolerance. The model runs
# with Feasibility_Tolerance := 1.0e-3 (OPF.ams), so 1e-3 is the only bound the solver actually
# guarantees and the only one that would be provable. 1e-4 is the deliberately strict choice:
# 10x finer than that guarantee (the same reasoning already used for TOL_FAIR below), 16x above
# the worst excess observed on TR9 (6e-6 p.u. = 6 W; the proj column is printed to 6 decimals,
# i.e. 1 W per digit), and three orders of magnitude below the smallest defect worth catching --
# a real contraction is ~3e-1 p.u. Going to 1e-5 would leave only 1.7x of margin over measured
# noise and would flag it again.
TOL_NEST = 1e-4

# Fairness equality. Checking it finer than the solver's guarantee reports solver noise as if it
# were a formulation defect: measured on L1, 3 of 1728 rows land above 1e-5 and none above 1e-4,
# all at a single vertex where the dispatch is zero. 1e-4 is 10x stricter than the guarantee, so
# it catches a real error without raising false alarms.
TOL_FAIR = 1e-4


def load_main(path):
    out = {}
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            out[(int(r["now"]), float(r["angle_deg"]))] = {
                "proj": float(r["proj"]),
                "status": r["status"].strip(),
            }
    return out


def load_fair(path):
    out = {}
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            k = (int(r["now"]), float(r["angle_deg"]))
            out.setdefault(k, []).append({
                "agg": r["aggregator"].strip(),
                "zeta": float(r["zeta"]),
                "util": float(r["util"]),
                "umin": float(r["util_min"]),
                "umax": float(r["util_max"]),
                "cap": float(r["cap_pu"]),
                "sump": float(r["sumP_pu"]),
            })
    return out


def check_nesting(a, b, name_a, name_b):
    """proj_b <= proj_a at every shared vertex."""
    viol = []
    for k in sorted(set(a) & set(b)):
        if a[k]["status"] != "Optimal" or b[k]["status"] != "Optimal":
            continue
        if b[k]["proj"] > a[k]["proj"] + TOL_NEST:
            viol.append((k, b[k]["proj"] - a[k]["proj"]))
    print("  %-28s %s" % (
        "proj(%s) <= proj(%s)" % (name_b, name_a),
        "OK" if not viol else "VIOLATED at %d vertices (max excess %.3e)" % (
            len(viol), max(v for _, v in viol)),
    ))
    for k, v in sorted(viol, key=lambda x: -x[1])[:5]:
        print("        now=%d ang=%.0f  excess=%.3e" % (k[0], k[1], v))
    return not viol


def check_constraint(fair, mode):
    """util must equal zeta in every aggregator; in L1, umin==umax as well."""
    bad_util, bad_spread, zmax = [], [], 0.0
    for k, rows in fair.items():
        for r in rows:
            zmax = max(zmax, abs(r["zeta"]))
            if r["cap"] <= 0:
                continue
            if abs(r["util"] - r["zeta"]) > TOL_FAIR:
                bad_util.append((k, r["agg"], r["util"] - r["zeta"]))
            if mode == 1 and (r["umax"] - r["umin"]) > TOL_FAIR:
                bad_spread.append((k, r["agg"], r["umax"] - r["umin"]))
    print("  %-28s %s" % ("util == zeta", "OK" if not bad_util
          else "FAILS in %d rows (max %.2e)" % (len(bad_util), max(abs(d) for _, _, d in bad_util))))
    if mode == 1:
        print("  %-28s %s" % ("L1: umin == umax", "OK" if not bad_spread
              else "FAILS in %d rows (max %.2e)" % (len(bad_spread), max(d for _, _, d in bad_spread))))
    print("  %-28s %.4f  %s" % ("max |zeta|", zmax, "OK" if zmax <= 1 + TOL_FAIR else "OUT OF BOUNDS"))
    return not bad_util and not bad_spread


def contraction(a, b):
    """Relative projection loss, over the vertices where proj_A is significant."""
    rel, absol = [], []
    for k in sorted(set(a) & set(b)):
        if a[k]["status"] != "Optimal" or b[k]["status"] != "Optimal":
            continue
        d = a[k]["proj"] - b[k]["proj"]
        absol.append(d)
        if abs(a[k]["proj"]) > 1e-4:
            rel.append(d / abs(a[k]["proj"]))
    if not absol:
        return
    binding = sum(1 for d in absol if d > TOL_PROJ)
    print("  contraction: median %.3e p.u. | max %.3e p.u. | affected vertices %d/%d (%.1f%%)"
          % (st.median(absol), max(absol), binding, len(absol), 100 * binding / len(absol)))
    if rel:
        print("               relative: median %.2f%% | max %.2f%%"
              % (100 * st.median(rel), 100 * max(rel)))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--suffix", default="", help="transformer suffix, e.g. _TR9")
    p.add_argument("--root", default=".", help="repo root")
    args = p.parse_args()
    s = args.suffix

    files = {
        "A":  ("FOR_rolling%s.csv" % s,          "FOR_rolling_fair%s.csv" % s),
        "L1": ("FOR_rolling%s_fairL1.csv" % s,   "FOR_rolling_fair%s_fairL1.csv" % s),
        "L2": ("FOR_rolling%s_fairL2.csv" % s,   "FOR_rolling_fair%s_fairL2.csv" % s),
    }

    main_d, fair_d = {}, {}
    for tag, (fm, ff) in files.items():
        pm, pf = os.path.join(args.root, fm), os.path.join(args.root, ff)
        if not os.path.exists(pm):
            print("[missing] %s  -> skipping case %s" % (fm, tag))
            continue
        d = load_main(pm)
        if not d:
            # the file exists but is empty: the run is either in progress (AIMMS has
            # already created the file with the BOM) or it aborted. Evaluating it
            # would yield a vacuous OK.
            print("[in progress or empty] %s -> skipping case %s" % (fm, tag))
            continue
        main_d[tag] = d
        if os.path.exists(pf):
            ff_d = load_fair(pf)
            if ff_d:
                fair_d[tag] = ff_d
        print("[ok] %s (%d vertices)" % (fm, len(main_d[tag])))

    ok = True
    for tag, mode in (("L1", 1), ("L2", 2)):
        if tag not in main_d:
            continue
        print("\n=== %s (FairMode=%d) ===" % (tag, mode))
        if tag in fair_d:
            ok &= check_constraint(fair_d[tag], mode)
        if "A" in main_d:
            ok &= check_nesting(main_d["A"], main_d[tag], "A", tag)
            contraction(main_d["A"], main_d[tag])

    if "L1" in main_d and "L2" in main_d:
        print("\n=== nesting between levels ===")
        ok &= check_nesting(main_d["L2"], main_d["L1"], "L2", "L1")

    print("\n%s" % ("ALL OK" if ok else "FAILURES - see above"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
