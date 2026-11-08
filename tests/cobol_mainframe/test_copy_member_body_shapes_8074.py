"""#8074: an extensionless PDS member under a library directory is claimed as COBOL only on body evidence. The
evidence read a PIC/USAGE clause on a data item's own line, so a group-only, 88-level / VALUE-only, multi-line or
COMPUTATIONAL copybook was never scanned: no COPY edge, and the det translator refused `CopyUnresolved`. One real scan
of an authored estate (invented names) backs the tests; negative controls stay unclaimed."""

import pytest

from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir
from gitgalaxy.tools.cobol_to_java.det import source as SRC
from scan_server import scan_to_db

MEMBERS = {
    "FAKEA": "       01  FAKEA-REC.\n           05  FAKEA-ID.\n           05  FAKEA-KEY.\n",
    "FAKEB": "       01  FAKEB-FLAGS.\n           88  FAKEB-ON   VALUE 'Y'.\n           88  FAKEB-OFF  VALUE 'N'.\n",
    "FAKEC": "       01  FAKEC-NAME  VALUE 'ABC'.\n",
    "FAKED": "       01  FAKED-REC.\n           05  FAKED-ID\n               PIC X(8).\n",
    "FAKEE": "000100 01  FAKEE-REC.\n000200     05  FAKEE-ID\n000300         PIC X(8).\n",
    "FAKEF": "       01  FAKEF-N  COMPUTATIONAL-3 PIC S9(5).\n",
    "FAKEG": "       01  FAKEG-N  COMP-5.\n",
    "FAKEH": "       01  FAKEH-REC.\n           05  FAKEH-N  SYNC.\n",
}
PROG = (
    "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. FAKEPGM.\n       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n"
    + "".join(f"       COPY {m}.\n" for m in MEMBERS)
    + "       PROCEDURE DIVISION.\n           GOBACK.\n"
)
NOT_COBOL = {
    "NOTES": "Notes on this library.\nOwner: nobody.\n",
    "STEPS": "Steps:\n10 Mix the value well\n01 Introduction to the value of x\n",
}


@pytest.fixture(scope="module")
def estate(tmp_path_factory):
    base = tmp_path_factory.mktemp("copy8074b")
    repo = base / "repo"
    (repo / "FAKE.APP.COBOL").mkdir(parents=True)
    (repo / "FAKE.APP.COBOL" / "FAKEPGM.cbl").write_text(PROG)
    (repo / "FAKE.APP.COPYLIB").mkdir()
    for m, body in MEMBERS.items():
        (repo / "FAKE.APP.COPYLIB" / m).write_text(body)
    for n, body in NOT_COBOL.items():
        (repo / "FAKE.APP.COPYLIB" / n).write_text(body)
    return repo, load_galaxy_ir(scan_to_db(repo, base / "scan"))


@pytest.mark.parametrize("m", MEMBERS)
def test_each_body_shape_is_scanned_and_resolved(estate, m):
    repo, ir = estate
    assert f"FAKE.APP.COPYLIB/{m}" in ir.files
    copies = SRC.engine_copies_from_ir(ir, "FAKE.APP.COBOL/FAKEPGM.cbl", repo)
    assert [p.name for p in copies.resolved[m]] == [m]


@pytest.mark.parametrize("n", NOT_COBOL)
def test_prose_in_a_library_dir_is_not_claimed(estate, n):
    _, ir = estate
    rel = f"FAKE.APP.COPYLIB/{n}"
    assert rel not in ir.files or ir.files[rel].language != "cobol"
