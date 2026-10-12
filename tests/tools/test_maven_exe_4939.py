# ruff: noqa: S101
"""#4939: Windows siblings of #4934 -- the bare `mvn` executable and POSIX-mode argline splitting.

`subprocess` without `shell=True` does not apply PATHEXT, so on Windows (Maven ships `mvn.cmd`) a literal "mvn" in an
argv is not found. Every caller resolves through `maven_exe.mvn_executable`; the guard below fails on a new bare one.
"""

from __future__ import annotations

import ast
import shutil
from pathlib import Path

import equivalence_java as ej
import maven_exe

TOOLS = Path(__file__).resolve().parent


def test_resolves_through_which_so_windows_gets_mvn_cmd(monkeypatch):
    seen = {}

    def fake_which(cmd, path=None):
        seen.update(cmd=cmd, path=path)
        return r"C:\tools\maven\bin\mvn.cmd"

    monkeypatch.setattr(shutil, "which", fake_which)
    assert maven_exe.mvn_executable({"PATH": r"C:\jdk\bin;C:\tools\maven\bin"}) == r"C:\tools\maven\bin\mvn.cmd"
    assert seen == {"cmd": "mvn", "path": r"C:\jdk\bin;C:\tools\maven\bin"}


def test_falls_back_to_the_bare_name_so_the_error_names_it(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda cmd, path=None: None)
    assert maven_exe.mvn_executable({"PATH": ""}) == "mvn"


def test_default_env_is_the_process_path(monkeypatch):
    seen = {}
    monkeypatch.setenv("PATH", "/x/bin")
    monkeypatch.setattr(shutil, "which", lambda cmd, path=None: seen.setdefault("path", path) and "/x/bin/mvn")
    assert maven_exe.mvn_executable() == "/x/bin/mvn"
    assert seen["path"] == "/x/bin"


def test_run_maven_launches_the_resolved_executable(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(ej, "mvn_executable", lambda env=None: r"C:\m\mvn.cmd")
    monkeypatch.setattr(ej, "_run_direct", lambda *a, **k: None)
    monkeypatch.setattr(ej.jtm, "_jdk", lambda v: str(tmp_path / "jdk"))
    monkeypatch.setattr(
        ej.subprocess, "run", lambda cmd, **kw: calls.append(cmd) or ej.subprocess.CompletedProcess(cmd, 0, "", "")
    )
    (tmp_path / "in").mkdir()
    ej.run_maven(tmp_path, tmp_path / "w", tmp_path / "in")
    assert calls and calls[0][0] == r"C:\m\mvn.cmd"


def test_split_argline_keeps_windows_backslashes():
    line = r"-Dequivalence.in=C:\work\in -Dequivalence.out=C:\work\out -Dx=1"
    assert ej.split_argline(line, windows=True) == [
        r"-Dequivalence.in=C:\work\in",
        r"-Dequivalence.out=C:\work\out",
        "-Dx=1",
    ]
    assert ej.split_argline(line, windows=False)[0] == "-Dequivalence.in=C:workin"  # the POSIX-mode damage, for contrast


def test_split_argline_follows_os_name(monkeypatch):
    monkeypatch.setattr(ej.os, "name", "nt")
    assert ej.split_argline(r"-Da=C:\w") == [r"-Da=C:\w"]
    monkeypatch.setattr(ej.os, "name", "posix")
    assert ej.split_argline("-Da='b c' -Dd=1") == ["-Da=b c", "-Dd=1"]


def _bare_mvn(source: str) -> list[int]:
    """Lines where a list/tuple literal starts with the string "mvn" (an argv for subprocess/run helpers)."""
    return sorted(
        n.lineno
        for n in ast.walk(ast.parse(source))
        if isinstance(n, (ast.List, ast.Tuple))
        and n.elts
        and isinstance(n.elts[0], ast.Constant)
        and n.elts[0].value in ("mvn", "mvn.cmd")
    )


def test_no_bare_mvn_argv_in_tests_tools():
    """#4939: resolve through maven_exe.mvn_executable; a literal "mvn" argv is not found on Windows."""
    found = [
        f"{p.relative_to(TOOLS)}:{n}"
        for p in sorted(TOOLS.rglob("*.py"))
        if p.name != Path(__file__).name
        for n in _bare_mvn(p.read_text(encoding="utf-8"))
    ]
    assert found == []


def test_the_guard_catches_a_bare_mvn():
    assert _bare_mvn('subprocess.run(["mvn", "-q"])\nx = ("mvn", "a")\ny = [mvn_executable(), "-q"]\n') == [1, 2]
