"""#5133 slice 4: the nightly smoke run has its own concurrency group and is never cancelled.

It used to share main's group with `cancel-in-progress: true`, so the next push cancelled it about 5 minutes in and
`full-suite-durations` never stored the calibrated durations. The expressions are evaluated here for each event.
"""

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "smoke-test.yml"
NAME = "GitGalaxy Smoke Tests"


def _doc():
    return yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader))


def _evaluate(expr, event, pr, ref):
    """Expand each `${{ ... }}` of a concurrency value (GitHub truthiness; a bare boolean stays a boolean)."""

    def one(match):
        body = match.group(1).strip()
        body = body.replace("github.workflow", repr(NAME)).replace("github.event_name", repr(event))
        body = body.replace("github.event.pull_request.number", repr(pr)).replace("github.ref", repr(ref))
        body = body.replace("||", " or ").replace("&&", " and ")
        return eval(body, {"__builtins__": {}}, {})  # noqa: S307 -- the expression comes from the committed workflow

    text = str(expr).strip()
    whole = re.fullmatch(r"\$\{\{((?:(?!\$\{\{).)*?)\}\}", text, re.S)
    if whole:
        return one(whole)
    return re.sub(r"\$\{\{(.*?)\}\}", lambda m: str(one(m)), text, flags=re.S)


def _group(event, pr, ref):
    return _evaluate(_doc()["concurrency"]["group"], event, pr, ref)


def _cancel(event, pr, ref):
    value = _doc()["concurrency"]["cancel-in-progress"]
    return value if isinstance(value, bool) else _evaluate(value, event, pr, ref)


MAIN = "refs/heads/main"
CASES = [
    # event, PR number (None outside a PR), ref, group, cancel-in-progress
    ("schedule", None, MAIN, f"{NAME}-nightly", False),
    ("push", None, MAIN, f"{NAME}-{MAIN}", False),
    ("pull_request", 6186, "refs/pull/6186/merge", f"{NAME}-6186", True),
    ("workflow_dispatch", None, "refs/heads/some-branch", f"{NAME}-refs/heads/some-branch", True),
]


@pytest.mark.parametrize(("event", "pr", "ref", "group", "cancel"), CASES, ids=[c[0] for c in CASES])
def test_group_and_cancel_by_event(event, pr, ref, group, cancel):
    assert _group(event, pr, ref) == group
    assert _cancel(event, pr, ref) is cancel


def test_the_nightly_group_is_not_the_main_push_group():
    assert _group("schedule", None, MAIN) != _group("push", None, MAIN)


def test_the_workflow_still_has_a_schedule():
    on = _doc().get(True) or _doc().get("on")
    assert "schedule" in on


def test_a_main_push_is_never_cancelled_but_a_pr_is():
    """#6514: eight main push runs in a row were cancelled by the next push, so main never had a verdict."""
    assert _cancel("push", None, MAIN) is False
    assert _cancel("pull_request", 1, "refs/pull/1/merge") is True


def _durations_if(event, part_result):
    """Evaluate the `full-suite-durations` job condition (`!cancelled()` is true here; a skipped ancestor is not modelled)."""
    expr = _doc()["jobs"]["full-suite-durations"]["if"]
    body = re.fullmatch(r"\$\{\{(.*)\}\}", str(expr).strip(), re.S).group(1).strip()
    body = body.replace("!cancelled()", "True").replace("github.event_name", repr(event))
    body = body.replace("needs.full-suite-part.result", repr(part_result))
    return eval(body.replace("&&", " and "), {"__builtins__": {}}, {})  # noqa: S307 -- committed workflow expression


def test_the_nightly_stores_its_durations_though_tested_tree_is_skipped():
    """#5133 slice 8: a bare `success()` is false under a skipped ancestor (push-only `tested-tree`), so the green
    nightly 40179743618 skipped the job and no calibrated cache was written."""
    job = _doc()["jobs"]["full-suite-durations"]
    assert "success()" not in str(job["if"])
    assert "tested-tree" not in job["needs"]  # the condition must not lean on it either way
    assert _durations_if("schedule", "success") is True


@pytest.mark.parametrize(("event", "part"), [("push", "success"), ("pull_request", "success"), ("schedule", "failure")])
def test_durations_are_stored_only_by_a_nightly_whose_parts_passed(event, part):
    assert _durations_if(event, part) is False
