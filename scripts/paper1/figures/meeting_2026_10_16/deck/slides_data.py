"""Data-driven slides: literature review, test case, FOR over time, and the two results slides."""
import json

from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_LEGEND_POSITION, XL_MARKER_STYLE
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from design import *  # noqa: F403
import paths

DATA = "data"          # the deck's data\ folder; paths.deck_json finds its files in --data


def load(name):
    p = paths.deck_json(DATA, name)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def m(latex, **o):
    return ("$", latex, o)


def placeholder(s, x, y, w, h, msg):
    rect(s, x, y, w, h, fill=CARD, line=HAIR)
    text(s, x, y, w, h, msg, size=11, color=MUTED, italic=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)


def finding(s, x, y, w, num, body, h=0.78):
    text(s, x, y, 1.55, h, num, size=24, color=AMBER, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    text(s, x + 1.65, y, w - 1.65, h, body, size=12, color=TEXT, anchor=MSO_ANCHOR.MIDDLE)


# ----------------------------------------------------------------------------- literature
def s_literature(prs, n):
    s = content_slide(prs, "03 · Fairness", "Fairness in the literature: 45 papers reviewed",
                      "Where fairness is applied, which criteria are used, and how.", n)
    label(s, L, 2.20, 5.6, "Where fairness is applied")
    rows = [("Downward allocation only", "DOEs, PV curtailment, payments", 40, INK_MID),
            ("Coupled with aggregation", "", 4, AMBER),
            ("Aggregated P–Q FOR, fairness by design", "", 0, None)]
    bx, bw_max, y = L + 2.75, 2.55, 2.62
    for name, sub, v, col in rows:
        text(s, L, y, 2.70, 0.45, [[(name, {"bold": True})]] + ([[(sub, {"size": 9.5, "color": MUTED, "italic": True})]] if sub else []),
             size=11, color=TEXT, anchor=MSO_ANCHOR.MIDDLE)
        if v > 0:
            rect(s, bx, y + 0.08, bw_max * v / 40, 0.30, fill=col)
            text(s, bx + bw_max * v / 40 + 0.08, y + 0.04, 0.6, 0.38, str(v), size=15, color=INK, bold=True, anchor=MSO_ANCHOR.MIDDLE)
        else:
            text(s, bx + 0.12, y + 0.04, 2.0, 0.38, [[("0", {"bold": True, "size": 15, "color": AMBER}),
                                                     ("   ← this work", {"size": 11, "color": AMBER, "bold": True})]],
                 size=15, color=AMBER, anchor=MSO_ANCHOR.MIDDLE)
        y += 0.68
    rect(s, bx - 0.01, 2.62, 0.012, 3 * 0.68 - 0.1, fill=GREY)
    text(s, L, y + 0.02, 5.7, 0.25, "One review of local energy systems fits none of these categories (40 + 4 + 0 + 1 = 45).",
         size=9.5, color=MUTED, italic=True)
    x0, w0 = 6.90, R - 6.90
    label(s, x0, 2.20, w0, "Main findings")
    finding(s, x0, 2.52, w0, "4", "papers couple fairness with aggregation; none builds an aggregated P–Q FOR with fairness by design.")
    finding(s, x0, 3.36, w0, "24", "papers implement egalitarian criteria and 23 proportional ones, the most common families (max-min 10, log 9).")
    finding(s, x0, 4.20, w0, "16 of 18", "papers use Jain's index only ex post; Gini in 5 of 5. Indices assess, rarely constrain.")
    yb = 5.30
    rect(s, L, yb, CW, 1.30, fill=CARD, line=HAIR)
    label(s, L + 0.25, yb + 0.12, 6.0, "Items considered to choose our criteria", color=MUTED, size=8.5)
    chips = ["Popularity", "Methodological fit", "Implementability", "Analytical richness", "Defensibility"]
    cx = L + 0.25
    for c in chips:
        w = 0.32 + 0.085 * len(c)
        rect(s, cx, yb + 0.43, w, 0.34, fill=WHITE, line=INK_MID, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
        text(s, cx, yb + 0.43, w, 0.34, c, size=10.5, color=INK, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        cx += w + 0.14
    rich(s, L + 0.25, yb + 0.88, CW - 0.5, 0.32,
         [[("Requirements: ", {"bold": True, "color": INK}),
           "established criteria as linear (or convex) constraints, not in the objective; the same feasible set in every direction ",
           m(r"\theta", size=11), ", with signed contributions; preserved under convex combination of setpoints  →  ",
           ("CP, HP, HB", {"bold": True, "color": AMBER})]], size=11)
    notes(s, "45 papers that implement, define or review fairness criteria. 40 apply fairness only when allocating downward "
             "(DOEs, PV curtailment, payments); 4 couple it with aggregation (Nazir & Almassalkhi 2022, Attarha 2024, "
             "Li, Motoki & Zhang 2025, Jeong 2024; the count depends on how the last two are classified: Li et al. has no "
             "network model and the readers disagreed on Jeong); none builds an aggregated P–Q FOR with fairness by design. "
             "Fair P–Q DOEs do exist, but as downward allocations. The closest, Nazir & Almassalkhi, uses nodal intervals in "
             "P only. Most implemented families: egalitarian (24), proportional (23), max-min (10), proportional fairness / "
             "log (9); a paper can count in several. Indices are mostly ex post: Jain in 16 of 18 papers, Gini in all 5. "
             "Why CP, HP, HB: CP covers the egalitarian and proportional families (they coincide for identical BESS); HP "
             "extends the uniform curtailment factor to bidirectional BESS with separate factors ζ↑ and ζ↓; HB relaxes HP "
             "by a tolerance ε, a linear per-prosumer band instead of an ex post dispersion index. Requirements considered: "
             "established criteria only; a constraint, not the objective; linear or convex; the same feasible set in every "
             "direction θ; signed contributions over 360°; preserved under convex combination; anchored at the P1 baseline; "
             "allocates the service contribution, not self-consumption; active power only; intra-aggregator and "
             "network-wide scopes.")
    return s


# ----------------------------------------------------------------------------- test case
def s_testcase(prs, n):
    s = content_slide(prs, "04 · Test case", "Test case: the LV network of TR4",
                      "UK MV–LV network of the case study; TR4 is simulated in detail.", n)
    from PIL import Image
    for x, fn, lab in ((L, "network_mv.png", "UK MV–LV network (TR4 shaded)"), (6.85, "network_tr4.png", "LV network of TR4")):
        img = IMG / fn
        label(s, x, 2.18, 5.75, lab)
        if img.exists():
            wpx, hpx = Image.open(img).size
            w = 5.75
            h = w * hpx / wpx
            picture(s, img, x, 2.48, w=w)
    rect(s, L, 6.02, CW, 0.012, fill=HAIR)
    rich(s, L, 6.12, CW, 0.40,
         [[("TR4 ", {"bold": True, "color": INK}), "800 kVA  ·  75 customers  ·  46 PV–BESS prosumers, 3 aggregators"
           "  ·  1.5–4-kWp PV (144 kWp)  ·  3.6-kW BESS (165.6 kW)  ·  ", m(r"\Delta t=30\ \mathrm{min},\ H=48", size=10.5),
           "  ·  12 directions"]], size=10.5, anchor=MSO_ANCHOR.MIDDLE)
    notes(s, "Fig. 4 of the draft. A 6.6-kV feeder connects nine MV/LV transformers to the TSO–DSO interface; the results "
             "that follow are for the LV network of TR4, simulated in detail. Values as in the case study of the draft.")
    return s


# ----------------------------------------------------------------------------- FOR over time
LAY = (0.075, 0.06, 0.905, 0.80)   # shared inner plot layout so the two time axes line up


def s_for_time(prs, n):
    s = content_slide(prs, "04 · Results", "Serving the TSO now changes the FOR offered later",
                      ["TR4, day 1, no fairness constraints: ", m(r"\mathcal{F}_{k+1}", size=11, color=MUTED),
                       " without TSO requests, and in a stress test with a request for its most-export point every half-hour 06:00–19:30."], n)
    d = load("for_time.json")
    if d is None:
        placeholder(s, L, 2.2, CW, 4.4, "FOR over time: data pending")
        return s
    nr, ex = d["cases"]["no_request"]["series"], d["cases"]["export_guarantee_on"]["series"]
    slots = d["slots"]
    t = [(sl["slot"] - 1) / 48 for sl in slots]          # fraction of day 1
    day1 = [sl["day"] == 1 for sl in slots]
    req = [c and r for c, r in zip(day1, ex["requested"])]

    def pts(ser, key, cond):
        return [(a, v) for a, v, c in zip(t, ser[key], cond) if v is not None and c]

    GR = GREY
    series = []
    for key in ("dP_max", "dP_min"):
        p = pts(nr, key, day1)
        series.append({"name": "no TSO request", "xs": [a for a, _ in p], "ys": [b for _, b in p], "color": GR, "width": 2.0})
    for key in ("dP_max", "dP_min"):
        p = pts(ex, key, req)
        series.append({"name": "TSO export requests", "xs": [a for a, _ in p], "ys": [b for _, b in p], "color": ORANGE, "width": 2.5})
    fr1 = (L, 2.45, CW, 2.40)
    label(s, L, 2.18, 4.0, "ΔP RANGE OF THE FOR (kW)", upper=False)
    rich(s, 5.4, 2.17, R - 5.4, 0.25, [[("━  ", {"color": GREY, "bold": True}), ("no TSO request      ", {"color": RGBColor(0x6E, 0x7E, 0x8A), "bold": True}),
                                        ("━  TSO export requests (guarantee on), 06:00–19:30", {"color": ORANGE, "bold": True})]], size=10, align=PP_ALIGN.RIGHT)
    ch = xy_chart(s, *fr1, series, x_title=None, y_title=None, x_range=(0, 1), y_range=(-200, 200), legend=False, size=10,
                  x_fmt="[hh]:mm")
    ch.category_axis.major_unit = 0.125
    ch.value_axis.major_unit = 100
    plot_layout(ch, *LAY)
    xr, yr = (0, 1), (-200, 200)
    P = lambda xv, yv: plot_to_slide(fr1, LAY, xr, yr, xv, yv)  # noqa: E731
    x1, y1 = P(0.005, 140)
    text(s, x1 + 0.05, y1, 1.2, 0.22, "+ import", size=9, color=MUTED, italic=True)
    x1, y1 = P(0.005, -150)
    text(s, x1 + 0.05, y1, 1.2, 0.22, "− export", size=9, color=MUTED, italic=True)
    x1, y1 = P(6.75 / 24, -40)
    text(s, x1, y1, 4.6, 0.24, "with requests the BESS reach the DOD floor: export side ≈ 0 until early afternoon", size=9.5, color=ORANGE, italic=True)
    x1, y1 = P(13.6 / 24, 92)
    text(s, x1 - 0.3, y1, 4.0, 0.24, "then net charging even at the most-export point (up to +35 kW)", size=9.5, color=ORANGE, italic=True)
    # SOC over day 1
    fr2 = (L, 5.22, CW, 1.42)
    label(s, L, 4.97, 4.0, "Mean SOC of the 46 BESS (%)")
    soc = []
    soc.append({"name": "DOD floor", "xs": [0, 1], "ys": [10, 10], "color": GREY, "width": 0.75, "dash": MSO_LINE_DASH_STYLE.DASH})
    for ser, nm, col, wd, first in ((nr, "no TSO request", GR, 2.0, 0), (ex, "TSO export requests", ORANGE, 2.5, 12)):
        p = [(a, v) for i, (a, v, c) in enumerate(zip(t, ser["soc_mean_pct"], day1)) if v is not None and c and i >= first]
        soc.append({"name": nm, "xs": [a for a, _ in p], "ys": [b for _, b in p], "color": col, "width": wd})
    ch2 = xy_chart(s, *fr2, soc, x_title=None, y_title=None, x_range=(0, 1), y_range=(0, 100), legend=False, size=10, x_fmt="[hh]:mm")
    ch2.category_axis.major_unit = 0.125
    ch2.value_axis.major_unit = 50
    plot_layout(ch2, *LAY)
    x1, y1 = plot_to_slide(fr2, LAY, (0, 1), (0, 100), 0.005, 10)
    text(s, x1 + 0.05, y1 - 0.24, 1.6, 0.22, "DOD floor (10 %)", size=9, color=MUTED, italic=True)
    notes(s, "TR4, day 1 of a two-day run (no requests on day 2). Top: range of ΔP of F_{k+1} (deviation from the interface "
             "exchange with all BESS idle; positive = import) at each flexibility slot, without TSO requests (grey) and with "
             "a TSO request every half-hour 06:00–19:30 for the FOR boundary point with the most export (orange). This is "
             "a stress scenario on one clear-sky day. After the first request the BESS sit at the DOD floor (mean SOC "
             "about 10–11 %) until about 13:00, so the export side of the FOR collapses while the import side stays wide; "
             "without requests the BESS fill up with PV and the import side shrinks instead. From 13:00 to 18:30 even the "
             "most-export point needs net charging (up to 35 kW at 16:30; from about 14:00 clearly above the accuracy of the reference): the self-consumption guarantee makes the BESS "
             "refill for the evening (values below about +3 kW are within the accuracy of the all-idle reference). Bottom: mean SOC of the 46 BESS. On day 2, without requests, both runs converge.")
    return s


# ----------------------------------------------------------------------------- results 1
def track_rows(s, x, y, w, rows, total, size=11):
    """Horizontal track bars: label (inline math), pale track = total, fill = value, value label."""
    lab_w, val_w = 1.25, 1.05
    tw = w - lab_w - val_w - 0.1
    for i, (lat, v, col) in enumerate(rows):
        yy = y + i * 0.52
        rich(s, x, yy, lab_w - 0.15, 0.34, [[m(lat, size=size)]], size=size, anchor=MSO_ANCHOR.MIDDLE, align=PP_ALIGN.RIGHT)
        rect(s, x + lab_w, yy + 0.06, tw, 0.22, fill=INK_PALE)
        if v > 0:
            rect(s, x + lab_w, yy + 0.06, tw * v / total, 0.22, fill=col)
        text(s, x + lab_w + tw + 0.1, yy, val_w, 0.34, f"{v} / {total}", size=size, color=INK, bold=True, anchor=MSO_ANCHOR.MIDDLE)


def cell_rich(cell, items, size=10.5, bold=False, align=PP_ALIGN.CENTER, color=TEXT):
    from omml import add_inline
    tf = cell.text_frame
    tf.text = ""
    p = tf.paragraphs[0]
    p.alignment = align
    for it in items:
        if isinstance(it, tuple):
            add_inline(p, it[1], size_pt=size, color_hex=str(color))
        else:
            r = p.add_run()
            r.text = it
            r.font.name, r.font.size, r.font.bold = FONT, Pt(size), bold
            r.font.color.rgb = color


def table(s, x, y, widths, row_h, rows, size=10.5, header=True):
    from lxml import etree
    from pptx.oxml.ns import qn
    nr, nc = len(rows), len(widths)
    gf = s.shapes.add_table(nr, nc, Inches(x), Inches(y), Inches(sum(widths)), Inches(row_h * nr))
    tb = gf.table
    tb.first_row = False
    tb.horz_banding = False
    for j, w in enumerate(widths):
        tb.columns[j].width = Inches(w)
    for i, row in enumerate(rows):
        tb.rows[i].height = Inches(row_h)
        for j, items in enumerate(row):
            c = tb.cell(i, j)
            c.fill.background()
            c.margin_left = c.margin_right = Inches(0.04)
            c.margin_top = c.margin_bottom = Inches(0.01)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell_rich(c, items if isinstance(items, list) else [items], size=size, bold=(header and i == 0),
                      align=PP_ALIGN.LEFT if j == 0 else PP_ALIGN.CENTER, color=INK if (header and i == 0) else TEXT)
            tcPr = c._tc.get_or_add_tcPr()
            for tag in ("a:lnL", "a:lnR", "a:lnT", "a:lnB"):
                ln = etree.SubElement(tcPr, qn(tag), w=str(int(Pt(0.75))) if tag == "a:lnB" else "0")
                if tag == "a:lnB":
                    sf = etree.SubElement(ln, qn("a:solidFill"))
                    etree.SubElement(sf, qn("a:srgbClr"), val=str(INK if (header and i == 0) else HAIR))
                else:
                    etree.SubElement(ln, qn("a:noFill"))
    return tb


def s_results_muf_guarantee(prs, n):
    g = load("guarantee.json")
    s = content_slide(prs, "04 · Results", "Results: throughput penalty and guarantee",
                      ["TR4. Left: one day, 576 directional solves per case. Right: two-day run with TSO export requests "
                       "every half-hour 06:00–19:30 on day 1."], n)
    d = load("muf.json")
    xL, wL = L, 5.55
    label(s, xL, 2.18, wL, "Throughput penalty")
    if d is None:
        placeholder(s, xL, 2.5, wL, 4.1, "data pending")
    else:
        sm = d["summary"]
        rich(s, xL, 2.45, wL, 0.58, [[m(r"\mu^{\mathrm{f}}", size=13, color=INK),
                                      " avoids simultaneous charging and discharging; with the headroom limits, the FOR changes by only about 1 %."]],
             size=13, color=INK, bold=True)
        text(s, xL, 3.10, wL, 0.25, "Directional solves with simultaneous charging and discharging", size=10, color=MUTED, italic=True)
        track_rows(s, xL, 3.40, wL, [(r"\mu^{\mathrm{f}}=0", sm["muf_0"]["simultaneous_solves"], INK_MID),
                                     (r"\mu^{\mathrm{f}}=0.1", sm["muf_0.1"]["simultaneous_solves"], INK_MID),
                                     (r"\mu^{\mathrm{f}}=0.2", sm["muf_0.2"]["simultaneous_solves"], INK_MID)], 576)
        hdr = [[""], [m(r"\mu^{\mathrm{f}}=0")], [m(r"\mu^{\mathrm{f}}=0.1")], [m(r"\mu^{\mathrm{f}}=0.2")]]
        rows = [hdr,
                [["Max. simultaneous power, fleet"], [f"{sm['muf_0']['simultaneous_kW_max']:.0f} kW"], ["0"], ["0"]],
                [["Mean BESS throughput, fleet"], [f"{sm['muf_0']['throughput_kW_mean']:.0f} kW"],
                 [f"{sm['muf_0.1']['throughput_kW_mean']:.0f} kW"], [f"{sm['muf_0.2']['throughput_kW_mean']:.0f} kW"]],
                [["FOR area vs ", m(r"\mu^{\mathrm{f}}=0.2")], [f"+{100 * (sm['muf_0']['area_ratio_mean'] - 1):.1f} %"],
                 [f"+{100 * (sm['muf_0.1']['area_ratio_mean'] - 1):.1f} %"], ["reference"]]]
        table(s, xL, 5.05, [2.75, 0.93, 0.93, 0.93], 0.36, rows, size=11)
        rich(s, xL, 6.50, wL, 0.22, [["Runs with ", m(r"\mu^{\mathrm{f}}=0", size=9.5), " and 0.1 use the earlier limits, ",
                                      m(r"D_{s}", size=9.5), " measured to ", m(r"(1-\mathrm{DOD}_{s})\,\overline{E}^{\mathrm{b}}_{s}", size=9.5), "."]],
             size=9.5, color=MUTED, italic=True)
    rect(s, 6.62, 2.2, 0.012, 4.42, fill=HAIR)
    xR, wR = 6.90, R - 6.90
    label(s, xR, 2.18, wR, "Self-consumption guarantee")
    if g is None:
        placeholder(s, xR, 2.5, wR, 4.1, "Guarantee results: data pending")
    else:
        guarantee_panel(s, g, xR, wR)
    notes(s, "Left: TR4, one day, 576 directional solves per case, all optimal, with the headroom limits on. A solve counts "
             "when at least one BESS has min(charging, discharging) > 1 W in slot k+1; powers are fleet totals. Without "
             "μ^f, 505 of 576 solves charge and discharge at once (up to 101 kW); with μ^f = 0.1 or 0.2, none. The FOR "
             "area changes by +1.0 % on average (max +1.6 %). Without the headroom limits, μ^f = 0 would enlarge the FOR by "
             "+8 % on average (max +20 %) through fictitious absorption; the limits reduce that to about +1 %. With μ^f = 0.2, "
             "0 of 576 solves charge and discharge at once even without the limits. These μ^f runs use the earlier "
             "headroom limits, measured to (1 − DOD_s)Ē^b_s; with μ^f = 0.2 the reference FOR is the same with "
             "either definition. Right: TR4, no fairness constraints, two-day run with 28 TSO export requests (every "
             "half-hour 06:00–19:30 on day 1, each for the FOR boundary point with the most export). Export service is "
             "measured from the P1-baseline point of each step. With the guarantee: 854.3 kWh, and outside the requested "
             "half-hours no prosumer imports more than 1.8 Wh extra over the two days (40 Wh fleet-wide: numerical "
             "tolerance, hence the 10-Wh threshold on the slide). With the guarantee relaxed: 993.5 kWh (+16 %), but all 46 prosumers import more in the other "
             "half-hours of the two days, 98.8 kWh in total (worst 3.5 kWh); 43 also import more within the requested "
             "half-hours (28.2 kWh). Net extra export at the interface vs the run without requests: 69.7 kWh with the "
             "guarantee, 180.7 kWh without.")
    return s


def guarantee_panel(s, g, x, w):
    on, rx = g["guarantee_on"], g["guarantee_relaxed"]
    oo, ro = on["extra_import_outside_requested"], rx["extra_import_outside_requested"]
    rich(s, x, 2.45, w, 0.58, [["Without the guarantee, P2 serves more export, but prosumers import more in the other half-hours."]],
         size=13, color=INK, bold=True)
    text(s, x, 3.10, w, 0.25, "No fairness constraints; 28 TSO export requests on day 1", size=10, color=MUTED, italic=True)
    cw = (w - 0.2) / 2
    fmt = lambda v: "≈ 0" if abs(v) < 0.5 else f"{v:.0f}"  # noqa: E731
    vmax = 1.35 * max(on["export_served_kWh"], rx["export_served_kWh"])
    for k, (ttl, vals) in enumerate((("Export service (kWh, vs P1 baselines)", (on["export_served_kWh"], rx["export_served_kWh"])),
                                    ("Extra prosumer imports, other half-hours (kWh)", (max(oo["total_kWh"], 0), max(ro["total_kWh"], 0))))):
        xx = x + k * (cw + 0.2)
        text(s, xx, 3.40, cw, 0.24, ttl, size=10, color=INK, bold=True)
        ch = bar_chart(s, xx, 3.62, cw, 1.30, ["guarantee on", "relaxed"], [("v", list(vals), AMBER)], horizontal=True,
                       legend=False, gap=45, value_min=0, value_max=vmax, label_size=11, cat_size=10.5,
                       label_texts=[[fmt(v) for v in vals]])
        ch.category_axis.reverse_order = True
        pts = ch.plots[0].series[0].points
        for pt, c in zip(pts, (AMBER, AMBER_PALE)):
            pt.format.fill.solid()
            pt.format.fill.fore_color.rgb = c
            pt.format.line.color.rgb = AMBER
            pt.format.line.width = Pt(1)
    above = lambda c: sum(1 for p in c["per_prosumer"] if p["outside_kWh"] > 0.010)  # noqa: E731
    energy = lambda v: f"{1000 * v:.1f} Wh" if v < 1 else f"{v:.1f} kWh"  # noqa: E731
    rows = [[[""], ["guarantee on"], ["relaxed"]],
            [["Prosumers importing > 10 Wh more"], [f"{above(on)} of 46"], [f"{above(rx)} of 46"]],
            [["Worst prosumer"], [energy(oo["worst_kWh"])], [energy(ro["worst_kWh"])]]]
    table(s, x, 5.12, [2.9, 1.4, 1.4], 0.36, rows, size=11)
    text(s, x, 6.25, w, 0.3, "vs the run without requests, outside the requested half-hours, two days; below 10 Wh is numerical tolerance",
         size=9.5, color=MUTED, italic=True)


# ----------------------------------------------------------------------------- results 2
def s_results_fairness(prs, n):
    s = content_slide(prs, "04 · Results", "CP keeps 40–51 % of the FOR; HP and HB about 99 %",
                      ["TR4, one day: area of ", m(r"\mathcal{F}_{k+1}", size=11, color=MUTED),
                       " with each criterion relative to the FOR without fairness (48 rolling steps × 12 directions)."], n)
    f = load("fair.json")
    if f is None:
        placeholder(s, L, 2.2, CW, 4.4, "Fairness results: data pending")
        return s
    st = next(x for x in f["polygons"]["steps"] if x["time"] == "07:30")
    label(s, L, 2.18, 5.8, f"FOR at {st['time']}, intra-aggregator scope (area at {st['time']})")
    styles = [("reference", "Reference", INK, 2.75, None), ("HP", "HP", HP_C, 2.25, None), ("CP", "CP", CP_C, 2.25, None),
              ("HB", "HB (ε = 0.1)", HB_C, 1.5, MSO_LINE_DASH_STYLE.DASH)]
    series, allv = [], []
    for key, name, col, wd, dash in styles:
        pts = st["FOR"][key] + [st["FOR"][key][0]]
        allv += [abs(v) for p in pts for v in p]
        r = st["area_ratio"][key]
        series.append({"name": f"{name}  {100 * r:.1f} %" if key != "reference" else f"{name}  100 %",
                       "xs": [p[0] for p in pts], "ys": [p[1] for p in pts], "color": col, "width": wd, "dash": dash})
    lim = 50 * (int(max(allv) / 50) + 1)
    fr = (L, 2.42, 5.75, 3.45)
    ch = xy_chart(s, *fr, series, x_title="ΔP (kW, + import)", y_title="ΔQ (kvar)", x_range=(-lim, lim), y_range=(-lim, lim),
                  legend=True, size=10, legend_pos=XL_LEGEND_POSITION.RIGHT)
    ch.category_axis.major_unit = 100
    ch.value_axis.major_unit = 100
    # square inner plot: 2.70 × 2.70 in inside the 5.75 × 3.45 frame
    plot_layout(ch, 0.11, 0.04, 2.70 / 5.75, 2.70 / 3.45)
    xR, wR = 6.90, R - 6.90
    rect(s, 6.62, 2.2, 0.012, 3.70, fill=HAIR)
    label(s, xR, 2.18, wR, "Mean FOR area relative to the reference (= 100 %)")
    sm = f["summary"]["energy floor"]
    cats = ["CP", "HP", "HB"]
    intra = [sm[c]["intra-aggregator"]["mean"] for c in cats]
    nw = [sm[c]["network-wide"]["mean"] for c in cats]
    ch2 = bar_chart(s, xR, 2.45, wR, 3.35, cats, [("intra-aggregator", intra, INK_MID), ("network-wide", nw, GREY)],
                    value_max=1.15, value_min=0, gap=70, overlap=-10, label_size=11, cat_size=12, legend=False,
                    label_texts=[[f"{100 * v:.1f} %" for v in intra], [f"{100 * v:.1f} %" for v in nw]])
    for sr, cols in zip(ch2.plots[0].series, ((CP_C, HP_C, HB_C), (CP_T, HP_T, HB_T))):
        for pt, c in zip(sr.points, cols):
            pt.format.fill.solid()
            pt.format.fill.fore_color.rgb = c
    text(s, xR, 5.72, wR, 0.24, "dark: intra-aggregator scope   ·   light: network-wide scope", size=10, color=MUTED,
         italic=True, align=PP_ALIGN.CENTER)
    # bottom strip: service delivery and the energy floor
    yb = 6.00
    rect(s, L, yb, CW, 0.66, fill=CARD, line=HAIR)
    rich(s, L + 0.2, yb + 0.03, 5.55, 0.60, [[("854 kWh  ", {"bold": True, "color": AMBER, "size": 14}),
                                             "export service with HP (intra-aggregator) for the 28 requests, as without fairness; no prosumer imports more in the requested half-hours."]],
         size=11, anchor=MSO_ANCHOR.MIDDLE)
    rich(s, xR, yb + 0.03, wR - 0.2, 0.60, [[("74 %  ", {"bold": True, "color": AMBER, "size": 14}),
                                             "of the FOR kept by HP (intra-aggregator) if ", m(r"D_{s}", size=11), " stopped at ",
                                             m(r"(1-\mathrm{DOD}_{s})\,\overline{E}^{\mathrm{b}}_{s}", size=11), " instead of ",
                                             m(r"\underline{E}^{\mathrm{b}}_{s}", size=11), ", with 21 % less export served."]],
         size=11, anchor=MSO_ANCHOR.MIDDLE)
    notes(s, "Left: F_{k+1} at 07:30 on TR4 (intra-aggregator scope), as deviation from the interface exchange with all BESS "
             "idle; percentages are areas relative to the reference. HB nearly coincides with the reference. Right: mean "
             "over 48 steps of the FOR area relative to the reference: CP 51.5 % / 40.3 %, HP 98.7 % / 98.6 % (minimum "
             "93.7 % / 92.5 % at 12:30), HB 99.8 % / 99.8 % (intra-aggregator / network-wide). CP collapses in the late "
             "afternoon (below 1 % at 17:30–19:30 intra-aggregator, 15:30–19:30 network-wide): the most constrained BESS "
             "fixes ζ for its whole group. Bottom: two-day run with TSO export requests every half-hour 06:00–19:30 on day 1 "
             "(28 requests): HP serves 854.3 kWh of export measured from the P1-baseline point of each step, the same as "
             "without fairness, and no prosumer imports more than in the run without requests (> 1 Wh) in the requested "
             "half-hours. If D_s were measured to (1 − DOD_s)Ē^b_s, HP would keep 74 % / 63 % of the FOR and serve 675.2 kWh (−21 %), "
             "with 22 prosumers importing more in the requested half-hours. Same colors per criterion as on the criteria slide.")
    return s
