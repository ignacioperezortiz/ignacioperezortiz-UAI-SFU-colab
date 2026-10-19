# Paper-1 fairness: reference results (TR4, 10-11 Oct 2026)

Compact data extracted from the runs in lanes N2/N3 (not in the repo). Files: fair.json, muf.json, service_T5.json (= data/service.json below), for_time.json, guarantee.json, sweeps.json, service_requests.json (= data_tulio/service.json below). Commits: 866c053 (previous floor, mu^f, no-limits, T5), 2f68674 (effective headrooms, T7). The guarantee pair (SCAlpha 0/99) used a diagnostic copy where PV2_Run does not overwrite SCAlpha; not reproducible from the repo as is. Key numbers: docs/paper1-fairness.md section 6. The provenance notes written when the data were extracted follow verbatim.


---

## Provenance: data/README.md

# Chart data: μ^f, fairness criteria and delivery (TR4)

This README covers `muf.json`, `fair.json`, `service.json`, the scripts in `scripts\` and four quick-look images: `quicklook\muf_quicklook.png`, `fair_area_ratio.png`, `fair_polygons.png` and `service_quicklook.png`. The images are for internal review only.

The folder is shared. `for_time.*`, `guarantee_*`, `work*\` and `quicklook\ql_*.png` come from another task and are not covered here.

Regenerate with `python -B scripts\build.py`, then `python -B scripts\quicklook.py`. Both scripts only read the lane and write only into this folder. `scripts\explore*.py` are the checks used while building.

## Source

- **Lane.** `C:\Users\LAPTOP-01\master\paper1-runs\N2`. Every run used has `done…txt` with "Return value = 0", and all 576 directional solves of every one-day run are Optimal.
- **Code.** Built by importing `analyze_fair.py` (`corners`, `area`, `read`, `done`, `info_lines`) and `scripts/paper1/analyze_paper1.py` (`days`, `clock`, `read`, `DT`). The t5 logic and the mixing count follow `analyze_t7.py`. `analyze_paper1.main()` was not run, because it writes into its `--work` folder.
- **Commits** (from RESULTADOS-2026-10-11.md, confirmed by the `FAIR settings` line of each `SCT_info`):
  - runs whose line includes `FairEffHead 1` are 2f68674 (energy floor);
  - the others are 866c053 (old floor (1−DOD_s)Ē_s).
- **μ^f.** Taken from the same line: `kappa_slot (FOR_ThruPenSlot)` is 0.200 by default, 0.100 with `_P2SlotPen0.1` and 0.000 with `_P2SlotPen0`. In `OPF.ams`, `FOR_ThruPenSlot := if P2SlotPen >= 0 then P2SlotPen else 0.2`. The P2 objective term (line 2354) is `FOR_ThruPenSlot * Σ_bat (BattP_Chg + BattP_Dis)` at slot k+1.

| JSON | case (display label) | run tag (suffix after `_REF_SWEEP_free_today_a2x4p8fin_TR4`) |
|---|---|---|
| muf | μ^f = 0.2, with limits | `_FairBox1` (866c053) |
| muf | μ^f = 0.1, with limits | `_P2SlotPen0.1` (866c053) |
| muf | μ^f = 0, with limits | `_P2SlotPen0` (866c053) |
| muf | μ^f = 0.2, without limits | `_FairBox0` |
| muf | μ^f = 0, without limits | `_FairBox0_P2SlotPen0` |
| fair | reference (ratio denominator) | `_FairEffHead1` |
| fair | CP / HP / HB, intra-aggregator, energy floor | `_FairCrit{1,2,3}_FairScope1[_FairEps0.1]_FairEffHead1` |
| fair | CP / HP / HB, network-wide, energy floor | `_FairCrit{1,2,3}_FairScope2[_FairEps0.1]_FairEffHead1` |
| fair | same, old floor | the same tags without `_FairEffHead1` |

`service.json` uses the prefix `_WC_EXPORT_free_today_a2x4p8fin2_TR4`, and its no-request counterparts `_REF_free_today_a2x4p8fin2_TR4`, each with one of three suffixes:
- `_FairBox1` (no fairness);
- `_FairCrit2_FairScope1` (HP, old floor);
- `_FairCrit2_FairScope1_FairEffHead1` (HP, energy floor).

Day 2 is joined from the `_d2` files.

## Coordinates (FOR polygons, ΔP ranges)

**The CSVs hold absolute values in MW / Mvar.** `FOR_rolling<tag>.csv` columns `P`, `Q` are the absolute interface exchange at the TSO–DSO interface (feeder head; TR4 detailed, the other transformers lumped), positive = import. Example: 617 kW at step 1, 0°.

**The JSON gives deviations (ΔP, ΔQ) in kW / kvar** from the exchange with all BESS idle, in the same slot k+1, positive = import. This is the paper's Fig. 6 convention.

**No all-idle power flow exists for TR4 on this day.** The `FOR_rolling_baseline*.csv` in the repo are for TR9, micro and the full feeder. The idle exchange is therefore estimated from the committed operation:
- **Formula.** P_idle(t) = `P_PCC1` − Σ`Pexec`, and Q_idle(t) = `Q_PCC1` − Σ`Qinv1`, read from `FOR_rolling_soc_REF_SWEEP…_FairEffHead1.csv` at `now = t` (slot k of that step is period t).
- **Values.** Σ`Qinv1` = 0 at every step, and |Σ`Pexec`| ≤ 54 kW.
- **Alignment.** The FOR of step `now` is for period `target = now mod 48 + 1`, and P_idle(target) is taken at `now = target`.
- **Same for every run.** The `soc` file is identical in all REF_SWEEP runs, so one estimate serves them all.
- **Same estimator as the other task.** `build_for_time.py` in this folder uses the same formula.

**Accuracy.** The estimate omits the loss change caused by the committed BESS power. Two independent checks bound the error:
- a quadratic fit of (P − ΣP^b) against ΣP^b over the 12 directional solves of the previous step (ΣP^b from `FOR_rolling_fair` `sumP_pu`), evaluated at ΣP^b = 0, differs from P_idle by **≤ 0.93 kW**;
- ΔQ at 90° and 270° is symmetric about 0 within **0.59 kvar**.

A misaligned period would show up as differences of 100 kW or more.

**Areas and area ratios do not depend on this choice** (they are invariant to translation). Absolute = deviation + `idle_exchange` (given per step in `fair.json`).

**Time labels.** All times are `HH:MM` at the start of flexibility slot k+1 (`analyze_paper1.clock(target)`). Step 48 is 00:00.

## Provenance of each number

- **Simultaneous charging/discharging** (muf). From `FOR_rolling_crit<tag>.csv`, summed over the 3 aggregator rows of each (`now`, `angle_deg`):
  - `n_cyc` counts the BESS with min(P^ch, P^dis) > 1e-6 MW (1 W) in slot k+1, and a directional solve counts when Σ`n_cyc` > 0;
  - `cyc_kW` = Σ min(P^ch, P^dis) gives "simultaneous kW" (per solve). The JSON gives the per-step max and sum over the 12 solves, and the overall max and total.
- **Slot-(k+1) BESS throughput.** `thr_kW` = Σ(P^ch + P^dis), summed over groups. Per step: the mean and max over 12 solves. Summary: the mean over 576.
- **FOR area.** Shoelace over the 12 points (`analyze_fair.area`) on `FOR_rolling` P, Q × 1000, in kW·kvar. Ratios are per step; the mean is the mean of the 48 ratios, as in `analyze_fair.pair`.
- **ΔP at 0°** (muf). `P` at `angle_deg` 0 minus the same for μ^f = 0.2 with limits.
- **Exceedance of the limits** (muf, extra). `box_up_viol_kW`, `box_dn_viol_kW` (per-BESS maximum, logged even when the limits are off).
- **Export served** (service). `FRQ<tag>.csv`: 0.5 h × Σ max(0, −`dP_kW`) over the 28 requests (`analyze_paper1` `export_more_kWh`). `dP_kW` = requested point − no-request point S0. The per-request series is `dP_kW`, `dQ_kvar` by `target`.
- **Prosumers buying more inside the requested half-hours.**
  - Inputs: `SCT_exec<tag>.csv` + `_d2`, joined on (`now`, `battery`) with the no-request run. Per prosumer, Σ(`imp1_kWh` − `imp1_kWh` of the no-request run) over the rows with `svc` = 1 (28 half-hours).
  - Counted when > 1e-3 kWh (1 Wh).
  - Also given: the worst value, the fleet sum, the count above 10 Wh, and the same sum outside (`svc` ≠ 1) in Wh.
- **Mixed allocations at 180°.** `FOR_rolling_crit` rows at `angle_deg` 180 with Optimal status and `zu` > 1e-3 and `zd` > 1e-3. There are 3 aggregator rows per step: 48 × 3 = 144 for the one-day FOR, 28 × 3 = 84 for the service run. Counts at 1e-6 are also given (`analyze_t7.mixed` uses 1e-6).

## Expected vs reproduced

| item | expected | reproduced | |
|---|---|---|---|
| μ^f = 0, with limits: directional solves with simultaneous charging/discharging | 505 / 576 | 505 / 576 | match |
| same, largest simultaneous power | up to 101 kW | 101.18 kW | match |
| slot-(k+1) BESS throughput, μ^f 0.2 → 0 | 55 → 137 kW | 55.01 → 136.67 kW (mean of 576 solves) | match |
| FOR area, μ^f = 0 vs 0.2 (with limits) | +1 % (max 1.6 %) | +1.01 % (max +1.57 %, 18:30) | match |
| without limits, μ^f = 0: FOR area vs μ^f = 0.2 with limits | +8 % (max +20 %) | +8.04 % (max +19.86 %, 17:30) | match |
| same, at 0° | +16 kW | max +16.38 kW (mean +8.57 kW) | match (16 kW is the maximum over steps) |
| μ^f = 0.1: simultaneous charging/discharging | none | 0 / 576 | match |
| μ^f = 0.1: FOR area vs μ^f = 0.2 | +0.7 % | +0.71 % | match |
| CP, intra / network-wide, energy floor (mean area ratio) | 51 / 40 % | 51.48 / 40.27 % | match |
| HP, intra / network-wide, energy floor | 98.7 / 98.6 % (min 93.7 / 92.5) | 98.71 / 98.58 % (min 93.70 / 92.52, both 12:30) | match |
| HB, intra / network-wide, energy floor | 99.8 / 99.8 % | 99.83 / 99.77 % | match |
| HP, old floor | 74 / 63 % | 73.83 / 63.42 % | match |
| HB, old floor | 82 / 74 % | 82.20 / 73.72 % | match |
| export served (no fairness / HP old floor / HP energy floor) | 854.3 / 675.2 / 854.3 kWh | 854.3 / 675.2 / 854.3 kWh | match |
| prosumers buying > 1 Wh more inside the requested half-hours | 0 / 22 (worst +1.10 kWh) / 0 | 0 / 22 (worst +1.099 kWh) / 0 | match |
| mixed allocations at 180°, HP intra-aggregator (one-day FOR) | 72 / 144 (old floor) vs 6 / 144 (energy floor) | 72 / 144 vs 6 / 144 | match |

**Every expected value is reproduced.**

Other figures in RESULTADOS-2026-10-11.md that are not in the list above:
- **Matches:**
  - worst prosumer outside the requested half-hours: 2.16 / 1.19 / 1.82 Wh (doc: 2.2 / 1.2 / 1.8);
  - without limits and μ^f = 0, the limits are exceeded in 205 solves by up to 0.361 kW per BESS (doc: 205, 0.36);
  - 28 / 28 requests served in all three cases.
- **Mismatches in the source document (flagged, not corrected there):**
  - **Prosumer count, 21 vs 22.** The T5 text says 21 prosumers buy more and the T7 table says 22. With the 1 Wh threshold the count is 22; 21 is the count above 10 Wh.
  - **Fleet total, 6.7 vs 7.67 kWh.** The T5 text says the fleet buys +6.7 kWh more inside the requested half-hours; the data give **+7.67 kWh**. The worst prosumer, +1.099 kWh, does match.
  - **Mixed corners, 41 vs 42.** The T5 text says 41 of 84 mixed at 180° in the service run with HP, old floor. At the 1e-3 threshold the count is **42 / 84**; 41 appears only at a 1e-2 threshold. It is 0 / 84 with the energy floor.
  - **Share of mixed groups, 49 vs 50 %.** The T5 text says 49 % of groups in HP intra are mixed; it is 72 / 144 = 50 % at 1e-3 (121 / 144 at 1e-6).
  - **CP collapse window.** The T4 note says CP collapses between 15:00 and 19:30. The ratio is below 1 % at 17:30–19:30 for intra-aggregator and at 15:30–19:30 for network-wide. At 15:00 it is 67.7 % (intra) and 11.4 % (network-wide).

## Caveats

1. **ΔP, ΔQ use an estimated idle exchange** (above). The error is ≤ 0.93 kW / 0.6 kvar, not zero. The areas and ratios are exact.
2. **The μ^f = 0 and 0.1 runs predate the energy floor** (866c053, U_s and D_s measured to the old floor). The μ^f = 0.2 case in `muf.json` is therefore `_FairBox1`, from the same commit.
   - The energy-floor reference `_FairEffHead1` has the same FOR: area ratio 1.0000 at every step, per point ≤ 0.023 kW / 0.108 kvar apart, the same throughput, and no simultaneous charging/discharging.
   - No run with μ^f = 0 and energy-floor limits exists.
3. **Simultaneous charging/discharging with and without limits.** At μ^f = 0, the per-step count of solves is identical with and without limits (505 each), but the power differs: 101 kW with limits vs 149 kW without (max). The throughput is 137 vs 167 kW (mean).
4. **Area ratios above 1.** HB with the energy floor has ratios slightly above 1 at 18:00–22:00 (> 1.0005; up to 1.0054 intra, 1.0062 network-wide, at 19:00).
   - The 12-point hull is not the region: points slide along flat faces, and each point maximises projection − μ^f × throughput.
   - HB reaches up to 0.25 kW farther in projection with more throughput, and its objective never exceeds the reference's by more than 1 W.
   - **Do not present these as HB enlarging the FOR.**
5. **Polygons.**
   - They have 12 points in θ order (0° = +ΔP, 90° = +ΔQ), and consecutive points can coincide.
   - At 12:30 the BESS are full, so the reference has no import side: ΔP ≤ +5 kW.
   - At 18:00, CP is a vertical segment at ΔP ≈ −7 kW (the committed discharge; only ΔQ remains), so its area is 0.
   - "HP, old floor" is included as an extra series for comparison.
6. **Service runs.** The metrics are summed over both days, with no requests on day 2. The 0.5 h factor turns kW into kWh. All of this is TR4, one profile set (`free_today`), and the clear-sky day.
7. **Prosumer identifiers** (`BES_TR4_three368_A`, …) are internal IDs for provenance, not display labels.

## JSON schemas (short)

- **`muf.json`.**
  - Top-level fields: `time`[48], `definitions`, `cases`[{`id`, `label`, `mu_f`, `limits`, `source_tag`}], `note_reference`.
  - `per_step[id]` holds arrays of 48: `simultaneous_solves` (0–12), `simultaneous_kW_max`, `simultaneous_kW_sum`, `throughput_kW_mean`, `throughput_kW_max`, `FOR_area_kWkvar`, `area_ratio` (vs μ^f = 0.2 with limits) and `dP_0deg_vs_ref_kW`.
  - `summary[id]` holds the totals, means and maxima, including `solves_exceeding_limits_by_1W` and `max_exceedance_per_BESS_kW`.
- **`fair.json`.**
  - Top-level fields: `time`[48], `coordinates`, `reference_FOR_area_kWkvar`[48], `sources`, and the notes.
  - Area ratios: `area_ratio[floor][CP|HP|HB][intra-aggregator|network-wide]`[48] for floor ∈ {energy floor, old floor}, with `summary[...]` = {`mean`, `min`, `min_time`, `max`, `max_time`, `times_below_1pct`}.
  - Per-step ΔP ranges: `dP_range_intra_energy_floor[reference|HB|HP|CP]` = {`dP_max_kW`, `dP_min_kW`}[48], and `idle_exchange_per_step` {`P_kW`, `Q_kvar`}[48].
  - Polygons: `polygons.steps`[3] = {`time`, `step`, `why`, `idle_exchange`, `area_kWkvar`, `area_ratio`, `FOR`{`reference`, `HB`, `HP`, `CP`, `HP, old floor`: [[ΔP, ΔQ] × 12]}}, at 07:30, 12:30 and 18:00.
- **`service.json`.**
  - Top-level fields: `cases`[3] (`no_fairness`, `HP_old_floor`, `HP_energy_floor`) and `definitions`.
  - `summary[id]`: `requests_served` / `planned`, `export_served_kWh`, `prosumers_buying_more_inside` (> 1 Wh), `worst_prosumer_inside_kWh` / `_id`, `fleet_extra_purchase_inside_kWh`, `worst_prosumer_outside_Wh` / `_id`, …
  - `per_request[id]` = {`time`[28], `dP_kW`, `dQ_kvar`}, and `extra_purchase_inside_by_prosumer_kWh[id]` (sorted, > 1 Wh only).
  - `mixing_180deg` = {`one_day_FOR`, `two_day_service`}[floor] = {`mixed`, `of`, `count_at_1e-6`, `source_tag`}.

---

## Provenance: data/README_time_guarantee.md

# Chart data: F_{k+1} over time with TSO service, and the self-consumption guarantee

Chart-ready data for two deck charts: (1) how the FOR F_{k+1} changes over two days, with and without TSO export
requests; (2) what the self-consumption guarantee costs and protects. Built 13/14-oct-2026 from the paper-1 run lanes
(read only; nothing in the repo, the lanes or OneDrive was touched; no AIMMS launched). Both N3 runs of the
current-commit pair finished (SCAlpha0 at 23:32, SCAlpha99 at 00:06) and are included.

| File | What |
|---|---|
| `for_time.json` | per-slot FOR ranges, points, SOC, comparison block, representative polygons (schema below) |
| `for_time.csv` | the same per-slot series in long format (one row per case x slot) |
| `guarantee.json` | guarantee metrics for the current-commit pair (guarantee on / relaxed), see section 4 |
| `guarantee_validation.json` | reproduction of the known figures (section 3) |
| `build_for_time.py` | builds `for_time.*` |
| `guarantee_metrics.py` | builds `guarantee.json`; `--validate` builds `guarantee_validation.json` |
| `quicklook_time_guarantee.py`, `quicklook/ql_*.png` | internal quick looks (not for the deck) |
| `work_time_guarantee/` | exploration scripts |

Run everything with the system Python (`python`, 3.11 with pandas/matplotlib), not the master `.venv` (no numpy there):

```
cd C:\Users\LAPTOP-01\master
python -B <data>\build_for_time.py [--case KEY=LANE/TAG ...]
python -B <data>\guarantee_metrics.py --validate
python -B <data>\guarantee_metrics.py --on N3/<tag on> --relaxed N3/<tag relaxed> --ref N2/<tag no request>
python -B <data>\quicklook_time_guarantee.py
```

## 1. Provenance (internal names allowed only here)

| Case in the data | Display label | Lane / tag |
|---|---|---|
| `no_request` (trajectory, both days) | No TSO request (P1 baselines only) | N2 `_REF_free_today_a2x4p8fin2_TR4_FairBox1` (commit 866c053) |
| `no_request` (FOR at every step of day 1) | idem | N2 `_REF_SWEEP_free_today_a2x4p8fin_TR4_FairBox1` (one-day run; its executed trajectory is identical to the line above, max diff 0) |
| `export_guarantee_on` | TSO export requests, self-consumption guarantee | N3 `_WC_EXPORT_free_today_a2x4p8fin2_TR4_FairBox1_RollOfferLog1_SCAlpha0` (current commit 2f68674 + N3 diagnostic patch that lets scenario.txt set SCAlpha; no fairness criterion) |
| `export_guarantee_relaxed` | TSO export requests, guarantee relaxed | N3 `_WC_EXPORT_free_today_a2x4p8fin2_TR4_FairBox1_RollOfferLog1_SCAlpha99` (same commit; SCAlpha = 99 x BESS rating of allowed later imports) |
| (not in the file; fallback) | idem, older commit | N2 `_WC_EXPORT_free_today_a2x4p8fin2_TR4_FairBox1` (866c053). Same aggregate F_{k+1} as the N3 SCAlpha0 run within 0.02 kW / 0.04 kvar at all 336 boundary points, same fleet trajectory within 1.8 kW; the per-prosumer split of the service differs (SOC of single BESS differs from slot 15). All key numbers in section 5 are identical with either run. |

TSO requests (scenario `WC_EXPORT.json`): flexibility slots 13-40 of day 1 (06:00-19:30 start times, i.e. every
half-hour 06:00-20:00), each time the boundary point of F_{k+1} with the most export (search direction 180 deg);
none on day 2. All 28 are served and delivered exactly (requested = delivered point, max diff < 0.05 kW).

## 2. Conventions

**What the CSVs contain.** `FOR_rolling<tag>.csv`: one row per (step `now`, search direction `angle_deg` = 0, 30,
..., 330); `P`, `Q` = ABSOLUTE interface exchange of the boundary point v_theta in **MW / Mvar**, positive = import;
`target` = flexibility slot. `FOR_rolling_svc`: requested/delivered/realised points (MW, absolute). `FRQ`: S0 (the
P1-baseline point of the step), requested point and `dP_kW = req - S0` (kW, absolute). `FOR_rolling_soc` and
`SCT_exec`: per step and BESS, SOC at the start of the executed slot, executed battery P (`Pexec` = charge - discharge,
MW), inverter Q (`Qinv1`, Mvar, + = absorbing), interface exchange of the executed slot (`P_PCC1`, `Q_PCC1`, MW) and
house import (`imp1_kWh`).

**Coordinates (paper Fig. 6).** Everything in `for_time.*` is a deviation (dP, dQ) from the interface exchange with
all BESS idle, in **kW / kvar**, positive = import. The model does not write the all-idle exchange; it is computed per
slot from the no-request run as `B(t) = P_PCC1 - sum Pexec` (and `Q_PCC1 - sum Qinv1`) of the executed slot t. This
neglects the change in network losses when the BESS go idle. Error estimate: the same formula applied to the export run
gives the same B(t) within 3.1 kW / 4.1 kvar (with up to 165 kvar of inverter Q flowing); day 2 vs day 1 within 0.3 kW.
The aggregate converter rating is 165.6 kW / 165.6 kVA (dashed circle in Fig. 6).

**Slot mapping.** Rolling step k (CSV `now`) builds F_{k+1} for flexibility slot k+1 (CSV `target`). Slots 1-96 run
over the two days (day-2 `now` + 48). The clock label is the START of the flexibility slot: `(slot - 1) * 30 min`
mod 24 h, so slot 13 = 06:00, slot 40 = 19:30, slot 49 = day 2 00:00 (built at day-1 step 48). Slot 1 (day 1 00:00)
has no FOR (it would be built at step 0).

**Where F_{k+1} exists** (`for_source` per slot):

- `computed`: the 12 directional solves exist. No-request: day-1 slots 2-49. Export runs: only the requested slots
  13-40 (the model builds F_{k+1} only when a request is due).
- `same-state`: F_{k+1} is built at step k from the per-prosumer SOC at the start of step k and the frozen plan of
  slot k. Where both (all 46 BESS, within 1e-6) equal those of the no-request run at the step that built a computed
  no-request FOR, at the same clock time (load and PV profiles are identical on both days), that FOR is reused. This
  fills slots 2-12 of the export run (before the first request) and day-2 slots 79-96 (15:00-23:30) of both cases.
- `null`: no FOR. That is day-2 00:30-14:30 for both cases and day-1 20:00-23:30 for the export run.
  For those slots use the SOC-based bounds (section 5).

## 3. Validation (`guarantee_metrics.py --validate`)

| Run (no-request reference) | Quantity | Expected | Reproduced |
|---|---|---|---|
| HP intra, guarantee on (N3 `..._FairCrit2_FairScope1_RollOfferLog1`; ref N2 `_REF..._FairCrit2_FairScope1`) | export served | 675.2 kWh | **675.2 kWh** |
| HP intra, guarantee relaxed (`..._SCAlpha99`) | export served | ~993 kWh | **993.5 kWh** |
| No criterion, older commit (N2 `_WC_EXPORT..._FairBox1`; ref N2 `_REF..._FairBox1`) | export served | 854.3 kWh | **854.3 kWh** |
| idem | prosumers buying > 1 Wh more inside requested half-hours | 0 | **0** (worst +0.4 Wh) |
| idem | worst prosumer outside requested half-hours | 2.2 Wh | **2.2 Wh** |
| HP intra, guarantee on | prosumers > 1 Wh inside (RESULTADOS table: 22, worst +1.10 kWh) | 22 | **22** (worst +1.099 kWh) |
| HP intra, guarantee on | worst outside (RESULTADOS: 1.2 Wh) | 1.2 Wh | **1.2 Wh** |
| No criterion, current commit (N3 `..._FairBox1_RollOfferLog1_SCAlpha0`; ref N2 `_REF..._FairBox1`) | export served / inside > 1 Wh / worst outside | (854.3 / 0 / ~2) | **854.3 kWh / 0 / 1.8 Wh** |

Also from the HP pair (not in the doc): with the guarantee relaxed, **46/46** prosumers buy more outside the requested
half-hours (fleet +98.8 kWh, worst +3.48 kWh over two days), against 1/46 (fleet -0.9 kWh, worst 1.2 Wh) with it.
In every run the SOC before the first request equals the no-request run exactly (checked by the script).

## 4. guarantee.json (current-commit pair, produced)

Command used (from `C:\Users\LAPTOP-01\master`):

```
python -B <data>\guarantee_metrics.py --on N3/_WC_EXPORT_free_today_a2x4p8fin2_TR4_FairBox1_RollOfferLog1_SCAlpha0 --relaxed N3/_WC_EXPORT_free_today_a2x4p8fin2_TR4_FairBox1_RollOfferLog1_SCAlpha99 --ref N2/_REF_free_today_a2x4p8fin2_TR4_FairBox1
```

| Two days, 28 TSO export requests on day 1, no fairness | Self-consumption guarantee | Guarantee relaxed |
|---|---|---|
| Requests served (services released) | 28/28 (0) | 28/28 (0) |
| Export served (from each step's P1-baseline point) | **854.3 kWh** | **993.5 kWh** (+16 %) |
| Extra interface export vs the no-request run, same half-hours | 69.7 kWh | 180.7 kWh |
| Extra import OUTSIDE requested half-hours: prosumers > 1 Wh | 15/46 (all < 2 Wh) | **46/46** |
| idem, fleet total / worst prosumer | +0.04 kWh / +1.8 Wh | **+98.8 kWh / +3.48 kWh** |
| Extra import INSIDE requested half-hours: prosumers > 1 Wh | 0/46 (worst +0.4 Wh) | 43/46 |
| idem, fleet total / worst prosumer | 0.00 kWh | +28.2 kWh / +3.52 kWh |
| Mean SOC at the start of day-1 23:30 (no request: 50.3 %) | 26.5 % | 10.0 % (DOD floor) |
| Stored energy above the floor at day-1 20:00, vs no request | -46.5 kWh | -150.6 kWh |
| First request (06:00): export capability of F_{k+1} | 77.0 kW | 80.6 kW |

The relaxed figures equal those of the HP relaxed run of 11-oct (993.5 kWh, +98.8 kWh, 46/46): without the guarantee
the HP rule has no mixed corners and changes nothing. The "> 1 Wh" count with the guarantee on (15) is numerical
noise: the largest is 1.8 Wh over two days.

## 5. The message for the "F_{k+1} changes over time with service" chart (no fairness)

- **F_{k+1} follows the SOC even without service.** No request: export capability (-dP_min) 49-60 kW at night,
  105-159 kW from 06:30 to 15:30 (rating-limited at 154-159 kW when the BESS are full), 83-101 kW in the evening;
  import capability 165 kW at night, falling to 1-5 kW from 12:30 to 17:30 (BESS full), back to 135 kW at 23:30.
- **First request (06:00):** both cases have the same F_{k+1}; the TSO takes its max-export vertex, dP = -77.0 kW
  (dQ = +143 kvar), which empties the BESS to the DOD floor (mean SOC 32 % -> 11 %).
- **Every later F_{k+1} on day 1 is different.** Requested slots 06:30-12:30: export capability **1.6 kW** on average
  vs **148.8 kW** without service; import capability 162.5 vs 63.1 kW. F_{k+1} is not just smaller (area 54-100 % of the
  no-request FOR); it moves to the import side. At 12:30 the two FORs are near mirror images: dP in [-0.9, +161.3] kW
  with service vs [-154.2, +4.9] kW without.
- **13:00-18:30: F_{k+1} no longer contains the all-idle point on the export side.** Its most-export point needs the fleet
  to charge at least 0.6-34.9 kW (max at 16:30): the self-consumption guarantee makes the prosumers refill for the
  evening, so the TSO's "max export" is net charging. Mean over 13:00-19:30: export capability -13.8 kW vs 124.4 kW.
- **Day 2 recovers by the early afternoon.** From 20:00 on day 1 the fleet holds 46.5 kWh less stored energy above the floor
  (mean SOC 68.2 % vs 92.3 % at 19:30; 23.5 % vs 47.5 % at day-2 00:00). The gap stays 46.4 kWh until 06:00, then PV
  closes it: -10.9 kWh at 09:00, -1.0 kWh at 12:00, and the per-prosumer SOC is identical from **day 2 14:00**; F_{k+1}
  is identical from **day 2 15:00** on (same-state). Before that, the import side (SOC bound, validated within 3-4 kW) is
  larger with service: +27.5 kW at 00:00, +40.5 kW at 07:00, +2.1 kW at 12:00 of day 2. Day-2 export-side FORs were not
  built in either run.
- **"Export served" vs the counterfactual.** Each request is measured from the P1-baseline point S0 of its own step:
  854.3 kWh over the 28 requests. Against the no-request trajectory the interface exported only 69.7 kWh more in the
  same half-hours, because after 06:00 the service mostly cancels charging that the P1 baseline of the depleted fleet
  plans (S0 is +37 to +110 kW of charging between 06:30 and 17:00). Use the first figure as "export served" (paper definition); say what it is
  measured from if both appear.
- **Guarantee relaxed (third case in the file).** The first request takes 80.6 kW, and every later max-export point
  drains whatever PV charged: export capability 0-3 kW at every requested slot (mean 1.7 kW), import capability
  ~163 kW, and F_{k+1} never leaves the idle point (no forced charging). The cost shows after 20:00: the fleet holds
  150.6 kWh less (vs 46.5 kWh with the guarantee) and sits at the DOD floor, and every prosumer buys more later
  (section 4). Day 2 converges at the same time (SOC identical from 14:00, F_{k+1} from 15:00).

## 6. Schemas

### for_time.json

```
meta      : generated, network, coordinates, csv_content, idle_reference, idle_reference_check, slot_mapping,
            requested_slots_definition, availability, fields (field definitions), soc_bound_check, battery_parameters
