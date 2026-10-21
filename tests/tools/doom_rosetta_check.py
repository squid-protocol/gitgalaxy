#!/usr/bin/env python3
"""DOOM-rosetta golden check and bless tool (#5619): the Golden Crucible's twin over ~44 real DOOM ports.

    python tests/tools/doom_rosetta_check.py [--only a,b]            # scan each port, diff against the golden (rc 1 on drift)
    python tests/tools/doom_rosetta_check.py --update --yes          # re-bless: rewrite the golden, print the scope report
    python tests/tools/doom_rosetta_check.py --diagnose PORT [--file PATH]   # local only: print the real function names

The golden (``tests/golden_doom_rosetta/<port>.json.gz``) holds MEASUREMENTS ONLY, never third-party code
(``docs/research/third-party-material-policy.md``): the scorer's six-check row, SARIF counts by rule and level, per
first-party file its language, LOC, function and class counts and a hash of its sorted
``(name, start_line, loc, complexity)`` tuples (no names are committed), and the exclusion path + reason table.
It is gzip with a zeroed mtime so a re-bless of unchanged output is byte-identical (``*.json`` is git-ignored).

Clones are fetched at run time at the manifest SHA under ``--work`` (outside the repo) and never committed. Every
check rescans: results are not reused by engine SHA, since an uncommitted engine edit must show as drift.
Scans run with ``GITGALAXY_DISABLE_GIT_HISTORY=1`` (shallow clones carry no history to measure).

``tests/doom_rosetta/manifest.csv`` has an ``expected_fails`` column: the space-separated six-check names
(coverage language functions typosquat credentials health) a port is known to fail, so the verdicts are gated too. A
port failing a check not listed, or passing one that is, is drift. doom-ios and doomsday list ``language``: their
``.h`` files sit beside ``.m`` files and read as C, which the language check (``.h`` as objective-c needs ObjC
syntax) rejects. cssdoom and sqldoom list ``functions``: their JavaScript files carry more engine-counted functions
than ctags and tree-sitter (4.7% and 11.4% over ctags); the disagreement is unresolved, so nothing is claimed about
which count is right, and the entry is removed when the engine and the oracles agree. Needs Universal Ctags on PATH.
"""

import argparse
import contextlib
import csv
import gzip
import hashlib
import json
import os
import shutil
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(REPO_ROOT))  # before any gitgalaxy import: a shared venv may editable-install another checkout
sys.path.insert(0, str(HERE / "doom_speedrun"))

import doom_scorer  # noqa: E402
import doom_speedrun  # noqa: E402

GOLDEN_DIR = REPO_ROOT / "tests" / "golden_doom_rosetta"
SCAN_ENV = {"GITGALAXY_DISABLE_GIT_HISTORY": "1"}
REPORT_LINES = 40  # per port: a drifted port prints this many field lines, then a count of the rest
SUMMARY_DROP = ("variant", "treesitter_functions", "ts_delta_pct")  # oracle columns are the nightly's, not the gate's


@contextlib.contextmanager
def scan_env():
    """Set the scan env vars for the duration of a scan and restore them (never leak into the pytest session)."""
    saved = {k: os.environ.get(k) for k in SCAN_ENV}
    os.environ.update(SCAN_ENV)
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def golden_path(name):
    return GOLDEN_DIR / f"{name}.json.gz"


def read_golden(name):
    path = golden_path(name)
    if not path.exists():
        return None
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def write_golden(name, golden):
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(golden, sort_keys=True, separators=(",", ":")).encode()
    with open(golden_path(name), "wb") as fh, gzip.GzipFile(fileobj=fh, mode="wb", mtime=0, filename="") as gz:
        gz.write(raw)


def func_hash(tuples):
    """Short digest of a file's sorted (name, start_line, loc, complexity) tuples; the names never leave the hash."""
    body = "\n".join(f"{n}\t{s}\t{loc}\t{cx}" for n, s, loc, cx in sorted(tuples, key=lambda t: (t[1], t[0], t[2])))
    return hashlib.sha256(body.encode("utf-8", "replace")).hexdigest()[:16]


