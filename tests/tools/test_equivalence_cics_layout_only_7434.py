"""#7434 (#6271): a case whose COMMAREA record is a WORKING-STORAGE item (CAXA's XCTL area) is only a LAYOUT: the forge
makes it an entity, never a contract DTO, so the harness names no COMMAREA class and compares the area as bytes."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import equivalence_cics as ec

REPO = Path(__file__).resolve().parents[2]
CASE = REPO / "tests/equivalence/cruc-ca-xctl-versions-front/case.json"
SEG = {"segments": [{"copybook": "x.cbl", "record": "WS-BLOCK"}]}


def _service(tmp_path: Path, takes: str = "") -> Path:
    svc = tmp_path / "CaxaService.java"
    svc.write_text(f"class CaxaService {{ void handleLink({takes}) {{}} }}\n", encoding="utf-8")
    return svc


def _entity(tmp_path: Path, name: str = "WsBlock") -> None:
    (tmp_path / "entity").mkdir()
    (tmp_path / "entity" / f"{name}.java").write_text("class X {}\n", encoding="utf-8")


@pytest.mark.parametrize("with_entity", [False, True])
def test_a_layout_only_record_names_no_commarea_class_even_with_a_same_named_entity(tmp_path, with_entity):
    if with_entity:
        _entity(tmp_path, "CaxaWsBlock")
    case = {"program": "CAXA", "commarea": {**SEG, "layout_only": True}}
    assert ec.commarea_class(case, tmp_path, _service(tmp_path)) is None


def test_a_record_without_the_flag_is_refused_when_only_the_declarers_entity_exists(tmp_path):
    _entity(tmp_path, "CaxaWsBlock")  # the forge names the entity for its declarer: no class WsBlock
    with pytest.raises(ec.Unsupported, match="no generated COMMAREA class WsBlock"):
        ec.commarea_class({"program": "CAXA", "commarea": SEG}, tmp_path, _service(tmp_path))


def test_a_service_that_takes_a_dto_is_unchanged_without_the_flag(tmp_path):
    svc = _service(tmp_path, "CaxbCommarea request")
    assert ec.commarea_class({"program": "CAXB", "commarea": SEG}, tmp_path, svc) == "CaxbCommarea"


@pytest.mark.parametrize("commarea", [None, SEG, {**SEG, "layout_only": False}])
def test_only_the_flag_makes_a_layout(commarea):
    assert not ec.layout_only({"commarea": commarea})
    assert not ec.layout_only({})


def test_the_front_case_states_the_layout_and_no_scenario_states_a_commarea():
    case = json.loads(CASE.read_text(encoding="utf-8"))
    assert ec.layout_only(case)
    assert case["scenarios"] and all(sc["commarea"] is None for sc in case["scenarios"])
