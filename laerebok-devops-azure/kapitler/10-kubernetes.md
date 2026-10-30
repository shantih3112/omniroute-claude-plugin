# Del 10 – Kubernetes

**Læringsmål for kapitlet.** Når du er ferdig, skal du kunne:

- forklare hvorfor Kubernetes finnes og hvilke problemer det løser,
- beskrive arkitekturen: cluster, kontrollplan og noder,
- jobbe med pods, deployments, services, ingress, ConfigMaps, Secrets og namespaces,
- forstå persistent lagring og autoskalering,
- bruke Helm, og forstå grunnleggende nettverk, sikkerhet og overvåking i Kubernetes,
- deploye en applikasjon til Azure Kubernetes Service (AKS).

## Hvorfor finnes Kubernetes?

**Problemet.** Docker gjør det enkelt å kjøre **én** container på **én** maskin. Men i produksjon har du kanskje 50 mikrotjenester, hver med 3–20 kopier, fordelt på 30 servere. Hvem bestemmer:

- hvilken server hver container skal kjøre på?
- hva som skjer når en container krasjer, eller en hel server dør?
- hvordan du oppdaterer til ny versjon uten nedetid?
- hvordan containere finner hverandre når de flytter rundt?
- hvordan du skalerer når trafikken øker?

**Hva er det?** Kubernetes (ofte forkortet **K8s** – K, åtte bokstaver, s) er en **container-orkestreringsplattform**. Den kjører containere på et cluster av maskiner og sørger hele tiden for at virkeligheten matcher det du har beskrevet.

Kubernetes ble opprinnelig utviklet av Google (inspirert av deres interne system *Borg*), gjort åpen kildekode i 2014, og er nå et prosjekt under **Cloud Native Computing Foundation (CNCF)**.

> **Hverdagsanalogi:** Kubernetes er **dirigenten i et orkester**. Du gir dirigenten noten («vi skal ha 3 fioliner, 2 cello og 1 tromme som spiller dette stykket»). Dirigenten plasserer musikerne, passer på at alle spiller, og hvis en fiolinist besvimer, henter dirigenten straks en ny fra reservebenken. Du forteller **hva** du vil ha – dirigenten sørger for **hvordan**.

### Det deklarative prinsippet – ønsket tilstand

Dette er den viktigste ideen i Kubernetes:

```text
  DU: «Jeg ønsker 3 kopier av web:v2»   (ønsket tilstand – desired state, i YAML)
                    │
                    ▼
        ┌───────────────────────┐
        │   KONTROLL-LØKKE      │  observer → sammenlign → handle → gjenta (for alltid)
        └───────────────────────┘
                    │
  VIRKELIGHET: 2 kopier kjører (én node døde)   → Kubernetes starter én ny kopi
```

Du sier ikke «start en container på server 4». Du sier «det skal alltid være 3». Kubernetes' **kontrollere** jobber kontinuerlig for å få den faktiske tilstanden til å matche den ønskede. Dette kalles **reconciliation** (avstemming) og gjør systemet **selvreparerende** (*self-healing*).

## Arkitekturen: cluster og noder

```text
 ┌─────────────────────────────── KUBERNETES CLUSTER ───────────────────────────────┐
 │                                                                                   │
 │  KONTROLLPLAN (control plane) – «hjernen»   (i AKS: administrert av Microsoft)    │
 │  ┌────────────┐ ┌──────┐ ┌───────────┐ ┌────────────────────┐                     │
 │  │ API-server │ │ etcd │ │ scheduler │ │ controller-manager │ (+cloud-controller) │
 │  └─────▲──────┘ └──────┘ └───────────┘ └────────────────────┘                     │
 │        │ alle snakker med API-serveren                                            │
 │  ──────┼──────────────────────────────────────────────────────────────────────    │
 │        │                                                                          │
 │  WORKER-NODE 1 (en VM)              WORKER-NODE 2 (en VM)                          │
 │  ┌──────────────────────────┐       ┌──────────────────────────┐                   │
 │  │ kubelet · kube-proxy     │       │ kubelet · kube-proxy     │                   │
 │  │ container runtime        │       │ container runtime        │                   │
 │  │ ┌─────┐ ┌─────┐ ┌─────┐  │       │ ┌─────┐ ┌─────┐          │                   │
 │  │ │ Pod │ │ Pod │ │ Pod │  │       │ │ Pod │ │ Pod │          │                   │
 │  │ └─────┘ └─────┘ └─────┘  │       │ └─────┘ └─────┘          │                   │
 │  └──────────────────────────┘       └──────────────────────────┘                   │
 └───────────────────────────────────────────────────────────────────────────────────┘
        ▲
   kubectl (du)
```

**Kontrollplanet:**

| Komponent | Oppgave |
|---|---|
| **kube-apiserver** | Inngangsdøren. Alle kommandoer (fra deg, `kubectl`, og fra andre komponenter) går gjennom API-serveren |
| **etcd** | Nøkkel–verdi-database som lagrer **hele** clusterets tilstand. Det viktigste å ta backup av i selvdriftede clustere |
| **kube-scheduler** | Bestemmer **hvilken node** nye pods skal kjøre på, basert på ressurser og regler |
| **kube-controller-manager** | Kjører kontrollerne som sørger for ønsket tilstand (f.eks. at riktig antall pods kjører) |
| **cloud-controller-manager** | Snakker med skyleverandøren (lager lastbalanserere, disker i Azure) |

