"""#4943: an import never resolves to a configuration / data / prose file.

CI workflows became scanned files (#4928), so `.github/workflows/dart.yml` joined the name
index and a Dart `dart` token drew five false edges (graph-accuracy-audit, dart-lang/http).
"""

import pytest

from gitgalaxy.core.network_risk_sensor import NetworkRiskSensor


def _edges(importer_lang, importer_path, token, decoy_path, decoy_lang):
    files = [
        {"path": importer_path, "lang_id": importer_lang, "raw_imports": [token]},
        {"path": decoy_path, "lang_id": decoy_lang, "raw_imports": []},
    ]
    return {dst for (_src, dst) in NetworkRiskSensor()._resolve_edges(files)}


DECOYS = [
    (".github/workflows/dart.yml", "yaml", "dart"),
    ("config/dart.json", "json", "dart"),
    ("docs/dart.md", "markdown", "dart"),
    ("notes/dart.txt", "plaintext", "dart"),
    ("data/dart.csv", "csv", "dart"),
]


@pytest.mark.parametrize("decoy_path, decoy_lang, token", DECOYS)
def test_dart_token_never_resolves_to_data_file(decoy_path, decoy_lang, token):
    assert _edges("dart", "pkgs/a/lib/a.dart", token, decoy_path, decoy_lang) == set()


@pytest.mark.parametrize("lang, path", [("python", "a.py"), ("go", "a.go"), ("ruby", "a.rb"), ("java", "A.java")])
def test_other_importers_ignore_workflow_decoy(lang, path):
    assert _edges(lang, path, "dart", ".github/workflows/dart.yml", "yaml") == set()


def test_real_dart_target_still_resolves_beside_decoy():
    files = [
        {"path": "a/lib/a.dart", "lang_id": "dart", "raw_imports": ["b.dart"]},
        {"path": "a/lib/b.dart", "lang_id": "dart", "raw_imports": []},
        {"path": ".github/workflows/b.yml", "lang_id": "yaml", "raw_imports": []},
    ]
    assert {d for (_s, d) in NetworkRiskSensor()._resolve_edges(files)} == {"a/lib/b.dart"}


def test_token_spelling_the_data_extension_still_resolves():
    assert _edges("javascript", "src/a.js", "./data.json", "src/data.json", "json") == {"src/data.json"}
