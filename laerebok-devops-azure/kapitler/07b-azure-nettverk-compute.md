## 7.2 Nettverk og compute

I dette kapitlet bygger vi steg for steg denne klassiske arkitekturen, og lærer hver tjeneste underveis:

```text
                       Internett
                           │
                 ┌─────────▼──────────┐
                 │ Azure DNS          │  www.firma.no → offentlig IP
                 └─────────┬──────────┘
                 ┌─────────▼──────────┐
                 │ Application Gateway│  (lag 7, TLS, WAF)  snet-agw 10.0.0.0/24
                 │  eller Load Balancer│ (lag 4)
                 └────┬──────────┬────┘
   VNet 10.0.0.0/16   │          │
  ┌───────────────────┼──────────┼──────────────────────────┐
  │ snet-web 10.0.1.0/24  (NSG: tillat 80/443 fra LB/AGW)   │
  │      ┌────▼───┐  ┌───▼────┐                             │
  │      │ VM web1│  │ VM web2│   (i hver sin tilgjengelighetssone)
  │      └────┬───┘  └───┬────┘                             │
  │ snet-data 10.0.2.0/24 (NSG: tillat 1433 kun fra snet-web)│
  │           └────┬─────┘                                  │
  │          Private Endpoint → Azure SQL Database          │
  │ AzureBastionSubnet 10.0.250.0/26 → Azure Bastion (SSH)  │
  └─────────────────────────────────────────────────────────┘
```

Før vi starter, sett noen variabler som brukes i eksemplene (i Bash/Cloud Shell):

```bash
RG=rg-lab-nett
LOC=norwayeast
az group create -n $RG -l $LOC --tags miljø=lab eier=student
```

### Virtual Networks (VNet)

**Hva den gjør.** Et Azure Virtual Network er ditt **private nettverk i Azure**. Ressurser i samme VNet kan snakke med hverandre over private IP-adresser, isolert fra andre kunder.

**Hvorfor.** VM-er, databaser med private endepunkter, AKS og mye annet trenger et nettverk med kontrollert adresseplan, ruting og sikkerhet – akkurat som et bedriftsnett (kapittel 2), men programvaredefinert.

**Viktige egenskaper:**

- Et VNet tilhører **én region** og **ett abonnement**, men strekker seg over alle tilgjengelighetssonene i regionen.
- Har ett eller flere **adresseområder** (CIDR), typisk fra private områder som `10.0.0.0/16`.
- Deles i **subnett**.
- Trafikk mellom subnett i samme VNet rutes automatisk (systemruter).
- **VNet peering** kobler VNets sammen (også på tvers av regioner) over Microsofts nett – adresseområdene kan **ikke** overlappe. Peering er **ikke transitivt**: A↔B og B↔C betyr ikke A↔C.
- **Hub-and-spoke**: et sentralt «hub»-VNet med delte tjenester (brannmur, VPN-gateway, Bastion) og flere «spoke»-VNets for arbeidslastene, koblet med peering. Det vanligste bedriftsoppsettet.

**Bedriftseksempel.** En kommune har ett hub-VNet koblet til rådhusets nett med VPN, og egne spoke-VNets for saksbehandlingssystemet og innbyggerportalen. All trafikk ut til internett går via Azure Firewall i huben.

**Opprett:**

```bash
az network vnet create -g $RG -n vnet-lab \
  --address-prefix 10.0.0.0/16 \
  --subnet-name snet-web --subnet-prefixes 10.0.1.0/24
```

**Portal:** *Virtual networks → + Create* → velg ressursgruppe, navn og region → fanen *IP addresses*: adresseområde og subnett → *Review + create*.

**Sikkerhet og kostnad.** Selve VNet-et og subnettene er gratis. Du betaler for ting du kobler til (gatewayer, offentlige IP-er, NAT Gateway, Firewall) og for trafikk over **peering** (per GB).

**Sammenheng.** Nesten alt av IaaS lever i et VNet. PaaS-tjenester (SQL, Storage, Key Vault) kobles inn med **Private Endpoints** eller **service endpoints**; App Service og Functions kan sende trafikk *inn* i et VNet med **VNet integration**.

### Subnett

**Hva den gjør.** Et subnett er en del av VNet-ets adresseområde. Ressurser plasseres i subnett, og sikkerhet (NSG) og ruting (route tables) knyttes ofte til subnettet.

**Viktige regler:**

