"""#8077: `--blind-root` on cics_census survey, census_nightly --after-merge and gap_prevalence. Fixture estates only:
the blind estate itself is never read by a test."""

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cics_census as cc
import census_nightly as cn
import gap_prevalence as gp

SHA = "c" * 40
ESTATE = "fixture-estate-zz"


def make_root(tmp_path, names=(ESTATE,), program=True):
    root = tmp_path / "blind"
    for n in names:
        d = root / n
        d.mkdir(parents=True)
        if program:
            (d / "PROG1.cbl").write_text("       IDENTIFICATION DIVISION.\n", encoding="utf-8")
    return root


def test_a_fixture_blind_root_is_accepted(tmp_path):
    assert cc.blind_root(make_root(tmp_path)) == tmp_path / "blind"


@pytest.mark.parametrize("kind", ["missing", "empty", "no_program", "burned", "census"])
def test_a_root_that_is_not_a_blind_estate_is_refused_by_count_not_name(tmp_path, kind):
    named = {"burned": sorted(cc.burned_names())[0], "census": sorted(cc.census_names())[0]}.get(kind)
    root = {
        "missing": tmp_path / "nope",
        "empty": make_root(tmp_path, names=()),
        "no_program": make_root(tmp_path, program=False),
    }.get(kind) or make_root(tmp_path, names=(named,))
    if kind == "empty":
        root.mkdir(exist_ok=True)
    with pytest.raises(SystemExit) as e:
        cc.blind_root(root)
    msg = str(e.value)
    assert "--blind-root" in msg and (named is None or named not in msg)


def test_blind_runs_is_the_one_blind_run_and_honours_corpus(tmp_path):
    root = make_root(tmp_path)
    assert cc.blind_runs(root) == [("blind", root, [ESTATE])]
    assert cc.blind_runs(root, ["other"]) == []


@pytest.mark.parametrize(
    "extra", [["--census-corpora", "/x"], ["--no-census"], ["--crucible", "/x"], ["--corpora", "/x"]]
)
def test_blind_root_contradicts_the_other_roots(tmp_path, extra):
    with pytest.raises(SystemExit) as e:
        cc.main(["survey", "--baseline", "--blind-root", str(make_root(tmp_path)), *extra])
    assert e.value.code == 2


def test_plain_survey_runs_only_the_blind_run(tmp_path, monkeypatch):
    root, seen = make_root(tmp_path), []
    monkeypatch.setattr(cc, "run_det_survey", lambda out, label, runs, **kw: seen.append((out, label, runs)) or 0)
    out = tmp_path / "out"
    assert cc.main(["survey", "--out", str(out), "--blind-root", str(root)]) == 0
    assert seen == [(out, "before", [("blind", root, [ESTATE])])]
    with pytest.raises(SystemExit):
        cc.main(["survey", "--out", str(out), "--blind-root", str(root), "--verb", "ASSIGN"])


def test_baseline_blind_uses_its_own_cache_and_meta(tmp_path, monkeypatch):
    root = make_root(tmp_path)
    monkeypatch.setattr(cc, "resolve_sha", lambda sha, fetch=False: SHA)
    monkeypatch.setattr(cc, "snapshot", lambda sha, dest: dest.mkdir(parents=True) or dest)
    monkeypatch.setattr(cc, "run_det_survey", lambda out, label, runs, **kw: 0)
    monkeypatch.setattr(cc, "cics_programs", lambda roots, extra=None: set())
    monkeypatch.setattr(cc, "baseline_blockers", lambda d, census=None, **kw: {"programs": 0})
    args = ["survey", "--baseline", "--no-fetch", "--root", str(tmp_path), "--blind-root", str(root)]
    assert cc.main(args) == 0
    meta = json.loads((cc.cache_dir(tmp_path, SHA, blind=True) / "meta.json").read_text())
    assert meta["blind"] is True and meta["census"] is False
    assert not cc.cache_dir(tmp_path, SHA).exists()
    assert ESTATE not in json.dumps(meta) and str(root) not in json.dumps(meta)


# ---- census_nightly --after-merge --blind-root -----------------------------------------------------------------
LINE = {"pr": 0, "main_sha": SHA, "date": "2026-11-08T00:00:00Z", "whole": 14, "total": 58, "whole_burned": 0,
        "total_burned": 0, "whole_non_burned": 14, "total_non_burned": 58, "refused_whole": 3, "nightly": True,
        "top_gaps": [], "scope": "blind estate (counts only)"}  # fmt: skip


