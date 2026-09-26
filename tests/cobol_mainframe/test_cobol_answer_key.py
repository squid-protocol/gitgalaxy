"""
#3210: the COBOL modernization answer key (tests/cobol_mainframe/answer_key/) and
the draft/score tool that builds and uses it (tests/tools/cobol_answer_key.py).

The key files are checked for integrity without the corpora. The draft rules are
pinned on tiny fixtures, one per shape that decides reachability or resolution on
the real corpora -- including every shape the first draft got wrong.
"""

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import cobol_answer_key as ak  # noqa: E402

KEY_DIR = Path(__file__).resolve().parent / "answer_key"
KEYS = sorted(KEY_DIR.glob("*.json"))


# ==============================================================================
# The committed keys
# ==============================================================================
def test_every_pinned_corpus_has_a_key():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    import mainframe_corpus as mc

    corpora = mc.load_manifest()
    assert all(c.get("answer_key") for c in corpora), "a pinned corpus without a key is not ground truth"
    assert {p.stem for p in KEYS} == {c["name"] for c in corpora}


@pytest.mark.parametrize("key_path", KEYS, ids=lambda p: p.stem)
def test_key_integrity(key_path):
    key = json.loads(key_path.read_text(encoding="utf-8"))
    assert key["schema_version"] == ak.SCHEMA_VERSION
    assert re.fullmatch(r"[0-9a-f]{40}", key["ref"]), "pin the corpus to a full commit"
    assert key["programs"]
    for rel, prog in key["programs"].items():
        where = f"{key_path.stem}:{rel}"
        v = prog["verification"]
        assert v["status"] == "validated", f"{where} is still a draft"
        assert v["by"] and v["at"]
        assert v.get("tier") in ak.TIERS, f"{where}: verification.tier must be one of {ak.TIERS}"
        if v["tier"] == "cross_verified":
            assert v.get("cross_by"), f"{where}: cross_verified needs cross_by (the second model)"
        if v["tier"] == "human_signed":
            assert v.get("signed_by"), f"{where}: human_signed needs signed_by"
        names = [u["name"] for u in prog["units"]]
        # A duplicate paragraph name is legal COBOL while it is never referenced
        # (CardDemo COACTVWC); the key must declare it rather than carry it silently.
        dupes = sorted({n for n in names if names.count(n) > 1})
        assert dupes == sorted(v.get("duplicate_units", [])), f"{where}: undeclared duplicate unit {dupes}"
        for name, verdict in prog["dead"].items():
            assert name in names, f"{where}: dead {name} is not a unit"
            assert verdict["reason"] and isinstance(verdict["trivial"], bool)
        for cb in prog["copybooks"]:
            assert cb["resolves_to"] or cb["why"], f"{where}: unresolved {cb['name']} without a reason"
            assert not (cb["resolves_to"] or "").lower().endswith((".cbl", ".cob")), "a COPY never means a program"
        for f in prog["files"]:
            assert set(f["modes"]) <= {"INPUT", "OUTPUT", "I-O", "EXTEND"}


def test_cbsa_key_carries_the_verified_findings():
    """The dead logic verified by hand on CBSA; a regenerated key that loses it is wrong."""
    key = json.loads((KEY_DIR / "cics-banking-sample-application-cbsa.json").read_text(encoding="utf-8"))
    progs = key["programs"]
    real_dead = {
        (Path(rel).stem, name)
        for rel, p in progs.items()
        for name, v in p["dead"].items()
        if not v["trivial"] and v["reason"].startswith("section")
    }
    assert real_dead == {
        ("BANKDATA", "CALC-DAY-OF-WEEK"),
        ("ACCTCTRL", "POPULATE-TIME-DATE"),
        ("CUSTCTRL", "POPULATE-TIME-DATE"),
        ("UPDACC", "POPULATE-TIME-DATE"),
        ("UPDCUST", "POPULATE-TIME-DATE"),
    }
    # Abend handlers registered with EXEC CICS HANDLE ABEND LABEL(...) are live.
    assert "ABEND-HANDLING" not in progs["src/base/cobol_src/INQACC.cbl"]["dead"]
    assert progs["src/base/cobol_src/BANKDATA.cbl"]["files"] == [
        {"internal": "CUSTOMER-FILE", "assign": "VSAM", "dd": "VSAM", "modes": ["OUTPUT"]}
    ]


# ==============================================================================
# Draft rules
# ==============================================================================
def _program(tmp_path, procedure, data="", name="PROG.cbl", extra_id=""):
    lines = [
        "       IDENTIFICATION DIVISION.",
        "       PROGRAM-ID. PROG.",
        *extra_id.splitlines(),
        "       DATA DIVISION.",
        "       WORKING-STORAGE SECTION.",
        *data.splitlines(),
        "       PROCEDURE DIVISION.",
        *procedure.splitlines(),
    ]
    path = tmp_path / name
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _reach(path):
    units = ak._units(ak.Source(path))
    return [u["name"] for u in units if u["name"]], ak.reachability(units)


def test_area_b_continuation_is_not_a_header(tmp_path):
    names, _ = _reach(
        _program(
            tmp_path,
            "       MAIN-PARA.\n           DISPLAY 'TIME = '\n                   CURRENT-SECOND.\n           GOBACK.\n",
        )
    )
    assert names == ["MAIN-PARA"]


def test_perform_goto_and_fall_through(tmp_path):
    names, why = _reach(
        _program(
            tmp_path,
            "       MAIN-PARA.\n"
            "           PERFORM A-PARA THRU B-PARA.\n"
            "           GO TO C-PARA.\n"
            "       A-PARA.\n"
            "           DISPLAY 'A'.\n"
            "       B-PARA.\n"
            "           DISPLAY 'B'.\n"
            "       C-PARA.\n"
            "           STOP RUN.\n"
            "       D-PARA.\n"
            "           DISPLAY 'NEVER'.\n",
        )
    )
    assert set(why) == {"MAIN-PARA", "A-PARA", "B-PARA", "C-PARA"}
    assert why["B-PARA"] == "fall-through from A-PARA"
    assert "D-PARA" in names and "D-PARA" not in why


def test_conditional_transfer_does_not_end_fall_through(tmp_path):
    _, why = _reach(
        _program(
            tmp_path,
            "       MAIN-PARA.\n           IF WS-X = 1\n              GOBACK.\n       NEXT-PARA.\n           GOBACK.\n",
            data="       01 WS-X PIC 9.",
        )
    )
    assert why["NEXT-PARA"] == "fall-through from MAIN-PARA"


def test_cics_handle_abend_label_is_live(tmp_path):
    _, why = _reach(
        _program(
            tmp_path,
            "       PREMIERE SECTION.\n"
            "       A010.\n"
            "           EXEC CICS HANDLE ABEND\n"
            "              LABEL(ABEND-HANDLING)\n"
            "           END-EXEC.\n"
            "           EXEC CICS RETURN\n"
            "           END-EXEC.\n"
            "       ABEND-HANDLING SECTION.\n"
            "       AH010.\n"
            "           EXEC CICS RETURN END-EXEC.\n",
        )
    )
    assert why["ABEND-HANDLING"].startswith("EXEC CICS HANDLE label")
    assert why["AH010"] == "fall-through from ABEND-HANDLING"


def test_perform_of_a_never_returning_section_is_terminal(tmp_path):
    """The CBSA shape: the main section ends `PERFORM GET-ME-OUT-OF-HERE.`, which RETURNs."""
    _, why = _reach(
        _program(
            tmp_path,
            "       PREMIERE SECTION.\n"
            "       A010.\n"
            "           PERFORM GET-ME-OUT-OF-HERE.\n"
            "       A999.\n"
            "           EXIT.\n"
            "       GET-ME-OUT-OF-HERE SECTION.\n"
            "       GMOFH010.\n"
            "           EXEC CICS RETURN\n"
            "           END-EXEC.\n"
            "       GMOFH999.\n"
            "           EXIT.\n",
        )
    )
    assert "A999" not in why and "GMOFH999" not in why
    assert why["GMOFH010"] == "fall-through from GET-ME-OUT-OF-HERE"


def test_apostrophe_in_a_comment_entry_does_not_hide_the_program(tmp_path):
    """`AUTHOR. James O'Grady.` once blanked everything after it (CBSA)."""
    path = _program(
        tmp_path,
        "       MAIN-PARA.\n           EXEC CICS RETURN END-EXEC.\n",
        extra_id="       AUTHOR. James O'Grady.",
    )
    entry, _ = ak.draft_program(path, tmp_path, [path], {"PROG": ["PROG.cbl"]})
    assert entry["cics"] is True


def test_end_call_and_hyphenated_names_are_not_calls(tmp_path):
    """CardDemo draft errors: `END-CALL` read as a CALL of the next word (`IF`), and
    `PERFORM 3200-INSERT-IMS-CALL THRU 3200-EXIT` as a CALL of `THRU`."""
    path = _program(
        tmp_path,
        "       MAIN-PARA.\n"
        "           CALL 'MQOPEN' USING WS-X\n"
        "           END-CALL\n"
        "           IF WS-X = 1\n"
        "              PERFORM 3200-INSERT-IMS-CALL THRU 3200-EXIT\n"
        "           END-IF.\n"
        "           GOBACK.\n"
        "       3200-INSERT-IMS-CALL.\n"
        "           DISPLAY 'I'.\n"
        "       3200-EXIT.\n"
        "           EXIT.\n",
        data="       01 WS-X PIC 9.",
    )
    entry, _ = ak.draft_program(path, tmp_path, [path], {"PROG": ["PROG.cbl"]})
    assert [(c["form"], c["operand"]) for c in entry["calls"]] == [("literal", "MQOPEN")]


