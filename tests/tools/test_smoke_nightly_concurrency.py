"""#5133: the nightly full suite must complete, or `full-suite-durations` never stores the calibrated durations.

It once shared main's concurrency group with cancel-in-progress, so the next push cancelled it (8 of 8 nightlies)."""

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

SMOKE = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "smoke-test.yml"


def _concurrency() -> dict:
    return yaml.safe_load(SMOKE.read_text(encoding="utf-8"))["concurrency"]


def _group(event: str, ref: str = "refs/heads/main", pr: str = "") -> str:
    """Evaluate the second `${{ a || b || c }}` of the group for one event (the first is the workflow name)."""
    exprs = re.findall(r"\$\{\{(.*?)\}\}", _concurrency()["group"])
    assert len(exprs) == 2 and exprs[0].strip() == "github.workflow"
    values = {"github.event.pull_request.number": pr, "github.ref": ref}
    for operand in (o.strip() for o in exprs[1].split("||")):
        if operand.startswith("("):
            assert "github.event_name == 'schedule' && 'nightly'" in operand
            value = "nightly" if event == "schedule" else ""
        else:
            value = values[operand]
        if value:
            return value
    return ""


def _cancels(event: str) -> bool:
    expr = str(_concurrency()["cancel-in-progress"])
    assert "github.event_name != 'schedule'" in expr
    return event != "schedule"


def test_the_nightly_group_differs_from_the_main_push_group():
    assert _group("schedule") != _group("push")
    assert _group("schedule") == "nightly"
    assert _group("push") == "refs/heads/main"
    assert _group("pull_request", pr="42") == "42"


@pytest.mark.parametrize("event", ["push", "pull_request", "workflow_dispatch"])
def test_other_events_still_cancel_a_superseded_run(event):
    assert _cancels(event)


def test_the_nightly_is_never_cancelled():
    assert not _cancels("schedule")
