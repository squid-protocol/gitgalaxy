"""#7844: the symbolic-map copybooks the det translator writes from BMS source (`source.bms_copybooks`), over the
whole file class: a one-mapset file of several maps (one copybook named by the member, both maps inside), a file
of two mapsets (one copybook per mapset), and a file with no map (none). A program that COPYs the area then finds
`<MAP>I` / `<MAP>O` for every map; one that never COPYs it is the source's defect, named, not guessed.
"""

from __future__ import annotations

import pytest

pytest.importorskip("tree_sitter_language_pack")

from gitgalaxy.tools.cobol_to_java.det import source as S  # noqa: E402

_ONE_SET = """\
MULTI    DFHMSD TYPE=&&SYSPARM,LANG=COBOL,MODE=INOUT
MAPA     DFHMDI SIZE=(24,80)
FA       DFHMDF POS=(1,1),LENGTH=4
MAPB     DFHMDI SIZE=(24,80)
FB       DFHMDF POS=(1,1),LENGTH=6
         DFHMSD TYPE=FINAL
"""
_TWO_SETS = """\
SETONE   DFHMSD TYPE=MAP,LANG=COBOL
MAPA     DFHMDI SIZE=(24,80)
FA       DFHMDF POS=(1,1),LENGTH=4
         DFHMSD TYPE=FINAL
SETTWO   DFHMSD TYPE=MAP,LANG=COBOL
MAPB     DFHMDI SIZE=(24,80)
FB       DFHMDF POS=(1,1),LENGTH=6
         DFHMSD TYPE=FINAL
"""


def _make(tmp_path, name, text):
    f = tmp_path / "bms" / name
    f.parent.mkdir(exist_ok=True)
    f.write_text(text, encoding="utf-8")
    return f


def test_one_mapset_of_several_maps_is_one_copybook_named_by_the_member(tmp_path):
    out = tmp_path / "cpy"
    assert S.bms_copybooks([_make(tmp_path, "scr1.bms", _ONE_SET)], out) == ["SCR1"]
    text = (out / "SCR1.cpy").read_text(encoding="utf-8")
    for want in ("01  MAPAI.", "01  MAPAO REDEFINES MAPAI.", "01  MAPBI.", "01  MAPBO REDEFINES MAPBI.", "FAO", "FBO"):
        assert want in text


def test_two_mapsets_in_one_file_are_a_copybook_each_named_by_the_mapset(tmp_path):
    out = tmp_path / "cpy"
    assert sorted(S.bms_copybooks([_make(tmp_path, "scr2.bms", _TWO_SETS)], out)) == ["SETONE", "SETTWO"]
    assert "MAPAI" in (out / "SETONE.cpy").read_text(encoding="utf-8")
    assert "MAPBI" in (out / "SETTWO.cpy").read_text(encoding="utf-8")
    assert "MAPBI" not in (out / "SETONE.cpy").read_text(encoding="utf-8")


def test_a_file_with_no_map_writes_no_copybook(tmp_path):
    out = tmp_path / "cpy"
    assert S.bms_copybooks([_make(tmp_path, "none.bms", "* comment only\n")], out) == []
    assert list(out.iterdir()) == []
