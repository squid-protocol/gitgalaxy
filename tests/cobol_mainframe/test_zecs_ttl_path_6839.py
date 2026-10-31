"""zECS ZECS001 rows J and K (#6839): the empty-path request and the non-digit TTL query.

JSON-only checks over the case, the coverage ledger and register C11.
"""

import json
import sys
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
    assert "family U" in text and "2026-10-31" in text
    assert "post-ttl-nonnumeric" in text


def test_row_f_text_and_xml_bodies_take_the_srvconvert_pass_and_540_true_is_covered():
    sc = _scenarios()
    assert sc["post-text-plain"]["http_request"]["mediatype"].startswith("text/")
    assert sc["post-text-plain"]["http_request"]["method"] == "POST"
    assert sc["put-application-xml"]["http_request"]["mediatype"] == "application/xml"
    assert sc["put-application-xml"]["http_request"]["method"] == "PUT"
    ledger = json.loads((ROOT / "tests/equivalence/det_sweep_coverage/zecs-zecs001.json").read_text(encoding="utf-8"))
    assert "540:true" not in ledger["uncovered"]["branches"]


def test_704_false_is_stated_undefined_by_ibm_and_netted_but_named():
    sys.path.insert(0, str(ROOT / "tests" / "tools"))
    import infeasible_outcomes as io  # noqa: E402

    ledger = io.load()
    entries = ledger["zecs-zecs001"]
    u = [e for e in entries if io.is_undefined(e)]
    assert [(e["unit"], e["line"], e["kind"], e["outcome"]) for e in u] == [("1310-TTL", 704, "IF", "false")]
    assert all(t in u[0]["reason"] for t in ("ttl=abc", "C11", "2026-10-31", "not infeasible"))
    assert io.problems_in({"zecs-zecs001": entries}) == []
    # the class: a family-U entry exists only where a ruling names it (2026-10-29 bounds, 2026-10-31 non-digit data)
    members = {(c, e["line"], e["outcome"]) for c, es in ledger.items() for e in es if io.is_undefined(e)}
    assert members == {
        ("cbsa-bnk1cac", 611, "true"),
        ("cbsa-bnk1cac", 637, "true"),
        ("cbsa-bnk1cac", 637, "false"),
        ("cbsa-bnk1cac", 717, "true"),
        ("zecs-zecs001", 704, "false"),
    }
    # taken out of the bar while uncovered; a proof that reaches it refutes it
    cov = (10, 10, 20, 30)
    got, taken, reached = io.adjust("zecs-zecs001", cov, ["704:false", "718:false"], ledger)
    assert any(k.endswith(":704:false") for k in taken) and reached == []
    assert io.split_undefined(taken, entries)[1] == [k for k in taken if k.endswith(":704:false")]
    assert any(k.endswith(":704:false") for k in io.adjust("zecs-zecs001", cov, ["718:false"], ledger)[2])
