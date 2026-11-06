# Hent tusenvis av PDF-ar

Korpuset har 7 354 registreringar. Hentekøen har 4 565 OA-lenkjer, der 1 707 ser ut som direkte PDF-adresser. Dette er **kandidatar**, ikkje ferdig nedlasta eller fagleg godkjende dokument. Dei 14 lisenskontrollerte PDF-ane i `fulltekst/` blir bevarte.

## Start innsamlinga

På Windows, frå repository-mappa:

```powershell
.\hent_tusen_pdfar.ps1 -Limit 8000
```

På Linux/macOS:

```bash
bash hent_tusen_pdfar.sh
```

Med Unpaywall (valfritt, krev ein ekte e-postadresse):

```powershell
.\hent_tusen_pdfar.ps1 -Limit 8000 -Email "din.epost@ditt.domene"
```

Skriptet hentar berre direkte tilgjengelege PDF-ar frå offentlege OA-lenkjer, arkiv og eventuelt OpenAlex/Unpaywall. Det gjenopptar samlinga, lagrar SHA-256 og stansar ved plassmangel eller API-grenser. Det prøver ikkje å omgå betalingsmurar.

**Kva du faktisk får:** PDF-filene blir lagra i `data/oa_fulltexts_private/pdf/` som private filer, med `progress.json` og ein etterkontrollert `pdf_local_index.csv` med tittel, DOI, forfattar, filsti, kjelde og checksum. Etter kvar køyring viser `pdf_archive_report.py` faktiske, kontrollerte PDF-filer på disk, ikkje berre nettlenkjer. Kjør `python pdf_archive_report.py --failed` for feila hentingar.

For store samlingar bør du bruke ein eigen disk:

```powershell
$env:DESIGNTEORI_PDF_CACHE = "D:\\Forsking\\designteori-pdf"
.\hent_tusen_pdfar.ps1 -MaxCacheGB 100 -MinFreeGB 10 -Limit 8000
```

Med standardinnstillingane stoppar innsamlinga ved 30 GB i cache eller når det er mindre enn 2 GB ledig diskplass. Du kan dele inn køen i sekvensielle delar: `-Shards 4 -Shard 0`, deretter shard 1, 2 og 3. Ikkje køyr fleire shard-prosessar parallelt mot den same framdriftsfila.

Manglande filer, avbrot og endra PDF-ar blir fanga opp ved kontroll av filstorleik, PDF-format og SHA-256. Mislykka forsøk blir ikkje prøvde igjen i kvar køyring med mindre du brukar `-RetryFailed`. Ved HTTP 429 blir den aktuelle tenaren eller oppslagstenesta hoppa over resten av køyringa, medan andre OA-kjelder kan halde fram. Desse postane blir merkte for seinare forsøk.

## Publisering

Privat lesetilgang, open tilgang og rett til offentleg vidarepublisering er forskjellige forhold. PDF-ar med ukjent distribusjonsrett blir **ikkje committa til GitHub**. Ein bestemt PDF med individuelt kontrollert CC-lisens kan publiserast manuelt via `publiser_lisensiert_pdf.py`. Dette krev kontroll av både identitet og lisens for akkurat den PDF-versjonen.

`docs/data/pdf_found.json` og `docs/data/pdf_status.json` er metadata for søkekatalogen, ikkje PDF-filene. Prosjektet skal telje berre verifiserte nedlastingar som faktisk finst i privat cache, og berre individuelt lisensierte filer som ligg i det offentlege arkivet.

## Importer eiga DOI-liste

Ei CSV-fil kan innehalde kolonnen `doi` og valfritt `title` og `oa_url`. Tomme/ugyldige DOI-ar blir rapporterte, duplikatar blir hoppa over og DOI-ar med tvitydige katalogtreff får ein separat kontrollstatus. Inga nedlasting skjer ved berre å validere fila.

```powershell
python hent_doi_csv.py --input doi_liste.csv
.\hent_tusen_pdfar.ps1 -DoiCsvPath doi_liste.csv -Limit 8000 -MaxCacheGB 60 -MinFreeGB 5
```

Sjølvstendig Linux/macOS: `DOI_CSV=doi_liste.csv bash hent_tusen_pdfar.sh`. For Unpaywall: legg til `-Email "kontakt@institusjon.no"` i PowerShell eller set `EMAIL` i shell. Resultata kjem som `doi_csv_report.csv`, `doi_csv_summary.json`, `doi_csv_metadata.json` og lokalt PDF-indeks i git-ignorert privat cache. DOI-ar utanfor OpenAlex-korpuset blir ikkje automatisk lagt til som kvalitetssikra designforsking. Ingen betalingsmurar blir omgått og ingen PDF får offentleg redistribusjonsrett utan kontroll av lisens og versjon.
