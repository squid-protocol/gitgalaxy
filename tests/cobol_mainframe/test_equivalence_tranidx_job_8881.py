"""#8881: the committed job case `tests/equivalence/jobs/carddemo-job-posttran-tranidx.json` (CardDemo POSTTRAN STEP15, then
TRANIDX: DEFINE ALTERNATEINDEX KEYS(26 304) NONUNIQUEKEY, DEFINE PATH, BLDINDEX; SC23-6846-60). Pins the wiring against the
real POSTTRAN case without Docker, and runs the IDCAMS step on TRANFILE-shaped input: the path's records in alternate-key
order (duplicates in the base's primary-key order) and the condition code. The Java comparison runs when a JDK is found
(and is None, never proven, without one)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/tools"))

import equivalence as eq  # noqa: E402
import equivalence_job as ej  # noqa: E402

NAME = "carddemo-job-posttran-tranidx"
PATH = "AWS.M2.CARDDEMO.TRANSACT.VSAM.AIX.PATH"


def _tran(pk: str, ts: str) -> bytes:
    """A 350-byte TRANSACT record: the 16-byte key at 0, the 26-byte processed timestamp at 304."""
    buf = bytearray(b"." * 350)
    buf[0:16] = pk.ljust(16).encode()
    buf[304:330] = ts.ljust(26).encode()
    return bytes(buf)


def _step():
    return json.loads((eq.CASES / "jobs" / f"{NAME}.json").read_text(encoding="utf-8"))["steps"][1]


def _run(rows, step=None, deck=None, monkeypatch=None):
    step = step or _step()
    if deck is not None:
        monkeypatch.setattr(ej, "JOBS", deck)
    outputs = {"carddemo-posttran": {"TRANFILE": b"".join(rows)}}
    report = {"steps": []}
    ok = ej._idcams_step(step, outputs, report)
    return ok, report["steps"][0], outputs.get("carddemo-tranidx", {})


def test_the_job_wiring_passes_check_job_over_the_real_posttran_case():
    job = eq.load_case(NAME)
    cases = ej.load_steps(job, eq.load_case)
    ej.check_job(job, cases)
    assert ej.step_names(job) == ["carddemo-posttran", "carddemo-tranidx"]
    tranfile = cases["carddemo-posttran"]["datasets"]["TRANFILE"]
    assert tranfile["reclen"] == 350 and tranfile["keys"] == [{"offset": 0, "length": 16}] and tranfile["compare"]
    assert cases["carddemo-tranidx"]["datasets"]["TRANPATH"] == {
        "organization": "sequential",
        "reclen": 350,
        "compare": True,
    }
    assert json.loads((eq.CASES / "jobs" / f"{NAME}.json").read_text(encoding="utf-8"))["notes"]


ROWSETS = {
    "distinct": [("T1", "2022-07-03-A"), ("T2", "2022-07-01-B"), ("T3", "2022-07-02-C")],
    "duplicates": [("T1", "2022-07-02-B"), ("T2", "2022-07-01-A"), ("T3", "2022-07-02-B"), ("T4", "2022-07-01-A")],
    "all equal": [("T1", "SAME"), ("T2", "SAME"), ("T3", "SAME")],
    "one record": [("T1", "ONLY")],
    "key order opposite to timestamp order": [("A", "9"), ("B", "5"), ("C", "1")],
    "blank timestamps": [("T1", ""), ("T2", "2022-07-01-A"), ("T3", "")],
}


@pytest.mark.parametrize("rows", ROWSETS.values(), ids=ROWSETS.keys())
def test_the_path_is_in_alternate_key_order_with_duplicates_in_the_bases_order(rows):
    recs = [_tran(pk, ts) for pk, ts in rows]
    ok, entry, out = _run(recs)
    assert ok and entry["rc"] == 0 and entry["fed"] == {"TRANKSDS": f"carddemo-posttran.TRANFILE ({len(recs)} records)"}
    assert out["TRANKSDS"] == b"".join(sorted(recs))  # the base, in primary-key order (the keys are all distinct)
    want = sorted(sorted(recs), key=lambda r: r[304:330])  # stable: ties stay in primary-key order
    assert out["TRANPATH"] == b"".join(want)
    if "java" in entry:  # the Java IDCAMS step is compared once the harness runs it (#8976); then it must agree
        assert entry["java"]["equal"] and entry["model_only"] is False, entry["java"]
    else:
        assert entry["model_only"] is True  # the Java side was not compared: never proven


def test_a_base_fed_out_of_key_order_is_loaded_in_key_order():
    recs = [_tran("T3", "C"), _tran("T1", "B"), _tran("T2", "A")]
    ok, _, out = _run(recs)
    assert ok and out["TRANKSDS"] == b"".join(sorted(recs))
    assert out["TRANPATH"] == b"".join(sorted(recs, key=lambda r: r[304:330]))


def test_an_empty_base_is_refused_by_name():  # IBM's condition code for BLDINDEX over an empty base is not modelled
    ok, entry, out = _run([])
    assert not ok and "empty base cluster" in entry["stopped"] and "TRANPATH" not in out


def _deck_dir(tmp_path, deck):
    (tmp_path / "carddemo-tranidx.idc").write_text(deck, encoding="utf-8")
    return tmp_path


REAL = (ROOT / "tests/equivalence/jobs/carddemo-tranidx.idc").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "deck",
    [
        REAL.replace("NONUNIQUEKEY", "UNIQUEKEY"),  # duplicates: refused by name, never executed
        REAL.replace("NONUNIQUEKEY", "NOUPGRADE"),
        REAL.replace("RELATE(AWS.M2.CARDDEMO.TRANSACT.VSAM.KSDS)", "RELATE(NO.SUCH.BASE)"),
        REAL.split("   BLDINDEX")[0],  # a path over an index nothing built
    ],
    ids=["unique-over-duplicates", "noupgrade", "relate-missing", "path-without-bldindex"],
)
def test_what_the_model_does_not_cover_stops_the_step_and_is_never_proven(tmp_path, monkeypatch, deck):
    dup = [_tran("T1", "SAME"), _tran("T2", "SAME")]
    ok, entry, out = _run(dup, deck=_deck_dir(tmp_path, deck), monkeypatch=monkeypatch)
    assert not ok and entry["ok"] is False and entry.get("stopped"), entry  # a refusal or a nonzero condition code
    assert "TRANPATH" not in out


@pytest.mark.parametrize(
    ("dd", "why"),
    [
        ({"path": PATH, "reclen": 350, "keys": [{"offset": 0, "length": 4}]}, "an output only"),
        ({"path": PATH, "reclen": 350, "cluster": "X"}, "an output only"),
    ],
)
def test_a_path_dd_is_an_output_only(dd, why):
    job = eq.load_case(NAME)
    job["steps"][1]["idcams"]["dds"]["TRANPATH"] = dd
    cases = ej.load_steps(job, eq.load_case)
    with pytest.raises(ej.Unsupported, match=why):
        ej.check_job(job, cases)


ONEKEY = "carddemo-job-posttran-tranidx-onekey"
ONEKEY_DECK = ROOT / "tests/equivalence/jobs/carddemo-tranidx-onekey.idc"
# The harness's POSTTRAN run stamps every TRANFILE record with one processed timestamp (the PARM date): one alternate key.
POSTTRAN_SHAPE = [_tran(f"{i:016d}", "2022-07-18-10.30.15.000000") for i in range(264)]


def test_the_real_deck_stops_by_name_on_the_one_key_posttran_leaves():
    """Run 2026-11-22: all 264 records share the key, BLDINDEX's record for it needs more than RECORDSIZE(350,350)."""
    ok, entry, out = _run(POSTTRAN_SHAPE)
    assert not ok and "RECORDSIZE maximum 350" in entry["stopped"] and "TRANPATH" not in out


