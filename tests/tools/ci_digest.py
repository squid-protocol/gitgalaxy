#!/usr/bin/env python3
"""What broke on a pull request's head, in a few lines each, and the local command that reproduces it (#4790).

    python tests/tools/ci_digest.py N            # one block per failed check
    python tests/tools/ci_digest.py N --json     # the same, machine-readable (the CI shepherd reads this)
    python tests/tools/pr_check.py N --digest    # the same, after pr_check's report

Per failed check: its triage -- `main` (a real failure of a check that also fails on main's newest commit:
main's to fix, not this PR's), `dirty` (`action_required` on a PR that conflicts with main: no checks ran; merge
origin/main and regenerate the generated files with their tools, never hand-merge them), `infra` (the runner, not the code: cancelled / startup failure / lost runner / disk /
rate limit, or (#5273) a check whose job dependency failed as infra; rerun it once), `flake` (a test listed in FLAKY
failed and nothing else did, only the time ratchet failed on tests outside the PR diff or within RATCHET_SLACK x their
limit, or the first attempt of a check the flake-history cache learned is flaky failed; rerun it once) or `real` (a fixer's job).
A roll-up check (full-suite, ground-truth, det) takes the triage of its failed part jobs. `main` is also a stale base
(#5273): the failing tests' files changed on origin/main since the PR's merge-base, so `git merge origin/main` is the
whole fix (also when main changed engine source and this PR touches none of it, #5276) -- then the job log's error lines and its last lines, ANSI and timestamps stripped, and the repro: the
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
    (r"^Pre-gate \(", GATES + " --only secrets xray"),  # #5132: Vault Sentinel, X-Ray and Supply Chain in one job
    (r"^(Vault Sentinel|X-Ray Inspector)$", GATES + " --only secrets xray"),  # the pre-#5132 job names
    (r"^crucible-audit", "tests/tools/box/golden-lock.sh " + GATES + " --only golden"),
    (r"^(full-suite|smoke-test)( part \d+/\d+)?$", "python -m pytest -q {tests}"),  # #4828: the suite runs in parts
    (r"^(det|shard \d+/\d+)$", SWEEP + " --cases {cases} --work /tmp/gitgalaxy-scratch/ci-digest/sweep"),
    (
        r"^db2 \d+/\d+$",
        SWEEP.replace("--skip-db2", "--db2-only") + " --cases {cases} --work /tmp/gitgalaxy-scratch/ci-digest/sweep",
    ),
    (r"^plan$", "python tests/tools/det_sweep_plan.py --base origin/main"),
    (r"^(compile \(.+\)|committed ports compile)$", RATCHET + " ports"),
    (r"^crosscheck$", RATCHET + " fact-crosscheck"),
    # the parts run pytest over tests/cobol_mainframe/ (mainframe-ground-truth.yml); --fast runs none of it
    (r"^ground-truth part \d+/\d+$", "python -m pytest -q {tests}"),
    (r"^ground-truth$", RATCHET + " ground-truth   (when a ground-truth part failed too, run that part's repro)"),
    (
        r"^crucible$",
        "tests/tools/box/heavy-run.sh python -m pytest -q tests/cics_crucible && tests/tools/box/heavy-run.sh "
        "python tests/tools/cics_crucible.py --ci --out /tmp/gitgalaxy-scratch/ci-digest/cics",
    ),
]
NO_LOCAL = re.compile(r"^(CodeQL|Analyze|Muninn|muninn|Small audits|rosetta-audit|"
                      r"Supply Chain Firewall|Full Report)", re.I)  # fmt: skip

# Test names the shepherd reruns once instead of reporting as a real failure. Empty on purpose: the wall-clock
# tests that used to live here (#4477) assert CPU-time ratios / best-of-3 CPU bounds now (tests/_timing.py), so
# they fail loudly. Add a name only for a flake you can NOT make deterministic, with its issue number.
FLAKY: set[str] = set()
INFRA_CONCLUSIONS = {"cancelled", "startup_failure", "timed_out"}
INFRA_LOG = re.compile(r"runner has received a shutdown signal|lost communication with the server|No space left on "
                       r"device|API rate limit exceeded|Could not resolve host|The operation was canceled|"
                       r"Error: The hosted runner|503 Service Unavailable|502 Bad Gateway|429 Too Many Requests|"
                       r"toomanyrequests|504 Gateway Time-out|http status: 504|Gateway Time-out|"
                       r"DownloadError.*Failed to fetch|Connection reset by peer|ECONNRESET|TLS handshake timeout|"
                       r"Build container for action use|failed to solve: .*(registry|docker\.io)|"
                       r"INFRASTRUCTURE \(not a code defect\)", re.I)  # fmt: skip
ERROR = re.compile(r"##\[error\]|^(FAILED|ERROR) |Traceback \(most recent call last\)|AssertionError|\bFAIL\b|"
                   r"NOT PROVEN|error: |Error: ", re.I)  # fmt: skip
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
STAMP = re.compile(r"^\d{4}-\d\d-\d\dT[\d:.]+Z ")
FAILED_TEST = re.compile(r"^FAILED (\S+::\S+)")
RUN_JOB = re.compile(r"/actions/runs/(\d+)/job/(\d+)")
UNPROVEN = re.compile(r"^\s*det (\S+)\s+NOT PROVEN")

# #5273 time_ratchet.py lines: `FAIL <nodeid>: 16.2s is over 15s and has no ...` / `... is over 2x its baseline 10.0s (...)`
RATCHET_FAIL = re.compile(r"^FAIL (\S+): ([\d.]+)s is over (?:([\d.]+)x its baseline ([\d.]+)s|([\d.]+)s and has no)")
EXIT_LINE = re.compile(r"Process completed with exit code")
RATCHET_SLACK = 1.5  # an overage within this multiple of its limit is runner noise, in the PR diff or not

# A roll-up / dependent check -> the part jobs it only summarises; it takes their non-real triage (#5273). The
# check-runs API carries no `needs`, so this mirrors smoke-test.yml, mainframe-ground-truth.yml and det-sweep.yml.
PARTS: dict[str, str] = {
    "full-suite": r"^(full-suite part \d+/\d+|tested-tree|suite-plan)$",
    "ground-truth": r"^(ground-truth part \d+/\d+|tested-tree|plan|ground-truth-warm)$",
    "det": r"^(shard \d+/\d+|db2 \d+/\d+|plan|detmut)$",
}
# A job -> the upstream jobs it `needs` (#5276): when one of those failed as infra, a dependent that shows no failing
# test or case (the plan / warm-up output it reads is missing) is a knock-on of it, not a code defect.
UPSTREAM: dict[str, str] = {
    r"^(shard|db2) \d+/\d+$": r"^plan$",
    r"^ground-truth part \d+/\d+$": r"^(tested-tree|plan|ground-truth-warm)$",
    r"^(full-suite part \d+/\d+|durations key)$": r"^(tested-tree|suite-plan)$",
}
NON_REAL = ("main", "flake", "infra")  # a roll-up with no real part takes the first of these any failed part has

Logs = Callable[[int], str]
Files = Callable[[], set[str] | None]


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
    ratchet: dict[str, list[float]] = {}  # nodeid -> [seconds, limit]
    for x in lines:
        if m := RATCHET_FAIL.match(x):
            limit = float(m.group(3)) * float(m.group(4)) if m.group(3) else float(m.group(5))
            ratchet[m.group(1)] = [float(m.group(2)), limit]
    other = [x for x in errors if not RATCHET_FAIL.match(x) and not EXIT_LINE.search(x)]
    return {"errors": errors[:max_errors], "more_errors": max(0, len(errors) - max_errors), "tail": lines[-tail:],
            "tests": tests, "cases": cases, "ratchet": ratchet,
            "ratchet_only": bool(ratchet) and not tests and not other}  # fmt: skip


def ratchet_triage(ratchet: dict[str, list[float]], diff_files: Files | None) -> str:
    """#5273: `flake` unless an over-limit test is in the PR diff (or the diff is unknown) AND over RATCHET_SLACK x its limit."""
    diff = diff_files() if diff_files else None
    for nodeid, (seconds, limit) in ratchet.items():
        if (diff is None or nodeid.split("::")[0] in diff) and seconds > RATCHET_SLACK * limit:
            return "real"
    return "flake"


