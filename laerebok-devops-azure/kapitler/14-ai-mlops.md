# Del 14 – AI Infrastructure og MLOps

**Læringsmål for kapitlet.** Når du er ferdig, skal du kunne:

- forklare hva AI-infrastruktur og MLOps er, og hvordan de bygger på DevOps,
- forklare forskjellen på CPU og GPU, og trening vs. inferens,
- beskrive hvordan modeller deployes, serveres, versjoneres og overvåkes,
- kjenne Azure Machine Learning og Azure AI-tjenestene,
- forstå Kubernetes og infrastruktur for store språkmodeller (LLM-er),
- vurdere sikkerhet og kostnader ved AI-løsninger,
- planlegge veien fra DevOps til MLOps / AI Infrastructure.

## Hva er AI-infrastruktur?

**Hva er det?** AI-infrastruktur er all maskinvare, programvare og plattform som trengs for å **trene, kjøre (servere), skalere og overvåke** AI-modeller: GPU-er, lagring for store datamengder, raske nettverk, Kubernetes-clustere, modellregistre, pipelines og overvåking.

**Hvorfor finnes det som eget felt?** AI-arbeidslaster er annerledes enn vanlige webapper:

| | Vanlig webapp | AI-arbeidslast |
|---|---|---|
| Maskinvare | CPU, litt RAM | Ofte **GPU** med mye GPU-minne |
| Data | Megabyte–gigabyte | Gigabyte–petabyte (treningsdata, modellvekter) |
| Artefakt | Container-image (100 MB) | Modell (fra MB til hundrevis av GB) **+** container |
| Responstid | Millisekunder | Fra millisekunder til sekunder (LLM-er strømmer svar) |
| Kostnad | Moderat | Kan være svært høy (GPU-timer) |
| Feil | Krasj, feilkode | Også «stille feil»: modellen svarer, men **dårligere** |
| Kapasitet | Lett å få | GPU-er kan være mangelvare – kvoter og tilgjengelighet per region |

> **Hverdagsanalogi:** En vanlig webapp er en kafé: en kaffemaskin og en kasse. En AI-plattform er et industrikjøkken med spesialovner (GPU-er), et kjølelager av råvarer (data), oppskrifter som stadig forbedres (modeller), kvalitetskontroll av hver rett (overvåking), og en strømregning som må følges tett (kostnad).

## Hva er MLOps?

**Hva er det?** **MLOps** (*Machine Learning Operations*) er DevOps-prinsipper anvendt på maskinlæring: automatisering, versjonering, testing, CI/CD, overvåking og samarbeid – men utvidet til å håndtere **data** og **modeller** i tillegg til kode.

**Hvorfor?** En kjent observasjon fra industrien er at bare en liten del av et produksjonssystem for ML er selve modellkoden. Resten er datainnsamling, datavalidering, features, infrastruktur, servering, overvåking og konfigurasjon. Mange ML-prosjekter stopper i en Jupyter-notebook på en dataforskers laptop og kommer aldri i produksjon. MLOps løser det.

**DevOps vs. MLOps:**

| | DevOps | MLOps |
|---|---|---|
| Versjonerer | Kode | Kode **+ data + modeller + eksperimenter** |
| Testing | Enhetstester, integrasjonstester | + datavalidering, modellevaluering (nøyaktighet, rettferdighet) |
| Bygg-artefakt | Image, pakke | Trent modell (+ image for servering) |
| Pipeline | CI/CD | CI/CD **+ CT (Continuous Training)** |
| Overvåking | Oppetid, latency, feil | + **modellkvalitet, data drift, concept drift** |
| Hvorfor ytelsen faller | Feil i kode/infrastruktur | Også fordi **verden endrer seg** (dataene ser annerledes ut enn treningsdataene) |

**LLMOps** er MLOps for store språkmodeller: prompt-versjonering, evaluering av svar, RAG-pipelines, guardrails, kostnad per token.

## Hvordan kjøres AI-modeller i Cloud?

### Livssyklusen til en modell

```text
 ┌─────────┐   ┌──────────┐   ┌──────────┐   ┌───────────┐   ┌────────────┐   ┌───────────┐
 │  DATA   │──►│ TRENING  │──►│EVALUERING│──►│ REGISTRER │──►│ DEPLOY /   │──►│ OVERVÅK   │
 │ samle,  │   │ (GPU-    │   │ test mot │   │ modell +  │   │ SERVERING  │   │ kvalitet, │
 │ rense,  │   │  cluster)│   │ holdout- │   │ versjon + │   │ (endepunkt)│   │ drift,    │
 │ versjon.│   │          │   │ data     │   │ metadata  │   │            │   │ kostnad   │
 └─────────┘   └──────────┘   └──────────┘   └───────────┘   └────────────┘   └─────┬─────┘
      ▲                                                                              │
      └─────────────── ny data / drift oppdaget → tren på nytt (CT) ◄────────────────┘
```

### Trening vs. inferens

| | **Trening** (*training*) | **Inferens** (*inference*) |
|---|---|---|
| Hva | Modellen lærer fra data | Modellen brukes til å gi svar/prediksjoner |
| Når | Sjeldent (timer–uker per kjøring) | Hele tiden, for hver forespørsel |
| Ressurser | Mange kraftige GPU-er, mye data | Fra CPU (små modeller) til GPU (store modeller) |
| Mønster | Batch-jobb | Tjeneste (API) eller batch |
| Kostnadsprofil | Store, sjeldne utgifter | Løpende utgift som skalerer med bruk |

