r"""The engine's side of the referee panel (#4377): a scanned corpus's master DB, read through
GalaxyIR plus the unit graph tests/tools/cobol_answer_key.py reads, as a referee-facts/1 document.

    python tests/tools/referees/engine_adapter.py --db <corpus>_galaxy_master.db --corpus <name> \
        --key tests/cobol_mainframe/answer_key/<name>.json --out facts/<name>/engine.json

The scan itself is `tests/tools/mainframe_corpus.py scan <name>` from the checkout under test.
Only the files the key covers are emitted (the key's programs and its keyed copybook layouts).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
for p in (str(REPO_ROOT), str(HERE.parent), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import cobol_answer_key as ak
import facts as F


def engine_version() -> str:
    """The engine checkout's HEAD (the scan is cached per engine commit, mainframe_corpus.py)."""
    out = subprocess.run(["git", "rev-parse", "--short=12", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True)
    return out.stdout.strip() or "unknown"


def _raw_imports(db: Path, repo_name: str, commit_hash: str) -> dict[str, set[str]]:
    """file -> every COPY / INCLUDE member the scan saw, resolved or not (file_data.raw_imports);
    GalaxyIR's copy_deps keeps only the resolved ones."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT file_path, raw_imports FROM file_data WHERE repo_name = ? AND commit_hash = ?", (repo_name, commit_hash)
        ).fetchall()
    finally:
        con.close()
    return {(p or "").replace("\\", "/"): {str(x).upper() for x in json.loads(raw or "[]")} for p, raw in rows}


def engine_doc(db: Path, corpus: str, key: dict[str, Any]) -> dict[str, Any]:
    from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir

    ir = load_galaxy_ir(db)
    graph = ak.engine_unit_graph(db, ir.repo_name, ir.commit_hash)
    access: dict[str, set[str]] = {}
    for row in ir.sql_table_access():
        access.setdefault(row["file"], set()).update(f"{a} {row['table']}" for a in row["accesses"])
    doc = F.new_doc("engine", engine_version(), corpus, F.CHANNELS)
    raw_imports = _raw_imports(db, ir.repo_name, ir.commit_hash)
    for rel, prog in key.get("programs", {}).items():
        ef = ir.files.get(rel)
        if ef is None:
            F.add_file(doc, rel, {}, status="fail", error="file not in the master DB")
            continue
        f: dict[str, set[str]] = {ch: set() for ch in F.CHANNELS if ch not in F.COPYBOOK_CHANNELS}
        f["program_ids"] = {p.upper() for p in ef.program_ids}
        units = graph.get(rel, [])
        call_names = {n.upper() for c in ef.calls for n in (c.operand, c.target) if n}
        f["unit_extents"] = ak.engine_unit_extents(prog, units)
        f["units"] = {ak.keyed_unit_name(prog, u["name"], u["start"]) for u in units if not u["synthetic"]}
        f["edges"] = ak.engine_unit_edges(prog, units, call_names)
        for c in ef.calls:
            if c.verb.upper() not in ("CALL", "LINK", "XCTL"):
                continue
            v = F.call_value(c.verb, c.form, c.operand)
            if v:
                f["calls"].add(v)
            if c.target:
                f["call_targets"].add(c.target.upper())
            if c.verb.upper() in ("LINK", "XCTL"):
                f["cics_commands"].add(f"L{c.line} {c.verb.upper()}")
        f["copybooks"] = raw_imports.get(rel, set())
        for it in ef.data_items:
            F.merge_item(f, F.item_values(it.line, it.level, it.name, it.pic, it.usage, it.occurs_min,
                                          it.occurs_max, it.occurs_depending_on, it.redefines, it.value))  # fmt: skip
        f["sql_access"] = access.get(rel, set())
        for r in ef.cics_resources:
            f["cics_commands"].add(F.cics_command(r.line, r.verb))
            if r.kind == "FILE" and r.name:
                f["cics_files"].add(f"{F.cics_verb(r.verb)} {r.name.upper()}")
        for t in ef.cics_tasks:
            f["cics_commands"].add(F.cics_command(t.line, t.verb))
        F.add_file(doc, rel, f)  # per-member time is the scan's, recorded by score.py --engine-seconds
    for rel in key.get("copybook_layouts", {}):
        units = ak.engine_copybook_units(ir, rel)
        if units is None:
            F.add_file(doc, rel, {}, status="fail", error="copybook not in the master DB")
        else:
            F.add_file(doc, rel, {"layouts": units})
    return doc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--key", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    key = json.loads(args.key.read_text(encoding="utf-8"))
    F.dump(engine_doc(args.db, args.corpus, key), args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
