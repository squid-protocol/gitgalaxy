"""An IDCAMS REPRO step (det/idcams.py, #4268): the command parsed to the two DDs it copies, every other command and
parameter refused by name. The byte-for-byte proof against GnuCOBOL is the IDCAMS step of test_dfsort_4268.py."""

from __future__ import annotations

import pytest

from gitgalaxy.tools.cobol_to_java.det import dfsort as D
from gitgalaxy.tools.cobol_to_java.det import idcams as I


@pytest.mark.parametrize(
    "sysin",
    [
        " REPRO INFILE(IN) OUTFILE(OUT)\n",
        " repro infile(in) outfile(out)\n",
        " REPRO IFILE(IN) OFILE(OUT)\n",
        " REPRO OUTFILE(OUT) INFILE(IN)\n",
        " REPRO -\n   INFILE(IN) -\n   OUTFILE(OUT)\n",
        " REPRO +\n   INFILE(IN) +\n   OUTFILE(OUT)\n",
        "/* copy the extract */\n REPRO INFILE(IN) /* from */ OUTFILE(OUT)\n\n",
        " REPRO INFILE( IN ) OUTFILE( OUT )\n",
    ],
)
def test_repro_is_a_copy_of_the_input_dd_to_the_output_dd(sysin):
    r = I.parse(sysin)
    assert (r.infile, r.outfile) == ("IN", "OUT")
    assert r.control == D.iebgener()  # the same COPY model, lowered by dfsort.cobol_program


def test_the_lowered_program_copies_the_named_dds():
    r = I.parse(" REPRO INFILE(INDD) OUTFILE(OUTDD)\n")
    src = D.cobol_program(r.control, 80, [r.infile], r.outfile)
    assert "ASSIGN TO INDD" in src and "ASSIGN TO OUTDD" in src


@pytest.mark.parametrize(
    ("sysin", "why"),
    [
        ("", "no IDCAMS command"),
        ("/* nothing */\n", "no IDCAMS command"),
        (" DEFINE CLUSTER(NAME(A.B)) -\n VOLUMES(V1)\n", "the IDCAMS DEFINE command"),
        (" DELETE A.B\n", "the IDCAMS DELETE command"),
        (" ALTER A.B NEWNAME(C.D)\n", "the IDCAMS ALTER command"),
        (" LISTCAT ENTRIES(A.B)\n", "the IDCAMS LISTCAT command"),
        (" PRINT INFILE(IN)\n", "the IDCAMS PRINT command"),
        (" REPRO INFILE(IN) OUTFILE(OUT)\n DELETE A.B\n", "more than one IDCAMS command"),
        (" REPRO INFILE(IN) OUTFILE(OUT)\n REPRO INFILE(IN) OUTFILE(OUT)\n", "more than one IDCAMS command"),
        (" REPRO INDATASET(A.B) OUTFILE(OUT)\n", "the IDCAMS REPRO INDATASET parameter"),
        (" REPRO INFILE(IN) OUTDATASET(A.B)\n", "the IDCAMS REPRO OUTDATASET parameter"),
        (" REPRO INFILE(IN) OUTFILE(OUT) REPLACE\n", "the IDCAMS REPRO REPLACE parameter"),
        (" REPRO INFILE(IN) OUTFILE(OUT) COUNT(5)\n", "the IDCAMS REPRO COUNT parameter"),
        (" REPRO INFILE(IN) OUTFILE(OUT) SKIP(2)\n", "the IDCAMS REPRO SKIP parameter"),
        (" REPRO INFILE(IN) OUTFILE(OUT) FROMKEY(A)\n", "the IDCAMS REPRO FROMKEY parameter"),
        (" REPRO INFILE(IN)\n", "without OUTFILE"),
        (" REPRO OUTFILE(OUT)\n", "without INFILE"),
        (" REPRO INFILE(IN) INFILE(IN2) OUTFILE(OUT)\n", "INFILE parameter twice"),
        (" REPRO INFILE(IN/PW) OUTFILE(OUT)\n", "INFILE password"),
        (" REPRO INFILE(TOOLONGNAME) OUTFILE(OUT)\n", "INFILE value"),
        (" REPRO INFILE() OUTFILE(OUT)\n", "INFILE value"),
        (" REPRO INFILE(IN) OUTFILE(OUT) /* open\n", "unterminated comment"),
        (" REPRO INFILE(IN) = OUTFILE(OUT)\n", "an IDCAMS REPRO operand"),
    ],
)
def test_what_the_model_does_not_cover_is_refused_by_name(sysin, why):
    with pytest.raises(D.Refused, match=why):
        I.parse(sysin)
