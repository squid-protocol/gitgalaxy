"""#5158: the census and the det survey count CICS Assembler / macro-level assembler members (.asm / .mac ...) with the
COBOL programs, refused by name as the det translator refuses them; macro tables, BMS map sources and plain assembler
are no row. Fixture corpora under tmp_path."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")  # det source (the refusal text comes from it)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cics_census as cc  # noqa: E402
import det_survey as ds  # noqa: E402

from gitgalaxy.core import cics_macro_level as ML  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "cics_macro_level"
SUFFIXES = sorted(ML.ASSEMBLER_SUFFIXES)


def corpus(root: Path, name: str, members: dict[str, str]) -> Path:
    """A corpus of fixture members: {relative path: fixture file name}."""
    d = root / name
    for rel, fixture in members.items():
        (d / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(FIXTURES / fixture, d / rel)
    return d


@pytest.mark.parametrize("suffix", [*SUFFIXES, *(s.upper() for s in SUFFIXES)])
@pytest.mark.parametrize(
    ("fixture", "key"),
    [("MACROASM.asm", "refused: macro-level CICS"), ("CMDASM.asm", "refused: CICS Assembler")],
)
def test_every_assembler_suffix_is_a_refused_row_in_its_family(tmp_path, suffix, fixture, key):
    c = corpus(tmp_path, "estate", {f"src/PROG{suffix}": fixture})
    (row,) = ds.assembler_rows(c)
    assert row["program"] == f"src/PROG{suffix}" and row["kind"] == "assembler"
    assert row["error"].startswith("MacroLevelCics: ")
    assert cc.error_key(row["error"]) == key
    assert cc.gap_classes(row) == {key}


@pytest.mark.parametrize("fixture", ["DFHFCT.asm", "MAPSET.asm", "PLAIN.asm"])
def test_a_macro_table_a_map_and_plain_assembler_are_no_row(tmp_path, fixture):
    assert ds.assembler_rows(corpus(tmp_path, "estate", {"T.asm": fixture, "T.mac": fixture})) == []


def test_cobol_members_other_suffixes_and_git_are_not_assembler_rows(tmp_path):
    c = corpus(
        tmp_path,
        "estate",
        {
            "MACROCBL.cbl": "MACROCBL.cbl",  # a COBOL member: det refuses it itself, the COBOL pass owns it
            "NOTES.txt": "MACROASM.asm",
            "MACROASM.asm.bak": "MACROASM.asm",
            ".git/hooks/X.asm": "MACROASM.asm",
        },
    )
    assert ds.assembler_rows(c) == []


def test_only_limits_the_rows_to_the_named_members(tmp_path):
    c = corpus(tmp_path, "estate", {"A.asm": "MACROASM.asm", "sub/B.mac": "CMDASM.asm"})
    assert [r["program"] for r in ds.assembler_rows(c)] == ["A.asm", "sub/B.mac"]
    assert [r["program"] for r in ds.assembler_rows(c, {"sub/B.mac"})] == ["sub/B.mac"]


def test_the_census_counts_assembler_members_as_cics_programs_and_ranks_their_family(tmp_path):
    main = tmp_path / "main"
    corpus(main, "zecs", {"A.asm": "CMDASM.asm", "B.mac": "MACROASM.asm", "T.asm": "DFHFCT.asm", "C.cbl": "CSACBL.cbl"})
    assert cc.cics_programs([main]) == {("zecs", "A.asm"), ("zecs", "B.mac"), ("zecs", "C.cbl")}  # C.cbl: EXEC CICS
    rows = {("zecs", r["program"]): r for r in ds.assembler_rows(main / "zecs")}
    res = cc.blockers(rows)
    by = {g["gap"]: g for g in res["gaps"]}
    assert set(by) == {"refused: CICS Assembler", "refused: macro-level CICS"}
    assert all(g["refuses_program"] and g["only"] == 1 for g in by.values())
    assert (res["programs"], res["whole"], res["refused"]) == (2, 0, 2)


def test_the_usage_count_stays_cobol_only(tmp_path):
    main = tmp_path / "main"
    corpus(main, "zecs", {"A.asm": "CMDASM.asm"})
    assert cc.usage([main], ["return"]) == []
