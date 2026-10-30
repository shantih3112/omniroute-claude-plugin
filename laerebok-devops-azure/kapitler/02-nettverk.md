# Del 2 – Nettverk for DevOps

**Læringsmål for kapitlet.** Når du er ferdig, skal du kunne:

- lese og forstå IPv4- og IPv6-adresser, og skille private fra offentlige,
- regne ut subnett med CIDR-notasjon (for eksempel hvor mange adresser `/24` gir),
- forklare DNS, DHCP, TCP, UDP og porter,
- forklare ruter, svitsj, brannmur, NAT, VPN, lastbalanserer, proxy og reverse proxy,
- forstå TLS-sertifikater og HTTP-statuskoder,
- bruke SSH og feilsøke nettverksproblemer systematisk med standardverktøy.

> **Hvorfor må en DevOps Engineer kunne nettverk?** Fordi «det virker ikke» i 50 % av tilfellene betyr «noe i nettverket er feil»: en brannmurregel, en DNS-oppføring, en port som ikke er åpen, et subnett som er for lite. I Azure designer du selv virtuelle nettverk, subnett og sikkerhetsregler. Uten nettverkskunnskap blir det gjetting.

## OSI- og TCP/IP-modellen – kartet over nettverk

**Hva er det?** En modell som deler nettverkskommunikasjon i **lag** (*layers*). Hvert lag har én jobb og bruker laget under seg.

**Hvorfor finnes det?** For å dele et svært komplekst problem i håndterbare biter – og for å gi et felles språk for feilsøking: «Er dette et lag 3-problem (IP) eller et lag 7-problem (HTTP)?»

```text
 OSI-modellen (7 lag)          TCP/IP (4 lag)     Eksempler
 ┌───────────────────────┐     ┌──────────────┐
 │ 7 Applikasjon         │     │              │   HTTP, DNS, SSH, SMTP
 │ 6 Presentasjon        │ ──► │ Applikasjon  │   TLS, JSON, kryptering
 │ 5 Sesjon              │     │              │   sesjoner
 ├───────────────────────┤     ├──────────────┤
 │ 4 Transport           │ ──► │ Transport    │   TCP, UDP, porter
 ├───────────────────────┤     ├──────────────┤
 │ 3 Nettverk            │ ──► │ Internett    │   IP, ruting, ICMP
 ├───────────────────────┤     ├──────────────┤
 │ 2 Datalink            │ ──► │ Nettverks-   │   Ethernet, MAC, svitsj
 │ 1 Fysisk              │     │ tilgang      │   kabel, fiber, Wi-Fi
 └───────────────────────┘     └──────────────┘
```

> **Hverdagsanalogi:** Å sende et brev. Lag 7 er innholdet du skriver. Lag 4 er at du nummererer sidene og ber om kvittering. Lag 3 er adressen på konvolutten. Lag 2 er postbilen som kjører mellom to terminaler. Lag 1 er selve veien.

> **Fra arbeidslivet:** Du vil høre «lag 4-lastbalanserer» (ser bare IP og port – f.eks. Azure Load Balancer) og «lag 7-lastbalanserer» (forstår HTTP, kan rute på URL – f.eks. Azure Application Gateway). Det er denne modellen de refererer til.

## IP-adresser: IPv4 og IPv6

### IPv4

En IPv4-adresse er 32 bit, skrevet som fire tall (oktetter) fra 0 til 255:

```text
   192   .   168   .    1    .   25
 11000000.10101000.00000001.00011001   ← samme adresse i binært (32 bit)
```

Hver oktett er 8 bit, og 8 bit kan uttrykke 2⁸ = 256 verdier (0–255).

En IP-adresse har to deler:

- **Nettverksdelen** – hvilket nettverk (gate) enheten tilhører.
- **Vertsdelen** (*host*) – hvilken enhet (husnummer) på nettverket.

Hvor skillet går, bestemmes av **subnettmasken** eller **CIDR-prefikset** (se under).

### IPv6

IPv6 er 128 bit, skrevet som åtte grupper heksadesimale tall:

```text
2001:0db8:0000:0000:0000:ff00:0042:8329
2001:db8::ff00:42:8329          ← forkortet: ledende nuller og én serie nuller fjernes
```

**Hvorfor?** IPv4 har ca. 4,3 milliarder adresser – for få til alle telefoner, PC-er og IoT-enheter i verden. IPv6 har 2¹²⁸ adresser (≈ 3,4 × 10³⁸). I praksis lever IPv4 og IPv6 side om side (*dual stack*), og de fleste bedriftsnett og skymiljøer bruker fortsatt primært IPv4 internt.

### Private og offentlige adresser

**Offentlige** (*public*) IP-adresser er unike på hele internett og kan nås derfra. **Private** adresser er reservert for interne nettverk (RFC 1918) og rutes aldri på internett:

| Område | CIDR | Antall adresser | Typisk bruk |
|---|---|---|---|
| 10.0.0.0 – 10.255.255.255 | 10.0.0.0/8 | ~16,7 millioner | Bedrifter, Azure VNets |
| 172.16.0.0 – 172.31.255.255 | 172.16.0.0/12 | ~1 million | Bedrifter, Docker-nettverk |
| 192.168.0.0 – 192.168.255.255 | 192.168.0.0/16 | 65 536 | Hjemmenettverk |

