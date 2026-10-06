"""det-port statements end to end: small COBOL programs, each run by GnuCOBOL (`cobc -x -std=ibm -fsign=EBCDIC`, the
harness's oracle) and translated (gitgalaxy/tools/cobol_to_java/det) and run as Java -- their DISPLAY output equal.

Each program DISPLAYs alphanumeric and unsigned DISPLAY items only, whose external form is their bytes on both sides.
The port runs on its own (runProgram) with the standalone runtime; nothing of a generated project is needed."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

IMAGE = "gitgalaxy-gnucobol:3"
PKG = "p"


def program(name: str, data: list[str], proc: list[str]) -> str:
    lines = ["       IDENTIFICATION DIVISION.", f"       PROGRAM-ID. {name}.", "       DATA DIVISION.",
             "       WORKING-STORAGE SECTION."]  # fmt: skip
    lines += [f"       {x}" for x in data]
    lines += ["       PROCEDURE DIVISION."] + [f"           {x}" for x in proc] + ["           GOBACK."]
    return "\n".join(lines) + "\n"


def fprogram(
    name: str, special: list[str], selects: list[str], files: list[str], data: list[str], proc: list[str]
) -> str:
    """A program with files: SPECIAL-NAMES, FILE-CONTROL, FILE SECTION, WORKING-STORAGE and a PROCEDURE DIVISION
    of paragraphs (each line from column 8: a paragraph name, or a statement indented four more)."""
    lines = ["IDENTIFICATION DIVISION.", f"PROGRAM-ID. {name}.", "ENVIRONMENT DIVISION."]
    if special:
        lines += ["CONFIGURATION SECTION.", "SPECIAL-NAMES.", *[f"    {x}" for x in special]]
    lines += ["INPUT-OUTPUT SECTION.", "FILE-CONTROL.", *[f"    {x}" for x in selects], "DATA DIVISION.",
              "FILE SECTION.", *files, "WORKING-STORAGE SECTION.", *data, "PROCEDURE DIVISION.", *proc]  # fmt: skip
    return "\n".join(f"       {x}" for x in lines) + "\n"


# SORT / MERGE (IBM Enterprise COBOL 6.4 Language Reference, SORT / MERGE / RELEASE / RETURN statements): an SD
# record with a zoned, a packed and an alphanumeric key; eight records, three with equal major and minor keys
SORT_SD = ["SD  SORT-FILE.", "01  SORT-REC.", "    05 SR-NAME  PIC X(6).", "    05 SR-DEPT  PIC 9(2).",
           "    05 SR-AMT   PIC S9(5) COMP-3.", "    05 SR-SEQ   PIC 9(2)."]  # fmt: skip
SORT_DATA = [
    "01  WS-DATA.",
    *[f"    05 FILLER PIC X(14) VALUE '{v}'." for v in ("DELTA 10-00050", "alpha 20+00300", "Bravo 10+00050",
      "ECHO  10+00700", "9LIVES20+00300", "ZULU  05-01000", "ALPHA 10-00050", "KILO  20+00300")],
    "01  WS-TABLE REDEFINES WS-DATA.",
    "    05 ENT OCCURS 8 TIMES.",
    "       10 E-NAME PIC X(6).",
    "       10 E-DEPT PIC 9(2).",
    "       10 E-AMT  PIC S9(5) SIGN LEADING SEPARATE.",
    "01  I       PIC 9(2) VALUE 0.",
    "01  EOF     PIC X VALUE 'N'.",
    "01  AMT-ED  PIC -ZZZZ9.",
    "01  WS-OUT  PIC X(8).",
    "01  RC-OUT  PIC 9(4).",
]  # fmt: skip
SORT_LOAD = [
    "LOAD-RECS.",
    "    PERFORM VARYING I FROM 1 BY 1 UNTIL I > 8",
    "        MOVE E-NAME(I) TO SR-NAME",
    "        MOVE E-DEPT(I) TO SR-DEPT",
    "        MOVE E-AMT(I) TO SR-AMT",
    "        MOVE I TO SR-SEQ",
    "        RELEASE SORT-REC",
    "    END-PERFORM.",
    "SHOW-RECS.",
    "    PERFORM UNTIL EOF = 'Y'",
    "        RETURN SORT-FILE",
    "            AT END MOVE 'Y' TO EOF",
    "            NOT AT END",
    "                MOVE SR-AMT TO AMT-ED",
    "                DISPLAY SR-DEPT ' ' AMT-ED ' ' SR-NAME ' ' SR-SEQ",
    "        END-RETURN",
    "    END-PERFORM.",
    "SHOW-INTO.",
    "    PERFORM UNTIL EOF = 'Y'",
    "        RETURN SORT-FILE INTO WS-OUT",
    "            AT END MOVE 'Y' TO EOF",
    "        END-RETURN",
    "        IF EOF = 'N'",
    "            DISPLAY '[' WS-OUT ']'",
    "        END-IF",
    "    END-PERFORM.",
    "SHOW-INTO-X.",
    "    EXIT.",
]  # fmt: skip

# SORT under an alphabet: an alphanumeric, a group (of characters only), a zoned, an edited key; eight records
SORTCS_SD = ["SD  SORT-FILE.", "01  SR.", "    05 SR-A PIC X(2).", "    05 SR-G.", "       10 SR-G1 PIC X.",
             "       10 SR-G2 PIC X(2).", "    05 SR-N PIC S9(2).", "    05 SR-E PIC Z9.", "    05 SR-T PIC X(3)."]  # fmt: skip
SORTCS_DATA = ["01  I   PIC 9(2).", "01  EOF PIC X.", "01  NE  PIC -99.",
               "01  RECS.",
               *[f"    05 FILLER PIC X(12) VALUE '{v}'." for v in (
                   "abaQ5-3 7T01", "BBZR11212T02", "b ZQ4 2 3T03", "-xxQ5-370T04", "X9 A0 0 9T05",
                   "c YB1 9 0T06", "Y0cB1 910T07", "zzbB2-9 1T08")],
               "01  RECT REDEFINES RECS.", "    05 REC PIC X(12) OCCURS 8."]  # fmt: skip
SORTCS_LOAD = [
    "LOAD-CS.",
    "    PERFORM VARYING I FROM 1 BY 1 UNTIL I > 8",
    "        MOVE REC(I)(1:5) TO SR(1:5)",
    "        MOVE FUNCTION NUMVAL(REC(I)(6:2)) TO SR-N",
    "        MOVE REC(I)(8:5) TO SR(8:5)",
    "        RELEASE SR",
    "    END-PERFORM.",
    "SHOW-CS.",
    "    MOVE 'N' TO EOF",
    "    PERFORM UNTIL EOF = 'Y'",
    "        RETURN SORT-FILE AT END MOVE 'Y' TO EOF",
    "            NOT AT END",
    "                MOVE SR-N TO NE",
    "                DISPLAY SR-T ' ' SR-A ' ' SR-G ' ' NE ' ' SR-E",
    "        END-RETURN",
    "    END-PERFORM.",
]  # fmt: skip

PROGRAMS = {
    # SORT with INPUT / OUTPUT PROCEDUREs: an ascending zoned major key and a descending packed minor key WITH
    # DUPLICATES IN ORDER (three records tie: they come back in RELEASE order), RETURN with and without INTO, a
    # THRU range, a descending and an ascending alphanumeric key (unique: no DUPLICATES needed), COLLATING
    # SEQUENCE STANDARD-1, SORT-RETURN
    "SORTIP": fprogram(
        "SORTIP",
        ["ALPHABET ASCII-SEQ IS STANDARD-1."],
        ["SELECT SORT-FILE ASSIGN TO SORTWK1."],
        SORT_SD,
        SORT_DATA,
        [
            "MAIN-PARA.",
            "    SORT SORT-FILE ON ASCENDING KEY SR-DEPT",
            "         DESCENDING KEY SR-AMT",
            "         WITH DUPLICATES IN ORDER",
            "         INPUT PROCEDURE IS LOAD-RECS",
            "         OUTPUT PROCEDURE IS SHOW-RECS",
            "    MOVE SORT-RETURN TO RC-OUT",
            "    DISPLAY 'SORT-RETURN ' RC-OUT",
            "    MOVE 'N' TO EOF",
            "    SORT SORT-FILE DESCENDING SR-NAME",
            "         INPUT PROCEDURE LOAD-RECS",
            "         OUTPUT PROCEDURE SHOW-INTO THRU SHOW-INTO-X",
            "    MOVE 'N' TO EOF",
            "    SORT SORT-FILE ON ASCENDING KEY SR-NAME",
            "         COLLATING SEQUENCE IS ASCII-SEQ",
            "         INPUT PROCEDURE LOAD-RECS",
            "         OUTPUT PROCEDURE SHOW-INTO THRU SHOW-INTO-X",
            "    GOBACK.",
            *SORT_LOAD,
        ],
    ),
    # SORT under an alphabet (IBM Enterprise COBOL 6.4 Language Reference, ALPHABET clause, SORT COLLATING
    # SEQUENCE): EBCDIC, and a literal alphabet (a multi-character literal, SPACE, ALSO, a descending THRU, the
    # characters it does not name after it) on an alphanumeric key, a descending group key, a numeric key (by value,
    # untouched by the alphabet) with an edited minor key, and an edited key. The records are such that IBM's
    # sequences and GnuCOBOL's agree (the port refuses a pair they order differently, register D1)
    "SORTCS": fprogram(
        "SORTCS",
        ["ALPHABET EB IS EBCDIC", "ALPHABET LT IS 'XYZ' SPACE 'b' ALSO 'B' ALSO 'c'", "    '9' THRU '0'."],
        ["SELECT SORT-FILE ASSIGN TO SORTWK1."],
        SORTCS_SD,
        SORTCS_DATA,
        [
            "MAIN-PARA.",
            "    DISPLAY 'EB A'",
            "    SORT SORT-FILE ON ASCENDING KEY SR-A WITH DUPLICATES",
            "         COLLATING SEQUENCE IS EB",
            "         INPUT PROCEDURE LOAD-CS OUTPUT PROCEDURE SHOW-CS",
            "    DISPLAY 'LT A'",
            "    SORT SORT-FILE ON ASCENDING KEY SR-A WITH DUPLICATES",
            "         COLLATING SEQUENCE LT",
            "         INPUT PROCEDURE LOAD-CS OUTPUT PROCEDURE SHOW-CS",
            "    DISPLAY 'LT G DESC'",
            "    SORT SORT-FILE ON DESCENDING KEY SR-G WITH DUPLICATES",
            "         COLLATING SEQUENCE LT",
            "         INPUT PROCEDURE LOAD-CS OUTPUT PROCEDURE SHOW-CS",
            "    DISPLAY 'LT N E'",
            "    SORT SORT-FILE ON ASCENDING KEY SR-N SR-E",
            "         COLLATING SEQUENCE LT",
            "         INPUT PROCEDURE LOAD-CS OUTPUT PROCEDURE SHOW-CS",
            "    DISPLAY 'LT E'",
            "    SORT SORT-FILE ON ASCENDING KEY SR-E",
            "         COLLATING SEQUENCE LT",
            "         INPUT PROCEDURE LOAD-CS OUTPUT PROCEDURE SHOW-CS",
            "    DISPLAY 'EB G DESC'",
            "    SORT SORT-FILE ON DESCENDING KEY SR-G",
            "         COLLATING SEQUENCE EB",
            "         INPUT PROCEDURE LOAD-CS OUTPUT PROCEDURE SHOW-CS",
            "    GOBACK.",
            *SORTCS_LOAD,
        ],
    ),
    # PROGRAM COLLATING SEQUENCE: a SORT without the phrase orders by it ('z' THRU 'a': the lower-case letters
    # first, descending, then every other character)
    "SORTPC": fprogram(
        "SORTPC",
        ["ALPHABET RV IS 'z' THRU 'a'."],
        ["SELECT SORT-FILE ASSIGN TO SORTWK1."],
        SORTCS_SD,
        SORTCS_DATA,
        [
            "MAIN-PARA.",
            "    SORT SORT-FILE ON ASCENDING KEY SR-A WITH DUPLICATES",
            "         INPUT PROCEDURE LOAD-CS OUTPUT PROCEDURE SHOW-CS",
            "    SORT SORT-FILE ON DESCENDING KEY SR-G SR-T",
            "         INPUT PROCEDURE LOAD-CS OUTPUT PROCEDURE SHOW-CS",
            "    GOBACK.",
            *SORTCS_LOAD,
        ],
    ).replace(
        "CONFIGURATION SECTION.\n",
        "CONFIGURATION SECTION.\n       OBJECT-COMPUTER. GG\n           PROGRAM COLLATING SEQUENCE IS RV.\n",
    ),
    # FUNCTION TRIM: spaces only, an all-space argument zero-length (COACTUPC's alphabetic-field check)
    "TRIMS": program(
        "TRIMS",
        [
            "01 S PIC X(10) VALUE SPACES.",
            "01 A PIC X(10) VALUE '  AB  '.",
            "01 L PIC X(10) VALUE LOW-VALUES.",
            "01 N PIC 9(4) VALUE 0.",
        ],
        [
            "MOVE FUNCTION LENGTH(FUNCTION TRIM(S)) TO N",
            "DISPLAY N",
            "MOVE FUNCTION LENGTH(FUNCTION TRIM(A)) TO N",
            "DISPLAY N",
            "MOVE FUNCTION LENGTH(FUNCTION TRIM(L)) TO N",
            "DISPLAY N",
            "DISPLAY '[' FUNCTION TRIM(S) ']'",
            "DISPLAY '[' FUNCTION TRIM(A LEADING) ']'",
            "DISPLAY '[' FUNCTION TRIM(A TRAILING) ']'",
            "IF FUNCTION LENGTH(FUNCTION TRIM(S)) = 0",
            "    DISPLAY 'EMPTY'",
            "END-IF",
        ],
    ),
    # GO TO the end of an outer PERFORM's range from inside an inner one: the outer PERFORM returns
    "GOTOOUT": "\n".join(
        [
            "       IDENTIFICATION DIVISION.",
            "       PROGRAM-ID. GOTOOUT.",
            "       DATA DIVISION.",
            "       WORKING-STORAGE SECTION.",
            "       01 N PIC 9(3) VALUE 0.",
            "       PROCEDURE DIVISION.",
            "       MAIN-PARA.",
            "           PERFORM A THRU A-EXIT",
            "           DISPLAY 'BACK IN MAIN N=' N",
            "           GOBACK.",
            "       A.",
            "           DISPLAY 'IN A'",
            "           PERFORM B THRU B-EXIT",
            "           DISPLAY 'AFTER B'.",
            "       A-EXIT.",
            "           DISPLAY 'IN A-EXIT'",
            "           EXIT.",
            "       B.",
            "           ADD 1 TO N",
            "           DISPLAY 'IN B N=' N",
            "           IF N > 3",
            "              DISPLAY 'LOOPED'",
            "              GOBACK",
            "           END-IF",
            "           GO TO A-EXIT.",
            "       B-EXIT.",
            "           EXIT.",
            "",
        ]
    ),  # fmt: skip
    "UNSTR1": program(
        "UNSTR1",
        [
            "01 SRC PIC X(30) VALUE 'ALPHA,BETA,,GAMMA DELTA'.",
            "01 A PIC X(8) VALUE SPACES.",
            "01 B PIC X(8) VALUE SPACES.",
            "01 C PIC X(8) VALUE SPACES.",
            "01 D PIC X(8) VALUE SPACES.",
            "01 DA PIC X VALUE SPACE.",
            "01 DB PIC X VALUE SPACE.",
            "01 CA PIC 9(2) VALUE 0.",
            "01 CB PIC 9(2) VALUE 0.",
            "01 PTR PIC 9(2) VALUE 1.",
            "01 TAL PIC 9(2) VALUE 0.",
        ],
        [
            "UNSTRING SRC DELIMITED BY ',' OR SPACE",
            "    INTO A DELIMITER IN DA COUNT IN CA",
            "         B DELIMITER IN DB COUNT IN CB C D",
            "    WITH POINTER PTR TALLYING IN TAL",
            "END-UNSTRING",
            "DISPLAY '[' A '][' B '][' C '][' D ']'",
            "DISPLAY '[' DA '][' DB ']' CA ' ' CB ' ' PTR ' ' TAL",
        ],
    ),
    "UNSTR2": program(
        "UNSTR2",
        [
            "01 SRC PIC X(20) VALUE 'A--B---C'.",
            "01 A PIC X(4) VALUE SPACES.",
            "01 B PIC X(4) VALUE SPACES.",
            "01 FLAG PIC X(10) VALUE 'NONE'.",
        ],
        [
            "UNSTRING SRC DELIMITED BY ALL '-' INTO A B",
            "    ON OVERFLOW MOVE 'OVERFLOW' TO FLAG",
            "    NOT ON OVERFLOW MOVE 'NO-OVF' TO FLAG",
            "END-UNSTRING",
            "DISPLAY '[' A '][' B '] ' FLAG",
        ],
    ),
    "UNSTR3": program(
        "UNSTR3",
        [
            "01 SRC PIC X(12) VALUE 'ABCDEFGHIJKL'.",
            "01 A PIC X(5) VALUE SPACES.",
            "01 B PIC X(5) VALUE SPACES.",
        ],
        [
            "UNSTRING SRC INTO A B",
            "DISPLAY '[' A '][' B ']'",
        ],
    ),
    "STRNG1": program(
        "STRNG1",
        [
            "01 OUT PIC X(10) VALUE ALL '*'.",
            "01 PTR PIC 9(2) VALUE 3.",
            "01 FLAG PIC X(10) VALUE 'NONE'.",
            "01 W PIC X(6) VALUE 'AB CD'.",
        ],
        [
            "STRING W DELIMITED BY SPACE",
            "    'XYZ' DELIMITED BY SIZE",
            "    'LONGTAIL' DELIMITED BY SIZE",
            "    INTO OUT WITH POINTER PTR",
            "    ON OVERFLOW MOVE 'OVERFLOW' TO FLAG",
            "END-STRING",
            "DISPLAY '[' OUT '] ' PTR ' ' FLAG",
        ],
    ),
    # B3 typed state: lifted items (String / long / BigDecimal) and items a use keeps as bytes (refmod, group move)
    "TYPED": program(
        "TYPED",
        [
            "01 FLAG PIC X(3) VALUE 'N'.",
            "   88 FLAG-YES VALUE 'Y'.",
            "   88 FLAG-NO VALUE 'N'.",
            "01 NAME PIC X(8) VALUE SPACES.",
            "01 SRC PIC X(12) VALUE 'ABCDEFGHIJKL'.",
            "01 CNT PIC S9(4) COMP VALUE 0.",
            "01 WRAP PIC 9(4) COMP VALUE 0.",
            "01 AMT PIC S9(5)V99 VALUE 1.50.",
            "01 PAMT PIC S9(5)V99 COMP-3 VALUE -2.25.",
            "01 OUTN PIC 9(7)V99 VALUE 0.",
            "01 GRP.",
            "   05 G1 PIC X(2) VALUE 'AB'.",
            "   05 G2 PIC 9(3) VALUE 7.",
            "01 GCOPY PIC X(5) VALUE SPACES.",
        ],
        [
            "IF FLAG-NO DISPLAY 'NO' END-IF",
            "SET FLAG-YES TO TRUE",
            "IF FLAG = 'Y' DISPLAY 'YES [' FLAG ']' END-IF",
            "MOVE SRC TO NAME",
            "DISPLAY '[' NAME ']'",
            "MOVE 'XY' TO NAME",
            "IF NAME < 'XZ' DISPLAY 'LESS' END-IF",
            "MOVE NAME(2:1) TO FLAG",
            "DISPLAY '[' FLAG ']'",
            "PERFORM 70000 TIMES ADD 1 TO CNT END-PERFORM",
            # (not below zero: GnuCOBOL's ADD / SUBTRACT wrap an unsigned binary item there, its COMPUTE / MOVE
            # and IBM store the absolute value -- a declared difference, det_port_design.md)
            "ADD 70000 TO WRAP",
            "SUBTRACT 3 FROM WRAP",
            "MOVE CNT TO OUTN",
            "DISPLAY OUTN",
            "MOVE WRAP TO OUTN",
            "DISPLAY OUTN",
            "ADD 123456.789 TO AMT",
            "MOVE AMT TO OUTN",
            "DISPLAY OUTN",
            "COMPUTE PAMT ROUNDED = PAMT * 3 / 7",
            "MOVE PAMT TO OUTN",
            "DISPLAY OUTN",
            "IF PAMT < 0 DISPLAY 'NEGATIVE' END-IF",
            "ADD 5 TO G2",
            "MOVE GRP TO GCOPY",
            "DISPLAY '[' GCOPY ']'",
        ],
    ),
    # negative zero: a signed item can hold -0 (a MOVE keeps the sending sign through truncation), which a typed
    # BigDecimal cannot -- such an item must stay byte storage
    "NEGZERO": program(
        "NEGZERO",
        [
            "01 SRC PIC S9V99 VALUE -0.05.",
            "01 A PIC S9(3) VALUE 0.",
            "01 B PIC S9(3) VALUE 0.",
            "01 C PIC S9(3) VALUE 0.",
            "01 OUTA PIC X(3) VALUE SPACES.",
            "01 OUTB PIC X(3) VALUE SPACES.",
            "01 OUTC PIC X(3) VALUE SPACES.",
            "01 GA.",
            "   05 DA PIC S9(3) VALUE 0.",
            "01 GB.",
            "   05 DB PIC S9(3) VALUE 0.",
            "01 GC.",
            "   05 DC PIC S9(3) VALUE 0.",
            "01 E PIC S9(3) VALUE 5.",
            "01 GE.",
            "   05 XE PIC S9(3) VALUE 0.",
            "01 OUTE PIC X(3) VALUE SPACES.",
            "01 WIDE PIC S9(5)V99 VALUE 0.",
            "01 GW.",
            "   05 DW PIC S9(5)V99 VALUE 0.",
            "01 OUTW PIC X(7) VALUE SPACES.",
        ],
        [
            "MOVE SRC TO A",
            "COMPUTE B = SRC",
            "SUBTRACT 0.05 FROM C",
            "MOVE A TO DA",
            "MOVE B TO DB",
            "MOVE C TO DC",
            "MOVE GA TO OUTA",
            "MOVE GB TO OUTB",
            "MOVE GC TO OUTC",
            "DISPLAY '[' OUTA '][' OUTB '][' OUTC ']'",
            "IF A = 0 DISPLAY 'A ZERO' END-IF",
            "MOVE -1000 TO E",
            "MOVE E TO XE",
            "MOVE GE TO OUTE",
            "MOVE C TO WIDE",
            "SUBTRACT 1.25 FROM WIDE",
            "MOVE WIDE TO DW",
            "MOVE GW TO OUTW",
            "DISPLAY '[' OUTE '][' OUTW ']'",
        ],
    ),
    # typed groups: items inside groups used whole -- read whole (SRCG), written whole (DSTG, by MOVE and
    # INITIALIZE), and through a reference modification of the group
    "TGROUPS": program(
        "TGROUPS",
        [
            "01 SRCG.",
            "   05 S-NAME PIC X(6) VALUE 'ALPHA'.",
            "   05 S-CNT PIC S9(4) COMP VALUE 7.",
            "   05 S-AMT PIC S9(5)V99 VALUE 12.5.",
            "01 DSTG.",
            "   05 D-NAME PIC X(6) VALUE SPACES.",
            "   05 D-CNT PIC S9(4) COMP VALUE 0.",
            "   05 D-AMT PIC S9(5)V99 VALUE 0.",
            "01 RAW PIC X(15) VALUE SPACES.",
            "01 NSTG.",
            "   05 N-NAME PIC X(4) VALUE 'OLD '.",
            "   05 N-REST PIC X(4) VALUE SPACES.",
            "01 OUTN PIC 9(7)V99 VALUE 0.",
            "01 OUTC PIC 9(4) VALUE 0.",
        ],
        [
            "MOVE 'BETA' TO S-NAME",
            "ADD 5 TO S-CNT",
            "ADD 1.25 TO S-AMT",
            "MOVE SRCG TO RAW",
            "MOVE SRCG TO DSTG",
            "IF D-NAME = 'BETA' DISPLAY 'NAME ' D-NAME END-IF",
            "MOVE D-CNT TO OUTC",
            "MOVE D-AMT TO OUTN",
            "DISPLAY OUTC ' ' OUTN",
            "MOVE 'GAMMA!' TO D-NAME",
            "MOVE DSTG(1:3) TO RAW",
            "DISPLAY '[' RAW ']'",
            "INITIALIZE DSTG",
            "MOVE D-CNT TO OUTC",
            "DISPLAY '[' D-NAME '] ' OUTC",
            "MOVE SPACES TO DSTG",
            "MOVE 'Z' TO D-NAME",
            "DISPLAY '[' D-NAME ']'",
            "STRING 'NESTED' DELIMITED BY SIZE INTO NSTG",
            "    ON OVERFLOW DISPLAY 'OVF [' N-NAME ']'",
            "    NOT ON OVERFLOW DISPLAY 'OK [' N-NAME ']'",
            "END-STRING",
            "DISPLAY '[' N-NAME ']'",
        ],
    ),
    # #4271 COMP-1 / COMP-2 (IBM hexadecimal floating point in the port, IEEE on GnuCOBOL): VALUE, MOVE both ways
    # (into numeric, numeric-edited and float items), ADD / SUBTRACT / MULTIPLY / DIVIDE with and without GIVING,
    # COMPUTE, comparisons (IF, 88 values and THRU, EVALUATE, sign), SET TO TRUE, PERFORM VARYING, INITIALIZE of
    # a group holding one. Every value is exact in IEEE, HFP and at its receiver's scale, so the two must agree;
    # where they cannot (rounding vs GnuCOBOL's truncation, its float expression bugs) test_det_hfp.py proves
    # the port by hand-computed vectors instead (register C6)
    "FLOAT": program(
        "FLOAT",
        [
            "01 S1 COMP-1 VALUE 12.5.",
            "01 S2 COMP-1 VALUE -0.375.",
            "01 L1 COMP-2 VALUE 1024.",
            "01 L2 COMP-2.",
            "01 GRP.",
            "   05 G-NAME PIC X(4) VALUE 'ABCD'.",
            "   05 G-F    COMP-2 VALUE 3.5.",
            "   05 G-N    PIC 9(3) VALUE 7.",
            "01 RATE COMP-1 VALUE 0.5.",
            "   88 HALF VALUE 0.5.",
            "   88 SMALL VALUE 0 THRU 0.25.",
            "01 N1 PIC S9(5)V9(4) SIGN LEADING SEPARATE.",
            "01 N2 PIC 9(5)V9(4).",
            "01 N3 PIC S9(3) COMP-3 VALUE -24.",
            "01 N4 PIC S9(4) COMP VALUE 8.",
            "01 ED PIC -ZZZ9.9999.",
            "01 I  PIC 9(2).",
        ],
        [
            "MOVE S1 TO N1 DISPLAY N1",
            "MOVE S2 TO N1 DISPLAY N1",
            "MOVE L1 TO N2 DISPLAY N2",
            "ADD S1 TO S2 MOVE S2 TO N1 DISPLAY N1",
            "SUBTRACT 0.125 FROM S1 MOVE S1 TO N1 DISPLAY N1",
            "MULTIPLY 4 BY S1 MOVE S1 TO N1 DISPLAY N1",
            "DIVIDE 8 INTO S1 MOVE S1 TO N1 DISPLAY N1",
            "DIVIDE L1 BY 256 GIVING L2 MOVE L2 TO N1 DISPLAY N1",
            "ADD S1 L1 GIVING L2 MOVE L2 TO N1 DISPLAY N1",
            "SUBTRACT N3 FROM L1 GIVING L2 MOVE L2 TO N1 DISPLAY N1",
            "MULTIPLY N4 BY S2 GIVING L2 MOVE L2 TO N1 DISPLAY N1",
            "COMPUTE L2 = L1 / N4 + S1",
            "MOVE L2 TO N2 DISPLAY N2",
            "COMPUTE N1 = L1 / 64 - S2",
            "DISPLAY N1",
            "COMPUTE S2 = S1 - S2",
            "MOVE S2 TO ED DISPLAY ED",
            "MOVE N3 TO L2 MOVE L2 TO N1 DISPLAY N1",
            "MOVE -1.5 TO S2 MOVE S2 TO ED DISPLAY ED",
            "MOVE N4 TO S2 MOVE S2 TO N2 DISPLAY N2",
            "MOVE L1 TO S2 MOVE S2 TO N2 DISPLAY N2",
            "MOVE S1 TO L2 MOVE L2 TO N1 DISPLAY N1",
            "ADD 1 TO G-N",
            "MOVE G-F TO N1 DISPLAY N1",
            "IF S1 > S2 DISPLAY 'GT' ELSE DISPLAY 'LE' END-IF",
            "IF L1 = 1024 DISPLAY 'EQ' ELSE DISPLAY 'NE' END-IF",
            "IF S2 < N3 DISPLAY 'LT' ELSE DISPLAY 'GE' END-IF",
            "IF N3 < S2 DISPLAY 'LT' ELSE DISPLAY 'GE' END-IF",
            "IF L1 = ZERO DISPLAY 'ZERO' ELSE DISPLAY 'NONZERO' END-IF",
            "IF L1 POSITIVE DISPLAY 'POS' END-IF",
            "IF HALF DISPLAY 'HALF' END-IF",
            "SET SMALL TO TRUE",
            "IF SMALL DISPLAY 'SMALL' END-IF",
            "IF NOT HALF DISPLAY 'NOT HALF' END-IF",
            "EVALUATE L1",
            "   WHEN 512 DISPLAY 'W512'",
            "   WHEN 1024 DISPLAY 'W1024'",
            "   WHEN OTHER DISPLAY 'WOTHER'",
            "END-EVALUATE",
            "PERFORM VARYING I FROM 1 BY 1 UNTIL I > 3",
            "   ADD 0.5 TO RATE",
            "END-PERFORM",
            "MOVE RATE TO N1 DISPLAY N1",
            "INITIALIZE GRP",
            "MOVE G-F TO N1 DISPLAY N1 ' ' G-N ' [' G-NAME ']'",
            "MOVE ZERO TO L1 MOVE L1 TO N2 DISPLAY N2",
        ],
    ),
    # #4501: a COMP-5 VALUE beyond its PICTURE keeps its value (IBM: the native binary capacity), little-endian as
    # the runtime reads it -- 32767 read back as -12534 before
    "COMP5": program(
        "COMP5",
        [
            "01 BIG PIC S9(4) COMP-5 VALUE 32767.",
            "01 NEG PIC S9(4) COMP-5 VALUE -32768.",
            "01 UB  PIC 9(4) COMP-5 VALUE 65535.",
            "01 WD  PIC S9(9) COMP-5 VALUE 2147483647.",
            "01 N5  PIC S9(10) SIGN LEADING SEPARATE.",
        ],
        [
            "MOVE BIG TO N5 DISPLAY N5",
            "MOVE NEG TO N5 DISPLAY N5",
            "MOVE UB TO N5 DISPLAY N5",
            "MOVE WD TO N5 DISPLAY N5",
            "SUBTRACT 1 FROM BIG MOVE BIG TO N5 DISPLAY N5",
        ],
    ),
}


def _put(rec: str, k1: str, k2: int, b: int, tag: str) -> list[str]:
    """One record written from W-REC: SORTUG's layout (K1 X(3), K2 S9(3), B S9(4) COMP, TAG X(4))."""
    return [f"    MOVE '{k1}' TO W-K1", f"    MOVE {k2} TO W-K2", f"    MOVE {b} TO W-B", f"    MOVE '{tag}' TO W-TAG",
            f"    WRITE {rec} FROM W-REC"]  # fmt: skip