**Hver node:**

| Komponent | Oppgave |
|---|---|
| **kubelet** | Agenten på noden. Får beskjed om hvilke pods som skal kjøre, og sørger for at containerne kjører og er friske |
| **container runtime** | Kjører containerne (typisk **containerd**) |
| **kube-proxy** | Setter opp nettverksregler slik at Services fungerer (noen nettverksløsninger erstatter den) |

**Hvordan en deploy faktisk skjer:**

1. Du kjører `kubectl apply -f deployment.yaml`.
2. API-serveren validerer og lagrer ønsket tilstand i etcd.
3. Deployment-kontrolleren ser at det trengs pods, og lager pod-objekter.
4. Scheduleren ser pods uten node, og tildeler dem noder.
5. Kubelet på hver node ser «sine» nye pods, ber container-runtime hente image og starte containerne.
6. Kubelet rapporterer status tilbake. Kontrollerne fortsetter å passe på.

## kubectl og første møte

**kubectl** er kommandolinjeverktøyet for Kubernetes. Det leser tilkoblingsinformasjon fra `~/.kube/config` (*kubeconfig*).

**Et lokalt cluster å øve på** (gratis):

- **Docker Desktop** – slå på Kubernetes i innstillingene.
- **kind** (*Kubernetes in Docker*) – `kind create cluster`.
- **minikube** – `minikube start`.
- **k3d/k3s** – lettvektsvarianter.

```bash
$ kubectl version                    # klient- og serverversjon
$ kubectl cluster-info
$ kubectl get nodes                  # list noder
NAME                 STATUS   ROLES           AGE   VERSION
kind-control-plane   Ready    control-plane   2m    v1.3x.x

$ kubectl get pods -A                # pods i ALLE namespaces (systemkomponenter)
$ kubectl api-resources              # alle ressurstyper clusteret kjenner
$ kubectl explain deployment.spec    # dokumentasjon for et felt – svært nyttig!
```

**Kommandomønsteret:** `kubectl <verb> <ressurstype> <navn> [flagg]`

| Verb | Gjør |
|---|---|
| `get` | List ressurser (`-o wide`, `-o yaml`, `-w` = følg med) |
| `describe` | Detaljer og **Events** – første sted å se ved feil |
| `apply -f` | Opprett/oppdater fra YAML (deklarativt – foretrukket) |
| `delete` | Slett |
| `logs` | Logger fra en container (`-f` følg, `--previous` forrige krasjede) |
| `exec -it` | Kjør kommando i en container |
| `port-forward` | Videresend en lokal port til en pod/service |
| `rollout` | Status, historikk og rollback for deployments |
| `scale` | Endre antall replikaer |

## Pods

**Hva er det?** En **pod** er den minste enheten i Kubernetes: **én eller flere containere** som kjører sammen på samme node, deler **IP-adresse** og kan dele **lagring**.

**Hvorfor ikke bare containere?** Noen ganger trenger to prosesser å være tett koblet: f.eks. en app-container og en hjelpecontainer (*sidecar*) som sender logger eller håndterer nettverkstrafikk. De må alltid kjøre sammen og snakke via `localhost`.

> **Husk:** I de aller fleste tilfeller er **én container per pod**. Tenk «pod ≈ én instans av appen din».

```yaml
# pod.yaml – en enkel pod (i praksis lager du sjelden pods direkte)
apiVersion: v1             # hvilken API-versjon ressurstypen tilhører
kind: Pod                  # ressurstype
metadata:
  name: hei                # navn
  labels:
    app: hei               # merkelapper – brukes til å velge ut ressurser
spec:                      # ønsket tilstand
  containers:
    - name: web
      image: nginx:1.27
      ports:
        - containerPort: 80
```

```bash
$ kubectl apply -f pod.yaml
$ kubectl get pods -o wide            # se hvilken node og IP poden fikk
$ kubectl describe pod hei
$ kubectl logs hei
$ kubectl exec -it hei -- sh          # -- skiller kubectl-flagg fra kommandoen
$ kubectl port-forward pod/hei 8080:80   # nå på http://localhost:8080
$ kubectl delete pod hei
```

**Pods er dødelige.** En pod som dør, blir *ikke* gjenopplivet – den blir erstattet av en **ny** pod med ny IP. Derfor lager vi nesten aldri pods direkte, men bruker **Deployments**.

**Livssyklus og status:** `Pending` (venter på node/image) → `Running` → `Succeeded`/`Failed`. Vanlige feilstatuser: `ImagePullBackOff`, `CrashLoopBackOff`, `OOMKilled` (se feilsøking).

## Deployments

**Hva er det?** En Deployment beskriver **ønsket tilstand for en tilstandsløs app**: hvilket image, hvor mange kopier (*replicas*), og hvordan oppdateringer skal rulles ut. Den lager og administrerer et **ReplicaSet**, som igjen sørger for riktig antall pods.

```text
 Deployment (web)  ──► ReplicaSet (web-7d9f, image v2) ──► Pod, Pod, Pod
                   └─► ReplicaSet (web-5c8a, image v1) ──► (0 pods – beholdt for rollback)
```

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
  labels:
    app: web
