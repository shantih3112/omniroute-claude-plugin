## Prosjekt 7 – CI/CD-pipeline til Azure App Service

**Læringsmål:** Bygge en komplett pipeline for en Python-API: lint, test, sikkerhetsskanning, build, deploy til staging og produksjon med godkjenning – med OIDC og managed identity.

**Forutsetninger:** Kapittel 4, 7.2 og 12.

**Arkitektur:**

```text
 PR ──► CI: ruff · pytest · pip-audit · CodeQL
 merge ──► build: zip-artefakt (én gang)
       ──► deploy staging  (app-p7-staging, F1/B1)  ── smoke test /health
       ──► [godkjenning: environment «production»]
       ──► deploy prod     (app-p7-prod)            ── smoke test /health
 Begge apper: managed identity → Key Vault (Key Vault-referanser i app settings)
              Application Insights (OpenTelemetry)
 GitHub ──OIDC──► Entra ID (federated credentials for staging og production)
```

**Verktøy:** GitHub Actions, Azure CLI, Python (Flask/FastAPI), Key Vault, Application Insights.

**Tid:** 6–8 timer. **Kostnad:** To apper på **F1** er gratis (Free-planen har begrensninger, f.eks. ingen deployment slots og begrenset CPU-tid). B1 koster litt per time. Key Vault og Application Insights koster lite ved lav bruk.

**Steg for steg:**

1. **Appen:** En liten Flask-API med `/`, `/health` og `/api/hilsen?navn=`. Legg til `azure-monitor-opentelemetry` (kapittel 13) og tester med `pytest`.
2. **Infrastruktur (CLI eller Bicep fra kapittel 7.4):** ressursgruppe, App Service Plan (Linux), to web-apper (`-staging`, `-prod`), Key Vault, Log Analytics + Application Insights. Slå på managed identity på begge appene, gi dem *Key Vault Secrets User*, og sett app setting `API_KEY=@Microsoft.KeyVault(VaultName=...;SecretName=ApiKey)`.
3. **OIDC:** App-registrering med to federated credentials (`environment:staging` og `environment:production`), rollen *Website Contributor* (eller *Contributor*) på ressursgruppen.
4. **GitHub:** environments `staging` og `production` (med required reviewer), variabler `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`.
5. **Workflow** `.github/workflows/cicd.yml`:

    ```yaml
    name: CI/CD
    on:
      pull_request:
      push:
        branches: [main]
    permissions:
      contents: read

    jobs:
      ci:
        runs-on: ubuntu-latest
        steps:
          - uses: actions/checkout@v4
          - uses: actions/setup-python@v5
            with: { python-version: "3.12", cache: pip }
          - run: pip install -r requirements.txt ruff pytest pip-audit
          - run: ruff check .
          - run: pytest -q
          - run: pip-audit -r requirements.txt

      build:
        if: github.ref == 'refs/heads/main'
        needs: ci
        runs-on: ubuntu-latest
        steps:
          - uses: actions/checkout@v4
          - run: zip -r app.zip . -x '.git/*' '.github/*' 'tests/*'
          - uses: actions/upload-artifact@v4
            with: { name: app, path: app.zip }

      deploy-staging:
        needs: build
        runs-on: ubuntu-latest
        environment: staging
        permissions:
          id-token: write
          contents: read
        steps:
          - uses: actions/download-artifact@v4
            with: { name: app }
          - uses: azure/login@v2
            with:
              client-id: ${{ vars.AZURE_CLIENT_ID }}
              tenant-id: ${{ vars.AZURE_TENANT_ID }}
              subscription-id: ${{ vars.AZURE_SUBSCRIPTION_ID }}
          - uses: azure/webapps-deploy@v3
            with:
              app-name: app-p7-staging
              package: app.zip
          - name: Smoke test
            run: curl --fail --retry 10 --retry-delay 10 --retry-all-errors https://app-p7-staging.azurewebsites.net/health

      deploy-prod:
        needs: deploy-staging                    # bare etter vellykket staging
        runs-on: ubuntu-latest
        environment: production                  # krever godkjenning
        permissions:
          id-token: write
          contents: read
        steps:
          - uses: actions/download-artifact@v4
            with: { name: app }                  # SAMME artefakt som i staging
          - uses: azure/login@v2
            with:
              client-id: ${{ vars.AZURE_CLIENT_ID }}
              tenant-id: ${{ vars.AZURE_TENANT_ID }}
              subscription-id: ${{ vars.AZURE_SUBSCRIPTION_ID }}
          - uses: azure/webapps-deploy@v3
            with:
              app-name: app-p7-prod
              package: app.zip
          - name: Smoke test
            run: curl --fail --retry 10 --retry-delay 10 --retry-all-errors https://app-p7-prod.azurewebsites.net/health
    ```

    (App Service bygger Python-appen ved deploy når app setting `SCM_DO_BUILD_DURING_DEPLOYMENT=true` er satt. Web-app-navn må være globalt unike – legg til et eget suffiks.)