Andre spesielle adresser du bør kjenne:

- `127.0.0.1` (*localhost*, *loopback*) – maskinen selv. IPv6: `::1`.
- `0.0.0.0` – «alle adresser på denne maskinen» når en tjeneste lytter; «hvilken som helst» i regler.
- `169.254.x.x` – automatisk adresse når DHCP feilet (et tegn på problemer). I Azure er `169.254.169.254` metadata-tjenesten for VM-er.

> **Hverdagsanalogi:** En offentlig IP er bedriftens gateadresse. Private IP-er er romnumrene inne i bygget. Posten utenfra kjenner bare gateadressen; resepsjonen (NAT-ruteren) vet hvilket rom brevet skal til.

## Subnetting og CIDR

Dette er et tema mange gruer seg for. Det er lettere enn det ser ut.

**Hva er det?** Subnetting er å dele et stort nettverk i mindre nettverk (subnett). **CIDR** (*Classless Inter-Domain Routing*) er skrivemåten `10.0.1.0/24`, der tallet etter skråstreken sier **hvor mange bit som er nettverksdelen**.

**Hvorfor?**

- **Organisering:** webservere i ett subnett, databaser i et annet.
- **Sikkerhet:** du kan sette brannmurregler mellom subnett («bare web-subnettet får snakke med database-subnettet»).
- **Effektivitet:** ikke sløse adresser.

**Hvordan fungerer det?** En IPv4-adresse har 32 bit. Hvis prefikset er `/24`, er 24 bit nettverk og 32 − 24 = **8 bit** igjen til verter. 8 bit gir 2⁸ = **256** adresser.

**Formelen du må kunne:**

```text
  Antall adresser i et subnett = 2^(32 − prefiks)
```

| CIDR | Subnettmaske | Adresser | Typisk bruk |
|---|---|---|---|
| /8 | 255.0.0.0 | 16 777 216 | Svært stort nettverk |
| /16 | 255.255.0.0 | 65 536 | Et helt VNet |
| /20 | 255.255.240.0 | 4 096 | Stort subnett (f.eks. AKS) |
| /22 | 255.255.252.0 | 1 024 | Mellomstort subnett |
| /24 | 255.255.255.0 | 256 | Vanlig subnett |
| /26 | 255.255.255.192 | 64 | Lite subnett |
| /27 | 255.255.255.224 | 32 | Lite subnett (f.eks. gateway) |
| /28 | 255.255.255.240 | 16 | Veldig lite |
| /29 | 255.255.255.248 | 8 | Minste subnett Azure tillater |
| /32 | 255.255.255.255 | 1 | Én enkelt adresse (i regler) |

> **Husk:** Mindre prefikstall = **større** nettverk. `/16` er mye større enn `/24`. Hver gang prefikset øker med 1, halveres antall adresser.

### Eksempel: dele et VNet i subnett

Du får `10.0.0.0/16` (65 536 adresser) og trenger tre subnett:

```text
 VNet 10.0.0.0/16
 ├── snet-web   10.0.1.0/24   →  10.0.1.0  – 10.0.1.255
 ├── snet-app   10.0.2.0/24   →  10.0.2.0  – 10.0.2.255
 └── snet-db    10.0.3.0/24   →  10.0.3.0  – 10.0.3.255
```

### Reserverte adresser

I vanlige nettverk er første adresse **nettverksadressen** og siste er **broadcast**, så et `/24` gir 254 brukbare adresser.

**I Azure** reserveres **5 adresser** i hvert subnett: de fire første og den siste. I `10.0.1.0/24`:

| Adresse | Brukes til |
|---|---|
| 10.0.1.0 | Nettverksadresse |
| 10.0.1.1 | Standard gateway (Azure) |
| 10.0.1.2 og 10.0.1.3 | Azure DNS-funksjoner |
| 10.0.1.255 | Broadcast |

Altså: et `/24` i Azure gir **251** brukbare adresser. Et `/29` (8 adresser) gir bare 3. Dette er et klassisk AZ-104-spørsmål.

### Regneøvelse steg for steg

*Hvor mange adresser er i `10.0.0.0/22`, og hvilket område dekker det?*

1. Vertsbit: 32 − 22 = 10.
2. Adresser: 2¹⁰ = 1 024.
3. 1 024 adresser = 4 × 256, altså fire «/24-blokker».
4. Området: `10.0.0.0` – `10.0.3.255`.

*Overlapper `10.0.2.0/24` med `10.0.0.0/22`?* Ja – `10.0.2.x` ligger innenfor `10.0.0.0`–`10.0.3.255`. Overlappende adresseområder er en vanlig feil når man kobler VNets sammen (*peering*) eller kobler skyen til kontornettet – det fungerer da ikke.

> **Vanlig feil:** Å lage VNets som er for små. Kubernetes (AKS) kan bruke svært mange IP-adresser – én per pod med noen nettverksmodeller. Planlegg romslig fra start; det er vanskelig å endre senere.

> **Fordypning:** Subnettmasken `255.255.255.192` i binært er `11111111.11111111.11111111.11000000` – 26 enere, altså `/26`. Masken og prefikset er to måter å skrive det samme på.

