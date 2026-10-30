# Del 12 – CI/CD og automatisering

**Læringsmål for kapitlet.** Når du er ferdig, skal du kunne:

- designe en CI/CD-pipeline fra kode til produksjon,
- bruke GitHub Actions i dybden, og kjenne Azure Pipelines og Jenkins,
- forklare build-, test- og deploy-pipelines, artefakter og hemmeligheter,
- koble GitHub Actions til Azure uten lagrede hemmeligheter (OIDC),
- implementere rollback, blue-green og canary deployment,
- bygge en komplett pipeline som deployer en container til Azure.

## Hva er en pipeline?

**Hva er det?** En **pipeline** er en automatisert kjede av steg som tar koden fra en commit til en kjørende tjeneste: hent kode → bygg → test → skann → pakk → deploy → verifiser.

> **Hverdagsanalogi:** Et samlebånd i en bilfabrikk. Hver stasjon gjør én ting (sveise, lakkere, kvalitetskontroll). Feiler kvalitetskontrollen, stopper båndet før bilen når kunden. Ingen bygger biler for hånd én og én – det er for tregt og for ujevnt.

```text
  ┌──────┐   ┌───────┐   ┌──────┐   ┌───────┐   ┌─────────┐   ┌─────────┐   ┌──────────┐
  │ Kode │──►│ Bygg  │──►│ Test │──►│ Skann │──►│ Artefakt│──►│ Deploy  │──►│ Verifiser│
  │ push │   │       │   │      │   │       │   │ (image) │   │ staging │   │ smoke    │
  └──────┘   └───────┘   └──────┘   └───────┘   └─────────┘   └────┬────┘   └────┬─────┘
       ▲            ✗ feil → stopp, varsle utvikleren                │ godkjent    │
       └──────────────────────────── rask tilbakemelding ◄───────────┴─► Deploy prod
                                                                          (blue-green/canary)
```

**Prinsipper for gode pipelines:**

1. **Rask** – CI bør gi svar på minutter. Trege pipelines blir ignorert eller omgått.
2. **Pålitelig** – ingen «flaky» tester som feiler tilfeldig.
3. **Bygg én gang, deploy mange ganger** – samme artefakt (f.eks. samme image) går gjennom dev, test og prod. Aldri bygg på nytt for prod.
4. **Alt i kode** – pipelinen ligger i repoet (YAML) og gjennomgås som annen kode.
5. **Sikker** – minste privilegium, ingen hemmeligheter i klartekst, låste versjoner av tredjepartskomponenter.
6. **Sporbar** – du vet hvilken commit som kjører i hvilket miljø.

## Testing i pipelinen

Testene er det som gjør automatisk deploy **trygt**.

```text
               ▲   få, trege, dyre
              ╱ ╲        E2E / UI-tester (Playwright, Selenium)
             ╱───╲
            ╱     ╲      Integrasjonstester (app + database, API-kontrakter)
           ╱───────╲
          ╱         ╲    Enhetstester (unit tests) – mange, raske, billige
         ╱───────────╲
                      TESTPYRAMIDEN
```

| Testtype | Tester | Når i pipelinen |
|---|---|---|
| **Linting / formatering** | Kodestil og åpenbare feil (ruff, shellcheck, yamllint, hadolint) | Først – sekunder |
| **Enhetstester** | Enkeltfunksjoner isolert | CI på hver push/PR |
| **Integrasjonstester** | Komponenter sammen (app + database i Docker Compose) | CI |
| **Sikkerhetsskanning** | SAST, avhengigheter, image, IaC, hemmeligheter | CI |
| **Smoke tests** | «Lever det i det hele tatt?» (`/health` svarer 200) | Rett etter hver deploy |
| **E2E-tester** | Hele brukerflyter i nettleser | Mot staging |
| **Last-/ytelsestester** | Tåler systemet forventet trafikk? (k6, JMeter, Azure Load Testing) | Periodisk / før store lanseringer |

**Kodedekning** (*code coverage*) måler hvor mye av koden testene kjører. Nyttig som indikator, men 100 % dekning betyr ikke feilfri kode.

## GitHub Actions i dybden

Grunnleggende ble vist i kapittel 5. Nå går vi dypere.

### Byggesteinene

```text
 .github/workflows/ci.yml
 └── workflow           (utløses av events: push, pull_request, schedule, workflow_dispatch …)
      └── jobs          (kjører parallelt som standard; needs: gir rekkefølge)
           ├── runs-on  (runner: ubuntu-latest, windows-latest, self-hosted …)
           └── steps    (uses: en action  |  run: et skall-kommando)
```

