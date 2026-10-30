# Del 9 – Docker og containere

**Læringsmål for kapitlet.** Når du er ferdig, skal du kunne:

- forklare hva containere er, og hvordan de skiller seg fra virtuelle maskiner,
- forklare images, containere, lag (*layers*) og registre,
- skrive en god Dockerfile (inkludert multi-stage builds),
- kjøre flere containere sammen med Docker Compose,
- bruke volumes og Docker-nettverk,
- sikre og feilsøke containere,
- bygge, kjøre og publisere en komplett applikasjon.

## Hva er containere?

**Hva er det?** Tenk deg at du har laget en applikasjon på PC-en din. Den fungerer perfekt hos deg, men når en kollega prøver den, fungerer den ikke – fordi PC-en deres har en annen Python-versjon, mangler et bibliotek, eller har andre innstillinger. «It works on my machine!»

En **container** pakker applikasjonen **sammen med alt den trenger for å kjøre** – runtime (f.eks. Python), biblioteker, systemverktøy og konfigurasjon – i én standardisert enhet. Containeren kjører på samme måte på din laptop, kollegaens PC, i testmiljøet og i produksjon i Azure.

> **Hverdagsanalogi:** Skipscontaineren. Før 1950-tallet ble varer lastet løst på skip – sekker, tønner og kasser i alle former. Det var tregt, og ting ble ødelagt. Standardcontaineren endret alt: uansett hva som er inni, har den samme mål og festepunkter, og passer på alle skip, kraner, tog og lastebiler i verden. En Docker-container er det samme for programvare: uansett hva som er inni, kan den kjøres overalt der det finnes en container-runtime.

**Hvorfor finnes det?**

- **Konsistens** – samme pakke i alle miljøer.
- **Isolasjon** – apper med motstridende avhengigheter kan kjøre side om side.
- **Lettvekt og fart** – containere starter på sekunder (ofte under ett), og bruker lite ressurser.
- **Tetthet** – mange containere på samme server.
- **Grunnlag for moderne drift** – mikrotjenester, Kubernetes, CI/CD og skalering bygger på containere.

## Containere vs. virtuelle maskiner

```text
   VIRTUELLE MASKINER                         CONTAINERE
 ┌───────┐┌───────┐┌───────┐          ┌───────┐┌───────┐┌───────┐
 │ App A ││ App B ││ App C │          │ App A ││ App B ││ App C │
 │ Libs  ││ Libs  ││ Libs  │          │ Libs  ││ Libs  ││ Libs  │
 │GJESTE-││GJESTE-││GJESTE-│          └───────┘└───────┘└───────┘
 │  OS   ││  OS   ││  OS   │          ┌─────────────────────────┐
 └───────┘└───────┘└───────┘          │ Container-runtime       │
 ┌─────────────────────────┐          │ (Docker / containerd)   │
 │       HYPERVISOR        │          ├─────────────────────────┤
 ├─────────────────────────┤          │ VERTS-OS (Linux-kjerne) │
 │       MASKINVARE        │          ├─────────────────────────┤
 └─────────────────────────┘          │       MASKINVARE        │
                                      └─────────────────────────┘
```

| | Virtuell maskin | Container |
|---|---|---|
| Isolerer | Hele maskinen (eget OS og kjerne) | Prosesser (deler vertens kjerne) |
| Størrelse | Gigabyte | Megabyte (ofte 20–500 MB) |
| Oppstart | Minutter | Sekunder eller mindre |
| Isolasjonsstyrke | Sterk | God, men svakere (delt kjerne) |
| Typisk bruk | Ulike OS, sterk isolasjon, hele servere | Applikasjoner og mikrotjenester |

> **Vanlig feil:** «Containere erstatter VM-er.» Ofte kjører containere **på** VM-er – for eksempel er nodene i AKS vanlige Azure-VM-er. De løser forskjellige problemer og brukes sammen.

**Hvordan fungerer isolasjonen?** Containere bruker funksjoner i Linux-kjernen:

- **Namespaces** – gir hver container sin egen «utsikt»: egne prosess-ID-er, eget nettverk, eget filsystem, eget vertsnavn. Prosessen tror den er alene.
- **cgroups** (*control groups*) – begrenser hvor mye CPU og minne en container kan bruke.
- **Union-filsystemer** (f.eks. overlayfs) – stabler lag av filer oppå hverandre (se «lag» under).

