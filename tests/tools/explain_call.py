"""
Explain one function's call links: which rung each callee took, which candidates
it had, and why the others lost (#3776, epic #3772).

Diagnosing a wrong or missing link used to mean re-deriving
core/call_resolver.py's ladder from source. This re-runs the real resolver on
the scan's own inputs -- the per-file functions the master DB holds (restored by
the state rehydrator, as a delta scan does) and its import edges -- so the
answer is the resolver's, not a re-implementation. It first checks that re-run
against the DB's recorded fcall rows for the caller, then shows per callee:

  - the step, target and qualifier the resolver chose (and whether the scan agrees);
  - every qualifier the function recorded for the name, and each one's own result;
  - every definition of the name in the link group: path:line, owner, def_shape,
    and whether a bare call (`free`) or a receiver (`methods`) can reach it;
  - definitions the resolver never indexes (bodyless signatures, #3757);
  - whether the caller's file imports each candidate's file (barrel re-exports included).

    python tests/tools/explain_call.py <master.db> <file>:<function> [<callee>]
    python tests/tools/explain_call.py <repo dir>  <file>:<function> [<callee>]   # scans first

<file> may be any unique suffix of the repo-relative path; <function> may carry
`@<line>` when the name repeats in the file.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO_ROOT = TOOLS.parents[1]
sys.path.insert(0, str(REPO_ROOT))

from gitgalaxy.core import call_resolver as cr  # noqa: E402
from gitgalaxy.core.state_rehydrator import StateRehydrator  # noqa: E402


def load_inputs(db: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]], str]:
    """(parsed files, import edges, repo name) exactly as a delta scan restores them."""
    conn = sqlite3.connect(db)
    try:
        repo = conn.execute("SELECT repo_name FROM file_data LIMIT 1").fetchone()[0]
        edges = [
            {"src": s, "dst": d, "edge_kind": "import"}
            for s, d in conn.execute(
                "SELECT sf.file_path, df.file_path FROM edge_data e "
                "JOIN file_data sf ON sf.id = e.src_file_id JOIN file_data df ON df.id = e.dst_file_id "
                "WHERE e.edge_kind = 'import'"
            )
        ]
    finally:
        conn.close()
    with contextlib.redirect_stdout(io.StringIO()):  # the rehydrator announces itself
        state = StateRehydrator(str(db)).load_state(repo)
    if not state:
        raise SystemExit(f"explain_call: {db} holds no restorable state for {repo}")
    parsed = list(state["ram_cache"].values())
    # A fresh scan hands the resolver each class's parents as `inheritance`; the
    # rehydrator restores only the DB column `inheritance_parents` (a JSON string),
    # so a delta scan loses every inherited-method link (#3786). Restore the
    # fresh-scan shape, so this explains what a scan resolves.
    for f in parsed:
        for cls in f.get("classes") or []:
            if "inheritance" not in cls and cls.get("inheritance_parents"):
                with contextlib.suppress(TypeError, ValueError):
                    cls["inheritance"] = json.loads(cls["inheritance_parents"])
    return parsed, edges, repo


def recorded_rows(db: Path, path: str, name: str, line: int) -> dict[str, tuple]:
    """callee -> (step, dst path, dst name, dst line) as the scan recorded it."""
    conn = sqlite3.connect(db)
    try:
        rows = conn.execute(
            "SELECT c.callee, c.step, dfd.file_path, dfn.func_name, dfn.start_line "
            "FROM fcall_data c JOIN function_data sfn ON sfn.id = c.src_func_id "
            "JOIN file_data sfd ON sfd.id = sfn.file_id "
            "LEFT JOIN function_data dfn ON dfn.id = c.dst_func_id "
            "LEFT JOIN file_data dfd ON dfd.id = dfn.file_id "
            "WHERE sfd.file_path = ? AND sfn.func_name = ? AND sfn.start_line = ? "
            "AND (c.kind IS NULL OR c.kind = 'call')",
            (path, name, line),
        ).fetchall()
    finally:
        conn.close()
    return {r[0]: r[1:] for r in rows}


def find_caller(parsed: list[dict[str, Any]], spec: str) -> tuple[dict[str, Any], dict[str, Any]]:
    file_part, _, func_part = spec.rpartition(":")
    name, _, want_line = func_part.partition("@")
    files = [f for f in parsed if f.get("path", "").endswith(file_part)]
    if len(files) != 1:
        raise SystemExit(f"explain_call: {file_part!r} matches {len(files)} files -- give more of the path")
    funcs = [
        fn
        for fn in files[0].get("functions") or []
        if str(fn.get("name")) == name and (not want_line or int(fn.get("start_line", 0)) == int(want_line))
    ]
    if len(funcs) != 1:
        lines = sorted(int(fn.get("start_line", 0)) for fn in files[0].get("functions") or [] if fn.get("name") == name)
        raise SystemExit(f"explain_call: {name!r} in {files[0]['path']} matches lines {lines} -- add @<line>")
    return files[0], funcs[0]


def explain(db: Path, spec: str, only: str | None = None) -> str:
    parsed, edges, repo = load_inputs(db)
    f, func = find_caller(parsed, spec)
    path, lang = f["path"], str(f.get("lang_id", "")).lower()
    name, line = str(func.get("name")), int(func.get("start_line", 0))
    group = cr._group(lang)

    sites, _ = cr.resolve_calls(parsed, edges)
    mine = {s["callee"]: s for s in sites if s["src_path"] == path and s["src_line"] == line and s["kind"] == "call"}
    scanned = recorded_rows(db, path, name, line)
    index = cr._index(parsed)
    imports = cr._with_reexports(cr._imports_by_file(edges)).get(path, set())
    quals = func.get("calls_out_qualifiers") or {}  # already decoded by the rehydrator
    signatures: dict[str, list[str]] = {}
    for pf in parsed:
        for fn in pf.get("functions") or []:
            if fn.get("def_shape") == "signature":
                signatures.setdefault(str(fn.get("name")), []).append(f"{pf['path']}:{fn.get('start_line')}")

    out = [f"{repo} :: {path}:{name}@{line} ({lang}), imports {len(imports)} files"]

    def target(s):  # a constructor call that reached a class has no function row
        return (s["step"], s["dst_path"], s["dst_line"]) if s["dst_kind"] == "function" else (s["step"], None, None)

    agree = all(
        target(s) == (scanned[c][0], scanned[c][1], scanned[c][3]) for c, s in mine.items() if c in scanned
    ) and set(scanned) <= set(mine)
    out.append(
        "  re-run matches the scan's recorded rows"
        if agree
        else "  WARNING: the re-run differs from the scan's recorded rows (the DB and this engine disagree)"
    )
    for callee in func.get("calls_out_to") or []:
        if only and callee != only:
            continue
        s = mine.get(callee)
        if s is None or s["dst_path"] is None:
            q = f"  qualifier {s['qualifier']!r}" if s else ""
            out.append(f"\n{callee}: none -- no definition this caller can reach (external){q}")
        else:
            out.append(
                f"\n{callee}: {s['step']} ({s['resolution']}) -> {s['dst_path']}:{s['dst_name']}@{s['dst_line']}"
                f"  qualifier {s['qualifier']!r}"
            )
        opts = quals.get(callee) or []
        out.append(f"  qualifiers recorded: {opts or ['(none captured)']}")
        bucket = index.get((group, cr._key(str(callee), lang)))
        if bucket is not None:
            free = {id(d) for d in bucket.free.defs}
            methods = {id(d) for d in bucket.methods.defs}
            for d in bucket.defs:
                reach = [w for w, ok in (("bare", id(d) in free), ("receiver", id(d) in methods)) if ok]
                out.append(
                    f"    {d.path}:{d.line} {d.name} owner={d.owner_key or '-'} shape={d.shape or '-'} kind={d.kind}"
                    f" reach={'+'.join(reach) or 'none'}"
                    f"{' same-file' if d.path == path else ''}{' imported' if d.path in imports else ''}"
                )
        out.extend(f"    {sig} (signature: never indexed, #3757)" for sig in signatures.get(str(callee), []))
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", type=Path, help="a *_master.db, or a repo directory to scan first")
    ap.add_argument("caller", help="<file>:<function>[@line]")
    ap.add_argument("callee", nargs="?")
    a = ap.parse_args(argv)
    db = a.source
    if db.is_dir():
        sys.path.insert(0, str(TOOLS))
        import call_graph_resolution as cgr

        db = cgr._scan(db)
    print(explain(db, a.caller, a.callee))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
