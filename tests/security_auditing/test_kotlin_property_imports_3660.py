"""
#3660: a Kotlin import can name a top-level PROPERTY (`import a.b.metadata.isPrimary` for
`internal val KmConstructor.isPrimary`). #3596's declaration index held only functions and
classes, so kotlinpoet's 17 such imports resolved to nothing. kotlin's `_declaration_capture`
records a file's top-level property names as `declared_names`; the resolver indexes them;
file_data persists them so a delta scan resolves the same edges (the #3220 raw_imports
precedent). Measured by tests/tools/import_graph_accuracy.py on square/kotlinpoet.
"""

import sqlite3
import time

import pytest

from gitgalaxy.core.network_risk_sensor import NetworkRiskSensor
from gitgalaxy.core.state_rehydrator import StateRehydrator
from gitgalaxy.recorders.record_keeper import RecordKeeper
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_CAPTURE = LANGUAGE_DEFINITIONS["kotlin"]["rules"]["_declaration_capture"]


def _declared(code: str) -> list[str]:
    return [m.group(1) for m in _CAPTURE.finditer(code)]


# ----------------------------------------------------------------------------- the capture


@pytest.mark.parametrize(
    "line, name",
    [
        ("internal val KmConstructor.isPrimary: Boolean", "isPrimary"),
        ("public val KmType.isExtensionType: Boolean", "isExtensionType"),
        ("internal val KM_PROPERTY_COMPARATOR =", "KM_PROPERTY_COMPARATOR"),
        ("val <T> List<T>.head: T get() = first()", "head"),
        ("const val MAX = 3", "MAX"),
        ("@JvmField val FLAG = true", "FLAG"),
        ('@get:JvmName("x") val Foo.bar get() = 1', "bar"),
        ("var counter by lazy { 0 }", "counter"),
        ("val x: Map<String, Int> = mapOf()", "x"),
    ],
)
def test_a_top_level_property_is_declared(line, name):
    assert _declared(line + "\n") == [name]


@pytest.mark.parametrize(
    "code",
    [
        "private val KmType?.simpleName: String\n",  # no other file can import it
        "class A {\n  val member = 1\n}\n",  # a member is indented
        "fun f() { val local = 2 }\n",
        "object O {\n    val indented = 2\n}\n",
    ],
)
def test_a_non_importable_val_is_not_declared(code):
    # Comments never reach the capture: the scan runs it over prism's code stream.
    assert _declared(code) == []


def test_the_capture_is_a_helper_rule():
    # `_`-prefixed like `_dependency_capture`: a compiled helper, never a counted signal.
    assert hasattr(_CAPTURE, "finditer")


@pytest.mark.parametrize(
    "payload",
    [
        "val " + "a." * 50000,
        "@" + "a" * 100000,
        "val <" + "T" * 100000,
        "val " + "A<" * 50000,
        ("internal " * 20000) + "val x",
    ],
)
def test_the_capture_stays_linear(payload):
    start = time.perf_counter()
    _declared(payload)
    assert time.perf_counter() - start < 3.0


# ----------------------------------------------------------------------------- resolution

_UTIL = "interop/kotlin-metadata/src/main/kotlin/com/squareup/kotlinpoet/metadata/util.kt"
_IMPORTER = "interop/kotlin-metadata/src/main/kotlin/com/squareup/kotlinpoet/metadata/specs/Inspector.kt"


def _files(declared):
    return [
        {
            "path": _IMPORTER,
            "lang_id": "kotlin",
            "raw_imports": ["com.squareup.kotlinpoet.metadata.isPrimary"],
            "classes": [],
            "functions": [],
        },
        {"path": _UTIL, "lang_id": "kotlin", "raw_imports": [], "classes": [], "functions": [], **declared},
    ]


def test_an_import_of_a_top_level_property_resolves_to_its_file():
    edges = set(NetworkRiskSensor().resolve_import_edges(_files({"declared_names": ["isPrimary"]})))
    assert edges == {(_IMPORTER, _UTIL)}


def test_without_declared_names_it_stays_unresolved():
    assert set(NetworkRiskSensor().resolve_import_edges(_files({}))) == set()


# ----------------------------------------------------------------------------- persistence

SESSION = {
    "target": "KtRepo",
    "git_audit": {"commit_hash": "k3660", "latest_commit_date": "2026-09-26T00:00:00Z"},
}


def test_declared_names_persist_and_rehydrate(tmp_path):
    db = tmp_path / "k.db"
    files = _files({"declared_names": ["isPrimary", "KM_PROPERTY_COMPARATOR"]})
    RecordKeeper().record_mission(files, [], {}, SESSION, str(db))
    conn = sqlite3.connect(db)
    try:
        rows = dict(conn.execute("SELECT file_path, declared_names FROM file_data").fetchall())
    finally:
        conn.close()
    assert rows[_UTIL] == '["KM_PROPERTY_COMPARATOR", "isPrimary"]'
    assert rows[_IMPORTER] is None  # none declared: NULL, not "[]"

    cache = StateRehydrator(str(db)).load_state("KtRepo")["ram_cache"]
    assert cache[_UTIL]["declared_names"] == ["KM_PROPERTY_COMPARATOR", "isPrimary"]
    assert cache[_IMPORTER]["declared_names"] == []
    restored = [{"path": path, **node} for path, node in sorted(cache.items())]
    assert set(NetworkRiskSensor().resolve_import_edges(restored)) == {(_IMPORTER, _UTIL)}
