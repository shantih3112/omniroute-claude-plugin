# Del 13 – Cloud security og monitoring

**Læringsmål for kapitlet.** Når du er ferdig, skal du kunne:

- forklare IAM, minste privilegium og Zero Trust,
- håndtere hemmeligheter og kryptering riktig,
- sikre nettverk og skanne etter sårbarheter,
- planlegge backup og katastrofegjenoppretting,
- forklare og bruke logger, metrikker og traces (OpenTelemetry),
- sette opp Prometheus og Grafana, og bruke Azure Monitor,
- håndtere hendelser og feilsøke systematisk.

> **Hvorfor dette kapitlet er viktig:** De fleste alvorlige hendelser i skyen skyldes ikke avanserte angrep, men **grunnleggende feil**: lekkede nøkler, for brede tilganger, åpne lagringskontoer, manglende MFA, manglende oppdateringer og manglende overvåking. Det betyr også at du kan forhindre det meste med god grunnhygiene.

## Del A – Sikkerhet

### CIA-triaden

All informasjonssikkerhet handler om tre mål:

| Mål | Betyr | Trussel | Tiltak |
|---|---|---|---|
| **Confidentiality** (konfidensialitet) | Bare de som skal, kan lese data | Datalekkasje | Tilgangskontroll, kryptering |
| **Integrity** (integritet) | Data endres ikke uautorisert | Manipulering | Signering, hashing, tilgangskontroll, logging |
| **Availability** (tilgjengelighet) | Systemet er tilgjengelig når det trengs | DDoS, løsepengevirus, feil | Redundans, backup, DDoS-beskyttelse |

### Identity and Access Management (IAM)

**Hva er det?** IAM handler om å styre **hvem** (identitet) som får gjøre **hva** (tilgang), på **hvilke ressurser**, og **under hvilke betingelser**.

```text
 AUTENTISERING (AuthN)          AUTORISASJON (AuthZ)
 «Hvem er du?»                  «Hva får du gjøre?»
 passord + MFA, sertifikat,     RBAC-roller, policyer,
 managed identity, OIDC-token   betingelser (Conditional Access)
```

**Typer identiteter:**

| Type | Eksempler | Beste praksis |
|---|---|---|
| **Menneskelige** | Ansatte, konsulenter, gjester | MFA (helst phishing-resistent), SSO, Conditional Access, PIM for admin-roller |
| **Arbeidslast-identiteter** (*workload identities*) | Apper, pipelines, skript | Managed identity, workload identity federation (OIDC) – **ikke** passord/nøkler |

**I Azure** (kapittel 7.1): Entra ID for identitet, Azure RBAC for tilgang til ressurser, Conditional Access for betingelser, PIM for midlertidig admin-tilgang, managed identities for apper.

**Livssyklus:** *Joiner – Mover – Leaver*. Når noen slutter, skal **all** tilgang fjernes umiddelbart. Når noen bytter rolle, skal gammel tilgang fjernes (ellers «samler» folk på seg tilganger over tid – *privilege creep*). Gjennomfør jevnlige **tilgangsgjennomganger** (*access reviews*).

### Least privilege – minste privilegium

**Hva er det?** Hver identitet skal ha **akkurat** den tilgangen den trenger, på **minst mulig** scope, i **kortest mulig** tid.

> **Hverdagsanalogi:** Et hotell gir deg nøkkelkort til **ditt** rom i **dine** netter – ikke en universalnøkkel til hele hotellet for alltid. Rengjøringspersonalet har tilgang til flere rom, men bare i arbeidstiden.

**I praksis:**

- *Reader* som standard; *Contributor* bare der det trengs; *Owner* nesten aldri.
- Gi tilgang til **grupper**, ikke enkeltpersoner.
- Gi på **ressursgruppe**-nivå, ikke abonnement, når det holder.
- Bruk **tjenestespesifikke roller** (*Key Vault Secrets User*, *AcrPull*, *Storage Blob Data Reader*) i stedet for brede roller.
- **Just-in-time**: PIM for administratorroller; JIT VM-tilgang.
- Separate kontoer for administrasjon og hverdagsbruk i modne organisasjoner.
- Ingen mennesker med skrivetilgang til produksjon i det daglige – endringer går via pipeline.

> **Vanlig feil:** Å gi en CI/CD-pipeline *Owner* på hele abonnementet «for å slippe tilgangsproblemer». Blir pipelinen kompromittert, har angriperen alt.

### Secrets management – håndtering av hemmeligheter

