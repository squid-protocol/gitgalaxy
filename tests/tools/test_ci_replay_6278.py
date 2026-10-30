"""#6278 acceptance replay: three real path sets through the classifier and every PR workflow's plan.

* #6245's file list (4 Markdown files under `.claude/`, no code) and a `README.md`-only change run at most 3 jobs.
* a `docs/language_status/register/*.md` change runs the tests that read it (and the ground-truth job, whose code reads it).
* a `tests/tools/test_zos_probes.py`-only change runs no ground-truth, det-sweep or db2 job.

A workflow with a plan is asked through its planner; one without a plan is asked through its `on.pull_request.paths`
filter (GitHub's glob rules). A workflow this test cannot place fails the test, so a new PR workflow must be classified
here (a planner or a path filter) and cannot silently join the always-run set.
"""

import re
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(TOOLS))
import accuracy_audit_plan as aap  # noqa: E402
import assess_install_plan as aip  # noqa: E402
import audit_skip_plan as asp  # noqa: E402
import det_sweep_plan as dsp  # noqa: E402
import equivalence_e2e_plan as e2e  # noqa: E402
import graph_accuracy_plan as gap  # noqa: E402
import ground_truth_plan as gtp  # noqa: E402
import suite_select_plan as ssp  # noqa: E402
import sweep_plan as swp  # noqa: E402

yaml = pytest.importorskip("yaml")

EVENT = "pull_request"
WORKFLOWS = ROOT / ".github" / "workflows"
PR_6245 = [
    ".claude/agents/gitgalaxy-pr-worker.md",
    ".claude/rules/python-test-traps.md",
    ".claude/rules/test-writing.md",
    ".claude/skills/det-port/SKILL.md",
]
README = ["README.md"]
REGISTER = ["docs/language_status/register/A1.md"]
ZOS = ["tests/tools/test_zos_probes.py"]


def no_places(_path):
    return []


# Workflows whose PR runs are decided by a plan job: name -> the job names that plan can start. A planner answer "run".
PLANNED = {
    "mainframe-ground-truth": lambda f: gtp.plan(f, EVENT)["mode"] != "none",
    "det-sweep": lambda f: dsp.plan(f, EVENT, dsp.case_dirs())["mode"] != "none",
    "equivalence-e2e": lambda f: e2e.plan(f, EVENT)["mode"] != "none",
    "smoke-test": lambda f: ssp.plan(f, EVENT)["mode"] != "skip",
    "gitgalaxy": lambda f: asp.plan(f, EVENT, "gate")["mode"] != "none",
    "small-audits": lambda f: asp.plan(f, EVENT, "small")["mode"] != "none",
    "mypy-audit": lambda f: asp.plan(f, EVENT, "lint")["mode"] != "none",
    "ruff-audit": lambda f: asp.plan(f, EVENT, "lint")["mode"] != "none",
    "graph-accuracy-audit": lambda f: bool(gap.plan(f, EVENT)["gates"]),
    "call-graph-accuracy-audit": lambda f: aap.plan(f, EVENT, aap.CALL, no_places)["run"],
    "detection-accuracy-audit": lambda f: aap.plan(f, EVENT, aap.DETECTION, no_places)["run"],
    "tree-sitter-accuracy-audit": lambda f: aap.plan(f, EVENT, aap.TREE, no_places)["run"],
    "tri-comparison-audit": lambda f: aap.plan(f, EVENT, aap.TRI, no_places)["run"],
    "ports-compile": lambda f: aip.plan([("M", p) for p in f], EVENT)["run"],
}
# Planned workflows that start no PR job of their own beyond the planned ones above (a sub-plan of another entry, a
# history job that is push-only, or a planner for shards inside a workflow listed above).
SUB_PLANNED = {
    "cics-crucible",
    "doom-rosetta",
    "evidence-refresh",
    "full-suite-gate",
    "graph-comparison-history",
    "tree-sitter-accuracy-history",
    "tri-comparison-history",
}


