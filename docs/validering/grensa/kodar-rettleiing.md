# Rettleiing til kodarane: er verket designforsking?

Du får eit ark med 400 verk (fil `kodeark_kodar_A.csv` eller `kodeark_kodar_B.csv`). Fyll ut éi kolonne, `design_research`, med **yes**, **no** eller **unclear**. Du veit ikkje om verket er med i korpuset eller ikkje, og det skal du ikkje prøve å finne ut. Kolonnen `merknad` er valfri.

## Spørsmålet

Ut frå tittel, kanal og samandrag: **er verket ei undersøking av design, eller gjort med design som metode?** Med design meiner vi å utforme eller forme artefaktar, tenester, system, rom eller praksisar med vilje, og kunnskapen om slik utforming.

- **yes**: design (utforminga, praksisen, teorien, metodane, utdanninga, historia eller dei utforma tinga) er sjølve emnet for verket, eller verket bruker design som metode for å finne noko ut. Døme på kva som tel: ein studie av korleis designarbeid går føre seg, ein designhistorisk studie, eit prosjekt der ein utformar og testar eit prototypesett for å lære noko, ein tekst om undervisning i design.
- **no**: verket brukar ordet design i ein annan tyding (til dømes studiedesign, forskingsdesign, utforming av ein algoritme, krins eller medisin), eller emnet ligg utanfor design (til dømes klinisk forsking, reint teknisk utvikling utan spørsmål om utforming, forvaltning). Eit verk som berre nemner design i forbifarten er **no**.
- **unclear**: du kan ikkje avgjere ut frå det du har. Bruk det når tittelen og samandraget ikkje rekk, ikkje som standard for vanskelege tilfelle. Skriv gjerne kvifor i `merknad`.

## Slik går du fram

1. Les tittel, kanal og år i arket. Opne lenkja i `abstract_link` og les samandraget. Les ikkje heile teksten. Er lenkja død, kode ut frå tittel og kanal, og skriv «lenkje feil» i `merknad`.
2. Bruk høgst tre minutt per verk.
3. Døm det verket seier om seg sjølv, ikkje kor godt det er, kor mykje det er sitert eller kva du trur om kanalen. Det er ikkje ei vurdering av feltet eller av forfattarane.
4. Kode åleine og i same rekkjefølgje som i arket ditt. Ikkje snakk med den andre kodaren om einskildverk før begge er ferdige.
5. Ikkje søk opp verket i andre kjelder for å sjå om det «er med» eller «ikkje er med» i ei samling.
6. Ein del verk står utan kanalnamn (29 av 400), og to titlar kan stå to gonger. Kode dei som vanleg.

## Kva som skjer med koden

Arka er trekte med fast frø (20261113) og stratifiserte på inngangsrute, periode og slag, 50 verk per rute. Delen yes i arket er difor ikkje delen i korpuset. Prosjektet har ein eigen nøkkel med vekter som blir brukt først etter at begge kodar er ferdige. Etterpå reknar vi samsvar mellom kodarane (kappa og del like svar, med unclear som eiga kategori) og vektar delen yes for dei som kom inn og dei som blei haldne ute. Verk der kodarane er ueinige går til ei tredje lesing.
