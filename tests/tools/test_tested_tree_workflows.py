"""#4964: every workflow with both a `pull_request` and a main `push` trigger is wired to the tested-tree gate, and the
gate's soundness does not depend on the two `paths` filters agreeing.

The proof a skipped push relies on is a `pull_request` run of the SAME workflow on the PR head. GitHub applies the
workflow's PR `paths` filter before creating that run, so a PR the filter skipped has no run and skip_tested_tree.decide()
runs the push (tests in test_skip_tested_tree.py). What can differ per workflow is only how often that happens; this
file pins each filter pair so a change to either side is a reviewed decision.
"""

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
GATED = [
    "mainframe-ground-truth", "smoke-test",  # #4961
    "fact-crosscheck", "estate-crucible", "ports-compile", "java-compile", "cics-crucible", "unicode-gauntlet",
    "tree-sitter-accuracy-audit",  # #4964
]  # fmt: skip
# push `paths` entries the PR filter lacks (the push could fire on a change the PR run was never created for), and
# PR-only entries (the PR runs where the push does not: harmless). Pinned; an edit to a filter updates it knowingly.
PUSH_ONLY = {"tree-sitter-accuracy-audit": "no push filter: every main push"}
PR_ONLY = {
    "fact-crosscheck": {"tests/tools/crucible_pins.py"},
    "estate-crucible": {"tests/tools/crucible_pins.py"},
    "ports-compile": {
        "pyproject.toml", "tests/cobol_mainframe/corpora.json", "tests/_cics_crucible_pin.py", "tests/crucible_pins.toml",
        "tests/tools/cics_crucible.py", "tests/tools/equivalence_java.py", "tests/tools/equivalence_cache.py",
        "tests/tools/java_target_matrix.py", "tests/tools/mainframe_corpus.py", "tests/tools/crucible_pins.py",
    },
    "java-compile": {"tests/tools/mainframe_corpus.py"},
    "cics-crucible": {
        "pyproject.toml", "tests/tools/crucible_port_provenance.py", "gitgalaxy/tools/cobol_to_cobol/cobol_graveyard_finder.py",
        "tests/tools/equivalence_common.py", "tests/tools/equivalence_java.py", "tests/tools/java_target_matrix.py",
        "tests/tools/cobol_answer_key.py", "tests/tools/crucible_pins.py",
    },
    "unicode-gauntlet": {"pyproject.toml", ".github/workflows/unicode-gauntlet.yml"},
}  # fmt: skip


def load(name):
    doc = yaml.safe_load((WORKFLOWS / f"{name}.yml").read_text(encoding="utf-8"))
    doc["on"] = doc.pop(True, doc.get("on"))  # PyYAML reads the bare key `on` as True
    return doc


DRAFT_ONLY = "github.event_name != 'pull_request' || github.event.pull_request.draft == false"


@pytest.mark.parametrize("name", GATED)
def test_gate_is_wired(name):
    doc = load(name)
    gate = doc["jobs"]["tested-tree"]
    runs = [s.get("run", "") for s in gate["steps"]]
    assert f"python tests/tools/skip_tested_tree.py {name}.yml" in runs  # the gate asks about ITS OWN workflow
    assert gate["permissions"] == {"contents": "read", "actions": "read", "pull-requests": "read"}
    # the gate always runs outside a draft PR, so the workflow always concludes success or failure for Main Watch;
    # #5104: on a draft PR it is skipped with everything else (the heavy jobs carry the same draft condition)
    assert gate.get("if", DRAFT_ONLY).strip() in (DRAFT_ONLY, "${{ " + DRAFT_ONLY + " }}")
    heavy = [j for k, j in doc["jobs"].items() if k != "tested-tree" and "tested-tree" in str(j.get("needs", ""))]
    assert heavy, "no job waits on tested-tree"
    # smoke-test's `full-suite` aggregator (if: always(), #4961) waits on the gate too and judges the skip itself
    gated = [j for j in heavy if not str(j.get("if")).startswith("${{ always()")]
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


def test_scheduled_gated_workflows_still_run_in_full_on_schedule():
    # decide() never skips a schedule / workflow_dispatch run (test_never_skips_other_events); the gate passes the event on
    for name in ("java-compile", "cics-crucible"):
        assert "schedule" in load(name)["on"]


def test_tree_sitter_push_has_no_path_filter():
    on = load("tree-sitter-accuracy-audit")["on"]
    assert "paths" not in on["push"] and re.search(r"main", str(on["push"]["branches"]))
