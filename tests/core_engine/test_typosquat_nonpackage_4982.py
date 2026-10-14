"""#4982: the typosquat radar never tests tokens that resolve to the project itself or the language stdlib."""

import sys
from unittest.mock import patch

import pytest

from gitgalaxy.galaxyscope import Orchestrator
from gitgalaxy.standards.stdlib_modules import (
    _ALL,
    _CPYTHON,
    _GO_STDLIB,
    _NODE_CORE,
    NO_REGISTRY_LANGS,
    is_stdlib_module,
    same_jvm_package,
)

CONFIG = {
    "LANGUAGE_DEFINITIONS": {},
    "APERTURE_CONFIG": {},
    "PARANOID_MODE": False,
    "FAIL_ON_SECRETS": False,
    "FAIL_ON_MALWARE": False,
    "MAX_RISK_EXPOSURE": 0.0,
}


def _scan(files, root=".", lang_ids=None):
    """files: {path: {tokens}}; every path gets the lang_id lang_ids maps its extension to."""
    scope = Orchestrator(str(root), CONFIG)
    lang_ids = lang_ids or {}
    scope.ram_cache = {
        path: {"raw_imports": set(imports), "lang_id": lang_ids.get("." + path.rsplit(".", 1)[-1], "")}
        for path, imports in files.items()
    }
    scope.stem_map = {k: k for k in scope.ram_cache}
    scope.ext_tally = {".js": 1, ".ts": 1, ".py": 1, ".adb": 1, ".ads": 1}
    with patch("gitgalaxy.galaxyscope.logger") as log:
        scope._resolve_dependency_graph()
    return scope, log


def _pair(orphan, anchor, ext, fmt="{}"):
    files = {f"src/a{i}{ext}": {fmt.format(anchor)} for i in range(3)}
    files[f"src/orphan{ext}"] = {fmt.format(orphan)}
    return files


def _fired(scope):
    return scope.typosquat_hits == 1 and "TYPOSQUATTING" in scope.ram_cache["src/orphan.js"]["metadata"]["alert"]


# ---- intra-project relative paths -------------------------------------------------------------


@pytest.mark.parametrize("prefix", ["./", "../", "../../", "../../../"])
@pytest.mark.parametrize("ext", [".js", ".mjs", ".ts", ".jsx"])
def test_relative_path_pair_is_not_a_typosquat(prefix, ext):
    files = _pair(f"{prefix}math/Vector2{ext}", f"{prefix}math/Vector3{ext}", ".js")
    # the anchors may be spelled differently from the orphan: only the orphan's prefix matters
    scope, _ = _scan(files)
    assert scope.typosquat_hits == 0


@pytest.mark.parametrize("orphan", ["../math/Vector2.js", "./math/Vector2.js", "../../math/Vector2.js"])
def test_relative_orphan_against_package_style_anchor(orphan):
    files = {f"src/a{i}.js": {"math/Vector3.js"} for i in range(3)}
    files["src/orphan.js"] = {orphan}
    scope, _ = _scan(files)
    assert scope.typosquat_hits == 0


def test_package_style_path_pair_still_fires():
    scope, _ = _scan(_pair("lodash-es/chunkk", "lodash-es/chunks", ".js"))
    assert _fired(scope)


# ---- Ada child units of the project's own hierarchy ------------------------------------------


@pytest.mark.parametrize("orphan", ["Alire.Roots", "alire.roots", "ALIRE.ROOTS", "Alire.Roots.Editable"])
@pytest.mark.parametrize("with_root_file", [True, False])
def test_ada_project_child_units_are_not_typosquats(orphan, with_root_file):
    files = {f"src/a{i}.adb": {"Alire.Root"} for i in range(3)}
    files["src/orphan.adb"] = {orphan}
    if with_root_file:
        files["src/alire.ads"] = set()
    files["src/alire-root.ads"] = set()  # the project's own hierarchy, even without the exact unit
    scope, _ = _scan(files)
    assert scope.typosquat_hits == 0


def test_ada_unrelated_unit_still_fires():
    files = {f"src/a{i}.adb": {"Gnatcoll.Json"} for i in range(3)}
    files["src/orphan.adb"] = {"Gnatcoll.Jsons"}
    files["src/alire.ads"] = set()
    scope, _ = _scan(files)
    assert scope.typosquat_hits == 1