- Azure reserverer **5 adresser** i hvert subnett (kapittel 2).
- Noen tjenester krever **dedikerte subnett med bestemte navn eller størrelser**: `GatewaySubnet` (VPN/ExpressRoute Gateway), `AzureBastionSubnet` (minst `/26`), `AzureFirewallSubnet` (minst `/26`), Application Gateway (eget subnett).
- **Subnet delegation** gir en tjeneste (f.eks. App Service VNet integration, Container Apps) rett til å bruke subnettet.

```bash
az network vnet subnet create -g $RG --vnet-name vnet-lab -n snet-data --address-prefixes 10.0.2.0/24
az network vnet subnet create -g $RG --vnet-name vnet-lab -n AzureBastionSubnet --address-prefixes 10.0.250.0/26
az network vnet subnet list -g $RG --vnet-name vnet-lab -o table
```

> **Vanlig feil:** Å bruke hele VNet-et til ett subnett (`10.0.0.0/16` både som VNet og subnett). Da er det ikke plass til flere subnett senere. Legg igjen ledig adresserom.

> **Merk – utgående internettilgang:** Microsoft har faset ut «default outbound access» for nye virtuelle nettverk: nye subnett blir private som standard, og VM-er uten offentlig IP, NAT Gateway, lastbalanserer med utgående regler eller brannmur får da ikke automatisk tilgang ut til internett. Sjekk Microsoft Learn («Default outbound access for VMs in Azure») for nøyaktig status og datoer. Får en VM ikke installert pakker med `apt`, er dette en vanlig årsak.

### Network Security Groups (NSG)

**Hva den gjør.** En NSG er en **tilstandsbasert brannmur** (*stateful*) på lag 3/4 med regler som tillater eller avviser trafikk basert på kilde, mål, port og protokoll. Knyttes til et **subnett** og/eller et **nettverkskort (NIC)**.

**Hvordan reglene evalueres:**

- Hver regel har en **prioritet** fra 100 til 4096. **Lavest tall evalueres først**, og første treff vinner.
- Separate regler for **inngående** og **utgående** trafikk.
- *Stateful*: hvis inngående trafikk er tillatt, er svaret automatisk tillatt.
- Standardregler (prioritet 65000+) som du ikke kan slette, men kan overstyre:

| Retning | Standardregel | Effekt |
|---|---|---|
| Inn | AllowVnetInBound | Tillat trafikk innen VNet (og peerede VNets) |
| Inn | AllowAzureLoadBalancerInBound | Tillat helsesjekker fra Azure Load Balancer |
| Inn | DenyAllInBound | **Avvis alt annet** |
| Ut | AllowVnetOutBound | Tillat til VNet |
| Ut | AllowInternetOutBound | Tillat ut til internett |
| Ut | DenyAllOutBound | Avvis alt annet |

- **Service tags** er navn på grupper av IP-adresser som Microsoft vedlikeholder: `Internet`, `VirtualNetwork`, `AzureLoadBalancer`, `Storage`, `Sql.NorwayEast`, `AzureCloud` …
- **Application Security Groups (ASG)** lar deg gruppere VM-er logisk («webservere») og bruke gruppen i regler i stedet for IP-adresser.
- Hvis det er NSG både på subnett og NIC, må trafikken tillates av **begge**.

```text
 Inngående: Internett → [NSG på subnett] → [NSG på NIC] → VM
 Utgående:  VM → [NSG på NIC] → [NSG på subnett] → ...
```

**Opprett og knytt til subnett:**

```bash
az network nsg create -g $RG -n nsg-web

# Tillat HTTP og HTTPS fra internett
az network nsg rule create -g $RG --nsg-name nsg-web -n allow-web \
  --priority 100 --direction Inbound --access Allow --protocol Tcp \
  --source-address-prefixes Internet --destination-port-ranges 80 443

# Knytt NSG-en til subnettet
az network vnet subnet update -g $RG --vnet-name vnet-lab -n snet-web --network-security-group nsg-web

# Database-subnett: bare SQL fra web-subnettet
az network nsg create -g $RG -n nsg-data
az network nsg rule create -g $RG --nsg-name nsg-data -n allow-sql-from-web \
  --priority 100 --direction Inbound --access Allow --protocol Tcp \
  --source-address-prefixes 10.0.1.0/24 --destination-port-ranges 1433
az network vnet subnet update -g $RG --vnet-name vnet-lab -n snet-data --network-security-group nsg-data
```

**Feilsøking.** *Network Watcher → IP flow verify* svarer på «blir denne pakken tillatt, og av hvilken regel?». *Effective security rules* på et nettverkskort viser de samlede reglene. Flow logs kan sendes til lagring/Log Analytics.

**Sikkerhet og kostnad.** NSG-er er gratis. Åpne aldri 22/3389 mot `Internet`; bruk Bastion eller begrens til din IP (`--source-address-prefixes <din-ip>/32`).

