#!/usr/bin/env python3
"""Byggjer eit versmanus med éi strofe per side (AHO_D): kvadratisk PDF, 148 x 148 mm, kvit på svart.

Førebiletet er «cor.» (Cardo, éi strofe per side, stor skrift som fyller sida). Systemet:
- Cardo, ei aldinsk antikva (etter Bembo), i store bokstavar med litt sperring, slik versalar skal ha.
- Éi strofe per side. Linjene i verset vert haldne; ei linje som er for lang, held fram på neste
  linje med innrykk (Bringhurst-konvensjonen for vers), og dei to siste orda heng alltid saman, så
  ingen påfølgjande linje vert ståande med eitt ord.
- Kvar side får sin eigen skriftstorleik: skriptet set strofa i mange storleikar og vel den største
  der strofa fyller sida frå toppmargen til botnmargen, med linjeavstand innanfor LINJE_MIN til
  LINJE_MAKS og helst nær LINJE.
- Lik marg på alle fire kantar (MARG, om lag 6 % av sida som i førebiletet). Første linje står med
  toppen sin mot toppmargen, siste grunnlinje på botnmargen. Aldri orddeling, aldri tankestrek.

Bruk:   python bygg_strofe.py AHO_D.md      (AHO_D.md -> AHO_D.pdf)
Krev:   lualatex med memoir, fontspec, babel, xcolor, microtype. Cardo (OFL) vert henta frå
        skrift/Cardo-*.ttf ved sida av dette skriptet; finst ho ikkje, vert EB Garamond nytta som
        vikar og skriptet seier frå.
"""
import re
import shutil
import sys
from pathlib import Path

import bygg  # tolk_manus, tex, køyr, UT

HER = Path(__file__).resolve().parent
UT = bygg.UT
SKRIFT = HER / "skrift"

SIDE_MM, MARG_MM = 148.0, 9.0
PT_PER_MM = 72.27 / 25.4
SATS = (SIDE_MM - 2 * MARG_MM) * PT_PER_MM      # tekstflata i TeX-punkt (130 x 130 mm)
LINJE = 1.14                                    # ønskt linjeavstand i forhold til skriftstorleiken
LINJE_MIN, LINJE_MAKS = 1.10, 1.36              # Cardo: Å-ringen når 0,97 em, så under 1,10 rører han linja over
SPERRING = 6                                    # sperring av versalane, i tusendelar av em x 10 (fontspec LetterSpace)
INNRYKK = 1.5                                   # innrykk for framhald av lange linjer, i em
RAG, FILL = 0.50, 0.05                         # strekk i høgremargen (alle linjer / i tillegg på siste), del av satsbreidda
GROV = [round(8 + 0.25 * i, 2) for i in range(int((90 - 8) / 0.25) + 1)]


def skriftoppsett() -> tuple[str, str]:
    if (SKRIFT / "Cardo-Regular.ttf").exists():
        ekstra = "".join(f", {k}=Cardo-{v}.ttf" for k, v in (("BoldFont", "Bold"), ("ItalicFont", "Italic"))
                         if (SKRIFT / f"Cardo-{v}.ttf").exists())
        return (r"\setmainfont{Cardo-Regular.ttf}[Path=%s/%s, Numbers=Lining, LetterSpace=%d]"
                % (SKRIFT.as_posix(), ekstra, SPERRING), "Cardo")
    print("ÅTVARING: Cardo finst ikkje i skrift/; EB Garamond vert nytta som vikar.")
    return (r"\setmainfont{EBGaramond-Regular.otf}[BoldFont=EBGaramond-Bold.otf, "
            r"ItalicFont=EBGaramond-Italic.otf, Numbers=Lining, LetterSpace=%d]" % SPERRING, "EB Garamond")


def preambel(skrift: str) -> str:
    marg = MARG_MM
    blokk = SIDE_MM - 2 * marg
    return r"""
\documentclass[10pt]{memoir}
\setstocksize{154mm}{154mm}
\settrimmedsize{148mm}{148mm}{*}
\settrims{3mm}{3mm}
\settypeblocksize{%(blokk).2fmm}{%(blokk).2fmm}{*}
\setlrmargins{%(marg).2fmm}{*}{*}
\setulmargins{%(marg).2fmm}{*}{*}
\setheadfoot{1pt}{1pt}
\setheaderspaces{*}{2pt}{*}
\checkandfixthelayout
\pdfvariable pageattr{/TrimBox [8.504 8.504 428.031 428.031] /BleedBox [0 0 436.535 436.535]}
\usepackage{xcolor}
\pagecolor{black}
\color{white}
\usepackage{fontspec}
\usepackage[nynorsk]{babel}
%(skrift)s
\usepackage[protrusion=true]{microtype}
\pagestyle{empty}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0pt}
\frenchspacing
\hyphenpenalty=10000 \exhyphenpenalty=10000
\tolerance=10000 \pretolerance=-1
\clubpenalty=0 \widowpenalty=0 \interlinepenalty=0 \brokenpenalty=0
\lineskiplimit=-\maxdimen
\hbadness=10000 \vbadness=10000 \hfuzz=0.3pt
\raggedbottom
\newdimen\fs \fs=20pt
\newcommand\storleik{\fontsize{\the\fs}{\the\fs}\selectfont}
\newcommand\vl[1]{\hangindent=%(innrykk).2fem\hangafter=1 \noindent #1\par}
%% Rag med endeleg strekk: ei lang verslinje vert delt i to jamne delar heller enn ei full linje og
%% eitt einsleg ord; ordmellomromma strekkjer seg ikkje.
\newcommand\strofeoppsett{\storleik\leftskip=0pt\rightskip=0pt plus %(rag).2f\hsize
  \parfillskip=0pt plus %(fill).2f\hsize\spaceskip=\fontdimen2\font\xspaceskip=\spaceskip\relax}
""" % {"blokk": blokk, "marg": marg, "skrift": skrift, "innrykk": INNRYKK, "rag": RAG, "fill": FILL}


