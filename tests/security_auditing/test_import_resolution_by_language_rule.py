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


def test_rust_mod_declarations_follow_the_module_tree():
    # lib.rs/mod.rs own their directory; any other file owns <dir>/<stem>/ (Rust 2018).
    # `algorithm` repeats elsewhere in the repo -- the tree, not the name, decides.
    # galaxyscope records a `mod name;` as `./name` (local_module_capture_group).
    edges = _edges(
        [
            ("src/lib.rs", "rust", ["./de", "./lexical", "serde"]),
            ("src/de.rs", "rust", ["./read"]),
            ("src/de/read.rs", "rust", []),
            ("src/lexical/mod.rs", "rust", ["./algorithm"]),
            ("src/lexical/algorithm.rs", "rust", []),
            ("benches/algorithm.rs", "rust", []),
            ("tests/test.rs", "rust", ["./macros"]),  # an integration test is a crate root
            ("tests/macros/mod.rs", "rust", []),
        ]
    )
    assert edges == {
        ("src/lib.rs", "src/de.rs"),
        ("src/lib.rs", "src/lexical/mod.rs"),
        ("src/de.rs", "src/de/read.rs"),
        ("src/lexical/mod.rs", "src/lexical/algorithm.rs"),
        ("tests/test.rs", "tests/macros/mod.rs"),
    }


def test_a_rust_mod_the_tree_cannot_place_draws_no_edge():
    # `mod util;` in a flattened corpus: util.rs is not in the tree. The same-named
    # shell and Lua files elsewhere are not it, and neither is a sibling util.rs.
    edges = _edges(
        [
            ("rust/io.rs", "rust", ["./util", "./fetch"]),
            ("rust/util.rs", "rust", []),
            ("shell/util.sh", "shell", []),
            ("lua/fetch.lua", "lua", []),
        ]
    )
    assert edges == set()


# ----------------------------------------------------------------------------- import-graph precision


def test_an_extensionless_include_names_an_extensionless_file():
    # fmt: `#include <chrono>` is the standard header, never fmt's own chrono.h.
    edges = _edges(
        [
            ("test/perf.cc", "cpp", ["chrono", "ostream", "fmt/format.h", "QtCore/QString"]),
            ("include/fmt/chrono.h", "cpp", []),
            ("include/fmt/ostream.h", "cpp", []),
            ("include/fmt/format.h", "cpp", []),
            ("vendor/QtCore/QString", "cpp", []),
        ]
    )
    assert edges == {("test/perf.cc", "include/fmt/format.h"), ("test/perf.cc", "vendor/QtCore/QString")}


def test_a_bare_js_specifier_is_a_package_not_a_same_named_file():
    edges = _edges(
        [
            ("examples/ejs/index.js", "javascript", ["ejs", "express", "node:path", "../../lib/express"]),
            ("test/acceptance/ejs.js", "javascript", []),
            ("lib/express.js", "javascript", []),
            ("packages/bench/jit.ts", "typescript", ["zod/mini", "zod/v4/core"]),
            ("packages/integration/fixtures/mini.ts", "typescript", []),
            ("packages/zod/src/v4/core/core.ts", "typescript", []),
        ]
    )
    assert edges == {("examples/ejs/index.js", "lib/express.js")}


def test_an_aliased_or_path_shaped_specifier_mirrors_a_real_file():
    edges = _edges(
        [
            ("src/pages/home.tsx", "typescript", ["@/components/Button", "~/utils", "#internal/db.js", "lib/api"]),
            ("src/components/Button.tsx", "typescript", []),
            ("src/utils/index.ts", "typescript", []),
            ("src/internal/db.ts", "typescript", []),
            ("src/lib/api.ts", "typescript", []),
            ("other/Button.tsx", "typescript", []),
        ]
    )
    assert edges == {
        ("src/pages/home.tsx", "src/components/Button.tsx"),
        ("src/pages/home.tsx", "src/utils/index.ts"),
        ("src/pages/home.tsx", "src/internal/db.ts"),
        ("src/pages/home.tsx", "src/lib/api.ts"),
    }


def test_from_dot_import_name_is_the_submodule_else_the_package():
    # galaxyscope records `from . import cli, Flask` as `.cli`, `.Flask`.
    edges = _edges(
        [
            ("src/flask/__init__.py", "python", []),
            ("src/flask/cli.py", "python", []),
            ("src/flask/app.py", "python", [".cli", ".Flask"]),
        ]
    )
    assert edges == {("src/flask/app.py", "src/flask/cli.py"), ("src/flask/app.py", "src/flask/__init__.py")}


