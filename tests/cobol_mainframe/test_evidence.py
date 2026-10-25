"""#4048: the evidence records -- one per ported program -- are current, complete, valid, rendered, and approved only
by a person.

Cheap: hashing and JSON, no Docker. tests/tools/evidence.py holds the record; docs/language_status/evidence_records.md
explains it.
"""

import ast
import copy
import json
import subprocess
import sys
import warnings
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import evidence as ev  # noqa: E402

REPO = ev.REPO_ROOT
MUTATION_SCORES = REPO / "docs" / "language_status" / "mutation_scores.json"

# Committed ports with no evidence record yet, each with the reason. A ratchet: it only shrinks (an entry whose
# record now exists fails test_the_missing_list_only_shrinks).
MISSING: dict[str, str] = {}

# Records whose `mutation` section is still null, each with the reason (#4048). A ratchet: it only shrinks.
MUTATION_PENDING: dict[str, str] = {
    "carddemo-cbstm03a": "#5856: a det batch port; its L5 mutation run (det_mutation.py run) and survivor review are a follow-up",
    "carddemo-cbpaup0c": "#5857: a det BMP port; its L5 mutation run (det_mutation.py run) and survivor review are a follow-up",
    "carddemo-copaua0c": "#5278: a det CICS port; its L5 mutation run (det_mutation.py run) and survivor review are a follow-up",
    "carddemo-copaus0c": "#5233: a det CICS port; its L5 mutation run (det_mutation.py run) and survivor review are a follow-up",
    "carddemo-copaus1c": "#5233: a det CICS port; its L5 mutation run (det_mutation.py run) and survivor review are a follow-up",
}


def _records():
    return [(t, ev.load(t)) for t in ev.targets()]


# ---- the committed records -----------------------------------------------------------------------------------------
def test_every_committed_record_is_current():
    """Q1: stale on the port, its case, its corpus pin or its declared differences fails here -- re-prove it in the
    PR (evidence.py prove KEY). Stale on the harness, the oracle or the generator is reported and re-proven by the
    scheduled job (.github/workflows/evidence-refresh.yml)."""
    blocking, scheduled = [], []
    for t, rec in _records():
        if rec is None:
            continue
        st = ev.status(rec, t)
        if st["blocking"]:
            blocking.append(f"{t.key}: {', '.join(st['blocking'])} changed since the proof")
        elif st["stale"]:
            scheduled.append(f"{t.key}: {', '.join(st['stale'])}")
    if scheduled:
        warnings.warn("evidence records stale on the harness / oracle / generator (re-proven by the scheduled job): "
                      + "; ".join(scheduled), stacklevel=1)  # fmt: skip
    assert not blocking, ("re-prove these in this PR (python tests/tools/evidence.py prove KEY):\n"
                          + "\n".join(blocking))  # fmt: skip


def test_records_cover_the_ports():
    missing = [t.key for t, rec in _records() if rec is None and t.key not in MISSING]
    assert not missing, f"committed ports with no evidence record (python tests/tools/evidence.py prove KEY): {missing}"


def test_the_missing_list_only_shrinks():
    have = {t.key for t, rec in _records() if rec is not None}
    known = {t.key for t in ev.targets()}
    assert not (set(MISSING) & have), f"these have a record now: drop them from MISSING: {sorted(set(MISSING) & have)}"
    assert set(MISSING) <= known, f"not a committed port: {sorted(set(MISSING) - known)}"


def test_every_record_carries_a_mutation_section():
    """#4048: a record's mutation section is filled from docs/language_status/mutation_scores.json, never null, and
    its source names a port that file really scores."""
    scored = {f"{p['case']}/{p['program']}" for p in json.loads(MUTATION_SCORES.read_text())["ports"]}
    nulls, dangling = [], []
    for t, rec in _records():
        if rec is None or t.key in MUTATION_PENDING:
            continue
        mut = rec.get("mutation")
        if not mut:
            nulls.append(t.key)
        elif mut.get("source", "").split("#", 1)[-1] not in scored:
            dangling.append(f"{t.key}: {mut.get('source')}")
    assert not nulls, (
        f"records with mutation: null (mutation.py run, mutation_scores.py build, evidence.py mutation): {nulls}"
    )
    assert not dangling, f"mutation source not in mutation_scores.json: {dangling}"


