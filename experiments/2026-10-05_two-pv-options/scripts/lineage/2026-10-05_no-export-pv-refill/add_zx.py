"""Patch model/MainProject/OPF.ams of THIS folder for the no-export / PV-refill test (2026-10-05).

Tulio's rule: surplus PV after the house and its battery cannot go to the grid without the TSO's agreement, so
it is cut. Only the battery is coordinated: when the TSO asks for more power, the batteries discharge (the FOR)
and PV that would otherwise be cut charges them back later.

What the patch adds (everything is inert at ZX_On = 0):
  ZX_Cut(bat,t)    surplus PV cut at every slot, 0 .. max(0, PV - house load)            (behind the meter)
  ZX_NoExport      no prosumer exports in P1 (the committed baseline), except slot 1 when it executes a
                   committed TSO service (that exchange was agreed)
  OFminImports     the cut costs what an export cost (same weight), so P1 still fills the battery with surplus
                   first and cuts what is left - the battery schedule is today's P1, export renamed cut
  ZX_FixSvc        in the FOR sweep the cut at the service slot stays at P1's value: PV is passive, the FOR
                   is batteries only (as in the paper); battery set-points that stop absorbing PV export it
  ZX_FixExec       slot 1 executing a committed service keeps the cut planned for it (ZX_CutCommit)
  FRQ worst cases  FRQ_Edge = 2 picks the corner with the most export, 3 the corner with the most import
  FRQ_Diag         0 skips the minimal-PV-cut diagnostic of the previous test (no PV cut in this FOR)
  SCT_ExecCSV      two more columns per house and half-hour: executed cut and surplus at slot 1
  ZX_Run           runner (copy of FRQ_Run): ZX_On = 1, PVC_On = 0, today's charging, ZX_GMP -> RollUseGMP

Every replacement must match exactly once. Usage: python scripts/add_zx.py
"""
import hashlib
from pathlib import Path

AMS = Path(__file__).resolve().parents[1] / "model" / "MainProject" / "OPF.ams"

raw = AMS.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n"), "expected CRLF line endings throughout"
s = raw.decode("utf-8").replace("\r\n", "\n")
assert "ZX_Declarations" not in s, "already patched"

T = "\t"


def rep(old, new):
    global s
    n = s.count(old)
    assert n == 1, f"{n} matches for: {old[:70]!r}"
    s = s.replace(old, new)


# 1. the cut enters the battery bus power and the prosumer exchange like PVC_Cut does
rep("Definition: BattP_Balance(bat,t) + PVC_Cut(bat,t) + PVC_ExecT(bat,t)=",
    "Definition: BattP_Balance(bat,t) + PVC_Cut(bat,t) + PVC_ExecT(bat,t) + ZX_Cut(bat,t)=")
rep("PVC_Cut(bat,t) + PVC_ExecT(bat,t))",
    "PVC_Cut(bat,t) + PVC_ExecT(bat,t) + ZX_Cut(bat,t))")

# 2. P1 objective: a cut costs what an export cost
old = "+ PVC_ReplanPen*sum((bat,t), PVC_Cut(bat,t))"
i = s.index(old)
indent = s[s.rindex("\n", 0, i) + 1:i]
rep(old, old + "\n" + indent + "+ ZX_Pen*sum((bat,t), SCT_W2(t)*P1ExpScale*ExpWeight(t)*ZX_Cut(bat,t))")

