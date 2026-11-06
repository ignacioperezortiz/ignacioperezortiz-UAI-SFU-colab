"""Compare a rebuild with reference files; prints PASS/FAIL per data file, per 3-D figure and per slide.

  JSON  value by value; ignores "generated" (time stamp) and compares "lane" fields by their last folder name only
        (older copies hold an absolute path there)
  PNG   bytes; when they differ, pixels
  PPTX  every part of the package, slide by slide: slide XML, notes, chart XML, embedded workbooks (cell values and
        every part but the workbook's own docProps, which carry its save time) and pictures; then the parts shared by
        all slides. Only docProps/core.xml (the deck's save time) is ignored.

Usage (from the repository root):
  python -B scripts/paper1/figures/meeting_2026_10_16/check_reproduction.py --ref-pptx FILE [--ref DIR] [--out DIR]
    --ref-pptx FILE  the reference deck
    --ref DIR        reference JSONs and PNGs, in the repository layout (results/paper1-fairness-2026-10) or the deck's
                     own (data\\*.json, data_tulio\\*.json, data_tulio\\*.png); optional
    --out DIR        the rebuild: <out>/<deck>.pptx, <out>/figures/*.png, <out>/data/*.json (default out/)
    --data DIR       JSONs to check instead of <out>/data (e.g. the committed results/paper1-fairness-2026-10)
    --pptx FILE      rebuilt deck to check instead of <out>/<deck>.pptx
Exit status 1 if anything fails.
"""
import argparse
import io
import json
import math
import posixpath
import re
import sys
import zipfile
from pathlib import Path

import numpy as np
from lxml import etree
from PIL import Image

import paths

R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
X_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
FOLLOW = ("/chart", "/image", "/notesSlide", "/package", "/oleObject")   # relationship types owned by one slide
IGNORED = {"docProps/core.xml"}


