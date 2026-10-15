"""#5166 part A: the extraction ReDoS sweeps are deselected only on a pull request that changes no sweep input.

The planner (tests/tools/sweep_plan.py) must never drop a sweep for a PR that touches something a sweep reads, and the
marker (tests/conftest.py) must select exactly the sweeps the workflow deselects.
"""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sweep_plan as sp

ROOT = Path(__file__).resolve().parents[2]

# one path per family: what a sweep reads
INPUT_PATHS = [
    "gitgalaxy/standards/language_standards/languages/cobol.py",
    "gitgalaxy/core/detector.py",
    "gitgalaxy/galaxyscope.py",
    "gitgalaxy/tools/cobol_to_java/det/emit.py",  # under gitgalaxy/: the whole engine is an input
    "gitgalaxy/core/README.md",
    "tests/extraction/languages/test_python.py",
    "tests/extraction/languages/_strict_harness.py",
    "tests/extraction/_extraction_harness.py",
    "tests/extraction/how_to_harden_strict_signatures.md",
    "tests/conftest.py",
    "tests/_timing.py",  # a test helper the sweeps import
    "tests/core_engine/test_detector.py",  # a test directory nobody listed: an input
    "pyproject.toml",
    "requirements.txt",
    "ci/requirements/test.txt",
    ".github/workflows/smoke-test.yml",
    ".github/workflows/full-suite-gate.yml",
    "tests/tools/sweep_plan.py",
    "tests/tools/test_sweep_plan.py",
    "setup.cfg",  # unlisted at the root
    "somewhere/new/file.py",
]
# what they provably do not read
NON_INPUT_PATHS = [
    "docs/ci.md",
    "docs/language_status/cobol.md",
    "README.md",
    "CLAUDE.md",
    ".claude/rules/test-writing.md",
    ".github/workflows/det-sweep.yml",
    ".github/dependabot.yml",
    "tests/cobol_mainframe/test_completeness.py",
    "tests/equivalence/some-case/case.json",
    "tests/tools/det_sweep_plan.py",
    "tests/tools/box/heavy-run.sh",
]


@pytest.mark.parametrize("path", INPUT_PATHS)
def test_every_input_family_runs_the_sweeps(path):
    p = sp.plan([path], "pull_request")
    assert p["mode"] == "full" and p["inputs"] == [path]


@pytest.mark.parametrize("path", NON_INPUT_PATHS)
def test_a_non_input_deselects_the_sweeps(path):
    assert sp.plan([path], "pull_request")["mode"] == "none"


def test_all_non_inputs_together_deselect():
    assert sp.plan(NON_INPUT_PATHS, "pull_request")["mode"] == "none"


@pytest.mark.parametrize("path", INPUT_PATHS)
def test_one_input_among_non_inputs_runs_them(path):
    assert sp.plan([*NON_INPUT_PATHS, path], "pull_request")["mode"] == "full"


@pytest.mark.parametrize("event", ["push", "schedule", "workflow_dispatch", "merge_group", ""])
def test_every_other_event_runs_the_sweeps(event):
    assert sp.plan(NON_INPUT_PATHS, event)["mode"] == "full"
    assert sp.plan([], event)["mode"] == "full"


def test_the_full_label_runs_the_sweeps():
    assert sp.plan(NON_INPUT_PATHS, "pull_request", ["bug", sp.FULL_LABEL])["mode"] == "full"
    assert sp.plan(NON_INPUT_PATHS, "pull_request", ["bug"])["mode"] == "none"


def test_an_empty_diff_runs_the_sweeps():
    assert sp.plan([], "pull_request")["mode"] == "full"


def test_an_unreadable_diff_runs_the_sweeps(monkeypatch, tmp_path, capsys):
    def boom(base):
        raise RuntimeError("bad revision")

    monkeypatch.setattr(sp, "changed_files", boom)
    out = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", ["sweep_plan", "--github-output", str(out)])
    assert sp.main() == 0
    assert out.read_text() == "mode=full\n"
    assert "cannot diff" in capsys.readouterr().out


