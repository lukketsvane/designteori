# Kodebok for teorielement (skjema `teorielement-rows-0.2`)

Du kodar **éin tekst om gongen**. Inndata er ei tekstfil med sidemerke (`===== SIDE n =====`), delt i
DEL A (framside, samandrag, innleiing) og DEL B (konklusjon). Du skal registrere **hovudpåstandane** til teksten.

**Grunnregel:** Basen *skildrar*. Du vurderer aldri kvaliteten på ein påstand, og «ikkje oppgjeve i teksten»
er ikkje ein mangel ved teksten. Ikkje gjett, ikkje fyll inn frå eigen kunnskap, ikkje tolk inn det som ikkje står der.
Alt du registrerer må kunne peikast ut i teksten du fekk.

## Kva er ein hovudpåstand?
Ei setning (eller to) der teksten sjølv **hevdar** ein samanheng mellom omgrep: at noko fører til, er ein type av, er
del av, krev, kjem før, heng saman med, er definert som, skil seg frå, har ein eigenskap, eller at noko **bør** gjerast.
Han står i samandrag, innleiing eller konklusjon. Ta med 0–12 påstandar per tekst, dei viktigaste først.

Ta **ikkje** med: målsetjingar («denne artikkelen utforskar …»), metodeskildring, oppsummering av struktur,
reine funn utan omgrep-samanheng (tal, utval), referat av andre sine studiar som teksten ikkje sjølv byggjer på,
tittel- og tidsskriftsinfo. Redaksjonelt stoff, innhaldslister, framsider og tekstar utan påstandar gir `"claims": []`.

## Felt per påstand (JSON-objekt)
| Felt | Verdi |
|---|---|
| `pdf_page` | heiltal, sida frå `===== SIDE n =====` der utdraget står |
| `claim_location` | `abstract`, `introduction` eller `conclusion` (conclusion = DEL B) |
| `attribution` | `own` (teksten hevdar det sjølv) eller `adopted` (teksten overtek påstanden frå andre, t.d. «X (2011)») |
| `excerpt` | **ordrett** utdrag frå teksten, same språk, same skrivemåte, 1–2 setningar, maks 350 teikn. Ikkje omsett, ikkje forkort med «…», ikkje retta feil. Linjeskift kan bli til mellomrom. |
| `relation_expression` | den ordrette frasen i utdraget som uttrykkjer samanhengen (t.d. «leads to», «is a form of») |
| `relation_kind` | `kind_of`, `part_of`, `causes_or_enables`, `requires`, `precedes`, `associated_with`, `defined_as`, `differs_from`, `has_property`, `prescribes`, `other` |
| `concepts` | liste: `{"term": ordrett frå teksten, "role": "from"/"to"/"condition"/"other", "definition_status": …, "definition_excerpt": ordrett (berre når status ikkje er `not_stated`)}` |
| `scope` | `{"status":"stated","excerpt":"ordrett"}` viss teksten seier kvar påstanden gjeld (kontekst, felt, avgrensing), elles `{"status":"not_stated"}` |
| `explanation` | `{"status":"stated","excerpt":…}` viss teksten seier **korleis eller kvifor** (mekanisme), elles `{"status":"not_stated"}` |
| `prediction` | `{"status":"stated","excerpt":…}` viss teksten seier kva som vil/kan/bør skje som følgje, elles `{"status":"not_stated"}` |
| `support_status` | `reported` (teksten oppgir korleis påstanden er støtta/prøvd), `not_stated` (ingenting oppgitt), `stated_untested` (teksten seier uttrykkjeleg at han ikkje er prøvd) |
| `support` | liste (tom viss ikkje `reported`): `{"source":"this_text"/"cited_work", "form": …, "excerpt":"ordrett"}` |
| `theories` | liste: `{"name": teoriar/rammeverk teksten **sjølv** seier han byggjer på, "role":"foundation"}`, elles `[]` |

**`definition_status`:** `defined` (teksten definerer omgrepet) · `defined_by_citation` (definert ved tilvising, «slik X definerer») ·
`not_stated` (ingen definisjon) · `stated_none_exists` (teksten seier at det ikkje finst ei felles/klar definisjon).
**`form` (støtteform):** `argument`, `literature`, `example`, `case`, `data_collection`, `experiment`, `design_work`,
`practice_reflection`, `modelling`, `use_in_practice`, `other`.

## Reglar
1. Alle `excerpt`-felt, `term`, `relation_expression` og `name` skal stå **ordrett** i inndataen. Eit validatorprogram sjekkar dette og avviser rader der utdraget ikkje finst.
2. 2–4 omgrep per påstand. `from`/`to` er dei to sidene av samanhengen, `condition` er vilkår.
3. Vel `relation_kind` ut frå kva teksten seier, ikkje kva du meiner er rett. Usikker → `associated_with` eller `other`.
4. Kvar påstand får berre `reported` viss teksten faktisk seier korleis påstanden er støtta (t.d. «Based on three case studies …»). Elles `not_stated`.
5. Tekstar kan vere på engelsk, svensk, dansk, norsk, finsk eller islandsk. Felt-verdiane (enum) er alltid dei engelske over.
6. Ikkje oppfinn side: bruk sida der utdraget står.

## Utdata
Skriv **éi JSON-fil per tekst** til `<ut-mappe>/<ID>.json` med nøyaktig denne forma (gyldig JSON, ingen kommentarar, ingen markdown-gjerde):

```json
{"id": "W1234567890", "claims": [ { "pdf_page": 1, "claim_location": "abstract", "attribution": "own",
  "excerpt": "...", "relation_expression": "...", "relation_kind": "causes_or_enables",
  "concepts": [{"term": "...", "role": "from", "definition_status": "not_stated"},
               {"term": "...", "role": "to", "definition_status": "not_stated"}],
  "scope": {"status": "not_stated"}, "explanation": {"status": "not_stated"}, "prediction": {"status": "not_stated"},
  "support_status": "not_stated", "support": [], "theories": [] } ]}
```
