"""
#3328 / #3329: the repository-wide call resolver (core/call_resolver.py).

Each test builds the minimal parsed-file dicts the resolver reads -- path, lang_id,
functions (name, start_line, parent_class_name, calls_out_to, calls_out_qualifiers)
and classes (name, inheritance) -- plus the import edges, and pins one rung of the
ladder or one qualifier rule.
"""

from gitgalaxy.core.call_resolver import resolve_calls


def _fn(name, line=1, owner=None, calls=(), quals=None, synthetic=False):
    f = {"name": name, "start_line": line, "calls_out_to": list(calls), "calls_out_qualifiers": quals or {}}
    if owner:
        f["parent_class_name"] = owner
    if synthetic:
        f["is_synthetic_slice"] = True
    return f


def _file(path, lang, functions=(), classes=()):
    return {"path": path, "lang_id": lang, "functions": list(functions), "classes": list(classes)}


def _site(sites, callee):
    (row,) = [s for s in sites if s["callee"] == callee]
    return row


def test_same_class_beats_same_file_and_repo():
    files = [
        _file(
            "a.py",
            "python",
            [
                _fn("save", 2, owner="Store"),
                _fn("save", 9),
                _fn("run", 5, owner="Store", calls=["save"], quals={"save": ["self"]}),
            ],
            [{"name": "Store", "inheritance": []}],
        ),
        _file("b.py", "python", [_fn("save", 1)]),
    ]
    sites, _ = resolve_calls(files)
    row = _site(sites, "save")
    assert (row["step"], row["resolution"], row["dst_path"], row["dst_line"]) == ("class", "scoped", "a.py", 2)


def test_inherited_method_resolves_through_the_lineage():
    files = [
        _file("base.py", "python", [_fn("load", 3, owner="Base")], [{"name": "Base", "inheritance": []}]),
        _file(
            "child.py",
            "python",
            [_fn("run", 2, owner="Child", calls=["load"], quals={"load": ["self"]})],
            [{"name": "Child", "inheritance": ["Base"]}],
        ),
    ]
    row = _site(resolve_calls(files)[0], "load")
    assert (row["step"], row["dst_path"]) == ("class", "base.py")


def test_import_edge_scopes_a_module_qualified_call():
    files = [
        _file("app.py", "python", [_fn("main", 1, calls=["parse"], quals={"parse": ["utils"]})]),
        _file("pkg/utils.py", "python", [_fn("parse", 1)]),
        _file("other/utils2.py", "python", [_fn("parse", 1)]),
    ]
    edges = [{"src": "app.py", "dst": "pkg/utils.py", "edge_kind": "import"}]
    row = _site(resolve_calls(files, edges)[0], "parse")
    assert (row["step"], row["resolution"], row["dst_path"]) == ("import", "scoped", "pkg/utils.py")


def test_unique_bare_name_is_a_confident_edge():
    files = [
        _file("a.c", "c", [_fn("main", 1, calls=["helper"], quals={"helper": [""]})]),
        _file("lib/h.c", "c", [_fn("helper", 1)]),
    ]
    row = _site(resolve_calls(files)[0], "helper")
    assert (row["resolution"], row["dst_path"]) == ("unique", "lib/h.c")


def test_bare_call_cannot_reach_another_classes_method():
    files = [
        _file("a.py", "python", [_fn("main", 1, calls=["save"], quals={"save": [""]})]),
        _file("b.py", "python", [_fn("save", 3, owner="Other")], [{"name": "Other", "inheritance": []}]),
    ]
    assert _site(resolve_calls(files)[0], "save")["step"] == "none"


def test_unknown_receiver_is_ambiguous_not_an_edge():
    # `d.get()` on a variable of unknown type: the one repo method named `get`
    # is a guess, kept as a row but never a confident edge.
    files = [
        _file("x/a.py", "python", [_fn("main", 1, calls=["get"], quals={"get": ["d"]})]),
        _file("y/conf.py", "python", [_fn("get", 3, owner="Config")], [{"name": "Config", "inheritance": []}]),
    ]
    sites, stats = resolve_calls(files)
    row = _site(sites, "get")
    assert (row["step"], row["resolution"], row["dst_path"]) == ("receiver", "ambiguous", "y/conf.py")
    assert stats["by_resolution"] == {"ambiguous": 1}


