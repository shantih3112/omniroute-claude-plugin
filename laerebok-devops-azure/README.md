# DevOps, Cloud & Microsoft Azure – Den komplette guiden fra nybegynner til profesjonell

Norsk lærebok (med engelske fagbegreper) for studenter i DevOps Engineering.

## Ferdige filer

Boken finnes i to utgaver med samme kapitler:

| Utgave | Filer | Passer når … |
|---|---|---|
| **Visuell utgave** (anbefalt å starte med) – ca. 145 sider, 329 illustrasjoner, kort tekst | [PDF](dist/DevOps-Cloud-Azure-Visuell.pdf) · [Word](dist/DevOps-Cloud-Azure-Visuell.docx) · [HTML](dist/DevOps-Cloud-Azure-Visuell.html) | du lærer best med bilder, diagrammer og stikkord |
| **Fullversjon** – ca. 360 sider med all tekst og kode | [PDF](dist/DevOps-Cloud-Azure-Fullversjon.pdf) · [Word](dist/DevOps-Cloud-Azure-Fullversjon.docx) · [HTML](dist/DevOps-Cloud-Azure-Fullversjon.html) | du vil slå opp detaljer, full kode og steg-for-steg-oppskrifter |

## Innhold

Introduksjon og læringsplan · 1 IT fra bunnen · 2 Nettverk · 3 Linux · 4 Programmering (Python/Bash) ·
5 Git og GitHub · 6 Cloud Computing · 7 Microsoft Azure (7.1–7.4 tjenester, 7.5 AZ-900, 7.6 AZ-104 med prøveeksamener) ·
8 DevOps Engineering · 9 Docker · 10 Kubernetes · 11 Infrastructure as Code · 12 CI/CD · 13 Sikkerhet og monitoring ·
14 AI Infrastructure og MLOps · 15 Tolv praktiske prosjekter · Vedlegg A–E: ordliste, hurtigreferanser,
sertifiseringer, kilder og 12-måneders læringsplan.

## Bygge på nytt

Kildene er Markdown: `visuell/*.md` (visuell utgave) og `kapitler/*.md` (fullversjon).
I den visuelle utgaven skrives illustrasjonene som små ```` ```vis ```` -blokker (YAML: kort, flyt, lag,
sammenligning, analogi, tidslinje …) eller ```` ```mermaid ````-diagrammer, og `build/viz/viz.py` gjør dem om til
bilder i `visuell/figurer/`. Krever `pandoc`, Node.js med Playwright/Chromium, `python-docx`, `pyyaml` og `Pillow`
(første gang: `cd build/viz && npm install`):

```bash
./build.sh        # lager dist/*.html, dist/*.pdf og dist/*.docx
```

Informasjon om priser, tjenestenavn, eksamener og versjoner er skrevet ut fra offentlig dokumentasjon slik den var kjent
per oktober 2026. Sjekk alltid offisiell dokumentasjon (se vedlegg D) før du stoler på noe som kan endre seg.
