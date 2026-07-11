#!/usr/bin/env python3
# Kamera_Konfigurationsmanager - Plugin-basierter Konfigurationsmanager fuer Netzwerkkameras.
# Copyright (C) 2026 Mirik
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Erzeugt Benutzerhandbuch.pdf aus BENUTZERHANDBUCH.md.

Quelle der Wahrheit ist die Markdown-Datei — das PDF wird daraus gebaut, damit beides
nicht auseinanderlaeuft. Unterstuetzt wird die Teilmenge Markdown, die das Handbuch
benutzt: Ueberschriften (##/###), Absaetze, Aufzaehlungen, nummerierte Listen,
Tabellen, Code-Bloecke, Zitatbloecke (-> Hinweiskasten) sowie **fett**, *kursiv* und
`code` im Fliesstext.

Nur zum Bauen der Dokumentation noetig, nicht zur Laufzeit des Programms:

    pip install reportlab
    python3 tools/make_manual.py
"""

from __future__ import annotations

import os
import re
import sys
from datetime import date

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether,
                                ListFlowable, ListItem, PageBreak, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "BENUTZERHANDBUCH.md")
OUT = os.path.join(ROOT, "Benutzerhandbuch.pdf")
ICON = os.path.join(ROOT, "assets", "Kamerakonfigurationsmanager.png")

ACCENT = colors.HexColor("#1E5FBF")     # Blau des Programm-Icons
NOTE_BG = colors.HexColor("#EEF3FC")
NOTE_LINE = colors.HexColor("#1E5FBF")
GREY = colors.HexColor("#555555")

# DejaVu deckt die im Handbuch benutzten Sonderzeichen ab (Pfeile, Dreiecke); eine
# kursive Schnitte hat es nicht, dafuer springt Noto Sans ein.
FONTS = {
    "normal": ("KKM", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    "bold": ("KKM-Bold", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    "italic": ("KKM-Italic", "/usr/share/fonts/truetype/noto/NotoSans-Italic.ttf"),
    "mono": ("KKM-Mono", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
}


def register_fonts():
    for name, path in FONTS.values():
        if not os.path.exists(path):
            sys.exit(f"Schrift fehlt: {path}")
        pdfmetrics.registerFont(TTFont(name, path))
    pdfmetrics.registerFontFamily(
        "KKM", normal="KKM", bold="KKM-Bold", italic="KKM-Italic",
        boldItalic="KKM-Bold")


def app_version() -> str:
    src = open(os.path.join(ROOT, "kkm", "version.py"), encoding="utf-8").read()
    m = re.search(r'__version__\s*=\s*"([^"]+)"', src)
    return m.group(1) if m else "?"


# --------------------------------------------------------------------- Stile
def build_styles():
    ss = getSampleStyleSheet()
    body = ParagraphStyle(
        "Body", parent=ss["BodyText"], fontName="KKM", fontSize=10, leading=15,
        spaceBefore=0, spaceAfter=7, alignment=TA_JUSTIFY)
    return {
        "body": body,
        "h1": ParagraphStyle("H1", parent=body, fontName="KKM-Bold", fontSize=17,
                             leading=22, textColor=ACCENT, spaceBefore=16,
                             spaceAfter=9, alignment=0),
        "h2": ParagraphStyle("H2", parent=body, fontName="KKM-Bold", fontSize=12.5,
                             leading=17, spaceBefore=11, spaceAfter=5, alignment=0),
        "bullet": ParagraphStyle("Bullet", parent=body, spaceAfter=3, alignment=0),
        "code": ParagraphStyle("Code", parent=body, fontName="KKM-Mono", fontSize=8.5,
                               leading=12, alignment=0, textColor=colors.HexColor("#222222")),
        "note": ParagraphStyle("Note", parent=body, fontSize=9.5, leading=14,
                               alignment=0, spaceAfter=0),
        "cell": ParagraphStyle("Cell", parent=body, fontSize=9, leading=12,
                               alignment=0, spaceAfter=0),
        "cellhead": ParagraphStyle("CellHead", parent=body, fontName="KKM-Bold",
                                   fontSize=9, leading=12, alignment=0, spaceAfter=0,
                                   textColor=colors.white),
        "title": ParagraphStyle("Title", parent=body, fontName="KKM-Bold", fontSize=30,
                                leading=36, alignment=1, textColor=ACCENT, spaceAfter=6),
        "subtitle": ParagraphStyle("Subtitle", parent=body, fontSize=13, leading=18,
                                   alignment=1, textColor=GREY, spaceAfter=4),
        "toc1": ParagraphStyle("TOC1", parent=body, fontName="KKM-Bold", fontSize=10.5,
                               leading=18, alignment=0, spaceAfter=0),
        "toc2": ParagraphStyle("TOC2", parent=body, fontSize=9.5, leading=15,
                               leftIndent=14, alignment=0, spaceAfter=0,
                               textColor=GREY),
    }


# ------------------------------------------------------------------ Inline
def inline(text: str) -> str:
    """Markdown-Auszeichnung im Fliesstext -> ReportLab-Markup."""
    text = (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    text = re.sub(r"`([^`]+)`",
                  r'<font face="KKM-Mono" size="9">\1</font>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", text)
    return text


# ------------------------------------------------------------------ Parser
class Manual:
    """Baut aus der Markdown-Quelle die Flowable-Liste."""

    def __init__(self, styles):
        self.s = styles
        self.story: list = []

    def note(self, lines: list[str]):
        """Zitatblock -> Hinweiskasten mit farbigem Balken links."""
        text = inline(" ".join(l.lstrip("> ").strip() for l in lines))
        inner = Paragraph(text, self.s["note"])
        box = Table([[inner]], colWidths=[160 * mm])
        box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), NOTE_BG),
            ("LINEBEFORE", (0, 0), (0, -1), 2.2, NOTE_LINE),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        self.story += [Spacer(1, 3), box, Spacer(1, 9)]

    def code(self, lines: list[str]):
        text = "<br/>".join(
            l.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace(" ", "&nbsp;") for l in lines)
        box = Table([[Paragraph(text, self.s["code"])]], colWidths=[160 * mm])
        box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F2F2F2")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#DDDDDD")),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        self.story += [Spacer(1, 2), box, Spacer(1, 9)]

    def table(self, rows: list[str]):
        cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
        cells = [r for r in cells if not set("".join(r)) <= set("-: ")]   # Trennzeile weg
        head, *rest = cells
        ncols = len(head)
        width = 160 * mm
        col_widths = [width * 0.34] + [(width * 0.66) / (ncols - 1)] * (ncols - 1) \
            if ncols > 1 else [width]
        data = [[Paragraph(inline(c), self.s["cellhead"]) for c in head]]
        data += [[Paragraph(inline(c), self.s["cell"]) for c in row] for row in rest]
        t = Table(data, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#F4F7FB")]),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        self.story += [Spacer(1, 2), t, Spacer(1, 10)]

    def bullets(self, items: list[str], numbered=False):
        flow = ListFlowable(
            [ListItem(Paragraph(inline(i), self.s["bullet"]), leftIndent=14)
             for i in items],
            bulletType="1" if numbered else "bullet",
            bulletFontName="KKM", bulletFontSize=8 if not numbered else 10,
            start="1" if numbered else "•", leftIndent=16, bulletDedent=10,
            spaceAfter=7)
        self.story.append(flow)

    def heading(self, text: str, level: int):
        style = self.s["h1"] if level == 2 else self.s["h2"]
        para = Paragraph(inline(text), style)
        para._toc_level = 0 if level == 2 else 1       # fuer das Inhaltsverzeichnis
        para._toc_text = text
        if level == 2 and self.story:
            self.story.append(Spacer(1, 6))
        self.story.append(para)

    def parse(self, text: str):
        lines = text.split("\n")
        i = 0
        para: list[str] = []

        def flush():
            nonlocal para
            if para:
                self.story.append(Paragraph(inline(" ".join(para)), self.s["body"]))
                para = []

        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            if stripped.startswith("# "):            # Dokumenttitel -> Titelseite
                i += 1
                continue
            if stripped.startswith("### "):
                flush(); self.heading(stripped[4:], 3); i += 1; continue
            if stripped.startswith("## "):
                flush(); self.heading(stripped[3:], 2); i += 1; continue
            if stripped.startswith("```"):
                flush()
                block = []
                i += 1
                while i < len(lines) and not lines[i].strip().startswith("```"):
                    block.append(lines[i]); i += 1
                self.code(block); i += 1; continue
            if stripped.startswith("> "):
                flush()
                block = []
                while i < len(lines) and lines[i].strip().startswith(">"):
                    block.append(lines[i].strip()); i += 1
                self.note(block); continue
            if stripped.startswith("|"):
                flush()
                block = []
                while i < len(lines) and lines[i].strip().startswith("|"):
                    block.append(lines[i]); i += 1
                self.table(block); continue
            if re.match(r"^[-*] ", stripped) or re.match(r"^\d+\. ", stripped):
                flush()
                numbered = bool(re.match(r"^\d+\. ", stripped))
                items: list[str] = []
                while i < len(lines):
                    s = lines[i].strip()
                    if re.match(r"^[-*] ", s) or re.match(r"^\d+\. ", s):
                        items.append(re.sub(r"^([-*]|\d+\.)\s+", "", s))
                    elif s and lines[i].startswith(("  ", "\t")) and items:
                        items[-1] += " " + s            # Fortsetzungszeile
                    else:
                        break
                    i += 1
                self.bullets(items, numbered); continue
            if not stripped:
                flush(); i += 1; continue

            para.append(stripped)
            i += 1
        flush()


# ------------------------------------------------------------------ Dokument
class ManualDoc(BaseDocTemplate):
    """Seitenrahmen + Kopf-/Fusszeile; meldet Ueberschriften ans Inhaltsverzeichnis."""

    def __init__(self, path, version, **kw):
        super().__init__(path, pagesize=A4, leftMargin=25 * mm, rightMargin=25 * mm,
                         topMargin=22 * mm, bottomMargin=20 * mm,
                         title="Kamera_Konfigurationsmanager — Benutzerhandbuch",
                         author="Mirik", **kw)
        self.version = version
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height,
                      id="body")
        self.addPageTemplates([
            PageTemplate(id="title", frames=[frame]),
            PageTemplate(id="content", frames=[frame], onPage=self.decorate),
        ])

    def decorate(self, canvas, doc):
        canvas.saveState()
        canvas.setFont("KKM", 8)
        canvas.setFillColor(GREY)
        canvas.drawString(self.leftMargin, A4[1] - 14 * mm,
                          "Kamera_Konfigurationsmanager — Benutzerhandbuch")
        canvas.drawRightString(A4[0] - self.rightMargin, A4[1] - 14 * mm,
                               f"Version {self.version}")
        canvas.setStrokeColor(colors.HexColor("#DDDDDD"))
        canvas.line(self.leftMargin, A4[1] - 16 * mm,
                    A4[0] - self.rightMargin, A4[1] - 16 * mm)
        canvas.drawCentredString(A4[0] / 2, 12 * mm, str(canvas.getPageNumber()))
        canvas.restoreState()

    def afterFlowable(self, flowable):
        level = getattr(flowable, "_toc_level", None)
        if level is not None:
            self.notify("TOCEntry", (level, flowable._toc_text, self.page))


def title_page(styles, version) -> list:
    story = []
    story.append(Spacer(1, 30 * mm))
    if os.path.exists(ICON):
        img = Image(ICON, width=34 * mm, height=34 * mm)
        img.hAlign = "CENTER"
        story += [img, Spacer(1, 12 * mm)]
    story.append(Paragraph("Benutzerhandbuch", styles["title"]))
    story.append(Paragraph("Kamera_Konfigurationsmanager", styles["subtitle"]))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "Netzwerkkameras finden und konfigurieren — Axis und ONVIF",
        styles["subtitle"]))
    story.append(Spacer(1, 30 * mm))
    meta = ParagraphStyle("Meta", parent=styles["subtitle"], fontSize=10, leading=16)
    story.append(Paragraph(f"Programmversion {version}", meta))
    story.append(Paragraph(f"Stand: {date.today().strftime('%d.%m.%Y')}", meta))
    story.append(Paragraph("GPL-3.0-or-later", meta))
    story.append(PageBreak())
    return story


def main():
    register_fonts()
    styles = build_styles()
    version = app_version()

    toc = TableOfContents()
    toc.levelStyles = [styles["toc1"], styles["toc2"]]

    manual = Manual(styles)
    manual.parse(open(SRC, encoding="utf-8").read())

    story = title_page(styles, version)
    story.append(Paragraph("Inhalt", styles["h1"]))
    story.append(toc)
    story.append(PageBreak())
    story += manual.story

    doc = ManualDoc(OUT, version)
    # Zweifacher Durchlauf: erst Seitenzahlen sammeln, dann das Inhaltsverzeichnis
    # damit fuellen (multiBuild erledigt beides).
    doc.multiBuild(story)
    print(f">> {OUT} ({os.path.getsize(OUT) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
