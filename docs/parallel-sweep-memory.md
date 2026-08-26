# The parallel sweep on the full feeder: what limits it

**2026-08-25/26.** `docs/whole-feeder-production.md` §3 records two whole-feeder runs that
stopped producing vertices with the parallel sweep at `RollAsyncK = 2`, and attributes them
to `GMP::Instance::Copy`. This note adds instrumented measurements that change where the
limit actually is, and records a configuration that runs the parallel sweep cleanly.

Everything here was measured on one machine — Lenovo 21KT000GCL, Intel Core Ultra 9 185H
(6 P-cores + 8 E-cores + 2 LP-E, 22 logical), 63.45 GB RAM, AIMMS 26.2.3.3-x64-VS2022 with
CPLEX 22.1 — on a copy of the repository. **The numbers are machine-specific; the rule is
not.** Section 6 says how to re-derive them.

---

## 1. The instance is very large

From the CPLEX log (`option solver_listing_messages := 'all'`, which writes
`log/CPLEX 22.1.sta`):

```
Solve problem 'FORrollasync1' with 6214854 rows, 6095686 columns, and 24289627 nonzeros
```

**6.21 M rows, 6.10 M columns, 24.29 M nonzeros.** Everything below follows from that: a
single barrier factorisation on this instance is already a large memory object.

## 2. The copy is not the constraint

A timestamped trace around every GMP call in the async launch and collection loops, over a
full period of 12 vertices:

| call | n | median | range |
|---|---:|---:|---|
| `GMP::Instance::Copy` | 12 | **3 s** | 2–4 s |
| `GMP::Coefficient::Set` ×2 | 12 | 0 s | — |
| `GMP::Instance::CreateSolverSession` | 12 | 0 s | — |
| `GMP::SolverSession::AsynchronousExecute` | 12 | 3 s | 3–4 s |
| `GMP::SolverSession::WaitForCompletion` | 6 | 335 s | 305–346 s |
| `GMP::Instance::Delete` | 12 | 3 s | 2–6 s |

The copy takes about 3 s and completed on all ~60 traced calls across six runs, with and
without a solve in flight (3 s alone, 4 s while a session was solving). It is not slow and
it did not fail.

## 3. What does fail, and why it was hard to see

In **every** batch, the **last solver session launched** comes back with:

```
C1 async returned NoSolution / solver SolverFailure
C2 SYNCHRONOUS RESCUE start
C3 SYNCHRONOUS RESCUE end, status Optimal
```

The rescue in `RunFOR_Rolling` re-solves that direction on its own copy and succeeds, so
**the vertex written to the CSV is correct**. What the CSV records is `Optimal` and the
*asynchronous* session's `GetTimeUsed` — the declaration of `Roll_SolTime` says so
explicitly: *"The synchronous rescue solve, when one ran, is NOT included."*

Two consequences worth naming, because they cost real time:

- The failure leaves no trace anywhere. CPLEX prints its parameter header for the failing
  problem and then no termination line at all — no optimum, no error, no memory message.
- **The step-1 acceptance check in `docs/whole-feeder-parallel.md` cannot fire.** It says
  *"Any `NoSolution` at this scale means memory, not mathematics. Stop — `K=2` does not
  fit."* That check was pointed at exactly the right thing, but the rescue rewrites the
  `NoSolution` before the CSV is written, so there is nothing for it to catch.

The signature was visible in the `time` column all along, once you know to look: at K=2 the
first direction of each batch reports 248–292 s and the second 109–125 s, alternating with
position in the batch. The sequential reference has no such alternation (271–327 s across
all twelve directions).

## 4. `RollAsyncThreads` is a memory knob

The CPLEX barrier reserves working space **per thread**. Measured from OS counters (private
bytes and system commit, sampled every 3 s):

| threads per session | memory per session |
|---:|---:|
| 12 | ~74 GB |
| 5 | ~42 GB |

What fits is:

```
base (~37 GB)  +  RollAsyncK x memory_per_session   <=   commit limit
```

On this machine the commit limit is **182.55 GB** (63.45 GB RAM + 119.10 GB page file).
That rule was fitted on two configurations and then used to predict a third:

| configuration | required | predicted | observed |
|---|---:|---|---|
| K=2 × 12 threads | 37 + 2×74 = 185 GB | the 2nd session cannot start | 1 of 2 fails |
| K=4 × 5 threads | 37 + 4×42 = 205 GB | three start, the fourth cannot | 3 of 4 succeed |
| **K=3 × 5 threads** | **37 + 3×42 = 163 GB** | **all three run** | **3 of 3, no rescues** |

It is always the **last session launched** that fails — the one that finds least memory
free. Not a positional bug; just the order in which the resource is handed out.

### Why the working set looked fine

Working set stays around 29 GB with 22–27 GB of RAM free while this happens, and the page
file peaks at 96 MB — so neither Task Manager's default view nor free-RAM readings show
anything. The pressure is on **private commit**, which reaches 110 GB at K=2 and 162 GB at
K=4. That is also why a flat RSS during the 2026-08-21/22 stalls is not evidence against a
memory limit: under commit pressure a flat RSS is what you would expect, because the process
cannot grow.

### `GMP::SolverSession::GetMemoryUsed` is not usable here

It returned 100 466 MB, 6 154 MB and 7 667 MB for sessions doing equivalent work on the same
matrix, and values larger than total RAM. Use OS counters instead.

## 5. What K=3 × 5 produced

`RunFullFeeder_ProductionK3`, launched 2026-08-25 16:50, stopped deliberately 2026-08-26
after 13 periods to free the machine.

