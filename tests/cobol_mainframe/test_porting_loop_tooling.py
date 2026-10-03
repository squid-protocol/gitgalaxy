"""#4023 follow-up: the tooling the automated porting loop runs on -- the proof's feedback, the CALL case kind, the
CEEDAYS model, INQUIRE PROGRAM, and the loop driver itself.

The pure parts are pinned here. The CEEDAYS model runs under Docker GnuCOBOL's C compiler when EQUIVALENCE_E2E=1,
checked against Python's own calendar (not against itself).
"""

import datetime
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence as eq  # noqa: E402
import equivalence_call as ecall  # noqa: E402
import equivalence_cics as ec  # noqa: E402
import porting_loop as pl  # noqa: E402

from gitgalaxy.tools.cobol_to_java import port_runner  # noqa: E402

MAVEN_LOG = """[INFO] Running com.gitgalaxy.modernized.EquivalenceRunTest
[ERROR] Tests run: 1, Failures: 0, Errors: 1, Skipped: 0, Time elapsed: 2.4 s <<< FAILURE! -- in EquivalenceRunTest
[ERROR] com.gitgalaxy.modernized.EquivalenceRunTest.run -- Time elapsed: 0.2 s <<< ERROR!
java.lang.NullPointerException: Cannot invoke "LocalDateTime.format" because "now" is null
\tat java.base/java.util.Objects.requireNonNull(Objects.java:1)
\tat com.gitgalaxy.modernized.service.Comen01cService.populateHeaderInfo(Comen01cService.java:277)
\tat com.gitgalaxy.modernized.service.Comen01cService.runTask(Comen01cService.java:122)
[ERROR] /work/java/src/main/java/com/gitgalaxy/modernized/service/X.java:[12,5] cannot find symbol
[ERROR] /work/java/src/main/java/com/gitgalaxy/modernized/service/X.java:[12,5] cannot find symbol
[ERROR] -> [Help 1]
[ERROR] Re-run Maven using the -X switch to enable full debug logging.
"""


def test_a_failed_java_run_is_feedback_errors_once_with_the_ports_frames(tmp_path):
    (tmp_path / "java").mkdir()
    (tmp_path / "java" / "maven.log").write_text(MAVEN_LOG, encoding="utf-8")
    report = eq.java_failure_report({"name": "c", "program": "P"}, tmp_path, "")
    fb = report["feedback"]
    assert report["java_failed"] and not report["proven"]
    assert fb.count("X.java:[12,5] cannot find symbol") == 1 and "/work/java" not in fb  # once, file name only
    assert "NullPointerException" in fb and "Comen01cService.populateHeaderInfo(Comen01cService.java:277)" in fb
    assert "Help 1" not in fb and "Re-run Maven" not in fb


def test_batch_feedback_names_the_differing_records_and_the_failing_fault_runs():
    diff = {
        "equal": 1,
        "records": 2,
        "diffs": [{"record": 2, "fields": [{"field": "ACCT-BAL", "cobol": "1.00", "java": "2.00"}]}],
    }
    report = {"return_code": {"cobol": "0", "java": "0"}, "abend": {"cobol": None, "java": None},
              "outputs": {"ACCTFILE": diff},
              "faults": [{"name": "dup", "ok": False, "plan": ["F WRITE 1 22"], "why": "22: duplicate key",
                          "summary": "ABEND: COBOL U0999, Java None", "outputs": {}}]}  # fmt: skip
    fb = eq.feedback_md(report)
    assert "ACCTFILE: 1/2 records equal" in fb and "record 2 ACCT-BAL: COBOL `1.00`, Java `2.00`" in fb
    assert "`dup` injects F WRITE 1 22" in fb and "ABEND: COBOL U0999, Java None" in fb


