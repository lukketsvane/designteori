# Utvalsdekning og risiko for feilslutning

**Status 6. november 2026.** Dette er intern datakvalitet i det frosne OpenAlex-uttrekket, ikkje ei måling av korleis nordisk designforsking faktisk fungerer.

## Det absolutte tilgangsproblemet

Me har **7 300** registrerte kandidatverk og **14** lisensierte PDF-ar offentleg arkiverte. Den valde køa på **336** siteringspar har **0** par med begge originalane i det offentlege fulltekstarkivet og **74** med minst éin.

Dette er det viktigaste praktiske hinderet for å teste P02 (kumulativitet) og P04 (overføringsverdi): Me kan ikkje lese ei faktisk vidareprøving utan både eldre påstand og nyare bruk. Null dokumentert test i denne arbeidskøa er **ikkje** null forsking.

## Samanlikning av utvalstypar

| Delramme | Par | Begge i auto-tittelramma | Begge med DOI | Begge med OA-metadata-URL | Negative årsgap | Median årsgap |
|---|---:|---:|---:|---:|---:|---:|
| Heile interne grafen | 5502 | 57.4 % | 94.1 % | 44.1 % | 28 | 5.0 |
| Tilfeldige kontrollpar | 120 | 60.0 % | 92.5 % | 36.7 % | 2 | 4.0 |
| Målretta motprøvekandidatar | 150 | 100.0 % | 94.7 % | 46.0 % | 0 | 5.0 |
| PDF-tilgjengelege siterande | 71 | 85.9 % | 95.8 % | 43.7 % | 0 | 5 |
| Samla arbeidskø | 336 | 82.7 % | 94.3 % | 42.0 % | 2 | 5.0 |

Tabellen viser skilnader mellom **utvalsrutene**. Målretta treff kan ikkje representere faget; tilfeldig kontroll representerer berre interne kantar i det aktuelle metadatauttrekket. Med OA-URL meiner me at ei registrert lenkje finst, ikkje at PDF er lesbar eller lovleg å spegle.

## Årsvask og utvalsfeil

Me fann **28** interne siteringskoplingar der OpenAlex-året for siterande verk er eldre enn året for referert verk. Desse er lagde i [revisjonskø](REVISJON_ARSTAL_I_SITERINGAR.csv). Årsskilje kan kome av online-first, bokkapittel/utgåver, feil metadata eller feil identitetskopling. Det skal ikkje automatisk tolkast som oppdikta siteringar.

## Konsekvens for P01–P10

Studie A treng fleire lovleg tilgjengelege fulltekstar i **begge endar av siteringspar**, sidan kvar vurdering krev dokumenterte sider. Studie B og C treng offentlege institusjonsdokument, oppdragsloggar, evalueringar og habilitetshistorikk; slikt kan ikkje rekonstruerast ut frå bibliometriske signal. Kravet om to uavhengige faglege kodarar står uendra, og ingen av arbeidsfelta i blinde skjema er fylte.
