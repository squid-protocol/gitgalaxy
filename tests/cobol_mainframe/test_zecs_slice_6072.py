"""zECS small-estate slice (#6072): the scenarios added to zecs-zecs000, zecs-zecs003 and zecs-ecs001.

JSON-only checks: each added scenario exists and sets up what its name says, and the ECS001 infeasible
entries name a family and a reason.
"""

import json
from pathlib import Path

EQUIV = Path(__file__).resolve().parents[1] / "equivalence"


def _case(name):
    return json.loads((EQUIV / name / "case.json").read_text(encoding="utf-8"))


def _scenarios(name):
    return {s["name"]: s for s in _case(name)["scenarios"]}


def test_zecs003_runs_under_trunc_bin_like_zecs000():
    assert _case("zecs-zecs003")["compiler_options"] == ["TRUNC(BIN)"]
    assert _case("zecs-zecs003")["compiler_options_why"]
    assert _case("zecs-zecs000")["compiler_options"] == ["TRUNC(BIN)"]


def test_zecs003_peer_url_scenarios_set_the_template():
    sc = _scenarios("zecs-zecs003")
    assert "://" not in sc["sdr-resources-url-unparsable"]["doctemplates"]["ZC01DC"]
    short = sc["sdr-resources-template-too-short"]["doctemplates"]["ZC01DC"]
    assert len(short) == 10


def test_zecs000_control_record_scenarios_seed_the_control_file():
    sc = _scenarios("zecs-zecs000")
    first = sc["control-record-first-write"]["datasets"]["ZECS.ZCEXPIRE.TEST"]["input"]
    assert first == "@case/zcempty.bin"
    elapsed = sc["interval-elapsed"]["datasets"]["ZECS.ZCEXPIRE.TEST"]["input"]
    seed = EQUIV / "zecs-zecs000" / elapsed.removeprefix("@case/")
    assert seed.stat().st_size == 70


def test_ecs001_terminal_input_exceeds_the_receive_area():
    typed = _scenarios("zecs-ecs001")["terminal-input-too-long"]["terminal"]
    assert len(typed) > 24 * 80


def test_ecs001_infeasible_entries_name_a_family_and_a_reason():
    entries = json.loads((EQUIV / "infeasible_outcomes" / "zecs-ecs001.json").read_text(encoding="utf-8"))["entries"]
    assert {e["line"] for e in entries} == {197, 353}
    for e in entries:
        assert e["family"] in "GCR"
        assert e["reason"]


def test_zecs001_clear_star_xctls_with_the_zecs003_area():
    case = _case("zecs-zecs001")
    sc = _scenarios("zecs-zecs001")["delete-clear-star"]
    assert sc["http_request"]["query"] == "clear=*"
    assert case["commarea"]["segments"][0]["record"] == "ZECS003-COMM-AREA"
