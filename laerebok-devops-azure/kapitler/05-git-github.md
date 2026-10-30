# Del 5 – Git, GitHub og versjonskontroll

**Læringsmål for kapitlet.** Når du er ferdig, skal du kunne:

- forklare hva versjonskontroll er og hvorfor alle profesjonelle team bruker det,
- bruke Git til å lage commits, branches og merges,
- samarbeide via GitHub med clone, push, pull og pull requests,
- løse merge-konflikter,
- velge en Git-arbeidsflyt og skrive gode commit-meldinger,
- lage en enkel GitHub Actions-workflow.

## Hva er versjonskontroll?

**Hva er det?** Versjonskontroll er et system som **husker alle endringer** i filer over tid: hvem endret hva, når og hvorfor. Du kan gå tilbake til enhver tidligere versjon.

**Hvorfor finnes det?** Uten versjonskontroll ender man med mapper som dette:

```text
 rapport.docx
 rapport_v2.docx
 rapport_v2_FINAL.docx
 rapport_v2_FINAL_ekte_final.docx
 rapport_v2_FINAL_ekte_final_Karis_endringer.docx
```

Tenk deg det med 500 kodefiler og 30 utviklere. Versjonskontroll løser:

- **Historikk** – hva endret seg, og hvorfor?
- **Samarbeid** – mange kan jobbe samtidig uten å overskrive hverandre.
- **Angring** – noe gikk galt i produksjon? Gå tilbake til forrige fungerende versjon.
- **Sporbarhet** – hvilken endring introduserte feilen?

> **Hverdagsanalogi:** Git er som lagringspunkter i et dataspill. Før du går inn i et farlig område, lagrer du. Går det galt, laster du det siste lagringspunktet. Branches er som å lage en kopi av spillet for å teste en annen vei, uten å ødelegge hovedspillet.

## Git og GitHub – ikke det samme

| | Git | GitHub |
|---|---|---|
| Hva | Et **verktøy** for versjonskontroll | En **nettjeneste** som lagrer Git-repoer |
| Hvor | Kjører lokalt på din maskin | I skyen (github.com) |
| Laget av | Linus Torvalds (2005) | GitHub Inc. (eid av Microsoft) |
| Tilbyr | Commits, branches, historikk | Deling, pull requests, issues, Actions (CI/CD), sikkerhetsskanning |
| Alternativer | (Git er dominerende) | GitLab, Bitbucket, Azure Repos |

Git er **distribuert**: hver utvikler har en full kopi av hele historikken. GitHub er bare et felles møtepunkt.

## Installasjon og oppsett

```bash
$ git --version                     # er Git installert?
$ sudo apt install git              # Ubuntu; Windows: git-scm.com; macOS: xcode-select --install

# Fortell Git hvem du er – dette står i hver commit du lager
$ git config --global user.name "Kari Nordmann"
$ git config --global user.email "kari@example.com"
$ git config --global init.defaultBranch main     # kall hovedbranchen "main"
$ git config --list                               # se innstillingene
```

**Autentisering mot GitHub.** GitHub tar ikke imot vanlig passord for Git-operasjoner. Bruk enten SSH-nøkkel (legg `~/.ssh/id_ed25519.pub` inn under *Settings → SSH and GPG keys* på GitHub), eller **GitHub CLI** (`gh auth login`), eller et *personal access token* over HTTPS.

## Kjernebegrepene

### Repository (repo)

**Hva er det?** Et repository er et prosjekt under versjonskontroll: alle filene pluss en skjult mappe `.git` som inneholder hele historikken.

```bash
$ mkdir mitt-prosjekt && cd mitt-prosjekt
$ git init                  # gjør mappen til et Git-repo
Initialized empty Git repository in /home/student/mitt-prosjekt/.git/
```

### De tre områdene

Dette er det viktigste å forstå i Git:

```text
 ┌──────────────────┐  git add   ┌──────────────────┐ git commit ┌──────────────────┐
 │  ARBEIDSMAPPE    │ ─────────► │  STAGING AREA    │ ─────────► │  REPOSITORY      │
 │ (working dir)    │            │  (index)         │            │  (historikken)   │
 │ filene du endrer │            │ «det som skal    │            │ lagrede          │
 │                  │            │  med i neste     │            │ øyeblikksbilder  │
 │                  │            │  commit»         │            │                  │
 └──────────────────┘            └──────────────────┘            └──────────────────┘
```

