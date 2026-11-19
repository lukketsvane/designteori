#!/usr/bin/env python3
"""Byggjer «Maskin å bu i» (og AHO_A/B/C) til ein kvadratisk PDF (148 x 148 mm, kvit tekst på svart).

Typografisk system:
- Éi skriftfamilie: DIN (Bahnschrift), den tyske industristandarden for skilt, maskinplater og
  teknisk teikning, i smal breidd (75 %). Le Corbusier-røysta (mono-partia i manuset) står i
  lett vekt. *Kursiv* vert halvfeit.
- Tett, nær klaustrofobisk vegg: lik marg (7 mm) på alle fire kantar, éin skriftstorleik for heile
  teksten, tett linjeavstand, justert kant til kant med font expansion (LuaLaTeX/microtype), aldri
  orddeling.
- Skriftstorleiken vert vald automatisk: skriptet prøver storleikar rundt MÅL_STORLEIK og vel den
  der teksten fyller eit heilt tal sider nøyaktig, så òg siste side er full; nærast målet vinn
  (jamnast tekstur), og eit fireartal sider er verdt om lag 4 % avvik.
- Eksakt rutenett: linjeavstanden vert rekna slik at kapitalhøgda står på toppmargen og siste
  grunnlinje på botnmargen.
- Struktur i dempa grått: «/» for linjeskift i vers, «//» for strofe- og avsnittsskil (MERKE).

Bruk:   python bygg.py              (manus.md  -> maskin-a-bu-i.pdf)
        python bygg.py AHO_A.md     (AHO_A.md  -> AHO_A.pdf)
Krev:   lualatex (MiKTeX eller TeX Live) med memoir, fontspec, babel (nynorsk), xcolor, microtype,
        og Bahnschrift (følgjer med Windows 10/11). Mellomfiler hamnar i bygg/.
"""
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

HER = Path(__file__).resolve().parent
MANUS = HER / "manus.md"
UT = HER / "bygg"
NAMN = "maskin-a-bu-i"

SATS = 379.84          # tekstflata: 134 x 134 mm i punkt (7 mm marg rundt på ei 148 mm side)
LINJE = 1.06           # ønskt linjeavstand i forhold til skriftstorleiken
LINJE_MIN, LINJE_MAKS = 1.02, 1.12   # grenser når linjeavstanden vert finjustert til rutenettet
MÅL_STORLEIK = 21.0    # skriftstorleiken vert vald nær dette (pt)
SPENN = 0.20           # søk innanfor ±20 % av MÅL_STORLEIK
STEG = 0.04            # i steg på 0,04 pt
MERKE = True           # «/» og «//» i grått for linjeskift og strofeskil

PREAMBEL = r"""
\documentclass[10pt,twoside]{memoir}
% Kvadratisk bok: 148 x 148 mm ferdig skoren, 3 mm utfallande kant (PDF-sida er 154 x 154 mm).
% Lik marg på alle fire kantar: 7 mm. Tekstflata er 134 x 134 mm.
\setstocksize{154mm}{154mm}
\settrimmedsize{148mm}{148mm}{*}
\settrims{3mm}{3mm}
\settypeblocksize{134mm}{134mm}{*}
\setlrmargins{7mm}{*}{*}
\setulmargins{7mm}{*}{*}
\setheadfoot{1pt}{1pt}
\setheaderspaces{*}{2pt}{*}
\checkandfixthelayout
% Skjerekant og utfallande kant for trykkeriet (i PostScript-punkt).
\pdfvariable pageattr{/TrimBox [8.504 8.504 428.031 428.031] /BleedBox [0 0 436.535 436.535]}

% 100 % svart på alle sider, kvit tekst; strukturmerka i dempa grått.
\usepackage{xcolor}
\pagecolor{black}
\color{white}
\definecolor{merke}{gray}{0.42}

\usepackage{fontspec}
\usepackage[nynorsk]{babel}
% DIN (Bahnschrift) som variabel skrift: breidd (wdth) og vekt (wght).
% Le Corbusier-røysta (cor) har same breidd, men lett vekt, så gråtonen held seg jamn.
\newfontfamily\hovudfamilie{bahnschrift.ttf}[RawFeature={axis={wdth=75,wght=400}}]
\newfontfamily\sterkfamilie{bahnschrift.ttf}[RawFeature={axis={wdth=75,wght=650}}]
\newfontfamily\corfamilie{bahnschrift.ttf}[RawFeature={axis={wdth=75,wght=300}}]
\newfontfamily\sterkcorfamilie{bahnschrift.ttf}[RawFeature={axis={wdth=75,wght=600}}]
\usepackage[protrusion=true,expansion=true,stretch=30,shrink=30,step=5]{microtype}

\pagestyle{empty}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0pt}
\frenchspacing
\hyphenpenalty=10000 \exhyphenpenalty=10000   % aldri orddeling
\tolerance=10000 \emergencystretch=3em
\clubpenalty=0 \widowpenalty=0 \interlinepenalty=0 \brokenpenalty=0
\lineskiplimit=-\maxdimen
\hbadness=10000 \vbadness=10000 \hfuzz=1pt
\flushbottom

\newdimen\fs \fs=20pt
\newcommand\storleik{\fontsize{\the\fs}{\the\dimexpr1.06\fs\relax}\selectfont}
\newcommand\hovud{\hovudfamilie\storleik}
\newcommand\cor{\corfamilie\storleik}
\newcommand\sterk[1]{{\sterkfamilie\storleik #1}}
\newcommand\sterkcor[1]{{\sterkcorfamilie\storleik #1}}
\newcommand\merkelinje{\textcolor{merke}{/}}
\newcommand\merkestrofe{\textcolor{merke}{//}}
\newcommand\blokkoppsett{\noindent\parfillskip=0pt\relax}
"""

