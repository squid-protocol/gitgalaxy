"""The IDCAMS step model (det/idcams_model.py, #8880): authored decks run against a catalog and a step's datasets --
REPRO both directions, DELETE of a missing cluster with and without SET MAXCC = 0, DEFINE then REPRO, IF on the
condition codes -- and every command or keyword the model does not cover refused by name."""

from __future__ import annotations

import pytest

from gitgalaxy.tools.cobol_to_java.det import idcams_model as M
from gitgalaxy.tools.cobol_to_java.det.dfsort import Refused

DEFINE = """ DEFINE CLUSTER (NAME(APP.TRAN.VSAM) -
        INDEXED -
        KEYS(4 0) -
        RECORDSIZE(8 8) -
        CYLINDERS(1 1) -
        VOLUMES(VOL001))
"""


def rec(key: str, tail: str = "xxxx") -> bytes:
    return (key + tail).encode()


def ksds(*records: bytes) -> M.Cluster:
    return M.Cluster("APP.TRAN.VSAM", True, 4, 0, 8, 8, list(records))


# -- REPRO, both directions -----------------------------------------------------------------------------------------
def test_repro_a_ksds_to_a_sequential_dataset_in_key_order():
    cat = {"APP.TRAN.VSAM": ksds(rec("0001"), rec("0002"), rec("0009"))}
    dds = {"IN": M.Vsam("APP.TRAN.VSAM"), "OUT": M.Sequential(8, [rec("old!")])}
    r = M.run(" REPRO INFILE(IN) OUTFILE(OUT)\n", cat, dds)
    assert r.rc == 0
    assert r.datasets["OUT"].records == [rec("0001"), rec("0002"), rec("0009")]  # rewritten from the start
    assert dds["OUT"].records == [rec("old!")]  # the caller's datasets are not changed


def test_repro_a_sequential_dataset_into_an_empty_ksds_loads_it_in_key_order():
    cat = {"APP.TRAN.VSAM": ksds()}
    seq = M.Sequential(8, [rec("0003"), rec("0005"), rec("0007")])
    r = M.run(" REPRO INFILE(IN) OUTDATASET(APP.TRAN.VSAM)\n", cat, {"IN": seq})
    assert r.rc == 0 and r.catalog["APP.TRAN.VSAM"].records == seq.records
    assert cat["APP.TRAN.VSAM"].records == []


def test_the_key_is_read_at_its_offset_and_compared_as_bytes():
    cat = {"K": M.Cluster("K", True, 2, 3, 6, 6)}  # key = bytes 4-5
    r = M.run(" REPRO INFILE(IN) OUTDATASET(K)\n", cat, {"IN": M.Sequential(6, [b"zzzAB!", b"yyyAC!", b"xxxBA!"])})
    assert [x[3:5] for x in r.catalog["K"].records] == [b"AB", b"AC", b"BA"]


@pytest.mark.parametrize(
    ("records", "why"),
    [
        ([rec("0002"), rec("0001")], "out of key order"),
        ([rec("0001"), rec("0001", "yyyy")], "duplicate key"),
    ],
)
def test_a_load_out_of_key_order_or_with_a_duplicate_is_refused(records, why):
    with pytest.raises(Refused, match="out of key order or with a duplicate"):
        M.run(
            " REPRO INFILE(IN) OUTDATASET(APP.TRAN.VSAM)\n", {"APP.TRAN.VSAM": ksds()}, {"IN": M.Sequential(8, records)}
        )


def test_repro_an_esds_reads_in_arrival_order_and_appends():
    cat = {"E": M.Cluster("E", False, 0, 0, 8, 8, [rec("0009"), rec("0001")])}
    r = M.run(" REPRO INFILE(IN) OUTFILE(OUT)\n REPRO INFILE(MORE) OUTDATASET(E)\n", cat,
              {"IN": M.Vsam("E"), "OUT": M.Sequential(8), "MORE": M.Sequential(8, [rec("0005")])})  # fmt: skip
    assert r.datasets["OUT"].records == [rec("0009"), rec("0001")]
    assert r.catalog["E"].records == [rec("0009"), rec("0001"), rec("0005")]


