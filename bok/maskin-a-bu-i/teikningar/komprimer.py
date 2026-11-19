#!/usr/bin/env python3
"""Flyttar dei fulle RGB-originalane til original/ (ikkje i git) og skriv side-NN.png som gråtone med
16 nivå: same strek og kantutjamning for tusjteikningar, om lag ein firedel av storleiken.

Bruk:   python komprimer.py         (sidene i denne mappa)
        python komprimer.py v2      (sidene i v2/)
"""
import shutil
import sys
from pathlib import Path

from PIL import Image

MAPPE = Path(__file__).resolve().parent / (sys.argv[1] if len(sys.argv) > 1 else "")
ORIGINAL = MAPPE / "original"
ORIGINAL.mkdir(exist_ok=True)

for side in sorted(MAPPE.glob("side-*.png")):
    with Image.open(side) as im:
        if im.mode == "P":
            continue                                   # alt komprimert
        im.load()
    shutil.copy2(side, ORIGINAL / side.name)
    im.convert("L").quantize(16, method=Image.Quantize.MEDIANCUT).save(side, optimize=True)
    print(f"{side.name}: {side.stat().st_size // 1024} KB")
