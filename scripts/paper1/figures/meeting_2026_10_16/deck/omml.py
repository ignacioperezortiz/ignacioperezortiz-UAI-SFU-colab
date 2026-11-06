"""LaTeX -> native, editable PowerPoint equations (OMML inside a14:m), via MathML and Office's MML2OMML.XSL."""
import copy
import re
import sys
from pathlib import Path

from lxml import etree

from latex2mathml.converter import convert  # pip package, pinned to 3.81.1 in requirements.txt

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))     # package root: paths.py
import paths  # noqa: E402

XSL = etree.XSLT(etree.parse(str(paths.mml2omml_xsl())))
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
A14 = "http://schemas.microsoft.com/office/drawing/2010/main"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _prep(latex):
    """Work around what latex2mathml/MML2OMML lose: upright text, spacing, upright operators."""
    t = re.sub(r"\\mathrm\{([^}]*)\}", r"\\text{\1}", latex)
    t = t.replace(r"\qquad", "\\text{\u2003\u2003}").replace(r"\quad", "\\text{\u2003}").replace(r"\;", "\\text{\u2005}").replace(r"\,", "\\text{\u2009}")
    for op in ("min", "max", "conv"):
        t = t.replace("\\" + op, "\\text{" + op + "}")
    for op in ("cos", "sin"):
        t = t.replace("\\" + op, "\\text{" + op + "\u2009}")
    t = t.replace(r"\Delta", "\\text{\u0394}")
    t = t.replace(r"\overline", r"\bar")
    return t


def _bar(e_children, pos):
    bar = etree.Element(f"{{{M}}}bar")
    pr = etree.SubElement(bar, f"{{{M}}}barPr")
    etree.SubElement(pr, f"{{{M}}}pos", {f"{{{M}}}val": pos})
    e = etree.SubElement(bar, f"{{{M}}}e")
    for c in e_children:
        e.append(c)
    return bar


def omath(latex):
    """OMML <m:oMath> element for a LaTeX string (Word flavour, run properties still to be adapted)."""
    mml = etree.fromstring(convert(_prep(latex)).encode("utf-8"))
    # \left X ... \right Y  ->  <mfenced>, which MML2OMML turns into a stretchy m:d delimiter
    MM = "http://www.w3.org/1998/Math/MathML"
    for row in list(mml.iter(f"{{{MM}}}mrow")):
        kids = list(row)
        if (len(kids) >= 2 and kids[0].tag == f"{{{MM}}}mo" and kids[0].get("fence") == "true"
                and kids[-1].tag == f"{{{MM}}}mo" and kids[-1].get("fence") == "true"):
            fen = etree.Element(f"{{{MM}}}mfenced", open=kids[0].text or "", close=kids[-1].text or "", separators="")
            inner = etree.SubElement(fen, f"{{{MM}}}mrow")
            for k in kids[1:-1]:
                inner.append(k)
            for k in list(row):
                row.remove(k)
            row.append(fen)
    out = XSL(mml).getroot()
    om = out if out.tag == f"{{{M}}}oMath" else out.find(f".//{{{M}}}oMath")
    # \underline{E}: limLow with a U+2015 rule underneath -> bottom bar
    for ll in list(om.iter(f"{{{M}}}limLow")):
        lim = ll.find(f"{{{M}}}lim")
        if lim is not None and "".join(lim.itertext()) == "\u2015":
            ll.getparent().replace(ll, _bar(list(ll.find(f"{{{M}}}e")), "bot"))
    for acc in list(om.iter(f"{{{M}}}acc")):
        chr_ = acc.find(f"{{{M}}}accPr/{{{M}}}chr")
        if chr_ is not None and chr_.get(f"{{{M}}}val") == "\u2015":
            acc.getparent().replace(acc, _bar(list(acc.find(f"{{{M}}}e")), "top"))
    # upright text as plain math style (scales in scripts), not "normal text"
    for nor in list(om.iter(f"{{{M}}}nor")):
        rpr = nor.getparent()
        rpr.remove(nor)
        etree.SubElement(rpr, f"{{{M}}}sty", {f"{{{M}}}val": "p"})
    # PowerPoint drops astral-plane letters (e.g. script S) when they share a run with other characters
    for r in list(om.iter(f"{{{M}}}r")):
        t = r.find(f"{{{M}}}t")
        if t is None or not t.text or len(t.text) < 2 or not any(ord(c) > 0xFFFF for c in t.text):
            continue
        parent, idx = r.getparent(), list(r.getparent()).index(r)
        parent.remove(r)
        for j, ch in enumerate(t.text):
            nr = copy.deepcopy(r)
            nr.find(f"{{{M}}}t").text = ch
            parent.insert(idx + j, nr)
    return om