| Begrep | Forklaring |
|---|---|
| **Event / trigger** | Hva som starter workflowen: `push`, `pull_request`, `schedule` (cron), `workflow_dispatch` (manuelt), `release`, `workflow_call` (gjenbruk) |
| **Job** | En gruppe steg på samme runner. Jobber er isolerte (egne maskiner) |
| **Step** | Én handling: en `run`-kommando eller en `uses`-action |
| **Action** | Gjenbrukbar komponent fra Marketplace eller eget repo (`actions/checkout`, `azure/login`) |
| **Runner** | Maskinen som kjører jobben. GitHub-hosted (ny VM hver gang) eller self-hosted |
| **Artifact** | Filer som lagres fra en jobb og kan lastes ned eller brukes av andre jobber |
| **Environment** | Deploymål (`staging`, `production`) med beskyttelsesregler, godkjenninger og egne hemmeligheter |
| **Secret / variable** | Konfigurasjon på repo-, environment- eller organisasjonsnivå |
| **Context / expression** | `${{ github.sha }}`, `${{ secrets.X }}`, `${{ needs.build.outputs.tag }}` |

### Eksempel: en profesjonell CI-workflow

```yaml
name: CI

on:
  pull_request:
  push:
    branches: [main]

# Minste privilegium: tokenet kan bare lese repoet som standard
permissions:
  contents: read

# Avbryt eldre kjøringer på samme branch når en ny kommer
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install ruff
      - run: ruff check .                 # linting
      - run: ruff format --check .        # formatering

  test:
    runs-on: ubuntu-latest
    needs: lint                           # vent på lint
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]  # kjør testene på to versjoner parallelt
    services:
      postgres:                           # database-container for integrasjonstester
        image: postgres:16
        env:
          POSTGRES_PASSWORD: test
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready --health-interval 5s --health-retries 10
    env:
      DATABASE_URL: postgresql://postgres:test@localhost:5432/postgres
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip                      # cache pip-pakker mellom kjøringer
      - run: pip install -r requirements.txt pytest pytest-cov
      - run: pytest --cov=. --cov-report=xml -q
      - uses: actions/upload-artifact@v4  # lagre dekningsrapporten
        with:
          name: coverage-${{ matrix.python-version }}
          path: coverage.xml
```

**Nøkkelpunkter:**

- `needs:` lager rekkefølge mellom jobber.
- `strategy.matrix` kjører samme jobb med ulike parametere.
- `services:` gir deg containere (database, Redis) under jobben.
- `cache:` gjør pipelinen raskere.
- `permissions:` og `concurrency:` er tegn på en moden workflow.

### Gjenbruk

- **Reusable workflows** (`on: workflow_call`) – en hel workflow som andre repoer kan kalle. Grunnlaget for felles pipeline-maler i en organisasjon.
- **Composite actions** – samle flere steg i én egen action.

```yaml
# I et annet repo:
jobs:
  ci:
    uses: min-org/pipeline-maler/.github/workflows/python-ci.yml@v1
    with:
      python-version: "3.12"
```

### Sikkerhet i GitHub Actions

| Risiko | Tiltak |
|---|---|
| For brede rettigheter på `GITHUB_TOKEN` | Sett `permissions:` eksplisitt, minst mulig |
| Kompromitterte tredjeparts-actions | Lås til **full commit-SHA** (`uses: noen/action@<40-tegns-sha>`), bruk Dependabot for å oppdatere |
| Hemmeligheter i logger | Bruk `secrets`, aldri `echo` dem; GitHub maskerer kjente hemmeligheter, men ikke avledede verdier |
| Lagrede sky-nøkler som lekker | **OIDC** til Azure – ingen lagrede nøkler (se under) |
| PR-er fra forks som kjører med hemmeligheter | Vær svært forsiktig med `pull_request_target`; hemmeligheter er ikke tilgjengelige for fork-PR-er med vanlig `pull_request` |
| Script injection | Ikke bruk `${{ github.event.pull_request.title }}` o.l. direkte i `run:` – send via `env:` |
| Ubeskyttet produksjonsdeploy | **Environments** med *required reviewers* og begrensning til `main` |

## Azure DevOps Pipelines

Azure Pipelines ble gjennomgått i kapittel 7.4. Sammenlignet med GitHub Actions:

| | GitHub Actions | Azure Pipelines |
|---|---|---|
| Fil | `.github/workflows/*.yml` | `azure-pipelines.yml` |
| Struktur | workflow → jobs → steps | pipeline → stages → jobs → steps |
| Gjenbruk | Actions, reusable workflows | Tasks, templates |
| Miljøer/godkjenning | Environments | Environments med approvals and checks |
| Azure-tilgang | `azure/login` med OIDC | Service connection med workload identity federation |
| Hemmeligheter | Secrets (repo/env/org) | Secret variables, variable groups (koblet til Key Vault) |
| Styrke | Tett integrasjon med GitHub, stort Marketplace | Moden for store bedrifter, sterke stages og godkjenninger |

Prinsippene er de samme; YAML-syntaksen er forskjellig.

## Jenkins

**Hva er det?** Jenkins er en eldre, svært utbredt **åpen kildekode CI/CD-server** som du drifter selv. Mange bedrifter har Jenkins fra før, så du vil sannsynligvis møte det.

**Kjennetegn:**

- Selvhostet (VM, container eller Kubernetes) – du har ansvar for oppdatering og sikkerhet.
- Enormt plugin-økosystem.
- Pipelines defineres i en **Jenkinsfile** (Groovy-basert DSL) i repoet.
- *Controller* (styrer) og *agents* (kjører jobbene).

```groovy
// Jenkinsfile (deklarativ pipeline)
pipeline {
    agent { docker { image 'python:3.12-slim' } }   // kjør stegene i en container

    environment {
        APP_ENV = 'ci'
    }

    stages {
        stage('Installer') {
            steps {
                sh 'pip install -r requirements.txt pytest'
            }
        }
        stage('Test') {
            steps {
                sh 'pytest -q --junitxml=results.xml'
            }
            post {
                always { junit 'results.xml' }        // vis testresultater i Jenkins
            }
        }
        stage('Deploy') {
            when { branch 'main' }                     // bare fra main
            steps {
                input message: 'Deploy til produksjon?'   // manuell godkjenning
                withCredentials([string(credentialsId: 'deploy-token', variable: 'TOKEN')]) {
                    sh './deploy.sh'                   // TOKEN er tilgjengelig som miljøvariabel
                }
            }
        }
    }
    post {
        failure { echo 'Pipelinen feilet – varsle teamet her' }
    }
}
```

> **Fra arbeidslivet:** Mange organisasjoner migrerer fra Jenkins til GitHub Actions eller Azure Pipelines for å slippe å drifte CI-serveren selv. Å kunne lese en Jenkinsfile og forklare hvordan den kan oversettes, er en nyttig ferdighet.

## Artefakter

**Hva er det?** Et **artefakt** er det ferdige produktet av et bygg: et container-image, en zip-fil, en Python-wheel, en JAR-fil, en Helm-chart, en Terraform-plan.

**Prinsipper:**

- **Bygg én gang** – samme artefakt promoteres gjennom alle miljøer.
- **Uforanderlig og versjonert** – tag med commit-SHA og/eller semantisk versjon (`1.4.2`). Aldri overskriv en eksisterende versjon.
- **Lagres i et register** – ACR/ghcr.io for images, Azure Artifacts/GitHub Packages for pakker.
- **Sporbar** – kunne svare på «hvilken commit kjører i produksjon nå?».
- **Signert og med SBOM** – for forsyningskjedesikkerhet (Cosign/Notation, `actions/attest-build-provenance`).

```text
 commit a1b2c3d ─► bygg ─► image  minapp:a1b2c3d ─► dev ✓ ─► staging ✓ ─► prod
                                  (samme image hele veien – bare konfigurasjonen endres)
```

## Hemmeligheter i pipelines

**Regel nummer én:** Hemmeligheter står **aldri** i koden eller i YAML-filen.

| Nivå | Løsning |
|---|---|
| OK | Pipeline-hemmeligheter (GitHub Secrets, Azure DevOps secret variables) |
| Bedre | Hemmeligheter i Key Vault, hentet av pipelinen ved kjøring |
| Best | **Ingen hemmelighet i det hele tatt**: OIDC / workload identity federation for skytilgang, managed identity for appen |

### OIDC fra GitHub Actions til Azure

**Hvordan det fungerer:**

```text
 1. Workflow ber GitHub om et OIDC-token          ┌──────────────┐
    (bevis: «jeg er repo X, branch main»)  ──────►│   GitHub     │
                                                  └──────┬───────┘
 2. azure/login sender tokenet til Entra ID               │ signert token
                                                  ┌──────▼───────┐
 3. Entra ID sjekker: finnes det en «federated    │  Entra ID    │
    credential» som stoler på akkurat dette       └──────┬───────┘
    repoet/branchen/environmentet?                       │ ja → kortlevd Azure-token
 4. Workflowen kjører az/terraform med tokenet ◄─────────┘   (gyldig i ca. 1 time)
```