> **Hverdagsanalogi:** Du pakker en flyttekasse. Arbeidsmappen er rommet ditt. Staging er kassen – du velger hva som skal oppi. Commit er å teipe igjen kassen og skrive en etikett på den. Kassen (commiten) endres ikke etterpå.

### Commit

**Hva er det?** Et **øyeblikksbilde** (*snapshot*) av prosjektet, med en melding, forfatter, tidspunkt og en unik ID (en *hash*, som `a1b2c3d`).

```bash
$ echo "# Mitt prosjekt" > README.md
$ git status                          # hva er endret?
Untracked files:
        README.md

$ git add README.md                   # legg i staging
$ git commit -m "Legg til README"     # lag commit med melding
[main (root-commit) 3f2a1b9] Legg til README
 1 file changed, 1 insertion(+)

$ git log --oneline                   # vis historikken kort
3f2a1b9 Legg til README
```

Nyttige varianter:

```bash
$ git add .                 # legg til ALLE endringer i mappen
$ git add -p                # velg bit for bit hva som skal med (anbefalt!)
$ git diff                  # hva har jeg endret (ikke staget)?
$ git diff --staged         # hva ligger i staging?
$ git log --oneline --graph --all   # historikk som tre
$ git show 3f2a1b9          # se hva en commit endret
```

### Gode commit-meldinger

En god commit-melding forklarer **hva** og **hvorfor**, i imperativ form («Legg til», ikke «La til»):

```text
 DÅRLIG                       BRA
 "fix"                        "Fiks nullpekerfeil i innloggingen ved tomt passord"
 "endringer"                  "Øk timeout mot betalings-API fra 5 til 15 sekunder"
 "asdf"                       "Legg til helsesjekk-endepunkt /health"
```

Mange team bruker **Conventional Commits**: `feat: legg til eksport til CSV`, `fix: rett beregning av mva`, `docs: oppdater README`, `ci: kjør tester på pull requests`. Det gjør historikken lettere å lese og kan brukes til automatisk versjonering.

> **Husk:** Små, hyppige commits som gjør *én* ting er bedre enn én kjempecommit med alt. Da er det lett å forstå, gjennomgå og angre.

### .gitignore

En fil som forteller Git hva som **ikke** skal versjonskontrolleres:

```text
# .gitignore
.venv/
__pycache__/
*.log
.env              # lokale hemmeligheter!
node_modules/
.terraform/
*.tfstate         # Terraform-state kan inneholde hemmeligheter
.DS_Store
```

> **Vanlig feil:** Å committe `.env` med passord. Selv om du sletter filen i neste commit, ligger den i **historikken**. Hvis en hemmelighet har havnet i Git: **roter (bytt) hemmeligheten umiddelbart**. Å skrive om historikken er ikke nok når den allerede er pushet.

### Branch

**Hva er det?** En branch (gren) er en **parallell utviklingslinje**. Du kan jobbe med en ny funksjon uten å påvirke hovedbranchen (`main`).

```text
                 feature/innlogging
                 ┌──●──●──●
                 │         \  (merge)
 main  ──●──●──●─┴──●───────●──►
```

Teknisk er en branch bare en lett «peker» til en commit – derfor er branches billige og raske i Git.

```bash
$ git branch                          # list branches (* = den du er på)
$ git switch -c feature/innlogging    # lag ny branch og bytt til den
$ git switch main                     # bytt tilbake til main
$ git branch -d feature/innlogging    # slett branch (etter merge)
```

(`git checkout -b` gjør det samme som `git switch -c` – du vil se begge i guider.)

### Merge

**Hva er det?** Å slå sammen endringene fra én branch inn i en annen.

```bash
$ git switch main
$ git merge feature/innlogging
```

To typer:

- **Fast-forward**: `main` har ikke endret seg siden branchen ble laget. Git flytter bare pekeren frem.
- **Merge commit (tre-veis merge)**: begge har endret seg. Git lager en ny commit som kombinerer dem.