def lag_strofer(einingar: list) -> list[str]:
    """Kvar strofe som TeX: éin \\vl per verslinje. Eittbokstavsord (I, Å) heng saman med ordet etter,
    så dei aldri står åleine ytst på ei linje."""
    strofer = []
    for e in einingar:
        linjer = []
        for linje in e["linjer"]:
            t = re.sub(r"(?<!\S)(\S) ", r"\1~", bygg.tex(linje))
            linjer.append(r"\vl{%s}" % t)
        strofer.append("".join(linjer))
    return strofer


def skann(strofer: list[str], storleikar: dict[int, list[float]], skrift: str, namn: str) -> dict:
    """Set kvar strofe i kvar storleik; skriv linjetal, høgda på første linje og om noko går over kanten."""
    aux = "skann" + re.sub(r"[^A-Za-z0-9]", "", namn)
    kropp = [
        r"\begin{document}",
        r"\newwrite\ut \immediate\openout\ut=%s.dat" % aux,
        r"\newcount\linjetal \newcount\over \newdimen\fyrst",
        r"\newcommand\proev[3]{\fs=#2pt"
        r"\setbox0=\vbox{\hsize=\textwidth\strofeoppsett #3"
        r"\global\linjetal=0 \global\over=0 \global\fyrst=0pt"
        r"\loop\unskip\unpenalty\unskip\unpenalty\unskip\unpenalty\unskip\setbox2=\lastbox\ifvoid2\else\global\advance\linjetal by 1 "
        r"\global\fyrst=\ht2 \setbox4=\hbox{\unhcopy2}\ifdim\wd4>\dimexpr\wd2+0.3pt\relax\global\advance\over by 1 \fi\repeat}"
        r"\immediate\write\ut{#1 #2 \the\linjetal\space\the\fyrst\space\the\over}}",
    ]
    for i, s_liste in storleikar.items():
        kropp.append(r"\long\def\S{%s}" % strofer[i])
        kropp += [r"\proev{%d}{%.2f}{\S}" % (i, s) for s in s_liste]
    kropp += [r"\immediate\closeout\ut", r"\end{document}", ""]
    (UT / f"{aux}.tex").write_text(preambel(skrift) + "\n".join(kropp), encoding="utf-8")
    bygg.køyr(aux)
    ut: dict = {}
    for linje in (UT / f"{aux}.dat").read_text(encoding="utf-8").splitlines():
        i, s, n, h, over = linje.split()
        ut.setdefault(int(i), []).append((float(s), int(n), float(h.removesuffix("pt")), int(over)))
    return ut


def vel(målingar: list) -> tuple:
    """Største storleik som fyller sida, justert for linjeavstand nær LINJE. Gjev (poeng, s, n, topp, lead)."""
    beste = None
    for s, n, topp, over in målingar:
        if over or n < 1:
            continue
        lead = (SATS - topp) / (n - 1) if n > 1 else LINJE * s
        if lead < LINJE_MIN * s:
            continue                       # strofa er for høg for sida
        lead = min(lead, LINJE_MAKS * s)
        fyll = (topp + (n - 1) * lead) / SATS
        poeng = s * fyll * (1 - 0.6 * abs(lead / s - LINJE))
        if beste is None or poeng > beste[0]:
            beste = (poeng, s, n, topp, lead)
    return beste


def main():
    UT.mkdir(exist_ok=True)
    manus = (Path.cwd() / sys.argv[1]).resolve()
    namn = manus.stem
    skrift, skriftnamn = skriftoppsett()
    strofer = lag_strofer(bygg.tolk_manus(manus.read_text(encoding="utf-8")))

    # Grovt søk over alle storleikar, så fint søk rundt det beste for kvar strofe.
    grov = skann(strofer, {i: GROV for i in range(len(strofer))}, skrift, namn)
    fin_storleikar = {}
    for i in range(len(strofer)):
        s0 = vel(grov[i])[1]
        fin_storleikar[i] = [round(s0 - 0.3 + 0.01 * k, 2) for k in range(61)]
    fin = skann(strofer, fin_storleikar, skrift, namn + "fin")

    kropp = [r"\begin{document}"]
    rapport = []
    for i, strofe in enumerate(strofer):
        _, s, n, topp, lead = vel(fin[i] + grov[i])
        lead -= 0.002 * (n > 1)
        kropp.append(
            r"\fs=%.2fpt\topskip=%.3fpt\setlength\maxdepth{%.3fpt}"
            r"{\strofeoppsett\baselineskip=%.4fpt\relax %s}\vfill\newpage" % (s, topp, 0.5 * s, lead, strofe)
        )
        rapport.append((s, n, lead / s))
    kropp += [r"\end{document}", ""]
    (UT / f"{namn}.tex").write_text(preambel(skrift) + "\n".join(kropp), encoding="utf-8")
    logg = bygg.køyr(namn)
    shutil.copy(UT / f"{namn}.pdf", HER / f"{namn}.pdf")
    m = re.search(r"Output written on .*?\((\d+)\s+pages?", logg, re.S)
    print(f"{namn}.pdf: {m.group(1) if m else '?'} sider ({len(strofer)} strofer), skrift {skriftnamn}")
    for k, (s, n, r) in enumerate(rapport, 1):
        print(f"  side {k:2d}: {s:5.2f} pt, {n:2d} linjer, linjeavstand {r:.3f}")


if __name__ == "__main__":
    main()
