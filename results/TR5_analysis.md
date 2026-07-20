# TR5 rolling self-consumption dispatch — analysis

**Run:** exact-QCP rolling horizon (FOR_PolyS=0, FOR_LinearizeVmax=0, CPLEX barrier),
48 steps, **214 prosumers — the largest fleet processed so far and the historical
stress test** (under the linearized/Gurobi setup TR5 took ~10 h and left 11 failed
directions; an earlier attempt on this machine was interrupted at 45/48 steps). The
exact run: **all 48 committed baselines and all 576 vertex solves Optimal, OVviol = 0,
zero cycling rows, no memory issues** — the new-generator fix holds at 2.4x the TR9
problem size. (Full mechanism discussion: `results/TR9_analysis/TR9_analysis.md`.)

## Headline numbers

| Quantity | TR5 | (TR9 reference) |
|---|---|---|
| Prosumers | 214 | 90 |
| PV generated | 5,100 kWh/day | 2,241 |
| Demand | 1,615 kWh/day | 643 |
| PV / demand | **3.16x** | 3.5x |
| Exported | 3,391 kWh (66% of PV) | 1,551 (69%) |
| Imported | 40.3 kWh (2.5% of demand) | 13.6 (2.1%) |
| SCR / SSR | 33.5% / 97.5% | 30.8% / 97.9% |
| Periods balanced <50 W | 58.9% | 57.5% |

TR5 has the mildest PV-to-demand ratio yet (3.16x) and correspondingly the highest
SCR (33.5%); one prosumer even reaches SCR = 100% (its PV fits entirely in its
demand + battery). The FOR is the largest of the per-TR regions: P extent
[-2.84, +1.73], Q extent [-0.71, +1.01] — 214 inverters' worth of reactive width.

## The import (40.3 kWh): energy-limited, as everywhere

195 importing prosumer-periods: **78% at the SOC floor** (mean SOC at import events
11.9%), **79% in dark hours**, **0% power-limited**. 39 of 214 prosumers import
more than 0.1 kWh/day; minimum individual SSR 73.6%.

## Distribution

SSR median 100% (min 73.6%); SCR median 32.9%, spread 12.8–100%.

## Fidelity

- Exact vs the interrupted linearized reference (45 steps / 530 common vertices):
  |dP| mean 0.0197, max 0.145 p.u. — the largest exact-vs-linearized gap of the
  campaign, consistent with TR5's larger fleet pushing harder against the voltage
  cap (more accumulated linearization optimism to remove); OVviol 0.0105 -> 0.
- Zero simultaneous charge/discharge rows (10,272/10,272 clean).
- SOC cycle: standard signature; SOC mean 0.700.
