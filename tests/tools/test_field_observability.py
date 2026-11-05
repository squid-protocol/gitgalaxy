"""#4175: field_observability's three facts on small programs -- each settles what it should and nothing else."""

import sys
from pathlib import Path

import pytest

pytest.importorskip("z3")
pytest.importorskip("tree_sitter_language_pack")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import branch_solver as bs
import field_observability as fo


def _obs(tmp_path, data: str, proc: str):
    lines = ["       IDENTIFICATION DIVISION.", "       PROGRAM-ID. T.", "       DATA DIVISION.",
             "       WORKING-STORAGE SECTION."]  # fmt: skip
    lines += [f"       {x}" for x in data.strip("\n").split("\n")]
    lines += ["       PROCEDURE DIVISION."] + [f"       {x}" for x in proc.strip("\n").split("\n")]
    src = tmp_path / "T.cbl"
    src.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return fo.Observability(bs.load_program(src, []), {})


def _decl(obs, name: str, off: int | None = None, ln: int | None = None) -> str:
    """A det-port Field declaration of item `name` (at another offset / length when given)."""
    it = next(x for x in obs.items.all if x.name.upper() == name)
    st = fo.storage(it).replace("-", "_")
    return f"private final Field f1_{name.replace('-', '_')} = Field.alphanumeric(s_{st}, {off if off is not None else it.offset}, {ln if ln is not None else it.size}, false);"


def test_a_declaration_line_names_item_record_offset_length():
    assert fo.decl("private final Field f69_TITLE01L = Field.binary(s_COADM1AI, 23, 4, 0, true, false);") == (
        "TITLE01L",
        "COADM1AI",
        23,
        4,
    )
    assert fo.decl("if (x) {") is None


AID_PROC = """
           EVALUATE EIBAID
               WHEN DFHENTER
                   CONTINUE
               WHEN DFHPF3
                   CONTINUE
               WHEN OTHER
                   CONTINUE
           END-EVALUATE
           EXEC CICS RETURN END-EXEC."""


def test_a_dfhaid_constant_no_comparison_tells_apart_is_settled(tmp_path):
    obs = _obs(tmp_path, "       COPY DFHAID.\n01 W PIC X.", AID_PROC)
    pf17 = next(x for x in obs.items.all if x.name.upper() == "DFHPF17")
    # one byte on: PF17 now reads PF18's byte; neither is compared, so every key matches the same comparisons
    assert obs.judge(_decl(obs, "DFHPF17"), _decl(obs, "DFHPF17", pf17.offset + 1)).startswith("DFHAID")


def test_a_compared_dfhaid_constant_moved_onto_another_key_is_not(tmp_path):
    obs = _obs(tmp_path, "       COPY DFHAID.\n01 W PIC X.", AID_PROC)
    pf3 = next(x for x in obs.items.all if x.name.upper() == "DFHPF3")
    # DFHPF3 reading PF4's byte: a PF4 press would now take the PF3 arm
    assert obs.judge(_decl(obs, "DFHPF3"), _decl(obs, "DFHPF3", pf3.offset + 1)) is None


def test_a_written_never_read_item_is_a_dead_window_and_a_read_one_is_not(tmp_path):
    data = "01 G.\n   05 W-OUT PIC X(4).\n   05 W-PAD PIC X(4).\n01 R PIC X(4) VALUE 'ABCD'.\n01 Z PIC X(4)."
    obs = _obs(
        tmp_path,
        data,
        "           MOVE 'XY' TO W-OUT\n           MOVE R TO Z\n           DISPLAY Z\n           GOBACK.",
    )
    assert obs.judge(_decl(obs, "W-OUT"), _decl(obs, "W-OUT", 1)).startswith("dead window")
    assert obs.judge(_decl(obs, "R"), _decl(obs, "R", 1)) is None  # R is read (MOVE R TO Z)


