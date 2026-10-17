"""#4506: RECEIVE MAP input generated from the BMS map definitions (`"receive": {"MAP": "@bms"}`).

Pinned on a hand-written BMS source and symbolic-map layout: which DFHMDF fields can be typed into (named, not ASKIP or
PROT, not OCCURS; a field with no ATTRB is ASKIP), the value classes (NUM and PICIN 9s digits, text otherwise, full width /
short / random length, `bad`, `empty`), per-field overrides, determinism, and the whole map input through `prepare_cics_case`.
"""

import random
import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence_inputs as ei  # noqa: E402

BMS = """\
MAPSET   DFHMSD TYPE=&SYSPARM,MODE=INOUT,LANG=COBOL
TESTMAP  DFHMDI SIZE=(24,80)
         DFHMDF POS=(1,1),LENGTH=5,ATTRB=(ASKIP,NORM),INITIAL='Acct:'
ACCT     DFHMDF POS=(1,7),LENGTH=11,ATTRB=(UNPROT,NUM,FSET,IC)
NAME     DFHMDF POS=(2,7),LENGTH=20,ATTRB=(UNPROT,NORM)
STATE    DFHMDF POS=(3,7),LENGTH=2,ATTRB=FSET
CODE     DFHMDF POS=(4,7),LENGTH=8,ATTRB=(UNPROT),PICIN='9(5)'
TXT      DFHMDF POS=(5,7),LENGTH=6,ATTRB=(UNPROT),PICIN='X(4)'
ONE      DFHMDF POS=(6,7),LENGTH=1,ATTRB=(UNPROT)
LABEL    DFHMDF POS=(7,7),LENGTH=9
PROTD    DFHMDF POS=(8,7),LENGTH=9,ATTRB=(PROT,BRT)
ASKD     DFHMDF POS=(9,7),LENGTH=9,ATTRB=(ASKIP,BRT)
ROW      DFHMDF POS=(10,7),LENGTH=4,ATTRB=(UNPROT),OCCURS=3
OTHER    DFHMDI SIZE=(24,80)
OTHERF   DFHMDF POS=(1,1),LENGTH=3,ATTRB=(UNPROT)
         DFHMSD TYPE=FINAL
"""
TYPABLE = {"ACCTI": (11, True), "NAMEI": (20, False), "STATEI": (2, False), "CODEI": (5, True), "TXTI": (4, False),
           "ONEI": (1, False)}  # fmt: skip


@pytest.fixture
def corpus(tmp_path):
    (tmp_path / "bms").mkdir()
    (tmp_path / "bms" / "TESTMAP.bms").write_text(BMS, encoding="utf-8")
    ei.bms_input_fields.cache_clear()
    return tmp_path


def _layout(names=None):
    names = names or [n for n in TYPABLE]
    return {n: {"name": n, "bytes": 30} for n in names}


def test_only_fields_a_user_can_key_into_are_typable(corpus):
    got = ei.bms_input_fields(corpus, "TESTMAP")
    assert {k: (v["length"], v["numeric"]) for k, v in got.items()} == TYPABLE
    for gone in ("LABELI", "PROTDI", "ASKDI", "ROWI", "OTHERFI"):  # no ATTRB = ASKIP; PROT; ASKIP; OCCURS; another map
        assert gone not in got
    assert ei.bms_input_fields(corpus, "testmap") == got  # map names are case-blind
    assert ei.bms_input_fields(corpus, "OTHER") == {"OTHERFI": {"length": 3, "numeric": False, "picture": None}}


def test_a_map_with_no_typable_field_or_not_in_the_source_is_refused(corpus):
    with pytest.raises(ValueError, match="no typable field"):
        ei.bms_input_fields(corpus, "NOSUCH")


@pytest.mark.parametrize(("picin", "want"), [("9(5)", (5, True)), ("999", (3, True)), ("X(10)", (10, False)),
                                             ("'9(3)'", (3, True)), ("9(3)X(2)", (5, False)), ("S9(5)V99", None),
                                             ("", None), (None, None), ("Z(4)", None)])  # fmt: skip
def test_picin_is_read_for_its_width_and_digits_or_left_alone(picin, want):
    assert ei._picture(picin) == want