6. **Branch ruleset:** krev at `ci` er grønn før merge.
7. **Test hele flyten:** lag en PR som bryter en test (rød), fiks den (grønn), merge, se staging deploye, godkjenn produksjon.
8. **Rollback-øvelse:** deploy en versjon som feiler smoke test i staging – bekreft at produksjon aldri ble rørt. Dokumenter hvordan du redeployer forrige artefakt (kjør workflowen på nytt fra en tidligere commit med *Re-run jobs*).

**Forventet resultat:** Hver merge går automatisk til staging; produksjon krever godkjenning; ingen hemmeligheter lagret i GitHub; telemetri i Application Insights.

**Vanlige feil:**

| Problem | Løsning |
|---|---|
| Appen starter ikke («Application Error») | `az webapp log tail`; sjekk oppstartskommando (`gunicorn --bind=0.0.0.0 app:app`) under *Configuration → Startup Command* |
| Key Vault-referansen viser «error» i portalen | Mangler RBAC-rolle, eller identiteten er ikke slått på |
| OIDC-feil | Subject må matche `environment:<navn>` nøyaktig |

**Opprydding:** `az group delete -n rg-prosjekt7 --yes`, slett app-registreringen, `az keyvault purge` hvis du vil gjenbruke navnet.

**På CV:** *«Bygget CI/CD med GitHub Actions for Python-API: linting, tester, avhengighetsskanning, artefakt bygget én gang, OIDC-innlogging mot Azure, staging med smoke tests og godkjenningsstyrt produksjonsdeploy til Azure App Service, hemmeligheter i Key Vault via managed identity.»*

## Prosjekt 8 – Azure-infrastruktur med Terraform og pipeline

**Læringsmål:** Bygge et realistisk Azure-miljø med Terraform-moduler, remote state, flere miljøer, og en pipeline med `plan` på PR og `apply` etter merge.

**Forutsetninger:** Kapittel 11 og 12.

**Arkitektur:**

```text
 infra-repo
 ├── modules/
 │    ├── network/   (VNet, subnett for app og data, NSG-er)
 │    ├── webapp/    (App Service Plan, Linux Web App med managed identity og VNet-integrasjon)
 │    ├── keyvault/  (Key Vault, RBAC, private endpoint)
 │    └── monitoring/ (Log Analytics, Application Insights, diagnostic settings)
 └── envs/
      ├── dev/  (backend: key = dev.tfstate)
      └── prod/ (backend: key = prod.tfstate)

 PR ──► GitHub Actions: fmt · validate · Checkov/Trivy · plan (som PR-kommentar)
 merge ──► apply dev automatisk ──► [godkjenning] ──► apply prod
 State: Azure Blob (rg-tfstate), låsing, versjonering, RBAC
```

**Tid:** 8–12 timer. **Kostnad:** Lav hvis du bruker F1/B1 og sletter etterpå. Private endpoints faktureres per time – kan droppes i dev for å spare.

**Steg for steg:**

