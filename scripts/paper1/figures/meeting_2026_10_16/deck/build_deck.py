"""Research-team deck: Paper 1 progress (Ignacio Pérez Ortiz and Tulio Coura). Fully editable: native text, shapes,
equations (OMML) and charts; only the paper figures are pictures. Nomenclature follows Methodology_v63.tex.
In this package it is a library of build_tulio.py (s_cover, s_framework, s_status); running it writes nothing."""
import sys
from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches

sys.path.insert(0, str(Path(__file__).parent))
from design import *  # noqa: E402,F403
import slides_data as SD  # noqa: E402
import slides_static as ST  # noqa: E402

OUT = HERE / "Paper1-progress-research-team.pptx"


def s_cover(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    frame(s)
    text(s, L, 1.42, CW, 0.2, [[("UAI × SFU COLLABORATION  ·  PAPER 1", {"tracking": 170})]], size=10, color=AMBER, bold=True)
    text(s, L, 1.80, CW, 1.3, ["Fair flexibility aggregation at the TSO–DSO interface",
                                 [("Progress update: P2 updates, fairness criteria and first results", {"size": 16, "bold": False, "color": INK_MID})]],
         size=33, color=INK, bold=True, spacing=8)
    rect(s, L, 3.58, 1.35, 0.06, fill=AMBER)
    text(s, L, 3.86, 9.4, 0.6, ["Research team meeting", [("Joint work in progress", {"size": 10.5, "italic": True, "color": GREY, "bold": False})]],
         size=15, color=TEXT, bold=True, spacing=4)
    text(s, L, 5.0, 9.0, 0.75, ["Ignacio Andrés Pérez Ortiz   ·   Tulio Coura",
                                [("Universidad Adolfo Ibáñez   ·   Simon Fraser University", {"size": 10.5, "bold": False, "color": MUTED})]],
         size=15, color=INK, bold=True, spacing=4)
    rect(s, L, 6.22, CW, 0.012, fill=HAIR)
    picture(s, IMG / "logo_uai.png", L, 6.46, h=0.44)
    picture(s, IMG / "logo_sfu.png", R - 1.80, 6.46, h=0.44)
    text(s, 2.55, 6.55, 8.25, 0.3, "October 2026", size=10, color=MUTED, align=PP_ALIGN.CENTER)
    notes(s, "Joint progress of Paper 1 (UAI × SFU): what changed in P2 (Tulio), the fairness criteria now implemented "
             "(Ignacio), first results on TR4 and the status of the manuscript. About 20 minutes.")
    return s


def s_framework(prs, n):
    s = content_slide(prs, "01 · Framework", "Framework overview",
                      "Prosumers keep their self-consumption first; the DSO offers the TSO a network-feasible region.", n)
    fig = IMG / "fig1_framework.png"
    if fig.exists():
        from PIL import Image
        wpx, hpx = Image.open(fig).size
        h = 4.45
        w = h * wpx / hpx
        if w > 7.3:
            w, h = 7.3, 7.3 * hpx / wpx
        picture(s, fig, R - w, 2.12 + (4.45 - h) / 2, w=w)
    items = [
        {"p": [[("Bottom-up construction", {"bold": True, "color": GREEN})],
               ["P1: each prosumer's self-consumption baseline and residual P–Q flexibility. P2: the DSO builds the FOR ",
                ST.m(r"\mathcal{F}_{k+1}", size=13), " under network and fairness constraints."]], "bar": GREEN, "h": 1.40},
        {"p": [[("Top-down activation", {"bold": True, "color": ORANGE})],
               ["The TSO may request a point inside the FOR; BESS setpoints are recovered from stored P2 solutions, "
                "without a new optimization. Otherwise, the baselines are retained."]], "bar": ORANGE, "h": 1.40},
        {"p": [[("Rolling horizon", {"bold": True, "color": INK})],
               ["24-h horizon advancing one slot per step, from the measured SOCs (case study: ",
                ST.m(r"\Delta t=30\ \mathrm{min},\ H=48", size=13), ")."]], "bar": INK, "h": 1.00},
    ]
    ST.bars(s, L, 2.25, 4.15, items, size=13, gap=10)
    notes(s, "Fig. 1 of the manuscript. S1: measured SOCs; S2: P1 baselines and residual flexibility; S3: aggregators "
             "forward offers; S4: P2 builds the reference and fair FOR for slot k+1; S5: TSO request (yes/no); S6: "
             "setpoint recovery; S7: actions applied at τ_{k+1}; S8: next rolling step.")
    return s


def s_status(prs, n):
    s = content_slide(prs, "05 · Manuscript", "Manuscript status", "Progress by section; next, a look at the current draft.", n)
    rows = [("Introduction", 0.80, "80 %", "functional version"),
            ("Methodology", 0.95, "95 %", "complete; condense and polish wording"),
            ("Case study", 0.175, "15–20 %", "starting"),
            ("Results and analysis", 0.0, "0 %", ""),
            ("Discussion", 0.0, "0 %", ""),
            ("Conclusion", 0.0, "0 %", "")]
    y0, rh = 2.35, 0.62
    bx, bw = 3.40, 5.40
    for i, (name, frac, pct, note) in enumerate(rows):
        y = y0 + i * rh
        text(s, L, y + 0.08, 2.5, 0.35, name, size=14, color=INK, bold=True)
        rect(s, bx, y + 0.14, bw, 0.26, fill=INK_PALE)
        if name == "Case study":
            rect(s, bx, y + 0.14, bw * 0.20, 0.26, fill=HB_T)
            rect(s, bx, y + 0.14, bw * 0.15, 0.26, fill=INK_MID)
        elif frac > 0:
            rect(s, bx, y + 0.14, bw * frac, 0.26, fill=INK_MID)
        text(s, 8.95, y + 0.08, 1.0, 0.35, pct, size=14, color=INK, bold=True)
        text(s, 10.05, y + 0.0, 2.55, 0.5, note, size=10, color=MUTED, italic=True, anchor=MSO_ANCHOR.MIDDLE)
    rect(s, R - 3.3, 6.20, 3.3, 0.42, fill=INK, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    text(s, R - 3.3, 6.20, 3.3, 0.42, "Next: the draft  →", size=12, color=WHITE, bold=True, align=PP_ALIGN.CENTER,
         anchor=MSO_ANCHOR.MIDDLE)
    notes(s, "Introduction: functional version (80 %). Methodology: complete (95 %), to be condensed and polished. "
             "Case study: starting (15–20 %). Results and analysis, discussion and conclusion: not started. "
             "Then switch to the PDF of the draft.")
    return s


def build():
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(SW), Inches(SH)
    s_cover(prs)
    order = (ST.s_agenda, s_framework, ST.s_muf, ST.s_guarantee, SD.s_literature, ST.s_criteria, SD.s_testcase,
             SD.s_for_time, SD.s_results_muf_guarantee, SD.s_results_fairness, s_status)
    for n, fn in enumerate(order, start=2):
        fn(prs, n)
    from datetime import datetime
    from pptx.oxml.ns import qn
    cp = prs.core_properties
    cp.title = "Fair flexibility aggregation at the TSO–DSO interface: progress update"
    cp.author = "Ignacio Pérez Ortiz; Tulio Coura"
    cp.last_modified_by = "Ignacio Pérez Ortiz"
    cp.created = cp.modified = datetime.now()
    cp.subject = "Paper 1 progress, research team meeting"
    sz = prs._element.find(qn("p:sldSz"))
    if sz is not None and "type" in sz.attrib:
        del sz.attrib["type"]
    alts = {"fig1_framework.png": "Fig. 1 of the draft: proposed coordination framework, steps S1 to S8",
            "fig3a.png": "Fig. 3(a) of the draft: one P2 solve per direction theta gives a boundary point of the FOR",
            "network_mv.png": "Fig. 4(a) of the draft: UK MV-LV network, nine transformers, TR4 shaded",
            "network_tr4.png": "Fig. 4(b) of the draft: LV network of TR4 with consumers and prosumers of three aggregators",
            "logo_uai.png": "Universidad Adolfo Ibanez logo", "logo_sfu.png": "Simon Fraser University logo"}
    for sl in prs.slides:
        for sh in sl.shapes:
            if sh.shape_type == 13:
                nv = sh._element.find(qn("p:nvPicPr")).find(qn("p:cNvPr"))
                nm = nv.get("descr", "")
                for k, v in alts.items():
                    if nm == k:
                        nv.set("descr", v)
    prs.save(OUT)
    import zipfile, shutil, tempfile
    tmp = Path(tempfile.mkdtemp()) / "x.pptx"
    with zipfile.ZipFile(OUT) as zi, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zo:
        for it in zi.infolist():
            data = zi.read(it.filename)
            if it.filename == "docProps/app.xml":
                data = data.replace(b"On-screen Show (4:3)", b"Widescreen")
            zo.writestr(it, data)
    shutil.move(str(tmp), OUT)
    print("saved", OUT, len(prs.slides._sldIdLst), "slides")


if __name__ == "__main__":   # in this package: library only (build() would write the 14-Oct team deck next to this file)
    print("build_deck.py is a library of build_tulio.py (the cover, framework and status slides); it writes nothing. "
          "Build the deck with deck/build_tulio.py or make_all.py.")
