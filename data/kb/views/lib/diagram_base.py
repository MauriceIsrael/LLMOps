#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generates the 5 architecture diagrams (v1.0, English) in SVG then PNG."""
import cairosvg

FONT = "DejaVu Sans, sans-serif"
COL = {
    "purple": {"fill": "#EEEDFE", "stroke": "#534AB7", "title": "#3C3489", "sub": "#534AB7"},
    "teal":   {"fill": "#E1F5EE", "stroke": "#0F6E56", "title": "#085041", "sub": "#0F6E56"},
    "coral":  {"fill": "#FAECE7", "stroke": "#993C1D", "title": "#712B13", "sub": "#993C1D"},
    "gray":   {"fill": "#F1EFE8", "stroke": "#5F5E5A", "title": "#444441", "sub": "#5F5E5A"},
    "amber":  {"fill": "#FAEEDA", "stroke": "#854F0B", "title": "#633806", "sub": "#854F0B"},
}
ARROW = "#5F5E5A"
TXT = "#2C2C2A"
TXT2 = "#5F5E5A"

DEFS = ('<defs><marker id="arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" '
        'markerHeight="7" orient="auto-start-reverse"><path d="M2 1L8 5L2 9" fill="none" '
        f'stroke="{ARROW}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>'
        '</marker></defs>')


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def box(x, y, w, h, color, title, subs=(), rx=10, tsize=21, ssize=15):
    c = COL[color]
    lh = 23
    total = tsize + len(subs) * lh
    ty = y + h / 2 - total / 2 + tsize * 0.8
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{c["fill"]}" '
           f'stroke="{c["stroke"]}" stroke-width="1.4"/>']
    out.append(f'<text x="{x + w / 2}" y="{ty:.0f}" text-anchor="middle" font-family="{FONT}" '
               f'font-size="{tsize}" font-weight="bold" fill="{c["title"]}">{esc(title)}</text>')
    for i, s in enumerate(subs):
        out.append(f'<text x="{x + w / 2}" y="{ty + (i + 1) * lh:.0f}" text-anchor="middle" '
                   f'font-family="{FONT}" font-size="{ssize}" fill="{c["sub"]}">{esc(s)}</text>')
    return "\n".join(out)


def zone(x, y, w, h, label, color="gray"):
    c = COL[color]
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="{c["fill"]}" '
            f'fill-opacity="0.30" stroke="{c["stroke"]}" stroke-width="1.4" stroke-dasharray="8 6"/>'
            f'<text x="{x + 22}" y="{y + 32}" font-family="{FONT}" font-size="18" '
            f'font-weight="bold" fill="{c["title"]}">{esc(label)}</text>')


def arrow(pts, dashed=False, both=False, width=1.8):
    d = "M" + " L".join(f"{p[0]} {p[1]}" for p in pts)
    dash = ' stroke-dasharray="7 6"' if dashed else ""
    ms = ' marker-start="url(#arr)"' if both else ""
    return (f'<path d="{d}" fill="none" stroke="{ARROW}" stroke-width="{width}"{dash} '
            f'marker-end="url(#arr)"{ms}/>')


def label(x, y, s, size=14, anchor="middle", color=TXT2, bold=False):
    fw = ' font-weight="bold"' if bold else ""
    return (f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="{FONT}" '
            f'font-size="{size}"{fw} fill="{color}">{esc(s)}</text>')


def num(x, y, n):
    return (f'<circle cx="{x}" cy="{y}" r="14" fill="#534AB7"/>'
            f'<text x="{x}" y="{y + 5}" text-anchor="middle" font-family="{FONT}" '
            f'font-size="14" font-weight="bold" fill="#FFFFFF">{n}</text>')


def svg(w, h, body, path):
    doc = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
           f'viewBox="0 0 {w} {h}"><rect width="{w}" height="{h}" fill="#FFFFFF"/>'
           f'{DEFS}\n{body}\n</svg>')
    with open(path, "w") as f:
        f.write(doc)
    cairosvg.svg2png(url=path, write_to=path.replace(".svg", ".png"), scale=2.0)
    print("OK", path)


