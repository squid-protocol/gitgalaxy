"""#2720: the outcome-label pilot tool (tests/tools/outcome_pilot.py) -- labeler, history join, analysis."""

import random
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import outcome_pilot as op


@pytest.mark.parametrize(
    "subject",
    [
        "fix null deref in parser",
        "Fixes #1234: crash on empty input",
        "fix(http): handle 304",
        "bugfix: off by one",
        "Bug: 1234 wrong header",
        "memory leak in the pool",
        "leaks a file descriptor on error",
        'Revert "add cache"',
        "CVE-2023-1234: bounds check",
        "regression in 7.2 resolver",
        "Fixed a typo in the loop",
        "Crashes when the list is empty",
    ],
)
def test_fix_subjects_are_labelled(subject):
    assert op.is_fix_subject(subject)


@pytest.mark.parametrize(
    "subject",
    [
        "",
        "add test fixtures for http",
        "prefix the symbols with gg_",
        "bugzilla import script",
        "Merge pull request #12 from x/fix-thing",
        "Merge branch 'fix-it'",
        "Bump the fix-version to 3",
        "docs: describe the fix workflow",
        "add feature flags",
        "refactor the leakage model",
        "the CVE database loader",
    ],
)
def test_non_fix_subjects_are_not(subject):
    assert not op.is_fix_subject(subject)


def _git(repo, *args, date="2024-01-01T00:00:00"):
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
        "GIT_AUTHOR_DATE": date,
        "GIT_COMMITTER_DATE": date,
        "PATH": "/usr/bin:/bin:/usr/local/bin",
        "HOME": str(repo),
    }
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)


def _commit(repo, message, date, files):
    for name, text in files.items():
        p = repo / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    _git(repo, "add", "-A", date=date)
    _git(repo, "commit", "-m", message, date=date)


