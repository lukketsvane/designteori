# Metavitskapleg gransking av nordisk designteori og designforsking (`gransking/`)

Denne mappa inneheld den komplette, reproduserbare kvantitative granskinga av ti vitskapsteoretiske påstandar (`P1`–`P10`) om nordisk designteori og designforsking (1900–2026), utført på det strengt avgrensa nordiske korpuset ($N = 6\,454$ verk frå Noreg, Sverige, Danmark, Finland og Island; $109\,631$ utgåande referansar; $6\,454$ `EmbeddingGemma-300M`-vektorar i $256$ dimensjonar; og $n = 1\,461$ fulltekst-PDF-ar på $28\,955$ sider / $12\,431\,220$ ord).

## Innhald i mappa

- [`artikkel.md`](./artikkel.md): Fullstendig vitskapleg artikkel på nynorsk med teoretisk rammeverk, metodikk, likningar, tabellar, innebygde vektorfigurar, validitetsdrøfting og litteraturliste.
- [`artikkel.tex`](./artikkel.tex): Tidsskriftklart LaTeX-manuskript (`babel` nynorsk, `booktabs`, `amsmath`) klart til kompilering med `pdflatex` eller `xelatex`.
- [`artikkel.pdf`](./artikkel.pdf): Ferdigkompilert PDF-utgåve av manuskriptet (`pdflatex`, 8 sider).
- [`analyse_korpus.py`](./analyse_korpus.py): Deterministisk statistisk analysemotor (frø `20261107`) som testar `P1`–`P10` med 95 % Wilson-konfidensintervall, ikkje-parametrisk bootstrap ($B = 2\,000$), Mann-Whitney $U$-test, Yates-korrigert $\chi^2$, tropisk siterings-DAG og gradbevarande nullmodellar.
- [`lag_figurar.py`](./lag_figurar.py): Genererer publiseringsklare SVG-vektorfigurar direkte frå `data/resultatsamandrag.json`.
- [`data/resultatsamandrag.json`](./data/resultatsamandrag.json): Komplette maskinlesbare testresultat og delindikatorar for `P1`–`P10`.
- [`data/tabell_hypotesetestar.csv`](./data/tabell_hypotesetestar.csv): Hovudtabell med punktanslag, utvalsstorleikar og 95 % konfidensintervall i CSV-format.
- [`figurar/`](./figurar/):
  - `fig1_hypotesetest_oversikt.svg`: Skogplott (*forest plot*) med 95 % Wilson-KI for `P1`–`P10`.
  - `fig2_kumulativitet_og_amnesi.svg`: Tropisk siteringsdjupn og semantisk amnesi etter cosinuslikskap.
  - `fig3_metode_og_etikkprofil.svg`: Metodisk og forskingsetisk asymmetri (alle fulltekstar $n = 1\,461$ mot kjernekanalar $n = 735$).
  - `fig4_ekstern_siteringsfordeling.svg`: Tverrfagleg fordeling av innkomande siteringar i OpenAlex-grafen.

## Reproduksjon

Køyr frå rotmappa i repositoriet:

```bash
py -3 gransking/analyse_korpus.py
py -3 gransking/lag_figurar.py
```