Docker Desktop på Windows og macOS kjører derfor en liten Linux-VM i bakgrunnen for å kjøre Linux-containere. (Det finnes også Windows-containere, men Linux-containere er det vanlige.)

## Hva er Docker?

**Docker** er verktøyet som gjorde containere enkle å bruke (lansert 2013). Det består av:

- **Docker CLI** (`docker`) – kommandoene du skriver.
- **Docker Engine** (`dockerd`) – tjenesten som bygger og kjører containere (bruker **containerd** og **runc** under panseret).
- **Docker Desktop** – pakke for Windows/macOS med GUI, Engine og Linux-VM. Gratis for personlig bruk, utdanning og små bedrifter; større bedrifter trenger betalt abonnement – sjekk Dockers gjeldende lisensvilkår.
- **Docker Hub** – et offentlig register for images.

Containerformatet er standardisert av **OCI** (*Open Container Initiative*), så images bygget med Docker kan kjøres av andre verktøy (Podman, containerd, Kubernetes).

**Installer:**

- Windows/macOS: Docker Desktop fra docker.com.
- Linux (Ubuntu): følg «Install Docker Engine on Ubuntu» på docs.docker.com, og legg brukeren din i `docker`-gruppen: `sudo usermod -aG docker $USER` (logg ut og inn igjen).

```bash
$ docker version
$ docker run hello-world
Hello from Docker!
This message shows that your installation appears to be working correctly.
```

> **Sikkerhet:** Medlemskap i `docker`-gruppen gir i praksis root-tilgang til maskinen. Gi det bare til betrodde brukere.

## Images og containere

**Image** – en **skrivebeskyttet mal** med alt som trengs for å kjøre appen: filsystem, avhengigheter, standardkommando.

**Container** – en **kjørende instans** av et image, med et tynt skrivbart lag på toppen.

> **Hverdagsanalogi:** Et image er en **oppskrift** (eller en kakeform). En container er **kaken** du har laget fra den. Du kan lage mange kaker fra samme oppskrift, og spiser du én kake, er oppskriften like hel. I programmeringsspråk: image = klasse, container = objekt.

```text
          docker build              docker run
 Dockerfile ─────────► IMAGE ───────────────► CONTAINER (kjører)
 (oppskrift)          (mal, lag)      ├─────► CONTAINER 2
                          ▲  │        └─────► CONTAINER 3
              docker pull │  │ docker push
                          │  ▼
                       REGISTRY (Docker Hub, ACR)
```

### Første container

```bash
$ docker run -d -p 8080:80 --name web nginx:1.27
# -d          = detached: kjør i bakgrunnen
# -p 8080:80  = port 8080 på DIN maskin → port 80 i containeren
# --name web  = gi containeren et navn
# nginx:1.27  = image "nginx" med tag "1.27" (hentes fra Docker Hub hvis du ikke har det)

$ curl http://localhost:8080          # eller åpne i nettleseren
<h1>Welcome to nginx!</h1>
```

### Navn på images

```text
 acrlab123.azurecr.io / team / flaskapp : 1.4.2
 └──── register ────┘ └─ repo-sti ───┘   └ tag ┘
 Uten register: Docker Hub. Uten tag: «latest».
 docker.io/library/nginx:1.27 = nginx:1.27
```

> **Vanlig feil:** Å bruke `:latest` i produksjon. «latest» er bare en tag som kan peke på hva som helst, og endres uten forvarsel. Bruk **eksplisitte versjoner** (`python:3.12-slim`, `minapp:1.4.2` eller Git-commit-hash som tag). For maksimal sikkerhet kan du referere til **digest** (`nginx@sha256:...`), som aldri endres.

### Viktige kommandoer

