"""Assemble indicator and strategy from one shared core so their logic cannot drift."""
from pathlib import Path
root = Path(__file__).parent
core = (root / "src/core.pine").read_text()
for name in ("indicator", "strategy"):
    out = (root / f"src/{name}_head.pine").read_text() + "\n" + core + (root / f"src/{name}_tail.pine").read_text()
    (root / f"build/{name}.pine").write_text(out)
    print(f"build/{name}.pine: {len(out.splitlines())} lines")