def glob_regex(pattern: str) -> re.Pattern:
    """GitHub's filter glob: `**` crosses `/`, `*` and `?` do not."""
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif pattern.startswith("**", i):
            out, i = out + ".*", i + 2
        elif pattern[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif pattern[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(pattern[i]), i + 1
    return re.compile(out + r"\Z")


def pr_trigger(name: str) -> dict | None:
    doc = yaml.safe_load((WORKFLOWS / f"{name}.yml").read_text(encoding="utf-8"))
    on = doc.get(True, doc.get("on"))  # PyYAML reads the key `on` as True
    if isinstance(on, str):
        on = {on: None}
    elif isinstance(on, list):
        on = dict.fromkeys(on)
    if not isinstance(on, dict) or "pull_request" not in on:
        return None
    return on["pull_request"] or {}


def path_filtered_runs(name: str, files: list[str]) -> bool:
    trig = pr_trigger(name) or {}
    paths, ignore = trig.get("paths"), trig.get("paths-ignore")
    if paths:
        pos = [glob_regex(p) for p in paths if not p.startswith("!")]
        neg = [glob_regex(p[1:]) for p in paths if p.startswith("!")]
        return any(any(r.match(f) for r in pos) and not any(r.match(f) for r in neg) for f in files)
    if ignore:
        return any(not any(glob_regex(p).match(f) for p in ignore) for f in files)
    return True


def runs(files: list[str]) -> set[str]:
    """Every PR workflow that starts a job of its own for `files`."""
    out = set()
    for path in sorted(WORKFLOWS.glob("*.yml")):
        name = path.stem
        if pr_trigger(name) is None or name in SUB_PLANNED or name.startswith("shepherd-"):
            continue
        ran = PLANNED[name](files) if name in PLANNED else path_filtered_runs(name, files)
        if ran:
            out.add(name)
    return out


def test_every_pr_workflow_is_classified():
    """A PR workflow with a plan job is in PLANNED; one without is held to a path filter (never an unfiltered run)."""
    unfiltered = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        name = path.stem
        trig = pr_trigger(name)
        if trig is None or name in PLANNED or name in SUB_PLANNED or name.startswith("shepherd-"):
            continue
        if not (trig.get("paths") or trig.get("paths-ignore")):
            unfiltered.append(name)
    assert unfiltered == [] or set(unfiltered) <= {"deploy-docs", "referee-panel"}, (
        f"PR workflow(s) with neither a plan nor a path filter run on every PR: {unfiltered}"
    )


@pytest.mark.parametrize("files", [PR_6245, README], ids=["pr-6245", "readme-only"])
def test_prose_change_runs_at_most_three_jobs(files):
    ran = runs(files)
    assert len(ran) <= 3, f"{files} starts {len(ran)} workflows: {sorted(ran)}"
    assert not ran & {"mainframe-ground-truth", "det-sweep", "equivalence-e2e", "ruff-audit", "mypy-audit"}


@pytest.mark.parametrize("files", [PR_6245, README], ids=["pr-6245", "readme-only"])
def test_prose_change_runs_only_the_tests_that_read_it(files):
    plan = ssp.plan(files, EVENT)
    assert plan["mode"] == "select", plan
    assert 0 < len(plan["paths"]) <= 30, plan["paths"]
    assert swp.plan(files, EVENT)["mode"] == "none"


def test_register_change_runs_the_tests_that_read_it():
    plan = ssp.plan(REGISTER, EVENT)
    assert plan["mode"] == "select", plan
    paths = set(plan["paths"])
    assert "tests/cobol_mainframe" in paths
    assert "tests/tools/test_generated_docs.py" in paths
    assert "tests/tools/test_status_page_snapshots.py" in paths
    # ground-truth code (the register is read by cobolrt_rules / register.py) and the equivalence shards read it too
    assert gtp.plan(REGISTER, EVENT)["mode"] == "full"
    assert e2e.plan(REGISTER, EVENT)["mode"] == "run"
    # ... but it is not a Db2 input, an engine input, or lintable code
    assert e2e.plan(REGISTER, EVENT)["db2"] == "none"
    assert asp.plan(REGISTER, EVENT, "lint")["mode"] == "none"
    assert "mainframe-ground-truth" in runs(REGISTER)


def test_zos_probes_test_runs_no_ground_truth_det_or_db2():
    assert gtp.plan(ZOS, EVENT)["mode"] == "none"
    det = dsp.plan(ZOS, EVENT, dsp.case_dirs())
    assert det["mode"] == "none" and not det["db2_cases"] and not det["cases"], det
    e2e_plan = e2e.plan(ZOS, EVENT)
    assert e2e_plan["db2"] == "none", e2e_plan
    assert e2e_plan.get("scope") == "zos", e2e_plan  # one shard, the file's own reader
    ran = runs(ZOS)
    assert not ran & {"mainframe-ground-truth", "det-sweep"}, sorted(ran)
    assert not ran & {"cics-crucible", "ports-compile", "java-compile", "estate-crucible", "golden-crucible"}, sorted(
        ran
    )
    assert ssp.plan(ZOS, EVENT)["mode"] == "select"


@pytest.mark.parametrize("files", [PR_6245, README, REGISTER, ZOS], ids=["pr-6245", "readme", "register", "zos"])
def test_a_non_pull_request_event_still_runs_everything(files):
    """The nightly / push net is untouched by the skips above."""
    assert gtp.plan(files, "schedule")["mode"] == "full"
    det = dsp.plan(files, "schedule", dsp.case_dirs())
    assert det["mode"] == "full" and det["cases"] == "all"
    assert ssp.plan(files, "schedule")["mode"] == "full"
