"""
#3313 step 3: the idiom-wrapper resolver's decision rules, each pinned on the
shape that measured it (tests/tools/wrapper_probe.py, wrapper_labels.json):

  - fortran/wrf's `wrf_error_fatal` (print + stop) wraps TWO rules.
  - The no-branch filter applies to debug_prints/panics_and_aborts, NOT to
    memory_alloc: allocator wrappers guard size/NULL (CPython `PyMem_Malloc`).
  - A method never receives an unqualified call (go/core `lock`).
  - Same-file definition wins; several definitions from a third file credit
    nothing; a misaligned engine span is not a candidate.
  - The closure crosses kinds both ways: curl's `Curl_safefree` macro via the
    `curlx_free` macro, and curl 8.18's public `curl_free` FUNCTION via it.
"""

from gitgalaxy.core.wrapper_resolver import RULE_FILTERS, RULE_SCOPE, attach_wrappers, resolve_wrappers


def _cand(name, hits=(), callees=(), loc=5, branches=0, aligned=True, method=False):
    return {
        "name": name,
        "loc": loc,
        "branches": branches,
        "aligned": aligned,
        "method": method,
        "hits": list(hits),
        "callees": list(callees),
    }


def _file(path, defined=(), candidates=(), calls=None, macros=(), lang="c"):
    return {
        "path": path,
        "lang_id": lang,
        "wrapper_facts": {
            "defined": {n: 1 for n in defined} if not isinstance(defined, dict) else dict(defined),
            "candidates": list(candidates),
            "calls": dict(calls or {}),
            "macros": list(macros),
        },
    }


def _rows(files):
    return {(r["name"], r["rule"]): r for r in resolve_wrappers(files)}


def test_a_print_and_stop_helper_wraps_both_rules():
    files = [
        _file("wrapper.F", ["wrf_error_fatal"], [_cand("wrf_error_fatal", ["debug_prints", "panics_and_aborts"])]),
        _file("caller.F", ["init_domain"], calls={"wrf_error_fatal": 3}),
    ]
    rows = _rows(files)
    for rule in ("debug_prints", "panics_and_aborts"):
        row = rows[("wrf_error_fatal", rule)]
        assert (row["path"], row["kind"], row["via"], row["call_sites"], row["calling_files"]) == (
            "wrapper.F",
            "function",
            "primitive",
            3,
            1,
        )


def test_the_no_branch_filter_is_per_rule():
    """A branching print helper is a check-and-print, not a wrapper; a branching
    allocator IS a wrapper (every real one guards size or NULL)."""
    assert RULE_FILTERS["debug_prints"][1] and not RULE_FILTERS["memory_alloc"][1]
    assert RULE_SCOPE["memory_alloc"][2] == frozenset({"c", "cpp", "objective-c"})
    files = [
        _file("log.c", ["warn_if"], [_cand("warn_if", ["debug_prints"], branches=1)]),
        _file("mem.c", ["xmalloc"], [_cand("xmalloc", ["memory_alloc"], branches=1)]),
        _file("user.c", ["main"], calls={"warn_if": 2, "xmalloc": 4}),
    ]
    rows = _rows(files)
    assert ("warn_if", "debug_prints") not in rows
    assert rows[("xmalloc", "memory_alloc")]["call_sites"] == 4


def test_loc_cutoffs_are_per_rule():
    files = [
        _file(
            "a.c",
            ["long_log", "long_alloc"],
            [
                _cand("long_log", ["debug_prints"], loc=10),
                _cand("long_alloc", ["memory_alloc"], loc=10),
            ],
        ),
        _file("b.c", ["main"], calls={"long_log": 1, "long_alloc": 1}),
    ]
    rows = _rows(files)
    assert ("long_log", "debug_prints") not in rows, "over debug_prints' 8-LOC cutoff"
    assert ("long_alloc", "memory_alloc") in rows, "within memory_alloc's 12-LOC cutoff"


def test_methods_and_misaligned_spans_are_never_wrappers():
    files = [
        _file("server.go", ["lock"], [_cand("lock", ["debug_prints"], method=True)], lang="go"),
        _file("odd.lua", ["foo"], [_cand("foo", ["debug_prints"], aligned=False)], lang="lua"),
        _file("proc.go", ["park"], calls={"lock": 106, "foo": 2}, lang="go"),
    ]
    assert _rows(files) == {}


def test_same_file_wins_and_an_ambiguous_name_credits_nothing():
    files = [
        _file("a.py", ["log_it"], [_cand("log_it", ["debug_prints"])]),
        _file("b.py", ["log_it", "local_caller"], [_cand("log_it", ["debug_prints"])], calls={"log_it": 1}),
        _file("c.py", ["elsewhere"], calls={"log_it": 5}),
    ]
    rows = resolve_wrappers(files)
    assert [(r["path"], r["call_sites"]) for r in rows] == [("b.py", 1)], "c.py's 5 calls are ambiguous"


