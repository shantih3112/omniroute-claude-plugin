# Del 6 – Cloud Computing fra A til Å

**Læringsmål for kapitlet.** Når du er ferdig, skal du kunne:

- forklare hva Cloud Computing er, og hvordan skyen fungerer fysisk,
- sammenligne sky og egne datasentre (*on-premises*),
- skille mellom public, private og hybrid cloud, og mellom IaaS, PaaS og SaaS,
- forklare regioner, tilgjengelighetssoner, skalering, høy tilgjengelighet, feiltoleranse og katastrofegjenoppretting,
- forstå prismodeller, kostnadsoptimalisering og modellen for delt ansvar,
- sammenligne AWS, Azure og Google Cloud.

## Hva er Cloud Computing?

**Hva er det?** Cloud Computing (skytjenester) er å **leie IT-ressurser over internett** – servere, lagring, databaser, nettverk, programvare, AI – i stedet for å eie og drifte dem selv. Du betaler for det du bruker, og kan få mer eller mindre på minutter.

**Hvorfor finnes det?** Før skyen måtte en bedrift som trengte en ny server:

1. få budsjett godkjent,
2. bestille maskinvare (ukers leveringstid),
3. montere den i et serverrom med strøm, kjøling og nettverk,
4. installere og sikre operativsystemet,
5. drifte og bytte deler i årevis – også når den sto ubrukt.

Og de måtte kjøpe nok kapasitet for **toppen** (julehandelen), selv om den bare trengtes noen uker i året.

> **Hverdagsanalogi:** Strøm. For hundre år siden hadde fabrikker egne generatorer. I dag kobler du deg til strømnettet og betaler for kilowattimene du bruker. Skyen gjør det samme med datakraft: du trenger ikke eie kraftverket.

### NIST-definisjonen – fem kjennetegn

Det amerikanske standardiseringsinstituttet NIST definerer skyen med fem egenskaper. De dukker ofte opp på eksamen:

| Egenskap | Betyr |
|---|---|
| **On-demand self-service** | Du kan selv opprette ressurser når du vil, uten å ringe noen |
| **Broad network access** | Tilgjengelig over nettverk fra mange typer enheter |
| **Resource pooling** | Leverandøren deler store mengder maskinvare mellom mange kunder |
| **Rapid elasticity** | Kapasiteten kan økes og minskes raskt, ofte automatisk |
| **Measured service** | Bruken måles, og du betaler for det du bruker |

## Hvordan fungerer skyen fysisk?

Skyen er ikke magisk eller «i lufta». Den er **andres datamaskiner i enorme datasentre**.

```text
 GEOGRAFI (f.eks. Europa)
 └── REGION (f.eks. Norway East – Oslo-området)
      ├── TILGJENGELIGHETSSONE 1  ┌──────────────┐  ← ett eller flere datasentre
      │                          │ DATASENTER   │     med egen strøm, kjøling
      │                          │ ┌──┬──┬──┬──┐│     og nettverk
      │                          │ │R1│R2│R3│..││  ← rack med servere
      │                          │ └──┴──┴──┴──┘│
      │                          └──────────────┘
      ├── TILGJENGELIGHETSSONE 2  (fysisk adskilt, kilometer unna)
      └── TILGJENGELIGHETSSONE 3
            ▲  koblet sammen med raske, private fiberforbindelser
```

### Datasentre

Et datasenter er en bygning full av servere i **rack** (stativer), med:

- **Strøm**: flere uavhengige strømtilførsler, UPS-batterier og dieselaggregater.
- **Kjøling**: servere produserer enorme mengder varme. Nordiske datasentre utnytter kald luft og vann.
- **Nettverk**: flere fiberforbindelser til internett og mellom datasentrene.
- **Sikkerhet**: adgangskontroll, vakter, kameraer, ofte biometriske lås.
- **Automatisering**: programvare som overvåker maskinvaren og flytter arbeidslaster når noe feiler.

Når du oppretter en VM, finner skyens **kontrollplan** (*control plane*) en fysisk server med ledig kapasitet, og hypervisoren starter VM-en din der (kapittel 1). Du ser bare resultatet: en IP-adresse og en innlogging.