@pytest.fixture
def box(tmp_path, monkeypatch):
    st = SimpleNamespace(calls=[], published=[], blind=True, line=dict(LINE))
    monkeypatch.setattr(cn, "box_verdict", lambda: "GREEN")
    monkeypatch.setattr(cn.cics_census, "resolve_sha", lambda sha=None, fetch=False: SHA)
    monkeypatch.setattr(cn.cics_census, "_git", lambda *a: "https://example.invalid/repo.git")
    monkeypatch.setattr(cn.equivalence_env, "census_repos", lambda: ["owner/secret-census-repo"])
    monkeypatch.setattr(cn.generated_branch, "read_published", lambda rel, root=None: None)
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
            return subprocess.CompletedProcess(argv, 0)
        if "survey" in argv:
            d = cn.cics_census.cache_dir(tmp_path, SHA, blind="--blind-root" in argv)
            d.mkdir(parents=True, exist_ok=True)
            (d / "meta.json").write_text(json.dumps({"sha": SHA, "blind": st.blind}))
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(cn.subprocess, "run", fake_run)
    st.root = make_root(tmp_path)
    st.args = ["--root", str(tmp_path), "--after-merge", SHA, "--blind-root", str(st.root)]
    return st


def test_after_merge_blind_surveys_the_blind_root_and_publishes_to_the_blind_series(box, tmp_path):
    assert cn.main(box.args) == 0
    (argv,) = [c for c in box.calls if "survey" in c]
    assert argv[argv.index("--blind-root") + 1] == str(box.root) and "--baseline" in argv
    assert not any("--provision" in c for c in box.calls)  # the blind estate is never provisioned
    ((paths, msg, text),) = box.published
    assert paths == [cc.GENERATED_BLIND_HISTORY] and ESTATE not in msg
    assert cn.counts_only(text.strip(), [ESTATE]) is None
    assert cn.stamp_file(tmp_path, SHA, blind=True).is_file() and not cn.stamp_file(tmp_path, SHA).exists()


def test_blind_root_needs_after_merge(box, capsys):
    assert cn.main(["--root", box.args[1], "--blind-root", str(box.root)]) == 2
    assert "--after-merge" in capsys.readouterr().err and not box.calls


def test_a_blind_baseline_without_the_blind_flag_publishes_nothing(box):
    box.blind = False
    assert cn.main(box.args) == 1 and not box.published


def test_a_blind_line_that_names_the_estate_is_refused(box):
    box.line["scope"] = f"blind {ESTATE}"
    assert cn.main(box.args) == 1 and not box.published


def test_the_census_stamp_does_not_stop_a_blind_run(box, tmp_path):
    cn.stamp_file(tmp_path, SHA).parent.mkdir(parents=True)
    cn.stamp_file(tmp_path, SHA).write_text("x")
    assert cn.main(box.args) == 0 and box.published


def test_history_show_generated_reads_the_blind_series(monkeypatch, capsys):
    seen = []
    monkeypatch.setattr(cc, "read_generated", lambda p: seen.append(p) or json.dumps(LINE) + "\n")
    assert cc.main(["history", "show", "--generated", "--series", "blind"]) == 0
    assert seen == [cc.GENERATED_BLIND_HISTORY]


# ---- gap_prevalence --census-survey --blind-root ------------------------------------------------------------------
def test_gap_prevalence_blind_prints_counts_and_writes_nothing(tmp_path, monkeypatch, capsys):
    root = make_root(tmp_path)
    surv = tmp_path / "surv"
    (surv / "before-blind").mkdir(parents=True)
    rows = [{"program": f"P{i}", "statements": 3, "translated": 3, "holes": []} for i in range(2)]
    rows.append({"program": "P2", "error": "refused: UnitRefused: no PROGRAM-ID"})
    (surv / "before-blind" / "survey.json").write_text(json.dumps({ESTATE: rows}))
    monkeypatch.setattr(gp, "census_eras", lambda corpora, names: {})
    monkeypatch.setattr(gp, "PAGE", tmp_path / "pg.txt")
    monkeypatch.setattr(gp, "SUMMARY", tmp_path / "s.json")
    monkeypatch.setattr(gp, "CENSUS_SUMMARY", tmp_path / "c.json")
    assert gp.main(["--census-survey", str(surv), "--blind-root", str(root)]) == 0
    out = capsys.readouterr().out
    assert "3 programs, 2 translate whole" in out and ESTATE not in out and "P2" not in out
    assert not list(tmp_path.glob("*.json")) and not (tmp_path / "pg.txt").exists()
    for bad in (["--write"], []):
        with pytest.raises(SystemExit):
            gp.main([*(["--census-survey", str(surv)] if bad else []), "--blind-root", str(root), *bad])


def test_silenced_hides_fd_level_output_and_restores_it(capfd):
    import os

    with gp._silenced():
        os.write(1, b"estate-name\n")
        os.write(2, b"estate-name\n")
    os.write(1, b"after\n")
    out, err = capfd.readouterr()
    assert out == "after\n" and err == ""
