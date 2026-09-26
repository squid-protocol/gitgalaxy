"""
Import resolution: build variants and symlinked copies (#3665, import contract C8), a
solidity relative path that names no file, and dart conditional imports (#3660). Measured
by tests/tools/import_graph_accuracy.py on circe, SDWebImage, openzeppelin-contracts and
dart-lang/http; these pin each shape.
"""

import os

import pytest

from gitgalaxy.core.network_risk_sensor import NetworkRiskSensor
from gitgalaxy.galaxyscope import extract_raw_imports
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _edges(files, root=None):
    """Resolved (importer, imported) pairs for a list of (path, lang_id, raw_imports)."""
    parsed = [{"path": p, "lang_id": lang, "raw_imports": list(imps), "classes": []} for p, lang, imps in files]
    sensor = NetworkRiskSensor()
    sensor.root = root
    return set(sensor.resolve_import_edges(parsed))


# ----------------------------------------------------------------------------- #3665 build variants

_SEMIAUTO_2 = "modules/generic/shared/src/main/scala-2/io/circe/generic/semiauto.scala"
_SEMIAUTO_3 = "modules/generic/shared/src/main/scala-3/io/circe/generic/semiauto.scala"


@pytest.mark.parametrize("variant, target", [("scala-2", _SEMIAUTO_2), ("scala-3", _SEMIAUTO_3)])
def test_an_import_means_the_copy_of_the_importers_own_build(variant, target):
    importer = f"modules/generic/shared/src/test/{variant}/io/circe/generic/Suite.scala"
    edges = _edges(
        [
            (importer, "scala", ["io.circe.generic.semiauto._"]),
            (_SEMIAUTO_2, "scala", []),
            (_SEMIAUTO_3, "scala", []),
        ]
    )
    assert edges == {(importer, target)}


def test_an_importer_in_no_variant_stays_ambiguous():
    # `src/test/scala/` compiles against both builds: nothing picks one.
    importer = "modules/generic/shared/src/test/scala/io/circe/generic/Suite.scala"
    edges = _edges(
        [
            (importer, "scala", ["io.circe.generic.semiauto._"]),
            (_SEMIAUTO_2, "scala", []),
            (_SEMIAUTO_3, "scala", []),
        ]
    )
    assert edges == set()


@pytest.mark.parametrize(
    "candidates, importer, expected",
    [
        (["a/jvm/src/X.scala", "a/js/src/X.scala"], "a/jvm/src/Y.scala", "a/jvm/src/X.scala"),
        # different depths: not parallel trees
        (["a/jvm/src/X.scala", "a/src/X.scala"], "a/jvm/src/Y.scala", None),
        # two differing segments: not one variant axis
        (["a/jvm/x/X.scala", "a/js/y/X.scala"], "a/jvm/x/Y.scala", None),
        # the importer sits in both variant names: nothing singles one out
        (["p/jvm/X.scala", "p/js/X.scala"], "jvm/js/Y.scala", None),
        (["m/scala-2.12/X.scala", "m/scala-2.13+/X.scala"], "t/scala-2.13+/Y.scala", "m/scala-2.13+/X.scala"),
        # sibling modules are not build variants (#261): the nearest same-named file is a guess
        (["service_a/utils.py", "service_b/utils.py"], "service_a/app.py", None),
        (["src/cobol_copy/CREACC.cpy", "src/cobol_src/CREACC.cbl"], "src/cobol_src/X.cbl", None),
    ],
)
def test_build_variant_only_decides_parallel_trees(candidates, importer, expected):
    assert NetworkRiskSensor._build_variant(candidates, importer) == expected


# ----------------------------------------------------------------------------- #3665/#3660 symlinks