def triage(
    conclusion: str,
    log: str,
    tests: list[str],
    mergeable_state: str | None = None,
    ex: dict[str, Any] | None = None,
    diff_files: Files | None = None,
) -> str:
    if conclusion == "action_required" and mergeable_state == "dirty":
        return "dirty"
    if conclusion in INFRA_CONCLUSIONS or INFRA_LOG.search(log):
        return "infra"
    if ex and ex.get("ratchet_only"):
        return ratchet_triage(ex["ratchet"], diff_files)
    names = {t.split("::")[-1].split("[")[0] for t in tests}
    if names and names <= FLAKY:
        return "flake"
    return "real"


def repro(name: str, ex: dict[str, Any], kind: str = "real", stale: bool | str = False) -> str | None:
    if kind == "main" and stale == "source":
        return (
            "stale base (main changed engine source since this branch, and this PR touches none of it): "
            "git merge origin/main; if the test still fails after the merge it is this PR's"
        )
    if kind == "main" and stale:
        return "stale base (main changed these tests since this branch): git merge origin/main"
    if kind == "main":
        return "fails on main too: fix main (then merge origin/main here)"
    if kind == "dirty":
        return "git merge origin/main  (then regenerate generated files with their tools; see the PR worker rules)"
    if NO_LOCAL.match(name):
        return None
    for pat, cmd in REPRO:
        if re.search(pat, name):
            whole = "tests/cobol_mainframe/" if name.startswith("ground-truth part") else "tests"
            return cmd.format(tests=" ".join(ex["tests"]) or whole, cases=",".join(ex["cases"]) or "<case>")
    return GATES + " --fast"


