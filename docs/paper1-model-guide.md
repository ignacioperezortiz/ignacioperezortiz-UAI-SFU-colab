# Paper-1 model: what it is, how to run it, the whole feeder, and where fairness goes

Branch `feature/paper1-model`, October 2026. Written for Ignacio by Tulio (with Claude). This is the model behind
Section IV of paper 1 (self-consumption first, TSO–DSO flexibility from the FOR). It is shared so that you can
(1) run it, (2) run the **whole feeder** on your machine, and (3) add the **fairness** part on top of it.

---

## 1. What the model does (paper-1 flow)

One simulation = one or two days of 48 rolling half-hour steps (PV2_Run). At every step k:

1. **P1, behind the meter.** Each prosumer's self-consumption plan for the next 24 h (batteries only; PV is
   **always exported, never curtailed**; inverter reactive power 0 in P1). No network in this solve.
2. **Network check (DSO).** P1's first two slots are fixed and the network is added (`MinImports` with the
   `NetworkModel`). If the plan breaks a limit, P1 is solved again with the network. This runs at every step.
3. **FOR only when the TSO asks.** If the TSO requests flexibility for slot k+1, the FOR at the interface is built:
   12 directions (P2), each with the **self-consumption guarantee**: no house may buy more in any later slot
   than P1 planned (0.01 W tolerance, `SCTight = 1`). Otherwise no FOR is computed (saves most of the time).
4. **Delivery without a new optimisation.** The TSO picks a point inside the published FOR. The set-points are
   the convex combination of the stored corner solutions (only corners, the least-throughput triangle:
   `SPD_CornersOnly = 1`), netted and capped at the SOC limits, executed in the next step.
5. **Plan once.** Slot k executes what P1 planned for it at step k-1 (`SPD_FixSlotK = 1`), unless a service runs.
6. **Two days** (`SPD_TwoDays = 1`): day 2 continues day 1 (same profiles) without requests, so effects that cross
   midnight are counted.

Where it lives in `MainProject/OPF.ams`: procedure **`PV2_Run`** (entry point, reads `scenario.txt`), which calls
`SCT_RunBed` (network scope) and then **`RunFOR_Rolling`** (the rolling loop: P1, network check, sweep, delivery).
Search for these markers inside `RunFOR_Rolling`:

| Marker in the code | What it is |
|---|---|
| `SPEED TEST (SPD_P1NoNet = 1)` | the network check after P1 |
| `NC RESCUE` | what happens when the check fails and a committed service is in slot 1 (see section 7) |
| `GMP path: hoist the direction-INDEPENDENT setup` | generation of the sweep instance (fairness rows included, `FairActive = 1`) |
| `AsynchronousExecute` | the parallel sweep (RollAsyncK directions at a time) |
| `FOR-FIRST REQUEST (SRQ_Mode = 2)` | delivery: triangle, weights, set-points |
| `DECISION TEST (SPD_CornersOnly = 1)` | rebuilding a request from corners only |
| `TWO DAYS` | day 2 |

The settings are written by the runner into `scenario.txt` (see `python scripts/paper1/run_paper1.py show ...`):

| Parameter | Value | Meaning |
|---|---|---|
| `PV2_Regime` | 0 | PV always exported, never cut; FOR = batteries only |
| `SPD_P1NoNet`, `SPD_P1Q0` | 1, 1 | P1 behind the meter, inverter Q = 0 in P1 |
| `SPD_NCAll` | 1 | network check at every step |
| `SPD_FixSlotK` | 1 | plan once |
| `SPD_CornersOnly` | 1 | delivery from corners only |
| `SCTight` | 1 | guarantee rows in kW with 0.01 W tolerance |
| `SPD_TwoDays` | 1 for `...fin2` | two days |
| `RollAsyncK`, `RollAsyncThreads`, `SPD_P1Threads` | from the speed name | parallel directions, threads per direction, threads for P1/check |
| `SPD_Trafo` | `TR4` (default), `TR9`, `TR3,TR4`, `ALL` | network in detail; `ALL` = whole feeder |

## 2. What changed against `main`

Only `MainProject/OPF.ams`. Use `git diff --histogram origin/main -- MainProject/OPF.ams` to read it:
**+7,599 / −19 lines** (the default diff algorithm shows a much larger, misaligned diff).

- The additions are new parameters, procedures and code paths for the paper-1 flow (self-consumption guarantee,
  TSO services, FOR-first delivery, P1 behind the meter, network check, plan once, two days, rescue,
  diagnostics). New switches default to the old behaviour.
- The 19 changed lines are inside `RunFOR_Rolling` (SOC carried between steps clamped inside its bounds, the
  executed slot-1 dispatch capped to the SOC envelope, slot-1 reactive power frozen in the sweep after a service,
  two objective terms). **The old production procedures (`RunTR1`..`RunTR9`, `RunFullFeeder_*`) were not re-run
  with this model**, so their published numbers in `results/` are not re-validated: expect at most
  tolerance-level differences, but check before using them.
- No new input data: case `v1_baseline` (the three files in the repository root, unchanged).

## 3. Setup

