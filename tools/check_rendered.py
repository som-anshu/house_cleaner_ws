#!/usr/bin/env python3
"""Check the RENDERED deck for layout faults.

python-pptx can only describe intent; the PDF tells us what LibreOffice
actually drew. This script parses `pdftotext -bbox-layout` output and reports:

  * text extending past the page edge
  * text lines from *different* text boxes that overlap each other
  * any slide whose text is suspiciously sparse (content silently missing)

Usage:
    soffice --headless --convert-to pdf --outdir /tmp/p docs/deck.pptx
    pdftotext -bbox-layout /tmp/p/deck.pdf /tmp/p/out.html
    ~/anaconda3/bin/python tools/check_rendered.py /tmp/p/out.html
"""
import html
import re
import sys
import xml.etree.ElementTree as ET

PAGE_W, PAGE_H = 959.98, 540.0     # points (13.333 x 7.5 in)
EDGE_TOL = 1.5


def parse(path):
    raw = open(path, encoding="utf-8", errors="replace").read()
    # pdftotext -bbox-layout emits XHTML with a default xmlns, so every tag
    # inherits a namespace and bare iter("page") would match nothing. Strip
    # the doctype, meta tags and namespace declarations, then parse normally.
    raw = re.sub(r"<!DOCTYPE[^>]*>", "", raw)
    raw = re.sub(r"<meta[^>]*>", "", raw)
    raw = re.sub(r'\sxmlns(:\w+)?="[^"]*"', "", raw)
    raw = raw.replace("<br>", "<br/>")
    root = ET.fromstring(raw)

    pages = []
    for page in root.iter("page"):
        lines = []
        for block in page.iter("block"):
            for line in block.iter("line"):
                words = [w for w in line.iter("word")]
                if not words:
                    continue
                txt = " ".join((w.text or "") for w in words).strip()
                if not txt:
                    continue
                x1 = float(line.get("xMin"))
                y1 = float(line.get("yMin"))
                x2 = float(line.get("xMax"))
                y2 = float(line.get("yMax"))
                # identify the owning block so we can tell "same text box"
                # (legitimate multi-line) from "different text box" (clash)
                bid = id(block)
                lines.append((bid, x1, y1, x2, y2, txt))
        pages.append(lines)
    return pages


def overlap(a, b, tol=1.0):
    ix = min(a[3], b[3]) - max(a[1], b[1])
    iy = min(a[4], b[4]) - max(a[2], b[2])
    if ix <= tol or iy <= tol:
        return 0.0
    return ix * iy


def main():
    path = sys.argv[1]
    pages = parse(path)
    problems = []
    print(f"{path}\n  pages: {len(pages)}")

    for i, lines in enumerate(pages, start=1):
        if not lines:
            problems.append(f"page {i}: NO TEXT AT ALL")
            continue
        for (bid, x1, y1, x2, y2, txt) in lines:
            if x1 < -EDGE_TOL or y1 < -EDGE_TOL or \
               x2 > PAGE_W + EDGE_TOL or y2 > PAGE_H + EDGE_TOL:
                problems.append(
                    f"page {i}: text past page edge "
                    f"({x1:.0f},{y1:.0f})-({x2:.0f},{y2:.0f}) \"{txt[:40]}\""
                )
        # cross-box overlaps
        for a in range(len(lines)):
            for b in range(a + 1, len(lines)):
                la, lb = lines[a], lines[b]
                if la[0] == lb[0]:
                    continue          # same text box: normal line flow
                ar = overlap(la, lb)
                if ar <= 0:
                    continue
                # ignore tiny kissing overlaps
                smaller = min((la[3] - la[1]) * (la[4] - la[2]),
                              (lb[3] - lb[1]) * (lb[4] - lb[2]))
                if smaller <= 0:
                    continue
                if ar / smaller < 0.06:
                    continue
                problems.append(
                    f"page {i}: text clash \"{la[5][:32]}\" vs "
                    f"\"{lb[5][:32]}\" ({ar:.0f}pt^2)"
                )
        # content density sanity: a slide with a title but almost nothing else
        if len(lines) <= 2:
            problems.append(
                f"page {i}: only {len(lines)} text line(s) -- content "
                "may be missing"
            )

    if problems:
        print(f"  PROBLEMS ({len(problems)}):")
        seen = set()
        for p in problems:
            if p in seen:
                continue
            seen.add(p)
            print("   -", p)
        return 1
    print("  render : OK (text inside page, no cross-box clashes, "
          "content present on every slide)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
