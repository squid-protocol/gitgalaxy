#!/usr/bin/env python3
"""RETIRED as the live shepherd (#5398): the GitHub workflows (shepherd-reconcile.yml / shepherd-event.yml, via
tests/tools/shepherd_gh.py) are the live one; no unit or process runs this on the box. Kept as the fallback docs/ci.md
names for when the workflows are down. Its learned-flake handling (below) now exists in shepherd_gh too.

The CI shepherd (#4790): takes a queue of pull requests to merge, and does the waiting and the sorting itself.

    python tests/tools/box/ci_shepherd.py add 4811 4819 [--after 4811]   # queue PRs (--after: wait for that one first)
    python tests/tools/box/ci_shepherd.py run [--once] [--every 600] [--hours 6]
    python tests/tools/box/ci_shepherd.py status
    python tests/tools/box/ci_shepherd.py drop 4819

Per queued PR, each pass (tests/tools/pr_check.py for the state, tests/tools/ci_digest.py for the failures):
  merged / closed         leaves the queue
  waits on --after PR     skipped until that one merged
  green + mergeable       `pr_check.merge` (a draft is only marked ready, merged on a later pass once its CI is green; else squash-merges pinned
                          to the checked head); a merge that moved
                          the crucible pin syncs the shared checkouts, as `pr_check.py --merge` does
  checks pending          waits
  behind main             never updated to stay current (#5134): a push restarts CI. It waits like any PR
  failed: infra / flake   `gh run rerun RUN --failed`, ONCE per (head SHA, check)
  failed: dirty           one PR comment per head SHA: merge origin/main (the conflict is the reason), regenerate generated files with their tools
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
sys.path.insert(0, str(Path(__file__).resolve().parent))  # box_status
import ci_digest  # noqa: E402
import flake_history  # noqa: E402
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


def has_seen(state: dict[str, Any], n: int, sha: str, key: str) -> bool:
    """True when `key` was already recorded for PR n at head `sha` (without recording it)."""
    seen = state["seen"].get(str(n), {})
    return seen.get("sha") == sha and key in seen


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


INFRA_RETRIES = 3  # an outage (Docker Hub 429/504 on 2026-10-09) outlasts one rerun
RETRY_GAP = 15 * 60  # seconds between reruns of the same check on the same head
# promoter affinity: at most this many drafts are marked ready (their CI started) in one pass
MAX_IN_FLIGHT = int(os.environ.get("CI_SHEPHERD_MAX_IN_FLIGHT", "4"))
MAX_LEDGER = 200  # epigenetic memory cap
MAX_FIXERS = int(os.environ.get("CI_SHEPHERD_MAX_FIXERS", "1"))  # fixers started per pass: the box is read before them
FLAKE_MAX_AGE = 6 * 3600  # seconds before the learned-flake cache is refreshed (in the background)


def record_event(state: dict[str, Any], n: int, sha: str, event: str, detail: str = "") -> None:
    """Append a bounded epigenetic mark to state['ledger'] recording transcriptional stress/outcomes across passes."""
    ledger = state.setdefault("ledger", [])
    ledger.append(
        {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "pr": n, "sha": sha[:12], "event": event, "detail": detail}
    )
    if len(ledger) > MAX_LEDGER:
        del ledger[:-MAX_LEDGER]


def box_verdict() -> str:
    """Global metabolic headroom signal (cAMP-CRP) from box_status: 'GREEN', 'YELLOW', or 'RED'."""
    try:
        import box_status

        if not Path("/proc/meminfo").exists():
            return "GREEN"
        return str(box_status.snapshot(sample=0.1).get("verdict") or "GREEN")
    except Exception as e:  # an unreadable box never blocks a fixer, but say so
        log(f"box_verdict: unreadable ({e!r}), treating as GREEN")
        return "GREEN"


def learned_flakes(state: dict[str, Any], t: float | None = None) -> set[str]:
    """The checks flake_history learned are flaky, from its cache beside the state file. A stale cache is refreshed by
    a detached `flake_history --refresh-only` (at most one an hour) so a pass never waits on it; no cache, no flakes."""
    t = now() if t is None else t
    path = STATE.parent / "flake_history.json"
    cache = flake_history.load(path)
    if t - float(cache.get("updated") or 0) > FLAKE_MAX_AGE and t - state.get("flake_refresh", 0) > 3600:
        state["flake_refresh"] = t
        subprocess.Popen([sys.executable, flake_history.__file__, "--refresh-only", "--cache", str(path)],  # noqa: S603
                         start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # fmt: skip
    return flake_history.learned(cache)


def fixer_priority(state: dict[str, Any], cand: tuple[int, str, dict[str, Any]]) -> tuple[int, int, int]:
    """Most useful fix first: the PR most others wait on (--after), then the fewest failing checks, then the oldest."""
    n, _, real = cand
    waiting = sum(1 for base in state["after"].values() if str(base) == str(n))
    return (-waiting, len(real["failed"]), n)


def start_fixers(
    state: dict[str, Any], cands: list[tuple[int, str, dict[str, Any]]], fixer: str, did: list[str]
) -> None:
    """Start at most MAX_FIXERS of the pass's fixer candidates, most useful first, when the box reads GREEN. The box
    is read once: a fixer just started has not loaded it yet, so a second reading in the same pass would lie."""
    cands = sorted(cands, key=lambda c: fixer_priority(state, c))
    verdict = box_verdict()
    for i, (n, sha, real) in enumerate(cands):
        if verdict in ("RED", "YELLOW"):
            did.append(f"#{n} fixer deferred: box is {verdict} (catabolite repression)")
            if once(state, n, sha, "note:fixer-deferred"):
                record_event(state, n, sha, "fixer_deferred", f"box {verdict}")
        elif i >= MAX_FIXERS:
            did.append(f"#{n} fixer queued: {MAX_FIXERS} started this pass (most useful first), next pass")
        elif once(state, n, sha, "fixer:real"):
            path = STATE.parent / f"digest-{n}-{sha[:12]}.json"
            path.write_text(json.dumps(real, indent=1), encoding="utf-8")
            subprocess.Popen([*fixer.split(), str(n), str(path)], start_new_session=True)  # noqa: S603
            did.append(f"#{n} fixer started: {fixer} {n} {path}")
            record_event(state, n, sha, "fixer_started", fixer)


def now() -> float:
    return time.time()


def retry_due(state: dict[str, Any], n: int, sha: str, key: str, tries: int, t: float) -> bool:
    """True (and records the attempt) when `key` has had fewer than `tries` reruns on this head, the last at least
    RETRY_GAP ago."""
    seen = state["seen"].setdefault(str(n), {})
    if seen.get("sha") != sha:
        seen.clear()
        seen["sha"] = sha
    done = seen[key] if isinstance(seen.get(key), list) else ([0.0] if key in seen else [])
    if len(done) >= tries or (done and t - done[-1] < RETRY_GAP):
        return False
    seen[key] = [*done, t]
    return True


def reruns_used_up(state: dict[str, Any], n: int, sha: str, key: str, tries: int) -> bool:
    """True when `key` already had `tries` reruns on this head (what retry_due counts)."""
    seen = state["seen"].get(str(n), {})
    done = seen.get(key) if seen.get("sha") == sha else None
    return isinstance(done, list) and len(done) >= tries


def rerun_key(f: dict[str, Any]) -> str:
    """The retry budget a failure draws on: its workflow run (`gh run rerun --failed` reruns every failed job of it, so
    matrix legs of one run share one budget), else its check name."""
    return f"rerun:run:{f['run_id']}" if f.get("run_id") else f"rerun:{f['check']}"


def required_checks(api: pr_check.Api) -> set[str] | None:
    """The status checks the rules on main require (#4825 ruleset); None when they cannot be read (then every
    check counts as required)."""
    try:
        rules = api(f"repos/{REPO_SLUG}/rules/branches/main")
    except SystemExit:
        return None
    return {c["context"] for r in rules if r.get("type") == "required_status_checks"
            for c in r.get("parameters", {}).get("required_status_checks", [])}  # fmt: skip


def _rerun_why(state: dict[str, Any], n: int, sha: str, key: str, tries: int) -> str:
    seen = state["seen"].get(str(n), {})
    used = seen.get(key) if seen.get("sha") == sha and isinstance(seen.get(key), list) else []
    if len(used) >= tries:
        return f"{tries} reruns used up"
    return f"{len(used)}/{tries} reruns used; the next waits {RETRY_GAP // 60} min after the last"


def _pass_one(
    state: dict[str, Any],
    n: int,
    res: dict[str, Any],
    api: pr_check.Api,
    run: Run,
    digest: Callable[[int], dict[str, Any]],
    settle: float,
    did: list[str],
    in_flight: list[int] | None = None,
    fixers: list[tuple[int, str, dict[str, Any]]] | None = None,
) -> None:
    """One open PR's part of a pass. Appends what it did, or why it did nothing."""
    base = state["after"].get(str(n))
    if base and base in state["queue"]:
        did.append(f"#{n} waits for #{base}")
        return
    sha = res["head_sha"]
    if res["ready"]:
        if res.get("draft") and in_flight is not None and in_flight[0] >= MAX_IN_FLIGHT:
            did.append(f"#{n} draft deferred: {in_flight[0]} PR(s) already in flight (max {MAX_IN_FLIGHT})")
            return
        errors = pr_check.merge(res, run)
        if pr_check.draft_marked_ready(errors):
            if in_flight is not None:
                in_flight[0] += 1
            did.append(f"#{n} was a draft: marked ready; its CI starts, a later pass merges")
            record_event(state, n, sha, "draft_ready")
            return
        if errors:
            did.append(f"#{n} merge failed: {'; '.join(errors)}")
            return
        state["queue"].remove(n)
        did.append(f"#{n} MERGED (head {sha[:12]})")
        record_event(state, n, sha, "merged")
        if any(f["path"] == pr_check.PIN_FILE for f in res["files"]):
            did.append(pr_check.sync_pins(run))
        time.sleep(settle)  # GitHub recomputes the others' mergeability
        return
    failed = res["checks"]["failed"]
    if not failed and res["mergeable_state"] == "behind" and not res["checks"]["pending"]:
        # green but GitHub calls it behind (classic strict protection): a human merges main or clears strict (#5134)
        did.append(f"#{n} behind main, not updated (#5134): merge it by hand or clear branch-protection strict")
        return
    if not failed and res["mergeable_state"] != "dirty":
        if res["checks"]["pending"] and in_flight is not None:
            in_flight[0] += 1
        did.append(f"#{n} waiting: {len(res['checks']['pending'])} pending")
        return
    d = digest(n)
    kinds = {f["triage"] for f in d["failed"]} or ({"dirty"} if res["mergeable_state"] == "dirty" else set())
    if "main" in kinds:
        did.append(f"#{n} waits for main: {', '.join(f['check'] for f in d['failed'] if f['triage'] == 'main')} "
                   "fails on main too (no PR note)")  # fmt: skip
    # An infra failure of a check main does not require (muninn on a Docker Hub outage) stops blocking once its
    # reruns are used up; a real finding there still blocks, and a required check always does.
    required = required_checks(api)
    if (d["failed"] and kinds == {"infra"} and required is not None and not res["checks"]["pending"]
            and res["mergeable_state"] not in ("dirty", "behind", "blocked")
            and all(f["check"] not in required for f in d["failed"])
            and all(reruns_used_up(state, n, sha, rerun_key(f), INFRA_RETRIES) for f in d["failed"])):  # fmt: skip
        if res.get("draft") and in_flight is not None and in_flight[0] >= MAX_IN_FLIGHT:
            did.append(f"#{n} draft deferred: {in_flight[0]} PR(s) already in flight (max {MAX_IN_FLIGHT})")
            return
        errors = pr_check.merge(res, run)
        names = ", ".join(f["check"] for f in d["failed"])
        if pr_check.draft_marked_ready(errors):
            if in_flight is not None:
                in_flight[0] += 1
            did.append(f"#{n} was a draft: marked ready; its CI starts, a later pass decides")
            record_event(state, n, sha, "draft_ready")
        elif errors:
            did.append(f"#{n} merge failed: {'; '.join(errors)}")
        else:
            state["queue"].remove(n)
            did.append(f"#{n} MERGED past non-required infra failure(s) after {INFRA_RETRIES} reruns: {names}")
            record_event(state, n, sha, "merged_past_infra", names)
            comment(n, f"CI shepherd: merged with {names} failing for infrastructure reasons only (not a "
                       f"required check; rerun {INFRA_RETRIES} times, 15 min apart). Its next run on main "
                       "will report again.", run)  # fmt: skip
        return
    reran_runs: set[int] = set()
    for f in d["failed"]:
        tries = INFRA_RETRIES if f["triage"] == "infra" else 1
        if f["triage"] not in ("infra", "flake"):
            continue
        key = rerun_key(f)
        rid = f.get("run_id")
        if not rid:
            did.append(f"#{n} blocked: {f['check']} ({f['triage']}) -- no action: no run id in its URL to rerun")
        elif rid in reran_runs:
            did.append(f"#{n} rerun {f['check']} ({f['triage']}): ok (shared run {rid})")
        elif retry_due(state, n, sha, key, tries, now()):
            r = run(["gh", "run", "rerun", str(rid), "--failed", "-R", REPO_SLUG])
            if not r.returncode:
                reran_runs.add(rid)
                record_event(state, n, sha, "rerun", f"{f['check']} ({f['triage']})")
            did.append(f"#{n} rerun {f['check']} ({f['triage']}): "
                       f"{'ok' if not r.returncode else r.stderr.strip()[:120]}")  # fmt: skip
        else:
            did.append(f"#{n} blocked: {f['check']} ({f['triage']}) -- no action: {_rerun_why(state, n, sha, key, tries)}")  # fmt: skip
    if "dirty" in kinds and once(state, n, sha, "note:dirty"):
        comment(n, "CI shepherd: this PR conflicts with main, so no checks ran. Merge `origin/main` into it and "
                   "regenerate generated files with their tools (never hand-merge them; see "
                   "`.claude/agents/gitgalaxy-pr-worker.md`), then push.", run)  # fmt: skip
        did.append(f"#{n} dirty: noted")
    if "real" in kinds:
        real = {**d, "failed": [f for f in d["failed"] if f["triage"] == "real"]}
        if once(state, n, sha, "note:real"):
            comment(n, "CI shepherd: real failure(s) on this head. Reproduce locally with the `repro` line; don't "
                       "re-push to find out.\n\n```\n" + ci_digest.render(real) + "\n```", run)  # fmt: skip
            did.append(f"#{n} real failure: digest posted")
            record_event(state, n, sha, "real_failure", ", ".join(f["check"] for f in real["failed"]))
        fixer = os.environ.get("CI_SHEPHERD_FIXER")
        if fixer and not has_seen(state, n, sha, "fixer:real"):
            if fixers is None:
                start_fixers(state, [(n, sha, real)], fixer, did)
            else:
                fixers.append((n, sha, real))  # step() starts the pass's most useful ones


