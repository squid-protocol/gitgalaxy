# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""`gitgalaxy change`: what did this change do? A diff-aware report for a reviewer.

    gitgalaxy change REPO [--rev REV] [--base REV] [--scan-db DB] [--base-db DB]

From the git diff alone: size by role (source / tests-docs / ci-config), the lines that are repeated renames (one call name swapped for another, 5 or
more times: skim these), and the TODO/FIXME/HACK/XXX markers the change added and removed. With `--scan-db` (a scan of the tree at REV): the functions the
change touched and who calls them. With `--base-db` as well (a scan of the base): which libraries' coupling moved.

Read-only: runs `git diff`, opens the scan databases immutable. Validation of the repeated-rename rule: temporal-crucible `docs/sensor-overhaul/sensors/change_aware.md`.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import subprocess
import sys
from pathlib import Path

from gitgalaxy.core.source_text import decode_bytes
from gitgalaxy.tools.sensors import libsurface, reach

MIN_REPEAT = 5  # a swap seen this often in one change is reported as a repeated rename
_CALL = re.compile(r"([A-Za-z_]\w*)\s*\(")
# a language keyword or C type before a parenthesis is a statement or a declarator, not a call
_NOT_CALLS = frozenset(
    [
        "if",
        "while",
        "for",
        "switch",
        "sizeof",
        "return",
        "defined",
        "int",
        "char",
        "void",
        "long",
        "short",
        "unsigned",
        "signed",
        "float",
        "double",
        "struct",
        "enum",
        "union",
        "const",
        "static",
        "extern",
        "volatile",
        "bool",
        "typeof",
    ]
)
_COMMENT = ("//", "*", "/*", "--")  # a comment names functions in prose; renaming one there is not a code edit
_MARKER = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b")
_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def _git(repo: Path, *args: str) -> str:
    out = subprocess.run(  # noqa: S603
        ["git", "-C", str(repo), *args],  # noqa: S607
        capture_output=True,
        check=False,
    )
    if out.returncode:
        raise RuntimeError(decode_bytes(out.stderr).strip() or f"git {' '.join(args)} failed")
    return decode_bytes(out.stdout)


def parse_diff(
    text: str,
) -> tuple[dict[str, list[int]], list[tuple[str, list[str], list[str]]], dict[str, list[tuple[int, int]]]]:
    """Per-file [added, removed] counts, hunks as (path, removed lines, added lines), and each file's new-side line ranges."""
    files: dict[str, list[int]] = {}
    hunks: list[tuple[str, list[str], list[str]]] = []
    ranges: dict[str, list[tuple[int, int]]] = collections.defaultdict(list)
    cur: str | None = None
    for line in text.splitlines():
        if line.startswith("+++ b/"):
            cur = line[6:]
            files.setdefault(cur, [0, 0])
        elif line.startswith("+++ "):
            cur = None
        elif cur and (m := _HUNK.match(line)):
            start, count = int(m.group(1)), int(m.group(2)) if m.group(2) is not None else 1
            ranges[cur].append((start, max(count, 1)))
            hunks.append((cur, [], []))
        elif cur and hunks and line.startswith("+") and not line.startswith("+++"):
            files[cur][0] += 1
            hunks[-1][2].append(line[1:])
        elif cur and hunks and line.startswith("-") and not line.startswith("---"):
            files[cur][1] += 1
            hunks[-1][1].append(line[1:])
    return files, hunks, dict(ranges)


def _calls(line: str) -> set[str]:
    return {c for c in _CALL.findall(line) if c not in _NOT_CALLS}


def repeated_renames(
    hunks: list[tuple[str, list[str], list[str]]], min_repeat: int = MIN_REPEAT
) -> dict[tuple[str, str], int]:
    """(old call, new call) pairs swapped line for line `min_repeat`+ times: in a hunk that removes and adds the same number of lines, a line pair where
    exactly one call name left and exactly one arrived."""
    counts: collections.Counter[tuple[str, str]] = collections.Counter()
    for _path, removed, added in hunks:
        if not removed or len(removed) != len(added):
            continue
        for old_line, new_line in zip(removed, added, strict=True):
            if old_line.lstrip().startswith(_COMMENT) or new_line.lstrip().startswith(_COMMENT):
                continue
            gone = _calls(old_line) - _calls(new_line)
            came = _calls(new_line) - _calls(old_line)
            if len(gone) == 1 and len(came) == 1:
                counts[(next(iter(gone)), next(iter(came)))] += 1
    return {k: v for k, v in counts.items() if v >= min_repeat}


