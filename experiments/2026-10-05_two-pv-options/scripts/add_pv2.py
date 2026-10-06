"""Patch model/MainProject/OPF.ams of THIS folder for the two-PV-options test (2026-10-05, evening).

The copy comes from ../2026-10-05_no-export-pv-refill/model (sha256 fcef1ac59c732049), which already has every
regime: FOR-first requests (FRQ), Option B PV cut in the FOR (PVC), coordinated charging (SRQ_Coord), no export
without agreement (ZX) and the 0.01 W self-consumption rule (SCTight). Tulio's choice (5 Oct): put both PV
options in the paper and compare them, with coordinated charging:

  option 1 (PV2_Regime = 1)  surplus PV is exported by default; it is cut only when the TSO asks for less export
                             (FOR = batteries + surplus-PV cut, Option B)
  option 2 (PV2_Regime = 2)  no export without the TSO's agreement: surplus PV is cut by default; the batteries
                             serve the TSO and PV refills them (FOR = batteries, PV passive)

What this patch adds (all inert at the defaults FRQ_BF = 0, PV2_Regime = 0):

  1. Batteries-first delivery (FRQ_BF = 1, option 1). The recovery of the FOR-first test (convex combination of
     the no-service solution and two adjacent corners) cut 36 % more PV than needed, because mixing corners
     carries their PV cut along even where the batteries alone could deliver the point. Now:
       - in the sweep, every corner that cuts PV gets a battery-only twin: the same direction solved again with
         no PV cut (row FRQ_NoCut, generated in the period's GMP instance, switched on only for the twin);
         a corner that cuts no PV is its own twin;
       - at a request, the usual mix is kept when it cuts no PV; otherwise the same point is rebuilt from the
         stored solutions (no-service, corners, twins) with the least PV cut, then the least battery
         throughput: a search over triangles of stored points, three weights each - no new optimisation.
         Any convex combination of stored solutions is feasible (the proposition of the methodology), so the
         point is still delivered exactly.
       - log BF<tag>.csv: PV cut of the usual mix and of the batteries-first mix for the same point, the battery-
         only FOR area, the chosen points and weights.
  2. Coordinated charging under option 2: the second P1 step minimised the squared EXPORTS, which are zero when
     exports are not allowed; it now minimises the squared exports + squared surplus cuts (what leaves the
     house unused), so charging moves to the PV peak in both options. The ZX_Cut term is empty under option 1.
  3. A numeric retry of the second P1 step before it falls back to the first step (17 fallbacks in the
     FOR-first test); counters SRQ_Retry2 / SRQ_Fall2 reported in SCT_info.
  4. Runner PV2_Run: reads PV2_Regime, SRQ_Coord, FRQ_BF, ZX_GMP (-> RollUseGMP), SCTight from scenario.txt;
     sets everything else the same way for all cases.

Every replacement must match exactly once, otherwise nothing is written. Usage: python scripts/add_pv2.py
"""
import hashlib
from pathlib import Path

AMS = Path(__file__).resolve().parents[1] / "model" / "MainProject" / "OPF.ams"
raw = AMS.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n"), "expected CRLF line endings throughout"
s = raw.decode("utf-8").replace("\r\n", "\n")
assert "ZX_SCTight" in s, "expected the no-export model (add_zx*.py) as the base"
assert "PV2_Declarations" not in s, "already patched"
T = "\t"


def rep(old, new, label):
    global s
    n = s.count(old)
    assert n == 1, f"{label}: {n} matches"
    s = s.replace(old, new)


def indent_of(marker):
    i = s.index(marker)
    return s[s.rindex("\n", 0, i) + 1:i]


