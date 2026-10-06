"""TSO-request stress test: add the request mode, executed PV curtailment and coordinated (two-step) P1
to the test copy of OPF.ams (a copy of the Option B model, ../2026-10-02_pv-curtailment-surplus/model).

Edits only experiments/2026-10-02_tso-request-stress/model/MainProject/OPF.ams. Every replacement must match
exactly once, otherwise nothing is written. Run once.

What is added (all inert unless SRQ_Mode = 1 / SRQ_Coord = 1):
  1. Requests in kW: at each request period the TSO asks for a change (dP, dQ) of the transformer exchange
     from the no-service point S0. A "ray" solve finds the largest fraction lambda <= 1 that fits (with every
     limit and the self-consumption rule), then P1 is re-planned pinned at S0 + lambda*(dP, dQ) - the same
     commitment the closed loop already uses - and the next step executes it at slot 1.
  2. Executed curtailment: the PV cut committed for the service slot is applied at slot 1 of the next step
     (PVC_Exec), in the battery current coupling and in the meter balance.
  3. Coordinated P1 (SRQ_Coord = 1): after the normal P1 solve, a second solve keeps every house's import in
     every slot at or below the first solve and the battery throughput at or below it, and minimises the sum
     of squared exports - so the batteries charge when the PV surplus is largest instead of at sunrise.
"""
from pathlib import Path

AMS = Path(__file__).resolve().parents[1] / "model" / "MainProject" / "OPF.ams"
NL = "\r\n"
src = AMS.read_bytes().decode("utf-8")
if "SRQ_Mode" in src:
    raise SystemExit("already patched (SRQ_Mode found) - nothing written")


def sub(text, old, new, label):
    old, new = old.replace("\n", NL), new.replace("\n", NL)
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected 1 match, found {n} - nothing written")
    return text.replace(old, new)


T = "\t"

# ---------------------------------------------------------------- 1. executed curtailment in the physics
src = sub(src,
    "Definition: BattP_Balance(bat,t) + PVC_Cut(bat,t)=Vre0(",
    "Definition: BattP_Balance(bat,t) + PVC_Cut(bat,t) + PVC_ExecT(bat,t)=Vre0(",
    "Pbat")
src = sub(src,
    "+ sum(bat|BattBus(bat)=n and BattPhase(bat)=f,PVC_Cut(bat,t))\n",
    "+ sum(bat|BattBus(bat)=n and BattPhase(bat)=f,PVC_Cut(bat,t) + PVC_ExecT(bat,t))\n",
    "TotPcust")

# ---------------------------------------------------------------- 2. apply the committed cut at slot 1
src = sub(src,
    T*5 + "RollSvcExec := RollSvcPend;   ! does slot 1 of THIS step carry a committed service?\n",
    T*5 + "RollSvcExec := RollSvcPend;   ! does slot 1 of THIS step carry a committed service?\n"
    + T*5 + "PVC_Exec(bat) := if RollSvcMode > 0 and RollSvcExec = 1 then SRQ_CutCommit(bat) else 0 endif;   ! SRQ: committed PV cut executed at slot 1\n",
    "exec cut")

