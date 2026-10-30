# Del 4 – Programmering for DevOps

**Læringsmål for kapitlet.** Når du er ferdig, skal du kunne:

- forklare hva programmering er og hvordan kode blir kjørt,
- skrive Python-programmer med variabler, datatyper, betingelser, løkker og funksjoner,
- jobbe med lister, ordbøker, JSON og YAML,
- gjøre API-kall, håndtere feil og logge på en profesjonell måte,
- skrive automatiseringsskript i Python og Bash,
- forstå hvordan Python brukes mot Azure.

## Hva er programmering egentlig?

**Hva er det?** Programmering er å skrive **presise instruksjoner** som en datamaskin kan følge. Datamaskinen er ekstremt rask, men helt uten sunn fornuft: den gjør *nøyaktig* det du skriver – ikke det du mente.

> **Hverdagsanalogi:** En oppskrift for en robotkokk. «Stek til den er gyllen» fungerer for et menneske. Roboten trenger: «Sett platen på nivå 6. Vent 180 sekunder. Snu. Vent 120 sekunder.» Programmering er å skrive oppskrifter for roboter.

**Hvordan blir kode kjørt?**

- **Kompilerte språk** (C, Go, Rust, Java/C# i en variant) oversettes først til maskinkode eller bytekode. Det gir rask kjøring.
- **Tolkede språk** (Python, Bash, JavaScript) leses og kjøres av en *tolk* (*interpreter*) linje for linje. Det gir raskere utvikling og enkel testing.

**Hvorfor må en DevOps Engineer programmere?** Du skal ikke nødvendigvis bygge store applikasjoner, men du skal:

- automatisere repeterende oppgaver (opprydding, rapporter, deploys),
- lese og forstå koden til utviklerne du jobber med,
- skrive pipelines, infrastrukturkode og konfigurasjon (YAML, HCL, Bicep),
- bruke API-er for Azure, GitHub, Slack osv.,
- feilsøke applikasjoner i produksjon.

**Hvilke språk?** Start med **Python** (lettlest, enormt mange biblioteker, brukes overalt i DevOps, sky og AI) og **Bash** (for Linux-automatisering). Senere kan **Go** være nyttig (Docker, Kubernetes og Terraform er skrevet i Go), og **PowerShell** er nyttig i Windows-tunge miljøer.

## Python fra bunnen

### Installasjon og første program

Sjekk om Python er installert:

```bash
$ python3 --version
Python 3.12.3
```

(Versjonen din kan være en annen. Bruk Python 3.10 eller nyere for eksemplene i boken.) På Windows kan du installere fra python.org eller Microsoft Store; på Ubuntu: `sudo apt install python3 python3-pip python3-venv`.

Lag filen `hei.py`:

```python
print("Hei, verden!")
```

```bash
$ python3 hei.py
Hei, verden!
```

`print()` er en **funksjon** som skriver ut det du gir den. Teksten i anførselstegn er en **streng** (*string*).

**Bruk en god editor.** Visual Studio Code (gratis) med Python-utvidelsen gir fargekoding, feilmarkering og feilsøking.

**Det interaktive skallet.** Skriv bare `python3` for å teste kode linje for linje. Avslutt med `exit()`.

### Virtuelle miljøer

**Hva er det?** Et virtuelt miljø (*virtual environment*) er en egen, isolert mappe med Python-pakker for ett prosjekt.

**Hvorfor?** Prosjekt A trenger kanskje `requests` versjon 2.28, prosjekt B en annen. Uten isolasjon krasjer de.

```bash
$ python3 -m venv .venv            # lag miljøet i mappen .venv
$ source .venv/bin/activate        # aktiver (Windows: .venv\Scripts\activate)
(.venv) $ pip install requests     # installer pakker inn i miljøet
(.venv) $ pip freeze > requirements.txt   # lagre listen over pakker
(.venv) $ deactivate               # gå ut av miljøet
```

En annen person (eller en CI-pipeline) gjenskaper miljøet med `pip install -r requirements.txt`.

> **Vanlig feil:** Å sjekke inn `.venv`-mappen i Git. Legg den i `.gitignore`; sjekk heller inn `requirements.txt`.

### Variabler

**Hva er det?** En variabel er et **navn** som peker på en **verdi**. Som en merkelapp på en eske.

```python
servernavn = "web-01"      # en tekst (str)
antall_cpu = 4             # et heltall (int)
cpu_last = 72.5            # et desimaltall (float)
er_aktiv = True            # en sannhetsverdi (bool): True eller False

print(servernavn)                          # web-01
print(f"{servernavn} har {antall_cpu} CPU-er")  # f-streng: setter inn verdier
```

Linje for linje:

- `servernavn = "web-01"` – lag navnet `servernavn` og la det peke på teksten `"web-01"`. `=` betyr «tilordne», ikke «er lik».
- `f"..."` – en **f-streng**. Alt inni `{ }` byttes ut med verdien.

**Navneregler:** små bokstaver og understrek (`antall_cpu`), ikke start med tall, ingen mellomrom, ikke æøå (det virker, men er uvanlig i kode). Velg beskrivende navn: `antall_feil` er bedre enn `x`.

### Datatyper

| Type | Eksempel | Brukes til |
|---|---|---|
| `str` | `"nginx"` | Tekst |
| `int` | `443` | Heltall |
| `float` | `99.9` | Desimaltall |
| `bool` | `True` | Ja/nei |
| `list` | `["web-01", "web-02"]` | Ordnet samling |
| `dict` | `{"navn": "web-01", "cpu": 4}` | Nøkkel → verdi |
| `None` | `None` | «Ingen verdi» |

```python
port = "8080"            # dette er TEKST, ikke et tall
print(port + 1)          # TypeError! Kan ikke legge tall til tekst
print(int(port) + 1)     # 8081 – int() konverterer tekst til tall
print(type(port))        # <class 'str'>
```

> **Vanlig feil:** Verdier fra miljøvariabler, filer og brukerinput er **alltid tekst**. Konverter dem med `int()` eller `float()` før du regner med dem.

**Strengoperasjoner du ofte trenger:**

```python
linje = "  ERROR: Disk full on /dev/sda1  "
print(linje.strip())               # fjern mellomrom i endene
print(linje.lower())               # små bokstaver
print("ERROR" in linje)            # True – inneholder teksten "ERROR"?
print(linje.strip().split(":"))    # ['ERROR', ' Disk full on /dev/sda1']
print("web-01".replace("01", "02"))  # web-02
```

### Betingelser (*conditions*)

**Hva er det?** Kode som bare kjøres hvis noe er sant.

```python
cpu_last = 91

if cpu_last > 90:                       # hvis lasten er over 90
    print("KRITISK: skaler opp!")       # innrykk (4 mellomrom) = denne blokken hører til if
elif cpu_last > 70:                     # ellers, hvis over 70
    print("ADVARSEL: høy last")
else:                                   # i alle andre tilfeller
    print("OK")
```

> **Husk:** I Python er **innrykk** (*indentation*) en del av språket. Linjene som hører til `if`, må ha samme innrykk. Bruk 4 mellomrom.

Sammenligninger: `==` (lik), `!=` (ulik), `<`, `>`, `<=`, `>=`. Kombiner med `and`, `or`, `not`:

```python
miljø = "prod"
er_godkjent = False
if miljø == "prod" and not er_godkjent:
    print("Stopp! Deploy til produksjon krever godkjenning.")
```

### Løkker (*loops*)

**`for`-løkke** – gjør noe for hvert element i en samling:

```python
servere = ["web-01", "web-02", "db-01"]

for server in servere:                  # server får hver verdi etter tur
    print(f"Sjekker {server} ...")

for i in range(3):                      # range(3) gir 0, 1, 2
    print(f"Forsøk nummer {i + 1}")
```

**`while`-løkke** – gjenta så lenge noe er sant:

```python
import time

forsøk = 0
while forsøk < 5:
    forsøk += 1                          # samme som forsøk = forsøk + 1
    print(f"Prøver å koble til (forsøk {forsøk}) ...")
    time.sleep(1)                        # vent ett sekund
```

`break` avslutter løkken, `continue` hopper til neste runde.

> **Vanlig feil:** En `while`-løkke som aldri blir usann, kjører for alltid. Avbryt med `Ctrl + C`.

### Funksjoner

**Hva er det?** En navngitt kodeblokk du kan gjenbruke. Den tar imot **parametere** og kan gi tilbake (**returnere**) en verdi.

**Hvorfor?** Unngå å skrive samme kode flere ganger, gjøre koden lesbar, og gjøre det mulig å teste deler hver for seg.

```python
def status_for_last(cpu_prosent: float, grense: float = 80.0) -> str:
    """Returnerer en status basert på CPU-last.

    cpu_prosent: målt last i prosent
    grense: når vi regner lasten som høy (standard 80)
    """
    if cpu_prosent >= grense:
        return "HØY"
    return "NORMAL"

print(status_for_last(95))              # HØY
print(status_for_last(60))              # NORMAL
print(status_for_last(60, grense=50))   # HØY
```

Forklaring:

- `def` – definerer en funksjon.
- `cpu_prosent: float` – parameter med **typehint** (forteller leseren og verktøy hvilken type som forventes; Python håndhever det ikke).
- `grense: float = 80.0` – parameter med **standardverdi**.
- `-> str` – funksjonen returnerer en streng.
- `"""..."""` – **docstring**: dokumentasjon av funksjonen.
- `return` – gir verdien tilbake og avslutter funksjonen.

### Lister og ordbøker

**Lister** (*lists*) er ordnede samlinger:

```python
porter = [22, 80, 443]
porter.append(8080)          # legg til på slutten → [22, 80, 443, 8080]
print(porter[0])             # 22 – første element har indeks 0!
print(porter[-1])            # 8080 – siste element
print(len(porter))           # 4
porter.remove(22)            # fjern verdien 22
print(80 in porter)          # True

# List comprehension: lag en ny liste i én linje
høye = [p for p in porter if p > 100]   # [443, 8080]
```

**Ordbøker** (*dictionaries, dict*) lagrer **nøkkel → verdi**:

```python
vm = {
    "navn": "web-01",
    "region": "norwayeast",
    "størrelse": "Standard_B2s",
    "tags": {"miljø": "test", "eier": "student"},
}

print(vm["navn"])                    # web-01
print(vm["tags"]["miljø"])           # test – ordbok inni ordbok
vm["status"] = "running"             # legg til / endre en nøkkel
print(vm.get("ip", "ingen IP"))      # .get() gir standardverdi hvis nøkkelen mangler

for nøkkel, verdi in vm.items():     # gå gjennom alle par
    print(f"{nøkkel}: {verdi}")
```

> **Vanlig feil:** `vm["ip"]` gir `KeyError` hvis nøkkelen ikke finnes. Bruk `vm.get("ip")` når nøkkelen kan mangle.

> **Husk:** Lister og ordbøker er de viktigste datastrukturene i DevOps-skripting, fordi JSON (fra API-er) blir nettopp lister og ordbøker i Python.

### Moduler og biblioteker

Python har et stort **standardbibliotek**, og du kan installere mer med `pip`:

```python
import os                    # operativsystemet: miljøvariabler, filer
import sys                   # argumenter, avslutning
import json                  # JSON
import subprocess            # kjøre andre programmer
from pathlib import Path     # moderne filstier
from datetime import datetime

print(os.environ.get("HOME"))              # les miljøvariabel
print(Path("/var/log").exists())           # finnes mappen?
print(datetime.now().isoformat())          # nåtid, f.eks. 2026-10-30T10:15:00
```

### Lese og skrive filer

```python
from pathlib import Path

# Skriv til fil. "with" sørger for at filen lukkes automatisk.
with open("servere.txt", "w", encoding="utf-8") as f:
    f.write("web-01\nweb-02\ndb-01\n")

# Les linje for linje
with open("servere.txt", encoding="utf-8") as f:
    for linje in f:
        print(linje.strip())

# Kortversjon med pathlib
innhold = Path("servere.txt").read_text(encoding="utf-8")
```

## JSON og YAML

Dette er de to dataformatene du kommer til å se *hele tiden* i DevOps.

### JSON

**Hva er det?** JSON (*JavaScript Object Notation*) er et tekstformat for data. Nesten alle API-er bruker det.

```json
{
  "navn": "web-01",
  "cpu": 4,
  "aktiv": true,
  "porter": [80, 443],
  "tags": { "miljø": "prod" }
}
```

Regler: nøkler i **doble** anførselstegn, ingen komma etter siste element, ingen kommentarer.

```python
import json

tekst = '{"navn": "web-01", "porter": [80, 443]}'
data = json.loads(tekst)               # JSON-tekst → Python-dict
print(data["porter"][1])               # 443

data["porter"].append(8080)
print(json.dumps(data, indent=2))      # Python → pen JSON-tekst

with open("vm.json", "w") as f:        # skriv til fil
    json.dump(data, f, indent=2)
with open("vm.json") as f:             # les fra fil
    data = json.load(f)
```

**På kommandolinjen** er `jq` gull verdt:

```bash
$ curl -s https://api.github.com/repos/kubernetes/kubernetes | jq '.stargazers_count'
$ az vm list | jq '.[].name'                      # navnet på alle VM-er
```

(Azure CLI har også sitt eget spørrespråk: `az vm list --query "[].name" -o tsv`.)

### YAML

**Hva er det?** YAML (*YAML Ain't Markup Language*) er et mer menneskevennlig dataformat. Det brukes i Kubernetes, GitHub Actions, Azure Pipelines, Docker Compose og Ansible.

```yaml
# Dette er en kommentar – YAML tillater kommentarer
navn: web-01            # nøkkel: verdi
cpu: 4
aktiv: true
porter:                 # en liste
  - 80
  - 443
tags:                   # en ordbok (innrykk med mellomrom!)
  miljø: prod
  eier: devops-team
beskrivelse: |          # | = flerlinjers tekst, linjeskift beholdes
  Webserver for
  nettbutikken.
```

Samme data i JSON og YAML:

```text
 JSON                                 YAML
 {"porter": [80, 443],                porter:
  "tags": {"miljø": "prod"}}            - 80
                                        - 443
                                      tags:
                                        miljø: prod
```

> **Vanlig feil:** YAML bruker **mellomrom, aldri tab**, og innrykket bestemmer strukturen. Ett mellomrom feil = feil struktur eller ugyldig fil. Bruk en editor med YAML-støtte og et verktøy som `yamllint`.

> **Vanlig feil:** YAML gjetter typer. `versjon: 1.10` blir tallet 1.1. `land: NO` kan i eldre YAML-tolkere bli `false`. Sett tekst i anførselstegn når du er i tvil: `versjon: "1.10"`.

```python
import yaml          # pip install pyyaml

with open("config.yaml") as f:
    config = yaml.safe_load(f)        # safe_load: aldri yaml.load på ukjente filer
print(config["tags"]["miljø"])
```

## API-kall med Python

Biblioteket `requests` (`pip install requests`) gjør HTTP enkelt.

```python
import requests

url = "https://api.github.com/repos/python/cpython"
svar = requests.get(url, timeout=10)      # ALLTID timeout – ellers kan skriptet henge for alltid

print(svar.status_code)                   # 200
svar.raise_for_status()                   # kaster unntak hvis 4xx/5xx
data = svar.json()                        # JSON → dict
print(f"{data['full_name']} har {data['stargazers_count']} stjerner")
```

**Med autentisering og POST:**

```python
import os
import requests

token = os.environ["GITHUB_TOKEN"]        # hemmelighet fra miljøet, ALDRI i koden
headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github+json",
}
body = {"title": "Disk nesten full på web-01", "body": "Automatisk opprettet av overvåkingsskript."}

svar = requests.post(
    "https://api.github.com/repos/MITT-BRUKERNAVN/MITT-REPO/issues",
    headers=headers, json=body, timeout=10,
)
print(svar.status_code)                   # 201 = opprettet
```

> **Vanlig feil:** Å lime inn tokens og passord direkte i koden og pushe til GitHub. Roboter skanner GitHub etter nøkler kontinuerlig, og en lekket nøkkel kan misbrukes innen minutter. GitHub har *secret scanning* som kan stoppe noen av disse, men ikke stol på det. Bruk miljøvariabler eller et hemmelighetshvelv.

## Feilhåndtering (*error handling*)

**Hva er det?** Når noe går galt, kaster Python et **unntak** (*exception*). Uten håndtering krasjer programmet. Med `try`/`except` kan du reagere kontrollert.

```python
import requests

def hent_status(url: str) -> int | None:
    """Returner HTTP-statuskode for url, eller None hvis den ikke kan nås."""
    try:
        svar = requests.get(url, timeout=5)
        return svar.status_code
    except requests.exceptions.Timeout:
        print(f"Tidsavbrudd mot {url}")
    except requests.exceptions.ConnectionError:
        print(f"Kan ikke koble til {url}")
    return None

print(hent_status("https://www.example.com"))
```

- `try:` – prøv denne koden.
- `except Type:` – hvis *denne typen* feil skjer, gjør dette.
- `finally:` – (valgfri) kjøres uansett, f.eks. for opprydding.
- `raise` – kast et unntak selv.

**Gjentatte forsøk med ventetid** (*retry with backoff*) er et viktig mønster i skyen, fordi nettverk og API-er av og til feiler midlertidig:

```python
import time
import requests

def get_med_retry(url: str, forsøk: int = 4) -> requests.Response:
    for n in range(forsøk):
        try:
            svar = requests.get(url, timeout=5)
            if svar.status_code < 500:        # 5xx kan være midlertidig; 4xx er det ikke
                return svar
        except requests.exceptions.RequestException as e:
            print(f"Feil: {e}")
        vent = 2 ** n                          # 1, 2, 4, 8 sekunder (eksponentiell backoff)
        print(f"Prøver igjen om {vent} s ...")
        time.sleep(vent)
    raise RuntimeError(f"Ga opp etter {forsøk} forsøk mot {url}")
```

> **Vanlig feil:** `except:` uten type, eller `except Exception: pass`. Da svelges *alle* feil, også de du burde visst om. Fang de feilene du forventer, og logg resten.

## Logging

**Hvorfor ikke bare `print`?** I produksjon trenger du tidsstempel, alvorlighetsgrad, og muligheten til å skru detaljnivået opp og ned uten å endre koden.

```python
import logging

logging.basicConfig(
    level=logging.INFO,                                       # vis INFO og alvorligere
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("diskmonitor")

log.debug("Detaljer for feilsøking")         # vises ikke på INFO-nivå
log.info("Starter sjekk av disker")
log.warning("Disk / er 85 % full")
log.error("Klarte ikke lese /mnt/data")
```

```text
2026-10-30 10:20:01,123 INFO diskmonitor: Starter sjekk av disker
2026-10-30 10:20:01,130 WARNING diskmonitor: Disk / er 85 % full
2026-10-30 10:20:01,131 ERROR diskmonitor: Klarte ikke lese /mnt/data
```

| Nivå | Bruk |
|---|---|
| DEBUG | Detaljer for utviklere ved feilsøking |
| INFO | Normale hendelser («startet», «ferdig») |
| WARNING | Noe uventet, men programmet fortsetter |
| ERROR | En operasjon feilet |
| CRITICAL | Programmet kan ikke fortsette |

> **Fra arbeidslivet:** I skyen logger man ofte i **JSON-format** (*strukturert logging*) til `stdout`. Plattformen (Kubernetes, App Service, Azure Monitor) samler loggene, og du kan søke på felt som `level`, `user_id` eller `request_id`. Logg aldri passord, tokens eller personopplysninger.

## Kommandolinjeargumenter

Profesjonelle skript tar imot argumenter i stedet for hardkodede verdier. `argparse` er innebygd:

```python
import argparse

parser = argparse.ArgumentParser(description="Sjekk om nettsider svarer.")
parser.add_argument("urler", nargs="+", help="En eller flere URL-er")
parser.add_argument("--timeout", type=int, default=5, help="Sekunder før tidsavbrudd")
args = parser.parse_args()

print(args.urler, args.timeout)
```

```bash
$ python3 sjekk.py https://example.com https://noroff.no --timeout 3
$ python3 sjekk.py --help       # gratis hjelpetekst!
```

## Kjøre andre programmer fra Python

```python
import subprocess

resultat = subprocess.run(
    ["df", "-h", "/"],          # kommando som liste – trygt mot injeksjon
    capture_output=True,        # fang utskriften
    text=True,                  # som tekst, ikke bytes
    check=True,                 # kast unntak hvis kommandoen feiler
)
print(resultat.stdout)
```

> **Vanlig feil:** `subprocess.run(f"rm -rf {mappe}", shell=True)` med data fra brukeren. Det åpner for *command injection*. Bruk liste-formen og unngå `shell=True`.

## Bash eller Python?

| Bruk Bash når … | Bruk Python når … |
|---|---|
| Du limer sammen Linux-kommandoer | Du har logikk, datastrukturer, mange betingelser |
| Skriptet er kort (under ~50 linjer) | Du jobber med JSON/API-er |
| Du installerer pakker, kopierer filer | Du trenger god feilhåndtering og tester |
| Det skal kjøre i en minimal container | Skriptet skal vedlikeholdes over tid |

Bash ble grundig gjennomgått i kapittel 3. Her er et lite Bash-skript som bruker et API, for sammenligning:

```bash
#!/usr/bin/env bash
set -euo pipefail
# helsesjekk.sh – sjekker at URL-er svarer 200
for url in "$@"; do
  kode=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$url" || echo "000")
  if [[ "$kode" == "200" ]]; then
    echo "OK   $url"
  else
    echo "FEIL $url ($kode)" >&2
  fi
done
```

`-s` stille, `-o /dev/null` kast innholdet, `-w "%{http_code}"` skriv bare statuskoden.

## Python for Cloud: Azure SDK

Microsoft har offisielle Python-biblioteker for Azure. Autentisering skjer typisk med `DefaultAzureCredential`, som automatisk prøver flere metoder: miljøvariabler, managed identity (i Azure), og din Azure CLI-innlogging (lokalt).

```bash
$ pip install azure-identity azure-mgmt-resource
$ az login        # logg inn lokalt, så kan DefaultAzureCredential bruke CLI-innloggingen
```

```python
import os
from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient

subscription_id = os.environ["AZURE_SUBSCRIPTION_ID"]   # sett med: export AZURE_SUBSCRIPTION_ID=...
credential = DefaultAzureCredential()                   # finner innlogging automatisk
client = ResourceManagementClient(credential, subscription_id)

# List alle ressursgrupper med region og tags
for rg in client.resource_groups.list():
    print(f"{rg.name:30} {rg.location:15} {rg.tags}")
```

> **Fra arbeidslivet:** Et klassisk skript er en «kostnadsjeger» som finner ressursgrupper uten `eier`-tag eller med `utløper`-dato i fortiden, og varsler eller sletter dem. Det bygger du i prosjekt 2.

## Prosjektskript: helsesjekk med rapport

Her er et komplett, profesjonelt lite verktøy som samler mye av kapitlet.

```python
#!/usr/bin/env python3
"""uptime_check.py – sjekker en liste nettsider og skriver en JSON-rapport.

Bruk:
    python3 uptime_check.py sites.yaml --out rapport.json
"""
import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone

import requests
import yaml

log = logging.getLogger("uptime")


def sjekk(url: str, timeout: int) -> dict:
    """Sjekk én URL og returner resultatet som en ordbok."""
    start = time.perf_counter()                       # start stoppeklokke
    try:
        svar = requests.get(url, timeout=timeout)
        ms = round((time.perf_counter() - start) * 1000)
        ok = svar.status_code < 400
        return {"url": url, "status": svar.status_code, "ms": ms, "ok": ok}
    except requests.exceptions.RequestException as e:
        return {"url": url, "status": None, "ms": None, "ok": False, "feil": type(e).__name__}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", help="YAML-fil med liste over nettsider")
    parser.add_argument("--out", default="rapport.json")
    parser.add_argument("--timeout", type=int, default=5)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    with open(args.config, encoding="utf-8") as f:
        urler = yaml.safe_load(f)["sites"]            # forventer: sites: [url1, url2, ...]

    resultater = []
    for url in urler:
        r = sjekk(url, args.timeout)
        nivå = logging.INFO if r["ok"] else logging.ERROR
        log.log(nivå, "%s → %s (%s ms)", url, r["status"], r["ms"])
        resultater.append(r)

    rapport = {
        "tidspunkt": datetime.now(timezone.utc).isoformat(),
        "antall_ok": sum(r["ok"] for r in resultater),   # True teller som 1
        "antall_feil": sum(not r["ok"] for r in resultater),
        "resultater": resultater,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(rapport, f, indent=2, ensure_ascii=False)

    return 0 if rapport["antall_feil"] == 0 else 1      # returkode 1 hvis noe feilet


if __name__ == "__main__":       # kjør main() bare når filen startes direkte
    sys.exit(main())
```

`sites.yaml`:

```yaml
sites:
  - https://www.example.com
  - https://www.noroff.no
  - https://finnes-ikke.example.invalid
```

Legg merke til profesjonelle detaljer: argumenter i stedet for hardkoding, timeout, feilhåndtering, logging, strukturert JSON-utdata og **returkode** som en CI-pipeline eller cron kan reagere på.

## Testing – en smakebit

Kode du ikke tester, vet du ikke om virker. `pytest` er standardverktøyet:

```python
# test_uptime.py
from uptime_check import sjekk

def test_ugyldig_url_gir_ok_false():
    r = sjekk("https://finnes-ikke.example.invalid", timeout=2)
    assert r["ok"] is False
```

```bash
$ pip install pytest
$ pytest -q
.                                                    [100%]
1 passed in 0.41s
```

I kapittel 12 kjører vi slike tester automatisk i en CI-pipeline ved hver endring.

## Kodekvalitet

- **Formatering:** `ruff format` eller `black` – alle får lik kodestil.
- **Linting:** `ruff check` (Python), `shellcheck` (Bash), `yamllint` (YAML) – finner feil og dårlig praksis.
- **Lesbarhet:** beskrivende navn, korte funksjoner, kommentarer som forklarer *hvorfor*, ikke *hva*.

## Kapitteloppsummering

- Programmering er presise instruksjoner. Python og Bash er de viktigste språkene for en DevOps-nybegynner.
- Python-grunnlag: variabler, datatyper, `if`/`elif`/`else`, `for`/`while`, funksjoner, lister, ordbøker.
- JSON (API-er) og YAML (konfigurasjon) blir lister og ordbøker i Python. YAML er følsomt for innrykk.
- Bruk `requests` med timeout for API-kall, `try`/`except` for feil, `logging` for logging, `argparse` for argumenter.
- Hemmeligheter skal aldri stå i koden.
- Returkoder lar skript samarbeide med cron og CI/CD.
- Azure SDK med `DefaultAzureCredential` lar Python styre Azure.

## Øvingsoppgaver

1. Skriv en funksjon `er_privat_ip(ip: str) -> bool` som sjekker om en IPv4-adresse er i et privat område. (Tips: modulen `ipaddress` har `ipaddress.ip_address(ip).is_private`.)
2. Les en fil `servere.txt` med ett servernavn per linje, og skriv ut navnene sortert alfabetisk uten duplikater.
3. Hent `https://api.github.com/users/<ditt-brukernavn>/repos` og skriv ut navnet og antall stjerner for hvert repo.
4. Konverter en JSON-fil til YAML med Python.
5. Utvid `uptime_check.py` slik at den også skriver en advarsel hvis responstiden er over 1000 ms.
6. Skriv en pytest-test for oppgave 1.

## Quiz

1. Hva er forskjellen på en liste og en ordbok?
2. Hva skriver `print(["a", "b", "c"][1])` ut?
3. Hvorfor gir `"5" + 5` en feil i Python?
4. Hva er galt med denne YAML-en?

    ```yaml
    tags:
    	miljø: prod
    ```

5. Hvorfor bør du alltid bruke `timeout` i `requests.get`?
6. Hva er forskjellen på `json.load` og `json.loads`?
7. Hvorfor er `except: pass` en dårlig idé?
8. Hva gjør `if __name__ == "__main__":`?
9. Hvorfor returnerer skriptet `1` når en nettside feiler?
10. Hvor skal et API-token ligge når skriptet kjører?

### Fasit

1. En **liste** er en ordnet samling elementer hentet med indeks (0, 1, 2 …). En **ordbok** lagrer par av nøkkel → verdi og hentes med nøkkelen.
2. `b` – indekser starter på 0.
3. Fordi `"5"` er tekst og `5` er et tall, og Python blander ikke typer automatisk. Bruk `int("5") + 5`.
4. Den bruker **tab** til innrykk. YAML tillater bare mellomrom.
5. Uten timeout kan skriptet vente for alltid hvis serveren aldri svarer, og f.eks. blokkere en pipeline eller cron-jobb.
6. `json.load` leser fra en **fil**; `json.loads` leser fra en **streng** (s = string).
7. Den skjuler alle feil, også alvorlige og uventede, slik at du ikke får vite at noe er galt.
8. Koden under kjøres bare når filen startes direkte, ikke når den importeres som modul (f.eks. fra en test).
9. Slik at det som kaller skriptet (cron, CI/CD, et annet skript) kan oppdage at noe gikk galt. 0 = suksess, alt annet = feil.
10. I en miljøvariabel eller et hemmelighetshvelv (f.eks. Azure Key Vault, GitHub Secrets) – aldri i koden eller i Git.
