"""Figure for the linearization-derivative fix - all nine transformers.

Two panels:
  LEFT   the change in reach by sweep direction, one line per transformer, normalised
         to each transformer's own peak. Normalised because the claim this panel makes
         is about SHAPE - that every transformer rotates the same way - not magnitude.
         Absolute magnitudes are annotated on the panel and tabulated in README.md.
  RIGHT  what that rotation looks like geometrically, on the clean half-hour with the
         largest pure region movement (TR5, half-hour 22, identical starting SOC).

Only CLEAN half-hours feed the left panel: those where the committed battery schedule
is bit-identical between the two runs, so the difference is the region moving and
nothing else.

Static figure for print and email: light mode, no hover layer.
Palette: categorical slots 1 and 2 of the validated reference palette
(#2a78d6 / #eb6834); validate_palette.js reports all checks PASS, CVD dE 24.7.
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]

SURFACE, INK, INK2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8985"
OLD, NEW = "#2a78d6", "#eb6834"
GRID, BOX = "#e6e5e1", "#dedcd6"

FEATURE_TR, FEATURE_HH = 5, 22          # clean half-hour, largest pure region movement
ANGLES = list(range(0, 360, 30))


def load(name):
    d = pd.read_csv(ROOT / name, skipinitialspace=True)
    d.columns = [c.strip() for c in d.columns]
    for c in d.columns:
        if d[c].dtype == object:
            d[c] = d[c].astype(str).str.strip()
    return d


def clean_halfhours(k):
    """Half-hours where the committed dispatch is identical between the two runs."""
    a = load(f"FOR_rolling_soc_TR{k}_base.csv")
    b = load(f"FOR_rolling_soc_TR{k}_dfix.csv")
    m = a.merge(b, on=["now", "battery"], suffixes=("_o", "_n"))
    soc = m.assign(d=(m.SOC_start_n - m.SOC_start_o).abs()).groupby("now").d.max()
    return set(soc[soc < 1e-9].index)


# ---------------------------------------------------------------- gather
patterns, peaks = {}, {}
for k in range(1, 10):
    B, D = load(f"FOR_rolling_TR{k}_base.csv"), load(f"FOR_rolling_TR{k}_dfix.csv")
    m = B.merge(D, on=["now", "angle_deg"], suffixes=("_o", "_n"))
    m = m[m.now.isin(clean_halfhours(k))]
    g = m.assign(d=(m.proj_n - m.proj_o) * 1000).groupby("angle_deg").d.mean()
    patterns[k] = np.array([g.get(a, np.nan) for a in ANGLES])
    peaks[k] = np.nanmax(np.abs(patterns[k]))

norm = np.array([patterns[k] / peaks[k] for k in range(1, 10)])
pooled = np.nanmean(norm, axis=0)

fig, (axL, axR) = plt.subplots(1, 2, figsize=(12.6, 6.0), facecolor=SURFACE,
                               gridspec_kw={"width_ratios": [1.35, 1]})

# ---------------------------------------------------------------- left panel
axL.set_facecolor(SURFACE)
for s in ("top", "right"):
    axL.spines[s].set_visible(False)
for s in ("left", "bottom"):
    axL.spines[s].set_color(MUTED); axL.spines[s].set_linewidth(0.8)
axL.grid(True, color=GRID, linewidth=0.7); axL.set_axisbelow(True)
axL.axhline(0, color=INK2, lw=1.0, zorder=2)

# the lobes the rotation consists of
axL.axvspan(60, 120, color=NEW, alpha=0.07, zorder=0)
axL.axvspan(180, 240, color=OLD, alpha=0.07, zorder=0)

axL.fill_between(ANGLES, norm.min(axis=0), norm.max(axis=0),
                 color=MUTED, alpha=0.16, lw=0, zorder=1, label="range across the nine")
for i, k in enumerate(range(1, 10)):
    axL.plot(ANGLES, norm[i], "-", color=MUTED, lw=1.1, alpha=0.65, zorder=3,
             label="each transformer" if i == 0 else None)
axL.plot(ANGLES, pooled, "-o", color=NEW, lw=2.6, ms=6, mec=SURFACE, mew=1.4,
         zorder=5, label="mean of the nine")

axL.text(90, 1.30, "reactive-import side\npushes OUT", ha="center", va="center",
         color=INK, fontsize=10, linespacing=1.4, zorder=6)
axL.text(210, -1.30, "export side\npulls IN", ha="center", va="center",
         color=INK, fontsize=10, linespacing=1.4, zorder=6)

axL.set_xticks(ANGLES)
axL.set_xlim(-8, 338); axL.set_ylim(-1.62, 1.62)
axL.set_xlabel("sweep direction  (degrees)", color=INK2, fontsize=10.5)
axL.set_ylabel("change in reach\n(normalised to each transformer's own peak)",
               color=INK2, fontsize=10.5, linespacing=1.5)
axL.tick_params(colors=INK2, labelsize=9.5)
axL.set_title("Every transformer rotates the same way", color=INK,
              fontsize=12.5, fontweight="bold", pad=10)
lo, hi = min(peaks.values()), max(peaks.values())
axL.text(0.985, 0.975, f"peak movement per transformer\nranges {lo:.1f} to {hi:.1f} kW",
         transform=axL.transAxes, ha="right", va="top", color=MUTED, fontsize=9,
         linespacing=1.5)
leg = axL.legend(loc="lower left", frameon=True, fontsize=9.5,
                 facecolor=SURFACE, edgecolor=BOX)
for t in leg.get_texts():
    t.set_color(INK2)

# ---------------------------------------------------------------- right panel
B = load(f"FOR_rolling_TR{FEATURE_TR}_base.csv")
D = load(f"FOR_rolling_TR{FEATURE_TR}_dfix.csv")
b = B[B.now == FEATURE_HH].sort_values("angle_deg")
d = D[D.now == FEATURE_HH].sort_values("angle_deg")
cyc = lambda v: np.append(v, v[0])

axR.set_facecolor(SURFACE)
for s in ("top", "right"):
    axR.spines[s].set_visible(False)
for s in ("left", "bottom"):
    axR.spines[s].set_color(MUTED); axR.spines[s].set_linewidth(0.8)
axR.grid(True, color=GRID, linewidth=0.7); axR.set_axisbelow(True)

axR.plot(cyc(b.P.values), cyc(b.Q.values), "--", color=OLD, lw=2.0, zorder=3,
         label="before fix")
axR.plot(cyc(d.P.values), cyc(d.Q.values), "-", color=NEW, lw=2.0, zorder=4,
         label="after fix")
axR.plot(b.P, b.Q, "o", color=OLD, ms=5.5, mec=SURFACE, mew=1.3, zorder=5)
axR.plot(d.P, d.Q, "o", color=NEW, ms=5.5, mec=SURFACE, mew=1.3, zorder=6)

dproj = np.cos(np.radians(d.angle_deg.values)) * (d.P.values - b.P.values) + \
        np.sin(np.radians(d.angle_deg.values)) * (d.Q.values - b.Q.values)
for ang, tx, ty, ha in [(90, 1.0, 0.96, "right"), (210, 0.02, 0.34, "left")]:
    i = ANGLES.index(ang)
    axR.annotate(f"{ang}°   {dproj[i]*1000:+.1f} kW",
                 xy=(d.P.values[i], d.Q.values[i]), xycoords="data",
                 xytext=(tx, ty), textcoords="axes fraction",
                 color=INK, fontsize=10, ha=ha, va="center", zorder=8,
                 bbox=dict(boxstyle="round,pad=0.3", fc=SURFACE, ec=BOX, lw=0.8),
                 arrowprops=dict(arrowstyle="-", color=INK2, lw=1.0, shrinkA=2, shrinkB=3))

allP = np.concatenate([b.P.values, d.P.values]); allQ = np.concatenate([b.Q.values, d.Q.values])
px, py = np.ptp(allP), np.ptp(allQ)
axR.set_xlim(allP.min() - 0.22*px, allP.max() + 0.12*px)
axR.set_ylim(allQ.min() - 0.30*py, allQ.max() + 0.26*py)
axR.set_aspect("equal", adjustable="box")
axR.set_xlabel("P at PCC   (p.u.)", color=INK2, fontsize=10.5)
axR.set_ylabel("Q at PCC   (p.u.)", color=INK2, fontsize=10.5)
axR.tick_params(colors=INK2, labelsize=9.5)
axR.set_title(f"TR{FEATURE_TR}, half-hour {FEATURE_HH}", color=INK,
              fontsize=12.5, fontweight="bold", pad=10)
axR.text(0.5, 1.012, "identical starting SOC — a pure region effect",
         transform=axR.transAxes, ha="center", va="center", color=MUTED, fontsize=9)
leg2 = axR.legend(loc="lower right", frameon=True, fontsize=9,
                  facecolor=SURFACE, edgecolor=BOX, handlelength=1.7,
                  borderpad=0.45, labelspacing=0.35)
for t in leg2.get_texts():
    t.set_color(INK2)

fig.suptitle("Correcting the load/PV derivatives rotates the flexibility region — "
             "consistently, across all nine transformers",
             color=INK, fontsize=13.5, fontweight="bold", y=0.975)
fig.text(0.5, 0.015,
         "Left: mean change in the supporting projection per sweep direction, over the half-hours whose committed battery schedule is unchanged. "
         "All nine transformers push out\non the reactive-import side and pull in on the export side, so the region turns rather than grows. "
         "Right: the same effect in the P–Q plane. Sign convention grid → feeder\npositive, so this region sits in export; 1 p.u. = 1000 kW. "
         "Both runs 576/576 Optimal on all nine transformers, exact quadratic formulation, 12 directions at 30°.",
         ha="center", va="bottom", color=INK2, fontsize=9, linespacing=1.7)

fig.tight_layout(rect=[0, 0.115, 1, 0.935])
for ext, dpi in (("png", 200), ("pdf", None)):
    fig.savefig(OUT / f"derivfix_summary.{ext}", dpi=dpi, facecolor=SURFACE,
                bbox_inches="tight")
print("wrote derivfix_summary.png / .pdf")
print(f"  feature panel: TR{FEATURE_TR} half-hour {FEATURE_HH}, "
      f"max |dproj| {np.abs(dproj).max()*1000:.2f} kW")
print(f"  peak movement per transformer: " +
      ", ".join(f"TR{k} {peaks[k]:.1f}" for k in range(1, 10)) + "  kW")
print(f"  pooled normalised pattern: " +
      " ".join(f"{a}:{v:+.2f}" for a, v in zip(ANGLES, pooled)))
