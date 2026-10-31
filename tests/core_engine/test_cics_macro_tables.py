"""
#5120: CICS resource macro tables (DFHFCT / DFHPCT / DFHPPT / DFHDCT / DFHTST, and #5154's DFHSIT / DFHSRT /
DFHJCT / DFHTCT / DFHMCT) as
`csd_resources` rows -- core/cics_macro_tables.py through `extract_boundary` as hlasm.

The syntax is read from IBM's macro reference, cited in the module header (register X62):
"CICS Resource Definition Guide", CICS TS for OS/390 Release 3, SC33-1684-30,
ch.13 (DFHFCT TYPE=FILE|REMOTE, DFHDCT TYPE=SDSCI|EXTRA|INDIRECT|INTRA|REMOTE,
DFHTCT TYPE=INITIAL|REGION|TERMINAL|REMOTE, DFHTST TYPE=LOCAL|RECOVERY|REMOTE|SECURITY),
ch.16 (macro -> RDO attribute table) and ch.17 (migrating the TCT to the CSD);
"Resource Definition Guide", CICS TS for VSE/ESA Release 1, SC33-1653-05, ch.29 (DFHJCT
TYPE=ENTRY,JFILEID={SYSTEM|nn}), ch.33 (DFHTCT TYPE=GPENTRY), and Appendices C/E/F (DFHPCT,
DFHPPT PROGRAM=/MAPSET=/PARTSET=/USAGE=MAP); CICS/VS System Programmer's Reference Manual
SH20-1043-6 (DFHDCT, DFHPCT, DFHPPT); CICS for MVS/ESA Migration Guide V4R1 GC33-1162-04;
and IBM APAR II05097 (`DFHPPT TYPE=ENTRY,MAPSET=`). The PPT `PARTITIONSET=` spelling is
ASSUMED as an alias of `PARTSET=` (register X62). DFHSIT SUFFIX= and the refusals of DFHMCT TYPE=RECORD and
DFHTCT TYPE=LINE / SDSCI are read from the CICS TS 5.x pages the module header cites. Every fixture is hand-written, with a
labelled and an unlabelled statement, column-72 continuation, comments and lower case.
"""

import time
from pathlib import Path

import pytest

from gitgalaxy.core.cics_macro_tables import sdsci_recform
from gitgalaxy.core.mainframe_boundary import extract_boundary

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "cics_macro_estate"


def _rows(src: str) -> list[dict]:
    return extract_boundary("hlasm", src).get("csd_resources", [])  # an empty stream carries no channel keys


def _lifted(src: str) -> list[tuple]:
    keys = (
        "resource_type",
        "name",
        "dsname",
        "ddname",
        "record_format",
        "key_length",
        "record_size",
        "queue_type",
        "program",
        "transid",
    )
    return [tuple(r[k] for k in keys) for r in _rows(src)]


def _rdo(row: dict) -> str:
    """The restated-under-RDO-names tail of `attributes`."""
    return row["attributes"].split(" => ", 1)[1] if " => " in row["attributes"] else ""


def _cont(first: str, *more: str) -> str:
    """A statement continued at column 72; each following line resumes at column 16."""
    lines = [first, *[" " * 15 + m for m in more]]
    return "\n".join(ln.ljust(71) + "X" if i < len(lines) - 1 else ln for i, ln in enumerate(lines))


# --- DFHFCT -----------------------------------------------------------------------------------


def test_dfhfct_type_file_is_a_file_with_its_join_attributes():
    src = "\n".join(
        [
            "         DFHFCT TYPE=INITIAL,SUFFIX=01",
            _cont(
                "ACCT     DFHFCT TYPE=FILE,ACCMETH=BDAM,FILE=ACCTDAT,",
                "DSNAME=BANK.ACCT.DAM,RECFORM=(FIXED,BLOCKED),",
                "BLKSIZE=600,LRECL=300,KEYLEN=11",
            ),
            "         DFHFCT TYPE=FINAL",
        ]
    )
    assert _lifted(src) == [("FILE", "ACCTDAT", "BANK.ACCT.DAM", None, "F", 11, 300, None, None, None)]
    row = _rows(src)[0]
    assert (row["source"], row["macro_table"], row["line"]) == ("MACRO", "DFHFCT01", 2)
    assert "KEYLEN=11" in row["attributes"]


def test_dfhfct_reads_both_the_file_and_the_retained_dataset_spelling():
    # RDG p.391: TYPE=DATASET / DATASET= are "retained for compatibility ... exactly the same".
    tail = ",DSNAME=A.B,KEYLEN=16,LRECL=80,RECFORM=(VARIABLE,BLOCKED)"
    new = _cont("         DFHFCT TYPE=FILE,FILE=CUST,", tail.lstrip(","))
    old = _cont("         DFHFCT TYPE=DATASET,DATASET=CUST,", tail.lstrip(","))
    mixed = _cont("         DFHFCT TYPE=FILE,DATASET=CUST,", tail.lstrip(","))
    want = [("FILE", "CUST", "A.B", None, "V", 16, 80, None, None, None)]
    assert _lifted(new) == _lifted(old) == _lifted(mixed) == want


@pytest.mark.parametrize(
    ("operand", "expected"),
    [
        ("RECFORM=FIXED", "F"),
        ("RECFORM=VARIABLE", "V"),
        ("RECFORM=UNDEFINED", "U"),
        ("RECFORM=(FIXED,BLOCKED,FBS)", "F"),
        ("RECFORM=(VARIABLE,UNBLOCKED)", "V"),
        ("RECFORM=(,BLOCKED)", None),  # the format word is optional
        ("RECFORM=WEIRD", None),  # a word the manual does not list claims nothing
        ("RECFORM=V", None),
        ("", None),
    ],
)
def test_dfhfct_recform_first_element_is_the_rdo_file_recordformat(operand, expected):
    src = f"         DFHFCT TYPE=FILE,FILE=A,{operand}" if operand else "         DFHFCT TYPE=FILE,FILE=A"
    assert _rows(src)[0]["record_format"] == expected


def test_dfhfct_remote_and_the_refused_and_unnamed_forms():
    src = "\n".join(
        [
            _cont("         DFHFCT TYPE=REMOTE,FILE=RMT,SYSIDNT=SYSB,RMTNAME=O,", "KEYLEN=8,LRECL=80"),
            "         DFHFCT TYPE=FILE,FILE=A,RECSIZE=999,KEYLEN=nan",  # RECSIZE is not an FCT operand
            "         DFHFCT TYPE=FILE",  # no FILE= -> no resource
            "         DFHFCT TYPE=GROUP,GROUP=X",  # CSD-migration statement
        ]
    )
    assert _lifted(src) == [
        ("FILE", "RMT", None, None, None, 8, 80, None, None, None),
        ("FILE", "A", None, None, None, None, None, None, None, None),
    ]
    assert "SYSIDNT=SYSB" in _rows(src)[0]["attributes"]
    assert _rdo(_rows(src)[0]) == "REMOTESYSTEM(SYSB) REMOTENAME(O)"


# --- DFHPCT / DFHPPT --------------------------------------------------------------------------


def test_dfhpct_entry_is_a_transaction_routing_to_its_program():
    src = "\n".join(
        [
            _cont(
                "         DFHPCT TYPE=ENTRY,TRANSID=BA01,PROGRAM=BANKINQ,TWASIZE=64,",
                "TRNPRTY=100,DTB=(YES,WAIT)",
            ),
            _cont(
                "         DFHPCT TYPE=ENTRY,TRANSID=RMT1,SYSIDNT=SYSB,RMTNAME=RR01,",
                "PARTSET=PS1,DTB=YES",
            ),
            "         DFHPCT TYPE=GROUP,FN=X",
        ]
    )
    assert _lifted(src) == [
        ("TRANSACTION", "BA01", None, None, None, None, None, None, "BANKINQ", "BA01"),
        ("TRANSACTION", "RMT1", None, None, None, None, None, None, None, "RMT1"),
    ]
    rows = _rows(src)
    assert _rdo(rows[0]) == "PRIORITY(100) INDOUBT(WAIT)"
    assert _rdo(rows[1]) == "REMOTESYSTEM(SYSB) REMOTENAME(RR01) PARTITIONSET(PS1) INDOUBT(BACKOUT)"


