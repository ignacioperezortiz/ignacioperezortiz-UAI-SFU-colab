"""3-D figure for slide R7: F_{k+1} over the requested slots 06:00-19:30, with and without TSO export requests.

Reads service_requests.json (--data; the deck's data_tulio\\service.json), writes <out>/figures/fig_3d_service.png.
Two panels side by side, same axes:
  left  : no request (grey wireframe) vs export requests, guarantee on (orange #C8551B)
  right : no request (grey wireframe) vs export requests, guarantee relaxed (pale orange #F3D9CB, dashed #C8551B slices)
Slices at 07:30, 12:30, 16:30, 19:30 are drawn thicker. No in-image legend: the slide draws it natively.
Camera and fonts match fig_3d_criteria.py (ortho, elev 20, azim -58, box 1:1:1.3). A thin vertical line marks the all-idle point (0, 0).
Usage: python -B fig_3d_service.py [--compact] [--data DIR] [--out DIR]
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import proj3d
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))     # package root: paths.py
import paths  # noqa: E402

ARGS = paths.cli(__doc__, data=True, flags=("--compact",))
S = json.loads(paths.deck_json("data_tulio", "service.json").read_text(encoding="utf-8"))
INK, INK_MID, GREY = "#14354A", "#3D637B", "#9AA8B2"
ORANGE, PALE = "#C8551B", "#F3D9CB"
DASH = (0, (4, 2))
FS_TICK, FS_AXLAB, FS_TITLE = 11, 11.5, 13
LW_CUT = 2.0
FIGSIZE = (12.3, 4.0)                 # same per-panel axes size as fig_3d_criteria.py
AX_W, AX_B, AX_H = 0.2132, -0.03, 1.03
COMPACT = ARGS.compact                # --compact: small gap between panels (for a narrower placement)
AX_LEFT = (0.03, 0.40) if COMPACT else (0.03, 0.66)   # default: wide gap so the image is ~11.8 x 3.5 in
OUT = paths.figures_out() / ("fig_3d_service_compact.png" if COMPACT else "fig_3d_service.png")
CUTS = ["07:30", "12:30", "16:30", "19:30"]

plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Segoe UI", "Arial", "DejaVu Sans"],
                     "font.size": 10, "axes.edgecolor": INK_MID, "text.color": INK,
                     "axes.labelcolor": INK, "xtick.color": INK_MID, "ytick.color": INK_MID})

times = S["times"]
hours = [int(t[:2]) + int(t[3:]) / 60 for t in times]


def closed(poly):
    return poly + [poly[0]]


def loft(ax, polys, face, alpha, edge=None):
    quads = []
    for k in range(len(polys) - 1):
        a, b = polys[k], polys[k + 1]
        za, zb = hours[k], hours[k + 1]
        n = len(a)
        for i in range(n):
            j = (i + 1) % n
            quads.append([(a[i][0], a[i][1], za), (a[j][0], a[j][1], za), (b[j][0], b[j][1], zb), (b[i][0], b[i][1], zb)])
    pc = Poly3DCollection(quads, facecolor=face, alpha=alpha, edgecolor="none", linewidth=0)
    ax.add_collection3d(pc)


def slices(ax, polys, color, lw_thin, lw_cut, alpha_thin=1.0, z_off=0.0, ls="-"):
    for k, p in enumerate(polys):
        c = closed(p)
        cut = times[k] in CUTS
        ax.plot([q[0] for q in c], [q[1] for q in c], [hours[k] + z_off] * len(c), color=color,
                lw=lw_cut if cut else lw_thin, alpha=1.0 if cut else alpha_thin, ls=ls if cut else "-",
                solid_joinstyle="round", dash_joinstyle="round")


def generators(ax, polys, color, lw, alpha):
    n = len(polys[0])
    for i in range(n):
        ax.plot([p[i][0] for p in polys], [p[i][1] for p in polys], hours, color=color, lw=lw, alpha=alpha)


def panel(ax, key, face, edge, title, ls="-"):
    ax.computed_zorder = False          # draw in call order: grey wireframe, surface, service slices, idle line
    nr = S["cases"]["no_request"]["polygons"]
    sv = S["cases"][key]["polygons"]
    # no request: faint grey wireframe (slices + generators), cut slices a little stronger
    generators(ax, nr, GREY, 0.5, 0.55)
    slices(ax, nr, GREY, 0.5, 1.4, alpha_thin=0.55)
    # service: lofted surface + slice outlines
    loft(ax, sv, face, 0.38 if key == "export_guarantee_on" else 0.5)
    slices(ax, sv, edge, 0.45, LW_CUT, alpha_thin=0.6, ls=ls)
    # all-idle point over time
    ax.plot([0, 0], [0, 0], [hours[0], hours[-1]], color=INK, lw=0.9, ls=(0, (3, 2)))
    ax.set_xlim(-180, 180); ax.set_ylim(-180, 180); ax.set_zlim(hours[0], hours[-1])
    ax.set_xlabel("ΔP (kW)", labelpad=2, fontsize=FS_AXLAB); ax.set_ylabel("ΔQ (kvar)", labelpad=2, fontsize=FS_AXLAB)
    ax.set_zlabel("")
    z_top = hours[-1] + 0.108 * (hours[-1] - hours[0])            # "time" on top of the time axis, as in the criteria figure
    t_time = ax.text(180, 180, z_top, "time", fontsize=FS_AXLAB, color=INK, ha="left", va="bottom")
    ax.set_xticks([-150, 0, 150]); ax.set_yticks([-150, 0, 150])
    ax.set_zticks([6] + [hours[times.index(t)] for t in CUTS]); ax.set_zticklabels(["06:00"] + CUTS)
    ax.tick_params(axis="both", labelsize=FS_TICK, pad=0)
    ax.yaxis.set_tick_params(pad=3)
    ax.zaxis.set_tick_params(pad=6)
    for a in (ax.xaxis, ax.yaxis, ax.zaxis):
        a.pane.set_facecolor((1, 1, 1, 0)); a.pane.set_edgecolor("#D5DCE1")
        a._axinfo["grid"].update(color="#E6EBEE", linewidth=0.6)
    ax.view_init(elev=20, azim=-58)
    ax.set_box_aspect((1, 1, 1.3), zoom=1.18)
    ax.set_proj_type("ortho")
    # title on the same line as "time": centred on the panel, but shifted left if it would run into "time"
    fig = ax.figure
    fig.canvas.draw()
    inv = fig.transFigure.inverted()
    px, py, _ = proj3d.proj_transform(180, 180, z_top, ax.get_proj())   # anchor of "time" (ha=left, va=bottom)
    tx, ty = inv.transform(ax.transData.transform((px, py)))
    ab = ax.get_position()
    ttl = fig.text(ab.x0 + ab.width / 2, ty, title, fontsize=FS_TITLE, color=INK, fontweight="semibold",
                   ha="center", va="bottom")
    fig.canvas.draw()
    wb = inv.transform(ttl.get_window_extent())
    gap = 0.15 / fig.get_figwidth()
    if wb[1, 0] > tx - gap:
        ttl.set_x(ttl.get_position()[0] - (wb[1, 0] - (tx - gap)))


fig = plt.figure(figsize=FIGSIZE, facecolor="white")
ax1 = fig.add_axes([AX_LEFT[0], AX_B, AX_W, AX_H], projection="3d", facecolor="none")
ax2 = fig.add_axes([AX_LEFT[1], AX_B, AX_W, AX_H], projection="3d", facecolor="none")
panel(ax1, "export_guarantee_on", ORANGE, ORANGE, "Export requests, self-consumption guarantee")
panel(ax2, "export_guarantee_relaxed", PALE, ORANGE, "Export requests, guarantee relaxed", ls=DASH)
fig.savefig(OUT, dpi=250, facecolor="white", bbox_inches="tight", pad_inches=0.05)
print("written", OUT)
