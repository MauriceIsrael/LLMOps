#!/usr/bin/env python3
"""Generates a .drawio file (4 pages) with the 4 architecture views in English."""
import html
import uuid

COL = {
    "purple": ("#EEEDFE", "#534AB7", "#3C3489"),
    "teal":   ("#E1F5EE", "#0F6E56", "#085041"),
    "coral":  ("#FAECE7", "#993C1D", "#712B13"),
    "gray":   ("#F1EFE8", "#5F5E5A", "#444441"),
    "amber":  ("#FAEEDA", "#854F0B", "#633806"),
}
EDGE = "#5F5E5A"


class Page:
    def __init__(self, name, w, h):
        self.name, self.w, self.h = name, w, h
        self.cells, self.n, self.geom = [], 0, {}

    def nid(self, prefix="c"):
        self.n += 1
        return f"{prefix}{self.n}"

    def box(self, x, y, w, h, color, title, subs=(), tsize=14, ssize=11, cid=None):
        cid = cid or self.nid("b")
        fill, stroke, font = COL[color]
        sub = "".join(f'<br/><font style="font-size:{ssize}px;" color="{stroke}">{html.escape(s)}</font>' for s in subs)
        value = f'<b style="font-size:{tsize}px;">{html.escape(title)}</b>{sub}'
        style = (f"rounded=1;whiteSpace=wrap;html=1;arcSize=8;fillColor={fill};"
                 f"strokeColor={stroke};fontColor={font};verticalAlign=middle;align=center;")
        self.cells.append(
            f'<mxCell id="{cid}" value="{html.escape(value)}" style="{style}" vertex="1" parent="1">'
            f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')
        self.geom[cid] = (x, y, w, h)
        return cid

    def zone(self, x, y, w, h, label, color="gray", cid=None):
        cid = cid or self.nid("z")
        fill, stroke, font = COL[color]
        style = (f"rounded=1;whiteSpace=wrap;html=1;arcSize=4;dashed=1;dashPattern=8 6;"
                 f"fillColor={fill};fillOpacity=35;strokeColor={stroke};fontColor={font};"
                 f"fontSize=13;fontStyle=1;verticalAlign=top;align=left;spacingLeft=14;spacingTop=8;")
        self.cells.append(
            f'<mxCell id="{cid}" value="{html.escape(label)}" style="{style}" vertex="1" parent="1">'
            f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')
        self.geom[cid] = (x, y, w, h)
        return cid

    def text(self, x, y, w, s, size=11, bold=False, color=EDGE, align="center"):
        cid = self.nid("t")
        fs = "fontStyle=1;" if bold else ""
        style = f"text;html=1;align={align};verticalAlign=middle;fontSize={size};fontColor={color};{fs}"
        self.cells.append(
            f'<mxCell id="{cid}" value="{html.escape(s)}" style="{style}" vertex="1" parent="1">'
            f'<mxGeometry x="{x}" y="{y}" width="{w}" height="24" as="geometry"/></mxCell>')
        return cid

    def badge(self, x, y, n):
        cid = self.nid("n")
        style = ("ellipse;whiteSpace=wrap;html=1;fillColor=#534AB7;strokeColor=none;"
                 "fontColor=#FFFFFF;fontSize=11;fontStyle=1;")
        self.cells.append(
            f'<mxCell id="{cid}" value="{n}" style="{style}" vertex="1" parent="1">'
            f'<mxGeometry x="{x - 12}" y="{y - 12}" width="24" height="24" as="geometry"/></mxCell>')
        return cid

    def _frac(self, cid, px, py):
        x, y, w, h = self.geom[cid]
        return round((px - x) / w, 3), round((py - y) / h, 3)

    def edge(self, src, dst, sp, tp, pts=(), dashed=False, both=False, label=None):
        cid = self.nid("e")
        sx, sy = self._frac(src, *sp)
        tx, ty = self._frac(dst, *tp)
        style = (f"edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor={EDGE};"
                 f"strokeWidth=1.5;endArrow=open;endFill=0;endSize=8;"
                 f"exitX={sx};exitY={sy};exitDx=0;exitDy=0;entryX={tx};entryY={ty};entryDx=0;entryDy=0;")
        if dashed:
            style += "dashed=1;dashPattern=7 6;"
        if both:
            style += "startArrow=open;startFill=0;startSize=8;"
        wp = ""
        if pts:
            wp = ('<Array as="points">'
                  + "".join(f'<mxPoint x="{p[0]}" y="{p[1]}"/>' for p in pts)
                  + "</Array>")
        val = f' value="{html.escape(label)}"' if label else ""
        lblstyle = "fontSize=11;fontColor=" + EDGE + ";" if label else ""
        self.cells.append(
            f'<mxCell id="{cid}"{val} style="{style}{lblstyle}" edge="1" parent="1" '
            f'source="{src}" target="{dst}"><mxGeometry relative="1" as="geometry">{wp}'
            f'</mxGeometry></mxCell>')
        return cid

    def xml(self):
        body = "".join(self.cells)
        return (f'<diagram id="{uuid.uuid4().hex[:12]}" name="{html.escape(self.name)}">'
                f'<mxGraphModel dx="1000" dy="700" grid="1" gridSize="10" guides="1" tooltips="1" '
                f'connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="{self.w}" '
                f'pageHeight="{self.h}" math="0" shadow="0"><root>'
                f'<mxCell id="0"/><mxCell id="1" parent="0"/>{body}'
                f'</root></mxGraphModel></diagram>')


pages = []

