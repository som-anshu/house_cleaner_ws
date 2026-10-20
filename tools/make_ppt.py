#!/usr/bin/env python3
"""Build a simple, non-technical slide deck explaining the house cleaner robot.

Run with the conda python (python-pptx lives there, not in the ROS system
interpreter):

    ~/anaconda3/bin/python tools/make_ppt.py

Output: docs/House_Cleaner_Robot.pptx
"""
import os

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

# ---------------------------------------------------------------- palette
NAVY = RGBColor(0x14, 0x2B, 0x50)
BLUE = RGBColor(0x1F, 0x6F, 0xB2)
LINE = RGBColor(0x0E, 0x1E, 0x38)
GREEN = RGBColor(0x17, 0x8F, 0x54)
ORANGE = RGBColor(0xE0, 0x7B, 0x1B)
RED = RGBColor(0xC0, 0x39, 0x2B)
GREY = RGBColor(0x5A, 0x64, 0x72)
LIGHT = RGBColor(0xF2, 0xF5, 0xF9)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
CREAM = RGBColor(0xFF, 0xF4, 0xE0)

SW = Inches(13.333)
SH = Inches(7.5)

prs = Presentation()
prs.slide_width = SW
prs.slide_height = SH
BLANK = prs.slide_layouts[6]

TOTAL = 16
_n = {"i": 0}


# ---------------------------------------------------------------- helpers
def blank():
    return prs.slides.add_slide(BLANK)


def box(slide, x, y, w, h, fill=None, line=None, lw=1.25,
        shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.12):
    sh = slide.shapes.add_shape(shape, x, y, w, h)
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        try:
            sh.adjustments[0] = radius
        except (IndexError, KeyError):
            pass
    if fill is None:
        sh.fill.background()
    else:
        sh.fill.solid()
        sh.fill.fore_color.rgb = fill
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = line
        sh.line.width = Pt(lw)
    sh.shadow.inherit = False
    return sh


def text(slide, x, y, w, h, runs, size=18, color=NAVY, bold=False,
         align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE, spacing=1.0,
         italic=False, font="Calibri"):
    """runs: str | list[(str, dict)] where dict may set size/color/bold."""
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Emu(0)
    tf.margin_top = tf.margin_bottom = Emu(0)

    if isinstance(runs, str):
        runs = [(runs, {})]

    first = True
    for item in runs:
        if isinstance(item, str):
            item = (item, {})
        s, opt = item
        para = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        para.alignment = opt.get("align", align)
        para.line_spacing = opt.get("spacing", spacing)
        if opt.get("space_before"):
            para.space_before = Pt(opt["space_before"])
        run = para.add_run()
        run.text = s
        f = run.font
        f.size = Pt(opt.get("size", size))
        f.bold = opt.get("bold", bold)
        f.italic = opt.get("italic", italic)
        f.name = opt.get("font", font)
        f.color.rgb = opt.get("color", color)
    return tb


def slide_base(title, num, kicker=None):
    s = blank()
    box(s, Emu(0), Emu(0), SW, Inches(0.10), fill=BLUE, shape=MSO_SHAPE.RECTANGLE)
    text(s, Inches(0.62), Inches(0.30), Inches(10.6), Inches(0.62),
         title, size=30, color=NAVY, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    if kicker:
        text(s, Inches(0.64), Inches(0.92), Inches(11.5), Inches(0.36),
             kicker, size=14, color=GREY, italic=True)
    text(s, Inches(12.25), Inches(6.92), Inches(0.85), Inches(0.3),
         f"{num}/{TOTAL}", size=11, color=GREY, align=PP_ALIGN.RIGHT)
    return s


def bubble(slide, x, y, d, n, label, sub=None, color=BLUE, tsize=20):
    box(slide, x, y, d, d, fill=color, shape=MSO_SHAPE.OVAL)
    text(slide, x, y, d, d, str(n), size=30, color=WHITE, bold=True,
         align=PP_ALIGN.CENTER)
    if label:
        text(slide, x - Inches(0.35), y + d + Inches(0.06), d + Inches(0.70),
             Inches(0.5), label, size=tsize, color=NAVY, bold=True,
             align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.TOP)
    if sub:
        text(slide, x - Inches(0.35), y + d + Inches(0.48), d + Inches(0.70),
             Inches(0.62), sub, size=12, color=GREY,
             align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.TOP)


def arrow(slide, x, y, w, h, color=BLUE):
    sh = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, x, y, w, h)
    sh.fill.solid()
    sh.fill.fore_color.rgb = color
    sh.line.fill.background()
    sh.shadow.inherit = False
    return sh


def down_arrow(slide, x, y, w, h, color=BLUE):
    sh = slide.shapes.add_shape(MSO_SHAPE.DOWN_ARROW, x, y, w, h)
    sh.fill.solid()
    sh.fill.fore_color.rgb = color
    sh.line.fill.background()
    sh.shadow.inherit = False
    return sh


def card(slide, x, y, w, h, n, title, body, accent=BLUE, tsize=17, bsize=13):
    box(slide, x, y, w, h, fill=WHITE, line=RGBColor(0xD3, 0xDC, 0xE8))
    box(slide, x, y, Inches(0.075), h, fill=accent, shape=MSO_SHAPE.RECTANGLE)
    text(slide, x + Inches(0.26), y + Inches(0.16), w - Inches(0.5),
         Inches(0.4), f"{n}.  {title}" if n else title,
         size=tsize, color=accent, bold=True, anchor=MSO_ANCHOR.TOP)
    text(slide, x + Inches(0.26), y + Inches(0.72), w - Inches(0.5),
         h - Inches(0.86), body, size=bsize, color=RGBColor(0x33, 0x3D, 0x49),
         anchor=MSO_ANCHOR.TOP, spacing=1.05)