spec:
  replicas: 3                         # ønsket antall pods
  selector:
    matchLabels:
      app: web                        # hvilke pods denne deploymenten eier
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0               # aldri færre enn 3 tilgjengelige under oppdatering
      maxSurge: 1                     # maks 1 ekstra pod under oppdatering
  template:                           # mal for podene
    metadata:
      labels:
        app: web                      # MÅ matche selector
    spec:
      containers:
        - name: web
          image: nginx:1.27
          ports:
            - containerPort: 80
          resources:
            requests:                 # det poden er garantert (brukes av scheduleren)
              cpu: 100m               # 100 millicores = 0,1 CPU-kjerne
              memory: 128Mi
            limits:                   # maks den får bruke
              memory: 256Mi           # over dette → OOMKilled
          readinessProbe:             # er poden klar til å ta trafikk?
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 3
            periodSeconds: 5
          livenessProbe:              # lever den fortsatt? hvis ikke → restart
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 10
            periodSeconds: 10
```

```bash
$ kubectl apply -f deployment.yaml
$ kubectl get deployments,replicasets,pods
$ kubectl delete pod <en-av-web-podene>     # se at en ny pod straks blir laget!
$ kubectl scale deployment web --replicas=5

# Rullerende oppdatering til ny versjon
$ kubectl set image deployment/web web=nginx:1.27-alpine
$ kubectl rollout status deployment/web
$ kubectl rollout history deployment/web
$ kubectl rollout undo deployment/web       # rollback til forrige versjon
```

(I et GitOps-/CI-oppsett endrer man heller image-taggen i YAML-filen og kjører `apply` – da er Git sannheten.)

### Probes – helsesjekker

| Probe | Spørsmål | Hvis den feiler |
|---|---|---|
| **readinessProbe** | Er poden klar til å ta imot trafikk? | Poden fjernes fra Service-ens endepunkter (får ikke trafikk), men startes ikke på nytt |
| **livenessProbe** | Lever poden, eller har den hengt seg opp? | Containeren **restartes** |
| **startupProbe** | Har en treg app rukket å starte? | Liveness/readiness venter til denne lykkes |

> **Vanlig feil:** En for aggressiv livenessProbe (kort tid, sjekker databasen) får pods til å restarte i en løkke når databasen er treg – og gjør et lite problem til et stort. Liveness skal sjekke at *prosessen selv* lever, ikke avhengighetene.

### Requests og limits

- **Requests** – det poden reserverer. Scheduleren plasserer bare poden på en node med nok ledige requests.
- **Limits** – taket. Overskrides **minne**-limit → containeren drepes (**OOMKilled**). Overskrides **CPU**-limit → containeren strupes (*throttling*), ikke drepes.
- Enheter: CPU i kjerner eller millicores (`500m` = en halv kjerne). Minne i `Mi`/`Gi`.

> **Husk:** Sett alltid **requests** (ellers kan scheduleren ikke planlegge fornuftig, og autoskalering virker ikke) og **minne-limits**.

### Andre arbeidslast-typer

| Ressurs | Bruk |
|---|---|
| **Deployment** | Tilstandsløse apper (web, API) – det vanligste |
| **StatefulSet** | Apper som trenger stabil identitet og egen lagring per pod (databaser, Kafka): `db-0`, `db-1` … |
| **DaemonSet** | Én pod på **hver** node (loggagenter, overvåkingsagenter) |
| **Job** | Kjør en oppgave til den er ferdig (migrering, batch) |
| **CronJob** | Jobb på tidsplan (samme cron-syntaks som Linux) |

## Services

**Problemet.** Pods kommer og går, og får ny IP hver gang. Hvordan skal andre finne dem?

**Hva er det?** En **Service** gir et sett med pods én **stabil IP-adresse og ett DNS-navn**, og lastbalanserer trafikk mellom dem. Den finner podene med en **label selector**.

```text
                 Service «web»  (stabil IP 10.96.12.5, DNS: web.default.svc.cluster.local)
                 selector: app=web
              ┌────────┼────────┐
              ▼        ▼        ▼
          Pod app=web  Pod app=web  Pod app=web     (IP-ene endres – det gjør ingenting)
```

**Typer:**

| Type | Tilgjengelig fra | Bruk |
|---|---|---|
| **ClusterIP** (standard) | Bare inne i clusteret | Intern kommunikasjon mellom tjenester |
| **NodePort** | En port (30000–32767) på hver node | Testing, sjelden i produksjon |
| **LoadBalancer** | Ekstern IP via skyens lastbalanserer | I AKS lages en Azure Load Balancer med offentlig (eller intern) IP automatisk |
| **ExternalName** | DNS-alias til noe utenfor clusteret | Peke på en ekstern database |

```yaml
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: web
spec:
  type: ClusterIP
  selector:
    app: web               # send trafikk til pods med denne labelen
  ports:
    - port: 80             # porten Service-en lytter på
      targetPort: 80       # porten containeren lytter på
