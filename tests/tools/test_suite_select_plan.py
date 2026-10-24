"""#6278 item 3: the Smoke full-suite selection -- prose skips, test-read docs / agent config run only their readers,
everything else (and every doubt) runs the whole suite. Real changed-file lists pin both directions."""

import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import change_classifier as cc  # noqa: E402
import suite_select_plan as sp  # noqa: E402

REFS = cc.load()


def plan(files, event="pull_request", labels=()):
    return sp.plan(files, event, tuple(labels), REFS)


def test_prose_nothing_reads_skips():
    # today the whole-tree readers (`**/*.md`, `docs/**`: post_merge_dispatch, test_workflow_inputs) name every doc, so
    # no real file is prose yet; lift them out to pin the skip for the day those tests stop enumerating
    refs = {k: v for k, v in REFS.items() if k not in ("**/*.md", "docs/**")}
    p = sp.plan(["docs/zz_unread_note.md"], "pull_request", (), refs)
    assert p["mode"] == "skip" and p["paths"] == []


def test_today_every_doc_is_read_by_the_enumerating_tests():
    p = plan(["docs/zz_unread_note.md"])
    assert p["mode"] == "select" and "tests/tools/test_workflow_inputs.py" in p["paths"]


def test_readme_only_runs_its_reader():
    p = plan(["README.md"])
    assert p["mode"] == "select"
    assert "tests/core_engine" in p["paths"]


def test_register_doc_runs_the_tests_that_read_it():
    p = plan(["docs/language_status/register/x.md"])
    assert p["mode"] == "select"
    assert "tests/cobol_mainframe" in p["paths"]
    assert "tests/tools/test_generated_docs.py" in p["paths"]


def test_agent_config_runs_only_tests_that_name_it():
    p = plan([".claude/agents/gitgalaxy-pr-worker.md", ".claude/rules/test-writing.md"])
    assert p["mode"] == "select"
    assert "tests/tools/test_workflow_inputs.py" in p["paths"]
    assert all(t.startswith("tests/tools/test_") for t in p["paths"])


def test_selected_paths_exist_and_have_no_nested_duplicates():
    root = TOOLS.parents[1]
    p = plan(["docs/language_status/register/x.md", "README.md"])
    assert all((root / t).exists() for t in p["paths"])
    assert not any(a != b and b.startswith(a + "/") for a in p["paths"] for b in p["paths"])


@pytest.mark.parametrize(
    "files",
    [
        ["gitgalaxy/core/prism.py"],
        ["tests/tools/test_zos_probes.py"],
        ["tests/tools/equivalence.py"],
        [".github/workflows/smoke-test.yml"],
        ["pyproject.toml"],
        ["README.md", "gitgalaxy/core/prism.py"],  # one engine file beside a doc
        ["docs/language_status/register/x.md", "tests/tools/change_classifier.py"],
    ],
)
def test_anything_else_runs_everything(files):
    p = plan(files)
    assert p["mode"] == "full" and p["paths"] == []


@pytest.mark.parametrize("event", ["push", "schedule", "workflow_dispatch"])
def test_other_events_run_everything(event):
    assert plan(["README.md"], event)["mode"] == "full"


def test_full_label_and_empty_diff_run_everything():
    assert plan(["README.md"], labels=["shepherd:full"])["mode"] == "full"
    assert plan([])["mode"] == "full"


def test_a_reader_no_test_maps_to_runs_everything():
    refs = {"docs/zz.md": ["gitgalaxy"], "docs/yy.md": ["tests/signal_contract_audit.py"]}
    for f in ("docs/zz.md", "docs/yy.md"):
        assert sp.plan([f], "pull_request", (), refs)["mode"] == "full"


def test_helper_scope_runs_the_tests_that_name_it():
    assert "tests/tools/test_post_merge_dispatch.py" in sp.test_target("tests/tools/post_merge_dispatch.py")
    assert sp.test_target("tests/tools/test_sweep_plan.py") == ["tests/tools/test_sweep_plan.py"]
    assert sp.test_target("tests/cobol_mainframe") == ["tests/cobol_mainframe"]
    assert sp.test_target("gitgalaxy") is None


def test_the_cli_writes_the_github_output(tmp_path):
    out = tmp_path / "o"
    sys.argv = ["x", "--files", "README.md", "--github-output", str(out)]
    assert sp.main() == 0
    assert out.read_text().splitlines() == ["mode=select", "paths=tests/core_engine"]


def _smoke():
    yaml = pytest.importorskip("yaml")
    path = TOOLS.parents[1] / ".github" / "workflows" / "smoke-test.yml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_the_workflow_wires_the_plan_to_skip_select_and_full():
    wf = _smoke()
    jobs = wf["jobs"]
    plan_job = jobs["suite-plan"]
    plan_step = next(s for s in plan_job["steps"] if s.get("id") == "plan")
    assert "suite_select_plan.py" in plan_step["run"] and "--github-output" in plan_step["run"]
    assert '"mode=full"' not in plan_step["run"] or "|| {" in plan_step["run"]  # a planner failure falls back to full
    assert "shepherd:full" in plan_step["run"] or "--labels" in plan_step["run"]
    assert plan_job["outputs"] == {"mode": "${{ steps.plan.outputs.mode }}", "paths": "${{ steps.plan.outputs.paths }}"}
    # only a pull request is planned; every other event leaves mode empty, which is the full suite
    assert "pull_request" in plan_job["if"]
    part = jobs["full-suite-part"]
    assert "suite-plan" in part["needs"] and "!= 'skip'" in part["if"]  # skip starts no part
    pytest_step = next(s for s in part["steps"] if s.get("name", "").startswith("Golden Record Integration Test"))
    assert "matrix.group == 1" in pytest_step["if"] and "!= 'select'" in pytest_step["if"]
    assert '[ "$PLAN" = "select" ]' in pytest_step["run"] and "$SELECTED" in pytest_step["run"]
    # the required check passes on a skipped part only for a skip plan (or the tested-tree gate)
    agg = jobs["full-suite"]
    assert "suite-plan" in agg["needs"]
    assert 'test "$PLAN" = "skip"' in agg["steps"][0]["run"]
    # the suite-time budget never totals a select / skip run's partial times
    assert "suite-plan.outputs.mode == 'full'" in jobs["suite-time"]["if"]


def test_the_pull_request_trigger_no_longer_ignores_docs():
    wf = _smoke()
    assert "paths-ignore" not in wf[True]["pull_request"]  # the planner decides (register edits run their readers)
    assert wf[True]["push"]["paths-ignore"] == ["docs/**"]  # push keeps its behaviour


def test_replay_of_known_change_lists():
    # #6245's file list is not provable here without its diff; the three shapes the workflow relies on:
    assert plan(["docs/language_status/register/x.md"])["mode"] == "select"
    assert plan(["gitgalaxy/core/detector.py"])["mode"] == "full"
    assert plan([], "pull_request")["mode"] == "full"  # a short or empty file list is full
