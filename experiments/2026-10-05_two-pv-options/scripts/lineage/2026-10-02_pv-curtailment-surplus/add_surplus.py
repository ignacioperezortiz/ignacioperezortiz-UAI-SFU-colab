"""Option B: curtail only SURPLUS PV (PV minus the house's own load) in the service slot.

Edits only experiments/2026-10-02_pv-curtailment-surplus/model/MainProject/OPF.ams (a copy of the Option A
model). Adds PVC_Mode (0 = Option A, all PV; 1 = Option B, surplus only) and the bound PVC_Cap. Every
replacement must match exactly once, otherwise nothing is written. Run once.
"""
from pathlib import Path

AMS = Path(__file__).resolve().parents[1] / "model" / "MainProject" / "OPF.ams"
NL = "\r\n"
src = AMS.read_bytes().decode("utf-8")
if "PVC_Mode" in src:
    raise SystemExit("already patched (PVC_Mode found) - nothing written")


def sub(text, old, new, label):
    old, new = old.replace("\n", NL), new.replace("\n", NL)
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected 1 match, found {n} - nothing written")
    return text.replace(old, new)


T = "\t"

# 1. the switch and the bound, declared right before PVC_Cut
src = sub(src,
    T*3 + "Variable PVC_Cut {\n",
    T*3 + "Parameter PVC_Mode {\n"
    + T*4 + "Default: 0;\n"
    + T*4 + "Comment: \"0 = Option A: a prosumer may cut all its PV. 1 = Option B: only the SURPLUS, PV minus the house's own load in that slot, so a request never makes the house buy for its own use (2026-10-02).\";\n"
    + T*3 + "}\n"
    + T*3 + "Parameter PVC_Cap {\n"
    + T*4 + "IndexDomain: (bat,t);\n"
    + T*4 + "Definition: {\n"
    + T*5 + "if PVC_Mode = 1 then\n"
    + T*6 + "max(0, sum(d | LoadBus(d) = BattBus(bat) and LoadPhase(d) = BattPhase(bat), GenP0(d,t) - P0(d,t)))\n"
    + T*5 + "else\n"
    + T*6 + "PVC_Avail(bat,t)\n"
    + T*5 + "endif\n"
    + T*4 + "}\n"
    + T*4 + "Comment: \"Upper bound of PVC_Cut, p.u.: all the PV (Option A) or the surplus over the house's own load (Option B).\";\n"
    + T*3 + "}\n"
    + T*3 + "Variable PVC_Cut {\n",
    "declarations")

# 2. the variable's bound
src = sub(src, T*4 + "Range: [0, PVC_Avail(bat,t)];", T*4 + "Range: [0, PVC_Cap(bat,t)];", "range")

# 3. log the bound next to the PV and the cut
src = sub(src,
    "(1000*PVC_Avail(bat,Element(Time,PeriodMaxP))):12:6, \",\", (1000*PVC_Cut(bat,Element(Time,PeriodMaxP))):12:6 / ;",
    "(1000*PVC_Avail(bat,Element(Time,PeriodMaxP))):12:6, \",\", (1000*PVC_Cut(bat,Element(Time,PeriodMaxP))):12:6, \",\", (1000*PVC_Cap(bat,Element(Time,PeriodMaxP))):12:6 / ;",
    "log row")
src = sub(src,
    "put \"now,target,angle_deg,status,battery,pv_kW,cut_kW\" / ;",
    "put \"now,target,angle_deg,status,battery,pv_kW,cut_kW,cap_kW\" / ;",
    "log header")

# 4. run info
src = sub(src,
    "\"   PVC_On \", PVC_On:2:0, \"   PVC_SweepPen \"",
    "\"   PVC_On \", PVC_On:2:0, \"   PVC_Mode \", PVC_Mode:2:0, \"   PVC_SweepPen \"",
    "info")

# 5. runners
runners = """		Procedure SCT_PVCB_Run {
			Arguments: (Mode,Tag);
			Body: {
				PVC_Mode := Mode;
				SCT_PVC_Run( 1, Tag );
				PVC_Mode := 0;
			}
			Parameter Mode {
				Property: Input;
			}
			StringParameter Tag {
				Property: Input;
			}
		}
		Procedure SCT_PVCB_TR4_AM {
			Body: {
				RollSweepFrom := 7;   RollMaxPeriods := 21;
				SCT_PVCB_Run( 1, "_PVCB_am" );
				RollSweepFrom := 0;   RollMaxPeriods := 0;
			}
			Comment: "Option B (surplus only), sweep + regret at steps 7-21 (sunrise to 11:00).";
		}
		Procedure SCT_PVCB_TR4_Mid {
			Body: {
				RollSweepFrom := 22;  RollMaxPeriods := 40;
				SCT_PVCB_Run( 1, "_PVCB_mid" );
				RollSweepFrom := 0;   RollMaxPeriods := 0;
			}
			Comment: "Option B (surplus only), sweep + regret at steps 22-40 (11:00 to 20:30).";
		}
		Procedure SCT_PVCB_TR4_Ctrl {
			Body: {
				RollSweepFrom := 22;  RollMaxPeriods := 23;
				SCT_PVCB_Run( 0, "_PVCB_ctrl" );
				RollSweepFrom := 0;   RollMaxPeriods := 0;
			}
			Comment: "Control: PVC_Mode = 0 (Option A) at steps 22-23. Must reproduce the Option A run (_PVC_noon) there.";
		}
		Procedure SCT_TR9_K000 {
"""
src = sub(src, "\t\tProcedure SCT_TR9_K000 {\n", runners, "runners")

AMS.write_bytes(src.encode("utf-8"))
print("patched", AMS)
