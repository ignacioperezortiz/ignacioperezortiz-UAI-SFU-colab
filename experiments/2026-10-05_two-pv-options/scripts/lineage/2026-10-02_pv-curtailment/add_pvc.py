"""Add per-prosumer PV curtailment (offered at the service slot) to the test copy of OPF.ams.

Edits only experiments/2026-10-02_pv-curtailment/model/MainProject/OPF.ams. Every replacement must match
exactly once, otherwise the script stops without writing. Run once; a second run refuses (marker check).
"""
from pathlib import Path

AMS = Path(__file__).resolve().parents[1] / "model" / "MainProject" / "OPF.ams"
NL = "\r\n"

src = AMS.read_bytes().decode("utf-8")
if "PVC_Cut" in src:
    raise SystemExit("already patched (PVC_Cut found) - nothing written")


def sub(text, old, new, label):
    old = old.replace("\n", NL)
    new = new.replace("\n", NL)
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected 1 match, found {n} - nothing written")
    return text.replace(old, new)


T = "\t"

# 1. battery current coupling: the curtailed PV is withdrawn at the battery's bus and phase, with the
#    same fixed-V0 power-to-current relation the battery uses (Pbat/Qbat)
src = sub(src,
    T*4 + "Definition: BattP_Balance(bat,t)=Vre0(BattBus(bat),BattPhase(bat),t)*Ire_Batt(bat,t) + Vim0(BattBus(bat),BattPhase(bat),t)*Iim_Batt(bat,t);",
    T*4 + "Definition: BattP_Balance(bat,t) + PVC_Cut(bat,t)=Vre0(BattBus(bat),BattPhase(bat),t)*Ire_Batt(bat,t) + Vim0(BattBus(bat),BattPhase(bat),t)*Iim_Batt(bat,t);\n"
    + T*4 + "Comment: \"PV CURTAILMENT TEST (2026-10-02): PVC_Cut is curtailed PV at this prosumer, withdrawn at the battery's bus and phase with the battery's own fixed-V0 power-current relation. Empty domain (zero) unless PVC_On = 1, so the production rows are unchanged.\";",
    "Pbat")

# 2. the prosumer's net exchange at the meter: curtailing PV raises it (less export / more import)
src = sub(src,
    T*5 + "sum(d|LoadBus(d)=n and LoadPhase(d)=f,P0minGenP(d,t))\n"
    + T*5 + "+ sum(bat|BattBus(bat)=n and BattPhase(bat)=f,BattP_Balance(bat,t))\n",
    T*5 + "sum(d|LoadBus(d)=n and LoadPhase(d)=f,P0minGenP(d,t))\n"
    + T*5 + "+ sum(bat|BattBus(bat)=n and BattPhase(bat)=f,BattP_Balance(bat,t))\n"
    + T*5 + "+ sum(bat|BattBus(bat)=n and BattPhase(bat)=f,PVC_Cut(bat,t))\n",
    "TotPcust")

# 3. sweep objective: tie-break cost on curtailment
src = sub(src,
    T*4 + "                           + BattThroughputPen*sum((bat,t) | ord(t) > PeriodMaxP, BattP_Chg(bat,t)+BattP_Dis(bat,t)) );\n",
    T*4 + "                           + BattThroughputPen*sum((bat,t) | ord(t) > PeriodMaxP, BattP_Chg(bat,t)+BattP_Dis(bat,t)) )\n"
    + T*4 + "            + PVC_SweepPen*sum((bat,t), PVC_Cut(bat,t));\n",
    "OF_FOR_cont")

# 4. P1 objective: curtailment only exists in the pinned regret re-plans; priced high so it is used only
#    when the pinned point needs it
src = sub(src,
    T*5 + "+ PVcutPen*sum(t, PVcut(t))\n" + T*4 + "}\n",
    T*5 + "+ PVcutPen*sum(t, PVcut(t))\n" + T*5 + "+ PVC_ReplanPen*sum((bat,t), PVC_Cut(bat,t))\n" + T*4 + "}\n",
    "OFminImports")

