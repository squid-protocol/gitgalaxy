"""merge_main (#6732): which conflicts a model-free merge of main resolves, and the merge itself in a scratch repo."""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import merge_main as mm


@pytest.mark.parametrize(
    ("path", "kind"),
    [
        ("tests/golden_master_audit/part.json", "regenerated"),
        ("tests/ruff_audit_baseline.json", "regenerated"),
        ("tests/tools/docs_read_by_tests.txt", "regenerated"),
        (".test_durations", "regenerated"),
        ("docs/language_status/mutation_testing.md", "region"),
        ("tests/equivalence/det_sweep_coverage/cbsa-inqacc.json", "record"),
        ("tests/equivalence/cbsa-inqacc/evidence.json", "record"),
        ("tests/equivalence/cbsa-inqacc/case.json", "hand"),
        ("tests/dead_key_audit_baseline.json", "hand"),
        ("gitgalaxy/core/detector.py", "hand"),
    ],
)
def test_classify(path, kind):
    assert mm.classify(path)[0] == kind


def test_conflicts_in_stops_at_the_messages():
    out = "abc123\na.py\nb.json\n\nAuto-merging a.py\nCONFLICT (content): Merge conflict in a.py\n"
    assert mm.conflicts_in(out) == ["a.py", "b.json"]


def test_writers_run_once_each_and_goldens_last():
    paths = ["tests/golden_master_audit/x.json", "tests/ruff_audit_baseline.json", "tests/mypy_audit_baseline.json"]
    writers = mm.writers_for(paths)
    assert writers[-1] == mm.GOLDEN_WRITER and len(writers) == 2


def test_blank_region_keeps_the_markers():
    text = "intro\n<!-- s -->\n| a |\n| b |\n<!-- /s -->\noutro\n"
    assert mm.blank_region(text, "<!-- s -->", "<!-- /s -->") == "intro\n<!-- s -->\n<!-- /s -->\noutro\n"


def _git(root, *args):
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A repo with main and a branch `pr` that both moved; `origin/main` points at main."""
    root = tmp_path / "r"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    monkeypatch.setattr(mm, "REPO", root)
    monkeypatch.setattr(mm, "stale_records", lambda: [])
    return root


def _commit(root, files, msg):
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", msg)


def _diverge(root, base, main, pr):
    _commit(root, base, "base")
    _git(root, "checkout", "-q", "-b", "pr")
    _commit(root, pr, "pr")
    _git(root, "checkout", "-q", "main")
    _commit(root, main, "main")
    _git(root, "update-ref", "refs/remotes/origin/main", "main")
    _git(root, "checkout", "-q", "pr")


def test_a_hand_written_conflict_changes_nothing(repo):
    _diverge(repo, {"a.py": "x = 1\n"}, {"a.py": "x = 2\n"}, {"a.py": "x = 3\n"})
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout
    assert mm.main(["--no-fetch"]) == 2
    assert subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout == head
    assert (repo / "a.py").read_text() == "x = 3\n"


def test_a_regenerated_file_without_a_writer_takes_mains_side(repo):
    _diverge(repo, {".test_durations": "{}\n", "a.py": "x\n"}, {".test_durations": '{"m": 1}\n'},
             {".test_durations": '{"p": 1}\n', "b.py": "y\n"})  # fmt: skip
    assert mm.main(["--no-fetch"]) == 0
    assert (repo / ".test_durations").read_text() == '{"m": 1}\n' and (repo / "b.py").exists()
    parents = subprocess.run(["git", "rev-list", "--parents", "-n1", "HEAD"], cwd=repo, capture_output=True, text=True)
    assert len(parents.stdout.split()) == 3  # a merge commit, never a rebase


def test_a_region_file_merges_its_prose_and_rerenders_the_region(repo, monkeypatch):
    path = "docs/language_status/mutation_testing.md"
    writer = [sys.executable, "-c", f"import re,pathlib;p=pathlib.Path('{path}');t=p.read_text();"
              "p.write_text(re.sub(r'(<!-- s -->\\n).*?(<!-- /s -->)', r'\\1| rendered |\\n\\2', t, flags=re.S))"]  # fmt: skip
    monkeypatch.setitem(mm.REGIONS, path, ("<!-- s -->", "<!-- /s -->", writer))
    doc = "title\n\nprose one\n\n<!-- s -->\n| {} |\n<!-- /s -->\n\nprose two\n"
    _diverge(repo, {path: doc.format("base")}, {path: doc.format("main")},
             {path: doc.format("pr").replace("prose two", "prose two, edited by the PR")})  # fmt: skip
    assert mm.main(["--no-fetch"]) == 0
    text = (repo / path).read_text()
    assert "| rendered |" in text and "edited by the PR" in text and "<<<<<<<" not in text
