"""#8074: an extensionless PDS copybook member was never scanned unless its directory's last qualifier was
`copylib` / `cpy` / `cobol` (and dotted), so the engine drew no COPY edge and the det translator refused whole with
`CopyUnresolved`. One real scan of an authored estate (invented names) backs the tests."""

import pytest

from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir
from gitgalaxy.tools.cobol_to_java.det import source as SRC
from scan_server import scan_to_db

DIRS = {
    "FAKE.APP.COPYLIB": "FAKEA",
    "FAKE.APP.COPYBOOK": "FAKEB",
    "FAKE.APP.CPYLIB": "FAKEC",
    "FAKE.APP.DCLGEN": "FAKED",
    "FAKE.APP.SRCLIB": "FAKEE",
    "COPYLIB": "FAKEF",  # no high-level qualifier
    "copybooks": "FAKEG",
}
BODY = "       01  {n}-REC.\n           05  {n}-ID   PIC X(8).\n           05  {n}-AMT  PIC S9(5)V99 COMP-3.\n"
PROG = (
    "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. FAKEPGM.\n       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n"
    + "".join(f"       COPY {m}.\n" for m in DIRS.values())
    + "       PROCEDURE DIVISION.\n           GOBACK.\n"
)


@pytest.fixture(scope="module")
def estate(tmp_path_factory):
    base = tmp_path_factory.mktemp("copy8074x")
    repo = base / "repo"
    (repo / "FAKE.APP.COBOL").mkdir(parents=True)
    (repo / "FAKE.APP.COBOL" / "FAKEPGM.cbl").write_text(PROG)
    for d, m in DIRS.items():
        (repo / d).mkdir()
        (repo / d / m).write_text(BODY.format(n=m))
    (repo / "FAKE.APP.COPYBOOK" / "README").write_text("Notes on this library.\nOwner: nobody.\n")
    (repo / "include").mkdir()
    # #8111: a COBOL body is claimed in any directory now; the C-style include dir keeps a C body
    (repo / "include" / "FAKEH").write_text("#define FAKEH_MAX 8\nint fakeh_count(void);\n")
    return repo, load_galaxy_ir(scan_to_db(repo, base / "scan"))


@pytest.mark.parametrize("d,m", DIRS.items())
def test_each_extensionless_member_is_scanned_and_resolved(estate, d, m):
    repo, ir = estate
    assert f"{d}/{m}" in ir.files
    copies = SRC.engine_copies_from_ir(ir, "FAKE.APP.COBOL/FAKEPGM.cbl", repo)
    assert [p.parent.name for p in copies.resolved[m]] == [d]


def test_a_readme_and_a_c_style_include_dir_are_not_claimed(estate):
    _, ir = estate
    for rel in ("FAKE.APP.COPYBOOK/README", "include/FAKEH"):
        assert rel not in ir.files or ir.files[rel].language != "cobol"