Ingen klienthemmelighet lagres noe sted. Tokenet gjelder bare for det repoet og den branchen/det miljøet du har godkjent.

**Oppsett (én gang):**

```bash
# 1. App-registrering og service principal
APP_ID=$(az ad app create --display-name "gh-minapp-deploy" --query appId -o tsv)
az ad sp create --id $APP_ID

# 2. Federated credential: stol på GitHub-environmentet «production» i repoet ditt
az ad app federated-credential create --id $APP_ID --parameters '{
  "name": "gh-production",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:<github-bruker>/<repo>:environment:production",
  "audiences": ["api://AzureADTokenExchange"]
}'

# 3. Gi tilgang – minst mulig: Contributor på én ressursgruppe
az role assignment create --assignee $APP_ID --role Contributor \
  --scope $(az group show -n rg-minapp-prod --query id -o tsv)

# 4. Verdier som skal inn i GitHub (som variables eller secrets – de er ikke hemmelige i seg selv)
echo "AZURE_CLIENT_ID=$APP_ID"
echo "AZURE_TENANT_ID=$(az account show --query tenantId -o tsv)"
echo "AZURE_SUBSCRIPTION_ID=$(az account show --query id -o tsv)"
```

(Alternativt kan du bruke en **user-assigned managed identity** med federated credential i stedet for en app-registrering.)

**I workflowen:**

```yaml
permissions:
  id-token: write          # NØDVENDIG for å be om OIDC-token
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: production                # må matche "subject" i federated credential
    steps:
      - uses: azure/login@v2
        with:
          client-id: ${{ vars.AZURE_CLIENT_ID }}
          tenant-id: ${{ vars.AZURE_TENANT_ID }}
          subscription-id: ${{ vars.AZURE_SUBSCRIPTION_ID }}
      - run: az group show -n rg-minapp-prod -o table
```

> **Vanlig feil:** `AADSTS70021: No matching federated identity record found`. **Subject** i federated credential matcher ikke det GitHub sender. Bruker jobben `environment: production`, er subject `repo:<eier>/<repo>:environment:production`. Uten environment på en push til main er det `repo:<eier>/<repo>:ref:refs/heads/main`. Store/små bokstaver må stemme.

## Automated deployment

Når CI er grønn, skal deploy skje **automatisk og likt hver gang**:

- **Til staging/test:** automatisk etter merge til `main`.
- **Til produksjon:** automatisk (Continuous Deployment) eller etter godkjenning (Continuous Delivery), via et **environment** med beskyttelsesregler.
- **Etter hver deploy:** automatiske **smoke tests**, og overvåking av feilrate og responstid.
- **Ved feil:** automatisk eller ett-klikks **rollback**.

```text
 PR ──► CI (lint, test, skann) ──► merge til main
                                       │
                                       ▼
                    Bygg image (tag = commit-SHA) ──► push til ACR
                                       │
                                       ▼
                  Deploy til STAGING ──► smoke test ──► E2E-tester
                                       │
                         [ godkjenning i environment «production» ]
                                       │
                                       ▼
                  Deploy til PROD (canary 10 % → 50 % → 100 %)
                                       │
                         overvåk feilrate/latency ──► ✗ → automatisk rollback
```

## Rollback

**Hva er det?** Å gå tilbake til forrige fungerende versjon når en deploy gir problemer.

**Strategier:**

| Strategi | Hvordan | Fart |
|---|---|---|
| **Redeploy forrige artefakt** | Kjør deploy-jobben med forrige image-tag | Minutter |
| **Bytt tilbake (blue-green)** | Swap slots / flytt trafikk tilbake | Sekunder |
| **Revisjonsbasert** | `kubectl rollout undo`, `helm rollback`, Container Apps: trafikk til forrige revisjon | Sekunder–minutter |
| **Feature flag av** | Slå av funksjonen uten deploy | Sekunder |
| **Roll forward** | Rett feilen raskt og deploy en ny versjon | Avhenger av feilen |
| **GitOps** | `git revert` → agenten synkroniserer | Minutter |

> **Husk:** En rollback-plan som aldri er testet, fungerer sjelden når det gjelder. Øv på rollback i staging. Og husk databasemigreringer (kapittel 8): skriv dem bakoverkompatible, slik at forrige appversjon fortsatt virker etter migreringen.