def test_dfhppt_entry_names_a_program_a_mapset_or_a_partition_set():
    src = "\n".join(
        [
            _cont("         DFHPPT TYPE=ENTRY,PROGRAM=BANKINQ,PGMLANG=COBOL,RES=NO,", "PGMSTAT=ENABLED"),
            "         DFHPPT TYPE=ENTRY,PROGRAM=BANKMAP,USAGE=MAP",  # SC33-1653-05 p.372: PROGRAM + USAGE=MAP -> MAPSET
            "         DFHPPT TYPE=ENTRY,PROGRAM=BANKASM,PGMLANG=ASSEMBLER,USAGE=MAP",  # ASSEMBLER + USAGE=MAP -> MAPSET
            "         DFHPPT TYPE=ENTRY,PROGRAM=BANKCBL,PGMLANG=COBOL,USAGE=MAP",  # non-ASSEMBLER stays PROGRAM
            "         DFHPPT TYPE=ENTRY,MAPSET=DSTMAPSM,RES=YES",  # IBM APAR II05097; SC33-1653-05 p.372
            "         DFHPPT TYPE=ENTRY,PARTITIONSET=BANKPS",
            "         DFHPPT TYPE=ENTRY,PARTSET=OLDPS,USAGE=MAP",  # SC33-1653-05 p.349, p.372
            "         DFHPPT TYPE=ENTRY",
            "         DFHPPT TYPE=FINAL",
        ]
    )
    rows = _rows(src)
    assert [(r["resource_type"], r["name"], r["program"], _rdo(r)) for r in rows] == [
        ("PROGRAM", "BANKINQ", "BANKINQ", "LANGUAGE(COBOL) RESIDENT(NO) STATUS(ENABLED)"),
        ("MAPSET", "BANKMAP", None, "USAGE(TRANSIENT)"),
        ("MAPSET", "BANKASM", None, "USAGE(TRANSIENT)"),
        ("PROGRAM", "BANKCBL", "BANKCBL", "LANGUAGE(COBOL) USAGE(TRANSIENT)"),
        ("MAPSET", "DSTMAPSM", None, "RESIDENT(YES)"),
        ("PARTITIONSET", "BANKPS", None, ""),
        ("PARTITIONSET", "OLDPS", None, "USAGE(TRANSIENT)"),
    ]
    assert "PGMLANG=COBOL" in rows[0]["attributes"]


# --- DFHDCT -----------------------------------------------------------------------------------

# RDG p.376: the twelve SDSCI RECFORM words -> (RECORDFORMAT, BLOCKFORMAT, PRINTCONTROL).
SDSCI_WORDS = [
    ("FIXUNB", ("FIXED", "UNBLOCKED", None)),
    ("FIXBLK", ("FIXED", "BLOCKED", None)),
    ("VARUNB", ("VARIABLE", "UNBLOCKED", None)),
    ("VARBLK", ("VARIABLE", "BLOCKED", None)),
    ("FIXUNBA", ("FIXED", "UNBLOCKED", "ASA")),
    ("FIXBLKA", ("FIXED", "BLOCKED", "ASA")),
    ("VARUNBA", ("VARIABLE", "UNBLOCKED", "ASA")),
    ("VARBLKA", ("VARIABLE", "BLOCKED", "ASA")),
    ("FIXUNBM", ("FIXED", "UNBLOCKED", "MACHINE")),
    ("FIXBLKM", ("FIXED", "BLOCKED", "MACHINE")),
    ("VARUNBM", ("VARIABLE", "UNBLOCKED", "MACHINE")),
    ("VARBLKM", ("VARIABLE", "BLOCKED", "MACHINE")),
]


@pytest.mark.parametrize(("word", "expected"), SDSCI_WORDS)
def test_every_sdsci_recform_word_maps_to_the_csd_tdqueue_spelling(word, expected):
    assert sdsci_recform(word) == expected
    assert sdsci_recform(word.lower()) == expected
    src = f"         DFHDCT TYPE=EXTRA,DESTID=Q1,DSCNAME=DD1\n         DFHDCT TYPE=SDSCI,DSCNAME=DD1,RECFORM={word}"
    row = _rows(src)[0]
    record, block, control = expected
    assert row["record_format"] == record  # FIXED / VARIABLE, as a CSD TDQUEUE RECORDFORMAT
    tail = _rdo(row)
    assert f"RECORDFORMAT({record})" in tail and f"BLOCKFORMAT({block})" in tail
    assert (f"PRINTCONTROL({control})" in tail) == (control is not None)


@pytest.mark.parametrize("word", ["UNDEFINED", "VARIABLE", "FIXED", "FIXBLKX", "FIXUNBAM", "BLK", ""])
def test_a_recform_word_outside_the_manual_set_claims_nothing(word):
    assert sdsci_recform(word) == (None, None, None)
    src = f"         DFHDCT TYPE=EXTRA,DESTID=Q1,DSCNAME=DD1\n         DFHDCT TYPE=SDSCI,DSCNAME=DD1,RECFORM={word}"
    assert _rows(src)[0]["record_format"] is None
    if word:  # the word is still kept, as stated, for the reader to see
        assert f"RECFORM({word})" in _rdo(_rows(src)[0])


def test_sdsci_is_folded_into_its_extra_entry_in_either_order_and_has_no_dsname():
    sdsci = _cont("         DFHDCT TYPE=SDSCI,DSCNAME=AUDITDD,RECFORM=VARBLK,", "RECSIZE=132,DSNAME=NOT.AN.OPERAND")
    extra = "         DFHDCT TYPE=EXTRA,DESTID=AUDT,DSCNAME=AUDITDD"
    want = [("TDQUEUE", "AUDT", None, "AUDITDD", "VARIABLE", None, 132, "EXTRA", None, None)]
    assert _lifted(extra + "\n" + sdsci) == want
    assert _lifted(sdsci + "\n" + extra) == want  # DSNAME is not an SDSCI operand: never lifted


def test_extra_without_an_sdsci_and_the_destid_truncation():
    src = "         DFHDCT TYPE=EXTRA,DESTID=NODSC,DSCNAME=ORPHAN,LENGTH=80"
    row = _rows(src)[0]
    assert (row["name"], row["ddname"], row["record_format"], row["record_size"]) == ("NODS", "ORPHAN", None, 80)


def test_intra_lifts_transid_and_trigger_level():
    src = "\n".join(
        [
            _cont("         DFHDCT TYPE=INTRA,DESTID=CSSL,DESTFAC=FILE,", "TRANSID=CSML,TRIGLEV=5"),
            "         DFHDCT TYPE=INTRA,DESTID=ATI1,TRANSID=CSMT",  # TRIGLEV defaults to 1
            "         DFHDCT TYPE=INTRA,DESTID=OFF1,TRANSID=CSMT,TRIGLEV=0",  # 0: no ATI trigger
            "         DFHDCT TYPE=INTRA,DESTID=BIG1,TRANSID=CSMT,TRIGLEV=40000",  # over the 32767 maximum
            "         DFHDCT TYPE=INTRA,DESTID=PLN1,DESTRCV=LG",  # no ATI at all
            "         DFHDCT TYPE=INTRA,DESTID=LVL1,TRIGLEV=3",  # a level with no transaction
        ]
    )
    rows = {r["name"]: r for r in _rows(src)}
    assert [(n, r["transid"], _rdo(r)) for n, r in rows.items()] == [
        ("CSSL", "CSML", "TRANSID(CSML) TRIGGERLEVEL(5)"),
        ("ATI1", "CSMT", "TRANSID(CSMT) TRIGGERLEVEL(1)"),
        ("OFF1", "CSMT", "TRANSID(CSMT) TRIGGERLEVEL(0)"),
        ("BIG1", "CSMT", "TRANSID(CSMT) TRIGGERLEVEL(1)"),
        ("PLN1", None, ""),
        ("LVL1", None, "TRIGGERLEVEL(3)"),
    ]
    assert {r["queue_type"] for r in rows.values()} == {"INTRA"}
    assert "TRIGLEV=5" in rows["CSSL"]["attributes"]


