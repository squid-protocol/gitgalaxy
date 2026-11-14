"""MVS 3.8J job runner (#8414): the printer-file parser and the card-reader submit, over fixture text and a local socket."""

import json
import socket
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "box" / "mvs38j"))
import runner

LOG = """\
 IEF403I TESTJOB - STARTED - TIME=12.00.01
 IEF285I   SYS1.PROCLIB                                 KEPT
 IEF142I TESTJOB STEP1 - STEP WAS EXECUTED - COND CODE 0008
 IEF285I   SYS90001.T120001.RA000.TESTJOB.TEMP          DELETED
 IEF272I TESTJOB STEP2 - STEP WAS NOT EXECUTED.
 IEF202I TESTJOB STEP3 - STEP WAS NOT RUN BECAUSE OF CONDITION CODES
 IEF450I TESTJOB STEP4 P1 - ABEND S0C7 U0000 SYSTEM=0C7 USER=0000
 IEF999X TESTJOB something this parser has not been taught
 $HASP395 TESTJOB  ENDED
"""


def test_steps_dispositions_and_abends_are_parsed():
    job = runner.parse_log(LOG)["jobs"][0]
    assert job["job"] == "TESTJOB" and job["ended"] and not job["jcl_error"]
    assert [(s["step"], s["executed"], s["cond_code"]) for s in job["steps"]] == [
        ("STEP1", True, 8),
        ("STEP2", False, None),
        ("STEP3", False, None),
    ]
    assert job["abends"] == [{"step": "STEP4", "system": "S0C7", "user": "U0000"}]
    assert [d["disposition"] for d in job["dispositions"]] == ["KEPT", "DELETED"]


def test_provenance_and_unknown_messages_are_counted_not_guessed():
    out = runner.parse_log(LOG)
    assert out["provenance"] == "mvs38j-run"
    assert out["unparsed_ief"] == 1


def test_a_jcl_error_is_flagged_and_the_job_filter_selects():
    text = LOG + " IEF452I BADJOB - JOB NOT RUN - JCL ERROR\n"
    assert [j["job"] for j in runner.parse_log(text, "badjob")["jobs"]] == ["BADJOB"]
    assert runner.parse_log(text, "badjob")["jobs"][0]["jcl_error"]
    assert runner.parse_log(text, "nosuch")["jobs"] == []


def test_the_parse_command_prints_json(tmp_path, capsys):
    f = tmp_path / "prt.txt"
    f.write_text(LOG)
    assert runner.main(["parse", str(f), "TESTJOB"]) == 0
    assert json.loads(capsys.readouterr().out)["jobs"][0]["steps"][0]["cond_code"] == 8


def test_submit_sends_80_column_cards_and_refuses_a_non_jcl_deck(tmp_path):
    deck = tmp_path / "d.jcl"
    deck.write_text("//T JOB\n//S EXEC PGM=IEFBR14\n")
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    got = []

    def serve():
        c, _ = srv.accept()
        with c:
            got.append(b"".join(iter(lambda: c.recv(4096), b"")))

    t = threading.Thread(target=serve)
    t.start()
    runner.submit(deck, "127.0.0.1", srv.getsockname()[1])
    t.join(10)
    srv.close()
    assert [len(x) for x in got[0].decode().splitlines()] == [80, 80]
    bad = tmp_path / "bad.txt"
    bad.write_text("hello\n")
    with pytest.raises(ValueError):
        runner.submit(bad)


def test_wait_ignores_an_earlier_run_of_the_same_job_name(tmp_path):
    f = tmp_path / "prt.txt"
    f.write_text(LOG)
    assert not runner.wait_for_job(f, "TESTJOB", 0.2, since=f.stat().st_size, interval=0.05)
    assert runner.wait_for_job(f, "TESTJOB", 0.2, since=0, interval=0.05)
