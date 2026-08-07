# TR9 rolling FOR under fairness — results

A fairness criterion (**C1: contribution proportional to installed capacity**) was added to the
rolling-horizon FOR and run at production scale on TR9. Three cases, same study case
(`v1_baseline`), same 48 periods × 12 directions = **576 vertices**:

| Case | Setting | Meaning |
|---|---|---|
| **A** | `FairMode = 0` | no fairness — the committed reference run |
| **L1** | `FairMode = 1` | proportional between **prosumers** |
| **L2** | `FairMode = 2` | proportional between **aggregators** |

All three are 576/576 Optimal. Fairness **changes results by design** — that is what is being
measured here. It must not be confused with `docs/rolling-for-performance.md`, whose claim is that
the sweep acceleration changed *no* results; that claim still holds, and case A below is the same
run it validates.

**Headline.** Level 1 costs a median **35.8 %** of the region's area; level 2 costs **2.3 %**. And
in the 16 target periods where at least one battery sits on its SOC floor, level 1 pins the whole
90-battery fleet to zero active power — the region collapses onto the all-idle point in the
maximum-export direction. Level 2 does not have that pathology.

**Scope.** `MainProject/OPF.ams`: a new `Fairness` declaration section inside `BatteryModel`, plus
the fairness gate and the new CSV writer inside `RollingHorizonFOR` (`RunFOR_Rolling`). Model side
committed as `4404d54` and `42f158c`.

**Formulation.** The full mathematical statement — sets, objective, network, batteries and the
fairness criterion, with everything new relative to the inherited model marked in red — is
`docs/formulation-opf-aggregators-fairness.pdf`. This document reports what that
formulation does when run; the PDF states what it is.

---

## 1. What is imposed

One free scalar per solve, `Zeta` — the fleet utilisation factor, dimensionless.

| Level | Constraint | Definition |
|---|---|---|
| 1 | `FairProportional_Prosumer` | `BattP_Balance(bat,PeriodMaxP) = Zeta*FairCap(bat)` for every battery |
| 2 | `FairProportional_Aggregator` | `sum_{i in a} BattP_Balance = Zeta * sum_{i in a} FairCap`, split inside `a` free |

Both act on the **active-power scalar at the service slot** (`PeriodMaxP`), which is the exchange
the FOR offers. The two are **mutually exclusive, not cumulative**: level 2 does not imply level 1.

- `FairCap(bat)` — the capacity share `s_i`, `Definition: BattMaxP(bat)`. The source of `s_i` is a
  single line, deliberately, so a different attribute is one edit away. `BattMaxP` is both the
  battery rating and the inverter S-circle radius in this model.
- `Zeta` removes exactly **one** degree of freedom. It is deliberately not written as `n-1` pairwise
  equalities, which would remove `n-1` and roughly double the apparent cost of fairness.
  `Zeta = 0` (everyone idle) is always feasible, so C1 contracts the FOR and can never make it
  infeasible.
- The section is declared in **`BatteryModel`, not `NetworkModel`**, so it survives
  `IncludeNetworkConstraints = 0`: fairness is an allocation rule, not a network law.
- With `FairMode = 0` both `IndexDomain`s are empty, so the constraints generate **zero rows** and
  `Zeta` is a free column with no coefficients that presolve removes. That is the mechanism by
  which case A reproduces the pre-fairness baseline exactly (verified on the micro bed, §4.1).

On this fleet `BattMaxP = 3.6 kW` on all 1,216 batteries, so "proportional to capacity" coincides
numerically with "equal absolute". The constraint is not slack for that reason: the network is
radial, so two identical batteries at different feeder positions cannot inject equally without
different voltage rise. **The heterogeneity that makes C1 bind is locational, not equipment.**

TR9's three aggregators come from `BattAgg`, the database column, used as the single source of
truth for membership:

| Aggregator | Prosumers | Capacity |
|---|---|---|
| `Agg1` | 28 | 100.8 kW |
| `Agg2` | 32 | 115.2 kW |
| `Agg3` | 30 | 108.0 kW |

---

## 2. Where fairness is imposed — and where it is deliberately not

`FairActive` is the runtime gate set by `RunFOR_Rolling`: **0** around the committed
self-consumption baseline solve, **1** around the 12 directional solves.

