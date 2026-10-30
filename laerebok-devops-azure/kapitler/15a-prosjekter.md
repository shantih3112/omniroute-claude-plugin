# Del 15 – Virkelige prosjekter

Prosjektene er der kunnskapen blir til **ferdigheter** – og der du bygger **porteføljen** arbeidsgivere vil se. De har økende vanskelighetsgrad og bygger på hverandre.

| # | Prosjekt | Nivå | Kapitler | Tid | Kostnad |
|---|---|---|---|---|---|
| 1 | Sett opp og herd en Linux-server | ★☆☆☆☆ | 2, 3 | 4–6 t | Gratis (lokal VM/WSL) |
| 2 | Python-automatisering: Azure-kostnadsjeger | ★★☆☆☆ | 4, 7.1 | 4–6 t | Gratis |
| 3 | Azure-VM med kode: CLI-skript + cloud-init | ★★☆☆☆ | 7.2 | 3–4 t | Øre–kroner |
| 4 | Profesjonelt GitHub-repo og portefølje | ★★☆☆☆ | 5 | 3–4 t | Gratis |
| 5 | Containeriser en app med Docker | ★★★☆☆ | 9 | 4–6 t | Gratis |
| 6 | Publiser en nettside på Azure med CI/CD | ★★★☆☆ | 5, 7, 12 | 3–5 t | Gratis (Free-plan) |
| 7 | CI/CD-pipeline til Azure App Service | ★★★☆☆ | 12 | 6–8 t | Gratis–lav |
| 8 | Azure-infrastruktur med Terraform og pipeline | ★★★★☆ | 11, 12 | 8–12 t | Lav |
| 9 | Deploy en app på Kubernetes med Helm | ★★★★☆ | 10 | 8–12 t | Gratis lokalt / moderat i AKS |
| 10 | Komplett Cloud/DevOps-plattform | ★★★★★ | Alle | 25–40 t | Lav–moderat |
| 11 | MLOps: modell-API med CI/CD og overvåking | ★★★★☆ | 14 | 10–15 t | Lav |
| 12 | Observability og hendelsesøvelse (game day) | ★★★★☆ | 8, 13 | 8–10 t | Gratis lokalt |

**Generelle regler for alle sky-prosjekter:**

1. Én ressursgruppe per prosjekt, med tags `prosjekt`, `eier`, `utløper`.
2. Budsjettvarsel på abonnementet (kapittel 7.1).
3. **Opprydding samme dag** – hvert prosjekt har en oppryddingsseksjon.
4. Alt i Git; ingen hemmeligheter i repoet.
5. Skriv README underveis, ikke etterpå.

**Mal for README i hvert prosjekt:**

```markdown
# <Prosjektnavn>
Kort beskrivelse (2–3 setninger): hva, hvorfor.

## Arkitektur
(diagram – bilde eller tekstdiagram)

## Teknologier
Azure (...), Terraform, Docker, GitHub Actions ...

## Slik kjører du det
Steg for steg.

## Hva jeg lærte
3–5 punkter – også hva som gikk galt og hvordan jeg løste det.

## Videre arbeid
Hva ville jeg gjort med mer tid?
```

> **Husk:** Arbeidsgivere leser **«Hva jeg lærte»** og ser etter hvordan du feilsøkte. Et prosjekt med ærlig beskrivelse av problemer du løste, er mer imponerende enn et som later som alt gikk knirkefritt.

## Prosjekt 1 – Sett opp og herd en Linux-server

**Læringsmål:** Installere og sikre en Linux-server, administrere brukere og tjenester, sette opp en webserver, brannmur, automatiske oppdateringer og backup med cron.

**Forutsetninger:** Kapittel 2 og 3.

**Arkitektur:**

```text
 Din PC ──SSH (nøkkel, port 22)──► Ubuntu Server 24.04 LTS (VM i VirtualBox/UTM eller WSL)
                                   ├── bruker «admin» (sudo), ingen root-innlogging
                                   ├── ufw: tillat 22, 80
                                   ├── nginx → /var/www/prosjekt1
                                   ├── fail2ban
                                   ├── unattended-upgrades
                                   └── cron: backup.sh kl 02:30 → /var/backups
```

**Verktøy:** VirtualBox eller UTM (eller WSL), Ubuntu Server 24.04 LTS ISO, terminal med SSH.

