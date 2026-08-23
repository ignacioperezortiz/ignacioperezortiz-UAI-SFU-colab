# Running the whole feeder with the parallel sweep

> **SUPERSEDED, 2026-08-23.** The two-step procedure below is Tulio's original write-up and is
> kept as the record of what the parallel sweep was designed to do and what it measured on the
> nine reduced transformers, which still stands. **Do not follow it on the whole feeder.**
> `GMP::Instance::Copy` hangs there — period 1 on 2026-08-21 and period 7 on 2026-08-22, one
> thread at 100 %, no vertex, no error. The whole-feeder entry point is now
> `RunFullFeeder_Production` with the sweep sequential. See `docs/whole-feeder-production.md`.


The whole-feeder FOR — every transformer at once, on the full network, so the grid
interaction between them is in the answer — took **82.17 h** sequentially on 2026-08-17.

This is how to try the same run with the 12 sweep directions solved in parallel, and how
to find out in about three hours whether it is worth days of wall clock on your machine.

Nothing here changes the model. Same exact QCP, same constraints, same settings as
`RunFullFeeder_NoFairness`. The only difference is that `RollAsyncK` directions solve at
the same time instead of one after another.

---

## Read this before you start

**The honest expectation is modest, and it might be zero.**

Measured on the reduced per-transformer networks, the gain shrinks as the instance grows:

| transformer | batteries | speed-up |
|---|---:|---:|
| TR9 | 90 | 2.73× |
| TR5 | 214 | 2.53× |
| TR7 | 259 | 1.31× |
| TR6 | 262 | 1.36× |

**The whole feeder is 1,216 batteries** — nearly five times TR6. That is well past anything
measured, and the trend points down, not up. If 1.3× still holds, 82 h becomes about 63 h.
That is worth having. It is not transformative, and it is not guaranteed.

**Memory is the real question.** Every concurrent direction holds its own copy of the
period matrix:

| | batteries | sessions | peak AIMMS memory |
|---|---:|---:|---:|
| TR9 | 90 | 6 | 7.2 GB |
| TR5 | 214 | 4 | 11.2 GB |
| TR7 | 259 | 4 | 14.8 GB |
| **whole feeder** | **1216** | **1 (sequential)** | **18.8 GB** |

That last row is why `RollAsyncK` is set to **2** and not 4 or 6. On a 32 GB machine the
sequential whole-feeder run already exhausted memory in August 2026 — every vertex came
back `NoSolution`, with no error message to explain it. Two concurrent copies of a
whole-feeder matrix is a real risk, not a theoretical one.

So: **step 1 measures memory, step 2 does the run.** Do not skip step 1.

---

## Step 1 — the memory check (~3 h)

```
RunFullFeeder_AsyncSmoke
```

This is the full run capped to the first 2 periods. **The cap does not make the problem
smaller** — each period still builds the complete 48-slot instance, so peak memory here is
peak memory for the whole run. Only the number of periods is reduced.

Watch memory while it runs. On Windows, Task Manager is enough; `scripts/watch_runs.ps1`
logs it every 30 s if you prefer a record.

When it finishes, check three things in order:

**1. Did every vertex solve?**

```
FOR_rolling_full_asyncsmoke.csv   ->   24 rows, all "Optimal"
```

Any `NoSolution` at this scale means memory, not mathematics. Stop — `K=2` does not fit.

**2. How close did free memory get to zero?**

If it dipped near zero, stop even if the solves succeeded. The full run is 24× longer and
the margin will not hold.

**3. How long did each solve take?**

Compare the `time` column against **344 s/vertex**, the sequential rate from the
2026-08-17 run. **Expect it to be higher** — running two at once makes each one slower.
That is normal and not a failure.

The question is whether two at a time beats one at a time overall:

| per-solve time in the smoke run | what it means |
|---|---|
| under ~520 s | worth it — 2 sessions are outrunning the per-solve cost |
| 520–690 s | marginal; the gain is small and may not survive the full day |
| over ~690 s | no gain left. Run `RunFullFeeder_NoFairness` instead |

*(688 s is 2 × 344: at that point two concurrent solves take exactly as long as two
sequential ones, and the parallelism has bought nothing.)*

---

## Step 2 — the full run

Only if step 1 passed all three checks:

```
RunFullFeeder_Async
```

48 periods × 12 directions, full network. Writes `FOR_rolling_full_async.csv` with its
`_soc_` and `_fair_` companions.

**You can watch it from outside the process.** `FOR_rolling_progress_full_async.txt` is
rewritten after every vertex and says which period and direction it is on, how long the
last solve took, and the configuration:

```
periodo    12 de  48   ->  objetivo  13   direccion   7 de  12   ( 180.0 grados)
ultimo vertice :       402.55 s   estado Optimal
config         : FairMode  0   RollUseGMP  1   ReduceNetwork  0   RollAsyncK  2 x 12 threads
```

The CSVs are written as the run goes, so if it is interrupted you keep every vertex it had
already finished.

> Both of those come from the flush and progress work in PR #12. They had to be carried
> into the parallel branch by hand — a plain merge left them in the sequential path only,
> where they would have worked in sequential runs and done nothing at all in parallel ones.

---

## If it does not work out

Then the sequential `RunFullFeeder_NoFairness` remains the way to get this result, and
82 h is what it costs. Nothing is lost by having asked — step 1 costs three hours.

There is also a different route to a whole-feeder region: run each transformer separately
and combine them with `scripts/combine_FOR_pertrafo.py`. That takes about **20 h** with the
parallel sweep, but it is a Minkowski sum of nine separately-solved regions, so the MV
coupling between transformers is not in the answer. The gap was measured in June at
0.2–4 % on transformer pairs. It is a different quantity, not a cheaper version of this
one — use it when that approximation is acceptable, not when the full grid interaction is
the point.

---

## Settings reference

| | |
|---|---|
| `RollAsyncK` | how many directions solve at once. **2** for the whole feeder |
| `RollAsyncThreads` | threads per session. 2 × 12 = 24, the physical core count here |
| `RollMaxPeriods` | stop after N periods. Used by the smoke test; 0 = full day |
| `RollFlushCSV` | write results as they are produced. On by default |

`RollAsyncK = 0` is the sequential path, unchanged. Every procedure resets these on the way
out, so a run cannot leave the session in a strange state.

On different hardware the split is worth re-checking: `RunTR6_AsyncTune` tries four
session/thread combinations on one transformer in about 1.5 h. Judge it by **wall clock**,
not by time per solve — on TR6 the split with the best per-solve time had the worst wall
clock.
