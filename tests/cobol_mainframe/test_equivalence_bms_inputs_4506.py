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
    assert ei.bms_input_fields(corpus, "OTHER") == {
        "OTHERFI": {"length": 3, "numeric": False, "picture": None, "mdt": False}
    }


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
    # left alone: not transmitted (nothing typed), except an FSET field, whose MDT is on: transmitted with no data
    assert ei._bms_receive(random.Random(1), "s", {"@bms": {"empty": 1.0}}, _layout(), bms, {}, 1) == {
        "ACCTI": "",
        "STATEI": "",
    }


def test_the_mdt_flag_is_fset_and_only_fset(corpus):
    got = ei.bms_input_fields(corpus, "TESTMAP")
    assert {k for k, v in got.items() if v["mdt"]} == {"ACCTI", "STATEI"}  # ATTRB=(..FSET..) and ATTRB=FSET


def test_an_unmodified_field_reaches_the_program_as_nulls_with_length_zero_and_an_fset_one_with_length_zero(corpus):
    """RECEIVE MAP's input area: X'00' everywhere (data, length, flag) but for the fields transmitted."""
    import equivalence_cics as cx

    fields = [{"name": n, "base": n, "offset": o, "bytes": b, "pic": p, "usage": "COMP" if n.endswith("L") else "DISPLAY"}
              for n, o, b, p in (("NAMEL", 0, 2, "S9(4)"), ("NAMEF", 2, 1, "X"), ("NAMEI", 3, 4, "X(4)"),
                                 ("STATEL", 7, 2, "S9(4)"), ("STATEF", 9, 1, "X"), ("STATEI", 10, 2, "X(2)"))]  # fmt: skip
    area = cx.map_input(fields, {}, "cp037")
    assert area == bytes(12)  # nothing typed: every byte X'00', every length 0, no flag
    area = cx.map_input(fields, {"STATEI": ""}, "cp037")
    # an FSET field sent empty: length 0, blank data (ASSUMED, X54); the untouched NAME field stays X'00'
    assert area[:10] == bytes(10) and area[10:12] == "  ".encode("cp037")


def test_every_fset_typable_field_of_every_burned_map_is_transmitted_when_left_alone():
    """The whole class, on the burned estates' BMS: a field with FSET is never omitted, any other is."""
    import os

    root = os.environ.get("GITGALAXY_MAINFRAME_CORPORA")
    if not root or not Path(root).is_dir():
        pytest.skip("no mainframe corpora")
    from gitgalaxy.core.bms_screen_fields import bms_screen_fields
    from gitgalaxy.core.source_text import read_source

    checked = 0
    for p in sorted(Path(root).rglob("*.bms")):
        if ".git" in p.parts or "_scans" in p.parts:
            continue
        maps = {r["name"] for r in bms_screen_fields(read_source(p).text) if r["kind"] == "map" and r["name"]}
        for m in sorted(maps):
            try:
                ei.bms_input_fields.cache_clear()
                bms = ei.bms_input_fields(p.parent, m)
            except ValueError:
                continue
            layout = {k: {"name": k, "bytes": v["length"]} for k, v in bms.items()}
            got = ei._bms_receive(random.Random(1), "s", {"@bms": {"empty": 1.0}}, layout, bms, {}, 0)
            assert got == {k: "" for k, v in bms.items() if v["mdt"]}, (p.name, m)
            checked += 1
    assert checked > 10


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


