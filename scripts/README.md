# Post-processing scripts

Python scripts that turn the model's CSV exports into combined FORs, comparison
reports, and the per-transformer analysis workbooks in `results/`.

Requires Python 3 with `numpy`, `pandas`, `xlrd`, and `openpyxl`. The four fairness
scripts (`check_fairness.py`, `make_viz_data.py`, `build_viz.py`, `run_timing.py`) need
the standard library only.

Paths are portable: the workbook and comparison scripts resolve their defaults from the
repo root (`Path(__file__).parents[1]`), so bare file names are looked up there and the
flags below only need overriding for files kept elsewhere. `compare_FOR_to_NCQ.py` also
honours `FOR_NCQ_DIR` for a machine-specific export folder. The fairness scripts instead
look for their CSVs in the **current directory** (`--root`, default `.`), so run them
from the repository root; `build_viz.py` resolves its template and output relative to
the script's own location.

---

## `combine_FOR_pertrafo.py`
Minkowski-combines the per-transformer rolling FORs into a whole-feeder FOR.

- **Inputs:** `FOR_rolling_TR<n>.csv` for each tag, plus `FOR_rolling_baseline.csv`
  (the passive background, needed when combining more than one transformer). These
  are model outputs (git-ignored) — generate them by running the model first.
- **Output:** `FOR_rolling_combined.csv`.
- **Run:**
  ```bash
  python combine_FOR_pertrafo.py --tags TR1,TR2,...,TR9 --dir <path-to-csv-folder>
  ```
  Add `--compare <coupled-run.csv>` to print coupling-gap metrics.

## `compare_FOR_to_NCQ.py`
Cell-by-cell comparison of two AIMMS `.xls` workbooks, aligned by row-header label —
the validation proof against Prof. Luis's base case.

- **Inputs:** two `.xls` workbooks (e.g. `FOR_ref_25.xls` vs `NC_Q_25.xls`). **These
  reference workbooks are not in the repo** — they must be supplied separately.
- **Run:**
  ```bash
  python compare_FOR_to_NCQ.py [vertex_file.xls]
  ```

## `compare_FOR_runs.py`
Compares two rolling-FOR runs row by row, to check that a change to the sweep left
the results untouched. Aligns on `(now, angle_deg)`.

- **Inputs:** two `FOR_rolling*.csv` files (model outputs, git-ignored). Bare names
  are looked up in the repo root.
- **Output:** a report on stdout; exit code 0 on pass, 1 on fail.
- **Run:**
  ```bash
  python compare_FOR_runs.py OLD.csv NEW.csv [--tol 2e-6]
  ```

The acceptance criterion is **`proj`, not P/Q equality**. The sweep maximises a linear
objective over a convex feasible set, so the optimal *value* is unique but the argmax
need not be: on a flat face perpendicular to the sweep direction the optimum is a
segment, and a different starting point may legitimately return a different point on
it. The script fails only on `proj` outside tolerance or on a changed solve status,
and reports P/Q movement as informational. See `docs/rolling-for-performance.md` §4.

## `build_workbook.py`
Builds a `TR<n>_analysis_data.xlsx` workbook (the source of the `results/*.xlsx`
files) from a rolling-dispatch CSV and a per-customer load+PV table.

- **Inputs:** `FOR_rolling_soc_<TAG>.csv` (model output) and a per-customer
  `TR<n>_load_PV_48periods.xlsx` load/PV table (currently exists for TR9 only).
- **Output:** `<TAG>_analysis_data.xlsx` (refuses to overwrite unless `--force`).
- **Run:**
  ```bash
  python build_workbook.py --tag TR9 --soc <soc.csv> --loadpv <loadpv.xlsx> --outdir <dir>
  ```
  Defaults are hard-coded to TR9; override with the flags for other transformers.

---

The four scripts below cover the fairness runs (`FairMode` 1 and 2 against the
no-fairness case A). They read their CSVs from the current directory by default, so run
them **from the repository root** with the model outputs there. Results and reasoning:
`results/TR9_fairness.md`.

## `check_fairness.py`
Verifies the fairness runs against case A: nesting `proj_L1 <= proj_L2 <= proj_A` at
every vertex, constraint satisfaction (`util == zeta` in every aggregator, plus
`util_min == util_max` for level 1), the `|zeta| <= 1` bound, and how much the
projection contracted.

