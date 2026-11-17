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


_SIG_CALLERS = 5  # callers named under a function whose signature changed
_WHILE_HERE_LINES = (
    50  # source lines changed before the "while you are here" list is offered (exploratory rule, see the wiki page)
)
_BLAME_CAP = 40  # markers blamed per report


def _args_by_key(db: Path) -> dict[tuple[str, str], int]:
    """Parameter count of every function whose (file, name) is unique in the scan."""
    con = reach.open_scan_db(db)
    try:
        rows = con.execute(
            "SELECT fi.file_path, f.func_name, f.args FROM function_data f JOIN file_data fi ON fi.id = f.file_id"
        ).fetchall()
    finally:
        con.close()
    count = collections.Counter((p, n) for p, n, _ in rows)
    return {(p, n): int(a or 0) for p, n, a in rows if count[(p, n)] == 1}


def touched_functions(db: Path, ranges: dict[str, list[tuple[int, int]]], base_db: Path | None = None) -> list[dict]:
    """Functions whose line span overlaps a changed hunk (new side), with their callers. Needs a scan of the tree at REV.

    A function's signature counts as changed when its parameter count differs between the base scan and this one (needs `base_db`), or, without
    one, when a changed hunk covers the line the function starts on. Those come first, then the most-called."""
    con = reach.open_scan_db(db)
    try:
        rows = con.execute(
            "SELECT f.id, f.func_name, f.start_line, f.loc, fi.file_path, f.args FROM function_data f JOIN file_data fi ON fi.id = f.file_id"
        ).fetchall()
        edges = con.execute(
            "SELECT dst_func_id, src_func_id, src_file_id FROM fcall_data WHERE kind = 'call' AND dst_func_id IS NOT NULL"
        ).fetchall()
    finally:
        con.close()
    names = {r[0]: (r[1], r[4]) for r in rows}
    base_args = None
    now_args: dict[tuple[str, str], int] = {}
    if base_db is not None:
        base_args = _args_by_key(base_db)
        now_args = _args_by_key(db)
    caller_fns: dict[int, set[int]] = collections.defaultdict(set)
    caller_files: dict[int, set[int]] = collections.defaultdict(set)
    for dst, src, src_file in edges:
        caller_fns[dst].add(src)
        caller_files[dst].add(src_file)
    out = []
    for fid, name, start, loc, path, _args in rows:
        if not start or path not in ranges:
            continue
        end = start + max(loc or 1, 1) - 1
        if any(not (s + n - 1 < start or s > end) for s, n in ranges[path]):
            direct = caller_fns.get(fid, set())
            two: set[int] = set()
            for c in direct:
                two |= caller_fns.get(c, set())
            signature = None
            if base_args is not None:
                before, after = base_args.get((path, name)), now_args.get((path, name))
                if before is not None and after is not None and before != after:
                    signature = f"parameters {before} -> {after}"
            elif any(s <= start < s + max(n, 1) for s, n in ranges[path]):
                signature = "declaration line edited"
            callers = sorted({f"{names[c][0]} ({names[c][1]})" for c in direct if c in names})
            out.append(
                {
                    "function": name,
                    "file": path,
                    "caller_functions": len(direct),
                    "caller_files": len(caller_files.get(fid, ())),
                    "one_hop_out": len(two - direct - {fid}),
                    "signature_changed": signature,
                    "callers": callers[:_SIG_CALLERS] if signature else [],
                }
            )
    return sorted(out, key=lambda r: (r["signature_changed"] is None, -r["caller_functions"], r["file"], r["function"]))


