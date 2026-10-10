#!/usr/bin/env python3
"""What broke on a pull request's head, in a few lines each, and the local command that reproduces it (#4790).

    python tests/tools/ci_digest.py N            # one block per failed check
    python tests/tools/ci_digest.py N --json     # the same, machine-readable (the CI shepherd reads this)
    python tests/tools/pr_check.py N --digest    # the same, after pr_check's report

Per failed check: its triage -- `main` (a real failure of a check that also fails on main's newest commit:
main's to fix, not this PR's), `dirty` (`action_required` on a PR that conflicts with main: no checks ran; merge
origin/main and regenerate the generated files with their tools, never hand-merge them), `infra` (the runner, not the code: cancelled / startup failure / lost runner / disk /
rate limit; rerun it once), `flake` (a test listed in FLAKY failed and nothing else did; rerun it once) or `real` (a
fixer's job) -- then the job log's error lines and its last lines, ANSI and timestamps stripped, and the repro: the
local command for that check from REPRO (pr_gates' own gate and ratchet names where one exists, otherwise the tool),
filled with what the log names (the failing pytest node ids, the det cases not proven). A check with no local
equivalent (CodeQL, Muninn, the dead-key audit ...) says so.

The point is that nobody -- person or model -- reads a raw CI log or waits on CI to learn whether a fix works: the
digest says what failed, the repro runs it locally in minutes. Four `gh api` calls plus one log per failed job.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pr_check  # noqa: E402

REPO_SLUG = pr_check.REPO_SLUG
GATES = "python tests/tools/pr_gates.py"
RATCHET = GATES + " --ratchets --only-ratchets"
SWEEP = "tests/tools/box/heavy-run.sh python tests/tools/proof_sweep.py --det-only --skip-db2"

# check name (regex, matched in order) -> the local command; {tests} / {cases} are filled from the log
REPRO: list[tuple[str, str]] = [
    (r"^ruff-audit$", GATES + " --only lint"),
    (r"^mypy-audit$", GATES + " --only audits"),
    (r"^(gauntlet|unicode-gauntlet)$", GATES + " --only gauntlet"),
    (r"^Vault Sentinel$", GATES + " --only secrets"),
    (r"^X-Ray Inspector$", GATES + " --only xray"),
    (r"^crucible-audit", "tests/tools/box/golden-lock.sh " + GATES + " --only golden"),
    (r"^(full-suite|smoke-test)$", "python -m pytest -q {tests}"),
    (r"^(det|shard \d+/\d+)$", SWEEP + " --cases {cases} --work /tmp/gitgalaxy-scratch/ci-digest/sweep"),
    (r"^plan$", "python tests/tools/det_sweep_plan.py --base origin/main"),
    (r"^(compile \(.+\)|committed ports compile)$", RATCHET + " ports"),
    (r"^crosscheck$", RATCHET + " fact-crosscheck"),
    (r"^ground-truth$", RATCHET + " ground-truth"),
    (
        r"^crucible$",
        "tests/tools/box/heavy-run.sh python -m pytest -q tests/cics_crucible && tests/tools/box/heavy-run.sh "
        "python tests/tools/cics_crucible.py --ci --out /tmp/gitgalaxy-scratch/ci-digest/cics",
    ),
]
NO_LOCAL = re.compile(r"^(CodeQL|Analyze|Muninn|muninn|dead-key-audit|ast-accuracy-audit|rosetta-audit|"
                      r"flag-golden-master-changes|Supply Chain Firewall|Full Report)", re.I)  # fmt: skip

FLAKY = {"test_regex_redos", "test_many_move_statements_stay_linear"}  # #4477: wall-clock bound under CI load
INFRA_CONCLUSIONS = {"cancelled", "startup_failure", "timed_out"}
INFRA_LOG = re.compile(r"runner has received a shutdown signal|lost communication with the server|No space left on "
                       r"device|API rate limit exceeded|Could not resolve host|The operation was canceled|"
                       r"Error: The hosted runner|503 Service Unavailable|502 Bad Gateway|429 Too Many Requests|"
                       r"toomanyrequests|Connection reset by peer|ECONNRESET|TLS handshake timeout|"
                       r"Build container for action use|failed to solve: .*(registry|docker\.io)", re.I)  # fmt: skip
ERROR = re.compile(r"##\[error\]|^(FAILED|ERROR) |Traceback \(most recent call last\)|AssertionError|\bFAIL\b|"
                   r"NOT PROVEN|error: |Error: ", re.I)  # fmt: skip
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
STAMP = re.compile(r"^\d{4}-\d\d-\d\dT[\d:.]+Z ")
FAILED_TEST = re.compile(r"^FAILED (\S+::\S+)")
RUN_JOB = re.compile(r"/actions/runs/(\d+)/job/(\d+)")
UNPROVEN = re.compile(r"^\s*det (\S+)\s+NOT PROVEN")

Logs = Callable[[int], str]


def job_log(job_id: int) -> str:
    """A job's full log (`gh api .../actions/jobs/ID/logs`), or a note when it can't be fetched."""
    path = f"repos/{REPO_SLUG}/actions/jobs/{job_id}/logs"
    # gh refuses to print a log holding ANSI escapes unless told; clean() strips them
    res = subprocess.run(["gh", "api", "--allow-escape-sequences", path], capture_output=True, text=True, check=False)  # noqa: S603, S607
    return res.stdout if res.returncode == 0 else f"(log unavailable: {res.stderr.strip()[:200]})"


def clean(log: str) -> list[str]:
    return [STAMP.sub("", ANSI.sub("", line)).rstrip() for line in log.splitlines()]


def extract(log: str, tail: int = 40, max_errors: int = 25) -> dict[str, Any]:
    """The lines a reader needs: errors (deduplicated, in order), the last lines, failing tests, unproven det cases."""
    lines = [x for x in clean(log) if x.strip()]
    errors: list[str] = []
    for x in lines:
        if ERROR.search(x) and x not in errors:
            errors.append(x)
    tests = sorted({m.group(1) for x in lines if (m := FAILED_TEST.match(x))})
    cases = sorted({m.group(1) for x in lines if (m := UNPROVEN.match(x))})
    return {"errors": errors[:max_errors], "more_errors": max(0, len(errors) - max_errors), "tail": lines[-tail:],
            "tests": tests, "cases": cases}  # fmt: skip


def triage(conclusion: str, log: str, tests: list[str], mergeable_state: str | None = None) -> str:
    if conclusion == "action_required" and mergeable_state == "dirty":
        return "dirty"
    if conclusion in INFRA_CONCLUSIONS or INFRA_LOG.search(log):
        return "infra"
    names = {t.split("::")[-1].split("[")[0] for t in tests}
    if names and names <= FLAKY:
        return "flake"
    return "real"


def repro(name: str, ex: dict[str, Any], kind: str = "real") -> str | None:
    if kind == "main":
        return "fails on main too: fix main (then merge origin/main here)"
    if kind == "dirty":
        return "git merge origin/main  (then regenerate generated files with their tools; see the PR worker rules)"
    if NO_LOCAL.match(name):
        return None
    for pat, cmd in REPRO:
        if re.search(pat, name):
            return cmd.format(tests=" ".join(ex["tests"]) or "tests", cases=",".join(ex["cases"]) or "<case>")
    return GATES + " --fast"


def main_failures(api: pr_check.Api) -> set[str]:
    """The checks failing on main's newest commit (#4790): a PR failing the same check inherited it from main."""
    try:
        sha = api(f"repos/{REPO_SLUG}/commits/main")["sha"]
        runs = pr_check.paged(api, f"repos/{REPO_SLUG}/commits/{sha}/check-runs", "check_runs")
    except (SystemExit, KeyError, TypeError):
        return set()
    return {x.split(" (")[0] for x in pr_check.classify(runs, [])["failed"]}