def _completed_names(runs: list[dict[str, Any]]) -> tuple[set[str], set[str]]:
    """(failed_names, all_completed_names) for a commit's check runs."""
    c = pr_check.classify(runs, [])
    failed = {x.rsplit(" (", 1)[0] for x in c["failed"]}
    neutral = {x.rsplit(" (", 1)[0] for x in c["neutral"]}
    return failed, set(c["passed"]) | failed | neutral


def changed_files(api: pr_check.Api, path: str) -> set[str] | None:
    """The file names of a files listing; None when unreadable (the callers then keep `real`)."""
    try:
        return {f["filename"] for f in pr_check.paged(api, path, limit=30)}
    except (SystemExit, KeyError, TypeError):
        return None


def files_since_merge_base(api: pr_check.Api, sha: str) -> set[str]:
    """Files changed on main since the merge-base of main and the PR head (#5273)."""
    try:
        base = api(f"repos/{REPO_SLUG}/compare/main...{sha}")["merge_base_commit"]["sha"]
        return {f["filename"] for f in api(f"repos/{REPO_SLUG}/compare/{base}...main").get("files", [])}
    except (SystemExit, KeyError, TypeError):
        return set()


def stale_by_source(mine: set[str] | None, main_changed: set[str], tests: list[str]) -> bool:
    """#5276: main changed engine source since the merge-base (its fix for a test file it never touched) and this PR
    provably cannot have moved the failing tests: its file list is readable and holds no engine source, conftest,
    fixture or file beside a failing test. Anything else stays `real` (a real breakage read as `main` once is the risk)."""
    if mine is None or not any(f.startswith("gitgalaxy/") for f in main_changed):
        return False
    dirs = {t.split("::")[0].rpartition("/")[0] for t in tests}
    return not any(
        f.startswith(("gitgalaxy/", "tests/fixtures/"))
        or f.rpartition("/")[2] == "conftest.py"
        or f.rpartition("/")[0] in dirs
        for f in mine
    )


