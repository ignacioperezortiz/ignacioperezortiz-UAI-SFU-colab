# Figures of the results meeting of 16-Oct-2026

The scripts that produced every figure of `Paper1-results-meeting-Tulio.pptx`, the 25-slide deck of the UAI × SFU results meeting of 16 October 2026 (TR4, one clear-sky day: fairness criteria, μ^f and headroom limits, TSO export service). The computations are those of the deck; only the path handling changed. The usual way to use the package is to rebuild the 3-D figures and the deck from the JSONs committed in `results/paper1-fairness-2026-10`. The JSONs themselves can also be rebuilt from the raw runs.

## Layout

| Path | Role |
|---|---|
| `paths.py` | resolves every location outside the package: `--runs` / `PAPER1_RUNS`, `--out`, `--data`, `--figures`, `MML2OMML_XSL`; checks that the package sits in the repository |
| `make_all.py` | checks the raw inputs, then runs the three steps below in order |
| `data/` | raw runs → JSON: `build.py`, `build_for_time.py`, `guarantee_metrics.py`, `build_sweeps.py`, `build_service.py`; `analyze_fair.py` is their helper; `validate_sweeps.py` is an optional check |
| `figures/` | JSON → 3-D PNGs: `fig_3d_criteria.py`, `fig_3d_service.py` |
| `deck/` | JSON + PNGs → pptx: `build_tulio.py` (entry point), `slides_*.py`, `build_deck.py` (library: slides shared with the 14-Oct team deck), `design.py`, `omml.py` (native equations); `img/` holds the six static pictures |
| `check_reproduction.py` | compares a rebuild with reference files |
| `raw_inputs.sha256` | the 171 raw files the data step reads, with their SHA-256 |

Outputs go to `out/` here (git-ignored) or to `--out DIR`:
- `<out>/data/*.json`, with the same names as in `results/paper1-fairness-2026-10`;
- `<out>/figures/*.png`;
- `<out>/Paper1-results-meeting-Tulio.pptx`.

The deck read `data\*.json` and `data_tulio\*.json`. The file names are the same here, except for the two `service.json`: `data\service.json` is `service_T5.json` and `data_tulio\service.json` is `service_requests.json` (`paths.JSON_NAMES`).

**Dependency in the repository.** `build.py` and `build_sweeps.py` import `scripts/paper1/analyze_paper1.py` (`clock`, `read`, `days`, `DT`, `SCEN`), and `build.py` reads `scripts/paper1/scenarios/WC_EXPORT.json`.

## Install

Python 3.11 or later, in a virtual environment:

```
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r scripts/paper1/figures/meeting_2026_10_16/requirements.txt
```

- **Equations.** They need Office's `MML2OMML.XSL`, which is looked up in the usual Office folders (Office16/Office15, 64- and 32-bit). If it is elsewhere, set `MML2OMML_XSL` to its path.
  - The deck was built with Office Click-to-Run 16.0.14334.20974, whose `MML2OMML.XSL` has SHA-256 `5558E69D8BD6534927C4176BD5D5032D0D4BDC17BDAAB7DE580CA41E996A609B`.
  - Another Office build may write the equations differently. The slides with equations (2–13, 15, 16, 18, 20, 22–24) would then FAIL in `check_reproduction.py` on their slide XML. Charts, workbooks and pictures do not depend on the stylesheet.
- **Byte-identical PNGs.** The 3-D PNGs come out byte-identical only with matplotlib 3.11.1 and the Segoe UI font (Windows). Otherwise only the rendering changes.
- **Font.** The deck uses the font MADE TOMMY. It is needed only to view the pptx as designed, not to build it.

## Run (from the repository root)

```
# usual: 3-D figures and deck from the committed JSONs
python -B scripts/paper1/figures/meeting_2026_10_16/make_all.py --figures-only

# full chain: raw runs -> JSON -> figures -> deck
python -B scripts/paper1/figures/meeting_2026_10_16/make_all.py --runs DIR
```