Without the gate, fairness would also bind in the committed baseline, because `PeriodMaxP = 2` in
both solves and `MinImports` uses the same constraint set. Two things would follow:

1. It would bind an agent that gains nothing from it. The baseline objective `OFminImports`
   carries **no service term at all**, and `w2(PeriodMaxP) = 0` by design — the baseline must not
   pre-commit value at the service slot, because that exchange *is* the flexibility being offered.
2. It would shift the executed slot-1 dispatch and therefore the realised SOC trajectory. The A/B
   comparison would then mix *"fairness contracts the offered region"* — what this document
   measures — with *"fairness moved the batteries somewhere else"*, and per-period comparison would
   stop being legitimate because the starting SOCs would no longer match.

Modelling reading: the committed baseline is a pure self-consumption agent that provides what it
happens to have available when service is called, not one that spends every half hour positioning
for a market it might be asked to serve.

`FairBaseline` (default 0) is an experiment toggle that also applies the constraints in the baseline
solve, for the opposite reading — "prosumers anticipate a fair market". It is implemented and off;
every result in this document was produced with it off.

---

## 3. Outputs

A **new** CSV per run, `FOR_rolling_fair<suffix><tag>.csv`, one row per (vertex, aggregator):

```
now,target,angle_deg,FairMode,zeta,status,aggregator,n_batt,cap_pu,sumP_pu,util,util_min,util_max
```

`util` is the aggregator's realised utilisation, `util_min` / `util_max` the extreme per-prosumer
utilisations inside it. Under `FairMode = 1` those two collapse onto `util`; under `FairMode = 2`
they are free to spread while only the total tracks `Zeta`. The file is written for **every**
`FairMode`, including 0, so case A supplies the unconstrained reference split.

**The pre-existing CSVs did not change schema.** `FOR_rolling*.csv` and `FOR_rolling_soc*.csv` keep
their columns, so `scripts/compare_FOR_runs.py` and `scripts/build_workbook.py` remain valid
regression evidence across the change.

One-click wrappers (section `SelfConsumptionOPF`), each of which resets `FairMode` and
`FairFileTag` on exit:

| Procedure | Runs | Writes |
|---|---|---|
| `RunMicro_FairL1` | micro bed, `FairMode=1` | `FOR_rolling_fairL1.csv` (+ `_soc_`, + fairness log) |
| `RunMicro_FairL2` | micro bed, `FairMode=2` | `FOR_rolling_fairL2.csv` (+ …) |
| `RunTR9_FairL1` | TR9, `FairMode=1` | `FOR_rolling_TR9_fairL1.csv` (+ …) |
| `RunTR9_FairL2` | TR9, `FairMode=2` | `FOR_rolling_TR9_fairL2.csv` (+ …) |
| `RunMicro_Baseline` | all-idle B(t) for the micro bed | `FOR_rolling_baseline_micro.csv` |

---

## 4. Runtime

Study case `v1_baseline`, 576 vertices each. "Vertex solve time" is the sum of the CSV `time`
column, i.e. `FOR_VertexCont.SolutionTime` only — it excludes the 48 baseline solves, the data
loading and the I/O, which is why it is below the wall-clock.

| Run | Wall-clock | Vertex solve time | solver / wall | median | max | Status |
|---|---|---|---|---|---|---|
| **A** (`FairMode=0`, reference) | 3 h 40 min | 8,440.7 s | 64 % | 14.50 s | 22.42 s | 576/576 Optimal |
| **L1** (`FairMode=1`) | 3 h 49 min 12 s | 8,440.5 s (**+0.0 %**) | 61.4 % | 14.49 s | 23.59 s | 576/576 Optimal |
| **L2** (`FairMode=2`) | 4 h 47 min 57 s | 10,118.6 s (**+19.9 %**) | 58.6 % | 15.59 s | 46.13 s | 576/576 Optimal |

Rebuild this table with `scripts/run_timing.py` (§9).

**Level 2 costs 20 % more solver time although it constrains less, and its worst vertex nearly
doubles.** Level 1 collapses the fleet to one effective degree of freedom, which makes the
barrier's job easier — 90 columns are pinned to a single scalar. Level 2 keeps 90 degrees of
freedom coupled by only 3 equality rows, leaving a large degenerate feasible set, which is the
expensive case for an interior-point method. The same explanation appears in
`docs/rolling-for-performance.md` §5.