def rollup_kind(name: str, kind: str, ex: dict[str, Any], kinds: dict[str, str]) -> str:
    """#5273: a `real` roll-up check (full-suite, ground-truth, det) whose failed part jobs are all non-real takes theirs:
    a Db2 image pull leaves `det` with "shard did not report", a suite part is over its time limit."""
    pat = PARTS.get(name)
    if kind != "real" or not pat or ex["tests"] or ex["cases"]:
        return kind
    parts = [k for part, k in kinds.items() if re.search(pat, part)]
    if not parts or any(k not in NON_REAL for k in parts):
        return kind
    return next(k for k in NON_REAL if k in parts)


def knock_on_kind(name: str, kind: str, ex: dict[str, Any], kinds: dict[str, str]) -> str:
    """#5276: a `real` job with no failing test or case whose upstream job (UPSTREAM) failed as infra is `infra` too."""
    if kind != "real" or ex["tests"] or ex["cases"]:
        return kind
    for dep, up in UPSTREAM.items():
        if re.search(dep, name) and any(k == "infra" for part, k in kinds.items() if re.search(up, part)):
            return "infra"
    return kind


MAIN_QUERY = """
query($owner: String!, $name: String!) {
  rateLimit { cost }
  repository(owner: $owner, name: $name) {
    ref(qualifiedName: "refs/heads/main") { target { ... on Commit { oid
      parents(first: 1) { nodes { oid } }
      @@SUITES@@
    } } }
  }
}""".replace("@@SUITES@@", pr_check.SUITES_SELECTION)


def main_tip(
    api: pr_check.Api, graphql: pr_check.GraphQL | None = None
) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
    """(main's newest commit as REST's {sha, parents}, its check runs), or None when unreadable (#6534: one GraphQL
    query when `graphql` is given, the two REST reads when it fails or comes back incomplete)."""
    if graphql:
        owner, name = REPO_SLUG.split("/")
        try:
            c = graphql(MAIN_QUERY, {"owner": owner, "name": name})["repository"]["ref"]["target"]
            runs = pr_check.runs_from_suites(pr_check.whole(c["checkSuites"]))
            return {"sha": c["oid"], "parents": [{"sha": x["oid"]} for x in c["parents"]["nodes"]]}, runs
        except (SystemExit, KeyError, TypeError, AttributeError, ValueError):
            pass
    try:
        commit = api(f"repos/{REPO_SLUG}/commits/main")
        return commit, pr_check.paged(api, f"repos/{REPO_SLUG}/commits/{commit['sha']}/check-runs", "check_runs")
    except (SystemExit, KeyError, TypeError):
        return None


def main_failures(
    api: pr_check.Api,
    lookback: int = 3,
    graphql: pr_check.GraphQL | None = None,
    tip: tuple[dict[str, Any], list[dict[str, Any]]] | None = None,
) -> set[str]:
    """The checks failing on main's newest commit (#4790): a PR failing the same check inherited it from main.
    Basal persistence: when main's tip commit just landed and its checks are still pending (or not yet registered),
    walk up to `lookback` first-parent commits on main so checks not yet completed on tip retain their last known
    completed main status instead of causing a false 'real' failure during the post-merge CI window.
    `tip`: main_tip's answer, when the pass already read it."""
    tip = tip or main_tip(api, graphql)
    if tip is None:
        return set()
    commit, runs = tip
    failed, decided = _completed_names(runs)
    pending = {x.rsplit(" (", 1)[0] for x in pr_check.classify(runs, [])["pending"]}
    parents = commit.get("parents") or []
    steps = 0
    while steps < lookback and parents and (pending - decided or not runs):
        parent_sha = (parents[0] or {}).get("sha")
        if not parent_sha:
            break
        try:
            p_commit = api(f"repos/{REPO_SLUG}/commits/{parent_sha}")
            p_runs = pr_check.paged(api, f"repos/{REPO_SLUG}/commits/{parent_sha}/check-runs", "check_runs")
        except (SystemExit, KeyError, TypeError):
            break
        p_failed, p_decided = _completed_names(p_runs)
        failed |= p_failed - decided
        decided |= p_decided
        if p_runs and not (pending - decided):
            break
        parents = p_commit.get("parents") or [] if isinstance(p_commit, dict) else []
        steps += 1
    return failed


