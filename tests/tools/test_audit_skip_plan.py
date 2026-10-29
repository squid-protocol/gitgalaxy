"""#6278 slice 4: ruff-audit, mypy-audit and small-audits skip their install and audit only for docs they cannot read."""

import json
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import audit_skip_plan as ap

WORKFLOWS = TOOLS.parents[1] / ".github" / "workflows"
# #6245 (the weekly agent retro): agent config and skills, nothing else
PR_6245 = [
    ".claude/agents/gitgalaxy-pr-worker.md",
    ".claude/rules/python-test-traps.md",
    ".claude/rules/test-writing.md",
    ".claude/skills/det-port/SKILL.md",
]


def mode(files, profile="lint", event="pull_request", labels=()):
    return ap.plan(files, event, profile, labels)["mode"]


def test_replays():
    assert mode(PR_6245) == "none"  # agent config only: the lint audits do not run
    assert mode(["README.md"]) == "none"
    assert mode(["README.md"], "small") == "none"  # a test opens the README; the four small audits do not
    assert mode(["tests/tools/test_zos_probes.py"]) == "full"  # a .py is always linted
    assert mode(["docs/language_status/register/x.md"]) == "none"


def test_small_audits_skip_docs_they_do_not_open_but_run_for_the_one_they_do():
    assert mode(PR_6245, "small") == "none"
    assert mode(["docs/language_status/register/x.md"], "small") == "none"
    assert (
        mode(["docs/signal_contracts.md"], "small") == "full"
    )  # signal_contract_audit.py --ci renders and compares it
    assert mode(["docs/signal_contracts.md", "README.md"], "small") == "full"
    assert (
        mode(["gitgalaxy/standards/how_to_add_a_language.md"], "small") == "full"
    )  # engine area: its schema comments are read


@pytest.mark.parametrize("profile", sorted(ap.PROFILES))
@pytest.mark.parametrize(
    "path",
    [
        "docs/helper.py",
        ".claude/hooks/check.sh",
        ".claude/settings.json",
        "docs/data.json",
        "docs/self_scan/history.jsonl",
        "pyproject.toml",
        "ci/requirements/lint.txt",
        "tests/ruff_audit_baseline.json",
        "tests/ruff_audit.py",
        "gitgalaxy/core/README.md",
        ".github/workflows/ruff-audit.yml",
        "tests/tools/audit_skip_plan.py",
        "setup.py",
    ],
)
def test_code_and_config_always_run_the_audits(profile, path):
    assert mode([path], profile) == "full"
    assert mode(["README.md", path], profile) == "full"


@pytest.mark.parametrize("profile", sorted(ap.PROFILES))
def test_doubt_runs_the_audits(profile):
    assert mode([], profile) == "full"
    assert mode(["README.md"], profile, labels=(ap.FULL_LABEL,)) == "full"
    for event in ("push", "schedule", "workflow_dispatch", ""):
        assert mode(["README.md"], profile, event) == "full"


def test_a_failed_diff_runs_the_audits(monkeypatch, tmp_path, capsys):
    def boom(base):
        raise RuntimeError("bad revision")

    monkeypatch.setattr(ap, "changed_files", boom)
    out = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", ["x", "--profile", "lint", "--github-output", str(out)])
    assert ap.main() == 0
    assert out.read_text() == "mode=full\n"
    assert "cannot diff" in capsys.readouterr().out


def test_the_cli_writes_the_mode(monkeypatch, tmp_path, capsys):
    out = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", ["x", "--profile", "lint", "--files", "README.md", "--github-output", str(out)])
    assert ap.main() == 0
    assert out.read_text() == "mode=none\n"
    assert json.loads(capsys.readouterr().out)["mode"] == "none"


def test_gate_profile_skips_unread_prose_only():
    assert mode(PR_6245, "gate") == "none"
    assert mode(["README.md"], "gate") == "none"
    assert mode(["docs/language_status/register/x.md"], "gate") == "none"
    assert mode(["docs/x.md", "gitgalaxy/core/detector.py"], "gate") == "full"
    assert mode(["action.yml"], "gate") == "full"  # the gates are the action: its config is never skipped


def test_the_pre_gate_asks_the_plan_instead_of_ignoring_docs():
    yaml = pytest.importorskip("yaml")
    wf = yaml.safe_load((WORKFLOWS / "gitgalaxy.yml").read_text(encoding="utf-8"))
    assert "paths-ignore" not in wf[True]["pull_request"] and "paths" not in wf[True]["pull_request"]
    job = wf["jobs"]["pre-gate"]
    assert job["permissions"] == {"contents": "read", "pull-requests": "read", "issues": "read"}
    steps = job["steps"]
    plan = next(i for i, s in enumerate(steps) if s.get("id") == "plan")
    assert "--profile gate" in steps[plan]["run"] and "audit_skip_plan.py" in steps[plan]["run"]
    assert '|| echo "mode=full"' in steps[plan]["run"]  # a planner failure runs the gates
    for s in steps[plan + 1 :]:
        assert "steps.plan.outputs.mode != 'none'" in s["if"], s["name"]


@pytest.mark.parametrize(
    ("name", "profile"), [("ruff-audit", "lint"), ("mypy-audit", "lint"), ("small-audits", "small")]
)
def test_the_workflow_gates_every_step_after_the_plan(name, profile):
    yaml = pytest.importorskip("yaml")
    wf = yaml.safe_load((WORKFLOWS / f"{name}.yml").read_text(encoding="utf-8"))
    assert "paths" not in wf[True]["pull_request"] and "paths-ignore" not in wf[True]["pull_request"]  # required check
    (job,) = wf["jobs"].values()
    assert "if" not in job  # the job always starts and reports
    assert job["permissions"] == {"contents": "read", "pull-requests": "read", "issues": "read"}
    steps = job["steps"]
    plan = next(i for i, s in enumerate(steps) if s.get("id") == "plan")
    assert steps[plan - 1]["name"] == "Check out repository code"
    assert f"--profile {profile}" in steps[plan]["run"] and "audit_skip_plan.py" in steps[plan]["run"]
    assert '|| echo "mode=full"' in steps[plan]["run"]  # a planner failure runs the audit
    for s in steps[plan + 1 :]:
        assert "steps.plan.outputs.mode != 'none'" in s["if"], s["name"]
