"""#5278: the CardDemo COPAUA0C equivalence case (IMS DBPAUTP0 through EXEC DLI, three VSAM files, the MQ request / reply
queues) and the harness steps it needed. The unit tests need nothing but the case; the proof itself (20 scenarios,
GnuCOBOL against the det port) is the det sweep's, `det_port.py run carddemo-copaua0c`."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tests" / "tools"
sys.path.insert(0, str(TOOLS))

from gitgalaxy.core.source_text import read_source  # noqa: E402

import equivalence_cics as ec  # noqa: E402
import equivalence_ims as ims  # noqa: E402

CASE = ROOT / "tests" / "equivalence" / "carddemo-copaua0c"
APP = "app/app-authorization-ims-db2-mq"

# the request outcomes the program decides, the file faults it handles, and the queue set-ups it reports
SCENARIOS = [
    "no-request", "approve-summary-found", "schd-already-held", "decline-insufficient-funds", "approve-no-summary",
    "decline-no-summary-over-account-limit", "card-not-in-xref", "account-not-in-master", "customer-not-in-master",
    "same-account-twice", "amount-without-decimals", "amount-with-sign", "three-requests-mixed",
    "read-xref-io-error", "read-acct-io-error", "read-cust-io-error", "no-trigger-data", "no-reply-queue",
    "gu-summary-bad-status", "repl-summary-fails", "request-longer-than-buffer", "schd-held-after-term",
    "open-request-queue-fails", "get-request-fails", "close-request-queue-fails", "five-hundred-one-requests",
]  # fmt: skip


def _case() -> dict:
    return json.loads((CASE / "case.json").read_text(encoding="utf-8"))


def _corpus() -> Path | None:
    corpora = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", ROOT / ".mainframe_corpora"))
    corpus = corpora / "aws-mainframe-modernization-carddemo"
    return corpus if (corpus / APP / "cbl/COPAUA0C.cbl").is_file() else None


def test_the_case_states_every_scenario_with_its_reason():
    case = _case()
    assert [s["name"] for s in case["scenarios"]] == SCENARIOS
    assert all(s["why"].strip() for s in case["scenarios"])


def test_every_queue_and_file_a_scenario_names_is_stated():
    case = _case()
    queues = set(case["mq"]["queues"])
    files = {f.split(".")[-3] if f.count(".") > 2 else f for f in case["datasets"]}
    assert len(files) == 3
    for s in case["scenarios"]:
        for q, msgs in s.get("mq_messages", {}).items():
            assert q in queues
            assert all(m["replytoq"] in queues for m in msgs if m.get("replytoq"))
        assert set(s.get("mq", {}).get("queues", queues)) <= queues
    assert {c["name"] for c in case["ims"]["compare"]} == {"DBPAUTP0"} if isinstance(case["ims"]["compare"][0], dict) \
        else set(case["ims"]["compare"]) == {"DBPAUTP0"}  # fmt: skip


def test_the_case_notice_names_the_sources_own_license():
    assert "Apache" in (CASE / "NOTICE").read_text(encoding="utf-8")
    assert (CASE / "LICENSE").read_text(encoding="utf-8").lstrip().startswith("Apache License")


def test_the_two_extra_xref_records_are_card_xref_records():
    rows = (CASE / "cardxref-5278.txt").read_text(encoding="ascii").splitlines()
    assert [len(r) for r in rows] == [36, 36]  # CVACT03Y: card 16, customer 9, account 11
    assert {r[:16] for r in rows} == {"8888000000000001", "8888000000000002"}


def test_a_dli_length_may_be_a_length_of():
    """COPAUA0C: SEGLENGTH(LENGTH OF PENDING-AUTH-DETAILS) -- the oracle passes it by value, as a literal."""
    out = ec.translate_dli("ISRT USING PCB(PAUT-PCB-NUM) SEGMENT(PAUTSUM0) SEGMENT(PAUTDTL1) "
                           "FROM(PENDING-AUTH-DETAILS) SEGLENGTH(length  of PENDING-AUTH-DETAILS)")  # fmt: skip
    assert "    BY VALUE LENGTH OF PENDING-AUTH-DETAILS" in out
    with pytest.raises(ec.Unsupported, match="a literal or a data name"):
        ec._dli_operand("LENGTH OF A(1)", "SEGLENGTH")


PSB = """\
P1       PCB   TYPE=DB,DBDNAME=D1,PROCOPT=A,KEYLEN=4
         SENSEG  NAME=ROOT,PARENT=0
         PSBGEN  LANG=COBOL,PSBNAME=P,CMPAT=YES
"""
DBD = """\
         DBD   NAME=D1,ACCESS=(HIDAM,VSAM)
         DATASET DD1=A,DEVICE=3380
SEG1     SEGM  NAME=ROOT,PARENT=0,BYTES=8
         FIELD NAME=(KEY,SEQ,U),BYTES=4,START=1,TYPE=C
         DBDGEN
         FINISH
         END
