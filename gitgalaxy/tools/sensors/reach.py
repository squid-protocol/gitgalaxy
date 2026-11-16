# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""`gitgalaxy reach SCAN_DB [--src ROOT]`: who depends on a file, from a finished scan.

    gitgalaxy reach SCAN_DB [--src ROOT] [--top N] [--all-roles] [--json FILE]

Reach is a count, not a score, and no risk claim: for a source file, the distinct other files and functions that call a
function it defines (and the callers of those callers, one hop out); for a header, the number of files that `#include` it
(call-based reach cannot see a header, so it is counted from the include strings the scan stored; `--src` re-reads them from the source instead); a file the call graph cannot see is reported as
not measured, with the reason. Counts are lower bounds: calls to names the scan cannot resolve (standard library,
macros) are not recorded, and only `call` edges that resolve to exactly one definition are counted (tie and ambiguous
edges are left out and their number is reported). The database is opened read-only; nothing is written except `--json`.
Research and validation: temporal-crucible `docs/sensor-overhaul/sensors/reach.md`.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import posixpath
import re
import sqlite3
import sys
from pathlib import Path, PurePosixPath

HEADER_SUFFIXES = (".h", ".hpp", ".hh", ".hxx")
_TEXT_SUFFIXES = (".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".hh", ".hxx")
_INCLUDE = re.compile(r'^\s*#\s*include\s*[<"]([^>"]+)[>"]', re.M)
CALL_GRAPH = "call graph"
INCLUDE_COUNT = "include count"
_ROLE_TESTS = re.compile(r"(^|/)(tests?|examples?|fuzz\w*|docs?|bench\w*)(/|$)")


def role(path: str) -> str:
    if _ROLE_TESTS.search(path):
        return "tests/docs"
    if path.startswith(".github/") or path.endswith((".yml", ".yaml")):
        return "ci/config"
    return "source"


def open_scan_db(db: str | Path) -> sqlite3.Connection:
    """Open a finished scan database read-only without leaving files behind.

    A plain read-only open of a database in WAL mode creates `-wal` and `-shm` files next to it, which a scan's documented output must not
    have and a user's database should not gain. With no `-wal` file beside it nothing is mid-write (the writer's last close removes it), so
    the database is opened `immutable`; with one, an ordinary read-only open sees the write-ahead log."""
    path = Path(db)
    immutable = "&immutable=1" if not Path(f"{path}-wal").exists() else ""
    return sqlite3.connect(f"file:{path}?mode=ro{immutable}", uri=True)


def _tokens(raw: str | None) -> list[str]:
    try:
        return [t for t in json.loads(raw or "[]") if isinstance(t, str)]
    except (ValueError, TypeError):
        return []


def _resolve_include(token: str, includer: str, headers: frozenset[str], by_name: dict[str, list[str]]) -> list[str]:
    """The header(s) an include names. C looks for a quoted include relative to the includer's own folder first, so that comes first
    (`../redismodule.h`, `sub/x.h`); then the include-path rules: `a/b.h` matches the header whose path ends with `a/b.h`, and a bare
    `b.h` prefers a header in the includer's folder, else the one sharing the longest path prefix."""
    near = posixpath.normpath(posixpath.join(posixpath.dirname(includer), token))
    if near in headers:
        return [near]
    cands = by_name.get(PurePosixPath(token).name, [])
    if not cands:
        return []
    pick = [c for c in cands if c.endswith("/" + token) or c == token] if "/" in token else []
    if not pick:
        here = str(PurePosixPath(includer).parent)
        pick = [c for c in cands if str(PurePosixPath(c).parent) == here] or cands
        if len(pick) > 1:
            best = max(len(os.path.commonpath([includer, c])) for c in pick)
            pick = [c for c in pick if len(os.path.commonpath([includer, c])) == best][:1]
    return pick


def _count_includes(paths: list[str], tokens_of) -> dict[str, set[str]]:
    """Header path -> the files that include it, given a function that yields an includer's include strings."""
    headers = frozenset(p for p in paths if p.endswith(HEADER_SUFFIXES))
    by_name: dict[str, list[str]] = collections.defaultdict(list)
    for h in sorted(headers):
        by_name[PurePosixPath(h).name].append(h)
    out: dict[str, set[str]] = collections.defaultdict(set)
    for p in paths:
        if not p.endswith(_TEXT_SUFFIXES):
            continue
        for token in tokens_of(p):
            for h in _resolve_include(token, p, headers, by_name):
                if h != p:
                    out[h].add(p)
    return out


def include_counts(src_root: Path, paths: list[str]) -> dict[str, set[str]]:
    """Header path -> the files that include it, reading the `#include` lines from the source tree."""

    def tokens_of(p: str) -> list[str]:
        try:
            return _INCLUDE.findall((src_root / p).read_text("utf8", "replace"))
        except OSError:
            return []

    return _count_includes(paths, tokens_of)


def include_counts_from_imports(imports: dict[str, list[str]]) -> dict[str, set[str]]:
    """Header path -> the files that include it, from the include strings the scan already stored (`file_data.raw_imports`): no source tree needed."""
    return _count_includes(list(imports), lambda p: imports.get(p, ()))


def build(db: str | Path, src_root: Path | None = None) -> dict:
    con = open_scan_db(db)
    try:
        rows_fd = con.execute("SELECT id, file_path, function_count, raw_imports FROM file_data").fetchall()
        files = {r[0]: r[1:3] for r in rows_fd}
        stored = {r[1]: _tokens(r[3]) for r in rows_fd}
        funcs = {r[0]: r[1:] for r in con.execute("SELECT id, file_id, func_name, is_public FROM function_data")}
        # one-definition call edges only: a tie has no destination, an ambiguous edge (candidates > 1) is a guess
        edges = con.execute(
            "SELECT src_func_id, src_file_id, dst_func_id, dst_file_id FROM fcall_data "
            "WHERE kind = 'call' AND dst_func_id IS NOT NULL AND COALESCE(candidates, 1) <= 1"
        ).fetchall()
        left_out = con.execute(
            "SELECT COUNT(*) FROM fcall_data WHERE kind = 'call' AND (dst_func_id IS NULL OR COALESCE(candidates, 1) > 1)"
        ).fetchone()[0]
        has_candidates = (
            con.execute("SELECT 1 FROM sqlite_master WHERE name = 'fcall_candidates'").fetchone() is not None
        )
        # a tie keeps every candidate definition here (#8161), and an ambiguous edge names the file the resolver chose among
        # several: both are possible callers, not counted ones
        candidate_pairs = (
            con.execute(
                "SELECT DISTINCT src_file_id, dst_file_id FROM fcall_candidates WHERE dst_file_id IS NOT NULL"
            ).fetchall()
            if has_candidates
            else []
        )
        candidate_pairs += con.execute(
            "SELECT DISTINCT src_file_id, dst_file_id FROM fcall_data "
            "WHERE kind = 'call' AND dst_file_id IS NOT NULL AND COALESCE(candidates, 1) > 1"
        ).fetchall()
    finally:
        con.close()
    callers: dict[int, set[int]] = collections.defaultdict(set)
    caller_files: dict[int, set[int]] = collections.defaultdict(set)
    file_callers: dict[int, set[int]] = collections.defaultdict(set)
    file_caller_files: dict[int, set[int]] = collections.defaultdict(set)
    for src_fn, src_file, dst_fn, dst_file in edges:
        # a call from a file's top-level code has no calling function: it is a caller FILE but not a caller function
        caller_files[dst_fn].add(src_file)
        if src_fn is not None:
            callers[dst_fn].add(src_fn)
        if src_file != dst_file:
            file_caller_files[dst_file].add(src_file)
            if src_fn is not None:
                file_callers[dst_file].add(src_fn)
    possible: dict[int, set[int]] = collections.defaultdict(set)
    for src_file, dst_file in candidate_pairs:
        if src_file != dst_file and src_file not in file_caller_files.get(dst_file, ()):
            possible[dst_file].add(src_file)
    by_file: dict[int, list[int]] = collections.defaultdict(list)
    for fid, (file_id, _name, _pub) in funcs.items():
        by_file[file_id].append(fid)
    paths = [v[0] for v in files.values()]
    incl = include_counts(src_root, paths) if src_root else include_counts_from_imports(stored)
    rows: list[dict] = []
    not_measured: list[dict] = []
    for file_id, (path, fcount) in files.items():
        if path.endswith(HEADER_SUFFIXES):
            rows.append(
                {
                    "path": path,
                    "kind": "header",
                    "role": role(path),
                    "reach_files": len(incl.get(path, ())),
                    "measured_by": INCLUDE_COUNT,
                }
            )
        elif fcount:
            two: set[int] = set()
            for fn in by_file.get(file_id, ()):
                for c in callers.get(fn, ()):
                    two |= callers.get(c, set())
            rows.append(
                {
                    "path": path,
                    "kind": "source",
                    "role": role(path),
                    "reach_files": len(file_caller_files.get(file_id, ())),
                    "caller_functions": len(file_callers.get(file_id, ())),
                    "one_hop_out": len(two),
                    "possible_caller_files": len(possible.get(file_id, ())),
                    "measured_by": CALL_GRAPH,
                }
            )
        else:
            not_measured.append({"path": path, "reason": "no functions found"})
    public = [
        {"function": name, "path": files[file_id][0], "called_from_files": n}
        for fid, (file_id, name, is_public) in funcs.items()
        if is_public and (n := len(caller_files.get(fid, set()) - {file_id}))
    ]
    public.sort(key=lambda r: (-r["called_from_files"], r["path"], r["function"]))
    return {
        "files": len(files),
        "rows": rows,
        "not_measured": not_measured,
        "public_functions": public,
        "edges_counted": len(edges),
        "edges_left_out": left_out,
    }


def scope(db: str | Path, name: str) -> dict:
    """Who calls `name`: the files and calling functions, whether the repository defines `name` (counted from `fcall_data`)
    or not (counted from `fcall_external`, when the scan wrote it). The scope of a rename or removal."""
    con = open_scan_db(db)
    try:
        defined = con.execute(
            "SELECT f.file_path, COUNT(DISTINCT c.src_func_id), COUNT(*) FROM fcall_data c "
            "JOIN function_data d ON d.id = c.dst_func_id JOIN file_data f ON f.id = c.src_file_id "
            "WHERE c.kind = 'call' AND COALESCE(c.candidates, 1) <= 1 AND d.func_name = ? GROUP BY f.file_path",
            (name,),
        ).fetchall()
        has_external = con.execute("SELECT 1 FROM sqlite_master WHERE name = 'fcall_external'").fetchone() is not None
        external = (
            con.execute(
                "SELECT f.file_path, e.callers FROM fcall_external e JOIN file_data f ON f.id = e.src_file_id WHERE e.callee = ?",
                (name,),
            ).fetchall()
            if has_external
            else []
        )
    finally:
        con.close()
    rows = [{"path": p, "callers": n, "defined_in_repository": True} for p, n, _ in defined]
    rows += [{"path": p, "callers": n, "defined_in_repository": False} for p, n in external]
    by_role = collections.Counter(role(r["path"]) for r in rows)
    return {
        "name": name,
        "files": len({r["path"] for r in rows}),
        "callers": sum(r["callers"] for r in rows),
        "by_role": dict(by_role),
        "rows": sorted(rows, key=lambda r: (-r["callers"], r["path"])),
        "external_recorded": has_external,
    }


def report_scope(result: dict, top: int = 8) -> str:
    kind = (
        "defined in the repository"
        if any(r["defined_in_repository"] for r in result["rows"])
        else "external to the repository"
    )
    lines = [
        f"SCOPE  {result['name']}: called from {result['files']} files by {result['callers']} functions ({kind}); by role: {result['by_role']}"
    ]
    if not result["rows"] and not result["external_recorded"]:
        lines.append(
            "  no calls found; this scan did not record external calls (fcall_external), so a name the repository does not define cannot be scoped"
        )
    lines += [f"  {r['path']:56s} {r['callers']:4d} callers" for r in result["rows"][:top]]
    lines.append("Counts are lower bounds: only calls the scan resolved or recorded are counted.")
    return "\n".join(lines)


def report(result: dict, top: int = 8, all_roles: bool = False, rank_with_possible: bool = False) -> str:
    rows = [r for r in result["rows"] if all_roles or r["role"] == "source"]

    def reach_key(r: dict) -> int:
        return r["reach_files"] + (r.get("possible_caller_files", 0) if rank_with_possible else 0)

    src = sorted((r for r in rows if r["kind"] == "source"), key=lambda r: (-reach_key(r), r["path"]))
    hdr = sorted((r for r in rows if r["kind"] == "header"), key=lambda r: (-r["reach_files"], r["path"]))
    n_calls = sum(1 for r in result["rows"] if r["measured_by"] == CALL_GRAPH)
    n_incl = sum(1 for r in result["rows"] if r["measured_by"] == INCLUDE_COUNT)
    lines = [
        (
            f"REACH  {result['files']} files: measured by call graph {n_calls}, by include count {n_incl}, "
            f"not measured {len(result['not_measured'])}."
        ),
        (
            "Counts are lower bounds: calls to standard-library names and macros are not recorded; "
            f"{result['edges_counted']} call edges counted, {result['edges_left_out']} tie or ambiguous edges not counted "
            "(their files show as possible callers)."
        ),
        "Files the most other files call into:",
    ]
    lines += [
        f"  {r['path']:48s} {r['reach_files']:4d} caller files {r['caller_functions']:5d} caller functions {r['one_hop_out']:5d} one hop out"
        + (f" (+{r['possible_caller_files']} possible)" if r["possible_caller_files"] else "")
        for r in src[:top]
    ]
    lines.append("Most-used public functions:")
    lines += [
        f"  {r['function']:34s} {r['path']:40s} {r['called_from_files']} files"
        for r in result["public_functions"][:top]
    ]
    if hdr:
        lines.append("Headers by number of files that include them:")
        lines += [f"  {r['path']:48s} {r['reach_files']:4d} files" for r in hdr[:top]]
    return "\n".join(lines)


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("db", help="the scan's *_galaxy_master.db")
    p.add_argument(
        "--src",
        type=Path,
        help="optional: read header includes from this source tree instead of the include strings stored in the scan",
    )
    p.add_argument("--top", type=int, default=8)
    p.add_argument(
        "--callee", metavar="NAME", help="scope a rename or removal: who calls NAME (defined in the repository or not)"
    )
    p.add_argument("--all-roles", action="store_true", help="include tests/docs and CI/config files in the lists")
    p.add_argument(
        "--rank-with-possible",
        action="store_true",
        help="rank files by counted plus possible caller files (ambiguous and tied calls): ranks C repositories better, other languages mixed",
    )
    p.add_argument("--json", type=Path, metavar="FILE", help="also write the full result as JSON")


def run(args: argparse.Namespace) -> int:
    if not Path(args.db).is_file():
        print(f"gitgalaxy reach: no such database: {args.db}", file=sys.stderr)
        return 2
    if args.callee:
        try:
            scoped = scope(args.db, args.callee)
        except sqlite3.Error as exc:
            print(f"gitgalaxy reach: cannot read {args.db}: {exc}", file=sys.stderr)
            return 2
        print(report_scope(scoped, args.top))
        if args.json:
            args.json.write_text(json.dumps(scoped, indent=1))
        return 0
    try:
        result = build(args.db, args.src)
    except sqlite3.Error as exc:
        print(f"gitgalaxy reach: cannot read {args.db}: {exc}", file=sys.stderr)
        return 2
    print(report(result, args.top, args.all_roles, args.rank_with_possible))
    if args.json:
        args.json.write_text(json.dumps(result, indent=1))
    return 0
