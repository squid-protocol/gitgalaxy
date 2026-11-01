"""#5858 (register Q5): DSNTIAC is one model on two sides -- the port's Dsntiac.java and the oracle's dsntiac.c.

The text is a declared, unproven assumption; what is proved here is that the two sides hold the same table, so a
proof run compares like with like, and that COTRTLIC's CALL DSNTIAC translates with no hole."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")

ROOT = Path(__file__).resolve().parents[2]
JAVA = ROOT / "gitgalaxy/tools/cobol_to_java/det/cobolrt/le/Dsntiac.java"
C = ROOT / "tests/equivalence/le/dsntiac.c"
ENTRY = re.compile(r'"(-?\d+\|[^"]*)"')


def _entries(path: Path) -> list[str]:
    return ENTRY.findall(path.read_text(encoding="utf-8"))


def test_java_and_c_hold_the_same_message_table():
    java, c = _entries(JAVA), _entries(C)
    assert len(java) == 10
    assert java == c


def test_every_return_code_is_in_both_models():
    for path in (JAVA, C):
        text = path.read_text(encoding="utf-8")
        assert "SQLCA   " in text and "136" in text


def test_library_and_return_code_registration():
    from gitgalaxy.tools.cobol_to_java.det import dyncall, gen

    assert "DSNTIAC" in gen.LIBRARY and "DSNTIAC" in gen.LIBRARY_RC and "DSNTIAC" in gen.LIBRARY_CHARSET
    assert "DSNTIAC" not in dyncall.REFUSED_BY_NAME and "DSNTIAR" in dyncall.REFUSED_BY_NAME


def test_dsntiar_stays_refused_by_name_and_the_message_points_at_register_q5():
    """#4269: DSNTIAR is kept refused with a register entry; the refusal names the entry that exists on disk."""
    from gitgalaxy.tools.cobol_to_java.det import dyncall

    message = dyncall.REFUSED_BY_NAME["DSNTIAR"]
    assert "Db2's message text is not modelled" in message and "(register Q5)" in message
    register = " ".join((ROOT / "docs/language_status/register/Q5.md").read_text(encoding="utf-8").split())
    assert "DSNTIAR stays refused by name" in register and "DSNTIAR: Db2's message text is not modelled" in register