def test_the_mutation_pending_list_only_shrinks():
    done = {t.key for t, rec in _records() if rec is not None and rec.get("mutation")}
    known = {t.key for t in ev.targets()}
    assert not (set(MUTATION_PENDING) & done), f"drop from MUTATION_PENDING: {sorted(set(MUTATION_PENDING) & done)}"
    assert set(MUTATION_PENDING) <= known, f"not a committed port: {sorted(set(MUTATION_PENDING) - known)}"


def test_every_record_is_valid():
    for t, rec in _records():
        if rec is not None:
            assert ev.validate(rec) == [], f"{t.key}: {ev.validate(rec)}"
            assert rec["program"] == t.program and rec["kind"] == t.kind


def test_no_record_lies_where_it_lives():
    """A record is about the port beside it: its own port files are the ones it names."""
    for t, rec in _records():
        if rec is not None:
            assert rec["port"]["paths"] == ev.port_files(t), t.key


def test_every_record_renders_a_page_deterministically():
    """#4825: the pages are no longer committed (evidence-pages.yml publishes them from main to the `generated` branch),
    so this checks the render itself: one page per record plus the index, the same text twice."""
    pages = ev.rendered()
    assert ev.PAGES / "README.md" in pages
    assert sum(1 for _, rec in ((t, ev.load(t)) for t in ev.targets()) if rec is not None) == len(pages) - 1
    assert pages == ev.rendered()


def test_main_does_not_commit_the_pages():
    """#4825: PRs collided on the rendered pages; they live on the `generated` branch only."""
    tracked = subprocess.run(["git", "ls-files", "docs/language_status/evidence"], cwd=ev.REPO_ROOT,  # noqa: S603, S607
                             capture_output=True, text=True, check=True).stdout.split()  # fmt: skip
    assert tracked == [], f"remove from git (they are published to the generated branch): {tracked[:5]}"


def test_committed_approvals_name_a_person_and_what_they_attest():
    for t, rec in _records():
        for a in (rec or {}).get("approvals", []):
            assert not ev._MODEL_NAMES.search(a["by"]), f"{t.key}: approved by {a['by']!r}"
            assert a["attests"] == ev.ATTESTATION.format(purpose=a["purpose"]), t.key


# ---- only a person writes an approval -----------------------------------------------------------------------------
_TOOLS_WITHOUT_APPROVALS = ("equivalence.py", "equivalence_call.py", "equivalence_cics.py",
                            "equivalence_cics_conditions.py", "equivalence_cics_containers.py", "equivalence_cics_filecontrol.py", "equivalence_cics_tempstorage.py", "cics_crucible.py",
                            "mutation.py", "mutation_crucible.py", "mutation_scores.py", "crucible_port_provenance.py")  # fmt: skip
_ALLOWED_WRITERS = {"_append_approval", "new_record", "save"}


def _parents(tree):
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child._parent = node  # type: ignore[attr-defined]


def _function(node):
    while node is not None and not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        node = getattr(node, "_parent", None)
    return node.name if node is not None else None


def _is_approvals(node):
    return isinstance(node, ast.Constant) and node.value == "approvals"


def _writes(tree):
    """Each place `approvals` is written: a store into rec["approvals"], .append/.extend/.insert on it, setdefault,
    or a dict literal with the key."""
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and _is_approvals(node.slice):
            parent = getattr(node, "_parent", None)
            if isinstance(node.ctx, (ast.Store, ast.Del)) or (
                isinstance(parent, ast.Attribute) and parent.attr in ("append", "extend", "insert", "update")
            ):
                out.append(node)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "setdefault" \
                and node.args and _is_approvals(node.args[0]):  # fmt: skip
            out.append(node)
        elif isinstance(node, ast.Dict) and any(_is_approvals(k) for k in node.keys if k is not None):
            out.append(node)
    return out


def test_no_tool_writes_an_approval():
    """#4048: tools write evidence; only `evidence.py approve|reject` (a person at a terminal) writes an approval.
    Nothing else in the tools or the engine names the key, and inside evidence.py every write to it sits in
    _append_approval (or makes the empty list / carries the disk's list through unchanged)."""
    for path in [*(REPO / "tests" / "tools").glob("*.py"), *(REPO / "gitgalaxy").rglob("*.py")]:
        if path.name == "evidence.py":
            continue
        text = path.read_text(encoding="utf-8")  # our own source: UTF-8, read strictly
        assert '"approvals"' not in text and "'approvals'" not in text, f"{path.relative_to(REPO)} names `approvals`"
        if path.name in _TOOLS_WITHOUT_APPROVALS:  # the proof and mutation tools: not even through a variable
            assert "_append_approval" not in text and "evidence.sign" not in text, path.relative_to(REPO)
    tree = ast.parse((REPO / "tests" / "tools" / "evidence.py").read_text(encoding="utf-8"))
    _parents(tree)
    where = {_function(n) for n in _writes(tree)}
    assert where <= _ALLOWED_WRITERS, (
        f"evidence.py writes approvals outside {_ALLOWED_WRITERS}: {where - _ALLOWED_WRITERS}"
    )
    assert "_append_approval" in where


