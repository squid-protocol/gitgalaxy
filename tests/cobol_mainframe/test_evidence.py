"""#4048: the evidence records -- one per ported program -- are current, complete, valid, rendered, and approved only
by a person.

Cheap: hashing and JSON, no Docker. tests/tools/evidence.py holds the record; docs/language_status/evidence_records.md
explains it.
"""

import ast
import copy
import json
import sys
import warnings
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import evidence as ev  # noqa: E402

REPO = ev.REPO_ROOT

# Committed ports with no evidence record yet, each with the reason. A ratchet: it only shrinks (an entry whose
# record now exists fails test_the_missing_list_only_shrinks).
MISSING: dict[str, str] = {}


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


def test_the_rendered_pages_are_current():
    pages = ev.rendered()
    stale = [ev.rel_path(p) for p, text in pages.items() if not p.is_file() or p.read_text(encoding="utf-8") != text]
    extra = [ev.rel_path(p) for p in ev.PAGES.glob("*.md") if p not in pages]
    assert not stale and not extra, f"run python tests/tools/evidence.py render: {stale + extra}"


def test_committed_approvals_name_a_person_and_what_they_attest():
    for t, rec in _records():
        for a in (rec or {}).get("approvals", []):
            assert not ev._MODEL_NAMES.search(a["by"]), f"{t.key}: approved by {a['by']!r}"
            assert a["attests"] == ev.ATTESTATION.format(purpose=a["purpose"]), t.key


# ---- only a person writes an approval -----------------------------------------------------------------------------
_TOOLS_WITHOUT_APPROVALS = ("equivalence.py", "equivalence_call.py", "equivalence_cics.py", "cics_crucible.py",
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
    assert where <= _ALLOWED_WRITERS, f"evidence.py writes approvals outside {_ALLOWED_WRITERS}: {where - _ALLOWED_WRITERS}"
    assert "_append_approval" in where


def _dateutil():
    t = ev.target("carddemo-dateutil")
    rec = ev.load(t)
    if rec is None:
        pytest.skip("no carddemo-dateutil record")
    return t, copy.deepcopy(rec)


def _with_unproven(rec):
    """The record with a ported method no proof runs (the generator's executeX that #4342 removed from the port)."""
    unproven = [*rec["reach"]["unproven"],
                {"class": "CsutldtcService", "method": "executeCsutldtc", "line": 30, "kind": "ported_unproven"}]
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
    assert text.startswith("**CSUTLDTC**: byte-identical on **17 calls**")
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
    assert "handleTransaction" not in {m["method"] for m in run["unproven"]} and "handleTransaction" in run["entry_points"]


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