```bash
# Containere
$ docker ps                      # kjørende containere
$ docker ps -a                   # alle, også stoppede
$ docker logs web                # se loggene (stdout/stderr)
$ docker logs -f web             # følg loggene live
$ docker exec -it web sh         # åpne et shell INNE i containeren (-it = interaktiv terminal)
$ docker stop web                # stopp (SIGTERM, så SIGKILL etter 10 s)
$ docker start web               # start igjen
$ docker rm web                  # slett (må være stoppet, eller bruk -f)
$ docker inspect web             # alle detaljer i JSON
$ docker stats                   # live CPU/minne per container
$ docker run --rm -it ubuntu:24.04 bash   # midlertidig container, slettes når du avslutter

# Images
$ docker images                  # list lokale images
$ docker pull python:3.12-slim   # hent et image
$ docker rmi nginx:1.27          # slett et image
$ docker image history nginx:1.27   # se lagene

# Rydding
$ docker system df               # hvor mye plass bruker Docker?
$ docker system prune            # slett stoppede containere, ubrukte nettverk og «dangling» images
```

### Lag (*layers*) og cache

Et image består av **lag**. Hver instruksjon i en Dockerfile som endrer filsystemet, lager et nytt lag. Lagene er **delt** mellom images og **cachet**: hvis et lag ikke har endret seg, gjenbrukes det ved neste bygg.

```text
 ┌────────────────────────────┐  ← skrivbart container-lag (forsvinner med containeren)
 ├────────────────────────────┤
 │ COPY . .        (din kode) │  ← endres ofte
 │ RUN pip install ...        │  ← endres når requirements.txt endres
 │ COPY requirements.txt .    │
 │ python:3.12-slim (base)    │  ← endres sjelden, deles med andre images
 └────────────────────────────┘
```

> **Husk:** Det som endres **sjeldnest** skal stå **øverst** i Dockerfile, det som endres **oftest** nederst. Da gjenbrukes cachen, og byggene blir raske.

## Dockerfile

**Hva er det?** En tekstfil med instruksjoner for å bygge et image.

### En enkel Dockerfile for en Flask-app

Prosjektstruktur:

```text
flaskapp/
├── app.py
├── requirements.txt
├── Dockerfile
└── .dockerignore
```

`app.py`:

```python
import os
from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/")
def hjem():
    return f"Hei fra container! Miljø: {os.environ.get('APP_ENV', 'ukjent')}"

@app.route("/health")
def health():
    return jsonify(status="ok")
```

`requirements.txt`:

```text
flask==3.1.*
gunicorn==23.*
```

(Versjonsnumrene er eksempler; sjekk siste versjoner på PyPI.)

`Dockerfile`:

```dockerfile
# 1. Start fra et offisielt, slankt Python-image (fast versjon, ikke latest)
FROM python:3.12-slim

# 2. Python-innstillinger: ikke lag .pyc-filer, og skriv logger umiddelbart
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 3. Arbeidsmappe inne i imaget (opprettes automatisk)
WORKDIR /app

# 4. Kopier BARE avhengighetslisten først – utnytter cache
COPY requirements.txt .

# 5. Installer avhengigheter (uten pip-cache for å holde imaget lite)
RUN pip install --no-cache-dir -r requirements.txt

# 6. Kopier resten av koden
COPY . .

# 7. Lag en vanlig bruker og bytt til den – ikke kjør som root
RUN useradd --create-home --uid 10001 appuser
USER appuser

# 8. Dokumenter hvilken port appen lytter på
EXPOSE 8000

# 9. Kommandoen som starter appen. Lytt på 0.0.0.0 – IKKE 127.0.0.1!
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "app:app"]
```

`.dockerignore` (hva som **ikke** skal kopieres inn i imaget):

```text
.git
.venv
__pycache__
*.pyc
.env
Dockerfile
.dockerignore
```

**Bygg og kjør:**

```bash
$ docker build -t flaskapp:1.0 .          # -t = navn:tag, . = byggekontekst (denne mappen)
$ docker run -d -p 8000:8000 -e APP_ENV=lokal --name flask flaskapp:1.0
$ curl localhost:8000
Hei fra container! Miljø: lokal
```

### Dockerfile-instruksjoner

