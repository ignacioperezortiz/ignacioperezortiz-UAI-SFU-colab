"""Results-in-detail block, part 2: TSO service (data_tulio\\service.json)."""
from pptx.enum.chart import XL_MARKER_STYLE
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN

from design import *  # noqa: F403
from slides_res import EYE, TD, CCOL, m, load, tfrac, legend_line, pending
import slides_data as SD
import paths

RELAX = ORANGE   # guarantee relaxed: orange, dashed (consensus)


def poly_chart(s, x, y, w, h, series, lim=200, size=9, lay=None):
    ch = xy_chart(s, x, y, w, h, series, x_title=None, y_title=None, x_range=(-lim, lim), y_range=(-lim, lim),
                  legend=False, size=size, markers=True)
    ch.category_axis.major_unit = 100
    ch.value_axis.major_unit = 100
    for sr, sd in zip(ch.plots[0].series, series):
        if not sd.get("marker"):
            sr.marker.style = XL_MARKER_STYLE.NONE
        else:
            sr.format.line.fill.background()
    if lay:
        plot_layout(ch, *lay)
    return ch


def closed(poly):
    pts = poly + [poly[0]]
    return [p[0] for p in pts], [p[1] for p in pts]


# ----------------------------------------------------------------------------- R7 3-D with and without service
def s_service_3d(prs, n):
    d = load("service.json")
    s = content_slide(prs, EYE, "With TSO export requests the FOR moves to the import side",
                      "TR4, no fairness constraints, one clear-sky day, stress test: a request for the most-export point every half-hour 06:00–19:30.", n)
    img = paths.figures_in() / "fig_3d_service_compact.png"
    legend_line(s, L, 2.12, CW, [("no TSO request", GREY, False), ("export requests, guarantee on", ORANGE, False),
                                 ("guarantee relaxed", ORANGE, True), ("all BESS idle (0, 0)", INK, True)], align=PP_ALIGN.CENTER)
    if img.exists():
        from PIL import Image
        wpx, hpx = Image.open(img).size
        w = min(CW, 3.55 * wpx / hpx)
        picture(s, img, L + (CW - w) / 2, 2.40, w=w)
    else:
        pending(s, "3-D figure pending")
    on, rx, nr = (d["cases"][k] for k in ("export_guarantee_on", "export_guarantee_relaxed", "no_request"))
    st = d["stored_energy_above_floor_vs_no_request"]
    facts = [("06:30–12:30", "mean export capability 148.8 kW without requests vs ≈ 0 kW with requests (1.6 / 2.0 kW, within ±3 kW): BESS at the DOD floor"),
             ("14:00–18:00", "with the guarantee the most-export point needs net charging beyond the ±3 kW accuracy, up to +34.9 kW at 16:30; relaxed never does"),
             ("20:00", "stored energy vs no request: −46.5 kWh with the guarantee, −150.6 kWh relaxed")]
    yb = 6.00
    tw = (CW - 0.3) / 3
    for i, (h, t) in enumerate(facts):
        x = L + i * (tw + 0.15)
        rect(s, x, yb, tw, 0.62, fill=CARD, line=HAIR)
        text(s, x + 0.12, yb + 0.04, tw - 0.2, 0.56, [[(h + "  ", {"bold": True, "color": ORANGE}), (t, {})]], size=10,
             anchor=MSO_ANCHOR.TOP)
    notes(s, "3-D view of F_{k+1} over the requested slots 06:00–19:30 (export runs build the FOR only there). Grey wireframe: "
             "no TSO request. Left: requests with the self-consumption guarantee (orange). Right: guarantee relaxed (pale orange, dashed). "
             "Thick slices at 07:30, 12:30, 16:30, 19:30 (next slide). Dashed line: all BESS idle (0, 0). After the first "
             "request at 06:00 the BESS sit at the DOD floor and the FOR moves to the import side. With the guarantee, from "
             "14:00 to 18:00 the FOR does not reach the idle point (most-export point +9.8 to +34.9 kW; values at 13:00, "
             "13:30 and 18:30 are within the ±3.1 kW accuracy): the BESS must recharge for the evening. With the guarantee "
             "relaxed the FOR is as large or larger in the afternoon (e.g. 40 652 vs 23 564 kW·kvar at 17:30), but the BESS "
             "end the day at the DOD floor (mean SOC 10 %). Coordinates: deviation from the all-idle exchange, estimated within "
             "±3.1 kW / ±4.1 kvar.")
    return s


