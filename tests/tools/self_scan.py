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
Regenerate it whenever it's gone stale enough to matter (e.g. after a batch
of merged PRs); there's no incremental-staleness tracking here, just a fast
full rescan (~6-8s on this repo as of 2026-07).

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
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SELF_SCAN_DIR = REPO_ROOT / "docs" / "self_scan"
DB_PATH = SELF_SCAN_DIR / "gitgalaxy_master.db"

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


def regenerate() -> None:
    _check_full_precision_deps()
    SELF_SCAN_DIR.mkdir(parents=True, exist_ok=True)
    galaxyscope = shutil.which("galaxyscope")
    if not galaxyscope:
        sys.exit("galaxyscope not found on PATH -- activate the venv with gitgalaxy installed (pip install -e .)")

    # The recorder DELETEs-then-INSERTs keyed on (repo_name, commit_hash), so it
    # only replaces rows from a run at the SAME commit -- rows from a previous
    # commit would otherwise accumulate forever as HEAD moves. Since this DB is
    # meant to reflect current state only (no history queries), just start
    # from a clean file every time instead of relying on that keyed replace.
    DB_PATH.unlink(missing_ok=True)

    result = subprocess.run(  # noqa: S603 -- galaxyscope resolved absolute via shutil.which, fixed args
        [
            galaxyscope,
            str(REPO_ROOT),
            "--config",
            str(REPO_ROOT / ".galaxyscope.yaml"),
            "--db-only",
            "--output",
            str(SELF_SCAN_DIR / "gitgalaxy.json"),
        ],
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
    if result.returncode != 0 or not DB_PATH.exists():
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        sys.exit(f"self-scan failed -- {DB_PATH} was not produced")


def print_summary() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        (total_files,) = conn.execute("SELECT COUNT(*) FROM file_data").fetchone()
        (total_funcs,) = conn.execute("SELECT COUNT(*) FROM function_data").fetchone()
        (total_classes,) = conn.execute("SELECT COUNT(*) FROM class_data").fetchone()
        print(f"✅ Regenerated {DB_PATH.relative_to(REPO_ROOT)}")
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

    regenerate()
    print_summary()

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