| Instruksjon | Gjør |
|---|---|
| `FROM` | Base-image (alltid først) |
| `WORKDIR` | Setter arbeidsmappe |
| `COPY` | Kopierer filer fra byggekonteksten inn i imaget |
| `ADD` | Som COPY, men kan også pakke ut arkiver og hente URL-er – bruk heller COPY |
| `RUN` | Kjører en kommando **under bygging** (installere pakker) |
| `ENV` | Setter miljøvariabler |
| `ARG` | Variabel som bare finnes under bygging (`docker build --build-arg`) |
| `EXPOSE` | Dokumenterer porten (åpner den ikke!) |
| `USER` | Hvilken bruker som kjører resten og containeren |
| `CMD` | Standardkommando **når containeren starter** (kan overstyres) |
| `ENTRYPOINT` | Fast hovedkommando; `CMD` blir da argumenter til den |
| `HEALTHCHECK` | Kommando Docker bruker for å sjekke om containeren er frisk |
| `LABEL` | Metadata (versjon, eier, kilde) |

> **Vanlig feil:** `RUN` vs. `CMD`. `RUN` kjøres **når imaget bygges**. `CMD` kjøres **når containeren starter**. `RUN python app.py` vil prøve å starte appen under byggingen – og bygget henger.

> **Vanlig feil:** `EXPOSE 8000` publiserer ikke porten. Du må fortsatt bruke `-p 8000:8000` (eller tilsvarende i Compose/Kubernetes).

### Multi-stage builds

**Hva er det?** En Dockerfile med **flere `FROM`-steg**. Du bygger i ett steg med alle byggeverktøy, og kopierer **bare resultatet** over i et lite, rent sluttimage.

**Hvorfor?** Mindre images (raskere, billigere), og færre verktøy i produksjonsimaget betyr **mindre angrepsflate**.

Eksempel med en Go-app (Go kompilerer til én fil):

```dockerfile
# --- Steg 1: bygg ---
FROM golang:1.23 AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o /out/app .

# --- Steg 2: kjør ---
FROM gcr.io/distroless/static-debian12     # minimalt image uten shell og pakkehåndterer
COPY --from=build /out/app /app
USER nonroot
ENTRYPOINT ["/app"]
```

Byggeimaget er på hundrevis av MB; sluttimaget kan bli under 20 MB.

Eksempel med Python (bygg «wheels» i ett steg, installer i et rent steg):

```dockerfile
FROM python:3.12-slim AS build
WORKDIR /app
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

FROM python:3.12-slim
WORKDIR /app
COPY --from=build /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels
COPY . .
RUN useradd --uid 10001 appuser
USER appuser
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]
```

## Volumes – data som overlever containeren

**Problemet.** Containere er **flyktige** (*ephemeral*). Data skrevet i containerens filsystem forsvinner når containeren slettes. Det er bra for applikasjonskode, men katastrofalt for en database.

**Løsningen.** Lagre data **utenfor** containeren:

| Type | Hva | Bruk |
|---|---|---|
| **Named volume** | Lagring administrert av Docker | Databaser, varige data (anbefalt) |
| **Bind mount** | En mappe fra vertsmaskinen monteres inn | Lokal utvikling (endre kode uten å bygge på nytt) |
| **tmpfs** | I minnet, forsvinner ved stopp | Midlertidige, sensitive data |

```bash
# Named volume for PostgreSQL
$ docker volume create pgdata
$ docker run -d --name db \
    -e POSTGRES_PASSWORD=bytt-meg \
    -v pgdata:/var/lib/postgresql/data \
    postgres:16
$ docker rm -f db              # slett containeren ...
$ docker run -d --name db -e POSTGRES_PASSWORD=bytt-meg -v pgdata:/var/lib/postgresql/data postgres:16
# ... dataene er der fortsatt!

# Bind mount for utvikling
$ docker run -d -p 8000:8000 -v "$(pwd)":/app flaskapp:1.0

$ docker volume ls
$ docker volume inspect pgdata
$ docker volume rm pgdata       # slett (data er borte!)
```

> **Fra arbeidslivet:** I produksjon kjører man sjelden databaser i containere man drifter selv; man bruker ofte en administrert database (Azure SQL, Azure Database for PostgreSQL). Containere er best for **tilstandsløse** (*stateless*) apper.

## Nettverk i Docker

Docker lager virtuelle nettverk for containere.

