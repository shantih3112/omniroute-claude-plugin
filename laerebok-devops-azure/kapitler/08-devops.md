# Del 8 – DevOps Engineering

**Læringsmål for kapitlet.** Når du er ferdig, skal du kunne:

- forklare hva DevOps er, hvorfor det oppstod, og hva DevOps-kultur betyr,
- forklare Agile, Scrum og livssyklusen for programvareutvikling (SDLC),
- skille mellom Continuous Integration, Continuous Delivery og Continuous Deployment,
- beskrive deploy-strategier, monitoring, observability og hendelseshåndtering,
- forklare SRE, Platform Engineering og DevSecOps,
- beskrive en typisk arbeidsdag for en DevOps Engineer.

## Hva er DevOps?

**Hva er det?** DevOps er en **kultur og en måte å jobbe på** der utvikling (*Development*) og drift (*Operations*) samarbeider tett gjennom hele livsløpet til en tjeneste – fra idé til produksjon og videre drift – med mye **automatisering** og raske **tilbakemeldinger**.

DevOps er **ikke**:

- bare et verktøy («vi har kjøpt Jenkins, så nå er vi DevOps»),
- bare en stillingstittel,
- et eget team som sitter mellom utviklere og drift og tar imot billetter (det er bare en ny mur).

> **Hverdagsanalogi:** Tenk på en restaurant der kokkene (utviklerne) lager retter og kaster dem over en vegg til servitørene (driften), som må finne ut hvordan de skal serveres. Når gjestene klager, skylder de på hverandre. I en DevOps-restaurant planlegger kokker og servitører menyen sammen, kokkene smaker på maten underveis, servitørene gir umiddelbar tilbakemelding fra gjestene, og kjøkkenet har maskiner som gjør de repeterende oppgavene.

## Hvorfor oppstod DevOps?

**Problemet: «muren» mellom Dev og Ops.**

```text
   UTVIKLERE (Dev)                           DRIFT (Ops)
   Mål: lever nye funksjoner raskt           Mål: hold systemet stabilt
   ┌──────────────┐                          ┌──────────────┐
   │ «Det virker  │  ── kaster over muren ─► │ «Hvorfor     │
   │  på min PC!» │      hvert halvår        │  krasjer det │
   └──────────────┘                          │  i prod?!»   │
          ▲               ███ MUR ███        └──────┬───────┘
          └──────── skyld og billetter ◄────────────┘
```

Før DevOps var det vanlig at:

- utviklere og drift hadde **motstridende mål** (endring vs. stabilitet),
- utgivelser skjedde **sjelden og var store** – derfor risikable og smertefulle («release-helg»),
- servere ble satt opp **manuelt**, ulikt fra miljø til miljø («snøfnugg-servere»),
- feil ble oppdaget **sent**, ofte av kundene,
- ingen eide helheten.

**Bakgrunn.** Rundt 2007–2009 begynte folk som Patrick Debois og Andrew Shafer å snakke om «agile infrastruktur». En kjent presentasjon fra Flickr i 2009, «10+ Deploys per Day: Dev and Ops Cooperation», viste at hyppige utgivelser og samarbeid ga **både** fart **og** stabilitet. Samme år ble den første *DevOpsDays*-konferansen arrangert i Belgia – og navnet var født. Samtidig gjorde skyen og API-er det mulig å automatisere infrastruktur.

**Viktig innsikt:** Fart og stabilitet er **ikke** motsetninger. Små, hyppige endringer er *lettere* å teste, *lettere* å forstå, og *lettere* å rulle tilbake enn store, sjeldne endringer.

## DevOps-kultur

### CALMS – fem søyler

| Bokstav | Betyr | I praksis |
|---|---|---|
| **C**ulture | Samarbeid, felles ansvar, tillit | «You build it, you run it» – teamet som lager tjenesten, drifter den også |
| **A**utomation | Automatiser repeterende arbeid | CI/CD, IaC, automatiske tester |
| **L**ean | Små leveranser, fjern sløsing, flyt | Små PR-er, korte køer, WIP-grenser |
| **M**easurement | Mål for å forbedre | DORA-metrikker, overvåking |
| **S**haring | Del kunnskap, verktøy og lærdom | Dokumentasjon, postmortems, interne plattformer |

