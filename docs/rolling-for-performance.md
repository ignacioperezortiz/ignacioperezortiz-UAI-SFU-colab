# Rolling-horizon FOR — runtime

Two sources of per-direction overhead were removed from the rolling FOR sweep. **Neither touches
the optimization**: no constraint was added or removed, no objective was modified. On the
production TR9 case the run went from **~28 h to 3 h 40 min** and every recorded number is
unchanged.

Both were found by profiling the existing sweep. Both are safe only because of how the sweep was
already built — the 12 directions genuinely share one feasible region, and the un-rotated inputs are
already frozen once per run. What changed is the placement of work that was reasonable when the
sweep was written and no longer pays off in the configuration now used in production (a continuous
QCP solved by barrier). **Reviewed and agreed before pushing.** The A/B evidence for "nothing moved"
is in §3.

**Scope:** the per-transformer path `RunTRk` → `RunTrafoFOR(tag)` → `RunFOR_Rolling` in
`MainProject/OPF.ams` (section `RollingHorizonFOR`), which writes `FOR_rolling_<tag>.csv` and
`FOR_rolling_soc_<tag>.csv`.

---

## 1. What the sweep used to do per period

Per half-hour period, `RunFOR_Rolling`:

1. solves the committed self-consumption baseline once (`MinImports`), which produces the executed
   slot-1 dispatch and advances the realised SOC; then
2. sweeps `FOR_nAngles = 12` directions for the service slot.

The 48 periods are sequential (the rolling horizon carries SOC forward), but the 12 directions
inside a period are **independent and share an identical feasible region**: same reset, same
rotated inputs, same initial SOC, and the committed slot-1 dispatch fixed to the same values via
`BattP_Chg/Dis(bat,'1').nonvar := 1`. Only the sweep objective changes with the angle.

Each direction ran the full sequence:

```
empty allvariables
run Load_data_dsn        ! re-reads the Access tables + OpData.xls (ReadExcelFile)
<re-rotate inputs onto the window, re-fix the committed slot-1 dispatch>
run MainExecution        ! a full solve of MinImportsMaxReverseP
solve FOR_VertexCont
```

That is **25 solves and 13 full data loads per period**.

### 1.1 The per-direction warm-start solve

`run MainExecution` solves `MinImportsMaxReverseP`. That program and `FOR_VertexCont` both declare
`Constraints: NotTobeExcluded_constraints` and `Variables: NotTobeExcluded_variables`, so they
generate a **row-for-row identical matrix** and differ only in the objective column. Its objective
value and status go to `ConvFlag`/`ConvTime`, neither of which the sweep reads or writes to CSV —
only its variable levels survived, as a starting point for the vertex solve.

Its purpose was to seed the vertex solve with a starting point. Two things prevent it from doing so
in the production configuration:

- **`OFminImportsmaxReverseP` does not depend on the sweep angle.** Combined with the shared
  feasible region, the 12 `MainExecution` solves of one period are *the same optimization problem
  solved 12 times*, returning the same answer, discarded each time.
- **The starting point they leave cannot be used.** In production configuration (`UseBattComp=0`,
  `FOR_PolyS=0`, `FOR_LinearizeVmax=0`) the program is a continuous convex QCP, which CPLEX solves
  with barrier. AIMMS passes variable levels to CPLEX as a start only on the MIP path; barrier
  takes an advanced basis instead, and the first solve — being barrier itself — produces no basis
  to hand over.

Measured, the starting point it left also slowed the vertex solve down: the cost-min optimum is an
extreme point of the feasible set, hugging the boundary and poorly centred, which is the opposite of
what an interior-point method wants. Removing it makes the remaining vertex solves **2.0–3.6×
faster** (§3).

### 1.2 The repeated data load

`Load_data_dsn` mixed **static reads** — the Access tables and `OpData.xls`, identical across all
directions and all periods — with per-solve resets that are genuinely needed (the `Qinv` fix, the
fixed transformer taps, the flat-start voltage seed). Running the whole thing per direction meant
1 + 12 = **13 full DB+Excel reloads per period, 624 per 48-period run**, even though the
un-rotated inputs are frozen once at the top of `RunFOR_Rolling` into `P0raw / Q0raw / GenP0raw /
Irrraw` — and the reload's output was overwritten two statements later by the rotation.

---

## 2. What changed

### 2.1 `Load_data_dsn` split into a static half and a per-solve reset

```
Load_data_static   Access tables + OpData.xls + kW->p.u. + VmultLV + tap coefficients mlin/nlin
Load_data_reset    Qinv fix + fixed taps + flat-start Vre/Vim + the Vre0/Vim0 linearization point
Load_data_dsn      run Load_data_static; run Load_data_reset; [ApplyNetworkReduction]
```