**Øvelse.** Lag en regel med prioritet 90 som **avviser** port 80 fra internett. Hva skjer med `allow-web` på prioritet 100? Bekreft med *IP flow verify*. (Svar: prioritet 90 vinner, port 80 avvises, 443 tillates fortsatt.)

### Azure Virtual Machines

**Hva den gjør.** En Azure VM er en **virtuell server** (IaaS) med Linux eller Windows, der du har full kontroll over operativsystemet.

**Hvorfor.** Når du trenger full kontroll: spesiell programvare, eldre applikasjoner som flyttes fra eget datasenter («lift and shift»), egne agenter, eller arbeidslaster som ikke passer i PaaS.

**Bestanddeler av en VM:**

```text
 VM ─┬─ størrelse (vCPU, RAM)          f.eks. Standard_B2s, Standard_D2s_v5
     ├─ image (OS)                      Ubuntu 24.04, Windows Server 2025 ...
     ├─ OS-disk (managed disk)          Standard HDD / Standard SSD / Premium SSD
     ├─ datadisker (valgfritt)
     ├─ nettverkskort (NIC) → subnett   privat IP, ev. NSG
     ├─ offentlig IP (valgfritt)
     └─ identitet, extensions, boot diagnostics, sikkerhetstype (Trusted Launch)
```

**VM-størrelser – familier:**

| Serie | Profil | Typisk bruk |
|---|---|---|
| B | *Burstable* – billig, bygger opp CPU-kreditt | Test, små webservere, lav jevn last |
| D | Generell bruk, balansert | De fleste applikasjoner |
| E | Mye minne | Databaser, cache |
| F | Mye CPU | Beregninger, batch |
| L | Lagringsoptimalisert | Store, raske lokale disker |
| N (NC, ND, NV) | GPU | AI, grafikk (kapittel 14) |

Navnet `Standard_D4s_v5` leses: familie **D**, **4** vCPU, **s** = støtter Premium SSD, versjon **5**.

**Disker:** Standard HDD (billigst, treg) → Standard SSD → Premium SSD → Premium SSD v2 / Ultra Disk (raskest). Diskene er **managed disks** – Azure håndterer lagringen og replikerer dem.

**Tilgjengelighet for VM-er:**

| Alternativ | Beskytter mot | 
|---|---|
| Én VM med Premium SSD | Ingenting utover maskinvarefeil-flytting – lavest SLA |
| **Availability set** | Feil på ett rack/én vert (fault domains) og planlagt vedlikehold (update domains) i samme datasenter |
| **Availability zones** | Feil på et helt datasenter |
| **Virtual Machine Scale Sets (VMSS)** | Automatisk skalering av mange like VM-er, ofte over flere soner |

**Opprett en Linux-VM med nginx:**

```bash
az vm create -g $RG -n vm-web01 \
  --image Ubuntu2404 \
  --size Standard_B1s \
  --vnet-name vnet-lab --subnet snet-web \
  --admin-username azureuser \
  --generate-ssh-keys \
  --public-ip-sku Standard \
  --nsg ""
# --image Ubuntu2404: alias for Ubuntu Server 24.04 LTS (list aliaser med: az vm image list -o table)
# --generate-ssh-keys: bruker ~/.ssh/id_rsa.pub eller lager et nytt nøkkelpar
# --nsg "": ikke lag egen NSG på NIC – vi bruker NSG-en på subnettet
# Resultatet viser publicIpAddress
```

Installer nginx uten å logge inn (Run Command):

```bash
az vm run-command invoke -g $RG -n vm-web01 --command-id RunShellScript \
  --scripts "sudo apt-get update && sudo apt-get install -y nginx"

curl http://<publicIpAddress>          # Welcome to nginx!
```

Alternativt kan du gi **cloud-init** ved opprettelse (`--custom-data cloud-init.yaml`) – en fil som kjøres ved første oppstart:

```yaml
#cloud-config
package_update: true
packages:
  - nginx
runcmd:
  - echo "Hei fra $(hostname)" > /var/www/html/index.html
```

**Daglig drift:**

```bash
az vm stop -g $RG -n vm-web01          # stopper OS – du BETALER FORTSATT for compute!
az vm deallocate -g $RG -n vm-web01    # frigjør maskinvaren – compute koster ikke
az vm start -g $RG -n vm-web01
az vm resize -g $RG -n vm-web01 --size Standard_B2s
az vm auto-shutdown -g $RG -n vm-web01 --time 1900   # slå av kl. 19:00 UTC hver dag
az vm list -d -g $RG -o table          # -d viser IP og strømstatus
```