## DNS – internettets telefonkatalog

**Hva er det?** Et distribuert, hierarkisk system som oversetter navn (`www.noroff.no`) til IP-adresser og annen informasjon.

**Hvordan fungerer et oppslag?**

```text
 Klient ──1──► Rekursiv resolver (f.eks. ISP, 1.1.1.1, 8.8.8.8)
                 │ 2. «Hvem har .no?»
                 ├──────────► Rot-server (.)       → «spør .no-serverne»
                 │ 3. «Hvem har noroff.no?»
                 ├──────────► .no-server (TLD)     → «spør noroffs navneservere»
                 │ 4. «Hva er www.noroff.no?»
                 ├──────────► Autoritativ server   → «IP er x.x.x.x»
 Klient ◄──5── svar (og resolveren cacher svaret i TTL sekunder)
```

1. Klienten spør en **rekursiv resolver**.
2. Resolveren spør en **rot-server**, som henviser til serverne for toppnivådomenet (TLD) `.no`.
3. `.no`-serverne henviser til den **autoritative** navneserveren for `noroff.no`.
4. Den autoritative serveren gir svaret.
5. Resolveren lagrer svaret i **cache** i en viss tid (**TTL** – *Time To Live*).

### DNS-posttyper (*record types*)

| Type | Betydning | Eksempel |
|---|---|---|
| A | Navn → IPv4 | `www → 20.50.1.10` |
| AAAA | Navn → IPv6 | `www → 2001:db8::10` |
| CNAME | Navn → annet navn (alias) | `www → minapp.azurewebsites.net` |
| MX | E-postserver for domenet | `@ → mail.example.com` |
| TXT | Fritekst, ofte verifisering | `"v=spf1 ..."` |
| NS | Hvilke navneservere som er autoritative | `ns1-01.azure-dns.com` |
| SOA | Informasjon om sonen | Serienummer, TTL-verdier |
| PTR | IP → navn (omvendt oppslag) | `10.1.50.20 → server.example.com` |
| SRV | Tjeneste og port | Brukes av f.eks. Active Directory |

### Praktisk

```bash
$ nslookup www.example.com          # enkelt oppslag (Windows, macOS, Linux)
$ dig www.example.com               # detaljert (Linux/macOS)
$ dig +short www.example.com A      # bare svaret
$ dig example.com MX                # hvilken e-postserver?
$ dig @1.1.1.1 www.example.com      # spør en bestemt DNS-server
```

> **Vanlig feil:** «Jeg endret DNS, men ingenting skjer!» Svaret er ofte **TTL/cache**. Hvis TTL var 3600 sekunder, kan gamle svar leve i en time. Senk TTL *før* en planlagt flytting.

> **Fra arbeidslivet:** Når du flytter en nettside fra en gammel server til Azure App Service, lager du en CNAME fra `www.firma.no` til `firma.azurewebsites.net`, verifiserer domenet med en TXT-post, og legger på et TLS-sertifikat.

> **Husk:** «It's always DNS» er et ekte ordtak blant driftsfolk. Sjekk DNS tidlig når noe ikke kan nås.

## DHCP

**Hva er det?** DHCP (*Dynamic Host Configuration Protocol*) deler automatisk ut IP-adresse, subnettmaske, standard gateway og DNS-server til enheter som kobler seg til et nettverk.

**Hvordan?** Fire steg, ofte husket som **DORA**:

```text
 Klient                         DHCP-server
   │── Discover (broadcast) ──────►│   «Er det en DHCP-server her?»
   │◄────────────── Offer ─────────│   «Du kan få 192.168.1.50»
   │── Request ───────────────────►│   «Jeg tar den!»
   │◄────────────── Ack ───────────│   «Bekreftet, leid i 24 timer»
```

> **Hverdagsanalogi:** Et hotell. Du kommer til resepsjonen (Discover), får tilbud om rom 214 (Offer), sier ja (Request), og får nøkkelkortet (Ack). Når du sjekker ut, kan rommet gis til en annen. Det er et *lease*.

> **Fra arbeidslivet:** I Azure får VM-er sin private IP via DHCP fra Azure-plattformen. Du kan sette adressen til **statisk** i Azure (på nettverkskortet), men du skal *ikke* endre IP-innstillingene manuelt inne i operativsystemet på en Azure-VM – da mister du kontakten med den.

## TCP og UDP

Begge er protokoller på **transportlaget** (lag 4). De bestemmer *hvordan* data leveres.

### TCP – den pålitelige

**TCP** (*Transmission Control Protocol*) garanterer at alt kommer frem, i riktig rekkefølge, uten feil. Mistede pakker sendes på nytt.

Før data sendes, gjøres et **tre-veis håndtrykk** (*three-way handshake*):

```text
 Klient                    Server
   │──── SYN ─────────────►│   «Vil du snakke?»
   │◄─── SYN-ACK ──────────│   «Ja, vil du?»
   │──── ACK ─────────────►│   «Ja!»  → forbindelsen er åpen
```

### UDP – den raske

**UDP** (*User Datagram Protocol*) sender pakkene og håper det beste. Ingen håndtrykk, ingen garanti, men lav forsinkelse.

