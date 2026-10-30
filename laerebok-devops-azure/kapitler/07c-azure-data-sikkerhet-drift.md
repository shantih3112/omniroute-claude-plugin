## 7.3 Lagring, data, sikkerhet og drift

```bash
RG=rg-lab-data
LOC=norwayeast
az group create -n $RG -l $LOC --tags miljø=lab eier=student
```

### Azure Storage Accounts

**Hva den gjør.** En lagringskonto er en **beholder for Azures lagringstjenester**, med ett felles navn, ett endepunkt-sett og felles innstillinger for sikkerhet og redundans. En konto kan inneholde:

| Tjeneste | Hva | Endepunkt |
|---|---|---|
| **Blob Storage** | Objekter/filer (bilder, video, backup, logger, data) | `https://<konto>.blob.core.windows.net` |
| **Azure Files** | Delte filområder (SMB/NFS) | `https://<konto>.file.core.windows.net` |
| **Queue Storage** | Enkle meldingskøer | `...queue.core.windows.net` |
| **Table Storage** | Enkel NoSQL nøkkel–verdi | `...table.core.windows.net` |

**Hvorfor.** Nesten alle løsninger trenger et sted å lagre filer billig og trygt – og mange Azure-tjenester (Functions, diagnostikklogger, Terraform-state) bruker lagringskontoer under panseret.

**Viktige valg ved opprettelse:**

1. **Navn** – 3–24 tegn, kun små bokstaver og tall, **globalt unikt** (det blir en del av en URL).
2. **Ytelse** – *Standard* (generell bruk) eller *Premium* (lav forsinkelse, SSD).
3. **Kontotype** – *StorageV2 (general purpose v2)* er standard.
4. **Redundans** – hvor mange kopier, og hvor:

```text
 LRS   3 kopier i ett datasenter                         ┌DC1┐
 ZRS   3 kopier fordelt på 3 tilgjengelighetssoner        ┌Z1┐┌Z2┐┌Z3┐
 GRS   LRS i primærregion + LRS i paret region (asynkront) ┌DC1┐ ═══► ┌DC (region 2)┐
 GZRS  ZRS i primærregion + LRS i paret region
 RA-GRS / RA-GZRS: som GRS/GZRS, men du kan LESE fra sekundærregionen hele tiden
```

| Redundans | Beskytter mot | Relativ pris |
|---|---|---|
| LRS | Disk-/rackfeil | Lavest |
| ZRS | Tap av et datasenter (sone) | Høyere |
| GRS / RA-GRS | Tap av en hel region | Høyere |
| GZRS / RA-GZRS | Sone- og regiontap | Høyest |

> **Merk:** Geo-redundans krever en paret region. Norway East er paret med Norway West. Sjekk på Microsoft Learn hvilke redundansvalg som er tilgjengelige i regionen du bruker.

**Opprett en sikker lagringskonto:**

```bash
ST=stlab$RANDOM          # tilfeldig suffiks for unikt navn
az storage account create -n $ST -g $RG -l $LOC \
  --sku Standard_LRS --kind StorageV2 \
  --min-tls-version TLS1_2 \
  --allow-blob-public-access false \
  --https-only true
```

**Tilgang til data – fire metoder:**

| Metode | Hva | Anbefaling |
|---|---|---|
| **Entra ID + RBAC** | Innlogging med identitet og data-roller (*Storage Blob Data Reader/Contributor*) | **Best** – bruk dette, særlig med managed identity |
| **SAS-token** (*Shared Access Signature*) | URL med tidsbegrenset, avgrenset tilgang | Bra for midlertidig deling; foretrekk *user delegation SAS* |
| **Tilgangsnøkler** (*account keys*) | To hovednøkler med full tilgang til alt | Unngå; kan slås av (`--allow-shared-key-access false`) |
| Anonym offentlig lesetilgang | Alle kan lese | Kun for helt offentlig innhold; av som standard |

**Nettverk:** Lagringskontoer kan begrenses med brannmur (bare valgte VNets/IP-er) eller nås kun via **Private Endpoint**.

**Datasikkerhet:** Kryptert i ro som standard (Microsoft-administrerte nøkler, eventuelt kundeadministrerte i Key Vault). **Soft delete** for blobs og containere, **versjonering**, og **immutable storage** (WORM – kan ikke endres eller slettes i en periode) beskytter mot sletting og løsepengevirus.