> **Vanlig feil:** *Stopped* vs. *Stopped (deallocated)*. Slår du av VM-en fra innsiden av OS-et (`sudo shutdown`), står den som «Stopped» og **koster fortsatt**. Bruk **Stop** i portalen eller `az vm deallocate`.

**Sikker innlogging med Azure Bastion.** Bastion gir SSH/RDP til VM-er via portalen eller CLI **uten offentlig IP på VM-en**. Det finnes flere SKU-er; *Developer*-SKU er gratis, men har begrensninger og er ikke tilgjengelig i alle regioner. Basic/Standard faktureres per time. Alternativt: **Just-In-Time VM access** i Microsoft Defender for Cloud åpner porten bare midlertidig.

**Sikkerhet:**

- SSH-nøkler, ikke passord. Ingen åpen 22 mot internett.
- **Trusted Launch** (Secure Boot + vTPM) er standard for nye VM-er der det støttes.
- Hold OS-et oppdatert – **Azure Update Manager** kan planlegge patching.
- Diskkryptering er på som standard (server-side encryption med plattformnøkler).
- Gi VM-en en **managed identity** i stedet for å lagre nøkler på den.

**Kostnad.** Du betaler per sekund VM-en er allokert (størrelse + eventuell OS-lisens), pluss disker (alltid, også når VM-en er deallokert), offentlig IP, og utgående trafikk. Azure free account har inkludert begrenset bruk av enkelte små B-serie-VM-er de første 12 månedene – sjekk gjeldende liste. **B1s** er billig, men har bare 1 GiB RAM.

**Øvelse.** Opprett `vm-web01` som over, installer nginx, endre `index.html`, deallokér VM-en, sjekk i *Cost analysis* dagen etter hva den kostet. Slett ressursgruppen når du er ferdig.

**Sammenheng.** VM-er lever i VNet/subnett, beskyttes av NSG, får trafikk fra Load Balancer/Application Gateway, overvåkes av Azure Monitor (via Azure Monitor Agent), sikkerhetskopieres av Azure Backup, og bygges ofte med Terraform/Bicep.

### Azure Load Balancer

**Hva den gjør.** En **lag 4**-lastbalanserer (TCP/UDP) som fordeler trafikk til et **backend pool** av VM-er eller VMSS-instanser, basert på **helsesjekker** (*health probes*).

**Typer:**

- **Public** – har offentlig IP, tar trafikk fra internett.
- **Internal** – har privat IP, fordeler trafikk inne i VNet-et (f.eks. til app-laget).

**SKU-er:** Bruk **Standard**. Basic-SKU ble pensjonert i september 2025. Standard er sikker som standard (*secure by default*): trafikk må eksplisitt tillates med NSG, og den støtter tilgjengelighetssoner.

**Bestanddeler:**

```text
 Frontend IP ──► Load balancing rule (port 80 → 80) ──► Backend pool [vm1, vm2]
                          │
                    Health probe (HTTP GET / på port 80 hvert 5. s)
 (+ inbound NAT rules for å nå enkelt-VM-er, + outbound rules for utgående trafikk)
```

**Opprett:**

```bash
az network public-ip create -g $RG -n pip-lb --sku Standard --zone 1 2 3

az network lb create -g $RG -n lb-web --sku Standard \
  --public-ip-address pip-lb --frontend-ip-name fe-web --backend-pool-name be-web

az network lb probe create -g $RG --lb-name lb-web -n probe-http \
  --protocol Http --port 80 --path /

az network lb rule create -g $RG --lb-name lb-web -n rule-http \
  --protocol Tcp --frontend-port 80 --backend-port 80 \
  --frontend-ip-name fe-web --backend-pool-name be-web --probe-name probe-http

# Legg VM-ens nettverkskort i backend pool (az vm create kaller NIC-en <vm>VMNic
# og IP-konfigurasjonen ipconfig<vm>)
az network nic ip-config address-pool add -g $RG \
  --nic-name vm-web01VMNic --ip-config-name ipconfigvm-web01 \
  --lb-name lb-web --address-pool be-web
```

**Bedriftseksempel.** Tre VM-er med et eldre Java-system i tre soner bak en Standard Load Balancer. Når én sone har problemer, slutter helsesjekken å svare, og trafikken går til de to andre.

**Sikkerhet og kostnad.** Standard Load Balancer faktureres per regel og per behandlet datamengde. NSG på backend må tillate både klienttrafikken og `AzureLoadBalancer` (helsesjekkene, tillatt i standardreglene).

