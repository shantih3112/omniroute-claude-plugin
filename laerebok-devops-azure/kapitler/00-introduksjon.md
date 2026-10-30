# Introduksjon {.unnumbered}

## Velkommen {.unnumbered}

Denne boken er skrevet for deg som studerer DevOps Engineering, er ganske ny innen IT, og ønsker å forstå **hvorfor** ting fungerer – ikke bare pugge ord.

Mange lærebøker starter med «Kubernetes er en orkestreringsplattform for containere» og forventer at du skal nikke. Denne boken gjør det motsatte. Vi starter med hva en datamaskin faktisk er, bygger videre med nettverk, Linux og programmering, og først når grunnmuren står, bygger vi Cloud, Azure, Docker, Kubernetes, Terraform, CI/CD, sikkerhet og til slutt AI-infrastruktur oppå.

Tenk på boken som et hus:

```text
                    ┌──────────────────────────────┐
                    │  KAP 14  AI Infrastructure /  │   ← Taket: spesialisering
                    │          MLOps                │
                ┌───┴──────────────────────────────┴───┐
                │ KAP 12–13  CI/CD · Sikkerhet ·        │   ← Profesjonell drift
                │            Monitoring                 │
            ┌───┴───────────────────────────────────────┴───┐
            │ KAP 9–11  Docker · Kubernetes · Terraform      │   ← Moderne verktøy
        ┌───┴───────────────────────────────────────────────┴───┐
        │ KAP 6–8  Cloud · Microsoft Azure · DevOps-kultur        │   ← Plattformen
    ┌───┴───────────────────────────────────────────────────────┴───┐
    │ KAP 1–5  IT-grunnlag · Nettverk · Linux · Programmering · Git  │   ← Grunnmuren
    └────────────────────────────────────────────────────────────────┘
```

Hvis du hopper rett til taket, faller huset sammen. Hvis du bygger grunnmuren skikkelig, blir alt det andre mye enklere.

## Hvordan bruke boken {.unnumbered}

### Læringsmetoden i hvert kapittel {.unnumbered}

Hvert viktig konsept forklares med den samme faste oppskriften, slik at du alltid vet hvor du finner hva:

| Steg | Spørsmål | Hva du får |
|---|---|---|
| 1 | **Hva er det?** | Forklaring med helt enkle ord |
| 2 | **Hvorfor finnes det?** | Problemet teknologien løser |
| 3 | **Hvordan fungerer det?** | Steg-for-steg teknisk forklaring |
| 4 | **Hverdagsanalogi** | Restaurant, lager, bygning, bil … |
| 5 | **Fra arbeidslivet** | Hvordan en ekte bedrift bruker det |
| 6 | **Diagram** | Visuell forklaring |
| 7 | **Praktisk** | Kode, kommandoer, oppsett |
| 8 | **Vanlige feil** | Det nybegynnere misforstår |
| 9 | **Husk** | Kort oppsummering |
| 10 | **Test deg selv** | Kontrollspørsmål med forklarte svar |

For små begreper slår vi noen av stegene sammen, slik at boken ikke blir kunstig lang. For de store temaene (for eksempel Docker, Kubernetes og Azure-tjenestene) får du hele oppskriften.

### Faste bokser i teksten {.unnumbered}

> **Hverdagsanalogi:** Sammenligner teknologien med noe du kjenner fra før.

> **Fra arbeidslivet:** Viser hvordan dette brukes i en ekte bedrift.

> **Vanlig feil:** Noe nybegynnere (og erfarne!) ofte gjør feil.

> **Husk:** Det viktigste du må ta med deg.

> **Kostnad:** Advarsel om ting som kan koste penger i Cloud.

> **Fordypning:** Avansert stoff. Du kan hoppe over dette første gang du leser.

### Kodeblokker og terminal {.unnumbered}

Kommandoer du skal skrive i terminalen vises slik. Tegnet `$` betyr «skriv dette som vanlig bruker» og skal **ikke** skrives inn. Linjer uten `$` er resultatet du får tilbake:

```bash
$ whoami
student
```

Kommentarer i kode starter med `#` og forklarer hva linjen gjør. De er der for deg – maskinen ignorerer dem.

### Engelske begreper {.unnumbered}

