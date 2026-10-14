"""
#5120: CICS resource macro tables (DFHFCT / DFHPCT / DFHPPT / DFHDCT / DFHTST) as
`csd_resources` rows -- core/cics_macro_tables.py through `extract_boundary` as hlasm.

The syntax is IBM's documented macro syntax (CICS Resource Definition Guide, the
macro-table appendix: DFHFCT TYPE=DATASET, DFHPCT / DFHPPT TYPE=ENTRY, DFHDCT
TYPE=INTRA / EXTRA / INDIRECT / SDSCI, DFHTST TYPE=LOCAL ...). Every fixture is
hand-written: a labelled and an unlabelled statement, a column-72 continuation, a
comment, lower case, a quoted operand and a list-valued operand.
"""

import time
from pathlib import Path

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


def _cont(first: str, *more: str) -> str:
    """A statement continued at column 72; each following line resumes at column 16."""
    lines = [first, *[" " * 15 + m for m in more]]
    return "\n".join(ln.ljust(71) + "X" if i < len(lines) - 1 else ln for i, ln in enumerate(lines))


def test_dfhfct_dataset_is_a_file_with_its_join_attributes():
    src = "\n".join(
        [
            "         DFHFCT TYPE=INITIAL,SUFFIX=01",
            _cont(
                "ACCT     DFHFCT TYPE=DATASET,DATASET=ACCTDAT,ACCMETH=VSAM,",
                "DSNAME=BANK.ACCT.KSDS,RECFORM=(VARIABLE,BLOCKED),",
                "KEYLEN=11,RECSIZE=300",
            ),
            "         DFHFCT TYPE=FINAL",
        ]
    )
    assert _lifted(src) == [("FILE", "ACCTDAT", "BANK.ACCT.KSDS", None, "V", 11, 300, None, None, None)]
    row = _rows(src)[0]
    assert (row["source"], row["macro_table"], row["line"]) == ("MACRO", "DFHFCT01", 2)
    assert "KEYLEN=11" in row["attributes"]


def test_dfhfct_recform_and_remote_and_unstated_operands():
    src = "\n".join(
        [
            "         DFHFCT TYPE=DATASET,DATASET=A,RECFORM=FIXED,KEYLEN=nan",
            "         DFHFCT TYPE=DATASET,DATASET=B,RECFORM=UNDEFINED",
            "         DFHFCT TYPE=DATASET,DATASET=C,RECFORM=WEIRD",
            "         DFHFCT TYPE=REMOTE,DATASET=RMT,SYSIDNT=SYSB",
            "         DFHFCT TYPE=DATASET",  # no DATASET= -> no resource
        ]
    )
    assert [(r[1], r[4], r[5]) for r in _lifted(src)] == [
        ("A", "F", None),
        ("B", "U", None),
        ("C", None, None),
        ("RMT", None, None),
    ]


def test_dfhpct_entry_is_a_transaction_routing_to_its_program():
    src = "         DFHPCT TYPE=ENTRY,TRANSID=BA01,PROGRAM=BANKINQ,TWASIZE=64\n         DFHPCT TYPE=GROUP,FN=X\n"
    assert _lifted(src) == [("TRANSACTION", "BA01", None, None, None, None, None, None, "BANKINQ", "BA01")]


def test_dfhppt_entry_is_a_program():
    src = "         DFHPPT TYPE=ENTRY,PROGRAM=BANKINQ,PGMLANG=COBOL,RES=NO"
    assert _lifted(src) == [("PROGRAM", "BANKINQ", None, None, None, None, None, None, "BANKINQ", None)]
    assert "PGMLANG=COBOL" in _rows(src)[0]["attributes"]