def _dateutil():
    t = ev.target("carddemo-dateutil")
    rec = ev.load(t)
    if rec is None:
        pytest.skip("no carddemo-dateutil record")
    return t, copy.deepcopy(rec)


def _with_unproven(rec):
    """The record with a ported method no proof runs (the generator's executeX that #4342 removed from the port)."""
    unproven = [
        *rec["reach"]["unproven"],
        {"class": "CsutldtcService", "method": "executeCsutldtc", "line": 30, "kind": "ported_unproven"},
    ]
    counts = {**rec["reach"]["counts"], "ported_unproven": rec["reach"]["counts"]["ported_unproven"] + 1}
    return {**rec, "reach": {**rec["reach"], "unproven": unproven, "counts": counts}}


def _current(t, rec):
    """The record made current and fully proven (as if re-proven now with every ported method reached)."""
    rec["inputs"] = ev.compute_inputs(t, rec.get("differences"))
    rec["proof"] = {**rec["proof"], "verdict": "proven", "inputs_digest": rec["inputs"]["digest"]}
    rec["reach"] = {**rec["reach"], "unproven": [m for m in rec["reach"]["unproven"] if m["kind"] != "ported_unproven"],
                    "port_sha256": ev.tree_sha256(ev.port_files(t))}  # fmt: skip
    return rec


# ---- status --------------------------------------------------------------------------------------------------------
def test_a_current_proof_with_no_ported_unproven_method_is_proven_unapproved():
    t, rec = _dateutil()
    st = ev.status(_current(t, rec), t)
    assert st["status"] == "proven, unapproved" and st["stale"] == [], st


def test_a_port_or_case_change_is_blocking_a_harness_change_is_not():
    t, rec = _dateutil()
    rec = _current(t, rec)
    port = copy.deepcopy(rec)
    port["inputs"]["port"]["sha256"] = "0" * 64
    st = ev.status(port, t)
    assert st["status"] == "stale" and st["blocking"] == ["port"]
    harness = copy.deepcopy(rec)
    harness["inputs"]["harness"]["sha256"] = "0" * 64
    del harness["inputs"]["harness"][
        "components"
    ]  # (#4731: a record proven before components compares the whole input)
    st = ev.status(harness, t)
    assert st["status"] == "stale" and st["stale"] == ["harness"] and st["blocking"] == []
    assert "stale: harness changed since the proof" in st["reasons"]


@pytest.mark.parametrize(("policy", "expect"), [("block", "not-proven"), ("report", "proven, unapproved")])
def test_ported_unproven_blocks_under_the_default_policy(policy, expect):
    """Q7 (owner decision): a ported_unproven method makes the record not proven; "report" counts it only."""
    t, rec = _dateutil()
    rec = _current(t, rec)
    rec["reach"]["unproven"] = [{"class": "X", "method": "executeX", "line": 1, "kind": "ported_unproven"},
                                {"class": "X", "method": "handleLink", "line": 2, "kind": "left_as_generated"},
                                {"class": "X", "method": "onAbend", "line": 3, "kind": "stub"}]  # fmt: skip
    st = ev.status(rec, t, policy=policy)
    assert st["status"] == expect
    if policy == "block":
        assert st["reasons"][0] == "1 ported_unproven method (executeX)"
    assert ev.PORTED_UNPROVEN_POLICY == "block"


def test_stubs_and_left_as_generated_never_block():
    t, rec = _dateutil()
    rec = _current(t, rec)
    rec["reach"]["unproven"] = [{"class": "X", "method": "handleLink", "line": 2, "kind": "left_as_generated"},
                                {"class": "X", "method": "onAbend", "line": 3, "kind": "stub"}]  # fmt: skip
    assert ev.status(rec, t)["status"] == "proven, unapproved"