**Fine-tuning** er å videretrene en eksisterende modell på egne data – mye billigere enn å trene fra bunnen. Mange bedrifter trener aldri egne store modeller, men bruker ferdige modeller via API, eventuelt med fine-tuning eller **RAG** (se under).

### Tre måter å kjøre AI i skyen

```text
 1. FERDIGE AI-TJENESTER (SaaS/API)      «Kall et API»
    Azure AI-tjenester, modeller i Microsoft Foundry (f.eks. OpenAI-modeller)
    → minst drift, betal per kall/token

 2. ADMINISTRERT ML-PLATTFORM (PaaS)     «Tren og deploy med plattformens verktøy»
    Azure Machine Learning: compute clusters, managed online endpoints
    → middels drift

 3. EGEN INFRASTRUKTUR (IaaS/containere) «Full kontroll»
    GPU-VM-er, AKS med GPU-noder, egne serveringsrammeverk (vLLM, Triton)
    → mest drift, mest kontroll
```

Samme prinsipp som i kapittel 6: velg det høyeste abstraksjonsnivået som dekker behovet.

## CPU vs. GPU

**CPU** – få, kraftige og fleksible kjerner. God på variert logikk og sekvensielle oppgaver.

**GPU** – tusenvis av enklere kjerner som gjør **samme regneoperasjon på mye data samtidig** (parallellisering). Nevrale nettverk består i stor grad av matrisemultiplikasjoner – akkurat det GPU-er er laget for.

```text
 CPU: 8–128 kraftige kjerner            GPU: tusenvis av små kjerner
 ┌──┐┌──┐┌──┐┌──┐                        ┌┐┌┐┌┐┌┐┌┐┌┐┌┐┌┐┌┐┌┐┌┐┌┐┌┐┌┐┌┐┌┐
 │  ││  ││  ││  │  «noen få eksperter»    ├┤├┤├┤├┤├┤├┤├┤├┤├┤├┤├┤├┤├┤├┤├┤├┤  «en hær av
 └──┘└──┘└──┘└──┘                        └┘└┘└┘└┘└┘└┘└┘└┘└┘└┘└┘└┘└┘└┘└┘└┘   regnemaskiner»
```

> **Hverdagsanalogi:** Du skal rette 10 000 enkle gangestykker. En CPU er fem matteprofessorer – de kan løse hva som helst, men må ta stykkene etter hverandre. En GPU er 5 000 elever som hver tar to stykker samtidig. For enkle, like oppgaver i stor skala vinner elevene.

**Viktige egenskaper ved GPU-er for AI:**

| Egenskap | Hvorfor det betyr noe |
|---|---|
| **GPU-minne (VRAM)** | Modellen må (helst) få plass i GPU-minnet. Ofte den viktigste begrensningen |
| **Regnekraft** (FLOPS, ved ulike presisjoner som FP16/BF16/FP8) | Hastighet på trening og inferens |
| **Minnebåndbredde** | Hvor raskt data flyttes – avgjørende for LLM-inferens |
| **Kobling mellom GPU-er** (NVLink, InfiniBand) | Store modeller fordeles over mange GPU-er som må snakke raskt sammen |

**Tommelfingerregel for minne:** En modell med *N* milliarder parametere i 16-bits presisjon trenger omtrent **2 × N GB** bare for vektene (en 7B-modell ≈ 14 GB), pluss ekstra til mellomlagring under kjøring (*KV-cache*). **Kvantisering** (8-bit, 4-bit) reduserer minnebehovet betydelig, med noe tap av kvalitet.

**GPU-er i Azure.** GPU-VM-er finnes i **N-familien**: **NC**-serien (generell GPU-beregning, trening og inferens), **ND**-serien (store treningsjobber med mange tett koblede GPU-er), **NV**-serien (visualisering og virtuelle skrivebord). Tilgjengelige GPU-typer (f.eks. NVIDIA T4, A100, H100 og nyere, og AMD Instinct) varierer per region og endres raskt – sjekk *«GPU-optimized virtual machine sizes»* på Microsoft Learn.

> **Kostnad:** GPU-VM-er er blant de **dyreste** ressursene i skyen – fra noen få til mange titalls dollar per time per VM for de største. De krever også ofte at du **ber om kvoteøkning** før du kan lage dem, og student-/gratisabonnementer har vanligvis ingen GPU-kvote. Øv på CPU og små modeller, eller bruk API-baserte tjenester med lave volumer.

**Andre akseleratorer:** Google TPU, AWS Trainium/Inferentia, Microsoft Maia – spesialbrikker for AI.

## AI-arbeidslaster (*AI workloads*)

| Type | Eksempel | Infrastrukturbehov |
|---|---|---|
| **Klassisk ML** | Kredittrisiko, prisprediksjon, svindeldeteksjon (scikit-learn, XGBoost) | Ofte CPU er nok |
| **Datasyn** (*computer vision*) | Bildeklassifisering, kvalitetskontroll i fabrikk | GPU for trening, ofte GPU/edge for inferens |
| **Tale og lyd** | Transkribering, talesyntese | GPU eller ferdige tjenester |
| **Generativ AI / LLM** | Chatboter, oppsummering, kodeassistenter | Store GPU-er, eller API |
| **RAG** (*Retrieval-Augmented Generation*) | Chatbot som svarer basert på bedriftens dokumenter | LLM + vektordatabase/søk + datapipeline |
| **Agenter** | AI som bruker verktøy og API-er for å utføre oppgaver | LLM + verktøyintegrasjoner + streng sikkerhet |
| **Batch-inferens** | Klassifiser 10 millioner dokumenter over natten | Skalerbare jobber, spot-VM-er |

