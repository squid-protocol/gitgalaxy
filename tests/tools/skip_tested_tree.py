#!/usr/bin/env python3
"""skip-tested-tree (#4935): skip a workflow's post-merge push run when the PR run already proved the same tree green.

Used by the `tested-tree` job of every workflow triggered on both `pull_request` and a main `push` whose push run is
still needed (mainframe-ground-truth, smoke-test, java-compile; #5131 moved the other #4964 members to post-merge.yml's
dispatch). The job runs on a main push only (#5129). Stdlib only; reads run metadata through `gh api`, never checks out
or runs PR code:

    python tests/tools/skip_tested_tree.py <workflow-file.yml>      # env: GH_TOKEN, GITHUB_REPOSITORY, GITHUB_SHA,
                                                                     #      GITHUB_EVENT_NAME, GITHUB_REF, GITHUB_OUTPUT

It writes `skip=true|false` to $GITHUB_OUTPUT. The rule is in decide() (pure: a snapshot in, (skip, reason) out). A push
run is skipped only when ALL of these hold:

  * the event is a push to main (schedule, workflow_dispatch and pull_request runs never skip);
  * the pushed commit has one parent (a squash or rebase merge; a merge commit joins two histories, so its tree is
    something no PR run tested);
  * exactly one merged PR maps to the commit, and the commit's tree SHA equals that PR head's tree SHA;
  * the commit's parent is an ancestor of the PR head. A `pull_request` run checks out the test merge of head and base,
    and the API does not say which base. On a linear main, "the final parent is in the head" means every earlier base
    was too, so that test merge was the head's own tree and not some other one (a PR behind main fails this);
  * the PR targeted main (a run on a PR into another base proved nothing about main's tree);
  * the newest `pull_request` run of THIS workflow on that head SHA completed with `success` (red, cancelled, in
    progress or missing: run it).

Fail-open: any API error, or anything unexpected, prints a reason and runs the workflow. A skipped run still concludes
`success`, which is a true verdict: this exact tree passed the same workflow on the PR. Main Watch
(tests/tools/main_watch.py) only counts success/failure conclusions, so a real red on main is still reported, and the
nightly run still covers drift in the pinned inputs.

Cadence (2026-11-03, owner: hourly): with CADENCE_HOURS set (equivalence-e2e, mainframe-ground-truth, smoke-test), a
push run the tree rule did not skip is DEFERRED when another real run of this workflow on main (push, schedule or
dispatch; not a cancelled one) started under CADENCE_HOURS ago or is still running: those suites cost ~75 run-minutes
per merge, 17 times in 5.6 h that day, while PRs queued for runners. A deferred run cancels itself (the workflow's
`Defer` step), so it never reports a green it did not earn; Main Watch counts only success / failure. The next push
past the window runs as usual, and post_merge_dispatch.py re-runs the newest deferred push run once the window has
passed, so main's head is checked within about CADENCE_HOURS + 20 min. Either way the run's tree holds every deferred
commit, and `base` (the newest real run's SHA) tells a planner which files moved since main was last checked.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Any

MAIN_REF = "refs/heads/main"


def newest_run(runs: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The newest pull_request run (highest id; a re-run keeps its id and reports its latest attempt)."""
    pr_runs = [r for r in runs if r.get("event") == "pull_request"]
    return max(pr_runs, key=lambda r: r["id"]) if pr_runs else None


def decide(s: dict[str, Any]) -> tuple[bool, str]:
    """snapshot -> (skip, reason). s: event, ref, parents (count), tree, pr (None | {head_tree, merge_sha, base}),
    sha, parent_in_head (bool | None), runs (the workflow's runs on the PR head SHA)."""
    if s["event"] != "push" or s["ref"] != MAIN_REF:
        return False, f"{s['event']} on {s['ref']}: never skipped"
    if s["parents"] != 1:
        return False, f"{s['parents']} parents (a merge commit): its tree was never tested on a PR"
    pr = s.get("pr")
    if not pr:
        return False, "no merged PR maps to this commit (a direct push)"
    if pr["merge_sha"] != s["sha"]:
        return False, "the PR's merge commit is another commit"
    if pr["head_tree"] != s["tree"]:
        return False, "main's tree differs from the PR head's tree (the PR was behind main, or main moved)"
    if not s.get("parent_in_head"):
        return False, "the PR head does not contain main's previous commit (its test merge was another tree)"
    if pr.get("base") != "main":
        return False, f"the PR's base is {pr.get('base')!r}, not main"
    run = newest_run(s.get("runs", []))
    if run is None:
        # Also the paths-filter case (#4964): a workflow whose pull_request `paths` skipped this PR has no run on the head,
        # while its push filter (or none, tree-sitter-accuracy-audit) still fires on main. Absence is never a proof.
        return False, "no pull_request run of this workflow on the PR head (its PR paths filter may have skipped it)"
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        return False, f"the PR head's newest run is {run.get('status')}/{run.get('conclusion')}, not a green verdict"
    return True, f"tree {s['tree'][:12]} passed in PR run {run['id']}"


REAL_EVENTS = ("push", "schedule", "workflow_dispatch")


def started(r: dict[str, Any]) -> float:
    stamp = r.get("run_started_at") or r.get("created_at") or ""
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()