# ---------------------------------------------------------------- 3. coordinated P1, right after the baseline
coord = """					! ---- TSO-REQUEST STRESS TEST: proof of program type and solver, once per run ----
					if SRQ_Mode = 1 and SCT_Checked = 0 then
						run SCT_TypeCheck;
						run SRQ_TypeCheck;
					endif;
					! ---- COORDINATED P1 (SRQ_Coord = 1): same purchases, charging moved to the PV surplus peak.
					! ---- Step 1 (the solve above) fixes what each house buys in every slot; step 2 keeps every
					! ---- import and the battery throughput at or below step 1 and minimises the squared exports.
					if SRQ_Mode = 1 and RollSvcExec = 1 and ConvFlag <> 'Optimal' and ConvFlag <> 'LocallyOptimal' then
						! the committed service cannot be executed from this state: release slot 1, plain self-consumption,
						! and record it (the realised point then differs from the committed one and the analysis flags it)
						SRQ_ExecFail := SRQ_ExecFail + 1;
						put SCT_Info;
						put "EXECFAIL at step ", RollNow:3:0, ": committed service released, baseline status ", ConvFlag / ;
						putclose SCT_Info;
						BattP_Chg(bat,'1').nonvar := 0;
						BattP_Dis(bat,'1').nonvar := 0;
						Qinv(bat,'1')             := 0;
						Qinv(bat,'1').nonvar      := 1;
						PVC_Exec(bat)             := 0;
						RollSvcExec               := 0;
						run MinOFminImports;
					endif;
					if SRQ_Mode = 1 and SRQ_Sweep = 1 then   ! demonstration runs: the step-1 plan of the whole window
						SRQ_PSOC1(tGMP) := 100*sum(bat, BattSOC(bat,tGMP))/max(1, sum(bat, 1));
						SRQ_PBat1(tGMP) := 1000*sum(bat, BattP_Balance(bat,tGMP));
						SRQ_PExp1(tGMP) := 1000*sum(bat, max(0, -TotPcust(BattBus(bat),BattPhase(bat),tGMP)));
						SRQ_PImp1(tGMP) := 1000*sum(bat, max(0,  TotPcust(BattBus(bat),BattPhase(bat),tGMP)));
					endif;
					SRQ_Stat2 := "off";
					if SRQ_Coord = 1 and ( ConvFlag = 'Optimal' or ConvFlag = 'LocallyOptimal' ) then
						SRQ_ImpRef1(bat,tGMP) := max( 0, TotPcust(BattBus(bat),BattPhase(bat),tGMP) );
						SRQ_ThruRef1(bat)     := sum(tGMP, BattP_Chg(bat,tGMP) + BattP_Dis(bat,tGMP));
						SRQ_SOCEnd1(bat)      := BattSOC(bat, Element(Time, nPeriods));
						SRQ_SunStart := 0;
						SRQ_SunEnd   := 0;
						for (tGMP) do
							if SRQ_SunStart = 0 and sum(bat, PVC_Avail(bat,tGMP)) > 1e-7 then SRQ_SunStart := ord(tGMP); endif;
							if SRQ_SunStart > 0 and SRQ_SunEnd = 0 and ord(tGMP) > SRQ_SunStart and sum(bat, PVC_Avail(bat,tGMP)) <= 1e-7 then SRQ_SunEnd := ord(tGMP) - 1; endif;
						endfor;
						if SRQ_SunStart > 0 and SRQ_SunEnd = 0 then SRQ_SunEnd := nPeriods; endif;
						SRQ_SOCSun1(bat) := if SRQ_SunEnd > 0 then BattSOC(bat, Element(Time, SRQ_SunEnd)) else 0 endif;
						SRQ_Exp2Ref1          := sum((bat,tGMP), (SRQ_ExpScale*ExportedPnode(BattBus(bat),BattPhase(bat),tGMP))^2) / SRQ_ExpScale;
						SRQ_Stage2 := 1;
						solve SRQ_P1Coord
							where  method     := 'deterministic concurrent',
							       time_limit := 3000;
						SRQ_Stage2 := 0;
						SRQ_Stat2  := SRQ_P1Coord.ProgramStatus;
						if SRQ_Stat2 <> 'Optimal' and SRQ_Stat2 <> 'LocallyOptimal' then
							run MinOFminImports;   ! fall back to the step-1 plan, so the executed dispatch is always P1's
						endif;
						put SRQ_P1CSV;
						put RollNow:3:0, ",", ConvFlag, ",", SRQ_Stat2, ",", SRQ_Exp2Ref1:14:6, ",",
						    (sum((bat,tGMP), (SRQ_ExpScale*ExportedPnode(BattBus(bat),BattPhase(bat),tGMP))^2) / SRQ_ExpScale):14:6, ",",
						    (1000*sum(bat, BattP_Chg(bat,'1'))):12:6, ",",
						    (1000*DeltaT*sum((bat,tGMP), max(0, TotPcust(BattBus(bat),BattPhase(bat),tGMP)))):12:6, ",",
						    (1000*DeltaT*sum((bat,tGMP), SRQ_ImpRef1(bat,tGMP))):12:6, ",",
						    (100*sum(bat, SRQ_SOCEnd1(bat))/max(1, sum(bat, 1))):10:4, ",", (100*sum(bat, BattSOC(bat, Element(Time, nPeriods)))/max(1, sum(bat, 1))):10:4, ",",
						    SRQ_SunEnd:3:0, ",", (100*sum(bat, SRQ_SOCSun1(bat))/max(1, sum(bat, 1))):10:4 / ;
						putclose SRQ_P1CSV;
					endif;
"""
anchor_base = (T*5 + "if BaseNoNetwork = 1 then\n"
               + T*6 + "IncludeNetworkConstraints := 1;          ! network back ON before the sweep instance generates below\n"
               + T*5 + "endif;\n")
src = sub(src, anchor_base, anchor_base + coord, "coordinated P1")

