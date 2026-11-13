"""Lag docs/metaanalyse/index.html frå rapporten om metaanalysen (Markdown).

Bruk: python -m designteori.metaside <rapport.md>

Sida tek ikkje med filstiar eller maskindetaljar. Pilotdelen om teorielementa ligg samanfalda,
fordi ei blind menneskeleg validering av dei same radene er i gang (sjå docs/validering/).
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

from designteori import ROOT

OUT = ROOT / "docs" / "metaanalyse" / "index.html"
DROP_SECTIONS = ("7. Filer",)
DROP_LINES = ("**Verktøy.**",)
KORT_DROP = ("I pilot v0.3",)
PILOT_SECTION = "2.8 Teorielement i pilotane"
PILOT_BULLET = "**Støtte oppgjeve i delane som er lesne.**"


def inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    return s


def slug(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9æøå]+", "-", s).strip("-")
    return s or "del"


def parse(md: str):
    """Del rapporten i blokker: (kind, level, text) eller ('ul'|'ol', items)."""
    blocks, cur, kind = [], [], None
    section = ""
    pilot_extra = []
    for raw in md.splitlines():
        line = raw.rstrip()
        m = re.match(r"^(#{1,3}) (.*)$", line)
        if m:
            if cur:
                blocks.append((kind, cur)); cur, kind = [], None
            section = m.group(2).strip()
            if any(section.startswith(d) for d in DROP_SECTIONS):
                kind = "skip"
                continue
            blocks.append(("h", (len(m.group(1)), section)))
            continue
        if kind == "skip":
            continue
        if any(line.lstrip("- ").startswith(d) for d in DROP_LINES):
            continue
        if section == "1. Kort" and any(d in line for d in KORT_DROP):
            continue
        if section.startswith("2.7") and PILOT_BULLET in line:
            pilot_extra.append(line[2:].strip())
            continue
        lm = re.match(r"^(\d+)\. (.*)$", line)
        bm = re.match(r"^- (.*)$", line)
        if lm or bm:
            k = "ol" if lm else "ul"
            if kind not in (k,) and cur:
                blocks.append((kind, cur)); cur = []
            kind = k
            cur.append((lm or bm).groups()[-1])
            continue
        if not line.strip():
            if cur:
                blocks.append((kind, cur)); cur, kind = [], None
            continue
        if kind in ("ul", "ol") and cur:
            blocks.append((kind, cur)); cur, kind = [], None
        kind = "p"
        cur.append(line.strip())
    if cur and kind != "skip":
        blocks.append((kind, cur))
    return blocks, pilot_extra


def render(blocks, pilot_extra) -> str:
    out, toc = [], []
    in_pilot = False
    for kind, data in blocks:
        if kind == "h":
            level, text = data
            if in_pilot and level <= 3:
                out.append("</div></details>")
                in_pilot = False
            if level == 1:
                continue
            sid = slug(text)
            tag = "h2" if level == 2 else "h3"
            out.append(f'<{tag} id="{sid}">{inline(text)}</{tag}>')
            if level == 2:
                toc.append((sid, text))
            if text == PILOT_SECTION:
                out.append('<details class="pilot"><summary>Vis tala frå pilotane</summary>'
                           '<div><p class="merk">Er du kodar i valideringa av teorielementbasen? '
                           'Lat vere å opne denne delen før du har levert begge kodearka.</p>')
                for b in pilot_extra:
                    out.append(f"<ul><li>{inline(b)}</li></ul>")
                in_pilot = True
            continue
        if kind == "p":
            out.append("<p>" + inline(" ".join(data)) + "</p>")
        elif kind in ("ul", "ol"):
            items = "".join(f"<li>{inline(x)}</li>" for x in data)
            out.append(f"<{kind}>{items}</{kind}>")
    if in_pilot:
        out.append("</div></details>")
    nav = "".join(f'<li><a href="#{s}">{inline(t)}</a></li>' for s, t in toc)
    return nav, "\n".join(out)


PAGE = """<!doctype html>
<html lang="nn">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Metaanalyse · designteori</title>
<meta name="description" content="Kva dei registrerte verka i nordisk designforsking viser: populasjon, vekst, kanalar, siteringar, tema, omgrep, kunnskapsformer og teorielement.">
<style>
:root{{--bg:#000;--fg:#e8e6e1;--dim:#9a978f;--line:#2b2a27;--acc:#e8e6e1;color-scheme:dark}}
@media (prefers-color-scheme: light){{:root:not([data-theme="dark"]){{--bg:#fbfaf7;--fg:#1d1c1a;--dim:#6b6860;--line:#dedbd3;color-scheme:light}}}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--fg);font:17px/1.6 Georgia,"Iowan Old Style","Times New Roman",serif}}
main{{max-width:46rem;margin:0 auto;padding:1.4rem 16px 5rem}}
a{{color:inherit;text-underline-offset:3px}}
.topp{{display:flex;gap:1rem;flex-wrap:wrap;font:14px/1.4 ui-monospace,Menlo,Consolas,monospace;color:var(--dim)}}
.topp a{{text-decoration:none}} .topp a:hover{{color:var(--fg)}}
h1{{font-size:1.9rem;line-height:1.2;margin:1.6rem 0 .4rem;font-weight:500}}
h2{{font-size:1.3rem;margin:2.6rem 0 .6rem;padding-top:.8rem;border-top:1px solid var(--line);font-weight:500}}
h3{{font-size:1.05rem;margin:1.8rem 0 .4rem;font-weight:600}}
.ingress{{color:var(--dim)}}
p,li{{overflow-wrap:anywhere}}
ul,ol{{padding-left:1.3em}} li{{margin:.45rem 0}}
code{{font-size:.88em}}
nav.toc{{margin:1.2rem 0;padding:.6rem 1rem;border:1px solid var(--line);border-radius:4px}}
nav.toc ol{{margin:.3rem 0}} nav.toc a{{text-decoration:none}} nav.toc a:hover{{text-decoration:underline}}
details.pilot{{border:1px solid var(--line);border-radius:4px;padding:.4rem 1rem;margin:.6rem 0}}
details.pilot summary{{cursor:pointer;font:15px/1.5 ui-monospace,Menlo,Consolas,monospace;color:var(--dim)}}
.merk{{color:var(--dim);font-style:italic}}
footer{{margin-top:3rem;color:var(--dim);font-size:.9rem}}
</style>
</head>
<body>
<main>
<div class="topp"><a href="../">← katalogen</a><a href="../utforsk/">utforsk</a><a href="#kort">kort</a></div>
<h1>Kva korpuset viser</h1>
<p class="ingress">Ei metaanalyse av dei 6 432 registrerte verka i nordisk designforsking, 13.11.2026. Ho skildrar kva dei registrerte verka viser, og seier ikkje kva som er god forsking. Tala er rekna maskinelt frå databasen og kvart funn er etterprøvd av ein uavhengig kontrollør som rekna det på nytt. Ingen fagfelle har lese ho.</p>
<nav class="toc" aria-label="Innhald"><ol>{toc}</ol></nav>
{body}
<footer>Rekna frå OpenAlex-laget og arkivlaget i dette korpuset, med fulltekst lesen lokalt og aldri publisert. Feil og spørsmål: opne ei sak på <a href="https://github.com/lukketsvane/designteori/issues">GitHub</a>.</footer>
</main>
</body>
</html>
"""


def build(md_path: Path) -> Path:
    md = md_path.read_text(encoding="utf-8")
    blocks, extra = parse(md)
    toc, body = render(blocks, extra)
    page = PAGE.format(toc=toc, body=body)
    page = page.replace('<h2 id="1-kort">', '<h2 id="kort">').replace('href="#1-kort"', 'href="#kort"')
    for bad in ("C:/", "C:\\", "Users/", "AppData", "pdf-cache", ".claude"):
        if bad in page:
            raise SystemExit(f"sida inneheld '{bad}': ta det ut av rapporten først")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf-8", newline="\n")
    return OUT


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    print(build(Path(sys.argv[1])))
