"""The Devin-port runner's adapter (tests/tools/devin_port.py): only marshalling, and checked here."""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import devin_port as dp  # noqa: E402

CASE = {"clock": "2022/07/18 10:30:15.00", "parm": "2022071800", "data_encoding": "latin-1"}


def test_the_frozen_clock_in_each_ports_own_form():
    assert dp.clock_arg(CASE, "%Y-%m-%d %H:%M:%S") == "2022-07-18 10:30:15"
    assert dp.clock_arg(CASE, "%Y-%m-%d-%H.%M.%S.000000") == "2022-07-18-10.30.15.000000"


def test_an_indexed_input_is_handed_over_in_primary_key_order():
    data = b"B2x" + b"A1y" + b"A0z"
    assert dp.key_ordered(data, 3, {"offset": 0, "length": 2}) == b"A0zA1yB2x"


def test_an_abend_is_read_the_way_the_port_reports_it():
    by_message = {"abend": {"stderr": r"CEE3ABD: USER ABEND U(\d+)"}}
    by_exit = {"abend": {"exit": 231, "code": 999}}
    done = subprocess.CompletedProcess([], 231, b"", b"CEE3ABD: USER ABEND U999\n")
    assert dp.abend_code(by_message, done) == 999
    assert dp.abend_code(by_exit, done) == 999
    assert dp.abend_code(by_exit, subprocess.CompletedProcess([], 4, b"", b"")) is None


def test_the_command_line_is_the_ports_own():
    port = {"now": "%Y-%m-%d %H:%M:%S"}
    dds = {"ACCTFILE": Path("/w/ACCTFILE.dat"), "TRANSACT": Path("/w/TRANSACT.dat")}
    argv = dp.command(port, dp._dd_launcher("CBACT04C"), CASE, dds, Path("/w/out"))
    assert argv == ["CBACT04C", "--dd", "ACCTFILE=/w/ACCTFILE.dat", "--dd", "TRANSACT=/w/TRANSACT.dat",
                    "--parm", "2022071800", "--now", "2022-07-18 10:30:15"]  # fmt: skip


def test_a_signed_number_shown_gnucobols_way_is_classed_apart():
    cobol = b"BAL :00000001940{\nCOUNT :000000003\n"
    java = b"BAL :000000019400+\nCOUNT :000000004\n"
    c = dp.sysout_classes(CASE, cobol, java)
    assert (c["sign-display"], c["other"]) == (1, 1)


def test_hex_packed_lines_become_the_copybook_record():
    """A packed field written as hex digits (#214's OUT-ACCT-CURR-CYC-DEBIT) back to its 7 bytes, the text around it
    kept: the record is the copybook's 107 bytes."""
    line = b"A" * 90 + b"0000000252500C" + b" " * 10 + b"\n"
    rec = dp.lines_hex_packed(line, 107, [(90, 7)])
    assert len(rec) == 107 and rec[90:97] == bytes.fromhex("0000000252500C") and rec[97:] == b" " * 10
    assert dp.lines_hex_packed(b"A" * 90 + b"ZZZZZZZZZZZZZZ" + b" " * 10 + b"\n", 107, [(90, 7)]).startswith(b"A" * 90 + b"Z")


def test_a_zos_rdw_is_reframed_as_gnucobol_frames_it():
    rdw = b"\x00\x10\x00\x00" + b"x" * 12 + b"\x00\x2b\x00\x00" + b"y" * 39  # the length counts the 4-byte header
    assert dp.vb_rdw(rdw) == dp.gnucobol_frame([b"x" * 12, b"y" * 39])
    assert dp.vb_rdw(b"\x00\x02\x00\x00") == b"\x00\x02\x00\x00"  # a length below the header's: not an RDW