# 1. declarations
DECL = """\t\tDeclarationSection PV2_Declarations {
\t\t\tComment: {
\t\t\t\t"TWO PV OPTIONS (2026-10-05, experiments/2026-10-05_two-pv-options). Option 1: surplus PV exported by
\t\t\t\tdefault, cut only when the TSO asks (Option B in the FOR). Option 2: no export without agreement, surplus
\t\t\t\tcut by default, batteries serve and PV refills them. Batteries-first delivery (FRQ_BF): a request is
\t\t\t\tdelivered from the stored solutions with the least PV cut. Inert at FRQ_BF = 0, PV2_Regime = 0."
\t\t\t}
\t\t\tParameter PV2_Regime {
\t\t\t\tDefault: 0;
\t\t\t\tComment: "Read by PV2_Run: 1 = PV exported by default, surplus cut only on TSO request; 2 = no export without agreement (surplus cut by default, PV refills the batteries).";
\t\t\t}
\t\t\tParameter FRQ_BF {
\t\t\t\tDefault: 0;
\t\t\t\tComment: "1 = batteries-first delivery: battery-only twins of the corners that cut PV, and the request rebuilt from the stored solutions with the least PV cut (needs the GMP sweep).";
\t\t\t}
\t\t\tParameter FRQ_GenNow {
\t\t\t\tDefault: 0;
\t\t\t\tComment: "1 only while the period's GMP sweep instance is generated, so FRQ_NoCut exists in that instance and in no other solve.";
\t\t\t}
\t\t\tParameter FRQ_BFTol {
\t\t\t\tDefault: 0.1;
\t\t\t\tComment: "kW. A corner cutting more PV than this gets a battery-only twin; a mix cutting more than 0.001 kW is rebuilt.";
\t\t\t}
\t\t\tConstraint FRQ_NoCut {
\t\t\t\tIndexDomain: ax | ord(ax) = 1 and FRQ_GenNow and FRQ_BF and PVC_On and SRQ_Mode = 2;
\t\t\t\tDefinition: 1000*sum(bat, PVC_Cut(bat,PeriodMaxP)) <= 0;
\t\t\t\tComment: "Battery-only twin of a corner: the same direction with no PV cut. Kept inactive in the sweep instance, switched on only for the twin solve.";
\t\t\t}
\t\t\tParameter FRQ_GP { IndexDomain: ia; }
\t\t\tParameter FRQ_GQ { IndexDomain: ia; }
\t\t\tParameter FRQ_GOK { IndexDomain: ia; }
\t\t\tParameter FRQ_GChg { IndexDomain: (ia,bat); }
\t\t\tParameter FRQ_GDis { IndexDomain: (ia,bat); }
\t\t\tParameter FRQ_GQv { IndexDomain: (ia,bat); }
\t\t\tParameter FRQ_GCut { IndexDomain: (ia,bat); }
\t\t\tParameter FRQ_NTwin { Comment: "Battery-only twin solves in the run."; }
\t\t\tParameter FRQ_NTwinFail { Comment: "Twin solves that did not reach Optimal (the twin is then left out)."; }
\t\t\tSet FRQ_PtSet {
\t\t\t\tSubsetOf: Integers;
\t\t\t\tIndex: bfp, bfq, bfr;
\t\t\t\tProperty: ElementsAreNumerical;
\t\t\t\tDefinition: ElementRange(1, 2*FOR_nAngles + 1);
\t\t\t\tComment: "Stored solutions at a request: 1 = no-service, 1+i = corner i, 1+n+i = battery-only twin of corner i.";
\t\t\t}
\t\t\tParameter FRQ_BP { IndexDomain: bfp; }
\t\t\tParameter FRQ_BQ { IndexDomain: bfp; }
\t\t\tParameter FRQ_BOK { IndexDomain: bfp; }
\t\t\tParameter FRQ_BCut { IndexDomain: bfp; }
\t\t\tParameter FRQ_BThr { IndexDomain: bfp; }
\t\t\tParameter FRQ_BChg { IndexDomain: (bfp,bat); }
\t\t\tParameter FRQ_BDis { IndexDomain: (bfp,bat); }
\t\t\tParameter FRQ_BQv { IndexDomain: (bfp,bat); }
\t\t\tParameter FRQ_BCutB { IndexDomain: (bfp,bat); }
\t\t\tElementParameter FRQ_J2 { Range: FOR_AngleSet; }
\t\t\tElementParameter FRQ_B1 { Range: FRQ_PtSet; }
\t\t\tElementParameter FRQ_B2 { Range: FRQ_PtSet; }
\t\t\tElementParameter FRQ_B3 { Range: FRQ_PtSet; }
\t\t\tParameter FRQ_Det;
\t\t\tParameter FRQ_W1;
\t\t\tParameter FRQ_W2;
\t\t\tParameter FRQ_W3;
\t\t\tParameter FRQ_WS;
\t\t\tParameter FRQ_BW1;
\t\t\tParameter FRQ_BW2;
\t\t\tParameter FRQ_BW3;
\t\t\tParameter FRQ_TCut;
\t\t\tParameter FRQ_TThr;
\t\t\tParameter FRQ_BestCut;
\t\t\tParameter FRQ_BestThr;
\t\t\tParameter FRQ_BFound;
\t\t\tParameter FRQ_BFUsed;
\t\t\tParameter FRQ_CutA;
\t\t\tParameter FRQ_ThrA;
\t\t\tParameter FRQ_CutBF;
\t\t\tParameter FRQ_ThrBF;
\t\t\tParameter FRQ_GArea;
\t\t\tParameter FRQ_BChkP;
\t\t\tParameter FRQ_BChkQ;
\t\t\tParameter SRQ_Retry2 { Comment: "Coordinated second P1 steps that needed the numeric retry."; }
\t\t\tParameter SRQ_Fall2 { Comment: "Coordinated second P1 steps that still fell back to the first step."; }
\t\t\tStringParameter BF_CSVName {
\t\t\t\tDefinition: "BF" + RollFileSuffix + ".csv";
\t\t\t}
\t\t\tFile BF_CSV {
\t\t\t\tName: BF_CSVName;
\t\t\t\tMode: append;
\t\t\t}
\t\t}
"""
rep("\t\tDeclarationSection ZX_Declarations {", DECL + "\t\tDeclarationSection ZX_Declarations {", "declarations")