"""


def test_cmpat_yes_is_refused_for_batch_dli_and_taken_under_cics():
    """Register I5: EXEC DLI numbers the DB PCBs from 1 (no I/O PCB first), so the PSB's CMPAT=YES changes nothing there;
    a batch program is still entered with the I/O PCB first (not modelled)."""
    dbds = {"D1": ims.dbd(DBD, "d1.dbd")}
    with pytest.raises(ims.Unsupported, match="CMPAT=YES"):
        ims.psb(PSB, "p.psb", dbds)
    assert [p["dbd"] for p in ims.psb(PSB, "p.psb", dbds, cics=True)] == ["D1"]


def test_an_unload_record_can_be_left_out_of_the_seed(tmp_path):
    """The corpus's HD unload ends with a root whose packed key is blank, which a GU qualification refuses by design."""
    corpus = _corpus()
    if corpus is None:
        pytest.skip("needs the burned mainframe corpora (GITGALAXY_MAINFRAME_CORPORA)")
    case = _case()
    dbds, _ = ims.definitions(case, corpus, cics=True)
    assert case["ims"]["seed"]["DBPAUTP0"]["skip"] == [223]
    kept = ims.seed(case, corpus, "DBPAUTP0", dbds["DBPAUTP0"])
    case["ims"]["seed"]["DBPAUTP0"].pop("skip")
    whole = ims.seed(case, corpus, "DBPAUTP0", dbds["DBPAUTP0"])
    assert len(whole) - len(kept) == 8 + dbds["DBPAUTP0"]["segments"][0]["bytes"]
    assert whole.startswith(kept)


def test_the_committed_det_port_has_a_recorded_proof():
    """`evidence.py prove` records a level only for a committed port: this one is the det translator's own."""
    prov = json.loads((CASE / "port" / "provenance.json").read_text(encoding="utf-8"))
    assert (prov["program"], prov["translator"]) == ("COPAUA0C", "det")
    assert (CASE / "port" / "service" / "Copaua0cService.java").is_file()
    rec = json.loads((CASE / "evidence.json").read_text(encoding="utf-8"))
    assert rec["proof"]["verdict"] == "proven" and not rec["proof"]["java_failed"]
    assert rec["proof"]["runs"] == len(SCENARIOS) and rec["provenance"]["written_by"] == "det"
    assert rec["coverage"]["branches"]["total"] == 71


def test_the_request_limit_exit_is_taken_by_a_501_request_scenario():
    """Line 339 (true): 501 requests in one task end the loop; the reply pointer is never reset, so every reply after the
    third puts a 201-byte length over the 200-byte buffer (undefined in IBM): the case states that assumption."""
    case = _case()
    sc = {s["name"]: s for s in case["scenarios"]}["five-hundred-one-requests"]
    msgs = sc["mq_messages"]["CARDDEMO.REQUEST.QUEUE"]
    assert len(msgs) == 501 and len({m["data"] for m in msgs}) == 501
    notes = case["notes"]
    assert "WS-RESP-LENGTH" in notes and "line 339" in notes and "assumption" in notes
    corpus = _corpus()
    if corpus is None:
        pytest.skip("needs the burned mainframe corpora (GITGALAXY_MAINFRAME_CORPORA)")
    src = read_source(corpus / APP / "cbl/COPAUA0C.cbl").text.splitlines()
    assert (
        "WS-RESP-LENGTH" in src[45] and "VALUE 1" in src[45] and "W02-PUT-BUFFER" in src[107] and "X(200)" in src[107]
    )
    assert (
        sum("WS-RESP-LENGTH" in ln for ln in src) == 3
    )  # declared, the STRING POINTER, the MQPUT1 length: never reset
    assert "WS-REQSTS-PROCESS-LIMIT" in src[338] and "VALUE 500" in src[39]


def test_the_mq_fault_scenarios_plan_one_failing_call_each():
    import equivalence_mq as emq

    case = _case()
    by_name = {s["name"]: s for s in case["scenarios"]}
    plans = {
        "open-request-queue-fails": ("MQOPEN", 1),
        "get-request-fails": ("MQGET", 1),
        "close-request-queue-fails": ("MQCLOSE", 1),
    }
    for name, (verb, nth) in plans.items():
        faults = by_name[name]["mq_faults"]
        assert [(f["call"], f["nth"]) for f in faults] == [(verb, nth)]
        text = emq.cfg(emq.state(case, by_name[name]), "latin-1")
        assert f"FAULT {verb} {nth} {faults[0]['reason']}" in text


@pytest.mark.parametrize(
    "plan",
    [
        [{"call": "MQDISC", "nth": 1, "reason": 2009}],
        [{"call": "MQCLOSE", "nth": 0, "reason": 2009}],
        [{"call": "MQCLOSE", "nth": 1, "reason": 2016}],
    ],
)
def test_a_bad_mq_fault_plan_is_refused(plan):
    import equivalence_mq as emq

    with pytest.raises(ValueError):
        emq.fault_plan(plan, "x")
