# TR4 rolling self-consumption dispatch — analysis

**Run:** exact-QCP rolling horizon (FOR_PolyS=0, FOR_LinearizeVmax=0, CPLEX barrier),
48 steps, 46 prosumers, TR4 detailed + others lumped passive. All committed baselines
and all 576 FOR vertex solves Optimal; OVviol = 0. **Clears TR4's 71 historical
Gurobi failures** — the worst transformer of the linearized-era campaign is now
fully clean. (Full mechanism discussion: `results/TR9_analysis/TR9_analysis.md`.)

## Headline numbers

| Quantity | TR4 | (TR9 reference) |
|---|---|---|
| Prosumers | 46 | 90 |
| PV generated | 1,163 kWh/day | 2,241 |
| Demand | 343 kWh/day | 643 |
| PV / demand | **3.39x** | 3.5x |
| Exported | 802 kWh (69% of PV) | 1,551 (69%) |
| Imported | 12.4 kWh (3.6% of demand) | 13.6 (2.1%) |
| SCR / SSR | 31.0% / 96.4% | 30.8% / 97.9% |
| Periods balanced <50 W | 56.8% | 57.5% |

## The import (12.4 kWh)

44 importing prosumer-periods: **77% at the SOC floor** (mean SOC at import events
11.6%), **89% in dark hours** (the most nocturnal import profile so far), **0%
power-limited**. 9 of 46 prosumers import more than 0.1 kWh/day; the lowest
individual SSR (74.5%) of the transformers processed so far, indicating TR4 hosts
the prosumers with the least storage relative to overnight demand.

## Distribution

SSR median 100% (min 74.5%); SCR median 29.9%, spread 14.7–82.1%.

## Fidelity

- Zero simultaneous charge/discharge rows (2,208/2,208 clean).
- No linearized production reference exists for TR4; the exact 576/576 + OVviol=0
  record stands on its own — a strong contrast with the 71/576 failure rate this
  transformer had under the linearized/Gurobi configuration.
- SOC cycle: standard signature; SOC mean 0.706.
