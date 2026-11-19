#!/usr/bin/env python3
"""Byggjer «Maskin å bu i» frå manus.md til ein kvadratisk PDF (148 x 148 mm, kvit tekst på svart) klar for trykk.

Bruk:   python bygg.py
Krev:   xelatex (MiKTeX eller TeX Live) med memoir, fontspec, babel (nynorsk), xurl
        og Libertinus-skriftene (følgjer med i begge distribusjonane).
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

PREAMBEL = r"""
\documentclass[10pt,twoside,openright]{memoir}
% Kvadratisk bok: 148 x 148 mm ferdig skoren, med 3 mm utfallande kant rundt (PDF-sida er 154 x 154 mm).
\setstocksize{154mm}{154mm}
\settrimmedsize{148mm}{148mm}{*}
\settrims{3mm}{3mm}
\settypeblocksize{110mm}{100mm}{*}
\setlrmargins{20mm}{*}{*}
\setulmargins{16mm}{*}{*}
\setheadfoot{\onelineskip}{11mm}
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
% «Space between»: sida er fylt frå topp til botn, og luft vert fordelt mellom strofene.
\flushbottom
\frenchspacing
\widowpenalty=10000
\clubpenalty=10000
\tolerance=1200
\emergencystretch=3em

% Tre stemmer: kapitalar (letterspatiert), vanleg sats, maskinskrift.
% Linjeavstanden kan strekkje seg litt, så sider utan strofeskil òg vert fylte.
\newcommand\kapsel{\kapselfamilie\fontsize{9}{13.5}\selectfont\setlength\baselineskip{13.5pt plus 0.6pt}}
\newcommand\vanleg{\rmfamily\fontsize{10}{14}\selectfont\setlength\baselineskip{14pt plus 0.6pt}}
\newcommand\maskin{\ttfamily\fontsize{8.6}{13.5}\selectfont\setlength\baselineskip{13.5pt plus 0.6pt}}

% Justert: kvar linje går frå kant til kant, òg den siste i avsnittet.
% Vers: kvar linje er eit eige avsnitt; mellomromma deler lufta likt.
\newcommand\vl[2]{{#1\noindent\hangindent=2em\hangafter=1\relax
  \spaceskip=\fontdimen2\font plus 2em minus 0.3\fontdimen2\font\relax\parfillskip=0pt\relax #2\par}}
\newenvironment{strofe}{\par\hyphenpenalty=10000\exhyphenpenalty=10000\relax}{\par}
\newcommand\strofeskil{\par\vspace{1\baselineskip plus 1.5\baselineskip minus 1pt}}
\newcommand\prosa[2]{{#1\noindent\parfillskip=0pt\relax #2\par}}
\newcommand\skilje{\par\vspace{1.4\baselineskip plus 1\baselineskip}{\centering\vanleg ·\par}\nobreak
  \vspace{1.4\baselineskip plus 1\baselineskip}}
\newenvironment{epigraf}[1]{\par\begin{flushright}#1}{\end{flushright}\par\vspace{2\baselineskip}}

\newcommand\del[3]{\cleardoublepage\thispagestyle{empty}%
  \vspace*{4mm}%
  {\sffamily\footnotesize #1\par}\vspace{4mm}%
  {\raggedright\tittelfamilie\fontsize{11}{17}\selectfont #2\par}%
  \label{#3}\vspace{12mm}}
\newcommand\undertittel[1]{\vspace{-10mm}{\vanleg\itshape #1\par}\vspace{10mm}}
\newcommand\bakdel[2]{\clearpage\thispagestyle{empty}\vspace*{14mm}%
  {\raggedright\tittelfamilie\fontsize{9}{13}\selectfont #1\par}\label{#2}\vspace{12mm}}
\newcommand\seksjon[2]{\clearpage\vspace*{4mm}%
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
\pagestyle{empty}
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


def lag_tex(md: str) -> str:
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

    return "\n".join([PREAMBEL, FRAMSIDER, *kropp, r"\end{document}", ""])


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


def bygg():
    UT.mkdir(exist_ok=True)
    (UT / f"{NAMN}.tex").write_text(lag_tex(MANUS.read_text(encoding="utf-8")), encoding="utf-8")


def main():
    bygg()
    kompiler()
    sider = kompiler()
    shutil.copy(UT / f"{NAMN}.pdf", HER / f"{NAMN}.pdf")
    print(f"{NAMN}.pdf: {sider} sider")


if __name__ == "__main__":
    main()
