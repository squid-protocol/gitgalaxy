"""#5919 slice 3: parts and timeouts for the Smoke full-suite job and the Full Suite Gate legs (suite_shard_plan.py)."""

from __future__ import annotations

import json
import math
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


def _synthetic():
    """Durations that plan one Smoke part whatever the committed file holds (#8218: the nightly restores a smaller cache)."""
    return {f"tests/t_{i}.py::test": 1.0 for i in range(1000)}


def test_growth_adds_parts_without_a_yaml_edit():
    base = _synthetic()
    assert plan.smoke_plan(base)["splits"] == 1
    assert plan.smoke_plan({k: v * 3 for k, v in base.items()})["splits"] > 1
    assert plan.smoke_plan({k: v * 1000 for k, v in base.items()})["splits"] == plan.SMOKE_MAX_PARTS


def test_growth_does_not_depend_on_the_durations_file_size(tmp_path):
    small = tmp_path / "small.json"
    small.write_text(json.dumps({f"t{i}": 0.01 for i in range(50)}), encoding="utf-8")
    assert plan.smoke_plan(plan.load_durations(small))["splits"] == 1
    test_growth_adds_parts_without_a_yaml_edit()


def test_a_busy_pool_halves_the_cap():
    huge = {k: v * 1000 for k, v in _synthetic().items()}
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
    assert any(
        "test-durations-" in str(s.get("with", {}).get("restore-keys")) for s in plan_job["steps"]
    )  # picks the newest, once
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


def test_a_windows_part_that_took_its_measured_minutes_fits_its_step_timeout_8572(durations):
    # 2026-11-19: windows 3.12 part 1 passed 18499 tests in 25:06 and the 25-min step cap killed it
    measured = {("windows-latest", "3.12"): 25, ("windows-latest", "3.11"): 21}
    for leg in plan.gate_plan(durations)["matrix"]:
        minutes = measured.get((leg["os"], leg["python-version"]))
        if minutes:
            assert leg["step_timeout"] >= minutes + 1, leg


def test_a_windows_step_cap_keeps_3_min_over_the_slowest_seen_part_whatever_the_cache_8701(durations):
    # #8701 [c:35ac4f04]: the issue's confirm item asks that no Windows leg finish within 3 min of its limit. The planner
    # side of that: the step cap stays >= 3 min over the slowest minutes seen (25:06 on windows 3.12), for the committed
    # durations and for a wall-calibrated cache a quarter of their size (which plans the fewest parts and the floor cap).
    for cache in (durations, {k: v / 4 for k, v in durations.items()}):
        legs = [x for x in plan.gate_plan(cache)["matrix"] if x["os"].startswith("windows")]
        assert {x["python-version"] for x in legs} == {"3.11", "3.12"}
        for leg in legs:
            seen = plan.SLOWEST_SEEN_MIN[(leg["os"], leg["python-version"])]
            assert leg["step_timeout"] - seen >= 3, leg
        assert min(x["step_timeout"] for x in legs if x["python-version"] == "3.12") >= 30


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


# #5919: the planned balance of every Smoke part and Gate leg, from the committed durations. The CI calibration of
# 2026-11-16 measured part wall ratios of 1.45-1.97 against the 1.3 acceptance; this pins that the PLAN is not the
# source (least_duration over .test_durations plans ~1.0), so a measured excess is runner/contention noise and
# unmeasured tests, which a re-sizing cannot remove. The fixed setup term is paid by every part alike, so it lowers
# the wall ratio of equal parts; that is checked here too.
RATIO_LIMIT = 1.3


def _planned_ratio(weight, n, setup_s):
    loads = [w / plan.JOBS for w, _ in sp._shard_loads(weight, n)]
    return (setup_s + max(loads)) / (setup_s + min(loads))


def test_the_smoke_parts_are_planned_balanced(durations):
    n = plan.smoke_plan(durations)["splits"]
    assert _planned_ratio(durations, n, plan.SMOKE_SETUP_S) <= RATIO_LIMIT
    assert _planned_ratio(durations, n, 0) <= RATIO_LIMIT