def test_unknown_receiver_in_the_same_directory_is_visible():
    files = [
        _file("pkg/a.java", "java", [_fn("run", 1, owner="A", calls=["save"], quals={"save": ["repo"]})]),
        _file("pkg/Repo.java", "java", [_fn("save", 3, owner="Repo")], [{"name": "Repo", "inheritance": []}]),
    ]
    row = _site(resolve_calls(files)[0], "save")
    assert (row["step"], row["resolution"]) == ("import", "scoped")


def test_class_qualified_static_call():
    files = [
        _file("a.cpp", "cpp", [_fn("main", 1, calls=["make"], quals={"make": ["Store"]})]),
        _file("s.cpp", "cpp", [_fn("Store::make", 3), _fn("make", 9)], [{"name": "Store", "inheritance": []}]),
    ]
    row = _site(resolve_calls(files)[0], "make")
    assert (row["step"], row["dst_name"]) == ("qualified", "Store::make")


def test_constructor_call_resolves_to_the_class():
    files = [
        _file("a.py", "python", [_fn("main", 1, calls=["Store"], quals={"Store": [""]})]),
        _file("s.py", "python", [], [{"name": "Store", "inheritance": []}]),
    ]
    row = _site(resolve_calls(files)[0], "Store")
    assert (row["resolution"], row["dst_kind"]) == ("unique", "class")


def test_equidistant_candidates_are_a_tie_with_no_target():
    files = [
        _file("src/a.c", "c", [_fn("main", 1, calls=["init"], quals={"init": [""]})]),
        _file("x/one.c", "c", [_fn("init", 1)]),
        _file("y/two.c", "c", [_fn("init", 1)]),
    ]
    row = _site(resolve_calls(files)[0], "init")
    assert (row["step"], row["dst_path"], row["candidates"]) == ("tie", None, 2)


def test_nearest_candidate_is_ambiguous_with_a_guess():
    files = [
        _file("src/a.c", "c", [_fn("main", 1, calls=["init"], quals={"init": [""]})]),
        _file("src/sub/one.c", "c", [_fn("init", 1)]),
        _file("far/deep/two.c", "c", [_fn("init", 1)]),
    ]
    row = _site(resolve_calls(files)[0], "init")
    assert (row["step"], row["resolution"], row["dst_path"]) == ("nearest", "ambiguous", "src/sub/one.c")


def test_undefined_name_is_external():
    files = [_file("a.py", "python", [_fn("main", 1, calls=["print"], quals={"print": [""]})])]
    row = _site(resolve_calls(files)[0], "print")
    assert (row["step"], row["resolution"], row["dst_path"]) == ("none", "external", None)


def test_link_groups_keep_languages_apart():
    files = [
        _file("a.py", "python", [_fn("main", 1, calls=["helper"], quals={"helper": [""]})]),
        _file("h.js", "javascript", [_fn("helper", 1)]),
        _file("h.c", "c", [_fn("util", 1)]),
        _file("m.cpp", "cpp", [_fn("run", 1, calls=["util"], quals={"util": [""]})]),
    ]
    sites, _ = resolve_calls(files)
    assert _site(sites, "helper")["resolution"] == "external"
    assert _site(sites, "util")["dst_path"] == "h.c"  # C and C++ link together


def test_case_insensitive_languages_fold_names():
    files = [
        _file("a.cbl", "cobol", [_fn("MAIN-PARA", 1, owner="PROG", calls=["Read-File"])]),
        _file("a2.cbl", "cobol", []),
    ]
    files[0]["functions"].append(_fn("READ-FILE", 9, owner="PROG"))
    row = _site(resolve_calls(files)[0], "Read-File")
    assert (row["step"], row["dst_name"]) == ("class", "READ-FILE")


def test_uncaptured_qualifier_uses_the_plain_ladder():
    # A language without qualifier capture (empty map) keeps every candidate.
    files = [
        _file("a.f90", "fortran", [_fn("main", 1, calls=["solve"])]),
        _file("b.f90", "fortran", [_fn("solve", 1, owner="mod")]),
    ]
    row = _site(resolve_calls(files)[0], "solve")
    assert (row["qualifier"], row["resolution"]) == (None, "unique")


def test_most_confident_qualifier_wins():
    files = [
        _file(
            "a.py",
            "python",
            [
                _fn("save", 2, owner="Store"),
                _fn("run", 5, owner="Store", calls=["save"], quals={"save": ["x", "self"]}),
            ],
            [{"name": "Store", "inheritance": []}],
        )
    ]
    row = _site(resolve_calls(files)[0], "save")
    assert (row["qualifier"], row["step"]) == ("self", "class")


