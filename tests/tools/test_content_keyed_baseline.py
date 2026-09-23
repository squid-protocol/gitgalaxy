"""
Content-keyed ruff/mypy baselines (#3384): tests/lint_baseline.py's key scheme,
as consumed by ruff_audit.py, mypy_audit.py and audit_check.py.

Most tests feed ruff_audit.parse_ruff_json() synthetic `ruff --output-format=json`
output produced by a tiny fake linter over real temp files, so they exercise the
real parsing/keying/comparison code without depending on which rules the installed
ruff happens to ship. One test runs the real `ruff` binary when it's on PATH.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TESTS_DIR))
import lint_baseline as lb
import mypy_audit
import ruff_audit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_check

REL = "pkg/mod.py"
PATTERN = "sorted(list("

BASE_SOURCE = """\
import os


def a(xs):
    return sorted(list(xs))


def b(ys):
    return sorted(list(ys))
"""


def _fake_ruff_json(repo: Path) -> str:
    """Emulates `ruff check --output-format=json`: one C414 per PATTERN occurrence."""
    items = []
    for path in sorted(repo.rglob("*.py")):
        for row, text in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            col = text.find(PATTERN)
            while col != -1:
                items.append(
                    {
                        "filename": str(path),
                        "location": {"row": row, "column": col + 1},
                        "code": "C414",
                        "message": "Unnecessary `list()` call within `sorted()`",
                    }
                )
                col = text.find(PATTERN, col + 1)
    return json.dumps(items)


def _write(repo: Path, source: str) -> None:
    path = repo / REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def _findings(repo: Path) -> dict:
    return ruff_audit.parse_ruff_json(_fake_ruff_json(repo), repo)


def _bless(repo: Path) -> str:
    """What `ruff_audit.py --write-baseline` would write, as text."""
    return lb.dump_baseline(lb.to_baseline(_findings(repo)))


def test_key_shape_and_roundtrip(tmp_path):
    _write(tmp_path, BASE_SOURCE)
    keys = sorted(_findings(tmp_path))
    assert len(keys) == 2
    for key in keys:
        # rebase_rebless.verify_baseline_refresh_scope relies on the file coming first.
        assert key.split(":", 1)[0] == REL
        file, code, digest, occurrence = lb.parse_key(key)
        assert (file, code) == (REL, "C414")
        assert len(digest) == lb.HASH_LEN
        assert lb.format_key(file, code, digest, occurrence) == key
    # different content -> different hashes, each #0
    assert {lb.parse_key(k)[3] for k in keys} == {0}


def test_unrelated_line_insertion_keeps_baseline_valid_and_byte_identical(tmp_path):
    _write(tmp_path, BASE_SOURCE)
    baseline_text = _bless(tmp_path)
    before = _findings(tmp_path)

    shifted = BASE_SOURCE.replace("import os\n", "import os\nimport sys\n\nCONSTANT = 1\n\n\n")
    _write(tmp_path, shifted)
    after = _findings(tmp_path)

    # same keys, but the human-readable line numbers moved
    assert set(after) == set(before)
    assert [f.line for f in after.values()] != [f.line for f in before.values()]
    assert "mod.py:10: C414" in lb.describe(*next(iter(after.items())))

    new, stale = ruff_audit.compare(after, json.loads(baseline_text))
    assert new == {} and stale == []
    assert _bless(tmp_path) == baseline_text  # regenerate is a byte-identical no-op


def test_reindent_and_respacing_is_stable(tmp_path):
    _write(tmp_path, BASE_SOURCE)
    baseline = json.loads(_bless(tmp_path))
    _write(tmp_path, BASE_SOURCE.replace("    return sorted(list(xs))", "        return  sorted(list(xs))"))
    assert ruff_audit.compare(_findings(tmp_path), baseline) == ({}, [])


def test_new_duplicate_of_baselined_line_is_caught(tmp_path):
    _write(tmp_path, BASE_SOURCE)
    baseline = json.loads(_bless(tmp_path))

    # an identical copy of an already-baselined violating line, ABOVE the original
    dup = BASE_SOURCE.replace("def a(xs):\n", "def a0(xs):\n    return sorted(list(xs))\n\n\ndef a(xs):\n")
    _write(tmp_path, dup)
    new, stale = ruff_audit.compare(_findings(tmp_path), baseline)

    assert stale == []
    assert len(new) == 1
    (key,) = new
    assert lb.parse_key(key)[3] == 1  # occurrence #1 of the same (file, code, hash)


def test_changed_line_is_caught(tmp_path):
    _write(tmp_path, BASE_SOURCE)
    baseline = json.loads(_bless(tmp_path))

    _write(tmp_path, BASE_SOURCE.replace("sorted(list(xs))", "sorted(list(xs), reverse=True)"))
    new, stale = ruff_audit.compare(_findings(tmp_path), baseline)
    assert len(new) == 1 and len(stale) == 1
    assert next(iter(new.values())).line == 5


def test_removed_violation_is_reported_stale(tmp_path):
    _write(tmp_path, BASE_SOURCE)
    baseline = json.loads(_bless(tmp_path))

    _write(tmp_path, BASE_SOURCE.replace("sorted(list(ys))", "sorted(ys)"))
    new, stale = ruff_audit.compare(_findings(tmp_path), baseline)
    assert new == {}
    assert len(stale) == 1 and baseline[stale[0]].startswith("Unnecessary")


def test_two_findings_on_one_line_do_not_collapse(tmp_path):
    _write(tmp_path, "x = sorted(list(a)) + sorted(list(b))\n")
    keys = sorted(_findings(tmp_path))
    assert [lb.parse_key(k)[3] for k in keys] == [0, 1]


def test_ci_check_end_to_end(tmp_path, monkeypatch, capsys):
    """run_ci_check(): pass after a shift, fail on a new duplicate, FYI for stale; prints current line numbers."""
    _write(tmp_path, BASE_SOURCE)
    baseline_path = tmp_path / "baseline.json"
    lb.write_baseline(baseline_path, lb.to_baseline(_findings(tmp_path)))
    monkeypatch.setattr(ruff_audit, "BASELINE_PATH", baseline_path)
    monkeypatch.setattr(ruff_audit, "run_ruff_format_check", lambda: True)
    monkeypatch.setattr(ruff_audit, "run_ruff_findings", lambda: _findings(tmp_path))

    _write(tmp_path, "\n\n" + BASE_SOURCE)
    assert ruff_audit.run_ci_check() == 0

    _write(tmp_path, "\n\n" + BASE_SOURCE + "\n\ndef c(zs):\n    return sorted(list(ys))\n")
    assert ruff_audit.run_ci_check() == 1
    out = capsys.readouterr().out
    assert "1 NEW lint finding(s) beyond the 2-finding baseline" in out
    assert "pkg/mod.py:15: C414" in out

    _write(tmp_path, "\n\n" + BASE_SOURCE.replace("sorted(list(xs))", "sorted(xs)"))
    assert ruff_audit.run_ci_check() == 0
    assert "no longer flagged" in capsys.readouterr().out


def test_mypy_output_parsing_uses_same_scheme(tmp_path):
    _write(tmp_path, BASE_SOURCE)
    stdout = (
        f"{REL}:5: error: Bad thing  [operator]\n"
        f"{REL}:5: error: Other bad thing  [operator]\n"
        f"{REL}:9: note: ignored\n"
        "Found 2 errors in 1 file (checked 1 source file)\n"
    )
    keyed = mypy_audit.parse_mypy_output(stdout, tmp_path)
    assert sorted(lb.parse_key(k)[3] for k in keyed) == [0, 1]
    assert {f.line for f in keyed.values()} == {5}
    shifted = stdout.replace(":5:", ":8:")
    _write(tmp_path, "\n\n\n" + BASE_SOURCE)
    assert set(mypy_audit.parse_mypy_output(shifted, tmp_path)) == set(keyed)


def test_audit_check_pairs_edited_lines_one_for_one():
    stale = {"f.py: C414 @aaaaaaaaaaaa#0": "msg"}
    new = {"f.py: C414 @bbbbbbbbbbbb#0": "msg", "f.py: C414 @cccccccccccc#0": "msg"}
    edited, genuine = audit_check._classify(new, stale)
    assert len(edited) == 1 and len(genuine) == 1


@pytest.mark.parametrize("name", ["ruff_audit_baseline.json", "mypy_audit_baseline.json"])
def test_committed_baselines_are_canonical_content_keys(name):
    path = TESTS_DIR / name
    text = path.read_text(encoding="utf-8")
    baseline = json.loads(text)
    assert lb.dump_baseline(baseline) == text, f"{name} is not in canonical (sorted) form"
    for key in baseline:
        file, code, digest, _occ = lb.parse_key(key)
        assert lb.format_key(*lb.parse_key(key)) == key, key
        assert file.startswith("gitgalaxy/") and code and len(digest) == lb.HASH_LEN, key


@pytest.mark.skipif(shutil.which("ruff") is None, reason="ruff not on PATH")
def test_real_ruff_line_shift(tmp_path):
    (tmp_path / "m.py").write_text("def f():\n    x = 1\n", encoding="utf-8")
    before = ruff_audit.run_ruff_findings(scan_root=tmp_path, repo_root=tmp_path)
    assert any(f.code == "F841" for f in before.values())
    (tmp_path / "m.py").write_text("import os\n\nos.getcwd()\n\n\ndef f():\n    x = 1\n", encoding="utf-8")
    after = ruff_audit.run_ruff_findings(scan_root=tmp_path, repo_root=tmp_path)
    assert set(after) == set(before)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True)
    assert result.returncode == 0, f"git {args} failed:\n{result.stdout}\n{result.stderr}"
    return result.stdout


def _commit_all(repo: Path, message: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)


@pytest.mark.skipif(shutil.which("git") is None, reason="git not on PATH")
def test_two_branches_shifting_lines_in_same_file_merge_baseline_conflict_free(tmp_path):
    """#3384 acceptance: each branch shifts lines in the same file and re-blesses; the merge is clean."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")

    source = BASE_SOURCE + "\n\n# end\n"
    _write(repo, source)
    (repo / "baseline.json").write_text(_bless(repo), encoding="utf-8")
    _commit_all(repo, "base")
    base_baseline = (repo / "baseline.json").read_text(encoding="utf-8")

    _git(repo, "checkout", "-q", "-b", "left")
    _write(repo, source.replace("import os\n", "import os\nimport re\nimport sys\n"))
    (repo / "baseline.json").write_text(_bless(repo), encoding="utf-8")
    _commit_all(repo, "left shifts lines")

    _git(repo, "checkout", "-q", "main")
    _git(repo, "checkout", "-q", "-b", "right")
    _write(repo, source.replace("# end\n", "# end\n\n\ndef helper():\n    return 42\n"))
    _write(repo, (repo / REL).read_text().replace("def b(ys):\n", "# note\n# note 2\ndef b(ys):\n"))
    (repo / "baseline.json").write_text(_bless(repo), encoding="utf-8")
    _commit_all(repo, "right shifts lines")

    _git(repo, "merge", "-q", "--no-edit", "left")  # asserts no conflict
    merged = (repo / "baseline.json").read_text(encoding="utf-8")
    assert merged == base_baseline
    assert _bless(repo) == merged
