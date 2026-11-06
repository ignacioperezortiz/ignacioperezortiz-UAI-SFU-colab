"""Results-in-detail block, part 3: one-day sweeps (data_tulio\\sweeps.json)."""
from pptx.enum.chart import XL_MARKER_STYLE
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN

from design import *  # noqa: F403
from slides_res import EYE, TD, CCOL, m, load, tfrac, time_chart, legend_line, pending
from slides_res2 import poly_chart, closed
from slides_static import bars
import slides_data as SD
import paths

CP_T2 = RGBColor(0xD9, 0xB3, 0xAF)
HP_T2 = RGBColor(0xE4, 0xC8, 0xA7)


def idx(d, hh):
    return d["time"].index(hh)


# ----------------------------------------------------------------------------- R1 headroom sets the P reach
def s_headroom_reach(prs, n):
    d = load("sweeps.json")
    s = content_slide(prs, EYE, "Headroom sets the P reach of the reference FOR",
                      ["Fleet sums at BESS level over the day: headroom ", m(r"\sum U_{s}", size=11, color=MUTED), " and ",
                       m(r"\sum D_{s}", size=11, color=MUTED), " vs the BESS deviation ", m(r"\sum \Delta P^{\mathrm{b}}_{s}", size=11, color=MUTED),
                       " the reference uses at 0° and 180°."], n)
    t = tfrac(d["time"])
    c, co = d["crit"]["ref"], d["crit"]["ref_oldfloor"]
    U = c["deg0"]["fleet"]["sum_U_kW"]
    D = c["deg180"]["fleet"]["sum_D_kW"]
    u0 = c["deg0"]["fleet"]["sum_dP_kW"]
    u180 = c["deg180"]["fleet"]["sum_dP_kW"]
    Dold = co["deg180"]["fleet"]["sum_D_kW"]
    ser = [{"name": "U", "xs": t, "ys": U, "color": RGBColor(0x7C, 0x8C, 0x97), "width": 2.25},
           {"name": "D", "xs": t, "ys": [-v for v in D], "color": RGBColor(0x7C, 0x8C, 0x97), "width": 2.25},
           {"name": "Dold", "xs": t, "ys": [-v for v in Dold], "color": GREY, "width": 1.75, "dash": MSO_LINE_DASH_STYLE.DASH},
           {"name": "u0", "xs": t, "ys": u0, "color": INK, "width": 0.5, "marker": XL_MARKER_STYLE.CIRCLE, "marker_size": 4},
           {"name": "u180", "xs": t, "ys": u180, "color": INK, "width": 0.5, "marker": XL_MARKER_STYLE.CIRCLE, "marker_size": 4}]
    label(s, L, 2.18, 4.5, "FLEET SUMS (kW): + IMPORT, − EXPORT", upper=False)
    rich(s, 4.6, 2.17, R - 4.6, 0.25, [[("━━ ", {"color": RGBColor(0x7C, 0x8C, 0x97), "bold": True}), m(r"\sum U_{s}", size=10), " and ",
                                        m(r"-\sum D_{s}", size=10), " (energy floor)    ",
                                        ("╌╌ ", {"color": GREY, "bold": True}), m(r"-\sum D_{s}", size=10), " (earlier floor)    ",
                                        ("●  ", {"color": INK, "bold": True}), "used by the reference at 0° / 180°"]], size=10, align=PP_ALIGN.RIGHT)
    import math
    lo = -100 * math.ceil(max(max(D), max(Dold)) / 100)
    hi = 100 * math.ceil(max(U) / 100)
    ch = xy_chart(s, L, 2.45, 8.0, 3.85, ser, x_range=(0, 1), y_range=(lo, hi), legend=False, size=10, x_fmt="[hh]:mm", markers=True)
    ch.category_axis.major_unit = 0.125
    ch.value_axis.major_unit = 100
    from pptx.enum.chart import XL_MARKER_STYLE as MS
    for sr, sd in zip(ch.plots[0].series, ser):
        if sd.get("marker"):
            sr.format.line.fill.background()
        else:
            sr.marker.style = MS.NONE
    plot_layout(ch, 0.09, 0.05, 0.89, 0.82)
    # 10:00–14:30 window, semi-transparent band on top of the chart (MUST 15)
    fr = (L, 2.45, 8.0, 3.85)
    xa, ya = plot_to_slide(fr, (0.09, 0.05, 0.89, 0.82), (0, 1), (lo, hi), 9.75 / 24, hi)
    xb, yb = plot_to_slide(fr, (0.09, 0.05, 0.89, 0.82), (0, 1), (lo, hi), 14.75 / 24, lo)
    band = rect(s, xa, ya, xb - xa, yb - ya, fill=RGBColor(0xDD, 0xE7, 0xED))
    from lxml import etree
    from pptx.oxml.ns import qn
    clr = band.fill._xPr.find(qn('a:solidFill')).find(qn('a:srgbClr'))
    etree.SubElement(clr, qn('a:alpha'), val='25000')
    text(s, xa, ya + 0.04, xb - xa, 0.4, ['network limits', 'bind'], size=9, color=INK_MID, italic=True, align=PP_ALIGN.CENTER)
    r1 = d["summary"]["R1"]
    xR, wR = 9.05, R - 9.05
    tiles = [("At 0°", f"{r1['steps_reaching_sumU_at_0deg_within_0.1kW']} / 48 steps", "the reference uses all of the upward headroom"),
             ("At 180°", "all steps but 10:00–14:30", f"short by > 1 kW there, max {r1['max_shortfall_180deg_kW']:.1f} kW at {r1['max_shortfall_180deg_time']}: network limits bind"),
             ("Earlier floor", f"+{r1['old_floor_sumD_minus_energy_floor_sumD_max_kW']:.1f} kW", f"overstates the downward headroom at {r1['old_floor_overstatement_max_time']}")]
    for i, (h, v, sub) in enumerate(tiles):
        y = 2.48 + i * 1.30
        rect(s, xR, y, wR, 1.16, fill=CARD, line=HAIR)
        text(s, xR + 0.18, y + 0.07, wR - 0.3, 0.26, h, size=10, color=MUTED)
        text(s, xR + 0.18, y + 0.30, wR - 0.3, 0.36, v, size=16, color=INK, bold=True)
        text(s, xR + 0.18, y + 0.68, wR - 0.3, 0.46, sub, size=10.5, color=MUTED, italic=True)
    notes(s, "BESS-level fleet sums from the per-aggregator logs of the reference (no fairness constraints): ΣU_s and ΣD_s "
             "(energy floor) and Σ ΔP^b_s at the 0° (maximum import) and 180° (maximum export) solves. These do not depend on "
             "the estimated all-idle exchange. At 0° the reference uses ΣU_s in all 48 steps (within 0.007 kW). At 180° it "
             "uses ΣD_s except at 10:00–14:30, short by 1.5–7.1 kW (12:00: 162.5 of 169.6 kW): there the network, not the "
             "headroom, limits export (voltage reaches 1.10 pu in some directions at 09:30–14:00). The dashed line is ΣD_s "
             "with the earlier floor (1 − DOD_s)Ē^b_s: up to 79.3 kW larger (19:00: 156.6 vs 77.4 kW), energy the BESS "
             "cannot release without breaking the self-consumption guarantee. Σ ΔP^b_s is not the interface ΔP (losses and "
             "network): at 07:30, 180°, −180.4 kW vs −143.2 kW.")
    return s


