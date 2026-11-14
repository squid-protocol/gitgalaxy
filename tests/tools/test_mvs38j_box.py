"""MVS 3.8J oracle box (#8414): the script's pins and refusals; nothing here builds, downloads or needs docker."""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="a bash script for the Linux box")

BOX = Path(__file__).resolve().parent / "box" / "mvs38j"
SCRIPT = BOX / "mvs38j.sh"


def _run(*args):
    return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, timeout=30)  # noqa: S603, S607


def test_no_argument_prints_usage_and_exits_2():
    r = _run()
    assert r.returncode == 2
    assert "mvs38j.sh" in r.stderr


def test_unknown_subcommand_is_refused():
    assert _run("bogus").returncode == 2


def test_bare_sysgen_is_refused_with_the_automated_stage_named():
    r = _run("sysgen")
    assert r.returncode == 3
    assert "only 'sysgen starter|smp1|smp2' are automated" in r.stderr


def test_every_tape_pin_is_an_md5():
    pins = re.findall(r'"(\S+\.tar\.gz) ([0-9a-f]+)"', SCRIPT.read_text())
    assert [p[0] for p in pins] == [
        "vs2StarterTapes.tar.gz",
        "vs2DistributionTapes.tar.gz",
        "mvsInstallationResources.tar.gz",
    ]
    assert all(len(m) == 32 for _, m in pins)


def test_the_box_never_names_a_turnkey_or_zos_image():
    text = (SCRIPT.read_text() + (BOX / "Dockerfile").read_text()).lower()
    assert not re.search(r"tk[45]-?\.|turnkey.*\.(zip|tar)|zos.*hercules", text)


def test_the_hyperion_tag_is_pinned():
    assert re.search(r"ARG HYPERION_TAG=Release_\d+\.\d+", (BOX / "Dockerfile").read_text())


def test_dasd_refuses_an_unknown_stage_and_a_missing_one():
    assert _run("dasd", "bogus").returncode == 2
    assert _run("dasd").returncode == 2


def test_dasd_and_stage_refuse_an_unstaged_work_dir(tmp_path):
    env = {"MVS38J_WORK": str(tmp_path), "PATH": "/usr/bin:/bin"}
    for args in (("dasd", "starter"), ("stage",)):
        r = subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, timeout=30, env=env)  # noqa: S603, S607
        assert r.returncode == 1
        assert "first" in r.stderr


# --- sysgen.py: the console driver's pure parts (no docker, no Hercules) ---

sys.path.insert(0, str(BOX))
import sysgen  # noqa: E402


def test_smp_failed_steps_bounds_by_listed_expectation():
    ok = {"job": "J", "step": "A", "executed": True, "cond_code": 8}
    exp = {("J", "A"): (8, "why")}
    assert sysgen.smp_failed_steps([ok], exp) == []
    assert sysgen.smp_failed_steps([ok], {}) == [ok]  # unlisted CC 8 fails
    assert sysgen.smp_failed_steps([{**ok, "cond_code": 4}], exp) != []  # a listed step must match exactly
    assert sysgen.smp_failed_steps([{**ok, "executed": False, "cond_code": None}], exp) != []


def test_smp2_expected_has_a_reason_for_each_entry():
    assert all(cc > 0 and reason for cc, reason in sysgen.SMP2_EXPECTED.values())


PRINTER = """\
 IEF142I SMP4P44 S1 - STEP WAS EXECUTED - COND CODE 0000
 IEF142I SMP4P44 LK S3 - STEP WAS EXECUTED - COND CODE 0004
 IEF272I JOBX STEP2 - STEP WAS NOT EXECUTED.
 IEF142I JOBX GO PROC1 - STEP WAS EXECUTED - COND CODE 0012
 IEF142I OTHER S1 - STEP WAS EXECUTED - COND CODE 0000
"""


def test_step_results_reads_executed_and_not_executed_steps():
    r = sysgen.step_results(PRINTER, "JOBX")
    assert [(x["step"], x["executed"], x["cond_code"]) for x in r] == [("STEP2", False, None), ("GO", True, 12)]
    assert r[1]["procstep"] == "PROC1" and r[0]["procstep"] is None


def test_step_results_all_and_job_filter_ignore_case():
    assert len(sysgen.step_results(PRINTER)) == 5
    assert [x["job"] for x in sysgen.step_results(PRINTER, "smp4p44")] == ["SMP4P44", "SMP4P44"]
    assert sysgen.step_results("no messages here\n") == []


def test_check_expected_flags_wrong_missing_and_unexecuted_steps():
    r = sysgen.step_results(PRINTER)
    assert sysgen.check_expected(r, {"S1": 0, "LK": 4}) == []
    assert sysgen.check_expected(r, {"LK": 0, "NOPE": 0, "STEP2": 0}) == ["LK", "NOPE", "STEP2"]