**Tid:** 4–6 timer. **Kostnad:** Gratis.

**Steg for steg:**

1. **Installer Ubuntu Server** i en VM (2 vCPU, 2 GB RAM, 20 GB disk). Velg «Install OpenSSH server» under installasjonen. Sett nettverket til *Bridged* (eller bruk port forwarding 2222→22 med NAT).
2. **Oppdater systemet:**

    ```bash
    sudo apt update && sudo apt upgrade -y
    ```

3. **Lag en administrasjonsbruker og SSH-nøkkel** (fra din PC):

    ```bash
    # på serveren
    sudo adduser admin
    sudo usermod -aG sudo admin
    # på din PC
    ssh-keygen -t ed25519 -C "prosjekt1"
    ssh-copy-id admin@<server-ip>
    ssh admin@<server-ip>          # test at nøkkelinnlogging virker!
    ```

4. **Herd SSH** – lag `/etc/ssh/sshd_config.d/99-herding.conf`:

    ```text
    PermitRootLogin no
    PasswordAuthentication no
    KbdInteractiveAuthentication no
    ```

    ```bash
    sudo sshd -t && sudo systemctl restart ssh
    ```

    Hold den gamle SSH-økten åpen og test i et nytt vindu.

5. **Brannmur:**

    ```bash
    sudo ufw allow OpenSSH
    sudo ufw allow 80/tcp
    sudo ufw enable
    sudo ufw status verbose
    ```

6. **Fail2ban og automatiske sikkerhetsoppdateringer:**

    ```bash
    sudo apt install -y fail2ban unattended-upgrades
    sudo systemctl enable --now fail2ban
    sudo dpkg-reconfigure -plow unattended-upgrades    # svar «Yes»
    sudo fail2ban-client status sshd
    ```

7. **Webserver:**

    ```bash
    sudo apt install -y nginx
    sudo mkdir -p /var/www/prosjekt1
    echo "<h1>Prosjekt 1 – $(hostname)</h1>" | sudo tee /var/www/prosjekt1/index.html
    sudo chown -R www-data:www-data /var/www/prosjekt1
    ```

    `/etc/nginx/sites-available/prosjekt1`:

    ```nginx
    server {
        listen 80 default_server;
        root /var/www/prosjekt1;
        index index.html;
        access_log /var/log/nginx/prosjekt1.access.log;
    }
    ```

    ```bash
    sudo ln -s /etc/nginx/sites-available/prosjekt1 /etc/nginx/sites-enabled/
    sudo rm /etc/nginx/sites-enabled/default
    sudo nginx -t && sudo systemctl reload nginx
    curl http://localhost
    ```

8. **Backup-skript med cron** – bruk `backup.sh` fra kapittel 3 (med `KILDE=/var/www/prosjekt1`), legg det i `/usr/local/bin/backup.sh`, `sudo chmod 755`, og legg inn i roots crontab (`sudo crontab -e`):

    ```text
    30 2 * * * /usr/local/bin/backup.sh >> /var/log/backup.log 2>&1
    ```

9. **Helsesjekkskript** `/usr/local/bin/helse.sh` som skriver disk, minne, load og status for nginx/ssh/fail2ban til en logg – kjøres hvert 15. minutt.
10. **Dokumenter** alt i en README, inkludert kommandoene, i et Git-repo.

**Forventet resultat:** En server du bare kan nå med SSH-nøkkel, som serverer en nettside, blokkerer brute-force-forsøk, oppdaterer seg selv, og tar daglig backup.

**Vanlige feil og feilsøking:**

| Problem | Løsning |
|---|---|
| Låst ute etter SSH-herding | Logg inn via VM-konsollen, rett konfigurasjonen. (Derfor: test i nytt vindu før du lukker det gamle.) |
| `ufw enable` kuttet SSH | Du glemte `ufw allow OpenSSH`. Bruk konsollen. |
| nginx gir 403 | Feil eier/rettigheter på `/var/www/prosjekt1` |
| Cron-jobben kjører ikke | Bruk fulle stier, sjekk `/var/log/backup.log` og `grep CRON /var/log/syslog` |

**Opprydding:** Ta et snapshot av VM-en (nyttig senere), eller slett den. Ingen sky-kostnader.

**Videreutvikling:** Automatiser hele oppsettet med en Ansible-playbook (kapittel 11) – kjør den mot en ny, tom VM og se at resultatet blir identisk.

