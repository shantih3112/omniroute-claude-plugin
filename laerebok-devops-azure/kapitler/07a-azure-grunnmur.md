# Del 7 – Microsoft Azure fra A til Å

Dette er bokens største del. Den er delt i seks kapitler:

| Kapittel | Innhold |
|---|---|
| 7.1 Grunnmur, identitet og styring | Konto, portal, CLI, ARM, hierarkiet, Entra ID, RBAC, managed identities, Policy, tags, låser, kostnader |
| 7.2 Nettverk og compute | VNet, subnett, NSG, Load Balancer, Application Gateway, DNS, VM, App Service, Functions, ACR, AKS |
| 7.3 Lagring, data, sikkerhet og drift | Storage Accounts, Blob, Files, Azure SQL, Key Vault, Monitor, Log Analytics, Backup |
| 7.4 Azure DevOps og Bicep | Azure DevOps, Pipelines, Bicep, referansearkitektur |
| 7.5 AZ-900 | Sertifiseringsmål, øvingsoppgaver og prøveeksamen |
| 7.6 AZ-104 | Sertifiseringsmål, laboppgaver og prøveeksamen |

**Mal for hver tjeneste.** Hver tjeneste beskrives med: *Hva den gjør · Hvorfor · Bedriftseksempel · Opprett og konfigurer · Sikkerhet og kostnad · Øvelse · Sammenheng med andre tjenester.*

> **Kostnad – les dette før du starter:** Gjør disse tre tingene før du lager noe i Azure:
> 1. Bruk **Azure for Students** hvis du kan (kreditt uten kredittkort, verifiseres med skole-e-post) eller en **Azure free account**. Vilkår, kreditbeløp og hvilke tjenester som er gratis endres – les gjeldende vilkår på azure.microsoft.com.
> 2. Lag et **budsjett med e-postvarsel** (vist i dette kapitlet).
> 3. Legg alt du lager i en **egen ressursgruppe per øvelse**, og slett ressursgruppen når du er ferdig.

## 7.1 Grunnmur, identitet og styring

### Kom i gang: konto, portal, Cloud Shell og Azure CLI

**Azure Portal** (`portal.azure.com`) er det grafiske nettgrensesnittet. Nyttig for å lære og utforske, men profesjonelle team gjør mest mulig med kode.

Det du bør finne i portalen:

- **Søkefeltet øverst** – raskeste vei til enhver tjeneste eller ressurs.
- **Cloud Shell-ikonet** (`>_`) øverst – en Linux-terminal i nettleseren med Azure CLI, PowerShell, Terraform, kubectl og git ferdig installert, og allerede innlogget.
- **Subscriptions**, **Resource groups**, **Cost Management**, **Microsoft Entra ID**.
- **Activity log** på hver ressurs – hvem gjorde hva, når.

**Azure CLI** (`az`) er kommandolinjeverktøyet. Installer det lokalt (se Microsoft Learn: «How to install the Azure CLI»), eller bruk Cloud Shell.

```bash
$ az login                                   # åpner nettleseren for innlogging
$ az account list -o table                   # vis abonnementene du har tilgang til
$ az account set --subscription "<navn eller id>"   # velg abonnement
$ az account show -o table                   # hvilket abonnement er aktivt?
$ az group list -o table                     # list ressursgrupper
$ az vm list -o table                        # list VM-er
$ az find "create storage account"           # foreslår kommandoer
$ az vm create --help                        # hjelp for en kommando
```

**Utdataformater** (`-o`/`--output`): `json` (standard), `table` (lesbart), `tsv` (for skript), `yaml`. **`--query`** filtrerer med JMESPath:

```bash
$ az vm list --query "[].{navn:name, region:location}" -o table
$ az group show -n rg-demo --query id -o tsv     # bare ID-en – nyttig i variabler
```

**Azure PowerShell** (`Az`-modulen) er et alternativ med kommandoer som `New-AzResourceGroup`. Boken bruker Azure CLI, men begge snakker med det samme API-et.

### Azure Resource Manager (ARM)

