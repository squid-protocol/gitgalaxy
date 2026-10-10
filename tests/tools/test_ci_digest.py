"""ci_digest (#4790): triage, the log extract and the local repro of each failed check, without the network."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ci_digest as cd  # noqa: E402

SHA = "a" * 40


def fake_api(runs, mergeable_state="clean", main_runs=()):
    def api(path):
        if path.endswith("/commits/main"):
            return {"sha": "m" * 40}
        if "/commits/" + "m" * 40 in path:
            return {"check_runs": list(main_runs)}
        if path.endswith("/pulls/7"):
            return {"head": {"sha": SHA}, "mergeable_state": mergeable_state}
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