@pytest.fixture
def history(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    body = "".join(f"line {i}\n" for i in range(40))
    _commit(repo, "initial", "2024-01-01T00:00:00", {"a.c": body, "b.c": body + "b\n", "gone.c": body + "g\n"})
    _commit(repo, "fix before the pin", "2024-01-02T00:00:00", {"a.c": body + "x\n"})
    pin = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    _commit(repo, "fix crash in a", "2024-02-01T00:00:00", {"a.c": body + "y\n"})
    (repo / "src").mkdir()
    _git(repo, "mv", "a.c", "src/a.c", date="2024-02-02T00:00:00")
    _git(repo, "commit", "-m", "move a", date="2024-02-02T00:00:00")
    _commit(repo, "fix leak in a", "2024-03-01T00:00:00", {"src/a.c": body + "z\n"})
    _commit(repo, "add feature to b", "2024-03-02T00:00:00", {"b.c": body + "feature\n"})
    _git(repo, "rm", "gone.c", date="2024-03-03T00:00:00")
    _git(repo, "commit", "-m", "fix: drop gone", date="2024-03-03T00:00:00")
    _commit(repo, "fix far future bug in b", "2027-01-01T00:00:00", {"b.c": body + "late\n"})
    return repo, pin


def test_later_fixes_follow_renames_and_ignore_the_past_and_the_far_future(history):
    repo, pin = history
    commits = op.history_after_pin(repo, pin, 730)
    fixes, touches, final = op.later_fix_counts(commits, ["a.c", "b.c", "gone.c"])
    assert fixes == {"a.c": 2, "gone.c": 1}  # the rename keeps a.c's count; the pin-time fix is not later
    assert touches["a.c"] == 3 and touches["b.c"] == 1
    assert "b.c" not in fixes  # the 2027 fix is outside the window
    assert final["a.c"] == "src/a.c" and final["gone.c"] == ""


def test_a_wide_window_counts_the_late_fix(history):
    repo, pin = history
    fixes, _t, _f = op.later_fix_counts(op.history_after_pin(repo, pin, 5000), ["a.c", "b.c"])
    assert fixes["b.c"] == 1


def test_a_re_added_name_is_not_credited_to_the_deleted_file():
    commits = [
        ("c3", "fix crash", [("M", "x.c", None)]),
        ("c2", "add x again", [("A", "x.c", None)]),
        ("c1", "remove x", [("D", "x.c", None)]),
    ]
    fixes, _t, final = op.later_fix_counts(commits, ["x.c"])
    assert fixes == {} and final["x.c"] == ""


def test_parse_log_reads_renames():
    text = "\x01aaa\x02fix thing\nR100\told.c\tnew.c\nM\tb.c\n\x01bbb\x02other\nA\tc.c\n"
    commits = op.parse_log(text)
    assert commits[0] == ("aaa", "fix thing", [("R", "new.c", "old.c"), ("M", "b.c", None)])
    assert commits[1][2] == [("A", "c.c", None)]


def _synthetic(effect, seed=1, n=600):
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        dyn = 1 if rng.random() < 0.3 else 0
        loc = rng.choice([50, 200, 800])
        base = loc / 400.0
        lam = base * (effect if dyn else 1.0)
        fixes = sum(1 for _ in range(8) if rng.random() < lam / 8.0)
        rows.append({"repo": "r", "gaps": 2, "loc": loc, "evidence": loc // 10, "dynamism": dyn, "fixes": fixes})
    return rows


def test_a_planted_dynamism_effect_is_recovered_and_the_null_is_not_invented():
    planted = op.analyze_rows(_synthetic(2.5), rounds=60)["dynamism_any_vs_none"]
    assert 1.7 < planted["mh_rate_ratio"] < 3.6
    assert planted["ci95"][0] > 1.0
    null = op.analyze_rows(_synthetic(1.0, seed=2), rounds=60)["dynamism_any_vs_none"]
    assert 0.7 < null["mh_rate_ratio"] < 1.4
    assert null["ci95"][0] < 1.0 < null["ci95"][1]


def test_strictness_is_contrasted_only_inside_repos_that_hold_several_rows():
    rows = _synthetic(1.0, n=200)
    for i, r in enumerate(rows):
        r["gaps"] = 0 if i % 2 else 3
    mixed = op.analyze_rows(rows, rounds=30)
    assert mixed["strictness_polyglot_repos"] == ["r"]
    assert mixed["strictness_gaps_ge3_vs_le1"]["mh_rate_ratio"] is not None
    solo = op.analyze_rows(_synthetic(1.0, n=100), rounds=30)  # one row everywhere: no contrast to draw
    assert solo["strictness_polyglot_repos"] == []
    assert solo["strictness_gaps_ge3_vs_le1"]["mh_rate_ratio"] is None


def test_strata_hold_evidence_equal():
    rows = [
        {"repo": "r", "gaps": 1, "loc": 10 * (i + 1), "evidence": (i * 7) % 30, "dynamism": 0, "fixes": 0}
        for i in range(30)
    ]
    op.assign_strata(rows)
    assert len({r["stratum"] for r in rows}) > 4
    assert {r["stratum"][0] for r in rows} == {"r"}


def test_strictness_gaps_follow_the_registry_and_skip_unrowed_languages():
    assert op.strictness_gaps("rust") == 0
    assert op.strictness_gaps("python") == 2
    assert op.strictness_gaps("embedded_python") == op.strictness_gaps("python")
    assert op.strictness_gaps("markdown") is None
    assert op.strictness_gaps("no_such_language") is None


def test_the_pilot_list_is_the_ten_repos_plus_the_burned_mainframe_estates():
    assert len(op.PILOT_REPOS) == 17
    burned = [n for n, e in op.PILOT_REPOS.items() if e["burned"]]
    assert burned == [
        "carddemo",
        "cbsa",
        "cbsa-late",
        "genapp",
        "zecs",
        "dbb-mortgage",
        "dbb-mortgage-2019",
        "async-credit-card",
    ]


def test_every_burned_entry_names_a_burned_upstream():
    estate4_draw = pytest.importorskip("estate4_draw")
    burned_urls = {
        "aws-mainframe-modernization-carddemo",
        "cics-banking-sample-application-cbsa",
        "cics-genapp",
        "zecs",
        "dbb",
        "cics-async-api-credit-card-application-example",
    }
    assert burned_urls <= estate4_draw.BURNED_NAMES | {"dbb"}
    for name, entry in op.PILOT_REPOS.items():
        if entry["burned"]:
            tail = entry["url"].rstrip("/").split("/")[-1].lower()
            assert tail in burned_urls, name
            # mid-history pin (None) or an explicit commit; there is no PROVENANCE copy for these
            assert entry["pin"] is None or name in ("dbb-mortgage", "dbb-mortgage-2019", "zecs", "cbsa-late")


def test_the_dbb_entry_is_limited_to_the_mortgage_application_subtree():
    assert op._subdir_args(op.PILOT_REPOS["dbb-mortgage"]) == ["zBuilder/MortgageApplication"]
    assert op._subdir_args(op.PILOT_REPOS["cbsa"]) == []


def test_history_limited_to_a_subdir_ignores_other_paths(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    body = "".join(f"line {i}\n" for i in range(40))
    _commit(repo, "initial", "2024-01-01T00:00:00", {"app/p.cbl": body, "tools/t.py": body, "app/c.cpy": body})
    pin = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    _commit(repo, "fix crash in tool", "2024-02-01T00:00:00", {"tools/t.py": body + "x\n"})
    _commit(repo, "fix bug in program", "2024-02-02T00:00:00", {"app/p.cbl": body + "y\n"})
    _commit(repo, "add copybook field", "2024-02-03T00:00:00", {"app/c.cpy": body + "z\n"})
    commits = op.history_after_pin(repo, pin, 365, "app")
    fixes, touches, _ = op.later_fix_counts(commits, ["app/p.cbl", "app/c.cpy", "tools/t.py"])
    assert fixes == {"app/p.cbl": 1}
    assert touches == {"app/p.cbl": 1, "app/c.cpy": 1}
    everything = op.history_after_pin(repo, pin, 365)
    assert op.later_fix_counts(everything, ["tools/t.py"])[0] == {"tools/t.py": 1}


def test_mainframe_file_kinds_have_a_strictness_row_or_are_skipped():
    for lang in ("cobol", "jcl"):
        gaps = op.strictness_gaps(lang)
        assert gaps is None or isinstance(gaps, int)
    assert op.strictness_gaps("no_such_language") is None


def test_the_2019_dbb_entry_shares_the_clone_and_pins_the_old_layout(tmp_path):
    old, new = op.PILOT_REPOS["dbb-mortgage-2019"], op.PILOT_REPOS["dbb-mortgage"]
    assert old["url"] == new["url"] and old["burned"]
    assert op._subdir_args(old) == ["Build/MortgageApplication"]
    assert old["pin"] and old["pin"] != new["pin"]
    assert op._repo_dir(tmp_path, "dbb-mortgage-2019") == op._repo_dir(tmp_path, "dbb-mortgage")
    assert op._repo_dir(tmp_path, "cbsa") == tmp_path / "clones" / "cbsa"


def test_a_stripped_subdir_entry_scans_at_the_root_and_joins_history_under_the_prefix():
    entry = op.PILOT_REPOS["dbb-mortgage-2019"]
    assert op._strip_args(entry) == ["--strip-components=2"]
    assert op._history_path(entry, "cobol/epscmort.cbl") == "Build/MortgageApplication/cobol/epscmort.cbl"
    plain = op.PILOT_REPOS["dbb-mortgage"]
    assert op._strip_args(plain) == []
    assert op._history_path(plain, "zBuilder/MortgageApplication/x.cbl") == "zBuilder/MortgageApplication/x.cbl"


def test_the_late_cbsa_entry_shares_the_clone_and_pins_after_the_midpoint(tmp_path):
    late, mid = op.PILOT_REPOS["cbsa-late"], op.PILOT_REPOS["cbsa"]
    assert late["url"] == mid["url"] and late["burned"] and mid["pin"] is None
    assert late["pin"] and op._subdir_args(late) == [] and op._strip_args(late) == []
    assert op._repo_dir(tmp_path, "cbsa-late") == op._repo_dir(tmp_path, "cbsa")


def test_bulk_guard_credits_no_file_for_a_wide_commit_but_still_follows_its_renames():
    commits = [
        ("c3", "fix crash in a", [("M", "b.c", None)]),
        (
            "c2",
            "COBOL updates and fixes",
            [("M", "a.c", None), ("M", "b.c", None), ("R", "c2.c", "c.c"), ("M", "d.c", None)],
        ),
        ("c1", "add a", [("M", "a.c", None)]),
    ]
    paths = ["a.c", "b.c", "c.c", "d.c"]
    fixes, touches, final = op.later_fix_counts(commits, paths)
    assert fixes == {"a.c": 1, "b.c": 2, "c.c": 1, "d.c": 1} and touches["a.c"] == 2
    fixes, touches, final = op.later_fix_counts(commits, paths, max_files=4)  # boundary: 4 files is not bulk
    assert fixes["a.c"] == 1
    fixes, touches, final = op.later_fix_counts(commits, paths, max_files=3)
    assert fixes == {"b.c": 1} and touches == {"a.c": 1, "b.c": 1}
    assert final["c.c"] == "c2.c"  # the alias moved even though the commit was not credited


@pytest.mark.parametrize(
    "body",
    ["Fixes #123", "details\n\nFixed octo/repo#4", "Fixes: abc123def", "see CVE-2024-12345 for impact"],
)
def test_body_labels_catch_linked_fixes(body):
    assert op.is_fix_body(body)


@pytest.mark.parametrize(
    "body",
    [
        "",
        "Closes #12",
        "Resolves #3",
        "adds a fixture for the prefix",
        "relates to #12",
        "the fixes were reverted later",
    ],
)
def test_body_labels_ignore_loose_mentions(body):
    assert not op.is_fix_body(body)


def test_recall_counts_split_subject_from_body_only():
    commits = [
        ("a", "fix crash", "Fixes #1"),
        ("b", "dnscache: check hostname on lookup", "Fixes #2"),
        ("c", "add feature", ""),
    ]
    assert op.recall_counts(commits) == {"commits": 3, "subject_fix": 1, "body_only_fix": 1, "either": 2}


def test_commit_bodies_reads_the_window(history):
    repo, pin = history
    got = op.commit_bodies(repo, pin, 730)
    assert [s for _h, s, _b in got][:1] == ["fix: drop gone"] and len(got) == 5