### RAG – forklart

**Hva er det?** En LLM vet bare det den ble trent på. **RAG** henter først relevante tekstbiter fra **dine** dokumenter og legger dem ved spørsmålet, slik at modellen kan svare basert på dem.

```text
 INNLASTING (batch)                         SPØRSMÅL (sanntid)
 Dokumenter ─► del opp ─► embeddings ─►     Bruker: «Hva er reisepolicyen for Japan?»
 (PDF, wiki)   (chunks)   (vektorer)  │            │ 1. embedding av spørsmålet
                                      ▼            ▼
                              ┌─────────────────────────┐
                              │ Vektorindeks / søk      │ 2. finn de mest like tekstbitene
                              │ (f.eks. Azure AI Search)│
                              └───────────┬─────────────┘
                                          │ 3. spørsmål + relevante tekstbiter
                                          ▼
                                    ┌──────────┐
                                    │   LLM    │ 4. svar med kildehenvisning
                                    └──────────┘
```

**Infrastrukturen** bak RAG er klassisk DevOps: datapipelines (innlasting og oppdatering), søkeindeks, API-er, hemmeligheter, tilgangskontroll (brukeren skal bare få svar fra dokumenter hen har tilgang til!), overvåking og kostnadsstyring.

## Model deployment og model serving

**Model deployment** – å gjøre en trent modell tilgjengelig i et miljø. **Model serving** – selve tjenesten som tar imot forespørsler og returnerer prediksjoner.

### Serveringsmønstre

| Mønster | Beskrivelse | Eksempel |
|---|---|---|
| **Sanntid** (*online*) | API som svarer på hver forespørsel | «Er denne transaksjonen svindel?» på 50 ms |
| **Batch** | Kjør modellen på store datamengder periodisk | Nattlig scoring av alle kunder |
| **Strømming** | Prediksjoner på hendelser fra en kø | Sensordata fra IoT |
| **Edge** | Modellen kjører på enheten | Kamera i fabrikk, mobiltelefon |

### En enkel modell som API

```python
# serve.py – en scikit-learn-modell som REST-API med FastAPI
# pip install fastapi uvicorn scikit-learn joblib
import joblib
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()
modell = joblib.load("modell.joblib")         # lastes én gang ved oppstart, ikke per forespørsel
MODELL_VERSJON = "1.3.0"

class Input(BaseModel):                         # validering av input
    areal: float
    rom: int
    byggeår: int

@app.get("/health")
def health():
    return {"status": "ok", "modell_versjon": MODELL_VERSJON}

@app.post("/predict")
def predict(x: Input):
    pris = modell.predict([[x.areal, x.rom, x.byggeår]])[0]
    return {"estimert_pris": round(float(pris)), "modell_versjon": MODELL_VERSJON}
```

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY serve.py modell.joblib ./
RUN useradd --uid 10001 app
USER app
CMD ["uvicorn", "serve:app", "--host", "0.0.0.0", "--port", "8000"]
```

Dette er nøyaktig det du lærte i kapittel 9 og 12 – et container-image som deployes med CI/CD. Forskjellen er at **modellen** er en ekstra artefakt som må versjoneres og spores.

### Serveringsrammeverk

| Verktøy | Bruk |
|---|---|
| FastAPI / Flask | Enkle modeller pakket som API |
| **vLLM** | Høyytelses servering av LLM-er (effektiv minnehåndtering, batching) |
| **NVIDIA Triton Inference Server** | Mange modelltyper og rammeverk, GPU-optimalisert |
| **KServe** | Standardisert modellservering på Kubernetes, med autoskalering |
| **Ollama / llama.cpp** | Kjøre små LLM-er lokalt (også på CPU) – fint for læring |
| ONNX Runtime | Kjør modeller fra mange rammeverk effektivt |

**Utrullingsstrategier fra kapittel 8 og 12 gjelder også for modeller:** canary (5 % av trafikken til ny modell), **shadow deployment** (ny modell får kopi av trafikken, men svarene brukes ikke – du sammenligner bare), og A/B-testing av modeller.

## ML-pipelines

**Hva er det?** Automatiserte arbeidsflyter for hele ML-livssyklusen – som CI/CD, men med data- og treningssteg.

```text
 Trigger: ny data / tidsplan / kodeendring / drift-varsel
    │
    ▼
 ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  ┌─────────────┐
 │Hent data │─►│ Valider   │─►│ Feature- │─►│  Tren    │─►│ Evaluer mot  │─►│ Registrer   │
 │          │  │ data      │  │ prosess. │  │          │  │ prod-modell  │  │ hvis bedre  │
 └──────────┘  │ (skjema,  │  └──────────┘  └──────────┘  └──────────────┘  └──────┬──────┘
               │ fordeling)│                                                       │
               └───────────┘                                         CD: deploy (canary)
