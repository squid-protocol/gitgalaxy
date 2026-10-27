"""#6072: the two case-data forms CardDemo COPAUS0C needed -- a COMMAREA field's raw bytes (letters in a PIC 9 field, for
IS NUMERIC false) and a scenario's own IMS seed (a pending-authorization detail with a response code other than '00') --
and the two scenarios that use them. Pure Python: no Java, no Docker."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import equivalence_cics as ec  # noqa: E402
import equivalence_common as common  # noqa: E402
import equivalence_ims as ims  # noqa: E402

CASE = ROOT / "tests" / "equivalence" / "carddemo-copaus0c" / "case.json"
APP = "app/app-authorization-ims-db2-mq"
ENC = "latin-1"

FIELDS = [
    {"name": "ID", "offset": 0, "bytes": 4, "pic": "9(4)", "usage": "DISPLAY"},
    {"name": "NAME", "offset": 4, "bytes": 4, "pic": "X(4)", "usage": "DISPLAY"},
    {"name": "AMT", "offset": 8, "bytes": 3, "pic": "S9(5)", "usage": "COMP-3"},
]


def _case() -> dict:
    return json.loads(CASE.read_text(encoding="utf-8"))


def _corpus() -> Path | None:
    corpora = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", ROOT / ".mainframe_corpora"))
    corpus = corpora / "aws-mainframe-modernization-carddemo"
    return corpus if (corpus / APP / "cbl/COPAUS0C.cbl").is_file() else None


needs_corpus = pytest.mark.skipif(_corpus() is None, reason="the CardDemo corpus is not checked out")


# ---- (a) raw bytes in a COMMAREA field -------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("field", "raw", "at"),
    [("ID", "41424344", 0), ("NAME", "00010203", 4), ("AMT", "ABCDEF", 8)],  # a digit field, a text field, a COMP-3
)
def test_a_raw_hex_value_is_the_fields_own_bytes(field, raw, at):
    rec = ec.commarea_record(FIELDS, {field: {"hex": raw}}, ENC)
    assert rec[at : at + len(raw) // 2] == bytes.fromhex(raw)
    assert len(rec) == 11


def test_a_raw_hex_value_leaves_every_other_field_initialized_and_a_plain_value_alone():
    rec = ec.commarea_record(FIELDS, {"ID": {"hex": "41424344"}, "NAME": "AB"}, ENC)
    assert rec[:8] == b"ABCDAB  "
    assert rec[8:] == ec.commarea_record(FIELDS, {}, ENC)[8:]  # AMT: INITIALIZE's zero, packed
    assert ec.commarea_record(FIELDS, {"ID": 7}, ENC)[:4] == b"0007"


@pytest.mark.parametrize("raw", ["", "414243", "4142434445"])
def test_a_raw_hex_value_of_the_wrong_width_is_refused(raw):
    with pytest.raises(ValueError, match="ID: hex is"):
        ec.commarea_record(FIELDS, {"ID": {"hex": raw}}, ENC)


def test_the_raw_names_are_those_stated_as_hex_only():
    values = {"ID": {"hex": "41424344"}, "NAME": "AB", "AMT": 5, "X": {"hex": "00", "other": 1}}
    assert ec.raw_commarea_names(values) == {"ID"}
    assert ec.raw_commarea_bytes(values)["ID"] == b"ABCD"
    assert ec.raw_commarea_bytes(values)["X"] == {"hex": "00", "other": 1}


# ---- (b) a scenario's own IMS seed -----------------------------------------------------------------------------------
def _seed(sc: dict | None = None) -> tuple[bytes, dict]:
    corpus, case = _corpus(), _case()
    dbds, _ = ims.definitions(case, corpus, cics=True)
    return ims.seed(case, corpus, "DBPAUTP0", dbds["DBPAUTP0"], sc), dbds["DBPAUTP0"]


def _insert(**over) -> dict:
    ins = {"after": 8, "segment": "PAUTDTL1", "fields": {"PA-AUTH-TIME-9C": 835153124, "PA-AUTH-RESP-CODE": "05"}}
    return {"name": "s", "ims_seed": {"DBPAUTP0": {"insert": [{**ins, **over}]}}}


def _segments(seed: bytes) -> list[tuple[str, bytes]]:
    return ims.split(seed, {"PAUTSUM0": 100, "PAUTDTL1": 200})


@needs_corpus
def test_an_inserted_detail_follows_its_record_with_the_fields_stated():
    plain, _ = _seed()
    seeded, _ = _seed(_insert())
    assert plain == _seed(None)[0]
    assert len(seeded) == len(plain) + 8 + 200
    before, after = _segments(plain), _segments(seeded)
    assert after[:9] == before[:9] and after[10:] == before[9:]  # nothing else moved
    name, data = after[9]
    assert name == "PAUTDTL1"
    lay = {f["name"]: f for f in ims._layout(_case(), _corpus(), "PAUTDTL1")}
    resp = lay["PA-AUTH-RESP-CODE"]
    assert data[resp["offset"] : resp["offset"] + resp["bytes"]] == b"05"
    assert before[8][1][resp["offset"] : resp["offset"] + resp["bytes"]] == b"00"  # the record it copied
    assert data[:8].hex() == "76700c835153124c"  # the key: the neighbour's, one tick on (a packed number)


@needs_corpus
def test_the_other_scenarios_keep_the_case_seed():
    case = _case()
    assert _seed({"name": "t", "receive": {}})[0] == _seed()[0]
    s = {sc["name"]: sc for sc in case["scenarios"]}
    assert s["enter-account-declined-detail"]["ims_seed"] and "ims_seed" not in s["enter-account-single-detail"]


@needs_corpus
def test_each_scenario_with_an_ims_seed_stages_its_own_java_directory(tmp_path):
    case, corpus = _case(), _corpus()
    seeded = {"name": "declined", "ims_seed": _insert()["ims_seed"]}
    plain = {"name": "plain"}
    a = ec._java_dli(case, corpus, tmp_path, seeded)
    b = ec._java_dli(case, corpus, tmp_path, plain)
    assert a["dli"]["dir"] == "dli-declined" and b["dli"]["dir"] == "dli"
    assert (tmp_path / "dli-declined" / "seed.DBPAUTP0").read_bytes() != (
        tmp_path / "dli" / "seed.DBPAUTP0"
    ).read_bytes()
    assert (tmp_path / "dli" / "seed.DBPAUTP0").read_bytes() == _seed()[0]


@needs_corpus
@pytest.mark.parametrize(
    ("over", "message"),
    [
        ({"fields": {"NO-SUCH-FIELD": "x"}}, "has no field NO-SUCH-FIELD"),
        ({"segment": "NOSEG"}, "segment NOSEG is not in DBD"),
        ({"after": 9999}, "no unload record 9999"),
        ({"after": 223}, "no unload record 223"),  # the skipped record
        ({"like": 7}, "is not a PAUTDTL1 segment"),  # a summary
        ({"fields": {"PA-AUTH-TIME-9C": 835153122}}, "would not stay unique and ascending"),  # not above its neighbour
        ({"fields": {"PA-AUTH-TIME-9C": 835153123}}, "would not stay unique and ascending"),  # a duplicate key
    ],
)
def test_a_seed_the_model_cannot_keep_in_order_is_refused_by_name(over, message):
    with pytest.raises(ims.Unsupported, match=message):
        _seed(_insert(**over))


@needs_corpus
def test_a_seed_before_the_next_detail_of_its_own_type_must_stay_below_it():
    with pytest.raises(ims.Unsupported, match="ascending"):
        _seed(_insert(after=1, fields={"PA-AUTH-TIME-9C": 999999999, "PA-AUTH-DATE-9C": 99999}))


@needs_corpus
def test_ims_seed_on_a_database_with_no_unload_to_add_to_is_refused():
    case, corpus = _case(), _corpus()
    dbds, _ = ims.definitions(case, corpus, cics=True)
    case["ims"]["seed"]["DBPAUTP0"] = {"segments": [{"segment": "PAUTSUM0", "hex": "00" * 100}]}
    with pytest.raises(ims.Unsupported, match="nothing to insert into"):
        ims.seed(case, corpus, "DBPAUTP0", dbds["DBPAUTP0"], _insert())
    del case["ims"]["seed"]["DBPAUTP0"]
    with pytest.raises(ims.Unsupported, match="has no seed to add to"):
        ims.seed(case, corpus, "DBPAUTP0", dbds["DBPAUTP0"], _insert())


# ---- the case ---------------------------------------------------------------------------------------------------------
def test_the_case_states_the_declined_detail_scenario_and_not_the_one_the_port_cannot_hold():
    by = {s["name"]: s for s in _case()["scenarios"]}
    declined = by["enter-account-declined-detail"]
    (ins,) = declined["ims_seed"]["DBPAUTP0"]["insert"]
    assert ins["fields"]["PA-AUTH-RESP-CODE"] != "00"
    assert declined["receive"]["COPAU0A"]["ACCTIDI"] == "00000000005" and declined["why"]
    # P119: the port's DTO decodes a zoned field to a long, so letters in CDEMO-ACCT-ID differ (COBOL bytes vs a number)
    assert "entered-with-account-id-letters" not in by