def test_a_failed_proof_is_not_proven_and_a_missing_record_says_so():
    t, rec = _dateutil()
    rec = _current(t, rec)
    rec["proof"]["verdict"] = "not-proven"
    assert ev.status(rec, t)["status"] == "not-proven"
    assert ev.status(None, t)["status"] == "no-record"


def _menu():
    t = ev.target("carddemo-menu")
    rec = ev.load(t)
    if rec is None:
        pytest.skip("no carddemo-menu record")
    return t, copy.deepcopy(rec)


def test_a_cics_port_with_facades_is_proven_only_through_them_too():
    """#4449: a CICS online port whose facades (handleTransaction / handleLink) no proof entered is not proven --
    as #4343 made the crucible's ports; a proof that ran the java-facade side and passed is."""
    t, rec = _menu()
    assert ev.port_facades(t) == ["handleLink", "handleTransaction"]
    rec = _current(t, rec)
    rec["proof"].pop("facade", None)
    st = ev.status(rec, t)
    assert st["status"] == "not-proven"
    assert st["reasons"][0].startswith("not proven through its deployed entry points (handleLink / handleTransaction)")
    rec["proof"]["facade"] = {"verdict": "proven", "runs": 16, "passed": 16, "entry_points": ["handleTransaction"],
                              "failed": [], "error": None}  # fmt: skip
    assert ev.status(rec, t)["status"] == "proven, unapproved"
    failed = copy.deepcopy(rec)
    failed["proof"]["verdict"] = "not-proven"
    failed["proof"]["facade"].update(verdict="not-proven", passed=15,
                                     failed=[{"scenario": "x", "why": "refused: ..."}])  # fmt: skip
    st = ev.status(failed, t)
    assert st["status"] == "not-proven"
    assert "through its deployed entry points (java-facade: 15/16 scenarios pass)" in st["reasons"][0]


def test_a_batch_or_call_port_needs_no_facade():
    t, rec = _dateutil()
    assert ev.port_facades(t) == []
    assert ev.status(_current(t, rec), t)["status"] == "proven, unapproved"


def test_the_facade_summary_keeps_each_failing_scenario_and_why():
    fc = {"proven": False, "entry_points": [{"method": "handleTransaction", "scenarios": ["a"]}],
          "outputs": {"a": {"pass": True, "equal": 2, "records": 2},
                      "b": {"pass": False, "equal": 1, "records": 2, "refused": "handleTransaction of P threw"},
                      "c": {"pass": False, "equal": 1, "records": 2, "files": {"F": {}}}}}  # fmt: skip
    got = ev.facade_summary(fc)
    assert got["verdict"] == "not-proven" and (got["runs"], got["passed"]) == (3, 1)
    assert got["entry_points"] == ["handleTransaction"]
    assert got["failed"] == [{"scenario": "b", "why": "refused: handleTransaction of P threw"},
                             {"scenario": "c", "why": "differs (1/2 events equal, files differ)"}]  # fmt: skip


FACADE_BASELINE = ev.CASES / "facade_baseline.json"


def test_every_failing_facade_scenario_is_ledgered_with_its_issue():
    """#4449: a CICS port whose java-facade side fails keeps its record honest (not proven) and its failing scenarios
    ledgered in tests/equivalence/facade_baseline.json, each case with the issue that owns the defect, as the
    crucible ledgers its cells (tests/cics_crucible/baseline.json). A record whose failures differ from the ledger --
    a fix, or a new failure -- fails here: update the ledger in the same PR."""
    ledger = json.loads(FACADE_BASELINE.read_text(encoding="utf-8"))["cases"]
    got = {}
    for t, rec in _records():
        fc = ((rec or {}).get("proof") or {}).get("facade")
        if t.kind == "cics" and fc and fc["verdict"] != "proven":
            got[t.key] = sorted(f["scenario"] for f in fc["failed"])
    assert got == {k: sorted(v["scenarios"]) for k, v in ledger.items()}
    for key, v in ledger.items():
        assert v["issue"].startswith("#") and v["why"], key
        prov = ev.target(key).port_dir / "provenance.json"
        if prov.is_file():  # the port's provenance says it is stale, and why
            assert v["issue"] in json.loads(prov.read_text(encoding="utf-8")).get("stale", {}).get("needs", ""), key


# ---- approval -------------------------------------------------------------------------------------------------------
def _tmp_target(tmp_path, t, rec):
    tt = ev.Target(**{**t.__dict__, "record": tmp_path / "evidence.json"})
    tt.record.write_text(json.dumps(rec), encoding="utf-8")
    return tt


