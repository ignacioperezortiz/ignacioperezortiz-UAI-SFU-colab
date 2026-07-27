# Per-transformer results

For each transformer (`TR1`–`TR9`) there are two files:

- **`TR<n>_analysis.xlsx`** — the analysis workbook: rolling-horizon results,
  self-consumption / self-sufficiency metrics, prosumer breakdown, and battery
  SOC behaviour, with charts.
- **`TR<n>_analysis.md`** — a short written summary of that transformer's results
  (renders directly here on GitHub).

| File | Transformer |
|------|-------------|
| `TR1_analysis.xlsx` | TR1 |
| `TR2_analysis.xlsx` | TR2 |
| `TR3_analysis.xlsx` | TR3 |
| `TR4_analysis.xlsx` | TR4 |
| `TR5_analysis.xlsx` | TR5 |
| `TR6_analysis.xlsx` | TR6 |
| `TR7_analysis.xlsx` | TR7 |
| `TR8_analysis.xlsx` | TR8 |
| `TR9_analysis.xlsx` | TR9 |

> These are static snapshots for review. GitHub does not preview `.xlsx` inline —
> download a file to open it in Excel.

## Flexibility operating regions

- **`TR9_FOR_rolling.xlsx`** — the rolling FOR workbook for TR9: one region per
  half-hour (48 rolling steps × 12 boundary directions = 576 solves), with the
  batteries-off baseline, the absolute region and the deviation region, and a chart
  pair per period.
- **`TR9_FOR_rolling.md`** — how to read it, and which of the two regions to use for
  fairness and dispatch.

Start with the `.md`. The short version: the **absolute** region says where the feeder
is, the **deviation** region says what the batteries can do about it, and the
deviation is the one to allocate and dispatch on.