def _show(f: str) -> list[str]:
    return [f"SHOW-{f}.", f"    OPEN INPUT {f}-FILE", "    MOVE 'N' TO EOF", "    PERFORM UNTIL EOF = 'Y'",
            f"        READ {f}-FILE INTO W-REC", "            AT END MOVE 'Y' TO EOF",
            "            NOT AT END PERFORM SHOW-W", "        END-READ", "    END-PERFORM", f"    CLOSE {f}-FILE."]  # fmt: skip


# files a test program's DDs name: each ASSIGN TO name is a dataset of that name (GnuCOBOL: a file in the working
# directory; the port: DatasetResolver's directory)
FILE_PROGRAMS = {
    # SORT USING / GIVING: a multi-key sort (ascending alphanumeric, descending signed zoned, ascending signed
    # binary), a second sort on the binary key alone WITH DUPLICATES, the GIVING file's FILE STATUS; MERGE of two
    # ordered files USING / GIVING and USING / OUTPUT PROCEDURE, equal keys across the files in USING order
    "SORTUG": fprogram(
        "SORTUG",
        [],
        [
            "SELECT IN-FILE ASSIGN TO INFILE.",
            "SELECT OUT-FILE ASSIGN TO OUTFILE FILE STATUS IS OUT-ST.",
            "SELECT M1-FILE ASSIGN TO M1FILE.",
            "SELECT M2-FILE ASSIGN TO M2FILE.",
            "SELECT MG-FILE ASSIGN TO MGFILE.",
            "SELECT SORT-FILE ASSIGN TO SORTWK1.",
        ],
        [
            *[x for f in ("IN", "OUT", "M1", "M2", "MG") for x in (f"FD  {f}-FILE.", f"01  {f}-REC PIC X(12).")],
            "SD  SORT-FILE.",
            "01  SR.",
            "    05 SR-K1  PIC X(3).",
            "    05 SR-K2  PIC S9(3).",
            "    05 SR-B   PIC S9(4) COMP.",
            "    05 SR-TAG PIC X(4).",
        ],
        [
            "01  W-REC.",
            "    05 W-K1  PIC X(3).",
            "    05 W-K2  PIC S9(3).",
            "    05 W-B   PIC S9(4) COMP.",
            "    05 W-TAG PIC X(4).",
            "01  EOF     PIC X VALUE 'N'.",
            "01  K2-ED   PIC -ZZ9.",
            "01  B-ED    PIC -ZZZ9.",
            "01  RC-OUT  PIC 9(4).",
            "01  OUT-ST  PIC X(2) VALUE SPACES.",
        ],
        [
            "MAIN-PARA.",
            "    OPEN OUTPUT IN-FILE",
            *_put("IN-REC", "BBB", 5, -7, "T01"),
            *_put("IN-REC", "AAA", 5, 300, "T02"),
            *_put("IN-REC", "BBB", -12, 40, "T03"),
            *_put("IN-REC", "B1B", 0, -7, "T04"),
            *_put("IN-REC", "AAA", 17, -2, "T05"),
            *_put("IN-REC", "BBB", 5, -9, "T06"),
            *_put("IN-REC", "aaa", 5, 300, "T07"),
            *_put("IN-REC", "AAA", 17, 300, "T08"),
            "    CLOSE IN-FILE",
            "    SORT SORT-FILE ON ASCENDING KEY SR-K1 DESCENDING KEY SR-K2",
            "         ASCENDING KEY SR-B",
            "         USING IN-FILE GIVING OUT-FILE",
            "    MOVE SORT-RETURN TO RC-OUT",
            "    DISPLAY 'SORT-RETURN ' RC-OUT ' OUT-ST ' OUT-ST",
            "    PERFORM SHOW-OUT",
            "    SORT SORT-FILE ON DESCENDING KEY SR-B WITH DUPLICATES",
            "         USING IN-FILE GIVING OUT-FILE",
            "    DISPLAY '--'",
            "    PERFORM SHOW-OUT",
            "    OPEN OUTPUT M1-FILE M2-FILE",
            *_put("M1-REC", "AAA", 1, 1, "M11"),
            *_put("M1-REC", "CCC", 2, 2, "M12"),
            *_put("M1-REC", "CCC", 3, 3, "M13"),
            *_put("M1-REC", "EEE", 4, 4, "M14"),
            *_put("M2-REC", "BBB", 5, 5, "M21"),
            *_put("M2-REC", "CCC", 6, 6, "M22"),
            *_put("M2-REC", "FFF", 7, 7, "M23"),
            "    CLOSE M1-FILE M2-FILE",
            "    MERGE SORT-FILE ON ASCENDING KEY SR-K1",
            "          USING M1-FILE M2-FILE GIVING MG-FILE",
            "    DISPLAY '--'",
            "    PERFORM SHOW-MG",
            "    MERGE SORT-FILE ON ASCENDING KEY SR-K1",
            "          USING M2-FILE M1-FILE OUTPUT PROCEDURE SHOW-SORT",
            "    GOBACK.",
            "SHOW-W.",
            "    MOVE W-K2 TO K2-ED",
            "    MOVE W-B TO B-ED",
            "    DISPLAY W-K1 ' ' K2-ED ' ' B-ED ' ' W-TAG.",
            *_show("OUT"),
            *_show("MG"),
            "SHOW-SORT.",
            "    DISPLAY '--'",
            "    MOVE 'N' TO EOF",
            "    PERFORM UNTIL EOF = 'Y'",
            "        RETURN SORT-FILE INTO W-REC",
            "            AT END MOVE 'Y' TO EOF",
            "            NOT AT END PERFORM SHOW-W",
            "        END-RETURN",
            "    END-PERFORM.",
        ],
    ),
}
FILE_DDS = {"SORTUG": ["INFILE", "OUTFILE", "M1FILE", "M2FILE", "MGFILE"]}


