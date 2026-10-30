# Del 11 – Infrastructure as Code

**Læringsmål for kapitlet.** Når du er ferdig, skal du kunne:

- forklare hva Infrastructure as Code (IaC) er og hvorfor det er standard i bransjen,
- bruke Terraform: providers, resources, variables, outputs, state, modules, plan og apply,
- sette opp remote state i Azure på en sikker måte,
- bygge Azure-infrastruktur automatisk med Terraform og Bicep,
- forklare configuration management med Ansible,
- forklare GitOps.

## Hva er Infrastructure as Code?

**Hva er det?** Infrastructure as Code (IaC) betyr at du **beskriver infrastrukturen din i kodefiler** – nettverk, VM-er, databaser, tilganger – og lar et verktøy opprette og vedlikeholde den, i stedet for å klikke i en portal.

**Hvorfor finnes det?** Tenk deg at du har satt opp et produksjonsmiljø med 40 ressurser ved å klikke i Azure Portal. Nå skal du:

- lage et identisk testmiljø (husker du alle innstillingene?),
- forklare en kollega hva som er satt opp (finnes det dokumentasjon?),
- finne ut hvem som endret brannmurregelen i forrige uke, og hvorfor,
- gjenoppbygge alt etter at noen slettet ressursgruppen.

Med klikking er alt dette vanskelig og feilutsatt. Med IaC:

| Fordel | Forklaring |
|---|---|
| **Repeterbarhet** | Samme kode gir samme infrastruktur – hver gang, i hvert miljø |
| **Versjonskontroll** | Infrastrukturen ligger i Git: historikk, hvem, hva, hvorfor |
| **Kodegjennomgang** | Endringer gjennomgås i pull requests før de rulles ut |
| **Automatisering** | Kjøres fra CI/CD-pipelines |
| **Dokumentasjon** | Koden *er* dokumentasjonen av hva som finnes |
| **Gjenoppretting** | Gjenoppbygg alt etter en katastrofe |
| **Testing** | Valider, lint, skann for sikkerhetsfeil før noe lages |

> **Hverdagsanalogi:** Å klikke i portalen er som å lage mat uten oppskrift – det kan bli godt, men det blir aldri helt likt neste gang, og ingen andre kan gjenta det. IaC er **oppskriften**: presis, delbar og forbedrebar.

### Deklarativ vs. imperativ

| | Deklarativ | Imperativ |
|---|---|---|
| Du beskriver | **Hva** sluttresultatet skal være | **Hvordan** – stegene |
| Eksempel | «Det skal finnes et VNet med disse subnettene» | «Kjør `az network vnet create`, så `az network vnet subnet create` …» |
| Kjører du to ganger | Ingen endring (allerede riktig) | Kan feile eller lage duplikater |
| Verktøy | Terraform, Bicep, Kubernetes YAML | Bash-/Python-skript med CLI-kommandoer |

**Idempotens** betyr at det å kjøre samme kode flere ganger gir samme resultat. Deklarative verktøy er idempotente av natur – en av hovedgrunnene til at de foretrekkes.

### To kategorier IaC

```text
 PROVISIONERING (lage infrastruktur)       KONFIGURASJONSSTYRING (konfigurere innsiden)
 Terraform, Bicep, Pulumi, CloudFormation  Ansible, Chef, Puppet, cloud-init
 «Lag VNet, VM, database, Key Vault»       «Installer nginx, sett opp brukere, kopier config»
                    └──────────────── brukes ofte sammen ───────────────┘
```

Med containere og PaaS har behovet for konfigurasjonsstyring av servere blitt mindre (imaget *er* konfigurasjonen), men Ansible er fortsatt svært utbredt.

## Terraform

**Hva er det?** Terraform er et deklarativt IaC-verktøy fra **HashiCorp**. Du skriver konfigurasjonen i **HCL** (*HashiCorp Configuration Language*), og Terraform snakker med API-ene til Azure, AWS, GCP, GitHub, Kubernetes og hundrevis av andre plattformer via **providers**.

> **Merk om lisens:** HashiCorp endret Terraforms lisens i 2023 til Business Source License (BSL), og HashiCorp er nå en del av IBM. Som følge av lisensendringen ble **OpenTofu** opprettet – en åpen kildekode-gren av Terraform under Linux Foundation, som er i stor grad kompatibel. Det du lærer her, gjelder i praksis for begge. Sjekk lisensvilkårene hvis du skal bygge kommersielle produkter *rundt* Terraform; vanlig bruk for å administrere egen infrastruktur er ikke berørt.

