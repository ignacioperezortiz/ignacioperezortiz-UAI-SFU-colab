"""Design system and primitives, copied from the 10-Sep-2026 research-team deck (meeting-presentation-10-09-26-v2.pptx):
white slide, ink spine + amber hairline on the left, amber eyebrow, ink title, amber rule, italic subtitle, footer."""
from pathlib import Path

from lxml import etree
from pptx.chart.data import CategoryChartData, XyChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION, XL_TICK_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

from omml import add_equation

HERE = Path(__file__).parent
IMG = HERE / "img"
FONT = "MADE TOMMY"

INK = RGBColor(0x14, 0x35, 0x4A)
INK_MID = RGBColor(0x3D, 0x63, 0x7B)
INK_PALE = RGBColor(0xDD, 0xE7, 0xED)
AMBER = RGBColor(0xC4, 0x86, 0x3C)
AMBER_PALE = RGBColor(0xF3, 0xE6, 0xD5)
TEXT = RGBColor(0x27, 0x36, 0x40)
MUTED = RGBColor(0x7C, 0x8C, 0x97)
HAIR = RGBColor(0xD5, 0xDF, 0xE6)
CARD = RGBColor(0xF6, 0xF9, 0xFA)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GREEN = RGBColor(0x1D, 0x7A, 0x55)   # Fig. 1: bottom-up flexibility construction
ORANGE = RGBColor(0xC8, 0x55, 0x1B)  # Fig. 1: top-down service activation
GREY = RGBColor(0x9A, 0xA8, 0xB2)

SW, SH = 13.3333, 7.5
L, R = 0.80, 12.60
CW = R - L
FOOTER = "Ignacio Pérez Ortiz  ·  Tulio Coura     ·     Paper 1 progress     ·     UAI × SFU Collaboration"


def hexs(rgb):
    return str(rgb)


def rect(slide, x, y, w, h, fill=None, line=None, shape=MSO_SHAPE.RECTANGLE, line_w=0.75):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if fill is None:
        s.fill.background()
    else:
        s.fill.solid()
        s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(line_w)
    s.shadow.inherit = False
    if s.has_text_frame:
        s.text_frame.text = ""
    return s


