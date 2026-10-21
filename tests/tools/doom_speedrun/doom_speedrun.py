#!/usr/bin/env python3
"""DOOM Port Speedrun harness (#5468): pinned manifest -> clone -> scan -> clean-scan score -> CSV + markdown.

    python tests/tools/doom_speedrun/doom_speedrun.py run [--only a,b] [--oracle] [--legacy-vendor] [--work DIR]
    python tests/tools/doom_speedrun/doom_speedrun.py fetch|scan|score|report  (the same steps, one at a time)
    python tests/tools/doom_speedrun/doom_speedrun.py diff BEFORE AFTER [--fail-on-regression]  (CSV, dir, SHA or round2)

Every step is resumable: a port already cloned at its SHA, or already scanned at this engine SHA, is skipped.
Clones go to ``<work>/repos`` (never inside this repo), scans to ``<work>/scans/<engine-sha>/<port>``, and the
results to ``<work>/results/<engine-sha>/clean_check.{csv,md}`` + ``details.json``, so before/after for one fix
is a diff of two result directories. Not part of default CI: opt-in, run it by hand (heavy-run.sh wraps scans).
Third-party code is fetched at run time at the manifest's pinned SHA and never committed.
"""

import argparse
import csv
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
sys.path.insert(0, str(REPO_ROOT))  # before any gitgalaxy import: a shared venv may editable-install another checkout
sys.path.insert(0, str(HERE))

import doom_diff  # noqa: E402
import doom_scorer  # noqa: E402

MANIFEST = REPO_ROOT / "tests" / "doom_rosetta" / "manifest.csv"  # moved from this directory (#5619)
DEFAULT_WORK = Path(os.environ.get("DOOM_SPEEDRUN_WORK", "/tmp/gitgalaxy-scratch/doom-speedrun"))
HEAVY_RUN = REPO_ROOT / "tests" / "tools" / "box" / "heavy-run.sh"
ORACLE_COLUMNS = ("treesitter_functions", "ts_delta_pct")
COLUMNS = [
    "variant", "rc", "first_party_src", "missed_src", "excluded_by_design",
    "excluded_by_design_reasons", "data_files_excluded", "vendor_files_mapped", "wrong_language",
    "gg_functions", "ctags_functions", "func_delta_pct", "functions_agree", "treesitter_functions", "ts_delta_pct", "clang_files", "clang_files_with_errors",
    "clang_compile_commands_files", "clang_functions", "clang_gg_functions", "clang_delta_pct", "files_func_mismatch",
    "files_ctags_checked", "typosquat", "sarif_total", "sarif_errors", "credential_files", "log_problems", "fails",
    "verdict",
]  # fmt: skip


def read_manifest(path=None, only=None):
    """Manifest rows, in file order, optionally narrowed to the named ports (an unknown name is an error)."""
    with open(path or MANIFEST, newline="") as fh:
        rows = list(csv.DictReader(fh))
    if only:
        unknown = sorted(set(only) - {r["name"] for r in rows})
        if unknown:
            raise SystemExit(f"doom_speedrun: not in the manifest: {', '.join(unknown)}")
        rows = [r for r in rows if r["name"] in only]
    return rows


def engine_sha():
    out = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "--short=9", "HEAD"], capture_output=True, text=True, check=False
    )
    return out.stdout.strip() or "unknown"


def _git(repo, *args, timeout=900):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=timeout, env=env, check=False
    )


