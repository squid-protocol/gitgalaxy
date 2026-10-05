"""#4447: a CALL to a program declared later in the SAME source member (plain or literal
PROGRAM-ID) resolves to that member. Before, the caller's own file was dropped as
"recursion", so every sibling call resolved to nothing. The pair still draws no edge."""

from gitgalaxy.core.invocation_resolver import resolve_invocations


def _site(target, line=10):
    return {"verb": "CALL", "form": "literal", "operand": target, "target": target, "line": line}


def _member(path, pids, calls=()):
    return {"path": path, "lang_id": "cobol", "classes": [{"name": p} for p in pids], "call_sites": list(calls)}


def test_plain_and_literal_siblings_resolve_to_their_member_without_an_edge():
    m = "apps/PAYR/cobol/PAYMAIN.cbl"
    sites, edges = resolve_invocations([_member(m, ["PAYMAIN", "PAYCALC", "PAYRPT"], [_site("PAYCALC"), _site("PAYRPT")])])
    assert [s["resolved_path"] for s in sites] == [m, m]
    assert edges == []


def test_single_program_self_call_is_still_recursion():
    m = "a/ONE.cbl"
    sites, edges = resolve_invocations([_member(m, ["ONE"], [_site("ONE")])])
    assert sites[0]["resolved_path"] is None and edges == []


def test_sibling_call_does_not_hide_calls_to_other_members_and_keeps_4419_preference():
    m, live, fork = "a/MAIN.cbl", "a/ORDVAL.cbl", "a/main/ORDV#OLD.cbl"
    files = [
        _member(m, ["MAIN", "SIB"], [_site("ORDVAL"), _site("SIB")]),
        _member(fork, ["ORDVAL"]),
        _member(live, ["ORDVAL"]),
    ]
    sites, edges = resolve_invocations(files)
    assert [s["resolved_path"] for s in sites] == [live, m]
    assert [(e["src"], e["dst"]) for e in edges] == [(m, live)]
