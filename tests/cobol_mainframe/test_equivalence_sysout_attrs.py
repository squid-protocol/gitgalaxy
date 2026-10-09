"""#4056 and #4053: what the equivalence proofs compare besides records and screen text, found missing by mutation
testing (#4047) -- a batch step's DISPLAY output (SYSOUT), and a SEND MAP's attributes, colour, highlight, cursor
and options.

The pure parts are pinned here. The DISPLAY model (tests/equivalence/faults/ggdisplay.c) runs under Docker
GnuCOBOL when EQUIVALENCE_E2E=1, against IBM's documented text.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence as eq
import equivalence_cics as ec


def test_sysout_is_compared_line_by_line_trailing_blanks_aside():
    cobol = b"START OF EXECUTION OF PROGRAM X   \nINVALID CARD NUMBER : 0500\nlibcob: warning: x\n\n"
    same = b"START OF EXECUTION OF PROGRAM X\nINVALID CARD NUMBER : 0500\n"
    s = eq.compare_sysout(cobol, same, "latin-1")
    assert s["compared"] and not s["diffs"] and s["lines"] == 2  # libcob's own message is not the program's
    s = eq.compare_sysout(cobol, b"START OF EXECUTION OF PROGRAM X\nXNVALID CARD NUMBER : 0500\n", "latin-1")
    assert s["diffs"] == [{"line": 2, "cobol": "INVALID CARD NUMBER : 0500", "java": "XNVALID CARD NUMBER : 0500"}]
    s = eq.compare_sysout(cobol, b"START OF EXECUTION OF PROGRAM X\n", "latin-1")
    assert s["diffs"][0] == {"line": 2, "cobol": "INVALID CARD NUMBER : 0500", "java": None}  # a missing DISPLAY


def test_sysout_records_are_split_on_a_plain_lf_under_an_ebcdic_charset():
    """#4698: the record separator is the capture's framing (0x0A on both sides), not a character of the code page."""
    cobol = "HELLO\nWORLD  \n".replace("\n", "\x00").encode("cp037").replace(b"\x00", b"\n")
    java = "HELLO\x00WORLD\x00".encode("cp037").replace(b"\x00", b"\n")
    s = eq.compare_sysout(cobol, java, "cp037")
    assert s["compared"] and not s["diffs"] and s["lines"] == 2


def test_sysout_is_not_compared_where_ibms_text_is_not_modelled():
    s = eq.compare_sysout(b"FL=1.5\nGGDISPLAY-NOT-MODELLED\n", b"FL=1.5E0\n", "latin-1")
    assert not s["compared"] and "not modelled" in s["why"] and not s["diffs"]


def test_a_run_whose_sysout_differs_is_not_equal_even_after_an_abend():
    case = {"program": "P", "datasets": {}}
    cobol = {"ABEND": b"U0999", "SYSOUT": b"ERROR OPENING X\nABENDING PROGRAM\n"}
    java = {"ABEND": b"U0999", "SYSOUT": b"ERROR OPENING X\n"}
    run = eq.compare_run(case, Path("."), cobol, java)
    assert not run["ok"] and "SYSOUT: 1/2 lines equal" in run["summary"]
    assert eq.compare_run({**case, "sysout": False}, Path("."), cobol, java)["ok"]  # a case may opt out


def test_the_ticket_asks_for_sysout_not_a_log_line():
    from gitgalaxy.tools.cobol_to_java import cobol_to_java_port_tickets as pt
    from gitgalaxy.tools.cobol_to_java import port_runner

    rules = " ".join(pt.PORTING_RULES)
    assert "Sysout.display" in rules and "a DISPLAY becomes a log line" not in rules
    assert "batch/Sysout.java" in port_runner._RUNTIME_HELPERS


def _event(subfields, options=("ERASE",), cursor=None):
    return {"event": "SEND-MAP", "map": "M", "screen": {}, "subfields": subfields, "options": list(options),
            "cursor": cursor}  # fmt: skip


def test_a_send_maps_colour_cursor_and_options_are_compared():
    cobol = [_event({"ERRMSG": {"color": 0xF2}, "ACCTSID": {"attr": 0xC1, "length": -1}}, ("CURSOR", "ERASE"))]
    java_ok = [{"event": "SEND-MAP", "map": "M", "screen": {}, "options": ["ERASE", "CURSOR"],
                "subfields": {"ERRMSG": {"color": 0xF2}, "ACCTSID": {"attr": 0xC1, "length": -1}}}]  # fmt: skip
    assert ec.compare_events(cobol, java_ok)["equal"] == 1
    wrong = [{**java_ok[0], "subfields": {"ERRMSG": {"color": 0xF4}, "ACCTSID": {"attr": 0xC1, "length": -1}}}]
    d = ec.compare_events(cobol, wrong)["diffs"][0]["fields"]
    assert d == [{"field": "subfields.ERRMSG", "cobol": {"color": 0xF2}, "java": {"color": 0xF4}}]
    no_cursor = [{**java_ok[0], "options": ["ERASE"]}]
    assert ec.compare_events(cobol, no_cursor)["diffs"][0]["fields"][0]["field"] == "options"


def test_unset_subfields_are_unset_on_both_sides():
    """X'00' (LOW-VALUES: the map's own) and a space are "not set"; a length other than -1 is not the cursor."""
    assert ec.java_subfields({"A": {"color": 0, "hilight": 0x40, "length": 5}, "B": {"length": -1}}) == {
        "B": {"length": -1}
    }
    assert ec.compare_events([_event({})], [_event(None)])["equal"] == 1


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1" or not shutil.which("docker"), reason="needs Docker")
def test_display_is_written_as_ibm_documents_it(tmp_path):
    """IBM Enterprise COBOL Language Reference, DISPLAY: an operand's external representation; binary and packed
    operands as external decimal. GnuCOBOL alone writes 012- / -00007; with ggdisplay.c, IBM's text."""
    program = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. D.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 A PIC S9(3) VALUE -12.
       01 B PIC S9(3) VALUE 12.
       01 C PIC 9(3) VALUE 12.
       01 E PIC S9(3)V99 VALUE -1.5.
       01 F PIC S9(4) COMP VALUE -7.
       01 P PIC S9(5)V99 COMP-3 VALUE -123.45.
       01 H PIC S9(3) SIGN LEADING SEPARATE VALUE -12.
       01 FL COMP-2 VALUE 1.5.
       PROCEDURE DIVISION.
           DISPLAY A ' ' B ' ' C ' ' E ' ' F ' ' P ' ' H.
           DISPLAY FL.
           STOP RUN.
"""
    (tmp_path / "D.cbl").write_text(program, encoding="ascii")
    shutil.copy(eq.FAULTS_DIR / "ggdisplay.c", tmp_path / "ggdisplay.c")
    script = ("gcc -shared -fPIC -O2 -o g.so ggdisplay.c -ldl && cobc -x -std=ibm -fsign=EBCDIC -o d D.cbl "
              "&& LD_PRELOAD=/w/g.so ./d")  # fmt: skip
    proc = subprocess.run(["docker", "run", "--rm", "-v", f"{tmp_path}:/w", "-w", "/w", eq.IMAGE, "bash", "-c",  # noqa: S603, S607
                           script], capture_output=True, text=True, check=False)  # fmt: skip
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.splitlines() == ["01K 01B 012 0015} 000P 001234N -012", "1.5", "GGDISPLAY-NOT-MODELLED"]
