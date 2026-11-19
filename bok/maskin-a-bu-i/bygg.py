#!/usr/bin/env python3
"""Byggjer «Maskin å bu i» frå manus.md til ein kvadratisk PDF (148 x 148 mm, kvit tekst på svart) klar for trykk.

Kvar side vert fylt maksimalt med tekst. Margen er lik på alle fire kantar, og skriftstorleiken
vert tilpassa automatisk side for side:

1. Eit målepass i XeLaTeX måler breidda på kvar verslinje og kvart prosaord.
2. Python deler diktet i sider. Vers fyller sida i den storleiken der den lengste linja går
   kant til kant (og bryt helst ved eit strofeskil). Prosa står éin blokk per side; lange
   avsnitt vert delte så skrifta ikkje går under MIN_PROSA.
3. I sluttpasset finn XeLaTeX den største skriftstorleiken som får plass på kvar side
   (binærsøk), og fordeler resten av lufta mellom strofene.

Bruk:   python bygg.py              (manus.md  -> maskin-a-bu-i.pdf)
        python bygg.py AHO_A.md     (AHO_A.md  -> AHO_A.pdf)
Krev:   xelatex (MiKTeX eller TeX Live) med memoir, fontspec, babel (nynorsk), xcolor
        og Libertinus-skriftene.
Resultat: maskin-a-bu-i.pdf i same mappe. Mellomfiler hamnar i bygg/.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

HER = Path(__file__).resolve().parent
MANUS = HER / "manus.md"
UT = HER / "bygg"
NAMN = "maskin-a-bu-i"

SATS = 340.16      # tekstflata: 120 x 120 mm i punkt
LINJE = 1.5        # linjeavstand i forhold til skriftstorleiken
MIN_PROSA = 12.0   # lange prosaavsnitt vert delte så skrifta ikkje går under dette (pt)
LANG_LINJE = 54    # verslinjer med fleire teikn enn dette får bryte over to linjer
KORT_STROFE = 8    # strofer med så mange linjer eller færre vert aldri delte over to sider

PREAMBEL = r"""
\documentclass[10pt,twoside]{memoir}
% Kvadratisk bok: 148 x 148 mm ferdig skoren, 3 mm utfallande kant (PDF-sida er 154 x 154 mm).
% Lik marg på alle fire kantar: 14 mm. Tekstflata er 120 x 120 mm.
\setstocksize{154mm}{154mm}
\settrimmedsize{148mm}{148mm}{*}
\settrims{3mm}{3mm}
\settypeblocksize{120mm}{120mm}{*}
\setlrmargins{14mm}{*}{*}
\setulmargins{14mm}{*}{*}
\setheadfoot{\onelineskip}{\onelineskip}
\checkandfixthelayout

% Skjerekant og utfallande kant for trykkeriet (i PostScript-punkt).
\AddToHook{shipout/background}{\special{pdf:put @thispage
  <</TrimBox [8.504 8.504 428.031 428.031] /BleedBox [0 0 436.535 436.535]>>}}

% 100 % svart på alle sider (DeviceGray 0, som trykkjer som K = 100), kvit tekst.
\usepackage{xcolor}
\pagecolor{black}
\color{white}

\usepackage{fontspec}
\usepackage[nynorsk]{babel}
\setmainfont{LibertinusSerif}[Extension=.otf, UprightFont=*-Regular, ItalicFont=*-Italic,
  BoldFont=*-Semibold, BoldItalicFont=*-SemiboldItalic]
\setmonofont{LibertinusMono}[Extension=.otf, UprightFont=*-Regular]
% Kapitalane er ikkje sperra: XeTeX reknar breidda feil med LetterSpace, og linjene stakk ut i margen.
\newfontfamily\kapselfamilie{LibertinusSerif}[Extension=.otf, UprightFont=*-Regular, ItalicFont=*-Italic]
\usepackage[protrusion=true,expansion=false]{microtype}

\pagestyle{empty}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0pt}
\frenchspacing
% Aldri orddeling.
\hyphenpenalty=10000
\exhyphenpenalty=10000
\tolerance=1200
\emergencystretch=3em
\vbadness=10000
\hbadness=10000
\hfuzz=1.5pt   % XeTeX kan rekne ordbreidder nokre tidels punkt feil; det synest ikkje