def test_indirect_and_remote_queues():
    src = "\n".join(
        [
            "         DFHDCT TYPE=INDIRECT,DESTID=ALIA,INDDEST=CSSL",
            _cont("         DFHDCT TYPE=REMOTE,DESTID=RMTQ,SYSIDNT=SYSB,", "LENGTH=80,RMTNAME=O1"),
            "         DFHDCT TYPE=GROUP,GROUP=X",
        ]
    )
    assert _lifted(src) == [
        ("TDQUEUE", "ALIA", None, None, None, None, None, "INDIRECT", None, None),
        ("TDQUEUE", "RMTQ", None, None, None, None, 80, "REMOTE", None, None),
    ]
    assert "INDDEST=CSSL" in _rows(src)[0]["attributes"]
    assert _rdo(_rows(src)[0]) == "INDIRECTNAME(CSSL)"
    assert "RMTNAME=O1" in _rows(src)[1]["attributes"]
    assert _rdo(_rows(src)[1]) == "REMOTESYSTEM(SYSB) REMOTENAME(O1)"


# --- DFHTST -----------------------------------------------------------------------------------


def test_dfhtst_dataid_list_is_one_tsmodel_per_prefix_with_its_rdo_attributes():
    src = "\n".join(
        [
            "         DFHTST TYPE=LOCAL,DATAID=(BANK,AUDT)",
            "         DFHTST TYPE=RECOVERY,DATAID=RCV",
            "         DFHTST TYPE=ENTRY,DATAID=OLD",  # retained spelling of RECOVERY (RDG p.484)
            "         DFHTST TYPE=SECURITY,DATAID=SEC",
            "         DFHTST TYPE=REMOTE,DATAID=RMT,SYSIDNT=SYSB,RMTNAME=RXX",
        ]
    )
    assert [(r["resource_type"], r["name"], _rdo(r)) for r in _rows(src)] == [
        ("TSMODEL", "BANK", ""),
        ("TSMODEL", "AUDT", ""),
        ("TSMODEL", "RCV", "RECOVERY(YES)"),
        ("TSMODEL", "OLD", "RECOVERY(YES)"),
        ("TSMODEL", "SEC", "SECURITY(YES)"),
        ("TSMODEL", "RMT", "REMOTESYSTEM(SYSB) REMOTEPREFIX(RXX)"),
    ]


def test_dfhtst_refuses_the_null_dataid_and_shared_pools():
    src = "         DFHTST TYPE=LOCAL,DATAID=()\n         DFHTST TYPE=SHARED,SYSIDNT=POOL,POOL=P1\n         DFHTST TYPE=LOCAL,DATAID=\n"
    assert _rows(src) == []


# --- shared reading rules ---------------------------------------------------------------------


def test_suffix_names_the_assembled_table_and_is_per_table():
    src = "\n".join(
        [
            "         DFHPCT TYPE=INITIAL,SUFFIX=A1",
            "         DFHPCT TYPE=ENTRY,TRANSID=T1,PROGRAM=P1",
            "         DFHPPT TYPE=ENTRY,PROGRAM=P1",
            "         DFHDCT TYPE=(INITIAL,MIGRATE),SUFFIX=B2",
            "         DFHDCT TYPE=INTRA,DESTID=Q1",
        ]
    )
    assert [r["macro_table"] for r in _rows(src)] == ["DFHPCTA1", "DFHPPT", "DFHDCTB2"]


def test_lower_case_comments_and_non_table_macros_are_handled():
    src = "\n".join(
        [
            "* DFHFCT TYPE=FILE,FILE=COMMENT",
            "         dfhfct type=file,file=lower,dsname=a.b",
            "         DFHMSD TYPE=&SYSPARM,MODE=INOUT",  # a BMS macro, not a resource table
            "         MVC   DFHFCT,=C'DFHFCT TYPE=FILE,FILE=NOT'",
        ]
    )
    assert [(r[1], r[2]) for r in _lifted(src)] == [("LOWER", "A.B")]


def test_text_with_no_table_macro_yields_nothing_and_never_raises():
    assert _rows("") == []
    assert _rows("         MVC A,B\n") == []
    assert _rows("         DFHFCT TYPE=FILE,FILE=(\n") == []  # an unbalanced list names nothing
    assert _rows("         DFHFCT\n         DFHDCT TYPE=\n         DFHTST TYPE=LOCAL,DATAID=\n") == []


def test_a_pathological_statement_is_cpu_bounded():
    src = (
        "         DFHFCT TYPE=FILE,FILE=A,"
        + "(" * 50000
        + "\n"
        + ("         DFHTST TYPE=LOCAL,DATAID=" + ",".join("PPP" for _ in range(2000)) + "\n") * 50
    )
    start = time.process_time()
    _rows(src)
    assert time.process_time() - start < 5


def test_the_fixture_estates_read_every_table():
    types = set()
    for estate in ("tables_only", "tables_and_csd"):
        rows = []
        for path in sorted((FIXTURES / estate).glob("*.asm")):
            rows += extract_boundary("hlasm", path.read_text())["csd_resources"]
        assert {r["source"] for r in rows} == {"MACRO"}
        if estate == "tables_only":
            types = {r["resource_type"] for r in rows}
    assert types == {
        "FILE",
        "TRANSACTION",
        "PROGRAM",
        "MAPSET",
        "PARTITIONSET",
        "TDQUEUE",
        "TSMODEL",
        "SIT",
        "SRT",
        "JOURNAL",
        "TERMINAL",
        "CONNECTION",
        "MONITORPOINT",
        "PLT",
        "DB2CONN",
        "DB2ENTRY",
    }


# --- #5154: DFHSRT / DFHJCT / DFHTCT / DFHMCT / DFHSIT and tables assembled in JCL --------------


def _named(src: str, rtype: str) -> list[str]:
    return [r["name"] for r in _rows(src) if r["resource_type"] == rtype]


@pytest.mark.parametrize(
    ("operands", "expected"),
    [
        ("TYPE=SYSTEM,ABCODE=(0C1,0C4),RECOVER=YES", ["S0C1", "S0C4"]),
        ("TYPE=SYSTEM,ABCODE=0c7,RECOVER=YES", ["S0C7"]),  # parentheses optional for one code; any case
        ("TYPE=USER,ABCODE=(1234,77),RECOVER=YES", ["U1234", "U77"]),
        ("TYPE=SYSTEM,ABCODE=(0C1),RECOVER=NO", []),  # a removal is not a definition
        ("TYPE=SYSTEM,ABCODE=(0C1)", []),  # RECOVER omitted reads as NO
        ("TYPE=SYSTEM,ABCODE=(0C1,ZZZ,0C12),RECOVER=YES", ["S0C1"]),  # not three hex digits
        ("TYPE=USER,ABCODE=(12345,AB),RECOVER=YES", []),  # not a decimal number of at most four digits
        ("TYPE=SYSTEM,RECOVER=YES", []),  # no ABCODE
        ("TYPE=INITIAL,SUFFIX=01", []),
        ("TYPE=FINAL", []),
    ],
)
def test_dfhsrt_rows_are_the_recoverable_abend_codes(operands, expected):
    assert _named(f"         DFHSRT {operands}\n", "SRT") == expected


