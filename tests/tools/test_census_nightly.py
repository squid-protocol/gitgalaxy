"""census_nightly (#6064): the box gate, once per SHA per day, nice / --jobs 2, and a counts-only publish. Git, the
survey and box_status are stubbed: no census clone, no network."""

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import census_nightly as cn

SHA = "b" * 40
LINE = {"pr": 0, "main_sha": SHA, "date": "2026-10-23T00:00:00Z", "whole": 5, "total": 9, "whole_burned": 3,
        "total_burned": 6, "whole_non_burned": 2, "total_non_burned": 3, "refused_whole": 1, "nightly": True,
        "top_gaps": [{"gap": "EXEC CICS GETMAIN", "only": 1, "only_burned": 0, "only_non_burned": 1,
                      "refuses_program": False}], "scope": "burned + local + census corpora"}  # fmt: skip


@pytest.fixture
def box(tmp_path, monkeypatch):
    """A run with every outside call stubbed; `box.calls` lists the subprocess argvs, `box.published` the commits."""
    st = SimpleNamespace(
        calls=[], published=[], verdict="GREEN", survey_rc=0, census=True, line=dict(LINE), series=None, fetches=0, on_main=True
    )
    monkeypatch.setattr(cn, "box_verdict", lambda: st.verdict)
    def resolve(sha=None, fetch=False):
        if sha is None:
            st.fetches += fetch
            return SHA
        if not SHA.startswith(sha):
            raise SystemExit(f"git rev-parse failed: {sha}")
        return SHA

    monkeypatch.setattr(cn.cics_census, "resolve_sha", resolve)
    monkeypatch.setattr(cn.cics_census, "_git", lambda *a: "https://example.invalid/repo.git")
    monkeypatch.setattr(cn.equivalence_env, "census_repos", lambda: ["owner/secret-census-repo"])
    monkeypatch.setattr(cn.generated_branch, "read_published", lambda rel, root=None: st.series)
    monkeypatch.setattr(cn.generated_branch, "publish",
                        lambda paths, msg, root=None, **kw: st.published.append((paths, msg, (root / paths[0]).read_text())) or "c0ffee")  # fmt: skip

    def append(path, d, pr, note, nightly=False):
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(st.line) + "\n")
        return 0

    monkeypatch.setattr(cn.cics_census, "append_history", append)

    def fake_run(argv, **kw):
        st.calls.append(argv)
        if "merge-base" in argv:
            return subprocess.CompletedProcess(argv, 0 if st.on_main else 1)
        if "survey" in argv:
            d = cn.cics_census.cache_dir(tmp_path, SHA)
            d.mkdir(parents=True, exist_ok=True)
            (d / "meta.json").write_text(json.dumps({"sha": SHA, "census": st.census}))
            return subprocess.CompletedProcess(argv, st.survey_rc)
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(cn.subprocess, "run", fake_run)
    st.args = ["--root", str(tmp_path)]
    return st


def surveys(st):
    return [c for c in st.calls if "survey" in c]


def test_green_box_surveys_with_census_nice_and_two_jobs_then_publishes_the_line_only(box, tmp_path, capsys):
    assert cn.main(box.args) == 0
    (argv,) = surveys(box)
    assert argv[:3] == ["nice", "-n", "10"] and argv[argv.index("--jobs") + 1] == "2"
    assert "--no-census" not in argv and "--baseline" in argv and "--no-fetch" in argv
    ((paths, msg, text),) = box.published
    assert paths == ["docs/language_status/blockers/census_history.jsonl"]
    assert json.loads(text)["total_non_burned"] == 3
    assert "counts only" in msg
    assert cn.stamp_file(tmp_path, SHA).is_file()


@pytest.mark.parametrize("verdict", ["YELLOW", "RED", "UNKNOWN"])
def test_a_box_that_is_not_green_skips_without_surveying(box, verdict, capsys):
    box.verdict = verdict
    assert cn.main(box.args) == 0
    assert not box.calls and not box.published
    assert "skipped" in capsys.readouterr().out


def test_same_sha_same_day_runs_once(box):
    assert cn.main(box.args) == 0
    n = len(box.calls)
    assert cn.main(box.args) == 0
    assert len(box.calls) == n and len(box.published) == 1


def test_a_sha_already_in_the_published_series_is_not_surveyed(box):
    box.series = (json.dumps(LINE) + "\n").encode()
    assert cn.main(box.args) == 0
    assert not surveys(box) and not box.published


def test_a_failed_survey_publishes_nothing_and_leaves_no_stamp(box, tmp_path):
    box.survey_rc = 3
    assert cn.main(box.args) == 3
    assert not box.published and not cn.stamp_file(tmp_path, SHA).exists()