**På GitHub og CV:** Repo `linux-server-hardening` med skript, konfigurasjonsfiler og README. *«Installerte og herdet Ubuntu Server: nøkkelbasert SSH, ufw, fail2ban, automatiske sikkerhetsoppdateringer, nginx og automatisert backup med cron og Bash.»*

## Prosjekt 2 – Python-automatisering: Azure-kostnadsjeger

**Læringsmål:** Skrive et profesjonelt Python-verktøy som bruker Azure SDK, argumenter, logging, feilhåndtering og tester.

**Forutsetninger:** Kapittel 4 og 7.1. Azure-abonnement og `az login`.

**Arkitektur:**

```text
 kostnadsjeger.py ──DefaultAzureCredential (az login / managed identity)──► Azure Resource Manager
   │  1. list alle ressursgrupper
   │  2. sjekk tags: eier, utløper
   │  3. rapport: mangler tag / utløpt
   │  4. (valgfritt, med --slett) slett utløpte grupper etter bekreftelse
   └─► rapport.json + loggutskrift + returkode (0 = ok, 1 = funn)
```

**Verktøy:** Python 3.10+, `azure-identity`, `azure-mgmt-resource`, `pytest`.

**Tid:** 4–6 timer. **Kostnad:** Gratis (leser bare metadata; sletting fjerner kostnader).

**Steg for steg:**

1. Lag prosjektet:

    ```bash
    mkdir kostnadsjeger && cd kostnadsjeger
    python3 -m venv .venv && source .venv/bin/activate
    pip install azure-identity azure-mgmt-resource pytest
    pip freeze > requirements.txt
    ```

2. Lag noen testgrupper:

    ```bash
    az group create -n rg-test-ok   -l norwayeast --tags eier=student utløper=2099-12-31
    az group create -n rg-test-gml  -l norwayeast --tags eier=student utløper=2020-01-01
    az group create -n rg-test-utag -l norwayeast
    ```

3. Skriv `kostnadsjeger.py`:

    ```python
    #!/usr/bin/env python3
    """Finn ressursgrupper som mangler eier-tag eller har utløpt."""
    import argparse
    import json
    import logging
    import os
    import sys
    from datetime import date

    from azure.identity import DefaultAzureCredential
    from azure.mgmt.resource import ResourceManagementClient

    log = logging.getLogger("kostnadsjeger")


    def vurder(navn: str, tags: dict | None, idag: date) -> list[str]:
        """Returner en liste med problemer for én ressursgruppe (tom liste = ok)."""
        tags = tags or {}
        problemer = []
        if "eier" not in tags:
            problemer.append("mangler tag 'eier'")
        utl = tags.get("utløper")
        if utl is None:
            problemer.append("mangler tag 'utløper'")
        else:
            try:
                if date.fromisoformat(utl) < idag:
                    problemer.append(f"utløpt {utl}")
            except ValueError:
                problemer.append(f"ugyldig dato '{utl}'")
        return problemer


    def main() -> int:
        p = argparse.ArgumentParser(description=__doc__)
        p.add_argument("--subscription", default=os.environ.get("AZURE_SUBSCRIPTION_ID"))
        p.add_argument("--out", default="rapport.json")
        p.add_argument("--slett", action="store_true", help="Slett UTLØPTE grupper (spør først)")
        p.add_argument("--ignorer", nargs="*", default=["NetworkWatcherRG"],
                       help="Grupper som aldri skal vurderes")
        args = p.parse_args()

        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
        if not args.subscription:
            log.error("Mangler --subscription eller AZURE_SUBSCRIPTION_ID")
            return 2

        klient = ResourceManagementClient(DefaultAzureCredential(), args.subscription)
        idag = date.today()
        funn = []
        for rg in klient.resource_groups.list():
            if rg.name in args.ignorer or rg.name.startswith("MC_"):   # AKS-administrerte grupper
                continue
            problemer = vurder(rg.name, rg.tags, idag)
            if problemer:
                log.warning("%s: %s", rg.name, "; ".join(problemer))
                funn.append({"gruppe": rg.name, "problemer": problemer})
            else:
                log.info("%s: ok", rg.name)

        with open(args.out, "w", encoding="utf-8") as f:
            json.dump({"dato": idag.isoformat(), "funn": funn}, f, indent=2, ensure_ascii=False)

        if args.slett:
            for f_ in funn:
                if any(pr.startswith("utløpt") for pr in f_["problemer"]):
                    svar = input(f"Slette {f_['gruppe']}? Skriv navnet for å bekrefte: ")
                    if svar == f_["gruppe"]:
                        klient.resource_groups.begin_delete(f_["gruppe"])
                        log.info("Sletting startet: %s", f_["gruppe"])
        return 1 if funn else 0


    if __name__ == "__main__":
        sys.exit(main())
    ```