def test_quoted_copy_and_dclgen_include_resolve(tmp_path):
    """CardDemo draft errors: `COPY 'CSUTLDWY'.` lost its name to literal blanking,
    and `EXEC SQL INCLUDE AUTHFRDS` did not resolve to the DCLGEN member AUTHFRDS.dcl.
    A `COPY` inside a literal is still not a copy."""
    path = _program(
        tmp_path,
        "       MAIN-PARA.\n           DISPLAY 'COPY NOTME'.\n           GOBACK.\n",
        data="       COPY 'CSUTLDWY'.\n           EXEC SQL\n                INCLUDE AUTHFRDS\n           END-EXEC.",
    )
    (tmp_path / "CSUTLDWY.cpy").write_text("       01 X PIC 9.\n", encoding="utf-8")
    (tmp_path / "AUTHFRDS.dcl").write_text("       01 Y PIC 9.\n", encoding="utf-8")
    files = [path, tmp_path / "CSUTLDWY.cpy", tmp_path / "AUTHFRDS.dcl"]
    entry, _ = ak.draft_program(path, tmp_path, files, {"PROG": ["PROG.cbl"]})
    assert {(c["name"], c["via"], c["resolves_to"]) for c in entry["copybooks"]} == {
        ("CSUTLDWY", "COPY", "CSUTLDWY.cpy"),
        ("AUTHFRDS", "SQL INCLUDE", "AUTHFRDS.dcl"),
    }


def test_header_period_on_the_next_line_and_spaced_exit(tmp_path):
    """CardDemo draft errors: COTRTLIC's `2000-SEND-MAP` header has its period on the
    next line, so the unit went missing and its THRU range's `-EXIT` read as dead; and
    `EXIT .` (spaced, CardDemo's style) was not recognised as an EXIT-only paragraph."""
    path = _program(
        tmp_path,
        "       MAIN-PARA.\n"
        "           PERFORM 2000-SEND-MAP\n"
        "              THRU 2000-SEND-MAP-EXIT\n"
        "           GOBACK.\n"
        "       2000-SEND-MAP\n"
        "            .\n"
        "           DISPLAY 'S'.\n"
        "       2000-SEND-MAP-EXIT.\n"
        "           EXIT\n"
        "           .\n"
        "       UNUSED-EXIT.\n"
        "           EXIT\n"
        "           .\n"
        "       COPY 'PROCBOOK'.\n",
    )
    entry, _ = ak.draft_program(path, tmp_path, [path], {"PROG": ["PROG.cbl"]})
    assert [u["name"] for u in entry["units"]] == ["MAIN-PARA", "2000-SEND-MAP", "2000-SEND-MAP-EXIT", "UNUSED-EXIT"]
    assert entry["dead"].keys() == {"UNUSED-EXIT"}
    assert entry["dead"]["UNUSED-EXIT"]["trivial"] is True


def test_perform_after_end_perform_is_seen(tmp_path):
    """CardDemo draft error: `END-PERFORM` then `PERFORM 9450-CLOSE ...` matched as a
    PERFORM of the word PERFORM, so the real target read as dead."""
    path = _program(
        tmp_path,
        "       MAIN-PARA.\n"
        "           PERFORM UNTIL WS-X = 1\n"
        "              MOVE 1 TO WS-X\n"
        "           END-PERFORM\n"
        "           PERFORM CLOSE-PARA\n"
        "           GOBACK.\n"
        "       CLOSE-PARA.\n"
        "           DISPLAY 'C'.\n",
        data="       01 WS-X PIC 9.",
    )
    entry, _ = ak.draft_program(path, tmp_path, [path], {"PROG": ["PROG.cbl"]})
    assert entry["dead"] == {}


def test_closed_if_before_a_terminal_does_not_fall_through(tmp_path):
    """`\\bIF\\b` matched inside `END-IF`, so a paragraph ending `... END-IF ... GOBACK.`
    read as conditional and falling through. CardDemo CBPAUP0C; the same bug hid
    CBSA DELACC/INQACCCU/UPDCUST's dead A999 (key corrected)."""
    path = _program(
        tmp_path,
        "       MAIN-PARA.\n"
        "           IF WS-X = 1\n"
        "              DISPLAY 'Y'\n"
        "           END-IF\n"
        "           GOBACK.\n"
        "       AFTER-PARA.\n"
        "           DISPLAY 'A'.\n",
        data="       01 WS-X PIC 9.",
    )
    entry, _ = ak.draft_program(path, tmp_path, [path], {"PROG": ["PROG.cbl"]})
    assert entry["dead"].keys() == {"AFTER-PARA"}


def test_multi_mode_open_and_call_through_a_value_clause(tmp_path):
    env = (
        "       ENVIRONMENT DIVISION.\n"
        "       INPUT-OUTPUT SECTION.\n"
        "       FILE-CONTROL.\n"
        "           SELECT IN-FILE ASSIGN TO INDD.\n"
        "           SELECT OUT-FILE ASSIGN TO UT-S-OUTDD."
    )
    path = _program(
        tmp_path,
        "       MAIN-PARA.\n"
        "           OPEN INPUT IN-FILE\n"
        "                OUTPUT OUT-FILE.\n"
        "           CALL SUBPGM USING WS-X.\n"
        "           GOBACK.\n",
        data="       01 SUBPGM PIC X(8) VALUE 'SUB1'.\n       01 WS-X PIC 9.",
        extra_id=env,
    )
    sub = tmp_path / "SUB1.cbl"
    sub.write_text("       IDENTIFICATION DIVISION.\n       PROGRAM-ID. SUB1.\n", encoding="utf-8")
    entry, _ = ak.draft_program(path, tmp_path, [path, sub], {"PROG": ["PROG.cbl"], "SUB1": ["SUB1.cbl"]})
    assert {f["dd"]: f["modes"] for f in entry["files"]} == {"INDD": ["INPUT"], "OUTDD": ["OUTPUT"]}
    (call,) = entry["calls"]
    assert (call["form"], call["target"], call["resolves_to"]) == ("identifier", "SUB1", "SUB1.cbl")


def test_key_transactions_reads_the_csd_map(tmp_path):
    """#3247: the key's own CSD reader yields program-id -> entry transaction ids
    from a repo's `.csd` decks, excluding a DB2TRAN's TRANSID."""
    (tmp_path / "BANK.csd").write_text(
        " DEFINE TRANSACTION(OPRG) GROUP(G) PROGRAM(PROG)\n DEFINE DB2TRAN(DB2T) GROUP(G) TRANSID(XXXX) ENTRY(E)\n",
        encoding="utf-8",
    )
    assert ak._key_transactions(tmp_path) == {"PROG": {"OPRG"}}


def test_draft_program_carries_entry_transactions(tmp_path):
    """draft_program fills the drafted `transactions` block from the repo CSD map,
    and defaults to an empty list when no map is supplied (older callers)."""
    path = _program(tmp_path, "       MAIN-PARA.\n           GOBACK.\n")
    (tmp_path / "BANK.csd").write_text(" DEFINE TRANSACTION(OPRG) GROUP(G) PROGRAM(PROG)\n", encoding="utf-8")
    tx_map = ak._key_transactions(tmp_path)
    entry, _ = ak.draft_program(path, tmp_path, [path], {"PROG": ["PROG.cbl"]}, tx_map)
    assert entry["transactions"] == ["OPRG"]

    entry_no_map, _ = ak.draft_program(path, tmp_path, [path], {"PROG": ["PROG.cbl"]})
    assert entry_no_map["transactions"] == []


