# DESIGNTEORI

Open, søkbar database for nordisk designteori. Målet er å samle publiserte designteoretiske artiklar frå Noreg, Sverige, Danmark, Finland og Island på éin stad.

**Status:** 7 300 OpenAlex-registreringar (6 060 artiklar), 54 nordiske kjeldekandidatar og 407 provisoriske historiske/internasjonale teorioppføringar. **15 PDF-ar** har dokumentert lisens og er offentleg arkiverte. Dette er enno ikkje eit fullstendig, manuelt verifisert korpus.

**[Søk](https://lukketsvane.github.io/designteori/)** · [PDF](https://lukketsvane.github.io/designteori/pdf.html) · [Samla korpus (CSV)](docs/data/korpus.csv) · [SQLite](data/designteori_hovuddatabase.sqlite.gz) · [PDF-innsamling](fulltekst/INNSAMLING.md)

Bidrag og rettingar er velkomne via pull requests. Kjelde, DOI og publikasjonsår skal vere etterprøvbare.

[Datakvalitet](docs/data/corpus_quality.json) · [Historisk teori](docs/data/theory_additions.json) · lokalt søk: `python sok_korpus.py "design methods" --layer all`. Kandidatar er ikkje verifiserte verk.

**DOI-CSV:** Legg ei fil med `doi`-kolonne i `doi_liste.csv`. Test: `python hent_doi_csv.py --input doi_liste.csv`. Start OA-innsamling: `.\hent_tusen_pdfar.ps1 -DoiCsvPath doi_liste.csv -Limit 8000`. Filer og rapportar blir lagra privat, ikkje publiserte automatisk.

**Generert DOI-liste:** `python bygg_doi_eksport.py` produserer [prioritert DOI-kø](results/doi_eksport.csv) og [dekningsstatistikk](results/doi_eksport_status.json). Start med `python hent_doi_csv.py --input results/doi_eksport.csv` for tørrkøyring, deretter `.\hent_tusen_pdfar.ps1 -DoiCsvPath results/doi_eksport.csv -Limit 8000` for offentleg OA-innsamling til privat cache.

Fulltekst: 15 lisensierte PDF-utgåver, der éi er ei krediterande tekstutgåve utan tredjepartsillustrasjonar. Den separate [PDF-katalogen](docs/pdf.html) viser også originalkjelder med uavklarte vidarepubliseringsrettar.
