#!/usr/bin/env python3
"""Does each path-filtered workflow trigger on what it reads? (#4825)

    python tests/tools/workflow_inputs.py          # list the gaps; exit 1 when there are any

A pull_request trigger with `paths:` runs a workflow only when a changed file matches. When the workflow runs a
script, or reads the crucible pins, that its filter does not match, a PR can change what the check would say and the
check never runs -- the gate is silently skipped, and a later, unrelated PR that does trigger it fails instead. Two
rules, checked for every workflow whose pull_request trigger has `paths:` (a trigger without them runs on every PR):

  scripts  every repo script a step runs (`python[3] [gitgalaxy/]tests/... .py`, `[gitgalaxy/]gitgalaxy/....py`) is
           matched by the filter -- the check's own code is an input to the check;
  pins     a workflow that reads the crucible pins (crucible_pins.py / tests/crucible_pins.toml) triggers on
           tests/crucible_pins.toml -- the pinned corpus is an input too.

GitHub's path-filter globs: `*` matches within one path segment, `**` across segments, a leading `!` excludes (the
last matching pattern decides). Checkouts under `path: gitgalaxy` are normalised (the `gitgalaxy/` prefix of a
`gitgalaxy/tests/...` path is dropped). ALLOW lists a gap that is intended, with the reason.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO / ".github" / "workflows"
PINS = "tests/crucible_pins.toml"
SCRIPT = re.compile(r"\bpython3?\s+(?:-[A-Za-z]\s+\S+\s+)*((?:gitgalaxy/)?(?:tests|gitgalaxy)/[\w./-]+\.py)\b")
# (workflow file, input) -> why it is deliberately not a trigger
ALLOW: dict[tuple[str, str], str] = {}


def glob_re(pattern: str) -> re.Pattern[str]:
    """GitHub's filter glob as a regex: `**` any depth, `*` one segment, `?` one character."""
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif pattern.startswith("**", i):
            out, i = out + ".*", i + 2
        elif pattern[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif pattern[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(pattern[i]), i + 1
    return re.compile(out + r"\Z")


def triggers(paths: list[str], f: str) -> bool:
    """Whether `paths` (with `!` exclusions) selects the changed file `f`: the last matching pattern decides."""
    hit = False
    for p in paths:
        neg = p.startswith("!")
        if glob_re(p[1:] if neg else p).match(f):
            hit = not neg
    return hit


def pr_paths(doc: dict) -> list[str] | None:
    on = doc.get(True, doc.get("on")) or {}
    pr = on.get("pull_request") if isinstance(on, dict) else None
    return list(pr["paths"]) if isinstance(pr, dict) and pr.get("paths") else None


def inputs(text: str) -> set[str]:
    """The repo scripts the workflow runs, and the pins file when it reads the pins."""
    found = set()
    for m in SCRIPT.finditer(text):
        p = m.group(1)
        p = p[len("gitgalaxy/") :] if p.startswith("gitgalaxy/tests/") or p.startswith("gitgalaxy/gitgalaxy/") else p
        if (REPO / p).is_file():
            found.add(p)
    if "crucible_pins" in text:
        found.add(PINS)
    return found


def gaps() -> list[tuple[str, str]]:
    out = []
    for wf in sorted(WORKFLOWS.glob("*.yml")):
        text = wf.read_text(encoding="utf-8")
        paths = pr_paths(yaml.safe_load(text) or {})
        if paths is None:
            continue
        for f in sorted(inputs(text)):
            if not triggers(paths, f) and (wf.name, f) not in ALLOW:
                out.append((wf.name, f))
    return out


def main() -> int:
    found = gaps()
    for wf, f in found:
        print(f"{wf}: reads {f} but its pull_request paths do not trigger on it")
    print(f"{len(found)} gap(s)" if found else "every path-filtered workflow triggers on what it reads")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