def test_copybooks_resolve_to_members_through_zapp_libraries(tmp_path):
    (tmp_path / "zapp.yaml").write_text(
        "propertyGroups:\n"
        "  - name: cobol-copybooks\n"
        "    language: cobol\n"
        "    libraries:\n"
        "      - name: syslib\n"
        "        type: local\n"
        "        locations:\n"
        '          - "**/COPYBOOK"\n'
        "      - name: MYLIB\n"
        "        type: local\n"
        "        locations:\n"
        '          - "**/COPYLIB"\n',
        encoding="utf-8",
    )
    files = []
    for rel in ("COPYBOOK/REC.cpy", "other/REC.cpy", "COPYLIB/DATES.cpy", "src/PROG.cbl"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("", encoding="utf-8")
        files.append(tmp_path / rel)
    prog = tmp_path / "src" / "PROG.cbl"

    def resolve(name, library=None):
        return ak.resolve_copybook(name, library, prog, tmp_path, files)

    assert resolve("REC")["resolves_to"] == "COPYBOOK/REC.cpy"  # the zapp syslib wins the duplicate
    assert resolve("DATES", "MYLIB")["resolves_to"] == "COPYLIB/DATES.cpy"
    assert resolve("PROG")["resolves_to"] is None  # a program is never a copybook
    assert resolve("DFHAID")["why"] == "CICS-supplied"


# ==============================================================================
# Scorer
# ==============================================================================
def test_score_measures_the_forge_against_a_key(tmp_path):
    path = _program(
        tmp_path,
        "       MAIN-PARA.\n           PERFORM USED-PARA.\n           GOBACK.\n"
        "       USED-PARA.\n           DISPLAY 'U'.\n"
        "       UNUSED-PARA.\n           DISPLAY 'X'.\n",
    )
    entry, _ = ak.draft_program(path, tmp_path, [path], {"PROG": ["PROG.cbl"]})
    entry["verification"]["status"] = "validated"
    key = {"schema_version": 1, "corpus": "fixture", "ref": "0" * 40, "programs": {"PROG.cbl": entry}}

    result, md = ak.score(tmp_path, key, db=None)

    assert entry["dead"].keys() == {"UNUSED-PARA"}
    assert result["unverified_programs"] == []
    assert result["fields"]["dead"]["forge"]["truth"] == 1
    assert result["fields"]["units"]["engine"] is None  # no DB given
    assert "| dead |" in md


def test_data_items_reads_the_record_layout_independently(tmp_path):
    """#3246: the key's own DATA DIVISION reader -- nesting, PIC, COMP-3, OCCURS,
    REDEFINES and a group item, read with this tool's Source (not the engine or
    the forge), so the key can adjudicate a record delta between them."""
    path = _program(
        tmp_path,
        "       MAIN-PARA.\n           GOBACK.\n",
        data=(
            "       01  CUST-REC.\n"
            "           05  CUST-ID       PIC 9(6).\n"
            "           05  CUST-BAL      PIC S9(9)V99 USAGE COMP-3.\n"
            "           05  CUST-FLAGS    OCCURS 3 TIMES PIC X.\n"
            "       01  CUST-ALT REDEFINES CUST-REC PIC X(20).\n"
        ),
    )
    items = {r["name"]: r for r in ak._data_items(ak.Source(path))}
    assert items["CUST-REC"]["pic"] is None  # a group item
    assert items["CUST-ID"]["parent"] == items["CUST-REC"]["ordinal"]
    assert items["CUST-BAL"]["usage"] == "COMP-3"
    assert (items["CUST-FLAGS"]["occurs_min"], items["CUST-FLAGS"]["occurs_max"]) == (3, 3)
    assert items["CUST-ALT"]["redefines"] == "CUST-REC"
    # Only the elementary, non-group fields are what all three sides turn into columns.
    assert {r["name"] for r in ak._data_items(ak.Source(path)) if ak.is_record_field(r)} == {
        "CUST-ID",
        "CUST-BAL",
        "CUST-FLAGS",
        "CUST-ALT",
    }


# ==============================================================================
# #3250: PL/I DECLARE record layouts -- the key's own reader
# ==============================================================================
def test_pli_reader_reads_the_raw_file_independently():
    """Raw source in: the reader strips its own comments and numbered columns
    73-80 (navikt/DSF), expands factoring and skips what is not storage."""
    src = "\n".join(
        [
            f"{'    DCL                  /* FILE AND TABLES */':<72}00000110",
            f"{'      1 REC BASED(P),':<72}00000120",
            f"{'        2 KEY,':<72}00000130",
            f"{'          3 (ID, TYPE) CHAR(5),':<72}00000140",
            f"{'        2 BAL PIC ' + chr(39) + '9V99' + chr(39) + ';':<72}00000150",
            "    DCL (ADDR, NULL) BUILTIN;  // a line comment",
            "    DCL F FILE, PSAM2 EXTERNAL ENTRY, EV ENTRY VARIABLE;",
            " %DECLARE MACROVAR CHARACTER;",
            " %M: PROCEDURE(I) RETURNS(FIXED);",
            "   DECLARE I FIXED;",
            " %END M;",
            "    DCL 1 B01 BASED(B01_PEKER), %INCLUDE P0019921;",
        ]
    )
    items = ak.pli_data_items(src)
    assert [(it["level"], it["name"], it["parent"]) for it in items] == [
        (1, "REC", None),
        (2, "KEY", 0),
        (3, "ID", 1),
        (3, "TYPE", 1),
        (2, "BAL", 0),
        (1, "EV", None),
        (1, "B01", None),
    ]
    assert items[2]["attributes"] == "CHAR(5)"
    assert items[4]["attributes"] == "PIC '9V99'"
    assert items[1]["line"] == 3


def test_pli_record_fields_are_dotted_leaf_paths():
    items = ak.pli_data_items(" DCL 1 A, 2 B, 3 C CHAR(1), 2 * CHAR(2), 2 D FIXED; DCL E CHAR(1);")
    assert ak.pli_record_fields(items) == {"A.B.C", "A.D", "E"}


@pytest.mark.parametrize("key_path", KEYS, ids=lambda p: p.stem)
def test_pli_key_entries_are_drafts_until_signed_off(key_path):
    """PL/I layouts are committed drafted (`records_validated: false`); a drafted
    field never adjudicates, so a sign-off is an explicit, reviewed edit."""
    key = json.loads(key_path.read_text(encoding="utf-8"))
    for rel, entry in key.get("pli_programs", {}).items():
        assert rel.lower().endswith(ak.PLI_EXTS), rel
        assert isinstance(entry["records_validated"], bool)
        assert entry["verification"]["status"] in ("draft", "validated")
        for it in entry["records"]:
            assert {"ordinal", "parent", "level", "name", "attributes", "line"} <= set(it)


# ==============================================================================
# #3344: DB2 DECLARE TABLE / DCLGEN columns -- the key's own reader
# ==============================================================================
def test_sql_reader_cuts_at_the_terminator_on_the_raw_file():
    """Raw fixed-format source in, sequence numbers in columns 1-6 and 73-80
    (IBM's DSN8 DCLGEN as stored on the host), a comment line inside the list."""
    src = "\n".join(
        [
            "000100* DCLGEN TABLE(DSN8C10.EMP)",
            f"{'000200     EXEC SQL DECLARE DSN8C10.EMP TABLE':<72}00020000",
            f"{'000300     ( EMPNO                          CHAR(6) NOT NULL,':<72}00030000",
            "000400*      OLDCOL                         CHAR(1),",
            f"{'000500       SALARY                         DECIMAL(9, 2),':<72}00050000",
            f"{'000600       RESUME                         CLOB(1M)':<72}00060000",
            f"{'000700     ) END-EXEC.':<72}00070000",
            "       01  DCLEMP.",
            "           10 EMPNO   PIC X(6).",
        ]
    )
    cols = ak.sql_table_columns(src)
    assert [(c["colno"], c["name"], c["sql_type"], c["length"], c["scale"], c["nullable"]) for c in cols] == [
        (1, "EMPNO", "CHAR", 6, None, False),
        (2, "SALARY", "DECIMAL", 9, 2, True),
        (3, "RESUME", "CLOB", 1024 * 1024, None, True),
    ]
    assert {c["table"] for c in cols} == {"DSN8C10.EMP"}
    assert cols[0]["line"] == 3


def test_sql_reader_pli_terminator_and_column_key():
    src = (
        " /* DCLGEN */\n EXEC SQL DECLARE DEPT TABLE\n ( DEPTNO CHAR(3) NOT NULL,\n   TS TIMESTAMP WITH TIME ZONE ) ;\n"
    )
    cols = ak.sql_table_columns(src, pli=True)
    assert ak.sql_column_keys(cols) == {"DEPT.DEPTNO CHAR(3) NOT NULL", "DEPT.TS TIMESTAMP WITH TIME ZONE NULLABLE"}


@pytest.mark.parametrize("key_path", KEYS, ids=lambda p: p.stem)
def test_sql_table_key_entries_are_drafts_until_signed_off(key_path):
    key = json.loads(key_path.read_text(encoding="utf-8"))
    for rel, entry in key.get("sql_tables", {}).items():
        assert rel.lower().endswith(ak.SQL_TABLE_EXTS), rel
        assert isinstance(entry["sql_tables_validated"], bool)
        assert entry["verification"]["status"] in ("draft", "validated")
        for c in entry["columns"]:
            assert {"table", "colno", "name", "sql_type", "length", "scale", "nullable", "line"} <= set(c)


# ==============================================================================
# #3347: BMS screen-field layouts -- the key's own reader
# ==============================================================================
def test_bms_reader_reads_the_raw_file_independently():
    """Raw source in: the reader drops its own `*` comment lines, joins column-72
    continuations at column 16 (a literal split mid-word too), ignores columns
    73-80 and skips the TYPE=FINAL closer."""
    src = "\n".join(
        [
            "*  BNK1CAM banner",
            f"{'BNK1CAM  DFHMSD TYPE=&SYSPARM,MODE=INOUT,LANG=COBOL':<72}00000100",
            f"{'BNK1CA   DFHMDI SIZE=(24,80),':<71}*",
            "               COLUMN=1,LINE=1",
            f"{'         DFHMDF POS=(3,1),LENGTH=57,ATTRB=(NORM,PROT),COLOR=TURQUOISE,':<71}*",
            f"{'               INITIAL=' + chr(39) + 'Please provide the requested information and pr':<71}*",
            "               ess Enter.'",
            f"{'ACCOUNT  DFHMDF POS=(9,1),LENGTH=79,ATTRB=(NORM,PROT),':<71}*",
            "               OCCURS=10,PICOUT='9999.99'     REMARKS HERE",
            "*OLD     DFHMDF POS=(10,1),LENGTH=1",
            "         DFHMSD TYPE=FINAL",
        ]
    )
    items = ak.bms_screen_items(src)
    assert [(it["kind"], it["name"], it["parent_ordinal"], it["line"]) for it in items] == [
        ("mapset", "BNK1CAM", None, 2),
        ("map", "BNK1CA", 0, 3),
        ("field", None, 1, 5),
        ("field", "ACCOUNT", 1, 8),
    ]
    assert items[2]["initial"] == "Please provide the requested information and press Enter."
    assert (items[3]["occurs"], items[3]["picout"], items[3]["attrb"]) == (10, "9999.99", "NORM,PROT")
    assert ak.bms_symbolic_names(items) == {"BNK1CA.ACCOUNT"}
    units = ak.bms_layout_units(items)
    assert "mapset BNK1CAM" in units and "map BNK1CAM.BNK1CA" in units
    assert "field BNK1CA.ACCOUNT @9,1 len=79 attrb=NORM,PROT picout=9999.99 occurs=10" in units


def test_symbolic_map_names_read_a_generated_copybook(tmp_path):
    cpy = tmp_path / "M.cpy"
    cpy.write_text(
        "\n".join(
            [
                "       01  CCRDLIAI.",
                "           02  FILLER PIC X(12).",
                "           02  TRNNAMEL    COMP  PIC  S9(4).",
                "           02  TRNNAMEF    PICTURE X.",
                "           02  FILLER REDEFINES TRNNAMEF.",
                "             03 TRNNAMEA    PICTURE X.",
                "           02  FILLER   PICTURE X(4).",
                "           02  TRNNAMEI  PIC X(4).",
                "       01  CCRDLIAO REDEFINES CCRDLIAI.",
                "           02  FILLER PIC X(12).",
                "           02  TRNNAMEO  PIC X(4).",
            ]
        ),
        encoding="utf-8",
    )
    assert ak.symbolic_map_names(cpy) == {"CCRDLIA.TRNNAME"}


@pytest.mark.parametrize("key_path", KEYS, ids=lambda p: p.stem)
def test_bms_key_entries_are_drafts_until_signed_off(key_path):
    key = json.loads(key_path.read_text(encoding="utf-8"))
    for rel, entry in key.get("bms_maps", {}).items():
        assert rel.lower().endswith(ak.BMS_EXTS), rel
        assert isinstance(entry["fields_validated"], bool)
        assert entry["verification"]["status"] in ("draft", "validated")
        for it in entry["fields"]:
            assert set(ak.BMS_ITEM_KEYS) | {"line"} <= set(it)


# ==============================================================================
# #3351-#3354: EXEC CICS resource operations -- the key's own reader
# ==============================================================================
def test_cics_reader_reads_the_raw_file_independently(tmp_path):
    """Raw fixed-format source in: sequence numbers in 1-6 and 73-80, a comment
    line carrying a command, a DISPLAY literal naming one, a VALUE on the line after
    its PIC (carddemo), a single MOVEd container name and an ambiguous one (CBSA)."""
    src = "\n".join(
        [
            "000100 IDENTIFICATION DIVISION.",
            "000200 PROGRAM-ID. INQ.",
            "000300 WORKING-STORAGE SECTION.",
            f"{'000400    05 LIT-ACCTFILENAME          PIC X(8)':<72}00040000",
            "000500                                  VALUE 'ACCTDAT '.",
            "000600 PROCEDURE DIVISION.",
            "000700*    EXEC CICS READ FILE('OLDFILE') END-EXEC",
            "000800     DISPLAY 'EXEC CICS WRITEQ TS QUEUE(X) failed'.",
            f"{'000900     EXEC CICS READ DATASET (LIT-ACCTFILENAME)':<72}00090000",
            "001000          INTO (ACCOUNT-RECORD) RESP(WS-RESP) END-EXEC.",
            "001100     MOVE 'CIPA' TO WS-CONT.",
            "001200     MOVE 'CIPCREDCHANN' TO WS-CHAN.",
            "001300     MOVE 'X1' TO WS-AMB.",
            "001400     MOVE 'X2' TO WS-AMB.",
            "001500     EXEC CICS GET CONTAINER(WS-CONT) CHANNEL(WS-CHAN)",
            "001600          INTO(WS-IN) END-EXEC.",
            "001700     EXEC CICS PUT CONTAINER(WS-AMB) FROM(WS-IN) END-EXEC.",
            "001800     EXEC CICS WRITEQ TD QUEUE('JOBS') FROM(JCL-REC) END-EXEC.",
            "001900     EXEC CICS SEND MAP('CUSTA') MAPSET('CUSTM') FROM(CUSTAO)",
            "002000          ERASE END-EXEC.",
        ]
    )
    path = tmp_path / "INQ.cbl"
    path.write_text(src, encoding="utf-8")
    assert ak.cics_resource_keys(ak.cics_resource_ops(path)) == {
        "L9 READ FILE ACCTDAT q=- INTO=ACCOUNT-RECORD",
        "L15 GET CONTAINER CIPA q=CIPCREDCHANN INTO=WS-IN",
        "L17 PUT CONTAINER <ambiguous:X1,X2> q=- FROM=WS-IN",
        "L18 WRITEQ QUEUE JOBS q=TD FROM=JCL-REC",
        "L19 SEND MAP CUSTA q=CUSTM FROM=CUSTAO",
    }
    read = ak.cics_resource_ops(path)[0]
    assert (read["resolution"], read["access"]) == ("value", "read")


@pytest.mark.parametrize("key_path", KEYS, ids=lambda p: p.stem)
def test_cics_key_entries_are_drafts_until_signed_off(key_path):
    key = json.loads(key_path.read_text(encoding="utf-8"))
    for rel, entry in key.get("cics_resources", {}).items():
        assert rel.lower().endswith(ak.CICS_EXTS + ak.HLASM_EXTS + ak.PLI_EXTS), rel  # #3495 HLASM, #3577 PL/I
        assert isinstance(entry["cics_validated"], bool)
        assert entry["verification"]["status"] in ("draft", "validated")
        for op in entry["operations"]:
            assert {"verb", "kind", "access", "name", "resolution", "qualifier", "record_clause", "line"} <= set(op)


def test_call_targets_exclude_transaction_routing():
    """`RETURN TRANSID('OMEN')` names a transaction, not a program, so it is not a
    call target (it put 25 false targets into CBSA's score once #3251 carried it)."""
    from types import SimpleNamespace as C

    calls = [
        C(verb="LINK", target="GETCOMPY"),
        C(verb="CALL", target="SAM2"),
        C(verb="RETURN TRANSID", target="OMEN"),
        C(verb="START TRANSID", target="OSTA"),
        C(verb="RUN TRANSID", target="ORUN"),
        C(verb="CALL", target=None),
    ]
    assert ak.engine_call_targets(calls) == {"GETCOMPY", "SAM2"}


def test_scorer_routing_verbs_mirror_the_reader():
    from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import TRANSACTION_ROUTING_VERBS

    assert ak._TRANSACTION_ROUTING_VERBS == frozenset(TRANSACTION_ROUTING_VERBS)


def test_draft_readers_never_import_the_parsers_they_grade(tmp_path):
    """Independence: the key is only evidence if its reader shares no code with the
    engine or the forge. Only `score` (and its forge-view helpers) may import
    gitgalaxy; every draft path must run with none of it loaded."""
    import subprocess

    (tmp_path / "PROG.cbl").write_text(
        "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. PROG.\n       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n       01 WS-X PIC 9.\n       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n           CALL 'SUB' USING WS-X.\n           GOBACK.\n",
        encoding="utf-8",
    )
    (tmp_path / "MAP.bms").write_text("MAP      DFHMSD TYPE=MAP\n", encoding="utf-8")
    (tmp_path / "JOB.jcl").write_text("//JOB JOB\n//S1 EXEC PGM=PROG\n//DD1 DD DSN=A.B,DISP=SHR\n", encoding="utf-8")
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]); import cobol_answer_key as ak; from pathlib import Path\n"
        "r = Path(sys.argv[2])\n"
        "ak.draft(r, 'c', 'u', '0' * 40)\n"
        "for f in (ak.draft_pli, ak.draft_sql_tables, ak.draft_bms, ak.draft_jcl, ak.draft_csd, ak.draft_cics):\n"
        "    f(r)\n"
        "print(sorted(m for m in sys.modules if m == 'gitgalaxy' or m.startswith('gitgalaxy.')))\n"
    )
    tools = str(Path(__file__).resolve().parents[1] / "tools")
    out = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code, tools, str(tmp_path)], capture_output=True, text=True, check=True
    ).stdout
    assert out.strip().splitlines()[-1] == "[]", out


