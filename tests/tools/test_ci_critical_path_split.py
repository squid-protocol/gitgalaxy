"""#5133, #5543: the CI critical path -- the ground-truth job as a warm job and 4 parts (or 2 self-warming parts when CI is busy) and the advisory evidence deltas in their own job.

`ground-truth` and `full-suite` are required checks (the ruleset names them), so each stays one job that aggregates its
parts. The parts must together cover everything the single job ran, and nothing advisory may hold the required check back.
"""

import sys
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))
import ci_layout as cl  # noqa: E402

WORKFLOWS = ROOT / ".github" / "workflows"


def _jobs(name):
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))["jobs"]


def _steps(job):
    return {s.get("name"): s for s in job["steps"]}


def test_ground_truth_is_the_aggregate_of_its_parts():
    jobs = _jobs("mainframe-ground-truth.yml")
    assert "ground-truth" in jobs and "ground-truth-part" in jobs and "ground-truth-warm" in jobs
    assert "ground-truth-part" in jobs["ground-truth"]["needs"]
    assert "ground-truth-warm" in jobs["ground-truth"]["needs"]  # #5543: a failed warm job must fail the required check
    assert "ground-truth" in jobs["publish-history"]["needs"] or jobs["publish-history"]["needs"] == "ground-truth"
    publish = jobs["publish-history"]
    assert "ground-truth-part" in publish["needs"]  # #5176: a tested-tree skip uploads no history artifact
    assert "needs.ground-truth-part.result == 'success'" in publish["if"]
    assert (
        "ground-truth-warm" in publish["needs"]
    )  # #5543: the history is uploaded by the warm job (or by part 1: no warm job on a cache hit)
    assert "name" not in jobs["ground-truth"]  # the check is named by its key: `ground-truth`


PARTS = 4  # #5543: the calm layout; the busy one is BUSY_PARTS. The ledger gate and the history are not in every part


def test_the_parts_partition_tests_cobol_mainframe():
    """#5133: pytest-split cuts the directory; no hand-listed files, so a new test is placed by its recorded seconds."""
    part = _jobs("mainframe-ground-truth.yml")["ground-truth-part"]
    assert "fromJSON(needs.plan.outputs.matrix" in part["strategy"]["matrix"]  # the plan job picks the layout (#5543)
    assert part["strategy"]["fail-fast"] is False
    run = _steps(part)["Full-corpus differential and answer-key tests"]["run"]
    pytest_line = " ".join(run[run.index("-m pytest") :].split("\\\n"))
    pytest_line = " ".join(pytest_line.split())
    assert "tests/cobol_mainframe/ " in pytest_line and "--ignore" not in pytest_line
    assert (
        "--splits ${{ matrix.parts }} --splitting-algorithm least_duration --group ${{ matrix.group }}" in pytest_line
    )
    assert part["name"] == "ground-truth part ${{ matrix.shard }}"  # ci_digest.PARTS matches "ground-truth part N/M"


def test_the_fallback_matrix_is_the_calm_layout():
    """A failed plan leaves `matrix` empty: the workflow runs the 4 parts of the warm layout, as it did before the plan chose."""
    import json
    import re

    expr = _jobs("mainframe-ground-truth.yml")["ground-truth-part"]["strategy"]["matrix"]
    fallback = json.loads(re.search(r"\|\| '(.*)'\) \}\}$", expr).group(1))
    assert fallback == cl.matrix(PARTS)


