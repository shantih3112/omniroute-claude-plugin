# Del 3 – Linux fra nybegynner til profesjonell

**Læringsmål for kapitlet.** Når du er ferdig, skal du kunne:

- forklare hva Linux er og hvorfor nesten hele skyen kjører på det,
- navigere i filsystemet og jobbe med filer fra terminalen,
- administrere brukere, grupper og rettigheter,
- styre prosesser og tjenester med `ps`, `top` og `systemctl`,
- installere programvare med pakkehåndterere,
- skrive enkle Bash-skript, planlegge jobber med cron og lese logger,
- sikre og feilsøke en Linux-server.

## Hva er Linux, og hvorfor bruker DevOps det?

**Hva er det?** Linux er et gratis operativsystem med åpen kildekode. Strengt tatt er «Linux» navnet på **kjernen** (*kernel*), skrevet av Linus Torvalds i 1991. Kjernen pluss verktøy, pakkesystem og programmer utgjør en **distribusjon** (*distro*), som Ubuntu eller Red Hat.

**Hvorfor bruker DevOps Linux?**

- Det store flertallet av servere på internett og i skyen kjører Linux – også mange arbeidslaster i Azure.
- Containere (Docker) og Kubernetes er bygget på Linux-kjernens funksjoner.
- Alt kan styres fra kommandolinjen og automatiseres med skript.
- Gratis, stabilt, sikkert, og enormt godt dokumentert.

> **Hverdagsanalogi:** Windows er som en ferdigmøblert leilighet: komfortabelt, men vanskelig å bygge om. Linux er som en verktøykasse og et lager av byggeklosser: du kan bygge akkurat det du trenger, og du kan automatisere byggingen.

### Distribusjoner

| Distro | Familie | Pakkeverktøy | Typisk bruk |
|---|---|---|---|
| Ubuntu (LTS) | Debian | `apt` | Svært populær i sky og blant utviklere |
| Debian | Debian | `apt` | Stabil, grunnlag for mange container-images |
| Red Hat Enterprise Linux (RHEL) | Red Hat | `dnf` | Store bedrifter, kommersiell support |
| Rocky Linux / AlmaLinux | Red Hat | `dnf` | Gratis RHEL-kompatible alternativer |
| Fedora | Red Hat | `dnf` | Nyeste teknologi |
| Alpine | Egen | `apk` | Svært små container-images |
| Azure Linux | Egen (Microsoft) | `tdnf` | Microsofts distro, brukes bl.a. på AKS-noder |

**LTS** (*Long Term Support*) betyr at versjonen får sikkerhetsoppdateringer i mange år. Ubuntu kommer med en LTS hvert annet år (f.eks. 22.04, 24.04, 26.04). Bruk LTS på servere.

> **Husk:** Lær én familie godt (Ubuntu/Debian er et godt valg), men vit at Red Hat-familien bruker `dnf` i stedet for `apt`. Resten er stort sett likt.

## Slik får du en Linux-maskin å øve på

Du har flere gratis muligheter:

1. **WSL** (*Windows Subsystem for Linux*) på Windows: åpne PowerShell som administrator og kjør `wsl --install`. Du får Ubuntu i et vindu.
2. **Virtuell maskin** med VirtualBox eller UTM (Mac) og Ubuntu Server.
3. **macOS-terminalen** – macOS er Unix og har mange av de samme kommandoene (men ikke alt, f.eks. ikke `systemctl`).
4. **Azure Cloud Shell** – en Linux-terminal i nettleseren, direkte i Azure Portal.
5. **En liten Azure-VM** (se kapittel 7; husk kostnader og opprydding).

## Terminal og shell

**Hva er det?**

- **Terminalen** er vinduet du skriver i.
- **Shellet** er programmet som tolker det du skriver og kjører kommandoer. Det vanligste er **Bash**; macOS bruker **zsh** som standard. Begge fungerer nesten likt for det vi gjør.

**Hvorfor kommandolinje når det finnes grafiske grensesnitt?** Servere har som regel ikke grafisk grensesnitt. Kommandoer kan dessuten **skriptes, gjentas, dokumenteres og automatiseres**. Ti klikk i et GUI kan bli én linje i et skript som kjøres på 500 servere.

### Anatomien til en kommando

```text
  ls   -l -a    /var/log
  │    │        │
  │    │        └── argument: hva kommandoen jobber med
  │    └─────────── flagg/opsjoner: endrer oppførselen (-la kan kombineres)
  └──────────────── kommandoen
```

### Prompten

```text
student@webserver:~$
│       │         │ └── $ = vanlig bruker   (# = root)
│       │         └──── ~ = du er i hjemmemappen din
│       └────────────── maskinens navn
└────────────────────── brukernavnet ditt
```

### Overlevelsestips

| Tast/kommando | Gjør |
|---|---|
| `Tab` | Fullfører fil- og kommandonavn. Bruk den hele tiden! |
| `↑` / `↓` | Bla i tidligere kommandoer |
| `Ctrl + C` | Avbryt kommandoen som kjører |
| `Ctrl + L` eller `clear` | Tøm skjermen |
| `Ctrl + R` | Søk i kommandohistorikken |
| `history` | Vis historikken |
| `man ls` | Manualen for `ls` (avslutt med `q`) |
| `ls --help` | Kort hjelp |

