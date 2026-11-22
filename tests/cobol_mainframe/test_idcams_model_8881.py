"""IDCAMS DEFINE ALTERNATEINDEX / DEFINE PATH / BLDINDEX in the step model (det/idcams_model.py, #8881): the three
steps of a transaction-master AIX job (a nonunique key, a path over it, BLDINDEX), the path read in alternate-key
order with duplicates in base order, both base kinds, the condition codes, and what the model refuses by name."""

from __future__ import annotations

import pytest

from gitgalaxy.tools.cobol_to_java.det import idcams_model as M
from gitgalaxy.tools.cobol_to_java.det.dfsort import Refused

BASE = "APP.TRAN.KSDS"
AIX = "APP.TRAN.KSDS.AIX"
PATH = "APP.TRAN.KSDS.AIX.PATH"

# the three steps' SYSIN, shaped like the nightly's (commas inside parentheses, DATA / INDEX components, continuations)
STEP20 = f"""   DEFINE ALTERNATEINDEX (NAME({AIX})-
   RELATE({BASE})                    -
   KEYS(4 4)                         -
   NONUNIQUEKEY                      -
   UPGRADE                           -
   RECORDSIZE(40,40)                 -
   VOLUMES(VOL001)                   -
   CYLINDERS(5,1))                   -
   DATA (NAME({AIX}.DATA))           -
   INDEX (NAME({AIX}.INDEX))
"""
STEP25 = f"""  DEFINE PATH                                -
   (NAME({PATH})                             -
    PATHENTRY({AIX}))
"""
STEP30 = f"""   BLDINDEX                          -
   INDATASET({BASE})                 -
   OUTDATASET({AIX})
"""


def rec(pk: str, ak: str, tail: str = "..") -> bytes:
    return (pk + ak + tail).encode()  # 4-byte primary key, 4-byte alternate key, 2 more bytes


def ksds(*records: bytes) -> dict[str, M.Cluster | M.Aix | M.Path]:
    return {BASE: M.Cluster(BASE, True, 4, 0, 10, 10, sorted(records))}


def esds(*records: bytes) -> dict[str, M.Cluster | M.Aix | M.Path]:
    return {BASE: M.Cluster(BASE, False, 0, 0, 10, 10, list(records))}


def job(catalog, *steps):
    """The steps run one after the other against the catalog the one before left, as a job does."""
    results = []
    for sysin in steps:
        r = M.run(sysin, catalog)
        results.append(r)
        catalog = r.catalog
    return results


ROWS = [rec("0001", "BBBB"), rec("0002", "AAAA"), rec("0003", "BBBB"), rec("0004", "CCCC"), rec("0005", "AAAA")]


# -- the job -----------------------------------------------------------------------------------------------------
def test_the_three_steps_run_with_code_0_and_the_path_reads_in_alternate_key_order():
    s20, s25, s30 = job(ksds(*ROWS), STEP20, STEP25, STEP30)
    assert [s20.rc, s25.rc, s30.rc] == [0, 0, 0]
    aix, path = s30.catalog[AIX], s30.catalog[PATH]
    assert aix == M.Aix(AIX, BASE, 4, 4, 40, 40, unique=False, upgrade=True, built=True)
    assert path == M.Path(PATH, AIX)
    # alternate key order; the records of one key in the order the base holds them (primary key order)
    assert M.path_records(s30.catalog, PATH) == [ROWS[1], ROWS[4], ROWS[0], ROWS[2], ROWS[3]]


def test_an_esds_base_keeps_arrival_order_within_a_key():
    rows = [rec("0009", "BBBB"), rec("0001", "AAAA"), rec("0005", "BBBB"), rec("0003", "AAAA")]
    cat = job(esds(*rows), STEP20, STEP25, STEP30)[-1].catalog
    assert M.path_records(cat, PATH) == [rows[1], rows[3], rows[0], rows[2]]


def test_the_key_is_read_at_its_offset_and_compared_as_bytes():
    rows = [rec("0001", "b"), rec("0002", "B"), rec("0003", "a")]  # unequal lengths are not the point: bytes order
    rows = [r[:4] + (k + "zzz")[:4].encode() + r[8:] for r, k in zip(rows, ("b", "B", "a"), strict=True)]
    cat = job(ksds(*rows), STEP20, STEP25, STEP30)[-1].catalog
    assert [r[4:8][:1] for r in M.path_records(cat, PATH)] == [b"B", b"a", b"b"]


def test_repro_reads_through_the_path_and_the_caller_s_catalog_is_not_changed():
    cat = ksds(*ROWS)
    cat2 = job(cat, STEP20, STEP25, STEP30)[-1].catalog
    r = M.run(f" REPRO INDATASET({PATH}) OUTFILE(OUT)\n", cat2, {"OUT": M.Sequential(10, [rec("old!", "xxxx")])})
    assert r.rc == 0 and r.datasets["OUT"].records == M.path_records(cat2, PATH)
    assert BASE in cat and AIX not in cat  # the first step ran on a copy


