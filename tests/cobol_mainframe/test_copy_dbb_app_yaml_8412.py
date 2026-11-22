"""#8412: an IBM DBB 3.x zBuilder `dbb-app.yaml` names, in the `impactQueryPatterns` variable, the directories a COBOL
program's copybooks come from (`${APP_DIR_NAME}/copybook/*.cpy` under a `languageExt: cbl` entry). With no
`--copy-libraries`, an unqualified COPY found in two directories resolves in the declared order. Authored fixtures
(invented names): the reader over the whole input class and a real scan for the order."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import pytest

pytest.importorskip("yaml")

from gitgalaxy.standards.language_lens import declared_dirs_in_folder
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db

APP = "FakeApp"
PROGRAM = (
    "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. MAINPG.\n       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n       01  REC.\n           COPY REC1.\n       PROCEDURE DIVISION.\n"
    "           GOBACK.\n"
)


def yaml_text(patterns: list[str], ext: str = "cbl", task: str = "ImpactAnalysis", name: str = "impactQueryPatterns"):
    lines = "".join(f"                - {p}\n" for p in patterns)
    return (
        "version: 1.0.0\napplication:\n  name: FakeApp\n  tasks:\n"
        f"    - task: {task}\n      variables:\n        - name: {name}\n          value:\n"
        f"            - languageExt: {ext}\n              dependencyPatterns:\n{lines}"
    )


def write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def app_tree(tmp_path: Path, dirs: list[str], text: str | None) -> Path:
    app = tmp_path / "ws" / APP
    for d in dirs:
        (app / d).mkdir(parents=True, exist_ok=True)
    if text is not None:
        write(app, "dbb-app.yaml", text)
    return app


def declared(app: Path) -> list[str]:
    return [Path(d).relative_to(app).as_posix() for d in declared_dirs_in_folder(str(app))]


@pytest.mark.parametrize(
    ("patterns", "expect"),
    [
        (["${APP_DIR_NAME}/zz/*.cpy", "${APP_DIR_NAME}/aa/*.cpy"], ["zz", "aa"]),  # declaration order
        (
            ["${APP_DIR_NAME}/aa/*.cpy", "${APP_DIR_NAME}/bms/*.bms", "${APP_DIR_NAME}/cobol/*.cbl"],
            ["aa"],
        ),  # copybooks only
        (["FakeApp/aa/*.cpy"], ["aa"]),  # a literal application name
        (["FAKEAPP/aa/*.CPY"], ["aa"]),  # folds case
        (["${APP_DIR_NAME}/n/**/*.cpy"], ["n", "n/x"]),  # a recursive mask declares its base too
        (["${APP_DIR_NAME}/aa/*.copy", "${APP_DIR_NAME}/zz/*.cpb"], ["aa", "zz"]),  # other copybook extensions
        (["aa/*.cpy", "aa/*.cpy"], ["aa"]),  # a repeat is one directory
    ],
)
def test_every_form_of_a_dependency_pattern_reads_to_its_directories(tmp_path, patterns, expect):
    app = app_tree(tmp_path, ["aa", "zz", "bms", "cobol", "n/x"], yaml_text(patterns))
    assert declared(app) == expect


@pytest.mark.parametrize(
    "text",
    [
        yaml_text(["${APP_DIR_NAME}/aa/*.cpy"], ext="lnk"),  # a link card's dependencies, not a COBOL program's
        yaml_text(["${APP_DIR_NAME}/aa/*.cpy"], name="otherVariable"),
        yaml_text(["${APP_DIR_NAME}/${other}/*.cpy"]),  # an unresolved variable
        yaml_text(["${APP_DIR_NAME}/../aa/*.cpy", "/aa/*.cpy"]),  # leaves the folder
        yaml_text(["${APP_DIR_NAME}/gone/*.cpy"]),  # a missing directory
        yaml_text(["${APP_DIR_NAME}/aa"]),  # no file mask
        "application: [not, a, mapping\n",  # malformed
        "- just\n- a list\n",
        "",
    ],
    ids=["link", "other-var", "variable", "escapes", "missing", "no-mask", "malformed", "list", "empty"],
)
def test_entries_that_name_no_copy_directory_declare_nothing(tmp_path, text):
    assert declared(app_tree(tmp_path, ["aa"], text)) == []


def test_a_folder_with_no_dbb_app_yaml_declares_nothing(tmp_path):
    assert declared(app_tree(tmp_path, ["aa"], None)) == []


def estate(tmp_path: Path, order: list[str]) -> Path:
    repo = tmp_path / "fakeestate"
    write(repo, f"{APP}/cobol/MAINPG.cbl", PROGRAM)
    write(repo, f"{APP}/q/REC1.cpy", "           05  FAKE-B  PIC X(2).\n")
    write(repo, f"{APP}/p/REC1.cpy", "           05  FAKE-A  PIC X(1).\n")
    write(repo, f"{APP}/dbb-app.yaml", yaml_text([f"${{APP_DIR_NAME}}/{d}/*.cpy" for d in order]))
    return repo


@pytest.mark.parametrize(
    ("order", "winner"),
    [(["q", "p"], f"{APP}/q/REC1.cpy"), (["p", "q"], f"{APP}/p/REC1.cpy")],
    ids=["q-first", "p-first"],
)
def test_the_declared_order_decides_which_same_name_member_a_copy_reads(tmp_path, order, winner):
    prog = f"{APP}/cobol/MAINPG.cbl"
    ir = load_galaxy_ir(scan_to_db(estate(tmp_path, order), tmp_path / "out"))
    assert set(ir.copy_resolution(prog)["edges"].get(prog, ())) == {winner}
