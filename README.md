# DESIGNTEORI

**Ope, etterprøvbart forskingskorpus for nordisk designteori og designforsking (1900–2026).**

Nettarbeidsbenk (GitHub Pages): **https://lukketsvane.github.io/designteori/**


## Søk og samandrag på nettsida

Nettsida (`docs/`) har ordsøk, ordliste, søk etter meining, samandrag og PDF-lenkjer for kvart verk. Alt er statiske filer i `docs/data/search/`; ingen server, ingen nøkkel. Kva som er i filene og korleis dei vert bygde:

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

Bygging (kvart steg kan køyrast om att; meta.json vert skriven sist):

```
python designteori.py build-search --stage lexical        # steg A: samandrag, tilgang, ordindeks, tal (utan modell)
python designteori.py build-search --stage embed --time-only 64   # tidsestimat for innbygginga
python designteori.py build-search --stage embed          # steg B: lang jobb, sjå under
python designteori.py build-search --stage finish         # steg C: naboar, spørjevektorar, kvalitet, parity, meta
python designteori.py bench-search                        # berre kvalitetsmålinga frå dei publiserte filene
python designteori.py verify                              # inkluderer kontrollane av søkjefilene
```

Steg B treng Python 3.13 med `onnxruntime` og `tokenizers` og modellfilene i den private cachen. Køyr han som éin bakgrunnsprosess med låg prioritet:
`DESIGNTEORI_ORT_CPU=1 DESIGNTEORI_ORT_THREADS=4`, `python -u`, og vektorane vert lagra i `search_doc_vectors.sqlite` i den private cachen, så ei avbroten køyring held fram der ho slapp. Ei full `python designteori.py build` kan endre rekkjefølgja på verk; då feilar `verify` til søkjefilene er bygde på nytt.

Rettsreglar som testane sjekkar: ingen PDF-kopi frå den private cachen er i repoet (berre dei 23 med open lisens i `pdf/`); ingen fulltekst er publisert; samandrag frå metadata er publiserte med kjelde; eit samandrag kan berre trekkjast ut av ein PDF når verket har kontrollert open PDF eller open lisens og dokumentet i cachen har same sjekksum som den kontrollerte fila, og det er då merkt som utdrag med lenkje til kjelda; verk utan samandrag får lenkje til utgjevaren. PDF-lenkjer utan kontroll er merkte som ikkje kontrollerte.
