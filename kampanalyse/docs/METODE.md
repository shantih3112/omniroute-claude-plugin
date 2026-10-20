# Analysemetode

Målet er etterprøvbar analyse, ikke flest mulig tips. Når ingen spill er godt begrunnet,
er riktig resultat å stå over.

## Daglig arbeidsflyt

| Tid (Oslo) | Steg |
|---|---|
| 06:15 | Kartlegg dagens kamper i valgte ligaer. Bare kamper som ikke har startet og som starter minst 30 min senere. |
| | Hent historikk per liga (inneværende + forrige sesong), odds fra alle bookmakere, NT-priser og fraværslister. |
| | Datakvalitet per kamp (0–1). Kamper under `MIN_QUALITY` utelates med begrunnelse. |
| | Vurder alle markeder med markedskonsensus. Rangér og lag kortliste (maks 3 per kamp). |
| | Bygg bonger i bånd B–G av kvalifiserte enkeltspill. |
| 08:00 | **Kontroll før publisering:** ferske priser, kampstatus og tid. Ledd under minste odds trekkes; bonger med trukne ledd publiseres ikke. Deretter brief og bonger. |
| −70 til 0 min | Bekreftede oppstillinger. Avvik mot fraværslisten og nye fravær varsles. |
| −10 min | Sluttodds lagres (for CLV). |
| Under kamp | Livedata hvert 60. sekund. Hendelser, tilstand per ledd, utsatte/avbrutte kamper. |
| Etter kamp | Bekreftelsesvindu (15 min uendret sluttresultat). Deretter oppgjør. Korrigeringer sjekkes i 3 timer. |
| Ved tap | Samlet varsel. Maks én ny analyse-runde per dag. |
| 23:30 | Dagsrapport. |

## Sannsynligheter

- **Rå implisitt sannsynlighet** = 1 / desimalodds. Den inkluderer bookmakerens margin.
- **Marginfri markedssannsynlighet:** Per bookmaker fjernes marginen med *power-metoden*. Den
  løser `Σ (1/oᵢ)^k = 1`, som håndterer favoritt/longshot-skjevhet bedre enn proporsjonal
  fjerning. Deretter tas medianen på tvers av bookmakere. Dobbeltsjanse avledes fra H-U-B.
- **Modell:** Tidsvektet Poisson (Maher) med Dixon-Coles-korreksjon for 0–0, 1–0, 0–1 og 1–1.
  - Angrep, forsvar og hjemmefordel estimeres fra kamper *før* analysedatoen, med halveringstid 180 dager og krymping mot ligasnitt (4 «pseudokamper»).
  - Når xG finnes, brukes 50/50 mål og xG.
  - Modellen gir en fordeling over oppgjørsutfall (vunnet, tapt, annullert, halvt vunnet, halvt tapt), så DNB, hele linjer og kvartlinjer prises riktig.
  - Fra fordelingen beregnes en *prisekvivalent* q = 1/rettferdig odds.
- **Brukt estimat:** `q = q_marked + w·(q_modell − q_marked)` med `w = 0,25`. Markedet er
  vanskelig å slå, og modellen er uvalidert, så den får bare påvirke svakt.
- **Usikkerhet:** `0,015 + min(0,06; 0,15/√n)`, der n er effektivt antall kamper for laget med
  minst data. Det legges til +0,01 ved færre enn 3 bookmakere og +0,01 uten modell.
- **Forventet verdi** per innsatsenhet: `(1 − push)·(q·odds − 1)`. Push er andelen
  tilbakebetaling. For valg uten push er dette p·odds − 1.
- **Minste akseptable odds:**
  - For spill merket *god pris*: oddsen der konservativ EV (med q − usikkerhet) faller under `MIN_EDGE` (3 %).
  - For øvrige: oddsen der punkt-EV faller under −4,5 %.

Et subjektivt kvalitetspoeng brukes aldri som sannsynlighet. Datakvalitet styrer bare
filtrering og usikkerhet.

