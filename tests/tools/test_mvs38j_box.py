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


def test_sysgen_says_it_is_not_automated():
    r = _run("sysgen")
    assert r.returncode == 3
    assert "not automated" in r.stderr


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
