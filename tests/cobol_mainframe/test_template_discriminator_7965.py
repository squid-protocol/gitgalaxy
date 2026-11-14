"""#7965 slices 1 and 3a (register X22): a store behind a template-named CICS file (the CSD's `ZC@ID@FILE`) carries a
`VSAM_INSTANCE` discriminator column, and the instance is part of its key (an @IdClass `InstanceKey`, or inside a group
key's @EmbeddedId class; an ESDS / RRDS keeps its generated id). The repository, its finders and the service take the
instance. Any other store is unchanged."""

import pytest

from gitgalaxy.tools.cobol_to_java.cobol_to_java_repository_forge import RepositoryForge

LAYOUT = {"bytes": 12, "fields": [
    {"name": "REC-KEY", "pic": "X(8)", "usage": None, "offset": 0, "bytes": 8, "occurs": None},
    {"name": "REC-VAL", "pic": "X(4)", "usage": None, "offset": 8, "bytes": 4, "occurs": None},
]}  # fmt: skip


LAYOUT2 = {"bytes": 12, "fields": [
    {"name": "K-A", "pic": "X(4)", "usage": None, "offset": 0, "bytes": 4, "occurs": None},
    {"name": "K-B", "pic": "X(4)", "usage": None, "offset": 4, "bytes": 4, "occurs": None},
    {"name": "REC-VAL", "pic": "X(4)", "usage": None, "offset": 8, "bytes": 4, "occurs": None},
]}  # fmt: skip


def _forge(cics_files: list[str], *, org: str = "INDEXED", key=(0, 8), verbs=("READ",), layout=LAYOUT, aix=()):
    raw = {"name": cics_files[0] if cics_files else "F", "dataset": "APP.TBL.KSDS", "organization": org,
           "record_max": 12, "key_offset": key[0], "key_length": key[1], "alternate_indexes": [],
           "cics_files": [{"file": n} for n in cics_files],
           "users": [{"program": "cbl/P.cbl", "kind": "cics", "name": "TBL", "verbs": list(verbs), "records": [
               {"record": "REC", "file": "cpy/REC.cpy", "layout": layout}]}]}  # fmt: skip
    if aix:
        raw["alternate_indexes"] = [{"aix": "AIX1", "paths": ["PATH1"], "key_offset": 8, "key_length": 4,
                                     "unique": False}]  # fmt: skip
    forge = RepositoryForge({"sections": {"vsam_stores": {"facts": [raw]}}},
                            {"P": {"program": {"file": "cbl/P.cbl"}}}, "com.t")  # fmt: skip
    assert len(forge.stores) == 1
    return forge


def _entity(cics_files: list[str], *, org: str = "INDEXED", key=(0, 8)) -> str:
    forge = _forge(cics_files, org=org, key=key)
    return forge.entity_source(forge.stores[0])


def _service(cics_files, **kw) -> str:
    forge = _forge(cics_files, **kw)
    return "\n".join(forge.service_extras("P")["methods"])


@pytest.mark.parametrize("name", ["ZC@ID@FILE", "ZC@ID@KEY", "ZC##FILE"])
def test_a_template_store_gets_the_instance_column(name):
    src = _entity([name])
    assert '@Column(name = "VSAM_INSTANCE", length = 8, nullable = false)' in src
    assert "private String vsamInstance" in src
    assert name in src


@pytest.mark.parametrize("org,key", [("INDEXED", (0, 8)), ("INDEXED", (0, 5)), ("NONINDEXED", (None, None))])
def test_a_template_store_of_every_key_shape_gets_it(org, key):
    assert "VSAM_INSTANCE" in _entity(["ZC@ID@FILE"], org=org, key=key)


def test_a_single_key_template_store_keys_by_key_and_instance():
    src = _entity(["ZC@ID@FILE"])
    assert "@IdClass(Rec.InstanceKey.class)" in src
    assert "public static class InstanceKey" in src
    assert src.count("    @Id\n") == 2  # the key and the instance
    repo = (lambda f: f.repository_source(f.stores[0]))(_forge(["ZC@ID@FILE"]))
    assert "JpaRepository<Rec, Rec.InstanceKey>" in repo