def test_the_onekey_variant_differs_from_the_real_deck_only_in_recordsize():
    real = REAL.replace("RECORDSIZE(350,350)    ", "RECORDSIZE(4400,4400)  ")
    assert ONEKEY_DECK.read_text(encoding="utf-8") == real
    job = eq.load_case(ONEKEY)
    ej.check_job(job, ej.load_steps(job, eq.load_case))
    assert job["steps"][1]["idcams"]["deck"] == "carddemo-tranidx-onekey.idc" and job["notes"]


def test_the_onekey_variant_reads_all_duplicates_in_the_bases_order():
    step = json.loads((eq.CASES / "jobs" / f"{ONEKEY}.json").read_text(encoding="utf-8"))["steps"][1]
    recs = list(reversed(POSTTRAN_SHAPE))  # fed out of key order: the base loads sorted, the path keeps that order
    ok, entry, out = _run(recs, step=step)
    assert ok and entry["rc"] == 0 and entry["log"][-1].endswith("264 records, 1 keys: condition code 0")
    assert out["TRANPATH"] == b"".join(sorted(recs))
    if "java" in entry:
        assert entry["java"]["equal"] and entry["model_only"] is False, entry["java"]


@pytest.mark.parametrize(
    "deck",
    [
        REAL.replace("INDATASET(AWS.M2.CARDDEMO.TRANSACT.VSAM.KSDS)", "INFILE(IN)"),  # the DD form
        REAL + REAL.split("   BLDINDEX")[1].join(["   BLDINDEX", ""]),  # a second BLDINDEX of a built index
        REAL + "   DELETE AWS.M2.CARDDEMO.TRANSACT.VSAM.AIX\n",  # dependents of an AIX are not modelled
        REAL.replace("PATHENTRY(AWS.M2.CARDDEMO.TRANSACT.VSAM.AIX)", "PATHENTRY(AWS.M2.CARDDEMO.TRANSACT.VSAM.KSDS)"),
        REAL.replace("KEYS(26 304)", "KEYS(26 340)"),  # past the 350-byte record
        REAL.replace("NONUNIQUEKEY", "REUSE"),
    ],
    ids=["bldindex-dd-form", "bldindex-twice", "delete-aix", "path-over-cluster", "key-past-record", "reuse"],
)
def test_more_unmodelled_aix_shapes_stop_the_step_by_name(tmp_path, monkeypatch, deck):
    ok, entry, out = _run([_tran("T1", "A"), _tran("T2", "B")], deck=_deck_dir(tmp_path, deck), monkeypatch=monkeypatch)
    assert not ok and entry["ok"] is False and entry["stopped"].startswith("the IDCAMS model refuses"), entry
    assert "TRANPATH" not in out
