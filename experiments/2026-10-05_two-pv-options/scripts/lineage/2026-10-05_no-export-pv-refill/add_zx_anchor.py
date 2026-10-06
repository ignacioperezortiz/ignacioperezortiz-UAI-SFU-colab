"""Fourth patch (after add_zx.py, add_zx_tight.py, add_zx_endcap.py) for model/MainProject/OPF.ams of THIS folder.

Why (5 Oct, 14:20): in WC_EXPORT the purchases P1 PLANS for the window drop first and then climb above REF's
(-5.8 kWh at 06:30, +4.0 kWh at 19:30, +3.4 kWh left for the next morning). The self-consumption rule
compares every service with P1's CURRENT plan, and that plan follows the measured SOC through the terminal
band (paper eq. 6: energy at the window end within +-delta_E of the energy measured NOW). A TSO that keeps
draining the batteries moves that target down step after step, so energy it takes can reappear as a
purchase after the window.

Switch ZX_AnchorOn (default 0 = unchanged): the lower side of the terminal band is anchored to the
no-service schedule: E_end >= max(E_now, E_noservice(now)) - delta_E * E_cap. With a perfect (persistence)
forecast the no-service schedule of the window end (tomorrow, same time) is the REF day at the same time,
read from anchor.txt (written by scripts/run_zx.py from REF's SCT_exec). In the method this is one more P1
solve per step for a "shadow" prosumer that never serves; here the REF run is that shadow (simulation
shortcut, like the FOR computed only at request half-hours). REF itself is unchanged by construction.
Usage: python scripts/add_zx_anchor.py
"""
import hashlib
from pathlib import Path

AMS = Path(__file__).resolve().parents[1] / "model" / "MainProject" / "OPF.ams"
raw = AMS.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n")
s = raw.decode("utf-8").replace("\r\n", "\n")
assert "ZX_EndCap" in s, "run add_zx.py, add_zx_tight.py and add_zx_endcap.py first"
assert "ZX_AnchorOn" not in s, "already patched"


def rep(old, new):
    global s
    n = s.count(old)
    assert n == 1, f"{n} matches for: {old[:70]!r}"
    s = s.replace(old, new)


rep("Definition: sum(t, BattP_Chg(bat,t)*etaChg(bat) - BattP_Dis(bat,t)/etaDis(bat)) >= -CyclicSOCBand * BattEcap(bat) / DeltaT;",
    "Definition: sum(t, BattP_Chg(bat,t)*etaChg(bat) - BattP_Dis(bat,t)/etaDis(bat)) >= -CyclicSOCBand * BattEcap(bat) / DeltaT"
    " + ZX_AnchorOn * max(0, ZX_SOCAnchor(bat) - BattSOCini(bat)) * BattEcap(bat) / DeltaT;")
rep("\t\t\tParameter FRQ_Diag {",
    "\t\t\tParameter ZX_AnchorOn {\n"
    "\t\t\t\tDefault: 0;\n"
    "\t\t\t\tComment: \"1 = lower side of the terminal band anchored to the no-service schedule (ZX_SOCAnchor), not only to the SOC measured now.\";\n"
    "\t\t\t}\n"
    "\t\t\tParameter ZX_SOCAnchorDay {\n"
    "\t\t\t\tIndexDomain: (bat,t);\n"
    "\t\t\t\tComment: \"SOC at the start of each real period in the no-service (REF) day, read from anchor.txt.\";\n"
    "\t\t\t}\n"
    "\t\t\tParameter ZX_SOCAnchor {\n"
    "\t\t\t\tIndexDomain: bat;\n"
    "\t\t\t\tComment: \"No-service SOC for this step's window end (tomorrow, same time) = REF at the current real period.\";\n"
    "\t\t\t}\n"
    "\t\t\tParameter FRQ_Diag {")
i0 = s.index("if RollMaxPeriods > 0 and RollNow > RollMaxPeriods then break; endif;")   # RunFOR_Rolling only
old = "RollMap(tt) := Element(Time, mod(ord(tt)-1 + (RollNow-1), nPeriods) + 1);"
i = s.index(old, i0)
assert i - i0 < 400, "RollMap line not right after the smoke cap"
ind = s[s.rindex("\n", 0, i) + 1:i]
s = (s[:i] + old + "\n"
     + ind + "if ZX_AnchorOn = 1 and RollNow = 1 then read from file \"anchor.txt\"; endif;   ! ZX: no-service SOC per real period\n"
     + ind + "ZX_SOCAnchor(bat) := if ZX_AnchorOn = 1 then ZX_SOCAnchorDay(bat, Element(Time, RollNow)) else 0 endif;"
     + s[i + len(old):])
rep("SRQ_MaxPer := 0;  FRQ_SweepAll := 0;  FRQ_PlanLog := 0;  ZX_GMP := 0;  SCTight := 0;  ZX_EndOn := 0;",
    "SRQ_MaxPer := 0;  FRQ_SweepAll := 0;  FRQ_PlanLog := 0;  ZX_GMP := 0;  SCTight := 0;  ZX_EndOn := 0;  ZX_AnchorOn := 0;")
rep("ZX_On := 0;  FRQ_Diag := 1;  RollUseGMP := 0;  SCTight := 0;  ZX_EndOn := 0;",
    "ZX_On := 0;  FRQ_Diag := 1;  RollUseGMP := 0;  SCTight := 0;  ZX_EndOn := 0;  ZX_AnchorOn := 0;")
rep('", ZX_EndOn ", ZX_EndOn:2:0, "): execution failures "',
    '", ZX_EndOn ", ZX_EndOn:2:0, ", ZX_AnchorOn ", ZX_AnchorOn:2:0, "): execution failures "')

out = s.replace("\n", "\r\n").encode("utf-8")
AMS.write_bytes(out)
print("patched", AMS, "sha256", hashlib.sha256(out).hexdigest()[:16])
