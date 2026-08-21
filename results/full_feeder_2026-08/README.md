# Whole-feeder rolling FOR, m=0 — August 2026

Raw output of the first whole-feeder production run that has ever completed. Until this run
`docs/network-scope.md` §4 recorded it as *never yet completed*.

Entry point `RunFullFeeder_NoFairness`, launched headless with
`AimmsCmd --run-only` on AIMMS 26.2.3.3-x64-VS2022.

| File | What it is |
|---|---|
| `FOR_rolling_full_m0_20260817.csv` | the FOR itself — one row per vertex: P, Q, projection, status, solver time, true voltage extremes, linearisation error |
| `FOR_rolling_fair_full_m0_20260817.csv` | per-aggregator block for the same vertices |
| `FOR_rolling_soc_full_m0_20260817.csv` | committed battery dispatch and SOC trajectory, one block per period |
| `FOR_rolling_progress_full_m0_20260817.txt` | the progress marker as it stood at the last vertex |

## The run

| | |
|---|---|
| Scope | 48 periods × 12 directions = **576 vertices**, full network (`ReduceNetwork = 0`) |
| Result | **576/576 optimal, zero failures** |
| Started | 2026-08-14 12:16:20 |
| Ended | 2026-08-17 22:26:32 |
| Wall clock | **82.17 h** (3.42 days) |
| Solver time | 55.05 h — the remaining 27 h is the per-period matrix generation |
| Per vertex | 344.1 s mean, 467.6 s worst |

Configuration: `FairMode = 0`, `UseBattComp = 0` (pure QCP), `RollUseGMP = 1`,
`RollGMPBaseline = 1`, `ReduceNetwork = 0`, `DetailTagCSV = ""`.

## Two things worth reading off these files

**Zero non-optimal vertices at m = 0.** The m = 4 fairness run reached 542/576. Those 34
failures are introduced by the fairness constraint, not by the network or the solver — this
run is the control that shows it.

**The first three periods reproduce bit-identically** against the 3-period partial of
2026-08-13 (`FOR_rolling_*_p3_20260813.csv`, kept outside the repository), across all three
CSVs, comparing every column except `time`.

## Why these are versioned when `.gitignore` excludes run CSVs

Excluding run output is the right default and stays the default — see
`results/gmp_validation_2026-08/README.md`, which tells you to regenerate rather than read.
This run is the exception: reproducing it costs 82 hours of a machine, so "regenerate it"
is not a real answer to a question about what it contains. `.gitignore` carries an explicit
negation for this directory and nothing else.

Reproduce with `RunFullFeeder_NoFairness`. Compare against a re-run with
`scripts/compare_FOR_runs.py`; the invariant is `proj`, not `P`/`Q`, and `time` never
compares.
