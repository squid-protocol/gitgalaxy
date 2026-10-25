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
    pr = {"number": 7, "title": "t", "state": "open", "merged": False, "draft": False, "mergeable": True,
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
    assert pc.flag("tests/crucible_pins.toml").startswith("crucible PIN")
    assert pc.flag("tests/estate_crucible/baseline.json") == "baseline"
    assert pc.flag("tests/cobol_mainframe/ground_truth_ledger.json") == "ledger"
    assert pc.flag("tests/golden/x.json") == "golden"
    assert pc.flag("docs/language_status/evidence/a.json") == "evidence"
    assert pc.flag("tests/tools/pr_check.py") is None


def test_green_pr_is_ready_in_four_calls():
    api = fake_api(pr={"draft": True}, runs=[run("ruff-audit", "success", 1)],
                   files=[{"filename": "tests/crucible_pins.toml", "status": "modified", "additions": 1, "deletions": 1}])  # fmt: skip
    res = pc.check(7, api)
    assert res["ready"] and res["draft"] and res["head_sha"] == SHA
    assert len(api.calls) == 4 and all("per_page=100" in c for c in api.calls if "check-runs" in c or "files" in c)
    out = pc.report(res)
    assert "READY to merge" in out and "FLAG crucible PIN" in out


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
    assert [a[:3] for a in seen] == [["gh", "pr", "merge"]]
    assert "merged #7" in capsys.readouterr().out


def test_merging_a_pin_change_runs_sync_and_a_sync_failure_is_not_fatal(capsys, monkeypatch):
    seen = []
    sync_rc = [0]

    def fake_run(argv):
        seen.append(argv)
        if argv[1].endswith("crucible_pins.py"):
            return subprocess.CompletedProcess(
                argv, sync_rc[0], "SYNCED cics: v0.5.0 -> v0.6.0\n", "REFUSE x" if sync_rc[0] else ""
            )
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(pc, "_run", fake_run)
    pin = [{"filename": "tests/crucible_pins.toml", "status": "modified", "additions": 1, "deletions": 1}]
    other = [{"filename": "tests/tools/x.py", "status": "modified", "additions": 1, "deletions": 1}]
    green = [run("det", "success", 1)]
    assert pc.main(["7", "--merge"], api=fake_api(runs=green, files=other)) == 0
    assert not any(a[1].endswith("crucible_pins.py") for a in seen)  # an ordinary PR: no sync
    seen.clear()
    assert pc.main(["7", "--merge"], api=fake_api(runs=green, files=pin)) == 0
    assert seen[-1][2:] == ["sync"] and "SYNCED cics: v0.5.0 -> v0.6.0" in capsys.readouterr().out
    sync_rc[0] = 1
    assert pc.main(["7", "--merge"], api=fake_api(runs=green, files=pin)) == 0  # merged: the failure is only reported
    out = capsys.readouterr().out
    assert "merged #7" in out and "WARNING" in out and "REFUSE x" in out


def test_merge_marks_ready_then_squashes_pinned_to_the_head():
    seen = []

    def ok(argv):
        seen.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    # #5104: a draft is marked ready and NOT merged (its skipped checks read as green)
    errs = pc.merge({"number": 7, "draft": True, "head_sha": SHA, "node_id": "PR_x"}, ok)
    assert len(errs) == 1 and "not merged" in errs[0] and pc.draft_marked_ready(errs)
    assert not pc.draft_marked_ready([]) and not pc.draft_marked_ready(["gh pr merge failed: x"])
    assert [a[:3] for a in seen] == [["gh", "pr", "ready"]]

    seen.clear()
    assert pc.merge({"number": 7, "draft": False, "head_sha": SHA, "node_id": "PR_x"}, ok) == []
    assert seen[0][:3] == ["gh", "pr", "merge"] and "--squash" in seen[0] and SHA in seen[0]

    seen.clear()

    def ready_fails(argv):
        seen.append(argv)
        return subprocess.CompletedProcess(argv, 1 if argv[:3] == ["gh", "pr", "ready"] else 0, "", "graphql error")

    assert len(pc.merge({"number": 7, "draft": True, "head_sha": SHA, "node_id": "PR_x"}, ready_fails)) == 1
    assert seen[1][:3] == ["gh", "api", "graphql"] and "id=PR_x" in seen[1]  # the mutation directly


def test_main_merge_on_a_draft_only_marks_it_ready(monkeypatch):
    # #5104: a draft's heavy checks are skipped (green), so --merge must not merge it in the same call
    seen = []
    monkeypatch.setattr(pc, "_run", lambda argv: seen.append(argv) or subprocess.CompletedProcess(argv, 0, "", ""))
    api = fake_api(pr={"draft": True}, runs=[run("ruff-audit", "success", 1)])
    assert pc.main(["7", "--merge"], api=api) == 1
    assert [a[:3] for a in seen] == [["gh", "pr", "ready"]]


# --- #6534 slice 4: check() reads through one GraphQL query, REST on anything short of whole ---


def gql_pr(runs=(), files=(), contexts=(), **over):
    """A CHECK_QUERY pullRequest: one check suite holding `runs` (name, conclusion, status)."""
    nodes = [{"databaseId": i, "name": n, "status": st.upper(), "conclusion": c.upper() if c else None,
              "detailsUrl": f"https://github.com/o/r/actions/runs/{i}", "url": f"https://x/{i}"}
             for i, (n, c, st) in enumerate(runs, 1)]  # fmt: skip
    p = {"id": "PR_x", "number": 7, "title": "t", "state": "OPEN", "merged": False, "isDraft": False,
         "mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN", "headRefOid": SHA,
         "files": {"totalCount": len(files), "nodes": list(files)},
         "commits": {"nodes": [{"commit": {"oid": SHA, "status": {"contexts": list(contexts)},
                                           "checkSuites": {"totalCount": 1, "nodes": [{
                                               "createdAt": "t", "app": {"slug": "github-actions"},
                                               "checkRuns": {"totalCount": len(nodes), "nodes": nodes}}]}}}]},
         **over}  # fmt: skip
    return p


def fake_graphql(p):
    calls = []

    def graphql(query, variables):
        calls.append((query, variables))
        if isinstance(p, Exception):
            raise p
        return {"repository": {"pullRequest": p}}

    graphql.calls = calls  # type: ignore[attr-defined]
    return graphql


def no_rest(path):
    raise AssertionError(f"REST read {path}")


PIN_FILE = {"path": "tests/crucible_pins.toml", "additions": 1, "deletions": 1, "changeType": "MODIFIED"}


def test_pr_fields_live_in_pr_check_and_shepherd_uses_them():
    import shepherd_gh as sg

    assert "@@SUITES@@" not in pc.PR_FIELDS and "checkSuites(first: 100)" in pc.PR_FIELDS
    assert sg.PR_FIELDS is pc.PR_FIELDS and pc.PR_FIELDS in sg.PR_QUERY


def test_graphql_and_rest_give_the_same_result():
    cases = [
        ({}, [("ruff-audit", "success", "completed")], [PIN_FILE]),
        ({"isDraft": True}, [("a", "success", "completed"), ("a", "cancelled", "completed")], []),
        ({"mergeable": "CONFLICTING", "mergeStateStatus": "DIRTY"},
         [("det", "failure", "completed"), ("x", None, "queued")], [PIN_FILE]),
        ({"mergeStateStatus": "BLOCKED"}, [("a", "skipped", "completed")], []),
    ]  # fmt: skip
    for over, runs, files in cases:
        g = pc.check(
            7, no_rest, fake_graphql(gql_pr(runs, files, contexts=[{"context": "ci/x", "state": "PENDING"}], **over))
        )
        rest_files = [{"filename": f["path"], "status": "modified", "additions": 1, "deletions": 1} for f in files]
        rest_runs = [run(n, c, i, st) for i, (n, c, st) in enumerate(runs, 1)]
        rest = pc.check(7, fake_api(
            pr={"draft": over.get("isDraft", False), "mergeable": over.get("mergeable") != "CONFLICTING",
                "mergeable_state": over.get("mergeStateStatus", "CLEAN").lower()},
            runs=rest_runs, statuses=[{"context": "ci/x", "state": "pending"}], files=rest_files))  # fmt: skip
        assert g == rest


def test_a_green_pr_is_one_graphql_call_and_no_rest():
    gq = fake_graphql(gql_pr([("a", "success", "completed")], [PIN_FILE]))
    res = pc.check(7, no_rest, gq)
    assert res["ready"] and res["head_sha"] == SHA and res["node_id"] == "PR_x" and len(gq.calls) == 1
    assert res["files"][0]["flag"].startswith("crucible PIN")
    assert gq.calls[0][1] == {"owner": "squid-protocol", "name": "gitgalaxy", "n": 7}


def test_every_change_type_maps_to_a_rest_status():
    for ct, want in {"ADDED": "added", "MODIFIED": "modified", "REMOVED": "removed", "RENAMED": "renamed",
                     "COPIED": "copied", "CHANGED": "changed"}.items():  # fmt: skip
        f = {"path": "a.py", "additions": 2, "deletions": 3, "changeType": ct}
        got = pc.check(7, no_rest, fake_graphql(gql_pr([("a", "success", "completed")], [f])))["files"][0]
        assert (got["status"], got["additions"], got["deletions"]) == (want, 2, 3)


def test_incomplete_graphql_reads_fall_back_to_rest():
    ok = [("a", "success", "completed")]
    big = gql_pr(ok, [PIN_FILE])
    big["files"]["totalCount"] = 101  # more files than came back
    cut = gql_pr(ok)
    cut["commits"]["nodes"][0]["commit"]["checkSuites"]["nodes"][0]["checkRuns"]["totalCount"] = 101
    moved = gql_pr(ok, headRefOid="f" * 40)
    broken = gql_pr(ok)
    del broken["files"]
    for bad in (
        SystemExit("gh api graphql failed"), None, big, cut, moved, broken,
        gql_pr(ok, mergeable="UNKNOWN"), gql_pr(ok, mergeStateStatus="UNKNOWN"),
    ):  # fmt: skip
        api = fake_api(runs=[run("rest-run", "success", 1)])
        res = pc.check(7, api, fake_graphql(bad))
        assert len(api.calls) == 4 and res["checks"]["passed"] == ["rest-run"], bad


def test_main_reads_through_graphql_by_default_and_rest_with_an_injected_api(monkeypatch, capsys):
    gq = fake_graphql(gql_pr([("a", "success", "completed")]))
    monkeypatch.setattr(pc, "gh_graphql", gq)
    assert pc.main(["7", "--json"]) == 0  # the default api (gh_api) is never called: the query answered
    assert len(gq.calls) == 1 and '"ready": true' in capsys.readouterr().out
    assert pc.main(["7"], api=fake_api(runs=[run("a", "success", 1)])) == 0
    assert len(gq.calls) == 1  # an injected api is REST only