| | |
|---|---|
| Vertices | 159 written (13 complete periods + 3 directions of period 14) |
| Status | **159/159 Optimal** |
| Rescues | **0** |
| `OVviol` | 1.8668e-10 in every vertex — identical to the 2026-08-17 reference |
| `UVviol` | 0 |

Deviation against the 2026-08-17 sequential reference, per period, with the K=2 run of
2026-08-22 alongside for scale (`whole-feeder-production.md` §5):

| period | K=3 × 5 max abs dproj | K=3 × 5 area | K=2 × 12 (22 Aug) area |
|---:|---:|---:|---:|
| 1 | 1.94e-04 | +0.0066 % | +0.0004 % |
| 2 | 7.90e-05 | −0.0014 % | −0.0013 % |
| 3 | 8.20e-05 | +0.0023 % | +0.0019 % |
| 4 | 8.10e-05 | +0.0020 % | −0.0013 % |
| 5 | 2.27e-04 | −0.0006 % | −0.0002 % |
| 6 | 1.34e-04 | −0.0035 % | −0.0024 % |
| 7 | 6.50e-05 | +0.0013 % | — |
| 8 | 1.94e-04 | +0.0001 % | — |
| 9 | 1.72e-04 | +0.0023 % | — |
| 10 | 5.00e-05 | −0.0021 % | — |
| 11 | 5.00e-05 | −0.0007 % | — |
| 12 | 1.80e-04 | −0.0025 % | — |
| 13 | 1.69e-04 | −0.0002 % | — |

**The deviation does not grow as periods chain**, which is the thing worth checking in a
rolling horizon. Period 1 (+0.0066 %) is the only value outside the band previously
observed; the twelve after it sit inside it. This is consistent with §5 of
`whole-feeder-production.md`: a single vertex can move 2.3e-04 while the region it belongs
to moves 0.0006 %, because the deviations largely cancel when the polygon is formed.

Raw output is versioned under `results/parallel_k3_2026-08/`.

### Timing, including a slowdown that is not explained

| periods | sweep | boundary | cycle | mean solve |
|---|---:|---:|---:|---:|
| 2–5 | 40–42 min | 22–28 min | 62–68 min | 529–561 s |
| 6–8 | 54–59 min | 22–28 min | 77–87 min | 689–748 s |
| 9–13 | ~59 min | ~28 min | 80–87 min | ~751 s |

Between periods 6 and 8 the cycle rises from ~64 to ~85 min and then holds. The increments
halve each period (+12.7, +6.8, +3.5, −0.0), so it converges rather than running away, but
**the cause is not established.** What was ruled out: it is not memory accumulation (the
private-bytes floor and ceiling are both flat over eight hours, ceiling pinned at ~150 GB
hour after hour); it is not reported CPU throttling (WMI reports the clock at 100 % of
maximum, though WMI is not reliable for sustained turbo on a laptop); and it is not
intrinsic period difficulty, because the sequential reference is flat there (295, 326, 334,
328, 349, 327, 340 s for periods 1–7).

A cheap test that would separate a process effect from a machine effect: after stopping a
long run, time one period from cold. Back to ~64 min means something accumulates inside the
AIMMS session; already degraded means it is thermal.

### Honest throughput

| | s/vertex, sweep only | full 48-period run |
|---|---:|---:|
| sequential reference | ~334 | 82.17 h |
| K=2 × 12 threads | 349 | — |
| K=3 × 5, periods 1–5 | ~205 | *(does not hold)* |
| K=3 × 5, settled regime | ~295 | **~65–68 h** |

Two cautions on these numbers. The 344 s/vertex figure quoted elsewhere for the sequential
run is `82.17 h / 576` and **includes the period boundaries**, so it is not comparable with
sweep-only measurements; net of ~36 min boundaries it is ~334 s/vertex of sweep. And the
early periods are not representative — a projection from the first five gives ~52 h, which
the slowdown then invalidates.

**The realistic saving is ~14–17 h on a ~82 h run, roughly 18–21 %.** Real, but it does not
fit a whole-feeder run into a weekend: started Friday morning it finishes Monday in the
early hours.

## 6. Checking the split on another machine

The rule travels; the numbers do not. On a new machine:

1. Find the commit limit — `Get-CimInstance Win32_OperatingSystem | Select TotalVirtualMemorySize`
   on Windows, i.e. RAM + page file, not RAM.
2. Run one period and watch **private bytes / commit**, not working set and not free RAM.
   The barrier reservation appears as a single step of tens of GB.
3. Confirm no direction needed a rescue before committing days of wall clock. Until the
   rescue is made visible (see below), the way to tell is to trace it or to notice that one
   direction per batch reports a suspiciously short `time`.

## 7. Open

- **The 2026-08-21 and 2026-08-22 stalls were not reproduced.** Six instrumented runs on
  2026-08-25/26, ~60 copies, none stalled — including a K=3 run that went through period 7
  cleanly, where the 2026-08-22 run had stopped. That the stalls are the occasional bad
  outcome of the same memory limit is a plausible reading, not a measured fact.
- **The rescue hides a real failure.** Recording that a rescue happened — a column, or
  adding the rescue's time to `time` — would have surfaced this in the first parallel run,
  and would make the step-1 check work as intended. Worth doing before the async path is
  used more widely.
- **The period 6–8 slowdown is unexplained**, as described above.
- **The instance size is the larger lever.** 6.21 M rows comes from building the full
  48-slot horizon in every period. The sweep pins slot 1 to the committed dispatch and
  looks for the region of slot 2. If that region could be obtained on a shorter horizon the
  instance would drop an order of magnitude and none of the above would bind. Whether it
  can is a modelling question — slots 3–48 carry the cyclic SOC band and the energy
  constraints — and one for Luis and Tulio, not a tooling change.