| Driver | Hva |
|---|---|
| `bridge` | Standard. Privat nettverk på verten; containere når hverandre, verten når dem via publiserte porter |
| `host` | Containeren deler vertens nettverk direkte (ingen isolasjon) |
| `none` | Ingen nettverk |
| `overlay` | Nettverk over flere verter (Swarm) |

**Viktig regel:** På et **brukerdefinert** bridge-nettverk kan containere nå hverandre **med navn** via Dockers innebygde DNS. På standardnettverket `bridge` kan de ikke det.

```bash
$ docker network create appnett
$ docker run -d --name db --network appnett -e POSTGRES_PASSWORD=bytt-meg postgres:16
$ docker run -it --rm --network appnett postgres:16 psql -h db -U postgres
#                                                            ▲ «db» er containernavnet = DNS-navn
```

```text
 Din PC (localhost:8000) ──-p 8000:8000──┐
                                          ▼
 ┌──────────── Docker-nettverk «appnett» ──────────────┐
 │  ┌──────────────┐   http://db:5432   ┌────────────┐ │
 │  │ web (Flask)  │ ─────────────────► │ db (Postgres)│
 │  └──────────────┘                    └────────────┘ │
 └─────────────────────────────────────────────────────┘
   (db har ingen publisert port – den kan ikke nås fra utsiden. Bra!)
```

> **Vanlig feil:** Inne i en container betyr `localhost` **containeren selv**, ikke din PC og ikke en annen container. Bruk tjenestenavnet (`db`) for å nå andre containere.

## Docker Compose

**Hva er det?** Et verktøy for å definere og kjøre **flere containere sammen** med én YAML-fil (`compose.yaml`) og én kommando.

**Hvorfor?** En ekte app består ofte av web + database + cache + kanskje en kø. Å starte alle med lange `docker run`-kommandoer er tungvint og feilutsatt.

`compose.yaml`:

```yaml
services:
  web:
    build: .                              # bygg fra Dockerfile i denne mappen
    ports:
      - "8000:8000"                       # vert:container
    environment:
      APP_ENV: utvikling
      DATABASE_URL: postgresql://app:${DB_PASSWORD}@db:5432/appdb   # ${} hentes fra .env-fil
    depends_on:
      db:
        condition: service_healthy        # vent til databasen er frisk
    restart: unless-stopped

  db:
    image: postgres:16
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: appdb
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d appdb"]
      interval: 5s
      retries: 10

  cache:
    image: redis:7

volumes:
  pgdata:                                 # named volume
```

`.env` (sjekkes **ikke** inn i Git):

```text
DB_PASSWORD=lokalt-utviklingspassord
```

```bash
$ docker compose up -d           # bygg (ved behov) og start alt i bakgrunnen
$ docker compose ps              # status
$ docker compose logs -f web     # logger for én tjeneste
$ docker compose exec db psql -U app appdb   # kjør kommando i en tjeneste
$ docker compose up -d --build   # bygg på nytt etter kodeendringer
$ docker compose down            # stopp og fjern containere og nettverk
$ docker compose down -v         # ... og slett volumes (data!)
```

Compose lager automatisk et eget nettverk for prosjektet, så tjenestene når hverandre på navn (`db`, `cache`).

> **Merk:** Den moderne kommandoen er `docker compose` (med mellomrom, Compose v2 som Docker-plugin). Eldre guider bruker `docker-compose` (bindestrek) og en `version:`-linje øverst i filen – begge deler er utdaterte.

> **Fra arbeidslivet:** Compose brukes mest til **lokal utvikling og testing** (og i CI for integrasjonstester). I produksjon brukes typisk Kubernetes, Azure Container Apps eller App Service.

## Registre (*registries*)

Et register lagrer og distribuerer images.

| Register | Type |
|---|---|
| Docker Hub | Offentlig (og private repoer); har grenser for nedlastinger for anonyme/gratisbrukere |
| GitHub Container Registry (`ghcr.io`) | Knyttet til GitHub-repoer |
| Azure Container Registry (ACR) | Privat, i Azure (kapittel 7.2) |
| Amazon ECR, Google Artifact Registry | De andre skyene |

**Publisere til Docker Hub:**

```bash
$ docker login                                     # brukernavn + access token
$ docker tag flaskapp:1.0 <brukernavn>/flaskapp:1.0
$ docker push <brukernavn>/flaskapp:1.0
```

