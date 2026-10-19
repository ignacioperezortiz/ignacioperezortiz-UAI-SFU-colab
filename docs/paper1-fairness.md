# Paper-1 fairness: implementation, the headroom box versus the throughput penalty, and the tests

Branch `feature/paper1-fairness`, created from `feature/paper1-model` (October 2026). This document covers three things:
- how the fairness subsection of the paper (methodology §III-C, eqs. 12–16) is implemented in `MainProject/OPF.ams`;
- why the headroom box (eq. 13) is added **and** the slot throughput penalty κ is kept;
- the tests that validate both.

Tests T0–T6 (section 5) ran on 10–11 Oct 2026 on commit 866c053 (TR4). T5 found that HP clashes with the self-consumption guarantee, which led to the effective headrooms below; T7 (commit 2f68674) tests them. All tests pass; section 6 gives the results and the reference data to validate a merge against.

## 1. What the paper says, and where it is in the code

Each quantity below refers to the flexibility slot `PeriodMaxP` (= 2 in the rolling flow) of the current rolling step.

| Paper | Code (declaration section `FairnessPaper1`) |
|---|---|
| ΔP_s = P^b_{s,k+1} − P^{b,sc}_{s,k+1} | `BattP_Balance(bat,PeriodMaxP) - FairPsc(bat)`. `FairPsc` is captured at every step from the committed baseline, after the network check (right after `RollSOCnext`). |
| U_s, D_s (eq. 12) | Defined parameters `FairU = [FairPhi − FairPsc]⁺` and `FairD = [FairPsc − FairPlo]⁺`. `FairPhi`/`FairPlo` are the highest and lowest slot power from `RollSOCnext`: the physical envelope `FairPchMax`/`−FairPdisMax`, or the effective one (below) when `FairEffHead = 1`. They are snapshotted in `FairUGen`/`FairDGen` when the sweep instance is generated. |
| Box −D_s ≤ ΔP_s ≤ U_s (eq. 13) | `FairBoxRow(bat)`, a ranged row in kW, active when `FairBox = 1` and `FairActive`. |
| CP, ΔP_s = ζ_G P̄_s (eq. 14) | `FairCP(bat)` with `FairZcp(group)`. |
| HP, ΔP_s = ζ↑U_s − ζ↓D_s, ζ↑ + ζ↓ ≤ 1 (eq. 15) | `FairHP(bat)` and `FairSimplex(group)`, with `FairZu` and `FairZd`. |
| HB, −εD_s ≤ ΔP_s − (ζ↑U_s − ζ↓D_s) ≤ εU_s (eq. 16) | `FairHB(bat)` (ranged) and `FairSimplex(group)`. |
| Groups: intra-aggregator or network-wide | `FairGroup(bat)` = `BattAgg(bat)` (scope 1), or the first element of `Aggregators` for every battery (scope 2, logged as `ALL`). |
| Rows only in the directional solves | Gate `FairActive`: 0 in P1, the network check and every self-consumption re-plan; 1 in the sweep. |

**Units.** All rows are written in kW (×1000), as `ZX_SCTight` is. The production `Feasibility_Tolerance` is 1e-3, which on a p.u. row would be 1 kW per battery.

**SOC ceiling.** `FairPchMax` uses the physical SOC ceiling: the minimum of the ceiling in force and `BattSOCmaxPhys`. The GMP sweep raises `BattSOCmax` by `RollSOCCeilTol` only so that the frozen slot-1 dispatch fits; the box must not offer that tolerance at slot 2. As a result:
- a full idle battery has U = 0 exactly, as in the paper;
- the box matches the SOC cap that delivery applies, so netting shaves at most ~0.01 W.

**Effective headrooms (`FairEffHead = 1`, paper flow).** With physical headrooms, T5 found the following on `WC_EXPORT` with HP intra:
- the self-consumption guarantee (`ZX_SCTight`) keeps a battery with a low SOC from charging less at slot 2, because its house would then buy later, but its physical D is still > 0;
- HP can then use ζ↓ only by mixing in ζ↑, so the batteries with a large U charge during an export request: 41 of 84 group-corners were mixed at 180°;
- 21 % less was served, and 21 houses bought inside the requested half-hours. Making the guarantee slack (`SCAlpha=99`) removed all of it.