def test_qualified_self_recursion_is_dropped():
    files = [_file("a.cpp", "cpp", [_fn("Foo::bar", 1, calls=["bar"], quals={"bar": [""]})])]
    sites, stats = resolve_calls(files)
    assert sites == [] and stats["by_step"] == {}


def test_synthetic_slices_call_but_are_never_targets():
    files = [
        _file(
            "a.py",
            "python",
            [_fn("<module>", 1, calls=["main"], quals={"main": [""]}, synthetic=True), _fn("main", 3)],
        ),
        _file("b.py", "python", [_fn("x", 1, calls=["<module>"], quals={"<module>": [""]})]),
    ]
    sites, _ = resolve_calls(files)
    assert _site(sites, "main")["src_synthetic"] is True
    assert _site(sites, "<module>")["resolution"] == "external"


def test_stats_group_steps_into_resolutions_per_language():
    files = [
        _file("a.c", "c", [_fn("main", 1, calls=["helper", "printf"], quals={"helper": [""], "printf": [""]})]),
        _file("h.c", "c", [_fn("helper", 1)]),
    ]
    stats = resolve_calls(files)[1]
    assert stats["by_step"] == {"unique": 1, "none": 1}
    assert stats["by_resolution"] == {"unique": 1, "external": 1}
    assert stats["by_language"] == {"c": {"unique": 1, "external": 1}}


def test_qualifier_encoding_round_trips():
    from gitgalaxy.core.call_resolver import decode_qualifiers, encode_qualifiers

    calls = ["parse", "save", "print"]
    quals = {"parse": ["utils"], "save": ["self", ""], "print": [""]}
    encoded = encode_qualifiers(calls, quals)
    assert encoded == ["utils", ["self", ""], ""]
    assert decode_qualifiers(calls, encoded) == quals
    assert encode_qualifiers(calls, {}) is None
    assert decode_qualifiers(calls, None) == {}
    assert decode_qualifiers(calls, ["a"]) == {}  # misaligned -> not captured


def test_resolution_rates_rows_per_language_and_repo():
    from gitgalaxy.core.call_resolver import resolution_rates

    stats = {"by_language": {"c": {"unique": 2, "external": 1}, "python": {"scoped": 1}, "go": {}}}
    assert resolution_rates(stats) == [
        {"language": "*", "scoped": 1, "unique": 2, "ambiguous": 0, "external": 1, "total": 4},
        {"language": "c", "scoped": 0, "unique": 2, "ambiguous": 0, "external": 1, "total": 3},
        {"language": "python", "scoped": 1, "unique": 0, "ambiguous": 0, "external": 0, "total": 1},
    ]
    assert resolution_rates({}) == []


def test_shared_class_name_prefers_the_callers_own_file():
    # #3332 found it: zopeneditor's SAM1.cbl and SAM1LIB.cbl both declare
    # PROGRAM-ID SAM1, and SAM1LIB's own PERFORMs landed in SAM1.cbl.
    files = [
        _file("COBOL/SAM1.cbl", "cobol", [_fn("READ-FILE", 5, owner="SAM1")]),
        _file(
            "COBOL/SAM1LIB.cbl",
            "cobol",
            [_fn("MAIN", 1, owner="SAM1", calls=["READ-FILE"]), _fn("READ-FILE", 9, owner="SAM1")],
        ),
    ]
    row = _site(resolve_calls(files)[0], "READ-FILE")
    assert (row["step"], row["dst_path"], row["dst_line"]) == ("class", "COBOL/SAM1LIB.cbl", 9)


def test_untyped_receiver_with_several_visible_classes_is_ambiguous():
    # #3332: `self.body.generate()` where the caller's own file defines `generate`
    # on two classes -- the receiver's type decides, and the engine cannot know it.
    files = [
        _file(
            "nodes.py",
            "python",
            [
                _fn("generate", 3, owner="A"),
                _fn("generate", 9, owner="B"),
                _fn("run", 20, owner="C", calls=["generate"], quals={"generate": ["self.body"]}),
            ],
            [{"name": n, "inheritance": []} for n in "ABC"],
        )
    ]
    row = _site(resolve_calls(files)[0], "generate")
    assert (row["step"], row["resolution"]) == ("receiver", "ambiguous")