@pytest.mark.parametrize(
    ("src", "expected"),
    [
        # label, lower case, a quoted code and a parenthesised one
        ("MYSRT    dfhsrt type=system,abcode=('0c1',(0c4)),recover=(yes)\n", ["S0C1", "S0C4"]),
        # a repeated code is one row, in one statement or across two
        ("         DFHSRT TYPE=SYSTEM,ABCODE=(0C1,0C1,0C4),RECOVER=YES\n", ["S0C1", "S0C4"]),
        (
            "         DFHSRT TYPE=SYSTEM,ABCODE=0C1,RECOVER=YES\n         DFHSRT TYPE=SYSTEM,ABCODE=0C1,RECOVER=YES\n",
            ["S0C1"],
        ),
        # RECOVER=NO takes out what an earlier YES defined in the same table, and a later YES puts it back
        (
            "         DFHSRT TYPE=SYSTEM,ABCODE=(0C1,0C4),RECOVER=YES\n         DFHSRT TYPE=SYSTEM,ABCODE=0C1,RECOVER=NO\n",
            ["S0C4"],
        ),
        (
            "         DFHSRT TYPE=SYSTEM,ABCODE=0C1,RECOVER=NO\n         DFHSRT TYPE=SYSTEM,ABCODE=0C1,RECOVER=YES\n",
            ["S0C1"],
        ),
        # SYSTEM and USER codes are different names: a USER removal leaves the SYSTEM code
        (
            "         DFHSRT TYPE=SYSTEM,ABCODE=123,RECOVER=YES\n         DFHSRT TYPE=USER,ABCODE=123,RECOVER=NO\n",
            ["S123"],
        ),
        ("         DFHSRT ABCODE=(0C1),RECOVER=YES\n", []),  # no TYPE names no kind of code
        ("* DFHSRT TYPE=SYSTEM,ABCODE=(0C1),RECOVER=YES\n", []),  # a comment line
        (_cont("         DFHSRT TYPE=SYSTEM,ABCODE=(0C1,0C4),", "RECOVER=YES"), ["S0C1", "S0C4"]),
        ("         DFHSRT TYPE=USER,ABCODE=(0012),RECOVER=YES\n", ["U0012"]),
    ],
)
def test_dfhsrt_effective_table(src, expected):
    assert _named(src, "SRT") == expected


def test_dfhsrt_removal_keeps_the_defining_line():
    src = (
        "         DFHSRT TYPE=SYSTEM,ABCODE=(0C1,0C4),RECOVER=YES\n         DFHSRT TYPE=SYSTEM,ABCODE=0C1,RECOVER=NO\n"
    )
    ((name, line),) = [(r["name"], r["line"]) for r in _rows(src) if r["resource_type"] == "SRT"]
    assert (name, line) == ("S0C4", 1)


def test_dfhsrt_row_provenance():
    (row,) = _rows("         DFHSRT TYPE=INITIAL,SUFFIX=01\n         DFHSRT TYPE=USER,ABCODE=(9),RECOVER=YES\n")
    assert (row["source"], row["macro_table"], row["line"], row["queue_type"]) == ("MACRO", "DFHSRT01", 2, None)
    assert "RECOVER(YES)" in _rdo(row)


@pytest.mark.parametrize(
    ("operands", "expected"),
    [
        ("TYPE=ENTRY,JFILEID=SYSTEM,JTYPE=DISK2", ["SYSTEM"]),
        ("TYPE=ENTRY,JFILEID=(05),JTYPE=TAPE", ["05"]),
        ("TYPE=ENTRY,JFILEID=2,JTYPE=DISK1,BUFSIZE=1500", ["2"]),
        ("TYPE=ENTRY,JFILEID=99,JTYPE=SMF,FORMAT=SMF", ["99"]),
        ("TYPE=ENTRY,JFILEID=0,JTYPE=DISK1", []),  # outside 1-99
        ("TYPE=ENTRY,JFILEID=100,JTYPE=DISK1", []),  # more than two digits
        ("TYPE=ENTRY,JFILEID=BOGUS,JTYPE=DISK1", []),  # neither SYSTEM nor nn
        ("TYPE=ENTRY,JTYPE=DISK1", []),  # no JFILEID
        ("TYPE=INITIAL,SUFFIX=01", []),
        ("TYPE=FINAL", []),
    ],
)
def test_dfhjct_entry_is_a_journal(operands, expected):
    assert _named(f"         DFHJCT {operands}\n", "JOURNAL") == expected


@pytest.mark.parametrize(
    ("src", "expected"),
    [
        ("DFHJCT   CSECT\n", []),  # a label line is no macro
        ("         dfhjct type=entry,jfileid=system\n", ["SYSTEM"]),
        ("MYJCT    DFHJCT TYPE=ENTRY,JFILEID=(SYSTEM)\n", ["SYSTEM"]),  # label, parenthesised value
        ("         DFHJCT JFILEID=SYSTEM\n", []),  # no TYPE names no entry
        ("* DFHJCT TYPE=ENTRY,JFILEID=SYSTEM\n", []),  # a comment line
        (_cont("         DFHJCT TYPE=ENTRY,JFILEID=03,", "JTYPE=TAPE1,BUFSIZE=4096"), ["03"]),
        ("         DFHJCT TYPE=ENTRY,JFILEID=1\n         DFHJCT TYPE=ENTRY,JFILEID=2\n", ["1", "2"]),
    ],
)
def test_dfhjct_statement_shapes(src, expected):
    assert _named(src, "JOURNAL") == expected


def test_dfhjct_dsname_is_lifted_as_an_assumed_operand():
    """DSNAME= is not among [VSE Table 41 p.270-272]'s JCT operands; it is lifted anyway (ASSUMED, estate H-0063)."""
    (row,) = _rows("         DFHJCT TYPE=ENTRY,JFILEID=01,DSNAME=A.B\n")
    assert row["dsname"] == "A.B" and "DSNAME=A.B" in row["attributes"]
    (row,) = _rows("         DFHJCT TYPE=ENTRY,JFILEID=01\n")
    assert row["dsname"] is None


@pytest.mark.parametrize("jtype", ["TAPE1", "TAPE2", "DISK1", "DISK2", "SMF", "TAPE"])
def test_dfhjct_jtype_never_decides_the_row(jtype):
    """JTYPE= is listed as {TAPE1|TAPE2|DISK1|DISK2|SMF} [VSE Table 41 p.270-272]; the journal is named by JFILEID alone.

    A word outside that list (`TAPE`) still yields the row (ASSUMED: the manual is silent on what it means); JTYPE,
    BUFSIZE and JOUROPT are kept verbatim in `attributes`.
    """
    (row,) = _rows(f"         DFHJCT TYPE=ENTRY,JFILEID=4,JTYPE={jtype},BUFSIZE=40,JOUROPT=P\n")
    assert (row["resource_type"], row["name"]) == ("JOURNAL", "4")
    assert all(f in row["attributes"] for f in (f"JTYPE={jtype}", "BUFSIZE=40", "JOUROPT=P"))


def test_dfhjct_repeated_journal_is_not_folded():
    """Unlike DFHSRT (#7211) no JCT rule folds a repeated JFILEID: `01` and `1` stay two rows, in source order.

    Pinned as current behavior; IBM's Table 41 does not say what a repeated entry means (left open, #5154).
    """
    src = "".join(f"         DFHJCT TYPE=ENTRY,JFILEID={j}\n" for j in ("01", "1", "SYSTEM", "SYSTEM"))
    assert _named(src, "JOURNAL") == ["01", "1", "SYSTEM", "SYSTEM"]


def test_dfhjct_suffix_names_the_table_and_assembled_in_jcl():
    src = "         DFHJCT TYPE=INITIAL,SUFFIX=A1\n         DFHJCT TYPE=ENTRY,JFILEID=SYSTEM\n"
    (row,) = _rows(src)
    assert (row["macro_table"], row["line"]) == ("DFHJCTA1", 2)
    job = "//J JOB\n//ASM EXEC PGM=ASMA90\n//SYSIN DD *\n" + src + "/*\n"
    rows = extract_boundary("jcl", job)["csd_resources"]
    assert [(r["name"], r["macro_table"], r["line"]) for r in rows] == [("SYSTEM", "DFHJCTA1", 5)]


