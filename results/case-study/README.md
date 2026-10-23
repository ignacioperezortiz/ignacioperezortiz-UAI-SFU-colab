# Case-study results (paper 1)

Written by `scripts/paper1/case_study/collect_run.py`; rules in `docs/case-study.md` §6–7. Do not edit by hand.

| Path | Content |
|---|---|
| `runs.csv` | the register: one row per recorded run (run id, who, job line, commit, start/end, wall time, computer, raw zip) |
| `records/<run_id>.json` | full run record: code commit, input hashes, settings (`scenario.txt`), computer, AIMMS, output hashes |
| `summary/<run_id>/` | compact files for the figures: FOR corners, fleet per step, per prosumer, fairness logs, time per step, run summary |
| `analysis/` | outputs of `scripts/paper1/case_study/analysis/*.py` |

Run id: `CS-<run>-<network>-<variant>-r<n>` (e.g. `CS-A-TR4-REF-r1`). Raw outputs of each run: `<run_id>.zip` in the
shared folder `CaseStudy/raw/` (SHA-256 in the record), not in Git.