# ----------------------------------------------------------------------------- #3596 #3597 #3598 #3595


def _edges_with_units(files):
    """Like _edges, but each entry may carry the file's declared functions/classes."""
    parsed = [
        {
            "path": p,
            "lang_id": lang,
            "raw_imports": list(imps),
            "classes": [{"name": c} for c in classes],
            "functions": [{"name": f} for f in funcs],
        }
        for p, lang, imps, funcs, classes in files
    ]
    return set(NetworkRiskSensor().resolve_import_edges(parsed))


def test_kotlin_top_level_functions_and_members_resolve_to_their_declaring_file():
    root = "src/main/kotlin/com/squareup/kotlinpoet/"
    edges = _edges_with_units(
        [
            (
                root + "metadata/X.kt",
                "kotlin",
                [
                    "com.squareup.kotlinpoet.asClassName",  # top-level extension in ClassNames.kt
                    "com.squareup.kotlinpoet.Util.JAVA_DEPRECATED",  # object member -> Util.kt
                    "java.util.Collections",  # never the lone util.kt
                    "com.squareup.kotlinpoet.joinToCode",  # only a TEST declares it: no edge
                ],
                [],
                [],
            ),
            (root + "ClassNames.kt", "kotlin", [], ["asClassName"], []),
            (root + "Util.kt", "kotlin", [], [], ["Util"]),
            (root + "metadata/util.kt", "kotlin", [], [], []),
            ("src/test/kotlin/com/squareup/kotlinpoet/CodeBlockTest.kt", "kotlin", [], ["joinToCode"], []),
        ]
    )
    assert edges == {(root + "metadata/X.kt", root + "ClassNames.kt"), (root + "metadata/X.kt", root + "Util.kt")}


def test_dart_package_uris_are_path_tails_and_dart_scheme_is_the_sdk():
    edges = _edges(
        [
            (
                "pkgs/cupertino/lib/src/client.dart",
                "dart",
                ["package:http_profile/http_profile.dart", "dart:io", "package:async/async.dart", "api.dart"],
            ),
            ("pkgs/http_profile/lib/http_profile.dart", "dart", []),
            ("pkgs/cupertino/lib/src/api.dart", "dart", []),
            ("pkgs/other/lib/src/api.dart", "dart", []),
            ("tool/io.dart", "dart", []),
        ]
    )
    assert edges == {
        ("pkgs/cupertino/lib/src/client.dart", "pkgs/http_profile/lib/http_profile.dart"),
        ("pkgs/cupertino/lib/src/client.dart", "pkgs/cupertino/lib/src/api.dart"),
    }


def test_shell_variable_paths_resolve_only_by_their_literal_tail():
    edges = _edges(
        [
            (
                "bash_it.sh",
                "shell",
                [
                    "$BASH_IT/themes/powerline/powerline.base.bash",
                    "$rvm_path/scripts/completion",  # never lib/completion.bash by stem
                    "$XDG_CONFIG_HOME:-$HOME/.config",  # never a config.yml
                    "~/.fzf.bash",
                    "$DIR/helpers.bash",  # a bare name: beside the importer
                ],
            ),
            ("themes/powerline/powerline.base.bash", "shell", []),
            ("themes/gitline/powerline.base.bash", "shell", []),
            ("lib/completion.bash", "shell", []),
            (".github/config.yml", "yaml", []),
            ("helpers.bash", "shell", []),
            ("lib/helpers.bash", "shell", []),
        ]
    )
    assert edges == {("bash_it.sh", "themes/powerline/powerline.base.bash"), ("bash_it.sh", "helpers.bash")}


def test_scala_declarations_members_and_package_objects():
    base = "core/src/main/scala/io/circe/"
    edges = _edges_with_units(
        [
            (
                "app/src/main/scala/todo/Todo.scala",
                "scala",
                [
                    "io.circe.DecodingFailure",  # declared in Error.scala
                    "io.circe.syntax._",  # package object -> syntax/package.scala
                    "io.circe.Json._",  # object members -> Json.scala
                ],
                [],
                [],
            ),
            (base + "Error.scala", "scala", [], [], ["Error", "DecodingFailure"]),
            (base + "syntax/package.scala", "scala", [], [], ["syntax"]),
            (base + "Json.scala", "scala", [], [], ["Json"]),
        ]
    )
    src = "app/src/main/scala/todo/Todo.scala"
    assert edges == {(src, base + "Error.scala"), (src, base + "syntax/package.scala"), (src, base + "Json.scala")}