def test_the_warm_job_runs_the_gate_once_and_the_parts_only_unpack_its_scans():
    """#5543: the warm-up (parallel scans + the ledger gate) is paid once; the gate runs in the warm job or, with none, in part 1 only."""
    jobs = _jobs("mainframe-ground-truth.yml")
    warm, part = jobs["ground-truth-warm"], jobs["ground-truth-part"]
    steps = _steps(warm)
    for name in ("Restore the published history from the generated branch", "Keep the history for the publish job"):
        assert "matrix" not in steps[name]["if"], name
    assert "--summary" in steps["Gate against the ground-truth ledger"]["run"]
    assert "mainframe_corpus.py scan" in steps["Scan the pinned corpora in parallel"]["run"]
    assert steps["Upload the scans for the parts"]["with"]["name"] == "ground-truth-scans"
    part_steps = _steps(part)
    gate = part_steps["Gate against the ground-truth ledger"]
    assert (
        gate["if"] == "needs.plan.outputs.warm == 'false' && matrix.group == 1"
    )  # never beside a warm job, never twice
    assert "needs.plan.outputs.warm != 'false'" in warm["if"]  # skipped on a cache hit and when busy
    assert part_steps["Download the scans"]["with"]["name"] == "ground-truth-scans"
    assert part_steps["Download the scans"]["if"] == "needs.plan.outputs.warm != 'false'"
    assert "ground-truth-warm" in part["needs"]
    assert "needs.ground-truth-warm.result == 'success'" in part["if"]  # the download needs an uploader that ran
    names = list(part_steps)
    for scans in ("Unpack the scans", "Restore the cached scans", "Scan the pinned corpora in parallel"):
        assert names.index("Fetch the pinned corpora") < names.index(scans)  # the fetch prunes `_scans`
        assert (
            names.index(scans)
            < names.index("Gate against the ground-truth ledger")
            < names.index("Full-corpus differential and answer-key tests")
        )


def test_the_scans_cache_is_saved_on_main_only_and_every_job_names_the_scans_alike():
    """#5543: a PR's cache scope is its own ref (#5024): restore-only on a PR; the keys and the engine key come from `plan`."""
    jobs = _jobs("mainframe-ground-truth.yml")
    key = "needs.plan.outputs.scans_key"
    save = _steps(jobs["ground-truth-warm"])["Save the scans (main)"]
    assert save["if"] == "github.event_name != 'pull_request'" and save["with"]["key"] == "${{ " + key + " }}"
    assert save["with"]["path"] == ".mainframe_corpora/_scans" and save["uses"].startswith("actions/cache/save@")
    restore = _steps(jobs["ground-truth-part"])["Restore the cached scans"]
    assert restore["uses"].startswith("actions/cache/restore@") and restore["with"]["key"] == save["with"]["key"]
    lookup = _steps(jobs["plan"])["Look up the cached scans"]
    assert lookup["with"]["lookup-only"] is True and lookup["with"]["path"] == save["with"]["path"]
    assert lookup["with"]["key"] == "${{ steps.key.outputs.scans }}"
    keyed = _steps(jobs["plan"])["Key the scans by engine state"]
    assert "corpora.json" in keyed["run"] and "gitgalaxy/**" in keyed["env"]["ENGINE"]  # content, never the commit
    assert "github.sha" not in str(keyed)
    for job in ("ground-truth-warm", "ground-truth-part"):
        assert jobs[job]["env"]["MAINFRAME_ENGINE_KEY"] == "${{ needs.plan.outputs.engine_key }}"


def test_the_aggregate_accepts_a_skipped_warm_job_only_when_the_plan_needed_none():
    run = _steps(_jobs("mainframe-ground-truth.yml")["ground-truth"])["Every part passed"]["run"]
    assert 'test "$PLANNED_WARM" = "false"' in run and 'ok "$PARTS"' in run