`Load_data_dsn` remains a wrapper **in the original statement order**, so all 33 existing callers
behave exactly as before. Inside `RunFOR_Rolling` only, the four in-loop loads call
`Load_data_reset`, which removes 623 of the 624 full reloads.

This is safe by construction: **every write target of `Load_data_static` is a Set, Parameter,
ElementParameter or StringParameter — none is a Variable**, so hoisting it out of the loop cannot
leave variable state unrestored. Of everything the loader touched, only `Qinv`, `Vre` and `Vim` are
Variables (i.e. wiped by `empty allvariables`), and all three are in `Load_data_reset`.
`Load_data_reset` also writes nothing indexed by `d`, so it is safe to call on the reduced network.

### 2.2 `FOR_SweepWarmStart` — the per-direction solve is off by default

New parameter, **`Default: 0`** (production). `1` reproduces the legacy behaviour. The three guards
in `RunFOR_Rolling` read:

```
if FOR_SweepWarmStart = 1 or UseBattComp = 1 then
    run MainExecution;
endif;
```

The `or UseBattComp = 1` matters: with the complementarity binary the program is a MIQCP, where
variable levels **are** a genuine CPLEX start channel. The MIQCP cross-checks
(`RunMicro_BattComp`, `RunFullTR9_BattComp`) therefore keep `MainExecution` automatically. That
path is unmeasured, and leaving it unchanged is the conservative choice.

`RunReducedTest_RollingMicro_LegacyWarm` re-runs the micro test bed with the legacy behaviour, for
re-checking the A/B after any change to the sweep or a solver upgrade.

### 2.3 Unchanged

The committed self-consumption baseline (`MinImports`, one solve per period over the whole rotated
window) is untouched, and so is everything downstream of it: the executed slot-1 dispatch, the SOC
carry-forward, and `FOR_rolling_soc_<tag>.csv`. The 19 other `run MainExecution` call sites in the
model are untouched. Per period the sweep now runs **13 solves and 1 data load** instead of 25 and
13.

---

## 3. Results

### 3.1 Micro test bed — `RunReducedTest_RollingMicro` (TR9_two, 12 batteries)

48 periods × 12 directions = 576 rows.

| | legacy | default | |
|---|---|---|---|
| Wall-clock | 41 min 22 s | **10 min 12 s** | **4.06×** |
| Vertex solve time | 731.0 s | 358.7 s | −50.9 % |
| Per solve | 1.27 s | **0.62 s** | 2.05× |
| Solve status | 576/576 Optimal | 576/576 Optimal | |
| `max \|delta proj\|` | — | **0.000e+00** | |

Also compared against a pre-refactor run of the same test bed: identical. All three runs agree.

### 3.2 Production case — `RunTR9` (90 prosumers)

Against the committed reference run of the same study case (`v1_baseline`).

| | reference | current | |
|---|---|---|---|
| **Wall-clock** | ~28 h | **3 h 40 min** | **~7.6×** |
| **Vertex solve time** | **30,213.4 s** (8.39 h) | **8,440.7 s** (2.34 h) | **−72.1 %** |
| Per solve | 52.45 s | **14.65 s** | 3.58× |
| Solve status | 576/576 Optimal | **576/576 Optimal** | |
| `max \|delta proj\|` | — | **0.000e+00** | |
| P,Q movement | — | **0.00 kW** | |

**Every recorded column is identical** — `now`, `target`, `angle_deg`, `P`, `Q`, `proj`, `status`,
`VminTrue`, `VmaxTrue`, `UVviol`, `OVviol`, `LinErr`. Only `time` differs, which is a wall-clock
measurement. **`FOR_rolling_soc_TR9.csv` is byte-identical** across all 4,320 rows.

The six validation metrics of `CONTRIBUTING.md` §7, rebuilt with `scripts/build_workbook.py`:

```
PV generated 2241.2 kWh/day   demand 643.1   exported 1550.5   imported 13.6
SCR 30.8 %                    SSR 97.9 %     |net|<50W 57.5 %
```

All match the reference exactly.

> **On the ~7.6×:** the reference wall-clock is soft — it comes from a run timed only as "roughly
> 35 min per period". The firm figure, measured on both sides with the same instrument, is the
> **−72.1 % in vertex solve time**.

Working back from 2,100 s/period (reference) to 275 s/period (current), of the ~1,825 s/period
removed roughly 454 s were the vertex solves running slowly from the bad starting point and
~1,371 s were the 12 `MainExecution` solves and their math-program generations — about **114 s
each, ~2.2× the cost of the vertex solve they were meant to help**.

