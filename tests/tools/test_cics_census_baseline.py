"""cics_census (#4270): the baseline cache keyed by commit SHA (a no-op once cached), `blockers` / `compare` reading
it, `history append` / `show`, and `blockers --unmask` (a what-if). det_survey and git are stubbed: no corpus, no
translator, no network."""

import argparse
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cics_census as cc

SHA = "a" * 40
CUT = "ExprError: P{n}.cbl:7: source defect: source text past column 72 (`x{n}.'`) cuts a literal open: fixed-form COBOL reads columns 8-72 only"
HOLE = "line 4: EXEC EXEC CICS: EXEC CICS GETMAIN not modelled"


def fixed(*code: str) -> str:
    return "\n".join(f"{i * 100:06d} {c}" for i, c in enumerate(code, 1)) + "\n"


CICS = fixed("PROCEDURE DIVISION.", "    EXEC CICS RETURN END-EXEC.")


def _corpora(tmp_path: Path) -> Path:
    main = tmp_path / "main"
    for name, progs in (("cics-genapp", ("A", "B")), ("dsf", ("C", "P1", "P2"))):
        for p in progs:
            (main / name / f"{p}.cbl").parent.mkdir(parents=True, exist_ok=True)
            (main / name / f"{p}.cbl").write_text(CICS)
    return main


ROWS = {
    "b": {"cics-genapp": [{"program": "A.cbl", "statements": 3, "translated": 3, "holes": []},
                          {"program": "B.cbl", "statements": 3, "translated": 2, "holes": [HOLE]}]},
    "nb-local": {"dsf": [{"program": "C.cbl", "statements": 3, "translated": 3, "holes": []},
                         {"program": "P1.cbl", "error": CUT.format(n=1)},
                         {"program": "P2.cbl", "error": CUT.format(n=2)}]},
}  # fmt: skip


@pytest.fixture
def stubbed(tmp_path, monkeypatch):
    calls: list[tuple] = []

    def fake_run(out, label, runs, **kw):
        calls.append((label, [r[0] for r in runs], kw.get("extra")))
        for suffix, root, _names in runs:
            if label == "whatif":  # the unmasked re-translation: P1 whole, P2 a GETMAIN hole
                rows = {"dsf": [{"program": "P1.cbl", "statements": 5, "translated": 5, "holes": [], "unmasked": "x"},
                                {"program": "P2.cbl", "statements": 5, "translated": 4, "holes": [HOLE]}]}  # fmt: skip
            else:
                rows = ROWS[suffix]
            (out / f"{label}-{suffix}").mkdir(parents=True, exist_ok=True)
            (out / f"{label}-{suffix}" / "survey.json").write_text(json.dumps(rows))
        (out / f"{label}-runs.json").write_text(json.dumps({s: str(r) for s, r, _ in runs}))
        return 0

    monkeypatch.setattr(cc, "resolve_sha", lambda sha=None, fetch=False: sha or SHA)
    monkeypatch.setattr(cc, "snapshot", lambda sha, dest: dest.mkdir(parents=True, exist_ok=True) or dest)
    monkeypatch.setattr(cc, "run_det_survey", fake_run)
    monkeypatch.setattr(cc, "_git", lambda *a: "1791331200" if a[0] == "show" else "abc123def456")
    monkeypatch.delenv(cc.CENSUS_ENV, raising=False)
    return {"calls": calls, "root": tmp_path / "scratch", "main": _corpora(tmp_path)}


def _full_census(root: Path) -> Path:
    """A census root holding exactly equivalence_env.census_repos(), one program each (#6064)."""
    import equivalence_env

    for repo in equivalence_env.census_repos():
        d = root / repo.split("/")[-1]
        d.mkdir(parents=True)
        (d / "A.cbl").write_text(CICS)
    return root


def _base(st) -> list[str]:
    return ["--root", str(st["root"]), "--corpora", str(st["main"]), "--no-census"]