def test_repro_a_ksds_into_an_empty_ksds_and_a_sequential_into_a_sequential():
    cat = {"A": M.Cluster("A", True, 4, 0, 8, 8, [rec("0001"), rec("0002")]), "B": M.Cluster("B", True, 4, 0, 8, 8)}
    r = M.run(" REPRO INDATASET(A) OUTDATASET(B)\n REPRO IFILE(S) OFILE(T)\n", cat,
              {"S": M.Sequential(8, [rec("zzzz")]), "T": M.Sequential(8)})  # fmt: skip
    assert r.catalog["B"].records == r.catalog["A"].records and r.datasets["T"].records == [rec("zzzz")]


def test_repro_continuation_and_comments_read_like_det_idcams():
    r = M.run("/* back it up */\n REPRO -\n   INFILE(IN) -\n   OUTFILE(OUT) /* done */\n", {},
              {"IN": M.Sequential(2, [b"ab"]), "OUT": M.Sequential(2)})  # fmt: skip
    assert r.datasets["OUT"].records == [b"ab"]


# -- DELETE and the condition codes ---------------------------------------------------------------------------------
def test_delete_of_a_missing_cluster_is_condition_code_8():
    r = M.run(" DELETE APP.NOT.THERE CLUSTER\n", {})
    assert (r.rc, r.lastcc, r.maxcc) == (8, 8, 8)


def test_delete_of_a_missing_cluster_with_set_maxcc_0_ends_with_return_code_0():
    r = M.run(" DELETE APP.NOT.THERE CLUSTER PURGE\n SET MAXCC = 0\n", {})
    assert (r.rc, r.lastcc, r.maxcc) == (0, 8, 0)  # LASTCC is the DELETE's, MAXCC what SET made it


def test_delete_removes_an_existing_cluster_and_its_records():
    cat = {"APP.TRAN.VSAM": ksds(rec("0001"))}
    r = M.run(" DELETE APP.TRAN.VSAM\n", cat)
    assert r.rc == 0 and r.catalog == {} and "APP.TRAN.VSAM" in cat


def test_the_if_lastcc_idiom_clears_only_a_not_found():
    for cat, rc in (({}, 0), ({"X.Y": M.Cluster("X.Y", False, 0, 0, 4, 4)}, 0)):
        r = M.run(" DELETE X.Y CLUSTER\n IF LASTCC = 8 THEN -\n   SET MAXCC = 0\n", cat)
        assert r.rc == rc
    # a duplicate DEFINE (12) is not cleared by a test for 8
    r = M.run(DEFINE + DEFINE + " IF LASTCC = 8 THEN SET MAXCC = 0\n", {})
    assert (r.rc, r.lastcc) == (12, 12)


def test_if_then_do_end_else_runs_the_branch_the_code_selects():
    deck = " DELETE A.B\n IF MAXCC GT 4 THEN DO\n   DEFINE CLUSTER(NAME(HIT) NONINDEXED RECORDSIZE(4 4))\n END\n ELSE DO\n" \
           "   DEFINE CLUSTER(NAME(MISS) NONINDEXED RECORDSIZE(4 4))\n END\n"  # fmt: skip
    assert set(M.run(deck, {}).catalog) == {"HIT"}
    assert set(M.run(deck, {"A.B": M.Cluster("A.B", False, 0, 0, 4, 4)}).catalog) == {"MISS"}


@pytest.mark.parametrize(("op", "num", "taken"), [("=", 8, True), ("EQ", 4, False), ("NE", 4, True), ("^=", 8, False),
                                                  (">", 7, True), ("GT", 8, False), (">=", 8, True), ("<", 9, True),
                                                  ("LT", 8, False), ("<=", 8, True), ("LE", 7, False)])  # fmt: skip
def test_every_comparison_operator(op, num, taken):
    r = M.run(f" DELETE NONE\n IF LASTCC {op} {num} THEN SET MAXCC = 1\n", {})
    assert r.rc == (1 if taken else 8)


def test_set_maxcc_does_not_hide_a_later_failure():
    r = M.run(" SET MAXCC = 0\n DELETE NONE\n", {})
    assert r.rc == 8