**Hva den gjør.** Azure Resource Manager er **kontrollplanet** i Azure: tjenesten som tar imot *alle* forespørsler om å opprette, endre eller slette ressurser – fra portalen, CLI, PowerShell, SDK-er, Terraform og Bicep.

```text
 Portal ─┐
 CLI ────┤
 PowerShell ┤──► AZURE RESOURCE MANAGER ──► autentisering (Entra ID)
 SDK ────┤          (management.azure.com)  autorisasjon (RBAC)
 Terraform ┤                                 policy-sjekk (Azure Policy)
 Bicep ──┘                                   låser (locks)
                            │
                            ▼
                 Ressursleverandører (resource providers)
          Microsoft.Compute · Microsoft.Network · Microsoft.Storage · ...
```

**Hvorfor det er viktig.** Fordi alt går gjennom ARM, får du *konsistent* sikkerhet, tilgangsstyring, policy og logging uansett verktøy. Det er også grunnen til at «klikk i portalen» og «kode» gir nøyaktig samme resultat.

**Viktige begreper:**

- **Ressurs** (*resource*) – én ting du administrerer: en VM, et VNet, en lagringskonto.
- **Ressursleverandør** (*resource provider*) – tjenesten som leverer en ressurstype, f.eks. `Microsoft.Compute/virtualMachines`. Noen må registreres i abonnementet før bruk: `az provider register --namespace Microsoft.ContainerService`.
- **Ressurs-ID** – full «adresse» til en ressurs:

```text
/subscriptions/<sub-id>/resourceGroups/rg-demo/providers/Microsoft.Compute/virtualMachines/vm-web01
```

- **ARM-maler** (*ARM templates*) – JSON-filer som beskriver ressurser deklarativt. **Bicep** er et enklere språk som oversettes til ARM-maler (kapittel 7.4).
- **Kontrollplan vs. dataplan**: *kontrollplanet* (ARM) er å lage og konfigurere en lagringskonto. *Dataplanet* er å lese og skrive filene i den. Tilgang styres separat – et viktig poeng for RBAC.

### Hierarkiet: management groups, subscriptions, resource groups

```text
 Microsoft Entra-tenant (organisasjonens identitetskatalog)
 └── Root management group
      ├── Management group: "Plattform"
      │    └── Subscription: "sub-connectivity"
      │         └── Resource group: rg-hub-network
      │              ├── vnet-hub
      │              └── azure-firewall
      └── Management group: "Landingssoner"
           ├── Subscription: "sub-nettbutikk-prod"
           │    ├── Resource group: rg-nettbutikk-prod-web
           │    │    ├── app-service-plan
           │    │    └── web-app
           │    └── Resource group: rg-nettbutikk-prod-data
           │         └── azure-sql-database
           └── Subscription: "sub-nettbutikk-dev"
```

Innstillinger som **policy** og **tilganger (RBAC)** som settes på et nivå, **arves nedover** til alt under.

#### Microsoft Entra-tenant

Organisasjonens instans av Microsoft Entra ID (identitetstjenesten). Alle abonnementer stoler på nøyaktig én tenant.

#### Management groups

**Hva den gjør.** Grupperer abonnementer slik at du kan styre policy og tilgang for mange abonnementer samtidig. Kan nøstes i opptil seks nivåer under rotgruppen.

**Hvorfor.** Store bedrifter har titalls eller hundrevis av abonnementer. Uten management groups måtte hver policy settes opp på hvert abonnement.

**Bedriftseksempel.** En bank har management groups for «Produksjon» og «Sandkasse». På «Produksjon» gjelder strenge policyer (bare Norway East og Sweden Central, ingen offentlige IP-er uten godkjenning). I «Sandkasse» får utviklere eksperimentere fritt, men med budsjettgrenser.

```bash
$ az account management-group create --name mg-lab --display-name "Lab"
$ az account management-group subscription add --name mg-lab --subscription "<sub-id>"
```

#### Subscriptions (abonnementer)

**Hva den gjør.** Et abonnement er en **faktureringsenhet** og en **tilgangsgrense**. Alle ressurser tilhører nøyaktig ett abonnement, og kostnadene faktureres per abonnement.

