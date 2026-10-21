"""#5053: a LINK event's COMMAREA is compared by the bytes the caller handed the LINK (the runtime's `area`, cut to the
LINK's LENGTH), not only by the DTO: a numeric DISPLAY field holding spaces is invisible to a DTO."""

from __future__ import annotations

import base64
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
import cics_crucible as runner  # noqa: E402
import cics_crucible_compare as cc  # noqa: E402


def _actual(monkeypatch, link: dict):
    dto = cc.FieldArea({"A-TXT": "    "}, 4, b"\xf0" * 4, 4)  # the DTO read the spaces as zeros
    monkeypatch.setattr(runner, "_java_area", lambda desc, src, shapes, length=None: dto if desc else None)
    monkeypatch.setattr(runner, "_answered_layout", lambda desc, shapes: None)
    ev = {"event": "LINK", "program": "P1", "target": "P2", "length": 4, "resp": "NORMAL", "resp2": None,
          "commarea": {"class": "Dto", "value": {}}, **link}  # fmt: skip
    raw = {"tasks": [{"transid": "T001", "program": "P1", "commarea": None, "end": "return", "events": [ev]}]}
    return runner.java_actual(None, raw, Path("."))["tasks"][0]["events"][0]["commarea"]


def test_the_link_event_is_compared_by_the_bytes_the_caller_sent(monkeypatch):
    got = _actual(monkeypatch, {"area": base64.b64encode(b"    TAIL").decode()})
    assert got.data == b"\x40" * 4 and got.known == 4  # spaces (X'40'), cut at the LINK's LENGTH, not the DTO's zeros


def test_a_link_without_area_bytes_falls_back_to_the_dto(monkeypatch):
    assert _actual(monkeypatch, {}).data == b"\xf0" * 4


def test_the_bytes_that_differ_from_the_sent_ones_are_seen(monkeypatch):
    a = _actual(monkeypatch, {"area": base64.b64encode(b"    ").decode()})
    b = _actual(monkeypatch, {"area": base64.b64encode(b"0000").decode()})
    assert a.data != b.data
