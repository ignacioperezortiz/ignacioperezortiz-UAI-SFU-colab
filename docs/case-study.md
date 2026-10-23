# Case study: how to run it and how to record the results

Tulio and Nacho, from the meeting of 22 October 2026 (`Case_Study_Meeting_Summary_2026-10-22`). This file is the
reference for the case-study runs of paper 1: what is run, with which inputs, how, and how every result is recorded.
**Decisions that are still open are marked OPEN; do not run a case that depends on one before it is closed here.**

---

## 1. What the case study is

1. **Run A (no service).** The rolling framework over one day, 48 half-hour periods, with no TSO request. The FOR is
   built at every period: the reference FOR and two fairness variants. Both network scopes: **Nacho runs the whole
   feeder, Tulio runs the nine transformers one by one.**
2. **Whole feeder vs transformers.** The whole-feeder FOR is compared with the Minkowski sum of the nine transformer
   FORs, period by period, with the computation times.
3. **Run B (one service).** As Run A, plus **one** service in period 25. The set-points are recovered from the stored
   FOR corners (no new optimisation for the dispatch), the rolling horizon continues, and the later trajectory, SOCs,
   self-consumption and FORs are compared with Run A.
4. **Fairness.** Daily FOR area with and without fairness, an overlay at period 25, contributions by aggregator and
   their relation to electrical distance. Later: sensitivity to the tolerance of the HB criterion (section 9).
5. **Later extension.** FORs only in selected windows of the day (section 10); does not block Run A.

## 2. Model version and inputs (frozen for all runs)