**Rebase** er et alternativ: flytter dine commits slik at de ligger «oppå» siste versjon av main, som gir en rett historikk.

```bash
$ git switch feature/innlogging
$ git rebase main
```

> **Vanlig feil:** Rebase skriver om historikk. **Rebase aldri commits som andre allerede har hentet** (f.eks. `main`). Bruk rebase på din egen, lokale branch.

### Merge-konflikter

**Hva er det?** Når to branches har endret **samme linjer** i samme fil, kan ikke Git vite hvilken versjon som er riktig. Du må bestemme.

```bash
$ git merge feature/farge
Auto-merging style.css
CONFLICT (content): Merge conflict in style.css
Automatic merge failed; fix conflicts and then commit the result.
```

Filen ser nå slik ut:

```text
body {
<<<<<<< HEAD
  background: white;          ← slik det er på main (der du står)
=======
  background: lightblue;      ← slik det er på branchen du merger inn
>>>>>>> feature/farge
}
```

**Løs konflikten:**

1. Åpne filen. Bestem hva som er riktig (én av dem, begge, eller noe nytt).
2. Fjern markørene `<<<<<<<`, `=======` og `>>>>>>>`.
3. `git add style.css`
4. `git commit` (Git foreslår en melding).

Angre hele mergen: `git merge --abort`.

> **Husk:** Konflikter er normalt og ikke farlig. De blir færre og mindre hvis du merger små endringer ofte. VS Code har et godt verktøy for å løse konflikter visuelt.

## Jobbe med GitHub: remote, clone, push og pull

**Remote** er en ekstern kopi av repoet, typisk på GitHub. Standardnavnet er `origin`.

```text
     DIN PC                                    GITHUB
 ┌──────────────┐        git push         ┌──────────────┐
 │ lokalt repo  │ ──────────────────────► │ origin       │
 │              │ ◄────────────────────── │ (remote)     │
 └──────────────┘  git pull / git fetch   └──────────────┘
                  ◄──── git clone ────────  (første gang)
```

```bash
# Hente et eksisterende repo første gang
$ git clone git@github.com:brukernavn/repo.git
$ cd repo

# Koble et lokalt repo til et nytt, tomt GitHub-repo
$ git remote add origin git@github.com:brukernavn/mitt-prosjekt.git
$ git push -u origin main         # -u: husk at lokal main følger origin/main

$ git push                        # send dine commits til GitHub
$ git fetch                       # hent nyheter, men ikke flett dem inn
$ git pull                        # fetch + merge (hent og flett inn)
$ git remote -v                   # vis remotes
```

> **Vanlig feil:** `git push` blir avvist med «Updates were rejected because the remote contains work that you do not have locally». Noen har pushet før deg. Kjør `git pull` (løs eventuelle konflikter), og push igjen. **Ikke** bruk `git push --force` på delte brancher – da sletter du kollegaenes arbeid.

## Pull requests

**Hva er det?** En pull request (PR) er en **forespørsel om å merge** en branch inn i en annen (vanligvis `main`), med mulighet for **kodegjennomgang** (*code review*), diskusjon og automatiske tester før endringen slippes inn. (GitLab kaller det *merge request*.)

**Hvorfor?** Fire øyne ser mer enn to. PR-er fanger feil, sprer kunnskap i teamet, og sikrer at tester kjører før noe havner i `main`.

```text
 1. Lag branch    2. Commit og push    3. Åpne PR på GitHub
 feature/x ──►    ●──●──● ──► origin   «Merge feature/x into main»
                                                   │
 4. CI kjører tester automatisk ✓  ◄────────────────┤
 5. Kollega gjennomgår, kommenterer ◄───────────────┤
 6. Du retter, pusher flere commits ◄───────────────┤
 7. Godkjent ✓ → Merge → branch slettes ◄──────────┘
```

**En god PR:**

- er liten og handler om én ting,
- har en beskrivelse: hva, hvorfor, hvordan testet,
- refererer til en issue (`Closes #42` lukker issue 42 automatisk ved merge),
- har grønne tester.

**Merge-metoder på GitHub:**

