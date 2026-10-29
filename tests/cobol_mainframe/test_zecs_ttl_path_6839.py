"""zECS ZECS001 rows J and K (#6839): the empty-path request and the non-digit TTL query.

JSON-only checks over the case, the coverage ledger and register C11.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CASE = ROOT / "tests" / "equivalence" / "zecs-zecs001"


def _scenarios():
    return {s["name"]: s for s in json.loads((CASE / "case.json").read_text(encoding="utf-8"))["scenarios"]}


def test_a_request_with_no_path_is_a_scenario_with_an_empty_path():
    req = _scenarios()["get-empty-path"]["http_request"]
    assert req["path"] == ""
    assert req["method"] == "GET"


def test_the_empty_path_arm_is_covered_and_the_non_digit_ttl_arm_is_a_named_gap():
    ledger = json.loads((ROOT / "tests/equivalence/det_sweep_coverage/zecs-zecs001.json").read_text(encoding="utf-8"))
    uncovered = ledger["uncovered"]["branches"]
    assert "492:false" not in uncovered
    assert "704:false" in uncovered


def test_every_ttl_scenario_sets_a_query_and_the_non_digit_one_cites_c11():
    ttl = {n: s for n, s in _scenarios().items() if n.startswith("post-ttl-")}
    assert ttl
    for name, s in ttl.items():
        assert s["http_request"]["query"].startswith("ttl="), name
    assert "C11" in ttl["post-ttl-nonnumeric"]["why"]
    digits = {n: s["http_request"]["query"][4:] for n, s in ttl.items() if n != "post-ttl-nonnumeric"}
    assert all(v.isdigit() for v in digits.values()), digits


def test_register_c11_names_the_zecs001_ttl_gap():
    text = (ROOT / "docs/language_status/register/C11.md").read_text(encoding="utf-8")
    assert "704:false" in text
    assert "post-ttl-nonnumeric" in text


def test_row_f_text_and_xml_bodies_take_the_srvconvert_pass_and_540_true_is_covered():
    sc = _scenarios()
    assert sc["post-text-plain"]["http_request"]["mediatype"].startswith("text/")
    assert sc["post-text-plain"]["http_request"]["method"] == "POST"
    assert sc["put-application-xml"]["http_request"]["mediatype"] == "application/xml"
    assert sc["put-application-xml"]["http_request"]["method"] == "PUT"
    ledger = json.loads((ROOT / "tests/equivalence/det_sweep_coverage/zecs-zecs001.json").read_text(encoding="utf-8"))
    assert "540:true" not in ledger["uncovered"]["branches"]