| | TCP | UDP |
|---|---|---|
| Pålitelighet | Garantert levering og rekkefølge | Ingen garanti |
| Hastighet | Litt tregere (overhead) | Raskere |
| Forbindelse | Ja (håndtrykk) | Nei |
| Brukes til | Web (HTTP/1.1, HTTP/2), SSH, e-post, databaser | DNS-oppslag, video, VoIP, spill, HTTP/3 (QUIC) |

> **Hverdagsanalogi:** TCP er rekommandert post med kvittering. UDP er å rope gjennom et vindu – raskt, men du vet ikke om noen hørte det.

## Porter

**Hva er det?** En port er et nummer (0–65535) som identifiserer **hvilken tjeneste** på en maskin trafikken skal til. IP-adressen er bygget; porten er døren.

En forbindelse identifiseres av: **protokoll + kilde-IP + kildeport + mål-IP + målport**.

| Port | Protokoll | Tjeneste |
|---|---|---|
| 20/21 | TCP | FTP (filoverføring, ukryptert – unngå) |
| 22 | TCP | SSH (sikker fjerninnlogging) |
| 25 | TCP | SMTP (e-post mellom servere) |
| 53 | UDP/TCP | DNS |
| 80 | TCP | HTTP |
| 123 | UDP | NTP (tidssynkronisering) |
| 443 | TCP (og UDP for HTTP/3) | HTTPS |
| 1433 | TCP | Microsoft SQL Server / Azure SQL |
| 3306 | TCP | MySQL |
| 3389 | TCP | RDP (Windows fjernskrivebord) |
| 5432 | TCP | PostgreSQL |
| 6379 | TCP | Redis |
| 6443 | TCP | Kubernetes API-server |
| 8080 | TCP | Vanlig alternativ HTTP-port for apper |
| 9090 | TCP | Prometheus |

- **Velkjente porter** (*well-known*): 0–1023 (krever ofte root-rettigheter for å lytte på i Linux).
- **Registrerte porter**: 1024–49151.
- **Dynamiske/midlertidige porter** (*ephemeral*): brukes som kildeport av klienter.

```bash
$ ss -tlnp            # Linux: hvilke TCP-porter lytter maskinen på?
State   Recv-Q  Send-Q  Local Address:Port   Peer Address:Port  Process
LISTEN  0       511     0.0.0.0:80           0.0.0.0:*          users:(("nginx",pid=812,fd=6))
LISTEN  0       128     0.0.0.0:22           0.0.0.0:*          users:(("sshd",pid=640,fd=3))
```

`-t` TCP, `-l` lyttende, `-n` vis tall i stedet for navn, `-p` vis prosess.

> **Vanlig feil:** En app som lytter på `127.0.0.1:8080` kan **bare** nås fra maskinen selv. For å nå den utenfra må den lytte på `0.0.0.0:8080` (alle grensesnitt). Dette er en klassiker med Docker-containere og Flask-apper.

> **Kostnad og sikkerhet:** Åpne aldri port 22 (SSH) eller 3389 (RDP) mot hele internett (`0.0.0.0/0`). Automatiserte roboter prøver å logge inn på disse portene hele døgnet. Bruk Azure Bastion, VPN eller begrens til din egen IP-adresse.

## Ruter og svitsj

**Svitsj** (*switch*, lag 2) kobler sammen enheter i **samme** lokale nettverk. Den lærer hvilke **MAC-adresser** (fysiske adresser på nettverkskort) som sitter på hvilken port, og sender trafikken kun dit den skal.

**Ruter** (*router*, lag 3) kobler sammen **forskjellige** nettverk og bestemmer hvilken vei pakker skal gå, basert på IP-adresser og en **rutetabell**.

```text
       Internett
           │
      ┌────┴────┐
      │ RUTER   │  ← kobler hjemmenettet til internett (og gjør NAT)
      └────┬────┘
      ┌────┴────┐
      │ SVITSJ  │  ← kobler enheter på samme nett
      └┬───┬───┬┘
      PC  TV  Skriver     (192.168.1.0/24)
```

**Standard gateway** (*default gateway*) er ruteren en enhet sender trafikk til når målet *ikke* er på det lokale nettet. Hjemme er det typisk `192.168.1.1`.

```bash
$ ip route            # Linux: vis rutetabellen
default via 192.168.1.1 dev eth0
192.168.1.0/24 dev eth0 proto kernel scope link src 192.168.1.50
```

Les: «Alt til 192.168.1.0/24 går direkte ut på eth0. Alt annet (*default*) sendes til ruteren 192.168.1.1.»

> **Fra arbeidslivet:** I Azure finnes ingen fysiske rutere du ser, men det finnes **systemruter** som automatisk ruter mellom subnett i et VNet og ut til internett. Du kan overstyre dem med **User Defined Routes (UDR)** i en **route table** – for eksempel for å tvinge all trafikk gjennom en brannmur.

## Brannmur (*firewall*)

**Hva er det?** En brannmur tillater eller blokkerer nettverkstrafikk basert på regler.

**Hvordan?** Regler ser typisk på: retning (inn/ut), kilde-IP, mål-IP, port, protokoll, og om trafikken er en del av en eksisterende forbindelse (*stateful*).

