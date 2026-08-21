"""Quantify what the LINEARIZED formulation costs, against the exact QCP.

Reads two rolling-FOR runs of the SAME transformer that differ only in
FOR_PolyS / FOR_LinearizeVmax, and produces:

  <TAG>_linearization.xlsx   Summary, Vertices, PerPeriod, ByDirection, Violations
  <TAG>_linearization_regions.png   FOR polygons, exact vs linearized
  <TAG>_linearization_overshoot.png where the relaxation breaks the voltage cap

Both linearizations are OUTER relaxations - the tangent plane lies below the
true convex Vre^2+Vim^2, and the 16-gon circumscribes the inverter S-circle - so
the linearized region must contain the exact one in every direction. The script
checks that rather than assuming it.

The columns VmaxTrue and OVviol are computed from the exact voltages either way,
so they stay meaningful under linearization: they are what says whether a vertex
is physically deliverable.

Usage:
  py -3 scripts/compare_linearization.py --tag TR3
  py -3 scripts/compare_linearization.py --exact <csv> --linear <csv> --tag TR3
Existing outputs are NOT overwritten unless --force is given.
"""
import argparse, math, os, sys
from pathlib import Path
import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[1]

# --- palette: dataviz reference instance, light surface (validator: all checks pass,
#     worst adjacent pair dE 24.7 protan / 33.6 normal) -------------------------
C_EXACT   = "#2a78d6"   # categorical slot 1
C_LINEAR  = "#eb6834"   # categorical slot 2
C_BAD     = "#d03b3b"   # status: critical
SURFACE   = "#fcfcfb"
GRID      = "#e1e0d9"
INK       = "#0b0b0b"
INK2      = "#52514e"
INK3      = "#8a8880"

VCAP = 1.10          # MaxV, p.u.
VIOL_EPS = 1e-6      # OVviol above this counts as a real breach, not solver dust

ap = argparse.ArgumentParser()
ap.add_argument("--tag", default="TR3")
ap.add_argument("--exact")
ap.add_argument("--linear")
ap.add_argument("--outdir", default=str(ROOT / "results" / "async-performance" / "linearization"))
ap.add_argument("--force", action="store_true")
a = ap.parse_args()

exact_csv  = a.exact  or str(ROOT / f"FOR_rolling_{a.tag}_base.csv")
linear_csv = a.linear or str(ROOT / f"FOR_rolling_{a.tag}_linear.csv")
outdir = Path(a.outdir); outdir.mkdir(parents=True, exist_ok=True)

xlsx = outdir / f"{a.tag}_linearization.xlsx"
fig1 = outdir / f"{a.tag}_linearization_regions.png"
fig2 = outdir / f"{a.tag}_linearization_overshoot.png"
for f in (xlsx, fig1, fig2):
    if f.exists() and not a.force:
        sys.exit(f"REFUSING to overwrite existing {f} (use --force)")


def load(p):
    d = pd.read_csv(p, skipinitialspace=True)
    d.columns = [c.strip() for c in d.columns]
    for c in d.columns:
        if d[c].dtype == object:
            d[c] = d[c].astype(str).str.strip()
    for c in ("P", "Q", "proj", "time", "VminTrue", "VmaxTrue", "UVviol", "OVviol", "LinErr"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["now"] = d["now"].astype(int)
    d["angle_deg"] = d["angle_deg"].astype(float)
    return d.sort_values(["now", "angle_deg"]).reset_index(drop=True)


def soc_divergence(tag_exact, tag_linear):
    """Max |dSOC_start| per period between the two committed trajectories.

    RunFOR_Rolling solves the committed baseline under the SAME formulation as the
    sweep, so a linearized run executes a different dispatch and the SOC it carries
    forward drifts. From the first period where that happens the two runs are
    computing regions from DIFFERENT physical states, and a direction-by-direction
    comparison is no longer a comparison of formulations.
    """
    try:
        A = pd.read_csv(tag_exact, skipinitialspace=True)
        B = pd.read_csv(tag_linear, skipinitialspace=True)
    except FileNotFoundError:
        return None
    for d in (A, B):
        d.columns = [c.strip() for c in d.columns]
        d["battery"] = d["battery"].astype(str).str.strip()
    m = A.merge(B, on=["now", "battery"], suffixes=("_e", "_l"))
    m["d"] = (m["SOC_start_e"] - m["SOC_start_l"]).abs()
    return m.groupby("now")["d"].max()


E, L = load(exact_csv), load(linear_csv)
SOCD = soc_divergence(exact_csv.replace("FOR_rolling_", "FOR_rolling_soc_"),
                      linear_csv.replace("FOR_rolling_", "FOR_rolling_soc_"))
SOC_EPS = 1e-5
if len(E) != len(L):
    sys.exit(f"row count differs: exact {len(E)}, linear {len(L)}")
if not (E["now"].equals(L["now"]) and E["angle_deg"].equals(L["angle_deg"])):
    sys.exit("the two runs are not on the same (period, angle) grid")

# ---------------------------------------------------------------- vertices
V = pd.DataFrame({
    "now": E["now"], "angle_deg": E["angle_deg"],
    "proj_exact": E["proj"], "proj_linear": L["proj"],
})
V["d_proj"] = V["proj_linear"] - V["proj_exact"]
den = V["proj_exact"].abs()
V["pct"] = np.where(den > 1e-6, 100.0 * V["d_proj"] / den, np.nan)
V["P_exact"], V["Q_exact"] = E["P"], E["Q"]
V["P_linear"], V["Q_linear"] = L["P"], L["Q"]
V["status_exact"], V["status_linear"] = E["status"], L["status"]
V["VmaxTrue_exact"], V["VmaxTrue_linear"] = E["VmaxTrue"], L["VmaxTrue"]
V["OVviol_exact"], V["OVviol_linear"] = E["OVviol"], L["OVviol"]
V["overshoot_V"] = (L["VmaxTrue"] - VCAP).clip(lower=0)
V["breaches_cap"] = L["OVviol"] > VIOL_EPS
if SOCD is not None:
    V["soc_divergence"] = V["now"].map(SOCD)
    V["comparable"] = V["soc_divergence"] <= SOC_EPS
else:
    V["soc_divergence"] = np.nan
    V["comparable"] = True

# ---------------------------------------------------------------- per period
def polygon_area(sub):
    """Area of the 12-gon through the solved vertices, in the P-Q plane."""
    pts = sub.sort_values("angle_deg")
    x, y = pts.values[:, 0], pts.values[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))

