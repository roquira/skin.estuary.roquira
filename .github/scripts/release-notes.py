"""Print the changelog.txt entry of the given version."""

import sys
from pathlib import Path

version = sys.argv[1]
lines = (Path(__file__).resolve().parents[2] / "changelog.txt").read_text(encoding="utf-8").splitlines()

entry, inside = [], False
for line in lines:
    if line and not line.startswith(("-", " ")):
        if inside:
            break
        inside = line.split()[0] == version
        continue
    if inside:
        entry.append(line)

if not entry:
    sys.exit(f"changelog.txt has no entry for {version}")
print("\n".join(entry).strip())