**Øvelse.** Lag to VM-er (`vm-web01`, `vm-web02`) med hver sin `index.html` som viser maskinnavnet. Legg begge i backend-poolen og kjør `curl http://<lb-ip>` flere ganger. Stopp nginx på én av dem – hva skjer?

### Application Gateway

**Hva den gjør.** En **lag 7**-lastbalanserer for HTTP/HTTPS med:

- **URL-basert ruting** (`/api/*` → API-servere, `/bilder/*` → bildeservere),
- **flere nettsteder** på samme gateway (*multi-site*, basert på vertsnavn),
- **TLS-terminering** og ende-til-ende-TLS,
- **Web Application Firewall (WAF)** mot vanlige angrep (OWASP-regler),
- autoskalering, tilgjengelighetssoner, omskriving av headers og omdirigering (http → https).

**Bestanddeler:** frontend-IP → **listener** (port/protokoll/vertsnavn/sertifikat) → **routing rule** → **backend pool** + **backend settings** (port, protokoll, timeout, helsesjekk).

**Hvorfor velge Application Gateway over Load Balancer?** Når du trenger å forstå HTTP: ruting på sti/vertsnavn, TLS-håndtering eller WAF. For ren TCP/UDP-trafikk holder Load Balancer.

**Relaterte tjenester:**

| Tjeneste | Lag | Rekkevidde | Typisk bruk |
|---|---|---|---|
| Load Balancer | 4 | Regional | TCP/UDP til VM-er |
| Application Gateway | 7 | Regional | Webapper i ett VNet, WAF |
| Azure Front Door | 7 | **Global** (Microsofts kantnett) | Globale nettsteder, CDN, WAF, failover mellom regioner |
| Traffic Manager | DNS | Global | DNS-basert fordeling mellom regioner |

**Opprett (forenklet – krever eget subnett):**

```bash
az network vnet subnet create -g $RG --vnet-name vnet-lab -n snet-agw --address-prefixes 10.0.0.0/24
az network public-ip create -g $RG -n pip-agw --sku Standard

az network application-gateway create -g $RG -n agw-web \
  --sku Standard_v2 --capacity 1 \
  --vnet-name vnet-lab --subnet snet-agw \
  --public-ip-address pip-agw \
  --frontend-port 80 --http-settings-port 80 --http-settings-protocol Http \
  --servers 10.0.1.4 10.0.1.5 \
  --priority 100
```

(`--servers` er de private IP-ene til VM-ene. Opprettelsen tar ofte flere minutter.) For læring er **portalen** ofte enklere her: *Application gateways → + Create*, og veiviseren går gjennom frontend, backend og routing rule.

**Sikkerhet og kostnad.** v2-SKU-ene faktureres per time pluss kapasitetsenheter. **WAF_v2** koster mer. Dette er en av ressursene studenter ofte glemmer – slett den etter øvelsen.

> **Vanlig feil:** **502 Bad Gateway** fra Application Gateway betyr nesten alltid at backend er usunn: appen kjører ikke, NSG blokkerer, feil port i backend settings, eller helsesjekken går mot en sti som ikke returnerer 200–399. Se *Backend health* i portalen.

### Azure DNS

**Hva den gjør.** Azure DNS hoster **DNS-soner** (kapittel 2) i Azure, slik at du administrerer DNS-poster med samme verktøy, RBAC og automatisering som resten av infrastrukturen.

**To typer:**

- **Public DNS zones** – for domener på internett (`firma.no`). Du kjøper domenet hos en registrar og peker NS-postene til Azures navneservere.
- **Private DNS zones** – navneoppslag **inne i VNets** (`intern.firma.no`, eller `privatelink.database.windows.net` for private endepunkter). Knyttes til VNets med *virtual network links*, og kan registrere VM-navn automatisk.

**Opprett:**

```bash
az network dns zone create -g $RG -n lab-eksempel.no
az network dns record-set a add-record -g $RG -z lab-eksempel.no -n www -a <offentlig-ip>
az network dns record-set cname set-record -g $RG -z lab-eksempel.no -n app -c minapp.azurewebsites.net
az network dns zone show -g $RG -n lab-eksempel.no --query nameServers   # legg disse inn hos registraren

# Privat sone for et VNet
az network private-dns zone create -g $RG -n intern.lab
az network private-dns link vnet create -g $RG -z intern.lab -n link-lab \
  --virtual-network vnet-lab --registration-enabled true
```

**Alias-poster** kan peke direkte på en Azure-ressurs (offentlig IP, Front Door, Traffic Manager), og oppdateres automatisk hvis IP-en endres. De kan også brukes på **sone-toppen** (`firma.no` uten `www`), der vanlig CNAME ikke er lov.

