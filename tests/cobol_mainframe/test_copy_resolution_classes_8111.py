"""#8111: resolver classes the copybook census found, proven on authored fixtures (invented names) through the real
engine: a same-stem non-source file beside a case-different member, and a `.copybooks` dot-directory library."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import copy_resolution_census as crc

ITEM = "       05  FAKE-ID   PIC X(8).\n       05  FAKE-NM   PIC X(8).\n"
PROGRAM = (
    "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. {pid}.\n       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n       01  REC.\n{copies}       PROCEDURE DIVISION.\n           GOBACK.\n"
)
SHADOWED = ["SHADA", "shadb", "ShadC", "SHADD", "SHADE", "SHADF"]  # members with a same-stem sibling of another kind
SIBLINGS = {"SHADA": "txt", "shadb": "json", "ShadC": "md", "SHADD": "", "SHADE": "csv", "SHADF": "py"}
DOT_DIRS = {
    "DOTA": ".copybooks/DOTA.cpy",
    "DOTB": ".copybooks/prof/DATA.SET.ONE/DOTB.cpy",
    "DOTC": "proj/.copybooks/a/b/c/DOTC.cpy",
    "DOTD": ".copybooks/prof/DOTD",
}


@pytest.fixture(scope="module")
def estate(tmp_path_factory):
    repo = tmp_path_factory.mktemp("est") / "fakeestate"
    (repo / "apps").mkdir(parents=True)
    copies = ""
    for i, m in enumerate(SHADOWED):
        # the member sits in a library directory under another case; a same-stem file of another kind sits elsewhere
        (repo / "lib").mkdir(exist_ok=True)
        (repo / "lib" / m.swapcase()).write_text(ITEM, encoding="utf-8")
        (repo / "data").mkdir(exist_ok=True)
        ext = SIBLINGS[m]
        (repo / "data" / (m + ("." + ext if ext else "x"))).write_text("plain data\n", encoding="utf-8")
        copies += f"       {'copy' if i % 2 else 'COPY'} {m}.\n"
    for m, rel in DOT_DIRS.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text("       01  " + m + "-REC.\n" + ITEM, encoding="utf-8")
        copies += f"       COPY {m}.\n"
    (repo / "apps" / "MAINPG.cbl").write_text(PROGRAM.format(pid="MAINPG", copies=copies), encoding="utf-8")
    # same-stem file in the importer's own language: the exact-case file still wins
    (repo / "apps" / "OWNCASE.cpy").write_text(ITEM, encoding="utf-8")
    (repo / "lib" / "owncase.CPY").write_text(ITEM, encoding="utf-8")
    (repo / "apps" / "OWNPG.cbl").write_text(
        PROGRAM.format(pid="OWNPG", copies="       COPY OWNCASE.\n"), encoding="utf-8"
    )
    # dot-named files inside the exempt directory stay blocked
    (repo / ".copybooks" / ".HIDDENX.cpy").write_text(ITEM, encoding="utf-8")
    edges, gaps = crc.engine_side(repo)
    return repo, edges, gaps


@pytest.mark.parametrize("member", SHADOWED)
def test_same_stem_non_source_file_does_not_hide_the_member(estate, member):
    _repo, edges, _gaps = estate
    assert {Path(p).name for p in edges["apps/MAINPG.cbl"]} >= {member.swapcase()}


@pytest.mark.parametrize("member", DOT_DIRS)
def test_copybooks_dot_directory_members_resolve(estate, member):
    _repo, edges, _gaps = estate
    assert DOT_DIRS[member] in edges["apps/MAINPG.cbl"]


def test_the_census_finds_no_disagreement(estate):
    repo, _edges, _gaps = estate
    n = crc.census_repo(repo)
    assert crc.disagreements(n) == 0, n


def test_exact_case_member_in_the_importers_language_still_wins(estate):
    _repo, edges, _gaps = estate
    assert set(edges["apps/OWNPG.cbl"]) == {"apps/OWNCASE.cpy"}


def test_dot_named_files_inside_the_library_stay_blocked(estate):
    _repo, edges, _gaps = estate
    assert not any(".HIDDENX" in f for f in edges)