def markers(hunks: list[tuple[str, list[str], list[str]]], source: set[str]) -> dict[str, list[tuple[str, str]]]:
    """TODO/FIXME/HACK/XXX lines the change added and removed in source files, as (path, text). A marker line that only moved shows on both sides."""
    out: dict[str, list[tuple[str, str]]] = {"added": [], "removed": []}
    for path, removed, added in hunks:
        if path not in source:
            continue
        out["removed"] += [(path, x.strip()) for x in removed if _MARKER.search(x)]
        out["added"] += [(path, y.strip()) for y in added if _MARKER.search(y)]
    return out


def touched_functions(db: Path, ranges: dict[str, list[tuple[int, int]]]) -> list[dict]:
    """Functions whose line span overlaps a changed hunk (new side), with their caller counts. Needs a scan of the tree at REV."""
    con = reach.open_scan_db(db)
    try:
        rows = con.execute(
            "SELECT f.id, f.func_name, f.start_line, f.loc, fi.file_path FROM function_data f JOIN file_data fi ON fi.id = f.file_id"
        ).fetchall()
        edges = con.execute(
            "SELECT dst_func_id, src_func_id, src_file_id FROM fcall_data WHERE kind = 'call' AND dst_func_id IS NOT NULL"
        ).fetchall()
    finally:
        con.close()
    caller_fns: dict[int, set[int]] = collections.defaultdict(set)
    caller_files: dict[int, set[int]] = collections.defaultdict(set)
    for dst, src, src_file in edges:
        caller_fns[dst].add(src)
        caller_files[dst].add(src_file)
    out = []
    for fid, name, start, loc, path in rows:
        if not start or path not in ranges:
            continue
        end = start + max(loc or 1, 1) - 1
        if any(not (s + n - 1 < start or s > end) for s, n in ranges[path]):
            direct = caller_fns.get(fid, set())
            two: set[int] = set()
            for c in direct:
                two |= caller_fns.get(c, set())
            out.append(
                {
                    "function": name,
                    "file": path,
                    "caller_functions": len(direct),
                    "caller_files": len(caller_files.get(fid, ())),
                    "one_hop_out": len(two - direct - {fid}),
                }
            )
    return sorted(out, key=lambda r: (-r["caller_functions"], r["file"], r["function"]))


def surface_moves(base_db: Path, db: Path) -> list[dict]:
    """Libraries whose coupling changed between the base scan and this one."""
    libs = libsurface.load_libraries([])
    before, after = libsurface.build(base_db, libs).libraries, libsurface.build(db, libs).libraries
    moves = []
    for lib in sorted(set(before) | set(after)):
        ch = libsurface.change(before.get(lib, {}), after.get(lib, {}))
        if ch.names_added or ch.names_dropped or ch.files_newly_coupled or ch.files_no_longer_coupled:
            moves.append(
                {
                    "library": lib,
                    "files_before": ch.files_before,
                    "files_after": ch.files_after,
                    "sites_before": ch.sites_before,
                    "sites_after": ch.sites_after,
                    "names_added": ch.names_added,
                    "names_dropped": ch.names_dropped,
                    "files_newly_coupled": ch.files_newly_coupled,
                    "files_no_longer_coupled": ch.files_no_longer_coupled,
                }
            )
    return moves


