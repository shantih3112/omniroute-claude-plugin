## 7.4 Azure DevOps, Azure Pipelines og Bicep

### Azure DevOps

**Hva den gjør.** Azure DevOps er Microsofts pakke av utviklingsverktøy (SaaS, `dev.azure.com`) for hele livssyklusen:

| Tjeneste | Hva | GitHub-ekvivalent |
|---|---|---|
| **Azure Boards** | Arbeidselementer, backlog, sprinter, kanban | Issues + Projects |
| **Azure Repos** | Git-repoer med pull requests og branch policies | Repositories |
| **Azure Pipelines** | CI/CD | GitHub Actions |
| **Azure Test Plans** | Manuell og utforskende testing | (tredjepart) |
| **Azure Artifacts** | Pakkefeeder (NuGet, npm, Maven, Python, Universal) | GitHub Packages |

**Hvorfor.** Mange bedrifter – spesielt i Microsoft-tunge miljøer, offentlig sektor og konsulentbransjen i Norge – har brukt Azure DevOps i mange år. Du vil sannsynligvis møte både Azure DevOps og GitHub i arbeidslivet. Microsoft investerer mest i GitHub fremover, men Azure DevOps er fullt støttet og mye brukt.

**Struktur:** *Organisasjon* (`dev.azure.com/<org>`) → *Prosjekter* → Boards/Repos/Pipelines/… i hvert prosjekt.

**Kom i gang:**

1. Gå til `dev.azure.com`, logg inn med Microsoft-/skolekontoen, opprett en organisasjon og et prosjekt (`devops-lab`, *Private*, Git).
2. *Repos* → importer eller push et repo (`git remote add origin https://dev.azure.com/<org>/devops-lab/_git/devops-lab`).
3. *Boards* → lag noen *User Stories* og *Tasks*, og en sprint.
4. Koble commits og PR-er til arbeidselementer med `AB#123` i commit-meldingen (eller `#123` i Azure Repos).

**Kostnad.** Gratis for et lite antall brukere med *Basic*-tilgang (og ubegrenset antall *Stakeholder*-brukere), pluss en gratis kvote av Microsoft-hostede pipeline-jobber. **Merk:** nye organisasjoner må ofte **søke om** gratis parallelljobb for Microsoft-hostede agenter (et skjema Microsoft lenker til i dokumentasjonen); inntil da kan pipelines stå i kø. Alternativet er en **selvhostet agent** (f.eks. på din egen PC eller en VM), som er gratis å bruke. Sjekk «Azure DevOps pricing» for gjeldende vilkår.

### Azure Pipelines

**Hva den gjør.** CI/CD-tjenesten i Azure DevOps. Pipelines defineres i **YAML** (`azure-pipelines.yml`) i repoet. Kan bygge kode fra Azure Repos, GitHub og andre, og deploye til Azure, andre skyer eller egne servere.

**Struktur:**

```text
 Pipeline
 ├── trigger / pr            (når skal den kjøre)
 ├── variables
 └── stages                  (f.eks. Build → Test → DeployDev → DeployProd)
      └── jobs               (kjører på en agent; parallelle som standard)
           └── steps         (task eller script)
```

**Agenter.** *Microsoft-hosted* (ny, ren VM for hver jobb: `ubuntu-latest`, `windows-latest`) eller *self-hosted* (din egen maskin, f.eks. inne i et privat nettverk).

**Service connections** gir pipelinen tilgang til Azure. Anbefalt type: **Azure Resource Manager med workload identity federation** – ingen hemmelighet lagres; Azure DevOps får kortlevde tokens via OIDC.

**Environments** representerer deploymål (`dev`, `prod`) med **godkjenninger og sjekker** (*approvals and checks*) – f.eks. at en person må godkjenne før produksjon.

**Eksempel – bygg, test og deploy en Python-app til App Service:**

