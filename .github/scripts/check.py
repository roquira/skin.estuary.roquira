"""Check that the add-on's XML parses and its Python compiles."""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

root = Path(__file__).resolve().parents[2]
errors = []

for path in sorted(root.rglob("*")):
    if ".git" in path.relative_to(root).parts or not path.is_file():
        continue
    relative = path.relative_to(root).as_posix()
    if path.suffix in (".xml", ".xsp"):
        try:
            ET.parse(path)
        except ET.ParseError as exc:
            errors.append(f"{relative}: {exc}")
    elif path.suffix == ".py":
        try:
            compile(path.read_text(encoding="utf-8"), relative, "exec")
        except SyntaxError as exc:
            errors.append(f"{relative}:{exc.lineno}: {exc.msg}")

addon = ET.parse(root / "addon.xml").getroot()
if addon.get("id") != "skin.estuary.roquira":
    errors.append(f"addon.xml: unexpected add-on id {addon.get('id')!r}")

for error in errors:
    print(error, file=sys.stderr)
print(f"Checked {addon.get('id')} {addon.get('version')}: {len(errors)} error(s)")
sys.exit(1 if errors else 0)
