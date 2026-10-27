"""#6278: the Det Sweep plan runs the Db2 runners only when the Db2 area (change_classifier.db2_area) or a Db2 case moved.

Real file lists: the PRs that ran Db2 for nothing (a skill / register / agent-config / probe-test edit) plan none; a
harness-core change keeps the full non-Db2 sweep but drops the Db2 half; every Db2-area file keeps it.
"""

import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import change_classifier as cc  # noqa: E402
import det_sweep_plan as dsp  # noqa: E402

CASES = {"alpha": {}, "beta": {"port_from": "alpha"}, "dbcase": {"db2": {}}, "dbdep": {"db2": {}, "port_from": "alpha"}}


@pytest.mark.parametrize(
    "files",
    [
        [".claude/skills/ladder-slice/SKILL.md"],
        [".claude/skills/det-port/SKILL.md", ".claude/rules/mainframe-evidence-policy.md", "CLAUDE.md"],
        ["README.md"],
        ["docs/language_status/cobol.md", "docs/language_status/zos_probes.json"],
        ["tests/tools/test_zos_probes.py", "tests/tools/ladder_refresh.py"],
        ["gitgalaxy/core/detector.py", ".github/workflows/smoke-test.yml"],
    ],
)
def test_a_pr_that_moves_no_det_input_plans_none_and_the_required_check_still_reports(files):
    p = dsp.plan(files, "pull_request", CASES)
    assert p["mode"] == "none" and p["cases"] == [] and p["db2_cases"] == []
    assert dsp.shards_for(p) == [] and dsp.db2_shards_for(p) == []  # det's gate treats 0 shards + 0 Db2 as a pass


@pytest.mark.parametrize(
    "path",
    [
        "tests/tools/equivalence.py",
        "tests/tools/equivalence_common.py",
        "tests/equivalence/gnucobol.Dockerfile",
        "tests/equivalence/faults/ggabend.c",
    ],
)
def test_a_full_plan_outside_the_db2_area_keeps_the_sweep_and_drops_the_db2_runners(path):
    p = dsp.plan([path], "pull_request", CASES)
    assert p["mode"] == "full" and p["cases"] == "all" and p["db2_cases"] == []
    assert dsp.db2_shards_for(p) == [] and "Db2 area" in p["reason"]


@pytest.mark.parametrize(
    "path",
    [
        "tests/equivalence/db2/ggsql.c",
        "tests/tools/equivalence_db2.py",
        "tests/tools/db2_shard_plan.py",
        "tests/tools/det_port.py",
        "tests/equivalence/odbc_cli.pin",
        "tests/equivalence/gnucobol-db2.Dockerfile",
        "gitgalaxy/tools/cobol_to_java/det/emit.py",
        "gitgalaxy/tools/cobol_to_java/det/cobolrt/Cobol.java",
        "gitgalaxy/tools/cobol_to_java/cobol_to_java_db2_forge.py",
        "tests/equivalence/dbcase/case.json",
        ".github/workflows/det-sweep.yml",
    ],
)
def test_a_db2_area_file_keeps_the_db2_runners(path):
    p = dsp.plan([path, "tests/equivalence/gnucobol.Dockerfile"], "pull_request", CASES)
    assert p["db2_cases"] == "all" or p["mode"] in ("ports", "narrow")
    assert cc.db2_area(path, ["dbcase"])
    if p["mode"] == "full":
        assert p["db2_cases"] == "all"


def test_a_db2_case_change_still_narrows_to_its_db2_runners():
    p = dsp.plan(["tests/equivalence/dbcase/case.json", "tests/equivalence/alpha/case.json"], "pull_request", CASES)
    assert p["mode"] == "narrow" and p["db2_cases"] == ["dbcase", "dbdep"] and dsp.db2_shards_for(p)


@pytest.mark.parametrize("event", ["schedule", "workflow_dispatch", "push"])
def test_every_other_event_is_unchanged(event):
    p = dsp.plan(["README.md"], event, CASES)
    assert p["mode"] == "full" and p["db2_cases"] == ([] if event == "schedule" else "all")


def test_the_full_label_keeps_every_db2_case():
    p = dsp.plan(["tests/tools/equivalence.py"], "pull_request", CASES, ["shepherd:full"])
    assert p["db2_cases"] == "all"


# The db2 job runs on ubuntu; on a Windows runner `bash` is the WSL launcher (no distribution installed, UTF-16 output,
# no /usr/bin), so the script-behaviour tests are Linux-only like test_ci_retry.py and test_box_tools.py.
needs_linux_bash = pytest.mark.skipif(sys.platform != "linux", reason="the db2 job's bash runs on the Linux runners")


def _pool_for(tmp_path, cases, shard):
    """Run the db2 job's pool-sizing lines (up to the ready dir) the way the workflow does; return GITGALAXY_DB2_POOL."""
    import shutil
    import subprocess

    yaml = pytest.importorskip("yaml")
    if shutil.which("bash") is None:
        pytest.skip("needs bash")
    wf = TOOLS.parents[1] / ".github" / "workflows" / "det-sweep.yml"
    steps = yaml.safe_load(wf.read_text(encoding="utf-8"))["jobs"]["db2"]["steps"]
    run = next(s["run"] for s in steps if "GITGALAXY_DB2_POOL" in s.get("run", ""))
    script = run.split("mkdir -p")[0]
    env_file = tmp_path / "env"
    env_file.touch()
    subprocess.run(
        ["bash", "-c", script],
        check=True,
        env={"PATH": "/usr/bin:/bin", "CASES": cases, "SHARD": shard, "GITHUB_ENV": str(env_file)},
    )
    return int(dict(ln.split("=", 1) for ln in env_file.read_text().split())["GITGALAXY_DB2_POOL"])


@needs_linux_bash
@pytest.mark.parametrize(
    ("n_cases", "shard", "expected"),
    [
        (1, "1/1", 1),
        (3, "1/1", 3),
        (4, "1/1", 4),
        (12, "1/1", 4),
        (13, "1/6", 3),
        (6, "1/6", 1),
        (7, "2/6", 2),
        (70, "1/6", 4),
    ],
)
def test_a_db2_shard_creates_only_the_databases_its_share_of_cases_uses(tmp_path, n_cases, shard, expected):
    cases = ",".join(f"c{i}" for i in range(n_cases))
    assert _pool_for(tmp_path, cases, shard) == expected


@needs_linux_bash
def test_a_full_sweep_shard_keeps_the_whole_pool(tmp_path):
    assert _pool_for(tmp_path, "all", "3/6") == 4


def test_every_harness_path_and_the_modules_it_imports_for_numbers_is_a_det_input():
    """#6782: cobol_coverage.py changed branch counts for every case but planned 'none', so main went red."""
    import evidence

    missing = sorted(
        p
        for p in (*evidence.HARNESS, "tests/tools/le_out_size.py")
        if (TOOLS.parents[1] / p).is_file() and not dsp.det_input(p)
    )
    assert not missing, f"not in det_sweep_plan.DET_INPUTS: {missing}"


def test_a_cobol_coverage_edit_plans_a_sweep_not_none():
    p = dsp.plan(["tests/tools/cobol_coverage.py"], "pull_request", CASES)
    assert p["mode"] != "none"