def text(slide, x, y, w, h, runs, size=11, color=TEXT, bold=False, italic=False, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, spacing=None, line_spacing=None, wrap=True):
    """runs: str, or list of paragraphs; a paragraph is a str or a list of (text, {overrides})."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = wrap
    tf.vertical_anchor = anchor
    for side in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, side, 0)
    paras = runs if isinstance(runs, list) else [runs]
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if line_spacing:
            p.line_spacing = line_spacing
        if spacing is not None and i > 0:
            p.space_before = Pt(spacing)
        pieces = para if isinstance(para, list) else [(para, {})]
        for t, o in pieces:
            r = p.add_run()
            r.text = t
            f = r.font
            f.name = o.get("font", FONT)
            f.size = Pt(o.get("size", size))
            f.bold = o.get("bold", bold)
            f.italic = o.get("italic", italic)
            f.color.rgb = o.get("color", color)
            if o.get("baseline"):
                r._r.get_or_add_rPr().set("baseline", str(o["baseline"]))
            if o.get("tracking"):
                r._r.get_or_add_rPr().set("spc", str(o["tracking"]))
    return tb


def rich(slide, x, y, w, h, paragraphs, size=12, color=TEXT, bold=False, italic=False, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, spacing=None):
    """Text with inline native math. paragraphs: list of lists; item = str | ("$", latex) | (str, {overrides})."""
    from omml import add_inline
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    for side in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, side, 0)
    for i, para in enumerate(paragraphs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if spacing is not None and i > 0:
            p.space_before = Pt(spacing)
        for item in para:
            if isinstance(item, tuple) and item[0] == "$":
                o = item[2] if len(item) > 2 else {}
                add_inline(p, item[1], size_pt=o.get("size", size), color_hex=hexs(o.get("color", color)))
                continue
            t, o = (item, {}) if isinstance(item, str) else item
            r = p.add_run()
            r.text = t
            f = r.font
            f.name = FONT
            f.size = Pt(o.get("size", size))
            f.bold = o.get("bold", bold)
            f.italic = o.get("italic", italic)
            f.color.rgb = o.get("color", color)
    return tb


def equation(slide, x, y, w, h, latex, size=20, color=TEXT, align="left"):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    for side in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, side, 0)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    add_equation(tf.paragraphs[0], latex, size_pt=size, color_hex=hexs(color), align=align)
    return tb


def picture(slide, path, x, y, w=None, h=None):
    kw = {}
    if w is not None:
        kw["width"] = Inches(w)
    if h is not None:
        kw["height"] = Inches(h)
    return slide.shapes.add_picture(str(path), Inches(x), Inches(y), **kw)


def frame(slide):
    rect(slide, 0, 0, SW, SH, fill=WHITE)
    rect(slide, 0, 0, 0.14, SH, fill=INK)
    rect(slide, 0.14, 0, 0.022, SH, fill=AMBER)


def content_slide(prs, eyebrow, title, subtitle=None, number=None):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    frame(s)
    rect(s, L, 6.80, CW, 0.01, fill=HAIR)
    text(s, L, 6.93, 8.85, 0.26, [[(FOOTER, {"tracking": 60})]], size=8.5, color=MUTED)
    if number is not None:
        text(s, 11.20, 6.93, 1.40, 0.26, f"{number:02d}", size=9, color=INK_MID, bold=True, align=PP_ALIGN.RIGHT)
    text(s, L, 0.60, CW, 0.26, [[(eyebrow.upper(), {"tracking": 160})]], size=9, color=AMBER, bold=True)
    if isinstance(title, list):   # paragraph with inline math
        rich(s, L, 0.86, CW, 0.66, [title], size=27, color=INK, bold=True)
    else:
        text(s, L, 0.86, CW, 0.66, title, size=27, color=INK, bold=True)
    rect(s, L, 1.60, 1.05, 0.06, fill=AMBER)
    if isinstance(subtitle, list):
        rich(s, L, 1.74, CW, 0.30, [subtitle], size=11, color=MUTED, italic=True)
    elif subtitle:
        text(s, L, 1.74, CW, 0.30, subtitle, size=11, color=MUTED, italic=True)
    return s


def notes(slide, txt):
    slide.notes_slide.notes_text_frame.text = txt


def accent_bar(slide, x, y, h, color=AMBER, w=0.05):
    return rect(slide, x, y, w, h, fill=color)


def label(slide, x, y, w, txt, color=INK, size=9.5, upper=True):
    return text(slide, x, y, w, 0.22, [[(txt.upper() if upper else txt, {"tracking": 90})]], size=size, color=color, bold=True)


# ------------------------------------------------------------------ native charts
def _font(tf_font, size=10, color=TEXT, bold=False):
    tf_font.size = Pt(size)
    tf_font.name = FONT
    tf_font.bold = bold
    tf_font.color.rgb = color


def _axis_style(ax, title=None, size=10, gridlines=False, number_format=None, line=True):
    ax.has_major_gridlines = gridlines
    if gridlines:
        ax.major_gridlines.format.line.color.rgb = HAIR
        ax.major_gridlines.format.line.width = Pt(0.5)
    ax.tick_labels.font.size = Pt(size)
    ax.tick_labels.font.name = FONT
    ax.tick_labels.font.color.rgb = MUTED
    if number_format:
        ax.tick_labels.number_format = number_format
        ax.tick_labels.number_format_is_linked = False
    if line:
        ax.format.line.color.rgb = GREY
        ax.format.line.width = Pt(0.75)
    else:
        ax.format.line.fill.background()
    if title:
        ax.has_title = True
        ax.axis_title.text_frame.text = title
        _font(ax.axis_title.text_frame.paragraphs[0].runs[0].font, size=size, color=MUTED)
    return ax


def bar_chart(slide, x, y, w, h, categories, series, horizontal=False, labels_fmt='0', legend=True,
              value_max=None, value_min=None, gap=60, overlap=0, label_size=10, cat_size=10, value_axis_visible=False,
              number_format=None, label_texts=None):
    cd = CategoryChartData()
    cd.categories = categories
    for name, values, _ in series:
        cd.add_series(name, values)
    kind = XL_CHART_TYPE.BAR_CLUSTERED if horizontal else XL_CHART_TYPE.COLUMN_CLUSTERED
    gf = slide.shapes.add_chart(kind, Inches(x), Inches(y), Inches(w), Inches(h), cd)
    ch = gf.chart
    ch.has_title = False
    ch.font.name = FONT
    ch.font.size = Pt(10)
    plot = ch.plots[0]
    plot.gap_width = gap
    plot.overlap = overlap
    for s, (_, _, color) in zip(plot.series, series):
        s.format.fill.solid()
        s.format.fill.fore_color.rgb = color
        s.format.line.fill.background()
        s.invert_if_negative = False
    if label_texts:
        # fixed text labels: number formats follow the PC locale (decimal comma here), text does not
        for s, texts in zip(plot.series, label_texts):
            for pt, t in zip(s.points, texts):
                dl = pt.data_label
                dl.position = XL_LABEL_POSITION.OUTSIDE_END
                tf = dl.text_frame
                tf.text = t
                _font(tf.paragraphs[0].runs[0].font, size=label_size, color=TEXT, bold=True)
    elif labels_fmt:
        plot.has_data_labels = True
        dl = plot.data_labels
        dl.number_format = labels_fmt
        dl.number_format_is_linked = False
        dl.position = XL_LABEL_POSITION.OUTSIDE_END
        _font(dl.font, size=label_size, color=TEXT, bold=True)
    va = ch.value_axis
    _axis_style(va, size=9, number_format=number_format)
    if value_max is not None:
        va.maximum_scale = value_max
    if value_min is not None:
        va.minimum_scale = value_min
    if not value_axis_visible:
        va.visible = False
    ca = ch.category_axis
    _axis_style(ca, size=cat_size)
    ca.tick_labels.font.color.rgb = TEXT
    from pptx.enum.chart import XL_TICK_MARK
    ca.major_tick_mark = XL_TICK_MARK.NONE
    ch.has_legend = legend and len(series) > 1
    if ch.has_legend:
        ch.legend.position = XL_LEGEND_POSITION.TOP
        ch.legend.include_in_layout = False
        _font(ch.legend.font, size=10, color=TEXT)
    return ch


def xy_chart(slide, x, y, w, h, series, x_title=None, y_title=None, x_range=None, y_range=None, legend=True,
             size=10, x_fmt="0", y_fmt="0", markers=False, legend_pos=XL_LEGEND_POSITION.TOP):
    """series: list of dicts {name, xs, ys, color, width, dash, marker}."""
    cd = XyChartData()
    for sd in series:
        s = cd.add_series(sd["name"])
        for xv, yv in zip(sd["xs"], sd["ys"]):
            s.add_data_point(xv, yv)
    kind = XL_CHART_TYPE.XY_SCATTER_LINES if markers else XL_CHART_TYPE.XY_SCATTER_LINES_NO_MARKERS
    gf = slide.shapes.add_chart(kind, Inches(x), Inches(y), Inches(w), Inches(h), cd)
    ch = gf.chart
    ch.font.name = FONT
    ch.font.size = Pt(size)
    for s, sd in zip(ch.plots[0].series, series):
        s.smooth = False
        ln = s.format.line
        ln.color.rgb = sd["color"]
        ln.width = Pt(sd.get("width", 2))
        if sd.get("dash"):
            ln.dash_style = sd["dash"]
        if sd.get("marker"):
            s.marker.style = sd["marker"]
            s.marker.size = sd.get("marker_size", 7)
            s.marker.format.fill.solid()
            s.marker.format.fill.fore_color.rgb = sd["color"]
            s.marker.format.line.color.rgb = sd["color"]
        else:
            s.marker.style = None
            from pptx.enum.chart import XL_MARKER_STYLE
            s.marker.style = XL_MARKER_STYLE.NONE
    xa, ya = ch.category_axis, ch.value_axis
    _axis_style(xa, x_title, size=size, number_format=x_fmt)
    _axis_style(ya, y_title, size=size, number_format=y_fmt, gridlines=True)
    xa.tick_label_position = XL_TICK_LABEL_POSITION.LOW
    ya.tick_label_position = XL_TICK_LABEL_POSITION.LOW
    if x_range:
        xa.minimum_scale, xa.maximum_scale = x_range[0], x_range[1]
    if y_range:
        ya.minimum_scale, ya.maximum_scale = y_range[0], y_range[1]
    ch.has_legend = legend
    if legend:
        ch.legend.position = legend_pos
        ch.legend.include_in_layout = False
        _font(ch.legend.font, size=size, color=TEXT)
    return ch


def set_axis_unit(ax, major):
    ax.major_unit = major


# brick for CP; amber for HP; ink-mid for HB (same meaning on every slide)
CP_C, HP_C, HB_C = RGBColor(0xA6, 0x5D, 0x57), AMBER, INK_MID
CP_T, HP_T, HB_T = RGBColor(0xD9, 0xB3, 0xAF), RGBColor(0xE4, 0xC8, 0xA7), RGBColor(0xA9, 0xBA, 0xC6)
PALE_GREEN = RGBColor(0xDD, 0xEE, 0xE5)


def plot_layout(chart, x, y, w, h):
    """Fix the inner plot area (fractions of the chart frame) so charts align and polygons can be square."""
    from lxml import etree
    from pptx.oxml.ns import qn
    pa = chart._chartSpace.find(qn("c:chart")).find(qn("c:plotArea"))
    old = pa.find(qn("c:layout"))
    if old is not None:
        pa.remove(old)
    lay = etree.SubElement(pa, qn("c:layout"))
    pa.remove(lay)
    pa.insert(0, lay)
    ml = etree.SubElement(lay, qn("c:manualLayout"))
    for tag, val in (("c:layoutTarget", "inner"), ("c:xMode", "edge"), ("c:yMode", "edge"),
                     ("c:x", x), ("c:y", y), ("c:w", w), ("c:h", h)):
        etree.SubElement(ml, qn(tag), val=str(val))


def plot_to_slide(frame, layout, xr, yr, xv, yv):
    """Slide coordinates (in) of a data point, for a chart frame (x, y, w, h) with a manual inner layout."""
    fx, fy, fw, fh = frame
    lx, ly, lw, lh = layout
    px = fx + fw * (lx + lw * (xv - xr[0]) / (xr[1] - xr[0]))
    py = fy + fh * (ly + lh * (1 - (yv - yr[0]) / (yr[1] - yr[0])))
    return px, py