slots[96] : {slot, day, time "HH:MM" (start of flexibility slot), label "d1 06:00", idle_exchange_kW, idle_exchange_kvar}
cases     : {no_request | export_guarantee_on | [export_guarantee_on_current] | [export_guarantee_relaxed]:
              {label, lane, tag, requested_slots[], series: {<field>: [96 values, index = slot - 1, null = n/a]}}}
   series fields: for_source, dP_min, dP_max, dQ_min, dQ_max (kW/kvar), area (kW*kvar), export_capability_kW (= -dP_min),
                  import_capability_kW (= dP_max), operating_point [dP,dQ] (executed slot), p1_baseline_point [dP,dQ],
                  requested_point [dP,dQ], delivered_point [dP,dQ], service_vs_p1_baseline [dP,dQ] (requested - S0),
                  requested (bool), soc_mean_pct, stored_energy_above_floor_kWh, soc_bound_export_kW, soc_bound_import_kW
comparison_vs_no_request: {<case>: {export_capability_change_kW[96], import_capability_change_kW[96],
              area_pct_of_no_request[96], soc_mean_change_pct[96], stored_energy_change_kWh[96],
              soc_bound_import_change_kW[96], soc_bound_export_change_kW[96], key_numbers{...}}}
polygons[] : {case, slot, day, time, requested, source, angles_deg[12], points[12][dP,dQ] ordered by search direction
              0..330 deg, area, operating_point, p1_baseline_point, requested_point, delivered_point, soc_mean_pct}
              (points null + reason where no FOR exists). Times: day 1 06:00, 07:00, 12:30, 17:00, 19:30, 21:30;
              day 2 07:00, 12:30 (null for both cases), 15:00, 17:00, 21:30.