def test_sample_is_seeded_and_covers_claim_kinds():
    key = json.loads((KEY_DIR / "cics-banking-sample-application-cbsa.json").read_text(encoding="utf-8"))
    a = ak.sample_claims(key, 60, seed=7)
    assert a == ak.sample_claims(key, 60, seed=7)
    assert len(a) == 60
    assert {r["kind"] for r in a} >= {"live", "copybook", "call"}


def test_a_terminal_sentence_before_the_last_ends_the_unit(tmp_path):
    """Blind cross-check finding (CBSA BNK1CCS): A010 ends
    `EXEC CICS RETURN TRANSID(...) END-EXEC.` then an `IF <resp> ... END-IF.`
    recovery sentence. Only the last sentence was tested, so A010 read as falling
    through and A999 as live; nine CBSA programs have this shape."""
    path = _program(
        tmp_path,
        "       A010.\n"
        "           EXEC CICS RETURN TRANSID('OCCS') RESP(WS-R) END-EXEC.\n"
        "           IF WS-R NOT = 0\n"
        "              DISPLAY 'FAIL'\n"
        "           END-IF.\n"
        "       A999.\n"
        "           EXIT.\n",
        data="       01 WS-R PIC S9(8) COMP.",
    )
    entry, _ = ak.draft_program(path, tmp_path, [path], {"PROG": ["PROG.cbl"]})
    assert entry["dead"].keys() == {"A999"}


def test_alter_target_is_reached(tmp_path):
    """CardDemo CBSTM03A: `ALTER 8100-FILE-OPEN TO PROCEED TO 8200-XREFFILE-OPEN`
    then `GO TO 8100-FILE-OPEN` -- 8200 is reached only through the ALTER."""
    path = _program(
        tmp_path,
        "       0000-START.\n"
        "           ALTER 8100-FILE-OPEN TO PROCEED TO 8200-OPEN\n"
        "           GO TO 8100-FILE-OPEN.\n"
        "       8100-FILE-OPEN.\n"
        "           GO TO 8100-FIRST.\n"
        "       8100-FIRST.\n"
        "           GOBACK.\n"
        "       8200-OPEN.\n"
        "           GOBACK.\n",
    )
    entry, _ = ak.draft_program(path, tmp_path, [path], {"PROG": ["PROG.cbl"]})
    assert entry["dead"] == {}