**Kostnad.** Lav: per sone per måned og per million spørringer.

**Sammenheng.** Private DNS zones er **avgjørende** for Private Endpoints: når en app slår opp `minserver.database.windows.net`, må svaret bli den private IP-en, ellers går trafikken mot den offentlige adressen.

### Azure App Service

**Hva den gjør.** App Service er en **PaaS for webapplikasjoner og API-er**. Du gir koden (Python, Node.js, .NET, Java, PHP) eller en container, og Azure drifter servere, OS, patching, lastbalansering og skalering.

**Hvorfor.** Mye mindre drift enn VM-er, innebygd HTTPS, egne domener, autoskalering, *deployment slots*, integrasjon med GitHub Actions og Azure DevOps, og innebygd autentisering («Easy Auth»).

**Bestanddeler:**

```text
 App Service Plan (maskinene – du betaler for planen)
 ├── Web App 1   (minapp.azurewebsites.net)
 ├── Web App 2
 └── ...   ← flere apper kan dele samme plan og dermed samme kapasitet
```

**App Service Plan-nivåer (forenklet):**

| Nivå | Typisk bruk | Merk |
|---|---|---|
| Free (F1) / Shared (D1) | Læring | Begrenset CPU-tid, ingen SLA, ingen egendefinerte TLS-sertifikater / slots |
| Basic (B1–B3) | Små apper, test | Egne domener, manuell skalering |
| Standard (S1–S3) | Produksjon | Autoskalering, deployment slots |
| Premium v3 / v4 (P*v3/v4) | Krevende produksjon | Raskere maskiner, flere slots, bedre skalering |
| Isolated v2 (App Service Environment) | Strenge krav om isolasjon | Dedikert miljø i eget VNet |

(Sjekk gjeldende nivåer og funksjoner på Microsoft Learn – nye generasjoner introduseres jevnlig.)

**Opprett og deploy en Python-app:**

```bash
# Enkel Flask-app lokalt:
mkdir flaskapp && cd flaskapp
cat > app.py <<'EOF'
from flask import Flask
app = Flask(__name__)

@app.route("/")
def hjem():
    return "Hei fra Azure App Service!"

@app.route("/health")
def health():
    return {"status": "ok"}
EOF
echo "flask" > requirements.txt

# Én kommando: lager plan, web app og deployer koden
az webapp up --name app-lab-<unik> --resource-group $RG --location $LOC \
  --runtime "PYTHON:3.12" --sku F1

curl https://app-lab-<unik>.azurewebsites.net
```

(`az webapp list-runtimes --os linux` viser gyldige runtime-verdier.)

**Konfigurasjon og drift:**

```bash
az webapp config appsettings set -g $RG -n app-lab-<unik> --settings APP_ENV=test   # blir miljøvariabler
az webapp log config -g $RG -n app-lab-<unik> --application-logging filesystem --docker-container-logging filesystem
az webapp log tail -g $RG -n app-lab-<unik>      # live logger
az webapp restart -g $RG -n app-lab-<unik>
```

**Deployment slots** (Standard og høyere): du deployer til en `staging`-slot, tester den på `minapp-staging.azurewebsites.net`, og gjør en **swap** – produksjon og staging bytter plass nesten uten nedetid. Går noe galt, swapper du tilbake. Dette er blue-green deployment (kapittel 12).

```bash
az webapp deployment slot create -g $RG -n app-lab-<unik> --slot staging
az webapp deployment slot swap -g $RG -n app-lab-<unik> --slot staging --target-slot production
```

**Hemmeligheter:** Bruk **Key Vault-referanser** i app settings, kombinert med managed identity:

```text
DB_PASSWORD = @Microsoft.KeyVault(VaultName=kv-lab-<unik>;SecretName=DbPassword)
```

**Sikkerhet:** Slå på *HTTPS Only*, minimum TLS 1.2, managed identity, og vurder *Access restrictions* og Private Endpoints. **Kostnad:** du betaler for **planen**, ikke per app. F1 er gratis med begrensninger.

**Øvelse.** Deploy Flask-appen, sett app setting `APP_ENV`, og endre appen til å vise verdien (`os.environ.get("APP_ENV")`). Se loggene med `az webapp log tail`.

**Sammenheng.** Kode fra GitHub → GitHub Actions/Azure Pipelines → App Service. Henter hemmeligheter fra Key Vault via managed identity. Snakker med Azure SQL via VNet integration + Private Endpoint. Overvåkes med Application Insights.

### Azure Functions