**Kostnad.** Betal for: lagret mengde (per GB/måned, avhengig av nivå og redundans), operasjoner (per 10 000 transaksjoner), datauthenting fra kalde nivåer, og utgående trafikk.

### Blob Storage

**Hva den gjør.** Objektlagring for **ustrukturerte data** i ubegrensede mengder. Organisert som:

```text
 Lagringskonto (stlab12345)
 └── Container (bilder)                    ← som en mappe på toppnivå
      ├── blob: logo.png                   ← filen
      ├── blob: 2026/10/kvittering-001.pdf ← «/» i navnet gir virtuelle mapper
      └── ...
```

**Blob-typer:** *Block blobs* (vanlige filer – de fleste tilfeller), *Append blobs* (logger som det bare legges til i), *Page blobs* (virtuelle disker).

**Tilgangsnivåer** (*access tiers*):

| Nivå | For data som … | Lagring | Lesing |
|---|---|---|---|
| Hot | brukes ofte | Dyrest | Billigst |
| Cool | brukes sjelden (min. 30 dager) | Billigere | Dyrere |
| Cold | brukes svært sjelden (min. 90 dager) | Enda billigere | Enda dyrere |
| Archive | nesten aldri (min. 180 dager) | Billigst | Dyrest; må *rehydreres* (timer) før lesing |

**Livssyklusregler** (*lifecycle management*) flytter eller sletter data automatisk:

```json
{
  "rules": [{
    "name": "flytt-gamle-logger",
    "enabled": true,
    "type": "Lifecycle",
    "definition": {
      "filters": { "blobTypes": ["blockBlob"], "prefixMatch": ["logger/"] },
      "actions": {
        "baseBlob": {
          "tierToCool":    { "daysAfterModificationGreaterThan": 30 },
          "tierToArchive": { "daysAfterModificationGreaterThan": 180 },
          "delete":        { "daysAfterModificationGreaterThan": 365 }
        }
      }
    }
  }]
}
```

```bash
az storage account management-policy create --account-name $ST -g $RG --policy @policy.json
```

**Last opp og ned med Entra-innlogging:**

```bash
# Gi deg selv data-tilgang (kontrollplan-tilgang som Owner er IKKE nok for --auth-mode login)
ME=$(az ad signed-in-user show --query id -o tsv)
az role assignment create --assignee-object-id $ME --assignee-principal-type User \
  --role "Storage Blob Data Contributor" \
  --scope $(az storage account show -n $ST -g $RG --query id -o tsv)

az storage container create --account-name $ST -n bilder --auth-mode login
echo "hei" > hei.txt
az storage blob upload --account-name $ST -c bilder -f hei.txt -n hei.txt --auth-mode login
az storage blob list --account-name $ST -c bilder --auth-mode login -o table
az storage blob download --account-name $ST -c bilder -n hei.txt -f ned.txt --auth-mode login
```

**AzCopy** er et kommandolinjeverktøy for å kopiere store datamengder raskt (`azcopy copy ./mappe "https://$ST.blob.core.windows.net/bilder" --recursive`). **Azure Storage Explorer** er et gratis grafisk program.

**Statisk nettside.** Blob Storage kan hoste en statisk nettside (HTML/CSS/JS) direkte fra containeren `$web`:

```bash
az storage blob service-properties update --account-name $ST --static-website \
  --index-document index.html --404-document 404.html
az storage blob upload-batch --account-name $ST -s ./site -d '$web' --auth-mode login
az storage account show -n $ST -g $RG --query "primaryEndpoints.web" -o tsv
```

(For moderne frontend-apper med API og CI/CD er **Azure Static Web Apps** et godt alternativ, med en gratis plan.)

**Bedriftseksempel.** En nettavis lagrer millioner av bilder i Blob Storage (Hot), serverer dem via Azure Front Door (CDN), og flytter bilder eldre enn ett år til Cool med livssyklusregler.

**Øvelse.** Lag lagringskontoen, last opp en fil med Entra-innlogging, lag en *user delegation SAS* med 1 times gyldighet (`az storage blob generate-sas --as-user --auth-mode login --permissions r --expiry <tid> --full-uri ...`), og åpne URL-en i nettleseren.

