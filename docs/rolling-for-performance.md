# Rolling-horizon FOR — runtime notes and options to reduce wall-clock time

Based on a profiling audit of the production rolling-FOR run, this note summarizes where
the wall-clock time goes and lists a few avenues that could reduce it **without changing
the optimization itself** — same feasible region, same objective, same results. These are
options to consider, not decisions; none has been implemented.

**Scope:** the production per-transformer path
`RunTRk` → `RunTrafoFOR(tag)` → `RunFOR_Rolling` in `MainProject/OPF.ams`
(section `RollingHorizonFOR`), which writes `FOR_rolling_<tag>.csv` and
`FOR_rolling_soc_<tag>.csv`.

---

## 1. Where the wall-clock time goes

A representative TR9 run took roughly **35 min per period** over the 48 periods, of which
about a third was spent inside the solver and about two thirds in per-period scaffolding
(model generation, data reloading, I/O). The rate was flat from the first period to the
last (early ≈ late), so the time sits in **structural overhead per solve**, not in a model
that gets harder over the day or in CPU contention.

That profile follows directly from the structure of `RunFOR_Rolling`. Per period it:

1. solves the committed self-consumption baseline once (`MinOFminImports`);
2. sweeps `FOR_nAngles = 12` directions for the service slot; and
3. advances the realised SOC to the next period.

The 48 periods are **sequential** (the rolling horizon carries SOC forward), while the 12
directions inside a period are **independent**: they share exactly the same feasible region
(network, battery and SOC constraints, plus the committed slot-1 dispatch fixed via
`BattP_Chg/Dis(bat,'1').nonvar := 1`); only the sweep objective (`FOR_Angle`) changes.

Inside the direction loop, each angle runs the full sequence:

```
empty allvariables
run Load_data_dsn        ! re-reads the Access DB tables + OpData.xls (ReadExcelFile)
<re-rotate inputs onto the window, re-fix the committed slot-1 dispatch>
run MainExecution
solve FOR_VertexCont
```

The dominant piece of overhead is that **`Load_data_dsn` runs on every direction**. It reads
the DB tables (buses, lines, transformers, loads/PV, batteries) **and** `OpData.xls` via
`ReadExcelFile`, then re-derives per-unit values, tap-linearization coefficients and the
warm-start voltage seed. That is ≈ 1 (baseline) + 12 (directions) = **13 full DB+Excel
reloads per period**, ≈ **624 over a 48-period run** — even though the underlying static
data never changes (the un-rotated inputs are already frozen once at the top of
`RunFOR_Rolling` into `P0raw / Q0raw / GenP0raw / Irrraw`).

---

## 2. Options, ranked by benefit / effort — all preserve the model's results

### (A) Reuse the generated model across the 12 directions

Within a period the 12 solves share an identical constraint system; only the objective
coefficients change with the sweep angle. Generating and loading the data **once per
period** and then re-solving with only the objective changed would avoid rebuilding the
math program 12 times for one feasible region. Optionally, each angle could warm-start from
the previous one (directions are 30° apart, so their optima are close). Same feasible
region, same vertices — purely computational.

A practical note: part of `Load_data_dsn` is a genuine per-solve reset (Qinv fix, voltage
warm-start seed, tap coefficients), so a refactor here would keep those resets and drop only
the redundant reads.

### (E) Hoist the static data read out of the loop — highest leverage

This is the concrete form of (A)'s largest cost. `Load_data_dsn` mixes **static reads**
(DB tables + `OpData.xls`, identical across all directions and all periods) with the
per-solve resets that are genuinely needed. Splitting it into a one-time static load plus a
light per-solve reset would remove the ~624 redundant reloads without touching the
optimization. This is the lowest-effort, highest-return option.

### (C) Solver threads and algorithm

No explicit `option Threads` is set in `OPF.ams`; the QCP solves use
`method := 'deterministic concurrent'`. It is worth confirming, from the solver log, how
many threads are actually used, and whether pinning `Threads` to the core count (or a barrier
method) helps. The gain is bounded (the solver is only about a third of the time) but nearly
free, and the results are unchanged.

### (D) Parallelize the 12 directions

The directions are independent, so in principle they can run on separate cores or processes;
the periods cannot (sequential SOC). AIMMS runs the `for` loop in a single process, so this
would need multiple AIMMS instances or a redesign. There is also an easier parallel axis
already available: the per-transformer runs (`RunTR1`…`RunTR9`) are independent and could be
launched concurrently, which captures much of the benefit with far less rework. The
mathematics is unchanged throughout.

### Already efficient

CSV output is already **append-style**, not a per-period rewrite: `FOR_RollCSV` and
`FOR_RollSOCCSV` are opened once, written line-by-line with `put`, and `putclose`d at the end
of the run. No change needed here.

---

## 3. A suggested order

1. **(E) + (A)** together: hoist the static DB/Excel read out of the per-direction loop and
   reuse the generated model across the 12 angles, keeping the necessary per-solve resets.
   Biggest benefit, results unchanged.
2. **(C)**: check and, if useful, tune solver threading — quick and independent.
3. **(D)**: consider running the per-transformer jobs concurrently before attempting
   intra-period parallelism.

## 4. Notes

- Every option above preserves the model's results (same feasible region and objective); they
  target only how the run is scaffolded and solved, not the formulation.
- The model formulation is the owner's domain; any change would go through the normal review.
- Re-running the standard TR9 validation after a change is a simple safety net to confirm the
  numbers are untouched.