def _writable_retry(func, path, *_exc):
    """rmtree error hook: git's pack and object files are read-only, which Windows refuses to delete."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        pass


def _rmtree(path):
    """Remove a directory tree, including a git checkout's read-only objects on Windows (a plain
    ``ignore_errors=True`` left them behind, so the next mkdir raised FileExistsError)."""
    if not Path(path).exists():
        return
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_writable_retry)
    else:
        shutil.rmtree(path, onerror=_writable_retry)


def fetch_port(row, repos):
    """Shallow-fetch exactly the pinned SHA. Returns None on success or a failure message."""
    dest = repos / row["name"]
    if dest.is_dir() and _git(dest, "rev-parse", "HEAD").stdout.strip() == row["sha"]:
        return None
    _rmtree(dest)
    dest.mkdir(parents=True)
    for args in (["init", "-q"], ["remote", "add", "origin", row["upstream"]],
                 ["fetch", "-q", "--depth", "1", "origin", row["sha"]], ["checkout", "-q", "FETCH_HEAD"]):  # fmt: skip
        r = _git(dest, *args)
        if r.returncode:
            _rmtree(dest)
            return f"git {args[0]}: {r.stderr.strip()[:200]}"
    return None


def scan_port(row, repos, scans):
    """Scan one port with the current engine (through heavy-run.sh when present); writes scan.log and rc.txt."""
    out = scans / row["name"]
    if (out / "rc.txt").exists():
        return
    _rmtree(out)
    out.mkdir(parents=True)
    env = dict(
        os.environ,
        PYTHONPATH=str(REPO_ROOT),
        GITGALAXY_LICENSE_KEY=os.environ.get("GITGALAXY_LICENSE_KEY", "COMMUNITY_FREE_TIER"),
    )
    cmd = [sys.executable, "-m", "gitgalaxy.galaxyscope", str(repos / row["name"]), "--output", str(out) + "/"]
    if HEAVY_RUN.exists():
        cmd = [str(HEAVY_RUN), *cmd]
    with open(out / "scan.log", "w") as log:
        rc = subprocess.run(cmd, cwd=out, env=env, stdout=log, stderr=subprocess.STDOUT, check=False).returncode
    (out / "rc.txt").write_text(f"{rc}\n")


def write_results(rows, details, dest, sha, oracle, clang=False):
    dest.mkdir(parents=True, exist_ok=True)
    cols = [c for c in COLUMNS if (oracle or c not in ORACLE_COLUMNS) and (clang or not c.startswith("clang_"))]
    with open(dest / "clean_check.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    (dest / "details.json").write_text(json.dumps(details, indent=1, sort_keys=True) + "\n")
    perfect = sum(r.get("verdict") == "PERFECT" for r in rows)
    lines = [f"# DOOM port clean-scan: engine `{sha}`", "", f"**{perfect} PERFECT / {len(rows)} ports**", "",
             "| port | verdict | fails | gg fn | ctags fn | delta % | ts fn | missed | by design | by-design reason | SARIF err |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
    for r in rows:
        lines.append(
            "| {variant} | {verdict} | {fails} | {gg_functions} | {ctags_functions} | {func_delta_pct} | {ts} | {missed_src} | {excluded_by_design} | {excluded_by_design_reasons} | {sarif_errors} |".format(
                **{k: r.get(k, "") for k in COLUMNS}, ts=r.get("treesitter_functions", "")
            )
        )
    (dest / "clean_check.md").write_text("\n".join(lines) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("step", choices=["run", "fetch", "scan", "score", "report", "diff"])
    ap.add_argument(
        "refs", nargs="*", help="diff only: BEFORE AFTER (a clean_check.csv, results dir, engine SHA or round2)"
    )
    ap.add_argument(
        "--fail-on-regression", action="store_true", help="diff only: exit 1 if a port gained a failed check"
    )
    ap.add_argument("--only", help="comma-separated port names (default: the whole manifest)")
    ap.add_argument(
        "--work", type=Path, default=DEFAULT_WORK, help=f"scratch dir outside the repo (default {DEFAULT_WORK})"
    )
    ap.add_argument(
        "--oracle", action="store_true", help="add tree-sitter definition counts beside ctags (reported, not scored)"
    )
    ap.add_argument(
        "--clang",
        metavar="PORTS",
        help="libclang definition counts for these comma-separated ports ('all' for every port); needs the "
        "`libclang` PyPI wheel; reported beside ctags, not scored",
    )
    ap.add_argument("--legacy-vendor", action="store_true", help="also skip the round-2 study's hand-kept vendor names")
    ap.add_argument("--manifest", type=Path, help="alternate manifest CSV")
    args = ap.parse_args(argv)
    work = args.work.resolve()
    if work == REPO_ROOT or REPO_ROOT in work.parents:
        raise SystemExit("doom_speedrun: --work must be outside the repo tree (third-party clones would poison scans)")
    if args.step == "diff":
        if len(args.refs) != 2:
            raise SystemExit("doom_speedrun: diff takes exactly two refs: BEFORE AFTER")
        return doom_diff.run(*args.refs, work, args.fail_on_regression)
    rows = read_manifest(args.manifest, args.only.split(",") if args.only else None)
    clang_ports = {r["name"] for r in rows} if args.clang == "all" else set((args.clang or "").split(",")) - {""}
    if unknown := clang_ports - {r["name"] for r in rows}:
        raise SystemExit(f"doom_speedrun: --clang names ports not in this run: {', '.join(sorted(unknown))}")
    sha = engine_sha()
    repos, scans, results = work / "repos", work / "scans" / sha, work / "results" / sha
    repos.mkdir(parents=True, exist_ok=True)
    scans.mkdir(parents=True, exist_ok=True)
    failed = []
    if args.step in ("run", "fetch", "scan"):
        for row in rows:
            err = fetch_port(row, repos) if args.step != "scan" else None
            if err:
                failed.append((row["name"], err))
                print(f"FETCH FAIL {row['name']}: {err}", file=sys.stderr)
            elif args.step != "fetch":
                scan_port(row, repos, scans)
            print(f"{args.step} {row['name']}", flush=True)
    if args.step in ("run", "score", "report"):
        out_rows, details = [], {}
        for row in rows:
            r, d = doom_scorer.score_port(
                row["name"],
                repos / row["name"],
                scans / row["name"],
                work,
                args.oracle,
                args.legacy_vendor,
                row["name"] in clang_ports,
            )
            out_rows.append(r)
            details[row["name"]] = d
            print(f"{row['name']:16} {r.get('verdict', ''):8} {r.get('fails', '')}")
        write_results(out_rows, details, results, sha, args.oracle, bool(clang_ports))
        print(f"wrote {results}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
