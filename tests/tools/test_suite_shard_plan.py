"""#5919 slice 3: parts and timeouts for the Smoke full-suite job and the Full Suite Gate legs (suite_shard_plan.py)."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import ci_shard_plan as sp  # noqa: E402
import suite_shard_plan as plan  # noqa: E402

WORKFLOWS = ROOT / ".github" / "workflows"


@pytest.fixture(scope="module")
def durations():
    return plan.load_durations()


def _legs(m):
    return {(x["os"], x["python-version"]) for x in m}


def _fits(weight, n, setup_s, target_s):
    return setup_s + sp.slowest_shard(weight, n) / plan.JOBS <= target_s


# The part counts are deliberately not pinned: .test_durations is refreshed from warm runs (#6146 shrank the plan), so
# the real file is checked for the planner's contract (fewest parts that fit the target, inside the cap), not a number.
def test_the_committed_durations_plan_the_fewest_smoke_parts_that_fit(durations):
    p = plan.smoke_plan(durations)
    n = p["splits"]
    assert 1 <= n <= plan.SMOKE_MAX_PARTS and p["matrix"] == {"group": list(range(1, n + 1))}
    assert plan.SMOKE_TIMEOUT_FLOOR <= p["timeout"] <= plan.SMOKE_TIMEOUT_CEILING
    assert n == plan.SMOKE_MAX_PARTS or _fits(durations, n, plan.SMOKE_SETUP_S, plan.SMOKE_TARGET_S)
    assert n == 1 or not _fits(durations, n - 1, plan.SMOKE_SETUP_S, plan.SMOKE_TARGET_S)


def test_the_committed_durations_plan_the_fewest_gate_parts_per_leg(durations):
    parts = {}
    for leg in plan.gate_plan(durations)["matrix"]:
        parts[(leg["os"], leg["python-version"])] = leg["splits"]
    assert set(parts) == {(o, py) for o, py, _ in plan.LEGS}
    mean = sum(durations.values()) / len(durations)
    for os_name, py, speed in plan.LEGS:
        even = os_name.startswith("windows")
        weight = {k: (mean if even else v) * speed for k, v in durations.items()}
        n = parts[(os_name, py)]
        assert 1 <= n <= plan.GATE_MAX_PARTS
        assert n == plan.GATE_MAX_PARTS or _fits(weight, n, plan.GATE_SETUP_S, plan.GATE_TARGET_S)
        assert n == 1 or not _fits(weight, n - 1, plan.GATE_SETUP_S, plan.GATE_TARGET_S)


def test_growth_adds_parts_without_a_yaml_edit(durations):
    grown = {k: v * 3 for k, v in durations.items()}
    assert plan.smoke_plan(grown)["splits"] > plan.smoke_plan(durations)["splits"]
    assert plan.smoke_plan({k: v * 1000 for k, v in durations.items()})["splits"] == plan.SMOKE_MAX_PARTS


def test_a_busy_pool_halves_the_cap(durations):
    huge = {k: v * 1000 for k, v in durations.items()}
    assert plan.smoke_plan(huge, waiting=99)["splits"] == plan.SMOKE_MAX_PARTS // 2
    assert max(x["splits"] for x in plan.gate_plan(huge, waiting=99)["matrix"]) == plan.GATE_MAX_PARTS // 2


def test_gate_legs_have_the_keys_the_workflow_reads(durations):
    legs = plan.gate_plan(durations)["matrix"]
    assert len(_legs(legs)) == len(plan.LEGS)
    for leg in legs:
        assert {"os", "python-version", "part", "splits", "timeout", "step_timeout"} <= set(leg)
        assert 1 <= leg["part"] <= leg["splits"]
        assert leg["step_timeout"] == leg["timeout"] - plan.STEP_MARGIN_MIN
        assert plan.GATE_TIMEOUT_FLOOR <= leg["timeout"] <= plan.GATE_TIMEOUT_CEILING
        assert leg.get("even", False) == leg["os"].startswith("windows")
    for os_py in _legs(legs):
        mine = sorted(x["part"] for x in legs if (x["os"], x["python-version"]) == os_py)
        assert mine == list(range(1, len(mine) + 1))


def test_the_workflows_still_read_the_shape_the_plan_emits():
    gate = (WORKFLOWS / "full-suite-gate.yml").read_text(encoding="utf-8")
    for key in ("matrix.part", "matrix.splits", "matrix.even", "matrix.timeout", "matrix.step_timeout"):
        assert key in gate
    assert re.search(r"matrix\.group", (WORKFLOWS / "smoke-test.yml").read_text(encoding="utf-8"))


def test_gate_plan_job_reads_the_queue_and_feeds_the_matrix():
    yaml = pytest.importorskip("yaml")
    jobs = yaml.safe_load((WORKFLOWS / "full-suite-gate.yml").read_text(encoding="utf-8"))["jobs"]
    plan_job = jobs["matrix"]
    assert plan_job["permissions"]["actions"] == "read"
    run = "\n".join(s.get("run", "") for s in plan_job["steps"])
    assert "ci_layout.py --print-waiting" in run and "${waiting:+--waiting" in run
    assert "suite_shard_plan.py --gate" in run
    checkout = next(s for s in plan_job["steps"] if "checkout" in s.get("uses", ""))
    for needed in (
        "suite_shard_plan.py",
        "ci_shard_plan.py",
        "ci_layout.py",
        "post_merge_dispatch.py",
        ".test_durations",
    ):
        assert needed in checkout["with"]["sparse-checkout"]
    assert jobs["full-suite-matrix"]["strategy"]["matrix"]["include"] == "${{ fromJSON(needs.matrix.outputs.include) }}"


def _smoke_jobs():
    yaml = pytest.importorskip("yaml")
    return yaml.safe_load((WORKFLOWS / "smoke-test.yml").read_text(encoding="utf-8"))["jobs"]


def test_smoke_parts_are_planned_not_typed():
    """#5919: no literal split count, group list or part timeout is left in smoke-test.yml; shard-plan feeds them."""
    text = (WORKFLOWS / "smoke-test.yml").read_text(encoding="utf-8")
    assert not re.search(r"--splits\s+\d", text)
    assert not re.search(r"group:\s*\[", text)
    assert not re.search(r"part \$\{\{ matrix\.group \}\}/\d", text)
    part = _smoke_jobs()["full-suite-part"]
    assert "shard-plan" in part["needs"]
    assert part["strategy"]["matrix"] == "${{ fromJSON(needs.shard-plan.outputs.matrix) }}"
    assert part["timeout-minutes"] == "${{ fromJSON(needs.shard-plan.outputs.timeout) }}"
    assert '--splits "$SPLITS"' in text


