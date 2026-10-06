"""FOR-first TSO requests: the TSO picks any point inside the published FOR, and the DSO recovers the
set-points by a convex combination of stored solutions (no new optimisation) - the recovery of the
methodology draft (proposition: convex combination of the no-service solution and two adjacent corners).

Edits only experiments/2026-10-04_for-requests/model/MainProject/OPF.ams (a copy of the stress-test model).
Every replacement must match exactly once, otherwise nothing is written. Run once.

At a half-hour with a TSO request (SRQ_Mode = 2):
  1. the 12-direction FOR is swept as usual; for every corner the slot-2 set-points (charge, discharge,
     reactive power, PV cut) are stored next to the corner's transformer point;
  2. the published FOR is the polygon of the no-service point S0 and the 12 corners, split into triangles
     (S0, V_i, V_next); the TSO's point is drawn uniformly over its area from three numbers fixed in the
     scenario (u1 picks the triangle by area, u2/u3 the place inside it; an "edge" request puts it on the
     outer edge V_i-V_next);
  3. the committed set-points are a0*x0 + a1*x_i + a2*x_next (the point's weights); a battery that would both
     charge and discharge executes only its net power (same power at the transformer); set-points are kept
     inside the battery's SOC band (tolerance-sized shave, reported);
  4. the next step executes them at slot 1 (batteries, inverters, PV cut) and the realised transformer point
     is compared with the chosen one.
FRQ_SweepAll = 0 sweeps the FOR only at request half-hours (a FOR nobody uses changes nothing later, so the
results are the same); FRQ_SweepAll = 1 sweeps every half-hour (reference days for the FOR over the day).
"""
from pathlib import Path

AMS = Path(__file__).resolve().parents[1] / "model" / "MainProject" / "OPF.ams"
NL = "\r\n"
src = AMS.read_bytes().decode("utf-8")
if "FRQ_SweepAll" in src:
    raise SystemExit("already patched (FRQ_SweepAll found) - nothing written")


def sub(text, old, new, label):
    old, new = old.replace("\n", NL), new.replace("\n", NL)
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected 1 match, found {n} - nothing written")
    return text.replace(old, new)


T = "\t"

# 1. modes 1 and 2 share the per-run checks
src = sub(src, T*5 + "if SRQ_Mode = 1 and SCT_Checked = 0 then\n", T*5 + "if SRQ_Mode >= 1 and SCT_Checked = 0 then\n", "type check")
src = sub(src, T*5 + "if SRQ_Mode = 1 and RollSvcExec = 1 and ConvFlag <> 'Optimal'", T*5 + "if SRQ_Mode >= 1 and RollSvcExec = 1 and ConvFlag <> 'Optimal'", "exec safety net")

# 2. sweep the FOR only where it is used (FRQ_SweepAll = 0) in mode 2
src = sub(src,
    "if BaselineOnly = 0 and ( RollSweepFrom = 0 or RollNow >= RollSweepFrom ) then",
    "if BaselineOnly = 0 and ( RollSweepFrom = 0 or RollNow >= RollSweepFrom )\n"
    + T*5 + "   and ( SRQ_Mode <> 2 or FRQ_SweepAll = 1 or RollSvcActive( Element(Time, mod(RollNow, nPeriods) + 1) ) = 1 ) then",
    "sweep condition")

# 3. store each corner's slot-2 set-points (standard sweep path)
src = sub(src,
    "\n" + T*7 + "RollVertOK(ia) := 1;\n",
    "\n" + T*7 + "RollVertOK(ia) := 1;\n"
    + T*7 + "if SRQ_Mode = 2 then   ! FOR-first requests: what each corner asks of every battery, for the recovery\n"
    + T*8 + "FRQ_VP(ia)      := FOR_Pcur;\n"
    + T*8 + "FRQ_VQ(ia)      := FOR_Qcur;\n"
    + T*8 + "FRQ_VOK(ia)     := 1;\n"
    + T*8 + "FRQ_Chg(ia,bat) := BattP_Chg(bat,PeriodMaxP);\n"
    + T*8 + "FRQ_Dis(ia,bat) := BattP_Dis(bat,PeriodMaxP);\n"
    + T*8 + "FRQ_Qv(ia,bat)  := Qinv(bat,PeriodMaxP);\n"
    + T*8 + "FRQ_Cut(ia,bat) := PVC_Cut(bat,PeriodMaxP);\n"
    + T*7 + "endif;\n",
    "corner storage")