1. **Remote state** som i kapittel 11 (`rg-tfstate`, ZRS, versjonering, `CanNotDelete`-lås).
2. **Moduler:** Start med `network` og `monitoring`. Hver modul har `variables.tf`, `main.tf`, `outputs.tf` og en kort `README.md`. Bruk `for_each` for subnett.
3. **Miljøer:** `envs/dev/main.tf` kaller modulene med dev-verdier; `envs/prod` med prod-verdier (større SKU, `purge_protection_enabled = true`, ZRS).
4. **Lokal kjøring først:** `terraform init/plan/apply` i `envs/dev`. Verifiser i portalen.
5. **Pipeline** `.github/workflows/terraform.yml`:

    ```yaml
    name: Terraform
    on:
      pull_request:
        paths: ["infra/**"]
      push:
        branches: [main]
        paths: ["infra/**"]

    permissions:
      id-token: write
      contents: read
      pull-requests: write          # for å kommentere planen på PR-en

    env:
      ARM_CLIENT_ID: ${{ vars.AZURE_CLIENT_ID }}
      ARM_TENANT_ID: ${{ vars.AZURE_TENANT_ID }}
      ARM_SUBSCRIPTION_ID: ${{ vars.AZURE_SUBSCRIPTION_ID }}
      ARM_USE_OIDC: "true"          # Terraform azurerm bruker GitHub OIDC-token
      TF_VAR_subscription_id: ${{ vars.AZURE_SUBSCRIPTION_ID }}

    jobs:
      plan:
        runs-on: ubuntu-latest
        environment: dev
        defaults:
          run:
            working-directory: infra/envs/dev
        steps:
          - uses: actions/checkout@v4
          - uses: hashicorp/setup-terraform@v3
          - run: terraform fmt -check -recursive ../..
          - run: terraform init -input=false
          - run: terraform validate
          - run: terraform plan -input=false -no-color -out=tfplan | tee plan.txt
          - name: Kommenter planen på PR
            if: github.event_name == 'pull_request'
            uses: actions/github-script@v7
            with:
              script: |
                const fs = require('fs');
                const plan = fs.readFileSync('infra/envs/dev/plan.txt', 'utf8').slice(-60000);
                await github.rest.issues.createComment({
                  owner: context.repo.owner, repo: context.repo.repo,
                  issue_number: context.issue.number,
                  body: "### Terraform plan (dev)\n```\n" + plan + "\n```"
                });
          - uses: actions/upload-artifact@v4
            if: github.ref == 'refs/heads/main'
            with: { name: tfplan-dev, path: infra/envs/dev/tfplan }

      apply-dev:
        if: github.ref == 'refs/heads/main'
        needs: plan
        runs-on: ubuntu-latest
        environment: dev
        defaults:
          run:
            working-directory: infra/envs/dev
        steps:
          - uses: actions/checkout@v4
          - uses: hashicorp/setup-terraform@v3
          - uses: actions/download-artifact@v4
            with: { name: tfplan-dev, path: infra/envs/dev }
          - run: terraform init -input=false
          - run: terraform apply -input=false tfplan     # nøyaktig den planen som ble vist
    ```

    Lag tilsvarende `plan-prod` og `apply-prod` (med environment `prod` og required reviewer). Federated credentials trengs for `environment:dev` og `environment:prod`, og identiteten trenger *Contributor* på målabonnementet/-gruppene og *Storage Blob Data Contributor* på state-kontoen.

6. **Sikkerhetsskanning:** legg til `bridgecrewio/checkov-action` eller `aquasecurity/trivy-action` med `scan-type: config` på `infra/`.
7. **Drift-deteksjon:** en planlagt workflow (`schedule`) som kjører `terraform plan -detailed-exitcode` hver natt og lager en issue hvis exit-koden er 2 (endringer funnet).
8. **Dokumenter** arkitekturen og hvordan man legger til et nytt miljø.

**Forventet resultat:** Infrastrukturendringer går kun via PR, planen vises som kommentar, dev oppdateres automatisk, prod etter godkjenning, og drift oppdages automatisk.

**Vanlige feil:**

| Problem | Løsning |
|---|---|
| `Error acquiring the state lock` | En annen kjøring holder låsen, eller en kjøring krasjet. Vent, eller `terraform force-unlock <id>` hvis du er sikker |
| `AuthorizationFailed` på state | Identiteten mangler *Storage Blob Data Contributor* |
| Planen i apply avviker fra PR-planen | Noe endret seg mellom plan og apply – derfor brukes lagret `tfplan` |
| Globale navn kolliderer | Bruk `random_string`-suffiks eller `uniqueString` |

**Opprydding:** `terraform destroy` i `envs/prod` og `envs/dev` (eller via en manuell workflow), deretter `rg-tfstate` til slutt.

