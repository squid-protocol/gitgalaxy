#!/usr/bin/env python3
"""The weekly control PR (#7155, part 2): a real PR from a `canary/` branch carrying one planted defect per gate.

A green gate means something only if it can go red. `gate_controls.py` proves each gate's logic on a fixture; this opens
a real, ready-for-review PR so the workflow around each gate (its shell, its reach, its skip paths) is exercised too.

    python tests/tools/canary_control.py plan             # the detection matrix to expect, as JSON
    python tests/tools/canary_control.py open [--dry-run]  # branch off main, plant, push, open the PR
    python tests/tools/canary_control.py open --clean      # the clean control PR: nothing planted, nothing may go red
    python tests/tools/canary_control.py results [--dry-run]  # matrix, comment, miss issue, close, delete the branch

Every defect is inert: a new file, no network, no secret, nothing under `.github/` or a release path. The PR body carries
a `canary-expect` JSON marker (the gates that must go red) that `results` reads. `results` never merges or labels: it
closes the PR, deletes the branch, and opens a `priority: high` issue for a miss (a planted defect no gate caught) or a
false alarm (a red check on the clean PR). The `ci-gate` hold and the merge-label refusal belong to the shepherd
(owner-only) and are not here. A `canary/` PR with no marker is closed (it cannot be judged), and a `canary/` branch with
no open PR is deleted.
Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_controls  # noqa: E402

BRANCH_PREFIX = "canary/"
MARKER = "canary-expect"
# A planted file may never land here: workflows, release paths, the shepherd, secrets.
FORBIDDEN_PREFIXES = (".github/", "release/", "dist/", ".claude/")
FORBIDDEN_NAMES = ("pyproject.toml", ".env", "publish.yml")
# A gate in gate_controls.GATES is not always one check run: the ruff-audit gates share the `ruff-audit` job, and the
# suite reports as `full-suite part N/M`. A run matches when its name is the value or starts with it plus a space.
CHECK_OF = {
    "ruff-audit (lint)": "ruff-audit",
    "ruff-audit (real ruff)": "ruff-audit",
    "ruff-audit (format)": "ruff-audit",
    "mypy-audit": "mypy-audit",
    "full-suite": "full-suite",
    "doc-refs-audit": "doc-refs-audit",
}
RED = frozenset({"failure", "timed_out", "startup_failure", "action_required"})
HOLD = "ci-gate"  # the shepherd's hold fails a canary on purpose: never a false alarm
MAX_AGE = timedelta(hours=24)  # a check still pending after this long counts as a miss


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


# The clean control: one valid twin per defect area, so the plan jobs run the same gates the defect PR reaches (a
# docs-only PR makes the code gates skip, and a skipped gate cannot false-alarm).
CLEAN_SET = (
    Defect(
        "clean-code",
        "gitgalaxy/canary_probe_clean.py",
        '"""Canary probe: a clean module (typed, formatted, nothing unused)."""\n\n\ndef probe() -> int:\n    return 1\n',
        (),
        "a clean typed module: lint, format and mypy-audit must stay green",
    ),
    Defect(
        "clean-test",
        "tests/tools/test_canary_probe_clean.py",
        '"""Canary probe: a test that passes."""\n\n\ndef test_the_clean_probe():\n    assert 1 == 1\n',
        (),
        "a passing test: the suite must stay green",
    ),
    Defect(
        "clean-doc",
        "docs/canary_probe_clean.md",
        "# Canary probe (clean)\n\nSee [the CI page](ci.md). A control PR with nothing wrong in it: no gate may go red.\n",
        (),
        "a clean doc with a live link: every gate must stay green",
    ),
)


def problems(defects: tuple[Defect, ...] = DEFECTS, *, clean: bool = False) -> list[str]:
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
        out += [f"{d.key}: no check mapped for {g!r}" for g in d.red if g not in CHECK_OF]
        if not d.red and not clean:
            out.append(f"{d.key}: expects no gate to go red")
    return out


def plan(defects: tuple[Defect, ...] = DEFECTS) -> dict:
    """The detection matrix to expect: each planted file and the gates that must go red on it."""
    return {
        "kind": "clean" if defects == CLEAN_SET else "defects",
        "defects": [{"key": d.key, "path": d.path, "what": d.what, "red": list(d.red)} for d in defects],
        "must_go_red": sorted({g for d in defects for g in d.red}),
    }


def branch_name(now: datetime | None = None, *, clean: bool = False) -> str:
    return BRANCH_PREFIX + (now or datetime.now(UTC)).strftime("%Y%m%dT%H%MZ") + ("-clean" if clean else "")


def pr_body(defects: tuple[Defect, ...] = DEFECTS) -> str:
    rows = "\n".join(f"- `{d.path}`: {d.what}; must turn red: {', '.join(d.red) or 'nothing'}" for d in defects)
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


def open_pr(branch: str, *, root: Path = REPO, dry_run: bool = False, clean: bool = False) -> int:
    if not branch.startswith(BRANCH_PREFIX):
        print(f"refusing: {branch!r} is not a {BRANCH_PREFIX} branch", file=sys.stderr)
        return 2
    defects = CLEAN_SET if clean else DEFECTS
    bad = problems(defects, clean=clean)
    if bad:
        print("\n".join(bad), file=sys.stderr)
        return 1
    if dry_run:
        print(json.dumps({"branch": branch, **plan(defects)}, indent=2))
        return 0
    _git("switch", "-c", branch, "origin/main", cwd=root)
    paths = plant(root, defects)
    _git("add", "--", *paths, cwd=root)
    _git(
        "-c", "user.name=canary-control", "-c", "user.email=canary-control@users.noreply.github.com",
        "commit", "-m", "canary: control PR (#7155). Never merge.",
        cwd=root,
    )  # fmt: skip
    _git("push", "origin", branch, cwd=root)
    subprocess.run(
        ["gh", "pr", "create", "--base", "main", "--head", branch, "--title", f"canary: {'clean ' if clean else ''}control PR {branch[7:]} (do not merge)",
         "--body", pr_body(defects)],
        cwd=root, check=True, env={**os.environ},
    )  # fmt: skip
    return 0


def _matches(gate: str, name: str) -> bool:
    check = CHECK_OF[gate]
    return name == check or name.startswith(check + " ")


def _seconds(run: dict) -> int | None:
    try:
        a = datetime.fromisoformat(run["started_at"].replace("Z", "+00:00"))
        b = datetime.fromisoformat(run["completed_at"].replace("Z", "+00:00"))
    except (KeyError, AttributeError, ValueError, TypeError):
        return None
    return int((b - a).total_seconds())


def evaluate(expect: dict, runs: list[dict], *, age: timedelta) -> dict:
    """Compare the check runs on a canary head with the marker's expectation.

    Each gate that must go red is `red` (a matching run failed), `pending` (a matching run has not finished, or none has
    appeared and the PR is under MAX_AGE) or `MISS` (everything matching passed, was skipped or cancelled, or no run ever
    came: a blind gate). On a clean PR any red run except the shepherd's hold is a `false_alarm`.
    """
    rows = []
    for gate in expect.get("must_go_red", []):
        hit = [r for r in runs if _matches(gate, r.get("name", ""))]
        failed = [r for r in hit if r.get("conclusion") in RED]
        if failed:
            verdict = "red"
        elif age < MAX_AGE and (not hit or any(r.get("status") != "completed" for r in hit)):
            verdict = "pending"
        else:
            verdict = "MISS"
        secs = [s for s in (_seconds(r) for r in (failed or hit)) if s is not None]
        rows.append({"gate": gate, "check": CHECK_OF[gate], "verdict": verdict, "seconds": max(secs) if secs else None})
    false_alarms: list[str] = []
    if expect.get("kind") == "clean":
        false_alarms = sorted({r["name"] for r in runs if r.get("conclusion") in RED and r.get("name") != HOLD})
    pending = any(r["verdict"] == "pending" for r in rows) or (
        expect.get("kind") == "clean" and age < MAX_AGE and any(r.get("status") != "completed" for r in runs)
    )
    return {
        "kind": expect.get("kind", "defects"),
        "rows": rows,
        "misses": [r["gate"] for r in rows if r["verdict"] == "MISS"],
        "false_alarms": false_alarms,
        "checks_run": len({r["name"] for r in runs if r.get("conclusion") not in (None, "skipped")}),
        "settled": not pending or age >= MAX_AGE,
    }


def render(result: dict) -> str:
    """The detection matrix as a PR comment."""
    lines = ["## Canary detection matrix (#7155)", ""]
    if result["rows"]:
        lines += ["| gate | check | verdict | seconds |", "|---|---|---|---|"]
        lines += [
            f"| {r['gate']} | {r['check']} | {r['verdict']} | {r['seconds'] if r['seconds'] is not None else ''} |"
            for r in result["rows"]
        ]
    if result["kind"] == "clean":
        fa = ", ".join(result["false_alarms"]) or "none"
        lines += [
            "",
            f"Clean control. False alarms (red checks): {fa}. Checks that ran: {result.get('checks_run', 0)}.",
        ]
    return "\n".join(lines) + "\n"


def _gh(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *args], check=check, capture_output=True, text=True)


def _expect(body: str) -> dict | None:
    m = re.search(rf"<!-- {MARKER} (\{{.*\}}) -->", body or "")
    return json.loads(m.group(1)) if m else None


def _runs(sha: str) -> list[dict]:
    out = _gh("api", "--paginate", f"repos/{{owner}}/{{repo}}/commits/{sha}/check-runs",
              "--jq", ".check_runs[] | {name,status,conclusion,started_at,completed_at}").stdout  # fmt: skip
    return [json.loads(line) for line in out.splitlines() if line.strip()]


def _issue(title: str, body: str) -> bool:
    """Raise a `priority: high` issue, or comment on the open one with the same title (a blind gate is one issue, not one a week).

    Returns False when neither could be done: the caller leaves the canary PR open so the next run tries again.
    """
    found = _gh("issue", "list", "--state", "open", "--label", "priority: high", "--search", f'"{title}" in:title',
                "--json", "number,title", check=False)  # fmt: skip
    try:
        same = [i["number"] for i in json.loads(found.stdout or "[]") if i.get("title") == title]
    except (ValueError, TypeError, KeyError):
        same = []
    if same:
        return _gh("issue", "comment", str(same[0]), "--body", body, check=False).returncode == 0
    return (
        _gh("issue", "create", "--title", title, "--label", "priority: high", "--body", body, check=False).returncode
        == 0
    )


def settle(pr: dict, *, dry_run: bool = False, now: datetime | None = None) -> str:
    """Evaluate one canary PR; when settled post the matrix, raise issues, close it and delete the branch."""
    branch = pr["headRefName"]
    if not branch.startswith(BRANCH_PREFIX):
        return "skipped"  # never touch a PR that is not from a canary/ branch
    expect = _expect(pr.get("body", ""))
    if expect is None:
        # A canary/ PR whose marker was lost cannot be judged, and would stay open for ever: close it, say why.
        n = str(pr["number"])
        if dry_run:
            return "dry-run"
        _gh(
            "pr",
            "comment",
            n,
            "--body",
            "Canary control PR with no `canary-expect` marker: cannot be judged. Closed. #7155",
        )
        return _close(n, branch)
    created = datetime.fromisoformat(pr["createdAt"].replace("Z", "+00:00"))
    result = evaluate(expect, _runs(pr["headRefOid"]), age=(now or datetime.now(UTC)) - created)
    if dry_run:
        print(json.dumps({"pr": pr["number"], **result}, indent=2))
        return "dry-run"
    if not result["settled"]:
        return "pending"
    n = str(pr["number"])
    text = render(result)
    _gh("pr", "comment", n, "--body", text)
    raised = [
        _issue(
            f"Canary miss: gate {gate} stayed green on a planted defect",
            f"The control PR #{n} planted a defect the `{gate}` gate should have failed, and it did not. "
            f"The gate is blind, not the code. #7155\n\n{text}",
        )  # fmt: skip
        for gate in result["misses"]
    ]
    if result["false_alarms"]:
        raised.append(
            _issue(
                f"Canary false alarm: the clean control PR #{n} went red",
                f"A PR with nothing wrong in it failed: {', '.join(result['false_alarms'])}. #7155\n\n{text}",
            )  # fmt: skip
        )
    if not all(raised):
        return "issue-failed"  # the PR stays open: the next run settles it again
    return _close(n, branch)


def _close(n: str, branch: str) -> str:
    closed = _gh("pr", "close", n, "--delete-branch", check=False)
    if closed.returncode != 0:
        _issue(
            f"Canary PR #{n} did not close",
            f"`gh pr close --delete-branch` failed on `{branch}`: {closed.stderr.strip()}. Close it by hand. #7155",
        )
        return "close-failed"
    return "closed"


def sweep_orphans(open_heads: set[str], *, dry_run: bool = False) -> list[str]:
    """Delete every `canary/` branch no open PR carries (a failed `gh pr create`, a PR closed by hand)."""
    out = _gh("api", "--paginate", f"repos/{{owner}}/{{repo}}/git/matching-refs/heads/{BRANCH_PREFIX}",
              "--jq", ".[].ref").stdout  # fmt: skip
    outcomes = []
    for ref in out.split():
        name = ref.removeprefix("refs/heads/")
        if not name.startswith(BRANCH_PREFIX) or name in open_heads:
            continue
        if dry_run:
            outcomes.append(f"orphan:{name}")
            continue
        gone = _gh("api", "-X", "DELETE", f"repos/{{owner}}/{{repo}}/git/refs/heads/{name}", check=False)
        if gone.returncode != 0:
            _issue(f"Canary branch {name} was not deleted",
                   f"No open PR carries `{name}` and deleting it failed: {gone.stderr.strip()}. Delete it by hand. #7155")  # fmt: skip
            outcomes.append("orphan-delete-failed")
        else:
            outcomes.append("orphan-deleted")
    return outcomes


def results(*, dry_run: bool = False) -> int:
    listed = _gh("pr", "list", "--state", "open", "--limit", "100",
                 "--json", "number,headRefName,headRefOid,body,createdAt").stdout  # fmt: skip
    prs = [pr for pr in json.loads(listed) if pr["headRefName"].startswith(BRANCH_PREFIX)]
    outcomes = [settle(pr, dry_run=dry_run) for pr in prs]
    # A PR still pending keeps its branch: its head is in `prs`, so only a branch with no open PR is an orphan.
    outcomes += sweep_orphans({pr["headRefName"] for pr in prs}, dry_run=dry_run)
    print(json.dumps(outcomes))
    return 1 if {"close-failed", "orphan-delete-failed", "issue-failed"} & set(outcomes) else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan")
    op = sub.add_parser("open")
    op.add_argument("--branch", default=None)
    op.add_argument("--dry-run", action="store_true")
    op.add_argument("--clean", action="store_true")
    rp = sub.add_parser("results")
    rp.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "plan":
        print(json.dumps(plan(), indent=2))
        return 0
    if a.cmd == "results":
        return results(dry_run=a.dry_run)
    return open_pr(a.branch or branch_name(clean=a.clean), dry_run=a.dry_run, clean=a.clean)


if __name__ == "__main__":
    sys.exit(main())