def test_the_closure_crosses_macros_and_functions():
    """curl 8.18: the allocator layer is macros, `Curl_safefree` chains through
    one, and the public `curl_free` FUNCTION now calls a macro, not free()."""
    files = [
        _file(
            "curl_setup.h",
            macros=[
                {"name": "curlx_free", "hits": ["memory_alloc"], "called": ["free"]},
                {"name": "Curl_safefree", "hits": [], "called": ["curlx_free"]},
            ],
        ),
        _file("escape.c", ["curl_free"], [_cand("curl_free", callees=["curlx_free"])], calls={"curlx_free": 1}),
        _file("url.c", ["cleanup"], calls={"Curl_safefree": 7, "curl_free": 3}),
    ]
    rows = _rows(files)
    assert (rows[("curlx_free", "memory_alloc")]["kind"], rows[("curlx_free", "memory_alloc")]["call_sites"]) == (
        "macro",
        1,
    )
    assert rows[("Curl_safefree", "memory_alloc")]["via"] == "via curlx_free"
    assert rows[("Curl_safefree", "memory_alloc")]["call_sites"] == 7
    assert (rows[("curl_free", "memory_alloc")]["kind"], rows[("curl_free", "memory_alloc")]["via"]) == (
        "function",
        "via curlx_free",
    )


def test_an_uncalled_wrapper_hides_nothing_and_is_not_recorded():
    files = [_file("log.c", ["say"], [_cand("say", ["debug_prints"])])]
    assert resolve_wrappers(files) == []


def test_the_output_does_not_depend_on_scan_order():
    files = [
        _file("wrapper.F", ["wrf_error_fatal"], [_cand("wrf_error_fatal", ["debug_prints"])]),
        _file("a.F", ["a"], calls={"wrf_error_fatal": 1}),
        _file("b.F", ["b"], calls={"wrf_error_fatal": 2}),
    ]
    assert resolve_wrappers(files) == resolve_wrappers(list(reversed(files)))


def test_attach_hangs_rows_on_the_defining_file_only():
    files = [
        _file("wrapper.F", ["wrf_error_fatal"], [_cand("wrf_error_fatal", ["debug_prints"])]),
        _file("caller.F", ["init"], calls={"wrf_error_fatal": 1}),
    ]
    attach_wrappers(files, resolve_wrappers(files))
    assert [w["name"] for w in files[0]["idiom_wrappers"]] == ["wrf_error_fatal"]
    assert "idiom_wrappers" not in files[1]


def test_files_without_facts_are_ignored():
    assert resolve_wrappers([{"path": "x.py"}, {"path": "y.py", "wrapper_facts": None}]) == []


def test_memory_alloc_is_scoped_to_the_c_preprocessor_family():
    """Step 2 measured allocator wrappers in C only. A JS `new`/Go `make` hit is a
    different vocabulary, so a same-shaped function there is not recorded."""
    files = [
        _file("buf.js", ["makeBuf"], [_cand("makeBuf", ["memory_alloc"])], lang="javascript"),
        _file("use.js", ["main"], calls={"makeBuf": 9}, lang="javascript"),
    ]
    assert resolve_wrappers(files) == []


def test_print_and_abort_rules_have_no_closure():
    """A function that only CALLS a print wrapper is not itself one: closure
    through debug_prints/panics_and_aborts was never measured."""
    files = [
        _file("log.py", ["say"], [_cand("say", ["debug_prints"])], lang="python"),
        _file("mid.py", ["relay"], [_cand("relay", callees=["say"])], calls={"say": 1}, lang="python"),
        _file("use.py", ["main"], calls={"relay": 4}, lang="python"),
    ]
    assert [(r["name"], r["call_sites"]) for r in resolve_wrappers(files)] == [("say", 1)]


def test_a_closure_edge_resolves_like_a_call_site():
    """`relay` calls `free_it`, but two files define `free_it` and neither is
    relay's: the edge is ambiguous, so relay does not inherit wrapper status."""
    files = [
        _file("a.c", ["free_it"], [_cand("free_it", ["memory_alloc"])], calls={}),
        _file("b.c", ["free_it"], [_cand("free_it")], calls={}),
        _file("c.c", ["relay"], [_cand("relay", callees=["free_it"])], calls={}),
        _file("d.c", ["main"], calls={"relay": 5}),
    ]
    assert ("relay", "memory_alloc") not in _rows(files)


def test_a_name_defined_twice_in_the_callers_own_file_is_ambiguous():
    """CPython's Lib/test: many nested `def f(): raise ...` in one file. A bare
    `f(` there could be any of them, so none is credited."""
    files = [_file("test_x.py", {"f": 10}, [_cand("f", ["panics_and_aborts"])], calls={"f": 93}, lang="python")]
    assert resolve_wrappers(files) == []


def test_memory_alloc_precision_reproduces_from_the_committed_labels():
    """#3313 step 3's allocator label pass (tests/tools/wrapper_labels_memory_alloc.json):
    46 engine-recorded memory_alloc wrappers from curl 8.18, CPython 3.14 and the
    crucible, hand-read. The claim in the PR -- 92% of recorded call sites go
    through a real allocator alias, 99% counting destructors -- re-scored here so
    it cannot drift from the data."""
    import json
    from pathlib import Path

    doc = json.loads(
        (Path(__file__).resolve().parents[1] / "tools" / "wrapper_labels_memory_alloc.json").read_text(encoding="utf-8")
    )
    labels = list(doc["labels"].values())
    assert len(labels) >= 40
    total = sum(e["call_sites"] for e in labels)
    strict = sum(e["call_sites"] for e in labels if e["label"] == "wrapper") / total
    lenient = sum(e["call_sites"] for e in labels if e["label"] in ("wrapper", "destructor")) / total
    assert strict >= 0.9
    assert lenient >= 0.98
    assert {e["label"] for e in labels} <= {"wrapper", "destructor", "incidental"}
