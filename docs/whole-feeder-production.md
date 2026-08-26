# Running the whole feeder: what works, and what hangs

**2026-08-23.** Two accelerations were taken to the full feeder. One works and is now the
default. The other — the parallel sweep — **hangs intermittently at whole-feeder scale** and is
deliberately off. This records both, the measurements, every test run, and one diagnosis that
was wrong for a day.

---

## 1. The two accelerations, and whose they are

Both existed before this work. Neither had been run on the full feeder, and **the code could
not express them together**.

| | origin | what it does |
|---|---|---|
| **Network-free committed baseline** | asked for by **Prof. Luis**, implemented and validated by **Tulio** (`BaseNoNetwork`, PR #16) | the committed self-consumption solve drops the `NetworkModel` section. Validated on TR4: 48 baseline solves fell from ~6 min to 13 s, max abs dP = 2.7e-7 p.u. |
| **Parallel sweep** | **Tulio** (`RollAsyncK` / `RollAsyncThreads`, PR #16) | a period's 12 sweep directions solve `RollAsyncK` at a time, each on its own copy of the period instance. Measured across nine reduced transformers: 35.7 h to 19.6 h |

**Why they could not be combined.** `BaseNoNetwork = 1` forces `RollGMPBaseline = 0`, because
the shared instance carries the network rows and so cannot serve a network-free baseline.

---

## 2. What works: `BaseNoNetGMP`

`Default: 0`, inert unless set. With `RollUseGMP = 1` and `RollGMPBaseline = 1` it deactivates
the `NetworkModel` rows around the committed baseline solve **on the shared instance**, so the
baseline is network-free without giving up the single generation per period.

27 `GMP::Row::DeactivateMulti` calls and their exact mirrors: the 20 constraints of
`Section NetworkModel` (lines 583-1032), the 5 defining rows of its defined variables
(`Vmag2approx`, `Ire_Gen`, `Ire_Load`, `Iim_Load`, `Iim_Gen`), and `P_PCC_definition` /
`Q_PCC_definition`.

Two design points worth keeping:

- **The defining rows must come out too.** Leaving them active makes the baseline infeasible.
- **No `FreezeMulti`.** A column that never entered the matrix cannot be frozen. `BattInvPn`
  does not exist when `FOR_ScaleInv = 0`; `MaxBattS_poly` rows do not exist when `FOR_PolyS = 0`;
  `FixedTaps` exists only for non-OLTC transformers; `Ire_Trafo` columns exist only for the two
  buses a transformer touches. Deactivating `P_PCC` and `Q_PCC`'s defining rows as well leaves
  every network column in no active row at all, so presolve drops them. Each binding domain
  mirrors its row's own `IndexDomain` condition.

`tGMP` is a second index on `Time`, added because the baseline block sits inside `for (t) do` and
`t` is not free for a binding domain. Purely additive: it appears in no definition.

### What it buys, measured

| | reference 2026-08-17 | with `BaseNoNetGMP` |
|---|---:|---:|
| period boundary | 36 min | **24 min** |
| over 48 periods | — | **about 9.6 h** |

### That it does not move results

- **TR3, `RunTR3_Base3b` vs `RunTR3_BaseNoNet`:** 576/576 `Optimal`, max abs dproj = 0.000e+00,
  and the committed dispatch identical column by column — `SOC_start`, `Pexec`, `Chg1`, `Dis1`
  all 0.000e+00.
- **Whole feeder, the six periods that completed on 2026-08-22:** 72/72 `Optimal`, `OVviol`
  unchanged at 1.867e-10 in every vertex, and the FOR area within **±0.0024 %** of the reference.

---

## 3. What hangs: the parallel sweep on the full feeder

`GMP::Instance::Copy` **does not return**. One thread at 100 %, memory flat, no vertex, no
error, and no time limit fires because nothing ever reaches a solver.

| date | run | outcome |
|---|---|---|
| 2026-08-21 | `RunFullFeeder_AsyncNoNet`, K=2 | hung in **period 1**. 9 h 06, 1 thread of 72, RSS frozen at 17.08 GB, **zero vertices**. Not memory: 26.5 GB free and RSS not growing |
| 2026-08-22 | `RunFullFeeder_3b` at K=2, from an uncommitted scratch copy — the configuration now preserved as `RunFullFeeder_ParallelRepro` | ran periods 1-6, then hung in **period 7** for 16.7 h. 1 thread of 72 with 22 h of CPU, RSS 20.23 GB, 33.7 GB free |

**The second hang refutes the first explanation.** For a day the working diagnosis was "the async
path copies an instance that was never solved" — `BaseNoNetwork = 1` forces `RollGMPBaseline = 0`,
which moves generation into the sweep block. `BaseNoNetGMP` was built to fix exactly that, and it
did put a solved shared instance in front of the copy. Periods 1 to 6 went through. Period 7 hung
anyway, with the baseline's own SOC block already written to disk at 23:06:53.

So the cause is **not** the never-solved instance. It is intermittent, it is specific to
whole-feeder scale — nine reduced transformers and hundreds of TR3 periods never showed it — and
**it is not understood**.

What is ruled out: memory (tens of GB free, RSS flat rather than growing or thrashing), the
machine (TR3 at 6x4 gives 9.78 cores and 306/306 `Optimal`), and the settings (`RunTR3_BaseNoNet`
reproduces the exact configuration at reduced scale, 48/48 `Optimal` in 83 s).

**A one-period success is not evidence of reliability.** `RunFullFeeder_Async` on 2026-08-22
completed period 1 cleanly and was read as proof the copy works at this scale. Period 7 shows one
period proves nothing about the next.

---

## 4. The runner

```
RunFullFeeder_Production
```

Shared instance, network-free committed baseline, **sequential sweep** (`RollAsyncK = 0`). The
cost of going sequential is small, because the copy ate most of what the parallelism won:
measured periods were 76-92 min at K=2 against roughly 83 min projected sequential, the boundary
being 24 min either way. `RunFullFeeder_NoFairness` is kept as the reference that produced
`results/full_feeder_2026-08/`. `RunFullFeeder_ParallelRepro` preserves the configuration that
hangs, so the failure can be reproduced rather than only read about.

**Neither `RunFullFeeder_Production` nor `RunFullFeeder_ParallelRepro` has written a byte on this
machine.** The measurements in section 2 come from `RunFullFeeder_3b`, a scratch-copy sibling with
an identical body bar the file suffix. A full 48-period run under the committed name is still owed.

Headless:

```
AimmsCmd.exe --run-only RunFullFeeder_Production <repo>\OPF.aimms
```

Check against the reference on `proj`, never on `P`/`Q` — the sweep maximises a linear functional
over a convex set, so a flat face admits many argmaxes:

```
py -3 scripts/compare_FOR_runs.py \
    results/full_feeder_2026-08/FOR_rolling_full_m0_20260817.csv \
    FOR_rolling_full_prod.csv
```

### Watch for a stall, not only for a slow start

Both hangs were silent. The 2026-08-22 one ran 16.7 h unnoticed because the monitor only alarmed
if the *first* vertex never appeared. `FOR_rolling_progress_full_prod.txt` is rewritten after
every vertex: alarm when its mtime stops advancing for longer than a period boundary plus a
solve — roughly 45 min — at any point in the run.

**There is no resume.** An interruption restarts at period 1.

---

## 5. An acceptance criterion for a rolling run

Over 48 chained periods, **bit-identity is not achievable** by any run that changes the solve
path. Each period freezes a committed dispatch and carries it forward as the next period's
initial state; a difference in the seventh decimal moves the next barrier trajectory.

Observed over the six periods that completed, against the 2026-08-17 reference:

| period | identical | max abs dproj | FOR area |
|---:|---:|---:|---:|
| 1 | 11/12 | 4.3e-05 | +0.0004 % |
| 2 | 2/12 | 7.2e-05 | -0.0013 % |
| 3 | 0/12 | 1.02e-04 | +0.0019 % |
| 4 | 0/12 | 4.7e-05 | -0.0013 % |
| 5 | 0/12 | 1.67e-04 | -0.0002 % |
| 6 | 0/12 | 1.25e-04 | -0.0024 % |

Deviations go both ways — 7 above and 4 smaller among the first 24 — so this is symmetric solver
noise, not a region systematically inflated or shrunk. **A single vertex can move 1.7e-04 while
the region it belongs to moves 0.0002 %**: the deviations largely cancel when the polygon is
formed. Against the 2-90 % area losses the fairness study reports, this is three to five orders
of magnitude below anything the work measures.

So the criterion should be: no `NoSolution`, no new violation (`OVviol`, `UVviol`, `VmaxTrue`),
and FOR area within a stated band of the reference — not max abs dproj = 0, which only makes
sense for a single period or a non-rolling comparison.

---

## 6. Hardening the whole-feeder runners (2026-08-23)

An audit of the nine `RunFullFeeder_*` procedures found more inheritance hazard than clutter.
These wrappers only set parameters and call `RunFOR_Rolling`, so anything they leave unset is
inherited from whatever the AIMMS session happens to hold — and a session is long-lived.

### What could go wrong silently

- **`RollLinearized` was pinned by none of the nine.** It is set to 1 by `RunTR3_Linear` and
  `RunTR7_Linear`, each with a restore whose own comment reads *"MUST reset: leaving this at 1
  would silently relax every later run."* Interrupt either before the restore and every
  whole-feeder run afterwards uses the outer relaxation — writing a region that is not
  reportable, under a production filename, with nothing to signal it.
- **`RollMaxPeriods` was pinned by none except `AsyncSmoke`, which sets it to 2.** `AsyncSmoke`
  and `Async` sit next to each other and are documented to be run in that order. Interrupt the
  smoke run before its restore and `Async` writes a two-period CSV that looks like a completed
  multi-day run: the closing block still executes, so the file is well formed.
- **`RunFullFeeder_NoFairness` pinned the least of all nine** — no `EnableRollDiag`,
  `RollAsyncK`, `RollAsyncThreads`, `RollMaxPeriods`, `BaseNoNetwork`, `BaseNoNetGMP` — and it
  writes `FOR_rolling_full.csv`, the reference filename. A leftover `RollAsyncK = 6` would have
  made the reference run parallel.
- **`RunFullFeeder_PreflightGMP` pinned none of `PreflightSlotOnly`, `PreflightExact`,
  `PreflightGMPBaseline`**, all three set to non-defaults by `RunFullFeeder_PreflightExact1Slot`
  immediately above it. Its own comment claims "3 slots x 12 directions", which was an assumption
  about session state rather than a property of the procedure.
- **`ReduceNetwork` and `EnableRollDiag` were declared without a `Default:` clause**, and
  `ReduceNetwork`'s comment described a default it did not declare.

### What was done

Every whole-feeder runner now pins what it depends on, including the values that equal the
declared default — the point is that the wrapper states them, not that they differ. The two
declarations got the `Default: 0` their comments already implied. Each pin carries a comment
naming the procedure that could have left the value dirty.

The two preflight wrappers were deliberately left without `RollLinearized` / `RollMaxPeriods`
pins: that path runs through `RunFOR_RollingPreflight` and reads `PreflightExact` instead, so
those two parameters never reach it.

### What was removed

`RunFullFeeder_NoNet` — referenced nowhere outside its own declaration, and its single run wrote
a CSV header and one SOC block, no vertices. It asked the model the same question as
`RunFullFeeder_Production` by the other generation path, an equivalence the `BaseNoNetGMP`
declaration already records as A/B'd at TR3.

Nothing else was removed. `RunFullFeeder_AsyncNoNet` and `RunFullFeeder_ParallelRepro` look
redundant — both are whole feeder, network-free baseline, parallel sweep — but they reach it by
the two different generation paths and **both hang**. That pair is the evidence that the state of
the copied instance does not explain the failure, which is worth more than the lines it costs.

### Regression check

`RunTR3_Base3b` was re-run from the hardened file and compared against the 576 vertices the
pre-hardening code produced: `max abs dproj`, `max abs dP`, `max abs dQ` all 0.000e+00, no status
changed.

---

## 7. `Ire_Trafo` / `Iim_Trafo` index domains

```
- IndexDomain: (tr,f,n,t);
+ IndexDomain: (tr,f,n,t) | n = StartBusTr(tr) or n = EndBusTr(tr);
```

A transformer touches exactly two buses, and all 40 references in the model use `StartBusTr(tr)`
or `EndBusTr(tr)` as the third index.

**Proven equivalent:** on the TR9 preflight, rows 565009, columns 456685, nonzeros 1956026 and
63.36 Mb are identical with and without, down to the objective row number, and max abs dproj =
0.000e+00 over 36/36 vertices.

**The speed gain is NOT established.** On the full-feeder one-slot preflight the boundary fell
from 1976 s to 1696 s (-14.2 %), but the solve — identical work on an identical matrix, which
this change cannot affect — fell 13.4 % in the same pair. The two ratios coincide, so the
difference is environment drift. Settling it needs an A-B-A pair on an idle machine, the way
`RunTR4_Timing_ABA` does. Kept for being exactly equivalent and making the declaration honest,
not for being faster.

---

## 8. Every test that was run

| # | what | result |
|---|---|---|
| 1 | `RunTR3_Base` — Tulio's exact reduced-scale config | OK. 9.78 cores, 306/306 `Optimal`, 8.93 s/solve |
| 2 | `RunTR3_BaseNoNet` — same plus `BaseNoNetwork=1` | OK. 7.84 cores, 48/48 `Optimal`, 8.15 s/solve. The settings are not the cause of the hang |
| 3 | `RunFullFeeder_Async` — full feeder, shared instance plus async | Period 1 only: 12/12 `Optimal`, 194.1 s/solve. **Read at the time as proof the copy works. It was not** |
| 4 | `Ire_Trafo` index domains, TR9 preflight A/B | Matrix identical to the last digit, max abs dproj = 0.000e+00 on 36/36. Speed inconclusive |
| 5 | `RunTR3_Base3b` — `BaseNoNetGMP=1` at TR3 | OK. 576/576 `Optimal`, dispatch identical column by column |
| 6 | `RunFullFeeder_3b` at K=2 — full feeder, both. Ran from a scratch copy, never committed; preserved as `RunFullFeeder_ParallelRepro` | Periods 1-6 clean, **hung in period 7**. Killed after 1 d 01:36, 72/576 vertices |

Partial results and the two forensic captures are kept outside the repo with the run; the six
completed periods are what section 5 tabulates.

### Two runtime errors the reduced bench caught in seconds

`t` already bound by the surrounding `for (t)`, and `BattInvPn` not in the model when
`FOR_ScaleInv = 0`. The second is why there is no `FreezeMulti` in the final design.

### The habit worth keeping

The 2026-08-21 failure launched a combination that had **never been run at any scale** against a
multi-day job. `RunTR3_BaseNoNet` — the test that exercises the same configuration — takes **83
seconds**. Run the reduced bench first. And when a whole-feeder run does start, alarm on a stall.

---

## 9. Open

- **The copy hang is not understood.** Two occurrences, different periods, both at whole-feeder
  scale, neither reproducible on a reduced transformer. Worth raising with Tulio: it is his
  machinery, and he has never been able to run the full feeder to compare.
- **The whole-feeder run with `BaseNoNetGMP` has not completed.** Its saving is measured over six
  periods and its effect on results over the same six; a full 48-period run is still owed.
- **`AimmsCmd` returns exit code 0 on a failed procedure.** The real signal is
  `Error: Procedure run failed` on stdout.
- **`scripts/watch_runs.ps1` writes to a fixed path** under
  `results/async-performance/baseline/`, which PR #15 versioned. Running it overwrites Tulio's
  committed campaign log.