def test_the_layout_follows_the_queue_and_the_cache():
    """#5543: calm = warm + 4 parts (no warm on a cache hit); busy = 2 self-warming parts; only a pull request goes busy."""
    calm = cl.choose("pull_request", "full", False, 0)
    assert (calm["layout"], calm["warm"], calm["parts"], calm["gate_in_part"]) == ("calm", False, PARTS, True)
    for event in (
        "push",
        "schedule",
        "workflow_dispatch",
    ):  # #5543: only main-side runs keep the warm job (it saves the cache)
        main_side = cl.choose(event, "full", False, 0)
        assert (main_side["warm"], main_side["parts"], main_side["gate_in_part"]) == (True, PARTS, False), event
    hit = cl.choose("pull_request", "full", True, cl.BUSY_ABOVE)  # at the threshold is still calm
    assert (hit["layout"], hit["warm"], hit["parts"], hit["gate_in_part"]) == ("calm", False, PARTS, True)
    for cached in (False, True):
        busy = cl.choose("pull_request", "full", cached, cl.BUSY_ABOVE + 1)
        assert (busy["layout"], busy["warm"], busy["parts"], busy["gate_in_part"]) == ("busy", False, 2, True)
    for event in ("push", "schedule", "workflow_dispatch"):
        assert cl.choose(event, "full", False, 999)["layout"] == "calm", event
    assert cl.choose("pull_request", "full", False, None)["layout"] == "calm"  # an unreadable queue is calm
    assert cl.choose("pull_request", "none", True, 999)["layout"] == "none"
    assert [m["shard"] for m in cl.matrix(2)["include"]] == ["1/2", "2/2"]


def test_the_layout_cli_writes_the_outputs_and_the_summary(tmp_path):
    import subprocess
    import sys

    out, summary = tmp_path / "out", tmp_path / "summary.md"
    cmd = [sys.executable, str(ROOT / "tests/tools/ci_layout.py"), "--event", "pull_request", "--waiting", "30"]
    subprocess.run([*cmd, "--github-output", str(out), "--summary", str(summary)], check=True, capture_output=True)  # noqa: S603
    lines = dict(ln.split("=", 1) for ln in out.read_text(encoding="utf-8").splitlines())
    assert (lines["layout"], lines["warm"], lines["parts"]) == ("busy", "false", "2")
    assert "## Ground-truth layout: busy" in summary.read_text(encoding="utf-8")


def test_the_engine_key_can_be_named_by_ci(monkeypatch):
    import mainframe_corpus as mc

    monkeypatch.setenv("MAINFRAME_ENGINE_KEY", "abc123")
    assert mc.engine_key() == "abc123"


