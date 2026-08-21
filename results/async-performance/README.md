# Parallel (async) sweep — performance campaign

**August 2026.** How the per-transformer rolling FOR was made **1.82× faster**, measured
end to end on all nine transformers under one controlled machine base.

Nothing about the physics changed. Same exact quadratic form, same constraints, same
production switches. The only change is *when* each of the 12 sweep directions in a
period is solved: previously one after another, now several at once in separate CPLEX
sessions.

---

## 1. The headline

| | |
|---|---|
| Whole per-transformer campaign | **35.72 h → 19.62 h, 1.82×** (saves 16.1 h) |
| Best case (TR9, 90 batteries) | 2.73× |
| Worst case (TR7, 259 batteries) | 1.31× |
| Solves | **5,184 of 5,184 Optimal** |
| Committed dispatch (SOC files) | **bit-identical on all nine** |
| FOR vertices | reproduce to 3e-6 – 7e-5 p.u. (3–70 W) |

The committed dispatch — the number the papers use — is unchanged, exactly. Only the
FOR boundary vertices move, and by amounts far below the model's own feasibility
tolerance (§6).

These are measurements, not projections. Every run was made one transformer per fresh
AIMMS session on a machine held in a fixed state; see `BASELINE_PROTOCOL.md`.

---

## 2. How it works

Within one period, the 12 sweep directions all share the same feasible region: the
data reset is deterministic, the rolling map is fixed, slot-1 dispatch is frozen, and
`FOR_TieEps = 0` makes each vertex independent of solve history. So the directions can
be solved in any order, or simultaneously.

Each direction gets its own copy of the period's generated matrix and its own CPLEX
session. Two knobs control the split:

- **`RollAsyncK`** — how many directions solve at once (sessions)
- **`RollAsyncThreads`** — threads per session

The machine has 24 physical cores, so `K × threads = 24` is the sensible budget.

Two derived quantities explain every result below:

- **inflation** = async mean solve ÷ sequential mean solve — what concurrency costs
  each individual solve
- **concurrency** = total solver seconds ÷ wall seconds — how many solves were really
  overlapping

**Net speed-up ≈ concurrency ÷ inflation.** Neither number alone predicts anything.

---

## 3. Results — all nine transformers

| | batt | split | sequential | base | speed-up | inflation | concurrency |
|---|---:|---|---:|---:|---:|---:|---:|
| TR4 | 46 | 6×4 | 35.7 | 18.6 | 1.92× | 2.20 | 3.63 |
| TR3 | 49 | 6×4 | 39.1 | 20.1 | 1.95× | 2.33 | 3.95 |
| TR1 | 77 | 6×4 | 96.5 | 50.1 | 1.93× | 2.31 | 3.84 |
| TR9 | 90 | 6×4 | 195.8 | 71.8 | **2.73×** | 1.59 | 3.78 |
| TR2 | 95 | 6×4 | 140.4 | 71.4 | 1.97× | 2.21 | 3.79 |
| TR8 | 124 | 4×6 | 298.9 | 125.1 | 2.39× | 1.18 | 2.42 |
| TR5 | 214 | 4×6 | 516.5 | 204.4 | **2.53×** | 1.11 | 2.39 |
| TR7 | 259 | 4×6 | 411.2 | 314.0 | 1.31× | 1.97 | 2.17 |
| TR6 | 262 | 4×6 | 409.1 | 301.6 | 1.36× | 1.99 | 2.20 |
| | | | **2143.2** | **1177.0** | **1.82×** | | |

Wall clock in minutes. Full data in `timings.csv`.

### The gain is not monotonic in size

It peaks in the middle. TR5 at 214 batteries beats every small transformer except TR9,
then the gain collapses above ~250. **Three regimes, not a trend:**

| band | behaviour |
|---|---|
| below ~120 batteries | ~1.9×; split is **neutral** (§4) |
| 124–214 | **best** — 2.4–2.5×, inflation only 1.11–1.18× |
| above ~250 | **ceiling ~1.35×** — inflation ~2.0× and no split fixes it |