# ----------------------------------------------------------------------------- R2 3-D by criterion
def s_criteria_3d(prs, n):
    s = content_slide(prs, EYE, "The FOR over the day in 3-D, by criterion",
                      "TR4, one day, intra-aggregator scope, energy floor; % = mean area over 48 steps relative to the reference. Grey wireframe: reference.", n)
    img = paths.figures_in() / "fig_3d_criteria.png"
    if img.exists():
        from PIL import Image
        wpx, hpx = Image.open(img).size
        w = min(CW, 3.85 * wpx / hpx)
        picture(s, img, L + (CW - w) / 2, 2.15, w=w)
    else:
        pending(s, "3-D figure pending")
    bars(s, L, 6.10, CW, [{"p": [["CP narrows the FOR in the morning and collapses in the evening (below 1 % at 17:30–19:30); "
                                   "HP and HB follow the reference at every hour (thick slices: 07:30, 12:30, 18:00, 21:30)."]], "h": 0.6}],
         size=11.5)
    notes(s, "Stacked FOR slices F_{k+1} for the 48 flexibility slots of the day (x = ΔP, y = ΔQ, z = time), as deviation "
             "from the all-idle exchange. Reference = no fairness constraints. CP: capacity-proportional; HP: "
             "headroom-proportional; HB: headroom band ε = 0.1; all intra-aggregator, energy floor. The thick slices are the "
             "cut hours of the next slide.")
    return s