@pytest.mark.parametrize("key_path", KEYS, ids=lambda p: p.stem)
def test_small_corpus_keys_are_fully_censused(key_path):
    """Every committed key has been read twice, blind: each program carries a clean
    census sign-off (cross_verify.py census/sign). A new or re-drafted program must
    be censused before it lands. A corpus too large to census would need its own
    sampled-confidence rule instead of this gate."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    import cross_verify as cv

    cov = cv.coverage(json.loads(key_path.read_text(encoding="utf-8")))
    assert not cov["missing"], f"not censused: {cov['missing'][:5]}"


def test_sql_table_access_reader_is_independent_and_joins_cursors():
    """#3446: the key's own token walk over EXEC SQL: tables per access, a cursor's
    reads reached through OPEN / FETCH, literals and INCLUDE ignored. Lines stay
    within column 72, as fixed-format source must."""
    src = (
        "       PROCEDURE DIVISION.\n"
        "           EXEC SQL INCLUDE SQLCA END-EXEC.\n"
        "           EXEC SQL DECLARE C1 CURSOR FOR\n"
        "                SELECT A FROM ACCOUNT X, CUST Y END-EXEC.\n"
        "           EXEC SQL OPEN C1 END-EXEC.\n"
        "           EXEC SQL DELETE FROM CARDDEMO.TT\n"
        "                WHERE K = 'FROM FAKE' END-EXEC.\n"
        "           EXEC SQL INSERT INTO HIST\n"
        "                SELECT * FROM LIVE END-EXEC.\n"
    )
    assert all(len(line) <= 72 for line in src.splitlines())
    assert ak.sql_table_access(src) == [
        "delete CARDDEMO.TT",
        "insert HIST",
        "read ACCOUNT",
        "read CUST",
        "read LIVE",
    ]


def test_cics_task_reader_is_independent_and_expands_string_ids(tmp_path):
    """#3449: the key's own task-control reader -- a STRING-built transid is a
    PIC-sized pattern expanded against the key's own CSD read (never OCRA), a
    DISPLAY literal is not a command, and the unit keys match the engine's shape."""
    (tmp_path / "BANK.csd").write_text(
        " DEFINE TRANSACTION(OCR1) GROUP(B)\n        PROGRAM(C1)\n"
        " DEFINE TRANSACTION(OCRA) GROUP(B)\n        PROGRAM(MENU)\n",
        encoding="utf-8",
    )
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. PARENT.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01 WS-N                 PIC 9.\n"
        "       01 WS-T                 PIC X(4).\n"
        "       PROCEDURE DIVISION.\n"
        "           MOVE 'CHAN1' TO WS-CH.\n"
        "           STRING 'OCR' DELIMITED BY SIZE, WS-N DELIMITED BY SIZE\n"
        "              INTO WS-T END-STRING.\n"
        "           EXEC CICS RUN TRANSID(WS-T) CHANNEL(WS-CH)\n"
        "                CHILD(WS-TKN) END-EXEC.\n"
        "           DISPLAY 'EXEC CICS FETCH ANY failed'.\n"
        "           EXEC CICS DELAY FOR SECONDS(3) END-EXEC.\n"
        "           EXEC CICS RETRIEVE INTO(MQTM) NOHANDLE END-EXEC.\n"
    )
    assert all(len(line) <= 72 for line in src.splitlines())
    (tmp_path / "PARENT.cbl").write_text(src, encoding="utf-8")
    entry = ak.draft_cics_tasks(tmp_path)["PARENT.cbl"]
    assert sorted(ak.cics_task_keys(entry["operations"])) == [
        "L11 RUN T=<pattern:OCR[0-9]> ch=CHAN1 tok=WS-TKN",
        "L14 DELAY T=- ch=- tok=- @FOR SECONDS(3)",
        "L15 RETRIEVE T=- ch=- tok=- INTO=MQTM",
    ]
    assert entry["children"] == ["RUN OCR1"]
    assert entry["cics_tasks_validated"] is False


def test_job_submission_reader_is_independent(tmp_path):
    """#3448: the key's own join -- a WRITEQ TD to an extrapartition queue is a
    submission only with a JOB card literal (or a region INTRDR DD for its DDNAME);
    a batch SYSOUT=(x,INTRDR) step submits its SYSUT1 member."""
    files = {
        "csd/D.csd": " DEFINE TDQUEUE(JOBS) GROUP(D)\n        TYPE(EXTRA) DDNAME(INREADER)\n"
        " DEFINE TDQUEUE(AUDT) GROUP(D)\n        TYPE(EXTRA) DDNAME(AUDITDD)\n",
        "cbl/RPT.cbl": (
            "       IDENTIFICATION DIVISION.\n"
            "       PROGRAM-ID. RPT.\n"
            "       DATA DIVISION.\n"
            "       WORKING-STORAGE SECTION.\n"
            "       01 F PIC X(80) VALUE \"//RPTJOB JOB 'R',CLASS=A\".\n"
            '       01 G PIC X(80) VALUE "//S1 EXEC PROC=RPTPROC".\n'
            "       PROCEDURE DIVISION.\n"
            "           EXEC CICS WRITEQ TD QUEUE('JOBS') FROM(F) END-EXEC.\n"
            "           EXEC CICS WRITEQ TD QUEUE('AUDT') FROM(F) END-EXEC.\n"
        ),
        "cbl/AUD.cbl": (
            "       IDENTIFICATION DIVISION.\n"
            "       PROGRAM-ID. AUD.\n"
            "       PROCEDURE DIVISION.\n"
            "           EXEC CICS WRITEQ TD QUEUE('AUDT') FROM(X) END-EXEC.\n"
        ),
        "proc/RPTPROC.prc": "//RPTPROC PROC\n",
        "jcl/RPTPROC.jcl": "//RPTPROC JOB\n",
        "jcl/SUB.jcl": "//SUB JOB\n//S1 EXEC PGM=IEBGENER\n//SYSUT1 DD DSN=L(RPTPROC),DISP=SHR\n//SYSUT2 DD SYSOUT=(A,INTRDR)\n",
    }
    for rel, text in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, encoding="utf-8")
    got = {rel: v["submissions"] for rel, v in ak.draft_job_submissions(tmp_path).items()}
    assert got == {
        "cbl/RPT.cbl": [
            "tdq AUDT -> JOB RPTJOB",
            "tdq AUDT -> PROC RPTPROC = proc/RPTPROC.prc",
            "tdq JOBS -> JOB RPTJOB",
            "tdq JOBS -> PROC RPTPROC = proc/RPTPROC.prc",
        ],
        "jcl/SUB.jcl": ["intrdr SYSUT2 -> JOB RPTPROC = jcl/RPTPROC.jcl"],
    }


def test_mq_reader_is_independent_and_follows_handles(tmp_path):
    """#3447: the key's own token walk over MQ calls -- queue through the
    descriptor's OBJECTNAME, a trigger-named input queue, a handle copied off
    the shared MQ-HOBJ, and a DISPLAY literal that is not a call."""
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. MQK.\n"
        "       PROCEDURE DIVISION.\n"
        "           MOVE MQTM-QNAME TO IN-Q\n"
        "           MOVE IN-Q TO MQOD-OBJECTNAME\n"
        "           COMPUTE OPTS = MQOO-INPUT-SHARED + MQOO-FAIL-IF-QUIESCING\n"
        "           CALL 'MQOPEN' USING HC OD OPTS MQ-HOBJ CC RC\n"
        "           MOVE MQ-HOBJ TO IN-HANDLE\n"
        "           MOVE 'APP.OUT' TO MQOD-OBJECTNAME\n"
        "           COMPUTE OPTS = MQOO-OUTPUT\n"
        "           CALL 'MQOPEN' USING HC OD OPTS MQ-HOBJ CC RC\n"
        "           MOVE MQ-HOBJ TO OUT-HANDLE\n"
        "           DISPLAY 'CALL MQGET FAILED'\n"
        "           MOVE IN-HANDLE TO MQ-HOBJ\n"
        "           CALL 'MQGET' USING HC MQ-HOBJ MD GMO L B DL CC RC\n"
        "           CALL 'MQPUT' USING HC OUT-HANDLE MD PMO L B CC RC.\n"
    )
    assert all(len(line) <= 72 for line in src.splitlines())
    (tmp_path / "MQK.cbl").write_text(src, encoding="utf-8")
    rows = ak.draft_mq(tmp_path)["MQK.cbl"]["calls"]
    assert sorted(ak.mq_call_keys(rows)) == [
        "L11 MQOPEN dir=put q=APP.OUT",
        "L15 MQGET dir=get q=<trigger> open=L7",
        "L16 MQPUT dir=put q=APP.OUT open=L11",
        "L7 MQOPEN dir=get q=<trigger>",
    ]


def test_uow_and_tdq_trigger_readers_are_independent(tmp_path):
    """#3453: the key's own reading of unit-of-work points, handlers and RESP
    checks (a paragraph header ends a RESP window), and of TD trigger starts."""
    (tmp_path / "D.csd").write_text(
        " DEFINE TDQUEUE(PRTQ) GROUP(D)\n        TYPE(INTRA) TRIGGERLEVEL(1) TRANSID(PRT1)\n"
        " DEFINE TRANSACTION(PRT1) GROUP(D)\n        PROGRAM(PRTPGM)\n",
        encoding="utf-8",
    )
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. UOWK.\n"
        "       PROCEDURE DIVISION.\n"
        "       P1.\n"
        "           EXEC CICS HANDLE ABEND LABEL(P9) END-EXEC.\n"
        "           EXEC CICS READ FILE('F') INTO(R) RESP(WS-R) END-EXEC.\n"
        "           IF WS-R NOT = DFHRESP(NORMAL)\n"
        "              EXEC CICS SYNCPOINT ROLLBACK END-EXEC\n"
        "           END-IF.\n"
        "           EXEC CICS WRITEQ TD QUEUE('PRTQ') FROM(R) RESP(WS-R)\n"
        "           END-EXEC.\n"
        "       P9.\n"
        "           IF WS-R = DFHRESP(QIDERR) CONTINUE END-IF.\n"
        "           EXEC CICS ABEND ABCODE('K001') NODUMP END-EXEC.\n"
    )
    assert all(len(line) <= 72 for line in src.splitlines())
    (tmp_path / "UOWK.cbl").write_text(src, encoding="utf-8")
    rows = ak.draft_uow(tmp_path)["UOWK.cbl"]["rows"]
    assert sorted(ak.uow_keys(rows), key=lambda k: int(k.split()[0][1:])) == [
        "L5 HANDLE_ABEND HANDLE ABEND c=- t=P9/LABEL v=- a=-",
        "L6 RESP_CHECK READ c=NORMAL t=-/- v=WS-R a=-",
        "L8 ROLLBACK SYNCPOINT ROLLBACK c=- t=-/- v=- a=-",
        "L10 RESP_CHECK WRITEQ c=- t=-/- v=WS-R a=-",
        "L14 ABEND ABEND c=K001 t=-/- v=- a=NODUMP",
    ]
    assert ak.draft_tdq_triggers(tmp_path)["UOWK.cbl"]["starts"] == ["PRTQ -> PRT1 -> PRTPGM"]


