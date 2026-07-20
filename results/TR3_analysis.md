# TR3 rolling self-consumption dispatch — analysis

**Run:** exact-QCP rolling horizon (FOR_PolyS=0, FOR_LinearizeVmax=0, CPLEX barrier),
48 steps, 49 prosumers, TR3 detailed + others lumped passive. All committed baselines
and all 576 FOR vertex solves Optimal; OVviol = 0. Clears TR3's 18 historical Gurobi
failures. (Full mechanism discussion: `results/TR9_analysis/TR9_analysis.md`.)

## Headline numbers

| Quantity | TR3 | (TR9 reference) |
|---|---|---|
| Prosumers | 49 | 90 |
| PV generated | 1,316 kWh/day | 2,241 |
| Demand | 352 kWh/day | 643 |
| PV / demand | **3.74x** — the most PV-heavy so far | 3.5x |
| Exported | 942 kWh (72% of PV) | 1,551 (69%) |
| Imported | 7.2 kWh (2.0% of demand) | 13.6 (2.1%) |
| SCR / SSR | 28.4% / 98.0% | 30.8% / 97.9% |
| Periods balanced <50 W | 55.6% | 57.5% |

The highest PV-to-demand ratio of the transformers processed so far — accordingly
the lowest SCR (28.4%: the more surplus, the smaller the locally usable share) and
the deepest per-prosumer midday export (fleet-average net -2.36 kW, vs -2.16 at TR9).

## The import (7.2 kWh)

36 importing prosumer-periods: **75% at the SOC floor** (mean SOC 11.3%), **69% in
dark hours**, **0% power-limited**. 7 of 49 prosumers import more than 0.1 kWh/day.

## Distribution

SSR median 100% (min 84.6%); SCR median 27.3%, spread 12.6–63.2%.

## Fidelity

- Zero simultaneous charge/discharge rows (2,352/2,352 clean).
- No linearized production reference exists for TR3 (its historical run predates the
  tagged-lin convention); the exact run stands on its own 576/576 + OVviol=0 record.
- SOC cycle: standard signature; SOC mean 0.721.