def test_an_approval_is_signed_by_a_person_at_a_terminal(tmp_path):
    t, rec = _dateutil()
    tt = _tmp_target(tmp_path, t, _current(t, rec))
    entry = ev.sign(tt, "Jane Reviewer", "the Q4 pilot", "approved", None, interactive=True,
                    confirm=lambda prompt: "Jane Reviewer")  # fmt: skip
    assert entry["attests"] == ("I reviewed this evidence summary (scenarios run, coverage, unproven methods, "
                                "declared differences) and accept it for the Q4 pilot.")  # fmt: skip
    saved = ev.load(tt)
    assert saved["approvals"] == [entry] and entry["inputs_digest"] == saved["inputs"]["digest"]
    st = ev.status(saved, tt)
    assert st["status"] == "proven, approved" and st["approved"]["by"] == "Jane Reviewer"
    # a tool rewriting the record keeps the approval exactly
    ev.save(tt, {**saved, "approvals": []})
    assert ev.load(tt)["approvals"] == [entry]
    # and any later change to an input makes it an approval of an earlier version
    moved = ev.load(tt)
    moved["inputs"]["harness"]["sha256"] = "0" * 64
    del moved["inputs"]["harness"]["components"]  # (#4731: compare the whole input)
    st = ev.status(moved, tt)
    assert st["status"] == "stale" and not st["approved"]["current"]


@pytest.mark.parametrize(("by", "purpose", "interactive", "why"), [
    ("Jane Reviewer", "the pilot", False, "terminal"),
    ("claude", "the pilot", True, "not a tool or model"),
    ("evidence-bot", "the pilot", True, "not a tool or model"),
    ("Jane Reviewer", "  ", True, "accepted for"),
])  # fmt: skip
def test_an_approval_is_refused_to_a_script_a_model_or_no_purpose(tmp_path, by, purpose, interactive, why):
    t, rec = _dateutil()
    tt = _tmp_target(tmp_path, t, _current(t, rec))
    with pytest.raises(ev.ApprovalRefused, match=why):
        ev.sign(tt, by, purpose, "approved", None, interactive=interactive, confirm=lambda prompt: by)
    assert ev.load(tt)["approvals"] == []


def test_only_a_proven_current_record_can_be_approved(tmp_path):
    t, rec = _dateutil()
    rec = _with_unproven(rec)  # a ported_unproven method: not proven
    tt = _tmp_target(tmp_path, t, rec)
    with pytest.raises(ev.ApprovalRefused, match="only a current proof"):
        ev.sign(tt, "Jane Reviewer", "the pilot", "approved", None, interactive=True, confirm=lambda p: "Jane Reviewer")


def test_a_mistyped_name_signs_nothing(tmp_path):
    t, rec = _dateutil()
    tt = _tmp_target(tmp_path, t, _current(t, rec))
    with pytest.raises(ev.ApprovalRefused, match="does not match"):
        ev.sign(tt, "Jane Reviewer", "the pilot", "approved", None, interactive=True, confirm=lambda p: "jane")
    assert ev.load(tt)["approvals"] == []


# ---- the claim and the fingerprints ----------------------------------------------------------------------------------
def test_the_claim_is_derived_from_the_numbers():
    t, rec = _dateutil()
    text = ev.claim(rec, ev.status(rec, t, live=False))
    assert text.startswith("**CSUTLDTC**: byte-identical on **34 calls**")
    assert "Proven through **handleCall** only; **0 ported method(s) that no proof runs**" in text
    rec = _with_unproven(rec)
    text = ev.claim(rec, ev.status(rec, t, live=False))
    assert "**1 ported method(s) that no proof runs** (executeCsutldtc)" in text and "not-proven" in text


def test_a_tree_digest_is_path_and_bytes_and_order_free():
    a = ev.tree_sha256(["tests/tools/evidence.py", "tests/tools/equivalence.py"])
    assert a == ev.tree_sha256(["tests/tools/equivalence.py", "tests/tools/evidence.py"])
    assert a != ev.tree_sha256(["tests/tools/evidence.py"])
    assert ev.tree_sha256([]) == ev.EMPTY_SHA