```

**Verktøy:** Azure Machine Learning pipelines, Kubeflow Pipelines, MLflow, Apache Airflow, Prefect, og vanlige CI/CD-verktøy (GitHub Actions, Azure Pipelines) som orkestrerer det hele.

**Viktig prinsipp:** Pipelinen skal være **reproduserbar** – samme kode + samme data + samme konfigurasjon skal gi samme modell. Derfor versjoneres data, kode, miljø (container/conda) og hyperparametere.

## Model versioning – versjonering av modeller

**Hva må versjoneres?**

| Hva | Hvordan |
|---|---|
| Kode | Git |
| Data | Datasett-versjoner (Azure ML data assets, DVC, Delta Lake/tidsstempel i lagring) |
| Modell | **Modellregister** (Azure ML registry, MLflow Model Registry) |
| Miljø | Container-image / conda-miljø |
| Eksperimenter | Parametere og metrikker per treningskjøring (MLflow tracking) |
| For LLM-apper | Prompter, systeminstruksjoner, modellversjon, evalueringsdatasett |

**Modellregisteret** er for modeller det et container-register er for images: hver modellversjon lagres med metadata – hvilke data og hvilken kode den ble trent med, evalueringsresultater, hvem som godkjente den, og hvilken versjon som er i produksjon.

**Lineage** (avstamming): Kunne svare på «hvilke data og hvilken kode laget modellen som ga dette svaret i produksjon 14. mars?». Viktig for feilsøking, revisjon og regulering (f.eks. **EUs KI-forordning / AI Act** for høyrisikosystemer).

```python
# MLflow – logg en treningskjøring og registrer modellen
import mlflow
import mlflow.sklearn
from sklearn.ensemble import RandomForestRegressor

with mlflow.start_run():
    params = {"n_estimators": 200, "max_depth": 8}
    modell = RandomForestRegressor(**params).fit(X_train, y_train)
    mae = abs(modell.predict(X_test) - y_test).mean()

    mlflow.log_params(params)                       # hyperparametere
    mlflow.log_metric("mae", mae)                   # evaluering
    mlflow.sklearn.log_model(modell, "modell",
                             registered_model_name="boligpris")   # registrer ny versjon
```

(Azure Machine Learning workspaces støtter MLflow som sporings-API.)

## Model monitoring – overvåking av modeller

En modell kan være **teknisk frisk** (200 OK, rask) men **gi dårlige svar**. Derfor overvåkes flere lag:

| Nivå | Hva | Eksempel |
|---|---|---|
| **Drift/infrastruktur** | Latency, feilrate, GPU-utnyttelse, minne, kø | Som kapittel 13 |
| **Data drift** | Input-dataene endrer seg sammenlignet med treningsdataene | Gjennomsnittlig boligareal i forespørslene har økt 30 % |
| **Prediction drift** | Fordelingen av modellens svar endrer seg | Plutselig flagges 15 % av transaksjonene som svindel i stedet for 1 % |
| **Concept drift** | Sammenhengen mellom input og riktig svar endrer seg | Svindlere endrer metoder; renten endrer boligpriser |
| **Modellkvalitet** | Nøyaktighet mot fasit når fasiten blir kjent | Faktisk salgspris vs. estimert |
| **For LLM-er** | Relevans, korrekthet (*groundedness*), skadelig innhold, token-forbruk, kostnad per forespørsel, brukerfeedback | Andel svar med «tommel ned» |

```text
 Tid ──────────────────────────────────────────────────────────►
 Modellkvalitet  ████████████████▇▇▇▆▆▅▅▄▄▃  ← gradvis forverring (drift)
                                      ▲
                          varsel → tren på nytt med nye data
```

**I Azure:** Azure Machine Learning har modellovervåking (data drift, prediction drift, datakvalitet); Application Insights og Azure Monitor for teknisk drift; Microsoft Foundry har evaluering og overvåking av generative AI-apper.

## Azure Machine Learning

**Hva den gjør.** Azure Machine Learning (Azure ML) er Azures **plattform for hele ML-livssyklusen**: data, eksperimenter, trening, modellregister, deploy og overvåking.

**Bestanddeler:**

```text
 Azure ML workspace
 ├── Data assets / datastores        (koblet til Blob Storage / Data Lake)
 ├── Compute
 │    ├── Compute instance           (personlig utviklings-VM med Jupyter/VS Code)
 │    ├── Compute cluster            (autoskalerende CPU/GPU-cluster for trening, kan skalere til 0)
 │    ├── Serverless compute         (bare oppgi størrelse, Azure håndterer resten)
 │    └── Kubernetes compute         (koble til et AKS-cluster)
 ├── Environments                    (container-/conda-miljøer)
 ├── Jobs og Pipelines               (trening, batch)
 ├── Experiments / MLflow tracking
 ├── Models (modellregister) og Registries (deles mellom workspaces)
 ├── Endpoints
 │    ├── Managed online endpoints   (sanntids-API, Azure drifter infrastrukturen; blue-green med trafikkdeling)
 │    └── Batch endpoints
 └── Monitoring
 Avhengigheter: Storage Account, Key Vault, Container Registry, Application Insights
```

**Eksempel – deploy en registrert modell til et managed online endpoint med CLI (ml-utvidelsen):**

```bash
az extension add -n ml

# endpoint.yml
# $schema: https://azuremlschemas.azureedge.net/latest/managedOnlineEndpoint.schema.json
# name: boligpris-ep
# auth_mode: key

# deployment-blue.yml
# $schema: https://azuremlschemas.azureedge.net/latest/managedOnlineDeployment.schema.json
# name: blue
# endpoint_name: boligpris-ep
# model: azureml:boligpris:3          # modell «boligpris» versjon 3 fra registeret
# instance_type: Standard_DS3_v2
# instance_count: 1