rows = []
for now, g in V.groupby("now"):
    ae = polygon_area(g[["P_exact", "Q_exact", "angle_deg"]].rename(
        columns={"P_exact": "x", "Q_exact": "y"})[["x", "y", "angle_deg"]])
    al = polygon_area(g[["P_linear", "Q_linear", "angle_deg"]].rename(
        columns={"P_linear": "x", "Q_linear": "y"})[["x", "y", "angle_deg"]])
    rows.append({
        "now": now, "area_exact": ae, "area_linear": al,
        "area_ratio": al / ae if ae > 0 else np.nan,
        "area_pct": 100.0 * (al / ae - 1) if ae > 0 else np.nan,
        "mean_d_proj": g["d_proj"].mean(),
        "max_d_proj": g["d_proj"].max(),
        "n_breaches": int(g["breaches_cap"].sum()),
        "max_VmaxTrue_linear": g["VmaxTrue_linear"].max(),
    })
PER = pd.DataFrame(rows).sort_values("now").reset_index(drop=True)

# ---------------------------------------------------------------- per direction
BYD = (V.groupby("angle_deg")
         .agg(mean_d_proj=("d_proj", "mean"),
              max_d_proj=("d_proj", "max"),
              mean_pct=("pct", "mean"),
              n_breaches=("breaches_cap", "sum"),
              max_overshoot_V=("overshoot_V", "max"))
         .reset_index())
BYD["n_breaches"] = BYD["n_breaches"].astype(int)

VIOL = V[V["breaches_cap"]].copy().sort_values("overshoot_V", ascending=False)

# ---------------------------------------------------------------- summary
nb = int(V["breaches_cap"].sum())
CMP = V[V["comparable"]]
larger = int((CMP["d_proj"] > 1e-6).sum())
smaller = int((CMP["d_proj"] < -1e-6).sum())
equal = len(CMP) - larger - smaller
ndiv = int((~V["comparable"]).sum())
ndivp = int(V.loc[~V["comparable"], "now"].nunique())
S = [
    ("transformer", a.tag),
    ("exact run", os.path.basename(exact_csv)),
    ("linearized run", os.path.basename(linear_csv)),
    ("directions", len(V)),
    ("", ""),
    ("--- outer-relaxation check (comparable directions only) ---", ""),
    ("comparable directions", f"{len(CMP)} / {len(V)}"),
    ("  ... linearized LARGER", larger),
    ("  ... equal", equal),
    ("  ... linearized SMALLER", smaller),
    ("", ""),
    ("--- trajectory divergence ---", ""),
    ("periods where committed SOC diverged", f"{ndivp} / {len(PER)}"),
    ("directions excluded from the check", ndiv),
    ("max |dSOC| (fraction of capacity)",
     round(float(SOCD.max()), 4) if SOCD is not None else "n/a"),
    ("", ""),
    ("--- how much bigger ---", ""),
    ("support inflation, median (p.u.)", round(V["d_proj"].median(), 6)),
    ("support inflation, mean (p.u.)", round(V["d_proj"].mean(), 6)),
    ("support inflation, max (p.u.)", round(V["d_proj"].max(), 6)),
    ("support inflation, median (%)", round(V["pct"].median(), 3)),
    ("region area, median (%)", round(PER["area_pct"].median(), 3)),
    ("region area, mean (%)", round(PER["area_pct"].mean(), 3)),
    ("region area, max (%)", round(PER["area_pct"].max(), 3)),
    ("", ""),
    ("--- what it costs: physical validity ---", ""),
    ("vertices breaching the true Vmax", f"{nb} / {len(V)}  ({100*nb/len(V):.1f} %)"),
    ("periods with >=1 breach", f"{int((PER['n_breaches']>0).sum())} / {len(PER)}"),
    ("max VmaxTrue, linearized (p.u.)", round(V["VmaxTrue_linear"].max(), 5)),
    ("max VmaxTrue, exact (p.u.)", round(V["VmaxTrue_exact"].max(), 5)),
    ("max overshoot above cap (p.u.)", round(V["overshoot_V"].max(), 5)),
    ("", ""),
    ("--- cost of the exact form ---", ""),
    ("mean solve, exact (s)", round(E["time"].mean(), 2)),
    ("mean solve, linearized (s)", round(L["time"].mean(), 2)),
    ("Optimal, exact", f"{int((E['status']=='Optimal').sum())} / {len(E)}"),
    ("Optimal, linearized", f"{int((L['status']=='Optimal').sum())} / {len(L)}"),
]
SUM = pd.DataFrame(S, columns=["quantity", "value"])

