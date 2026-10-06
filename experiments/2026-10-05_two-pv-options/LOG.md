# Status log: two PV options test (2026-10-05 to 2026-10-06)

Self-contained test. **Nothing outside this folder is modified.** The AIMMS project in `model/` is a copy of
`../2026-10-05_no-export-pv-refill/model` (sha256 of `OPF.ams` fcef1ac59c732049, unchanged there) plus
`scripts/add_pv2.py` (patched `OPF.ams` sha256 starts 08fee590fbaa1c80). Every run uses the exact QCP solved by
CPLEX 22.1 (`SCT_info_<tag>.txt`).

## Why (Tulio, 5 Oct evening)

Tulio chose: FOR = batteries + surplus-PV cut when the TSO asks, with coordinated charging, to show that
coordination lowers PV curtailment. Then: "I would like to include these two options in the paper and in the
results show the different results in comparison" - the two PV options:

| | Option 1 - export by default | Option 2 - no export without agreement |
|---|---|---|
| Surplus PV (after the house and its battery) | exported | cut, unless the TSO takes it |
| PV cut happens | only when the TSO asks for less export | by default; a TSO request can save it |
| FOR | batteries + surplus-PV cut (Option B) | batteries (PV passive at the service slot) |
| How the method saves PV | battery room at noon absorbs "export less" instead of cutting PV (coordinated charging, batteries-first delivery) | batteries serve "export more", PV that would be cut refills them |
| Own reference (REF) | no request: no PV cut | no request: ~800 kWh of surplus cut |

Both with today's charging and with coordinated charging (P1 in two steps: same purchases, charging moved to the
PV peak). Priority 1 (self-consumption never compromised) is checked in every run against the REF day of the
same case; the self-consumption rule uses the 0.01 W slack in kW (`SCTight = 1`) everywhere.

## What changes in the model (`scripts/add_pv2.py`, inert at the defaults)

| Piece | What |
|---|---|
| Batteries-first delivery (`FRQ_BF = 1`, option 1) | The FOR-first recovery (mix of the no-service solution and two adjacent corners) cut 36 % more PV than needed. Now each corner that cuts PV gets a **battery-only twin** (the same direction solved again with no PV cut; row `FRQ_NoCut`, generated in the period's GMP instance, on only for the twin). At a request the usual mix is kept if it cuts no PV; otherwise the same point is rebuilt from the stored solutions (no-service, corners, twins) with the **least PV cut**, then the least battery throughput - a search over triangles of stored points, three weights each, **no new optimisation**. Any convex combination of stored solutions is feasible (the methodology's proposition), so delivery stays exact. Log `BF<tag>.csv`: PV cut of the usual mix and of the batteries-first mix for the same point, battery-only FOR area. |
| Coordinated charging under option 2 | the second P1 step minimised squared exports, which are zero without exports; it now minimises squared exports + squared surplus cuts (what leaves the house unused), so charging moves to the PV peak in both options (the cut term is empty under option 1). |
| Numeric retry of the second P1 step | before falling back to the first step (17 fallbacks in the FOR-first test); counters in `SCT_info`. |
| Runner `PV2_Run` | reads `PV2_Regime` (1/2), `SRQ_Coord`, `FRQ_BF`, `ZX_GMP`, `SCTight` from `scenario.txt`; everything else identical for all cases (`SCFirst = 1`, `SCAlpha = 0`, `PVC_SweepPen = 0.1`, FOR-first requests, `FRQ_Diag = 0`). |

## Cases and patterns

Cases (`scripts/run_pv2.py`): `exp_today`, `exp_coord` (option 1, batteries-first delivery), `noexp_today`,
`noexp_coord` (option 2). All on the GMP sweep with `SCTight = 1`.