def _java() -> Path | None:
    home = os.environ.get("JDK_17") or os.environ.get("JAVA_HOME")
    return Path(home) / "bin" if home and (Path(home) / "bin/javac").is_file() else None


def _cobol(src: str, work: Path) -> str:
    (work / "prog.cbl").write_text(src)
    run = subprocess.run(["docker", "run", "--rm", "-v", f"{work}:/w", "-w", "/w", IMAGE, "sh", "-c",  # noqa: S607
                          "cobc -x -std=ibm -fsign=EBCDIC prog.cbl -o prog 2>&1 && ./prog"], capture_output=True,
                         text=True, check=False)  # fmt: skip
    assert run.returncode == 0, run.stdout + run.stderr
    return run.stdout


def _java_run(
    name: str, src: str, work: Path, typed: bool = False, groups: bool = False, unit: str | None = None
) -> str:
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (work / f"{name}.cbl").write_text(src)
    project = work / "project"  # no generated project: the standalone runtime
    project.mkdir()
    cls = (unit or name).title()
    r = P.translate(work / f"{name}.cbl", [], f"public class {cls}Service {{\n}}\n", PKG, None, project,
                    typed=typed, groups=groups, unit=unit)  # fmt: skip
    assert not r.stats["holes"], r.stats["holes"]
    srcdir = work / "java"
    java = r.java.replace("import org.springframework.stereotype.Service;\n", "").replace("@Service\n", "")
    # the runtime without its CICS boundary (it needs a generated CicsTask)
    runtime = {k: v for k, v in P.runtime_files(PKG, batch=False).items() if not k.startswith("cobolrt/cics/")}
    for rel, text in [(f"service/{r.service}.java", java), *runtime.items()]:
        (srcdir / PKG / rel).parent.mkdir(parents=True, exist_ok=True)
        (srcdir / PKG / rel).write_text(text)
    # the generated project's record charset, as the harness runs it: ISO-8859-1
    rec = srcdir / PKG / "entity/vsam/CobolRecords.java"
    rec.parent.mkdir(parents=True, exist_ok=True)
    rec.write_text(f"package {PKG}.entity.vsam;\npublic final class CobolRecords {{\n    public static java.nio.charset."
                   "Charset charset() {\n        return java.nio.charset.StandardCharsets.ISO_8859_1;\n    }\n}\n")  # fmt: skip
    (srcdir / "Main.java").write_text(f"public class Main {{ public static void main(String[] a) {{ "
                                      f"new {PKG}.service.{r.service}().runProgram(); }} }}\n")  # fmt: skip
    jdk = _java()
    files = [str(f) for f in srcdir.rglob("*.java")]
    subprocess.run([str(jdk / "javac"), "-nowarn", "-d", str(work / "classes"), *files], check=True)  # noqa: S603
    return subprocess.run([str(jdk / "java"), "-cp", str(work / "classes"), "Main"], capture_output=True, text=True,  # noqa: S603
                          check=True).stdout  # fmt: skip