def footer(slide, msg, color=LIGHT, tcolor=NAVY):
    # Stops at 12.10 in so it never collides with the page-number box (12.25+).
    box(slide, Inches(0.62), Inches(6.42), Inches(11.48), Inches(0.62),
        fill=color, line=None)
    text(slide, Inches(0.86), Inches(6.42), Inches(11.0), Inches(0.62),
         msg, size=13.5, color=tcolor, bold=True)


# ================================================================ 1 TITLE
s = blank()
box(s, Emu(0), Emu(0), SW, Inches(2.55), fill=NAVY, shape=MSO_SHAPE.RECTANGLE)
box(s, Emu(0), Inches(2.55), SW, Inches(0.09), fill=BLUE, shape=MSO_SHAPE.RECTANGLE)
text(s, Inches(0.9), Inches(0.72), Inches(11.5), Inches(0.9),
     "House Cleaner Robot", size=48, color=WHITE, bold=True)
text(s, Inches(0.9), Inches(1.66), Inches(11.5), Inches(0.6),
     "A small robot that cleans a room all by itself",
     size=22, color=RGBColor(0xBF, 0xD4, 0xEE))
text(s, Inches(0.9), Inches(3.05), Inches(11.5), Inches(0.5),
     "What it does, how it thinks, and how it never gets stuck",
     size=20, color=GREY, italic=True)

# the five-step story, as a visual strip
steps = [("Build a map\nof the room"), ("Clean every\npart in strips"),
         ("Battery gets\nlow — it knows"), ("Parks & charges\nat its dock"),
         ("Goes back\nto work again")]
# 5 cards + 4 arrows inside x = 0.95 .. 12.35 (11.40 in of usable width)
cw = Inches(2.02)
aw = Inches(0.30)
x = Inches(0.95)
for i, lab in enumerate(steps):
    box(s, x, Inches(3.95), cw, Inches(1.55), fill=LIGHT,
        line=RGBColor(0xC5, 0xD2, 0xE2))
    text(s, x + Inches(0.10), Inches(4.02), cw - Inches(0.20), Inches(1.41),
         lab, size=14, color=BLUE, bold=True,
         align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, spacing=1.1)
    if i < len(steps) - 1:
        arrow(s, x + cw + Inches(0.035), Inches(4.60), Inches(0.23),
              Inches(0.26), color=RGBColor(0x9F, 0xB4, 0xCC))
    x += cw + aw

footer(s, "In one line: it maps the room, cleans it in neat strips, and "
          "recharges itself when tired — no human needed.")
prs.slides[-1].notes_slide.notes_text_frame.text = (
    "Opening line: this is a robot that vacuums a room on its own. "
    "Five simple steps. Everything else in this deck explains those five steps."
)

# ================================================================ 2 WHAT
s = slide_base("What is this project?", 2,
               "The plain-English version")
box(s, Inches(0.62), Inches(1.42), Inches(12.1), Inches(1.15),
    fill=CREAM, line=RGBColor(0xF0, 0xD2, 0x9A))
text(s, Inches(1.0), Inches(1.42), Inches(11.4), Inches(1.15),
     "A robot vacuum that works in a computer, so we can test it safely "
     "before buying hardware.", size=19, color=RGBColor(0x8A, 0x54, 0x0A),
     bold=True, anchor=MSO_ANCHOR.MIDDLE)

items = [
    ("Real robot, virtual room", "It is a TurtleBot3 Burger robot driving "
     "inside a pretend house made in a physics simulator."),
    ("No map, no problem", "It starts knowing nothing about the room and "
     "builds the map as it drives around."),
    ("It charges itself", "When the battery runs low it drives back to its "
     "dock, charges up, and gets back to work."),
    ("Built to never get stuck", "Three layers of 'babysitters' watch it and "
     "fix problems automatically."),
]
x = Inches(0.62)
for i, (t, b) in enumerate(items):
    card(s, x, Inches(2.85), Inches(2.92), Inches(3.25), i + 1, t, b,
         accent=[BLUE, GREEN, ORANGE, RED][i], tsize=15, bsize=12)
    x += Inches(3.07)

text(s, Inches(0.62), Inches(6.28), Inches(12.1), Inches(0.4),
     "You can watch all of it live: the 3D room window, a dashboard view, "
     "and a web page in your browser.", size=14, color=GREY, italic=True)
prs.slides[-1].notes_slide.notes_text_frame.text = (
    "Emphasise the 'why': simulation lets us try dangerous things — running "
    "the battery to zero, blocking the dock — without breaking a real robot."
)

# ================================================================ 3 STORY
s = slide_base("The robot's day, in 5 steps", 3,
               "The whole mission is one simple loop")
names = ["Map", "Clean", "Tired", "Charge", "Resume"]
subs = ["learn the room", "neat strips", "battery low", "at the dock",
        "and repeat"]
colors = [BLUE, GREEN, ORANGE, ORANGE, BLUE]
w = Inches(2.05)
gap = Inches(0.42)
x = Inches(0.75)
for i in range(5):
    bubble(s, x, Inches(1.75), Inches(1.15), i + 1, names[i], subs[i],
           color=colors[i], tsize=19)
    if i < 4:
        arrow(s, x + Inches(1.15) + Inches(0.04), Inches(2.18),
              gap - Inches(0.08), Inches(0.30),
              color=RGBColor(0x9F, 0xB4, 0xCC))
    x += Inches(1.15) + gap

box(s, Inches(0.62), Inches(4.15), Inches(12.1), Inches(0.05),
    fill=RGBColor(0xD3, 0xDC, 0xE8), shape=MSO_SHAPE.RECTANGLE)
text(s, Inches(0.62), Inches(4.32), Inches(12.1), Inches(0.45),
     "…then step 5 loops straight back to step 2, so it cleans pass after pass.",
     size=15, color=GREY, italic=True, align=PP_ALIGN.CENTER)

