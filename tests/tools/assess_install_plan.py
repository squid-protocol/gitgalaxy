#!/usr/bin/env python3
"""Does a pull request run the `gitgalaxy assess` clean-install check? (a step of ports-compile.yml, #6672)

    python tests/tools/assess_install_plan.py --event pull_request --files-tsv FILE [--github-output PATH]
    python tests/tools/assess_install_plan.py --event schedule

scripts/check_assess_install.py builds the wheel, installs it into a fresh venv with no network and runs the installed
`gitgalaxy assess` on a planted estate and the six burned estates (#4726). It is the only check that sees the wheel, so
what it alone catches is a packaging break: a module or data file the wheel does not ship, an entry point, an extra.
It took ~3.1 min of the ~7.9 min Ports Compile job and had not failed once in ~420 runs (2026-10-22..25). A pull
request runs it only when a changed file can break what it checks (`needs_check`):

* packaging or the check itself: pyproject.toml, MANIFEST.in, the script, this planner, the workflow, the pinned
  estates (tests/cobol_mainframe/corpora.json);
* the assess command: gitgalaxy/cli.py, gitgalaxy/tools/readiness/**;
* a file added, removed, renamed or copied under gitgalaxy/ (a new module or data file `packages.find` / package-data
  may not ship, or a path the wheel no longer has);
* a non-Python file modified under gitgalaxy/ that the wheel ships (a `[tool.setuptools.package-data]` glob of
  pyproject.toml matches it): an edited data file nothing ships (language_addition_costs.jsonl) cannot break it.

Markdown never runs it (no package-data glob ships prose). Every other event (main dispatch, nightly, manual) runs it,
and so does any doubt: an unreadable or truncated file list, or a pyproject.toml tomllib cannot read.
Input: `status<TAB>path` lines (the pull request files API's `status`: added, removed, modified, renamed, copied,
changed, unchanged). Output: JSON {run, reason}; with --github-output, `run=true|false`. Stdlib only.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ALWAYS = (
    "pyproject.toml",
    "MANIFEST.in",
    "scripts/check_assess_install.py",
    "tests/tools/assess_install_plan.py",
    ".github/workflows/ports-compile.yml",
    "tests/cobol_mainframe/corpora.json",
    "gitgalaxy/cli.py",
    "gitgalaxy/tools/readiness/*",  # fnmatch: `*` crosses `/`
)
NOT_AN_EDIT = frozenset({"added", "removed", "renamed", "copied"})


def shipped_globs(root: Path = REPO_ROOT) -> tuple[str, ...]:
    """The repo-relative globs of [tool.setuptools.package-data] (`gitgalaxy.core` + `x/*.json` -> `gitgalaxy/core/x/*.json`)."""
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    table = data.get("tool", {}).get("setuptools", {}).get("package-data", {})
    return tuple(f"{pkg.replace('.', '/')}/{g}" for pkg, globs in table.items() for g in globs)


def needs_check(status: str, path: str, shipped: tuple[str, ...]) -> bool:
    if path.endswith(".md"):
        return False
    if any(fnmatch.fnmatchcase(path, p) for p in ALWAYS):
        return True
    if not path.startswith("gitgalaxy/"):
        return False
    if status in NOT_AN_EDIT:  # a module or data file appears, moves or goes: what the wheel ships may change
        return True
    if path.endswith(".py"):  # an edited module is shipped already; the other jobs test what it does
        return False
    # a modified data file: only what the wheel ships (fnmatch `*` crosses `/`, wider than setuptools' glob: safe side)
    return any(fnmatch.fnmatchcase(path, g) for g in shipped)


def plan(changes: list[tuple[str, str]] | None, event: str, shipped: tuple[str, ...] | None = None) -> dict:
    if event != "pull_request":
        return {"run": True, "reason": f"{event}: always"}
    if not changes:
        return {"run": True, "reason": "no changed files found (the list is unreadable, truncated or empty)"}
    shipped = shipped_globs() if shipped is None else shipped
    hit = next(((s, p) for s, p in changes if needs_check(s, p, shipped)), None)
    if hit:
        return {"run": True, "reason": f"{hit[1]} ({hit[0]}) can change what the wheel ships or what assess does"}
    return {"run": False, "reason": f"none of {len(changes)} changed file(s) can break the clean install"}


def read_tsv(path: Path) -> list[tuple[str, str]]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if "\t" in line:
            status, name = line.split("\t", 1)
            out.append((status.strip(), name.strip()))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--event", default="pull_request")
    ap.add_argument("--files-tsv", type=Path, help="`status<TAB>path` per changed file; missing or empty = run")
    ap.add_argument("--github-output", type=Path, help="append run=true|false for later steps")
    args = ap.parse_args()
    try:
        changes = read_tsv(args.files_tsv) if args.files_tsv and args.files_tsv.is_file() else None
        p = plan(changes, args.event)
    except (OSError, ValueError) as e:  # cannot tell what changed: run
        p = {"run": True, "reason": f"cannot plan ({e})"}
    print(json.dumps(p, indent=1))
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as fh:
            fh.write(f"run={'true' if p['run'] else 'false'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
