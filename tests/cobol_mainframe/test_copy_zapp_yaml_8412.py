"""#8412: a Z Open Editor `zapp.yaml` names the SYSLIB order of a COBOL estate (`propertyGroups[].libraries[]`,
`type: local`, `locations` globs). With no `--copy-libraries`, an unqualified COPY found in two directories resolves
in the declared order instead of falling to the default resolver. Authored fixtures (invented names): the reader over
the whole class (glob forms, declaration order, nearest folder, entries that declare nothing, a malformed file) and
real scans for the order."""

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("yaml")  # the `yaml` extra

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from gitgalaxy.standards.language_lens import declared_dirs_in_folder, named_zapp_dirs_in_folder
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db

ITEM_A = "           05  FAKE-A  PIC X(1).\n"
ITEM_B = "           05  FAKE-B  PIC X(2).\n"
PROGRAM = (
    "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. MAINPG.\n       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n       01  REC.\n           COPY REC1.\n       PROCEDURE DIVISION.\n"
    "           GOBACK.\n"
)


def zapp(*groups: tuple[str, list[tuple[str, str, list[str]]]]) -> str:
    """A zapp.yaml text: groups of (language, [(library name, type, locations)])."""
    lines = ["name: fake", "propertyGroups:"]
    for language, libs in groups:
        lines += ["  - name: g", f"    language: {language}", "    libraries:"]
        for name, kind, locs in libs:
            lines += [f"      - name: {name}", f"        type: {kind}", "        locations:"]
            lines += [f"          - {json.dumps(loc)}" for loc in locs]
    return "\n".join(lines) + "\n"


def write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def tree(root: Path, dirs: list[str], yaml_text: str, at: str = "zapp.yaml") -> Path:
    for d in dirs:
        (root / d).mkdir(parents=True, exist_ok=True)
    write(root, at, yaml_text)
    return root


def declared(root: Path, at: str = "") -> list[str]:
    base = root / at if at else root
    return [Path(d).relative_to(base).as_posix() for d in declared_dirs_in_folder(str(base))]


def cobol(*locs: str) -> str:
    return zapp(("cobol", [("syslib", "local", list(locs))]))


def test_plain_directories_are_declared_in_the_order_written(tmp_path):
    tree(tmp_path, ["zz/LIBB", "aa/LIBA"], cobol("zz/LIBB", "aa/LIBA"))
    assert declared(tmp_path) == ["zz/LIBB", "aa/LIBA"]


@pytest.mark.parametrize(
    ("glob", "expect"),
    [
        ("**/COPYBOOK", ["COPYBOOK", "a/COPYBOOK", "a/b/copybook"]),  # any depth, case-folded, sorted
        ("a/*", ["a/COPYBOOK", "a/b"]),  # one level only
        ("a/COPY?OOK", ["a/COPYBOOK"]),
        ("**/nothing", []),
    ],
)
def test_a_glob_expands_over_the_directories_of_the_folder(tmp_path, glob, expect):
    tree(tmp_path, ["COPYBOOK", "a/COPYBOOK", "a/b/copybook", "other"], cobol(glob))
    assert declared(tmp_path) == expect


def test_every_syslib_entry_of_a_cobol_group_counts_in_order_and_named_libraries_do_not(tmp_path):
    text = zapp(
        ("cobol", [("syslib", "local", ["d1"]), ("MYLIB", "local", ["d2"]), ("SYSLIB", "local", ["d3"])]),
    )
    tree(tmp_path, ["d1", "d2", "d3"], text)
    assert declared(tmp_path) == ["d1", "d3"]  # an unqualified COPY never searches MYLIB
    assert {k: [Path(d).name for d in v] for k, v in named_zapp_dirs_in_folder(str(tmp_path)).items()} == {
        "MYLIB": ["d2"]
    }


@pytest.mark.parametrize(
    "text",
    [
        zapp(("cobol", [("syslib", "mvs", ["d1", "HLQ.SAMPLE.COPY"])])),  # a data set, not a directory
        zapp(("pl1", [("syslib", "local", ["d1"])])),  # another language's includes
        zapp(("cobol", [("syslib", "local", ["${HLQ}/d1", "${zopeneditor.workspaceFolder}/d1"])])),  # variables
        zapp(("cobol", [("syslib", "local", ["../d1", "d1/../../d1", "/d1"])])),  # leaves the folder
        "propertyGroups: [unclosed\n",  # malformed
        "name: fake\n",  # no groups
        "propertyGroups:\n  - libraries: 3\n    language: cobol\n",  # the wrong shape
    ],
    ids=["mvs", "pl1", "variables", "escapes", "malformed", "no-groups", "wrong-shape"],
)
def test_entries_that_name_no_local_directory_declare_nothing(tmp_path, text):
    tree(tmp_path, ["d1"], text)
    assert declared(tmp_path) == []