# ---- Dockerfile --from=<stage> ----------------------------------------------------------------

DF = {".Dockerfile": "dockerfile"}


@pytest.mark.parametrize("stage_decl", ["AS registry", "as registry", "As Registry"])
@pytest.mark.parametrize("where", ["same", "sibling"])
def test_stage_named_in_from_is_not_a_typosquat(tmp_path, stage_decl, where):
    decl = f"FROM distribution/distribution:3 {stage_decl}\n"
    if where == "same":
        (tmp_path / "daemon.Dockerfile").write_text(decl + "COPY --from=registry /b /b\n")
        (tmp_path / "other.Dockerfile").write_text("FROM scratch\n")
    else:
        (tmp_path / "daemon.Dockerfile").write_text("FROM scratch\nCOPY --from=registry /b /b\n")
        (tmp_path / "other.Dockerfile").write_text(decl)
    files = {f"a{i}.Dockerfile": {"registry2"} for i in range(3)}
    files["daemon.Dockerfile"] = {"registry"}
    files["other.Dockerfile"] = set()
    scope, _ = _scan(files, tmp_path, DF)
    assert scope.typosquat_hits == 0


def test_numeric_stage_index_is_not_a_package(tmp_path):
    (tmp_path / "d.Dockerfile").write_text("FROM scratch\n")
    files = {f"a{i}.Dockerfile": {"12345"} for i in range(3)}
    files["d.Dockerfile"] = {"12346"}
    scope, _ = _scan(files, tmp_path, DF)
    assert scope.typosquat_hits == 0


def test_undeclared_dockerfile_name_stays_eligible(tmp_path):
    (tmp_path / "d.Dockerfile").write_text("FROM scratch\nCOPY --from=registry /b /b\n")
    files = {f"a{i}.Dockerfile": {"registry2"} for i in range(3)}
    files["d.Dockerfile"] = {"registry"}
    scope, _ = _scan(files, tmp_path, DF)
    assert scope.typosquat_hits == 1


def test_dockerfile_stage_declared_for_another_name_does_not_shield(tmp_path):
    (tmp_path / "d.Dockerfile").write_text("FROM x AS builder\nCOPY --from=registry /b /b\n")
    files = {f"a{i}.Dockerfile": {"registry2"} for i in range(3)}
    files["d.Dockerfile"] = {"registry"}
    scope, _ = _scan(files, tmp_path, DF)
    assert scope.typosquat_hits == 1


# ---- Python / MicroPython stdlib --------------------------------------------------------------


def _one_edit(name):
    return name + "s" if not name.endswith("s") else name[:-1]


@pytest.mark.parametrize("module", sorted(m for m in _ALL if len(m) >= 5))
def test_every_stdlib_module_is_exempt_as_a_suspect(module):
    scope, _ = _scan(_pair(module, _one_edit(module), ".py"))
    assert scope.typosquat_hits == 0


@pytest.mark.parametrize(("orphan", "anchor"), [("builtins", "builtin"), ("ubinascii", "binascii")])
def test_issue_pairs(orphan, anchor):
    scope, _ = _scan(_pair(orphan, anchor, ".py"))
    assert scope.typosquat_hits == 0


@pytest.mark.parametrize(("orphan", "anchor"), [("requestss", "requests"), ("jsonn", "json"), ("numpyy", "numpy")])
def test_near_miss_of_a_stdlib_or_package_name_still_fires(orphan, anchor):
    files = {f"src/a{i}.py": {anchor} for i in range(3)}
    files["src/orphan.py"] = {orphan}
    scope, _ = _scan(files)
    assert scope.typosquat_hits == (1 if len(orphan) >= 5 and len(anchor) >= 5 else 0)


def test_stdlib_names_only_exempt_for_python_importers():
    scope, _ = _scan(_pair("builtins", "builtin", ".js"))
    assert _fired(scope)


def test_stdlib_set_covers_this_interpreter():
    names = getattr(sys, "stdlib_module_names", None)
    if names is None:
        pytest.skip("sys.stdlib_module_names needs Python 3.10+")
    assert {n for n in names if not n.startswith("_")} - set(_CPYTHON) == set()


