"""DFSORT CH fields under EBCDIC collation (det/dfsort.py, #4268, #4035): DFSORT orders and compares CH fields by their
EBCDIC bytes, the oracle's data is ASCII. A step that compares a CH field is lowered under an EBCDIC PROGRAM COLLATING
SEQUENCE, so GnuCOBOL (the oracle) and the det port both order letters before digits as IBM does, and the port stops by
name on the characters the two EBCDIC tables place differently (register D1). BI is a byte-value compare the alphabet
would reorder: a step comparing both is refused. The whole class: a CH SORT key (ascending, descending), a MERGE key and
an INCLUDE / OMIT CH operand (against a constant, against another field)."""

from __future__ import annotations

import os
import random
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_det_programs import _cobol
from test_dfsort_4268 import _java_step, _need_java

from gitgalaxy.tools.cobol_to_java.det import dfsort as D

RECLEN = 8
EB = "PROGRAM COLLATING SEQUENCE IS EB"


def _lines(src: str) -> list[str]:
    return [x[7:].strip() for x in src.splitlines()]


@pytest.mark.parametrize(
    "sysin",
    [
        " SORT FIELDS=(1,4,CH,A)\n",
        " SORT FIELDS=(1,4,CH,D),EQUALS\n",
        " SORT FIELDS=(5,2,ZD,A,1,4,CH,A)\n",
        " SORT FIELDS=COPY\n OMIT COND=(1,1,CH,EQ,C'A')\n",
        " SORT FIELDS=(1,2,ZD,A)\n INCLUDE COND=(3,2,CH,GE,5,2,CH)\n",
        " SORT FIELDS=(1,2,PD,A)\n INCLUDE COND=(5,1,CH,LT,C'a',OR,6,1,CH,EQ,X'F1')\n",
    ],
)
def test_a_step_that_compares_a_ch_field_is_lowered_under_the_ebcdic_alphabet(sysin):
    src = D.cobol_program(D.parse(sysin), RECLEN, ["SORTIN"])
    lines = _lines(src)
    assert EB + "." in lines and "ALPHABET EB IS EBCDIC." in lines
    assert lines.index("OBJECT-COMPUTER. GG") < lines.index(EB + ".") < lines.index("SPECIAL-NAMES.")
    assert lines.index("CONFIGURATION SECTION.") < lines.index("INPUT-OUTPUT SECTION.")


def test_a_merge_on_a_ch_key_is_lowered_under_the_ebcdic_alphabet():
    src = D.cobol_program(D.parse(" MERGE FIELDS=(1,4,CH,A),EQUALS\n"), RECLEN, ["SORTIN01", "SORTIN02"])
    assert EB + "." in _lines(src)


@pytest.mark.parametrize(
    "sysin",
    [
        " SORT FIELDS=(1,4,BI,A)\n",
        " SORT FIELDS=(1,2,ZD,A,5,2,PD,D)\n",
        " SORT FIELDS=(1,2,ZD,A)\n INCLUDE COND=(3,2,PD,GT,5)\n",
        " SORT FIELDS=(1,4,BI,A)\n INCLUDE COND=(5,1,BI,EQ,X'F1')\n",
        " SORT FIELDS=COPY\n",
    ],
)
def test_a_step_that_compares_no_ch_field_keeps_the_native_order(sysin):
    src = D.cobol_program(D.parse(sysin), RECLEN, ["SORTIN"])
    assert "COLLATING" not in src and "ALPHABET" not in src


@pytest.mark.parametrize(
    "sysin",
    [
        " SORT FIELDS=(1,2,CH,A,3,2,BI,A)\n",
        " SORT FIELDS=(1,2,BI,A)\n INCLUDE COND=(3,2,CH,EQ,C'AB')\n",
        " SORT FIELDS=(1,2,CH,A)\n OMIT COND=(3,2,BI,EQ,5,2,BI)\n",
        " SORT FIELDS=COPY\n INCLUDE COND=(1,2,CH,EQ,C'AB',AND,3,2,BI,EQ,X'0001')\n",
    ],
)
def test_ch_and_bi_in_one_step_are_refused_by_name(sysin):
    with pytest.raises(D.Refused, match="CH and BI fields compared in one step"):
        D.cobol_program(D.parse(sysin), RECLEN, ["SORTIN"])


# Letters, digits, a space: where IBM's EBCDIC order (lower case, upper case, digits) and ASCII's (digits, upper, lower)
# are far apart, and GnuCOBOL's EBCDIC table agrees with IBM's.
ALPHABET = "ABZabz0159 "


def _records(n: int = 40) -> list[bytes]:
    rng = random.Random(4035)
    keys = set()
    while len(keys) < n:
        keys.add("".join(rng.choice(ALPHABET) for _ in range(4)))
    return [(k + "wxyz").encode() for k in sorted(keys, key=lambda _: rng.random())]


def _ebcdic(rec: bytes) -> bytes:
    return rec[:4].decode("ascii").encode("cp037")