# 4. no-service solution x0 (after the final baseline, coordinated or not) and a clean slate for the corners
anchor_b = T*5 + "! ---- SC-SAFE TEST (SCT_On = 1 only): B = the service-slot PCC point with NO service called, and\n"
src = sub(src, anchor_b,
    T*5 + "if SRQ_Mode = 2 then   ! FOR-first requests: the no-service solution x0 and a clean slate for the corners\n"
    + T*6 + "FRQ_S0P       := P_PCC(PeriodMaxP);\n"
    + T*6 + "FRQ_S0Q       := Q_PCC(PeriodMaxP);\n"
    + T*6 + "FRQ_Chg0(bat) := BattP_Chg(bat,PeriodMaxP);\n"
    + T*6 + "FRQ_Dis0(bat) := BattP_Dis(bat,PeriodMaxP);\n"
    + T*6 + "FRQ_Q0(bat)   := Qinv(bat,PeriodMaxP);\n"
    + T*6 + "FRQ_VOK(ia)   := 0;\n"
    + T*5 + "endif;\n"
    + anchor_b, "x0 storage")

# 5. the request: point inside the FOR, convex-combination recovery, commitment
req = """					! ---- FOR-FIRST REQUEST (SRQ_Mode = 2): the TSO picks a point inside the FOR just published (the
					! ---- polygon of S0 and the swept corners), and the set-points are the same convex combination of
					! ---- the stored solutions - no new optimisation. Executed at slot 1 of the next step.
					if SRQ_Mode = 2 then
						RollSvcTgt  := mod(RollNow, nPeriods) + 1;
						RollSvcPend := 0;
					endif;
					if SRQ_Mode = 2 and RollSvcActive( Element(Time, RollSvcTgt) ) = 1 and sum(ia, FRQ_VOK(ia)) >= 2 then
						! next corner that solved, cyclic, and the triangle (S0, V_i, V_next) areas
						for (ia | FRQ_VOK(ia)) do
							FRQ_Off := 1;
							while FRQ_Off < FOR_nAngles and FRQ_VOK( Element(FOR_AngleSet, mod(ord(ia) - 1 + FRQ_Off, FOR_nAngles) + 1) ) = 0 do
								FRQ_Off := FRQ_Off + 1;
							endwhile;
							FRQ_NextOrd(ia) := mod(ord(ia) - 1 + FRQ_Off, FOR_nAngles) + 1;
						endfor;
						FRQ_Area(ia) := 0;
						for (ia | FRQ_VOK(ia)) do
							FRQ_J := Element(FOR_AngleSet, FRQ_NextOrd(ia));
							FRQ_Area(ia) := 0.5*abs( (FRQ_VP(ia) - FRQ_S0P)*(FRQ_VQ(FRQ_J) - FRQ_S0Q)
							                       - (FRQ_VQ(ia) - FRQ_S0Q)*(FRQ_VP(FRQ_J) - FRQ_S0P) );
						endfor;
						FRQ_AreaTot := sum(ia, FRQ_Area(ia));
						FRQ_U1v := FRQ_U1( Element(Time, RollSvcTgt) );
						FRQ_U2v := FRQ_U2( Element(Time, RollSvcTgt) );
						FRQ_U3v := FRQ_U3( Element(Time, RollSvcTgt) );
						FRQ_Edgev := FRQ_Edge( Element(Time, RollSvcTgt) );
						if FRQ_AreaTot > 1e-9 then
							! triangle by area (u1), then a uniform point inside it (u2, u3); edge = on V_i-V_next
							FRQ_Cum := 0;
							FRQ_Found := 0;
							for (ia | FRQ_VOK(ia)) do
								FRQ_Cum := FRQ_Cum + FRQ_Area(ia);
								FRQ_Ilast := ia;
								if FRQ_Found = 0 and FRQ_Cum >= FRQ_U1v*FRQ_AreaTot - 1e-12 then
									FRQ_I := ia;
									FRQ_Found := 1;
								endif;
							endfor;
							if FRQ_Found = 0 then FRQ_I := FRQ_Ilast; endif;
							FRQ_J  := Element(FOR_AngleSet, FRQ_NextOrd(FRQ_I));
							FRQ_Sq := if FRQ_Edgev = 1 then 1 else sqrt(FRQ_U2v) endif;
							FRQ_A0 := 1 - FRQ_Sq;
							FRQ_A1 := FRQ_Sq*(1 - FRQ_U3v);
							FRQ_A2 := FRQ_Sq*FRQ_U3v;
						else
							! degenerate FOR (all corners at S0): the only point offered is S0
							FRQ_Found := 0;
							for (ia | FRQ_VOK(ia)) do
								if FRQ_Found = 0 then FRQ_I := ia; FRQ_Found := 1; endif;
							endfor;
							FRQ_J := FRQ_I;
							FRQ_A0 := 1;  FRQ_A1 := 0;  FRQ_A2 := 0;
						endif;
						FRQ_RP := FRQ_A0*FRQ_S0P + FRQ_A1*FRQ_VP(FRQ_I) + FRQ_A2*FRQ_VP(FRQ_J);
						FRQ_RQ := FRQ_A0*FRQ_S0Q + FRQ_A1*FRQ_VQ(FRQ_I) + FRQ_A2*FRQ_VQ(FRQ_J);
						! recovery: the same weights on the stored set-points
						FRQ_C(bat)  := FRQ_A0*FRQ_Chg0(bat) + FRQ_A1*FRQ_Chg(FRQ_I,bat) + FRQ_A2*FRQ_Chg(FRQ_J,bat);
						FRQ_D(bat)  := FRQ_A0*FRQ_Dis0(bat) + FRQ_A1*FRQ_Dis(FRQ_I,bat) + FRQ_A2*FRQ_Dis(FRQ_J,bat);
						FRQ_QQ(bat) := FRQ_A0*FRQ_Q0(bat)   + FRQ_A1*FRQ_Qv(FRQ_I,bat)  + FRQ_A2*FRQ_Qv(FRQ_J,bat);
						FRQ_K(bat)  :=                        FRQ_A1*FRQ_Cut(FRQ_I,bat) + FRQ_A2*FRQ_Cut(FRQ_J,bat);
						FRQ_Net := 1000*sum(bat, min(FRQ_C(bat), FRQ_D(bat)));   ! charge and discharge that cancel out
						! net power only (the transformer sees the same power), kept inside the SOC band
						SRQ_SOCc(bat)   := min( BattSOCmaxPhys(bat) - RollSOCEps, max( BattSOCmin(bat) + RollSOCEps, RollSOCnext(bat) ) );
						RollSvcChg(bat) := min( max(0, FRQ_C(bat) - FRQ_D(bat)),
						                        max( 0, (BattSOCmaxPhys(bat) - RollSOCEps - SRQ_SOCc(bat))*BattEcap(bat)/(etaChg(bat)*DeltaT) ) );
						RollSvcDis(bat) := min( max(0, FRQ_D(bat) - FRQ_C(bat)),
						                        max( 0, (SRQ_SOCc(bat) - BattSOCmin(bat) - RollSOCEps)*BattEcap(bat)*etaDis(bat)/DeltaT ) );
						FRQ_ShaveNow := 1000*DeltaT*sum(bat, (max(0, FRQ_C(bat) - FRQ_D(bat)) - RollSvcChg(bat)) + (max(0, FRQ_D(bat) - FRQ_C(bat)) - RollSvcDis(bat)));
						SRQ_Shave       := SRQ_Shave + FRQ_ShaveNow;
						RollSvcQ(bat)   := FRQ_QQ(bat);
						SRQ_CutCommit(bat) := FRQ_K(bat);
						RollSvcDelP := FRQ_RP;
						RollSvcDelQ := FRQ_RQ;
						RollSvcReqP( Element(Time,RollSvcTgt) ) := FRQ_RP;
						RollSvcReqQ( Element(Time,RollSvcTgt) ) := FRQ_RQ;
						RollSvcPend := 1;
						! diagnostic only (not executed): the smallest PV cut that delivers the same point - P1 re-planned with
						! the transformer pinned at it (battery charging first, PV cut at 3 per p.u.); measures the cost of recovery (a)
						FairActive  := 1;
						SCRefActive := 1;
						empty allvariables;
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
							Qinv(bat,'1')        := RollSvcQ_exec(bat);
							Qinv(bat,'1').nonvar := 1;
						endif;
						RollSvcReqPcur := FRQ_RP;
						RollSvcReqQcur := FRQ_RQ;
						RollSvcPinOn   := 1;
						solve MinImports
							where  MIP_Relative_Optimality_Tolerance := 0.01,
							       method     := 'deterministic concurrent',
							       time_limit := 3000;
						RollSvcPinOn := 0;
						FRQ_StatMin  := MinImports.ProgramStatus;
						FRQ_CutMin   := if FRQ_StatMin = 'Optimal' or FRQ_StatMin = 'LocallyOptimal' then 1000*sum(bat, PVC_Cut(bat,PeriodMaxP)) else -1 endif;
						FRQ_CycMin   := if FRQ_StatMin = 'Optimal' or FRQ_StatMin = 'LocallyOptimal' then 1000*sum(bat, min(BattP_Chg(bat,PeriodMaxP), BattP_Dis(bat,PeriodMaxP))) else -1 endif;
						FairActive  := 0;
						SCRefActive := 0;
						put FRQ_CSV;
						put RollNow:3:0, ",", RollSvcTgt:3:0, ",", FRQ_U1v:8:5, ",", FRQ_U2v:8:5, ",", FRQ_U3v:8:5, ",", FRQ_Edgev:2:0, ",",
						    ord(FRQ_I):3:0, ",", ord(FRQ_J):3:0, ",", FRQ_A0:8:5, ",", FRQ_A1:8:5, ",", FRQ_A2:8:5, ",",
						    (1000*FRQ_S0P):12:4, ",", (1000*FRQ_S0Q):12:4, ",", (1000*FRQ_RP):12:4, ",", (1000*FRQ_RQ):12:4, ",",
						    (1000*(FRQ_RP - FRQ_S0P)):12:4, ",", (1000*(FRQ_RQ - FRQ_S0Q)):12:4, ",", (1e6*FRQ_AreaTot):14:3, ",",
						    sum(ia, FRQ_VOK(ia)):3:0, ",", FRQ_Net:10:4, ",", FRQ_ShaveNow:10:6, ",",
						    (1000*sum(bat, RollSvcChg(bat))):10:4, ",", (1000*sum(bat, RollSvcDis(bat))):10:4, ",",
						    (1000*sum(bat, RollSvcQ(bat))):10:4, ",", (1000*sum(bat, SRQ_CutCommit(bat))):10:4, ",",
						    (1000*sum(bat, FRQ_Chg0(bat) - FRQ_Dis0(bat))):10:4, ",",
						    (100*sum(bat, RollSOCnext(bat))/max(1, sum(bat, 1))):9:4, ",", FRQ_CutMin:10:4, ",", FRQ_StatMin, ",", FRQ_CycMin:10:4 / ;
						putclose FRQ_CSV;
					endif;

"""
anchor_r = T*5 + "! ---- SC-SAFE TEST (SCT_On = 1 only): what does each offered point cost self-consumption later?\n"
src = sub(src, anchor_r, req + anchor_r, "request block")