### Azure Files

**Hva den gjør.** Fullt administrerte **filområder** (*file shares*) som kan monteres over **SMB** (Windows, Linux, macOS) eller **NFS** (Linux, krever Premium). Som en nettverksdisk på kontoret – i skyen.

**Hvorfor.** «Lift and shift» av apper som forventer en delt mappe, delte konfigurasjonsfiler mellom flere VM-er, erstatning for lokale filservere, og vedvarende lagring for containere.

**Azure File Sync** synkroniserer lokale Windows-filservere med Azure Files, med *cloud tiering* (sjelden brukte filer ligger bare i skyen).

```bash
az storage share-rm create -g $RG --storage-account $ST -n delt --quota 100   # 100 GiB
```

**Monter fra Linux (SMB):** portalen gir deg et ferdig skript under *File share → Connect*. Merk at SMB bruker **port 445**, som mange internettleverandører og bedriftsnett blokkerer utgående – fra hjemmenett kan monteringen derfor feile; fra en Azure-VM virker det.

**Sikkerhet og kostnad.** Identitetsbasert tilgang med AD DS / Entra Kerberos for SMB, Private Endpoint, snapshots og Azure Backup. Betal per GiB (Standard: per brukt mengde; Premium: per *provisjonert* størrelse) pluss transaksjoner. Sjekk den nyere **provisioned v2**-faktureringsmodellen på Learn.

### Azure SQL Database

**Hva den gjør.** En **fullt administrert relasjonsdatabase** (PaaS) basert på Microsoft SQL Server-motoren. Microsoft håndterer patching, backup, høy tilgjengelighet og oppgraderinger.

**Familien Azure SQL:**

| Tjeneste | Modell | Bruk |
|---|---|---|
| **Azure SQL Database** | PaaS, én database (eller elastic pool) | Nye skyapplikasjoner |
| **Azure SQL Managed Instance** | PaaS, nesten 100 % kompatibel med SQL Server | Flytting av eksisterende SQL Server-løsninger |
| **SQL Server på Azure VM** | IaaS | Full kontroll, spesielle behov |

(For PostgreSQL og MySQL finnes tilsvarende *Azure Database for PostgreSQL / MySQL – Flexible Server*.)

**Bestanddeler:**

```text
 Logisk server (sql-lab-123.database.windows.net)  ← innlogging, brannmur, Entra-admin
 ├── Database: appdb    (egen størrelse/pris)
 └── Database: rapportdb
```

**Kjøpsmodeller:**

- **vCore** (anbefalt): velg antall vCores og nivå: *General Purpose*, *Business Critical* (raskere, flere replikaer), *Hyperscale* (svært stor, rask skalering). **Serverless** compute skalerer automatisk og kan pause når databasen ikke brukes.
- **DTU**: enklere pakker (Basic, Standard, Premium) med samlet ytelsesmål.

**Gratis tilbud.** Azure SQL Database har et gratistilbud (en månedlig kvote av vCore-sekunder og lagring for et begrenset antall databaser per abonnement) – sjekk gjeldende vilkår på Microsoft Learn («Azure SQL Database free offer»).

**Opprett:**

```bash
SQLSRV=sql-lab-$RANDOM
MY_UPN=$(az ad signed-in-user show --query userPrincipalName -o tsv)
MY_OID=$(az ad signed-in-user show --query id -o tsv)

# Logisk server med KUN Entra-autentisering (ingen SQL-passord) – anbefalt
az sql server create -g $RG -n $SQLSRV -l $LOC \
  --enable-ad-only-auth \
  --external-admin-principal-type User \
  --external-admin-name "$MY_UPN" --external-admin-sid "$MY_OID"

# Database med gratistilbudet (pauser når kvoten er brukt opp)
az sql db create -g $RG -s $SQLSRV -n appdb \
  --edition GeneralPurpose --compute-model Serverless --family Gen5 --capacity 2 \
  --use-free-limit --free-limit-exhaustion-behavior AutoPause

# Tillat din egen IP gjennom serverbrannmuren
MYIP=$(curl -s https://api.ipify.org)
az sql server firewall-rule create -g $RG -s $SQLSRV -n min-ip \
  --start-ip-address $MYIP --end-ip-address $MYIP
```