def _batch_package(srcdir: Path) -> None:
    """The generated project's batch package (CobolFiles, DatasetResolver, Dd, MainframeClock, Sysout, CobolAbend)
    from the batch forge's own templates, without Spring: what a det port with files runs on."""
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_batch_forge import _RUNTIME

    for cls in ("CobolFiles", "DatasetResolver", "Dd", "MainframeClock", "Sysout", "CobolAbend"):
        text = _RUNTIME[cls].replace("{pkg}", f"{PKG}.batch").replace("{zone}", "UTC")
        text = re.sub(r"^import org\.springframework\..*\n|^@Component\n", "", text, flags=re.M)
        text = re.sub(r'@Value\("(?:[^"\\]|\\.)*"\)\s*', "", text)
        (srcdir / PKG / "batch" / f"{cls}.java").parent.mkdir(parents=True, exist_ok=True)
        (srcdir / PKG / "batch" / f"{cls}.java").write_text(text)


def _java_run_batch(name: str, src: str, work: Path, dds: list[str], typed: bool = False, groups: bool = False) -> str:
    """As _java_run, on the batch runtime (DetFiles): runBatch with one DD per dataset, each a file of its name in
    a datasets directory."""
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (work / f"{name}.cbl").write_text(src)
    srcdir = work / "java"
    project = work / "project"
    _batch_package(project / "src/main/java")  # has_batch: the project has its batch package
    r = P.translate(work / f"{name}.cbl", [], f"public class {name.title()}Service {{\n}}\n", PKG, None, project,
                    typed=typed, groups=groups)  # fmt: skip
    assert not r.stats["holes"], r.stats["holes"]
    java = r.java.replace("import org.springframework.stereotype.Service;\n", "").replace("@Service\n", "")
    runtime = {k: v for k, v in P.runtime_files(PKG, batch=True).items() if not k.startswith("cobolrt/cics/")}
    runtime = {k: v for k, v in runtime.items() if not k.startswith("cobolrt/sql/")}
    for rel, text in [(f"service/{r.service}.java", java), *runtime.items()]:
        (srcdir / PKG / rel).parent.mkdir(parents=True, exist_ok=True)
        (srcdir / PKG / rel).write_text(text)
    _batch_package(srcdir)
    rec = srcdir / PKG / "entity/vsam/CobolRecords.java"
    rec.parent.mkdir(parents=True, exist_ok=True)
    rec.write_text(f"package {PKG}.entity.vsam;\npublic final class CobolRecords {{\n    public static java.nio.charset."
                   "Charset charset() {\n        return java.nio.charset.StandardCharsets.ISO_8859_1;\n    }\n}\n")  # fmt: skip
    data = work / "datasets"
    data.mkdir()
    b = f"{PKG}.batch"
    dd_list = ", ".join(f'new {b}.Dd("{d}", "{d}", "NEW", "CATLG", null)' for d in dds)
    (srcdir / "Main.java").write_text(
        f"public class Main {{ public static void main(String[] a) {{ new {PKG}.service.{r.service}("
        f'new {b}.DatasetResolver("{data}"), new {b}.CobolFiles("", ""), new {b}.MainframeClock("", "UTC"))'
        f".runBatch(java.util.List.of({dd_list}), null); }} }}\n"
    )
    jdk = _java()
    files = [str(f) for f in srcdir.rglob("*.java")]
    subprocess.run([str(jdk / "javac"), "-nowarn", "-d", str(work / "classes"), *files], check=True)  # noqa: S603
    return subprocess.run([str(jdk / "java"), "-cp", str(work / "classes"), "Main"], capture_output=True, text=True,  # noqa: S603
                          check=True).stdout  # fmt: skip


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1" or not shutil.which("docker") or _java() is None,
                    reason="needs Docker and a JDK 17 (JAVA_HOME / JDK_17)")  # fmt: skip
