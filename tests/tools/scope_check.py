#!/usr/bin/env python3
"""
Isolated-diff scope checker: proves a change's real-corpus impact is confined to the
language(s) you meant to touch, WITHOUT needing the committed golden-master fixtures to be
current or even correct yet.

Why this exists: `crucible_check.py` / `update_golden_master.py` diff your working tree's
output against the COMMITTED fixture -- exactly right for "is main still green" or "bless my
change," but useless mid-investigation when the fixture itself might be stale for reasons that
have nothing to do with you (another PR merged since you branched; local environment drift).
What you actually want while iterating is a narrower question this script answers directly:
"relative to a clean comparison ref, did my change touch anything outside the language(s) I
expect?" That was answered by hand across ~15 ad hoc `python3 -c` one-liners on PR #2518
(2026-08-30) -- scanning both trees, sanitizing, deep-comparing, and eyeballing every path for
an unexpected language -- this script is that exact methodology, packaged.

Usage:
    python tests/tools/scope_check.py                          # vs origin/main, report only
    python tests/tools/scope_check.py --expect jcl              # fail if anything outside jcl/ changed
    python tests/tools/scope_check.py --expect jcl,cobol        # multiple languages
    python tests/tools/scope_check.py --base HEAD~3              # compare against a different ref
    python tests/tools/scope_check.py --mode zero                # zero-dependency mode only (default: both)

Exit code: 0 if --expect was satisfied (or omitted, report-only mode with no crash), 1 if
--expect named languages but something outside that set changed, 2 on a setup failure (corpus
missing, worktree/venv build failure, etc.) -- distinct from 1 so a caller can tell "your change
is out of scope" apart from "the check itself couldn't run."

Runs `crucible_check.py`'s own corpus-pin / unsafe-path checks first (imported directly, not
duplicated) since a stale or unsafely-located corpus invalidates this comparison exactly the
same way it would a fixture diff.
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import crucible_check

sys.path.insert(0, str(Path(__file__).parent.parent))
import golden_diff

REPO_ROOT = crucible_check.REPO_ROOT
CRUCIBLE_PATH = crucible_check.CRUCIBLE_PATH

# Matches golden_diff's own path rendering for a per-file record, e.g.
# "/6. Parsed Files (Scanned Artifacts)/jcl/cics-genapp/Files/jcl/cics-genapp/foo.jcl/...".
# The language is always the FIRST path segment after this fixed section header, for both a
# MISMATCH/MISSING/EXTRA line and a bare directory-level entry -- see golden_diff.py's own
# JSON structure (keyed by corpus-relative directory, e.g. "jcl/cics-genapp").
_LANGUAGE_IN_PATH_RE = re.compile(r"Parsed Files \(Scanned Artifacts\)/([A-Za-z0-9_.+-]+)")
# "/2. Global Ecosystem Summary/composition/<lang>/..." and ".../directory_groups/<lang>/..."
# also name a language directly, for repo-wide rollup fields.
_LANGUAGE_IN_SUMMARY_RE = re.compile(r"Global Ecosystem Summary/(?:composition|directory_groups)/([A-Za-z0-9_.+-]+)")


def _language_for_diff_line(line: str) -> str | None:
    m = _LANGUAGE_IN_PATH_RE.search(line) or _LANGUAGE_IN_SUMMARY_RE.search(line)
    return m.group(1) if m else None


def _scan(py: Path, repo_root: Path, output_dir: Path) -> Path:
    subprocess.run(
        [str(py), "-m", "pip", "install", "-e", str(repo_root), "--no-deps", "-q"],
        env=crucible_check._venv_env(py),
        check=True,
    )
    env = crucible_check._venv_env(py)
    subprocess.run(
        [
            str(py.parent / "galaxyscope"),
            str(CRUCIBLE_PATH / "data"),
            "--output",
            str(output_dir) + "/",
            "--file-speed",
            "--splicing-speed",
        ],
        cwd=repo_root,
        env={**env, "GITGALAXY_LICENSE_KEY": "COMMUNITY_FREE_TIER"},
        check=True,
        timeout=300,
        capture_output=True,
    )
    out = output_dir / "data_galaxy_audit.json"
    if not out.exists():
        raise RuntimeError(f"galaxyscope did not produce {out}")
    return out


def run_scope_check(mode_key: str, base_ref: str, expect: set[str] | None) -> bool:
    label = crucible_check.MODES[mode_key][0]
    print(f"\n=== {label} ===")

    py_mine = crucible_check.ensure_venv(mode_key)
    crucible_check._check_unsafe_corpus_path(py_mine)

    with tempfile.TemporaryDirectory(prefix="scope_check_") as tmp:
        tmp_path = Path(tmp)
        base_worktree = tmp_path / "base_worktree"
        out_mine = tmp_path / "out_mine"
        out_base = tmp_path / "out_base"
        out_mine.mkdir()
        out_base.mkdir()

        subprocess.run(["git", "fetch", "origin", base_ref.split("/")[-1], "--quiet"], cwd=REPO_ROOT, check=False)
        subprocess.run(
            ["git", "worktree", "add", "--detach", str(base_worktree), base_ref],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
        )
        try:
            print(f"[{mode_key}] Scanning this checkout ...")
            audit_mine = _scan(py_mine, REPO_ROOT, out_mine)
            print(f"[{mode_key}] Building comparison venv for {base_ref} (first run only) ...")
            py_base = crucible_check.ensure_venv(mode_key, repo_root=base_worktree)
            print(f"[{mode_key}] Scanning {base_ref} ...")
            audit_base = _scan(py_base, base_worktree, out_base)
        finally:
            subprocess.run(["git", "worktree", "remove", "--force", str(base_worktree)], cwd=REPO_ROOT, check=False)

        mine = golden_diff.load_and_sanitize(str(audit_mine))
        base = golden_diff.load_and_sanitize(str(audit_base))
        diffs = golden_diff.deep_compare(base, mine)

    by_language: dict[str, list[str]] = {}
    unattributed: list[str] = []
    for d in diffs:
        lang = _language_for_diff_line(d)
        (by_language.setdefault(lang, []) if lang else unattributed).append(d)  # type: ignore[arg-type]
    if unattributed:
        by_language.setdefault("(unattributed -- repo-wide rollup fields)", []).extend(unattributed)

    print(f"Total differences vs {base_ref}: {len(diffs)}")
    for lang, lines in sorted(by_language.items(), key=lambda kv: -len(kv[1])):
        print(f"  {lang}: {len(lines)}")

    if expect is None:
        return True

    out_of_scope = {lang: lines for lang, lines in by_language.items() if lang not in expect}
    if out_of_scope:
        print(f"❌ Changes outside --expect {sorted(expect)}:")
        for lang, lines in out_of_scope.items():
            print(f"  {lang} ({len(lines)}):")
            for line in lines[:5]:
                print(f"    {line[:300]}")
            if len(lines) > 5:
                print(f"    ... and {len(lines) - 5} more")
        return False

    print(f"✅ All changes confined to --expect {sorted(expect)}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", default="origin/main", help="Comparison ref (default: origin/main).")
    parser.add_argument("--mode", choices=["full", "zero", "both"], default="both")
    parser.add_argument(
        "--expect",
        default=None,
        help="Comma-separated language(s) your change should touch. If any OTHER language's "
        "output differs from --base, exit non-zero. Omit for report-only mode.",
    )
    parser.add_argument(
        "--json", action="store_true", help="(reserved) machine-readable output -- not yet implemented."
    )
    args = parser.parse_args()

    if not (CRUCIBLE_PATH / "data").exists():
        print(f"❌ language-crucible corpus not found at {CRUCIBLE_PATH}.")
        return 2
    crucible_check._check_corpus_pin()

    if not shutil.which("git"):
        print("❌ git not found on PATH.")
        return 2

    expect = {lang.strip() for lang in args.expect.split(",")} if args.expect else None
    mode_keys = ["full", "zero"] if args.mode == "both" else [args.mode]

    try:
        results = [run_scope_check(mode_key, args.base, expect) for mode_key in mode_keys]
    except (subprocess.CalledProcessError, RuntimeError) as e:
        print(f"❌ scope_check setup failed: {e}")
        return 2

    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
