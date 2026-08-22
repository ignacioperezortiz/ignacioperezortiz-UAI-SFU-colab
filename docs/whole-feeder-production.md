# Running the whole feeder: the two accelerations together

**2026-08-22.** The whole-feeder rolling FOR now runs in about **61 h** instead of the
**82.17 h** it took on 2026-08-17, with results that do not move. This records what changed,
who it came from, and every test that was run to get there — including the one that failed for
nine hours.

---

## 1. The two accelerations, and whose they are

Both existed before this work. Neither had been run on the full feeder, and **the code could
not express them together**.

| | origin | what it does |
|---|---|---|
| **Network-free committed baseline** | asked for by **Prof. Luis**, implemented and validated by **Tulio** (`BaseNoNetwork`, PR #16) | the committed self-consumption solve drops the `NetworkModel` section. Validated on TR4: 48 baseline solves fell from ~6 min to 13 s, max abs dP = 2.7e-7 p.u. |
| **Parallel sweep** | **Tulio** (`RollAsyncK` / `RollAsyncThreads`, PR #16) | a period's 12 sweep directions solve `RollAsyncK` at a time, each on its own copy of the period instance. Measured across nine reduced transformers: 35.7 h to 19.6 h |

**Why they could not be combined.** `BaseNoNetwork = 1` forces `RollGMPBaseline = 0`, because
the shared instance carries the network rows and so cannot serve a network-free baseline. With
`RollGMPBaseline = 0` the sweep matrix is generated in the sweep block instead, and the async
path then copies an instance that has **never been solved**. On the reduced transformers that is
harmless. On the full feeder it hangs.

---

## 2. What was added here

### `BaseNoNetGMP` — the two together

`Default: 0`, inert unless set. With `RollUseGMP = 1` and `RollGMPBaseline = 1` it deactivates
the `NetworkModel` rows around the committed baseline solve **on the shared instance**, instead
of forcing a second generation path. Same network-free baseline; the instance is generated once
and **solved** before the async sweep copies it.

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
  every network column in no active row at all, so presolve drops them and no freezing is needed.
  Each binding domain mirrors its row's own `IndexDomain` condition.

### `tGMP` — a second index on `Time`

The baseline block sits inside `for (t) do`, so `t` is not free for a `GMP::*Multi` binding
domain. `tGMP` is a second index on the same set, purely additive: it appears in no definition.

### `Ire_Trafo` / `Iim_Trafo` index domains

```
- IndexDomain: (tr,f,n,t);
+ IndexDomain: (tr,f,n,t) | n = StartBusTr(tr) or n = EndBusTr(tr);
```

A transformer touches exactly two buses, and all 40 references in the model use `StartBusTr(tr)`
or `EndBusTr(tr)` as the third index. Without the condition the identifier is declared over
`tr x f x ALL BUSES x t`.

**Proven equivalent, not argued:** on the TR9 preflight, rows 565009, columns 456685, nonzeros
1956026 and 63.36 Mb are identical with and without, down to the objective row number, and
max abs dproj = 0.000e+00 over 36/36 vertices.

**The speed gain is NOT established.** On the full-feeder one-slot preflight the boundary fell
from 1976 s to 1696 s (-14.2 %), but the solve — identical work on an identical matrix, which
this change cannot affect — fell 13.4 % in the same pair. The two ratios coincide, so the
difference is environment drift, not generation. Settling it needs an A-B-A pair on an idle
machine, the way `RunTR4_Timing_ABA` does. The change is kept because it is exactly equivalent
and makes the declaration honest, not because it was shown to be faster.

### `RunFullFeeder_Production`

The standard whole-feeder entry point. `RunFullFeeder_NoFairness` is kept as the reference that
produced `results/full_feeder_2026-08/`.

---

## 3. What it measures

Against the 82.17 h sequential reference of 2026-08-17 (576/576 `Optimal`), period 1 of the
2026-08-22 run:

| | reference | production | gain |
|---|---:|---:|---|
| solve, mean | 295.2 s | **189.4 s** | 1.56x |
| period boundary | 36 min | **24 min** | -12 min |
| period, wall clock | 102.7 min | **76 min** | -26 min |
| whole run | 82.17 h | **~61 h** | **-21 h (26 %)** |

Roughly **9.6 h** of the saving is the network-free baseline and **11 h** the parallel sweep.

**Results.** 11 of 12 directions bit-identical on `proj`; the twelfth at 4.3e-05 on proj ~3.9,
i.e. 1.1e-05 relative. 12/12 `Optimal`. `VmaxTrue` identical in all twelve and `OVviol` at
1.867e-10 throughout — no new violation.

`proj` is the invariant, not `P`/`Q`: the sweep maximises a linear functional over a convex set,
so a flat face admits many argmaxes. The model's own `Barrier_Convergence_Tolerance` is 1e-2,
some 200x looser than the largest deviation seen.

---

## 4. Every test that was run

| # | what | result |
|---|---|---|
| — | `RunFullFeeder_AsyncNoNet` — full feeder, `BaseNoNetwork=1` plus async | **FAILED.** 9 h 06, one thread at 100 %, memory frozen at 17.08 GB, **zero vertices**. Not memory: 26.5 GB free and RSS not growing |
| 1 | `RunTR3_Base` — Tulio's exact reduced-scale config | OK. 9.78 cores, 306/306 `Optimal`, 8.93 s/solve. The parallel path works on this machine |
| 2 | `RunTR3_BaseNoNet` — same plus `BaseNoNetwork=1` | OK. 7.84 cores, 48/48 `Optimal`, 8.15 s/solve. **The configuration is innocent** — the hang is scale, not settings |
| 3 | `RunFullFeeder_Async` — full feeder, shared instance plus async | OK. 12/12 `Optimal`, 194.1 s/solve, `proj` bit-identical in 10 of 12. **Copying a solved instance returns.** The hang was the never-solved instance |
| 4 | `#2` — `Ire_Trafo`/`Iim_Trafo` index domains, TR9 preflight A/B | OK. Matrix identical to the last digit, max abs dproj = 0.000e+00 on 36/36. Speed inconclusive |
| 5 | `RunTR3_Base3b` — `BaseNoNetGMP=1` at TR3 | OK. 576/576 `Optimal`, max abs dproj = 0.000e+00 vs `BaseNoNetwork`, **committed dispatch identical column by column**: `SOC_start`, `Pexec`, `Chg1`, `Dis1` all 0.000e+00 |
| 6 | `RunFullFeeder_Production` — full feeder, both | OK. Period 1 validated above; run in progress |

**Two runtime errors were found by the TR3 bench in seconds each**, both from binding domains:
`t` already bound by the surrounding `for (t)`, and `BattInvPn` not in the model when
`FOR_ScaleInv = 0`. The second is why there is no `FreezeMulti` in the final design.

### What the nine-hour failure cost, and why

The combination had **never been run at any scale** before it was launched against a multi-day
whole-feeder job. The test that would have caught it — `RunTR3_BaseNoNet`, test 2 above — takes
**83 seconds**. Run the reduced bench before committing the machine.

---

## 5. How to run it

```
RunFullFeeder_Production
```

Headless, and watch it from outside:

```
AimmsCmd.exe --run-only RunFullFeeder_Production <repo>\OPF.aimms
```

`FOR_rolling_progress_full_prod.txt` is rewritten after every vertex. The CSVs are flushed per
vertex, so an interruption keeps everything already finished — but **there is no resume**:
`RunFOR_Rolling` restarts at period 1.

Check it against the reference on `proj`, never on `P`/`Q`:

```
py -3 scripts/compare_FOR_runs.py \
    results/full_feeder_2026-08/FOR_rolling_full_m0_20260817.csv \
    FOR_rolling_full_prod.csv
```

### Do not set `BaseNoNetwork = 1` here

It buys the same baseline and forces the generation path that hung. `BaseNoNetGMP` exists so the
two accelerations can be had together.

---

## 6. Open

- **`AimmsCmd` returns exit code 0 on a failed procedure.** The real signal is
  `Error: Procedure run failed` on stdout. Every run here was checked that way.
- **`scripts/watch_runs.ps1` writes to a fixed path** under
  `results/async-performance/baseline/`, which PR #15 versioned. Running it overwrites Tulio's
  committed campaign log.
- **`#2`'s speed is unproven.** A-B-A on an idle machine would settle it.
- **The instance copy costs about 2 min per copy**, six batches per period — roughly half of
  what the parallel sweep wins back. Worth attacking next.
- **The 2026-08-22 run was launched from a scratch copy of the project** under the working name
  `RunFullFeeder_3b`, with a body identical to `RunFullFeeder_Production` except for the file
  suffix, and **without** the `Ire_Trafo` index-domain change of `#2`. Since that change is
  exactly equivalent, re-running from this repo reproduces the same answers; the wall clock is
  the one number that could differ.
