# Post-processing scripts

Python scripts that turn the model's CSV exports into combined FORs, comparison
reports, and the per-transformer analysis workbooks in `results/`.

Requires Python 3 with `numpy`, `pandas`, `xlrd`, and `openpyxl`.

> **Heads-up on paths.** These scripts were written with hard-coded default paths
> pointing at the author's machine (e.g. `...\UAI-SFU-colab\model_clean`, and a
> `C:\Users\LAPTOP-01\Desktop` default in `compare_FOR_to_NCQ.py`). They are all
> overridable from the command line — pass the flags below to point them at your
> own repo. Making the defaults portable is a good early cleanup task.

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