```

`for_time.csv`: case, slot, day, time, requested, for_source (computed / same-state / empty), dP_min, dP_max, dQ_min,
dQ_max, area, export_capability_kW, import_capability_kW, soc_mean_pct, stored_energy_above_floor_kWh,
soc_bound_export_kW, soc_bound_import_kW, op_dP, op_dQ, req_dP, req_dQ, del_dP, del_dQ, service_dP_vs_p1.

### guarantee.json

```
generated, definitions{...}, no_request{lane, tag},
guarantee_on | guarantee_relaxed: {tag, lane, requests_served, requested_slots[], export_served_kWh,
    export_vs_no_request_realised_kWh, extra_import_inside_requested{prosumers_above_1Wh, total_kWh, worst_kWh,
    worst_prosumer}, extra_import_outside_requested{same}, released_services_EXECFAIL,
    pre_request_max_soc_gap_vs_no_request, mean_soc_end_day1_pct, mean_soc_end_day1_no_request_pct,
    per_prosumer[46]{prosumer, aggregator, inside_kWh, outside_kWh}}
```

Definitions: export served = dt * sum over requested slots of max(0, -(requested P - P1-baseline P)) (FRQ `dP_kW`,
same as `analyze_paper1.py`); extra import = house import of the run minus the no-request run (`SCT_exec imp1_kWh`,
both days), split by the run's `svc` flag (inside = the 28 requested half-hours); "above 1 Wh" = > 0.001 kWh; total =
fleet sum; worst = max over the 46 prosumers.

## 7. Caveats

- FORs exist only where the model built them (section 2). Day-2 00:30-14:30 has no FOR in any run; the day-2 recovery
  is shown with SOC, stored energy and the SOC bounds, plus the identical FORs from 15:00.
- Same-state FORs assume the model is deterministic given the per-prosumer SOC, the frozen slot plan and the profiles
  (identical on both days). They are copies, not new solves; the chart should not mark them differently unless asked.
- SOC bounds are BESS-only (converter rating and stored energy, eta = 0.949, DOD 0.9, 4.2 kWh, 3.6 kW). Import side:
  matches dP_max within 3.0 kW (no request) / 4.3 kW (export run) at every computed slot, so it is a fair stand-in.
  Export side: NOT a stand-in. It overstates -dP_min by 2-79 kW without service and by up to 155 kW with service,
  because the self-consumption guarantee reserves stored energy for later household imports (and voltage limits bind
  at midday). Do not plot it as the FOR.
- The all-idle reference is an estimate (section 2): +-3 kW / +-4 kvar.
- The export runs in `for_time.json` are the current-commit N3 pair; the no-request run is the N2 one (older commit;
  it has no P2 dispatch, so the commit change should not touch it). Both scripts check that each export run equals it
  exactly (all 46 SOC) before the first request; it does for all runs used here.
- With the guarantee relaxed, the export-side SOC bound matches -dP_min within 3 kW at the requested slots, but there
  both are near 0 (empty BESS); it is not a general validation of that bound.
- dQ ranges reach +-170 kvar, slightly above the 165.6 kVA converter rating: network reactive effects plus the
  idle-reference estimate.

---

## Provenance: data_tulio/README_sweeps.md

# One-day sweeps for the detailed results slides (TR4)

Files in this folder:
- `sweeps.json`: all data (schema below).
- `validation_sweeps.json`: 329 checks, each with expected value, reproduced value, pass/fail and source.
- `fig_3d_criteria.png`: the R2 figure.
- `scripts\build_sweeps.py`, `scripts\validate_sweeps.py`, `scripts\fig_3d_criteria.py`: the code that made them.

To regenerate, run `python -B build_sweeps.py`, then `python -B validate_sweeps.py` (set `PYTHONIOENCODING=utf-8` so the console can print the output), then `python -B fig_3d_criteria.py`. The scripts only read the lane `C:\Users\LAPTOP-01\master\paper1-runs\N2` and write only into `deck\data_tulio\`.

Every run used has a `done` file with "Return value = 0". All 576 directional solves of every run are Optimal, checked by an assert.

## Conventions (same as `deck\data\scripts\build.py`)

- **Code reused.**
  - From `analyze_fair.py`: `corners`, `area` (shoelace on the 12 points), `read`, `done`, `info_lines`.
  - From `analyze_paper1.py`: `clock`, `read`.
- **Time.** `time[i]` = `clock(target)` = HH:MM at the start of flexibility slot k+1. Index i corresponds to rolling step `now` = i+1, so step 48 is 00:00. `hour[i]` = 0.5·(i+1), so 00:30 → 0.5 and 00:00 → 24; it is the z coordinate of the figure.
- **Coordinates.**
  - Polygon points are [ΔP kW, ΔQ kvar], the deviation of the interface exchange (`FOR_rolling` `P`, `Q` × 1000) from the estimated all-idle exchange, with + = import.
  - All-idle estimate: P_idle = `P_PCC1` − Σ`Pexec`, and Q_idle = `Q_PCC1` − Σ`Qinv1`. Both come from `FOR_rolling_soc_…_FairEffHead1.csv` at `now` = target.
  - The estimate is identical to `fair.json` `idle_exchange_per_step`, with accuracy ≤ 0.93 kW.
  - The 12 points are ordered θ = 0°, 30°, …, 330° (0° = +ΔP, 90° = +ΔQ).
- **Area and ratio.** Area is in kW·kvar. `area_ratio` is the per-step ratio to the reference `_FairEffHead1` at the same step. Means are means of the 48 per-step ratios, as in `fair.json`.
  - Areas and ratios do not depend on the idle estimate.
  - Neither do the BESS-level quantities (ΣU, ΣD, Σ ΔP^b, ζ), nor the export/import loss vs the reference at the same step.

## Cases (`cases[id]`: label, source_tag, floor, headroom_limits, mu_f, criterion, scope, commit, FAIR settings line)

Each tag is the prefix `_REF_SWEEP_free_today_a2x4p8fin_TR4` followed by the suffix below. The commit is read from the `FAIR settings` line of `SCT_info`: 2f68674 if the line contains `FairEffHead 1`, else 866c053.

| id | suffix | floor | limits | μ^f | commit |
|---|---|---|---|---|---|
| ref | `_FairEffHead1` | energy | on | 0.2 | 2f68674 |
| CP_intra / CP_nw | `_FairCrit1_FairScope{1,2}_FairEffHead1` | energy | on | 0.2 | 2f68674 |
| HP_intra / HP_nw | `_FairCrit2_FairScope{1,2}_FairEffHead1` | energy | on | 0.2 | 2f68674 |
| HB_intra / HB_nw | `_FairCrit3_FairScope{1,2}_FairEps0.1_FairEffHead1` | energy | on | 0.2 | 2f68674 |
| {CP,HP,HB}_{intra,nw}_oldfloor | the same without `_FairEffHead1` | (1−DOD)Ē | on | 0.2 | 866c053 |
| ref_oldfloor | `_FairBox1` | old | on | 0.2 | 866c053 |
| ref_nolimits | `_FairBox0` | old | off | 0.2 | 866c053 |
| CP_intra_nolimits | `_FairCrit1_FairScope1_FairBox0_FairAllowNoBox1` | old | off | 0.2 | 866c053 |
| HB_intra_nolimits | `_FairCrit3_FairScope1_FairEps0.1_FairBox0_FairAllowNoBox1` | old | off | 0.2 | 866c053 |
| muf0 | `_P2SlotPen0` | old | on | 0 | 866c053 |
| muf01 | `_P2SlotPen0.1` | old | on | 0.1 | 866c053 |
| muf0_nolimits | `_FairBox0_P2SlotPen0` | old | off | 0 | 866c053 |
| HP_intra_oldfloor_muf01 (extra) | `_FairCrit2_FairScope1_P2SlotPen0.1` | old | on | 0.1 | 866c053 |

`_FairCrit2_FairScope1_FairEffHead0` also exists in the lane. It was not used.

## Schema of `sweeps.json`

**Top level:**
- `time`[48], `hour`[48];
- `coordinates`, `idle_exchange` {`P_kW`, `Q_kvar`}[48];
- `cases`, `per_case`, `crit`, `reference_voltage`, `summary`, `checks`.

**`per_case[id]`** (source: `FOR_rolling<tag>.csv` columns `now`, `angle_deg`, `P`, `Q`):
- `polygons`[48][12][2] = [ΔP, ΔQ], 2 dp;
- `area_kWkvar`[48], 1 dp;
- `dP_min_kW`[48], `dP_max_kW`[48] = min/max of ΔP over the 12 points;
- `area_ratio`[48] vs ref (10 dp; round to 4 dp to compare with `fair.json`);
- old-floor and μ^f cases also carry `area_ratio_vs_ref_oldfloor`[48], against `_FairBox1` (as in `muf.json`).

**`crit[id]`** (source: `FOR_rolling_crit<tag>.csv`):
- `groups` = `["Agg1","Agg2","Agg3"]`, or `["ALL"]` for network-wide runs.
- `deg0` and `deg180`, each holding:
  - `{group: {sum_dP_kW, sum_U_kW, sum_D_kW, zcp, zu, zd}[48]}`, read from the columns of the same name at `angle_deg` 0 / 180. ζ values are given to 4 dp and kW to 3 dp; null where the column is empty (zcp only exists for CP; zu, zd for HP/HB).
  - `fleet` {`sum_dP_kW`, `sum_U_kW`, `sum_D_kW`}[48] = sum over the groups.
  - `per_aggregator_dP_from_fair_kW` {Agg1..3}[48] = 1000·`sumP_pu` (`FOR_rolling_fair<tag>.csv`) minus the reference's per-aggregator P1 baseline. This gives per-aggregator Σ ΔP^b_s for the network-wide runs too. The baseline is S0 = 1000·`sumP_pu` − `sum_dP_kW` of the reference, constant over the 12 directions within 0.001 kW.
    - Checks: S0 is the same in every run within 0.0008 kW, and for intra runs this field equals the crit `sum_dP_kW` within 0.001 kW.
- U_s and D_s sums are identical (to 0.0 kW) in every run with the same floor, so ΣU and ΣD of `ref` (energy floor) and `ref_oldfloor` (old floor) serve all cases.

**`reference_voltage`** (source: `FOR_rolling_…_FairEffHead1.csv` `VmaxTrue`, `OVviol`):
- `VmaxTrue_max_pu`[48] and its `angle_deg`[48], the max over the 12 directions;
- `VmaxTrue_180deg_pu`[48];
- `OVviol_max`[48];
- `times_at_or_above_1.0995_pu`.

**`summary`:**
- `capability_mean_kW[id]` = {`export_mean_kW`: mean over 48 of −dP_min, `import_mean_kW`: mean of dP_max}.
- `area_ratio_stats[id]` = {mean, min, min_time, max, max_time, times_below_1pct, times_above_1.0005}, vs ref. `area_ratio_stats_vs_ref_oldfloor[id]` is the same against `_FairBox1`.
- `volume_ratio[id]` = Σ_t area / Σ_t ref area. `width_ratio_mean[id]` = mean of (dP_max − dP_min) / the same for ref.
- `R1`:
  - the BESS-level fleet sums from crit, with shortfall(180°) = ΣD + Σ ΔP^b and gap(0°) = ΣU − Σ ΔP^b;
  - the steps above 0.1 and above 1 kW, the maximum and its time;
  - the old-floor overstatement of ΣD;
  - `sumD_at` / `sumU_at` at selected times.
- `R5[id]`:
  - the export loss = dP_min(case) − dP_min(ref) and the import loss = dP_max(ref) − dP_max(case), both at the same step: max, time, and the steps above 0.1 kW;
  - for HP/HB, the per-step export loss above 0.05 kW, the window where the loss exceeds 0.5 kW, and the minimum area ratio outside that window.
- `R6[id][time]`: at 07:30, 12:30, 15:00, 18:00 and 21:30, per group:
  - share180 = −Σ ΔP^b / ΣD at 180° and share0 = Σ ΔP^b / ΣU at 0°, with the raw sums and zcp, zu, zd at 0° and 180°;
  - for network-wide runs, `AggN_from_fair` shares as well;
  - plus `dP_min_kW`, `dP_max_kW` and `area_ratio` of the case at that step;
  - cases: ref, CP/HP/HB intra and nw, and HP_intra_oldfloor.
- `scope_contrast_15:00`, `mixed_180deg_HP_intra` (zu > 1e-3 and zd > 1e-3 at 180°).
- `muf_limits[id]`: simultaneous solves (Σ`n_cyc` > 0), max `cyc_kW`, mean `thr_kW`, area ratio vs `_FairBox1`, ΔP at 0° vs `_FairBox1`, and limit exceedance (`box_up_viol_kW` / `box_dn_viol_kW` > 1 W).
- `ref_vs_ref_oldfloor`, `reference_area`.

## Validation

`validate_sweeps.py` runs 329 checks: **326 pass, 1 mismatch, 2 informational.**

- **Against `deck\data\fair.json` (74 checks, all pass).** At the stated precision:
  - all 48 area ratios for CP/HP/HB × intra/nw × both floors (4 dp, exact) and their mean, min, min_time and below-1 % times;
  - the reference area (0 dp, ≤ 1);
  - the idle exchange P/Q (2 dp, exact);
  - `dP_range_intra_energy_floor` (2 dp, exact);
  - all five polygons (reference, HB, HP, CP, HP old floor) at 07:30, 12:30 and 18:00 (2 dp, exact).
- **Against `deck\data\muf.json` (60 checks, all pass).** For the five μ^f/limits cases:
  - 48 area ratios vs `_FairBox1` (4 dp, exact) and the FOR area;
  - simultaneous solves, max simultaneous kW, mean throughput, area-ratio mean/max/max_time, ΔP at 0° mean/max, solves exceeding the limits, and max exceedance.
- **Brief's means:** all reproduced exactly — CP 51.48 / 40.27, HP 98.71 / 98.58, HB 99.83 / 99.77, old-floor HP 73.83 / 63.42, old-floor HB 82.20 / 73.72 %.
- **Planners' and consensus quoted values (185 checks).** All reproduce except:
  - **ΣU at 00:30:** plan B says 174.6 kW, the data give **174.5 kW** (174.47). Plan B summed rounded group values.
  - **R1 window:** the reference falls short of ΣD_s by > 0.1 kW at 10:00–**15:00** (15:00 is only 0.12 kW). By > 1 kW the window is exactly 10:00–14:30. Use "> 1 kW" wording (consensus amendment 6).
  - **Voltage (not in the automated list).**
    - Plan A says "V_max = 1.098 pu at the 180° point (12:00)". At 12:00, 180°, `VmaxTrue` = 1.0957; 1.0976 is at 12:30, 180° (that matches plan B, "1.098 at 12:30").
    - Over all 12 directions, `VmaxTrue` = 1.1000 pu (OVviol = 0) at **09:30–14:00**, every time at θ = 210°, so it is not only 12:00–12:30.
    - Suggested wording: "voltage reaches 1.10 pu in some directions at 09:30–14:00".
    - That 1.10 pu is the limit is inferred from the clamp at exactly 1.10000 with zero OVviol; it has not been confirmed in the case-study table.
  - **Rounding only:** plan A quotes HP intra ζ↓ at Agg3 (12:30) as 0.9996, while the consensus says 1.000; both are the same value (0.9996).

## Caveats

1. **Old-floor runs come from an earlier commit.** All runs without `_FairEffHead1` (old floor, `_FairBox1`, `_FairBox0`, μ^f runs, no-limit criteria) are commit 866c053. The energy-floor runs are 2f68674.
   - The reference FOR is the same in both: area ratio 0.99999–1.00001, per point ≤ 0.023 kW / 0.108 kvar (`summary.ref_vs_ref_oldfloor`).
   - The P1 baseline is identical: per-aggregator S0 equal within 0.0008 kW.
   - No μ^f = 0 or no-limit run exists with the energy floor.
2. **Per-prosumer U_s and D_s are not logged in these one-day runs.** Only group sums (`sum_U_kW`, `sum_D_kW`) and group factors are, so statements about single BESS follow from (14)–(17), not from logs. Per-prosumer values are logged only in the N3 service runs (`FOR_rolling_offer_*`).
3. **HB factors are not unique.** When the band is slack, ζ↑ and ζ↓ are not unique (e.g. 12:30 Agg3: ζ↓ = 0.900, ζ↑ = 0.050, while the share used is 0.977). They are in `crit` for completeness; do not plot them. Plot shares (Σ ΔP^b / ΣD) instead.
4. **HB area > 1 is an artefact.**
   - HB area ratios exceed 1 at 18:00–22:00 (max 1.0054 intra, 1.0062 nw, both at 19:00).
   - This is the 12-point hull: points slide along flat faces and each maximises projection − μ^f·throughput. It is not an enlargement.
   - `ref_nolimits` also shows ratios up to 1.0005.
5. **ΣΔP^b is not the interface ΔP.** Σ ΔP^b is BESS-level, from the P1 baseline. The interface ΔP also includes the baseline's distance from all-idle and loss changes (e.g. 07:30, 180°: Σ ΔP^b = −180.4 kW vs interface ΔP_min = −143.15 kW).
6. **The CP no-limits run cycles.** CP_intra_nolimits has 55 directional solves with simultaneous charging/discharging (max 19.6 kW) and exceeds (14) by up to 0.361 kW per BESS. HB_intra_nolimits has 0 such solves, and its exceedance is 0.0009 kW.
7. **Results scope.** TR4 only, one profile set, clear-sky day. The polygons are through 12 boundary points.

## Figure `fig_3d_criteria.png`

- **Format:** 12.5 × 4.6 in, 250 dpi, 1 × 4 panels.
- **Panels:** reference, CP, HP and HB, all intra-aggregator with the energy floor, built from `per_case[*].polygons`.
- **Layout choice:** 1 × 4 because it fits the slide's 11.8-in content width at about 95 % scale, keeping 8–12 pt text. A 2 × 2 layout at 12.5 × 8 in would have to shrink to about 55 % to fit under a slide title, and its labels would fall below 6 pt.
- **What each panel shows:**
  - a lofted translucent surface (α 0.13), with every second slice outlined thin;
  - in CP/HP/HB, the reference as a faint grey wireframe (every second slice);
  - the slices at 07:30, 12:30, 18:00 and 21:30 thicker, in the criterion colour, and labelled on the reference panel.
- **Axes and view:** orthographic projection, elevation 20°, azimuth −58° in all panels, ΔP and ΔQ limited to ±180.
- **Titles:** the mean area kept vs the reference (CP 51.5 %, HP 98.7 %, HB 99.8 %).
- **Font:** Segoe UI, because the deck font MADE TOMMY is not installed for matplotlib.

## Appendix: all planner/brief checks (expected vs reproduced)

| item | source | expected | reproduced | match |
|---|---|---|---|---|
| brief: mean area ratio CP_intra (%) | brief | 51.48 | 51.48 | yes |
| brief: mean area ratio CP_nw (%) | brief | 40.27 | 40.27 | yes |
| brief: mean area ratio HP_intra (%) | brief | 98.71 | 98.71 | yes |
| brief: mean area ratio HP_nw (%) | brief | 98.58 | 98.58 | yes |
| brief: mean area ratio HB_intra (%) | brief | 99.83 | 99.83 | yes |
| brief: mean area ratio HB_nw (%) | brief | 99.77 | 99.77 | yes |
| brief: mean area ratio HP_intra_oldfloor (%) | brief | 73.83 | 73.83 | yes |
| brief: mean area ratio HP_nw_oldfloor (%) | brief | 63.42 | 63.42 | yes |
| brief: mean area ratio HB_intra_oldfloor (%) | brief | 82.2 | 82.2 | yes |
| brief: mean area ratio HB_nw_oldfloor (%) | brief | 73.72 | 73.72 | yes |
| HP intra ζ↓ 12:30 Agg1 | A/B/consensus | 0.694 | 0.6935 | yes |
| HP intra ζ↓ 12:30 Agg2 | A/B/consensus | 0.993 | 0.9927 | yes |
| HP intra ζ↓ 12:30 Agg3 | A/B/consensus | 1.0 | 0.9996 | yes |
| HP nw ζ↓ 12:30 | A/B | 0.865 | 0.8651 | yes |
| ref max shortfall at 180° (kW) | A/B/consensus | 7.1 | 7.1 | yes |
| old-floor ΣD at 19:00 (kW) | A/consensus | 156.6 | 156.6 | yes |
| energy-floor ΣD at 19:00 (kW) | A/consensus | 77.4 | 77.4 | yes |
| ref Σ ΔP^b 180° at 19:00 (kW) | A | -77.4 | -77.4 | yes |
| ΣD at 12:00 (kW) | A | 169.6 | 169.6 | yes |
| ref Σ ΔP^b 180° at 12:00 (kW) | A | -162.5 | -162.5 | yes |
| ΣU at 12:30 (kW) | A | 1.6 | 1.6 | yes |
| ref Σ ΔP^b 0° at 12:30 (kW) | A | 1.6 | 1.6 | yes |
| ΣU at 00:30 (kW) | B | 174.6 | 174.5 | **no** |
| ΣD at 00:30 (kW) | B | 48.1 | 48.123 | yes |
| ΣD at 07:30 (kW) | B | 180.4 | 180.4 | yes |
| ΣD at 06:00 energy floor (kW) | C | 107.6 | 107.626 | yes |
| ΣD at 06:00 old floor (kW) | C | 111.3 | 111.307 | yes |
| mean export capability ref (kW) | B/consensus | 108.3 | 108.34 | yes |
| mean export capability HP_intra (kW) | B/consensus | 106.8 | 106.83 | yes |
| mean export capability HB_intra (kW) | B/consensus | 108.2 | 108.15 | yes |
| mean export capability CP_intra (kW) | B/consensus | 49.7 | 49.71 | yes |
| mean export capability CP_nw (kW) | B/consensus | 31.8 | 31.76 | yes |
| mean import capability ref (kW) | B | 79.8 | 79.79 | yes |
| mean import capability HP_intra (kW) | B | 79.8 | 79.79 | yes |
| mean import capability HB_intra (kW) | B | 79.8 | 79.79 | yes |
| mean import capability CP_intra (kW) | B | 51.2 | 51.18 | yes |
| HP intra largest export loss (kW) | B/consensus | 12.6 | 12.61 | yes |
| HP nw largest export loss (kW) | coordinator | 15.4 | 15.44 | yes |
| ref dP_min 12:00 (kW) | B | -153.8 | -153.79 | yes |
| HP intra dP_min 12:00 (kW) | B | -141.2 | -141.18 | yes |
| ref 12:30 180° Σ ΔP^b Agg1 | A/B | -59.1 | -59.081 | yes |
| ref 12:30 ΣD Agg1 | A/B | 61.5 | 61.47 | yes |
| ref 12:30 180° Σ ΔP^b Agg2 | A/B | -54.3 | -54.346 | yes |
| ref 12:30 ΣD Agg2 | A/B | 57.1 | 57.081 | yes |
| ref 12:30 180° Σ ΔP^b Agg3 | A/B | -45.1 | -45.086 | yes |
| ref 12:30 ΣD Agg3 | A/B | 46.8 | 46.8 | yes |
| ref 12:30 share180 Agg1 (%) | C | 96.1 | 96.11 | yes |
| ref 12:30 share180 Agg2 (%) | C | 95.2 | 95.21 | yes |
| ref 12:30 share180 Agg3 (%) | C | 96.3 | 96.34 | yes |
| HB intra 12:30 share180 Agg1 (%) | C | 89.0 | 88.98 | yes |
| HB intra 12:30 share180 Agg2 (%) | C | 96.3 | 96.32 | yes |
| HB intra 12:30 share180 Agg3 (%) | C | 97.7 | 97.66 | yes |
| HB intra 12:30 Agg3 ζ↓ | B | 0.9 | 0.8997 | yes |
| HB intra 12:30 Agg3 ζ↑ | B | 0.05 | 0.0502 | yes |
| ref 07:30 180° Σ ΔP^b Agg1 | C | -67.8 | -67.766 | yes |
| ref 07:30 180° Σ ΔP^b Agg2 | C | -58.4 | -58.394 | yes |
| ref 07:30 180° Σ ΔP^b Agg3 | C | -54.2 | -54.228 | yes |
| CP intra 06:00 180° ζ Agg1 | A | -0.208 | -0.2076 | yes |
| CP intra 06:00 180° ζ Agg2 | A | -0.258 | -0.2582 | yes |
| CP intra 06:00 180° ζ Agg3 | A | -0.074 | -0.0741 | yes |
| CP intra 18:00 180° |ζ| Agg1 < 2e-5 | A/B | 0.0 | 0.0 | yes |
| CP intra 18:00 0° |ζ| Agg1 ≈ 0 | B | 0.0 | 0.0 | yes |
| CP intra 18:00 180° |ζ| Agg2 < 2e-5 | A/B | 0.0 | 0.0 | yes |
| CP intra 18:00 0° |ζ| Agg2 ≈ 0 | B | 0.0 | 0.0 | yes |
| CP intra 18:00 180° |ζ| Agg3 < 2e-5 | A/B | 0.0 | 0.0 | yes |
| CP intra 18:00 0° |ζ| Agg3 ≈ 0 | B | 0.0 | 0.0 | yes |
| CP intra 12:30 ζ Agg1 | B | -0.808 | -0.8082 | yes |
| CP intra 12:30 ζ Agg2 | B | -0.856 | -0.8558 | yes |
| CP intra 12:30 ζ Agg3 | B | -1.0 | -0.9996 | yes |
| CP intra 15:00 ζ Agg1 | B | -0.672 | -0.6721 | yes |
| CP intra 15:00 ζ Agg2 | B | -0.082 | -0.0819 | yes |
| CP intra 15:00 ζ Agg3 | B | -1.0 | -0.9998 | yes |
| CP nw 15:00 ζ | B/consensus | -0.082 | -0.0819 | yes |
| CP nw 12:30 ζ | B | -0.856 | -0.8558 | yes |
| CP intra dP_min 15:00 (kW) | B/consensus | -92.6 | -92.58 | yes |
| CP nw dP_min 15:00 (kW) | B/consensus | -16.0 | -15.95 | yes |
| 18:00 ΣD energy floor Agg1 | B | 36.4 | 36.354 | yes |
| 18:00 ref-without-limits Σ ΔP^b 180° Agg1 | B | -36.4 | -36.353 | yes |
| 18:00 HP intra ζ↓ Agg1 | B | 1.0 | 1.0 | yes |
| 18:00 ΣD energy floor Agg2 | B | 28.0 | 27.96 | yes |
| 18:00 ref-without-limits Σ ΔP^b 180° Agg2 | B | -28.0 | -27.96 | yes |
| 18:00 HP intra ζ↓ Agg2 | B | 1.0 | 1.0 | yes |
| 18:00 ΣD energy floor Agg3 | B | 20.3 | 20.251 | yes |
| 18:00 ref-without-limits Σ ΔP^b 180° Agg3 | B | -20.3 | -20.251 | yes |
| 18:00 HP intra ζ↓ Agg3 | B | 1.0 | 1.0 | yes |
| 18:00 ΣD old floor Agg1 | B | 60.8 | 60.826 | yes |
| 18:00 ΣD old floor Agg2 | B | 54.3 | 54.331 | yes |
| 18:00 ΣD old floor Agg3 | B | 43.5 | 43.529 | yes |
| HP old floor 18:00 Agg1 ζ↓ | B | 0.0 | 0.0 | yes |
| HP old floor 18:00 Agg2 ζ↑ | B | 0.205 | 0.2046 | yes |
| HP old floor 18:00 Agg2 ζ↓ | B | 0.078 | 0.0784 | yes |
| HP old floor dP_min 18:00 (kW) | B | -10.1 | -10.09 | yes |
| ref dP_min 06:00 | A | -77.0 | -76.98 | yes |
| ref dP_max 06:00 | A | 164.4 | 164.42 | yes |
| CP_intra dP_min 06:00 | A | -1.2 | -1.19 | yes |
| CP_intra dP_max 06:00 | A | 150.0 | 150.02 | yes |
| ref dP_min 22:00 | A | -97.4 | -97.37 | yes |
| ref dP_max 22:00 | A | 115.9 | 115.94 | yes |
| CP_intra dP_min 22:00 | A | -21.5 | -21.45 | yes |
| CP_intra dP_max 22:00 | A | 6.7 | 6.72 | yes |
| ref dP_min 12:30 | A | -154.2 | -154.2 | yes |
| ref dP_max 12:30 | A | 4.9 | 4.94 | yes |
| HP_intra dP_min 12:30 | A | -142.6 | -142.55 | yes |
| HP_intra dP_max 12:30 | A | 4.9 | 4.94 | yes |
| HP_nw dP_min 12:30 | A | -139.9 | -139.95 | yes |
| HP_nw dP_max 12:30 | A | 4.9 | 4.94 | yes |
| CP_nw dP_min 06:00 | A | 17.4 | 17.41 | yes |
| CP_nw dP_max 06:00 | A | 148.6 | 148.62 | yes |
| CP_nw dP_min 12:30 | A | -138.9 | -138.87 | yes |
| CP_nw dP_max 12:30 | A | 3.3 | 3.35 | yes |
| CP_nw dP_min 18:00 | A | -7.2 | -7.19 | yes |
| CP_nw dP_max 18:00 | A | -6.6 | -6.64 | yes |
| CP_nw dP_min 22:00 | A | -21.5 | -21.45 | yes |
| CP_nw dP_max 22:00 | A | 2.3 | 2.34 | yes |
| ref dP_min 18:00 | A/B | -91.4 | -91.37 | yes |
| ref dP_max 18:00 | A/B | 8.9 | 8.92 | yes |
| CP_intra dP_min 18:00 | B | -7.2 | -7.19 | yes |
| CP_intra dP_max 18:00 | B | -6.6 | -6.64 | yes |
| ref dP_min 15:00 | B | -153.8 | -153.81 | yes |
| ref dP_max 15:00 | B | 2.5 | 2.5 | yes |
| CP_intra dP_min 15:00 | B | -92.6 | -92.58 | yes |
| CP_intra dP_max 15:00 | B | 1.8 | 1.79 | yes |
| ref dP_min 21:30 | B | -97.2 | -97.23 | yes |
| ref dP_max 21:30 | B | 101.6 | 101.56 | yes |
| CP_intra dP_min 21:30 | B | -21.7 | -21.71 | yes |
| CP_intra dP_max 21:30 | B | 4.0 | 3.99 | yes |
| ref dP_min 07:30 | B | -143.1 | -143.15 | yes |
| ref dP_max 07:30 | B | 134.3 | 134.26 | yes |
| CP_intra dP_min 07:30 | B | -29.9 | -29.86 | yes |
| CP_intra dP_max 07:30 | B | 64.0 | 64.04 | yes |
| HB intra dP_min 12:30 | A/B | -151.4 | -151.37 | yes |
| CP intra dP_max 20:00 (import capability) | B | -15.9 | -15.9 | yes |
| HP intra export 10:00 (kW) | C | 151 | 151.16 | yes |
| ref export 10:00 (kW) | C | 157 | 157.42 | yes |
| mean width ratio CP_intra (%) | A | 50.7 | 50.71 | yes |
| mean width ratio CP_nw (%) | A | 39.9 | 39.91 | yes |
| mean width ratio HP_intra (%) | A | 99.1 | 99.09 | yes |
| mean width ratio HP_nw (%) | A | 98.9 | 98.9 | yes |
| mean width ratio HB_intra (%) | A | 99.9 | 99.88 | yes |
| mean width ratio HB_nw (%) | A | 99.9 | 99.85 | yes |
| area ratio CP_intra 07:30 (%) | B/C | 39.5 | 39.4523 | yes |
| area ratio HP_intra 07:30 (%) | C | 98.3 | 98.2789 | yes |
| area ratio HB_intra 07:30 (%) | C | 99.9 | 99.9067 | yes |
| area ratio CP_intra 12:30 (%) | C | 92.3 | 92.3035 | yes |
| area ratio HP_intra 12:30 (%) | C | 93.7 | 93.6961 | yes |
| area ratio HB_intra 12:30 (%) | C | 97.5 | 97.4806 | yes |
| area ratio CP_intra 18:00 (%) | C | 0.0 | 0.0023 | yes |
| area ratio HP_intra 18:00 (%) | C | 99.0 | 99.0213 | yes |
| area ratio HB_intra 18:00 (%) | C | 100.2 | 100.1519 | yes |
| area ratio CP_intra 06:00 (%) | A | 60.3 | 60.3119 | yes |
| area ratio CP_nw 06:00 (%) | A | 50.7 | 50.6615 | yes |
| area ratio CP_intra 22:00 (%) | A | 13.7 | 13.6709 | yes |
| area ratio CP_nw 22:00 (%) | A | 11.2 | 11.2438 | yes |
| area ratio HP_intra 22:00 (%) | A | 98.8 | 98.7559 | yes |
| area ratio HP_nw 22:00 (%) | A | 98.7 | 98.7438 | yes |
| area ratio HP_intra_oldfloor 06:00 (%) | A | 75.4 | 75.4295 | yes |
| area ratio HP_intra_oldfloor 18:00 (%) | A/C | 20.5 | 20.5471 | yes |
| area ratio HP_intra_oldfloor 22:00 (%) | A | 71.2 | 71.2017 | yes |
| area ratio HP_intra_oldfloor 17:00 (%) | A | 6.2 | 6.174 | yes |
| area ratio CP_intra 21:30 (%) | C | 12.8 | 12.8467 | yes |
| area ratio CP_nw 07:30 (%) | C | 17.7 | 17.6643 | yes |
| area ratio CP_intra 15:00 (%) | B | 67.7 | 67.6705 | yes |
| area ratio CP_nw 15:00 (%) | B | 11.4 | 11.3691 | yes |
| area ratio HP_intra_oldfloor 18:30 (%) | C | 22.4 | 22.3716 | yes |
| area ratio HP_intra 18:30 (%) | C | 99.1 | 99.0844 | yes |
| area ratio HP_intra 17:00 (%) | A | 98.6 | 98.6207 | yes |
| volume ratio CP_intra (%) | C | 53.4 | 53.36 | yes |
| volume ratio HP_intra (%) | C | 98.8 | 98.82 | yes |
| volume ratio HB_intra (%) | C | 99.85 | 99.85 | yes |
| CP intra no limits mean (%) | A/C | 53.27 | 53.27 | yes |
| HB intra no limits mean (%) | A/C | 82.2 | 82.2 | yes |
| CP intra no limits max exceedance (kW) | A | 0.361 | 0.3607 | yes |
| HB intra no limits max exceedance (kW) | A | 0.0009 | 0.0009 | yes |
| HP intra old floor μ^f 0.1 mean (%) | A/C | 74.45 | 74.45 | yes |
| ref no limits export capability (kW) | B | 108.3 | 108.34 | yes |
| CP intra no limits export capability (kW) | B | 49.7 | 49.71 | yes |
| HB intra old floor export capability (kW) | B | 81.3 | 81.27 | yes |
| HB intra no limits export capability (kW) | B | 81.3 | 81.27 | yes |
| mixed 180° HP intra old floor | consensus | 72 | 72 | yes |
| mixed 180° HP intra energy floor | consensus | 6 | 6 | yes |
| reference area max (kW·kvar) | C | 75543 | 75543.0 | yes |
| reference area min (kW·kvar) | C | 28494 | 28494.0 | yes |
| reference area 07:30 (kW·kvar) | C | 74122 | 74121.6 | yes |
| HP intra min ratio (%) | consensus R3 | 93.7 | 93.7 | yes |
| HP nw min ratio (%) | consensus R3 | 92.52 | 92.52 | yes |
| HB max ratio intra | consensus | 1.0054 | 1.0054 | yes |
| HB max ratio nw | consensus | 1.0062 | 1.0062 | yes |
| R1 shortfall > 0.1 kW window | A/B/consensus | 10:00–14:30 | ['10:00', '10:30', '11:00', '11:30', '12:00', '12:30', '13:00', '13:30', '14:00', '14:30', '15:00'] | see note |
| R1 max shortfall time | A | 12:00 | 12:00 | yes |
| R1 steps reaching ΣU at 0° | A/B | 48 | 48 | yes |
| R5 HP_intra largest export loss time | B/coordinator | 12:00 | 12:00 | yes |
| R5 HP_nw largest export loss time | B/coordinator | 12:00 | 12:00 | yes |

---

## Provenance: data_tulio/README_service.md

# Service data for slides R7, R8, R9 (with vs without TSO export service)

Built 15-oct-2026 from the paper-1 run lanes (read only). Files:

| File | What |
|---|---|
| `service.json` | per-slot FORs (slots 13–40) for 6 cases, area ratios, export served, extra imports, SOC, stored energy, R8 cuts, validation |
| `build_service.py` | builds `service.json` (`python -B build_service.py`, run from `C:\Users\LAPTOP-01\master`, system Python) |
| `fig_3d_service.png` | R7 figure, 12.5 × 4.8 in, 250 dpi (two panels: guarantee on / guarantee relaxed, each over the no-request FOR) |
| `fig_3d_service.py` | builds the figure from `service.json` |

## 1. Provenance (internal names allowed only here)

| Key in `service.json` | Display label | Lane / tag | No-request run used for "extra import" |
|---|---|---|---|
| `no_request` | No TSO request | trajectory N2 `_REF_free_today_a2x4p8fin2_TR4_FairBox1`; FOR from the one-day run N2 `_REF_SWEEP_free_today_a2x4p8fin_TR4_FairBox1` (day-1 executed trajectory identical: max diff 0 over SOC_start, Pexec, P_PCC1, 48 × 46 rows; checked by the script) | – |
| `export_guarantee_on` | Export requests, self-consumption guarantee | N3 `_WC_EXPORT_free_today_a2x4p8fin2_TR4_FairBox1_RollOfferLog1_SCAlpha0` (commit 2f68674 + N3 SCAlpha patch) | N2 `_REF_…_FairBox1` |
| `export_guarantee_relaxed` | Export requests, guarantee relaxed | N3 `…_SCAlpha99` | N2 `_REF_…_FairBox1` |
| `hp_energy_floor` | HP intra-aggregator, energy floor, with requests | N2 `_WC_EXPORT_free_today_a2x4p8fin2_TR4_FairCrit2_FairScope1_FairEffHead1` (2f68674) | N2 `_REF_…_FairCrit2_FairScope1_FairEffHead1` |
| `hp_old_floor` | HP intra-aggregator, previous floor (1−DOD)Ē, with requests | N2 `_WC_EXPORT_…_FairCrit2_FairScope1` (866c053) | N2 `_REF_…_FairCrit2_FairScope1` |
| `no_fairness_older` | Export requests, guarantee on, no fairness (older commit) | N2 `_WC_EXPORT_…_FairBox1` (866c053) | N2 `_REF_…_FairBox1` |

Requests: TSO export request at every flexibility slot 13–40 of day 1 (start 06:00–19:30), the boundary point of
F_{k+1} with the most export (θ = 180°); none on day 2. All 28 are served and delivered exactly in all five export runs
(requested − delivered = 0.0 kW). No non-optimal directional solve in any FOR used. Before the first request every run
has exactly the SOC of its own no-request run.

## 2. Conventions

- Coordinates: deviation (ΔP, ΔQ) in kW / kvar from the all-idle interface exchange, + import. B(t) = P_PCC1 − ΣPexec,
  Q_PCC1 − ΣQinv1 of executed slot t of the no-request run, one B(t) for all cases (same as `data/build_for_time.py`).
  The same estimate from each export run agrees within 3.1 kW / 4.1 kvar (old-floor HP run: 3.7 kW / 3.9 kvar). Areas
  do not depend on B.
- Polygon i = F_{k+1} of slot `slots[i]` (built at step `slots[i]−1`), 12 points ordered by θ = 0, 30, …, 330°.
  Time label = start of the flexibility slot.
- Export served = 0.5 h × Σ max(0, −(requested P − P1-baseline P of the same step)) (FRQ `dP_kW`).
- Extra import = per prosumer, house import of the run minus its own no-request run (SCT_exec `imp1_kWh`, both days),
  split into the 28 requested half-hours (inside) and all other half-hours of the two days (outside).
- Area ratio = shoelace area of the 12-point polygon, HP run / no-fairness export run, same slot.

## 3. Schema of `service.json`

```
meta        : scenario, coordinates, idle_reference(+check per run), polygon_order, slot_mapping, availability,
              no_fairness_runs_agreement (N3 vs N2 no-fairness FOR), state_gap_at_building_steps