```yaml
# azure-pipelines.yml
trigger:
  branches:
    include: [main]          # kjør ved push til main
pr:
  branches:
    include: [main]          # og ved pull requests mot main (gjelder GitHub/Bitbucket-repoer;
                             # for Azure Repos brukes branch policies i stedet)

variables:
  pythonVersion: '3.12'
  azureSubscription: 'sc-azure-lab'      # navnet på service connection
  webAppName: 'app-lab-12345'

stages:
- stage: Build
  jobs:
  - job: BuildAndTest
    pool:
      vmImage: ubuntu-latest
    steps:
    - task: UsePythonVersion@0
      inputs:
        versionSpec: $(pythonVersion)
    - script: |
        pip install -r requirements.txt
        pip install pytest
        pytest -q --junitxml=test-results.xml
      displayName: 'Installer og test'
    - task: PublishTestResults@2           # vis testresultater i Azure DevOps
      condition: always()
      inputs:
        testResultsFiles: test-results.xml
    - task: ArchiveFiles@2                 # pakk appen som zip
      inputs:
        rootFolderOrFile: '$(System.DefaultWorkingDirectory)'
        includeRootFolder: false
        archiveFile: '$(Build.ArtifactStagingDirectory)/app.zip'
    - publish: '$(Build.ArtifactStagingDirectory)/app.zip'   # lagre som pipeline-artefakt
      artifact: drop

- stage: DeployProd
  dependsOn: Build
  condition: and(succeeded(), eq(variables['Build.SourceBranch'], 'refs/heads/main'))
  jobs:
  - deployment: Deploy
    environment: prod                      # godkjenninger settes opp på environment i Azure DevOps
    pool:
      vmImage: ubuntu-latest
    strategy:
      runOnce:
        deploy:
          steps:
          - task: AzureWebApp@1
            inputs:
              azureSubscription: $(azureSubscription)
              appType: webAppLinux
              appName: $(webAppName)
              package: '$(Pipeline.Workspace)/drop/app.zip'
```

**Variabler og hemmeligheter.** Hemmelige variabler settes i pipelinen eller i **variable groups** (*Library*), som kan kobles direkte til Key Vault. Hemmeligheter maskeres (`***`) i loggene.

**Maler** (*templates*) lar deg gjenbruke stages, jobs og steps på tvers av mange pipelines – nøkkelen til *Platform Engineering* i Azure DevOps.

**Classic vs. YAML.** Eldre «classic» pipelines lages i et grafisk grensesnitt (build- og release-pipelines). YAML anbefales: pipelinen versjonskontrolleres sammen med koden.

**Bedriftseksempel.** En bank har sentrale YAML-maler som alle team må bruke. Malene inkluderer sikkerhetsskanning, testing og godkjenning før produksjon, slik at alle team automatisk følger bankens krav.

**Øvelse.** Importer Flask-appen fra kapittel 7.2 til Azure Repos, lag en service connection (workload identity federation) til ressursgruppen, og kjør pipelinen over. Legg til en godkjenning på environment `prod`.

### Bicep – Azures eget IaC-språk

**Hva den gjør.** Bicep er et **deklarativt språk** for å beskrive Azure-ressurser. Du beskriver **hva** du vil ha, og Azure Resource Manager finner ut **hvordan**. Bicep kompileres til ARM-maler (JSON), men er mye kortere og lettere å lese.

**Hvorfor.** Infrastruktur som kode (kapittel 11) gir repeterbarhet, versjonskontroll, kodegjennomgang og automatisering. Bicep er førstevalget hvis du bare bruker Azure: ingen state-fil å administrere (Azure *er* tilstanden), støtte for nye ressurstyper fra dag én, og gratis.

**Bicep vs. ARM JSON** – samme lagringskonto:

```text
 ARM JSON (utdrag, ~25 linjer)                     Bicep (8 linjer)
 {                                                 resource st 'Microsoft.Storage/
   "$schema": "...",                                 storageAccounts@2023-05-01' = {
   "resources": [{                                   name: stName
     "type": "Microsoft.Storage/storageAccounts",     location: location
     "apiVersion": "2023-05-01",                      sku: { name: 'Standard_LRS' }
     "name": "[parameters('stName')]",               kind: 'StorageV2'
     "location": "[parameters('location')]",       }
     ...
```

