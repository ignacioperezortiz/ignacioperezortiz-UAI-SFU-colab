# Parallel sweep at K=3 × 5 threads — 13 periods, August 2026

**This is a PARTIAL run: 13 of 48 periods.** It was stopped on purpose to free the machine,
not because anything went wrong. It is kept because it is the evidence that the parallel
sweep runs on the full feeder without a single failed solver session, and because it cost
17 h of wall clock.

Do not read a total off these files. `FOR_rolling_k3_p13_20260826.csv` has 159 data rows,
which is 13 complete periods (156 vertices) plus the first 3 directions of period 14. A
complete whole-feeder run is 48 × 12 = **576 vertices** — see
`results/full_feeder_2026-08/` for one.

Entry point `RunFullFeeder_ProductionK3`, launched headless with `AimmsCmd --run-only` on
AIMMS 26.2.3.3-x64-VS2022.

| File | What it is |
|---|---|
| `FOR_rolling_k3_p13_20260826.csv` | the FOR itself — one row per vertex: P, Q, projection, status, solver time, true voltage extremes, linearisation error |
| `FOR_rolling_fair_k3_p13_20260826.csv` | per-aggregator block for the same vertices |
| `FOR_rolling_soc_k3_p13_20260826.csv` | committed battery dispatch and SOC trajectory, one block per period |
| `FOR_rolling_progress_k3_p13_20260826.txt` | the progress marker as it stood when the run was stopped |

## The run

| | |
|---|---|
| Scope | full network (`ReduceNetwork = 0`), 12 directions per period |
| Sweep | `RollAsyncK = 3`, `RollAsyncThreads = 5` |
| Started | 2026-08-25 16:50:32 |
| Stopped | 2026-08-26 10:32 (deliberately) |
| Wall clock | ~17.7 h for 13 periods |
| Result | **159/159 Optimal**, **zero synchronous rescues** |
| `OVviol` | 1.8668e-10 in every vertex, identical to the 2026-08-17 reference |
| `UVviol` | 0 |

Configuration: `FairMode = 0`, `UseBattComp = 0` (pure QCP), `RollUseGMP = 1`,
`RollGMPBaseline = 1`, `BaseNoNetGMP = 1`, `RollLinearized = 0`, `ReduceNetwork = 0`.

## What this run is evidence for

**The parallel sweep works at this scale with the right thread split.** At
`RollAsyncK = 2 × 12 threads` the last session of every batch returns `SolverFailure` and is
silently re-solved by the rescue, costing a full extra solve per batch. At 3 × 5 all three
sessions fit and no rescue is needed. The reasoning, the measurements and how to re-derive
the split on a different machine are in `docs/parallel-sweep-memory.md`.

**It also cleared period 7.** The 2026-08-22 run stopped there with 72 vertices; this run
went through it and eleven more. That is not proof that 3 × 5 is immune to the stalls
recorded in `docs/whole-feeder-production.md` §3 — those were never reproduced under any
configuration during this work — but it is the furthest a parallel sweep has got on the full
feeder.

## Deviation against the sequential reference

Compared per period against `results/full_feeder_2026-08/FOR_rolling_full_m0_20260817.csv`:
max abs `dproj` stays between 5.0e-05 and 2.27e-04, and the FOR area between −0.0035 % and
+0.0066 %, **with no trend across the 13 periods**. Period 1 is the only value outside the
band previously observed on a parallel run.

Bit-identity is not reachable here by construction — the rolling horizon freezes a committed
dispatch and carries it forward, so any difference propagates — and the deviations are three
to four orders of magnitude below anything the fairness study measures. The invariant to
compare on is `proj`, not `P`/`Q`, and `time` never compares:

```
py -3 scripts/compare_FOR_runs.py \
    results/full_feeder_2026-08/FOR_rolling_full_m0_20260817.csv \
    results/parallel_k3_2026-08/FOR_rolling_k3_p13_20260826.csv
```

## Why these are versioned when `.gitignore` excludes run CSVs

Same reasoning as `results/full_feeder_2026-08/README.md`: excluding run output is the right
default and stays the default. These are kept because they are the only record that this
configuration runs clean, and regenerating them costs most of a day. `.gitignore` carries an
explicit negation for this directory.
