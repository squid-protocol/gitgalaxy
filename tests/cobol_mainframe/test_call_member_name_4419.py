"""#4419: when several members declare the same PROGRAM-ID (an old fork still saying the
original name), a CALL / CICS LINK / XCTL / JCL EXEC PGM resolves to the member NAMED for
the target; with no such member the nearest declarer is kept and the ambiguity reported."""

import pytest

from gitgalaxy.core.invocation_resolver import resolve_invocations, resolve_transactions


def _prog(path, pid, calls=()):
    return {"path": path, "lang_id": "cobol", "classes": [{"name": pid}], "call_sites": list(calls)}


def _site(verb, target):
    return {"verb": verb, "form": "literal", "operand": target, "target": target, "line": 10}


# the fork sits NEXT TO the caller, the live member one directory away: proximity alone picks the fork
LIVE = "apps/ORDR/cobol/ORDVAL.cbl"
FORK = "apps/ORDR/cobol/main/ORDV#OLD.cbl"


@pytest.mark.parametrize("verb", ["CALL", "LINK", "XCTL"])
def test_member_named_for_target_beats_a_fork_with_the_same_program_id(verb):
    files = [
        _prog("apps/ORDR/cobol/main/ORDMAIN.cbl", "ORDMAIN", [_site(verb, "ORDVAL")]),
        _prog(FORK, "ORDVAL"),
        _prog(LIVE, "ORDVAL"),
    ]
    amb: list = []
    sites, edges = resolve_invocations(files, amb)
    assert sites[0]["resolved_path"] == LIVE
    assert [e["dst"] for e in edges] == [LIVE]
    assert amb == []


def test_jcl_exec_pgm_prefers_the_member_named_for_the_program():
    jcl = {"path": "jcl/ORDJOB.jcl", "lang_id": "jcl", "call_sites": [_site("EXEC PGM", "ORDVAL")]}
    files = [jcl, _prog("jcl/ORDV#OLD.cbl", "ORDVAL"), _prog(LIVE, "ORDVAL")]
    sites, edges = resolve_invocations(files)
    assert sites[0]["resolved_path"] == LIVE
    assert edges[0]["edge_kind"] == "exec"


def test_no_member_named_for_target_keeps_nearest_and_reports_ambiguity():
    files = [
        _prog("a/b/MAIN.cbl", "MAIN", [_site("CALL", "ORDVAL")]),
        _prog("a/b/ORDV#OLD.cbl", "ORDVAL"),
        _prog("z/ORDVAL2.cbl", "ORDVAL"),
    ]
    amb: list = []
    sites, _ = resolve_invocations(files, amb)
    assert sites[0]["resolved_path"] == "a/b/ORDV#OLD.cbl"  # today's rule
    assert amb == [
        {
            "src_path": "a/b/MAIN.cbl",
            "target": "ORDVAL",
            "chosen": "a/b/ORDV#OLD.cbl",
            "candidates": ["a/b/ORDV#OLD.cbl", "z/ORDVAL2.cbl"],
        }
    ]


def test_single_declarer_is_never_ambiguous_even_when_the_member_is_named_differently():
    files = [_prog("m/MAIN.cbl", "MAIN", [_site("CALL", "ORDVAL")]), _prog("m/ORDV2.cbl", "ORDVAL")]
    amb: list = []
    sites, _ = resolve_invocations(files, amb)
    assert sites[0]["resolved_path"] == "m/ORDV2.cbl"
    assert amb == []


def test_member_name_match_is_case_insensitive_and_ignores_extension():
    files = [
        _prog("x/MAIN.cbl", "MAIN", [_site("CALL", "ordval")]),
        _prog("x/y/OLDV.cbl", "ORDVAL"),
        _prog("q/ordval.cob", "ORDVAL"),
    ]
    sites, _ = resolve_invocations(files)
    assert sites[0]["resolved_path"] == "q/ordval.cob"


def test_csd_transaction_program_uses_the_same_preference():
    csd = {
        "path": "csd/APP.csd",
        "lang_id": "csd",
        "transaction_defs": [{"transid": "ORD1", "program": "ORDVAL", "line": 1}],
    }
    files = [csd, _prog("csd/ORDV#OLD.cbl", "ORDVAL"), _prog(LIVE, "ORDVAL")]
    assert resolve_transactions(files)[0]["resolved_path"] == LIVE