## Filsystemet

**Hva er det?** Linux organiserer alt i ett tre som starter i **roten** `/`. Det finnes ingen `C:`-disk; andre disker «monteres» inn som mapper.

```text
/                     ← roten
├── bin, sbin         ← grunnleggende programmer (ofte lenker til /usr/bin)
├── boot              ← kjernen og oppstartsfiler
├── dev               ← enheter (disker: /dev/sda, /dev/nvme0n1)
├── etc               ← KONFIGURASJONSFILER (nginx, ssh, brukere)
├── home              ← brukernes hjemmemapper (/home/student)
├── opt               ← tredjeparts programvare
├── proc, sys         ← virtuelle filer med info om kjernen og prosesser
├── root              ← hjemmemappen til root-brukeren
├── tmp               ← midlertidige filer (slettes ofte ved omstart)
├── usr               ← programmer og biblioteker (/usr/bin, /usr/lib)
└── var               ← data som endres: LOGGER (/var/log), nettsider (/var/www)
```

> **Husk:** Tre mapper du kommer til å bruke hele tiden: **`/etc`** (konfigurasjon), **`/var/log`** (logger) og **`/home`** (brukerfiler).

> **«Alt er en fil»:** I Linux er nesten alt representert som filer – også disker (`/dev/sda`), prosesser (`/proc/1234`) og systeminformasjon (`/proc/cpuinfo`). Derfor kan de samme verktøyene (`cat`, `grep`) brukes på nesten alt.

### Absolutte og relative stier

- **Absolutt sti** starter med `/`: `/home/student/prosjekt/app.py` – virker uansett hvor du står.
- **Relativ sti** starter der du er: `prosjekt/app.py`.
- `.` = mappen du står i. `..` = mappen over. `~` = hjemmemappen din.

## Grunnleggende kommandoer

Her er kommandoene du *må* kunne. For hver: hva du skriver, hva det betyr, hva du får, og når du bruker den.

### `pwd` – hvor er jeg?

```bash
$ pwd
/home/student
```

*Print Working Directory.* Bruk når du er usikker på hvor du er.

### `ls` – hva finnes her?

```bash
$ ls
dokumenter  prosjekt  notater.txt

$ ls -la
total 24
drwxr-xr-x 4 student student 4096 Oct 30 10:12 .
drwxr-xr-x 3 root    root    4096 Oct 28 09:00 ..
-rw------- 1 student student  220 Oct 28 09:00 .bash_history
drwxr-xr-x 2 student student 4096 Oct 30 10:10 dokumenter
-rw-r--r-- 1 student student  512 Oct 30 10:12 notater.txt
drwxr-xr-x 3 student student 4096 Oct 30 10:11 prosjekt
```

`-l` = lang liste med detaljer, `-a` = vis også skjulte filer (de som starter med punktum), `-h` = lesbare størrelser (KB, MB). Vi forklarer kolonnene under «Rettigheter».

### `cd` – bytt mappe

```bash
$ cd prosjekt          # gå inn i mappen prosjekt
$ cd ..                # gå én mappe opp
$ cd /var/log          # gå til en absolutt sti
$ cd ~                 # gå hjem (bare `cd` gjør det samme)
$ cd -                 # gå tilbake dit du var sist
```

### `mkdir` – lag mapper

```bash
$ mkdir backup                    # lag én mappe
$ mkdir -p prosjekt/src/utils     # lag hele stien; -p = lag foreldremapper ved behov
```

### `touch`, `cat`, `less`, `head`, `tail` – lag og les filer

```bash
$ touch tom-fil.txt               # lag en tom fil (eller oppdater tidsstempelet)
$ cat notater.txt                 # skriv ut hele filen
$ less /var/log/syslog            # bla i store filer (q = avslutt, / = søk)
$ head -n 20 fil.txt              # de 20 første linjene
$ tail -n 50 /var/log/syslog      # de 50 siste linjene
$ tail -f /var/log/nginx/access.log   # FØLG filen live – helt sentralt ved feilsøking
```

### `cp`, `mv`, `rm` – kopier, flytt, slett

```bash
$ cp notater.txt notater-backup.txt       # kopier fil
$ cp -r prosjekt prosjekt-kopi            # kopier mappe (-r = rekursivt)
$ mv notater.txt dokumenter/              # flytt fil
$ mv gammelt-navn.txt nytt-navn.txt       # gi nytt navn (= flytt til nytt navn)
$ rm tom-fil.txt                          # slett fil
$ rm -r gammel-mappe                      # slett mappe med innhold
$ rmdir tom-mappe                         # slett tom mappe
```

> **Vanlig feil:** `rm` har **ingen papirkurv**. `rm -rf` sletter alt uten å spørre. Kjør aldri `rm -rf` med variabler du ikke har sjekket, og aldri som root uten å dobbeltsjekke stien. Bruk `rm -ri` (spør for hver fil) når du er usikker.

### Redigere filer: `nano` og `vim`

