"""#4964: every workflow with both a `pull_request` and a main `push` trigger is wired to the tested-tree gate, and the
gate's soundness does not depend on the two `paths` filters agreeing.

The proof a skipped push relies on is a `pull_request` run of the SAME workflow on the PR head. GitHub applies the
workflow's PR `paths` filter before creating that run, so a PR the filter skipped has no run and skip_tested_tree.decide()
runs the push (tests in test_skip_tested_tree.py). What can differ per workflow is only how often that happens; this
file pins each filter pair so a change to either side is a reviewed decision.

#5129: the gate runs on a main push only (a PR run never skips, so it only cost a runner and a serial queue wait).
#5131: the read-only crucibles left their push trigger for post-merge.yml's dispatch, and with it the gate
(test_post_merge_dispatch.py pins those); the gate is kept where the push run does work a dispatch cannot.
"""

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
GATED = [
    "mainframe-ground-truth",  # #4961; its push run appends and publishes the ground-truth history
    "smoke-test",  # #4961; the per-merge ubuntu full suite
    "java-compile",  # #4964; its push run builds main's tree (the base-generation cache is java-base-generation.yml's, #5142)
    "equivalence-e2e",  # #5954 slice 4; its post-merge run, planned from the pushed files, is skipped for a tree its PR run proved
]  # fmt: skip
# push `paths` entries the PR filter lacks (the push could fire on a change the PR run was never created for), and
# PR-only entries (the PR runs where the push does not: harmless). Pinned; an edit to a filter updates it knowingly.
PUSH_ONLY: dict[str, str] = {"equivalence-e2e": "no paths filter on either trigger: its plan job decides from the changed files"}
PR_ONLY = {"java-compile": {"tests/tools/mainframe_corpus.py"}}
# PR + main-push workflows that are not gated: their push run does something the PR run never did
NOT_GATED = {"generated-docs": "its push run publishes the rendered pages to `generated`; the PR run only renders"}


def load(name):
    doc = yaml.safe_load((WORKFLOWS / f"{name}.yml").read_text(encoding="utf-8"))
    doc["on"] = doc.pop(True, doc.get("on"))  # PyYAML reads the bare key `on` as True
    return doc


PUSH = "github.event_name == 'push'"


@pytest.mark.parametrize("name", GATED)
def test_gate_is_wired(name):
    doc = load(name)
    gate = doc["jobs"]["tested-tree"]
    runs = [s.get("run", "") for s in gate["steps"]]
    assert f"python tests/tools/skip_tested_tree.py {name}.yml" in runs  # the gate asks about ITS OWN workflow
    assert gate["permissions"] == {"contents": "read", "actions": "read", "pull-requests": "read"}
    # #5129: the gate runs on a main push only; elsewhere it is skipped, `skip` is empty and the heavy jobs run, so the
    # workflow still concludes success or failure for Main Watch
    assert str(gate.get("if")).strip() in (PUSH, "${{ " + PUSH + " }}")
    heavy = [j for k, j in doc["jobs"].items() if k != "tested-tree" and "tested-tree" in str(j.get("needs", ""))]
    assert heavy, "no job waits on tested-tree"
    # the aggregators (`full-suite`, #4961, ...) wait on the gate too and judge the skip themselves
    gated = [j for k, j in doc["jobs"].items() if j in heavy and k not in ("full-suite", "ground-truth", "equivalence-e2e")]
    assert gated
    for job in gated:
        assert "needs.tested-tree.outputs.skip != 'true'" in job["if"]
        assert "github.event.pull_request.draft == false" in job["if"]  # #5104: a skipped gate must not start it
        assert "!cancelled()" in job["if"]  # a gate crash leaves skip empty: the heavy job runs


@pytest.mark.parametrize("name", GATED[2:])
def test_every_non_gate_job_waits_on_the_gate(name):
    jobs = load(name)["jobs"]
    assert all("tested-tree" in str(j.get("needs", "")) for k, j in jobs.items() if k != "tested-tree")


@pytest.mark.parametrize("name", GATED[2:])
def test_trigger_pair_is_pinned(name):
    on = load(name)["on"]
    assert "pull_request" in on and "push" in on
    pr, push = on["pull_request"].get("paths"), on["push"].get("paths")
    assert on["push"]["branches"] == ["main"]
    if push is None:
        assert name in PUSH_ONLY  # the filter-less push: a PR the filter skipped has no run, so the push runs
        return
    assert name not in PUSH_ONLY
    assert pr is not None
    positive = lambda xs: {x for x in xs if not x.startswith("!")}  # noqa: E731
    assert positive(push) - positive(pr) == set(), "a push path with no PR-filter twin"
    assert positive(pr) - positive(push) == PR_ONLY.get(name, set())


def _main_push(on):
    push = on.get("push")
    return isinstance(push, dict) and "main" in (push.get("branches") or [])


def test_the_gate_is_exactly_where_a_pr_run_can_prove_a_push():
    """The class (#5129/#5131): a gate in a workflow with no main push is a runner spent on nothing, and a workflow run
    on both a PR and a main push without one repeats the PR's work on every merge."""
    both, gated = set(), set()
    for p in sorted(WORKFLOWS.glob("*.yml")):
        doc = load(p.stem)
        on = doc["on"] if isinstance(doc["on"], dict) else {}
        if "pull_request" in on and _main_push(on):
            both.add(p.stem)
        if "tested-tree" in (doc.get("jobs") or {}):
            gated.add(p.stem)
    assert gated == both - set(NOT_GATED) == set(GATED)


def test_scheduled_gated_workflows_still_run_in_full_on_schedule():
    # decide() never skips a schedule / workflow_dispatch run (test_never_skips_other_events); the gate passes the event on
    for name in GATED:
        assert "schedule" in load(name)["on"]
