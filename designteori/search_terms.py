"""Hand-written term data for the site search: stopwords, glossary expansions, examples, glossary entries.

Only data, no logic. `designteori/search_build.py` folds and validates it before it is published in
`docs/data/search/search_config.json` and `docs/data/search/glossary.json`.
"""
from __future__ import annotations

# --- stopwords -------------------------------------------------------------------------------
# English, Bokmal, Nynorsk, Danish, Swedish. Written with their normal spelling; search_build folds
# them (5.1) and removes duplicates. Domain words (design, research, practice, user, service, public,
# participation, craft, method ...) and every glossary term must NOT be here (checked at build time).
# "ar" (Swedish "ar"/"är") is left out on purpose because "AR" means augmented reality.
STOPWORDS_TEXT = """
the of and in for to a an on with by is are at as from how what which that this these those it its be
been being was were or not but into through between about their they them we our you your can may also
has have had do does did than then such more most when where who whom why will would should could
toward towards over under within without via per upon each other
og i på av for til med som en ei eit er om det den de dei dette denne desse ikkje ikke kva hva korleis
hvordan kvifor hvorfor kven hvem var vart blir blei ble bli vere være har hadde har har vi vi oss oss
seg sin sitt sine si ho han hun hans hennar hennes deira deres dei dem eg jeg du meg deg ein eit eller
men så sa når nar der her no nå også og òg både fra frå mot mellom mellom etter før under over ved
frå gjennom gjennom utan uten inn ut opp ned alle all alt noko noe nokon noen nokre noen berre bare
kan skal vil må må skulle ville kunne kunne måtte vore vært vorte blitt mykje mye meir mer mest minst
eigen egen eige egne sjølv selv slik slikt sånn sånne
af at og er det den de et en til som med for ikke hvad hvordan hvorfor hvem har havde han hun vi jeg du
mig dig sig sin sit sine hans hendes deres dem eller men også fra mellem efter før ved gennem uden ind
ud op ned alle noget nogen nogle kun bare kan skal vil må skulle ville kunne blev blive bliver været
mere mest selv sådan hvis når hvor her der nu
och att det som en ett är av för med på inte om den de dem har hade han hon vi jag du mig dig sig sin sitt
sina hans hennes deras eller men också från mellan efter före vid genom utan in ut upp ner alla allt
något någon några bara kan ska vill måste skulle ville kunde blev bli blir varit mer mest själv sådan om
när var här där nu hur vad varför vem vilken vilka denna detta dessa
""".split()

