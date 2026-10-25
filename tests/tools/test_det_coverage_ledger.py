"""det_coverage_ledger: the sweep's coverage line -> ledger numbers, and the ratchet CI applies (missing / disagreeing /
stale entries). Fingerprints are stubbed; no sweep, git or corpus needed."""

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cobol_coverage as cov
import det_coverage_ledger as dcl

TOOLS = Path(__file__).resolve().parent

LINE = "proven on 8 scenarios, covering 4/4 paragraphs and 2/2 branches"
FP = {"case": "a", "corpus": "b", "harness": "c", "oracle": "d"}
CASE = "cbsa-abndproc"  # a case that exists in the tree


def entry(**over):
    return {"scenarios": 8, "paragraphs": {"covered": 4, "live": 4}, "branches": {"covered": 2, "total": 2},
            "inputs": dict(FP), **over}  # fmt: skip


def test_parse_line():
    assert dcl.parse_line(LINE) == {"scenarios": 8, "paragraphs": {"covered": 4, "live": 4},
                                    "branches": {"covered": 2, "total": 2}}  # fmt: skip
    assert dcl.parse_line("not proven") is None
    assert dcl.parse_line("") is None


# #5008: the harness that proves each case kind, and so prints its coverage line (each counts its own unit).
KIND_HARNESS = {"batch": "equivalence.py", "call": "equivalence_call.py", "cics": "equivalence_cics.py"}
_HEADLINE = re.compile(r"cov\.headline\(([^\n]*)\)\}")


def _harness_units(harness: str) -> list[str]:
    """The unit word(s) a harness's printed coverage line uses: cov.headline's `what` (default "run")."""
    calls = _HEADLINE.findall((TOOLS / harness).read_text(encoding="utf-8"))
    assert calls, f"{harness} prints no COBOL coverage line through cov.headline"
    return [m.group(1) if (m := re.search(r"'(\w+)'\s*$", c)) else "run" for c in calls]


def test_every_case_kind_has_a_harness():
    kinds = {json.loads(f.read_text(encoding="utf-8")).get("kind", "batch") for f in dcl.CASES.glob("*/case.json")}
    assert kinds <= set(KIND_HARNESS), f"a case kind with no harness here: {sorted(kinds - set(KIND_HARNESS))}"


@pytest.mark.parametrize("kind", sorted(KIND_HARNESS))
@pytest.mark.parametrize("n", [1, 3])
def test_a_proven_case_of_every_kind_gets_a_ledger_entry(monkeypatch, kind, n):
    """#5008: a passing det proof's coverage line, as its kind's harness prints it, yields a ledger entry (the ledger
    once read only "scenarios", so no batch ("runs") or CALL ("calls") case ever got one) and passes the check."""
    monkeypatch.setattr(dcl, "fingerprints", lambda case: dict(FP))
    s = {"paragraphs": {"covered": 4, "live": 5}, "branches": {"covered": 2, "total": 6}}
    for unit in _harness_units(KIND_HARNESS[kind]):
        line = cov.headline(s, n, True, unit)
        built = dcl.build({CASE: {"proved": True, "coverage": line}}, {})
        assert CASE in built, f"{kind}: {line!r} gave no ledger entry"
        assert dcl.fresh_coverage(CASE, built) == (4, 5, 2, 6) and built[CASE]["scenarios"] == n
        assert dcl.check({CASE: {"proved": True, "coverage": line}}, built) == ([], [])


def test_check_fails_on_a_coverage_line_it_cannot_read(monkeypatch):
    """#5008: an unknown wording used to be a warning only, so the cases it hid never reached the ledger."""
    monkeypatch.setattr(dcl, "fingerprints", lambda case: dict(FP))
    problems, _ = dcl.check({CASE: {"proved": True, "coverage": "proven on 2 widgets, covering 1/1 paragraphs"}}, {})
    assert "not understood" in problems[0]
    assert dcl.check({CASE: {"proved": True, "coverage": ""}}, {})[0] == []  # no line at all: reported, not failed