Koble til med **Query editor** i portalen, Azure Data Studio-etterfølgeren **VS Code med mssql-utvidelsen**, eller `sqlcmd`. Lag en tabell:

```sql
CREATE TABLE kunder (
    id INT IDENTITY(1,1) PRIMARY KEY,   -- automatisk økende ID
    navn NVARCHAR(100) NOT NULL,
    epost NVARCHAR(200) UNIQUE
);
INSERT INTO kunder (navn, epost) VALUES (N'Kari', N'kari@example.com');
SELECT * FROM kunder;
```

**La appen logge inn med managed identity** (ingen passord): i databasen, kjørt som Entra-admin:

```sql
CREATE USER [app-lab-123] FROM EXTERNAL PROVIDER;   -- navnet på web-appen/identiteten
ALTER ROLE db_datareader ADD MEMBER [app-lab-123];
ALTER ROLE db_datawriter ADD MEMBER [app-lab-123];
```

**Høy tilgjengelighet og gjenoppretting:**

- Innebygd HA i regionen; **zone redundancy** som valg.
- **Automatisk backup** med **point-in-time restore** (PITR) – gjenopprett til et hvilket som helst tidspunkt innen oppbevaringsperioden (standard 7 dager, kan økes til 35), og **long-term retention** (LTR) i opptil 10 år.
- **Active geo-replication** og **failover groups** for DR til en annen region.

**Sikkerhet:** Entra-autentisering, brannmur eller (bedre) **Private Endpoint** og *Deny public network access*, **TDE** (Transparent Data Encryption, på som standard), Always Encrypted for spesielt sensitive kolonner, **Microsoft Defender for SQL**, auditing til Log Analytics.

> **Vanlig feil:** Å slå på «Allow Azure services and resources to access this server». Det tillater trafikk fra **alle** Azure-kunder sine ressurser, ikke bare dine. Bruk Private Endpoint eller VNet-regler i stedet.

**Bedriftseksempel.** En SaaS-leverandør har én database per kunde i en **elastic pool**, slik at mange små databaser deler kapasitet og kostnad.

**Øvelse.** Opprett server og database som over, lag tabellen, og gjør en point-in-time restore til en ny database (`az sql db restore ... --time <ISO-tid> --dest-name appdb-restore`). Hvor lang tid tok det?

### Azure Key Vault

**Hva den gjør.** Et sikkert **hvelv** for:

- **Secrets** – passord, tilkoblingsstrenger, API-nøkler.
- **Keys** – kryptografiske nøkler (for kryptering og signering), eventuelt i HSM.
- **Certificates** – TLS-sertifikater, med automatisk fornyelse fra støttede utstedere.

**Hvorfor.** Hemmeligheter skal ikke ligge i kode, konfigurasjonsfiler eller Git. Key Vault gir sentral lagring, tilgangskontroll, **revisjonslogg** (hvem leste hvilken hemmelighet når), versjonering og rotasjon.

**Tilgangsmodell.** Bruk **Azure RBAC** (standard for nye hvelv) med roller som:

| Rolle | Kan |
|---|---|
| Key Vault Administrator | Alt på dataplanet |
| Key Vault Secrets Officer | Administrere hemmeligheter |
| **Key Vault Secrets User** | **Lese** hemmeligheter (det appene trenger) |
| Key Vault Crypto User | Bruke nøkler |
| Key Vault Certificates Officer | Administrere sertifikater |

(Den eldre modellen *access policies* finnes fortsatt, men Microsoft anbefaler RBAC.)

**Beskyttelse mot sletting:**

- **Soft delete** (alltid på): slettede hvelv og hemmeligheter kan gjenopprettes i oppbevaringsperioden (7–90 dager).
- **Purge protection**: hindrer permanent sletting i oppbevaringsperioden – selv for administratorer. Anbefalt i produksjon.

**Opprett og bruk:**

