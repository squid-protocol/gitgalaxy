"""
#3789: a JS/TS package importing itself by name (`import * as z from "zod/v4"` inside zod) is
resolved through the nearest package.json -- its `name`, then the file its `exports` declares for
the subpath -- and nothing else. Before, every bare specifier was an external package, so a
package's own tests and examples drew no edge to its source.
"""

import json

import pytest

from gitgalaxy.core.network_risk_sensor import NetworkRiskSensor
from gitgalaxy.core.package_self_reference import Package, export_targets, split_specifier

_EXPORTS = {
    ".": {"@zod/source": "./src/index.ts", "import": "./index.js"},
    "./v4": {"@zod/source": "./src/v4/index.ts", "types": "./v4/index.d.cts", "import": "./v4/index.js"},
    "./locales/*": "./src/locales/*.ts",
    "./internal": None,
}


@pytest.mark.parametrize(
    "spec, expected",
    [("zod", ("zod", ".")), ("zod/v4", ("zod", "./v4")), ("@a/b/c/d", ("@a/b", "./c/d")), ("@a/b", ("@a/b", "."))],
)
def test_split_specifier(spec, expected):
    assert split_specifier(spec) == expected


def _pkg(exports=None, **fields):
    manifest = {"name": "zod", **fields}
    if exports is not None:
        manifest["exports"] = exports
    return Package("packages/zod", manifest)


def test_export_targets_follow_declaration_order():
    assert export_targets(_pkg(_EXPORTS), "./v4") == ["./src/v4/index.ts", "./v4/index.d.cts", "./v4/index.js"]
    assert export_targets(_pkg(_EXPORTS), ".") == ["./src/index.ts", "./index.js"]


def test_export_patterns_and_undeclared_subpaths():
    assert export_targets(_pkg(_EXPORTS), "./locales/fr") == ["./src/locales/fr.ts"]
    assert export_targets(_pkg(_EXPORTS), "./internal") == []  # exports: null hides it
    assert export_targets(_pkg(_EXPORTS), "./nope") == []  # not exported: no guess


def test_no_exports_field_means_main_or_the_path_itself():
    assert export_targets(_pkg(main="./lib/index.js", module="./es/index.js"), ".") == [
        "./es/index.js",
        "./lib/index.js",
    ]
    assert export_targets(_pkg(), "./v4") == ["./v4"]


def test_string_exports_is_the_root_export_only():
    assert export_targets(_pkg("./src/index.ts"), ".") == ["./src/index.ts"]
    assert export_targets(_pkg("./src/index.ts"), "./v4") == []


def _repo(tmp_path, manifest, files, extra_manifests=None):
    (tmp_path / "packages" / "zod").mkdir(parents=True)
    (tmp_path / "packages" / "zod" / "package.json").write_text(json.dumps(manifest))
    for rel, text in (extra_manifests or {}).items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text)
    return [
        {"path": p, "lang_id": "typescript", "raw_imports": imports, "classes": [], "functions": []}
        for p, imports in files.items()
    ]


def _edges(tmp_path, manifest, files, **kw):
    parsed = _repo(tmp_path, manifest, files, **kw)
    sensor = NetworkRiskSensor()
    sensor.root = str(tmp_path)
    return set(sensor.resolve_import_edges(parsed))


_TEST = "packages/zod/src/v4/classic/tests/string.test.ts"
_V4 = "packages/zod/src/v4/index.ts"
_SOURCE = {_V4: [], "packages/zod/src/index.ts": [], "packages/zod/src/locales/fr.ts": []}


def test_self_import_resolves_through_exports(tmp_path):
    edges = _edges(
        tmp_path, {"name": "zod", "exports": _EXPORTS}, {**_SOURCE, _TEST: ["zod/v4", "zod", "zod/locales/fr"]}
    )
    assert {(_TEST, _V4), (_TEST, "packages/zod/src/index.ts"), (_TEST, "packages/zod/src/locales/fr.ts")} <= edges


def test_emitted_spelling_maps_to_the_source_file(tmp_path):
    manifest = {"name": "zod", "exports": {"./v4": {"import": "./src/v4/index.js"}}}
    assert (_TEST, _V4) in _edges(tmp_path, manifest, {**_SOURCE, _TEST: ["zod/v4"]})


