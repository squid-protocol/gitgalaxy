"""#3784: C++ overloads are chosen by the caller's argument counts, as in Java (#3835). A count that
cannot choose leaves an ambiguous `overload` row, never an edge (libclang judged 220 fmt links the wrong overload)."""

import pytest

from gitgalaxy.core.call_resolver import CONFIDENT_RESOLUTIONS, OVERLOAD_LANGS, resolve_calls


def _fn(name, line, owner=None, args=0, calls=(), quals=None, arities=None):
    f = {
        "name": name,
        "start_line": line,
        "args": args,
        "calls_out_to": list(calls),
        "calls_out_qualifiers": quals or {},
    }
    if owner:
        f["parent_class_name"] = owner
    if arities is not None:
        f["calls_out_arities"] = arities
    return f


def _file(path, functions, lang="cpp"):
    return {"path": path, "lang_id": lang, "functions": functions, "classes": []}


def _repo(caller, lang="cpp"):
    # the caller is a Box member too: a bare call reaches its own class
    box = [_fn("put", 10, "Box", 1), _fn("put", 14, "Box", 2), _fn("put", 18, "Box", 2), _fn("get", 22, "Box", 0)]
    return [_file("src/box.cc", box + [caller], lang)]


def _rows(files, callee="put"):
    return [s for s in resolve_calls(files)[0] if s["callee"] == callee]


def _caller(arities, callee="put"):
    return _fn(
        "run", 3, "Box", calls=[callee], quals={callee: [""]}, arities={callee: arities} if arities is not None else {}
    )


def test_cpp_is_an_overload_language_and_c_is_not():
    assert "cpp" in OVERLOAD_LANGS
    assert "c" not in OVERLOAD_LANGS


def test_the_argument_count_picks_the_one_overload_with_that_many_parameters():
    (row,) = _rows(_repo(_caller([1])))
    assert row["dst_line"] == 10
    assert row["resolution"] in CONFIDENT_RESOLUTIONS


def test_two_counts_are_two_links():
    rows = _rows(_repo(_caller([1, 0])), "put")
    assert [r["dst_line"] for r in rows if r["resolution"] in CONFIDENT_RESOLUTIONS] == [10]
    assert any(r["resolution"] == "ambiguous" for r in rows)  # 0 matches nothing


@pytest.mark.parametrize("arities", [[2], [5], None])
def test_a_count_that_cannot_choose_is_an_ambiguous_overload_row(arities):
    # two overloads take 2 parameters, none takes 5, no recorded count is no evidence
    (row,) = _rows(_repo(_caller(arities)))
    assert (row["step"], row["resolution"]) == ("overload", "ambiguous")


def test_a_single_definition_keeps_its_link_whatever_the_count():
    caller = _fn("run", 3, "Box", calls=["get"], quals={"get": [""]}, arities={"get": [4]})
    (row,) = _rows(_repo(caller), "get")
    assert row["dst_line"] == 22 and row["resolution"] in CONFIDENT_RESOLUTIONS


def test_overloads_in_another_file_are_not_grouped():
    files = [
        _file("src/box.cc", [_fn("put", 10, "Box", 1), _caller([1])]),
        _file("src/other.cc", [_fn("put", 10, "Box", 2)]),
    ]
    assert all(r["step"] != "overload" for r in _rows(files))


def test_c_keeps_one_row_per_callee_whatever_it_records():
    (row,) = _rows(_repo(_caller([2]), lang="c"))
    assert row["step"] != "overload"