**Hvorfor flere abonnementer?** For å skille miljøer (prod/dev), avdelinger eller prosjekter – med egne budsjetter, tilganger og **kvoter** (grenser, f.eks. hvor mange vCPU-er du kan bruke per region).

> **Vanlig feil:** Å treffe en kvotegrense og tro at noe er ødelagt. Feilmeldinger som «Operation could not be completed as it results in exceeding approved ... Cores quota» betyr at du må velge mindre størrelse, annen region, eller be om økt kvote (*Quotas* i portalen). Studentabonnementer har ofte lave kvoter.

#### Resource groups (ressursgrupper)

**Hva den gjør.** En logisk **mappe** for ressurser som hører sammen og har samme livssyklus.

**Regler å kunne:**

- Hver ressurs ligger i **nøyaktig én** ressursgruppe.
- Ressursgrupper kan **ikke nøstes**.
- Ressursgruppen har en region (der *metadata* lagres), men ressursene i den kan ligge i andre regioner.
- **Sletter du ressursgruppen, slettes alt i den.** Perfekt for opprydding etter øvelser.
- Ressurser kan flyttes mellom grupper og abonnementer (med noen unntak).

**Bedriftseksempel.** «Alt for nettbutikkens testmiljø» i `rg-nettbutikk-test`. Når testperioden er over: én kommando sletter alt.

```bash
$ az group create --name rg-lab-01 --location norwayeast --tags miljø=lab eier=student
$ az group list -o table
$ az group delete --name rg-lab-01 --yes --no-wait      # slett alt i gruppen
```

**Navnekonvensjon.** Microsoft Cloud Adoption Framework anbefaler prefikser som `rg-`, `vnet-`, `snet-`, `nsg-`, `vm-`, `st` (lagringskonto), `kv-`, `app-`, `func-`, `log-`, `aks-`, `acr`. Eksempel: `rg-nettbutikk-prod-norwayeast-001`. Konsekvente navn gjør automatisering og feilsøking mye enklere.

### Microsoft Entra ID

**Hva den gjør.** Microsoft Entra ID (tidligere **Azure Active Directory / Azure AD**) er Microsofts skybaserte **identitets- og tilgangstjeneste**. Den svarer på spørsmålet **«hvem er du?»** (autentisering) og gir tokens som andre tjenester bruker for å avgjøre **«hva får du lov til?»** (autorisasjon).

> **Hverdagsanalogi:** Entra ID er resepsjonen og ID-kortsystemet i et kontorbygg. Den sjekker hvem du er og gir deg et adgangskort. Dørene (Azure-ressurser, Microsoft 365, andre apper) leser kortet og avgjør om du slipper inn.

**Hvorfor.** Én sentral identitet per person gir enkel innlogging (*single sign-on*), sentral kontroll med MFA, og mulighet til å stenge all tilgang med ett klikk når noen slutter.

**Viktige objekter:**

| Objekt | Hva |
|---|---|
| **Bruker** (*user*) | En person. Kan være intern (medlem) eller gjest (B2B) |
| **Gruppe** (*group*) | Samling brukere – gi tilgang til grupper, ikke enkeltpersoner |
| **App registration** | Definisjonen av en applikasjon som skal bruke Entra ID |
| **Service principal** | Identiteten en applikasjon bruker i en tenant (f.eks. en CI/CD-pipeline) |
| **Managed identity** | En service principal som Azure administrerer automatisk (se under) |

**Sikkerhetsfunksjoner:**

- **MFA** (*multifaktorautentisering*) – passord + noe du har (app, nøkkel). Microsoft krever nå MFA for innlogging til Azure-portalen, CLI og andre administrasjonsverktøy (innført gradvis fra 2024–2025).
- **Conditional Access** – regler som «krev MFA utenfor kontoret», «blokker innlogging fra visse land», «krev administrert enhet». Krever Entra ID P1-lisens eller høyere.
- **Privileged Identity Management (PIM)** – administratorroller aktiveres *bare når de trengs*, for en begrenset tid, med godkjenning. Krever P2 / Entra ID Governance.
- **Passordløs innlogging** – passkeys, Windows Hello, Authenticator-appen.