def test_a_field_rule_can_leave_its_field_alone_fset_sends_it_empty_and_any_other_omits_it(corpus):
    """BNK1DAC tests `ACCNOI = LOW-VALUES OR ACCNOL = 0` on a non-FSET field: an `empty` share on a field rule leaves it
    unmodified (not in the input: X'00', length 0), an FSET one is transmitted with length 0."""
    bms = ei.bms_input_fields(corpus, "TESTMAP")
    for field, want in (("NAMEI", None), ("ACCTI", ""), ("STATEI", "")):
        always = {"@bms": {}, field: {"values": ["X"], "empty": 1.0}}
        never = {"@bms": {}, field: {"values": ["X"], "empty": 0.0}}
        for i in range(6):
            got = ei._bms_receive(random.Random(i), "s", always, _layout(), bms, {}, i)
            assert got.get(field, "absent") == (want if want is not None else "absent")
            assert ei._bms_receive(random.Random(i), "s", never, _layout(), bms, {}, i)[field] == "X"
    half = {"@bms": {}, "NAMEI": {"values": ["X"], "empty": 0.5}}
    seen = {"NAMEI" in ei._bms_receive(random.Random(i), "s", half, _layout(), bms, {}, i) for i in range(40)}
    assert seen == {True, False}


def test_a_rule_without_empty_draws_nothing_extra_so_other_cases_keep_their_input(corpus):
    bms = ei.bms_input_fields(corpus, "TESTMAP")
    plain = {"@bms": {}, "NAMEI": {"values": ["X"]}}
    zero = {"@bms": {}, "NAMEI": {"values": ["X"], "empty": 0}}
    for i in range(6):
        a = ei._bms_receive(random.Random(i), "s", plain, _layout(), bms, {}, i)
        assert a == ei._bms_receive(random.Random(i), "s", zero, _layout(), bms, {}, i)


def test_the_generated_bnk1dac_case_leaves_its_non_fset_account_field_alone_in_some_scenarios():
    """BNK1DAC.cbl `IF ACCNOI = LOW-VALUES OR ACCNOL = 0`; ACCNO is not FSET, so unmodified means absent (X'00')."""
    import json
    import os

    root = os.environ.get("GITGALAXY_MAINFRAME_CORPORA")
    path = Path(__file__).resolve().parents[1] / "equivalence" / "cbsa-bnk1dac-generated" / "case.json"
    case = json.loads(path.read_text("utf-8"))
    assert case["scenario_generate"]["receive"]["BNK1DA"]["ACCNOI"]["empty"] > 0
    if not root or not (Path(root) / case["corpus"]).is_dir():
        pytest.skip("no CBSA corpus")
    ei.bms_input_fields.cache_clear()
    case = {**case, "datasets": {}, "scenario_generate": {**case["scenario_generate"], "commarea": None}}
    out = ei.prepare_cics_case(case, Path(root) / case["corpus"], [])["scenarios"]
    prefix = case["scenario_generate"]["prefix"] + "-"
    maps = [s["receive"].get("BNK1DA", {}) for s in out if s["name"].startswith(prefix)]
    assert any("ACCNOI" not in m for m in maps) and any(m.get("ACCNOI") for m in maps)
    assert not any(m.get("ACCNOI") == "" for m in maps)  # never transmitted empty: it has no FSET


def test_the_generated_bnk1ccs_case_sends_its_fset_fields_empty_in_some_scenarios():
    """BNK1CCS.cbl tests `CUSTTITL < 1`, `CHRISTNL < 1`, `CUSTSNL < 1`, `CUSTAD1L < 1`; all four are FSET, so unmodified means
    transmitted with length 0 (MDT on), never absent."""
    import json
    import os

    fields = ("CUSTTITI", "CHRISTNI", "CUSTSNI", "CUSTAD1I")
    root = os.environ.get("GITGALAXY_MAINFRAME_CORPORA")
    path = Path(__file__).resolve().parents[1] / "equivalence" / "cbsa-bnk1ccs-generated" / "case.json"
    case = json.loads(path.read_text("utf-8"))
    rules = case["scenario_generate"]["receive"]["BNK1CC"]
    assert all(rules[f]["empty"] > 0 for f in fields)
    if not root or not (Path(root) / case["corpus"]).is_dir():
        pytest.skip("no CBSA corpus")
    ei.bms_input_fields.cache_clear()
    case = {**case, "datasets": {}, "scenario_generate": {**case["scenario_generate"], "commarea": None}}
    out = ei.prepare_cics_case(case, Path(root) / case["corpus"], [])["scenarios"]
    prefix = case["scenario_generate"]["prefix"] + "-"
    maps = [s["receive"].get("BNK1CC", {}) for s in out if s["name"].startswith(prefix)]
    for f in fields:
        assert any(m.get(f) == "" for m in maps), f
        assert any(m.get(f) for m in maps), f
        assert not any(f not in m for m in maps), f  # FSET: never absent


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


