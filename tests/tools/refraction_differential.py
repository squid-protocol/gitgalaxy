"""
#3120: the differential between the refraction pipeline's own COBOL parsers
(gitgalaxy/tools/cobol_to_cobol/) and the engine's master DB (read through
gitgalaxy/tools/cobol_to_cobol/galaxy_ir.py).

Neither side is the oracle. A delta is a finding to EXPLAIN (old-parser defect,
engine defect, semantic difference, or stated absence), never a verdict that the
DB value is better. docs/refraction_engine_differential.md records the explained
run over the two cobol_corpus repos.

    python tests/tools/refraction_differential.py <repo> --db <repo>_galaxy_master.db \
        [--json out.json] [--md out.md]

Omit --db to scan <repo> first (galaxyscope --db-only into a temp dir).
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from gitgalaxy.tools.cobol_to_cobol.cobol_dag_architect import extract_lineage
from gitgalaxy.tools.cobol_to_cobol.cobol_graveyard_finder import (
    COPY_PATTERN,
    find_copybook,
    paragraph_headers,
    resolve_copybooks,
    x_ray_dead_code,
)
from gitgalaxy.tools.cobol_to_cobol.cobol_jcl_forge import analyze_cobol_intent
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import GalaxyIR, load_galaxy_ir, scan_to_db

# The graveyard does not return its paragraph list, only the count and the dead
# subset, so the harness calls the same helpers x_ray_dead_code uses.


def old_paragraphs(path: Path, repo: Path) -> set[str]:
    content = resolve_copybooks(path.read_text(encoding="utf-8", errors="ignore").upper(), path, repo)
    if "PROCEDURE DIVISION" not in content:
        return set()
    return set(paragraph_headers(content.split("PROCEDURE DIVISION", 1)[1]))


def old_copybooks(path: Path, repo: Path) -> tuple[set[str], dict[str, Path]]:
    """(named, resolved): COPY names in the source, and the member the graveyard
    inlines for each name it can resolve (searched under `repo`, as the refractor does)."""
    named = {m.group(1).upper() for m in COPY_PATTERN.finditer(path.read_text(encoding="utf-8", errors="ignore"))}
    resolved = {n: hit for n in named if (hit := find_copybook(n, repo, path)) is not None}
    return named, resolved


def compare(repo: Path, ir: GalaxyIR) -> list[dict[str, Any]]:
    rows = []
    for ef in ir.programs("cobol"):
        path = repo / ef.file_path
        intent = analyze_cobol_intent(path)
        graveyard = x_ray_dead_code(path, copybook_root=repo) or {}
        dead_old = set(graveyard.get("dead_paras", set()))
        lineage = extract_lineage(path, dead_paras=dead_old) or {}
        paras_old = old_paragraphs(path, repo)
        paras_new = {u.name.upper() for u in ef.units}
        copy_named, copy_old = old_copybooks(path, repo)
        copy_new = {Path(p).stem.upper() for p in ef.copy_deps}
        rows.append(
            {
                "file": ef.file_path,
                "program_id": {"old": intent["program_id"], "db": ef.program_ids},
                "paragraphs": {
                    "old_count": len(paras_old),
                    "db_count": len(paras_new),
                    "old_only": sorted(paras_old - paras_new),
                    "db_only": sorted(paras_new - paras_old),
                },
                "dead": {
                    "old": sorted(dead_old),
                    "db_usage_status_1": sorted(u.name for u in ef.units if u.usage_status == 1),
                },
                "copybooks": {
                    "named": sorted(copy_named),
                    "old_resolved": sorted(copy_old),
                    "db_edges": sorted(copy_new),
                },
                "subsystems": {
                    "old_cics": intent["cics_calls"],
                    "old_sql": intent["sql_calls"],
                    "db_signals": ef.signals,
                },
                # Stated absences: the DB carries no equivalent (see galaxy_ir.py SCOPE).
                "forge_only": {
                    "dd_files": sorted(f["dd_name"] for f in intent["files_requested"]),
                    "inputs": sorted(lineage.get("inputs", set())),
                    "outputs": sorted(lineage.get("outputs", set())),
                    "unresolved_calls": sorted(lineage.get("unresolved_calls", [])),
                    "orphaned_vars": len(graveyard.get("orphaned_vars", set())),
                },
            }
        )
    return rows


def summarize(ir: GalaxyIR, rows: list[dict[str, Any]]) -> dict[str, Any]:
    def count(pred) -> int:
        return sum(1 for r in rows if pred(r))

    return {
        "repo": ir.repo_name,
        "commit": ir.commit_hash,
        "inventory": ir.inventory(),
        "cobol_programs": len(rows),
        "program_id_mismatch": count(lambda r: r["program_id"]["old"] not in r["program_id"]["db"]),
        "paragraph_set_differs": count(lambda r: r["paragraphs"]["old_only"] or r["paragraphs"]["db_only"]),
        "paragraphs_old_only": sum(len(r["paragraphs"]["old_only"]) for r in rows),
        "paragraphs_db_only": sum(len(r["paragraphs"]["db_only"]) for r in rows),
        "dead_old_total": sum(len(r["dead"]["old"]) for r in rows),
        "dead_db_total": sum(len(r["dead"]["db_usage_status_1"]) for r in rows),
        "dead_agree": sum(len(set(r["dead"]["old"]) & set(r["dead"]["db_usage_status_1"])) for r in rows),
        "copy_named": sum(len(r["copybooks"]["named"]) for r in rows),
        "copy_old_resolved": sum(len(r["copybooks"]["old_resolved"]) for r in rows),
        "copy_db_edges": sum(len(r["copybooks"]["db_edges"]) for r in rows),
        "cics_programs_old": count(lambda r: r["subsystems"]["old_cics"] > 0),
        "sql_programs_old": count(lambda r: r["subsystems"]["old_sql"] > 0),
        "programs_with_outputs_old": count(lambda r: r["forge_only"]["outputs"]),
        "programs_with_dd_old": count(lambda r: r["forge_only"]["dd_files"]),
    }


def to_markdown(summary: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    out = [f"## {summary['repo']} @ {summary['commit'][:8]}", "", "| metric | value |", "|---|---|"]
    out += [f"| {k} | {v} |" for k, v in summary.items() if k not in ("repo", "commit")]
    out += [
        "",
        "| file | PROGRAM-ID old / db | paras old / db (old-only, db-only) | dead old / db | COPY named / old / db | CICS/SQL old |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        p, d, c, s = r["paragraphs"], r["dead"], r["copybooks"], r["subsystems"]
        out.append(
            f"| {r['file']} | {r['program_id']['old']} / {','.join(r['program_id']['db'])} "
            f"| {p['old_count']} / {p['db_count']} ({len(p['old_only'])}, {len(p['db_only'])}) "
            f"| {len(d['old'])} / {len(d['db_usage_status_1'])} "
            f"| {len(c['named'])} / {len(c['old_resolved'])} / {len(c['db_edges'])} "
            f"| {s['old_cics']}/{s['old_sql']} |"
        )
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo", type=Path)
    ap.add_argument("--db", type=Path, help="existing <repo>_galaxy_master.db (scans the repo if omitted)")
    ap.add_argument("--json", type=Path)
    ap.add_argument("--md", type=Path)
    args = ap.parse_args()

    repo = args.repo.resolve()
    if args.db:
        ir = load_galaxy_ir(args.db)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            ir = load_galaxy_ir(scan_to_db(repo, Path(tmp)))

    rows = compare(repo, ir)
    summary = summarize(ir, rows)
    if args.json:
        args.json.write_text(json.dumps({"summary": summary, "programs": rows}, indent=2), encoding="utf-8")
    md = to_markdown(summary, rows)
    if args.md:
        args.md.write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