# 5. declarations, before SCT_SolveCase
decl = """		DeclarationSection PVC_Declarations {
			Comment: {
				"PV CURTAILMENT TEST (2026-10-02, experiments/2026-10-02_pv-curtailment). In the production model
				PV is a fixed parameter (GenP0 = PVsize*Irradiance/1000) that is always injected, and each BESS has
				its own inverter (MaxBattS_def holds only BattP_Balance and Qinv), so the FOR contains BESS
				flexibility only. Here every prosumer may also curtail its PV in the SERVICE slot of the
				directional sweep, as extra flexibility on the 'export less' side.
				.
				Where it exists: PVC_On = 1 and (SCRefActive = 1, i.e. the directional sweep, or SCT_PinOn = 1, i.e.
				a pinned regret re-plan) and only at t = PeriodMaxP. Never in the committed P1 baseline, so the
				baseline, SCImpRef and the carried SOC are those of the run without curtailment.
				Network: the curtailed power is withdrawn at the battery's bus and phase through Pbat with the
				battery's fixed-V0 power-to-current relation - the same zero-order term as the PV injection
				(Ire_Gen/Iim_Gen at V0), without the PV's first-order voltage term, which would be bilinear.
				Not inside the BESS S-circle: separate PV and BESS inverters, as in the production model."
			}
			Parameter PVC_On {
				Default: 0;
				Comment: "1 = offer PV curtailment in the service slot of the sweep (and allow it in pinned regret re-plans). 0 = model identical to the copy it came from: PVC_Cut has an empty domain.";
			}
			Parameter PVC_SweepPen {
				Default: 0.01;
				Comment: "Tie-break cost per p.u. of curtailment in the directional objective. Smaller than FOR_ThruPenSlot (0.2) and than any direction weight that matters, so it only decides ties.";
			}
			Parameter PVC_ReplanPen {
				Default: 10;
				Comment: "Cost per p.u. of curtailment in the pinned P1 re-plans (regret check). Far above the P1 weights (w2 <= 2 per import or export), so P1 curtails only what the pinned point needs.";
			}
			Parameter PVC_Avail {
				IndexDomain: (bat,t);
				Definition: sum(d | LoadBus(d) = BattBus(bat) and LoadPhase(d) = BattPhase(bat), GenP0(d,t));
				Comment: "PV output at the prosumer that owns this battery (one load and one PV array per battery bus and phase), p.u.";
			}
			Variable PVC_Cut {
				IndexDomain: (bat,t) | PVC_On and (SCRefActive or SCT_PinOn) and ord(t) = PeriodMaxP;
				Range: [0, PVC_Avail(bat,t)];
				Comment: "PV curtailed at this prosumer in the service slot, p.u. Cannot exceed the PV available there.";
			}
			Parameter SCT_PVCcut;
			StringParameter PVC_CSVName {
				Definition: "PVC_cut" + RollFileSuffix + ".csv";
			}
			File PVC_CSV {
				Name: PVC_CSVName;
				Mode: append;
			}
		}
		Procedure SCT_SolveCase {
"""
src = sub(src, "\t\tProcedure SCT_SolveCase {\n", decl, "declarations")

# 6. regret re-plan: record how much PV the pinned P1 re-plan curtailed
src = sub(src,
    T*4 + "if SCT_Stat = 'Optimal' or SCT_Stat = 'LocallyOptimal' then\n" + T*5 + "SCT_ImpFut  :=",
    T*4 + "SCT_PVCcut := 1000*sum((bat,tGMP), PVC_Cut(bat,tGMP));\n"
    + T*4 + "if SCT_Stat = 'Optimal' or SCT_Stat = 'LocallyOptimal' then\n" + T*5 + "SCT_ImpFut  :=",
    "regret cut")
src = sub(src,
    "SCT_StatIP, \",\", SCT_ImpFutIP:14:6, \",\", SCT_ImpBatMaxIP:12:6, \",\", SCT_NBatRegIP:4:0, \",\", SCT_ImpSlotMaxIP:12:6 / ;",
    "SCT_StatIP, \",\", SCT_ImpFutIP:14:6, \",\", SCT_ImpBatMaxIP:12:6, \",\", SCT_NBatRegIP:4:0, \",\", SCT_ImpSlotMaxIP:12:6, \",\", SCT_PVCcut:12:6 / ;",
    "regret row")
src = sub(src,
    "status_ip,imp_fut_ip_kWh,imp_bat_max_ip_kWh,n_bat_regret_ip,imp_slot_max_ip_kWh\" / ;",
    "status_ip,imp_fut_ip_kWh,imp_bat_max_ip_kWh,n_bat_regret_ip,imp_slot_max_ip_kWh,pvc_cut_kW\" / ;",
    "regret header")