### 4.1 Case A was not re-run

With `FairMode = 0` the two constraints generate zero rows (§1). This was verified on the micro bed
before the production runs: `max |delta proj| = 0` against the pre-fairness run, and a
byte-identical SOC CSV. The A files are therefore the 29-Jul run that
`docs/rolling-for-performance.md` §3.2 already validates, re-used unchanged.

---

## 5. Verification

Run `scripts/check_fairness.py --suffix _TR9` (§9). Results:

### 5.1 The constraint is actually enforced

| Check | L1 | L2 |
|---|---|---|
| `util == zeta` in every aggregator | OK | OK |
| `util_min == util_max` (level 1 only) | OK | n/a |
| `\|zeta\|` max | 1.0000 | 1.0000 |

**`-1 <= zeta <= 1` is derived, not imposed.** No row of the model enforces it, and none should:
`MaxBattP_Chg_def` and `MaxBattP_Dis_def` already bound every battery to
`|BattP_Balance| <= BattMaxP` unconditionally, and `FairCap = BattMaxP`, so dividing the fairness
equality by the capacity carries the bound onto `zeta` — directly at level 1, and through the
triangle inequality on the aggregator sum at level 2. Adding it as a row would be redundant, and
adding it as `|zeta| <= 1` would make it nonlinear. It is **reached** (1.0000) and never exceeded,
so it is a genuine facet of the feasible set rather than slack. The check above therefore validates
the derivation, not a constraint.

*Caveat for the m=3/m=4 criteria:* the derivation needs the normalising capacity to be the same
quantity that bounds the left-hand side. Once fairness moves to the prosumer exchange and the
normalisation is no longer `BattMaxP`, the bound stops coming for free.

### 5.2 Nesting

Level 1 is stricter than level 2, which is stricter than no fairness, so
`proj_L1 <= proj_L2 <= proj_A` must hold at every vertex.

- `proj_L1 <= proj_A` — **holds at all 576 vertices**.
- `proj_L1 <= proj_L2` — **holds at all 576 vertices**.
- `proj_L2 <= proj_A` — **holds at all 576 vertices**, at the tolerance derived in §5.4.

### 5.3 Fairness does not enter the committed baseline

`FOR_rolling_soc_TR9_fairL1.csv` is **byte-identical** to case A's `FOR_rolling_soc_TR9.csv`, and
so is the level-2 file. All three runs produce the same 4,320-row SOC trajectory. That confirms at
production scale what `FairActive` is supposed to do: the committed dispatch and the realised SOC
are untouched, so every difference reported below is a difference in the *offered region* and
nothing else. It is also what makes the per-period A/B comparison legitimate — the three cases
enter each period from the same state.

### 5.4 Why the nesting check has its own tolerance

The nesting check compares **two different formulations**, each solved independently. That is not
the same problem as comparing two runs of one formulation, and it does not take the same tolerance.

`scripts/check_fairness.py` therefore carries two constants. `TOL_PROJ = 2e-6` is inherited from
`scripts/compare_FOR_runs.py` and is correct for what it still does here — counting how many
vertices moved at all. `TOL_NEST = 1e-4` p.u. is used only for nesting, and is derived as follows:

1. **The nesting cannot actually be violated.** `FairMode = 2` only *adds* equality rows to case A's
   program. L2's feasible set is a subset of A's, and the maximum of the same linear objective over
   a subset cannot exceed the maximum over the set. Any positive excess is numerical.
2. **1e-3 is the only provable bound.** The model runs with `Feasibility_Tolerance := 1.0e-3` (1 kW),
   so residuals are guaranteed only to that.
3. **1e-4 is the deliberately strict choice inside that bound.** It is 10× finer than the solver's
   guarantee — the same reasoning already applied to `TOL_FAIR` — and 16× above the worst excess
   measured on TR9 (6e-6 p.u. = 6 W; the `proj` column is printed to 6 decimals, i.e. 1 W per digit,
   so that excess is 6 units in the last printed digit). It stays three orders of magnitude below
   the smallest defect worth catching: a real contraction is ~3e-1 p.u. Tightening to 1e-5 would
   leave 1.7× of margin over measured noise and flag it again.

At 2e-6 the check reported 4 vertices, all at the noise floor and spread across unrelated periods
and angles; a genuine formulation defect would concentrate. At `TOL_NEST` all three nesting
relations hold at all 576 vertices and the script exits 0. The contraction counts are unaffected:
they still use `TOL_PROJ`.