@pytest.mark.parametrize(
    "manifest, token",
    [
        ({"name": "other", "exports": _EXPORTS}, "zod/v4"),  # the manifest is another package's
        ({"name": "zod", "exports": _EXPORTS}, "zodx/v4"),  # a different package, same prefix
        ({"name": "zod", "exports": _EXPORTS}, "zod/v5"),  # a subpath the manifest does not export
        ({"name": "zod", "exports": _EXPORTS}, "lodash"),
        ({"exports": _EXPORTS}, "zod/v4"),  # no name
    ],
)
def test_nothing_beyond_what_the_manifest_declares(tmp_path, manifest, token):
    assert not [e for e in _edges(tmp_path, manifest, {**_SOURCE, _TEST: [token]}) if e[0] == _TEST]


def test_only_the_nearest_package_json_counts(tmp_path):
    nested = {"packages/zod/src/v4/classic/tests/package.json": json.dumps({"name": "zod-tests"})}
    edges = _edges(
        tmp_path, {"name": "zod", "exports": _EXPORTS}, {**_SOURCE, _TEST: ["zod/v4"]}, extra_manifests=nested
    )
    assert not [e for e in edges if e[0] == _TEST]


def test_without_a_scan_root_a_bare_specifier_stays_external(tmp_path):
    parsed = _repo(tmp_path, {"name": "zod", "exports": _EXPORTS}, {**_SOURCE, _TEST: ["zod/v4"]})
    assert not [e for e in NetworkRiskSensor().resolve_import_edges(parsed) if e[0] == _TEST]


def test_unreadable_manifest_is_ignored(tmp_path):
    parsed = _repo(tmp_path, {}, {**_SOURCE, _TEST: ["zod/v4"]})
    (tmp_path / "packages" / "zod" / "package.json").write_text("{not json")
    sensor = NetworkRiskSensor()
    sensor.root = str(tmp_path)
    assert not [e for e in sensor.resolve_import_edges(parsed) if e[0] == _TEST]


def test_workspace_sibling_imports_resolve(tmp_path):
    (tmp_path / "package.json").write_text(
        json.dumps({"private": True, "workspaces": ["packages/*", "!packages/ignored"]})
    )
    (tmp_path / "packages" / "core").mkdir(parents=True)
    (tmp_path / "packages" / "core" / "package.json").write_text(
        json.dumps({"name": "@scope/core", "main": "src/index.ts", "exports": {"./utils": "./src/utils.ts"}})
    )
    (tmp_path / "packages" / "app").mkdir(parents=True)
    (tmp_path / "packages" / "app" / "package.json").write_text(json.dumps({"name": "@scope/app"}))
    (tmp_path / "packages" / "ignored").mkdir(parents=True)
    (tmp_path / "packages" / "ignored" / "package.json").write_text(
        json.dumps({"name": "@scope/ignored", "main": "index.ts"})
    )

    core_idx = "packages/core/src/index.ts"
    core_utils = "packages/core/src/utils.ts"
    app_main = "packages/app/src/main.ts"
    ignored_idx = "packages/ignored/index.ts"
    files = {
        core_idx: [],
        core_utils: [],
        ignored_idx: [],
        app_main: ["@scope/core/utils", "@scope/ignored"],
    }
    parsed = []
    for rel, imports in files.items():
        full = tmp_path / rel
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text("")
        parsed.append({"path": rel, "lang_id": "typescript", "raw_imports": imports, "classes": [], "functions": []})

    sensor = NetworkRiskSensor()
    sensor.root = str(tmp_path)
    edges = set(sensor.resolve_import_edges(parsed))
    assert (app_main, core_utils) in edges
    assert (app_main, ignored_idx) not in edges


def test_workspace_sibling_main_without_exports(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"workspaces": {"packages": ["pkgs/*"]}}))
    (tmp_path / "pkgs" / "lib").mkdir(parents=True)
    (tmp_path / "pkgs" / "lib" / "package.json").write_text(json.dumps({"name": "@acme/lib", "main": "src/entry.ts"}))
    (tmp_path / "pkgs" / "web").mkdir(parents=True)
    (tmp_path / "pkgs" / "web" / "package.json").write_text(json.dumps({"name": "@acme/web"}))

    lib_entry = "pkgs/lib/src/entry.ts"
    web_app = "pkgs/web/src/app.ts"
    parsed = []
    for rel, imports in ((lib_entry, []), (web_app, ["@acme/lib"])):
        full = tmp_path / rel
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text("")
        parsed.append({"path": rel, "lang_id": "typescript", "raw_imports": imports, "classes": [], "functions": []})

    sensor = NetworkRiskSensor()
    sensor.root = str(tmp_path)
    edges = set(sensor.resolve_import_edges(parsed))
    assert (web_app, lib_entry) in edges