def main_green(
    api: pr_check.Api,
    graphql: pr_check.GraphQL | None = None,
    tip: tuple[dict[str, Any], list[dict[str, Any]]] | None = None,
) -> tuple[str, set[str]]:
    """(main's newest sha, the checks completed green on exactly that commit) (#5484). Tip only, no look-back: a check
    still pending on the tip is not green yet, so a PR waiting on main keeps waiting. Unreadable: ("", set())."""
    tip = tip or main_tip(api, graphql)
    if tip is None:
        return "", set()
    commit, runs = tip
    c = pr_check.classify(runs, [])
    failed, _ = _completed_names(runs)
    pending = {x.rsplit(" (", 1)[0] for x in c["pending"]}
    return commit["sha"], set(c["passed"]) - failed - pending


def first_attempt(api: pr_check.Api, job_id: int) -> bool:
    """True when the job ran in its workflow run's first attempt (unknown counts as not)."""
    try:
        return (api(f"repos/{REPO_SLUG}/actions/jobs/{job_id}").get("run_attempt") or 0) == 1
    except (SystemExit, AttributeError):
        return False


def digest(
    n: int,
    api: pr_check.Api = pr_check.gh_api,
    logs: Logs = job_log,
    on_main: set[str] | None = None,
    flaky: set[str] | None = None,
    pr: dict[str, Any] | None = None,
    runs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """`pr`, `runs`: the pull request and its head's check runs when the caller already read them (#6534)."""
    on_main = main_failures(api) if on_main is None else on_main
    pr = api(f"repos/{REPO_SLUG}/pulls/{n}") if pr is None else pr
    sha = pr["head"]["sha"]
    if runs is None:
        runs = pr_check.paged(api, f"repos/{REPO_SLUG}/commits/{sha}/check-runs", "check_runs")
    failed = pr_check.failed_names(runs)
    newest: dict[str, dict[str, Any]] = {}
    for r in sorted(runs, key=lambda r: r.get("id", 0)):
        if r["name"] in failed and r.get("conclusion") not in pr_check.NEUTRAL | {None}:
            newest[r["name"]] = r
    lazy: dict[str, set[str] | None] = {}

    def diff_files() -> set[str] | None:  # fetched once, and only when a verdict needs the PR's files
        if "pr" not in lazy:
            lazy["pr"] = changed_files(api, f"repos/{REPO_SLUG}/pulls/{n}/files")
        return lazy["pr"]

    first = []
    for name, r in sorted(newest.items()):
        actions = (r.get("app") or {}).get("slug") == "github-actions"
        log = logs(r["id"]) if actions else ""
        ex = extract(log)
        kind = triage(r.get("conclusion") or "", log, ex["tests"], pr.get("mergeable_state"), ex, diff_files)
        first.append((name, r, ex, kind))
    kinds = {name: kind for name, _, _, kind in first}
    out = []
    for name, r, ex, kind in first:
        kind = knock_on_kind(name, rollup_kind(name, kind, ex, kinds), ex, kinds)
        stale: bool | str = False
        if kind == "real" and name in on_main:
            kind = "main"  # the same check fails on main: fix main, not this PR
        elif kind == "real" and ex["tests"]:
            files = {t.split("::")[0] for t in ex["tests"]}
            mine = diff_files()
            since = files_since_merge_base(api, sha)
            if mine is not None and files & since and not files & mine:
                kind, stale = "main", True  # main fixed these tests since the merge-base (#5273)
            elif stale_by_source(mine, since, ex["tests"]):
                kind, stale = "main", "source"  # main's fix was in source only, the PR touches none of it (#5276)
        ids = RUN_JOB.search(r.get("details_url") or "")
        if kind == "real" and flaky and name in flaky and ids and first_attempt(api, int(ids.group(2))):
            kind = "flake"  # a learned flake's first failure gets one rerun; a second failure is real
        out.append({"check": name, "conclusion": r.get("conclusion"), "url": r.get("html_url") or r.get("details_url"),
                    "run_id": int(ids.group(1)) if ids else None, "job_id": int(ids.group(2)) if ids else None,
                    "triage": kind, "repro": repro(name, ex, kind, stale), **ex})  # fmt: skip
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