> **Fra arbeidslivet:** Microsoft har regioner i Norge: **Norway East** (Oslo-området) og **Norway West** (Stavanger-området, begrenset tilgang, brukt bl.a. for katastrofegjenoppretting). Norske virksomheter velger ofte Norway East for lav forsinkelse og for å holde data i Norge. Sjekk alltid hvilke tjenester som finnes i hvilken region – ikke alle tjenester er tilgjengelige overalt.

## Sky vs. on-premises

**On-premises** («on-prem») betyr at bedriften eier og drifter maskinvaren selv, i eget serverrom eller i et leid datasenter (*colocation*).

| | On-premises | Sky |
|---|---|---|
| Oppstartskostnad | Høy (kjøpe maskinvare) | Lav (ingen investering) |
| Kostnadstype | **CapEx** – kapitalutgift, investering | **OpEx** – driftsutgift, løpende |
| Tid til ny server | Uker–måneder | Minutter |
| Skalering | Må kjøpe for toppen | Skaler opp og ned etter behov |
| Vedlikehold av maskinvare | Deg | Leverandøren |
| Kontroll | Full | Mindre over det underliggende |
| Global rekkevidde | Vanskelig | Regioner over hele verden |
| Kompetansebehov | Maskinvare, strøm, kjøling | Sky-arkitektur, sikkerhet, kostnadsstyring |

> **Vanlig feil:** «Skyen er alltid billigere.» Ikke nødvendigvis. For stabile, forutsigbare arbeidslaster kan egen maskinvare være billigere over tid. Skyen vinner på **fleksibilitet, hastighet og tjenester**, men koster mye hvis man ikke styrer kostnadene. Noen virksomheter flytter til og med arbeidslaster tilbake (*repatriation*).

## Deployeringsmodeller: public, private, hybrid

**Public cloud** – ressursene eies og driftes av en leverandør (Microsoft, Amazon, Google) og deles mellom mange kunder (logisk isolert). Det er dette de fleste mener med «skyen».

**Private cloud** – skyteknologi (selvbetjening, automatisering, virtualisering) brukt av **én** organisasjon, ofte i eget datasenter. Gir kontroll, men du må drifte alt.

**Hybrid cloud** – en kombinasjon. For eksempel: kundedata må ligge i eget datasenter av regulatoriske grunner, mens nettsiden og analysene kjører i Azure. **Azure Arc** lar deg styre servere og Kubernetes-klynger utenfor Azure fra Azure-portalen.

**Multi-cloud** – å bruke flere offentlige skyer (f.eks. Azure + AWS) samtidig. Gir fleksibilitet, men mer kompleksitet.

```text
   PUBLIC                 PRIVATE                HYBRID
 ┌─────────┐            ┌─────────┐       ┌─────────┐ VPN/  ┌─────────┐
 │  Azure  │            │  Eget   │       │  Eget   │═══════│  Azure  │
 │ (delt)  │            │datasenter│      │datasenter│Express│         │
 └─────────┘            └─────────┘       └─────────┘ Route └─────────┘
```

## Tjenestemodeller: IaaS, PaaS, SaaS

Dette er et av de viktigste begrepene i hele sky-feltet. Spørsmålet er: **hvor mye drifter du selv, og hvor mye drifter leverandøren?**

```text
            ON-PREM      IaaS          PaaS          SaaS
          ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐
 Data     │   DU    │  │   DU    │  │   DU    │  │   DU    │ ← du har alltid ansvar for data
 App      │   DU    │  │   DU    │  │   DU    │  │ LEVERAN.│
 Runtime  │   DU    │  │   DU    │  │ LEVERAN.│  │ LEVERAN.│
 OS       │   DU    │  │   DU    │  │ LEVERAN.│  │ LEVERAN.│
 Virtual. │   DU    │  │ LEVERAN.│  │ LEVERAN.│  │ LEVERAN.│
 Servere  │   DU    │  │ LEVERAN.│  │ LEVERAN.│  │ LEVERAN.│
 Lagring  │   DU    │  │ LEVERAN.│  │ LEVERAN.│  │ LEVERAN.│
 Nettverk │   DU    │  │ LEVERAN.│  │ LEVERAN.│  │ LEVERAN.│
          └─────────┘  └─────────┘  └─────────┘  └─────────┘
```

### IaaS – Infrastructure as a Service

Du leier **infrastruktur**: virtuelle maskiner, disker, nettverk. Du installerer og drifter operativsystem og programvare selv.