def test_every_gate_leg_is_planned_balanced(durations):
    mean = sum(durations.values()) / len(durations)
    legs = {(x["os"], x["python-version"]): x["splits"] for x in plan.gate_plan(durations)["matrix"]}
    for os_name, py, speed in plan.LEGS:
        even = os_name.startswith("windows")
        weight = {k: (mean if even else v) * speed for k, v in durations.items()}
        n = legs[(os_name, py)]
        assert _planned_ratio(weight, n, plan.GATE_SETUP_S) <= RATIO_LIMIT, (os_name, py, n)
        assert _planned_ratio(weight, n, 0) <= RATIO_LIMIT, (os_name, py, n)


def test_windows_312_is_planned_no_faster_than_windows_311_8701():
    # 2026-11-19: 2 parts planned at 18 min at speed 1.3 measured 25:06. The speed is pinned, not the planned minutes: the
    # nightly's restored durations differ from the committed file and move the minutes by a few percent.
    speed = {(o, py): s for o, py, s in plan.LEGS}
    assert speed[("windows-latest", "3.12")] >= speed[("windows-latest", "3.11")]


def test_a_windows_part_is_planned_to_finish_inside_the_gate_target_8701(durations):
    # #8701 [c:ab1161f2]: 2 parts planned at 18 min measured 25:06. Every Windows leg must plan at least 3 parts
    # (part 1 of 2 left no margin) and each part's planned minutes, setup included, must stay inside the target.
    legs = {(x["os"], x["python-version"]): x["splits"] for x in plan.gate_plan(durations)["matrix"]}
    mean = sum(durations.values()) / len(durations)
    for os_name, py, speed in plan.LEGS:
        if not os_name.startswith("windows"):
            continue
        n = legs[(os_name, py)]
        assert n >= 3, (py, n)
        weight = dict.fromkeys(durations, mean * speed)
        # a busy durations cache can need more than the part cap: then the plan is at the cap, not under the target
        assert n == plan.GATE_MAX_PARTS or _fits(weight, n, plan.GATE_SETUP_S, plan.GATE_TARGET_S), (py, n)


# 2026-11-23 (#8701): the Gate's caps read the measured wall of each leg (history), not a hand table re-typed after each red night
def _job(os_name: str, py: str, part: int, splits: int, minutes: float, step_cap: int = 25, ok: bool = True) -> dict:
    """A completed Gate leg job whose `Full Suite` step took `minutes` (a leg named as the matrix writes it)."""
    even = "true, " if os_name.startswith("windows") else ""
    name = f"full-suite-matrix ({os_name}, {py}, {part}, {splits}, {even}{step_cap + 3}, {step_cap})"
    start, end = "2026-11-19T10:00:00Z", f"2026-11-19T{10 + int(minutes) // 60:02d}:{int(minutes) % 60:02d}:00Z"
    step = {"name": f"Full Suite ({os_name}, Python {py})", "conclusion": "success" if ok else "failure",
            "started_at": start, "completed_at": end}  # fmt: skip
    return {
        "name": name,
        "conclusion": "success" if ok else "failure",
        "completed_at": end,
        "started_at": start,
        "steps": [step],
    }


def _runs(os_name: str, py: str, splits: int, minutes: list[float], step_cap: int = 25) -> list[list[dict]]:
    return [[_job(os_name, py, 1, splits, m, step_cap)] for m in minutes]


def _leg(matrix: dict, os_name: str, py: str) -> dict:
    return next(x for x in matrix["matrix"] if x["os"] == os_name and x["python-version"] == py)


def test_leg_walls_reads_the_measured_minutes_per_os_python_and_parts():
    walls = plan.leg_walls([*_runs("windows-latest", "3.12", 2, [18, 25]), [{"name": "plan", "completed_at": "x"}]])
    assert walls == {("windows-latest", "3.12", 2): [18.0, 25.0]}