# ---------------------------------------------------------------- JSON
def walk(a, b, p="", out=None):
    """Differences between two parsed JSON values, ignoring 'generated' and the folder part of 'lane'."""
    out = [] if out is None else out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k == "generated":
                continue
            if k not in a or k not in b:
                out.append(f"{p}/{k}: only in {'reference' if k in a else 'rebuild'}")
            elif k == "lane" and isinstance(a[k], str) and isinstance(b[k], str):
                if re.split(r"[\\/]", a[k])[-1] != re.split(r"[\\/]", b[k])[-1]:
                    out.append(f"{p}/{k}: {a[k]!r} vs {b[k]!r}")
            else:
                walk(a[k], b[k], f"{p}/{k}", out)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{p}: length {len(a)} vs {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            walk(x, y, f"{p}[{i}]", out)
    elif type(a) is not type(b) and not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
        out.append(f"{p}: {a!r:.60} vs {b!r:.60}")
    elif isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        pass
    elif a != b:
        out.append(f"{p}: {a!r:.60} vs {b!r:.60}")
    return out


def find(ref, candidates):
    for c in candidates:
        if (ref / c).is_file():
            return ref / c
    return None


def check_json(ref, data):
    rows = []
    for (folder, deck_name), name in paths.JSON_NAMES.items():
        a = find(ref, [name, f"data/{name}", f"{folder}/{deck_name}"]) if ref else None
        b = data / name
        if a is None or not b.is_file():
            rows.append((name, "SKIP", "no reference" if a is None else "not rebuilt"))
            continue
        ra, rb = a.read_bytes(), b.read_bytes()
        d = walk(json.loads(ra), json.loads(rb))
        how = "bytes identical" if ra == rb else ("identical but for line ends" if ra.replace(b"\r\n", b"\n") == rb.replace(b"\r\n", b"\n")
                                                 else "same values (bytes differ)")
        rows.append((name, "FAIL" if d else "PASS", f"{len(d)} differences, first: {d[0]}" if d else how))
    return rows


# ---------------------------------------------------------------- PNG
def same_image(a, b):
    """(identical?, how) for two encoded images: bytes first, then decoded pixels."""
    if a == b:
        return True, "bytes identical"
    x, y = np.asarray(Image.open(io.BytesIO(a)).convert("RGBA")), np.asarray(Image.open(io.BytesIO(b)).convert("RGBA"))
    if x.shape != y.shape:
        return False, f"size {x.shape[1]}x{x.shape[0]} vs {y.shape[1]}x{y.shape[0]}"
    n = int((x != y).any(axis=-1).sum())
    return n == 0, "pixels identical (bytes differ)" if n == 0 else f"{n} pixels differ"


def check_png(ref, figs):
    rows = []
    for name in paths.FIGURES:
        a = find(ref, [name, f"figures/{name}", f"data_tulio/{name}"]) if ref else None
        b = figs / name
        if a is None or not b.is_file():
            rows.append((name, "SKIP", "no reference" if a is None else "not rebuilt"))
            continue
        ok, how = same_image(a.read_bytes(), b.read_bytes())
        rows.append((name, "PASS" if ok else "FAIL", how))
    return rows


# ---------------------------------------------------------------- PPTX
def rels_of(z, part):
    """[(type, target part)] of a package part."""
    d, f = posixpath.split(part)
    rp = posixpath.join(d, "_rels", f + ".rels")
    if rp not in z.namelist():
        return []
    out = []
    for r in etree.fromstring(z.read(rp)).iter(f"{{{PKG_REL}}}Relationship"):
        if r.get("TargetMode") == "External":
            continue
        out.append((r.get("Type"), posixpath.normpath(posixpath.join(d, r.get("Target")))))
    return out


def slide_parts(z):
    """Slide part names in presentation order."""
    pres = etree.fromstring(z.read("ppt/presentation.xml"))
    rid = {r.get("Id"): posixpath.normpath(posixpath.join("ppt", r.get("Target")))
           for r in etree.fromstring(z.read("ppt/_rels/presentation.xml.rels")).iter(f"{{{PKG_REL}}}Relationship")}
    return [rid[s.get(f"{{{R_NS}}}id")] for s in pres.iter("{http://schemas.openxmlformats.org/presentationml/2006/main}sldId")]


def owned(z, slide):
    """Parts that belong to one slide: {part: kind}, kind in slide, notes, chart, workbook, picture."""
    parts, todo = {slide: "slide"}, [slide]
    while todo:
        p = todo.pop()
        for t, target in rels_of(z, p):
            if not t.endswith(FOLLOW) or target in parts:
                continue
            kind = {"/chart": "chart", "/image": "picture", "/notesSlide": "notes"}.get(t[t.rfind("/"):], "workbook")
            parts[target] = kind
            if kind in ("chart", "notes") or kind == "workbook" and not target.endswith(".xlsx"):
                todo.append(target)
    for p in list(parts):                                   # each part's .rels goes with it
        d, f = posixpath.split(p)
        rp = posixpath.join(d, "_rels", f + ".rels")
        if rp in z.namelist():
            parts[rp] = parts[p]
    return parts


def cells(xlsx):
    """{sheet part: {cell ref: value}} of a workbook, from its XML (no spreadsheet library needed)."""
    z = zipfile.ZipFile(io.BytesIO(xlsx))
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        shared = ["".join(si.itertext()) for si in etree.fromstring(z.read("xl/sharedStrings.xml")).iter(f"{{{X_NS}}}si")]
    out = {}
    for n in sorted(x for x in z.namelist() if x.startswith("xl/worksheets/sheet")):
        vals = {}
        for c in etree.fromstring(z.read(n)).iter(f"{{{X_NS}}}c"):
            v = c.find(f"{{{X_NS}}}v")
            t = c.get("t")
            if t == "s" and v is not None:
                vals[c.get("r")] = shared[int(v.text)]
            elif t == "inlineStr":
                vals[c.get("r")] = "".join(c.itertext())
            elif v is not None:
                vals[c.get("r")] = v.text
        out[n] = vals
    return out


def same_workbook(a, b):
    if a == b:
        return True, "bytes identical"
    za, zb = zipfile.ZipFile(io.BytesIO(a)), zipfile.ZipFile(io.BytesIO(b))
    na = {n for n in za.namelist() if not n.startswith("docProps/")}
    nb = {n for n in zb.namelist() if not n.startswith("docProps/")}
    bad = sorted(na ^ nb) + sorted(n for n in na & nb if za.read(n) != zb.read(n))
    try:
        if cells(a) != cells(b):
            return False, "cell values differ"
    except (IndexError, ValueError, etree.XMLSyntaxError) as e:
        return False, f"cells unreadable ({e})"
    return not bad, "cell values and parts identical (docProps differ)" if not bad else f"parts differ: {bad[:3]}"


def title(xml):
    """Text of the largest run on the slide (the title)."""
    best, size = "", -1
    for r in etree.fromstring(xml).iter(f"{{{A_NS}}}r"):
        pr, t = r.find(f"{{{A_NS}}}rPr"), r.find(f"{{{A_NS}}}t")
        sz = int(pr.get("sz", 0)) if pr is not None else 0
        if t is not None and t.text and t.text.strip() and sz > size:
            best, size = t.text.strip(), sz
    return best


def check_pptx(ref, new):
    za, zb = zipfile.ZipFile(ref), zipfile.ZipFile(new)
    rows, seen = [], set()
    sa, sb = slide_parts(za), slide_parts(zb)
    if sa != sb:
        rows.append(("-", "slide list", "FAIL", f"{len(sa)} vs {len(sb)} slides"))
    for i, s in enumerate(sa, start=1):
        pa = owned(za, s)
        pb = owned(zb, s) if s in zb.namelist() else {}
        seen |= set(pa) | set(pb)
        kinds = {"slide": [0, 0], "notes": [0, 0], "chart": [0, 0], "workbook": [0, 0], "picture": [0, 0]}
        notes, soft = [], set()                             # soft: passed, but not byte for byte
        for p in sorted(set(pa) | set(pb)):
            k = pa.get(p) or pb.get(p)
            if p.endswith(".rels"):
                ok = p in za.namelist() and p in zb.namelist() and za.read(p) == zb.read(p)
            elif p not in za.namelist() or p not in zb.namelist():
                ok = False
                notes.append(f"{p} only in {'reference' if p in za.namelist() else 'rebuild'}")
            elif k == "workbook":
                ok, how = same_workbook(za.read(p), zb.read(p))
                if not ok:
                    notes.append(f"{posixpath.basename(p)}: {how}")
                elif how != "bytes identical":
                    soft.add("workbooks: docProps (save time) differ")
            elif k == "picture":
                ok, how = same_image(za.read(p), zb.read(p))
                if not ok:
                    notes.append(f"{posixpath.basename(p)}: {how}")
                elif how != "bytes identical":
                    soft.add("pictures: same pixels, bytes differ")
            else:
                ok = za.read(p) == zb.read(p)
                if not ok:
                    notes.append(f"{posixpath.basename(p)} differs")
            if not p.endswith(".rels"):
                kinds[k][0] += 1
            kinds[k][1] += 0 if ok else 1
            if p.endswith(".rels") and not ok:
                notes.append(f"{posixpath.basename(p)} differs")
        fails = sum(v[1] for v in kinds.values())
        what = ", ".join(f"{v[0]} {k}{'s' if v[0] != 1 else ''}" for k, v in kinds.items() if v[0] and k not in ("slide", "notes"))
        detail = (what + "; " if what else "") + ("; ".join(notes[:3]) if fails else
                                                  "identical" + (f" ({'; '.join(sorted(soft))})" if soft else ""))
        rows.append((str(i), title(za.read(s))[:46], "FAIL" if fails else "PASS", detail))
    rest = sorted((set(za.namelist()) | set(zb.namelist())) - seen - IGNORED)
    bad = [p for p in rest if p not in za.namelist() or p not in zb.namelist() or za.read(p) != zb.read(p)]
    rows.append(("-", "shared parts (layouts, masters, theme, ...)", "FAIL" if bad else "PASS",
                 f"{len(rest)} parts, " + ("all identical" if not bad else f"differ: {bad[:4]}")))
    core = "identical" if za.read("docProps/core.xml") == zb.read("docProps/core.xml") else "differs (save time), ignored"
    rows.append(("-", "docProps/core.xml", "INFO", core))
    return rows


# ---------------------------------------------------------------- report
def table(head, rows):
    w = [max(len(str(r[i])) for r in [head] + rows) for i in range(len(head))]
    w[-1] = min(w[-1], 90)
    line = "  ".join("-" * x for x in w)
    print("  ".join(str(h).ljust(x) for h, x in zip(head, w)))
    print(line)
    for r in rows:
        print("  ".join(str(c).ljust(x) for c, x in zip(r, w)))
    print()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    ap.add_argument("--ref-pptx", help="reference deck")
    ap.add_argument("--ref", help="folder with the reference JSONs and PNGs")
    ap.add_argument("--pptx", help="rebuilt deck (default <out>/" + paths.DECK_PPTX + ")")
    paths.add_args(ap, data=True, figures=True)
    a = ap.parse_args()
    paths.use(a)
    ref = Path(a.ref).resolve() if a.ref else None
    data = paths.data_in() if a.data else paths.out_dir() / "data"
    fails = 0
    if ref:
        print(f"reference JSON/PNG: {ref}\nchecked JSON:       {data}\nchecked PNG:        {paths.figures_in()}\n")
        rows = check_json(ref, data)
        table(("data file", "result", "detail"), rows)
        rows2 = check_png(ref, paths.figures_in())
        table(("3-D figure", "result", "detail"), rows2)
        fails += sum(r[1] == "FAIL" for r in rows + rows2)
    if a.ref_pptx:
        new = Path(a.pptx) if a.pptx else paths.out_dir() / paths.DECK_PPTX
        print(f"reference deck: {Path(a.ref_pptx).resolve()}\nchecked deck:   {new.resolve()}\n")
        rows = check_pptx(a.ref_pptx, new)
        table(("slide", "title", "result", "detail"), rows)
        fails += sum(r[2] == "FAIL" for r in rows)
    if not (ref or a.ref_pptx):
        ap.error("give --ref-pptx and/or --ref")
    print("ALL PASS" if not fails else f"{fails} FAIL")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