TR7 and TR6 are the same result twice — 259 and 262 batteries, inflation 1.97 and 1.99,
concurrency 2.17 and 2.20, speed-up 1.31× and 1.36×. So the ceiling is structural, not
a bad night. It is not memory exhaustion either: peak AIMMS 14.8 GB with 8.1 GB still
free.

### Why TR9 tops the table

TR9 and TR2 are nearly the same run — 71.8 vs 71.4 min, 28.29 vs 28.14 s per solve,
concurrency 3.78 vs 3.79. The entire difference in speed-up comes from the *sequential*
side, where TR9's solves are intrinsically 40 % heavier (17.76 s vs 12.73 s). Heavier
solves carry the parallel overhead better.

> **Worth remembering when quoting these:** the speed-up column is partly a statement
> about the sequential baseline, not only about the parallel gain.

---

## 4. Choosing the split

Three experiments, all in `split_tests.csv`.

**TR4 tuning** (46 batteries, full runs, 2026-08-14) — sequential 35m20s, 6×2 28m16s,
**6×4 20m13s**, 12×2 24m39s. Above ~6 sessions the box saturates.

**TR6 probe** (262 batteries, 2 periods per split, 24 threads throughout):

| split | wall | mean solve | concurrency |
|---|---:|---:|---:|
| 6×4 | 692 s | 95.4 s | 3.31 |
| **4×6** | **621 s** | 60.3 s | 2.33 |
| 3×8 | 706 s | 53.4 s | 1.82 |
| 2×12 | 746 s | 39.3 s | 1.27 |

Fewer, fatter sessions cut per-solve time sharply (95 s → 39 s), but concurrency lands
at only 0.55–0.63 × K whatever the split. Below four sessions, concurrency falls faster
than per-solve time improves.

**TR3 split test** (49 batteries, full runs) — 6×4 **20.05 min**, 4×6 **20.02 min**.
A dead heat. 4×6 cut the mean solve from 8.24 s to 5.44 s exactly as predicted, and
concurrency fell from 3.95 to 2.61, cancelling it out.

> **The lesson from all three: judge a split by wall clock, never by mean solve time.**
> On TR6, 2×12 had the best mean solve of any split and the worst wall clock. On TR3,
> 4×6 improved the mean by a third and moved the wall by two seconds.

So the crossover is **not** "6×4 is better below ~120 batteries". It is:

- **below ~120** — the split does not matter; 6×4 is kept because there is no reason to change
- **above ~120** — 4×6, and the margin is large
- **above ~250** — 4×6 is still the best available, but nothing recovers the ceiling

### How the probe held up

The TR6 probe predicted 1.73× inflation for 4×6; the full 48-period run gave 1.99×, and
the wall clock came in at 5.03 h against a 4.5 h projection. **Directionally right,
quantitatively soft** — good enough to pick a split, not to promise a wall clock.

---

## 5. The batch wrapper cost 1.48× for nothing

`RunFOR_Rolling_PerTrafo_Async` used to load the whole feeder once up front, purely to
read the list of transformer tags. But `RunFOR_Rolling` empties everything and reloads
as its first action — so that load bought nothing, while permanently growing the AIMMS
heap to full-feeder size.

Measured, period-matched, identical settings:

| | standalone | in the batch | penalty |
|---|---:|---:|---:|
| TR4 | 7.76 s/solve | 11.58 s/solve | 1.49× |
| TR6 | 95.4 s/solve | 141.0 s/solve | 1.48× |

Same penalty at different positions in the batch, so it was a constant, not creeping
fragmentation. Removing the load fixed it: TR4 went 40.8 min → 18.9 min.

This is why the August 17–18 pass is not quoted here. It ran across a batch, across
days and across machine loads, and produced two transformers *slower* than sequential.
The numbers in §3 replace it entirely.

---

## 6. Is it still correct?

Yes, with one caveat.

- **Every solve Optimal** — 5,184 of 5,184 across the nine runs.
- **Committed dispatch bit-identical** — all nine `_soc_` files match their sequential
  twins byte for byte. The dispatch results are unaffected.