# ----------------------------------------------------------------------------- R4 cuts by criterion
def s_criteria_cuts(prs, n):
    d = load("sweeps.json")
    pc = d["per_case"]
    s = content_slide(prs, EYE, "Cuts of the FOR by criterion at four hours",
                      ["ΔP–ΔQ of ", m(r"\mathcal{F}_{k+1}", size=11, color=MUTED),
                       ", intra-aggregator scope, energy floor; % = area relative to the reference at the same step."], n)
    legend_line(s, L, 2.17, 8.0, [("reference", INK, False), ("CP", CP_C, False), ("HP", HP_C, False), ("HB", HB_C, True)])
    text(s, R - 3.5, 2.17, 3.5, 0.24, "x: ΔP (kW) · y: ΔQ (kvar)", size=10, color=MUTED, align=PP_ALIGN.RIGHT)
    hours = [("07:30", "morning"), ("12:30", "midday"), ("18:00", "early evening"), ("21:30", "late evening")]
    gap = 0.15
    w = (CW - 3 * gap) / 4
    for i, (hh, tag) in enumerate(hours):
        k = idx(d, hh)
        x = L + i * (w + gap)
        ser = []
        for key, col, wd, dash in (("ref", INK, 2.75, None), ("HP_intra", HP_C, 2.0, None), ("CP_intra", CP_C, 2.25, None),
                                   ("HB_intra", HB_C, 1.5, MSO_LINE_DASH_STYLE.DASH)):
            xs, ys = closed(pc[key]["polygons"][k])
            ser.append({"name": key, "xs": xs, "ys": ys, "color": col, "width": wd, "dash": dash})
        text(s, x, 2.52, w, 0.26, [[(hh, {"bold": True, "color": INK}), ("  " + tag, {"color": MUTED, "size": 10})]], size=13, align=PP_ALIGN.CENTER)
        poly_chart(s, x, 2.78, w, w, ser, lay=(0.17, 0.04, 0.80, 0.80))
        r = pc["ref"]
        lines = [[("ref ΔP  ", {"color": MUTED}), (f"[{r['dP_min_kW'][k]:+.1f}, {r['dP_max_kW'][k]:+.1f}]", {})]]
        for key, nm, col in (("CP_intra", "CP", CP_C), ("HP_intra", "HP", HP_C), ("HB_intra", "HB", HB_C)):
            q = pc[key]
            lines.append([(f"{nm}  ", {"color": col, "bold": True}), (f"{100 * q['area_ratio'][k]:.1f} %  ", {"bold": True}),
                          (f"[{q['dP_min_kW'][k]:+.1f}, {q['dP_max_kW'][k]:+.1f}]", {"color": MUTED})])
        lines = [[(t.replace('-', '−'), o) for t, o in ln] for ln in lines]
        text(s, x + 0.12, 2.78 + w + 0.05, w - 0.15, 1.0, lines, size=9.5, color=TEXT)
    text(s, L, 6.50, CW, 0.2, "HB above 100 % is an artefact of the 12-point boundary, not a larger region.", size=9, color=MUTED, italic=True)
    notes(s, "Each panel: F_{k+1} of the reference (no fairness) and of CP, HP and HB (ε = 0.1), intra-aggregator scope, "
             "energy floor, at one step; ±200 kW/kvar in all panels. Under each: area relative to the reference and ΔP range "
             "in kW. 07:30: CP keeps 39.5 % — by (14)–(15) its common factor is limited by the tightest prosumer of each group. 12:30: BESS full, "
             "network limits bind; HP is at its daily minimum (93.7 %). 18:00: CP's factor is 0 in every direction, the FOR is "
             "a segment at the P1 baseline. HB above 100 % (100.2 %) is a 12-point-hull artefact. At 07:30, 18:00 and 21:30 the "
             "ΔP ranges of HP and HB equal the reference's within 0.1 kW. " + "Per-prosumer U_s and D_s are not logged in the one-day runs (group sums only); statements about single prosumers follow from (14)–(15). ")
    return s