# 2. the sweep instance carries FRQ_NoCut, inactive
gen = 'RollGMP := GMP::Instance::Generate( FOR_VertexCont, "FORrollsweep" );\n\n'
ind = indent_of(gen)
assert s.count(ind + gen) == 1
rep(ind + gen,
    ind + "FRQ_GenNow := 1;   ! PV2: FRQ_NoCut enters this instance only\n"
    + ind + 'RollGMP := GMP::Instance::Generate( FOR_VertexCont, "FORrollsweep" );\n'
    + ind + "FRQ_GenNow := 0;\n"
    + ind + "if FRQ_BF = 1 and PVC_On = 1 and SRQ_Mode = 2 then\n"
    + ind + T + "GMP::Row::DeactivateMulti( RollGMP, ax | ord(ax) = 1, FRQ_NoCut(ax) );   ! on only for the battery-only twins\n"
    + ind + "endif;\n\n", "generation")

# 3. battery-only twin of each corner, at the end of the direction loop (sequential GMP path)
I6 = T * 6
anchor = I6 + "putclose FOR_RollProgress;\n\n" + I6 + "put FOR_RollCSV;   ! restore the active file for the next direction\n"
twin = f"""{I6}putclose FOR_RollProgress;

{I6}! ---- PV2 batteries-first (FRQ_BF = 1): the battery-only twin of this corner = the same direction with no
{I6}! ---- PV cut (FRQ_NoCut switched on in the same instance). A corner that cuts no PV is its own twin. The
{I6}! ---- twins span the battery-only part of the FOR, which the delivery uses first.
{I6}if SRQ_Mode = 2 and FRQ_BF = 1 and PVC_On = 1 and RollUseGMP = 1 then
{I6}{T}FRQ_GOK(ia) := 0;
{I6}{T}if FRQ_VOK(ia) = 1 then
{I6}{T}{T}if 1000*sum(bat, FRQ_Cut(ia,bat)) > FRQ_BFTol then
{I6}{T}{T}{T}GMP::Row::ActivateMulti( RollGMP, ax | ord(ax) = 1, FRQ_NoCut(ax) );
{I6}{T}{T}{T}GMP::Instance::Solve( RollGMP );
{I6}{T}{T}{T}Roll_SolState := GMP::Solution::GetProgramStatus( RollGMP, 1 );
{I6}{T}{T}{T}if Roll_SolState <> 'Optimal' and Roll_SolState <> 'LocallyOptimal' then
{I6}{T}{T}{T}{T}option numeric_focus       := 3;
{I6}{T}{T}{T}{T}option barrier_homogeneous := 1;
{I6}{T}{T}{T}{T}GMP::Instance::Solve( RollGMP );
{I6}{T}{T}{T}{T}Roll_SolState := GMP::Solution::GetProgramStatus( RollGMP, 1 );
{I6}{T}{T}{T}{T}option numeric_focus       := 0;
{I6}{T}{T}{T}{T}option barrier_homogeneous := 0;
{I6}{T}{T}{T}endif;
{I6}{T}{T}{T}if Roll_SolState = 'Optimal' or Roll_SolState = 'LocallyOptimal' then
{I6}{T}{T}{T}{T}GMP::Solution::SendToModel( RollGMP, 1 );
{I6}{T}{T}{T}{T}FRQ_GP(ia)       := P_PCC(PeriodMaxP);
{I6}{T}{T}{T}{T}FRQ_GQ(ia)       := Q_PCC(PeriodMaxP);
{I6}{T}{T}{T}{T}FRQ_GChg(ia,bat) := BattP_Chg(bat,PeriodMaxP);
{I6}{T}{T}{T}{T}FRQ_GDis(ia,bat) := BattP_Dis(bat,PeriodMaxP);
{I6}{T}{T}{T}{T}FRQ_GQv(ia,bat)  := Qinv(bat,PeriodMaxP);
{I6}{T}{T}{T}{T}FRQ_GCut(ia,bat) := PVC_Cut(bat,PeriodMaxP);
{I6}{T}{T}{T}{T}FRQ_GOK(ia)      := 1;
{I6}{T}{T}{T}else
{I6}{T}{T}{T}{T}FRQ_NTwinFail := FRQ_NTwinFail + 1;
{I6}{T}{T}{T}endif;
{I6}{T}{T}{T}GMP::Row::DeactivateMulti( RollGMP, ax | ord(ax) = 1, FRQ_NoCut(ax) );
{I6}{T}{T}{T}FRQ_NTwin := FRQ_NTwin + 1;
{I6}{T}{T}else
{I6}{T}{T}{T}FRQ_GP(ia)       := FRQ_VP(ia);
{I6}{T}{T}{T}FRQ_GQ(ia)       := FRQ_VQ(ia);
{I6}{T}{T}{T}FRQ_GChg(ia,bat) := FRQ_Chg(ia,bat);
{I6}{T}{T}{T}FRQ_GDis(ia,bat) := FRQ_Dis(ia,bat);
{I6}{T}{T}{T}FRQ_GQv(ia,bat)  := FRQ_Qv(ia,bat);
{I6}{T}{T}{T}FRQ_GCut(ia,bat) := FRQ_Cut(ia,bat);
{I6}{T}{T}{T}FRQ_GOK(ia)      := 1;
{I6}{T}{T}endif;
{I6}{T}endif;
{I6}endif;

{I6}put FOR_RollCSV;   ! restore the active file for the next direction
"""
rep(anchor, twin, "twin solve")