---

## 6. How much the region contracts

Two metrics are reported, because they answer different questions. `check_fairness.py` measures the
loss of **projection** per direction; `make_viz_data.py` measures the loss of **area** (shoelace
over the 12 vertices). On the micro bed the area loss was far larger than the per-direction
projection loss (median ~0), because the FOR has flat faces where the optimum slides to a fair point
at no projection cost. Projection alone would suggest fairness is nearly free, and the area figures
show it is not.

TR9, 576 vertices / 48 periods:

| | L1 (prosumers) | L2 (aggregators) | ratio |
|---|---|---|---|
| Area loss, median | **35.83 %** | **2.27 %** | 16× |
| Area loss, max | 90.09 % (step 42) | 6.84 % (step 21) | 13× |
| Projection loss, median | 17.4 kW | 0.26 kW | 66× |
| Projection loss, max | 315.9 kW | 23.6 kW | 13× |
| Vertices affected | 545/576 (94.6 %) | 450/576 (78.1 %) | |

Case A's own area ranges from **102,950.8 to 276,851.4 kW·kVAr** across the day, so the medians
above are losses against a region that is itself an order of magnitude larger than the worst-case
loss.

Micro bed (`TR9_two`, 12 prosumers, 1/7/4 aggregator split) for reference — median / max area loss:
**L1 22.16 % / 87.35 %**, **L2 7.46 % / 23.08 %**. Level 2 bites harder there than on TR9 because
the micro split is far more unbalanced than TR9's 28/32/30. TR9's near-equal aggregators are why
level 2 costs so little here; that is a property of this fleet, not a general result.

> The "max relative" percentage `check_fairness.py` prints (4124 % for L1, 2166 % for L2) is not a
> meaningful figure: it divides by `proj_A`, which is near zero at some vertices. The absolute
> projection losses and the area losses above are the ones to read.

---

## 7. Main result — one battery at the SOC floor idles the whole fleet under level 1

The SOC floor is `BattSOCmin = 0.10` (constraint `MinSOC_def`), from the database.

The sweep at rolling step `now` offers the region for target period `(now mod 48) + 1`, so the
battery state that matters for the service slot is the SOC entering the **target** period.

**16 of the 48 target periods have at least one battery on the floor** — targets 4–12, 14, and
43–48. In **all 16**, `|zeta|` at 180° (maximum import reduction / maximum export) is
**0.0000** (largest observed 1e-6, the print resolution). In the other 32 it averages **0.5430**.
One battery on the floor is sufficient to zero the fleet, with no exception in 16 out of 16.

The converse is not exact: one of the 32 unfloored periods also has `zeta = 0` at 180° — the wrap
step `now = 48`, whose service slot is target period 1, where every battery is still at the 0.40
initial SOC. Whatever blocks that step, it is not the floor. It is the only such case.

The transition into the evening block, at 180°:

| Rolling step | 40 | 41 | 42 |
|---|---|---|---|
| `zeta` | −0.9537 | −0.2492 | **0.0000** |

**Mechanism.** The fleet is homogeneous — `s_i = BattMaxP = 3.6 kW` for all 90 batteries — so
`x_i = zeta * s_i` forces lockstep. One battery that cannot discharge because it is on its floor
pins `zeta` to zero, and with it the other 89. This is not a solver artifact: it is exactly what
the level-1 equality says.

**Consequence, measured.** In those 16 periods the level-1 vertex in the 180° direction sits within
**5.5 kW** of the all-idle point in active power (range 0.8–5.5 kW), against **97.7–321.4 kW** of
capability at the same vertex in case A — and 246.7–321.4 kW over the six evening periods (targets
43–48). The worst is rolling step 42, whose service slot is target period **43 = 21:00, the evening
peak**, where case A reaches 321.4 kW of export deviation and level 1 reaches 5.5 kW. That is also
the step with the maximum area loss (90.09 %) and the maximum projection loss (315.9 kW).

The few-kW residual is **not numerical noise**. With `zeta = 0` the active power of every battery
is zero, but the inverters still have reactive power available at the service slot — the level-1
constraint binds `BattP_Balance` only — and up to 322 kVAr of Q moves the PCC active power through
network losses.

