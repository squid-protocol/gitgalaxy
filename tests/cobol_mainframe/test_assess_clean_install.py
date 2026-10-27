"""#4726 `gitgalaxy assess` from the built wheel on a clean machine: the wheel is installed into a fresh virtual
environment with no extras and no PYTHONPATH, and the installed console script runs on an estate.

A plain install has no COBOL grammar, so the translate-only dry run is skipped with a notice (not every program
reported refused) and the report stays schema-valid, with no source text in it. No `tree_sitter_language_pack`
importorskip here: this is the test for its absence."""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from gitgalaxy.tools.readiness import schema as SC

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_assess as TA  # noqa: E402  (sibling helper: the source-text check)

REPO = Path(__file__).resolve().parents[2]
CORPORA = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", REPO / ".mainframe_corpora"))
MARK = "ZQXCLEAN"
PROGRAM = (
    "       IDENTIFICATION DIVISION.\n"
    "       PROGRAM-ID. CLEAN1.\n"
    f"      * {MARK} COMMENT\n"
    "       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n"
    f"       01 WS-{MARK}-NAME PIC X(20) VALUE '{MARK} LITERAL'.\n"
    "       PROCEDURE DIVISION.\n"
    f"       {MARK}-PARA.\n"
    f"           DISPLAY WS-{MARK}-NAME.\n"
    "           GOBACK.\n"
)


def _run(cmd: list[str], cwd: Path, env: dict[str, str], timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, env=env, check=False, timeout=timeout)  # noqa: S603


@pytest.fixture(scope="module")
def clean(tmp_path_factory):
    """(venv bin dir, a neutral working directory, the clean environment)."""
    base = tmp_path_factory.mktemp("clean")
    wheels = base / "wheels"
    # setuptools from this environment when it has it (no network); otherwise pip's isolated build fetches it
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "VIRTUAL_ENV", "PYTHONHOME")}
    env["GITGALAXY_LICENSE_KEY"] = "COMMUNITY_FREE_TIER"
    isolation = ["--no-build-isolation"] if importlib.util.find_spec("setuptools") else []
    built = _run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", *isolation, "-w", str(wheels), str(REPO)],
        base,
        env,
    )
    assert built.returncode == 0, built.stderr[-3000:]
    wheel = next(wheels.glob("gitgalaxy-*.whl"))
    venv = base / "venv"
    made = _run([sys.executable, "-m", "venv", str(venv)], base, env)
    assert made.returncode == 0, made.stderr[-2000:]
    bindir = venv / ("Scripts" if os.name == "nt" else "bin")
    py = str(bindir / ("python.exe" if os.name == "nt" else "python"))
    done = _run([py, "-m", "pip", "install", "--no-index", "--no-deps", str(wheel)], base, env)
    assert done.returncode == 0, done.stderr[-3000:]
    work = base / "work"
    work.mkdir()
    return py, bindir, work, env


def _probe(py: str, work: Path, env: dict[str, str], code: str) -> str:
    res = _run([py, "-I", "-c", code], work, env)
    assert res.returncode == 0, res.stderr[-2000:]
    return res.stdout.strip()


def _assess(clean, estate: Path, *extra: str) -> tuple[subprocess.CompletedProcess, str]:
    py, bindir, work, env = clean
    out = work / "report.json"
    exe = str(bindir / ("gitgalaxy.exe" if os.name == "nt" else "gitgalaxy"))
    res = _run([exe, "assess", str(estate), "--out", str(out), *extra], work, env)
    return res, out.read_text(encoding="utf-8") if out.exists() else ""


@pytest.mark.slow(reason="#4726: builds the wheel, makes a venv and installs it, then runs the installed command")
def test_the_installed_package_is_the_wheel_and_has_no_translator(clean):
    py, _bindir, work, env = clean
    where = _probe(py, work, env, "import gitgalaxy; print(gitgalaxy.__file__)")
    assert "site-packages" in where and Path(REPO) not in Path(where).parents
    has = _probe(py, work, env, "import importlib.util as u; print(u.find_spec('tree_sitter_language_pack') is None)")
    assert has == "True"


@pytest.mark.slow(reason="#4726: runs the installed gitgalaxy assess on a planted estate, plain and redacted")
def test_clean_install_assesses_an_estate_without_the_translator(clean, tmp_path):
    estate = tmp_path / "estate"
    estate.mkdir()
    (estate / "CLEAN1.cbl").write_text(PROGRAM)
    for extra in ((), ("--redact",)):
        res, text = _assess(clean, estate, *extra)
        assert res.returncode == 0, res.stderr[-3000:]
        assert "translate-only dry run skipped: pip install gitgalaxy[translator]" in res.stderr
        report = json.loads(text)
        assert SC.validate(report) == []
        assert report["totals"]["programs"] == 1
        assert "translation" not in report["totals"]
        assert all("translation" not in r for r in report["programs"])
        assert MARK not in text and MARK not in res.stdout + res.stderr
        if extra:
            assert "CLEAN1" not in text


@pytest.mark.slow(reason="#4726: runs the installed gitgalaxy assess on a burned estate, plain and redacted")
@pytest.mark.parametrize("name", TA.BURNED)
def test_clean_install_assesses_every_burned_estate(clean, name):
    """The installed command on each burned estate: schema-valid, no estate source text, no program name when redacted."""
    estate = CORPORA / name
    if not estate.is_dir():
        pytest.skip(f"the {name} corpus is not available (GITGALAXY_MAINFRAME_CORPORA)")
    inv = TA._inventory(name)
    for extra, allowed in ((), TA._program_names(inv)), (("--redact",), set()):
        res, text = _assess(clean, estate, *extra)
        assert res.returncode == 0, res.stderr[-3000:]
        report = json.loads(text)
        assert SC.validate(report) == []
        assert report["totals"]["programs"] > 0
        assert all("translation" not in r for r in report["programs"])
        TA.assert_no_source_text(report, estate, allowed)
        if extra:
            assert all(r["name"].startswith("P-") for r in report["programs"])
