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


def test_two_instances_holding_one_key_are_refused_where_the_entity_names_no_instance(tmp_path):
    case = _stated(tmp_path, _rec("AAAAAAAA"), _rec("AAAAAAAA"))
    with pytest.raises(EC.Unsupported, match="both hold key"):
        EC.instance_records(case, tmp_path, FILES1)
    with pytest.raises(EC.Unsupported, match="both hold key"):
        EC.instance_records(case, tmp_path, FILES1, scoped={"other"})


def test_two_instances_may_hold_one_key_where_the_entity_names_its_instance(tmp_path):
    case = _stated(tmp_path, _rec("AAAAAAAA"), _rec("AAAAAAAA"))
    got = EC.instance_records(case, tmp_path, FILES1, scoped={"zcfile"})
    assert got == {"ZC02FILE": _rec("AAAAAAAA")}


def test_the_harness_scopes_a_store_by_its_entity_shape(tmp_path):
    for shape, scoped in (('class ZcFile { private String vsamInstance = ""; }', True), ("class ZcFile { }", False)):
        _entity(tmp_path, "ZcFile", shape)
        assert (EC._instance_accessors(tmp_path, "ZcFile") is not None) is scoped


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


# #7965 slice 3b: the port builds one Store per instance, so a task may reach two instances without a Hole.
def _entity(root, name, body):
    d = root / "entity" / "vsam"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.java").write_text(body)


@pytest.mark.parametrize(
    ("shape", "want"),
    [
        ("own", ("{r}.getVsamInstance()", "{r}.setVsamInstance({i})")),
        ("embedded", ("{r}.getId().getVsamInstance()", "{r}.getId().setVsamInstance({i})")),
        ("unreadable", None),
    ],
)
def test_the_instance_accessor_follows_the_entity_shape(tmp_path, shape, want):
    from gitgalaxy.tools.cobol_to_java.det import cics_filecontrol as FC

    if shape == "own":
        _entity(tmp_path, "Rec", 'class Rec { private String vsamInstance = ""; }')
    elif shape == "embedded":
        _entity(tmp_path, "Rec", "class Rec {\n    @EmbeddedId\n    private RecKey id;\n}")
        _entity(tmp_path, "RecKey", 'class RecKey { private String vsamInstance = ""; }')
    else:
        _entity(tmp_path, "Rec", "class Rec { private String other; }")
    assert FC.instance_accessors(tmp_path, "Rec") == want
    assert FC.instance_accessors(None, "Rec") is None


def test_a_scoped_store_map_drops_the_claim_hole_and_a_plain_list_keeps_it():
    from gitgalaxy.tools.cobol_to_java.det import cics_filecontrol as FC

    names = FC.StoreMap({"ZC@ID@FILE": "x"})
    scoped = "\n".join(FC.file_key_method(names))
    assert "private void claimInstance(String name) { }" in scoped
    assert "regionFiles" not in scoped.split("claimInstance", 1)[1]
    names.unscoped = True
    assert "private void claimInstance(String name) { }" not in "\n".join(FC.file_key_method(names))
    assert "private void claimInstance(String name) { }" not in "\n".join(FC.file_key_method(["ZC@ID@FILE"]))


def test_the_harness_tags_a_plain_cases_own_rows_when_the_entity_names_an_instance(tmp_path):
    import equivalence_java as ej

    (tmp_path / "service").mkdir()
    (tmp_path / "service" / f"{ej._service_class('PROG')}.java").write_text("public void handleLink() {}")
    _entity(tmp_path, "ZcFile", "class ZcFile {\n    @EmbeddedId\n    private ZcFileKey id;\n}")
    _entity(tmp_path, "ZcFileKey", 'class ZcFileKey { private String vsamInstance = ""; }')
    case = {
        **_stated(tmp_path, _rec("AAAAAAAA"), _rec("BBBBBBBB")),
        "program": "PROG", "commarea": None, "scenarios": [], "transid": "ABCD", "name": "n", "screens": {},
        "clock": "2026/10/01 10:30:15.00",
        "region_instances": {"values": ["ZC02FILE"], "why": "x"},
    }  # fmt: skip
    java = EC.cics_equivalence_test(case, tmp_path, FILES1)
    assert 'row.getId().setVsamInstance("ZC01FILE")' in java
    assert '"ZC01FILE".equals(row.getId().getVsamInstance())' in java