4. Skriv tester for logikken (`test_kostnadsjeger.py`) – uten å snakke med Azure:

    ```python
    from datetime import date
    from kostnadsjeger import vurder

    IDAG = date(2026, 10, 30)

    def test_ok():
        assert vurder("rg", {"eier": "kari", "utløper": "2027-01-01"}, IDAG) == []

    def test_mangler_alt():
        assert len(vurder("rg", None, IDAG)) == 2

    def test_utløpt():
        assert "utløpt 2020-01-01" in vurder("rg", {"eier": "x", "utløper": "2020-01-01"}, IDAG)

    def test_ugyldig_dato():
        assert any("ugyldig" in p for p in vurder("rg", {"eier": "x", "utløper": "snart"}, IDAG))
    ```

    ```bash
    pytest -q
    export AZURE_SUBSCRIPTION_ID=$(az account show --query id -o tsv)
    python kostnadsjeger.py
    ```

5. Legg til en GitHub Actions-workflow som kjører `pytest` og `ruff` på hver push.
6. **Bonus:** Kjør skriptet automatisk hver morgen som en Azure Function (timer trigger) med managed identity og *Reader*-rolle, eller som en planlagt GitHub Actions-workflow med OIDC.

**Forventet resultat:**

```text
INFO rg-test-ok: ok
WARNING rg-test-gml: utløpt 2020-01-01
WARNING rg-test-utag: mangler tag 'eier'; mangler tag 'utløper'
```

**Vanlige feil:**

| Problem | Løsning |
|---|---|
| `DefaultAzureCredential failed to retrieve a token` | Kjør `az login`; sjekk at riktig tenant/abonnement er valgt |
| `AuthorizationFailed` | Identiteten trenger minst *Reader* på abonnementet |
| Testene snakker med Azure | Hold logikk (`vurder`) adskilt fra I/O – da kan den testes isolert |

**Opprydding:** `az group delete -n rg-test-ok --yes`, samme for de to andre.

**På GitHub og CV:** *«Utviklet et Python-verktøy som bruker Azure SDK og managed identity til å finne ressurser uten eier- og utløpstagger, med tester, logging og CI – for å redusere unødvendige skykostnader.»*

## Prosjekt 3 – Azure-VM med kode: CLI-skript og cloud-init

**Læringsmål:** Opprette en komplett, sikker VM-løsning i Azure **utelukkende med kode**: VNet, subnett, NSG, VM med cloud-init, auto-shutdown, og overvåking – og rydde opp med én kommando.

**Forutsetninger:** Kapittel 2, 3 og 7.2.

**Arkitektur:**

```text
 rg-prosjekt3 (norwayeast)
 └── vnet-p3 10.30.0.0/16
      └── snet-web 10.30.1.0/24 ── nsg-web: 80 fra Internet, 22 KUN fra din IP
           └── vm-p3 (Ubuntu 24.04, B1s/B2s) ── cloud-init: nginx + side
                ├── offentlig IP (Standard)
                ├── auto-shutdown 19:00 UTC
                └── CPU-varsel → action group (e-post)
```

**Verktøy:** Azure CLI (lokalt eller Cloud Shell), Bash.

**Tid:** 3–4 timer. **Kostnad:** En liten B-serie-VM i noen timer koster lite (sjekk Pricing Calculator); kan være dekket av gratiskontoens VM-timer. Disk og offentlig IP koster så lenge de finnes – **slett etterpå**.

**Steg for steg:**

1. Lag `cloud-init.yaml`:

    ```yaml
    #cloud-config
    package_update: true
    package_upgrade: true
    packages: [nginx, unattended-upgrades]
    write_files:
      - path: /var/www/html/index.html
        content: |
          <h1>Prosjekt 3</h1><p>Laget med Azure CLI og cloud-init.</p>
    runcmd:
      - systemctl enable --now nginx
    ```