# ---- entry runs: a batch step proven through its controller's no-argument method too ------------------------------
def test_an_entry_method_is_reached_only_when_the_proof_ran_it():
    t = ev.equivalence_target("carddemo-acctview")
    without = ev.reach_section(t)
    assert "handleTransaction" in {m["method"] for m in without["unproven"]}
    run = ev.reach_section(t, entries=["handleTransaction"])
    assert (
        "handleTransaction" not in {m["method"] for m in run["unproven"]} and "handleTransaction" in run["entry_points"]
    )


def test_the_generated_test_drives_each_entry_and_refuses_a_parm(monkeypatch):
    import equivalence_java as ej  # noqa: PLC0415

    case = json.loads((REPO / "tests/equivalence/carddemo-readcard/case.json").read_text(encoding="utf-8"))
    case["name"] = "carddemo-readcard"
    case["entries"] = [{"method": "executeCbact02c", "why": "a test"}]
    monkeypatch.setattr(ej, "_entry_returns", lambda case, svc: {"executeCbact02c": "int"})
    src = ej.equivalence_test(case)
    assert 'System.getProperty("equivalence.entry", "")' in src
    # #4342: the generated executeX returns runBatch's RETURN-CODE, and the entry run compares that one
    assert 'case "executeCbact02c" -> rc = cbact02cService.executeCbact02c();' in src and "runBatch(List.of(" in src
    monkeypatch.setattr(ej, "_entry_returns", lambda case, svc: {"executeCbact02c": "void"})
    void = ej.equivalence_test(case)  # a void entry that returns normally ends the step RETURN-CODE 0
    assert "cbact02cService.executeCbact02c();\n                    rc = 0;" in void
    assert "equivalence.entry" not in ej.equivalence_test({**case, "entries": []})
    with pytest.raises(SystemExit, match="passes no PARM"):
        ej.entry_names({**case, "parm": "2022071800"})
    with pytest.raises(SystemExit, match="not Java method names"):
        ej.entry_names({**case, "entries": [{"method": "x(); evil"}]})


def test_a_task_judged_up_to_x6_is_recorded_and_stated_as_an_assumption():
    """Owner decision on #4607: a task judged up to a refused WRITEQ (X6) is recorded as such, and the page states X6
    as an assumption of those tasks; a task judged whole carries neither."""
    t = next(t for t, _ in _records())
    report = {"proven": True, "outputs": {
        "whole": {"equal": 2, "records": 2},
        "error-path": {"equal": 5, "records": 5, "judged_to": "the refused WRITEQ (X6 ...)", "x6": {"ok": True}}}}  # fmt: skip
    proof = ev.proof_section(t, report, "d")
    assert proof["outputs"]["whole"] == {"equal": 2, "records": 2}
    assert proof["outputs"]["error-path"]["assumes"] == "X6"


def test_a_task_that_ran_a_padded_writeq_states_x6_as_an_assumption():
    """X6 ASSUMED (owner 2026-10-21): a task that runs on through a WRITEQ past FROM (padded on both sides) is judged
    whole, and still names X6 among its proof's assumptions; the page says it was padded, not judged up to a refusal."""
    t = next(t for t, _ in _records())
    report = {"proven": True, "outputs": {
        "whole": {"equal": 2, "records": 2},
        "error-path": {"equal": 6, "records": 6, "x6_padded": ["WRITEQ TD", "WRITEQ TS"]}}}  # fmt: skip
    proof = ev.proof_section(t, report, "d")
    assert proof["outputs"]["whole"] == {"equal": 2, "records": 2}
    assert proof["outputs"]["error-path"] == {"equal": 6, "records": 6, "assumes": "X6",
                                              "x6_padded": ["WRITEQ TD", "WRITEQ TS"]}  # fmt: skip
    assert "judged_to" not in proof["outputs"]["error-path"]
    page = ev.render_page(t, {**_runtime_record()[1], "proof": proof})
    assert "| error-path | 6 | 6 (assumes X6: a WRITEQ past FROM, padded) |" in page
    assert "Assumes oracle_assumptions.md X6 for 1 task(s) (error-path): each ran a WRITEQ" in page
    assert "judged up to the refusal" not in page and "each is compared up" not in page


# ---- #4744: the refresh's shards ---------------------------------------------------------------------------------------
def _refresh_args(*extra):
    ap_args = ["refresh", "--stale", "--skip-db2", *extra]
    import argparse

    ns = argparse.Namespace(cmd="refresh", keys=[], all=False, stale=True, skip_db2=True, only_db2=False, shard=None)
    for a in ap_args:
        if a.startswith("--shard="):
            ns.shard = ev._parse_shard(a.split("=", 1)[1])
    return ns


