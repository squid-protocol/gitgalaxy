"""#8111 slice 6: with no `--copy-libraries`, `COPY x OF lib` reads the directory named `lib`, and the directories a
workspace declares (`.cobolplugin/proc_grps.json`, `.vscode/settings.json`) are searched first for an unqualified COPY.
Authored fixtures (invented names), through a real scan, over the whole class: qualifier case, member-name case, any
extension or none, a qualifier no directory carries, two directories of one name, both declaration files."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db

ITEM_A = "           05  FAKE-A  PIC X(1).\n"
ITEM_B = "           05  FAKE-B  PIC X(2).\n"
PROGRAM = (
    "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. MAINPG.\n       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n       01  REC.\n{copies}       PROCEDURE DIVISION.\n           GOBACK.\n"
)


def write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def edges_of(repo: Path, tmp: Path, importer: str = "apps/MAINPG.cbl") -> set[str]:
    ir = load_galaxy_ir(scan_to_db(repo, tmp / "out"))
    return set(ir.copy_resolution(importer)["edges"].get(importer, ()))


def estate(tmp_path: Path, copies: str, files: dict[str, str], decl: tuple[str, str] | None = None) -> Path:
    repo = tmp_path / "fakeestate"
    write(repo, "apps/MAINPG.cbl", PROGRAM.format(copies=copies))
    for rel, text in files.items():
        write(repo, rel, text)
    if decl:
        write(repo, *decl)
    return repo


@pytest.mark.parametrize("qual", ["LIBA", "liba", "LibA"])
@pytest.mark.parametrize(("member_file", "ext"), [("REC1", ".cpy"), ("rec1", ".CPY"), ("Rec1", "")])
@pytest.mark.parametrize("keyword", ["OF", "IN"])
def test_a_qualifier_reads_the_directory_of_that_name(tmp_path, qual, member_file, ext, keyword):
    files = {f"z/LIBB/{member_file}{ext}": ITEM_B, f"a/LIBA/{member_file}{ext}": ITEM_A}
    if not ext:  # an extensionless member is COBOL by the COBOL files beside it (slice 5 covers declared libraries)
        files |= {"z/LIBB/PADB.cpy": ITEM_B, "a/LIBA/PADA.cpy": ITEM_A}
    repo = estate(tmp_path, f"       COPY REC1 {keyword} {qual}.\n", files)
    # the other directory sorts after it in one case and before it in another: the qualifier alone decides
    assert edges_of(repo, tmp_path) == {f"a/LIBA/{member_file}{ext}"}


def test_the_other_library_is_chosen_by_its_own_qualifier(tmp_path):
    repo = estate(tmp_path, "       COPY REC1 OF LIBB.\n", {"z/LIBB/REC1.cpy": ITEM_B, "a/LIBA/REC1.cpy": ITEM_A})
    assert edges_of(repo, tmp_path) == {"z/LIBB/REC1.cpy"}


@pytest.mark.parametrize(
    "files",
    [
        {"only/LIBZ/REC1.cpy": ITEM_A},  # the qualifier names no directory: the default resolver still finds it
        {"x/LIBA/REC1.cpy": ITEM_A, "y/LIBA/REC1.cpy": ITEM_B},  # two directories of one name: left to the default
    ],
    ids=["no-such-directory", "two-directories-one-name"],
)
def test_an_unmatched_or_ambiguous_qualifier_falls_back_to_the_default_resolver(tmp_path, files):
    repo = estate(tmp_path, "       COPY REC1 OF LIBA.\n", files)
    default = estate(tmp_path / "d", "       COPY REC1.\n", files)
    assert edges_of(repo, tmp_path) == edges_of(default, tmp_path / "d")


DECLS = [
    ("proc_grps", lambda libs: (".cobolplugin/proc_grps.json", json.dumps({"pgroups": [{"name": "P", "libs": libs}]}))),
    (
        "settings",
        lambda libs: (
            ".vscode/settings.json",
            '{\n // note\n "cobol-lsp.cpy-manager.paths-local": ' + json.dumps(libs) + "\n}\n",
        ),
    ),
]


@pytest.mark.parametrize(("kind", "maker"), DECLS, ids=[d[0] for d in DECLS])
def test_a_declared_directory_is_searched_first_for_an_unqualified_copy(tmp_path, kind, maker):
    files = {"a/OTHER/REC1.cpy": ITEM_B, "decl/LIBD/REC1.cpy": ITEM_A}
    repo = estate(tmp_path, "       COPY REC1.\n", files, maker(["decl/LIBD"]))
    assert edges_of(repo, tmp_path) == {"decl/LIBD/REC1.cpy"}


def test_a_malformed_or_absolute_declaration_changes_nothing(tmp_path):
    files = {"a/OTHER/REC1.cpy": ITEM_B}
    bad = estate(tmp_path / "b", "       COPY REC1.\n", files, (".cobolplugin/proc_grps.json", "{not json"))
    absolute = estate(
        tmp_path / "c",
        "       COPY REC1.\n",
        files,
        (".vscode/settings.json", json.dumps({"cobol-lsp.cpy-manager.paths-local": ["/etc"]})),
    )
    assert edges_of(bad, tmp_path / "b") == {"a/OTHER/REC1.cpy"}
    assert edges_of(absolute, tmp_path / "c") == {"a/OTHER/REC1.cpy"}


def test_exec_sql_include_has_no_qualifier_and_resolves_as_before(tmp_path):
    repo = estate(
        tmp_path,
        "       EXEC SQL INCLUDE REC1 END-EXEC.\n",
        {"a/LIBA/REC1.cpy": ITEM_A},
    )
    assert edges_of(repo, tmp_path) == {"a/LIBA/REC1.cpy"}
