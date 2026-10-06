# Two PV options test: model, scripts and results

This folder holds the exact AIMMS model and the scripts behind the results of 6 Oct 2026, so the results can
be checked and the work can continue, in particular the **fairness** part.

- **What changed and why, in plain words:** [`OVERVIEW.md`](OVERVIEW.md). Read it first.
- **All the numbers:** [`results/RESULTS.md`](results/RESULTS.md) and `results/pv2_summary.txt`.
- **Day-by-day notes of the test:** [`LOG.md`](LOG.md).

## 1. What is in the folder

| Path | What |
|---|---|
| `model/` | The AIMMS project used for every run (`OPF.aimms`, `MainProject/OPF.ams`, sha256 starts `e000fbda90019cb8`) |
| `scripts/run_pv2.py` | Runs days headless, one AIMMS session per "lane", lanes share one job queue |
| `scripts/analyze_pv2.py` | Reads the runs and writes `results/` |
| `scripts/add_pv2.py`, `add_pv2_fix.py` | The last two patches applied to the model (already applied; for reference) |
| `scripts/lineage/` | The earlier patches, in the order they were applied (for reference, see section 8) |
| `scenarios/` | The 16 TSO behaviours + `SMOKE` (`index.csv` describes them) |
| `results/` | Results of the 66 days (the raw run folders are not in git: 214 MB) |

## 2. What you need

- AIMMS 26.3.2.1 with CPLEX 22.1. With the academic cloud licence, only 3 AIMMS sessions can run at the same
  time.
- Microsoft Access Database Driver (ODBC), as for the main model.
- The three input files from the cloud folder: `Database.mdb`, `Database.dsn`, `OpData.xls`. **Copy them into
  `model/`** (not the repository root). `Database.dsn` points to `.\Database.mdb`, so it works from any folder.
- Python 3 with `pandas` and `scipy` (only for the analysis).

## 3. Run one day

**A. In the AIMMS IDE (easiest for a first try)**
1. Open `model/OPF.aimms`.
2. Create `model/scenario.txt` (example below, or let `run_pv2.py` write one, see B).
3. Run the procedure `PV2_Run`. It reads `scenario.txt` and runs one TR4 rolling day of 48 half-hours.
4. The output files appear in `model/` (section 6).

Example `scenario.txt` (the `SMOKE` pattern, rule (ii), coordinated charging, fairness mode 2):

```
SRQ_Tag := "_SMOKE_exp_coord_f2" ;
SRQ_MaxPer := 30 ;
FRQ_SweepAll := 0 ;
FRQ_PlanLog := 0 ;
SRQ_Periods := "12,17,20,22,24,26" ;
ZX_GMP := 1 ;
SCTight := 1 ;
PV2_Regime := 1 ;
SRQ_Coord := 1 ;
FRQ_BF := 1 ;
FairMode := 2 ;
FRQ_U1 := DATA { 12 : 0.4, 17 : 0, 20 : 0.7, 22 : 0, 24 : 0, 26 : 0.2 } ;
FRQ_U2 := DATA { 12 : 0.5, 17 : 0, 20 : 0.3, 22 : 0, 24 : 0, 26 : 0.8 } ;
FRQ_U3 := DATA { 12 : 0.5, 17 : 0, 20 : 0.6, 22 : 0, 24 : 0, 26 : 0.4 } ;
FRQ_Edge := DATA { 12 : 0, 17 : 2, 20 : 1, 22 : 2, 24 : 3, 26 : 0 } ;
```

**B. Headless, many days (how all the results were made)**

```bat
set AIMMS_CMD=C:\path\to\your\Aimms\Bin\AimmsCmd.exe
python scripts\run_pv2.py prepare L1 L2 L3
python scripts\run_pv2.py lane L1 runs\queue.txt
```

- `prepare` copies `model/` (with the data files) to `runs/L1`, `runs/L2`, ... One copy per lane.
- A queue file has one job per line, `<pattern> <case>`, for example `R00_sun exp_coord_f2`. Lines starting
  with `#` are skipped.
- Start one `lane` command per AIMMS licence, in separate windows, about 40 s apart. Lanes take the next free
  job from the shared queue.
- **Resumable:** a job is skipped if any lane already has `done_<tag>.txt` with "Return value = 0". Claims are
  in `runs/claims/`; delete a claim file to run that job again.
- If all licences are busy, the launcher waits and tries again every 3 min.

**Run times on TR4** (3 runs in parallel on a 32-core PC):

| Day | Time |
|---|---|
| Day without requests (REF) | 10-26 min |
| Random pattern (4-21 requests) | 18-67 min |
| Worst cases (28-33 requests) | 53-85 min |