def test_a_dd_naming_the_path_reads_the_same_way():
    cat2 = job(ksds(*ROWS), STEP20, STEP25, STEP30)[-1].catalog
    r = M.run(" REPRO INFILE(IN) OUTFILE(OUT)\n", cat2, {"IN": M.Vsam(PATH), "OUT": M.Sequential(10)})
    assert r.datasets["OUT"].records == M.path_records(cat2, PATH)


def test_a_unique_key_alternate_index_over_distinct_keys_builds():
    rows = [rec("0001", "CCCC"), rec("0002", "AAAA"), rec("0003", "BBBB")]
    cat = job(ksds(*rows), STEP20.replace("NONUNIQUEKEY", "UNIQUEKEY"), STEP25, STEP30)[-1].catalog
    assert cat[AIX].unique is True
    assert M.path_records(cat, PATH) == [rows[1], rows[2], rows[0]]


def test_the_defaults_are_a_nonunique_upgrade_alternate_index_and_an_update_path():
    deck = f" DEFINE AIX (NAME({AIX}) RELATE({BASE}) -\n KEYS(4 4) RECORDSIZE(40 40))\n"
    cat = job(ksds(*ROWS), deck, f" DEFINE PATH (NAME({PATH}) -\n PATHENTRY({AIX}) NOUPDATE)\n")[-1].catalog
    assert (cat[AIX].unique, cat[AIX].upgrade, cat[PATH].update) == (False, True, False)


def test_a_comma_separates_operands_like_a_blank_and_data_index_names_work_on_a_cluster():
    deck = f""" DEFINE CLUSTER (NAME({BASE}) KEYS(4,0) RECORDSIZE(10,10) -
    ERASE INDEXED CYLINDERS(1,5) -
    VOLUMES(VOL001 -
    )) DATA (NAME({BASE}.DATA)) -
    INDEX (NAME({BASE}.INDEX))
"""
    r = M.run(deck, {})
    assert r.rc == 0 and r.catalog[BASE] == M.Cluster(BASE, True, 4, 0, 10, 10)


# -- condition codes -------------------------------------------------------------------------------------------
def test_a_duplicate_name_is_code_12_and_changes_nothing():
    cat = job(ksds(*ROWS), STEP20)[-1].catalog
    for deck, name in ((STEP20, AIX), (STEP25, PATH)):
        if name == PATH:
            cat = job(cat, STEP25)[-1].catalog
        r = M.run(deck, cat)
        assert (r.rc, r.lastcc) == (12, 12) and r.catalog == cat


def test_the_codes_feed_if_and_set_maxcc():
    cat = job(ksds(*ROWS), STEP20)[-1].catalog
    r = M.run(STEP20 + " IF LASTCC = 12 THEN SET MAXCC = 0\n", cat)
    assert (r.lastcc, r.maxcc, r.rc) == (12, 0, 0)


# -- refusals, by name -----------------------------------------------------------------------------------------
def built() -> dict[str, M.Cluster | M.Aix | M.Path]:
    return job(ksds(*ROWS), STEP20, STEP25, STEP30)[-1].catalog


def defined() -> dict[str, M.Cluster | M.Aix | M.Path]:
    return job(ksds(*ROWS), STEP20, STEP25)[-1].catalog


def aix_deck(extra: str = "", keys: str = "KEYS(4 4)", relate: str = BASE) -> str:
    return f" DEFINE ALTERNATEINDEX (NAME(A.NEW) RELATE({relate}) -\n {keys} RECORDSIZE(40 40) {extra})\n"


