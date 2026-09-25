"""The compile workflow's diff gate (java_target_matrix.py --same-as): two generated
trees compare equal after the run timestamps are blanked, and any real difference --
a changed, missing or extra file -- is reported, so the build runs."""

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "java_target_matrix", Path(__file__).resolve().parents[1] / "tools" / "java_target_matrix.py"
)
matrix = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(matrix)


def _tree(root: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    return root


def test_timestamps_are_blanked_and_identical_trees_compare_equal(tmp_path):
    a = _tree(tmp_path / "a", {"audit.txt": "from x_gitgalaxy_clean_20260925_120000 ok", "S.java": "class S {}"})
    b = _tree(tmp_path / "b", {"audit.txt": "from x_gitgalaxy_clean_20260925_130501 ok", "S.java": "class S {}"})
    assert matrix._same_tree(a, b) == ["audit.txt"]
    matrix.normalize(a)
    matrix.normalize(b)
    assert (a / "audit.txt").read_text(encoding="utf-8") == "from x_gitgalaxy_clean_TIMESTAMP ok"
    assert matrix._same_tree(a, b) == []


def test_changed_missing_and_extra_files_are_differences(tmp_path):
    a = _tree(tmp_path / "a", {"p/A.java": "a", "p/B.java": "b", "p/q/C.java": "c"})
    b = _tree(tmp_path / "b", {"p/A.java": "a", "p/B.java": "B!", "p/q/D.java": "d"})
    assert sorted(matrix._same_tree(a, b)) == ["p/B.java", "p/q/C.java", "p/q/D.java"]
