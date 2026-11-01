"""The SORT equivalence case (#4268): `tests/equivalence/carddemo-sort-tranrept` carries its COBOL (CardDemo TRANREPT
STEP05R lowered by det/dfsort.py), so `program_source` may be `@case/<file>`. The proof itself is `det_port.py run
carddemo-sort-tranrept` (GnuCOBOL against the det port); these pin what it rests on."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/tools"))

import equivalence_common as ecm  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import dfsort as D  # noqa: E402

CASE = ROOT / "tests/equivalence/carddemo-sort-tranrept"
RECLEN = 350
# CardDemo app/proc/TRANREPT.prc STEP05R (verbatim, as test_dfsort_4268.py)
SYM = """TRAN-CARD-NUM,263,16,ZD
TRAN-PROC-DT,305,10,CH
PARM-START-DATE,C'2022-01-01' //Date format yyyy-mm-dd
PARM-END-DATE,C'2022-07-06' //Date format yyyy-mm-dd
"""
SYSIN = """ SORT FIELDS=(TRAN-CARD-NUM,A)
 INCLUDE COND=(TRAN-PROC-DT,GE,PARM-START-DATE,AND,
    TRAN-PROC-DT,LE,PARM-END-DATE)
"""


def _records() -> list[bytes]:
    data = (CASE / "sortin.txt").read_bytes()
    lines = data.split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()
    return lines


def test_program_file_resolves_a_case_local_and_a_corpus_program(tmp_path):
    case = {"name": "carddemo-sort-tranrept", "program_source": "@case/DFSORTST.cbl"}
    assert ecm.program_file(case, tmp_path) == ecm.CASES / "carddemo-sort-tranrept" / "DFSORTST.cbl"
    assert ecm.program_file({"name": "x", "program_source": "app/cbl/P.cbl"}, tmp_path) == tmp_path / "app/cbl/P.cbl"
    assert ecm.program_file(case, tmp_path, "app/cbl/Q.cbl") == tmp_path / "app/cbl/Q.cbl"


def test_the_committed_program_is_the_dfsort_lowering():
    want = D.cobol_program(D.parse(SYSIN, SYM), RECLEN, ["SORTIN"])
    assert (CASE / "DFSORTST.cbl").read_text(encoding="utf-8") == want


def test_the_input_is_the_class_the_case_claims():
    recs = _records()
    assert recs and all(len(r) == RECLEN for r in recs)
    keys = [r[262:278] for r in recs]
    assert len(set(keys)) == len(keys), "equal keys: DFSORT's order is undefined (no EQUALS), the port stops by name"
    assert keys != sorted(keys), "the input must be unsorted"
    dates = [r[304:314].decode("ascii") for r in recs]
    kept = [d for d in dates if "2022-01-01" <= d <= "2022-07-06"]
    assert 0 < len(kept) < len(dates), "the INCLUDE must both keep and drop records"
    assert {"2022-01-01", "2022-07-06"} <= set(dates), "both boundaries of the INCLUDE are taken"


COMB = ROOT / "tests/equivalence/carddemo-sort-combtran"


def test_the_concatenated_sortin_case_is_the_dfsort_lowering():
    """CardDemo COMBTRAN.jcl STEP05R: SORTIN is TRANSACT.BKUP(0) then SYSTRAN(0), sorted on TRAN-ID (1,16,CH)."""
    want = D.cobol_program(D.parse(" SORT FIELDS=(TRAN-ID,A)\n", "TRAN-ID,1,16,CH\n"), RECLEN, ["SORTIN1", "SORTIN2"])
    assert (COMB / "DFSORTST.cbl").read_text(encoding="utf-8") == want
    case = json.loads((COMB / "case.json").read_text(encoding="utf-8"))
    assert [dd for dd, s in case["datasets"].items() if "input" in s] == ["SORTIN1", "SORTIN2"]


def _ebcdic(k: bytes) -> bytes:
    return k.decode("ascii").encode("cp037")


def test_the_concatenated_inputs_are_the_class_the_case_claims():
    ins = []
    for n in ("1", "2"):
        data = (COMB / f"sortin{n}.txt").read_bytes()
        assert data.endswith(b"\n")
        lines = data[:-1].split(b"\n")
        assert lines and all(len(r) == RECLEN for r in lines)
        ins.append([r[:16] for r in lines])
    a, b = ins
    assert len(set(a + b)) == len(a + b), "equal keys: DFSORT's order is undefined (no EQUALS)"
    assert a != sorted(a) and b != sorted(b), "each input must be unsorted"
    assert min(b) < max(a) and min(a) < max(b), "the files interleave: the output is not their concatenation"
    # CH over letters AND digits: IBM orders a letter before a digit (EBCDIC), the oracle's byte order the reverse, so
    # the case only passes when the lowering's EBCDIC collating sequence is in force (#4035)
    allk = a + b
    assert any(k[:1].isalpha() for k in allk) and any(k[:1].isdigit() for k in allk)
    assert all(k.isalnum() and k.isascii() and k == k.upper() for k in allk)
    assert sorted(allk) != sorted(allk, key=_ebcdic), "the EBCDIC order must differ from the byte order"
    assert (COMB / "LICENSE").is_file() and (COMB / "NOTICE").is_file()


def test_the_case_names_its_files():
    case = json.loads((CASE / "case.json").read_text(encoding="utf-8"))
    for ds in case["datasets"].values():
        if "input" in ds:
            assert ecm.program_file(case | {"name": CASE.name}, Path("/nonexistent"), ds["input"]).is_file()
    assert ecm.program_file(case | {"name": CASE.name}, Path("/nonexistent")).is_file()
    assert (CASE / "LICENSE").is_file() and (CASE / "NOTICE").is_file()


@pytest.mark.parametrize(
    "case_json", sorted((ROOT / "tests/equivalence").glob("*/case.json")), ids=lambda p: p.parent.name
)
def test_every_case_program_source_is_a_case_local_file_or_a_corpus_path(case_json):
    src = json.loads(case_json.read_text(encoding="utf-8")).get("program_source")
    if src and src.startswith("@case/"):
        assert (case_json.parent / src[len("@case/") :]).is_file()


def test_the_sort_cases_l5_ledgers_state_every_survivor():
    """#4268: det_mutation's L5 for both lowered-DFSORT cases. Every survivor is stated, none is open: the DD labels
    (SORTIN, SORTIN1, SORTIN2) are killed by the per-DD fault runs below."""
    for case in ("carddemo-sort-tranrept", "carddemo-sort-combtran"):
        run = json.loads((ROOT / f"tests/equivalence/det_mutation/{case}.json").read_text(encoding="utf-8"))["entry"]
        stated = json.loads(
            (ROOT / f"tests/equivalence/det_mutation_survivors/{case}.json").read_text(encoding="utf-8")
        )
        by_id = {e["id"]: e for e in stated["survivors"]}
        assert {s["id"] for s in run["survived"]} == set(by_id), "every survivor has a verdict"
        assert all(e["verdict"] in ("equivalent", "unreachable") for e in by_id.values())


@pytest.mark.parametrize(
    "case_dir, dds",
    [(CASE, ["SORTIN"]), (COMB, ["SORTIN1", "SORTIN2"])],
    ids=lambda v: v.name if isinstance(v, Path) else "+".join(v),
)
def test_every_sort_input_dd_has_its_own_fault_run(case_dir, dds):
    """The label of a SORT input DD is compared only by a fault run on it (the injector names the DD): one run per
    DD, ending the file early (READ status 10, AT END, defined by IBM). An OPEN failure is not used: on a SORT USING
    file IBM's result depends on FASTSRT and the port refuses it by name (Sort.expect); on the lowered input
    procedure's explicit OPEN with no FILE STATUS the oracle ends in a run-time error the port does not model."""
    case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    inputs = [dd for dd, ds in case["datasets"].items() if "input" in ds]
    assert inputs == dds
    for dd in inputs:
        runs = [f for f in case["faults"] if [p["dd"] for p in f["plan"]] == [dd]]
        assert len(runs) == 1, dd
        assert [(p["op"], p["status"]) for p in runs[0]["plan"]] == [("READ", "10")]
        assert runs[0]["plan"][0]["nth"] >= 2, "a record is read before the file ends"
