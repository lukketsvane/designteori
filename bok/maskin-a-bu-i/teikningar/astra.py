#!/usr/bin/env python3
"""Andre runde av teikningane til «MASKINA Å BU I»: speculative drawing gjennom gpt-6.2-astra.

GPT-6.2 Astra (reasoning effort max) les tekstdelen og dei seks stilreferansesidene frå Töpfers
«Speculative Drawing» (sd_pNNN.png i OpenAI Files), tenkjer ut tankediagram i den stilen og kallar
image_generation-verktøyet med gpt-image-2.6-sunburst, quality max, 1920 x 1920 (1:1).

Bruk:   python astra.py 1              (berre side 1)
        python astra.py 2-46 -j 3      (fleire om gongen)
Resultat: v2/side-NN.png, prompten Astra skreiv i v2/side-NN.txt, kostnad i v2/logg.txt.
"""
import argparse
import base64
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from sider import SIDER

HER = Path(__file__).resolve().parent
UT = HER / "v2"
BASE = "https://api.openai.com/v1"
MODELL = "gpt-6.2-astra"
VERKTØY = {"type": "image_generation", "model": "gpt-image-2.6-sunburst", "quality": "max",
           "size": "1920x1920", "background": "opaque", "output_format": "png"}
REFS = {
    "middels": "206 153 067 066 269 043",
    "lite": "206 207 153 269 043 067",
    "mykje": "066 067 269 043 014 268",
}
USD = {"inn": 8, "inn_cache": 0.4, "ut": 40}        # gpt-6.2-astra per 1M token
BILETE_USD = 0.46                                   # målt per side med sunburst, quality max, 1920^2
LÅS = threading.Lock()

INSTRUKS = """du skal illustrere vedlagt tekst. heile saken del for del. gjer det eksakt i denne stilen med topfer speculative drawing. ei side etter den andre til me har dekt det tekstlege innhaldet.

Du er teiknaren. Dei vedlagde bileta er sider frå Andreas Töpfer, «Speculative Drawing». Studer dei nøye før du teiknar: dette er tenkjande teikningar, ikkje illustrasjonar. Ein gjenstand glir over i eit omgrep (ein blyant der streken løyser seg opp i løkker og vert ein hund), ei form vert eit diagram, omgrep vert små biomorfe kroppar, institusjonar vert organismar med rør og slangar. Streken er svart tusj, litt skjelvande og ujamn, fri hand, med enkle konturar, nesten utan skravur. Teikningane står spreidde på kvitt papir med mykje luft. Merknadene er handskrivne, laust plasserte ved figurane, ofte med bokstavar (A, B, C eller a, b, c) og ei handskriven legende, piler og strekar som peikar.

Gjer slik:
1. Les tekstdelen. Finn dei to til fem tankane eller overgangane i han som ber mest (ikkje gjenfortel handlinga), og tenk ut korleis kvar av dei kan teiknast spekulativt i Töpfers måte: materialet i teksten (stein, kopar, betong, papir, bein, vatn, lyn) skal gå over i det teksten seier om det.
2. Kall image_generation éin gong med ein presis prompt som skildrar sida: kvar figur, kvar han står, kvar merknad står og kva han peikar på.

Krav til sida:
- Kvadratisk side (1:1), kvitt papir, berre svart tusj. Ingen gråtonar, ingen fargar, ingen skuggelegging.
- Handskriven tekst berre ordrett henta frå tekstdelen, i STORE BOKSTAVAR, rett nynorsk med Æ, Ø og Å. Bokstavar som A, B, C til ei legende er lov. Ingen annan tekst: inga engelsk, ingen sidetal, ingen topptekst, ingen namn eller ord frå referansesidene.
- Ikkje kopier motiv, figurar eller oppsett frå referansesidene; berre strek, handskrift og tenkjemåte.
- Ingen kroppar som lid, inga vald, ingen symbol frå krigen; der teksten handlar om leiren, teikn plan, skjema og hender.
"""