az ml online-endpoint create -f endpoint.yml -g rg-ml -w mlw-lab
az ml online-deployment create -f deployment-blue.yml -g rg-ml -w mlw-lab --all-traffic

# Ny modellversjon som "green" med 10 % trafikk (canary)
az ml online-deployment create -f deployment-green.yml -g rg-ml -w mlw-lab
az ml online-endpoint update -n boligpris-ep -g rg-ml -w mlw-lab --traffic "blue=90 green=10"
```

(Modeller i MLflow-format kan deployes uten egen scoring-kode; andre modeller trenger et scoring-skript og et miljø. Se Microsoft Learn: «Deploy and score a machine learning model by using an online endpoint».)

**Sikkerhet:** Managed virtual network / private endpoints for workspace, managed identity for compute, RBAC-roller som *AzureML Data Scientist*, nøkkel- eller Entra-autentisering på endepunkter.

**Kostnad:** Workspace i seg selv koster lite, men du betaler for **compute** (instanser som står på!, clustere, endepunkter – endepunkter kjører hele tiden), og avhengighetene (lagring, ACR, Key Vault, Application Insights). **Slå av compute instances** når du ikke bruker dem – sett *idle shutdown*.

## Azure AI-tjenester og Microsoft Foundry

**Ferdige AI-tjenester** (tidligere kalt *Cognitive Services*, nå del av **Azure AI services / Foundry Tools**) gir AI via API uten at du trener modeller selv:

| Tjeneste | Gjør |
|---|---|
| **Azure OpenAI / Foundry Models** | Tilgang til store språkmodeller (bl.a. OpenAI-modeller) og mange andre modeller fra en modellkatalog, med Azures sikkerhet, nettverk og compliance |
| **Azure AI Search** | Søk og vektorsøk – ofte kjernen i RAG |
| **Azure AI Speech** | Tale til tekst, tekst til tale, oversettelse |
| **Azure AI Language** | Sentimentanalyse, nøkkelfraser, gjenkjenning av personopplysninger (PII) |
| **Azure AI Vision** | Bildeanalyse, OCR |
| **Azure AI Document Intelligence** | Hente strukturerte data fra fakturaer, skjemaer, kvitteringer |
| **Azure AI Translator** | Oversettelse |
| **Azure AI Content Safety** | Oppdage skadelig innhold og prompt-angrep i input/output |

**Microsoft Foundry** (tidligere *Azure AI Foundry*, og før det *Azure AI Studio*) er Microsofts samlede plattform for å bygge generative AI-apper og agenter: modellkatalog, prompt-utvikling, evaluering, agenter, innholdssikkerhet og overvåking. Navn og struktur har endret seg flere ganger – sjekk Microsoft Learn for gjeldende begreper.

**Kalle en språkmodell fra Python** (eksempel med OpenAI-biblioteket mot en Azure-deployment og Entra-autentisering):

```python
# pip install openai azure-identity
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

token_provider = get_bearer_token_provider(
    DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
)
client = AzureOpenAI(
    azure_endpoint="https://<din-ressurs>.openai.azure.com/",
    azure_ad_token_provider=token_provider,        # managed identity / az login – ingen API-nøkkel
    api_version="<api-versjon fra Microsoft Learn>",
)

svar = client.chat.completions.create(
    model="<navnet på din deployment>",             # deploymentnavnet du valgte i Azure
    messages=[
        {"role": "system", "content": "Du er en hjelpsom DevOps-mentor. Svar kort på norsk."},
        {"role": "user", "content": "Forklar forskjellen på en container og en VM."},
    ],
)
print(svar.choices[0].message.content)
print(svar.usage)                                    # antall tokens = grunnlaget for kostnaden
```

> **Merk:** SDK-er, API-versjoner og anbefalte klienter for Azure OpenAI/Foundry endres ofte (Microsoft har bl.a. introdusert et nytt «v1»-API som gjør at man ikke trenger å angi `api_version` på samme måte). Følg den nyeste *quickstart* på Microsoft Learn når du skriver kode.

**Driftsbegreper for LLM-tjenester:**

- **Tokens** – tekst måles i tokens (biter av ord). Både input og output koster.
- **Kvoter og rate limits** – målt i tokens per minutt (TPM) og forespørsler per minutt (RPM) per deployment og region. Får du `429 Too Many Requests`, er grensen nådd → retry med backoff (kapittel 4), eller fordel lasten.
- **Deploymenttyper** – *Standard/pay-as-you-go* (betal per token, delt kapasitet), *Global*/*Data Zone* (rutes mellom regioner innen et område – vurder datakrav), og **provisioned throughput** (reservert kapasitet med forutsigbar ytelse og fast pris).
- **API-gateway foran AI** – Azure API Management kan lastbalansere mellom flere AI-deployments, håndheve token-grenser per team og logge forbruk («AI gateway»-mønsteret).

## Kubernetes for AI

Kubernetes er mye brukt for AI fordi det gir felles plattform for både vanlige tjenester og GPU-arbeidslaster.

**Byggesteiner:**

- **GPU node pools** – egne node pools med GPU-VM-er, som kan skalere til null når de ikke brukes.
- **NVIDIA device plugin / GPU Operator** – gjør GPU-er synlige for Kubernetes, slik at pods kan be om dem.
- **Taints og tolerations** – sørger for at bare GPU-arbeidslaster havner på (dyre) GPU-noder.
- **Jobber og køsystemer** – Kubernetes Jobs, **Kueue**, Volcano for batch- og treningsjobber.
- **KServe / vLLM / Triton** for servering; **Ray** og **Kubeflow** for distribuert trening og pipelines.
- **KEDA** – skaler inferenspods etter kølengde eller forespørsler.
- I AKS: **KAITO** (*Kubernetes AI Toolchain Operator*) – en add-on som automatiserer utrulling av åpne modeller med riktige GPU-noder.

```yaml
# Pod som ber om én GPU
apiVersion: v1
kind: Pod
metadata:
  name: gpu-test