def test_a_missing_directory_declares_nothing(tmp_path):
    tree(tmp_path, ["real"], cobol("gone", "real"))
    assert declared(tmp_path) == ["real"]


def test_a_directory_named_twice_is_declared_once(tmp_path):
    tree(tmp_path, ["a/LIBA"], cobol("a/LIBA", "**/LIBA"))
    assert declared(tmp_path) == ["a/LIBA"]


def estate(tmp_path: Path, order: list[str], dirs: dict[str, str]) -> Path:
    repo = tmp_path / "fakeestate"
    write(repo, "apps/MAINPG.cbl", PROGRAM)
    for rel, text in dirs.items():
        write(repo, rel, text)
    write(repo, "zapp.yaml", cobol(*order))
    return repo


def edges_of(repo: Path, tmp: Path) -> set[str]:
    ir = load_galaxy_ir(scan_to_db(repo, tmp / "out"))
    return set(ir.copy_resolution("apps/MAINPG.cbl")["edges"].get("apps/MAINPG.cbl", ()))


FILES = {"q/LIBQ/REC1.cpy": ITEM_B, "p/LIBP/REC1.cpy": ITEM_A}


@pytest.mark.parametrize(
    ("order", "winner"),
    [
        (["q/LIBQ", "p/LIBP"], "q/LIBQ/REC1.cpy"),
        (["p/LIBP", "q/LIBQ"], "p/LIBP/REC1.cpy"),
        (["**/LIBQ"], "q/LIBQ/REC1.cpy"),
    ],
    ids=["q-first", "p-first", "glob"],
)
def test_the_declared_order_decides_which_same_name_member_a_copy_reads(tmp_path, order, winner):
    repo = estate(tmp_path, order, FILES)
    assert edges_of(repo, tmp_path) == {winner}


def test_a_nearer_zapp_yaml_governs_its_folder_alone(tmp_path):
    repo = estate(tmp_path, ["p/LIBP"], FILES)
    write(repo, "apps/zapp.yaml", cobol("local"))
    write(repo, "apps/local/REC1.cpy", ITEM_B)
    assert edges_of(repo, tmp_path) == {"apps/local/REC1.cpy"}


def test_a_nearer_zapp_yaml_that_names_no_directory_does_not_hand_over_to_the_root_one(tmp_path):
    """A multi-root sample names workspace folders (`cust`), not directories: the root's libraries must not apply."""
    nearer = estate(tmp_path / "n", ["p/LIBP"], FILES)
    write(nearer, "apps/zapp.yaml", cobol("cust", "trans"))
    plain = estate(tmp_path / "d", ["p/LIBP"], FILES)
    (plain / "zapp.yaml").unlink()  # the default resolver's answer, with no declaration at all
    assert edges_of(nearer, tmp_path / "n") == edges_of(plain, tmp_path / "d")


NAMED_PROGRAM = PROGRAM.replace("COPY REC1.", "COPY REC1 IN MYLIB.")


def named_estate(tmp_path: Path, named: list[str], syslib: list[str]) -> Path:
    repo = tmp_path / "fakeestate"
    write(repo, "apps/MAINPG.cbl", NAMED_PROGRAM)
    write(repo, "q/LIBQ/REC1.cpy", ITEM_B)
    write(repo, "p/LIBP/REC1.cpy", ITEM_A)
    text = zapp(("cobol", [("syslib", "local", syslib), ("MYLIB", "local", named)]))
    write(repo, "zapp.yaml", text)
    return repo


@pytest.mark.parametrize(
    ("named", "syslib", "winner"),
    [
        (["p/LIBP"], ["q/LIBQ"], "p/LIBP/REC1.cpy"),  # `IN MYLIB` reads MYLIB's directory, not the SYSLIB winner
        (["q/LIBQ"], ["p/LIBP"], "q/LIBQ/REC1.cpy"),
        (["**/LIBP", "q/LIBQ"], [], "p/LIBP/REC1.cpy"),  # the first named directory holding the member wins
        (["q/LIBQ", "**/LIBP"], [], "q/LIBQ/REC1.cpy"),
    ],
    ids=["p-named", "q-named", "glob-first", "glob-second"],
)
def test_copy_in_a_named_library_reads_the_directories_the_zapp_yaml_names_it(tmp_path, named, syslib, winner):
    repo = named_estate(tmp_path, named, syslib)
    assert edges_of(repo, tmp_path) == {winner}


def test_a_named_library_the_zapp_yaml_does_not_declare_leaves_the_copy_to_the_default_resolver(tmp_path):
    repo = named_estate(tmp_path / "n", ["p/LIBP"], ["q/LIBQ"])
    write(repo, "zapp.yaml", zapp(("cobol", [("syslib", "local", ["q/LIBQ"])])))
    (repo / "p/LIBP/REC1.cpy").unlink()
    assert edges_of(repo, tmp_path / "n") == {"q/LIBQ/REC1.cpy"}  # the one candidate; no declaration, no loss
