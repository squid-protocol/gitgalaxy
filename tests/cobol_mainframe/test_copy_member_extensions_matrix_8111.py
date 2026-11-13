"""#8111 / #8412: COPY members whose extension no language claims (`.lib`, `.cobcpy`, `.cobcopy`, `.cpb`). Aperture admits
one only to let the lens judge its body, and the lens calls it COBOL only for a COBOL body. Authored fixtures (invented
names), one real scan; the lens is also checked over the whole class, upper and lower case, with non-COBOL bodies."""

import pytest
from scan_server import scan_to_db

from gitgalaxy.standards.language_lens import LanguageDetector
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir
from gitgalaxy.tools.cobol_to_java.det import source as SRC

EXTS = [".lib", ".cobcpy", ".cobcopy", ".cpb"]
BODY = "       01  {n}-REC.\n           05  {n}-ID   PIC X(8).\n"
PROSE = "Fake notes\nsee the manual\n"
BINARY = b"!<arch>\n" + bytes(range(1, 40)) + b"\x00\x00\x00"
NON_COBOL = {
    "a.lib": "local M = {}\nreturn M\n",
    "b.cpb": "[section]\nkey=value\n",
    "c.lib": PROSE,
    "d.cobcpy": "#include <stdio.h>\nint fake(void);\n",
}
MEMBERS = {f"FAKE{i}": ext for i, ext in enumerate(EXTS + [e.upper() for e in EXTS])}


@pytest.fixture(scope="module")
def estate(tmp_path_factory):
    base = tmp_path_factory.mktemp("ext8412")
    repo = base / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "lib").mkdir()
    copies = ""
    for m, ext in MEMBERS.items():
        (repo / "lib" / (m + ext)).write_text(BODY.format(n=m), encoding="utf-8")
        copies += f"       COPY {m}.\n"
    (repo / "src" / "FAKEPGM.cbl").write_text(
        "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. FAKEPGM.\n       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n" + copies + "       PROCEDURE DIVISION.\n           GOBACK.\n",
        encoding="utf-8",
    )
    (repo / "other").mkdir()
    for name, text in NON_COBOL.items():
        (repo / "other" / name).write_text(text, encoding="utf-8")
    (repo / "other" / "bin.lib").write_bytes(BINARY)
    return repo, load_galaxy_ir(scan_to_db(repo, base / "scan"))


@pytest.fixture(scope="module")
def detector():
    return LanguageDetector(LANGUAGE_DEFINITIONS, {})


@pytest.mark.parametrize("member", sorted(MEMBERS))
def test_the_program_copy_resolves_to_a_member_with_this_extension(estate, member):
    repo, ir = estate
    copies = SRC.engine_copies_from_ir(ir, "src/FAKEPGM.cbl", repo)
    assert [p.relative_to(repo).as_posix() for p in copies.resolved[member]] == [f"lib/{member}{MEMBERS[member]}"]
    assert not copies.gaps


@pytest.mark.parametrize("ext", EXTS + [e.upper() for e in EXTS])
def test_the_lens_calls_a_cobol_body_cobol(detector, tmp_path, ext):
    assert detector.focus(str(tmp_path / ("FAKEA" + ext)), BODY.format(n="FAKEA"))[0] == "cobol"


@pytest.mark.parametrize("name", sorted(NON_COBOL))
def test_a_non_cobol_body_is_not_cobol(detector, tmp_path, name):
    assert detector.focus(str(tmp_path / name), NON_COBOL[name])[0] != "cobol"


def test_a_scan_drops_the_non_cobol_and_binary_files(estate):
    repo, ir = estate
    assert not [n for n in [*NON_COBOL, "bin.lib"] if ir.copy_resolution(f"other/{n}")["edges"].get(f"other/{n}")]