### Installasjon

Følg «Install Terraform» på developer.hashicorp.com (pakker finnes for Windows, macOS og Linux). Terraform er også forhåndsinstallert i Azure Cloud Shell.

```bash
$ terraform version
Terraform v1.x.x
```

### Arbeidsflyten

```text
  skriv .tf-filer ─► terraform init ─► terraform plan ─► terraform apply ─► (endre) ─► plan ─► apply
                     (last ned         (vis hva som     (gjør endringene,
                      providers,        VIL skje)        oppdater state)
                      sett opp backend)
                                                          terraform destroy (slett alt)
```

| Kommando | Gjør |
|---|---|
| `terraform init` | Initialiserer mappen: laster ned providers og moduler, setter opp state-backend |
| `terraform fmt` | Formaterer koden pent |
| `terraform validate` | Sjekker syntaks og intern konsistens |
| `terraform plan` | Sammenligner kode, state og virkelighet – viser hva som vil bli **lagt til (+), endret (~), slettet (-)** |
| `terraform apply` | Utfører planen (spør om bekreftelse) |
| `terraform destroy` | Sletter alt Terraform administrerer i denne konfigurasjonen |
| `terraform output` | Viser outputs |
| `terraform state list` | Lister ressurser i state |
| `terraform import` / `import`-blokk | Tar en eksisterende ressurs under Terraform-kontroll |

### Providers

**Hva er det?** En **provider** er en plugin som vet hvordan Terraform skal snakke med et bestemt API. For Azure bruker vi primært **azurerm** (Azure Resource Manager). Det finnes også **azuread** (Entra ID-objekter) og **azapi** (direkte mot ARM-API-et, for helt nye funksjoner).

```hcl
# providers.tf
terraform {
  required_version = ">= 1.6"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"   # hvor provideren hentes fra (Terraform Registry)
      version = "~> 4.0"              # tillat 4.x, men ikke 5.0 (unngå brytende endringer)
    }
  }
}

provider "azurerm" {
  features {}                          # påkrevd blokk (kan være tom)
  subscription_id = var.subscription_id   # påkrevd i azurerm v4 (eller miljøvariabelen ARM_SUBSCRIPTION_ID)
}
```

**Autentisering mot Azure.** Lokalt bruker provideren din `az login`-innlogging. I CI/CD bruker man en service principal eller managed identity, helst med **OIDC** (workload identity federation) via miljøvariabler som `ARM_CLIENT_ID`, `ARM_TENANT_ID`, `ARM_SUBSCRIPTION_ID` og `ARM_USE_OIDC=true` (kapittel 12).

**Låsefilen** `.terraform.lock.hcl` lagrer nøyaktig hvilken provider-versjon som ble valgt. **Sjekk den inn i Git**, slik at alle bruker samme versjon.

### Resources

**Hva er det?** En **resource** er én infrastrukturkomponent Terraform skal administrere.

```hcl
#        ressurstype            lokalt navn (brukes i Terraform-koden)
resource "azurerm_resource_group" "main" {
  name     = "rg-tf-lab"            # navnet i Azure
  location = "norwayeast"
  tags = {
    miljo = "lab"
    eier  = "student"
  }
}

resource "azurerm_virtual_network" "main" {
  name                = "vnet-tf-lab"
  location            = azurerm_resource_group.main.location   # REFERANSE til en annen ressurs
  resource_group_name = azurerm_resource_group.main.name
  address_space       = ["10.0.0.0/16"]
}
```

**Referanser og avhengigheter.** `azurerm_resource_group.main.name` leses: «attributtet `name` fra ressursen av typen `azurerm_resource_group` med lokalt navn `main`». Fordi VNet-et refererer til ressursgruppen, **forstår Terraform at ressursgruppen må lages først**. Terraform bygger en **avhengighetsgraf** og lager uavhengige ressurser parallelt. (`depends_on` brukes bare når en avhengighet ikke kan uttrykkes med referanser.)

**Data sources** leser informasjon om ting som finnes fra før, uten å administrere dem:

```hcl
data "azurerm_client_config" "current" {}          # info om hvem som kjører Terraform

data "azurerm_resource_group" "delt" {
  name = "rg-delte-tjenester"                      # en eksisterende gruppe noen andre eier
}
# bruk: data.azurerm_client_config.current.tenant_id
```

Dokumentasjonen for hver ressurstype finnes i **Terraform Registry** (registry.terraform.io → providers → hashicorp/azurerm). Den viser påkrevde og valgfrie argumenter og eksempler – bruk den hele tiden.