**Entra ID vs. Active Directory (on-prem).** Klassisk *Active Directory Domain Services* (AD DS) i Windows-servere bruker Kerberos/LDAP og domener. Entra ID er skybasert og bruker moderne web-protokoller (OAuth 2.0, OpenID Connect, SAML). **Entra Connect** synkroniserer brukere fra lokal AD til Entra ID i hybride miljøer.

**Opprett bruker og gruppe:**

```bash
# Domenet ditt finner du i portalen: Entra ID → Overview → Primary domain
$ az ad user create --display-name "Test Bruker" \
    --user-principal-name testbruker@<ditt-domene>.onmicrosoft.com \
    --password "<et-sterkt-midlertidig-passord>" --force-change-password-next-sign-in true

$ az ad group create --display-name "devops-team" --mail-nickname "devops-team"
$ az ad group member add --group "devops-team" \
    --member-id $(az ad user show --id testbruker@<ditt-domene>.onmicrosoft.com --query id -o tsv)
```

**Sikkerhet og kostnad.** Entra ID Free følger med alle abonnementer. P1/P2-funksjoner (Conditional Access, PIM) koster per bruker. **Bruk aldri delte administratorkontoer**, og ha minst to «break-glass»-nødkontoer med sterk beskyttelse i ekte organisasjoner.

**Øvelse.** Opprett en testbruker og gruppen `devops-team`, legg brukeren i gruppen, og gi gruppen *Reader* på en ressursgruppe (neste seksjon). Logg inn som testbrukeren i et privat nettleservindu og bekreft at du kan se, men ikke endre.

**Sammenheng.** Entra ID er grunnlaget for RBAC, managed identities, Key Vault-tilgang, innlogging i AKS, og føderert innlogging fra GitHub Actions og Azure Pipelines.

### Azure RBAC – rollebasert tilgangskontroll

**Hva den gjør.** Azure RBAC (*Role-Based Access Control*) styrer **hva** en identitet får gjøre med Azure-ressurser.

En **rolletildeling** (*role assignment*) består av tre deler:

```text
   HVEM               HVA                     HVOR
 (security principal) (rolledefinisjon)       (scope)
 ┌───────────────┐   ┌──────────────────┐   ┌──────────────────────────┐
 │ bruker        │   │ Reader           │   │ management group         │
 │ gruppe        │ + │ Contributor      │ + │ subscription             │
 │ service princ.│   │ Owner            │   │ resource group           │
 │ managed ident.│   │ Storage Blob ... │   │ enkeltressurs            │
 └───────────────┘   └──────────────────┘   └──────────────────────────┘
```

**De viktigste innebygde rollene:**

| Rolle | Kan |
|---|---|
| **Owner** | Alt, *inkludert* å gi andre tilgang |
| **Contributor** | Opprette og administrere alt, men *ikke* gi tilgang |
| **Reader** | Se alt, endre ingenting |
| **User Access Administrator** | Administrere tilganger |
| **Role Based Access Control Administrator** | Administrere tilganger, kan begrenses med betingelser (tryggere enn UAA) |
| Tjenestespesifikke | f.eks. *Virtual Machine Contributor*, *Storage Blob Data Reader*, *Key Vault Secrets User*, *AcrPull* |

**Hvordan det evalueres:**

- Tilganger **arves** nedover: Reader på abonnementet gir Reader på alle ressursgrupper i det.
- Tilganger er **additive**: Reader + Contributor = effektivt Contributor.
- **Deny assignments** (avslag) vinner over tillatelser, men lages som regel av Azure selv (f.eks. av *deployment stacks*), ikke manuelt.
- **Kontrollplan vs. dataplan**: *Contributor* på en lagringskonto lar deg konfigurere den, men å lese blob-data med Entra-innlogging krever en **data-rolle** som *Storage Blob Data Reader*.

**Hvorfor.** Prinsippet om **minste privilegium** (*least privilege*): gi akkurat den tilgangen som trengs, på det minste scopet, i kortest mulig tid.