# ---- #7965 slice 5: a variable-length template's record lengths, per instance ----------------------------------------
def _variable(tmp_path, own, other, own_lengths, other_lengths):
    case = _stated(tmp_path, own, other)
    case["datasets"]["zcfile"].update({"vsam": {"variable": True}, "lengths": own_lengths})
    case["region_instances"]["datasets"]["ZC02FILE"]["lengths"] = other_lengths
    return case


def test_a_variable_length_instance_dataset_is_no_longer_refused_and_keeps_its_own_lengths(tmp_path):
    key = "AAAAAAAA".encode().hex().upper()
    case = _variable(tmp_path, _rec("AAAAAAAA"), _rec("AAAAAAAA"), {key: 30}, {key: 50})
    assert EC.instance_records(case, tmp_path, FILES1, scoped={"zcfile"}) == {"ZC02FILE": _rec("AAAAAAAA")}
    lens = EC.instance_lengths(case, tmp_path, FILES1)
    assert list(lens) == ["ZC02FILE"] and EC.parse_lengths(lens["ZC02FILE"]) == {key: 50}  # not the own file's 30
    assert EC.parse_lengths(EC.record_lengths(case, tmp_path, case["datasets"]["zcfile"], FILES1[0])) == {key: 30}


def test_a_fixed_length_file_and_an_unstated_instance_have_no_instance_lengths(tmp_path):
    assert EC.instance_lengths(_stated(tmp_path, _rec("AAAAAAAA"), _rec("BBBBBBBB")), tmp_path, FILES1) == {}
    plain = {**_variable(tmp_path, _rec("A"), _rec("B"), {}, {})}
    plain["region_instances"].pop("datasets")
    assert EC.instance_lengths(plain, tmp_path, FILES1) == {}


def test_compare_files_judges_each_instances_record_lengths(tmp_path):
    key = "AAAAAAAA".encode().hex().upper()
    case = _variable(tmp_path, _rec("AAAAAAAA"), _rec("AAAAAAAA"), {}, {})
    out = tmp_path / "out"
    out.mkdir()
    cobol = {
        "zcfile": _rec("AAAAAAAA"),
        "zcfile.ZC02FILE": _rec("AAAAAAAA"),
        "zcfile.ZC02FILE.len": f"{key} 50\n".encode(),
    }
    (out / "s.zcfile.out").write_bytes(_rec("AAAAAAAA"))
    (out / "s.zcfile.ZC02FILE.out").write_bytes(_rec("AAAAAAAA"))
    (out / "s.zcfile.ZC02FILE.len.out").write_text(f"{key} 50\n")
    assert EC.compare_files(case, tmp_path, FILES1, cobol, out, "s") == {}
    (out / "s.zcfile.ZC02FILE.len.out").write_text(f"{key} 30\n")  # the port kept the other instance's length
    got = EC.compare_files(case, tmp_path, FILES1, cobol, out, "s")
    assert list(got) == ["zcfile.ZC02FILE lengths"]
    assert got["zcfile.ZC02FILE lengths"]["lengths"] == [{"key": key, "cobol": 50, "java": 30}]


