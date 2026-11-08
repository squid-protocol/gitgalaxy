"""#5565: a COMMAREA elementary item with its own OCCURS (a `List<T>` DTO property) is converted, not refused.

CardDemo's COPAUS0C / COPAUS1C carry `CDEMO-CPVS-PAUKEY-PREV-PG PIC X(08) OCCURS 20 TIMES` in their COMMAREA; the DTO
lists it as `List<String>` and the translator's hole read "a property the port cannot convert (List<String>)". The
layout's `bytes` is the whole table, so one occurrence is bytes / OCCURS, and occurrence i sits at offset + i * width.
"""

from __future__ import annotations

import sys
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
        (DTO.replace("List<String> caKeys", "String caKeys"), "cannot lay out"),
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


# ---- #8076: a DTO property the port cannot map is classified by its Java type, never `EXEC: other` -------------------
# The blind trial's 3 scrubbed keys were `... a property the port cannot convert (<type>)`: the census key dropped the
# type and scrub_key collapsed the rest. The forge emits Double (COMP-1 / COMP-2 / PIC F) and Boolean (PL/I BIT(1)).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import cics_census as cc  # noqa: E402
import gap_prevalence as gp  # noqa: E402

DTO8076 = """\
package com.x.dto.contract;

/**
 * COBOL record DFHCOMMAREA (TBLLNK.cbl), 20 bytes, from GitGalaxy's verified skeleton.
 */
public class TbllnkDfhcommarea {

    // CA-HEAD: PIC X(3), offset 0, 3 bytes (tblca.cpy)
    private String caHead;

%s
}
"""
PROPS = {
    "Double": "    // CA-RATE: COMP-2, offset 3, 8 bytes (tblca.cpy)\n    private Double caRate;",
    "Boolean": "    // CA-FLAG: BIT(1), offset 3, 1 bytes (tblca.cpy)\n    private Boolean caFlag;",
    "Float": "    // CA-F: COMP-1, offset 3, 4 bytes (tblca.cpy)\n    private Float caF;",
    "Object": "    // CA-ANY: PIC X(8), offset 3, 8 bytes (tblca.cpy)\n    private Object caAny;",
}


def _dto(tmp_path: Path, prop: str):
    from gitgalaxy.tools.cobol_to_java.det import cics as C

    contract = tmp_path / "proj/src/main/java/com/x/dto/contract"
    contract.mkdir(parents=True)
    (contract / "TbllnkDfhcommarea.java").write_text(DTO8076 % prop, encoding="utf-8")
    stub = "package com.x.service;\npublic class TbllnkService {}\n"
    return C.Generated(tmp_path / "proj", stub).dto("TbllnkDfhcommarea")


@pytest.mark.parametrize("jtype", sorted(PROPS))
def test_an_unconvertible_type_is_refused_by_its_type_and_the_census_keeps_it(tmp_path, jtype):
    from gitgalaxy.tools.cobol_to_java.det import cics as C

    with pytest.raises(C.CicsError) as e:
        _dto(tmp_path, PROPS[jtype])
    assert f"cannot convert ({jtype})" in str(e.value)
    key = cc.gap_key(f"line 9: EXEC EXEC CICS: {e.value}")
    assert key == f"EXEC CICS <class>.<property>: a property the port cannot convert ({jtype})"
    assert gp.scrub_key(key) == key  # no `EXEC: other`


def test_a_list_of_doubles_is_refused_by_its_element_type(tmp_path):
    from gitgalaxy.tools.cobol_to_java.det import cics as C

    prop = "    // CA-RATES: COMP-2, offset 3, 16 bytes (tblca.cpy)\n    // OCCURS 2 TIMES\n    private List<Double> caRates;"
    with pytest.raises(C.CicsError, match=r"cannot convert \(Double\)"):
        _dto(tmp_path, prop)


def test_a_class_name_type_never_reaches_the_census_key():
    key = cc.gap_key("line 9: EXEC EXEC CICS: AcmeCommarea.caX: a property the port cannot convert (AcmePayRecord)")
    assert "AcmePayRecord" not in key
    assert gp.scrub_key(key) == "EXEC CICS <class>.<property>: a property the port cannot convert"


def test_a_table_that_is_not_a_leaf_is_its_own_class(tmp_path):
    from gitgalaxy.tools.cobol_to_java.det import cics as C

    prop = "    // CA-KEYS: PIC X(8), offset 3, 8 bytes (tblca.cpy)\n    // OCCURS 2 TIMES\n    private String caKeys;"
    with pytest.raises(C.CicsError, match="cannot lay out") as e:
        _dto(tmp_path, prop)
    key = cc.gap_key(f"line 9: EXEC EXEC CICS: {e.value}")
    assert key == "EXEC CICS <class>.<property>: a property the port cannot lay out"
    assert gp.scrub_key(key) == key


def test_the_convertible_types_still_convert(tmp_path):
    prop = "    // CA-N: PIC S9(4) COMP, offset 3, 2 bytes (tblca.cpy)\n    private Integer caN;"
    assert [x.var for x in _dto(tmp_path, prop).leaves] == ["caHead", "caN"]