- AIMMS 26.x with CPLEX 22.1. Tulio's runs used AIMMS 26.3.2.1; `OPF.aimms` on `main` says 26.2.3.3. If your AIMMS
  updates the library versions in `OPF.aimms`, do not commit that change. With an AIMMS newer than the version in
  `OPF.aimms`, AimmsCmd can crash on exit after a complete run, so the runner sees no `Return value = 0`: open the
  project once in that AIMMS, keep the updated `OPF.aimms` outside Git and pass it to `prepare --project <file>`.
- `Database.mdb`, `Database.dsn`, `OpData.xls` in the repository root (as always). SHA-256 prefixes of the files
  Tulio used: `Database.mdb` 8b474da7f5b57956, `OpData.xls` daf841adc4db08f3.
- Python 3 with `pandas` and `numpy` for the runner and the analysis.
- The runner copies the model into one folder per lane, outside the repository (default `../paper1-runs/`), so
  outputs never land in Git. One lane = one AIMMS session = one licence seat.

## 4. First: a check on TR4 (about 12 minutes)

```bash
python scripts/paper1/run_paper1.py prepare L1
python scripts/paper1/run_paper1.py lane L1 scripts/paper1/queues/check_tr4.txt
python scripts/paper1/analyze_paper1.py
```

Expected for `REF free_today a2x4p8fin2 TR4` (reproduced exactly from this branch with this runner on Tulio's PC,
9 Oct, 16 min alone; 11.6 min on 3 lanes in the original batch):

| | day 1 | day 2 |
|---|---|---|
| batteries | 46 | 46 |
| purchases (sum of `imp1_kWh` in `SCT_exec_*.csv`) | 12.285 kWh | 18.538 kWh |
| exports (sum of `exp1_kWh`) | 801.901 kWh | 824.114 kWh |
| network checks / failed (`SCT_info_*.txt`) | 48 / 0 | 48 / 0 |

`SPD_SMOKE` (requests at 12:00–13:00, stops after step 26) must end with `Return value = 0` and 3 requests in
`FRQ_*.csv`.

## 5. The whole feeder

```bash
python scripts/paper1/run_paper1.py prepare W1
python scripts/paper1/run_paper1.py lane W1 scripts/paper1/queues/whole_feeder.txt
```

The queue runs, in order: `WF_PLUMB` (P1 + network check at the first 2 half-hours, no FOR), `SPD_SMOKE` (26
half-hours, the first FORs at full scale), then the paper runs (REF, R04_sun, WC_EXPORT, WC_IMPORT, EDGE_SUN over two
days) and REF_SWEEP (FOR at every half-hour of one day). **Look at the first two before letting the rest run**:
they give the time per step and the memory.

- **Speed name.** `a3x5p16fin2` = 3 directions in parallel x 5 CPLEX threads each, 16 threads for P1 and the
  network check. Your `docs/parallel-sweep-memory.md` found 3 x 5 to be the split that fits on your machine at full
  scale; adjust if needed (`a0x16p16fin2` = directions one after the other).
- **Scale.** 1,216 batteries, about 7.5 M rows x 6.1 M columns per sweep instance (~0.9 GB); in August a
  sequential full-feeder sweep took 344 s per direction on average, plus ~34 min of matrix generation per period
  (`results/full_feeder_2026-08/README.md`). In this flow there is also one network check per step (a full-network
  solve), and the FOR is built only at requested steps.
- **On Tulio's PC (i9-14900, 32 GB), `WF_PLUMB`:** 1,216 batteries, P1 Optimal and network check passed at both
  steps; step 1 took 78 min (includes loading the data), step 2 took 31 min, almost all in one single-threaded
  AIMMS phase (generating the full-network matrix of the check), peak ~10.6 GB. So budget about 30 min per step
  before any FOR: a two-day run without requests is about 2 days of wall clock on such a PC.
- **Watch for a stall**, as in `docs/whole-feeder-production.md` §3: `FOR_rolling_progress<tag>.txt` and
  `SCT_exec<tag>.csv` in the lane folder must keep growing; there is no resume (a stopped job restarts at step 1).
  The August hang happened with `BaseNoNetwork = 1` and the parallel sweep, which is this flow (P1 behind the meter):
  if a stall appears, re-run with `a0x...` (sequential sweep) and tell Tulio.

## 6. Outputs and checks

Per job, in the lane folder (tag = `_<scenario>_<case>_<speed>_<network>[_extras]`, day 2 adds `_d2`):

| File | Content |
|---|---|
| `SCT_exec<tag>.csv` | per step and battery: status of P1, SOC, purchases/exports of slot 1, service flag |
| `FOR_rolling<tag>.csv` | every FOR corner built: P, Q, status, time, true voltage extremes |
| `FRQ<tag>.csv` | every TSO request: chosen point, corners used, weights, energy shaved |
| `FOR_rolling_svc<tag>.csv` | requested vs realised interface point at execution |
| `SCT_info<tag>.txt` | program type and solver (must be QCP + CPLEX 22.1), and the lines below |
| `done<tag>.txt` | `Return value = 0` when PV2_Run ended normally |

