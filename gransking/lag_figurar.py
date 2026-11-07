"""Genererer publiseringsklare vektorfigurar (SVG) med 95 % konfidensintervall for granskinga."""
from __future__ import annotations

import html
import json
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent
DATA_FILE = OUT_DIR / "data" / "resultatsamandrag.json"
FIG_DIR = OUT_DIR / "figurar"

FONT = "-apple-system, BlinkMacSystemFont, 'Helvetica Neue', Arial, sans-serif"
INK = "#181817"
MUTED = "#5c5a55"
LINE = "#c6c4bd"
PAPER = "#ffffff"
ACCENT = "#1f4e79"
WARN = "#8b2635"


def esc(s: object) -> str:
    return html.escape(str(s))


def make_fig1_forest(res: dict) -> None:
    """Figur 1: Skogplott (Forest Plot) med 95 % Wilson-KI for hovudindikatorane på P1-P10."""
    rows = res["summary_table"]
    W, H = 880, 520
    left, right, top = 335, 810, 82
    plot_w = right - left
    row_h = 39

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
        f'<rect width="{W}" height="{H}" fill="{PAPER}"/>',
        f'<text x="24" y="32" font-family="{FONT}" font-size="15" font-weight="700" fill="{INK}">Figur 1. Empirisk utslag på påstand P1–P10 med 95 % Wilson-konfidensintervall</text>',
        f'<text x="24" y="52" font-family="{FONT}" font-size="12" fill="{MUTED}">Prosentdel (med 95 % KI) som oppfyller påstandskriteriet i kvar delanalyse (N = {res["metadata"]["corpus_total_works"]} verk; n = {res["metadata"]["fulltext_pdfs_analyzed"]} fulltekstar)</text>',
        f'<line x1="24" y1="64" x2="{W - 24}" y2="64" stroke="{INK}" stroke-width="1"/>',
    ]

    for pct in (0, 20, 40, 60, 80, 100):
        x = left + (pct / 100.0) * plot_w
        lines.append(f'<line x1="{x:.1f}" y1="{top - 8}" x2="{x:.1f}" y2="{top + len(rows) * row_h}" stroke="{LINE}" stroke-width="0.8" stroke-dasharray="2,3"/>')
        lines.append(f'<text x="{x:.1f}" y="{top + len(rows) * row_h + 20}" text-anchor="middle" font-family="{FONT}" font-size="11" fill="{MUTED}">{pct} %</text>')

    labels_short = {
        "P1": "P1: Einsleg-siterte referansar (ingen felles kjerne)",
        "P2": "P2: Semantisk amnesi (cos >= 0.80 ikkje sitert)",
        "P3": "P3: Fulltekstar utan formelle hypotesar",
        "P4": "P4: Siteringar lukka i design-/HCI-/innovasjonsenklave",
        "P5": "P5: Prosessmetode utan kontrollert effekt/nullfunn",
        "P6": "P6: Oppdragsprosjekt utan kritisk mandatreversering",
        "P7": "P7: Doktorandar (<=2021) med 0 seinare publikasjonar",
        "P8": "P8: Institusjonsendogame interne siteringar",
        "P9": "P9: Menneskestudiar utan etisk nemndgodkjenning",
        "P10": "P10: Fulltekstar utan validert måleinstrument",
    }

    for idx, r in enumerate(rows):
        cy = top + idx * row_h + 18
        est = float(r["estimat_pct"])
        lo = float(r["ki95_lav_pct"])
        hi = float(r["ki95_hog_pct"])
        x_est = left + (est / 100.0) * plot_w
        x_lo = left + (lo / 100.0) * plot_w
        x_hi = left + (hi / 100.0) * plot_w

        if idx > 0:
            lines.append(f'<line x1="24" y1="{top + idx * row_h}" x2="{W - 24}" y2="{top + idx * row_h}" stroke="#eceae3" stroke-width="1"/>')
        lines.append(f'<text x="24" y="{cy + 4}" font-family="{FONT}" font-size="12" font-weight="600" fill="{INK}">{esc(labels_short.get(r["id"], r["id"]))}</text>')
        lines.append(f'<line x1="{left}" y1="{cy}" x2="{x_est:.1f}" y2="{cy}" stroke="#d9e2ec" stroke-width="6"/>')
        lines.append(f'<line x1="{x_lo:.1f}" y1="{cy}" x2="{x_hi:.1f}" y2="{cy}" stroke="{INK}" stroke-width="2"/>')
        lines.append(f'<line x1="{x_lo:.1f}" y1="{cy - 4}" x2="{x_lo:.1f}" y2="{cy + 4}" stroke="{INK}" stroke-width="1.5"/>')
        lines.append(f'<line x1="{x_hi:.1f}" y1="{cy - 4}" x2="{x_hi:.1f}" y2="{cy + 4}" stroke="{INK}" stroke-width="1.5"/>')
        lines.append(f'<circle cx="{x_est:.1f}" cy="{cy}" r="4.2" fill="{WARN}"/>')
        lines.append(f'<text x="{W - 24}" y="{cy + 4}" text-anchor="end" font-family="{FONT}" font-size="11.5" font-variant-numeric="tabular-nums" fill="{INK}">{est:.1f} %</text>')

    lines.append("</svg>")
    (FIG_DIR / "fig1_hypotesetest_oversikt.svg").write_text("\n".join(lines), encoding="utf-8")


