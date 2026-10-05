r"""mapa referee (#4377): cschneid-the-elder/mapa's COBOL CallTree tool (MIT; ANTLR grammars for
IBM Z COBOL, CICS and DB2) as a referee-facts/1 document: PROGRAM-IDs, COPY / SQL INCLUDE members,
CALL / CICS LINK / XCTL targets, DB2 table access and EXEC CICS file-control commands.

    python tests/tools/referees/mapa_adapter.py --corpus <name> --root <corpus clone> \
        --key tests/cobol_mainframe/answer_key/<name>.json --out facts/<name>/mapa.json

Needs the environment variable MAPA_CALLTREE_JAR (mapa/cobol/CallTree.jar from a clone outside
this repository; README.md). The tool runs once per corpus over the key's programs, with every
directory of the corpus that holds a copybook on its copy list; mapa writes its CSV, a log and
temporary files into a scratch directory this adapter removes afterwards.

mapa reports a resolved identifier's program, not the identifier, so it feeds `call_targets` but
not `calls`. Its per-member time is the run's wall time divided by the members (one JVM).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import facts as F

JAR_ENV = "MAPA_CALLTREE_JAR"
COPY_EXTS = {".cpy", ".copy", ".dcl", ".cbl", ".cob", ".inc", ""}
_CICS_FILE = {"CICSREAD": "READ", "CICSWRITE": "WRITE", "CICSREWRITE": "REWRITE", "CICSDELETE": "DELETE",
              "CICSSTARTBR": "STARTBR", "CICSREADNEXT": "READNEXT", "CICSREADPREV": "READPREV"}  # fmt: skip
_CALL_TYPES = {"CALLBY": "CALL", "CICSLINKBY": "LINK", "CICSXCTLBY": "XCTL", "SQLCALLBY": "SQLCALL"}


def sql_access(kind: str) -> str:
    k = kind.lower()
    for word in ("insert", "update", "delete"):
        if word in k:
            return word
    return "read"


def mapa_version(jar: Path) -> str:
    repo = jar.resolve().parents[1]
    out = subprocess.run(["git", "rev-parse", "--short=12", "HEAD"], cwd=repo, capture_output=True, text=True)
    return out.stdout.strip() or jar.name


def parse_csv(text: str, root: Path) -> dict[str, dict[str, set[str]]]:
    """mapa's record stream -> {absolute file path: channel facts}."""
    files: dict[str, str] = {}
    prog_file: dict[str, str] = {}
    out: dict[str, dict[str, set[str]]] = {}

    def facts_of(path: str) -> dict[str, set[str]]:
        return out.setdefault(path, {"program_ids": set(), "copybooks": set(), "call_targets": set(),
                                     "sql_access": set(), "cics_files": set()})  # fmt: skip

    rows = [r for r in csv.reader(text.splitlines()) if r]
    for row in rows:  # first pass: files and programs (a program's PGM record follows its INCLUDEs)
        if row[0] == "FILE" and len(row) >= 3:
            files[row[1]] = row[2]
            facts_of(row[2])
    for row in rows:
        if row[0] in ("PGM", "FUNCTION", "CLASS") and len(row) >= 4 and row[2] in files:
            prog_file[row[1]] = files[row[2]]
            pid = row[3].strip().strip("'\"").upper()  # a literal PROGRAM-ID keeps its quotes in mapa's CSV
            facts = facts_of(files[row[2]])
            if pid:
                facts["program_ids"].add(pid)
    for row in rows:
        kind = row[0]
        if len(row) < 4:
            continue
        # the owner column is a file UUID for COPY / SQLINCLUDE and a program UUID otherwise
        # (mapa's README says program for SQLINCLUDE; its output says file)
        owner = files.get(row[2]) or prog_file.get(row[2])
        if owner is None:
            continue
        name = row[3].strip().upper()
        if kind in ("COPY", "SQLINCLUDE"):
            facts_of(owner)["copybooks"].add(name)
        elif kind == "CALL" and len(row) >= 6:
            facts_of(owner)["call_targets"].add(row[5].strip().upper())
        elif kind == "DB2TABLE" and len(row) >= 5:
            facts_of(owner)["sql_access"].add(f"{sql_access(row[4])} {name}")
        elif kind in _CICS_FILE:
            facts_of(owner)["cics_files"].add(f"{_CICS_FILE[kind]} {name}")
    return out


def copy_dirs(root: Path) -> list[Path]:
    dirs = set()
    for p in root.rglob("*"):
        if p.is_file() and ".git" not in p.parts and p.suffix.lower() in COPY_EXTS:
            dirs.add(p.parent)
    return sorted(dirs)


def run_calltree(jar: Path, paths: list[Path], libs: list[Path], root: Path) -> tuple[dict[str, dict[str, set[str]]], float, str]:
    """One CallTree run over `paths`: (facts by absolute path, wall seconds, error tail)."""
    scratch = os.environ.get("REFEREES_CACHE")
    if scratch:
        Path(scratch).mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="mapa-", dir=scratch))
    try:
        (work / "files").write_text("\n".join(str(p.resolve()) for p in paths) + "\n", encoding="utf-8")
        (work / "libs").write_text("\n".join(str(d.resolve()) for d in libs) + "\n", encoding="utf-8")
        t0 = time.perf_counter()
        proc = subprocess.run(
            ["java", "-jar", str(jar), "-fileList", "files", "-copyList", "libs", "-out", "out.csv"],
            cwd=work, capture_output=True, text=True,
        )  # fmt: skip
        wall = time.perf_counter() - t0
        csv_path = work / "out.csv"
        found = parse_csv(csv_path.read_text(encoding="utf-8"), root) if csv_path.is_file() else {}
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()
        err = f"exit {proc.returncode}: " + " | ".join(ln.strip() for ln in tail[:2])[:240] if proc.returncode else ""
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return found, wall, err


def mapa_doc(corpus: str, root: Path, key: dict[str, Any]) -> dict[str, Any]:
    jar = Path(os.environ.get(JAR_ENV) or "")
    if not jar.is_file():
        raise SystemExit(f"{JAR_ENV} does not name mapa's CallTree.jar (see tests/tools/referees/README.md)")
    rels = sorted(key.get("programs", {}))
    channels = ["program_ids", "copybooks", "call_targets", "sql_access", "cics_files"]
    doc = F.new_doc("mapa", mapa_version(jar), corpus, channels)
    libs = copy_dirs(root)
    found, wall, err = run_calltree(jar, [root / r for r in rels], libs, root)
    per = {rel: wall / max(len(rels), 1) for rel in rels}
    errors = dict.fromkeys(rels, err)
    if err and not found:
        # one member that crashes CallTree (an uncaught exception) aborts the whole run:
        # fall back to one run per member so the others still count
        found, wall = {}, 0.0
        for rel in rels:
            f1, w1, e1 = run_calltree(jar, [root / rel], libs, root)
            found.update(f1)
            per[rel], errors[rel] = w1, e1
            wall += w1
    doc["wall_seconds"] = wall
    for rel in rels:
        facts = found.get(str((root / rel).resolve()))
        if not facts or not facts["program_ids"]:
            F.add_file(doc, rel, {}, status="fail", seconds=per[rel], error=f"no PGM record ({errors[rel] or 'no error'})")
        else:
            F.add_file(doc, rel, facts, seconds=per[rel])
    return doc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--key", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    key = json.loads(args.key.read_text(encoding="utf-8"))
    F.dump(mapa_doc(args.corpus, args.root, key), args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