def test_check(monkeypatch):
    monkeypatch.setattr(dcl, "fingerprints", lambda case: dict(FP))
    det = {CASE: {"proved": True, "coverage": LINE}}
    assert dcl.check(det, {CASE: entry()}) == ([], [])
    problems, _ = dcl.check(det, {})
    assert "no entry" in problems[0]
    problems, _ = dcl.check(det, {CASE: entry(branches={"covered": 1, "total": 2})})
    assert "coverage moved" in problems[0]
    problems, _ = dcl.check(det, {CASE: entry(inputs={**FP, "case": "x"})})
    assert "stale (case changed)" in problems[0]
    problems, warnings = dcl.check(det, {CASE: entry(inputs={**FP, "harness": "x"})})
    assert not problems and "harness" in warnings[0]
    problems, _ = dcl.check(det, {CASE: entry(), "no-such-case": entry()})
    assert "no such case" in problems[0]
    assert dcl.check({CASE: {"proved": False, "coverage": ""}}, {}) == ([], [])


def test_build_and_fresh(monkeypatch):
    monkeypatch.setattr(dcl, "fingerprints", lambda case: dict(FP))
    det = {CASE: {"proved": True, "coverage": LINE}, "cbsa-updcust": {"proved": False, "coverage": LINE}}
    built = dcl.build(det, {})
    assert set(built) == {CASE} and built[CASE]["inputs"] == FP
    assert dcl.fresh_coverage(CASE, built) == (4, 4, 2, 2)
    monkeypatch.setattr(dcl, "fingerprints", lambda case: {**FP, "oracle": "z"})
    assert dcl.fresh_coverage(CASE, built) is None


def test_update_rewrites_stale_fingerprints(monkeypatch):
    """A harness-stale entry whose numbers the sweep reproduces is refreshed (#4270): update never keeps old fingerprints."""
    monkeypatch.setattr(dcl, "fingerprints", lambda case: {**FP, "harness": "new"})
    old = {CASE: entry(inputs={**FP, "harness": "old"})}
    assert dcl.stale(old[CASE], dcl.fingerprints(CASE)) == ["harness"]
    built = dcl.build({CASE: {"proved": True, "coverage": LINE}}, old)
    assert built[CASE]["inputs"]["harness"] == "new" and dcl.stale(built[CASE], dcl.fingerprints(CASE)) == []
    assert dcl.fresh_coverage(CASE, built) == (4, 4, 2, 2)


def test_update_drops_a_case_the_sweep_did_not_prove_and_keeps_one_it_did_not_run(monkeypatch):
    """#4758: an entry means the last sweep of its case proved it (the evidence report reads a Db2 case's verdict from
    it); a case the sweep skipped (a push refresh skips Db2) keeps its entry."""
    monkeypatch.setattr(dcl, "fingerprints", lambda case: dict(FP))
    old = {CASE: entry(), "cbsa-updcust": entry()}
    built = dcl.build({CASE: {"proved": False, "coverage": ""}}, old)
    assert set(built) == {"cbsa-updcust"}
    assert dcl.build({}, old) == old


def test_ledger_files_are_not_git_ignored():
    """The per-case files must be committable (a `*.json` ignore rule once kept the ledger out of PR #4606)."""
    assert not dcl._ignored(dcl.path_of(CASE))
    assert dcl.load(), f"no entries under {dcl.LEDGER_DIR}"


def test_the_single_file_ledger_is_retired():
    """#4789: a branch from before the per-case ledger that still writes the single file fails here (every PR's CI runs
    this, not only the det sweep), with the command that moves its entries over."""
    assert not dcl.LEGACY.exists(), dcl.legacy_problem()


def test_check_fails_loudly_on_the_single_file(monkeypatch, tmp_path):
    monkeypatch.setattr(dcl, "fingerprints", lambda case: dict(FP))
    legacy = tmp_path / "det_sweep_coverage.json"
    legacy.write_text("{}")
    monkeypatch.setattr(dcl, "LEGACY", legacy)
    problems, _ = dcl.check({}, {})
    assert "split --base" in problems[0] and "retired" in problems[0]
    monkeypatch.setattr(dcl, "REPO", tmp_path)
    monkeypatch.setattr(dcl, "LEDGER_DIR", tmp_path / "dir")
    assert dcl.main(["update", str(tmp_path)]) == 1  # update refuses until the split