@pytest.mark.parametrize(("aid", "want"), [("DFHPF3", ["DFHPF3"] * 5), (["DFHENTER", "DFHPF3", "DFHPF9"], ["DFHENTER", "DFHPF3", "DFHPF9", "DFHENTER", "DFHPF3"]), (None, ["DFHENTER"] * 5)])  # fmt: skip
def test_aid_is_one_key_or_a_list_in_turn(corpus, aid, want):
    gen = {"seed": 1, "count": 5} | ({"aid": aid} if aid else {})
    assert [s["aid"] for s in ei.prepare_cics_case({"scenario_generate": gen}, corpus, [])["scenarios"]] == want


def test_the_generated_tranview_case_turns_through_keys_and_types_its_one_field():
    """The committed COTRN01 case (#4506): the BMS source has one unprotected field (TRNIDIN), and the aid list reaches
    PF3 / PF4 / PF5 and a key the screen does not assign, beside a run with no COMMAREA (and, since #4049, the
    hand-written scenarios its mutation survivors point at, each with its reason)."""
    import json

    case = json.loads(
        (Path(__file__).resolve().parents[1] / "equivalence" / "carddemo-tranview-generated" / "case.json").read_text(
            "utf-8"
        )
    )
    gen = case["scenario_generate"]
    assert set(gen["aid"]) == {"DFHENTER", "DFHPF3", "DFHPF4", "DFHPF5", "DFHPF9"}
    assert gen["receive"] == {"COTRN1A": {"@bms": {"bad": 0.1, "empty": 0.3}}}
    first, *rest = case["scenarios"]
    assert first["name"] == "no-commarea" and first["commarea"] is None
    assert rest and all("#4049" in s["why"] or "#4506" in s["why"] for s in rest)


def test_the_generated_tranview_screen_sends_its_fset_id_field_empty_in_some_scenarios():
    """COTRN01C tests `TRNIDINI = SPACES OR LOW-VALUES`; TRNIDIN is FSET, so its generated empty input is a transmitted
    empty field (length 0), not an omitted one -- and the case still has scenarios that type it."""
    import json
    import os

    root = os.environ.get("GITGALAXY_MAINFRAME_CORPORA")
    if not root or not (Path(root) / "aws-mainframe-modernization-carddemo").is_dir():
        pytest.skip("no CardDemo corpus")
    case = json.loads(
        (Path(__file__).resolve().parents[1] / "equivalence" / "carddemo-tranview-generated" / "case.json").read_text(
            "utf-8"
        )
    )
    ei.bms_input_fields.cache_clear()
    case = {**case, "datasets": {}, "scenario_generate": {**case["scenario_generate"], "commarea": None}}
    out = ei.prepare_cics_case(case, Path(root) / case["corpus"], [])["scenarios"]
    prefix = case["scenario_generate"]["prefix"] + "-"
    typed = [s["receive"]["COTRN1A"].get("TRNIDINI") for s in out if s["name"].startswith(prefix)]
    assert "" in typed and any(typed)
    assert None not in typed


