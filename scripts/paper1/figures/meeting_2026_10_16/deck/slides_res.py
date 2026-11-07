"""Results-in-detail block for the meeting with Tulio (data: data\\ and data_tulio\\)."""
import json

from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_MARKER_STYLE
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from design import *  # noqa: F403
from slides_static import bars
import slides_data as SD
import paths

DATA = "data"          # the deck's data\ and data_tulio\ folders; paths.deck_json finds their files in --data
TD = "data_tulio"
EYE = "04 · Results in detail"
LAYT = (0.07, 0.06, 0.91, 0.80)
CCOL = {"CP": CP_C, "HP": HP_C, "HB": HB_C, "reference": INK}


def m(latex, **o):
    return ("$", latex, o)


def load(name, folder=TD):
    p = paths.deck_json(folder, name)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def tfrac(times):
    """Fraction of day 1; a trailing 00:00 is the end of the day (24:00), not its start."""
    out = [(int(t[:2]) + int(t[3:5]) / 60) / 24 for t in times]
    return [1.0 if (v == 0 and i > 0) else v for i, v in enumerate(out)]


def time_chart(s, frame, series, y_range, y_major, legend=False, size=10, lay=LAYT):
    ch = xy_chart(s, *frame, series, x_title=None, y_title=None, x_range=(0, 1), y_range=y_range, legend=legend,
                  size=size, x_fmt="[hh]:mm")
    ch.category_axis.major_unit = 0.125
    ch.value_axis.major_unit = y_major
    plot_layout(ch, *lay)
    return ch


def legend_line(s, x, y, w, items, size=10, align=PP_ALIGN.LEFT):
    runs = []
    for lab, col, dashed in items:
        runs.append(("╌╌ " if dashed else "━━ ", {"color": col, "bold": True}))
        runs.append((lab + "     ", {"color": TEXT}))
    text(s, x, y, w, 0.24, [runs], size=size, align=align)


def pending(s, msg):
    SD.placeholder(s, L, 2.3, CW, 4.2, msg)


# ----------------------------------------------------------------------------- R3 area kept over the day
def s_area_day(prs, n):
    f = load("fair.json", DATA)
    s = content_slide(prs, EYE, "Area kept over the day, by criterion and scope",
                      ["Area of ", m(r"\mathcal{F}_{k+1}", size=11, color=MUTED),
                       " with each criterion relative to the reference FOR at the same step (TR4, energy floor, 48 rolling steps)."], n)
    t = tfrac(f["time"])
    ar = f["area_ratio"]["energy floor"]
    series = []
    for crit in ("CP", "HP", "HB"):
        for scope, dash in (("intra-aggregator", None), ("network-wide", MSO_LINE_DASH_STYLE.DASH)):
            series.append({"name": f"{crit} {scope}", "xs": t, "ys": [100 * v for v in ar[crit][scope]], "color": CCOL[crit],
                           "width": 2.25 if dash is None else 1.75, "dash": dash})
    label(s, L, 2.18, 6.0, "FOR area relative to the reference (%)")
    legend_line(s, 5.6, 2.17, R - 5.6, [("CP", CP_C, False), ("HP", HP_C, False), ("HB", HB_C, False),
                                         ("intra-aggregator", MUTED, False), ("network-wide", MUTED, True)], align=PP_ALIGN.RIGHT)
    time_chart(s, (L, 2.45, CW, 3.35), series, (0, 105), 25)
    sm = f["summary"]["energy floor"]

    def mm(c, k):
        return f"{100 * sm[c]['intra-aggregator'][k]:.1f} / {100 * sm[c]['network-wide'][k]:.1f} %"
    tiles = [("CP", mm("CP", "mean"), "below 1 % at 17:30–19:30 (intra) and 15:30–19:30 (network-wide)"),
             ("HP", mm("HP", "mean"), f"minimum {mm('HP', 'min')} at {sm['HP']['intra-aggregator']['min_time']}"),
             ("HB", mm("HB", "mean"), f"minimum {mm('HB', 'min')} at {sm['HB']['intra-aggregator']['min_time']}")]
    tw = (CW - 0.4) / 3
    for i, (c, v, sub) in enumerate(tiles):
        x = L + i * (tw + 0.2)
        rect(s, x, 5.88, tw, 0.74, fill=CARD, line=HAIR)
        rect(s, x, 5.88, 0.06, 0.74, fill=CCOL[c])
        text(s, x + 0.2, 5.90, tw - 0.3, 0.32, [[(c + "   ", {"bold": True, "color": INK}), ("mean " + v, {"bold": True, "color": INK})]], size=13)
        text(s, x + 0.2, 6.20, tw - 0.3, 0.42, "intra / network-wide; " + sub, size=10, color=MUTED, italic=True)
    text(s, R - 6.0, 5.62, 6.0, 0.22, "HB above 100 % (≤ 100.6 %) is an artefact of the 12-point boundary, not a larger region.",
         size=9, color=MUTED, italic=True, align=PP_ALIGN.RIGHT)
    notes(s, "Per-step FOR area with each criterion over the reference FOR (no fairness constraints, energy floor, μ^f = 0.2, "
             "headroom limits on) at the same step; 12 boundary points per step. CP collapses in the evening (17:30–19:30 "
             "intra-aggregator, from 15:30 network-wide): by (14)–(15) its common factor is pinned at zero when a prosumer of the group has no "
             "headroom in a direction. HP and HB stay above 92 % at every step, with their minimum at 12:30, when network "
             "limits bind. HB slightly above 100 % at 18:00–22:00 (≤ 100.6 %) is an artefact of the 12-point hull, not a "
             "larger region.")
    return s