slots[28]   : 13..40            times[28] : "06:00".."19:30"
cases.<key> : label, lane, tag, note,
              polygons[28][12][dP,dQ], area[28], dP_min/dP_max/dQ_min/dQ_max[28], export_capability_kW[28] (= −dP_min),
              import_capability_kW[28], built_at_step[28], non_optimal_solves, soc_mean_pct_day1[48] (start of slots 1–48)
              (export cases also) requests, requests_executed, export_served_kWh, requested_point[28], delivered_point[28],
              p1_baseline_point[28], service_vs_p1_baseline[28] (requested − S0, [kW, kvar]),
              extra_import{no_request_run, inside_requested_halfhours{prosumers_above_1Wh, prosumers_above_10Wh,
              fleet_total_kWh, worst_kWh, worst_Wh, worst_prosumer}, outside_requested_halfhours{…}},
              max_abs_requested_minus_delivered_dP_kW, pre_request_max_soc_gap_vs_own_no_request
area_ratios.<num>_vs_<den> : pct[28], mean_pct, min_pct, min_at, min_areas_kWkvar[num,den], max_pct, max_at,
              volume_ratio_pct (Σ areas), slots_at_or_above_99pct
soc_vs_no_fairness_export_run.<a>_vs_<b> : {requested | building_steps | day1}: fleet_mean_abs_diff_mean_pp,
              fleet_mean_abs_diff_max_pp(+_at), single_bess_abs_diff_max_pp(+_at), single_bess_abs_diff_mean_pp
              (requested also fleet_mean_soc_diff_pp_per_slot[28])