- **Azure-eksempler:** Virtual Machines, Virtual Network, Managed Disks.
- **Fordel:** Maksimal kontroll og fleksibilitet. Lett å flytte eksisterende servere («lift and shift»).
- **Ulempe:** Du må patche OS, sikre, ta backup og skalere selv.

### PaaS – Platform as a Service

Du leier en **plattform** der du bare laster opp koden eller dataene. Leverandøren drifter OS, runtime, patching og ofte skalering.

- **Azure-eksempler:** App Service, Azure SQL Database, Azure Functions, Azure Container Apps.
- **Fordel:** Mye mindre drift. Raskere utvikling. Innebygd skalering og høy tilgjengelighet.
- **Ulempe:** Mindre kontroll; du må tilpasse deg plattformens begrensninger.

### SaaS – Software as a Service

Du bruker **ferdig programvare** over nettet. Du konfigurerer og bruker; alt annet er leverandørens ansvar.

- **Eksempler:** Microsoft 365, Gmail, Salesforce, Slack, GitHub.

> **Hverdagsanalogi – pizza som tjeneste:**
> **On-prem:** du lager pizza hjemme fra bunnen – kjøper ovn, ingredienser, lager deig.
> **IaaS:** du leier et kjøkken med ovn; du tar med ingredienser og lager pizzaen selv.
> **PaaS:** du bestiller pizza levert på døren; du dekker bordet og server.
> **SaaS:** du går på pizzarestaurant; du bare spiser.

**Serverless** og **containere** (Container Apps, AKS) ligger et sted mellom IaaS og PaaS; vi kommer tilbake til dem.

> **Husk:** Jo lenger mot SaaS, jo mindre drift for deg – men også mindre kontroll. Velg det høyeste abstraksjonsnivået som dekker behovet. En DevOps Engineer bør spørre: «Hvorfor trenger vi en VM her, når App Service kunne gjort jobben?»

## Regioner og tilgjengelighetssoner

- **Region** – et geografisk område med ett eller flere datasentre (f.eks. *Norway East*, *West Europe*, *Sweden Central*).
- **Tilgjengelighetssone** (*Availability Zone, AZ*) – fysisk adskilte lokasjoner **innenfor en region**, hver med egen strøm, kjøling og nettverk. Som regel tre per region som støtter soner.
- **Regionpar** (*region pairs*) – noen Azure-regioner er paret med en annen region i samme geografi for katastrofegjenoppretting og koordinerte oppdateringer. (Nyere regioner har ikke alltid et par.)

**Hvordan velge region?**

1. **Nærhet til brukerne** – lav forsinkelse (*latency*).
2. **Lovkrav og datasuverenitet** – f.eks. GDPR, krav om at data blir i Norge/EU.
3. **Tilgjengelige tjenester** – ikke alle tjenester og VM-størrelser finnes i alle regioner.
4. **Pris** – prisene varierer mellom regioner.
5. **Støtte for tilgjengelighetssoner.**

## Skalering, elastisitet, høy tilgjengelighet og feiltoleranse

### Skalerbarhet (*scalability*)

Evnen til å håndtere mer last ved å legge til ressurser.

```text
 VERTIKAL SKALERING (scale up)        HORISONTAL SKALERING (scale out)
  ┌──┐       ┌──────┐                  ┌──┐      ┌──┐┌──┐┌──┐┌──┐
  │VM│  ──►  │ STØRRE│                 │VM│ ──►  │VM││VM││VM││VM│
  └──┘       │  VM   │                 └──┘      └──┘└──┘└──┘└──┘
             └──────┘                            bak en lastbalanserer
  Enkel, men har et tak og               Nesten ubegrenset, krever at appen
  krever ofte omstart                    tåler flere instanser (stateless)
```

- **Vertikal** (*scale up/down*): større eller mindre maskin.
- **Horisontal** (*scale out/in*): flere eller færre maskiner.

### Elastisitet (*elasticity*)

Evnen til å skalere **automatisk** opp og ned i takt med etterspørselen. Skalerbarhet er *at* du kan skalere; elastisitet er at det skjer *automatisk og dynamisk*.

> **Fra arbeidslivet:** En nettbutikk kjører 2 instanser til vanlig, autoskalerer til 20 på Black Friday, og tilbake til 2 natten etter. De betaler bare for toppen mens den varer.

### Høy tilgjengelighet (*high availability, HA*)

Systemet er tilgjengelig **så mye av tiden som mulig**, målt i prosent oppetid:

| Tilgjengelighet | Maks nedetid per år | Per måned (ca.) |
|---|---|---|
| 99 % | 3,65 dager | 7,2 timer |
| 99,9 % («tre niere») | 8,76 timer | 43,8 minutter |
| 99,95 % | 4,38 timer | 21,9 minutter |
| 99,99 % («fire niere») | 52,6 minutter | 4,4 minutter |
| 99,999 % | 5,26 minutter | 26 sekunder |

En **SLA** (*Service Level Agreement*) er leverandørens løfte om tilgjengelighet, med kompensasjon (kreditt) hvis de bryter det. For eksempel gir Azure høyere SLA for VM-er spredt over flere tilgjengelighetssoner enn for én enkelt VM. Sjekk gjeldende SLA-er i Microsofts SLA-dokument («Service Level Agreements (SLA) for Online Services»), siden de oppdateres.

> **Vanlig feil:** Å tro at SLA-en til hver tjeneste er SLA-en til hele systemet. Hvis appen avhenger av tre tjenester med 99,9 % hver, blir den samlede tilgjengeligheten omtrent 0,999 × 0,999 × 0,999 ≈ **99,7 %**. Avhengigheter i serie *senker* tilgjengeligheten.

### Feiltoleranse (*fault tolerance*)

Systemet **fortsetter å virke** selv om en komponent feiler, fordi det finnes **redundans** – ekstra eksemplarer som tar over. Høy tilgjengelighet handler om å minimere nedetid; feiltoleranse handler om at enkeltfeil ikke gir nedetid i det hele tatt.

### Katastrofegjenoppretting (*disaster recovery, DR*)

Planen og løsningen for å gjenopprette tjenesten etter en **stor** hendelse: en hel region er nede, løsepengevirus har kryptert alt, eller noen slettet databasen.

To nøkkeltall:

- **RPO** (*Recovery Point Objective*) – hvor mye **data** har vi råd til å miste? (RPO = 1 time → backup minst hver time.)
- **RTO** (*Recovery Time Objective*) – hvor **lang tid** kan det ta før tjenesten er tilbake?

```text
   siste backup            KATASTROFE                tjenesten er tilbake
        │◄────── RPO ───────►│◄──────── RTO ───────────►│
   ─────●────────────────────✖──────────────────────────●──────► tid
       (data mellom disse                 (nedetid)
        punktene er tapt)
```

DR-strategier, fra billig/treg til dyr/rask:

| Strategi | Beskrivelse | RTO |
|---|---|---|
| Backup & restore | Ta backup, gjenopprett ved behov | Timer–dager |
| Pilot light | Minimal kjerne (f.eks. replikert database) kjører i reserve-regionen | Timer |
| Warm standby | Nedskalert full kopi kjører | Minutter |
| Active-active | Fullt system i flere regioner samtidig | Nær null |

> **Husk:** Backup du ikke har testet å gjenopprette, er ikke en backup – det er et håp.

## Sky-tjenestekategorier

### Compute (regnekraft)

| Type | Hva | Azure |
|---|---|---|
| Virtuelle maskiner | Full OS-kontroll | Virtual Machines, VM Scale Sets |
| Containere | Pakkede apper | Container Apps, Container Instances, AKS |
| PaaS-webhosting | Last opp kode | App Service |
| Serverless | Kode som kjører ved hendelser | Azure Functions |

### Lagring (*storage*)

| Type | Hva | Analogi | Azure |
|---|---|---|---|
| **Blokklagring** (*block*) | Rå disk for en VM | En harddisk | Managed Disks |
| **Fillagring** (*file*) | Delte mapper (SMB/NFS) | En nettverksdisk på kontoret | Azure Files |
| **Objektlagring** (*object*) | Filer (objekter) via HTTP, nesten ubegrenset | Et enormt lager med merkede esker | Blob Storage |

Lagring har ofte **nivåer** (*tiers*): *hot* (ofte brukt, dyrere lagring, billig tilgang), *cool*, *cold* og *archive* (sjelden brukt, svært billig lagring, dyr og treg å hente).

### Nettverk

Virtuelle nettverk (VNet), subnett, sikkerhetsgrupper, lastbalanserere, DNS, VPN-gatewayer, CDN – alt fra kapittel 2, men som programvaredefinerte tjenester du oppretter med klikk eller kode.

### Databaser