```bash
$ nano /etc/hosts      # enkel editor. Ctrl+O = lagre, Ctrl+X = avslutt
$ vim fil.txt          # kraftig editor. i = skriv, Esc, :wq = lagre og avslutt, :q! = avslutt uten å lagre
```

Lær deg nok `vim` til å overleve – den finnes på nesten alle servere.

### `grep` – søk i tekst

```bash
$ grep "error" /var/log/syslog            # linjer som inneholder "error"
$ grep -i "error" app.log                 # -i = ignorer store/små bokstaver
$ grep -r "DATABASE_URL" ./prosjekt       # -r = søk rekursivt i mapper
$ grep -n "listen" /etc/nginx/nginx.conf  # -n = vis linjenummer
$ grep -v "DEBUG" app.log                 # -v = linjer som IKKE matcher
$ grep -c "404" access.log                # -c = tell treff
```

### `find` – finn filer

```bash
$ find /var/log -name "*.log"                 # alle .log-filer under /var/log
$ find . -type f -size +100M                  # filer større enn 100 MB her
$ find /tmp -type f -mtime +7                 # filer endret for mer enn 7 dager siden
$ find . -name "*.tmp" -delete                # finn og slett (vær forsiktig!)
```

### Pipes og omdirigering – superkraften

**Pipe** (`|`) sender resultatet fra én kommando inn i neste. Små verktøy kombineres til kraftige.

```bash
# Hvilke 5 IP-adresser har gjort flest forespørsler mot webserveren?
$ cat /var/log/nginx/access.log | awk '{print $1}' | sort | uniq -c | sort -rn | head -5
   1532 203.0.113.44
    821 198.51.100.7
    ...
```

Les det steg for steg: hent loggen → plukk ut første kolonne (IP) → sorter → tell like linjer → sorter etter antall, største først → vis topp 5.

**Omdirigering:**

```bash
$ echo "hei" > fil.txt        # > skriver til fil (OVERSKRIVER)
$ echo "igjen" >> fil.txt     # >> legger til på slutten
$ kommando 2> feil.log        # 2> sender feilmeldinger (stderr) til fil
$ kommando > alt.log 2>&1     # både vanlig utskrift og feil til samme fil
$ kommando > /dev/null        # kast utskriften
```

> **Fordypning – stdin, stdout, stderr:** Hvert program har tre «strømmer»: inn (0, stdin), ut (1, stdout) og feil (2, stderr). `2>&1` betyr «send strøm 2 dit strøm 1 går».

### Nyttige småverktøy

```bash
$ wc -l fil.txt          # tell linjer
$ sort fil.txt           # sorter linjer
$ uniq                   # fjern like linjer som står etter hverandre
$ cut -d',' -f2 data.csv # plukk ut kolonne 2 fra en CSV
$ df -h                  # ledig diskplass per filsystem
$ du -sh /var/log        # hvor mye plass bruker en mappe?
$ free -h                # RAM-bruk
$ uname -a               # kjerneversjon
$ cat /etc/os-release    # hvilken distro og versjon
$ which python3          # hvor ligger programmet?
$ tar -czf backup.tar.gz mappe/   # pakk og komprimer
$ tar -xzf backup.tar.gz          # pakk ut
```

## Brukere og grupper

**Hva er det?** Linux er et flerbrukersystem. Hver **bruker** har et brukernavn, en ID (UID) og en hjemmemappe. **Grupper** samler brukere slik at de kan få felles rettigheter.

Spesielle brukere:

- **root** (UID 0) – superbrukeren som kan alt. Farlig å bruke direkte.
- **Systembrukere** – for tjenester, f.eks. `www-data` (nginx/Apache), `postgres`. De kan ikke logge inn, og begrenser skaden hvis tjenesten blir hacket.

```bash
$ whoami                              # hvem er jeg?
$ id                                  # min UID, GID og grupper
uid=1000(student) gid=1000(student) groups=1000(student),27(sudo)

$ sudo adduser ola                    # lag ny bruker (Debian/Ubuntu, interaktivt)
$ sudo useradd -m -s /bin/bash kari   # lag bruker (alle distroer); -m = lag hjemmemappe
$ sudo passwd kari                    # sett passord
$ sudo groupadd utviklere             # lag gruppe
$ sudo usermod -aG utviklere kari     # legg kari i gruppen (-aG = append til Group)
$ sudo usermod -aG docker student     # vanlig: gi deg tilgang til docker
$ groups kari                         # hvilke grupper er kari med i?
$ sudo deluser ola                    # slett bruker
```

Informasjonen lagres i `/etc/passwd` (brukere), `/etc/group` (grupper) og `/etc/shadow` (krypterte passord, bare lesbar for root).

### `sudo` – låne superkrefter

`sudo` (*superuser do*) kjører én kommando med root-rettigheter, hvis brukeren din har lov (er i gruppen `sudo` på Ubuntu eller `wheel` på Red Hat).

```bash
$ apt update
E: Could not open lock file ... - open (13: Permission denied)
$ sudo apt update        # nå virker det
```

> **Vanlig feil:** Å logge inn som root og gjøre alt der. Bruk en vanlig bruker og `sudo` for enkeltkommandoer. Det gir sporbarhet (logges) og hindrer mange uhell.

