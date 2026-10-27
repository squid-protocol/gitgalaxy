"""generated_branch (#4847): publish/fetch/show against a local bare remote (no network), and a lint that main is
written by bot workflows only where listed -- the history bots publish to `generated` instead."""

import re
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import generated_branch as gb  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO / ".github" / "workflows"


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def remote_and_clone(tmp_path):
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", str(remote))
    clone = tmp_path / "clone"
    git(tmp_path, "clone", "-q", str(remote), str(clone))
    git(clone, "config", "user.email", "t@t")
    git(clone, "config", "user.name", "t")
    (clone / "docs").mkdir()
    (clone / "docs" / "h.csv").write_text("seed\n", newline="\n")
    git(clone, "add", ".")
    git(clone, "commit", "-q", "-m", "seed")
    git(clone, "push", "-q", "origin", "HEAD:main")
    return remote, clone


def test_first_publish_creates_the_branch_and_leaves_the_checkout_alone(remote_and_clone):
    remote, clone = remote_and_clone
    head = git(clone, "rev-parse", "HEAD")
    (clone / "docs" / "h.csv").write_text("seed\nrow1\n", newline="\n")
    assert gb.publish(["docs/h.csv"], "m", root=clone, stamp="w1")
    assert git(remote, "show", "generated:docs/h.csv") == "seed\nrow1"
    assert "Source: main @" in git(remote, "show", "generated:.generated_from/w1.txt")
    assert git(clone, "rev-parse", "HEAD") == head and git(clone, "status", "--porcelain").endswith("M docs/h.csv")


def test_unchanged_files_commit_nothing_and_a_change_is_one_commit(remote_and_clone):
    remote, clone = remote_and_clone
    assert gb.publish(["docs/h.csv"], "m", root=clone, stamp="w1")
    assert gb.publish(["docs/h.csv"], "m", root=clone, stamp="w1") is None
    (clone / "docs" / "h.csv").write_text("changed\n", newline="\n")
    assert gb.publish(["docs/h.csv"], "m2", root=clone, stamp="w1")
    assert git(remote, "rev-list", "--count", "generated") == "2"


def test_writers_with_disjoint_paths_do_not_overwrite_each_other(remote_and_clone):
    remote, clone = remote_and_clone
    (clone / "docs" / "other.json").write_text("{}\n", newline="\n")
    assert gb.publish(["docs/other.json"], "other", root=clone)
    assert gb.publish(["docs/h.csv"], "mine", root=clone)
    assert git(remote, "show", "generated:docs/other.json") == "{}"
    assert git(remote, "show", "generated:docs/h.csv") == "seed"


def test_fetch_restores_the_published_copy_and_falls_back_when_absent(remote_and_clone):
    remote, clone = remote_and_clone
    assert gb.fetch(["docs/h.csv"], root=clone) == []  # no generated branch yet: the committed copy stays
    assert gb.show("docs/h.csv", root=clone) == b"seed\n"
    (clone / "docs" / "h.csv").write_text("seed\nnewer\n", newline="\n")
    gb.publish(["docs/h.csv"], "m", root=clone)
    git(clone, "checkout", "-q", "--", "docs/h.csv")
    assert gb.show("docs/h.csv", root=clone) == b"seed\nnewer\n"
    assert gb.fetch(["docs/h.csv", "docs/not-published.csv"], root=clone) == ["docs/h.csv"]
    assert (clone / "docs" / "h.csv").read_text() == "seed\nnewer\n"


def test_publish_expands_a_directory_to_the_files_beneath_it(remote_and_clone):
    remote, clone = remote_and_clone
    rep = clone / "docs" / "report"
    (rep / "a").mkdir(parents=True)
    (rep / "a" / "report.md").write_text("one\n", newline="\n")
    (rep / "README.md").write_text("top\n", newline="\n")
    assert gb.expand(["docs/report", "docs/h.csv"], clone) == [
        "docs/report/README.md",
        "docs/report/a/report.md",
        "docs/h.csv",
    ]
    assert gb.publish(["docs/report"], "m", root=clone)
    assert git(remote, "show", "generated:docs/report/a/report.md") == "one"
    assert git(remote, "show", "generated:docs/report/README.md") == "top"
    assert gb.publish(["docs/report"], "again", root=clone) is None  # unchanged: nothing committed


def test_publish_refuses_a_missing_file(remote_and_clone):
    _, clone = remote_and_clone
    with pytest.raises(FileNotFoundError):
        gb.publish(["docs/nope.csv"], "m", root=clone)


# --- the workflows -----------------------------------------------------------------------------------------------