# ---------------------------------------------------------------- 4. the request: ray solve, commitment, log
rebuild = """						empty allvariables;
						run Load_data_reset;
						P0(d,tt)        := P0raw(d, RollMap(tt));
						Q0(d,tt)        := Q0raw(d, RollMap(tt));
						GenP0(d,tt)     := GenP0raw(d, RollMap(tt));
						Irradiance(tt)  := Irrraw(RollMap(tt));
						BattSOCini(bat) := BattSOCstart(bat);
						if SOCFloorOverride >= 0 then BattSOCmin(bat) := SOCFloorOverride; endif;
						BattP_Chg(bat,'1')        := RollChgExec(bat);
						BattP_Chg(bat,'1').nonvar := 1;
						BattP_Dis(bat,'1')        := RollDisExec(bat);
						BattP_Dis(bat,'1').nonvar := 1;
						if RollSvcMode > 0 and RollSvcExec = 1 then
							Qinv(bat,'1')        := RollSvcQ(bat);
							Qinv(bat,'1').nonvar := 1;
						endif;
"""
req = ("""					! ---- TSO-REQUEST STRESS TEST (SRQ_Mode = 1): the TSO asks for a change (dP, dQ) of the transformer
					! ---- exchange from the no-service point S0 at this step's service slot. The ray solve finds the
					! ---- largest fraction lambda <= 1 of it that fits every limit and the self-consumption rule; P1 is
					! ---- then re-planned pinned at S0 + lambda*(dP, dQ), and the next step executes that dispatch.
					if SRQ_Mode = 1 then
						RollSvcTgt  := mod(RollNow, nPeriods) + 1;
						RollSvcPend := 0;
					endif;
					if SRQ_Mode = 1 and RollSvcActive( Element(Time, RollSvcTgt) ) = 1 then
						SRQ_ReqP    := SRQ_dP( Element(Time, RollSvcTgt) );
						SRQ_ReqQ    := SRQ_dQ( Element(Time, RollSvcTgt) );
						SRQ_S0P     := RollBaseP;
						SRQ_S0Q     := RollBaseQ;
						FairActive  := 1;
						SCRefActive := 1;
""" + rebuild + """						SRQ_RayOn := 1;
						solve SRQ_Ray
							where  method     := 'deterministic concurrent',
							       time_limit := 3000;
						SRQ_RayStat := SRQ_Ray.ProgramStatus;
						SRQ_Lam     := 0;
						if SRQ_RayStat = 'Optimal' or SRQ_RayStat = 'LocallyOptimal' then
							SRQ_Lam := sum(ax, SRQ_Lambda(ax));   ! read BEFORE the gate closes: outside its domain it reads 0
						endif;
						SRQ_RayOn   := 0;
						SRQ_Try     := 0;
						SRQ_Back    := 0;
						RollSvcStat := "none";
						while SRQ_Lam > 1e-4 and SRQ_Try < 7 and RollSvcStat <> 'Optimal' and RollSvcStat <> 'LocallyOptimal' do
							SRQ_Try  := SRQ_Try + 1;
							if SRQ_Try = 1 then
								SRQ_Back := 0.999;
							elseif SRQ_Try = 2 then
								SRQ_Back := 0.98;
							elseif SRQ_Try = 3 then
								SRQ_Back := 0.95;
							elseif SRQ_Try = 4 then
								SRQ_Back := 0.9;
							elseif SRQ_Try = 5 then
								SRQ_Back := 0.8;
							elseif SRQ_Try = 6 then
								SRQ_Back := 0.65;
							else
								SRQ_Back := 0.5;
							endif;
""" + rebuild.replace("\t\t\t\t\t\t", "\t\t\t\t\t\t\t") + """							RollSvcReqPcur := SRQ_S0P + SRQ_Back*SRQ_Lam*SRQ_ReqP;
							RollSvcReqQcur := SRQ_S0Q + SRQ_Back*SRQ_Lam*SRQ_ReqQ;
							RollSvcPinOn   := 1;
							solve MinImports
								where  MIP_Relative_Optimality_Tolerance := 0.01,
								       method     := 'deterministic concurrent',
								       time_limit := 3000;
							RollSvcPinOn := 0;
							RollSvcStat  := MinImports.ProgramStatus;
							! a battery may not charge and discharge in the same half-hour: when the batteries are full the
							! pinned P1 can 'absorb' energy through their losses that way; such a commitment is refused and
							! the request reduced (back-off) until none is needed
							SRQ_Cyc := 1000*sum(bat, min(BattP_Chg(bat,PeriodMaxP), BattP_Dis(bat,PeriodMaxP)));
							if ( RollSvcStat = 'Optimal' or RollSvcStat = 'LocallyOptimal' ) and SRQ_Cyc > SRQ_CycTol then
								RollSvcStat := "Cycling";
							endif;
						endwhile;
						if RollSvcStat = 'Optimal' or RollSvcStat = 'LocallyOptimal' then
							! shaved to the physical SOC band seen from the SOC the next step will start from (clamped like
							! BattSOCstart): a commitment that fills a battery to its ceiling lands a solver tolerance above it
							! when re-applied by arithmetic, and the next baseline is then infeasible (seen 3 times: 12:00 after an
							! 'export less' request). Costs at most a fraction of a Wh; RollExecCap does the same for the baseline.
							SRQ_SOCc(bat)      := min( BattSOCmaxPhys(bat) - RollSOCEps, max( BattSOCmin(bat) + RollSOCEps, RollSOCnext(bat) ) );
							RollSvcChg(bat)    := min( BattP_Chg(bat,PeriodMaxP),
							                           max( 0, (BattSOCmaxPhys(bat) - RollSOCEps - SRQ_SOCc(bat))*BattEcap(bat)/(etaChg(bat)*DeltaT) ) );
							RollSvcDis(bat)    := min( BattP_Dis(bat,PeriodMaxP),
							                           max( 0, (SRQ_SOCc(bat) - BattSOCmin(bat) - RollSOCEps)*BattEcap(bat)*etaDis(bat)/DeltaT ) );
							SRQ_Shave          := SRQ_Shave + 1000*DeltaT*sum(bat, (BattP_Chg(bat,PeriodMaxP) - RollSvcChg(bat)) + (BattP_Dis(bat,PeriodMaxP) - RollSvcDis(bat)));
							RollSvcQ(bat)      := Qinv(bat,PeriodMaxP);
							SRQ_CutCommit(bat) := PVC_Cut(bat,PeriodMaxP);
							RollSvcDelP        := P_PCC(PeriodMaxP);
							RollSvcDelQ        := Q_PCC(PeriodMaxP);
							RollSvcReqP( Element(Time,RollSvcTgt) ) := RollSvcReqPcur;
							RollSvcReqQ( Element(Time,RollSvcTgt) ) := RollSvcReqQcur;
							RollSvcPend        := 1;
						else
							SRQ_CutCommit(bat) := 0;
							RollSvcDelP := SRQ_S0P;
							RollSvcDelQ := SRQ_S0Q;
							SRQ_Back    := 0;
							RollSvcPend := 0;
						endif;
						put SRQ_CSV;
						put RollNow:3:0, ",", RollSvcTgt:3:0, ",", (1000*SRQ_ReqP):12:6, ",", (1000*SRQ_ReqQ):12:6, ",",
						    (1000*SRQ_S0P):12:6, ",", (1000*SRQ_S0Q):12:6, ",", SRQ_Lam:10:6, ",", SRQ_RayStat, ",",
						    RollSvcStat, ",", SRQ_Try:2:0, ",", SRQ_Back:6:3, ",",
						    (1000*RollSvcDelP):12:6, ",", (1000*RollSvcDelQ):12:6, ",",
						    (1000*(RollSvcDelP - SRQ_S0P)):12:6, ",", (1000*(RollSvcDelQ - SRQ_S0Q)):12:6, ",",
						    (1000*RollSvcPend*sum(bat, SRQ_CutCommit(bat))):12:6, ",",
						    (1000*RollSvcPend*sum(bat, RollSvcChg(bat))):12:6, ",", (1000*RollSvcPend*sum(bat, RollSvcDis(bat))):12:6, ",",
						    (1000*RollSvcPend*sum(bat, RollSvcQ(bat))):12:6, ",",
						    (1000*sum(bat, PVC_Avail(bat,PeriodMaxP))):12:6, ",", (1000*sum(bat, PVC_Cap(bat,PeriodMaxP))):12:6, ",",
						    (100*sum(bat, RollSOCnext(bat))/max(1, sum(bat, 1))):10:4, ",", SRQ_Cyc:10:4 / ;
						putclose SRQ_CSV;
						FairActive  := 0;
						SCRefActive := 0;
					endif;

""")
anchor_regret = T*5 + "! ---- SC-SAFE TEST (SCT_On = 1 only): what does each offered point cost self-consumption later?\n"
src = sub(src, anchor_regret, req + anchor_regret, "request block")

