"""#5136 / #5130 / #5131: post-merge.yml's cadence-capped dispatch (tests/tools/post_merge_dispatch.py).

decide() is pure: every branch of the rule, then the TARGETS table pinned against the workflow files themselves (each
target can be dispatched, has no main push trigger of its own, keeps a nightly schedule, is watched by Main Watch, and
a `from-pr-filter` target's relevance patterns are exactly its PR `paths`).
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")  # before workflow_inputs, which imports it

sys.path.insert(0, str(Path(__file__).resolve().parent))
import post_merge_dispatch as pmd  # noqa: E402
import workflow_inputs  # noqa: E402

SHA, OLD, OLDER = "c" * 40, "b" * 40, "a" * 40
NOW = pmd.epoch("2026-10-14T18:00:00Z")
H = 3600.0
CADENCE = 3 * H


def run(sha=OLD, hours_ago=4.0, event="workflow_dispatch", conclusion="success", status="completed"):
    stamp = datetime.fromtimestamp(NOW - hours_ago * H, timezone.utc)
    return {
        "head_sha": sha, "event": event, "conclusion": conclusion, "status": status,
        "created_at": stamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }  # fmt: skip


def decide(runs, changed=("gitgalaxy/core/detector.py",), patterns=pmd.NOT_DOCS):
    asked = []

    def changed_since(base):
        asked.append(base)
        return None if changed is None else list(changed)

    go, reason = pmd.decide(SHA, NOW, CADENCE, runs, list(patterns), changed_since)
    return go, reason, asked


# --- the rule ---------------------------------------------------------------------------------------------------------


def test_no_earlier_run_dispatches():
    assert decide([])[0] is True


def test_a_run_for_this_sha_already_exists_skips_whatever_its_conclusion():
    for conclusion in ("success", "failure", "cancelled", None):
        go, reason, asked = decide([run(sha=SHA, hours_ago=10, conclusion=conclusion)])
        assert go is False and "already" in reason and asked == []


@pytest.mark.parametrize("event", ["workflow_dispatch", "schedule", "push"])
def test_inside_the_cadence_window_skips_and_every_main_event_counts(event):
    go, reason, asked = decide([run(hours_ago=1, event=event)])
    assert go is False and "cadence" in reason and asked == []  # the nightly counts toward the window too


def test_an_in_progress_run_counts_toward_the_window():
    go, reason, _ = decide([run(hours_ago=0.2, status="in_progress", conclusion=None)])
    assert go is False and "cadence" in reason


def test_a_cancelled_run_does_not_hold_the_window():
    go, _, asked = decide([run(hours_ago=0.5, conclusion="cancelled"), run(sha=OLDER, hours_ago=5)])
    assert go is True and asked == [OLDER]  # compared against the newest run that gave a verdict


def test_pull_request_runs_are_ignored():
    go, reason, _ = decide([run(sha=SHA, hours_ago=0.1, event="pull_request")])
    assert go is True and reason == "no earlier run on main"


def test_window_expired_and_a_relevant_change_dispatches():
    go, reason, asked = decide([run(hours_ago=3.5), run(sha=OLDER, hours_ago=9)])
    assert go is True and asked == [OLD] and "detector.py" in reason


@pytest.mark.parametrize("changed", [["docs/ci.md"], ["README.md"], ["tests/README.md", "docs/a/b.json"], []])
def test_only_irrelevant_changes_skip(changed):
    go, reason, _ = decide([run(hours_ago=5)], changed=changed)
    assert go is False and "no file it reads changed" in reason


def test_an_unknown_comparison_dispatches():
    assert decide([run(hours_ago=5)], changed=None)[0] is True  # error, truncated or diverged: fail-open


def test_a_crucible_filter_and_its_exclusions():
    estate = pmd.patterns_for("estate-crucible.yml")
    assert pmd.matches("gitgalaxy/core/detector.py", estate)
    assert not pmd.matches("gitgalaxy/tools/cobol_to_java/det/emit.py", estate)  # `!` after the include wins
    assert not pmd.matches("gitgalaxy/README.md", estate)
    assert not pmd.matches("tests/tools/det_port.py", estate)
    go, _, _ = decide([run(hours_ago=5)], changed=["gitgalaxy/tools/cobol_to_java/x.py"], patterns=estate)
    assert go is False


def test_the_last_matching_pattern_decides():
    assert pmd.matches("docs/x.py", ["**", "!docs/**"]) is False
    assert pmd.matches("docs/x.py", ["!docs/**", "**"]) is True
    assert pmd.matches("a.py", ["!**/*.md"]) is False  # a negation alone includes nothing


@pytest.mark.parametrize(
    "pattern,path",
    [
        ("gitgalaxy/**", "gitgalaxy/a/b.py"), ("**/*.md", "README.md"), ("**/*.md", "a/b/c.md"),
        ("tests/equivalence/*/case.json", "tests/equivalence/x/case.json"),
        ("tests/equivalence/*/case.json", "tests/equivalence/x/y/case.json"),
        ("tests/tools/cics_crucible*.py", "tests/tools/cics_crucible_x.py"), ("a?c", "abc"), ("**", ".github/x.yml"),
    ],
)  # fmt: skip
def test_glob_agrees_with_workflow_inputs(pattern, path):
    assert bool(pmd.glob_re(pattern).match(path)) == bool(workflow_inputs.glob_re(pattern).match(path))


# --- the targets, pinned against the workflow files ----------------------------------------------------------------


def load(name):
    doc = yaml.safe_load((pmd.WORKFLOWS / name).read_text(encoding="utf-8"))
    return doc, doc.get(True) or doc.get("on") or {}  # PyYAML reads the bare key `on` as True


@pytest.mark.parametrize("name", sorted(pmd.TARGETS))
def test_target_is_dispatch_only_on_main_with_a_nightly(name):
    _, on = load(name)
    assert "workflow_dispatch" in on
    assert "schedule" in on, "the nightly is what covers a day the idle dispatch never fires"
    push = on.get("push") or {}
    assert not push.get("branches"), "a main push trigger would start it on every merge again (#5131)"
    assert "branches-ignore" not in push and (not push or push.get("tags")), "only a tag push may remain"


@pytest.mark.parametrize("name", sorted(pmd.TARGETS))
def test_target_is_watched_by_main_watch(name):
    doc, _ = load(name)
    _, mw = load("main-watch.yml")
    assert doc["name"] in mw["workflow_run"]["workflows"]


@pytest.mark.parametrize("name", sorted(n for n, s in pmd.TARGETS.items() if s == pmd.FROM_PR_FILTER))
def test_pr_filter_reader_matches_yaml(name):
    _, on = load(name)
    want = on["pull_request"]["paths"]
    assert want and pmd.patterns_for(name) == want


def test_pr_paths_reader_shapes():
    text = (
        "on:\n  pull_request:\n    types: [opened]\n    paths:\n"
        '      - "a/**"  # why\n      # a comment\n      - "!a/b.md"\n    branches: [main]\n'
        '  push:\n    paths:\n      - "zzz"\n'
    )
    assert pmd.pr_paths(text) == ["a/**", "!a/b.md"]
    assert pmd.pr_paths("on:\n  push:\n") == []


def test_the_dispatcher_reads_only_what_post_merge_checks_out():
    wf = (pmd.WORKFLOWS / "post-merge.yml").read_text(encoding="utf-8")
    assert "tests/tools/post_merge_dispatch.py" in wf and ".github/workflows" in wf
    assert "run: python3 tests/tools/post_merge_dispatch.py" in wf
    src = Path(pmd.__file__).read_text(encoding="utf-8")
    assert "import yaml" not in src  # the runner's bare python3


def test_the_old_per_merge_triggers_are_gone():
    # #5130: the OS grid left smoke-test.yml (which keeps the per-merge full suite); #5131: these read-only workflows
    # lost their push trigger and so their tested-tree gate
    smoke, _ = load("smoke-test.yml")
    assert "smoke-test" not in smoke["jobs"]
    for name in pmd.TARGETS:
        doc, _ = load(name)
        assert "tested-tree" not in doc["jobs"], name


# #6670: advisory checks that never failed on a PR run only here (dispatch + nightly); their PR trigger stays for `paths`
POST_MERGE_ONLY = {
    "fact-crosscheck.yml": "crosscheck",
    "unicode-gauntlet.yml": "gauntlet",
    "estate-crucible.yml": "estate",
    "crucible-path-independence.yml": "path-independence",
}


@pytest.mark.parametrize("name", sorted(POST_MERGE_ONLY))
def test_a_post_merge_only_check_skips_on_a_pr_and_is_dispatched(name):
    doc, _ = load(name)
    assert pmd.TARGETS.get(name) == pmd.FROM_PR_FILTER, f"{name} must be a from-pr-filter dispatch target"
    assert pmd.pr_paths((pmd.WORKFLOWS / name).read_text(encoding="utf-8")), f"{name} lost the paths the dispatch reads"
    assert set(doc["jobs"]) == {POST_MERGE_ONLY[name]}, f"{name}: a new job must skip on a PR too"
    for job, spec in doc["jobs"].items():
        cond = str(spec.get("if") or "")
        assert "github.event_name != 'pull_request'" in cond, f"{name}:{job} still runs on a PR"
        assert "||" not in cond, f"{name}:{job}: an `||` would let a PR event through"
