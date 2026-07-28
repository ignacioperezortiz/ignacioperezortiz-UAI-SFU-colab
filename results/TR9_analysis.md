# TR9 rolling self-consumption dispatch — analysis

**Run:** exact-QCP rolling horizon (FOR_PolyS=0, FOR_LinearizeVmax=0, CPLEX barrier),
48 half-hour steps, 90 prosumers with batteries, TR9 detailed + other transformers
lumped passive. All 48 committed baselines and all 576 FOR vertex solves returned
Optimal; OVviol = 0 (the exact Vmax cap leaves no overvoltage optimism to measure).

**Scope.** Everything in sections 1–5 is measured at the **90 prosumer meters**. TR9
has 172 customers; the other 82 have no PV and no battery, and they do not appear in
the dispatch workbook. Their demand is real and it sits inside TR9, so prosumer export
reaches them before it reaches the transformer. Where a feeder-level figure exists it
is given beside the prosumer one. Separately, the FOR quantities referred to in
sections 4 and 7 are measured at the **feeder's slack/HV bus**, not at TR9 — see
`results/FOR_interpretation/FOR_reading.md`.

## 1. The headline numbers

At the 90 prosumer meters:

| Quantity | Value | Reading |
|---|---|---|
| PV generated | 2,241 kWh/day | 3.5x the prosumers' own demand |
| Prosumer demand | 643 kWh/day | half of TR9's full customer demand |
| Prosumer-meter export | 1,551 kWh/day | 69% of PV leaves the prosumer meters |
| Prosumer-meter import | 13.6 kWh/day | 2.1% of prosumer demand |
| SCR (PV used at the meter) | 30.8% | capped by storage size, not by dispatch |
| SSR (prosumer demand met locally) | 97.9% | near-perfect, for the prosumers |
| Prosumer-periods within 50 W | 57.5% | more than half the day within 50 W of balance |

The same day at feeder level:

| Quantity | Value |
|---|---|
| TR9 demand, all 172 customers | 1,248 kWh/day |
| of which the 82 PV-less customers | 605 kWh/day |
| TR9 PV | 2,241 kWh/day — every panel is on a prosumer roof |
| **TR9 net export upstream** | **932 kWh/day = 42% of PV** |
| PV / demand | 1.8x |

The ratio that explains the shape of the day: **PV is 3.5x the prosumers' own demand,
and 1.8x TR9's.** No dispatch policy can self-consume 2,241 kWh into 643 kWh of
prosumer demand plus ~700 kWh of usable storage; the surplus must leave the meters.
Part of it is then absorbed inside TR9 by the PV-less customers, which is why the
transformer exports 932 kWh and not 1,551 kWh. The batteries' job is to place that
export well — and to make the import side vanish.

## 2. The daily cycle (SOC sheet)

Fleet-average SOC: starts at 40% -> drifts to 23.5% by 04:30 (overnight demand served
from storage) -> charges hard on the morning PV ramp (peak 1.2 kW/prosumer at 07:30)
-> sits at 97–99% from about 10:30 to 18:30, still 96.5% at 19:00 -> discharges
through the evening back to 51% by 23:30.

The fleet average does not reach 100%; it peaks just under. Individual batteries do
ride both bounds — the 10% floor pre-dawn and the 100% ceiling at midday.

## 3. Why the import is 13.6 kWh and not zero

Counting the prosumer-periods that import more than 1 W, there are **74** of them, and
they carry 13.4 kWh of the 13.6 kWh total. Of those 74: **74% occur with the battery
at its SOC floor** (mean SOC at those events 12.0%, floor 10%), **all 74 fall in the
dark hours** (pre-dawn 01:00–06:00 or late evening 20:30–23:30), and **none is at the
discharge power limit**.

The import is *energy-limited, not power-limited*: through the no-PV stretch the
battery discharges to hold net at zero until MinSOC_def forbids further discharge; the
remaining overnight demand can only come from the grid. Three model ingredients set
where the floor is hit: bounded usable energy (10% floor), round-trip losses
(eta^2 ~ 0.90), and the cyclic-SOC band (the plan may not run itself flat). The model
is *correctly refusing to over-discharge*; the residual is 2.1% of prosumer demand.

## 4. Why the export basin is deep (and welcome)

The prosumer export residual (midday, avg −2.3 kW/prosumer, fleet total −209 kW at
12:30) coincides with the SOC plateau: storage is above 98% by 11:00 and surplus PV
has nowhere else to go (curtailment disabled). This is not a dispatch failure — it is
the sellable surplus.

Two cautions when carrying this into the FOR work. First, −209 kW is the prosumer
fleet; TR9's own midday surplus is −178 kW, and the FOR baseline at that period is
−2,258 kW because it is the **whole feeder**, all nine transformers. Second, the FOR
is *smallest* at midday — the P width of the TR9 region at period 25 is 0.287 MW, the
narrowest of the 48 periods (saturated batteries = least flexibility). The
self-consumption result and the FOR result are two views of the same physics, but they
are measured at different places, and the numbers should not be compared without
saying so.

## 5. Distribution across prosumers (ProsumerMetrics sheet)

- **SSR:** rounds to 100.0% for 72 of 90 prosumers, and 76 import no more than
  0.1 kWh/day. No prosumer is at exactly zero import. Minimum SSR is 77.1%. The 14
  prosumers importing more than 0.1 kWh/day are those with the least favorable
  storage-to-overnight-demand ratio.
- **SCR:** spread 13.8–92.0%, median 29.7%. High-SCR prosumers are the small-PV ones
  (their generation fits their demand + battery); low-SCR prosumers have large PV
  relative to load.

## 6. Fidelity notes (honest accounting)

- **Exact vs linearized dispatch:** the committed baseline differs from the
  linearized run by ~0.003 MW per fleet-step where limits engage; every metric above
  is unchanged to the reported precision. The FOR boundary differs more (exact sits
  ~2.8% smaller in area, 6.6% at midday) — see TR9_FOR_exact_vs_linearized.png.
- **Two rows of residual simultaneous charge/discharge** (battery
  `BES_TR9_five881_C`, steps 26–27, 3.0 and 2.9 kW of overlap across that hour,
  ~0.3 kWh of extra round-trip loss): a numerical residue of the loosened exact-QCP
  barrier settings (Barrier_Convergence_Tolerance 1e-2 — the throughput-penalty
  gradient on a 3 kW overlap is below the convergence slack). 4,318 of 4,320 rows are
  clean; the linearized run was 4,320/4,320. If it ever matters, tightening the
  barrier tolerance for the committed baseline solve only would remove it at modest
  runtime cost.

## 7. What this feeds

- The **FOR chapters**: this dispatch is the committed starting point every FOR
  sweep departs from (reachability). Note the change of measuring point — the
  dispatch is at prosumer meters, the FOR is at the feeder slack bus.
- The **DOE dispatch study**: the midday saturation window is the interesting
  period to disaggregate fairly (least flexibility, tightest fairness problem);
  the deep-export window is where the service value is.

---

*Every number in sections 1–5 was rebuilt from `FOR_rolling_soc_TR9.csv` (4,320 rows,
all Optimal) and `TR9_load_PV_48periods.xlsx`, and checked against the dispatch
workbook.*