def test_write_is_one_file_per_case_and_only_touches_what_changed(tmp_path):
    """#4789: two sweeps of different cases change different files; an unchanged entry is an unchanged file."""
    d = tmp_path / "led"
    changed = dcl.write({CASE: entry(), "cbsa-updcust": entry()}, d)
    assert changed == [CASE, "cbsa-updcust"]
    assert sorted(p.name for p in d.iterdir()) == [f"{CASE}.json", "cbsa-updcust.json"]
    assert json.loads((d / f"{CASE}.json").read_text())["format"] == dcl.FORMAT
    assert dcl.load(d) == {CASE: entry(), "cbsa-updcust": entry()}  # the format key stays in the file
    before = (d / "cbsa-updcust.json").stat().st_mtime_ns
    changed = dcl.write({CASE: entry(scenarios=9), "cbsa-updcust": entry()}, d)
    assert changed == [CASE]
    assert (d / "cbsa-updcust.json").stat().st_mtime_ns == before
    changed = dcl.write({CASE: entry(scenarios=9)}, d)
    assert changed == ["cbsa-updcust"]  # #4758: a dropped entry is a deleted file
    assert dcl.load(d) == {CASE: entry(scenarios=9)}
    assert dcl.load(tmp_path / "none") == {}


def _legacy(path, cases):
    path.write_text(json.dumps({"format": "det-sweep-coverage/1", "about": "x", "cases": cases}, indent=1) + "\n")


def test_split_all_is_the_one_shot_migration(monkeypatch, tmp_path):
    monkeypatch.setattr(dcl, "REPO", tmp_path)
    legacy, d = tmp_path / "det_sweep_coverage.json", tmp_path / "led"
    dcl.write({"gone-case": entry()}, d)  # a per-case file the single file no longer has: removed
    _legacy(legacy, {CASE: entry(), "cbsa-updcust": entry(scenarios=2)})
    assert dcl.split(None, legacy, d) == [CASE, "cbsa-updcust", "gone-case"]
    assert dcl.load(d) == {CASE: entry(), "cbsa-updcust": entry(scenarios=2)}
    assert not legacy.exists()


def test_split_base_applies_only_the_branchs_changes(monkeypatch, tmp_path):
    """A branch from before #4789 merging main: its own rewrites / drops / additions since the merge base land; a case it
    did not touch keeps main's (newer) per-case file."""
    monkeypatch.setattr(dcl, "REPO", tmp_path)
    legacy, d = tmp_path / "det_sweep_coverage.json", tmp_path / "led"
    base = {CASE: entry(), "cbsa-updcust": entry(), "cbsa-crecust": entry()}
    main_now = {CASE: entry(measured_at="main"), "cbsa-updcust": entry(measured_at="main"),
                "cbsa-crecust": entry(measured_at="main"), "cbsa-delacc": entry(measured_at="main")}  # fmt: skip
    dcl.write(main_now, d)
    branch = {CASE: entry(scenarios=9), "cbsa-updcust": entry(), "cbsa-inqacc": entry(scenarios=1)}  # crecust dropped
    _legacy(legacy, branch)
    monkeypatch.setattr(dcl, "_show_at", lambda rev, path: json.dumps({"cases": base}) if rev == "mb" else None)
    dcl.split("mb", legacy, d)
    assert dcl.load(d) == {CASE: entry(scenarios=9), "cbsa-updcust": entry(measured_at="main"),
                           "cbsa-inqacc": entry(scenarios=1), "cbsa-delacc": entry(measured_at="main")}  # fmt: skip
    assert not legacy.exists()
    _legacy(legacy, branch)
    with pytest.raises(SystemExit, match="merge base from BEFORE"):
        dcl.split("after-the-merge", legacy, d)  # a base with no single file would overwrite main's entries
    assert legacy.exists()


def test_main_split_needs_all_or_base(capsys):
    with pytest.raises(SystemExit):
        dcl.main(["split"])
    assert "--all" in capsys.readouterr().err


def test_last_coverage_keeps_a_scheduled_stale_entry_and_flags_a_blocking_one(monkeypatch):
    """#4730: harness / oracle staleness leaves the last measurement readable; case / corpus makes it unknown."""
    monkeypatch.setattr(dcl, "fingerprints", lambda case: dict(FP))
    e = entry(measured_at="abc123")
    assert dcl.last_coverage(CASE, {CASE: e}) == {"coverage": (4, 4, 2, 2), "stale_inputs": [], "blocking": False,
                                                  "measured_at": "abc123"}  # fmt: skip
    monkeypatch.setattr(dcl, "fingerprints", lambda case: {**FP, "harness": "z", "oracle": "z"})
    got = dcl.last_coverage(CASE, {CASE: e})
    assert got["stale_inputs"] == ["harness", "oracle"] and not got["blocking"] and got["coverage"] == (4, 4, 2, 2)
    assert dcl.fresh_coverage(CASE, {CASE: e}) is None  # still not "current"
    monkeypatch.setattr(dcl, "fingerprints", lambda case: {**FP, "harness": "z", "case": "z"})
    assert dcl.last_coverage(CASE, {CASE: e})["blocking"] is True
    assert dcl.last_coverage(CASE, {}) is None
    assert dcl.last_coverage(CASE, {CASE: entry()})["measured_at"] is None  # an entry from before measured_at


