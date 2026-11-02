#!/usr/bin/env bash
# Bygger begge utgaver av læreboken til HTML, PDF og DOCX.
#   Visuell utgave:  visuell/*.md   (illustrasjoner rendres fra ```vis/```mermaid-blokker)
#   Fullversjon:     kapitler/*.md
set -euo pipefail
cd "$(dirname "$0")"
NODE_PATH="$(npm root -g)"; export NODE_PATH
python3 build/make_reference_docx.py build/reference.docx

bygg() {   # $1 = kildemappe, $2 = filnavn, $3 = forsidefil, $4 = undertittel
  local src="$1" name="$2" cover="$3"
  pandoc "$src"/*.md -f markdown -t html5 -s --toc --toc-depth=2 \
    --metadata pagetitle="DevOps, Cloud & Microsoft Azure" --metadata lang=nb \
    --include-before-body="$cover" --css=style.css --embed-resources --resource-path="$src:." \
    --highlight-style=tango -o "dist/$name.html"
  node build/pdf.js "$PWD/dist/$name.html" "dist/$name.pdf"
  pandoc build/title.yaml "$src"/*.md -f markdown -t docx --toc --toc-depth=2 \
    --metadata lang=nb --metadata subtitle="$4" --reference-doc=build/reference.docx \
    --resource-path="$src:." --highlight-style=tango -o "dist/$name.docx"
}

python3 build/viz/viz.py visuell build/visuell-md visuell/figurer
bygg build/visuell-md DevOps-Cloud-Azure-Visuell cover-visuell.html "Visuell utgave – lær med bilder"
bygg kapitler DevOps-Cloud-Azure-Fullversjon cover.html "Fullversjon – oppslagsverk med all tekst"
echo "Ferdig: dist/"
