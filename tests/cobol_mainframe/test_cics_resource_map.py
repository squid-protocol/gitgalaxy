"""
#5120: CICS macro tables and the CSD merged into one resource map.

Two hand-written estates (tests/fixtures/cics_macro_estate): `tables_only`
(DFHFCT / DFHPCT / DFHPPT / DFHDCT / DFHTST, no CSD) and `tables_and_csd` (three of
the tables plus REGION.csd, built so some resources agree, some disagree and some
sit in one source only). A REAL scan, so the hlasm dialect's `csd_resources` key is
proven to reach csd_resource_data through the config pipeline.
"""

import shutil
from pathlib import Path

import pytest

from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "cics_macro_estate"


def _ir(tmp_path_factory, estate):
    base = tmp_path_factory.mktemp(f"macro_{estate}")
    repo = base / "region"
    shutil.copytree(FIXTURES / estate, repo)
    return load_galaxy_ir(scan_to_db(repo, base / "scan"))


@pytest.fixture(scope="module")
def tables_only(tmp_path_factory):
    return _ir(tmp_path_factory, "tables_only")


@pytest.fixture(scope="module")
def both(tmp_path_factory):
    return _ir(tmp_path_factory, "tables_and_csd")


def _entry(ir, rtype, name):
    return next(e for e in ir.resource_map() if (e["resource_type"], e["name"]) == (rtype, name))


def test_tables_only_estate_produces_every_resource_type_with_provenance(tables_only):
    entries = {(e["resource_type"], e["name"]): e for e in tables_only.resource_map()}
    assert {t for t, _ in entries} == {"FILE", "TRANSACTION", "PROGRAM", "MAPSET", "PARTITIONSET", "TDQUEUE", "TSMODEL"}
    acct = entries[("FILE", "ACCTDAT")]
    assert acct["sources"] == ["MACRO"]
    (d,) = acct["definitions"]
    assert (d["macro_table"], d["defined_in"], d["line"]) == ("DFHFCT01", "DFHFCT.asm", 5)
    assert acct["merged"]["dsname"] == "BANK.ACCT.DAM" and acct["merged"]["key_length"] == 11
    audt = entries[("TDQUEUE", "AUDT")]["merged"]
    assert (audt["ddname"], audt["dsname"], audt["queue_type"]) == ("AUDITDD", None, "EXTRA")  # SDSCI has no DSNAME
    assert entries[("TDQUEUE", "CSSL")]["merged"]["transid"] == "CSML"
    assert ("FILE", "RMTFIL") in entries and ("MAPSET", "BANKMAP") in entries
    assert entries[("TRANSACTION", "BA01")]["merged"]["program"] == "BANKINQ"
    assert {n for t, n in entries if t == "TSMODEL"} == {"BANK", "AUDT", "RCV", "SEC", "RMT"}


def test_tables_only_estate_has_no_conflicts(tables_only):
    assert tables_only.resource_conflicts() == []


def test_a_macro_file_joins_dataset_lineage_like_a_csd_file(tables_only):
    files = {f["file"]: f for f in tables_only.cics_file_datasets()}
    assert files["ACCTDAT"]["dsname"] == "BANK.ACCT.DAM"
    assert files["ACCTDAT"]["defined_in"] == "DFHFCT.asm"


def test_macro_and_csd_definitions_merge_into_one_entry(both):
    acct = _entry(both, "FILE", "ACCTDAT")
    assert acct["sources"] == ["CSD", "MACRO"]
    assert sorted(d["source"] for d in acct["definitions"]) == ["CSD", "MACRO"]
    assert acct["merged"]["dsname"] == "BANK.ACCT.DAM"  # they agree
    assert _entry(both, "MAPSET", "BANKMAP")["sources"] == ["CSD", "MACRO"]
    assert {d["defined_in"] for d in acct["definitions"]} == {"DFHFCT.asm", "REGION.csd"}
    # TDQUEUE AUDT: the macro EXTRA+SDSCI and the CSD DEFINE state the same ddname, format and size.
    audt = _entry(both, "TDQUEUE", "AUDT")["merged"]
    assert (audt["ddname"], audt["record_format"]) == ("AUDITDD", "VARIABLE")


def test_conflicts_are_named_with_both_sides_and_their_provenance(both):
    attr = {
        (c["resource_type"], c["name"], c["field"]): c for c in both.resource_conflicts() if c["kind"] == "attribute"
    }
    assert set(attr) == {
        ("FILE", "CUSTDAT", "dsname"),
        ("TRANSACTION", "BA02", "program"),
        ("TDQUEUE", "CSSL", "transid"),
    }
    c = attr[("FILE", "CUSTDAT", "dsname")]
    seen = {(v["value"], v["defined"][0]["source"], v["defined"][0]["defined_in"]) for v in c["values"]}
    assert seen == {("BANK.CUST.DAM", "MACRO", "DFHFCT.asm"), ("BANK.CUST.OTHER", "CSD", "REGION.csd")}
    assert {v["value"] for v in attr[("TDQUEUE", "CSSL", "transid")]["values"]} == {"CSML", "CSMT"}
    assert _entry(both, "FILE", "CUSTDAT")["merged"]["dsname"] is None  # no silent winner
    assert {v["value"] for v in attr[("TRANSACTION", "BA02", "program")]["values"]} == {"BANKUPD", "BANKXFR"}


def test_a_field_one_source_omits_is_not_a_conflict(both):
    # The macro CUSTDAT states no RECSIZE and the CSD states none either; ACCTDAT's
    # macro and CSD both state RECORDSIZE. A one-sided value merges, never conflicts.
    assert not [
        c for c in both.resource_conflicts() if c["kind"] == "attribute" and c["field"] in ("record_size", "key_length")
    ]
    assert _entry(both, "FILE", "CUSTDAT")["merged"]["key_length"] == 16


def test_single_source_resources_are_named_only_in_when_both_sources_exist(both):
    only = {(c["resource_type"], c["name"]): c["only_in"] for c in both.resource_conflicts() if c["kind"] == "only_in"}
    assert only[("FILE", "MACONLY")] == "MACRO"
    assert only[("FILE", "CSDONLY")] == "CSD"
    assert ("FILE", "ACCTDAT") not in only