# 7. run info: record the curtailment switches
src = sub(src,
    "\"   FairMode \", FairMode:2:0, \"   RollUseGMP \", RollUseGMP:2:0, \"   UseBattComp \", UseBattComp:2:0 / ;",
    "\"   FairMode \", FairMode:2:0, \"   RollUseGMP \", RollUseGMP:2:0, \"   UseBattComp \", UseBattComp:2:0,\n"
    + T*5 + "    \"   PVC_On \", PVC_On:2:0, \"   PVC_SweepPen \", PVC_SweepPen:8:4, \"   PVC_ReplanPen \", PVC_ReplanPen:8:2 / ;",
    "info")

# 8. per-direction log of curtailment (standard for(ia) sweep path, 6 tabs deep; the async batch path,
#    8 tabs deep, is not used in these runs: RollAsyncK < 2). The leading newline keeps the 8-tab copy out.
anchor = ("\n" + T*6 + "! ---- progress marker, rewritten and flushed to disk after every vertex (see FOR_RollProgress) ----\n")
log = ("\n" + T*6 + "! ---- PV curtailment test: what each prosumer curtailed at this vertex (PVC_On = 1 only) ----\n"
       + T*6 + "if PVC_On = 1 then\n"
       + T*7 + "put PVC_CSV;\n"
       + T*7 + "for (bat) do\n"
       + T*8 + "put RollNow:3:0, \",\", (mod(RollNow,nPeriods)+1):3:0, \",\", FOR_Angle:6:1, \",\", FOR_StatCur, \",\", bat:24, \",\",\n"
       + T*8 + "    (1000*PVC_Avail(bat,Element(Time,PeriodMaxP))):12:6, \",\", (1000*PVC_Cut(bat,Element(Time,PeriodMaxP))):12:6 / ;\n"
       + T*7 + "endfor;\n"
       + T*7 + "putclose PVC_CSV;\n"
       + T*6 + "endif;\n")
src = sub(src, anchor, log + anchor, "per-direction log")

# 9. runners, after SCT_TR4W_H4_Fix
runners = """		Procedure SCT_PVC_Run {
			Arguments: (On,Tag);
			Body: {
				! PV curtailment test: the recommended setup on TR4 (SCFirst = 1, SCAlpha = 0, regret at every
				! vertex) with per-prosumer PV curtailment offered in the service slot when On = 1
				PVC_On         := On;
				SCT_Trafo      := "TR4";  RollOfferLog := 1;  SCT_PlanDump := 1;  SCT_PlanSteps := "2,24,38";
				RollFileSuffix := Tag;
				if FileExists( PVC_CSVName ) then FileDelete( PVC_CSVName ); endif;
				PVC_CSV.PageWidth := 32767;
				put PVC_CSV;
				put "now,target,angle_deg,status,battery,pv_kW,cut_kW" / ;
				putclose PVC_CSV;
				SCT_SC1Run( 0, 1, 0, Tag, "" );
				SCT_Trafo := "";  RollOfferLog := 0;  SCT_PlanDump := 0;  PVC_On := 0;
			}
			Parameter On {
				Property: Input;
			}
			StringParameter Tag {
				Property: Input;
			}
		}
		Procedure SCT_PVC_TR4_On {
			Body: {
				SCT_PVC_Run( 1, "_PVC_on" );
			}
			Comment: "Full TR4 day, recommended setup + PV curtailment in the service slot. Compare with SCT_TR4W_Fix (2026-10-01_tr4-walkthrough, laneB).";
		}
		Procedure SCT_PVC_TR4_Ctrl {
			Body: {
				RollSweepFrom := 22;  RollMaxPeriods := 23;
				SCT_PVC_Run( 0, "_PVC_ctrl" );
				RollSweepFrom := 0;   RollMaxPeriods := 0;
			}
			Comment: "Control: curtailment OFF, baselines 1-23, sweep + regret at 22-23 (midday). Must reproduce SCT_TR4W_Fix at those steps, which shows the edits change nothing when PVC_On = 0.";
		}
		Procedure SCT_PVC_TR4_Noon {
			Body: {
				RollSweepFrom := 22;  RollMaxPeriods := 26;
				SCT_PVC_Run( 1, "_PVC_noon" );
				RollSweepFrom := 0;   RollMaxPeriods := 0;
			}
			Comment: "Early look: curtailment ON, sweep + regret at steps 22-26 only (around midday).";
		}
		Procedure SCT_TR9_K000 {
"""
src = sub(src, "\t\tProcedure SCT_TR9_K000 {\n", runners, "runners")

AMS.write_bytes(src.encode("utf-8"))
print("patched", AMS)