with pd.ExcelWriter(xlsx, engine="openpyxl") as w:
    SUM.to_excel(w, sheet_name="Summary", index=False)
    V.to_excel(w, sheet_name="Vertices", index=False)
    PER.to_excel(w, sheet_name="PerPeriod", index=False)
    BYD.to_excel(w, sheet_name="ByDirection", index=False)
    VIOL.to_excel(w, sheet_name="Violations", index=False)
    for name, ncol in (("Summary", 2), ("Vertices", len(V.columns)),
                       ("PerPeriod", len(PER.columns)), ("ByDirection", len(BYD.columns)),
                       ("Violations", len(VIOL.columns))):
        ws = w.sheets[name]
        ws.freeze_panes = "A2"
        for i in range(1, ncol + 1):
            ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = 18
print(f"wrote {xlsx}")

# ================================================================= figure 1
def close_ring(g, px, qx):
    p = list(g[px]) + [g[px].iloc[0]]
    q = list(g[qx]) + [g[qx].iloc[0]]
    return p, q

# pick six periods spanning the day, preferring ones that show the transition
clean = [int(n) for n in PER[PER["n_breaches"] == 0]["now"]]
dirty = [int(n) for n in PER.sort_values(["n_breaches", "max_d_proj"], ascending=False)["now"]]
picks = sorted(set(([clean[0], clean[len(clean)//2], clean[-1]] if len(clean) >= 3 else clean)
                   + dirty[:3]))[:6]

fig, axes = plt.subplots(2, 3, figsize=(13.2, 8.4), facecolor=SURFACE)
for ax, now in zip(axes.ravel(), picks):
    g = V[V["now"] == now].sort_values("angle_deg")
    ax.set_facecolor(SURFACE)
    pe, qe = close_ring(g, "P_exact", "Q_exact")
    pl, ql = close_ring(g, "P_linear", "Q_linear")
    ax.fill(pl, ql, color=C_LINEAR, alpha=0.10, zorder=1)
    ax.plot(pl, ql, color=C_LINEAR, lw=2.0, ls=(0, (5, 2)), zorder=3)
    ax.fill(pe, qe, color=C_EXACT, alpha=0.13, zorder=2)
    ax.plot(pe, qe, color=C_EXACT, lw=2.0, zorder=4)
    ax.scatter(g["P_linear"], g["Q_linear"], s=16, color=C_LINEAR,
               edgecolor=SURFACE, linewidth=1.0, zorder=5)
    bad = g[g["breaches_cap"]]
    if len(bad):
        ax.scatter(bad["P_linear"], bad["Q_linear"], s=64, marker="X",
                   color=C_BAD, edgecolor=SURFACE, linewidth=1.2, zorder=6)
    nb_p = int(g["breaches_cap"].sum())
    ax.set_title(f"period {now}", color=INK, fontsize=11, pad=7, loc="left")
    ax.set_title(f"{nb_p}/12 breach cap" if nb_p else "all 12 feasible",
                 color=(C_BAD if nb_p else INK3), fontsize=9.5, loc="right", pad=7)
    ax.grid(True, color=GRID, lw=0.7)
    ax.set_axisbelow(True)
    ax.margins(0.16)          # never draw the origin: it dwarfs the region and hides the difference
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(colors=INK2, labelsize=9, length=0)
    ax.set_xlabel("P at PCC  (p.u.)", color=INK2, fontsize=9)
    ax.set_ylabel("Q at PCC  (p.u.)", color=INK2, fontsize=9)

handles = [
    Line2D([], [], color=C_EXACT, lw=2.0, label="exact QCP"),
    Line2D([], [], color=C_LINEAR, lw=2.0, ls=(0, (5, 2)), label="linearized"),
    Line2D([], [], color=C_BAD, marker="X", ls="none", ms=9,
           label=f"vertex breaching Vmax = {VCAP:g} p.u."),
]
fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False,
           fontsize=10, bbox_to_anchor=(0.5, -0.005), labelcolor=INK2)
fig.suptitle(f"{a.tag} — linearized against exact: nearly the same region, a fifth to a half of it undeliverable",
             color=INK, fontsize=13.5, x=0.055, ha="left", y=0.985)
_sub = (f"The two boundaries almost coincide - area grows {PER['area_pct'].median():.1f}% (median), "
        f"{PER['area_pct'].max():.1f}% at worst - yet {nb} of {len(V)} vertices "
        f"({100*nb/len(V):.0f}%)" + chr(10) +
        "are not physically deliverable. Panels are zoomed on each region; the origin is off-scale.")
fig.text(0.055, 0.930, _sub, color=INK2, fontsize=10.5, ha="left", va="top", linespacing=1.5)
fig.tight_layout(rect=[0, 0.035, 1, 0.905])
fig.savefig(fig1, dpi=170, facecolor=SURFACE)
print(f"wrote {fig1}")

# ================================================================= figure 2
angles = sorted(V["angle_deg"].unique())
periods = sorted(V["now"].unique())
M = (V.pivot(index="angle_deg", columns="now", values="overshoot_V")
      .reindex(index=angles, columns=periods).to_numpy())

fig, (ax, axb) = plt.subplots(
    2, 1, figsize=(13.2, 6.6), facecolor=SURFACE,
    gridspec_kw={"height_ratios": [2.5, 1], "hspace": 0.42})

# sequential, single hue light -> dark, with the zero step at the surface colour
from matplotlib.colors import LinearSegmentedColormap
cmap = LinearSegmentedColormap.from_list("overshoot", [SURFACE, "#f2c4c4", C_BAD, "#7d1f1f"])
vmax = float(np.nanmax(M)) if np.nanmax(M) > 0 else 1.0
im = ax.imshow(M * 1000, aspect="auto", origin="lower", cmap=cmap,
               vmin=0, vmax=vmax * 1000,
               extent=[periods[0] - 0.5, periods[-1] + 0.5, -0.5, len(angles) - 0.5])
ax.set_facecolor(SURFACE)
ax.set_yticks(range(len(angles)))
ax.set_yticklabels([f"{x:.0f}°" for x in angles], fontsize=9, color=INK2)
ax.set_xlabel("rolling period", color=INK2, fontsize=9.5)
ax.set_ylabel("sweep direction", color=INK2, fontsize=9.5)
ax.tick_params(colors=INK2, labelsize=9, length=0)
for s in ax.spines.values():
    s.set_visible(False)
cb = fig.colorbar(im, ax=ax, pad=0.012, fraction=0.026)
cb.set_label("overshoot above the 1.10 p.u. cap  (10⁻³ p.u.)", color=INK2, fontsize=9)
cb.ax.tick_params(colors=INK2, labelsize=8.5, length=0)
cb.outline.set_visible(False)
ax.set_title("Where the relaxation breaks the voltage cap", color=INK,
             fontsize=12.5, loc="left", pad=8)

axb.set_facecolor(SURFACE)
bars = axb.bar([f"{x:.0f}°" for x in BYD["angle_deg"]], BYD["n_breaches"],
               color=[C_BAD if n else GRID for n in BYD["n_breaches"]], width=0.62)
axb.set_ylabel("periods breaching\n(of 48)", color=INK2, fontsize=9.5)
axb.set_xlabel("sweep direction", color=INK2, fontsize=9.5)
axb.grid(True, axis="y", color=GRID, lw=0.7)
axb.set_axisbelow(True)
for s in axb.spines.values():
    s.set_visible(False)
axb.tick_params(colors=INK2, labelsize=9, length=0)
for b, n in zip(bars, BYD["n_breaches"]):
    if n:
        axb.text(b.get_x() + b.get_width() / 2, n + 0.7, str(n),
                 ha="center", va="bottom", fontsize=8.5, color=INK2)
axb.set_title("Every breach is on the export side, and none on the import side",
              color=INK, fontsize=11, loc="left", pad=6)
fig.tight_layout()
fig.savefig(fig2, dpi=170, facecolor=SURFACE)
print(f"wrote {fig2}")

# ---------------------------------------------------------------- console
print()
print(SUM.to_string(index=False))