> **Vanlig feil:** `usermod -G` *uten* `-a` erstatter alle gruppene til brukeren – inkludert `sudo`-gruppen. Da har du låst deg selv ute. Bruk alltid `-aG`.

## Rettigheter (*permissions*)

**Hva er det?** Hver fil og mappe har en **eier** (*user*), en **gruppe** (*group*), og rettigheter for tre kategorier: eieren, gruppen og **alle andre** (*others*).

```text
 -rwxr-xr--  1  student  utviklere  2048  Oct 30 10:12  deploy.sh
 │└┬┘└┬┘└┬┘     │        │
 │ │  │  │      eier     gruppe
 │ │  │  └── andre (others):   r-- = kan lese
 │ │  └───── gruppen:          r-x = kan lese og kjøre
 │ └──────── eieren (user):    rwx = kan lese, skrive og kjøre
 └────────── filtype: - = fil, d = mappe, l = lenke
```

| Bokstav | På en fil | På en mappe |
|---|---|---|
| `r` (read) | Lese innholdet | Liste innholdet (`ls`) |
| `w` (write) | Endre innholdet | Lage/slette filer i mappen |
| `x` (execute) | Kjøre som program | Gå inn i mappen (`cd`) |

### Tallnotasjon

Hver rettighet har en verdi: **r = 4, w = 2, x = 1**. Legg sammen for hver kategori:

```text
 rwx = 4+2+1 = 7      r-x = 4+0+1 = 5      r-- = 4      rw- = 6
 rwxr-xr-- = 754      rw-r--r-- = 644      rw------- = 600
```

| Tall | Betyr | Typisk bruk |
|---|---|---|
| 755 | Alle kan lese og kjøre, bare eier kan endre | Skript, programmer, mapper |
| 644 | Alle kan lese, bare eier kan skrive | Vanlige filer, konfig |
| 600 | Bare eier kan lese og skrive | Private SSH-nøkler, hemmeligheter |
| 700 | Bare eier har tilgang | `~/.ssh`-mappen |
| 777 | Alle kan alt | **Nesten aldri riktig!** |

### `chmod` og `chown`

```bash
$ chmod +x deploy.sh                 # gjør skriptet kjørbart
$ chmod 600 ~/.ssh/id_ed25519        # privat nøkkel: bare eier
$ chmod -R 755 /var/www/minside      # -R = rekursivt
$ chmod u+w,g-w,o-rwx fil.txt        # symbolsk: legg til/fjern for u(ser), g(roup), o(thers)

$ sudo chown www-data:www-data /var/www/minside -R   # endre eier og gruppe
$ sudo chown student fil.txt                          # bare eier
```

> **Vanlig feil:** «Det virker ikke, så jeg kjørte `chmod 777`.» Da kan hvem som helst endre filen – et alvorlig sikkerhetshull. Finn ut *hvilken* bruker som trenger tilgang, og gi akkurat den tilgangen.

> **Fra arbeidslivet:** En typisk feil etter deploy: nginx viser `403 Forbidden` fordi filene i `/var/www` eies av brukeren som kopierte dem, og `www-data` ikke kan lese dem. Løsning: riktig eier/gruppe og `644`/`755`.

## Prosesser

**Hva er det?** En prosess er et program som kjører. Hver prosess har en **PID** (*process ID*), en eier, og bruker CPU og minne.

```bash
$ ps aux                       # alle prosesser
USER   PID %CPU %MEM    VSZ   RSS TTY STAT START   TIME COMMAND
root     1  0.0  0.3 167640 12800 ?   Ss   09:00   0:02 /sbin/init
www-data 812 0.1 0.5 55280  9800 ?   S    09:01   0:05 nginx: worker process
...
$ ps aux | grep nginx          # finn en bestemt prosess
$ pgrep -a python              # finn prosesser ved navn

$ top                          # live oversikt (q = avslutt, P = sorter CPU, M = sorter minne)
$ htop                         # penere versjon (må ofte installeres: sudo apt install htop)
```

**Avslutte prosesser:**

```bash
$ kill 1234          # be prosess 1234 avslutte pent (signal SIGTERM)
$ kill -9 1234       # tving den (SIGKILL) – bare når den ikke reagerer
$ pkill -f app.py    # avslutt basert på navn/kommandolinje
```

> **Hverdagsanalogi:** `kill` er å be en gjest pent om å gå. `kill -9` er å la vekteren bære dem ut. Prøv det høflige først, slik at programmet får lagret og ryddet.

**Forgrunn og bakgrunn:**

```bash
$ python3 app.py &       # & = kjør i bakgrunnen
$ jobs                   # vis bakgrunnsjobber
$ fg %1                  # hent jobb 1 til forgrunnen
$ nohup ./langjobb.sh &  # fortsett selv om du logger ut
```

For ekte tjenester bruker vi ikke `&`, men **systemd** (neste seksjon).

### Lastgjennomsnitt (*load average*)

`uptime` og `top` viser tre tall, f.eks. `load average: 0.50, 1.20, 0.80`. Det er gjennomsnittlig antall prosesser som kjører eller venter, siste 1, 5 og 15 minutter. Tommelfingerregel: sammenlign med antall CPU-kjerner (`nproc`). Konstant høyere load enn kjerner betyr at maskinen er overbelastet.