**Bedriftseksempel.** Utviklerteamet får *Contributor* på `rg-nettbutikk-dev`, men bare *Reader* på produksjon. CI/CD-pipelinen sin identitet får *Contributor* på produksjonsgruppen – ingen mennesker endrer produksjon manuelt.

```bash
$ RG_ID=$(az group show -n rg-lab-01 --query id -o tsv)
$ GROUP_ID=$(az ad group show --group devops-team --query id -o tsv)

$ az role assignment create --assignee-object-id "$GROUP_ID" \
    --assignee-principal-type Group --role "Reader" --scope "$RG_ID"

$ az role assignment list --scope "$RG_ID" -o table    # hvem har tilgang her?
$ az role definition list --name "Contributor" -o json # hva inneholder rollen?
```

> **Vanlig feil:** Å forveksle **Entra-roller** (f.eks. *Global Administrator*, *User Administrator* – styrer Entra ID selv: brukere, grupper, lisenser) med **Azure RBAC-roller** (*Owner*, *Contributor* – styrer Azure-ressurser). De er to separate systemer. En Global Administrator har ikke automatisk tilgang til Azure-ressurser (men kan gi seg selv det via «Access management for Azure resources»).

> **Vanlig feil:** RBAC-endringer kan bruke litt tid før de slår gjennom. Får du «AuthorizationFailed» rett etter en tildeling, vent et par minutter og prøv igjen (logg eventuelt inn på nytt).

**Egendefinerte roller** (*custom roles*) kan lages i JSON med lister over `Actions`, `NotActions`, `DataActions` og `AssignableScopes` når ingen innebygd rolle passer.

**Øvelse.** Gi deg selv *Storage Blob Data Contributor* på en lagringskonto (kapittel 7.3) og bekreft at `az storage blob list --auth-mode login` virker før og ikke virker etter at du fjerner tildelingen.

### Managed identities

**Hva den gjør.** En managed identity er en **identitet i Entra ID som Azure lager og administrerer automatisk for en ressurs** (en VM, en App Service, en Function, en AKS-pod). Ressursen kan bruke identiteten til å logge inn på andre Azure-tjenester **uten passord eller nøkler i koden**.

**Hvorfor.** Det klassiske problemet: appen må koble seg til databasen eller Key Vault. Hvor lagrer du passordet? I koden (farlig), i en konfigfil (farlig), i en miljøvariabel (bedre, men den må roteres)? Med managed identity finnes det **ingen hemmelighet å lekke** – Azure utsteder kortlevde tokens automatisk.

```text
 ┌──────────────┐ 1. «Gi meg et token for Key Vault»   ┌────────────────┐
 │  Web App     │ ───────────────────────────────────► │ Entra ID       │
 │ (med managed │ ◄─────────────────────────────────── │ (via lokal     │
 │  identity)   │ 2. kortlevd token                    │ token-tjeneste)│
 └──────┬───────┘                                      └────────────────┘
        │ 3. Hent hemmelighet med token
        ▼
 ┌──────────────┐  4. RBAC-sjekk: har identiteten
 │  Key Vault   │     «Key Vault Secrets User»? ✓
 └──────────────┘
```

**To typer:**

| | System-assigned | User-assigned |
|---|---|---|
| Opprettes | Sammen med ressursen | Som egen ressurs |
| Livssyklus | Slettes når ressursen slettes | Lever uavhengig |
| Deling | Én ressurs | Kan deles av mange ressurser |
| Bruk | Enkelt, én app | Mange instanser med samme tilgang, eller når identiteten må finnes før ressursen |

**Opprett og bruk:**

```bash
# Slå på system-assigned identity for en web-app
$ az webapp identity assign -g rg-lab-01 -n app-demo-<unik>
{ "principalId": "1111aaaa-...", "type": "SystemAssigned" }

# Gi identiteten lesetilgang til hemmeligheter i Key Vault
$ KV_ID=$(az keyvault show -n kv-demo-<unik> --query id -o tsv)
$ az role assignment create --assignee-object-id "1111aaaa-..." \
    --assignee-principal-type ServicePrincipal \
    --role "Key Vault Secrets User" --scope "$KV_ID"
```