- *Create a merge commit* – beholder alle commits pluss en merge commit.
- *Squash and merge* – slår alle commits i PR-en sammen til én. Gir ren historikk; svært vanlig.
- *Rebase and merge* – legger commitene rett på main uten merge commit.

**Branch protection / rulesets.** I profesjonelle repoer beskyttes `main`: ingen kan pushe direkte, PR krever godkjenning og grønne tester. Dette settes opp under *Settings → Rules* (rulesets) eller *Branches* i GitHub.

## Angre ting i Git

| Situasjon | Kommando |
|---|---|
| Forkast endringer i en fil (ikke staget) | `git restore fil.txt` |
| Ta en fil ut av staging | `git restore --staged fil.txt` |
| Endre siste commit-melding (ikke pushet) | `git commit --amend` |
| Angre en commit som er pushet (trygt) | `git revert <hash>` – lager en ny commit som gjør det motsatte |
| Flytt branchen tilbake (lokalt, farlig) | `git reset --hard <hash>` – forkaster alt etter |
| Legg arbeid til side midlertidig | `git stash` … `git stash pop` |
| Finn tapte commits | `git reflog` |

> **Husk:** På delte brancher: bruk **`revert`**, ikke `reset`. `revert` legger til historikk; `reset` skriver den om.

## Git-arbeidsflyter (*workflows*)

### GitHub Flow (anbefalt for de fleste)

```text
 main ──●─────────●─────────●─────►  (alltid deploybar)
         \       /  \      /
          ●──●──●    ●──●─●         korte feature-brancher + PR
```

1. `main` er alltid i en tilstand som kan deployes.
2. Lag en kortlevd branch for hver endring.
3. Åpne PR, få review og grønne tester.
4. Merge til `main` → deploy automatisk.

### Trunk-based development

Alle integrerer til `main` (*trunken*) svært ofte – minst daglig – med svært kortlevde brancher eller direkte. Uferdige funksjoner skjules med **feature flags**. Brukes av mange høytytende team og henger tett sammen med Continuous Integration.

### Git Flow (eldre, mer kompleks)

Egne brancher for `develop`, `feature/*`, `release/*` og `hotfix/*`. Passer for produkter med planlagte, versjonerte utgivelser (f.eks. programvare som installeres hos kunder), men er ofte for tungt for webtjenester med kontinuerlig deploy.

> **Fra arbeidslivet:** De fleste moderne skyteam bruker GitHub Flow eller trunk-based. Hvis du får spørsmålet i intervju, vis at du kjenner forskjellen og hvorfor korte brancher reduserer konflikter og risiko.

### Navngivning av brancher

`feature/eksport-csv`, `fix/innlogging-timeout`, `docs/readme`, `chore/oppgrader-python`. Gjerne med issue-nummer: `feature/123-eksport-csv`.

### Tags og versjoner

```bash
$ git tag -a v1.2.0 -m "Versjon 1.2.0"
$ git push origin v1.2.0
```

**Semantisk versjonering** (*SemVer*): `MAJOR.MINOR.PATCH`. Øk MAJOR ved endringer som brekker kompatibilitet, MINOR ved ny funksjonalitet, PATCH ved feilrettinger.

## Samarbeid på GitHub

- **Issues** – oppgaver, feil og ideer. Kan tildeles, merkes og kobles til PR-er.
- **Projects** – kanban-tavler for planlegging.
- **README.md** – forsiden til repoet. Første inntrykk for arbeidsgivere!
- **CODEOWNERS** – bestemmer hvem som automatisk blir bedt om review for hvilke filer.
- **Forks** – din egen kopi av noen andres repo. Brukes for å bidra til open source.
- **Dependabot** – foreslår automatisk oppdateringer av avhengigheter og varsler om sårbarheter.
- **Secret scanning og code scanning** – finner lekkede hemmeligheter og sårbarheter.

## GitHub Actions – en første smakebit

**Hva er det?** GitHub Actions er GitHubs innebygde CI/CD-system. Du beskriver automatiske jobber i YAML-filer i mappen `.github/workflows/`. De kjøres på hendelser som `push` og `pull_request`.

```text
 hendelse (push/PR) ──► workflow ──► job(s) ──► steps
                                      │
                               kjører på en «runner»
                               (en VM hos GitHub eller din egen)
```