`FairEffHead = 1` measures U and D to the SOC band [`FairSOCLo`, `FairSOCHi`] at the end of the slot from which the prosumer can still meet everything that binds it later in the window:
- its SOC limits;
- the guarantee: at every t > k+1 the battery must cover its own net load down to the baseline's import, `SCImpRef + SCAlpha·P̄`;
- the cyclic end-of-window band (and `ZX_EndCap` when on).

`FairEffBand` walks the window backwards, one slot at a time and per battery, after `FairPsc` is captured. The walk is exact for a single prosumer and ignores the network, so the band contains every slot-2 point the sweep can reach. Three consequences:
- the box (13) it implies is redundant in the reference FOR, which must not change;
- U and D can only shrink;
- HP and HB now split only what each prosumer can actually give.

The walk covers rule (i) only (PV never cut) and one battery per bus and phase. It halts otherwise.

**Knobs.** All of them can be set on a job line as `NAME=VALUE`.

| Parameter | Values | Paper-flow default (PV2_Run) |
|---|---|---|
| `FairCrit` | 0 none (reference FOR), 1 CP, 2 HP, 3 HB | 0 |
| `FairScope` | 1 intra-aggregator, 2 network-wide | 1 |
| `FairEps` | ε in [0,1] (HB) | 0 |
| `FairBox` | 1 = box in every directional solve | **1** |
| `FairEffHead` | 1 = effective headrooms, 0 = physical (commit 866c053) | **1** |
| `P2SlotPen` | κ override: < 0 keeps 0.2 | −1 (κ = 0.2) |
| `FairAllowNoBox` | 1 lets CP/HB run without the box (diagnostic only) | 0 |
| `FairLogOn` | 1 writes the logs of section 4 | 1 |

`FairBox=0` on a job line reproduces Tulio's 9-Oct model exactly: without the box or a criterion, the band is only logged. `FairEffHead=0` reproduces commit 866c053. With no requests, the box is never generated at all, because P2 only runs when the TSO asks.

**The 2026-08 criteria** (`FairMode` 1–4, section `Fairness`) are left untouched. The wrappers that reproduce earlier evidence use them, including the κ evidence (`RunTR4_ThruPen*` ran with `FairMode = 2`). They cannot be combined with the new rows (`RunFOR_Rolling` halts), and the paper flow refuses `FairMode ≠ 0`.

**Guards.** `RunFOR_Rolling` halts if any of the following holds:
- FairCrit, FairScope, FairEps or FairBox is out of range;
- FairMode ≠ 0 or FairBaseline ≠ 0 together with FairCrit or FairBox;
- RollExecCap = 1 with FairCrit or FairBox;
- CP or HB is selected without the box (unless FairAllowNoBox = 1);
- the shared-instance GMP path (`RollGMPBaseline = 1`) would be taken, because its matrix is generated before the baseline that defines FairPsc;
- a battery has BattMaxP ≤ 0;
- under intra-aggregator scope, a battery has no aggregator;
- `FairEffHead = 1` with PV cut (`ZX_On` or `PVC_On`), or with two batteries on one bus and phase.

## 2. Does the box replace the throughput penalty κ? No. Both stay.

This was analysed on 9–10 Oct 2026 by two independent reviewers: a validator and an adversarial reviewer. Two rounds of analysis were followed by a review of the implementation, and the decision was reached by consensus. The working files are in the session scratchpad (`fair_impl/`).

The penalty κ is `FOR_ThruPenSlot = 0.2` in P2's objective, μ^f in the paper.