def digest(n: int, api: pr_check.Api = pr_check.gh_api, logs: Logs = job_log) -> dict[str, Any]:
    on_main = main_failures(api)
    pr = api(f"repos/{REPO_SLUG}/pulls/{n}")
    sha = pr["head"]["sha"]
    runs = pr_check.paged(api, f"repos/{REPO_SLUG}/commits/{sha}/check-runs", "check_runs")
    failed = {x.split(" (")[0] for x in pr_check.classify(runs, [])["failed"]}
    newest: dict[str, dict[str, Any]] = {}
    for r in sorted(runs, key=lambda r: r.get("id", 0)):
        if r["name"] in failed and r.get("conclusion") not in pr_check.NEUTRAL | {None}:
            newest[r["name"]] = r
    out = []
    for name, r in sorted(newest.items()):
        actions = (r.get("app") or {}).get("slug") == "github-actions"
        log = logs(r["id"]) if actions else ""
        ex = extract(log)
        kind = triage(r.get("conclusion") or "", log, ex["tests"], pr.get("mergeable_state"))
        if kind == "real" and name in on_main:
            kind = "main"  # the same check fails on main: fix main, not this PR
        ids = RUN_JOB.search(r.get("details_url") or "")
        out.append({"check": name, "conclusion": r.get("conclusion"), "url": r.get("html_url") or r.get("details_url"),
                    "run_id": int(ids.group(1)) if ids else None, "job_id": int(ids.group(2)) if ids else None,
                    "triage": kind, "repro": repro(name, ex, kind), **ex})  # fmt: skip
    return {"number": n, "head_sha": sha, "mergeable_state": pr.get("mergeable_state"), "failed": out}


def render(d: dict[str, Any]) -> str:
    if not d["failed"]:
        return f"PR #{d['number']} @ {d['head_sha'][:12]}: no failed checks"
    out = [f"PR #{d['number']} @ {d['head_sha'][:12]}: {len(d['failed'])} failed check(s)"]
    for f in d["failed"]:
        out += ["", f"== {f['check']} ({f['conclusion']}) -- {f['triage']}", f"   {f['url']}",
                f"   repro: {f['repro'] or 'no local equivalent; read the check page'}"]  # fmt: skip
        if f["tests"]:
            out.append("   failing tests: " + " ".join(f["tests"]))
        if f["cases"]:
            out.append("   det cases not proven: " + ",".join(f["cases"]))
        if f["errors"]:
            out += ["   errors:"] + [f"     {x[:240]}" for x in f["errors"]]
            if f["more_errors"]:
                out.append(f"     ... {f['more_errors']} more")
        out += ["   log tail:"] + [f"     {x[:240]}" for x in f["tail"]]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("number", type=int)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    d = digest(args.number)
    print(json.dumps(d, indent=1) if args.json else render(d))
    return 1 if d["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
