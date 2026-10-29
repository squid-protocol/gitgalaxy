"""#6967 (register C20): a program whose paragraph can PERFORM itself gets the dispatcher's depth guard (the stop
GnuCOBOL's `-fstack-check` makes at 255 nested PERFORMs); a program without a PERFORM cycle gets no change."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from gitgalaxy.tools.cobol_to_java.det import source as SRC  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import stmt as S  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det.program import performs_cyclically  # noqa: E402

HEAD = ["IDENTIFICATION DIVISION.", "PROGRAM-ID. T.", "DATA DIVISION.", "WORKING-STORAGE SECTION.",
        "01 A PIC X.", "PROCEDURE DIVISION."]  # fmt: skip


def _proc(body: list[str]):
    return S.parse(SRC.logical_lines(["       " + t for t in HEAD + body], "t.cbl"))


@pytest.mark.parametrize(
    "body, cyclic",
    [
        (["MAIN.", "    PERFORM TERM.", "    GOBACK.", "TERM.", "    PERFORM TERM."], True),  # itself
        (
            ["MAIN.", "    PERFORM A1.", "    GOBACK.", "A1.", "    PERFORM B1.", "B1.", "    PERFORM A1."],
            True,
        ),  # via B1
        (
            [
                "MAIN.",
                "    PERFORM A1.",
                "    GOBACK.",
                "A1.",
                "    PERFORM B1 THRU C1.",
                "B1.",
                "    MOVE 'B' TO A.",
                "C1.",
                "    PERFORM A1.",
            ],
            True,
        ),  # a THRU range reaches C1, which PERFORMs A1
        (
            [
                "MAIN.",
                "    PERFORM A1.",
                "    PERFORM B1.",
                "    GOBACK.",
                "A1.",
                "    PERFORM B1.",
                "B1.",
                "    MOVE 'B' TO A.",
            ],
            False,
        ),  # a diamond is no cycle
        (["MAIN.", "    MOVE 'A' TO A.", "    GOBACK."], False),
    ],
)
def test_performs_cyclically(body: list[str], cyclic: bool) -> None:
    assert performs_cyclically(_proc(body)) is cyclic


def test_stack_check_is_opt_in() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    import equivalence_common as common  # noqa: E402

    src = "\n".join("       " + t for t in HEAD) + "\n"
    assert "-fstack-check" not in common.compile_options({}, src)[1]
    assert "-fstack-check" in common.compile_options({"perform_stack_check": True}, src)[1]
