"""Build the interactive visualisation of the FOR under fairness, for any test bed.

Usage (from the repo root, after make_viz_data.py):
    py -3 scripts/build_viz.py                   # micro bed -> results/viz/FOR_fairness_micro.html
    py -3 scripts/build_viz.py --suffix _TR9     # TR9       -> results/viz/FOR_fairness_TR9.html

Takes scripts/for_viz_template.html and injects the JSON produced by make_viz_data.py,
plus the text and the two figures that depend on the test bed. The resulting page is
self-contained: it loads nothing from the network, so it opens with a double click.

The two footer figures are NOT written by hand (in the 30-Jul version they were, and
that is why the template did not work for TR9):
  __SPAN_REGION__ = median width in P of the region over the course of the day
  __SPAN_DAY__    = travel in P of the feeder during the day (case A)
Both come out of the JSON, so they cannot fall out of step with the data they illustrate.
"""
import argparse
import io
import json
import math
import os
import statistics as st
import sys

# NOTE: "short" and "desc" are page content, not script output: they are substituted into
# for_viz_template.html, so they must read as English prose alongside the rest of the page.
BEDS = {
    "": {
        "tag": "TR9_two",
        "short": "TR9_two micro test bed",
        "desc": "TR9_two micro test bed, 12 prosumers; the rest of the feeder enters as passive load.",
        "base_file": "FOR_rolling_baseline_micro.csv",
        "base_proc": "RunMicro_Baseline",
        "out": "FOR_fairness_micro.html",
    },
    "_TR9": {
        "tag": "TR9",
        "short": "TR9 production",
        "desc": ("Full TR9, 90 prosumers split across 3 aggregators (28/32/30); the other "
                 "eight transformers enter as passive load on the MV side."),
        "base_file": "FOR_rolling_baseline.csv",
        "base_proc": "RunFOR_Rolling_Baseline",
        "out": "FOR_fairness_TR9.html",
    },
}


def kw(x):
    """Format in kW with an English-convention thousands separator (3,959 kW)."""
    if abs(x) >= 1000:
        return format(x, ",.0f") + " kW"
    return "%.0f kW" % x


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--suffix", default="", help="transformer suffix, e.g. _TR9")
    p.add_argument("--json", default=None, help="JSON path (defaults to scripts/for_data<suffix>.json)")
    p.add_argument("--out", default=None, help="path of the output HTML")
    args = p.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(here)
    if args.suffix not in BEDS:
        print("ERROR: no test bed declared for suffix '%s'. Add it to BEDS." % args.suffix)
        return 1
    bed = BEDS[args.suffix]

    jpath = args.json or os.path.join(here, "for_data%s.json" % args.suffix)
    if not os.path.exists(jpath):
        print("ERROR: %s is missing. Run first: py -3 scripts/make_viz_data.py --suffix %s"
              % (jpath, args.suffix or '""'))
        return 1
    data = json.load(io.open(jpath, encoding="utf-8"))

    # footer figures, derived from the data
    per = data["meta"]["periods"]
    A = data["cases"]["A"]
    spans = []
    allP = []
    for n in per:
        P = [pt[0] for pt in A[str(n)]["pts"]]
        spans.append(max(P) - min(P))
        allP.extend(P)
    span_region = st.median(spans)
    span_day = max(allP) - min(allP)

    tpl = io.open(os.path.join(here, "for_viz_template.html"), encoding="utf-8").read()
    html = (tpl
            .replace("__BED_TAG__", bed["tag"])
            .replace("__BED_SHORT__", bed["short"])
            .replace("__BED_DESC__", bed["desc"])
            .replace("__BASE_FILE__", bed["base_file"])
            .replace("__BASE_PROC__", bed["base_proc"])
            .replace("__SPAN_REGION__", kw(span_region))
            .replace("__SPAN_DAY__", kw(span_day))
            .replace("__DATA__", json.dumps(data, separators=(",", ":"))))

    if "__" in html.replace("__DATA__", ""):
        import re
        left = sorted(set(re.findall(r"__[A-Z_]+__", html)))
        if left:
            print("WARNING: placeholders left unfilled: %s" % left)

    dest = args.out or os.path.join(repo, "results", "viz", bed["out"])
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    io.open(dest, "w", encoding="utf-8", newline="").write(html)

    cases = [t for t in ("A", "L1", "L2") if t in data["cases"]]
    print("written : %s  (%.1f KB)" % (dest, os.path.getsize(dest) / 1024))
    print("bed     : %s" % data["meta"]["bed"])
    print("cases   : %s" % ", ".join(cases))
    print("deviation view: %s" % ("YES" if data.get("baseline") else "NO (baseline missing)"))
    print("footer  : region %s | travel over the day %s" % (kw(span_region), kw(span_day)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
