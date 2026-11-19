#!/usr/bin/env python3
"""Samlar side-NN.png til teikningar.pdf (148 x 148 mm, tapsfri gråtone) og teikningar-lett.pdf
(1200 punkt JPEG, liten nok for mobilen).

Bruk:   python samle.py         (sidene i denne mappa)
        python samle.py v2      (sidene i v2/)
"""
import io
import sys
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image

MAPPE = Path(__file__).resolve().parent / (sys.argv[1] if len(sys.argv) > 1 else "")
SIDE = 148 / 25.4 * 72          # 148 mm i PostScript-punkt
sider = sorted(MAPPE.glob("side-*.png"))

full, lett = fitz.open(), fitz.open()
for png in sider:
    gråtone = fitz.Pixmap(fitz.csGRAY, fitz.Pixmap(str(png)))   # 1 kanal, ikkje RGB
    full.new_page(width=SIDE, height=SIDE).insert_image(fitz.Rect(0, 0, SIDE, SIDE), pixmap=gråtone)
    b = io.BytesIO()
    Image.open(png).convert("L").resize((1200, 1200), Image.LANCZOS).save(b, "JPEG", quality=80)
    lett.new_page(width=SIDE, height=SIDE).insert_image(fitz.Rect(0, 0, SIDE, SIDE), stream=b.getvalue())
for namn, pdf in (("teikningar.pdf", full), ("teikningar-lett.pdf", lett)):
    pdf.save(MAPPE / namn, deflate=True, garbage=4)
    print(f"{namn}: {len(pdf)} sider, {(MAPPE / namn).stat().st_size / 2**20:.1f} MiB")
