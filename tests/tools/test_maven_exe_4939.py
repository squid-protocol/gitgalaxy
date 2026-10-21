# ruff: noqa: S101
"""#4939: Windows siblings of #4934 -- the bare `mvn` executable and POSIX-mode argline splitting.

`subprocess` without `shell=True` does not apply PATHEXT, so on Windows (Maven ships `mvn.cmd`) a literal "mvn" in an
argv is not found. Every caller resolves through `maven_exe.mvn_executable` / `launcher_exe` (#4969: npm); the guard below fails on a
new bare one.
"""

from __future__ import annotations

import ast
import shutil
from pathlib import Path

import callgraph_refs
import equivalence_java as ej
import launcher_exe
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
    assert (
        ej.split_argline(line, windows=False)[0] == "-Dequivalence.in=C:workin"
    )  # the POSIX-mode damage, for contrast


def test_split_argline_follows_os_name(monkeypatch):
    monkeypatch.setattr(ej.os, "name", "nt")
    assert ej.split_argline(r"-Da=C:\w") == [r"-Da=C:\w"]
    monkeypatch.setattr(ej.os, "name", "posix")
    assert ej.split_argline("-Da='b c' -Dd=1") == ["-Da=b c", "-Dd=1"]


# Launchers that ship as `.cmd`/`.bat` shims on Windows (#4939 mvn, #4969 npm and its siblings).
SHIMS = ("mvn", "npm", "npx", "yarn", "pnpm", "gradle", "tsc")
SHIM_ARGV = frozenset(n + ext for n in SHIMS for ext in ("", ".cmd", ".bat"))


def _may_name_shim(source: str) -> bool:
    """Cheap prefilter: a hit needs a constant that is a shim name, so a file with none of the words has no hit and
    is not worth an `ast.parse` (the tree-wide scans were the slowest tests of a CI part, #5610)."""
    return any(n in source for n in SHIMS)


def _shim_sources(root: Path):
    """(path, text) of every .py under root that may name a shim, sorted."""
    for p in sorted(root.rglob("*.py")):
        if p.name != Path(__file__).name and ".venv" not in p.parts:
            text = p.read_text(encoding="utf-8")
            if _may_name_shim(text):
                yield p, text


def _bare_launcher(source: str) -> list[int]:
    """Lines where a list/tuple literal starts with a Windows-shim launcher name (an argv for subprocess/run helpers)."""
    return sorted(
        n.lineno
        for n in ast.walk(ast.parse(source))
        if isinstance(n, (ast.List, ast.Tuple))
        and n.elts
        and isinstance(n.elts[0], ast.Constant)
        and n.elts[0].value in SHIM_ARGV
    )


def test_no_bare_launcher_argv_in_tests_tools():
    """#4939/#4969: resolve through launcher_exe; a literal "mvn"/"npm" argv is not found on Windows."""
    found = [f"{p.relative_to(TOOLS)}:{n}" for p, text in _shim_sources(TOOLS) for n in _bare_launcher(text)]
    assert found == []


def _first_word(node: ast.expr) -> str | None:
    """The leading text of a str literal or f-string (`f"mvn -q {x}"` -> "mvn"), else None."""
    if isinstance(node, ast.JoinedStr) and node.values:
        node = node.values[0]
    if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.split():
        return node.value.split()[0]
    return None


def _bare_launcher_forms(source: str) -> list[int]:
    """#4939 blind spots of `_bare_launcher`: `mvn = "mvn"` style bindings of a shim name to a variable, and a
    `subprocess.*(...)` / `run_decoded(...)` whose command is a bare list, str or f-string starting with a shim."""
    out = set()
    for n in ast.walk(ast.parse(source)):
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant) and n.value.value in SHIM_ARGV:
            if all(isinstance(t, ast.Name) for t in n.targets):
                out.add(n.lineno)
        if isinstance(n, ast.Call) and n.args:
            f = n.func
            name = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""
            if name not in ("run", "Popen", "call", "check_call", "check_output", "run_decoded"):
                continue
            if name != "run_decoded" and not (
                isinstance(f, ast.Attribute) and getattr(f.value, "id", "") == "subprocess"
            ):
                continue
            a = n.args[0]
            word = _first_word(a.elts[0]) if isinstance(a, (ast.List, ast.Tuple)) and a.elts else _first_word(a)
            if word in SHIM_ARGV:
                out.add(n.lineno)
    return sorted(out)