def test_a_string_vsam_key_template_store_keys_by_key_and_instance():
    src = _entity(["ZC@ID@FILE"], key=(0, 5))
    assert "@IdClass(Rec.InstanceKey.class)" in src and "private String vsamKey;" in src
    assert "InstanceKey(String vsamKey, String vsamInstance)" in src


def test_a_group_key_carries_the_instance_in_its_key_class():
    f = _forge(["ZC@ID@FILE"], key=(0, 8), layout=LAYOUT2)
    st = f.stores[0]
    assert st.composite
    ent, key = f.entity_source(st), f.key_source(st)
    assert "@IdClass" not in ent and "private String vsamInstance" not in ent
    assert 'name = "VSAM_INSTANCE"' in key and "private String vsamInstance" in key
    assert "@Data" in key  # lombok equality covers every field, the instance too


@pytest.mark.parametrize("org", ["NONINDEXED", "NUMBERED"])
def test_an_esds_or_rrds_template_store_keeps_its_generated_id(org):
    src = _entity(["ZC@ID@FILE"], org=org, key=(None, None))
    assert "@IdClass" not in src and "@GeneratedValue" in src
    assert src.count("    @Id\n") == 1 and "VSAM_INSTANCE" in src


def test_the_repository_finders_of_a_template_store_stay_in_one_instance():
    f = _forge(["ZC@ID@FILE"], verbs=("READ", "STARTBR", "READNEXT", "READPREV"), aix=True)
    repo = f.repository_source(f.stores[0])
    assert "findByVsamInstanceAndRecKeySortGreaterThanEqualOrderByRecKeySortAsc(String vsamInstance, String" in repo
    assert "findByVsamInstanceAndRecKeySortLessThanEqualOrderByRecKeySortDesc(String vsamInstance, String" in repo
    assert "e.vsamInstance = :vsamInstance" in repo  # the alternate index finder


def test_the_group_key_finder_of_a_template_store_stays_in_one_instance():
    f = _forge(["ZC@ID@FILE"], layout=LAYOUT2, verbs=("READ", "STARTBR", "READNEXT"))
    assert "findByIdVsamInstanceOrderByIdKAAscIdKBAsc(String vsamInstance, Pageable page)" in (
        f.repository_source(f.stores[0])
    )


def test_the_service_of_a_template_store_takes_the_instance():
    svc = _service(["ZC@ID@FILE"], verbs=("READ", "WRITE", "REWRITE", "DELETE", "STARTBR", "READNEXT", "READPREV"))
    assert "readTbl(String vsamInstance, String key)" in svc
    assert "findById(new Rec.InstanceKey(key, vsamInstance))" in svc
    assert "deleteById(new Rec.InstanceKey(key, vsamInstance))" in svc
    assert "writeTbl(String vsamInstance, Rec record)" in svc and "record.setVsamInstance(vsamInstance);" in svc
    assert "rewriteTbl(String vsamInstance, Rec record)" in svc
    assert "browseTbl(String vsamInstance, String from, int count)" in svc
    assert "browseBackTbl(String vsamInstance, String from, int count)" in svc


def test_the_service_of_a_group_key_template_store_sets_the_instance_in_the_key():
    svc = _service(["ZC@ID@FILE"], layout=LAYOUT2, verbs=("READ", "WRITE", "DELETE"))
    assert "key.setVsamInstance(vsamInstance);" in svc
    assert "record.getId().setVsamInstance(vsamInstance);" in svc


def test_the_service_of_an_esds_template_store_filters_by_instance():
    svc = _service(["ZC@ID@FILE"], org="NONINDEXED", key=(None, None), verbs=("READ", "DELETE"))
    assert "readTbl(String vsamInstance, Long key)" in svc
    assert ".filter(r -> vsamInstance.equals(r.getVsamInstance()))" in svc


def test_a_plain_store_service_and_repository_are_unchanged():
    svc = _service(["ACCTF"], verbs=("READ", "WRITE", "DELETE", "STARTBR", "READNEXT"))
    assert "readTbl(String key)" in svc and "vsamInstance" not in svc
    f = _forge(["ACCTF"])
    assert "JpaRepository<Rec, String>" in f.repository_source(f.stores[0])
    assert "@IdClass" not in f.entity_source(f.stores[0])


def test_a_plain_store_is_unchanged():
    assert "VSAM_INSTANCE" not in _entity(["ACCTF"])
    assert "VSAM_INSTANCE" not in _entity([])