def read_scan(name, repo, scan):
    """Per first-party file rows ``{path: [language, loc, functions, classes, hash]}``, the raw tuples (for diagnose),
    and the exclusion table, read from one scan DB."""
    vendored = doom_scorer._engine_vendor_test(repo)
    con = sqlite3.connect(f"file:{scan / (name + '_galaxy_master.db')}?mode=ro", uri=True)
    try:
        files = {
            fid: (p, lang, loc)
            for fid, p, lang, loc in con.execute("select id, file_path, language, total_loc from file_data")
        }
        tuples = defaultdict(list)
        for fid, fname, start, loc, cx in con.execute(
            "select file_id, func_name, start_line, loc, complexity from function_data"
        ):
            tuples[fid].append((fname, start, loc, cx))
        classes = dict(con.execute("select file_id, count(*) from class_data group by file_id"))
        excluded = {
            p: reason for p, reason in con.execute("select file_path, exclusion_reason from excluded_artifacts")
        }
    finally:
        con.close()
    rows, raw = {}, {}
    for fid, (path, lang, loc) in files.items():
        if vendored(path):
            continue
        rows[path] = [lang, loc, len(tuples[fid]), classes.get(fid, 0), func_hash(tuples[fid])]
        raw[path] = sorted(tuples[fid], key=lambda t: (t[1], t[0]))
    return rows, raw, excluded


def sarif_counts(name, scan):
    path = scan / f"{name}_galaxy_sarif.json"
    results = json.loads(path.read_text())["runs"][0]["results"] if path.exists() else []
    return {
        "by_rule": dict(Counter(r.get("ruleId") for r in results)),
        "by_level": dict(Counter(r.get("level") for r in results)),
    }


def scan_and_build(row, work, fetch=True):
    """Fetch (unless told not to), rescan and measure one port. Returns (golden, raw tuples by file)."""
    name = row["name"]
    repos, scans, scratch = work / "repos", work / "rosetta-scans", work / "rosetta-scratch"
    for d in (repos, scans, scratch):
        d.mkdir(parents=True, exist_ok=True)
    if fetch and (err := doom_speedrun.fetch_port(row, repos)):
        raise RuntimeError(f"{name}: fetch failed: {err}")
    doom_speedrun._rmtree(scans / name)  # always rescan: an engine edit with no new SHA must show as drift
    with scan_env():
        doom_speedrun.scan_port(row, repos, scans)
    scored, _details = doom_scorer.score_port(name, repos / name, scans / name, scratch)
    summary = {k: v for k, v in scored.items() if k not in SUMMARY_DROP and not k.startswith("clang_")}
    summary.update(sarif_counts(name, scans / name))
    files, raw, excluded = read_scan(name, repos / name, scans / name)
    summary["files"] = len(files)
    summary["loc"] = sum(r[1] or 0 for r in files.values())
    summary["functions"] = sum(r[2] for r in files.values())
    summary["classes"] = sum(r[3] for r in files.values())
    summary["languages"] = dict(Counter(r[0] for r in files.values()))
    expected = sorted((row.get("expected_fails") or "").split())
    summary["expected_fails_met"] = sorted((summary.get("fails") or "").split()) == expected
    golden = {"port": name, "sha": row["sha"], "summary": summary, "files": files, "exclusions": excluded}
    return golden, raw


FILE_FIELDS = ("language", "loc", "functions", "classes", "func_hash")


def diff_golden(old, new):
    """Differences between two goldens as report lines (empty when identical): which port field, which file, which field."""
    out = []
    for k in sorted(set(old["summary"]) | set(new["summary"])):
        a, b = old["summary"].get(k), new["summary"].get(k)
        if a != b:
            out.append(f"summary.{k}: {a!r} -> {b!r}")
    if old["sha"] != new["sha"]:
        out.append(f"sha: {old['sha']} -> {new['sha']}")
    out += _diff_table("file", old["files"], new["files"], FILE_FIELDS)
    out += _diff_table("exclusion", old["exclusions"], new["exclusions"], None)
    return out