```

```bash
$ kubectl apply -f service.yaml
$ kubectl get svc
$ kubectl get endpointslices -l kubernetes.io/service-name=web   # hvilke pod-IP-er står bak?
$ kubectl run test --rm -it --image=busybox:1.36 -- wget -qO- http://web    # test fra innsiden
$ kubectl port-forward svc/web 8080:80                                       # test fra din PC
```

**DNS i clusteret:** En Service `web` i namespace `butikk` kan nås som `web` (fra samme namespace) eller `web.butikk` / `web.butikk.svc.cluster.local` (fra andre namespaces). CoreDNS sørger for dette.

> **Vanlig feil:** Service-en har ingen endepunkter. Nesten alltid fordi **selector ikke matcher** labels på podene (skrivefeil, `app: Web` vs. `app: web`), eller fordi podene ikke er *Ready*. Sjekk med `kubectl get pods --show-labels` og `kubectl describe svc web`.

## Ingress og Gateway API

**Problemet.** Med `type: LoadBalancer` får **hver** tjeneste sin egen offentlige IP og lastbalanserer. Med 20 tjenester blir det dyrt og uoversiktlig, og du får ikke HTTP-funksjoner som ruting på sti og TLS.

**Hva er det?** **Ingress** er et Kubernetes-objekt med **HTTP-rutingregler**: hvilke vertsnavn og stier som skal til hvilke Services. Selve trafikken håndteres av en **Ingress-kontroller** (en reverse proxy som kjører i clusteret).

```text
 Internett ─► (én offentlig IP) ─► INGRESS-KONTROLLER
                                    │  butikk.no/        → Service frontend
                                    │  butikk.no/api     → Service api
                                    │  admin.butikk.no   → Service admin
```

```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: butikk
spec:
  ingressClassName: webapprouting.kubernetes.azure.com   # hvilken kontroller (her: AKS app routing)
  tls:
    - hosts: [butikk.example.com]
      secretName: butikk-tls                # TLS-sertifikat lagret som Secret
  rules:
    - host: butikk.example.com
      http:
        paths:
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: api
                port:
                  number: 80
          - path: /
            pathType: Prefix
            backend:
              service:
                name: frontend
                port:
                  number: 80
```

**Ingress-kontrollere og utviklingen fremover:**

- Kubernetes-prosjektet har kunngjort at det populære community-prosjektet **ingress-nginx** pensjoneres (med begrenset vedlikehold frem til en sluttdato i 2026). Mange miljøer bruker det fortsatt, men nye oppsett bør velge et aktivt vedlikeholdt alternativ. Sjekk kubernetes.io-bloggen for detaljer.
- **Gateway API** er Kubernetes' moderne etterfølger til Ingress: mer uttrykksfull (trafikkdeling for canary, header-basert ruting), med roller for plattformteam (*Gateway*) og appteam (*HTTPRoute*). Støttes av mange kontrollere (Envoy Gateway, Istio, Cilium, Traefik, NGINX Gateway Fabric m.fl.).
- I **AKS** finnes **application routing add-on** (administrert NGINX-basert kontroller, med Microsofts egne planer for overgang – sjekk Learn) og **Application Gateway for Containers** (Azure-administrert lag 7-lastbalansering som støtter Gateway API).

Et enkelt eksempel med Gateway API:

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: butikk
spec:
  parentRefs:
    - name: hoved-gateway          # en Gateway som plattformteamet har satt opp
  hostnames: ["butikk.example.com"]
  rules:
    - matches:
        - path: { type: PathPrefix, value: /api }
      backendRefs:
        - name: api
          port: 80
          weight: 90               # 90 % til stabil versjon
        - name: api-canary
          port: 80
          weight: 10               # 10 % til ny versjon (canary)
```

> **Husk:** Lær **begge** konseptene. Du vil møte Ingress i nesten alle eksisterende clustere, og Gateway API i nye.

**TLS-sertifikater** håndteres ofte automatisk med **cert-manager**, som henter sertifikater fra Let's Encrypt og lagrer dem som Secrets.

## ConfigMaps og Secrets

**Prinsipp:** Samme image i alle miljøer – **konfigurasjonen** settes utenfra (jf. Twelve-Factor, kapittel 3).

**ConfigMap** – ikke-sensitiv konfigurasjon (loggnivå, URL-er, feature-flagg, konfigurasjonsfiler).

**Secret** – sensitiv informasjon (passord, tokens, nøkler).

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: web-config
data:
  APP_ENV: produksjon
  LOG_LEVEL: info
---                                   # --- skiller flere objekter i samme fil
apiVersion: v1
kind: Secret
metadata:
  name: web-secret
type: Opaque
stringData:                           # stringData: skriv i klartekst, lagres base64-kodet
  DB_PASSWORD: ikke-sjekk-meg-inn-i-git
```

Bruk dem i en pod:

```yaml
    spec:
      containers:
        - name: web
          image: minapp:1.0
          envFrom:
            - configMapRef:
                name: web-config          # alle nøkler blir miljøvariabler
          env:
            - name: DB_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: web-secret
                  key: DB_PASSWORD
          volumeMounts:                   # eller monter som filer
            - name: config
              mountPath: /etc/minapp
      volumes:
        - name: config
          configMap:
            name: web-config
