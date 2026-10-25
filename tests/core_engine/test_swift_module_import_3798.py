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