**Hva er hemmeligheter?** Passord, API-nøkler, tilkoblingsstrenger, private nøkler, sertifikater, tokens.

**Hierarkiet – fra verst til best:**

```text
 ✗ Hardkodet i koden / i Git
 ✗ I konfigurasjonsfiler på disk
 ~ I miljøvariabler (bedre, men må komme fra et sted og roteres)
 ✓ I et hemmelighetshvelv (Azure Key Vault), hentet ved kjøring
 ✓✓ Ingen hemmelighet: managed identity / workload identity federation
```

**Regler:**

1. Aldri hemmeligheter i Git – bruk `.gitignore`, pre-commit-hooks (gitleaks) og GitHub secret scanning med *push protection*.
2. Sentral lagring (Key Vault) med RBAC og revisjonslogg.
3. **Rotasjon** – bytt hemmeligheter jevnlig og automatisk; Key Vault kan varsle før utløp.
4. **Kortlevde legitimasjoner** fremfor langlivede.
5. Ikke logg hemmeligheter.
6. Ved lekkasje: **roter først**, undersøk etterpå.

### Kryptering

**Kryptering i ro** (*at rest*) – data lagret på disk er kryptert. I Azure er dette **på som standard** for Storage, Managed Disks, SQL (TDE) og de fleste tjenester, med Microsoft-administrerte nøkler.

**Kryptering under overføring** (*in transit*) – data som sendes over nettverket er kryptert med **TLS**. Krev TLS 1.2 eller nyere og HTTPS overalt, også internt.

**Kryptering i bruk** (*in use*) – data krypteres også mens det behandles i minnet (**confidential computing**, f.eks. Azure confidential VMs). Avansert.

**Nøkkelhåndtering:**

| Modell | Hvem kontrollerer nøkkelen | Bruk |
|---|---|---|
| Plattformadministrerte nøkler (PMK) | Microsoft | Standard, null arbeid |
| **Kundeadministrerte nøkler (CMK)** | Du, i Key Vault / Managed HSM | Regulatoriske krav, mulighet til å «trekke tilbake» tilgang |
| Kundelevert nøkkel per forespørsel | Du, ved hver forespørsel | Spesielle behov |

**Begreper du bør kjenne:**

- **Symmetrisk kryptering** – samme nøkkel krypterer og dekrypterer (AES). Rask; brukes for store datamengder.
- **Asymmetrisk kryptering** – nøkkelpar (RSA, ECC); brukes til nøkkelutveksling og signaturer (kapittel 2).
- **Hashing** – enveisfunksjon (SHA-256). Brukes til integritetssjekk og passordlagring (med salt og trege algoritmer som bcrypt/Argon2).
- **Digital signatur** – bevis på hvem som laget noe og at det ikke er endret (f.eks. signerte container-images).

> **Vanlig feil:** Å «kryptere» med base64. Base64 er **koding**, ikke kryptering – alle kan dekode det.

### Nettverkssikkerhet

**Defense in depth** – flere lag med beskyttelse, slik at ett brudd ikke gir full tilgang:

```text
 ┌──────────────────────────────────────────────────────────┐
 │ Fysisk sikkerhet (datasenteret – leverandørens ansvar)   │
 │ ┌──────────────────────────────────────────────────────┐ │
 │ │ Identitet og tilgang (MFA, RBAC, Conditional Access) │ │
 │ │ ┌──────────────────────────────────────────────────┐ │ │
 │ │ │ Perimeter (DDoS Protection, Front Door/WAF,      │ │ │
 │ │ │            Azure Firewall)                       │ │ │
 │ │ │ ┌──────────────────────────────────────────────┐ │ │ │
 │ │ │ │ Nettverk (VNet, NSG, private endpoints)      │ │ │ │
 │ │ │ │ ┌──────────────────────────────────────────┐ │ │ │ │
 │ │ │ │ │ Compute (patching, herding, EDR)         │ │ │ │ │
 │ │ │ │ │ ┌──────────────────────────────────────┐ │ │ │ │ │
 │ │ │ │ │ │ Applikasjon (sikker kode, skanning)  │ │ │ │ │ │
 │ │ │ │ │ │ ┌──────────────────────────────────┐ │ │ │ │ │ │
 │ │ │ │ │ │ │ DATA (kryptering, klassifisering)│ │ │ │ │ │ │
 └─┴─┴─┴─┴─┴─┴──────────────────────────────────┴─┴─┴─┴─┴─┴─┘
```

**Tiltak i Azure:**