# 3. declarations
DECL = """\t\tDeclarationSection ZX_Declarations {
\t\t\tComment: {
\t\t\t\t"NO-EXPORT / PV-REFILL TEST (2026-10-05, experiments/2026-10-05_no-export-pv-refill). Surplus PV after the
\t\t\t\thouse and its battery cannot be exported without the TSO's agreement, so P1 cuts it (behind the meter).
\t\t\t\tThe FOR stays batteries only: at the service slot the cut is held at P1's value, so a battery that
\t\t\t\tstops absorbing PV or discharges exports that power as the agreed service. PV that would be cut later
\t\t\t\trefills the battery - that is the curtailment the service saves. Inert at ZX_On = 0."
\t\t\t}
\t\t\tParameter ZX_On {
\t\t\t\tDefault: 0;
\t\t\t\tComment: "1 = no export without agreement, surplus PV cut in P1. 0 = model identical to the copy it came from.";
\t\t\t}
\t\t\tParameter ZX_Pen {
\t\t\t\tDefault: 1;
\t\t\t\tComment: "Weight of a cut in P1, as a multiple of the export weight it replaces (1 = same decisions as today's P1).";
\t\t\t}
\t\t\tParameter ZX_Eps {
\t\t\t\tDefault: 1e-6;
\t\t\t\tComment: "Tolerance of the no-export row, p.u. (1e-6 = 1 W), as SCEps.";
\t\t\t}
\t\t\tParameter ZX_GMP {
\t\t\t\tDefault: 0;
\t\t\t\tComment: "Read from scenario.txt by ZX_Run: 1 = sweep on the GMP path (one matrix per period, objective changed in place).";
\t\t\t}
\t\t\tParameter FRQ_Diag {
\t\t\t\tDefault: 1;
\t\t\t\tComment: "1 = FOR-first diagnostic (smallest PV cut for the same point, not executed); 0 = skipped.";
\t\t\t}
\t\t\tParameter ZX_Cap {
\t\t\t\tIndexDomain: (bat,t);
\t\t\t\tDefinition: max(0, sum(d | LoadBus(d) = BattBus(bat) and LoadPhase(d) = BattPhase(bat), GenP0(d,t) - P0(d,t)));
\t\t\t\tComment: "Surplus PV of the prosumer that owns this battery: PV minus its own load, p.u. (never the PV the house uses).";
\t\t\t}
\t\t\tVariable ZX_Cut {
\t\t\t\tIndexDomain: (bat,t) | ZX_On;
\t\t\t\tRange: [0, ZX_Cap(bat,t)];
\t\t\t\tComment: "Surplus PV cut at this prosumer, p.u.";
\t\t\t}
\t\t\tParameter ZX_CutRef {
\t\t\t\tIndexDomain: bat;
\t\t\t\tComment: "P1's cut at the service slot, captured after the baseline solve; the sweep holds the cut there.";
\t\t\t}
\t\t\tParameter ZX_CutCommit {
\t\t\t\tIndexDomain: bat;
\t\t\t\tComment: "Cut that goes with a committed service, executed at slot 1 of the next step.";
\t\t\t}
\t\t\tConstraint ZX_NoExport {
\t\t\t\tIndexDomain: (bat,t) | ZX_On and SCRefActive = 0 and not ( ord(t) = 1 and RollSvcExec = 1 );
\t\t\t\tDefinition: TotPcust(BattBus(bat),BattPhase(bat),t) >= -ZX_Eps;
\t\t\t\tComment: "No export without agreement, in P1. Not in the sweep: there a cut can always replace a later export, so the FOR is the same without these rows.";
\t\t\t}
\t\t\tConstraint ZX_FixSvc {
\t\t\t\tIndexDomain: bat | ZX_On and SCRefActive;
\t\t\t\tDefinition: ZX_Cut(bat,PeriodMaxP) = ZX_CutRef(bat);
\t\t\t\tComment: "PV is passive in the FOR: the service-slot cut stays at P1's value in every directional solve.";
\t\t\t}
\t\t\tConstraint ZX_FixExec {
\t\t\t\tIndexDomain: bat | ZX_On and RollSvcExec = 1;
\t\t\t\tDefinition: ZX_Cut(bat,'1') = ZX_CutCommit(bat);
\t\t\t\tComment: "Slot 1 executing a committed service keeps the cut the FOR was built with.";
\t\t\t}
\t\t}
"""
rep("\t\tDeclarationSection SRQ_Declarations {", DECL + "\t\tDeclarationSection SRQ_Declarations {")

# 4. capture P1's service-slot cut right after the no-service solution x0
old = "FRQ_Q0(bat)   := Qinv(bat,PeriodMaxP);"
i = s.index(old)
indent = s[s.rindex("\n", 0, i) + 1:i]
rep(old, old + "\n" + indent + "ZX_CutRef(bat) := if ZX_On = 1 then ZX_Cut(bat,PeriodMaxP) else 0 endif;   ! ZX: P1's cut at the service slot")

# 5. the committed service carries that cut
old = "SRQ_CutCommit(bat) := FRQ_K(bat);"
i = s.index(old)
indent = s[s.rindex("\n", 0, i) + 1:i]
rep(old, old + "\n" + indent + "ZX_CutCommit(bat) := ZX_CutRef(bat);   ! ZX: PV passive, the cut planned for that slot")

# 6. worst-case TSO: the corner with the most export (FRQ_Edge = 2) or the most import (3)
old = "FRQ_RP := FRQ_A0*FRQ_S0P + FRQ_A1*FRQ_VP(FRQ_I) + FRQ_A2*FRQ_VP(FRQ_J);"
i = s.index(old)
ind = s[s.rindex("\n", 0, i) + 1:i]
WC = (f"{ind}! ZX worst cases: the corner with the most export (FRQ_Edge = 2) or the most import (3), exactly\n"
      f"{ind}if FRQ_Edgev >= 2 and FRQ_AreaTot > 1e-9 then\n"
      f"{ind}{T}FRQ_Found := 0;\n"
      f"{ind}{T}for (ia | FRQ_VOK(ia)) do\n"
      f"{ind}{T}{T}if FRQ_Found = 0 then\n"
      f"{ind}{T}{T}{T}FRQ_I := ia;  FRQ_Found := 1;\n"
      f"{ind}{T}{T}elseif ( FRQ_Edgev = 2 and FRQ_VP(ia) < FRQ_VP(FRQ_I) ) or ( FRQ_Edgev = 3 and FRQ_VP(ia) > FRQ_VP(FRQ_I) ) then\n"
      f"{ind}{T}{T}{T}FRQ_I := ia;\n"
      f"{ind}{T}{T}endif;\n"
      f"{ind}{T}endfor;\n"
      f"{ind}{T}FRQ_J := FRQ_I;\n"
      f"{ind}{T}FRQ_A0 := 0;  FRQ_A1 := 1;  FRQ_A2 := 0;\n"
      f"{ind}endif;\n")