spec:
  restartPolicy: Never
  tolerations:
    - key: "sku"
      operator: "Equal"
      value: "gpu"
      effect: "NoSchedule"               # tåler GPU-nodenes taint
  containers:
    - name: cuda
      image: nvidia/cuda:12.4.1-base-ubuntu22.04
      command: ["nvidia-smi"]            # viser GPU-ene containeren ser
      resources:
        limits:
          nvidia.com/gpu: 1              # be om én GPU (krever device plugin / GPU Operator)
```

```bash
# GPU node pool i AKS (krever GPU-kvote i regionen!)
az aks nodepool add -g rg-ai -n gpupool --cluster-name aks-ai \
  --node-vm-size <GPU-VM-størrelse> --node-count 0 \
  --enable-cluster-autoscaler --min-count 0 --max-count 2 \
  --node-taints sku=gpu:NoSchedule
```

**Utfordringer:** store images og modellfiler (tregt å laste – bruk cache, forhåndsnedlasting, eller montert lagring), GPU-deling (MIG, time-slicing), og at GPU-er er dyre når de står ledige.

## Infrastruktur for LLM-er

### Hva skal til for å kjøre en LLM selv?

```text
 Klient ─► API Gateway (auth, rate limit, logging, token-telling)
              │
              ▼
        Inferenstjeneste (vLLM / Triton / KServe) på GPU-noder
              │  modellvekter lastet i GPU-minne
              │  KV-cache for samtalekontekst
              │  continuous batching (flere forespørsler samtidig)
              ▼
        Svar strømmes token for token (Server-Sent Events)
 Rundt: modellager (Blob), autoskalering (KEDA), overvåking (tokens/s, time-to-first-token),
        guardrails (Content Safety), kostnadsrapportering per team
