"""Extract the A / L1..L4 cases of the rolling FOR into a compact JSON and report the
AREA contraction, which is the metric check_fairness.py does not cover.

Usage (from the repo root):
    py -3 scripts/make_viz_data.py                  # micro test bed (no suffix)
    py -3 scripts/make_viz_data.py --suffix _TR9    # TR9 production

Why this exists separately from check_fairness.py: that script measures the contraction
of the PROJECTION per direction; this one measures the AREA of the region. On the micro
bed the area fell much more than the projection (22.2% median against ~0), because the
FOR has flat faces where the optimum slides to a fair point at no projection cost.
Looking at the projection alone would lead to the conclusion that fairness is nearly
free, and it is not. Report both.
"""
import argparse
import csv
import json
import os
import sys

# Test bed by suffix: what changes between the micro bed and production.
BEDS = {
    "": {
        "bed": "TR9_two (micro): 12 prosumers, 21 loads, 21 buses",
        "nBatt": 12,
        "baseline": "FOR_rolling_baseline_micro.csv",
    },
    "_TR9": {
        "bed": "TR9 (production): 90 prosumers, reduced network with the rest passive",
        "nBatt": 90,
        "baseline": "FOR_rolling_baseline.csv",
    },
}
BATT_MAX_P_KW = 3.6   # homogeneous fleet: 3.6 kW across the 1,216 batteries


# L1/L2 allocate the battery, L3/L4 the prosumer's whole exchange. Listed once so the three
# places that iterate over levels cannot drift apart. Levels with no run on disk are skipped,
# so this is safe to leave in place mid-campaign.
LEVELS = ("L1", "L2", "L3", "L4")


def paths(suffix):
    """(tag -> main csv, tag -> fairness csv) for the given suffix."""
    cases = [("A", "FOR_rolling%s.csv" % suffix)]
    cases += [(lv, "FOR_rolling%s_fair%s.csv" % (suffix, lv)) for lv in LEVELS]
    fair = {"A": "FOR_rolling_fair%s.csv" % suffix}
    for lv in LEVELS:
        fair[lv] = "FOR_rolling_fair%s_fair%s.csv" % (suffix, lv)
    return cases, fair