# ----------------------------------------------------------------------------- R8 cuts with and without service
def s_service_cuts(prs, n):
    d = load("service.json")
    s = content_slide(prs, EYE, "Cuts of the FOR with and without TSO service",
                      ["ΔP–ΔQ of ", m(r"\mathcal{F}_{k+1}", size=11, color=MUTED),
                       " at four requested slots; % = area relative to the FOR without requests at the same slot."], n)
    legend_line(s, L, 2.17, CW, [("no TSO request", GREY, False), ("export requests, guarantee on", ORANGE, False),
                                 ("guarantee relaxed", RELAX, True)])
    text(s, R - 4.6, 2.17, 4.6, 0.24, [[("●  requested = delivered point (guarantee on)", {"color": ORANGE, "bold": True}), ("     x: ΔP (kW) · y: ΔQ (kvar)", {"color": MUTED})]], size=10, align=PP_ALIGN.RIGHT)
    hours = ["07:30", "12:30", "16:30", "19:30"]
    gap = 0.15
    w = (CW - 3 * gap) / 4
    for i, hh in enumerate(hours):
        c = d["cuts"][hh]
        x = L + i * (w + gap)
        ser = []
        for key, col, wd, dash in (("no_request", GREY, 2.0, None), ("export_guarantee_relaxed", RELAX, 1.75, MSO_LINE_DASH_STYLE.DASH),
                                   ("export_guarantee_on", ORANGE, 2.25, None)):
            xs, ys = closed(c[key]["polygon"])
            ser.append({"name": key, "xs": xs, "ys": ys, "color": col, "width": wd, "dash": dash})
        rp = c["export_guarantee_on"]["requested_point"]
        ser.append({"name": "req", "xs": [rp[0]], "ys": [rp[1]], "color": ORANGE, "marker": XL_MARKER_STYLE.CIRCLE, "marker_size": 7})
        text(s, x, 2.52, w, 0.26, hh, size=13, color=INK, bold=True, align=PP_ALIGN.CENTER)
        poly_chart(s, x, 2.78, w, w, ser, lay=(0.17, 0.04, 0.80, 0.80))
        on, rx, nr = c["export_guarantee_on"], c["export_guarantee_relaxed"], c["no_request"]
        fmt = lambda r: f"[{r[0]:+.1f}, {r[1]:+.1f}]".replace("-", "−")  # noqa: E731
        lines = [[("ΔP range (kW)", {"bold": True, "color": INK})],
                 [("no request  ", {"color": MUTED}), fmt(nr["dP_range"])],
                 [("guarantee  ", {"color": ORANGE}), fmt(on["dP_range"]), (f"  {on['area_pct_of_no_request']:.0f} %", {"color": MUTED})],
                 [("relaxed  ", {"color": RELAX}), fmt(rx["dP_range"]), (f"  {rx['area_pct_of_no_request']:.0f} %", {"color": MUTED})],
                 [("mean SOC  ", {"color": MUTED}), f"{nr['soc_mean_pct']:.0f} / {on['soc_mean_pct']:.0f} / {rx['soc_mean_pct']:.0f} %"]]
        lines = [[it if isinstance(it, tuple) else (it, {}) for it in ln] for ln in lines]
        text(s, x + 0.12, 2.78 + w + 0.05, w - 0.15, 1.1, lines, size=9.5, color=TEXT)
    notes(s, "Each panel: F_{k+1} at one requested slot as deviation (ΔP, ΔQ) from the all-idle exchange; x = ΔP, y = ΔQ, "
             "±200 kW/kvar, same scale in all panels. The dot is the requested (and delivered) most-export point with the "
             "guarantee. 07:30: after the first request the BESS are at the DOD floor and the FOR keeps only the import side "
             "(55 % of the area). 12:30: the FOR without requests is on the export side (BESS full), with requests it lies on the "
             "import side. 16:30: with the guarantee the most-export point is +34.9 kW (net charging for the evening); "
             "relaxed it is −1.0 kW and the FOR is 21 % larger than without requests. 19:30: last request. The idle-point "
             "estimate is within ±3.1 kW / ±4.1 kvar, so −0.9 kW at 12:30 is zero within accuracy; +34.9 kW is not.")
    return s