@pytest.mark.parametrize("mode", ["bytes", "typed", "groups"])
@pytest.mark.parametrize("name", sorted(FILE_PROGRAMS))
def test_file_program_output_is_gnucobols(name, mode, tmp_path):
    """Programs with files (SORT USING / GIVING, MERGE): GnuCOBOL's files are in its working directory, the port's
    in a datasets directory; the DISPLAY output must be equal."""
    cob = tmp_path / "cobol"
    cob.mkdir()
    want = _cobol(FILE_PROGRAMS[name], cob)
    got = _java_run_batch(name, FILE_PROGRAMS[name], tmp_path, FILE_DDS[name], mode != "bytes", mode == "groups")
    assert got == want, f"java {got!r} != cobol {want!r}"


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1" or not shutil.which("docker") or _java() is None,
                    reason="needs Docker and a JDK 17 (JAVA_HOME / JDK_17)")  # fmt: skip
@pytest.mark.parametrize("mode", ["bytes", "typed", "groups"])
@pytest.mark.parametrize("name", sorted(PROGRAMS))
def test_program_output_is_gnucobols(name, mode, tmp_path):
    cob = tmp_path / "cobol"
    cob.mkdir()
    want = _cobol(PROGRAMS[name], cob)
    got = _java_run(name, PROGRAMS[name], tmp_path, mode != "bytes", mode == "groups")
    assert got == want, f"java {got!r} != cobol {want!r}"


