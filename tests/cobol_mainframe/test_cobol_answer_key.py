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
def test_both_corpora_have_a_key():
    assert {p.stem for p in KEYS} == {"zopeneditor-sample", "cics-banking-sample-application-cbsa"}


@pytest.mark.parametrize("key_path", KEYS, ids=lambda p: p.stem)
def test_key_integrity(key_path):
    key = json.loads(key_path.read_text(encoding="utf-8"))
    assert key["schema_version"] == ak.SCHEMA_VERSION
    assert re.fullmatch(r"[0-9a-f]{40}", key["ref"]), "pin the corpus to a full commit"
    assert key["programs"]
    for rel, prog in key["programs"].items():
        where = f"{key_path.stem}:{rel}"
        assert prog["verification"]["status"] == "validated", f"{where} is still a draft"
        assert prog["verification"]["by"] and prog["verification"]["at"]
        names = [u["name"] for u in prog["units"]]
        assert len(names) == len(set(names)), f"{where}: duplicate unit"
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