```text
 Prioritet  Retning  Kilde          Port   Handling
 100        Inn      Internett      443    TILLAT
 110        Inn      84.20.10.5/32  22     TILLAT   (bare kontor-IP)
 4096       Inn      Alle           Alle   AVVIS    (standard: avvis alt annet)
```

Typer:

- **Vertsbasert** – på selve maskinen: `ufw`/`iptables`/`nftables` på Linux, Windows Defender Firewall.
- **Nettverksbasert** – foran nettverket: maskinvarebrannmur, **Azure Network Security Group (NSG)**, **Azure Firewall**.
- **WAF** (*Web Application Firewall*) – lag 7, forstår HTTP og stopper angrep som SQL-injeksjon. Finnes i Azure Application Gateway og Azure Front Door.

> **Husk:** Prinsippet er **«avvis alt, tillat det som trengs»** (*default deny*). Hver åpning skal ha en grunn.

## NAT – Network Address Translation

**Hva er det?** NAT oversetter IP-adresser når trafikk passerer en ruter. Vanligst: mange private adresser deler én offentlig adresse.

```text
 PC 192.168.1.50:51000  ─┐                    ┌─► Server på internett
 PC 192.168.1.51:51001  ─┼─► RUTER (NAT) ─────┤   ser bare 84.20.10.5
 TV 192.168.1.52:51002  ─┘  84.20.10.5        └─
        (privat)            (offentlig)
```

Ruteren husker hvem som sendte hva (i en NAT-tabell), slik at svarene kommer tilbake til riktig enhet.

**Hvorfor?** Det sparer offentlige IPv4-adresser, og interne enheter kan ikke nås direkte utenfra uten videre.

> **Fra arbeidslivet:** I Azure gir **NAT Gateway** VM-er i et subnett felles, stabil utgående IP-adresse. Det er nyttig når en ekstern partner bare vil tillate trafikk fra kjente IP-er. Microsoft har dessuten endret standarden slik at nye VNets/subnett ikke lenger får «skjult» utgående internettilgang automatisk (*default outbound access*); utgående trafikk skal settes opp eksplisitt med NAT Gateway, offentlig IP, lastbalanserer eller brannmur. Sjekk Microsoft Learn («Default outbound access in Azure») for gjeldende status.

**Port forwarding** (*DNAT*) er det motsatte: trafikk til ruterens offentlige IP på en bestemt port sendes videre til en intern maskin.

## VPN

**Hva er det?** Et VPN (*Virtual Private Network*) lager en **kryptert tunnel** over et usikkert nettverk (internett), slik at to steder kan snakke sammen som om de var på samme private nettverk.

To hovedtyper:

- **Site-to-site** – kobler et helt kontornett til et annet nett (f.eks. kontoret til Azure VNet). I Azure: **VPN Gateway**.
- **Point-to-site** (*remote access*) – kobler én enkelt bruker/PC til nettverket.

```text
  Kontor (10.10.0.0/16)                       Azure VNet (10.0.0.0/16)
 ┌──────────────────┐   kryptert tunnel   ┌──────────────────┐
 │ VPN-enhet        │═════════════════════│ VPN Gateway      │
 └──────────────────┘  over internett     └──────────────────┘
```

Legg merke til at adresseområdene **ikke** overlapper. Det må de ikke gjøre.

> **Fordypning:** **Azure ExpressRoute** er en privat, dedikert forbindelse mellom bedriften og Azure som *ikke* går over det offentlige internett – høyere ytelse og forutsigbarhet, men dyrere.

## Lastbalansering (*load balancing*)

**Hva er det?** En lastbalanserer fordeler innkommende trafikk mellom flere servere.

**Hvorfor?**

1. **Skalering:** én server klarer ikke all trafikken.
2. **Høy tilgjengelighet:** dør én server, sendes trafikken til de andre.
3. **Vedlikehold uten nedetid:** ta én server ut, oppdater, sett inn igjen.

```text
                     ┌─────────────┐
   Brukere ────────► │LASTBALANSER │
                     └──┬────┬────┬┘
          helsesjekk ✓  │    │    │  ✗ (svarer ikke → får ikke trafikk)
                   ┌────▼┐ ┌─▼───┐ ┌▼────┐
                   │Web 1│ │Web 2│ │Web 3│
                   └─────┘ └─────┘ └─────┘
```

**Helsesjekker** (*health probes*): lastbalansereren spør jevnlig hver server, f.eks. `GET /health`. Svarer den ikke, slutter den å få trafikk.

**Algoritmer:** *round robin* (på rad), *least connections* (minst belastet), *hash* på kilde-IP (samme bruker til samme server).

| | Lag 4 | Lag 7 |
|---|---|---|
| Ser på | IP og port | HTTP: URL, headers, cookies |
| Kan | Fordele TCP/UDP raskt | Rute `/api` og `/bilder` til ulike servere, TLS-terminering, WAF |
| Azure | Azure Load Balancer | Application Gateway, Front Door |

> **Hverdagsanalogi:** En hovmester i en travel restaurant som fordeler gjestene på servitørene, og som slutter å sende gjester til en servitør som har gått hjem syk.

## Proxy og reverse proxy

