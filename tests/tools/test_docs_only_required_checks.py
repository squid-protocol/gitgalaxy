"""#7963: a docs-only record PR (registers, blockers_history.jsonl) skips heavy work but every required check of the
`main: required checks` ruleset (#4825) still reports. The plans say none / select, and each required aggregate job
accepts the skipped parts that plan leaves behind. No workflow edit: this pins the arrangement."""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import change_classifier as cc  # noqa: E402
import equivalence_e2e_plan as ep  # noqa: E402
import ground_truth_plan as gp  # noqa: E402
import shepherd_gh  # noqa: E402
import suite_select_plan as sp  # noqa: E402

REPO = TOOLS.parents[1]
WF = REPO / ".github" / "workflows"
DOCS = ["docs/language_status/register/A1.md", "docs/language_status/blockers_history.jsonl"]
CODE = [*DOCS, "gitgalaxy/core/prism.py"]


def det_mode(files):
    out = subprocess.run(
        [sys.executable, str(TOOLS / "det_sweep_plan.py"), "--event", "pull_request", "--files", *files],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO,
    ).stdout
    return json.loads(out[out.index("{") :])["mode"]


def test_docs_only_plans_skip_the_heavy_gates():
    assert gp.plan(DOCS, "pull_request")["mode"] == "none"
    assert ep.plan(DOCS, "pull_request", (), cc.load())["mode"] == "none"
    assert sp.plan(DOCS, "pull_request", (), cc.load())["mode"] == "select"
    assert det_mode(DOCS) == "none"


def test_a_code_file_in_the_diff_is_never_the_lane():
    assert gp.plan(CODE, "pull_request")["mode"] != "none"
    assert sp.plan(CODE, "pull_request", (), cc.load())["mode"] == "full"


@pytest.mark.parametrize(
    ("workflow", "job", "tolerance"),
    [
        ("mainframe-ground-truth.yml", "ground-truth", r'"\$MODE" = "none"'),
        ("smoke-test.yml", "full-suite", r'"\$PLAN" = "skip"'),
    ],
)
def test_a_required_aggregate_job_accepts_the_skipped_parts(workflow, job, tolerance):
    text = (WF / workflow).read_text(encoding="utf-8")
    body = text[text.index(f"\n  {job}:") :].split("\n\n")[0]
    assert "!cancelled()" in body and "draft == false" in body  # runs on every non-draft PR, never skipped
    assert re.search(tolerance, body)


def test_det_reports_under_a_none_plan():
    text = (WF / "det-sweep.yml").read_text(encoding="utf-8")
    body = text[text.index("\n  det:") :].split("\n\n")[0]
    assert "!cancelled()" in body and "draft == false" in body
    assert re.search(r"pull_request:\s+#[^\n]*no path filter", text)


@pytest.mark.parametrize("workflow", ["mypy-audit.yml", "ruff-audit.yml"])
def test_the_audit_checks_have_no_path_filter(workflow):
    text = (WF / workflow).read_text(encoding="utf-8")
    assert not re.search(r"^\s+paths(-ignore)?:", text, re.M)


def test_every_required_check_is_a_job_of_some_workflow():
    jobs = {m for p in WF.glob("*.yml") for m in re.findall(r"^  ([\w-]+):\s*$", p.read_text(encoding="utf-8"), re.M)}
    assert set(shepherd_gh.REQUIRED_CHECKS) <= jobs


MUT = [
    "tests/equivalence/det_mutation/carddemo-cbstm03a.json",
    "tests/equivalence/det_mutation_survivors/carddemo-cbstm03a.json",
]


def test_mutation_data_only_skips_the_shards_and_selects_its_readers():
    """#7963 option (b): the shards skip, the suite selects, ground truth stays full (its tests read the data)."""
    assert ep.plan(MUT, "pull_request", (), cc.load())["mode"] == "none"
    out = sp.plan(MUT, "pull_request", (), cc.load())
    assert out["mode"] == "select" and out["paths"]
    assert gp.plan(MUT, "pull_request")["mode"] == "full"


def test_a_code_file_beside_mutation_data_is_still_the_full_lane():
    assert (
        ep.plan([*MUT, "gitgalaxy/tools/cobol_to_java/det/translate.py"], "pull_request", (), cc.load())["mode"]
        == "run"
    )
    assert sp.plan([*MUT, "gitgalaxy/core/prism.py"], "pull_request", (), cc.load())["mode"] == "full"


def test_no_shard_test_reads_the_mutation_data():
    """The claim behind the shard skip: no file the shards run names a mutation directory."""
    import equivalence_e2e_select as sel

    for rel in sel.select():
        text = (REPO / rel).read_text(encoding="utf-8")
        assert "det_mutation" not in text, rel