def _byte_storage(java: str, name: str) -> bool:
    """`name` is held as bytes: declared as a Field bound to its storage (one line since #4202), never as a typed
    Java field."""
    bound = re.search(rf"^    private final Field {name} = Field\.\w+\(", java, re.M)
    typed = re.search(rf"^    private (?:String|long|BigDecimal) {name};", java, re.M)
    return bool(bound) and not typed


def test_typed_lifts_only_what_every_use_allows(tmp_path):
    """TYPED's lifts, without running anything: NAME is read by reference modification, G1 / G2 sit in a group that
    is moved whole and OUTN is DISPLAYed (a numeric item's external form), so they stay byte storage; the rest are
    typed fields."""
    pytest.importorskip("tree_sitter_language_pack")  # the translator's parser (not in every CI job)
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (tmp_path / "TYPED.cbl").write_text(PROGRAMS["TYPED"])
    (tmp_path / "project").mkdir()
    r = P.translate(tmp_path / "TYPED.cbl", [], "public class TypedService {\n}\n", PKG, None, tmp_path / "project",
                    style="structured", typed=True)  # fmt: skip
    for decl in ("private String flag;", "private String src;", "private long cnt;", "private long wrap;",
                 "private BigDecimal amt;", "private BigDecimal pamt;", "private String gcopy;"):  # fmt: skip
        assert decl in r.java, decl
    for name in ("name", "g2", "g1", "outn"):
        assert _byte_storage(r.java, name), name


