"""pr_check (#4270): one call for a PR's merge readiness -- a cancelled run ignored ONLY beside a same-name success
on the same SHA, flagged paths, and --merge only when everything is green. A fake `gh api`; no network."""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pr_check as pc

SHA = "ab2807081f97ac321527f727a72c3b5d1c5c0c97"


def run(name, conclusion, i, status="completed"):
    return {"id": i, "name": name, "status": status, "conclusion": conclusion}


def fake_api(pr=None, runs=(), statuses=(), files=()):
    calls = []
    pr = {"number": 7, "title": "t", "state": "open", "merged": False, "draft": True, "mergeable": True,
          "mergeable_state": "clean", "node_id": "PR_x", "head": {"sha": SHA}, **(pr or {})}  # fmt: skip

    def api(path):
        calls.append(path)
        if path.endswith("/pulls/7"):
            return pr
        if "/check-runs" in path:
            return {"total_count": len(runs), "check_runs": list(runs)}
        if path.endswith("/status"):
            return {"statuses": list(statuses)}
        if "/files" in path:
            return list(files)
        raise AssertionError(path)

    api.calls = calls  # type: ignore[attr-defined]
    return api


def test_a_cancelled_duplicate_is_ignored_only_beside_a_success():
    c = pc.classify([run("rosetta-audit", "cancelled", 1), run("rosetta-audit", "success", 2),
                     run("lint", "cancelled", 3), run("smoke", "skipped", 4)], [])  # fmt: skip
    assert c["passed"] == ["rosetta-audit"]
    assert c["failed"] == ["lint (cancelled)"]  # no success beside it: a real cancellation
    assert c["neutral"] == ["smoke (skipped)"]
    assert c["ignored"] == ["rosetta-audit: 1 cancelled run(s) ignored -- a same-name run on this SHA succeeded"]


def test_a_skipped_event_run_after_a_success_does_not_hide_it_and_a_rerun_wins():
    c = pc.classify([run("rosetta-audit", "success", 1), run("rosetta-audit", "skipped", 2),
                     run("det", "failure", 3), run("det", "success", 4), run("gate", None, 5, "in_progress")],
                    [{"context": "ci/x", "state": "pending"}])  # fmt: skip
    assert c["passed"] == ["det", "rosetta-audit"] and not c["failed"]
    assert c["pending"] == ["gate (in_progress)", "ci/x (pending)"]
    assert any("skipped run(s) after the successful one" in x for x in c["ignored"])


def test_files_are_flagged():
    assert pc.flag("tests/_cics_crucible_pin.py").startswith("CICS crucible PIN")
    assert pc.flag("tests/estate_crucible/baseline.json") == "baseline"
    assert pc.flag("tests/cobol_mainframe/ground_truth_ledger.json") == "ledger"
    assert pc.flag("tests/golden/x.json") == "golden"
    assert pc.flag("docs/language_status/evidence/a.json") == "evidence"
    assert pc.flag("tests/tools/pr_check.py") is None


def test_green_pr_is_ready_in_four_calls():
    api = fake_api(runs=[run("ruff-audit", "success", 1)],
                   files=[{"filename": "tests/_cics_crucible_pin.py", "status": "modified", "additions": 1, "deletions": 1}])  # fmt: skip
    res = pc.check(7, api)
    assert res["ready"] and res["draft"] and res["head_sha"] == SHA
    assert len(api.calls) == 4 and all("per_page=100" in c for c in api.calls if "check-runs" in c or "files" in c)
    out = pc.report(res)
    assert "READY to merge" in out and "FLAG CICS crucible PIN" in out


def test_not_ready_reasons():
    res = pc.check(7, fake_api(pr={"mergeable": False, "mergeable_state": "dirty"},
                               runs=[run("det", "failure", 1), run("x", None, 2, "queued")]))  # fmt: skip
    assert not res["ready"]
    text = "; ".join(res["reasons"])
    assert "merge conflicts" in text and "failed: det (failure)" in text and "pending: x (queued)" in text
    merged = pc.check(
        7, fake_api(pr={"state": "closed", "merged": True, "mergeable": None}, runs=[run("a", "success", 1)])
    )
    assert merged["reasons"] == ["merged already"] and merged["state"] == "merged"


def test_merge_only_when_green(capsys, monkeypatch):
    seen = []

    def fake_run(argv):
        seen.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(pc, "_run", fake_run)
    red = fake_api(runs=[run("det", "failure", 1)])
    assert pc.main(["7", "--merge"], api=red) == 1 and seen == []
    assert "not merging #7" in capsys.readouterr().err
    green = fake_api(runs=[run("det", "success", 1)])
    assert pc.main(["7", "--merge"], api=green) == 0
    assert [a[:3] for a in seen] == [["gh", "pr", "ready"], ["gh", "pr", "merge"]]
    assert "merged #7" in capsys.readouterr().out


def test_merge_marks_ready_then_squashes_pinned_to_the_head():
    seen = []

    def ok(argv):
        seen.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    assert pc.merge({"number": 7, "draft": True, "head_sha": SHA, "node_id": "PR_x"}, ok) == []
    assert seen[0][:3] == ["gh", "pr", "ready"]
    assert seen[1][:3] == ["gh", "pr", "merge"] and "--squash" in seen[1] and SHA in seen[1]

    seen.clear()

    def ready_fails(argv):
        seen.append(argv)
        return subprocess.CompletedProcess(argv, 1 if argv[:3] == ["gh", "pr", "ready"] else 0, "", "graphql error")

    assert pc.merge({"number": 7, "draft": True, "head_sha": SHA, "node_id": "PR_x"}, ready_fails) == []
    assert seen[1][:3] == ["gh", "api", "graphql"] and "id=PR_x" in seen[1]  # the mutation directly
