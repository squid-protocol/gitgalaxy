"""#5053: the whole COMMAREA byte-channel class of the crucible driver. Every event kind of `java_actual` that carries
a COMMAREA's bytes compares them as bytes (`_with_answered_bytes` / `RawArea`), never through the DTO alone, so a facade
that stops producing the bytes is seen. A kind added to the class without its bytes fails here by name."""

from __future__ import annotations

import inspect
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
import cics_crucible as runner  # noqa: E402

# event branch (its `elif kind ...` head) -> the call that carries its bytes
BYTE_CARRIERS = {
    'kind == "RETURN" and (e.get("level") or 1) > 1': "_with_answered_bytes(",  # caller_commarea, area_bytes
    'kind == "RETURN":': 'e.get("answer_bytes")',
    'kind == "LINK"': 'e.get("area")',
    'kind == "XCTL"': 'e.get("area")',
    'kind == "START"': "cc.RawArea(base64.b64decode(b64), cc.EBCDIC)",
    'kind == "RETRIEVE"': "cc.RawArea(base64.b64decode(b64), cc.EBCDIC)",
}


def _branches() -> dict[str, str]:
    src = inspect.getsource(runner.java_actual)
    parts = re.split(r"\n            (?:el)?if (?=kind )", src)
    return {p.split("\n", 1)[0]: p for p in parts[1:]}


@pytest.mark.parametrize("head", sorted(BYTE_CARRIERS))
def test_every_commarea_event_kind_is_compared_by_its_bytes(head):
    branch = next((b for h, b in _branches().items() if h.startswith(head)), None)
    assert branch is not None, f"no java_actual branch for {head}"
    assert BYTE_CARRIERS[head] in branch


@pytest.mark.parametrize("head", ['kind == "LINK"', 'kind == "XCTL"', 'kind == "RETURN":'])
def test_a_commarea_branch_routes_its_bytes_through_the_page_conversion(head):
    branch = next(b for h, b in _branches().items() if h.startswith(head))
    assert "_with_answered_bytes(" in branch and "RUNTIME_PAGE" in branch
