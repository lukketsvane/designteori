#!/usr/bin/env python3
"""Byggjer «Maskin å bu i» frå manus.md til ein A5-PDF klar for trykk.

Bruk:   python bygg.py
Krev:   xelatex (MiKTeX eller TeX Live) med memoir, fontspec, babel (nynorsk), xurl
        og Libertinus-skriftene (følgjer med i begge distribusjonane).
Resultat: maskin-a-bu-i.pdf i same mappe. Mellomfiler hamnar i bygg/.

Sidetalet vert runda opp til næraste fireartal med tomme sider til slutt,
slik at boka kan falsast og heftast.
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

# Skriv namnet til forfattaren her om det skal stå på tittelsida.
FORFATTAR = ""

PREAMBEL = r"""
\documentclass[10pt,twoside,openright]{memoir}
\setstocksize{210mm}{148mm}
\settrimmedsize{\stockheight}{\stockwidth}{*}
\settypeblocksize{160mm}{100mm}{*}
\setlrmargins{20mm}{*}{*}
\setulmargins{20mm}{*}{*}
\setheadfoot{\onelineskip}{12mm}
\checkandfixthelayout

\usepackage{fontspec}
\usepackage[nynorsk]{babel}
\setmainfont{LibertinusSerif}[Extension=.otf, UprightFont=*-Regular, ItalicFont=*-Italic,
  BoldFont=*-Semibold, BoldItalicFont=*-SemiboldItalic]
\setsansfont{LibertinusSans}[Extension=.otf, UprightFont=*-Regular, ItalicFont=*-Italic, BoldFont=*-Bold]
\setmonofont{LibertinusMono}[Extension=.otf, UprightFont=*-Regular]
\newfontfamily\kapselfamilie{LibertinusSerif}[Extension=.otf, UprightFont=*-Regular,
  ItalicFont=*-Italic, LetterSpace=4.0]
\newfontfamily\tittelfamilie{LibertinusSans}[Extension=.otf, UprightFont=*-Regular, LetterSpace=16.0]
\usepackage[protrusion=true,expansion=false]{microtype}
\usepackage[hidelinks]{hyperref}
\usepackage{xurl}
\urlstyle{tt}

\makepagestyle{bok}
\makeevenfoot{bok}{}{\footnotesize\sffamily\thepage}{}
\makeoddfoot{bok}{}{\footnotesize\sffamily\thepage}{}
\aliaspagestyle{cleared}{empty}

\setlength{\parindent}{0pt}
\setlength{\parskip}{0pt}
\raggedbottom
\widowpenalty=10000
\clubpenalty=10000
\tolerance=1200
\emergencystretch=3em

% Tre stemmer: kapitalar (letterspatiert), vanleg sats, maskinskrift.
\newcommand\kapsel{\kapselfamilie\fontsize{9}{13.5}\selectfont}
\newcommand\vanleg{\rmfamily\fontsize{10}{14}\selectfont}
\newcommand\maskin{\ttfamily\fontsize{8.6}{13.5}\selectfont}

