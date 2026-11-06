"""Agenda, P2 updates (μ^f, self-consumption guarantee) and fairness criteria, with native inline math."""
from lxml import etree
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

from design import *  # noqa: F403


def m(latex, **o):
    return ("$", latex, o)


def bars(s, x, y, w, items, size=12, gap=10, colors=(AMBER, INK_MID, INK_MID, INK_MID)):
    """Statements with a thin accent bar (first amber, then ink-mid, as in the reference deck)."""
    yy = y
    for i, it in enumerate(items):
        h = it.get("h", 0.62)
        accent_bar(s, x, yy + 0.04, h - 0.08, color=it.get("bar", colors[min(i, len(colors) - 1)]))
        rich(s, x + 0.22, yy, w - 0.22, h, it["p"], size=it.get("size", size), anchor=MSO_ANCHOR.MIDDLE, spacing=2)
        yy += h + gap / 72
    return yy


def arrow(s, x1, y1, x2, y2, color=INK_MID, w=1.75):
    c = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = color
    c.line.width = Pt(w)
    tail = etree.SubElement(c.line._get_or_add_ln(), qn("a:tailEnd"))
    tail.set("type", "triangle")
    tail.set("w", "med")
    tail.set("h", "med")
    return c


# ----------------------------------------------------------------------------- agenda
def s_agenda(prs, n):
    s = content_slide(prs, "Agenda", "Agenda", "About 20 minutes; the last part switches to the manuscript.", n)
    items = [
        ("01", "Framework overview", ["P1 baseline, P2 FOR, service activation, rolling horizon"], ""),
        ("02", "P2 updates", ["throughput penalty ", m(r"\mu^{\mathrm{f}}", size=11, color=MUTED), "  ·  self-consumption guarantee"], "Tulio Coura"),
        ("03", "Fairness in P2", ["literature review  ·  criteria implemented: CP, HP, HB"], "Ignacio Pérez Ortiz"),
        ("04", "Test case and results", ["TR4  ·  FOR over time  ·  ", m(r"\mu^{\mathrm{f}}", size=11, color=MUTED),
                                         " and guarantee  ·  fairness criteria"], "Ignacio Pérez Ortiz  ·  Tulio Coura"),
        ("05", "Manuscript status", ["progress by section, then a look at the draft"], ""),
    ]
    y0, rh = 2.30, 0.82
    rect(s, L, y0, CW, 0.012, fill=INK)
    for i, (num, head, sub, who) in enumerate(items):
        y = y0 + i * rh
        text(s, L, y + 0.16, 0.8, 0.5, num, size=22, color=AMBER, bold=True)
        text(s, L + 0.95, y + 0.12, 7.0, 0.32, head, size=16, color=INK, bold=True)
        rich(s, L + 0.95, y + 0.45, 7.6, 0.28, [sub], size=11, color=MUTED, italic=True)
        if who:
            text(s, R - 4.0, y + 0.24, 4.0, 0.3, who, size=11, color=INK_MID, align=PP_ALIGN.RIGHT)
        if i < len(items) - 1:
            rect(s, L, y + rh, CW, 0.008, fill=HAIR)
    notes(s, "Section 02 summarizes Tulio's updates to P2; section 03 the fairness criteria (Ignacio). Results are on the "
             "LV network of TR4.")
    return s