def test_key_reads_resp_codes_tested_by_number():
    """#3453 follow-up: `EVALUATE v WHEN 0 / WHEN 13` tests NORMAL / NOTFND (CardDemo
    COSGN00C); a nested EVALUATE's WHEN arms belong to that EVALUATE, not to v."""
    text = (
        "EVALUATE WS-RESP-CD\n WHEN 0\n  EVALUATE WS-MONTH\n   WHEN 12 CONTINUE\n  END-EVALUATE\n"
        " WHEN 13 CONTINUE\nEND-EVALUATE\nIF WS-RESP-CD NOT = 22 CONTINUE END-IF\nIF WS-RESP-CD = 923 CONTINUE END-IF\n"
    )
    assert ak._uow_numeric(text, "WS-RESP-CD") == {"NORMAL", "NOTFND", "LENGERR", "923"}


def test_file_definition_readers_are_independent(tmp_path):
    """#3455: the key's own SELECT and IDCAMS readers."""
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. FDK.\n"
        "       ENVIRONMENT DIVISION.\n"
        "       FILE-CONTROL.\n"
        "           SELECT X-FILE ASSIGN TO XDD\n"
        "                  ORGANIZATION IS INDEXED ACCESS IS DYNAMIC\n"
        "                  RECORD KEY IS X-KEY\n"
        "                  ALTERNATE RECORD KEY IS X-ALT WITH DUPLICATES\n"
        "                  FILE STATUS IS X-STAT.\n"
        "       DATA DIVISION.\n"
        "       FILE SECTION.\n"
        "       FD  X-FILE.\n"
        "       COPY XREC.\n"
    )
    assert all(len(line) <= 72 for line in src.splitlines())
    (tmp_path / "FDK.cbl").write_text(src, encoding="utf-8")
    (tmp_path / "DEF.jcl").write_text(
        "//DEF JOB\n//S1 EXEC PGM=IDCAMS\n//SYSIN DD *\n"
        "  DEFINE CLUSTER (NAME(A.KSDS) -\n    INDEXED KEYS(8 0) -\n    RECORDSIZE(80 80)) -\n"
        "    DATA (NAME(A.KSDS.D))\n  DEF AIX (NAME(A.AIX) RELATE(A.KSDS) KEYS(5 8) UNIQUEKEY)\n/*\n",
        encoding="utf-8",
    )
    fc, vd = ak.draft_file_defs(tmp_path)
    assert ak.file_control_keys(fc["FDK.cbl"]["selects"]) == {
        "L5 SELECT X-FILE ASSIGN=XDD ORG=INDEXED ACCESS=DYNAMIC KEY=X-KEY ALT=X-ALT+DUP REL=- STATUS=X-STAT COPY=XREC"
    }
    assert ak.vsam_define_keys(vd["DEF.jcl"]["defines"]) == {
        "L4 CLUSTER A.KSDS ORG=INDEXED KEYS=8,0 REC=80,80 REL=- UNIQ=- UPG=- STEP=S1",
        "L8 AIX A.AIX ORG=- KEYS=5,8 REC=- REL=A.KSDS UNIQ=UNIQUE UPG=- STEP=S1",
    }


def test_job_flow_reader_is_independent():
    """#3451: the key's own job-flow reading: steps with COND / IF / ELSE, an
    override DD, a concatenation, DISP defaults and GDG generations."""
    text = (
        "//J1 JOB CLASS=A\n"
        "//S1 EXEC PGM=SORT,COND=(4,LT)\n"
        "//SORTIN DD DSN=A.B(0),DISP=SHR\n"
        "//       DD DSN=A.C,DISP=OLD\n"
        "// IF (S1.RC = 0) THEN\n"
        "//S2 EXEC PROC=P1\n"
        "//P1S1.IN DD DISP=SHR,\n"
        "//        DSN=A.D\n"
        "// ELSE\n"
        "//S3 EXEC PGM=X\n"
        "//OUT DD DSN=A.E(+1),DISP=(,CATLG)\n"
        "// ENDIF\n"
    )
    assert ak.job_flow_keys(ak.job_flow_rows(text)) == {
        "L1 JOB J1 COND=-",
        "L2 STEP 1 S1 PGM=SORT PROC=- COND=(4,LT) IF=- IN=-",
        "L3 DD S1.SORTIN DSN=A.B DISP=SHR GEN=0 IN=-",
        "L4 DD S1.SORTIN DSN=A.C DISP=OLD GEN=- IN=-",
        "L6 STEP 2 S2 PGM=- PROC=P1 COND=- IF=(S1.RC = 0) IN=-",
        "L7 DD P1S1.IN DSN=A.D DISP=SHR GEN=- IN=-",
        "L10 STEP 3 S3 PGM=X PROC=- COND=- IF=NOT (S1.RC = 0) IN=-",
        "L11 DD S3.OUT DSN=A.E DISP=NEW GEN=+1 IN=-",
    }


def test_call_using_reader_is_independent(tmp_path):
    """#3454: the key's own reading of CALL USING lists and entry parameters."""
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. CU.\n"
        "       PROCEDURE DIVISION USING LS-A, LS-B.\n"
        "           CALL 'X' USING BY CONTENT 'LIT' WS-A\n"
        "                BY REFERENCE T OF G (I)\n"
        "           END-CALL\n"
        "           CALL 'Y'.\n"
        "           ENTRY 'DLITCBL' USING PCB-1.\n"
        "           DISPLAY 'CALL Z USING Q'.\n"
    )
    assert all(len(line) <= 72 for line in src.splitlines())
    (tmp_path / "CU.cbl").write_text(src, encoding="utf-8")
    assert ak.call_using_keys(ak.draft_call_using(tmp_path)["CU.cbl"]["rows"]) == {
        "L3 PROCEDURE - USING LS-A,LS-B",
        "L4 CALL X USING CONTENT:'LIT',CONTENT:WS-A,T OF G",
        "L8 ENTRY DLITCBL USING PCB-1",
    }


def test_dli_reader_resolves_on_its_own(tmp_path):
    """#3450: the key's own DL/I reading -- a function code through a copybook
    VALUE, an SSA's segment from its group VALUEs, path calls read their parents."""
    (tmp_path / "IMSF.cpy").write_text(
        "       01 FUNCS.\n          05 FUNC-GN PIC X(4) VALUE 'GN  '.\n", encoding="utf-8"
    )
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. IMSK.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       COPY IMSF.\n"
        "       01 SSA1.\n"
        "          05 FILLER PIC X(08) VALUE 'PAUTSUM0'.\n"
        "          05 FILLER PIC X(01) VALUE ' '.\n"
        "       PROCEDURE DIVISION.\n"
        "           CALL 'CBLTDLI' USING FUNC-GN PCB1 IOA SSA1.\n"
        "           EXEC DLI ISRT USING PCB(1) SEGMENT(PAUTSUM0)\n"
        "                SEGMENT(PAUTDTL1) FROM(IOB) END-EXEC.\n"
    )
    assert all(len(line) <= 72 for line in src.splitlines())
    (tmp_path / "IMSK.cbl").write_text(src, encoding="utf-8")
    entry = ak.draft_dli(tmp_path)["IMSK.cbl"]
    assert ak.dli_keys(entry["calls"]) == {
        "L10 CALL FN=FUNC-GN PCB=PCB1 IO=IOA SEG=SSA1 WHERE=- PSB=-",
        "L11 EXEC FN=ISRT PCB=1 IO=IOB SEG=PAUTSUM0,PAUTDTL1 WHERE=- PSB=-",
    }
    assert entry["segment_access"] == ["insert PAUTDTL1", "read PAUTSUM0"]


def test_ims_gen_reader_and_access_check_on_its_own(tmp_path):
    """#3477: the key's own PSB / DBD / region reading and access check -- a
    column-72 continuation, an unlabeled PCB, a region by PROGRAM-ID, a PROCOPT
    that refuses an update."""
    (tmp_path / "ims").mkdir()
    (tmp_path / "ims" / "PSBX.psb").write_text(
        "XPCB     PCB   TYPE=DB,DBDNAME=DBDX,PROCOPT=G\n"
        "         SENSEG  NAME=SEGA,PARENT=0\n"
        "         PCB   TYPE=GSAM,DBDNAME=GSX,PROCOPT=LS\n"
        "         PSBGEN  LANG=COBOL,PSBNAME=PSBX\n",
        encoding="utf-8",
    )
    (tmp_path / "ims" / "DBDX.dbd").write_text(
        "       DBD     NAME=DBDX,".ljust(71) + "C\n" + " " * 15 + "ACCESS=(HIDAM,VSAM)\n"
        "       SEGM    NAME=SEGA,PARENT=0,BYTES=(50)\n",
        encoding="utf-8",
    )
    (tmp_path / "RUN.jcl").write_text("//RUN JOB\n//S1 EXEC PGM=DFSRRC00,PARM='DLI,PGMX,PSBX'\n", encoding="utf-8")
    (tmp_path / "PGMX.cbl").write_text(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. PGMX.\n"
        "       PROCEDURE DIVISION.\n"
        "           EXEC DLI REPL USING PCB(1) SEGMENT(SEGA) FROM(IOA)\n"
        "           END-EXEC.\n",
        encoding="utf-8",
    )
    ig = ak.draft_ims_gen(tmp_path, ak.draft_dli(tmp_path))
    assert ak.ims_gen_keys(ig["ims/PSBX.psb"]["rows"]) == {
        "L1 PCB name=XPCB dbd=DBDX procopt=G type=DB",
        "L2 SENSEG name=SEGA parent=0 owner=XPCB",
        "L3 PCB name=PCB@3 dbd=GSX procopt=LS type=GSAM",
        "L4 PSBGEN name=PSBX",
    }
    assert ak.ims_gen_keys(ig["ims/DBDX.dbd"]["rows"]) == {
        "L1 DBD name=DBDX access=HIDAM",
        "L3 SEGM name=SEGA parent=0 owner=DBDX bytes=50",
    }
    assert ak.ims_gen_keys(ig["RUN.jcl"]["rows"]) == {"L2 REGION name=PGMX access=DLI psb=PSBX program=PGMX"}
    assert ig["PGMX.cbl"]["access_check"] == ["SEGA denied PSBX/XPCB:update"]


