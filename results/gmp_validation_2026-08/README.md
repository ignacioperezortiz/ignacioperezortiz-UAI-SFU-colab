# GMP validation evidence — August 2026

Raw output of the checks behind `docs/gmp-validation-nine-transformers.md`. Read that
document first; these files are the receipts.

| File | What it is |
|---|---|
| `TR<n>_boundary.txt` | `compare_FOR_runs.py` output, pre-update reference vs GMP run, at the 2e-6 default and again at 1e-5 |
| `ALL_soc_dispatch.txt` | committed dispatch, all nine — `SOC_start`, `Pexec`, `Chg1`, `Dis1`, `TotPV1_pu`, every row |
| `ALL_workbooks_cells.txt` | the nine analysis workbooks rebuilt cell-by-cell from the new dispatch |
| `ALL_headline_metrics.txt` | the 72 published headline metrics recomputed and compared |
| `gmp_run_timing.csv` | per-transformer start, end, wall-clock, solver time, s/solve |
| `TR2_same_build_AB.txt` | the same-build A/B: `RunTR2` vs `RunTR2_GMP`, per period |
| `GMP_validation_summary.pdf` | one-page summary |

Reproducing the boundary and dispatch checks needs the run CSVs, which `.gitignore`
excludes by design — regenerate them with `RunTR<n>` and `RunTR<n>_GMP`.

The workbook and metric checks additionally need the per-transformer analysis workbooks,
which live outside this repository (`*_analysis_data.xlsx` is also gitignored).

**Note on the timing columns.** `gmp_run_timing.csv` carries both `july_ref_s_per_solve`
and `gmp_s_per_solve`. Do **not** difference them: the July references ran on AIMMS
26.1.3.1 / 26.2.3.3 and every GMP run here is on 26.3.2.1, so the gap measures the version,
not GMP. `TR2_same_build_AB.txt` is the controlled comparison.
