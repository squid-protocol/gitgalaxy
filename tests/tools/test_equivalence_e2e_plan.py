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
    ],
)
def test_a_path_outside_the_area_does_not(path):
    assert plan([path])["mode"] == "none"


def test_a_tool_outside_the_live_ground_truth_closure_does_not_run():
    # #7103: a pinned example went stale when a mainframe test began naming a tool that chains to it; derive one.
    reached = cc.ground_truth_scopes(workflow=True)
    outside = sorted(
        p.relative_to(REPO).as_posix()
        for p in TOOLS.glob("*.py")
        if not p.name.startswith(("test_", "conftest"))
        and not cc.PATTERN_HOLDERS.search(p.as_posix())
        and p.relative_to(REPO).as_posix() not in reached
    )
    assert outside, "every tests/tools module is now reached by the ground-truth job"
    assert plan([outside[0]])["mode"] == "none"


def test_every_tool_the_ground_truth_job_reaches_plans_a_run():
    # #7103 class: no pinned example to go stale; the whole input class is checked against the live closure.
    # (The plan may also run a tool the closure misses, e.g. an equivalence-only one, so only this direction holds.)
    reached = cc.ground_truth_scopes(workflow=True)
    wrong = []
    for p in TOOLS.glob("*.py"):
        rel = p.relative_to(REPO).as_posix()
        if p.name.startswith(("test_", "conftest")) or cc.PATTERN_HOLDERS.search(p.as_posix()):
            continue
        if rel in reached and not ep.in_area(rel, REFS):
            wrong.append(rel)
    assert not wrong, f"the ground-truth job reaches tools the equivalence plan skips: {sorted(wrong)}"


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


@pytest.mark.parametrize("event", ["schedule", "workflow_dispatch"])
def test_nightly_and_manual_always_run(event):
    assert plan(["README.md"], event)["mode"] == "run"


def test_a_main_push_is_planned_from_its_files():
    assert plan(["README.md"], "push")["mode"] == "none"
    assert plan(["gitgalaxy/tools/cobol_to_java/x.py"], "push")["mode"] == "run"
    assert plan([], "push")["mode"] == "run"  # no file list (over 300 files, API failure): fail open


def test_the_workflow_runs_after_a_merge_to_main():
    text = (REPO / ".github" / "workflows" / "equivalence-e2e.yml").read_text(encoding="utf-8")
    assert "push:\n    branches: [main]" in text
    assert "cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in text


def test_label_empty_diff_and_failure_all_run():
    assert plan(["tests/tools/test_shepherd_gh.py"], labels=["shepherd:full"])["mode"] == "run"
    assert plan([])["mode"] == "run"


def test_the_workflow_wires_the_planner_to_the_shards():
    text = (REPO / ".github" / "workflows" / "equivalence-e2e.yml").read_text(encoding="utf-8")
    assert "tests/tools/equivalence_e2e_plan.py" in text
    assert "needs.plan.outputs.mode == 'run'" in text.replace('"', "'")


# --- the db2 job (#6664) ---------------------------------------------------------------------------------------------
DB2 = ep.db2_inputs()


def plan_db2(files, event="pull_request", labels=()):
    return ep.plan(files, event, tuple(labels), REFS, DB2)["db2"]


def test_the_db2_closure_reaches_the_translator_the_harness_and_the_scripts_the_tests_run():
    modules, cases = DB2
    assert set(ep.DB2_FILES) <= modules
    for path in (
        "gitgalaxy/tools/cobol_to_java/det/sql.py",  # imported directly
        "tests/tools/equivalence_db2.py",
        "tests/tools/det_port.py",  # run as a subprocess (tools / "det_port.py")
        "tests/tools/equivalence.py",
    ):
        assert path in modules, path
    assert {"cbsa-inqacccu", "mortgage-cmort"} <= cases  # a -generated case's base, and a case read by path