```bash
KV=kv-lab-$RANDOM          # 3–24 tegn, globalt unikt
az keyvault create -n $KV -g $RG -l $LOC --enable-rbac-authorization true

# Gi deg selv rett til å administrere hemmeligheter
az role assignment create --assignee-object-id $(az ad signed-in-user show --query id -o tsv) \
  --assignee-principal-type User --role "Key Vault Secrets Officer" \
  --scope $(az keyvault show -n $KV --query id -o tsv)

az keyvault secret set --vault-name $KV -n DbPassword --value 'Eksempel-Ikke-Ekte-123!'
az keyvault secret show --vault-name $KV -n DbPassword --query value -o tsv
az keyvault secret list --vault-name $KV -o table
```

**Fra Python med managed identity / din innlogging:**

```python
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient   # pip install azure-keyvault-secrets

client = SecretClient(vault_url="https://kv-lab-12345.vault.azure.net", credential=DefaultAzureCredential())
passord = client.get_secret("DbPassword").value     # ALDRI print/logg verdien i ekte kode
```

**Sammenheng.** App Service og Functions (Key Vault-referanser), AKS (Secrets Store CSI Driver), Azure Pipelines (variable groups koblet til Key Vault), GitHub Actions (hent hemmeligheter etter OIDC-innlogging), Terraform (`azurerm_key_vault_secret`), VM-diskkryptering og TLS-sertifikater til Application Gateway.

**Kostnad.** Lav: per 10 000 operasjoner, pluss per sertifikatfornyelse og høyere pris for HSM-nøkler. Det finnes også *Managed HSM* for strenge krav (dyrt).

> **Vanlig feil:** Å kalle Key Vault for hver forespørsel i en app med mye trafikk. Key Vault har **throttling-grenser**. Hent hemmeligheten ved oppstart og cache den (eller bruk Key Vault-referanser i App Service, som cacher for deg).

### Azure Monitor

**Hva den gjør.** Azure Monitor er Azures samlede plattform for **overvåking**: den samler inn, lagrer, analyserer og reagerer på **metrikker** og **logger** fra Azure-ressurser, applikasjoner, VM-er og containere.

```text
 KILDER                          DATALAGRE                 BRUK
 ┌─────────────────┐           ┌──────────────────┐      ┌──────────────────────┐
 │ Azure-ressurser │──metrics─►│ Metrics-database │─────►│ Metrics explorer     │
 │ (plattform)     │           │ (tidsserier)     │      │ Dashboards/Workbooks │
 │ Activity log    │           └──────────────────┘      │ Grafana              │
 │ VM-er (agent)   │──logs────►┌──────────────────┐─────►│ Log queries (KQL)    │
 │ Containere      │           │ Log Analytics    │      │ Alerts → Action group│
 │ Apper (App      │           │ workspace        │      │ (e-post, SMS, webhook│
 │  Insights/OTel) │           └──────────────────┘      │  Teams, Function ...)│
 └─────────────────┘                                     └──────────────────────┘
```

**Datatyper:**

- **Metrikker** – tall over tid (CPU %, forespørsler/sek, ledig disk). Lette, raske, samles inn automatisk for de fleste ressurser.
- **Logger** – hendelser med detaljer (feilmeldinger, innlogginger, HTTP-forespørsler). Lagres i Log Analytics og søkes med **KQL**.
- **Activity log** – hvem gjorde hva på kontrollplanet (opprettet, slettet, endret ressurser). Samles automatisk, oppbevares i 90 dager.
- **Traces** – sporing av forespørsler gjennom flere tjenester (kapittel 13).

**Viktige komponenter:**

- **Diagnostic settings** – sender ressurslogger og metrikker til Log Analytics, lagring eller Event Hubs. **Ressurslogger samles ikke inn før du lager en diagnostic setting.**
- **Azure Monitor Agent (AMA)** + **Data Collection Rules (DCR)** – samler logger og ytelsesdata fra VM-er. (Den gamle Log Analytics-agenten ble pensjonert i 2024.)
- **Application Insights** – overvåking av applikasjoner (forespørsler, feil, avhengigheter, ytelse), basert på OpenTelemetry.
- **Container Insights** og **Managed Prometheus** / **Azure Managed Grafana** – for AKS.
- **Alerts** + **Action groups** – varsler når noe skjer, og bestemmer hvem som får beskjed og hva som skjer.
- **Workbooks** og **dashboards** – visualisering.

**Lag et CPU-varsel på en VM:**