rows = [
    ("How it decides", "It checks its battery level constantly. Below 40% "
     "it stops cleaning and heads home."),
    ("How it gets home", "It remembers where the dock is and drives to a spot "
     "just in front of it."),
    ("What 'done' means", "Battery back to 95% \u2192 it reverses out and "
     "carries on exactly where it left off."),
]
y = Inches(5.00)
for t, b in rows:
    box(s, Inches(0.62), y, Inches(12.1), Inches(0.44), fill=LIGHT)
    text(s, Inches(0.88), y, Inches(3.0), Inches(0.44), t, size=14,
         color=BLUE, bold=True)
    text(s, Inches(4.0), y, Inches(8.5), Inches(0.44), b, size=13,
         color=RGBColor(0x33, 0x3D, 0x49))
    y += Inches(0.52)
prs.slides[-1].notes_slide.notes_text_frame.text = (
    "This is the single most important slide. If the audience remembers one "
    "picture, it should be this loop."
)

# ================================================================ 4 MAP
s = slide_base("Step 1 — It learns the room by driving", 4,
               "Like feeling your way around a dark room with a torch")
# sketch: room + dock + robot + laser fan
room_x, room_y, room_w, room_h = Inches(1.15), Inches(1.55), Inches(5.1), Inches(4.3)
box(s, room_x, room_y, room_w, room_h, fill=WHITE,
    line=NAVY, lw=2.0, shape=MSO_SHAPE.RECTANGLE)
# furniture
box(s, room_x + Inches(2.55), room_y + Inches(0.55), Inches(2.05), Inches(0.85),
    fill=RGBColor(0xDD, 0xE3, 0xEC), line=GREY, shape=MSO_SHAPE.RECTANGLE)
text(s, room_x + Inches(2.55), room_y + Inches(0.55), Inches(2.05), Inches(0.85),
     "sofa", size=11, color=GREY, align=PP_ALIGN.CENTER)
box(s, room_x + Inches(0.85), room_y + Inches(2.05), Inches(1.1), Inches(0.75),
    fill=RGBColor(0xDD, 0xE3, 0xEC), line=GREY, shape=MSO_SHAPE.RECTANGLE)
text(s, room_x + Inches(0.85), room_y + Inches(2.05), Inches(1.1), Inches(0.75),
     "table", size=11, color=GREY, align=PP_ALIGN.CENTER)
box(s, room_x + Inches(3.7), room_y + Inches(3.15), Inches(0.85), Inches(0.75),
    fill=RGBColor(0xDD, 0xE3, 0xEC), line=GREY, shape=MSO_SHAPE.RECTANGLE)
text(s, room_x + Inches(3.7), room_y + Inches(3.15), Inches(0.85), Inches(0.75),
     "crates", size=11, color=GREY, align=PP_ALIGN.CENTER)
# dock
box(s, room_x + Inches(1.95), room_y + Inches(-0.02), Inches(1.2), Inches(0.34),
    fill=GREEN, shape=MSO_SHAPE.RECTANGLE)
text(s, room_x + Inches(1.95), room_y + Inches(-0.36), Inches(1.2), Inches(0.34),
     "charging dock", size=11, color=GREEN, bold=True, align=PP_ALIGN.CENTER)
# robot + laser fan
rx, ry = room_x + Inches(2.35), room_y + Inches(3.35)
box(s, rx, ry, Inches(0.42), Inches(0.42), fill=BLUE, shape=MSO_SHAPE.OVAL)
for ang, ln in ((-42, 1.25), (-14, 1.65), (14, 1.65), (42, 1.25)):
    import math
    a = math.radians(90 + ang)
    sh = slide_x = s.shapes.add_shape(
        MSO_SHAPE.ISOSCELES_TRIANGLE if False else MSO_SHAPE.OVAL,
        Emu(int(rx + Inches(0.21) + Inches(ln) * math.cos(a) - Inches(0.05))),
        Emu(int(ry + Inches(0.21) + Inches(ln) * math.sin(a) - Inches(0.05))),
        Inches(0.10), Inches(0.10))
    sh.fill.solid()
    sh.fill.fore_color.rgb = RGBColor(0x8F, 0xC2, 0xE8)
    sh.line.fill.background()
    sh.shadow.inherit = False
text(s, rx - Inches(0.55), ry - Inches(0.52), Inches(1.6), Inches(0.4),
     "robot's laser", size=11, color=BLUE, bold=True)

facts = [
    ("Spinning laser", "The robot has a laser that measures distance to "
     "everything around it, 360 degrees."),
    ("Map grows as it drives", "Every new reading is stitched onto the map. "
     "Unknown areas fill in over time."),
    ("It knows where it is", "By comparing readings to the map it always "
     "knows its own position."),
]
y = Inches(1.62)
for i, (t, b) in enumerate(facts):
    card(s, Inches(6.75), y, Inches(5.97), Inches(1.32), i + 1, t, b,
         accent=BLUE, tsize=15, bsize=12.5)
    y += Inches(1.48)
prs.slides[-1].notes_slide.notes_text_frame.text = (
    "Analogy: walking through your own living room in the dark with a "
    "flashlight. The map is the picture you build in your head."
)

# ================================================================ 5 PLAN
s = slide_base("Step 2 — It plans a 'lawnmower' route", 5,
               "The trick that guarantees no spot is missed")
box(s, Inches(0.62), Inches(1.45), Inches(6.9), Inches(4.6), fill=LIGHT,
    line=RGBColor(0xC5, 0xD2, 0xE2))
text(s, Inches(0.62), Inches(1.52), Inches(6.9), Inches(0.35),
     "one goal at the end of each strip", size=12, color=GREY,
     align=PP_ALIGN.CENTER, italic=True)