# ---------------------------------------------------------------- 5. per-house executed log: cut and PV at slot 1
src = sub(src,
    "(1000*DeltaT*BattP_Balance(bat,'1')):12:6 / ;",
    "(1000*DeltaT*BattP_Balance(bat,'1')):12:6, \",\", (1000*DeltaT*PVC_Exec(bat)):12:6, \",\", (1000*DeltaT*PVC_Avail(bat,'1')):12:6 / ;",
    "exec row")
src = sub(src,
    "put \"now,battery,svc,base_status,soc_start,imp1_kWh,exp1_kWh,imp_plan_fut_kWh,batt1_kWh\" / ;",
    "put \"now,battery,svc,base_status,soc_start,imp1_kWh,exp1_kWh,imp_plan_fut_kWh,batt1_kWh,cut1_kWh,pv1_kWh\" / ;",
    "exec header")

# ---------------------------------------------------------------- 6. declarations
decl = """		DeclarationSection SRQ_Declarations {
			Comment: {
				"TSO-REQUEST STRESS TEST (2026-10-02, experiments/2026-10-02_tso-request-stress). Requests in kW
				read from scenario.txt, delivered as far as they fit (ray solve + pinned P1 commitment, executed at
				slot 1 of the next step, PV cut included), and an optional coordinated P1 (two steps: same
				purchases, charging moved to the PV surplus peak). Everything here is inert at SRQ_Mode = 0 and
				SRQ_Coord = 0: the gated rows have empty domains and PVC_Exec is 0."
			}
			Parameter SRQ_Mode {
				Default: 0;
				Comment: "1 = serve the TSO requests SRQ_dP/SRQ_dQ at the periods in RollSvcPeriodsCSV (needs RollSvcMode = 4).";
			}
			Parameter SRQ_Coord {
				Default: 0;
				Comment: "1 = coordinated P1: a second solve after the normal P1 keeps every import and the battery throughput at or below it and minimises the squared exports.";
			}
			Parameter SRQ_dP {
				IndexDomain: t;
				Comment: "Requested change of the transformer active power at REAL period t, p.u. from S0 (+ = more import / less export).";
			}
			Parameter SRQ_dQ {
				IndexDomain: t;
				Comment: "Requested change of the transformer reactive power at REAL period t, p.u. from S0.";
			}
			StringParameter SRQ_Tag;
			StringParameter SRQ_Periods;
			Parameter SRQ_MaxPer;
			Parameter SRQ_Sweep {
				Comment: "1 = also sweep the 12-direction FOR at every step (demonstration runs); 0 = stress runs (requests only).";
			}
			Parameter SRQ_ReqP;
			Parameter SRQ_ReqQ;
			Parameter SRQ_S0P;
			Parameter SRQ_S0Q;
			Parameter SRQ_Lam;
			Parameter SRQ_Try;
			Parameter SRQ_Back;
			StringParameter SRQ_RayStat;
			StringParameter SRQ_Stat2;
			Parameter SRQ_RayOn {
				Comment: "Runtime gate of the ray rows: 1 only around the ray solve.";
			}
			Parameter SRQ_RayTol {
				Default: 1e-5;
				Comment: "Half-width of the ray band at the transformer, p.u. (1e-5 = 10 W).";
			}
			Variable SRQ_Lambda {
				IndexDomain: ax | SRQ_RayOn and ord(ax) = 1;
				Range: [0, 1];
				Comment: "Fraction of the request delivered. One column during the ray solve, none otherwise.";
			}
			Variable SRQ_Obj {
				Range: free;
			}
			Constraint SRQ_ObjDef {
				IndexDomain: ax | SRQ_RayOn and ord(ax) = 1;
				Definition: SRQ_Obj = -SRQ_Lambda(ax);
			}
			Constraint SRQ_RayPlo {
				IndexDomain: ax | SRQ_RayOn and ord(ax) = 1;
				Definition: P_PCC(PeriodMaxP) >= SRQ_S0P + SRQ_Lambda(ax)*SRQ_ReqP - SRQ_RayTol;
			}
			Constraint SRQ_RayPhi {
				IndexDomain: ax | SRQ_RayOn and ord(ax) = 1;
				Definition: P_PCC(PeriodMaxP) <= SRQ_S0P + SRQ_Lambda(ax)*SRQ_ReqP + SRQ_RayTol;
			}
			Constraint SRQ_RayQlo {
				IndexDomain: ax | SRQ_RayOn and ord(ax) = 1;
				Definition: Q_PCC(PeriodMaxP) >= SRQ_S0Q + SRQ_Lambda(ax)*SRQ_ReqQ - SRQ_RayTol;
			}
			Constraint SRQ_RayQhi {
				IndexDomain: ax | SRQ_RayOn and ord(ax) = 1;
				Definition: Q_PCC(PeriodMaxP) <= SRQ_S0Q + SRQ_Lambda(ax)*SRQ_ReqQ + SRQ_RayTol;
			}
			MathematicalProgram SRQ_Ray {
				Objective: SRQ_Obj;
				Direction: minimize;
				Constraints: NotTobeExcluded_constraints;
				Variables: NotTobeExcluded_variables;
				Type: Automatic;
				Comment: "Largest fraction of the request that fits: every model constraint, the self-consumption rule (SCRefActive = 1) and PV curtailment (Option B) included.";
			}
			Parameter SRQ_CutCommit {
				IndexDomain: bat;
				Comment: "PV cut committed for the service slot, executed at slot 1 of the next step, p.u.";
			}
			Parameter PVC_Exec {
				IndexDomain: bat;
				Comment: "PV cut executed at slot 1 of the current step (= SRQ_CutCommit of the previous step when it carries a service), p.u.";
			}
			Parameter PVC_ExecT {
				IndexDomain: (bat,t);
				Definition: if ord(t) = 1 then PVC_Exec(bat) else 0 endif;
				Comment: "PVC_Exec placed at slot 1; enters Pbat and TotPcust like PVC_Cut does at the service slot.";
			}
			Parameter SRQ_Stage2 {
				Comment: "Runtime gate of the coordinated-P1 rows: 1 only around the second P1 solve.";
			}
			Parameter SRQ_ExpScale {
				Default: 1000;
				Comment: "Scale of the squared-export objective: exports in kW inside the square, divided by 1000 outside.";
			}
			Parameter SRQ_ImpRef1 {
				IndexDomain: (bat,t);
				Comment: "Import of each house in each slot in the first P1 solve, p.u. The second solve may not exceed it.";
			}
			Parameter SRQ_ThruRef1 {
				IndexDomain: bat;
				Comment: "Battery throughput (charge + discharge) over the window in the first P1 solve, p.u. The second solve may not exceed it, so it cannot burn energy in simultaneous cycling to cut exports.";
			}
			Parameter SRQ_Exp2Ref1;
			Parameter SRQ_Cyc {
				Comment: "Simultaneous charge and discharge in the last commitment solve, summed over the batteries, kW.";
			}
			Parameter SRQ_CycTol {
				Default: 0.5;
				Comment: "Largest simultaneous charge+discharge accepted in a commitment, kW over the feeder.";
			}
			Parameter SRQ_PSOC1 {
				IndexDomain: t;
			}
			Parameter SRQ_PBat1 {
				IndexDomain: t;
			}
			Parameter SRQ_PExp1 {
				IndexDomain: t;
			}
			Parameter SRQ_PImp1 {
				IndexDomain: t;
			}
			Parameter SRQ_PSOC2 {
				IndexDomain: t;
			}
			Parameter SRQ_PBat2 {
				IndexDomain: t;
			}
			Parameter SRQ_PExp2 {
				IndexDomain: t;
			}
			Parameter SRQ_PImp2 {
				IndexDomain: t;
			}
			StringParameter SRQ_PlanCSVName {
				Definition: "SRQ_plan" + RollFileSuffix + ".csv";
			}
			File SRQ_PlanCSV {
				Name: SRQ_PlanCSVName;
				Mode: append;
			}
			Parameter SRQ_SOCc {
				IndexDomain: bat;
				Comment: "SOC the next step starts from, clamped as BattSOCstart is (working).";
			}
			Parameter SRQ_Shave {
				Comment: "Energy shaved off committed set-points in the run, kWh (should be tolerance-sized).";
			}
			Parameter SRQ_ExecFail {
				Comment: "Committed services that could not be executed in the run (released, see EXECFAIL lines in SCT_info).";
			}
			Parameter SRQ_SunStart;
			Parameter SRQ_SunEnd {
				Comment: "Window slot (ord) of the last PV half-hour of the first sunny period in the window; 0 = no PV in the window.";
			}
			Parameter SRQ_SOCSun1 {
				IndexDomain: bat;
				Comment: "SOC of each battery at SRQ_SunEnd in the first P1 solve.";
			}
			Parameter SRQ_SOCEnd1 {
				IndexDomain: bat;
				Comment: "End-of-window SOC of each battery in the first P1 solve.";
			}
			Parameter SRQ_CapTolKW {
				Default: 0;
				Comment: "Tolerance of the coordinated-P1 caps, kW. 0: the step-1 plan satisfies its own caps exactly, and any slack is used by step 2 to export less by importing more (1e-4 kW gave +0.07 kWh over the window). Written in kW so the solver's feasibility tolerance (1e-6) is 1 mW per house and slot.";
			}
			Variable SRQ_Obj2 {
				Range: free;
			}
			Constraint SRQ_Obj2Def {
				IndexDomain: ax | SRQ_Stage2 and ord(ax) = 1;
				Definition: {
					sum((bat,t), (SRQ_ExpScale*ExportedPnode(BattBus(bat),BattPhase(bat),t))^2) / SRQ_ExpScale
					+ BattThroughputPen*sum((bat,t), BattP_Chg(bat,t) + BattP_Dis(bat,t)) <= SRQ_Obj2
				}
				Comment: "Epigraph of the coordinated objective (convex quadratic, so the program stays a QCP).";
			}
			Constraint SRQ_ImpCap {
				IndexDomain: (bat,t) | SRQ_Stage2;
				Definition: 1000*TotPcust(BattBus(bat),BattPhase(bat),t) <= 1000*SRQ_ImpRef1(bat,t) + SRQ_CapTolKW;
			}
			Constraint SRQ_SunCap {
				IndexDomain: bat | SRQ_Stage2 and SRQ_SunEnd > 0;
				Definition: 1000*sum(t | ord(t) = SRQ_SunEnd, BattSOC(bat,t)) >= 1000*SRQ_SOCSun1(bat);
				Comment: "Each battery is at least as charged as in step 1 at the end of the first sunny period of the window (today's by day, tomorrow's by night): step 2 re-times charging WITHIN that period and cannot push it to the next day. Without it, the batteries never filled (86 % at 16:00) and 30 kWh less PV was stored on the no-service day.";
			}
			Constraint SRQ_EndCap {
				IndexDomain: bat | SRQ_Stage2;
				Definition: 1000*sum(t | ord(t) = nPeriods, BattSOC(bat,t)) >= 1000*SRQ_SOCEnd1(bat);
				Comment: "Each battery ends the window at least as charged as in step 1, so step 2 only re-times: without it, houses with spare energy sold it at night to make room for the next day (no-service day: +30 kWh exports, end SOC 35 % instead of 50 %).";
			}
			Constraint SRQ_ThruCap {
				IndexDomain: bat | SRQ_Stage2;
				Definition: 1000*sum(t, BattP_Chg(bat,t) + BattP_Dis(bat,t)) <= 1000*SRQ_ThruRef1(bat) + SRQ_CapTolKW;
			}
			MathematicalProgram SRQ_P1Coord {
				Objective: SRQ_Obj2;
				Direction: minimize;
				Constraints: NotTobeExcluded_constraints;
				Variables: NotTobeExcluded_variables;
				Type: Automatic;
				Comment: "Coordinated P1, step 2: same imports (or less) in every slot for every house, same throughput (or less), squared exports minimised.";
			}
			StringParameter SRQ_CSVName {
				Definition: "SRQ" + RollFileSuffix + ".csv";
			}
			File SRQ_CSV {
				Name: SRQ_CSVName;
				Mode: append;
			}
			StringParameter SRQ_P1CSVName {
				Definition: "SRQ_p1" + RollFileSuffix + ".csv";
			}
			File SRQ_P1CSV {
				Name: SRQ_P1CSVName;
				Mode: append;
			}
		}
		Procedure SCT_SolveCase {
"""
src = sub(src, "\t\tProcedure SCT_SolveCase {\n", decl, "declarations")