def step(state: dict[str, Any], api: pr_check.Api = pr_check.gh_api, run: Run = _run,
         digest: Callable[[int], dict[str, Any]] | None = None, settle: float = 30,
         graphql: pr_check.GraphQL | None = None) -> list[str]:  # fmt: skip
    """One pass over the queue. Returns what it did (for the log and the tests). Every queued PR gets at least one
    line: what it did, or its state and why nothing was done (#4790: a pass logged nothing about #4837).
    `graphql` (#6534): each PR's state and a failing PR's digest, and main's failing checks (read once per pass), come
    from GraphQL, REST when a query fails."""
    on_main_cache: list[set[str]] = []

    flaky_cache: list[set[str]] = []

    def _default_digest(n: int) -> dict[str, Any]:
        if not on_main_cache:
            on_main_cache.append(ci_digest.main_failures(api, graphql=graphql))
            flaky_cache.append(learned_flakes(state))
        return ci_digest.digest(n, api, on_main=on_main_cache[0], flaky=flaky_cache[0], graphql=graphql)

    digest_fn = digest or _default_digest
    did: list[str] = []
    in_flight = [0]
    fixers: list[tuple[int, str, dict[str, Any]]] = []
    for n in list(state["queue"]):
        res = pr_check.check(n, api, graphql)
        if res["state"] != "open":
            state["queue"].remove(n)
            did.append(f"#{n} {res['state']}: left the queue")
            continue
        before = len(did)
        _pass_one(state, n, res, api, run, digest_fn, settle, did, in_flight=in_flight, fixers=fixers)
        if len(did) == before:  # the fallback: no code path returns silently for a PR
            failed = ", ".join(res["checks"]["failed"]) or "none"
            did.append(
                f"#{n} no action: head {res['head_sha'][:12]}, mergeable_state {res['mergeable_state']}, "
                f"failed: {failed}, pending: {len(res['checks']['pending'])}"
            )
    if fixers:
        start_fixers(state, fixers, os.environ.get("CI_SHEPHERD_FIXER", ""), did)
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
    r.add_argument("--hours", type=float, default=6.0, help="stop after this long")
    r.add_argument("--exit-when-empty", action="store_true",
                   help="also stop when the queue is empty (default: keep watching -- a PR queued later is merged too)")  # fmt: skip
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
                    for line in step(state, graphql=pr_check.gh_graphql):
                        log(line)
                    save(state)
                if args.once or (args.exit_when_empty and not state["queue"]) or time.time() > end:
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
        if args.cmd == "status" and state.get("ledger"):
            recent = state["ledger"][-5:]
            print("recent events: " + ", ".join(f"#{e['pr']} {e['event']}" for e in recent))
    return 0


if __name__ == "__main__":
    sys.exit(main())
