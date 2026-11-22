"""The IDCAMS step model's path order against GnuCOBOL's alternate keys (#8881, SC23-6846-60 "BLDINDEX" / "DEFINE PATH").

The model (det/idcams_model.py) reads a path as the base KSDS's records in alternate-key order, records sharing a key in
the base's (primary-key) order. GnuCOBOL has no IDCAMS, but its indexed files carry `ALTERNATE RECORD KEY ... WITH
DUPLICATES` (Berkeley DB), which a program can read back with START on the alternate key and READ NEXT: an independent
executor of the same order. The always-run half pins the model's order on each input; the `EQUIVALENCE_E2E=1` half runs
the COBOL reader under GnuCOBOL and requires the same records in the same order.

Not checked: an ESDS base (GnuCOBOL has no ESDS alternate keys, so its arrival-order rule stays an assumption of the
model, register F6) and UNIQUEKEY over duplicates (refused by the model, never executed)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gitgalaxy.tools.cobol_to_java.det import idcams_model as M

IMAGE = "gitgalaxy-gnucobol:3"
E2E = pytest.mark.skipif(
    os.environ.get("EQUIVALENCE_E2E") != "1" or not shutil.which("docker"),
    reason="runs GnuCOBOL in Docker (EQUIVALENCE_E2E=1)",
)
BASE, AIX, PATH = "APP.BASE", "APP.BASE.AIX", "APP.BASE.AIX.PATH"
LEN = 10  # records of 10 bytes: a 4-byte primary key, a 4-byte alternate key, 2 bytes of data

# (primary key offset, alternate key offset): the keys never overlap
LAYOUTS = [(0, 4), (4, 0), (0, 6), (2, 6)]


def make(pk_off: int, ak_off: int, rows: list[tuple[str, str]]) -> list[bytes]:
    out = []
    for pk, ak in rows:
        buf = bytearray(b"..........")
        buf[pk_off : pk_off + 4] = pk.encode()
        buf[ak_off : ak_off + 4] = ak.encode()
        out.append(bytes(buf))
    return out


CASES = {
    "distinct": [("0001", "DDDD"), ("0002", "BBBB"), ("0003", "AAAA"), ("0004", "CCCC")],
    "duplicates": [("0001", "BBBB"), ("0002", "AAAA"), ("0003", "BBBB"), ("0004", "CCCC"), ("0005", "AAAA")],
    "one record": [("0001", "ZZZZ")],
    "all equal": [("0001", "SAME"), ("0002", "SAME"), ("0003", "SAME"), ("0004", "SAME")],
    "descending alternate": [("0001", "EEEE"), ("0002", "DDDD"), ("0003", "CCCC"), ("0004", "BBBB")],
    "digits and blanks": [("0001", "  A1"), ("0002", "0001"), ("0003", "  A1"), ("0004", "9999"), ("0005", "0001")],
}


def model_order(pk_off: int, ak_off: int, records: list[bytes]) -> list[bytes]:
    """The path's records after the three steps of the nightly's AIX job, run through the step model."""
    catalog: dict[str, M.Cluster | M.Aix | M.Path] = {
        BASE: M.Cluster(BASE, True, 4, pk_off, LEN, LEN, sorted(records, key=lambda r: r[pk_off : pk_off + 4]))
    }
    decks = (
        f"  DEFINE ALTERNATEINDEX (NAME({AIX}) RELATE({BASE}) -\n"  # SYSIN is read to column 72
        f"    KEYS(4 {ak_off}) NONUNIQUEKEY UPGRADE -\n"
        "    RECORDSIZE(40 40) VOLUMES(VOL001) CYLINDERS(5 1))\n",
        f"  DEFINE PATH (NAME({PATH}) PATHENTRY({AIX}))\n",
        f"  BLDINDEX INDATASET({BASE}) OUTDATASET({AIX})\n",
    )
    for sysin in decks:
        res = M.run(sysin, catalog)
        assert res.rc == 0, res.log
        catalog = res.catalog
    return M.path_records(catalog, PATH)


def _fields(pk_off: int, ak_off: int) -> str:
    """The FD record: the two keys at their offsets, FILLER between."""
    parts, pos = [], 0
    for name, off in sorted((("R-PK", pk_off), ("R-AK", ak_off)), key=lambda t: t[1]):
        if off > pos:
            parts.append(f"           05  FILLER            PIC X({off - pos}).")
        parts.append(f"           05  {name}              PIC X(4).")
        pos = off + 4
    if pos < LEN:
        parts.append(f"           05  FILLER            PIC X({LEN - pos}).")
    return "\n".join(parts)


def cobol_reader(pk_off: int, ak_off: int, records: list[bytes]) -> str:
    """A program that loads the records in primary-key order into an indexed file with a duplicate-allowing alternate
    key and prints them back through that key (START at its lowest value, READ NEXT to the end)."""
    loads = "\n".join(
        f"           MOVE '{r.decode()}' TO REC\n           WRITE REC\n"
        "           IF FS NOT = '00' AND FS NOT = '02'\n"  # 02: the alternate key repeats, the write succeeded
        "               DISPLAY 'LOADFAIL' FS STOP RUN END-IF"
        for r in sorted(records, key=lambda r: r[pk_off : pk_off + 4])
    )
    return f"""       IDENTIFICATION DIVISION.
       PROGRAM-ID. AIXPATH.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT F ASSIGN TO 'base.dat'
               ORGANIZATION IS INDEXED
               ACCESS MODE IS DYNAMIC
               RECORD KEY IS R-PK
               ALTERNATE RECORD KEY IS R-AK WITH DUPLICATES
               FILE STATUS IS FS.
       DATA DIVISION.
       FILE SECTION.
       FD  F.
       01  REC.
{_fields(pk_off, ak_off)}
       WORKING-STORAGE SECTION.
       01  FS                    PIC XX.
       PROCEDURE DIVISION.
           OPEN OUTPUT F
           CLOSE F
           OPEN I-O F
{loads}
           MOVE LOW-VALUES TO R-AK
           START F KEY >= R-AK
           IF FS NOT = '00' DISPLAY 'STARTFAIL' FS STOP RUN END-IF
           PERFORM UNTIL FS NOT = '00'
               READ F NEXT
               IF FS = '00' OR FS = '02' DISPLAY 'REC=' REC
               END-IF
               IF FS = '02' MOVE '00' TO FS END-IF
           END-PERFORM
           CLOSE F
           STOP RUN.