| Tiltak | Tjeneste |
|---|---|
| Segmentering | VNets, subnett, NSG, ASG |
| Sentral brannmur og utgående kontroll | Azure Firewall, NAT Gateway, UDR |
| Webbeskyttelse | WAF på Application Gateway / Front Door |
| DDoS-beskyttelse | Grunnleggende er inkludert; **Azure DDoS Protection** for utvidet beskyttelse |
| Ingen offentlig eksponering av PaaS | **Private Endpoints** + *public network access disabled* |
| Sikker admin-tilgang | Azure Bastion, JIT, VPN – aldri åpen SSH/RDP |
| Synlighet | NSG/VNet flow logs, Network Watcher |

### Zero Trust

**Hva er det?** En sikkerhetsmodell som går ut fra at **ingenting er automatisk til å stole på** – verken brukere, enheter eller nettverk – selv om de er «innenfor». Den gamle modellen var «borgen med vollgrav»: stol på alt innenfor brannmuren. Problemet: når en angriper først er inne (via phishing, en sårbar server), kan de bevege seg fritt.

**De tre prinsippene** (Microsofts formulering):

1. **Verify explicitly** – autentiser og autoriser alltid basert på alle tilgjengelige signaler: identitet, lokasjon, enhetens helse, tjeneste, dataklassifisering, avvik.
2. **Use least privilege access** – JIT og JEA (*just enough access*), risikobaserte policyer, databeskyttelse.
3. **Assume breach** – anta at angriperen allerede er inne: segmenter for å begrense skadeomfang (*blast radius*), krypter ende-til-ende, overvåk og analyser for å oppdage trusler.

> **Hverdagsanalogi:** En flyplass. Du viser pass ved innsjekk, går gjennom sikkerhetskontroll, viser boardingkort ved gaten – og selv om du er «inne på flyplassen», kommer du ikke inn i cockpiten eller bagasjehallen. Hver dør sjekker på nytt.

### Sårbarhetsskanning (*vulnerability scanning*)

**Hva er det?** Automatisk leting etter **kjente sårbarheter** (registrert som **CVE**-er, *Common Vulnerabilities and Exposures*, med alvorlighetsgrad etter **CVSS**-skala) og feilkonfigurasjoner.

| Hva skannes | Verktøy (eksempler) | Når |
|---|---|---|
| Egen kildekode (SAST) | CodeQL (GitHub code scanning), SonarQube, Semgrep | Hver PR |
| Avhengigheter (SCA) | Dependabot, `pip-audit`, `npm audit`, Trivy | Hver PR + daglig |
| Hemmeligheter | GitHub secret scanning, gitleaks | Hver push |
| Container-images | Trivy, Grype, Docker Scout, Defender for Containers | Ved bygg + kontinuerlig i registeret |
| IaC | Checkov, Trivy, tfsec, PSRule for Azure | Hver PR |
| Kjørende webapp (DAST) | OWASP ZAP | Mot staging |
| Sky-konfigurasjon (CSPM) | **Microsoft Defender for Cloud** (secure score, anbefalinger) | Kontinuerlig |
| VM-er / OS | Defender for Servers, Azure Update Manager | Kontinuerlig |

```bash
# Eksempler
$ pip-audit                                  # sårbarheter i Python-avhengigheter
$ trivy fs .                                 # skann prosjektmappen (avhengigheter, IaC, hemmeligheter)
$ trivy image minapp:1.0 --severity HIGH,CRITICAL
$ checkov -d infra/                          # skann Terraform/Bicep for feilkonfigurasjon
```

**Prioritering:** Du kan ikke fikse alt med en gang. Prioriter etter alvorlighet, om sårbarheten faktisk kan utnyttes (er pakken i bruk? er tjenesten eksponert?), og om den utnyttes aktivt i verden (f.eks. CISA KEV-listen).

**OWASP Top 10** er listen over de vanligste sårbarhetene i webapplikasjoner (f.eks. *Broken Access Control*, *Injection*, *Security Misconfiguration*). Les den – den kommer ofte opp i intervjuer.

**Forsyningskjedesikkerhet** (*supply chain security*): angrep via avhengigheter, byggeverktøy eller CI-systemer. Tiltak: lås versjoner, bruk interne speil av pakkeregistre, generer SBOM, signer artefakter, og følg rammeverk som **SLSA**.

### Backup og disaster recovery

Begrepene RPO og RTO ble forklart i kapittel 6, og Azure Backup og Site Recovery i kapittel 7.3. Her er prinsippene.

**3-2-1-regelen:**