- **Async is deterministic run-to-run.** Five transformers were compared against their
  August async runs and came back **0.0e+00** — bit-identical, including TR9 across two
  days and a reboot. The drift below is against the *sequential* solver only.
- **FOR vertices drift slightly, and the drift grows with size:**

| | max abs delta proj | rows over gate (of 576) |
|---|---:|---:|
| TR3, TR4 | 3e-6 p.u. (3 W) | 0 |
| TR1, TR2, TR9 | 7–9e-6 p.u. | 6–10 |
| TR8 | 2.2e-5 p.u. | 0 |
| TR5 | 3.9e-5 p.u. | 0 |
| TR6 | 4.8e-5 p.u. | 0 |
| TR7 | 7e-5 p.u. (70 W) | 1 |

The cause is the thread cap changing the order of arithmetic inside the CPLEX barrier
solver. For scale, 70 W is **14× inside the model's own `Feasibility_Tolerance`** of
1e-3 p.u. = 1 kW, and ~0.005 % of the FOR extent.

> **Caveat.** If a number needs the strict 5e-6 gate, run that case sequentially. The
> `_gmp` (sequential) results remain the set to quote from.

Validate any async run against its sequential twin with:

```
py -3 scripts/compare_FOR_runs.py FOR_rolling_TRn_gmp.csv FOR_rolling_TRn_base.csv --tol 5e-5
```

The invariant is `proj`, not P and Q separately — flat faces of the region make the
argmax a segment, so P and Q can slide legitimately while `proj` holds.

---

## 7. What to run

| goal | procedure |
|---|---|
| One transformer, controlled conditions | `RunTRn_Base` — split already correct for its size |
| All nine in one pass | `RunFOR_Rolling_PerTrafo_Async` — fixed wrapper, size-adaptive split, writes `_asyncB` |
| Re-probe the split after a hardware change | `RunTR6_AsyncTune` — ~1.5 h, four splits, two periods each |

> The older `RunTRn_Async` wrappers are all hard-coded 6×4, so **TR5–TR8 are mis-tuned
> there** — prefer `RunTRn_Base`. `RunTR6_Async38` (3×8) and `RunTR3_Base4x6` are kept
> as records of their experiments; neither split won.

Rules of thumb, on this 24-core / 32 GB machine:

- keep `K × threads = 24`
- **4×6 above ~120 batteries**; below that the split is neutral and 6×4 is the default
- **never at full-feeder scale** (`ReduceNetwork = 0`) — even sequential exhausted 32 GB
- **never linearized for a reportable FOR** — measured on TR3, the relaxation leaves 20 %
  of boundary vertices undeliverable for a 28 % solve saving; see `linearization/`
- when re-tuning, pick the lowest **wall clock**, never the lowest per-solve time
- one transformer per fresh AIMMS session if the timings are to be compared

Memory observed, peak AIMMS / minimum free: TR4 3.4 / 21.5 GB, TR9 7.2 / 17.3 GB,
TR5 11.2 / 11.8 GB, TR7 14.8 / 8.1 GB, TR6 14.4 / 9.1 GB.

---

## 8. Files here

| file | what |
|---|---|
| `async-performance.pdf` | this report as a typeset PDF |
| `README.md` | this report, in markdown |
| `timings.csv` | every transformer: size, all three passes, speed-up, inflation, concurrency, validation |
| `split_tests.csv` | all three split experiments in one table |
| `BASELINE_PROTOCOL.md` | how the controlled base was set up and run |
| `baseline/` | the campaign's environment log and per-run timings |
| `probe/` | raw TR6 probe output, two periods per split |
| `linearization/` | what the linearized formulation costs, measured on TR3: report, workbook, two figures |
| `src/` | LaTeX source of the PDF |

`README.md`, the summary CSVs and the PDF are tracked. Raw `FOR_rolling*.csv` output
matches the repository-wide ignore rule and is shared separately, as everywhere else in
this repository.
