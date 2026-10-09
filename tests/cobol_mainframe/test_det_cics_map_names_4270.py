"""#4270: BMS map / mapset names in SEND MAP / RECEIVE MAP (IBM CICS TS: a name is 1-8 characters, blank-padded; MAPSET
defaults to the MAP name; a map lives in its own mapset). CBSA's BNK1CCS asks for MAP('BNK1CCM') with no MAPSET, but
BNK1CCM is the mapset (its map is BNK1CC); the NexusBank programs write 'NBLKMAP ' with a trailing blank."""

from __future__ import annotations

import pytest

pytest.importorskip("tree_sitter_language_pack")

from gitgalaxy.tools.cobol_to_java.det import cics as C  # noqa: E402


def _cics(tmp_path):
    d = tmp_path / "src/main/java/x/dto/screen"
    d.mkdir(parents=True)
    (d / "BnkCcScreen.java").write_text(
        'class BnkCcScreen { public static final String MAP = "BNK1CC";\n'
        '  public static final String MAPSET = "BNK1CCM"; }\n',
        encoding="utf-8",
    )
    c = C.Cics.__new__(C.Cics)
    c.gp = C.Generated(tmp_path, "")
    return c


def test_generated_records_each_mapset_with_its_maps(tmp_path):
    c = _cics(tmp_path)
    assert c.gp.screens == {"BNK1CC": "BnkCcScreen"}
    assert c.gp.mapsets == {"BNK1CCM": ["BNK1CC"]}


def test_trailing_blank_in_a_map_literal_is_the_same_name(tmp_path):
    c = _cics(tmp_path)
    m, ms, _ = c.map_names({"MAP": "'BNK1CC  '", "MAPSET": "'BNK1CCM '"}, None, "O", "")
    assert (m, ms) == ("BNK1CC", "BNK1CCM")


def test_a_mapset_name_asked_for_as_a_map_is_refused_by_name(tmp_path):
    c = _cics(tmp_path)
    with pytest.raises(C.CicsError) as e:
        c.send_map({"MAP": "'BNK1CCM'", "MAPONLY": None, "ERASE": None}, "")
    msg = str(e.value)
    assert "map BNK1CCM" in msg and "MAPSET omitted" in msg and "BNK1CC" in msg and "not modelled" in msg


def test_a_map_with_no_bms_source_keeps_the_plain_refusal(tmp_path):
    c = _cics(tmp_path)
    with pytest.raises(C.CicsError, match="no generated screen for map NOPE"):
        c.receive_map({"MAP": "'NOPE'", "MAPSET": "'NOPESET'"}, "")
