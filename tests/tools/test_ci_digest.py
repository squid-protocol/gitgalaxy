"""ci_digest (#4790): triage, the log extract and the local repro of each failed check, without the network."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ci_digest as cd  # noqa: E402

SHA = "a" * 40


def fake_api(runs, mergeable_state="clean", main_runs=(), pr_files=(), main_files=()):
    def api(path):
        if path.endswith("/commits/main"):
            return {"sha": "m" * 40}
        if "/commits/" + "m" * 40 in path:
            return {"check_runs": list(main_runs)}
        if "/pulls/7/files" in path:
            return [{"filename": f} for f in pr_files]
        if path.endswith("/pulls/7"):
            return {"head": {"sha": SHA}, "mergeable_state": mergeable_state}
        if path.endswith(f"/compare/main...{SHA}"):
            return {"merge_base_commit": {"sha": "b" * 40}}
        if path.endswith("/compare/" + "b" * 40 + "...main"):
            return {"files": [{"filename": f} for f in main_files]}
        if "/check-runs" in path:
            return {"check_runs": runs}
        raise AssertionError(path)

    return api


def run(i, name, conclusion, app="github-actions"):
    return {"id": i, "name": name, "status": "completed", "conclusion": conclusion, "app": {"slug": app},
            "html_url": f"https://example/runs/{i}"}  # fmt: skip


PYTEST_LOG = "\n".join([
    "2026-10-09T19:00:00.0000000Z \x1b[31m##[group]Run pytest\x1b[0m",
    "2026-10-09T19:00:01.0000000Z FAILED tests/cobol_mainframe/test_det_hfp.py::test_numval_store - AssertionError",
    "2026-10-09T19:00:01.0000000Z FAILED tests/cobol_mainframe/test_x.py::test_y[a] - ValueError",
    "2026-10-09T19:00:02.0000000Z ##[error]Process completed with exit code 1.",
])  # fmt: skip


def test_a_real_pytest_failure_names_the_tests_and_the_command():
    d = cd.digest(7, fake_api([run(1, "full-suite", "success"), run(2, "full-suite", "failure")]), lambda i: PYTEST_LOG)
    (f,) = d["failed"]
    assert f["triage"] == "real" and f["check"] == "full-suite"
    assert f["tests"] == [
        "tests/cobol_mainframe/test_det_hfp.py::test_numval_store",
        "tests/cobol_mainframe/test_x.py::test_y[a]",
    ]
    assert f["repro"] == "python -m pytest -q " + " ".join(f["tests"])
    assert not any("\x1b" in x or x.startswith("2026-") for x in f["tail"])  # ANSI + timestamps stripped
    assert any("exit code 1" in x for x in f["errors"])


def test_det_shard_failure_repro_names_the_unproven_cases():
    log = "det: 12/13 proven\n  det carddemo-acctupdate            NOT PROVEN  \n  det cbsa-inqacc   PROVED  x"
    d = cd.digest(7, fake_api([run(3, "shard 2/6", "failure")]), lambda i: log)
    assert d["failed"][0]["cases"] == ["carddemo-acctupdate"]
    assert "--cases carddemo-acctupdate" in d["failed"][0]["repro"]


def test_triage_infra_flake_dirty(monkeypatch):
    monkeypatch.setattr(cd, "FLAKY", {"test_regex_redos"})  # the mechanism, whatever the set holds today
    assert cd.triage("cancelled", "", []) == "infra"
    assert cd.triage("failure", "##[error]The runner has received a shutdown signal.", []) == "infra"
    # muninn on #4821: a third-party action's Docker image hit Docker Hub's rate limit
    hub = "ERROR: failed to solve: unexpected status from HEAD request to https://registry-1.docker.io/v2/library/alpine/manifests/3.24.2: 429 Too Many Requests"
    assert cd.triage("failure", hub, []) == "infra"
    dl_504 = "tree_sitter_language_pack.DownloadError: Download error: Failed to fetch manifest from https://github.com/xberg-io/tree-sitter-language-pack/releases/download/v1.21.0/parsers.json: http status: 504"
    assert cd.triage("failure", dl_504, []) == "infra"
    assert cd.triage("failure", "", ["tests/x.py::test_regex_redos[big]"]) == "flake"
    assert cd.triage("failure", "", ["tests/x.py::test_regex_redos", "tests/x.py::test_other"]) == "real"
    assert cd.triage("action_required", "", [], "dirty") == "dirty"
    assert cd.triage("action_required", "", [], "clean") == "real"


def test_dirty_pr_says_merge_main_and_fetches_no_log():
    fetched = []
    api = fake_api([run(4, "squid-protocol.gitgalaxy", "action_required", app="squid")], mergeable_state="dirty")
    d = cd.digest(7, api, lambda i: fetched.append(i) or "")
    assert d["failed"][0]["triage"] == "dirty" and d["failed"][0]["repro"].startswith("git merge origin/main")
    assert fetched == []  # not a GitHub Actions job: no log to fetch


def test_repro_table():
    ex = {"tests": [], "cases": []}
    assert cd.repro("ruff-audit", ex).endswith("--only lint")
    assert cd.repro("compile (cics-genapp)", ex).endswith("--only-ratchets ports")
    assert cd.repro("CodeQL", ex) is None
    assert cd.repro("some-new-check", ex).endswith("--fast")


def test_a_ground_truth_part_repro_runs_its_tests_not_fast():
    ex = {"tests": ["tests/cobol_mainframe/test_proof_reach.py::test_x"], "cases": []}
    assert cd.repro("ground-truth part 1/2", ex) == "python -m pytest -q " + ex["tests"][0]
    assert cd.repro("ground-truth part 2/2", {"tests": [], "cases": []}) == "python -m pytest -q tests/cobol_mainframe/"
    assert "--only-ratchets ground-truth" in cd.repro("ground-truth", {"tests": [], "cases": []})


def test_render_and_a_green_pr():
    assert "no failed checks" in cd.render(cd.digest(7, fake_api([run(5, "ruff-audit", "success")]), lambda i: ""))
    text = cd.render(cd.digest(7, fake_api([run(6, "ruff-audit", "failure")]), lambda i: "##[error]E501 x.py:3"))
    assert "== ruff-audit (failure) -- real" in text and "repro: python tests/tools/pr_gates.py --only lint" in text


def test_a_real_failure_main_also_has_is_triaged_main():
    api = fake_api([run(1, "ground-truth", "failure")], main_runs=[run(2, "ground-truth", "failure")])
    (f,) = cd.digest(7, api, lambda i: "FAILED tests/x.py::test_y - AssertionError")["failed"]
    assert f["triage"] == "main" and f["repro"].startswith("fails on main too")


def test_a_suite_part_and_the_prism_timing_test(monkeypatch):
    ex = {"tests": ["tests/core_engine/test_prism.py::test_prism_suppression_regex_bomb"], "cases": []}
    assert cd.repro("full-suite part 2/3", ex) == "python -m pytest -q " + ex["tests"][0]
    assert cd.triage("failure", "", ex["tests"]) == "real"
    monkeypatch.setattr(cd, "FLAKY", {"test_prism_suppression_regex_bomb"})
    assert cd.triage("failure", "", ex["tests"]) == "flake"


def test_the_infrastructure_marker_of_ci_retry_and_the_db2_pull_triages_as_infra():  # #5048
    marker = "::error::INFRASTRUCTURE (not a code defect): 'docker pull -q x' failed after 4 attempts (exit 1)"
    assert cd.triage("failure", marker, []) == "infra"
    assert cd.triage("failure", "FileNotFoundError: INFRASTRUCTURE (not a code defect): could not pull", []) == "infra"


def ratchet_log(*rows):
    """A suite part whose only failing step is `time_ratchet.py check`: (nodeid, seconds, limit-text) rows."""
    lines = ["2026-10-15T10:00:00.0000000Z ##[group]Per-test time ratchet"]
    lines += [f"2026-10-15T10:00:01.0000000Z FAIL {n}: {sec}s is over {lim}" for n, sec, lim in rows]
    lines += ["2026-10-15T10:00:02.0000000Z 900 tests checked, 1 over the per-test limit, 0 warned",
              "2026-10-15T10:00:02.0000000Z ##[error]Process completed with exit code 1."]  # fmt: skip
    return "\n".join(lines)


UNMARKED = "15s and has no @pytest.mark.slow(reason=...) and no entry in tests/test_time_baseline.json"
BASELINED = "2x its baseline 10.0s (make it faster, or mark it slow with a reason)"
T_IN, T_OUT = "tests/in_diff/test_a.py::test_slow", "tests/elsewhere/test_b.py::test_slow"


def part(log, pr_files=(), **kw):
    api = fake_api([run(1, "full-suite part 1/3", "failure")], pr_files=pr_files, **kw)
    return cd.digest(7, api, lambda i: log)["failed"][0]


def test_a_ratchet_only_red_outside_the_pr_diff_is_a_flake():
    f = part(ratchet_log((T_OUT, 31.0, UNMARKED)), pr_files=["tests/in_diff/test_a.py"])
    assert f["triage"] == "flake" and f["ratchet"] == {T_OUT: [31.0, 15.0]}


def test_a_ratchet_only_red_inside_the_diff_is_real_over_1_5x_and_flake_under():
    over = part(ratchet_log((T_IN, 22.6, UNMARKED)), pr_files=["tests/in_diff/test_a.py"])  # 1.51 x 15 s
    assert over["triage"] == "real"
    under = part(ratchet_log((T_IN, 22.4, UNMARKED)), pr_files=["tests/in_diff/test_a.py"])
    assert under["triage"] == "flake"
    base_over = part(ratchet_log((T_IN, 31.0, BASELINED)), pr_files=["tests/in_diff/test_a.py"])  # limit 20 s
    assert base_over["triage"] == "real" and base_over["ratchet"][T_IN] == [31.0, 20.0]
    base_under = part(ratchet_log((T_IN, 29.0, BASELINED)), pr_files=["tests/in_diff/test_a.py"])
    assert base_under["triage"] == "flake"


def test_one_in_diff_overage_among_outside_ones_keeps_the_ratchet_red_real():
    log = ratchet_log((T_OUT, 40.0, UNMARKED), (T_IN, 40.0, UNMARKED))
    assert part(log, pr_files=["tests/in_diff/test_a.py"])["triage"] == "real"


def test_an_unreadable_pr_file_list_keeps_a_big_overage_real():
    def api(path):
        if "/pulls/7/files" in path:
            raise SystemExit("gh api failed")
        return fake_api([run(1, "full-suite part 1/3", "failure")])(path)

    d = cd.digest(7, api, lambda i: ratchet_log((T_OUT, 40.0, UNMARKED)))
    assert d["failed"][0]["triage"] == "real"


def test_a_ratchet_overage_beside_a_failed_test_or_another_error_stays_real():
    both = ratchet_log((T_OUT, 31.0, UNMARKED)) + "\nFAILED tests/x.py::test_y - AssertionError"
    assert part(both)["triage"] == "real"
    other = ratchet_log((T_OUT, 31.0, UNMARKED)) + "\nTraceback (most recent call last):"
    assert part(other)["triage"] == "real"


def test_the_full_suite_roll_up_is_triaged_by_its_parts():
    runs = [run(1, "full-suite part 1/3", "failure"), run(2, "full-suite", "failure")]
    logs = {1: ratchet_log((T_OUT, 31.0, UNMARKED)), 2: "##[error]Process completed with exit code 1."}
    d = cd.digest(7, fake_api(runs), lambda i: logs[i])
    assert {f["check"]: f["triage"] for f in d["failed"]} == {"full-suite": "flake", "full-suite part 1/3": "flake"}
    runs.append(run(3, "full-suite part 2/3", "failure"))
    logs[3] = "FAILED tests/x.py::test_y - AssertionError"
    d = cd.digest(7, fake_api(runs), lambda i: logs[i])
    assert {f["check"]: f["triage"] for f in d["failed"]}["full-suite"] == "real"  # one real part keeps it real


def test_the_ground_truth_roll_up_follows_an_infra_part():
    runs = [run(1, "ground-truth part 2/2", "cancelled"), run(2, "ground-truth", "failure")]
    d = cd.digest(7, fake_api(runs), lambda i: "##[error]Process completed with exit code 1.")
    assert {f["check"]: f["triage"] for f in d["failed"]} == {"ground-truth": "infra", "ground-truth part 2/2": "infra"}


def test_det_after_a_db2_infra_failure_is_an_infra_knock_on():  # 5089-20261015T2217Z
    pull = "::error::INFRASTRUCTURE (not a code defect): 'docker pull -q db2' failed after 4 attempts (exit 1)"
    knock = "det Z: no result (its shard did not report)\n##[error]Process completed with exit code 1."
    runs = [run(1, "db2 1/1", "failure"), run(2, "det", "failure")]
    d = cd.digest(7, fake_api(runs), lambda i: {1: pull, 2: knock}[i])
    assert {f["check"]: f["triage"] for f in d["failed"]} == {"db2 1/1": "infra", "det": "infra"}
    runs.append(run(3, "shard 1/6", "failure"))  # a real shard failure beside it: det is a real red
    d = cd.digest(7, fake_api(runs), lambda i: {1: pull, 2: knock, 3: "det A NOT PROVEN"}[i])
    assert {f["check"]: f["triage"] for f in d["failed"]}["det"] == "real"


def test_det_with_no_failed_part_stays_real():
    d = cd.digest(7, fake_api([run(2, "det", "failure")]), lambda i: "det Z: no result (its shard did not report)")
    assert d["failed"][0]["triage"] == "real"


def test_a_cancelled_roll_up_with_no_failed_part_keeps_its_infra_triage():  # #5276: no part to take a verdict from
    for rollup in cd.PARTS:
        d = cd.digest(7, fake_api([run(1, rollup, "cancelled")]), lambda i: "")
        (f,) = d["failed"]
        assert f["check"] == rollup and f["triage"] == "infra"
    runs = [run(1, "det", "cancelled"), run(2, "shard 1/6", "success")]  # parts that passed do not change it
    assert cd.digest(7, fake_api(runs), lambda i: "")["failed"][0]["triage"] == "infra"


FIXED = "tests/core_engine/test_x.py"
STALE_LOG = f"FAILED {FIXED}::test_y - AssertionError"


def test_a_stale_base_main_red_is_main_with_a_merge_repro():  # 5134-20261014T1831Z
    api = fake_api(
        [run(1, "full-suite part 1/3", "failure")], main_files=[FIXED, "docs/a.md"], pr_files=["gitgalaxy/z.py"]
    )
    (f,) = cd.digest(7, api, lambda i: STALE_LOG)["failed"]
    assert f["triage"] == "main" and f["repro"].startswith("stale base") and "git merge origin/main" in f["repro"]


def test_a_failing_test_main_did_not_touch_or_the_pr_edited_stays_real():
    untouched = fake_api([run(1, "full-suite part 1/3", "failure")], main_files=["tests/other/test_o.py"])
    assert cd.digest(7, untouched, lambda i: STALE_LOG)["failed"][0]["triage"] == "real"
    edited = fake_api([run(1, "full-suite part 1/3", "failure")], main_files=[FIXED], pr_files=[FIXED])
    assert cd.digest(7, edited, lambda i: STALE_LOG)["failed"][0]["triage"] == "real"


def _source_stale(pr_files, main_files=("gitgalaxy/core/detector.py",)):
    api = fake_api([run(1, "full-suite part 1/3", "failure")], main_files=list(main_files), pr_files=list(pr_files))
    return cd.digest(7, api, lambda i: STALE_LOG)["failed"][0]


def test_a_pr_that_cannot_move_the_tests_is_stale_when_main_fixed_source_only():  # #5276
    for files in (["docs/a.md"], [".github/workflows/x.yml"], ["tests/other/test_o.py"]):
        f = _source_stale(files)
        assert f["triage"] == "main" and "engine source" in f["repro"] and "git merge origin/main" in f["repro"]


def test_source_stale_stays_real_when_the_pr_could_have_caused_it():  # #5276
    for files in (["gitgalaxy/z.py"], ["tests/core_engine/test_other.py"], ["tests/conftest.py"],
                  ["tests/fixtures/a.json"], ["docs/a.md", "gitgalaxy/z.py"]):  # fmt: skip
        assert _source_stale(files)["triage"] == "real", files
    assert _source_stale(["docs/a.md"], main_files=["scripts/b.txt", "tests/x/test_q.py"])["triage"] == "real"


def test_source_stale_with_an_unreadable_pr_file_list_stays_real():  # #5276
    assert cd.stale_by_source(None, {"gitgalaxy/a.py"}, ["tests/x/test_a.py::t"]) is False
    assert cd.stale_by_source({"docs/a.md"}, {"gitgalaxy/a.py"}, ["tests/x/test_a.py::t"]) is True


def test_real_failures_still_triage_real():
    """No change to how real failures are triaged (#5273): a failed test, a det case, a lint error, a big overage."""
    assert cd.triage("failure", PYTEST_LOG, ["tests/x.py::test_y"]) == "real"
    ex = cd.extract(ratchet_log((T_IN, 90.0, UNMARKED)))
    assert cd.triage("failure", "", [], ex=ex, diff_files=lambda: {"tests/in_diff/test_a.py"}) == "real"
    assert cd.triage("failure", "##[error]E501 x.py:3", []) == "real"
    d = cd.digest(7, fake_api([run(3, "shard 2/6", "failure")]), lambda i: "  det carddemo-acctupdate  NOT PROVEN")
    assert d["failed"][0]["triage"] == "real"
    inside = fake_api([run(1, "full-suite part 1/3", "failure")], pr_files=["tests/in_diff/test_a.py"])
    assert cd.digest(7, inside, lambda i: ratchet_log((T_IN, 90.0, UNMARKED)))["failed"][0]["triage"] == "real"


# #5276: PARTS mirrors the part-job names of three workflows by hand (the check-runs API has no `needs`)
WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
ROLLUP_PARTS = {  # roll-up check -> (workflow, the part jobs whose check-run names its PARTS pattern must match)
    "full-suite": ("smoke-test.yml", {"full-suite-part", "tested-tree", "suite-plan"}),
    "ground-truth": ("mainframe-ground-truth.yml", {"ground-truth-part", "tested-tree", "plan", "ground-truth-warm"}),
    "det": ("det-sweep.yml", {"plan", "shard", "db2", "detmut"}),
}
MATRIX_SAMPLE = {"matrix.group": "1", "matrix.shard": "1/4", "needs.shard-plan.outputs.splits": "3"}  # fmt: skip


def rendered_job_names(workflow):
    """Check-run name of each job (`name:` or the job id) with its matrix expressions filled in."""
    import re

    import pytest

    yaml = pytest.importorskip("yaml")
    jobs = yaml.safe_load((WORKFLOWS / workflow).read_text(encoding="utf-8"))["jobs"]
    names = {}
    for job_id, job in jobs.items():
        name = re.sub(
            r"\$\{\{\s*([\w.-]+)\s*\}\}", lambda m: MATRIX_SAMPLE.get(m.group(1), m.group(0)), job.get("name", job_id)
        )
        assert "${{" not in name, f"{workflow}: job {job_id} name {name!r} has an expression this test cannot render"
        names[job_id] = name
    return jobs, names


def test_every_parts_pattern_still_matches_the_workflow_jobs_it_mirrors():
    import re

    assert set(cd.PARTS) == set(ROLLUP_PARTS), "a PARTS roll-up is missing from (or extra in) ROLLUP_PARTS"
    for rollup, (workflow, expected) in ROLLUP_PARTS.items():
        jobs, names = rendered_job_names(workflow)
        assert rollup in jobs, f"{workflow} has no job {rollup}"
        needs = jobs[rollup]["needs"]
        assert expected <= set(needs), f"{rollup} no longer needs {expected - set(needs)}"
        matched = {job_id for job_id, name in names.items() if re.search(cd.PARTS[rollup], name)}
        assert matched == expected, (
            f"PARTS[{rollup!r}] matches {sorted(matched)} in {workflow}, expected {sorted(expected)}"
        )


def test_every_alternative_of_the_det_pattern_matches_a_job():
    """`det` alternates three part names; one renamed job must not hide behind the others."""
    import re

    _, names = rendered_job_names("det-sweep.yml")
    inner = cd.PARTS["det"].removeprefix("^(").removesuffix(")$")
    for alt in inner.split("|"):
        assert any(re.fullmatch(alt, n) for n in names.values()), f"no det-sweep.yml job matches {alt!r}"


def test_a_job_whose_upstream_failed_as_infra_is_an_infra_knock_on():  # #5276
    runs = [run(1, "plan", "cancelled"), run(2, "shard 1/6", "failure"), run(3, "durations key", "failure")]
    logs = {1: "", 2: "det A: no plan output", 3: "no key"}
    d = cd.digest(7, fake_api(runs), lambda i: logs[i])
    assert {f["check"]: f["triage"] for f in d["failed"]} == {
        "plan": "infra",
        "shard 1/6": "infra",
        "durations key": "real",
    }
    runs.append(run(4, "tested-tree", "startup_failure"))
    d = cd.digest(7, fake_api(runs), lambda i: logs.get(i, ""))
    assert {f["check"]: f["triage"] for f in d["failed"]}["durations key"] == "infra"
    logs[2] = "FAILED tests/x.py::test_y - AssertionError"  # a failing test beside an infra upstream stays real
    d = cd.digest(7, fake_api(runs), lambda i: logs.get(i, ""))
    assert {f["check"]: f["triage"] for f in d["failed"]}["shard 1/6"] == "real"


def test_every_upstream_pattern_matches_a_job_its_dependent_needs():  # #5276
    import re

    for workflow in ("smoke-test.yml", "mainframe-ground-truth.yml", "det-sweep.yml"):
        jobs, names = rendered_job_names(workflow)
        for dep, up in cd.UPSTREAM.items():
            for dep_id in (j for j, n in names.items() if re.search(dep, n)):
                ups = {j for j, n in names.items() if re.search(up, n)}
                needs = jobs[dep_id].get("needs") or []
                needs = {needs} if isinstance(needs, str) else set(needs)
                assert ups & needs, f"{workflow}: {dep_id} needs none of {sorted(ups)}"


# --- #6534: main's tip through one GraphQL query ---------------------------------------------------------------------


def _run(i, name, status="completed", conclusion="success"):
    return {"id": i, "name": name, "status": status, "conclusion": conclusion, "app": {"slug": "github-actions"},
            "details_url": f"https://x/{i}", "html_url": f"https://x/{i}"}  # fmt: skip


def _main_graphql(runs, parents=(), cut=False):
    nodes = [
        {"databaseId": r["id"], "name": r["name"], "status": r["status"].upper(),
         "conclusion": r["conclusion"].upper() if r["conclusion"] else None, "detailsUrl": r["details_url"],
         "url": r["html_url"]}
        for r in runs
    ]  # fmt: skip
    suite = {"createdAt": None, "app": {"slug": "github-actions"},
             "checkRuns": {"totalCount": len(nodes) + cut * 1000, "nodes": nodes}}  # fmt: skip
    tip = {"oid": "m" * 40, "parents": {"nodes": [{"oid": x} for x in parents]},
           "checkSuites": {"totalCount": 1, "nodes": [suite]}}  # fmt: skip
    seen = []

    def graphql(query, variables):
        assert query == cd.MAIN_QUERY
        seen.append(variables)
        return {"repository": {"ref": {"target": tip}}}

    graphql.seen = seen
    return graphql


def _no_rest(path):
    raise AssertionError(f"unexpected REST read {path}")


def test_main_green_and_failures_read_one_query_and_match_rest():
    runs = [_run(1, "det"), _run(2, "ruff", conclusion="failure"), _run(3, "mypy", "in_progress", None)]
    gql = _main_graphql(runs)
    tip = cd.main_tip(_no_rest, gql)
    assert cd.main_green(_no_rest, graphql=gql, tip=tip) == cd.main_green(fake_api([], main_runs=runs))
    assert (
        cd.main_failures(_no_rest, graphql=gql, tip=tip) == {"ruff"} == cd.main_failures(fake_api([], main_runs=runs))
    )
    assert len(gql.seen) == 1  # both functions share the one read


def test_a_tip_with_pending_checks_walks_back_through_rest_from_the_graphql_parent():
    parent = "p" * 40
    gql = _main_graphql([_run(1, "det", "queued", None)], parents=[parent])

    def api(path):
        assert parent in path
        return {"parents": []} if path.endswith(parent) else {"check_runs": [_run(9, "det", conclusion="failure")]}

    assert cd.main_failures(api, graphql=gql) == {"det"}


def test_an_unreadable_or_cut_main_query_reads_through_rest():
    runs = [_run(1, "det")]

    def fail(q, v):
        raise SystemExit("x")

    for gql in (fail, _main_graphql(runs, cut=True)):
        assert cd.main_green(fake_api([], main_runs=runs), graphql=gql) == ("m" * 40, {"det"})
    assert cd.main_green(_no_rest_unreadable, graphql=fail) == ("", set())


def _no_rest_unreadable(path):
    raise SystemExit("gh api failed")