1. **Neither is needed for convexity.** CP, HP and HB are linear in the P2 variables and the factors, because U, D and P_sc are parameters fixed before the instance is generated.
2. **The box removes the slot-k+1 net phantom exactly, and only on the import side.** The export side is already implied by the model's own rows. The phantom is the absorption that simultaneous charge and discharge make possible in the convex model: (1 − η²)·P̄ ≈ 0.36 kW for a full battery, ~16.6 kW for the TR4 fleet.
3. **Per battery, κ = 0.2 removes that phantom too**, whenever one unit of slot-2 net power is worth less than 19κ in the objective.
4. **Under CP, κ fails and the box does not.** The group coupling multiplies the value of the phantom. It survives κ when n/m > 18κ/(cos θ − κ), where n is the group size and m the number of full batteries. At θ = 0 that means more than ~4.5 batteries per full one. On TR4 (~15 per aggregator) one full battery unlocks ~5.4 kW of fake import. Under HB, the box is also not implied when ζ↑ + ε > 1. **So the box is required by the fairness criteria.**
5. **The box cannot stop energy disposal at slot k+1, and κ ≥ ~1/19 does.** Disposal means the same net power with gross cycling, leaving a lower SOC at the end of the slot. It enlarges the import side when a later slot is forced to absorb, e.g. midday voltage limits with PV never curtailed, which is the paper's regime. Two examples:
   - one-battery example: box with κ = 0 gives 0.706 kW, against 0.384 kW for the binary (complementarity) model;
   - adversarial example: 1.979 kW against 1.800 kW.

   **A small μ^f (1e-3 to 1e-2) does not block this. Hence κ stays at 0.2.**
6. **κ also removes the degenerate charge/discharge split.** With κ = 0 the barrier returns cycling corners. That would make the least-throughput triangle of the delivery arbitrary, make the NC RESCUE exact combination execute cycling, and pollute the logs.
7. **The cost of κ is a known, conservative distortion of about κ²sin²θ/2:** 1–3 kW in oblique directions on TR4. This matches Tulio's ~1.4 kW RMS against the MIQCP reference. κ = 0.1 would cut it about fourfold, but amplified disposal would then survive from a ratio of 2 instead of 4.5, so κ = 0.1 is a test item only.
8. **Not cut by any option:** energy disposal at later slots (t ≥ k+2), which no formulation here penalises. It matters most where the midday voltage limit binds (TR6, whole feeder).

**For the paper**, outside the fairness subsection:
- The P2 objective keeps μ^f, but its value is 0.2, so "small μ^f" is inaccurate.
- The text should state μ^f's two roles: blocking disposal and the degenerate split.
- The text should state that the FOR is slightly conservative because of it.
- (13) is what makes the fairness criteria physical.
- The limitation in item 8 should be stated.

**Other paper-flow details.**
- PV2_Run pins `RollExecCap := 0`. Some older wrappers "restore" it to 1, which would trip the guard.
- With fairness and the box off, nothing new is evaluated except the logs that `FairLogOn` writes.
- **Interactive sessions.** If PV2_Run halts midway, FairBox, FairLogOn and P2SlotPen keep their paper-flow values in that AIMMS session. A later SCT wrapper would then inherit P2SlotPen. Restart the session, or reset those parameters, before running anything else. Runner jobs are fresh sessions, so this does not affect them.
- **Diagnostic overrides.** With FairBox = 1, `SOCCeilOverride` values above the physical ceiling (e.g. 1.0001, 1.05) no longer widen slot 2, because the box caps at the physical ceiling.
- **Offer log.** With `FairLogOn = 0` and `RollOfferLog = 1`, the psc/U/D columns of the offer CSV can carry values from an earlier run in the same session. This is cosmetic.
- Known hazard in the existing code, not touched here: with `RollSvcMode = 4` the commitment block (replay branch) would run a pinned MinImports if a session were reused after a delivered request. `RollSvcReqP` is never emptied. Each runner job is a fresh AimmsCmd session, so it does not arise in the paper runs.

## 3. Behaviour that changes with the new criteria