# 4. clean slate for the twins with the corners
rep(T * 6 + "FRQ_VOK(ia)   := 0;\n", T * 6 + "FRQ_VOK(ia)   := 0;\n" + T * 6 + "FRQ_GOK(ia)   := 0;   ! PV2: battery-only twins\n", "twin reset")

# 5. batteries-first delivery at the request, before netting
kline = "FRQ_K(bat)  :=                        FRQ_A1*FRQ_Cut(FRQ_I,bat) + FRQ_A2*FRQ_Cut(FRQ_J,bat);\n"
I = indent_of(kline)
bf = f"""{I}{kline}{I}! ---- PV2 batteries-first delivery (FRQ_BF = 1): the mix above is kept when it cuts no PV. Otherwise the
{I}! ---- same point is rebuilt from the stored solutions (no-service, corners, battery-only twins) with the
{I}! ---- least PV cut, then the least battery throughput. Any convex combination of stored solutions is
{I}! ---- feasible (the proposition), so this is no new optimisation: three weights per triangle of points.
{I}FRQ_CutA   := 1000*sum(bat, FRQ_K(bat));
{I}FRQ_ThrA   := 1000*sum(bat, FRQ_C(bat) + FRQ_D(bat));
{I}FRQ_CutBF  := FRQ_CutA;
{I}FRQ_ThrBF  := FRQ_ThrA;
{I}FRQ_BFUsed := 0;
{I}FRQ_BFound := 0;
{I}FRQ_GArea  := 0;
{I}FRQ_BChkP  := 0;
{I}FRQ_BChkQ  := 0;
{I}if FRQ_BF = 1 and PVC_On = 1 then
{I}{T}for (bfp) do
{I}{T}{T}if ord(bfp) = 1 then
{I}{T}{T}{T}FRQ_BOK(bfp) := 1;
{I}{T}{T}{T}FRQ_BP(bfp)  := FRQ_S0P;
{I}{T}{T}{T}FRQ_BQ(bfp)  := FRQ_S0Q;
{I}{T}{T}{T}FRQ_BChg(bfp,bat)  := FRQ_Chg0(bat);
{I}{T}{T}{T}FRQ_BDis(bfp,bat)  := FRQ_Dis0(bat);
{I}{T}{T}{T}FRQ_BQv(bfp,bat)   := FRQ_Q0(bat);
{I}{T}{T}{T}FRQ_BCutB(bfp,bat) := 0;
{I}{T}{T}elseif ord(bfp) <= 1 + FOR_nAngles then
{I}{T}{T}{T}FRQ_J2 := Element(FOR_AngleSet, ord(bfp) - 1);
{I}{T}{T}{T}FRQ_BOK(bfp) := FRQ_VOK(FRQ_J2);
{I}{T}{T}{T}FRQ_BP(bfp)  := FRQ_VP(FRQ_J2);
{I}{T}{T}{T}FRQ_BQ(bfp)  := FRQ_VQ(FRQ_J2);
{I}{T}{T}{T}FRQ_BChg(bfp,bat)  := FRQ_Chg(FRQ_J2,bat);
{I}{T}{T}{T}FRQ_BDis(bfp,bat)  := FRQ_Dis(FRQ_J2,bat);
{I}{T}{T}{T}FRQ_BQv(bfp,bat)   := FRQ_Qv(FRQ_J2,bat);
{I}{T}{T}{T}FRQ_BCutB(bfp,bat) := FRQ_Cut(FRQ_J2,bat);
{I}{T}{T}else
{I}{T}{T}{T}FRQ_J2 := Element(FOR_AngleSet, ord(bfp) - 1 - FOR_nAngles);
{I}{T}{T}{T}FRQ_BOK(bfp) := FRQ_GOK(FRQ_J2);
{I}{T}{T}{T}FRQ_BP(bfp)  := FRQ_GP(FRQ_J2);
{I}{T}{T}{T}FRQ_BQ(bfp)  := FRQ_GQ(FRQ_J2);
{I}{T}{T}{T}FRQ_BChg(bfp,bat)  := FRQ_GChg(FRQ_J2,bat);
{I}{T}{T}{T}FRQ_BDis(bfp,bat)  := FRQ_GDis(FRQ_J2,bat);
{I}{T}{T}{T}FRQ_BQv(bfp,bat)   := FRQ_GQv(FRQ_J2,bat);
{I}{T}{T}{T}FRQ_BCutB(bfp,bat) := FRQ_GCut(FRQ_J2,bat);
{I}{T}{T}endif;
{I}{T}endfor;
{I}{T}FRQ_BCut(bfp) := sum(bat, FRQ_BCutB(bfp,bat));
{I}{T}FRQ_BThr(bfp) := sum(bat, FRQ_BChg(bfp,bat) + FRQ_BDis(bfp,bat));
{I}{T}! battery-only FOR (no-service point and the twins), reported
{I}{T}for (ia | FRQ_GOK(ia) and FRQ_VOK(ia)) do
{I}{T}{T}FRQ_J2 := Element(FOR_AngleSet, FRQ_NextOrd(ia));
{I}{T}{T}if FRQ_GOK(FRQ_J2) = 1 then
{I}{T}{T}{T}FRQ_GArea := FRQ_GArea + 0.5*abs( (FRQ_GP(ia) - FRQ_S0P)*(FRQ_GQ(FRQ_J2) - FRQ_S0Q) - (FRQ_GQ(ia) - FRQ_S0Q)*(FRQ_GP(FRQ_J2) - FRQ_S0P) );
{I}{T}{T}endif;
{I}{T}endfor;
{I}{T}if FRQ_CutA > 0.001 then
{I}{T}{T}FRQ_BestCut := 1e9;
{I}{T}{T}FRQ_BestThr := 1e9;
{I}{T}{T}for (bfp, bfq, bfr | ord(bfp) < ord(bfq) and ord(bfq) < ord(bfr) and FRQ_BOK(bfp) and FRQ_BOK(bfq) and FRQ_BOK(bfr)) do
{I}{T}{T}{T}FRQ_Det := (FRQ_BP(bfq) - FRQ_BP(bfp))*(FRQ_BQ(bfr) - FRQ_BQ(bfp)) - (FRQ_BP(bfr) - FRQ_BP(bfp))*(FRQ_BQ(bfq) - FRQ_BQ(bfp));
{I}{T}{T}{T}if abs(FRQ_Det) > 1e-10 then
{I}{T}{T}{T}{T}FRQ_W2 := ( (FRQ_RP - FRQ_BP(bfp))*(FRQ_BQ(bfr) - FRQ_BQ(bfp)) - (FRQ_BP(bfr) - FRQ_BP(bfp))*(FRQ_RQ - FRQ_BQ(bfp)) ) / FRQ_Det;
{I}{T}{T}{T}{T}FRQ_W3 := ( (FRQ_BP(bfq) - FRQ_BP(bfp))*(FRQ_RQ - FRQ_BQ(bfp)) - (FRQ_RP - FRQ_BP(bfp))*(FRQ_BQ(bfq) - FRQ_BQ(bfp)) ) / FRQ_Det;
{I}{T}{T}{T}{T}FRQ_W1 := 1 - FRQ_W2 - FRQ_W3;
{I}{T}{T}{T}{T}if FRQ_W1 >= -1e-7 and FRQ_W2 >= -1e-7 and FRQ_W3 >= -1e-7 then
{I}{T}{T}{T}{T}{T}FRQ_TCut := 1000*(FRQ_W1*FRQ_BCut(bfp) + FRQ_W2*FRQ_BCut(bfq) + FRQ_W3*FRQ_BCut(bfr));
{I}{T}{T}{T}{T}{T}FRQ_TThr := 1000*(FRQ_W1*FRQ_BThr(bfp) + FRQ_W2*FRQ_BThr(bfq) + FRQ_W3*FRQ_BThr(bfr));
{I}{T}{T}{T}{T}{T}if FRQ_TCut < FRQ_BestCut - 1e-3 or ( FRQ_TCut <= FRQ_BestCut + 1e-3 and FRQ_TThr < FRQ_BestThr ) then
{I}{T}{T}{T}{T}{T}{T}FRQ_BestCut := FRQ_TCut;
{I}{T}{T}{T}{T}{T}{T}FRQ_BestThr := FRQ_TThr;
{I}{T}{T}{T}{T}{T}{T}FRQ_B1 := bfp;
{I}{T}{T}{T}{T}{T}{T}FRQ_B2 := bfq;
{I}{T}{T}{T}{T}{T}{T}FRQ_B3 := bfr;
{I}{T}{T}{T}{T}{T}{T}FRQ_BW1 := FRQ_W1;
{I}{T}{T}{T}{T}{T}{T}FRQ_BW2 := FRQ_W2;
{I}{T}{T}{T}{T}{T}{T}FRQ_BW3 := FRQ_W3;
{I}{T}{T}{T}{T}{T}{T}FRQ_BFound := 1;
{I}{T}{T}{T}{T}{T}endif;
{I}{T}{T}{T}{T}endif;
{I}{T}{T}{T}endif;
{I}{T}{T}endfor;
{I}{T}{T}if FRQ_BFound = 1 and FRQ_BestCut < FRQ_CutA - 1e-3 then
{I}{T}{T}{T}FRQ_BW1 := max(0, FRQ_BW1);
{I}{T}{T}{T}FRQ_BW2 := max(0, FRQ_BW2);
{I}{T}{T}{T}FRQ_BW3 := max(0, FRQ_BW3);
{I}{T}{T}{T}FRQ_WS  := FRQ_BW1 + FRQ_BW2 + FRQ_BW3;
{I}{T}{T}{T}FRQ_BW1 := FRQ_BW1/FRQ_WS;
{I}{T}{T}{T}FRQ_BW2 := FRQ_BW2/FRQ_WS;
{I}{T}{T}{T}FRQ_BW3 := FRQ_BW3/FRQ_WS;
{I}{T}{T}{T}FRQ_C(bat)  := FRQ_BW1*FRQ_BChg(FRQ_B1,bat)  + FRQ_BW2*FRQ_BChg(FRQ_B2,bat)  + FRQ_BW3*FRQ_BChg(FRQ_B3,bat);
{I}{T}{T}{T}FRQ_D(bat)  := FRQ_BW1*FRQ_BDis(FRQ_B1,bat)  + FRQ_BW2*FRQ_BDis(FRQ_B2,bat)  + FRQ_BW3*FRQ_BDis(FRQ_B3,bat);
{I}{T}{T}{T}FRQ_QQ(bat) := FRQ_BW1*FRQ_BQv(FRQ_B1,bat)   + FRQ_BW2*FRQ_BQv(FRQ_B2,bat)   + FRQ_BW3*FRQ_BQv(FRQ_B3,bat);
{I}{T}{T}{T}FRQ_K(bat)  := FRQ_BW1*FRQ_BCutB(FRQ_B1,bat) + FRQ_BW2*FRQ_BCutB(FRQ_B2,bat) + FRQ_BW3*FRQ_BCutB(FRQ_B3,bat);
{I}{T}{T}{T}FRQ_CutBF  := 1000*sum(bat, FRQ_K(bat));
{I}{T}{T}{T}FRQ_ThrBF  := 1000*sum(bat, FRQ_C(bat) + FRQ_D(bat));
{I}{T}{T}{T}FRQ_BChkP  := 1000*(FRQ_BW1*FRQ_BP(FRQ_B1) + FRQ_BW2*FRQ_BP(FRQ_B2) + FRQ_BW3*FRQ_BP(FRQ_B3) - FRQ_RP);
{I}{T}{T}{T}FRQ_BChkQ  := 1000*(FRQ_BW1*FRQ_BQ(FRQ_B1) + FRQ_BW2*FRQ_BQ(FRQ_B2) + FRQ_BW3*FRQ_BQ(FRQ_B3) - FRQ_RQ);
{I}{T}{T}{T}FRQ_BFUsed := 1;
{I}{T}{T}endif;
{I}{T}endif;
{I}{T}put BF_CSV;
{I}{T}put RollNow:3:0, ",", RollSvcTgt:3:0, ",", FRQ_CutA:10:4, ",", FRQ_CutBF:10:4, ",", FRQ_ThrA:10:4, ",", FRQ_ThrBF:10:4, ",",
{I}{T}    FRQ_BFUsed:2:0, ",", (if FRQ_BFUsed = 1 then ord(FRQ_B1) else 0 endif):3:0, ",", (if FRQ_BFUsed = 1 then ord(FRQ_B2) else 0 endif):3:0, ",",
{I}{T}    (if FRQ_BFUsed = 1 then ord(FRQ_B3) else 0 endif):3:0, ",", (if FRQ_BFUsed = 1 then FRQ_BW1 else 0 endif):8:5, ",",
{I}{T}    (if FRQ_BFUsed = 1 then FRQ_BW2 else 0 endif):8:5, ",", (if FRQ_BFUsed = 1 then FRQ_BW3 else 0 endif):8:5, ",",
{I}{T}    FRQ_BChkP:10:6, ",", FRQ_BChkQ:10:6, ",", sum(ia, FRQ_GOK(ia)):3:0, ",", (1e6*FRQ_GArea):14:3, ",", (1e6*FRQ_AreaTot):14:3 / ;
{I}{T}putclose BF_CSV;
{I}endif;
"""
rep(I + kline, bf, "batteries-first delivery")

