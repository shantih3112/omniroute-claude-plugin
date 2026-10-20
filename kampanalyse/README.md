# Kampanalysen

En Telegram-bot for fotballanalyse og daglige spillforslag, tilpasset Norsk Tipping (Oddsen).
Boten analyserer dagens kamper, rangerer enkeltspill og bygger kombinasjoner i flere
oddsnivåer. Den sender morgenbrief kl. 08:00 og følger aktive kamper automatisk. All
historikk lagres åpent.

> Ingen modell kan garantere gevinst. Boten presenterer analyser, aldri sikre spill.
> Du leverer selv eventuelle spill hos Norsk Tipping. Boten plasserer ingen spill og håndterer ikke penger.
> Hjelpelinjen: 800 800 40.

## Innhold

- [Arkitektur](#arkitektur)
- [Kom i gang (demo uten nøkler)](#kom-i-gang-demo-uten-nøkler)
- [Produksjonsoppsett](#produksjonsoppsett)
- [Telegram-design og kommandoer](#telegram-design-og-kommandoer)
- [Kostnader og tilganger](#kostnader-og-tilganger)
- [Hva virker og hva gjenstår](#hva-virker-og-hva-gjenstår)
- Utdypning: [docs/METODE.md](docs/METODE.md) · [docs/DRIFT.md](docs/DRIFT.md) · [docs/eksempel-demo.txt](docs/eksempel-demo.txt)

## Arkitektur

Én Python-prosess, én SQLite-fil. Jeg valgte dette bevisst fordi det er enkelt og robust:

```
                   ┌───────────────────────── kampanalyse (én prosess) ───────────────────────────┐
API-Football ─────►│ providers/   →  analysis.py  →  coupons.py  →  repo.py (SQLite, varig volum) │
NT-kilder ────────►│ (manuell /     marked + modell   bånd B–G,      forslag, versjoner, outbox,   │
(manuell/tredjep.) │  tredjepart)   + usikkerhet      1 ledd/kamp    endringslogg, helse         │
                   │                                                                               │
                   │ engine.tick() hvert 30. sek: analyse 06:15 · kontroll + brief 08:00 ·         │
                   │ oppstillinger · sluttodds · live · oppgjør · ny analyse ved tap · rapport     │
                   │                                                                               │
Telegram  ◄───────►│ bot.py: kommandoer, knapper, roller (eier/admin/leser), utsending fra outbox  │
                   └───────────────────────────────────────────────────────────────────────────────┘
```

| Modul | Ansvar |
|---|---|
| `providers/apifootball.py` | Kamper, historikk, odds fra flere bookmakere, fravær, oppstillinger, livedata |
| `providers/norsktipping.py` | NT-priser: manuelt kontrollert (`/ntodds`) eller tredjepart (eksperimentell) |
| `providers/demo.py` | Fiktive data for demo og tester. Alt merkes «DEMO – EKSEMPELDATA» |
| `model.py` | Tidsvektet Poisson / Dixon-Coles, oppgjørsfordeling inkl. push/kvartlinjer |
| `analysis.py` | Marginfri markedskonsensus, krymping av modellen, usikkerhet, EV, minste odds og begrunnelser |
| `coupons.py` | Bonger per oddsbånd fra kvalifiserte enkeltspill, korrelasjonsregler, overlapp |
| `engine.py` | Planlegging, kontroll før publisering, overvåking, oppgjør, korreksjoner, ny analyse, driftsavvik |
| `markets.py` | Markeder, norske navn, oppgjørsregler, live-tilstand |
| `render.py` | Alle norske Telegram-tekster |
| `stats.py` / `backtest.py` | Åpen historikk, simulert yield, største fall, CLV / tidsbasert modelltest |

Robusthet er bygget inn slik:

- `tick()` leser all tilstand fra databasen og har ingen tilstand i minnet. En omstart fortsetter derfor der den slapp.
- Hver planlagt hendelse har en unik nøkkel (`kv_claim`, `outbox.dedupe_key`). Det hindrer dobbel analyse og duplikatmeldinger, også etter omstart.
- Meldinger går gjennom en utsendingskø. Den respekterer stilleperioder, gjør nye forsøk ved feil og deler opp lange meldinger.

## Kom i gang (demo uten nøkler)

```bash
cd kampanalyse
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
python -m pytest            # 58 tester
python -m kampanalyse demo  # simulerer en hel dag med FIKTIVE data og skriver alle meldinger
```

`demo` kjører hele dagsløpet med en simulert klokke. Det omfatter analyse 06:15, kontroll og
brief 08:00, bonger, oppstillinger, avspark, oppgjør, tapte bonger, ny analyse og
dagsrapport. Et eksempel ligger i [docs/eksempel-demo.txt](docs/eksempel-demo.txt). Lagene,
ligaen og prisene i demoen er oppdiktet.

Du kan også kjøre selve Telegram-boten med `DATA_PROVIDER=demo` for å teste menyer og knapper.
Alle meldinger merkes da tydelig som demo.

## Produksjonsoppsett

1. **Lag boten.** Bruk `/newbot` hos @BotFather. Foreslått navn: *Kampanalysen*, brukernavn f.eks. `kampanalysen_bot`.
   Ta vare på tokenet. Lim det aldri inn i kode, chat eller git.
2. **Finn din Telegram-ID**, f.eks. via @userinfobot.
3. **Skaff en API-Football-nøkkel** (api-sports.io, Pro-plan). Se [kostnader](#kostnader-og-tilganger).
4. **Lei en liten Linux-server** (VPS) og installer Docker.
5. **Konfigurer hemmeligheter på serveren:**
   ```bash
   git clone <repo> && cd kampanalyse
   cp .env.example .env && chmod 600 .env
   nano .env   # TELEGRAM_BOT_TOKEN, OWNER_TELEGRAM_ID, DATA_PROVIDER=apifootball, APIFOOTBALL_KEY
   ```
6. **Kontroller tilgangene før start:** `docker compose run --rm kampanalyse python -m kampanalyse selftest`.
   Den viser om kamper, odds og Telegram faktisk svarer.
7. **Start:** `docker compose up -d --build`. Følg loggen med `docker compose logs -f`.
8. Send `/start` og deretter `/help` til boten. Veiledningen festes i chatten.
9. **NT-priser:** Kontroller prisene i Oddsen og legg dem inn med `/ntodds <spill-ID> <odds>`.
   En bong får status *kontrollert* først når alle leddene er kontrollert. Hver kontroll gir en ny versjon av bongen.

Alternativ uten Docker: `deploy/kampanalyse.service` (systemd med `Restart=always`).
Drift, sikkerhetskopi og feilsøking er beskrevet i [docs/DRIFT.md](docs/DRIFT.md).

## Telegram-design og kommandoer

**Navn:** Kampanalysen
**Kort beskrivelse:** «Nøktern fotballanalyse og spillforslag tilpasset Norsk Tipping. Ingen garantier.»
**Beskrivelse:** settes automatisk ved oppstart (`render.BOT_DESCRIPTION`).
**Velkomst** (`/start`) med hovedmeny. **Festet brukerveiledning** (`/help`).

Uttrykket er bygget på noen faste prinsipper:

- Konklusjonen står først og er kort. Utdyping ligger bak knappene *Full analyse*, *Kilder*, *Kampstatus* og *Andre bonger*.
- Det er få emojier, og hver har en fast betydning: 🌅 brief, 📋 oppstilling, 🔄 endring, ⚽ kamp, ❌ tapt, 🔎 ny analyse, 🧾 nytt forslag, 📊 rapport, ⚙️ drift.
- Det finnes ingen brede tabeller. Hvert ledd vises som korte linjer som fungerer på mobil.
- Hver bong viser ID, versjon, status (foreløpig / kontrollert / startet / avgjort), publiseringstid, kontrolltid for odds, ledd, totalodds med verifiseringsstatus, risiko, overlapp og forbehold.
- Ordene «banker», «gratis penger», «sikker gevinst» og «garantert» er forbudt. En test kontrollerer alle genererte meldinger.

| Kommando | Funksjon | Rolle |
|---|---|---|
| `/today` `/morning` `/singles` `/coupons` | Oversikt, siste brief, enkeltspill, bonger | leser |
| `/odds20` `/odds50` `/odds100` | Bonger rundt nivået (bånd C–D, D–E, F–G) | leser |
| `/active` `/status` `/updates` `/results` `/stats` | Aktive bonger, kampstatus, endringer, resultater, historikk | leser |
| `/settings` `/notifications` `/pause` `/resume` | Brieftid, stilleperiode, kategorier, ligaer, varslingsnivå | leser |
| `/budget` `/placed <ID> <innsats> [odds]` | Underholdningsbudsjett og egne spill (privat) | leser |
| `/refresh` `/ntodds <ID> <odds>` `/health` | Ny priskontroll, legg inn kontrollert NT-pris, driftsstatus | admin |
| `/adduser <id> reader\|admin` `/removeuser` `/users` | Medlemmer (aldri automatisk) | eier |

Varslingsnivåer:

- **Minimal:** brief, bonger, tap og gevinst, ny analyse, rapport.
- **Normal:** i tillegg oppstillinger, vesentlige endringer, avspark, røde kort og VAR.
- **Detaljert:** i tillegg alle mål og gule kort.

## Kostnader og tilganger

Prisene er veiledende per oktober 2026 og må kontrolleres hos leverandøren.

| Post | Pris | Merknad |
|---|---|---|
| VPS (1–2 vCPU, 2 GB RAM) | ca. 50–100 kr/mnd | F.eks. Hetzner, DigitalOcean, UpCloud |
| API-Football Pro | ca. 19 USD/mnd (≈ 200 kr) | 7 500 kall/døgn. Boten bruker anslagsvis 500–1 000 per døgn. Gratisplanen (100/døgn) holder bare til testing, ikke til live-overvåking. |
| Telegram Bot API | gratis | |
| odds-api.io (valgfri NT-tredjepart) | ukjent | Ikke kontrollert. Prisene merkes som tredjepart. |
| **Sum** | **ca. 250–300 kr/mnd** | |

Disse tilgangene trengs: Telegram-bottoken, din Telegram-ID, en API-Football-nøkkel og SSH til en server.

**Norsk Tipping har ingen offentlig odds-API.** Boten skraper ikke og omgår ingen innlogging.
NT-priser kommer derfor fra én av to kilder:

- **Primært:** Du kontrollerer prisen i Oddsen og legger den inn med `/ntodds`.
- **Valgfritt:** En tredjepartsleverandør. Disse prisene merkes «NT via tredjepart – kontroller i Oddsen».

Uten NT-pris vises medianen av referansebookmakere. Forslaget merkes da
«Ikke verifisert hos Norsk Tipping», og det står at det ikke er klart til innlevering.

## Hva virker og hva gjenstår

**Virker og er testet (58 automatiske tester og en fullstendig dagssimulering med fiktive data):**

- Analyseflyten: kartlegging av kamper, filtrering på datakvalitet, marginfri markedskonsensus (power-metoden), modell, krymping, usikkerhet, EV, minste odds og begrunnelser for og mot fra faktiske data.
- Enkeltspill i tre kategorier (høy treffmulighet, god pris, høy odds) og bonger i båndene B–G. Hver bong har maks ett ledd per kamp, bruker aldri fyll-ledd og viser «Ingen kvalifisert bong» når grunnlaget mangler.
- Prisene kontrolleres på nytt før publisering. Ledd under minste akseptable odds trekkes, og bonger med trukne ledd publiseres ikke.
- Morgenbrief kl. 08:00 Oslo-tid, testet over begge sommertidsovergangene, med egen brieftid per bruker.
- Oppstillingsvarsel med avvik mot fraværslisten, overvåking av mål, kort og VAR, utsatte og avbrutte kamper og 1. omgang.
- Oppgjør skjer først etter et bekreftelsesvindu, og korrigerte resultater håndteres. Kampvinner merkes aldri tapt underveis.
- Tapte bonger varsles samlet per kamp, med maks én ekstra analyse-runde per dag. Ekstrarunden kan ikke ha høyere oddsbånd eller flere ledd, og gjenbruker ikke ledd fra aktive bonger.
- Duplikatbeskyttelse, omstart som fortsetter aktive bonger, varsel ved avbrudd i livedata og ærlig varsel når dataene er tilbake.
- Roller og tilgangskontroll på kommandoer og knapper. Alle knapper er testet.
- Innstillinger, stilleperioder, pause og varslingsnivåer.
- Budsjett, daglig eksponeringsgrense (gjelder også etter tap), overlappvarsel og private spill per bruker.
- `/ntodds` med versjonering. Gamle versjoner beholdes.
- Åpen historikk: treff, simulert yield, største fall, per marked og oddskategori, CLV mot sluttodds. Simulering holdes atskilt fra egne spill.
- Backtest-motor: tidsbasert, uten lekkasje, med kalibrering og markedsreferanse.

**Ikke verifisert i dette miljøet, fordi nettverket blokkerte alle eksterne API-er:**

- API-Football-integrasjonen er skrevet etter det dokumenterte v3-formatet og testet mot simulerte HTTP-svar, ikke mot det ekte API-et. Kjør `selftest` ved første oppstart.
- Telegram-tilkoblingen. Kommandoer og knapper er testet med simulerte oppdateringer, men ingen melding er sendt til ekte Telegram.
- odds-api.io-adapteren (eksperimentell; feltnavnene er tolket defensivt).
- Docker-bygget. Docker Hub avviste nedlastingen (429). Pakkingen er verifisert med `pip install` i et rent miljø.
- Boten kjører ikke noe sted ennå. Kontinuerlig drift krever at du setter den opp på en server (steg 4–7 over).

**Gjenstår eller er bevisst avgrenset:**

- **Modellen er uvalidert.** Kjør `python -m kampanalyse backtest <csv-filer>` på flere sesonger fra football-data.co.uk. Øk `MODEL_WEIGHT` bare hvis modellen slår markedsreferansen på log loss og er godt kalibrert. Til da merkes alle estimater som usikre.
- **Taktikk, xG og spillerbetydning** inngår ikke i estimatet:
  - Taktiske data (press, formasjonsmatchup) finnes ikke i kilden.
  - xG brukes bare når historikken har det. API-Footballs fixture-liste har det ikke; det krever ekstra kall per kamp.
  - Fravær vises og varsles, men tallfestes ikke.
- **Kort og hjørnespark** er av som standard (`ENABLE_CARDS`), fordi dommer- og lagprofiler mangler. Spillerspill er ikke implementert.
- **Livespill** er av og ikke implementert, i tråd med kravet om at det skal være deaktivert som standard.
- **Kanal og flere medlemmer:** Arkitekturen er klar med roller, private spill og `PUBLISH_CHANNEL_ID`. Ingenting publiseres før du selv setter dette.
- **Norsk Tippings oppgjørsregler og kombinasjonsbegrensninger** er ikke hentet automatisk. Bransjestandard brukes og forklares, og det står alltid at NTs regler gjelder.