### De tre veiene (*The Three Ways*)

Fra boken *The Phoenix Project* / *The DevOps Handbook*:

1. **Flyt** (*flow*) – få arbeid raskt og jevnt fra utvikler til kunde. Små batcher, automatisering, synliggjør arbeid.
2. **Tilbakemelding** (*feedback*) – få rask informasjon om problemer: tester, overvåking, varsler, kundeinnsikt.
3. **Kontinuerlig læring og eksperimentering** – lær av feil uten skyld, forbedre hele tiden.

### Blameless culture – kultur uten skyld

Når noe går galt, spør man **«hvordan lot systemet dette skje?»**, ikke **«hvem gjorde feil?»**. Mennesker gjør feil; gode systemer gjør det vanskelig å gjøre feil og lett å oppdage og rette dem. Hvis folk blir straffet, skjuler de feil – og organisasjonen slutter å lære.

> **Fra arbeidslivet:** En utvikler slettet ved et uhell en produksjonsdatabase. I en skyld-kultur får hun sparken. I en DevOps-kultur spør teamet: hvorfor hadde en utvikler skrivetilgang til produksjon? Hvorfor fantes det ingen lås eller bekreftelse? Hvorfor tok gjenopprettingen fire timer? Tiltakene blir minste privilegium, ressurslåser, og testet backup – og hele organisasjonen blir tryggere.

### Måling: DORA-metrikkene

Forskningsprogrammet **DORA** (*DevOps Research and Assessment*, nå del av Google Cloud) har i mange år studert tusenvis av organisasjoner. De fant fire nøkkeltall som skiller høytytende team fra andre:

| Metrikk | Spørsmål | Høytytende team |
|---|---|---|
| **Deployment frequency** | Hvor ofte deployer vi til produksjon? | Ofte – flere ganger daglig, ved behov |
| **Lead time for changes** | Hvor lang tid fra commit til produksjon? | Kort – under en dag |
| **Change failure rate** | Hvor stor andel av deployene gir feil i produksjon? | Lav |
| **Time to restore service** (*failed deployment recovery time*) | Hvor raskt gjenoppretter vi etter en feil? | Raskt – under en time |

De to første måler **fart**, de to siste **stabilitet**. DORA fant at de beste teamene er gode på **begge**. (De nyere rapportene har justert navn og lagt til *rework rate*; se dora.dev for gjeldende definisjoner.)

> **Husk:** I et intervju er DORA-metrikkene et sterkt svar på «Hvordan måler du om et DevOps-initiativ fungerer?»

## Agile

**Hva er det?** Agile (smidig utvikling) er en tankegang for programvareutvikling basert på **Agile-manifestet** (2001). I stedet for å planlegge alt på forhånd (fossefall, *waterfall*), leverer man **små, fungerende biter ofte**, får tilbakemelding, og justerer.

Manifestets fire verdier:

- **Individer og samspill** fremfor prosesser og verktøy
- **Programvare som virker** fremfor omfattende dokumentasjon
- **Samarbeid med kunden** fremfor kontraktsforhandlinger
- **Å reagere på endringer** fremfor å følge en plan

(«Fremfor» betyr at tingene til høyre også har verdi, men tingene til venstre verdsettes mer.)

```text
 FOSSEFALL (waterfall)                      AGILE (iterativt)
 Krav → Design → Kode → Test → Drift        ┌─► Planlegg ─► Bygg ─► Test ─► Lever ─┐
 (måneder/år; kunden ser noe først          └────────── tilbakemelding ◄───────────┘
  helt på slutten)                          (2-ukers sykluser; kunden ser noe hele tiden)
```

**Agile og DevOps** henger sammen: Agile gjorde *utviklingen* rask og iterativ. Men hvis koden bare blir deployet hvert halvår, hjelper det lite. DevOps utvider smidigheten **helt ut i produksjon**.

## Scrum