def test_the_shards_of_a_refresh_are_exactly_the_unsharded_selection(monkeypatch):
    """Slices I/N of the stale records together are the whole selection, once each: no record is proved twice or dropped."""
    keys = [f"k{i:02d}" for i in range(11)]
    fake = [type("T", (), {"key": k, "db2": k == "k03"})() for k in keys]
    monkeypatch.setattr(ev, "_pick", lambda ks, all_: fake)
    monkeypatch.setattr(ev, "load", lambda t: {})
    monkeypatch.setattr(ev, "status", lambda rec, t: {"status": "stale", "stale": ["harness"]} if t.key != "k05" else {"status": "proven", "stale": []})  # fmt: skip
    whole = [t.key for t in ev._selected(_refresh_args(), say=lambda s: None)]
    assert "k03" not in whole and "k05" not in whole and len(whole) == 9  # Db2 and current records left out
    for n in (1, 3, 4, 20):
        got = [
            [t.key for t in ev._selected(_refresh_args(f"--shard={i}/{n}"), say=lambda s: None)]
            for i in range(1, n + 1)
        ]
        assert sorted(k for s in got for k in s) == sorted(whole)
        assert max(map(len, got)) - min(map(len, got)) <= 1


@pytest.mark.parametrize("text", ["0/4", "5/4", "x", "2"])
def test_a_bad_shard_is_refused(text):
    import argparse

    with pytest.raises(argparse.ArgumentTypeError):
        ev._parse_shard(text)


# ---- #4707: the runtime option fingerprint on the page ----------------------------------------------------------------
def _runtime_record(le_storage="NONE,NONE,NONE,0K"):
    t, rec = _dateutil()
    rec["inputs"] = ev.compute_inputs(t, rec.get("differences"))
    eff = rec["inputs"]["options"]["effective"]
    eff["runtime"] = {"le": {"STORAGE": le_storage, "TRAP": "ON,SPIE"}, "db2": {"ISOLATION": "UR"}, "cics": {}}
    return t, rec


def _runtime_row(page):
    return [ln for ln in page.splitlines() if ln.startswith("| runtime options |")]


def test_the_page_shows_the_runtime_options_a_proof_ran_under():
    t, rec = _runtime_record()
    (row,) = _runtime_row(ev.render_page(t, rec))
    runtime = rec["inputs"]["options"]["effective"]["runtime"]
    assert ev.json_sha256({s: v for s, v in runtime.items() if v})[:16] in row
    assert "(db2 1, le 2)" in row and "cics" not in row  # an empty section is not shown
    assert "le.STORAGE=NONE,NONE,NONE,0K" in row and "db2.ISOLATION=UR" in row


@pytest.mark.parametrize("runtime", [None, {}, {"le": {}, "db2": {}, "cics": {}}])
def test_a_record_with_no_runtime_options_renders_no_row(runtime):
    t, rec = _runtime_record()
    rec["inputs"]["options"]["effective"].pop("runtime")
    if runtime is not None:
        rec["inputs"]["options"]["effective"]["runtime"] = runtime
    assert _runtime_row(ev.render_page(t, rec)) == []
    assert ev.runtime_line(rec["inputs"]["options"]) is None
    assert ev.runtime_line(None) is None


def test_the_live_options_input_carries_the_runtime_hash_but_changed_ignores_it():
    t, rec = _dateutil()
    now = ev.compute_inputs(t, rec.get("differences"))
    opts = now["options"]
    assert opts["runtime_sha256"] == ev.json_sha256(opts["effective"]["runtime"])
    stored = {k: copy.deepcopy(v) for k, v in now.items()}
    stored["options"].pop("runtime_sha256")  # a record written before this key: still current
    assert "options" not in ev.changed(stored, now)


def test_a_changed_runtime_value_changes_the_row_and_a_note_does_not():
    t, a = _runtime_record()
    _, b = _runtime_record(le_storage="00,NONE,NONE,0K")
    assert _runtime_row(ev.render_page(t, a)) != _runtime_row(ev.render_page(t, b))
    # the fingerprint hashes values, never provenance: a changed note leaves the runtime hash alone
    from gitgalaxy.core.estate_options import effective_options

    case = ev._case_json(t.case)
    base = effective_options(case, program=t.program).fingerprint()["runtime"]
    noted = copy.deepcopy(effective_options(case, program=t.program))
    noted.runtime_sources = {k: "changed note" for k in noted.runtime_sources}
    assert noted.fingerprint()["runtime"] == base