## Tjenester (*services*) med systemd

**Hva er det?** En tjeneste er et program som kjører i bakgrunnen hele tiden (en *daemon*): webserver, database, SSH-server. På nesten alle moderne distroer styres de av **systemd**, med kommandoen `systemctl`.

```bash
$ sudo systemctl status nginx      # kjører den? siste loggmeldinger
● nginx.service - A high performance web server and a reverse proxy server
     Loaded: loaded (/lib/systemd/system/nginx.service; enabled)
     Active: active (running) since Thu 2026-10-30 09:01:12 UTC; 2h ago
   Main PID: 811 (nginx)

$ sudo systemctl start nginx       # start
$ sudo systemctl stop nginx        # stopp
$ sudo systemctl restart nginx     # stopp og start
$ sudo systemctl reload nginx      # les konfigurasjonen på nytt uten å stoppe
$ sudo systemctl enable nginx      # start automatisk ved oppstart
$ sudo systemctl disable nginx     # ikke start ved oppstart
$ sudo systemctl enable --now nginx   # enable + start i ett
$ systemctl list-units --type=service --state=running   # alle kjørende tjenester
```

> **Vanlig feil:** `start` uten `enable`. Tjenesten kjører – til serveren startes på nytt. Da er den borte, og ingen skjønner hvorfor.

### Lag din egen tjeneste

Har du en Python-app som skal kjøre som tjeneste, lager du en *unit-fil*:

```ini
# /etc/systemd/system/minapp.service
[Unit]
Description=Min Python-app
After=network.target                 # start etter at nettverket er oppe

[Service]
User=minapp                          # kjør som egen bruker, ikke root
WorkingDirectory=/opt/minapp
ExecStart=/usr/bin/python3 /opt/minapp/app.py
Restart=on-failure                   # start på nytt hvis den krasjer
Environment=PORT=8000

[Install]
WantedBy=multi-user.target           # starte ved vanlig oppstart
```

```bash
$ sudo systemctl daemon-reload         # systemd leser inn nye/endrede unit-filer
$ sudo systemctl enable --now minapp
$ journalctl -u minapp -f              # følg loggen til tjenesten
```

## Pakkehåndtering (*package management*)

**Hva er det?** En pakkehåndterer installerer, oppdaterer og fjerner programvare fra trygge **repositories** (pakkebrønner), og håndterer **avhengigheter** automatisk.

> **Hverdagsanalogi:** Som App Store for serveren. Du sier «installer nginx», og pakkehåndtereren henter nginx og alt nginx trenger, fra en kilde den stoler på.

**Debian/Ubuntu (`apt`):**

```bash
$ sudo apt update                 # oppdater LISTEN over tilgjengelige pakker
$ sudo apt upgrade                # oppgrader installerte pakker
$ sudo apt install nginx          # installer
$ sudo apt install -y git curl    # -y = svar ja automatisk (nyttig i skript)
$ sudo apt remove nginx           # fjern
$ apt search postgresql           # søk
$ apt list --installed            # hva er installert?
```

**Red Hat-familien (`dnf`):**

```bash
$ sudo dnf check-update
$ sudo dnf install nginx
$ sudo dnf upgrade
$ sudo dnf remove nginx
```

> **Vanlig feil:** `apt install` feiler med «Unable to locate package». Ofte har du glemt `sudo apt update` først.

Andre pakkeverktøy du møter: `pip` (Python-biblioteker), `npm` (JavaScript), `snap`, og `apk` (Alpine, i containere).

## SSH i praksis

Grunnleggende SSH ble forklart i kapittel 2. Her er det du trenger for serverdrift:

```bash
$ ssh -i ~/.ssh/id_ed25519 azureuser@20.100.1.2    # bruk en bestemt nøkkel
$ ssh -p 2222 bruker@server                         # annen port
$ ssh bruker@server 'df -h'                         # kjør én kommando eksternt
$ scp -r ./site bruker@server:/tmp/                 # kopier mappe
$ rsync -avz ./site/ bruker@server:/var/www/site/   # synkroniser effektivt (bare endringer)
$ ssh -L 8080:localhost:80 bruker@server            # tunnel: din port 8080 → serverens port 80
```

**Herde SSH-serveren** i `/etc/ssh/sshd_config` (eller en fil i `/etc/ssh/sshd_config.d/`):

```text
PermitRootLogin no              # ingen direkte root-innlogging
PasswordAuthentication no       # bare nøkler
PubkeyAuthentication yes
```

```bash
$ sudo sshd -t                  # test konfigurasjonen før restart!
$ sudo systemctl restart ssh    # tjenesten heter "ssh" på Ubuntu, "sshd" på Red Hat
```

> **Vanlig feil:** Å slå av passordinnlogging *før* du har testet at nøkkelinnlogging virker. Hold alltid én SSH-økt åpen mens du tester i en ny – ellers kan du låse deg ute.

## Miljøvariabler (*environment variables*)

**Hva er det?** Navngitte verdier som prosesser kan lese. Brukes til konfigurasjon: hvilken database å koble til, hvilket miljø (dev/prod) appen kjører i, osv.