**Hva er det?** Scrum er det mest brukte rammeverket for å jobbe smidig. Arbeidet deles inn i **sprinter** – faste perioder på 1–4 uker (oftest 2) – der teamet leverer en fungerende økning av produktet.

**Roller:**

| Rolle | Ansvar |
|---|---|
| **Product Owner** | Bestemmer *hva* som er viktigst; eier og prioriterer produktbackloggen |
| **Scrum Master** | Hjelper teamet å følge Scrum og fjerner hindringer; en tjenende leder, ikke en sjef |
| **Developers** (utviklerteamet) | Alle som bygger produktet – også DevOps-, test- og designkompetanse |

**Artefakter:** *Product backlog* (prioritert liste over alt som kan gjøres), *Sprint backlog* (det teamet forplikter seg til denne sprinten), *Increment* (fungerende resultat). **Definition of Done** sier når noe er ferdig (f.eks. «testet, kodegjennomgått, deployet til test, dokumentert»).

**Hendelser:**

```text
 ┌──────────────── SPRINT (f.eks. 2 uker) ─────────────────┐
 │ Sprint Planning → Daily Scrum (15 min hver dag) → ...    │
 │                    → Sprint Review → Sprint Retrospective│
 └──────────────────────────────────────────────────────────┘
```

- **Sprint Planning** – hva skal vi levere, og hvordan?
- **Daily Scrum** – kort daglig synk: fremdrift mot sprintmålet, hindringer.
- **Sprint Review** – vis frem resultatet for interessenter, få tilbakemelding.
- **Sprint Retrospective** – hvordan jobbet vi? Hva skal vi forbedre?

**Kanban** er et alternativ: kontinuerlig flyt i stedet for sprinter, med en tavle (*To Do → In Progress → Review → Done*) og **begrensning av pågående arbeid** (*WIP limits*). Mange drifts- og plattformteam foretrekker Kanban, fordi uplanlagt arbeid (hendelser) passer dårlig inn i faste sprinter.

**User stories** beskriver behov fra brukerens perspektiv: *«Som kunde vil jeg få e-post når pakken er sendt, slik at jeg vet når den kommer.»* Med **akseptansekriterier**: «E-post sendes innen 5 minutter etter at status endres til *sendt*.»

## SDLC – livssyklusen for programvareutvikling

**Hva er det?** SDLC (*Software Development Life Cycle*) beskriver fasene programvare går gjennom:

```text
   1. Planlegging ─► 2. Analyse/krav ─► 3. Design ─► 4. Implementering (koding)
        ▲                                                       │
        │                                                       ▼
   7. Vedlikehold ◄─ 6. Deploy/drift ◄──────────────── 5. Testing
```

I tradisjonell utvikling går man gjennom fasene én gang (fossefall). I Agile/DevOps går man gjennom alle fasene **kontinuerlig i små sløyfer** – for hver funksjon, hver dag.

## DevOps-livssyklusen

DevOps-livssyklusen tegnes ofte som en **uendelighetssløyfe**:

```text
            ┌───── DEV ─────┐           ┌───── OPS ─────┐
          PLAN            BUILD       RELEASE         OPERATE
            ▲  ╲          ╱   ╲       ╱    ╲          ╱   │
            │    CODE ◄──     TEST ──►     DEPLOY ──►     │
            │                                              ▼
            └──────────────────── MONITOR ◄────────────────┘
                         (tilbakemelding til neste plan)
```

| Fase | Aktiviteter | Verktøy (eksempler) |
|---|---|---|
| Plan | Backlog, krav, prioritering | Azure Boards, Jira, GitHub Projects |
| Code | Skrive kode, kodegjennomgang | Git, GitHub, VS Code |
| Build | Kompilere, bygge artefakter/images | GitHub Actions, Azure Pipelines, Docker |
| Test | Enhetstester, integrasjonstester, sikkerhetsskanning | pytest, SonarQube, Trivy |
| Release | Versjonering, godkjenning | GitHub Releases, Azure Pipelines environments |
| Deploy | Rulle ut til miljøer | Actions, Pipelines, Argo CD, Helm |
| Operate | Drift, skalering, konfigurasjon | Kubernetes, Terraform, Ansible |
| Monitor | Metrikker, logger, varsler, brukeratferd | Azure Monitor, Prometheus, Grafana |