IT-bransjen snakker engelsk, også i Norge. Første gang et begrep dukker opp, får du både det norske og det engelske ordet, for eksempel «lastbalansering (*load balancing*)». Senere bruker vi ofte det engelske ordet, fordi det er det du vil høre på jobb. Bakerst i boken finner du en ordliste.

### Tre måter å lese boken på {.unnumbered}

1. **Fra start til slutt** – anbefalt hvis du er helt ny. Kapitlene bygger på hverandre.
2. **Som oppslagsverk** – bruk innholdsfortegnelsen, ordlisten og hurtigreferansene.
3. **Prosjektdrevet** – start med et prosjekt i kapittel 15, og les kapitlene prosjektet viser til når du står fast.

> **Husk:** Du lærer DevOps med fingrene, ikke bare med øynene. Skriv kommandoene selv. Gjør feil. Fiks dem. Det er slik ferdighetene faktisk bygges.

## En ærlig forventningsavklaring {.unnumbered}

Å lese denne boken gjør deg ikke til senioringeniør. Ingen bok kan det. Det boken *kan* gjøre, er å gi deg:

- et solid mentalt kart over hvordan alle bitene henger sammen,
- presise forklaringer du kan komme tilbake til,
- oppgaver og prosjekter som bygger ekte, praktiske ferdigheter,
- en realistisk plan for de neste tolv månedene.

Erfaring kommer av å bygge, feile, feilsøke og bygge igjen – helst sammen med andre. En god juniorkandidat er ikke en som kan alt, men en som forstår grunnprinsippene, kan lære raskt og kan vise frem ekte prosjekter.

## Om kostnader og oppdatert informasjon {.unnumbered}

> **Kostnad:** Cloud-tjenester koster ekte penger. Gratiskontoer og studentkreditter har grenser. Hvert prosjekt i boken har en egen seksjon om **opprydding**. Følg den hver gang. Sett opp et budsjettvarsel (*budget alert*) i Azure før du gjør noe annet – det viser vi i kapittel 7.

Teknologi endrer seg raskt. Tjenester får nye navn (Azure Active Directory heter nå *Microsoft Entra ID*), priser endres, og verktøy får nye versjoner. Informasjonen i boken er skrevet ut fra offentlig dokumentasjon fra Microsoft Learn, Docker, Kubernetes, HashiCorp, GitHub og Python slik den var kjent per **oktober 2026**. Der noe er spesielt utsatt for endring, står det en merknad. **Sjekk alltid offisiell dokumentasjon før du stoler på priser, kvoter, eksamensinnhold og versjonsnumre.** En samlet kildeliste med lenker finner du i vedlegg D.

Boken bruker tekstbaserte diagrammer (laget med tegn) i stedet for skjermbilder. Det er et bevisst valg: skjermbilder av Azure Portal blir raskt utdaterte fordi Microsoft endrer utseendet ofte, mens diagrammene forklarer prinsippene som ikke endrer seg. Der et skjermbilde ville vært nyttig, beskriver teksten hva du skal se etter i portalen.

## Læringsreisen – oversikt {.unnumbered}

```text
  FASE 1: GRUNNMUR (mnd 1–3)            FASE 2: PLATTFORM (mnd 4–6)
  ┌──────────────────────────┐          ┌──────────────────────────┐
  │ IT-grunnlag   (kap 1)    │          │ Cloud Computing (kap 6)  │
  │ Nettverk      (kap 2)    │  ─────►  │ Microsoft Azure (kap 7)  │
  │ Linux         (kap 3)    │          │ DevOps-kultur   (kap 8)  │
  │ Python/Bash   (kap 4)    │          │ ► AZ-900                 │
  │ Git/GitHub    (kap 5)    │          └────────────┬─────────────┘
  └──────────────────────────┘                       │
                                                     ▼
  FASE 4: SPESIALISERING (mnd 10–12)    FASE 3: VERKTØY (mnd 7–9)
  ┌──────────────────────────┐          ┌──────────────────────────┐
  │ Sikkerhet/Monitor(kap 13)│          │ Docker          (kap 9)  │
  │ AI/MLOps        (kap 14) │  ◄─────  │ Kubernetes      (kap 10) │
  │ Sluttprosjekt   (kap 15) │          │ Terraform/IaC   (kap 11) │
  │ ► AZ-104, internship     │          │ CI/CD           (kap 12) │
  └──────────────────────────┘          └──────────────────────────┘
```