@pytest.mark.parametrize(
    ("deck", "cat", "why"),
    [
        (aix_deck("NOUPGRADE"), "base", "NOUPGRADE"),
        (aix_deck("UNIQUEKEY NONUNIQUEKEY"), "base", "key uniqueness stated twice"),
        (aix_deck("REUSE"), "base", "ALTERNATEINDEX REUSE parameter"),
        (aix_deck(keys=""), "base", "without KEYS"),
        (aix_deck(keys="KEYS(8 4)"), "base", "not inside the base's shortest record"),
        (aix_deck(relate="APP.GONE"), "base", "is not in the catalog"),
        (aix_deck(relate=PATH), "defined", "is not a cluster"),
        (" DEFINE ALTERNATEINDEX (NAME(APP.NEW.AIX) KEYS(4 4) RECORDSIZE(40 40))\n", "base", "without a single RELATE"),
        (f" DEFINE ALTERNATEINDEX (NAME(APP.NEW.AIX) -\n RELATE({BASE}) KEYS(4 4))\n", "base", "without RECORDSIZE"),
        (aix_deck() + "", "base", None),  # control: the same deck is accepted
        (aix_deck().rstrip() + " DATA(NAME(A.D) KEYS(1 0))\n", "base", "DATA component operand"),
        (aix_deck().rstrip() + " DATA(NAME(A.D)) DATA(NAME(A.E))\n", "base", "DATA component stated twice"),
        (aix_deck().rstrip() + f" INDEX(NAME({BASE}))\n", "base", "component name is already an entry"),
        (" DEFINE PATH (NAME(A.P) PATHENTRY(NOPE.AIX))\n", "base", "is not in the catalog"),
        (f" DEFINE PATH (NAME(A.P) PATHENTRY({BASE}))\n", "base", "is not an alternate index"),
        (f" DEFINE PATH (NAME(A.P) PATHENTRY({PATH}))\n", "defined", "is not an alternate index"),
        (f" DEFINE PATH (NAME(A.P) PATHENTRY({AIX}) CYLINDERS(1 1))\n", "defined", "PATH CYLINDERS parameter"),
        (" DEFINE PATH (PATHENTRY(A))\n", "base", "without a single NAME"),
        (" DEFINE PATH (NAME(A.P))\n", "defined", "without a single PATHENTRY"),
        (f" DEFINE PATH (NAME(A.P) PATHENTRY({AIX})) DATA(NAME(A.D))\n", "defined", "outside PATH"),
        (" BLDINDEX INFILE(IN) OUTFILE(OUT)\n", "defined", "INFILE"),
        (f" BLDINDEX INDATASET({BASE})\n", "defined", "both INDATASET and OUTDATASET"),
        (f" BLDINDEX INDATASET({BASE}) OUTDATASET({AIX}) EXTERNALSORT\n", "defined", "BLDINDEX EXTERNA parameter"),
        (f" BLDINDEX IDS({BASE}) -\n INDATASET({BASE}) ODS({AIX})\n", "defined", "names its INDATASET twice"),
        (f" BLDINDEX INDATASET({BASE}/PW) OUTDATASET({AIX})\n", "defined", "plain data set name"),
        (f" BLDINDEX INDATASET(APP.GONE) OUTDATASET({AIX})\n", "defined", "not a cluster in the catalog"),
        (f" BLDINDEX INDATASET({BASE}) OUTDATASET({PATH})\n", "defined", "not an alternate index"),
        (f" BLDINDEX INDATASET({BASE}) OUTDATASET({AIX})\n", "built", "already built"),
        (f" REPRO INFILE(IN) OUTDATASET({PATH})\n", "built", "writes through a path"),
        (f" REPRO INFILE(IN) OUTDATASET({AIX})\n", "built", "is an alternate index"),
        (f" REPRO INFILE(IN) OUTDATASET({BASE})\n", "built", "base cluster with an alternate index"),
        (f" REPRO INDATASET({PATH}) OUTFILE(OUT)\n", "defined", "BLDINDEX has not built"),
        (f" DELETE {AIX}\n", "built", "alternate index or path"),
        (f" DELETE {PATH}\n", "built", "alternate index or path"),
        (f" DELETE {BASE}\n", "built", "alternate index related to it"),
    ],
)
def test_what_the_model_does_not_cover_is_refused_by_name(deck, cat, why):
    catalog = {"base": ksds(*ROWS), "defined": defined(), "built": built()}[cat]
    dds = {"IN": M.Sequential(10, [rec("0099", "ZZZZ")]), "OUT": M.Sequential(10)}
    if why is None:
        assert M.run(deck, catalog, dds).rc == 0
        return
    with pytest.raises(Refused, match=why):
        M.run(deck, catalog, dds)


def test_bldindex_of_an_empty_base_is_refused():
    with pytest.raises(Refused, match="empty base cluster"):
        job(ksds(), STEP20, STEP30)


def test_a_unique_key_alternate_index_over_duplicate_keys_is_refused():
    with pytest.raises(Refused, match="UNIQUEKEY alternate index over duplicate keys"):
        job(ksds(*ROWS), STEP20.replace("NONUNIQUEKEY", "UNIQUEKEY"), STEP30)


@pytest.mark.parametrize(("maxsize", "ok"), [(5 + 4 + 4 * 2, True), (5 + 4 + 4 * 2 - 1, False)])
def test_the_record_of_the_busiest_key_must_fit_recordsize(maxsize, ok):
    """A KSDS base's pointers are its 4-byte primary keys: two records per key need header 5 + key 4 + 2 x 4."""
    deck = STEP20.replace("RECORDSIZE(40,40)", f"RECORDSIZE({maxsize},{maxsize})")
    if ok:
        assert job(ksds(*ROWS), deck, STEP30)[-1].rc == 0
    else:
        with pytest.raises(Refused, match="over RECORDSIZE maximum"):
            job(ksds(*ROWS), deck, STEP30)


def test_an_esds_base_s_pointers_are_4_byte_rbas():
    rows = [rec("0009", "AAAA"), rec("0001", "AAAA")]
    cat = {BASE: M.Cluster(BASE, False, 0, 0, 10, 10, rows)}
    need = 5 + 4 + 4 * 2
    assert job(cat, STEP20.replace("RECORDSIZE(40,40)", f"RECORDSIZE({need},{need})"), STEP30)[-1].rc == 0
    with pytest.raises(Refused, match="over RECORDSIZE maximum"):
        job(cat, STEP20.replace("RECORDSIZE(40,40)", f"RECORDSIZE({need - 1},{need - 1})"), STEP30)


def test_path_records_refuses_what_is_not_a_path():
    with pytest.raises(Refused, match="not a path"):
        M.path_records(built(), BASE)