def test_cics_feedback_names_a_file_a_scenario_left_different_when_its_events_are_equal():
    """A LINKed program's write, or the port's own, can differ while every event is equal: the model must hear of it
    (an empty feedback left three model ports nothing to act on)."""
    case = {"scenarios": [{"name": "abend-path", "commarea": {"ACCNO": "4"}}, {"name": "fine"}]}
    files = {
        "ABNDFILE": {"records": 1, "equal": 0, "diffs": [{"record": 1, "missing": "java"}]},
        "DB2 ACCOUNT": {
            "records": 2,
            "equal": 1,
            "diffs": [{"record": 2, "fields": [{"field": "BAL", "cobol": "1.00", "java": "2.00"}]}],
        },
    }
    report = {"outputs": {"abend-path": {"equal": 3, "records": 3, "diffs": [], "files": files},
                          "fine": {"equal": 2, "records": 2, "diffs": [], "files": {}}}}  # fmt: skip
    fb = ec.feedback_md(case, report)
    assert "### Scenario abend-path: 3/3 events equal" in fb and "fine" not in fb
    assert "- ABNDFILE: 0/1 records equal" in fb and "record 1: missing on the java side" in fb
    assert "record 2 BAL: COBOL `1.00`, Java `2.00`" in fb


def test_the_ticket_key_is_the_member_name_the_generator_wrote(tmp_path):
    """GenApp's members are lower case (lgicdb01.cbl), so are its tickets; the case names the program upper case."""
    jobs = tmp_path / "ai_agent_jobs"
    jobs.mkdir()
    for key in ("lgicdb01", "INQACC"):
        (jobs / f"{key}_port_ticket.json").write_text("{}", encoding="utf-8")
    assert pl.ticket_key(tmp_path, "LGICDB01") == "lgicdb01" and pl.ticket_key(tmp_path, "INQACC") == "INQACC"
    with pytest.raises(SystemExit):
        pl.ticket_key(tmp_path, "LGUPDB01")


def test_an_adopted_port_carries_its_own_estates_licence():
    for corpus, words in (("cics-genapp", "EPL-2.0"), ("cics-banking-sample-application-cbsa", "EPL-2.0"),
                          ("aws-mainframe-modernization-carddemo", "Apache-2.0")):  # fmt: skip
        assert words in pl.PORT_LICENCE[corpus]


CALL_CASE = {"name": "c", "program": "SUBP", "using": [{"name": "LS-A", "size": 4}, {"name": "LS-B", "size": 6}],
             "calls": [{"name": "one", "args": ["AB", ""]}, {"name": "two", "args": ["it's", "X"]}]}  # fmt: skip


def test_a_call_case_drives_every_using_item_and_records_them_with_the_return_code():
    fields = ecall.record_fields(CALL_CASE)
    assert [(f["name"], f["offset"], f["bytes"]) for f in fields] == [
        ("LS-A", 0, 4),
        ("LS-B", 4, 6),
        ("RETURN-CODE", 10, 5),
    ]
    assert ecall.reclen(CALL_CASE) == 15
    driver = ecall.cobol_driver(CALL_CASE)
    assert "CALL 'SUBP' USING A0 A1" in driver and "MOVE 'it''s' TO A0" in driver and "MOVE SPACES TO A1" in driver
    assert driver.count("WRITE OUT-R FROM CALL-REC") == 2
    assert all(len(line) <= 72 for line in driver.splitlines())
    test = ecall.java_test({**CALL_CASE, "clock": "2022/07/18 10:30:15.00"})
    assert "int rc = subpService.handleCall(a0, a1);" in test and "CobolRef<String> a1 = CobolRef.of(pad(" in test
    with pytest.raises(ecall.Unsupported):
        ecall.cobol_driver({**CALL_CASE, "calls": [{"name": "x", "args": ["TOO LONG", ""]}]})


def test_inquire_program_translates_and_can_be_injected():
    assert ec.translate_command("INQUIRE PROGRAM(WS-PGM) NOHANDLE")[:2] == ["MOVE WS-PGM TO GG-NAME1",
                                                                             "CALL 'GGCINQP' USING GG-CICS"]  # fmt: skip
    with pytest.raises(ec.Unsupported):
        ec.translate_command("INQUIRE PROGRAM(X) STATUS(WS-S)")
    sc = {"name": "s", "faults": [{"cmd": "INQUIRE", "program": "COPAUS0C", "resp": "PGMIDERR"}]}
    assert ec.fault_lines(sc) == ["INQUIRE COPAUS0C 1 27 0"]


def test_the_prompt_shows_the_runtime_a_port_must_call():
    assert "batch/CobolFiles.java" in port_runner._RUNTIME_HELPERS
    assert "batch/CobolAbend.java" in port_runner._RUNTIME_HELPERS