def _ground_truth_totals():
    """Replays pytest-split's least_duration (heaviest first, into the lightest group) over the committed durations."""
    import json
    import subprocess

    # The full-suite parts overwrite the working-tree .test_durations with the restored cache (smoke-test.yml, "Balance
    # by the restored durations"), which has no ground-truth seconds: read the committed blob, the file the fallback uses.
    shown = subprocess.run(
        ["git", "show", "HEAD:.test_durations"],  # noqa: S607
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    text = shown.stdout if shown.returncode == 0 and shown.stdout else (ROOT / ".test_durations").read_text("utf-8")
    durations = json.loads(text)
    seconds = sorted((v for k, v in durations.items() if k.startswith("tests/cobol_mainframe/")), reverse=True)
    assert seconds, "no recorded tests/cobol_mainframe/ durations"
    totals = [0.0] * PARTS
    for s in seconds:
        totals[totals.index(min(totals))] += s
    return seconds, totals


def test_the_ground_truth_seconds_are_recorded_and_the_parts_balanced():
    """#5133: the ground-truth tests were absent from .test_durations (the smoke runs have no corpora), so pytest-split
    cut them by a default weight. Refresh from the test-times-ground-truth-part-N artifacts of a main run; the replay
    of the parts must then be within 20% (#5133 acceptance)."""
    seconds, totals = _ground_truth_totals()
    assert len(seconds) > 7000, f"only {len(seconds)} tests/cobol_mainframe/ durations recorded: refresh them"
    assert max(totals) <= min(totals) * 1.2, totals
    assert seconds[0] < sum(totals) / 4, "one test is a quarter of the ground-truth job: no split can balance it"


def test_evidence_deltas_is_advisory_and_off_the_required_check():
    jobs = _jobs("smoke-test.yml")
    deltas = jobs["evidence-deltas"]
    assert deltas["continue-on-error"] is True
    assert "evidence-deltas" not in jobs["full-suite"]["needs"]
    assert not any("evidence_report" in str(s.get("run")) for s in jobs["full-suite-part"]["steps"])
    assert any("evidence_report.py --deltas" in str(s.get("run")) for s in deltas["steps"])


def test_full_suite_parts_are_balanced_by_least_duration():
    """#5133: the default duration_based_chunks cuts contiguous slices, which put tests/cobol_mainframe all in part 1."""
    steps = _jobs("smoke-test.yml")["full-suite-part"]["steps"]
    # The part count is planned by the shard-plan job (#5919): match the planned flag, not a literal count.
    runs = [str(s.get("run")) for s in steps if '--splits "$SPLITS"' in str(s.get("run"))]
    assert runs
    assert all("--splitting-algorithm least_duration" in r for r in runs)


def test_every_artifact_download_waits_on_a_job_that_can_upload_it():
    """#5176: a download job gated only on an aggregate that passes when the uploader was skipped fails on a green run."""
    for path in sorted(WORKFLOWS.glob("*.yml")):
        jobs = yaml.safe_load(path.read_text(encoding="utf-8"))["jobs"]
        text = path.read_text(encoding="utf-8")
        if "skip_tested_tree" not in text:
            continue
        for name, job in jobs.items():
            if not any("download-artifact" in str(s.get("uses", "")) for s in job.get("steps", [])):
                continue
            needs = job.get("needs", [])
            needs = [needs] if isinstance(needs, str) else needs
            uploaders = [
                n for n in jobs if any("upload-artifact" in str(s.get("uses", "")) for s in jobs[n].get("steps", []))
            ]
            gate = str(job.get("if", ""))
            assert any(
                n in needs and (f"needs.{n}.result == 'success'" in gate or "success()" in gate) for n in uploaders
            ), f"{path.name}:{name} downloads an artifact without requiring its uploader to have succeeded"


# ---- #5132: fewer PR jobs ------------------------------------------------------------------------------------------


def _on(name):
    doc = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    return doc.get(True) or doc.get("on")


def _glob(pattern):
    """GitHub's filter glob: `**` crosses directories, `*` does not, a leading `!` excludes."""
    import re

    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif pattern.startswith("**", i):
            out, i = out + ".*", i + 2
        elif pattern[i] == "*":
            out, i = out + "[^/]*", i + 1
        else:
            out, i = out + re.escape(pattern[i]), i + 1
    return re.compile(out + r"\Z")


def _starts(name, changed):
    """Whether a PR that changes only `changed` starts the workflow (GitHub: any path matches, last pattern wins)."""
    patterns = _on(name)["pull_request"]["paths"]
    for f in changed:
        hit = False
        for p in patterns:
            if _glob(p.lstrip("!")).match(f):
                hit = not p.startswith("!")
        if hit:
            return True
    return False


ENGINE = "gitgalaxy/core/detector.py"
TRANSLATOR = "gitgalaxy/tools/cobol_to_java/det/emit.py"
ONLY_TESTS_AND_DOCS = ["tests/tools/test_x.py", "docs/ci.md", "README.md", "tests/cobol_mainframe/answer_key/a.json"]


@pytest.mark.parametrize("name", ["muninn.yml", "codeql.yml"])
def test_security_scans_run_on_prs_only_for_engine_dependency_or_workflow_changes(name):
    assert "schedule" in _on(name)  # the backstop that covers everything the PR filter skips
    assert "paths-ignore" not in _on(name)["pull_request"]
    for changed in (
        ENGINE,
        "pyproject.toml",
        "ci/requirements/test.txt",
        ".github/workflows/smoke-test.yml",
        "action.yml",
    ):
        assert _starts(name, [changed]), changed
    for changed in ONLY_TESTS_AND_DOCS:
        assert not _starts(name, [changed]), changed


def test_golden_crucible_skips_translator_only_and_prose_changes():
    name = "golden-crucible.yml"
    assert _starts(name, [ENGINE]) and _starts(name, ["tests/golden_master_audit/_groups.json"])
    assert _starts(name, ["tests/crucible_pins.toml"]) and _starts(name, [".github/workflows/golden-crucible.yml"])
    assert not _starts(name, [TRANSLATOR, "gitgalaxy/cobol_to_java_controller.py"])
    assert not _starts(name, ["gitgalaxy/README.md", *ONLY_TESTS_AND_DOCS])
    assert _starts(name, [TRANSLATOR, ENGINE])  # one engine file among translator files still runs it


def test_golden_crucible_paths_cover_every_file_the_test_imports():
    """The sibling modules tests/test_golden_crucible.py imports bare must be in the filter, or editing one skips the check."""
    import re

    text = (ROOT / "tests" / "test_golden_crucible.py").read_text(encoding="utf-8")
    for mod in re.findall(r"^import (golden_\w+|_crucible_pin)$", text, re.M):
        assert _starts("golden-crucible.yml", [f"tests/{mod}.py"]), mod


def test_the_three_pre_gates_are_one_job():
    jobs = _jobs("gitgalaxy.yml")
    assert {"vault-sentinel", "xray-inspector", "supply-chain-firewall"}.isdisjoint(jobs)
    steps = jobs["pre-gate"]["steps"]
    gates = [s for s in steps if s.get("uses") == "./"]
    assert [s["with"]["tool"] for s in gates] == ["vault-sentinel", "xray-inspector", "supply-chain-firewall"]
    # each gate runs even when an earlier one failed, and none may swallow its own failure
    assert all("!cancelled()" in str(s.get("if", "")) for s in gates[1:])
    assert not any(s.get("continue-on-error") for s in steps)


def test_print_waiting_prints_the_count_or_nothing(monkeypatch, capsys):
    """#5919: a workflow step hands the count to another planner; an unreadable queue prints nothing and exits 0."""
    monkeypatch.setattr(sys, "argv", ["ci_layout.py", "--print-waiting"])
    monkeypatch.setattr(cl, "waiting_now", lambda: 12)
    assert cl.main() == 0
    assert capsys.readouterr().out == "12\n"
    monkeypatch.setattr(cl, "waiting_now", lambda: None)
    assert cl.main() == 0
    assert capsys.readouterr().out == "\n"


def test_print_waiting_is_calm_without_a_repo(tmp_path):
    import os
    import subprocess

    env = {k: v for k, v in os.environ.items() if k != "GITHUB_REPOSITORY"}
    done = subprocess.run(  # noqa: S603
        [sys.executable, str(ROOT / "tests/tools/ci_layout.py"), "--print-waiting"],
        check=True, capture_output=True, text=True, env=env, cwd=tmp_path,
    )  # fmt: skip
    assert done.stdout.strip() == ""


def test_det_sweep_plans_read_the_queue_in_the_workflow_not_the_planner():
    """#5919: both plan steps get the waiting count from ci_layout (pull requests only) and pass it on as --waiting."""
    job = _jobs("det-sweep.yml")["plan"]
    assert job["permissions"]["actions"] == "read"
    steps = _steps(job)
    for name in ("Plan the sweep", "Plan from the port diff"):
        step = steps[name]
        assert "GH_TOKEN" in step["env"], name
        run = step["run"]
        assert 'if [ "$GITHUB_EVENT_NAME" = "pull_request" ]' in run, name
        assert "ci_layout.py --print-waiting" in run, name
        assert '${waiting:+--waiting "$waiting"}' in run, name
        assert run.index("--print-waiting") < run.index("det_sweep_plan.py"), name
    planner = (ROOT / "tests/tools/det_sweep_plan.py").read_text(encoding="utf-8")
    assert "ci_layout" not in planner and "post_merge_dispatch" not in planner  # test_ground_truth_plan reaches it
