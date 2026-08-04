#!/usr/bin/env python3
"""
Regenerates GitGalaxy's self-scan of its own repo -- a SQLite database of
per-file/function/class structural facts (LOC, complexity, function/class
counts, dependency-network scores, etc.) at docs/self_scan/gitgalaxy_master.db.

Why this exists: an LLM coding session working in this repo often starts a
task by re-deriving basic structural facts (how big is this file, how many
functions does it have, which files already exist for language X) via grep or
an Explore subagent -- both of which cost real tokens for what is, in this
codebase's own terms, a Structural Signature the engine already knows how to
extract about itself. Querying the self-scan DB directly with `sqlite3` is
near-zero-token for exactly that class of question. It does NOT replace
reading actual file content -- the DB has no line numbers and doesn't parse
the internals of a dict literal (e.g. it can't tell you where the "scala" key
starts inside language_standards.py's LANGUAGE_DEFINITIONS dict) -- it's for
orientation and prioritization, not symbol lookup.

The DB is gitignored (*.db, see .gitignore) and NOT committed -- it's a local,
disposable, cheaply-regenerable artifact, same spirit as .crucible_venvs/.

Regeneration uses galaxyscope's own `--incremental` Delta Scan (gitgalaxy/state_rehydrator.py)
when a usable baseline already exists at DB_PATH: it rehydrates the previous structural state
from SQLite, diffs the working tree against the baseline commit, and only re-parses
added/modified files -- the same mechanism CI uses for large repos. If the DB already exactly
matches current HEAD with a clean working tree, the scan is skipped entirely. First run (or a
DB from before this existed) falls back to a full scan. Either way, run() prunes the DB back
down to a single commit's rows afterward -- see _prune_stale_commits()'s docstring for why that
matters.

USAGE
    python tests/tools/self_scan.py               # regenerate, print a summary
    python tests/tools/self_scan.py --query "SELECT ..."   # regenerate, then
                                                            # run an ad hoc
                                                            # query and print
                                                            # the result

SCHEMA (as of this writing -- always confirm with `.schema <table>` in
sqlite3 rather than trusting this comment, since the engine's own recorders
evolve): repo_data (one row, repo-wide aggregates + all Structural Signature
totals), folder_data, file_data (per-file: file_path, language, total_loc,
coding_loc, function_count, class_count, complexity/dependency-network
scores), function_data (per-function: func_name, complexity, loc, args,
calls_out_to, docstring -- joined to file_data via file_id), class_data
(per-class: class_name, inheritance_parents, method_count -- joined via
file_id).
"""

import argparse
import importlib.util
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SELF_SCAN_DIR = REPO_ROOT / "docs" / "self_scan"
DB_PATH = SELF_SCAN_DIR / "gitgalaxy_master.db"
# Matches target_path.name in galaxyscope.py's main() -- the exact string both
# the recorder (repo_name column) and StateRehydrator.load_latest_state() key on.
PROJECT_NAME = REPO_ROOT.name

# Mirrors the HAS_NETWORKX / HAS_TIKTOKEN / ML_AVAILABLE / HAS_PYYAML checks in
# galaxyscope.py / network_risk_sensor.py / security_auditor.py. Without every
# one of these, galaxyscope silently drops into "Zero-Dependency Mode" --
# pagerank_score and normalized_blast_radius (and other network/ML-derived
# columns) get written as NULL instead of erroring, since zero-dependency mode
# is a legitimate, intentional mode for scanning *other* repos where installing
# the full ML stack isn't wanted. But for THIS repo's own self-scan, silently
# degraded output defeats the point -- callers query this DB assuming full
# precision. Fail loudly before wasting a scan on a DB nobody wanted.
FULL_PRECISION_PACKAGES = ("networkx", "tiktoken", "numpy", "pandas", "xgboost", "yaml")


def _check_full_precision_deps() -> None:
    missing = [pkg for pkg in FULL_PRECISION_PACKAGES if importlib.util.find_spec(pkg) is None]
    if missing:
        sys.exit(
            "self-scan aborted -- missing full-precision dependencies: "
            + ", ".join(missing)
            + "\nWithout these, galaxyscope silently degrades to Zero-Dependency Mode and "
            "pagerank_score/normalized_blast_radius (and other network/ML-derived columns) "
            "come back NULL instead of erroring. Install them into this environment first:\n"
            "    pip install " + " ".join(pkg if pkg != "yaml" else "pyyaml" for pkg in missing)
        )


def _git(*args: str) -> str:
    return subprocess.check_output(  # noqa: S603 -- fixed "git" binary via PATH, args are literals/constants only
        ["git", *args], cwd=REPO_ROOT, text=True, stderr=subprocess.DEVNULL
    ).strip()


def _current_head() -> str:
    return _git("rev-parse", "HEAD")


def _working_tree_dirty() -> bool:
    return bool(_git("status", "--porcelain"))


def _db_commit_hashes() -> set[str]:
    if not DB_PATH.exists():
        return set()
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            "SELECT DISTINCT commit_hash FROM file_data WHERE repo_name = ?", (PROJECT_NAME,)
        ).fetchall()
        return {r[0] for r in rows}
    except sqlite3.OperationalError:
        # Pre-existing DB predates a column/table this query relies on -- treat as unusable.
        return set()
    finally:
        conn.close()