stored_energy_above_floor_vs_no_request.<case> : {"d1 20:00" | "d1 23:30" | "d2 00:00": case_kWh, no_request_kWh, change_kWh}
cuts."07:30"|"12:30"|"16:30"|"19:30" : slot, index, and for no_request / export_guarantee_on / export_guarantee_relaxed:
              polygon[12], area, area_pct_of_no_request, dP_range, dQ_range, soc_mean_pct
              (+ requested_point, delivered_point, p1_baseline_point for the export cases)
validation[] : item, expected, reproduced, ok
```

## 4. Validation

| Check | Expected | Reproduced | |
|---|---|---|---|
| 12:30 ΔP range, guarantee on | [−0.9, +161.3] | [−0.9, +161.3] | OK |
| 12:30 ΔP range, no request | [−154.2, +4.9] | [−154.2, +4.9] | OK |
| 16:30 most-export point, guarantee on | +34.9 kW (net charging) | +34.9 kW | OK |
| All slots 13–40, three cases: ΔP/ΔQ ranges, area, mean SOC, requested point vs `data/for_time.json` | – | max diff 0.0 | OK |
| Export served: on / relaxed / HP energy floor / HP old floor / no fairness older | 854.3 / 993.5 / 854.3 / 675.2 / 854.3 | 854.3 / 993.5 / 854.3 / 675.2 / 854.3 kWh | OK |
| Prosumers > 1 Wh more inside: HP old floor / HP energy floor / no fairness | 22 / 0 / 0 | 22 / 0 / 0 | OK |
| Prosumers > 10 Wh more inside: HP old floor | 21 | 21 | OK |
| Worst prosumer inside, HP old floor | 1.099 kWh | 1.099 kWh (three368_A) | OK |
| Worst outside: no fairness older / HP old / HP energy floor | 2.16 / 1.19 / 1.82 Wh | 2.16 / 1.19 / 1.82 Wh | OK |
| Guarantee on / relaxed, > 1 Wh inside; outside (`guarantee.json`) | 0 / 43; 15 / 46 | 0 / 43; 15 / 46 | OK |
| Stored energy above floor at d1 20:00 vs no request, on / relaxed | −46.5 / −150.6 kWh | −46.5 / −150.6 kWh | OK |
| HP energy floor vs no fairness, area ratio mean | 99.36 % | 99.36 % | OK |
| idem, min | 97.8 % at 17:30 (23 044 vs 23 564) | 97.80 % at 17:30 (23 044 vs 23 564) | OK |
| idem, range "97.8–100 %" | – | 97.80–99.98 % (never above 100 %) | OK |
| HP old floor vs no fairness (plan A) | mean 72.5 %, min 26.0 % | mean 72.51 %, min 25.98 % at 18:30 (max 120.6 % at 10:00) | OK |
| Amendment 4: HP energy-floor run within 0.5 pp mean SOC, single BESS up to 19.6 pp | 0.5 / 19.6 pp | 0.50 / 19.64 pp **over day 1, both at 23:00** | see note |

Note on amendment 4: the 0.5 pp / 19.6 pp gaps exist only after the service window (max at 23:00). At the steps that
build the requested FORs (06:00–19:30) the energy-floor HP run has the same state as the no-fairness run: fleet mean
SOC within 0.003 pp, every single BESS within 0.01 pp. So the HP energy-floor area ratio IS like-for-like. Suggested
footnote: "same system state at every requested slot (each BESS within 0.01 pp SOC); the runs diverge only after
20:00 (≤ 0.5 pp fleet mean, ≤ 19.6 pp one BESS, at 23:00)". The old-floor run differs by 20.0 pp fleet mean SOC on
average over the requested slots (max 47.2 pp at 16:00; one BESS 90 pp at 15:30).

The N3 (current commit) and N2 (older commit) no-fairness runs give the same F_{k+1} within 0.02 kW / 0.035 kvar at all
336 points (area ratio 100.00 %), so every ratio is the same against either run (min 97.79 % vs N2).

## 5. Caveats

- Export runs build F_{k+1} only when a request is due: no FOR after 19:30 of day 1 (and none at 20:00–23:30) in any
  service run. The 3-D figure ends at 19:30.
- At 06:00 (first request) the service FOR equals the no-request FOR (same state); the change starts at 06:30.
- The old-floor HP run follows a different SOC trajectory (it served 675.2 kWh, not 854.3), so its area ratio mixes the
  criterion with the state. Show it only as tiles (export served, prosumers importing more), not as a ratio line.
- The all-idle reference is an estimate: ±3.1 kW / ±4.1 kvar (old-floor run 3.7 kW). Ranges near 0 (e.g. −0.9 kW) are
  within that error; the +34.9 kW at 16:30 is not.
- Relaxed vs guarantee on: the relaxed FOR is within 1.3 % of the guarantee-on area at 06:30–10:00 (smaller by ≤ 538
  kW·kvar at 5 slots) and equal or larger from 10:30 on; in the afternoon it is much larger (e.g. 40 652 vs 23 564
  kW·kvar at 17:30). It never requires net charging (export capability 0.2–3.1 kW at every slot after 06:00).
- A 12-point hull; areas are of that polygon.
