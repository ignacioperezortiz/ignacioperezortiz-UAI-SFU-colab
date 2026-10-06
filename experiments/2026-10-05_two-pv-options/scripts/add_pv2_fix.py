"""Second patch (after add_pv2.py) for model/MainProject/OPF.ams of THIS folder (2026-10-05, 21:55).

Findings of the smoke runs (21:04-21:37):
  1. SMOKE exp_coord, step 22: the most-export corner chosen at step 21 (option 1, 10:30, Vmax 1.092 pu) could not
     be executed - the P1 baseline with slot 1 fixed at the committed set-points was Infeasible (also after the
     numeric rescue), so the service was released (EXECFAIL). Earlier tests never executed an extreme corner
     under option 1, so the cause is not known yet.
  2. The coordinated second P1 step failed 2 times (option 1) and 4 times (option 2) in 30 half-hours
     (Infeasible / IntermediateNonOptimal, both around the requests), and the numeric retry did not rescue it.
     Its caps are written with zero tolerance (SRQ_CapTolKW = 0): the step-1 plan meets them exactly, so the
     region is razor-thin.

What this patch adds (no change at all where nothing fails):
  1. Before releasing a committed service: a diagnostic solve of the same P1 WITHOUT the network (is the network
     the cause?), then one retry of the baseline with the battery set-points (charge, discharge, reactive)
     shrunk by 0.1 % (SRQ_ExecShrink = 0.999, so every limit is met by more than the solver tolerance); the
     realised point is recorded as usual, so the analysis shows the difference. Only if that fails too is the
     service released as before. Line "EXECRETRY" in SCT_info; counter SRQ_ExecRescued.
  2. The numeric retry of the second P1 step uses a tolerance on its caps, SRQ_CapTolRetry = 1e-3 (kW for the
     import and throughput caps = 1 W per house and half-hour; 1e-6 of capacity for the two SOC caps), restored
     to 0 afterwards. The first attempt is unchanged.
Usage: python scripts/add_pv2_fix.py
"""
import hashlib
from pathlib import Path

AMS = Path(__file__).resolve().parents[1] / "model" / "MainProject" / "OPF.ams"
raw = AMS.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n")
s = raw.decode("utf-8").replace("\r\n", "\n")
assert "PV2_Declarations" in s, "run add_pv2.py first"
assert "SRQ_ExecShrink" not in s, "already patched"
T = "\t"


def rep(old, new, label):
    global s
    n = s.count(old)
    assert n == 1, f"{label}: {n} matches"
    s = s.replace(old, new)


# declarations (in the PV2 section)
rep("\t\t\tParameter SRQ_Retry2 {",
    "\t\t\tParameter SRQ_ExecShrink {\n"
    "\t\t\t\tDefault: 0.999;\n"
    "\t\t\t\tComment: \"Factor on the committed battery set-points in the one retry before a service is released.\";\n"
    "\t\t\t}\n"
    "\t\t\tParameter SRQ_ExecRescued { Comment: \"Committed services executed thanks to the shrunk retry.\"; }\n"
    "\t\t\tStringParameter SRQ_ExecStat0;\n"
    "\t\t\tStringParameter SRQ_ExecNoNet;\n"
    "\t\t\tParameter SRQ_CapTolRetry {\n"
    "\t\t\t\tDefault: 1e-3;\n"
    "\t\t\t\tComment: \"Tolerance of the coordinated caps in the retry of the second P1 step (kW for imports and throughput).\";\n"
    "\t\t\t}\n"
    "\t\t\tParameter SRQ_CapTol0;\n"
    "\t\t\tParameter SRQ_Retry2 {", "declarations")

