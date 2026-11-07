"""Extract vector figures (Figs. 1-3) from the compiled draft as high-dpi PNGs.

Method
  1. Search region per figure = column band between page header / body text and
     the caption top (caption located by its text block "Fig. N.").
  2. Element boxes inside the region = vector drawings (inflated by half the
     stroke width) + text spans. Their union is the figure bbox.
  3. Render the bbox (inflated by a few pt, never beyond the region) at DPI,
     trim to the actual ink, check the ink never touches the rendered edge
     (=> nothing cut off), and pad with a uniform white margin.

Source: the compiled draft of 13-Oct-2026, vista-previa-v63-con-fairness-2026-10-13.pdf (shared project folder
05_UAI-SFU-COLAB, 00-documentation/escritura/decision-criterios-fairness/fuente/subseccion-fairness/).
Writes fig1_framework.png, fig2_qcp.png, fig3_p2_pq.png, fig3a.png, fig3b.png into <out>/img (needs PyMuPDF).
The deck uses fig1_framework.png and fig3a.png (copies in img/).
Run:  python -B extract_vector.py --pdf FILE [--out DIR]
"""
import argparse
import os
import sys
from pathlib import Path

import fitz
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))     # package root: paths.py
import paths  # noqa: E402

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--pdf", required=True, help="vista-previa-v63-con-fairness-2026-10-13.pdf")
paths.add_args(ap)
ARGS = paths.use(ap.parse_args())
PDF = ARGS.pdf
OUT = str(paths.img_out())
DPI = 600
MARGIN_PX = 30          # white margin added around the ink (~0.05 in at 600 dpi)
INK_THRESHOLD = 252     # pixel counts as ink if any channel is below this


# ---------------------------------------------------------------- helpers
def caption_top(page, label):
    """Top y of the caption text block that starts with e.g. 'Fig. 1.'."""
    for b in page.get_text("blocks"):
        if b[4].strip().startswith(label):
            return b[1]
    raise ValueError(f"caption {label!r} not found")


def element_boxes(page, region):
    """Boxes of drawings and text spans whose centre lies inside region."""
    boxes = []
    for d in page.get_drawings():
        r = fitz.Rect(d["rect"])
        half = (d.get("width") or 0) / 2
        r = fitz.Rect(r.x0 - half, r.y0 - half, r.x1 + half, r.y1 + half)
        c = fitz.Point((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)
        if c in region:
            boxes.append(("draw", r))
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                if not span["text"].strip():
                    continue
                r = fitz.Rect(span["bbox"])
                c = fitz.Point((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)
                if c in region:
                    boxes.append(("text", r))
    return boxes


def union(boxes):
    u = fitz.Rect()
    for _, r in boxes:
        u |= r
    return u


def render_trimmed(page, bbox, region, name, pad_pt=3.0):
    """Render bbox (+pad, clipped to region), trim to ink, add white margin."""
    clip = fitz.Rect(bbox.x0 - pad_pt, bbox.y0 - pad_pt,
                     bbox.x1 + pad_pt, bbox.y1 + pad_pt) & region
    pix = page.get_pixmap(dpi=DPI, clip=clip, alpha=False)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    a = np.asarray(img)
    ink = a.min(axis=2) < INK_THRESHOLD
    ys, xs = np.where(ink)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    touches = []
    if y0 == 0: touches.append("top")
    if x0 == 0: touches.append("left")
    if y1 == a.shape[0] - 1: touches.append("bottom")
    if x1 == a.shape[1] - 1: touches.append("right")
    crop = img.crop((x0, y0, x1 + 1, y1 + 1))
    out = Image.new("RGB", (crop.width + 2 * MARGIN_PX, crop.height + 2 * MARGIN_PX), "white")
    out.paste(crop, (MARGIN_PX, MARGIN_PX))
    path = os.path.join(OUT, name)
    out.save(path, dpi=(DPI, DPI), optimize=True)
    print(f"{name:20s} {out.width}x{out.height}px  clip={[round(v, 1) for v in clip]}"
          f"  ink-touches-edge={touches or 'none'}")
    return out


def x_gaps(boxes, lo, hi, min_gap=1.0):
    """Gaps in the x-coverage of boxes, restricted to (lo, hi)."""
    iv = sorted((r.x0, r.x1) for _, r in boxes)
    merged = [list(iv[0])]
    for a, b in iv[1:]:
        if a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    gaps = [(merged[i][1], merged[i + 1][0]) for i in range(len(merged) - 1)]
    return [g for g in gaps if g[1] - g[0] >= min_gap and lo < g[0] < hi]


# ---------------------------------------------------------------- main
doc = fitz.open(PDF)
RIGHT_COL = (305.0, 575.0)   # right column x-band (left column text ends at ~301 pt)
HEADER_BOTTOM = 45.0         # running header sits at y ~ 25-35 pt

# ---- Fig. 1: framework diagram (page 1, right column, below the author block)
page = doc[0]
cap = caption_top(page, "Fig. 1.")
region = fitz.Rect(RIGHT_COL[0], 150.0, RIGHT_COL[1], cap - 1.5)
boxes = element_boxes(page, region)
bb = union(boxes)
print("Fig1 caption top", round(cap, 1), "bbox", [round(v, 1) for v in bb], "n", len(boxes))
render_trimmed(page, bb, region, "fig1_framework.png")

# ---- Fig. 2: QCP-OPF representation (page 3, right column top)
page = doc[2]
cap = caption_top(page, "Fig. 2.")
region = fitz.Rect(RIGHT_COL[0], HEADER_BOTTOM, RIGHT_COL[1], cap - 1.5)
boxes = element_boxes(page, region)
bb = union(boxes)
print("Fig2 caption top", round(cap, 1), "bbox", [round(v, 1) for v in bb], "n", len(boxes))
render_trimmed(page, bb, region, "fig2_qcp.png")

# ---- Fig. 3: P2 in the P-Q plane (page 4, right column top)
page = doc[3]
cap = caption_top(page, "Fig. 3.")
region = fitz.Rect(RIGHT_COL[0], HEADER_BOTTOM, RIGHT_COL[1], cap - 1.5)
boxes = element_boxes(page, region)
bb = union(boxes)
print("Fig3 caption top", round(cap, 1), "bbox", [round(v, 1) for v in bb], "n", len(boxes))
render_trimmed(page, bb, region, "fig3_p2_pq.png")

# separate panels: drop the sub-captions "(a) ..."/"(b) ..." (they sit on the last
# line of the figure), then split at the x-gap between the two panels
sub_top = min(r.y0 for k, r in boxes if k == "text" and r.y0 > 150)
graph = [(k, r) for k, r in boxes if r.y1 <= sub_top - 0.5]
gaps = x_gaps(graph, bb.x0 + 0.3 * bb.width, bb.x0 + 0.7 * bb.width)
print("Fig3 subcaption top", round(sub_top, 1), "x-gaps between panels", gaps)
g0, g1 = max(gaps, key=lambda g: g[1] - g[0])
split = (g0 + g1) / 2
left = [(k, r) for k, r in graph if r.x1 <= split]
right = [(k, r) for k, r in graph if r.x0 >= split]
assert len(left) + len(right) == len(graph), "an element straddles the split"
reg_a = fitz.Rect(region.x0, region.y0, split, sub_top - 0.5)
reg_b = fitz.Rect(split, region.y0, region.x1, sub_top - 0.5)
render_trimmed(page, union(left), reg_a, "fig3a.png")
render_trimmed(page, union(right), reg_b, "fig3b.png")
