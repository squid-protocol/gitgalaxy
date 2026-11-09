"""#8185: the Evidence Refresh `refresh` job uploads the survey cache as the `blockers-survey` artifact. A corpus file
named with a character upload-artifact refuses (`>>Icon.png` in an estate's doc images) failed the upload, so
publish-blockers found no artifact. The class: any file name holding one of ` " : < > | * ? CR LF `. The test runs the
workflow's own rsync line over a tree with each of them."""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "evidence-refresh.yml"
REFUSED = ['"', ":", "<", ">", "|", "*", "?", "\r", "\n"]


def _rsync_line():
    lines = [ln.strip() for ln in WORKFLOW.read_text(encoding="utf-8").splitlines()]
    hits = [ln for ln in lines if ln.startswith("rsync -a --exclude src") and "census-cache" in ln]
    assert len(hits) == 1
    return hits[0]


def test_the_survey_copy_leaves_out_names_the_artifact_refuses():
    line = _rsync_line()
    for ch in REFUSED:
        assert ch in line or "$'\\r'" in line or "$'\\n'" in line, ch
    assert re.search(r"--exclude '\*\[[^\]]*\]\*'", line)


@pytest.mark.skipif(
    sys.platform != "linux" or shutil.which("rsync") is None or shutil.which("bash") is None,
    reason="needs rsync and bash on linux (bash is the WSL launcher on Windows, #7312)",
)
def test_every_refused_character_is_dropped_and_other_names_survive(tmp_path):
    sha = "abc"
    src = tmp_path / "scratch" / "census-cache" / sha / "before-b" / "estate" / "doc"
    src.mkdir(parents=True)
    kept = ["Icon.png", "Icon.PNG", "a b.png", "a-b_c.1.png", "nonasciié.png"]
    for name in kept:
        (src / name).write_text("x")
    dropped = []
    for i, ch in enumerate(REFUSED):
        name = f"n{i}{ch}x.png"
        (src / name).write_text("x")
        dropped.append(name)
    (src.parent / "src").mkdir()
    (src.parent / "src" / "t.java").write_text("x")
    out = tmp_path / "temp" / "blockers-cache" / "census-cache"
    out.mkdir(parents=True)
    env = {
        "GG_SCRATCH": str(tmp_path / "scratch"),
        "SHA": sha,
        "RUNNER_TEMP": str(tmp_path / "temp"),
        "PATH": "/usr/bin:/bin",
    }
    subprocess.run(["bash", "-c", _rsync_line()], check=True, env=env)
    got = {p.name for p in (out / sha / "before-b" / "estate" / "doc").iterdir()}
    assert got == set(kept)
    assert not (out / sha / "before-b" / "estate" / "src").exists()
