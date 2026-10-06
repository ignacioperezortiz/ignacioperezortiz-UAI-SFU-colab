# Two PV options, with and without coordinated charging - results (TR4, 6 Oct 2026)

66 rolling days on TR4 (46 PV-BESS prosumers, one clear-sky day, persistence forecast), exact QCP solved by
CPLEX 22.1, finished 6 Oct 12:09. Four cases x 16 TSO behaviours (REF without requests, EDGE_SUN, 12 random
patterns R00-R11, two worst cases WC_EXPORT / WC_IMPORT) + 2 smoke checks. The TSO always picks a point inside
the FOR published for that half-hour (same three numbers per request in every case, applied to each case's own
FOR); delivery by convex combination of stored solutions, no new optimisation.

| Case | PV export rule | Charging | Delivery |
|---|---|---|---|
| exp_today | option 1 = rule (ii): exported by default, cut only when the requested point needs it | today's | batteries-first |
| exp_coord | option 1 = rule (ii) | coordinated | batteries-first |
| noexp_today | option 2 = rule (iii): no export without agreement, PV refills | today's | usual mix (FOR = batteries) |
| noexp_coord | option 2 = rule (iii) | coordinated | usual mix |

Numbers: `pv2_summary.txt` (all statistics), `pv2_runs.csv`, `pv2_requests.csv`, `pv2_halfhour.csv`.
Script: `python scripts/analyze_pv2.py`. Wilcoxon signed-rank tests, paired by TSO pattern.

## 1. Checks (all 66 runs)

- 800 requests, all executed; realised vs chosen transformer point <= 0.042 kW; no execution failure.
- Every P1, coordinated second problem and FOR corner Optimal; 33 second problems needed the 1 W retry, 0 fell
  back; 1 770 battery-only twins, all Optimal; batteries-first mixes reproduce the chosen point to 2e-5 kW.
- **Self-consumption never compromised**: worst house buys +3.8 Wh more outside the requested half-hours than on
  the REF day of its case (0 houses above 10 Wh); worst cases included (WC_EXPORT: worst house +1 to +4 Wh, fleet
  <= +0.017 kWh, next-24-h planned purchases <= +0.12 kWh).
- Option 2 exports without a request: at most 0.7 kWh per day (1 W tolerance of the no-export rows).
- 66/66 runs QCP + CPLEX 22.1; no binary variable anywhere.

## 2. Reference days (no request)

All four cases: purchases 12.28 kWh, end SOC 50.3 %. Option 1: exports 801.9 kWh, PV cut 0. Option 2: PV cut
801.6 kWh (today) / 801.2 kWh (coordinated), exports 0.3 / 0.7 kWh. Coordinated charging and option 2 leave
the plain day's self-consumption unchanged.

## 3. Option 1 (rule ii): coordination lowers the PV cut per kWh of service

13 normal patterns (EDGE_SUN + R00-R11):

| | today's charging | coordinated |
|---|---|---|
| mean FOR area at the requests, kW x kvar | 74 500 | 78 800 (+6 %, 11 of 15 larger, p = 0.015) |
| "export less" delivered, kWh | 2 463 | 3 484 (+41 %) |
| "export more" delivered, kWh | 2 418 | 1 698 (-30 %) |
| PV cut, kWh | 1 364 | 1 346 (unchanged, p = 0.22) |
| **PV cut per kWh of "export less"** (pooled, all 14 patterns with such requests) | **0.64** | **0.49 (-23 %; lower in 12 of 12 patterns with a difference, p = 0.0015)** |

- Coordination keeps BESS capacity for midday: the TSO can take ~40 % more "export less" for the same PV cut. The
  price is less "export more" in the morning (BESS emptier before noon).
- **Batteries-first delivery** (least PV cut among stored solutions, incl. battery-only twins): PV cut per kWh of
  "export less" 0.70 -> 0.64 (today) and 0.59 -> 0.49 (coordinated); less PV cut in 12 of 15 patterns each
  (p = 0.002), 199 kWh and 427 kWh saved. About half of the requests whose usual mix cut PV were rebuilt (43 of
  90, 49 of 100); the rest lie on the FOR edge or outside the battery-only part (the batteries alone cover a
  median 67-69 % of the FOR area at the requests).
- Worst cases: WC_IMPORT (most import every half-hour 00:30-17:00) cuts 912 kWh for 1 087 kWh of "export less"
  in both charging cases (0.84 per kWh; the corner uses all the PV cut). WC_EXPORT: no PV cut; "export more" 849
  kWh (today) vs 385 kWh (coordinated).

## 4. Option 2 (rule iii): serving the TSO saves PV; coordination works against it

| | today's charging | coordinated |
|---|---|---|
| PV saved vs its REF (13 normal patterns), kWh | 2 785 (13 of 13 save) | 777 (11 of 13 save) |
| PV saved, all 15 patterns | 3 348 (14 of 15, p = 0.0015) | 875 (12 of 15, p = 0.04) |
| **PV saved per kWh of "export more"** (pooled) | **0.84** | **0.37** |

- Paired coordinated - today: +139 kWh/day PV cut (median; 14 of 15, p = 0.0001), +36 kWh/day purchases (the
  TSO's "import more" requests charge the emptier BESS from the grid, displacing PV). Hence the paper uses
  coordinated charging only with rule (ii).
- Worst cases: WC_EXPORT saves 725 kWh of 802 (today) / 259 (coordinated); WC_IMPORT cuts 161 kWh MORE than REF
  in both (grid charging displaces PV).

## 5. Option 2 vs option 1 (same TSO behaviour, same charging)

Today's charging, 15 patterns: option 2 has a smaller FOR (median ratio 0.73, 15 of 15), cuts +495 kWh/day more
PV (median), exports -509 kWh/day and buys -16 kWh/day less (its FOR offers less "import more"). Coordinated:
FOR ratio 0.77, PV cut +626 kWh/day, exports -653 kWh/day. Option 1 also offers PV curtailment as flexibility,
which is why its FOR is larger.

## 6. Limits

One clear-sky day, TR4 only, persistence forecast, FairMode 0 (no fairness rows), P1 solved with the network
(the paper presents it behind the meter). The FOR is computed only at request half-hours (identical outcomes,
see the FOR-first test).