`.github/workflows/ci.yml`:

```yaml
name: CI                                  # navn som vises på GitHub

on:                                       # når skal workflowen kjøre?
  push:
    branches: [main]
  pull_request:                           # på alle pull requests

jobs:
  test:                                   # navnet på jobben
    runs-on: ubuntu-latest                # GitHub-hostet Linux-maskin
    steps:
      - uses: actions/checkout@v4         # hent koden (en ferdig "action")
      - uses: actions/setup-python@v5     # installer Python
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt   # kjør en kommando
      - run: pytest -q                          # feiler testene, blir jobben rød
```

Når du pusher, ser du resultatet under fanen **Actions** i repoet, og som en grønn ✓ eller rød ✗ på PR-en.

> **Kostnad:** GitHub Actions er gratis for offentlige repoer på GitHub-hostede standard-runnere. For private repoer følger det med et visst antall gratis minutter per måned avhengig av plan; over det betaler du. Sjekk «About billing for GitHub Actions» i GitHub Docs for gjeldende kvoter.

> **Merk om versjoner:** `@v4`/`@v5` viser til hovedversjoner av offisielle actions. Nye hovedversjoner kommer jevnlig (f.eks. har `actions/checkout` fått v5). Sjekk siden til hver action på GitHub Marketplace og bruk en aktivt vedlikeholdt versjon.

CI/CD med GitHub Actions blir gjennomgått i dybden i kapittel 12.

## Praktisk prosjekt: fra null til samarbeid

Dette prosjektet tar deg gjennom en komplett, realistisk arbeidsflyt. Tid: ca. 2 timer. Kostnad: gratis.

### Steg 1 – lag repoet

1. Logg inn på github.com → **New repository** → navn `devops-notater`, *Public*, huk av for **Add a README**, velg `.gitignore`-malen **Python** → **Create repository**.
2. Klon det:

```bash
$ git clone git@github.com:<brukernavn>/devops-notater.git
$ cd devops-notater
```

### Steg 2 – første funksjon på en branch

```bash
$ git switch -c feature/kommandoliste
$ mkdir -p notater
$ cat > notater/linux.md <<'EOF'
# Linux-kommandoer jeg kan
- `pwd` – vis hvor jeg er
- `ls -la` – list alle filer med detaljer
EOF
$ git add notater/linux.md
$ git commit -m "docs: legg til liste over Linux-kommandoer"
$ git push -u origin feature/kommandoliste
```

### Steg 3 – pull request

1. GitHub viser en gul boks: **Compare & pull request**. Klikk.
2. Skriv en beskrivelse: *Hva:* liste over Linux-kommandoer. *Hvorfor:* repetisjon til eksamen.
3. **Create pull request** → **Squash and merge** → **Delete branch**.

```bash
$ git switch main
$ git pull                       # hent den mergede endringen
$ git branch -d feature/kommandoliste
```

### Steg 4 – fremprovoser og løs en konflikt

```bash
# Branch A
$ git switch -c fix/tittel-a
$ sed -i 's/# Linux-kommandoer jeg kan/# Mine Linux-kommandoer/' notater/linux.md
$ git commit -am "docs: ny tittel (A)"
$ git switch main

# Branch B endrer samme linje
$ git switch -c fix/tittel-b
$ sed -i 's/# Linux-kommandoer jeg kan/# Linux – jukselapp/' notater/linux.md
$ git commit -am "docs: ny tittel (B)"

$ git switch main
$ git merge fix/tittel-a          # går fint (fast-forward)
$ git merge fix/tittel-b          # KONFLIKT
$ git status                      # viser filen med konflikt
```

Åpne `notater/linux.md`, velg tittelen du vil ha, fjern markørene, og:

```bash
$ git add notater/linux.md
$ git commit                      # godta foreslått melding
$ git push
```

(`git commit -am` = legg til alle *sporede* endrede filer og commit i ett.)

### Steg 5 – legg til CI

Lag `.github/workflows/lint.yml` som sjekker Markdown-filene:

```yaml
name: Lint
on: [push, pull_request]
jobs:
  markdown:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: DavidAnson/markdownlint-cli2-action@v20
        with:
          globs: "**/*.md"
```

