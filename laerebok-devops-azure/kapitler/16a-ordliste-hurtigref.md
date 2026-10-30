# Vedlegg A – Ordliste

Begrepene er sortert alfabetisk. Engelsk begrep står først når det er det som brukes i bransjen; tallet i parentes viser kapitlet der begrepet forklares nærmere.

| Begrep | Forklaring |
|---|---|
| **ACR** (Azure Container Registry) | Privat register for container-images i Azure (7.2) |
| **Agile** (smidig) | Arbeidsmåte med korte iterasjoner og hyppig tilbakemelding (8) |
| **AKS** (Azure Kubernetes Service) | Azures administrerte Kubernetes (7.2, 10) |
| **Alert / varsel** | Automatisk melding når en betingelse i overvåkingen er oppfylt (7.3, 13) |
| **Ansible** | Agentløst verktøy for konfigurasjonsstyring over SSH (11) |
| **API** | Avtalt grensesnitt for at programmer kan snakke sammen, ofte over HTTP med JSON (1) |
| **App Service** | Azures PaaS for webapper og API-er (7.2) |
| **Application Gateway** | Azures lag 7-lastbalanserer med WAF (7.2) |
| **Application Insights** | Applikasjonsovervåking i Azure Monitor (7.3, 13) |
| **ARM** (Azure Resource Manager) | Kontrollplanet som tar imot alle forespørsler om Azure-ressurser (7.1) |
| **Artefakt** (*artifact*) | Ferdig byggeresultat: image, pakke, zip (12) |
| **Autentisering** (AuthN) | Å bekrefte hvem noen er (13) |
| **Autorisasjon** (AuthZ) | Å bestemme hva noen får gjøre (13) |
| **Autoskalering** | Automatisk justering av kapasitet etter last (6, 10) |
| **Availability set** | VM-er fordelt på feil- og oppdateringsdomener i ett datasenter (7.2) |
| **Availability zone** (tilgjengelighetssone) | Fysisk adskilt datasenter-lokasjon i en region (6) |
| **Backend** | Serverdelen av en applikasjon: logikk og data (1) |
| **Bash** | Vanlig Linux-shell og skriptspråk (3) |
| **Bastion** | Azure-tjeneste for SSH/RDP uten offentlig IP på VM-en (7.2) |
| **Bicep** | Azures deklarative IaC-språk (7.4, 11) |
| **Blob Storage** | Objektlagring i Azure (7.3) |
| **Blue-green deployment** | To like miljøer; all trafikk byttes på én gang (8, 12) |
| **Branch** | Parallell utviklingslinje i Git (5) |
| **Canary deployment** | Ny versjon får gradvis økende andel trafikk (8, 12) |
| **CapEx / OpEx** | Investering på forhånd / løpende driftsutgift (6) |
| **CI/CD** | Continuous Integration / Delivery / Deployment (8, 12) |
| **CIDR** | Notasjon for IP-område, f.eks. `10.0.0.0/16` (2) |
| **CLI** | Kommandolinjegrensesnitt, f.eks. `az`, `kubectl` (3, 7) |
| **Cloud-init** | Konfigurasjon som kjøres ved første oppstart av en VM (7.2) |
| **Cluster** | Gruppe maskiner som samarbeider, f.eks. i Kubernetes (10) |
| **CNI** | Nettverksplugin for Kubernetes (10) |
| **Commit** | Lagret øyeblikksbilde i Git (5) |
| **ConfigMap** | Kubernetes-objekt for ikke-sensitiv konfigurasjon (10) |
| **Container** | Isolert, pakket applikasjon som deler vertens kjerne (9) |
| **Control plane** (kontrollplan) | Den styrende delen av et system (ARM i Azure, API-server i Kubernetes) |
| **CPU** | Prosessoren som utfører instruksjoner (1) |
| **Cron** | Planlegging av jobber på faste tidspunkter (3) |
| **CVE** | Offentlig registrert sårbarhet (13) |
| **DaemonSet** | Kubernetes-arbeidslast med én pod per node (10) |
| **Data drift** | At produksjonsdata endrer seg fra treningsdata (14) |
| **Deallocate** | Stoppe en Azure-VM slik at compute ikke faktureres (7.2) |
| **Deklarativ** | Beskriver ønsket sluttresultat, ikke stegene (10, 11) |
| **Deployment** | Utrulling av software; også Kubernetes-objekt for tilstandsløse apper (10) |
| **DevSecOps** | Sikkerhet integrert i hele DevOps-livssyklusen (8) |
| **DHCP** | Deler ut IP-adresser automatisk (2) |
| **DNS** | Oversetter navn til IP-adresser (1, 2) |
| **Docker / Dockerfile** | Containerverktøy / oppskrift for å bygge et image (9) |
| **DORA-metrikker** | Fire mål for leveranseevne: frekvens, ledetid, feilrate, gjenopprettingstid (8) |
| **DR** (*disaster recovery*) | Gjenoppretting etter større hendelser (6, 13) |
| **Elastisitet** | Automatisk skalering opp og ned etter behov (6) |
| **Entra ID** | Microsofts identitetstjeneste, tidligere Azure AD (7.1) |
| **Environment** | Deploymål med regler (GitHub/Azure DevOps) (12) |
| **Error budget** | Tillatt upålitelighet innenfor en SLO (8) |
| **etcd** | Databasen som lagrer Kubernetes-clusterets tilstand (10) |
| **Feature flag** | Slår funksjoner av/på uten ny deploy (8) |
| **Firewall** (brannmur) | Tillater eller blokkerer nettverkstrafikk (2) |
| **Frontend** | Delen av appen brukeren ser (1) |
| **Functions** | Azures serverless kodetjeneste (7.2) |
| **Gateway API** | Kubernetes' moderne etterfølger til Ingress (10) |
| **Git / GitHub** | Versjonskontrollverktøy / nettjeneste for Git-repoer (5) |
| **GitOps** | Git som sannhetskilde, agent synkroniserer miljøet (11) |
| **GPU** | Prosessor med tusenvis av kjerner for parallell beregning (14) |
| **Grafana** | Visualisering og dashboards (13) |
| **Helm / chart** | Pakkehåndterer for Kubernetes / pakke med maler og verdier (10) |
| **HPA** | Horizontal Pod Autoscaler (10) |
| **HTTP / HTTPS** | Protokollen for web / kryptert med TLS (1, 2) |
| **Hypervisor** | Programvare som kjører virtuelle maskiner (1) |
| **IaaS / PaaS / SaaS** | Infrastruktur / plattform / programvare som tjeneste (6) |
| **IaC** | Infrastructure as Code (11) |
| **Idempotens** | Samme operasjon flere ganger gir samme resultat (11) |
| **Image** | Skrivebeskyttet mal for containere (9) |
| **Incident** | Uplanlagt avbrudd eller forringelse av en tjeneste (8, 13) |
| **Ingress** | Kubernetes-objekt for HTTP-ruting inn i clusteret (10) |
| **IP-adresse** | Adresse for en enhet på et nettverk (2) |
| **Key Vault** | Azures hvelv for hemmeligheter, nøkler og sertifikater (7.3) |
| **Kernel** (kjerne) | Kjernen i operativsystemet (1, 3) |
| **KQL** | Spørrespråket i Log Analytics (7.3) |
| **kubectl** | Kommandolinjeverktøy for Kubernetes (10) |
| **Latency** | Forsinkelse / responstid (2, 13) |
| **Least privilege** | Minste nødvendige tilgang (13) |
| **Load balancer** (lastbalanserer) | Fordeler trafikk mellom servere (2, 7.2) |
| **Log Analytics** | Azures loggdatabase (7.3) |
| **Managed identity** | Azure-administrert identitet for ressurser – uten passord (7.1) |
| **Management group** | Gruppe av Azure-abonnementer (7.1) |
| **Merge / merge conflict** | Slå sammen brancher / når samme linjer er endret begge steder (5) |
| **MFA** | Multifaktorautentisering (7.1, 13) |
| **Microservices** | Applikasjon delt i mange små tjenester (1) |
| **MLOps** | DevOps for maskinlæring (14) |
| **Namespace** | Logisk område i Kubernetes; også Linux-isolasjonsmekanisme (9, 10) |
| **NAT** | Oversetting av IP-adresser, f.eks. privat → offentlig (2) |
| **Node** | En maskin i et cluster (10) |
| **NSG** | Network Security Group – Azures nettverksfilter (7.2) |
| **Observability** | Evnen til å forstå et system ut fra metrikker, logger og traces (8, 13) |
| **OIDC** | Åpen standard for innlogging; brukes for hemmelighetsløs tilgang fra CI til Azure (12) |
| **OOMKilled** | Prosess drept fordi den gikk tom for minne (9, 10) |
| **OpenTelemetry** | Standard for innsamling av telemetri (13) |
| **Peering** | Kobling mellom VNets (7.2) |
| **Pipeline** | Automatisert kjede av steg fra kode til drift (12) |
| **Pod** | Minste enhet i Kubernetes (10) |
| **Policy** (Azure Policy) | Regler for hvilke ressurser og innstillinger som er tillatt (7.1) |
| **Port** | Nummer som identifiserer en tjeneste på en maskin (2) |
| **Postmortem** | Etteranalyse etter en hendelse, uten skyld (8) |
| **Private endpoint** | Privat IP i ditt VNet for en PaaS-tjeneste (7.2, 7.3) |
| **Prometheus / PromQL** | Metrikksystem / dets spørrespråk (13) |
| **Probe** | Helsesjekk (readiness, liveness) (10) |
| **Pull request** | Forespørsel om å merge en branch, med gjennomgang (5) |
| **PVC / PV** | Forespørsel om lagring / lagringsressurs i Kubernetes (10) |
| **RAG** | Retrieval-Augmented Generation (14) |
| **RAM** | Raskt, flyktig arbeidsminne (1) |
| **RBAC** | Rollebasert tilgangskontroll (7.1, 10) |
| **Region** | Geografisk område med datasentre (6) |
| **Registry** | Lager for container-images (9) |
| **Remote state** | Terraform-state lagret sentralt med låsing (11) |
| **Repository** (repo) | Prosjekt under versjonskontroll (5) |
| **Resource group** | Logisk mappe for Azure-ressurser (7.1) |
| **Reverse proxy** | Står foran servere og tar imot forespørsler (2) |
| **Rollback** | Gå tilbake til forrige versjon (12) |
| **RPO / RTO** | Maks datatap / maks gjenopprettingstid (6) |
| **SAS** | Shared Access Signature – tidsbegrenset tilgang til Azure Storage (7.3) |
| **Scrum** | Rammeverk for smidig arbeid i sprinter (8) |
| **SDLC** | Livssyklusen for programvareutvikling (8) |
| **Secret** | Hemmelighet; også Kubernetes-objekt (10, 13) |
| **Serverless** | Kode som kjører ved hendelser uten serveradministrasjon (6, 7.2) |
| **Service** (Kubernetes) | Stabil adresse og lastbalansering for pods (10) |
| **Service principal** | Identitet for en applikasjon i Entra ID (7.1) |
| **Shared responsibility** | Delt sikkerhetsansvar mellom skyleverandør og kunde (6) |
| **SLA / SLO / SLI** | Avtale / mål / måling for tjenestekvalitet (8) |
| **Smoke test** | Rask test rett etter deploy (12) |
| **SRE** | Site Reliability Engineering (8) |
| **SSH** | Kryptert fjerninnlogging (2, 3) |
| **Staging** | Testmiljø som ligner produksjon (12) |
| **State** (Terraform) | Terraforms kobling mellom kode og ekte ressurser (11) |
| **Subnet** | Del av et nettverks adresseområde (2, 7.2) |
| **Subscription** | Azure-abonnement: fakturerings- og tilgangsgrense (7.1) |
| **systemd / systemctl** | Linux' tjenestesystem / kommandoen for det (3) |
| **Tag** | Nøkkel–verdi-merkelapp på ressurser; også versjonsmerke i Git/Docker |
| **TCP / UDP** | Pålitelig / rask transportprotokoll (2) |
| **Terraform** | Deklarativt IaC-verktøy fra HashiCorp (11) |
| **TLS** | Kryptering av nettverkstrafikk (2) |
| **Toil** | Manuelt, repeterende arbeid som bør automatiseres (8) |
| **Trace / span** | En forespørsels vei gjennom tjenester / ett ledd i den (13) |
| **TTL** | Hvor lenge et DNS-svar caches (2) |
| **UDR** | User Defined Route – egen rute i Azure (7.2) |
| **Virtualisering** | Kjøre flere virtuelle maskiner på én fysisk (1) |
| **VM** | Virtuell maskin (1, 7.2) |
| **VNet** | Virtuelt nettverk i Azure (7.2) |
| **Volume** | Varig lagring for containere (9) |
| **VPN** | Kryptert tunnel mellom nettverk (2) |
| **WAF** | Web Application Firewall (2, 7.2) |
| **Workload identity federation** | Tillit mellom eksternt system og Entra ID uten hemmelighet (7.1, 12) |
| **YAML** | Menneskevennlig dataformat brukt i konfigurasjon (4) |
| **Zero Trust** | «Stol aldri, verifiser alltid» (13) |