# 6. coordinated step 2: squared exports + squared surplus cuts (the ZX term is empty under option 1)
rep("\t\t\t\t\t+ BattThroughputPen*sum((bat,t), BattP_Chg(bat,t) + BattP_Dis(bat,t)) <= SRQ_Obj2\n",
    "\t\t\t\t\t+ sum((bat,t), (SRQ_ExpScale*ZX_Cut(bat,t))^2) / SRQ_ExpScale\n"
    "\t\t\t\t\t+ BattThroughputPen*sum((bat,t), BattP_Chg(bat,t) + BattP_Dis(bat,t)) <= SRQ_Obj2\n", "step-2 objective")

# 7. numeric retry of step 2 before the fallback
old = (I6 + "solve SRQ_P1Coord\n"
       + I6 + T + "where  method     := 'deterministic concurrent',\n"
       + I6 + T + "       time_limit := 3000;\n"
       + I6 + "SRQ_Stage2 := 0;\n"
       + I6 + "SRQ_Stat2  := SRQ_P1Coord.ProgramStatus;\n"
       + I6 + "if SRQ_Stat2 <> 'Optimal' and SRQ_Stat2 <> 'LocallyOptimal' then\n")
new = (I6 + "solve SRQ_P1Coord\n"
       + I6 + T + "where  method     := 'deterministic concurrent',\n"
       + I6 + T + "       time_limit := 3000;\n"
       + I6 + "if SRQ_P1Coord.ProgramStatus <> 'Optimal' and SRQ_P1Coord.ProgramStatus <> 'LocallyOptimal' then   ! PV2: numeric retry before falling back\n"
       + I6 + T + "SRQ_Retry2 := SRQ_Retry2 + 1;\n"
       + I6 + T + "solve SRQ_P1Coord\n"
       + I6 + T + T + "where  method              := 'deterministic concurrent',\n"
       + I6 + T + T + "       numeric_focus       := 3,\n"
       + I6 + T + T + "       barrier_homogeneous := 1,\n"
       + I6 + T + T + "       time_limit          := 3000;\n"
       + I6 + "endif;\n"
       + I6 + "SRQ_Stage2 := 0;\n"
       + I6 + "SRQ_Stat2  := SRQ_P1Coord.ProgramStatus;\n"
       + I6 + "if SRQ_Stat2 <> 'Optimal' and SRQ_Stat2 <> 'LocallyOptimal' then\n"
       + I6 + T + "SRQ_Fall2 := SRQ_Fall2 + 1;\n")
