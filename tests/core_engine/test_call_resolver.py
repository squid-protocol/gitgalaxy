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
        _file("a.cpp", "cpp", [_fn("main", 1, calls=["Store"], quals={"Store": [""]})]),
        _file("s.cpp", "cpp", [], [{"name": "Store", "inheritance": []}]),
    ]
    row = _site(resolve_calls(files)[0], "Store")
    assert (row["resolution"], row["dst_kind"]) == ("unique", "class")


# #3443: in a package-scoped language a bare call sees only its own module, what
# it imports, and (directory-namespaced languages) its own directory. The one
# definition elsewhere is a guess, not a `unique` edge.


def test_package_scoped_bare_call_to_an_unimported_definition_is_unseen():
    files = [
        _file("bugzilla/Bug.pm", "perl", [_fn("set_all", 1, calls=["remove"], quals={"remove": [""]})]),
        _file("mojo/IOLoop.pm", "perl", [_fn("remove", 3)]),
    ]
    sites, stats = resolve_calls(files)
    row = _site(sites, "remove")
    assert (row["step"], row["resolution"], row["dst_path"]) == ("unseen", "ambiguous", "mojo/IOLoop.pm")
    assert stats["by_resolution"] == {"ambiguous": 1}


def test_package_scoped_constructor_needs_the_class_to_be_visible():
    files = [
        _file("a.py", "python", [_fn("main", 1, calls=["Store"], quals={"Store": [""]})]),
        _file("s.py", "python", [], [{"name": "Store", "inheritance": []}]),
    ]
    row = _site(resolve_calls(files)[0], "Store")
    assert (row["step"], row["dst_kind"]) == ("unseen", "class")
    edges = [{"src": "a.py", "dst": "s.py", "edge_kind": "import"}]
    row = _site(resolve_calls(files, edges)[0], "Store")
    assert (row["step"], row["resolution"]) == ("import", "scoped")


def test_package_directory_keeps_a_same_directory_definition_unique():
    files = [
        _file("pkg/a.go", "go", [_fn("run", 1, calls=["helper", "reset"], quals={"helper": [""], "reset": [""]})]),
        _file("pkg/b.go", "go", [_fn("helper", 3)]),
        _file("other/proc.go", "go", [_fn("reset", 3)]),
    ]
    sites, _ = resolve_calls(files)
    assert (_site(sites, "helper")["step"], _site(sites, "helper")["dst_path"]) == ("unique", "pkg/b.go")
    assert (_site(sites, "reset")["step"], _site(sites, "reset")["dst_path"]) == ("unseen", "other/proc.go")


def test_unseen_is_only_for_a_bare_call():
    # an uncaptured qualifier (None) could be `Pkg::name(...)`: the plain ladder
    files = [
        _file("a.pl", "perl", [_fn("main", 1, calls=["helper"])]),
        _file("lib/H.pm", "perl", [_fn("helper", 3)]),
    ]
    assert _site(resolve_calls(files)[0], "helper")["step"] == "unique"


def test_unseen_pairs_never_join_the_file_graph():
    from gitgalaxy.core.call_resolver import confident_file_pairs

    files = [
        _file("fp-ts/TaskEither.ts", "typescript", [_fn("_alt", 1, calls=["pipe"], quals={"pipe": [""]})]),
        _file("jquery/deferred.js", "javascript", [_fn("pipe", 3)]),
    ]
    sites, _ = resolve_calls(files)
    assert _site(sites, "pipe")["step"] == "unseen"
    assert confident_file_pairs(sites) == {}


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


def test_same_directory_visibility_is_for_package_scoped_languages_only():
    # #3333: a Java sibling class is in the caller's package; a Python sibling
    # module is not visible until imported.
    def files(lang, ext):
        return [
            _file(f"pkg/a.{ext}", lang, [_fn("run", 1, owner="A", calls=["save"], quals={"save": ["repo"]})]),
            _file(f"pkg/repo.{ext}", lang, [_fn("save", 3, owner="Repo")], [{"name": "Repo", "inheritance": []}]),
        ]

    assert _site(resolve_calls(files("java", "java"))[0], "save")["step"] == "import"
    assert _site(resolve_calls(files("python", "py"))[0], "save")["step"] == "receiver"


def test_transfers_resolve_as_their_own_kind_outside_the_rates():
    # #3362: COBOL GO TO targets are linked like calls but are not calls.
    main = _fn("MAIN-PARA", 1, owner="P", calls=["SUB-PARA"])
    main["transfers_to"] = ["EXIT-PARA"]
    files = [_file("p.cbl", "cobol", [main, _fn("SUB-PARA", 5, owner="P"), _fn("EXIT-PARA", 9, owner="P")])]
    sites, stats = resolve_calls(files)
    assert {(s["callee"], s["kind"], s["step"]) for s in sites} == {
        ("SUB-PARA", "call", "class"),
        ("EXIT-PARA", "transfer", "class"),
    }
    assert stats["by_step"] == {"class": 1}
    assert stats["transfers_by_step"] == {"class": 1}


