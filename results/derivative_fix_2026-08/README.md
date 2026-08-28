# Linearization-derivative fix — all nine transformers, 2026-08-24/26

Two analytic errors in the load/PV current Jacobian were found, fixed, and measured on
every transformer. This folder holds the measurement.

Model change: `MainProject/OPF.ams`, `NetworkModel` → `DeclarationSection Linearization`.
Branch `fix/linearization-derivatives`, commit `e5381fb`.
Runner: `RunAllTrafos_DerivFix` (TR9 run separately as `RunTR9_DerivFix`).

## The two errors

Both had been in the model since the first commit, in the section documented as
*"inherited unchanged from the OPF model of Prof. Luis"*.

**`dIimdVim_Load`** — closing parenthesis one term too late, so the `Q0` cross term was
multiplied by `P0`:

```
before   P0*( Vre0^2 - Vim0^2 + 2*Q0*Vre0*Vim0 ) / (.)^2
after    ( P0*(Vre0^2 - Vim0^2) + 2*Q0*Vre0*Vim0 ) / (.)^2
```

`P0` is p.u. on a 1 MW base, so a 1 kW load is 1e-3. Multiplying by `P0` did not distort
the cross term — it shrank it ~1000× and effectively **deleted** it. The original is also
dimensionally incoherent: inside the bracket it adds volts² to power·volts².

**`dIredVim_Gen`** — used `P0minGenP` (= `P0 - GenP0`) where every other `_Gen` derivative
uses `GenP0`, and where `Ire_Gen` is itself defined from `GenP0` alone:

```
before   ( -2*P0minGenP(d,t)*Vre0*Vim0 ) / (.)^2
after    ( -2*GenP0(d,t)*Vre0*Vim0 ) / (.)^2
```

This one changes sign with the sun:

| Condition | used (`P0 − GenP0`) | correct (`GenP0`) | effect |
|---|---|---|---|
| Midday, PV 3 kW, load 1 kW | −0.0020 | +0.0030 | **sign flipped** |
| Dawn/dusk, PV 0.5 kW, load 1 kW | +0.0005 | +0.0005 | accidentally right |
| Night, PV 0 kW, load 1 kW | +0.0010 | 0 | spurious non-zero |

**Cross-check.** After the fix, `dIredVim_Gen` is identical to `dIimdVre_Gen`, which was
always correct — the PV-injection Jacobian is symmetric in that off-diagonal
(`∂Ire/∂Vim = ∂Iim/∂Vre`). Run `verify_derivatives.py` to confirm all of this independently.

## Why it was invisible

These are coefficients on `(V − V0)` in a linearization. They appear in no constraint that
can be violated, do not affect feasibility, and do not change solve status. Every run —
before and after — returns 576/576 `Optimal` and passes every ex-post AC check.

## The measurement

`RunTRk_Base` (pre-fix) vs `RunAllTrafos_DerivFix` (post-fix), identical configuration:
per-TR reduced network, exact quadratic, 48 half-hours × 12 directions, GMP, async.
**All nine: 576/576 `Optimal`, zero under- and over-voltage violations.**

### Boundary movement

| | TR1 | TR2 | TR3 | TR4 | TR5 | TR6 | TR7 | TR8 | TR9 |
|---|---|---|---|---|---|---|---|---|---|
| batteries | 77 | 95 | 49 | 46 | 214 | 262 | 259 | 124 | 90 |
| max \|Δproj\| (kW) | 22.9 | 22.3 | 20.9 | 21.9 | **33.7** | 28.9 | 32.2 | 24.3 | 23.6 |
| median \|Δproj\| (kW) | 1.70 | 1.76 | 1.80 | 1.60 | 3.44 | 1.41 | 1.61 | 2.10 | 1.95 |

**5,180 of 5,184 directions changed.**

### The region rotates — on all nine

Mean change in supporting projection by sweep direction, pooled over the half-hours whose
committed battery schedule is unchanged (kW):

```
   0°    30°    60°    90°   120°   150°   180°   210°   240°   270°   300°   330°
 1.53   2.38   3.53   3.61   1.47  -1.07  -2.87  -3.54  -2.29  -0.39   1.45   2.79
```

Reactive-import side **+2.87 kW out**, export side **−2.90 kW in** — and **9 of 9
transformers show that same sign pattern**. Both corrected terms are *cross* derivatives,
so they act mainly on reactive power. The two lobes cancel, which is why the area survives
while every boundary point moves. See `derivfix_summary.png`.

### Area change — split by whether the dispatch also moved

The rolling baseline is solved under the same formulation, so correcting it also moved the
committed battery schedule in some half-hours. Only those with an identical starting SOC
isolate the region effect.