```

```bash
$ kubectl create secret generic web-secret --from-literal=DB_PASSWORD='...'   # uten å skrive YAML-fil
$ kubectl get secret web-secret -o jsonpath='{.data.DB_PASSWORD}' | base64 -d
```

> **Vanlig feil:** Å tro at Secrets er kryptert. Som standard er de bare **base64-kodet** – det er *koding*, ikke kryptering; alle som kan lese Secret-objektet kan lese verdien. Beskytt dem med:
> - **RBAC** – begrens hvem som kan lese Secrets,
> - **kryptering i etcd** (AKS krypterer etcd; KMS-integrasjon med Key Vault er mulig),
> - **ekstern hemmelighetslagring**: Azure Key Vault med **Secrets Store CSI Driver**, eller External Secrets Operator,
> - **aldri** sjekk inn Secret-YAML med ekte verdier i Git (bruk Sealed Secrets/SOPS hvis du må).

> **Merk:** Pods som leser miljøvariabler fra en ConfigMap får **ikke** nye verdier automatisk når ConfigMap-en endres – podene må startes på nytt (`kubectl rollout restart deployment/web`). Monterte filer oppdateres etter en stund.

## Namespaces

**Hva er det?** Namespaces deler et cluster i **logiske områder**. Navn må være unike innenfor et namespace, men kan gjentas i andre.

**Hvorfor?** Skille team, applikasjoner eller miljøer; sette **ressurskvoter** (*ResourceQuota*) og standardgrenser (*LimitRange*); og gi tilgang med RBAC per namespace.

```bash
$ kubectl get namespaces
NAME              STATUS
default           Active     ← der ting havner hvis du ikke sier noe
kube-system       Active     ← systemkomponenter (ikke rør!)
kube-public, kube-node-lease ...

$ kubectl create namespace butikk
$ kubectl apply -f deployment.yaml -n butikk
$ kubectl get pods -n butikk
$ kubectl config set-context --current --namespace=butikk   # sett standard namespace
```

> **Vanlig feil:** «Podene mine er borte!» – de ligger i et annet namespace. Bruk `-n <namespace>` eller `-A`.

> **Merk:** Namespaces er **ikke** en sterk sikkerhetsgrense alene. Pods i ulike namespaces kan som standard snakke fritt med hverandre over nettverket – bruk NetworkPolicies.

## Persistent lagring

**Problemet.** Containere er flyktige (kapittel 9). En database i Kubernetes trenger lagring som overlever at poden flyttes til en annen node.

**Begrepene:**

```text
 Utvikler                           Plattform/sky
 ┌──────────────────────┐          ┌────────────────────────┐
 │ PersistentVolumeClaim│ ──bind──► │ PersistentVolume (PV)  │ ◄── lages automatisk av
 │ (PVC): «jeg trenger  │          │ f.eks. en Azure Disk   │     StorageClass
 │ 10 Gi, ReadWriteOnce»│          └────────────────────────┘     (dynamic provisioning)
 └──────────┬───────────┘
            │ monteres i
           Pod
```

- **PersistentVolume (PV)** – en lagringsressurs i clusteret (en Azure Disk, en Azure Files-share).
- **PersistentVolumeClaim (PVC)** – en **forespørsel** om lagring fra en app («10 Gi, lese/skrive fra én node»).
- **StorageClass** – en «oppskrift» for å lage PV-er automatisk. AKS har innebygde klasser som `managed-csi` (Azure Disk) og `azurefile-csi` (Azure Files).

**Tilgangsmoduser:** `ReadWriteOnce` (én node om gangen – Azure Disk), `ReadWriteMany` (mange noder – Azure Files), `ReadOnlyMany`.

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: data
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: managed-csi
  resources:
    requests:
      storage: 10Gi
---
# I pod-spesifikasjonen:
#   volumes:
#     - name: data
#       persistentVolumeClaim:
#         claimName: data
#   containers[].volumeMounts:
#     - name: data
#       mountPath: /var/lib/postgresql/data
```

**Reclaim policy** bestemmer hva som skjer med disken når PVC-en slettes: `Delete` (disken slettes – standard for dynamiske) eller `Retain` (beholdes).

> **Kostnad:** Hver PVC med Azure Disk er en ekte, fakturert disk. Slett PVC-er (og sjekk etter «foreldreløse» disker i ressursgruppen `MC_...`) når du rydder opp.

## Autoskalering

Kubernetes kan skalere på tre nivåer:

| Hva | Skalerer | Basert på |
|---|---|---|
| **HPA** (*Horizontal Pod Autoscaler*) | Antall **pods** | CPU, minne eller egne metrikker |
| **VPA** (*Vertical Pod Autoscaler*) | Requests/limits per pod | Faktisk forbruk over tid |
| **Cluster Autoscaler** / **Node Auto-Provisioning** | Antall **noder** | Pods som ikke får plass (Pending) / ubrukte noder |
| **KEDA** (*event-driven*) | Pods, også til null | Kølengde, meldinger, HTTP-trafikk, cron … (AKS-add-on finnes) |

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: web
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: web
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70        # mål: 70 % av CPU-request i snitt
```

```bash
$ kubectl get hpa -w      # følg med mens du genererer last
```

HPA krever **metrics-server** (installert i AKS) og at podene har **CPU-requests**.

```text
 Trafikk ↑ ─► CPU ↑ ─► HPA lager flere pods ─► noen blir Pending (ikke plass)
           ─► Cluster Autoscaler legger til en node ─► pods kjører ─► CPU ↓
