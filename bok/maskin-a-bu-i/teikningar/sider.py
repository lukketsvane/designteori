"""Sideplan for teikningane til «MASKINA Å BU I» (speculative drawing, 1:1).

Kvar side: tekst (ordrett frå manuset), teikningar (ovanfrå og ned), merknader (handskrivne, ordrett,
i store bokstavar), ref (referansesett i img.py) og eventuelt tittel (berre side 1).
"""

SIDER = [
    dict(
        tittel="MASKINA Å BU I",
        tekst="I KORRIDORGOLVET LIGG MØRK ORDOVICISK KALKSTEIN, SLIPT PLAN TVERS GJENNOM FEM HUNDRE MILLIONAR ÅR GAMLE TRILOBITTAR, KVITE GRUNNPLANAR RETT UNDER SKOSÅLANE SOM HASTAR FRÅ MØTE TIL MØTE. LENGE FØR NOKON TEIKNA EIT ÅRSHJUL, LENGE FØR DET FANST TRE ELLER KNOKLAR ELLER AUGELOK, LÅG DEI I SLAMMET MED DEI FØRSTE AUGO PÅ JORDA: SEKSTI PRISME AV REIN KALKSPAT I KVART BLIKK, VINKLA FOR KLARSYN GJENNOM GRUMS. SLAMMET VART STEIN. AUGO VART VERANDE. GOLVET VART LAGT OVER DEI SÅ DEI SOM GJEKK HER SKULLE HA NOKO Å STÅ PÅ.",
        teikningar=[
            "ei slipt steinflis sett ovanfrå: trilobittar skorne tvers av, teikna som kvite grunnplanar med segment, lik arkitektplanar",
            "skosålar i fart over flisa, berre sålar og hælar i kontur",
            "nærbilete av eit trilobittauge: seksti små kalkspatprisme i rader, lysstrålar som går rett gjennom grumsete slam",
            "eit snitt: slam blir stein, golvet lagt over, ein fot som står på toppen",
        ],
        merknader=["SLIPT PLAN TVERS GJENNOM", "KVITE GRUNNPLANAR", "SEKSTI PRISME AV REIN KALKSPAT", "SLAMMET VART STEIN. AUGO VART VERANDE."],
        ref="middels",
    ),
    dict(
        tekst="DEN FØRSTE DAGEN VÅR STANSA DU MIDT I GANGEN. EG TRUDDE DET VAR SKOLISSA DI DU SÅG PÅ. DU TOK OM HOVUDET MITT OG FLYTTA DET EIN TOMME TIL SIDA TIL EG ÒG SÅG DET: I ÉI LINSE AV STEIN LÅG HEILE DET LANGE LYSRØYRET I TAKET AVSPEGLA. EG VISSTE ENNO IKKJE KVA DU HEITTE. UNDER DET SAME RØYRET RØRDE DU BLYANTEN SNØGT ATT OG FRAM TIL HAN OPNA SEG I EI VIFTE AV SVARTE STREKAR, HUNDRE BLINK AV FEMTI HEILE SVINGINGAR I SEKUNDET. MEDVITET SER SAMANHENGANDE DAGSLYS. I MELLOMROMMA MELLOM BLINKA LIGG HEILE HALLEN I MØRKRE.",
        teikningar=[
            "to hender som held om eit hovud og flyttar det ein tomme til sida, med ei lita pil og eit mål",
            "ei lita steinlinse i golvet der heile det lange lysrøyret i taket ligg spegla, med siktelinje frå auga",
            "ein blyant som vert rørd snøgt att og fram og opnar seg i ei vifte av svarte strekar",
            "ei tidslinje med hundre blink og mørke mellomrom mellom dei",
        ],
        merknader=["EIN TOMME TIL SIDA", "HEILE DET LANGE LYSRØYRET I TAKET AVSPEGLA", "HUNDRE BLINK", "I MELLOMROMMA LIGG HEILE HALLEN I MØRKRE"],
        ref="middels",
    ),
    dict(
        tekst="I 1936 TEIKNA HARALD ENG EIN VERKSTAD FOR OSLO LYSVERKER. TO ÅR SEINARE STOD HAN I MARIDALSVEGEN 29, TEGL MOT REGNET, BETONG MOT JORDA, STØYPEJERNSSKILTET INNMURT I FASADEN. EIT ROM FOR MASKINER SOM VAR FOR TUNGE Å LYFTE MED HENDENE. UNDER GLASTAKET GJEKK TRAVERSKRANA, DIMENSJONERT FOR FØRTI TONN. EI LYFT HAND PÅ GOLVET TYDDE VENT; TO TONN JERN HANG EI HANDSBREIDD OVER TREKLOSSANE TIL LASTA TOK NEDI OG TO KJETTINGLEDD SLO LAUST MOT KVARANDRE I STILLA.",
        teikningar=[
            "fasaden av ein tegla verkstadhall frå 1930-talet med store vindauge og eit innmura støypejernsskilt utan lesbar tekst",
            "snitt gjennom hallen: glastak, traverskran på skinner",
            "ei lyft hand på golvet",
            "ein tung jernblokk som heng i kjetting ei handsbreidd over treklossar, to kjettingledd som slår mot kvarandre",
        ],
        merknader=["MARIDALSVEGEN 29", "TEGL MOT REGNET, BETONG MOT JORDA", "DIMENSJONERT FOR FØRTI TONN", "EI LYFT HAND PÅ GOLVET TYDDE VENT"],
        ref="middels",
    ),
    dict(
        tekst="EIN TRANSFORMATOR HAR TO VIKLINGAR KRING SAME JERNKJERNEN, ALDRI KONTAKT MELLOM PRIMÆRSPOLE OG SEKUNDÆRSPOLE, BERRE LAG AV OLJETREKT PAPIR AV SUNDMALNE TRE. VEKSELSTRAUMEN SNUR HUNDRE GONGER I SEKUNDET; ELEKTRONA SKJELV PÅ STADEN UTAN Å FLYTTE SEG EIN MILLIMETER, JERNKJERNEN VERT VARM, OG DET SOM SKJER I DEN EINE VIKLINGA SET DEN ANDRE I RØRSLE I MØRKRET UTAN Å RØRE HENNE. DÅ EIN ARBEIDAR VIKLA AV MIL MED KOPAR, OMGANG FOR OMGANG, KUNNE HAN HALDE DET SOM HADDE SLØKT EI GATE MELLOM TOMMEL OG PEIKEFINGER: EIT HOL MED SVART, SVIDD RAND I DET OLJEVÅTE PAPIRET. NOKO GÅR INN MED ÉI SPENNING OG KJEM UT MED EI ANNA. MATAR EIN LÅGSPENNING INN BAKLENGS, STIG HO TIL DØDELEG HØGSPENNING. HUSET HADDE LÆRT DET FØR DET FEKK STUDENTAR.",
        teikningar=[
            "ein transformator teikna eksplodert: jernkjerne, to viklingar, papirlag mellom dei",
            "ei bølgjelinje for vekselstraum og små elektron som skjelv på staden",
            "ei hand som held eit papirark mellom tommel og peikefinger, med eit hol med svidd rand",
            "to piler: inn med éi spenning, ut med ei anna; og den same baklengs, stigande",
        ],
        merknader=["PRIMÆRSPOLE", "SEKUNDÆRSPOLE", "OLJETREKT PAPIR AV SUNDMALNE TRE", "EIT HOL MED SVART, SVIDD RAND", "NOKO GÅR INN MED ÉI SPENNING OG KJEM UT MED EI ANNA."],
        ref="mykje",
    ),
    dict(
        tekst="UNDER KRIGEN REKVIRERTE TYSKARANE VERKSTADEN TIL MOTORPRØVESTASJON: MOTORAR BOLTA FAST I BETONGEN PÅ FULLT TURTAL, TIME ETTER TIME, UTAN Å FLYTTE SEG EIN MILLIMETER. SÅ SEINT SOM HAUSTEN 1944 VART DET TINGA METALL TIL DØRBESLAG. PÅ TINGINGSARKET STÅR DET KVA DØRA TRENG AV JERN, IKKJE KVEN SOM FÅR GÅ GJENNOM HENNE. EG VEIT IKKJE KVAR DEI BESLAGA HAMNA, MEN EG VEIT KORLEIS EI LÅST DØR VERKAR.",
        teikningar=[
            "motorar bolta fast i eit betonggolv, med skjelvande strekar rundt men utan å flytte seg (ingen symbol eller flagg)",
            "eit tingingsark med ei liste over beslag: hengsler, lås, nøklar, skruar, teikna som små gjenstandar",
            "ei lukka dør med lås og nøkkelhol, sett tett",
        ],
        merknader=["MOTORPRØVESTASJON", "HAUSTEN 1944", "KVA DØRA TRENG AV JERN", "KORLEIS EI LÅST DØR VERKAR"],
        ref="middels",
    ),
    dict(
        tekst="NEDE I KJELLAREN KAN DU LEGGJE HANDFLATA MOT DEN UBEHANDLA BETONGEN OG LESE SKOGEN SOM STOD HER FØR KRIGEN. ÅRRINGANE OG KVISTANE FRÅ FORSKALINGSPLANKANE SIT ATT BAKLENGS I DEN GRÅ MASSEN, EIT NEGATIV AV OPPBRENDE GRANTRE. SÅ SNART STØYPEN HADDE STIVNA, RØSKA DEI BORT DET LEVANDE TREVERKET MED BREKKJERN OG KALLA TOMROMMET ARKITEKTUR. SLIK FEKK MASKINA RØTER UTAN AT NOKO LEVANDE FEKK VERE MED INN.",
        teikningar=[
            "ei handflate lagd mot ein betongvegg med avtrykk av plankar, årringar og kvistar",
            "snitt: forskalingsplankar rundt fersk betong, eit brekkjern som riv plankane laus",
            "eit grantre teikna som negativ: berre omrisset av årringane att i den grå massen",
        ],
        merknader=["ÅRRINGANE SIT ATT BAKLENGS", "EIT NEGATIV AV OPPBRENDE GRANTRE", "KALLA TOMROMMET ARKITEKTUR"],
        ref="lite",
    ),
    dict(
        tekst="VÅREN 1945 BYRJA EIN ANNAN VERKSTAD I ULLEVÅLSVEGEN, EIT KRISEKURS FOR STUDENTAR KRIGEN HADDE TEKE ÅRA FRÅ. DEI FEKK IKKJE ÅRA ATT; DEI FEKK EIT BORD, BLYANTAR, PAPIR OG EIN BY SOM ENNO IKKJE VAR FERDIG MED Å TELJE DEI SOM VAR BORTE. SET DU BLYANTSPISSEN LITT INNPÅ DEN AVBROTNE STREKEN, SYNER PAUSEN SOM EIN MILLIMETER MØRKARE VEGG.",
        teikningar=[
            "eit enkelt bord med blyantar og papirark, tomme stolar rundt",
            "nærbilete av ein blyantstrek som er broten og teken opp att, der overlappinga vert ein millimeter mørkare vegg, med målestrek",
            "rader av teljestrekar som held fram over kanten",
        ],
        merknader=["ULLEVÅLSVEGEN", "EIT BORD, BLYANTAR, PAPIR", "PAUSEN SOM EIN MILLIMETER MØRKARE VEGG"],
        ref="lite",
    ),
    dict(
        tekst="SAME VÅREN VART BERGEN-BELSEN FRIGJORD. DER FANST IKKJE GASSKAMMER; DET VAR SVOLTEN OG SJUKDOMMEN OG AVDELINGANE, MENNESKE SORTERTE I ARBEIDSFØRE OG FOR SJUKE TIL Å BRUKAST, BRAKKEREKKER OG ORGANISASJONSKART MED BOKSAR OG PILER OVANFRÅ OG NED, TABELLAR FOR MINSTE GOLVFLATE OG KUBIKKMETER LUFT PER KROPP, NEDREGULERT TIL NULL VOLT OG TØMT FOR NAMN. ARKITEKTEN SPISSAR BLYANTEN OG FLYTTAR EIN STREK TO MILLIMETER PÅ KALKERPAPIRET. EIT ORGANISASJONSKART KAN IKKJE VASKE HENDENE PÅ DEN SOM HAR TEIKNA DET.",
        teikningar=[
            "ein situasjonsplan med rader av like brakker, teikna nøkternt som ein arkitektplan, utan menneske",
            "eit organisasjonskart med tomme boksar og piler ovanfrå og ned som endar i eit jordsymbol",
            "ein tom tabell med kolonnar og strekar, utan tal",
            "ei hand som spissar ein blyant, og ein strek som er flytta to millimeter på kalkerpapir",
            "ingen kroppar, ingen symbol, inga vald: berre plan, skjema og hender",
        ],
        merknader=["BRAKKEREKKER", "KUBIKKMETER LUFT PER KROPP", "NEDREGULERT TIL NULL VOLT", "TO MILLIMETER"],
        ref="middels",
    ),
    dict(
        tekst="I ST. OLAVS GATE VART DET FOR TRONGT; I 1996 KOM INDUSTRIDESIGN INN, STOLAR OG HANDTAK SOM SKULLE HALDE NÅR NOKON LA HEILE TYNGDA SI PÅ DEI. I 1998 TEIKNA JARMUND OG VIGSNÆS DEN GAMLE TRANSFORMATORHALLEN OM: OLJA TØMD GJENNOM KJELLARSLUKET, KOPAREN RØSKA UT, TEGLEN FEKK STÅ, BYGNINGEN SKOREN OPP I MIDTEN OG SÅRET KLEDD I GLAS OG ALUMINIUM. DEN 30. OKTOBER 2001 AVDUKA KONGEN EIN PLAKETT VED INNGANGEN, OG TEIKNEBORDA VART BORNE INN GJENNOM VERKSTADPORTEN SOM I SI TID HADDE TEKE IMOT DET SOM VAR FOR STORT TIL Å REPARERAST DER DET STOD. I 2005 FEKK SKULEN NAMNET ARKITEKTUR OG DESIGN. TO VIKLINGAR KRING SAME KJERNEN. MASKINA HADDE IKKJE SLUTTA; HO HADDE BERRE SKIFTA DET HO ARBEIDDE MED.",
        teikningar=[
            "ein stol og eit handtak med piler for tyngd",
            "ein tegla hall skoren opp i midten som eit sår, kledd i glas og aluminium; olje som renn ut gjennom eit kjellarsluk",
            "teiknebord som vert borne inn gjennom ein stor verkstadport",
            "to viklingar kring same kjernen, liten",
        ],
        merknader=["OLJA TØMD GJENNOM KJELLARSLUKET", "SÅRET KLEDD I GLAS OG ALUMINIUM", "30. OKTOBER 2001", "TO VIKLINGAR KRING SAME KJERNEN"],
        ref="mykje",
    ),
    dict(
        tekst="UNE MAISON EST UNE MACHINE-À-HABITER, SKREIV LE CORBUSIER I 1923. INGEN BUR I EI MASKIN; MASKINER BUR I SEG SJØLVE. MANNEN HANS KOM OPP PÅ VEGGEN I TEIKNESALEN: HUNDRE OG ÅTTITRE CENTIMETER FRÅ HÆL TIL ISSE MED ARMEN LYFT. DEN LYFTE HANDA TYDDE IKKJE LENGER VENT; HO VAR EIT MÅL NO, OG HADDE KRANFØRAREN VENTA PÅ HENNE, HADDE JERNET HANGE UNDER GLASTAKET ENNO. MODULOR ER EIN KROPP SOM ALDRI VERT SJUK, UTAN TARMAR, UTAN SVEITTE, UTAN RYGGVIRVLAR SOM SØKK, UTAN NEGLAR SOM VEKS EIN TIANDEDELS MILLIMETER I DØGNET, OM LAG FIRE CENTIMETER I ÅRET. PROPORSJONANE SMALNAR NED TIL DET MINSTE REKTANGELET SOM IKKJE SVARAR TIL NOKON TING, FOR KALKYLANE FORSVINN I AVRUNDINGSFEIL. DET FANST VERSJONAR FOR KVINNER, FOR BORN, FOR DEI SOM SAT OG DEI SOM MANGLA ARMEN; INGEN AV DEI VART TEIKNA. DET STOD ÉIN MANN I ROMMET, OG HAN STOD STILLE LENGE NOK.",
        teikningar=[
            "ein stiliserd mannsfigur med lyft arm på ein vegg, med målestrekar frå hæl til hand (eigen figur, ikkje kopi av noko kjent bilete)",
            "jern som heng under eit glastak og ventar på ei lyft hand",
            "rektangel i proporsjon som smalnar inn til eit lite rektangel",
            "prikka, uferdige omriss av ei kvinne, eit barn, ein sitjande og ein utan arm, som aldri vart teikna ferdige",
        ],
        merknader=["UNE MAISON EST UNE MACHINE-À-HABITER", "HUNDRE OG ÅTTITRE CENTIMETER", "UTAN TARMAR, UTAN SVEITTE", "INGEN AV DEI VART TEIKNA"],
        ref="mykje",
    ),
    dict(
        tekst="TIL MORA TEIKNA HAN SEKSTI KVADRATMETER VED GENÈVESJØEN; HO FRAUS OG SA INGENTING, FAREN DØYDDE ETTER EITT ÅR OG BUDDE I JORDA DER DET VAR MEIR PLASS, OG MORA BUDDE DER TIL HO VART HUNDRE MEDAN RYGGVIRVLANE HENNAR SOKK SAMAN OG HUSET VART RELATIVT STØRRE ETTER KVART SOM HO VART MINDRE, TIL HO NESTEN VAR BORTE. I UNITÉ D'HABITATION FILTRERER TRE TUSEN TO HUNDRE NYRER AVFALL SOM ALLTID RENN NEDOVER. INGEN TEIKNAR KLOAKKEN UNDER VERKSTADEN. KLOAKKEN TEIKNAR SEG SJØLV; HAN ER DEN EINASTE ÆRLEGE ARKITEKTUREN, HAN FØLGJER TYNGDEKRAFTA MOT ELVA OG TEK IMOT ALT UTAN Å KLAGE.",
        teikningar=[
            "eit lite, langt hus ved ein innsjø; inne ei gammal kvinne som vert mindre i fleire steg medan huset står like stort",
            "ei ryggsøyle med virvlar som søkk saman",
            "snitt gjennom ein stor bustadblokk med avløpsrøyr som går nedover",
            "kloakkrøyr under ein verkstad som fell mot ei elv",
        ],
        merknader=["SEKSTI KVADRATMETER VED GENÈVESJØEN", "HUSET VART RELATIVT STØRRE", "TRE TUSEN TO HUNDRE NYRER", "KLOAKKEN TEIKNAR SEG SJØLV"],
        ref="middels",
    ),
    dict(
        tekst="I SALANE LÆRER ME AT FORM FØLGJER FUNKSJON. EIN STOL SKAL BERE EIN KROPP, EI DØR SKAL SKILJE TO ROM, EIT HANDTAK SKAL TA IMOT EI HAND. MEN EIN STOL KAN VELTAST, EI DØR KAN STÅ OPEN, OG EI HAND KAN NEKTE Å GRIPE. FUNKSJON FØLGJER INGENTING; FUNKSJON VERT LAGD INN I NOKO ANNA UTANFRÅ SLIK AT EIN KAN LESE HAN UT ATT OG SEIE AT EIN HAR FUNNE HAN, EI PIL FRÅ KROPPEN TIL BRUKEN SÅ EIN SLEPP Å SPØRJE KROPPEN OM HAN VIL BRUKAST. EI ELV VERT KJØLEVATN, EIN STUDENT VERT LEVERANSE.",
        teikningar=[
            "tre par: ein stol som ber ein kropp og ein velta stol; ei lukka dør og ei open dør; eit handtak med hand og ei hand som nektar å gripe",
            "ei pil frå ein kropp til ein bruk",
            "ei elv som vert leidd inn i eit røyr, og ein student som vert ein pakke",
        ],
        merknader=["FORM FØLGJER FUNKSJON", "EI HAND KAN NEKTE Å GRIPE", "EI PIL FRÅ KROPPEN TIL BRUKEN", "EIN STUDENT VERT LEVERANSE"],
        ref="middels",
    ),
    dict(
        tekst="FØR NOKON KALLA DET BRUKARINNSIKT, GJEKK ANATOMANE NOKRE KVARTAL UNNA MED SKYVELÆRE OG KRANIOMETER TIL SAMISKE GRAVER, TOK HOVUDSKALLAR OPP OR JORDA, DELTE BREIDDA PÅ LENGDA GONGER HUNDRE OG SKREIV KATALOGNUMMER MED SVART TUSJ RETT PÅ PANNEBEINET. KVAR MUNN VAR BORTE. SKALLEN FEKK EIT NUMMER, OG DEN SOM HADDE LEVD INNI VART KALLA EIT FUNN. DET VAR IKKJE SKALLEN SOM BAR DEN TEORIEN; DET VAR HANDA SOM HELD SKYVELÆRET, TEIKNA EI GRENSE OG KALLA GRENSA NATUR.",
        teikningar=[
            "eit skyvelære og eit kraniometer, teikna som instrument",
            "ein hovudskalle sett frå sida som museumsgjenstand, med målelinjer for lengd og breidd, utan tal",
            "ein brøk: breidd over lengd gonger hundre",
            "ei hand som held skyvelæret og dreg ei grenselinje",
        ],
        merknader=["BREIDDA PÅ LENGDA GONGER HUNDRE", "KVAR MUNN VAR BORTE", "DEN SOM HADDE LEVD INNI VART KALLA EIT FUNN", "GRENSA NATUR"],
        ref="middels",
    ),
    dict(
        tekst="ELVANE I NORD VART LAGDE I RØYR INN PÅ PRIMÆRSPOLEN. HOS FOSTERET OG DET NYFØDDE MENNESKET ER SKALLEN ENNO OPNE FUGER, FONTANELLAR, SÅ HOVUDET KAN KLEMMAST GJENNOM EIN TRONG KANAL UTAN Å BRISTE; SIDAN VEKS DEI TAKKETE SAUMANE SAMAN TIL SUTURAR SÅ TANKEN FÅR EIT TAK Å BU UNDER. EIN SKALLE ER ÒG EI MASKIN Å BU I. HER INNE VIL DEI HA PROSESSEN I REVERS: SKALLAR MJUKNA NOK TIL Å SKYVAST UNDER EI LÅST KONTORDØR SOM EIT REVIDERT BUDSJETT.",
        teikningar=[
            "elvar i eit nordleg landskap som vert leidde i røyr inn på ein spole",
            "skallen til eit nyfødd barn sett ovanfrå med opne fontanellar",
            "ein vaksen skalle med takkete suturar teikna som eit tak",
            "ei mjuk, flat skalleform som vert skyvd under ei lukka kontordør som eit ark",
        ],
        merknader=["ELVANE I NORD VART LAGDE I RØYR", "FONTANELLAR", "SUTURAR", "EIN SKALLE ER ÒG EI MASKIN Å BU I"],
        ref="middels",
    ),
    dict(
        tekst="UNDER HIMLINGA ER DET LIMT KVITE PLATER AV PRESSA STEINULL SÅ KVAR SETNING MISSER VENGJENE OG EIT ROLEG SPØRSMÅL DØYR UT PÅ TO METER OG VERT TIL ISOLASJON. PÅ BORDA STÅR MODELLAR I MÅLESTOKK EIN TIL HUNDRE MED SKUMPLASTMENNESKE UTAN INNVOLAR, UTAN HUSLEIGE, UTAN REDSLE FOR EI LÅST DØR, LIMTE FAST FRAMFOR TRAPPER INGEN GÅR I. OVER JERNBRUENE VED AKERSELVA MÅ SOLDATAR BRYTE TAKT FORDI KVART SPENN HAR SIN EIGENFREKVENS OG STÅLET RYK TVERS AV OM ALLE GÅR LIKT.",
        teikningar=[
            "ei himling av akustikkplater; ei setning med små venger som fell til golvet etter to meter",
            "ein arkitektmodell med små skumfigurar limte framfor ei trapp",
            "ei jernbru over ei elv med marsjerande føter og ei svingande bølgje i spennet",
        ],
        merknader=["PRESSA STEINULL", "DØYR UT PÅ TO METER", "MÅLESTOKK EIN TIL HUNDRE", "EIGENFREKVENS"],
        ref="middels",
    ),
    dict(
        tekst="HER INNE ER DET MOTSETTE VEDTEKE: PÅ TAVLENE STÅR DEN DOBLE DIAMANTEN — DISCOVER, DEFINE, DEVELOP, DELIVER — TO KJEVAR SOM OPNAR SEG OG KLAPPAR ATT OG PRESSAR ALT UREGJERLEG GJENNOM FLASKEHALSEN TIL GLATT LEVERANSE. FIRE STEG I TAKT OVER EI BRU, OG DE KALLAR DET METODE. PÅ SKJERMANE GÅR ÅRSHJULET, TANNLAUST OG FRIKSJONSLAUST, TOLV SEKTORAR BERRE FRAMOVER ATTENDE TIL NULL. DÅ EG BAD OM EIT STUDIEÅR ATT, FANST DET INGA PIL SOM VISSTE KOR HO SKULLE SNU. EG HADDE FUNNE EIT HOL I DIAMANTEN; HOL GÅR IKKJE INN I MODELLEN, BERRE UT AV HAN.",
        teikningar=[
            "to diamantar på ei tavle teikna som to kjevar som opnar og lukkar seg, med uregjerlege former som vert pressa gjennom ein flaskehals",
            "fire like steg over ei bru",
            "eit tannlaust hjul delt i tolv sektorar med ei pil berre framover",
            "eit hol i diamanten med ei pil ut",
        ],
        merknader=["DISCOVER", "DEFINE", "DEVELOP", "DELIVER", "TO KJEVAR", "HOL GÅR IKKJE INN I MODELLEN, BERRE UT AV HAN."],
        ref="mykje",
    ),
    dict(
        tekst="ME SAT INNI MASKINA OG TEIKNA HENNE I EIN TIL HUNDRE. MED PASSAREN DROG EG EIN KVART SIRKEL VED KVAR TERSKEL; PÅ ARKET MITT STOD DØRA TIL REKTOR OPEN. DU TOK TEIKNINGA MED NED I KJELLAREN; EG HELDT HENNE MOT BETONGEN MEDAN DU LA BLYANTEN PÅ SIDA TIL FØRST EIN KVIST OG SIDAN ÅRRINGANE STEIG FRAM I GRÅ GRAFITT PÅ BAKSIDA AV SNITTET, PÅ DET TYNNE, SUNDMALNE TREET ME KALLAR PAPIR.",
        teikningar=[
            "ein planteikning med dørslag teikna som kvarte sirklar med passar; éi dør står open",
            "eit ark halde mot ein betongvegg, ein blyant lagd på sida som gnir fram ein kvist og årringar (frottage)",
        ],
        merknader=["EIN KVART SIRKEL VED KVAR TERSKEL", "DØRA TIL REKTOR OPEN", "DET TYNNE, SUNDMALNE TREET ME KALLAR PAPIR"],
        ref="lite",
    ),
    dict(
        tekst="ME SKULLE LÆRE Å FORME; EG LÆRTE Å SKJERE HOL — EIT HOL I EI PLATE, EIT HOL I EIN DAG, EIT HOL I DET EG HADDE TRUDD EG SKULLE BLI — OG GJENNOM ALLE TRE SER EG NESTE KULL KOME INN PORTEN I AUGUST MED MATPAKKE OG UTAN Å KJENNE NAMNET PÅ NOKON. HAN TEK AV SEG JAKKA; HUSET TEK MÅL AV HAN MED EIN GONG, DET ER PLASS DERSOM HAN BRETTAR SEG. EG VILLE LEGGJE EI LITA UJAMNHEIT I GOLVET FØR HAN KOM: EIT NEI MED FØTER UNDER, EIT NEI SOM KAN BERAST AV TO, MED EIT SKÅR DER TOMMELEN FINN FESTE. DÅ EG SETTE DET PÅ BORDET, SA DEI DET MANGLA EI GRUNNGJEVING. EG SNUDDE DET; UNDERSIDA VAR FULL AV ANDLET, OG ALLE SÅG OPP.",
        teikningar=[
            "tre hol på rad: i ei plate, i eit kalenderark, i eit omriss av ein person; ei siktelinje gjennom alle tre",
            "ein ny student i porten med matpakke som tek av seg jakka, med målestrekar rundt seg",
            "ein liten gjenstand med føter, eit skår for tommelen, boren av to hender",
            "den same gjenstanden snudd: undersida full av små andlet som ser opp",
        ],
        merknader=["EIT HOL I EI PLATE, EIT HOL I EIN DAG", "DET ER PLASS DERSOM HAN BRETTAR SEG", "EIT NEI MED FØTER UNDER", "UNDERSIDA VAR FULL AV ANDLET"],
        ref="middels",
    ),
    dict(
        tekst="DEN 30. JUNI SKREIV EG TIL SKULEN FRÅ BORDET MITT PÅ SKULEN OG SPURDE KVA DEI LÆRER STUDENTANE Å SEIE NEI TIL. EG LA VED SNITTET FRÅ VERKSTADPORTEN TIL AKERSELVA MED KJELLARKVISTEN PÅ BAKSIDA OG MÅTTE BRETTE HUSET TO GONGER FØR DET GJEKK GJENNOM SI EIGA POSTLUKE: EIN HEIL DAG BRETTA I TRE, ELVA PRESSA RETT INNTIL ROMMET DER BREVET SKULLE OPNAST. DET VAR FEILEN EG HADDE GJORT: EG HADDE SENDT DYKK NOKO SOM RANN. SAME DAGEN KOM SVARET — MOTTEKE — OG EIT SAKSNUMMER, SAK 26/01143.",
        teikningar=[
            "eit langt snitt frå ein port til ei elv, bretta i tre som eit brev, med ein kvist på baksida",
            "brevet på veg gjennom ei postluke",
            "vatn som renn ut av brevet",
            "eit stempel på eit ark",
        ],
        merknader=["30. JUNI", "EIN HEIL DAG BRETTA I TRE", "EG HADDE SENDT DYKK NOKO SOM RANN", "MOTTEKE", "SAK 26/01143"],
        ref="middels",
    ),
    dict(
        tekst="FØR HADDE HUSET TRANSFORMATOREN PÅ BENKEN; NO HADDE DET OSS. DEI SETTE KONVOLUTTEN I PERMEN PÅ HYLLA, MEN VATNET RANN VIDARE GJENNOM JUNI OG JULI LANGS KANTEN AV SAKSNUMMERET. DET VAKS EIT POSTMOTTAK I MUNNEN MIN MEDAN EG VENTA; EG KJENDTE DEN BITRE SMAKEN AV FRIMERKELIMET, EIT LITE LAND MED LIM PÅ BAKSIDA SOM FESTA SEG TIL GANEN. DEI BAD MEG VENDE MEG TIL RETTE VEDKOMANDE; EG VENDE MEG SÅ MANGE GONGER AT DET SKAR SEG GJENGAR I FØTENE MINE, GJENGAR SOM PASSA RETT I BOLTEHOLA ETTER TRANSFORMATORANE. DEI KALLA DET TILHØYRSLE.",
        teikningar=[
            "ein perm på ei hylle der vatn renn ned langs kanten",
            "ein open munn med eit lite postmottak og eit frimerke festa til ganen",
            "føter som snur seg rundt og rundt og får skruegjengar, skrudde ned i bolthol i eit golv",
        ],
        merknader=["PERMEN PÅ HYLLA", "EIT LITE LAND MED LIM PÅ BAKSIDA", "RETTE VEDKOMANDE", "GJENGAR SOM PASSA RETT I BOLTEHOLA", "TILHØYRSLE"],
        ref="middels",
    ),
    dict(
        tekst="MASKINA GJEKK HEILE SOMMAREN OG PRODUSERTE DET SAME ROMMET: EI DØR, EIN STOL, EIN STUDENT. OM NATTA FLYTTA STOLANE SEG EIT HÅR OM GONGEN MOT KVARANDRE; OM MORGONEN STOD DEI SOM FØR, MED EIT REFERAT AV FERDA PÅ BORDET. INNE I VENTILASJONSKANALANE LÅG STØVET SOM GRÅ FILT, OG MILLIONAR BLINDE STØVMIDDAR BEITA FREDELEG PÅ HUDFLASSET ETTER REKTORAR, STUDENTAR OG REINHALDARAR — DEN EINASTE KOMITÉEN I HUSET SOM VERKAR UTAN SKILNAD OG ALDRI LEGG FRAM NOKO REFERAT.",
        teikningar=[
            "ei rekkje som gjentek seg: ei dør, ein stol, ein student, ei dør, ein stol, ein student",
            "stolar med små rørslestrekar mot kvarandre om natta, og eit referat på eit bord",
            "snitt gjennom ein ventilasjonskanal med støv som filt, og forstørra støvmiddar som beitar på hudflak",
        ],
        merknader=["EI DØR, EIN STOL, EIN STUDENT", "EIT HÅR OM GONGEN", "STØVMIDDAR", "ALDRI LEGG FRAM NOKO REFERAT"],
        ref="middels",
    ),
    dict(
        tekst="PÅ ALLMØTA TØMDE DEI ORDA SINE OVER LANGBORDET — OMSTILLING, SYNERGI, FRAMDRIFT, KVALITETSSIKRING — SOM VULKANSK OSKE OVER DEI SOM TAGDE; OM TUSEN ÅR KAN ARKEOLOGANE HELLE GIPS I HOLROMMA OG SJÅ NØYAKTIG KORLEIS KNOKANE VAR KNYTTE I FANGET. EG SLO STEMMEGAFFELEN MOT STÅLKANTEN PÅ BORDET, BERRE ÉIN TONE SOM NEKTA Å SØKKE; I VASSGLASET FRAMFOR REKTOR GJEKK RINGANE INNOVER MOT MIDTEN.",
        teikningar=[
            "eit langbord der ord fell som oske over sitjande figurar",
            "gipsavstøypingar av knytte hender i eit fang",
            "ein stemmegaffel slått mot ein stålkant",
            "eit vassglas ovanfrå med ringar som går innover mot midten",
        ],
        merknader=["OMSTILLING, SYNERGI, FRAMDRIFT, KVALITETSSIKRING", "VULKANSK OSKE", "ÉIN TONE SOM NEKTA Å SØKKE"],
        ref="middels",
    ),
    dict(
        tekst="DEI TALA OM POTENSIAL UTAN Å VITE AT POTENSIAL VERT MÅLT I VOLT. PÅ ORGANISASJONSKARTET SYNTE DEI KVA VEG EI RØYST SKULLE GÅ LANGS TYNNE SVARTE GREINER; PÅ DEN SOM GJEKK NEDOVER STOD DET MEDVERKNAD, OG ALLER NEDST STOD DEI TRE STUTTE VASSRETTE STREKANE FOR JORD. DEI HADDE MONTERT EIN LYNAVLEIAR SÅ ALT SOM GLØDDE VART LEIDD STILLFERDIG NED I GRUNNEN.",
        teikningar=[
            "eit voltmeter med to målepinnar",
            "eit organisasjonskart teikna som tynne svarte greiner; éi grein går nedover og endar i jordsymbolet med tre korte vassrette strekar",
            "ein lynavleiar på eit tak som leier ein glød ned i bakken",
        ],
        merknader=["POTENSIAL VERT MÅLT I VOLT", "MEDVERKNAD", "JORD", "LYNAVLEIAR"],
        ref="lite",
    ),
    dict(
        tekst="STIGANDE SPENNINGAR, SVIKANDE STILLINGAR. GUMMISÅLAR OG HUNDRE PROSENT ULL OVER FOSSILKALKEN OG ADMINISTRASJONSTEPPET I DEN TØRRASTE, MEST RESIRKULERTE LUFTA I BYGGET, MOT ARMERINGSJERNET I BETONGEN. KROPPEN VERT VEKSELSTRAUM, EI UJORDA VIKLING. DÅ BESLAGET FRÅ 1944 SLO I PORTEN, REISTE KATTEN PÅ RISTA PELSEN FØR HAN HADDE SNUDD SEG; HAN VART EIN PELSBREIDD STØRRE, EIT TILLEGG DET IKKJE FANST TABELL FOR I TEIKNEBOKA VÅR. EIT FELT KAN LYFTE EIT HÅR UTANFRÅ, MEN KATTEN GJER DET FRÅ ROTA: LANGS EI NERVEGREIN GÅR BODET TIL FEM MILLIONAR SMÅ SKRÅ MUSKLAR VED KVAR HÅRSEKK, UTANFOR VILJEN, UTAN STILLINGSINSTRUKS — MUSCULUS ARRECTOR PILI — DET SISTE SOM SVARAR FØR DET ER TID TIL Å TENKJE. HØYR KOR NÆR DØRSKILTET LIGG I DET LATINSKE NAMNET PÅ EIN REFLEKS REKTOR IKKJE RÅR OVER.",
        teikningar=[
            "gummisålar på eit teppe over fossilkalk, med små gnistar; ein kropp teikna som ei spole utan jording",
            "ein katt på ei rist med pelsen reist, ein pelsbreidd større enn omrisset sitt",
            "snitt gjennom hud: ein hårsekk med ein liten skrå muskel og ei nervegrein",
        ],
        merknader=["STIGANDE SPENNINGAR, SVIKANDE STILLINGAR", "EI UJORDA VIKLING", "MUSCULUS ARRECTOR PILI", "DET SISTE SOM SVARAR FØR DET ER TID TIL Å TENKJE"],
        ref="mykje",
    ),
    dict(
        tekst="DØRA MERKT REKTOR, DEN EINASTE DØRA I MASKINA SOM ALLTID VAR LUKKA OG TREIVST MED DET. FØR KNOKANE RØRDE DØRBLADET, HADDE UNDERARMEN ALT FÅTT BODET; HÅRA STOD RETT UT SOM KATTEPELS UNDER TORDENSKY, IKKJE FRYKT, FELTSTYRKE. I VENSTRE HAND HELDT EG BREVET FRÅ 30. JUNI, FRAMLEIS FUKTIG ETTER ELVA. ALT FÅNYTTES EG GJORDE, VAR FOR Å LAUSLATAST, IKKJE FRIKJENNAST.",
        teikningar=[
            "ei lukka dør med eit lite skilt",
            "ein underarm med hår som står rett ut før knokane rører dørbladet, feltlinjer rundt",
            "ei venstre hand som held eit fuktig brev med vassdropar",
        ],
        merknader=["REKTOR", "IKKJE FRYKT, FELTSTYRKE", "FRAMLEIS FUKTIG ETTER ELVA", "LAUSLATAST, IKKJE FRIKJENNAST"],
        ref="lite",
    ),
    dict(
        tekst="NEDE VED SKOTUPPEN STOD LYSET FRÅ LYSRØYRET KLÅRT I KALKAUGET; FRÅ RØYRET TIL STEINEN, FRÅ STEINEN TIL NETTHINNA, DER LYSET SKIFTA FORM OG GJEKK VIDARE SOM STRAUM I GREINENE BAK AUGO. I KRANIET GJEKK TRANSFORMATOREN BAKLENGS: MØRKLEGGINGANE FRÅ RØYRET MATA MILLIVOLT ETTER MILLIVOLT OPP MOT TRE TUSEN VOLT PER MILLIMETER, DER LUFTA BRYT SAMAN. TØRR HUD ISOLERER; AUGET STÅR OPE, DEKT AV SALT VATN, KOPLA RETT INN I SKALLEN. OG LYN GÅR IKKJE FRÅ TOPPEN AV ORGANISASJONSKARTET OG NED; LYN SLÅR NÅR GOLVET SVARAR, NÅR SKILNADEN IKKJE ORKAR SEG SJØLV LENGER.",
        teikningar=[
            "ein strålegang: lysrøyr i taket, eit lite steinauge ved ein skotupp, eit auge med netthinne og greiner av nervar bak",
            "eit kranium med ein transformator inni, teikna baklengs, med ei stigande kurve",
            "eit lyn som går frå golvet og opp, ved sida av eit organisasjonskart",
        ],
        merknader=["FRÅ RØYRET TIL STEINEN, FRÅ STEINEN TIL NETTHINNA", "TRE TUSEN VOLT PER MILLIMETER", "LYN SLÅR NÅR GOLVET SVARAR"],
        ref="middels",
    ),
    dict(
        tekst="HØGRE HAND RØRDE METALLBESLAGET FRÅ 1944. KRINSEN SLUTTA SEG. DØRA GJEKK OPP. REKTOR STOD DER MED BREVET MITT I HANDA OG HELDT DET OPP MOT ÅRSHJULET PÅ VEGGEN FOR Å PEIKE UT KVAR DAGEN MIN HØYRDE TIL. SÅ SÅG HO PÅ MEG OVER KANTEN. DÅ VAR DET MI SIDE SOM SVARA.",
        teikningar=[
            "ei høgre hand som rører eit gammalt metallbeslag på ei dør; ein elektrisk krins som sluttar seg",
            "ei dør som går opp",
            "ein skjematisk kvinnefigur utan tydeleg andlet som held eit brev opp mot eit årshjul på veggen og ser over kanten av arket",
        ],
        merknader=["KRINSEN SLUTTA SEG.", "DØRA GJEKK OPP.", "DÅ VAR DET MI SIDE SOM SVARA."],
        ref="lite",
    ),
    dict(
        tekst="LYSBOGEN SLO UT FRÅ SYNSNERVANE BAK AUGO, LANGS GREINFESTET DU HADDE HENTA OPP FRÅ KJELLAREN, GJENNOM ALLE TRE LAGA AV BREVET — JUNIELVA OG TREFIBRANE BLAFFA KVITT — GJENNOM BESLAGET OG BEINT GJENNOM REKTOR, FRÅ PUPILL TIL PEIKEFINGER, SLIK SKRIFT GÅR GJENNOM DEN SOM LES. SKALLE OG RIBBEIN TEIKNA SEG EIT AUGNEBLINK I KALK MOT MØRKRET MEDAN HÅRA REISTE SEG OVER HANDLEDDET HENNAR.",
        teikningar=[
            "ein lysboge som går frå synsnervane bak eit auge, langs ein kvist, gjennom tre lag av eit bretta brev",
            "ein skjematisk figur der skalle og ribbein syner seg som omriss i eit augneblink, utan blod eller skade",
            "hår som reiser seg over eit handledd",
        ],
        merknader=["FRÅ PUPILL TIL PEIKEFINGER", "SLIK SKRIFT GÅR GJENNOM DEN SOM LES", "SKALLE OG RIBBEIN"],
        ref="lite",
    ),
    dict(
        tekst="BOGEN REIV OVER DEN DOBLE DIAMANTEN, SVEISA ÅRSHJULET FAST UNDER NEGLEN HENNAR DER JUNI LIGG INNTIL JULI SÅ HJULET IKKJE KOM LENGER, TEIKNA RAUDE LICHTENBERG-BREGNER LANGS RYGGRADENE I ROMMET — SAME GREINMØNSTER SOM TREA OG NERVANE — OG STUPTE NED GJENNOM ALLE SEKSTI KALKSPATPRISMA I TRILOBITTAUGET, SOM BLINKA SAMSTUNDES, LANGS ARMERINGSJERNET FORBI ÅRRINGANE I KJELLAREN RETT I GRUNNEN. DÅ HO BRETTA BREVET UT, SAT DET TRE SVARTE SVIHOL I ARKET MED SAME BRENDE RANDA SOM I OLJEPAPIRET FØR: EITT VED BORDET HENNAR, EITT VED MITT, EITT DER ELVA GÅR UT AV TEIKNINGA.",
        teikningar=[
            "ein boge som riv over to diamantar og sveisar eit hjul fast",
            "greinete lichtenbergfigurar langs ei ryggsøyle, ved sida av eit tre og ei nervegrein med same mønster",
            "lynet som stuper gjennom eit trilobittauge, langs armeringsjern og forbi årringar ned i grunnen",
            "eit utbretta brev med tre svarte svihol",
        ],
        merknader=["LICHTENBERG-BREGNER", "SAME GREINMØNSTER SOM TREA OG NERVANE", "TRE SVARTE SVIHOL", "EITT DER ELVA GÅR UT AV TEIKNINGA"],
        ref="middels",
    ),
    dict(
        tekst="NEDE I MORENESANDEN UNDER STØYPEN SMELTA KVARTSEN VED TRE TUSEN GRADER TIL EIN FULGURITT: EI HOL GLASGREIN AV FORSTEINA LYN, RU AV SANDKORN PÅ UTSIDA, BLANK OG GLATT INNI DER LYSET FÓR, FORMA NØYAKTIG ETTER DET SOM BRANN GJENNOM HENNE — EIT BLIKK, EIT BREV, EIN REKTOR, EIT ÅRSHJUL, EI GREIN UTAN TRE, EIT TRE INGEN KAN KALLE EIN FUNKSJON.",
        teikningar=[
            "snitt gjennom sand under eit betonggolv med ein greinete fulguritt",
            "eit stykke fulguritt skore over: ru utside, glatt hol inni",
            "fulgurittgreina teikna som eit tre utan stamme",
        ],
        merknader=["FULGURITT", "TRE TUSEN GRADER", "RU AV SANDKORN PÅ UTSIDA, BLANK OG GLATT INNI", "EIT TRE INGEN KAN KALLE EIN FUNKSJON"],
        ref="lite",
    ),
    dict(
        tekst="MEDAN DEI ANDRE SAMLA POENG, SAT DU URØRLEG PÅ STÅLRØYRSSTOLEN OG TALDE BAKLENGS MOT KAMBRIUM. DÅ DEI KOM MED SKJEMA OG BAD OM DIALOG, DROG DU HAKA INN OG RULLA DEG SAMAN, LEDD FOR LEDD, TIL EI LUKKA KULE AV KALK UTAN NOKON MJUK STAD Å SETJE KRYSS MED KULEPENN. AUGO DINE STIVNA FØRST, SEKSTI PRISME AV REIN KALKSPAT SOM SÅG GJENNOM GLASET, GJENNOM GIPSEN OG GJENNOM DET STANSA ÅRSHJULET RETT NED I MINERALRIKET.",
        teikningar=[
            "ein figur urørleg på ein stålrøyrsstol, med ei tidslinje som går baklengs",
            "ein trilobitt som rullar seg saman ledd for ledd til ei lukka kule, i fire steg",
            "eit skjema og ein kulepenn som ikkje finn nokon mjuk stad",
        ],
        merknader=["TALDE BAKLENGS MOT KAMBRIUM", "LEDD FOR LEDD", "EI LUKKA KULE AV KALK", "RETT NED I MINERALRIKET"],
        ref="middels",
    ),
    dict(
        tekst="I OKTOBER STOD PLASSEN DIN TOM, PROTOKOLLFØRT SOM FRÅFALL. PÅ SETET LÅG BERRE EIT TØRT RYGGSKJOLD, KLØYVT REINT LANGS ANDLETSSAUMEN OVER KINNET SLIK SKALET SPRIKJER NÅR FORMA VERT FOR TRONG. EG LÉT VERE Å LIME SAUMEN; EI DØR SOM OPNAR SEG BERRE ÉIN GONG, TRENG IKKJE BESLAG. DYRET VAR UTE AV FORMA, MJUKT OG UTAN ETTERNAMN, GÅTT NED GJENNOM SLUKET I KJELLAREN DER TRANSFORMATOROLJA RANN UT FØR, DIT PERSONNUMMERA SØKK MOT NULL. ETASJEN OVER SIT EI ARBEIDSGRUPPE OG SKRIV OM DANNING. NEDE I DET SVARTE SLAMMET SKREIV DU MED EIN TØRR KVIST: FORSVINNING ER DANNING. DET ER INGEN SOM STRYK I URTIDA; DET ER BERRE VENTETID FRÅ LEIRE TIL SKIFER.",
        teikningar=[
            "eit tomt stolsete med eit tørt trilobittskal, kløyvt langs andletssaumen",
            "eit sluk i eit kjellargolv",
            "snitt gjennom etasjar: eit møtebord øvst, svart slam nedst der ein tørr kvist skriv",
        ],
        merknader=["PROTOKOLLFØRT SOM FRÅFALL", "KLØYVT REINT LANGS ANDLETSSAUMEN", "FORSVINNING ER DANNING", "FRÅ LEIRE TIL SKIFER"],
        ref="middels",
    ),
    dict(
        tekst="PÅ GIPSVEGGEN I VERKSTADEN HAR NOKON PLUKKA UT TEIKNESTIFTANE: FIRE SVARTE NÅLESTIKK RUNDT EIT LYST, UBLEIKA REKTANGEL SOM IKKJE HAR GULNA UNDER LYSRØYRA, EIT SPØKELSE ETTER EIT BILETE. INNANFOR VAKTA STÅR POSTHYLLENE FRÅ GOLV TIL TAK SOM EIT ROMERSK COLUMBARIUM, HUNDRE FIRKANTA NISJAR FOR OSKE OG UOPNA SKRIV. EIN TOMMELNEGL VIPPAR BORT NAMNESTRIMMELEN ETTER EIN SOM NETT BAR UT KOPPEN SIN I EIN PLASTPOSE; UNDER LIMET ER PLASTEN ALLTID LITT LYSARE.",
        teikningar=[
            "ein vegg med fire små nålestikk rundt eit lyst rektangel",
            "posthyller frå golv til tak med firkanta nisjar, som eit columbarium",
            "ein tommelnegl som vippar bort ein namnestrimmel, med ein lysare stripe under",
        ],
        merknader=["FIRE SVARTE NÅLESTIKK", "EIT SPØKELSE ETTER EIT BILETE", "COLUMBARIUM", "UNDER LIMET ER PLASTEN ALLTID LITT LYSARE"],
        ref="lite",
    ),
    dict(
        tekst="MEN VATNET FRÅ JUNIBREVET HADDE SIGE NED LANGS STÅLBOLTANE. UNDER SANDEN SPREKK OSLOS SVARTE ALUNSKIFER, GAMAL HAVBOTN UTAN PUST. SÅ LENGE SKIFEREN FÅR LIGGJE I MØRKRET, TEIER HAN; MEN SLEPPER LUFT OG ELVEVATN NED TIL SVOVELKISEN, VAKNAR HAN OG BRENN UTAN ELD. STEINEN SVELL, ET OPP STÅLBOLTANE OG LYFTAR GRUNNMUREN MILLIMETER FOR MILLIMETER MELLOM ÅTTE OG FIRE, ALDRI MELDT INN SOM AVVIK — VERDAS LANGSAMASTE OPPRØR. GJENNOM HÅRFINE RISS I KJELLAREN SIV RADON, EI USYNLEG DOTTER AV URAN, OG SET SEG VED BORDET I ROM DER INGEN OPNAR VINDAUGO. EIN MORGON TOK DØRBLADET NEDI DER DET FØR GJEKK FRITT OG RISSA SIN EIGEN KVARTSIRKEL I KALKSTEINEN, OG AUGET DU VISTE MEG HADDE SKIFTA SYNSVINKEL UTAN Å FLYTTE SEG UT AV STEINEN.",
        teikningar=[
            "geologisk snitt under ein bygning: vatn som sig ned langs boltar til lagdelt skifer som sveller og lyftar grunnmuren",
            "små prikkar som stig opp gjennom riss i eit kjellargolv inn i eit rom",
            "eit dørblad som har rissa ein kvart sirkel i eit steingolv",
        ],
        merknader=["ALUNSKIFER", "SVOVELKISEN", "VERDAS LANGSAMASTE OPPRØR", "RADON", "SIN EIGEN KVARTSIRKEL"],
        ref="middels",
    ),
    dict(
        tekst="VED GLASDØRA HELDT EG KORTET MOT LESAREN I SLUDDET. EI VIKLING I VEGGEN VAKTE EI VIKLING I PLASTEN, INDUKSJON EIN SISTE GONG, NETT NOK KRAFT TIL AT HUSET KJENDE MEG ATT. DET LYSTE RAUDT. ALT DET ELEKTRISKE VAR I ORDEN. DET GJEKK FORTARE Å BLI INGEN ENN Å BLI TIL. SPEGELBILETET MITT LOSNA FRÅ RUTA, SNUDDE OG GJEKK INN ATT I VEKSELSTRAUMEN UTAN MEG; DET NIKKAR HØFLEG, SKRIV UNDER PÅ ALT, TEK IMOT FUNKSJON, TEK IKKJE PLASS.",
        teikningar=[
            "eit kort halde mot ein kortlesar ved ei glasdør i sludd; ei spole i veggen og ei spole i kortet med feltlinjer",
            "ei lita lampe som lyser",
            "eit spegelbilete som losnar frå ei glasrute, snur og går inn att",
        ],
        merknader=["INDUKSJON EIN SISTE GONG", "DET LYSTE RAUDT.", "DET GJEKK FORTARE Å BLI INGEN ENN Å BLI TIL.", "TEK IKKJE PLASS"],
        ref="lite",
    ),
    dict(
        tekst="FØR EG SNUDDE, LA EG EIN SVART, RUND ELVESTEIN PÅ SKRANKEN I RESEPSJONEN — EIN GASTROLITT, SLIK UTDØYDDE KJEMPEØGLER SLUKTE FOR Å KVERNE SUND SEIGE PLANTAR I MØRKRET I BUKEN. HAN HAR INGA UNDERSKRIFT. HAN VERT LIGGJANDE DER LENGE ETTER AT GLASET HAR FALLE UT AV OVERLYSET OG REGNET RENN RETT GJENNOM HALLEN OG VASKAR GOLVET REINT. I PORTEN MØTTE EG EI JENTE FRÅ FØRSTE KULL MED GIPSSTØV I AUGNEVIPPENE OG LEIRE UNDER NEGLANE SOM VEKS EIN TIANDEDELS MILLIMETER I DØGNET ANTEN DET STÅR I PLANEN ELLER IKKJE. ME SÅG PÅ KVARANDRE UTAN Å SEIE NOKO, SLIK TO FRAMANDE SER GJENNOM VÅTE BUSSGLAS I EIT LYSKRYSS FØR DET SKIFTAR TIL GRØNT.",
        teikningar=[
            "ein svart, rund stein på ein skranke",
            "snitt av ei kjempeøgle med steinar i magen",
            "ein hall utan glas i overlyset, regn som renn gjennom",
            "ei hand med leire under neglane og eit auge med støv i augnevippene",
        ],
        merknader=["GASTROLITT", "HAN HAR INGA UNDERSKRIFT.", "EIN TIANDEDELS MILLIMETER I DØGNET"],
        ref="middels",
    ),
    dict(
        tekst="BAK VERKSTADEN STÅR EIT OSPETRE. GREINENE TEIKNAR SAME MØNSTERET I LUFTA SOM LYNET TEIKNA I JORDA; BLADSTILKEN ER VRIDEN NITTI GRADER OG GJEV ETTER FØR VINDEN NÅR BAKKEN SÅ STORMEN SLEPP FORBI OG GREINA HELD. INNE LÆRER DEI Å GJERE FORMA FAST; UTE LEVER FORMA AV AT HO KAN FORANDRE SEG. I TOPPEN SIT EI KRÅKE, KVIT AV GIPSSTØV, OG SER GJENNOM TRE LAG ISOLERGLAS PÅ DEI SOM FLYTTAR SMÅ KVITE MENNESKE AV SKUMPLAST OVER PAPP-TORG I MÅLESTOKK EIN TIL HUNDRE. HO HARKAR OPP EIN RUSTEN MUTTER FRÅ TRANSFORMATORHALLEN OG SLEPPER HAN MOT STEINEN SÅ EIN EKTE TONE ENDELEG GÅR GJENNOM HUSET.",
        teikningar=[
            "eit ospetre over bakken og ein spegla fulgurittgreinverk under bakken, same mønster",
            "eit ospeblad med bladstilken vriden nitti grader",
            "ei kråke i trekrona som slepper ein mutter, med lydbølgjer",
        ],
        merknader=["BLADSTILKEN ER VRIDEN NITTI GRADER", "UTE LEVER FORMA AV AT HO KAN FORANDRE SEG", "EIN RUSTEN MUTTER", "EIN EKTE TONE"],
        ref="lite",
    ),
    dict(
        tekst="UTANFOR MUREN RENN AKERSELVA SVART I HAUSTFLAUMEN, UTE AV JUNIKONVOLUTTEN. PÅ BOTNEN HAR PAPIRET GITT FRÅ SEG DATOEN OG LØYST SEG OPP TIL TREVLAR OG ULESELEGHEIT. DET FINST TO SLAGS HOL I VERDA: DET LYNET BRENN I SANDEN PÅ EITT SEKUND, OG DET SOM BYRJAR MED EI LITA UJAMNHEIT MIDT I STRAUMEN. EIN RUND GRÅSTEIN UTAN IDEOLOGI LEGG SEG I SKÅRET, VERT IKKJE MED VIDARE TIL B, OG TYNGDA AV ELVA TVINGAR HAN RUNDT OG RUNDT PÅ SAME FLEKKEN, EITT SANDKORN DJUPARE FOR KVAR OMDREIING — VATN MOT STEIN, STEIN MOT GRANITT.",
        teikningar=[
            "ei elv i flaum der eit papir løyser seg opp i trevlar",
            "to hol side om side: eit greinete hol brent i sand, og eit rundt hol som byrjar med ei lita ujamnheit",
            "ein rund stein som går rundt og rundt i ei grop, med spiralpiler",
        ],
        merknader=["TO SLAGS HOL I VERDA", "EIN RUND GRÅSTEIN UTAN IDEOLOGI", "VATN MOT STEIN, STEIN MOT GRANITT"],
        ref="lite",
    ),
    dict(
        tekst="ELLEVE HERTZ GJENNOM GRUNNMUREN, UNDER MIKROFONANE PÅ STYREBORDET, FOR SEINT TIL Å FØRAST I REFERAT. MEN HAMMAREN, AMBOLTEN OG STIGBØYLEN — EI LITA SMIE ELDRE ENN SPRÅKET, OPPHENGD I MØRKRET I TINNINGBEINET — SVINGAR MED. UTAN INNSKRIFT AV LYN ELLER NEGL MEL RULLESTEINEN SEG SJØLV NED TIL INGENTING. ATT STÅR JETTEGRYTA I GRUNNFJELLET, FULL AV SVART VATN OG HIMMEL, EIT HOLROM INGEN KAN OMORGANISERE.",
        teikningar=[
            "langsame bølgjer gjennom ein grunnmur under eit bord med mikrofonar",
            "dei tre øyrebeina, hammaren, ambolten og stigbøylen, teikna som ei lita smie",
            "ei djup rund jettegryte i berget, full av vatn som speglar himmelen",
        ],
        merknader=["ELLEVE HERTZ", "HAMMAREN, AMBOLTEN OG STIGBØYLEN", "JETTEGRYTA", "EIT HOLROM INGEN KAN OMORGANISERE"],
        ref="lite",
    ),
    dict(
        tekst="EG SKRUDDE FØTENE LAUS FRÅ GOLVET, OMDREIING FOR OMDREIING, TIL GJENGANE VAR SLITNE NED TIL GLATT HUD ATT, OG GJEKK UT I AKERSELVA MED TØRRKVISTAR OG SKUM OG ALT SOM IKKJE LET SEG BRETTE. UNDER YTA VAKS SVART HUD MELLOM TÆRNE DER GJENGANE SAT; EG SKYV FRÅ MOT STRAUMEN UTAN AT NOKON SER ARBEIDET. I NOVEMBERKULDA REISTE HÅRA PÅ ARMANE SEG PÅ NYTT OG LA SEG IKKJE; SMÅ GREINER SKAUT UT FRÅ KVART SKAFT, FJØR LA SEG OVER FJØR, OG MELLOM LAGA LÅG TØRR LUFT MOT HUDA. DET ER DENNE LUFTA EG BUR I NO.",
        teikningar=[
            "føter som vert skrudde laus frå eit golv, gjengane slitne glatte",
            "ein fot med svømmehud under vassflata som skyv mot straumen",
            "hår på ein arm som greiner seg ut og blir fjør, lag på lag med luft imellom",
        ],
        merknader=["OMDREIING FOR OMDREIING", "SVART HUD MELLOM TÆRNE", "FJØR LA SEG OVER FJØR", "DET ER DENNE LUFTA EG BUR I NO."],
        ref="lite",
    ),
    dict(
        tekst="HALSEN HAR VORTE SÅ LANG I HAUST AT EG KAN BØYE HAN I EIN KVIT BOGE NED GJENNOM SPEGELBILETET AV TEIKNESALEN, HEILT NED TIL BOTNSTEINANE OVER SKIFEREN DER DU LIGG VED SIDA AV DEN HOLE GLASGREINA. EG LEITAR MED MUNNEN I GRUSEN ETTER PUNKTSKRIFTA I STEINKNUDDERET, EIT DØDT SPRÅK ME BEGGE FORSTÅR NO NÅR INGEN AV OSS HAR STUDIERETT LENGER. EIN DAG ER HEILE BYGNINGEN GRUS ATT; DÅ SKAL ARKEOLOGAR ETTER MENNESKET FINNE EI GRYTE I FJELLET, EI GLASGREIN I SANDEN OG DEG I SKIFEREN — TRE MINNESMERKE UTAN INNSKRIFT.",
        teikningar=[
            "ein lang kvit svanehals bøygd ned gjennom ei vassflate der ein teiknesal er spegla",
            "eit nebb som leitar i grus med små knuter som punktskrift",
            "tre gjenstandar i lag under kvarandre: ei gryte i fjellet, ei glasgrein i sanden, ein trilobitt i skifer",
        ],
        merknader=["PUNKTSKRIFTA I STEINKNUDDERET", "TRE MINNESMERKE UTAN INNSKRIFT"],
        ref="lite",
    ),
    dict(
        tekst="INNE I KORRIDORANE TRUR DEI TYNGD ER DET SAME SOM ALVOR. KNOKLANE MINE HAR TØMT SEG GJENNOM HAUSTEN; NOVEMBERLUFTA DREG GJENNOM MARGPIPENE UTAN FUNKSJON. I KJØLEN PÅ BRYSTBEINET LIGG LUFTRØYRET I EI DOBBEL SLØYFE, SOM KOPARTRÅD KRING EIN JERNKJERNE, SOM EIN BRONSELUR I EI MYR — EIT HORN INGEN HAR BLÅSE I ENNO. I REFERATET STÅR DET STUM. DET ER LENGER FRÅ BRYSTET MITT TIL MUNNEN ENN DEN SOM TOK MÅL AV MEG KUNNE SJÅ, OG INSTRUMENTET SKAL BERRE BRUKAST ÉIN GONG, VED AVREISE.",
        teikningar=[
            "snitt gjennom ein hol fugleknokkel med tynne stag inni",
            "eit fuglebrystbein med kjøl der luftrøyret ligg i ei dobbel sløyfe, ved sida av ein spole kring ein jernkjerne",
            "ein lang bronselur som ligg i ei myr",
        ],
        merknader=["MARGPIPENE UTAN FUNKSJON", "EI DOBBEL SLØYFE", "EIN BRONSELUR I EI MYR", "STUM", "VED AVREISE"],
        ref="lite",
    ),
    dict(
        tekst="SLUDDET VERT TØRR SNØ OG LEGG SEG PÅ SKULDRENE MINE UTAN Å SMELTE, KVITT PÅ KVITT, EITT MED VÊRET. OVER SKYENE STÅR FEM STJERNER SPENTE I KROSS MED STRAK HALS LANGS MJØLKEVEGEN, PÅ VEG UT AV KARTET. ISEN KRYP UT FRÅ BEGGE BREIDDENE TIL BERRE EI SMAL SVART RÅK PEIKAR SØROVER MOT FJORDEN. EG SNUR MEG MOT VINDEN OG STREKKJER ARMANE UT, TO METER FRÅ SPISS TIL SPISS; DET SMELL SOM VÅTE LAKEN I FROSTEN NÅR EG SLÅR. EG ER FOR TUNG TIL Å LETTE FRÅ STADEN OG SPRING PÅ VATNET FØRST — TUNGE STEG MOT DEN SVARTE HINNA, EITT, TO, TRE — MED STADIG LENGRE MELLOMROM TIL DET SOM SVARAR UNDER MEG IKKJE LENGER ER VATN.",
        teikningar=[
            "fem stjerner i kross langs eit band av stjerner (stjernebiletet Svanen)",
            "ei elv sett ovanfrå med is frå begge breiddene og ei smal svart råk",
            "ein svane som spring på vatnet med vengene ute, to meter frå spiss til spiss, med fotavtrykk med stadig lengre mellomrom",
        ],
        merknader=["FEM STJERNER SPENTE I KROSS", "TO METER FRÅ SPISS TIL SPISS", "EITT, TO, TRE"],
        ref="lite",
    ),
    dict(
        tekst="FROSTLUFTA SLÅR GJENNOM HOLE KNOKLAR INN I DEN DOBLE SLØYFA I BRYSTBEINET. ÉIN DJUP, LANG TONE LOSNAR UTAN NAMN OG UTAN SAKSNUMMER OG FORSVINN IDET HAN LYDER — IKKJE EIT SKRIK, BERRE DET HUSET ALDRI FEKK HØYRE.",
        teikningar=[
            "luft som strøymer gjennom hole knoklar inn i ei dobbel sløyfe i eit brystbein",
            "éin lang, tynn tonelinje som går ut frå ein svanehals og tynnast ut til ingenting over mykje kvitt papir",
        ],
        merknader=["ÉIN DJUP, LANG TONE", "IKKJE EIT SKRIK"],
        ref="lite",
    ),
    dict(
        tekst="UNDER MEG I SNØDREVET KRYMPAR MARIDALSVEGEN 29 TIL MÅLESTOKK EIN TIL HUNDRE, SÅ LITE AT EG KAN TA HUSET MED MEG HEILT UTAN Å BRETTE ELVA, VIDARE NEDOVER SKALAEN TIL DET MINSTE REKTANGELET, BORTE I EIN AVRUNDINGSFEIL, EIT KVITT FORSVINNINGSPUNKT BAK SENKA AUGELOK. I MORGON TIDLEG SKAL DEN SOM KJEM ETTER MEG GÅ LANGS ELVA MED TERMOSKOPPEN I HANDA OG STUSSE OVER SPORA I SØRPA PÅ NYISEN: BREIE AVTRYKK MED HUD MELLOM TÆRNE SOM TOK FART LANGS MUREN MED STADIG LENGRE STEG FØR DEI SLUTTA MIDT UTE PÅ DJUPET UTAN Å KOME NED ATT.",
        teikningar=[
            "ein verkstadhall sett ovanfrå som krympar i fleire steg til eit lite rektangel og eit forsvinningspunkt",
            "ein person med termoskopp på ein elvesti",
            "fotspor med svømmehud på nyis, med stadig lengre mellomrom, som sluttar midt ute",
        ],
        merknader=["MÅLESTOKK EIN TIL HUNDRE", "EIT KVITT FORSVINNINGSPUNKT", "STADIG LENGRE STEG"],
        ref="lite",
    ),
    dict(
        tekst="SNØEN FYLLER ATT KVAR EINASTE FURE LANGS VEGGEN, KRYSTALL FOR KRYSTALL, TIL NYISEN LIGG SLETT OG ULESELEG UTANFOR EIT TOMT HUS DER DET GAMLE LYSRØYRET I KORRIDOREN FRAMLEIS SLOKNAR OG TENNEST HUNDRE GONGER I SEKUNDET, MED MØRKRE IMELLOM, I DET EINE KALKAUGET DU FLYTTA HOVUDET MITT FOR Å SJÅ — FOR INGEN.",
        teikningar=[
            "snøkrystallar som fyller ei fure, éin og éin",
            "eit tomt hus med eit lysrøyr i korridoren som blinkar, med mørke mellomrom",
            "eit lite kalkauge i golvet som speglar lysrøyret, og ingen der",
        ],
        merknader=["KRYSTALL FOR KRYSTALL", "HUNDRE GONGER I SEKUNDET", "FOR INGEN."],
        ref="lite",
    ),
]
