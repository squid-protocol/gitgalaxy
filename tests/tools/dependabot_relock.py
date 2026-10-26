#!/usr/bin/env python3
"""Relock a Dependabot pull request on the hash-pinned requirement sets with our own compiler (#4918).

Run by .github/workflows/dependabot-relock.yml (pull_request_target, Dependabot's own pushes only):

    python tests/tools/dependabot_relock.py --event-path "$GITHUB_EVENT_PATH" --workdir relock-pr

Dependabot cannot write ci/requirements/*.txt or templates/requirements/*.txt: it compiles a flat lockfile on its own
Python, which drops every python_full_version marker (numpy, scipy, pandas, xgboost... split across 3.10/3.11/3.12)
and rewrote the shipped pin `gitgalaxy==` as `gitgalaxy[full]==` (#5368, #5790, #5792 all went red that way).
Version updates can be ignored in dependabot.yml, but security updates cannot, so every such PR is repaired here:

  1. the PR may touch only files under ci/requirements/ and templates/requirements/ (anything else: refuse);
  2. the PR head is checked out beside this checkout and main is merged into it (a conflict: refuse);
  3. the packages Dependabot bumped are read off its .txt diff (a version main's lockfile does not have);
  4. the .txt files go back to main's, the PR's .in files stay, and tests/tools/pin_requirements.py recompiles
     with `-P name==version` for each bump (seeded from the committed lock, so nothing else moves);
  5. a relocked templates/requirements is committed, then stamped into the templates (stamp_template_pins.py).

The workflow pushes the result to the PR branch. Only this checkout's (main's) tools run: after step 2 the PR tree's
tests/tools is main's, because step 1 guarantees the PR changed nothing outside the two requirement directories.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQ_DIRS = ("ci/requirements/", "templates/requirements/")
TEMPLATE_DIR = "templates/requirements/"
PIN = re.compile(r"^([A-Za-z0-9_.\-]+)(?:\[[^\]]*\])?==([^\s;\\]+)", re.M)
DEPENDABOT_BUMP = re.compile(
    r"^\s*-\s*dependency-name:\s*([A-Za-z0-9_.\-]+)\s*\n\s*dependency-version:\s*([^\s\n]+)",
    re.M,
)


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_pins(text: str) -> dict[str, set[str]]:
    """Map each pinned package (normalised name, extras dropped) to the set of versions a lockfile pins."""
    pins: dict[str, set[str]] = {}
    for name, ver in PIN.findall(text):
        pins.setdefault(_norm(name), set()).add(ver)
    return pins


def parse_dependabot_metadata(text: str) -> dict[str, set[str]]:
    """Extract (dependency-name, dependency-version) pairs from Dependabot's commit/PR YAML footer.

    Needed when Dependabot's pip-compile drops an "unsafe" package like setuptools or pip from bootstrap.txt
    instead of writing the new version (#6300), leaving no new version in the .txt diff for parse_pins() to see.
    """
    bumps: dict[str, set[str]] = {}
    for name, ver in DEPENDABOT_BUMP.findall(text or ""):
        bumps.setdefault(_norm(name), set()).add(ver)
    return bumps


def bumped(base: dict[str, set[str]], head: dict[str, set[str]]) -> dict[str, set[str]]:
    """Versions the head pins that the base does not (a flattened multi-version pin adds nothing new)."""
    return {name: vers - base.get(name, set()) for name, vers in head.items() if vers - base.get(name, set())}


def upgrade_args(bumps: dict[str, set[str]]) -> list[str]:
    """`-P` arguments: an exact target for a single new version, a plain upgrade otherwise."""
    args: list[str] = []
    for name in sorted(bumps):
        vers = bumps[name]
        args += ["-P", f"{name}=={next(iter(vers))}" if len(vers) == 1 else name]
    return args


def outside_req_dirs(paths: list[str]) -> list[str]:
    return [p for p in paths if not p.startswith(REQ_DIRS)]


def git(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout  # noqa: S603, S607


def run(event_path: Path, workdir: Path) -> int:
    event = json.loads(event_path.read_text(encoding="utf-8"))
    pr = event["pull_request"]
    number, head_sha = pr["number"], pr["head"]["sha"]

    git("fetch", "-q", "origin", "main", f"+refs/pull/{number}/head:refs/relock/head")
    if git("rev-parse", "refs/relock/head").strip() != head_sha:
        print(f"#{number}: head moved past {head_sha[:9]}; the newer push gets its own run")
        return 0
    changed = git("diff", "--name-only", "origin/main...refs/relock/head").split()
    foreign = outside_req_dirs(changed)
    if foreign:
        print(f"::error::#{number} changes files outside the requirement sets; not relocking: {foreign}")
        return 1

    git("worktree", "add", "-q", "--detach", str(workdir), "refs/relock/head")
    git("merge", "-q", "--no-edit", "origin/main", cwd=workdir)

    txt = [p for p in changed if p.endswith(".txt")]
    bumps: dict[str, set[str]] = {}
    for path in txt:
        base = parse_pins(git("show", f"origin/main:{path}") if _on_main(path) else "")
        for name, vers in bumped(base, parse_pins((workdir / path).read_text(encoding="utf-8"))).items():
            bumps.setdefault(name, set()).update(vers)
    meta_text = "\n".join(
        [
            str(pr.get("body") or ""),
            git("log", "--format=%B", "origin/main..refs/relock/head"),
        ]
    )
    for name, vers in parse_dependabot_metadata(meta_text).items():
        bumps.setdefault(name, set()).update(vers)
    if not bumps and not any(p.endswith(".in") for p in changed):
        print(f"#{number}: no pin changes to relock")
        return 0

    present = [p for p in txt if _on_main(p)]
    if present:
        git("checkout", "origin/main", "--", *present, cwd=workdir)
    targets = sorted({"templates" if p.startswith(TEMPLATE_DIR) else "ci" for p in changed})
    pin = workdir / "tests" / "tools" / "pin_requirements.py"
    for target in targets:
        subprocess.run([sys.executable, str(pin), "--target", target, *upgrade_args(bumps)], cwd=workdir, check=True)  # noqa: S603

    git("add", "--", *REQ_DIRS, cwd=workdir)
    if not git("diff", "--cached", "--name-only", cwd=workdir).strip():
        print(f"#{number}: already locked the way pin_requirements.py writes it")
        return 0
    names = ", ".join(sorted(bumps)) or "the .in changes"
    git("commit", "-q", "-m", f"build(deps): relock {names} with tests/tools/pin_requirements.py (#4918)", cwd=workdir)
    if "templates" in targets:
        stamp = workdir / "tests" / "tools" / "stamp_template_pins.py"
        subprocess.run([sys.executable, str(stamp)], cwd=workdir, check=True)  # noqa: S603
        git("add", "--", "templates", cwd=workdir)
        if git("diff", "--cached", "--name-only", cwd=workdir).strip():
            git(
                "commit",
                "-q",
                "-m",
                "build(deps): stamp the relocked lockfiles into the templates (#4918)",
                cwd=workdir,
            )
    print(f"#{number}: relocked {names}")
    return 0


def _on_main(path: str) -> bool:
    probe = ["git", "cat-file", "-e", f"origin/main:{path}"]
    return subprocess.run(probe, cwd=ROOT, capture_output=True, check=False).returncode == 0  # noqa: S603


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--event-path", type=Path, required=True)
    parser.add_argument("--workdir", type=Path, required=True, help="where the PR head is checked out and relocked")
    args = parser.parse_args(argv)
    return run(args.event_path, args.workdir.resolve())


if __name__ == "__main__":
    sys.exit(main())