```

## Helm – pakkehåndtereren for Kubernetes

**Problemet.** En ekte app består av mange YAML-filer (Deployment, Service, Ingress, ConfigMap, HPA …) som er nesten like for dev, test og prod, men med ulike verdier.

**Hva er det?** **Helm** pakker Kubernetes-ressurser i **charts**: maler med variabler, pluss en `values.yaml` med standardverdier. En installert chart kalles en **release**.

> **Hverdagsanalogi:** Helm er `apt` for Kubernetes. Og en chart er en oppskrift med tomme felt («antall personer: ___»), der `values.yaml` fyller inn tallene.

```text
minapp/                      # en Helm chart
├── Chart.yaml               # navn, versjon, beskrivelse
├── values.yaml              # standardverdier
└── templates/
    ├── deployment.yaml      # maler med {{ .Values.... }}
    ├── service.yaml
    └── _helpers.tpl
```

`templates/deployment.yaml` (utdrag):

```yaml
spec:
  replicas: {{ .Values.replicaCount }}
  template:
    spec:
      containers:
        - name: {{ .Chart.Name }}
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
```

`values.yaml`:

```yaml
replicaCount: 2
image:
  repository: acrlab123.azurecr.io/flaskapp
  tag: "1.0"
```

```bash
$ helm create minapp                                 # lag en ferdig chart-mal å starte fra
$ helm install web ./minapp -n butikk                # installer
$ helm upgrade web ./minapp --set image.tag=1.1      # oppgrader med ny verdi
$ helm upgrade --install web ./minapp -f values-prod.yaml   # installer eller oppgrader (vanlig i CI)
$ helm list -n butikk
$ helm history web -n butikk
$ helm rollback web 1 -n butikk                      # tilbake til revisjon 1
$ helm template web ./minapp                         # vis ferdig YAML uten å installere

# Installer andres charts, f.eks. Prometheus-stacken:
$ helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
$ helm repo update
$ helm install monitoring prometheus-community/kube-prometheus-stack -n monitoring --create-namespace
```

**Kustomize** er et alternativ (innebygd i `kubectl apply -k`) som bruker *overlegg* (*overlays*) i stedet for maler: en felles base + små endringer per miljø.

## Kubernetes-nettverk

**Grunnreglene i Kubernetes-nettverksmodellen:**

1. Hver pod får **sin egen IP-adresse**.
2. Alle pods kan nå alle andre pods **uten NAT** (med mindre du begrenser det).
3. Agenter på en node kan nå alle pods på den noden.

Dette implementeres av en **CNI-plugin** (*Container Network Interface*). I AKS: **Azure CNI** (pods får IP fra VNet-et), **Azure CNI Overlay** (pods får IP fra et eget, privat område – sparer VNet-adresser; anbefalt for de fleste nye clustere), og **Azure CNI Powered by Cilium** (eBPF-basert, med avanserte nettverkspolicyer og observerbarhet).

**Trafikkflyt:**

```text
 Ekstern bruker ─► Azure LB / App Gateway ─► Ingress/Gateway ─► Service ─► Pod
 Pod A ─► «http://api» (CoreDNS slår opp) ─► Service api (ClusterIP) ─► Pod B
```

**NetworkPolicy** – brannmurregler mellom pods. Uten policyer er **alt tillatt**.

```yaml
# Tillat bare trafikk til databasen fra pods med app=api
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: db-tillat-kun-api
  namespace: butikk
spec:
  podSelector:
    matchLabels:
      app: db                 # policyen gjelder db-podene
  policyTypes: [Ingress]
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: api
      ports:
        - protocol: TCP
          port: 5432
```

NetworkPolicy krever at CNI-en støtter det (Azure NPM, Calico eller Cilium i AKS).

**Service mesh** (Istio, Linkerd, Cilium) legger til mTLS mellom tjenester, avansert trafikkstyring og observability – avansert tema, men nyttig å kjenne navnet på.

## Kubernetes-sikkerhet

| Område | Tiltak |
|---|---|
| **Tilgang til API-et** | Kubernetes **RBAC**: `Role`/`ClusterRole` (hva) + `RoleBinding`/`ClusterRoleBinding` (hvem). I AKS: Entra ID-innlogging og gjerne Azure RBAC for Kubernetes |
| **Pod-identitet** | **ServiceAccounts** for pods; i AKS **Workload Identity** for å nå Azure-tjenester uten hemmeligheter |
| **Pod-sikkerhet** | `securityContext`: `runAsNonRoot`, `readOnlyRootFilesystem`, `allowPrivilegeEscalation: false`, drop capabilities. **Pod Security Admission** (nivåene *privileged*, *baseline*, *restricted*) per namespace |
| **Nettverk** | NetworkPolicies, private clustere, begrens API-servertilgang (authorized IP ranges / private API) |
| **Images** | Bare fra godkjente registre (Azure Policy / Kyverno / Gatekeeper), skanning, signering |
| **Hemmeligheter** | Key Vault + CSI-driver, RBAC på Secrets |
| **Oppdatering** | Hold Kubernetes-versjon og node-images oppdatert (AKS auto-upgrade-kanaler) |
| **Overvåking** | Audit-logger, Microsoft Defender for Containers |

```yaml
# Herdet container
securityContext:
  runAsNonRoot: true
  runAsUser: 10001
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  capabilities:
    drop: ["ALL"]
```

```yaml
# RBAC: «utviklere» kan lese pods og logger i namespace butikk
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: pod-leser
  namespace: butikk
rules:
  - apiGroups: [""]
    resources: ["pods", "pods/log"]
    verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: utviklere-leser-pods
  namespace: butikk