% Vers: kvar linje er eit eige avsnitt med hengjande innrykk for lange linjer.
\newcommand\vl[2]{{#1\noindent\hangindent=2em\hangafter=1\relax #2\par}}
\newenvironment{strofe}{\par\raggedright\hyphenpenalty=10000\exhyphenpenalty=10000\relax}{\par}
\newcommand\strofeskil{\par\vspace{1\baselineskip plus 2pt minus 1pt}}
\newcommand\prosa[2]{{#1\noindent #2\par}}
\newcommand\skilje{\par\vspace{1.4\baselineskip}{\centering\vanleg ·\par}\nobreak\vspace{1.4\baselineskip}}
\newenvironment{epigraf}[1]{\par\begin{flushright}#1}{\end{flushright}\par\vspace{2\baselineskip}}

\newcommand\del[3]{\cleardoublepage\thispagestyle{empty}%
  \vspace*{26mm}%
  {\sffamily\footnotesize #1\par}\vspace{4mm}%
  {\raggedright\tittelfamilie\fontsize{11}{17}\selectfont #2\par}%
  \label{#3}\vspace{14mm}}
\newcommand\undertittel[1]{\vspace{-10mm}{\vanleg\itshape #1\par}\vspace{10mm}}
\newcommand\bakdel[2]{\clearpage\thispagestyle{empty}\vspace*{14mm}%
  {\raggedright\tittelfamilie\fontsize{9}{13}\selectfont #1\par}\label{#2}\vspace{12mm}}
\newcommand\seksjon[2]{\clearpage\vspace*{10mm}%
  {\raggedright\tittelfamilie\fontsize{8.5}{13}\selectfont #1\par}\label{#2}\vspace{9mm}}

% Personleg modulor: eit skjema lesaren fyller ut sjølv.
\newcommand\felt{\rule[-1pt]{5.6em}{0.4pt}\,cm}
\newcommand\feltvh{v\,\rule[-1pt]{3.4em}{0.4pt}\enspace h\,\rule[-1pt]{3.4em}{0.4pt}\,cm}
\newcommand\skjemarad[3]{{\maskin\noindent\makebox[1.6em][r]{#1}\hspace{0.7em}#2\hfill#3\par}\vspace{2.6mm}}

\newcommand\kjeldefrase[1]{{\vanleg\itshape\small #1\par}\nobreak}
\newenvironment{kjelder}{\par\raggedright\ttfamily\fontsize{6.8}{9.5}\selectfont}{\par}

\newcommand\innhaldsdel[3]{\par\vspace{2.4mm}{\sffamily\footnotesize\noindent
  \makebox[2.4em][l]{#1}#2\dotfill\pageref{#3}\par}}
\newcommand\innhaldsseksjon[2]{{\sffamily\footnotesize\noindent\hspace*{2.4em}#1\dotfill\pageref{#2}\par}}

\newcount\padtal
\newcommand\padsider[1]{\clearpage\padtal=#1\relax
  \loop\ifnum\padtal>0 \thispagestyle{empty}\null\clearpage\advance\padtal by -1 \repeat}
"""

FRAMSIDER = r"""
\begin{document}
\pagestyle{bok}
\thispagestyle{empty}
\vspace*{48mm}
{\centering\tittelfamilie\fontsize{9}{13}\selectfont MASKIN Å BU I\par}
\clearpage
\thispagestyle{empty}\null\clearpage
\thispagestyle{empty}
\vspace*{34mm}
{\centering\tittelfamilie\fontsize{17}{26}\selectfont MASKIN\par Å BU I\par}
\vspace{8mm}
{\centering\vanleg\itshape dikt\par}
\vfill
{\centering\sffamily\footnotesize FORFATTAR\par}
\vspace*{6mm}
\clearpage
\thispagestyle{empty}
\vspace*{\fill}
{\vanleg\footnotesize\raggedright
MASKIN Å BU I\par\medskip
© 2026\par\medskip
Sett i Libertinus Serif, Libertinus Sans og Libertinus Mono.\par
Format A5, 148 × 210 mm.\par\medskip
Manus til Tigertrykk, november 2026.\par}
\clearpage
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
            indre = tex(bit[1:-1])
            ut.append(r"{\rmfamily\itshape\fontsize{10.4}{13.5}\selectfont " + indre + "}" if mono
                      else r"\textit{" + indre + "}")
        else:
            ut.append(tex(bit))
    return "".join(ut)


def er_kapitalar(s: str) -> bool:
    bokstavar = [c for c in s if c.isalpha()]
    return bool(bokstavar) and all(c.isupper() for c in bokstavar)


def lag_tex(md: str, pad: int = 0) -> str:
    kropp, innhald = [], []
    modus, blokk, epi = "vers", [], []
    treng_skil = False
    i_kommentar = False
    teljar = 0

    def nytt_merke() -> str:
        nonlocal teljar
        teljar += 1
        return f"m{teljar}"

    def skrift(tekst: str) -> str:
        if modus == "mono":
            return r"\maskin"
        return r"\kapsel" if er_kapitalar(tekst) else r"\vanleg"

    def tøm_epigraf():
        nonlocal epi, treng_skil
        if not epi:
            return
        if modus == "mono":
            f = r"\maskin"
        elif all(er_kapitalar(x) for x in epi):
            f = r"\kapsel"
        else:
            f = r"\vanleg\itshape"
        linjer = r"\\".join(inline(x, modus == "mono") for x in epi)
        kropp.append(r"\begin{epigraf}{" + f + "}" + linjer + r"\end{epigraf}")
        epi = []
        treng_skil = False

    def tøm():
        nonlocal blokk, treng_skil
        if not blokk:
            return
        mono = modus == "mono"
        if modus in ("vers", "mono"):
            if treng_skil:
                kropp.append(r"\strofeskil")
            kropp.append(r"\begin{strofe}")
            n = len(blokk)
            for i, linje in enumerate(blokk):
                kropp.append(r"\vl{%s}{%s}" % (skrift(linje), inline(linje, mono)))
                if i < n - 1:
                    # Lite lyst til sideskift inne i ei strofe, aldri etter første eller før siste linje.
                    kropp.append(r"\penalty%d" % (3000 if i in (0, n - 2) else 150))
            kropp.append(r"\end{strofe}")
        elif modus == "prosa":
            if treng_skil:
                kropp.append(r"\strofeskil")
            tekst = " ".join(blokk)
            kropp.append(r"\prosa{%s}{%s}" % (skrift(tekst), inline(tekst)))
        elif modus == "skjema":
            for linje in blokk:
                m = re.match(r"(\d+)\.\s+(.*)", linje)
                nr, mål = m.group(1), m.group(2)
                felt = r"\felt"
                if "venstre/høgre" in mål:
                    mål, felt = mål.replace("venstre/høgre", "").strip(), r"\feltvh"
                kropp.append(r"\skjemarad{%s}{%s}{%s}" % (nr, tex(mål), felt))
        elif modus == "kjelder":
            kropp.append(r"\begin{kjelder}")
            for linje in blokk:
                frase, url = (x.strip() for x in linje.split("|", 1))
                kropp.append(r"\kjeldefrase{%s}" % inline(frase))
                # \url må stå på toppnivå (ikkje som argument) for at % og & skal lesast rett.
                kropp.append(r"\url{%s}\par\vspace{2.2mm}" % url)
            kropp.append(r"\end{kjelder}")
        blokk = []
        treng_skil = True

    for rå in md.splitlines():
        s = rå.strip()
        if i_kommentar:
            if s == "-->":
                i_kommentar = False
            continue
        if s == "<!--":
            i_kommentar = True
            continue
        d = re.fullmatch(r"<!--\s*(.*?)\s*-->", s)
        if d:
            tøm()
            tøm_epigraf()
            verdi = d.group(1)
            if verdi in ("vers", "prosa", "mono", "skjema", "kjelder"):
                modus = verdi
            elif verdi == "side":
                kropp.append(r"\clearpage")
                treng_skil = False
            continue
        if s.startswith(">"):
            tøm()
            epi.append(s[1:].strip())
            continue
        tøm_epigraf()
        if s.startswith("### "):
            tøm()
            kropp.append(r"\undertittel{%s}" % inline(s[4:]))
            treng_skil = False
        elif s.startswith("## "):
            tøm()
            tittel, merke = s[3:], nytt_merke()
            kropp.append(r"\seksjon{%s}{%s}" % (inline(tittel), merke))
            innhald.append((2, "", tittel, merke))
            treng_skil = False
        elif s.startswith("# "):
            tøm()
            tittel, merke = s[2:], nytt_merke()
            if " · " in tittel:
                nr, tittel = tittel.split(" · ", 1)
                kropp.append(r"\del{%s}{%s}{%s}" % (nr, inline(tittel), merke))
            else:
                nr = ""
                kropp.append(r"\bakdel{%s}{%s}" % (inline(tittel), merke))
            innhald.append((1, nr, tittel, merke))
            treng_skil = False
        elif s == "---":
            tøm()
            kropp.append(r"\skilje")
            treng_skil = False
        elif not s:
            tøm()
        else:
            blokk.append(s)
    tøm()
    tøm_epigraf()

    inn = [r"\bakdel{INNHALD}{innhald}"]
    for nivå, nr, tittel, merke in innhald:
        if nivå == 1:
            inn.append(r"\innhaldsdel{%s}{%s}{%s}" % (nr, inline(tittel), merke))
        else:
            inn.append(r"\innhaldsseksjon{%s}{%s}" % (inline(tittel), merke))

    framsider = FRAMSIDER.replace("FORFATTAR", tex(FORFATTAR))
    return "\n".join([PREAMBEL, framsider, *kropp, *inn, r"\padsider{%d}" % pad, r"\end{document}", ""])


def kompiler() -> int:
    r = subprocess.run(
        ["xelatex", "-interaction=nonstopmode", "-halt-on-error", f"{NAMN}.tex"],
        cwd=UT, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if r.returncode != 0:
        print(r.stdout[-4000:])
        sys.exit("xelatex feila; sjå bygg/%s.log" % NAMN)
    m = re.search(r"Output written on .*?\((\d+)\s+pages?", r.stdout, re.S)
    return int(m.group(1)) if m else 0


def bygg(pad: int):
    UT.mkdir(exist_ok=True)
    (UT / f"{NAMN}.tex").write_text(lag_tex(MANUS.read_text(encoding="utf-8"), pad), encoding="utf-8")


def main():
    bygg(0)
    kompiler()
    sider = kompiler()
    pad = (-sider) % 4
    if pad:
        bygg(pad)
        kompiler()
        sider = kompiler()
    shutil.copy(UT / f"{NAMN}.pdf", HER / f"{NAMN}.pdf")
    print(f"{NAMN}.pdf: {sider} sider ({pad} tomme sider lagde til for fireartal)")


if __name__ == "__main__":
    main()