def _rpr(size_pt, color_hex, bold=False):
    r = etree.Element(f"{{{A}}}rPr", lang="en-US", sz=str(int(size_pt * 100)), b="1" if bold else "0", i="0")
    fill = etree.SubElement(r, f"{{{A}}}solidFill")
    etree.SubElement(fill, f"{{{A}}}srgbClr", val=color_hex)
    etree.SubElement(r, f"{{{A}}}latin", typeface="Cambria Math")
    etree.SubElement(r, f"{{{A}}}cs", typeface="Cambria Math")
    return r


def _styled(latex, size_pt, color_hex):
    om = copy.deepcopy(omath(latex))
    for wr in om.iter(f"{{{W}}}rPr"):
        wr.getparent().remove(wr)
    for mr in om.iter(f"{{{M}}}r"):
        old = mr.find(f"{{{A}}}rPr")
        if old is not None:
            mr.remove(old)
        t = mr.find(f"{{{M}}}t")
        mr.insert(list(mr).index(t) if t is not None else 0, _rpr(size_pt, color_hex))
    return om


def _wrap(math_el, fallback_text=""):
    ac = etree.Element(f"{{{MC}}}AlternateContent", nsmap={"mc": MC})
    choice = etree.SubElement(ac, f"{{{MC}}}Choice", Requires="a14", nsmap={"a14": A14})
    m = etree.SubElement(choice, f"{{{A14}}}m")
    m.append(math_el)
    fb = etree.SubElement(ac, f"{{{MC}}}Fallback")
    if fallback_text:
        r = etree.SubElement(fb, f"{{{A}}}r")
        etree.SubElement(r, f"{{{A}}}rPr", lang="en-US")
        etree.SubElement(r, f"{{{A}}}t").text = fallback_text
    return ac


def add_inline(paragraph, latex, size_pt=12, color_hex="273640"):
    """Append an inline native equation after the paragraph's current runs."""
    ac = _wrap(_styled(latex, size_pt, color_hex), latex)
    p = paragraph._p
    end = p.find(f"{{{A}}}endParaRPr")
    if end is not None:
        end.addprevious(ac)
    else:
        p.append(ac)
    return ac


def add_equation(paragraph, latex, size_pt=18, color_hex="273640", align="left"):
    """Append a native equation to a python-pptx paragraph (the paragraph should hold nothing else)."""
    om = copy.deepcopy(omath(latex))
    for wr in om.iter(f"{{{W}}}rPr"):
        wr.getparent().remove(wr)
    for mr in om.iter(f"{{{M}}}r"):
        old = mr.find(f"{{{A}}}rPr")
        if old is not None:
            mr.remove(old)
        t = mr.find(f"{{{M}}}t")
        mr.insert(list(mr).index(t) if t is not None else 0, _rpr(size_pt, color_hex))
    para = etree.Element(f"{{{M}}}oMathPara")
    ppr = etree.SubElement(para, f"{{{M}}}oMathParaPr")
    etree.SubElement(ppr, f"{{{M}}}jc", {f"{{{M}}}val": {"left": "left", "center": "centerGroup", "right": "right"}[align]})
    para.append(om)
    ac = etree.Element(f"{{{MC}}}AlternateContent", nsmap={"mc": MC})
    choice = etree.SubElement(ac, f"{{{MC}}}Choice", Requires="a14", nsmap={"a14": A14})
    m = etree.SubElement(choice, f"{{{A14}}}m")
    m.append(para)
    fb = etree.SubElement(ac, f"{{{MC}}}Fallback")
    p = paragraph._p
    end = p.find(f"{{{A}}}endParaRPr")
    if end is not None:
        end.addprevious(ac)
    else:
        p.append(ac)
    return ac
