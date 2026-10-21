"""#5053: what an XCTL chain's RETURN shows the LINK caller (`caller_commarea`) is compared by the bytes the first
LINKed program left in the caller's area, not by the DTO (which reads a numeric DISPLAY field holding spaces as a
number). An XCTL target holds only a copy of the bytes XCTL passed, so the bytes are kept for the chain's RETURN."""

from __future__ import annotations

import base64
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
import cics_crucible as runner  # noqa: E402
import cics_crucible_compare as cc  # noqa: E402


def _body(src: str, head: str, end: str) -> str:
    i = src.index(head)
    return src[i : src.index(end, i)]


def test_the_first_program_keeps_its_bytes_when_it_xctled_instead_of_returning():
    body = _body(runner._JAVA_TEST, "void linkBytes(", "void entry(")
    assert "if (!tagReturn(task.level(), left, mark))" in body
    assert "callerLeft.put(task.level(), left);" in body
    assert "if (left == null || !task.linkAreaOfCaller())" in body  # a copy's bytes are never the caller's


def test_an_xctl_target_takes_the_kept_bytes_whether_or_not_it_has_the_bytes_overload():
    body = _body(runner._JAVA_TEST, "void enter(", "boolean tagReturn(")
    assert body.index("if (bytes) {\n                    linkBytes(") < body.index("task.linkAreaOfCaller() ? null : callerLeft.remove")
    assert "task.linkAreaOfCaller() ? null : callerLeft.remove(task.level())" in body
    assert "callerLeft.put(task.level(), kept);" in body  # A -> B -> C: B XCTLed on, C's RETURN takes them


def test_a_new_chain_at_the_level_forgets_an_earlier_ones_bytes():
    body = _body(runner._JAVA_TEST, "void enter(", "boolean tagReturn(")
    assert "if (task.linkAreaOfCaller()) {\n                    callerLeft.remove(task.level());" in body


def test_only_this_programs_own_events_can_be_tagged():
    """An earlier RETURN of the same level (an untagged one of a past LINK) is never given this chain's bytes."""
    body = _body(runner._JAVA_TEST, "boolean tagReturn(", "void linkBytes(")
    assert "i >= mark" in body and '!e.containsKey("area_bytes")' in body
    assert "int mark = scenarioTask.events().size();" in runner._JAVA_TEST


def test_the_caller_commarea_of_an_xctl_chain_is_compared_by_those_bytes():
    dto = cc.FieldArea({"A-NUM": 0}, 4, b"\xf0" * 4, 4)  # the DTO read the spaces as zeros
    left = base64.b64encode(b"    ").decode()
    got = runner._with_answered_bytes(dto, left, runner.RUNTIME_PAGE, None)
    assert got.data == b"\x40" * 4
    assert runner._with_answered_bytes(dto, None, runner.RUNTIME_PAGE, None) is dto  # none kept: the DTO's