**Hva den gjør.** Azure Functions er **serverless** kode som kjører når en **trigger** skjer: HTTP-kall, en tidsplan, en fil i Blob Storage, en melding i en kø, en hendelse i Event Grid. Du skriver bare funksjonen.

**Hvorfor.** For små, hendelsesdrevne oppgaver er det svært effektivt: ingen servere, automatisk skalering (også til null), og du betaler for faktisk bruk på serverless-planene.

**Begreper:**

- **Trigger** – hva som starter funksjonen (nøyaktig én per funksjon).
- **Bindings** – deklarative koblinger til data inn/ut (les fra en kø, skriv til Blob) uten egen tilkoblingskode.
- **Function App** – beholderen for én eller flere funksjoner, med felles konfigurasjon.

**Hosting-planer (forenklet):**

| Plan | Egenskaper |
|---|---|
| **Flex Consumption** | Serverless, skalerer til null, raskere skalering og VNet-støtte – Microsofts anbefalte serverless-plan for nye apper |
| Consumption (klassisk) | Serverless; Microsoft har kunngjort utfasing av Linux-varianten – sjekk Learn |
| Premium | Forhåndsoppvarmede instanser (ingen kaldstart), VNet, lengre kjøretid |
| Dedicated (App Service Plan) | Kjører på en App Service Plan du allerede betaler for |
| Container Apps | Functions i Azure Container Apps-miljø |

**Eksempel – HTTP-funksjon i Python (programmeringsmodell v2):**

```python
# function_app.py
import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

@app.route(route="hei")                                   # HTTP-trigger på /api/hei
def hei(req: func.HttpRequest) -> func.HttpResponse:
    navn = req.params.get("navn", "verden")               # les ?navn=... fra URL-en
    return func.HttpResponse(f"Hei, {navn}!", status_code=200)

@app.timer_trigger(schedule="0 0 6 * * *", arg_name="timer")   # hver dag 06:00 UTC (6 felt: sek min time ...)
def morgenjobb(timer: func.TimerRequest) -> None:
    print("God morgen! Her kunne vi ryddet opp i gamle ressurser.")
```

**Lokalt og deploy** (krever Azure Functions Core Tools):

```bash
func init funcapp --python && cd funcapp     # lag prosjekt
# lim inn koden over i function_app.py
func start                                   # kjør lokalt: http://localhost:7071/api/hei?navn=Kari

az storage account create -n stfunc<unik> -g $RG -l $LOC --sku Standard_LRS
az functionapp create -g $RG -n func-lab-<unik> --storage-account stfunc<unik> \
  --flex-consumption-location <region-som-støtter-flex> --runtime python --runtime-version 3.12
func azure functionapp publish func-lab-<unik>
```

(`az functionapp list-flexconsumption-locations -o table` viser hvilke regioner som støtter Flex Consumption.)

> **Vanlig feil:** Timer-triggere i Functions bruker **seks felt** (med sekunder først), i motsetning til vanlig cron med fem. `0 */5 * * * *` = hvert 5. minutt.

**Sikkerhet og kostnad.** Serverless-planene har en månedlig gratiskvote for kjøringer og ressursbruk; over det betales per bruk. Function App trenger en lagringskonto (koster litt). Bruk managed identity mot andre tjenester og *function keys* eller Entra-autentisering for HTTP-funksjoner som ikke skal være åpne.

**Bedriftseksempel.** Når en kunde laster opp en PDF-faktura til Blob Storage, starter en Function som leser fakturaen, lagrer data i databasen og legger en melding i en kø til regnskapssystemet.

### Azure Container Registry (ACR)

**Hva den gjør.** Et **privat register for container-images** (og andre OCI-artefakter som Helm-charts). Som Docker Hub, men privat, i din Azure-tenant, og integrert med Entra ID.

**Hvorfor.** Produksjonsimages skal ikke ligge åpent. ACR gir tilgangsstyring, nærhet til AKS/App Service (raskere nedlasting), geo-replikering og sårbarhetsskanning (via Microsoft Defender for Containers).

**SKU-er:** Basic (læring/små), Standard, Premium (geo-replikering, private endepunkter, mer lagring og ytelse).

**Opprett og bruk:**

```bash
az acr create -g $RG -n acrlab<unik> --sku Basic       # navnet må være globalt unikt, kun bokstaver/tall
az acr login -n acrlab<unik>                          # logger Docker inn i registeret

docker build -t acrlab<unik>.azurecr.io/flaskapp:v1 .
docker push acrlab<unik>.azurecr.io/flaskapp:v1

# Alternativ: bygg i skyen uten lokal Docker (ACR Tasks)
az acr build -r acrlab<unik> -t flaskapp:v1 .

az acr repository list -n acrlab<unik> -o table
az acr repository show-tags -n acrlab<unik> --repository flaskapp -o table
```

