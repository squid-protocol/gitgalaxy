"""#6672: the assess clean-install step of ports-compile.yml runs on a PR only when a change can break the install."""

import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import assess_install_plan as ap  # noqa: E402

REPO = TOOLS.parents[1]
SHIPPED = ap.shipped_globs()


def plan(*changes, event="pull_request"):
    return ap.plan(list(changes), event, SHIPPED)["run"]


@pytest.mark.parametrize(
    "change",
    [
        ("modified", "pyproject.toml"),
        ("modified", "MANIFEST.in"),
        ("modified", "scripts/check_assess_install.py"),
        ("modified", "gitgalaxy/cli.py"),
        ("modified", "gitgalaxy/tools/readiness/assess.py"),
        ("modified", "tests/cobol_mainframe/corpora.json"),
        ("added", "gitgalaxy/tools/cobol_to_java/cics_task_web.py"),  # a new module (#6630)
        ("added", "gitgalaxy/standards/new_table.json"),  # a new data file package-data may not ship
        ("removed", "gitgalaxy/core/aperture.py"),
        ("renamed", "gitgalaxy/core/renamed_module.py"),
        ("modified", "gitgalaxy/standards/fact_channel_confidence.json"),  # shipped data
        ("modified", "gitgalaxy/tools/cobol_to_java/det/cobolrt/Storage.java"),  # shipped runtime
        ("modified", "gitgalaxy/tools/cobol_to_java/det/copy/SQLCA.cpy"),
    ],
)
def test_a_change_that_can_break_the_install_runs_it(change):
    assert plan(change, ("modified", "README.md"))


@pytest.mark.parametrize(
    "change",
    [
        ("modified", "gitgalaxy/core/detector.py"),  # an edited module: shipped already, tested by the other jobs
        ("modified", "gitgalaxy/standards/language_addition_costs.jsonl"),  # data no package-data glob ships
        ("modified", "gitgalaxy/tools/readiness/README.md"),  # prose
        ("added", "gitgalaxy/tools/new_tool/README.md"),
        ("modified", "tests/cobol_mainframe/test_det_funcs.py"),
        ("added", "tests/equivalence/new-case/case.json"),
    ],
)
def test_a_change_that_cannot_skips_it(change):
    assert not plan(change)


@pytest.mark.parametrize("event", ["push", "schedule", "workflow_dispatch"])
def test_every_other_event_runs_it(event):
    assert plan(("modified", "gitgalaxy/core/detector.py"), event=event)


def test_an_unreadable_or_empty_list_runs_it():
    assert ap.plan(None, "pull_request", SHIPPED)["run"]
    assert ap.plan([], "pull_request", SHIPPED)["run"]


def test_the_shipped_globs_are_pyprojects_package_data_and_match_real_files():
    assert "gitgalaxy/standards/fact_channel_confidence.json" in SHIPPED
    for glob in SHIPPED:
        assert list(REPO.glob(glob)), f"package-data glob {glob} matches no file: the planner would never see it"


def test_the_cli_reads_a_tsv_and_writes_the_output(tmp_path):
    tsv = tmp_path / "files.tsv"
    tsv.write_text("modified\tgitgalaxy/core/detector.py\nmodified\tdocs/ci.md\n", encoding="utf-8")
    out = tmp_path / "out"
    cmd = [sys.executable, str(TOOLS / "assess_install_plan.py"), "--files-tsv", str(tsv), "--github-output", str(out)]
    subprocess.run(cmd, check=True, capture_output=True)  # noqa: S603
    assert out.read_text(encoding="utf-8") == "run=false\n"
    cmd = [sys.executable, str(TOOLS / "assess_install_plan.py"), "--github-output", str(out)]  # no list: run
    subprocess.run(cmd, check=True, capture_output=True)  # noqa: S603
    assert out.read_text(encoding="utf-8").endswith("run=true\n")


def test_the_workflow_gates_the_step_on_the_plan():
    text = (REPO / ".github" / "workflows" / "ports-compile.yml").read_text(encoding="utf-8")
    assert "tests/tools/assess_install_plan.py" in text
    assert "if: steps.assess_plan.outputs.run != 'false'" in text  # a missing output (failed plan) still runs it
    assert "pull-requests: read" in text
