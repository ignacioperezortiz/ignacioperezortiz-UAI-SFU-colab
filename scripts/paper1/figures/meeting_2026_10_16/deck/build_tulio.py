"""Deck for the results meeting with Tulio (16-Oct-2026): the team deck unchanged + U_s/D_s slide + 12 results slides.
Run:  python -B build_tulio.py [--data DIR] [--figures DIR] [--out DIR]
  --data     the JSONs (default results/paper1-fairness-2026-10)
  --figures  fig_3d_criteria.png and fig_3d_service_compact.png (default <out>/figures)
  writes <out>/Paper1-results-meeting-Tulio.pptx"""
import sys
from pathlib import Path

from pptx import Presentation
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))     # package root: paths.py
import paths  # noqa: E402
from design import *  # noqa: E402,F403
import build_deck as BD  # noqa: E402
import slides_data as SD  # noqa: E402
import slides_static as ST  # noqa: E402
import slides_tulio as T  # noqa: E402
import slides_res as R1  # noqa: E402
import slides_res2 as R2  # noqa: E402
import slides_res3 as R3  # noqa: E402

OUT = paths.DECK_PPTX                          # file name, written into <out>


def s_cover(prs):
    s = BD.s_cover(prs)
    for sh in s.shapes:
        if sh.has_text_frame:
            for p in sh.text_frame.paragraphs:
                for r in p.runs:
                    if r.text == "Research team meeting":
                        r.text = "Results meeting"
                    elif r.text == "Joint work in progress":
                        r.text = "Case study and results in detail"
                    elif r.text == "October 2026":
                        r.text = "October 16, 2026"
                    elif r.text == "Progress update: P2 updates, fairness criteria and first results":
                        r.text = "Progress update: P2 updates, fairness criteria and results in detail"
    notes(s, "Joint progress of Paper 1 (UAI × SFU): P2 updates, the fairness criteria now implemented, and the results of "
             "the runs in detail (case study TR4). About 50 minutes.")
    return s


def s_agenda(prs, n):
    s = ST.s_agenda(prs, n)
    for sh in s.shapes:
        if sh.has_text_frame:
            for p in sh.text_frame.paragraphs:
                for r in p.runs:
                    if r.text.startswith("About 20 minutes"):
                        r.text = "About 50 minutes; the results in detail are the core; the last part switches to the manuscript."
                    if r.text == " and guarantee  ·  fairness criteria":
                        r.text = " and guarantee  ·  fairness criteria  ·  results in detail"
    return s


def build():
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(SW), Inches(SH)
    s_cover(prs)
    order = (s_agenda, BD.s_framework, ST.s_muf, ST.s_guarantee, SD.s_literature, ST.s_criteria, T.s_headroom,
             SD.s_testcase, SD.s_for_time, SD.s_results_muf_guarantee, SD.s_results_fairness,
             R3.s_headroom_reach, R3.s_criteria_3d, R1.s_area_day, R3.s_criteria_cuts, R3.s_p_only, R3.s_mechanism,
             R2.s_service_3d, R2.s_service_cuts, R2.s_service_hp, R1.s_floor, R1.s_muf_limits, R3.s_summary,
             BD.s_status)
    for n, fn in enumerate(order, start=2):
        fn(prs, n)
    from datetime import datetime
    cp = prs.core_properties
    cp.title = "Fair flexibility aggregation at the TSO–DSO interface: results in detail"
    cp.author = "Ignacio Pérez Ortiz; Tulio Coura"
    cp.last_modified_by = "Ignacio Pérez Ortiz"
    cp.created = cp.modified = datetime.now()
    # no-break space between a number and its unit, so "100 %" never splits across lines
    import re
    nb = re.compile(r"(\d) (%|kWh|kW|kvar|Wh|pp)(?![A-Za-z])")

    def fix_tf(tf):
        for p in tf.paragraphs:
            for r in p.runs:
                if r.text:
                    r.text = nb.sub("\\1\u00a0\\2", r.text)
    for sl in prs.slides:
        for sh in sl.shapes:
            if sh.has_text_frame:
                fix_tf(sh.text_frame)
            if sh.has_table:
                for row in sh.table.rows:
                    for cell in row.cells:
                        fix_tf(cell.text_frame)
    from pptx.oxml.ns import qn
    sz = prs._element.find(qn("p:sldSz"))
    if sz is not None and "type" in sz.attrib:
        del sz.attrib["type"]
    prs.save(paths.out_dir() / OUT)
    print("saved", paths.out_dir() / OUT, len(prs.slides._sldIdLst), "slides")


if __name__ == "__main__":
    paths.cli(__doc__, data=True, figures=True)
    for png, slide in zip(paths.FIGURES, (14, 19)):
        if not (paths.figures_in() / png).is_file():
            print(f"WARNING: {png} not in {paths.figures_in()}: slide {slide} gets a 'pending' box "
                  "(build it with figures/ or make_all.py --figures-only)")
    build()