| Item | Value | Where it comes from |
|---|---|---|
| Model | `main` after the case-study PR (paper-1 model + fairness PR #25 + this setup) | Git: the run record stores the commit and the SHA-256 of `MainProject/OPF.ams` |
| Network, profiles, devices | case `v1_baseline` (`Database.mdb`, `Database.dsn`, `OpData.xls`, not in Git) | shared folder; SHA-256 in the run record (`Database.mdb` 8b474da7f5b57956 before AIMMS opens it) |
| Aggregators | three aggregators, distance-based (section 4), `CaseAggMap=1` | `inputs/case-study/` (in Git) |
| Feeder | ENWL 6.6 kV, nine 6.6/0.433 kV transformers (fixed tap), 4,579 nodes, 2,430 customers | `Database.mdb` |
| Prosumers | 1,216 with PV 1–4 kWp (mean 3.06, total 3,723.5 kWp) and a battery 3.6 kW / 4.2 kWh, efficiency 0.9487 each way, SOC 10–100 %, start 40 % | `Database.mdb` (Batteries, LoadsAndPV) |
| Time | 48 periods of 30 min from 00:00; one day | model (`nPeriods = 48`) |
| Voltage limits | 0.94–1.10 pu at customers; feeder head 1.0 pu | `Database.mdb` (Buses), model |
| Paper-1 flow | P1 behind the meter, network check at every step, plan once, delivery from corners only, PV always exported (`free_today`) | runner settings (`fin`), written to `scenario.txt` |
| Self-consumption guarantee | on (`SCAlpha = 0`, `SCTight = 1`) | model defaults |
| Fairness rows | headroom box on, effective headrooms (`FairBox = 1`, `FairEffHead = 1`) | `PV2_Run` defaults (PR #25) |
| FOR | 12 directions, every 30° | model |
| Solver | CPLEX 22.1 (pinned by `SCT_UseCPLEX`), exact QCP | model |
| AC audit | `ACAudit=1` in the transformer runs: every FOR corner checked with an AC power flow and, if it breaks a limit, the point option C would offer instead; a log only (`FOR_rolling_ac<tag>.csv`), results unchanged. Off for the whole feeder | model (section Paper1, `ACAudit_Declarations`) |
| AIMMS | 26.3.2.1 (Tulio); Nacho's version in his records | run record (`aimms_cmd`) |

Every run records these automatically (section 6). Nothing in this table may change during the campaign without a
new PR and a note here.

## 3. Conventions

- **Periods.** Period *t* = the half-hour starting at (t − 1) × 30 min: t = 25 is 12:00–12:30.
- **Request vs execution.** At rolling step *k* the model builds the FOR of period *k + 1* (output column `now` = k,
  `target` = k + 1). A request "at period 25" is a point of the FOR of period 25, built at step 24; its set-points are
  executed in period 25 (step 25). The FOR of step 48 is the first period of the next day.
- **Interface and signs.** P and Q are the exchange at the 6.6 kV feeder head, positive = import from the upstream
  grid (`FOR_rolling*.csv`: MW and Mvar; summaries: kW and kvar).
- **Comparing FORs across scopes.** Every FOR is expressed as a deviation from the run's own scheduled exchange for the
  same period (the executed exchange in Run A). A transformer-level run carries the other eight transformers as passive
  load at the feeder head; the deviation removes it. Minkowski sum = the nine deviations added direction by direction
  (each corner maximises cos θ·P + sin θ·Q). OPEN: confirm this convention and the treatment of MV losses.

## 4. Aggregator assignment (`inputs/case-study/`)

Three aggregators of almost equal size (406 / 406 / 404). **Agg3** has more prosumers that are electrically far from
their LV transformer; Agg1 and Agg2 have similar distance spreads. Electrical distance = sum of the series
self-impedance |Rs + jXs| of the cables from the transformer's LV side to the prosumer (p.u. on 1 MVA / 0.4 kV;
1 p.u. = 0.16 Ω). In every transformer, a third of the prosumers is drawn for Agg3 with a probability that rises with
their distance rank in that transformer (Gaussian weight centred on the 90th percentile, σ = 0.2, seed 20261022); the
rest is split at random between Agg1 and Agg2. Result: Agg3 median 2.96 p.u. (0.47 Ω), Agg1 / Agg2 about 1.9 p.u.
(0.31 Ω); full statistics in `aggregators_stats.md`.

- Files: `aggregators_config.json` (settings), `aggregators.csv` (one row per battery: distance, percentile,
  aggregator), `aggregators_case_study.txt` (what the model reads), `aggregators_stats.md`.
- The model uses it when the job line has `CaseAggMap=1` (all case-study queues do); without it, the aggregators of
  `Database.mdb` are used (the earlier random assignment). The run summary (`SCT_info`) prints the aggregator sizes.
- To regenerate (only if the settings change, together): `export_network.ps1` then `make_aggregators.py`;
  `make_aggregators.py --check` confirms the committed files.

## 5. How to run

### 5.1 Before the first run (both)

1. `git checkout main && git pull` (the case-study PR merged). Do not run from a branch with uncommitted changes.
2. Put the three `v1_baseline` files in the repository root.
3. Use the AIMMS project file of your AIMMS version (`--project`, see `docs/paper1-model-guide.md` §3).

### 5.2 Tulio: the nine transformers

```
python scripts/paper1/run_paper1.py prepare L1 L2 L3 --strict --work ..\paper1-runs --project <OPF.aimms of AIMMS 26.3>
python scripts/paper1/run_paper1.py lane L1 scripts/paper1/queues/case_study_A_transformers.txt --work ..\paper1-runs
```
(one `lane` command per seat: L1, L2, L3; start them about a minute apart). The queue holds 27 jobs: three variants ×
nine transformers, longest first. TR6 and TR7 use the sequential sweep and never run at the same time (memory); the
other lanes take the next job meanwhile. Expected: about 14 h per variant on three seats, so about 2–2.5 days in all
(TR6 / TR7 take 8–9 h each), plus about 10–25 % for the AC audit (`ACAudit=1`, a log only).

### 5.3 Nacho: the whole feeder

```
python scripts/paper1/run_paper1.py prepare W1 --strict --work ..\paper1-runs --project <your OPF.aimms>
python scripts/paper1/run_paper1.py lane W1 scripts/paper1/queues/case_study_A_whole_feeder.txt --work ..\paper1-runs
```
Three jobs (reference, HP within each aggregator, HP network-wide), about 2 days each at full scale (adjust the speed
name `a3x5p16fin` to your machine, `docs/parallel-sweep-memory.md`). Watch `FOR_rolling_progress<tag>.txt`; if it
stops for more than 45 min, re-run that job with a sequential sweep (`a0x...`) and tell Tulio.

### 5.4 Run B (after its decisions)

`scripts/paper1/queues/case_study_B.txt` and `scenarios/CS_B_t25.json` are **blocked** (OPEN: requested point and
fairness case). When decided: set `requests` in `CS_B_t25.json`, delete its `blocked` key, keep one fairness case in
the queue, record the choice in section 11, and run it like Run A.

## 6. How every run is recorded

**No run without a record, nothing overwritten, nothing from uncommitted code.**

1. The runner writes `prepare_info.json` in each lane (commit, uncommitted changes yes/no, SHA-256 of the model and
   input files) and, after every job, `record<tag>.json` (job line, scenario, start/end, wall time, return line,
   computer, AIMMS, every output file with its SHA-256).
2. After a job ends, record it:
   ```
   python scripts/paper1/case_study/collect_run.py ..\paper1-runs\L1 <tag> --who Tulio
   python scripts/paper1/case_study/collect_run.py --all ..\paper1-runs --who Tulio       # every finished job not yet recorded
   ```
   This gives the run an id **`CS-<run>-<network>-<variant>-r<n>`** (e.g. `CS-A-TR4-REF-r1`, `CS-A-ALL-HPi-r1`,
   `CS-A-TR9-HPn-r1`, `CS-B25-TR4-REF-r1`; HPi = HP within each aggregator, HPn = HP network-wide). A repeat of the
   same case gets `r2`, never the same id. It writes:
   - `results/case-study/records/<run_id>.json`: the run record;
   - `results/case-study/summary/<run_id>/`: compact files for the figures (`for_corners.csv`, `fleet_by_step.csv`,
     `prosumer_day.csv`, `fairness_*.csv`, `requests.csv` / `service.csv` for Run B, `time_per_step.csv`, `info.txt`);
   - `results/case-study/runs.csv`: the register, rebuilt from all records (never edit it by hand);
   - `..\case-study-raw\<run_id>.zip`: every output file of the job. **Upload it to the shared folder
     `CaseStudy/raw/`**; its SHA-256 is in the record. Raw outputs are not committed.
3. A run from a working tree with uncommitted changes is refused (`--allow-dirty` only for tests; flagged in the register).
4. A failed run (no `Return value = 0`) is not recorded as a result: note it in the run log of the PR and re-run.

## 7. Pull requests

- **Code PRs** (model, runner, scripts): one idea each, from an up-to-date `main`, with the evidence that results did
  not change where they should not (`scripts/paper1/ams_compare.py` for `OPF.ams`, and an identity run). Announce
  before editing `OPF.ams` (AIMMS rewrites the whole file): only one of us edits it at a time (`CONTRIBUTING.md`).
- **Results PRs** (`results: Run A <scope> <variants>`): only files under `results/case-study/` (records, summaries,
  register, analysis outputs); no code change in the same PR. The description lists the run ids, the commit they ran
  on, the computer, and anything unusual (failed or repeated runs, stalls). Raw zips are in the shared folder before
  the PR is opened.
- Tell the other person on WhatsApp when a batch starts, when it ends, and when its results PR is open.

## 8. Comparisons (what to compute)

| Comparison | Script | Notes |
|---|---|---|
| Daily FOR evolution, fairness cost | `analysis/for_area.py` | area of each 12-corner FOR (kW·kvar); fairness ratio = Σ fair areas / Σ reference areas over the same periods, zero-area periods counted and excluded |
| Whole feeder vs Minkowski sum | `analysis/minkowski.py --variant REF` | per period: areas, largest directional differences, solve times; compare the reference FORs first (a fairness rule applied per transformer is not the same rule over the feeder) |
| Run B vs Run A | (to add with Run B) | delivered vs requested exchange, set-points against the model's limits (voltage, thermal, battery), SOC and imports per prosumer after period 25, later FORs |
| Computation time | records + `time_per_step.csv` | report solver settings and computers; the two computers differ, so wall times alone do not isolate the effect of decomposition |
| AC audit of the FOR corners | `analysis/ac_audit.py` | corners that break a limit in AC and why; how far option C would move them; FOR area kept with the audited corners; audit time |

Setpoint feasibility (meeting §10): record, for Run B, the interface tracking error and the voltage, thermal and battery
limits of the recovered dispatch in the model; keep model feasibility separate from any AC validation. The AC audit
(`ACAudit=1`) checks every corner in AC and logs the point option C would offer, without changing any result;
`ACAuditApply=1` would replace the corners used for delivery (option C) and therefore change Run B: comparison only.

## 9. Fairness tolerance (later, transformers only)

The meeting's "HP / HC" with parameter "E" is, in the code, criterion **HB** (`FairCrit = 3`) with tolerance
**ε = `FairEps`**: −ε·D ≤ ΔP − (ζ↑U − ζ↓D) ≤ ε·U. ε = 0 is HP exactly; Nacho's reference value is 0.1. OPEN: test
values (proposal: ε = 0, 0.05, 0.1, 0.2) and scope.

## 10. Selected windows (later)

FORs only in selected windows (morning ramp, midday export, afternoon ramp, evening peak; about 10–12 periods). OPEN:
the exact periods (both of us use the same), justified from the case profiles and public UK information. Measure the
cost; do not scale the 48-period total by a period ratio (solve times vary over the day).

## 11. Decisions

| Decision | Status |
|---|---|
| Aggregator assignment | **Closed 23 Oct**: weighted draw, equal sizes, Agg3 far (section 4) |
| Run A variants | **Closed 23 Oct**: reference + HP within each aggregator + HP network-wide, both scopes |
| Results storage | **Closed 23 Oct**: records and summaries in Git, raw zips in the shared folder |
| AC check of the FOR corners | **Closed 23 Oct**: as an add-on that does not change the results: `ACAudit=1` in the transformer runs (log only); `ACAuditApply=1` (option C) for comparisons only |
| Interface convention for the Minkowski comparison | OPEN (proposal in section 3) |
| Run B: requested point and fairness case | OPEN (period 25 agreed) |
| Fairness tolerance values | OPEN (section 9) |
| Selected windows | OPEN (section 10) |
