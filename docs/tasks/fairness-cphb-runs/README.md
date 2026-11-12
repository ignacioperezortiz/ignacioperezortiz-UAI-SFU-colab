# Task: Run A with CP and HB on TR5-TR9 (fairness at the interface) - for Ignacio

Written Thu 12 Nov 2026 by Tulio (with Claude Code). This file is self-contained: open it in Claude Code and ask it to carry out the task step by step.

## Goal

Section VI-C of paper 1 must report the fairness criteria CP and HB at the TSO-DSO interface, i.e. summed over the nine LV networks (eq. `for_sum`).
CP and HB are already run in Chile for TR1-TR4, for TR6 (CP) and for TR5 (CP). This task runs the **8 missing jobs** with the exact model of those
runs, after a consistency check that your setup reproduces ours. The interface sums are then computed in Chile from your outputs.

**Why the runs are per transformer when the result is at the interface:**

- The method solves each LV network separately: P2 with one network in detail and the other eight lumped as fixed loads.
- It then adds the nine FORs direction by direction to form the FOR at the TSO-DSO interface (paper, Section V, eq. `for_sum`).
- The fairness groups also stay inside one LV network: one per aggregator for HPi, one per network for HPn.
- So the interface FOR under CP or HB needs all nine networks run under CP and HB:

  | LV network | CP | HB |
  |---|---|---|
  | TR1-TR4 | Chile | Chile |
  | TR5 | Chile | **this task** |
  | TR6 | Chile | **this task** |
  | TR7-TR9 | **this task** | **this task** |

- With your 8 jobs, all nine are complete, and `v_cphb_sum.py` in Chile adds them into the interface FOR.
- The TR4 job at the top of the queue only checks your setup. It is not part of the result.

The review of the fairness text (introduction, Section IV-C, run design, VI-C, Discussion, Conclusion) is part of the same handoff. The paper files are
**not** in this repository, which is public. They come in a private package from Tulio (`handoff_ignacio.zip`, folder `2_review`, with its own README).
Never commit paper text, PDFs or results tables of the paper to this repository.

## What is in this folder

| File | Content |
|---|---|
| `queue.txt` | line 1: the consistency check (TR4 CP); lines 2-9: the 8 jobs |
| `reference_TR4_CP/` | our outputs of the TR4 CP job: `FOR_rolling<tag>.csv` (FOR vertices) and `SCT_exec<tag>.csv` (executed BESS dispatch) |
| `compare_with_reference.py` | compares your TR4 CP outputs with the reference |

## The model

- **Branch:** this branch starts from commit `af0958c` ("case study: unblock Run B ..."), the commit of every CP/HB run made in Chile. It does not start from `main` (5 commits ahead, 2 behind).
  - The model, `scripts/paper1/run_paper1.py`, `scripts/paper1/scenarios/CS_A.json` and `inputs/case-study/aggregators_case_study.txt` are exactly those of the Chile runs.
  - The runner and scenario were checked identical apart from line endings.
- **Do not edit `MainProject/OPF.ams` on this branch.** Do not open and save it in AIMMS either: AIMMS rewrites the file on save.
- **Hashes (sha256):**
  - `MainProject/OPF.ams` starts `96e2c1319190f05e`.
  - `OPF.aimms` starts `0a44f18a21c2cfb7`.
  - The `prepare` step writes them into each lane's `prepare_info.json` (`files_sha256`). Check them there.

The three input files are not in Git (`.gitignore`). Place them in the repository root and check their sha256 before preparing the lanes:

| File | sha256 |
|---|---|
| `Database.mdb` | `8b474da7f5b579561ae734d5f89a753e84f390b07082a8489fb32be08f95a8ed` |
| `Database.dsn` | `3b9783d0d6801898c1e6d124a544b79fbd47761d470a93872a5bb04778973717` |
| `OpData.xls` | `daf841adc4db08f3577e9c8554bdf9fc3a1962286236d70c513b98a34f1defda` |

(PowerShell: `Get-FileHash Database.mdb -Algorithm SHA256`.) If a hash differs, stop and ask Tulio for the files. They are also in his private package
(`1_runs\lane_template`).

**Software:** AIMMS 26.3.2.1 (AimmsCmd), CPLEX 22.1, Python 3.12 with pandas. Chile computer: Intel Core i9-14900, 32 GB, Windows 11.

## Steps

From the repository root, on this branch, with a clean working tree:

1. **Check the three input files** (table above).