# Vedlegg B – Hurtigreferanser

## Linux

| Oppgave | Kommando |
|---|---|
| Hvor er jeg / list filer | `pwd` · `ls -la` |
| Bytt mappe | `cd /sti` · `cd ..` · `cd ~` |
| Lag / slett mappe | `mkdir -p a/b` · `rm -r mappe` |
| Kopier / flytt | `cp -r kilde mål` · `mv gammel ny` |
| Les fil | `cat` · `less` · `head -n 20` · `tail -f` |
| Søk i tekst | `grep -rin "tekst" .` |
| Finn filer | `find / -name "*.log" -size +100M` |
| Rettigheter / eier | `chmod 640 fil` · `chown bruker:gruppe fil` |
| Brukere | `sudo useradd -m -s /bin/bash navn` · `sudo usermod -aG gruppe navn` · `id navn` |
| Prosesser | `ps aux` · `top` · `kill PID` |
| Tjenester | `sudo systemctl status/start/stop/restart/enable nginx` |
| Logger | `journalctl -u nginx -f` · `tail -f /var/log/syslog` |
| Pakker (Ubuntu) | `sudo apt update && sudo apt install -y pakke` |
| Disk / minne | `df -h` · `du -sh *` · `free -h` |
| Nettverk | `ip addr` · `ip route` · `ss -tlnp` |
| Fjerninnlogging / kopiering | `ssh bruker@vert` · `scp fil bruker@vert:/sti` |
| Cron | `crontab -e` · `crontab -l` |
| Brannmur (Ubuntu) | `sudo ufw allow 22/tcp` · `sudo ufw enable` · `sudo ufw status` |