def test_dfhdct_queue_types_and_the_sdsci_folded_into_its_extra_entry():
    src = "\n".join(
        [
            "         DFHDCT TYPE=EXTRA,DESTID=AUDT,DSCNAME=AUDITDD",  # the SDSCI follows its user
            _cont("         DFHDCT TYPE=SDSCI,DSCNAME=AUDITDD,RECFORM=VARIABLE,", "RECSIZE=132,DSNAME=BANK.AUDIT.LOG"),
            "         DFHDCT TYPE=INTRA,DESTID=CSSL",
            "         DFHDCT TYPE=INDIRECT,DESTID=ALIA,INDEST=CSSL",
            "         DFHDCT TYPE=REMOTE,DESTID=RMTQ,SYSIDNT=SYSB",
            "         DFHDCT TYPE=EXTRA,DESTID=NODSC",
        ]
    )
    assert _lifted(src) == [
        ("TDQUEUE", "AUDT", "BANK.AUDIT.LOG", "AUDITDD", "VARIABLE", None, 132, "EXTRA", None, None),
        ("TDQUEUE", "CSSL", None, None, None, None, None, "INTRA", None, None),
        ("TDQUEUE", "ALIA", None, None, None, None, None, "INDIRECT", None, None),
        ("TDQUEUE", "RMTQ", None, None, None, None, None, "REMOTE", None, None),
        ("TDQUEUE", "NODSC", None, None, None, None, None, "EXTRA", None, None),
    ]  # fmt: skip


def test_dfhtst_dataid_list_is_one_tsmodel_per_prefix():
    src = "         DFHTST TYPE=LOCAL,DATAID=(BANK,AUDT)\n         DFHTST TYPE=RECOVERY,DATAID=RCV\n"
    assert [(r["resource_type"], r["name"]) for r in _rows(src)] == [
        ("TSMODEL", "BANK"),
        ("TSMODEL", "AUDT"),
        ("TSMODEL", "RCV"),
    ]


def test_suffix_names_the_assembled_table_and_is_per_table():
    src = "         DFHPCT TYPE=INITIAL,SUFFIX=A1\n         DFHPCT TYPE=ENTRY,TRANSID=T1,PROGRAM=P1\n         DFHPPT TYPE=ENTRY,PROGRAM=P1\n"
    assert [r["macro_table"] for r in _rows(src)] == ["DFHPCTA1", "DFHPPT"]


def test_lower_case_comments_and_non_table_macros_are_handled():
    src = "\n".join(
        [
            "* DFHFCT TYPE=DATASET,DATASET=COMMENT",
            "         dfhfct type=dataset,dataset=lower,dsname=a.b",
            "         DFHSIT TYPE=CSECT,FCT=01",
            "         MVC   DFHFCT,=C'DFHFCT TYPE=DATASET,DATASET=NOT'",
        ]
    )
    assert [(r[1], r[2]) for r in _lifted(src)] == [("LOWER", "A.B")]


def test_text_with_no_table_macro_yields_nothing_and_never_raises():
    assert _rows("") == []
    assert _rows("         MVC A,B\n") == []
    assert _rows("         DFHFCT TYPE=DATASET,DATASET=(\n") == []  # an unbalanced list names nothing
    assert _rows("         DFHFCT\n         DFHDCT TYPE=\n         DFHTST TYPE=LOCAL,DATAID=\n") == []


def test_a_pathological_statement_is_cpu_bounded():
    src = (
        "         DFHFCT TYPE=DATASET,DATASET=A,"
        + "(" * 50000
        + "\n"
        + ("         DFHTST TYPE=LOCAL,DATAID=" + ",".join("P" * 3 for _ in range(2000)) + "\n") * 50
    )
    start = time.process_time()
    _rows(src)
    assert time.process_time() - start < 5


def test_the_fixture_estates_read_every_table():
    for estate in ("tables_only", "tables_and_csd"):
        rows = []
        for path in sorted((FIXTURES / estate).glob("*.asm")):
            rows += extract_boundary("hlasm", path.read_text())["csd_resources"]
        assert {r["resource_type"] for r in rows} >= {"FILE", "TRANSACTION", "TDQUEUE"}
        assert {r["source"] for r in rows} == {"MACRO"}
    types = {
        r["resource_type"]
        for p in (FIXTURES / "tables_only").glob("*.asm")
        for r in extract_boundary("hlasm", p.read_text())["csd_resources"]
    }
    assert types == {"FILE", "TRANSACTION", "PROGRAM", "TDQUEUE", "TSMODEL"}