def test_data_move_reader_and_truncation_on_its_own(tmp_path):
    """#3452: the key's own data-move reading -- a keyword inside a literal, an
    EXEC block, STRING delimiters, INVALID KEY -- and its own widths: a group with
    a COPY spliced in, a REDEFINES skipped, a VALUES continuation line."""
    (tmp_path / "DATES.cpy").write_text(
        "           10 WS-DATE.\n"
        "              20 WS-MM                 PIC X(2).\n"
        "                 88 WS-VALID-MONTH     VALUES\n"
        "                                       1 THROUGH 12.\n"
        "              20 WS-MM-N REDEFINES WS-MM PIC 9(2).\n"
        "              20 WS-DD                 PIC X(2).\n",
        encoding="utf-8",
    )
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. MV.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01 WS-AREA.\n"
        "           COPY DATES.\n"
        "       01 WS-LONG               PIC X(6).\n"
        "       01 WS-SHORT              PIC X(3).\n"
        "       PROCEDURE DIVISION.\n"
        "           MOVE 'FAILED TO READ' TO WS-LONG.\n"
        "           EXEC SQL SELECT A INTO :WS-LONG FROM T END-EXEC.\n"
        "           MOVE WS-LONG TO WS-DATE.\n"
        "           MOVE WS-LONG TO WS-SHORT.\n"
        "           STRING WS-MM DELIMITED BY SIZE '/' INTO WS-LONG.\n"
        "           READ F INVALID KEY MOVE 4 TO WS-SHORT END-READ.\n"
    )
    assert all(len(line) <= 72 for line in src.splitlines())
    (tmp_path / "MV.cbl").write_text(src, encoding="utf-8")
    entry = ak.draft_data_moves(tmp_path)["MV.cbl"]
    assert entry["moves"] == [
        "L10 MOVE 'FAILED TO READ' -> WS-LONG",
        "L12 MOVE WS-LONG -> WS-DATE",
        "L13 MOVE WS-LONG -> WS-SHORT",
        "L14 STRING '/' -> WS-LONG",
        "L14 STRING WS-MM -> WS-LONG",
        "L15 MOVE 4 -> WS-SHORT",
    ]
    # WS-DATE is 4 bytes (MM + DD; the REDEFINES and the VALUES line add nothing).
    assert entry["truncations"] == [
        "L10 'FAILED TO READ' -> WS-LONG",
        "L12 WS-LONG -> WS-DATE",
        "L13 WS-LONG -> WS-SHORT",
    ]


def test_symbolic_map_units_by_arithmetic(tmp_path):
    """#3490: the key's own symbolic-map layout -- offsets by arithmetic from the
    BMS source (prefix, 3 + k + LENGTH per field, O overlaying I)."""
    (tmp_path / "SCRM.bms").write_text(
        "SCRM    DFHMSD TYPE=&&SYSPARM,LANG=COBOL,TIOAPFX=YES,EXTATT=YES\n"
        "SCRMA   DFHMDI SIZE=(24,80)\n"
        "        DFHMDF POS=(1,1),LENGTH=5,INITIAL='Name:'\n"
        "NAME    DFHMDF POS=(1,7),LENGTH=10\n"
        "        DFHMSD TYPE=FINAL\n",
        encoding="utf-8",
    )
    units = ak.draft_symbolic_maps(tmp_path)["SCRM.bms"]["layouts"]["SCRM"]
    assert units == sorted(
        ["SCRMAI @0+29", "SCRMAO @0+29", "NAMEL @12+2", "NAMEF @14+1", "NAMEA @14+1", "NAMEC @15+1",
         "NAMEP @16+1", "NAMEH @17+1", "NAMEV @18+1", "NAMEI @19+10", "NAMEO @19+10"]
    )  # fmt: skip


def test_io_move_reader_on_its_own(tmp_path):
    """#3492: the key's own reading of READ / RETURN INTO (READ's NEXT is no NEXT
    SENTENCE), WRITE / REWRITE FROM, ACCEPT [FROM]."""
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. IOK.\n"
        "       PROCEDURE DIVISION.\n"
        "           READ ACCT-FILE NEXT RECORD INTO WS-ACCT\n"
        "               AT END MOVE 'Y' TO WS-EOF END-READ.\n"
        "           WRITE OUT-REC FROM WS-LINE AFTER ADVANCING 1.\n"
        "           ACCEPT WS-DATE FROM DATE YYYYMMDD.\n"
        "           ACCEPT WS-PARM.\n"
    )
    (tmp_path / "IOK.cbl").write_text(src, encoding="utf-8")
    assert ak.draft_io_moves(tmp_path)["IOK.cbl"]["moves"] == [
        "L4 READ ACCT-FILE -> WS-ACCT",
        "L6 WRITE WS-LINE -> OUT-REC",
        "L7 ACCEPT DATE YYYYMMDD -> WS-DATE",
        "L8 ACCEPT SYSIN -> WS-PARM",
    ]


def test_dynamic_targets_on_its_own(tmp_path):
    """#3493: the key's own candidates -- an OCCURS table over a VALUE-filled
    REDEFINES, a MOVEd literal and a MOVEd VALUE item."""
    (tmp_path / "MENUCPY.cpy").write_text(
        "       01 MENU-OPTIONS.\n"
        "         05 MENU-DATA.\n"
        "           10 FILLER PIC 9(02) VALUE 1.\n"
        "           10 FILLER PIC X(08) VALUE 'PGMAAA'.\n"
        "           10 FILLER PIC 9(02) VALUE 2.\n"
        "           10 FILLER PIC X(08) VALUE 'PGMBBB'.\n"
        "         05 MENU-TABLE REDEFINES MENU-DATA.\n"
        "           10 MENU-OPT OCCURS 2 TIMES.\n"
        "             15 MENU-OPT-NUM PIC 9(02).\n"
        "             15 MENU-OPT-PGM PIC X(08).\n",
        encoding="utf-8",
    )
    (tmp_path / "MENU.cbl").write_text(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. MENU.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01 WS-NEXT PIC X(08).\n"
        "       01 LIT-SIGNON PIC X(08) VALUE 'SIGNON'.\n"
        "       COPY MENUCPY.\n"
        "       PROCEDURE DIVISION.\n"
        "           EXEC CICS XCTL PROGRAM(MENU-OPT-PGM(WS-OPT)) END-EXEC.\n"
        "           MOVE 'PGMBBB' TO WS-NEXT.\n"
        "           MOVE LIT-SIGNON TO WS-NEXT.\n"
        "           EXEC CICS XCTL PROGRAM(WS-NEXT) END-EXEC.\n",
        encoding="utf-8",
    )
    assert ak.draft_dynamic_targets(tmp_path)["MENU.cbl"]["targets"] == [
        "L12 XCTL WS-NEXT -> PGMBBB",
        "L12 XCTL WS-NEXT -> SIGNON",
        "L9 XCTL MENU-OPT-PGM -> PGMAAA",
        "L9 XCTL MENU-OPT-PGM -> PGMBBB",
    ]


def test_exhaustive_evaluate_ending_every_branch_in_a_transfer_is_terminal():
    """GENAPP LGTESTP4 NO-ADD (found by the blind census): an EVALUATE with WHEN
    OTHER whose every branch GO TOs never falls through; without WHEN OTHER, or
    with a branch that does not transfer, it can."""
    assert ak._sentence_is_terminal(
        "EVALUATE CA-RETURN-CODE WHEN 70 MOVE 'X' TO A GO TO ERROR-OUT WHEN OTHER MOVE 'Y' TO A GO TO ERROR-OUT END-EVALUATE"
    )
    assert not ak._sentence_is_terminal("EVALUATE A WHEN 70 GO TO E1 WHEN 80 GO TO E2 END-EVALUATE")
    assert not ak._sentence_is_terminal("EVALUATE A WHEN 70 GO TO E1 WHEN OTHER MOVE 1 TO B END-EVALUATE")


def test_web_service_reader_on_its_own(tmp_path):
    """#3496: the key's own reading of the web-services assistant JCL."""
    (tmp_path / "WS.jcl").write_text(
        "//J JOB\n//LS2WS EXEC DFHLS2WS\n//INPUT.SYSUT1 DD *\n PGMNAME=LGICUS01\n URI=GENAPP/LGICUS01\n"
        " REQMEM=SOAIC01\n RESPMEM=SOAIC01\n PGMINT=COMMAREA\n/*\n",
        encoding="utf-8",
    )
    assert ak.draft_web_services(tmp_path)["WS.jcl"]["services"] == [
        "L2 DFHLS2WS provider program=LGICUS01 uri=GENAPP/LGICUS01 request=SOAIC01 response=SOAIC01 interface=COMMAREA"
    ]


def test_jcics_reader_on_its_own(tmp_path):
    """#3497: the key's own line reading of JCICS -- constants, a wrapped chained
    call's line, a commented-out call."""
    src = (
        "import com.ibm.cics.server.KSDS;\n"
        'class A { static final String F = "CUST";\n'
        "  void f(Channel ch) { KSDS k = new KSDS(); k.setName(F);\n"
        "    k.read(key, h); // k.delete();\n"
        '    Program p = new Program(); p.setName("GETSCODE"); p.link(d);\n'
        "    Container c = ch\n"
        '        .getContainer("CIPB"); } }\n'
    )
    (tmp_path / "A.java").write_text(src, encoding="utf-8")
    assert ak.draft_jcics(tmp_path)["A.java"]["calls"] == [
        "L4 FILE CUST read",
        "L5 LINK GETSCODE",
        "L7 CONTAINER CIPB read",
    ]


