"""#3798 (import contract C7): a Swift `import Mod` names a module, which has no file of its own.

The name index found a local `Foundation.swift` for `import Foundation` (22 false edges in
swift-argument-parser). A scoped `import struct Mod.Name` names a declaration and still resolves.
"""

import pytest

from gitgalaxy.core.network_risk_sensor import NetworkRiskSensor


def _edges(importer_lang, token, decoy_path, decoy_lang):
    files = [
        {"path": "Sources/App/main.swift", "lang_id": importer_lang, "raw_imports": [token]},
        {"path": decoy_path, "lang_id": decoy_lang, "raw_imports": []},
    ]
    return {dst for (_src, dst) in NetworkRiskSensor()._resolve_edges(files)}


@pytest.mark.parametrize("token", ["Foundation", "ArgumentParser", "Testing", "_Concurrency"])
def test_bare_module_import_draws_no_edge(token):
    assert _edges("swift", token, f"Sources/Lib/Utilities/{token}.swift", "swift") == set()


def test_scoped_import_still_resolves_to_the_declaring_file():
    assert _edges("swift", "Lib.Widget", "Sources/Lib/Widget.swift", "swift") == {"Sources/Lib/Widget.swift"}


def test_other_languages_keep_the_bare_stem_edge():
    assert _edges("dart", "util", "lib/util.dart", "dart") == {"lib/util.dart"}


def _scoped(token, decls, importer="Sources/App/main.swift"):
    """Edges from a scoped import; `decls` maps path -> declared names (as the detector records them)."""
    files = [{"path": importer, "lang_id": "swift", "raw_imports": [token]}]
    files += [
        {"path": p, "lang_id": "swift", "raw_imports": [], "classes": [{"name": n} for n in names]}
        for p, names in decls.items()
    ]
    return {dst for (_src, dst) in NetworkRiskSensor()._resolve_edges(files)}


@pytest.mark.parametrize("kind", ["struct", "class", "enum", "protocol", "typealias", "func", "var", "let"])
def test_scoped_import_finds_a_declaration_in_a_file_not_named_after_it(kind):
    decls = {"Sources/Lib/Deep/Misc.swift": ["Widget"], "Sources/Other/Widget2.swift": ["Gadget"]}
    assert _scoped("Lib.Widget", decls) == {"Sources/Lib/Deep/Misc.swift"}, kind


def test_nested_name_falls_back_to_its_owner():
    assert _scoped("Lib.Outer.Inner", {"Sources/Lib/Misc.swift": ["Outer"]}) == {"Sources/Lib/Misc.swift"}


def test_declaration_outside_the_named_target_is_not_linked():
    assert _scoped("Lib.Widget", {"Sources/Other/Widget.swift": ["Widget"]}) == set()


def _scoped_edges(token, decls, importer="Sources/App/main.swift"):
    files = [{"path": importer, "lang_id": "swift", "raw_imports": [token]}]
    files += [
        {"path": p, "lang_id": "swift", "raw_imports": [], "classes": [{"name": n} for n in names]}
        for p, names in decls.items()
    ]
    return NetworkRiskSensor()._resolve_edges(files)


def test_name_declared_in_several_files_links_each():
    decls = {"Sources/Lib/A.swift": ["Widget"], "Sources/Lib/B.swift": ["Widget"], "Sources/Lib/C.swift": ["Gadget"]}
    edges = _scoped_edges("Lib.Widget", decls)
    assert set(edges) == {
        ("Sources/App/main.swift", "Sources/Lib/A.swift"),
        ("Sources/App/main.swift", "Sources/Lib/B.swift"),
    }
    assert all(e["weight"] == 1.0 and e["import_statements"] == 1 for e in edges.values())


def test_nested_name_links_every_owner_file():
    decls = {"Sources/Lib/A.swift": ["Outer"], "Sources/Lib/B.swift": ["Outer"]}
    assert _scoped("Lib.Outer.Inner", decls) == {"Sources/Lib/A.swift", "Sources/Lib/B.swift"}


def test_several_files_stay_inside_the_named_target():
    decls = {"Sources/Lib/A.swift": ["Widget"], "Sources/Lib/B.swift": ["Widget"], "Sources/Other/C.swift": ["Widget"]}
    assert _scoped("Lib.Widget", decls) == {"Sources/Lib/A.swift", "Sources/Lib/B.swift"}


def test_several_files_in_a_test_importer_include_test_files():
    decls = {"Sources/Lib/A.swift": ["Widget"], "Tests/Lib/B.swift": ["Widget"]}
    assert _scoped("Lib.Widget", decls, importer="Tests/LibTests/T.swift") == set(decls)


def test_undeclared_name_in_the_target_draws_no_edge():
    assert _scoped("Lib.Nope", {"Sources/Lib/A.swift": ["Widget"], "Sources/Lib/B.swift": ["Widget"]}) == set()


def test_test_target_decoy_is_ignored_for_production_importer():
    decls = {"Sources/Lib/A.swift": ["Widget"], "Tests/Lib/B.swift": ["Widget"]}
    assert _scoped("Lib.Widget", decls) == {"Sources/Lib/A.swift"}


def test_declaration_capture_reads_top_level_names_only():
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    rx = LANGUAGE_DEFINITIONS["swift"]["rules"]["_declaration_capture"]
    src = (
        "public struct A {}\n@MainActor final class B {}\nextension C: P {}\nfunc d() {}\n"
        "    struct Nested {}\nprivate struct Hidden {}\ntypealias E = Int\nlet f = 1\n"
    )
    assert [m.group(1) for m in rx.finditer(src)] == ["A", "B", "C", "d", "E", "f"]