def test_a_move_that_can_leave_negative_zero_keeps_the_item_bytes(tmp_path):
    """NEGZERO's lifts: A (MOVEd -0.05) and E (MOVEd -1000) can hold negative zero, so they stay byte storage;
    B and C (arithmetic: +0) and WIDE (MOVEd C, whose digits all fit) are typed."""
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (tmp_path / "NEGZERO.cbl").write_text(PROGRAMS["NEGZERO"])
    (tmp_path / "project").mkdir()
    r = P.translate(tmp_path / "NEGZERO.cbl", [], "public class NegzeroService {\n}\n", PKG, None,
                    tmp_path / "project", style="structured", typed=True)  # fmt: skip
    for name in ("a", "e"):
        assert _byte_storage(r.java, name), name
    for decl in ("private BigDecimal b;", "private BigDecimal c;", "private BigDecimal wide;"):
        assert decl in r.java, decl


def test_typed_groups_sync_a_groups_bytes_around_its_whole_uses(tmp_path):
    """TGROUPS with groups synced: the items in SRCG and DSTG are typed although both groups are used whole. A
    typed number stays only where its group is never written whole (S-AMT, not D-AMT: bytes MOVEd into DSTG may be
    no number). A simple statement packs once, before itself -- INITIALIZE's own element moves must not be undone by
    a second pack -- and a write is followed by the unpack."""
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (tmp_path / "TGROUPS.cbl").write_text(PROGRAMS["TGROUPS"])
    (tmp_path / "project").mkdir()
    r = P.translate(tmp_path / "TGROUPS.cbl", [], "public class TgroupsService {\n}\n", PKG, None,
                    tmp_path / "project", style="structured", typed=True, groups=True)  # fmt: skip
    for decl in ("private String sName;", "private long sCnt;", "private BigDecimal sAmt;", "private String dName;",
                 "private long dCnt;"):  # fmt: skip
        assert decl in r.java, decl
    assert _byte_storage(r.java, "dAmt")  # a number in a group written whole stays bytes
    init = r.java[r.java.index("// INITIALIZE DSTG") :].split("// MOVE D-CNT", 1)[0]
    lines = [ln.strip() for ln in init.splitlines()]
    assert lines.count("pack_dstg();") == 1 and lines.count("unpack_dstg();") == 1
    assert "pack_dstg()." not in init  # inside the statement: the plain field, no second pack
    unpack_src = r.java[r.java.index("private void unpack_srcg()") :].split("    }", 1)[0]
    assert "sAmt" not in unpack_src  # a read-only group's number is never read back from bytes


def _sort_variant(proc: list[str], special: list[str] | None = None) -> str:
    return fprogram("SORTX", special or [], ["SELECT SORT-FILE ASSIGN TO SORTWK1."], SORT_SD, SORT_DATA,
                    ["MAIN-PARA.", *proc, "    GOBACK.", *SORT_LOAD])  # fmt: skip


def _holes(tmp_path: Path, src: str) -> list[str]:
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (tmp_path / "SORTX.cbl").write_text(src)
    (tmp_path / "project").mkdir(exist_ok=True)
    return P.translate(tmp_path / "SORTX.cbl", [], "public class SortxService {\n}\n", PKG, None,
                       tmp_path / "project").stats["holes"]  # fmt: skip