### Variables

**Hva er det?** Input-variabler gjør koden **gjenbrukbar** – samme kode for dev og prod, med ulike verdier.

```hcl
# variables.tf
variable "subscription_id" {
  type        = string
  description = "Azure subscription ID"
}

variable "location" {
  type        = string
  description = "Azure-region for alle ressurser"
  default     = "norwayeast"
}

variable "miljo" {
  type        = string
  description = "Miljø: dev eller prod"
  validation {
    condition     = contains(["dev", "prod"], var.miljo)
    error_message = "miljo må være 'dev' eller 'prod'."
  }
}

variable "subnets" {
  type = map(string)                    # en map: navn → CIDR
  default = {
    web  = "10.0.1.0/24"
    data = "10.0.2.0/24"
  }
}

variable "db_admin_password" {
  type      = string
  sensitive = true                      # skjules i plan/apply-utskrift
}
```

**Typer:** `string`, `number`, `bool`, `list(...)`, `map(...)`, `set(...)`, `object({...})`.

**Hvordan sette verdier** (senere vinner over tidligere):

1. `default` i variabelen,
2. `terraform.tfvars` eller `*.auto.tfvars` (lastes automatisk),
3. `-var-file=prod.tfvars`,
4. miljøvariabler `TF_VAR_navn` (f.eks. `export TF_VAR_db_admin_password=...`),
5. `-var="miljo=prod"` på kommandolinjen.

```hcl
# dev.tfvars
miljo    = "dev"
location = "norwayeast"
```

**Locals** er hjelpeverdier som beregnes i koden:

```hcl
locals {
  prefix = "tf-${var.miljo}"
  tags = {
    miljo          = var.miljo
    administrertAv = "terraform"
  }
}
# bruk: local.prefix, local.tags
```

> **Vanlig feil:** Å legge hemmeligheter i `terraform.tfvars` og sjekke den inn i Git. Bruk miljøvariabler (`TF_VAR_...`) fra et hemmelighetshvelv i pipelinen, eller enda bedre: la Terraform generere passordet og lagre det i Key Vault (eksempel senere).

### Outputs

**Hva er det?** Verdier Terraform skriver ut etter `apply`, og som andre konfigurasjoner eller skript kan bruke.

```hcl
# outputs.tf
output "resource_group_name" {
  value = azurerm_resource_group.main.name
}

output "web_app_url" {
  value       = "https://${azurerm_linux_web_app.main.default_hostname}"
  description = "URL til web-appen"
}
```

```bash
$ terraform output
$ terraform output -raw web_app_url      # bare verdien – nyttig i skript
```

### Løkker og betingelser

```hcl
# Lag ett subnett per element i var.subnets
resource "azurerm_subnet" "main" {
  for_each             = var.subnets               # web, data
  name                 = "snet-${each.key}"        # each.key = "web" / "data"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = [each.value]              # each.value = CIDR
}
# referanse: azurerm_subnet.main["web"].id

# Betingelse: lag Application Insights bare i prod
resource "azurerm_application_insights" "main" {
  count               = var.miljo == "prod" ? 1 : 0
  name                = "appi-${local.prefix}"
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name
  workspace_id        = azurerm_log_analytics_workspace.main.id
  application_type    = "web"
}
```

> **Husk:** Foretrekk **`for_each`** fremfor `count` for lister av ting. Med `count` identifiseres ressurser med indeks (0, 1, 2); fjerner du element nummer 0, «flytter» alle de andre seg, og Terraform vil slette og gjenskape dem. Med `for_each` identifiseres de med nøkkel.

### State-filen

**Hva er det?** Terraform lagrer det den vet om infrastrukturen i en **state-fil** (`terraform.tfstate`): en kobling mellom ressursene i koden og de ekte ressursene i Azure (med ID-er og attributter).

```text
   KODE (.tf)              STATE (tfstate)              VIRKELIGHETEN (Azure)
 «det skal være"   ◄──►  «dette laget jeg sist,   ◄──►   faktiske ressurser
  et VNet»                VNet-ID = /subscriptions/..»
          └──────────── terraform plan sammenligner alle tre ──────────────┘
```

**Hvorfor trengs state?**

- Koble kode til ekte ressurser (hvilket VNet i Azure er `azurerm_virtual_network.main`?).
- Vite hva som skal **slettes** når du fjerner noe fra koden.
- Ytelse og avhengigheter.

**Viktig om state:**

