# DESIGNTEORI: program for eit stort, ope forskingsarkiv

## Overordna mål

Byggje ein open, etterprøvbar og langsiktig database over publisert designteori,
med Norden som systematisk kartlagt kjerne og med globale kjelder når dei er
nødvendige for å dokumentere faglege slektskapslinjer. Eit stort tal metadata-
treff er ikkje eit mål i seg sjølv. Dekning, kjeldebevis, fulltekst og fagleg
etterprøvbarheit skal kunne rapporterast kvar for seg.

**Status 6. november 2026:** 7 300 metadataregistreringar, av dei 3 729
automatisk tittelinkluderte og 3 571 i manuell vurderingskø. Ingen av desse
tala dokumenterer eit fullstendig forskingsfelt. Fulltekstarkivet vart starta
med 11 lisensgjennomgåtte PDF-filer og lenkjer til dei resterande OA-kandidatane.

## Definer populasjon før statistikk

For kvar publikasjon må desse tre eigenskapane skiljast:
- Nordisk **forfattar/institusjonstilknyting** (Noreg, Sverige, Danmark, Finland, Island og eventuelle sjølvstyrte område med eigne kodar).
- Nordisk **utgjevar/utgjevingsstad**, som ikkje nødvendigvis er nordisk forsking.
- Nordisk **forskingstema/empiri**, som også internasjonale forskarar kan studere.

Nordisk språk er ein fjerde, uavhengig eigenskap. Ingen av dei fire er automatisk
ekvivalente. Kjernekorpuset skal ikkje avgrensast til tekstar på engelsk. Åra
2000–2026 er første gjennomførte uttrekk, ikkje ein endeleg historisk grense.
Eit separat historisk korpus skal etter kvart omfatte eldre publikasjonar.

## Kjelder som må kombinerast

1. **NVA (Noreg):** publikasjonar, doktoravhandlingar, institusjonar, DOI og eventuelle repositorieversjonar.
2. **DiVA, SwePub og Chalmers (Sverige):** særleg avhandlingar, svenskpråkleg designteori og forskingsarbeid utanfor OpenAlex.
3. **Forskningsportalen / Pure og Det Kgl. Akademi (Danmark):** designfilosofi, CEPHAD og bokkapittel.
4. **Aalto, Oulu og Helsingfors (Finland):** kunstnarleg forsking, handverksforsking, teori og fulltekstar.
5. **IRIS og Skemman (Island):** avhandlingar og lokal publisering.
6. **OpenAlex, Crossref, DataCite, DOAJ, OpenAIRE og ORCID:** identifikatorar, siteringar, metadata- og OA-kontroll.
7. **Tidsskrift, forlag og faglege konferansar:** FormAkademisk, Nordes, DRS, IASDR, Design Studies, Design Issues, Design Science, Artifact og tilgrensande fag.
8. **Bibliotek og katalogar:** bøker, antologiar, redigerte verk, eldre designteori og forskingsarbeid utan DOI.

Kjeldedata frå ulike register skal lagrast med proveniens, dato, original ID og
dato for verifikasjon. Bøker, avhandlingar og monografiar skal ha same status
som artiklar i innsamlinga, men vere eigne sjangrar i analysane.

## Datamodell: frå treff til kunnskapsarkiv

**Work:** kanonisk verk-ID; DOI, ISBN/ISSN, OpenAlex/NVA/DiVA-ID; tittel,
varianttitlar, språk, år, utgjevingsstad, forfattarar, forskingsinstitusjonar,
tema, kjeldetilvisingar, status og versjonshistorikk.

**Manifestation:** publisert PDF, akseptert manus, preprint, trykt bok,
omsetjing eller arkivkopi. Skil ulike manifestasjonar frå verkelege ulike verk.
Lagra filhash, sidetal, format, kjelde-URL og lisens for kvar versjon.

**Evidence/claims:** konkrete påstandar, definisjonar, hypotesar, formelle
modellar, resultat, negative resultat, arbeidsmåtar, datakjelder, figurar og
sidereferansar. Automatisk språkattkjenning er forslag, ikkje forskingsfunn.

**Relations:** «siterer» kan importerast automatisk; «byggjer vidare på»,
«testar», «replikerer», «motseier», «reviderer» og «låner omgrep frå» krev
kjeldebevis i fulltekst og uavhengig koding.