def test_update_records_the_commit_measured_at(monkeypatch):
    monkeypatch.setattr(dcl, "fingerprints", lambda case: dict(FP))
    monkeypatch.setattr(dcl, "_head", lambda: "feedface")
    built = dcl.build({CASE: {"proved": True, "coverage": LINE}}, {})
    assert built[CASE]["measured_at"] == "feedface"


def test_update_is_idempotent_when_nothing_moved(monkeypatch):
    # The evidence-refresh bot's merge triggers the next refresh: restamping measured_at on unchanged entries made the
    # ledger change on every run, so it never settled and every open PR touching it went dirty.
    monkeypatch.setattr(dcl, "fingerprints", lambda case: dict(FP))
    monkeypatch.setattr(dcl, "_head", lambda: "feedface")
    first = dcl.build({CASE: {"proved": True, "coverage": LINE}}, {})
    monkeypatch.setattr(dcl, "_head", lambda: "c0ffee")
    assert dcl.build({CASE: {"proved": True, "coverage": LINE}}, first) == first
    monkeypatch.setattr(dcl, "fingerprints", lambda case: {**FP, "harness": "new"})
    assert dcl.build({CASE: {"proved": True, "coverage": LINE}}, first)[CASE]["measured_at"] == "c0ffee"


def test_a_component_the_case_does_not_use_does_not_stale_the_entry():
    """#4731: harness / oracle fingerprints differ, but every component the case uses is as it was: current. One it uses
    changing, or an entry with no components (written before them), keeps the whole-input meaning."""
    comps = {"harness": {"harness:core": "h1"}, "oracle": {"oracle:core": "o1", "oracle:le": "l1"}}
    held = entry(inputs={**FP, "components": comps})
    now = {**FP, "harness": "moved", "oracle": "moved", "components": comps}
    assert dcl.stale(held, now) == []
    now2 = {**now, "components": {**comps, "oracle": {**comps["oracle"], "oracle:le": "l2"}}}
    assert dcl.stale(held, now2) == ["oracle"]
    assert dcl.stale(entry(), now) == ["harness", "oracle"]  # a legacy entry
    assert dcl.stale(held, {**now, "case": "x"}) == ["case"]  # case / corpus have no components


def test_migrate_adds_components_only_to_a_current_entry(monkeypatch):
    comps = {"harness": {"harness:core": "h1"}, "oracle": {"oracle:core": "o1"}}
    monkeypatch.setattr(dcl, "fingerprints", lambda case: {**FP, "components": comps})
    got = dcl.migrate({CASE: entry(), "cbsa-updcust": entry(inputs={**FP, "harness": "old"})})
    assert got[CASE]["inputs"]["components"] == comps
    assert "components" not in got["cbsa-updcust"]["inputs"]  # stale on the whole input: left for the next sweep


def test_an_unchanged_sweep_touches_no_case_file(monkeypatch, tmp_path):
    """#4789 + #4813: the bot re-sweeping a case whose numbers and inputs did not move rewrites no file (measured_at is
    kept), so a refresh never touches the file of a case an open PR is changing."""
    monkeypatch.setattr(dcl, "fingerprints", lambda case: dict(FP))
    monkeypatch.setattr(dcl, "_head", lambda: "first")
    d = tmp_path / "led"
    det = {CASE: {"proved": True, "coverage": LINE}}
    dcl.write(dcl.build(det, {}), d)
    monkeypatch.setattr(dcl, "_head", lambda: "second")
    changed = dcl.write(dcl.build(det, dcl.load(d)), d)
    assert changed == [] and dcl.load(d)[CASE]["measured_at"] == "first"


# ---- #5084: LINKed-program counts, and a re-checked entry's fingerprints ------------------------------------------
LINKED = {"SUBP": {"paragraphs": {"covered": 1, "live": 2}, "branches": {"covered": 0, "total": 0}}}