# 1. diagnostic + shrunk retry before the release
I5 = T * 5
old = I5 + "if SRQ_Mode >= 1 and RollSvcExec = 1 and ConvFlag <> 'Optimal' and ConvFlag <> 'LocallyOptimal' then\n"
new = (I5 + "! ---- PV2: before a committed service is released, (1) is the plan feasible WITHOUT the network? (diagnostic)\n"
       + I5 + "! ---- (2) one retry with the battery set-points shrunk by SRQ_ExecShrink (inside every limit by more than tolerance)\n"
       + I5 + "if SRQ_Mode >= 1 and RollSvcExec = 1 and ConvFlag <> 'Optimal' and ConvFlag <> 'LocallyOptimal' and PV2_Regime > 0 then\n"
       + I5 + T + "SRQ_ExecStat0 := ConvFlag;\n"
       + I5 + T + "IncludeNetworkConstraints := 0;\n"
       + I5 + T + "run MinOFminImports;\n"
       + I5 + T + "SRQ_ExecNoNet := ConvFlag;\n"
       + I5 + T + "IncludeNetworkConstraints := 1;\n"
       + I5 + T + "BattP_Chg(bat,'1')        := SRQ_ExecShrink*RollSvcChg(bat);\n"
       + I5 + T + "BattP_Chg(bat,'1').nonvar := 1;\n"
       + I5 + T + "BattP_Dis(bat,'1')        := SRQ_ExecShrink*RollSvcDis(bat);\n"
       + I5 + T + "BattP_Dis(bat,'1').nonvar := 1;\n"
       + I5 + T + "Qinv(bat,'1')             := SRQ_ExecShrink*RollSvcQ(bat);\n"
       + I5 + T + "if RollQAllSlots = 0 then Qinv(bat,'1').nonvar := 1; endif;\n"
       + I5 + T + "run MinOFminImports;\n"
       + I5 + T + "if ConvFlag <> 'Optimal' and ConvFlag <> 'LocallyOptimal' then\n"
       + I5 + T + T + "solve MinImports\n"
       + I5 + T + T + T + "where  MIP_Relative_Optimality_Tolerance := 0.01,\n"
       + I5 + T + T + T + "       method              := 'deterministic concurrent',\n"
       + I5 + T + T + T + "       numeric_focus       := 3,\n"
       + I5 + T + T + T + "       barrier_homogeneous := 1,\n"
       + I5 + T + T + T + "       time_limit          := 3000;\n"
       + I5 + T + T + "ConvFlag := MinImports.ProgramStatus;\n"
       + I5 + T + "endif;\n"
       + I5 + T + "if ConvFlag = 'Optimal' or ConvFlag = 'LocallyOptimal' then SRQ_ExecRescued := SRQ_ExecRescued + 1; endif;\n"
       + I5 + T + "put SCT_Info;\n"
       + I5 + T + "put \"EXECRETRY at step \", RollNow:3:0, \": baseline \", SRQ_ExecStat0, \", same plan without the network \", SRQ_ExecNoNet, \", set-points x\", SRQ_ExecShrink:6:4, \" -> \", ConvFlag / ;\n"
       + I5 + T + "putclose SCT_Info;\n"
       + I5 + "endif;\n"
       + old)
rep(old, new, "exec retry")

# 2. the step-2 retry with a tolerance on the caps
I6 = T * 6
old = (I6 + T + "SRQ_Retry2 := SRQ_Retry2 + 1;\n"
       + I6 + T + "solve SRQ_P1Coord\n"
       + I6 + T + T + "where  method              := 'deterministic concurrent',\n"
       + I6 + T + T + "       numeric_focus       := 3,\n"
       + I6 + T + T + "       barrier_homogeneous := 1,\n"
       + I6 + T + T + "       time_limit          := 3000;\n")
new = (I6 + T + "SRQ_Retry2 := SRQ_Retry2 + 1;\n"
       + I6 + T + "SRQ_CapTol0  := SRQ_CapTolKW;\n"
       + I6 + T + "SRQ_CapTolKW := SRQ_CapTolRetry;   ! PV2: a hair of room on the caps (the first attempt has none)\n"
       + I6 + T + "solve SRQ_P1Coord\n"
       + I6 + T + T + "where  method              := 'deterministic concurrent',\n"
       + I6 + T + T + "       numeric_focus       := 3,\n"
       + I6 + T + T + "       barrier_homogeneous := 1,\n"
       + I6 + T + T + "       time_limit          := 3000;\n"
       + I6 + T + "SRQ_CapTolKW := SRQ_CapTol0;\n")
rep(old, new, "step-2 retry tolerance")
rep("Definition: 1000*sum(t | ord(t) = SRQ_SunEnd, BattSOC(bat,t)) >= 1000*SRQ_SOCSun1(bat);",
    "Definition: 1000*sum(t | ord(t) = SRQ_SunEnd, BattSOC(bat,t)) >= 1000*SRQ_SOCSun1(bat) - SRQ_CapTolKW;", "sun cap")
rep("Definition: 1000*sum(t | ord(t) = nPeriods, BattSOC(bat,t)) >= 1000*SRQ_SOCEnd1(bat);",
    "Definition: 1000*sum(t | ord(t) = nPeriods, BattSOC(bat,t)) >= 1000*SRQ_SOCEnd1(bat) - SRQ_CapTolKW;", "end cap")

# runner: reset and report the new counter
rep("FRQ_NTwin := 0;  FRQ_NTwinFail := 0;  SRQ_Retry2 := 0;  SRQ_Fall2 := 0;",
    "FRQ_NTwin := 0;  FRQ_NTwinFail := 0;  SRQ_Retry2 := 0;  SRQ_Fall2 := 0;  SRQ_ExecRescued := 0;", "runner reset")
rep('" fallbacks ", SRQ_Fall2:4:0, ',
    '" fallbacks ", SRQ_Fall2:4:0, ", exec rescued ", SRQ_ExecRescued:3:0, ', "runner summary")

out = s.replace("\n", "\r\n").encode("utf-8")
AMS.write_bytes(out)
print("patched", AMS, "sha256", hashlib.sha256(out).hexdigest()[:16])