- **Administrerte relasjonsdatabaser**: Azure SQL Database, Azure Database for PostgreSQL / MySQL (*Flexible Server*). Leverandøren tar seg av patching, backup og HA.
- **NoSQL**: Azure Cosmos DB.
- **Cache**: Azure Cache for Redis / Azure Managed Redis (sjekk Microsoft Learn for gjeldende produktnavn og veikart).

> **Fra arbeidslivet:** Å drifte en database selv på en VM (installere, patche, sette opp replikering og backup) er mye arbeid og risiko. De fleste team velger en **administrert database** (PaaS) med mindre de har særskilte behov.

### Serverless

**Hva er det?** Du skriver bare kode (en *funksjon*) som kjøres når noe skjer – en HTTP-forespørsel, en fil lastes opp, en melding i en kø, et tidspunkt. Du tenker ikke på servere i det hele tatt (de finnes, men leverandøren håndterer dem), og betaler typisk per kjøring.

- **Fordeler:** null serverdrift, skalerer automatisk (også til null), svært billig ved lav eller ujevn bruk.
- **Ulemper:** **kaldstart** (*cold start*) – første kall etter en stille periode kan være tregt; begrensninger på kjøretid; vanskeligere lokal testing; risiko for leverandørbinding.
- **Azure:** Azure Functions, Logic Apps (arbeidsflyter med lite kode), Container Apps (skalerer også til null).

## Sky-sikkerhet og modellen for delt ansvar

**Hva er det?** Sikkerheten i skyen er **delt** mellom leverandøren og kunden. Leverandøren sikrer **skyen** (fysiske datasentre, maskinvare, hypervisor). Du sikrer det du **legger i** skyen.

| Ansvar | On-prem | IaaS | PaaS | SaaS |
|---|---|---|---|---|
| Data, kontoer og identiteter | Kunde | Kunde | Kunde | Kunde |
| Enheter (PC-er, mobiler) | Kunde | Kunde | Kunde | Kunde |
| Applikasjon | Kunde | Kunde | Delt | Leverandør |
| Nettverkskontroller | Kunde | Kunde | Delt | Leverandør |
| Operativsystem | Kunde | Kunde | Leverandør | Leverandør |
| Fysiske verter, nettverk, datasenter | Kunde | Leverandør | Leverandør | Leverandør |

> **Husk:** Du er **alltid** ansvarlig for: dine **data**, dine **brukerkontoer og tilganger**, og **enhetene** som brukes. De aller fleste sikkerhetsbrudd i skyen skyldes kundens feilkonfigurasjon – åpne lagringskontoer, svake passord, manglende MFA – ikke at leverandøren ble hacket.

Grunnleggende sky-sikkerhet (utdypes i kapittel 13):

- **Identitet er den nye perimeteren**: MFA for alle, minste privilegium, ingen delte kontoer.
- **Kryptering** av data i ro (*at rest*) og under overføring (*in transit*).
- **Nettverkssegmentering** og private endepunkter.
- **Logging og overvåking** av alt.
- **Policy** som hindrer usikker konfigurasjon.

## Prising og kostnadsoptimalisering

### Hva koster penger i skyen?

| Kategori | Eksempel |
|---|---|
| Compute | Per sekund/time en VM kjører, per vCPU/minne, per funksjonskjøring |
| Lagring | Per GB per måned, pluss per transaksjon |
| Utgående datatrafikk (*egress*) | Data **ut** av skyen til internett koster ofte; data **inn** er som regel gratis |
| Lisenser | Windows Server, SQL Server (kan inngå i timeprisen) |
| Administrerte tjenester | Lastbalanserere, gatewayer, brannmurer, offentlige IP-er – ofte per time |
| Støtte | Supportavtaler |

### Prismodeller

- **Pay-as-you-go** – betal per bruk, ingen binding. Dyrest per time, mest fleksibelt.
- **Reservasjoner** (*Reserved Instances*) – forplikt deg til 1 eller 3 år for en bestemt ressurs; stor rabatt.
- **Savings Plans** – forplikt deg til et beløp per time i 1 eller 3 år; rabatt med mer fleksibilitet.
- **Spot** – ledig kapasitet med stor rabatt, men kan bli tatt tilbake på kort varsel. Bra for batchjobber og testing.
- **Azure Hybrid Benefit** – bruk eksisterende Windows Server/SQL Server-lisenser i Azure.

### Kostnadsoptimalisering – sjekkliste

