"""Lager en reference.docx med lesbare fonter og sideskift før hvert hovedkapittel."""
import subprocess, sys
from docx import Document
from docx.shared import Pt, RGBColor

out = sys.argv[1]
with open(out, "wb") as f:
    f.write(subprocess.run(["pandoc", "--print-default-data-file", "reference.docx"],
                           capture_output=True, check=True).stdout)
doc = Document(out)
styles = doc.styles
def setfont(name, size=None, color=None, bold=None, font="Calibri"):
    s = next((st for st in styles if st.name and st.name.lower() == name.lower()), None)
    if s is None:
        return None
    s.font.name = font
    if size: s.font.size = Pt(size)
    if color: s.font.color.rgb = RGBColor.from_string(color)
    if bold is not None: s.font.bold = bold
    return s
for n in ["Normal", "Body Text", "First Paragraph", "Compact"]:
    setfont(n, 11)
h1 = setfont("Heading 1", 22, "0E1A2B", True)
h1.paragraph_format.page_break_before = True
setfont("Heading 2", 16, "0B5CAD", True)
setfont("Heading 3", 13, "1B2430", True)
setfont("Heading 4", 11.5, "5B6675", True)
setfont("Title", 30, "0B5CAD", True)
setfont("Subtitle", 16, "0F7B6C")
setfont("Source Code", 9, font="Consolas")
setfont("Verbatim Char", 9.5, font="Consolas")
bt = setfont("Block Text", 10.5, "0B3B70")
doc.save(out)