subjects:
  - kind: Group
    name: "<objekt-ID til Entra-gruppen>"     # i AKS med Entra-integrasjon
    apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: Role
  name: pod-leser
  apiGroup: rbac.authorization.k8s.io
```

```bash
$ kubectl auth can-i delete pods -n butikk --as=kari@firma.no    # test tilganger
```

## Overvåking av Kubernetes

**Hva vil du vite?** Er nodene friske? Hvor mye CPU/minne brukes? Restarter pods? Feiler deployer? Hva sier applikasjonsloggene?

**Grunnleggende kommandoer:**

```bash
$ kubectl top nodes                     # CPU/minne per node (krever metrics-server)
$ kubectl top pods -A --sort-by=memory
$ kubectl get events -A --sort-by=.lastTimestamp   # hva har skjedd i clusteret?
$ kubectl logs -l app=web --tail=50 -f  # logger fra alle pods med label
```

**Plattformer:**

- **Prometheus** (metrikker) + **Grafana** (dashboards) + **Alertmanager** – de facto standard i Kubernetes-verdenen (kapittel 13). Installeres ofte med Helm-charten `kube-prometheus-stack`.
- **I AKS:** **Azure Monitor managed service for Prometheus**, **Azure Managed Grafana**, og **Container Insights** (logger til Log Analytics). Slås på med `az aks update --enable-azure-monitor-metrics` og tilsvarende for logger.
- **Logger:** Containere skal logge til **stdout/stderr**; en agent (DaemonSet) samler dem.

## Azure Kubernetes Service i praksis

Se også kapittel 7.2. Her er en komplett flyt fra image til offentlig app i AKS.

```bash
RG=rg-aks-lab; LOC=norwayeast; ACR=acrlab$RANDOM; AKS=aks-lab
az group create -n $RG -l $LOC

# 1. Register og image
az acr create -g $RG -n $ACR --sku Basic
az acr build -r $ACR -t flaskapp:1.0 ./flaskapp            # eller docker build + push

# 2. Cluster med tilgang til ACR og app routing (administrert ingress)
az aks create -g $RG -n $AKS --tier free --node-count 2 --node-vm-size Standard_B2s \
  --attach-acr $ACR --enable-app-routing --generate-ssh-keys
az aks get-credentials -g $RG -n $AKS

