"""#5104: a draft PR starts only the cheap audits; every heavy pull_request workflow skips on a draft.

The free-tier runner pool is shared, and churn workers push WIP to draft PRs. A heavy `pull_request` workflow must
(1) list `ready_for_review` in its `types` (that event starts the full set when the PR is marked ready) and
(2) carry the draft condition on every job, so a draft PR starts no heavy job. The condition must not block
push / schedule / dispatch runs (`github.event.pull_request.draft` is null there).
"""

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
CHEAP = {"ruff-audit.yml", "mypy-audit.yml", "small-audits.yml", "answer-key-guard.yml"}  # run on drafts too
NOT_ON_PR = {  # jobs that cannot start on a pull_request event (their own `if` excludes it)
    ("generated-docs.yml", "publish"),
    ("gitgalaxy.yml", "full-report"),
    ("mainframe-ground-truth.yml", "publish-history"),
    ("smoke-test.yml", "full-suite-durations"),
    # #5129: the post-merge tested-tree gate runs on a main push only
    ("smoke-test.yml", "tested-tree"),
    ("mainframe-ground-truth.yml", "tested-tree"),
    ("java-compile.yml", "tested-tree"),
    ("equivalence-e2e.yml", "tested-tree"),
    ("doom-rosetta.yml", "callgraph"),  # #5630: nightly / manual only
    # #6670: post-merge dispatch + nightly only; the pull_request trigger stays for its `paths` (the dispatch filter)
    ("fact-crosscheck.yml", "crosscheck"),
    ("unicode-gauntlet.yml", "gauntlet"),
    ("estate-crucible.yml", "estate"),
    ("crucible-path-independence.yml", "path-independence"),
}
MARK = "github.event.pull_request.draft"
NON_PR = "github.event_name != 'pull_request'"


def _on(doc):
    return doc.get(True) or doc.get("on") or {}


def _load(path):
    # #5882: libyaml's loader where the wheel has it (this module parses every workflow at collection, per worker)
    return yaml.load(path.read_text(encoding="utf-8"), Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader))


def heavy_pr_workflows():
    out = {}
    for p in sorted(WORKFLOWS.glob("*.yml")):
        doc = _load(p)
        on = _on(doc)
        if isinstance(on, dict) and "pull_request" in on and p.name not in CHEAP:
            out[p.name] = doc
    return out


def problems(name, doc, not_on_pr=NOT_ON_PR):
    """Everything wrong with one heavy PR workflow's draft handling."""
    found = []
    pr = _on(doc)["pull_request"] or {}
    if "ready_for_review" not in (pr.get("types") or []):
        found.append(
            f"{name}: pull_request.types must list ready_for_review (explicitly, with opened/synchronize/reopened)"
        )
    for job, spec in doc["jobs"].items():
        if (name, job) in not_on_pr:
            continue
        cond = str((spec or {}).get("if") or "")
        if MARK not in cond or NON_PR not in cond:
            found.append(f"{name}: job {job!r} lacks the draft condition (`{NON_PR} || {MARK} == false`)")
    return found


def test_the_class_is_not_empty():
    assert len(heavy_pr_workflows()) >= 20


@pytest.mark.parametrize("name", sorted(heavy_pr_workflows()))
def test_heavy_pr_workflow_skips_drafts(name):
    assert problems(name, heavy_pr_workflows()[name]) == []


@pytest.mark.parametrize("name", sorted(CHEAP))
def test_cheap_audits_run_on_drafts(name):
    doc = _load(WORKFLOWS / name)
    assert "types" not in (_on(doc)["pull_request"] or {}) or "ready_for_review" in _on(doc)["pull_request"]["types"]
    for job, spec in doc["jobs"].items():
        assert MARK not in str((spec or {}).get("if") or ""), f"{name}:{job} must keep running on drafts"


def test_allowlisted_non_pr_jobs_really_exclude_pull_requests():
    for name, job in NOT_ON_PR:
        cond = str(_load(WORKFLOWS / name)["jobs"][job].get("if") or "")
        assert cond and ("pull_request'" in cond or "schedule" in cond or "event_name == 'push'" in cond), (name, job)


def test_pull_request_target_workflows_are_untouched():
    for p in WORKFLOWS.glob("*.yml"):
        if "pull_request_target" in _on(_load(p)):
            assert MARK not in p.read_text(encoding="utf-8"), (
                f"{p.name}: the shepherd's label events must not skip drafts"
            )


def test_every_heavy_workflow_job_is_checked_not_just_the_first():
    doc = {
        "on": {"pull_request": {"types": ["opened", "ready_for_review"]}},
        "jobs": {
            "a": {"if": f"${{{{ {NON_PR} || {MARK} == false }}}}"},
            "b": {"needs": "a"},  # no condition: must be reported
        },
    }
    found = problems("x.yml", doc)
    assert len(found) == 1 and "'b'" in found[0]


def test_missing_ready_for_review_and_a_bare_draft_test_are_reported():
    doc = {
        "on": {"pull_request": {"types": ["opened", "synchronize"]}},
        # `draft == false` alone is null-false on push/schedule/dispatch, which would disable those runs
        "jobs": {"a": {"if": f"{MARK} == false"}},
    }
    found = problems("x.yml", doc)
    assert any("ready_for_review" in f for f in found) and any("'a'" in f for f in found)
