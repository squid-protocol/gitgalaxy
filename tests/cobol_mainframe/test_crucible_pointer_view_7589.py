"""#7589 (register X47): the cics-crucible runner's COBOL side lowers a POINTER's numeric view the way the equivalence
harness does. Without it the oracle added 4 to the high half of the 8-byte pointer (CAGMPT) and the program died at the next
`SET ADDRESS OF`; the cell was ledgered as a failure of the cobol-stub side. The whole input class: `ADD` / `SUBTRACT` on the
view, `MOVE view TO view`, the zero test (`=` and `NOT =`, either side), and a use the oracle does not model."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import cics_crucible as runner  # noqa: E402

_HEAD = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. PVIEW.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-PTR                POINTER.
       01  WS-PTR2               POINTER.
       01  WS-PTR2-N REDEFINES WS-PTR2 PIC S9(8) COMP.
       01  WS-PTR3               POINTER.
       01  WS-PTR3-N REDEFINES WS-PTR3 PIC S9(8) COMP.
       01  WS-FLAG               PIC X VALUE 'N'.
       PROCEDURE DIVISION.
       MAIN-PARA.
"""
_TAIL = """           EXEC CICS RETURN END-EXEC.
"""


def _translate(tmp_path: Path, body: str):
    (tmp_path / "PVIEW.cbl").write_text(_HEAD + body + _TAIL, encoding="utf-8")
    case = SimpleNamespace(dir=tmp_path, data={"sources": {"cobol": ["PVIEW.cbl"]}})
    return runner.translate_programs(case)["PVIEW"]


@pytest.mark.parametrize(
    ("body", "needle"),
    [
        ("           SET WS-PTR2 TO WS-PTR\n           ADD 4 TO WS-PTR2-N\n", "GGCPTRADV"),
        ("           SET WS-PTR2 TO WS-PTR\n           SUBTRACT 4 FROM WS-PTR2-N\n", "GGCPTRADV"),
        ("           MOVE WS-PTR2-N TO WS-PTR3-N\n", "SET WS-PTR3 TO WS-PTR2"),
        ("           IF WS-PTR2-N = 0\n               MOVE 'Y' TO WS-FLAG\n           END-IF\n", "WS-PTR2 = NULL"),
        ("           IF WS-PTR2-N NOT = ZERO\n               MOVE 'Y' TO WS-FLAG\n           END-IF\n", "NOT = NULL"),
        ("           IF 0 = WS-PTR2-N\n               MOVE 'Y' TO WS-FLAG\n           END-IF\n", "WS-PTR2 = NULL"),
    ],
    ids=["add", "subtract", "move", "eq-zero", "not-eq-zero", "zero-left"],
)
def test_a_numeric_view_of_a_pointer_is_lowered_to_pointer_arithmetic(tmp_path, body, needle):
    out = _translate(tmp_path, body)
    assert not isinstance(out, Exception), out
    text, _has_commarea = out
    assert needle in text
    code = [ln for ln in text.split("\n") if len(ln) > 6 and ln[6] != "*"]
    assert not any(v in ln for ln in code for v in ("PTR2-N", "PTR3-N"))  # the view's declaration and uses are gone


def test_a_program_with_no_view_is_translated_unchanged(tmp_path):
    body = "           SET WS-PTR2 TO WS-PTR\n           MOVE 'Y' TO WS-FLAG\n"
    text = _translate(tmp_path, body)[0]
    assert "GGCPTRADV" not in text and "NULL" not in text


@pytest.mark.parametrize(
    "body",
    [
        "           IF WS-PTR2-N > 0\n               MOVE 'Y' TO WS-FLAG\n           END-IF\n",
        "           MOVE 5 TO WS-PTR2-N\n",
        "           COMPUTE WS-PTR2-N = WS-PTR2-N + 4\n",
    ],
    ids=["ordering", "move-number", "compute"],
)
def test_a_use_the_oracle_does_not_model_is_refused_by_name(tmp_path, body):
    out = _translate(tmp_path, body)
    assert isinstance(out, runner_unsupported())
    assert out.features == ["POINTER numeric view"]
    assert "numeric view of the POINTER" in str(out)


def runner_unsupported():
    import equivalence_cics as ec

    return ec.Unsupported
