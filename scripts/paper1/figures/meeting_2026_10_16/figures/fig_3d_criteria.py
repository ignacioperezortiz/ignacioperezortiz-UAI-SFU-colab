"""3-D figure: F_{k+1} over the day (ΔP, ΔQ, time) for reference, CP, HP, HB (intra-aggregator, energy floor).
Reads only sweeps.json (--data); writes <out>/figures/fig_3d_criteria.png.
Run:  python -B fig_3d_criteria.py [--data DIR] [--out DIR]
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from mpl_toolkits.mplot3d import proj3d  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))     # package root: paths.py
import paths  # noqa: E402

paths.cli(__doc__, data=True)
S = json.loads(paths.deck_json("data_tulio", "sweeps.json").read_text(encoding="utf-8"))
T, H = S["time"], np.array(S["hour"])
INK, CP, HP, HB, GREY, TEXT = "#14354A", "#A65D57", "#C4863C", "#3D637B", "#9AA8B2", "#14354A"
CUTS = ["07:30", "12:30", "18:00", "21:30"]
PANELS = [("ref", "Reference", INK), ("CP_intra", "CP", CP), ("HP_intra", "HP", HP), ("HB_intra", "HB", HB)]
ELEV, AZIM = 20, -58
LIM_P, LIM_Q = (-180, 180), (-180, 180)
FIGSIZE = (12.3, 4.0)
FS_TICK, FS_AXLAB, FS_TITLE, FS_CUT = 11, 11.5, 13, 11
LW_CUT = 2.0

plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Segoe UI", "Arial", "DejaVu Sans"],
                     "font.size": 9, "axes.edgecolor": GREY, "text.color": TEXT, "axes.labelcolor": TEXT,
                     "xtick.color": TEXT, "ytick.color": TEXT})


def poly(cid):
    return np.array(S["per_case"][cid]["polygons"], float)          # 48 x 12 x 2


def closed(a):
    return np.vstack([a, a[:1]])


def loft(ax, P, color, alpha):
    quads = []
    for k in range(len(H) - 1):
        for j in range(12):
            j2 = (j + 1) % 12
            quads.append([(P[k, j, 0], P[k, j, 1], H[k]), (P[k, j2, 0], P[k, j2, 1], H[k]),
                          (P[k + 1, j2, 0], P[k + 1, j2, 1], H[k + 1]), (P[k + 1, j, 0], P[k + 1, j, 1], H[k + 1])])
    pc = Poly3DCollection(quads, facecolor=color, edgecolor="none", alpha=alpha)
    ax.add_collection3d(pc)


def slices(ax, P, color, lw, alpha, every=1):
    for k in range(0, len(H), every):
        c = closed(P[k])
        ax.plot(c[:, 0], c[:, 1], H[k], color=color, lw=lw, alpha=alpha)


fig = plt.figure(figsize=FIGSIZE, dpi=250)
ref = poly("ref")
mean_kept = {cid: S["summary"]["area_ratio_stats"][cid]["mean"] for cid, _, _ in PANELS}
for p, (cid, name, col) in enumerate(PANELS):
    ax = fig.add_subplot(1, 4, p + 1, projection="3d", computed_zorder=False)
    ax.set_facecolor("none")                                         # never hide the neighbour's time labels
    P = poly(cid)
    if cid != "ref":
        slices(ax, ref, GREY, 0.35, 0.55, every=2)                  # reference: faint grey wireframe
    loft(ax, P, col, 0.13)
    slices(ax, P, col, 0.3, 0.45, every=2)
    labels = []
    for t in CUTS:
        k = T.index(t)
        c = closed(P[k])
        ax.plot(c[:, 0], c[:, 1], H[k], color=col, lw=LW_CUT, alpha=1.0, zorder=10)
        if p == 0:
            labels.append((k, t))
    ax.set_xlim(*LIM_P)
    ax.set_ylim(*LIM_Q)
    ax.set_zlim(0, 24)
    ax.view_init(elev=ELEV, azim=AZIM)
    ax.set_box_aspect((1, 1, 1.3), zoom=1.18)
    ax.set_proj_type("ortho")
    for k, t in labels:                                                 # label each cut at its left-most screen point
        fig.canvas.draw()
        M = ax.get_proj()
        xs, ys, _ = proj3d.proj_transform(P[k, :, 0], P[k, :, 1], np.full(12, H[k]), M)
        j = int(np.argmin(xs))
        ax.text(P[k, j, 0], P[k, j, 1], H[k], t + "  ", fontsize=FS_CUT, color=TEXT, ha="right", va="center", zorder=11)
    ax.set_xticks([-150, 0, 150])
    ax.set_yticks([-150, 0, 150])
    ax.set_zticks([0, 6, 12, 18, 24])
    ax.set_zticklabels(["00:00", "06:00", "12:00", "18:00", "24:00"])
    ax.tick_params(axis="both", labelsize=FS_TICK, pad=0)
    ax.yaxis.set_tick_params(pad=3)
    ax.zaxis.set_tick_params(pad=6)
    ax.set_xlabel("ΔP (kW)", labelpad=2, fontsize=FS_AXLAB)
    ax.set_ylabel("ΔQ (kvar)", labelpad=2, fontsize=FS_AXLAB)
    ax.set_zlabel("")
    ax.text(LIM_P[1], LIM_Q[1], 26.6, "time", fontsize=FS_AXLAB, color=TEXT, ha="left", va="bottom")  # z-axis label on top of the axis
    for a in (ax.xaxis, ax.yaxis, ax.zaxis):
        a.set_pane_color((1, 1, 1, 0))
        a._axinfo["grid"].update(color="#E3E8EC", linewidth=0.5)
    title = "Reference" if cid == "ref" else f"{name} · {100 * mean_kept[cid]:.1f} %"
    ax.set_title(title, fontsize=FS_TITLE, color=col if cid != "ref" else INK, pad=-2, fontweight="semibold")

fig.subplots_adjust(left=0.0, right=0.955, bottom=-0.03, top=1.0, wspace=0.16)
out = paths.figures_out() / "fig_3d_criteria.png"
fig.savefig(out, dpi=250, facecolor="white", bbox_inches="tight", pad_inches=0.05)
print("written", out)
