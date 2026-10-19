"""#5565: a COMMAREA elementary item with its own OCCURS (a `List<T>` DTO property) is converted, not refused.

CardDemo's COPAUS0C / COPAUS1C carry `CDEMO-CPVS-PAUKEY-PREV-PG PIC X(08) OCCURS 20 TIMES` in their COMMAREA; the DTO
lists it as `List<String>` and the translator's hole read "a property the port cannot convert (List<String>)". The
layout's `bytes` is the whole table, so one occurrence is bytes / OCCURS, and occurrence i sits at offset + i * width.
"""

from __future__ import annotations

from pathlib import Path

import pytest

COPYBOOK = """\
          03 CA-HEAD                 PIC X(3).
          03 CA-KEYS                 PIC X(08) OCCURS 3 TIMES.
          03 CA-AMTS                 PIC S9(3) COMP-3 OCCURS 2 TIMES.
          03 CA-TAIL                 PIC X(5).
"""
DTO = """\
package com.x.dto.contract;

/**
 * COBOL record DFHCOMMAREA (TBLLNK.cbl), 37 bytes, from GitGalaxy's verified skeleton.
 */
public class TbllnkDfhcommarea {

    // CA-HEAD: PIC X(3), offset 0, 3 bytes (tblca.cpy)
    private String caHead;

    // CA-KEYS: PIC X(08), offset 3, 24 bytes (tblca.cpy)
    // OCCURS 3 TIMES
    private List<String> caKeys;

    // CA-AMTS: PIC S9(3) COMP-3, offset 27, 4 bytes (tblca.cpy)
    // OCCURS 2 TIMES
    private List<Integer> caAmts;

    // CA-TAIL: PIC X(5), offset 31, 5 bytes (tblca.cpy)
    private String caTail;
}
"""
TBLLNK = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TBLLNK.
       DATA DIVISION.
       LINKAGE SECTION.
       01 DFHCOMMAREA.
          COPY TBLCA.
       PROCEDURE DIVISION USING DFHCOMMAREA.
           MOVE CA-KEYS(2) TO CA-TAIL
           EXEC CICS RETURN END-EXEC.
"""
STUB = (
    "package com.x.service;\nimport com.x.cics.CicsTask;\nimport com.x.dto.contract.TbllnkDfhcommarea;\n"
    "public class TbllnkService {\n"
    "    public TbllnkDfhcommarea handleLink(TbllnkDfhcommarea request) { return request; }\n"
    "    public void runTask(CicsTask task) {}\n}\n"
)


def _project(tmp_path: Path, dto: str) -> Path:
    contract = tmp_path / "proj/src/main/java/com/x/dto/contract"
    contract.mkdir(parents=True)
    (contract / "TbllnkDfhcommarea.java").write_text(dto, encoding="utf-8")
    return tmp_path / "proj"


def test_a_list_property_is_one_leaf_of_n_occurrences(tmp_path):
    from gitgalaxy.tools.cobol_to_java.det import cics as C

    d = C.Generated(_project(tmp_path, DTO), STUB).dto("TbllnkDfhcommarea")
    assert [(x.var, x.jtype, x.offset, x.size, x.occurs) for x in d.leaves] == [
        ("caHead", "String", 0, 3, 1), ("caKeys", "String", 3, 8, 3),
        ("caAmts", "Integer", 27, 2, 2), ("caTail", "String", 31, 5, 1)]  # fmt: skip
    assert d.extent == 36  # the last property's end counts every occurrence


@pytest.mark.parametrize(
    "dto, why",
    [
        (DTO.replace("24 bytes", "25 bytes"), "not 3 equal items"),
        (DTO.replace("List<String> caKeys", "String caKeys"), "cannot convert"),
        (DTO.replace("List<Integer> caAmts", "List<Object> caAmts"), "cannot convert"),
    ],
)
def test_a_table_that_is_not_n_equal_convertible_items_is_still_refused_by_name(tmp_path, dto, why):
    from gitgalaxy.tools.cobol_to_java.det import cics as C

    with pytest.raises(C.CicsError, match=why):
        C.Generated(_project(tmp_path, dto), STUB).dto("TbllnkDfhcommarea")


def test_the_codec_places_occurrence_i_at_offset_plus_i_widths(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    proj = _project(tmp_path, DTO)
    (tmp_path / "TBLLNK.cbl").write_text(TBLLNK, encoding="utf-8")
    (tmp_path / "tblca.cpy").write_text(COPYBOOK, encoding="utf-8")
    vsam = proj / "src/main/java/com/x/entity/vsam"
    vsam.mkdir(parents=True)
    (vsam / "CobolRecords.java").write_text("package com.x.entity.vsam; public class CobolRecords {}\n")
    r = P.translate(tmp_path / "TBLLNK.cbl", [tmp_path], STUB, "com.x", {}, proj)
    assert not any("cannot convert" in h for h in r.stats["holes"]), r.stats["holes"]
    codec = r.java[r.java.index("private void in_TbllnkDfhcommarea") :]
    assert "for (int i = 0; i < 3; i++)" in codec and "base + 3 + i * 8" in codec
    assert "for (int i = 0; i < 2; i++)" in codec and "base + 27 + i * 2" in codec
    assert "d.setCaKeys(t)" in codec and "d.setCaAmts(t)" in codec