- State kan inneholde **hemmeligheter i klartekst** (passord, nøkler). Behandle den som sensitiv.
- **Aldri** sjekk inn `terraform.tfstate` i Git (legg i `.gitignore`).
- **Aldri** rediger state manuelt; bruk `terraform state mv/rm`, `moved`-blokker og `import`-blokker.
- **To personer som kjører apply samtidig** mot samme state kan ødelegge den → du trenger **låsing**.

**Drift** (*configuration drift*) er når virkeligheten avviker fra koden – f.eks. noen endret en innstilling i portalen. `terraform plan` avslører det, og `apply` setter det tilbake.

> **Vanlig feil:** «Jeg slettet ressursen i portalen, og nå klager Terraform.» Eller: «Jeg endret noe i portalen, og Terraform overskrev det.» Når et miljø er administrert av Terraform, gjør **alle** endringer gjennom koden.

### Remote state

**Problemet.** Lokal state-fil på din laptop fungerer ikke for et team eller en pipeline: andre har den ikke, den kan bli borte, og det er ingen låsing.

**Løsningen.** Lagre state i en **remote backend**. I Azure: en **Blob Storage-container**, som støtter **låsing** via blob leases.

**1. Lag lagringskontoen for state (én gang, f.eks. med CLI):**

```bash
RG=rg-tfstate; LOC=norwayeast; ST=sttfstate$RANDOM
az group create -n $RG -l $LOC
az storage account create -n $ST -g $RG -l $LOC --sku Standard_ZRS \
  --min-tls-version TLS1_2 --allow-blob-public-access false
az storage account blob-service-properties update --account-name $ST -g $RG \
  --enable-versioning true --enable-delete-retention true --delete-retention-days 30
az storage container create -n tfstate --account-name $ST --auth-mode login

# Gi deg selv (og senere pipeline-identiteten) data-tilgang
az role assignment create --assignee-object-id $(az ad signed-in-user show --query id -o tsv) \
  --assignee-principal-type User --role "Storage Blob Data Contributor" \
  --scope $(az storage account show -n $ST -g $RG --query id -o tsv)
echo $ST
```

**2. Konfigurer backend:**

```hcl
# backend.tf
terraform {
  backend "azurerm" {
    resource_group_name  = "rg-tfstate"
    storage_account_name = "sttfstate12345"     # navnet fra over
    container_name       = "tfstate"
    key                  = "lab/dev.terraform.tfstate"   # én state-fil per miljø/prosjekt
    use_azuread_auth     = true                  # Entra-innlogging i stedet for kontonøkkel
  }
}
```

```bash
$ terraform init            # flytter/kobler state til Azure (spør om å migrere eksisterende state)
```

Nå er state delt, låst under `apply`, versjonert og sikret med RBAC.

> **Husk:** Ressursene for remote state (lagringskontoen) lages som regel **utenfor** den Terraform-konfigurasjonen som bruker dem – ellers får du et høna-og-egget-problem. Beskytt kontoen med en `CanNotDelete`-lås.

### Modules

**Hva er det?** En **modul** er en mappe med Terraform-filer som kan **gjenbrukes** – som en funksjon i programmering. All Terraform-kode er egentlig en modul (*root module*); moduler du kaller fra den kalles *child modules*.

**Hvorfor?** Unngå copy-paste, standardiser (f.eks. «slik lager vi alltid en sikker lagringskonto hos oss»), og skjul kompleksitet.

```text
infra/
├── modules/
│   └── webapp/                 # en gjenbrukbar modul
│       ├── main.tf
│       ├── variables.tf
│       └── outputs.tf
└── envs/
    ├── dev/
    │   ├── main.tf             # kaller modulen med dev-verdier
    │   ├── backend.tf
    │   └── dev.tfvars
    └── prod/
        ├── main.tf
        ├── backend.tf
        └── prod.tfvars
```

```hcl
# envs/dev/main.tf
module "webapp" {
  source   = "../../modules/webapp"     # lokal sti; kan også være Git-URL eller Registry
  name     = "butikk-dev"
  location = "norwayeast"
  sku_name = "F1"
}

output "url" {
  value = module.webapp.url             # output fra modulen
}
```

**Offentlige moduler:** Terraform Registry har tusenvis av moduler, inkludert **Azure Verified Modules (AVM)** fra Microsoft (`Azure/avm-res-...`). Les koden og lås versjonen (`version = "x.y.z"`) før du bruker andres moduler.

### Komplett eksempel: Azure-webapp med Key Vault, overvåking og managed identity

Denne konfigurasjonen bygger en realistisk liten plattform automatisk. Filene ligger i én mappe.