```bash
$ echo $HOME                 # /home/student
$ echo $PATH                 # mappene shellet leter etter programmer i
$ env                        # vis alle miljøvariabler
$ export APP_ENV=production  # sett variabel for dette shellet og prosesser det starter
$ echo $APP_ENV
production
$ unset APP_ENV              # fjern den
```

For å gjøre en variabel permanent for brukeren din, legg `export`-linjen i `~/.bashrc` og kjør `source ~/.bashrc`.

**`PATH`** er spesielt viktig: når du skriver `python3`, leter shellet gjennom mappene i `PATH` (separert med `:`) etter et program med det navnet. «command not found» betyr ofte at programmet ikke ligger i `PATH`.

> **Fra arbeidslivet:** Prinsippet «konfigurasjon i miljøet, ikke i koden» (fra *The Twelve-Factor App*) brukes overalt: samme container-image kjører i test og produksjon, bare med forskjellige miljøvariabler. App Service, Kubernetes og GitHub Actions bruker alle miljøvariabler.

> **Vanlig feil:** Å skrive passord direkte i `.bashrc` eller i skript som sjekkes inn i Git. Hemmeligheter hører hjemme i et hemmelighetshvelv (Azure Key Vault, kapittel 7 og 13).

## Bash-scripting

**Hva er det?** Et Bash-skript er en tekstfil med kommandoer som kjøres i rekkefølge. Alt du kan skrive i terminalen, kan du legge i et skript.

**Hvorfor?** Gjenta oppgaver feilfritt, dokumentere fremgangsmåter, og automatisere.

### Ditt første skript

```bash
#!/usr/bin/env bash
# hilsen.sh – et første skript
# Linje 1 («shebang») forteller hvilket program som skal kjøre skriptet.

navn="Student"                       # variabel: INGEN mellomrom rundt =
echo "Hei, $navn!"                   # $navn henter verdien
echo "I dag er det $(date +%A)"      # $( ) kjører en kommando og setter inn resultatet
```

```bash
$ chmod +x hilsen.sh
$ ./hilsen.sh
Hei, Student!
I dag er det torsdag
```

### Argumenter, betingelser og løkker

```bash
#!/usr/bin/env bash
set -euo pipefail
# set -e: stopp ved første feil
# set -u: feil hvis du bruker en variabel som ikke finnes
# set -o pipefail: en feil midt i en pipe regnes som feil

# $1 er første argument. ${1:-} gir tom streng hvis det mangler (pga. set -u).
if [[ -z "${1:-}" ]]; then
    echo "Bruk: $0 <mappe>" >&2       # >&2 = skriv til stderr
    exit 1                           # avslutt med feilkode
fi

mappe="$1"

if [[ -d "$mappe" ]]; then           # -d = finnes mappen?
    echo "Mappen $mappe finnes."
else
    echo "Lager $mappe ..."
    mkdir -p "$mappe"
fi

# for-løkke over filer
for fil in "$mappe"/*.log; do
    [[ -e "$fil" ]] || continue      # hopp over hvis ingen treff
    linjer=$(wc -l < "$fil")
    echo "$fil har $linjer linjer"
done
```

Nyttige tester i `[[ ]]`:

| Test | Sann hvis |
|---|---|
| `-f fil` | fil finnes og er en vanlig fil |
| `-d mappe` | mappe finnes |
| `-z "$var"` | variabelen er tom |
| `-n "$var"` | variabelen er ikke tom |
| `"$a" == "$b"` | strengene er like |
| `$a -eq $b`, `-lt`, `-gt` | tall er lik / mindre / større |

**Returkoder (*exit codes*).** Hver kommando returnerer et tall: **0 = suksess**, alt annet = feil. Du ser det med `echo $?`. CI/CD-pipelines bruker dette: et steg som returnerer noe annet enn 0, stopper pipelinen.

### Funksjoner

```bash
logg() {
    # $* = alle argumentene
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

logg "Starter backup"
```

### Et nyttig skript: backup med rotasjon

```bash
#!/usr/bin/env bash
# backup.sh – lager komprimert backup av en mappe og sletter gamle backuper
set -euo pipefail

KILDE="/var/www/minside"          # hva skal tas backup av
MAL="/var/backups/minside"        # hvor backupene lagres
BEHOLD_DAGER=7                    # hvor lenge vi beholder backuper

mkdir -p "$MAL"
fil="$MAL/minside-$(date +%Y%m%d-%H%M%S).tar.gz"

tar -czf "$fil" -C "$(dirname "$KILDE")" "$(basename "$KILDE")"
echo "Backup laget: $fil ($(du -h "$fil" | cut -f1))"

# slett backuper eldre enn BEHOLD_DAGER
find "$MAL" -name "minside-*.tar.gz" -mtime +"$BEHOLD_DAGER" -print -delete
```

> **Vanlig feil:** Å glemme anførselstegn rundt variabler. `rm -rf $MAPPE/` med en tom `$MAPPE` blir `rm -rf /`. Bruk alltid `"$variabel"` og `set -u`. Verktøyet **ShellCheck** (`sudo apt install shellcheck`) finner slike feil automatisk – bruk det.