def test_a_baseline_surveyed_without_the_census_is_not_published(box, tmp_path):
    box.census = False
    assert cn.main(box.args) == 1
    assert not box.published


def test_dry_run_publishes_and_stamps_nothing(box, tmp_path, capsys):
    assert cn.main([*box.args, "--dry-run"]) == 0
    assert not box.published and not cn.stamp_file(tmp_path, SHA).exists()
    assert "dry run" in capsys.readouterr().out


@pytest.mark.parametrize(
    "bad",
    [
        {"note": "read /srv/x/census/secret-census-repo/PGM.cbl"},  # a census path and repo name
        {"programs": ["PGM1"]},  # a key that is not a count
        {"copy_members": ["REC.cbl"]},  # copy members as names, not a count
        {"copy_members": True},  # not a count either
    ],
)
def test_a_line_that_is_not_counts_only_is_refused(box, bad):
    box.line = {**LINE, **bad}
    assert cn.main(box.args) == 1
    assert not box.published


def test_counts_only_checks_the_gap_keys_and_names():
    assert cn.counts_only(json.dumps(LINE), ["/srv/census"]) is None
    assert cn.counts_only(json.dumps({**LINE, "copy_members": 1}), []) is None  # the 2026-11-07 nightly refusal
    assert "gap keys" in cn.counts_only(json.dumps({**LINE, "top_gaps": [{"gap": "g", "program": "P"}]}), [])
    assert cn.counts_only(json.dumps({**LINE, "scope": "x /srv/census y"}), ["/srv/census"])


@pytest.mark.parametrize(
    ("series", "path"), [("census", "census_history.jsonl"), ("nightly", "blockers_history.jsonl")]
)
def test_history_show_generated_reads_the_chosen_series(monkeypatch, capsys, series, path):
    seen = []
    monkeypatch.setattr(cn.cics_census, "read_generated", lambda p: seen.append(p) or json.dumps(LINE) + "\n")
    assert cn.cics_census.main(["history", "show", "--generated", "--series", series]) == 0
    assert seen[0].endswith(path)
    assert "nightly" in capsys.readouterr().out


@pytest.mark.parametrize("given", [SHA, SHA[:12]])
def test_after_merge_surveys_that_sha_full_or_short_with_the_same_gates(box, tmp_path, given):
    assert cn.main([*box.args, "--after-merge", given]) == 0
    (argv,) = surveys(box)
    assert argv[argv.index("--sha") + 1] == SHA and "--no-fetch" in argv
    assert any("merge-base" in c for c in box.calls)
    ((_, _, text),) = box.published
    assert cn.counts_only(text.strip(), ["owner/secret-census-repo"]) is None
    assert cn.stamp_file(tmp_path, SHA).is_file()


def test_after_merge_refuses_an_unknown_sha_and_surveys_nothing(box, capsys):
    assert cn.main([*box.args, "--after-merge", "deadbeef"]) == 1
    assert not box.calls and not box.published
    assert "not a commit" in capsys.readouterr().err


def test_after_merge_refuses_a_sha_that_is_not_on_main(box, capsys):
    box.on_main = False
    assert cn.main([*box.args, "--after-merge", SHA]) == 1
    assert not surveys(box) and not box.published
    assert "not on origin/main" in capsys.readouterr().err


@pytest.mark.parametrize("verdict", ["YELLOW", "RED"])
def test_after_merge_still_needs_a_green_box_unless_forced(box, verdict):
    box.verdict = verdict
    assert cn.main([*box.args, "--after-merge", SHA]) == 0
    assert not box.calls
    assert cn.main([*box.args, "--after-merge", SHA, "--force"]) == 0
    assert len(surveys(box)) == 1


def test_after_merge_keeps_the_stamp_and_published_series_skips(box):
    assert cn.main([*box.args, "--after-merge", SHA]) == 0
    assert cn.main([*box.args, "--after-merge", SHA]) == 0  # stamped: the nightly would skip it too
    assert len(surveys(box)) == 1 and len(box.published) == 1
    assert cn.main(box.args) == 0 and len(surveys(box)) == 1


def test_after_merge_skips_a_sha_the_published_series_holds(box):
    box.series = (json.dumps(LINE) + "\n").encode()
    assert cn.main([*box.args, "--after-merge", SHA]) == 0
    assert not surveys(box) and not box.published


def test_after_merge_dry_run_publishes_and_stamps_nothing(box, tmp_path):
    assert cn.main([*box.args, "--after-merge", SHA, "--dry-run"]) == 0
    assert surveys(box) and not box.published and not cn.stamp_file(tmp_path, SHA).exists()


def test_the_default_run_fetches_main_and_never_checks_ancestry(box):
    assert cn.main(box.args) == 0
    assert box.fetches == 1 and not any("merge-base" in c for c in box.calls)