**På CV:** *«Designet modulær Terraform-kode for Azure (nettverk, App Service, Key Vault, overvåking) med remote state i Azure Storage, flere miljøer, og GitHub Actions-pipeline med plan på pull requests, sikkerhetsskanning, godkjenningsstyrt apply via OIDC og nattlig drift-deteksjon.»*

## Prosjekt 9 – Deploy en app på Kubernetes med Helm

**Læringsmål:** Deploye en flerkomponent-app på Kubernetes med Helm: deployment, service, ingress, config, secrets, probes, ressursgrenser, HPA og NetworkPolicy – lokalt først, deretter (valgfritt) i AKS.

**Forutsetninger:** Kapittel 9 og 10.

**Arkitektur:**

```text
 kind-cluster (lokalt)  /  AKS (valgfritt)
 └── namespace: butikk
      ├── Ingress / HTTPRoute  butikk.localhost → web
      ├── Deployment web (2–5 replikaer, HPA på CPU) ── Service web (ClusterIP)
      │     env fra ConfigMap + Secret, readiness/liveness, requests/limits
      ├── StatefulSet / Deployment postgres + PVC ── Service db
      └── NetworkPolicy: bare web → db:5432
 Pakket som Helm chart «butikk» med values-dev.yaml og values-prod.yaml
```

**Verktøy:** Docker, kind, kubectl, Helm.

**Tid:** 8–12 timer. **Kostnad:** Gratis lokalt. I AKS: noder faktureres – stopp/slett samme dag.

**Steg for steg:**

1. **Cluster med ingress-støtte** (kind):

    ```yaml
    # kind-config.yaml
    kind: Cluster
    apiVersion: kind.x-k8s.io/v1alpha4
    nodes:
      - role: control-plane
        extraPortMappings:
          - containerPort: 80
            hostPort: 80
    ```

    ```bash
    kind create cluster --name butikk --config kind-config.yaml
    ```

    Installer en ingress- eller Gateway API-kontroller etter dokumentasjonen til kontrolleren du velger (kind-dokumentasjonen har en egen side om ingress). Se merknaden i kapittel 10 om ingress-nginx sin pensjonering, og velg et aktivt vedlikeholdt alternativ.

2. **Last imaget inn i kind** (slipper register lokalt):

    ```bash
    docker build -t butikk-web:1.0 .
    kind load docker-image butikk-web:1.0 --name butikk
    ```

3. **Skriv manifestene først som ren YAML** (deployment, service, configmap, secret, postgres med PVC, ingress) og test med `kubectl apply -f k8s/ -n butikk`. Bruk eksemplene i kapittel 10.
4. **Gjør dem om til en Helm chart:** `helm create butikk`, slett eksempelmalene du ikke trenger, flytt inn dine manifester og erstatt verdier med `{{ .Values... }}`.
5. **To miljøer:**

    ```bash
    helm upgrade --install butikk ./butikk -n butikk-dev  --create-namespace -f values-dev.yaml
    helm upgrade --install butikk ./butikk -n butikk-prod --create-namespace -f values-prod.yaml
    ```

6. **Robusthet:** Slett en web-pod og se at den erstattes. Sett en feil i readinessProbe og se at podene ikke får trafikk. Rull ut et image som ikke finnes og gjør `helm rollback`.
7. **HPA:** installer metrics-server i kind (kind trenger flagget `--kubelet-insecure-tls` – se metrics-server-dokumentasjonen), lag HPA, generer last og se skaleringen med `kubectl get hpa -w`.
8. **NetworkPolicy:** kind sin standard-CNI håndhever ikke NetworkPolicy; installer Calico eller Cilium i kind for å teste, eller test i AKS med nettverkspolicy slått på.
9. **CI:** en workflow som kjører `helm lint` og `kubeconform` (validerer manifester) på hver PR.
10. **Valgfritt – AKS:** push imaget til ACR, `az aks create ... --attach-acr --enable-app-routing`, sett `ingressClassName: webapprouting.kubernetes.azure.com` i `values-aks.yaml`, og installer chart-en. **Slett clusteret etterpå.**

**Forventet resultat:** `http://butikk.localhost` viser appen; data overlever pod-restart; HPA skalerer; rollback virker.