2. Lag `deploy.sh`:

    ```bash
    #!/usr/bin/env bash
    set -euo pipefail

    RG=rg-prosjekt3
    LOC=norwayeast
    VM=vm-p3
    MYIP=$(curl -s https://api.ipify.org)
    EPOST="${1:?Bruk: ./deploy.sh <e-post-for-varsler>}"

    az group create -n $RG -l $LOC --tags prosjekt=p3 eier=student utløper=$(date -d '+7 days' +%F) -o none

    az network vnet create -g $RG -n vnet-p3 --address-prefix 10.30.0.0/16 \
      --subnet-name snet-web --subnet-prefixes 10.30.1.0/24 -o none

    az network nsg create -g $RG -n nsg-web -o none
    az network nsg rule create -g $RG --nsg-name nsg-web -n allow-http --priority 100 \
      --access Allow --protocol Tcp --direction Inbound \
      --source-address-prefixes Internet --destination-port-ranges 80 -o none
    az network nsg rule create -g $RG --nsg-name nsg-web -n allow-ssh-me --priority 110 \
      --access Allow --protocol Tcp --direction Inbound \
      --source-address-prefixes "$MYIP/32" --destination-port-ranges 22 -o none
    az network vnet subnet update -g $RG --vnet-name vnet-p3 -n snet-web --network-security-group nsg-web -o none

    az vm create -g $RG -n $VM --image Ubuntu2404 --size Standard_B1s \
      --vnet-name vnet-p3 --subnet snet-web --nsg "" \
      --public-ip-sku Standard --admin-username azureuser --generate-ssh-keys \
      --custom-data cloud-init.yaml -o none

    az vm auto-shutdown -g $RG -n $VM --time 1900 -o none

    az monitor action-group create -g $RG -n ag-p3 --short-name agp3 --action email meg "$EPOST" -o none
    az monitor metrics alert create -g $RG -n cpu-hoy-p3 \
      --scopes "$(az vm show -g $RG -n $VM --query id -o tsv)" \
      --condition "avg Percentage CPU > 80" --window-size 5m --evaluation-frequency 1m \
      --action ag-p3 -o none

    IP=$(az vm show -d -g $RG -n $VM --query publicIps -o tsv)
    echo "Ferdig! http://$IP   (ssh azureuser@$IP)"
    ```

3. Kjør: `chmod +x deploy.sh && ./deploy.sh deg@example.com`. Vent 1–3 minutter på at cloud-init blir ferdig, og åpne URL-en.
4. Verifiser sikkerheten: test SSH fra mobilnettet (annen IP) – skal **ikke** virke. Sjekk *Network Watcher → IP flow verify*.
5. Test varselet: `ssh azureuser@<ip> "sudo apt-get install -y stress-ng && stress-ng --cpu 1 --timeout 600"`.
6. Lag `destroy.sh` med `az group delete -n rg-prosjekt3 --yes --no-wait`.

**Forventet resultat:** En nettside på en VM laget helt fra kode, med SSH bare fra din IP, auto-shutdown og e-postvarsel ved høy CPU.

**Vanlige feil:**

| Problem | Løsning |
|---|---|
| Siden svarer ikke rett etter opprettelse | cloud-init kjører fortsatt; sjekk `sudo cloud-init status --wait` og `/var/log/cloud-init-output.log` |
| `apt` får ikke kontakt med internett | Utgående tilgang – se merknaden om *default outbound access* i kapittel 7.2. VM-en har offentlig IP her, så det skal virke |
| `SkuNotAvailable` / kvotefeil | Velg annen størrelse (`Standard_B2s`, `Standard_B2ats_v2`) eller region |
| `date -d` virker ikke på macOS | Bruk `gdate` (coreutils) eller skriv datoen manuelt |

**Opprydding:** `./destroy.sh`. Sjekk i portalen at ressursgruppen er borte.

**På GitHub og CV:** *«Automatiserte opprettelse av en sikker Linux-VM i Azure med Azure CLI og cloud-init: segmentert nettverk med NSG (SSH kun fra godkjent IP), automatisk avslåing og metrikkvarsler med Azure Monitor.»*

## Prosjekt 4 – Profesjonelt GitHub-repo og portefølje

