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
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
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
    line = f"skip={'true' if skip else 'false'}"
    print(f"{line}: {reason}")
    if env.get("GITHUB_OUTPUT"):
        with open(env["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    if env.get("GITHUB_STEP_SUMMARY"):
        verb = "Skipped the heavy jobs" if skip else "Ran the heavy jobs"
        with open(env["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write(f"**tested-tree (#4935):** {verb}: {reason}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