I Python-koden holder det med `DefaultAzureCredential()` (kapittel 4) – den finner managed identity automatisk når koden kjører i Azure, og din `az login` når du kjører lokalt. **Samme kode, ingen hemmeligheter.**

> **Husk:** Managed identity er svaret på nesten alle spørsmål av typen «hvordan bør appen autentisere seg mot en annen Azure-tjeneste?» – både i virkeligheten og på AZ-104.

**Workload identity federation** er en beslektet teknikk der eksterne systemer (GitHub Actions, Azure Pipelines, Kubernetes) får Azure-tokens uten lagrede hemmeligheter, basert på tillit (OIDC). Vi bruker det i kapittel 12.

### Azure Policy

**Hva den gjør.** Azure Policy **håndhever regler** for hvordan ressurser kan konfigureres, og **rapporterer** hvilke ressurser som bryter reglene (*compliance*).

**RBAC vs. Policy:**

- RBAC: **hvem** får gjøre noe? («Kari får opprette VM-er.»)
- Policy: **hva** er lov å lage? («Ingen – heller ikke Kari – får lage VM-er utenfor Norway East.»)

**Hvordan det fungerer.**

1. En **policydefinisjon** beskriver en regel i JSON (*if* … *then* effekt).
2. Definisjoner kan samles i et **initiativ** (*policy set*).
3. Du gjør en **tildeling** (*assignment*) av definisjonen eller initiativet til et scope (management group, abonnement, ressursgruppe).
4. ARM sjekker nye og endrede ressurser mot reglene, og Azure evaluerer eksisterende ressurser jevnlig.

**Vanlige effekter:**

| Effekt | Gjør |
|---|---|
| `Deny` | Stopper opprettelsen |
| `Audit` | Tillater, men markerer som ikke-kompatibel |
| `Append` / `Modify` | Legger til eller endrer egenskaper (f.eks. legger til en tag) |
| `DeployIfNotExists` | Oppretter noe som mangler (f.eks. diagnostikkinnstillinger) |
| `AuditIfNotExists` | Rapporterer at noe mangler |
| `Disabled` | Av |

**Bedriftseksempler på policyer:** bare tillatte regioner; påkrevd tag `kostnadssted`; ingen offentlig tilgang til lagringskontoer; bare godkjente VM-størrelser; krev TLS 1.2; send alle logger til Log Analytics.

**Eksempel – «Allowed locations» på en ressursgruppe:**

```bash
$ RG_ID=$(az group show -n rg-lab-01 --query id -o tsv)

# Finn den innebygde definisjonen «Allowed locations»
$ az policy definition list --query "[?displayName=='Allowed locations'].name" -o tsv
e56962a6-4747-49cd-b67b-bf8b01975c4c

$ az policy assignment create --name allowed-locations-lab \
    --policy e56962a6-4747-49cd-b67b-bf8b01975c4c \
    --scope "$RG_ID" \
    --params '{"listOfAllowedLocations": {"value": ["norwayeast", "swedencentral"]}}'

# Test: dette skal nå bli avvist med "RequestDisallowedByPolicy"
$ az storage account create -n sttest$RANDOM -g rg-lab-01 -l westus --sku Standard_LRS
```

En policyregel i JSON ser slik ut (forenklet):

```json
{
  "if": {
    "allOf": [
      { "field": "type", "equals": "Microsoft.Storage/storageAccounts" },
      { "field": "Microsoft.Storage/storageAccounts/allowBlobPublicAccess", "equals": true }
    ]
  },
  "then": { "effect": "deny" }
}
```

**Sikkerhet og kostnad.** Azure Policy for Azure-ressurser er gratis. Det er et av de viktigste verktøyene for **governance** (styring) i skyen.

> **Fordypning:** **Unntak** (*exemptions*) lar deg unnta enkeltressurser. **Remediation tasks** retter eksisterende ressurser for `Modify`/`DeployIfNotExists`. Microsoft Defender for Cloud bruker Azure Policy under panseret for sikkerhetsanbefalinger.

