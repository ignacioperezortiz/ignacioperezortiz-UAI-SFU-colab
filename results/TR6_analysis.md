# TR6 rolling self-consumption dispatch — analysis

**Run:** exact-QCP rolling horizon (FOR_PolyS=0, FOR_LinearizeVmax=0, CPLEX barrier),
48 steps, **262 prosumers — the largest fleet in the entire feeder**. All 48 committed
baselines and all 576 vertex solves Optimal, OVviol = 0, zero cycling rows, no memory
issues. The exact-QCP + new-generator configuration now holds at the campaign's
maximum problem size (2.9x the TR9 fleet). TR6 has no linearized-era reference (no
prior tagged run), so the exact 576/576 record stands on its own.
(Full mechanism discussion: `results/TR9_analysis/TR9_analysis.md`.)

## Headline numbers

| Quantity | TR6 | (TR9 reference) |
|---|---|---|
| Prosumers | 262 | 90 |
| PV generated | 6,477 kWh/day | 2,241 |
| Demand | 1,889 kWh/day | 643 |
| PV / demand | **3.43x** | 3.5x |
| Exported | 4,456 kWh (69% of PV) | 1,551 (69%) |
| Imported | 56.6 kWh (3.0% of demand) | 13.6 (2.1%) |
| SCR / SSR | 31.2% / 97.0% | 30.8% / 97.9% |
| Periods balanced <50 W | 57.5% | 57.5% |

TR6 is essentially a scaled-up TR9: nearly identical PV/demand ratio and SCR/SSR,
with about 3x the fleet. Its per-TR FOR spans P [-2.51, +1.66], Q [-0.64, +0.89].
The larger, more dispersed fleet gives it the lowest individual SSR of the campaign
so far (66.4%), i.e. it hosts the single prosumer with the least storage relative to
its overnight demand.

## The import (56.6 kWh): energy-limited, as everywhere

273 importing prosumer-periods: **79% at the SOC floor** (mean SOC at import events
11.7%), **74% in dark hours**, **0% power-limited**. 51 of 262 prosumers import more
than 0.1 kWh/day — the campaign's largest count, but a normal 19% share of a large
fleet.

## Distribution

SSR median 100% (min 66.4%); SCR median 30.9%, spread 12.5–100%.

## Fidelity

- Zero simultaneous charge/discharge rows (12,576/12,576 clean).
- No linearized reference exists for TR6; the exact 576/576 + OVviol = 0 record is
  the primary result. Notably the largest fleet solved without any of the numerical
  fragility that motivated the linearization in the first place.
- SOC cycle: standard signature; SOC mean 0.708.