Push via en branch og PR. Se jobben kjøre under *Actions*. Hvis den feiler, les loggen, fiks, og push igjen.

> **Merk:** Tredjeparts actions (som `DavidAnson/markdownlint-cli2-action`) har egne versjonsnumre. Sjekk siste versjon på GitHub Marketplace. I sikkerhetsbevisste team låser man tredjeparts actions til en **full commit-hash** i stedet for en tag.

### Steg 6 – beskytt main

*Settings → Rules → Rulesets → New branch ruleset*: mål `main`, krev pull request før merge, krev at statussjekken «Lint» er grønn. Prøv å pushe direkte til `main` – det blir nå avvist.

### Steg 7 – presentasjon

Skriv en god README: hva repoet er, hvordan det er organisert, og et merke (*badge*) som viser CI-status:

```markdown
![Lint](https://github.com/<brukernavn>/devops-notater/actions/workflows/lint.yml/badge.svg)
```

**På CV-en:** «Bruker Git og GitHub daglig med feature-brancher, pull requests, kodegjennomgang, beskyttede brancher og GitHub Actions.»

## Kapitteloppsummering

- Git er et lokalt versjonskontrollverktøy; GitHub er en nettjeneste for å dele og samarbeide om Git-repoer.
- Arbeidsmappe → `git add` → staging → `git commit` → historikk.
- Branches er billige parallelle linjer; merge slår dem sammen; konflikter løses manuelt.
- `clone`, `push`, `pull`, `fetch` synkroniserer med GitHub.
- Pull requests gir kodegjennomgang og automatiske tester før merge.
- Bruk `revert` på delte brancher; aldri `push --force` på `main`.
- GitHub Flow og trunk-based er vanligst i moderne team.
- GitHub Actions kjører automatiske workflows definert i YAML.

## Øvingsoppgaver

1. Lag et repo lokalt, gjør fem commits, og vis historikken med `git log --oneline --graph`.
2. Gjør en endring, stage den, og angre den med `git restore --staged` og `git restore`.
3. Lag en commit med en «feil», push den, og angre den trygt med `git revert`.
4. Bruk `git stash` for å bytte branch midt i arbeidet.
5. Fork et åpent prosjekt på GitHub, gjør en liten forbedring i dokumentasjonen på en branch, og åpne en PR mot din egen fork.
6. Legg til en workflow som kjører `pytest` på Python-koden fra kapittel 4.

## Quiz

1. Hva er forskjellen på Git og GitHub?
2. Hva er staging area?
3. Hva er en branch, teknisk sett?
4. Når oppstår en merge-konflikt?
5. Hva er forskjellen på `git fetch` og `git pull`?
6. Hvorfor bør du ikke bruke `git push --force` på `main`?
7. Du har committet et passord og pushet. Hva er det *første* du gjør?
8. Hva er forskjellen på `git revert` og `git reset --hard`?
9. Hva gjør `Closes #12` i en PR-beskrivelse?
10. Hvor ligger GitHub Actions-workflows i et repo?

### Fasit

1. **Git** er verktøyet for versjonskontroll som kjører lokalt. **GitHub** er en nettjeneste som lagrer Git-repoer og legger til samarbeid (PR-er, issues, Actions).
2. Et mellomområde der du samler endringene som skal være med i neste commit.
3. En lett, flyttbar peker til en commit.
4. Når to brancher har endret de samme linjene i samme fil (eller én har slettet en fil den andre endret), slik at Git ikke kan velge automatisk.
5. `fetch` henter nye data fra remote uten å endre dine filer. `pull` er `fetch` + `merge` (eller rebase) inn i branchen din.
6. Det overskriver historikken på remote og kan slette andres commits.
7. **Bytt (roter) passordet** umiddelbart. Rydd deretter i historikken og sett opp tiltak (secret scanning, `.gitignore`, hemmelighetshvelv).
8. `revert` lager en ny commit som opphever en tidligere – trygt på delte brancher. `reset --hard` flytter branchen tilbake og forkaster commits og endringer – skriver om historikken.
9. Lukker issue nummer 12 automatisk når PR-en merges til standardbranchen.
10. I `.github/workflows/` som `.yml`-filer.
