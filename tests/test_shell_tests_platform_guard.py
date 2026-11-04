"""A test that spawns bash or sh must check the platform (#7312, #7619).

PR CI runs on ubuntu only; the Windows and macOS legs run only in the Full Suite Gate on main. On a Windows runner `bash`
is the WSL launcher: `shutil.which("bash")` finds it, so a `which`-is-None skip never fires, and it drops the env a
workflow step reads and keeps the `\\r` of a CRLF line. Two tests that ran a workflow's bash step through `subprocess`
passed every PR check and turned main red on Windows: #7171's `test_full_suite_control.py` (#7312, fixed by #7314) and
`test_infeasible_outcomes.py`'s solver-check filter (#7619, fixed by #7620).

The gate is AST-based and per file: a tracked test file that calls `subprocess.run` / `Popen` / `call` / `check_call` /
`check_output` with bash, sh, a `.sh` script, or a name bound to `shutil.which("bash")`, must mention `sys.platform`,
`os.name` or `platform.system()` (a `skipif`, a `pytest.skip`, or a branch for Windows). Coarse on purpose: it catches
the file that never thought about Windows, which is what both reds were.
"""

from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SHELLS = frozenset({"bash", "sh", "/bin/bash", "/bin/sh", "/usr/bin/bash", "/usr/bin/env"})
SPAWNS = frozenset({"run", "Popen", "call", "check_call", "check_output"})
PLATFORM_CHECKS = ("sys.platform", "os.name", "platform.system()")
# A quoted shell name or .sh path: only a file with one is parsed (about 2 s for all 338 files that merely say
# "subprocess" and "sh"; the suite's per-test time ratchet is 15 s, #5166).
MAYBE_SHELL = re.compile(r"""["'](?:/usr)?(?:/bin/)?(?:ba)?sh(?:\s|["'])|\.sh["']""")


def _which_shell(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "which"
        and bool(node.args)
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value in ("bash", "sh")
    )


def _is_shell(node: ast.AST, shell_names: set[str]) -> bool:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value in SHELLS or node.value.endswith(".sh")
    return (isinstance(node, ast.Name) and node.id in shell_names) or _which_shell(node)


def shell_spawns(source: str) -> list[int]:
    """Line numbers of the subprocess calls in `source` that run bash, sh or a .sh script."""
    tree = ast.parse(source)
    shell_names = {
        t.id
        for n in ast.walk(tree)
        if isinstance(n, ast.Assign) and _which_shell(n.value)
        for t in n.targets
        if isinstance(t, ast.Name)
    }
    lines = []
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in SPAWNS and n.args):
            continue
        cmd = n.args[0]
        if isinstance(cmd, (ast.List, ast.Tuple)) and cmd.elts and _is_shell(cmd.elts[0], shell_names):
            lines.append(n.lineno)
        elif isinstance(cmd, ast.Constant) and isinstance(cmd.value, str) and cmd.value.split(" ")[0] in SHELLS:
            lines.append(n.lineno)
    return sorted(lines)


def unguarded(source: str) -> list[int]:
    """The shell spawns of a file that never checks the platform ([] when it does, or spawns none)."""
    spawns = shell_spawns(source)
    return [] if any(k in source for k in PLATFORM_CHECKS) else spawns


def _tracked_tests() -> list[str]:
    out = subprocess.run(["git", "ls-files", "tests"], cwd=REPO, capture_output=True, text=True, check=True).stdout
    return [f for f in out.split() if f.endswith(".py") and not f.startswith("tests/fixtures/")]


def test_every_test_that_spawns_a_shell_checks_the_platform():
    bad = {}
    for rel in _tracked_tests():
        source = (REPO / rel).read_text(encoding="utf-8", errors="surrogateescape")
        if "subprocess" not in source or not MAYBE_SHELL.search(source):
            continue
        try:
            if lines := unguarded(source):
                bad[rel] = lines
        except SyntaxError:
            continue  # the py3.11 syntax floor (ruff_audit) reports it
    assert not bad, (
        "these tests run bash/sh through subprocess with no platform check; on a Windows runner `bash` is WSL "
        "(it drops the step's env, keeps CRLF's \\r) and the Full Suite Gate goes red on main (#7312, #7619). Add "
        '`pytest.mark.skipif(sys.platform != "linux", reason=...)` or handle Windows: ' + repr(bad)
    )


PRE_7314 = """
import subprocess

def _passes(env):
    return subprocess.run(["bash", "-e", "-c", "true"], env=env).returncode == 0
"""

PRE_7620 = """
import shutil, subprocess, sys
import pytest

def _run(script):
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("no bash")
    return subprocess.run([bash, "-e", "-c", script], check=False)
"""


def test_the_two_red_main_shapes_are_caught_and_their_fixes_pass():
    assert unguarded(PRE_7314) == [5]
    assert unguarded(PRE_7620) == [9]  # a which-is-None skip is not a platform check: WSL's bash is on PATH
    fixed = PRE_7620.replace("def _run", '@pytest.mark.skipif(sys.platform != "linux", reason="bash")\ndef _run')
    assert unguarded(fixed) == []


def test_strings_scripts_and_non_shell_commands():
    assert shell_spawns('import subprocess\nsubprocess.check_output("bash -c true", shell=True)\n') == [2]
    assert shell_spawns('import subprocess\nsubprocess.run(["tests/tools/box/heavy-run.sh", "x"])\n') == [2]
    assert shell_spawns('import subprocess, sys\nsubprocess.run([sys.executable, "-c", "print(1)"])\n') == []
    assert shell_spawns('LANGS = ["bash", "sh"]\n') == []  # a language name in a list is not a spawn