Patterns: the same 16 TSO behaviours as `../2026-10-05_no-export-pv-refill` (same three numbers per request as
the FOR-first test, applied to each case's own FOR): REF, EDGE_SUN, R00-R11, WC_EXPORT, WC_IMPORT; SMOKE for
the checks. 16 x 4 = 64 days; lanes share one queue (`runs/queue_main.txt`), reference days and EDGE_SUN first,
then the worst cases, then the random patterns, interleaved so the paired comparisons fill in evenly.

Analysis: `python scripts/analyze_pv2.py` -> `results/pv2_runs.csv`, `pv2_requests.csv`, `pv2_halfhour.csv`,
`pv2_summary.txt`.

## Status log

- 5 Oct 21:04 smoke runs started (lanes L1-L3, shared queue `runs/queue_smoke.txt`): SMOKE exp_coord (twins,
  batteries-first, coordination), SMOKE noexp_coord (coordination without exports), REF noexp_coord (the plain
  day under the new coordinated step). All compiled; programs QCP + CPLEX 22.1; coordinated second steps
  Optimal in the first half-hours.
- 5 Oct 21:37 smoke runs done (32 min each to 14:30; REF noexp_coord 28 min for the whole day). Twins and
  batteries-first work: 30 twin solves, none failed; at 05:30 the battery-only FOR is 90 % of the full FOR (20 kW
  of surplus PV already), at 12:30 54 %; the one interior request with PV cut was rebuilt (97.8 -> 96.9 kW of
  cut, point reproduced to 1e-6 kW); edge and corner points cannot change (they lie on the FOR boundary).
  REF noexp_coord: every second step Optimal. Two problems: (1) **EXECFAIL at step 22** in SMOKE exp_coord: the
  most-export corner chosen at 10:00 (option 1, Vmax 1.092 pu, so not the voltage limit) could not be executed -
  P1 with slot 1 fixed was Infeasible, the service was released (realised -2.124 MW vs chosen -2.280 MW); never
  seen before because earlier tests never executed an extreme corner under option 1. (2) the coordinated second
  step failed 2x (option 1) and 4x (option 2) in 30 half-hours around the requests, and the numeric retry did
  not rescue it (zero-tolerance caps). Smoke lanes archived in `runs/archive_smoke_v1/`.
- 5 Oct 21:40 `scripts/add_pv2_fix.py` (model sha256 e000fbda90019cb8): before a release, a diagnostic solve
  without the network and one retry with the set-points x 0.999 (EXECRETRY line in SCT_info, realised point
  recorded); the step-2 retry gets a 1 W tolerance on its caps. Nothing changes where nothing fails.
- 5 Oct 21:42 batch launched (fresh lanes L1-L3, `runs/queue_main.txt`, 66 jobs): the two smoke patterns again
  first (to check both safety steps), then A: REF + EDGE_SUN x 4 cases; B: R00-R05 x 3 cases; C: WC_EXPORT,
  WC_IMPORT x 4; D: R06-R11 x 3; E: R00-R11 noexp_today (the earlier test has these with the 1 W rule).
- 5 Oct 22:10 both smoke patterns re-run on the fixed model: **the step-2 retry with the 1 W tolerance rescued
  every failed second step** (2 retries, 0 fallbacks in each option, vs 2 and 4 fallbacks before); **no execution
  failure** (the most-export corner at 10:00 executed; realised = chosen to 1e-6 MW for all 12 requests). The
  earlier EXECFAIL came after two fallbacks at 08:30-09:00, i.e. from a different battery state; the shrunk
  retry stays as a safety net (not needed here). REF exp_today done in 11.8 min.
- 6 Oct 00:10 stage A done (REF 10-26 min, EDGE_SUN 40-66 min; R00_sun exp_today also done). Interim
  (`python scripts/analyze_pv2.py`; one structured pattern, not statistics yet):
  - REF days: option 1 PV cut 0, exports 801.9 kWh; option 2 cut 801.6 (today) / 801.2 (coordinated) kWh;
    purchases 12.28 kWh and end SOC 50.3 % in all four - coordination and option 2 leave self-consumption
    unchanged on the plain day.
  - Checks: 108 requests, all executed, realised vs chosen <= 0.041 kW; no execution failure; second-step
    retries 4, fallbacks 0; 300 twins, none failed; worst house outside the requests +0.1 Wh vs its REF.
  - Option 1, EDGE_SUN: PV cut per kWh of "export less" 0.75 (today) -> 0.60 (coordinated, -21 %); the TSO took
    more "export less" (+271 kWh, FOR shifted to midday), so total cut +84 kWh (as in the FOR-first test).
  - Option 2, EDGE_SUN: today's charging saves 601 of 802 kWh (0.82 kWh per kWh of "export more");
    **coordinated charging saves only 176 kWh**: batteries emptier at midday -> the FOR offers more "import
    more", the TSO's grid charging (372 kWh) displaces PV. Coordination helps option 1, not option 2.
  - Batteries-first from stored solutions: small gain (R00_sun 11 kWh of 236, ~5 %; edge points cannot change),
    far below the 36 % of the earlier full re-optimisation diagnostic: most PV-cut requests lie outside the
    battery-only part of the FOR (at noon the batteries cover ~50-70 % of its area).
- 6 Oct 03:34 stage B done (R00-R05 x exp_today, exp_coord, noexp_coord; 18-67 min per day). 28 runs, 261
  requests: all executed (worst 0.041 kW), 0 execution failures, 0 second-step fallbacks (5 retries), 730 twins
  all Optimal, worst house +0.1 Wh vs its REF, 28/28 QCP + CPLEX. Paired over 7 patterns (EDGE_SUN + R00-R05):
  - Option 1: PV cut per kWh of "export less" (batteries-first) **0.66 today -> 0.49 coordinated (-26 %), lower
    in 7 of 7 (Wilcoxon p = 0.016)**; total PV cut unchanged (+33 kWh, p = 0.94) while "export less" +620 kWh
    (+40 %, 7 of 7). Batteries-first vs usual mix: 0.72 -> 0.66 (today), 0.59 -> 0.49 (coordinated), PV saved
    in 6 of 7 each (p = 0.031); 219 kWh of 1 284 with coordination (17 %).
  - Option 2 coordinated: PV saved in 7 of 7 (520 kWh, median 55 kWh/day), **0.36 kWh per kWh of "export more"**
    vs 0.98 with today's charging in ../2026-10-05_no-export-pv-refill (0.82 on EDGE_SUN here) - coordination
    is counter-productive under option 2 (to be confirmed by stage E, noexp_today on the same patterns).
  - Option 2 vs option 1 (both coordinated): +607 kWh/day of PV cut (median), -653 kWh/day of exports, FOR
    -18 000 kW x kvar (-23 %), 7 of 7.
- 6 Oct 12:09 **batch complete**: 66 of 66 runs Return value = 0 (stage D done 10:46, stage E 12:09), no AIMMS
  run active. Final results in `results/RESULTS.md` (800 requests executed, self-consumption never compromised:
  worst house +3.8 Wh; option 1 PV cut per kWh of "export less" 0.64 -> 0.49 with coordination, p = 0.0015;
  batteries-first 0.70 -> 0.64 / 0.59 -> 0.49; option 2 PV saved per kWh of "export more" 0.84 today vs 0.37
  coordinated).
- 6 Oct 12:25-12:44 package check for sharing (Ignacio, fairness): only `model/` (with the data files),
  `scripts/` and `scenarios/` copied to an empty folder, then run there. REF exp_today is identical to the batch
  (purchases 12.2849 kWh, exports 801.897 kWh, every SOC equal), 7.3 min alone. `SMOKE exp_coord_f2`
  (FairMode 2, new `_fN` case suffix of `run_pv2.py`) runs in 15.1 min: 6 points delivered exactly, util = Zeta
  (0.627) for all aggregators at every corner, but the mix still uses the no-request point (a0 = 0.29 at
  05:30), which is not fair - the change Ignacio needs to make (README section 7). Docs added: `OVERVIEW.md`
  (plain-language summary), `README.md` (how to run, fairness code locations); this log moved from README.md;
  earlier patch scripts copied to `scripts/lineage/`.
- 6 Oct 06:48 stage C done (worst cases, 53-85 min per day). **Priority 1 holds in all 8 worst-case days**: worst
  house +1 to +4 Wh vs its REF, fleet purchases outside the requests <= +0.017 kWh, purchases planned for the
  next 24 h <= +0.12 kWh; 244 requests all executed (worst 0.042 kW), no execution failure, no fallback (20
  second-step retries). WC_EXPORT: option 1 delivers 849 kWh of "export more" (today) / 385 (coordinated,
  batteries emptier in the morning); option 2 saves 725 kWh of PV (today) / 259 (coordinated). WC_IMPORT: option
  1 cuts 912 kWh for 1 087 kWh of "export less" (0.84 per kWh, the corner uses all the PV cut); option 2 cuts
  161 kWh MORE than its REF (grid charging displaces PV). End SOC -24 % on WC_EXPORT in all cases (the terminal
  band follows the drained batteries; costs <= 0.12 kWh of planned purchases).
