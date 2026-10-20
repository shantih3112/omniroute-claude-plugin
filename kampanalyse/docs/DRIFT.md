# Drift

## Kontinuerlig drift mens du er offline

Boten kjører på serveren. Den trenger ikke at telefonen din er på, at du har Telegram åpent
eller at du svarer.

| Mekanisme | Hvordan |
|---|---|
| Planlagte jobber | `engine.tick()` hvert 30. sekund. Alle tider i Europe/Oslo via `zoneinfo` (sommertid håndteres). |
| Automatisk omstart | Docker `restart: unless-stopped` (+ valgfri autoheal ved feilet helsesjekk) eller systemd `Restart=always` |
| Helsesjekk | `python -m kampanalyse healthcheck`: OK hvis motoren har kjørt siste 3 min |
| Varig database | SQLite i WAL-modus på volumet `./data` |
| Gjenopptakelse | All tilstand ligger i databasen. Etter omstart fortsetter overvåking og oppgjør av aktive bonger. |
| Duplikatvern | Unike nøkler per jobb (`kv`) og per melding (`outbox.dedupe_key`) |
| Datakontroll | `health`-tabellen per kilde. Varsel hvis livedata er eldre enn 6 min mens kamper pågår. Ved gjenoppretting kommer en egen melding om at hendelser i perioden ikke ble fanget i sanntid. |
| Feilhåndtering | Hvert steg i `tick` er isolert. Feil gir ⚙️ Driftsavvik til eier og administrator, maks én per time per steg. |
| Hemmeligheter | Bare i `.env` på serveren (`chmod 600`). Aldri i git (`.gitignore`). |

Én kjent grense: Krasjer prosessen i millisekundene mellom at Telegram har mottatt en
melding og at databasen registrerer den som sendt, kan den ene meldingen komme to ganger
etter omstart.

## Vanlige oppgaver

```bash
docker compose logs -f --tail=200          # logg
docker compose restart                     # omstart
docker compose exec kampanalyse python -m kampanalyse selftest
cp data/kampanalyse.db backup-$(date +%F).db   # sikkerhetskopi (eller sqlite3 .backup)
git pull && docker compose up -d --build   # oppdatering
```

Sett gjerne opp daglig sikkerhetskopi av `data/` med cron på serveren.

## API-kvote

API-Football teller kall per døgn. Boten teller selv og stopper ved `APIFOOTBALL_DAILY_CAP`.

| Del av dagen | Anslått antall kall |
|---|---|
| Morgen | 1 + 2 per liga + 2 per kamp (≈ 100–150) |
| Kontroll før publisering | ≈ 20 |
| Oppstillinger | ≈ 2–4 per fulgt kamp |
| Live | 1 kall per minutt per 20 kamper mens kamper pågår (≈ 300–600) |

Det gir ca. 500–1 000 kall per døgn. Gratisplanen (100/døgn) holder ikke til overvåking.
Livedata hentes med fast intervall, så varsler kommer typisk 1–2 minutter etter hendelsen.

## Flere medlemmer og kanal

- Eier legger til med `/adduser <id> reader|admin`. Brukeren må selv sende `/start`.
- Lesere ser publiserte analyser. Egne spill (`/placed`) og budsjett er private per bruker.
- Felles publiserte tips har én historikk for alle. Tips slettes aldri, og endringer gir ny versjon eller en rad i `changes`.
- Privat kanal: sett `PUBLISH_CHANNEL_ID` og gjør boten til administrator i kanalen. Da publiseres brief, bonger, tap, ny analyse og rapport dit. Dette er av som standard.

## Feilsøking

| Symptom | Sjekk |
|---|---|
| Ingen morgenbrief | `/health`, loggen. Feilet analysen, får du en egen brief med beskjed om det, pluss driftsavvik. |
| «Ikke verifisert hos Norsk Tipping» overalt | Forventet uten NT-kilde. Bruk `/ntodds` etter kontroll i Oddsen. |
| Ingen bonger | Kan være riktig: ingen spill oppfylte kravene. Se «Datamangler» i briefen. |
| 401/403 fra API-Football | Nøkkel eller plan. Kjør `selftest`. |