```

**Nøkkelmetrikker for LLM-servering:**

| Metrikk | Betyr |
|---|---|
| **TTFT** (*time to first token*) | Hvor lang tid før brukeren ser første ord |
| **Tokens per sekund** (per bruker og totalt) | Hastighet og kapasitet |
| **Samtidige forespørsler** | Hvor mange brukere samtidig |
| **GPU-utnyttelse og GPU-minne** | Om du utnytter (dyre) ressurser |
| **Kostnad per 1000 tokens / per forespørsel** | Økonomi |

### Kjøpe (API) eller bygge (egen hosting)?

| | Administrert API (Azure OpenAI/Foundry) | Egen hosting (åpne modeller på GPU) |
|---|---|---|
| Oppstart | Minutter | Dager–uker |
| Drift | Minimal | Betydelig (GPU-er, servering, oppdateringer) |
| Kostnadsmodell | Per token – billig ved lavt volum | Per GPU-time – kan lønne seg ved høyt, jevnt volum |
| Kontroll | Begrenset til tjenestens muligheter | Full (modellvalg, fine-tuning, data) |
| Datahåndtering | Avtalebasert; velg region/data zone | Data blir i ditt miljø |
| Skalering | Kvoter | Begrenset av GPU-tilgang |

For de fleste bedrifter er det riktig å **starte med administrerte API-er** og vurdere egen hosting når volum, krav eller kostnader tilsier det.

## Scaling AI applications – skalering

- **Horisontal skalering** av inferens: flere replikaer bak lastbalanserer, autoskalert på kø eller samtidighet (ikke bare CPU – GPU-arbeidslaster er ofte begrenset av GPU-minne).
- **Batching**: samle flere forespørsler i én GPU-kjøring for høyere gjennomstrømning.
- **Caching**: cache svar på identiske forespørsler; **semantisk cache** for lignende spørsmål.
- **Modellvalg**: bruk den **minste modellen som er god nok**. En liten modell kan håndtere enkle oppgaver; send bare vanskelige oppgaver til den store (*routing*).
- **Asynkron behandling**: lange jobber via kø (Service Bus) + workers, ikke synkrone HTTP-kall.
- **Flere regioner/deployments** bak en gateway for å omgå kvoter og øke tilgjengelighet.
- **Skaler til null** for sjelden brukte modeller (men husk oppstartstid – store modeller tar tid å laste).

## AI-sikkerhet

AI-systemer har **alle** de vanlige sikkerhetsutfordringene (kapittel 13) **pluss** nye:

| Trussel | Beskrivelse | Tiltak |
|---|---|---|
| **Prompt injection** | Brukeren (eller et dokument/en nettside modellen leser) gir instruksjoner som overstyrer systemet: «Ignorer tidligere instruksjoner og …» | Behandle all input som upålitelig, Content Safety / prompt shields, begrens hva modellen *kan* gjøre, menneskelig godkjenning for viktige handlinger |
| **Datalekkasje** | Modellen avslører sensitiv informasjon fra kontekst eller treningsdata | Tilgangskontroll i RAG (sikkerhetstrimming), ikke legg hemmeligheter i prompter, PII-filtrering |
| **Overprivilegerte agenter** | En AI-agent med verktøy kan gjøre skade hvis den lures | Minste privilegium for agentens identitet, sandkasse, logging, godkjenning |
| **Usikker output-håndtering** | Modellens svar brukes direkte i SQL, shell eller HTML | Valider og «escape» output som all annen upålitelig input |
| **Modell- og datatyveri / forgiftning** | Noen stjeler modellvekter eller manipulerer treningsdata | Tilgangskontroll, integritetssjekk, signering, kontroll med datakilder |
| **Forsyningskjede** | Ondsinnede modeller eller pakker fra offentlige kilder | Bruk kjente kilder, skann, foretrekk trygge formater (f.eks. safetensors fremfor pickle) |
| **Denial of wallet** | Angriper sender store mengder dyre forespørsler | Rate limiting, token-grenser per bruker, budsjettvarsler |

**OWASP Top 10 for LLM Applications** er en god sjekkliste. Microsoft har også rammeverk for **ansvarlig AI** (*Responsible AI*): rettferdighet, pålitelighet og sikkerhet, personvern, inkludering, åpenhet og ansvarlighet. I EU stiller **AI Act** krav til visse AI-systemer – relevant også i Norge via EØS.

## Kostnader ved AI-infrastruktur

**Hva koster?**

| Kostnadsdriver | Eksempel |
|---|---|
| **GPU-compute** | Trening og selvhostet inferens – den desidert største posten |
| **Tokens** | Input + output for API-baserte modeller; lange prompter og RAG-kontekst koster |
| **Ledig kapasitet** | GPU-er/endepunkter som står på uten trafikk |
| **Lagring** | Datasett, modellversjoner, checkpoints, logger |
| **Datatrafikk** | Flytting av store datasett mellom regioner |
| **Søk/vektorindekser** | AI Search-nivåer, embeddings |
| **Overvåking** | Logging av prompter og svar kan bli store volumer |

**Optimalisering:**

1. **Velg riktig modell** – minste modell som løser oppgaven; test billigere modeller først.
2. **Kort ned prompter** og begrens output-lengde; cache gjenbrukbar kontekst der tjenesten støtter det.
3. **Batch** ikke-hastende jobber (flere tjenester har rabatterte batch-API-er).
4. **Skaler GPU-noder til null**; bruk **spot**-VM-er for avbrytbar trening med checkpointing.
5. **Provisioned throughput** kun når volumet er høyt og forutsigbart.
6. **Mål kostnad per forespørsel/per bruker** og tagg alt per team/prosjekt (FinOps for AI).
7. **Budsjetter og varsler** – særlig for eksperimenter.

> **Kostnad:** Et klassisk studentuhell er en compute instance i Azure ML eller en GPU-VM som står på over helgen. Sett **auto-shutdown** og **idle shutdown** første gang du lager noe.

## Fra DevOps Engineer til MLOps / AI Infrastructure Engineer

**Hva du allerede har fra denne boken:**

```text
 DevOps-kompetanse                    Brukes i MLOps / AI Infra som …
 ─────────────────                    ──────────────────────────────
 Linux, nettverk, sky                 Grunnlaget for alle AI-plattformer
 Docker                               Pakking av modeller og treningsmiljøer
 Kubernetes                           GPU-clustere, KServe, KAITO, Kubeflow
 Terraform/Bicep                      Reproduserbare AI-miljøer
 CI/CD                                ML-pipelines, CT, modell-deploy med canary
 Monitoring                           Modellovervåking, token- og GPU-metrikker
 Sikkerhet                            AI-sikkerhet, hemmeligheter, private endepunkter
 Kostnadsstyring                      FinOps for GPU og tokens