def test_smoke_shard_plan_reads_the_queue_and_balances_by_the_parts_durations():
    jobs = _smoke_jobs()
    plan_job = jobs["shard-plan"]
    assert plan_job["permissions"]["actions"] == "read"
    assert {"matrix", "splits", "timeout"} <= set(plan_job["outputs"])
    # it is skipped exactly when the parts are (suite plan `skip`), so a skip run still passes full-suite
    assert plan_job["if"] == jobs["full-suite-part"]["if"]
    run = "\n".join(s.get("run", "") for s in plan_job["steps"])
    assert "ci_layout.py --print-waiting" in run
    assert 'GITHUB_EVENT_NAME" = "pull_request"' in run  # a queue read on a pull request only (empty = calm)
    assert "suite_shard_plan.py --smoke" in run and "${waiting:+--waiting" in run
    assert any("test-durations-" in str(s.get("with", {}).get("restore-keys")) for s in plan_job["steps"])  # picks the newest, once
    checkout = next(s for s in plan_job["steps"] if "checkout" in s.get("uses", ""))
    # ci_layout reads the queue through post_merge_dispatch: without it the plan is always calm
    for needed in (
        "suite_shard_plan.py",
        "ci_shard_plan.py",
        "ci_layout.py",
        "post_merge_dispatch.py",
        ".test_durations",
    ):
        assert needed in checkout["with"]["sparse-checkout"]
    for job in ("full-suite-durations", "suite-time"):  # the per-part artifact counts follow the plan, not a 3
        assert "shard-plan" in jobs[job]["needs"]
        assert "= 3 ||" not in "\n".join(s.get("run", "") for s in jobs[job]["steps"])


def test_missing_or_empty_durations_fail_the_plan(tmp_path):
    empty = tmp_path / "d.json"
    empty.write_text("{}", encoding="utf-8")
    with pytest.raises(sp.PlanError):
        plan.load_durations(empty)
    with pytest.raises(sp.PlanError):
        plan.load_durations(tmp_path / "nope.json")