# Bot workflows that still land a commit on main through a PR. Each is a known gap (#4847 / #4935), not a pattern to
# copy: new bot output goes to `generated` through tests/tools/generated_branch.py.
STILL_COMMITS_TO_MAIN = {
    "evidence-refresh.yml",  # evidence records + det-sweep ledger: inputs of human approval, must be on main (its report is MOVED)
    "release-crucible-archive.yml",  # opens its PR in language-crucible, not in this repo
}
MOVED = {
    "call-resolution-history.yml": ["docs/self_scan/call_resolution_history.csv"],
    "graph-comparison-history.yml": ["docs/self_scan/graph_comparison_ledger.json"],
    "tree-sitter-accuracy-history.yml": ["docs/self_scan/tree_sitter_accuracy_history.csv"],
    "tri-comparison-history.yml": ["docs/self_scan/tri_comparison_ledger.json"],
    "mainframe-ground-truth.yml": ["docs/self_scan/ground_truth_history.jsonl"],  # #4963
    "gitgalaxy.yml": ["docs/gitgalaxy_architecture_brief.md"],  # #4963
    "archetype-validation.yml": ["gitgalaxy/standards/archetype_brains/archetype_validation.json"],
    # #5057: rendered from committed sources, never committed (tests/tools/generated_docs.py PAGES)
    "generated-docs.yml": [
        "docs/language_status/oracle_assumptions.md",
        "docs/language_status/cics_spec_status.md",
        "docs/language_status/cobolrt_rules.md",  # #4711
        "docs/language_status/readiness_report.md",  # #4725
        "docs/language_status/progress.md",  # #5280
        "docs/language_status/progress.json",  # #5280
        "docs/language_status/progress.svg",  # #5286
    ],
}


def _text(name):
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def _code(name):
    return "\n".join(ln for ln in _text(name).splitlines() if not ln.lstrip().startswith("#"))


def test_only_the_listed_workflows_commit_to_main():
    offenders = []
    for p in sorted(WORKFLOWS.glob("*.yml")):
        code = _code(p.name)
        if re.search(r"create-pull-request@|gh pr merge|git push[^\n]*\borigin\b[^\n]*\bmain\b", code):
            offenders.append(p.name)
    assert set(offenders) == STILL_COMMITS_TO_MAIN, (
        f"workflows committing to main: {offenders}; publish bot output to `generated` "
        f"(tests/tools/generated_branch.py) or list the new writer here with a reason"
    )


@pytest.mark.parametrize("name", sorted(MOVED))
def test_a_moved_writer_publishes_to_generated_and_never_opens_a_pr(name):
    code = _code(name)
    assert "create-pull-request" not in code and "gh pr merge" not in code and "AUTOMATION_PAT" not in code
    assert "generated_branch.py publish" in code
    for path in MOVED[name]:
        assert path in code, f"{name} does not publish {path}"
    assert re.search(r"pull-requests:\s*write", code) is None, "a writer that opens no PR needs no pull-requests: write"
    assert re.search(r"persist-credentials:\s*true", code), "the publish step pushes with the checkout's credentials"


@pytest.mark.parametrize(
    "name",
    [
        "call-resolution-history.yml",
        "tree-sitter-accuracy-history.yml",
        "graph-comparison-history.yml",
        "mainframe-ground-truth.yml",
    ],
)
def test_an_appending_writer_starts_from_the_published_series(name):
    """The history CSV is appended to: it must be restored from generated before the tool runs, or each run would
    append to main's frozen copy and publish a series that forgets every earlier batch."""
    code = _code(name)
    assert code.index("generated_branch.py fetch") < code.index("--history")


def test_the_evidence_report_is_published_not_committed_by_the_refresh_bot():
    """#4963: the bot PR carries the records and the ledger (approval inputs), never the rendered report; #5057: nor
    the CICS spec status page (generated-docs.yml publishes it), which the job no longer renders at all."""
    code = _code("evidence-refresh.yml")
    add_paths = code.split("add-paths: |", 1)[1].split("- name:", 1)[0]
    assert "evidence_report" not in add_paths
    assert "cics_spec_status" not in code
    publish = code.split("publish-report:", 1)[1].split("\n  publish-blockers:", 1)[0]
    assert "generated_branch.py publish" in publish
    assert "docs/language_status/evidence_report" in publish
    assert "create-pull-request" not in publish and "gh pr merge" not in publish
    assert re.search(r"persist-credentials:\s*true", publish)
    assert 'EVIDENCE_REPORT_WRITE_INDEX: "1"' in code  # #5206: the index is written in the refresh job only