@pytest.mark.parametrize(
    ("operands", "rtype", "expected"),
    [
        ("TYPE=TERMINAL,TRMIDNT=T001,ACCMETH=VTAM,TRMTYPE=3270", "TERMINAL", ["T001"]),
        ("TYPE=REMOTE,SYSIDNT=SYSB,TRMIDNT=r001,RMTNAME=RR01", "TERMINAL", ["R001"]),
        ("TYPE=GPENTRY,TRMIDNT=SEQ2,GPBLKSZ=(80,80),GPTYPE=(2540,1403),LININL=80", "TERMINAL", ["SEQ2"]),
        ("TYPE=SYSTEM,SYSIDNT=SYSB,ACCMETH=IRC", "CONNECTION", ["SYSB"]),
        ("TYPE=TERMINAL,ACCMETH=VTAM", "TERMINAL", []),  # no TRMIDNT
        ("TYPE=LINE,ACCMETH=VTAM", "TERMINAL", []),
        ("TYPE=GPENTRY,ENTRY=TERMINAL", "TERMINAL", []),  # no TRMIDNT
        ("TYPE=SDSCI,DSCNAME=X", "TERMINAL", []),
        ("TYPE=INITIAL,SUFFIX=01,SYSIDNT=HOME", "CONNECTION", []),
    ],
)
def test_dfhtct_terminals_and_systems(operands, rtype, expected):
    assert _named(f"         DFHTCT {operands}\n", rtype) == expected


def test_dfhtct_keeps_the_operands_it_does_not_lift():
    (row,) = _rows("         DFHTCT TYPE=REMOTE,SYSIDNT=SYSB,TRMIDNT=R001,RMTNAME=RR01\n")
    assert "SYSIDNT=SYSB" in row["attributes"] and "RMTNAME=RR01" in row["attributes"]
    assert _rdo(row) == "REMOTESYSTEM(SYSB) REMOTENAME(RR01)"
    assert row["macro_table"] == "DFHTCT"


def test_dfhtct_region_and_initial_sysidnt_control_remote_terminal_routing():
    """RDG p.473-475 & p.552-553: TYPE=REGION sets REMOTESYSTEM until LOCAL or matching TYPE=INITIAL,SYSIDNT=."""
    src = "\n".join(
        [
            "         DFHTCT TYPE=INITIAL,SUFFIX=01,SYSIDNT=HOME",
            "         DFHTCT TYPE=TERMINAL,TRMIDNT=T001,ACCMETH=VTAM",
            "         DFHTCT TYPE=REGION,SYSIDNT=SYSB",
            "         DFHTCT TYPE=TERMINAL,TRMIDNT=T002,ACCMETH=VTAM",
            "         DFHTCT TYPE=REGION,SYSIDNT=LOCAL",
            "         DFHTCT TYPE=TERMINAL,TRMIDNT=T003,ACCMETH=VTAM",
            "         DFHTCT TYPE=REGION,SYSIDNT=HOME",
            "         DFHTCT TYPE=TERMINAL,TRMIDNT=T004,ACCMETH=VTAM",
            "         DFHTCT TYPE=REMOTE,SYSIDNT=HOME,TRMIDNT=T005,RMTNAME=RR05",  # matches INITIAL SYSIDNT -> local
            "         DFHTCT TYPE=REMOTE,SYSIDNT=SYSC,TRMIDNT=T006,RMTNAME=RR06",
            "         DFHTCT TYPE=SYSTEM,SYSIDNT=SYSB,ACCMETH=IRC",
        ]
    )
    rows = {r["name"]: r for r in _rows(src)}
    assert [(n, _rdo(rows[n])) for n in ("T001", "T002", "T003", "T004", "T005", "T006", "SYSB")] == [
        ("T001", ""),
        ("T002", "REMOTESYSTEM(SYSB)"),
        ("T003", ""),
        ("T004", ""),
        ("T005", "REMOTENAME(RR05)"),
        ("T006", "REMOTESYSTEM(SYSC) REMOTENAME(RR06)"),
        ("SYSB", "ACCESSMETHOD(IRC)"),
    ]


@pytest.mark.parametrize(
    ("operand", "expected"),
    [
        ("180", ["USER.180"]),
        ("(PP,3)", ["USER.202"]),  # "equivalent to ID 199 + number"
        ("(PP,56)", ["USER.255"]),
        ("(PP,57)", []),
        ("BANK.180", ["BANK.180"]),
        ("bank.7", ["BANK.7"]),
        ("0", []),
        ("256", []),
        ("BANK.", []),
        ("ABC", []),
    ],
)
def test_dfhmct_emp_id_forms(operand, expected):
    assert _named(f"         DFHMCT TYPE=EMP,CLASS=PERFORM,ID={operand}\n", "MONITORPOINT") == expected


@pytest.mark.parametrize(
    ("src", "expected"),
    [
        ("DFHTCT   CSECT\n", []),  # a label line is no macro
        ("         dfhtct type=terminal,trmidnt=t1\n", ["T1"]),
        ("MYTCT    DFHTCT TYPE=TERMINAL,TRMIDNT=(T1)\n", ["T1"]),  # label, parenthesised value
        ("         DFHTCT TRMIDNT=T1\n", []),  # no TYPE names no entry
        ("* DFHTCT TYPE=TERMINAL,TRMIDNT=T1\n", []),  # a comment line
        (_cont("         DFHTCT TYPE=TERMINAL,TRMIDNT=T1,", "TRMTYPE=3270"), ["T1"]),
        ("         DFHTCT TYPE=TERMINAL,TRMIDNT=T1\n         DFHTCT TYPE=GPENTRY,TRMIDNT=T2\n", ["T1", "T2"]),
    ],
)
def test_dfhtct_statement_shapes(src, expected):
    assert _named(src, "TERMINAL") == expected


@pytest.mark.parametrize(
    ("src", "expected"),
    [
        ("DFHMCT   CSECT\n", []),
        ("         dfhmct type=emp,class=perform,id=180\n", ["USER.180"]),
        ("MYMCT    DFHMCT TYPE=EMP,CLASS=PERFORM,ID=(PP,3)\n", ["USER.202"]),
        ("         DFHMCT CLASS=PERFORM,ID=180\n", []),
        ("* DFHMCT TYPE=EMP,CLASS=PERFORM,ID=180\n", []),
        (_cont("         DFHMCT TYPE=EMP,CLASS=PERFORM,", "ID=BANK.7"), ["BANK.7"]),
        ("         DFHMCT TYPE=EMP,ID=1\n         DFHMCT TYPE=EMP,ID=2\n", ["USER.1", "USER.2"]),
    ],
)
def test_dfhmct_statement_shapes(src, expected):
    assert _named(src, "MONITORPOINT") == expected


@pytest.mark.parametrize(
    ("op", "entry", "rtype", "name", "table"),
    [
        ("DFHTCT", "TYPE=TERMINAL,TRMIDNT=T1", "TERMINAL", "T1", "DFHTCTA1"),
        ("DFHTCT", "TYPE=SYSTEM,SYSIDNT=SYSB,ACCMETH=IRC", "CONNECTION", "SYSB", "DFHTCTA1"),
        ("DFHMCT", "TYPE=EMP,CLASS=PERFORM,ID=180", "MONITORPOINT", "USER.180", "DFHMCTA1"),
    ],
)
def test_tct_and_mct_suffix_names_the_table_and_assembled_in_jcl(op, entry, rtype, name, table):
    src = f"         {op} TYPE=INITIAL,SUFFIX=A1\n         {op} {entry}\n"
    (row,) = _rows(src)
    assert (row["resource_type"], row["name"], row["macro_table"], row["line"]) == (rtype, name, table, 2)
    job = "//J JOB\n//ASM EXEC PGM=ASMA90\n//SYSIN DD *\n" + src + "/*\n"
    rows = extract_boundary("jcl", job)["csd_resources"]
    assert [(r["name"], r["macro_table"], r["line"]) for r in rows] == [(name, table, 5)]
    # a suffix longer than two characters names no table: the rows keep the bare table name
    (row,) = _rows(src.replace("A1", "ABC"))
    assert row["macro_table"] == op