def _cpy(tmp_path, name, lines):
    cpy = tmp_path / name
    cpy.write_text("\n".join("       " + ln for ln in lines) + "\n", encoding="utf-8")
    return cpy


def test_copybook_record_units_follow_the_engine_layout_contract(tmp_path):
    """#3602: `ROOT/NAME @offset+bytes` per elementary PIC item -- REDEFINES skipped,
    no-PIC items take their storage (POINTER 4, COMP-2 8) but are not units, OCCURS
    multiplies, an item under a PIC item is not storage, and an 88's `1 THROUGH 12.`
    continuation is not a level-1 item."""
    cpy = _cpy(tmp_path, "REC.cpy", [
        "01  ACCT-REC.",
        "    05 ACCT-ID       PIC 9(8).",
        "    05 ACCT-PTR      POINTER.",
        "    05 ACCT-RATE     COMP-2.",
        "    05 ACCT-BAL      PIC S9(7)V99 COMP-3.",
        "    05 ACCT-MONTH    PIC 99.",
        "       88 VALID-MONTH VALUES",
        "                           1 THROUGH 12.",
        "    05 ACCT-HIST     OCCURS 3 TIMES.",
        "       10 HIST-AMT   PIC 9(4) COMP.",
        "    05 ACCT-DATE     PIC X(8).",
        "    05 ACCT-DATE-N   REDEFINES ACCT-DATE PIC 9(8).",
        "    05 ACCT-SIGN     PIC 9(3)CR.",
        "    05 ACCT-NAME     PIC N(4).",
        "01  ODD-REC.",
        "    03 CA-NUM        PIC 9(10).",
        "    05 CA-UNDER      PIC 9(10).",
    ])  # fmt: skip
    assert ak.copybook_record_units(cpy) == {
        "ACCT-REC/ACCT-ID @0+8",
        "ACCT-REC/ACCT-BAL @20+5",      # after POINTER (4) and COMP-2 (8)
        "ACCT-REC/ACCT-MONTH @25+2",
        "ACCT-REC/HIST-AMT @27+2",      # first occurrence; the group spans 3 x 2
        "ACCT-REC/ACCT-DATE @33+8",     # REDEFINES ACCT-DATE-N is an overlay: not a unit
        "ACCT-REC/ACCT-SIGN @41+5",     # 9(3) + CR
        "ACCT-REC/ACCT-NAME @46+8",     # national: 2 bytes a position
        "ODD-REC/CA-NUM @0+10",         # CA-UNDER sits under a PIC item: not storage
    }  # fmt: skip


def test_refmod_units_key_the_reference_modification_text(tmp_path):
    """#3649: `L<line> VERB SOURCE(start:length) -> TARGET(start:length)`, one spelling on
    both sides (spacing around + - : normalized); a subscript is not a refmod."""
    src = tmp_path / "RM.cbl"
    src.write_text(
        "\n".join("       " + ln for ln in [
            "IDENTIFICATION DIVISION.",
            "PROGRAM-ID. RM.",
            "PROCEDURE DIVISION.",
            "    MOVE DFHCOMMAREA (LENGTH OF SHARED + 1 :",
            "                      LENGTH OF WS-OWN) TO WS-OWN.",
            "    MOVE WS-TAB (I) TO WS-X.",
            "    MOVE WS-A TO WS-B (I) (2:3).",
        ]) + "\n",
        encoding="utf-8",
    )  # fmt: skip
    assert ak.refmod_units(ak.data_move_rows(src)) == {
        "L4 MOVE DFHCOMMAREA(LENGTH OF SHARED+1:LENGTH OF WS-OWN) -> WS-OWN",
        "L7 MOVE WS-A -> WS-B(2:3)",
    }

    class M:  # an EngineDataMove's relevant fields
        line, verb, source, target = 4, "MOVE", "DFHCOMMAREA", "WS-OWN"
        source_refmod_text, target_refmod_text = "LENGTH OF SHARED + 1:LENGTH OF WS-OWN", None

    class Ef:
        data_moves = [M()]

    assert ak.engine_refmod_units(Ef()) == {"L4 MOVE DFHCOMMAREA(LENGTH OF SHARED+1:LENGTH OF WS-OWN) -> WS-OWN"}


def test_ridfld_units_key_the_cics_file_key_operand(tmp_path):
    """#3649: `L<line> VERB FILE NAME RIDFLD=OPERAND`, from this tool's EXEC CICS reader;
    the engine side parses cics_resource_data.attributes, nested parentheses included."""
    src = tmp_path / "RF.cbl"
    src.write_text(
        "\n".join("       " + ln for ln in [
            "IDENTIFICATION DIVISION.",
            "PROGRAM-ID. RF.",
            "PROCEDURE DIVISION.",
            "    EXEC CICS READ FILE('ACCTDAT') INTO(WS-REC)",
            "         RIDFLD(WS-KEY(1:4)) END-EXEC.",
            "    EXEC CICS WRITE FILE('LOGF') FROM(WS-REC) END-EXEC.",
        ]) + "\n",
        encoding="utf-8",
    )  # fmt: skip
    assert ak.ridfld_units(ak.cics_resource_ops(src)) == {"L4 READ FILE ACCTDAT RIDFLD=WS-KEY(1:4)"}

    class Op:  # an EngineCicsResource's relevant fields
        def __init__(self, kind, attributes, line=4, verb="READ", name="ACCTDAT"):
            self.kind, self.attributes, self.line, self.verb, self.name = kind, attributes, line, verb, name

    class Ef:
        cics_resources = [Op("FILE", "LENGTH(LENGTH OF WS-REC) RIDFLD(WS-KEY (1:4)) KEYLENGTH(4)"),
                          Op("QUEUE", "RIDFLD(X)")]  # fmt: skip

    assert ak.engine_ridfld_units(Ef()) == {"L4 READ FILE ACCTDAT RIDFLD=WS-KEY(1:4)"}  # spacing normalized


def test_a_copybook_that_copies_is_not_keyed(tmp_path):
    assert (
        ak.copybook_record_units(_cpy(tmp_path, "OUTER.cpy", ["01 OUTER.", "   COPY INNER.", "   05 X PIC X."])) is None
    )
    assert "OUTER.cpy" not in ak.draft_copybook_layouts(tmp_path)


def test_copybook_layout_units_lay_out_an_ibm_symbolic_map(tmp_path):
    """#3575: the oracle for symbolic maps -- IBM's DFHMAPS output read as storage."""
    cpy = tmp_path / "SMAP.cpy"
    cpy.write_text(
        "\n".join(
            "       " + ln
            for ln in (
                "01  SMAPI.",
                "    02  FILLER PIC X(12).",
                "    02  NAMEL    COMP  PIC  S9(4).",
                "    02  NAMEF    PICTURE X.",
                "    02  FILLER REDEFINES NAMEF.",
                "      03 NAMEA    PICTURE X.",
                "    02  NAMEI  PIC X(8).",
                "01  SMAPO REDEFINES SMAPI.",
                "    02  FILLER PIC X(12).",
                "    02  FILLER PICTURE X(3).",
                "    02  NAMEO  PIC X(8).",
            )
        )
        + "\n"
    )
    assert ak.copybook_layout_units(cpy) == {
        "SMAPI @0+23", "NAMEL @12+2", "NAMEF @14+1", "NAMEA @14+1", "NAMEI @15+8",
        "SMAPO @0+23", "NAMEO @15+8",
    }  # fmt: skip
    assert (ak._pic_bytes("S9(4)", "COMP"), ak._pic_bytes("S9(9)", "BINARY"), ak._pic_bytes("9(5)", "COMP-3")) == (
        2,
        4,
        3,
    )


def test_a_sign_separate_display_item_takes_its_own_byte(tmp_path):
    """#3649 census (CBSA ABNDINFO): `PIC S9(8) DISPLAY SIGN LEADING SEPARATE` is 9 bytes;
    an embedded sign (no SEPARATE) and a packed item are unchanged."""
    cpy = _cpy(tmp_path, "SIGN.cpy", [
        "03 RESPCODE    PIC S9(8) DISPLAY",
        "       SIGN LEADING SEPARATE.",
        "03 PLAIN       PIC S9(8).",
        "03 TRAILER     PIC S9(3) SIGN IS TRAILING SEPARATE CHARACTER.",
        "03 PACKED      PIC S9(7) COMP-3.",
    ])  # fmt: skip
    assert ak.copybook_record_units(cpy) == {
        "RESPCODE/RESPCODE @0+9", "PLAIN/PLAIN @0+8", "TRAILER/TRAILER @0+4", "PACKED/PACKED @0+4",
    }  # fmt: skip


def test_a_function_result_reference_modification_is_a_refmod(tmp_path):
    """#3649 census (CardDemo CBIMPORT): `FUNCTION CURRENT-DATE(1:4)` reference-modifies the
    result; a colon inside an argument (`NUMVAL(WS-X(1:3))`) is not the function's refmod."""
    src = tmp_path / "FN.cbl"
    src.write_text(
        "\n".join("       " + ln for ln in [
            "IDENTIFICATION DIVISION.",
            "PROGRAM-ID. FN.",
            "PROCEDURE DIVISION.",
            "    MOVE FUNCTION CURRENT-DATE(1:4) TO WS-D(1:4).",
            "    MOVE FUNCTION UPPER-CASE(WS-N)(2:3) TO WS-U.",
            "    MOVE FUNCTION NUMVAL(WS-X(1:3)) TO WS-V.",
        ]) + "\n",
        encoding="utf-8",
    )  # fmt: skip
    rows = ak.data_move_rows(src)
    assert ak.refmod_units(rows) == {
        "L4 MOVE FUNCTION CURRENT-DATE(1:4) -> WS-D(1:4)",
        "L5 MOVE FUNCTION UPPER-CASE(2:3) -> WS-U",
    }
    assert "L6 MOVE FUNCTION NUMVAL -> WS-V" in ak.data_move_keys(rows)