@pytest.mark.parametrize(
    ("case_dir", "map_name", "typed_field"),
    [
        ("carddemo-cardview-generated", "CCRDSLA", "CARDSIDI"),
        ("carddemo-userdel-generated", "COUSR3A", "USRIDINI"),
        ("carddemo-useradd-generated", "COUSR1A", "USERIDI"),
        ("carddemo-userupd-generated", "COUSR2A", "USRIDINI"),
    ],
)
def test_the_generated_screen_cases_type_their_map_from_the_bms_source(case_dir, map_name, typed_field):
    """The hand-written receive of cardview, userdel, useradd and userupd moved to `@bms` (#4506): the map input is generated from the
    BMS source, the one field a case names beside `@bms` is drawn from its file (with misses), the aid list turns
    through more than ENTER, and each hand-written scenario left carries its reason."""
    import json

    case = json.loads((Path(__file__).resolve().parents[1] / "equivalence" / case_dir / "case.json").read_text("utf-8"))
    gen = case["scenario_generate"]
    rule = gen["receive"][map_name]
    assert rule["@bms"] == {"bad": 0.1, "empty": 0.3}
    assert rule[typed_field]["from"].rsplit(".", 1)[0] in case["datasets"]
    assert rule[typed_field]["miss"] > 0
    assert len(set(gen["aid"])) > 2 and case["port_from"] == case_dir.removesuffix("-generated")
    assert case["scenarios"] and all(s.get("why") for s in case["scenarios"])


@pytest.mark.parametrize(
    ("case_dir", "map_name", "typed_field", "opts"),
    [
        ("carddemo-adminmenu-generated", "COADM1A", None, {"bad": 0, "empty": 0.3}),
        ("carddemo-menu-generated", "COMEN1A", "OPTIONI", {"bad": 0, "empty": 0}),
    ],
)
def test_the_generated_menu_cases_type_their_option_from_the_bms_source(case_dir, map_name, typed_field, opts):
    """The menus have no file to draw from (#4506): the map input is generated from the BMS source, `bad` is 0 (a NUM
    field cannot be keyed with letters, #5116), the menu pins the option to 1-12 (0, blank and 13+ are X8 bounds
    refusals, left to carddemo-menu's bounds_refused scenarios), and each hand-written scenario left carries its reason."""
    import json

    case = json.loads((Path(__file__).resolve().parents[1] / "equivalence" / case_dir / "case.json").read_text("utf-8"))
    gen = case["scenario_generate"]
    rule = gen["receive"][map_name]
    assert rule["@bms"] == opts and not case["datasets"]
    if typed_field:
        assert {int(v) for v in rule[typed_field]["values"]} == set(range(1, 13))
    assert len(set(gen["aid"])) > 2 and case["port_from"] == case_dir.removesuffix("-generated")
    assert case["scenarios"] and all(s.get("why") for s in case["scenarios"])


@pytest.mark.parametrize(
    ("case_dir", "map_name", "typed_fields"),
    [
        ("carddemo-signon-generated", "COSGN0A", {"USERIDI", "PASSWDI"}),
        ("carddemo-billpay-generated", "COBIL0A", {"ACTIDINI", "CONFIRMI"}),
        ("carddemo-report-generated", "CORPT0A", {"MONTHLYI", "SDTMMI", "CONFIRMI"}),
    ],
)
def test_the_generated_signon_billpay_and_report_cases_type_their_map_from_the_bms_source(
    case_dir, map_name, typed_fields
):
    """The hand-written receive of signon, billpay and report moved to `@bms` (#4506): NUM fields are never keyed with
    letters (`bad` 0, #5116), the fields a case pins beside `@bms` keep their own rule (signon's empty share is on the
    field rule, which replaces `@bms`'s), the aid list turns through more than ENTER, the files the program reads are
    generated (or none), and each hand-written scenario left carries its reason."""
    import json

    case = json.loads((Path(__file__).resolve().parents[1] / "equivalence" / case_dir / "case.json").read_text("utf-8"))
    gen = case["scenario_generate"]
    rule = gen["receive"][map_name]
    assert rule["@bms"]["bad"] == 0 and typed_fields <= set(rule)
    assert all(d["input"] == "@generate" for d in case["datasets"].values())
    assert len(set(gen["aid"])) > 2 and case["port_from"] == case_dir.removesuffix("-generated")
    assert case["scenarios"] and all(s.get("why") for s in case["scenarios"])
