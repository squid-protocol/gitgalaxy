"""Stamp the immutable ref + per-file sha256 of templates/requirements/*.txt into every template (#4918).

Each template install carries one marker line:
    GG_REF=<40-hex commit> GG_SHA256=<64-hex> # gg-pin:<core|yaml|full>
This rewrites every marker. REF defaults to the last commit that touched templates/requirements, so
commit regenerated lockfiles first, then run this, then commit the stamped templates.
Usage: stamp_template_pins.py [REF]
"""

import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQS = ROOT / "templates" / "requirements"
MARKER = re.compile(r"GG_REF=[0-9a-f]{40} GG_SHA256=[0-9a-f]{64} # gg-pin:(core|yaml|full)")


def targets():
    return [ROOT / "templates" / "scan.yml", *sorted((ROOT / "templates").glob("*/*.yml"))]


def main(argv):
    ref = (
        argv[1]
        if len(argv) > 1
        else subprocess.check_output(
            ["git", "log", "-1", "--format=%H", "--", "templates/requirements"], cwd=ROOT, text=True
        ).strip()
    )
    sha = {n: hashlib.sha256((REQS / f"{n}.txt").read_bytes()).hexdigest() for n in ("core", "yaml", "full")}
    for p in targets():
        text = p.read_text()
        new = MARKER.sub(lambda m: f"GG_REF={ref} GG_SHA256={sha[m.group(1)]} # gg-pin:{m.group(1)}", text)
        if new != text:
            p.write_text(new)
            print("stamped", p.relative_to(ROOT))


if __name__ == "__main__":
    main(sys.argv)
