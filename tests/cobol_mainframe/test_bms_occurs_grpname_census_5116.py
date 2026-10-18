"""#5116: census of BMS OCCURS / GRPNAME fields in the burned estates (register X54, "Not modelled").

RECEIVE MAP does not justify per occurrence (OCCURS) or inherit a group's ATTRB (GRPNAME). That gap only matters if a
burned program's map has such a field the user can key into. This pins that none does, so a corpus bump that adds one
fails here and the gap gets a ticket, instead of staying unseen.
"""

import os
import re
import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import estate4_draw  # noqa: E402

from gitgalaxy.core.bms_screen_fields import bms_screen_fields  # noqa: E402
from gitgalaxy.core.source_text import read_source  # noqa: E402
from gitgalaxy.tools.cobol_to_java.cobol_to_java_screen_forge import _attrs  # noqa: E402

GRPNAME = re.compile(r"\bGRPNAME\s*=", re.I)


def _burned_maps():
    root = os.environ.get("GITGALAXY_MAINFRAME_CORPORA")
    if not root or not Path(root).is_dir():
        pytest.skip("GITGALAXY_MAINFRAME_CORPORA not available")
    found = [
        p
        for d in sorted(Path(root).iterdir())
        if d.name.lower() in estate4_draw.BURNED_NAMES
        for p in sorted(d.rglob("*.bms"))
        if ".git" not in p.parts
    ]
    if not found:
        pytest.skip("no burned-estate BMS source on disk")
    return found


def test_no_burned_map_uses_grpname():
    hits = [p.name for p in _burned_maps() if GRPNAME.search(read_source(p).text)]
    assert hits == [], f"GRPNAME in a burned map, X54 needs the group's ATTRB inheritance: {hits}"


def test_every_burned_occurs_field_is_output_only():
    occurs = {}
    for p in _burned_maps():
        for r in bms_screen_fields(read_source(p).text):
            if r["kind"] == "field" and (r.get("occurs") or 1) > 1:
                occurs[(p.name, (r["name"] or "").upper())] = _attrs(r)
    for key, attrs in occurs.items():
        assert attrs & {"ASKIP", "PROT"}, f"{key} is OCCURS and typable: per-occurrence JUSTIFY is reachable"
    # the one known: CBSA BNK1ACC's account list (a SEND-only row of 10)
    assert ("BNK1ACC.bms", "ACCOUNT") in occurs


def test_burned_maps_with_a_typable_initial_field():
    """IBM's DFHMDF note: input typed into a field BMS initialized overwrites only the equivalent length of the existing
    data. X54 does not model that; this pins which burned maps could reach it, so a bump that adds one is seen."""
    maps = set()
    for p in _burned_maps():
        for r in bms_screen_fields(read_source(p).text):
            if r["kind"] == "field" and r["name"] and (r.get("initial") or "") != "":
                if not _attrs(r) & {"ASKIP", "PROT"}:
                    maps.add(p.name)
    known = {
        "BNK1B2M.bms", "BNK1CAM.bms", "BNK1CDM.bms", "BNK1MAI.bms", "BNK1TFM.bms", "COACTUP.bms", "COPAU00.bms",
        "CORPT00.bms", "COSGN00.bms", "COTRN00.bms", "COTRN01.bms", "COTRN02.bms", "COUSR00.bms", "epsmort.bms",
        "ssmap.bms",
    }  # fmt: skip
    assert maps == known, f"typable INITIAL fields changed: +{sorted(maps - known)} -{sorted(known - maps)}"


def test_no_burned_occurs_field_is_generated_as_map_input():
    """#4506: `Unsupported("BMS OCCURS input")` (RECEIVE MAP typing into NAME(n)) stays because no burned map has a typable
    OCCURS field; `bms_input_fields` must never offer one, so no generated case can reach the refusal."""
    import equivalence_inputs as ei

    checked = 0
    for p in _burned_maps():
        rows = bms_screen_fields(read_source(p).text)
        for m in (r for r in rows if r["kind"] == "map" and r["name"]):
            repeated = {
                r["name"].upper() + "I"
                for r in rows
                if r["kind"] == "field"
                and r["parent_ordinal"] == m["ordinal"]
                and r["name"]
                and (r.get("occurs") or 1) > 1
            }
            if not repeated:
                continue
            ei.bms_input_fields.cache_clear()
            try:
                got = ei.bms_input_fields(p.parent, m["name"])
            except ValueError:  # the map holds no typable field at all
                got = {}
            assert not repeated & set(got), f"{p.name}: an OCCURS field is offered as input: {repeated & set(got)}"
            checked += 1
    assert checked >= 1  # BNK1ACC