- **Checks before the data step.** The full chain first compares the 171 raw files under `DIR` with `raw_inputs.sha256` and stops on any missing or different file. `--no-verify` skips that check, for building from other runs.
- **Other options.**
  - `--out DIR` writes somewhere other than `out/`.
  - `--deck-only` builds only the deck; `--data-only` runs only the data step.
  - `--data DIR` sets where `--figures-only` and `--deck-only` read the JSONs, for example the `<out>/data` of an earlier full run. In those modes `--runs` is ignored.
- **Failures.** If a step fails, `make_all.py` stops and names it.

Every script also runs on its own with the same options:

```
python -B scripts/paper1/figures/meeting_2026_10_16/data/build_sweeps.py --runs DIR --out OUT
python -B scripts/paper1/figures/meeting_2026_10_16/data/guarantee_metrics.py --runs DIR --out OUT --on N3/_WC_EXPORT_free_today_a2x4p8fin2_TR4_FairBox1_RollOfferLog1_SCAlpha0 --relaxed N3/_WC_EXPORT_free_today_a2x4p8fin2_TR4_FairBox1_RollOfferLog1_SCAlpha99 --ref N2/_REF_free_today_a2x4p8fin2_TR4_FairBox1
python -B scripts/paper1/figures/meeting_2026_10_16/figures/fig_3d_service.py --compact --data DIR
python -B scripts/paper1/figures/meeting_2026_10_16/deck/build_tulio.py --data DIR --figures DIR
```

- **`build_service.py` runs last.** It is a consistency check of the rebuild: it compares its output with `for_time.json`, `guarantee.json` and `service_T5.json` in the same `<out>/data`, and stops if they are missing.
  - It prints 58 checks: 57 OK and 1 FAIL ("amendment 4 restricted to requested slots 13-40").
  - The FAIL is expected: the planning note it tests was wrong. The 19.6 pp gap holds over day 1; within the requested slots the gap is 0.01 pp, as slide 21 says.
- **`validate_sweeps.py`** checks the committed JSONs unless given `--data <out>/data`. It prints 329 checks: 326 OK, 1 mismatch (ΣU at 00:30, 174.5 vs a quoted 174.6) and 2 informative.
- **Missing 3-D PNGs.** `build_tulio.py` places the 3-D PNGs from `<out>/figures` (or `--figures`). If one is missing, it prints a WARNING and slide 14 or 19 gets a "pending" box.

## Raw inputs

The data step reads 171 files (28.1 MB) from lanes N2 and N3 of the case-study runs, the `paper1-runs` folder that `scripts/paper1/run_paper1.py` writes. They are listed with their SHA-256 in `raw_inputs.sha256`. They are bundled in **`meeting-2026-10-16_raw_inputs.zip`** (2.9 MB) in the shared case-study folder `CaseStudy/raw/`:

SHA-256 `766b9f603c5f7ebfa68951e216890e6f6e04552b38ce020e936d507d5e36d9d3`

**Pointing the scripts at the raw files.**
- Unzip the bundle to a short path, because of the 260-character path limit of Windows (the longest member path is 115 characters). You get `N2/` and `N3/`.
- Pass that folder as `--runs DIR`, or set `PAPER1_RUNS=DIR`.
- Without either, the scripts read `../paper1-runs` next to the repository, the same default as `run_paper1.py --work`. They print a note when they do. That folder may hold other runs with the same tags; `make_all.py` would then stop at its check.
- A folder without `N2/` and `N3/` stops every data script with a message naming where the folder came from.
- **Aggregator labels.** `guarantee_metrics.py` takes each prosumer's aggregator from the first `FOR_rolling_offer_*.csv` larger than 1 kB in N1, N2 and N3. In the bundle that file is the offer log of the N3 `…_SCAlpha0` run. With other lanes present it may pick another log; only the `aggregator` field of `per_prosumer` in `guarantee.json` could change.
- **Fallback run.** `build_for_time.py` falls back to N2 `EXP_FairBox1` if the N3 `…_SCAlpha0` run is missing, and prints a WARNING when it does.