- **3** kopier av dataene,
- på **2** forskjellige typer lagring/medier,
- **1** kopi utenfor hovedlokasjonen (annen region).

Moderne tillegg: **1** kopi som er **uforanderlig eller frakoblet** (*immutable/air-gapped*) – beskyttelse mot løsepengevirus som prøver å slette backupene – og **0** feil ved test av gjenoppretting (**3-2-1-1-0**).

**Hva må beskyttes?**

| Komponent | Hvordan |
|---|---|
| Databaser | Automatisk backup + PITR, geo-replikering |
| Filer og blobs | Soft delete, versjonering, immutable storage, Azure Backup |
| VM-er | Azure Backup, Site Recovery |
| Kubernetes | Konfigurasjonen ligger i Git (GitOps); persistente volumer med AKS Backup / Velero |
| **Infrastrukturen** | **IaC i Git** – kan gjenoppbygges |
| Hemmeligheter og nøkler | Key Vault med soft delete og purge protection |
| Konfigurasjon og kode | Git (med backup av Git-plattformen) |

**DR-plan** – dokumenter og **øv**:

1. Hva er kritisk, og hva er RPO/RTO for hver tjeneste?
2. Hvem bestemmer at vi aktiverer DR?
3. Steg-for-steg-runbook for failover og tilbakeføring (*failback*).
4. Avhengigheter (DNS, identitet, tredjeparter).
5. **Regelmessige øvelser** – minst årlig, gjerne oftere.

> **Husk:** Backup handler om **gjenoppretting**. Mål suksess på om du faktisk klarte å gjenopprette innen RTO, ikke på om backupjobben var grønn.

## Del B – Monitoring og observability

### Hvorfor overvåke?

- **Oppdage** problemer før kundene gjør det.
- **Feilsøke** raskt når noe skjer.
- **Forstå** ytelse, kapasitet og kostnader.
- **Måle** mot SLO-er (kapittel 8).
- **Sikkerhet** – oppdage angrep og misbruk.

### Logging

**Hva er det?** Logger er **tidsstemplede hendelser** med detaljer: «kl. 10:15:03 feilet betaling for ordre 123 med timeout mot Vipps».

**Gode logger er:**

- **Strukturerte** (JSON), slik at de kan søkes og filtreres på felt:

```json
{"tid":"2026-10-30T10:15:03Z","nivå":"ERROR","tjeneste":"betaling","ordre_id":123,
 "feil":"timeout","varighet_ms":5003,"trace_id":"4bf92f3577b34da6a3ce929d0e0e4736"}
```

- **På riktig nivå** (DEBUG/INFO/WARNING/ERROR – kapittel 4).
- **Med kontekst**: request-ID / trace-ID, bruker-ID (ikke personopplysninger), versjon.
- **Uten hemmeligheter og unødvendige personopplysninger** (GDPR!).
- **Sentralisert**: samlet på ett sted (Log Analytics, Elasticsearch/OpenSearch, Grafana Loki, Splunk).
- **Med oppbevaringstid** tilpasset behov og lovkrav (og kostnad).

**Typer logger i skyen:**

| Type | Eksempel | I Azure |
|---|---|---|
| Applikasjonslogger | Appens egne meldinger | Application Insights, container-logger |
| Plattformlogger | Ressurslogger fra tjenester | Diagnostic settings → Log Analytics |
| Revisjonslogger (*audit*) | Hvem gjorde hva i kontrollplanet | Activity log, Entra-innloggingslogger |
| Sikkerhetslogger | Innlogginger, avvik | Microsoft Sentinel (SIEM) |

### Metrics – metrikker

**Hva er det?** Tall målt over tid (tidsserier): CPU-bruk, antall forespørsler per sekund, responstid, feilrate, kølengde.

**Hvorfor?** Metrikker er billige å lagre, raske å spørre i, og perfekte for **dashboards og varsler**. Logger forteller *hva* som skjedde i detalj; metrikker forteller *hvor mye* og *hvor ofte*.

**Metrikktyper** (Prometheus-terminologi):

| Type | Beskrivelse | Eksempel |
|---|---|---|
| **Counter** | Øker bare (nullstilles ved restart) | `http_requests_total` |
| **Gauge** | Kan gå opp og ned | `memory_usage_bytes`, `queue_length` |
| **Histogram** | Fordeling i «bøtter» | `http_request_duration_seconds` (gir persentiler) |
| **Summary** | Ferdigberegnede persentiler | Brukes sjeldnere |

**Rammeverk for hva du skal måle:**