def test_a_relocated_item_is_settled_only_when_nothing_else_touches_either_window(tmp_path):
    data = "01 G.\n   05 A PIC X VALUE ' '.\n   05 B PIC X VALUE ' '.\n   05 C PIC X VALUE ' '."
    quiet = _obs(tmp_path, data, "           MOVE 'Q' TO A\n           DISPLAY A\n           GOBACK.")
    assert quiet.judge(_decl(quiet, "A"), _decl(quiet, "A", 1)).startswith("relocated")
    busy = _obs(tmp_path, data, "           MOVE 'Q' TO A\n           DISPLAY A B\n           GOBACK.")
    assert busy.judge(_decl(busy, "A"), _decl(busy, "A", 1)) is None  # B shares the mutant's byte and is read


MAP = """01 XMAPI.
   05 FILLER PIC X(12).
   05 TITLEL PIC S9(4) COMP.
   05 TITLEF PIC X.
   05 FILLER REDEFINES TITLEF.
      10 TITLEA PIC X.
   05 TITLEI PIC X(2).
   05 NOTEL PIC S9(4) COMP.
   05 NOTEF PIC X.
   05 FILLER REDEFINES NOTEF.
      10 NOTEA PIC X.
   05 NOTEI PIC X(2).
01 XMAPO REDEFINES XMAPI.
   05 FILLER PIC X(15).
   05 TITLEO PIC X(2).
   05 FILLER PIC X(3).
   05 NOTEO PIC X(2)."""


def test_map_subfields_that_only_hold_blanks_read_not_set_either_way(tmp_path):
    proc = """
           MOVE LOW-VALUES TO XMAPO
           MOVE 'HI' TO TITLEO
           EXEC CICS SEND MAP('XMAP') MAPSET('XSET') END-EXEC
           EXEC CICS RETURN END-EXEC."""
    obs = _obs(tmp_path, MAP, proc)
    a = next(x for x in obs.items.all if x.name.upper() == "TITLEA")
    assert obs.judge(_decl(obs, "TITLEA"), _decl(obs, "TITLEA", a.offset, 2)).startswith("map attribute")  # length
    assert obs.judge(_decl(obs, "TITLEA"), _decl(obs, "TITLEA", a.offset + 1)) is None  # onto TITLEO's 'H'
    ln = next(x for x in obs.items.all if x.name.upper() == "NOTEL")
    assert obs.judge(_decl(obs, "NOTEL"), _decl(obs, "NOTEL", ln.offset + 1)).startswith("map length")
    tl = next(x for x in obs.items.all if x.name.upper() == "TITLEL")
    assert (
        obs.judge(_decl(obs, "TITLEL"), _decl(obs, "TITLEL", tl.offset + 2)) is None
    )  # onto TITLEI / TITLEO, which the MOVE writes


def test_a_named_map_subfield_is_left_to_an_attack(tmp_path):
    proc = """
           MOVE LOW-VALUES TO XMAPO
           MOVE -1 TO TITLEL
           EXEC CICS SEND MAP('XMAP') MAPSET('XSET') END-EXEC
           EXEC CICS RETURN END-EXEC."""
    obs = _obs(tmp_path, MAP, proc)
    tl = next(x for x in obs.items.all if x.name.upper() == "TITLEL")
    assert obs.judge(_decl(obs, "TITLEL"), _decl(obs, "TITLEL", tl.offset + 1)) is None


def test_a_group_only_moved_into_a_shorter_item_is_truncated_either_way(tmp_path):
    data = (
        "01 R.\n   05 D.\n      10 D1 PIC X(4) VALUE 'ABCD'.\n      10 D2 PIC X(4) VALUE 'EFGH'.\n"
        "   05 TAIL PIC X(4) VALUE 'IJKL'.\n01 OUT8 PIC X(8).\n01 OUT9 PIC X(9)."
    )
    obs = _obs(tmp_path, data, "           MOVE D TO OUT8\n           DISPLAY OUT8\n           GOBACK.")
    grp = "private final Field f1_D = Field.group(s_R, 0, 8);"
    assert obs.judge(grp, grp.replace(", 0, 8)", ", 0, 9)")).startswith("truncated")
    wide = _obs(tmp_path, data, "           MOVE D TO OUT9\n           DISPLAY OUT9\n           GOBACK.")
    assert wide.judge(grp, grp.replace(", 0, 8)", ", 0, 9)")) is None  # a 9-byte target sees the extra byte
