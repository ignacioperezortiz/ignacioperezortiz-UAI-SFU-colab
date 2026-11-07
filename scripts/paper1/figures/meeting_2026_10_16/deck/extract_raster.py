"""Network figure (Fig. 4) from the original 600-dpi raster, and its two panels.

Panel boundary (found from the row profile of the image):
  rows    0-1207 : panel (a) MV-LV network, label "(a) ..." at x 10-587, y 6-57
  rows 1208-1214 : empty
  rows 1215-1267 : label "(b) LV network of TR4"
  rows 1268-1294 : empty
  rows 1295-2518 : panel (b) grey box + legend
Separate panels are delivered without their "(a)/(b)" labels (as fig3a/fig3b).

Source: the network figure of the publication script, uk_mv_lv_network_single_tr44.png (shared project folder
05_UAI-SFU-COLAB, 04-publication-script/methodology-so-far/).
Writes network_full.png, network_mv.png, network_tr4.png into <out>/img. The deck uses network_mv.png and
network_tr4.png (copies in img/).
Run:  python -B extract_raster.py --png FILE [--out DIR]
"""
import argparse
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))     # package root: paths.py
import paths  # noqa: E402

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--png", required=True, help="uk_mv_lv_network_single_tr44.png")
paths.add_args(ap)
ARGS = paths.use(ap.parse_args())
SRC = ARGS.png
OUT = str(paths.img_out())
MARGIN_PX = 30
INK_THRESHOLD = 252
DPI = 600

src = Image.open(SRC)
alpha = np.asarray(src.getchannel("A")) if src.mode == "RGBA" else None
if alpha is not None:
    print("alpha min/max", alpha.min(), alpha.max(), "fully opaque:", bool(alpha.min() == 255))
# flatten onto white (identical pixels if the image is opaque)
rgb = Image.new("RGB", src.size, "white")
rgb.paste(src, mask=src.getchannel("A") if src.mode == "RGBA" else None)
a = np.asarray(rgb)
ink = a.min(axis=2) < INK_THRESHOLD


def save(img, name):
    img.save(os.path.join(OUT, name), dpi=(DPI, DPI), optimize=True)
    print(f"{name:20s} {img.width}x{img.height}px")


def trim_pad(arr, name):
    m = arr.min(axis=2) < INK_THRESHOLD
    ys, xs = np.where(m)
    crop = Image.fromarray(arr[ys.min():ys.max() + 1, xs.min():xs.max() + 1])
    out = Image.new("RGB", (crop.width + 2 * MARGIN_PX, crop.height + 2 * MARGIN_PX), "white")
    out.paste(crop, (MARGIN_PX, MARGIN_PX))
    save(out, name)


# full figure: original pixels, full resolution
save(rgb, "network_full.png")

# ---- panel (a): rows above the first empty band
empty = ~ink.any(axis=1)
gap_a = next(y for y in range(1100, 1300) if empty[y])           # first empty row after (a)
panel_a = a[:gap_a].copy()
# remove the "(a) UK MV-LV network" label: it is the only ink in x<620, y<70
lab = ink[:70, :620]
ys, xs = np.where(lab)
assert not ink[:90, 600:940].any(), "unexpected ink next to the label"
assert not ink[60:90, :620].any(), "unexpected ink below the label"
print("label (a) bbox x", xs.min(), xs.max(), "y", ys.min(), ys.max(), "| panel (a) rows 0 -", gap_a - 1)
panel_a[: ys.max() + 3, : xs.max() + 3] = 255
trim_pad(panel_a, "network_mv.png")

# ---- panel (b): rows after the second empty band (below the "(b)" label)
runs, y = [], gap_a
while y < len(empty):
    if empty[y]:
        y0 = y
        while y < len(empty) and empty[y]:
            y += 1
        runs.append((y0, y - 1))
    y += 1
second_gap = runs[1]                                              # band between label (b) and grey box
print("empty bands after (a):", runs[:3], "-> panel (b) starts at row", second_gap[1] + 1)
trim_pad(a[second_gap[1] + 1:].copy(), "network_tr4.png")