def _sorted(recs: list[bytes], descending: bool = False) -> list[bytes]:
    return sorted(recs, key=_ebcdic, reverse=descending)


def _split(data: bytes) -> list[bytes]:
    return [data[i : i + RECLEN] for i in range(0, len(data), RECLEN)]


def _cases() -> dict[str, tuple[str, dict[str, bytes], list[bytes]]]:
    """Step name -> (SYSIN, input DDs, the records IBM's EBCDIC order writes)."""
    recs = _records()
    half = (_sorted(recs[::2]), _sorted(recs[1::2]))
    ge = lambda r: r[0:1].decode().encode("cp037") >= "a".encode("cp037")  # noqa: E731
    return {
        "SORTCH": (" SORT FIELDS=(1,4,CH,A),EQUALS\n", {"SORTIN": b"".join(recs)}, _sorted(recs)),
        "SORTCHD": (" SORT FIELDS=(1,4,CH,D),EQUALS\n", {"SORTIN": b"".join(recs)}, _sorted(recs, True)),
        "MERGECH": (" MERGE FIELDS=(1,4,CH,A),EQUALS\n", {"SORTIN01": b"".join(half[0]), "SORTIN02": b"".join(half[1])},
                    _sorted(recs)),
        # 'a' in EBCDIC sits below every upper-case letter and digit and above no lower-case one: GE keeps the
        # lower-case letters from 'a' up, the upper-case letters and the digits; in ASCII it would keep only 'a'..'z'
        "INCLUDECH": (" SORT FIELDS=(1,4,CH,A),EQUALS\n INCLUDE COND=(1,1,CH,GE,C'a')\n", {"SORTIN": b"".join(recs)},
                      [r for r in _sorted(recs) if ge(r)]),
        "OMITCH": (" SORT FIELDS=(1,4,CH,A),EQUALS\n OMIT COND=(1,1,CH,GE,C'a')\n", {"SORTIN": b"".join(recs)},
                   [r for r in _sorted(recs) if not ge(r)]),
        "FIELDCH": (" SORT FIELDS=COPY\n INCLUDE COND=(1,1,CH,LT,2,1,CH)\n", {"SORTIN": b"".join(recs)},
                    [r for r in recs if r[0:1].decode().encode("cp037") < r[1:2].decode().encode("cp037")]),
    }  # fmt: skip


@pytest.mark.slow(reason="javac of the batch runtime and a GnuCOBOL container per step")
@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1" or not shutil.which("docker"),
                    reason="needs EQUIVALENCE_E2E=1 and Docker")  # fmt: skip
@pytest.mark.parametrize("step", ["SORTCH", "SORTCHD", "MERGECH", "INCLUDECH", "OMITCH", "FIELDCH"])
def test_ch_steps_write_ibms_ebcdic_order_in_the_oracle_and_the_port(step, tmp_path):
    _need_java()
    sysin, inputs, want_records = _cases()[step]
    assert want_records
    if step in ("INCLUDECH", "OMITCH", "FIELDCH"):  # the condition must actually select, or the case proves nothing
        assert len(want_records) < len(_split(next(iter(inputs.values()))))
    ctl = D.parse(sysin)
    src = D.cobol_program(ctl, RECLEN, list(inputs))
    cob = tmp_path / "cobol"
    cob.mkdir()
    for dd, body in inputs.items():
        (cob / dd).write_bytes(body)
    _cobol(src, cob)
    oracle = (cob / "SORTOUT").read_bytes()
    (tmp_path / "port").mkdir()
    port = _java_step(src, tmp_path / "port", inputs, "SORTOUT")
    assert _split(oracle) == want_records, "the oracle did not write IBM's EBCDIC order"
    assert port == oracle


@pytest.mark.slow(reason="javac of the batch runtime")
@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1" or not shutil.which("docker"),
                    reason="needs EQUIVALENCE_E2E=1 and Docker")  # fmt: skip
@pytest.mark.parametrize(
    "sysin, data, named",
    [
        # '-' and '^' are placed the other way round by GnuCOBOL's EBCDIC table and IBM's: the port stops by name
        (" SORT FIELDS=(1,4,CH,A),EQUALS\n", [b"-AAAwxyz", b"^AAAwxyz"], "S-FILE COLLATING SEQUENCE EB: keys"),
        (" SORT FIELDS=COPY\n INCLUDE COND=(1,1,CH,GT,C'-')\n", [b"^AAAwxyz"], "PROGRAM COLLATING SEQUENCE EB"),
    ],
)
def test_where_the_two_ebcdic_tables_disagree_the_port_stops_by_name(sysin, data, named, tmp_path):
    _need_java()
    src = D.cobol_program(D.parse(sysin), RECLEN, ["SORTIN"])
    with pytest.raises(subprocess.CalledProcessError) as e:
        _java_step(src, tmp_path, {"SORTIN": b"".join(data)}, "SORTOUT")
    assert named in e.value.stderr
