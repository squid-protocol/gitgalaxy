"""#8074: every extension the det translator's COPY search tries (`COPYBOOK_EXTS`, `PROGRAM_EXTS`) is one the engine
scans as COBOL, in either case. A member the translator finds but the census never scanned draws no COPY edge, and
the program refuses `CopyUnresolved` ("the engine resolved nothing; the estate holds X"). One real scan of an
authored estate (invented names) backs the tests."""

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir
from gitgalaxy.tools.cobol_to_java.det import source as SRC
from scan_server import scan_to_db

MEMBERS = {
    "FAKEA": "FAKEA.copy",
    "FAKEB": "FAKEB.COPY",
    "FAKEC": "FAKEC.cpy",
    "FAKED": "FAKED.CPY",
    "FAKEE": "FAKEE.dcl",
    "FAKEF": "FAKEF.DCL",
}
BODY = "       01  {n}-REC.\n           05  {n}-ID   PIC X(8).\n           05  {n}-AMT  PIC S9(5)V99 COMP-3.\n"
PROG = (
    "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. FAKEPGM.\n       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n"
    + "".join(f"       COPY {m}.\n" for m in MEMBERS)
    + "       PROCEDURE DIVISION.\n           GOBACK.\n"
)


@pytest.fixture(scope="module")
def estate(tmp_path_factory):
    base = tmp_path_factory.mktemp("copy8074e")
    repo = base / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "FAKEPGM.cbl").write_text(PROG)
    (repo / "lib").mkdir()
    for m, f in MEMBERS.items():
        (repo / "lib" / f).write_text(BODY.format(n=m))
    return repo, load_galaxy_ir(scan_to_db(repo, base / "scan"))


@pytest.mark.parametrize("m,f", MEMBERS.items())
def test_each_member_extension_is_scanned_and_resolved(estate, m, f):
    repo, ir = estate
    assert f"lib/{f}" in ir.files
    copies = SRC.engine_copies_from_ir(ir, "src/FAKEPGM.cbl", repo)
    assert [p.name for p in copies.resolved[m]] == [f]


def test_every_translator_copy_extension_is_a_cobol_extension():
    cobol = {e.lower() for e in LANGUAGE_DEFINITIONS["cobol"]["extensions"]}
    tried = {e.lower() for e in SRC.COPY_EXTS if e}
    assert tried <= cobol, sorted(tried - cobol)