@pytest.mark.parametrize(
    "path",
    [
        "gitgalaxy/tools/cobol_to_java/det/sql.py",
        "gitgalaxy/tools/cobol_to_java/det/cobolrt/sql/DetSql.java",  # a runtime file: not Python, so fail open
        "tests/cobol_mainframe/test_sql_whenever.py",
        "tests/equivalence/db2/whenever/cbl/WHENDEMO.cbl",  # shared Db2 harness data, not a case
        "tests/equivalence/cbsa-inqacccu/case.json",
        "tests/equivalence/det_sweep_coverage/cbsa-inqacccu.json",
        "tests/equivalence/gnucobol.Dockerfile",
        ".github/workflows/equivalence-e2e.yml",
        "ci/requirements/test.txt",
    ],
)
def test_an_input_of_the_db2_files_runs_db2(path):
    assert plan_db2([path, "README.md"]) == "run"


@pytest.mark.parametrize(
    "path",
    [
        "tests/cobol_mainframe/test_det_funcs.py",  # a shard file the Db2 files do not import
        "tests/equivalence/asynccc-crdtchk/case.json",  # a case no Db2 file names
        "tests/equivalence/det_sweep_coverage/asynccc-crdtchk.json",
    ],
)
def test_a_shard_only_change_skips_db2(path):
    assert path not in DB2[0]
    assert ep.plan([path], "pull_request", (), REFS, DB2)["mode"] == "run"
    assert plan_db2([path]) == "none"


@pytest.mark.parametrize("event", ["schedule", "workflow_dispatch"])
def test_nightly_and_manual_always_run_db2(event):
    assert plan_db2(["README.md"], event) == "run"


def test_label_and_empty_diff_run_db2_and_no_area_skips_it():
    assert plan_db2(["tests/cobol_mainframe/test_det_funcs.py"], labels=["shepherd:full"]) == "run"
    assert plan_db2([]) == "run"
    assert plan_db2(["README.md"]) == "none"


def test_the_db2_files_are_the_ones_the_workflow_splits_off():
    text = (REPO / ".github" / "workflows" / "equivalence-e2e.yml").read_text(encoding="utf-8")
    for f in ep.DB2_FILES:
        assert f"--ignore={f}" in text, f"the shards do not --ignore {f}"
        assert text.count(f) >= 2, f"the db2 job does not run {f}"
    flat = text.replace('"', "'")
    assert "needs.plan.outputs.db2 != 'none'" in flat
    assert "db2: ${{ steps.plan.outputs.db2 }}" in text


# --- scope zos: a test_zos_probes-only change runs one shard, one file -------------------------------------------------
def test_a_zos_probes_only_change_is_scoped_to_one_file():
    for files in (["tests/tools/test_zos_probes.py"], ["tests/tools/zos_probes.py", "README.md"]):
        p = plan(files)
        assert (p["mode"], p["db2"], p.get("scope")) == ("run", "none", "zos")


def test_a_doc_only_the_zos_test_reads_is_scoped_too():
    docs = [
        d
        for d, readers in REFS.items()
        if "*" not in d and d.startswith("docs/") and set(readers) == {"tests/tools/test_zos_probes.py"}
    ]
    for d in docs:
        assert plan([d]).get("scope") == "zos"


@pytest.mark.parametrize(
    "files",
    [
        ["tests/tools/test_zos_probes.py", "tests/cobol_mainframe/test_det_funcs.py"],
        ["tests/tools/test_zos_probes.py", "gitgalaxy/tools/cobol_to_java/det/translator.py"],
        ["tests/tools/test_zos_probes.py", ".github/workflows/equivalence-e2e.yml"],
        ["tests/tools/zos_probes.py", "tests/tools/equivalence.py"],
    ],
)
def test_anything_else_in_the_area_keeps_all_shards(files):
    assert plan(files).get("scope") is None


def test_label_and_nightly_never_narrow():
    assert plan(["tests/tools/test_zos_probes.py"], labels=["shepherd:full"]).get("scope") is None
    assert plan(["tests/tools/test_zos_probes.py"], "schedule").get("scope") is None


def test_the_workflow_narrows_the_shards_on_scope_zos():
    text = (REPO / ".github" / "workflows" / "equivalence-e2e.yml").read_text(encoding="utf-8")
    assert "scope: ${{ steps.plan.outputs.scope }}" in text
    assert "needs.plan.outputs.scope == 'zos' && '{\"group\":[1]}' || needs.plan.outputs.matrix" in text
    assert text.count("needs.plan.outputs.scope == 'zos'") >= 2 and "scope != 'zos'" in text