- **De fire gylne signalene** (kapittel 8): latency, traffic, errors, saturation.
- **RED** for tjenester: **R**ate (forespørsler/s), **E**rrors (feil/s), **D**uration (responstid).
- **USE** for ressurser: **U**tilization (utnyttelse), **S**aturation (kø/metning), **E**rrors.

> **Husk:** Mål **persentiler**, ikke bare gjennomsnitt. Hvis snittet er 200 ms men **p99** er 4 sekunder, har 1 av 100 brukere en elendig opplevelse – og gjennomsnittet skjuler det.

### Tracing – sporing

**Hva er det?** En **trace** følger **én forespørsel** gjennom alle tjenestene den berører, med tidsbruk i hvert ledd (**spans**).

```text
 Trace 4bf92f35...  (totalt 820 ms)
 ├─ frontend   GET /kasse                         ████████████████████  820 ms
 │  ├─ api     POST /ordre                          ████████████████    700 ms
 │  │  ├─ db   INSERT ordre                          ██                  60 ms
 │  │  └─ betaling  POST /betal                        ████████████     580 ms  ← flaskehalsen!
 │  │       └─ ekstern Vipps-API                         ███████████    540 ms
```

**Hvorfor?** I mikrotjenestearkitekturer er det umulig å finne ut hvorfor noe er tregt bare ved å se på logger fra hver tjeneste for seg. Tracing viser hele kjeden.

**Hvordan?** Hver forespørsel får en **trace-ID** som sendes videre i HTTP-headere (standarden **W3C Trace Context**, headeren `traceparent`) til neste tjeneste. Logger som inkluderer trace-ID-en, kan kobles til tracen.

### OpenTelemetry

**Hva er det?** **OpenTelemetry (OTel)** er en åpen, leverandøruavhengig standard og et sett med SDK-er og verktøy for å **samle inn traces, metrikker og logger** fra applikasjoner. Et CNCF-prosjekt. Instrumenter koden én gang med OTel, og send dataene dit du vil (Azure Monitor, Prometheus, Grafana, Jaeger, Datadog …).

```text
 App (OTel SDK) ──OTLP──► OpenTelemetry Collector ──► Azure Monitor / Application Insights
                                                 ├──► Prometheus (metrikker)
                                                 └──► Jaeger / Tempo (traces)
```

**Python med Azure Monitor:**

```python
# pip install azure-monitor-opentelemetry flask
from azure.monitor.opentelemetry import configure_azure_monitor
configure_azure_monitor()          # leser APPLICATIONINSIGHTS_CONNECTION_STRING fra miljøet
                                   # og instrumenterer automatisk Flask, requests, logging m.m.
from flask import Flask
app = Flask(__name__)
```

### Prometheus

**Hva er det?** **Prometheus** er et åpen kildekode-system for **innsamling og lagring av metrikker** og **varsling**, og de facto standard i Kubernetes-verdenen (CNCF-prosjekt).

**Hvordan fungerer det?**

```text
 ┌────────────┐  /metrics (HTTP)  ┌──────────────────────┐   PromQL   ┌─────────┐
 │ App        │◄────── scrape ────│ PROMETHEUS SERVER    │◄───────────│ Grafana │
 │ node-      │   hvert 15. sek   │ (tidsseriedatabase)  │            └─────────┘
 │ exporter   │                   │ + varslingsregler    │──alerts──►┌──────────────┐
 │ kube-state │                   └──────────────────────┘           │ Alertmanager │─► e-post,
 └────────────┘                                                      └──────────────┘   Slack, Teams
```

- Prometheus **henter** (*pull/scrape*) metrikker fra et HTTP-endepunkt, typisk `/metrics`, på hvert mål.
- **Exporters** gjør metrikker tilgjengelige for ting som ikke har det selv: **node_exporter** (Linux-servere), **kube-state-metrics** (Kubernetes-objekter), blackbox_exporter (sjekker URL-er utenfra).
- **PromQL** er spørrespråket.
- **Alertmanager** grupperer, demper og sender varsler.

**Eksponer metrikker fra en Python-app:**

```python
# pip install prometheus-client flask
from flask import Flask
from prometheus_client import Counter, Histogram, make_wsgi_app
from werkzeug.middleware.dispatcher import DispatcherMiddleware

app = Flask(__name__)
FORESPØRSLER = Counter("app_requests_total", "Antall forespørsler", ["endepunkt", "status"])
VARIGHET = Histogram("app_request_duration_seconds", "Responstid", ["endepunkt"])

@app.route("/")
def hjem():
    with VARIGHET.labels("/").time():                 # mål tiden
        FORESPØRSLER.labels("/", "200").inc()         # tell forespørselen
        return "Hei!"

# Legg /metrics til appen
app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {"/metrics": make_wsgi_app()})
```

