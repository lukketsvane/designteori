"""Stratifisert trekk til grensekodeark: 200 inne og 200 ute, fast frø.

Berre lesing av databasane (read-only SQLite URI og JSON).
Strata: inngangsrute (4 inne, 4 ute) x periode (3) x slag (3).
50 verk per rute, fordelt over cellene etter storleik (Hare-Niemeyer / største rest, minst eitt per ikkje-tom celle).
Kodarane får arka utan inne/ute og utan ruteinformasjon.

Genererer i docs/validering/grensa/:
- kodeark_kodar_A.csv (400 rader + overskrift, frø 20261114)
- kodeark_kodar_B.csv (same 400 rader, ulik rekkjefølgje, frø 20261115)
- nokkel_IKKJE_TIL_KODARAR.csv (400 rader + overskrift, vekter summerer til 26 425.0)
- kodar-rettleiing.md (rettleiing for kodarane)
- ut/g02.json (samandragsdata for trekket)
"""
from __future__ import annotations

import csv
import html
import json
import os
import pathlib
import re
import sqlite3
import sys
from collections import Counter, defaultdict

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "nordic_design_research.sqlite"
ADD = ROOT / "docs" / "data" / "nordic_additions.json"
OUT_DIR = ROOT / "docs" / "validering" / "grensa"

SEED = 20261113
PER_RUTE = 50

ROUTE_OA = {
    "Dedicated design theory and research venue": ("inne", "OA tidsskriftliste"),
    "Explicit design theory or design research title": ("inne", "OA tittelord"),
    "Core OpenAlex design research topic and title": ("inne", "OA emne og tittel"),
    "Excluded non-design academic subfield": ("ute", "ute: anna fagfelt"),
    "Outside strict design theory and design research scope": ("ute", "ute: utanfor tittelord"),
    "Excluded non-design domain or methodology term": ("ute", "ute: domene- eller metodeord"),
    "Below Google EmbeddingGemma design-theory semantic threshold": ("ute", "ute: under semantisk terskel"),
}

RETTLEIING_TEKST = """# Rettleiing til kodarane: er verket designforsking?

Du får eit ark med 400 verk (fil `kodeark_kodar_A.csv` eller `kodeark_kodar_B.csv`). Fyll ut éi kolonne, `design_research`, med **yes**, **no** eller **unclear**. Du veit ikkje om verket er med i korpuset eller ikkje, og det skal du ikkje prøve å finne ut. Kolonnen `merknad` er valfri.

## Spørsmålet

Ut frå tittel, kanal og samandrag: **er verket ei undersøking av design, eller gjort med design som metode?** Med design meiner vi å utforme eller forme artefaktar, tenester, system, rom eller praksisar med vilje, og kunnskapen om slik utforming.

- **yes**: design (utforminga, praksisen, teorien, metodane, utdanninga, historia eller dei utforma tinga) er sjølve emnet for verket, eller verket bruker design som metode for å finne noko ut. Døme på kva som tel: ein studie av korleis designarbeid går føre seg, ein designhistorisk studie, eit prosjekt der ein utformar og testar eit prototypesett for å lære noko, ein tekst om undervisning i design.
- **no**: verket brukar ordet design i ein annan tyding (til dømes studiedesign, forskingsdesign, utforming av ein algoritme, krins eller medisin), eller emnet ligg utanfor design (til dømes klinisk forsking, reint teknisk utvikling utan spørsmål om utforming, forvaltning). Eit verk som berre nemner design i forbifarten er **no**.
- **unclear**: du kan ikkje avgjere ut frå det du har. Bruk det når tittelen og samandraget ikkje rekk, ikkje som standard for vanskelege tilfelle. Skriv gjerne kvifor i `merknad`.

## Slik går du fram

1. Les tittel, kanal og år i arket. Opne lenkja i `abstract_link` og les samandraget. Les ikkje heile teksten. Er lenkja død, kode ut frå tittel og kanal, og skriv «lenkje feil» i `merknad`.
2. Bruk høgst tre minutt per verk.
3. Døm det verket seier om seg sjølv, ikkje kor godt det er, kor mykje det er sitert eller kva du trur om kanalen. Det er ikkje ei vurdering av feltet eller av forfattarane.
4. Kode åleine og i same rekkjefølgje som i arket ditt. Ikkje snakk med den andre kodaren om einskildverk før begge er ferdige.
5. Ikkje søk opp verket i andre kjelder for å sjå om det «er med» eller «ikkje er med» i ei samling.
6. Ein del verk står utan kanalnamn (29 av 400), og to titlar kan stå to gonger. Kode dei som vanleg.

## Kva som skjer med koden

Arka er trekte med fast frø (20261113) og stratifiserte på inngangsrute, periode og slag, 50 verk per rute. Delen yes i arket er difor ikkje delen i korpuset. Prosjektet har ein eigen nøkkel med vekter som blir brukt først etter at begge kodar er ferdige. Etterpå reknar vi samsvar mellom kodarane (kappa og del like svar, med unclear som eiga kategori) og vektar delen yes for dei som kom inn og dei som blei haldne ute. Verk der kodarane er ueinige går til ei tredje lesing.
"""


