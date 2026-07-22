r"""Validate a FOR export against Prof. Luis's base workbook.

Compares two AIMMS .xls workbooks sheet-by-sheet, cell-by-cell, aligning
rows by their row-header label (the first column) so a different write
order does not register as a difference.

Usage (from a normal terminal):
    py -3 compare_FOR_to_NCQ.py
        -> compares FOR_ref_25.xls  vs  NC_Q_25.xls   (the validation proof)

    py -3 compare_FOR_to_NCQ.py FOR_v1_25.xls
        -> compares that vertex file vs NC_Q_25.xls    (expected to DIFFER;
           a FOR vertex is a different operating point, not the base case)

Reference must match within solver tolerance. Vertex files are for
inspection: the report just shows how far each vertex moves from the base.
"""
import sys
from pathlib import Path

import xlrd

DESK = Path(r"C:\Users\LAPTOP-01\Desktop")


def _resolve(p):
    """Allow bare names; look on Desktop and in the AIMMS folder."""
    p = Path(p)
    if p.is_absolute():
        return p
    for cand in (DESK / p.name,
                 DESK / "FOR_AIMMS2" / "AIMMS_LGchecked" / p.name,
                 DESK / "FOR_AIMMS2" / "AIMMS_LGchecked" / "MainProject" / p.name):
        if cand.exists():
            return cand
    return p


# Usage:
#   py -3 compare_FOR_to_NCQ.py                            -> FOR_ref vs NC_Q
#   py -3 compare_FOR_to_NCQ.py <new>                      -> <new>  vs NC_Q
#   py -3 compare_FOR_to_NCQ.py <new> <reference>          -> <new>  vs <reference>
NEW = _resolve(sys.argv[1]) if len(sys.argv) > 1 else _resolve("FOR_ref_25.xls")
BASE = _resolve(sys.argv[2]) if len(sys.argv) > 2 else _resolve("NC_Q_25.xls")

TOL = 1e-6           # abs tolerance for "match" (solver-level agreement)
REL = 5e-3           # rel tolerance (still tighter than the model's own
                     # MIP_Relative_Optimality_Tolerance = 1e-2; absorbs
                     # downstream solver noise on derived quantities).


def load(path):
    """sheet -> {row_label: [floats]}  plus a flag for header-only sheets."""
    bk = xlrd.open_workbook(str(path))
    out = {}
    for sh in bk.sheets():
        rows = {}
        has_label = sh.ncols and isinstance(sh.cell_value(1 if sh.nrows > 1 else 0, 0), str) \
            and sh.cell_value(0, 0) == ""
        for r in range(sh.nrows):
            cells = [sh.cell_value(r, c) for c in range(sh.ncols)]
            if has_label:
                key = str(cells[0])
                vals = cells[1:]
            else:
                key = f"__row{r}"
                vals = cells
            # keep only numeric payload
            nums = []
            for v in vals:
                try:
                    nums.append(float(v))
                except (TypeError, ValueError):
                    nums.append(None)
            rows[key] = nums
        out[sh.name] = rows
    return out


def main():
    if not BASE.exists():
        sys.exit(f"missing reference: {BASE}")
    if not NEW.exists():
        sys.exit(f"missing file to check: {NEW}\n"
                 f"(run RunFOR_4Vertices in AIMMS first)")

    print(f"REFERENCE : {BASE}")
    print(f"CHECKING  : {NEW}")
    print(f"tol abs={TOL:g}  rel={REL:g}")
    print("=" * 78)

    a = load(BASE)
    b = load(NEW)

    only_a = sorted(set(a) - set(b))
    only_b = sorted(set(b) - set(a))
    if only_a:
        print(f"sheets only in reference : {only_a}")
    if only_b:
        print(f"sheets only in checked   : {only_b}")

    grand_ok = True
    hdr = f"{'sheet':<26}{'rows':>7}{'cells':>9}{'max|d|':>14}" \
          f"{'>tol':>8}  worst-cell"
    print(hdr)
    print("-" * 78)
    for name in [s for s in a if s in b]:
        ra, rb = a[name], b[name]
        keys = [k for k in ra if k in rb]
        ncell = 0
        maxd = 0.0
        nbad = 0
        worst = ""
        for k in keys:
            va, vb = ra[k], rb[k]
            for j in range(min(len(va), len(vb))):
                x, y = va[j], vb[j]
                if x is None or y is None:
                    continue
                ncell += 1
                d = abs(x - y)
                scale = max(1.0, abs(x))
                bad = d > TOL and d > REL * scale
                if bad:
                    nbad += 1
                if d > maxd:
                    maxd = d
                    worst = f"{k!r} col{j + 2} ref={x:.8g} new={y:.8g}"
        status = "OK " if nbad == 0 else "DIFF"
        if nbad:
            grand_ok = False
        print(f"{name:<26}{len(keys):>7}{ncell:>9}{maxd:>14.3e}"
              f"{nbad:>8}  {status} {worst if nbad else ''}")

    print("=" * 78)
    is_validation = NEW.name.startswith("FOR_ref") or NEW.name.startswith("OUR_")
    if is_validation:
        if grand_ok and not only_a and not only_b:
            print(f"PASS - {NEW.name} reproduces {BASE.name} within tolerance.")
            print("       The reorganized model + Excel writer are faithful for this case.")
        else:
            print(f"FAIL - {NEW.name} differs from {BASE.name}. Investigate the")
            print("       'DIFF' sheets above (worst-cell points to the value).")
    else:
        print("Vertex / non-validation file: differences from the base case are EXPECTED")
        print("(it is a different operating point). Use the per-sheet max|d|")
        print("to see how far this dispatch moves.")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
