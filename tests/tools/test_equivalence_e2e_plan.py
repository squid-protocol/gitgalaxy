"""#5954 slice 2: the EQUIVALENCE_E2E shards run on a PR only when it touches the COBOL / mainframe / equivalence area
(owner condition, gated through the #6278 classifier); main, nightly, manual runs and every doubt run them."""

import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import change_classifier as cc  # noqa: E402
import equivalence_e2e_plan as ep  # noqa: E402

REPO = TOOLS.parents[1]
REFS = cc.load()


def plan(files, event="pull_request", labels=()):
    return ep.plan(files, event, tuple(labels), REFS)


@pytest.mark.parametrize(
    "path",
    [
        "gitgalaxy/tools/cobol_to_java/det/translator.py",
        "gitgalaxy/standards/cics/commands/link.py",
        "tests/cobol_mainframe/test_det_funcs.py",
        "tests/equivalence/some-case/case.json",
        "tests/tools/equivalence_common.py",
        "tests/tools/test_zos_probes.py",
        ".github/workflows/equivalence-e2e.yml",
        "ci/requirements/test.txt",
    ],
)
def test_a_path_in_the_area_runs(path):
    assert plan([path, "README.md"])["mode"] == "run"


@pytest.mark.parametrize(
    "path",
    [
        "gitgalaxy/standards/language_standards/languages/rust.py",
        "tests/extraction/languages/test_rust_strict.py",
        "tests/tools/test_shepherd_gh.py",
        "tests/tools/box/heavy-run.sh",
        ".github/workflows/rosetta-audit.yml",
        "tests/tools/rosetta_audit.py",
    ],
)
def test_a_path_outside_the_area_does_not(path):
    assert plan([path])["mode"] == "none"


def test_a_test_tool_the_cobol_tests_reach_runs():
    assert cc.runs_in_ground_truth("tests/tools/equivalence.py")
    assert plan(["tests/tools/equivalence.py"])["mode"] == "run"


def test_a_doc_the_cobol_tests_open_runs():
    reader_docs = [
        p for p, scopes in REFS.items() if "tests/cobol_mainframe" in scopes and "*" not in p and p.startswith("docs/")
    ]
    assert reader_docs, "the classifier lists no doc read by tests/cobol_mainframe"
    path = reader_docs[0]
    assert plan([path])["mode"] == "run"


@pytest.mark.parametrize("event", ["push", "schedule", "workflow_dispatch"])
def test_main_nightly_and_manual_always_run(event):
    assert plan(["README.md"], event)["mode"] == "run"


def test_label_empty_diff_and_failure_all_run():
    assert plan(["tests/tools/test_shepherd_gh.py"], labels=["shepherd:full"])["mode"] == "run"
    assert plan([])["mode"] == "run"


def test_the_workflow_wires_the_planner_to_the_shards():
    text = (REPO / ".github" / "workflows" / "equivalence-e2e.yml").read_text(encoding="utf-8")
    assert "tests/tools/equivalence_e2e_plan.py" in text
    assert "needs.plan.outputs.mode == 'run'" in text.replace('"', "'")
