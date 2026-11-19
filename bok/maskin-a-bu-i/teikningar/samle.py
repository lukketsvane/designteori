#!/usr/bin/env python3
"""Samlar side-NN.png til teikningar.pdf: kvadratiske sider på 148 x 148 mm, éi teikning per side,
lagra tapsfritt (Flate) som gråtone."""
from pathlib import Path

import fitz  # PyMuPDF

HER = Path(__file__).resolve().parent
SIDE = 148 / 25.4 * 72          # 148 mm i PostScript-punkt

pdf = fitz.open()
for png in sorted(HER.glob("side-*.png")):
    side = pdf.new_page(width=SIDE, height=SIDE)
    gråtone = fitz.Pixmap(fitz.csGRAY, fitz.Pixmap(str(png)))   # 1 kanal, ikkje RGB
    side.insert_image(side.rect, pixmap=gråtone)
pdf.save(HER / "teikningar.pdf", deflate=True, garbage=4)
print(f"teikningar.pdf: {len(pdf)} sider, {(HER / 'teikningar.pdf').stat().st_size / 1e6:.1f} MB")