# --- glossary expansions ---------------------------------------------------------------------
# One line = "from phrase | from phrase => english | english". A from-phrase is a list of folded tokens
# (5.1). A from-token t matches a query token q when q == t, or len(t) >= 5 and q starts with t.
# The order of the lines is the order in which expansion tokens are collected (cap of 6 per query),
# so the more specific lines come first. Spelling variants are written with their own characters and
# folded at build time. "mote" alone is NOT a from-phrase: folded it equals "mote" (meeting).
GLOSSARY_LINES = """
taus kunnskap | tyst kunnskap | tavs kunnskap | tyst kunskap | tavs viden | tyst viden => tacit knowledge
handverk | håndverk | hantverk | håndværk => craft | craftsmanship
tenestedesign | tjenestedesign | tjänstedesign | servicedesign | tjenestedesign => service design
tenesteinnovasjon | tjenesteinnovasjon => service innovation
offentleg sektor | offentlig sektor | offentlige sektor | offentlege sektor | offentlig sector => public sector
offentleg forvaltning | offentlig forvaltning | offentleg tenester | offentlige tjenester | offentlige tenester => public administration | public services
offentleg innovasjon | offentlig innovasjon => public sector innovation
offentleg | offentlig | offentlige | offentlege => public
deltakande design | deltagande design | deltagende design | deltakende design | deltagande formgivning => participatory design
nordisk deltakande tradisjon | skandinavisk deltakande tradisjon | scandinavian deltakande => scandinavian participatory design | cooperative design
brukarmedverknad | brukermedvirkning | brukarinvolvering | brukerinvolvering | användarmedverkan | brugerinddragelse | brukarmedverking => user involvement | participatory design
deltaking | deltakelse | deltagelse | deltagande | deltakande | deltagende | deltakende | deltagelse => participation | participatory
medverknad | medvirkning | medverkan | medvirken | medverking | inddragelse | involvering => participation | involvement
samskaping | samskapning | samskapande | samskabelse => co-creation | cocreation
samdesign | medskaping | medskapande | meddesign | codesign | medskabelse => co-design | codesign | co-creation
designtenking | designtänkande | designtænkning | designtenkning => design thinking
design tenking | design tänkande | design tænkning => design thinking
spekulativt design | spekulativ design | spekulative design | spekulativ | spekulativt | spekulative => speculative design | speculative
kritisk design | kritiske design | kritisk | kritiske => critical design | critical
levande laboratorium | levande laboratorier | levande labs | levande lab | levande laboratoriet => living lab | living labs
overgangsdesign | transisjonsdesign | omstillingsdesign | omställningsdesign | overgangsdesign => transition design | sustainability transitions
omstilling | omställning | omstilling => transition | sustainability transitions
design for omsorg | omsorgsdesign | designing for care => care design | design for care
velferdsteknologi | välfärdsteknik | velfærdsteknologi => welfare technology | assistive technology
velferd | välfärd | velfærd => welfare
omsorgsteknologi | omsorgsarbeid | omsorg | omsorgs => care
berekraftig | bærekraftig | bæredygtig | hållbar | hållbarhet | berekraft | bærekraft | hållbart | bæredygtighed | berekraftige => sustainable | sustainability
designforsking | designforskning | designforskning => design research
praksisbasert forsking | praksisbasert forskning | praksisbaserad forskning | praksisbaseret forskning | praksisbasert => practice-based research | practice-led research
praksis | praksisbasert | praksisbaserad | praktikbaserad | praktik | praksisnær => practice | practice-based
forskingsdesign | forskningsdesign | forskningsdesign | forskingsopplegg => research design
forsking | forskning | forskar | forsker | forskare | forskarar | forskere => research | researcher
aksjonsforsking | aksjonsforskning | aktionsforskning | handlingsforskning | aksjonsforsking => action research
kvalitativ | kvalitative | kvalitativt => qualitative
kvantitativ | kvantitative => quantitative
casestudie | casestudium | kasusstudie | kasusstudium | tilfellestudie | casestudier | case studie => case study
formgjeving | formgivning | formgivare | formgiving | formgivere | formgjevar => design | form giving
designpedagogikk | designutdanning | designundervisning | designpedagogik | designundervising | designutbildning | designuddannelse => design education | design pedagogy
studiopedagogikk | studiokultur | studiobasert undervisning | studiopedagogik | designstudio => design studio | studio education
undervisning | undervising | pedagogikk | pedagogik | didaktikk | didaktik => teaching | pedagogy | education
utdanning | utbildning | uddannelse | utdannelse | opplæring | oppleiing => education | training
lærar | lærer | lärare | laerar | lærarar | lærere | lærare => teacher | teachers | educator
læring | læringsprosess | lärande | læringa | laering => learning
elev | elevar | elever | elevene | elevane => pupil | pupils | student | students
studentar | studenter | studerande | studenten | studentane | studenterne => student | students
skule | skole | skola | skoler | skolar | skulen | skolen => school | schools
barnehage | barnehagar | förskola | børnehave => kindergarten | preschool | early childhood
born | barn | børn | barnet | barna | barns | barnas | borna => children | child
ungdom | ungdommar | ungdomar | ungdomsskole | ungdomsskule => youth | young people | adolescents
vaksen | vaksne | voksen | voksne | vuxen | vuxna | voksenopplæring => adult | adults
eldre | aldring | äldre | ældre | eldreomsorg | aldrande | alderdom => elderly | ageing | older adults | aging
demens | demenssjukdom | demenssykdom | demensomsorg | demensvenleg => dementia
funksjonshemming | funksjonsnedsettelse | funksjonshemma | funksjonsnedsetting | handikapp | funktionsnedsättning | funktionshindrede => disability | disabilities | impairment
hjelpemiddel | hjelpemidler | hjälpmedel | hjaelpemidler | hjelpemiddelet => assistive technology | assistive devices
psykisk helse | mental helse | psykisk sykdom | psykisk lidelse => mental health
psykisk | psykiatri | psykiatrisk | psykiske => mental | psychiatric
rehabilitering | rehabilitation | rehabilitere | habilitering => rehabilitation
helse | helsetenester | helsevesen | sundhed | hälsa | helsetjenester | helsetjeneste | helsevesenet | sundhedsvæsen => health | healthcare
sjukehus | sykehus | sygehus | sjukhus | sykehuset | sjukehuset => hospital
pasient | patient | patientar | pasientar | pasienter | patienter | patienten => patient | patients
innbyggjar | innbygger | borger | medborgar | medborger | innbyggjarar | medborgare | innbyggere | invånare => citizen | citizens
kommune | kommunar | kommuner | kommunal | kommunale | kommunen | kommunerna | kommun => municipality | municipal | local government
forvaltning | förvaltning | forvaltningen | forvaltningsdesign => governance | public administration
brukar | bruker | användare | bruger | brukare | brukarar | brukere | brukerne => user | users
brukaropplevelse | brukeropplevelse | användarupplevelse | brukaropplevinga | brugeroplevelse | brukaropplevinga => user experience | UX
brukartest | brukertest | brukartesting | brukbarhet | brukbarheit | användbarhet | anvendelighed | brukertesting => usability | user testing
teneste | tjeneste | tjänst | tjenester | tenester | tjenesten | tenesta | tjänster => service | services
infrastruktur | infrastrukturering | infrastrukturar | infrastrukturer | infrastruktur => infrastructure | infrastructuring
fellesskap | fellesskapet | gemenskap | fællesskab | fellesskap | fellesskapa => community | communities | commons
lokalsamfunn | lokalsamfunnet | närsamhälle | lokalsamfund | lokalmiljø => local community | community
samfunn | samfunnet | samfunnsansvar | samhälle | samfund => society | social
sosial innovasjon | sosiale innovasjon | samfunnsinnovasjon | social innovation => social innovation
innovasjon | innovasjonsprosess | innovasjonar | innovasjoner | innovationsprocess => innovation
samarbeid | samarbeidsdesign | samarbete | samarbejde | samarbeidet => collaboration | collaborative | cooperation
kroppsleg | kroppslig | kropp | kroppen | kroppar | kroppslege => embodied | body | embodiment
materiell engasjement | materielt engasjement | materiell engagement | materielt engagement => material engagement
materialitet | materialitetar | materialiteter => materiality | material
materiale | materialar | materialer | materialet | materiell | materielle | materiell => material | materials
engasjement | engasjere | engagement | engasjerande => engagement
kunstig intelligens | artificiell intelligens | kunstig intelligens | kunstig intelligens => artificial intelligence
maskinlæring | maskinlaering | maskinlärande | maskinlæring => machine learning
verktøy | verktoy | verktyg => tool | tools
kunnskapsproduksjon | kunnskapsutvikling | kunskapsproduktion => knowledge production | knowledge creation
kunnskap | kunskap | viden | kunnskaper | kunnskapen => knowledge
kunst | konst | kunsten | kunstnar | kunstnarleg | kunstnerisk => art | artistic
moda | motedesign | mote tekstil | modedesign => fashion | fashion design
klesdesign | kleder | klaer | kläder | kleding | klesplagg => clothing | garment | fashion design
tekstil | textil | tekstiler | tekstilar | tekstildesign => textile | textiles
smykke | smykker | smycke | smykkekunst | gullsmed | gullsmedkunst => jewellery | jewelry | goldsmith
ull | uld | ullgarn => wool
keramikk | keramik | keramisk => ceramics | ceramic
møbel | møbeldesign | møbler | mobel | mobeldesign | möbel | møblar => furniture | furniture design
stol | stolar | stoler => chair | chairs
leik | lek | leke | leika | leiken => play | playfulness
leketøy | leker | leketoy | legetøj | leksak | leksaker => toy | toys
spel | spil | spillutvikling | spilldesign | spelutvikling | speldesign | spelifisering => game | games | gamification
arkitektur | arkitekt | arkitektar | arkitekter | arkitektonisk => architecture | architect
byutvikling | byplanlegging | stadsutveckling | stadsplanering | byplanlægning | byplan => urban development | urban planning | city
bolig | bustad | bostad | boligar | boliger | boende | hjem | heim => housing | home | domestic
universell utforming | universell utformning | universelt design | universal design | universell design => universal design | accessibility
tilgjengelegheit | tilgjengelighet | tilgjenge | tilgängligheit | tilgængelighed => accessibility
inkluderande | inkluderende | inkludering | inkluderande design | inkluderende design => inclusive design | inclusion
mangfald | mangfold | mångfald | mangfoldighed | diversitet => diversity
kjønn | kjonn | kjøn | køn | kön | kjønnsroller => gender
feminisme | feministisk | feministiske | feministisk design => feminism | feminist
makt | maktforhold | maktforhold | maktrelasjonar => power
politikk | politisk | politiske | politik | politiskt => politics | political | policy
demokrati | demokratisk | demokratiske | demokratisering => democracy | democratic | democratization
etikk | etisk | etiske | etik => ethics | ethical
tillit | tillid | förtroende | tilliten => trust
trygg | trygghet | säkerhet | sikkerhet | sikkerheit | trygging => safety | security
klima | klimaendring | klimaendringar | klimaendringer | klimakrise | klimakrisa | klimaförändring => climate | climate change
sirkulær | sirkulaer | sirkulær økonomi | circular | sirkulært | sirkulaert | cirkulär => circular | circular economy
gjenbruk | resirkulering | ombruk | återbruk | genbrug | gjenvinning => reuse | recycling
forbruk | forbruker | forbrukar | forbrukere | konsum | konsumtion | konsument => consumption | consumer
økonomi | okonomi | ekonomi | økonomisk | okonomisk | ekonomisk => economy | economic
verdiskaping | verdiskapning | värdeskapande | vaerdiskabelse => value creation
næringsliv | naeringsliv | näringsliv | erhvervsliv | bedrift | bedrifter | foretak | företag | virksomhet => industry | business | enterprise
entreprenørskap | entreprenorskap | entreprenörskap | entreprenørskab => entrepreneurship
teknologi | teknologien | teknologiar | teknologier | teknik | teknologisk => technology | technologies
digitalisering | digitalisation | digitalisering | digitalisering => digitalization | digitisation | digital transformation
interaksjon | interaksjonsdesign | interaktion | interaktionsdesign | interaksjonar => interaction | interaction design
prototyp | prototyping | prototyper | prototypar => prototype | prototyping
skisse | skisser | skissing | skissetegning | skissar => sketching | sketch
modell | modellar | modeller | modellering | modellbygging => model | models | modelling
metod | metode | metodar | metoder | metodologi | metodikk | metodik => method | methods | methodology
designmetode | designmetodar | designmetoder | designmetodikk | designmetodik => design methods | design methodology
designprosess | designprosessar | designprocess | designprocessen | designprosessen => design process
designpraksis | designpraksisar | designpraksisen => design practice
designkunnskap | designkunskap | designkunnskapen => design knowledge
designteori | designteoriar | designteorier | designteorien => design theory
designhistorie | designhistoria | designhistorien => design history
designantropologi | designantropologisk | designantropolog => design anthropology | ethnography
industridesign | industriell design | industriell formgiving | industridesigner | industridesignar => industrial design
produktdesign | produktutvikling | produktutveckling => product design | product development
grafisk design | grafisk formgiving | grafisk | grafikk | visuell kommunikasjon => graphic design | visual communication
visuell | visuelle | visuella | visuel => visual
teori | teoriar | teorier | teorien | teoretisk | teoretiske => theory | theories | theoretical
fenomenologi | fenomenologisk | fenomenologiske => phenomenology | phenomenological
refleksjon | refleksiv | refleksjonar | refleksjoner => reflection | reflective | reflexive
reflekterande | reflektion | reflektiv | reflekterende => reflection | reflective
kreativitet | kreativ | kreative | kreativt | kreativitetens => creativity | creative
estetikk | estetik | estetikken => aesthetics
estetisk | estetiske | estetiska | æstetisk => aesthetic | aesthetics
opplevelse | oppleving | upplevelse | oplevelse | opplevingar | opplevelser | opplevinga => experience | experiential
erfaring | erfaringar | erfaringer | erfarenhet | erfaringsbasert => experience | experiential
improvisasjon | improvisation | improvisere | improvisering => improvisation
sansing | sansar | sanselig | sansemessig | sensorisk | sanseleg => sensory | senses | sensing
lyd | lydlandskap | ljud | ljudlandskap | lydkunst | lydbilde => sound | soundscape | audio
lys | lysdesign | belysning | ljus | lyssetting => light | lighting
farge | fargar | farger | färg | farve | fargebruk => colour | color
formsprak | formspråk | formsprog => form language | design language | aesthetics
dans | danse | dansar | koreografi => dance | choreography
teater | scenekunst | teatret | teaterdesign | scenografi => theatre | performance | scenography
tradisjon | tradisjonell | tradisjonar | tradisjoner | tradisjonelle | traditionell => tradition | traditional
kultur | kulturarv | kulturminne | kulturell | kulturelle => culture | cultural heritage
framtid | framtida | framtidsstudiar | framtidsbilde | fremtid | framtiden | fremtider | framtidsdesign | framtider => future | futures | foresight
fortelling | forteljing | berättelse | narrativer | narrativar | historiefortelling | forteljingar | fortellinger => narrative | storytelling | story
endring | forandring | förändring | forandringsarbeid | endringsarbeid | forandringar => change | transformation
migrasjon | innvandring | innvandrar | innvandrere | migration => migration | immigrant
flyktning | flyktningar | flyktninger | flykting | flyktningane => refugee | refugees
urfolk | samisk | samiske | urfolksperspektiv | samiskspråkleg => indigenous | sami
nordisk | nordiske | norden | nordiska | nordisk | skandinavisk | skandinaviske | skandinavia => nordic | scandinavian | scandinavia
norsk | norske | noreg | norge => norway | norwegian
svensk | svenske | sverige => sweden | swedish
dansk | danske | danmark => denmark | danish
finsk | finske | finland | suomi => finland | finnish
islandsk | islandske => iceland | icelandic
københavn | kopenhamn | kjøbenhavn | kobenhavn => copenhagen
göteborg | goteborg | gøteborg => gothenburg
helsingfors => helsinki
mobilitet | transport | trafikk | sykkel | sykling | cykel | cykling => mobility | transport | traffic | bicycle | cycling
matkultur | måltid | maltid | matdesign | kjokken | kjøkken => food | meal | kitchen
""".strip().splitlines()