def test_main_writes_the_mode_for_the_workflow(monkeypatch, tmp_path):
    out = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", ["sweep_plan", "--files", "docs/ci.md", "--github-output", str(out)])
    assert sp.main() == 0
    assert out.read_text() == "mode=none\n"
    out.write_text("")
    monkeypatch.setattr(sys, "argv", ["sweep_plan", "--files", "docs/ci.md", "--labels", "x," + sp.FULL_LABEL,
                                      "--github-output", str(out)])  # fmt: skip
    sp.main()
    assert out.read_text() == "mode=full\n"


def test_the_sweeps_import_no_non_input_module():
    """INPUTS name what a sweep reads: a bare import of a module under a NON_INPUT directory would make that wrong."""
    non_input_modules = set()
    for d in ("tests/tools", "tests/cobol_mainframe", "tests/equivalence"):
        non_input_modules |= {p.stem for p in (ROOT / d).glob("*.py")}
    bad = []
    for f in sorted((ROOT / "tests" / "extraction").rglob("*.py")):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            names = (
                [a.name for a in node.names] if isinstance(node, ast.Import)
                else [node.module or ""] if isinstance(node, ast.ImportFrom) and node.level == 0 else []
            )  # fmt: skip
            bad += [f"{f.relative_to(ROOT)}: {n}" for n in names if n.split(".")[0] in non_input_modules]
    assert not bad, bad


def _collect(*args):
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/extraction", "--collect-only", "-q", "-p", "no:cacheprovider", *args],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
    return {ln for ln in proc.stdout.splitlines() if ln.startswith("tests/")}


def test_the_marker_selects_exactly_the_name_rule_and_m_deselects_it():
    everything = _collect("-m", "not golden_crucible")
    marked = _collect("-m", "redos_sweep")
    kept = _collect("-m", "not golden_crucible and not redos_sweep")  # the expression smoke-test.yml uses
    assert marked, "no sweep is marked: the hook did not run before -m"
    assert marked | kept == everything and not marked & kept
    for nodeid in marked:
        assert nodeid.startswith("tests/extraction/")
        name = nodeid.split("[")[0].split("::")[-1]
        assert "redos" in name or "linear_on_pathological" in name, nodeid
    for nodeid in kept:
        name = nodeid.split("[")[0].split("::")[-1]
        assert "redos" not in name and "linear_on_pathological" not in name, nodeid


def test_a_test_outside_extraction_is_not_marked():
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/core_engine", "--collect-only", "-q", "-m", "redos_sweep",
         "-p", "no:cacheprovider"], cwd=ROOT, capture_output=True, text=True, check=False)  # fmt: skip
    assert "tests/core_engine/" not in proc.stdout  # the ~23 core_engine sweeps stay always-on


def test_the_workflow_plans_then_deselects_with_golden_crucible_kept():
    yaml = pytest.importorskip("yaml")
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "smoke-test.yml").read_text(encoding="utf-8"))["jobs"]
    job = wf["full-suite-part"]
    names = [s.get("name", "") for s in job["steps"]]
    plan_i = next(i for i, n in enumerate(names) if n.startswith("Plan the ReDoS sweeps"))
    pytest_i = next(i for i, n in enumerate(names) if n.startswith("Golden Record Integration Test"))
    assert plan_i < pytest_i
    plan_step, run_step = job["steps"][plan_i], job["steps"][pytest_i]
    assert plan_step["id"] == "sweeps" and "sweep_plan.py" in plan_step["run"]
    assert '--event "$GITHUB_EVENT_NAME"' in plan_step["run"]
    assert run_step["env"]["SWEEPS"] == "${{ steps.sweeps.outputs.mode }}"
    assert '[ "$SWEEPS" = "none" ]' in run_step["run"]  # only an explicit none deselects
    assert '-m "not golden_crucible and not redos_sweep"' in run_step["run"]
    checkout = next(s for s in job["steps"] if str(s.get("uses", "")).startswith("actions/checkout"))
    assert "pull_request" in str(checkout["with"]["fetch-depth"])  # the diff needs the merge base
    # the required aggregate and its needs are unchanged; the matrix gate never deselects
    assert wf["full-suite"]["needs"] == ["tested-tree", "full-suite-part"]
    gate = (ROOT / ".github" / "workflows" / "full-suite-gate.yml").read_text(encoding="utf-8")
    assert "redos_sweep" not in gate and "sweep_plan" not in gate
