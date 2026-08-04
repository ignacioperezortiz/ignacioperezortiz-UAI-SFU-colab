"""Check the Stage 0 fairness runs against case A.

Usage (from the repo root):
    py -3 scripts/check_fairness.py                # micro: A vs L1..L4
    py -3 scripts/check_fairness.py --suffix _TR9  # TR9

Four criteria, in two pairs. L1/L2 allocate the BATTERY, L3/L4 the prosumer's whole EXCHANGE
with the grid; within each pair the first is between prosumers and the second between
aggregators. Cases that have not been run are skipped, so this works mid-campaign.

Verifies three things:
  1. Nesting  proj_L1 <= proj_L2 <= proj_A  at every vertex (a defect if it fails), and the
     same for L3 <= L4 <= A.
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
                "n": int(float(r["n_batt"])),
            })
    return out


def participation(fair):
    """Periods where the criterion bound fewer prosumers than its own maximum.

    From m=3 on, n_batt counts the PARTICIPATING fleet: a prosumer sitting on its SOC floor has
    no export to offer and is left out of the sharing rule rather than dragging it down. The
    exclusion is a modelling result worth reporting per period, not an implementation detail --
    it is what stops one empty battery from making a whole period infeasible.
    """
    tot = {}
    for k, rows in fair.items():
        tot[k] = sum(r["n"] for r in rows)
    if not tot:
        return None
    full = max(tot.values())
    short, unpinned = {}, set()
    for (now, _), n in tot.items():
        if n < full:
            short[now] = min(short.get(now, n), n)
        if n == 0:
            # Nobody left on the equality. zeta is then a free column appearing only in one-sided
            # rows, with no objective coefficient, so ANY sufficiently slack value satisfies them:
            # what the solver reports is wherever the barrier stopped, not something the problem
            # determines. It looks like a normal number and is not one -- do not read it, do not
            # plot it. Seen on the micro bed at FairSOCTol=1e-3, periods 21-23.
            unpinned.add(now)
    return full, short, unpinned


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
    """util must equal zeta in every aggregator; at prosumer level, umin==umax as well."""
    prosumer_level = mode in (1, 3)      # 1 and 3 pin every prosumer; 2 and 4 only the totals
    exchange = mode >= 3                 # 3 and 4 allocate the exchange, not the battery
    bad_util, bad_spread = [], []
    zmin, zmax = 0.0, 0.0
    for k, rows in fair.items():
        for r in rows:
            zmin, zmax = min(zmin, r["zeta"]), max(zmax, r["zeta"])
            if r["cap"] <= 0:
                continue
            if abs(r["util"] - r["zeta"]) > TOL_FAIR:
                bad_util.append((k, r["agg"], r["util"] - r["zeta"]))
            if prosumer_level and (r["umax"] - r["umin"]) > TOL_FAIR:
                bad_spread.append((k, r["agg"], r["umax"] - r["umin"]))
    print("  %-28s %s" % ("util == zeta", "OK" if not bad_util
          else "FAILS in %d rows (max %.2e)" % (len(bad_util), max(abs(d) for _, _, d in bad_util))))
    if prosumer_level:
        print("  %-28s %s" % ("umin == umax", "OK" if not bad_spread
              else "FAILS in %d rows (max %.2e)" % (len(bad_spread), max(d for _, _, d in bad_spread))))

    # The bound is DERIVED, never imposed: no row of the model enforces it, at any level.
    #
    # m=1/m=2: |BattP_Balance| <= BattMaxP holds per battery and FairCap = BattMaxP, so dividing
    # the fairness equality by the capacity carries the bound onto zeta (through the triangle
    # inequality at level 2). Two-sided, and a value outside means the premise broke -- not that
    # a constraint was violated.
    #
    # m=3/m=4: only ONE side survives. s_i = BattMaxP + PVsize bounds the EXPORT (PV at full
    # output plus the battery at rated power), so zeta <= 1 still holds; but the import side is
    # load + BattMaxP, and a prosumer whose load exceeds its own PV plus battery can legitimately
    # push zeta below -1. So the lower end is REPORTED, not asserted.
    if exchange:
        print("  %-28s %.4f  %s" % ("max zeta (derived <= 1)", zmax,
              "OK" if zmax <= 1 + TOL_FAIR else "DERIVATION BROKEN"))
        print("  %-28s %.4f  %s" % ("min zeta (no bound)", zmin,
              "" if zmin >= -1 else "below -1: expected, import side is unbounded"))
    else:
        print("  %-28s %.4f  %s" % ("max |zeta| (derived <= 1)", max(abs(zmin), abs(zmax)),
              "OK" if max(abs(zmin), abs(zmax)) <= 1 + TOL_FAIR else "DERIVATION BROKEN"))
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

    files = {"A": ("FOR_rolling%s.csv" % s, "FOR_rolling_fair%s.csv" % s)}
    for lv in ("L1", "L2", "L3", "L4"):
        files[lv] = ("FOR_rolling%s_fair%s.csv" % (s, lv),
                     "FOR_rolling_fair%s_fair%s.csv" % (s, lv))

    main_d, fair_d, nonoptimal = {}, {}, {}
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
        # Non-optimal vertices must be surfaced HERE, at load time. They used to pass unmentioned
        # because every check below skips them, so a case could report "ALL OK" while a whole
        # period had failed to solve -- which is exactly what m=3 did on the micro bed (period 45,
        # all 12 directions). Under m=1/m=2 a non-optimal vertex would be a defect, since Zeta=0
        # is always admissible there; under m=3/m=4 it is a legitimate result, because the passive
        # net load enters the row as a per-prosumer constant and no single Zeta need fit everyone.
        # Either way it is never something to pass over in silence.
        nonopt = [k for k, v in d.items() if v["status"] != "Optimal"]
        if nonopt:
            per = sorted(set(k[0] for k in nonopt))
            print("[ok] %s (%d vertices)  ** %d NON-OPTIMAL in periods %s **"
                  % (fm, len(d), len(nonopt), ", ".join(str(p) for p in per)))
            nonoptimal[tag] = (len(nonopt), per)
        else:
            print("[ok] %s (%d vertices)" % (fm, len(d)))

    ok = True
    for tag, mode in (("L1", 1), ("L2", 2), ("L3", 3), ("L4", 4)):
        if tag not in main_d:
            continue
        print("\n=== %s (FairMode=%d) ===" % (tag, mode))
        if tag in fair_d:
            ok &= check_constraint(fair_d[tag], mode)
            part = participation(fair_d[tag])
            if part:
                full, short, unpinned = part
                if unpinned:
                    print("  %-28s %d periods with an EMPTY equality set: %s"
                          % ("zeta UNPINNED", len(unpinned),
                             ", ".join(str(p) for p in sorted(unpinned))))
                    print("        the criterion does not bind there and the logged zeta is an"
                          " artefact, not a result")
                if short:
                    worst = min(short.values())
                    print("  %-28s %d of %d prosumers at the tightest period; %d periods affected"
                          % ("participation", worst, full, len(short)))
                    print("        periods: %s"
                          % ", ".join("%d(%d)" % (p, n) for p, n in sorted(short.items())[:12]))
                else:
                    print("  %-28s %d of %d, every period" % ("participation", full, full))
        if "A" in main_d:
            ok &= check_nesting(main_d["A"], main_d[tag], "A", tag)
            contraction(main_d["A"], main_d[tag])

    # Within each pair the prosumer-level criterion implies the aggregator-level one: summing the
    # per-prosumer equality over an aggregator reproduces the aggregate equality with the same
    # zeta. So L1 nests inside L2 and L3 inside L4. ACROSS pairs there is no such implication --
    # they constrain different quantities -- so L1 vs L3 is deliberately not checked here.
    for inner, outer in (("L1", "L2"), ("L3", "L4")):
        if inner in main_d and outer in main_d:
            print("\n=== nesting between levels (%s inside %s) ===" % (inner, outer))
            ok &= check_nesting(main_d[outer], main_d[inner], outer, inner)

    if nonoptimal:
        print("\nNON-OPTIMAL VERTICES")
        for tag, (n, per) in sorted(nonoptimal.items()):
            print("  %-3s %d vertices, periods %s"
                  % (tag, n, ", ".join(str(p) for p in per)))
        print("  Every check above SKIPS these, so read the verdict with them in mind.")

    if not ok:
        verdict = "FAILURES - see above"
    elif nonoptimal:
        verdict = "CHECKS OK - but some vertices did not solve, see above"
    else:
        verdict = "ALL OK"
    print("\n%s" % verdict)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