def test_no_history_and_empty_history_plan_the_same_as_before(durations):
    assert plan.gate_plan(durations, history={}) == plan.gate_plan(durations, history=None) == plan.gate_plan(durations)


@pytest.mark.parametrize("room", [True, False])
def test_a_leg_measured_slow_at_n_parts_gets_a_part_before_its_cap_is_raised(durations, monkeypatch, room):
    # the 2026-11-19 night: windows 3.12 at 2 parts ran 25 min against a 25-min step cap and was cut.
    # The maximum is pinned: with room (50) the leg gets one more part; already AT the maximum (1) it can only get a
    # longer cap. Unpinned, the answer follows the committed durations (CI's merge with main planned 4 of 4 parts).
    monkeypatch.setattr(plan, "GATE_MAX_PARTS", 50 if room else 1)
    base = plan.gate_plan(durations)
    n0 = _leg(base, "windows-latest", "3.12")["splits"]
    hist = plan.leg_walls(_runs("windows-latest", "3.12", n0, [24, 25, 25], step_cap=25))
    got = _leg(plan.gate_plan(durations, history=hist), "windows-latest", "3.12")
    if room:
        assert got["splits"] == n0 + 1  # rebalanced, not just given a longer cap
    else:
        # no part to add: the cap never drops below the planned one and always covers the worst measured wall x 1.3
        assert n0 == 1 and got["splits"] == 1
        assert got["timeout"] >= max(_leg(base, "windows-latest", "3.12")["timeout"], 25 * 1.3)
    assert got["timeout"] <= plan.GATE_TIMEOUT_CEILING and got["step_timeout"] == got["timeout"] - plan.STEP_MARGIN_MIN


def test_a_measured_slow_leg_raises_its_cap_and_a_fast_one_never_undercuts_the_planned_window(durations):
    base = plan.gate_plan(durations)
    n0 = _leg(base, "macos-latest", "3.12")["splits"]
    slow = plan.leg_walls(
        _runs("macos-latest", "3.12", n0, [19.5, 21.5, 22.0])
    )  # under SPLIT_ABOVE_MIN: same parts, higher cap
    fast = plan.leg_walls(_runs("macos-latest", "3.12", n0, [6.0, 7.0, 6.5]))
    up = _leg(plan.gate_plan(durations, history=slow), "macos-latest", "3.12")
    assert (
        up["splits"] == n0
        and up["timeout"] >= math.ceil(22.0 * plan.SEEN_HEADROOM) > _leg(base, "macos-latest", "3.12")["timeout"]
    )
    assert (
        plan.gate_plan(durations, history=fast) == base
    )  # history is a floor over the durations plan, never a cut under it


def test_too_few_observations_fall_back_to_the_committed_table(durations):
    n0 = _leg(plan.gate_plan(durations), "windows-latest", "3.11")["splits"]
    hist = plan.leg_walls(
        _runs("windows-latest", "3.11", n0, [5.0, 5.0])
    )  # 2 < HISTORY_MIN_OBS: the table still floors it
    assert plan.gate_plan(durations, history=hist) == plan.gate_plan(durations)


def test_history_that_cannot_be_read_never_fails_the_plan(monkeypatch, capsys):
    import gate_leg_margin as glm

    def boom(_n):
        raise OSError("gh unreachable")

    monkeypatch.setattr(glm, "scheduled_jobs", boom)
    assert plan.load_history(3) == {}
    assert "history: unavailable" in capsys.readouterr().err


def test_the_gate_workflow_plans_with_history_and_checks_out_what_it_reads():
    text = (WORKFLOWS / "full-suite-gate.yml").read_text(encoding="utf-8")
    assert "suite_shard_plan.py --gate --history-runs" in text
    for f in ("gate_leg_margin.py", "ci_rerun_stats.py"):
        assert (
            f"tests/tools/{f}" in text.split("Plan the legs for this trigger")[0]
        )  # in the plan job's sparse checkout