### 3.3 Where the remaining time goes

The earlier profiling note in this file estimated about a third of the wall-clock inside the solver
and two thirds in scaffolding. That was measured by summing the CSV `time` column, which is
`FOR_VertexCont.SolutionTime` only — it excluded the 12 `MainExecution` solves per period and
reclassified them as scaffolding. **The solver was ~62 %, not a third.**

Data loading was never the bottleneck. Profiled directly, one full `Load_data_dsn` costs **0.619 s**
(`Load_data_static` ~0.12 s, `Load_data_reset` ~0.42 s), so the split saves
`623 × (0.619 − 0.424) ≈ 121 s` per run — around 5 % of the micro run and ~0.1 % of TR9. It is kept
because it removes real redundant work and makes the 12 in-loop calls cheap, but the win came from
§2.2.

What remains per period is the 13 solves plus the generation of their math programs. Model
generation, not I/O, is now the largest non-solver cost.

---

## 4. Verifying a change to the sweep

Use **`scripts/compare_FOR_runs.py`**, which aligns two `FOR_rolling*.csv` files on
`(now, angle_deg)`:

```
py -3 scripts/compare_FOR_runs.py OLD.csv NEW.csv
```

The acceptance criterion is **`proj`, not P/Q equality**. The sweep maximises a linear objective
over a convex feasible set, so the optimal *value* `proj = cos(theta)·P + sin(theta)·Q` is unique,
but the argmax need not be: where the FOR boundary has a flat face perpendicular to the sweep
direction the optimum is a segment, and a different starting point or tolerance may legitimately
return a different point on that same face. The script fails only on `proj` outside tolerance
(default 2e-6) or on a changed solve status, and reports P/Q movement as informational.

Measured on the committed TR9 boundary, 15 % of directions have a near-flat face at the run's own
`Feasibility_Tolerance` of 1e-3, the widest spanning 0.18 MW of Q — so the allowance is real, even
though in this change nothing moved.

Time the **run**, not the CSV `time` column: that column covers `FOR_VertexCont.SolutionTime` only
and sees neither the removed solve nor the scaffolding.

---

## 5. Runtime of the fairness runs

Added later, on top of the accelerated sweep. **This section is about cost, not correctness:** the
fairness constraints (`FairMode = 1` / `2`, section `BatteryModel` → `Fairness`) *do* change the
results, by design — see `results/TR9_fairness.md`. Nothing in sections 1–4 is affected; case A
below is the same run measured in §3.2, re-used unchanged.

TR9, study case `v1_baseline`, 48 periods × 12 directions = 576 vertices each.

| Run | Wall-clock | Vertex solve time | solver / wall | median | max | Status |
|---|---|---|---|---|---|---|
| **A** — `FairMode=0` (reference) | 3 h 40 min | 8,440.7 s | 64 % | 14.50 s | 22.42 s | 576/576 Optimal |
| **L1** — `FairMode=1`, per prosumer | 3 h 49 min 12 s | 8,440.5 s (**+0.0 %**) | 61.4 % | 14.49 s | 23.59 s | 576/576 Optimal |
| **L2** — `FairMode=2`, per aggregator | 4 h 47 min 57 s | 10,118.6 s (**+19.9 %**) | 58.6 % | 15.59 s | 46.13 s | 576/576 Optimal |

Rebuild the table with `scripts/run_timing.py` (sum of the CSV `time` column, plus wall-clock from
the file mtime and `--inicio`). The same caveat as §4 applies: that column is
`FOR_VertexCont.SolutionTime` only.

**Level 1 is free; level 2 costs 20 % — although level 2 constrains less.** Level 1 adds 90 equality
rows and collapses the fleet to **one effective degree of freedom** (`x_i = zeta * s_i`), which
makes the barrier's job easier: the vertex solve time is unchanged to the first decimal and the
worst vertex moves by 1.2 s. Level 2 adds only **3** equality rows and leaves all 90 columns free
inside them, so the feasible set stays 90-dimensional but heavily coupled — a large degenerate set,
which is the expensive case for an interior-point method. Its worst vertex nearly doubles, 22.4 s
to 46.1 s.

Case A was not re-run under the fairness build. With `FairMode = 0` both constraints have an empty
`IndexDomain` and generate zero rows, verified on the micro bed with `max |delta proj| = 0` and a
byte-identical SOC CSV — the same acceptance criterion used in §3.

The `FairMode = 0` production path therefore carries no measurable cost from this addition, and the
figures in §3.2 remain the reference for it.