```text
$ curl localhost:8000/metrics
# HELP app_requests_total Antall forespørsler
# TYPE app_requests_total counter
app_requests_total{endepunkt="/",status="200"} 42.0
app_request_duration_seconds_bucket{endepunkt="/",le="0.005"} 40.0
...
```

**PromQL-eksempler:**

```promql
# Forespørsler per sekund siste 5 minutter
rate(app_requests_total[5m])

# Feilrate i prosent
100 * sum(rate(app_requests_total{status=~"5.."}[5m])) / sum(rate(app_requests_total[5m]))

# 95-persentil responstid
histogram_quantile(0.95, sum(rate(app_request_duration_seconds_bucket[5m])) by (le))

# Ledig diskplass i prosent (node_exporter)
100 * node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}
```

**Varslingsregel:**

```yaml
groups:
  - name: app
    rules:
      - alert: HøyFeilrate
        expr: |
          sum(rate(app_requests_total{status=~"5.."}[5m]))
            / sum(rate(app_requests_total[5m])) > 0.05
        for: 10m                            # må vare i 10 minutter før varsel
        labels:
          severity: critical
        annotations:
          summary: "Feilraten er over 5 % i 10 minutter"
          runbook: "https://wiki.firma.no/runbooks/hoy-feilrate"
```

**Kjør Prometheus og Grafana lokalt med Docker Compose:**

```yaml
# compose.yaml
services:
  prometheus:
    image: prom/prometheus:v3.0.0          # sjekk siste versjon
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports: ["9090:9090"]
  node-exporter:
    image: prom/node-exporter:v1.8.2
  grafana:
    image: grafana/grafana:11.3.0
    ports: ["3000:3000"]                   # logg inn admin/admin første gang og bytt passord
```

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
scrape_configs:
  - job_name: prometheus
    static_configs: [{ targets: ["localhost:9090"] }]
  - job_name: node
    static_configs: [{ targets: ["node-exporter:9100"] }]
```

I Kubernetes installeres alt med Helm-charten **kube-prometheus-stack** (kapittel 10). I Azure finnes **Azure Monitor managed service for Prometheus** – Microsoft drifter lagringen, og du bruker PromQL og Grafana som vanlig.

### Grafana

**Hva er det?** **Grafana** er et åpen kildekode-verktøy for **visualisering og dashboards**. Det kobler seg til mange datakilder: Prometheus, Azure Monitor, Log Analytics, Loki (logger), Tempo (traces), Elasticsearch, SQL-databaser.

**Bruk:**

1. *Connections → Data sources → Add* → Prometheus → URL `http://prometheus:9090`.
2. *Dashboards → New → Add visualization* → skriv en PromQL-spørring.
3. Eller *Import* et ferdig dashboard fra grafana.com (f.eks. «Node Exporter Full»).

**Gode dashboards:**

- Ett dashboard per tjeneste med **RED**-metrikker øverst.
- Fra overblikk (er alt grønt?) til detaljer (hvilken pod/endepunkt?).
- Merk deployer på tidsaksen (*annotations*) – «feilene startet rett etter deploy kl. 14:02».
- Ikke for mange paneler; hvert panel skal svare på et spørsmål.

**Azure Managed Grafana** er en administrert Grafana-tjeneste i Azure, integrert med Entra ID og Azure Monitor.

### Azure Monitor – oppsummert

Azure Monitor (kapittel 7.3) er Azures samlede plattform:

| Behov | Azure Monitor-komponent |
|---|---|
| Plattformmetrikker | Metrics (automatisk) |
| Logger | Log Analytics workspace + KQL |
| Applikasjonsovervåking | **Application Insights** (OpenTelemetry-basert): forespørsler, avhengigheter, unntak, *Application Map*, distribuert tracing |
| VM-er | Azure Monitor Agent + VM insights |
| Kubernetes | Container Insights + managed Prometheus + Managed Grafana |
| Syntetiske tester | Application Insights *availability tests* (sjekker URL-en din fra flere steder i verden) |
| Varsler | Alert rules + action groups (+ alert processing rules for demping) |
| Sikkerhet | **Microsoft Sentinel** (SIEM/SOAR) bygget på Log Analytics |

**Varslingsfilosofi** – unngå *alert fatigue* (folk slutter å reagere fordi det er for mange varsler):