**Vanlige feil:** Se feilsøkingstabellen i kapittel 10. Spesielt: `ImagePullBackOff` i kind betyr ofte at du glemte `kind load docker-image`, eller at `imagePullPolicy: Always` får kind til å prøve et register – bruk `IfNotPresent` lokalt.

**Opprydding:** `kind delete cluster --name butikk`. I AKS: `az group delete`.

**På CV:** *«Pakket en webapp med PostgreSQL som Helm chart for Kubernetes med probes, ressursgrenser, HPA, persistent lagring, NetworkPolicy og separate verdier per miljø; validert i CI med helm lint og kubeconform; deployet til AKS.»*

## Prosjekt 10 – Komplett Cloud/DevOps-plattform

**Læringsmål:** Kombinere alt: IaC, containere, CI/CD, sikkerhet, overvåking, kostnadsstyring og dokumentasjon i én helhetlig plattform – sluttprosjektet ditt.

**Forutsetninger:** Hele boken, særlig prosjekt 5, 7, 8 og 9.

**Arkitektur (målbilde):**

```text
                         GitHub (app-repo + infra-repo)
                  PR: lint · test · CodeQL · Trivy · Checkov · terraform plan
                  main: build image (SHA) → ACR → deploy staging → [godkjenning] → prod (canary)
                                 │ OIDC (ingen lagrede hemmeligheter)
 ┌────────────────────────────────┼─────────────────────────────────────────────────────────┐
 │ Azure – alt laget med Terraform (moduler, remote state, dev + prod)                      │
 │                                                                                          │
 │  Brukere ─► Container Apps (ingress, HTTPS, revisjoner for canary)                       │
 │                 │ managed identity                                                       │
 │        ┌────────┼──────────────┬───────────────────┐                                     │
 │        ▼        ▼              ▼                   ▼                                     │
 │   Key Vault  Azure Database   Blob Storage     ACR (AcrPull)                             │
 │   (RBAC)     for PostgreSQL   (opplastinger)                                             │
 │              (Entra-auth)                                                                │
 │  ── VNet med subnett for Container Apps-miljø og private endpoints (prod) ──             │
 │                                                                                          │
 │  Observability: Log Analytics · Application Insights (OTel) · availability test          │
 │                 alerts (5xx-rate, latency p95, tilgjengelighet) → action group (e-post)  │
 │  Styring: Azure Policy (tillatte regioner, påkrevde tags, ingen offentlig blob-tilgang)  │
 │           budsjett med varsler · tags på alt · ressurslås på prod-data                   │
 │  Robusthet: PITR på database · soft delete/versjonering på blob · IaC for gjenoppbygging │
 └──────────────────────────────────────────────────────────────────────────────────────────┘
```

**Verktøy:** Alt fra boken.

**Tid:** 25–40 timer, gjerne fordelt over 3–4 uker. **Kostnad:** Lav–moderat. Hold dev og prod små (Container Apps med min-replicas 0, minste databasenivå, ingen private endpoints i dev). **Lag et kostnadsestimat i Pricing Calculator før du starter**, og slett alt når du har tatt opp demo-videoen.

**Faser:**

**Fase 1 – Design (2–3 timer).**
- Skriv en kort **arkitekturbeslutningslogg** (ADR – *Architecture Decision Record*): hvorfor Container Apps og ikke AKS? Hvorfor PostgreSQL Flexible Server? Hvorfor Terraform?
- Definer **SLO-er**: f.eks. 99,5 % vellykkede forespørsler og p95 < 500 ms over 30 dager.
- Tegn arkitekturen.

**Fase 2 – Grunnmur med IaC (6–10 timer).**
- Remote state, moduler for nettverk, overvåking, Key Vault, database, lagring, ACR og Container Apps.
- Azure Policy-tildelinger og budsjett som Terraform-ressurser (`azurerm_resource_group_policy_assignment`, `azurerm_consumption_budget_resource_group`).
- Tags på alt via `locals`.

**Fase 3 – Applikasjonen (4–6 timer).**
- En enkel, men ekte app (f.eks. «lenkesamling», «treningslogg» eller «utstyrsutlån») med API, database og filopplasting til Blob.
- Managed identity mot database (Entra-autentisering), Blob og Key Vault – **null passord i konfigurasjonen**.
- OpenTelemetry for traces, metrikker og strukturerte logger.