def defer(runs: list[dict[str, Any]], run_id: int, now: float, cadence_s: float) -> tuple[bool, str, str]:
    """-> (defer?, reason, base). runs: this workflow's recent runs on branch main; run_id: this run (a re-run keeps its
    id). A real run is one of REAL_EVENTS that is not this run and did not end cancelled (a deferred run cancels
    itself). base: the newest real run's head SHA ('' when there is none)."""
    real = [r for r in runs if r.get("event") in REAL_EVENTS and r.get("id") != run_id
            and not (r.get("status") == "completed" and r.get("conclusion") == "cancelled")]  # fmt: skip
    if not real:
        return False, "no earlier real run on main", ""
    last = max(real, key=started)
    base = str(last.get("head_sha") or "")
    if last.get("status") != "completed":
        return True, f"run {last.get('id')} on main is still {last.get('status')}", base
    age = now - started(last)
    if age < cadence_s:
        return True, f"run {last.get('id')} on main started {age / 60:.0f} min ago (cadence {cadence_s / 3600:g} h)", base
    return False, f"main last checked {age / 3600:.1f} h ago (cadence {cadence_s / 3600:g} h)", base


# --- GitHub I/O -----------------------------------------------------------------------------------------------------


def gh(path: str) -> Any:
    res = subprocess.run(["gh", "api", path], capture_output=True, text=True, check=False)  # noqa: S603, S607
    if res.returncode:
        raise RuntimeError(f"gh api {path[:100]} failed: {res.stderr.strip()[:200]}")
    return json.loads(res.stdout)


def snapshot(repo: str, workflow: str, env: dict[str, str]) -> dict[str, Any]:
    s: dict[str, Any] = {
        "event": env.get("GITHUB_EVENT_NAME", ""),
        "ref": env.get("GITHUB_REF", ""),
        "sha": env.get("GITHUB_SHA", ""),
        "parents": 0, "tree": "", "pr": None, "parent_in_head": None, "runs": [],
    }  # fmt: skip
    if s["event"] != "push" or s["ref"] != MAIN_REF:
        return s
    commit = gh(f"repos/{repo}/commits/{s['sha']}")
    s["parents"], s["tree"] = len(commit["parents"]), commit["commit"]["tree"]["sha"]
    if s["parents"] != 1:
        return s
    merged = [
        p
        for p in gh(f"repos/{repo}/commits/{s['sha']}/pulls?per_page=100")
        if p.get("merged_at") and p.get("merge_commit_sha") == s["sha"]
    ]
    if len(merged) != 1:
        return s
    head_sha = merged[0]["head"]["sha"]
    head = gh(f"repos/{repo}/commits/{head_sha}")
    s["pr"] = {
        "head_tree": head["commit"]["tree"]["sha"],
        "merge_sha": merged[0]["merge_commit_sha"],
        "base": (merged[0].get("base") or {}).get("ref"),
    }
    parent = commit["parents"][0]["sha"]
    s["parent_in_head"] = gh(f"repos/{repo}/compare/{parent}...{head_sha}")["status"] in ("ahead", "identical")
    if s["pr"]["head_tree"] == s["tree"] and s["parent_in_head"]:
        doc = gh(f"repos/{repo}/actions/workflows/{workflow}/runs?head_sha={head_sha}&event=pull_request&per_page=100")
        s["runs"] = doc.get("workflow_runs", [])
    return s


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    env = dict(os.environ)
    try:
        skip, reason = decide(snapshot(env["GITHUB_REPOSITORY"], argv[1], env))
    except Exception as exc:  # fail-open: never let the gate's own trouble hide a run  # noqa: BLE001
        skip, reason = False, f"gate error, running the workflow: {exc}"
    late, base, why = False, "", ""
    cadence_h = env.get("CADENCE_HOURS", "")
    if (not skip and cadence_h and env.get("GITHUB_EVENT_NAME") == "push"
            and env.get("GITHUB_REF") == MAIN_REF):  # fmt: skip
        try:
            doc = gh(f"repos/{env['GITHUB_REPOSITORY']}/actions/workflows/{argv[1]}/runs?branch=main&per_page=30")
            late, why, base = defer(doc.get("workflow_runs", []), int(env.get("GITHUB_RUN_ID") or 0), time.time(),
                                    float(cadence_h) * 3600)  # fmt: skip
        except Exception as exc:  # fail-open: a cadence that cannot be read runs the workflow  # noqa: BLE001
            late, why, base = False, f"cadence unreadable, running: {exc}", ""
    lines = [f"skip={'true' if skip else 'false'}", f"defer={'true' if late else 'false'}", f"base={base}"]
    print(f"{lines[0]}: {reason}")
    if why:
        print(f"{lines[1]}: {why}" + (f" (base {base[:12]})" if base else ""))
    if env.get("GITHUB_OUTPUT"):
        with open(env["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    if env.get("GITHUB_STEP_SUMMARY"):
        verb = ("Skipped the heavy jobs" if skip else "Deferred to the hourly cadence (this run cancels itself)" if late
                else "Ran the heavy jobs")  # fmt: skip
        with open(env["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write(f"**tested-tree (#4935):** {verb}: {why if late else reason}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