## Nettverksfeilsøking

| Oppgave | Kommando |
|---|---|
| DNS | `dig +short navn` · `nslookup navn` |
| Rekkevidde | `ping -c 4 vert` · `traceroute vert` · `mtr vert` |
| Port åpen? | `nc -zv vert 443` |
| HTTP | `curl -v https://vert` · `curl -I url` |
| TLS-sertifikat | `openssl s_client -connect vert:443 -servername vert` |
| Trafikk | `sudo tcpdump -i eth0 port 53` |

## Git

| Oppgave | Kommando |
|---|---|
| Start / klon | `git init` · `git clone URL` |
| Status / forskjeller | `git status` · `git diff` · `git diff --staged` |
| Commit | `git add -p` · `git commit -m "melding"` |
| Historikk | `git log --oneline --graph --all` |
| Branch | `git switch -c ny` · `git switch main` · `git branch -d gammel` |
| Synkroniser | `git pull` · `git push -u origin branch` · `git fetch` |
| Merge / rebase | `git merge branch` · `git rebase main` |
| Angre | `git restore fil` · `git restore --staged fil` · `git revert HASH` |
| Midlertidig lagring | `git stash` · `git stash pop` |
| Tag | `git tag -a v1.0.0 -m "..."` · `git push origin v1.0.0` |

