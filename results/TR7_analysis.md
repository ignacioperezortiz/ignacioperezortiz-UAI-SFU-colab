# TR7 rolling self-consumption dispatch — analysis

**Run:** exact-QCP rolling horizon (FOR_PolyS=0, FOR_LinearizeVmax=0, CPLEX barrier),
48 steps, **259 prosumers** (the largest single fleet analyzed), TR7 detailed +
others lumped passive. All 48 committed baselines and all 576 FOR vertex solves
Optimal; OVviol = 1.9e-10 (numerical zero), UVviol = 0; zero simultaneous
charge/discharge rows. This is the **re-run of 2026-07-12** (the original PerTrafo
TR7 was regenerated after an out-of-memory AIMMS crash; identical clean record).
(Full mechanism discussion: `results/TR9_analysis/TR9_analysis.md`.)

## Headline numbers

| Quantity | TR7 | (TR8 reference) |
|---|---|---|
| Prosumers | 259 | 124 |
| PV generated | 6,526 kWh/day | 3,081 |
| Demand | 1,916 kWh/day | 851 |
| PV / demand | 3.41x | 3.62x |
| Exported | 4,517 kWh (69% of PV) | 2,167 (70%) |
| Imported | 52.9 kWh (2.8% of demand) | 25.8 (3.0%) |
| SCR / SSR | 30.8% / 97.2% | 29.7% / 97.0% |
| Periods balanced <50 W | 57.6% | 57.0% |

TR7 is the largest detailed fleet and reproduces the feeder-wide signature closely.
Being the biggest, its per-TR FOR is the widest of the single transformers: it
reaches **P = 0 in 18 of 48 slots** (mean P-width 0.93 p.u., widest 1.47), and its
Q band contains zero in **all 48** slots.

## The import (52.9 kWh): energy-limited, not power-limited

185 importing prosumer-periods (>50 W): **78% at the SOC floor** (mean SOC at import
events 11.8%), **86% in dark hours**, **0% power-limited**. Import happens only when
a battery is already empty in the dark — never because inverter power ran out. 44 of
259 prosumers import more than 0.1 kWh/day.

## FOR at the PCC (next-slot flexibility)

- 576/576 Optimal; AC-valid (max bus |V| = 1.100 at the 1.10 cap, OVviol = 1.9e-10).
- P at PCC in [-2.556 (h=12, midday export peak), +1.694 (h=20.5, evening import)] p.u.
- Q at PCC in [-0.691 (h=4.5), +0.931 (h=20.5)] p.u.
- FOR area 0.241 (h=12) to 1.559 (h=6) p.u.^2 — flexibility is largest overnight
  when storage headroom is greatest.

## Distribution

SSR median 100% (min 63.8%); the fleet self-supplies almost entirely, with a small
tail of demand-heavy / PV-light prosumers. SOC fleet mean 0.707, swing 0.25–1.00.

## Fidelity

- Zero simultaneous charge/discharge rows (12,432/12,432 clean).
- Full battery names written natively (the `bat:24` put-width fix); no post-hoc
  name repair needed on this run.
- SOC cycle: standard signature; nightly draw-down to the floor, midday recharge.