**Level 2 does not have the pathology.** Over the same 16 target periods it keeps `|zeta|`
averaging **0.5557**, about 56 % of nameplate. Intra-aggregator freedom lets the floored battery
stay idle while the other 89 dispatch; only the aggregator *total* has to track `zeta`.

The practical reading: capacity-proportional fairness applied **per prosumer** makes the weakest
battery in the fleet the binding constraint on everyone, and it does so precisely at the evening
peak, when the service is worth most. Applied **per aggregator** it does not.

---

## 8. Secondary checks

**Nameplate consistency.** Case A's deviation region — the FOR measured from the all-idle baseline
B(t) — spans **−326.8 to +323.9 kW** in active power across the whole day, against an aggregate
nameplate of exactly **90 × 3.6 = 324.0 kW**. The fleet reaches its rating on the import side
(+323.9 kW) and does not exceed it; the 2.8 kW overshoot on the export side is network losses
moving with Q, the same effect as in §7. This is a sanity check on the deviation view, not a
fairness result.

**The all-idle baseline B(t).** `RunFOR_Rolling_Baseline` writes `FOR_rolling_baseline.csv`,
48/48 Optimal, PCC active power from **−2,311.7 kW** (period 26, deepest export) to
**+1,236.9 kW** (period 43, evening peak). Despite the generic name this file is **TR9-specific**:
the procedure hardcodes `DetailTagCSV := "TR9"` with `ReduceNetwork := 1`, the same reduction the
sweep uses. That is deliberate and is what makes the deviation view cancel the reduction error
instead of carrying it — B(t) and the FOR are computed on the same network. Using a baseline from a
different reduction would compare the region against the wrong origin.

---

## 9. Reproducing

Model runs, in AIMMS, in this order (case `v1_baseline` loaded):

```
RunReducedTest_RollingMicro     ! case A, micro bed          — validate FIRST
RunMicro_FairL1                 ! micro, level 1             ~10 min
RunMicro_FairL2                 ! micro, level 2             ~10 min
RunMicro_Baseline               ! all-idle B(t), micro bed   — cheap
RunFOR_Rolling_Baseline         ! all-idle B(t), TR9         — cheap
RunTR9                          ! case A, TR9                ~3 h 40 min
RunTR9_FairL1                   ! TR9, level 1               ~3 h 49 min
RunTR9_FairL2                   ! TR9, level 2               ~4 h 48 min
```

Post-processing, from the repository root, with the CSVs in the root:

```bash
py -3 scripts/check_fairness.py --suffix _TR9      # constraint, nesting, projection contraction
py -3 scripts/run_timing.py --inicio "YYYY-MM-DD HH:MM"   # the table in section 4
py -3 scripts/make_viz_data.py --suffix _TR9       # area contraction + scripts/for_data_TR9.json
py -3 scripts/build_viz.py --suffix _TR9           # results/viz/FOR_fairness_TR9.html
```

Drop `--suffix _TR9` for the micro bed. `run_timing.py` takes the wall-clock end from the file
mtime, so `--inicio` is the start time of the **last** file in the list; the solver totals need no
flag.

Artifacts this document is built from:

| Artifact | Tracked? |
|---|---|
| `FOR_rolling_TR9.csv`, `FOR_rolling_soc_TR9.csv` (case A) | no — git-ignored, shared separately |
| `FOR_rolling_TR9_fairL1.csv`, `FOR_rolling_soc_TR9_fairL1.csv` | no |
| `FOR_rolling_TR9_fairL2.csv`, `FOR_rolling_soc_TR9_fairL2.csv` | no |
| `FOR_rolling_fair_TR9_fairL1.csv`, `FOR_rolling_fair_TR9_fairL2.csv` (fairness log) | no |
| `FOR_rolling_baseline.csv` (all-idle B(t)) | no |
| `results/viz/FOR_fairness_TR9.html` | **yes** |
| `results/viz/FOR_fairness_micro.html` | **yes** |

The raw CSVs regenerate on every run and are excluded by `.gitignore` (`CONTRIBUTING.md` §3); the
two HTML viewers are self-contained and are committed, so the results can be inspected without
re-running the model.

---

Measured on study case `v1_baseline`. `FairCap = BattMaxP` is the capacity source used throughout;
the numbers change with that choice and nothing else in the formulation does, so a run should always
record which source it used.
