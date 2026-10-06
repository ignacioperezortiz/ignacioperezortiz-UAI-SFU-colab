"""Second patch (after add_zx.py) for model/MainProject/OPF.ams of THIS folder (2026-10-05, 14:00).

Finding of the worst-case run WC_EXPORT (max export every half-hour 06:00-20:00): one house bought 110 Wh more
in the evening than without requests. Cause: the self-consumption row SCNoImportFuture allows each later slot
a slack SCEps = 1e-6 p.u. (1 W), and a TSO that asks again every half-hour can use that slack again at every
request; the planned future purchases of that house crept up by ~5-10 Wh per request (2.81 -> 2.92 kWh).

Switch SCTight (default 0 = unchanged): the same rule written in kW (rows scaled by 1000, so the solver's
feasibility tolerance is 1 mW instead of 1 W) with a slack of ZX_TightTol = 1e-5 kW (0.01 W), 100 times
smaller than SCEps. SCNoImportFuture is switched off while SCTight = 1.
Read from scenario.txt by ZX_Run. Usage: python scripts/add_zx_tight.py
"""
import hashlib
from pathlib import Path

AMS = Path(__file__).resolve().parents[1] / "model" / "MainProject" / "OPF.ams"
raw = AMS.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n")
s = raw.decode("utf-8").replace("\r\n", "\n")
assert "ZX_Declarations" in s, "run add_zx.py first"
assert "ZX_SCTight" not in s, "already patched"


def rep(old, new):
    global s
    n = s.count(old)
    assert n == 1, f"{n} matches for: {old[:70]!r}"
    s = s.replace(old, new)


rep("IndexDomain: (bat,t) | (SCFirst = 1 or SCT_Hard = 1) and SCRefActive and ord(t) > PeriodMaxP;\n"
    "\t\t\t\tDefinition: TotPcust(BattBus(bat),BattPhase(bat),t) <= SCImpRef(bat,t) + SCAlpha*BattMaxP(bat) + SCEps;",
    "IndexDomain: (bat,t) | (SCFirst = 1 or SCT_Hard = 1) and SCRefActive and ord(t) > PeriodMaxP and SCTight = 0;\n"
    "\t\t\t\tDefinition: TotPcust(BattBus(bat),BattPhase(bat),t) <= SCImpRef(bat,t) + SCAlpha*BattMaxP(bat) + SCEps;")
rep("\t\t\tParameter FRQ_Diag {",
    "\t\t\tParameter SCTight {\n"
    "\t\t\t\tDefault: 0;\n"
    "\t\t\t\tComment: \"1 = self-consumption rule in kW with a 0.01 W slack (ZX_SCTight) instead of SCNoImportFuture (1 W slack, p.u.).\";\n"
    "\t\t\t}\n"
    "\t\t\tParameter ZX_TightTol {\n"
    "\t\t\t\tDefault: 1e-5;\n"
    "\t\t\t\tComment: \"Slack of ZX_SCTight, kW (1e-5 kW = 0.01 W).\";\n"
    "\t\t\t}\n"
    "\t\t\tConstraint ZX_SCTight {\n"
    "\t\t\t\tIndexDomain: (bat,t) | SCTight and (SCFirst = 1 or SCT_Hard = 1) and SCRefActive and ord(t) > PeriodMaxP;\n"
    "\t\t\t\tDefinition: 1000*TotPcust(BattBus(bat),BattPhase(bat),t) <= 1000*SCImpRef(bat,t) + 1000*SCAlpha*BattMaxP(bat) + ZX_TightTol;\n"
    "\t\t\t\tComment: \"SCNoImportFuture in kW: the solver tolerance and the slack no longer add up to 1 W per later slot at every request.\";\n"
    "\t\t\t}\n"
    "\t\t\tParameter FRQ_Diag {")
rep("SRQ_MaxPer := 0;  FRQ_SweepAll := 0;  FRQ_PlanLog := 0;  ZX_GMP := 0;",
    "SRQ_MaxPer := 0;  FRQ_SweepAll := 0;  FRQ_PlanLog := 0;  ZX_GMP := 0;  SCTight := 0;")
rep("ZX_On := 0;  FRQ_Diag := 1;  RollUseGMP := 0;",
    "ZX_On := 0;  FRQ_Diag := 1;  RollUseGMP := 0;  SCTight := 0;")
rep('put "ZX summary (ZX_On ", ZX_On:2:0, ", RollUseGMP ", RollUseGMP:2:0, "): execution failures "',
    'put "ZX summary (ZX_On ", ZX_On:2:0, ", RollUseGMP ", RollUseGMP:2:0, ", SCTight ", SCTight:2:0, "): execution failures "')

out = s.replace("\n", "\r\n").encode("utf-8")
AMS.write_bytes(out)
print("patched", AMS, "sha256", hashlib.sha256(out).hexdigest()[:16])