def test_the_java_test_loads_and_dumps_lengths_under_each_instances_key(tmp_path):
    import equivalence_java as ej

    (tmp_path / "service").mkdir()
    (tmp_path / "service" / f"{ej._service_class('PROG')}.java").write_text("public void handleLink() {}")
    _entity(tmp_path, "ZcFile", "class ZcFile {\n    @EmbeddedId\n    private ZcFileKey id;\n}")
    _entity(tmp_path, "ZcFileKey", 'class ZcFileKey { private String vsamInstance = ""; }')
    case = {
        **_variable(tmp_path, _rec("AAAAAAAA"), _rec("AAAAAAAA"), {}, {}),
        "program": "PROG", "commarea": None, "scenarios": [], "transid": "ABCD", "name": "n", "screens": {},
        "clock": "2026/10/01 10:30:15.00",
    }  # fmt: skip
    java = EC.cics_equivalence_test(case, tmp_path, FILES1)
    assert 'lengthsIn(sc, "zcfile", CicsTask.instanceKey("ZcFile", "ZC01FILE"));' in java
    assert 'lengthsIn(sc, "zcfile.ZC02FILE", CicsTask.instanceKey("ZcFile", "ZC02FILE"));' in java
    assert 'zcfile.ZC02FILE.len.out", CicsTask.instanceKey("ZcFile", "ZC02FILE"));' in java
    # a store whose entity names no instance is one shared table: the entity's own key, as before (#6839)
    _entity(tmp_path, "ZcFile", "class ZcFile { }")
    shared = EC.cics_equivalence_test(
        {**case, "region_instances": {"values": ["ZC02FILE"], "why": "x"}}, tmp_path, FILES1
    )
    assert 'lengthsIn(sc, "zcfile", "ZcFile");' in shared and "instanceKey" not in shared.split("lengthsIn(sc", 1)[1]


def test_the_translator_and_runtime_key_a_stores_lengths_by_instance():
    from gitgalaxy.tools.cobol_to_java import cobol_to_java_transaction_forge as forge
    from gitgalaxy.tools.cobol_to_java.det import cics as det_cics

    text = Path(det_cics.__file__).read_text(encoding="utf-8")
    assert "withLengths(CicsTask.recordLengths({G_jstr(entity)}, n))" in text  # the instance Store
    assert "withLengths(CicsTask.recordLengths({G_jstr(entity)}))" in text  # a shared store, unchanged
    assert 'return entity + "@" + instance.stripTrailing();' in forge.CICS_TASK_JAVA
    assert "recordLengths(String entity, String instance)" in forge.CICS_TASK_JAVA


def test_a_scenario_may_leave_an_extra_instance_out_of_its_region():
    case = _case(["ZC02FILE", "ZC02KEY"])
    sc = {"name": "s", "undefined_files": ["ZC02FILE"]}
    assert EC.undefined_files(case, sc, FILES) == ["ZC02FILE"]
    cfg = EC._instance_cfg(case, FILES, "/work/files", sc).splitlines()
    assert [ln.split()[0] for ln in cfg] == ["ZC02KEY"]  # the other instance stays installed
    assert len(EC._instance_cfg(case, FILES, "/work/files").splitlines()) == 2  # no scenario: both
    with pytest.raises(EC.Unsupported):  # a name that is neither the case's file nor an instance it states
        EC.undefined_files(case, {"name": "s", "undefined_files": ["ZC03FILE"]}, FILES)


def test_an_instance_fits_a_store_by_its_template_once_the_install_symbols_resolved_its_name():
    resolved = [
        {**f, "file": f["file"].replace("@ID@", "01"), "template": f["file"]} if "@" in f["file"] else f for f in FILES
    ]
    got = EC.region_instances(_case(["ZC02FILE", "ZC02KEY"]), resolved)
    assert [(n, f["base"]) for n, f in got] == [("ZC02FILE", "zcfile"), ("ZC02KEY", "zckey")]
    with pytest.raises(EC.Unsupported):  # the case's own resolved name is no extra instance
        EC.region_instances(_case(["ZC01FILE"]), resolved)


def test_zecs003_holds_one_key_in_two_instances_and_the_task_leaves_the_other_alone():
    import json

    d = Path(__file__).resolve().parents[1] / "equivalence" / "zecs-zecs003"
    case = json.loads((d / "case.json").read_text(encoding="utf-8"))
    assert case["region_instances"]["values"] == ["ZC02FILE"] and case["region_instances"]["why"]
    names = {s["name"]: s for s in case["scenarios"]}
    assert "expired-record-deleted-other-instance-same-key" in names
    assert names["transid-zc02"]["undefined_files"] == ["ZC02FILE"]  # #7487: still the region without instance 02
    own, other = (d / "zcfile-expired.bin").read_bytes(), (d / "zcfile-zc02.bin").read_bytes()
    assert own != other and own[:16] == other[:16]  # the same key, other contents
