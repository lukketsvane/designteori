# KORPUS: fulltekst og embeddingar

Korpuset er ein dokumentert samling av **verk**, **publiserte dokumentversjonar**, **PDF-filer**, **sider**, **tekstbolkar** og **embeddingar**. Desse identitetane er ikkje det same. Ein DOI kan ha fleire dokumentversjonar, og fleire postar kan vise til same PDF.

## Arkitektur

| Lag | Lagring | Innhald |
|---|---|---|
| Bibliografi | GitHub, JSON/CSV, SQLite | DOI, forfattarar, år, land, kjelde, status |
| Originalfiler | Privat disk, SHA-256 | PDF, opphavsrett, lenkje og dokumentversjon |
| Fulltekst | Privat SQLite `corpus.sqlite` | Sidetekst, kvalitet, OCR-behov og tekstbolkar |
| Semantisk indeks | Samme private SQLite | Vektorar med modell, dimensjonar og teksthash |
| Nettstad | GitHub Pages | Søkjegrensesnitt og kjeldetilvisingar, ikkje uavklart fulltekst |

Original-PDF-ane blir ikkje endra. Vektorane kan slettast eller byggjast på nytt utan å hente PDF-ane igjen. Tekstbolkane inneheld alltid sidetal og kopling til originalfil. Dei blir merkte med ein versjon, slik at endringar i chunking ikkje kan forvekslast med gamle embeddingar.

**Innsamlingsstatus:** 7 300 OpenAlex-registreringar og nordiske kjeldekandidatar. Registreringane er ikkje lik manuelt verifiserte designteoriartiklar. På CYGNUS er 26 PDF-ar i privat cache; 14 av dei ligg òg i det offentlege lisensierte arkivet. Desse tala gjeld ei lokal kontrollkøyring 6. november 2026.

## Samle nedlasta PDF-ar frå fleire lokale cacher

Dersom ei anna innsamling alt køyrer i ein eigen arbeidsmappe, må me **ikkje starte ein parallell nettverksinnsamlar**. Ferdige PDF-ar kan i staden verifiserast og importerast lokalt:

```powershell
$env:DESIGNTEORI_PDF_CACHE = "C:\Users\Iver\Documents\designteori-pdf-cache\harvester"
cd C:\Users\Iver\Documents\github\designteori-henting
py -3 pdf_archive_report.py --merge-local ".\data\oa_fulltexts_private"
py -3 bygg_fulltekstkorpus.py --build
```

Importen brukar berre filer som finst på disken. Han kontrollerer SHA-256, PDF-signatur, avslutningsmarkør og storleik, kopierer eller hardlenkjer til den private cachen og skriv atomisk framdriftsstatus. Mislykka nettverksførespurnader blir ikkje importerte. Originalar, lisensstatus og historikk blir bevarte.

## 1. Lokal fulltekst

I den reine arbeidsmappa på CYGNUS:

```powershell
$env:DESIGNTEORI_PDF_CACHE = "C:\Users\Iver\Documents\designteori-pdf-cache\harvester"
cd C:\Users\Iver\Documents\github\designteori-henting
py -3 -m pip install pypdf
py -3 bygg_fulltekstkorpus.py --build
py -3 bygg_fulltekstkorpus.py --search "participatory design" --limit 10
```

`bygg_fulltekstkorpus.py` nyttar PyMuPDF når det er installert, elles `pypdf`. Prosessen er inkrementell og byggjer FTS5. Tekstbolkane ligg innanfor éi side, slik at sitat kan etterprøvast. Filer utan nyttbart tekstlag blir merkte `needs_ocr`, ikkje fylte med oppdikta tekst. Ingen tekst blir sendt til ei skyteneste i dette steget.

## 2. Google-embeddingar

Google er primærleverandør, men modellen kan bytast:

```powershell
py -3 embedding_google.py --plan
```

Dette er ei **nettverksfri** oversikt over kor mange tekstbolkar som står att. Modellnamnet `gemini-embedding-001` er ein konfigurerbar grunnverdi, ikkje ein påstand om å vere Googles aller nyaste modell. Kontroller dei gjeldande modell-ID-ane og tilgangsvilkåra frå Google før ei stor køyring. For ein nyare kompatibel modell:

```powershell
$env:GOOGLE_EMBEDDING_MODEL = "modell-id-fra-google"
```

Etter å ha lagt `GOOGLE_API_KEY` i eit **privat miljøvariabeloppsett**, utanfor Git, kan me gjere ein avgrensa pilot:

```powershell
py -3 embedding_google.py --embed --consent-cloud --limit 100 --batch 12 --dims 768
```

Berre tekst frå lisenskontrollerte dokument som tillèt vidarebehandling blir sendt som standard. `--include-unreviewed` er eit **eige aktivt val**, som berre skal brukast dersom du har rett til å overføre desse fulltekstane til Google og vil akseptere Googles databehandling og API-prisar. CC-lisens er heller ikkje universelt bevis for rett til alle typar vidarebruk.

Embeddingar blir lagra som normaliserte float32-vektorar, kopla til `chunk_id`, modell, dimensjonar og eksakt teksthash. Ein ny modell gjev nye vektorrader og øydelegg ikkje den gamle indeksen. Forsøk **768, 1 536 og 3 072 dimensjonar** på eit felles testutval før me vel kostnad/kvalitet.

## 3. Søk med kjeldespor

```powershell
py -3 embedding_google.py --search "Korleis blir deltaking definert i nordisk designforsking?" --limit 10
```

Når embeddingar finst, blir semantisk likskap kombinert med FTS5 gjennom *reciprocal rank fusion*. Resultata har PDF, tittel, DOI, sidetal og lokal tekstbolk. Utan embeddingar finst berre nøkkelordsøk. Den første vektorsøkimplementasjonen brukar eksakt skanning; for eit stort korpus bør me byte dette søkjelaget til ein persisterande ANN-indeks, som HNSW, utan å endre dataformatet.

## 4. Kvalitet før skala

Eit stort korpus krev meir enn filteljing: DOI- og tittelavstemming, dokumentversjon, rett forfattartilknyting, publikasjonsform, verifiserbar teori-relevans, tekstkvalitet, OCR og rettar. Me bør ha eit manuelt fasitsvarsett med søkjeførespurnader på alle dei fem nordiske språka. Mål *Recall@10*, *nDCG@10*, sidetreff og feilaktige dokumenttreff for både nøkkelordsøk og Google-embeddingar.

Som neste steg bør ein PDF som inneheld viktige illustrasjonar få ei separat side-/bileteindeksering. Tekstembeddingar kan ikkje i seg sjølve søkje i teikningar, skjema eller tabellar som ikkje har kome med i tekstuttrekket.

## 5. Tryggleik og rettar

- Originalfiler, privat fulltekst, API-nøklar og embeddingar skal ikkje leggjast i det offentlege repoet.
- Dei opne metadataa må framleis kunne kontrollerast, lastast ned og brukast uavhengig av Google.
- OA-lesetilgang, forskingsbruk, sending til ein tredjeparts API og offentleg redistribusjon er ulike rettsspørsmål.
- Hald ein kopi av det private korpuset på ein annan disk. SHA-256 er kontroll mot bitrot, ikkje backup.

Køyr offline-testar med `python -m unittest -v test_fulltekstkorpus test_embedding_google`.