**Fase 4 – CI/CD (5–8 timer).**
- App-pipeline fra kapittel 12 (canary + automatisk rollback).
- Infra-pipeline fra prosjekt 8.
- Sikkerhetsskanning: CodeQL, Dependabot, Trivy (image og IaC), secret scanning med push protection.

**Fase 5 – Observability og drift (4–6 timer).**
- Dashboard (Azure Workbook eller Managed Grafana) med RED-metrikker og SLO-status.
- Varsler: 5xx-rate, p95-latency, availability test, budsjett.
- **Runbooks** for de tre mest sannsynlige hendelsene (database utilgjengelig, høy feilrate etter deploy, kostnadsvarsel).

**Fase 6 – Robusthet og sikkerhet (3–5 timer).**
- Test **point-in-time restore** av databasen til en ny server, og dokumenter tiden (din faktiske RTO).
- Test **gjenoppbygging**: slett dev-miljøet og bygg det opp igjen fra Terraform. Hvor lang tid tok det?
- Gå gjennom Defender for Cloud-anbefalingene og fiks det du kan.

**Fase 7 – Dokumentasjon og presentasjon (3–4 timer).**
- README med arkitekturdiagram, ADR-er, SLO-er, hvordan kjøre det, kostnadsestimat, og «Hva jeg lærte».
- En **3–5 minutters demovideo**: arkitektur, en PR gjennom pipelinen, canary, et varsel som utløses, og en rollback.
- Rydd opp og skriv i README at miljøet er slettet for å spare kostnader (videoen viser at det fungerte).

**Forventet resultat:** En plattform du kan forklare fra ende til annen i et intervju – med kode, pipeline, overvåking, sikkerhet, kostnadskontroll og dokumentert gjenoppretting.

**Vanlige feil:**

- **For stort omfang.** Start med en «walking skeleton»: minste versjon som går hele veien fra commit til prod. Bygg ut deretter.
- **Manuelle endringer** i portalen som ikke kommer inn i Terraform.
- **Glemte kostnader**: databaser og private endpoints koster per time selv uten trafikk.

**Feilsøking:** Bruk metoden i kapittel 13 – og noter hvert problem du løser i en `TROUBLESHOOTING.md`. Den filen er gull i intervjuer.

**Opprydding:** `terraform destroy` for prod og dev, slett state-gruppen, slett app-registreringer, purge Key Vault, og sjekk *Cost Management* et par dager senere for å bekrefte at forbruket er null.

**På GitHub og CV:** Dette er porteføljens hovedprosjekt. *«Designet og bygget en komplett Azure-plattform med Terraform (moduler, remote state, flere miljøer), containerisert Python-applikasjon på Azure Container Apps, CI/CD med GitHub Actions (OIDC, sikkerhetsskanning, canary og automatisk rollback), passordløs tilgang med managed identity, observability med OpenTelemetry/Application Insights og SLO-baserte varsler, Azure Policy, budsjettstyring og testet gjenoppretting (PITR og full gjenoppbygging fra kode).»*

## Prosjekt 11 – MLOps: modell-API med CI/CD og overvåking

**Læringsmål:** Ta en ML-modell fra notebook til produksjon: reproduserbar trening, sporing med MLflow, modell som API i en container, CI/CD med evaluering som kvalitetsport, og overvåking av både drift og modellkvalitet.

**Forutsetninger:** Kapittel 4, 9, 12 og 14.

**Arkitektur:**

```text
 data/ (versjonert datasett, f.eks. åpent boligprisdatasett)
   │
 train.py ──► MLflow tracking (parametere, MAE) ──► modell.joblib + metrics.json
   │
 CI (GitHub Actions):
   1. test kode (pytest)
   2. tren modellen (liten nok til å kjøre i CI)
   3. KVALITETSPORT: MAE ≤ terskel OG ikke dårligere enn forrige prod-modell → ellers rødt
   4. bygg image (serve.py + modell) tag = SHA → ACR / ghcr.io
   5. deploy til Container Apps (canary 20 % → 100 %)
 serve.py (FastAPI): /predict, /health, /metrics  ── logger input-statistikk for drift
 Overvåking: Application Insights (latency, feil) + daglig drift-sjekk (jobb som sammenligner
             fordelingen av input mot treningsdata og varsler ved avvik)
```