**Installer:** Azure CLI installerer Bicep automatisk (`az bicep install` / `az bicep upgrade`). Bruk VS Code med **Bicep-utvidelsen** for autofullføring og validering.

**Et komplett eksempel** – `main.bicep` som lager en sikker lagringskonto, en App Service Plan og en web-app med managed identity:

```bicep
// main.bicep
@description('Miljø: dev eller prod')
@allowed(['dev', 'prod'])
param miljo string = 'dev'

@description('Region for ressursene')
param location string = resourceGroup().location     // standard: samme region som ressursgruppen

@description('Unikt suffiks for globale navn')
param suffiks string = uniqueString(resourceGroup().id)   // deterministisk «tilfeldig» streng

var tags = {
  miljo: miljo
  eier: 'student'
  administrertAv: 'bicep'
}
var appSkuName = miljo == 'prod' ? 'P0v3' : 'F1'     // betingelse: større plan i prod

resource st 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: 'st${suffiks}'
  location: location
  tags: tags
  sku: { name: miljo == 'prod' ? 'Standard_ZRS' : 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    supportsHttpsTrafficOnly: true
  }
}

resource plan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: 'plan-${miljo}-${suffiks}'
  location: location
  tags: tags
  sku: { name: appSkuName }
  kind: 'linux'
  properties: { reserved: true }                      // reserved: true = Linux-plan
}

resource app 'Microsoft.Web/sites@2023-12-01' = {
  name: 'app-${miljo}-${suffiks}'
  location: location
  tags: tags
  identity: { type: 'SystemAssigned' }                // managed identity
  properties: {
    serverFarmId: plan.id                             // referanse → Bicep ordner rekkefølgen selv
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.12'
      minTlsVersion: '1.2'
      appSettings: [
        { name: 'APP_ENV', value: miljo }
        { name: 'STORAGE_ACCOUNT', value: st.name }
      ]
    }
  }
}

output appUrl string = 'https://${app.properties.defaultHostName}'
output appPrincipalId string = app.identity.principalId
```

> **Merk:** Tallet etter `@` (f.eks. `@2023-05-01`) er **API-versjonen** til ressurstypen. Bicep-utvidelsen i VS Code foreslår nyere versjoner, og Microsoft Learn («Azure resource reference» / «Bicep resource definitions») viser alle egenskaper per versjon.

**Deploy:**

```bash
az group create -n rg-bicep-lab -l norwayeast

# Hva VIL skje? (som terraform plan)
az deployment group what-if -g rg-bicep-lab -f main.bicep -p miljo=dev

# Gjør det
az deployment group create -g rg-bicep-lab -f main.bicep -p miljo=dev

# Vis outputs
az deployment group show -g rg-bicep-lab -n main --query properties.outputs
```

**Parameterfiler** (`.bicepparam`):

```bicep
// dev.bicepparam
using './main.bicep'
param miljo = 'dev'
```

```bash
az deployment group create -g rg-bicep-lab -f main.bicep -p dev.bicepparam
```

**Moduler.** Del opp i gjenbrukbare filer:

```bicep
module nett 'modules/network.bicep' = {
  name: 'nettverk'
  params: {
    vnetName: 'vnet-${miljo}'
    addressPrefix: '10.0.0.0/16'
  }
}
// bruk output fra modulen: nett.outputs.subnetId
```

**Azure Verified Modules (AVM)** er Microsofts offisielle, vedlikeholdte bibliotek av Bicep- og Terraform-moduler (offentlig *Bicep registry*: `br/public:avm/res/...`). Bruk dem i stedet for å skrive alt selv.

**Deployment-modi og scope:**