Run tags in the table below:
- **`SW`** = `_REF_SWEEP_free_today_a2x4p8fin_TR4`: one day, F_{k+1} at every step, lane N2. Its suffixes are:
  - `_FairEffHead1`: reference, energy floor;
  - `_FairCrit{1,2,3}_FairScope{1,2}[_FairEps0.1][_FairEffHead1]`: CP / HP / HB, intra-aggregator / network-wide, energy floor / earlier floor;
  - `_FairBox1`: reference, earlier floor, μ^f = 0.2;
  - `_P2SlotPen0.1` and `_P2SlotPen0`: μ^f = 0.1 and 0;
  - `_FairBox0[...]`: headroom limits off.
- **`EXP`** = `_WC_EXPORT_free_today_a2x4p8fin2_TR4` and **`REF`** = `_REF_free_today_a2x4p8fin2_TR4`: two days, with TSO export requests 06:00–19:30 on day 1 and without requests. Lane N2, with the suffixes `_FairBox1` (no fairness), `_FairCrit2_FairScope1` (HP, earlier floor) and `_FairCrit2_FairScope1_FairEffHead1` (HP, energy floor).
- **`EXP·α0`** and **`EXP·α99`** = `EXP_FairBox1_RollOfferLog1_SCAlpha0` (guarantee on) and `…_SCAlpha99` (guarantee relaxed), lane N3.

Model commits and the caveat on the N3 pair: `results/paper1-fairness-2026-10/README.md`.

## Figures

Native charts live inside `<out>/Paper1-results-meeting-Tulio.pptx`. "Raw runs" names the runs behind the JSON keys used.