# ----------------------------------------------------------------------------- R9 HP under service
def s_service_hp(prs, n):
    d = load("service.json")
    a = d["area_ratios"]["hp_energy_floor_vs_export_guarantee_on"]
    s = content_slide(prs, EYE, "Fairness under service: HP keeps the FOR and the service",
                      "TR4, export requests every half-hour 06:00–19:30 on day 1, self-consumption guarantee on; HP intra-aggregator, energy floor.", n)
    label(s, L, 2.18, 7.4, "HP AREA VS NO FAIRNESS, PER REQUESTED SLOT (%)", upper=False)
    t = tfrac(d["times"])
    ys = a["pct"]
    ser = [{"name": "ref", "xs": [t[0], t[-1]], "ys": [100, 100], "color": GREY, "width": 1.0, "dash": MSO_LINE_DASH_STYLE.DASH},
           {"name": "HP", "xs": t, "ys": ys, "color": HP_C, "width": 2.5}]
    ch = xy_chart(s, L, 2.45, 7.4, 3.2, ser, x_range=(0.25, 0.8125), y_range=(0, 105), legend=False, size=10, x_fmt="[hh]:mm")
    ch.category_axis.major_unit = 0.0625
    ch.value_axis.major_unit = 25
    plot_layout(ch, 0.09, 0.06, 0.88, 0.80)
    text(s, L, 5.75, 7.4, 0.5, f"mean {a['mean_pct']:.2f} %, minimum {a['min_pct']:.2f} % at {a['min_at']}, at least 99 % in "
         f"{a['slots_at_or_above_99pct']} of 28 slots. Same system state at every requested slot (each BESS within 0.01 pp of SOC).",
         size=10.5, color=MUTED, italic=True)
    xR, wR = 8.55, R - 8.55
    label(s, xR, 2.18, wR, "Service delivered")
    c = d["cases"]
    tiles = [("Export service (kWh, vs P1 baselines)",
              [("without fairness", f"{c['export_guarantee_on']['export_served_kWh']:.1f}"), ("HP, energy floor", f"{c['hp_energy_floor']['export_served_kWh']:.1f}"),
               ("HP, earlier floor", f"{c['hp_old_floor']['export_served_kWh']:.1f}")]),
             ("Prosumers importing > 1 Wh more in the requested half-hours",
              [("without fairness", f"{c['export_guarantee_on']['extra_import']['inside_requested_halfhours']['prosumers_above_1Wh']} of 46"),
               ("HP, energy floor", f"{c['hp_energy_floor']['extra_import']['inside_requested_halfhours']['prosumers_above_1Wh']} of 46"),
               ("HP, earlier floor", f"{c['hp_old_floor']['extra_import']['inside_requested_halfhours']['prosumers_above_1Wh']} of 46")])]
    for i, (ttl, rows) in enumerate(tiles):
        y = 2.48 + i * 1.95
        rect(s, xR, y, wR, 1.80, fill=CARD, line=HAIR)
        text(s, xR + 0.18, y + 0.08, wR - 0.3, 0.45, ttl, size=10, color=MUTED)
        for j, (lab, v) in enumerate(rows):
            yy = y + 0.55 + j * 0.38
            col = GREY if j == 0 else (HP_C if j == 1 else MUTED)
            text(s, xR + 0.18, yy, 2.2, 0.34, lab, size=11, color=TEXT, anchor=MSO_ANCHOR.MIDDLE)
            text(s, xR + 2.3, yy, wR - 2.5, 0.34, v, size=14 if j < 2 else 12, color=INK if j < 2 else MUTED, bold=j < 2,
                 anchor=MSO_ANCHOR.MIDDLE, align=PP_ALIGN.RIGHT)
    text(s, xR, 6.40, wR, 0.24, f"earlier floor: worst +{c['hp_old_floor']['extra_import']['inside_requested_halfhours']['worst_kWh']:.2f} kWh; "
         "its run follows a different state of charge", size=9.5, color=MUTED, italic=True)
    notes(s, "Left: FOR area with HP (intra-aggregator, energy floor) over the FOR without fairness, both with the export "
             "requests and the guarantee, at each of the 28 requested slots. Full 0–105 % scale; dashed line = 100 %. Both runs "
             "have the same state of charge at every requested slot (fleet mean within 0.003 pp, each BESS within 0.01 pp); "
             "they diverge only after 20:00. Right: export service measured from the P1-baseline point of each step; imports "
             "compared with the run without requests with the same criterion and floor. With the earlier floor "
             "(1 − DOD_s)Ē^b_s, HP serves 21 % less and 22 prosumers import more within the requested half-hours (21 above "
             "10 Wh); that run follows a different state of charge, so its FOR is not plotted.")
    return s