@pytest.fixture
def linked_headers(tmp_path):
    # SDWebImage: include/SDWebImage/X.h -> ../../Core/X.h, and the MapKit include of a MapKit file.
    for rel in ("SDWebImage/Core/SDWebImageCompat.h", "SDWebImageMapKit/MapKit/MK+WebCache.h"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("#import <Foundation/Foundation.h>\n")
    links = {
        "SDWebImage/include/SDWebImage/SDWebImageCompat.h": "../../Core/SDWebImageCompat.h",
        "SDWebImageMapKit/include/SDWebImageMapKit/MK+WebCache.h": "../../MapKit/MK+WebCache.h",
    }
    for rel, target in links.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        try:
            os.symlink(target, tmp_path / rel)
        except (OSError, NotImplementedError):
            pytest.skip("symlinks not available")
    return tmp_path


def _objc_files(importer_imports):
    return [
        ("SDWebImage/Private/SDAssociatedObject.h", "objective-c", importer_imports),
        ("SDWebImage/Core/SDWebImageCompat.h", "objective-c", []),
        ("SDWebImage/include/SDWebImage/SDWebImageCompat.h", "objective-c", []),
        ("SDWebImageMapKit/MapKit/MK+WebCache.h", "objective-c", []),
        ("SDWebImageMapKit/include/SDWebImageMapKit/MK+WebCache.h", "objective-c", []),
    ]


def test_two_paths_to_one_file_are_one_candidate(linked_headers):
    edges = _edges(_objc_files(["SDWebImageCompat.h"]), root=str(linked_headers))
    # the real file, not the link
    assert edges == {("SDWebImage/Private/SDAssociatedObject.h", "SDWebImage/Core/SDWebImageCompat.h")}


def test_without_a_root_the_pair_stays_ambiguous(linked_headers):
    assert _edges(_objc_files(["SDWebImageCompat.h"])) == set()


def test_a_spelled_path_still_names_the_path_it_spells(linked_headers):
    edges = _edges(_objc_files(["SDWebImage/SDWebImageCompat.h"]), root=str(linked_headers))
    assert edges == {("SDWebImage/Private/SDAssociatedObject.h", "SDWebImage/include/SDWebImage/SDWebImageCompat.h")}


def test_a_directory_no_candidate_has_is_not_collapsed_into_an_edge(linked_headers):
    # `<SDWebImage/MK+WebCache.h>` names a path that only exists under SDWebImageMapKit/.
    edges = _edges(_objc_files(["SDWebImage/MK+WebCache.h"]), root=str(linked_headers))
    assert edges == set()


def test_two_real_files_with_one_name_stay_ambiguous(tmp_path):
    for rel in ("a/X.h", "b/X.h"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("")
    files = [("c/Y.m", "objective-c", ["X.h"]), ("a/X.h", "objective-c", []), ("b/X.h", "objective-c", [])]
    assert _edges(files, root=str(tmp_path)) == set()


# ----------------------------------------------------------------------------- #3660 solidity


def test_solidity_relative_import_naming_no_file_draws_no_edge():
    # openzeppelin: fv/harnesses import ../patched/access/AccessControl.sol, generated at build time.
    files = [
        ("fv/harnesses/AccessControlHarness.sol", "solidity", ["../patched/access/AccessControl.sol"]),
        ("contracts/access/AccessControl.sol", "solidity", []),
    ]
    assert _edges(files) == set()


def test_solidity_relative_import_naming_a_file_still_resolves():
    files = [
        ("contracts/token/ERC20.sol", "solidity", ["../utils/Context.sol"]),
        ("contracts/utils/Context.sol", "solidity", []),
    ]
    assert _edges(files) == {("contracts/token/ERC20.sol", "contracts/utils/Context.sol")}


def test_relative_imports_are_exact_is_top_level_not_a_rule():
    # #2806: a non-pattern key inside `rules` would be re.compile()d by language_lens.
    assert LANGUAGE_DEFINITIONS["solidity"].get("relative_imports_are_exact") is True
    assert "relative_imports_are_exact" not in LANGUAGE_DEFINITIONS["solidity"]["rules"]


# ----------------------------------------------------------------------------- #3660 dart


def _dart_imports(code: str) -> set[str]:
    lang = LANGUAGE_DEFINITIONS["dart"]
    return extract_raw_imports(lang["rules"]["_dependency_capture"], code, lang)


def test_dart_conditional_import_alternatives_are_imports():
    code = (
        "import 'client_stub.dart'\n"
        "    if (dart.library.js_interop) 'browser_client.dart'\n"
        "    if (dart.library.io) 'io_client.dart';\n"
        "export 'b.dart' if (dart.library.html) 'c.dart';\n"
    )
    assert _dart_imports(code) == {"client_stub.dart", "browser_client.dart", "io_client.dart", "b.dart", "c.dart"}


def test_dart_collection_if_is_not_an_import():
    assert _dart_imports("final xs = ['a', if (debug) 'b.dart'];\n") == set()


@pytest.mark.parametrize(
    "payload",
    [
        "'" + " " * 100000,
        "' if (" + "x" * 100000,
        ("'\n if (a) 'b'" * 20000),
        "import '" + "a" * 100000,
    ],
)
def test_dart_capture_stays_linear(payload):
    import time

    start = time.perf_counter()
    _dart_imports(payload)
    assert time.perf_counter() - start < 3.0
