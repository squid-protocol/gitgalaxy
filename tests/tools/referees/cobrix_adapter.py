r"""Cobrix referee (#4377): copybook record layouts -- offsets and sizes -- from AbsaOSS/cobrix's
CopybookParser (Apache-2.0), as a referee-facts/1 document with the `layouts` channel.

    python tests/tools/referees/cobrix_adapter.py --corpus <name> --root <corpus clone> \
        --key tests/cobol_mainframe/answer_key/<name>.json --out facts/<name>/cobrix.json

Needs the environment variable COBRIX_CLASSPATH: the cobol-parser jar plus its runtime
dependencies, built outside this repository (README.md). The small Java driver
java/CobrixFacts.java is compiled on first use into $REFEREES_CACHE (default ~/.cache/gitgalaxy-referees).

The layout contract is the engine's and the key's (#3602): `ROOT/NAME @offset+bytes` per named
elementary item with a PICTURE, offsets relative to the 01; an item under a REDEFINES (or a root
that REDEFINES) is an overlay and left out; an item inside an OCCURS group is listed once, at its
first occurrence, its size covering its own OCCURS.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import facts as F

DRIVER = HERE / "java" / "CobrixFacts.java"


def cache_dir() -> Path:
    return Path(os.environ.get("REFEREES_CACHE") or Path.home() / ".cache" / "gitgalaxy-referees")


def classpath() -> str:
    cp = os.environ.get("COBRIX_CLASSPATH")
    if not cp:
        raise SystemExit("COBRIX_CLASSPATH is not set (see tests/tools/referees/README.md)")
    return cp


def compile_driver(cp: str) -> Path:
    out = cache_dir() / "cobrix-driver"
    cls = out / "CobrixFacts.class"
    if not cls.is_file() or cls.stat().st_mtime < DRIVER.stat().st_mtime:
        out.mkdir(parents=True, exist_ok=True)
        subprocess.run(["javac", "-d", str(out), "-cp", cp, str(DRIVER)], check=True)
    return out


def cobrix_version(cp: str) -> str:
    for part in cp.split(os.pathsep):
        name = Path(part).name
        if name.startswith("cobol-parser"):
            return name.removesuffix(".jar")
    return "unknown"


def layout_units(fields: list[dict[str, Any]]) -> set[str]:
    """The #3602 layout units of one Cobrix-parsed copybook (see the module docstring)."""
    out: set[str] = set()
    root_at: dict[str, int] = {}
    stack: list[tuple[int, bool]] = []  # (level, overlaid) of the open ancestors
    for f in fields:
        while stack and stack[-1][0] >= f["level"]:
            stack.pop()
        overlaid = bool(f.get("redefines")) or (bool(stack) and stack[-1][1])
        if f["level"] == 1 or not stack:
            root_at[f["root"]] = f["offset"]
        if f["group"]:
            stack.append((f["level"], overlaid))
            continue
        if overlaid or f.get("filler") or not f.get("pic") or f["name"].upper() == "FILLER":
            continue
        at = f["offset"] - root_at.get(f["root"], 0)
        out.add(f"{f['root'].upper()}/{f['name'].upper()} @{at}+{f['size']}")
    return out


def run(paths: list[Path], cp: str) -> list[dict[str, Any]]:
    driver = compile_driver(cp)
    proc = subprocess.run(
        ["java", "-cp", cp + os.pathsep + str(driver), "CobrixFacts"],
        input="\n".join(str(p) for p in paths) + "\n",
        capture_output=True,
        text=True,
        check=True,
    )
    return [json.loads(line) for line in proc.stdout.splitlines() if line.startswith("{")]


def cobrix_doc(corpus: str, root: Path, key: dict[str, Any]) -> dict[str, Any]:
    cp = classpath()
    rels = sorted(key.get("copybook_layouts", {}))
    t0 = time.perf_counter()
    rows = run([root / r for r in rels], cp)
    wall = time.perf_counter() - t0
    doc = F.new_doc("cobrix", cobrix_version(cp), corpus, ["layouts"])
    doc["wall_seconds"] = wall
    by_path = {Path(r["path"]).resolve(): r for r in rows}
    for rel in rels:
        r = by_path.get((root / rel).resolve())
        if r is None:
            F.add_file(doc, rel, {}, status="fail", error="no output from the driver")
        elif not r["ok"]:
            F.add_file(doc, rel, {}, status="fail", seconds=r["seconds"], error=r["error"])
        else:
            F.add_file(doc, rel, {"layouts": layout_units(r["fields"])}, seconds=r["seconds"])
    return doc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--key", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    key = json.loads(args.key.read_text(encoding="utf-8"))
    F.dump(cobrix_doc(args.corpus, args.root, key), args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
