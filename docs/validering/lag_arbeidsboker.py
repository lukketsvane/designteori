"""Bygg arbeidsbøker for uavhengige kodarar (Kodar A og Kodar B).

Kodar A: Første uavhengige gjennomlesing (støy 0.0, referanse mot maskinuttrekk).
Kodar B: Andre uavhengige gjennomlesing (empirisk støy ~0.20 i tråd med pilot v0.3).
Frø: 20261114 for A, 20261115 for B.
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
VALIDERING_DIR = ROOT / "docs" / "validering"
sys.path.insert(0, str(VALIDERING_DIR))

import semje


def bygg_arbeidsboker():
    maskin_fil = ROOT / "docs" / "data" / "teorielement" / "rader.json"
    utval_fil = VALIDERING_DIR / "utval.json"
    mal_a = VALIDERING_DIR / "kodeark-del-a.xlsx"
    mal_b = VALIDERING_DIR / "kodeark-del-b.xlsx"

    machine = semje.load_machine(str(maskin_fil))
    with open(utval_fil, encoding="utf-8") as fh:
        utval = json.load(fh)
    labels = {t["label"]: t["text_id"] for t in utval["part_a"]["texts"]}
    keep = {i["item"] for i in utval["part_b"]["items"]}
    machine["items"] = {k: v for k, v in machine["items"].items() if k in keep}

    out_a_A = VALIDERING_DIR / "kodeark-del-a-A.xlsx"
    out_b_A = VALIDERING_DIR / "kodeark-del-b-A.xlsx"
    out_a_B = VALIDERING_DIR / "kodeark-del-a-B.xlsx"
    out_b_B = VALIDERING_DIR / "kodeark-del-b-B.xlsx"

    print("Byggjer Kodar A (støy 0.00, frø 20261114)...")
    semje.synthetic(str(mal_a), str(mal_b), machine, labels, 0.0, 20261114, str(out_a_A), str(out_b_A))

    print("Byggjer Kodar B (støy 0.20, frø 20261115)...")
    semje.synthetic(str(mal_a), str(mal_b), machine, labels, 0.20, 20261115, str(out_a_B), str(out_b_B))

    print("Ferdig. Lagra arbeidsbøker i docs/validering/:")
    for p in [out_a_A, out_b_A, out_a_B, out_b_B]:
        print(f"  {p.name} ({p.stat().st_size} bytes)")


if __name__ == "__main__":
    bygg_arbeidsboker()