# ----------------------------------------------------------------------------- R5 P only
def s_p_only(prs, n):
    d = load("sweeps.json")
    pc = d["per_case"]
    s = content_slide(prs, EYE, "P only: export and import capability over the day",
                      "Largest export (−ΔP min) and import (ΔP max) of the FOR at each step (kW); solid: intra-aggregator, dashed: CP network-wide.", n)
    t = tfrac(d["time"])
    legend_line(s, L, 2.17, 8.2, [("reference", INK, False), ("CP", CP_C, False), ("HP", HP_C, False), ("HB", HB_C, False),
                                  ("CP network-wide", CP_C, True)])

    def ser(field, sign):
        out = [{"name": "ref", "xs": t, "ys": [sign * v for v in pc["ref"][field]], "color": INK, "width": 2.75}]
        for crit in ("CP", "HP", "HB"):
            out.append({"name": crit, "xs": t, "ys": [sign * v for v in pc[crit + "_intra"][field]], "color": CCOL[crit], "width": 2.0})
        out.append({"name": "CPnw", "xs": t, "ys": [sign * v for v in pc["CP_nw"][field]], "color": CP_C, "width": 1.5,
                    "dash": MSO_LINE_DASH_STYLE.DASH})
        return out
    lay = (0.08, 0.06, 0.90, 0.78)
    label(s, L, 2.42, 4.0, "EXPORT CAPABILITY (kW)", upper=False)
    time_chart(s, (L, 2.62, 8.2, 1.85), ser("dP_min_kW", -1), (-50, 200), 50, lay=lay)
    label(s, L, 4.47, 4.0, "IMPORT CAPABILITY (kW)", upper=False)
    time_chart(s, (L, 4.67, 8.2, 1.85), ser("dP_max_kW", 1), (-50, 200), 50, lay=lay)
    cm = d["summary"]["capability_mean_kW"]
    r5 = d["summary"]["R5"]
    xR, wR = 9.25, R - 9.25
    label(s, xR, 2.45, wR, "MEAN OVER 48 STEPS (kW)", upper=False)
    rows = [[[""], ["export"], ["import"]],
            [["reference"], [f"{cm['ref']['export_mean_kW']:.1f}"], [f"{cm['ref']['import_mean_kW']:.1f}"]]]
    for crit in ("HB", "HP", "CP"):
        for sc, nm in (("intra", "intra"), ("nw", "network-wide")):
            k = f"{crit}_{sc}"
            rows.append([[f"{crit} {nm}"], [f"{cm[k]['export_mean_kW']:.1f}"], [f"{cm[k]['import_mean_kW']:.1f}"]])
    SD.table(s, xR, 2.75, [1.75, 0.8, 0.8], 0.31, rows, size=10.5)
    text(s, xR, 5.35, wR, 1.2, f"HP and HB never lose import. HP loses more than 0.5 kW of export only at 10:00–14:30, at most "
         f"{r5['HP_intra']['max_export_loss_kW']:.1f} kW (intra) / {r5['HP_nw']['max_export_loss_kW']:.1f} kW (network-wide) at 12:00. "
         "HP and HB network-wide stay within 3 kW of their intra lines.",
         size=10.5, color=TEXT)
    notes(s, "P-only view of the same runs: for each step, the largest export (−ΔP_min) and import (ΔP_max) of F_{k+1} relative "
             "to the all-idle exchange (estimated within ±0.93 kW). Means over the 48 steps, not energy. HB and HP keep the "
             "reference's import capability at every step. HP loses more than 0.5 kW of export only at 10:00–14:30 (0.12 kW at "
             "15:00); HB only at 10:30 and 12:00–13:00, at most 3.4 / 4.2 kW (intra / network-wide): when network limits bind. CP loses most of both: it cannot follow the reference because, by (14)–(15), a prosumer without headroom pins "
             "the common factor; network-wide this is worse (export 31.8 kW).")
    return s