2. **Prepare two lanes** outside the repository, e.g. `C:\fair_runs`. Each lane is one AIMMS session and one licence seat.
   ```
   python scripts/paper1/run_paper1.py prepare L1 L2 --work C:\fair_runs --strict
   ```
   Check `C:\fair_runs\L1\prepare_info.json`: `MainProject/OPF.ams` must start `96e2c1319190f05e`.
   If AimmsCmd is not under `%LOCALAPPDATA%\AIMMS\IFA\Aimms\*\Bin`, set `AIMMS_CMD` to its full path.

3. **Start both lanes**, each in its own console. They share the queue through claim files in `C:\fair_runs\claims`:
   ```
   python scripts/paper1/run_paper1.py lane L1 docs/tasks/fairness-cphb-runs/queue.txt --work C:\fair_runs
   python scripts/paper1/run_paper1.py lane L2 docs/tasks/fairness-cphb-runs/queue.txt --work C:\fair_runs
   ```
   - **Lanes and memory:** the runner never runs TR6 and TR7 at the same time (about 5 GB each). Do not run more than two lanes on 32 GB.
   - **Logs:** each lane logs to `<lane>\lane.log`.
   - **Per job:** each job writes `done<tag>.txt` and `record<tag>.json`.

4. **Consistency check.** When the TR4 CP job (line 1, about 1.1 h in Chile) is done:
   ```
   python docs/tasks/fairness-cphb-runs/compare_with_reference.py C:\fair_runs\L1
   ```
   Use `L2` if that lane ran it.
   - **Expected:** the same solver statuses, and differences of order 1e-6 or less. Run on our own files, it gives exactly 0.
   - **If a status differs, or a difference exceeds 1e-3:** stop both lanes and report the output in this PR before running anything else. The interface sums mix your runs with ours, so they must come from the same model.
   - **Otherwise:** let the lanes continue with the 8 jobs, and post the comparison output in this PR.

5. **The 8 jobs** (lines 2-9 of `queue.txt`). Times are from Chile. `~` = estimate.

   | Job | Time |
   |---|---|
   | TR7 CP (`a0x2p16fin`) | ~12-14 h |
   | TR6 HB eps 0.5 (`a0x2p16fin`) | ~12 h (TR6 CP: 12.0 h) |
   | TR7 HB eps 0.5 (`a0x2p16fin`) | ~12-14 h |
   | TR5 HB eps 0.5 (`a0x2p4fin`) | ~12 h (TR5 CP: about 12 h) |
   | TR8 CP and TR8 HB (`a0x2p4fin`) | ~8-12 h each |
   | TR9 CP and TR9 HB (`a0x4p8fin`, `SPD_P1NoNet=0`) | ~4 h each |

   Keep the job lines exactly as written. The speed codes reproduce the Run A runs of each network, and they are part of the output tag.

6. **Known behaviour, not a failure: CP in the evening of the large networks.**
   - In TR6, CP stopped every aggregator group in the evening, as the BESSs filled. The FORs for 17:30 and 19:00 were Infeasible in all 12 directions. The executed dispatch stayed Optimal.
   - Expect the same in TR7 CP.
   - **Do not restart such a run.** The model is deterministic, and the same steps would fail again.
   - In Chile, failed CP directions and slots count as zero (no movement) in the interface sums.

7. **Return the outputs.**
   - **What to commit:** for each job, `FOR_rolling*<tag>*`, `SCT_exec<tag>*`, `SCT_info<tag>*` and `done<tag>.txt`, plus both `lane.log` files.
   - **Where:** under `results/paper1-cphb-runA/<tag>/` on this branch, unchanged.
   - **Leave out:** `record<tag>.json` and `stdout<tag>.txt`. They hold local paths of your computer.
   - **Alternative:** if you prefer not to commit results, zip the same files and send them to Tulio.
   - **Then:** post a summary in this PR, with each job, its time and any steps not Optimal.

## For Claude Code (if Ignacio asks you to do this task)

- Follow the steps in order. Ask Ignacio before anything that is not in them.
- **Never** edit or save `MainProject/OPF.ams`, the runner, the scenario or the input files. Never change a job line.
- Never run more than two lanes, and never TR6 and TR7 together. The runner enforces this, so do not bypass it.
- Stop and report if an input-file hash or the `OPF.ams` hash in `prepare_info.json` does not match, or if the consistency check fails.
- A job whose evening FOR steps are Infeasible under CP is expected (step 6). Note it and do not restart it.
- Do not commit paper text, PDFs or tables of results of the paper. The repository is public.
- The fairness review uses the private package (`2_review` folder of `handoff_ignacio.zip`). Its README lists the parts, the questions and the style rules. Send suggestions to Tulio, not to this repository.
