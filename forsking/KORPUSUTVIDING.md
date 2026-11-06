# Utviding av korpuset

Nordisk hovudkorpus: 7 300 OpenAlex-postar frå eit avgrensa uttrekk.
Redaksjonell nordisk bibliografi: 77 kjeldeoppføringar, der 54 tidlegare
ikkje hadde eksakt identitetskopling til OpenAlex-katalogen.

## Historisk og internasjonalt register

`python bygg_teoriregister.py` grupperer dei 430 bibliografiske
referansane etter identitetsreglar. Kvar kjeldeoppføring står att i
`results/theory_source_audit.csv`, med moglege matchar og dokumentert
grunnlag. DOI kan gje eksakt kopling til katalogen; ei lik tittel/år-
kombinasjon er berre ein kandidat for manuell vurdering.

Søkbare, men **uavklara** referansar ligg i
`docs/data/theory_additions.json`; teljingane i
`docs/data/theory_status.json`. Dette laget er skilt frå
nordiske primærpostar. Det omfattar internasjonale bøker, eldre
verk og andre referansar som ikkje er verifiserte nordiske designverk.
Ein provisorisk dublettgruppe er ikkje eit stadfesta kanonisk verk.

I søkjegrensesnittet finst desse under «Historiske / internasjonale».
Dei blir ikkje rekna som nordiske artiklar.

## Manglande metadata for refererte verk

`python bygg_referansefrontier.py --limit 5000 --min-citing 2`
produserer ei separat prioritert kø av OpenAlex-ID-ar som er siterte,
men manglar i det lokale uttrekket. Køa dokumenterer referansar,
ikkje nye publikasjonar. Relevans, forfattarar, DOI, institusjonstilknyting,
verkstilhøve og dokumentrettar må validerast før full inkludering.

## Utvalskritikk

Verken OpenAlex-uttrekket eller historiebibliografien er eit
representativt eller fullstendig register over designforsking.
Råmetadata, rekonstruert identitet, fagleg relevans, fulltekst og
dobbelkoda evidens blir rapporterte separat. Særleg P02 og P07
krev lesing av den konkrete siteringsfunksjonen og verifisert
fagleg vidareføring.