# ---------------------------------------------------------------- 7. runner and type check
runners = """		Procedure SRQ_TypeCheck {
			Body: {
				! the two new programs are QCPs solved by CPLEX: generated with their gated rows switched on
				SCT_Info.PageWidth := 32767;
				put SCT_Info;
				SRQ_Stage2 := 1;
				SCT_GMP    := GMP::Instance::Generate( SRQ_P1Coord, "SRQ_type_P1Coord" );
				SCT_MPType := GMP::Instance::GetMathematicalProgrammingType( SCT_GMP );
				SCT_Solver := GMP::Instance::GetSolver( SCT_GMP );
				put "SRQ_P1Coord    (coordinated P1, step 2)     : type ", SCT_MPType, "   solver ", SCT_Solver / ;
				GMP::Instance::Delete( SCT_GMP );
				SRQ_Stage2 := 0;
				SRQ_RayOn  := 1;
				SCRefActive := 1;
				SCT_GMP    := GMP::Instance::Generate( SRQ_Ray, "SRQ_type_Ray" );
				SCT_MPType := GMP::Instance::GetMathematicalProgrammingType( SCT_GMP );
				SCT_Solver := GMP::Instance::GetSolver( SCT_GMP );
				put "SRQ_Ray        (largest deliverable share)  : type ", SCT_MPType, "   solver ", SCT_Solver / ;
				GMP::Instance::Delete( SCT_GMP );
				SRQ_RayOn   := 0;
				SCRefActive := 0;
				put "SRQ_Mode ", SRQ_Mode:2:0, "   SRQ_Coord ", SRQ_Coord:2:0, "   requests ", (sum(t, RollSvcActive(t))):3:0,
				    "   RollSvcTol ", RollSvcTol, "   SRQ_RayTol ", SRQ_RayTol, "   BaselineOnly ", BaselineOnly:2:0 / ;
				putclose SCT_Info;
			}
		}
		Procedure SRQ_Run {
			Body: {
				! one TR4 day under the TSO requests in scenario.txt (written by scripts/run_scenarios.py into this
				! project folder before the run): SRQ_Tag, SRQ_Coord, SRQ_Periods, SRQ_dP(t), SRQ_dQ(t), SRQ_MaxPer
				SRQ_Coord := 0;  SRQ_Tag := "";  SRQ_Periods := "";  SRQ_MaxPer := 0;  SRQ_Sweep := 0;
				empty SRQ_dP, SRQ_dQ;
				nPeriods := 48;   ! Time = ElementRange(1, nPeriods) must exist before the scenario's period data is read
				read from file "scenario.txt";
				if SRQ_Tag = "" then halt with "scenario.txt did not set SRQ_Tag"; endif;
				SCFirst := 1;  SCAlpha := 0;  PVC_On := 1;  PVC_Mode := 1;
				PVC_ReplanPen := 3;   ! commitment: cutting surplus PV must cost more than the export it removes is worth to P1
				                      ! (w2 = 1.99 at the service slot; at 1 P1 cut 105 kW for a 60 kW request) and less than
				                      ! absorbing energy through simultaneous charge/discharge losses (about 3.8 per p.u.)
				SRQ_Mode := 1;  RollSvcMode := 4;  RollSvcPeriodsCSV := SRQ_Periods;  RollSvcTol := 1e-4;
				BaselineOnly := 1 - SRQ_Sweep;  SCT_Regret := 0;  SCT_PlanDump := 0;  RollOfferLog := 0;  SCT_Trafo := "TR4";
				RollMaxPeriods := SRQ_MaxPer;
				RollFileSuffix := SRQ_Tag;
				if FileExists( SRQ_CSVName ) then FileDelete( SRQ_CSVName ); endif;
				SRQ_CSV.PageWidth := 32767;
				put SRQ_CSV;
				put "now,target,req_dP_kW,req_dQ_kW,S0_P_kW,S0_Q_kW,lambda,ray_status,commit_status,tries,back,",
				    "del_P_kW,del_Q_kW,del_dP_kW,del_dQ_kW,cut_kW,chg_kW,dis_kW,q_kvar,pv_kW,surplus_kW,soc_mean_pct,cyc_kW" / ;
				putclose SRQ_CSV;
				if FileExists( SRQ_P1CSVName ) then FileDelete( SRQ_P1CSVName ); endif;
				SRQ_P1CSV.PageWidth := 32767;
				put SRQ_P1CSV;
				put "now,stat1,stat2,exp2_step1,exp2_step2,chg1_kW,imp_window_kWh,imp_window_step1_kWh,soc_end_step1_pct,soc_end_pct,sun_end_slot,soc_sun_end_step1_pct" / ;
				putclose SRQ_P1CSV;
				SRQ_Shave := 0;  SRQ_ExecFail := 0;
				if SRQ_Sweep = 1 then
					if FileExists( SRQ_PlanCSVName ) then FileDelete( SRQ_PlanCSVName ); endif;
					SRQ_PlanCSV.PageWidth := 32767;
					put SRQ_PlanCSV;
					put "now,slot,soc1_pct,batt1_kW,exp1_kW,imp1_kW,soc2_pct,batt2_kW,exp2_kW,imp2_kW,pv_kW,load_kW,pcc_P_kW,pcc_Q_kvar" / ;
					putclose SRQ_PlanCSV;
				endif;
				SCT_RunBed( SRQ_Tag, "" );
				RollFileSuffix := SRQ_Tag;   ! SCT_RunBed cleared it; the summary belongs in this run's info file
				put SCT_Info;
				put "SRQ summary: execution failures ", SRQ_ExecFail:3:0, "   energy shaved off commitments ", SRQ_Shave:12:6, " kWh" / ;
				putclose SCT_Info;
				SRQ_Mode := 0;  RollSvcMode := 0;  RollSvcPeriodsCSV := "";  RollSvcTol := 0.001;
				BaselineOnly := 0;  SCT_Regret := 1;  SCFirst := 0;  SCAlpha := 0;  PVC_On := 0;  PVC_Mode := 0;
				PVC_Exec(bat) := 0;  SRQ_CutCommit(bat) := 0;  SCT_Trafo := "";  RollMaxPeriods := 0;  SRQ_Coord := 0;
				PVC_ReplanPen := 10;  RollFileSuffix := "";
			}
			Comment: "One TR4 rolling day, recommended setup + Option B, TSO requests from scenario.txt (kW from the no-service point, delivered as far as they fit), today's P1 (SRQ_Coord = 0) or coordinated P1 (SRQ_Coord = 1).";
		}
		Procedure SCT_TR9_K000 {
"""
src = sub(src, "\t\tProcedure SCT_TR9_K000 {\n", runners, "runners")