- **S0 is fair now.** With ΔP = 0 and zero factors it satisfies every criterion, unlike under the 2026-08 rules. A request that mixes S0 is therefore fair too.
- **Delivery stays fair.** A convex combination of fair corners satisfies the criterion with the combined factors; under HB the band combines convexly as well. Netting does not change ΔP. The SOC cap at execution may shave at most ~0.01 W per battery, because the box already uses the physical ceiling.

## 4. Logs (FairLogOn = 1)

- **`FOR_rolling_crit<tag>.csv`.** One row per (step, direction, group), with these columns:
  - criterion, scope, ε, box and κ;
  - status;
  - n_batt;
  - ΣΔP, ΣU and ΣD in kW;
  - the factors zcp, zu and zd;
  - `cp_dev_max`, which is 0 under CP;
  - `rule_res_max_kW`, which is 0 under HP;
  - `hb_viol_max_kW`, which is 0 under HB and HP;
  - the box violations, which are 0 with the box;
  - `n_cyc` and `cyc_kW`: batteries cycling in the slot above 1 W. With κ = 0.2, a remaining cycle is disposal that pays, i.e. a corner where the region may be optimistic;
  - `thr_kW`: the group's slot throughput. κ times its sum over groups is the penalty term of the objective;
  - `cp_spread`, written for every criterion: half the range of ΔP/P̄ over the group. It equals min over ζ of max|ΔP/P̄ − ζ|, so it is 0 under CP and, for the reference FOR, its distance from CP.

  Each criterion column, and each factor, is written only under its own criterion and left empty otherwise. Without rows the factors are 0, and the column would report max|ΔP| instead of a distance from the criterion.

  A direction that did not solve gets its status and empty columns.
- **`FOR_rolling_offer<tag>.csv`** (RollOfferLog = 1) gets three more columns: `psc_pu`, `U_pu` and `D_pu`.
- **`SCT_info<tag>.txt`** gets three new kinds of line:
  - `FAIR settings` (written by SCT_RunBed);
  - `FAIRCLIP`, at steps where the baseline lies outside the envelope the sweep uses by more than 0.1 W. It is computed from the snapshots, where the box is built, and is the only visible sign of a phantom baseline, e.g. a network-forced P1 re-solve that cycles;
  - `FAIRBASE`, when the committed baseline that defines FairPsc is not optimal;
  - `FAIREFF` (`FairEffHead = 1`), at every step. It gives the batteries whose D or U the band cuts by more than 1 W, how many are left with D below 1 W, the total cut in kW, and the baselines outside the band (expected 0: a count means the walk is stricter than the model);
  - `FAIRDELIV`, after each delivered request. It reports the residual of the criterion and the box violation, before and after netting/capping, plus the shave.
- **SWEEPDIAG**, when a direction fails, also probes "fairness rows off". Its SOC-ceiling probes also switch the box off.

## 5. Tests (to run in order; TR4 first)

Before starting:
- Close AIMMS (and any AimmsCmd).
- Check that `git status` is clean on `feature/paper1-fairness`, and write down `git rev-parse --short HEAD`.
- The PC should not be running other heavy jobs.

All runs use the paper runner (`scripts/paper1/run_paper1.py`; one lane = one AIMMS session = one licence seat). The queues are in `scripts/paper1/queues/fair_*.txt`.

### T0. Compile and licence (5 min)
Copy the project to a scratch folder and run `AimmsCmd --run-only MainInitialization` on the copy (20 s; `docs/` or the personal AIMMS notes give the exact command).
- **Pass:** no compile error in `log/aimms.err` or `log/messages.log`.
- **If AIMMS rewrites `OPF.ams` when the project is opened in the GUI:** commit that alone as `chore: AIMMS reformat on open (no semantic change)`, as the model guide asks.