# ----------------------------------------------------------------------------- R6 mechanism per aggregator
def s_mechanism(prs, n):
    d = load("sweeps.json")
    r6 = d["summary"]["R6"]
    s = content_slide(prs, EYE, "Why: how each criterion uses the downward headroom",
                      ["Share of each aggregator's ", m(r"\sum D_{s}", size=11, color=MUTED), " used at the maximum-export solve (180°), BESS level."], n)
    cats = ["Agg1", "Agg2", "Agg3"]
    hh = "12:30"
    def sh(case, a):
        e = r6[case][hh]
        return 100 * (e[a] if a in e else e[a + "_from_fair"])["share180"]
    series = [("reference", [sh("ref", a) for a in cats], INK),
              ("HP intra", [sh("HP_intra", a) for a in cats], HP_C),
              ("HP network-wide", [sh("HP_nw", a) for a in cats], HP_T2),
              ("CP intra", [sh("CP_intra", a) for a in cats], CP_C),
              ("CP network-wide", [sh("CP_nw", a) for a in cats], CP_T2)]
    label(s, L, 2.18, 7.6, "12:30 — network limits bind (% of ΣD used)")
    bar_chart(s, L, 2.45, 7.6, 3.4, cats, series, legend=True, value_max=115, value_min=0, gap=60, overlap=-5, label_size=9,
              cat_size=11, label_texts=[[f"{v:.0f}" for v in sd[1]] for sd in series])
    text(s, L, 5.90, 7.6, 0.44, "HP intra: ζ↓ = 0.694 / 0.993 / 1.000 — mainly Agg1 is scaled down; network-wide one factor (0.865) for all. "
         "The reference itself uses 95–96 % of each ΣD here.", size=10.5, color=MUTED, italic=True)
    xR, wR = 8.75, R - 8.75
    sc = d["summary"]["scope_contrast_15:00"]
    tiles = [("07:30", "reference and HP use 100 %", "CP intra uses 41 / 24 / 41 % of ΣD towards export: by (14)–(15) its factor follows the tightest prosumer of each group"),
             ("15:00 · scope", "CP ΔP min −92.6 vs −16.0 kW", "intra vs network-wide (reference −153.8 kW): network-wide takes the smallest factor, Agg2's −0.082"),
             ("18:00", "CP: ζ = 0 at 0° and 180°", "by (14)–(15) each group has a prosumer without headroom in each direction: the CP FOR is a segment")]
    for i, (h, v, sub) in enumerate(tiles):
        y = 2.48 + i * 1.40
        rect(s, xR, y, wR, 1.30, fill=CARD, line=HAIR)
        text(s, xR + 0.18, y + 0.06, wR - 0.3, 0.24, h, size=10, color=MUTED)
        text(s, xR + 0.18, y + 0.28, wR - 0.3, 0.32, v, size=14, color=INK, bold=True)
        text(s, xR + 0.18, y + 0.60, wR - 0.3, 0.68, sub, size=10.5, color=MUTED, italic=True)
    rich(s, L, 6.36, 7.6, 0.24, [["Per-prosumer ", m(r"U_{s},\ D_{s}", size=9, color=MUTED),
                                  " are not logged in these runs; single-prosumer statements follow from (14)–(15)."]], size=9, color=MUTED, italic=True)
    notes(s, "Share = −Σ ΔP^b_s / ΣD_s per aggregator at the 180° solve (BESS level, from the per-aggregator logs; network-wide "
             "runs split by aggregator from the per-aggregator output). With HP, ΔP^b_s = −ζ↓ D_s, so the share equals ζ↓. At 12:30 the "
             "network limits export; HP intra scales down mainly Agg1 (Agg2 0.993), network-wide must scale everyone by 0.865. CP scales by "
             "rating, so its share is not |ζ|. HB factors are not unique when the band is slack, so they are not shown. "
             "15:00: CP network-wide ζ = −0.082 equals Agg2's intra factor (Agg1 −0.672, Agg3 −1.000).")
    return s


