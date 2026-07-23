"""Build the organized data workbook behind the TR9 rolling-dispatch figures.

Reads the committed rolling dispatch (FOR_rolling_soc_<TAG>.csv) and the
per-customer load+PV table, reconstructs every series used by the four figures
(SOC, demand, PV, charge, discharge, net), and writes one xlsx with one sheet
per quantity (periods as rows, prosumers as columns) plus fleet averages,
per-prosumer self-consumption metrics, and a summary.

Battery identity: the SOC CSV truncates battery names to 12 characters, but rows
are written in the model's set order, which equals the load+PV workbook's ID
order - the join is positional and verified by prefix match.

Usage:
  python build_workbook.py [--soc <csv>] [--tag TR9] [--force]
The output <TAG>_analysis_data.xlsx is NOT overwritten unless --force is given.
"""
import argparse, os, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = str(Path(__file__).resolve().parents[1])
SB_KW, NPER, DT = 1000.0, 48, 0.5

ap = argparse.ArgumentParser()
ap.add_argument("--soc", default=os.path.join(ROOT, "FOR_rolling_soc_TR9.csv"))
ap.add_argument("--loadpv", default=os.path.join(ROOT, "results", "tables", "TR9_load_PV_48periods.xlsx"),
                help="per-customer load+PV workbook (currently exists for TR9 only)")
ap.add_argument("--tag", default="TR9")
ap.add_argument("--outdir", default=ROOT)
ap.add_argument("--force", action="store_true", help="allow overwriting an existing workbook")
a = ap.parse_args()

out = os.path.join(a.outdir, f"{a.tag}_analysis_data.xlsx")
if os.path.exists(out) and not a.force:
    sys.exit(f"REFUSING to overwrite existing {out} (use --force)")

# ---- committed dispatch, identity restored by workbook ID order ----
s = pd.read_csv(a.soc, skipinitialspace=True)
s.columns = [c.strip() for c in s.columns]
for c in s.columns:
    if s[c].dtype == object or pd.api.types.is_string_dtype(s[c]):
        s[c] = s[c].astype(str).str.strip()
bat = pd.read_excel(a.loadpv, "Batteries").sort_values("ID").reset_index(drop=True)
cust = pd.read_excel(a.loadpv, "Customers")
NB = len(bat)
first = s[s["now"] == 1]["battery"].tolist()
assert len(first) == NB and all(str(f)[:len(x)] == x for x, f in zip(first, bat["BattName"])), \
    "positional identity join failed"
names = bat["BattName"].astype(str).tolist()

SOC = np.full((NB, NPER), np.nan); CHG = np.zeros((NB, NPER)); DIS = np.zeros((NB, NPER))
for now, g in s.groupby("now"):
    g = g.reset_index(drop=True); k = int(now) - 1
    SOC[:, k] = g["SOC_start"].values
    CHG[:, k] = g["Chg1"].values * SB_KW
    DIS[:, k] = g["Dis1"].values * SB_KW

loadP = pd.read_excel(a.loadpv, "Load_P_kW"); pvg = pd.read_excel(a.loadpv, "PV_generation_kW")
loadP = loadP.set_index(loadP.columns[0]); pvg = pvg.set_index(pvg.columns[0])
loadP.columns = [int(c) for c in loadP.columns]; pvg.columns = [int(c) for c in pvg.columns]
bp = {}
for r in cust.itertuples():
    bp.setdefault((r.LoadBus, r.LoadPhase), []).append(r.LoadName)
DEM = np.zeros((NB, NPER)); PV = np.zeros((NB, NPER))
for i in range(NB):
    b = bat.iloc[i]; L = bp.get((b.BattBus, b.BattPhase), [])
    if L:
        DEM[i, :] = loadP.loc[L, range(1, NPER + 1)].sum(axis=0).values
        PV[i, :] = pvg.loc[L, range(1, NPER + 1)].sum(axis=0).values
NET = (DEM - PV) + (CHG - DIS)

# ---- per-prosumer metrics ----
imp = np.maximum(NET, 0); exp = np.maximum(-NET, 0)
pv_e = PV.sum(1) * DT; dem_e = DEM.sum(1) * DT
exp_e = exp.sum(1) * DT; imp_e = imp.sum(1) * DT
SCR = np.where(pv_e > 1e-9, 1 - exp_e / pv_e, np.nan) * 100
SSR = np.where(dem_e > 1e-9, 1 - imp_e / dem_e, np.nan) * 100

