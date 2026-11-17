#!/usr/bin/env python3
"""Whether a pull request must go through the all-OS matrix before it merges (#8425).

    python tests/tools/matrix_plan.py --pr N          # plan one PR (needs gh)
    python tests/tools/matrix_plan.py --replay 50     # how many of the last N merged PRs the rule would have selected

PRs run Linux only; `full-suite-gate.yml` (OS x Python) runs on main. Two classes of change turned main red on another
platform within a week (#8165 -> #8167 -> #8181, #8185 -> #8195), so the shepherd treats a PR as carrying
`shepherd:matrix` (dispatch on the head, auto-merge waits for green) when it:

  (a) fixes a `ci-red-main` issue (a closing keyword or `Part of` naming an issue with that label), or
  (b) adds or changes a test (tests/**/*.py) that
        - shells out to a platform tool (rsync, sed, find, ...) with no platform guard in the added lines,
        - links, chmods or makes fifos with no platform guard,
        - creates files or directories under names that differ only by case, or reads path case (casefold /
          normcase / samefile) next to file creation.

The rule is narrow on purpose: the legs are expensive and the runner pool is small. Anything unreadable (no file list,
a truncated list) selects nothing. Stdlib only. `select_for` is pure; `plan_pr` reads through an injected api.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Callable
from typing import Any

RED_MAIN_LABEL = "ci-red-main"
REPO_SLUG = "squid-protocol/gitgalaxy"
FILE_CAP = 300  # GitHub truncates a PR's file list here: an unreadable list selects nothing
CLOSING = re.compile(r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?|part of)\s+#(\d+)", re.I)

TOOLS = "rsync|sed|find|awk|xargs|chmod|chown|cp|mv|ln|tar|diff|patch|touch|mkfifo|stat|du|df|ls|cat|grep|dos2unix"
_CALL = re.compile(r"subprocess\.|os\.system\(|os\.popen\(|\bPopen\(|check_output\(|check_call\(|shlex\.")
_TOOL = re.compile(rf"""["'](?:{TOOLS})(?:["'\s])""")
_GUARD = re.compile(
    r"sys\.platform|platform\.system|os\.name\b|skipif|shutil\.which|importorskip|pytest\.skip|_IS_WINDOWS|IS_WINDOWS"
)
_LINK = re.compile(
    r"symlink_to\(|hardlink_to\(|os\.symlink\(|os\.link\(|os\.chmod\(|\.chmod\(|os\.mkfifo\(|os\.chown\("
)
_CREATE = re.compile(
    r"\.mkdir\(|makedirs\(|os\.mkdir\(|\.write_text\(|\.write_bytes\(|\.touch\(|copytree\(|shutil\.copy"
)
_CASE_READ = re.compile(r"\.casefold\(|normcase\(|samefile\(")
_SEGMENT = re.compile(r"""["']([A-Za-z0-9_][\w.\-]*(?:/[\w.\-]+)*)["']""")


def _added(patch: str) -> str:
    return "\n".join(x[1:] for x in patch.splitlines() if x.startswith("+") and not x.startswith("+++"))


def _case_collision(text: str) -> bool:
    """Two creation lines whose path literals match case-insensitively but not exactly."""
    seen: dict[str, str] = {}
    for line in text.splitlines():
        if not (_CREATE.search(line) or re.search(r"/\s*[\"']", line)):
            continue
        for seg in _SEGMENT.findall(line):
            if "/" not in seg and "." not in seg and not seg[:1].isalpha():
                continue
            old = seen.setdefault(seg.casefold(), seg)
            if old != seg:
                return True
    return False


def test_reasons(path: str, patch: str) -> list[str]:
    """Why one added or changed test file needs the other platforms (empty: it does not)."""
    text = _added(patch)
    guarded = bool(_GUARD.search(text))
    out: list[str] = []
    if _CALL.search(text) and _TOOL.search(text) and not guarded:
        out.append(f"{path}: shells out to a platform tool with no platform guard")
    if _LINK.search(text) and not guarded:
        out.append(f"{path}: links / chmods with no platform guard")
    if _CREATE.search(text) and (_case_collision(text) or _CASE_READ.search(text)):
        out.append(f"{path}: creates files and depends on path case")
    return out


def closing_issues(body: str | None) -> list[int]:
    return sorted({int(x) for x in CLOSING.findall(body or "")})


def select_for(
    files: list[dict[str, Any]] | None, body: str | None, red_main_issues: set[int] | frozenset[int] = frozenset()
) -> list[str]:
    """The reasons the PR needs the matrix; an empty list means it does not. `files`: the PR files API records
    (filename, status, patch), None when unreadable. `red_main_issues`: the closing issues that carry the label."""
    reasons = [f"fixes a `{RED_MAIN_LABEL}` issue (#{n})" for n in closing_issues(body) if n in red_main_issues]
    if files is None or len(files) >= FILE_CAP:
        return reasons
    for f in files:
        name = f.get("filename") or ""
        base = name.rsplit("/", 1)[-1]
        is_test = (
            name.startswith("tests/") and base.endswith(".py") and (base.startswith("test_") or base == "conftest.py")
        )
        if is_test and f.get("status") != "removed" and f.get("patch"):
            reasons += test_reasons(name, f["patch"])
    return reasons


def plan_pr(api: Callable[[str], Any], number: int, body: str | None, repo: str = REPO_SLUG) -> list[str]:
    """select_for over a live PR. Every read that fails selects nothing for its half."""
    red: set[int] = set()
    for n in closing_issues(body):
        try:
            doc = api(f"repos/{repo}/issues/{n}")
        except SystemExit:
            continue
        if any((x or {}).get("name") == RED_MAIN_LABEL for x in (doc or {}).get("labels") or []):
            red.add(n)
    files: list[dict[str, Any]] | None
    try:
        files = []
        for page in range(1, 4):
            got = api(f"repos/{repo}/pulls/{number}/files?per_page=100&page={page}")
            files += got
            if len(got) < 100:
                break
    except SystemExit:
        files = None
    return select_for(files, body, red)


def _gh(path: str) -> Any:
    proc = subprocess.run(["gh", "api", path], capture_output=True, text=True, check=False)
    if proc.returncode:
        raise SystemExit(f"gh api {path} failed")
    return json.loads(proc.stdout)


def replay(n: int, api: Callable[[str], Any] = _gh, repo: str = REPO_SLUG) -> dict[str, Any]:
    """Plan the last n merged PRs: how many it would have selected, per reason class and per week."""
    proc = subprocess.run(
        ["gh", "pr", "list", "-R", repo, "--state", "merged", "--limit", str(n), "--json", "number,body,mergedAt"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode:
        raise SystemExit("gh pr list failed")
    prs = json.loads(proc.stdout)
    picked = []
    for pr in prs:
        why = plan_pr(api, pr["number"], pr.get("body"), repo)
        if why:
            picked.append({"number": pr["number"], "mergedAt": pr.get("mergedAt"), "reasons": why})
    stamps = sorted(p["mergedAt"] for p in prs if p.get("mergedAt"))
    return {
        "planned": len(prs),
        "selected": len(picked),
        "share": round(len(picked) / len(prs), 3) if prs else 0.0,
        "span": [stamps[0], stamps[-1]] if stamps else [],
        "prs": picked,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pr", type=int)
    ap.add_argument("--replay", type=int, metavar="N")
    args = ap.parse_args(argv)
    try:
        if args.replay:
            print(json.dumps(replay(args.replay), indent=1))
        elif args.pr:
            body = _gh(f"repos/{REPO_SLUG}/pulls/{args.pr}").get("body")
            print(json.dumps({"reasons": plan_pr(_gh, args.pr, body)}, indent=1))
        else:
            ap.error("give --pr or --replay")
    except SystemExit as e:
        print(f"matrix_plan: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