px, py, pw, ph = Inches(0.95), Inches(2.05), Inches(6.2), Inches(3.7)
box(s, px, py, pw, ph, fill=WHITE, line=NAVY, lw=2, shape=MSO_SHAPE.RECTANGLE)
rows_, step = 7, ph / Inches(7.0)
# the sweeping line
pts = []
for r in range(rows_):
    yy = py + Emu(int(step * (r + 0.5)))
    if r % 2 == 0:
        pts.append((px + Inches(0.15), yy))
        pts.append((px + pw - Inches(0.15), yy))
    else:
        pts.append((px + pw - Inches(0.15), yy))
        pts.append((px + Inches(0.15), yy))
# connect rows vertically at the ends
path = []
for r in range(rows_):
    yy = py + Emu(int(step * (r + 0.5)))
    xr = px + (Inches(0.15) if r % 2 == 0 else pw - Inches(0.15))
    xl = px + (pw - Inches(0.15) if r % 2 == 0 else Inches(0.15))
    path.append((xr, yy, xl, yy))
from pptx.util import Emu as E
for r, (x1, y1, x2, y2) in enumerate(path):
    if r % 2 == 0:
        a, b = (x1, y1), (x2, y2)
    else:
        a, b = (x1, y1), (x2, y2)
    sh = s.shapes.add_shape(MSO_SHAPE.LEFT_RIGHT_ARROW, a[0], a[1] - Inches(0.035),
                            b[0] - a[0], Inches(0.07))
    sh.fill.solid()
    sh.fill.fore_color.rgb = BLUE
    sh.line.fill.background()
    sh.shadow.inherit = False
    cx = b[0] - Inches(0.30) if r % 2 == 0 else a[0] + Inches(0.12)
    cy = a[1] + step * 0.28 if r % 2 == 0 else a[1] - step * 0.42
    box(s, cx, cy, Inches(0.19), Inches(0.19), fill=GREEN, shape=MSO_SHAPE.OVAL)

text(s, Inches(0.62), Inches(5.72), Inches(6.9), Inches(0.4),
     "green dots = the 'go there' points the robot is given",
     size=12, color=GREEN, align=PP_ALIGN.CENTER, bold=True)

acts = [
    ("Cover in strips", "Parallel rows 45 cm apart. The robot fills each "
     "strip, like mowing a lawn."),
    ("Alternate direction", "It turns around at the end of every second "
     "strip — no wasted 180° spins."),
    ("Check before going", "Just before driving to a point, it re-checks the "
     "latest map. Blocked? It slides 2 m sideways."),
    ("Skip the furniture", "Known furniture is simply banned as a "
     "destination — the robot never aims at the sofa."),
]
y = Inches(1.62)
for i, (t, b) in enumerate(acts):
    card(s, Inches(7.72), y, Inches(5.0), Inches(1.10), i + 1, t, b,
         accent=GREEN, tsize=14, bsize=11.5)
    y += Inches(1.20)
prs.slides[-1].notes_slide.notes_text_frame.text = (
    "Emphasise 'lawnmower' — everyone understands mowing a lawn. "
    "45 cm strips fit the robot's cleaning width."
)

# ================================================================ 6 DRIVE
s = slide_base("Step 2b — How it actually drives there", 6,
               "Two brains: one for the big picture, one for the steering wheel")
box(s, Inches(0.62), Inches(1.45), Inches(5.9), Inches(2.05), fill=WHITE,
    line=RGBColor(0xD3, 0xDC, 0xE8))
box(s, Inches(0.62), Inches(1.45), Inches(0.075), Inches(2.05), fill=BLUE,
    shape=MSO_SHAPE.RECTANGLE)
text(s, Inches(0.95), Inches(1.62), Inches(5.4), Inches(0.4),
     "Brain 1 — the navigator", size=18, color=BLUE, bold=True)
text(s, Inches(0.95), Inches(2.10), Inches(5.4), Inches(1.25),
     "Works out the shortest sensible path from here to the next green dot, "
     "going around walls and furniture. Re-plans if something new appears.",
     size=13.5, color=RGBColor(0x33, 0x3D, 0x49))

box(s, Inches(6.82), Inches(1.45), Inches(5.9), Inches(2.05), fill=WHITE,
    line=RGBColor(0xD3, 0xDC, 0xE8))
box(s, Inches(6.82), Inches(1.45), Inches(0.075), Inches(2.05), fill=GREEN,
    shape=MSO_SHAPE.RECTANGLE)
text(s, Inches(7.15), Inches(1.62), Inches(5.4), Inches(0.4),
     "Brain 2 — the driver", size=18, color=GREEN, bold=True)
text(s, Inches(7.15), Inches(2.10), Inches(5.4), Inches(1.25),
     "At 20 times a second it imagines 600 possible ways to move in the next "
     "3 seconds, picks the safest one, and applies the wheel and pedals "
     "gently.", size=13.5, color=RGBColor(0x33, 0x3D, 0x49))

text(s, Inches(0.62), Inches(3.72), Inches(12.1), Inches(0.4),
     "Every command then passes through the same safety gate:",
     size=15, color=NAVY, bold=True)

chain = ["Navigator\npicks path", "Driver\nsteers", "Smoothing\n(no jerks)",
         "Safety gate\n(slow near walls)", "Robot\nmoves"]
