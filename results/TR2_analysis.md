# TR2 rolling self-consumption dispatch — analysis

**Run:** exact-QCP rolling horizon (FOR_PolyS=0, FOR_LinearizeVmax=0, CPLEX barrier),
48 steps, 95 prosumers, TR2 detailed + others lumped passive. All committed baselines
and all 576 FOR vertex solves Optimal; OVviol = 0. Clears TR2's 2 historical Gurobi
failures. (Full mechanism discussion: see `results/TR9_analysis/TR9_analysis.md` —
the physics is identical; this file records TR2's numbers.)

## Headline numbers

| Quantity | TR2 | (TR9 reference) |
|---|---|---|
| Prosumers | 95 | 90 |
| PV generated | 2,370 kWh/day | 2,241 |
| Demand | 666 kWh/day | 643 |
| PV / demand | **3.56x** | 3.5x |
| Exported | 1,638 kWh (69% of PV) | 1,551 (69%) |
| Imported | 16.1 kWh (2.4% of demand) | 13.6 (2.1%) |
| SCR / SSR | 30.9% / 97.6% | 30.8% / 97.9% |
| Periods balanced <50 W | 56.9% | 57.5% |

TR2 is the largest of the small transformers and nearly a twin of TR9 in every
ratio — PV 3.56x demand, ~69% of PV structurally exported, near-perfect
self-sufficiency.

## The import (16.1 kWh): energy-limited, as everywhere

94 importing prosumer-periods: **79% at the SOC floor** (mean SOC at import events
11.1%), **74% in dark hours**, **0% power-limited**. Same mechanism as TR9/TR1:
overnight storage runs down to MinSOC_def and the residual demand must be bought.
15 of 95 prosumers import more than 0.1 kWh/day.

## Distribution

SSR median 100% (min 83.2%); SCR median 28.3%, spread 11.4–81.4%.

## Fidelity

- Exact vs linearized boundary (vs `FOR_rolling_TR2_lin.csv`): 576 common Optimal
  vertices, |dP| mean 0.0081 / max 0.0502 p.u., OVviol 0.0122 -> 0.0000.
- Zero simultaneous charge/discharge rows (4,560/4,560 clean).
- SOC cycle: 40% -> pre-dawn trough -> pinned 100% midday -> evening discharge;
  SOC mean 0.714.
