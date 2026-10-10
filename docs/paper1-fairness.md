# Paper-1 fairness: implementation, the headroom box versus the throughput penalty, and the tests

Branch `feature/paper1-fairness`, created from `feature/paper1-model` (October 2026). This document covers three things:
- how the fairness subsection of the paper (methodology §III-C, eqs. 12–16) is implemented in `MainProject/OPF.ams`;
- why the headroom box (eq. 13) is added **and** the slot throughput penalty κ is kept;
- the tests that validate both.

**No optimisation has been run with this code yet.** Section 5 lists the tests to run before any number is used.

## 1. What the paper says, and where it is in the code

Each quantity below refers to the flexibility slot `PeriodMaxP` (= 2 in the rolling flow) of the current rolling step.

| Paper | Code (declaration section `FairnessPaper1`) |
|---|---|
| ΔP_s = P^b_{s,k+1} − P^{b,sc}_{s,k+1} | `BattP_Balance(bat,PeriodMaxP) - FairPsc(bat)`. `FairPsc` is captured at every step from the committed baseline, after the network check (right after `RollSOCnext`). |
| U_s, D_s (eq. 12) | Defined parameters `FairU`, `FairD`, built on `FairPchMax`/`FairPdisMax`. They come from `RollSOCnext` and the SOC limits in force when the sweep instance is generated, and are snapshotted in `FairUGen`/`FairDGen`. |
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

**Knobs.** All of them can be set on a job line as `NAME=VALUE`.

| Parameter | Values | Paper-flow default (PV2_Run) |
|---|---|---|
| `FairCrit` | 0 none (reference FOR), 1 CP, 2 HP, 3 HB | 0 |
| `FairScope` | 1 intra-aggregator, 2 network-wide | 1 |
| `FairEps` | ε in [0,1] (HB) | 0 |
| `FairBox` | 1 = box in every directional solve | **1** |
| `P2SlotPen` | κ override: < 0 keeps 0.2 | −1 (κ = 0.2) |
| `FairAllowNoBox` | 1 lets CP/HB run without the box (diagnostic only) | 0 |
| `FairLogOn` | 1 writes the logs of section 4 | 1 |

`FairBox=0` on a job line reproduces Tulio's 9-Oct model exactly. With no requests, the box is never generated at all, because P2 only runs when the TSO asks.

**The 2026-08 criteria** (`FairMode` 1–4, section `Fairness`) are left untouched. The wrappers that reproduce earlier evidence use them, including the κ evidence (`RunTR4_ThruPen*` ran with `FairMode = 2`). They cannot be combined with the new rows (`RunFOR_Rolling` halts), and the paper flow refuses `FairMode ≠ 0`.

**Guards.** `RunFOR_Rolling` halts if any of the following holds:
- FairCrit, FairScope, FairEps or FairBox is out of range;
- FairMode ≠ 0 or FairBaseline ≠ 0 together with FairCrit or FairBox;
- RollExecCap = 1 with FairCrit or FairBox;
- CP or HB is selected without the box (unless FairAllowNoBox = 1);
- the shared-instance GMP path (`RollGMPBaseline = 1`) would be taken, because its matrix is generated before the baseline that defines FairPsc;
- a battery has BattMaxP ≤ 0;
- under intra-aggregator scope, a battery has no aggregator.

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
  - `FAIRDELIV` res_pre ≈ 0 and res_post ≤ 2e-5 kW (0.02 W) per battery;
  - `EXECFAIL` = 0;
  - `analyze_paper1.py` shows no extra purchase beyond the REF of the same settings (Tulio's guarantee unchanged);
  - day-2 lines present.

### T6 (optional). κ = 0.1 with the box
Run `REF_SWEEP … TR4 P2SlotPen=0.1`, and the same with `FairCrit=2`.
- Measure the distortion against T2, and `n_cyc`, which reveals disposal that pays at κ = 0.1.

**When reporting a number,** write down the commit hash and that the tree was clean (model guide, section 10).