EXAMPLES = [
    {"q": "participation in service design in the public sector", "lang": "en"},
    {"q": "research through design", "lang": "en"},
    {"q": "infrastructuring", "lang": "en"},
    {"q": "sustainable design", "lang": "en"},
    {"q": "taus kunnskap i handverk", "lang": "nn"},
    {"q": "korleis involverer ein innbyggjarar i offentlege tenester", "lang": "nn"},
    {"q": "co-design with children", "lang": "en"},
    {"q": "speculative design", "lang": "en"},
    {"q": "velferdsteknologi og design for eldre", "lang": "nb"},
    {"q": "designutdanning og studiopedagogikk", "lang": "nb"},
]

# Common Norwegian words whose folded form equals a short word. Used by the collision check (22):
# every single-token from-entry in GLOSSARY_LINES is compared with the fold of these words.
NORWEGIAN_FOLD_CHECK = [
    "møte", "være", "når", "år", "få", "så", "på", "gå", "på", "vår", "får", "lå", "nå", "tå", "må",
    "ål", "bær", "hær", "kjær", "sær", "mål", "kår", "sår", "bål", "tål", "gjær", "lære", "ære", "fære",
    "mote", "kunst", "bøker", "bøte", "løse", "møter", "møtet", "røde", "søke", "støtte", "tøy", "øye",
    "øya", "ørn", "åpne", "åker", "åpen", "ås", "ætt", "ærlig", "væske", "vært", "bære", "tære", "særlig",
]