TEX_TEIKN = {
    "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
    "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
}


def tex(s: str) -> str:
    return "".join(TEX_TEIKN.get(c, c) for c in s)


def tolk_manus(md: str) -> list:
    """Gjer manuset om til einingar (strofer/avsnitt) med linjer og røyst (hovud eller cor)."""
    einingar, blokk = [], []
    modus, i_kommentar = "vers", False

    def tøm():
        nonlocal blokk
        if blokk:
            linjer = [" ".join(blokk)] if modus == "prosa" else list(blokk)
            einingar.append({"linjer": linjer, "cor": modus == "mono"})
        blokk = []

    for rå in md.splitlines():
        s = rå.strip()
        if i_kommentar:
            i_kommentar = s != "-->"
            continue
        if s == "<!--":
            i_kommentar = True
            continue
        d = re.fullmatch(r"<!--\s*(.*?)\s*-->", s)
        if d:
            tøm()
            if d.group(1) in ("vers", "prosa", "mono"):
                modus = d.group(1)
        elif s == "---" or not s:
            tøm()
        else:
            blokk.append(s)
    tøm()
    return einingar


def lag_tekst(einingar: list) -> str:
    """Heile teksten som éin justert blokk. Merka heng saman med ordet før, så ingen linje byrjar med «/»."""
    deler = []
    for ui, e in enumerate(einingar):
        linjer = []
        for linje in e["linjer"]:
            t = tex(linje)
            t = re.sub(r"\*([^*]+)\*", (r"\\sterkcor{\1}" if e["cor"] else r"\\sterk{\1}"), t)
            linjer.append(t)
        skil = r"~\merkelinje{} " if MERKE else " "
        innhald = skil.join(linjer)
        if e["cor"]:
            innhald = r"{\cor %s}" % innhald
        if ui > 0:
            deler.append(r"~\merkestrofe{} " if MERKE else " ")
        deler.append(innhald)
    return "".join(deler)