def while_you_are_here(repo: Path, rev: str, db: Path, source_lines: int, files: set[str]) -> dict:
    """The open TODO / FIXME / HACK / XXX markers in the touched source files, oldest and this author's own first, when the change is large enough.

    Needs a scan of the tree at REV that recorded markers (`debt_marker`); age and author come from `git blame` of each marker's line at REV."""
    res: dict = {
        "offered": source_lines >= _WHILE_HERE_LINES,
        "source_lines": source_lines,
        "measured": True,
        "markers": [],
    }
    con = reach.open_scan_db(db)
    try:
        if con.execute("SELECT 1 FROM sqlite_master WHERE name = 'debt_marker'").fetchone() is None:
            res["measured"] = False
            return res
        if not res["offered"]:
            return res
        found = con.execute(
            "SELECT fi.file_path, m.line, m.class, m.text FROM debt_marker m JOIN file_data fi ON fi.id = m.file_id ORDER BY fi.file_path, m.line"
        ).fetchall()
    finally:
        con.close()
    found = [r for r in found if r[0] in files]
    res["open_markers"] = len(found)
    author = _git(repo, "show", "-s", "--format=%ae", rev).strip().lower()
    now = int(_git(repo, "show", "-s", "--format=%ct", rev).strip())
    out = []
    for path, line, cls, text in found[:_BLAME_CAP]:
        info = _git(repo, "blame", "--porcelain", "-L", f"{line},{line}", rev, "--", path).splitlines()
        sha = info[0].split()[0] if info else ""
        mail = next((x[12:].strip("<>").lower() for x in info if x.startswith("author-mail ")), "")
        when = next((int(x[12:]) for x in info if x.startswith("author-time ")), now)
        if sha.lstrip("^") == rev[: len(sha.lstrip("^"))]:
            continue  # written by this change
        out.append(
            {
                "file": path,
                "line": line,
                "class": cls,
                "text": text,
                "age_years": round((now - when) / (365.25 * 86400), 1),
                "by_author": mail == author,
            }
        )
    out.sort(key=lambda m: (not m["by_author"], -m["age_years"], m["file"], m["line"]))
    res["markers"] = out
    res["truncated"] = len(found) > _BLAME_CAP
    return res


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
        result["touched_functions"] = touched_functions(scan_db, ranges, base_db)
        source_lines = sum(sum(files[p]) for p in source)
        result["while_you_are_here"] = while_you_are_here(repo, rev, scan_db, source_lines, source)
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
        flagged = [r for r in t if r["signature_changed"]]
        out.append(
            f"FUNCTIONS TOUCHED ({len(t)}; {len(flagged)} with a changed signature first, then most-called); one hop out = further functions that reach it through a caller"
        )
        for r in t[:top]:
            mark = f"! {r['signature_changed']}; " if r["signature_changed"] else ""
            out.append(
                f"  {r['function']} ({r['file']}): {mark}{r['caller_functions']} caller functions in {r['caller_files']} files, {r['one_hop_out']} one hop out"
            )
            if r["callers"]:
                out.append("      callers to check: " + ", ".join(r["callers"]))
        if flagged:
            out.append(
                "  Callers are listed for a changed signature because that is where later fixes tended to land: in the study behind this order, fixes after a signature change"
                " were found in the callers about 1.2 times as often as in other functions of the same file, pooled over six repositories (exploratory; docs/wiki/08-26)."
            )
        out.append("  Counts come from the scan you gave; a call the scan could not resolve is not counted.")
    w = res.get("while_you_are_here")
    if w is not None:
        if not w["measured"]:
            out.append(
                "WHILE YOU ARE HERE: not measured (this scan recorded no debt markers; rescan with a current engine)"
            )
        elif not w["offered"]:
            out.append(
                f"WHILE YOU ARE HERE: not offered (source changes of {_WHILE_HERE_LINES}+ lines trigger it; this one has {w['source_lines']})"
            )
        else:
            out.append(
                f"WHILE YOU ARE HERE (source changes of {_WHILE_HERE_LINES}+ lines; {w.get('open_markers', 0)} open markers in the touched files, this author's and the oldest first)"
            )
            for m in w["markers"][:top]:
                who = ", written by this author" if m["by_author"] else ""
                out.append(
                    f"  {m['file']}:{m['line']} {m['class']} open {m['age_years']:.1f} y{who} | {m['text'][:80]}"
                )
            if not w["markers"]:
                out.append("  none left open by earlier changes")
            if w.get("truncated"):
                out.append(f"  (first {_BLAME_CAP} markers by file order were aged)")
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
        "--base-db",
        type=Path,
        help="a scan of the base (needs --scan-db): adds parameter-count changes and the library coupling that moved",
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
