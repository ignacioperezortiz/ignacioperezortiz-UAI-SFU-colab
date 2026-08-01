"""Timing table for the rolling-FOR runs.

Usage (from the repo root):
    py -3 scripts/run_timing.py                      # the known TR9 files
    py -3 scripts/run_timing.py a.csv b.csv          # whichever files are passed in

The CSV `time` column is FOR_VertexCont.SolutionTime: ONLY the vertex solve, 576 per
run. It does not include the per-period baseline (48 MinImports solves), nor the data
loading, nor the I/O. That is why "solver" < "wall": in the TR9 case A it was 8440.7 s
of solver inside 3h40 of wall-clock (~64%).

The wall-clock is taken from the file mtime (= when AIMMS closed it) minus the start
time, which is entered by hand with --inicio "YYYY-MM-DD HH:MM".
"""
import argparse
import csv
import datetime as dt
import os
import statistics as st
import sys

DEFAULTS = [
    "FOR_rolling_TR9.csv",            # case A (reference, 29-Jul)
    "FOR_rolling_TR9_fairL1.csv",     # C1 across prosumers
    "FOR_rolling_TR9_fairL2.csv",     # C1 across aggregators
]

REF_A_SOLVER = 8440.7   # s, TR9 case A measured on 29-Jul


def leer(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("csvs", nargs="*", default=None)
    p.add_argument("--inicio", default=None,
                   help='start time of the LAST run, "YYYY-MM-DD HH:MM"')
    args = p.parse_args()
    archivos = args.csvs if args.csvs else DEFAULTS

    print("| file | n | status | solver total | vs case A | median | max | end (mtime) |")
    print("|---|---|---|---|---|---|---|---|")
    for f in archivos:
        if not os.path.exists(f):
            print("| %s | - | *does not exist yet* | | | | | |" % f)
            continue
        filas = leer(f)
        if not filas:
            print("| %s | 0 | *empty: run in progress* | | | | | |" % f)
            continue
        t = [float(r["time"]) for r in filas]
        est = {}
        for r in filas:
            s = r["status"].strip()
            est[s] = est.get(s, 0) + 1
        est_txt = " ".join("%s:%d" % kv for kv in sorted(est.items()))
        tot = sum(t)
        rel = "%+.1f%%" % (100 * (tot / REF_A_SOLVER - 1))
        fin = dt.datetime.fromtimestamp(os.path.getmtime(f))
        print("| %s | %d | %s | %.1f s (%s) | %s | %.2f s | %.2f s | %s |" % (
            f, len(filas), est_txt, tot, hms(tot), rel,
            st.median(t), max(t), fin.strftime("%d-%m %H:%M:%S")))

        if args.inicio and f == archivos[-1]:
            ini = dt.datetime.strptime(args.inicio, "%Y-%m-%d %H:%M")
            wall = (fin - ini).total_seconds()
            print("\nWall-clock of %s: %s (start %s -> end %s)" % (
                f, hms(wall), ini.strftime("%d-%m %H:%M"), fin.strftime("%d-%m %H:%M")))
            print("Solver = %.1f%% of the wall." % (100 * tot / wall))


def hms(s):
    s = int(round(s))
    return "%dh %02dm %02ds" % (s // 3600, (s % 3600) // 60, s % 60)


if __name__ == "__main__":
    sys.exit(main())