## Tre ulike egenskaper

| Merke | Betydning |
|---|---|
| **Høy treffmulighet** | Ikke-tap-sannsynlighet ≥ 62 % og prisen er rimelig (EV ≥ −4 %). Ikke dokumentert verdi. |
| **God pris** | Konservativ EV ≥ 3 %. Usikkert så lenge modellen er uvalidert. |
| **Høy odds** | Odds ≥ 3,0 og rimelig pris. Lav treffmulighet. |

Spill der modellen er tydelig mer negativ enn markedet (> 3 poeng), brukes ikke som ledd.

## Begrunnelser

Argumenter for og mot bygges bare fra data som faktisk finnes:

- pris mot markedets marginfrie pris (bare når avviket er over 2 %)
- modell mot marked
- forventede mål mot ligasnitt
- xG
- forventet målforskjell
- resultater over eller under forventning (bærekraft)
- hviledager
- datagrunnlag
- kjente fravær
- kvartlinjer

Innbyrdes oppgjør vises som supplerende informasjon og påvirker ikke estimatet. Formuleringer som
«de må vinne» brukes ikke. Flere tall som beskriver samme forhold, f.eks. mål og xG, regnes ikke
som uavhengige bevis i estimatet; de vises bare som kontekst.

Taktikk (press, ballbesittelse, omstillinger) og spillerbetydning finnes ikke i datakilden.
Analysen sier dette eksplisitt i stedet for å late som.

## Bonger og korrelasjon

- Bonger bygges bare av kvalifiserte enkeltspill, med maks ett ledd per kamp. Bet builder brukes derfor ikke, og ingen pris blir feilberegnet ved å multiplisere avhengige odds.
- Søket er en strålesøk som maksimerer `log(treffanslag) + 2·EV − straff for gjenbruk` innenfor båndet.
- Hovedbongen (B) bruker bare ledd merket *høy treffmulighet* eller *god pris*, med kvalitet ≥ 0,65.
- Bånd D–G merkes *spekulativ*.
- Treffanslag er produktet av ledd-anslagene. Det forutsetter uavhengighet mellom ulike kamper og vises som grovt anslag.
- Totalodds er produktet av leddene og merkes «ikke verifisert» til alle ledd er kontrollert hos NT.
- Overlapp vises: «Deler kamp med …». Ett resultat kan ødelegge flere bonger, og varsler om tap samles per kamp.
- Ekstrarunden etter tap kan ikke bruke ledd fra bonger som fortsatt er aktive. Nesten identiske bonger skal ikke fremstå som risikospredning.

## Live-tilstander

| Tilstand | Betydning |
|---|---|
| Lever | Utfallet kan fortsatt gå begge veier |
| Virker vunnet/tapt | Bare monotone markeder (over/under, BTTS, lagtotaler). Kampvinner og handikap merkes aldri avgjort underveis. |
| Slutt – venter på bekreftelse | Sluttresultat sett, bekreftelsesvindu pågår. Endres resultatet, starter vinduet på nytt. |
| Bekreftet | Sluttresultat uendret i 15 min. Norsk Tippings oppgjør er gjeldende. |
| Uavklart | Utsatt, avbrutt eller avlyst kamp, eller manglende data. Følg NTs oppgjør. |

## Validering (før modellen får høyere vekt)

`python -m kampanalyse backtest E0_2223.csv E0_2324.csv E0_2425.csv`

Backtesten:

- refitter ukentlig, bare på kamper før datoen
- sammenligner modell, marked og blanding med log loss og Brier
- viser kalibrering i 10 intervaller
- simulerer flat innsats mot B365- eller snittpris (ikke maks-odds)
- måler CLV mot Pinnacles sluttodds

Kriterier før vekten økes:

- Blandingen slår markedsreferansen på log loss over flere sesonger og ligaer.
- Kalibreringen er god.
- Positiv CLV over minst flere hundre spill.

Kortsiktige gevinstperioder er ikke bevis. Modellen justeres ikke etter enkelttap.