x = Inches(0.70)
cw = Inches(2.28)
for i, c in enumerate(chain):
    col = BLUE if i < 2 else (ORANGE if i == 3 else GREEN)
    box(s, x, Inches(4.30), cw, Inches(0.95), fill=LIGHT, line=col, lw=1.5)
    text(s, x + Inches(0.08), Inches(4.30), cw - Inches(0.16), Inches(0.95),
         c.replace("\n", " "), size=13, color=col, bold=True,
         align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    if i < len(chain) - 1:
        arrow(s, x + cw + Inches(0.02), Inches(4.66), Inches(0.22),
              Inches(0.24), color=RGBColor(0x9F, 0xB4, 0xCC))
    x += cw + Inches(0.28)

footer(s, "If any single link in that chain goes quiet, the robot notices "
          "within seconds and fixes it instead of sitting there.")
prs.slides[-1].notes_slide.notes_text_frame.text = (
    "Avoid jargon: 'navigator' vs 'driver' is the clearest way to explain "
    "global planner vs local controller."
)

# ================================================================ 7 BATTERY
s = slide_base("Step 3 — It notices it is tired", 7,
               "A simulated fuel gauge the robot checks constantly")
# battery bar
box(s, Inches(0.85), Inches(1.75), Inches(11.6), Inches(0.95),
    fill=RGBColor(0xE6, 0xEB, 0xF2), line=GREY, lw=1.5)
box(s, Inches(0.95), Inches(1.85), Inches(5.6), Inches(0.75), fill=GREEN)
box(s, Inches(6.55), Inches(1.85), Inches(2.3), Inches(0.75), fill=ORANGE)
box(s, Inches(8.85), Inches(1.85), Inches(3.5), Inches(0.75), fill=RED)
text(s, Inches(0.95), Inches(1.85), Inches(5.6), Inches(0.75),
     "100% \u2192 40%   keep cleaning", size=14, color=WHITE, bold=True,
     align=PP_ALIGN.CENTER)
text(s, Inches(6.55), Inches(1.85), Inches(2.3), Inches(0.75),
     "40%", size=14, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
text(s, Inches(8.85), Inches(1.85), Inches(3.5), Inches(0.75),
     "go home \u2192 1% = emergency stop", size=13, color=WHITE, bold=True,
     align=PP_ALIGN.CENTER)

facts = [
    ("It drains for real", "The battery empties a little every second the "
     "robot is driving — faster if you speed the demo up."),
    ("It is checked 2× per second", "A dedicated little program publishes the "
     "battery level on a topic everyone can read."),
    ("40% = time to go home", "Crossing 40% cancels whatever chore it is "
     "doing and sends it to the dock."),
    ("1% = stop everything", "Below 1% it refuses to start new work, so it "
     "can never die in the middle of the room."),
]
x = Inches(0.62)
for i, (t, b) in enumerate(facts):
    card(s, x, Inches(3.20), Inches(2.92), Inches(2.55), 0, t, b,
         accent=[GREEN, BLUE, ORANGE, RED][i], tsize=14, bsize=12)
    x += Inches(3.07)
footer(s, "For demos you can speed the battery up, so a whole clean-and-charge "
          "cycle takes minutes instead of hours.")
prs.slides[-1].notes_slide.notes_text_frame.text = (
    "The battery bar is a good place to pause: 40% trigger, 95% resume, "
    "1% hard stop. These three numbers explain the whole energy strategy."
)

# ================================================================ 8 DOCK
s = slide_base("Step 4 — It parks and charges itself", 8,
               "The hardest centimetres: the last 15 cm into the dock")
steps = [
    ("Drive home", "Follows the map to a spot about a metre in front of the "
     "dock.", BLUE),
    ("Line up", "Turns to face the dock squarely.", BLUE),
    ("Creep in slowly", "Slows to 4 cm per second using only its front laser "
     "as eyes.", ORANGE),
    ("Touch & confirm", "When the wall of the dock is 13 cm away it considers "
     "itself parked.", GREEN),
    ("Charge", "Tells the dock to start charging, then waits quietly for 95%.",
     GREEN),
    ("Reverse out", "Backs up 48 cm, proves it really moved, and resumes "
     "cleaning.", BLUE),
]
x = Inches(0.62)
for i, (t, b, c) in enumerate(steps):
    box(s, x, Inches(1.55), Inches(1.90), Inches(2.75), fill=WHITE,
        line=RGBColor(0xD3, 0xDC, 0xE8))
    box(s, x, Inches(1.55), Inches(1.90), Inches(0.10), fill=c,
        shape=MSO_SHAPE.RECTANGLE)
    box(s, x + Inches(0.72), Inches(1.80), Inches(0.46), Inches(0.46),
        fill=c, shape=MSO_SHAPE.OVAL)
    text(s, x + Inches(0.72), Inches(1.80), Inches(0.46), Inches(0.46),
         str(i + 1), size=14, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
    text(s, x + Inches(0.14), Inches(2.40), Inches(1.62), Inches(0.55),
         t, size=14, color=c, bold=True, align=PP_ALIGN.CENTER,
         anchor=MSO_ANCHOR.TOP)
    text(s, x + Inches(0.14), Inches(2.95), Inches(1.62), Inches(1.25),
         b, size=11, color=RGBColor(0x33, 0x3D, 0x49),
         align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.TOP)
    if i < len(steps) - 1:
        arrow(s, x + Inches(1.90) + Inches(0.01), Inches(2.80), Inches(0.16),
              Inches(0.20), color=RGBColor(0xA9, 0xBA, 0xCE))
    x += Inches(2.07)

box(s, Inches(0.62), Inches(4.62), Inches(12.1), Inches(1.05), fill=CREAM,
    line=RGBColor(0xF0, 0xD2, 0x9A))
text(s, Inches(0.95), Inches(4.62), Inches(11.45), Inches(1.05),
     "Why it is tricky: the map is a little fuzzy, so it might stop 28 cm "
     "short of the dock. The robot therefore uses the laser for the final "
     "approach, and tries up to five slightly different parking spots before "
     "giving up.", size=14, color=RGBColor(0x8A, 0x54, 0x0A),
     anchor=MSO_ANCHOR.MIDDLE)

footer(s, "It never pretends to be docked: if it did not move when asked, it "
          "says so and the battery will not claim to be charging.")
prs.slides[-1].notes_slide.notes_text_frame.text = (
    "The dock is where most robotics demos fail. This slide shows the "
    "sequence and the safety principle: verify, never assume."
)

# ================================================================ 9 WATCHDOGS
s = slide_base("Step 5 — Why it never gets stuck", 9,
               "Three layers of babysitters, from inside the robot to the host PC")
layers = [
    ("Layer 1 — inside the robot", "A watchdog timer checks the battery "
     "twice a second and cancels the current chore the moment it gets low.",
     BLUE),
    ("Layer 2 — the robot's instinct", "It measures its own movement. If it "
     "is told to drive but nothing happens for 15 seconds, it gives up on "
     "that spot and moves on.", GREEN),
    ("Layer 3 — the computer watching", "A separate program on the host reads "
     "the logs. If the robot is silent, stuck or repeating the same failure, "
     "it restarts the affected parts — and the whole simulation if needed.",
     ORANGE),
]
y = Inches(1.55)
for i, (t, b, c) in enumerate(layers):
    box(s, Inches(0.62), y, Inches(12.1), Inches(1.30), fill=WHITE,
        line=RGBColor(0xD3, 0xDC, 0xE8))
    box(s, Inches(0.62), y, Inches(0.085), Inches(1.30), fill=c,
        shape=MSO_SHAPE.RECTANGLE)
    box(s, Inches(0.90), y + Inches(0.35), Inches(0.62), Inches(0.62),
        fill=c, shape=MSO_SHAPE.OVAL)
    text(s, Inches(0.90), y + Inches(0.35), Inches(0.62), Inches(0.62),
         str(i + 1), size=18, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
    text(s, Inches(1.75), y + Inches(0.14), Inches(4.0), Inches(1.0),
         t, size=16, color=c, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    text(s, Inches(5.9), y + Inches(0.14), Inches(6.6), Inches(1.0),
         b, size=13, color=RGBColor(0x33, 0x3D, 0x49),
         anchor=MSO_ANCHOR.MIDDLE)

box(s, Inches(0.62), Inches(5.72), Inches(12.1), Inches(0.62), fill=NAVY)
text(s, Inches(0.95), Inches(5.72), Inches(11.45), Inches(0.62),
     "Result: the robot skips one bad spot and carries on. It does not freeze, "
     "and it does not restart the whole simulation.", size=14, color=WHITE,
     bold=True, anchor=MSO_ANCHOR.MIDDLE)
prs.slides[-1].notes_slide.notes_text_frame.text = (
    "The key insight: recovery is layered. Small problems are fixed locally "
    "in seconds; only a real crash escalates to a full restart."
)

# ================================================================ 10 STACK
s = slide_base("What the robot is made of", 10,
               "Four groups of programs, each with one plain job")
groups = [
    ("Eyes & ears", "Laser, wheel sensors, camera-less mapping. 'What is "
     "around me?'", BLUE, ["Gazebo simulator", "Laser scan", "Live map (SLAM)"]),
    ("The driver", "Path planning, steering, obstacle avoidance, smooth "
     "accelerations.", GREEN, ["Navigator", "Driver (MPPI)", "Safety gate"]),
    ("The brain", "The to-do list: clean \u2192 park \u2192 charge \u2192 "
     "resume, plus all the checks.", ORANGE,
     ["Mission supervisor", "Battery model", "Docking controller"]),
    ("Watching it", "Windows and web pages so a human can see what is going "
     "on.", RED, ["3D room window", "Dashboard", "Log files"]),
]
x = Inches(0.62)
for t, b, c, items in groups:
    box(s, x, Inches(1.55), Inches(2.92), Inches(4.35), fill=WHITE,
        line=RGBColor(0xD3, 0xDC, 0xE8))
    box(s, x, Inches(1.55), Inches(2.92), Inches(0.10), fill=c,
        shape=MSO_SHAPE.RECTANGLE)
    text(s, x + Inches(0.20), Inches(1.80), Inches(2.52), Inches(0.45),
         t, size=17, color=c, bold=True)
    text(s, x + Inches(0.20), Inches(2.30), Inches(2.52), Inches(1.05),
         b, size=12, color=RGBColor(0x33, 0x3D, 0x49),
         anchor=MSO_ANCHOR.TOP)
    iy = Inches(3.45)
    for it in items:
        box(s, x + Inches(0.20), iy, Inches(2.52), Inches(0.52), fill=LIGHT)
        text(s, x + Inches(0.30), iy, Inches(2.32), Inches(0.52), it,
             size=11.5, color=NAVY, bold=True, anchor=MSO_ANCHOR.MIDDLE)
        iy += Inches(0.62)
    x += Inches(3.07)
footer(s, "Everything talks over 'ROS 2' — think of it as a postal service "
          "inside the robot that delivers messages between programs.")
prs.slides[-1].notes_slide.notes_text_frame.text = (
    "Analogy for ROS 2: a postal service. Each program posts messages to a "
    "mailbox and others subscribe to it. No program is wired directly to "
    "another."
)

# ================================================================ 11 NUMBERS
s = slide_base("Nice numbers to remember", 11,
               "The tuning that makes it work in practice")
data = [
    ("45 cm", "Cleaning strip width — how far apart the mowing lines are", BLUE),
    ("40 %", "Battery level that sends the robot home", ORANGE),
    ("95 %", "Battery level at which it goes back to work", GREEN),
    ("13 cm", "Distance to the dock that counts as 'parked'", GREEN),
    ("30 cm", "How close counts as 'arrived' — because maps are fuzzy", BLUE),
    ("15 s", "Silence that means 'stuck here', then it skips that spot", RED),
    ("3", "Babysitter layers watching for trouble", RED),
]
y = Inches(1.60)
for i, (n, d, c) in enumerate(data):
    box(s, Inches(0.62), y, Inches(12.1), Inches(0.60), fill=LIGHT)
    box(s, Inches(0.62), y, Inches(0.075), Inches(0.60), fill=c,
        shape=MSO_SHAPE.RECTANGLE)
    text(s, Inches(0.95), y, Inches(1.75), Inches(0.60), n, size=19,
         color=c, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    text(s, Inches(2.85), y, Inches(9.6), Inches(0.60), d, size=13.5,
         color=RGBColor(0x33, 0x3D, 0x49), anchor=MSO_ANCHOR.MIDDLE)
    y += Inches(0.68)
prs.slides[-1].notes_slide.notes_text_frame.text = (
    "These are the numbers an audience usually asks about. Each one came from "
    "a real failure that was measured and fixed."
)

# ================================================================ 12 HOW TO RUN
s = slide_base("How to run it (one command)", 12,
               "No expertise needed — the script cleans up and checks itself")
box(s, Inches(0.62), Inches(1.50), Inches(12.1), Inches(0.95), fill=LINE)
text(s, Inches(0.95), Inches(1.50), Inches(11.45), Inches(0.95),
     "./run_all.sh", size=26, color=RGBColor(0x8F, 0xE3, 0xB0),
     bold=True, font="Consolas", anchor=MSO_ANCHOR.MIDDLE)

what = [
    ("1.  Cleans up", "Closes anything left over from a previous run, so you "
     "never get two robots fighting."),
    ("2.  Starts everything", "The room, the robot, the dashboard, the web "
     "view, the battery model and the babysitters."),
    ("3.  Checks itself", "Runs eight health checks and prints a tidy list. "
     "Look for eight green OK lines."),
]
y = Inches(2.70)
for t, b in what:
    box(s, Inches(0.62), y, Inches(12.1), Inches(1.05), fill=WHITE,
        line=RGBColor(0xD3, 0xDC, 0xE8))
    text(s, Inches(0.95), y, Inches(2.6), Inches(1.05), t, size=16,
         color=BLUE, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    text(s, Inches(3.75), y, Inches(8.75), Inches(1.05), b, size=13.5,
         color=RGBColor(0x33, 0x3D, 0x49), anchor=MSO_ANCHOR.MIDDLE)
    y += Inches(1.17)

box(s, Inches(0.62), Inches(6.28), Inches(12.1), Inches(0.05),
    fill=RGBColor(0xD3, 0xDC, 0xE8), shape=MSO_SHAPE.RECTANGLE)
text(s, Inches(0.62), Inches(6.42), Inches(12.1), Inches(0.4),
     "Stop it with:  ./run_all.sh --stop        Check it again with:  "
     "./run_all.sh --verify",
     size=13, color=GREY, italic=True, align=PP_ALIGN.CENTER)
prs.slides[-1].notes_slide.notes_text_frame.text = (
    "Stress that the user types exactly one command. The script handles "
    "permissions, stale containers and verification on its own."
)

# ================================================================ 13 WHAT YOU SEE
s = slide_base("What you actually see", 13,
               "Three windows, one story")
views = [
    ("The 3D room", "The robot driving around the furniture in a physical "
     "simulation. Watch it sweep the room in strips.", BLUE,
     "Gazebo window"),
    ("The robot's dashboard", "Live map, laser dots, planned route, robot "
     "position. The engineer's view.", GREEN,
     "RViz window"),
    ("The web view", "The same information in a browser tab, useful for "
     "showing other people on their own screen.", ORANGE,
     "app.foxglove.dev + ws://localhost:8765"),
    ("The logs", "Text files quietly recording every decision: what it "
     "cleaned, when it charged, what went wrong.", RED,
     "/tmp/opencode/*.log"),
]
x = Inches(0.62)
for i, (t, b, c, tag) in enumerate(views):
    box(s, x, Inches(1.55), Inches(2.92), Inches(4.10), fill=WHITE,
        line=RGBColor(0xD3, 0xDC, 0xE8))
    box(s, x, Inches(1.55), Inches(2.92), Inches(0.10), fill=c,
        shape=MSO_SHAPE.RECTANGLE)
    text(s, x + Inches(0.20), Inches(1.78), Inches(2.52), Inches(0.5),
         t, size=17, color=c, bold=True)
    text(s, x + Inches(0.20), Inches(2.35), Inches(2.52), Inches(2.0),
         b, size=12.5, color=RGBColor(0x33, 0x3D, 0x49),
         anchor=MSO_ANCHOR.TOP)
    box(s, x + Inches(0.20), Inches(4.62), Inches(2.52), Inches(0.85),
        fill=LIGHT)
    text(s, x + Inches(0.30), Inches(4.62), Inches(2.32), Inches(0.85),
         tag, size=10.5, color=GREY, anchor=MSO_ANCHOR.MIDDLE)
    x += Inches(3.07)
footer(s, "A full cycle — clean, park, charge, resume — takes a few minutes "
          "when the battery is sped up for a demo.")
prs.slides[-1].notes_slide.notes_text_frame.text = (
    "If demoing live, open the 3D window first and let it run while talking."
)

# ================================================================ 14 CHALLENGES
s = slide_base("The tricky parts (and how they were solved)", 14,
               "Honest list — these are the things that actually broke")
prob = [
    ("The robot would not move at all",
     "Two programs disagreed about the message format for the wheels.",
     "Make every program speak the same plain format."),
    ("It aimed at the sofa",
     "The map sometimes says furniture is 'unknown', not 'blocked'.",
     "Ban known furniture as a destination, and re-check each spot before "
     "driving."),
    ("It froze next to the table",
     "The steering algorithm can give up near a goal, silently outputting "
     "zero.",
     "Detect 15 s of silence, skip that spot, move on."),
    ("It got 'stuck' forever at the dock",
     "A safety rule stopped the robot and then stopped talking to it.",
     "Replace the hard stop with a slow-down rule."),
    ("After docking, the map was wrong",
     "The mapping update needs movement; the undock move was slightly too "
     "short.",
     "Lower the movement needed to update the map."),
]
y = Inches(1.86)
for i, (t, c, f) in enumerate(prob):
    box(s, Inches(0.62), y, Inches(12.1), Inches(0.86), fill=WHITE,
        line=RGBColor(0xD3, 0xDC, 0xE8))
    box(s, Inches(0.62), y, Inches(0.075), Inches(0.86), fill=RED,
        shape=MSO_SHAPE.RECTANGLE)
    text(s, Inches(0.92), y + Inches(0.08), Inches(3.6), Inches(0.70), t,
         size=12, color=RED, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    text(s, Inches(4.65), y + Inches(0.08), Inches(3.8), Inches(0.70), c,
         size=10.5, color=GREY, anchor=MSO_ANCHOR.MIDDLE)
    text(s, Inches(8.60), y + Inches(0.08), Inches(3.95), Inches(0.70), f,
         size=10.5, color=GREEN, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    y += Inches(0.90)
text(s, Inches(0.62), Inches(1.24), Inches(4.3), Inches(0.3),
     "symptom", size=11, color=RED, bold=True)
text(s, Inches(4.65), Inches(1.24), Inches(4.3), Inches(0.3),
     "real cause", size=11, color=GREY, bold=True)
text(s, Inches(8.60), Inches(1.24), Inches(4.3), Inches(0.3),
     "fix", size=11, color=GREEN, bold=True)
prs.slides[-1].notes_slide.notes_text_frame.text = (
    "This slide builds credibility: the system works because each of these "
    "was found and fixed by measuring, not guessing."
)

# ================================================================ 15 NEXT
s = slide_base("What is next", 15, "Clear, honest roadmap")
improve = [
    ("Clean better", "Dwell longer on dirty spots and re-plan as the map "
     "fills in."),
    ("Handle several rooms", "Split a home into rooms and clean them one by "
     "one."),
    ("Smarter docking", "Use a visual marker for millimetre-accurate "
     "parking."),
    ("Smoother odometry", "Combine wheel and sensor data so the map drifts "
     "less."),
    ("Automatic testing", "Run the whole simulation automatically on every "
     "change, so nothing breaks quietly."),
    ("Run on real hardware", "The same software already supports a real "
     "TurtleBot3 — finish validating it."),
]
x = Inches(0.62)
for i, (t, b) in enumerate(improve):
    cx = Inches(0.62) + Inches(3.07) * (i % 3)
    cy = Inches(1.66) + Inches(2.32) * (i // 3)
    card(s, cx, cy, Inches(2.92), Inches(2.16), 0, t, b,
         accent=[BLUE, GREEN, ORANGE][i % 3], tsize=15, bsize=12.5)
footer(s, "None of this changes the core idea: map it, clean it, charge "
          "itself, repeat.")
prs.slides[-1].notes_slide.notes_text_frame.text = (
    "Keep it short. The roadmap signals the project is alive without "
    "overselling."
)

# ================================================================ 16 TAKEAWAY
s = blank()
box(s, Emu(0), Emu(0), SW, SH, fill=NAVY, shape=MSO_SHAPE.RECTANGLE)
text(s, Inches(1.05), Inches(0.80), Inches(11.2), Inches(0.7),
     "Three things to remember", size=34, color=WHITE, bold=True)

pts = [
    ("1", "It figures out the room itself", "No map is given to it. It "
     "drives, looks, and builds its own plan.", GREEN),
    ("2", "It takes care of itself", "Watches its battery, parks, charges, "
     "and gets back to work without help.", ORANGE),
    ("3", "It cannot get permanently stuck", "Three layers of watchdogs "
     "notice problems and fix them automatically.", BLUE),
]
y = Inches(2.05)
for n, t, b, c in pts:
    box(s, Inches(1.05), y, Inches(11.2), Inches(1.28),
        fill=RGBColor(0x1D, 0x3A, 0x66), line=RGBColor(0x2E, 0x55, 0x8C))
    box(s, Inches(1.32), y + Inches(0.30), Inches(0.68), Inches(0.68),
        fill=c, shape=MSO_SHAPE.OVAL)
    text(s, Inches(1.32), y + Inches(0.30), Inches(0.68), Inches(0.68), n,
         size=22, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
    text(s, Inches(2.25), y + Inches(0.14), Inches(9.7), Inches(0.5), t,
         size=19, color=WHITE, bold=True)
    text(s, Inches(2.25), y + Inches(0.66), Inches(9.7), Inches(0.5), b,
         size=14, color=RGBColor(0xB6, 0xCB, 0xE6))
    y += Inches(1.44)

text(s, Inches(1.05), Inches(6.55), Inches(11.2), Inches(0.5),
     "Questions welcome — and you can watch the whole thing run live.",
     size=15, color=RGBColor(0x8F, 0xB4, 0xDC), italic=True)
prs.slides[-1].notes_slide.notes_text_frame.text = (
    "Close with the three-line summary, then offer the live demo."
)

# ---------------------------------------------------------------- save
here = os.path.dirname(os.path.abspath(__file__))
out_dir = os.path.join(os.path.dirname(here), "docs")
os.makedirs(out_dir, exist_ok=True)
out = os.path.join(out_dir, "House_Cleaner_Robot.pptx")
prs.save(out)
print(f"Wrote {out} ({len(prs.slides.__iter__.__self__._sldIdLst)} slides)")