def test_the_page_shows_the_compiler_options_a_proof_ran_under():
    t, rec = _runtime_record()
    rec["inputs"]["options"]["effective"]["semantic"] = {"ARITH": "COMPAT", "TRUNC": "STD"}
    (row,) = [ln for ln in ev.render_page(t, rec).splitlines() if ln.startswith("| compiler options |")]
    assert ev.json_sha256({"ARITH": "COMPAT", "TRUNC": "STD"})[:16] in row
    assert "(2): ARITH=COMPAT, TRUNC=STD" in row


@pytest.mark.parametrize("semantic", [None, {}])
def test_a_record_with_no_compiler_options_renders_no_row(semantic):
    t, rec = _runtime_record()
    rec["inputs"]["options"]["effective"].pop("semantic", None)
    if semantic is not None:
        rec["inputs"]["options"]["effective"]["semantic"] = semantic
    page = ev.render_page(t, rec)
    assert "| compiler options |" not in page
    assert ev.compiler_line(rec["inputs"]["options"]) is None
    assert ev.compiler_line(None) is None


def test_a_scenario_records_the_commands_its_cobol_run_executed():
    """#5229: `commands` is the sorted distinct verbs of the oracle run, without the end-state snapshots; a scenario
    with none carries no key (python-test-traps.md)."""
    sys.path.insert(0, str(REPO / "tests" / "tools"))
    import equivalence_cics as ec

    events = [{"event": "RECEIVE-MAP"}, {"event": "WRITEQ-TS"}, {"event": "RECEIVE-MAP"},
              {"event": "COMMAREA"}, {"event": "CONTAINERS"}, {"event": "RETURN"}]  # fmt: skip
    assert ec.executed_commands(events) == ["RECEIVE-MAP", "RETURN", "WRITEQ-TS"]
    assert ec.executed_commands([{"event": "COMMAREA"}]) == []
    t = next(t for t, _ in _records())
    report = {"proven": True, "outputs": {"a": {"equal": 3, "records": 3, "commands": ["RETURN", "WRITEQ-TS"]},
                                          "b": {"equal": 1, "records": 1}}}  # fmt: skip
    proof = ev.proof_section(t, report, "d")
    assert proof["outputs"]["a"] == {"equal": 3, "records": 3, "commands": ["RETURN", "WRITEQ-TS"]}
    assert proof["outputs"]["b"] == {"equal": 1, "records": 1}


# ---- #6680: a ledgered facade failure does not fail the refresh -------------------------------------------------------
def _facade_rec(failed, **over):
    proof = {"verdict": "not-proven", "java_failed": False,
             "facade": {"verdict": "not-proven", "error": None, "failed": [{"scenario": n} for n in failed]}}  # fmt: skip
    return {"proof": {**proof, **over}}


@pytest.fixture
def _ledger(tmp_path):
    p = tmp_path / "facade_baseline.json"
    p.write_text(json.dumps({"cases": {"k": {"issue": "#1", "why": "w", "scenarios": ["a", "b"]}}}), encoding="utf-8")
    return p


@pytest.mark.parametrize(
    "key,rec,want",
    [
        ("k", _facade_rec(["b", "a"]), "#1"),
        ("k", _facade_rec(["a"]), None),  # one fixed: update the ledger
        ("k", _facade_rec(["a", "b", "c"]), None),  # a new failure
        ("k", _facade_rec(["a", "b"], java_failed=True), None),
        ("k", {"proof": {**_facade_rec(["a", "b"])["proof"], "facade": {"verdict": "not-proven", "error": "x", "failed": [{"scenario": "a"}, {"scenario": "b"}]}}}, None),
        ("other", _facade_rec(["a", "b"]), None),
        ("k", {"proof": {"verdict": "not-proven"}}, None),
        ("k", None, None),
    ],
)  # fmt: skip
def test_only_the_exact_ledgered_facade_failure_is_exempt(_ledger, key, rec, want):
    assert ev.ledgered_facade_only(key, rec, _ledger) == want


def test_the_committed_ledgered_records_do_not_fail_prove(monkeypatch, capsys):
    keys = json.loads(FACADE_BASELINE.read_text(encoding="utf-8"))["cases"]
    for k in keys:
        assert ev.ledgered_facade_only(k, ev.load(ev.target(k))) == keys[k]["issue"]