**Læringsmål:** Sette opp GitHub som en profesjonell utvikler: profil-README, porteføljerepo, branch rulesets, PR-maler, issues, Dependabot og CI.

**Forutsetninger:** Kapittel 5.

**Arkitektur:**

```text
 github.com/<deg>
 ├── <deg>/<deg>            ← profil-README (vises på profilsiden din)
 └── devops-portefolje      ← samler alle prosjektene
      ├── README.md (oversikt + lenker + badges)
      ├── .github/
      │    ├── workflows/ci.yml          (lint av Markdown/YAML/shell)
      │    ├── pull_request_template.md
      │    ├── ISSUE_TEMPLATE/bug.md
      │    └── dependabot.yml
      ├── CODEOWNERS
      └── prosjekter/ (eller lenker til egne repoer per prosjekt)
```

**Tid:** 3–4 timer. **Kostnad:** Gratis.

**Steg for steg:**

1. **Profil-README:** Lag et repo med *nøyaktig samme navn som brukernavnet ditt*. README-en vises på profilen. Skriv kort: hvem du er, hva du lærer, teknologier, og lenker til 3–4 beste prosjekter. Hold det ryddig – ingen overdrevne animasjoner.
2. **Porteføljerepo:** `devops-portefolje` med README som har en tabell over prosjektene (navn, beskrivelse, teknologier, status, lenke).
3. **PR-mal** `.github/pull_request_template.md`:

    ```markdown
    ## Hva
    ## Hvorfor
    ## Hvordan testet
    - [ ] CI er grønn
    - [ ] README oppdatert ved behov
    ```

4. **CI** `.github/workflows/ci.yml` som kjører `markdownlint`, `yamllint` og `shellcheck`.
5. **Dependabot** `.github/dependabot.yml`:

    ```yaml
    version: 2
    updates:
      - package-ecosystem: "github-actions"
        directory: "/"
        schedule:
          interval: "weekly"
    ```

6. **Ruleset** på `main`: krev PR, krev grønn CI, blokker force push.
7. **Sikkerhet:** Slå på *secret scanning* og *push protection* (Settings → Code security).
8. **Arbeid som et team:** Lag 3 issues, en Project-tavle (Kanban), og løs issuene via brancher og PR-er med `Closes #n`.
9. **Lisens:** Legg til en LICENSE (f.eks. MIT) så andre vet hva de kan gjøre med koden.

**Forventet resultat:** En profil som ser profesjonell ut, og et repo som viser at du kan moderne Git-arbeidsflyt.

**Vanlige feil:** Profil-README vises ikke → repoet må hete nøyaktig det samme som brukernavnet og være *public*. Ruleset hindrer deg i å merge → statussjekkens navn må matche jobbnavnet i workflowen.

**Opprydding:** Ingen.

**På CV:** Lenke til GitHub-profilen øverst på CV-en, og til 2–3 utvalgte repoer.

## Prosjekt 5 – Containeriser en app med Docker

**Læringsmål:** Containerisere en webapp med database, optimalisere imaget, skanne det og publisere det automatisk.

**Forutsetninger:** Kapittel 9.

**Arkitektur:** Se prosjektet i kapittel 9 (Flask + PostgreSQL med Compose, Trivy-skanning, publisering til ghcr.io med GitHub Actions).

**Tid:** 4–6 timer. **Kostnad:** Gratis.

**Steg for steg:** Følg «Prosjekt: bygg, kjør og publiser en applikasjon» i kapittel 9, og gjør i tillegg:

1. **Multi-stage Dockerfile** – mål størrelsen før og etter med `docker images`, og dokumenter det i README.
2. **`HEALTHCHECK`** i Dockerfile og `depends_on: condition: service_healthy` i Compose.
3. **Lint Dockerfile** med hadolint: `docker run --rm -i hadolint/hadolint < Dockerfile`.
4. **Integrasjonstest i CI:** start Compose i workflowen, kall `/` to ganger, og sjekk at telleren øker:

    ```yaml
          - run: docker compose up -d --build --wait
            env:
              DB_PASSWORD: ci-passord
          - run: |
              curl -sf localhost:8000/ && curl -sf localhost:8000/ | grep -q "2 besøk"
          - if: always()
            run: docker compose logs && docker compose down -v
    ```

5. **Tagging:** både commit-SHA og, ved Git-tag `v*`, semantisk versjon.