> **Merk:** ACR Tasks (`az acr build`) kan være begrenset på enkelte gratis- og studentabonnementer. Får du en feilmelding om dette, bygg lokalt med Docker og bruk `docker push`.

**Sikkerhet.** Slå **av** admin-brukeren (standard). Gi AKS/App Service tilgang med managed identity og rollen **AcrPull**; gi CI/CD-pipelinen **AcrPush**. **Kostnad:** fast pris per dag per SKU, pluss lagring utover inkludert mengde.

**Sammenheng.** CI bygger image → push til ACR → App Service / Container Apps / AKS henter derfra.

### Azure Kubernetes Service (AKS)

**Hva den gjør.** AKS er Azures **administrerte Kubernetes**. Microsoft drifter kontrollplanet (API-server, etcd, scheduler); du administrerer nodene (VM-er) og arbeidslastene. Kubernetes forklares grundig i kapittel 10 – her ser vi på Azure-siden.

**Hvorfor.** Kubernetes er standarden for å kjøre mange containere i produksjon med selvreparasjon, skalering og rullerende oppdateringer. Å drifte kontrollplanet selv er krevende; AKS tar den jobben.

**Bestanddeler:**

```text
 AKS-cluster
 ├── Kontrollplan (administrert av Microsoft; Free/Standard/Premium-tier)
 ├── System node pool (VM-er for systemkomponenter, f.eks. CoreDNS)
 ├── User node pool(s) (VM-er for dine apper; kan skalere, kan være spot/GPU)
 ├── Nettverk: Azure CNI (Overlay) / kubenet (eldre), i et VNet
 ├── Identitet: managed identity for clusteret, Entra ID-innlogging, Workload Identity for pods
 └── Integrasjoner: ACR, Key Vault (CSI-driver), Azure Monitor (Container Insights), Azure Policy
```

**Opprett (minimalt lab-cluster):**

```bash
az aks create -g $RG -n aks-lab \
  --tier free \
  --node-count 1 --node-vm-size Standard_B2s \
  --generate-ssh-keys \
  --attach-acr acrlab<unik>
# --attach-acr gir clusterets identitet AcrPull på registeret

az aks get-credentials -g $RG -n aks-lab        # skriver kubeconfig for kubectl
kubectl get nodes
```

(`Standard_B2s` holder for læring; produksjon bruker typisk D-serien og minst tre noder spredt over soner. Velg en størrelse som er tilgjengelig i regionen og innenfor kvoten din: `az vm list-skus -l $LOC --resource-type virtualMachines -o table`.)

**AKS Automatic** er en variant der Microsoft også håndterer mye av nodehåndteringen, skalering og sikkerhetsinnstillinger med anbefalte standarder – et godt valg for team som vil ha Kubernetes med mindre drift.

**Sikkerhet:** Entra ID-integrasjon og Kubernetes RBAC, Workload Identity for pods, nettverkspolicyer, private clustere, Azure Policy for Kubernetes, oppdater Kubernetes-versjonen jevnlig (Kubernetes-versjoner har begrenset støttetid i AKS).

**Kostnad.** Kontrollplanet er gratis i *Free*-tier (uten SLA); *Standard*-tier koster per cluster-time og gir SLA. **Nodene er vanlige VM-er** og faktureres som det – det er der kostnaden ligger. Stopp clusteret når du ikke bruker det:

```bash
az aks stop -g $RG -n aks-lab      # stopper nodene (og kontrollplanet)
az aks start -g $RG -n aks-lab
```

**Alternativer som ofte er bedre for små team:** **Azure Container Apps** (serverless containere basert på Kubernetes-teknologi, uten at du ser Kubernetes; skalerer til null) og **App Service for containere**. Velg AKS når du trenger full Kubernetes.

### Oppsummering av 7.2

- **VNet** er ditt private nettverk; **subnett** deler det; **NSG** filtrerer trafikk etter prioritet.
- **VM** = IaaS med full kontroll. Husk *deallocate* for å slutte å betale for compute.
- **Load Balancer** (lag 4) og **Application Gateway** (lag 7, WAF) fordeler trafikk; **Front Door** er global.
- **Azure DNS** hoster offentlige og private soner; private soner er nødvendige for private endepunkter.
- **App Service** (PaaS for web) og **Functions** (serverless) gir mye mindre drift enn VM-er.
- **ACR** lagrer container-images; **AKS** kjører dem med Kubernetes.

**Opprydding:**

```bash
az group delete -n rg-lab-nett --yes --no-wait
```