def _prune_stale_commits(keep_hash: str) -> None:
    """
    record_mission() (gitgalaxy/recorders/record_keeper.py) DELETEs-then-INSERTs keyed on
    (repo_name, commit_hash) -- a Delta Scan against a moved HEAD writes a NEW commit_hash's
    rows without touching the old baseline's, so left alone they'd accumulate forever as HEAD
    moves. This DB is meant to reflect current state only (no history queries), so collapse it
    back down to a single commit after every scan, incremental or not.

    file_data/folder_data/repo_data all carry commit_hash directly and have no FK relationship
    to each other (checked: file_data has no FK back to repo_data), so each needs its own
    DELETE. function_data/class_data are NOT touched directly -- they cascade automatically via
    their file_id -> file_data(id) ON DELETE CASCADE foreign key.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        for table in ("repo_data", "folder_data", "file_data"):
            conn.execute(f"DELETE FROM {table} WHERE repo_name = ? AND commit_hash != ?", (PROJECT_NAME, keep_hash))
        conn.commit()
    finally:
        conn.close()


def regenerate() -> bool:
    """Returns True if a scan actually ran, False if the existing DB was already current."""
    _check_full_precision_deps()
    SELF_SCAN_DIR.mkdir(parents=True, exist_ok=True)
    galaxyscope = shutil.which("galaxyscope")
    if not galaxyscope:
        sys.exit("galaxyscope not found on PATH -- activate the venv with gitgalaxy installed (pip install -e .)")

    head = _current_head()
    existing = _db_commit_hashes()

    # DB already reflects exactly this commit with nothing uncommitted on top -- a rescan
    # (incremental or not) would produce byte-identical structural facts. Skip the subprocess.
    if existing == {head} and not _working_tree_dirty():
        return False

    # StateRehydrator.load_latest_state() needs a real baseline row to rehydrate from -- if the
    # DB is missing, or predates this repo_name/schema, there's nothing to diff against, so
    # start clean instead of passing --incremental at a baseline it can't use.
    incremental = DB_PATH.exists() and bool(existing)
    if not incremental:
        DB_PATH.unlink(missing_ok=True)

    cmd = [
        galaxyscope,
        str(REPO_ROOT),
        "--config",
        str(REPO_ROOT / ".galaxyscope.yaml"),
        "--db-only",
        "--output",
        str(SELF_SCAN_DIR / "gitgalaxy.json"),
    ]
    if incremental:
        cmd += ["--incremental", str(DB_PATH)]

    start = time.time()
    result = subprocess.run(  # noqa: S603 -- galaxyscope resolved absolute via shutil.which, fixed args
        cmd,
        cwd=REPO_ROOT,
        # Merge with (not replace) the parent env -- galaxyscope shells out to
        # `git` to resolve commit_hash, which needs PATH/HOME/etc. A bare
        # env={"GITGALAXY_LICENSE_KEY": ...} strips all of that, silently
        # degrading commit_hash to "Unknown" instead of erroring loudly.
        env={**os.environ, "GITGALAXY_LICENSE_KEY": "COMMUNITY_FREE_TIER"},
        capture_output=True,
        text=True,
        timeout=120,
    )
    elapsed = time.time() - start
    if result.returncode != 0 or not DB_PATH.exists():
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        sys.exit(f"self-scan failed -- {DB_PATH} was not produced")

    # galaxyscope falls back to a full scan internally if the delta (git diff against the
    # baseline commit) fails, so the DB may hold more than just {head} even on the incremental
    # path -- and on the happy path, the keyed DELETE-then-INSERT above never touches the old
    # baseline's rows either way. Collapse to current HEAD regardless of which path ran.
    _prune_stale_commits(_current_head())

    mode = "incremental" if incremental else "full"
    print(f"   ({mode} scan, {elapsed:.1f}s)")
    return True


def print_summary(ran: bool) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        (total_files,) = conn.execute("SELECT COUNT(*) FROM file_data").fetchone()
        (total_funcs,) = conn.execute("SELECT COUNT(*) FROM function_data").fetchone()
        (total_classes,) = conn.execute("SELECT COUNT(*) FROM class_data").fetchone()
        if ran:
            print(f"✅ Regenerated {DB_PATH.relative_to(REPO_ROOT)}")
        else:
            print(f"✅ {DB_PATH.relative_to(REPO_ROOT)} already current at HEAD -- scan skipped")
        print(f"   {total_files} files, {total_funcs} functions, {total_classes} classes indexed.")

        # Belt-and-suspenders: _check_full_precision_deps() confirms the
        # packages are importABLE, not that galaxyscope actually used them --
        # an internal exception during graph-building could still leave these
        # NULL even with every dependency present. Verify the real output.
        (with_pagerank,) = conn.execute("SELECT COUNT(*) FROM file_data WHERE pagerank_score IS NOT NULL").fetchone()
        if total_files and with_pagerank == 0:
            print(
                "⚠️  pagerank_score/normalized_blast_radius are NULL for every file -- this scan "
                "ran in Zero-Dependency Mode despite full-precision packages being importable. "
                "Blast-radius queries against this DB will return nothing; check galaxyscope's "
                "stderr output above for why.",
                file=sys.stderr,
            )
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--query", help="Ad hoc SQL to run against the DB after regenerating, printed as rows")
    args = parser.parse_args()

    ran = regenerate()
    print_summary(ran)

    if args.query:
        conn = sqlite3.connect(DB_PATH)
        try:
            cur = conn.execute(args.query)
            cols = [d[0] for d in cur.description]
            print("\n" + " | ".join(cols))
            for row in cur.fetchall():
                print(" | ".join(str(v) for v in row))
        finally:
            conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
