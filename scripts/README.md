# Post-processing scripts

Python scripts that turn the model's CSV exports into combined FORs, comparison
reports, and the per-transformer analysis workbooks in `results/`.

Requires Python 3 with `numpy`, `pandas`, `xlrd`, and `openpyxl`.

Paths are portable: every script resolves its defaults from the repo root
(`Path(__file__).parents[1]`), so bare file names are looked up there and the flags
below only need overriding for files kept elsewhere. `compare_FOR_to_NCQ.py` also
honours `FOR_NCQ_DIR` for a machine-specific export folder.

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
