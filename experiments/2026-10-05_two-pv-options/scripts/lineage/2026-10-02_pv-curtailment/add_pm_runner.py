"""Add the afternoon runner SCT_PVC_TR4_PM to the patched test copy (after add_pvc.py). Runner only, no model change."""
from pathlib import Path

AMS = Path(__file__).resolve().parents[1] / "model" / "MainProject" / "OPF.ams"
src = AMS.read_bytes().decode("utf-8")
if "SCT_PVC_TR4_PM" in src:
    raise SystemExit("already added - nothing written")
anchor = "\t\tProcedure SCT_PVC_TR4_Noon {\r\n"
assert src.count(anchor) == 1
new = ("\t\tProcedure SCT_PVC_TR4_PM {\r\n"
       "\t\t\tBody: {\r\n"
       "\t\t\t\tRollSweepFrom := 27;  RollMaxPeriods := 40;\r\n"
       "\t\t\t\tSCT_PVC_Run( 1, \"_PVC_pm\" );\r\n"
       "\t\t\t\tRollSweepFrom := 0;   RollMaxPeriods := 0;\r\n"
       "\t\t\t}\r\n"
       "\t\t\tComment: \"Afternoon: curtailment ON, sweep + regret at steps 27-40 (the rest of the sunny hours).\";\r\n"
       "\t\t}\r\n")
AMS.write_bytes(src.replace(anchor, new + anchor).encode("utf-8"))
print("added")