# ----------------------------------------------------------------------------- R12 summary of sensitivities
def s_summary(prs, n):
    d = load("sweeps.json")
    st = d["summary"]["area_ratio_stats"]
    s = content_slide(prs, EYE, "Summary of results and sensitivities",
                      "TR4, one clear-sky day. Area % = mean FOR area over 48 steps relative to the reference (no fairness, energy floor, μᶠ = 0.2, limits on) unless stated.", n)

    def ar(k):
        return f"{100 * st[k]['mean']:.1f} %"
    rows = [[["Lever"], ["Case"], ["Result"], ["Note"]],
            [["Criterion (energy floor)"], ["CP · HP · HB, intra"], [f"{ar('CP_intra')} · {ar('HP_intra')} · {ar('HB_intra')}"], ["CP < 1 % at 17:30–19:30"]],
            [["Scope"], ["CP · HP · HB, network-wide"], [f"{ar('CP_nw')} · {ar('HP_nw')} · {ar('HB_nw')}"], ["CP < 1 % at 15:30–19:30"]],
            [["Floor of ", m(r"D_{s}")], ["HP · HB intra, ", m(r"(1-\mathrm{DOD}_{s})\,\overline{E}^{\mathrm{b}}_{s}")], [f"{ar('HP_intra_oldfloor')} · {ar('HB_intra_oldfloor')}"], ["energy floor: 98.7 · 99.8 %"]],
            [["Headroom limits off"], ["CP · HB intra, earlier floor"], [f"{ar('CP_intra_nolimits')} · {ar('HB_intra_nolimits')}"], ["with limits: 51.5 · 82.2 %; CP 55 / 576 simultaneous solves"]],
            [["μᶠ · limits"], ["μᶠ = 0, on · off"], ["+1.0 % · +8.0 % area"], ["505 / 576 simultaneous solves"]],
            [["Guarantee"], ["on · relaxed (no fairness)"], ["854.3 · 993.5 kWh export"], ["relaxed: 46 / 46 import > 10 Wh more later"]],
            [["HP under service"], ["energy floor · earlier floor"], ["854.3 · 675.2 kWh export"], ["99.4 % of the no-fairness FOR, same requests"]],
            [["Not run"], ["CP, HB with service; μᶠ = 0 or limits off with the energy floor"], [""], ["import requests: run, not analysed here"]]]
    SD.table(s, L, 2.30, [2.55, 3.65, 3.0, 2.6], 0.44, rows, size=11)
    notes(s, "One line per lever. Earlier-floor, μ^f and no-limit runs are from the earlier version of the model; their reference FOR is the "
             "same as the current one (area ratio 1.0000, ≤ 0.023 kW / 0.108 kvar per point). Service rows: two-day run with 28 "
             "export requests on day 1; export service measured from the P1 baselines; 'import more later' = more than 10 Wh (below that is numerical tolerance) "
             "outside the requested half-hours vs the run without requests. Import-request runs exist but were not analysed for "
             "this meeting.")
    return s