def test_dfhtct_region_state_holds_inside_jcl_sysin():
    src = (
        "         DFHTCT TYPE=INITIAL,SUFFIX=01,SYSIDNT=HOME\n"
        "         DFHTCT TYPE=REGION,SYSIDNT=SYSB\n"
        "         DFHTCT TYPE=TERMINAL,TRMIDNT=T2,ACCMETH=VTAM\n"
    )
    job = "//J JOB\n//ASM EXEC PGM=ASMA90\n//SYSIN DD *\n" + src + "/*\n"
    (row,) = extract_boundary("jcl", job)["csd_resources"]
    assert (row["name"], row["macro_table"], _rdo(row)) == ("T2", "DFHTCT01", "REMOTESYSTEM(SYSB)")


def test_dfhmct_other_types_are_refused():
    src = "         DFHMCT TYPE=RECORD,CLASS=PERFORM\n         DFHMCT TYPE=INITIAL,SUFFIX=01\n"
    assert _rows(src) == []


def test_dfhsit_is_one_row_with_its_parameters_in_attributes():
    src = "         DFHSIT TYPE=CSECT,FCT=01,DCT=01,SRT=01\n"
    (row,) = _rows(src)
    assert (row["resource_type"], row["name"], row["macro_table"]) == ("SIT", "DFHSIT", "DFHSIT")
    assert "FCT=01" in row["attributes"] and "SRT=01" in row["attributes"]
    assert [r["resource_type"] for r in _rows("         DFHSIT TYPE=DSECT\n")] == ["SIT"]
    assert _rows("         DFHSIT TYPE=BOGUS\n") == []


@pytest.mark.parametrize(
    ("suffix", "expected"),
    [
        ("01", "DFHSIT01"),
        ("6$", "DFHSIT6$"),
        ("a", "DFHSITA"),  # one character is valid; the table name is upper case
        ("'xy'", "DFHSITXY"),
        ("NO", "DFHSIT"),  # "other than NO and DY" [TS dfha2_suffix]
        ("DY", "DFHSIT"),
        ("ABC", "DFHSIT"),  # more than two characters
        ("", "DFHSIT"),
    ],
)
def test_dfhsit_suffix_names_the_table(suffix, expected):
    (row,) = _rows(f"         DFHSIT TYPE=CSECT,SUFFIX={suffix},FCT=01,GRPLIST=(DFHLIST,MYLIST)\n")
    assert (row["name"], row["macro_table"]) == (expected, expected)
    assert "GRPLIST=(DFHLIST,MYLIST)" in row["attributes"]  # kept as text, never expanded to rows


def test_dfhsit_parameters_are_never_rows():
    src = "         DFHSIT TYPE=CSECT,SUFFIX=01,FCT=01,DCT=01,SRT=01,TST=01,GRPLIST=(A,B),PCT=01\n"
    assert [r["resource_type"] for r in _rows(src)] == ["SIT"]


def test_sequential_device_line_and_sdsci_name_no_resource():
    """DFHTCT sequential devices [TS tct/seq.html]: SDSCI is a DD, LINE joins two SDSCIs; TERMINAL is the row."""
    src = (
        "         DFHTCT TYPE=SDSCI,DSCNAME=ISADS,DDNAME=INDD\n"
        "         DFHTCT TYPE=SDSCI,DSCNAME=OSADS,DDNAME=OUTDD\n"
        "         DFHTCT TYPE=LINE,ACCMETH=BSAM,ISADSCN=ISADS,OSADSCN=OSADS\n"
        "         DFHTCT TYPE=TERMINAL,TRMIDNT=SEQ1,TRMTYPE=SEQ,ACCMETH=BSAM\n"
    )
    assert [(r["resource_type"], r["name"]) for r in _rows(src)] == [("TERMINAL", "SEQ1")]


def test_dfhmct_record_names_no_resource():
    """TYPE=RECORD selects performance-class fields [TS mct/record.html]; there is nothing to name."""
    src = "         DFHMCT TYPE=RECORD,CLASS=PERFORM,EXCLUDE=(DFHTASK,98),INCLUDE=(70)\n"
    assert _rows(src) == []


def test_dfhsit_column_72_continuation():
    (row,) = _rows(_cont("         DFHSIT TYPE=CSECT,FCT=01,", "SRT=02"))
    assert "FCT=01,SRT=02" in row["attributes"]


def test_dfhsit_label_line_lower_case_and_missing_type():
    """A `DFHSIT CSECT` label line is no macro; lower case reads; TYPE= missing or unknown names no table (#5154)."""
    src = "DFHSIT   CSECT\n         dfhsit type=csect,suffix=a,fct=01\n         END\n"
    assert [(r["resource_type"], r["name"]) for r in _rows(src)] == [("SIT", "DFHSITA")]
    assert _rows("         DFHSIT FCT=01\n") == []
    assert _rows("DFHSIT   CSECT\n") == []


@pytest.mark.parametrize(
    ("operands", "expected"),
    [("TYPE=CSECT,FCT=01", "DFHSIT"), ("TYPE=CSECT,SUFFIX=AB,FCT=01", "DFHSITAB"), ("TYPE=DSECT", "DFHSIT")],
)
def test_dfhsit_assembled_in_jcl_sysin_is_a_sit_row_on_the_job_line(operands, expected):
    job = f"//J JOB\n//ASM EXEC PGM=ASMA90\n//SYSIN DD *\n         DFHSIT {operands}\n/*\n"
    rows = extract_boundary("jcl", job)["csd_resources"]
    assert [(r["resource_type"], r["name"], r["source"], r["line"]) for r in rows] == [("SIT", expected, "MACRO", 4)]


@pytest.mark.parametrize(
    "step",
    [
        "//ASM EXEC PGM=ASMA90",
        "//ASM EXEC PGM=IEV90,PARM='OBJECT'",
        "//ASM EXEC PGM=IEUASM",
        "//ASM EXEC PGM=ASMAHL",
        "//ASM EXEC PGM=ASMBLR",
        "//ASM EXEC DFHAUPLE",
        "//ASM EXEC PROC=DFHAUPLE,TABLE=X",
    ],
)
def test_a_jcl_assembler_step_with_inline_sysin_yields_the_tables(step):
    job = f"//J JOB\n{step}\n//SYSIN DD *\n         DFHFCT TYPE=FILE,FILE=F1,DSNAME=A.B\n         DFHSRT TYPE=USER,ABCODE=9,RECOVER=YES\n/*\n"
    rows = extract_boundary("jcl", job)["csd_resources"]
    assert [(r["resource_type"], r["name"], r["source"], r["line"]) for r in rows] == [
        ("FILE", "F1", "MACRO", 4),
        ("SRT", "U9", "MACRO", 5),
    ]


@pytest.mark.parametrize(
    "step",
    ["//S EXEC PGM=IEFBR14", "//S EXEC PGM=SORT", "//S EXEC PGM=ASMA90X", "//* EXEC DFHAUPLE is a comment word"],
)
def test_a_job_without_an_assembler_step_reads_no_tables(step):
    job = f"//J JOB\n{step}\n//SYSIN DD *\n         DFHFCT TYPE=FILE,FILE=F1,DSNAME=A.B\n/*\n"
    assert extract_boundary("jcl", job)["csd_resources"] == []


def test_a_jcl_job_keeps_its_csd_resources_beside_assembled_tables():
    job = (
        "//J JOB\n//CSD EXEC PGM=DFHCSDUP\n//SYSIN DD *\n DEFINE FILE(CF) GROUP(G) DSNAME(A.B)\n/*\n"
        "//ASM EXEC PGM=ASMA90\n//SYSIN DD *\n         DFHJCT TYPE=ENTRY,JFILEID=SYSTEM\n/*\n"
    )
    rows = extract_boundary("jcl", job)["csd_resources"]
    assert {(r["resource_type"], r["name"], r.get("source", "CSD")) for r in rows} == {
        ("FILE", "CF", "CSD"),
        ("JOURNAL", "SYSTEM", "MACRO"),
    }