def test_cli_prints_the_outputs_and_fails_loudly(tmp_path, capsys):
    d = tmp_path / "d.json"
    d.write_text(json.dumps({"t::a": 100.0, "t::b": 200.0}), encoding="utf-8")
    assert plan.main(["--smoke", "--durations", str(d)]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == 'matrix={"group": [1]}' and out[1] == "splits=1" and out[2].startswith("timeout=")
    assert plan.main(["--gate", "--durations", str(d)]) == 0
    assert json.loads(capsys.readouterr().out.splitlines()[0].removeprefix("matrix="))
    d.write_text("{}", encoding="utf-8")
    assert plan.main(["--smoke", "--durations", str(d)]) == 1
    assert "::error::" in capsys.readouterr().err


def test_a_leg_cap_never_drops_below_its_slowest_seen_time(durations):
    # 2026-10-26: the first stored nightly cache was wall-calibrated (~1/4 of the committed seconds) and planned every leg
    # as 1 part at the 20-22 min floor, under the 25 min a Windows part has taken (#5764 headroom)
    small = {k: v / 4 for k, v in durations.items()}
    for leg in plan.gate_plan(small)["matrix"]:
        seen = plan.SLOWEST_SEEN_MIN.get((leg["os"], leg["python-version"]), 0)
        assert leg["timeout"] >= seen * plan.SEEN_HEADROOM, leg
        assert leg["step_timeout"] == leg["timeout"] - plan.STEP_MARGIN_MIN


def _e2e_fits(weight, n):
    return sp.shard_seconds(weight, n, plan.E2E_SETUP_S, plan.E2E_JOBS) <= plan.E2E_TARGET_S


def _e2e_durations(cases):
    return {f"tests/cobol_mainframe/t_{i}.py::t": 10.0 for i in range(cases)}


def test_the_committed_e2e_durations_plan_the_fewest_shards_that_fit():
    d = plan.load_durations(plan.E2E_DURATIONS)
    p = plan.e2e_plan(d)
    n = p["splits"]
    assert p["matrix"] == {"group": list(range(1, n + 1))} and 1 <= n <= plan.E2E_MAX_SHARDS
    assert _e2e_fits(d, n) or n == plan.E2E_MAX_SHARDS
    assert n == 1 or not _e2e_fits(d, n - 1)
    assert plan.E2E_TIMEOUT_FLOOR <= p["timeout"] <= plan.E2E_TIMEOUT_CEILING


def test_e2e_growth_adds_shards_without_a_yaml_edit_and_a_busy_pool_halves_the_cap():
    # 100 tests of 10 s are 500 s over E2E_JOBS workers: one shard fits; 3000 do not
    counts = [plan.e2e_plan(_e2e_durations(c))["splits"] for c in (100, 400, 3000)]
    assert counts == sorted(counts) and counts[0] == 1 and counts[-1] > counts[0]
    assert plan.e2e_plan(_e2e_durations(3000))["splits"] <= plan.E2E_MAX_SHARDS
    assert plan.e2e_plan(_e2e_durations(3000), waiting=99)["splits"] <= plan.E2E_MAX_SHARDS // 2


def test_e2e_shards_are_planned_not_typed():
    """#5919: no literal split count, group list, shard total or timeout is left in equivalence-e2e.yml."""
    text = (WORKFLOWS / "equivalence-e2e.yml").read_text(encoding="utf-8")
    assert not re.search(r"--splits\s+\d", text)
    assert "[1, 2, 3]" not in text and "group:" not in text.split("matrix:")[1].split("\n")[1]
    assert not re.search(r"shard \$\{\{ matrix\.group \}\}/\d", text)
    jobs = pytest.importorskip("yaml").safe_load(text)["jobs"]
    shard, plan_job = jobs["shard"], jobs["plan"]
    assert "needs.plan.outputs.matrix" in shard["strategy"]["matrix"]
    assert shard["timeout-minutes"].startswith("${{ fromJSON(needs.plan.outputs.timeout")
    assert plan_job["permissions"]["actions"] == "read"
    assert {"matrix", "splits", "timeout"} <= set(plan_job["outputs"])
    run = "\n".join(s.get("run", "") for s in plan_job["steps"])
    assert "ci_layout.py --print-waiting" in run
    assert 'GITHUB_EVENT_NAME" = "pull_request"' in run  # a queue read on a pull request only (empty = calm)
    assert "suite_shard_plan.py --e2e" in run and "${waiting:+--waiting" in run
    assert '--splits "$SPLITS"' in text


def test_cli_e2e_prints_the_outputs(capsys):
    assert plan.main(["--e2e"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith('matrix={"group": [1') and out[1].startswith("splits=") and out[2].startswith("timeout=")