1. **Slå av eller slett det du ikke bruker.** Den vanligste lekkasjen. Stoppede (*deallocated*) VM-er koster ikke compute, men disker og offentlige IP-er koster fortsatt.
2. **Riktig størrelse** (*right-sizing*): ikke kjør en 16-kjerners VM som bruker 5 % CPU.
3. **Autoskalering** og **automatisk avslåing** av dev/test-miljøer om natten.
4. **Riktig lagringsnivå** og livssyklusregler som flytter gamle data til billigere nivåer.
5. **Reservasjoner/Savings Plans** for stabile arbeidslaster.
6. **Tagging** av alle ressurser med eier, prosjekt og miljø – så du vet hvem som bruker hva.
7. **Budsjetter og varsler.**
8. **Velg PaaS/serverless** der det passer – du betaler ikke for ledig kapasitet.

> **Kostnad:** Den farligste setningen for en student er «jeg rydder opp i morgen». En glemt VM, lastbalanserer, NAT Gateway, VPN Gateway, Azure Firewall, eller et AKS-cluster kan spise opp studentkreditten på dager eller uker. Rydd opp **samme dag**, og slett hele ressursgruppen når du er ferdig.

**FinOps** er fagfeltet for økonomistyring i skyen: samarbeid mellom teknologi, økonomi og forretning for å få mest mulig verdi per krone.

## AWS, Azure og Google Cloud – en sammenligning

De tre store leverandørene tilbyr i hovedsak de samme kategoriene av tjenester. Når du har lært én skikkelig, er det mye lettere å lære de andre.

| Kategori | Microsoft Azure | Amazon Web Services (AWS) | Google Cloud (GCP) |
|---|---|---|---|
| Virtuelle maskiner | Virtual Machines | EC2 | Compute Engine |
| Autoskalerende VM-grupper | VM Scale Sets | Auto Scaling Groups | Managed Instance Groups |
| Objektlagring | Blob Storage | S3 | Cloud Storage |
| Virtuelt nettverk | Virtual Network (VNet) | VPC | VPC |
| Brannmurregler | Network Security Group | Security Group / NACL | VPC firewall rules |
| Administrert relasjonsdatabase | Azure SQL Database, Azure Database for PostgreSQL | RDS, Aurora | Cloud SQL, AlloyDB |
| NoSQL | Cosmos DB | DynamoDB | Firestore, Bigtable |
| Serverless funksjoner | Azure Functions | Lambda | Cloud Run functions |
| Container-plattform (enkel) | Container Apps | App Runner, ECS/Fargate | Cloud Run |
| Kubernetes | AKS | EKS | GKE |
| Container-register | Azure Container Registry | ECR | Artifact Registry |
| Identitet | Microsoft Entra ID, Azure RBAC | IAM, IAM Identity Center | Cloud IAM |
| Hemmeligheter | Key Vault | Secrets Manager, KMS | Secret Manager, Cloud KMS |
| Infrastruktur som kode (egen) | ARM / Bicep | CloudFormation | Infrastructure Manager (Terraform-basert) |
| Overvåking | Azure Monitor | CloudWatch | Cloud Monitoring/Logging |
| CI/CD | Azure DevOps / GitHub Actions | CodePipeline / CodeBuild | Cloud Build |
| AI-plattform | Azure Machine Learning, Microsoft Foundry (tidl. Azure AI Foundry) | SageMaker, Bedrock | Vertex AI |

**Styrker, grovt sagt:**

- **Azure:** sterk i bedrifter som allerede bruker Microsoft (Windows Server, Microsoft 365, Entra ID, .NET), hybrid-løsninger, og tett integrasjon med GitHub og OpenAI-modeller. Svært utbredt i Norge og offentlig sektor.
- **AWS:** størst og eldst, bredest tjenestetilbud og enormt økosystem.
- **Google Cloud:** sterk på data, analyse, Kubernetes (Google laget Kubernetes) og AI.

> **Fra arbeidslivet:** I norske stillingsannonser er Azure svært ofte etterspurt, særlig hos konsulentselskaper, banker og offentlig sektor. Begreper og prinsipper (IaaS/PaaS, nettverk, IAM, IaC, containere) er overførbare mellom leverandører – og det er det arbeidsgivere egentlig ser etter.

## Cloud-native og Well-Architected

**Cloud-native** betyr applikasjoner bygget for å utnytte skyen: containere, mikrotjenester, automatisering, deklarativ infrastruktur, observability og robusthet mot feil.