**Publisere til ACR:**

```bash
$ az acr login -n acrlab123
$ docker tag flaskapp:1.0 acrlab123.azurecr.io/flaskapp:1.0
$ docker push acrlab123.azurecr.io/flaskapp:1.0
```

**Bygg for riktig arkitektur.** Bygger du på en Mac med Apple Silicon (ARM), får du et ARM-image som ikke kjører på vanlige x86-servere i skyen. Bruk:

```bash
$ docker buildx build --platform linux/amd64 -t acrlab123.azurecr.io/flaskapp:1.0 --push .
```

## Container-sikkerhet

| Praksis | Hvorfor |
|---|---|
| **Kjør som ikke-root** (`USER`) | Begrenser skaden hvis appen blir kompromittert |
| **Små, offisielle base-images** (slim, alpine, distroless) | Færre pakker = færre sårbarheter |
| **Faste versjoner** (tag eller digest) | Forutsigbarhet, ingen overraskelser |
| **Skann images** (Trivy, Docker Scout, Defender for Containers) | Finn kjente sårbarheter (CVE-er) |
| **Ingen hemmeligheter i images** | Alle som har imaget kan lese alle lag – også slettede filer i tidligere lag |
| **`.dockerignore`** | Hindrer at `.env`, `.git` og nøkler havner i imaget |
| **Oppdater base-images jevnlig** | Sikkerhetsoppdateringer |
| **Begrens ressurser** (`--memory`, `--cpus`) | Hindrer at én container tar ned verten |
| **Read-only filsystem** (`--read-only`) og dropp capabilities (`--cap-drop ALL`) | Herding |
| **Signer images** (Notation, Cosign) og lag SBOM | Forsyningskjedesikkerhet |

```bash
# Skann et image med Trivy (kan kjøres som container)
$ docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:latest image flaskapp:1.0
```

(Her er `latest` for selve skanneverktøyet akseptabelt i en lab; i en pipeline bør også verktøyversjonen låses.)

> **Vanlig feil:** `ENV DB_PASSWORD=hemmelig` i Dockerfile, eller `COPY .env .`. Hemmeligheten ligger da i imaget for alltid, og alle med tilgang til registeret kan lese den. Hemmeligheter gis **når containeren kjører** (miljøvariabler fra Key Vault, Kubernetes Secrets, osv.), og byggehemmeligheter med `RUN --mount=type=secret`.

> **Vanlig feil:** Å montere `/var/run/docker.sock` inn i en app-container. Det gir containeren full kontroll over Docker – og dermed verten.

## Feilsøking av containere

**Metode:**

```text
 1. Kjører den?           docker ps -a           (Exited? Restarting?)
 2. Hvorfor stoppet den?  docker logs <navn>     (feilmelding fra appen)
                          docker inspect <navn> --format '{{.State.ExitCode}}'
 3. Gå inn og se          docker exec -it <navn> sh
 4. Nettverk/porter       docker port <navn> ; curl fra innsiden ; lytter appen på 0.0.0.0?
 5. Ressurser             docker stats           (minne fullt? → OOMKilled)
 6. Bygg-problemer        docker build --progress=plain --no-cache .
```

**Vanlige feil og løsninger:**

| Symptom | Sannsynlig årsak | Løsning |
|---|---|---|
| Containeren stopper umiddelbart (`Exited (0)`) | Hovedprosessen avsluttet (f.eks. CMD kjører et skript som er ferdig) | Containeren lever bare så lenge hovedprosessen kjører; start en prosess som blir kjørende i forgrunnen |
| `Exited (1)` | Appen krasjet | `docker logs` |
| `Exited (137)` | Drept med SIGKILL, ofte **OOMKilled** (tom for minne) | `docker inspect` → `OOMKilled: true`; øk minne eller fiks lekkasje |
| Ingen svar på `localhost:8000` | Port ikke publisert, eller appen lytter på `127.0.0.1` | `-p 8000:8000`, og bind til `0.0.0.0` |
| `port is already allocated` | Porten brukes allerede på verten | Velg en annen vertsport (`-p 8001:8000`) eller stopp den andre |
| `exec format error` | Feil CPU-arkitektur (ARM vs. AMD64) | `docker buildx build --platform linux/amd64` |
| `permission denied` på filer | Appen kjører som ikke-root, men filene eies av root | `COPY --chown=appuser:appuser` eller `chown` i Dockerfile |
| Kan ikke nå `db` | Containerne er ikke på samme brukerdefinerte nettverk | Bruk Compose eller `--network` |
| Endringer i koden vises ikke | Du bruker et gammelt image | `docker compose up --build` |
| `toomanyrequests` fra Docker Hub | Nedlastingsgrense | Logg inn, eller bruk et eget register (ACR) som speil |