def load(root, fn):
    d = {}
    with open(os.path.join(root, fn), encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            now = int(r["now"])
            d.setdefault(now, []).append({
                "ang": float(r["angle_deg"]),
                "P": float(r["P"]) * 1000.0,   # p.u. (Sb=1MW) -> kW
                "Q": float(r["Q"]) * 1000.0,
                "proj": float(r["proj"]) * 1000.0,
                "st": r["status"].strip(),
            })
    for now in d:
        d[now].sort(key=lambda x: x["ang"])
    return d


def shoelace(pts):
    a = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def load_zeta(root, fn):
    """zeta by (period, angle)."""
    z = {}
    with open(os.path.join(root, fn), encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            z.setdefault(int(r["now"]), {})[float(r["angle_deg"])] = float(r["zeta"])
    return z


def median(xs):
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--suffix", default="", help="transformer suffix, e.g. _TR9")
    p.add_argument("--root", default=".", help="repo root (defaults to the cwd)")
    p.add_argument("--out", default=None, help="JSON path (defaults to scripts/for_data<suffix>.json)")
    args = p.parse_args()

    root, suffix = args.root, args.suffix
    if suffix not in BEDS:
        print("WARNING: suffix '%s' has no declared test bed; using the micro one for the metadata" % suffix)
    bed = BEDS.get(suffix, BEDS[""])
    cases, fair = paths(suffix)

    data, absent = {}, []
    for tag, fn in cases:
        if not os.path.exists(os.path.join(root, fn)):
            absent.append((tag, fn))
            continue
        data[tag] = load(root, fn)
        print("[ok] %-32s %d periods" % (fn, len(data[tag])))
    for tag, fn in absent:
        print("[missing] %-28s -> skipping case %s" % (fn, tag))

    if "A" not in data:
        print("\nERROR: without case A there is nothing to compare against. Aborting.")
        return 1

    zeta = {t: load_zeta(root, f) for t, f in fair.items()
            if os.path.exists(os.path.join(root, f))}

    periods = sorted(data["A"].keys())
    angles = [v["ang"] for v in data["A"][periods[0]]]

    out = {
        "meta": {
            "bed": bed["bed"],
            "suffix": suffix,
            "units": "kW / kVAr at the PCC, positive = network -> feeder",
            "angles": angles,
            "periods": periods,
            "nBatt": bed["nBatt"],
            "namePlateKW": round(bed["nBatt"] * BATT_MAX_P_KW, 1),
        },
        "cases": {},
        "series": {},
    }

    for tag in data:
        per = {}
        for now in periods:
            rows = data[tag][now]
            # A vertex the solver could not place writes P = Q = proj = 0.000000. That is a
            # placeholder, NOT an operating point, and it must never reach the page: joining
            # twelve of them draws a region collapsed onto the origin and reports a 100% area
            # loss, which reads as "fairness shrank the region to nothing" when the truth is
            # that no region exists for that period. m=3 does this legitimately -- see the
            # constraint comment in OPF.ams -- so the null has to be carried, not patched over.
            if all(r["st"] == "Optimal" for r in rows):
                pts = [[round(r["P"], 3), round(r["Q"], 3)] for r in rows]
                per[str(now)] = {
                    "pts": pts,
                    "area": round(shoelace(pts), 3),
                    "proj": [round(r["proj"], 4) for r in rows],
                    "allOpt": True,
                }
            else:
                st = sorted({r["st"] for r in rows if r["st"] != "Optimal"})
                per[str(now)] = {"pts": None, "area": None, "proj": None,
                                 "allOpt": False, "status": ", ".join(st)}
        out["cases"][tag] = per
        out["series"]["area_" + tag] = [per[str(n)]["area"] for n in periods]
        gaps = [n for n in periods if not per[str(n)]["allOpt"]]
        if gaps:
            print("[gap] %-3s no region in %d period(s): %s"
                  % (tag, len(gaps), ", ".join(str(n) for n in gaps)))

    for tag in LEVELS:
        if tag not in data:
            continue
        # null wherever either side has no region: a loss against something that does not exist
        # is not zero and not 100%, it is undefined, and the page has to show a gap.
        loss, lossmax, arealoss = [], [], []
        for n in periods:
            a = out["cases"]["A"][str(n)]["proj"]
            b = out["cases"][tag][str(n)]["proj"]
            if a is None or b is None:
                loss.append(None)
                lossmax.append(None)
                arealoss.append(None)
                continue
            d = [x - y for x, y in zip(a, b)]
            loss.append(round(sum(d) / len(d), 4))
            lossmax.append(round(max(d), 4))
            aA = out["cases"]["A"][str(n)]["area"]
            arealoss.append(round(100.0 * (aA - out["cases"][tag][str(n)]["area"])
                                  / max(aA, 1e-9), 2))
        out["series"]["projLossMean_" + tag] = loss
        out["series"]["projLossMax_" + tag] = lossmax
        out["series"]["areaLossPct_" + tag] = arealoss
        if tag in zeta:
            out["series"]["zeta_" + tag] = [
                [round(zeta[tag][n][a], 6) for a in angles] for n in periods
            ]

    # ---- B(t) trajectory with the batteries idle, for the deviation view ----
    # ALIGNMENT: the sweep of step `now` offers the region for the TARGET period
    # target = (now mod 48) + 1, because the window is rotated and the service block is
    # slot 2. The baseline is computed over the day WITHOUT rotation, indexed by absolute
    # period. Subtracting B(now) instead of B(target) would shift the reference by half an
    # hour and would ruin the zero.
    bp = os.path.join(root, bed["baseline"])
    if os.path.exists(bp):
        babs = {}
        with open(bp, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                babs[int(r["period"])] = (float(r["P"]) * 1000.0, float(r["Q"]) * 1000.0,
                                          r["status"].strip())
        n_per = len(periods)
        bad = [p_ for p_, v in babs.items() if v[2] not in ("Optimal", "LocallyOptimal")]
        missing = [((n % n_per) + 1) for n in periods if ((n % n_per) + 1) not in babs]
        if missing:
            print("WARNING: periods missing from the baseline:", missing[:8], "-> no baseline emitted")
        else:
            out["baseline"] = {str(n): [round(babs[(n % n_per) + 1][0], 3),
                                        round(babs[(n % n_per) + 1][1], 3)] for n in periods}
            print("baseline loaded from %s  (%d periods, %d non-optimal)"
                  % (bed["baseline"], len(babs), len(bad)))
            if bad:
                print("   WARNING: non-optimal periods in the baseline:", bad[:8])
            dP = [out["cases"]["A"][str(n)]["pts"][i][0] - out["baseline"][str(n)][0]
                  for n in periods if out["cases"]["A"][str(n)]["pts"]
                  for i in range(len(angles))]
            if dP:
                print("   dP range (case A): %.1f .. %.1f kW" % (min(dP), max(dP)))
    else:
        print("no baseline (%s does not exist) -> absolute region only, no deviation view"
              % bed["baseline"])

    dest = args.out or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "for_data%s.json" % suffix)
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))

    print("\nwritten : %s  (%.1f KB)" % (dest, os.path.getsize(dest) / 1024))
    print("bed     : %s" % bed["bed"])
    print("periods : %d | angles: %d | aggregate nameplate: %.1f kW"
          % (len(periods), len(angles), out["meta"]["namePlateKW"]))
    print()
    aA = [v for v in out["series"]["area_A"] if v is not None]
    print("case A area (kW*kVAr): min %.1f  max %.1f" % (min(aA), max(aA)))
    for tag in LEVELS:
        k = "areaLossPct_" + tag
        if k not in out["series"]:
            continue
        # periods with no region are null, and are reported as a gap rather than folded into
        # the statistics -- averaging over them would understate or invent a contraction.
        pc = [v for v in out["series"][k] if v is not None]
        if not pc:
            print("area loss %s: no period has a region" % tag)
            continue
        gaps = sum(1 for v in out["series"][k] if v is None)
        print("area loss %s: median %.2f%%  max %.2f%%  (period of the max: %d)%s"
              % (tag, median(pc), max(pc),
                 periods[out["series"][k].index(max(pc))],
                 "  [%d period(s) with no region, excluded]" % gaps if gaps else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
