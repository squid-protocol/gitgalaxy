"""#8625 slice 2: a real scan (the CLI, nothing hand-built) counts mainframe credential shapes as `hardcoded_secrets`.

Planted case and near-miss per member type: JCL, PROC (`.prc` and `.proc`), REXX, CLIST (`.clist`, slice 3) and
embedded Db2. Every value is invented. Extensionless members route by directory or body (slice 4, `test_extensionless_rexx_clist_8625.py`).
"""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from gitgalaxy.core.aperture import ApertureFilter
from gitgalaxy.security.mainframe_secrets import mainframe_secret_sites
from gitgalaxy.security.security_lens import SecurityLens
from gitgalaxy.standards.gitgalaxy_config import APERTURE_CONFIG
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

PW = "PASS" + "WORD"  # split so no scanner reads this file as a leak
SQL_LEAK = "       EXEC SQL CONNECT TO PRODDB USER BATCH1 USING 'Xy7pq2' END-EXEC.\n"
SQL_OK = "       EXEC SQL CONNECT TO :LOC USER :UID USING :PWD END-EXEC.\n"
FTP = "//PAYPROC  PROC\n//S1 EXEC PGM=FTP\n//INPUT DD *\n10.1.2.3\n"

MEMBERS = {
    "leak_job.jcl": (f"//PAYJOB   JOB (ACCT),'PAY',CLASS=A,{PW}=S3CR3T1\n//STEP1 EXEC PGM=IEFBR14\n", 1),
    "leak_proc.proc": (FTP + "USER BATCH1 Xy7pq2\n/*\n", 1),
    "leak_proc.prc": (FTP + "PASS Xy7pq2\n/*\n", 1),
    "leak_exec.rexx": ("/* REXX */\nuserid = 'BATCH1'\npw = 'Xy7pq2'\n", 1),
    "leak_connect.rexx": ('/* REXX */\naddress tso\n"db2 connect to PRODDB user batch1 using Xy7pq2"\n', 1),
    "leak_sql.cbl": ("       IDENTIFICATION DIVISION.\n" + SQL_LEAK, 1),
    "leak_cmd.clist": ("/* CLIST */\nSET &USERID = BATCH1\nSET &PW = Xy7pq2\nALLOC FI(IN) DA(&DSN)\n", 1),
    "ok_job.jcl": ("//PAYJOB   JOB (ACCT),'PAY',CLASS=A,PASSWORD=&PW\n//STEP1 EXEC PGM=IEFBR14\n", 0),
    "ok_comment.jcl": (f"//* SET {PW}=XXXXXXX BEFORE SUBMIT\n//STEP1 EXEC PGM=IEFBR14\n", 0),
    "ok_proc.proc": (FTP + "USER BATCH1 &FTPPW\n/*\n", 0),
    "ok_exec.rexx": ("/* REXX */\nuserid = 'BATCH1'\npw = value('PWENV')\n", 0),
    "ok_cmd.clist": ("/* CLIST */\nSET &USERID = BATCH1\nSET &PW = &SYSPWD\n/* SET &PW = XXXXXXX */\n", 0),
    "ok_sql.cbl": ("       IDENTIFICATION DIVISION.\n" + SQL_OK, 0),
}


