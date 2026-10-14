"""
#5120: CICS resource macro tables (DFHFCT / DFHPCT / DFHPPT / DFHDCT / DFHTST) as
`csd_resources` rows -- core/cics_macro_tables.py through `extract_boundary` as hlasm.

The syntax is read from IBM's macro reference, cited in the module header:
"CICS Resource Definition Guide", CICS TS for OS/390 Release 3, SC33-1684-30,
ch.13 (DFHFCT TYPE=FILE|REMOTE, DFHDCT TYPE=SDSCI|EXTRA|INDIRECT|INTRA|REMOTE,
DFHTST TYPE=LOCAL|RECOVERY|REMOTE|SECURITY) and ch.16 (macro -> RDO attribute
table); CICS for MVS/ESA Migration Guide V4R1 GC33-1162-04 (DFHPCT / DFHPPT); IBM
APAR II05097 (`DFHPPT TYPE=ENTRY,MAPSET=`). Operands those sources leave open
(DFHPCT's operand list, the PPT PARTITIONSET= spelling, DCT RECFORM=UNDEFINED) are
ASSUMED in the module and pinned here as such. Every fixture is hand-written, with a
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


# --- DFHPCT / DFHPPT --------------------------------------------------------------------------


def test_dfhpct_entry_is_a_transaction_routing_to_its_program():
    src = "         DFHPCT TYPE=ENTRY,TRANSID=BA01,PROGRAM=BANKINQ,TWASIZE=64\n         DFHPCT TYPE=GROUP,FN=X\n"
    assert _lifted(src) == [("TRANSACTION", "BA01", None, None, None, None, None, None, "BANKINQ", "BA01")]


def test_dfhppt_entry_names_a_program_a_mapset_or_a_partition_set():
    src = "\n".join(
        [
            "         DFHPPT TYPE=ENTRY,PROGRAM=BANKINQ,PGMLANG=COBOL,RES=NO",
            "         DFHPPT TYPE=ENTRY,MAPSET=DSTMAPSM",  # IBM APAR II05097
            "         DFHPPT TYPE=ENTRY,PARTITIONSET=BANKPS",
            "         DFHPPT TYPE=ENTRY,PARTSET=OLDPS",
            "         DFHPPT TYPE=ENTRY",
            "         DFHPPT TYPE=FINAL",
        ]
    )
    assert [(r["resource_type"], r["name"], r["program"]) for r in _rows(src)] == [
        ("PROGRAM", "BANKINQ", "BANKINQ"),
        ("MAPSET", "DSTMAPSM", None),
        ("PARTITIONSET", "BANKPS", None),
        ("PARTITIONSET", "OLDPS", None),
    ]
    assert "PGMLANG=COBOL" in _rows(src)[0]["attributes"]


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
    assert "RMTNAME=O1" in _rows(src)[1]["attributes"]


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
            "         DFHSIT TYPE=CSECT,FCT=01",
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
    assert types == {"FILE", "TRANSACTION", "PROGRAM", "MAPSET", "PARTITIONSET", "TDQUEUE", "TSMODEL"}
