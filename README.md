# DESIGNTEORI

**Ope, etterprøvbart forskingskorpus for nordisk designteori og designforsking (1900–2026).**

Nettarbeidsbenk (GitHub Pages): **https://lukketsvane.github.io/designteori/**

---

## Heilskapleg arkitektur

Repoet samlar metadata, fulltekst-PDF-ar, siteringsnettverk, Google-embeddingar og empirisk analyse i éin samla arkitektur på `main`:

- **`designteori.py` + `designteori/`** — éin kommandolinjeklient og éin modulær Python-pakke for innsamling, avstemming, PDF-henting, sideindeksering, Google-embeddingar, hybridsøk, analyse og verifisering.
- **`pdf/` + `pdf/manifest.json`** — tusenvis av SHA-256-verifiserte Open Access fulltekst-PDF-ar direkte i repoet, klare for personleg forsking, tekstutvinning og siterbar sideanalyse.
- **`data/designteori.sqlite.gz`** — éin samla relasjonsdatabase (SQLite + FTS5) med OpenAlex-verk (`1900–2026`), nordiske arkivkandidatar (`Cristin/NVA`, `DiVA`, `Aaltodoc`, `tidsskrift.dk/AAU`, `IRIS/Skemman`, `Nordes/DRS`), historiske BibTeX-referansar, siteringsgraf, sitert grunnlagskanon, PDF-register og **Google `EmbeddingGemma-300M`**-vektorar for alle verk.
- **`docs/`** — forskingsarbeidsbenk på GitHub Pages med fritekstsøk, semantisk vektorsøk (Google `EmbeddingGemma-300M`), fulltekst-PDF-katalog, siteringsutforskar, interaktivt 2D semantisk kart og empirisk analyse på tvers av Noreg (`NO`), Sverige (`SE`), Danmark (`DK`), Finland (`FI`) og Island (`IS`).

## Kjeldelag og vitskapleg etterprøvbarheit

Korpuset held ulike kjeldelag eksplisitt åtskilde utan automatisk samansmelting:

1. **OpenAlex primærkorpus (`1900–2026`, `NO/SE/DK/FI/IS`)** — komplette nordiske årgangar frå 17 sentrale designtidsskrift (*Design Studies*, *Design Issues*, *FormAkademisk*, *CoDesign*, *International Journal of Design*, *The Design Journal*, *She Ji*, *Journal of Design History*, *Design and Culture*, *Artifact*, *Design Science* m.fl.), 6 nordiske design- og arkitekturhøgskular (AHO, Konstfack, Designskolen Kolding, Det Kongelige Akademi, Arkitektskolen Aarhus, Listaháskóli Íslands), fleirspråklege søk på engelsk og fem nordiske språk samt siteringsfrontieren.
2. **Nordiske nasjonale og institusjonelle arkiv (`imports/`)** — Noreg (`nva`/Cristin), Sverige (`diva`), Finland (`aalto`/Aaltodoc), Danmark (`kgl`/`tidsskrift.dk`), Island (`iris`) og `nordes`/Design Research Society (`10.21606`).
3. **Historisk og redaksjonell bibliografi (`bibliografi/`)** — kuraterte nordiske og internasjonale designteoretiske referansar.

## Bruk frå kommandolinja

```bash
pip install -r requirements.txt

# 1. Verifiser heile korpuset, SQLite-databasen, PDF-manifestet og Google-embeddingane
python designteori.py verify

# 2. Hybridsøk (FTS5 + Google EmbeddingGemma-300M + siterbare PDF-sider)
python designteori.py search "participatory design workplace democracy"
python designteori.py search "designteori formgjeving" --country NO --pdf-only

# 3. Oppdater kjelder, hent nye Open Access PDF-ar, indekser fulltekst og bygg alt på nytt
python designteori.py collect
python designteori.py harvest-pdf --limit 8000 --workers 12
python designteori.py index-pdf --workers 6
python designteori.py embed
python designteori.py build
```

## Testar

```bash
python -m unittest discover -s tests -