| Slide | What it shows | Script (file:function) | Data file: keys | Raw runs | Output |
|---|---|---|---|---|---|
| 10 | ΔP range of F_{k+1} over day 1 and mean SOC, without requests vs export requests (2 charts) | `deck/slides_data.py:s_for_time` | `for_time.json`: `slots`, `cases.{no_request,export_guarantee_on}.series` (`dP_min`, `dP_max`, `soc_mean_pct`, `requested`) | N2 `REF_FairBox1`, N2 `SW_FairBox1`, N3 `EXP·α0` | pptx, slide 10 |
| 11 | left: solves with simultaneous charging (shapes) and table by μ^f; right: export service and extra imports, guarantee on vs relaxed (2 bar charts + table) | `deck/slides_data.py:s_results_muf_guarantee`, `guarantee_panel` | `muf.json`: `summary.{muf_0,muf_0.1,muf_0.2}`; `guarantee.json`: `guarantee_on`, `guarantee_relaxed` (`export_served_kWh`, `extra_import_outside_requested`, `per_prosumer`) | N2 `SW_FairBox1`, `SW_P2SlotPen0.1`, `SW_P2SlotPen0`; N3 `EXP·α0`, `EXP·α99`; N2 `REF_FairBox1` | pptx, slide 11 |
| 12 | F_{k+1} at 07:30 for the reference, CP, HP and HB; mean area by criterion and scope (2 charts) | `deck/slides_data.py:s_results_fairness` | `fair.json`: `polygons.steps[07:30]` (`FOR`, `area_ratio`), `summary["energy floor"]` | N2 `SW_FairEffHead1`, `SW_FairCrit*_FairScope*…_FairEffHead1` | pptx, slide 12 |
| 13 | ΣU_s, ΣD_s (both floors) and ΣΔP^b_s at 0°/180° over the day | `deck/slides_res3.py:s_headroom_reach` | `sweeps.json`: `time`, `crit.{ref,ref_oldfloor}.{deg0,deg180}.fleet`, `summary.R1` | N2 `SW_FairEffHead1`, `SW_FairBox1` | pptx, slide 13 |
| 14 | F_{k+1} over the day in 3-D: reference, CP, HP, HB (intra-aggregator, energy floor) | `figures/fig_3d_criteria.py` (module level); placed by `deck/slides_res3.py:s_criteria_3d` | `sweeps.json`: `time`, `hour`, `per_case.{ref,CP_intra,HP_intra,HB_intra}.polygons`, `summary.area_ratio_stats` | N2 `SW_FairEffHead1`, `SW_FairCrit*_FairScope1…_FairEffHead1` | `<out>/figures/fig_3d_criteria.png` → slide 14 |
| 15 | area kept per step, CP / HP / HB × intra / network-wide | `deck/slides_res.py:s_area_day` | `fair.json`: `time`, `area_ratio["energy floor"]`, `summary["energy floor"]` | N2 `SW_FairEffHead1`, `SW_FairCrit*…_FairEffHead1` | pptx, slide 15 |
| 16 | ΔP–ΔQ cuts at 07:30, 12:30, 18:00 and 21:30 by criterion (4 charts) | `deck/slides_res3.py:s_criteria_cuts` (+ `slides_res2.py:poly_chart`) | `sweeps.json`: `per_case.{ref,CP_intra,HP_intra,HB_intra}` (`polygons`, `area_ratio`, `dP_min_kW`, `dP_max_kW`) | as slide 14 | pptx, slide 16 |
| 17 | export and import capability per step (2 charts) | `deck/slides_res3.py:s_p_only` | `sweeps.json`: `per_case.*.{dP_min_kW,dP_max_kW}`, `summary.capability_mean_kW`, `summary.R5` | N2 `SW_FairEffHead1`, `SW_FairCrit*…_FairEffHead1` | pptx, slide 17 |
| 18 | share of each aggregator's ΣD_s used at 180°, 12:30 | `deck/slides_res3.py:s_mechanism` | `sweeps.json`: `summary.R6.{ref,HP_intra,HP_nw,CP_intra,CP_nw}["12:30"]` | N2 `SW_FairEffHead1`, `SW_FairCrit{1,2}_FairScope{1,2}_FairEffHead1` | pptx, slide 18 |
| 19 | F_{k+1} 06:00–19:30 in 3-D, export requests with the guarantee on and relaxed vs no request | `figures/fig_3d_service.py --compact` (module level); placed by `deck/slides_res2.py:s_service_3d` | `service_requests.json`: `times`, `cases.{no_request,export_guarantee_on,export_guarantee_relaxed}.polygons` | N3 `EXP·α0`, `EXP·α99`; N2 `REF_FairBox1`, `SW_FairBox1` | `<out>/figures/fig_3d_service_compact.png` → slide 19 |
| 20 | ΔP–ΔQ cuts at 07:30, 12:30, 16:30 and 19:30 with and without service (4 charts) | `deck/slides_res2.py:s_service_cuts` | `service_requests.json`: `cuts` | as slide 19 | pptx, slide 20 |
| 21 | HP area vs no fairness per requested slot; service tiles | `deck/slides_res2.py:s_service_hp` | `service_requests.json`: `times`, `area_ratios.hp_energy_floor_vs_export_guarantee_on`, `cases.{export_guarantee_on,hp_energy_floor,hp_old_floor}` | N3 `EXP·α0`; N2 `EXP_FairCrit2_FairScope1[_FairEffHead1]` and their `REF` | pptx, slide 21 |
| 22 | mean area with the earlier vs the energy floor (dot plot drawn with shapes); HP service tiles | `deck/slides_res.py:s_floor` | `fair.json`: `summary`; `service_T5.json`: `summary.{HP_old_floor,HP_energy_floor,no_fairness}`, `mixing_180deg` | N2 `SW_FairCrit*` (both floors); N2 `EXP`/`REF` `_FairBox1`, `_FairCrit2_FairScope1[_FairEffHead1]` | pptx, slide 22 |
| 23 | μ^f × headroom limits: table and area change per step | `deck/slides_res.py:s_muf_limits` | `muf.json`: `summary`, `per_step.{muf_0_nolimits,muf_0,muf_0.1}.area_ratio` | N2 `SW_FairBox1`, `SW_P2SlotPen0.1`, `SW_P2SlotPen0`, `SW_FairBox0`, `SW_FairBox0_P2SlotPen0` | pptx, slide 23 |
| 24 | summary table of results and sensitivities (no chart) | `deck/slides_res3.py:s_summary` | `sweeps.json`: `summary.area_ratio_stats` (the area-% column) | as slides 14 and 23 | pptx, slide 24 |

