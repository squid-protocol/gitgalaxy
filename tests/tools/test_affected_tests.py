"""affected_tests (#6733): which test files a change reaches, and the budget that picks the ones run locally. The
graph is built from strings here; no git needed except where noted."""

import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import affected_tests as at

FILES = [
    "gitgalaxy/__init__.py", "gitgalaxy/core/__init__.py", "gitgalaxy/core/detector.py", "gitgalaxy/core/prism.py",
    "tests/tools/evidence.py", "tests/tools/det_port.py", "tests/extraction/_harness.py",
    "tests/extraction/languages/test_c.py", "tests/tools/test_evidence.py", "tests/cobol_mainframe/test_det.py",
]  # fmt: skip


def _imports(rel, src):
    return at.imports_of(rel, src, at.Resolver(FILES))


def test_gitgalaxy_imports_resolve_to_modules_and_relative_ones_inside_the_package():
    assert _imports("tests/x/test_a.py", "from gitgalaxy.core.detector import scan") == {"gitgalaxy/core/detector.py"}
    assert _imports("tests/x/test_a.py", "from gitgalaxy.core import detector") == {"gitgalaxy/core/detector.py"}
    assert _imports("gitgalaxy/core/prism.py", "from .detector import scan") == {"gitgalaxy/core/detector.py"}
    assert _imports("tests/x/test_a.py", "import os, json, pytest") == set()


def test_bare_imports_find_an_ancestor_harness_then_tests_tools():
    src = "import _harness\nimport evidence\n"
    assert _imports("tests/extraction/languages/test_c.py", src) == {
        "tests/extraction/_harness.py",
        "tests/tools/evidence.py",
    }


def test_a_string_naming_a_tool_is_a_read():
    src = 'subprocess.run([sys.executable, "tests/tools/det_port.py", "run"])\nX = "det_port.py"\n'
    assert _imports("tests/cobol_mainframe/test_det.py", src) == {"tests/tools/det_port.py"}


def test_affected_walks_importers_and_keeps_the_nearest_distance():
    g = {
        "gitgalaxy/core/detector.py": set(),
        "tests/tools/det_port.py": {"gitgalaxy/core/detector.py"},
        "tests/cobol_mainframe/test_det.py": {"tests/tools/det_port.py", "gitgalaxy/core/detector.py"},
        "tests/tools/test_evidence.py": {"tests/tools/det_port.py"},
        "tests/extraction/languages/test_c.py": set(),
    }
    hits = at.affected(["gitgalaxy/core/detector.py"], g, readers={})
    assert hits == {"tests/cobol_mainframe/test_det.py": 1, "tests/tools/test_evidence.py": 2}


def test_a_changed_data_file_reaches_the_files_that_name_it():
    g = {"tests/tools/det_port.py": set(), "tests/tools/test_evidence.py": {"tests/tools/det_port.py"},
         "tests/extraction/languages/test_c.py": set()}  # fmt: skip
    readers = {".github/workflows/det-sweep.yml": {"tests/tools/det_port.py"}}
    assert at.affected([".github/workflows/det-sweep.yml"], g, readers) == {"tests/tools/test_evidence.py": 2}


def test_name_keys_use_a_unique_file_name_else_the_directory():
    files = Counter({"det-sweep.yml": 1, "case.json": 180})
    dirs = Counter({"carddemo-copaus0c": 1, "languages": 3})
    assert at.name_keys(".github/workflows/det-sweep.yml", files, dirs) == ["det-sweep.yml"]
    assert at.name_keys("tests/equivalence/carddemo-copaus0c/case.json", files, dirs) == ["carddemo-copaus0c"]
    assert at.name_keys("tests/extraction/languages/case.json", files, dirs) == []


def test_select_runs_nearest_first_within_the_budget_and_names_the_rest():
    hits = {"a.py": 1, "b.py": 1, "c.py": 2, "d.py": 3}
    seconds = {"a.py": 50.0, "b.py": 10.0, "c.py": 100.0, "d.py": 1.0}
    run, left, total = at.select(hits, seconds, budget=120.0)
    assert run == ["b.py", "a.py", "d.py"] and left == ["c.py"] and total == 61.0


def test_select_always_runs_the_nearest_file_even_over_the_budget():
    run, left, _ = at.select({"big.py": 1, "x.py": 2}, {"big.py": 900.0, "x.py": 1.0}, budget=60.0)
    assert run == ["big.py"] and left == ["x.py"]


def test_the_repo_graph_reaches_this_tests_module_from_the_tool():
    g = at.graph()  # the real tree: the scan must at least see this file import the tool
    assert "tests/tools/affected_tests.py" in g["tests/tools/test_affected_tests.py"]


def test_pytest_runs_under_this_interpreter_when_it_has_pytest():
    assert at.pytest_command(has_pytest=True, which=lambda _: "/elsewhere/pytest") == (
        [sys.executable, "-m", "pytest"], None)  # fmt: skip


def test_an_interpreter_without_pytest_uses_the_one_on_path_with_this_checkout_first():
    """PR #6799: churn's precheck runs the gates under /usr/bin/python3, which has no pytest."""
    cmd, env = at.pytest_command(has_pytest=False, which=lambda _: "/venv/bin/pytest")
    assert cmd == ["/venv/bin/pytest"]
    assert env["PYTHONPATH"].split(os.pathsep)[0] == str(at.REPO)


def test_no_pytest_anywhere_keeps_the_module_form_so_the_error_names_it():
    assert at.pytest_command(has_pytest=False, which=lambda _: None)[0] == [sys.executable, "-m", "pytest"]
