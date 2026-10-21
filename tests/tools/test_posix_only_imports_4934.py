# ruff: noqa: S101
"""#4934: a POSIX-only module import (fcntl, ...) cannot reach Windows unguarded.

The Full Suite Gate runs on Windows; `import fcntl` there raises ModuleNotFoundError. Every import of such a module
must be (a) inside a `try` that catches ImportError, (b) in a file that calls `pytest.importorskip` for it, or
(c) in LINUX_ONLY below, with the reason the file is never reached on Windows.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
POSIX_ONLY = frozenset({"fcntl", "termios", "pwd", "grp", "resource", "posix"})
# #5882: an import names its module as a word, so a file without one cannot import it: only those are parsed (~1 in 10)
_MENTIONS = re.compile(r"\b(?:" + "|".join(sorted(POSIX_ONLY)) + r")\b")
# Linux-only by design: the file runs only where Docker/Db2 or the CI shepherd box is, and every test reaching it
# skips on Windows (the test files `importorskip("fcntl")`).
LINUX_ONLY = {
    "tests/tools/equivalence_db2.py": "the Db2 pool's database locks (Db2 runs in a Linux container)",
    "tests/tools/box/ci_shepherd.py": "the CI shepherd is a Linux box tool (its test importorskips fcntl)",
}


def _module_names(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Import):
        return {a.name.split(".")[0] for a in node.names}
    if isinstance(node, ast.ImportFrom) and node.module and not node.level:
        return {node.module.split(".")[0]}
    return set()


def _catches_import_error(node: ast.Try) -> bool:
    names = {"ImportError", "ModuleNotFoundError", "Exception", "BaseException"}
    for h in node.handlers:
        types = h.type.elts if isinstance(h.type, ast.Tuple) else [h.type]
        if h.type is None or any(isinstance(t, ast.Name) and t.id in names for t in types):
            return True
    return False


def _guarded_by_try(tree: ast.AST) -> set[int]:
    """Line numbers of the nodes in the body of a `try` that catches ImportError."""
    lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try) and _catches_import_error(node):
            for stmt in node.body:
                lines.update(n.lineno for n in ast.walk(stmt) if hasattr(n, "lineno"))
    return lines


def _importorskipped(tree: ast.AST) -> set[str]:
    skipped: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and getattr(node.func, "attr", getattr(node.func, "id", "")) == "importorskip"
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ):
            skipped.add(str(node.args[0].value).split(".")[0])
    return skipped


def unguarded(root: Path = REPO_ROOT) -> list[str]:
    found = []
    for sub in ("tests", "gitgalaxy"):
        for path in sorted((root / sub).rglob("*.py")):
            rel = path.relative_to(root).as_posix()
            if rel in LINUX_ONLY:
                continue
            try:
                text = path.read_text(encoding="utf-8")
                if not _MENTIONS.search(text):
                    continue
                tree = ast.parse(text)
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue
            guarded, skipped = _guarded_by_try(tree), _importorskipped(tree)
            found.extend(
                f"{rel}:{node.lineno}: import {mod}"
                for node in ast.walk(tree)
                for mod in sorted(_module_names(node) & POSIX_ONLY)
                if node.lineno not in guarded and mod not in skipped
            )
    return found


@pytest.mark.slow(reason="parses every .py under tests and gitgalaxy with ast (#5178)")
def test_no_posix_only_import_is_unguarded():
    """#4934: guard it (try/except ImportError, pytest.importorskip) or list it in LINUX_ONLY with the reason."""
    assert unguarded() == []


def test_the_guard_catches_an_unguarded_fcntl_import(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "gitgalaxy").mkdir()
    (tmp_path / "tests" / "bad.py").write_text("def f():\n    import fcntl\n", encoding="utf-8")
    (tmp_path / "tests" / "ok_try.py").write_text("try:\n    import fcntl\nexcept ImportError:\n    fcntl = None\n")
    (tmp_path / "tests" / "ok_skip.py").write_text(
        "import pytest\nfcntl = pytest.importorskip('fcntl')\nimport fcntl\n"
    )
    assert unguarded(tmp_path) == ["tests/bad.py:2: import fcntl"]


def test_linux_only_entries_exist():
    """A stale allowlist entry (a renamed or deleted file) would silently exempt nothing."""
    for rel in LINUX_ONLY:
        assert (REPO_ROOT / rel).is_file(), rel