```hcl
# main.tf
locals {
  prefix = "${var.prosjekt}-${var.miljo}"
  tags = {
    prosjekt       = var.prosjekt
    miljo          = var.miljo
    administrertAv = "terraform"
  }
}

data "azurerm_client_config" "current" {}

resource "random_string" "suffix" {          # krever provideren hashicorp/random
  length  = 5
  upper   = false
  special = false
}

resource "azurerm_resource_group" "main" {
  name     = "rg-${local.prefix}"
  location = var.location
  tags     = local.tags
}

# --- Overvåking ---
resource "azurerm_log_analytics_workspace" "main" {
  name                = "log-${local.prefix}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = local.tags
}

resource "azurerm_application_insights" "main" {
  name                = "appi-${local.prefix}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  workspace_id        = azurerm_log_analytics_workspace.main.id
  application_type    = "web"
  tags                = local.tags
}

# --- Key Vault med RBAC ---
resource "azurerm_key_vault" "main" {
  name                       = "kv-${var.prosjekt}-${random_string.suffix.result}"
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  enable_rbac_authorization  = true          # nyere azurerm-versjoner: rbac_authorization_enabled
  purge_protection_enabled   = false         # true i produksjon
  soft_delete_retention_days = 7
  tags                       = local.tags
}

# Den som kjører Terraform må kunne skrive hemmeligheter
resource "azurerm_role_assignment" "kv_terraform" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.current.object_id
}

resource "random_password" "api_key" {
  length  = 32
  special = false
}

resource "azurerm_key_vault_secret" "api_key" {
  name         = "ApiKey"
  value        = random_password.api_key.result
  key_vault_id = azurerm_key_vault.main.id
  depends_on   = [azurerm_role_assignment.kv_terraform]   # vent på tilgangen
}

# --- App Service ---
resource "azurerm_service_plan" "main" {
  name                = "plan-${local.prefix}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  os_type             = "Linux"
  sku_name            = var.app_sku
  tags                = local.tags
}

resource "azurerm_linux_web_app" "main" {
  name                = "app-${local.prefix}-${random_string.suffix.result}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  service_plan_id     = azurerm_service_plan.main.id
  https_only          = true
  tags                = local.tags

  identity {
    type = "SystemAssigned"                  # managed identity
  }

  site_config {
    always_on           = var.app_sku == "F1" ? false : true   # Free støtter ikke always_on
    minimum_tls_version = "1.2"
    application_stack {
      python_version = "3.12"
    }
  }

  app_settings = {
    APP_ENV                               = var.miljo
    APPLICATIONINSIGHTS_CONNECTION_STRING = azurerm_application_insights.main.connection_string
    API_KEY = "@Microsoft.KeyVault(VaultName=${azurerm_key_vault.main.name};SecretName=${azurerm_key_vault_secret.api_key.name})"
  }
}

# Appens identitet får lese hemmeligheter
resource "azurerm_role_assignment" "kv_app" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_linux_web_app.main.identity[0].principal_id
}
```

```hcl
# variables.tf
variable "subscription_id" { type = string }
variable "prosjekt" {
  type    = string
  default = "butikk"
}
variable "miljo" {
  type    = string
  default = "dev"
}
variable "location" {
  type    = string
  default = "norwayeast"
}
variable "app_sku" {
  type    = string
  default = "F1"
}
```

```hcl
# providers.tf
terraform {
  required_version = ">= 1.6"
  required_providers {
    azurerm = { source = "hashicorp/azurerm", version = "~> 4.0" }
    random  = { source = "hashicorp/random",  version = "~> 3.6" }
  }
}
provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}
```

```hcl
# outputs.tf
output "web_app_url" {
  value = "https://${azurerm_linux_web_app.main.default_hostname}"
}
output "key_vault_name" {
  value = azurerm_key_vault.main.name
}
```

> **Merk:** Argumentnavn i azurerm endres av og til mellom hovedversjoner (f.eks. er `enable_rbac_authorization` på Key Vault i ferd med å erstattes av `rbac_authorization_enabled`). Hvis `terraform validate` klager på et argument, sjekk dokumentasjonen for akkurat din provider-versjon i Terraform Registry.

**Kjør:**

```bash
$ export TF_VAR_subscription_id=$(az account show --query id -o tsv)
$ terraform init
$ terraform fmt && terraform validate
$ terraform plan -out=tfplan          # lagre planen
Plan: 12 to add, 0 to change, 0 to destroy.
$ terraform apply tfplan              # utfør nøyaktig den lagrede planen
$ terraform output web_app_url
$ terraform destroy                   # rydd opp når du er ferdig
```