| | half-hours | median | worst | over 1% |
|---|---|---|---|---|
| **Clean** (identical starting SOC) | 151 | **−0.05 %** | −2.83 % | 5 |
| **Confounded** (dispatch also moved) | 281 | −0.26 % | **−7.11 %** | 102 |

Per transformer:

| | TR1 | TR2 | TR3 | TR4 | TR5 | TR6 | TR7 | TR8 | TR9 |
|---|---|---|---|---|---|---|---|---|---|
| clean half-hours | 15 | 13 | 36 | 40 | 5 | 5 | 9 | 14 | 14 |
| clean median % | −0.08 | −0.01 | −0.12 | −0.05 | −0.12 | −0.04 | −0.01 | −0.02 | −0.04 |
| clean worst % | −1.27 | −1.61 | −0.64 | −0.66 | −2.83 | −0.25 | −0.40 | +0.31 | −0.80 |
| confounded worst % | −7.11 | −3.32 | −0.20 | +0.44 | −3.49 | −6.46 | −5.05 | −5.55 | −1.54 |
| max ΔSOC_start % | 39.4 | 14.1 | 0.0 | 0.0 | 7.0 | 17.8 | 22.1 | 17.5 | 5.1 |

> **Do not quote "area moves by under 1 %" without the split.** That was the TR9-only
> result. Across nine transformers the worst confounded half-hour moves −7.1 %.

### The dispatch divergence is real but narrow

Tested for degeneracy — whether the fleet does something different, or merely reshuffles
work between batteries. Coherence (fleet-total deviation ÷ per-battery deviation × fleet
size) is **0.55–1.00**, so the fleet genuinely behaves differently.

But it is localised. TR1, the worst at 39.4 % of capacity:

- **3 batteries of 77**; 18 battery-periods of 3,696 exceed 1 %
- confined to **half-hours 19–30**, the midday PV window
- worst case charges to `SOC = 1.000`, hitting the ceiling, where the pre-fix run left it at 0.605
- by half-hour 48, **75 of 77 batteries are identical again**

End-of-day SOC difference is 0.0 on all nine: the divergence opens at midday and closes by
nightfall. Physically coherent — the fix restores the PV cross-coupling that was sign-flipped
at exactly those hours.

## What this means

- **How much flexibility a feeder offers:** essentially unaffected. Clean half-hours move a
  median 0.05 %, and 146 of 151 stay under 1 %.
- **A specific operating point:** moves by up to 33.7 kW.
- **Reactive power:** most exposed. The error is systematic on that axis, consistent across
  all nine transformers, and does not average out.
- **Published battery trajectories:** affected in the midday window on 7 of 9 transformers.

## Contents

| File | What it is |
|---|---|
| `verify_derivatives.py` | **Independent proof.** Standard library only; checks all 8 derivatives against finite differences at 24 operating points, before and after |
| `derivative-fix-explained.pdf` | Plain-language explanation, with the figure |
| `derivative-fix-explained.tex` | Its source (`tectonic -X compile`) |
| `derivfix_summary.png` / `.pdf` | The figure: direction pattern across all nine + a representative before/after region |
| `plot_derivfix.py` | Regenerates the figure from the run CSVs in the repo root |
| `message-to-luis-and-nacho.md` | Draft note to collaborators — **draft, not sent** |

`plot_derivfix.py` reads `FOR_rolling_TR*_{base,dfix}.csv` and their `soc` companions from
the repo root. Those are git-ignored (`.gitignore:32`) and are **not** archived here — unlike
`results/full_feeder_2026-08/`, which has explicit negations at `.gitignore:46-47`. Re-run
`RunTRk_Base` and `RunAllTrafos_DerivFix` to reproduce them, or add matching negations if the
A/B data should be versioned.

## Notes on the campaign

Run 2026-08-24/26. TR9 standalone; TR1–TR8 in one batch via `RunAllTrafos_DerivFix`.

The batch session degraded: per-vertex solve time rose from 1.02× (TR1) to 1.26× (TR7)
relative to the one-per-fresh-session `_base` set, and non-solve overhead per half-hour grew
from 3.0 to 10.7 minutes. TR9 — run standalone — came in at **1.00×**, which identifies the
cause as session accumulation rather than anything about the fix. AIMMS also wrote one crash
dump mid-TR7 (`log/ErrorReports/`, 2026-08-25 08:40) and recovered without losing a vertex.

**For future campaigns of this size, run transformers one or two per fresh AIMMS session.**
The resume list in `RunAllTrafos_DerivFix` supports this without code changes.

## Open

Re-linearization is still untouched: the model draws its linearization once at the flat-start
voltage and never redraws it, with measured `LinErr` up to 0.032 p.u. (~1.6 % in voltage
magnitude). That is a larger approximation than the one fixed here. If the results are ever
regenerated again, the two are worth correcting in one campaign rather than two.
