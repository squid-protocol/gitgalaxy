"""#7667: ruff_audit --ci fails on Python a 3.11 interpreter cannot parse, anywhere in the repo (not just gitgalaxy/).

#7637 put a backslash inside an f-string expression in tests/cics_crucible/; PR CI (3.12) passed and main's py3.11 legs
broke. The baseline-gated lint scans gitgalaxy/ only, so the syntax floor is its own zero-tolerance pass.
"""

import shutil
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS_DIR))
import ruff_audit  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("ruff") is None, reason="needs ruff on PATH (ci/requirements/lint.txt)")

PYPROJECT = '[tool.ruff]\nexclude = ["tests/fixtures/*"]\ntarget-version = "py311"\n'


def _repo(tmp_path: Path, files: dict[str, str]) -> Path:
    (tmp_path / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    for rel, text in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, encoding="utf-8")
    return tmp_path


def test_a_backslash_in_an_f_string_expression_under_tests_is_reported(tmp_path):
    repo = _repo(tmp_path, {"tests/x/test_a.py": "def f(xs):\n    return f\"{'\\n'.join(xs)}\"\n"})
    found = ruff_audit.run_syntax_check(repo)
    assert len(found) == 1 and "tests/x/test_a.py:2:" in found[0] and "3.11" in found[0]


def test_clean_3_11_code_and_excluded_fixtures_pass(tmp_path):
    repo = _repo(
        tmp_path,
        {
            "tests/x/test_a.py": "def f(xs):\n    nl = '\\n'\n    return f'{nl.join(xs)}'\n",
            "tests/fixtures/legacy.py": "print 'py2'\n",  # pyproject excludes fixtures, as for the lint
        },
    )
    assert ruff_audit.run_syntax_check(repo) == []


def test_the_live_repo_parses_under_its_3_11_floor():
    assert ruff_audit.run_syntax_check() == []