# ---------------------------------------------------------------- 8. demonstration runs: executed window plan per step
T = "\t"
agg2 = (T*6 + "SRQ_PSOC2(tGMP) := 100*sum(bat, BattSOC(bat,tGMP))/max(1, sum(bat, 1));\n"
        + T*6 + "SRQ_PBat2(tGMP) := 1000*sum(bat, BattP_Balance(bat,tGMP));\n"
        + T*6 + "SRQ_PExp2(tGMP) := 1000*sum(bat, max(0, -TotPcust(BattBus(bat),BattPhase(bat),tGMP)));\n"
        + T*6 + "SRQ_PImp2(tGMP) := 1000*sum(bat, max(0,  TotPcust(BattBus(bat),BattPhase(bat),tGMP)));\n")
anchor_b = T*5 + "! ---- SC-SAFE TEST (SCT_On = 1 only): B = the service-slot PCC point with NO service called, and\n"
src = sub(src, anchor_b,
    T*5 + "if SRQ_Mode = 1 and SRQ_Sweep = 1 then   ! demonstration runs: the plan that is executed, per window slot\n"
    + agg2
    + T*6 + "put SRQ_PlanCSV;\n"
    + T*6 + "for (tGMP) do\n"
    + T*7 + "put RollNow:3:0, \",\", ord(tGMP):3:0, \",\", SRQ_PSOC1(tGMP):9:3, \",\", SRQ_PBat1(tGMP):10:4, \",\", SRQ_PExp1(tGMP):10:4, \",\", SRQ_PImp1(tGMP):10:4, \",\",\n"
    + T*7 + "    SRQ_PSOC2(tGMP):9:3, \",\", SRQ_PBat2(tGMP):10:4, \",\", SRQ_PExp2(tGMP):10:4, \",\", SRQ_PImp2(tGMP):10:4, \",\",\n"
    + T*7 + "    (1000*sum(bat, PVC_Avail(bat,tGMP))):10:4, \",\",\n"
    + T*7 + "    (1000*sum(bat, sum(d | LoadBus(d) = BattBus(bat) and LoadPhase(d) = BattPhase(bat), P0(d,tGMP)))):10:4, \",\",\n"
    + T*7 + "    (1000*P_PCC(tGMP)):12:4, \",\", (1000*Q_PCC(tGMP)):12:4 / ;\n"
    + T*6 + "endfor;\n"
    + T*6 + "putclose SRQ_PlanCSV;\n"
    + T*5 + "endif;\n"
    + anchor_b, "plan log write")

AMS.write_bytes(src.encode("utf-8"))
print("patched", AMS)
