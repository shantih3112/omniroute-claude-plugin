#!/usr/bin/env bash
# Bygger læreboken til HTML, PDF og DOCX fra kapitlene i kapitler/.
set -euo pipefail
cd "$(dirname "$0")"
CHAPTERS=(kapitler/*.md)
TITLE="DevOps, Cloud & Microsoft Azure – Den komplette guiden fra nybegynner til profesjonell"

pandoc "${CHAPTERS[@]}" -f markdown -t html5 -s --toc --toc-depth=2 \
  --metadata pagetitle="$TITLE" --metadata lang=nb \
  --include-before-body=cover.html --css=style.css --embed-resources \
  --highlight-style=tango -o dist/DevOps-Cloud-Azure-Laerebok.html

NODE_PATH="$(npm root -g)" node build/pdf.js "$PWD/dist/DevOps-Cloud-Azure-Laerebok.html" dist/DevOps-Cloud-Azure-Laerebok.pdf

python3 build/make_reference_docx.py build/reference.docx
pandoc build/title.yaml "${CHAPTERS[@]}" -f markdown -t docx --toc --toc-depth=2 \
  --metadata lang=nb --reference-doc=build/reference.docx --highlight-style=tango \
  -o dist/DevOps-Cloud-Azure-Laerebok.docx
echo "Ferdig: dist/"