## CI/CD – kontinuerlig integrasjon, levering og deploy

Dette er hjertet av DevOps i praksis. Kapittel 12 viser hvordan du bygger det; her forklarer vi begrepene.

### Continuous Integration (CI)

**Hva er det?** Utviklere **integrerer** (merger) koden sin i en felles hovedbranch **ofte** – minst daglig – og hver integrasjon **bygges og testes automatisk**.

**Hvorfor?** Hvis fem utviklere jobber hver for seg i tre uker og så prøver å slå sammen alt, får de «integrasjonshelvete»: konflikter og feil som er vanskelige å finne. Med CI oppdages problemer innen minutter, mens endringen fortsatt er liten og fersk i minnet.

**Kjennetegn:** én felles hovedbranch, automatisk bygg og test på hver push/PR, rask tilbakemelding (helst under 10 minutter), og en regel om at **rødt bygg fikses umiddelbart**.

### Continuous Delivery (CD)

**Hva er det?** Hver endring som består testene, blir automatisk gjort **klar for produksjon** (bygget, testet, deployet til testmiljø). Selve produksjonsdeployen skjer med **et tastetrykk / en godkjenning**.

### Continuous Deployment

**Hva er det?** Som Continuous Delivery, men **uten manuell godkjenning**: hver endring som består alle automatiske sjekker, går **rett i produksjon**.

```text
                   CODE → BUILD → TEST → STAGING → PRODUKSJON
 Continuous Integration  [  auto  ][ auto ]
 Continuous Delivery     [  auto  ][ auto ][ auto  ] [ MANUELL godkjenning ]
 Continuous Deployment   [  auto  ][ auto ][ auto  ] [ auto ]
```

> **Vanlig feil:** Å tro at «CD» alltid betyr Continuous Deployment. Mange organisasjoner (f.eks. banker med regulatoriske krav) har Continuous **Delivery** med manuell godkjenning til produksjon – og det er helt legitimt.

## Automatisering

**Prinsipp:** Hvis du gjør noe **mer enn to ganger**, eller det er **kritisk at det gjøres likt hver gang**, bør det automatiseres.

Hva automatiseres typisk i DevOps:

- bygg, test, sikkerhetsskanning og deploy (CI/CD),
- opprettelse av infrastruktur (IaC – Terraform, Bicep),
- konfigurasjon av servere (Ansible, cloud-init),
- skalering (autoskalering),
- overvåking og varsling,
- rutineoppgaver: opprydding, sertifikatfornyelse, backup, rapporter,
- *self-service* for utviklere («lag et nytt miljø med ett klikk»).

**Toil** er Googles SRE-begrep for manuelt, repeterende, automatiserbart arbeid uten varig verdi. Målet er å redusere toil systematisk.

> **Vanlig feil:** Å automatisere en dårlig prosess. Forenkle prosessen først, automatiser etterpå.

## Infrastruktur i DevOps

Moderne infrastruktur behandles som **programvare**:

- **Infrastructure as Code (IaC)** – infrastruktur beskrives i kode, versjonskontrolleres og gjennomgås (kapittel 11).
- **Immutable infrastructure** – servere oppdateres ikke på plass; man bygger en ny versjon og erstatter den gamle. Containere er et typisk eksempel.
- **Pets vs. cattle** – før hadde servere navn og ble pleid som kjæledyr («kjære gamle *zeus*»). Nå er servere som buskap: like, nummererte og byttbare. Feiler en, erstattes den automatisk.
- **Miljøparitet** – utvikling, test og produksjon skal være så like som mulig (samme image, samme IaC, ulik størrelse og konfigurasjon).

## Deploy-strategier

Hvordan bytter du ut gammel versjon med ny, uten nedetid og med lav risiko?

