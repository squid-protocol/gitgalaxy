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