Each request adds about 1.3 min for the FOR, more under rule (ii) because of the battery-only twins.
Coordinated charging roughly doubles the time of the day without requests.

## 4. Cases and patterns

| Case | PV rule | Charging | Delivery |
|---|---|---|---|
| `exp_today` | (ii) exported, cut only if the TSO's point needs it | normal P1 | batteries first |
| `exp_coord` | (ii) | charging at the PV peak (second P1 problem) | batteries first |
| `noexp_today` | (iii) no export without the TSO's agreement | normal P1 | usual mix |
| `noexp_coord` | (iii) | charging at the PV peak | usual mix |

Add `_f1` ... `_f4` to any case to set `FairMode` (for example `exp_coord_f2`).

Patterns (`scenarios/index.csv`):
- `REF`: no request.
- `EDGE_SUN`: a request every half-hour 07:00-17:00, on the FOR edge.
- `R00`-`R11`: random points inside the FOR.
- `WC_EXPORT` / `WC_IMPORT`: the most-export / most-import corner every half-hour.
- `SMOKE`: 6 requests, stops at 14:30, about 30 min.

Each request has three numbers `u1, u2, u3` that pick a point uniformly over the FOR's area, plus a flag
(0 inside, 1 on the edge, 2 most export, 3 most import). The same numbers are used in every case, so the TSO
behaviour is the same, but it is applied to each case's own FOR.

## 5. The main switches (all read or set by `PV2_Run`)

| Switch | Value used | Meaning |
|---|---|---|
| `PV2_Regime` | 1 / 2 | 1 = rule (ii): PV-cut variable in the FOR (`PVC_On = 1`, `PVC_Mode = 1`: only the surplus). 2 = rule (iii): `ZX_On = 1` (P1 cuts the surplus, no export, PV fixed in the FOR) |
| `SRQ_Coord` | 0 / 1 | 1 = second P1 problem (`SRQ_P1Coord`): charging at the PV peak, same purchases |
| `FRQ_BF` | 1 under rule (ii) | batteries-first delivery (battery-only twins, least PV cut) |
| `SCFirst`, `SCAlpha` | 1, 0 | P1 weighs the service half-hour; no house buys more later than its P1 plan |
| `SCTight` | 1 | that rule in kW with a 0.01 W tolerance (`ZX_SCTight`), instead of 1 W (`SCNoImportFuture`) |
| `SRQ_Mode`, `RollSvcMode` | 2, 4 | the TSO picks a point inside the FOR; set-points by mixing stored solutions |
| `FRQ_SweepAll` | 0 | build the FOR only at request half-hours (1 = every half-hour) |
| `ZX_GMP` → `RollUseGMP` | 1 | GMP sweep (one matrix per half-hour). Needed by `FRQ_BF` |
| `PVC_SweepPen` | 0.1 | small cost on PV cut in the FOR directions, so corners cut PV only when it helps |
| `FairMode` | 0 (results) | your fairness levels 1-4 (section 7) |

## 6. Output files (one set per run, in the lane folder)

| File | One row per | Main columns |
|---|---|---|
| `SCT_exec<tag>.csv` | house and half-hour | `svc` (1 = this half-hour executes a TSO request), `imp1_kWh`, `exp1_kWh`, `cut1_kWh` (rule ii cut), `zx_cut1_kWh` (rule iii cut), `soc_start`, `imp_plan_fut_kWh` |
| `FRQ<tag>.csv` | request | chosen point (`req_P_kW`, `dP_kW`, ...), weights `a0 a1 a2`, FOR area, set-points, `cut_kW` |
| `BF<tag>.csv` | request (rule ii) | `cut_mix_kW` (usual mix) vs `cut_bf_kW` (batteries first), battery-only FOR area |
| `FOR_rolling<tag>.csv` | FOR corner | P, Q, solver status, voltages |
| `FOR_rolling_svc<tag>.csv` | executed request | requested vs realised transformer point |
| `SRQ_p1<tag>.csv` | half-hour (coordinated runs) | status of the two P1 problems |
| `SCT_info<tag>.txt` | run | program types (all QCP), CPLEX version, summary line `PV2 summary ...` |
| `done<tag>.txt` | run | the AIMMS return line |

Run `python scripts/analyze_pv2.py` after copying the run folders to `runs/L*/` (it reads every finished run
and writes `results/`).

## 7. Fairness: how it works now, and what to change

**Now (unchanged from `main`):**
- The proportional rows are `FairProportional_Prosumer` (line 1487), `..._Aggregator`, `..._ProsumerExch` and
  `..._AggregatorExch`. They use `Zeta * FairCap` (`FairCap`, line 1389).
