# DESIGNTEORI

**Ope, etterprøvbart forskingskorpus for nordisk designteori og designforsking (1983–2026).**

Nettarbeidsbenk (GitHub Pages): **https://lukketsvane.github.io/designteori/**

Korpuset har 6 432 registrerte postar (om lag 6 236 ulike verk): 4 694 frå OpenAlex-laget og 1 738 frå nordiske nasjonalarkiv og konferanseseriar (NVA/Cristin, Nordes, DiVA, Aaltodoc, KGL og IRIS).

## Nettarbeidsbenken (`docs/`)

Alle sidene er statiske filer i `docs/`; ingen server og ingen API-nøkkel trengst.

| Side / fane | Innhald |
|---|---|
| `docs/` (`katalog`) | Ordsøk, ordliste, meiningssøk i nettlesaren (EmbeddingGemma-300m), samandrag, PDF-lenkjer, leseliste og eksport (BibTeX, RIS, CSV) |
| `docs/utforsk/` | Interaktiv utforskar for alle 6 432 postane: semantisk kart, medforfattar- og institusjonsnett, verdskart, siteringar og tidsliner |
| `docs/funn/` | Biletutgåva av korpusmetaanalysen (runde 1 og 2): 18 konsoliderte figurar (`f01`–`f18`, delar `d01`–`d36`), 164 kontrollerte funn og 24 spørsmål |
| `docs/metaanalyse/` | Fullstendig skriftleg metaanalyserapport for runde 1 og 2 |
| `docs/#siteringar` (`kanon`), `#kart`, `#analyse`, `#teorielement` (`teori`), `#om` | Kanonoversikt, klyngekart over 8 hovudklynger og 52 underklynger, deskriptiv analyse, pilotbase over teorielement og dokumentasjon av korpus og søk |
| `docs/validering/` | Rettleiing, tomme kodeark (`kodeark-del-a.xlsx`, `kodeark-del-b.xlsx`) og skript for kodarsamsvar (`semje.py`; syntetiske testfiler i `semje.json` / `*-{A,B}.xlsx`), samt grensekodeark (`grensa/`) for 400 verk |

For historisk samanlikning ligg den tidlegare metavitskaplege studien av ti vitskapsteoretiske påstandar (`P1`–`P10`, 07.11.2026) i [`gransking/`](gransking/README.md).

## Søk og samandrag på nettsida

Alt søkedata ligg som statiske filer i `docs/data/search/`. Kva som er i filene og korleis dei vert bygde:

| Fil | Innhald |
|---|---|
| `meta.json` | Verk i fast rekkjefølgje (`ids`), kode per verk for språk, samandrag, tilgang og merking, tal, filhasjar og `build_id` |
| `search_config.json` | Stoppord, ordliste (norsk/svensk/dansk til engelsk), eksempelsøk |
| `lex.json` | Ordindeks for BM25 (tittel, forfattar, tidsskrift, tilknyting, samandrag) |
| `access.json` | PDF-lenkje per verk, med nivået `h` (kopi i `pdf/`), `v` (kontrollert), `u` (ikkje kontrollert) |
| `abstracts/aNNN.json` | Samandrag i skjervar à 128 verk, med kjelde (`oa` frå OpenAlex, `x` utdrag frå open PDF) |
| `vectors.i8`, `similar.bin`, `query_vectors.json` | Innbygging (EmbeddingGemma-300m, 256 dimensjonar, int8), 20 næraste verk per verk og lagra spørjevektorar |
| `about.json`, `glossary.json`, `search_quality.json` | Tal om korpuset, ordliste, målt søkjekvalitet (recall@10) |
| `benchmark_queries.json`, `parity.json`, `abstracts_report.json` | Testspørjingar med relevansvurdering, fasit for JavaScript-testen, rapport om utdraget |

Bygging av søkjefilene (kvart steg kan køyrast om att; `meta.json` vert skriven sist):

```bash
python designteori.py build-search --stage lexical        # steg A: samandrag, tilgang, ordindeks, tal (utan modell)
python designteori.py build-search --stage embed --time-only 64   # tidsestimat for innbygginga
python designteori.py build-search --stage embed          # steg B: lang jobb, sjå under
python designteori.py build-search --stage finish         # steg C: naboar, spørjevektorar, kvalitet, parity, meta
python designteori.py bench-search                        # berre kvalitetsmålinga frå dei publiserte filene
python designteori.py verify                              # inkluderer kontrollane av søkjefilene
```

Steg B treng Python 3.13 med `onnxruntime` og `tokenizers` og modellfilene i den private cachen. Køyr han som éin bakgrunnsprosess med låg prioritet:
`DESIGNTEORI_ORT_CPU=1 DESIGNTEORI_ORT_THREADS=4`, `python -u`, og vektorane vert lagra i `search_doc_vectors.sqlite` i den private cachen, så ei avbroten køyring held fram der ho slapp. Ei full `python designteori.py build` kan endre rekkjefølgja på verk; då feilar `verify` til søkjefilene er bygde på nytt.

## Andre databyggjarar og validering

- **Klyngekart (`docs/data/klynger/`):** `python -u -m designteori.klynger`
- **Utforskar (`docs/data/vis/`):** `python -u -m designteori.visdata`
- **Biletutgåva av metaanalysen (`docs/data/meta/`):** `python -u -m designteori.metavis`
- **Metaanalysesida (`docs/metaanalyse/index.html`):** `python -m designteori.metaside <rapport.md>`
- **Teorielement-førebuing og kodarsamsvar:** `python teorielement/prep.py` førebur private inndata i cachen frå `teorielement/kodebok.md`; `python semje.py --sjolvtest --maskin ../data/teorielement/rader.json --utval utval.json --mal-a kodeark-del-a.xlsx --mal-b kodeark-del-b.xlsx` (frå `docs/validering/`) testar samsvarsrekninga.
- **Grensekodeark (`docs/validering/grensa/`):** `python scripts/lag_grensekodeark.py` byggjer stratifiserte blinda ark (`400` verk i `8 × 50` strata over kandidatpopulasjonen på `26 425` verk) og fasitnøkkel med Hare–Niemeyer-utvalsvekting.
- **NVA-revisjon og OpenAlex-køyring:** `python designteori.py audit-nva` kontrollerer NVA-handle-lenkjer mot `api.nva.unit.no` (`docs/data/nva_audit_report.json`); `python designteori.py rerun-nordic` nullstiller eventuelle kvote-feil og køyrer dei 18 nordiske språkspørjingane mot OpenAlex på nytt.

## Verifisering og testar

```bash
python -m compileall -q designteori.py designteori tests teorielement scripts docs/validering
python -m unittest discover -s tests -v
python -m pytest tests/test_teorielement_prep.py tests/test_teorielement_e2e.py -q
python designteori.py verify
node --test tests/js/*.test.mjs
```

Rettsreglar som testane sjekkar: ingen PDF-kopi frå den private cachen er i repoet (berre dei 23 med open lisens i `pdf/`); ingen fulltekst er publisert; samandrag frå metadata er publiserte med kjelde; eit samandrag kan berre trekkjast ut av ein PDF når verket har kontrollert open PDF eller open lisens og dokumentet i cachen har same sjekksum som den kontrollerte fila, og det er då merkt som utdrag med lenkje til kjelda; verk utan samandrag får lenkje til utgjevaren. PDF-lenkjer utan kontroll er merkte som ikkje kontrollerte.
