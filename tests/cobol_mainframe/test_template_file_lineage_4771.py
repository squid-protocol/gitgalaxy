"""#4771 slice 2: a CICS file named by a template (zECS `FILE(ZF-FCT)`, a group of VALUE'd items spelling `ZC##FILE`)
reaches the CSD's `ZC@ID@FILE` store, and the det translator switches a run-time `ZC01FILE` onto it.

- galaxy_ir: `_group_template` reads the group's VALUEs; `_template_names` joins it to exactly one CSD name by
  wildcard shape; a group that is not plain valued X items, an ambiguous join and a template no CSD file fits resolve
  to nothing (never a guess);
- det/cics_filecontrol: `file_key_method` emits `fileKey` only for a template store;
- slice 3: det/cics `Generated._map_files` binds a file the program only DELETEs by RIDFLD (ZECS003's `ZC##KEY`: a
  void `deleteX(key)` stub, no `Optional<>` / `List<>` entity), naming the entity from the repository field.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import (
    EngineCicsResource,
    EngineDataItem,
    EngineFile,
    GalaxyIR,
)
from gitgalaxy.tools.cobol_to_java.det import cics_filecontrol as FC


def _item(ordinal, parent, level, name, pic=None, value=None, **kw):
    return EngineDataItem(
        ordinal, parent, level, name, "WORKING-STORAGE", None, pic, None, None, kw.get("occurs"), None,
        kw.get("redefines"), value, ordinal,
    )  # fmt: skip


def _group(*leaves, group="ZF-FCT"):
    """01 `group`. followed by one 02 leaf per (pic, value) -- children threaded as the reader does."""
    top = _item(1, None, 1, group)
    items = [top]
    for i, (pic, value, *rest) in enumerate(leaves, start=2):
        kw = rest[0] if rest else {}
        leaf = _item(i, 1, 2, "FILLER" if i % 2 else f"ZF-P{i}", pic, value, **kw)
        top.children.append(leaf)
        items.append(leaf)
    return items


def _ir(tmp_path, items, csd_names, monkeypatch, operand="ZF-FCT"):
    op = EngineCicsResource("READ", "FILE", "read", operand, None, "unresolved", None, None, None, None, None, None, 9)
    files = {"P.cbl": EngineFile("P.cbl", "cobol", 1, data_items=items, cics_resources=[op])}
    ir = GalaxyIR(tmp_path / "x.db", "r", "c", files)
    monkeypatch.setattr(
        GalaxyIR,
        "cics_file_datasets",
        lambda self: [{"file": n, "dsname": f"D.{n}", "bindings": [], "batch_programs": []} for n in csd_names],
    )
    return ir, files["P.cbl"], op


def test_group_of_valued_items_joins_the_one_template_csd_file(tmp_path, monkeypatch):
    items = _group(("X(04)", "ZC##"), ("X(04)", "FILE"))
    ir, ef, op = _ir(tmp_path, items, ["ZC@ID@FILE", "ZC@ID@KEY", "OTHER"], monkeypatch)
    assert ir._group_template(ef, "ZF-FCT") == "ZC##FILE"
    assert ir._template_names(ef, op, ["ZC@ID@FILE", "ZC@ID@KEY"]) == {"ZC@ID@FILE"}
    (entry,) = ir.cics_file_lineage()
    assert (entry["program"], entry["name"], len(entry["definitions"])) == ("P.cbl", "ZC@ID@FILE", 1)


@pytest.mark.parametrize(
    "leaves",
    [
        [("X(04)", "ZC##"), ("X(04)", None)],  # a leaf with no VALUE: filled at run time
        [("X(04)", "ZC##"), ("X(04)", "SPACES")],  # a figurative VALUE is not a name
        [("X(04)", "ZC##"), ("9(04)", "1234")],  # not an X item
        [("X(04)", "ZC##"), ("X(04)", "FILE", {"redefines": "ZF-OTHER"})],
        [("X(04)", "ZC##"), ("X(04)", "FILE", {"occurs": 2})],
    ],
)
def test_a_group_that_is_not_plain_valued_text_names_no_file(tmp_path, monkeypatch, leaves):
    ir, ef, op = _ir(tmp_path, _group(*leaves), ["ZC@ID@FILE"], monkeypatch)
    assert ir._template_names(ef, op, ["ZC@ID@FILE"]) == set()
    assert ir.cics_file_lineage() == []


def test_an_ambiguous_or_unmatched_template_is_not_a_guess(tmp_path, monkeypatch):
    ir, ef, op = _ir(tmp_path, _group(("X(04)", "ZC##"), ("X(04)", "FILE")), [], monkeypatch)
    assert ir._template_names(ef, op, ["ZC@ID@FILE", "ZC@XX@FILE"]) == set()  # two fit
    assert ir._template_names(ef, op, ["ZC@ID@KEY", "PLAIN"]) == set()  # none fits


def test_a_resolved_literal_file_is_left_alone(tmp_path, monkeypatch):
    ir, ef, _ = _ir(tmp_path, _group(("X(04)", "ZC##"), ("X(04)", "FILE")), ["ZC@ID@FILE"], monkeypatch)
    lit = EngineCicsResource(
        "READ", "FILE", "read", "'ZC@ID@FILE'", "ZC@ID@FILE", "literal", None, None, None, None, None, None, 3
    )
    assert ir._template_names(ef, lit, ["ZC@ID@FILE"]) == set()  # only an unresolved operand is read as a template


def test_file_key_method_is_emitted_only_for_template_stores():
    assert FC.file_key_method(["CUSTOMER", "ACCT"]) == []
    assert FC.file_key_call(["CUSTOMER"], "n") == "n"
    java = "\n".join(FC.file_key_method(["ZC@ID@FILE", "CUSTOMER"]))
    assert 'if (t.matches("ZC.+FILE")) return "ZC@ID@FILE";' in java
    assert "CUSTOMER" not in java
    assert FC.file_key_call(["ZC@ID@FILE"], "n") == "fileKey(n)"
    assert FC.file_key_method(["ZC##FILE"])[3] == '        if (t.matches("ZC.+FILE")) return "ZC##FILE";'


_DELETE_ONLY_STUB = """
/** Stand-in for EXEC CICS DELETE as CICS file ZK-FCT at ZECS003.cbl:210 */
public void deleteZkRecord(String key) {
    zkRecordRepository.deleteById(key);
}
"""


def test_a_delete_only_stub_binds_its_file_to_the_repository_entity():
    from gitgalaxy.tools.cobol_to_java.det.cics import Generated

    files: dict = {}
    Generated._map_files(_DELETE_ONLY_STUB, files)
    assert files == {"ZK-FCT": ("zkRecordRepository", "ZkRecord", None)}


def test_a_stub_without_a_repository_call_binds_nothing():
    from gitgalaxy.tools.cobol_to_java.det.cics import Generated

    files: dict = {}
    Generated._map_files("/** as CICS file X-FCT at P.cbl:1 */\npublic void f() { }\n", files)
    assert files == {}


CORPORA = os.environ.get("GITGALAXY_MAINFRAME_CORPORA")


@pytest.mark.skipif(not CORPORA or not (Path(CORPORA or "") / "zecs").is_dir(), reason="needs the zecs corpus")
def test_zecs_003_file_op_reaches_the_zc_id_file_store(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    import equivalence_cache as ec

    from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir

    import mainframe_corpus as mc

    try:  # #5882: the pinned clone's cached scan (the parts have it), else a scan of whatever clone is there
        db = mc.scan(mc.select(["zecs"])[0])
    except SystemExit:  # not fetched at its pin
        db = ec.scan_db(Path(CORPORA) / "zecs", tmp_path / "scan")
    ir = load_galaxy_ir(db)
    got = {(e["program"], e["name"]) for e in ir.cics_file_lineage()}
    assert ("Source/ZECS003.cbl", "ZC@ID@FILE") in got
