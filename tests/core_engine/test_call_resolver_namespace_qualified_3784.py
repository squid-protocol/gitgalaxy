"""#3784: `fmt::format(x)` named no class, so the import-stem step landed on a same-name MEMBER
(`formatter<T>::format`) of an imported file. A namespace qualifier reaches free functions."""

import pytest

from gitgalaxy.core.call_resolver import resolve_calls


def _fn(name, line, calls=(), qualifier=""):
    return {
        "name": name,
        "start_line": line,
        "calls_out_to": list(calls),
        "calls_out_qualifiers": {c: [qualifier] for c in calls},
    }


def _edges(files, edges=None, lang="cpp"):
    parsed = [{"path": p, "lang_id": lang, "functions": fns, "classes": []} for p, fns in files.items()]
    imports = [{"src": s, "dst": t} for s, t in (edges or [])]
    sites, _ = resolve_calls(parsed, imports)
    return [(s["src_name"], s["dst_name"], s["dst_path"], s["step"]) for s in sites if s["dst_name"]]


def _files(member_path, free_path, qualifier="::fmt"):
    return {
        "test/a.cc": [_fn("t", 1, ["format"], qualifier)],
        member_path: [_fn("formatter::format", 1)],
        free_path: [_fn("format", 1)],
    }


@pytest.mark.parametrize("member_path", ["include/fmt/chrono.h", "include/fmt/ranges.h", "include/fmt/xchar.h"])
def test_namespace_qualified_call_prefers_the_free_function_over_an_imported_member(member_path):
    files = _files(member_path, "include/fmt/format.h")
    imports = [("test/a.cc", member_path), ("test/a.cc", "include/fmt/format.h")]
    (edge,) = _edges(files, imports)
    assert edge[2] == "include/fmt/format.h"


def test_class_qualified_call_still_reaches_the_member():
    files = {
        "test/a.cc": [_fn("t", 1, ["format"], "::formatter")],
        "include/fmt/chrono.h": [_fn("formatter::format", 1)],
        "include/fmt/format.h": [_fn("format", 1)],
    }
    imports = [("test/a.cc", "include/fmt/chrono.h"), ("test/a.cc", "include/fmt/format.h")]
    (edge,) = _edges(files, imports)
    assert (edge[2], edge[3]) == ("include/fmt/chrono.h", "qualified")


def test_module_qualified_call_in_another_language_still_reaches_a_member_by_import_stem():
    files = {
        "a.py": [_fn("t", 1, ["format"], "fmt")],
        "fmt.py": [_fn("Formatter.format", 1)],
    }
    (edge,) = _edges(files, [("a.py", "fmt.py")], lang="python")
    assert (edge[2], edge[3]) == ("fmt.py", "import")


def _cpp(caller_fns, others, edges=()):
    return _edges({"src/a.cc": caller_fns, **others}, list(edges))


def test_marked_namespace_call_beats_a_same_file_member():
    files = {
        "src/a.cc": [_fn("t", 1, ["format"], "::fmt"), _fn("Logger::format", 5)],
        "include/fmt/format.h": [_fn("format", 1)],
    }
    (edge,) = _edges(files, [("src/a.cc", "include/fmt/format.h")])
    assert edge[2] == "include/fmt/format.h"


def test_marked_namespace_call_uses_the_file_step_for_a_free_function_in_the_same_file():
    files = {"src/a.cc": [_fn("t", 1, ["format"], "::fmt"), _fn("format", 5), _fn("Logger::format", 9)]}
    (edge,) = _edges(files)
    assert (edge[1], edge[3]) == ("format", "file")


def test_global_scope_call_reaches_a_free_function_not_the_callers_member():
    files = {
        "src/a.cc": [_fn("Logger::t", 1, ["f"], "::"), _fn("Logger::f", 5)],
        "src/b.cc": [_fn("f", 1)],
    }
    (edge,) = _edges(files, [("src/a.cc", "src/b.cc")])
    assert edge[2] == "src/b.cc"


def test_marked_call_never_reaches_a_free_function_the_caller_cannot_see():
    files = {"src/a.cc": [_fn("t", 1, ["move"], "::std")], "lib/b.cc": [_fn("move", 1)]}
    assert _edges(files) == []


def test_marked_namespace_call_without_a_free_definition_falls_back_to_the_method_ladder():
    files = {"src/a.cc": [_fn("t", 1, ["make"], "::util"), _fn("Pool::make", 5)]}
    (edge,) = _edges(files)
    assert edge[0:2] == ("t", "Pool::make")


def test_unmarked_receiver_call_still_reaches_a_member_by_import_stem():
    files = _files("include/fmt/chrono.h", "include/fmt/format.h", qualifier="fmt")
    imports = [("test/a.cc", "include/fmt/chrono.h"), ("test/a.cc", "include/fmt/format.h")]
    (edge,) = _edges(files, imports)
    assert edge[2] == "include/fmt/chrono.h"