# ----------------------------------------------------------------------------- throughput penalty
def s_muf(prs, n):
    s = content_slide(prs, "02 · P2 updates", ["Throughput penalty ", m(r"\mu^{\mathrm{f}}", size=27, color=INK), " in the P2 objective"],
                      ["One solve of P2 per direction ", m(r"\theta", size=11, color=MUTED),
                       " gives one FOR boundary point; the second term acts on the BESS throughput in slot k+1."], n)
    rect(s, L, 2.25, CW, 1.05, fill=CARD, line=HAIR)
    label(s, L + 0.25, 2.33, 4.0, "P2, DIRECTION θ ∈ Θ", color=MUTED, size=8.5, upper=False)
    equation(s, L + 0.25, 2.55, CW - 0.5, 0.65,
             r"\min_{\mathbf{x}_{k}}\; -\left(\cos\theta \cdot P^{\mathrm{int}}_{k+1}+\sin\theta \cdot Q^{\mathrm{int}}_{k+1}\right)"
             r" + \mu^{\mathrm{f}} \sum_{s\in\mathcal{S}} \left(P^{\mathrm{b},+}_{s,k+1}+P^{\mathrm{b},-}_{s,k+1}\right)",
             size=22, color=INK, align="center")
    fig = IMG / "fig3a.png"
    if fig.exists():
        from PIL import Image
        wpx, hpx = Image.open(fig).size
        h = 3.15
        w = min(4.4, h * wpx / hpx)
        h = w * hpx / wpx
        picture(s, fig, L, 3.48 + (3.2 - h) / 2, w=w)
    bars(s, 5.75, 3.85, 3.95, [
        {"p": [[("Why", {"bold": True, "color": INK})],
               ["The convex P2 does not exclude charging and discharging a BESS in the same slot."]], "h": 0.95},
        {"p": [[("Effect", {"bold": True, "color": INK})],
               ["With ", m(r"\mu^{\mathrm{f}}>0", size=12), ", simultaneous operation is penalized, so the directional solutions avoid it."]], "h": 1.0},
    ], size=12, gap=16)
    # sketch: both directions at once vs one direction
    bx = 10.0
    for k, (lat, both) in enumerate(((r"\mu^{\mathrm{f}}=0", True), (r"\mu^{\mathrm{f}}>0", False))):
        yy = 3.80 + k * 1.50
        rich(s, bx, yy - 0.05, 2.0, 0.28, [[m(lat, size=12, color=INK_MID)]], size=12)
        rect(s, bx + 0.95, yy + 0.32, 0.95, 0.62, fill=WHITE, line=INK_MID, shape=MSO_SHAPE.ROUNDED_RECTANGLE, line_w=1.5)
        rect(s, bx + 1.90, yy + 0.52, 0.08, 0.22, fill=INK_MID)
        rect(s, bx + 1.02, yy + 0.39, 0.45, 0.48, fill=INK_PALE)
        arrow(s, bx + 0.05, yy + 0.50, bx + 0.90, yy + 0.50, color=INK_MID, w=2.5)
        rich(s, bx + 0.05, yy + 0.18, 0.9, 0.28, [[m(r"P^{\mathrm{b},+}", size=12, color=INK_MID)]], size=12)
        if both:
            arrow(s, bx + 0.90, yy + 0.80, bx + 0.05, yy + 0.80, color=INK_MID, w=2.5)
            rich(s, bx + 0.05, yy + 0.86, 0.9, 0.28, [[m(r"P^{\mathrm{b},-}", size=12, color=INK_MID)]], size=12)
            text(s, bx + 2.08, yy + 0.38, 0.52, 0.5, ["energy", "lost"], size=10.5, color=AMBER, italic=True)
    notes(s, "Objective of P2 for direction θ, as in the manuscript. The first term maximizes the interface exchange along "
             "(cos θ, sin θ) and gives the boundary point v_θ (left: Fig. 3(a) of the draft). The second term, μ^f times "
             "the BESS throughput in slot k+1, discourages simultaneous charging and discharging. Value used in the "
             "tests: μ^f = 0.2.")
    return s


