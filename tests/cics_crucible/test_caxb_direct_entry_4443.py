"""#4443: a typed-transid step of a strengthened scenario may enter its program with a COMMAREA of its own
(`commarea: {"hex", "length"}`), so a program only a RETURN TRANSID reaches (CAXB, CA03) is proven on a short or
odd area without a neighbour program passing one. The stub's `commarea.in` is the first `length` bytes of the record."""

import json
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS))
import cics_crucible as C  # noqa: E402  (bare import: tests/ has no __init__.py, see CLAUDE.md)

STRENGTHENED = Path(__file__).resolve().parent / "strengthened" / "ca-xctl-versions"
DIRECT = ("direct-8-byte-area", "direct-22-byte-area", "direct-negative-balance")


def test_a_step_without_a_commarea_starts_with_none():
    assert C.step_commarea({"at": 0, "aid": "ENTER", "text": "CA03"}) is None


def test_the_commarea_is_the_first_length_bytes_of_the_record():
    step = {"text": "CA03", "commarea": {"hex": "32C3F0F0F0F1", "length": 4}}
    assert C.step_commarea(step) == bytes.fromhex("32C3F0F0")
    assert C.step_commarea({"commarea": {"hex": "3243"}}) == b"2C"  # no length: the whole record


def test_a_malformed_record_is_refused_not_guessed():
    with pytest.raises(ValueError):
        C.step_commarea({"commarea": {"hex": "3Z", "length": 1}})


def test_a_step_with_no_commarea_is_the_java_plan_s_step_unchanged():
    step = {"at": 0, "aid": "ENTER", "text": "CA02 S"}
    assert C.seeded_step(None, Path("."), step) is step


@pytest.mark.parametrize("scenario", DIRECT)
def test_each_direct_entry_scenario_has_a_derived_log_from_the_cobol(scenario):
    case = json.loads((STRENGTHENED / "case.json").read_text(encoding="utf-8"))
    sc = next(s for s in case["scenarios"] if s["id"] == scenario)
    step = sc["steps"][0]
    assert step["text"] == "CA03" and len(bytes.fromhex(step["commarea"]["hex"])) == 80
    log = json.loads((STRENGTHENED / "expected" / f"{scenario}.json").read_text(encoding="utf-8"))
    assert log["tasks"][0]["eibcalen"] == step["commarea"]["length"]