```bash
# Action group: hvem skal varsles
az monitor action-group create -g $RG -n ag-student --short-name agstud \
  --action email student student@example.com

VM_ID=$(az vm show -g rg-lab-nett -n vm-web01 --query id -o tsv)   # en VM du har laget
az monitor metrics alert create -g $RG -n cpu-hoy \
  --scopes "$VM_ID" \
  --condition "avg Percentage CPU > 80" \
  --window-size 5m --evaluation-frequency 1m \
  --action ag-student \
  --description "CPU over 80 % i 5 minutter"
```

Test varselet ved å stresse VM-en: `sudo apt install -y stress-ng && stress-ng --cpu 1 --timeout 600`.

**Sikkerhet og kostnad.** Plattformmetrikker og activity log er gratis. **Logginnsamling til Log Analytics koster per GB** – den største kostnadsdriveren i overvåking. Varsler koster litt per regel. Samle det du faktisk bruker.

### Log Analytics og KQL

**Hva den gjør.** Et **Log Analytics workspace** er databasen der Azure Monitor lagrer logger. Du spør i den med **KQL** (*Kusto Query Language*).

```bash
az monitor log-analytics workspace create -g $RG -n log-lab --retention-time 30

# Send logger og metrikker fra Key Vault til workspace
WS_ID=$(az monitor log-analytics workspace show -g $RG -n log-lab --query id -o tsv)
az monitor diagnostic-settings create --name diag-kv \
  --resource $(az keyvault show -n $KV --query id -o tsv) \
  --workspace "$WS_ID" \
  --logs '[{"categoryGroup":"allLogs","enabled":true}]' \
  --metrics '[{"category":"AllMetrics","enabled":true}]'
```

**KQL – grunnleggende.** En spørring starter med en **tabell**, og data sendes gjennom operatorer med `|` (som pipes i Linux):

```kusto
// Siste 50 hendelser i activity log siste døgn
AzureActivity
| where TimeGenerated > ago(1d)
| project TimeGenerated, Caller, OperationNameValue, ActivityStatusValue, ResourceGroup
| order by TimeGenerated desc
| take 50
```

```kusto
// Hvem har lest hemmeligheter i Key Vault?
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.KEYVAULT" and OperationName == "SecretGet"
| summarize antall = count() by CallerIPAddress, identity_claim_upn_s
```

```kusto
// Gjennomsnittlig CPU per VM i 5-minutters intervaller (krever Azure Monitor Agent / VM insights)
Perf
| where ObjectName == "Processor" and CounterName == "% Processor Time"
| summarize snitt_cpu = avg(CounterValue) by Computer, bin(TimeGenerated, 5m)
| render timechart
```

```kusto
// Antall HTTP 5xx-feil per time fra App Service
AppServiceHTTPLogs
| where ScStatus >= 500
| summarize feil = count() by bin(TimeGenerated, 1h)
| render columnchart
```

| KQL-operator | Gjør | SQL-ekvivalent |
|---|---|---|
| `where` | Filtrer rader | `WHERE` |
| `project` | Velg kolonner | `SELECT kol1, kol2` |
| `extend` | Lag ny kolonne | `SELECT ..., uttrykk AS ny` |
| `summarize ... by` | Aggreger | `GROUP BY` |
| `order by` / `sort by` | Sorter | `ORDER BY` |
| `take` / `limit` | Begrens antall | `TOP` / `LIMIT` |
| `join` | Koble tabeller | `JOIN` |
| `render` | Lag diagram | – |
| `ago(1h)`, `bin()` | Tid relativt til nå, gruppering i tidsintervaller | – |

**Log alerts** kjører en KQL-spørring jevnlig og varsler hvis resultatet oppfyller en betingelse (f.eks. «mer enn 10 mislykkede innlogginger på 5 minutter»).

**Sikkerhet og kostnad.** Styr tilgang med RBAC (*Log Analytics Reader*). Kostnad per innsamlet GB og for oppbevaring utover inkludert periode; ulike **tabellplaner** (Analytics, Basic, Auxiliary) gir lavere pris for logger du sjelden spør i. Sett en **daglig grense** (*daily cap*) i labmiljøer.