def make_fig2_cumulativity(res: dict) -> None:
    """Figur 2: Tropisk siteringsdjupn i korpuset (venstre) og semantisk amnesi etter cosinuslikskap (høgre)."""
    W, H = 880, 360
    p2 = res["P2_cumulativity"]
    dist = p2["dag_depth_distribution"]
    tot_n = sum(dist.values()) or 1

    # Aggreger djupn 0, 1, 2, 3, 4, >=5
    d_bins = [("0 (isolert)", dist.get("0", 0)), ("1 ledd", dist.get("1", 0)), ("2 ledd", dist.get("2", 0)), ("3 ledd", dist.get("3", 0)), ("4 ledd", dist.get("4", 0)), (">=5 ledd", sum(v for k, v in dist.items() if int(k) >= 5))]

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
        f'<rect width="{W}" height="{H}" fill="{PAPER}"/>',
        f'<text x="24" y="30" font-family="{FONT}" font-size="15" font-weight="700" fill="{INK}">Figur 2. Fråvær av kumulative kjeder (P2): Tropisk siteringsdjupn og semantisk amnesi</text>',
        f'<line x1="24" y1="44" x2="{W - 24}" y2="44" stroke="{INK}" stroke-width="1"/>',
        f'<text x="24" y="70" font-family="{FONT}" font-size="12.5" font-weight="600" fill="{INK}">A. Lengste interne siteringskjede (n = {tot_n} verk)</text>',
        f'<text x="465" y="70" font-family="{FONT}" font-size="12.5" font-weight="600" fill="{INK}">B. Del eldre nær-identiske verk som ikkje vert siterte</text>',
    ]

    # Panel A
    bx0, by0, bw, bh = 110, 92, 270, 210
    for i, (lbl, cnt) in enumerate(d_bins):
        y = by0 + i * 35
        pct = 100.0 * cnt / tot_n
        w_bar = (pct / 100.0) * bw
        lines.append(f'<text x="{bx0 - 10}" y="{y + 15}" text-anchor="end" font-family="{FONT}" font-size="11.5" fill="{MUTED}">{esc(lbl)}</text>')
        lines.append(f'<rect x="{bx0}" y="{y + 2}" width="{max(1.5, w_bar):.1f}" height="18" fill="{ACCENT}"/>')
        lines.append(f'<text x="{bx0 + w_bar + 7:.1f}" y="{y + 15}" font-family="{FONT}" font-size="11.5" fill="{INK}">{pct:.1f} % ({cnt})</text>')

    # Panel B: Semantisk amnesi
    am = p2["semantic_amnesia_by_cosine"]
    rx0, ry0, rw = 570, 108, 220
    for i, key in enumerate(("0.75-0.80", "0.80-0.85", ">=0.85")):
        item = am[key]
        pct = item["uncited_amnesia_rate"] * 100.0
        y = ry0 + i * 58
        w_bar = (pct / 100.0) * rw
        lines.append(f'<text x="{rx0 - 12}" y="{y + 16}" text-anchor="end" font-family="{FONT}" font-size="11.5" fill="{MUTED}">cos {esc(key)}</text>')
        lines.append(f'<rect x="{rx0}" y="{y}" width="{rw}" height="22" fill="#eeece5"/>')
        lines.append(f'<rect x="{rx0}" y="{y}" width="{w_bar:.1f}" height="22" fill="{WARN}"/>')
        lines.append(f'<text x="{rx0 + rw + 8}" y="{y + 15}" font-family="{FONT}" font-size="11.5" font-weight="600" fill="{INK}">{pct:.1f} %</text>')
        lines.append(f'<text x="{rx0}" y="{y + 37}" font-family="{FONT}" font-size="10.5" fill="{MUTED}">Usiterte par: {item["prior_similar_pairs"] - item["cited_pairs"]} av {item["prior_similar_pairs"]}</text>')

    lines.append("</svg>")
    (FIG_DIR / "fig2_kumulativitet_og_amnesi.svg").write_text("\n".join(lines), encoding="utf-8")