def test_the_loop_runs_the_model_with_no_tools_outside_the_repository():
    assert "--tools ''" in pl.CLAUDE and "--strict-mcp-config" in pl.CLAUDE and "cd {prompt_dir}" in pl.CLAUDE
    md = pl.loop_md({"case": "c", "program": "P", "model": "m", "backend": "b", "proven": True, "seconds": 9,
                     "attempts": [{"n": 1, "verdict": "not proven", "java_failed": True, "feedback": "boom"},
                                  {"n": 2, "verdict": "proven", "outputs": {"F": "2/2"}, "faults": {"a": True}}]})  # fmt: skip
    assert (
        "proven on attempt 2" in md
        and "| 1 | not proven | Java failed |" in md
        and "| 2 | proven | F 2/2 | 1/1 |" in md
    )


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1" or not shutil.which("docker"), reason="needs Docker")
def test_the_ceedays_model_against_the_calendar(tmp_path):
    """Lilian days are days since 14 October 1582 (IBM): checked against Python's calendar, and each documented
    feedback message number."""
    cases = {"2022-07-18": 0, "1582-10-15": 0, "9999-12-31": 0, "2024-02-29": 0, "1900-02-29": 2508,
             "2022-AB-01": 2520, "2022/07/18": 2520, "1582-10-14": 2513}  # fmt: skip
    main = ['#include <stdio.h>', '#include <string.h>',
            'int CEEDAYS(unsigned char*, unsigned char*, unsigned char*, unsigned char*);',
            'static void vs(unsigned char *b, const char *s) { size_t n = strlen(s); b[0] = 0; b[1] = (unsigned char)n; memcpy(b + 2, s, n); }',
            'int main(void) { unsigned char d[16], p[16], l[4], fc[12];']  # fmt: skip
    for date in cases:
        main += [
            f'vs(d, "{date}"); vs(p, "YYYY-MM-DD"); CEEDAYS(d, p, l, fc);',
            'printf("%ld %d\\n", ((long)l[0] << 24) | (l[1] << 16) | (l[2] << 8) | l[3], (fc[2] << 8) | fc[3]);',
        ]
    main.append("return 0; }")
    (tmp_path / "t.c").write_text("\n".join(main), encoding="ascii")
    shutil.copy(ecall.LE / "ceedays.c", tmp_path / "ceedays.c")
    proc = subprocess.run(["docker", "run", "--rm", "-v", f"{tmp_path}:/w", "-w", "/w", eq.IMAGE, "bash", "-c",  # noqa: S603, S607
                           "gcc -o t t.c ceedays.c && ./t"], capture_output=True, text=True, check=False)  # fmt: skip
    assert proc.returncode == 0, proc.stderr
    epoch = datetime.date(1582, 10, 14)
    for (date, msg), line in zip(cases.items(), proc.stdout.split("\n")):
        lilian, got = (int(x) for x in line.split())
        assert got == msg, date
        if not msg:
            assert lilian == (datetime.date.fromisoformat(date) - epoch).days, date


def test_a_call_cases_file_is_well_formed():
    case = json.loads((eq.CASES / "carddemo-dateutil" / "case.json").read_text(encoding="utf-8"))
    assert case["kind"] == "call" and all(len(c["args"]) == len(case["using"]) for c in case["calls"])
    assert all(c["args"][1] in ("YYYY-MM-DD", "YYYY/MM/DD") for c in case["calls"])  # only the modelled pictures


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1", reason="needs Docker (GnuCOBOL) and a JDK + Maven")
@pytest.mark.parametrize(
    "case",
    [
        "carddemo-trnrpt",
        "carddemo-menu",
        "carddemo-dateutil",
        "carddemo-useradd",
        "carddemo-adminmenu",
        "carddemo-cardview",
        "carddemo-userupd",
        "carddemo-tranview",
        "carddemo-userdel",
        "carddemo-userlist",
        "carddemo-tranlist",
        "carddemo-tranadd",
        "carddemo-billpay",
        "carddemo-cardlist",
        "carddemo-signon",
        "carddemo-report",
        "carddemo-readcard",
        "carddemo-readxref",
        "carddemo-readcust",
        "carddemo-dailyval",
        "cbsa-updacc",
        "genapp-lgicdb01",
        "genapp-lgapvs01",
    ],
)
def test_the_loops_committed_ports_are_proven(case, tmp_path):
    """The ports the porting loop wrote (port/provenance.json: the model's answer, unedited) prove against their case:
    the report with its 24 fault runs, the menu's 11 CICS scenarios, the date check's 11 CALLs."""
    provenance = json.loads((eq.CASES / case / "port" / "provenance.json").read_text(encoding="utf-8"))
    assert provenance["edited_after"].startswith("none")
    proc = subprocess.run([sys.executable, str(Path(eq.__file__)), "run", case, "--keep", str(tmp_path)],  # noqa: S603
                          capture_output=True, text=True, check=False)  # fmt: skip
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-3000:]
    assert json.loads((tmp_path / "report.json").read_text())["proven"]


