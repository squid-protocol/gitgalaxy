#!/usr/bin/env python3
"""
Self-scan context pack: turn an issue into "read path:start-end" pointers.

A churn worker given only an issue number spends its first 5-14 requests grepping for the
code. The self-scan master DB (docs/self_scan/gitgalaxy_master.db, see self_scan.py) already
knows every function's file, start line, size and call edges, so this tool resolves the paths,
function names, class names and backticked identifiers an issue mentions against the DB and
prints a small Markdown block (default cap 3000 tokens) a worker brief can include verbatim.

USAGE
    python tests/tools/context_pack.py 5521                       # fetches the issue with gh
    python tests/tools/context_pack.py 5521 --body-file issue.md  # offline (title = first line)
    python tests/tools/context_pack.py 5521 --db other.db --max-tokens 1500
    python tests/tools/context_pack.py --eval 24                  # hit rate against merged PRs

--eval N measures the tool: for the newest N issues closed by a squash-merged PR on origin/main
("Part of #I" / "Closes #I" plus "(#PR)" in the subject) it builds the pack as it would have been
built before that PR (earlier-PR files come from commits strictly before it), then reports whether
the pack names the files the PR changed. "Source" files are hand-written code (tests included); docs, data and workflows are excluded. The DB is
the one you pass, so regenerate it at the commit under test (self_scan.py) for a fair number.

Nothing resolved -> prints nothing (exit 0). Line ranges are hints from the last scan: the
worker still reads the code. Files over BIG_FILE_TOKENS get "read only the named ranges".
"""

import argparse
import json
import re
import sqlite3
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = REPO_ROOT / "docs" / "self_scan" / "gitgalaxy_master.db"
ISSUE_API = "repos/squid-protocol/gitgalaxy/issues/{n}"

BIG_FILE_TOKENS = 8000  # same threshold as dev_agent_firewall
CHARS_PER_TOKEN = 4  # cheap estimate; the cap is a budget, not a measurement
MAX_AMBIGUOUS = 4  # a bare name defined in more places than this is noise unless a file is named
MAX_FUNCS = 12
MAX_EDGES = 3  # callers and callees shown per function
MAX_FILES = 8
MAX_PRIOR = 6  # files earlier PRs for the same issue changed (an epic's bodies name no code)
PRIOR_COMMITS = 30
MIN_NAME_LEN = 4  # shorter names (`fp`, `py`, `run`) match too much unrelated code
TEST_DEMOTION = 0.5  # a test file ranks below the source it exercises
# Directories whose file stems are language names: an issue saying "GLSL" points at glsl.py.
STEM_DIRS = ("gitgalaxy/standards/language_standards/languages/",)

_PATH_RE = re.compile(r"[A-Za-z0-9_.\-/]+\.[A-Za-z0-9]{1,6}\b")
_BACKTICK_RE = re.compile(r"`([^`\n]+)`")
_CALL_RE = re.compile(r"(?:[A-Za-z_][A-Za-z0-9_]*\.)*([A-Za-z_][A-Za-z0-9_]*)(?:\(\))?")
_PROSE_IDENT_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")


def _is_identifier_like(tok: str) -> bool:
    """snake_case with an underscore, or CamelCase/camelCase: safe to match without backticks."""
    return "_" in tok.strip("_") or bool(re.search(r"[a-z][A-Z]", tok))


def extract_mentions(title: str, body: str) -> tuple[Counter, Counter]:
    """Return (paths, names): mention counts of path-like tokens and identifier-like tokens."""
    text = f"{title}\n{body}"
    paths: Counter = Counter()
    names: Counter = Counter()
    for tok in _PATH_RE.findall(text):
        tok = tok.strip("./")
        if tok and "." in tok and not tok.replace(".", "").isdigit():
            paths[tok] += 1
    for span in _BACKTICK_RE.findall(text):
        # Only a span that is one (possibly dotted / called) identifier names a symbol; splitting
        # `.py` or `a/b.c` would turn extensions and directories into "names".
        m = _CALL_RE.fullmatch(span.strip())
        if m:
            names[m.group(1)] += 1
    for tok in _PROSE_IDENT_RE.findall(text):
        if _is_identifier_like(tok):
            names[tok] += 1
    return paths, Counter({n: c for n, c in names.items() if len(n) >= MIN_NAME_LEN})