## Produksjonsplan og kapitteloversikt {.unnumbered}

Boken er bygget opp i 15 deler pluss vedlegg. Her er planen for hele boken, med hva hvert kapittel inneholder og hvilke praktiske leveranser du sitter igjen med.

| Del | Kapittel | Innhold | Du kan etterpå |
|---|---|---|---|
| 1 | Forstå IT fra bunnen | Datamaskin, OS, server, database, applikasjon, frontend/backend, internett, IP, DNS, HTTP(S), API, klient–server, virtualisering | Forklare hva som skjer når du åpner en nettside |
| 2 | Nettverk for DevOps | IPv4/IPv6, subnetting/CIDR, DNS, DHCP, TCP/UDP, porter, ruter/svitsj, brannmur, VPN, NAT, lastbalansering, proxy, TLS, statuskoder, SSH, feilsøking | Planlegge et VNet og feilsøke tilkoblingsproblemer |
| 3 | Linux | Distribusjoner, shell, filsystem, brukere, rettigheter, prosesser, systemd, pakker, SSH, Bash, cron, miljøvariabler, logger, sikkerhet | Drifte en Linux-server fra terminalen |
| 4 | Programmering for DevOps | Python fra null, datatyper, løkker, funksjoner, JSON/YAML, API-kall, feilhåndtering, logging, Bash, automatisering, Azure SDK | Skrive egne automatiseringsskript |
| 5 | Git og GitHub | Repo, commit, branch, merge, PR, konflikter, arbeidsflyter, GitHub Actions, samarbeid | Jobbe profesjonelt med versjonskontroll |
| 6 | Cloud Computing | Datasentre, IaaS/PaaS/SaaS, regioner/soner, skalering, HA, DR, sikkerhet, prising, delt ansvar, AWS/Azure/GCP | Velge riktig skytjeneste for et behov |
| 7 | Microsoft Azure A–Å | 30+ tjenester med opprettelse, sikkerhet, kostnad og øvelser; AZ-900 og AZ-104 med prøveeksamener | Administrere grunnleggende Azure-miljøer |
| 8 | DevOps Engineering | Kultur, Agile/Scrum, SDLC, CI/CD, deploy-strategier, observability, hendelser, SRE, Platform Engineering, DevSecOps | Forklare DevOps i et intervju |
| 9 | Docker | Images, containere, Dockerfile, Compose, registry, volumes, nettverk, sikkerhet, feilsøking | Containerisere en applikasjon |
| 10 | Kubernetes | Cluster, noder, pods, deployments, services, ingress, config, secrets, lagring, autoskalering, Helm, AKS | Deploye en app på Kubernetes |
| 11 | Infrastructure as Code | Terraform, state, moduler, remote state, Bicep, Ansible, GitOps | Bygge Azure-infrastruktur med kode |
| 12 | CI/CD og automatisering | GitHub Actions, Azure Pipelines, Jenkins, testing, artefakter, hemmeligheter, rollback, blue-green, canary | Bygge en pipeline fra kode til produksjon |
| 13 | Sikkerhet og overvåking | IAM, minste privilegium, kryptering, Zero Trust, skanning, backup, logger, metrikker, tracing, Prometheus, Grafana, hendelseshåndtering | Sikre og overvåke et system |
| 14 | AI Infrastructure og MLOps | GPU, modellservering, ML-pipelines, Azure ML, Azure AI-tjenester, LLM-infrastruktur, kostnader, karrierevei | Forstå hvordan AI kjøres i produksjon |
| 15 | Virkelige prosjekter | 12 prosjekter med økende vanskelighetsgrad | Vise frem en sterk portefølje |
| A–E | Vedlegg | Ordliste, hurtigreferanser, sertifiseringer, kilder, 12-måneders læringsplan | Repetere og planlegge videre |

**Slik er hvert kapittel bygget opp:** læringsmål → forklaringer med læringsmetoden → praktiske øvelser → kapitteloppsummering → quiz med fasit.

**Kvalitetsprinsipper for boken:**

- Ingen plassholdere og ingen «forklaring kommer senere».
- Alle kommandoer er ekte kommandoer fra offisielle verktøy.
- Grunnleggende stoff og fordypning holdes adskilt.
- Kostnader og gratisalternativer nevnes eksplisitt.
- Informasjon som endres ofte er merket med dato og kilde.