def test_is_stdlib_module_dotted_and_extension():
    assert is_stdlib_module("os.path", ".py")
    assert is_stdlib_module("os/path", ".pyi")
    assert not is_stdlib_module("os.path", ".rs")
    assert not is_stdlib_module("numpy", ".py")


# ---- no-registry languages, JVM classes, Node core, Go stdlib (#4982 second half) --------------


def _scan_lang(orphan, anchor, ext, lang):
    scope, _ = _scan(_pair(orphan, anchor, ext), lang_ids={ext: lang})
    return scope


@pytest.mark.parametrize("lang", sorted(NO_REGISTRY_LANGS))
@pytest.mark.parametrize(
    ("orphan", "anchor"),
    [("DSNC10/SDSNLOD2", "DSNC10/SDSNLOAD"), ("S001V0", "S001A0"), ("S001A1", "S001A0"), ("COPYBOOK1", "COPYBOOK")],
)
def test_no_registry_language_member_names_are_not_squats(lang, orphan, anchor):
    assert _scan_lang(orphan, anchor, ".x1", lang).typosquat_hits == 0


def test_registry_language_with_the_same_pair_still_fires():
    assert _scan_lang("S001V0", "S001A0", ".py", "python").typosquat_hits == 1
    assert _scan_lang("COPYBOOK1", "COPYBOOK", ".py", "python").typosquat_hits == 1


@pytest.mark.parametrize("ext", [".java", ".groovy", ".gradle", ".kt", ".kts", ".scala"])
@pytest.mark.parametrize(
    ("orphan", "anchor"),
    [
        ("org/gradle/api/tasks/InputFiles", "org/gradle/api/tasks/InputFile"),
        ("com/acme/model/Customers", "com/acme/model/Customer"),
    ],
)
def test_jvm_classes_of_one_package_are_not_squats(ext, orphan, anchor):
    scope, _ = _scan(_pair(orphan, anchor, ext))
    assert scope.typosquat_hits == 0


@pytest.mark.parametrize("ext", [".java", ".groovy", ".kt"])
def test_jvm_package_typo_still_fires(ext):
    scope, _ = _scan(_pair("org/apachee/commons/Lang", "org/apache/commons/Lang", ext))
    assert scope.typosquat_hits == 1


def test_same_package_rule_is_jvm_only():
    scope, _ = _scan(_pair("org/gradle/api/tasks/InputFiles", "org/gradle/api/tasks/InputFile", ".js"))
    assert scope.typosquat_hits == 1
    assert not same_jvm_package("a/b/CC", "a/b/C", ".py")
    assert same_jvm_package("a/b/CC", "a/b/C", ".java")
    assert not same_jvm_package("a/b/CC", "a/x/C", ".java")


@pytest.mark.parametrize("ext", [".js", ".mjs", ".cjs", ".ts", ".tsx"])
@pytest.mark.parametrize("module", sorted(m for m in _NODE_CORE if len(m) >= 5))
def test_every_node_core_module_is_exempt_as_a_suspect(ext, module):
    scope, _ = _scan(_pair(module, _one_edit(module), ext))
    assert scope.typosquat_hits == 0


@pytest.mark.parametrize("token", ["node:fs", "node:test", "fs/promises", "stream/web", "path/posix"])
def test_node_prefix_and_subpaths(token):
    assert is_stdlib_module(token, ".ts")


@pytest.mark.parametrize(("orphan", "anchor"), [("expresss", "express"), ("lodashs", "lodash")])
def test_node_package_near_misses_still_fire(orphan, anchor):
    scope, _ = _scan(_pair(orphan, anchor, ".js"))
    assert _fired(scope)


@pytest.mark.parametrize("module", sorted(m for m in _GO_STDLIB if len(m) >= 5))
def test_every_go_stdlib_package_is_exempt_as_a_suspect(module):
    scope, _ = _scan(_pair(module, _one_edit(module), ".go"))
    assert scope.typosquat_hits == 0


def test_go_stdlib_paths_and_third_party():
    assert is_stdlib_module("net/http", ".go")
    assert is_stdlib_module("encoding/json", ".go")
    assert not is_stdlib_module("github.com/net/http", ".go")
    assert not is_stdlib_module("golang.org/x/net", ".go")
    assert not is_stdlib_module("net/http", ".py")
    assert not is_stdlib_module("fs", ".go")
    assert not is_stdlib_module("fmt", ".js")
