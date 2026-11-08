"""#8074: a program whose copybooks live under z/OS dataset-name directories (`FAKE.APP.COPYLIB`) of a
tree with no `.git` was refused whole with `CopyUnresolved`: the fallback walk pruned the directory
(its `.COPYLIB` suffix read as an unsupported file extension). One real galaxyscope scan of an authored
fixture (invented names) backs the tests."""

import pytest

from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir
from gitgalaxy.tools.cobol_to_java.det import source as SRC
from scan_server import scan_to_db

PROG = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. FAKEPGM.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY FAKECPY.
       PROCEDURE DIVISION.
           GOBACK.
"""
COPYBOOK = "       01  FAKE-REC.\n           05  FAKE-ID   PIC X(8).\n"
MEMBERS = ["FAKE.APP.COPYLIB", "FAKE.APP.CPYLIB", "FAKE.APP.INCLUDE"]


@pytest.fixture(scope="module")
def estate(tmp_path_factory):
    base = tmp_path_factory.mktemp("copy8074")
    repo = base / "repo"
    (repo / "FAKE.APP.COBOL").mkdir(parents=True)
    (repo / "FAKE.APP.COBOL" / "FAKEPGM.cbl").write_text(PROG)
    for d in MEMBERS[:1]:
        (repo / d).mkdir()
        (repo / d / "FAKECPY.cpy").write_text(COPYBOOK)
    # a sibling dataset dir that holds no copybook, only an extensionless member
    (repo / "FAKE.APP.DBRMLIB").mkdir()
    (repo / "FAKE.APP.DBRMLIB" / "FAKEPGM").write_text("DBRM FAKEPGM\n")
    return repo, load_galaxy_ir(scan_to_db(repo, base / "scan"))


def test_the_copybook_in_a_dataset_dir_is_scanned(estate):
    _, ir = estate
    assert "FAKE.APP.COPYLIB/FAKECPY.cpy" in ir.files


def test_the_engine_resolves_the_copy_and_the_translator_does_not_refuse(estate):
    repo, ir = estate
    rel = "FAKE.APP.COBOL/FAKEPGM.cbl"
    copies = SRC.engine_copies_from_ir(ir, rel, repo)
    assert copies is not None
    assert [p.as_posix().rsplit("/", 2)[-2:] for p in copies.resolved["FAKECPY"]] == [
        ["FAKE.APP.COPYLIB", "FAKECPY.cpy"]
    ]
