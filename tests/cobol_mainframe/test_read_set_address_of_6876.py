"""#6876 (oracle_assumptions.md X47 / X58): READ / READNEXT / READPREV SET(ADDRESS OF rec), rec a LINKAGE 01 record.

IBM lets SET name `ADDRESS OF` a LINKAGE record instead of a pointer; the record then views the block holding the file's
record (as SET ADDRESS OF rec TO ptr would). The translator emits DetCics.setBlockAt for it, setBlock for a pointer, and
refuses by name any other record.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_det_translate as T  # (bare imports: tests/ has no __init__.py, see CLAUDE.md)


class _LinkCics(T._PtrCics):
    def __init__(self):
        super().__init__()
        from gitgalaxy.tools.cobol_to_java.det import layout as L
        from gitgalaxy.tools.cobol_to_java.det.gen import Gen

        items = {"PTR": L.Item(1, "PTR", "WORKING-STORAGE", usage="POINTER"),
                 "REC": L.Item(1, "REC", "WORKING-STORAGE"),
                 "LS-REC": L.Item(1, "LS-REC", "LINKAGE"),
                 "LS-SUB": L.Item(5, "LS-SUB", "LINKAGE")}  # fmt: skip
        self.g.resolve = lambda ref: items[ref.name]
        self.g.address_record = types.MethodType(Gen.address_record, self.g)


_SHAPES = [
    ("READ FILE('KSDS') SET(ADDRESS OF LS-REC) RIDFLD(KEY)", 'DetCics.setBlockAt(task, f_LS-REC, "READ " + '),
    ("READ FILE('KSDS') SET(address  of ls-rec) RIDFLD(KEY) UPDATE", 'DetCics.setBlockAt(task, f_LS-REC, "READ " + '),
    ("READNEXT FILE('KSDS') SET(ADDRESS OF LS-REC) RIDFLD(KEY)", 'DetCics.setBlockAt(task, f_LS-REC, "BROWSE " + '),
    ("READPREV FILE('KSDS') SET(ADDRESS OF LS-REC) RIDFLD(KEY)", 'DetCics.setBlockAt(task, f_LS-REC, "BROWSE " + '),
    ("READ FILE('KSDS') SET(PTR) RIDFLD(KEY)", 'DetCics.setBlock(task, f_PTR, "READ " + '),
    ("READNEXT FILE('KSDS') SET(PTR) RIDFLD(KEY)", 'DetCics.setBlock(task, f_PTR, "BROWSE " + '),
]  # fmt: skip


@pytest.mark.parametrize(("text", "hold"), _SHAPES)
def test_set_address_of_a_linkage_record_gets_the_block(text, hold):
    out = "\n".join(_LinkCics().command(text, ""))
    assert hold in out, out
    assert ("setBlockAt" in out) == ("ADDRESS" in text.upper())


@pytest.mark.parametrize(
    ("name", "why"),
    [("LS-SUB", "subordinate item"), ("REC", "not a LINKAGE 01 record")],
)
def test_set_address_of_any_other_record_is_refused_by_name(name, why):
    with pytest.raises(T.C.CicsError, match=why):
        _LinkCics().command(f"READ FILE('KSDS') SET(ADDRESS OF {name}) RIDFLD(KEY)", "")


@pytest.mark.parametrize(
    ("text", "holds"),
    [
        ("READ FILE('KSDS') SET(ADDRESS OF LS-REC) RIDFLD(KEY)", ["task.readSetEvent(", ", false, () ->"]),
        ("READ FILE('KSDS') SET(ADDRESS OF LS-REC) RIDFLD(KEY) UPDATE", ["task.readSetEvent(", ", true, () ->"]),
        ("READNEXT FILE('KSDS') SET(ADDRESS OF LS-REC) RIDFLD(KEY)", ["task.readnextSetEvent(", "byte[] rid"]),
        ("READPREV FILE('KSDS') SET(ADDRESS OF LS-REC) RIDFLD(KEY)", ["task.readprevSetEvent(", "byte[] rid"]),
        ("STARTBR FILE('KSDS') RIDFLD(KEY)", ["task.startbrEvent(", "byte[] rid"]),
        ("STARTBR FILE('KSDS') RIDFLD(KEY) EQUAL", ["task.startbrEvent(", ", true, () -> "]),
        ("ENDBR FILE('KSDS')", ["task.endbrEvent("]),
    ],
)
def test_the_file_commands_record_their_spec_6_2_events(text, holds):
    """#7434: the event forms of CicsTask (READ with `set`, READNEXT / READPREV with `set`, STARTBR, ENDBR)."""
    cics = _LinkCics()
    cics.g.p = types.SimpleNamespace(
        proc=types.SimpleNamespace(execs={1: "READNEXT FILE('KSDS') SET(PTR) RIDFLD(KEY)"})
    )
    out = "\n".join(cics.command(text, ""))
    for h in holds:
        assert h in out, out


@pytest.mark.parametrize(
    ("text", "plain"),
    [("STARTBR FILE('KSDS') RIDFLD(KEY)", "task.startbr("), ("ENDBR FILE('KSDS')", "task.endbr(")],
)
def test_a_browse_that_reads_into_keeps_the_event_free_startbr_and_endbr(text, plain):
    """#7434: the COBOL stub records neither, so an INTO-form browse is not given the event forms (sibling gap)."""
    cics = _LinkCics()
    cics.g.p = types.SimpleNamespace(
        proc=types.SimpleNamespace(execs={1: "READNEXT FILE('KSDS') INTO(REC) RIDFLD(KEY)"})
    )
    out = "\n".join(cics.command(text, ""))
    assert plain in out and "Event(" not in out, out
