"""The readings ledger (docs/family_oracle_readings.md) is ratified, not provisional (#8863, #8862)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tests" / "tools"))  # noqa: E402
sys.path.insert(0, str(REPO))  # noqa: E402

DOC = (REPO / "docs" / "family_oracle_readings.md").read_text(encoding="utf-8")


def _rows(section: str) -> list[list[str]]:
    """Table rows of the section starting at heading `section`, cells split on unescaped pipes."""
    body = DOC.split(section, 1)[1].split("\n## ", 1)[0]
    out = []
    for line in body.splitlines():
        if line.startswith("| ") and not line.startswith("| ---") and not line.startswith("|---"):
            out.append([c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))])
    return out


def test_no_tree_sitter_row_is_left_provisional():
    rows = _rows("## Non-Python oracles (tree-sitter)")
    verdicts = {r[0].strip("`"): r[2] for r in rows if len(r) == 4 and r[0].startswith("`")}
    assert verdicts, "the shared tree-sitter table was not found"
    assert not [k for k, v in verdicts.items() if "provisional" in v], verdicts
    assert "Not re-read" not in DOC


def test_every_ledger_family_has_a_contract_and_an_allowed_verdict():
    from gitgalaxy.standards.signal_contracts import CONTRACTS

    allowed = ("aligned", "realigned", "added", "open question")
    for section in ("## Non-Python oracles (tree-sitter)",):
        for r in _rows(section):
            if len(r) == 4 and r[0].startswith("`"):
                assert r[0].strip("`") in CONTRACTS, r[0]
                assert r[2].startswith(allowed), r


def test_every_spec_language_is_named_in_the_ledger():
    import family_oracle_ts as ts

    names = {"cpp": "C++", "csharp": "C#", "c_sharp": "C#", "bash": "shell"}
    for lang in ts.languages():
        assert names.get(lang, lang).lower() in DOC.lower(), lang


def test_the_cpp_stream_reading_is_recorded():
    assert "| C++ |" in DOC and "cin >>" in DOC


def test_the_2026_11_24_rulings_are_recorded_not_open():
    """#8862 closed with rulings: assert is not an abort, doc is the structured form, the C/C++ debug_prints fix landed."""
    seen = 0
    for line in DOC.splitlines():
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if cells and cells[0] in ("`panics_and_aborts`", "`doc`", "`debug_prints`") and len(cells) >= 4:
            seen += 1
            verdict = cells[-2]
            assert verdict.startswith("aligned"), line[:80]
    assert seen >= 5
    open_part = DOC.split("## Open owner questions", 1)[1]
    assert "Is `assert` an abort" not in open_part
    assert "Which documentation form" not in open_part
    assert "Ruled 2026-11-24" in open_part


def test_only_owner_only_questions_stay_open():
    """llm_api absences landed (#9275); generator expressions and C#/PHP `??` still need an owner ruling."""
    open_part = DOC.split("## Open owner questions", 1)[1]
    questions = re.findall(r"^\d+\. (.*)$", open_part, flags=re.M)
    assert len(questions) == 2, questions
    assert "comprehensions" in questions[0] and "generator expressions" in questions[0]
    assert "`??`" in questions[1]
    assert not any("llm_api" in q for q in questions)
    unplanted = (REPO / "docs" / "unplanted_family_contracts.md").read_text(encoding="utf-8")
    assert "### `llm_api` stated absences" in unplanted