**Les en plan:**

```text
  # azurerm_linux_web_app.main will be updated in-place
  ~ resource "azurerm_linux_web_app" "main" {
      ~ app_settings = {
          ~ "APP_ENV" = "dev" -> "test"
        }
    }
  # azurerm_subnet.main["data"] must be replaced
-/+ resource "azurerm_subnet" "main" {
      ~ address_prefixes = ["10.0.2.0/24"] -> ["10.0.3.0/24"]   # forces replacement
    }
```

`+` lages, `~` endres på stedet, `-` slettes, `-/+` **slettes og lages på nytt** (pass på – kan gi nedetid eller datatap!).

> **Husk:** **Les alltid planen** før du kjører `apply`. «Forces replacement» på en database er et rødt flagg.

### Beste praksis for Terraform

- Én state per miljø og logisk komponent (ikke én gigantisk state for alt).
- Remote state med låsing, versjonering og begrenset tilgang.
- Lås provider- og modulversjoner; sjekk inn `.terraform.lock.hcl`.
- `terraform fmt`, `validate`, og sikkerhetsskanning (Checkov, Trivy) i CI.
- `plan` på pull request (vis planen som kommentar), `apply` etter merge – fra pipeline, ikke fra laptop.
- `lifecycle { prevent_destroy = true }` på kritiske ressurser.
- Ikke hardkod hemmeligheter; bruk `sensitive = true`.
- `.gitignore`: `.terraform/`, `*.tfstate*`, `*.tfvars` med hemmeligheter, `tfplan`.

## Bicep – kort repetisjon

Bicep ble gjennomgått i kapittel 7.4. Kort sagt: Azure-spesifikt, ingen state-fil, deploy med `az deployment group create`, forhåndsvis med `what-if`. Her er den samme ressursgruppen + VNet som Terraform-eksemplet, for sammenligning:

```bicep
// main.bicep (deployes på abonnementsnivå for å kunne lage ressursgruppen)
targetScope = 'subscription'

param location string = 'norwayeast'

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-bicep-lab'
  location: location
}

module nett 'network.bicep' = {
  name: 'nett'
  scope: rg
  params: { location: location }
}
```

```bicep
// network.bicep
param location string

resource vnet 'Microsoft.Network/virtualNetworks@2024-01-01' = {
  name: 'vnet-bicep-lab'
  location: location
  properties: {
    addressSpace: { addressPrefixes: ['10.0.0.0/16'] }
    subnets: [
      { name: 'snet-web', properties: { addressPrefix: '10.0.1.0/24' } }
      { name: 'snet-data', properties: { addressPrefix: '10.0.2.0/24' } }
    ]
  }
}
output vnetId string = vnet.id
```

```bash
$ az deployment sub create -l norwayeast -f main.bicep
```

**Valget mellom Terraform og Bicep** handler ofte om hva organisasjonen allerede bruker. Multi-cloud eller mange ikke-Azure-ressurser (GitHub, Datadog, Cloudflare) → Terraform. Bare Azure og ønske om null state-håndtering → Bicep.

## Ansible og configuration management

**Hva er det?** **Configuration management** sørger for at **innsiden** av servere er konfigurert riktig og likt: pakker, filer, brukere, tjenester. **Ansible** (Red Hat) er det mest brukte verktøyet.

**Hvorfor Ansible?**

- **Agentløst** – kobler til servere over **SSH** (eller WinRM for Windows); ingenting må installeres på målmaskinene utover Python.
- **YAML** – lett å lese.
- **Idempotent** – moduler sjekker tilstanden før de endrer noe.

**Begreper:**

| Begrep | Betyr |
|---|---|
| **Control node** | Maskinen du kjører Ansible fra |
| **Managed nodes** | Serverne som konfigureres |
| **Inventory** | Liste over servere (statisk fil, eller dynamisk fra Azure) |
| **Module** | En enhet som gjør én ting (`apt`, `copy`, `template`, `service`, `user`) |
| **Task** | Et kall til en modul |
| **Playbook** | YAML-fil med en eller flere *plays* (hvilke verter + hvilke tasks) |
| **Role** | Gjenbrukbar pakke av tasks, maler og variabler |
| **Handler** | Task som bare kjøres når noe er endret (f.eks. restart nginx) |

**Inventory** (`inventory.ini`):

```ini
[web]
vm-web01 ansible_host=10.0.1.4
vm-web02 ansible_host=10.0.1.5

[web:vars]
ansible_user=azureuser
ansible_ssh_private_key_file=~/.ssh/id_ed25519
```

