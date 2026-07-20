# TR8 rolling self-consumption dispatch — analysis

**Run:** exact-QCP rolling horizon (FOR_PolyS=0, FOR_LinearizeVmax=0, CPLEX barrier),
48 steps, 124 prosumers, TR8 detailed + others lumped passive. All 48 committed
baselines and all 576 FOR vertex solves Optimal; OVviol = 0; zero simultaneous
charge/discharge rows. No linearized-era reference (no prior tagged run for TR8).
(Full mechanism discussion: `results/TR9_analysis/TR9_analysis.md`.)

## Headline numbers

| Quantity | TR8 | (TR9 reference) |
|---|---|---|
| Prosumers | 124 | 90 |
| PV generated | 3,081 kWh/day | 2,241 |
| Demand | 851 kWh/day | 643 |
| PV / demand | 3.62x | 3.5x |
| Exported | 2,167 kWh (70% of PV) | 1,551 (69%) |
| Imported | 25.8 kWh (3.0% of demand) | 13.6 (2.1%) |
| SCR / SSR | 29.7% / 97.0% | 30.8% / 97.9% |
| Periods balanced <50 W | 57.0% | 57.5% |

TR8 is a mid-size fleet that reproduces the feeder-wide signature closely. Its per-TR
FOR reaches P = 0 in only 5 of 48 slots (a modest 0.45 p.u. fleet), and its Q band
contains zero in all 48.

## The import (25.8 kWh): energy-limited

130 importing prosumer-periods: **77% at the SOC floor** (mean SOC at import events
11.8%), **78% in dark hours**, **0% power-limited**. 25 of 124 prosumers import more
than 0.1 kWh/day; minimum individual SSR 75.4%.

## Distribution

SSR median 100% (min 75.4%); SCR median 27.3%, spread 13.8–100%.

## Fidelity

- Zero simultaneous charge/discharge rows (5,952/5,952 clean).
- No linearized reference exists for TR8; the exact 576/576 + OVviol = 0 record
  stands on its own.
- SOC cycle: standard signature; SOC mean 0.712.