### T1. Bit-identity with the box off (~2 × 15 min, two lanes)
Run `SPD_SMOKE free_today a2x4p8fin TR4` twice:
- on Tulio's branch: `git worktree add ../paper1-model-orig origin/feature/paper1-model`, then from that worktree `python scripts/paper1/run_paper1.py prepare O1 --work ../paper1-runs-orig` and `... lane O1 scripts/paper1/queues/check_tr4.txt --work ../paper1-runs-orig` (only the SPD_SMOKE line is needed);
- on this branch with `FairBox=0`: `prepare N1`, then `lane N1 scripts/paper1/queues/fair_t1_identity.txt`.

Compare `FOR_rolling*.csv`, `FRQ*.csv`, `SCT_exec*.csv` and `FOR_rolling_svc*.csv` row by row.
- **Pass:** identical apart from timing columns, and 3 requests served.
- This proves the new code is inert when switched off.

### T2. Reference FOR: box on against box off (~2 × 30–45 min)
Run `REF_SWEEP free_today a2x4p8fin TR4` with `FairBox=1` (the default) and with `FairBox=0`. Queue: `fair_t2_box.txt`.

Compare the 12 corners of all 48 steps.
- **Pass (box on):**
  - every status is Optimal;
  - `box_*_viol_kW` = 0;
  - any difference from box off is only toward less import, at steps with full batteries.
- **Report:**
  - the largest |ΔP| and |ΔQ| per step;
  - `n_cyc`/`cyc_kW` with κ = 0.2 (expected ≈ 0);
  - the FAIRCLIP count (expected 0).

### T3. The role of κ (diagnostic, ~2 × 30–45 min)
Run `REF_SWEEP … TR4` with `FairBox=1 P2SlotPen=0`, and with `FairBox=0 P2SlotPen=0`. Queue: `fair_t3_kappa.txt`.
- **Expected:**
  - box + κ = 0: cycling corners (`n_cyc` > 0), and import corners ≥ those of T2 where a later slot is forced to absorb;
  - no box, κ = 0: the import-side phantom at steps with full batteries (up to ~16 kW).
- This is the empirical side of section 2.

### T4. Criteria on the reference sweep (6 × 30–45 min; parallel lanes if seats allow)
Run `REF_SWEEP … TR4` with `FairCrit=1|2|3` × `FairScope=1|2`, using `FairEps=0.1` for HB. Queue: `fair_t4_criteria.txt`.
- **Pass:**
  - `cp_dev_max` ≈ 0 (CP), `rule_res_max_kW` ≈ 0 (HP) and `hb_viol_max_kW` ≈ 0 (HB) in every solved corner;
  - box violations = 0;
  - network-wide never better than intra-aggregator in the directional objective. Direction by direction, (proj from `FOR_rolling.csv`) − κ·Σ thr_kW (from `FOR_rolling_crit.csv`) under network-wide must not exceed the same quantity under intra-aggregator, up to solver tolerance. The exchange alone may differ by at most κ times the throughput difference;
  - HB(0.1) between HP and the reference.
- **Report:**
  - the corners that fail (count per criterion and scope);
  - the FOR area against T2.

