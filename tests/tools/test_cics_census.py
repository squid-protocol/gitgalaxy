"""cics_census: EXEC CICS option counts (names only), the burned / non-burned split from estate4_draw, the survey
runs and the before / after comparison. Fixture corpora under tmp_path; no corpus or translator needed."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cics_census as cc


def fixed(*code: str) -> str:
    """Fixed-format COBOL: sequence area 000100.., code from column 8; a line starting `*` is a comment (column 7)."""
    return "\n".join(f"{i * 100:06d}{c if c.startswith('*') else ' ' + c}" for i, c in enumerate(code, 1)) + "\n"


ASSIGN_PROG = fixed(
    "PROCEDURE DIVISION.",
    "    EXEC CICS ASSIGN APPLID(WS-APPLID OF WS-AREA)",
    "                     SYSID(WS-SYSID) RESP(WS-RESP)",
    "    END-EXEC.",
    "*   EXEC CICS ASSIGN USERID(WS-U) END-EXEC.",
    "    EXEC CICS ASSIGN STARTCODE(WS-SC) NOHANDLE END-EXEC.",
    "    EXEC CICS SEND TEXT FROM('A (B) C') LENGTH(5) ERASE END-EXEC.",
)


def corpus(root: Path, name: str, files: dict[str, str]) -> Path:
    d = root / name
    for rel, text in files.items():
        (d / rel).parent.mkdir(parents=True, exist_ok=True)
        (d / rel).write_text(text)
    return d


def test_top_level_words_skip_arguments_and_literals():
    words = cc.top_level_words("SEND TEXT FROM('A (B) C') LENGTH(LENGTH OF X) ERASE")
    assert words == ["SEND", "TEXT", "FROM", "LENGTH", "ERASE"]


def test_commands_read_the_code_area_and_skip_comments():
    cmds = cc.commands(ASSIGN_PROG)
    assert cmds[0] == ["ASSIGN", "APPLID", "SYSID", "RESP"]
    assert cmds[1] == ["ASSIGN", "STARTCODE", "NOHANDLE"]  # the commented USERID ASSIGN is not counted
    assert cc.options_of(cmds[0], ["ASSIGN"]) == ["APPLID", "SYSID"]
    assert cc.options_of(cmds[0], ["ASSIGN"], all_options=True) == ["APPLID", "SYSID", "RESP"]
    assert cc.options_of(cmds[2], cc.verb_words("send-text")) == ["FROM", "LENGTH", "ERASE"]
    assert cc.options_of(cmds[2], ["ASSIGN"]) is None


def test_pli_commands_end_at_the_semicolon_and_drop_sequence_numbers():
    pli = " EXEC CICS ASSIGN APPLID(A) /* USERID(U) */                                 00001890\n USERID(U);\n"
    assert cc.commands(pli, pli=True) == [["ASSIGN", "APPLID", "USERID"]]


def test_the_split_comes_from_estate4_draw():
    import estate4_draw

    assert cc.burned_names() == {n.lower() for n in estate4_draw.BURNED_NAMES}
    assert cc.is_burned("cics-genapp") and not cc.is_burned("cics-async-api-redbooks")
    assert "cics-async-api-redbooks" in cc.census_names() and "cics-genapp" not in cc.census_names()


def test_usage_counts_programs_per_option_split_burned(tmp_path):
    main, census = tmp_path / "main", tmp_path / "census"
    corpus(
        main,
        "cics-genapp",
        {"src/A.cbl": ASSIGN_PROG, "src/B.cbl": fixed("EXEC CICS RETURN END-EXEC."), "copy/C.cpy": ASSIGN_PROG},
    )  # a copybook is not a program
    corpus(main, "_scans", {"x.cbl": ASSIGN_PROG})  # tool directories are skipped
    corpus(census, "cics-async-api-redbooks", {"D.cbl": fixed("EXEC CICS ASSIGN STARTCODE(S) USERID(U) END-EXEC.")})
    uses = cc.usage([main, census], ["ASSIGN"])
    assert [(u.corpus, u.program, u.burned) for u in uses] == [
        ("cics-async-api-redbooks", "D.cbl", False),
        ("cics-genapp", "src/A.cbl", True),
    ]
    assert {o: (n, k) for o, n, k, _ in cc.totals(uses, "ASSIGN")} == {
        "STARTCODE": (2, 1),
        "APPLID": (1, 0),
        "SYSID": (1, 0),
        "USERID": (1, 1),
    }
    assert uses[1].commands["ASSIGN"] == 2


def test_usage_cli_prints_names_and_counts_only(tmp_path, capsys, monkeypatch):
    main, census = tmp_path / "main", tmp_path / "census"
    corpus(main, "zecs", {"Z.cbl": ASSIGN_PROG})
    corpus(census, "cics-java-recgen", {"R.cbl": fixed("EXEC CICS ASSIGN USERID(U) END-EXEC.")})
    corpus(census, "some-new-repo", {"N.cbl": fixed("EXEC CICS RETURN END-EXEC.")})
    monkeypatch.setenv(cc.CENSUS_ENV, str(census))
    assert cc.main(["usage", "ASSIGN", "--corpora", str(main)]) == 0
    out, err = capsys.readouterr()
    assert "2 COBOL programs (1 non-burned)" in out
    assert "WS-APPLID" not in out and "WS-AREA" not in out  # no source text
    assert "some-new-repo" in err and "burns it" in err  # not on the census list: warned
    assert cc.main(["usage", "ASSIGN", "--corpora", str(main), "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert {r["corpus"] for r in doc["programs"]} == {"zecs", "cics-java-recgen"}


def test_a_missing_census_root_is_a_clear_error(tmp_path, monkeypatch):
    monkeypatch.delenv(cc.CENSUS_ENV, raising=False)
    with pytest.raises(SystemExit) as e:
        cc.main(["usage", "ASSIGN", "--corpora", str(tmp_path)])
    assert cc.CENSUS_ENV in str(e.value) and "--no-census" in str(e.value)
    assert cc.main(["usage", "ASSIGN", "--corpora", str(tmp_path), "--no-census"]) == 0


def test_survey_runs_split_burned_local_and_census(tmp_path):
    main, census = tmp_path / "main", tmp_path / "census"
    for n in ("cics-genapp", "zecs", "dsf"):
        corpus(main, n, {"A.cbl": ASSIGN_PROG})
    for n in ("cics-async-api-redbooks", "zecs"):
        corpus(census, n, {"A.cbl": ASSIGN_PROG})
    runs = cc.survey_runs(main, census, None, None)
    assert runs == [
        ("b", main, ["cics-genapp", "zecs"]),
        ("nb-local", main, ["dsf"]),
        ("nb", census, ["cics-async-api-redbooks"]),
    ]  # zecs once, from the main root
    uses = [cc.ProgramUse("zecs", "A.cbl", True, {"ASSIGN": {"APPLID"}}, {"ASSIGN": 1})]
    assert cc.survey_runs(main, census, uses, None) == [("b", main, ["zecs"])]


def _survey(d: Path, rows: dict) -> None:
    d.mkdir(parents=True)
    (d / "survey.json").write_text(json.dumps(rows))


def test_compare_before_after(tmp_path, capsys):
    main, census, s = tmp_path / "main", tmp_path / "census", tmp_path / "s"
    corpus(main, "cics-genapp", {"src/A.cbl": ASSIGN_PROG, "src/B.cbl": fixed("EXEC CICS ASSIGN SYSID(S) END-EXEC.")})
    corpus(census, "cics-async-api-redbooks", {"D.cbl": fixed("EXEC CICS ASSIGN STARTCODE(S) END-EXEC.")})
    hole = "EXEC EXEC CICS: ASSIGN STARTCODE: option not modelled"
    _survey(
        s / "before-b",
        {
            "cics-genapp": [
                {"program": "src/A.cbl", "statements": 5, "translated": 4, "holes": [f"line 3: {hole}"]},
                {"program": "src/B.cbl", "statements": 2, "translated": 2, "holes": []},
            ]
        },
    )
    _survey(
        s / "before-nb",
        {
            "cics-async-api-redbooks": [
                {
                    "program": "D.cbl",
                    "statements": 3,
                    "translated": 2,
                    "holes": [f"line 9: {hole}", "line 10: READ GTEQ"],
                }
            ]
        },
    )
    _survey(
        s / "after-b",
        {
            "cics-genapp": [
                {"program": "src/A.cbl", "statements": 5, "translated": 5, "holes": []},
                {"program": "src/B.cbl", "error": "ParseError: /home/x/B.cbl line 1"},
            ]
        },
    )
    _survey(
        s / "after-nb",
        {
            "cics-async-api-redbooks": [
                {
                    "program": "D.cbl",
                    "statements": 3,
                    "translated": 2,
                    "holes": ["line 10: READ GTEQ", "line 12: READ GTEQ"],
                }
            ]
        },
    )
    uses = cc.usage([main, census], ["ASSIGN"])
    res = cc.compare_rows(uses, cc.load_surveys(s, "before"), cc.load_surveys(s, "after"), ["ASSIGN"])
    assert res["summary"] == {
        "programs": 3,
        "non_burned": 1,
        "whole_before": 1,
        "whole_after": 1,
        "whole_before_nb": 0,
        "whole_after_nb": 0,
        "missing_before": 0,
        "missing_after": 0,
        "verb_holes_before": 2,
        "verb_holes_after": 0,
    }
    d = next(r for r in res["rows"] if r["program"] == "D.cbl")
    assert d["holes_after"] == ["READ GTEQ"] and not d["burned"]  # deduplicated, line numbers stripped
    b = next(r for r in res["rows"] if r["program"] == "src/B.cbl")
    assert b["after"].startswith("ERROR") and "/home" not in b["after"]
    assert (
        cc.main(["compare", str(s), "--verb", "ASSIGN", "--corpora", str(main), "--census-corpora", str(census)]) == 0
    )
    assert "translated whole: 1 -> 1 (non-burned 0 -> 0)" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("hole", "key"),
    [
        ("line 3: EXEC EXEC CICS: ASSIGN STARTCODE: option not modelled", "EXEC CICS ASSIGN STARTCODE"),
        ("line 4: EXEC EXEC CICS: ASSIGN APPLID", "EXEC CICS ASSIGN APPLID"),
        ("line 5: EXEC EXEC CICS: EXEC CICS GETMAIN not modelled", "EXEC CICS GETMAIN"),
        (
            "line 6: EXEC EXEC CICS: RUN CHANNEL: option not modelled (RUN CHANNEL: the child's copy (#4270: later))",
            "EXEC CICS RUN CHANNEL",
        ),
        (
            "line 7: EXEC EXEC CICS: HANDLE CONDITION NOTFND(X-PARA): no such paragraph",
            "EXEC CICS HANDLE CONDITION NOTFND(…): no such paragraph",
        ),
        ("line 8: HOLE does not parse", "grammar: does not parse"),
        ("line 9: HOLE grammar node exit_statement", "grammar: grammar node exit_statement"),
        ("line 10: MOVE WS-ITEM-1: FILLER", "<name>: FILLER"),  # one class whatever the statement
        ("line 10: IF DIBSTAT: no such item", "<name>: no such item"),
        (
            "line 10: ENTRY ENTRY DLITCBL: an alternate entry point is not modelled",
            "ENTRY DLITCBL: an alternate entry point is not modelled",
        ),  # no hyphen, no digit: kept, it is the gap
        ("line 10: CALL CALL CBLTDLI", "CALL CBLTDLI"),
        (
            "line 10: COMPUTE FUNCTION NUMVAL in a floating-point expression (oracle_assumptions.md C6)",
            "COMPUTE FUNCTION NUMVAL in a floating-point expression",
        ),
        ("line 10: EXEC EXEC DLI", "EXEC DLI"),
        ("line 10: EXEC EXEC CICS", "EXEC CICS (no reason given)"),
        (
            "line 10: EXEC EXEC CICS: DEFINE COUNTER: named counters are not modelled",
            "EXEC CICS DEFINE COUNTER: named counters are not modelled",
        ),
        ("line 10: EXEC EXEC CICS: not a data area: Length of WS-Qarea", "EXEC CICS not a data area: Length of <name>"),
        (
            "line 10: EXEC EXEC CICS: no generated screen for map BNK1CCM",
            "EXEC CICS no generated screen for map <name>",
        ),
        (
            "line 10: EXEC EXEC CICS: Copaus0cCommarea.cdemoPaukeyPrevPg: a property the port cannot convert (List<String>)",
            "EXEC CICS <class>.<property>: a property the port cannot convert",
        ),
        ("line 11: EXEC EXEC SQL: WHENEVER 'X' (a later slice)", "EXEC SQL: WHENEVER '…'"),
    ],
)
def test_gap_key_strips_line_numbers_and_specifics(hole, key):
    assert cc.gap_key(hole) == key


def test_error_key_names_the_copybook_and_drops_paths():
    assert cc.error_key("LayoutError: NBLK-ACCT.cbl:137: national / DBCS text ('—', U+2014) is not modelled: the "
                        "translator reads a single-byte code page") == (
        "refused: LayoutError: national / DBCS text (…) is not modelled: the translator reads a single-byte code page"
    )  # fmt: skip
    assert cc.error_key("LayoutError: DATA DIVISION does not parse near expanded line(s) [21]") == (
        "refused: LayoutError: DATA DIVISION does not parse near expanded line(…)"
    )
    assert cc.error_key("CopyNotFound: /home/x/src/a.cbl:34: COPY BAQRI") == "missing copybook BAQRI"
    assert cc.error_key("ExprError: line 117: paragraph_header does not parse") == (
        "refused: ExprError: paragraph_header does not parse"
    )
    assert cc.error_key("ExprError: the PROCEDURE DIVISION does not parse at line 86") == (
        "refused: ExprError: the PROCEDURE DIVISION does not parse"
    )


def _row(program: str, *holes: str, error: str | None = None) -> dict:
    if error:
        return {"program": program, "error": error}
    return {"program": program, "statements": 9, "translated": 9 - len(holes), "holes": list(holes)}


def test_blockers_rank_gaps_by_programs_made_whole(tmp_path, capsys):
    getmain, applid = "line 1: EXEC EXEC CICS: EXEC CICS GETMAIN not modelled", "line 2: EXEC EXEC CICS: ASSIGN APPLID"
    grammar = "line 3: HOLE does not parse"
    s = tmp_path / "s"
    _survey(s / "before-b", {"cics-genapp": [
        _row("A.cbl"),  # whole
        _row("B.cbl", getmain, getmain.replace("line 1", "line 40")),  # GETMAIN only (twice: one class)
        _row("C.cbl", getmain, applid),  # one away
    ]})  # fmt: skip
    _survey(s / "before-nb", {"cics-async-api-redbooks": [
        _row("D.cbl", grammar),  # grammar only, non-burned
        _row("E.cbl", getmain, applid, grammar),  # three classes
        _row("F.cbl", error="CopyNotFound: /x/F.cbl:3: COPY BAQRI"),
        _row("G.cbl", getmain),  # not a CICS program: left out below
    ]})  # fmt: skip
    rows = cc.load_surveys(s, "before")
    res = cc.blockers(rows, only={k for k in rows if k[1] != "G.cbl"})
    assert (res["programs"], res["non_burned"], res["whole"], res["whole_non_burned"], res["refused"]) == (
        6,
        3,
        1,
        0,
        1,
    )
    assert res["histogram"] == {"0": 1, "1": 3, "2": 1, "3": 1}
    by = {g["gap"]: g for g in res["gaps"]}
    # only-gap programs first, non-burned ones break the tie, then one away, then touched
    assert [g["gap"] for g in res["gaps"]] == ["grammar: does not parse", "missing copybook BAQRI",
                                               "EXEC CICS GETMAIN", "EXEC CICS ASSIGN APPLID"]  # fmt: skip
    gm = by["EXEC CICS GETMAIN"]
    assert (gm["only"], gm["only_burned"], gm["only_non_burned"], gm["one_away"], gm["touched"]) == (1, 1, 0, 1, 3)
    assert (gm["touched_burned"], gm["touched_non_burned"]) == (2, 1)
    assert by["grammar: does not parse"]["only_non_burned"] == 1
    assert by["EXEC CICS ASSIGN APPLID"]["only"] == 0 and by["EXEC CICS ASSIGN APPLID"]["one_away"] == 1
    assert by["missing copybook BAQRI"]["refuses_program"] and not gm["refuses_program"]
    assert cc.blockers(rows)["programs"] == 7  # no filter: every surveyed program
    assert cc.main(["blockers", str(s), "--all-programs", "--no-census", "--corpora", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "translated whole: 1 / 7 (non-burned 0 / 4)" in out and "EXEC CICS GETMAIN" in out


def test_blockers_cli_keeps_the_cics_programs(tmp_path, capsys):
    main, s = tmp_path / "main", tmp_path / "s"
    corpus(main, "zecs", {"A.cbl": ASSIGN_PROG, "B.cbl": fixed("PROCEDURE DIVISION.", "    GOBACK.")})
    _survey(s / "before-b", {"zecs": [_row("A.cbl", "line 2: EXEC EXEC CICS: ASSIGN APPLID"), _row("B.cbl")]})
    assert cc.main(["blockers", str(s), "--corpora", str(main), "--no-census", "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert (doc["programs"], doc["whole"], doc["scope"]) == (1, 0, "programs with an EXEC CICS command")
    assert doc["gaps"][0]["gap"] == "EXEC CICS ASSIGN APPLID" and doc["gaps"][0]["only_burned"] == 1
    with pytest.raises(SystemExit):
        cc.main(["blockers", str(tmp_path / "nothing"), "--all-programs", "--no-census"])
