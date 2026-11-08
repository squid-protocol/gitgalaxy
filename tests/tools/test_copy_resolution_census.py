"""#8111: the copybook-resolution census (engine resolver vs plain file search), counts only."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import copy_resolution_census as crc  # noqa: E402

PROGRAM = (
    "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. MAINPG.\n       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n{copies}       PROCEDURE DIVISION.\n           GOBACK.\n"
)
ITEM = "           05  X   PIC X(8).\n"
SECRET = "zzsecretrepo"


def build(base: Path, copies: str, members: dict[str, str]) -> Path:
    repo = base / SECRET
    (repo / "apps").mkdir(parents=True)
    (repo / "apps" / "MAINPG.cbl").write_text(PROGRAM.format(copies=copies), encoding="utf-8")
    for rel, text in members.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    return repo


def edges_of(*members: str):
    """A stand-in engine that resolves exactly `members` (repo-relative files) for the program."""
    return lambda repo: ({"apps/MAINPG.cbl": {m: set() for m in members}}, set())


def test_classes_are_counted_apart(tmp_path):
    repo = build(
        tmp_path,
        "       COPY ALPHA.\n       COPY BETA.\n       COPY GHOST.\n       COPY GAMMA.\n",
        {"lib/alpha.cpy": ITEM, "lib/BETA": ITEM, "lib/GAMMA.cpy": ITEM, "lib/GAMMA.cbl": ITEM},
    )
    n = crc.census_repo(repo, edges_of("lib/alpha.cpy"))
    assert (n["members"], n["agree"], n["miss"], n["neither"], n["different"]) == (4, 1, 1, 1, 0)
    assert n["ambiguous"] == 1  # GAMMA: a copybook and a program of the name, no edge
    assert crc.disagreements(n) == 1


def test_exec_sql_include_and_commented_copy(tmp_path):
    repo = build(
        tmp_path,
        "      * COPY NOTREAL.\n       EXEC SQL INCLUDE SQLINC END-EXEC.\n",
        {"lib/sqlinc.cpy": ITEM, "lib/NOTREAL.cpy": ITEM},
    )
    assert crc._members(PROGRAM.format(copies="      * COPY NOTREAL.\n       EXEC SQL INCLUDE SQLINC END-EXEC.\n")) == {
        "SQLINC"
    }
    n = crc.census_repo(repo, lambda r: ({}, set()))
    assert (n["members"], n["miss"]) == (1, 1)


def test_engine_gap_counts_as_a_miss_even_with_an_edge(tmp_path):
    repo = build(tmp_path, "       COPY ALPHA.\n", {"lib/ALPHA.cpy": ITEM})
    n = crc.census_repo(repo, lambda r: ({"apps/MAINPG.cbl": {"lib/ALPHA.cpy": set()}}, {("apps/MAINPG.cbl", "ALPHA")}))
    assert n["miss"] == 1


def test_a_program_picked_over_the_copybook_is_different(tmp_path):
    repo = build(
        tmp_path,
        "       COPY ACCTCTRL.\n",
        {"lib/ACCTCTRL.cpy": ITEM, "src/ACCTCTRL.cbl": PROGRAM.format(copies="").replace("MAINPG", "ACCTCTRL")},
    )
    n = crc.census_repo(repo, edges_of("src/ACCTCTRL.cbl"))
    assert (n["different"], n["miss"], n["agree"]) == (1, 0, 0)


def test_render_names_nothing(tmp_path):
    repo = build(tmp_path, "       COPY ALPHA.\n", {"lib/ALPHA.cpy": ITEM})
    line = crc.render(crc.census_repo(repo, edges_of("lib/ALPHA.cpy")), 1)
    assert line == "repos 1, members 1, agree 1, miss 0, ambiguous 0, different 0, neither 0"
    assert SECRET not in line and "ALPHA" not in line


def test_excluded_repos_are_refused_and_burned_are_not():
    import equivalence_env as ee

    cand = sorted({n.split("/")[-1] for n in ee.candidate_names()})
    excluded = crc.excluded_names()
    if cand:
        assert all(n in excluded for n in cand)
        with pytest.raises(SystemExit):
            crc.check_allowed(Path("/x") / cand[0])
    for burned in ee.burned_names():
        assert burned not in excluded
    crc.check_allowed(Path("/x/some-fixture"))


def test_run_roots_skips_an_excluded_name(tmp_path, monkeypatch):
    build(tmp_path / "root", "       COPY ALPHA.\n", {"lib/alpha.cpy": ITEM})
    seen: list[str] = []

    def engine(repo):
        seen.append(repo.name)
        return {}, set()

    monkeypatch.setattr(crc, "excluded_names", lambda: {SECRET})
    total, repos = crc.run_roots([tmp_path / "root"], engine)
    assert (repos, seen, total["members"]) == (0, [], 0)
    monkeypatch.setattr(crc, "excluded_names", lambda: set())
    total, repos = crc.run_roots([tmp_path / "root"], engine)
    assert (repos, seen, total["miss"]) == (1, [SECRET], 1)


@pytest.fixture(scope="module")
def scanned(tmp_path_factory):
    """One real engine scan of an authored fixture: every shape of member the resolver must find."""
    base = tmp_path_factory.mktemp("copy_census")
    copies = (
        "".join(f"       COPY {m}.\n" for m in ("LOWER1", "UPPER2", "NOEXT3", "NESTED4"))
        + "       EXEC SQL INCLUDE SQLINC7 END-EXEC.\n       COPY GHOST6.\n"
    )
    repo = build(
        base,
        copies,
        {
            "apps/lower1.cpy": ITEM,
            "cpy/UPPER2.CPY": ITEM,
            "cpy/NOEXT3": ITEM,
            "cpy/inc/nested4.copy": ITEM,
            "lib/SQLINC7.cpy": ITEM,
        },
    )
    return crc.census_repo(repo)


def test_real_engine_resolves_case_extension_and_nesting(scanned):
    assert scanned["members"] == 6
    assert scanned["miss"] == 0 and scanned["different"] == 0
    assert scanned["agree"] == 5 and scanned["neither"] == 1


GROUP = "       01  REC-A.\n" + ITEM + "           05  Y   PIC 9(4).\n"


def test_real_engine_extensionless_include_and_mixed_case_copy(tmp_path):
    """EXEC SQL INCLUDE of an extensionless member, and a mixed-case COPY of one, in ordinary directories."""
    copies = "       EXEC SQL INCLUDE sqlnoext END-EXEC.\n       COPY MixedNoExt.\n"
    repo = build(tmp_path, copies, {"shared/SQLNOEXT": GROUP, "shared/mixednoext": GROUP})
    n = crc.census_repo(repo)
    assert n["members"] == 2
    assert crc.disagreements(n) == 0 and n["agree"] == 2