**Øvelse.** Send Key Vault-logger til workspace, les hemmeligheten fem ganger med `az keyvault secret show`, og finn hendelsene med KQL-spørringen over. (Det kan ta noen minutter før data dukker opp.)

### Azure Backup

**Hva den gjør.** En administrert **backup-tjeneste** for Azure-VM-er, Azure Files, SQL Server og SAP HANA på VM-er, Azure Database for PostgreSQL, blobs, AKS, disker og lokale servere.

**Hvelv:**

- **Recovery Services vault** – VM-er, Azure Files, SQL/SAP HANA i VM, lokale servere (MARS-agent).
- **Backup vault** – nyere arbeidslaster som Azure Disks, Blobs, PostgreSQL, AKS.

**Begreper:**

- **Backup policy** – hvor ofte (daglig/ukentlig, eller flere ganger daglig med *Enhanced policy*) og hvor lenge backuper beholdes.
- **Restore point** – et punkt du kan gjenopprette til.
- **Soft delete** – slettede backuper beholdes i en periode (beskytter mot ondsinnet sletting).
- **Immutable vault** og **Multi-user authorization** – ekstra beskyttelse mot at en angriper med admin-tilgang sletter backupene.
- **Cross Region Restore** – gjenopprett i den parede regionen (krever GRS på hvelvet).
- **Azure Site Recovery (ASR)** – noe annet enn backup: **replikerer** VM-er kontinuerlig til en annen region for **katastrofegjenoppretting** med lav RPO/RTO.

**Ta backup av en VM:**

```bash
az backup vault create -g $RG -n rsv-lab -l $LOC
az backup protection enable-for-vm -g $RG --vault-name rsv-lab \
  --vm $(az vm show -g rg-lab-nett -n vm-web01 --query id -o tsv) \
  --policy-name DefaultPolicy

# Ta en backup nå (i stedet for å vente på planen)
az backup protection backup-now -g $RG --vault-name rsv-lab \
  --container-name vm-web01 --item-name vm-web01 --backup-management-type AzureIaasVM
az backup job list -g $RG --vault-name rsv-lab -o table
```

Gjenoppretting kan lage en ny VM, erstatte disker, eller hente enkeltfiler (*file recovery*, monterer restore pointet som en disk).

**Bedriftseksempel.** En regnskapsbedrift tar daglig backup av alle VM-er med 30 dagers oppbevaring, månedlig med 12 måneder, og årlig med 10 år (lovkrav). Hvelvet er *immutable* slik at løsepengevirus ikke kan slette backupene.

**Kostnad.** Per beskyttet instans (etter størrelse) pluss lagring av backupdata (LRS/ZRS/GRS). **Merk:** Du kan ikke slette et Recovery Services vault som har beskyttede elementer eller soft-deleted backuper – stopp beskyttelsen og slett backupdata først. Det kan gjøre opprydding i lab tregere; se *«Delete a Recovery Services vault»* på Microsoft Learn.

> **Husk:** Test gjenoppretting jevnlig. En backup du aldri har gjenopprettet, er en antakelse – ikke en plan.

### Oppsummering av 7.3

- **Storage account** samler Blob, Files, Queue og Table; velg redundans (LRS/ZRS/GRS/GZRS) etter behov.
- **Blob** for objekter med nivåer Hot/Cool/Cold/Archive og livssyklusregler; **Files** for delte mapper over SMB/NFS.
- **Azure SQL Database** er en administrert SQL-database med automatisk backup og PITR; bruk Entra-autentisering og Private Endpoint.
- **Key Vault** lagrer hemmeligheter, nøkler og sertifikater; tilgang med RBAC og managed identity.
- **Azure Monitor** samler metrikker og logger; **Log Analytics** + **KQL** for analyse; **alerts** + **action groups** for varsling.
- **Azure Backup** beskytter data; **Site Recovery** gir DR for hele VM-er.

**Opprydding:**

```bash
# Backup-hvelv må tømmes først:
az backup protection disable -g $RG --vault-name rsv-lab --container-name vm-web01 \
  --item-name vm-web01 --backup-management-type AzureIaasVM --delete-backup-data true --yes
az group delete -n rg-lab-data --yes --no-wait
# Key Vault blir "soft-deleted" – fjern helt hvis du vil gjenbruke navnet:
az keyvault purge -n $KV
```