# 6. declarations
decl = """		DeclarationSection FRQ_Declarations {
			Comment: {
				"FOR-FIRST TSO REQUESTS (2026-10-04, experiments/2026-10-04_for-requests). The TSO picks any point
				inside the published FOR; the set-points are the convex combination of the stored no-service and
				corner solutions with the point's weights (the recovery of the methodology draft). Inert unless
				SRQ_Mode = 2."
			}
			Parameter FRQ_SweepAll {
				Default: 1;
				Comment: "1 = sweep the FOR at every half-hour; 0 = only at half-hours with a TSO request (identical results: a FOR nobody uses changes nothing later).";
			}
			Parameter FRQ_U1 { IndexDomain: t; Comment: "Scenario: picks the triangle of the FOR by area (0-1), per REAL request period."; }
			Parameter FRQ_U2 { IndexDomain: t; Comment: "Scenario: distance from S0 inside the triangle (uniform over the area through sqrt)."; }
			Parameter FRQ_U3 { IndexDomain: t; Comment: "Scenario: position between the two corners."; }
			Parameter FRQ_Edge { IndexDomain: t; Comment: "Scenario: 1 = the point is on the FOR edge (V_i-V_next)."; }
			Parameter FRQ_VP { IndexDomain: ia; }
			Parameter FRQ_VQ { IndexDomain: ia; }
			Parameter FRQ_VOK { IndexDomain: ia; }
			Parameter FRQ_Chg { IndexDomain: (ia,bat); }
			Parameter FRQ_Dis { IndexDomain: (ia,bat); }
			Parameter FRQ_Qv { IndexDomain: (ia,bat); }
			Parameter FRQ_Cut { IndexDomain: (ia,bat); }
			Parameter FRQ_Chg0 { IndexDomain: bat; }
			Parameter FRQ_Dis0 { IndexDomain: bat; }
			Parameter FRQ_Q0 { IndexDomain: bat; }
			Parameter FRQ_S0P;
			Parameter FRQ_S0Q;
			Parameter FRQ_NextOrd { IndexDomain: ia; }
			Parameter FRQ_Area { IndexDomain: ia; }
			Parameter FRQ_AreaTot;
			Parameter FRQ_Off;
			Parameter FRQ_Cum;
			Parameter FRQ_Found;
			ElementParameter FRQ_I { Range: FOR_AngleSet; }
			ElementParameter FRQ_J { Range: FOR_AngleSet; }
			ElementParameter FRQ_Ilast { Range: FOR_AngleSet; }
			Parameter FRQ_U1v;
			Parameter FRQ_U2v;
			Parameter FRQ_U3v;
			Parameter FRQ_Edgev;
			Parameter FRQ_Sq;
			Parameter FRQ_A0;
			Parameter FRQ_A1;
			Parameter FRQ_A2;
			Parameter FRQ_RP;
			Parameter FRQ_RQ;
			Parameter FRQ_C { IndexDomain: bat; }
			Parameter FRQ_D { IndexDomain: bat; }
			Parameter FRQ_QQ { IndexDomain: bat; }
			Parameter FRQ_K { IndexDomain: bat; }
			Parameter FRQ_Net;
			Parameter FRQ_ShaveNow;
			Parameter FRQ_CutMin;
			Parameter FRQ_CycMin;
			StringParameter FRQ_StatMin;
			Parameter RollSvcQ_exec { IndexDomain: bat; }
			StringParameter FRQ_CSVName {
				Definition: "FRQ" + RollFileSuffix + ".csv";
			}
			File FRQ_CSV {
				Name: FRQ_CSVName;
				Mode: append;
			}
		}
		Procedure SCT_SolveCase {
"""
src = sub(src, "\t\tProcedure SCT_SolveCase {\n", decl, "declarations")

