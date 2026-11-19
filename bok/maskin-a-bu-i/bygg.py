#!/usr/bin/env python3
"""Byggjer «Maskin å bu i» (og AHO_A/B/C) til ein kvadratisk PDF (148 x 148 mm, kvit tekst på svart).

Tett sats, nær klaustrofobisk: kvar side er éin kvit tekstblokk som fyller tekstflata frå kant
til kant og frå topp til botn. Margen er lik og smal på alle fire kantar, linjeavstanden er tett,
og skriftstorleiken vert tilpassa automatisk side for side:

1. Eit målepass i XeLaTeX måler breidda på kvart ord (med rett skrift).
2. Python fyller sidene med ord i lesefølgje til teksten fyller flata ved om lag MÅL_STORLEIK,
   og bryt helst ved eit strofe- eller avsnittsskil nær slutten av sida.
3. I sluttpasset finn XeLaTeX den største skriftstorleiken som får plass på kvar side
   (binærsøk), utan orddeling og utan linjer med eitt einsleg ord (utanom den siste).

Bruk:   python bygg.py              (manus.md  -> maskin-a-bu-i.pdf)
        python bygg.py AHO_A.md     (AHO_A.md  -> AHO_A.pdf)
Krev:   xelatex (MiKTeX eller TeX Live) med memoir, fontspec, babel (nynorsk), xcolor
        og Libertinus-skriftene. Mellomfiler hamnar i bygg/.
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

SATS = 379.84        # tekstflata: 134 x 134 mm i punkt (7 mm marg rundt på ei 148 mm side)
LINJE = 1.12         # tett linjeavstand i forhold til skriftstorleiken
MÅL_STORLEIK = 20.0  # sidene vert fylte med så mykje tekst at skrifta landar rundt dette (pt)

PREAMBEL = r"""
\documentclass[10pt,twoside]{memoir}
% Kvadratisk bok: 148 x 148 mm ferdig skoren, 3 mm utfallande kant (PDF-sida er 154 x 154 mm).
% Lik og smal marg på alle fire kantar: 7 mm. Tekstflata er 134 x 134 mm.
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
% Kapitalane er ikkje sperra: XeTeX reknar breidda feil med LetterSpace.
\newfontfamily\kapselfamilie{LibertinusSerif}[Extension=.otf, UprightFont=*-Regular, ItalicFont=*-Italic]
\usepackage[protrusion=true,expansion=false]{microtype}

\pagestyle{empty}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0pt}
\frenchspacing
% Aldri orddeling.
\hyphenpenalty=10000
\exhyphenpenalty=10000
\vbadness=10000
\hbadness=10000
\hfuzz=1.5pt   % XeTeX kan rekne ordbreidder nokre tidels punkt feil; det synest ikkje

% Skriftstorleiken \fs vert sett side for side. Tett linjeavstand.
\newdimen\fs \fs=10pt
\newcommand\kapsel{\kapselfamilie\fontsize{\the\fs}{\the\dimexpr1.12\fs\relax}\selectfont
  \baselineskip=1.12\fs plus 0.1\fs\relax}
\newcommand\vanleg{\rmfamily\fontsize{\the\dimexpr1.1\fs\relax}{\the\dimexpr1.12\fs\relax}\selectfont
  \baselineskip=1.12\fs plus 0.1\fs\relax}
\newcommand\maskin{\ttfamily\fontsize{\the\dimexpr0.95\fs\relax}{\the\dimexpr1.12\fs\relax}\selectfont
  \baselineskip=1.12\fs plus 0.1\fs\relax}