def test_transfers_never_become_file_edges():
    from gitgalaxy.core.call_resolver import confident_file_pairs

    sites = [
        {"src_path": "a.cbl", "dst_path": "b.cbl", "resolution": "unique", "kind": "transfer"},
        {"src_path": "a.cbl", "dst_path": "b.cbl", "resolution": "unique", "kind": "call"},
    ]
    assert confident_file_pairs(sites) == {("a.cbl", "b.cbl"): 1}


def test_bare_perl_builtin_never_links_to_a_same_named_sub():
    """#3401: Mojo's Promise.pm defines `sub map`; every bare `map(` in bugzilla
    and spamassassin resolved `unique` to it. A Perl bare call to a built-in is
    the built-in, even in the defining file."""
    files = [
        _file("bugzilla/Bug.pm", "perl", [_fn("run", 1, calls=["map"], quals={"map": [""]})]),
        _file(
            "mojo/Promise.pm",
            "perl",
            [_fn("map", 68), _fn("then", 90, calls=["map"], quals={"map": [""]})],
        ),
    ]
    sites, _ = resolve_calls(files)
    rows = [s for s in sites if s["callee"] == "map"]
    assert rows and all((r["step"], r["resolution"], r["dst_path"]) == ("none", "external", None) for r in rows)


def test_a_redefinable_name_still_resolves():
    """A language whose definitions CAN shadow a built-in keeps the edge: redis's
    global `function printf` in printf.lua is what a bare `printf(` calls."""
    files = [
        _file("redis/a.lua", "lua", [_fn("run", 1, calls=["printf"], quals={"printf": [""]})]),
        _file("redis/printf.lua", "lua", [_fn("printf", 1)]),
    ]
    row = _site(resolve_calls(files)[0], "printf")
    assert (row["resolution"], row["dst_path"]) == ("unique", "redis/printf.lua")


# ----------------------------------------------------------------------------- constructors


def _ctor_site(files, callee):
    row = _site(resolve_calls(files)[0], callee)
    return row["dst_kind"], row["dst_name"], row["dst_path"], row["dst_class_name"]


def test_python_constructor_call_links_init():
    files = [
        _file("m.py", "python", [_fn("__init__", 3, owner="Store"), _fn("run", 9, calls=["Store"], quals={"Store": [""]})],
              [{"name": "Store", "inheritance": [], "start_line": 1}]),
    ]  # fmt: skip
    assert _ctor_site(files, "Store") == ("function", "__init__", "m.py", "Store")


def test_class_without_its_own_constructor_stays_the_class():
    files = [
        _file("m.py", "python", [_fn("run", 9, calls=["Plain"], quals={"Plain": [""]})],
              [{"name": "Plain", "inheritance": [], "start_line": 1}]),
    ]  # fmt: skip
    assert _ctor_site(files, "Plain") == ("class", "Plain", "m.py", None)


def test_typescript_constructor_and_java_class_named_constructor():
    ts = [
        _file("a.ts", "typescript", [_fn("constructor", 2, owner="Box"), _fn("main", 8, calls=["Box"], quals={"Box": [""]})],
              [{"name": "Box", "inheritance": [], "start_line": 1}]),
    ]  # fmt: skip
    assert _ctor_site(ts, "Box") == ("function", "constructor", "a.ts", "Box")
    java = [
        _file("Box.java", "java", [_fn("Box", 3, owner="Box")], [{"name": "Box", "inheritance": [], "start_line": 1}]),
        _file("Main.java", "java", [_fn("main", 2, calls=["Box"], quals={"Box": [""]})]),
    ]
    assert _ctor_site(java, "Box") == ("function", "Box", "Box.java", "Box")


def test_cpp_out_of_class_constructor_beside_its_header():
    files = [
        _file("src/foo.h", "cpp", [], [{"name": "Foo", "inheritance": [], "start_line": 1}]),
        _file("src/foo.cpp", "cpp", [_fn("Foo::Foo", 4)]),
        _file("src/main.cpp", "cpp", [_fn("main", 1, calls=["Foo"], quals={"Foo": [""]})]),
    ]
    assert _ctor_site(files, "Foo") == ("function", "Foo::Foo", "src/foo.cpp", "Foo")


def test_constructor_inside_itself_is_not_an_edge():
    # `Foo()` written inside Foo's own constructor would link the constructor to itself: dropped.
    files = [
        _file("m.py", "python", [_fn("__init__", 3, owner="Foo", calls=["Foo"], quals={"Foo": [""]})],
              [{"name": "Foo", "inheritance": [], "start_line": 1}]),
    ]  # fmt: skip
    assert [s for s in resolve_calls(files)[0] if s["callee"] == "Foo"] == []


def test_a_same_named_class_elsewhere_does_not_lend_its_constructor():
    # fastapi: tests/test_read_with_orm_mode.py's own `Person` (no __init__) must not reach
    # tests/test_jsonable_encoder.py's `Person.__init__`.
    files = [
        _file("a.py", "python", [_fn("__init__", 3, owner="Person")], [{"name": "Person", "inheritance": [], "start_line": 1}]),
        _file("b.py", "python", [_fn("run", 9, calls=["Person"], quals={"Person": [""]})],
              [{"name": "Person", "inheritance": [], "start_line": 1}]),
    ]  # fmt: skip
    assert _ctor_site(files, "Person") == ("class", "Person", "b.py", None)