% Skriftstorleiken \fs vert sett side for side. Tre stemmer, same linjeavstand.
\newdimen\fs \fs=10pt
\newcommand\kapsel{\kapselfamilie\fontsize{\the\fs}{\the\dimexpr1.5\fs\relax}\selectfont
  \baselineskip=1.5\fs plus 0.25\fs\relax}
\newcommand\vanleg{\rmfamily\fontsize{\the\dimexpr1.1\fs\relax}{\the\dimexpr1.5\fs\relax}\selectfont
  \baselineskip=1.5\fs plus 0.25\fs\relax}
\newcommand\maskin{\ttfamily\fontsize{\the\dimexpr0.95\fs\relax}{\the\dimexpr1.5\fs\relax}\selectfont
  \baselineskip=1.5\fs plus 0.25\fs\relax}
\newcommand\kursiv[1]{{\rmfamily\itshape\fontsize{\the\dimexpr1.2\fs\relax}{\the\dimexpr1.5\fs\relax}\selectfont #1}}

% Justert kant til kant. Verslinja er eit eige avsnitt; mellomromma deler lufta likt.
% \vl tel linjer som bryt (då er skrifta for stor); \vlb er ei lang linje som får bryte.
\newcount\fitbrot
\newbox\fittest
\newcommand\versrom{\spaceskip=\fontdimen2\font plus 2em minus 0.3\fontdimen2\font\relax}
\newcommand\versoppsett{\hyphenpenalty=10000\exhyphenpenalty=10000\noindent
  \hangindent=2em\hangafter=1\relax\versrom\parfillskip=0pt\relax}
% Ei verslinje som ikkje får plass i breidda (overfull) eller bryt, gjer storleiken for stor.
\newcommand\vl[2]{{#1\setbox\fittest=\hbox to \hsize{\versrom #2}%
  \ifnum\badness>10000 \global\advance\fitbrot by 1 \fi
  \versoppsett #2\par\ifnum\prevgraf>1 \global\advance\fitbrot by 1 \fi}}
\newcommand\vlb[2]{{#1\versoppsett #2\par}}
% Prosa: utan orddeling må mellomromma få strekkje seg fritt, så ingen linje stikk ut i margen.
% Under målinga vert kvar linje (utanom den siste) sjekka: står det berre eitt ord på ho,
% kan ho ikkje justerast, og då er skrifta for stor.
\newif\iffitmaaling
\newbox\prosaboks
\newcount\fitlinjer
\newcommand\prosaoppsett{\noindent\tolerance=10000\versrom\parfillskip=0pt\relax}
\newcommand\prosa[2]{\iffitmaaling\prosasjekk{#1}{#2}\fi{#1\prosaoppsett #2\par}}
\newcommand\prosasjekk[2]{%
  \setbox\prosaboks=\vbox{\hsize=\textwidth #1\prosaoppsett #2\par
    \global\fitlinjer=0
    \loop\unskip\unpenalty\unskip
      \setbox2=\lastbox
    \ifvoid2\else
      \global\advance\fitlinjer by 1
      \setbox4=\hbox to \wd2{\unhcopy2}%
      \ifnum\fitlinjer>1 \ifnum\badness>9999 \global\advance\fitbrot by 1 \fi\fi
    \repeat}}
\newcommand\strofeskil{\par\vspace{1.5\fs plus 1.5\fs}}
\newcommand\skilje{\par\vspace{1.5\fs plus 1\fs}{\centering\vanleg ·\par}\vspace{1.5\fs plus 1\fs}}

% Kvar side: finn største \fs der innhaldet får plass i tekstflata utan brotne verslinjer.
\newbox\fitboks
\newdimen\fitlo \newdimen\fithi \newdimen\fitmid
\newcount\fitsteg
\newcommand\fitmaal{\global\fitbrot=0 \fitmaalingtrue
  \setbox\fitboks=\vbox{\hfuzz=\maxdimen\hsize=\textwidth\fitinnhald}\fitmaalingfalse}
\newcommand\fitside[2]{%
  \def\fitinnhald{#2}%
  \fitlo=3pt \fithi=#1pt \fitsteg=0
  \loop
    \fitmid=\dimexpr(\fitlo+\fithi)/2\relax
    \fs=\fitmid \fitmaal
    \ifdim\dimexpr\ht\fitboks+\dp\fitboks\relax>\textheight \fithi=\fitmid
    \else\ifnum\fitbrot>0 \fithi=\fitmid \else \fitlo=\fitmid \fi\fi
    \advance\fitsteg by 1
  \ifnum\fitsteg<14 \repeat
  \fs=\fitlo \fitmaal
  \typeout{FITSIDE \the\fs}%
  % \kern0pt held djupna til siste linja inne i boksen (djupn 0), så sida aldri vert for høg.
  \vbox to \textheight{\hsize=\textwidth\fitinnhald\kern0pt}%
  \clearpage}
"""

TEX_TEIKN = {
    "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
    "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
}


def tex(s: str) -> str:
    return "".join(TEX_TEIKN.get(c, c) for c in s)


def inline(s: str, mono: bool = False) -> str:
    """*kursiv* -> kursiv. I maskinskrift vert kursiv sett i antikva, sidan monoskrifta manglar kursiv."""
    ut = []
    for bit in re.split(r"(\*[^*]+\*)", s):
        if len(bit) > 2 and bit.startswith("*") and bit.endswith("*"):
            ut.append((r"\kursiv{%s}" if mono else r"\textit{%s}") % tex(bit[1:-1]))
        else:
            ut.append(tex(bit))
    return "".join(ut)


def er_kapitalar(s: str) -> bool:
    bokstavar = [c for c in s if c.isalpha()]
    return bool(bokstavar) and all(c.isupper() for c in bokstavar)


def tolk_manus(md: str) -> list:
    """Gjer manus.md om til ei flat rekkje: linje, prosa, rom (strofeskil) og skilje (·)."""
    element, blokk = [], []
    modus, i_kommentar = "vers", False

    def skil(art):
        if not element:
            return
        if element[-1]["art"] in ("rom", "skilje"):
            if art == "skilje":
                element[-1] = {"art": "skilje"}
        else:
            element.append({"art": art})

    def tøm():
        nonlocal blokk
        if not blokk:
            return
        skil("rom")
        if modus == "prosa":
            element.append({"art": "prosa", "tekst": " ".join(blokk)})
        else:
            for linje in blokk:
                mono = modus == "mono"
                skrift = r"\maskin" if mono else (r"\kapsel" if er_kapitalar(linje) else r"\vanleg")
                element.append({"art": "linje", "tekst": linje, "mono": mono, "skrift": skrift,
                                "lang": len(linje) > LANG_LINJE})
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
        elif s == "---":
            tøm()
            skil("skilje")
        elif not s:
            tøm()
        else:
            blokk.append(s)
    tøm()

    # Nøklar til målepasset
    nl = nw = 0
    for e in element:
        if e["art"] == "linje":
            e["nøkkel"] = f"L{nl}"
            nl += 1
        elif e["art"] == "prosa":
            e["ord"] = e["tekst"].split()
            e["nøklar"] = [f"W{nw + i}" for i in range(len(e["ord"]))]
            nw += len(e["ord"])
    return element


def mål_breidder(element: list, namn: str) -> dict:
    """Målepass: breidda (pt ved \\fs = 10pt) på kvar verslinje, kvart prosaord og eit ordmellomrom."""
    maal = "maal" + re.sub(r"[^A-Za-z0-9]", "", namn)
    linjer = [r"\newwrite\maalfil", r"\begin{document}", r"\immediate\openout\maalfil=%s.dat" % maal,
              r"\newcommand\maal[3]{\settowidth{\dimen0}{#2#3}\immediate\write\maalfil{#1 \the\dimen0}}"]
    for e in element:
        if e["art"] == "linje":
            linjer.append(r"\maal{%s}{%s}{%s}" % (e["nøkkel"], e["skrift"], inline(e["tekst"], e["mono"])))
        elif e["art"] == "prosa":
            for k, o in zip(e["nøklar"], e["ord"]):
                linjer.append(r"\maal{%s}{\kapsel}{%s}" % (k, tex(o)))
    linjer += [r"\setbox0\hbox{\kapsel\global\dimen1=\fontdimen2\font}",
               r"\immediate\write\maalfil{SPACE \the\dimen1}",
               r"\immediate\closeout\maalfil", r"\end{document}", ""]
    (UT / f"{maal}.tex").write_text(PREAMBEL + "\n".join(linjer), encoding="utf-8")
    køyr(maal)
    mål = {}
    for linje in (UT / f"{maal}.dat").read_text(encoding="utf-8").splitlines():
        k, v = linje.split()
        mål[k] = float(v.removesuffix("pt"))
    return mål


def lag_sider(element: list, mål: dict):
    rom = mål["SPACE"]

    def breidd(e, s):
        return mål[e["nøkkel"]] * s / 10

    def prosalinjer(e, s):
        linjer, cur, mellom = 1, 0.0, rom * s / 10 * 0.8
        for k in e["nøklar"]:
            w = mål[k] * s / 10
            if cur == 0:
                cur = w
            elif cur + mellom + w <= SATS:
                cur += mellom + w
            else:
                linjer, cur = linjer + 1, w
        return linjer

    def høgd(side, s):
        n = rom_ = skil = 0
        for e in side:
            a = e["art"]
            if a == "linje":
                n += 2 if e["lang"] and breidd(e, s) > SATS * 0.97 else 1
            elif a == "prosa":
                n += prosalinjer(e, s)
            elif a == "rom":
                rom_ += 1
            else:
                skil += 1
        return LINJE * s * (n - 1) + 0.75 * s + rom_ * LINJE * s + skil * 3 * LINJE * s

    def ordgrense(side):
        g = [SATS * 10 / max(mål[k] for k in e["nøklar"]) for e in side if e["art"] == "prosa"]
        return min(g) if g else float("inf")

    def breiddgrense(side):
        g = [SATS * 0.97 * 10 / mål[e["nøkkel"]] for e in side if e["art"] == "linje" and not e["lang"]]
        return min(g) if g else float("inf")

    def storleik(side):
        lo, hi = 2.0, min(150.0, breiddgrense(side), ordgrense(side))
        for _ in range(30):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if høgd(side, mid) <= SATS else (lo, mid)
        return lo

    def fyll(side):
        return høgd(side, storleik(side)) / SATS if side else 0.0

    def rydd(side):
        while side and side[0]["art"] in ("rom", "skilje"):
            side = side[1:]
        while side and side[-1]["art"] in ("rom", "skilje"):
            side = side[:-1]
        return side

    def del_prosa(e):
        par = list(zip(e["ord"], e["nøklar"]))
        total = sum(mål[n] for _, n in par)
        for k in range(2, 60):
            bitar, o_, n_, acc = [], [], [], 0.0
            for o, n in par:
                o_.append(o)
                n_.append(n)
                acc += mål[n]
                if acc >= total / k * (len(bitar) + 1) and len(bitar) < k - 1:
                    bitar.append({"art": "prosa", "tekst": " ".join(o_), "ord": o_, "nøklar": n_})
                    o_, n_ = [], []
            if o_:
                bitar.append({"art": "prosa", "tekst": " ".join(o_), "ord": o_, "nøklar": n_})
            if all(storleik([b]) >= MIN_PROSA for b in bitar):
                return bitar
        return bitar

    sider, cur = [], []

    def ut(side):
        side = rydd(side)
        if side:
            sider.append(side)

    for idx, e in enumerate(element):
        a = e["art"]
        if a in ("rom", "skilje"):
            if cur:
                cur.append(e)
        elif a == "linje":
            prøve = rydd(cur + [e])
            if not cur or høgd(prøve, breiddgrense(prøve)) <= SATS:
                cur.append(e)   # sida er framleis bunden av breidda: meir tekst gjev betre fylling
                continue
            # Sida er full. Korte strofer (KORT_STROFE linjer eller færre) vert aldri delte:
            # byrjar strofa lenger nede, flyttar ho til neste side; står ho øvst, får ho bli heil.
            s0 = len(cur)
            while s0 > 0 and cur[s0 - 1]["art"] == "linje":
                s0 -= 1
            k = len(cur) - s0
            rest = 0
            for x in element[idx:]:
                if x["art"] != "linje":
                    break
                rest += 1
            if k + rest <= KORT_STROFE:
                if s0 > 0:
                    ut(cur[:s0])
                    cur = cur[s0:] + [e]
                else:
                    cur.append(e)
                continue
            brot = None         # lang strofe: bryt helst ved eit strofeskil
            for i in range(len(cur) - 1, 0, -1):
                if cur[i]["art"] in ("rom", "skilje") and fyll(rydd(cur[:i])) >= 0.75:
                    brot = i
                    break
            if brot is None:
                # Inga strofe skal delast med éi linje åleine på nokon av sidene.
                if (rest == 1 and k >= 3) or (k == 1 and len(cur) > 1):
                    ut(cur[:-1])
                    cur = [cur[-1], e]
                else:
                    ut(cur)
                    cur = [e]
            else:
                ut(cur[:brot])
                cur = rydd(cur[brot + 1:]) + [e]
        else:  # prosa
            førre = rydd(cur)
            if førre and fyll(førre) < 0.5:
                saman = førre + [{"art": "rom"}, e]
                if storleik(saman) >= 0.85 * storleik(førre):
                    ut(saman)
                    cur = []
                    continue
            ut(cur)
            cur = []
            if storleik([e]) >= MIN_PROSA:
                sider.append([e])
            else:
                sider.extend([b] for b in del_prosa(e))
    ut(cur)
    return sider, storleik, ordgrense


def side_tex(side) -> str:
    deler = []
    for e in side:
        a = e["art"]
        if a == "linje":
            deler.append(r"\%s{%s}{%s}" % ("vlb" if e["lang"] else "vl", e["skrift"], inline(e["tekst"], e["mono"])))
        elif a == "prosa":
            deler.append(r"\prosa{\kapsel}{%s}" % inline(e["tekst"]))
        elif a == "rom":
            deler.append(r"\strofeskil")
        else:
            deler.append(r"\skilje")
    return "\n".join(deler)


def køyr(namn: str):
    r = subprocess.run(
        ["xelatex", "-interaction=nonstopmode", "-halt-on-error", f"{namn}.tex"],
        cwd=UT, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if r.returncode != 0:
        print(r.stdout[-4000:])
        sys.exit(f"xelatex feila; sjå bygg/{namn}.log")
    return r.stdout


def main():
    UT.mkdir(exist_ok=True)
    manus = (Path.cwd() / sys.argv[1]).resolve() if len(sys.argv) > 1 else MANUS
    namn = manus.stem if len(sys.argv) > 1 else NAMN
    element = tolk_manus(manus.read_text(encoding="utf-8"))
    mål = mål_breidder(element, namn)
    sider, storleik, ordgrense = lag_sider(element, mål)

    kropp = [r"\begin{document}"]
    for side in sider:
        hi = min(storleik(side) * 1.3 + 1, ordgrense(side) * 0.99, 150)
        kropp.append(r"\fitside{%.2f}{%s}" % (hi, side_tex(side)))
    kropp += [r"\end{document}", ""]
    (UT / f"{namn}.tex").write_text(PREAMBEL + "\n".join(kropp), encoding="utf-8")
    logg = køyr(namn)
    shutil.copy(UT / f"{namn}.pdf", HER / f"{namn}.pdf")

    storleikar = [float(x) for x in re.findall(r"FITSIDE ([\d.]+)pt", logg)]
    m = re.search(r"Output written on .*?\((\d+)\s+pages?", logg, re.S)
    print(f"{namn}.pdf: {m.group(1) if m else '?'} sider, skrift {min(storleikar):.1f}–{max(storleikar):.1f} pt "
          f"(median {sorted(storleikar)[len(storleikar) // 2]:.1f} pt)")


if __name__ == "__main__":
    main()