def make_fig3_methods_and_ethics(res: dict) -> None:
    """Figur 3: Metodisk og forskingsetisk profil i fulltekstkorpuset (heile korpuset vs kjernekanalar)."""
    W, H = 880, 390
    p3 = res["P3_falsifiability"]
    p5 = res["P5_process_justification"]
    p9 = res["P9_ethics_accountability"]
    p10 = res["P10_validated_measurement"]

    metrics = [
        ("Prosessmetodar (workshop/probe/RtD)", p5["process_method_share"] * 100, p5["process_method_share"] * 100),
        ("Open fortolkingsprosa (illustrerer/opnar)", p3["interpretive_open_discourse_share"] * 100, p3["interpretive_open_discourse_share"] * 100),
        ("Inferensstatistikk (p-verdi / ANOVA / KI)", p3["inferential_stats_all_share"] * 100, p3["inferential_stats_flagship_share"] * 100),
        ("Validert måleinstrument / reliabilitet", p10["any_validated_or_psychometric_share"] * 100, p10["flagship_validated_or_psychometric_share"] * 100),
        ("Etisk nemndgodkjenning (menneskestudiar)", p9["with_ethics_board_approval_share"] * 100, p9["flagship_human_studies_with_ethics_board_share"] * 100),
        ("Negative funn eller null-utfall", p5["negative_or_null_outcome_share"] * 100, p5["flagship_negative_outcome_share"] * 100),
        ("Formelle hypotesar (H0/H1/testbar)", p3["formal_hypothesis_all_share"] * 100, p3["formal_hypothesis_flagship_share"] * 100),
        ("Opne rådata eller kodearkiv", p10["open_data_or_code_share"] * 100, p10["flagship_open_data_share"] * 100),
        ("Preregistrert studieprotokoll", p3["preregistered_share"] * 100, 0.0),
    ]

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
        f'<rect width="{W}" height="{H}" fill="{PAPER}"/>',
        f'<text x="24" y="30" font-family="{FONT}" font-size="15" font-weight="700" fill="{INK}">Figur 3. Metodisk asymmetri i fulltekst (P3, P5, P9, P10): Prosessprosa vs streng etterprøving</text>',
        f'<rect x="24" y="42" width="12" height="8" fill="#8d99ae"/><text x="42" y="50" font-family="{FONT}" font-size="11.5" fill="{MUTED}">Alle fulltekstar (n = {p3["n_fulltext"]})</text>',
        f'<rect x="220" y="42" width="12" height="8" fill="{INK}"/><text x="238" y="50" font-family="{FONT}" font-size="11.5" fill="{MUTED}">Dedikerte designtidsskrift/-konferansar (n = {p3["n_flagship_fulltext"]})</text>',
        f'<line x1="24" y1="60" x2="{W - 24}" y2="60" stroke="{INK}" stroke-width="1"/>',
    ]

    x0, y0, max_w = 305, 76, 470
    for idx, (lbl, v_all, v_flag) in enumerate(metrics):
        y = y0 + idx * 33
        w1 = (v_all / 100.0) * max_w
        w2 = (v_flag / 100.0) * max_w
        lines.append(f'<text x="{x0 - 12}" y="{y + 13}" text-anchor="end" font-family="{FONT}" font-size="11.5" fill="{INK}">{esc(lbl)}</text>')
        lines.append(f'<rect x="{x0}" y="{y + 1}" width="{max(1.0, w1):.1f}" height="8" fill="#8d99ae"/>')
        lines.append(f'<rect x="{x0}" y="{y + 10}" width="{max(1.0, w2):.1f}" height="8" fill="{INK}"/>')
        lines.append(f'<text x="{x0 + max(w1, w2) + 8:.1f}" y="{y + 14}" font-family="{FONT}" font-size="11" fill="{MUTED}">{v_all:.1f} % / kjerne {v_flag:.1f} %</text>')

    lines.append("</svg>")
    (FIG_DIR / "fig3_metode_og_etikkprofil.svg").write_text("\n".join(lines), encoding="utf-8")


