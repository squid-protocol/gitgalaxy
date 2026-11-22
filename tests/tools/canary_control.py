#!/usr/bin/env python3
"""The weekly control PR (#7155, part 2): a real PR from a `canary/` branch carrying one planted defect per gate.

A green gate means something only if it can go red. `gate_controls.py` proves each gate's logic on a fixture; this opens
a real, ready-for-review PR so the workflow around each gate (its shell, its reach, its skip paths) is exercised too.

    python tests/tools/canary_control.py plan             # the detection matrix to expect, as JSON
    python tests/tools/canary_control.py open [--dry-run]  # branch off main, plant, push, open the PR

Every defect is inert: a new file, no network, no secret, nothing under `.github/` or a release path. The PR body carries
a `canary-expect` JSON marker (the gates that must go red) for the results job, a later slice. A canary PR is never to
merge: the `ci-gate` hold and the merge-label refusal belong to the shepherd (owner-only) and are not here.
Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_controls  # noqa: E402

BRANCH_PREFIX = "canary/"
MARKER = "canary-expect"
# A planted file may never land here: workflows, release paths, the shepherd, secrets.
FORBIDDEN_PREFIXES = (".github/", "release/", "dist/", ".claude/")
FORBIDDEN_NAMES = ("pyproject.toml", ".env", "publish.yml")


@dataclass(frozen=True)
class Defect:
    key: str
    path: str  # a NEW file (never edits an existing one)
    content: str
    red: tuple[str, ...]  # names of gate_controls.GATES that must go red
    what: str


DEFECTS = (
    Defect(
        "lint",
        "gitgalaxy/canary_probe_lint.py",
        '"""Canary probe: an unused import."""\n\nimport os\n',
        ("ruff-audit (lint)", "ruff-audit (real ruff)"),
        "an unused import (F401) in a new module",
    ),
    Defect(
        "format",
        "gitgalaxy/canary_probe_format.py",
        '"""Canary probe: not ruff-format clean."""\n\nVALUE  =  {"a":1,\n  "b":2}\n',
        ("ruff-audit (format)",),
        "a file `ruff format --check` rewrites",
    ),
    Defect(
        "types",
        "gitgalaxy/canary_probe_types.py",
        '"""Canary probe: a type error."""\n\n\ndef probe() -> int:\n    return "not an int"\n',
        ("mypy-audit",),
        "a function returning str where int is declared",
    ),
    Defect(
        "test",
        "tests/tools/test_canary_probe_fails.py",
        '"""Canary probe: a test that must fail."""\n\n\ndef test_the_planted_failure():\n    assert 1 == 2\n',
        ("full-suite",),
        "a test that always fails",
    ),
    Defect(
        "docref",
        "docs/canary_probe_doc.md",
        "# Canary probe\n\nSee [a page that does not exist](canary_probe_missing_page.md).\n",
        ("doc-refs-audit",),
        "a hand-written doc with a dead relative link",
    ),
)


def problems(defects: tuple[Defect, ...] = DEFECTS) -> list[str]:
    """Why a catalog is unsafe or stale: an unknown gate, a path a canary must not touch, a duplicate."""
    known = {g.name for g in gate_controls.GATES}
    out: list[str] = []
    seen: set[str] = set()
    for d in defects:
        norm = d.path.replace("\\", "/")
        if d.path in seen:
            out.append(f"{d.key}: {d.path} planted twice")
        seen.add(d.path)
        if norm.startswith("/") or ".." in norm.split("/"):
            out.append(f"{d.key}: {d.path} leaves the repo")
        if norm.startswith(FORBIDDEN_PREFIXES) or norm.rsplit("/", 1)[-1] in FORBIDDEN_NAMES:
            out.append(f"{d.key}: {d.path} is a workflow, release or secret path")
        if (REPO / d.path).exists():
            out.append(f"{d.key}: {d.path} already exists (a defect is a new file)")
        out += [f"{d.key}: no gate named {g!r}" for g in d.red if g not in known]
        if not d.red:
            out.append(f"{d.key}: expects no gate to go red")
    return out


def plan(defects: tuple[Defect, ...] = DEFECTS) -> dict:
    """The detection matrix to expect: each planted file and the gates that must go red on it."""
    return {
        "defects": [{"key": d.key, "path": d.path, "what": d.what, "red": list(d.red)} for d in defects],
        "must_go_red": sorted({g for d in defects for g in d.red}),
    }


def branch_name(now: datetime | None = None) -> str:
    return BRANCH_PREFIX + (now or datetime.now(UTC)).strftime("%Y%m%dT%H%MZ")


def pr_body(defects: tuple[Defect, ...] = DEFECTS) -> str:
    rows = "\n".join(f"- `{d.path}`: {d.what}; must turn red: {', '.join(d.red)}" for d in defects)
    return (
        "Weekly control PR (#7155). Every defect below is planted on purpose; **do not merge, do not label.**\n\n"
        f"{rows}\n\n"
        f"<!-- {MARKER} {json.dumps(plan(defects), sort_keys=True)} -->\n"
    )


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True)


def plant(root: Path, defects: tuple[Defect, ...] = DEFECTS) -> list[str]:
    paths = []
    for d in defects:
        target = root / d.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(d.content, encoding="utf-8", newline="\n")
        paths.append(d.path)
    return paths


def open_pr(branch: str, *, root: Path = REPO, dry_run: bool = False) -> int:
    if not branch.startswith(BRANCH_PREFIX):
        print(f"refusing: {branch!r} is not a {BRANCH_PREFIX} branch", file=sys.stderr)
        return 2
    bad = problems()
    if bad:
        print("\n".join(bad), file=sys.stderr)
        return 1
    if dry_run:
        print(json.dumps({"branch": branch, **plan()}, indent=2))
        return 0
    _git("switch", "-c", branch, "origin/main", cwd=root)
    paths = plant(root)
    _git("add", "--", *paths, cwd=root)
    _git(
        "-c", "user.name=canary-control", "-c", "user.email=canary-control@users.noreply.github.com",
        "commit", "-m", "canary: planted defects, one per gate (#7155). Never merge.",
        cwd=root,
    )  # fmt: skip
    _git("push", "origin", branch, cwd=root)
    subprocess.run(
        ["gh", "pr", "create", "--base", "main", "--head", branch, "--title", f"canary: control PR {branch[7:]} (do not merge)",
         "--body", pr_body()],
        cwd=root, check=True, env={**os.environ},
    )  # fmt: skip
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan")
    op = sub.add_parser("open")
    op.add_argument("--branch", default=None)
    op.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "plan":
        print(json.dumps(plan(), indent=2))
        return 0
    return open_pr(a.branch or branch_name(), dry_run=a.dry_run)


if __name__ == "__main__":
    sys.exit(main())
