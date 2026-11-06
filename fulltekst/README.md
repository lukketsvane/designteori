# Fulltekstarkivet

Dette er eit offentleg spegelarkiv for originaldokument med identifisert
lisens for vidarefordeling. Arbeida er **ikkje** frigjevne under éin felles
lisens. Rettane står i kvar PDF og i [manifest.json](manifest.json).

- [manifest.csv](manifest.csv): tittel, DOI, forfattarar, kjelde, lisens, SHA-256 og filer.
- [pdf/](pdf/): uendra PDF-ar med dokumentert redistribusjonsløyve.
- [tekst/](tekst/): rein, automatisk tekstuttrekking frå PDF-filer med lisens som tillèt omarbeidd versjon. Layout er tapt; bruk original-PDF ved sitering.
- [andre_oa_kandidatar.csv](andre_oa_kandidatar.csv): PDF-ar med tilgjengeleg original-URL, men utan stadfesta rett til ny publisering her.

## Første arkivering, 6. november 2026

14 PDF-ar vart kontrollerte mot eksplisitte CC-lisensar i sjølve dokumenta,
nokre først på dei siste sidene, med original kjeldelenkje, DOI,
forfattarar og hash i manifestet. 13 tekstuttrekk høyrer til
lisensar som tillèt tilpassingar.
Éin CC BY-NC-ND-fulltekst er publisert som uendra original PDF utan
separat tekstutgåve. NC-lisensierte verk er berre delte her som del av
eit ikkje-kommersielt forskingsarkiv. Lisensvilkåra følgjer kvar fil,
uavhengig av om arkivet blir brukt i andre samanhengar.

Dokument som berre har open access/lesetilgang, blir **ikkje** automatisk
spegla. Eit tidsskrift, ein DOI eller eit institusjonsarkiv kan vere ope
utan at vidarepublisering er tillaten. Rettsstatus må knytast til rett
manifestasjon av det aktuelle verket, ikkje berre til DOI-en.

## Reprodusering

Med originalfilene lagra lokalt på CYGNUS, køyr:

```powershell
python arkiver_fulltekst.py --source "C:\\...\\data\\oa_fulltexts_private"
python bygg_katalog.py
python test_publisering.py
```

Skriptet `arkiver_fulltekst.py` speglar **berre** manuelt oppførte
lisensgodkjende PDF-ar; det legg aldri ukjende dokument til ved å sjå
etter uttrykket «open access». Nye verk må gjennomgåast før publisering.

## Opphavsrett

For kvar fil skal sitering normalt vise:
forfattar(ar), år, original tittel, publikasjonsstad, DOI,
kjelde-/original-URL og konkret CC-lisens med lenkje.
Tekstuttrekka er ei teknisk tilpassing utan fagleg revisjon.
Ved motstrid i lisensopplysningar, eller dersom eit dokument er feil
arkivert, må fila takast ut av spegelen til rettsstatus er avklart.