## Docker

| Oppgave | Kommando |
|---|---|
| Bygg | `docker build -t navn:tag .` |
| Kjør | `docker run -d -p 8080:80 --name web image:tag` |
| List | `docker ps -a` · `docker images` |
| Logger / shell | `docker logs -f web` · `docker exec -it web sh` |
| Stopp / slett | `docker stop web` · `docker rm web` · `docker rmi image` |
| Inspiser | `docker inspect web` · `docker stats` |
| Register | `docker login` · `docker tag` · `docker push` |
| Compose | `docker compose up -d --build` · `docker compose logs -f` · `docker compose down -v` |
| Rydd | `docker system df` · `docker system prune` |

## Kubernetes (kubectl)

| Oppgave | Kommando |
|---|---|
| Kontekst og namespace | `kubectl config get-contexts` · `kubectl config set-context --current --namespace=ns` |
| List | `kubectl get pods,svc,deploy -n ns -o wide` |
| Detaljer og hendelser | `kubectl describe pod navn` · `kubectl get events --sort-by=.lastTimestamp` |
| Logger | `kubectl logs pod [-c container] [-f] [--previous]` |
| Shell | `kubectl exec -it pod -- sh` |
| Bruk YAML | `kubectl apply -f fil.yaml` · `kubectl delete -f fil.yaml` |
| Skaler / oppdater | `kubectl scale deploy/web --replicas=3` · `kubectl set image deploy/web web=img:2` |
| Utrulling | `kubectl rollout status/history/undo deploy/web` |
| Port-forward | `kubectl port-forward svc/web 8080:80` |
| Ressursbruk | `kubectl top nodes` · `kubectl top pods` |
| Tilgang | `kubectl auth can-i create pods --as=bruker` |
| Helm | `helm upgrade --install navn ./chart -f values.yaml` · `helm rollback navn 1` |