# ----------------------------------------------------------------------------- R10 energy floor vs (1-DOD)E
def s_floor(prs, n):
    f = load("fair.json", DATA)
    sv = load("service.json", DATA)
    s = content_slide(prs, EYE, ["Sensitivity: measuring ", m(r"D_{s}", size=27, color=INK), " to the energy floor"],
                      ["Mean FOR area relative to the reference, with ", m(r"D_{s}", size=11, color=MUTED), " measured to ",
                       m(r"(1-\mathrm{DOD}_{s})\,\overline{E}^{\mathrm{b}}_{s}", size=11, color=MUTED), " (earlier version) and to ",
                       m(r"\underline{E}^{\mathrm{b}}_{s}", size=11, color=MUTED), " (current)."], n)
    so, se = f["summary"]["old floor"], f["summary"]["energy floor"]
    rows = [("HP", "intra-aggregator"), ("HP", "network-wide"), ("HB", "intra-aggregator"),
            ("HB", "network-wide"), ("CP", "intra-aggregator"), ("CP", "network-wide")]
    x0, x1 = L + 2.65, L + 6.85
    y0 = 2.62
    label(s, L, 2.18, 7.6, "Mean area kept over 48 steps")
    for v, lab in ((0, "0 %"), (50, "50 %"), (100, "100 %")):
        xx = x0 + (x1 - x0) * v / 100
        rect(s, xx, y0 - 0.05, 0.008, 6 * 0.52 + 0.05, fill=HAIR)
        text(s, xx - 0.4, y0 + 6 * 0.52 + 0.03, 0.8, 0.22, lab, size=9.5, color=MUTED, align=PP_ALIGN.CENTER)
    for i, (c, sc) in enumerate(rows):
        y = y0 + i * 0.52
        a, b = 100 * so[c][sc]["mean"], 100 * se[c][sc]["mean"]
        text(s, L, y, 2.6, 0.34, [[(c + "  ", {"bold": True, "color": INK}), (sc, {"color": MUTED})]], size=11.5, anchor=MSO_ANCHOR.MIDDLE)
        xa, xb = x0 + (x1 - x0) * a / 100, x0 + (x1 - x0) * b / 100
        rect(s, min(xa, xb), y + 0.155, max(abs(xb - xa), 0.01), 0.03, fill=GREY)
        rect(s, xa - 0.08, y + 0.09, 0.16, 0.16, fill=GREY, shape=MSO_SHAPE.OVAL)
        rect(s, xb - 0.09, y + 0.08, 0.18, 0.18, fill=CCOL[c], shape=MSO_SHAPE.OVAL)
        txt = f"{a:.1f} → {b:.1f} %" if abs(a - b) > 0.05 else f"{b:.1f} % (unchanged)"
        text(s, x1 + 0.25, y, 1.30, 0.34, txt, size=11, color=INK, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    rich(s, L, y0 + 6 * 0.52 + 0.32, 7.8, 0.26, [[("● ", {"color": GREY}), "floor ", m(r"(1-\mathrm{DOD}_{s})\,\overline{E}^{\mathrm{b}}_{s}", size=10),
                                                 "      ", ("● ", {"color": HP_C}), "energy floor ", m(r"\underline{E}^{\mathrm{b}}_{s}", size=10),
                                                 " (criterion colour)"]], size=10, color=MUTED)
    xR, wR = 9.35, R - 9.35
    label(s, xR, 2.18, wR, "HP under TSO export requests")
    so_, se_ = sv["summary"]["HP_old_floor"], sv["summary"]["HP_energy_floor"]
    mx = sv["mixing_180deg"]["one_day_FOR"]
    tiles = [("Export service (kWh, vs P1 baselines)", f"{so_['export_served_kWh']:.1f} → {se_['export_served_kWh']:.1f}",
              f"without fairness: {sv['summary']['no_fairness']['export_served_kWh']:.1f}"),
             ("Prosumers importing > 1 Wh more in the requested half-hours", f"{so_['prosumers_buying_more_inside']} → {se_['prosumers_buying_more_inside']} of 46",
              f"worst +{so_['worst_prosumer_inside_kWh']:.2f} kWh with the earlier floor"),
             ("Mixed allocations at 180° (ζ↑ and ζ↓ > 0)", f"{mx['old floor']['mixed']} → {mx['energy floor']['mixed']} of {mx['energy floor']['of']}",
              "group-step pairs, HP intra-aggregator")]
    for i, (ttl, v, sub) in enumerate(tiles):
        y = 2.48 + i * 1.36
        rect(s, xR, y, wR, 1.22, fill=CARD, line=HAIR)
        text(s, xR + 0.18, y + 0.07, wR - 0.3, 0.42, ttl, size=10, color=MUTED)
        text(s, xR + 0.18, y + 0.50, wR - 0.3, 0.36, v, size=17, color=INK, bold=True)
        text(s, xR + 0.18, y + 0.90, wR - 0.3, 0.26, sub, size=9.5, color=MUTED, italic=True)
    notes(s, "Same criteria, two definitions of D_s. With the earlier floor (1 − DOD_s)Ē^b_s, a BESS that must keep energy "
             "for the self-consumption guarantee still shows a large D_s that it cannot deliver; HP then has to mix ζ↑ and "
             "ζ↓ and loses area. The energy floor removes that. CP's FOR is the same with both floors (51.48 % / 40.27 %). "
             "Earlier-floor runs are from the earlier version of the model; the reference FOR is the same with both definitions (area "
             "ratio 1.0000 at every step, ≤ 0.023 kW / 0.108 kvar per point). Service tiles: two-day run, 28 export "
             "requests on day 1, HP intra-aggregator; imports are compared with the run without requests with the same "
             "criterion and floor. The earlier-floor service run follows a different state of charge, so its FOR is not "
             "compared with the others.")
    return s


# ----------------------------------------------------------------------------- R11 mu^f x headroom limits
def s_muf_limits(prs, n):
    d = load("muf.json", DATA)
    sm, ps = d["summary"], d["per_step"]
    s = content_slide(prs, EYE, ["Sensitivity: ", m(r"\mu^{\mathrm{f}}", size=27, color=INK), " and the headroom limits"],
                      ["TR4, one day, 576 solves per case; earlier floor ",
                       m(r"(1-\mathrm{DOD}_{s})\,\overline{E}^{\mathrm{b}}_{s}", size=11, color=MUTED), ". Reference: ",
                       m(r"\mu^{\mathrm{f}}=0.2", size=11, color=MUTED), " with limits, whose FOR equals the current reference."], n)
    label(s, L, 2.18, 5.6, "Four combinations")

    def cell(k):
        c = sm[k]
        dm, dx = 100 * (c['area_ratio_mean'] - 1), 100 * (c['area_ratio_max'] - 1)
        fm = (lambda v: f"{v:+.2f}") if abs(dx) < 0.1 else (lambda v: f"{v:+.1f}")
        return (f"{c['simultaneous_solves']} / 576 · {c['simultaneous_kW_max']:.0f} kW", f"{fm(dm)} % (max {fm(dx)} %)")
    a0, b0 = cell("muf_0")
    a1, b1 = cell("muf_0_nolimits")
    a2, _ = cell("muf_0.2")
    a3, b3 = cell("muf_0.2_nolimits")
    rows = [[[""], [""], ["limits on"], ["limits off"]],
            [[m(r"\mu^{\mathrm{f}}=0")], ["solves · max power"], [a0], [a1]],
            [[""], ["FOR area"], [b0], [b1]],
            [[m(r"\mu^{\mathrm{f}}=0.2")], ["solves · max power"], [a2], [a3]],
            [[""], ["FOR area"], ["reference"], [b3]]]
    SD.table(s, L, 2.48, [0.80, 1.75, 1.55, 1.55], 0.42, rows, size=10.5)
    text(s, L, 4.66, 5.65, 0.3, "solves with simultaneous charging and discharging (of 576); max power: fleet",
         size=9.5, color=MUTED, italic=True)
    bars(s, L, 5.12, 5.65, [
        {"p": [["Without both, simultaneous operation absorbs through losses: up to +",
                f"{sm['muf_0_nolimits']['dP_0deg_vs_ref_kW_max']:.1f} kW at 0° (mean +{sm['muf_0_nolimits']['dP_0deg_vs_ref_kW_mean']:.1f} kW)."]], "h": 0.62},
        {"p": [[m(r"\mu^{\mathrm{f}}=0.1", size=11.5), f" with limits: 0 / 576 simultaneous solves, FOR +{100 * (sm['muf_0.1']['area_ratio_mean'] - 1):.1f} %."]], "h": 0.5},
    ], size=11.5, gap=6)
    xR, wR = 6.75, R - 6.75
    label(s, xR, 2.18, wR, "FOR area change vs the reference, per step (%)")
    t = tfrac(d["time"])
    series = [{"name": "a", "xs": t, "ys": [100 * (v - 1) for v in ps["muf_0_nolimits"]["area_ratio"]], "color": INK, "width": 2.25},
              {"name": "b", "xs": t, "ys": [100 * (v - 1) for v in ps["muf_0"]["area_ratio"]], "color": INK_MID, "width": 2.25},
              {"name": "c", "xs": t, "ys": [100 * (v - 1) for v in ps["muf_0.1"]["area_ratio"]], "color": HB_T, "width": 2.0}]
    ch = xy_chart(s, xR, 2.48, wR, 3.3, series, x_range=(0, 1), y_range=(0, 25), legend=False, size=10, x_fmt="[hh]:mm")
    ch.category_axis.major_unit = 0.25
    ch.value_axis.major_unit = 5
    plot_layout(ch, 0.10, 0.06, 0.86, 0.80)
    rich(s, xR, 5.92, wR, 0.5, [[("━━ ", {"color": INK, "bold": True}), m(r"\mu^{\mathrm{f}}=0", size=10), ", limits off    ",
                                 ("━━ ", {"color": INK_MID, "bold": True}), m(r"\mu^{\mathrm{f}}=0", size=10), ", limits on    ",
                                 ("━━ ", {"color": HB_T, "bold": True}), m(r"\mu^{\mathrm{f}}=0.1", size=10), ", limits on"]], size=10)
    notes(s, "Rows: μ^f; columns: headroom limits −D_s ≤ ΔP^b_s ≤ U_s on or off. A solve counts as simultaneous when at "
             "least one BESS has min(charging, discharging) > 1 W in slot k+1; powers are fleet totals. Area changes are "
             "means over 48 steps (maximum in brackets) relative to μ^f = 0.2 with limits. Without μ^f and without limits the "
             f"FOR grows by {100 * (sm['muf_0_nolimits']['area_ratio_mean'] - 1):.1f} % on average (max "
             f"{100 * (sm['muf_0_nolimits']['area_ratio_max'] - 1):.1f} % at {sm['muf_0_nolimits']['area_ratio_max_time']}), "
             "through fictitious absorption: BESS charge and discharge at once and absorb through losses. The limits alone "
             "cut that to about +1 %; μ^f alone removes the simultaneous operation. These μ^f runs use the earlier headroom "
             "limits ((1 − DOD_s)Ē^b_s); no μ^f = 0 run exists with the energy floor.")
    return s