**Forventet resultat:** En app som starter med én kommando, et lite og skannet image, og automatisk publisering.

**Vanlige feil:** Se feilsøkingstabellen i kapittel 9 (port, `0.0.0.0`, nettverk, arkitektur).

**Opprydding:** `docker compose down -v`, `docker system prune`.

**På CV:** Se kapittel 9.

## Prosjekt 6 – Publiser en nettside på Azure med CI/CD

**Læringsmål:** Publisere en statisk nettside (f.eks. din egen CV/portefølje) på **Azure Static Web Apps** med automatisk deploy fra GitHub, forhåndsvisningsmiljøer for pull requests, og eventuelt eget domene.

**Forutsetninger:** Kapittel 5 og 7.

**Arkitektur:**

```text
 GitHub repo (index.html, style.css)
     │ push / PR
     ▼
 GitHub Actions (workflow generert av Azure)
     │ deploy
     ▼
 Azure Static Web Apps (Free) ──► global distribusjon, HTTPS automatisk
     ├── produksjon: https://<navn>.azurestaticapps.net   (fra main)
     └── PR-miljø:   https://<navn>-<pr>.<region>.azurestaticapps.net (slettes når PR lukkes)
```

**Verktøy:** GitHub, Azure CLI eller portalen, HTML/CSS (eller en statisk side-generator).

**Tid:** 3–5 timer. **Kostnad:** **Free**-planen er gratis (med begrensninger på størrelse og funksjoner – sjekk gjeldende vilkår). Eget domene kjøpes hos en registrar.

**Steg for steg:**

1. Lag repoet `cv-nettside` med `index.html` (din CV/portefølje), `style.css` og `404.html`.
2. Opprett Static Web App koblet til repoet. Enklest i portalen: *Static Web Apps → + Create* → Plan *Free* → Source *GitHub* → velg repo og branch `main` → Build preset *Custom*, App location `/`, Output location tom. Eller med CLI:

    ```bash
    az group create -n rg-prosjekt6 -l westeurope
    az staticwebapp create -n swa-cv-<unik> -g rg-prosjekt6 -l westeurope \
      --source https://github.com/<deg>/cv-nettside --branch main \
      --app-location "/" --output-location "" --login-with-github
    ```

    (Static Web Apps er tilgjengelig i et utvalg regioner – innholdet distribueres globalt uansett.)
3. Azure legger automatisk inn en workflow i `.github/workflows/` og en deploy-token som GitHub Secret. Se jobben kjøre under *Actions*.
4. Åpne URL-en (`az staticwebapp show -n swa-cv-<unik> --query defaultHostname -o tsv`).
5. Lag en branch, endre noe, åpne en PR – legg merke til at det lages et **forhåndsvisningsmiljø** med egen URL i PR-kommentaren.
6. Legg til `staticwebapp.config.json` for sikkerhetsheadere:

    ```json
    {
      "globalHeaders": {
        "Content-Security-Policy": "default-src 'self'",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "strict-origin-when-cross-origin"
      },
      "responseOverrides": { "404": { "rewrite": "/404.html" } }
    }
    ```

7. **Valgfritt – eget domene:** *Custom domains → + Add*, lag CNAME `www` → `<navn>.azurestaticapps.net` hos registraren (eller i Azure DNS). HTTPS-sertifikat ordnes automatisk.
8. Legg til en Lighthouse-sjekk i workflowen (ytelse/tilgjengelighet) som bonus.

**Forventet resultat:** Din egen nettside med HTTPS, automatisk deploy ved push, og forhåndsvisning av endringer.

**Vanlige feil:**

| Problem | Løsning |
|---|---|
| Deploy feiler med «App Directory Location ... could not be found» | `app_location` i workflowen peker feil |
| 404 på undersider | Sjekk filnavn (store/små bokstaver) og `navigationFallback` for SPA-er |
| Domenet valideres ikke | DNS-endringen har ikke propagert ennå (TTL), eller feil posttype |

**Opprydding:** `az group delete -n rg-prosjekt6 --yes` (eller behold den – Free-planen koster ikke).

**På CV:** Lenk til nettsiden! *«Publiserte personlig nettside på Azure Static Web Apps med CI/CD fra GitHub Actions, forhåndsvisningsmiljøer per pull request og sikkerhetsheadere.»*