```bash
# Nyttig: start et feilende image med et shell i stedet for vanlig kommando
$ docker run -it --rm --entrypoint sh flaskapp:1.0
```

## Prosjekt: bygg, kjør og publiser en applikasjon

**Mål:** Containeriser Flask-appen, kjør den med PostgreSQL via Compose, skann den, og publiser imaget til GitHub Container Registry automatisk med GitHub Actions. Tid: 2–3 timer. Kostnad: gratis.

### Steg 1 – appen med database

Utvid `app.py` til å telle besøk i PostgreSQL:

```python
import os
import psycopg                                   # pip: psycopg[binary]
from flask import Flask, jsonify

app = Flask(__name__)
DB_URL = os.environ["DATABASE_URL"]              # krasj tidlig hvis den mangler

def db():
    return psycopg.connect(DB_URL, autocommit=True)

with db() as conn:                               # lag tabellen ved oppstart
    conn.execute("CREATE TABLE IF NOT EXISTS besok (id SERIAL PRIMARY KEY, tid TIMESTAMPTZ DEFAULT now())")

@app.route("/")
def hjem():
    with db() as conn:
        conn.execute("INSERT INTO besok DEFAULT VALUES")
        antall = conn.execute("SELECT count(*) FROM besok").fetchone()[0]
    return f"Hei! Denne siden har hatt {antall} besøk."

@app.route("/health")
def health():
    return jsonify(status="ok")
```

`requirements.txt`:

```text
flask==3.1.*
gunicorn==23.*
psycopg[binary]==3.2.*
```

### Steg 2 – Dockerfile, .dockerignore og compose.yaml

Bruk Dockerfile og `.dockerignore` fra tidligere i kapitlet, og `compose.yaml` fra Compose-seksjonen (du kan fjerne `cache`). Legg til en `HEALTHCHECK` i Dockerfile:

```dockerfile
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
```

### Steg 3 – kjør

```bash
$ echo "DB_PASSWORD=lokalt-passord" > .env
$ docker compose up -d --build
$ curl localhost:8000          # «Denne siden har hatt 1 besøk.»
$ curl localhost:8000          # 2 ...
$ docker compose down && docker compose up -d
$ curl localhost:8000          # 3 – dataene overlevde takket være volumet
```

### Steg 4 – skann

```bash
$ docker build -t flaskapp:test .
$ docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:latest image --severity HIGH,CRITICAL flaskapp:test
```

### Steg 5 – publiser automatisk med GitHub Actions

`.github/workflows/docker.yml`:

```yaml
name: Docker
on:
  push:
    branches: [main]

permissions:
  contents: read
  packages: write                          # tillat push til ghcr.io

jobs:
  build-push:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}     # automatisk token, ingen egen hemmelighet
      - uses: docker/build-push-action@v6
        with:
          push: true
          tags: |
            ghcr.io/${{ github.repository }}:${{ github.sha }}
            ghcr.io/${{ github.repository }}:latest
```

(Repo-navnet må være med små bokstaver for ghcr.io. Har du store bokstaver i brukernavnet, sett taggen manuelt med små bokstaver.)

### Steg 6 – verifiser

Push til `main`. Under **Packages** på GitHub-profilen din ser du imaget. Hent og kjør det et annet sted:

```bash
$ docker run -d -p 8000:8000 -e DATABASE_URL=... ghcr.io/<bruker>/<repo>:<sha>
```

### Forventet resultat, feilsøking og opprydding