| Strategi | Hvordan | Fordel | Ulempe |
|---|---|---|---|
| **Recreate** | Stopp gammel, start ny | Enkel | Nedetid |
| **Rolling** | Bytt instanser én og én (eller noen om gangen) | Ingen nedetid, standard i Kubernetes | Gammel og ny kjører samtidig en stund; rollback tar tid |
| **Blue-green** | Ny versjon (green) settes opp ved siden av gammel (blue); trafikken byttes på én gang | Rask, enkel rollback (bytt tilbake) | Dobbel kapasitet under bytte |
| **Canary** | Send en liten andel trafikk (f.eks. 5 %) til ny versjon, øk gradvis hvis alt ser bra ut | Lav risiko, ekte brukerdata | Krever god overvåking og trafikkstyring |
| **Feature flags** | Ny kode deployes «av», og slås på for utvalgte brukere uten ny deploy | Skiller *deploy* fra *release* | Flagg må ryddes opp i, ellers blir koden kompleks |
| **A/B-testing** | To varianter for å måle hvilken som fungerer best for brukerne | Forretningsinnsikt | Mer en produktteknikk enn en deploy-teknikk |

```text
 BLUE-GREEN                              CANARY
          ┌────► BLUE  (v1) ✗ etter bytte          ┌──95 %──► v1
 Brukere ─┤                              Brukere ──┤
          └────► GREEN (v2) ✓                      └── 5 %──► v2  (øk til 25 %, 50 %, 100 %)
```

> **Fra arbeidslivet:** I Azure App Service gjør du blue-green med **deployment slots** og swap. I Kubernetes er rolling standard; canary gjøres med verktøy som Argo Rollouts, Flagger eller en service mesh. Azure Front Door og Container Apps kan dele trafikk mellom revisjoner.

**Rollback** – å gå tilbake til forrige versjon – må være planlagt, testet og helst automatisert. Husk at **databaseendringer** er det vanskeligste å rulle tilbake: gjør dem bakoverkompatible («expand and contract»: legg til ny kolonne → deploy kode som bruker begge → fjern gammel kolonne senere).

## Monitoring og observability

**Monitoring (overvåking)** svarer på spørsmål du **visste** du måtte stille: Er serveren oppe? Er CPU over 90 %? Er feilraten over 1 %? Du definerer metrikker og terskler på forhånd.

**Observability (observerbarhet)** er evnen til å forstå **hva som skjer inne i systemet** ut fra dataene det sender ut – også for problemer du **ikke** forutså. «Hvorfor er utsjekken treg bare for brukere i Bergen som bruker Vipps?»

**De tre søylene** (mer i kapittel 13):

| Søyle | Hva | Eksempel |
|---|---|---|
| **Metrikker** | Tall over tid | Forespørsler/sek, feilrate, responstid, CPU |
| **Logger** | Hendelser med detaljer | `ERROR betaling feilet ordre=123 kode=TIMEOUT` |
| **Traces** | En forespørsels vei gjennom mange tjenester | frontend → API → betaling → database, med tid i hvert ledd |

**De fire gylne signalene** (Google SRE) for enhver tjeneste: **latency** (responstid), **traffic** (trafikk), **errors** (feil), **saturation** (metning/belastning).

## Incident management – hendelseshåndtering

**Hva er det?** En strukturert måte å håndtere **hendelser** (*incidents*) – uplanlagte avbrudd eller forringelse av en tjeneste.

**Livssyklus:**

```text
 Oppdag ─► Varsle ─► Triager ─► Begrens/løs ─► Gjenopprett ─► Postmortem ─► Forbedre
 (alert)  (vakt)    (alvorlighet) (mitigate)   (verifiser)    (læring)      (tiltak)
```

**Nøkkelbegreper:**

- **Alvorlighetsgrad** (*severity*): SEV1 (alle kunder rammet, kritisk) … SEV4 (liten påvirkning).
- **Vaktordning** (*on-call*): én person har ansvar for å svare på varsler utenom arbeidstid, ofte på rotasjon. Verktøy: PagerDuty, Opsgenie, Azure Monitor action groups.
- **Incident commander**: koordinerer håndteringen; andre fokuserer på teknisk feilsøking og kommunikasjon.
- **Mitigate først, root cause etterpå**: først få tjenesten opp igjen (rollback, failover, skalering), *deretter* finne grunnårsaken.
- **Runbooks / playbooks**: ferdige oppskrifter for kjente problemer («Hvis disken er full på DB-serveren, gjør …»).
- **MTTD / MTTR**: *Mean Time To Detect* og *Mean Time To Recover/Restore*.
- **Statusside** og kommunikasjon til kunder.