# 7. runner
runner = """		Procedure FRQ_Run {
			Body: {
				! one TR4 day with FOR-first TSO requests from scenario.txt (written by scripts/run_frq.py):
				! SRQ_Tag, SRQ_Coord, SRQ_Periods, FRQ_SweepAll, FRQ_U1/U2/U3/Edge(t), SRQ_MaxPer
				SRQ_Coord := 0;  SRQ_Tag := "";  SRQ_Periods := "";  SRQ_MaxPer := 0;  FRQ_SweepAll := 0;
				empty FRQ_U1, FRQ_U2, FRQ_U3, FRQ_Edge;
				nPeriods := 48;   ! Time must exist before the scenario's period data is read
				read from file "scenario.txt";
				if SRQ_Tag = "" then halt with "scenario.txt did not set SRQ_Tag"; endif;
				SCFirst := 1;  SCAlpha := 0;  PVC_On := 1;  PVC_Mode := 1;  PVC_ReplanPen := 3;
				PVC_SweepPen := 0.1;   ! a corner cuts PV only where that really moves it (0.01 let the reactive-only corners cut ~115 kW for ~2 kvar)
				SRQ_Mode := 2;  RollSvcMode := 4;  RollSvcPeriodsCSV := SRQ_Periods;  RollSvcTol := 1e-4;  SRQ_Sweep := 0;
				BaselineOnly := 0;  SCT_Regret := 0;  SCT_PlanDump := 0;  RollOfferLog := 0;  SCT_Trafo := "TR4";
				RollMaxPeriods := SRQ_MaxPer;
				RollFileSuffix := SRQ_Tag;
				if FileExists( FRQ_CSVName ) then FileDelete( FRQ_CSVName ); endif;
				FRQ_CSV.PageWidth := 32767;
				put FRQ_CSV;
				put "now,target,u1,u2,u3,edge,corner_i,corner_j,a0,a1,a2,S0_P_kW,S0_Q_kvar,req_P_kW,req_Q_kvar,dP_kW,dQ_kvar,",
				    "for_area_kWkvar,n_corners,netted_kW,shave_kWh,chg_kW,dis_kW,q_kvar,cut_kW,batt0_kW,soc_mean_pct,cutmin_kW,stat_min,cycmin_kW" / ;
				putclose FRQ_CSV;
				if FileExists( SRQ_P1CSVName ) then FileDelete( SRQ_P1CSVName ); endif;
				SRQ_P1CSV.PageWidth := 32767;
				put SRQ_P1CSV;
				put "now,stat1,stat2,exp2_step1,exp2_step2,chg1_kW,imp_window_kWh,imp_window_step1_kWh,soc_end_step1_pct,soc_end_pct,sun_end_slot,soc_sun_end_step1_pct" / ;
				putclose SRQ_P1CSV;
				SRQ_Shave := 0;  SRQ_ExecFail := 0;
				SCT_RunBed( SRQ_Tag, "" );
				RollFileSuffix := SRQ_Tag;
				put SCT_Info;
				put "FRQ summary: execution failures ", SRQ_ExecFail:3:0, "   energy shaved off commitments ", SRQ_Shave:12:6, " kWh   FRQ_SweepAll ", FRQ_SweepAll:2:0, "   PVC_SweepPen ", PVC_SweepPen:6:3 / ;
				putclose SCT_Info;
				SRQ_Mode := 0;  RollSvcMode := 0;  RollSvcPeriodsCSV := "";  RollSvcTol := 0.001;
				BaselineOnly := 0;  SCT_Regret := 1;  SCFirst := 0;  SCAlpha := 0;  PVC_On := 0;  PVC_Mode := 0;  PVC_ReplanPen := 10;  PVC_SweepPen := 0.01;
				PVC_Exec(bat) := 0;  SRQ_CutCommit(bat) := 0;  SCT_Trafo := "";  RollMaxPeriods := 0;  SRQ_Coord := 0;  RollFileSuffix := "";
			}
			Comment: "One TR4 rolling day, recommended setup + Option B, FOR-first TSO requests (any point inside the published FOR, recovered by convex combination of stored solutions), today's (SRQ_Coord = 0) or coordinated (1) charging.";
		}
		Procedure SCT_TR9_K000 {
"""
src = sub(src, "\t\tProcedure SCT_TR9_K000 {\n", runner, "runner")

# 8. keep a copy of the reactive set-points executed at slot 1 (used by the minimal-cut diagnostic)
src = sub(src,
    T*5 + "PVC_Exec(bat) := if RollSvcMode > 0 and RollSvcExec = 1 then SRQ_CutCommit(bat) else 0 endif;   ! SRQ: committed PV cut executed at slot 1\n",
    T*5 + "PVC_Exec(bat) := if RollSvcMode > 0 and RollSvcExec = 1 then SRQ_CutCommit(bat) else 0 endif;   ! SRQ: committed PV cut executed at slot 1\n"
    + T*5 + "RollSvcQ_exec(bat) := RollSvcQ(bat);   ! FRQ: the reactive set-points executed at slot 1 this step (RollSvcQ is overwritten by a new commitment)\n",
    "executed Q copy")

AMS.write_bytes(src.encode("utf-8"))
print("patched", AMS)