def test_condcode_cli_exit_code_follows_expectations(tmp_path):
    f = tmp_path / "prt00e.txt"
    f.write_text(PRINTER)
    ok = subprocess.run(
        [sys.executable, "-I", str(BOX / "sysgen.py"), "condcode", str(f), "SMP4P44", "--expect", "S1=0"],
        capture_output=True,
        text=True,
        timeout=30,
    )  # noqa: S603
    bad = subprocess.run(
        [sys.executable, "-I", str(BOX / "sysgen.py"), "condcode", str(f), "SMP4P44", "--expect", "S1=8"],
        capture_output=True,
        text=True,
        timeout=30,
    )  # noqa: S603
    assert (ok.returncode, bad.returncode) == (0, 1)
    assert "unexpected: S1" in bad.stderr


def test_starter_refuses_an_unstaged_work_dir(tmp_path):
    with pytest.raises(sysgen.SysgenError, match="stage and dasd starter"):
        sysgen.starter(tmp_path, "img", "name")


class _FakeHercules(sysgen.Hercules):
    """A Hercules whose log is fed by the test: no process."""

    def __init__(self, lines=()):
        super().__init__("/w", "conf/x.cnf", "img", "n")
        self.lines = list(lines)
        self.sent = []

    def send(self, command):
        self.sent.append(command)


def test_wait_matches_since_and_raises_on_a_standalone_error_and_on_timeout():
    h = _FakeHercules(["old IBC105A", "now IBC105A  DEFINE INPUT DEVICE"])
    assert h.wait(r"IBC105A", 1, since=1).startswith("now")
    with pytest.raises(sysgen.SysgenError, match="CONTROL STATEMENT ERROR"):
        _FakeHercules(["x /IBC102A  CONTROL STATEMENT ERROR."]).wait(r"never", 1)
    with pytest.raises(sysgen.SysgenError, match="timed out"):
        _FakeHercules(["quiet"]).wait(r"never", 0.05)


def test_the_starter_plan_covers_both_volumes_with_distinct_readers_and_tapes():
    assert [v[0] for v in sysgen.STARTER_VOLUMES] == ["START1", "SPOOL0"]
    readers = [r for v in sysgen.STARTER_VOLUMES for r in v[2:]]
    assert sorted(readers) == ["00c", "00d", "00e", "00f"]
    assert {v[1] for v in sysgen.STARTER_VOLUMES} == {"280", "281"}


def test_sysgen_subcommand_refuses_a_stage_that_is_not_automated():
    r = _run("sysgen", "stage1")
    assert r.returncode == 3 and "only 'sysgen starter|smp1|smp2'" in r.stderr


# --- console.py: the telnet 3215 client, against an in-process fake server ---

import socket  # noqa: E402
import threading  # noqa: E402

import console  # noqa: E402

IAC, DO, WILL, WONT, DONT = console.IAC, console.DO, console.WILL, console.WONT, console.DONT


def test_strip_telnet_answers_negotiation_and_keeps_text_across_chunks():
    st = {}
    text, rep = console.strip_telnet(bytes([IAC, DO, 24, IAC, WILL, 1, IAC, DO, 3]) + b"HELLO", st)
    assert text == b"HELLO"
    assert rep == bytes([IAC, WILL, 24, IAC, console.DO, 1, IAC, WILL, 3])
    # a sequence split over two reads, an escaped 255 and a subnegotiation
    t1, r1 = console.strip_telnet(b"a" + bytes([IAC]), st)
    t2, r2 = console.strip_telnet(
        bytes([DO, 99]) + b"b" + bytes([IAC, IAC]) + bytes([IAC, 250, 24, 1, IAC, 240]) + b"c", st
    )
    assert (t1, r1) == (b"a", b"")
    ans = bytes([IAC, 250, 24, 0]) + b"ANSI" + bytes([IAC, 240])  # SB TERMINAL-TYPE SEND is answered IS ANSI
    assert (t2, r2) == (b"b\xffc", bytes([IAC, WONT, 99]) + ans)


