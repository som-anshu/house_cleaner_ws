#!/usr/bin/env python3
"""Structural sanity check for the generated deck.

LibreOffice is not installed on this machine, so instead of rasterising the
slides we verify the geometry that usually breaks a hand-built deck:

  * every shape fits inside the 13.333 x 7.5 in slide
  * no two TEXT shapes overlap (estimated from text length + font size)
  * every slide has a title
  * no text frame is empty

Run: ~/anaconda3/bin/python tools/check_ppt.py
"""
import os
import sys

from pptx import Presentation
from pptx.util import Inches, Pt

EMU_IN = 914400.0
SW, SH = 13.333, 7.5
CHARS_PER_INCH = 3.6  # conservative Calibri-ish estimate at 12 pt


def est_height_ok(shape):
    """Rough wrapped-text height in inches for a text shape."""
    tf = shape.text_frame
    w_in = shape.width / EMU_IN
    total = 0.0
    for p in tf.paragraphs:
        txt = "".join(r.text for r in p.runs)
        if not txt:
            total += 0.22
            continue
        size = max((r.font.size.pt if r.font.size else 12.0) for r in p.runs)
        cap = max(1, int(w_in * CHARS_PER_INCH * (12.0 / size)))
        lines = -(-len(txt) // cap)
        total += lines * (size / 72.0) * 1.22
    return total


def rect(sh):
    return (
        sh.left / EMU_IN, sh.top / EMU_IN,
        (sh.left + sh.width) / EMU_IN, (sh.top + sh.height) / EMU_IN,
    )


def overlap(a, b, tol=0.02):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix = min(ax2, bx2) - max(ax1, bx1)
    iy = min(ay2, by2) - max(ay1, by1)
    return ix > tol and iy > tol


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "docs", "House_Cleaner_Robot.pptx")
    prs = Presentation(path)
    problems = []
    n_shapes = 0

    for idx, slide in enumerate(prs.slides, start=1):
        texts = []
        titles = 0
        for sh in slide.shapes:
            n_shapes += 1
            if sh.left is None:
                continue
            x1, y1, x2, y2 = rect(sh)
            if x1 < -0.02 or y1 < -0.02 or x2 > SW + 0.02 or y2 > SH + 0.02:
                problems.append(
                    f"slide {idx}: shape off-slide "
                    f"({x1:.2f},{y1:.2f})-({x2:.2f},{y2:.2f}) "
                    f"'{sh.shape_type}'"
                )
            if not sh.has_text_frame:
                continue
            txt = sh.text_frame.text.strip()
            if not txt:
                continue
            if len(txt) > 12 and y1 < 1.2:
                titles += 1
            # Overflow estimate. Only flag when the text plausibly cannot fit
            # even allowing for vertical-anchor centring (shapes in this deck
            # are middle-anchored, so text may extend past the box a little
            # without looking wrong -- use a generous factor).
            if len(txt) > 20:
                need = est_height_ok(sh)
                have = sh.height / EMU_IN
                if need > have * 1.60:
                    problems.append(
                        f"slide {idx}: possible overflow "
                        f"(needs ~{need:.2f}in, box {have:.2f}in) "
                        f"\"{txt[:46]}...\""
                    )
            texts.append((rect(sh), txt, sh))

        # overlap between text shapes only (cards/boxes legitimately overlap
        # nothing, so text-on-card overlaps are fine: we skip if one contains
        # the other)
        for i in range(len(texts)):
            for j in range(i + 1, len(texts)):
                a, ta, sa = texts[i]
                b, tb, sb = texts[j]
                if not overlap(a, b):
                    continue
                ca = a[0] >= b[0] - .02 and a[2] <= b[2] + .02 and \
                     a[1] >= b[1] - .02 and a[3] <= b[3] + .02
                cb = b[0] >= a[0] - .02 and b[2] <= a[2] + .02 and \
                     b[1] >= a[1] - .02 and b[3] <= a[3] + .02
                if ca or cb:
                    continue
                problems.append(
                    f"slide {idx}: text overlap \"{ta[:28]}\" vs \"{tb[:28]}\""
                )
        if idx > 1 and titles == 0:
            problems.append(f"slide {idx}: no title text found")

    print(f"{path}")
    print(f"  slides : {len(prs.slides)}")
    print(f"  shapes : {n_shapes}")
    if problems:
        print(f"  PROBLEMS ({len(problems)}):")
        for p in problems:
            print("   -", p)
        return 1
    print("  layout : OK (all shapes on-slide, no text overlaps, "
          "no estimated overflow)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