rep(old, new, "step-2 retry")

# 8. runner PV2_Run, derived from ZX_Run
i = s.index("\t\tProcedure ZX_Run {")
j = s.index("\t\tProcedure SCT_TR9_K000 {")
zx = s[i:j]
pv = zx.replace("Procedure ZX_Run {", "Procedure PV2_Run {", 1)
for old, new in [
    ("ZX_GMP := 0;  SCTight := 0;  ZX_EndOn := 0;  ZX_AnchorOn := 0;",
     "ZX_GMP := 0;  SCTight := 0;  ZX_EndOn := 0;  ZX_AnchorOn := 0;  PV2_Regime := 0;  FRQ_BF := 0;"),
    ("SCFirst := 1;  SCAlpha := 0;  PVC_On := 0;  PVC_Mode := 0;  PVC_ReplanPen := 3;\n"
     "\t\t\t\tZX_On := 1;  FRQ_Diag := 0;  SRQ_Coord := 0;  RollUseGMP := ZX_GMP;   ! ZX: no export without agreement, batteries-only FOR, today's charging\n",
     "if PV2_Regime <> 1 and PV2_Regime <> 2 then halt with \"scenario.txt must set PV2_Regime to 1 or 2\"; endif;\n"
     "\t\t\t\tif PV2_Regime = 1 then   ! option 1: PV exported by default, surplus cut only on TSO request (FOR = batteries + surplus-PV cut)\n"
     "\t\t\t\t\tZX_On := 0;  PVC_On := 1;  PVC_Mode := 1;\n"
     "\t\t\t\telse                    ! option 2: no export without agreement, surplus cut by default (FOR = batteries, PV passive)\n"
     "\t\t\t\t\tZX_On := 1;  PVC_On := 0;  PVC_Mode := 0;  FRQ_BF := 0;\n"
     "\t\t\t\tendif;\n"
     "\t\t\t\tSCFirst := 1;  SCAlpha := 0;  PVC_ReplanPen := 3;  FRQ_Diag := 0;  RollUseGMP := ZX_GMP;\n"
     "\t\t\t\tif FRQ_BF = 1 and RollUseGMP = 0 then halt with \"batteries-first delivery needs the GMP sweep (ZX_GMP = 1)\"; endif;\n"
     "\t\t\t\tFRQ_NTwin := 0;  FRQ_NTwinFail := 0;  SRQ_Retry2 := 0;  SRQ_Fall2 := 0;\n"),
    ("\t\t\t\tSRQ_Shave := 0;  SRQ_ExecFail := 0;\n",
     "\t\t\t\tif FileExists( BF_CSVName ) then FileDelete( BF_CSVName ); endif;\n"
     "\t\t\t\tBF_CSV.PageWidth := 32767;\n"
     "\t\t\t\tput BF_CSV;\n"
     "\t\t\t\tput \"now,target,cut_mix_kW,cut_bf_kW,thr_mix_kW,thr_bf_kW,bf_used,p1,p2,p3,w1,w2,w3,chk_P_kW,chk_Q_kvar,n_twins,area_batt_kWkvar,area_for_kWkvar\" / ;\n"
     "\t\t\t\tputclose BF_CSV;\n"
     "\t\t\t\tSRQ_Shave := 0;  SRQ_ExecFail := 0;\n"),
    ('put "ZX summary (ZX_On ", ZX_On:2:0, ',
     'put "PV2 summary (PV2_Regime ", PV2_Regime:2:0, ", SRQ_Coord ", SRQ_Coord:2:0, ", FRQ_BF ", FRQ_BF:2:0, ", twins ", FRQ_NTwin:5:0, " failed ", FRQ_NTwinFail:4:0, '
     '", step-2 retries ", SRQ_Retry2:4:0, " fallbacks ", SRQ_Fall2:4:0, ", ZX_On ", ZX_On:2:0, ", PVC_On ", PVC_On:2:0, ", PVC_Mode ", PVC_Mode:2:0, ", FRQ_Diag ", FRQ_Diag:2:0, '),
    ("ZX_On := 0;  FRQ_Diag := 1;  RollUseGMP := 0;  SCTight := 0;  ZX_EndOn := 0;  ZX_AnchorOn := 0;",
     "ZX_On := 0;  FRQ_Diag := 1;  RollUseGMP := 0;  SCTight := 0;  ZX_EndOn := 0;  ZX_AnchorOn := 0;  PV2_Regime := 0;  FRQ_BF := 0;"),
    ('Comment: "NO-EXPORT / PV-REFILL (2026-10-05): one TR4 rolling day, no export without agreement (surplus PV cut in P1), batteries-only FOR, today\'s charging. Derived from FRQ_Run:',
     'Comment: "TWO PV OPTIONS (2026-10-05): one TR4 rolling day under option 1 (PV exported by default, surplus cut only on TSO request) or option 2 (no export without agreement), today\'s or coordinated charging, optional batteries-first delivery. Derived from ZX_Run / FRQ_Run:'),
]:
    assert pv.count(old) == 1, f"runner: {pv.count(old)} matches for {old[:70]!r}"
    pv = pv.replace(old, new)
rep("\t\tProcedure SCT_TR9_K000 {", pv + "\t\tProcedure SCT_TR9_K000 {", "runner")

out = s.replace("\n", "\r\n").encode("utf-8")
AMS.write_bytes(out)
print("patched", AMS, "sha256", hashlib.sha256(out).hexdigest()[:16])