**Verktøy:** Python (pandas, scikit-learn, MLflow, FastAPI), Docker, GitHub Actions, Azure Container Apps (eller lokalt).

**Tid:** 10–15 timer. **Kostnad:** Lav (Container Apps med min-replicas 0). Kan gjøres helt lokalt.

**Steg for steg:**

1. **Velg et åpent, lite datasett** (f.eks. et tabulært boligpris- eller diabetesdatasett fra scikit-learn). Lagre en fast kopi i repoet (eller i Blob med versjonsnummer) og en `DATA_VERSION`.
2. **`train.py`** – les data, del i trening/test med fast `random_state`, tren, beregn MAE, logg til MLflow, lagre `modell.joblib` og `metrics.json`.
3. **Kvalitetsport** `evaluate.py`:

    ```python
    import json, sys
    ny = json.load(open("metrics.json"))["mae"]
    terskel = 55.0                                   # akseptabel feil (velg ut fra datasettet)
    forrige = json.load(open("prod_metrics.json"))["mae"] if __import__("os").path.exists("prod_metrics.json") else None
    print(f"Ny MAE: {ny:.2f}  Forrige: {forrige}")
    if ny > terskel or (forrige is not None and ny > forrige * 1.02):   # maks 2 % dårligere
        print("Modellen besto IKKE kvalitetsporten"); sys.exit(1)
    print("Kvalitetsport OK")
    ```

4. **`serve.py`** – FastAPI fra kapittel 14 med `/predict`, `/health` (inkl. modellversjon) og Prometheus-metrikker (`prometheus-client`) for antall prediksjoner og latency. Logg et utvalg av input-verdier (ikke personopplysninger) for drift-analyse.
5. **Dockerfile** som kopierer inn `serve.py` og den **trente** modellen.
6. **Workflow:** test → train → evaluate → build → deploy (canary som i kapittel 12). Last opp `metrics.json` og MLflow-kjøringen som artefakter.
7. **Drift-sjekk:** et skript som sammenligner gjennomsnitt og standardavvik for hver input-variabel siste døgn mot treningsdataene, og feiler (→ varsel/issue) hvis avviket er stort. Kjør det med `schedule` i GitHub Actions.
8. **Simuler drift:** send forespørsler med systematisk forskjøvne verdier og se at drift-sjekken slår ut. Tren på nytt med «nye» data og se den nye modellen gå gjennom porten.

**Forventet resultat:** Hver endring i kode **eller data** gir en ny, evaluert, sporbar modellversjon; dårligere modeller stoppes automatisk; drift oppdages.

**Vanlige feil:** Ikke-reproduserbar trening (glemt `random_state`, ulike bibliotekversjoner – lås dem i `requirements.txt`); modellfil som er for stor for Git (bruk Git LFS, Blob eller MLflow-artefakter); trening og servering bruker forskjellig forbehandling (*training/serving skew*) – del koden for forbehandling mellom dem.

**Opprydding:** Slett ressursgruppen; `mlflow`-data lokalt kan slettes.

**På CV:** *«Bygget en MLOps-pipeline: reproduserbar trening sporet med MLflow, automatisk kvalitetsport som stopper dårligere modeller, modell servert som FastAPI-container med canary-utrulling via GitHub Actions, og overvåking av latency og data drift.»*

## Prosjekt 12 – Observability og hendelsesøvelse (game day)

**Læringsmål:** Sette opp full observability for en mikrotjeneste-app lokalt (metrikker, logger, traces), definere SLO-er og varsler, og gjennomføre en kontrollert hendelsesøvelse med postmortem.

**Forutsetninger:** Kapittel 8, 9 og 13.

**Arkitektur:**

```text
 Docker Compose:
   frontend (Flask) ──HTTP──► api (FastAPI) ──► postgres
        │ OpenTelemetry SDK          │ OTel SDK
        └────────────┬───────────────┘
                     ▼ OTLP
            OpenTelemetry Collector
            ├─► Prometheus (metrikker) ──► Alertmanager (varsler → webhook/e-post)
            ├─► Grafana Tempo eller Jaeger (traces)
            └─► Grafana Loki (logger)
                     ▼
                  Grafana (dashboards: RED, SLO, traces ↔ logger)
```