- **Incremental** (standard): legger til/oppdaterer ressurser i malen, **rører ikke** andre ressurser i gruppen.
- **Complete**: sletter ressurser i gruppen som *ikke* er i malen. Farlig – bruk heller **deployment stacks** (`az stack group create`), som håndterer livssyklus og kan låse administrerte ressurser mot endring utenfra.
- Scope: `az deployment group` (ressursgruppe), `sub` (abonnement – f.eks. for å lage ressursgrupper og policyer), `mg` (management group), `tenant`.

**Bicep vs. Terraform – kort:**

| | Bicep | Terraform |
|---|---|---|
| Skyer | Kun Azure | Mange (Azure, AWS, GCP, GitHub, Kubernetes …) |
| Tilstand | Ingen state-fil – Azure er kilden | State-fil som må lagres og beskyttes |
| Nye Azure-funksjoner | Tilgjengelig umiddelbart | Når provideren oppdateres (som regel raskt) |
| Forhåndsvisning | `what-if` | `plan` |
| Utbredelse i jobbannonser | Vanlig i Azure-miljøer | Svært vanlig, også multi-cloud |

Lær begge på grunnleggende nivå; Terraform får et eget kapittel (11).

**Sikkerhet og kostnad.** Bicep er gratis. Ikke legg hemmeligheter i parameterfiler i Git; bruk `@secure()`-parametere og hent verdier fra Key Vault (`getSecret()` i `.bicepparam` eller i modulkall). Kjør deploy fra en pipeline med workload identity federation, ikke fra laptoper.

**Øvelse.** Deploy `main.bicep` med `miljo=dev`, sjekk at web-appen svarer, kjør `what-if` med en endring (legg til en ny tag), og deploy igjen. Slett ressursgruppen.

### Hvordan alt henger sammen – referansearkitektur

Her er en realistisk, moderne arkitektur for en nettbutikk som binder sammen tjenestene i del 7:

```text
                         Utviklere
                             │ git push / PR
                             ▼
                  ┌──────────────────────┐
                  │ GitHub / Azure Repos │
                  └──────────┬───────────┘
                             │ trigger
                  ┌──────────▼───────────┐   OIDC (workload identity federation)
                  │ GitHub Actions /     │─────────────────────────────────────┐
                  │ Azure Pipelines      │ bygg, test, skann, Bicep/Terraform  │
                  └──────────┬───────────┘                                     │
                             │ docker push                                     │
                  ┌──────────▼───────────┐                                     ▼
                  │ Azure Container      │                          Azure Resource Manager
                  │ Registry             │                          (+ Azure Policy, RBAC)
                  └──────────┬───────────┘
 Brukere                     │ AcrPull (managed identity)
   │                         ▼
   ▼          ┌───────────────────────────────────────────────────────────────┐
 Azure DNS ─► │ Front Door (WAF, CDN) ─► Container Apps / App Service / AKS   │
              │                              │ managed identity              │
              │                ┌─────────────┼──────────────┐                │
              │                ▼             ▼              ▼                │
              │           Key Vault     Azure SQL      Blob Storage          │
              │                    (Private Endpoints i VNet + Private DNS)  │
              └───────────────────────────────┬──────────────────────────────┘
                                              │ logger, metrikker, traces
                                   ┌──────────▼───────────┐
                                   │ Azure Monitor        │──► Alerts ──► Action groups
                                   │ Log Analytics,       │               (e-post, Teams,
                                   │ Application Insights │                vakttelefon)
                                   └──────────────────────┘
 Styring: Management groups · Azure Policy · Entra ID (MFA, PIM) · Cost Management (budsjetter, tags)
 Robusthet: Tilgjengelighetssoner · Azure Backup · geo-replikering for SQL · IaC for gjenoppbygging
```

Les diagrammet som en historie:

1. Utvikleren pusher kode. Pipelinen bygger, tester og skanner.
2. Pipelinen logger inn i Azure **uten hemmeligheter** (OIDC) og deployer infrastruktur med Bicep/Terraform – ARM sjekker RBAC og Policy.
3. Image legges i ACR; appen henter det med managed identity.
4. Brukerne går via DNS og Front Door (med WAF) til appen.
5. Appen bruker managed identity mot Key Vault, SQL og Storage, alt via private endepunkter.
6. Alt logges til Azure Monitor; varsler går til de som har vakt.
7. Styring, kostnadskontroll og backup ligger rundt alt.

