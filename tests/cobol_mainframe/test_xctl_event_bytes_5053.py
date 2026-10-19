"""#5053: an XCTL event's COMMAREA is compared by the bytes the caller handed the XCTL (the runtime's `area`, cut to the
XCTL's LENGTH), as a LINK's is (#5650): a numeric DISPLAY field holding spaces is invisible to a DTO."""

from __future__ import annotations

import base64
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
import cics_crucible as runner  # noqa: E402
import cics_crucible_compare as cc  # noqa: E402

from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CICS_TASK_JAVA  # noqa: E402


def _actual(monkeypatch, xctl: dict):
    dto = cc.FieldArea({"A-TXT": "    "}, 4, b"\xf0" * 4, 4)  # the DTO read the spaces as zeros
    monkeypatch.setattr(runner, "_java_area", lambda desc, src, shapes, length=None: dto if desc else None)
    monkeypatch.setattr(runner, "_answered_layout", lambda desc, shapes: None)
    ev = {"event": "XCTL", "program": "P1", "target": "P2", "length": 4, "resp": "NORMAL", "resp2": None,
          "commarea": {"class": "Dto", "value": {}}, **xctl}  # fmt: skip
    raw = {"tasks": [{"transid": "T001", "program": "P1", "commarea": None, "end": "return", "events": [ev]}]}
    return runner.java_actual(None, raw, Path("."))["tasks"][0]["events"][0]["commarea"]


def test_the_xctl_event_is_compared_by_the_bytes_the_caller_sent(monkeypatch):
    got = _actual(monkeypatch, {"area": base64.b64encode(b"    ").decode()})
    assert got.data == b"\x40" * 4 and got.known == 4  # spaces (X'40'), not the DTO's zeros


def test_an_xctl_without_area_bytes_falls_back_to_the_dto(monkeypatch):
    assert _actual(monkeypatch, {}).data == b"\xf0" * 4


def test_the_bytes_that_differ_from_the_sent_ones_are_seen(monkeypatch):
    a = _actual(monkeypatch, {"area": base64.b64encode(b"    ").decode()})
    b = _actual(monkeypatch, {"area": base64.b64encode(b"0000").decode()})
    assert a.data != b.data


def test_the_runtime_puts_the_cut_bytes_on_the_event_even_when_the_xctl_fails():
    """The byte overload tags the event the DTO form just recorded, before (and whatever) the resp, cut at LENGTH."""
    i = CICS_TASK_JAVA.index("public String xctl(String program, Object commarea, Integer length, byte[] area)")
    body = CICS_TASK_JAVA[i : CICS_TASK_JAVA.index("xctlArea = areaOf", i)]
    assert 'put("area", java.util.Base64.getEncoder().encodeToString(areaOf(area, length)))' in body
    assert body.index("if (area != null)") < body.index('if ("NORMAL".equals(resp))')