def test_a_jct_journal_and_a_csd_journalmodel_are_two_resource_types():
    """RDO JOURNALMODEL (SC33-1684-30 ch.16) is a different resource from a JCT `JFILEID` journal (SC33-1653-05 Table 41).

    Pinned: both are read, each under its own type, so the resource map never merges or conflicts them. A same-named
    JOURNALMODEL does not stand in for the JCT journal (IBM gives no mapping between them; left open, #5154).
    """
    job = (
        "//J JOB\n//CSD EXEC PGM=DFHCSDUP\n//SYSIN DD *\n"
        " DEFINE JOURNALMODEL(SYSTEM) GROUP(G) JOURNALNAME(DFHLOG) TYPE(MVS)\n/*\n"
        "//ASM EXEC PGM=ASMA90\n//SYSIN DD *\n         DFHJCT TYPE=ENTRY,JFILEID=SYSTEM\n/*\n"
    )
    rows = extract_boundary("jcl", job)["csd_resources"]
    assert sorted((r["resource_type"], r["name"], r.get("source")) for r in rows) == [
        ("JOURNAL", "SYSTEM", "MACRO"),
        ("JOURNALMODEL", "SYSTEM", None),
    ]


def test_the_new_tables_are_cpu_bounded():
    src = ("         DFHSRT TYPE=SYSTEM,ABCODE=(" + ",".join("0C1" for _ in range(2000)) + "),RECOVER=YES\n") * 50 + (
        "         DFHMCT TYPE=EMP,ID=" + "(" * 3000 + "\n"
    ) * 50
    start = time.process_time()
    _rows(src)
    assert time.process_time() - start < 5


def test_hlasm_alternative_statement_format_continuation_and_label_rules():
    """HLASM Language Reference (SC26-4940-05) ch.2 'Continuation lines' (p.15) and ch.8 'Alternative formats
    for a macro instruction' (p.296):
    1. In the alternative format, each continued line may carry remarks after its trailing comma; only the
       operand prefix before the remark space is joined into the macro's operands.
    2. If an operand on a continuation line begins after column 16 (column 16 is blank) outside a continued
       quoted string, HLASM treats that line and any following continuation lines as remarks.
    3. Long labels (up to 63 chars, with underscores) and sequence symbols (.SKIP) in the name field are accepted.
    4. Sequence numbers in columns 73-80 are ignored.
    """

    def _card(body: str, cont: str = " ", seq: int = 100) -> str:
        return body.ljust(71) + cont + f"{seq:08d}"

    src = "\n".join(
        [
            _card("         DFHFCT TYPE=INITIAL,SUFFIX=01", " ", 100),
            # Alternative format: remarks on each continued line, plus a trailing remark continuation starting at col 17
            _card("LONG_FILE_LABEL_01 DFHFCT TYPE=FILE,    DEFINE MASTER FILE", "X", 200),
            _card("               FILE=ACCTDAT,            FILE IDENTIFIER", "X", 300),
            _card("               DSNAME=BANK.ACCT.DAM,    VSAM DATASET NAME", "X", 400),
            _card("               RECFORM=(FIXED,BLOCKED), FIXED BLOCKED RECORDS", "X", 500),
            _card("               KEYLEN=11,LRECL=300      KEY AND RECORD LENGTH", "X", 600),
            _card("                DSNAME=FAKE.REMARK.DSN,LRECL=999", "X", 700),
            _card("               KEYLEN=99", " ", 800),
            # Sequence symbol in the name field + quoted operand containing a space
            _card(".PCT01   DFHPCT TYPE=ENTRY,TRANSID=BA01,DESC='INQUIRY TRAN',", "X", 900),
            _card("               PROGRAM=BANKINQ,TRNPRTY=100", " ", 1000),
            _card("         DFHFCT TYPE=FINAL", " ", 1100),
        ]
    )
    b = extract_boundary("hlasm", src)
    rows = {r["name"]: r for r in b["csd_resources"]}
    acct = rows["ACCTDAT"]
    assert (acct["dsname"], acct["record_format"], acct["key_length"], acct["record_size"], acct["line"]) == (
        "BANK.ACCT.DAM",
        "F",
        11,
        300,
        2,
    )
    ba01 = rows["BA01"]
    assert (ba01["program"], ba01["transid"], _rdo(ba01)) == ("BANKINQ", "BA01", "PRIORITY(100)")
    assert b["transactions"] == [
        {"transid": "BA01", "program": "BANKINQ", "group": "DFHPCT", "profile": None, "line": 9}
    ]


def test_dfhplt_programs_and_dfhdelim_stage_delimiter():
    """DFHPLT TYPE=ENTRY [SC33-1684-30 p.415-418]: PROGRAM=(p1,p2) defines one PLT row per program;
    PROGRAM=DFHDELIM 'is not a program -- it serves as a delimiter only' and flips STAGE(1) to STAGE(2)."""
    src = (
        "         DFHPLT TYPE=INITIAL,SUFFIX=I1\n"
        "         DFHPLT TYPE=ENTRY,PROGRAM=(TRAQA,TRAQB)\n"
        "         DFHPLT TYPE=ENTRY,PROGRAM=DFHDELIM\n"
        "         DFHPLT TYPE=ENTRY,PROGRAM=TRASA\n"
        "         DFHPLT TYPE=FINAL\n"
    )
    rows = _rows(src)
    assert [(r["resource_type"], r["name"], r["program"], r["macro_table"], r["line"], _rdo(r)) for r in rows] == [
        ("PLT", "TRAQA", "TRAQA", "DFHPLTI1", 2, "STAGE(1)"),
        ("PLT", "TRAQB", "TRAQB", "DFHPLTI1", 2, "STAGE(1)"),
        ("PLT", "TRASA", "TRASA", "DFHPLTI1", 4, "STAGE(2)"),
    ]