def _serve(script):
    """Listen on a free loopback port; the fake Hercules sends `script` bytes after connect and records what it gets."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    got = []

    def run():
        c, _ = srv.accept()
        c.sendall(script)
        c.settimeout(3)
        try:
            while True:
                d = c.recv(4096)
                if not d:
                    break
                got.append(d)
                if b"r 0,clpa" in b"".join(got):
                    c.sendall(b"\r\n$HASP426 SPECIFY OPTIONS - JES2\r\n")
        except OSError:
            pass
        c.close()
        srv.close()

    threading.Thread(target=run, daemon=True).start()
    return srv.getsockname()[1], got


def test_console_waits_on_a_prompt_with_no_newline_and_sends_crlf_lines():
    port, got = _serve(bytes([IAC, DO, 24]) + b"HHC01603I hi\r\n 00 IEA101A SPECIFY SYSTEM PARAMETERS")
    con = console.Console(port=port, connect_timeout=5).connect()
    try:
        assert "IEA101A" in con.wait(r"IEA101A", 5)  # the prompt has no trailing newline
        con.send("r 0,clpa")
        assert "HASP426" in con.wait(r"\$HASP426", 5)
        assert b"".join(got).startswith(bytes([IAC, WILL, 24]))
        assert b"r 0,clpa\r\n" in b"".join(got)
    finally:
        con.close()


def test_console_wait_times_out_and_connect_refuses_a_dead_port():
    port, _ = _serve(b"quiet\r\n")
    con = console.Console(port=port, connect_timeout=5).connect()
    try:
        with pytest.raises(console.ConsoleError, match="timed out"):
            con.wait(r"never", 0.2)
    finally:
        con.close()
    dead = socket.socket()
    dead.bind(("127.0.0.1", 0))
    dead_port = dead.getsockname()[1]
    dead.close()  # nothing listens here now
    with pytest.raises(console.ConsoleError, match="no console"):
        console.Console(port=dead_port, connect_timeout=0.1).connect()


# --- sysgen.py: the SMP stage's parsing and refusals ---


def test_mount_requests_are_answered_once_with_devinit_and_a_reply(tmp_path):
    con = console.Console()
    con.lines = ["*IEC501A M 170,SMPTAP,SL,6250 BPI,", " IEC501A SMP4P44,S1", "*IEC501A M 170,OTHER,SL,X"]
    sent, replies, seen = [], [], set()
    con.send = replies.append
    sysgen.answer_mounts(sent.append, con, 0, {"SMPTAP": "tape/smp.het", "OTHER": "tape/o.het"}, seen)
    sysgen.answer_mounts(sent.append, con, 0, {"SMPTAP": "x", "OTHER": "x"}, seen)  # already answered: no repeat
    assert sent == ["devinit 170 tape/smp.het", "devinit 170 tape/o.het"]
    assert replies == []  # a mount is satisfied by readying the drive: no reply
    con.lines = ["*IEC501A M 171,NOPE,SL"]
    with pytest.raises(sysgen.SysgenError, match="--tape NOPE=FILE"):
        sysgen.answer_mounts(sent.append, con, 0, {}, set())


def test_a_device_name_ask_is_answered_with_the_configs_tape_unit(tmp_path):
    (tmp_path / "conf").mkdir()
    (tmp_path / "conf" / "s.cnf").write_text("0150 3350 dasd/x\n0170 3420 *\n0171 3420 *\n")
    assert sysgen.tape_unit(tmp_path, "conf/s.cnf") == "170"
    con = console.Console()
    con.lines = ["*02 IEF238D SMP4P44 - REPLY DEVICE NAME OR 'CANCEL'.", "*03 IEC507D REPLY 'U'-USE OR 'M'-UNLOAD"]
    replies, seen = [], set()
    con.send = replies.append
    sysgen.answer_mounts(lambda c: None, con, 0, {}, seen, "170")
    sysgen.answer_mounts(lambda c: None, con, 0, {}, seen, "170")
    assert replies == ["r 02,170", "r 03,u"]


def test_smp2_console_asks_are_answered_once_and_default_tapes_resolve():
    con = console.Console()
    con.lines = [
        "*02 IEH841D 148    CONFIRM REQUEST TO INITIALIZE",
        "*03 IEH841D 149    CONFIRM REQUEST TO INITIALIZE",
        "*IEF233A M 170,MVS38J,,SMPJOB01,SMP",  # smp2 mounts come as IEF233A, smp1's as IEC501A
        "*IEC501A M 170,PTFS20,SL,6250 BPI,",
    ]
    replies, sent, seen = [], [], set()
    con.send = replies.append
    for _ in range(2):  # the second pass must not repeat any answer
        sysgen.answer_mounts(sent.append, con, 0, {}, seen)
    assert replies == ["r 02,u", "r 03,u"]
    assert sent == ["devinit 170 tape/zdlib1.het", "devinit 170 tape/ptfs.het"]
    assert sysgen.COMMAND_ASK_RE.search("*01 IEF166D REPLY Y/N TO EXECUTE/SUPPRESS COMMAND").group(1) == "01"
    sysgen.answer_mounts(sent.append, con, 0, {"PTFS20": "tape/other.het"}, set())  # --tape overrides the default
    assert sent[-1] == "devinit 170 tape/other.het"


def test_a_terminated_utility_in_the_printer_text_is_refused():
    line = "IEH824I  ANALYZE TERMINATED. DEVICE NOT OFF-LINE AND CONFIRMED. TODD= 148"
    assert sysgen.PRINTER_REFUSED_RE.search(line)
    assert not sysgen.PRINTER_REFUSED_RE.search("IEH839I  HIGHEST RETURN CODE ENCOUNTERED WAS 08")


def test_a_tape_keep_message_is_not_a_console_error():
    assert not sysgen.SMP_CONSOLE_ERRORS.search(" IEC502E K 170,MVS38J,SL,SMP4P44,S2")
    assert sysgen.SMP_CONSOLE_ERRORS.search(" IEC145E I/O ERROR 170")


def test_smp1_conf_gains_the_target_volumes_smp2_defines(tmp_path):
    (tmp_path / "conf").mkdir()
    (tmp_path / "conf" / "smp1.cnf").write_text("0150 3330 dasd/start1.3330\n0148 3350 dasd/already\n")
    (tmp_path / "conf" / "smp2.cnf").write_text(
        "0148 3350 dasd/smp000.3350\n0149 3350 dasd/work00.3350\n014A 3350 dasd/work01.3350\n0150 3330 x\n"
    )
    out = sysgen.with_target_volumes(tmp_path, "conf/smp1.cnf")
    assert out == "conf/smp1-gg.cnf"
    lines = (tmp_path / out).read_text().splitlines()
    assert lines == [
        "0150 3330 dasd/start1.3330",
        "0148 3350 dasd/already",
        "0149 3350 dasd/work00.3350",
        "014A 3350 dasd/work01.3350",
    ]


def test_printer_file_reads_the_first_1403_and_smp_refuses_an_unstaged_work_dir(tmp_path):
    (tmp_path / "conf").mkdir()
    (tmp_path / "conf" / "smp1.cnf").write_text("000C 3505 localhost:3505 sockdev\n000E 1403 prt/prt00e.txt crlf\n")
    assert sysgen.printer_file(tmp_path, "conf/smp1.cnf") == tmp_path / "prt/prt00e.txt"
    (tmp_path / "conf" / "none.cnf").write_text("001F 3215\n")
    with pytest.raises(sysgen.SysgenError, match="no 1403"):
        sysgen.printer_file(tmp_path, "conf/none.cnf")
    with pytest.raises(sysgen.SysgenError, match="smp2.cnf missing"):
        sysgen.smp_stage(tmp_path, "img", "n", "smp2", {})
    with pytest.raises(sysgen.SysgenError, match="smpjob"):
        sysgen.smp_stage(tmp_path, "img", "n", "smp1", {})


def test_the_console_port_is_published_on_loopback_only():
    h = sysgen.Hercules("/w", "conf/x.cnf", "img", "n", console_port=3270)
    assert h.console_port == 3270
    assert 'f"127.0.0.1:{self.console_port}:3270"' in (BOX / "sysgen.py").read_text()


def test_run_without_a_deck_is_a_usage_error():
    assert _run("run").returncode == 2


def test_run_with_a_missing_deck_is_refused(tmp_path):
    r = _run("run", str(tmp_path / "nope.jcl"))
    assert r.returncode == 1
    assert "no deck" in r.stderr


def test_run_without_a_generated_system_names_the_conf(tmp_path):
    deck = tmp_path / "d.jcl"
    deck.write_text("//J JOB\n")
    env = {**os.environ, "MVS38J_WORK": str(tmp_path)}
    r = subprocess.run(["bash", str(SCRIPT), "run", str(deck)], capture_output=True, text=True, timeout=30, env=env)  # noqa: S603, S607
    assert r.returncode == 1
    assert "conf/mvs.conf" in r.stderr


def test_run_takes_the_printer_from_the_first_1403_in_the_conf(tmp_path):
    (tmp_path / "conf").mkdir()
    (tmp_path / "conf" / "mvs.conf").write_text("00c 3505 sockdev ebcdic\n00e 1403 prt/prt00e.txt crlf\n")
    deck = tmp_path / "d.jcl"
    deck.write_text("not a job card\n")
    env = {**os.environ, "MVS38J_WORK": str(tmp_path)}
    r = subprocess.run(["bash", str(SCRIPT), "run", str(deck)], capture_output=True, text=True, timeout=30, env=env)  # noqa: S603, S607
    # the runner is reached (it refuses a deck with no JCL card) and never touched a socket
    assert r.returncode != 0
    assert "does not start with a JCL card" in r.stderr or "first card" in r.stderr