- They exist only when `FairActive = 1`, which is set before the FOR directions are built. P1 and the second P1
  problem run with `FairActive = 0`.
- The GMP sweep matrix is generated after `FairActive := 1` (line 4079; generation at line 4119), so the rows
  are in every direction and in every battery-only twin.

**What to change for fair delivery.** The request code builds the FOR from the no-request point S0 plus the
corners, and puts S0 in the mix. S0 is the P1 plan, which is usually not fair.

| Where in `MainProject/OPF.ams` | What it does now | Suggested change when `FairMode > 0` |
|---|---|---|
| line ~3950, block "FOR-first requests: the no-service solution x0" | stores S0: `FRQ_S0P/Q`, `FRQ_Chg0/Dis0/Q0` | keep it (it is still what runs when there is no request) |
| line ~5005, block "FOR-FIRST REQUEST (SRQ_Mode = 2)", before `FRQ_Area` | triangles (S0, corner i, next corner) | replace S0 by the **average of the solved corners** (and its average set-points and PV cut). The average of fair solutions is fair, and it lies inside the FOR. |
| `FRQ_K(bat) := FRQ_A1*FRQ_Cut(...) + FRQ_A2*FRQ_Cut(...)` | PV cut of the mix; S0 has no cut | add `FRQ_A0 *` (average cut), because the new centre point can cut PV |
| line ~5094, `if ord(bfp) = 1 then` (batteries first) | stored point 1 = S0 | use the same average point (or leave point 1 out: `FRQ_BOK := 0`) |
| `ZX worst cases` block (line ~5059) | most-export / most-import corner | nothing to change (corners only) |

**A first check is already done (6 Oct):** `SMOKE exp_coord_f2` (FairMode 2) runs without problems, in
15 min.
- All 6 points were delivered exactly.
- The fairness log shows `util = Zeta` (0.627) for the three aggregators at every corner.
- But the mix at 05:30 still used 29 % of the no-request point (`a0 = 0.29` in `FRQ<tag>.csv`). That is exactly
  the change described above.

Because the fairness rows are linear, any mix of fair stored solutions is fair, so delivery stays exact.
Points to decide (see `OVERVIEW.md`, section 5):
- PV cut shared fairly or not: modes 1-2 vs 3-4.
- The self-consumption rule may make mode 1 collapse the FOR.

**Checks after the change:**
- `FOR_rolling_svc`: realised = chosen point.
- The fairness log `FOR_rolling_fair<tag>.csv` (one row per corner and aggregator): `util` equal to `Zeta`.
- For the executed mix: battery powers proportional to `FairCap` (they are a mix of fair corners).
- `SCT_exec`: no house buys more outside the request half-hours than on `REF`.

## 8. Where the model comes from

The model is **not** the `main` version. It is Tulio's local `OPF.ams` of 30 Sep 2026: the branch
`fix/linearization-derivatives` plus about 4 500 lines that were never pushed (the self-consumption rule
`SCFirst` / `SCNoImportFuture`, the TSO-service code `RollSvcMode`, pro-rata, the `RunTR4_*` tests). On top of
that, these changes were applied in order:

| Date | Folder (Tulio's local `experiments/`) | Added |
|---|---|---|
| 30 Sep | `2026-09-30_sc-safe-FOR` | test runner `SCT_RunBed`, logs (`scripts/lineage/2026-09-30_sc-safe-FOR_changes.md`) |
| 2 Oct | `2026-10-02_pv-curtailment` | PV-cut variable in the FOR (`add_pvc.py`) |
| 2 Oct | `2026-10-02_pv-curtailment-surplus` | cut only the surplus (`add_surplus.py`) |
| 2-3 Oct | `2026-10-02_tso-request-stress` | TSO requests, coordinated P1 (`add_srq.py`) |
| 4 Oct | `2026-10-04_for-requests` | FOR-first requests and delivery by mixing (`add_frq.py`, `add_planlog.py`) |
| 5 Oct | `2026-10-05_no-export-pv-refill` | rule (iii), 0.01 W rule, end/anchor options (`add_zx*.py`) |
| 5 Oct | this folder | batteries first, coordinated P1 for rule (iii), retries, runner `PV2_Run` (`add_pv2.py`, `add_pv2_fix.py`) |

Each patch script edits the copy of the model in its own folder and checks that every replacement matches
exactly once. They are here to show what was done, not to be run again.

## 9. Limits

- One clear-sky day, TR4 only, persistence forecast.
- `FairMode = 0` in all results.
- P1 solved with the network (the paper presents P1 behind the meter).
- The FOR is computed only at request half-hours (a test showed the same outcomes).
