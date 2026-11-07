"""Slides added for the meeting with Tulio: U_s / D_s definition and the detailed case-study results."""
import json

from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from design import *  # noqa: F403
from slides_static import arrow, bars
import paths

DATA = "data"          # the deck's data\ and data_tulio\ folders; paths.deck_json finds their files in --data
TD = "data_tulio"


def m(latex, **o):
    return ("$", latex, o)


def load(name, folder=None):
    p = paths.deck_json(folder or TD, name)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


# ----------------------------------------------------------------------------- U_s and D_s
def s_headroom(prs, n):
    s = content_slide(prs, "03 · Fairness", ["Headroom of each prosumer: ", m(r"U_{s}", size=27, color=INK), " and ",
                                            m(r"D_{s}", size=27, color=INK)],
                      ["Largest increase and decrease of ", m(r"P^{\mathrm{b}}_{s,k+1}", size=11, color=MUTED),
                       " from the P1 baseline, computed after P1 and fixed in every solve of P2."], n)
    rect(s, L, 2.20, 8.05, 2.55, fill=CARD, line=HAIR)
    label(s, L + 0.25, 2.28, 4.0, "EQ. (13a) AND (13b) OF THE DRAFT", color=MUTED, size=8.5, upper=False)
    equation(s, L + 0.2, 2.55, 7.7, 0.85,
             r"U_{s}=\left[\min\left\{\overline{P}^{\mathrm{b}}_{s},\ \frac{\overline{E}^{\mathrm{b}}_{s}-E^{\mathrm{b},\mathrm{sc}}_{s,k+1}}"
             r"{\eta^{\mathrm{b},+}_{s}\cdot\Delta t}\right\}-P^{\mathrm{b},\mathrm{sc}}_{s,k+1}\right]^{+}", size=17, color=INK)
    equation(s, L + 0.2, 3.45, 7.7, 1.15,
             r"D_{s}=\left[\min\left\{\overline{P}^{\mathrm{b}}_{s},\ \frac{\eta^{\mathrm{b},-}_{s}\left(E^{\mathrm{b},\mathrm{sc}}_{s,k+1}-\underline{E}^{\mathrm{b}}_{s}\right)}{\Delta t},"
             r"\ \frac{E^{\mathrm{b},\mathrm{sc}}_{s,k+1}-\underline{E}^{\mathrm{b}}_{s}}{\eta^{\mathrm{b},+}_{s}\cdot\Delta t}\right\}+P^{\mathrm{b},\mathrm{sc}}_{s,k+1}\right]^{+}",
             size=17, color=INK)
    bars(s, L, 4.95, 8.05, [
        {"p": [[("Energy floor ", {"bold": True, "color": INK}), m(r"\underline{E}^{\mathrm{b}}_{s}", size=12),
                (": the lowest energy at ", {}), m(r"\tau_{k+2}", size=12),
                " from which the BESS limits, the terminal condition and the self-consumption guarantee "
                "(no import above ", m(r"P^{+,\mathrm{sc}}_{s,t}", size=12), " later) can still be met."]], "h": 0.78},
        {"p": [[("Use, eq. (14): ", {"bold": True, "color": INK}), m(r"-D_{s}\leq\Delta P^{\mathrm{b}}_{s}\leq U_{s}", size=12),
                " in every P2 solve; HP shares the service in proportion to ", m(r"U_{s}", size=12), " and ",
                m(r"D_{s}", size=12), ", HB within a band ", m(r"\varepsilon", size=12), " around it."]], "h": 0.62},
    ], size=12, gap=8)
    # schematic: stored energy axis with the two headroom ranges
    x0, y_top, y_bot = 9.35, 2.35, 6.35
    text(s, x0 - 0.1, 2.12, 3.3, 0.24, "Stored energy at the end of slot k+1 (schematic)", size=9.5, color=MUTED, italic=True)
    rect(s, x0 + 0.55, y_top + 0.15, 0.55, y_bot - y_top - 0.15, fill=INK_PALE, line=INK_MID, line_w=1)
    levels = [(y_top + 0.15, r"\overline{E}^{\mathrm{b}}_{s}", "capacity"),
              (3.95, r"E^{\mathrm{b},\mathrm{sc}}_{s,k+2}", "P1 baseline"),
              (5.25, r"\underline{E}^{\mathrm{b}}_{s}", "energy floor"),
              (6.05, r"(1-\mathrm{DOD}_{s})\,\overline{E}^{\mathrm{b}}_{s}", "minimum SOC")]
    for y, lat, nm in levels:
        rect(s, x0 + 0.40, y, 0.85, 0.02, fill=INK if nm != "minimum SOC" else GREY)
        rich(s, x0 + 1.35, y - 0.17, 1.90, 0.34, [[m(lat, size=11, color=INK if nm != "minimum SOC" else MUTED), ("  " + nm, {"size": 9.5, "color": MUTED, "italic": True})]], size=11)
    arrow(s, x0 + 0.22, 3.95, x0 + 0.22, y_top + 0.2, color=INK, w=2.25)
    rich(s, x0 - 0.42, 3.0, 0.6, 0.3, [[m(r"U_{s}", size=13, color=INK)]], size=13)
    arrow(s, x0 + 0.22, 3.98, x0 + 0.22, 5.22, color=INK, w=2.25)
    rich(s, x0 - 0.42, 4.45, 0.6, 0.3, [[m(r"D_{s}", size=13, color=INK)]], size=13)
    text(s, x0 - 0.1, 6.40, 3.3, 0.22, "converted to power with η and Δt; capped by the rating", size=9, color=MUTED, italic=True)
    notes(s, "Definitions as in the draft, eqs. (13a) and (13b). U_s and D_s are the largest increase and decrease of the "
             "net BESS power in slot k+1 from the P1 baseline that the BESS equations, the terminal condition and the "
             "absence of simultaneous charging and discharging allow, without importing more than P^{+,sc}_{s,t} later. "
             "The latter sets the energy floor E^b_s (underlined) at τ_{k+2}; without that limit it equals (1 − DOD_s)Ē^b_s. "
             "The third term of the min in D_s applies only when the floor exceeds E^{b,sc}_{s,k+1}, i.e. when the BESS "
             "must keep charging; then the conversion uses 1/η^{b,+}. [·]^+ = max{0, ·}: a full idle BESS has U_s = 0. "
             "The schematic on the right is not to scale.")
    return s