**Proxy (forward proxy)** sitter foran **klientene** og sender forespørsler ut på deres vegne. Brukes i bedrifter for å filtrere og logge internettbruk, eller cache innhold.

**Reverse proxy** sitter foran **serverne** og tar imot forespørsler på deres vegne. Klienten vet ikke hvilken server som egentlig svarer.

```text
 FORWARD PROXY                         REVERSE PROXY
 Klient ─┐                                          ┌─► App-server A
 Klient ─┼─► Proxy ─► Internett   Internett ─► Rev. ├─► App-server B
 Klient ─┘                                   proxy  └─► App-server C
 (beskytter/styrer klienter)           (beskytter/styrer servere)
```

En reverse proxy gjør ofte:

- **TLS-terminering** (håndterer HTTPS, så appene slipper),
- lastbalansering,
- caching og komprimering,
- ruting basert på URL (`/api` → backend, `/` → frontend),
- skjuler interne servere.

Eksempler: **nginx**, HAProxy, Traefik, Envoy, Azure Application Gateway, Kubernetes Ingress-kontrollere.

Et enkelt nginx-oppsett som reverse proxy:

```nginx
server {
    listen 80;                         # lytt på port 80
    server_name minapp.example.com;    # for dette domenet

    location / {
        proxy_pass http://127.0.0.1:8000;          # send videre til appen på port 8000
        proxy_set_header Host $host;               # behold opprinnelig vertsnavn
        proxy_set_header X-Real-IP $remote_addr;   # gi appen klientens ekte IP
    }
}
```

## SSL/TLS og sertifikater

**Hva er det?** TLS (*Transport Layer Security*) krypterer trafikk mellom klient og server. SSL er det gamle navnet (alle SSL-versjoner er utdaterte og usikre); folk sier fortsatt «SSL-sertifikat», men det er TLS som brukes. Bruk TLS 1.2 eller 1.3.

TLS gir tre ting:

1. **Konfidensialitet** – ingen kan lese trafikken.
2. **Integritet** – ingen kan endre den uten at det oppdages.
3. **Autentisering** – du vet at du snakker med riktig server (via sertifikatet).

**Sertifikater.** Et sertifikat er et digitalt «pass» for et domene. Det inneholder domenenavnet, en **offentlig nøkkel**, gyldighetsperiode og en signatur fra en **sertifikatutsteder** (*Certificate Authority, CA*) som nettleseren stoler på.

```text
 Nettleseren stoler på  ──►  Rot-CA (innebygd i OS/nettleser)
                                 │ signerer
                             Mellom-CA (intermediate)
                                 │ signerer
                             Sertifikat for www.firma.no
```

**Asymmetrisk kryptering, enkelt forklart:** Serveren har et nøkkelpar – en **offentlig nøkkel** alle kan få, og en **privat nøkkel** som aldri forlater serveren. Noe som er låst med den offentlige nøkkelen kan bare låses opp med den private. I TLS brukes dette til å bli enige om en felles, rask **symmetrisk** nøkkel som så krypterer resten av samtalen.

> **Hverdagsanalogi:** Den offentlige nøkkelen er en åpen postkasse med smal sprekk – alle kan legge brev inn. Bare eieren har nøkkelen (den private) som åpner den.

**Praktisk:**

```bash
# Se sertifikatet til en nettside (utløpsdato, utsteder)
$ openssl s_client -connect www.example.com:443 -servername www.example.com </dev/null 2>/dev/null \
    | openssl x509 -noout -subject -issuer -dates
```