def test_no_committed_port_or_case_lost_its_json_to_the_ignore_rule():
    """.gitignore ignores *.json repo-wide, with exceptions. A new case.json or provenance.json outside them is
    silently never committed: #4025's 17 crucible provenance files were lost that way. CI checks out only tracked
    files, so a missing one fails here."""
    root = eq.CASES.parents[1]
    ports = sorted(p for p in (root / "tests" / "cics_crucible" / "ports").glob("*/*") if (p / "overlay").is_dir())
    assert ports and [p for p in ports if not (p / "provenance.json").is_file()] == []
    cases = sorted(p for p in eq.CASES.iterdir() if p.is_dir() and (p / "LICENSE").is_file())
    assert cases and [p for p in cases if not (p / "case.json").is_file()] == []
    looped = [p for p in cases if (p / "port").is_dir() and (p / "port" / "provenance.json").exists()]
    assert {p.name for p in looped} >= {"carddemo-trnrpt", "carddemo-menu", "carddemo-dateutil"}


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1" or not shutil.which("docker"), reason="needs Docker")
@pytest.mark.parametrize("date", ["2022-07-1 ", "2022-07   ", "          "])
def test_the_ceedays_model_refuses_a_blank_padded_date(tmp_path, date):
    """#4049: IBM does not document whether CEEDAYS ignores trailing blanks (2507 once the date is shorter than the
    picture) or reads a blank in a numeric position (2520) -- so the model refuses, as for month 13."""
    main = ['#include <stdio.h>', '#include <string.h>',
            'int CEEDAYS(unsigned char*, unsigned char*, unsigned char*, unsigned char*);',
            'static void vs(unsigned char *b, const char *s) { size_t n = strlen(s); b[0] = 0; b[1] = (unsigned char)n; memcpy(b + 2, s, n); }',
            'int main(void) { unsigned char d[16], p[16], l[4], fc[12];',
            f'vs(d, "{date}"); vs(p, "YYYY-MM-DD"); CEEDAYS(d, p, l, fc); puts("converted"); return 0; }}']  # fmt: skip
    (tmp_path / "t.c").write_text("\n".join(main), encoding="ascii")
    shutil.copy(ecall.LE / "ceedays.c", tmp_path / "ceedays.c")
    proc = subprocess.run(["docker", "run", "--rm", "-v", f"{tmp_path}:/w", "-w", "/w", eq.IMAGE, "bash", "-c",  # noqa: S603, S607
                           "gcc -o t t.c ceedays.c && ./t"], capture_output=True, text=True, check=False)  # fmt: skip
    assert proc.returncode == 98 and "converted" not in proc.stdout
    assert "trailing blanks is not modelled" in proc.stderr


def test_adopt_refuses_a_loop_that_did_not_prove(tmp_path):
    """Only a proven loop's port is taken into a case: never a failed one, never another case's."""
    (tmp_path / "loop.json").write_text(json.dumps({"case": "carddemo-menu", "proven": False, "attempts": []}))
    with pytest.raises(SystemExit, match="not a proven loop"):
        pl.adopt("carddemo-menu", tmp_path)
    (tmp_path / "loop.json").write_text(json.dumps({"case": "carddemo-useradd", "proven": True, "attempts": []}))
    with pytest.raises(SystemExit, match="not a proven loop of carddemo-menu"):
        pl.adopt("carddemo-menu", tmp_path)


def test_a_baseline_whose_java_did_not_build_is_not_reused(tmp_path):
    assert not pl._baseline_built(tmp_path / "none")
    (tmp_path / "report.json").write_text(json.dumps({"java_failed": True}))
    assert not pl._baseline_built(tmp_path)
    (tmp_path / "report.json").write_text(json.dumps({"java_failed": False, "proven": False}))
    assert pl._baseline_built(tmp_path)  # it built and ran (the stub is not proven): reusable