**Postmortem (etteranalyse)** – et dokument skrevet uten skyld etter en hendelse:

1. Sammendrag og påvirkning (hvem, hvor lenge, hvor mange).
2. Tidslinje.
3. Grunnårsak(er) og medvirkende faktorer («5 hvorfor»).
4. Hva gikk bra, hva gikk dårlig, hvor var vi heldige.
5. **Konkrete tiltak** med eier og frist.

## SRE – Site Reliability Engineering

**Hva er det?** SRE er Googles tilnærming til drift, beskrevet som «hva som skjer når du ber en programvareingeniør designe et driftsteam». SRE kan sees som én **konkret implementasjon** av DevOps-prinsippene.

**Kjernebegreper:**

| Begrep | Betyr | Eksempel |
|---|---|---|
| **SLI** (*Service Level Indicator*) | Et målt tall for tjenestekvalitet | Andel vellykkede forespørsler; andel forespørsler under 300 ms |
| **SLO** (*Service Level Objective*) | Internt **mål** for SLI-en | 99,9 % vellykkede forespørsler over 30 dager |
| **SLA** (*Service Level Agreement*) | **Avtale** med kunden, med konsekvenser | 99,5 %, ellers kreditt |
| **Error budget** | Hvor mye feil vi «har lov til» | 100 % − 99,9 % = 0,1 % ≈ 43 minutter per 30 dager |

**Error budget i praksis:** Så lenge budsjettet ikke er brukt opp, kan teamet slippe nye funksjoner raskt. Hvis budsjettet er brukt opp, prioriteres stabilitet foran nye funksjoner. Dette gjør konflikten mellom «fart» og «stabilitet» til en **datadrevet** beslutning.

Andre SRE-prinsipper: maks ~50 % av tiden på toil (resten på automatisering og ingeniørarbeid), blameless postmortems, og at 100 % pålitelighet er feil mål (det er uendelig dyrt, og brukerne merker ikke forskjellen fra 99,99 %).

> **Husk:** **SLA ≤ SLO ≤ det systemet faktisk leverer.** Man lover kunden mindre enn man sikter mot internt, for å ha margin.

## Platform Engineering

**Hva er det?** Platform Engineering er å bygge en **intern utviklerplattform** (*Internal Developer Platform, IDP*) – et sett med verktøy, maler og selvbetjente tjenester – slik at produktteamene kan levere raskt og trygt **uten** at hvert team må være eksperter på Kubernetes, nettverk, sikkerhet og CI/CD.

**Hvorfor?** «You build it, you run it» ga team mer ansvar – men også enorm **kognitiv belastning**. Plattformteamet tar på seg den felles kompleksiteten og tilbyr **«golden paths»** (asfalterte stier): anbefalte, ferdig oppsatte veier for vanlige oppgaver.

```text
 PRODUKTTEAM (kunder av plattformen)
   «Jeg vil ha en ny tjeneste med database og CI/CD»
           │  self-service (portal, CLI, mal)
           ▼
 ┌─────────────────── INTERN UTVIKLERPLATTFORM ────────────────────┐
 │ Maler for nye tjenester · CI/CD-maler · Miljøer på forespørsel   │
 │ Observability ferdig koblet · Hemmeligheter · Sikkerhetsskanning │
 │ Developer portal (f.eks. Backstage) · Dokumentasjon             │
 └──────────────────────────────┬──────────────────────────────────┘
                                ▼
         Azure · Kubernetes · Terraform · GitHub · Monitor ...
```

> **Fra arbeidslivet:** Mange norske selskaper har plattformteam (ofte kalt «Platform», «Developer Experience» eller «Cloud Platform»). En DevOps Engineer kan godt jobbe *i* et slikt team. Plattformen skal behandles som et **produkt**, med utviklerne som kunder.

