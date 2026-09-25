"""
The import resolver follows each language's own rule for WHERE an import points,
not only a name search (#3544, #3545, #3552, #3553, #3554). Measured on real repos
by tests/tools/import_graph_accuracy.py; these pin each shape it found.
"""

import pytest

from gitgalaxy.core.network_risk_sensor import NetworkRiskSensor


def _edges(files):
    """Resolved (importer, imported) pairs for a list of (path, lang_id, raw_imports)."""
    parsed = [{"path": p, "lang_id": lang, "raw_imports": list(imps), "classes": []} for p, lang, imps in files]
    return set(NetworkRiskSensor().resolve_import_edges(parsed))


# ----------------------------------------------------------------------------- #3553


def test_a_quoted_include_resolves_beside_the_includer_when_the_name_repeats():
    # libuv: src/unix/internal.h and src/win/internal.h -- the name alone is ambiguous.
    edges = _edges(
        [
            ("src/unix/core.c", "c", ["internal.h", "poll.h"]),
            ("src/unix/internal.h", "c", []),
            ("src/unix/poll.c", "c", []),
            ("src/win/internal.h", "c", []),
        ]
    )
    assert ("src/unix/core.c", "src/unix/internal.h") in edges
    # an include WITH an extension names that file: <poll.h> is never poll.c
    assert ("src/unix/core.c", "src/unix/poll.c") not in edges


def test_relative_js_require_and_ruby_require_relative_use_the_location():
    edges = _edges(
        [
            ("examples/a/index.js", "javascript", ["./db"]),
            ("examples/a/db.js", "javascript", []),
            ("examples/b/db.js", "javascript", []),
            ("lib/rack/common_logger.rb", "ruby", ["request"]),
            ("lib/rack/request.rb", "ruby", []),
            ("lib/rack/auth/abstract/request.rb", "ruby", []),
            ("src/Server.zig", "zig", ["features/goto.zig"]),
            ("src/features/goto.zig", "zig", []),
        ]
    )
    assert ("examples/a/index.js", "examples/a/db.js") in edges
    assert ("lib/rack/common_logger.rb", "lib/rack/request.rb") in edges
    assert ("src/Server.zig", "src/features/goto.zig") in edges


def test_a_relative_directory_import_takes_its_index_file():
    edges = _edges([("src/app.ts", "typescript", ["./lib"]), ("src/lib/index.ts", "typescript", [])])
    assert edges == {("src/app.ts", "src/lib/index.ts")}


# ----------------------------------------------------------------------------- #3552


def test_an_esm_js_spelling_resolves_to_the_typescript_source():
    edges = _edges(
        [
            ("packages/bench/array.ts", "typescript", ["./benchUtil.js", "../zod/src/checks.js"]),
            ("packages/bench/benchUtil.ts", "typescript", []),
            ("packages/zod/src/checks.ts", "typescript", []),
        ]
    )
    assert edges == {
        ("packages/bench/array.ts", "packages/bench/benchUtil.ts"),
        ("packages/bench/array.ts", "packages/zod/src/checks.ts"),
    }


def test_an_existing_js_file_still_wins_over_a_ts_source_of_the_same_stem():
    edges = _edges(
        [("a/main.js", "javascript", ["./x.js"]), ("a/x.js", "javascript", []), ("a/x.ts", "typescript", [])]
    )
    assert edges == {("a/main.js", "a/x.js")}


# ----------------------------------------------------------------------------- #3545 / #3544 (python)


PY = [
    ("fastapi/__init__.py", "python", []),
    ("fastapi/types.py", "python", []),
    ("fastapi/requests.py", "python", []),
    ("fastapi/security/__init__.py", "python", []),
    ("fastapi/security/http.py", "python", []),
]


def test_a_package_import_binds_its_init_file():
    edges = _edges(PY + [("tests/test_a.py", "python", ["fastapi", "fastapi.security.http"])])
    assert ("tests/test_a.py", "fastapi/__init__.py") in edges
    assert ("tests/test_a.py", "fastapi/security/http.py") in edges


def test_a_module_inside_a_package_is_not_a_top_level_module():
    # `import types` is the stdlib and `starlette.requests` is another package --
    # neither is the local fastapi/types.py or fastapi/requests.py.
    edges = _edges(PY + [("fastapi/routing.py", "python", ["types", "starlette.requests", "fastapi.types"])])
    assert edges == {("fastapi/routing.py", "fastapi/types.py")}


def test_python_relative_imports_resolve_against_the_importing_package():
    edges = _edges(
        PY
        + [
            ("fastapi/security/api_key.py", "python", [".http", "..types", "."]),
        ]
    )
    assert edges == {
        ("fastapi/security/api_key.py", "fastapi/security/http.py"),
        ("fastapi/security/api_key.py", "fastapi/types.py"),
        ("fastapi/security/api_key.py", "fastapi/security/__init__.py"),
    }


def test_a_src_layout_package_is_found_under_its_source_root():
    edges = _edges(
        [
            ("src/flask/__init__.py", "python", []),
            ("src/flask/app.py", "python", []),
            ("tests/test_app.py", "python", ["flask.app", "flask"]),
        ]
    )
    assert edges == {("tests/test_app.py", "src/flask/app.py"), ("tests/test_app.py", "src/flask/__init__.py")}


# ----------------------------------------------------------------------------- #3544 (lua/perl/java)


def test_a_dotted_token_needs_its_package_path_even_for_a_lone_candidate():
    edges = _edges(
        [
            ("src/luarocks/search.lua", "lua", ["luarocks.manif", "other.util", "test/all.lua"]),
            ("src/luarocks/test/all.lua", "lua", []),
            ("src/luarocks/manif.lua", "lua", []),
            ("src/luarocks/util.lua", "lua", []),
        ]
    )
    # a token that already names a FILE (`dofile("test/all.lua")`) is not a dotted module path
    assert edges == {
        ("src/luarocks/search.lua", "src/luarocks/manif.lua"),
        ("src/luarocks/search.lua", "src/luarocks/test/all.lua"),
    }


# ----------------------------------------------------------------------------- #3554


def test_perl_package_names_map_to_pm_paths():
    edges = _edges(
        [
            ("lib/HTTP/Message.pm", "perl", ["strict", "HTTP::Headers", "HTTP::Headers::Util", "Other::Headers"]),
            ("lib/HTTP/Headers.pm", "perl", []),
            ("lib/HTTP/Headers/Util.pm", "perl", []),
        ]
    )
    assert edges == {
        ("lib/HTTP/Message.pm", "lib/HTTP/Headers.pm"),
        ("lib/HTTP/Message.pm", "lib/HTTP/Headers/Util.pm"),
    }


@pytest.mark.parametrize(
    "token",
    [
        "com.google.gson.stream.JsonScope.DANGLING_NAME",  # import static ... member
        "com.google.gson.stream.JsonScope.Inner",  # nested class
    ],
)
def test_java_member_and_nested_imports_resolve_to_the_class_file(token):
    edges = _edges(
        [
            ("src/com/google/gson/stream/JsonWriter.java", "java", [token]),
            ("src/com/google/gson/stream/JsonScope.java", "java", []),
            ("metrics/com/google/gson/metrics/Inner.java", "java", []),
        ]
    )
    assert edges == {("src/com/google/gson/stream/JsonWriter.java", "src/com/google/gson/stream/JsonScope.java")}