@pytest.mark.parametrize("i", range(12))
def test_each_typable_field_gets_a_value_of_its_class_at_most_its_length(corpus, i):
    rng = random.Random(i)
    got = ei._bms_receive(rng, "s", "@bms", _layout(), ei.bms_input_fields(corpus, "TESTMAP"), {}, i)
    assert set(got) == set(TYPABLE)
    for k, (length, numeric) in TYPABLE.items():
        assert 1 <= len(got[k]) <= length
        assert got[k].isdigit() if numeric else got[k].isalnum(), (k, got[k])


def test_values_cover_full_width_short_and_in_between(corpus):
    bms = ei.bms_input_fields(corpus, "TESTMAP")
    lens = set()
    for i in range(30):
        lens.add(len(ei._bms_receive(random.Random(i), "s", "@bms", _layout(), bms, {}, i)["NAMEI"]))
    assert 20 in lens and 10 in lens and len(lens) > 3


def test_bad_gives_text_that_is_not_a_number_and_empty_leaves_a_field_alone(corpus):
    bms = ei.bms_input_fields(corpus, "TESTMAP")
    spec = {"@bms": {"bad": 1.0, "empty": 0.5}}
    sizes, not_numbers = [], 0
    for i in range(60):
        got = ei._bms_receive(random.Random(i), "s", spec, _layout(), bms, {}, i)
        sizes.append(len(got))
        not_numbers += sum(1 for k, v in got.items() if not (v.isdigit() and v.strip("0")))
        assert all(len(v) <= TYPABLE[k][0] for k, v in got.items())
    assert min(sizes) < max(sizes) < len(TYPABLE) + 1 and any(s < len(TYPABLE) for s in sizes)
    assert not_numbers > 0.7 * sum(sizes)  # the bad pool's few all-digit entries (a long digit run cut to width) aside
    assert ei._bms_receive(random.Random(1), "s", {"@bms": {"empty": 1.0}}, _layout(), bms, {}, 1) == {}


def test_the_symbolic_map_decides_what_exists_and_its_width_caps_the_field(corpus):
    bms = ei.bms_input_fields(corpus, "TESTMAP")
    layout = {"NAMEI": {"name": "NAMEI", "bytes": 4}}
    for i in range(9):
        got = ei._bms_receive(random.Random(i), "s", "@bms", layout, bms, {}, i)
        assert set(got) == {"NAMEI"} and len(got["NAMEI"]) <= 4


def test_a_rule_beside_bms_replaces_the_generated_value_and_none_never_types(corpus):
    bms = ei.bms_input_fields(corpus, "TESTMAP")
    spec = {"@bms": {}, "ACCTI": {"values": ["00000000011"]}, "NAMEI": None, "ONEI": "Z"}
    for i in range(6):
        got = ei._bms_receive(random.Random(i), "s", spec, _layout(), bms, {}, i)
        assert got["ACCTI"] == "00000000011" and got["ONEI"] == "Z" and "NAMEI" not in got
        assert {"CODEI", "TXTI", "STATEI"} <= set(got)
    with pytest.raises(ValueError, match="no input field"):
        ei._bms_receive(random.Random(0), "s", {"@bms": {}, "NOPEI": "1"}, _layout(), bms, {}, 0)


def test_the_same_seed_types_the_same_input(corpus):
    bms = ei.bms_input_fields(corpus, "TESTMAP")
    a, b, c = (ei._bms_receive(random.Random(s), "s", "@bms", _layout(), bms, {}, 4) for s in (3, 3, 4))
    assert a == b and a != c


def test_prepare_cics_case_expands_bms_for_every_scenario(corpus, monkeypatch):
    import equivalence_cics as cx

    monkeypatch.setattr(cx, "screen_fields", lambda c, case, m, side: list(_layout().values()))
    case = {"scenario_generate": {"seed": 5, "count": 8, "receive": {"TESTMAP": {"@bms": {"empty": 0.2}}}}}
    out = ei.prepare_cics_case(case, corpus, [])["scenarios"]
    assert len(out) == 8
    typed = [s["receive"]["TESTMAP"] for s in out]
    assert all(set(t) <= set(TYPABLE) and t for t in typed) and len({tuple(sorted(t.items())) for t in typed}) > 4
    assert out == ei.prepare_cics_case(case, corpus, [])["scenarios"]
