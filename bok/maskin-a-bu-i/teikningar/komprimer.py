#!/usr/bin/env python3
"""Flyttar dei fulle RGB-originalane til original/ (ikkje i git) og skriv side-NN.png som gråtone med
16 nivå: same strek og kantutjamning for tusjteikningar, om lag ein firedel av storleiken."""
import shutil
from pathlib import Path

from PIL import Image

HER = Path(__file__).resolve().parent
ORIGINAL = HER / "original"
ORIGINAL.mkdir(exist_ok=True)

for side in sorted(HER.glob("side-*.png")):
    with Image.open(side) as im:
        if im.mode == "P":
            continue                                   # alt komprimert
        im.load()
    shutil.copy2(side, ORIGINAL / side.name)
    im.convert("L").quantize(16, method=Image.Quantize.MEDIANCUT).save(side, optimize=True)
    print(f"{side.name}: {side.stat().st_size // 1024} KB")