## Blue-green deployment

**Hva er det?** To identiske produksjonsmiljøer: **blue** (nåværende versjon, får all trafikk) og **green** (ny versjon). Du deployer og tester green, og **bytter all trafikk på én gang**. Rollback = bytt tilbake.

```text
 FØR BYTTE                         ETTER BYTTE                   ROLLBACK
 Brukere ──► BLUE v1 ✓            Brukere ──► GREEN v2 ✓        Brukere ──► BLUE v1 ✓
             GREEN v2 (testes)                BLUE v1 (venter)              GREEN v2 (feilsøkes)
```

**I Azure App Service med deployment slots:**

```yaml
      - name: Deploy til staging-slot
        uses: azure/webapps-deploy@v3
        with:
          app-name: app-minapp-prod
          slot-name: staging
          images: acrminapp.azurecr.io/minapp:${{ github.sha }}

      - name: Smoke test staging
        run: curl --fail --retry 10 --retry-delay 6 https://app-minapp-prod-staging.azurewebsites.net/health

      - name: Swap staging → production
        run: az webapp deployment slot swap -g rg-minapp-prod -n app-minapp-prod --slot staging --target-slot production
```

(Det eksakte vertsnavnet for slots kan variere – bruk `az webapp deployment slot list` for å se det.)

**Fordeler:** nesten null nedetid, øyeblikkelig rollback. **Ulemper:** dobbel kapasitet, og delt database må være kompatibel med begge versjoner.

## Canary deployment

**Hva er det?** Den nye versjonen får først **en liten andel** av trafikken (f.eks. 5–10 %). Ser metrikkene gode ut, øker du gradvis til 100 %. Ser de dårlige ut, flytter du trafikken tilbake – og bare en liten andel brukere ble berørt.

Navnet kommer fra kanarifuglene gruvearbeidere tok med seg: fuglen reagerte på giftig gass før menneskene.

**I Azure Container Apps med revisjoner:**

```bash
# Container-appen kjører i "multiple revisions"-modus
az containerapp revision set-mode -n ca-minapp -g rg-minapp-prod --mode multiple

# Deploy ny versjon som ny revisjon (får 0 % trafikk først hvis vi styrer vektene eksplisitt)
az containerapp update -n ca-minapp -g rg-minapp-prod \
  --image acrminapp.azurecr.io/minapp:v2 --revision-suffix v2

az containerapp revision list -n ca-minapp -g rg-minapp-prod -o table

# 10 % til ny versjon, 90 % til gammel
az containerapp ingress traffic set -n ca-minapp -g rg-minapp-prod \
  --revision-weight ca-minapp--v1=90 ca-minapp--v2=10

# Alt ser bra ut → 100 % til ny
az containerapp ingress traffic set -n ca-minapp -g rg-minapp-prod --revision-weight ca-minapp--v2=100

# Problemer → tilbake
az containerapp ingress traffic set -n ca-minapp -g rg-minapp-prod --revision-weight ca-minapp--v1=100
```

**Andre steder:** Kubernetes med Gateway API-vekter (kapittel 10), Argo Rollouts eller Flagger (automatisk analyse og utrulling), Azure Front Door, App Service (*Testing in production* – prosentvis trafikk til en slot).

**Automatisert canary-analyse:** Verktøy som Argo Rollouts sammenligner feilrate og latency mellom canary og stabil versjon, og ruller tilbake **automatisk** hvis canary er dårligere. Det er målet i modne miljøer.

| | Blue-green | Canary |
|---|---|---|
| Trafikkbytte | Alt på én gang | Gradvis |
| Risiko ved feil | Alle brukere (kort tid) | Få brukere |
| Krav til overvåking | Moderat | Høyt – må kunne sammenligne versjoner |
| Kapasitet | Dobbel under bytte | Litt ekstra |

## Komplett CI/CD-pipeline: fra kode til produksjon

Nå setter vi alt sammen. Vi deployer Flask-appen fra kapittel 9 som container til **Azure Container Apps**, med:

- lint og test på hver PR,
- bygg og push av image til ACR med commit-SHA som tag,
- deploy til **staging** automatisk etter merge,
- smoke test,
- deploy til **produksjon** etter manuell godkjenning, som **canary** (20 % → 100 %),
- OIDC – ingen lagrede Azure-hemmeligheter.

### Arkitektur

