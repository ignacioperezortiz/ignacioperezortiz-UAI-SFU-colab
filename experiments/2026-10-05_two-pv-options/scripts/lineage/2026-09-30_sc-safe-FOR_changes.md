## What was changed in the copied model (`model/MainProject/OPF.ams`)

All additive and inert at the defaults, so a default run is production:

1. `OF_FOR_cont` gains `+ FOR_SCWeight * ( sum over bat, t > PeriodMaxP of w2(t) * (Import +
   FOR_SCExpWeight * ExpWeight(t) * Export) + BattThroughputPen * sum(Chg + Dis) )`. Default kappa = 0.
2. `RunFOR_Rolling`: when `SCT_On = 1`, capture the no-service point B after the committed baseline,
   and after the sweep call `SCT_SolveCase` for the reference, B, and each vertex x shrink value.
3. New section `SCSafeTest` (end of file): pins `SCT_PinProw/SCT_PinQrow` (zero rows unless active),
   `SCT_SolveCase`, `SCT_TypeCheck` (writes the program type and solver to `SCT_info_<tag>.txt`),
   `SCT_UseCPLEX` (pins CPLEX 22.1 for QCP/QP/LP), runners `SCT_Micro_*`, `SCT_TR9_*`.

Solver check (written by every run): `MinImports` and `FOR_VertexCont` are generated as **QCP** and solved
by **CPLEX 22.1**, with `FOR_PolyS = 0`, `FOR_LinearizeVmax = 0` (exact S-circle and exact Vmax).

