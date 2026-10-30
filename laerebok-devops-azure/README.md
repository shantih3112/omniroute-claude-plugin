# DevOps, Cloud & Microsoft Azure – Den komplette guiden fra nybegynner til profesjonell

Norsk lærebok (med engelske fagbegreper) for studenter i DevOps Engineering.

## Ferdige filer

| Fil | Beskrivelse |
|---|---|
| [`dist/DevOps-Cloud-Azure-Laerebok.pdf`](dist/DevOps-Cloud-Azure-Laerebok.pdf) | Hele boken som PDF (A4, ca. 360 sider) |
| [`dist/DevOps-Cloud-Azure-Laerebok.docx`](dist/DevOps-Cloud-Azure-Laerebok.docx) | Redigerbar Word-versjon |
| [`dist/DevOps-Cloud-Azure-Laerebok.html`](dist/DevOps-Cloud-Azure-Laerebok.html) | Én HTML-fil som kan åpnes i nettleseren |

## Innhold

Introduksjon og læringsplan · 1 IT fra bunnen · 2 Nettverk · 3 Linux · 4 Programmering (Python/Bash) ·
5 Git og GitHub · 6 Cloud Computing · 7 Microsoft Azure (7.1–7.4 tjenester, 7.5 AZ-900, 7.6 AZ-104 med prøveeksamener) ·
8 DevOps Engineering · 9 Docker · 10 Kubernetes · 11 Infrastructure as Code · 12 CI/CD · 13 Sikkerhet og monitoring ·
14 AI Infrastructure og MLOps · 15 Tolv praktiske prosjekter · Vedlegg A–E: ordliste, hurtigreferanser,
sertifiseringer, kilder og 12-måneders læringsplan.

## Bygge på nytt

Kildeteksten ligger i `kapitler/*.md` (Markdown). Krever `pandoc`, Node.js med Playwright/Chromium og `python-docx`:

```bash
./build.sh        # lager dist/*.html, dist/*.pdf og dist/*.docx
```

Informasjon om priser, tjenestenavn, eksamener og versjoner er skrevet ut fra offentlig dokumentasjon slik den var kjent
per oktober 2026. Sjekk alltid offisiell dokumentasjon (se vedlegg D) før du stoler på noe som kan endre seg.
