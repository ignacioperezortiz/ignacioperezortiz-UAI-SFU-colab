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

- **`TR9_FOR_rolling.xlsx`** — the rolling FOR workbook: one region per half-hour
  (48 rolling steps × 12 boundary directions = 576 solves), measured at the feeder
  PCC with TR9's batteries as the flexible resource, with the batteries-off baseline,
  the absolute region and the deviation region, and a chart pair per period.
- **`TR9_FOR_rolling.md`** — how to read it, and which of the two regions to use for
  fairness and dispatch.

Start with the `.md`. The short version: the **absolute** region says where the feeder
is, the **deviation** region says what the batteries can do about it, and the
deviation is the one to allocate and dispatch on.

## Fairness

- **`TR9_fairness.md`** — the rolling FOR under the capacity-proportional fairness
  criterion C1, at two levels (between prosumers and between aggregators), against the
  no-fairness reference run. Covers what is imposed and where, how it was verified,
  runtime, how much the region contracts, and the main finding: under prosumer-level
  fairness a single battery on its SOC floor idles the whole fleet.
- **`viz/FOR_fairness_TR9.html`** — interactive viewer for those three cases on TR9
  (90 prosumers): region per period, absolute and deviation views, `zeta` and the
  contraction series. Self-contained — no network access, opens with a double click.
- **`viz/FOR_fairness_micro.html`** — the same viewer for the micro test bed
  (`TR9_two`, 12 prosumers), which is the sharper test of aggregator-level fairness.

Both HTML files are rebuilt by `scripts/make_viz_data.py` + `scripts/build_viz.py`.

> As everywhere else in this repository, the raw model outputs behind these files
> (`FOR_rolling*.csv`, including the new `FOR_rolling_fair*.csv` fairness log) are
> **git-ignored** and shared separately — they regenerate on every run. See
> `CONTRIBUTING.md` §3.
