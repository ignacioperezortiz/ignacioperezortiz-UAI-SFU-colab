# TR9 rolling self-consumption dispatch — analysis

**Run:** exact-QCP rolling horizon (FOR_PolyS=0, FOR_LinearizeVmax=0, CPLEX barrier),
48 half-hour steps, 90 prosumers with batteries, TR9 detailed + other transformers
lumped passive. All 48 committed baselines and all 576 FOR vertex solves returned
Optimal; OVviol = 0 (the exact Vmax cap leaves no overvoltage optimism to measure).

## 1. The headline numbers

| Quantity | Value | Reading |
|---|---|---|
| PV generated | 2,241 kWh/day | ~3.5x the local demand |
| Demand | 643 kWh/day | |
| Exported | 1,551 kWh/day | 69% of PV — the structural surplus |
| Imported | 13.6 kWh/day | 2.1% of demand |
| SCR (PV used locally) | 30.8% | capped by storage size, not by dispatch |
| SSR (demand met locally) | 97.9% | near-perfect self-sufficiency |
| Prosumer-periods balanced to <50 W | 57.5% | more than half the day exactly on target |

The single ratio that explains everything: **PV is 3.5x demand.** No dispatch policy
can self-consume 2,241 kWh into 643 kWh of demand plus ~700 kWh of usable storage;
the surplus must export. The batteries' job is to place that export well — and to
make the import side vanish.

## 2. The daily cycle (SOC sheet)

Fleet-average SOC: starts 40% -> drifts to ~24% by 04:30 (overnight demand served
from storage) -> charges hard on the morning PV ramp (~07:00, avg 1.2 kW/prosumer)
-> pinned at ~100% from 11:00 to ~19:00 -> discharges through the evening back to
~50% by midnight. Individual batteries visibly ride both the 10% floor (pre-dawn)
and the 100% ceiling (midday).

## 3. Why the import is 13.6 kWh and not zero

Tracing all 74 importing prosumer-periods: **74% occur with the battery at its SOC
floor** (mean SOC at those events 12%, floor 10%), **69% in the dark hours**
(pre-dawn 01:00-06:00, late evening 20:30-23:30), **0% at the discharge power
limit**. The import is *energy-limited, not power-limited*: through the no-PV
stretch the battery discharges to hold net at zero until MinSOC_def forbids further
discharge; the remaining overnight demand can only come from the grid. Three model
ingredients set where the floor is hit: bounded usable energy (10% floor), round-trip
losses (eta^2 ~ 0.90), and the cyclic-SOC band (the plan may not run itself flat).
The model is *correctly refusing to over-discharge*; the residual is 2% of demand.

## 4. Why the export basin is deep (and welcome)

The export residual (midday, avg -2.3 kW/prosumer, fleet total ~-210 kW) coincides
exactly with SOC = 100%: storage saturates by 11:00 and surplus PV has nowhere else
to go (curtailment disabled). This is not a dispatch failure — it is the feeder's
sellable surplus, and precisely the quantity the FOR characterizes. Consistently,
the FOR area is *smallest* at midday (saturated batteries = least flexibility):
the self-consumption result and the FOR result are two views of the same physics.

## 5. Distribution across prosumers (ProsumerMetrics sheet)

- **SSR:** 100% for 76 of 90 prosumers; minimum 77%. Only 14 prosumers import more
  than 0.1 kWh/day — those with the least favorable storage-to-overnight-demand ratio.
- **SCR:** spread 14-92%, median ~30%. High-SCR prosumers are the small-PV ones
  (their generation fits their demand + battery); low-SCR prosumers have large PV
  relative to load.

## 6. Fidelity notes (honest accounting)

- **Exact vs linearized dispatch:** the committed baseline differs from the
  linearized run by ~0.003 MW per fleet-step where limits engage; every metric above
  is unchanged to the reported precision. The FOR boundary differs more (exact sits
  ~2.8% smaller in area, 6.6% at midday) — see TR9_FOR_exact_vs_linearized.png.
- **Two rows of residual simultaneous charge/discharge** (one battery, steps 26-27,
  ~3.0 kW overlap for one hour, ~0.3 kWh extra losses): a numerical residue of the
  loosened exact-QCP barrier settings (Barrier_Convergence_Tolerance 1e-2 — the
  throughput-penalty gradient on a 3 kW overlap is below the convergence slack).
  4,318 of 4,320 rows are clean; the linearized run was 4,320/4,320. If it ever
  matters, tightening the barrier tolerance for the committed baseline solve only
  would remove it at modest runtime cost.

## 7. What this feeds

- The **FOR chapters**: this dispatch is the committed starting point every FOR
  sweep departs from (reachability).
- The **DOE dispatch study**: the midday saturation window is the interesting
  period to disaggregate fairly (least flexibility, tightest fairness problem);
  the deep-export window is where the service value is.