**Playbook** (`webserver.yml`):

```yaml
- name: Konfigurer webservere
  hosts: web                      # gruppen fra inventory
  become: true                    # bruk sudo
  vars:
    sidetittel: "Hei fra Ansible"

  tasks:
    - name: Installer nginx
      ansible.builtin.apt:
        name: nginx
        state: present            # deklarativt: «skal være installert»
        update_cache: true

    - name: Legg ut forsiden fra mal
      ansible.builtin.template:
        src: templates/index.html.j2     # Jinja2-mal med {{ sidetittel }} og {{ inventory_hostname }}
        dest: /var/www/html/index.html
        mode: "0644"
      notify: Restart nginx               # kjør handleren hvis filen endres

    - name: Sørg for at nginx kjører og starter ved oppstart
      ansible.builtin.service:
        name: nginx
        state: started
        enabled: true

  handlers:
    - name: Restart nginx
      ansible.builtin.service:
        name: nginx
        state: restarted
```

`templates/index.html.j2`:

```html
<h1>{{ sidetittel }}</h1>
<p>Server: {{ inventory_hostname }}</p>
```

```bash
$ pip install ansible                                  # eller: sudo apt install ansible
$ ansible -i inventory.ini web -m ping                 # test tilkobling
$ ansible-playbook -i inventory.ini webserver.yml --check --diff   # tørrkjøring: hva VILLE endret seg?
$ ansible-playbook -i inventory.ini webserver.yml      # kjør
$ ansible-playbook -i inventory.ini webserver.yml      # kjør igjen → "changed=0" (idempotent!)
```

**Hemmeligheter** i Ansible krypteres med **Ansible Vault** (`ansible-vault encrypt secrets.yml`).

**Terraform + Ansible sammen:** Terraform lager VM-ene og skriver ut IP-adressene; Ansible konfigurerer dem. (Alternativt brukes **dynamic inventory** med Azure-pluginen `azure.azcollection.azure_rm`, som henter VM-er basert på tags.)

## GitOps

**Hva er det?** GitOps er en arbeidsmåte der **Git er den eneste sannhetskilden** for ønsket tilstand til infrastruktur og applikasjoner, og en **agent kontinuerlig synkroniserer** miljøet mot det som står i Git.

**Fire prinsipper** (OpenGitOps):

1. **Deklarativt** – ønsket tilstand er beskrevet deklarativt.
2. **Versjonert og uforanderlig** – lagret i Git med full historikk.
3. **Hentes automatisk** (*pulled*) – agenter henter ønsket tilstand selv.
4. **Kontinuerlig avstemt** – agenter retter avvik automatisk.

**Push vs. pull:**

```text
 PUSH (klassisk CI/CD)                       PULL (GitOps)
 Git ─► Pipeline ──kubectl apply──► Cluster   Git ◄──overvåker── Agent (Argo CD/Flux) I clusteret
        (pipelinen trenger tilgang                         └─► gjør clusteret likt Git
         til clusteret)                       (ingen ekstern tilgang til clusteret nødvendig)
```

**Hvorfor GitOps?**

- Alle endringer går via pull request → gjennomgang og historikk.
- **Rollback = `git revert`.**
- Drift rettes automatisk (noen endrer noe manuelt → agenten setter det tilbake).
- Sikrere: CI-systemet trenger ikke administratortilgang til clusteret.

**Verktøy:** **Argo CD** og **Flux** (begge CNCF-prosjekter). AKS har en **GitOps-utvidelse basert på Flux v2**.

**Typisk oppsett:**

```text
 app-repo (kode)                           config-repo (Kubernetes-manifester / Helm values)
   │ push                                     ▲
   ▼                                          │ 3. CI oppdaterer image-tag (PR eller commit)
 CI: test, bygg image ─► push til ACR ────────┘
                                              │ 4. Argo CD/Flux ser endringen
                                              ▼
                                   AKS-cluster synkroniseres → ny versjon kjører
```

Et Argo CD `Application`-objekt (forenklet):

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: butikk
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/<org>/butikk-config.git
    targetRevision: main
    path: envs/prod                       # mappen med manifester for prod
  destination:
    server: https://kubernetes.default.svc
    namespace: butikk
  syncPolicy:
    automated:
      prune: true                         # slett ressurser som er fjernet fra Git
      selfHeal: true                      # rett manuelle endringer automatisk