# ----------------------------------------------------------------------------- guarantee
def s_guarantee(prs, n):
    s = content_slide(prs, "02 · P2 updates", "Self-consumption guarantee in P2",
                      "Self-consumption takes priority over service participation.", n)
    rect(s, L, 2.25, CW, 1.05, fill=CARD, line=HAIR)
    label(s, L + 0.25, 2.33, 3.0, "New constraint in P2", color=MUTED, size=8.5)
    equation(s, L + 0.25, 2.55, CW - 0.5, 0.65,
             r"P_{s,t} \leq P^{+,\mathrm{sc}}_{s,t}, \qquad s\in\mathcal{S},\quad t=k+2,\ldots,k+H-1",
             size=24, color=INK, align="center")
    y = 3.62
    text(s, L, y - 0.02, 4.0, 0.25, "Slots of rolling step k", size=10, color=MUTED, italic=True)
    x = L
    cells = [("k", "operation slot", RGBColor(0xD9, 0xDA, 0xDD), TEXT, None, 2.16),
             ("k+1", "flexibility slot: service", PALE_GREEN, GREEN, None, 2.16),
             ("k+2", "", AMBER_PALE, TEXT, AMBER, 2.16), ("k+3", "", AMBER_PALE, TEXT, AMBER, 2.16),
             ("…", "", AMBER_PALE, TEXT, AMBER, 1.0), ("k+H−1", "", AMBER_PALE, TEXT, AMBER, 2.16)]
    for lab, sub, fill, fc, line, w in cells:
        rect(s, x, y + 0.3, w - 0.06, 0.68, fill=fill, line=line, line_w=1.25)
        text(s, x, y + 0.3, w - 0.06, 0.68, [[(lab, {"bold": True})]] + ([[(sub, {"size": 11, "bold": fc == GREEN})]] if sub else []),
             size=13, color=fc, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        x += w
    gx0 = L + 2.16 + 2.16
    rect(s, gx0, y + 1.10, x - gx0 - 0.06, 0.035, fill=AMBER)
    text(s, gx0, y + 1.18, x - gx0 - 0.06, 0.3, "guarantee: later imports within the P1 baseline", size=11.5, color=AMBER, bold=True,
         align=PP_ALIGN.CENTER)
    bars(s, L, 5.32, CW, [
        {"p": [["The DSO may use a prosumer's BESS for the service in slot k+1, but this must not make the prosumer import "
                "more than its P1 baseline later."]], "h": 0.5},
        {"p": [["Slot k+1 is excluded: that is where the service is delivered."]], "h": 0.5},
    ], size=12.5, gap=8)
    notes(s, "New constraint in 'Prosumer Constraints and Horizon' of P2. P_{s,t} is the prosumer's net grid exchange in P2 "
             "and P^{+,sc}_{s,t} its import in the P1 baseline. It holds in every later slot of the horizon, t = k+2, ..., "
             "k+H−1; the flexibility slot k+1 is excluded.")
    return s


# ----------------------------------------------------------------------------- criteria
def s_criteria(prs, n):
    s = content_slide(prs, "03 · Fairness", "Fairness criteria implemented in P2",
                      "The service is shared among the prosumers of each group 𝒢 by a common rule.", n)
    rect(s, L, 2.20, CW, 1.02, fill=CARD, line=HAIR)
    label(s, L + 0.25, 2.27, 3.5, "Service contribution", color=MUTED, size=8.5)
    equation(s, L + 0.25, 2.50, 4.1, 0.6, r"\Delta P^{\mathrm{b}}_{s} = P^{\mathrm{b}}_{s,k+1} - P^{\mathrm{b},\mathrm{sc}}_{s,k+1}", size=19, color=INK)
    rect(s, L + 4.55, 2.32, 0.012, 0.78, fill=HAIR)
    label(s, L + 4.8, 2.27, 3.5, "Headroom limits, every P2 solve", color=MUTED, size=8.5)
    equation(s, L + 4.8, 2.50, 2.7, 0.6, r"-D_{s} \leq \Delta P^{\mathrm{b}}_{s} \leq U_{s}", size=19, color=INK)
    rich(s, L + 7.7, 2.34, CW - 7.9, 0.82,
         [[m(r"U_{s},\ D_{s}", size=11.5), ": largest increase / decrease from the P1 baseline; ",
           m(r"D_{s}", size=11.5), " stops at the energy floor ", m(r"\underline{E}^{\mathrm{b}}_{s}", size=11.5), "."]],
         size=11.5, anchor=MSO_ANCHOR.MIDDLE)
    cards = [
        ("CP", "Capacity-proportional", r"\Delta P^{\mathrm{b}}_{s} = \zeta_{\mathcal{G}} \cdot \overline{P}^{\mathrm{b}}_{s}", 15,
         [["Same fraction of rated power for every prosumer of a group ", m(r"\mathcal{G}", size=11), "."]], "cp", CP_C),
        ("HP", "Headroom-proportional", r"\Delta P^{\mathrm{b}}_{s} = \zeta^{\uparrow}_{\mathcal{G}} U_{s} - \zeta^{\downarrow}_{\mathcal{G}} D_{s}", 15,
         [["Same fraction of each prosumer's headroom, with"],
          [m(r"\zeta^{\uparrow}_{\mathcal{G}},\zeta^{\downarrow}_{\mathcal{G}}\geq 0,\ \zeta^{\uparrow}_{\mathcal{G}}+\zeta^{\downarrow}_{\mathcal{G}}\leq 1", size=11), "."]], "hp", HP_C),
        ("HB", "Headroom band",
         r"-\varepsilon D_{s} \leq \Delta P^{\mathrm{b}}_{s} - \left(\zeta^{\uparrow}_{\mathcal{G}} U_{s} - \zeta^{\downarrow}_{\mathcal{G}} D_{s}\right) \leq \varepsilon U_{s}", 13,
         [["HP within ", m(r"\varepsilon", size=11), " times the prosumer's own headroom;"], [m(r"\varepsilon=0", size=11), " gives HP."]], "hb", HB_C),
    ]
    cw, gap, y = 3.80, 0.20, 3.38
    ch = 2.92
    head = [3.6, 2.4, 1.2, 0.5]   # illustrative headroom of four prosumers (export direction), kW
    for i, (ab, name, tex, esz, desc, kind, col) in enumerate(cards):
        x = L + i * (cw + gap)
        rect(s, x, y, cw, ch, fill=WHITE, line=HAIR)
        rect(s, x, y, cw, 0.06, fill=col)
        text(s, x + 0.22, y + 0.16, 1.0, 0.4, ab, size=20, color=INK, bold=True)
        text(s, x + 1.0, y + 0.25, cw - 1.2, 0.3, name, size=11.5, color=MUTED)
        equation(s, x + 0.10, y + 0.66, cw - 0.20, 0.48, tex, size=esz, color=INK, align="center")
        rich(s, x + 0.22, y + 1.16, cw - 0.44, 0.52, desc, size=11)
        bx, by, bw, bh = x + 0.55, y + 1.80, 0.52, 0.90
        if kind == "cp":
            contrib = [min(head)] * 4
        elif kind == "hp":
            contrib = [0.5 * h for h in head]
        else:
            contrib = [0.5 * h + d for h, d in zip(head, (0.3, -0.2, 0.1, -0.04))]
        for j, (hh, cc) in enumerate(zip(head, contrib)):
            xx = bx + j * (bw + 0.2)
            hh_in, cc_in = bh * hh / 3.6, bh * cc / 3.6
            rect(s, xx, by + bh - hh_in, bw, max(hh_in, 0.01), fill=None, line=GREY, line_w=1)
            rect(s, xx, by + bh - cc_in, bw, max(cc_in, 0.01), fill=col)
            if kind == "hb":
                lo, hi = bh * 0.4 * hh / 3.6, bh * 0.6 * hh / 3.6
                band = rect(s, xx - 0.03, by + bh - hi, bw + 0.06, max(hi - lo, 0.02), fill=None, line=HB_C, line_w=1)
                band.line.dash_style = MSO_LINE_DASH_STYLE.DASH
        rect(s, bx - 0.1, by + bh, 4 * bw + 3 * 0.2 + 0.2, 0.012, fill=GREY)
    rich(s, L, 6.40, 6.0, 0.25, [[("Scopes:  ", {"bold": True, "color": INK}), "intra-aggregator ", m(r"\mathcal{G}=\mathcal{S}_{a}", size=11),
                                  "   ·   network-wide ", m(r"\mathcal{G}=\mathcal{S}", size=11)]], size=11, color=INK_MID)
    text(s, R - 6.4, 6.42, 6.4, 0.22, "illustrative, export direction: outline = headroom, fill = contribution, band = HB tolerance",
         size=10, color=MUTED, italic=True, align=PP_ALIGN.RIGHT)
    notes(s, "Criteria as in the manuscript. ΔP^b_s is the deviation of the net BESS power in slot k+1 from the P1 baseline, "
             "so fairness shares the service, not self-consumption. U_s and D_s are the largest increase and decrease of "
             "P^b_{s,k+1} that the BESS constraints allow without simultaneous charging and discharging or importing more "
             "than P^{+,sc}_{s,t} later, which sets the energy floor E^b_s (underlined) at τ_{k+2}. CP: ζ_G·P̄^b_s. "
             "HP: ζ↑U_s − ζ↓D_s with ζ↑, ζ↓ ≥ 0 and ζ↑ + ζ↓ ≤ 1. HB: −εD_s ≤ ΔP^b_s − (ζ↑U_s − ζ↓D_s) ≤ εU_s. The headroom "
             "limits apply to every solve of P2, fair or not. All are linear with parameters fixed before the directional "
             "solves, so P2 stays a convex QCP and convex combinations of fair setpoints remain fair. Scopes: "
             "intra-aggregator (G = S_a) or network-wide (G = S). Colors used for CP, HP and HB are the same in the results.")
    return s