> **Vanlig feil:** **Utløpte sertifikater** er en av de vanligste årsakene til nedetid i hele bransjen. Automatiser fornyelse (f.eks. Let's Encrypt med `certbot`, App Service Managed Certificates, eller Azure Key Vault med automatisk fornyelse) og overvåk utløpsdatoer. Merk at bransjen har vedtatt gradvis kortere maksimal levetid for offentlige sertifikater fremover – automatisering blir derfor obligatorisk i praksis.

## HTTP-statuskoder

Statuskoder er tresifrede tall i HTTP-svar. Første siffer sier hvilken kategori:

| Kategori | Betydning |
|---|---|
| 1xx | Informasjon |
| 2xx | Suksess |
| 3xx | Omdirigering |
| 4xx | Klientfeil – feilen er i forespørselen |
| 5xx | Serverfeil – feilen er på serversiden |

De viktigste:

| Kode | Navn | Hva det betyr i praksis |
|---|---|---|
| 200 | OK | Alt gikk bra |
| 201 | Created | Noe ble opprettet (etter POST) |
| 204 | No Content | Gikk bra, men ingen data tilbake |
| 301 | Moved Permanently | Permanent flyttet (f.eks. http → https) |
| 302 / 307 | Found / Temporary Redirect | Midlertidig omdirigering |
| 304 | Not Modified | Bruk cachet versjon |
| 400 | Bad Request | Forespørselen er feilformatert |
| 401 | Unauthorized | Ikke autentisert – du må logge inn |
| 403 | Forbidden | Autentisert, men ikke lov |
| 404 | Not Found | Finnes ikke |
| 405 | Method Not Allowed | Feil HTTP-metode |
| 409 | Conflict | Konflikt, f.eks. finnes allerede |
| 429 | Too Many Requests | Du blir begrenset (*rate limiting*) |
| 500 | Internal Server Error | Appen krasjet / ukjent feil |
| 502 | Bad Gateway | Proxyen fikk ugyldig svar fra backend (backend nede?) |
| 503 | Service Unavailable | Tjenesten er overbelastet eller i vedlikehold |
| 504 | Gateway Timeout | Proxyen ventet for lenge på backend |

> **Fra arbeidslivet:** Statuskoder er gull ved feilsøking. **502** fra Application Gateway eller nginx betyr nesten alltid at *appen bak* ikke svarer – ikke at proxyen er ødelagt. **401 vs. 403**: 401 = «hvem er du?», 403 = «jeg vet hvem du er, men du får ikke lov».

## SSH – Secure Shell

**Hva er det?** SSH er en kryptert protokoll for å logge inn på og styre en annen maskin over nettverket, typisk Linux-servere. Bruker port 22.

**Passord vs. nøkler.** Passord kan gjettes. **SSH-nøkler** er et nøkkelpar: den private nøkkelen ligger på din PC, den offentlige legges på serveren. Det er mye sikrere, og standard i bransjen.

```bash
# 1. Lag et nøkkelpar (ed25519 er moderne og anbefalt)
$ ssh-keygen -t ed25519 -C "student@noroff"
#    Lagres som ~/.ssh/id_ed25519 (PRIVAT – del aldri!) og ~/.ssh/id_ed25519.pub (offentlig)

# 2. Kopier den offentlige nøkkelen til serveren
$ ssh-copy-id student@203.0.113.10

# 3. Logg inn
$ ssh student@203.0.113.10

# 4. Kopier en fil til serveren
$ scp rapport.txt student@203.0.113.10:/home/student/
```

En `~/.ssh/config`-fil sparer deg for skriving:

```text
Host webserver
    HostName 203.0.113.10
    User student
    IdentityFile ~/.ssh/id_ed25519
```

Nå holder det med `ssh webserver`.

> **Vanlig feil:** Feil rettigheter på nøkkelfilen gir feilmeldingen «UNPROTECTED PRIVATE KEY FILE!». Løsning: `chmod 600 ~/.ssh/id_ed25519`.

> **Husk:** Den **private** nøkkelen deles aldri, sjekkes aldri inn i Git, og sendes aldri på e-post eller chat.

*(IP-adressene `203.0.113.x` i eksemplene er reservert for dokumentasjon og finnes ikke på ekte.)*

## Nettverksfeilsøking – en systematisk metode

Når «nettsiden virker ikke», jobb deg **nedenfra og opp** i lagene, og test én ting om gangen:

```text
 1. Har jeg nettverk?           ip addr / ipconfig      → har jeg IP-adresse?
 2. Når jeg gatewayen?          ping 192.168.1.1
 3. Når jeg internett?          ping 1.1.1.1
 4. Virker DNS?                 nslookup / dig minside.no
 5. Er porten åpen?             nc -zv minside.no 443
 6. Hvilken vei går trafikken?  traceroute / tracert / mtr
 7. Virker TLS?                 openssl s_client -connect minside.no:443
 8. Hva svarer HTTP?            curl -v https://minside.no
 9. Lytter tjenesten?           ss -tlnp (på serveren)
10. Hva sier loggene?           journalctl, /var/log/nginx/error.log
```

### Verktøyene

| Verktøy | Hva det gjør | Eksempel |
|---|---|---|
| `ip addr` / `ipconfig` | Vis IP-adresser | `ip addr show` |
| `ping` | Sjekk om en vert svarer (ICMP) | `ping -c 4 1.1.1.1` |
| `traceroute` / `tracert` | Vis veien pakkene tar | `traceroute vg.no` |
| `mtr` | ping + traceroute kontinuerlig | `mtr vg.no` |
| `nslookup` / `dig` | DNS-oppslag | `dig +short vg.no` |
| `nc` (netcat) | Test om en TCP-port er åpen | `nc -zv vg.no 443` |
| `curl` | HTTP-forespørsler | `curl -v https://vg.no` |
| `ss` / `netstat` | Vis åpne porter og forbindelser | `ss -tlnp` |
| `tcpdump` | Fang nettverkstrafikk | `sudo tcpdump -i eth0 port 53` |
| `openssl s_client` | Test TLS | se over |

> **Vanlig feil:** Å konkludere at serveren er nede fordi `ping` ikke svarer. Mange brannmurer (også Azure-standarder) blokkerer ICMP. Test heller porten med `nc` eller `curl`.

### Eksempel på feilsøking

*Situasjon:* Du har satt opp en webserver på en Azure-VM, men `http://<offentlig-ip>` henger.

1. `curl -v http://<ip>` fra din PC → henger på «Trying ...» → trafikken kommer ikke frem. Mistenk brannmur.
2. Sjekk NSG-reglene i Azure → port 80 er ikke åpnet. Legg til regel → prøv igjen.
3. Nå får du «Connection refused» → trafikken kommer frem, men ingenting lytter.
4. SSH inn, kjør `sudo ss -tlnp` → nginx kjører ikke. `sudo systemctl status nginx` viser feil i konfigurasjonen.
5. `sudo nginx -t` viser linjen med feilen. Fiks, `sudo systemctl restart nginx` → `200 OK`.

> **Husk:** «Henger/timeout» betyr ofte **brannmur** (pakkene droppes). «Connection refused» betyr at maskinen svarte, men **ingen tjeneste lytter** på porten. Den forskjellen sparer deg mye tid.

## Hvordan en DevOps Engineer bruker nettverk i praksis

- Designe Azure VNets og subnett uten overlapp, med plass til vekst.
- Skrive NSG-regler og brannmurregler etter minste-privilegium-prinsippet.
- Sette opp DNS for nye tjenester og TLS-sertifikater med automatisk fornyelse.
- Konfigurere lastbalanserere og helsesjekker.
- Koble skymiljøet sammen med kontornettet (VPN/ExpressRoute) eller andre VNets (*peering*).
- Bruke private endepunkter (*Private Endpoints*) slik at databaser og lagring ikke er eksponert mot internett.
- Feilsøke «hvorfor får ikke tjeneste A kontakt med tjeneste B?» – kanskje den vanligste supportsaken i Kubernetes og Cloud.

## Kapitteloppsummering

- Nettverk beskrives i lag (OSI/TCP-IP); feilsøk nedenfra og opp.
- IPv4 er 32 bit; private områder er 10/8, 172.16/12 og 192.168/16. IPv6 er 128 bit.
- Antall adresser i et subnett = 2^(32 − prefiks). Azure reserverer 5 adresser per subnett.
- DNS oversetter navn til IP; husk TTL og cache. DHCP deler ut adresser automatisk.
- TCP er pålitelig med håndtrykk; UDP er raskt uten garanti. Porter identifiserer tjenester.
- Ruter kobler nettverk; svitsj kobler enheter; brannmur filtrerer; NAT oversetter adresser; VPN lager krypterte tunneler.
- Lastbalanserere fordeler trafikk og bruker helsesjekker; reverse proxy står foran servere.
- TLS gir kryptering, integritet og autentisering med sertifikater. Automatiser fornyelse.
- SSH med nøkler er standard for Linux-servere.

## Øvingsoppgaver

1. Regn ut antall adresser i `/25`, `/23` og `/27`. Hvor mange er brukbare i Azure?
2. Del `172.16.0.0/16` i fire like store subnett. Skriv opp CIDR og område for hvert.
3. Kjør `dig noroff.no MX` og `dig noroff.no NS`. Hva forteller svarene?
4. Kjør `traceroute vg.no` (eller `tracert` på Windows). Hvor mange «hopp» er det?
5. Lag et SSH-nøkkelpar med `ssh-keygen -t ed25519`. Se på innholdet i `.pub`-filen.
6. Bruk `curl -v https://www.noroff.no` og identifiser DNS, TCP, TLS og HTTP i utskriften.
7. Kjør `ss -tlnp` (Linux) eller `netstat -ano` (Windows). Hvilke porter lytter maskinen din på?

## Quiz

1. Hvor mange adresser er det i et `/26`-subnett?
2. Hvilket av disse er en privat adresse: `8.8.8.8`, `10.20.30.40`, `172.32.0.1`?
3. Hva er forskjellen på en A-post og en CNAME-post?
4. Hvorfor bruker DNS ofte UDP?
5. Hvilken port bruker HTTPS? SSH? PostgreSQL?
6. Hva betyr «Connection refused» sammenlignet med «timeout»?
7. Hva er forskjellen på en forward proxy og en reverse proxy?
8. Hva er forskjellen på 401 og 403?
9. Hvorfor bør du ikke åpne port 22 mot `0.0.0.0/0`?
10. To VNets har `10.0.0.0/16` og `10.0.128.0/17`. Kan de kobles sammen med peering?

### Fasit

1. 2^(32−26) = 2⁶ = **64** adresser (59 brukbare i Azure).
2. **`10.20.30.40`**. `172.32.0.1` er utenfor 172.16.0.0/12 (som slutter på 172.31.255.255), så den er offentlig.
3. En **A-post** peker et navn direkte til en IPv4-adresse. En **CNAME** peker et navn til et *annet navn* (alias), som så slås opp videre.
4. Fordi et DNS-oppslag er ett lite spørsmål og ett lite svar – håndtrykket i TCP ville gjort det tregere. (Store svar og soneoverføringer bruker TCP.)
5. HTTPS: **443**. SSH: **22**. PostgreSQL: **5432**.
6. **Refused**: maskinen nås, men ingen tjeneste lytter på porten. **Timeout**: pakkene kommer ikke frem eller blir droppet – ofte brannmur eller ruting.
7. **Forward proxy** står foran klientene og sender forespørsler ut for dem. **Reverse proxy** står foran serverne og tar imot forespørsler for dem.
8. **401**: ikke autentisert (vi vet ikke hvem du er). **403**: autentisert, men mangler tilgang.
9. Fordi roboter konstant prøver å bryte seg inn via SSH. Begrens til kjente IP-er, bruk Bastion/VPN og nøkkelbasert innlogging.
10. **Nei.** `10.0.128.0/17` ligger innenfor `10.0.0.0/16` – adresseområdene overlapper, og overlappende VNets kan ikke peeres.