def test_the_baseline_is_surveyed_once_per_sha(stubbed, capsys):
    argv = ["survey", "--baseline", "--no-fetch", *_base(stubbed)]
    assert cc.main(argv) == 0
    d = stubbed["root"] / "census-cache" / SHA
    meta = json.loads((d / "meta.json").read_text())
    assert meta["sha"] == SHA and meta["census"] is False and set(meta["runs"]) == {"b", "nb-local"}
    assert json.loads((d / "cics_programs.json").read_text())  # blockers --baseline needs no corpora
    assert "translated whole: 2 / 5 (non-burned 1 / 3)" in (d / "blockers.txt").read_text()
    assert len(stubbed["calls"]) == 1
    capsys.readouterr()
    assert cc.main(argv) == 0  # cached: nothing surveyed
    assert len(stubbed["calls"]) == 1 and "nothing to do" in capsys.readouterr().out
    census = _full_census(stubbed["root"].parent / "census")
    with_census = ["survey", "--baseline", "--no-fetch", "--root", str(stubbed["root"]), "--corpora",
                   str(stubbed["main"]), "--census-corpora", str(census)]  # fmt: skip
    assert cc.main(with_census) == 2  # cached without the census: says so, never mixes
    assert "--force" in capsys.readouterr().err


def test_a_failed_survey_leaves_no_cache(stubbed, monkeypatch):
    monkeypatch.setattr(cc, "run_det_survey", lambda *a, **k: 1)
    assert cc.main(["survey", "--baseline", "--no-fetch", *_base(stubbed)]) == 1
    assert not (stubbed["root"] / "census-cache" / SHA / "meta.json").exists()
    with pytest.raises(SystemExit, match="survey --baseline"):
        cc.main(["blockers", "--baseline", "--root", str(stubbed["root"])])