## Azure CLI

| Oppgave | Kommando |
|---|---|
| Innlogging | `az login` · `az account set --subscription ID` · `az account show` |
| Ressursgruppe | `az group create -n rg -l norwayeast` · `az group delete -n rg --yes --no-wait` |
| VM | `az vm create ...` · `az vm deallocate -g rg -n vm` · `az vm list -d -o table` |
| Nettverk | `az network vnet create ...` · `az network nsg rule create ...` |
| Lagring | `az storage account create ...` · `az storage blob upload --auth-mode login ...` |
| Web-app | `az webapp up --runtime "PYTHON:3.12" --sku F1 -n app` · `az webapp log tail` |
| Key Vault | `az keyvault secret set/show --vault-name kv -n navn` |
| RBAC | `az role assignment create --assignee ID --role Reader --scope SCOPE` |
| Policy | `az policy assignment create --policy ID --scope SCOPE` |
| ACR | `az acr create ...` · `az acr login -n acr` · `az acr build -r acr -t img:tag .` |
| AKS | `az aks create ...` · `az aks get-credentials -g rg -n aks` · `az aks stop` |
| Deploy Bicep | `az deployment group what-if/create -g rg -f main.bicep` |
| Filtrere utdata | `--query "[].name" -o tsv` · `-o table` |

## Terraform

| Oppgave | Kommando |
|---|---|
| Initialiser | `terraform init` (`-migrate-state` ved backend-bytte) |
| Format / valider | `terraform fmt -recursive` · `terraform validate` |
| Planlegg / utfør | `terraform plan -out=tfplan` · `terraform apply tfplan` |
| Slett alt | `terraform destroy` |
| Outputs | `terraform output` · `terraform output -raw navn` |
| State | `terraform state list` · `terraform state show adresse` |
| Variabler | `-var-file=prod.tfvars` · `export TF_VAR_navn=verdi` |

## Python – mønstre du ofte trenger

```python
import os, json, logging, argparse, subprocess, requests
verdi = os.environ.get("NAVN", "standard")                    # miljøvariabel
data = json.load(open("fil.json"))                            # les JSON
svar = requests.get(url, timeout=10); svar.raise_for_status() # HTTP-kall
logging.basicConfig(level=logging.INFO)                       # logging
subprocess.run(["ls", "-la"], check=True)                     # kjør kommando
```

## KQL og PromQL

```kusto
Tabell | where TimeGenerated > ago(1h) | summarize count() by bin(TimeGenerated, 5m) | render timechart
```

```promql
sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))
```

## Subnetting

| CIDR | Adresser | Brukbare i Azure |
|---|---|---|
| /16 | 65 536 | 65 531 |
| /24 | 256 | 251 |
| /25 | 128 | 123 |
| /26 | 64 | 59 |
| /27 | 32 | 27 |
| /28 | 16 | 11 |
| /29 | 8 | 3 |

Formel: `2^(32 − prefiks)`. Azure reserverer 5 adresser per subnett.
