"""#7965 (X22): a case can state a region that installs several instances of one template.

`install_symbols` resolves a template (`ZC@ID@FILE`) to ONE instance (`ZC01FILE`). `region_instances` names the others the
region also defines (`ZC02FILE`): the stub's files.cfg gives each an empty data set and the port's region set holds it.
One generated table still stands behind every instance (register X22), so the port refuses a task that reaches one.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import equivalence_cics as EC  # noqa: E402

FILES = [
    {"file": "ZC@ID@FILE", "base": "zcfile", "reclen": 80, "key_offset": 0, "key_length": 8},
    {"file": "ZC@ID@KEY", "base": "zckey", "reclen": 40, "key_offset": 0, "key_length": 8},
    {"file": "PLAINFIL", "base": "plain", "reclen": 10, "key_offset": 0, "key_length": 2},
]
SYMBOLS = {"values": {"ID": "01"}, "why": "instance 01"}


def _case(values=None, **extra):
    case = {"install_symbols": SYMBOLS, **extra}
    if values is not None:
        case["region_instances"] = {"values": values, "why": "the region also installs instance 02"}
    return case


def test_no_key_is_no_extra_instance():
    assert EC.region_instances(_case(), FILES) == []
    assert EC._instance_cfg(_case(), FILES, "/work/files") == ""


def test_each_template_takes_its_own_extra_instance():
    got = EC.region_instances(_case(["ZC02FILE", "ZC02KEY", "ZC03FILE"]), FILES)
    assert [(n, f["base"]) for n, f in got] == [("ZC02FILE", "zcfile"), ("ZC02KEY", "zckey"), ("ZC03FILE", "zcfile")]
    cfg = EC._instance_cfg(_case(["ZC02FILE", "ZC02KEY"]), FILES, "/work/files").splitlines()
    assert cfg[0].startswith("ZC02FILE /work/files/zcfile.ZC02FILE 80 0 8")
    assert cfg[1].startswith("ZC02KEY /work/files/zckey.ZC02KEY 40 0 8")


@pytest.mark.parametrize(
    "bad",
    [
        ["ZC01FILE"],  # the case's own instance
        ["PLAINFIL"],  # a plain file is not a template instance
        ["NOSUCH"],  # fits no template
        ["zc02file"],  # not upper case
        ["ZC02FILE", "ZC02FILE"],  # twice
        [],
        "ZC02FILE",
        [7],
    ],
)
def test_a_value_that_is_not_another_instance_of_one_template_is_refused(bad):
    with pytest.raises(EC.Unsupported):
        EC.region_instances(_case(bad), FILES)


def test_the_statement_needs_a_reason_and_no_other_key():
    for spec in ({"values": ["ZC02FILE"]}, {"values": ["ZC02FILE"], "why": "x", "more": 1}, ["ZC02FILE"]):
        case = {**_case(), "region_instances": spec}
        with pytest.raises(EC.Unsupported):
            EC.region_instances(case, FILES)


# ---- #7965 slice 2: per-instance seed and dump ----------------------------------------------------------------------
def _stated(tmp_path, own, other, other_name="ZC02FILE"):
    (tmp_path / "own.dat").write_bytes(own)
    (tmp_path / "other.dat").write_bytes(other)
    return {
        "install_symbols": SYMBOLS,
        "datasets": {"zcfile": {"input": str(tmp_path / "own.dat"), "entity": "ZcFile"}},
        "region_instances": {
            "values": [other_name],
            "why": "the region also installs instance 02",
            "datasets": {other_name: {"input": str(tmp_path / "other.dat")}},
        },
    }


FILES1 = FILES[:1]


def _rec(key):
    return key.ljust(80).encode("ascii")


def test_instance_records_are_the_stated_bytes_and_unstated_ones_are_empty(tmp_path):
    case = _stated(tmp_path, _rec("AAAAAAAA"), _rec("BBBBBBBB"))
    assert EC.instance_records(case, tmp_path, FILES1) == {"ZC02FILE": _rec("BBBBBBBB")}
    assert list(EC.instance_data(case, FILES1)) == ["zcfile"]
    plain = {"install_symbols": SYMBOLS, "region_instances": {"values": ["ZC02FILE"], "why": "x"}}
    assert EC.instance_data(plain, FILES1) == {}  # nothing stated: the store is seeded and dumped as before
    assert EC.instance_records(plain, tmp_path, FILES1) == {}


def test_two_instances_holding_one_key_are_refused_until_the_key_has_the_instance(tmp_path):
    case = _stated(tmp_path, _rec("AAAAAAAA"), _rec("AAAAAAAA"))
    with pytest.raises(EC.Unsupported, match="both hold key"):
        EC.instance_records(case, tmp_path, FILES1)


@pytest.mark.parametrize(
    "ds",
    [
        {"ZC09FILE": {"input": "x"}},
        {"ZC02FILE": {"input": "@generate"}},
        {"ZC02FILE": {"inp": "x"}},
        {"ZC02FILE": "x"},
        ["x"],
    ],
)
def test_a_bad_instance_dataset_is_refused(ds):
    spec = {"values": ["ZC02FILE"], "why": "x", "datasets": ds}
    with pytest.raises(EC.Unsupported):
        EC.region_instances({"install_symbols": SYMBOLS, "region_instances": spec}, FILES)


def test_compare_files_judges_each_extra_instance(tmp_path):
    case = _stated(tmp_path, _rec("AAAAAAAA"), _rec("BBBBBBBB"))
    out = tmp_path / "out"
    out.mkdir()
    same = {"zcfile": _rec("AAAAAAAA"), "zcfile.ZC02FILE": _rec("BBBBBBBB")}
    (out / "s.zcfile.out").write_bytes(_rec("AAAAAAAA"))
    (out / "s.zcfile.ZC02FILE.out").write_bytes(_rec("BBBBBBBB"))
    assert EC.compare_files(case, tmp_path, FILES1, same, out, "s") == {}
    (out / "s.zcfile.ZC02FILE.out").write_bytes(b"")  # the port lost the other instance's row
    assert list(EC.compare_files(case, tmp_path, FILES1, same, out, "s")) == ["zcfile.ZC02FILE"]


def test_the_java_test_tags_and_filters_rows_by_instance_only_when_instances_state_data(tmp_path):
    import equivalence_java as ej

    (tmp_path / "service").mkdir()
    (tmp_path / "service" / f"{ej._service_class('PROG')}.java").write_text("public void handleLink() {}")
    case = {
        **_stated(tmp_path, _rec("AAAAAAAA"), _rec("BBBBBBBB")),
        "program": "PROG",
        "commarea": None,
        "scenarios": [],
        "transid": "ABCD",
        "name": "n",
        "screens": {},
        "clock": "2026/10/01 10:30:15.00",
    }
    java = EC.cics_equivalence_test(case, tmp_path, FILES1)
    assert 'load(sc, "zcfile.ZC02FILE", 80,' in java and 'row.setVsamInstance("ZC02FILE")' in java
    assert 'row.setVsamInstance("ZC01FILE")' in java
    assert 'zcfile.ZC02FILE.out"' in java
    assert '"ZC01FILE".equals(row.getVsamInstance())' in java
    plain = {**case, "region_instances": {"values": ["ZC02FILE"], "why": "x"}}
    java2 = EC.cics_equivalence_test(plain, tmp_path, FILES1)
    assert "setVsamInstance" not in java2 and "getVsamInstance" not in java2