def test_no_bare_launcher_binding_or_command_string_in_tests():
    """#4939: the list-literal guard misses `mvn = "mvn"`, `subprocess.run("mvn -q")` and anything outside tests/tools."""
    root = TOOLS.parent
    found = [f"{p.relative_to(root)}:{n}" for p, text in _shim_sources(root) for n in _bare_launcher_forms(text)]
    assert found == []


def test_the_prefilter_keeps_every_file_the_guards_can_flag():
    assert _may_name_shim('mvn = "mvn"') and _may_name_shim('run_decoded(["npm.cmd"])')
    assert not _may_name_shim("x = 1\n")


def test_the_form_guard_catches_bindings_and_command_strings():
    assert _bare_launcher_forms('mvn = "mvn"\nx = "other"\n') == [1]
    assert _bare_launcher_forms('import subprocess\nsubprocess.run("mvn -q")\n') == [2]
    assert _bare_launcher_forms('import subprocess\nsubprocess.check_output(f"npm {a}")\n') == [2]
    assert _bare_launcher_forms('run_decoded(["mvn.cmd", "-q"])\n') == [1]
    assert _bare_launcher_forms('run_decoded([mvn_executable(), "-q"])\nd["npm"] = 1\nshutil.which("mvn")\n') == []


def test_strengthen_ask_formats_after_splitting(monkeypatch, tmp_path):
    """#4939: a work dir with a space or a backslash (a Windows path) stays one argument, backslashes intact."""
    import subprocess

    import strengthen

    seen = {}

    def fake_run(argv, **kw):
        seen["argv"] = argv
        return subprocess.CompletedProcess(argv, 0, "out", "")

    monkeypatch.setattr(strengthen.subprocess, "run", fake_run)
    work = tmp_path / "a b\\c"
    out, _ = strengthen.ask("p", work, "m", "tool --in {prompt_file} --dir {prompt_dir}")
    assert out == "out"
    assert seen["argv"] == ["tool", "--in", str(work / "prompt.md"), "--dir", str(work)]


def test_the_guard_catches_a_bare_launcher():
    src = 'subprocess.run(["mvn", "-q"])\nx = ("mvn", "a")\ny = [mvn_executable(), "-q"]\n'
    assert _bare_launcher(src) == [1, 2]
    assert _bare_launcher('run(["npm", "root", "-g"])\nz = ("npx", "tsc")\nw = [npm_executable(), "root"]\n') == [1, 2]
    assert _bare_launcher('run(["npm.cmd", "i"])\nrun(["node", "x.js"])\n') == [1]


def test_npm_resolves_to_npm_cmd_on_windows(monkeypatch):
    seen = {}

    def fake_which(cmd, path=None):
        seen.update(cmd=cmd, path=path)
        return r"C:\Program Files\nodejs\npm.cmd"

    monkeypatch.setattr(shutil, "which", fake_which)
    assert launcher_exe.npm_executable({"PATH": r"C:\Program Files\nodejs"}) == r"C:\Program Files\nodejs\npm.cmd"
    assert seen == {"cmd": "npm", "path": r"C:\Program Files\nodejs"}


def test_npm_falls_back_to_the_bare_name(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda cmd, path=None: None)
    assert launcher_exe.npm_executable({"PATH": ""}) == "npm"


def test_node_env_runs_the_resolved_npm(monkeypatch):
    calls = []
    monkeypatch.delenv("NODE_PATH", raising=False)
    monkeypatch.setattr(callgraph_refs, "npm_executable", lambda env=None: r"C:\nodejs\npm.cmd")
    monkeypatch.setattr(
        callgraph_refs.subprocess,
        "run",
        lambda cmd, **kw: calls.append(cmd) or callgraph_refs.subprocess.CompletedProcess(cmd, 0, "C:\\g\\nm\n", ""),
    )
    assert callgraph_refs.node_env()["NODE_PATH"] == "C:\\g\\nm"
    assert calls == [[r"C:\nodejs\npm.cmd", "root", "-g"]]