def _file_hits(db: sqlite3.Connection, paths: Counter) -> dict[int, float]:
    """file id -> score for paths named in the issue (exact path, path suffix, or basename)."""
    hits: dict[int, float] = {}
    for tok, count in paths.items():
        rows = db.execute(
            "SELECT id FROM file_data WHERE file_path = ? OR file_path LIKE ? ESCAPE '\\'",
            (tok, "%/" + tok.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")),
        ).fetchall()
        if not rows and "/" not in tok:
            rows = db.execute("SELECT id FROM file_data WHERE file_name = ?", (tok,)).fetchall()
        if len(rows) > MAX_AMBIGUOUS:
            continue
        for (fid,) in rows:
            hits[fid] = hits.get(fid, 0.0) + 3.0 * count
    return hits


def _stem_hits(db: sqlite3.Connection, text: str) -> dict[int, float]:
    """file id -> score for files in STEM_DIRS whose stem is a word of the issue text."""
    words = {w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9_]{3,}", text)}
    hits: dict[int, float] = {}
    for prefix in STEM_DIRS:
        for fid, name in db.execute(
            "SELECT id, file_name FROM file_data WHERE file_path LIKE ? ESCAPE '\\'", (prefix + "%",)
        ):
            if name.rsplit(".", 1)[0].lower() in words:
                hits[fid] = 1.0
    return hits


def _symbol_hits(db: sqlite3.Connection, names: Counter, named_files: dict[int, float]):
    """Resolve names to functions and classes; returns (func rows, class rows) with scores."""
    funcs: dict[int, tuple[float, tuple]] = {}
    classes: dict[int, tuple[float, tuple]] = {}
    for name, count in names.items():
        frows = db.execute(
            "SELECT f.id, f.file_id, f.func_name, f.start_line, f.loc, f.complexity "
            "FROM function_data f WHERE f.func_name = ?",
            (name,),
        ).fetchall()
        crows = db.execute("SELECT id, file_id, class_name FROM class_data WHERE class_name = ?", (name,)).fetchall()
        for rows, store, weight in ((frows, funcs, 2.0), (crows, classes, 2.0)):
            in_named = [r for r in rows if r[1] in named_files]
            # A name defined all over the repo is only useful when the issue names the file.
            chosen = in_named or (rows if len(rows) <= MAX_AMBIGUOUS else [])
            for r in chosen:
                bonus = 2.0 if r[1] in named_files else 0.0
                score = weight * count / max(len(rows), 1) ** 0.5 + bonus
                prev = store.get(r[0])
                store[r[0]] = (max(score, prev[0]) if prev else score, r)
    return funcs, classes


def _file_info(db: sqlite3.Connection, fid: int) -> tuple:
    return db.execute(
        "SELECT file_path, total_loc, COALESCE(token_mass, 0) FROM file_data WHERE id = ?", (fid,)
    ).fetchone()


def _edges(db: sqlite3.Connection, func_id: int) -> tuple[list, list]:
    """One hop of resolved callers and callees as (path, name, start, end) tuples."""
    base = (
        "SELECT DISTINCT fd.file_path, f.func_name, f.start_line, f.loc FROM fcall_data c "
        "JOIN function_data f ON f.id = c.{far}_func_id "
        "JOIN file_data fd ON fd.id = f.file_id WHERE c.{near}_func_id = ? "
        "AND f.id != ? ORDER BY f.func_fan_in DESC LIMIT ?"
    )
    callers = db.execute(base.format(far="src", near="dst"), (func_id, func_id, MAX_EDGES)).fetchall()
    callees = db.execute(base.format(far="dst", near="src"), (func_id, func_id, MAX_EDGES)).fetchall()
    return callers, callees


def _span(path: str, start, loc) -> str:
    start = start or 1
    return f"{path}:{start}-{start + max((loc or 1) - 1, 0)}"


def _edge_text(rows: list) -> str:
    return ", ".join(f"`{n}` {_span(p, s, loc)}" for p, n, s, loc in rows)


def prior_files(issue: str, repo: Path = REPO_ROOT, before: str | None = None) -> list[str]:
    """Files changed by the newest commits whose message mentions `#<issue>`, most-touched first.

    `before` (a commit) limits the search to that commit's ancestors, excluding itself.
    """
    if not issue.isdigit():
        return []
    tip = f"{before}^" if before else "origin/main"
    try:
        out = subprocess.run(
            [
                "git",
                "log",
                tip,
                f"--grep=#{issue}([^0-9]|$)",  # POSIX ERE has no \\b (macOS)
                "-E",
                f"-n{PRIOR_COMMITS}",
                "--name-only",
                "--format=",
            ],
            capture_output=True,
            text=True,
            cwd=repo,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    return [p for p, _ in Counter(ln for ln in out.splitlines() if ln).most_common()]


def build_pack(
    db: sqlite3.Connection, title: str, body: str, max_tokens: int = 3000, prior: list[str] | None = None
) -> str:
    """Markdown pack for the issue text, or "" when nothing resolves."""
    paths, names = extract_mentions(title, body)
    named_files = _file_hits(db, paths)
    stem_files = _stem_hits(db, f"{title}\n{body}")
    funcs, classes = _symbol_hits(db, names, named_files)
    prior_hits = {fid: 0.0 for fid in _file_hits(db, Counter(prior or []))}
    if not (named_files or stem_files or funcs or classes or prior_hits):
        return ""

    file_scores: dict[int, float] = dict(named_files)
    for fid, score in stem_files.items():
        file_scores[fid] = file_scores.get(fid, 0.0) + score
    for score, r in list(funcs.values()) + list(classes.values()):
        file_scores[r[1]] = file_scores.get(r[1], 0.0) + score
    for fid in file_scores:
        if _file_info(db, fid)[0].startswith("tests/"):
            file_scores[fid] *= TEST_DEMOTION
    ranked_files = sorted(file_scores, key=lambda f: -file_scores[f])[:MAX_FILES]

    lines = ["## Where to look (self-scan; line ranges are hints from the last scan)", ""]
    for fid in ranked_files:
        path, loc, tokens = _file_info(db, fid)
        fan_in = db.execute("SELECT COUNT(*) FROM edge_data WHERE dst_file_id = ?", (fid,)).fetchone()[0]
        note = f", {tokens} tokens: BIG, read only the named ranges" if tokens > BIG_FILE_TOKENS else ""
        lines.append(f"- `{path}` ({loc} loc{note}; imported by {fan_in})")
    lines.append("")

    ranked_funcs = sorted(funcs.values(), key=lambda t: -t[0])[:MAX_FUNCS]
    if ranked_funcs:
        lines.append("Functions:")
    for _score, (fid, file_id, name, start, loc, cx) in ranked_funcs:
        path = _file_info(db, file_id)[0]
        lines.append(f"- `{name}` {_span(path, start, loc)} (complexity {cx})")
        callers, callees = _edges(db, fid)
        if callers:
            lines.append(f"  - callers: {_edge_text(callers)}")
        if callees:
            lines.append(f"  - callees: {_edge_text(callees)}")
    seen = set(ranked_files)
    prior_ids = [f for f in prior_hits if f not in seen][:MAX_PRIOR]
    if prior_ids:
        lines.append("Earlier PRs for this issue changed:")
        for fid in prior_ids:
            lines.append(f"- `{_file_info(db, fid)[0]}`")
    ranked_classes = sorted(classes.values(), key=lambda t: -t[0])[:MAX_FUNCS]
    if ranked_classes:
        lines.append("Classes:")
        for _score, (_cid, file_id, name) in ranked_classes:
            lines.append(f"- `{name}` in `{_file_info(db, file_id)[0]}`")

    # Cap: drop trailing lines (lowest ranked) until the estimate fits.
    budget = max_tokens * CHARS_PER_TOKEN
    while len(lines) > 3 and len("\n".join(lines)) > budget:
        lines.pop()
    return "\n".join(lines).rstrip() + "\n"


def fetch_issue(number: str) -> tuple[str, str]:
    out = subprocess.run(["gh", "api", ISSUE_API.format(n=number)], capture_output=True, text=True, check=True).stdout
    data = json.loads(out)
    return data.get("title") or "", data.get("body") or ""


_PR_RE = re.compile(r"\(#(\d+)\)\s*$")
_ISSUE_RE = re.compile(r"(?:Part of|Closes|Fixes|Resolves) #(\d+)", re.I)
# top-level directory names, not "docs/" prefixes: a literal doc path here would make every doc a test-read doc
_NON_SOURCE_DIRS = ("docs", ".github", ".claude")
_NON_SOURCE_SUFFIXES = (".md", ".json", ".yml", ".yaml", ".txt", ".csv", ".toml")


def is_source(path: str) -> bool:
    """A hand-written code file (tests included): not a doc, data file, workflow or agent note."""
    return path.split("/", 1)[0] not in _NON_SOURCE_DIRS and not path.endswith(_NON_SOURCE_SUFFIXES)


def recent_issue_prs(n: int, repo: Path = REPO_ROOT, scan: int = 600) -> list[tuple[str, str, str, list[str]]]:
    """Newest `n` (issue, pr, sha, changed files), one per issue, from squash commits on origin/main."""
    out = subprocess.run(
        ["git", "log", "origin/main", f"-n{scan}", "--name-only", "--format=\x1e%H\x1f%s"],
        capture_output=True,
        text=True,
        cwd=repo,
        check=True,
    ).stdout
    rows: list[tuple[str, str, str, list[str]]] = []
    seen: set[str] = set()
    for chunk in out.split("\x1e")[1:]:
        head, _, names = chunk.partition("\n")
        sha, _, subject = head.partition("\x1f")
        pr, issue = _PR_RE.search(subject), _ISSUE_RE.search(subject)
        if not (pr and issue) or issue.group(1) in seen:
            continue
        seen.add(issue.group(1))
        rows.append((issue.group(1), pr.group(1), sha, [x for x in names.splitlines() if x]))
        if len(rows) == n:
            break
    return rows


def evaluate(db: sqlite3.Connection, prs, fetch=fetch_issue, repo: Path = REPO_ROOT, max_tokens: int = 3000) -> str:
    """Markdown table: does the pack for each issue name the files its PR changed."""
    lines = ["| issue | PR | tokens | source files named | any file named |", "|---|---|---|---|---|"]
    any_hit = src_hit = full = 0
    for issue, pr, sha, files in prs:
        title, body = fetch(issue)
        pack = build_pack(db, title, body, max_tokens, prior_files(issue, repo, before=sha))
        src = [f for f in files if is_source(f)]
        named_src = [f for f in src if f"`{f}`" in pack or f"{f}:" in pack]
        named_any = [f for f in files if f"`{f}`" in pack or f"{f}:" in pack]
        any_hit += bool(named_any)
        src_hit += bool(named_src)
        full += bool(src) and len(named_src) == len(src)
        lines.append(
            f"| #{issue} | #{pr} | {len(pack) // CHARS_PER_TOKEN} | {len(named_src)}/{len(src)} | "
            f"{len(named_any)}/{len(files)} |"
        )
    n = len(prs)
    lines += [
        "",
        f"Issues: {n}. Pack names >=1 changed file: {any_hit}/{n}; >=1 changed source file: {src_hit}/{n}; "
        f"every changed source file: {full}/{n}.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("issue", nargs="?", help="issue number (used for gh unless --body-file is given)")
    ap.add_argument("--eval", type=int, metavar="N", help="hit rate against the newest N issue-closing PRs")
    ap.add_argument("--db", default=None, help="master DB (default docs/self_scan/gitgalaxy_master.db)")
    ap.add_argument("--body-file", help="read the issue text from this file instead of gh")
    ap.add_argument("--max-tokens", type=int, default=3000)
    args = ap.parse_args(argv)

    db_path = Path(args.db) if args.db else DEFAULT_DB
    if not db_path.exists():
        print(f"context_pack: no DB at {db_path}; run tests/tools/self_scan.py", file=sys.stderr)
        return 2
    if args.eval:
        db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            sys.stdout.write(evaluate(db, recent_issue_prs(args.eval), max_tokens=args.max_tokens))
        finally:
            db.close()
        return 0
    if not args.issue:
        ap.error("an issue number (or --eval N) is required")
    if args.body_file:
        text = Path(args.body_file).read_text(encoding="utf-8")
        title, _, body = text.partition("\n")
    else:
        title, body = fetch_issue(args.issue)
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        sys.stdout.write(build_pack(db, title, body, args.max_tokens, prior_files(args.issue)))
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