- Varsle på **symptomer** brukerne merker (høy feilrate, treg responstid, SLO i fare), ikke på hver høy CPU-topp.
- Hvert varsel skal være **handlingsbart** og ha en **runbook**.
- Skill mellom **page** (vekk noen nå – kritisk) og **ticket** (fiks i arbeidstiden).
- Gå gjennom og rydd i varsler jevnlig.

## Del C – Hendelseshåndtering og feilsøking

### Incident response

**Sikkerhetshendelser** og **driftshendelser** håndteres etter samme grunnmønster, men sikkerhetshendelser krever ekstra hensyn (bevis, varsling til myndigheter).

**NIST-modellen for hendelseshåndtering:**

```text
 1. FORBEREDELSE        2. OPPDAGELSE OG      3. BEGRENSNING, FJERNING    4. ETTER-
 (planer, roller,       ANALYSE               OG GJENOPPRETTING           AKTIVITETER
  verktøy, øvelser) ──► (varsler, logger, ──► (isoler, fjern trusselen, ──► (postmortem,
                         triage, alvorlig-     gjenopprett fra ren         forbedringer)
                         het)                  backup)
        ▲                                                                       │
        └───────────────────────── lærdom tilbake ◄────────────────────────────┘
```

**Eksempel – lekket lagringskontonøkkel funnet i et offentlig GitHub-repo:**

1. **Oppdag:** GitHub secret scanning varsler.
2. **Begrens umiddelbart:** roter nøkkelen (`az storage account keys renew`), og vurder å slå av nøkkelbasert tilgang helt.
3. **Analyser:** les lagringskontoens logger i Log Analytics – har noen brukt nøkkelen? Hva ble lest/endret?
4. **Fjern:** fjern hemmeligheten fra koden; skriv om Git-historikken hvis nødvendig.
5. **Gjenopprett:** gjenopprett eventuelt endrede data fra versjonering/backup.
6. **Varsle:** hvis personopplysninger kan være berørt – GDPR krever som hovedregel varsling til **Datatilsynet innen 72 timer**. Følg virksomhetens rutiner.
7. **Lær:** innfør push protection, managed identity i stedet for nøkler, og Azure Policy som krever *allowSharedKeyAccess = false*.

**Under en hendelse:**

- Utnevn en **incident commander**.
- Ha én kommunikasjonskanal og en løpende logg med tidsstempler.
- Prioriter: **stopp blødningen** (mitigate) før du finner grunnårsaken.
- Ikke slett bevis ved sikkerhetshendelser (ta snapshot av disker før du gjenoppbygger).
- Kommuniser jevnlig til interessenter og kunder.

### Troubleshooting – en generell metode

Den viktigste ferdigheten til en DevOps Engineer. Bruk **den vitenskapelige metoden**:

```text
 1. Definer problemet presist   «/kasse gir 502 for ca. 30 % av forespørslene siden 14:05»
 2. Samle data                  dashboards, logger, traces, siste endringer (deploy? konfig?)
 3. Lag hypoteser               «én av podene har feil konfigurasjon etter deploy»
 4. Test én hypotese om gangen  sjekk podene; sammenlign; port-forward til hver
 5. Fiks (mitigate først)       rollback til forrige versjon → feilen forsvinner
 6. Verifiser                   feilrate tilbake til normalt
 7. Finn grunnårsak og dokumenter → postmortem, tiltak, oppdater runbook
```

**Spørsmål som ofte løser saken:**

- **Hva er endret?** Deploy, konfigurasjon, sertifikat, avhengighet, trafikk, data? (Over halvparten av hendelser skyldes endringer.)
- **Hva er felles** for det som feiler? (Én region, én node, én versjon, én kundetype?)
- **Hvor i kjeden** stopper det? (DNS → nettverk → lastbalanserer → app → database – kapittel 2.)
- **Hva sier dataene**, ikke hva du *tror*?

**Verktøykasse per lag:**

| Lag | Verktøy |
|---|---|
| DNS | `dig`, `nslookup` |
| Nettverk/port | `curl -v`, `nc -zv`, Network Watcher, NSG flow logs |
| TLS | `openssl s_client` |
| Lastbalanserer/gateway | Backend health, gateway-logger |
| Kubernetes | `kubectl describe/logs/get events`, `kubectl top` |
| Container | `docker logs/inspect/exec` |
| VM/OS | `systemctl`, `journalctl`, `top`, `df -h`, `free -h` |
| Applikasjon | Application Insights, traces, logger |
| Database | Query performance insights, langsomme spørringer, låser |
| Azure-plattform | Service Health, Activity log, Resource health |