# 3. Deploy
kubectl create namespace demo
kubectl apply -n demo -f k8s/                              # deployment.yaml, service.yaml, ingress.yaml
kubectl get pods,svc,ingress -n demo
```

`k8s/deployment.yaml` bruker `image: <ACR>.azurecr.io/flaskapp:1.0`, `k8s/service.yaml` er en ClusterIP-service, og `k8s/ingress.yaml` bruker `ingressClassName: webapprouting.kubernetes.azure.com`. Etter et par minutter viser `kubectl get ingress -n demo` en offentlig IP-adresse.

**Nyttige AKS-operasjoner:**

```bash
az aks nodepool add -g $RG --cluster-name $AKS -n userpool --node-count 1 --mode User   # ny node pool
az aks update -g $RG -n $AKS --enable-cluster-autoscaler --min-count 1 --max-count 3
az aks get-upgrades -g $RG -n $AKS -o table          # tilgjengelige Kubernetes-versjoner
az aks upgrade -g $RG -n $AKS --kubernetes-version <versjon>
az aks stop -g $RG -n $AKS                           # spar penger når du ikke bruker clusteret
```

**AKS-spesifikke ting å kjenne til:**

- AKS lager en **egen ressursgruppe** (`MC_<rg>_<cluster>_<region>`) for nodene, diskene og lastbalansereren. Ikke endre ting der manuelt.
- **Workload Identity** + Key Vault CSI-driveren for hemmeligheter.
- **Azure Policy-add-on** for å håndheve regler i clusteret.
- **Kubernetes-versjoner** støttes i en begrenset periode; planlegg jevnlige oppgraderinger (eller bruk auto-upgrade-kanaler).

> **Kostnad:** Nodene er VM-er som faktureres per sekund. To `Standard_B2s`-noder som står på i en måned kan koste mer enn hele studentkreditten tåler over tid. **Stopp eller slett clusteret samme dag.** Offentlige IP-er og disker koster også.

## Feilsøking i Kubernetes

**Gullregelen:** `kubectl describe` og **Events** forteller deg som regel hva som er galt.

| Status / symptom | Betyr | Sjekk |
|---|---|---|
| `Pending` | Poden får ikke node | `describe pod` → «Insufficient cpu/memory», node selector, PVC som ikke binder |
| `ImagePullBackOff` / `ErrImagePull` | Kan ikke hente image | Feil navn/tag, privat register uten tilgang (AcrPull?), Docker Hub-grense |
| `CrashLoopBackOff` | Containeren starter og krasjer gjentatte ganger | `kubectl logs <pod> --previous`, manglende miljøvariabel, feil kommando |
| `OOMKilled` | Overskred minne-limit | Øk limit eller fiks minnelekkasje |
| `Running`, men `0/1 READY` | readinessProbe feiler | Feil sti/port i proben, appen ikke klar |
| Service svarer ikke | Ingen endepunkter | Selector vs. labels, `targetPort`, pods ikke Ready |
| Ingress gir 404/502/503 | Feil regel, service eller backend | `describe ingress`, kontrollerens logger, test service med port-forward |
| `CreateContainerConfigError` | Mangler ConfigMap/Secret som refereres | `describe pod` |

**Systematisk:**

```bash
kubectl get pods -n demo                         # 1. status
kubectl describe pod <pod> -n demo               # 2. events nederst
kubectl logs <pod> -n demo [--previous]          # 3. app-logger
kubectl get svc,endpointslices -n demo           # 4. nettverk: har service endepunkter?
kubectl port-forward svc/web 8080:80 -n demo     # 5. test service direkte
kubectl get events -n demo --sort-by=.lastTimestamp
```

## Kapitteloppsummering

- Kubernetes orkestrerer containere over mange maskiner og holder **ønsket tilstand** med kontroll-løkker.
- Kontrollplan (API-server, etcd, scheduler, controller-manager) + noder (kubelet, runtime, kube-proxy).
- **Pod** = minste enhet. **Deployment** = ønsket antall pods og rullerende oppdateringer. Bruk probes og requests/limits.
- **Service** = stabil adresse og lastbalansering for pods. **Ingress/Gateway API** = HTTP-ruting inn i clusteret.
- **ConfigMap** for konfigurasjon, **Secret** for hemmeligheter (base64, ikke kryptert – beskytt dem).
- **Namespaces** organiserer; **PVC/StorageClass** gir varig lagring; **HPA/Cluster Autoscaler** skalerer.
- **Helm** pakker og versjonerer applikasjoner.
- Sikkerhet: RBAC, Workload Identity, securityContext, NetworkPolicies, oppdateringer.
- AKS = administrert kontrollplan; du betaler for nodene.

## Øvingsoppgaver

1. Lag et lokalt cluster med kind eller Docker Desktop. Deploy nginx med 3 replikaer og en ClusterIP-service. Slett en pod og se hva som skjer.
2. Gjør en rullerende oppdatering til et image-tag som **ikke finnes**. Hva skjer med de gamle podene? Rull tilbake.
3. Lag en ConfigMap med `LOG_LEVEL` og bruk den i en deployment. Endre verdien – når ser podene den nye verdien?
4. Lag en HPA og generer last med `kubectl run load --rm -it --image=busybox:1.36 -- sh -c "while true; do wget -qO- http://web; done"`.
5. Skriv en NetworkPolicy som blokkerer all innkommende trafikk til et namespace, og en som åpner for én bestemt app.
6. Lag en Helm chart med `helm create`, og installer den med to ulike `values`-filer (dev og prod) i to namespaces.

## Quiz

1. Hva betyr det at Kubernetes er deklarativt?
2. Hva lagres i etcd?
3. Hva er forskjellen på en pod og en deployment?
4. Hva skjer hvis en pod overskrider minne-limit? CPU-limit?
5. Hva er forskjellen på readinessProbe og livenessProbe?
6. Hvorfor trenger vi Services når pods har IP-adresser?
7. Hva er forskjellen på en Service av typen LoadBalancer og en Ingress?
8. Er Kubernetes Secrets kryptert som standard?
9. Hva er en PersistentVolumeClaim?
10. En pod står i `ImagePullBackOff` i AKS. Nevn to sannsynlige årsaker.
11. Hva er Helm, og hva er en release?
12. Hva gjør HPA, og hva krever den?

### Fasit

1. Du beskriver **ønsket tilstand** (hva), og Kubernetes jobber kontinuerlig for at faktisk tilstand skal matche den (hvordan), i stedet for at du gir trinnvise kommandoer.
2. **Hele clusterets tilstand og konfigurasjon** – alle objekter (deployments, pods, secrets …).
3. En **pod** er én kjørende instans (en eller flere containere). En **deployment** beskriver ønsket antall pods og håndterer opprettelse, erstatning og rullerende oppdateringer av dem.
4. Minne: containeren **drepes (OOMKilled)** og restartes. CPU: containeren **strupes** (throttling), men drepes ikke.
5. **Readiness**: er poden klar for trafikk? Feiler → tas ut av Service, ikke restart. **Liveness**: lever poden? Feiler → containeren restartes.
6. Fordi pods er flyktige og får nye IP-er når de erstattes. En Service gir en **stabil** IP/DNS og lastbalanserer mellom de pods som til enhver tid finnes.
7. **LoadBalancer** gir én ekstern IP per tjeneste (lag 4). **Ingress** gir HTTP-ruting (vertsnavn/sti, TLS) til mange tjenester bak én inngang, via en Ingress-kontroller.
8. **Nei**, de er bare base64-kodet i API-et. Kryptering i etcd, RBAC og eksterne hvelv (Key Vault) må brukes for beskyttelse.
9. En forespørsel om lagring fra en app (størrelse og tilgangsmodus), som bindes til et PersistentVolume – ofte opprettet automatisk via en StorageClass.
10. Feil image-navn/tag; clusteret mangler tilgang til ACR (ikke `--attach-acr`/AcrPull); imaget er bygget for feil arkitektur; nedlastingsgrense i Docker Hub.
11. Helm er en pakkehåndterer for Kubernetes som bruker **charts** (maler + verdier). En **release** er en installert instans av en chart i et cluster, med versjonshistorikk.
12. HPA justerer **antall pods** automatisk basert på metrikker (f.eks. CPU). Den krever **metrics-server** og at podene har **resource requests**.
