#!/usr/bin/env python3
"""The CI shepherd (#4790): takes a queue of pull requests to merge, and does the waiting and the sorting itself.

    python tests/tools/box/ci_shepherd.py add 4811 4819 [--after 4811]   # queue PRs (--after: wait for that one first)
    python tests/tools/box/ci_shepherd.py run [--once] [--every 600] [--hours 6]
    python tests/tools/box/ci_shepherd.py status
    python tests/tools/box/ci_shepherd.py drop 4819

Per queued PR, each pass (tests/tools/pr_check.py for the state, tests/tools/ci_digest.py for the failures):
  merged / closed         leaves the queue
  waits on --after PR     skipped until that one merged
  green + mergeable       `pr_check.merge` (marks ready, squash-merges pinned to the checked head); a merge that moved
                          the crucible pin syncs the shared checkouts, as `pr_check.py --merge` does
  checks pending          waits
  failed: infra / flake   `gh run rerun RUN --failed`, ONCE per (head SHA, check)
  failed: dirty           one PR comment per head SHA: merge origin/main, regenerate generated files with their tools
  failed: real            one PR comment per head SHA with the digest (error lines, log tail, local repro) -- the
                          fixer's input; $CI_SHEPHERD_FIXER, when set, is run as `$CI_SHEPHERD_FIXER N DIGEST.json`
A new head SHA (someone pushed) resets the once-per-SHA memory. Nothing here reads a raw log or guesses a fix.

One shepherd at a time: the state file is locked with flock (a second `run` exits at once), so it is never matched by
`pgrep` against its own command line. State: $CI_SHEPHERD_STATE (default ~/.cache/gitgalaxy/ci_shepherd.json).
Census history (`cics_census.py history append`) is NOT done here: it writes a committed file, so it belongs in the
evidence-refresh bot, not in a commit per merge.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import ci_digest  # noqa: E402
import pr_check  # noqa: E402

STATE = Path(os.environ.get("CI_SHEPHERD_STATE", Path.home() / ".cache" / "gitgalaxy" / "ci_shepherd.json"))
REPO_SLUG = pr_check.REPO_SLUG
Run = Callable[[list[str]], subprocess.CompletedProcess[str]]


def _run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, capture_output=True, text=True, check=False)  # noqa: S603


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S ") + msg, flush=True)


def load(path: Path | None = None) -> dict[str, Any]:
    path = path or STATE
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"queue": [], "after": {}, "seen": {}}


def save(state: dict[str, Any], path: Path | None = None) -> None:
    path = path or STATE
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def comment(n: int, body: str, run: Run) -> None:
    r = run(["gh", "api", f"repos/{REPO_SLUG}/issues/{n}/comments", "-f", f"body={body[:60000]}"])
    if r.returncode:
        log(f"#{n}: comment failed: {r.stderr.strip()[:200]}")


def once(state: dict[str, Any], n: int, sha: str, key: str) -> bool:
    """True the first time `key` is seen for PR n at head `sha` (and records it)."""
    seen = state["seen"].setdefault(str(n), {})
    if seen.get("sha") != sha:
        seen.clear()
        seen["sha"] = sha
    if key in seen:
        return False
    seen[key] = time.strftime("%Y-%m-%dT%H:%M:%S")
    return True


def step(state: dict[str, Any], api: pr_check.Api = pr_check.gh_api, run: Run = _run,
         digest: Callable[[int], dict[str, Any]] | None = None, settle: float = 30) -> list[str]:  # fmt: skip
    """One pass over the queue. Returns what it did (for the log and the tests)."""
    digest = digest or (lambda n: ci_digest.digest(n, api))
    did: list[str] = []
    for n in list(state["queue"]):
        res = pr_check.check(n, api)
        if res["state"] != "open":
            state["queue"].remove(n)
            did.append(f"#{n} {res['state']}: left the queue")
            continue
        base = state["after"].get(str(n))
        if base and base in state["queue"]:
            did.append(f"#{n} waits for #{base}")
            continue
        sha = res["head_sha"]
        if res["ready"]:
            errors = pr_check.merge(res, run)
            if errors:
                did.append(f"#{n} merge failed: {'; '.join(errors)}")
                continue
            state["queue"].remove(n)
            did.append(f"#{n} MERGED (head {sha[:12]})")
            if any(f["path"] == pr_check.PIN_FILE for f in res["files"]):
                did.append(pr_check.sync_pins(run))
            time.sleep(settle)  # GitHub recomputes the others' mergeability
            continue
        failed = res["checks"]["failed"]
        if not failed and res["mergeable_state"] != "dirty":
            did.append(f"#{n} waiting: {len(res['checks']['pending'])} pending")
            continue
        d = digest(n)
        kinds = {f["triage"] for f in d["failed"]} or ({"dirty"} if res["mergeable_state"] == "dirty" else set())
        for f in d["failed"]:
            if f["triage"] in ("infra", "flake") and f.get("run_id") and once(state, n, sha, f"rerun:{f['check']}"):
                r = run(["gh", "run", "rerun", str(f["run_id"]), "--failed", "-R", REPO_SLUG])
                did.append(
                    f"#{n} rerun {f['check']} ({f['triage']}): {'ok' if not r.returncode else r.stderr.strip()[:120]}"
                )
        if "dirty" in kinds and once(state, n, sha, "note:dirty"):
            comment(n, "CI shepherd: this PR conflicts with main, so no checks ran. Merge `origin/main` into it and "
                       "regenerate generated files with their tools (never hand-merge them; see "
                       "`.claude/agents/gitgalaxy-pr-worker.md`), then push.", run)  # fmt: skip
            did.append(f"#{n} dirty: noted")
        if "real" in kinds and once(state, n, sha, "note:real"):
            real = {**d, "failed": [f for f in d["failed"] if f["triage"] == "real"]}
            comment(n, "CI shepherd: real failure(s) on this head. Reproduce locally with the `repro` line; don't "
                       "re-push to find out.\n\n```\n" + ci_digest.render(real) + "\n```", run)  # fmt: skip
            did.append(f"#{n} real failure: digest posted")
            fixer = os.environ.get("CI_SHEPHERD_FIXER")
            if fixer:
                path = STATE.parent / f"digest-{n}-{sha[:12]}.json"
                path.write_text(json.dumps(real, indent=1), encoding="utf-8")
                subprocess.Popen([*fixer.split(), str(n), str(path)], start_new_session=True)  # noqa: S603
                did.append(f"#{n} fixer started: {fixer} {n} {path}")
    return did


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("prs", type=int, nargs="+")
    a.add_argument("--after", type=int, help="these wait until this PR merged (a stacked PR's base)")
    d = sub.add_parser("drop")
    d.add_argument("prs", type=int, nargs="+")
    sub.add_parser("status")
    r = sub.add_parser("run")
    r.add_argument("--once", action="store_true")
    r.add_argument("--every", type=int, default=600, help="seconds between passes")
    r.add_argument("--hours", type=float, default=6.0, help="stop after this long, or when the queue is empty")
    args = ap.parse_args(argv)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    if args.cmd == "run":
        with open(STATE.with_suffix(".run.lock"), "w") as running:  # one shepherd at a time, for its whole run
            try:
                fcntl.flock(running, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                print("another ci_shepherd run is active: exiting", file=sys.stderr)
                return 1
            end = time.time() + args.hours * 3600
            while True:
                with open(STATE.with_suffix(".lock"), "w") as lock:  # held per pass; add/drop wait for it
                    fcntl.flock(lock, fcntl.LOCK_EX)
                    state = load()
                    for line in step(state):
                        log(line)
                    save(state)
                if args.once or not state["queue"] or time.time() > end:
                    log(
                        "queue empty"
                        if not state["queue"]
                        else "stopping; queue: " + " ".join(map(str, state["queue"]))
                    )
                    return 0
                time.sleep(args.every)
    with open(STATE.with_suffix(".lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = load()
        if args.cmd == "add":
            state["queue"] += [n for n in args.prs if n not in state["queue"]]
            for n in args.prs:
                if args.after and n != args.after:
                    state["after"][str(n)] = args.after
        elif args.cmd == "drop":
            state["queue"] = [n for n in state["queue"] if n not in args.prs]
        save(state)
        print("queue: " + (" ".join(f"{n}" + (f"(after {state['after'][str(n)]})" if str(n) in state["after"] else "")
                                    for n in state["queue"]) or "empty"))  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main())