**Static pictures** (`deck/img/`, placed as they are):
- **Logos.** `logo_uai.png` and `logo_sfu.png` (slide 1) are copies of the institutional logos; no script makes them.
- **From the compiled draft.** `fig1_framework.png` (slide 3, Fig. 1) and `fig3a.png` (slide 4, Fig. 3a) are cut by `deck/extract_vector.py --pdf FILE` (needs PyMuPDF). FILE is `vista-previa-v63-con-fairness-2026-10-13.pdf`, in `00-documentation/escritura/decision-criterios-fairness/fuente/subseccion-fairness/` of the shared project folder 05_UAI-SFU-COLAB.
- **From the network figure.** `network_mv.png` and `network_tr4.png` (slide 9, Fig. 4) are cut by `deck/extract_raster.py --png FILE`. FILE is `uk_mv_lv_network_single_tr44.png`, in `04-publication-script/methodology-so-far/` of the same folder.

Both extractors write to `<out>/img`. They reproduce the four committed PNGs byte for byte.

## Numbers typed in the slide code

These numbers are not read from the JSONs, so they must be edited by hand if the data change:
- **Slide 10** (`slides_data.s_for_time`): the two chart annotations ("export side ≈ 0 until early afternoon", "up to +35 kW") and their positions, plus the DOD-floor line at 10 %.
- **Slide 12** (`slides_data.s_results_fairness`): the title ("CP keeps 40–51 % … about 99 %") and the bottom strip: 854 kWh, 74 %, "21 % less export".
- **Slide 18** (`slides_res3.s_mechanism`):
  - the caption: ζ↓ = 0.694 / 0.993 / 1.000, 0.865, 95–96 %;
  - the three tiles: 100 %; 41 / 24 / 41 %; −92.6 vs −16.0 kW, −153.8 kW, −0.082; ζ = 0 at 18:00.
- **Slide 19** (`slides_res2.s_service_3d`): the three boxes under the figure: 148.8 kW, 1.6 / 2.0 kW, ±3 kW; +34.9 kW at 16:30; −46.5 / −150.6 kWh.
- **Slide 24** (`slides_res3.s_summary`):
  - the "Note" column;
  - the μ^f, guarantee and HP-under-service rows: 98.7 · 99.8 %, 51.5 · 82.2 %, 55 / 576, +1.0 · +8.0 %, 505 / 576, 854.3 · 993.5 kWh, 46 / 46, 854.3 · 675.2 kWh, 99.4 %.

Elsewhere, the speaker notes and a few captions also quote numbers and time windows: for example 10:00–14:30 on slides 13 and 17 (and the shaded band on 13), and 17:30–19:30 on slides 14 and 15. The printed checks of `build_service.py` and `validate_sweeps.py` re-derive several of them.

## Verify

The reference deck is `Paper1-results-meeting-Tulio.pptx` (3,159,994 bytes, SHA-256 `c9268fb24a29bea8225cccc3f82c999bfc8cb921385c674f2bd8ab8a4cef2a50`).

```
python -B scripts/paper1/figures/meeting_2026_10_16/check_reproduction.py --ref-pptx FILE --ref results/paper1-fairness-2026-10
```

Here FILE is the reference deck. The script compares:
- **The deck**, slide by slide: slide XML, notes, chart XML, embedded workbooks and pictures (including the two 3-D PNGs), then the parts all slides share.
  - For the workbooks it checks the cell values and every part except their own `docProps`, which hold a save time.
  - Only the deck's `docProps/core.xml` (its save time) is ignored.
- **The JSONs in `<out>/data`**, after a data rebuild, value by value. It ignores `generated` and compares only the last folder name of `lane`.
- **The 3-D PNGs in `<out>/figures`**, byte by byte, then pixel by pixel. This needs a `--ref` folder that holds them, either directly or in `figures/` or `data_tulio/`, as in the deck's source folder.

It prints PASS/FAIL per data file, per 3-D figure and per slide, and exits with status 1 on any FAIL. Other options: `--data DIR` checks other JSONs, and `--pptx FILE` checks another deck.

**SKIP rows after `--figures-only`.** The JSON rows show SKIP ("not rebuilt"), and with `--ref results/paper1-fairness-2026-10` so do the PNG rows ("no reference"). The deck check still covers both 3-D PNGs, as the pictures of slides 14 and 19.

Rebuilding from the zip (full chain) and from the committed JSONs (`--figures-only`) both reproduce the deck. Every slide passes, and only the save times in `docProps` differ.