```

**Hva du må lære i tillegg:**

1. **ML-grunnlag** – hva trening, validering, overtilpasning, evalueringsmetrikker og typiske algoritmer er. (Du trenger ikke være dataforsker, men du må snakke språket.)
2. **Python for data** – pandas, NumPy, scikit-learn; grunnleggende PyTorch.
3. **ML-verktøy** – MLflow, Azure Machine Learning, Jupyter.
4. **GPU-infrastruktur** – CUDA-grunnlag, GPU-er i Kubernetes, `nvidia-smi`.
5. **LLM-økosystemet** – API-er, RAG, vektorsøk, evaluering, vLLM, guardrails.
6. **Data engineering-grunnlag** – datapipelines, formater (Parquet), datakvalitet.

**Foreslått læringsvei (6–12 måneder etter DevOps-grunnlaget):**

| Steg | Innhold | Prosjekt |
|---|---|---|
| 1 | ML-grunnlag (f.eks. Microsoft Learn, fast.ai, Andrew Ngs kurs) | Tren en scikit-learn-modell og spor den med MLflow |
| 2 | Modellservering | FastAPI-modell i Docker med CI/CD til Container Apps (prosjekt 11) |
| 3 | Azure ML | Trening på compute cluster, registrering, managed online endpoint med blue-green |
| 4 | LLM-apper | RAG-chatbot med Azure AI Search og en Foundry-modell, med evaluering |
| 5 | Kubernetes for AI | Kjør en liten åpen LLM med vLLM/Ollama på Kubernetes (CPU lokalt, ev. GPU i sky) |
| 6 | Overvåking | Drift- og kvalitetsmonitorering av modellen; kostnadsdashboard |

**Relevante sertifiseringer:** *AI-900* (grunnleggende AI på Azure), *AI-102* / etterfølgere (Azure AI Engineer), *DP-100* (Azure Data Scientist – Azure ML), *CKA* (Kubernetes). Microsoft fornyer AI-sertifiseringene ofte – sjekk Microsoft Learn.

**Rolletitler du vil se:** MLOps Engineer, ML Platform Engineer, AI Infrastructure Engineer, LLMOps Engineer, AI Platform Engineer, ML Engineer (ofte mer modellnært).

> **Husk:** Bedrifter trenger langt flere som kan **drifte AI pålitelig, sikkert og kostnadseffektivt** enn som kan finne opp nye modeller. En solid DevOps-bakgrunn er et svært godt utgangspunkt.

## Kapitteloppsummering

- AI-infrastruktur er plattformen for å trene, servere og overvåke modeller; MLOps er DevOps for ML (kode + data + modeller).
- Trening er sjeldent og GPU-tungt; inferens skjer hele tiden og bestemmer løpende kostnad.
- GPU-er er laget for parallelle matriseoperasjoner; GPU-minne er ofte den viktigste begrensningen.
- Modeller serveres som API-er (sanntid), batch, strømming eller på edge; deploy med canary/shadow.
- ML-pipelines automatiserer data → trening → evaluering → registrering → deploy; alt versjoneres.
- Overvåk både teknisk helse og modellkvalitet (data drift, concept drift).
- Azure ML er plattformen for egen ML; Azure AI-tjenester og Microsoft Foundry gir ferdige modeller og verktøy for generativ AI.
- Kubernetes med GPU-noder, KServe/vLLM og KEDA er vanlig for AI i skala.
- AI-sikkerhet: prompt injection, datalekkasje, overprivilegerte agenter, «denial of wallet».
- Kostnad styres med modellvalg, skalering til null, batching, caching og budsjetter.

## Øvingsoppgaver

1. Installer Ollama lokalt, kjør en liten åpen modell, og kall den via HTTP-API-et med `curl`.
2. Tren en enkel scikit-learn-modell (f.eks. på et åpent boligprisdatasett), lagre den med `joblib`, og server den med FastAPI-eksemplet i en Docker-container.
3. Legg til MLflow-sporing og sammenlign tre treningskjøringer med ulike hyperparametere i MLflow UI (`mlflow ui`).
4. Regn ut omtrentlig GPU-minne for vektene til en 8B- og en 70B-modell i 16-bit og 4-bit.
5. Skriv en trusselmodell (1 side) for en RAG-chatbot som svarer på spørsmål om HR-dokumenter. Hvilke trusler fra tabellen gjelder, og hvilke tiltak velger du?
6. Lag et kostnadsestimat i Azure Pricing Calculator for en chatbot med 1 000 brukere som stiller 10 spørsmål om dagen (anta et gjennomsnittlig tokenantall per spørsmål og svar).

## Quiz

1. Hva er forskjellen på DevOps og MLOps?
2. Hva er forskjellen på trening og inferens?
3. Hvorfor egner GPU-er seg bedre enn CPU-er for nevrale nettverk?
4. Hva er data drift?
5. Hva er et modellregister?
6. Hva er RAG, og hvorfor brukes det?
7. Hva er prompt injection?
8. Hva er TTFT?
9. Nevn tre måter å redusere kostnadene for en LLM-applikasjon.
10. Hvorfor er en god DevOps-bakgrunn verdifull for AI Infrastructure-roller?

### Fasit

1. MLOps anvender DevOps-prinsippene på ML, men versjonerer og tester i tillegg **data og modeller**, har **kontinuerlig trening** og overvåker **modellkvalitet** (drift), ikke bare teknisk helse.
2. **Trening**: modellen lærer fra data (sjelden, ressurskrevende). **Inferens**: den trente modellen brukes til å gi svar (kontinuerlig, per forespørsel).
3. Nevrale nettverk består i stor grad av matriseoperasjoner som kan utføres parallelt, og GPU-er har tusenvis av kjerner laget for nettopp slik parallell beregning, pluss høy minnebåndbredde.
4. At input-dataene i produksjon endrer seg sammenlignet med dataene modellen ble trent på, slik at modellens ytelse kan forverres.
5. Et sentralt lager for modellversjoner med metadata (data, kode, metrikker, status), brukt til sporbarhet, godkjenning og deploy.
6. *Retrieval-Augmented Generation*: relevante tekstbiter fra egne dokumenter hentes og legges ved spørsmålet til LLM-en, slik at den kan svare basert på oppdatert, bedriftsspesifikk informasjon uten å trenes på nytt.
7. Et angrep der input (fra bruker eller fra innhold modellen leser) inneholder instruksjoner som prøver å overstyre systemets instruksjoner eller få modellen til å gjøre noe uønsket.
8. *Time to first token* – tiden fra forespørselen sendes til brukeren mottar første del av svaret.
9. For eksempel: bruke en mindre modell, korte ned prompter og begrense output, caching, batching av ikke-hastende jobber, skalere GPU-ressurser til null, rate limiting per bruker.
10. Fordi AI i produksjon i stor grad er et infrastrukturproblem: containere, Kubernetes, IaC, CI/CD, overvåking, sikkerhet og kostnadsstyring – akkurat DevOps-ferdighetene.