@pytest.fixture(scope="module")
def scan_counts(tmp_path_factory):
    repo = tmp_path_factory.mktemp("repo")
    out = tmp_path_factory.mktemp("out")
    for name, (text, _) in MEMBERS.items():
        (repo / name).write_text(text, encoding="utf-8")
    env = dict(os.environ, GITGALAXY_DISABLE_GIT_HISTORY="1", GITGALAXY_LICENSE_KEY="COMMUNITY_FREE_TIER")
    r = subprocess.run(
        [sys.executable, "-m", "gitgalaxy.galaxyscope", str(repo), "--db-only", "--output", str(out)],
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert r.returncode == 0, r.stderr[-2000:]
    db = next(Path(out).glob("*_galaxy_master.db"))
    with sqlite3.connect(db) as con:
        return dict(con.execute("select file_path, threat_private_info from file_data"))


@pytest.mark.parametrize("name", MEMBERS)
def test_a_planted_member_fires_and_a_near_miss_stays_quiet_in_a_real_scan(scan_counts, name):
    assert name in scan_counts, "the member was not scanned"
    assert scan_counts[name] == MEMBERS[name][1]


def test_the_snippet_names_the_shape_and_never_holds_the_password():
    text = MEMBERS["leak_job.jcl"][0]
    res = SecurityLens().scan_content(text, language="jcl")
    assert res["counts"]["hardcoded_secrets"] == 1
    assert res["snippets"]["hardcoded_secrets"] == ["JCL PASSWORD= [REDACTED]"]
    assert res["sites"]["hardcoded_secrets"] == [[1, mainframe_secret_sites(text)[0][1]]]
    assert "S3CR3T1" not in str(res)


def test_a_language_without_these_shapes_is_untouched():
    text = MEMBERS["leak_job.jcl"][0]
    assert SecurityLens().scan_content(text, language="python")["counts"]["hardcoded_secrets"] == 0
    assert SecurityLens().scan_content(text)["counts"]["hardcoded_secrets"] == 0


@pytest.mark.parametrize("ext", [".jcl", ".prc", ".proc"])
def test_aperture_admits_jcl_and_proc_members(tmp_path, ext):
    (tmp_path / f"m{ext}").write_text(MEMBERS["leak_job.jcl"][0], encoding="utf-8")
    ap = ApertureFilter(root_dir=tmp_path, language_definitions=LANGUAGE_DEFINITIONS, aperture_config=APERTURE_CONFIG)
    ok, _, reason = ap.evaluate_path_integrity(tmp_path / f"m{ext}")
    assert ok, reason


def test_a_clist_member_is_its_own_language_and_the_snippet_never_holds_the_password():
    text = MEMBERS["leak_cmd.clist"][0]
    res = SecurityLens().scan_content(text, language="clist")
    assert res["counts"]["hardcoded_secrets"] == 1
    assert "Xy7pq2" not in str(res)
    assert LANGUAGE_DEFINITIONS["clist"]["extensions"] == [".clist"]


@pytest.mark.parametrize(
    ("rule", "positive", "negative"),
    [
        ("branch", "  IF &RC = 0 THEN", "  SET &IF = 1"),
        ("branch", "  DO WHILE &I < 5", "  SET &DO = 1"),
        ("func_start", "LOOP: SET &I = 1", "  SET &LOOP = 1"),
        ("args", "PROC 1 DSN MEM(ABC)", "  SET &PROC = 1"),
        ("state_mutation", "  SET &X = 1", "  IF &X = 1 THEN"),
        ("io", "  READ &ANSWER", "  SET &READ = 1"),
        ("calls_out", "  %SUBCMD ARG", "  SET &X = 50%"),
        ("calls_out", "  SYSCALL SUBRTN", "  SET &SYSCALL = 1"),
        ("safety", "  ERROR DO", "  SET &ERROR = 1"),
        ("safety_bypasses", "  GOTO DONE", "  SET &GOTO = 1"),
        ("high_risk_execution", "  EXIT CODE(8)", "EXIT: "),
        ("debug_prints", "  WRITE HELLO", "  SET &WRITE = 1"),
        ("cleanup", "  FREE FI(IN)", "  SET &FREE = 1"),
    ],
)
def test_clist_rule_positive_and_negative(rule, positive, negative):
    pattern = LANGUAGE_DEFINITIONS["clist"]["rules"][rule]
    assert pattern.search(positive), (rule, positive)
    assert not pattern.search(negative), (rule, negative)


def test_a_clist_member_routes_to_clist_by_extension():
    from gitgalaxy.standards.language_lens import LanguageDetector

    lang, _, _ = LanguageDetector(LANGUAGE_DEFINITIONS, {}).focus("lib/member.clist", "PROC 1 DSN\nSET &X = 1\n")
    assert lang == "clist"


@pytest.mark.parametrize("hit", ["IKJEFT01", "BPXBATCH", "IRXJCL"])
def test_a_clist_member_running_a_batch_host_program_is_a_vector(hit):
    """#8625: IKJEFT01 / BPXBATCH / IRXJCL run a TSO command or REXX exec from JCL and a CLIST: in scope for clist and
    still not for a language outside the mainframe set."""
    assert SecurityLens._high_risk_applies(hit, "clist")
    assert not SecurityLens._high_risk_applies(hit, "rust")
