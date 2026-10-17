"""CALL MVSWAIT (#5106, CardDemo's COBSWAIT): the det translator's LIBRARY entry and the routine's two models."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LE = ROOT / "gitgalaxy" / "tools" / "cobol_to_java" / "det" / "cobolrt" / "le" / "Mvswait.java"
TWIN = ROOT / "tests" / "equivalence" / "le" / "mvswait.c"


def test_mvswait_is_a_one_argument_runtime_library_call():
    from gitgalaxy.tools.cobol_to_java.det import gen as G

    assert G.LIBRARY["MVSWAIT"] == ("__PACKAGE__.cobolrt.le.Mvswait.call", 1)
    assert "MVSWAIT" not in G.LIBRARY_CLOCK and "MVSWAIT" not in G.LIBRARY_CHARSET


def test_the_java_model_returns_at_once_and_touches_no_storage():
    text = LE.read_text(encoding="utf-8")
    assert "oracle_assumptions.md A1" in text and "[rule RT-LE-MVSWAIT]" in text
    body = text[text.index("public static void call") :]
    assert "Thread.sleep" not in text and "storage()" not in body  # not slept, nothing written to the caller
    assert "length() < FULLWORD" in body and "UnsupportedOperationException" in body  # a short argument is refused


def test_the_c_twin_is_the_entry_the_oracle_links_and_returns_zero():
    text = TWIN.read_text(encoding="utf-8")
    assert re.search(r"int MVSWAIT\(unsigned char \*\w+\)\s*\{\s*\(void\)\w+;\s*return 0;\s*\}", text)


def test_the_rule_is_registered():
    import json

    rules = json.loads((ROOT / "docs" / "language_status" / "cobolrt_rules.json").read_text(encoding="utf-8"))
    rows = [r for r in (rules["rules"] if isinstance(rules, dict) else rules) if r["id"] == "RT-LE-MVSWAIT"]
    assert len(rows) == 1 and rows[0]["site"] == "le/Mvswait.java:call" and rows[0]["register"] == ["A1"]