Lines to look for in `SCT_info`: `NETCHECK` (the check failed, P1 re-solved with the network: normal at midday on
TR2/TR9), `NCRESCUE` / `NCCLIP` (section 7), `EXECFAIL` (a committed service could not be executed: should be 0),
and the summary lines `SPEED settings`, `NC RESCUE`, `DECISION TEST`, `DAY 2`.

`python scripts/paper1/analyze_paper1.py` compares every pattern with the REF run of the same network and settings
and writes `paper1_summary.txt`: checks, requests served, worst house (extra purchase outside the requested
half-hours), fleet totals, FOR statistics of REF_SWEEP.

## 7. Known behaviours (found on TR9 and TR3, October 2026)

- **Rescue after a failed check.** If a request sits on the FOR edge at the 1.10 pu limit, netting and the SOC cap
  can push the executed point across the limit. The rescue then executes the exact corner combination, under the
  sweep's SOC ceiling and clipped to the SOC limits (`NCCLIP`, fractions of a Wh). On TR9 the realised point equals
  the requested one.
- **The FOR can collapse.** On TR3 under the import worst case (all batteries full from 07:00, PV never cut), some
  steps lose most corners: the voltage cap, full batteries, the end-of-window SOC band and the guarantee leave
  almost no room. Failed directions are dropped and counted ("FORs short"); the FOR is built from the corners found.
- **A purchase can move out of a requested half-hour.** On TR1 WC_EXPORT one house bought 110 Wh less in the last
  requested half-hour and 110 Wh more one hour later (P1 had planned it there). Its two-day total is unchanged; the
  analysis reports both views.

## 8. Fairness: where it goes

**Update (branch `feature/paper1-fairness`, 10 Oct 2026):** the paper's criteria are now implemented in section
`FairnessPaper1`, and `docs/paper1-fairness.md` explains the code, the decision and the tests:
- capacity-proportional, headroom-proportional and headroom band;
- intra-aggregator and network-wide scopes;
- the headroom box, eq. 13 of the methodology.

The job-line knobs are `FairCrit=1|2|3`, `FairScope=1|2`, `FairEps=…` and `FairBox=0|1` (1 by default in PV2_Run).
`FairBox=0` reproduces this branch's model exactly. κ = `FOR_ThruPenSlot` = 0.2 stays: the box does not replace it.
The paper flow (PV2_Run) refuses `FairMode ≠ 0`. The bullets below describe the 2026-08 rows, which are kept only for the
wrappers that reproduce earlier evidence.

- The fairness rows (`FairMode` 1–4, section `Fairness` in `BatteryModel`, `docs/formulation-opf-aggregators-fairness.pdf`)
  are already in the model. `FairActive` is 0 in P1 and the network check, and 1 in the sweep: the sweep instance is
  generated after `FairActive := 1`, so with `FairMode > 0` the 12 corners are the **fair FOR**.
- A job line can set it: `REF free_today a3x5p16fin2 ALL FairMode=2` (any `NAME=VALUE` field goes into
  `scenario.txt` and into the tag). PV2_Run does not reset `FairMode`; please check that nothing in your code path
  does.
- Delivery: a convex combination of fair corners keeps the proportional rule (each corner satisfies
  `BattP_Balance(b) = Zeta * FairCap(b)` with its own `Zeta`, so the combination does too, with the averaged
  `Zeta`). Corners only (`SPD_CornersOnly = 1`) keeps the no-request point S0 out of the combination, which matters
  because S0 is not fair. Netting, the SOC cap and the rescue can break exact proportionality by small amounts:
  worth measuring.
- Not used with fairness: `SPD_S0FOR` (requires `FairMode = 0`; it is off in the paper settings anyway).
- Open points to decide together: which mode for the paper (reference FOR vs fair FOR), and how to report
  directions that fail under fairness (in August m = 4 lost 34 of 576 vertices on the full feeder).

## 9. Measured with this branch

- TR4 REF: section 4. Nine transformers: Tulio runs `scripts/paper1/queues/tr_by_tr.txt` on his PC.
- Whole feeder `WF_PLUMB` on Tulio's PC (9 Oct, speed a2x4p8fin): Return value = 0 in 108.9 min; step 1 78 min,
  step 2 31 min; 1,216 batteries; P1 Optimal at both steps; 2 network checks, 0 failed; QCP + CPLEX 22.1.

## 10. Git steps for the fairness work (CONTRIBUTING.md)

```bash
git fetch origin
git checkout -b feature/paper1-fairness origin/feature/paper1-model
# open OPF.aimms in AIMMS, save without changes, close; if AIMMS rewrote OPF.ams:
git add MainProject/OPF.ams
git commit -m "chore: AIMMS reformat on open (no semantic change)"
# then small commits: feat: / fix: / docs:
git push -u origin feature/paper1-fairness
```

Open the PR against `feature/paper1-model` (or against `main` once that is merged) and tell Tulio. Keep run
outputs out of Git (they stay in `../paper1-runs/`); when you report a number, write down the commit hash
(`git rev-parse --short HEAD`) and that the tree was clean. Before editing a model section, tell Tulio which one:
he is not editing `OPF.ams` while you work on fairness; his runs use the model of this branch as it is.
