# TR1 rolling self-consumption dispatch — analysis

**Run:** exact-QCP rolling horizon (FOR_PolyS=0, FOR_LinearizeVmax=0, CPLEX barrier),
48 half-hour steps, 77 prosumers with batteries, TR1 detailed + other transformers
lumped passive. All committed baselines and all 576 FOR vertex solves returned
Optimal; OVviol = 0. (Historical note: under the linearized/Gurobi setup TR1 had 13
failed directions; the exact CPLEX configuration clears every one.)

## 1. The headline numbers

| Quantity | Value | vs TR9 |
|---|---|---|
| Prosumers | 77 | 90 |
| PV generated | 1,797 kWh/day | 2,241 |
| Demand | 573 kWh/day | 643 |
| PV / demand ratio | **3.1x** | 3.5x |
| Exported | 1,201 kWh/day (67% of PV) | 1,551 (69%) |
| Imported | 22.6 kWh/day (3.9% of demand) | 13.6 (2.1%) |
| SCR (PV used locally) | 33.1% | 30.8% |
| SSR (demand met locally) | 96.0% | 97.9% |
| Prosumer-periods balanced to <50 W | 58.2% | 57.5% |

Same story as TR9, slightly softer: PV is ~3.1x demand, so roughly two-thirds of the
PV must export regardless of dispatch. TR1's marginally lower PV surplus gives it a
slightly higher SCR (33% vs 31%); its higher import (3.9% vs 2.1% of demand) means
its batteries are a bit smaller relative to overnight demand than TR9's.

## 2. The daily cycle

Fleet-average SOC: 40% start -> ~24% pre-dawn trough -> hard charge on the morning
PV ramp -> pinned at ~100% through midday -> evening discharge. SOC mean over the
day 0.70; individual batteries ride both the 10% floor (pre-dawn) and the 100%
ceiling (midday). Fleet net: exactly balanced overnight (|net| avg 0.003 kW),
midday export basin up to -163 kW fleet-wide.

## 3. Why the import is 22.6 kWh and not zero

Of the 91 importing prosumer-periods: **79% occur with the battery at its SOC floor**
(mean SOC at import events 12.0%, floor 10%), **79% in the dark hours**, **0% at the
discharge power limit**. Energy-limited, not power-limited — identical mechanism to
TR9: overnight the battery holds net at zero until MinSOC_def forbids further
discharge, and the remaining dark-hours demand must be bought. TR1 imports
proportionally more than TR9 (3.9% vs 2.1% of demand) because its
storage-to-overnight-demand ratio is less favorable; 18 of 77 prosumers import more
than 0.1 kWh/day (TR9: 14 of 90).

## 4. Distribution across prosumers

- **SSR:** median 100%, minimum 72.1%.
- **SCR:** spread 15.8-96.1%, median 35.1% — high-SCR prosumers are the small-PV
  ones whose generation fits demand + battery.

## 5. Fidelity notes

- **Exact vs linearized boundary:** 576/576 common Optimal vertices; mean |dP|
  0.0048, max 0.0498 p.u.; OVviol 0.0087 -> 0.0000. Exact region sits slightly
  inside the linearized surrogate, as at TR9.
- **Zero simultaneous charge/discharge rows** (4,320/4,320 clean at 1 W tolerance).
  The 2-row barrier-tolerance residue seen at TR9 does not recur here.

## 6. What this feeds

Same pipeline as TR9: this dispatch is the committed state the TR1 FOR sweeps
depart from, and TR1's per-TR FOR enters the whole-feeder Minkowski combination
(anchor: FOR_rolling_baseline.csv).
