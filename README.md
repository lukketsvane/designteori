# DESIGNTEORI

Open, søkbar database for nordisk designteori. Målet er å samle publiserte designteoretiske artiklar frå Noreg, Sverige, Danmark, Finland og Island på éin stad.

**Status:** 7 300 OpenAlex-registreringar (6 060 artiklar), 54 nordiske kjeldekandidatar og 407 provisoriske historiske/internasjonale teorioppføringar. **14 PDF-ar** har dokumentert lisens og er offentleg arkiverte. Dette er enno ikkje eit fullstendig, manuelt verifisert korpus.

**[Søk](https://lukketsvane.github.io/designteori/)** · [OpenAlex (CSV)](docs/data/publications.csv) · [SQLite](data/designteori_hovuddatabase.sqlite.gz) · [PDF-innsamling](fulltekst/INNSAMLING.md)

Bidrag og rettingar er velkomne via pull requests. Kjelde, DOI og publikasjonsår skal vere etterprøvbare.

[Datakvalitet](docs/data/corpus_quality.json) · lokalt søk: `python scripts/sok_korpus.py "design methods" --layer all`. Kandidatar er ikkje verifiserte verk.

**DOI-CSV:** Legg ei fil med `doi`-kolonne i `doi_liste.csv`. Test: `python scripts/hent_doi_csv.py --input doi_liste.csv`. Start OA-innsamling: `.\hent_tusen_pdfar.ps1 -DoiCsvPath doi_liste.csv -Limit 8000`. Filer og rapportar blir lagra privat, ikkje publiserte automatisk.
