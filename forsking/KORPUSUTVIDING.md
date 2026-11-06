# Utviding av publikasjonskorpuset

Målet er å oppdage **fleire reelle publikasjonar** og prøve forskingskritikken
med eit korpus der identitet, tilknyting og evidensgrad kan ettergåast.

## Referansefrontier (nettverksfri kø)

`python bygg_referansefrontier.py --limit 5000 --min-citing 2`

Finn refererte OpenAlex-ID-ar som **ikkje** finst i `works`-tabellen,
rangert etter kor mange kjende publikasjonar som siterer dei. Utgangen
`results/reference_frontier_priority.csv` har ID, siteringsgrunnlag,
døme på siterande verk og eventuelle koplingar til historisk bibliografi.
`results/reference_frontier_status.json` gjev fullstendige teljingar.
`python -m unittest test_reference_frontier` testar vilkåra utan nettverk.

Desse ID-ane kan vere artiklar, bøker, arbeid utan nordisk tilknyting,
feiltilskrivingar eller dublettar. Dei er **ikkje nye verifiserte
publikasjonar**. Verifisering av tittel, DOI, forfattar, år, nordisk
institusjonstilknyting og fagleg relevans må skje ved kjelda før ein
kan slå fast kor mange nye unike verk som er oppdaga.

## Metodologisk samanlikningslitteratur

`forsking/EKSTERNE_METODESTUDIAR.csv` inneheld seks publiserte/omtala
metodologiske forskingsarbeid med kjeldelenkjer for den pågåande
prøvinga av P01–P10. Desse er eit **eksternt samanlikningskorpus**,
ikkje seks nye nordiske designteoriartiklar. Metadata og årstal er
utgangspunkt for vidare verifikasjon, ikkje fulltekstlesne kodingsfunn.

## Neste import med nye verk

Nordiske metadataeksportar går framleis i
`imports/<kjelde>/`, og vert avstemde med `batch_import_norden.py`
og `samkoyr_norden.py`. I dette steget er ikkje nye metadata henta
frå NVA/DiVA/OpenAlex fordi kjeldetilgang ikkje var tilgjengeleg.
Kandidatane må handsamast utan å løfte usikre DOI-/tittelmatchar til
verifisert status. Sjølv ein omfattande referansefrontier må ikkje
forvekslast med representativ dekning av forskingsfeltet.