def _diff_table(kind, old, new, fields):
    out = [f"{kind} added: {p}" for p in sorted(set(new) - set(old))]
    out += [f"{kind} removed: {p}" for p in sorted(set(old) - set(new))]
    for p in sorted(set(old) & set(new)):
        if old[p] == new[p]:
            continue
        if fields is None:
            out.append(f"{kind} {p}: reason {old[p]!r} -> {new[p]!r}")
            continue
        moved = ", ".join(f"{f} {a!r} -> {b!r}" for f, a, b in zip(fields, old[p], new[p], strict=True) if a != b)
        out.append(f"{kind} {p}: {moved}")
    return out


def format_report(name, lines, limit=REPORT_LINES):
    head = f"{name}: {len(lines)} difference(s) from the golden"
    shown = lines[:limit]
    more = [f"  ... and {len(lines) - limit} more (run the check tool for the full list)"] if len(lines) > limit else []
    return "\n".join([head, *(f"  {ln}" for ln in shown), *more])


def check_port(row, work, fetch=True):
    """Measure one port and diff it against its golden. Returns (report text or '', new golden)."""
    golden, _ = scan_and_build(row, work, fetch)
    old = read_golden(row["name"])
    if old is None:
        return f"{row['name']}: no golden at {golden_path(row['name']).relative_to(REPO_ROOT)} (bless it)", golden
    lines = diff_golden(old, golden)
    return (format_report(row["name"], lines) if lines else ""), golden


def diagnose(row, work, only_file=None):
    """Local only: rescan one port and print the real function names of every drifted file (or ``only_file``)."""
    golden, raw = scan_and_build(row, work)
    old = read_golden(row["name"])
    drifted = set(raw) if only_file else set()
    if old and not only_file:
        drifted = {p for p in golden["files"] if golden["files"][p] != old["files"].get(p)}
    for line in diff_golden(old, golden)[:REPORT_LINES] if old else ["no golden to compare with"]:
        print(line)
    for path in sorted(p for p in drifted if not only_file or p == only_file):
        print(f"\n{path}: now {golden['files'][path]}  golden {old['files'].get(path) if old else None}")
        for fname, start, loc, cx in raw[path]:
            print(f"  {start:>6} loc={loc} cx={cx}  {fname}")
    return 0


def scope_report(changed):
    """Bless scope report (like bless_scope.py): per port, how many fields and files moved. For the PR body."""
    print("## DOOM-rosetta bless scope")
    for name, lines in changed.items():
        kinds = Counter(ln.split(":")[0].split(" ")[0] for ln in lines)
        print(f"- {name}: {len(lines)} change(s) ({', '.join(f'{n} {k}' for k, n in sorted(kinds.items()))})")
    if not changed:
        print("- no port moved")


def select(only):
    return doom_speedrun.read_manifest(None, only.split(",") if only else None)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", help="comma-separated port names (default: the whole manifest)")
    ap.add_argument("--work", type=Path, default=doom_speedrun.DEFAULT_WORK, help="scratch dir outside the repo")
    ap.add_argument("--update", action="store_true", help="rewrite the golden for the selected ports")
    ap.add_argument("--yes", action="store_true", help="confirm --update")
    ap.add_argument("--diagnose", metavar="PORT", help="rescan one port and print the real function names (local only)")
    ap.add_argument("--file", help="with --diagnose: just this file")
    args = ap.parse_args(argv)
    work = args.work.resolve()
    if work == REPO_ROOT or REPO_ROOT in work.parents:
        raise SystemExit("doom_rosetta_check: --work must be outside the repo tree (clones would poison scans)")
    if args.diagnose:
        return diagnose(select(args.diagnose)[0], work, args.file)
    if args.update and not args.yes:
        raise SystemExit("doom_rosetta_check: --update rewrites the golden; add --yes to confirm")
    if shutil.which("ctags") is None:
        raise SystemExit("doom_rosetta_check: Universal Ctags is required on PATH (the functions check)")
    drift, changed = [], {}
    for row in select(args.only):
        report, golden = check_port(row, work)
        print(f"{row['name']:22} {'drift' if report else 'ok'}", flush=True)
        if report:
            drift.append(report)
            old = read_golden(row["name"])
            changed[row["name"]] = diff_golden(old, golden) if old else ["new port"]
        if args.update:
            write_golden(row["name"], golden)
    if args.update:
        scope_report(changed)
        return 0
    if drift:
        print("\n" + "\n\n".join(drift), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