```

> **Fra arbeidslivet:** GitOps brukes mest for **Kubernetes**. For Azure-infrastruktur (Terraform/Bicep) er det vanligste mønsteret «PR → plan som kommentar → merge → apply fra pipeline», som deler mange av GitOps-fordelene.

## Kapitteloppsummering

- IaC beskriver infrastruktur i kode: repeterbart, versjonert, gjennomgått og automatisert.
- Deklarative verktøy (Terraform, Bicep) er idempotente; imperative skript er det ikke nødvendigvis.
- Terraform: providers snakker med API-er; resources beskriver infrastruktur; variables/locals/outputs gjør koden fleksibel; `init → plan → apply`.
- State kobler kode til virkelighet; lagre den remote (Azure Blob) med låsing, og behandle den som sensitiv.
- Moduler gir gjenbruk og standardisering.
- Bicep er Azures eget, state-løse alternativ.
- Ansible konfigurerer servere agentløst over SSH med idempotente playbooks.
- GitOps: Git er sannheten, agenter (Argo CD/Flux) synkroniserer kontinuerlig.

## Øvingsoppgaver

1. Skriv Terraform som lager en ressursgruppe, et VNet med tre subnett (bruk `for_each`) og en NSG knyttet til web-subnettet. Kjør `plan`, `apply`, endre en tag, `plan` igjen, og `destroy`.
2. Sett opp remote state i Azure Blob og flytt state dit med `terraform init -migrate-state`.
3. Gjør VNet-koden om til en modul og kall den to ganger (dev og test) med ulike adresseområder.
4. Endre en tag manuelt i portalen, og se hvordan `terraform plan` oppdager driften.
5. Skriv en Ansible-playbook som oppretter en bruker `deploy`, legger inn din SSH-nøkkel, og installerer `htop` og `git`. Kjør den to ganger og bekreft idempotens.
6. Skriv samme ressursgruppe + VNet i Bicep og sammenlign med Terraform-versjonen.

## Quiz

1. Hva betyr idempotens, og hvorfor er det viktig i IaC?
2. Hva er forskjellen på provisionering og configuration management?
3. Hva gjør `terraform plan`?
4. Hvorfor skal du ikke sjekke inn `terraform.tfstate` i Git?
5. Hva oppnår du med remote state i Azure Blob Storage?
6. Hva betyr `-/+` i en Terraform-plan?
7. Hvorfor er `for_each` ofte bedre enn `count`?
8. Hva er en Terraform-modul?
9. Hvorfor trenger ikke Bicep en state-fil?
10. Hva betyr at Ansible er agentløst?
11. Hva er forskjellen på push- og pull-basert deploy i GitOps-sammenheng?
12. En kollega endret en NSG-regel i portalen. Hva skjer ved neste `terraform apply`?

### Fasit

1. At det å kjøre samme kode flere ganger gir samme resultat. Det gjør det trygt å kjøre IaC ofte og automatisk, uten duplikater eller utilsiktede endringer.
2. **Provisionering** lager infrastrukturen (VM, nettverk, database). **Configuration management** konfigurerer innsiden av serverne (pakker, filer, tjenester).
3. Sammenligner koden med state og den faktiske infrastrukturen, og viser hvilke endringer `apply` vil gjøre – uten å gjøre dem.
4. Den kan inneholde hemmeligheter i klartekst, og den må deles og låses på en trygg måte, noe Git ikke gir.
5. Delt tilgang for team og pipelines, låsing mot samtidige endringer, versjonering/backup og tilgangskontroll.
6. Ressursen vil bli **slettet og laget på nytt** (replacement) – kan gi nedetid eller datatap.
7. Med `for_each` identifiseres ressurser med stabile nøkler. Med `count` identifiseres de med indeks, så fjerning av ett element kan føre til at andre ressurser slettes og lages på nytt.
8. En gjenbrukbar samling Terraform-filer med input-variabler og outputs, som kalles fra annen Terraform-kode.
9. Fordi Azure Resource Manager selv er kilden til sannhet om hva som finnes; Bicep sammenligner direkte mot Azure ved deploy.
10. Det krever ingen egen agent på serverne; Ansible kobler til over SSH (eller WinRM) og kjører modulene der.
11. **Push**: en pipeline utenfor clusteret sender endringer inn (trenger tilgang til clusteret). **Pull**: en agent i clusteret henter ønsket tilstand fra Git og synkroniserer selv.
12. Terraform oppdager avviket og **setter regelen tilbake** til det som står i koden (hvis regelen er administrert av Terraform). Endringen bør derfor gjøres i koden.