def clean(t: any) -> str:
    t = html.unescape(str(t or ""))
    t = re.sub(r"<[^>]+>", "", t)
    return re.sub(r"\s+", " ", t).strip()


def kgroup(k: str | None) -> str:
    k = (k or "").lower()
    if k in ("article", "journal-article"):
        return "artikkel"
    if k in ("conference-paper", "proceedings-article", "conference-abstract"):
        return "konferanse"
    return "anna eller ukjend"


def pgroup(y: any) -> str:
    try:
        y = int(y)
    except Exception:
        return "ukjend år"
    return "før 2010" if y < 2010 else ("2010-2019" if y < 2020 else "2020 og seinare")


def generer_grensekodeark(out_dir: pathlib.Path = OUT_DIR) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(out_dir / "ut", exist_ok=True)

    pop = []
    # Read-only connect to prevent any accidental write
    c = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    for wid, doi, title, year, kind, source, decision, in_scope in c.execute(
        "select id,doi,title,year,kind,source,decision,in_scope from works"
    ):
        if decision not in ROUTE_OA or not clean(title):
            continue
        side, route = ROUTE_OA[decision]
        link = doi if (doi or "").startswith("http") else ("https://doi.org/" + doi if doi else "https://openalex.org/" + wid)
        pop.append(
            dict(
                id=wid,
                title=clean(title),
                venue=clean(source),
                year=year,
                link=link,
                side=side,
                route=route,
                per=pgroup(year),
                kg=kgroup(kind),
                kind_raw=kind,
            )
        )
    c.close()

    add = json.load(open(ADD, encoding="utf-8"))
    n_dup_arkiv = 0
    for a in add:
        if a.get("duplicate_status") != "new-candidate":
            n_dup_arkiv += 1
            continue
        pop.append(
            dict(
                id=a["id"],
                title=clean(a["title"]),
                venue=clean(a.get("venue") or a.get("source")),
                year=a.get("year"),
                link=a.get("source_url") or a.get("oa_url") or "",
                side="inne",
                route="arkivlaget (utan moglege dublettar)",
                per=pgroup(a.get("year")),
                kg=kgroup(a.get("kind")),
                kind_raw=a.get("kind"),
            )
        )

    print(
        "populasjon:",
        len(pop),
        "inne",
        sum(1 for p in pop if p["side"] == "inne"),
        "ute",
        sum(1 for p in pop if p["side"] == "ute"),
        "| arkivpostar utelatne som moglege dublettar:",
        n_dup_arkiv,
    )

    rng = np.random.default_rng(SEED)
    cells = defaultdict(list)
    for p in pop:
        cells[(p["side"], p["route"], p["per"], p["kg"])].append(p)

    routes = sorted({(p["side"], p["route"]) for p in pop})
    sample = []
    alloc_log = []

    for side, route in routes:
        ck = sorted(k for k in cells if k[0] == side and k[1] == route)
        sizes = np.array([len(cells[k]) for k in ck], float)
        tot = sizes.sum()
        base = np.maximum(1, np.floor(PER_RUTE * sizes / tot)).astype(int)
        base = np.minimum(base, sizes.astype(int))
        # Largest remainder method (Hare-Niemeyer)
        frac = PER_RUTE * sizes / tot - base
        while base.sum() < PER_RUTE:
            cand = [i for i in np.argsort(-frac) if base[i] < sizes[i]]
            base[cand[0]] += 1
            frac[cand[0]] -= 1
        while base.sum() > PER_RUTE:
            cand = [i for i in np.argsort(frac) if base[i] > 1]
            base[cand[0]] -= 1
            frac[cand[0]] += 1

        for k, nk in zip(ck, base):
            pool = cells[k]
            idx = rng.choice(len(pool), size=int(nk), replace=False)
            for i in idx:
                p = dict(pool[i])
                p["cell_N"] = len(pool)
                p["cell_n"] = int(nk)
                p["weight"] = round(len(pool) / int(nk), 4)
                sample.append(p)
            alloc_log.append(dict(side=side, route=route, periode=k[2], slag=k[3], N=len(pool), n=int(nk)))

    print("trekk:", len(sample), Counter(p["side"] for p in sample), Counter(p["route"] for p in sample))
    for side, route in routes:
        ws = sum(p["weight"] for p in sample if p["route"] == route)
        print("  %-40s N=%6d  sum vekter=%.1f" % (route, sum(1 for p in pop if p["route"] == route), ws))

    assert len({p["id"] for p in sample}) == len(sample)

    tc = Counter(re.sub(r"\W+", " ", p["title"].lower()).strip() for p in sample)
    dups = [t for t, n in tc.items() if n > 1]
    print("titlar som står fleire gonger i trekket:", len(dups))

    cols = ["id", "title", "venue", "year", "abstract_link", "design_research", "merknad"]

    def write_sheet(path: pathlib.Path, order: np.ndarray) -> None:
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f, delimiter=",", quoting=csv.QUOTE_MINIMAL)
            w.writerow(cols)
            for i in order:
                p = sample[i]
                w.writerow([p["id"], p["title"], p["venue"], p["year"], p["link"], "", ""])

    rng_a = np.random.default_rng(SEED + 1)
    rng_b = np.random.default_rng(SEED + 2)

    path_a = out_dir / "kodeark_kodar_A.csv"
    path_b = out_dir / "kodeark_kodar_B.csv"
    path_key = out_dir / "nokkel_IKKJE_TIL_KODARAR.csv"
    path_guide = out_dir / "kodar-rettleiing.md"

    write_sheet(path_a, rng_a.permutation(len(sample)))
    write_sheet(path_b, rng_b.permutation(len(sample)))

    with open(path_key, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "inne_ute", "rute", "periode", "slag", "kjelde_slag_raa", "celle_N", "celle_n", "vekt"])
        for p in sample:
            w.writerow(
                [
                    p["id"],
                    p["side"],
                    p["route"],
                    p["per"],
                    p["kg"],
                    p["kind_raw"],
                    p["cell_N"],
                    p["cell_n"],
                    p["weight"],
                ]
            )

    path_guide.write_text(RETTLEIING_TEKST, encoding="utf-8")

    nolink = sum(1 for p in sample if not p["link"])
    noven = sum(1 for p in sample if not p["venue"])
    print("utan lenkje:", nolink, "utan kanalnamn:", noven)

    summary = {
        "seed": SEED,
        "per_rute": PER_RUTE,
        "populasjon_n": len(pop),
        "arkiv_utelatne_dublettar": n_dup_arkiv,
        "trekk_n": len(sample),
        "celler": alloc_log,
        "utan_lenkje": nolink,
        "utan_kanalnamn": noven,
        "rute_N": {r: sum(1 for p in pop if p["route"] == r) for _, r in routes},
    }

    json.dump(summary, open(out_dir / "ut" / "g02.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(summary, open(out_dir / "g02.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    return summary


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    generer_grensekodeark()


if __name__ == "__main__":
    main()