@pytest.mark.parametrize(
    ("proc", "special", "why"),
    [
        # an ordinal names a code of the native character set: EBCDIC on z/OS, ISO-8859-1 here (register D1)
        (["    SORT SORT-FILE ASCENDING SR-NAME COLLATING SEQUENCE OD", "         INPUT PROCEDURE LOAD-RECS",
          "         OUTPUT PROCEDURE SHOW-RECS"], ["ALPHABET OD IS 'A' 1 THRU 65."], "COLLATING SEQUENCE OD: 1 in"),
        # an alphabet orders characters: a group key holding a packed item is not all characters
        (["    SORT SORT-FILE ASCENDING SORT-REC COLLATING SEQUENCE EB", "         INPUT PROCEDURE LOAD-RECS",
          "         OUTPUT PROCEDURE SHOW-RECS"], ["ALPHABET EB IS EBCDIC."], "holds numeric or national items"),
        # an alphabet of HIGH-VALUE: defined by the collating sequence it is in
        (["    SORT SORT-FILE ASCENDING SR-NAME COLLATING SEQUENCE HV", "         INPUT PROCEDURE LOAD-RECS",
          "         OUTPUT PROCEDURE SHOW-RECS"], ["ALPHABET HV IS 'A' HIGH-VALUE."], "HIGH-VALUE in"),
        # IBM: 16 in SORT-RETURN ends the sort at the next RELEASE / RETURN
        (["    MOVE 16 TO SORT-RETURN"], None, "SORT-RETURN set by the program"),
        # format 2: a table, not an SD file
        (["    SORT ENT ON ASCENDING KEY E-NAME"], None, "SORT of a table (format 2) not modelled"),
        # a key outside the SD's record
        (["    SORT SORT-FILE ASCENDING E-DEPT INPUT PROCEDURE LOAD-RECS", "         OUTPUT PROCEDURE SHOW-RECS"],
         None, "not in a record of SORT-FILE"),
    ],
)  # fmt: skip
def test_sort_refuses_by_name_what_ibm_leaves_open(proc, special, why, tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    holes = _holes(tmp_path, _sort_variant(proc, special))
    assert any(why in h for h in holes), holes


def test_sort_translates_every_phrase(tmp_path):
    """The grammar drops a SORT's later phrases (WITH DUPLICATES, OUTPUT PROCEDURE); the placeholder pass keeps
    them: SORTIP and SORTUG translate whole, and a SORT followed by another statement on its line ends there."""
    pytest.importorskip("tree_sitter_language_pack")
    assert not _holes(tmp_path, PROGRAMS["SORTIP"])
    src = _sort_variant(["    SORT SORT-FILE ON DESCENDING KEY SR-AMT WITH DUPLICATES",
                         "         INPUT PROCEDURE LOAD-RECS", "         OUTPUT PROCEDURE SHOW-RECS DISPLAY 'X'"])  # fmt: skip
    from gitgalaxy.tools.cobol_to_java.det import stmt as S
    from gitgalaxy.tools.cobol_to_java.det.source import logical_lines

    (tmp_path / "s.cbl").write_text(src)
    proc = S.parse(logical_lines(src.splitlines(), "s.cbl"))
    main = proc.paragraphs[0].body
    assert [s.kind for s in main[:2]] == ["SORT", "DISPLAY"]
    assert main[0].data["duplicates"] and main[0].data["output"] == ("SHOW-RECS", None)
    assert [(k.name, a) for k, a in main[0].data["keys"]] == [("SR-AMT", False)]


@pytest.mark.skipif(not shutil.which("javac") and _java() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_sort_without_duplicates_refuses_equal_keys(tmp_path):
    """IBM: without DUPLICATES the order of records with equal keys is undefined. Records whose keys tie and whose
    bytes differ stop the run by name; GnuCOBOL's order is not taken as IBM's."""
    pytest.importorskip("tree_sitter_language_pack")
    if _java() is None:
        pytest.skip("needs JAVA_HOME / JDK_17")
    src = _sort_variant(["    SORT SORT-FILE ON ASCENDING KEY SR-DEPT", "         INPUT PROCEDURE LOAD-RECS",
                         "         OUTPUT PROCEDURE SHOW-RECS"])  # fmt: skip
    with pytest.raises(subprocess.CalledProcessError) as e:
        _java_run("SORTX", src, tmp_path)
    assert "without DUPLICATES: records with equal keys" in e.value.stderr
    assert "not modelled" in e.value.stderr


def test_merge_refuses_an_input_out_of_order(tmp_path):
    """IBM: a MERGE's result is predictable only when every USING file is in key order. SORTUG with M1FILE's last
    record moved first in key order: the run stops by name at the MERGE."""
    pytest.importorskip("tree_sitter_language_pack")
    if _java() is None:
        pytest.skip("needs JAVA_HOME / JDK_17")
    src = FILE_PROGRAMS["SORTUG"].replace("'EEE'", "'@@@'")
    with pytest.raises(subprocess.CalledProcessError) as e:
        _java_run_batch("SORTUG", src, tmp_path, FILE_DDS["SORTUG"])
    assert "MERGE SORT-FILE: an input file out of key order" in e.value.stderr


def test_alphabets_keep_each_definition_whole():
    """program.alphabets: a word definition, a literal alphabet's tokens (doubled quotes kept, FOR ALPHANUMERIC,
    across lines) up to the next clause, and "?" for a token no literal alphabet has (a hexadecimal literal)."""
    from gitgalaxy.tools.cobol_to_java.det.program import alphabets
    from gitgalaxy.tools.cobol_to_java.det.source import logical_lines

    src = fprogram("ALPH", ["ALPHABET EB IS EBCDIC", "ALPHABET LT FOR ALPHANUMERIC IS 'A' ALSO 'a' 'it''s'",
                            "    SPACE 'z' THRU 'q' 7", "ALPHABET HX IS 'A' X'C1'", "CLASS DIGIT IS '0' THRU '9'."],
                   [], [], [], ["MAIN-PARA.", "    GOBACK."]).replace("CONFIGURATION SECTION.\n",
                   "CONFIGURATION SECTION.\n       OBJECT-COMPUTER. GG PROGRAM COLLATING SEQUENCE LT.\n")  # fmt: skip
    names, pcs = alphabets(logical_lines(src.splitlines(), "a.cbl"))
    assert pcs == "LT"
    assert names["EB"] == ["EBCDIC"]
    assert names["LT"] == ["'A'", "ALSO", "'a'", "'it''s'", "SPACE", "'z'", "THRU", "'q'", "7"]
    assert names["HX"] == ["'A'", "?"]


@pytest.mark.parametrize(
    ("key", "alphabet"),
    [
        # '^': EBCDIC code page 037 puts it after the lower-case letters (X'B0'), GnuCOBOL's EBCDIC table before
        # them (X'5F')
        ("^b", "EB"),
        # 'A' and 'z', neither named by LT: after LT's characters in native order -- EBCDIC on z/OS ('z' first),
        # the data's bytes in GnuCOBOL ('A' first)
        ("Ab", "LT"),
    ],
)
def test_sort_under_an_alphabet_refuses_what_ibm_and_gnucobol_order_differently(key, alphabet, tmp_path):
    """SORTCS with one key changed so that IBM's sequence and GnuCOBOL's order two records differently: the port
    does not pick one, the run stops by name (register D1)."""
    pytest.importorskip("tree_sitter_language_pack")
    if _java() is None:
        pytest.skip("needs JAVA_HOME / JDK_17")
    src = PROGRAMS["SORTCS"].replace("'abaQ5-3 7T01'", f"'{key}aQ5-3 7T01'")
    assert src != PROGRAMS["SORTCS"]
    with pytest.raises(subprocess.CalledProcessError) as e:
        _java_run("SORTCS", src, tmp_path)
    assert f"COLLATING SEQUENCE {alphabet}: keys" in e.value.stderr
    assert "ordered differently by IBM and by GnuCOBOL (register D1): not modelled" in e.value.stderr


# ---- #4462: a multi-program source, one program at a time; a reference modification of an intrinsic function -----
MULTI = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID.    MULTI.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-UP                  PIC X(4).
       01  WS-SRC                 PIC X(8) VALUE 'abcdefgh'.
       PROCEDURE DIVISION.
           MOVE FUNCTION UPPER-CASE(WS-SRC) (3:4) TO WS-UP
           DISPLAY 'MULTI ' WS-UP
           MOVE FUNCTION CURRENT-DATE (1:2) TO WS-UP
           IF WS-UP(1:2) = '20' DISPLAY 'CENTURY 20' END-IF
           MOVE ALL X'4142' TO WS-UP
           DISPLAY WS-UP
           GOBACK.
       IDENTIFICATION DIVISION.
       PROGRAM-ID.    INNER.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-I                   PIC 9(4) VALUE 41.
       PROCEDURE DIVISION.
           ADD 1 TO WS-I
           DISPLAY 'INNER ' WS-I
           GOBACK.
       END PROGRAM INNER.
       END PROGRAM MULTI.
       IDENTIFICATION DIVISION.
       PROGRAM-ID.    SIBLING.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-LINES               PIC 9(4) VALUE 7.
       PROCEDURE DIVISION.
           DISPLAY 'SIBLING ' WS-LINES
           GOBACK.
       END PROGRAM SIBLING.
"""


@pytest.mark.skipif(_java() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
@pytest.mark.parametrize("unit, want", [(None, "MULTI CDEF\nCENTURY 20\nABAB\n"), ("INNER", "INNER 0042\n"),
                                        ("SIBLING", "SIBLING 0007\n")])  # fmt: skip
def test_each_program_of_a_multi_program_source_translates_and_runs_on_its_own(unit, want, tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    assert _java_run("MULTI", MULTI, tmp_path, unit=unit) == want