def make_fig4_external_fields(res: dict) -> None:
    """Figur 4: Fagfelt som siterer nordisk designteori globalt (P4)."""
    W, H = 880, 380
    flds = list(res["P4_external_impact"]["citing_fields_top12"].items())[:10]
    tot = sum(v for _, v in res["P4_external_impact"]["citing_fields_top12"].items()) or 1

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
        f'<rect width="{W}" height="{H}" fill="{PAPER}"/>',
        f'<text x="24" y="30" font-family="{FONT}" font-size="15" font-weight="700" fill="{INK}">Figur 4. Kven siterer nordisk designteori? Global feltfordeling i OpenAlex (P4)</text>',
        f'<text x="24" y="49" font-family="{FONT}" font-size="12" fill="{MUTED}">Fordeling av siterande arbeid på topp-10 fagfelt; natur- og livsvitskap utgjer samla {res["P4_external_impact"]["citing_natural_and_basic_sciences_share"]*100:.1f} %</text>',
        f'<line x1="24" y1="60" x2="{W - 24}" y2="60" stroke="{INK}" stroke-width="1"/>',
    ]

    x0, y0, max_w = 290, 78, 460
    max_pct = max((100.0 * c / tot for _, c in flds), default=1.0)
    for idx, (fname, cnt) in enumerate(flds):
        pct = 100.0 * cnt / tot
        w_bar = (pct / max_pct) * max_w
        y = y0 + idx * 28
        col = ACCENT if idx < 3 else "#7a7870"
        lines.append(f'<text x="{x0 - 12}" y="{y + 14}" text-anchor="end" font-family="{FONT}" font-size="11.5" fill="{INK}">{esc(fname)}</text>')
        lines.append(f'<rect x="{x0}" y="{y + 2}" width="{max(1.5, w_bar):.1f}" height="15" fill="{col}"/>')
        lines.append(f'<text x="{x0 + w_bar + 8:.1f}" y="{y + 14}" font-family="{FONT}" font-size="11" fill="{INK}">{pct:.1f} % ({cnt:,})</text>')

    lines.append("</svg>")
    (FIG_DIR / "fig4_ekstern_siteringsfordeling.svg").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    res = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    make_fig1_forest(res)
    make_fig2_cumulativity(res)
    make_fig3_methods_and_ethics(res)
    make_fig4_external_fields(res)
    print("Genererte 4 SVG-figurar i", FIG_DIR)


if __name__ == "__main__":
    main()

