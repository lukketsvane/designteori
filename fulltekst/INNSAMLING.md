# PDF-innsamling

**Mål:** Finn så mange lovleg tilgjengelege fulltekstar som mogleg. Bibliografisk identitet, lesetilgang og rett til vidarepublisering er tre ulike forhold.

Køen omfattar OpenAlex-postane og dei nordiske kjeldekandidatane. `results/pdf_henteko.csv` og `docs/data/pdf_status.json` blir genererte automatisk ved push. Køa er sortert slik at artiklar, direkte PDF-liknande OA-lenkjer og høg leserangering kjem først.

## Hent PDF-ar

Køyr på ei datamaskin med internettilgang:

```bash
python hent_oa_pdf.py --download --limit 500 --lookup-openalex
```

For fleire lovlege OA-versjonar via Unpaywall:

```bash
python hent_oa_pdf.py --download --limit 8000 --lookup-openalex --email DI_EPOST
```

Fortsett frå førre runde:

```bash
python hent_oa_pdf.py --download --limit 8000 --lookup-openalex --email DI_EPOST --retry-failed
```

Skriptet sjekkar OA-lenkjer og valfrie Unpaywall/OpenAlex-lokasjonar, følgjer berre offentlege HTTPS-omdirigeringar, avgrensar filstorleik, sjekkar PDF-signatur, ventar mellom førespurnader og tek vare på framdrifta. Ved HTTP 401/403, betalingsmur, HTML i staden for PDF eller manglande tilgang blir dokumentet ikkje henta. Inga kringgåing av tilgangen.

Nedlasta PDF-ar ligg i **`data/oa_fulltexts_private/pdf/`**, utanfor Git-historikken. Framdriftsfila `data/oa_fulltexts_private/progress.json` gjer vidareføring mogleg. Del ikkje private eller uklårt lisensierte filer gjennom repoet.

Den offentlege søkekatalogen får berre bibliografiske metadata, kjeldelenkjer og status. Etter ei lokal innsamling kan du committe `docs/data/pdf_found.json` og `docs/data/pdf_status.json`, men ikkje dei private PDF-ane.

## Offentleg arkivering av enkeltverk

Dersom den konkrete PDF-en har eksplisitt, dokumentert løyve til vidarefordeling, undersøk lisens og rett dokumentversjon manuelt. Døme:

```bash
python publiser_lisensiert_pdf.py --id W1234567890 --license "CC BY 4.0" --evidence "CC BY 4.0, sida 1 i original-PDF" --confirm-rights
python bygg_katalog.py
python bygg_fulltekstsok.py
python bygg_hovuddatabase.py
python test_database.py
```

Dette kopierer berre éin kontrollert PDF til `fulltekst/pdf/`, oppdaterer manifestet med SHA-256 og endrar **ikkje** dei tidlegare godkjende filene. Prosessen krev aktiv stadfesting av løyvet. Ei OA-lenkje aleine gjev ikkje lov til å leggje fullteksten i det offentlege arkivet.

Merk: Dei eksisterande 14 lisensierte PDF-ane er bevarte. Også NVA, DiVA, Aalto, Chalmers og andre arkiv kan levere OA-kjelder gjennom metadataimporten, men inga tilgjengelegheits- eller lisenskontroll blir automatisk utleidd frå namnet på arkivet.