# (id, term, nn, en, no, q): the readable glossary (F15). `nn` is a short, factual explanation in
# Nynorsk without quotes from sources. The owner reads it before it is published (professional claim).
GLOSSARY_ENTRIES = [
    ("rtd", "research through design",
     "Ei forskingsform der ein lagar og prøver ut ting, til dømes prototypar, for å lære noko om eit problem eller ein situasjon. Det ein lagar er ein del av korleis kunnskapen oppstår.",
     ["research through design", "RtD"], ["forsking gjennom design"], "research through design"),
    ("infrastructuring", "infrastructuring",
     "Arbeidet med å byggje og halde ved like delte strukturar rundt eit prosjekt, slik at fleire aktørar kan halde fram med å utvikle noko saman også etter at designprosjektet er slutt. Omgrepet vert mykje brukt i nordisk deltakande design.",
     ["infrastructuring"], ["infrastrukturering"], "infrastructuring"),
    ("taus-kunnskap", "taus kunnskap",
     "Kunnskap ein har i kroppen og i praksis, men som er vanskeleg å setje ord på, til dømes det ein handverkar kjenner i materialet.",
     ["tacit knowledge"], ["tyst kunnskap", "taus kunnskap"], "tacit knowledge"),
    ("deltakande-design", "deltakande design",
     "Ein designtradisjon der dei som skal bruke eller bli råka av ei løysing, er med på å utforme ho frå starten av. Tradisjonen har sterke røter i Skandinavia og i arbeidslivet på 1970-talet.",
     ["participatory design", "cooperative design"], ["deltakende design", "deltagande design"], "participatory design"),
    ("samdesign", "samdesign",
     "Å designe saman med dei som blir råka, ofte i verkstader der fagfolk og brukarar utviklar idear side om side. Orda samdesign, medskaping og co-design vert ofte brukte om kvarandre.",
     ["co-design", "codesign", "co-creation"], ["medskaping", "samskaping"], "co-design"),
    ("tenestedesign", "tenestedesign",
     "Design av heile tenester, til dømes ein pasientveg eller ei kommunal teneste, med vekt på møtepunkta mellom brukarar og tilsette og på alt som skjer bak kulissene.",
     ["service design"], ["tjenestedesign", "servicedesign"], "service design"),
    ("spekulativt-design", "spekulativt design",
     "Design som lagar moglege framtider eller alternative verder for å få folk til å stille spørsmål ved det som er sjølvsagt i dag. Ting vert laga for å skape samtale, ikkje for å seljast.",
     ["speculative design"], ["spekulativ design"], "speculative design"),
    ("kritisk-design", "kritisk design",
     "Design som granskar og utfordrar føresetnader i teknologi og samfunn gjennom tinga det lagar. Ofte nært knytt til spekulativt design.",
     ["critical design"], ["kritisk design"], "critical design"),
    ("designtenking", "designtenking",
     "Ein måte å arbeide med problem på som hentar metodar frå design, til dømes å setje seg inn i brukarane, lage mange idear og prøve dei ut tidleg. Brukt langt utanfor design.",
     ["design thinking"], ["designtenkning", "designtänkande"], "design thinking"),
    ("handverk", "handverk",
     "Kunnskap og ferdigheit som veks fram gjennom langvarig arbeid med eit materiale og verktøy. I designforsking er handverk både ein praksis og eit perspektiv på kunnskap.",
     ["craft", "craftsmanship"], ["håndverk", "hantverk"], "craft"),
    ("materiell-engasjement", "materiell engasjement",
     "Korleis folk tenkjer og lærer ved å arbeide med fysiske materiale. Omgrepet vert brukt til å forstå korleis kunnskap oppstår i møtet mellom hand, verktøy og material.",
     ["material engagement"], ["materielt engasjement"], "material engagement"),
    ("materialitet", "materialitet",
     "Kva som kjenneteiknar materialet i ei ting, og korleis dei fysiske eigenskapane påverkar kva ei ting kan brukast til og kva ho tyder.",
     ["materiality"], ["materialitet"], "materiality"),
    ("designantropologi", "designantropologi",
     "Eit felt som kombinerer antropologiske metodar, som feltarbeid, med designpraksis for å forstå og forme kvardagsliv og framtider.",
     ["design anthropology"], ["designantropologi"], "design anthropology"),
    ("levande-laboratorium", "levande laboratorium",
     "Ein arena der nye løysingar vert prøvde ut saman med brukarar i verkelege omgjevnader, til dømes eit bustadområde eller eit sjukehus, i staden for i eit lukka laboratorium.",
     ["living lab", "living labs"], ["levende laboratorium"], "living lab"),
    ("berekraftig-design", "berekraftig design",
     "Design som tek omsyn til miljø og samfunn gjennom heile livsløpet til ei ting. Det engelske uttrykket «design for sustainability» femner om alt frå betre produkt til endring av heile system.",
     ["sustainable design", "design for sustainability"], ["bærekraftig design", "bæredygtigt design"], "sustainable design"),
    ("overgangsdesign", "overgangsdesign",
     "Design som arbeider med store samfunnsendringar over lang tid, til dømes overgangen til eit meir berekraftig samfunn, og som ser løysingar som delar av større system.",
     ["transition design"], ["overgangsdesign"], "transition design"),
    ("design-for-omsorg", "design for omsorg",
     "Design av tenester, produkt og miljø for omsorg og helse, med vekt på dei som gir og får omsorg og på relasjonane mellom dei. Ofte knytt til velferdsteknologi.",
     ["design for care", "care design"], ["design for omsorg"], "design for care"),
    ("brukarmedverknad", "brukarmedverknad",
     "At dei som skal bruke ei løysing, er med på å påverke ho undervegs. Det kan gå frå å bli spurd om synspunkt til å vere med på å bestemme.",
     ["user involvement", "user participation"], ["brukermedvirkning"], "user involvement"),
    ("designforsking", "designforsking",
     "Forsking om design: korleis design vert gjort, kva det fører til, og korleis ein kan lære av det. Omfattar forsking om design, for design og gjennom design.",
     ["design research"], ["designforskning"], "design research"),
    ("praksisbasert-forsking", "praksisbasert forsking",
     "Forsking der praksisen sjølv, til dømes å lage ting, er ein viktig del av metoden og av resultatet. Vanleg i kunst- og designutdanningar, mellom anna i doktorgradar med praktisk arbeid.",
     ["practice-based research", "practice-led research"], ["praksisbasert forskning"], "practice-based research"),
    ("forskingsdesign", "forskingsdesign",
     "Her: korleis ei forsking er lagd opp, med spørsmål, metode og utval. Ordet er ikkje det same som å designe ting.",
     ["research design"], ["forskningsdesign"], "research design"),
    ("formgjeving", "forming og formgjeving",
     "Arbeidet med å gi ting form: utsjånad, struktur og eigenskapar. Ordet vert helst brukt om fysiske ting, særleg i produkt- og møbeldesign.",
     ["form giving", "design"], ["formgivning", "forming"], "form giving"),
    ("designpedagogikk", "designpedagogikk",
     "Korleis ein underviser og lærer design, til dømes gjennom studio, kritikk og prosjektarbeid. Dekkjer både utdanning i design og undervising i designmetode i andre fag.",
     ["design education", "design pedagogy"], ["designutdanning"], "design education"),
    ("nordisk-deltakande-tradisjon", "nordisk deltakande tradisjon",
     "Den skandinaviske tradisjonen i deltakande design, med røter i 1970-åra, der arbeidstakarar og fagforeiningar fekk medverke i utviklinga av teknologi på arbeidsplassen. Legg vekt på demokrati og samarbeid.",
     ["Scandinavian participatory design", "cooperative design"], ["skandinavisk deltakande design"], "Scandinavian participatory design"),
    ("designteori", "designteori",
     "Teoriar om kva design er, korleis det verkar og korleis ein kan forstå det. Teorien kan handle om prosess, om kunnskap, om objektet eller om samfunnet.",
     ["design theory"], ["designteori"], "design theory"),
    ("universell-utforming", "universell utforming",
     "At ting, bygg og tenester skal kunne brukast av så mange som mogleg, utan spesiell tilpassing. Omgrepet er knytt til lovverk om likestilling og tilgjenge.",
     ["universal design", "inclusive design"], ["universell utforming"], "universal design"),
    ("kanon", "kanon",
     "På denne sida: dei mest siterte verka og forfattarane i korpuset. Ei kanon her seier kva som oftast vert referert til i dette utvalet, ikkje kva som er best.",
     ["canon", "most cited works"], ["kanon"], "design theory canon"),
    ("likskap-i-meining", "likskap i meining",
     "Når to verk handlar om det same sjølv om dei ikkje brukar dei same orda. Sida reknar det ut frå tittel og samandrag med ein språkmodell. Det er ikkje ein kvalitetsmåling.",
     ["semantic similarity"], ["semantisk likskap"], "semantic similarity"),
]