> **Vanlig feil:** Å endre mange ting samtidig under feilsøking. Da vet du ikke hva som løste problemet – eller hva som skapte et nytt. Én endring om gangen, og noter alt.

## Kapitteloppsummering

- Sikkerhet bygger på CIA-triaden, defense in depth og Zero Trust (verify explicitly, least privilege, assume breach).
- IAM: sterk autentisering (MFA), minste privilegium, managed identities og OIDC for arbeidslaster.
- Hemmeligheter i Key Vault – eller enda bedre: ingen hemmeligheter. Krypter i ro og under overføring.
- Skann kode, avhengigheter, images, IaC og sky-konfigurasjon kontinuerlig.
- Backup etter 3-2-1(-1-0), og test gjenoppretting.
- Observability: logger (hendelser), metrikker (tall over tid), traces (forespørselens reise), samlet med OpenTelemetry.
- Prometheus samler metrikker med pull og PromQL; Grafana visualiserer; Azure Monitor er Azures samlede plattform.
- Hendelser håndteres strukturert; feilsøking gjøres med hypoteser og én endring om gangen.

## Øvingsoppgaver

1. Gå gjennom ditt eget Azure-abonnement: hvem har Owner? Har alle MFA? Finnes det lagringskontoer med offentlig tilgang? (Se Microsoft Defender for Cloud → Recommendations.)
2. Kjør `trivy fs .` og `pip-audit` på et av prosjektene dine, og fiks minst én funnet sårbarhet.
3. Installer gitleaks som pre-commit-hook, og test at den stopper en commit med en falsk nøkkel.
4. Kjør Prometheus, node-exporter og Grafana med Compose. Importer «Node Exporter Full»-dashboardet.
5. Legg til Prometheus-metrikker i Flask-appen og lag et Grafana-dashboard med RED-metrikker.
6. Skriv en DR-plan (1–2 sider) for prosjekt 10 i kapittel 15: RPO, RTO, backup, failover-steg.
7. Lag en Application Insights *availability test* som sjekker appen din hvert 5. minutt, med varsel på e-post.

## Quiz

1. Hva står C, I og A for i CIA-triaden?
2. Hva er de tre prinsippene i Zero Trust?
3. Hva er forskjellen på autentisering og autorisasjon?
4. Hvorfor er managed identity bedre enn en lagret tilkoblingsstreng?
5. Hva er forskjellen på kryptering i ro og under overføring?
6. Hva er en CVE?
7. Hva er 3-2-1-regelen?
8. Hva er forskjellen på logger, metrikker og traces?
9. Hvorfor bør du se på p99 og ikke bare gjennomsnittlig responstid?
10. Bruker Prometheus push eller pull for å samle metrikker?
11. Hva er OpenTelemetry?
12. Hva er det første du gjør når du oppdager at en hemmelighet har lekket?

### Fasit

1. **Confidentiality** (konfidensialitet), **Integrity** (integritet), **Availability** (tilgjengelighet).
2. **Verify explicitly**, **use least privilege access**, **assume breach**.
3. **Autentisering**: bekrefte hvem du er. **Autorisasjon**: bestemme hva du får gjøre.
4. Det finnes ingen hemmelighet som kan lekke, glemmes i kode eller må roteres; Azure utsteder kortlevde tokens automatisk, og tilgangen styres med RBAC.
5. **I ro**: data lagret på disk er kryptert. **Under overføring**: data som sendes over nettverket er kryptert (TLS).
6. *Common Vulnerabilities and Exposures* – en offentlig registrert, kjent sårbarhet med en unik ID (f.eks. CVE-2021-44228).
7. Tre kopier av dataene, på to forskjellige medier/lagringstyper, hvorav én utenfor hovedlokasjonen.
8. **Logger**: detaljerte hendelser. **Metrikker**: tall målt over tid. **Traces**: en forespørsels vei gjennom flere tjenester med tidsbruk per ledd.
9. Fordi gjennomsnittet skjuler de tregeste forespørslene; p99 viser opplevelsen til de 1 % verst stilte brukerne.
10. **Pull** – Prometheus scraper `/metrics`-endepunkter.
11. En åpen, leverandøruavhengig standard med SDK-er og verktøy for å samle inn traces, metrikker og logger fra applikasjoner.
12. **Roter (bytt ut) hemmeligheten umiddelbart**, så den lekkede verdien blir ubrukelig. Deretter undersøk misbruk og fjern den fra koden/historikken.