**Rights/access:** DOI og OA-lenkje er ikkje lisens. For offentleg spegling av
PDF eller tekst må redistribusjonsrett registrerast med lisens, kjelde, dato
og helst dokumentert løyve. Kvar fil får ein egen SHA-256. Filer utan påvist
rett vert katalogiserte og lenkja til, ikkje spegla automatisk.

## Kvalitetsnivå

1. Oppdaga metadata: ikkje fagleg kontrollert.
2. Identitet kontrollert: DOI, tittel, år, forfattarar og versjon skilde.
3. Relevans kontrollert: publikasjonsform og designteoretisk innhald vurdert.
4. Fulltekst kontrollert: komplett tekst, sidetal, rettar og rett versjon.
5. Fagleg koda: utsegner, metode og kjeldebruk dokumenterte med sidetal.
6. Dobbelkoda: to uavhengige vurderarar, usemje logga og reliabilitet vurdert.

Ingen publikasjon skal få høgare nivå fordi eit språkmodell-svar, eit
metadatafelt eller eit referansetreff såg truverdig ut.

## Faglege tema

Grunnlagsteori (ontologi og epistemologi); form-/funksjons- og artefaktteori;
designmetodikk; research through design; vitskapsteori og metodologi;
estetikk; etikk; økologi; systems-oriented design; tenestedesign;
interaksjonsdesign; participatory design; handverksvitskap; designhistorie;
designprofesjon; feministisk/postkolonial/kritisk teori; designpedagogikk.
Fleire merkelappar per verk. Maskinelle kandidatar skal merkjast som maskinelle.

## Arbeidspakker, i prioritert rekkjefølgje

**A. Bevar og publiser:** metadataarkiv, kode, søk, siteringsnettverk, figurar,
bibliografi, dokumentert fulltekst og lisensmatrise. Fullfør metadata-revisjon
og medhaldskontroll for eksisterande korpus.

**B. Dekk det som manglar:** bygg separate importløyper for NVA, DiVA, Aalto,
dansk forskingsportal og islandske arkiv. Rapporter nye unike ID-ar,
dublettar, søkjeresultat og manuelle avvisingar. Bruk årsspesifikke søk eller
kjeldefulle dumpar, ikkje berre relevanssorterte toppsider.

**C. Fulltekst:** oppdag lovlege utgåver, sjekk rettar, spegl CC/PD-tekstar,
registrer PDF + lesbar tekst + format; bygg søk på tvers av heile fullteksten.
Lag offentleg katalog for dokument som berre kan lenkjast til.

**D. Fagleg teoriindeks:** manus med tydelege definisjonar, testbare eller
ikkje-testbare påstandar, empirisk/teoretisk metode og referansefunksjon.
Grunnlagsteori må kunne skillast frå generell «design»-bruk i andre fag.

**E. Etterprøv faktisk kunnskapsvekst:** bruk kodeboka til å teste
vidarebygging, prøving, falsifikasjon, kritikk og teoretisk revisjon over tid.
Rapporter både bekreftande og avkreftande døme, kontroller for sjanger og alder,
og samanlikn med relevante andre disiplinar. Ikkje døm på førehand.

**F. Offentleg forskingsatlas:** søk, filter, DOI-/fulltekstlenkjer, kart over
forfattarar og institusjonar, siteringsgrafar, datasettnedlasting og
dokumenterte endringar per import.

## Kva «rikast» må bety

Omfang må etter kvart samanliknast med etablerte bibliografiar og korpus,
med identiske populasjonsgrenser. Eit seriøst kvalitetsmål er eit
**publikasjonskorpus med sporbar dekning og verifiserbare relasjonar**, ikkje
berre det største ufiltrerte talet på moglege treff.

Følg separat: tal registrerte verk, identitetsverifiserte verk,
fagleg inkluderingsgrad, OA-lenkjedekning, spegla fulltekstar med lovleg
redistribusjon, sider manuelt kontrollerte, påstandar med sidebevis,
dobbelkoda vurderingar, dublettar og kjeldedekning. Rapporter både tal og
uvisse. Held ein desse måla skilde, kan arkivet vekse utan å verte falsk presist.