Alle de store leverandørene har et **Well-Architected Framework** med beste praksis. Microsofts har fem søyler:

| Søyle | Spørsmål |
|---|---|
| **Reliability** (pålitelighet) | Tåler løsningen feil og gjenoppretter den seg? |
| **Security** (sikkerhet) | Er data og tilgang beskyttet? |
| **Cost Optimization** | Får vi mest mulig verdi for pengene? |
| **Operational Excellence** | Er drift, deploy og overvåking automatisert og god? |
| **Performance Efficiency** | Skalerer løsningen effektivt med lasten? |

Bruk disse fem som sjekkliste når du designer noe – og når du svarer på arkitekturspørsmål i intervjuer.

## Kapitteloppsummering

- Skyen er å leie IT-ressurser over internett, betalt etter bruk – fysisk er det enorme datasentre.
- Regioner inneholder tilgjengelighetssoner, som er fysisk adskilte datasentre.
- IaaS (du drifter OS), PaaS (du drifter app og data), SaaS (du bruker ferdig programvare).
- Public, private, hybrid og multi-cloud er måter å kombinere ressurser på.
- Skalering kan være vertikal eller horisontal; elastisitet er automatisk skalering.
- HA, feiltoleranse og DR (med RPO og RTO) handler om robusthet på ulike nivåer.
- Delt ansvar: leverandøren sikrer skyen; du sikrer data, identiteter og konfigurasjon.
- Kostnader styres med riktig størrelse, avslåing, tagging, budsjetter og riktige prismodeller.
- Azure, AWS og GCP tilbyr de samme kategoriene med ulike navn.

## Øvingsoppgaver

1. Klassifiser som IaaS, PaaS eller SaaS: Azure VM, Microsoft 365, Azure App Service, Azure SQL Database, Gmail, Azure Functions.
2. En app har en SLA-kjede med App Service (99,95 %) og Azure SQL Database (99,99 %). Regn ut omtrentlig samlet tilgjengelighet.
3. En bedrift kan tåle å miste 15 minutter med data og må være oppe igjen innen 2 timer. Hva er RPO og RTO? Hvilken DR-strategi passer?
4. Bruk Azure Pricing Calculator (azure.microsoft.com/pricing/calculator) til å anslå månedskostnaden for én liten Linux-VM i Norway East. Sammenlign med samme VM i en annen region.
5. Lag en tabell med fem tjenester du kjenner fra Azure, og finn tilsvarende tjeneste i AWS og GCP.

## Quiz

1. Nevn tre av NISTs fem kjennetegn ved skyen.
2. Hva er forskjellen på CapEx og OpEx?
3. Hva er en tilgjengelighetssone?
4. Hva er forskjellen på vertikal og horisontal skalering?
5. Hva er forskjellen på skalerbarhet og elastisitet?
6. Hva betyr RPO og RTO?
7. I PaaS – hvem patcher operativsystemet?
8. Hva er du *alltid* ansvarlig for, uansett tjenestemodell?
9. Hvorfor kan utgående datatrafikk bli en overraskende kostnad?
10. Hva heter Azure Blob Storage hos AWS?

### Fasit

1. Hvilke som helst tre av: on-demand self-service, broad network access, resource pooling, rapid elasticity, measured service.
2. **CapEx** er investeringer i fysiske eiendeler på forhånd (kjøpe servere). **OpEx** er løpende driftsutgifter (betale per bruk).
3. En fysisk adskilt lokasjon (ett eller flere datasentre) innenfor en region, med egen strøm, kjøling og nettverk.
4. **Vertikal**: gjøre én maskin større/mindre. **Horisontal**: legge til eller fjerne maskiner.
5. **Skalerbarhet** er evnen til å håndtere mer last ved å legge til ressurser. **Elastisitet** er at dette skjer automatisk, opp og ned, i takt med etterspørselen.
6. **RPO**: hvor mye data man har råd til å miste (målt i tid). **RTO**: hvor lang tid gjenopprettingen kan ta.
7. **Leverandøren** (f.eks. Microsoft).
8. **Data**, **kontoer/identiteter** og **enhetene** (endepunktene) som brukes.
9. Fordi data *ut* av skyen ofte faktureres per GB, og store volumer (video, backuper, nedlastinger) kan gi store regninger.
10. **Amazon S3**.
