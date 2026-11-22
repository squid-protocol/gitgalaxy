"""#7155: negative controls for java-compile and assess-from-pypi. Each is fed a planted failure and must go red.

The build, the generation and the install are stubbed, so these prove each gate's decision (its exit code), not the job
around it. A clean input is the positive control. The referee-panel control is in
tests/cobol_mainframe/test_referee_panel_runner.py.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
import java_target_matrix as jtm  # noqa: E402


def _load_assess():
    spec = importlib.util.spec_from_file_location(
        "check_assess_install_7155", REPO / "scripts" / "check_assess_install.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


assess = _load_assess()


def _run_matrix(monkeypatch, tmp_path, built, *extra):
    """java_target_matrix.main() with generation and the build stubbed; `built` maps a project dir name to (ok, errors)."""
    origin = Path(importlib.util.find_spec("gitgalaxy").origin).resolve()
    monkeypatch.setattr(jtm, "REPO_ROOT", origin.parents[1])
    monkeypatch.setattr(jtm, "refactor", lambda corpus, work, scan=False, scan_cache=None: tmp_path)

    def fake_generate(clean, name, config, work, header=None):
        project = tmp_path / f"java_{name}"
        project.mkdir(exist_ok=True)
        return project

    monkeypatch.setattr(jtm, "generate", fake_generate)
    monkeypatch.setattr(jtm, "build", lambda project, version, m2: built(project.name))
    summary = tmp_path / "summary.md"
    argv = ["java_target_matrix.py", str(tmp_path), "--work", str(tmp_path / "w"), "--summary", str(summary), *extra]
    monkeypatch.setattr(sys, "argv", argv)
    return jtm.main(), summary


def test_java_compile_goes_red_when_one_config_does_not_build(monkeypatch, tmp_path, capsys):
    rc, summary = _run_matrix(monkeypatch, tmp_path, lambda name: (True, ""))
    assert rc == 0  # positive control: every config compiles
    planted = f"java_{next(iter(jtm.MATRIX))}"
    rc, summary = _run_matrix(
        monkeypatch,
        tmp_path,
        lambda name: (False, "Foo.java:1: error: cannot find symbol") if name == planted else (True, ""),
    )
    assert rc == 1
    assert "FAIL" in capsys.readouterr().out
    assert "| FAIL -- Foo.java:1: error: cannot find symbol |" in summary.read_text(encoding="utf-8").replace("`", "")


def test_java_compile_goes_red_when_a_project_was_not_generated(monkeypatch, tmp_path):
    monkeypatch.setattr(jtm, "build", lambda project, version, m2: (True, ""))
    origin = Path(importlib.util.find_spec("gitgalaxy").origin).resolve()
    monkeypatch.setattr(jtm, "REPO_ROOT", origin.parents[1])
    monkeypatch.setattr(
        sys, "argv", ["x", str(tmp_path), "--work", str(tmp_path / "w"), "--generated", str(tmp_path / "none")]
    )
    assert jtm.main() == 1  # a missing project is a failure, never a pass


def test_java_compile_refuses_an_engine_imported_from_another_checkout(monkeypatch, tmp_path):
    monkeypatch.setattr(jtm, "REPO_ROOT", tmp_path / "elsewhere")
    monkeypatch.setattr(sys, "argv", ["x", str(tmp_path), "--work", str(tmp_path / "w")])
    assert jtm.main() == 2


def test_java_compile_same_as_exits_1_when_the_generated_java_changed(monkeypatch, tmp_path):
    verdict = {"value": (True, "same")}
    monkeypatch.setattr(jtm, "same_as", lambda *a, **k: verdict["value"])
    monkeypatch.setattr(sys, "argv", ["x", str(tmp_path), "--work", str(tmp_path / "w"), "--same-as", str(tmp_path)])
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    assert jtm.main() == 0
    verdict["value"] = (False, "Foo.java differs")
    assert jtm.main() == 1  # changed: the compile must run


def test_assess_install_check_records_a_failed_assertion():
    failures = []
    assess.check(True, "fine", failures)
    assert failures == []
    assess.check(False, "planted", failures)
    assert failures == ["planted"]


def test_assess_install_exits_2_when_there_is_nothing_to_install(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(sys, "argv", ["x", "--wheel-dir", str(tmp_path)])  # no wheel in it
    assert assess.main() == 2
    assert "no gitgalaxy wheel" in capsys.readouterr().out


def test_assess_install_refuses_pypi_with_a_local_wheel(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["x", "--from-pypi", "1.0.0", "--wheel-dir", str(tmp_path)])
    with pytest.raises(SystemExit) as exc:
        assess.main()
    assert exc.value.code == 2


def _fake_run(assess_rc=0, report="{}", install_rc=0, with_command=True):
    import subprocess

    def fake(cmd, cwd, env):
        text = " ".join(map(str, cmd))
        out = ""
        if "-m venv" in text:
            bindir = Path(cmd[-1]) / ("Scripts" if assess.os.name == "nt" else "bin")
            bindir.mkdir(parents=True)
            if with_command:
                (bindir / ("gitgalaxy.exe" if assess.os.name == "nt" else "gitgalaxy")).write_text("", encoding="utf-8")
        elif " assess " in f" {text} ":
            Path(cmd[cmd.index("--out") + 1]).write_text(report, encoding="utf-8")
            return subprocess.CompletedProcess(cmd, assess_rc, stdout="", stderr="")
        elif "pip install" in text:
            return subprocess.CompletedProcess(cmd, install_rc, stdout="", stderr="no matching distribution")
        elif "gitgalaxy.__file__" in text:
            out = "/elsewhere/site-packages/gitgalaxy/__init__.py"
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")

    return fake


def test_assess_install_exits_2_when_the_published_package_does_not_install(monkeypatch):
    monkeypatch.setattr(assess, "run", _fake_run(install_rc=1))
    monkeypatch.setattr(assess.time, "sleep", lambda s: None)
    monkeypatch.setattr(sys, "argv", ["x", "--from-pypi", "9.9.9"])
    assert assess.main() == 2


def test_assess_install_exits_1_on_a_bad_report_and_when_the_command_is_missing(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["x", "--from-pypi", "9.9.9"])
    monkeypatch.setattr(assess.time, "sleep", lambda s: None)
    monkeypatch.setattr(assess, "run", _fake_run(with_command=False))
    assert assess.main() == 1  # a release with no `gitgalaxy` command
    monkeypatch.setattr(assess, "run", _fake_run(assess_rc=1, report=""))
    assert assess.main() == 1  # assess failed and wrote no report
    out = capsys.readouterr().out
    assert "FAIL gitgalaxy assess exits 0" in out and "FAIL the report was written" in out
    monkeypatch.setattr(
        assess, "run", _fake_run(report='{"tool_version": "0.0.1", "totals": {"programs": 0}, "programs": []}')
    )
    assert assess.main() == 1  # wrong version and counts
    assert "tool_version is '0.0.1', published '9.9.9'" in capsys.readouterr().out