def køyr(namn: str) -> str:
    r = subprocess.run(
        ["lualatex", "-interaction=nonstopmode", "-halt-on-error", f"{namn}.tex"],
        cwd=UT, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if r.returncode != 0:
        print(r.stdout[-4000:])
        sys.exit(f"lualatex feila; sjå bygg/{namn}.log")
    return r.stdout


def skann(tekst: str, namn: str) -> list:
    """Set heile teksten ved mange storleikar; skriv linjetal og kapitalhøgd for kvar."""
    aux = "skann" + re.sub(r"[^A-Za-z0-9]", "", namn)
    lo, hi = MÅL_STORLEIK * (1 - SPENN), MÅL_STORLEIK * (1 + SPENN)
    storleikar = [round(lo + i * STEG, 2) for i in range(int((hi - lo) / STEG) + 1)]
    kropp = [
        r"\begin{document}",
        r"\newwrite\ut \immediate\openout\ut=%s.dat" % aux,
        r"\long\def\TEKST{%s}" % tekst,
        r"\newcount\linjetal \newdimen\kapphogd \newcount\laus \newcount\einsleg \newcount\nr",
        # Laus linje: naturleg breidd under 86 % av satsbreidda (store hol når ho vert justert).
        # Einsleg: linja har berre eitt ord og kan ikkje justerast (badness 10000).
        r"\newcommand\proev[1]{\fs=#1pt"
        r"\setbox0=\vbox{\hsize=\textwidth\hovud\blokkoppsett\TEKST\par\global\linjetal=\prevgraf"
        r"\global\laus=0 \global\einsleg=0 \global\nr=0"
        r"\loop\unskip\unpenalty\unskip\setbox2=\lastbox\ifvoid2\else\global\advance\nr by 1 "
        r"\ifnum\nr>1 \setbox4=\hbox{\unhcopy2}\ifdim\wd4<0.86\wd2 \global\advance\laus by 1 \fi"
        r"\setbox4=\hbox to \wd2{\unhcopy2}\ifnum\badness>9999 \global\advance\einsleg by 1 \fi\fi\repeat}"
        r"\setbox2=\hbox{\hovud ÅÊÉÈ/}\kapphogd=\ht2"
        r"\immediate\write\ut{#1 \the\linjetal\space\the\kapphogd\space\the\laus\space\the\einsleg}}",
        *[r"\proev{%.2f}" % s for s in storleikar],
        r"\immediate\closeout\ut",
        r"\end{document}", "",
    ]
    (UT / f"{aux}.tex").write_text(PREAMBEL + "\n".join(kropp), encoding="utf-8")
    køyr(aux)
    ut = []
    for linje in (UT / f"{aux}.dat").read_text(encoding="utf-8").splitlines():
        s, n, h, laus, einsleg = linje.split()
        ut.append((float(s), int(n), float(h.removesuffix("pt")), int(laus), int(einsleg)))
    return ut


def vel_storleik(målingar: list):
    """Vel storleiken der teksten fyller heile sider, med jamnast tekstur (færrast laust sette linjer),
    nær MÅL_STORLEIK og helst eit fireartal sider."""
    kandidatar = []
    for s, linjer, kapp, laus, einsleg in målingar:
        topp = kapp + 0.02 * s                       # litt rom over aksentar (Å, Ê)
        avstand = abs(s - MÅL_STORLEIK) / MÅL_STORLEIK
        # Linjeavstanden kan variere mellom 1,02 og 1,12 x skrifta; kvar verdi gjev eit linjetal per side.
        n_lo = math.floor((SATS - topp) / (LINJE_MAKS * s)) + 1
        n_hi = math.floor((SATS - topp) / (LINJE_MIN * s)) + 1
        for per_side in range(max(2, n_lo), n_hi + 1):
            lead = (SATS - topp) / (per_side - 1)
            if not LINJE_MIN * s <= lead <= LINJE_MAKS * s:
                continue
            sider = math.ceil(linjer / per_side)
            fylt = (linjer - (sider - 1) * per_side) / per_side
            # Full siste side først; så jamn tekstur (del laust sette linjer), nærleik til målet,
            # linjeavstand nær LINJE og eit lite plussord for eit fireartal sider.
            straff = (einsleg + laus / linjer + 0.5 * avstand + 0.5 * abs(lead / s - LINJE)
                      + (0 if sider % 4 == 0 else 0.02))
            kandidatar.append(((0 if fylt == 1 else 1, straff, -fylt), s, per_side, sider, topp, linjer))
    _, s, per_side, sider, topp, linjer = min(kandidatar)
    lead = (SATS - topp) / (per_side - 1) - 0.01
    return s, per_side, sider, topp, lead, linjer


def main():
    UT.mkdir(exist_ok=True)
    manus = (Path.cwd() / sys.argv[1]).resolve() if len(sys.argv) > 1 else MANUS
    namn = manus.stem if len(sys.argv) > 1 else NAMN
    tekst = lag_tekst(tolk_manus(manus.read_text(encoding="utf-8")))

    s, per_side, sider, topp, lead, linjer = vel_storleik(skann(tekst, namn))
    kropp = [
        r"\begin{document}",
        r"\fs=%.2fpt \topskip=%.3fpt \setlength\maxdepth{%.3fpt}" % (s, topp, 0.35 * s),
        r"{\hovud\baselineskip=%.4fpt\relax\blokkoppsett %s\par}" % (lead, tekst),
        r"\end{document}", "",
    ]
    (UT / f"{namn}.tex").write_text(PREAMBEL + "\n".join(kropp), encoding="utf-8")
    logg = køyr(namn)
    shutil.copy(UT / f"{namn}.pdf", HER / f"{namn}.pdf")
    m = re.search(r"Output written on .*?\((\d+)\s+pages?", logg, re.S)
    print(f"{namn}.pdf: {m.group(1) if m else '?'} sider (venta {sider}), {s:.2f} pt, "
          f"{per_side} linjer per side, {linjer} linjer i alt, linjeavstand {lead:.2f} pt")


if __name__ == "__main__":
    main()