def test_the_estate_rollup_is_published_not_committed_and_never_blocks_the_report():
    """#4054: estate_evidence.py writes outside the repo (--out), the roll-up is published on its own path and stamp,
    and a failure of either step leaves the L0-L5 report's publish alone."""
    code = _code("evidence-refresh.yml")
    add_paths = code.split("add-paths: |", 1)[1].split("- name:", 1)[0]
    assert "estate_evidence" not in add_paths
    build = code.split("id: estate", 1)[1].split("- name:", 1)[0]
    assert "continue-on-error: true" in build
    assert 'estate_evidence.py --out "$RUNNER_TEMP/' in build
    publish = code.split("publish-report:", 1)[1].split("\n  publish-blockers:", 1)[0]
    assert "docs/language_status/estate_evidence" in publish
    assert "--stamp estate-evidence" in publish and "--stamp evidence-report" in publish
    assert "docs/language_status/evidence_report/estate" not in code


def test_the_ground_truth_pr_job_holds_no_write_token():
    """The job that runs PR code only reads; the publish to generated is a separate, main-only job."""
    code = _code("mainframe-ground-truth.yml")
    job = code.split("  ground-truth:", 1)[1].split("\n  publish-history:", 1)[0]
    assert "contents: write" not in job and "persist-credentials: true" not in job
    publish = code.split("publish-history:", 1)[1]
    assert "refs/heads/main" in publish and "pull_request" not in publish.split("steps:", 1)[0]


def test_the_generated_docs_render_job_holds_no_write_token_and_publish_runs_on_main_only():
    """#5057: the job that runs PR code only reads; the publish to generated is a separate, main-only job that
    publishes exactly the pages generated_docs.py renders."""
    import generated_docs

    code = _code("generated-docs.yml")
    render = code.split("\n  render:", 1)[1].split("\n  publish:", 1)[0]
    assert "contents: write" not in render and "persist-credentials: true" not in render
    assert "generated_docs.py check" in render
    publish = code.split("\n  publish:", 1)[1]
    head = publish.split("steps:", 1)[0]
    assert "refs/heads/main" in head and "github.event_name != 'pull_request'" in head
    assert set(MOVED["generated-docs.yml"]) == set(generated_docs.PAGES)


def test_the_architecture_brief_is_published_from_main_only_and_never_tracked():
    """#4963: the brief is read with `generated_branch.py show`; a committed copy would be a stale fallback (#5206)."""
    code = _code("gitgalaxy.yml")
    step = code.split("Publish the LLM Brief to the generated branch", 1)[1].split("- name:", 1)[0]
    assert "refs/heads/main" in step and "generated_branch.py publish" in step
    assert "security-events: write" in code  # the SARIF upload keeps its permission
    brief = "docs/gitgalaxy_architecture_brief.md"
    tracked = subprocess.run(["git", "ls-files", brief], cwd=REPO, capture_output=True, text=True, check=False)
    assert tracked.returncode == 0 and tracked.stdout.strip() == "", "the brief must not be committed to main"
    assert brief in (REPO / ".gitignore").read_text(encoding="utf-8").splitlines()