### T5. Delivery and self-consumption with fairness (two-day, ~16 min each)
Run `WC_EXPORT`, `WC_IMPORT` and `REF` (`free_today a2x4p8fin2 TR4`), each with `FairCrit=2 FairScope=1` and with `FairCrit=0`. Queue: `fair_t5_delivery.txt`.
- **Pass:**
  - `FAIRDELIV` res_pre ≈ 0 and res_post ≤ 1e-4 kW (0.1 W) per battery. That is the corners' own solver tolerance (T4: ≤ 1e-4 kW), and netting adds nothing to it. The 2e-5 kW of the first version was below the solver tolerance;
  - `EXECFAIL` = 0;
  - `analyze_paper1.py` shows no extra purchase beyond the REF of the same settings (Tulio's guarantee unchanged), and no house buys more inside the requested half-hours than without the criterion;
  - day-2 lines present.

### T6 (optional). κ = 0.1 with the box
Run `REF_SWEEP … TR4 P2SlotPen=0.1`, and the same with `FairCrit=2`.
- Measure the distortion against T2, and `n_cyc`, which reveals disposal that pays at κ = 0.1.

### T7. Effective headrooms (`FairEffHead=1`)
Queue: `fair_t7_effhead.txt`. It runs the following:
- `REF_SWEEP` with `FairCrit=0`. **Pass:** the FOR equals T2 (box on) up to solver tolerance, and `FAIREFF` reports base_out = 0;
- `REF_SWEEP` with CP, HP and HB × intra and network-wide. **Pass:** the T4 criteria. CP equals T4, because the box is redundant there too. Report the area against T2, and the mixed group-corners (ζ↑ > 0 and ζ↓ > 0) against T4;
- T5 with HP intra (`WC_EXPORT`, `WC_IMPORT`, `REF`). **Pass:** the T5 criteria, including no extra purchase inside the requested half-hours;
- `REF_SWEEP` HP intra with `FairEffHead=0`. **Pass:** equal to T4 (the switch is inert when off).

**When reporting a number,** write down the commit hash and that the tree was clean (model guide, section 10).

## 6. Results (10–11 Oct 2026) and the reference to validate against

All runs are TR4, `free_today`, lane N2 (N3 for the guarantee pair), with the tree clean. One-day sweeps have 48 steps × 12 directions = 576 solves.

| Test | Result |
|---|---|
| T0 | compiles |
| T1 | `FairBox=0` is bit-identical to Tulio's 9-Oct model; 3 requests served |
| T2 | 576/576 Optimal with the box; the box only removes the tolerance band (~0.9 W per battery) |
| T3 | box + κ = 0: cycling in 505/576 solves (up to 101 kW), FOR +1.01 %; no box + κ = 0: phantom absorption, area +8.04 % (max +19.86 % at 17:30), +16.38 kW at 0° |
| T4 | all six criteria × scope: 576/576 Optimal, residuals ≤ 1e-4 kW, box violation 0, no cycling; nestings (nw ≤ intra, HP ≤ HB ≤ ref) within 1 W |
| T5 | delivery correct (28/28 and 33/33 requests), but HP with physical headrooms serves 675.2 instead of 854.3 kWh on `WC_EXPORT` and 22 houses buy more inside the requested half-hours |
| T6 | κ = 0.1: no cycling; FOR +0.71 % against κ = 0.2 |
| T7 | `FairEffHead=1`: reference FOR equal to T2 (area ratio 1.0000, ≤ 4 W per corner); `FairEffHead=0` reproduces T4 bit for bit; HP on `WC_EXPORT` serves 854.3 kWh with 0 houses buying more inside the requested half-hours |

**FOR area against the reference (mean over 48 steps):**

| | intra, effective (T7) | intra, physical (T4) | network-wide, effective | network-wide, physical |
|---|---|---|---|---|
| CP | 51.48 % | 51.48 % | 40.27 % | 40.27 % |
| HP | 98.71 % (min 93.70) | 73.83 % | 98.58 % (min 92.52) | 63.42 % |
| HB (ε = 0.1) | 99.83 % | 82.20 % | 99.77 % | 73.72 % |

**The self-consumption guarantee** (`WC_EXPORT`, two days, `SCAlpha=0` against `SCAlpha=99`): 854.3 against 993.5 kWh of export served. Relaxed, all 46 prosumers buy more than 10 Wh more later (98.8 kWh for the fleet, worst 3.48 kWh). This pair used a diagnostic copy of the model in which PV2_Run does not overwrite `SCAlpha` and `RollOfferLog` after reading scenario.txt, so it cannot be reproduced from the repo as is.

**Reference data:** `results/paper1-fairness-2026-10/` holds compact JSON files extracted from these runs, with a README giving the provenance of each file. `scripts/paper1/check_fairness_reference.py` recomputes the same quantities from a lane's `FOR_rolling*` outputs and compares them with the reference, within stated tolerances. It is a draft that has not been tested yet: validate it on the N2/N3 lanes before relying on it. Until then, compare by hand against the JSON files and the tables above.