def build_report(repo: Path, rev: str, base: str, scan_db: Path | None, base_db: Path | None) -> dict:
    files, hunks, ranges = parse_diff(_git(repo, "diff", "-U0", "--no-color", "-M", base, rev))
    roles: dict[str, dict[str, int]] = {}
    for path, (add, rem) in files.items():
        r = roles.setdefault(reach.role(path), {"files": 0, "lines": 0})
        r["files"] += 1
        r["lines"] += add + rem
    source = {p for p in files if reach.role(p) == "source"}
    total = sum(v["lines"] for v in roles.values())
    renames = repeated_renames(hunks)
    result: dict = {
        "rev": rev,
        "base": base,
        "files": len(files),
        "lines_changed": total,
        "roles": roles,
        "repeated_renames": [
            {"old": o, "new": n, "times": t} for (o, n), t in sorted(renames.items(), key=lambda kv: -kv[1])
        ],
        "lines_in_repeated_renames": sum(2 * t for t in renames.values()),
        "markers": markers(hunks, source),
    }
    if scan_db:
        result["touched_functions"] = touched_functions(scan_db, ranges)
    if scan_db and base_db:
        result["library_moves"] = surface_moves(base_db, scan_db)
    return result


def report(res: dict, top: int = 6) -> str:
    out = [f"CHANGE {res['base'][:10]}..{res['rev'][:10]}: {res['files']} files, {res['lines_changed']} lines changed"]
    out.append(
        "  " + "; ".join(f"{k}: {v['lines']} lines in {v['files']} files" for k, v in sorted(res["roles"].items()))
    )
    out.append("REPEATED RENAMES (one call swapped for another, 5 or more times; skim these)")
    if res["repeated_renames"]:
        out.extend(f"  {r['old']} -> {r['new']} x{r['times']}" for r in res["repeated_renames"][:top])
        out.append(
            f"  {res['lines_in_repeated_renames']} of the {res['lines_changed']} changed lines are in these swaps (not all of them are pure renames)"
        )
    else:
        out.append("  none")
    m = res["markers"]
    out.append("DEBT MARKERS (TODO/FIXME/HACK/XXX in source lines)")
    out.append(f"  added {len(m['added'])}, removed {len(m['removed'])}")
    for sign, key in (("+", "added"), ("-", "removed")):
        for path, text in m[key][:3]:
            out.append(f"    {sign} {path}: {text[:80]}")
    if "touched_functions" in res:
        t = res["touched_functions"]
        out.append(
            f"FUNCTIONS TOUCHED ({len(t)}), most-called first; one hop out = further functions that reach it through a caller"
        )
        out.extend(
            f"  {r['function']} ({r['file']}): {r['caller_functions']} caller functions in {r['caller_files']} files, {r['one_hop_out']} one hop out"
            for r in t[:top]
        )
        out.append("  Counts come from the scan you gave; a call the scan could not resolve is not counted.")
    if "library_moves" in res:
        mv = res["library_moves"]
        out.append(f"LIBRARY COUPLING THAT MOVED ({len(mv)})")
        out.extend(
            f"  {r['library']}: files {r['files_before']} -> {r['files_after']}, sites {r['sites_before']} -> {r['sites_after']}, "
            f"API names +{len(r['names_added'])} -{len(r['names_dropped'])}"
            for r in mv[:top]
        )
    return "\n".join(out)


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("repo", type=Path, help="a git repository")
    p.add_argument("--rev", default="HEAD", help="the change to report on (default HEAD)")
    p.add_argument("--base", help="what to compare against (default: the parent of REV)")
    p.add_argument(
        "--scan-db", type=Path, help="a scan of the tree at REV: adds the functions touched and who calls them"
    )
    p.add_argument(
        "--base-db", type=Path, help="a scan of the base (needs --scan-db): adds the library coupling that moved"
    )
    p.add_argument("--top", type=int, default=6)
    p.add_argument("--json", type=Path, metavar="FILE", help="also write the full result as JSON")


def run(args: argparse.Namespace) -> int:
    if args.base_db and not args.scan_db:
        print("gitgalaxy change: --base-db needs --scan-db", file=sys.stderr)
        return 2
    for db in (args.scan_db, args.base_db):
        if db and not db.is_file():
            print(f"gitgalaxy change: no such database: {db}", file=sys.stderr)
            return 2
    try:
        rev = _git(args.repo, "rev-parse", args.rev).strip()
        base = _git(args.repo, "rev-parse", args.base or f"{rev}^").strip()
        res = build_report(args.repo, rev, base, args.scan_db, args.base_db)
    except (RuntimeError, OSError) as exc:
        print(f"gitgalaxy change: {exc}", file=sys.stderr)
        return 2
    print(report(res, args.top))
    if args.json:
        args.json.write_text(json.dumps(res, indent=1))
    return 0
