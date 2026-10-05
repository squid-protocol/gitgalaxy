"""#4419: when several members declare one PROGRAM-ID, the member named for the call
target wins; with none, the nearest declarer is kept and the guess is reported."""

from gitgalaxy.core.invocation_resolver import resolve_invocations


def _prog(path, pid, calls=()):
    return {
        "path": path,
        "lang_id": "cobol",
        "classes": [{"name": pid}],
        "call_sites": [{"verb": v, "target": t, "line": 1} for v, t in calls],
    }


def _resolve(files):
    amb: list = []
    sites, _ = resolve_invocations(files, amb)
    return {(s["verb"], s["target"]): s["resolved_path"] for s in sites}, amb


def test_member_named_for_target_beats_a_fork_that_is_nearer():
    files = [
        _prog("apps/ORDR/cobol/ORDMAIN.cbl", "ORDMAIN", [("CALL", "ORDVAL"), ("LINK", "ORDVAL"), ("XCTL", "ORDVAL")]),
        # alphabetically first and in the caller's own directory, but a dead fork
        _prog("apps/ORDR/cobol/ORDV#OLD.cbl", "ORDVAL"),
        _prog("apps/ORDR/cobol/ORDVAL.cbl", "ORDVAL"),
        _prog("apps/ORDR/ORDVAL.cbl", "ORDVAL"),
    ]
    resolved, amb = _resolve(files)
    for verb in ("CALL", "LINK", "XCTL"):
        assert resolved[(verb, "ORDVAL")] == "apps/ORDR/cobol/ORDVAL.cbl"
    assert amb == []


def test_jcl_exec_pgm_prefers_the_named_member():
    files = [
        {"path": "jcl/RUN.jcl", "lang_id": "jcl", "call_sites": [{"verb": "EXEC PGM", "target": "ORDVAL", "line": 1}]},
        _prog("jcl/ORDV#OLD.cbl", "ORDVAL"),
        _prog("src/ORDVAL.cbl", "ORDVAL"),
    ]
    resolved, _ = _resolve(files)
    assert resolved[("EXEC PGM", "ORDVAL")] == "src/ORDVAL.cbl"


def test_no_matching_member_keeps_nearest_and_reports_ambiguity():
    files = [
        _prog("a/MAIN.cbl", "MAIN", [("CALL", "SHARED")]),
        _prog("a/FORK1.cbl", "SHARED"),
        _prog("z/FORK2.cbl", "SHARED"),
    ]
    resolved, amb = _resolve(files)
    assert resolved[("CALL", "SHARED")] == "a/FORK1.cbl"
    assert amb == [
        {
            "src_path": "a/MAIN.cbl",
            "target": "SHARED",
            "chosen": "a/FORK1.cbl",
            "candidates": ["a/FORK1.cbl", "z/FORK2.cbl"],
        }
    ]


def test_unique_declarer_is_not_ambiguous():
    files = [_prog("a/MAIN.cbl", "MAIN", [("CALL", "SUB")]), _prog("a/SUBX.cbl", "SUB")]
    resolved, amb = _resolve(files)
    assert resolved[("CALL", "SUB")] == "a/SUBX.cbl" and amb == []