# ----------------------------------------------------------------------------- re-exports


def _reexport_files(barrel="pkg/__init__.py"):
    # `from pkg import Depends` lands on the barrel, which re-exports it from pkg/params.py;
    # a same-named function elsewhere makes a repository-wide search tie.
    return [
        _file("pkg/params.py", "python", [_fn("Depends", 10)]),
        _file(barrel, "python", []),
        _file("other/params.py", "python", [_fn("Depends", 4)]),
        _file("tests/test_x.py", "python", [_fn("test_it", 3, calls=["Depends"], quals={"Depends": [""]})]),
    ]


def test_a_barrel_re_export_is_an_import_link():
    edges = [
        {"src": "tests/test_x.py", "dst": "pkg/__init__.py"},
        {"src": "pkg/__init__.py", "dst": "pkg/params.py"},
    ]
    row = _site(resolve_calls(_reexport_files(), edges)[0], "Depends")
    assert (row["step"], row["resolution"], row["dst_path"], row["dst_line"]) == (
        "import",
        "scoped",
        "pkg/params.py",
        10,
    )


def test_an_ordinary_module_does_not_re_export_its_imports():
    # Only barrels are followed: importing util.py does not make what util.py imports visible.
    files = _reexport_files()
    files.append(_file("pkg/util.py", "python", []))
    edges = [
        {"src": "tests/test_x.py", "dst": "pkg/util.py"},
        {"src": "pkg/util.py", "dst": "pkg/params.py"},
    ]
    row = _site(resolve_calls(files, edges)[0], "Depends")
    assert row["step"] != "import"


def test_nested_barrels_are_followed_two_hops():
    files = [
        _file("pkg/sub/impl.py", "python", [_fn("make", 2)]),
        _file("pkg/__init__.py", "python", []),
        _file("pkg/sub/__init__.py", "python", []),
        _file("elsewhere/impl.py", "python", [_fn("make", 2)]),
        _file("app.py", "python", [_fn("run", 1, calls=["make"], quals={"make": [""]})]),
    ]
    edges = [
        {"src": "app.py", "dst": "pkg/__init__.py"},
        {"src": "pkg/__init__.py", "dst": "pkg/sub/__init__.py"},
        {"src": "pkg/sub/__init__.py", "dst": "pkg/sub/impl.py"},
    ]
    row = _site(resolve_calls(files, edges)[0], "make")
    assert (row["step"], row["dst_path"]) == ("import", "pkg/sub/impl.py")


def test_a_typescript_index_barrel_is_followed():
    files = [
        _file("lib/core.ts", "typescript", [_fn("render", 5)]),
        _file("lib/index.ts", "typescript", []),
        _file("old/core.ts", "typescript", [_fn("render", 5)]),
        _file("app.ts", "typescript", [_fn("main", 1, calls=["render"], quals={"render": [""]})]),
    ]
    edges = [{"src": "app.ts", "dst": "lib/index.ts"}, {"src": "lib/index.ts", "dst": "lib/core.ts"}]
    row = _site(resolve_calls(files, edges)[0], "render")
    assert (row["step"], row["dst_path"]) == ("import", "lib/core.ts")


# ----------------------------------------------------------------------------- typed receivers


def _typed_files(rtypes):
    main = _fn("main", 1, calls=["post"], quals={"post": ["app"]})
    main["calls_out_receiver_types"] = rtypes
    return [
        _file("fastapi/applications.py", "python", [_fn("post", 20, owner="FastAPI")],
              [{"name": "FastAPI", "inheritance": ["Starlette"], "start_line": 5}]),
        _file("fastapi/routing.py", "python", [_fn("post", 40, owner="APIRouter")],
              [{"name": "APIRouter", "inheritance": [], "start_line": 3}]),
        _file("tests/test_app.py", "python", [main]),
    ]  # fmt: skip


def test_a_receiver_of_known_class_resolves_to_that_class_method():
    row = _site(resolve_calls(_typed_files({"app": "FastAPI"}))[0], "post")
    assert (row["step"], row["resolution"], row["dst_path"], row["dst_line"]) == (
        "typed",
        "scoped",
        "fastapi/applications.py",
        20,
    )


def test_a_typed_receiver_finds_an_inherited_method():
    files = _typed_files({"app": "App"})
    files.append(_file("my/app.py", "python", [], [{"name": "App", "inheritance": ["FastAPI"], "start_line": 1}]))
    row = _site(resolve_calls(files)[0], "post")
    assert (row["step"], row["dst_path"]) == ("typed", "fastapi/applications.py")


def test_a_receiver_type_that_is_not_a_known_class_changes_nothing():
    # `app = create_app()` records create_app; it is a function, not a class, so the old ladder runs.
    typed = _site(resolve_calls(_typed_files({"app": "create_app"}))[0], "post")
    plain = _site(resolve_calls(_typed_files({}))[0], "post")
    assert typed["step"] == plain["step"] != "typed"
