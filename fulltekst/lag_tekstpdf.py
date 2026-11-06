"""Produce a text-only accessible PDF from an explicitly CC BY licensed article.

Omit all source illustrations, photographs, third-party graphics and complex
layout. Used when the original PDF includes artwork with restricted permission.

The original article PDF must stay in the private reading cache and is NOT
copied to the public repo. The adapted PDF contains only extractable article
text, source-page labels, complete authorship and explicit change notice.
"""
from __future__ import annotations
from html import escape
from pathlib import Path
import re

def make_text_only_pdf(pages: list[str], destination: Path, *, title: str,
                       authors: list[str], year: int, doi: str, license_url: str,
                       original_url: str) -> None:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,HRFlowable
    except ImportError as exc:
        raise RuntimeError("Text-only CC derivative requires reportlab") from exc

    # Use an installed host TTF font. Embed it in the PDF, but never publish
    # standalone font files with the repository. Font changes may affect
    # layout and the generated PDF's SHA-256.
    import os
    font_candidates=[
        Path(os.environ["DESIGNTEORI_TTF_FONT"]) if os.environ.get("DESIGNTEORI_TTF_FONT") else None,
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    ]
    font=next((p for p in font_candidates if p is not None and p.is_file()),None)
    if font is None:
        raise FileNotFoundError("Set DESIGNTEORI_TTF_FONT to a locally installed Unicode TTF.")
    pdfmetrics.registerFont(TTFont("Designteori-Arial",str(font)))
    body = ParagraphStyle("body",fontName="Designteori-Arial",fontSize=9.4,
                          leading=13.1,spaceAfter=7,allowWidows=0,allowOrphans=0)
    small = ParagraphStyle("small",parent=body,fontSize=8.3,leading=11.3,
                           textColor="#555555")
    h1 = ParagraphStyle("title",parent=body,fontSize=17,leading=22,
                        spaceAfter=10)
    h2 = ParagraphStyle("page",parent=small,fontSize=9.5,leading=12,
                        spaceBefore=13,spaceAfter=8)
    destination.parent.mkdir(parents=True,exist_ok=True)
    doc=SimpleDocTemplate(str(destination),pagesize=A4,
                          leftMargin=20*mm,rightMargin=20*mm,
                          topMargin=19*mm,bottomMargin=19*mm,
                          title=title+" (tekstutgåve utan figurar)",
                          author="; ".join(authors),
                          subject="Tekstadaptasjon av CC BY 4.0-artikkel utan tredjepartsmateriale")
    items=[
        Paragraph(escape(title),h1),
        Paragraph(escape("; ".join(authors)),body),
        Paragraph(escape(f"Publiseringsår: {year} | DOI: {doi}"),small),
        Paragraph(escape("Originalutgåve: "+original_url),small),
        Paragraph(escape("Lisens for sjølve artikkelteksten: CC BY 4.0 "+license_url),small),
        Spacer(1,7*mm),
        Paragraph(escape("Tilpassa tekstutgåve: grafikk, fotografi, figurar og eventuelt tredjepartsmateriale er utelatne. Linjedeling og sidetilpassing er endra. Opphavleg PDF-side er markert for kjeldekontroll. Ikkje bruk denne utgåva til å sitere sidetal utan å kontrollere originalen."),small),
        Spacer(1,5*mm),
        HRFlowable(width="100%",thickness=.6,color="#666666"),
    ]
    for i,raw in enumerate(pages,1):
        items.append(Paragraph(f"Original PDF-side {i}",h2))
        # Remove control chars not representable in PDF; preserve the article's
        # readable Unicode wording, subject to text-extraction limitations.
        raw="".join(c for c in raw if c=="\n" or c=="\t" or ord(c)>=32)
        chunks = re.split(r"\n\s*\n",raw)
        if len(chunks)<2:
            # Many PDFs use single linebreaks for layout; reflow them.
            chunks=re.split(r"(?<=\.)\s{2,}",raw)
        for chunk in chunks:
            chunk=re.sub(r"\s+"," ",chunk).strip()
            if not chunk:continue
            # Limit extremely long flowable paragraphs for reliable ReportLab
            # splitting and screen-reader traversal.
            while len(chunk)>4500:
                boundary=chunk.rfind(" ",2200,4400)
                if boundary<1200:boundary=4400
                segment,chunk=chunk[:boundary],chunk[boundary:].lstrip()
                items.append(Paragraph(escape(segment),body))
            if chunk:
                items.append(Paragraph(escape(chunk),body))
    def footer(canvas, pdf):
        canvas.saveState()
        canvas.setFont("Designteori-Arial",7)
        canvas.drawString(20*mm,12*mm,
            "Artikkeltekst (CC BY 4.0), illustrasjonar utelatne. Kontrollér originalutgåva.")
        canvas.drawRightString(A4[0]-20*mm,12*mm,str(pdf.page))
        canvas.restoreState()
    doc.build(items,onFirstPage=footer,onLaterPages=footer)

    import fitz
    with fitz.open(destination) as ready:
        if not ready.page_count:raise RuntimeError("Empty text PDF")
        if any(ready[i].get_images(full=True) for i in range(ready.page_count)):
            raise RuntimeError("Text-only derivative unexpectedly includes embedded images")
        extracted="".join(ready[i].get_text() for i in range(ready.page_count))
        if len(extracted)<sum(len(x) for x in pages)*0.70:
            raise RuntimeError("Derived PDF lost too much extractable text")
