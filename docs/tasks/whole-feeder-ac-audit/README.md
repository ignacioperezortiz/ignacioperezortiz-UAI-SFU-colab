# Task: AC audit of the whole-feeder FOR (Run A, REF, four slots)

For Ignacio (and his Claude Code). Tulio tried job 1 on his computer (32 GB): AIMMS reached 22 GB (38 of 42 GB committed), and the step-1 P1 plan and all 12 directions of the first FOR ended NoSolution after about 3 min each, while your PR #30 run solved the same step; nothing was audited. If job 1 also gives NoSolution on your computer, stop and tell Tulio. Your computer (64 GB)
ran the whole-feeder Run A before (`CS-A-ALL-REF-r1`, PR #30). This task runs the same whole-feeder P2 for four slots, now with the AC audit on.

## Why

The LV-network runs (one P2 per LV network) are AC-audited: each FOR vertex goes through an AC power flow, and a vertex that breaks a
limit is moved toward the no-request point by bisection. Many vertices fail, mostly at night, because P2 computes the BESS currents at
the fixed linearization voltage of 1.037 pu. The whole-feeder P2 uses the same BESS current model, but it was never AC-audited
(`ACAudit 0` in its `info.txt`). Its own columns `VminTrue`/`VmaxTrue`/`UVviol`/`OVviol` come from P2's solution, not from an AC power
flow, and in the LV runs they flag none of the vertices that the AC audit rejects. This task gives the whole-feeder AC audit for the
same slots, plus an export of every AC power flow, so Tulio can check it in OpenDSS.

## The model

This branch = `af0958c` (the model of every LV-network run in the paper) with `MainProject/OPF.ams` replaced by the exact file Tulio's lanes
use for the AC export (SHA-256 starts `62aed078f8696d2e`). It adds two switches to `af0958c`, both inert by default:
- `ZX_Retry` (default 0 = `af0958c`): not used here.
- `ACA_Export` (default 0): with 1, the AC audit also writes `ACX_*.csv` (network, injections and converged solution of every
  load-flow test). Files only: no other output changes (checked on four LV networks, 22 files each, identical).

Check the hash before you start:
```
python -c "import hashlib;print(hashlib.sha256(open('MainProject/OPF.ams','rb').read()).hexdigest()[:16])"
```
It must print `62aed078f8696d2e` (the hash of the file with Windows line endings, as Git checks it out with `core.autocrlf=true`; with LF endings, convert first).

## Steps

1. `git fetch origin pull/32/head:task/whole-feeder-ac-audit` and `git checkout task/whole-feeder-ac-audit`.
2. Prepare one lane, as for PR #30 (your AIMMS 26.4 project file through `--project` if needed):
   `python scripts/paper1/run_paper1.py prepare WA --strict --work <your runs folder>`
3. Close other AIMMS sessions. Run the queue of this folder in that one lane:
   `python scripts/paper1/run_paper1.py lane WA docs/tasks/whole-feeder-ac-audit/wf_ac_audit.txt --work <your runs folder>`
   One lane only: each job loads the whole feeder (1216 BESSs).
4. After job 1, run the consistency check below before you let the others run (or stop the lane, check, and start it again: the runner
   skips finished jobs).
5. Send back what is listed under "What to send".

## The four jobs (`wf_ac_audit.txt`)

| # | Slot of the FOR | Settings | Why this slot |
|---|---|---|---|
| 1 | 00:30 (period 1) | `SRQ_MaxPer=1` | night import; no earlier periods, so the cheapest; the same job Tulio tried |
| 2 | 04:00 (period 8) | `RollSweepFrom=8 SRQ_MaxPer=8` | night import, slot of the FOR figure |
| 3 | 12:30 (period 25) | `RollSweepFrom=25 SRQ_MaxPer=25` | maximum export, voltage at its upper limit |
| 4 | 18:00 (period 36) | `RollSweepFrom=36 SRQ_MaxPer=36` | evening, slot of the FOR figure |

All four: `CS_A free_today a0x16p16fin ALL CaseAggMap=1 ACAudit=1` + the settings above + `ACA_Export=1` (job 1 has the same tag as Tulio's test). `a0x16` = the 12 directions one after the other with
16 CPLEX threads (less memory than `a3x5`). `RollSweepFrom=n` runs P1 at every period as always (same SOC trajectory as a full day) and
sweeps only from period n; `SRQ_MaxPer=n` stops after period n. Period n builds the FOR of target n+1 (`now = n`, `target = n+1`).
`ACAuditApply` stays 0: the audit only logs, so the FOR itself is the one of PR #30.

**Expected time:** P2 alone took about 2.5 h per period on your computer in PR #30 (12 directions one after the other). The audit adds an
AC power flow of the whole feeder for each bisection test, about 8 per failing vertex; nobody has timed that on the whole feeder yet.
Count on several hours per job. Jobs 2-4 also run P1 for the periods before their slot (minutes each, P1 without network).

## Consistency check (after job 1)

Job 1's FOR must equal PR #30's FOR at `now = 1` (`results/case-study/summary/CS-A-ALL-REF-r1/for_corners.csv`): for each of the 12
directions, P and Q within 1 kW / 1 kvar (PR #30's checkpoint model and this one share P2; only the audit is new). If they differ more,
stop and tell Tulio: then the inputs or the model differ.

## What to send

From the lane folder, for each job (`<tag>` = the job's tag):
- `FOR_rolling<tag>.csv`, `FOR_rolling_ac<tag>.csv`, `FOR_rolling_soc<tag>.csv`, `record<tag>.json`, `done<tag>.txt`, `aimms_err<tag>.txt`;
- all `ACX_*<tag>.csv` (the export; these can be large);
- `lane.log`, and the peak memory of AimmsCmd if you watched it.

Zip them and send the zip to Tulio (do not commit the `ACX_` files). Tulio compares the whole-feeder audit with the LV-network audits of the
same slots and repeats the power flows in OpenDSS.

## Stop and ask

Stop and tell Tulio before anything not in these steps: a job that fails or is infeasible, a consistency check that does not pass,
memory that runs out, or a change to the model.
