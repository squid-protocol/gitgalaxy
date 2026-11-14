"""MVS 3.8J oracle box (#8414): the script's pins and refusals; nothing here builds, downloads or needs docker."""

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
    assert "only 'sysgen starter' is automated" in r.stderr


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


def test_sysgen_subcommand_still_refuses_anything_but_starter():
    r = _run("sysgen", "stage1")
    assert r.returncode == 3 and "only 'sysgen starter'" in r.stderr