# -- DEFINE then REPRO ----------------------------------------------------------------------------------------------
def test_define_then_repro_loads_the_new_cluster():
    deck = " DELETE APP.TRAN.VSAM CLUSTER\n SET MAXCC = 0\n" + DEFINE + " REPRO INFILE(IN) OUTDATASET(APP.TRAN.VSAM)\n"
    r = M.run(deck, {}, {"IN": M.Sequential(8, [rec("0001"), rec("0002")])})
    assert (r.rc, r.lastcc) == (0, 0)
    c = r.catalog["APP.TRAN.VSAM"]
    assert (c.indexed, c.key_len, c.key_off, c.avg, c.max) == (True, 4, 0, 8, 8) and len(c.records) == 2


def test_define_replaces_nothing_a_duplicate_name_is_condition_code_12():
    cat = {"APP.TRAN.VSAM": ksds(rec("0001"))}
    r = M.run(DEFINE, cat)
    assert r.rc == 12 and r.catalog["APP.TRAN.VSAM"].records == [rec("0001")]


def test_define_a_nonindexed_cluster_is_an_esds_and_indexed_is_the_default():
    r = M.run(" DEFINE CLUSTER(NAME(E) NONINDEXED RECORDSIZE(80 80) TRACKS(1))\n"
              " DEFINE CLUSTER(NAME(K) KEYS(8 2) RECORDSIZE(80 80))\n", {})  # fmt: skip
    assert (
        not r.catalog["E"].indexed
        and r.catalog["K"].indexed
        and (r.catalog["K"].key_off, r.catalog["K"].key_len) == (2, 8)
    )


def test_delete_then_define_then_the_dd_of_the_old_cluster_is_stale():
    cat = {"APP.TRAN.VSAM": ksds(rec("0001"))}
    with pytest.raises(Refused, match="deleted in the step"):
        M.run(" DELETE APP.TRAN.VSAM\n" + DEFINE + " REPRO INFILE(IN) OUTFILE(OUT)\n", cat,
              {"IN": M.Vsam("APP.TRAN.VSAM"), "OUT": M.Sequential(8)})  # fmt: skip


# -- refusals, by name ----------------------------------------------------------------------------------------------
SEQ8 = {"IN": M.Sequential(8, [rec("0001")]), "OUT": M.Sequential(8)}
CAT = {"APP.TRAN.VSAM": ksds(rec("0001")), "V": M.Cluster("V", True, 4, 0, 4, 12, [b"abcd"])}