hours = (np.arange(1, NPER + 1) - 1) * 0.5
def sheet(M):
    df = pd.DataFrame(M.T, columns=names)
    df.insert(0, "hour", hours); df.insert(0, "period", np.arange(1, NPER + 1))
    df["fleet_average"] = M.mean(0); df["fleet_total"] = M.sum(0)
    return df

fleet = pd.DataFrame({
    "period": np.arange(1, NPER + 1), "hour": hours,
    "demand_avg_kW": DEM.mean(0), "PV_avg_kW": PV.mean(0),
    "charge_avg_kW": CHG.mean(0), "discharge_avg_kW": DIS.mean(0),
    "net_avg_kW": NET.mean(0), "SOC_avg_pct": np.nanmean(SOC, 0) * 100,
    "demand_total_kW": DEM.sum(0), "PV_total_kW": PV.sum(0), "net_total_kW": NET.sum(0),
})
metrics = pd.DataFrame({
    "battery": names, "bus": bat["BattBus"], "phase": bat["BattPhase"],
    "BattMaxP_kW": bat["BattMaxP_kW"], "BattEcap_kWh": bat["BattEcap_kWh"],
    "PV_kWh": pv_e.round(2), "demand_kWh": dem_e.round(2),
    "export_kWh": exp_e.round(2), "import_kWh": imp_e.round(3),
    "SCR_pct": SCR.round(1), "SSR_pct": SSR.round(1),
})
summary = pd.DataFrame([
    ("run", f"{a.tag} exact-QCP rolling (FOR_PolyS=0, FOR_LinearizeVmax=0), 48 steps, all Optimal"),
    ("source dispatch", os.path.basename(a.soc)),
    ("source load/PV", os.path.basename(a.loadpv)),
    ("prosumers", NB),
    ("PV generated kWh/day", round(pv_e.sum(), 1)),
    ("demand kWh/day", round(dem_e.sum(), 1)),
    ("exported kWh/day", round(exp_e.sum(), 1)),
    ("imported kWh/day", round(imp_e.sum(), 1)),
    ("SCR % (PV used locally)", round(100 * (1 - exp_e.sum() / pv_e.sum()), 1)),
    ("SSR % (demand met locally)", round(100 * (1 - imp_e.sum() / dem_e.sum()), 1)),
    ("prosumer-periods |net|<50W %", round(100 * (np.abs(NET) < 0.05).mean(), 1)),
    ("SOC min/max over day", f"{np.nanmin(SOC):.2f} / {np.nanmax(SOC):.2f}"),
    ("simultaneous chg+dis rows", int(((CHG > 1e-3) & (DIS > 1e-3)).sum())),
], columns=["quantity", "value"])
readme = pd.DataFrame({"README": [
    f"Data behind the {a.tag} rolling-dispatch figures (SOC, demand/PV/dispatch, net, self-consumption, metrics histogram).",
    "Each quantity sheet: rows = 48 half-hour periods (with hour of day), columns = prosumers, plus fleet_average / fleet_total.",
    "Dispatch is the committed slot-1 execution of the rolling horizon (self-consumption baseline, Term 2 + Term 3).",
    "SOC is the realised state at the START of each step (fraction of capacity).",
    "net_kW = (demand - PV) + (charge - discharge); positive = import, negative = export.",
    "Regenerate: python build_workbook.py --force   (see README.md for other transformers).",
]})

with pd.ExcelWriter(out, engine="openpyxl") as w:
    readme.to_excel(w, sheet_name="ReadMe", index=False)
    summary.to_excel(w, sheet_name="Summary", index=False)
    fleet.to_excel(w, sheet_name="FleetAverage", index=False)
    sheet(SOC * 100).to_excel(w, sheet_name="SOC_pct", index=False)
    sheet(DEM).to_excel(w, sheet_name="Demand_kW", index=False)
    sheet(PV).to_excel(w, sheet_name="PV_kW", index=False)
    sheet(CHG).to_excel(w, sheet_name="Charge_kW", index=False)
    sheet(DIS).to_excel(w, sheet_name="Discharge_kW", index=False)
    sheet(NET).to_excel(w, sheet_name="Net_kW", index=False)
    metrics.to_excel(w, sheet_name="ProsumerMetrics", index=False)
print("wrote", out)
print(summary.to_string(index=False))