def test_dsncrct_db2conn_db2entry_plan_inheritance_and_group():
    """DSNCRCT [SC33-1684-30 p.419-432, p.529-541]:
    - TYPE=INIT emits DB2CONN (named RDONAME= or DFHRCT + SUFFIX, with SUFFIX=NO|DY|BA rejected) and sets PLANI/PLNPGMI.
    - TYPE=COMD and TYPE=POOL emit no standalone resource row.
    - TYPE=GROUP sets the group for following entries (`GROUP=*DEFAULT` resets to None).
    - TYPE=ENTRY emits one DB2ENTRY per TXID, inheriting PLANI when PLAN= is omitted (unless PLNEXIT=YES),
      or defaulting to the single TXID when neither PLAN= nor PLANI= is coded."""
    src = "\n".join(
        [
            _cont(
                "         DSNCRCT TYPE=INIT,SUFFIX=01,SUBID=DB2A,SIGNID=CICSAUTH,",
                "PLANI=DEFPLAN,PLNPGMI=DEFEXIT,THRDMAX=16",
            ),
            "         DSNCRCT TYPE=COMD,AUTH=USERID,THRDM=1,THRDA=1",
            "         DSNCRCT TYPE=POOL,PLAN=POOLPLN,THRDM=3,THRDA=3",
            "         DSNCRCT TYPE=GROUP,GROUP=DB2GRP1",
            _cont("         DSNCRCT TYPE=ENTRY,TXID=(TX01),PLAN=PLN01,RDONAME=ENT01,", "THRDA=4,THRDS=2,TWAIT=POOL"),
            "         DSNCRCT TYPE=ENTRY,TXID=(TX02,TX03),THRDA=2,TWAIT=YES",
            "         DSNCRCT TYPE=GROUP,GROUP=*DEFAULT",
            "         DSNCRCT TYPE=ENTRY,TXID=TX04,PLNEXIT=YES",
            "         DSNCRCT TYPE=FINAL",
        ]
    )
    rows = _rows(src)
    assert [
        (r["resource_type"], r["name"], r["macro_table"], r["group"], r["plan"], r["transid"], _rdo(r)) for r in rows
    ] == [
        (
            "DB2CONN",
            "DFHRCT01",
            "DFHRCT01",
            None,
            "DEFPLAN",
            None,
            "DB2ID(DB2A) SIGNID(CICSAUTH) PLANEXITNAME(DEFEXIT) TCBLIMIT(16)",
        ),
        (
            "DB2ENTRY",
            "ENT01",
            "DFHRCT01",
            "DB2GRP1",
            "PLN01",
            "TX01",
            "PLAN(PLN01) THREADLIMIT(4) PROTECTNUM(2) THREADWAIT(POOL) TRANSID(TX01)",
        ),
        (
            "DB2ENTRY",
            "TX02",
            "DFHRCT01",
            "DB2GRP1",
            "DEFPLAN",
            "TX02",
            "PLAN(DEFPLAN) THREADLIMIT(2) THREADWAIT(YES) TRANSID(TX02)",
        ),
        (
            "DB2ENTRY",
            "TX03",
            "DFHRCT01",
            "DB2GRP1",
            "DEFPLAN",
            "TX03",
            "PLAN(DEFPLAN) THREADLIMIT(2) THREADWAIT(YES) TRANSID(TX03)",
        ),
        (
            "DB2ENTRY",
            "TX04",
            "DFHRCT01",
            None,
            None,
            "TX04",
            "PLANEXITNAME(DEFEXIT) TRANSID(TX04)",
        ),
    ]
    # Without PLANI on TYPE=INIT, a single-TXID TYPE=ENTRY defaults its plan to TXID [SC33-1684-30 p.421, p.428];
    # SUFFIX=BA is disallowed on DSNCRCT [p.423].
    rows2 = _rows("         DSNCRCT TYPE=INIT,SUFFIX=BA,RDONAME=MYDB2C\n         DSNCRCT TYPE=ENTRY,TXID=TX99\n")
    assert [(r["resource_type"], r["name"], r["macro_table"], r["plan"]) for r in rows2] == [
        ("DB2CONN", "MYDB2C", "DFHRCT", None),
        ("DB2ENTRY", "TX99", "DFHRCT", "TX99"),
    ]


# --- DFHTCT shapes the IBM manuals leave open: pinned, ASSUMED by name (#5154) ----------------------


def _tct(*statements: str) -> str:
    return "".join(f"         DFHTCT {s}\n" for s in statements)


def _tct_rows(src: str) -> list[tuple[str, str, str]]:
    return [(r["resource_type"], r["name"], _rdo(r) if " => " in r["attributes"] else "") for r in _rows(src)]


@pytest.mark.parametrize(
    ("trmidnt", "expected"),
    [
        ("T1", "T1"),
        ("(T1)", "T1"),
        ("t1", "T1"),  # read as MVS reads a name: upper case
        (
            "ABCDEFG",
            "ABCDEFG",
        ),  # longer than the 4 characters of a TERMINAL id: kept, ASSUMED (no manual page read states a refusal)
    ],
)
def test_dfhtct_trmidnt_forms_name_the_terminal(trmidnt, expected):
    assert _named(_tct(f"TYPE=TERMINAL,TRMIDNT={trmidnt}"), "TERMINAL") == [expected]


def test_dfhtct_empty_trmidnt_names_no_terminal():
    assert _rows(_tct("TYPE=TERMINAL,TRMIDNT=", "TYPE=TERMINAL,ACCMETH=VTAM")) == []


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("TYPE=TERMINAL,TRMIDNT=T1", "TYPE=TERMINAL,TRMIDNT=T1"),
        ("TYPE=TERMINAL,TRMIDNT=T1", "TYPE=TERMINAL,TRMIDNT=t1"),
        ("TYPE=TERMINAL,TRMIDNT=T1", "TYPE=GPENTRY,TRMIDNT=T1"),
        ("TYPE=SYSTEM,SYSIDNT=SYSB", "TYPE=SYSTEM,SYSIDNT=SYSB"),
    ],
)
def test_dfhtct_a_repeated_name_is_not_folded(a, b):
    """IBM is silent on a repeated TRMIDNT / SYSIDNT: each statement is a row (ASSUMED), nothing is merged away."""
    assert len(_rows(_tct(a, b))) == 2


def test_dfhtct_type_remote_ignores_the_region_set_by_type_region():
    """A TYPE=REMOTE names its own SYSIDNT; the TYPE=REGION context applies to TYPE=TERMINAL only [RDG p.473-474]."""
    src = _tct(
        "TYPE=REGION,SYSIDNT=SYSC", "TYPE=REMOTE,TRMIDNT=R1", "TYPE=GPENTRY,TRMIDNT=G1", "TYPE=TERMINAL,TRMIDNT=T1"
    )
    assert _tct_rows(src) == [
        ("TERMINAL", "R1", ""),
        ("TERMINAL", "G1", ""),
        ("TERMINAL", "T1", "REMOTESYSTEM(SYSC)"),
    ]


def test_dfhtct_explicit_sysidnt_local_beats_the_region():
    src = _tct("TYPE=REGION,SYSIDNT=SYSC", "TYPE=TERMINAL,TRMIDNT=T1,SYSIDNT=LOCAL")
    assert _tct_rows(src) == [("TERMINAL", "T1", "")]


@pytest.mark.parametrize(
    ("accmeth", "expected"),
    [
        ("IRC", "ACCESSMETHOD(IRC)"),
        ("VTAM", "ACCESSMETHOD(VTAM)"),
        ("INDIRECT", "ACCESSMETHOD(INDIRECT)"),
        ("(IRC,XM)", "ACCESSMETHOD(XM)"),
        ("irc", "ACCESSMETHOD(IRC)"),
        ("BSAM", ""),  # not a connection access method [RDG p.529]: row kept, no restatement
        ("(IRC,VTAM)", ""),  # a pair the manual does not list
        (None, ""),
    ],
)
def test_dfhtct_system_accmeth_forms(accmeth, expected):
    ops = "TYPE=SYSTEM,SYSIDNT=SYSB" + (f",ACCMETH={accmeth}" if accmeth else "")
    assert _tct_rows(_tct(ops)) == [("CONNECTION", "SYSB", expected)]


@pytest.mark.parametrize("ops", ["TYPE=SYSTEM,ACCMETH=IRC", "TYPE=SYSTEM", "SYSIDNT=SYSB", "TYPE=BOGUS,TRMIDNT=T1"])
def test_dfhtct_unnamed_or_unlisted_shapes_are_refused(ops):
    assert _rows(_tct(ops)) == []


def test_dfhtct_whole_class_reads_the_same_in_a_jcl_sysin():
    src = _tct(
        "TYPE=INITIAL,SUFFIX=01,SYSIDNT=HOME",
        "TYPE=REGION,SYSIDNT=SYSC",
        "TYPE=TERMINAL,TRMIDNT=T1",
        "TYPE=GPENTRY,TRMIDNT=G1",
        "TYPE=SYSTEM,SYSIDNT=SYSB,ACCMETH=IRC",
        "TYPE=TERMINAL,TRMIDNT=T1",
    )
    job = "//J JOB\n//ASM EXEC PGM=ASMA90\n//SYSIN DD *\n" + src + "/*\n"
    in_jcl = extract_boundary("jcl", job)["csd_resources"]
    assert [(r["resource_type"], r["name"], r["macro_table"], _rdo(r)) for r in in_jcl] == [
        (r["resource_type"], r["name"], r["macro_table"], _rdo(r) if " => " in r["attributes"] else "")
        for r in _rows(src)
    ]
    assert len(in_jcl) == 4 and {r["macro_table"] for r in in_jcl} == {"DFHTCT01"}
