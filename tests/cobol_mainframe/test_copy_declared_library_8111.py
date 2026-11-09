"""#8111 slice 5: an extensionless COPY member in a directory the workspace DECLARES as a copy library
(`.cobolplugin/proc_grps.json` `libs`, or `.vscode/settings.json` `cpy-manager.paths-local`) is COBOL even when the
directory holds no COBOL-extension file. Authored fixtures (invented names), through the lens over the whole class
(both declaration files, every path spelling, the body evidence that still gates) and one real scan."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import copy_resolution_census as crc

from gitgalaxy.standards.language_lens import LanguageDetector
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

ITEM = "       05 FAKE-ID PIC 9.\n"
CHAIN = "      * Fake banner line one                                          *\n       COPY FAKEZ.\n"
PROGRAM = (
    "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. {pid}.\n       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n       01  REC.\n{copies}       PROCEDURE DIVISION.\n           GOBACK.\n"
)


def proc_grps(libs):
    return ".cobolplugin/proc_grps.json", json.dumps({"pgms": [], "pgroups": [{"name": "P1", "libs": libs}]})


def settings(libs, key="cobol-lsp.cpy-manager.paths-local"):
    # a settings file is JSONC: comments must not hide the declaration
    return ".vscode/settings.json", '{\n  // fake note\n  "editor.tabSize": 4, /* x */\n  "' + key + '": ' + json.dumps(
        libs
    ) + "\n}\n"


DECLARATIONS = [
    ("proc_grps", proc_grps),
    ("settings", settings),
    ("settings_broadcom", lambda libs: settings(libs, "broadcom-cobol-lsp.cpy-manager.paths-local")),
]
SPELLINGS = ["FAKELIB", "fakelib", "./FAKELIB", "FAKELIB/", "FAKELIB\\", {"path": "FAKELIB"}]


@pytest.fixture(scope="module")
def detector():
    return LanguageDetector(LANGUAGE_DEFINITIONS, {})


def declare(root: Path, maker, libs):
    rel, text = maker(libs)
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text(text, encoding="utf-8")


def member(root: Path, rel: str, text: str) -> str:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return str(p)


@pytest.mark.parametrize("body", [ITEM, CHAIN], ids=["item", "chain"])
@pytest.mark.parametrize("spelling", SPELLINGS, ids=lambda s: str(s))
@pytest.mark.parametrize(("kind", "maker"), DECLARATIONS, ids=[d[0] for d in DECLARATIONS])
def test_a_declared_library_member_is_cobol(detector, tmp_path, kind, maker, spelling, body):
    declare(tmp_path, maker, [spelling])
    assert detector.focus(member(tmp_path, "FAKELIB/FAKEA", body), body)[0] == "cobol"


def test_a_nested_declaration_folder_is_the_base(detector, tmp_path):
    declare(tmp_path / "ws", proc_grps, ["sub/FAKELIB"])
    assert detector.focus(member(tmp_path, "ws/sub/FAKELIB/FAKEA", ITEM), ITEM)[0] == "cobol"
    assert detector.focus(member(tmp_path, "ws/FAKELIB/FAKEB", ITEM), ITEM)[0] != "cobol"


@pytest.mark.parametrize(("kind", "maker"), DECLARATIONS, ids=[d[0] for d in DECLARATIONS])
def test_an_undeclared_directory_is_not_claimed(detector, tmp_path, kind, maker):
    declare(tmp_path, maker, ["OTHERLIB"])
    assert detector.focus(member(tmp_path, "FAKELIB/FAKEA", ITEM), ITEM)[0] != "cobol"


@pytest.mark.parametrize(("kind", "maker"), DECLARATIONS, ids=[d[0] for d in DECLARATIONS])
@pytest.mark.parametrize(
    "text", ["just some text\n", "<?php\n$fake = 1;\n", "01 Introduction.\n", "#!/bin/sh\necho 05 X PIC 9\n"]
)
def test_a_declared_directory_still_needs_a_cobol_body(detector, tmp_path, kind, maker, text):
    declare(tmp_path, maker, ["FAKELIB"])
    assert detector.focus(member(tmp_path, "FAKELIB/FAKEA", text), text)[0] != "cobol"


@pytest.mark.parametrize(
    "files",
    [
        {".cobolplugin/proc_grps.json": "{ not json"},
        {".cobolplugin/proc_grps.json": '{"pgroups": [{"libs": [1, null, {"path": 2}]}]}'},
        {".cobolplugin/proc_grps.json": '["pgroups"]'},
        {".vscode/settings.json": '{"cobol-lsp.cpy-manager.paths-local": "FAKELIB"}'},
        {".vscode/settings.json": "[]"},
        {".vscode/settings.json": '{"cobol-lsp.cpy-manager.paths-local": ["/abs/FAKELIB"]}'},
    ],
    ids=range(6),
)
def test_a_malformed_or_foreign_declaration_claims_nothing_and_never_raises(detector, tmp_path, files):
    for rel, text in files.items():
        member(tmp_path, rel, text)
    assert detector.focus(member(tmp_path, "FAKELIB/FAKEA", ITEM), ITEM)[0] != "cobol"


def test_a_file_with_an_extension_is_not_claimed_by_a_declaration(detector, tmp_path):
    declare(tmp_path, proc_grps, ["FAKELIB"])
    assert detector.focus(member(tmp_path, "FAKELIB/data.txt", ITEM), ITEM)[0] != "cobol"


def test_real_scan_resolves_qualified_and_extensionless_members_of_a_declared_library(tmp_path):
    """The census over an authored estate: every member is an extensionless file in a declared library, one a chain
    member that holds only a COPY, copied with `OF`, `IN` and unqualified. (A member name held by two libraries is
    resolved by name without a `--copy-libraries` declaration: a sibling gap, not asserted here.)"""
    repo = tmp_path / "fakeestate"
    declare(repo, proc_grps, ["FAKELIBA", "FAKELIBB"])
    (repo / "apps").mkdir(parents=True)
    copies = "       COPY ALPHAREC OF FAKELIBA.\n       COPY BETAREC in fakelibb.\n       COPY GAMMAREC.\n"
    (repo / "apps" / "MAINPG.cbl").write_text(PROGRAM.format(pid="MAINPG", copies=copies), encoding="utf-8")
    member(repo, "FAKELIBA/ALPHAREC", ITEM)
    member(repo, "FAKELIBB/BETAREC", CHAIN.replace("FAKEZ", "ALPHAREC"))
    member(repo, "FAKELIBB/GAMMAREC", ITEM)
    n = crc.census_repo(repo)
    assert n["members"] == 3
    assert n["agree"] == 3 and crc.disagreements(n) == 0, dict(n)