## Cron – planlagte jobber

**Hva er det?** Cron kjører kommandoer automatisk på faste tidspunkter.

```bash
$ crontab -e      # rediger dine cron-jobber
$ crontab -l      # vis dem
```

Formatet er fem tidsfelt etterfulgt av kommandoen:

```text
 ┌──────── minutt (0–59)
 │ ┌────── time (0–23)
 │ │ ┌──── dag i måneden (1–31)
 │ │ │ ┌── måned (1–12)
 │ │ │ │ ┌ ukedag (0–7, 0 og 7 = søndag)
 │ │ │ │ │
 30 2 * * * /opt/scripts/backup.sh >> /var/log/backup.log 2>&1
```

| Uttrykk | Betyr |
|---|---|
| `30 2 * * *` | Hver dag kl. 02:30 |
| `*/15 * * * *` | Hvert 15. minutt |
| `0 9 * * 1-5` | Kl. 09:00 mandag–fredag |
| `0 0 1 * *` | Midnatt den 1. hver måned |
| `@reboot` | Ved oppstart |

> **Vanlig feil:** Skriptet virker når du kjører det selv, men ikke i cron. Årsak: cron har en minimal `PATH` og et annet miljø. Bruk **fulle stier** (`/usr/bin/python3`), og send utskrift til en loggfil slik at du ser feilene. Husk også at serverens tidssone kan være UTC.

> **Fra arbeidslivet:** Den samme cron-syntaksen brukes i GitHub Actions (`on: schedule`), Kubernetes CronJobs og Azure Functions (med et ekstra sekundfelt). Lær den én gang, bruk den overalt.

**Systemd timers** er et moderne alternativ til cron, med bedre logging. Du vil se begge deler.

## Logger

**Hvor finner jeg loggene?**

| Plassering | Innhold |
|---|---|
| `journalctl` | systemd-journalen: logger fra alle tjenester |
| `/var/log/syslog` (Ubuntu) eller `/var/log/messages` (Red Hat) | Generelle systemmeldinger |
| `/var/log/auth.log` (Ubuntu) eller `/var/log/secure` (Red Hat) | Innlogginger, sudo |
| `/var/log/nginx/access.log` og `error.log` | Webserveren |
| `/var/log/apt/` | Pakkeinstallasjoner |
| `dmesg` | Meldinger fra kjernen (maskinvare, OOM-killer) |

```bash
$ journalctl -u nginx                     # logger for én tjeneste
$ journalctl -u nginx -f                  # følg live
$ journalctl -u nginx --since "1 hour ago"
$ journalctl -p err -b                    # bare feil siden siste oppstart
$ sudo tail -f /var/log/auth.log          # se innloggingsforsøk live
$ sudo grep "Failed password" /var/log/auth.log | wc -l   # mislykkede innlogginger
$ sudo dmesg -T | grep -i "out of memory"
```

**Loggrotasjon.** Logger vokser. `logrotate` roterer, komprimerer og sletter gamle logger automatisk (konfig i `/etc/logrotate.d/`). Fulle disker på grunn av logger er en klassisk årsak til nedetid.

## Systemovervåking

```bash
$ uptime                 # oppetid og load average
$ top / htop             # CPU, minne og prosesser live
$ free -h                # minne
$ df -h                  # diskplass per filsystem
$ df -i                  # inoder (kan gå tomt selv om det er plass!)
$ du -sh /var/* | sort -h   # hvilke mapper er størst?
$ iostat -x 2            # diskaktivitet (pakken sysstat)
$ vmstat 2               # CPU, minne, swap hvert 2. sekund
$ ss -tunap              # nettverksforbindelser
```

Manuell overvåking er greit for feilsøking. I produksjon samles slike metrikker automatisk av verktøy som Azure Monitor, Prometheus og Grafana (kapittel 13).

## Linux-sikkerhet – grunnregler

1. **Oppdater jevnlig:** `sudo apt update && sudo apt upgrade`. Vurder `unattended-upgrades` for automatiske sikkerhetsoppdateringer.
2. **Ingen root-innlogging og ingen passord over SSH** – bare nøkler.
3. **Brannmur:** på Ubuntu er `ufw` enkelt:

    ```bash
    $ sudo ufw allow OpenSSH        # IKKE glem denne før du slår på!
    $ sudo ufw allow 80/tcp
    $ sudo ufw allow 443/tcp
    $ sudo ufw enable
    $ sudo ufw status verbose
    ```

4. **Minste privilegium:** tjenester kjører som egne brukere, ikke root. Bare de som trenger det, får `sudo`.
5. **Fail2ban:** blokkerer IP-er som prøver å gjette passord.
6. **Fjern det du ikke bruker:** færre pakker og åpne porter = mindre angrepsflate.
7. **Overvåk logger:** `auth.log` forteller hvem som prøver å komme inn.
8. **SELinux/AppArmor:** ekstra sikkerhetslag som begrenser hva programmer får gjøre. Ikke slå dem av for å «få ting til å virke».

## Feilsøking på Linux – metode