\newcommand\kursiv[1]{{\rmfamily\itshape\fontsize{\the\dimexpr1.2\fs\relax}{\the\dimexpr1.12\fs\relax}\selectfont #1}}

% Éin blokk per side, justert kant til kant, òg den siste linja.
\newcount\fitbrot
\newif\iffitmaaling
\newbox\prosaboks
\newcount\fitlinjer
\newcommand\blokkoppsett{\noindent\tolerance=10000\parfillskip=0pt\relax
  \spaceskip=\fontdimen2\font plus 2em minus 0.3\fontdimen2\font\relax}
\newcommand\blokk[1]{\iffitmaaling\blokksjekk{#1}\fi{\kapsel\blokkoppsett #1\par}}
% Under målinga: ei linje (utanom den siste) med berre eitt ord kan ikkje justerast,
% og då er skrifta for stor.
\newcommand\blokksjekk[1]{%
  \setbox\prosaboks=\vbox{\hsize=\textwidth\kapsel\blokkoppsett #1\par
    \global\fitlinjer=0
    \loop\unskip\unpenalty\unskip
      \setbox2=\lastbox
    \ifvoid2\else
      \global\advance\fitlinjer by 1
      \setbox4=\hbox to \wd2{\unhcopy2}%
      \ifnum\fitlinjer>1 \ifnum\badness>9999 \global\advance\fitbrot by 1 \fi\fi
    \repeat}}

% Kvar side: finn største \fs der blokka får plass i tekstflata.
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
  % \kern0pt held djupna til siste linja inne i boksen, så sida aldri vert for høg.
  \vbox to \textheight{\hsize=\textwidth\fitinnhald\kern0pt}%
  \clearpage}
"""

TEX_TEIKN = {
    "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
    "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
}


def tex(s: str) -> str:
    return "".join(TEX_TEIKN.get(c, c) for c in s)


def ord_tex(o: str, mono: bool) -> str:
    """Eitt ord; *ord* vert kursiv (i maskinskrift sett i antikva, som manglar kursiv)."""
    if len(o) > 2 and o.startswith("*") and o.endswith("*"):
        return (r"\kursiv{%s}" if mono else r"\textit{%s}") % tex(o[1:-1])
    return tex(o)


def er_kapitalar(s: str) -> bool:
    bokstavar = [c for c in s if c.isalpha()]
    return bool(bokstavar) and all(c.isupper() for c in bokstavar)


def tolk_manus(md: str) -> list:
    """Gjer manus.md om til ein ordstraum. Kvart ord veit skrifta si og om det står eit skil etter det."""
    straum, blokk = [], []
    modus, i_kommentar = "vers", False

    def skil():
        if straum:
            straum[-1]["skil"] = True

    def tøm():
        nonlocal blokk
        if not blokk:
            return
        for linje in blokk:
            mono = modus == "mono"
            skrift = r"\maskin" if mono else (r"\kapsel" if er_kapitalar(linje) else r"\vanleg")
            # *fleire ord* -> *kvart* *ord*, så kursiv held seg når teksten vert delt i ord
            linje = re.sub(r"\*([^*]+)\*", lambda m: " ".join(f"*{w}*" for w in m.group(1).split()), linje)
            for o in linje.split():
                straum.append({"ord": o, "mono": mono, "skrift": skrift, "skil": False})
        blokk = []
        skil()

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
    for i, o in enumerate(straum):
        o["nøkkel"] = f"W{i}"
    return straum


def mål_breidder(straum: list, namn: str) -> dict:
    """Målepass: breidda (pt ved \\fs = 10pt) på kvart ord og eit ordmellomrom."""
    maal = "maal" + re.sub(r"[^A-Za-z0-9]", "", namn)
    linjer = [r"\newwrite\maalfil", r"\begin{document}", r"\immediate\openout\maalfil=%s.dat" % maal,
              r"\newcommand\maal[3]{\settowidth{\dimen0}{#2#3}\immediate\write\maalfil{#1 \the\dimen0}}"]
    for o in straum:
        linjer.append(r"\maal{%s}{%s}{%s}" % (o["nøkkel"], o["skrift"], ord_tex(o["ord"], o["mono"])))
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


def lag_sider(straum: list, mål: dict):
    rom = mål["SPACE"]

    def linjer(ord_, s):
        n, cur, mellom = 1, 0.0, rom * s / 10 * 0.8
        for o in ord_:
            w = mål[o["nøkkel"]] * s / 10
            if cur == 0:
                cur = w
            elif cur + mellom + w <= SATS:
                cur += mellom + w
            else:
                n, cur = n + 1, w
        return n

    def høgd(ord_, s):
        return LINJE * s * (linjer(ord_, s) - 1) + 0.75 * s

    def ordgrense(ord_):
        return SATS * 10 / max(mål[o["nøkkel"]] for o in ord_)

    def storleik(ord_):
        lo, hi = 2.0, min(200.0, ordgrense(ord_))
        for _ in range(30):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if høgd(ord_, mid) <= SATS else (lo, mid)
        return lo

    sider, i, n = [], 0, len(straum)
    while i < n:
        # Fyll sida til teksten ikkje lenger får plass ved MÅL_STORLEIK.
        j = i + 1
        while j < n and høgd(straum[i:j + 1], MÅL_STORLEIK) <= SATS:
            j += 1
        # Bryt helst ved eit strofe- eller avsnittsskil i den siste firedelen av sida.
        if j < n:
            for k in range(j, i + max(1, int((j - i) * 0.75)), -1):
                if straum[k - 1]["skil"]:
                    j = k
                    break
        sider.append(straum[i:j])
        i = j
    return sider, storleik, ordgrense


def side_tex(side) -> str:
    """Éin blokk: ord i same skrift vert samla; maskinskrift står i ei eiga gruppe."""
    deler, cur_skrift, cur = [], None, []

    def tøm():
        if cur:
            tekst = " ".join(cur)
            deler.append(tekst if cur_skrift == r"\kapsel" else "{%s %s}" % (cur_skrift, tekst))

    for o in side:
        if o["skrift"] != cur_skrift:
            tøm()
            cur_skrift, cur = o["skrift"], []
        cur.append(ord_tex(o["ord"], o["mono"]))
    tøm()
    return r"\blokk{%s}" % " ".join(deler)


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
    straum = tolk_manus(manus.read_text(encoding="utf-8"))
    mål = mål_breidder(straum, namn)
    sider, storleik, ordgrense = lag_sider(straum, mål)

    kropp = [r"\begin{document}"]
    for side in sider:
        hi = min(storleik(side) * 1.3 + 1, ordgrense(side) * 0.99, 200)
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
