"""#8196: a case's `entity` must be the generated entity of its dataset's file.

The estate names a record's entity bare for the first file that claims it, so a case added to the corpus later (cics-crucible
v0.13.0's hc-syncpoint-rollback SFILE took `WsRec`) renames another file's (UFILE became `UfileWsRec`): the Java leg then
seeded SFILE's table and the port read an empty one (cruc-hc-file-unlock, NOT PROVEN on every PR)."""

import json
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
import equivalence_cics as ec  # noqa: E402


def _estate(tmp_path, tables):
    d = tmp_path / "entity" / "vsam"
    d.mkdir(parents=True)
    for cls, table in tables.items():
        (d / f"{cls}.java").write_text(
            f'@Entity\n@Table(name = "{table}")\npublic class {cls} {{}}\n', encoding="utf-8"
        )
    return tmp_path


TABLES = {"WsRec": "vsam_sfile", "UfileWsRec": "vsam_ufile"}


def test_the_entity_of_the_datasets_table_passes(tmp_path):
    ec.check_entity_table(_estate(tmp_path, TABLES), "CRUCIBLE.HC.UFILE", "UfileWsRec")


def test_a_stale_bare_name_is_refused_naming_the_right_entity(tmp_path):
    with pytest.raises(ec.Unsupported) as e:
        ec.check_entity_table(_estate(tmp_path, TABLES), "CRUCIBLE.HC.UFILE", "WsRec")
    assert 'use "UfileWsRec"' in str(e.value)


def test_an_entity_with_no_generated_owner_of_the_table_is_left_alone(tmp_path):
    ec.check_entity_table(_estate(tmp_path, {"WsRec": "vsam_sfile"}), "CRUCIBLE.HC.UFILE", "WsRec")
    ec.check_entity_table(_estate(tmp_path / "b", {}), "CRUCIBLE.HC.UFILE", "Missing")


def test_the_crucible_case_names_the_prefixed_entity():
    case = json.loads((TESTS / "equivalence" / "cruc-hc-file-unlock" / "case.json").read_text(encoding="utf-8"))
    assert case["datasets"]["CRUCIBLE.HC.UFILE"]["entity"] == "UfileWsRec"