```text
 GitHub repo ──PR──► CI (lint, test, Trivy)
      │ merge
      ▼
 GitHub Actions ──OIDC──► Entra ID ──token──► Azure
      │ docker push                              │
      ▼                                          ▼
 ACR (acrminapp) ◄──AcrPull (managed identity)── Container Apps-miljø (cae-minapp)
                                                  ├── ca-minapp-staging
                                                  └── ca-minapp-prod  (revisjoner: v-old 80 % / v-new 20 %)
                                                         │
                                                  Log Analytics / Azure Monitor
```

### Engangsoppsett i Azure

```bash
RG=rg-minapp; LOC=norwayeast; ACR=acrminapp$RANDOM
az group create -n $RG -l $LOC
az acr create -g $RG -n $ACR --sku Basic

# Container Apps-miljø (lager også Log Analytics automatisk hvis du ikke oppgir et)
az containerapp env create -n cae-minapp -g $RG -l $LOC

# Bygg et første image slik at appene kan opprettes
az acr build -r $ACR -t minapp:init .

for APP in ca-minapp-staging ca-minapp-prod; do
  az containerapp create -n $APP -g $RG --environment cae-minapp \
    --image $ACR.azurecr.io/minapp:init \
    --registry-server $ACR.azurecr.io --registry-identity system \
    --target-port 8000 --ingress external \
    --min-replicas 0 --max-replicas 3 \
    --revisions-mode multiple
done
# --registry-identity system: appens managed identity får AcrPull og henter images uten passord
# --min-replicas 0: skalerer til null når ingen bruker den (billig i lab)
```

Sett deretter opp OIDC som beskrevet tidligere i kapitlet, med **to** federated credentials (subject for environment `staging` og `production`) og rollen **Contributor** på `rg-minapp` samt **AcrPush** på registeret.

I GitHub-repoet:

- *Settings → Environments*: lag `staging` og `production`. På `production`: **Required reviewers** (deg selv) og **Deployment branches: main**.
- *Settings → Secrets and variables → Actions → Variables*: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `ACR_NAME`, `RESOURCE_GROUP`.

### Workflowen

`.github/workflows/cicd.yml`:

```yaml
name: CI/CD

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read

env:
  IMAGE: ${{ vars.ACR_NAME }}.azurecr.io/minapp:${{ github.sha }}

jobs:
  # ---------- CI: kjører på alle PR-er og på main ----------
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - run: pip install -r requirements.txt pytest ruff
      - run: ruff check .
      - run: pytest -q

  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Bygg image lokalt for skanning
        run: docker build -t minapp:scan .
      - name: Skann med Trivy (feil ved kritiske sårbarheter)
        uses: aquasecurity/trivy-action@0.28.0    # sjekk siste versjon; lås gjerne til SHA
        with:
          image-ref: minapp:scan
          severity: CRITICAL
          exit-code: "1"
          ignore-unfixed: true

  # ---------- Bygg og push (bare main) ----------
  build:
    if: github.ref == 'refs/heads/main'
    needs: [test, scan]
    runs-on: ubuntu-latest
    environment: staging                       # OIDC-subject: environment:staging
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/checkout@v4
      - uses: azure/login@v2
        with:
          client-id: ${{ vars.AZURE_CLIENT_ID }}
          tenant-id: ${{ vars.AZURE_TENANT_ID }}
          subscription-id: ${{ vars.AZURE_SUBSCRIPTION_ID }}
      - run: az acr login -n ${{ vars.ACR_NAME }}
      - run: |
          docker build -t "$IMAGE" .
          docker push "$IMAGE"

  # ---------- Deploy til staging ----------
  deploy-staging:
    needs: build
    runs-on: ubuntu-latest
    environment: staging
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: azure/login@v2
        with:
          client-id: ${{ vars.AZURE_CLIENT_ID }}
          tenant-id: ${{ vars.AZURE_TENANT_ID }}
          subscription-id: ${{ vars.AZURE_SUBSCRIPTION_ID }}
      - name: Oppdater staging og send all trafikk til ny revisjon
        run: |
          SUFFIX=$(echo ${{ github.sha }} | cut -c1-7)
          az containerapp update -n ca-minapp-staging -g ${{ vars.RESOURCE_GROUP }} \
            --image "$IMAGE" --revision-suffix "s$SUFFIX"
          az containerapp ingress traffic set -n ca-minapp-staging -g ${{ vars.RESOURCE_GROUP }} \
            --revision-weight latest=100
      - name: Smoke test
        run: |
          FQDN=$(az containerapp show -n ca-minapp-staging -g ${{ vars.RESOURCE_GROUP }} \
                 --query properties.configuration.ingress.fqdn -o tsv)
          curl --fail --silent --show-error --retry 10 --retry-delay 6 --retry-all-errors "https://$FQDN/health"

  # ---------- Deploy til produksjon som canary ----------
  deploy-prod:
    needs: deploy-staging
    runs-on: ubuntu-latest
    environment: production                    # krever godkjenning
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: azure/login@v2
        with:
          client-id: ${{ vars.AZURE_CLIENT_ID }}
          tenant-id: ${{ vars.AZURE_TENANT_ID }}
          subscription-id: ${{ vars.AZURE_SUBSCRIPTION_ID }}
      - name: Finn nåværende produksjonsrevisjon
        id: current
        run: |
          OLD=$(az containerapp ingress traffic show -n ca-minapp-prod -g ${{ vars.RESOURCE_GROUP }} \
                --query "[?weight==\`100\`].revisionName | [0]" -o tsv)
          echo "old=$OLD" >> "$GITHUB_OUTPUT"
      - name: Ny revisjon med 20 % trafikk
        id: canary
        run: |
          SUFFIX=p$(echo ${{ github.sha }} | cut -c1-7)
          az containerapp update -n ca-minapp-prod -g ${{ vars.RESOURCE_GROUP }} \
            --image "$IMAGE" --revision-suffix "$SUFFIX"
          NEW="ca-minapp-prod--$SUFFIX"
          echo "new=$NEW" >> "$GITHUB_OUTPUT"
          if [ -n "${{ steps.current.outputs.old }}" ]; then
            az containerapp ingress traffic set -n ca-minapp-prod -g ${{ vars.RESOURCE_GROUP }} \
              --revision-weight "${{ steps.current.outputs.old }}=80" "$NEW=20"
          fi
      - name: Verifiser canary
        run: |
          FQDN=$(az containerapp show -n ca-minapp-prod -g ${{ vars.RESOURCE_GROUP }} \
                 --query properties.configuration.ingress.fqdn -o tsv)
          for i in $(seq 1 30); do
            curl --fail --silent --output /dev/null "https://$FQDN/health" || { echo "Feil ved forsøk $i"; exit 1; }
            sleep 2
          done
          # I et ekte miljø: spør Azure Monitor/Application Insights om feilrate for ny revisjon her.
      - name: Fullfør utrulling (100 %)
        run: |
          az containerapp ingress traffic set -n ca-minapp-prod -g ${{ vars.RESOURCE_GROUP }} \
            --revision-weight "${{ steps.canary.outputs.new }}=100"
      - name: Rollback ved feil
        if: failure() && steps.current.outputs.old != ''
        run: |
          az containerapp ingress traffic set -n ca-minapp-prod -g ${{ vars.RESOURCE_GROUP }} \
            --revision-weight "${{ steps.current.outputs.old }}=100"
```

**Hva skjer, steg for steg:**

1. **PR:** `test` og `scan` kjører. PR-en kan ikke merges før de er grønne (branch ruleset).
2. **Merge til main:** `build` logger inn med OIDC, bygger og pusher `minapp:<sha>`.
3. `deploy-staging` lager en ny revisjon i staging og smoke-tester den.
4. `deploy-prod` venter på **godkjenning** i environment `production`.
5. Ny revisjon får **20 %** trafikk, verifiseres, og får så **100 %**.
6. Feiler noe, flyttes trafikken **automatisk tilbake** til forrige revisjon.

> **Merk:** Første gang (når prod bare har `init`-revisjonen) kan logikken for «gammel revisjon» trenge en manuell start. Sjekk revisjonene med `az containerapp revision list`. Gamle, inaktive revisjoner kan deaktiveres med `az containerapp revision deactivate`.

### Forventet resultat

- En grønn pipeline med fem jobber, synlig under *Actions*.
- To kjørende Container Apps; produksjon viser ny versjon etter godkjenning.
- Full sporbarhet: image-tag = commit-SHA.

### Feilsøking

| Feil | Løsning |
|---|---|
| `AADSTS70021` ved login | Subject i federated credential matcher ikke environment/branch |
| `unauthorized` ved `docker push` | Identiteten mangler **AcrPush** |
| Container App starter ikke / henger i «Activating» | `az containerapp logs show -n <app> -g <rg> --follow`; sjekk `--target-port` (må matche porten appen lytter på) |
| Smoke test feiler | Appen lytter på 127.0.0.1, `/health` mangler, eller kald start (øk retries) |
| Trivy feiler bygget | Oppdater base-image eller avhengigheter; bruk `.trivyignore` kun med begrunnelse |