- **Resultat:** Et repo med Dockerfile, compose.yaml, workflow, og et publisert image i ghcr.io.
- **Feilsøking:** Workflow feiler med `denied` → sjekk `permissions: packages: write`. Appen krasjer med `KeyError: 'DATABASE_URL'` → miljøvariabelen mangler.
- **Opprydding:** `docker compose down -v`, `docker system prune`. Pakker på ghcr.io kan slettes under *Package settings*.
- **På CV/GitHub:** «Containeriserte en Python-webapp med multi-stage Dockerfile, Docker Compose for lokal utvikling med PostgreSQL, sårbarhetsskanning med Trivy og automatisk publisering til GitHub Container Registry med GitHub Actions.»

## Kapitteloppsummering

- En container pakker app + avhengigheter, og deler vertens kjerne. Lettere og raskere enn VM-er, men svakere isolasjon.
- Image = mal (lag, skrivebeskyttet). Container = kjørende instans. Registre lagrer images.
- Dockerfile: sjeldent endrede ting øverst for cache, `.dockerignore`, ikke-root, faste versjoner, multi-stage for små images.
- Volumes gjør data varige; brukerdefinerte nettverk lar containere finne hverandre på navn.
- Compose kjører flere containere sammen – ideelt for lokal utvikling.
- Sikkerhet: ingen hemmeligheter i images, skann, minimalt image, ikke-root.
- Feilsøking: `ps -a`, `logs`, `inspect`, `exec`, `stats`.

## Øvingsoppgaver

1. Kjør `docker run -it --rm alpine:3.20 sh`, lag en fil, avslutt, og start på nytt. Finnes filen? Hvorfor ikke?
2. Bygg Flask-imaget to ganger etter hverandre. Hvor lang tid tar andre bygg? Endre `app.py` og bygg igjen – hvilke lag gjenbrukes?
3. Sammenlign størrelsen på `python:3.12`, `python:3.12-slim` og `python:3.12-alpine` med `docker images`.
4. Gjør Python-imaget ditt om til multi-stage og mål størrelsesforskjellen.
5. Fremprovoser `OOMKilled`: `docker run --memory=50m python:3.12-slim python -c "a = 'x' * 10**9"` og finn årsaken med `docker inspect`.
6. Legg Redis til i compose-filen og bruk den som teller i stedet for PostgreSQL.

## Quiz

1. Hva er forskjellen på et image og en container?
2. Hva deler containere som VM-er ikke deler?
3. Hvorfor kopierer man `requirements.txt` før resten av koden i Dockerfile?
4. Hva er forskjellen på `RUN` og `CMD`?
5. Åpner `EXPOSE 80` porten slik at du kan nå den fra din PC?
6. Hvorfor bør du ikke bruke `:latest` i produksjon?
7. Hva skjer med data skrevet i en containers filsystem når containeren slettes?
8. Hvordan når en container en annen container i Compose?
9. Hva betyr exit-kode 137?
10. Du har slettet en fil med passord i et senere lag (`RUN rm .env`). Er passordet borte fra imaget?

### Fasit

1. **Image**: skrivebeskyttet mal med app og avhengigheter. **Container**: en kjørende instans av et image, med et skrivbart lag.
2. **Operativsystemets kjerne** (Linux-kjernen på verten).
3. For å utnytte lag-cachen: avhengighetene installeres bare på nytt når `requirements.txt` endres, ikke ved hver kodeendring.
4. `RUN` kjøres **når imaget bygges**. `CMD` er kommandoen som kjøres **når containeren starter**.
5. **Nei.** `EXPOSE` er bare dokumentasjon. Du må publisere porten med `-p` (eller `ports:` i Compose).
6. Fordi taggen kan peke på en ny versjon når som helst, slik at du ikke vet hva som kjører, og rollback blir vanskelig.
7. Den forsvinner – med mindre den er lagret i et volume eller en bind mount.
8. Med **tjenestenavnet** som vertsnavn (f.eks. `db:5432`), via Docker sin innebygde DNS på Compose-nettverket.
9. Prosessen ble drept med SIGKILL (128 + 9), ofte fordi containeren gikk tom for minne (OOMKilled).
10. **Nei.** Filen finnes fortsatt i laget der den ble kopiert inn, og kan hentes ut. Bytt passordet og bygg imaget uten å kopiere filen inn.