- **Inputs:** `FOR_rolling<suffix>.csv` / `_fairL1` / `_fairL2` plus the matching
  `FOR_rolling_fair<suffix>*.csv` fairness logs (model outputs, git-ignored). Missing
  or still-empty cases are skipped with a notice rather than passing vacuously.
- **Output:** a report on stdout; exit code 0 on pass, 1 on fail.
- **Run:**
  ```bash
  py -3 scripts/check_fairness.py                 # micro test bed
  py -3 scripts/check_fairness.py --suffix _TR9   # TR9
  ```

Two tolerances, deliberately. `TOL_PROJ = 2e-6` — inherited from `compare_FOR_runs.py` —
counts how many vertices moved at all. `TOL_NEST = 1e-4` is used only by the nesting
checks, which compare two *different* formulations, each solved independently to
`Feasibility_Tolerance = 1e-3`; 1e-4 is 10× stricter than that guarantee and three orders
of magnitude below the smallest defect worth catching. The derivation is in
`results/TR9_fairness.md` §5.4.

## `make_viz_data.py`
Extracts cases A / L1 / L2 to one compact JSON for the viewer, and reports the **area**
contraction (shoelace over the 12 vertices per period) — the metric `check_fairness.py`
does not cover.

- **Inputs:** the same rolling-FOR CSVs, plus the all-idle baseline
  (`FOR_rolling_baseline.csv`, or `FOR_rolling_baseline_micro.csv` for the micro bed)
  for the deviation view. Without the baseline it emits the absolute region only.
- **Output:** `scripts/for_data<suffix>.json` (git-ignored, regenerated).
- **Run:**
  ```bash
  py -3 scripts/make_viz_data.py                 # micro test bed
  py -3 scripts/make_viz_data.py --suffix _TR9   # TR9
  ```

Report **both** metrics. Area loss and projection loss diverge widely: where the FOR has
a flat face the optimum slides to a fair point at no projection cost, so projection alone
suggests fairness is nearly free when it is not.

## `build_viz.py`
Builds the self-contained interactive HTML viewer from that JSON plus
`for_viz_template.html`.

- **Inputs:** `scripts/for_data<suffix>.json` (run `make_viz_data.py` first) and
  `scripts/for_viz_template.html`.
- **Output:** `results/viz/FOR_fairness_micro.html` or
  `results/viz/FOR_fairness_TR9.html`. No network access at runtime — the page opens
  with a double click.
- **Run:**
  ```bash
  py -3 scripts/build_viz.py                 # -> results/viz/FOR_fairness_micro.html
  py -3 scripts/build_viz.py --suffix _TR9   # -> results/viz/FOR_fairness_TR9.html
  ```

Per-bed text and the two footer figures are substituted into the template; the figures
are derived from the JSON, never typed in, so they cannot drift from the data they
illustrate. A new test bed needs an entry in the `BEDS` dict of both this script and
`make_viz_data.py`.

## `for_viz_template.html`
The parameterised page for `build_viz.py` — placeholders (`__DATA__`, `__BED_TAG__`,
`__SPAN_REGION__`, …) and all the CSS/JS the viewer needs. Not usable on its own; edit
it here and rebuild both HTML files. `build_viz.py` warns if any placeholder is left
unfilled.

## `run_timing.py`
Timing table for the rolling-FOR runs: per file, the number of vertices, the status
tally, total/median/max solver time and the change against the case-A reference.

- **Inputs:** any `FOR_rolling*.csv` (defaults to the three TR9 files: case A, `_fairL1`,
  `_fairL2`).
- **Output:** a Markdown table on stdout.
- **Run:**
  ```bash
  py -3 scripts/run_timing.py
  py -3 scripts/run_timing.py a.csv b.csv --inicio "2026-07-31 17:15"
  ```

The CSV `time` column is `FOR_VertexCont.SolutionTime` only — 576 vertex solves per run,
excluding the 48 per-period baseline solves, the data loading and the I/O. That is why
solver time is below wall-clock. Wall-clock is derived from the file mtime (when AIMMS
closed it) minus the `--inicio` start time, which applies to the **last** file listed.