@pytest.mark.parametrize(
    ("deck", "why"),
    [
        ("", "no IDCAMS command"),
        (" LISTCAT ENTRIES(A.B)\n", "the IDCAMS LISTCAT command"),
        (" PRINT INFILE(IN)\n", "the IDCAMS PRINT command"),
        (" ALTER A.B NEWNAME(C.D)\n", "the IDCAMS ALTER command"),
        (" SET LASTCC = 0\n", "only SET MAXCC is modelled"),
        (" SET MAXCC = 17\n", "the model covers 0 to 16"),
        (" SET MAXCC = 0 ELSE\n", "SET"),
        (" END\n", "END with no IF"),
        (" IF LASTCC = 8 THEN DO\n SET MAXCC = 0\n", "DO with no END"),
        (" IF LASTCC = 8\n", "IF with no THEN"),
        (" IF LASTCC = 8 THEN\n", "no command after"),
        (" IF RC = 8 THEN SET MAXCC = 0\n", "IF condition"),
        (" DELETE A.B GDG\n", "DELETE GDG parameter"),
        (" DELETE A.B NONVSAM\n", "DELETE NONVSAM parameter"),
        (" DELETE A.B/PW\n", "no password"),
        (" DELETE CLUSTER\n", "without one entry name"),
        (" DELETE (A.B C.D)\n", "with no keyword before it"),
        (" DELETE 'A.B'\n", "quoted string"),
        (" DEFINE ALIAS(NAME(A) RELATE(B))\n", "DEFINE ALIAS"),
        (" DEFINE GDG(NAME(A) LIMIT(3))\n", "DEFINE GDG"),
        (" DEFINE CLUSTER(NAME(A) KEYS(4 0) RECORDSIZE(8 8)) DATA(NAME(A.D))\n", "outside CLUSTER"),
        (" DEFINE CLUSTER(NAME(A) NUMBERED RECORDSIZE(8 8))\n", "NUMBERED parameter"),
        (" DEFINE CLUSTER(NAME(A) LINEAR)\n", "LINEAR parameter"),
        (" DEFINE CLUSTER(NAME(A) KEYS(4 0) REUSE RECORDSIZE(8 8))\n", "REUSE parameter"),
        (" DEFINE CLUSTER(NAME(A) KEYS(4 0) SPANNED RECORDSIZE(8 8))\n", "SPANNED parameter"),
        (" DEFINE CLUSTER(NAME(A) KEYS(4 0) INDEXED NONINDEXED RECORDSIZE(8 8))\n", "organisation stated twice"),
        (" DEFINE CLUSTER(KEYS(4 0) RECORDSIZE(8 8))\n", "without a single NAME"),
        (" DEFINE CLUSTER(NAME(A) KEYS(4 0))\n", "without RECORDSIZE"),
        (" DEFINE CLUSTER(NAME(A) RECORDSIZE(8 8))\n", "INDEXED without KEYS"),
        (" DEFINE CLUSTER(NAME(A) KEYS(6 4) RECORDSIZE(8 8))\n", "not inside the shortest record"),
        (" DEFINE CLUSTER(NAME(A) KEYS(4 0) RECORDSIZE(9 8))\n", "average <= maximum"),
        (" DEFINE CLUSTER(NAME(A) NONINDEXED KEYS(4 0) RECORDSIZE(8 8))\n", "NONINDEXED with KEYS"),
        (" DEFINE CLUSTER(NAME(A.1) KEYS(4 0) RECORDSIZE(8 8))\n", "plain data set name"),
        (" REPRO INFILE(IN) OUTFILE(OUT) FROMKEY(1)\n", "REPRO FROMKEY parameter"),
        (" REPRO INFILE(IN) OUTFILE(OUT) SKIP(1)\n", "REPRO SKIP parameter"),
        (" REPRO INFILE(IN) OUTFILE(OUT) COUNT(1)\n", "REPRO COUNT parameter"),
        (" REPRO INFILE(IN) OUTFILE(OUT) REPLACE\n", "REPRO REPLACE parameter"),
        (" REPRO INFILE(IN) OUTFILE(OUT) REUSE\n", "REPRO REUSE parameter"),
        (" REPRO INFILE(IN)\n", "both an input and an output"),
        (" REPRO INFILE(IN) INFILE(IN) OUTFILE(OUT)\n", "names its input twice"),
        (" REPRO INFILE(IN/PW) OUTFILE(OUT)\n", "no password"),
        (" REPRO INFILE(NOPE) OUTFILE(OUT)\n", "not a dataset of the step"),
        (" REPRO INFILE(IN) OUTDATASET(NOPE.NOPE)\n", "not a cluster in the catalog"),
        (" REPRO INFILE(IN) OUTFILE(IN)\n", "onto itself"),
        (" REPRO INDATASET(V) OUTFILE(OUT)\n", "variable-length records"),
        (" REPRO INFILE(IN) OUTDATASET(APP.TRAN.VSAM)\n", "non-empty KSDS"),
        (" REPRO INFILE(SHORT) OUTFILE(OUT)\n", "between record lengths 4 and 8"),
        (" REPRO INFILE(EMPTY) OUTFILE(OUT)\n", "zero records"),
        (" REPRO INFILE(IN) OUTFILE(MOD)\n", "DISP=MOD"),
    ],
)
def test_what_the_model_does_not_cover_is_refused_by_name(deck, why):
    dds = {**SEQ8, "SHORT": M.Sequential(4, [b"abcd"]), "EMPTY": M.Sequential(8), "MOD": M.Sequential(8, [], "MOD")}
    with pytest.raises(Refused, match=why):
        M.run(deck, CAT, dds)


def test_a_dd_naming_a_cluster_that_is_not_cataloged_is_refused():
    with pytest.raises(Refused, match="not in the catalog"):
        M.run(" REPRO INFILE(IN) OUTFILE(OUT)\n", {}, {"IN": M.Vsam("GONE"), "OUT": M.Sequential(8)})


def test_a_sequential_record_of_the_wrong_length_is_a_caller_bug_not_a_refusal():
    with pytest.raises(ValueError, match="not 8 bytes"):
        M.run(" DELETE A\n", {}, {"IN": M.Sequential(8, [b"short"])})