def test_blockers_and_compare_read_the_baseline(stubbed, capsys, tmp_path):
    cc.main(["survey", "--baseline", "--no-fetch", *_base(stubbed)])
    capsys.readouterr()
    assert cc.main(["blockers", "--baseline", "--root", str(stubbed["root"]), "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert (doc["whole"], doc["programs"], doc["refused"]) == (2, 5, 2)
    after = tmp_path / "branch"
    (after / "after-b").mkdir(parents=True)
    (after / "after-b" / "survey.json").write_text(json.dumps({"cics-genapp": [
        {"program": "A.cbl", "statements": 3, "translated": 3, "holes": []},
        {"program": "B.cbl", "statements": 3, "translated": 3, "holes": []}]}))  # fmt: skip
    assert cc.main(["compare", str(after), "--before-baseline", "--verb", "RETURN", *_base(stubbed)]) == 0
    out = capsys.readouterr().out
    assert "translated whole: 2 -> 2" in out  # A and B (after), A and C (before) -- per the programs using RETURN
    with pytest.raises(SystemExit, match="needs a survey DIR or --baseline"):
        cc.main(["blockers", "--no-census"])


def test_history_append_and_show(stubbed, capsys, tmp_path):
    cc.main(["survey", "--baseline", "--no-fetch", *_base(stubbed)])
    hist = tmp_path / "h.jsonl"
    argv = [
        "history",
        "append",
        "--pr",
        "4600",
        "--note",
        "a test",
        "--root",
        str(stubbed["root"]),
        "--file",
        str(hist),
    ]
    assert cc.main(argv) == 0
    (entry,) = [json.loads(ln) for ln in hist.read_text().splitlines()]
    assert (entry["pr"], entry["main_sha"], entry["whole"], entry["total"]) == (4600, SHA, 2, 5)
    assert (entry["whole_burned"], entry["total_burned"], entry["whole_non_burned"], entry["total_non_burned"]) == (
        1, 2, 1, 3)  # fmt: skip
    assert entry["refused_whole"] == 2 and len(entry["top_gaps"]) <= 5 and entry["note"] == "a test"
    assert entry["date"].startswith("2026-10-07")
    assert cc.main(argv) == 2  # the same PR at the same SHA: not appended twice
    capsys.readouterr()
    assert cc.main(["history", "show", "--file", str(hist)]) == 0
    assert "#4600" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="--pr"):
        cc.main(["history", "append", "--file", str(hist)])


def test_publish_lays_the_baseline_and_a_nightly_line(stubbed, capsys, tmp_path):
    cc.main(["survey", "--baseline", "--no-fetch", *_base(stubbed)])
    gen = tmp_path / "generated"
    argv = ["publish", "--into", str(gen), "--root", str(stubbed["root"])]
    assert cc.main(argv) == 0
    out = gen / cc.GENERATED_DIR
    assert {p.name for p in out.iterdir()} == {*cc.GENERATED_FILES, "blockers_history.jsonl"}
    assert json.loads((out / "blockers.json").read_text())["whole"] == 2
    rows = cc.read_history(out / "blockers_history.jsonl")
    seeded = cc.read_history()  # the branch had none: seeded from main's per-slice series
    assert rows[: len(seeded)] == seeded
    assert [r["pr"] for r in rows[len(seeded) :]] == [0] and rows[-1]["nightly"] and rows[-1]["main_sha"] == SHA
    assert cc.main(argv) == 0  # a rerun at the same SHA: still one line
    assert len(cc.read_history(out / "blockers_history.jsonl")) == len(rows)
    capsys.readouterr()
    assert cc.main(["history", "show", "--file", str(out / "blockers_history.jsonl")]) == 0
    assert "nightly" in capsys.readouterr().out


def test_publish_refuses_a_census_baseline(stubbed, tmp_path):
    cc.main(["survey", "--baseline", "--no-fetch", *_base(stubbed)])
    mf = stubbed["root"] / "census-cache" / SHA / "meta.json"
    mf.write_text(json.dumps({**json.loads(mf.read_text()), "census": True}))
    with pytest.raises(SystemExit, match="census"):
        cc.main(["publish", "--into", str(tmp_path / "g"), "--root", str(stubbed["root"])])


def test_generated_readers_use_the_published_files(stubbed, capsys, monkeypatch, tmp_path):
    cc.main(["survey", "--baseline", "--no-fetch", *_base(stubbed)])
    gen = tmp_path / "g"
    cc.main(["publish", "--into", str(gen), "--root", str(stubbed["root"])])
    monkeypatch.setattr(
        cc.generated_branch, "read_published", lambda rel, root=None, remote="origin": (gen / rel).read_bytes()
    )
    capsys.readouterr()
    assert cc.main(["blockers", "--generated"]) == 0
    assert "translated whole: 2 / 5" in capsys.readouterr().out
    assert cc.main(["history", "show", "--generated"]) == 0
    assert "nightly" in capsys.readouterr().out


def test_the_committed_history_is_well_formed():
    rows = cc.read_history()
    assert [r["pr"] for r in rows][:3] == [4587, 4590, 4592]
    for r in rows:
        assert len(r["main_sha"]) == 40 and r["whole"] <= r["total"]
        assert r["whole_burned"] + r["whole_non_burned"] == r["whole"]
        assert r["total_burned"] + r["total_non_burned"] == r["total"]


def test_unmask_finds_the_check_behind_a_gap():
    assert cc.unmask_check(cc.error_key(CUT.format(n=1))) == "cut-literal"
    assert cc.unmask_check("missing copybook CMQGMOV") == "missing-copybook"
    assert cc.unmask_check("missing copybook X (ambiguous)") is None
    assert cc.unmask_check("refused: LayoutError: national / DBCS text (…) is not modelled") == "unmodelled"
    assert cc.unmask_check("refused: ExprError: the PROCEDURE DIVISION does not parse") is None
    rows = {"x": {("dsf", "P1.cbl"): ROWS["nb-local"]["dsf"][1], ("dsf", "Q.cbl"): {"program": "Q.cbl",
            "error": "CopyNotFound: /x/Q.cbl:3: COPY BAQRI"}}}  # fmt: skip
    keys, check = cc.unmask_targets(rows, "*source defect")
    assert check == "cut-literal" and len(keys) == 1 and "x1" not in keys[0]  # no source text in the key
    with pytest.raises(SystemExit, match="no whole-program refusal"):
        cc.unmask_targets(rows, "GETMAIN")
    rows["x"][("dsf", "R.cbl")] = {"program": "R.cbl", "error": "ExprError: line 9: paragraph_header does not parse"}
    with pytest.raises(SystemExit, match="no survey-mode switch"):
        cc.unmask_targets(rows, "paragraph_header")
    with pytest.raises(SystemExit, match="different checks"):
        cc.unmask_targets(rows, "refused")


def test_blockers_unmask_is_a_labelled_what_if(stubbed, capsys):
    cc.main(["survey", "--baseline", "--no-fetch", *_base(stubbed)])
    capsys.readouterr()
    assert (
        cc.main(["blockers", "--baseline", "--root", str(stubbed["root"]), "--unmask", "source text past column"]) == 0
    )
    out = capsys.readouterr().out
    assert out.startswith("# WHAT-IF, NOT A TRANSLATION")
    assert "refusal check `cut-literal` switched off in survey mode only" in out
    assert "programs it refuses whole: 2 (non-burned 2)" in out
    assert "would translate whole with it lifted: 1 (non-burned 1)" in out
    assert "EXEC CICS GETMAIN" in out  # the gap it hid
    label, suffixes, extra = stubbed["calls"][-1]
    assert label == "whatif" and suffixes == ["nb-local"]
    assert extra[:2] == ["--unmask", "cut-literal"] and "--estate-from" in extra
    assert extra.count("--program") == 2 and "P1.cbl" in extra and "A.cbl" not in extra  # only the refused ones
    d = stubbed["root"] / "census-cache" / SHA / "unmask"
    assert json.loads(next(d.glob("*/whatif.json")).read_text())["what_if"] is True


def test_no_census_ignores_the_census_env(tmp_path, monkeypatch, stubbed):
    """--no-census means no census at all: $CICS_CENSUS_CORPORA is not read (the nightly burned-only job)."""
    census = tmp_path / "census"
    (census / "cics-async-api-redbooks").mkdir(parents=True)
    (census / "cics-async-api-redbooks" / "A.cbl").write_text(CICS)
    monkeypatch.setenv(cc.CENSUS_ENV, str(census))
    assert cc.roots_from(argparse.Namespace(corpora=stubbed["main"], census_corpora=None,
                                                                    no_census=True)) == [stubbed["main"]]  # fmt: skip
    assert cc.main(["survey", "--out", str(tmp_path / "s"), "--no-census", "--corpora", str(stubbed["main"])]) == 0
    assert all(s != "nb" for s in stubbed["calls"][-1][1])  # no census run
    assert cc.main(["survey", "--baseline", "--no-fetch", *_base(stubbed)]) == 0
    assert all(s != "nb" for s in stubbed["calls"][-1][1])


def test_no_census_never_reads_the_census_root(tmp_path, monkeypatch, stubbed, capsys):
    """#4598: --no-census reads no census root whatever $CICS_CENSUS_CORPORA holds -- survey, usage and compare --
    and --no-census with --census-corpora is an error."""
    census = tmp_path / "census"
    (census / "cics-async-api-redbooks").mkdir(parents=True)
    (census / "cics-async-api-redbooks" / "A.cbl").write_text(CICS)
    monkeypatch.setenv(cc.CENSUS_ENV, str(census))
    main = ["--no-census", "--corpora", str(stubbed["main"])]
    assert cc.main(["usage", "RETURN", "--json", *main]) == 0
    assert {r["corpus"] for r in json.loads(capsys.readouterr().out)["programs"]} == {"cics-genapp", "dsf"}
    assert cc.main(["survey", "--out", str(tmp_path / "s"), *main]) == 0
    assert "nb" not in stubbed["calls"][-1][1]
    s = tmp_path / "s2"
    for label in ("before", "after"):
        (s / f"{label}-b").mkdir(parents=True)
        (s / f"{label}-b" / "survey.json").write_text(json.dumps(ROWS["b"]))
    assert cc.main(["compare", str(s), "--verb", "RETURN", "--json", *main]) == 0
    assert {r["corpus"] for r in json.loads(capsys.readouterr().out)["rows"]} == {"cics-genapp", "dsf"}
    with pytest.raises(SystemExit):
        cc.main(["usage", "RETURN", *main, "--census-corpora", str(census)])
    assert "contradict" in capsys.readouterr().err


def test_a_bad_census_root_is_refused_naming_the_corpora(stubbed, tmp_path, capsys):
    """#6064: `main` + `scratch` (the placeholder corpora of the broken 2026-10-14 baseline) is not the census."""
    import equivalence_env

    bad = tmp_path / "badcensus"
    for n in ("main", "scratch"):
        (bad / n).mkdir(parents=True)
        (bad / n / "A.cbl").write_text(CICS)
    argv = ["survey", "--baseline", "--no-fetch", "--root", str(stubbed["root"]), "--corpora", str(stubbed["main"]),
            "--census-corpora", str(bad)]  # fmt: skip
    with pytest.raises(SystemExit) as e:
        cc.main(argv)
    msg = str(e.value)
    assert "unexpected: main, scratch" in msg and equivalence_env.census_repos()[0] in msg
    assert not stubbed["calls"] and not (stubbed["root"] / "census-cache" / SHA / "meta.json").exists()
    with pytest.raises(SystemExit, match="unexpected: main, scratch"):
        cc.main(
            ["survey", "--out", str(tmp_path / "s"), "--corpora", str(stubbed["main"]), "--census-corpora", str(bad)]
        )
    (tmp_path / "s" / "before-b").mkdir(parents=True)
    (tmp_path / "s" / "before-b" / "survey.json").write_text(json.dumps({"c": [{"program": "A.cbl"}]}))
    with pytest.raises(SystemExit, match="unexpected: main, scratch"):
        cc.main(["blockers", str(tmp_path / "s"), "--corpora", str(stubbed["main"]), "--census-corpora", str(bad)])


def test_a_census_root_with_a_missing_or_empty_repo_is_refused(stubbed, tmp_path):
    import equivalence_env

    census = _full_census(tmp_path / "census")
    first, second = (r.split("/")[-1] for r in equivalence_env.census_repos()[:2])
    import shutil

    shutil.rmtree(census / first)
    (census / second / "A.cbl").unlink()
    with pytest.raises(SystemExit) as e:
        cc.check_census_root(census)
    assert f"missing: {equivalence_env.census_repos()[0]}" in str(e.value)
    assert f"no COBOL program: {equivalence_env.census_repos()[1]}" in str(e.value)


def test_a_full_census_root_passes(tmp_path):
    cc.check_census_root(_full_census(tmp_path / "census"))


def test_a_no_census_run_with_no_non_burned_says_not_surveyed(tmp_path, capsys):
    """#6064: blockers.txt's header and the history line say `not surveyed`, never `non-burned 0 / 0`."""
    res = {"scope": "s", "whole": 3, "programs": 3, "whole_non_burned": 0, "non_burned": 0, "refused": 0,
           "histogram": {}, "gaps": [], "census_surveyed": False}  # fmt: skip
    assert "non-burned: not surveyed" in cc.format_blockers(res, "w") and "non-burned 0" not in cc.format_blockers(
        res, "w"
    )
    assert "non-burned 0 / 0" in cc.format_blockers({**res, "census_surveyed": True}, "w")
    assert "non-burned 0 / 0" in cc.format_blockers({k: v for k, v in res.items() if k != "census_surveyed"}, "w")
    local = {**res, "non_burned": 2, "whole_non_burned": 1}  # local non-burned corpora were counted: show them
    assert "non-burned 1 / 2" in cc.format_blockers(local, "w")
    entry = cc.history_entry(res, SHA, "2026-10-22T00:00:00Z", 0, None, "burned")
    assert entry["whole_non_burned"] is None and entry["total_non_burned"] is None and entry["census_surveyed"] is False
    assert cc.history_entry(local, SHA, "d", 0, None, "burned")["total_non_burned"] == 2
    hist = tmp_path / "h.jsonl"
    hist.write_text(json.dumps(entry) + "\n")
    assert cc.main(["history", "show", "--file", str(hist)]) == 0
    assert "not surveyed" in capsys.readouterr().out


def test_a_bad_census_root_from_the_env_is_refused(stubbed, tmp_path, monkeypatch):
    """#6064: $CICS_CENSUS_CORPORA naming a placeholder root is refused the same as --census-corpora."""
    bad = tmp_path / "badcensus"
    (bad / "scratch").mkdir(parents=True)
    (bad / "scratch" / "A.cbl").write_text(CICS)
    monkeypatch.setenv(cc.CENSUS_ENV, str(bad))
    with pytest.raises(SystemExit, match="unexpected: scratch"):
        cc.main(["survey", "--out", str(tmp_path / "s"), "--corpora", str(stubbed["main"])])
    assert not stubbed["calls"]