## DevSecOps

**Hva er det?** DevSecOps er å bygge **sikkerhet inn i hele DevOps-livssyklusen** i stedet for å legge den til på slutten. Ofte kalt **«shift left»** – flytt sikkerhet (og testing) til venstre, tidligere i prosessen, der feil er billigere å rette.

```text
 Plan ──► Code ──► Build ──► Test ──► Release ──► Deploy ──► Operate ──► Monitor
 trussel-  pre-commit  SCA:      SAST/    signering   policy-     runtime-   SIEM,
 modell.   hooks,      avhengig- DAST,    av images,  sjekk       beskyttelse varsler,
           secret      heter,    image-   SBOM        (Azure      (Defender)  hendelses-
           scanning    lisenser  skanning             Policy,OPA)              håndtering
```

| Teknikk | Hva den finner | Eksempel på verktøy |
|---|---|---|
| **Secret scanning** | Passord og nøkler i kode | GitHub secret scanning, gitleaks |
| **SAST** (statisk analyse) | Sårbarheter i egen kildekode | CodeQL, SonarQube, Semgrep |
| **SCA** (avhengighetsanalyse) | Kjente sårbarheter i biblioteker | Dependabot, `pip-audit`, `npm audit` |
| **Container-skanning** | Sårbarheter i images | Trivy, Microsoft Defender for Containers |
| **IaC-skanning** | Usikker infrastrukturkode | Checkov, tfsec/Trivy |
| **DAST** (dynamisk analyse) | Sårbarheter i kjørende app | OWASP ZAP |
| **SBOM** | Oversikt over alle komponenter | Syft, `docker sbom` |

Mer i kapittel 13.

## En typisk arbeidsdag for en DevOps Engineer

Ingen dager er like, men slik kan en dag se ut for en DevOps Engineer i et produktteam hos et norsk selskap som bruker Azure:

| Tid | Aktivitet |
|---|---|
| 08:30 | Sjekker dashbordet i Grafana/Azure Monitor og varslingskanalen i Teams/Slack. Natten var rolig, bortsett fra et diskvarsel på en build-agent. |
| 08:45 | Rydder diskplassen på agenten og lager en oppgave om å automatisere opprydding av gamle Docker-images. |
| 09:00 | **Daily standup** med teamet (15 min). Status: Terraform-modul for nytt miljø er nesten ferdig. |
| 09:15 | Kodegjennomgang: en utviklers PR legger til en ny miljøvariabel. Foreslår at verdien hentes fra Key Vault i stedet for å stå i YAML. |
| 10:00 | Fokustid: skriver Terraform for et nytt testmiljø (VNet, Container Apps, PostgreSQL med private endpoint). Kjører `terraform plan` i pipelinen. |
| 11:30 | En utvikler spør hvorfor appen ikke når databasen i test. Feilsøker sammen: privat DNS-sone var ikke koblet til det nye VNet-et. Fikser i Terraform. |
| 12:00 | Lunsj. |
| 12:30 | Møte med sikkerhetsteamet om å innføre container-skanning i alle pipelines. Avtaler å lage en felles pipeline-mal. |
| 13:30 | Oppdaterer CI-pipelinen: legger til Trivy-skanning som feiler bygget ved kritiske sårbarheter. Tester på en branch. |
| 15:00 | Deploy av ny versjon til produksjon (canary 10 % → 100 %). Følger med på feilrate og responstid. Alt grønt. |
| 15:30 | Skriver dokumentasjon / runbook for det nye miljøet. |
| 16:00 | Retro-oppfølging: kostnadsanalyse viser at et gammelt testmiljø har kostet penger i tre måneder uten bruk. Avtaler sletting med teamet, og lager en policy som krever `utløper`-tag. |
| 16:30 | Overleverer til kollegaen som har vakt i kveld. |

**Kjennetegn ved jobben:** mye samarbeid og kommunikasjon, mye feilsøking, mye lesing av dokumentasjon og logger, en god del koding (YAML, HCL, Bash, Python), og et konstant fokus på å **gjøre andre mer produktive**.

