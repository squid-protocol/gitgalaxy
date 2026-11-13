"""#7965 slice 1 (register X22): a store behind a template-named CICS file (the CSD's `ZC@ID@FILE`) carries a
`VSAM_INSTANCE` discriminator column; any other store's entity is unchanged."""

import pytest

from gitgalaxy.tools.cobol_to_java.cobol_to_java_repository_forge import RepositoryForge

LAYOUT = {"bytes": 12, "fields": [
    {"name": "REC-KEY", "pic": "X(8)", "usage": None, "offset": 0, "bytes": 8, "occurs": None},
    {"name": "REC-VAL", "pic": "X(4)", "usage": None, "offset": 8, "bytes": 4, "occurs": None},
]}  # fmt: skip


def _entity(cics_files: list[str], *, org: str = "INDEXED", key=(0, 8)) -> str:
    raw = {"name": cics_files[0] if cics_files else "F", "dataset": "APP.TBL.KSDS", "organization": org,
           "record_max": 12, "key_offset": key[0], "key_length": key[1], "alternate_indexes": [],
           "cics_files": [{"file": n} for n in cics_files],
           "users": [{"program": "cbl/P.cbl", "kind": "cics", "name": "TBL", "verbs": ["READ"], "records": [
               {"record": "REC", "file": "cpy/REC.cpy", "layout": LAYOUT}]}]}  # fmt: skip
    forge = RepositoryForge({"sections": {"vsam_stores": {"facts": [raw]}}},
                            {"P": {"program": {"file": "cbl/P.cbl"}}}, "com.t")  # fmt: skip
    assert len(forge.stores) == 1
    return forge.entity_source(forge.stores[0])


@pytest.mark.parametrize("name", ["ZC@ID@FILE", "ZC@ID@KEY", "ZC##FILE"])
def test_a_template_store_gets_the_instance_column(name):
    src = _entity([name])
    assert '@Column(name = "VSAM_INSTANCE", length = 8, nullable = false)' in src
    assert "private String vsamInstance" in src
    assert name in src


@pytest.mark.parametrize("org,key", [("INDEXED", (0, 8)), ("INDEXED", (0, 5)), ("NONINDEXED", (None, None))])
def test_a_template_store_of_every_key_shape_gets_it(org, key):
    assert "VSAM_INSTANCE" in _entity(["ZC@ID@FILE"], org=org, key=key)


def test_a_plain_store_is_unchanged():
    assert "VSAM_INSTANCE" not in _entity(["ACCTF"])
    assert "VSAM_INSTANCE" not in _entity([])
