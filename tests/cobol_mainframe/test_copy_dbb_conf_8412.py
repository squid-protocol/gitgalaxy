"""#8412: an IBM DBB (zAppBuild) `application-conf` names the copybook search order of a COBOL application in
`cobol_dependencySearch` (`search:[:copy]<root>/?path=<dir>/*.cpy;<dir2>/*.cpy` rules, directories relative to the
workspace). With no `--copy-libraries`, an unqualified COPY found in two directories resolves in the declared order.
Authored fixtures (invented names): the reader over the whole input class (the rule forms, variables, the three
property files, line continuations, scoped values, rules and entries that declare nothing) and real scans for the order."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import pytest

from gitgalaxy.standards.language_lens import declared_dirs_in_folder
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db

ITEM_A = "           05  FAKE-A  PIC X(1).\n"
ITEM_B = "           05  FAKE-B  PIC X(2).\n"
PROGRAM = (
    "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. MAINPG.\n       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n       01  REC.\n           COPY REC1.\n       PROCEDURE DIVISION.\n"
    "           GOBACK.\n"
)
APP = "FakeApp"


def write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def search(*dirs: str, root: str = "${workspace}/", kind: str = "") -> str:
    """One `search:` rule over workspace-relative directories (each given as a `?path=` mask)."""
    return f"search:{kind}{root}?path=" + ";".join(f"{APP}/{d}/*.cpy" for d in dirs)


def app_tree(tmp_path: Path, dirs: list[str], files: dict[str, str]) -> Path:
    """The application folder (named APP, inside a workspace folder) with its directories and conf files."""
    app = tmp_path / "ws" / APP
    for d in dirs:
        (app / d).mkdir(parents=True, exist_ok=True)
    for rel, text in files.items():
        write(app, rel, text)
    return app


def declared(app: Path) -> list[str]:
    return [Path(d).relative_to(app).as_posix() for d in declared_dirs_in_folder(str(app))]


def conf(text: str, name: str = "Cobol.properties") -> dict[str, str]:
    return {f"application-conf/{name}": text}


def test_the_search_rules_are_declared_in_the_order_written(tmp_path):
    app = app_tree(tmp_path, ["zz", "aa"], conf("cobol_dependencySearch=" + search("zz", "aa")))
    assert declared(app) == ["zz", "aa"]


@pytest.mark.parametrize(
    ("value", "expect"),
    [
        ("search:/u/build/ws/?path=FakeApp/b/*.cpy", ["b"]),  # an absolute workspace root is dropped
        ("search:[:copy]${workspace}/?path=${application}/b/*.cpy", ["b"]),  # variables
        ("search:${workspace}/?path=FakeApp/b/*.cpy;FakeApp/a/*.cpy", ["b", "a"]),  # `;` list in one rule
        ("search:${workspace}/?path=FakeApp/b/*.cpy,FakeApp/a/*.cpy", ["b", "a"]),  # `,` list
        ("search:${workspace}/?path=FakeApp/b/*.cpy search:${workspace}/?path=FakeApp/a/*.cpy", ["b", "a"]),
        ("search:${workspace}/?path=FAKEAPP/b/*.cpy", ["b"]),  # application name folds case
        ("search:${workspace}/?path=FakeApp/n/**/c/*.cpy", ["n/x/c", "n/y/c"]),  # a `**` glob expands
        ("search:${workspace}/?path=FakeApp\\b\\*.cpy", ["b"]),  # backslashes
        ("search:${workspace}/?path=FakeApp/b", ["b"]),  # no file mask: the directory itself
        ("search:${workspace}/?path=b/*.cpy", ["b"]),  # relative to the folder without the application prefix
    ],
)
def test_every_form_of_a_copy_search_rule_reads_to_its_directories(tmp_path, value, expect):
    app = app_tree(tmp_path, ["a", "b", "n/x/c", "n/y/c"], conf("cobol_dependencySearch=" + value))
    assert declared(app) == expect


@pytest.mark.parametrize(
    "value",
    [
        "search:[:LINK]${workspace}/?path=FakeApp/b/*.cpy",  # a link-edit rule, not a copybook rule
        "search:${workspace}/?file=FakeApp/b/REC1.cpy",  # a file rule names no directory
        "search:${workspace}/?path=${nothing}/b/*.cpy",  # an undefined variable
        "search:${workspace}/?path=FakeApp/../b/*.cpy;/b/*.cpy;../b/*.cpy",  # leaves the folder
        "FakeApp/b/*.cpy",  # not a search rule
        "search:${workspace}/?path=FakeApp/gone/*.cpy",  # a missing directory
        "",
    ],
    ids=["link", "file-rule", "variable", "escapes", "no-search", "missing", "empty"],
)
def test_rules_that_name_no_copy_directory_declare_nothing(tmp_path, value):
    app = app_tree(tmp_path, ["b"], conf("cobol_dependencySearch=" + value))
    assert declared(app) == []


def test_other_properties_and_other_languages_declare_nothing(tmp_path):
    text = "pli_dependencySearch=" + search("b") + "\nimpactSearch=" + search("b") + "\ncobol_cpyPDS=A.B.COPY\n"
    assert declared(app_tree(tmp_path, ["b"], conf(text))) == []


def test_a_properties_value_follows_java_syntax(tmp_path):
    text = (
        "# cobol_dependencySearch=" + search("b") + "\n"
        "! a comment\n"
        "dirs = FakeApp/c/*.cpy\n"
        "cobol_dependencySearch : search:${workspace}/?path=\\\n"
        "    FakeApp/a/*.cpy;\\\n"
        "    ${dirs}\n"
    )
    assert declared(app_tree(tmp_path, ["a", "b", "c"], conf(text))) == ["a", "c"]


def test_the_three_property_files_are_read_and_a_later_one_overrides(tmp_path):
    files = {
        "application-conf/application.properties": "cobol_dependencySearch=" + search("a"),
        "application-conf/COBOL.PROPERTIES": "cobol_dependencySearch=" + search("b"),  # file name folds case
    }
    assert declared(app_tree(tmp_path, ["a", "b"], files)) == ["b"]
    files = {"application-conf/application.properties": "cobol_dependencySearch=" + search("a")}
    assert declared(app_tree(tmp_path / "x", ["a", "b"], files)) == ["a"]
    files = {"application-conf/file.properties": "cobol_dependencySearch=" + search("a")}
    assert declared(app_tree(tmp_path / "y", ["a", "b"], files)) == ["a"]


def test_a_value_scoped_to_files_by_a_pattern_declares_nothing(tmp_path):
    text = "cobol_dependencySearch=" + search("a") + "::**/cobol/one.cbl\n"
    assert declared(app_tree(tmp_path, ["a"], conf(text, "file.properties"))) == []


def test_a_folder_with_no_application_conf_declares_nothing(tmp_path):
    assert declared(app_tree(tmp_path, ["a"], {})) == []
    assert declared(app_tree(tmp_path / "x", ["a"], {"application-conf": ""})) == []  # a file, not a directory


def test_an_unreadable_properties_file_declares_nothing(tmp_path):
    app = app_tree(tmp_path, ["a"], {})
    (app / "application-conf" / "Cobol.properties").mkdir(parents=True)  # a directory where the file should be
    assert declared(app) == []


def estate(tmp_path: Path, order: list[str], dirs: dict[str, str]) -> Path:
    repo = tmp_path / "fakeestate"
    write(repo, f"{APP}/cobol/MAINPG.cbl", PROGRAM)
    for rel, text in dirs.items():
        write(repo, f"{APP}/{rel}", text)
    write(repo, f"{APP}/application-conf/Cobol.properties", "cobol_dependencySearch=" + search(*order) + "\n")
    return repo


def edges_of(repo: Path, tmp: Path) -> set[str]:
    prog = f"{APP}/cobol/MAINPG.cbl"
    ir = load_galaxy_ir(scan_to_db(repo, tmp / "out"))
    return set(ir.copy_resolution(prog)["edges"].get(prog, ()))


FILES = {"q/REC1.cpy": ITEM_B, "p/REC1.cpy": ITEM_A}


@pytest.mark.parametrize(
    ("order", "winner"),
    [(["q", "p"], f"{APP}/q/REC1.cpy"), (["p", "q"], f"{APP}/p/REC1.cpy")],
    ids=["q-first", "p-first"],
)
def test_the_declared_order_decides_which_same_name_member_a_copy_reads(tmp_path, order, winner):
    assert edges_of(estate(tmp_path, order, FILES), tmp_path) == {winner}
