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
import test_det_translate as T  # noqa: E402  (bare imports: tests/ has no __init__.py, see CLAUDE.md)


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
