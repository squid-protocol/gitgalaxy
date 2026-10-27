"""#6271: since #6573 a WRITEQ whose LENGTH runs past FROM is written padded (X6); only LENGTH > 32767 is refused.
Prose that still says a task is judged up to *that* WRITEQ misstates it."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROSE = ("docs/language_status/det_port_design.md", "docs/wiki/05-19-proven-cobol-to-java-ports.md")


def test_prose_states_the_padded_writeq_and_the_32767_refusal():
    for rel in PROSE:
        text = " ".join((ROOT / rel).read_text(encoding="utf-8").split())
        assert "since #6573" in text.lower() or "Since #6573" in text, rel
        assert "32767" in text, rel
        assert "judged up to that refused WRITEQ" not in text, rel
        assert "That WRITEQ is refused on both sides" not in text, rel


def test_the_judged_up_to_words_name_the_32767_limit():
    sys_path = ROOT / "tests" / "tools"
    text = (sys_path / "equivalence_cics.py").read_text(encoding="utf-8")
    start = text.index("X6_JUDGED = (")
    assert "32767" in text[start : start + 400]