def test_no_rendered_evidence_report_page_is_tracked():
    """#4963/#5206: the report lives on generated; a committed page would be a stale fallback. Only the README stays."""
    tracked = subprocess.run(
        ["git", "ls-files", "docs/language_status/evidence_report"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert tracked.returncode == 0
    assert set(tracked.stdout.split()) <= {"docs/language_status/evidence_report/README.md"}


def test_the_harness_report_is_built_in_refresh_and_published_by_its_own_main_only_step():
    """#4493: harness_report.py runs where the corpora are (the refresh job, after the survey) and rides in the
    blockers-survey artifact; publish-blockers publishes it in its own step, on main only, and never via a bot PR."""
    code = _code("evidence-refresh.yml")
    add_paths = code.split("add-paths: |", 1)[1].split("- name:", 1)[0]
    assert "harness" not in add_paths
    build = code.split("id: harness", 1)[1].split("- name:", 1)[0]
    assert "continue-on-error: true" in build
    assert "steps.survey.outcome == 'success'" in build
    assert 'harness_report.py --survey "$GG_SCRATCH/census-cache/$SHA"' in build
    assert '--out "$RUNNER_TEMP/blockers-cache/harness"' in build
    job = code.split("\n  publish-blockers:", 1)[1]
    pub = job.split("Publish the harness report to the generated branch", 1)[1]
    step = pub.split("- name:", 1)[0]
    assert "generated_branch.py publish --stamp harness-report" in step
    assert "docs/language_status/harness" in step
    assert "refs/heads/main" in pub.split("run:", 1)[0]
    preview = job.split("Preview the harness report", 1)[1].split("- name:", 1)[0]
    assert "refs/heads/main" in preview.split("run:", 1)[0] and "generated-preview" in preview
    assert "create-pull-request" not in job and "gh pr merge" not in job


def test_the_wiki_names_the_path_the_harness_report_is_published_to():
    """#4493: the page a reader is pointed at is the directory the workflow publishes."""
    wiki = (WORKFLOWS.parents[1] / "docs/wiki/05-20-equivalence-harness.md").read_text(encoding="utf-8")
    assert "/tree/generated/docs/language_status/harness" in wiki
    assert "docs/language_status/harness" in _code("evidence-refresh.yml").split("--stamp harness-report", 1)[1]


def test_the_harness_report_path_is_git_ignored():
    ignored = (WORKFLOWS.parents[1] / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "docs/language_status/harness/" in ignored


# --- push_head (#6563) -------------------------------------------------------------------------------------------


def _generated_checkout(tmp_path, remote, name):
    c = tmp_path / name
    git(tmp_path, "clone", "-q", "-b", "generated", str(remote), str(c))
    git(c, "config", "user.email", "t@t")
    git(c, "config", "user.name", "t")
    return c


def _commit(c, rel, text):
    (c / rel).parent.mkdir(parents=True, exist_ok=True)
    (c / rel).write_text(text, newline="\n")
    git(c, "add", "-A")
    git(c, "commit", "-q", "-m", f"w {rel}")


def test_push_head_pushes_cleanly(remote_and_clone, tmp_path):
    remote, clone = remote_and_clone
    gb.publish(["docs/h.csv"], "m", root=clone)
    mine = _generated_checkout(tmp_path, remote, "mine")
    _commit(mine, "evidence/a.txt", "a\n")
    assert gb.push_head(mine) == git(remote, "rev-parse", "generated")


def test_push_head_rebases_over_a_concurrent_writer(remote_and_clone, tmp_path):
    remote, clone = remote_and_clone
    gb.publish(["docs/h.csv"], "m", root=clone)
    mine = _generated_checkout(tmp_path, remote, "mine")
    theirs = _generated_checkout(tmp_path, remote, "theirs")
    _commit(theirs, "other/b.txt", "b\n")
    git(theirs, "push", "-q", "origin", "HEAD:generated")
    _commit(mine, "evidence/a.txt", "a\n")  # built on the old tip: a plain push is rejected
    gb.push_head(mine)
    assert git(remote, "show", "generated:evidence/a.txt") == "a"
    assert git(remote, "show", "generated:other/b.txt") == "b"


def test_push_head_raises_and_leaves_no_rebase_on_a_conflict(remote_and_clone, tmp_path):
    remote, clone = remote_and_clone
    gb.publish(["docs/h.csv"], "m", root=clone)
    mine = _generated_checkout(tmp_path, remote, "mine")
    theirs = _generated_checkout(tmp_path, remote, "theirs")
    _commit(theirs, "GENERATED_FROM", "theirs\n")
    git(theirs, "push", "-q", "origin", "HEAD:generated")
    _commit(mine, "GENERATED_FROM", "mine\n")
    with pytest.raises(RuntimeError, match="conflicts"):
        gb.push_head(mine)
    assert not (mine / ".git" / "rebase-merge").exists()


def test_no_workflow_pushes_generated_with_a_bare_git_push():
    """A bare `git push origin HEAD:generated` is rejected whenever another writer pushed since the fetch (#6563)."""
    offenders = [
        p.name
        for p in sorted(WORKFLOWS.glob("*.yml"))
        if re.search(r"git push[^\n]*:(refs/heads/)?generated\b", _code(p.name))
    ]
    assert not offenders, f"use generated_branch.py publish / push-head: {offenders}"


def _publish_dirs_and_checkouts(name):
    """(job, directory the publish runs in, that directory's checkout step) for each publish step of a workflow."""
    code = _code(name)
    found = []
    for job in re.split(r"\n(?=  [\w-]+:\n)", code):
        steps = re.split(r"\n(?=      - )", job)
        checkouts = {}
        for step in steps:
            if "actions/checkout@" in step:
                m = re.search(r"^\s+path:\s*(\S+)", step, re.M)
                checkouts[m.group(1) if m else "."] = step
        for step in steps:
            if "generated_branch.py publish" in step:
                cd = re.search(r"^\s*(?:\(\s*)?cd\s+(\S+)", step, re.M)
                d = cd.group(1) if cd else "."
                found.append((job.split(":", 1)[0].strip(), d, checkouts.get(d)))
    return found


@pytest.mark.parametrize(
    "name",
    sorted(p.name for p in WORKFLOWS.glob("*.yml") if "generated_branch.py publish" in p.read_text(encoding="utf-8")),
)
def test_a_publish_step_pushes_from_a_checkout_that_kept_its_credentials(name):
    """#6555: publish-blockers ran the harness publish from a `persist-credentials: false` checkout; every push
    failed with 'could not read Username'. The checkout of the directory a publish runs in must persist them."""
    for job, d, step in _publish_dirs_and_checkouts(name):
        assert step is not None, f"{name}:{job} publishes from {d!r}, which no checkout step populates"
        assert re.search(r"persist-credentials:\s*true", step), f"{name}:{job} publishes from {d!r} without credentials"