**Nøkkelegenskaper hos gode DevOps Engineers:** nysgjerrighet, systematisk feilsøking, evne til å forklare tekniske ting enkelt, automatiseringsrefleks, sikkerhetsbevissthet, og ydmykhet – ingen kan alt.

## Kapitteloppsummering

- DevOps er kultur + praksis + verktøy for raskt og trygt samarbeid mellom utvikling og drift.
- Det oppstod for å bryte muren mellom Dev og Ops; små, hyppige endringer gir både fart og stabilitet.
- CALMS og «de tre veiene» beskriver kulturen. DORA-metrikkene måler resultatet.
- Agile og Scrum organiserer arbeidet i korte iterasjoner; Kanban gir kontinuerlig flyt.
- CI = integrer og test ofte. Continuous Delivery = alltid klar for prod (manuell knapp). Continuous Deployment = automatisk til prod.
- Deploy-strategier: rolling, blue-green, canary, feature flags – alle med plan for rollback.
- Observability = metrikker, logger og traces. Hendelser håndteres strukturert og uten skyld.
- SRE bruker SLI/SLO/error budget. Platform Engineering bygger selvbetjente plattformer. DevSecOps bygger sikkerhet inn i alle steg.

## Øvingsoppgaver

1. Forklar forskjellen på Continuous Delivery og Continuous Deployment til en medstudent på under ett minutt.
2. En tjeneste har SLO på 99,5 % over 30 dager. Hvor mange minutter error budget har den?
3. Skriv en blameless postmortem for et påfunnet scenario: «Nettbutikken var nede i 47 minutter fordi et TLS-sertifikat utløp.»
4. Lag et Kanban-brett i GitHub Projects eller Azure Boards for ditt neste prosjekt i kapittel 15.
5. Finn de fire DORA-metrikkene for ditt eget GitHub-prosjekt (så godt det lar seg gjøre): hvor ofte merger du til main, og hvor lang tid går det fra første commit til merge?

## Quiz

1. Nevn de fem bokstavene i CALMS og hva de står for.
2. Hvorfor er små, hyppige deployer mindre risikable enn store, sjeldne?
3. Hva er de fire DORA-metrikkene?
4. Hva er forskjellen på Scrum Master og Product Owner?
5. Hva er forskjellen på en SLO og en SLA?
6. Hva er et error budget?
7. Hvilken deploy-strategi sender en liten andel av trafikken til ny versjon først?
8. Hva betyr «shift left»?
9. Hva er forskjellen på monitoring og observability?
10. Hva er hovedmålet med Platform Engineering?

### Fasit

1. **C**ulture (samarbeid og felles ansvar), **A**utomation (automatisering), **L**ean (små leveranser, fjerne sløsing), **M**easurement (måling), **S**haring (deling av kunnskap).
2. Små endringer er lettere å teste, gjennomgå, forstå og rulle tilbake; når noe går galt, er det lett å finne hvilken endring som var årsaken.
3. Deployment frequency, lead time for changes, change failure rate, time to restore service (failed deployment recovery time).
4. **Product Owner** bestemmer *hva* som skal bygges og prioriterer backloggen. **Scrum Master** hjelper teamet med *prosessen* og fjerner hindringer.
5. **SLO** er et internt mål. **SLA** er en avtale med kunden med konsekvenser hvis den brytes.
6. Den mengden upålitelighet SLO-en tillater (100 % − SLO). Brukes til å balansere nye funksjoner mot stabilitet.
7. **Canary.**
8. Å flytte sikkerhet og testing tidligere i utviklingsprosessen, der feil er billigere å finne og rette.
9. **Monitoring** svarer på kjente spørsmål med forhåndsdefinerte metrikker og terskler. **Observability** er evnen til å forstå ukjente problemer ut fra systemets data (metrikker, logger, traces).
10. Å redusere kognitiv belastning for produktteam ved å tilby en intern, selvbetjent plattform med «golden paths», slik at de kan levere raskt og trygt.