### Tags og ressurslåser

**Tags** er nøkkel–verdi-merkelapper på ressurser og ressursgrupper: `miljø=prod`, `eier=team-betaling`, `kostnadssted=4410`, `utløper=2026-12-01`.

- Brukes til kostnadsrapportering (Cost Management kan gruppere på tags), automatisering og oversikt.
- Tags **arves ikke automatisk** fra ressursgruppen til ressursene – bruk Azure Policy (f.eks. «Inherit a tag from the resource group») for å få det til.

```bash
$ az group update -n rg-lab-01 --tags miljø=lab eier=student utløper=2026-11-30
$ az resource list --tag miljø=lab -o table
```

**Ressurslåser** (*resource locks*) beskytter mot uhell, **også for Owner**:

| Lås | Effekt |
|---|---|
| `CanNotDelete` (*Delete*) | Kan endres, men ikke slettes |
| `ReadOnly` | Kan verken endres eller slettes |

```bash
$ az lock create --name ikke-slett --lock-type CanNotDelete --resource-group rg-prod-data
$ az lock list -g rg-prod-data -o table
$ az lock delete --name ikke-slett --resource-group rg-prod-data
```

> **Vanlig feil:** `ReadOnly` kan ha uventede bivirkninger. En `ReadOnly`-lås på en lagringskonto hindrer for eksempel listing av tilgangsnøkler (det er en POST-operasjon), og på en App Service kan den hindre ting som å se konfigurasjon i portalen. Les Microsoft Learn («Lock your resources») før du bruker den.

### Azure-priser og Cost Management

**Hva det gjør.** **Cost Management + Billing** viser hva du har brukt, hva du kommer til å bruke (prognose), og lar deg sette budsjetter og varsler. **Azure Pricing Calculator** estimerer kostnader *før* du bygger. **Azure Advisor** gir anbefalinger om sparing (f.eks. «denne VM-en er nesten ubrukt»).

**Hva påvirker prisen?** Ressurstype og størrelse, region, tid i bruk, lagringsmengde og -nivå, utgående trafikk, lisenser, og prismodell (pay-as-you-go, reservasjoner, savings plan, spot). Se kapittel 6.

**Lag et budsjett (portal) – gjør dette nå:**

1. Søk etter **Cost Management** → **Budgets** → **+ Add**.
2. Scope: abonnementet ditt.
3. Navn `budsjett-student`, periode *Monthly*, beløp f.eks. 20 (i valutaen din).
4. **Alert conditions**: *Actual* 50 %, *Actual* 90 %, *Forecasted* 100 %.
5. Legg inn e-postadressen din → **Create**.

> **Vanlig feil:** Å tro at et budsjett **stopper** forbruket. Et budsjett **varsler** bare. (Kreditbaserte student- og gratisabonnementer har en egen utgiftsgrense som stanser ressursene når kreditten er brukt opp – men stol ikke på det; rydd opp selv.) For automatisk handling kan et budsjett kobles til en *action group* som starter en automatisering.

**Kostnadsanalyse:** *Cost Management → Cost analysis* → grupper etter **Resource group**, **Service name** eller **Tag**. Gjør dette ukentlig mens du studerer.

**Øvelse.** Sett opp budsjettet over. Lag deretter en Pricing Calculator-estimering for arkitekturen i prosjekt 10 (kapittel 15), og lagre den.

### Oppsummering av 7.1

- Alt i Azure går gjennom **Azure Resource Manager** – samme API for portal, CLI og kode.
- Hierarki: **tenant → management groups → subscriptions → resource groups → ressurser**. Policy og RBAC arves nedover.
- **Entra ID** = identitet (hvem er du). **RBAC** = tilgang til Azure-ressurser (hva får du gjøre, hvor). **Policy** = regler for hva som er lov å lage.
- **Managed identities** fjerner behovet for passord mellom Azure-tjenester.
- **Tags** gir oversikt og kostnadsfordeling; **låser** hindrer uhell.
- **Budsjetter** varsler, de stopper ikke forbruk.