"""


@pytest.mark.parametrize("layout", LAYOUTS)
@pytest.mark.parametrize("name", sorted(CASES))
def test_the_model_reads_a_path_in_alternate_key_then_primary_key_order(name, layout):
    pk_off, ak_off = layout
    records = make(pk_off, ak_off, CASES[name])
    got = model_order(pk_off, ak_off, records)
    assert sorted(got) == sorted(records)  # nothing lost or invented
    # the definition of the order, stated independently of the model's own sort: stable over the base's key order
    base = sorted(records, key=lambda r: r[pk_off : pk_off + 4])
    want = []
    for ak in sorted({r[ak_off : ak_off + 4] for r in base}):
        want += [r for r in base if r[ak_off : ak_off + 4] == ak]
    assert got == want


def test_every_line_of_the_reader_is_fixed_format():
    src = cobol_reader(0, 4, make(0, 4, CASES["duplicates"]))
    for n, ln in enumerate(src.splitlines(), 1):
        assert len(ln) <= 72, (n, ln)


@E2E
@pytest.mark.parametrize("layout", LAYOUTS)
@pytest.mark.parametrize("name", sorted(CASES))
def test_gnucobol_alternate_keys_read_the_same_order(name, layout, tmp_path):
    pk_off, ak_off = layout
    records = make(pk_off, ak_off, CASES[name])
    (tmp_path / "prog.cbl").write_text(cobol_reader(pk_off, ak_off, records))
    script = "cobc -x -std=ibm -fsign=EBCDIC -o prog prog.cbl && ./prog"
    run = subprocess.run(  # noqa: S603
        ["docker", "run", "--rm", "-v", f"{tmp_path}:/w", "-w", "/w", IMAGE, "sh", "-c", script],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    got = [ln[4:].encode() for ln in run.stdout.splitlines() if ln.startswith("REC=")]
    assert got == model_order(pk_off, ak_off, records)