```text
 1. Hva er symptomet?       «Nettsiden gir 502»
 2. Kjører tjenesten?       systemctl status <tjeneste>
 3. Hva sier loggene?       journalctl -u <tjeneste> -n 100 / tail /var/log/...
 4. Ressurser?              df -h · free -h · top
 5. Nettverk/porter?        ss -tlnp · curl localhost:<port>
 6. Rettigheter?            ls -l · id <bruker>
 7. Hva er endret sist?     deploy? oppdatering? konfig? (history, git log)
 8. Endre ÉN ting, test, dokumenter.
```

**Eksempel – «disken er full»:**

```bash
$ df -h
/dev/root        30G   30G     0 100% /
$ sudo du -xh / --max-depth=1 2>/dev/null | sort -h | tail -5
...
 18G  /var
$ sudo du -xh /var --max-depth=2 | sort -h | tail -3
 17G  /var/log/minapp
$ ls -lh /var/log/minapp
-rw-r--r-- 1 minapp minapp 17G Oct 30 11:00 debug.log
```

Årsak: appen logger på debug-nivå uten rotasjon. Løsning: senk loggnivået, sett opp `logrotate`, og legg inn diskvarsel i overvåkingen.

> **Vanlig feil:** Å slette en stor loggfil som et program fortsatt skriver til. Plassen frigjøres ikke før programmet lukker filen. Tøm den heller: `sudo truncate -s 0 debug.log`.

## Kapitteloppsummering

- Linux er kjernen; distroer (Ubuntu, RHEL, Debian, Alpine) bygger komplette systemer rundt den.
- Filsystemet starter i `/`. `/etc` = konfig, `/var/log` = logger, `/home` = brukere.
- Kjernekommandoer: `pwd ls cd mkdir cp mv rm cat less tail grep find` + pipes og omdirigering.
- Rettigheter: eier/gruppe/andre × r/w/x. 644 for filer, 755 for skript/mapper, 600 for hemmeligheter.
- Tjenester styres med `systemctl`; logger leses med `journalctl` og i `/var/log`.
- Programvare installeres med `apt` eller `dnf`.
- Bash-skript automatiserer; bruk `set -euo pipefail`, anførselstegn og ShellCheck.
- Cron planlegger jobber; bruk fulle stier og logg utskriften.
- Sikkerhet: oppdater, SSH-nøkler, brannmur, minste privilegium.

## Øvingsoppgaver

1. Lag mappestrukturen `~/lab/{logs,scripts,data}` med én kommando (tips: `mkdir -p` og klammeparenteser).
2. Lag en bruker `testbruker`, en gruppe `team`, legg brukeren i gruppen, og bekreft med `id testbruker`.
3. Lag en fil som bare eier kan lese og skrive. Bekreft med `ls -l`.
4. Installer nginx, start og enable den, og bekreft med `curl localhost`.
5. Skriv et skript `diskvarsel.sh` som skriver en advarsel hvis diskbruken på `/` er over 80 %. (Tips: `df --output=pcent / | tail -1 | tr -dc '0-9'`.)
6. Legg skriptet i cron slik at det kjører hvert 10. minutt og logger til `~/lab/logs/disk.log`.
7. Finn de 10 største filene under `/var` med `find` eller `du`.

## Quiz

1. Hva er forskjellen på Linux-kjernen og en distribusjon?
2. Hvor ligger konfigurasjonsfiler, og hvor ligger logger?
3. Hva betyr `chmod 640 fil.txt`?
4. Hva er forskjellen på `>` og `>>`?
5. Hva er forskjellen på `systemctl start` og `systemctl enable`?
6. Hvorfor bør du bruke `sudo` i stedet for å logge inn som root?
7. Hva gjør `set -euo pipefail` i et Bash-skript?
8. Hva betyr cron-uttrykket `0 */6 * * *`?
9. Hva betyr returkode 0?
10. Et program sier «Permission denied» når det skal lese `/etc/minapp/config.yaml`. Hva sjekker du?

### Fasit

1. **Kjernen** er kjernen i OS-et som styrer maskinvaren. En **distribusjon** er kjernen pluss verktøy, pakkesystem og programmer, satt sammen til et komplett operativsystem.
2. Konfigurasjon i **`/etc`**, logger i **`/var/log`** (og i systemd-journalen via `journalctl`).
3. Eier: les+skriv (6), gruppe: les (4), andre: ingenting (0).
4. `>` **overskriver** filen; `>>` **legger til** på slutten.
5. `start` starter tjenesten **nå**. `enable` gjør at den starter **automatisk ved oppstart**.
6. Det gir sporbarhet (hvem gjorde hva), begrenser root-makten til enkeltkommandoer, og reduserer risikoen for katastrofale uhell.
7. Stopp ved feil (`-e`), feil ved udefinerte variabler (`-u`), og at feil midt i en pipe teller (`pipefail`).
8. På minutt 0 hver sjette time: 00:00, 06:00, 12:00 og 18:00.
9. Suksess. Alt annet enn 0 er en feil.
10. Sjekk hvilken bruker programmet kjører som (`ps aux`, unit-filen), og filens eier og rettigheter (`ls -l`). Sjekk også rettighetene på mappen `/etc/minapp` (krever `x` for å gå inn). Gi riktig gruppe/eier – ikke `chmod 777`.
