# GMP validation across all nine transformers

Independent replication of the two performance phases documented in
`docs/rolling-for-performance.md`, extended from TR9 to the whole network.

**Result 1 — the performance work changed nothing.** Nine transformers, 5,184 FOR
vertices, 58,368 committed-dispatch rows. Every dispatch row is bit-identical. The worst
FOR boundary movement anywhere is 8e-6 p.u. = **8 W** at Sb = 1 MW.

**Result 2 — on AIMMS 26.3.2.1 the GMP path is 3.5× faster**, and the earlier
reference-vs-GMP timing comparison was invalid. See §4.

Environment: AIMMS **26.3.2.1** (not the 26.2.3.3 the README pins), CPLEX 22.1, Windows 11.
Runs 10–13 August 2026. Exact formulation throughout: `FOR_PolyS = 0`,
`FOR_LinearizeVmax = 0`, `UseBattComp = 0`.

---

## 1. Method

Every transformer was run with `RunTR<n>_GMP` and compared against its pre-update
production run at three levels:

| Level | Artifact | What it proves |
|---|---|---|
| FOR boundary | `FOR_rolling_TR<n>.csv` | the 576 sweep vertices land in the same place |
| Committed dispatch | `FOR_rolling_soc_TR<n>.csv` | the operating point every sweep departs from is unchanged |
| Published analysis | the per-transformer analysis workbooks | the numbers already written up are unaffected |

Acceptance is on **`proj`, not (P,Q)**, per `scripts/compare_FOR_runs.py` — flat faces let
the argmax slide along an edge without the region changing.

The reference runs pre-date both phases. A second independent archive of the same period
corroborates them: six of nine byte-identical, the other three numerically identical at
exactly `0.000e+00`, differing only in the `time` column.

## 2. Correctness

| TR | Batteries | max \|Δproj\| | 2e-6 default | 1e-5 | Committed dispatch |
|---|---|---|---|---|---|
| TR4 | 46 | 1e-6 | pass | pass | identical |
| TR3 | 49 | 1e-6 | pass | pass | identical |
| TR1 | 77 | 1e-6 | pass | pass | identical |
| TR9 | 90 | 3e-6 | — | pass | identical |
| TR2 | 95 | 1e-6 | pass | pass | identical |
| TR8 | 124 | 1e-6 | pass | pass | identical |
| TR5 | 214 | 1e-6 | pass | pass | identical |
| TR7 | 259 | 8e-6 | — | pass | identical |
| TR6 | 262 | 2e-6 | — | pass | identical |

- **5,184 vertices**, 576/576 → 576/576 Optimal on every transformer, no status change.
- **58,368 dispatch rows** across 1,216 batteries. `SOC_start`, `Pexec`, `Chg1`, `Dis1`,
  `TotPV1_pu` all `max |d| = 0.000e+00`. Not within tolerance — identical.

Three transformers miss the script's 2e-6 default on a handful of rows. The worst movement
in the campaign is **8 W** against the model's own `Feasibility_Tolerance = 1e-3` (1 kW),
i.e. 125× below the solver's guarantee, and it is scattered across unrelated periods and
angles — the signature `results/TR9_fairness.md` §5.4 identifies as numerical noise. Read
these as passes with the tolerance stated, not as silent passes: the 2e-6 default is
calibrated to one environment, not a physical constant.

The nine analysis workbooks were also rebuilt from the new dispatch — about **234,000
cells**, worst deviation 8.5e-14 (float64 rounding on the ×100 / ×1000 unit conversions) —
and all **72 published headline metrics** (PV, demand, export, import, SCR, SSR, periods
within 50 W, simultaneous charge/discharge rows) reproduce for all nine. Including the fine
detail: TR9's two documented `BES_TR9_five881_C` overlap rows come back as exactly 2, and
the other eight transformers as exactly 0.

## 3. Runtime

Wall-clock is elapsed real time; solver is the `time` column, which is
`FOR_VertexCont.SolutionTime` over the 576 vertices only and sees neither the committed
baseline solves nor matrix generation.