def nøkkel() -> str:
    k = os.environ.get("OPENAI_API_KEY")
    if not k and sys.platform == "win32":
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as n:
            k = winreg.QueryValueEx(n, "OPENAI_API_KEY")[0]
    return k


HODE = {"Authorization": f"Bearer {nøkkel()}", "Content-Type": "application/json"}


def api(sti: str, data: dict | None = None) -> dict:
    req = urllib.request.Request(BASE + sti, json.dumps(data).encode() if data else None, HODE)
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode(errors='replace')[:1500]}")


def fil_id() -> dict:
    return {f["filename"]: f["id"] for f in api("/files?purpose=vision")["data"]}


def lag(k: int, n: int, s: dict, ids: dict, effort: str) -> str:
    ut = UT / f"side-{k:02d}.png"
    if ut.exists():
        return f"side {k}: finst alt"
    tekst = f"Side {k} av {n}. Tekstdelen som skal teiknast:\n«{s['tekst']}»"
    innhald = [{"type": "input_text", "text": INSTRUKS + "\n" + tekst}]
    innhald += [{"type": "input_image", "file_id": ids[f"sd_p{nr}.png"], "detail": "high"}
                for nr in REFS[s.get("ref", "middels")].split()]
    svar = api("/responses", {
        "model": MODELL,
        "input": [{"role": "user", "content": innhald}],
        "tools": [VERKTØY],
        "tool_choice": {"type": "image_generation"},
        "reasoning": {"effort": effort},
        "background": True,
        "store": True,
    })
    while svar["status"] in ("queued", "in_progress"):
        time.sleep(10)
        svar = api(f"/responses/{svar['id']}")
    if svar["status"] != "completed":
        raise RuntimeError(f"side {k}: status {svar['status']}: {json.dumps(svar.get('error') or svar.get('incomplete_details'))}")
    bilete = [o for o in svar["output"] if o["type"] == "image_generation_call" and o.get("result")]
    if not bilete:
        raise RuntimeError(f"side {k}: inga bilete i svaret: {json.dumps(svar['output'])[:1500]}")
    ut.write_bytes(base64.b64decode(bilete[0]["result"]))
    (UT / f"side-{k:02d}.txt").write_text(bilete[0].get("revised_prompt") or "", encoding="utf-8")
    u = svar.get("usage") or {}
    cache = (u.get("input_tokens_details") or {}).get("cached_tokens", 0)
    usd = ((u.get("input_tokens", 0) - cache) * USD["inn"] + cache * USD["inn_cache"]
           + u.get("output_tokens", 0) * USD["ut"]) / 1e6 + BILETE_USD
    tenk = (u.get("output_tokens_details") or {}).get("reasoning_tokens", 0)
    melding = (f"side {k}: ok ~${usd:.2f} (inn {u.get('input_tokens')}, ut {u.get('output_tokens')}, "
               f"resonnering {tenk}) {svar['id']}")
    with LÅS:
        with open(UT / "logg.txt", "a", encoding="utf-8") as f:
            f.write(melding + "\n")
        print(melding, flush=True)
    return melding


def main():
    p = argparse.ArgumentParser()
    p.add_argument("sider")
    p.add_argument("-j", type=int, default=1)
    p.add_argument("--effort", default="max")
    a = p.parse_args()
    UT.mkdir(exist_ok=True)
    fra, _, til = a.sider.partition("-")
    nr = range(int(fra), int(til or fra) + 1)
    ids = fil_id()

    def køyr(k):
        try:
            return lag(k, len(SIDER), SIDER[k - 1], ids, a.effort)
        except Exception as e:                                  # noqa: BLE001
            with LÅS:
                print(f"side {k}: FEIL {e}", flush=True)
                with open(UT / "logg.txt", "a", encoding="utf-8") as f:
                    f.write(f"side {k}: FEIL {e}\n")

    with ThreadPoolExecutor(a.j) as ex:
        list(ex.map(køyr, nr))


if __name__ == "__main__":
    main()
