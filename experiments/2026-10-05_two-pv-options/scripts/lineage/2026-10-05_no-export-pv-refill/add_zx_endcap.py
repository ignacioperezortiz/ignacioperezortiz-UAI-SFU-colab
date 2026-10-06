"""Third patch (after add_zx.py and add_zx_tight.py) for model/MainProject/OPF.ams of THIS folder (5 Oct, 14:10).

Second finding of WC_EXPORT: the fleet ends the day at 24 % SOC instead of 50 % and its planned purchases for
the next 24 h are 3.4 kWh higher than without requests. The rule of the paper protects every slot INSIDE the
24-h window, but the terminal band (eq. 6, +-delta_E around the SOC measured at each step) moves with every
step, so a service can leave the battery emptier at the window end and the purchase falls just outside it.

Switch ZX_EndOn (default 0 = unchanged): in every directional solve the stored energy at the end of the window
may not be lower than in P1's plan, i.e. whatever a service takes must be refilled within 24 h (by PV that
would otherwise be cut). Rows in SOC x 1000 with a slack ZX_EndTol = 1e-5 (4e-8 kWh), as SRQ_EndCap.
Read from scenario.txt by ZX_Run. Usage: python scripts/add_zx_endcap.py
"""
import hashlib
from pathlib import Path

AMS = Path(__file__).resolve().parents[1] / "model" / "MainProject" / "OPF.ams"
raw = AMS.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n")
s = raw.decode("utf-8").replace("\r\n", "\n")
assert "ZX_SCTight" in s, "run add_zx.py and add_zx_tight.py first"
assert "ZX_EndCap" not in s, "already patched"


def rep(old, new):
    global s
    n = s.count(old)
    assert n == 1, f"{n} matches for: {old[:70]!r}"
    s = s.replace(old, new)


rep("\t\t\tParameter FRQ_Diag {",
    "\t\t\tParameter ZX_EndOn {\n"
    "\t\t\t\tDefault: 0;\n"
    "\t\t\t\tComment: \"1 = a service may not leave less energy at the end of the window than P1's plan (ZX_EndCap).\";\n"
    "\t\t\t}\n"
    "\t\t\tParameter ZX_EndTol {\n"
    "\t\t\t\tDefault: 1e-5;\n"
    "\t\t\t}\n"
    "\t\t\tParameter ZX_SOCEndRef {\n"
    "\t\t\t\tIndexDomain: bat;\n"
    "\t\t\t\tComment: \"SOC at the end of the window in P1's plan, captured after the baseline solve.\";\n"
    "\t\t\t}\n"
    "\t\t\tConstraint ZX_EndCap {\n"
    "\t\t\t\tIndexDomain: bat | ZX_EndOn and SCRefActive;\n"
    "\t\t\t\tDefinition: 1000*sum(t | ord(t) = nPeriods, BattSOC(bat,t)) >= 1000*ZX_SOCEndRef(bat) - ZX_EndTol;\n"
    "\t\t\t\tComment: \"What a service takes from a battery must be back by the end of the 24-h window.\";\n"
    "\t\t\t}\n"
    "\t\t\tParameter FRQ_Diag {")
old = "ZX_CutRef(bat) := if ZX_On = 1 then ZX_Cut(bat,PeriodMaxP) else 0 endif;   ! ZX: P1's cut at the service slot"
i = s.index(old)
ind = s[s.rindex("\n", 0, i) + 1:i]
rep(old, old + "\n" + ind + "ZX_SOCEndRef(bat) := BattSOC(bat, Element(Time, nPeriods));   ! ZX: P1's energy at the window end")
rep("SRQ_MaxPer := 0;  FRQ_SweepAll := 0;  FRQ_PlanLog := 0;  ZX_GMP := 0;  SCTight := 0;",
    "SRQ_MaxPer := 0;  FRQ_SweepAll := 0;  FRQ_PlanLog := 0;  ZX_GMP := 0;  SCTight := 0;  ZX_EndOn := 0;")
rep("ZX_On := 0;  FRQ_Diag := 1;  RollUseGMP := 0;  SCTight := 0;",
    "ZX_On := 0;  FRQ_Diag := 1;  RollUseGMP := 0;  SCTight := 0;  ZX_EndOn := 0;")
rep('", SCTight ", SCTight:2:0, "): execution failures "',
    '", SCTight ", SCTight:2:0, ", ZX_EndOn ", ZX_EndOn:2:0, "): execution failures "')

out = s.replace("\n", "\r\n").encode("utf-8")
AMS.write_bytes(out)
print("patched", AMS, "sha256", hashlib.sha256(out).hexdigest()[:16])