rep(ind + old, WC + ind + old)

# 7. the minimal-cut diagnostic becomes optional
old = "! diagnostic only (not executed): the smallest PV cut that delivers the same point - P1 re-planned with"
i = s.index(old)
ind = s[s.rindex("\n", 0, i) + 1:i]
rep(ind + old, ind + "if FRQ_Diag = 1 then   ! ZX: skippable\n" + ind + old)
old = (f"{ind}FairActive  := 0;\n{ind}SCRefActive := 0;\n{ind}put FRQ_CSV;\n")
rep(old, (f"{ind}FairActive  := 0;\n{ind}SCRefActive := 0;\n"
          f"{ind}else\n{ind}{T}FRQ_StatMin := \"skipped\";  FRQ_CutMin := -1;  FRQ_CycMin := -1;\n"
          f"{ind}{T}FairActive  := 0;\n{ind}{T}SCRefActive := 0;\n{ind}endif;\n{ind}put FRQ_CSV;\n"))

# 8. execution log: executed cut and surplus at slot 1
rep('put "now,battery,svc,base_status,soc_start,imp1_kWh,exp1_kWh,imp_plan_fut_kWh,batt1_kWh,cut1_kWh,pv1_kWh" / ;',
    'put "now,battery,svc,base_status,soc_start,imp1_kWh,exp1_kWh,imp_plan_fut_kWh,batt1_kWh,cut1_kWh,pv1_kWh,zx_cut1_kWh,zx_cap1_kWh" / ;')
rep("(1000*DeltaT*PVC_Exec(bat)):12:6, \",\", (1000*DeltaT*PVC_Avail(bat,'1')):12:6 / ;",
    "(1000*DeltaT*PVC_Exec(bat)):12:6, \",\", (1000*DeltaT*PVC_Avail(bat,'1')):12:6, \",\", "
    "(1000*DeltaT*ZX_Cut(bat,'1')):12:6, \",\", (1000*DeltaT*ZX_Cap(bat,'1')):12:6 / ;")

# 9. runner: FRQ_Run with ZX on, no PV cut in the FOR, today's charging, optional GMP sweep
i = s.index("\t\tProcedure FRQ_Run {")
j = s.index("\t\tProcedure SCT_TR9_K000 {")
frq = s[i:j]
zx = frq.replace("Procedure FRQ_Run {", "Procedure ZX_Run {", 1)
for old, new in [
    ("SRQ_MaxPer := 0;  FRQ_SweepAll := 0;  FRQ_PlanLog := 0;",
     "SRQ_MaxPer := 0;  FRQ_SweepAll := 0;  FRQ_PlanLog := 0;  ZX_GMP := 0;"),
    ("SCFirst := 1;  SCAlpha := 0;  PVC_On := 1;  PVC_Mode := 1;  PVC_ReplanPen := 3;",
     "SCFirst := 1;  SCAlpha := 0;  PVC_On := 0;  PVC_Mode := 0;  PVC_ReplanPen := 3;\n"
     "\t\t\t\tZX_On := 1;  FRQ_Diag := 0;  SRQ_Coord := 0;  RollUseGMP := ZX_GMP;   ! ZX: no export without agreement, batteries-only FOR, today's charging"),
    ('put "FRQ summary: execution failures "', 'put "ZX summary (ZX_On ", ZX_On:2:0, ", RollUseGMP ", RollUseGMP:2:0, "): execution failures "'),
    ("PVC_Exec(bat) := 0;  SRQ_CutCommit(bat) := 0;  SCT_Trafo := \"\";  RollMaxPeriods := 0;  SRQ_Coord := 0;  RollFileSuffix := \"\";",
     "PVC_Exec(bat) := 0;  SRQ_CutCommit(bat) := 0;  SCT_Trafo := \"\";  RollMaxPeriods := 0;  SRQ_Coord := 0;  RollFileSuffix := \"\";\n"
     "\t\t\t\tZX_On := 0;  FRQ_Diag := 1;  RollUseGMP := 0;  ZX_CutRef(bat) := 0;  ZX_CutCommit(bat) := 0;"),
    ('Comment: "One TR4 rolling day, recommended setup + Option B, FOR-first TSO requests',
     'Comment: "NO-EXPORT / PV-REFILL (2026-10-05): one TR4 rolling day, no export without agreement (surplus PV cut in P1), batteries-only FOR, today\'s charging. Derived from FRQ_Run: FOR-first TSO requests'),
]:
    assert zx.count(old) == 1, f"runner: {zx.count(old)} matches for {old[:60]!r}"
    zx = zx.replace(old, new)
rep("\t\tProcedure SCT_TR9_K000 {", zx + "\t\tProcedure SCT_TR9_K000 {")

out = s.replace("\n", "\r\n").encode("utf-8")
AMS.write_bytes(out)
print("patched", AMS, "sha256", hashlib.sha256(out).hexdigest()[:16])