| TR | Batteries | Wall | Solver | Wall/solver | s/solve |
|---|---|---|---|---|---|
| TR4 | 46 | 0 h 36 m | 0 h 31 m | 1.16 | 3.19 |
| TR3 | 49 | 0 h 39 m | 0 h 34 m | 1.15 | 3.53 |
| TR1 | 77 | 1 h 37 m | 1 h 23 m | 1.16 | 8.68 |
| TR2 | 95 | 2 h 20 m | 2 h 02 m | 1.15 | 12.73 |
| TR9 | 90 | 3 h 16 m | 2 h 50 m | 1.15 | 17.76 |
| TR8 | 124 | 4 h 59 m | 4 h 15 m | 1.17 | 26.65 |
| TR6 | 262 | 6 h 49 m | 5 h 34 m | 1.22 | 34.84 |
| TR7 | 259 | 6 h 51 m | 5 h 46 m | 1.19 | 36.06 |
| TR5 | 214 | 8 h 36 m | 7 h 21 m | 1.17 | 45.98 |
| **Total** | **1216** | **35 h 43 m** | **30 h 18 m** | **1.18** | |

Cost does not track battery count: **TR5 at 214 batteries is the most expensive run of the
nine**, above TR7 (259) and TR6 (262). Topology drives it. The five largest runs are 89 %
of the total.

**Wall-clock is recoverable from file timestamps.** `RunFOR_Rolling` opens its CSV at the
start of the run and finishes writing at the end, so on NTFS `CreationTime` and
`LastWriteTime` bracket the run. Validated against three runs whose start times were known
independently, agreeing within 1–2 minutes (the model-init gap before the file opens). This
only holds for a freshly created file — an overwritten one keeps its original
`CreationTime`, which is why the July references cannot be timed this way.

## 4. Is GMP worth enabling? Yes — and the earlier comparison was invalid

Comparing the July reference `time` column against the new GMP runs appears to show GMP
*costing* solver time on most transformers. **That comparison does not measure GMP.** The
July references ran on AIMMS 26.1.3.1 / 26.2.3.3; every GMP run here is on 26.3.2.1, so the
delta is dominated by the version change.

A same-build A/B settles it. `RunTR2` and `RunTR2_GMP` on the same AIMMS, same machine,
same day — and `RunTrafoFOR("TR2")` sets exactly the switches `RunTR2_GMP` sets apart from
`RollUseGMP` / `RollGMPBaseline`, so the pair is clean. Over the **same 24 complete
periods** (288 vertices):

| TR2, same model + machine | AIMMS | s/solve |
|---|---|---|
| without GMP | 26.1 / 26.2 (July) | 10.76 |
| **without GMP** | **26.3.2.1** | **47.36** |
| **with GMP** | **26.3.2.1** | **13.61** |

**GMP is 3.5× faster (−71.3 %), and faster in every individual period.** AIMMS 26.3.2.1
made the non-GMP path roughly 4.4× slower; GMP insulates against that and lands near the
old non-GMP cost.

Practical consequence: **on AIMMS 26.3.2.1, run the `_GMP` procedures.** It also means the
35 h 43 m above was already the cheap path.

The comparison uses the 24 periods for which both runs have all 12 directions, so the two
sides cover identical work.

## 5. The July timings are not reproducible

The July *results* are trustworthy — §2 rests on them, and the second archive corroborates
them. The July *timings* are not.

The clearest evidence is TR9, run twice before any performance work: **bit-identical
results, 2.28× apart in speed** — 14.25 s/solve on 13 July, 32.53 s/solve on 24 July.
A second check: TR7 (259 batteries) and TR6 (262) are effectively the same size and their
July references differ by 51 %, while their same-build GMP runs differ by 3.5 %.

## 6. What is in this PR

- **`MainProject/OPF.ams`** — `RunTR1_GMP` … `RunTR8_GMP`, exact clones of `RunTR9_GMP`
  with only the tag and file suffix changed, inserted after it. +176 / −0, no other edit.
  These are what made the campaign possible; without them only TR9 had a GMP wrapper.
- **`results/gmp_validation_2026-08/`** — the per-transformer comparison reports, the
  timing table, the same-build A/B, and the one-page summary PDF.

Raw run outputs are **not** included: `.gitignore` excludes `FOR_rolling*.csv` and
`*_analysis_data.xlsx` by design. Everything needed to re-derive the tables above is in the
reports; the CSVs themselves are reproducible by running the procedures.

## 7. Open items

- `docs/rolling-for-performance.md` §6.3 records an untested hypothesis: the GMP generate
  block pins `Bound_Tolerance := 1e-6` because solving the baseline from the shared
  instance skips `MinOFminImports`, which otherwise sets it as a session option. Worth
  testing now that the version effect is known to be large.
- **`RunFOR_Rolling` writes its CSV incrementally**, contrary to the note that an
  interrupted run leaves it empty — the in-progress reference file was readable row-by-row
  at the halfway mark. The incremental-flush item in `docs/rolling-for-performance.md`
  "next steps" may already be satisfied for the production sweep.