Prosjekt 10 i kapittel 15 bygger en forenklet versjon av denne arkitekturen.

## Del 7 – kapitteloppsummering

- Azure styres gjennom ARM; alt kan gjøres med portal, CLI, PowerShell, SDK og IaC.
- Hierarkiet (management group → subscription → resource group) styrer arv av RBAC og Policy.
- Identitet (Entra ID), tilgang (RBAC) og regler (Policy) er fundamentet for sikkerhet og styring.
- Managed identities og Key Vault fjerner hemmeligheter fra kode.
- Nettverk: VNet, subnett, NSG, Load Balancer, Application Gateway, DNS, Private Endpoints.
- Compute: VM (IaaS), App Service (PaaS), Functions (serverless), Container Apps/AKS (containere), ACR (images).
- Data: Storage (Blob/Files), Azure SQL Database.
- Drift: Azure Monitor, Log Analytics/KQL, alerts, Backup.
- Leveranse: Azure DevOps/Pipelines eller GitHub Actions, med Bicep eller Terraform.
- Kostnad: budsjetter, tags, riktig størrelse, deallokering og opprydding.

## Del 7 – quiz

1. Hva er forskjellen på et abonnement og en ressursgruppe?
2. En bruker har Reader på abonnementet og Contributor på én ressursgruppe. Hva kan brukeren gjøre i den ressursgruppen?
3. Du vil hindre at noen lager ressurser utenfor Norway East. RBAC eller Policy?
4. Hvordan bør en web-app autentisere seg mot Key Vault?
5. En NSG har en regel som tillater port 22 på prioritet 200 og en som avviser port 22 på prioritet 150. Hva skjer?
6. Hvilken lastbalanserer bruker du for URL-basert ruting og WAF?
7. Hva er forskjellen på *Stopped* og *Stopped (deallocated)* for en VM?
8. Hvilken redundans beskytter en lagringskonto mot at et helt datasenter (sone) feiler, men ikke en hel region?
9. Hva er point-in-time restore i Azure SQL Database?
10. Hvorfor ser du ingen ressurslogger fra Key Vault i Log Analytics, selv om workspace finnes?
11. Hva gjør `az deployment group what-if`?
12. Hvilken RBAC-rolle trenger AKS for å hente images fra ACR?

### Fasit

1. Et **abonnement** er en faktureringsenhet og tilgangsgrense som inneholder ressursgrupper. En **ressursgruppe** er en logisk mappe for ressurser med samme livssyklus.
2. Alt Contributor tillater (opprette, endre, slette ressurser), men ikke gi andre tilgang. Rettighetene er additive.
3. **Azure Policy** (f.eks. «Allowed locations» med effekt Deny).
4. Med **managed identity** og RBAC-rollen *Key Vault Secrets User* på hvelvet – uten lagrede hemmeligheter.
5. Port 22 **avvises** – lavest prioritetstall (150) evalueres først.
6. **Application Gateway** (regionalt) eller **Azure Front Door** (globalt).
7. *Stopped* (fra innsiden av OS-et) beholder maskinvaren og faktureres fortsatt for compute. *Deallocated* frigjør maskinvaren, og compute faktureres ikke (disker faktureres fortsatt).
8. **ZRS** (zone-redundant storage).
9. Gjenoppretting av databasen til et vilkårlig tidspunkt innenfor oppbevaringsperioden, basert på automatiske backuper.
10. Fordi ressurslogger krever en **diagnostic setting** som sender dem til workspace.
11. Viser hvilke endringer en Bicep/ARM-deploy vil gjøre – uten å gjøre dem.
12. **AcrPull** (gis automatisk med `az aks create/update --attach-acr`).
