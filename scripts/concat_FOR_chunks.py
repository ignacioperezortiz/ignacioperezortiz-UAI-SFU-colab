r"""Stitch the CSVs of a chunked rolling-FOR run back into one set of files.

A chunked run splits the 48 periods across several AimmsCmd processes, so that each
starts with an unfragmented address space -- see docs/parallel-sweep-address-space.md.
Every chunk writes under its own RollFileSuffix; this puts them back together.

It concatenates the three per-run CSVs (the vertex file, the soc file and the fair
file), keeping one header, and it CHECKS the joint before writing:

    * every chunk must be non-empty and carry the same header
    * the periods of chunk k+1 must start exactly where chunk k stopped -- a gap means
      a chunk died early, an overlap means the chunk bounds were wrong
    * every period present must carry the same number of rows as the others

Any of those fails loudly rather than producing a file that looks complete.

Usage (from anywhere; bare suffixes are resolved against the repo root):
    py -3 concat_FOR_chunks.py _TR3_c1 _TR3_c2 --out _TR3_chunked
    py -3 concat_FOR_chunks.py _full_c1 _full_c2 _full_c3 _full_c4 --out _full_k3

Writes FOR_rolling<out>.csv, FOR_rolling_soc<out>.csv, FOR_rolling_fair<out>.csv.
Exit code is 0 when the joint is clean, 1 otherwise.
"""
import argparse
import csv
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# stem -> the column that holds the period number
FAMILIES = [
    ("FOR_rolling%s.csv", "now"),
    ("FOR_rolling_soc%s.csv", "now"),
    ("FOR_rolling_fair%s.csv", "now"),
]


def _read(path):
    with io.open(path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.reader(fh))
    if not rows:
        sys.exit("ERROR: %s is empty" % path)
    return rows[0], rows[1:]


def _periods(header, body, col, path):
    try:
        i = header.index(col)
    except ValueError:
        sys.exit("ERROR: %s has no '%s' column" % (path, col))
    out = []
    for r in body:
        try:
            out.append(int(r[i].strip()))
        except (IndexError, ValueError):
            sys.exit("ERROR: %s has a row whose '%s' is not a number: %r" % (path, col, r[:3]))
    return out


def concat_family(pattern, col, suffixes, out_suffix):
    header = None
    body = []
    seen = []          # (chunk suffix, first period, last period)

    for sfx in suffixes:
        path = ROOT / (pattern % sfx)
        if not path.exists():
            sys.exit("ERROR: missing chunk file %s" % path)
        h, b = _read(path)
        if not b:
            sys.exit("ERROR: %s has a header but no rows -- that chunk produced nothing" % path)
        if header is None:
            header = h
        elif h != header:
            sys.exit("ERROR: %s has a different header from the first chunk" % path)

        per = _periods(h, b, col, path)
        lo, hi = min(per), max(per)
        if per != sorted(per):
            sys.exit("ERROR: %s is not in period order" % path)
        if seen and lo != seen[-1][2] + 1:
            sys.exit("ERROR: chunk %s starts at period %d, but chunk %s ended at %d -- %s"
                     % (sfx, lo, seen[-1][0], seen[-1][2],
                        "gap" if lo > seen[-1][2] + 1 else "overlap"))
        seen.append((sfx, lo, hi))
        body.extend(b)

    # every period should carry the same number of rows
    counts = {}
    for p in _periods(header, body, col, "the joint"):
        counts[p] = counts.get(p, 0) + 1
    sizes = sorted(set(counts.values()))
    if len(sizes) > 1:
        odd = sorted(p for p, c in counts.items() if c != max(sizes))
        sys.exit("ERROR: %s -- periods %s do not have %d rows like the rest"
                 % (pattern % out_suffix, odd[:10], max(sizes)))

    out = ROOT / (pattern % out_suffix)
    # Match what AIMMS writes -- UTF-8 with a BOM, CRLF line endings -- so a stitched
    # file is byte-comparable with a single-process run, not merely equal in content.
    with io.open(out, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, lineterminator="\r\n")
        w.writerow(header)
        w.writerows(body)

    span = ", ".join("%s=%d-%d" % s for s in seen)
    print("  %-34s %5d rows, periods %d-%d  (%s)"
          % (out.name, len(body), seen[0][1], seen[-1][2], span))
    return len(body)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("suffixes", nargs="+", help="chunk suffixes, in period order")
    ap.add_argument("--out", required=True, help="suffix for the stitched files")
    a = ap.parse_args()

    if len(a.suffixes) < 2:
        sys.exit("ERROR: give at least two chunk suffixes")
    if a.out in a.suffixes:
        sys.exit("ERROR: --out must differ from every chunk suffix")

    print("stitching %s -> %s" % (" + ".join(a.suffixes), a.out))
    for pattern, col in FAMILIES:
        concat_family(pattern, col, a.suffixes, a.out)
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