def _cj(linked):
    return {"paragraphs": {"covered": 1, "live": 1}, "branches": {"covered": 0, "total": 0},
            "linked": {"SUBP": {"paragraphs": {"covered": 1, "live": 2, "dead": []},
                                "branches": {"covered": 0, "total": 0}}, **linked}}  # fmt: skip


def test_linked_counts_leaves_out_a_program_that_could_not_be_measured():
    assert dcl.linked_counts(_cj({"BAD": {"error": "x"}})) == LINKED
    assert dcl.linked_counts({}) == {} and dcl.linked_counts(None) == {}


def test_build_records_the_linked_counts_and_check_compares_them(monkeypatch):
    monkeypatch.setattr(dcl, "fingerprints", lambda case: dict(FP))
    det = {CASE: {"proved": True, "coverage": LINE, "linked": LINKED}}
    built = dcl.build(det, {CASE: entry()})  # an old entry without them is rewritten
    assert built[CASE]["linked"] == LINKED and dcl.last_coverage(CASE, built)["linked"] == LINKED
    assert dcl.check(det, built) == ([], [])
    problems, warnings = dcl.check(det, {CASE: entry()})
    assert not problems and "no LINKed-program counts" in warnings[0]
    moved = {SUB: {**v, "paragraphs": {"covered": 2, "live": 2}} for SUB, v in LINKED.items()}
    problems, _ = dcl.check(det, {CASE: entry(linked=moved)})
    assert "LINKed programs' coverage moved" in problems[0]


def test_a_rechecked_sweep_makes_a_stale_harness_fingerprint_a_problem(monkeypatch):
    monkeypatch.setattr(dcl, "fingerprints", lambda case: {**FP, "harness": "new"})
    det = {CASE: {"proved": True, "coverage": LINE}}
    old = {CASE: entry()}
    problems, warnings = dcl.check(det, old)  # scheduled / bot runs: a warning
    assert not problems and "harness" in warnings[0]
    problems, _ = dcl.check(det, old, recheck=True)  # a PR's sweep re-checked the counts: re-record
    assert "stale (harness changed)" in problems[0] and "det_coverage_ledger.py update" in problems[0]
    built = dcl.build(det, old)
    assert dcl.check(det, built, recheck=True) == ([], [])


def test_build_records_the_uncovered_lists_only_when_there_are_some(monkeypatch):
    """#6072: ladder_gaps.py reads them; an empty list leaves no key (an always-present empty key breaks equality)."""
    monkeypatch.setattr(dcl, "fingerprints", lambda case: dict(FP))
    row = {"proved": True, "coverage": LINE, "uncovered": ["8:false"], "uncovered_paragraphs": ["RARE:20"]}
    got = dcl.build({CASE: row}, {})[CASE]
    assert got["uncovered"] == {"paragraphs": ["RARE:20"], "branches": ["8:false"]}
    only = dcl.build({CASE: {**row, "uncovered_paragraphs": []}}, {})[CASE]
    assert only["uncovered"] == {"branches": ["8:false"]}
    assert "uncovered" not in dcl.build({CASE: {"proved": True, "coverage": LINE, "uncovered": []}}, {})[CASE]


def test_an_unchanged_sweep_keeps_the_entry_and_a_moved_list_rewrites_it(monkeypatch):
    monkeypatch.setattr(dcl, "fingerprints", lambda case: dict(FP))
    row = {"proved": True, "coverage": LINE, "uncovered": ["8:false"]}
    first = dcl.build({CASE: row}, {})
    assert dcl.build({CASE: row}, first) == first
    moved = dcl.build({CASE: {**row, "uncovered": ["9:true"]}}, first)
    assert moved[CASE]["uncovered"] == {"branches": ["9:true"]}


def test_check_only_warns_when_the_uncovered_lists_differ(monkeypatch):
    monkeypatch.setattr(dcl, "fingerprints", lambda case: dict(FP))
    row = {"proved": True, "coverage": LINE, "uncovered": ["8:false"]}
    assert dcl.check({CASE: row}, {CASE: entry(uncovered={"branches": ["8:false"]})}) == ([], [])
    problems, warnings = dcl.check({CASE: row}, {CASE: entry()})  # an entry from before #6072
    assert not problems and "uncovered lists differ" in warnings[0]
    assert dcl.check({CASE: {"proved": True, "coverage": LINE}}, {CASE: entry()}) == ([], [])  # a row without the key