**Verktøy:** Docker Compose, OpenTelemetry Collector, Prometheus, Grafana, Loki, Tempo/Jaeger.

**Tid:** 8–10 timer. **Kostnad:** Gratis (lokalt).

**Steg for steg:**

1. **To tjenester** som kaller hverandre (frontend → api → database). Instrumenter begge med OpenTelemetry (auto-instrumentering for Flask/FastAPI/requests/psycopg) og strukturerte JSON-logger med `trace_id`.
2. **Compose-oppsett** med Collector, Prometheus, Grafana, Loki og Tempo (eller Jaeger). Grafana har ferdige eksempeloppsett for denne stacken i dokumentasjonen sin – bruk dem som utgangspunkt og lås image-versjoner.
3. **Dashboards:** RED per tjeneste, p95/p99-latency, feilrate, databasekall per forespørsel.
4. **SLO og varsler:** SLO 99 % vellykkede forespørsler over 1 time (kort periode for øvelsen). Lag en Prometheus-regel for *burn rate* (hvor fort error budget brukes) og en for p95 > 1 s.
5. **Feilinjeksjon:** legg inn miljøvariabler i api-tjenesten: `FEILRATE` (andel forespørsler som gir 500) og `FORSINKELSE_MS`. Skriv en enkel lastgenerator (`while true; do curl ...; done` eller k6).
6. **Game day** – med en medstudent som «angriper»:
    - Medstudenten endrer i hemmelighet én ting: øker `FORSINKELSE_MS`, setter `FEILRATE=0.2`, stopper databasen, eller fyller disken i en container.
    - Du får bare varselet, og skal finne og løse problemet med dashboards, traces og logger. Noter tidspunkter: *oppdaget*, *diagnostisert*, *løst* (MTTD/MTTR).
    - Bytt roller.
7. **Postmortem:** skriv en blameless postmortem (mal i kapittel 8) for hvert scenario. Hva gjorde det lett/vanskelig å finne feilen? Hvilket dashboard/varsel manglet? Implementer minst én forbedring.

**Forventet resultat:** Du kan følge én forespørsel fra frontend til database i en trace, hoppe fra trace til tilhørende logger, se SLO-status, og du har praktisk erfaring med hendelseshåndtering.

**Vanlige feil:** Traces henger ikke sammen mellom tjenester (trace-kontekst propageres ikke – bruk OTel-instrumentering av HTTP-klienten); for mange varsler (juster terskler og `for:`); metrikker med for mange unike labelverdier (*high cardinality*, f.eks. bruker-ID som label) som sprenger Prometheus.

**Opprydding:** `docker compose down -v`.

**På CV:** *«Implementerte observability for mikrotjenester med OpenTelemetry, Prometheus, Loki, Tempo og Grafana; definerte SLO-er med burn rate-varsler; gjennomførte hendelsesøvelser (game days) med blameless postmortems.»*

## Slik presenterer du prosjektene

**På GitHub:**

- Fest (*pin*) de 4–6 beste repoene på profilen.
- Hver README: problem, arkitektur, teknologier, hvordan kjøre, hva du lærte, videre arbeid.
- Grønne CI-badges. Ryddig historikk med gode commit-meldinger.
- Ingen hemmeligheter, ingen `node_modules`/`.venv`, ingen state-filer.

**På CV-en (prosjektseksjon):**

```text
 Azure DevOps-plattform (sluttprosjekt)                         github.com/<deg>/plattform
 Terraform · Azure Container Apps · PostgreSQL · Key Vault · GitHub Actions · OpenTelemetry
 • Bygget hele infrastrukturen som kode med moduler og remote state for dev og prod
 • CI/CD med OIDC (ingen lagrede hemmeligheter), sikkerhetsskanning, canary og automatisk rollback
 • SLO-basert overvåking og varsling; testet gjenoppretting (PITR) og full gjenoppbygging på 18 min
```

Tallfest der du kan (byggetid, image-størrelse redusert fra X til Y MB, gjenoppbygging på Z minutter).

**I intervju – STAR-metoden:** *Situation* (hva var problemet), *Task* (hva skulle du oppnå), *Action* (hva gjorde **du**, konkret), *Result* (hva ble resultatet, og hva lærte du). Ha 2–3 historier klare fra prosjektene – særlig én om et vanskelig problem du feilsøkte.
