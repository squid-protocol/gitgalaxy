"""#5164: the Mainframe Ground Truth plan -- a pull request that changes no ground-truth input proves nothing, any input runs it all.

The classifier is an allow-list of what the job does not read (ground_truth_plan.NON_INPUTS); these tests pin both
directions, the "when in doubt, run" default, and that nothing the job's tests reach is on the skip list.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(TOOLS))
import change_classifier as cc  # noqa: E402
import ground_truth_plan as gp  # noqa: E402
from gitgalaxy.core.source_text import read_source  # noqa: E402

yaml = pytest.importorskip("yaml")


@pytest.mark.parametrize(
    "path",
    [
        "README.md",
        "CLAUDE.md",
        "docs/ci.md",
        "docs/wiki/Home.md",
        "docs/research/third-party-material-policy.md",
        ".claude/rules/agent-memory.md",
        ".claude/skills/det-port/SKILL.md",
        ".github/workflows/smoke-test.yml",
        ".github/workflows/shepherd-reconcile.yml",
        ".github/dependabot.yml",
        "tests/tools/shepherd_gh.py",
        "tests/tools/box/heavy-run.sh",
        "tests/tools/box/ci_shepherd.py",
        "tests/tools/ci_rerun_stats.py",
        "tests/tools/test_shepherd_gh.py",
        "tests/tools/test_ground_truth_plan.py",
        "tests/extraction/languages/test_python_strict.py",
        "tests/core_engine/test_workflow_draft_gate.py",
        "tests/golden_master_audit/6._Parsed_Files/x.json",
        # #6278: the files of the PRs that ran the whole job for nothing
        "tests/tools/test_zos_probes.py",
        "tests/tools/ladder_refresh.py",
        "docs/language_status/zos_probes.json",
        "docs/language_status/cobol.md",
        ".claude/settings.json",
        ".claude/rules/mainframe-evidence-policy.md",
        ".claude/agents/gitgalaxy-pr-worker.md",
        ".claude/skills/ladder-slice/SKILL.md",
    ],
)
def test_a_file_the_job_does_not_read_is_not_an_input(path):
    assert not gp.is_input(path)
    assert gp.plan([path], "pull_request")["mode"] == "none"


@pytest.mark.parametrize(
    "path",
    [
        "gitgalaxy/core/detector.py",
        "gitgalaxy/standards/language_standards/languages/cobol.py",
        "gitgalaxy/tools/cobol_to_java/det/translator.py",
        "gitgalaxy/core/README.md",
        "gitgalaxy/galaxyscope.py",
        "tests/cobol_mainframe/answer_key/carddemo.json",
        "tests/cobol_mainframe/answer_key/README.md",
        "tests/cobol_mainframe/corpora.json",
        "tests/cobol_mainframe/ground_truth_ledger.json",
        "tests/cobol_mainframe/test_batch_jobs.py",
        "tests/equivalence/delta/case.json",
        "tests/tools/ground_truth_ledger.py",
        "tests/tools/mainframe_corpus.py",
        "tests/tools/cobol_answer_key.py",
        "tests/tools/evidence.py",
        "tests/tools/ground_truth_plan.py",
        "tests/tools/test_evidence_report.py",
        "tests/cultural_gauntlet/jdk.py",
        "tests/conftest.py",
        "docs/language_status/register/C5.md",
        "docs/language_status/cobolrt_rules.json",
        "docs/self_scan/ground_truth_history.jsonl",
        # #6278: docs/ outside language_status that a tool the job reaches names (the net is wide: over-approximate)
        "docs/self_scan/tri_comparison_ledger.json",
        "docs/zero_dependency_mode.md",
        ".github/workflows/mainframe-ground-truth.yml",
        ".github/workflows/det-sweep.yml",
        "pyproject.toml",
        "ci/requirements/test.txt",
        "some/new/unclassified/file.txt",
    ],
)
def test_an_input_or_an_unknown_file_runs_the_check(path):
    assert gp.is_input(path)
    p = gp.plan([path], "pull_request")
    assert p["mode"] == "full" and path in p["inputs"]


def test_one_input_among_docs_runs_the_check():
    assert gp.plan(["docs/ci.md", ".claude/x.md", "gitgalaxy/core/prism.py"], "pull_request")["mode"] == "full"


@pytest.mark.parametrize("event", ["push", "schedule", "workflow_dispatch"])
def test_every_event_but_a_pull_request_is_full(event):
    assert gp.plan(["docs/ci.md"], event)["mode"] == "full"
    assert gp.plan([], event)["mode"] == "full"


def test_an_empty_diff_is_full():
    assert gp.plan([], "pull_request")["mode"] == "full"


def test_cli_writes_the_mode_and_an_unreadable_diff_is_full(tmp_path):
    out = tmp_path / "o"
    run = [sys.executable, str(TOOLS / "ground_truth_plan.py"), "--github-output", str(out)]
    subprocess.run([*run, "--files", "docs/a.md"], check=True, capture_output=True)
    assert out.read_text() == "mode=none\n"
    out.write_text("")
    subprocess.run([*run, "--base", "no-such-ref-5164"], check=True, capture_output=True, cwd=ROOT)
    assert out.read_text() == "mode=full\n"


# --- the allow-list never hides what the job reads ---------------------------------------------------------------


def _closure():
    """Every tests/tools module the job's tests reach: named (as a word) in tests/cobol_mainframe/*.py, the ledger tool
    or a module already reached. Over-approximate on purpose: a false hit only makes the guard stricter."""
    mods = {p.stem: p for p in TOOLS.glob("*.py")}
    seeds = [
        *(ROOT / "tests" / "cobol_mainframe").glob("*.py"),
        TOOLS / "ground_truth_ledger.py",
        TOOLS / "mainframe_corpus.py",
    ]

    word_re = re.compile(r"\w+")
    mod_names = mods.keys()

    def named(path):
        if cc.PATTERN_HOLDERS.search(path.as_posix()):
            return set()  # a planner / the classifier lists paths to skip (#6278): it is imported, not run by the job
        return mod_names & set(word_re.findall(read_source(path).text))

    seen: set[str] = set()
    for s in seeds:
        seen |= named(s)
    todo = list(seen)
    while todo:
        for m in named(mods[todo.pop()]) - seen:
            seen.add(m)
            todo.append(m)
    return seen


def test_no_skippable_tool_is_reached_by_the_jobs_tests():
    reached = _closure()
    skippable = {p.stem for p in TOOLS.glob("*.py") if not gp.is_input(f"tests/tools/{p.name}")}
    skippable |= {Path(x).stem for x in gp.NON_INPUTS if x.startswith("tests/tools/") and "*" not in x}
    assert not (reached & skippable), (
        f"the ground-truth tests reach tools the planner skips: {sorted(reached & skippable)}"
    )


def test_every_named_non_input_exists():
    for pat in (*gp.NON_INPUTS, *gp.INPUTS):
        if "*" not in pat:
            assert (ROOT / pat).exists(), f"{pat} no longer exists: fix ground_truth_plan.py"


def test_the_workflow_reads_nothing_the_planner_skips():
    # every file a workflow step runs from tests/tools is an input (the planner is run, so it must be one)
    text = (ROOT / ".github/workflows/mainframe-ground-truth.yml").read_text(encoding="utf-8")
    for tool in set(re.findall(r"tests/tools/([A-Za-z0-9_]+\.(?:py|sh))", text)):
        assert gp.is_input(f"tests/tools/{tool}"), tool


def test_the_workflow_wires_the_plan_to_the_required_check():
    jobs = yaml.safe_load((ROOT / ".github/workflows/mainframe-ground-truth.yml").read_text(encoding="utf-8"))["jobs"]
    assert "plan" in jobs["ground-truth"]["needs"] and "plan" in jobs["ground-truth-part"]["needs"]
    assert "plan" in jobs["ground-truth-warm"]["needs"]
    assert "needs.plan.outputs.mode != 'none'" in jobs["ground-truth-warm"]["if"]
    assert "needs.plan.outputs.mode != 'none'" in jobs["ground-truth-part"]["if"]
    # the required check reports unless the run was cancelled, and passes on skipped parts only for mode none or a tested tree
    assert jobs["ground-truth"]["if"].startswith("${{ !cancelled()")
    env = jobs["ground-truth"]["steps"][0]["env"]
    assert env["MODE"] == "${{ needs.plan.outputs.mode }}"
    run = jobs["ground-truth"]["steps"][0]["run"]
    assert '"$MODE" = "none"' in run and 'ok "$PARTS"' in run and 'ok "$WARM"' in run
    # #5176: publish-history also needs the part that uploads the history (skipped parts upload nothing)
    assert jobs["publish-history"]["needs"] == ["ground-truth", "ground-truth-warm", "ground-truth-part"]


def test_the_6245_markdown_under_claude_proves_nothing():
    files = [
        ".claude/rules/mainframe-evidence-policy.md",
        ".claude/rules/python-test-traps.md",
        ".claude/agents/gitgalaxy-pr-worker.md",
        ".claude/skills/ladder-slice/SKILL.md",
    ]
    assert gp.plan(files, "pull_request")["mode"] == "none"


def test_the_zos_probe_pr_proves_nothing_but_a_register_edit_beside_it_does():
    zos = ["tests/tools/test_zos_probes.py", "docs/language_status/zos_probes.json"]
    assert gp.plan(zos, "pull_request")["mode"] == "none"
    assert gp.plan([*zos, "docs/language_status/register/A1.md"], "pull_request")["mode"] == "full"


def test_docs_outside_language_status_ask_the_classifier_too():
    assert gp.plan(["docs/ci.md", "docs/wiki/Home.md"], "pull_request")["mode"] == "none"
    assert gp.plan(["README.md"], "pull_request")["mode"] == "none"
    assert gp.plan(["docs/ci.md", "docs/zero_dependency_mode.md"], "pull_request")["mode"] == "full"


def test_an_unreadable_classifier_list_runs_the_check(monkeypatch):
    def broken():
        raise OSError("no list")

    monkeypatch.setattr(gp.change_classifier, "load", broken)
    assert gp.is_input("docs/language_status/zos_probes.json")
    assert gp.is_input("docs/ci.md")  # any docs/ path, not only language_status