### Kostnad og opprydding

Container Apps på *Consumption* med `min-replicas 0` har en månedlig gratiskvote og koster lite i lab; ACR Basic har fast dagspris; Log Analytics koster per GB. Rydd opp:

```bash
az group delete -n rg-minapp --yes --no-wait
az ad app delete --id <APP_ID>      # fjern app-registreringen for OIDC
```

### På GitHub og CV

Lag en README med arkitekturdiagram, pipeline-badge og en kort forklaring av OIDC, canary og rollback. CV-linje: *«Bygget en CI/CD-pipeline i GitHub Actions med testing, sårbarhetsskanning, OIDC-autentisering mot Azure (ingen lagrede hemmeligheter), deploy til Azure Container Apps med godkjenning, canary-utrulling og automatisk rollback.»*

## Kapitteloppsummering

- En pipeline automatiserer veien fra commit til produksjon; den skal være rask, pålitelig, sikker og sporbar.
- Testpyramiden: mange enhetstester, færre integrasjonstester, få E2E-tester. Smoke tests etter hver deploy.
- GitHub Actions: workflows → jobs → steps, med matrix, services, cache, environments og reusable workflows.
- Azure Pipelines og Jenkins bygger på de samme prinsippene.
- Bygg artefaktet én gang, versjoner det med commit-SHA, og promoter det gjennom miljøene.
- Hemmeligheter: best er ingen – bruk OIDC til Azure og managed identity for appen.
- Rollback må være planlagt og testet; blue-green bytter alt på én gang, canary gradvis.

## Øvingsoppgaver

1. Legg til en matrix i CI-workflowen som tester på både `ubuntu-latest` og `windows-latest`.
2. Lag en reusable workflow for Python-CI og kall den fra to forskjellige repoer.
3. Sett opp OIDC fra GitHub Actions til Azure og kjør `az group list` i en workflow – uten noen hemmeligheter.
4. Implementer blue-green med App Service deployment slots (krever Standard-plan – husk kostnad og opprydding).
5. Lag en workflow med `on: schedule` som kjører uptime-skriptet fra kapittel 4 hver time og lager en GitHub Issue hvis noe feiler.
6. Oversett Jenkinsfile-eksemplet i dette kapitlet til GitHub Actions.

## Quiz

1. Hva betyr «bygg én gang, deploy mange ganger»?
2. Hvorfor bør tester ligge tidlig i pipelinen?
3. Hva gjør `needs:` og `strategy.matrix` i GitHub Actions?
4. Hvorfor bør tredjeparts actions låses til en full commit-SHA?
5. Hva er fordelen med OIDC sammenlignet med en lagret klienthemmelighet?
6. Hvilken permission må workflowen ha for å bruke OIDC?
7. Hva er et environment i GitHub Actions, og hvorfor bruke det?
8. Hva er forskjellen på blue-green og canary?
9. Hva er en smoke test?
10. Nevn tre måter å gjøre rollback på.

### Fasit

1. Artefaktet (f.eks. container-imaget) bygges én gang i CI, og nøyaktig samme artefakt deployes til alle miljøer. Bare konfigurasjonen endres. Det sikrer at det som ble testet, er det som kjører i produksjon.
2. For å gi rask tilbakemelding og stoppe feil før man bruker tid og ressurser på bygging og deploy.
3. `needs:` gjør at en jobb venter på andre jobber. `strategy.matrix` kjører samme jobb flere ganger med ulike parametere (f.eks. versjoner eller OS).
4. En tag kan flyttes til ny (potensielt ondsinnet) kode; en commit-SHA er uforanderlig.
5. Ingen langlivet hemmelighet som kan lekke eller må roteres; tokenet er kortlevd og bundet til et bestemt repo/branch/environment.
6. `id-token: write`.
7. Et deploymål (f.eks. production) med beskyttelsesregler: godkjenninger, begrensning til bestemte brancher, og egne hemmeligheter/variabler. Gir kontroll og sporbarhet for deploy.
8. **Blue-green** bytter all trafikk fra gammel til ny versjon på én gang (med mulighet til å bytte tilbake). **Canary** sender gradvis økende andel trafikk til ny versjon.
9. En rask, enkel test rett etter deploy som sjekker at tjenesten lever og svarer (f.eks. `GET /health` gir 200).
10. Redeploy forrige artefakt, bytt tilbake slot/trafikk (blue-green), `kubectl rollout undo` / `helm rollback`, flytt trafikk til forrige revisjon, slå av feature flag, `git revert` i GitOps.
