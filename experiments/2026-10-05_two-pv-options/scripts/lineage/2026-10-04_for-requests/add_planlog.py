"""Demonstration runs in FOR-request mode: log the window plan (step 1 and executed) at every step.

Runner and logging only (no change to the equations). Applied after add_frq.py. Run once.
FRQ_PlanLog = 1 in scenario.txt switches it on (it sets SRQ_Sweep, which in FRQ_Run only gates the plan log).
"""
from pathlib import Path

AMS = Path(__file__).resolve().parents[1] / "model" / "MainProject" / "OPF.ams"
NL = "\r\n"
src = AMS.read_bytes().decode("utf-8")
if "FRQ_PlanLog" in src:
    raise SystemExit("already patched - nothing written")
T = "\t"


def sub(text, old, new, label, count=1):
    old, new = old.replace("\n", NL), new.replace("\n", NL)
    n = text.count(old)
    if n != count:
        raise SystemExit(f"{label}: expected {count} matches, found {n} - nothing written")
    return text.replace(old, new)


src = sub(src, "if SRQ_Mode = 1 and SRQ_Sweep = 1 then", "if SRQ_Mode >= 1 and SRQ_Sweep = 1 then", "plan-log gates", count=2)
src = sub(src,
    "SRQ_Coord := 0;  SRQ_Tag := \"\";  SRQ_Periods := \"\";  SRQ_MaxPer := 0;  FRQ_SweepAll := 0;",
    "SRQ_Coord := 0;  SRQ_Tag := \"\";  SRQ_Periods := \"\";  SRQ_MaxPer := 0;  FRQ_SweepAll := 0;  FRQ_PlanLog := 0;",
    "runner reset")
src = sub(src,
    "SRQ_Mode := 2;  RollSvcMode := 4;  RollSvcPeriodsCSV := SRQ_Periods;  RollSvcTol := 1e-4;  SRQ_Sweep := 0;\n",
    "SRQ_Mode := 2;  RollSvcMode := 4;  RollSvcPeriodsCSV := SRQ_Periods;  RollSvcTol := 1e-4;  SRQ_Sweep := FRQ_PlanLog;\n",
    "runner plan-log switch")
src = sub(src,
    "\t\t\t\tSRQ_Shave := 0;  SRQ_ExecFail := 0;\n\t\t\t\tSCT_RunBed( SRQ_Tag, \"\" );\n\t\t\t\tRollFileSuffix := SRQ_Tag;\n\t\t\t\tput SCT_Info;\n\t\t\t\tput \"FRQ summary:",
    "\t\t\t\tif FRQ_PlanLog = 1 then\n"
    "\t\t\t\t\tif FileExists( SRQ_PlanCSVName ) then FileDelete( SRQ_PlanCSVName ); endif;\n"
    "\t\t\t\t\tSRQ_PlanCSV.PageWidth := 32767;\n"
    "\t\t\t\t\tput SRQ_PlanCSV;\n"
    "\t\t\t\t\tput \"now,slot,soc1_pct,batt1_kW,exp1_kW,imp1_kW,soc2_pct,batt2_kW,exp2_kW,imp2_kW,pv_kW,load_kW,pcc_P_kW,pcc_Q_kvar\" / ;\n"
    "\t\t\t\t\tputclose SRQ_PlanCSV;\n"
    "\t\t\t\tendif;\n"
    "\t\t\t\tSRQ_Shave := 0;  SRQ_ExecFail := 0;\n\t\t\t\tSCT_RunBed( SRQ_Tag, \"\" );\n\t\t\t\tRollFileSuffix := SRQ_Tag;\n\t\t\t\tput SCT_Info;\n\t\t\t\tput \"FRQ summary:",
    "runner plan-log header")
src = sub(src,
    T*3 + "Parameter FRQ_SweepAll {\n",
    T*3 + "Parameter FRQ_PlanLog {\n" + T*4 + "Comment: \"1 = log the window plan at every step (demonstration runs, SRQ_plan<tag>.csv).\";\n" + T*3 + "}\n"
    + T*3 + "Parameter FRQ_SweepAll {\n",
    "declaration")
AMS.write_bytes(src.encode("utf-8"))
print("patched", AMS)
