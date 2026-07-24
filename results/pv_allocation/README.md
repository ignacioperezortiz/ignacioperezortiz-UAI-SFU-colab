# PV allocation — prosumers vs. pure customers

Where does each feeder's rooftop PV actually go? This folder tracks every kWh of
prosumer PV to its destination, for all nine transformers, over one representative
day (48 half-hours).

Each prosumer's PV is allocated every half-hour in **priority order**:

> **PV → prosumer's own load → charge battery → nearby pure-customer load → export to grid**

and grid import covers any load the PV cannot. The point of interest is how much PV
reaches the **pure customers** (load only, no PV or battery).

## What's here

Per feeder (`TR1/` … `TR9/`):

| File | What it is |
|------|------------|
| `TRn_PV_allocation_prosumers_vs_customers.xlsx` | Auditable 8-sheet workbook. The raw per-connection PV/load profiles and per-battery charge/discharge are pasted verbatim (sheets 3–6); the per-half-hour allocation and daily totals are then built with **live Excel formulas** (sheet 7–8). Change any raw cell and everything recomputes. |
| `TRn_pv_allocation_briefing.pdf` | Two-page briefing: context, key finding, the "where the PV goes across the day" figure, and two summary tables. |

## Headline results

Priority allocation, one representative day. "Cust. load from PV" = share of the pure
customers' daily demand supplied by neighbours' rooftop PV.

| Feeder | Prosumers | Customers | PV (kWh/day) | → customers (% of PV) | Cust. load from PV |
|--------|----------:|----------:|-------------:|----------------------:|-------------------:|
| TR1 | 77 | 55 | 1,797 | 10.8 % | 53.8 % |
| TR2 | 95 | 82 | 2,370 | 12.8 % | 53.0 % |
| TR3 | 49 | 21 | 1,316 |  6.4 % | 51.7 % |
| TR4 | 46 | 29 | 1,163 |  8.7 % | 49.7 % |
| TR5 | 214 | 203 | 5,100 | 14.2 % | 50.4 % |
| TR6 | 262 | 272 | 6,477 | 15.6 % | 51.1 % |
| TR7 | 259 | 294 | 6,526 | 17.3 % | 51.4 % |
| TR8 | 124 | 176 | 3,081 | 20.8 % | 51.4 % |
| TR9 | 90 | 82 | 2,241 | 14.2 % | 52.7 % |
| **Fleet** | **1,216** | **1,214** | **30,072** | **15.0 %** | **51.4 %** |

**Two robust patterns across all nine feeders:**

1. **An invariant.** Pure customers draw **~50–54 %** of their electricity from
   neighbours' rooftop PV on every feeder (mean 51.7 %), regardless of feeder size
   (70–553 connections) or PV volume (1.2–6.5 MWh/day).
2. **A clean driver.** The customers' *share of PV* rises almost linearly with the
   customer-to-prosumer ratio (R² = 0.99): from 6.4 % (TR3) to 20.8 % (TR8). Export
   mirrors it downward — from 64 % (TR3) to 49 % (TR8).

## Method & provenance

- **Inputs:** per-connection load & PV profiles (`TRn_load_PV_48periods.xlsx`, from
  OpData); battery dispatch from the exact-QCP rolling OPF (`RunFOR_Rolling`, CPLEX);
  connection classification by PV size (`PVsize > 0` ⇒ prosumer).
- **Caveat:** downstream network and battery round-trip losses (~3–4 % of PV) are not
  separated out in the per-period disposition.
- **Validation:** the allocation conserves energy every half-hour (worst residual
  < 10⁻¹³ kW), and the total PV / total load / prosumer demand each match two
  independent source workbooks (`Aggregate` sheet and dispatch `FleetAverage`) to
  < 0.1 kWh on every feeder.
