"""#4125: a Kotlin import of a top-level function overloaded across several files of one package
(`import com.squareup.kotlinpoet.ksp.toKModifier` declared in both `Modifiers.kt` and `Visibilities.kt`)
links the importer to every declaring file in that package.
"""

from gitgalaxy.core.network_risk_sensor import NetworkRiskSensor


def test_kotlin_overloaded_top_level_function_import_links_all_declaring_files():
    files = [
        {
            "path": "interop/ksp/test-processor/src/main/kotlin/TestProcessor.kt",
            "lang_id": "kotlin",
            "raw_imports": ["com.squareup.kotlinpoet.ksp.toKModifier"],
        },
        {
            "path": "interop/ksp/src/main/kotlin/com/squareup/kotlinpoet/ksp/Modifiers.kt",
            "lang_id": "kotlin",
            "raw_imports": [],
            "functions": [{"name": "toKModifier"}],
        },
        {
            "path": "interop/ksp/src/main/kotlin/com/squareup/kotlinpoet/ksp/Visibilities.kt",
            "lang_id": "kotlin",
            "raw_imports": [],
            "functions": [{"name": "toKModifier"}],
        },
        {
            "path": "interop/ksp/src/main/kotlin/com/squareup/kotlinpoet/other/Unrelated.kt",
            "lang_id": "kotlin",
            "raw_imports": [],
            "functions": [{"name": "toKModifier"}],
        },
    ]
    edges = NetworkRiskSensor()._resolve_edges(files)
    assert set(edges) == {
        (
            "interop/ksp/test-processor/src/main/kotlin/TestProcessor.kt",
            "interop/ksp/src/main/kotlin/com/squareup/kotlinpoet/ksp/Modifiers.kt",
        ),
        (
            "interop/ksp/test-processor/src/main/kotlin/TestProcessor.kt",
            "interop/ksp/src/main/kotlin/com/squareup/kotlinpoet/ksp/Visibilities.kt",
        ),
    }


def test_kotlin_overloaded_import_excludes_test_files_for_production_importer():
    files = [
        {
            "path": "src/main/kotlin/app/Main.kt",
            "lang_id": "kotlin",
            "raw_imports": ["pkg.helper"],
        },
        {
            "path": "src/main/kotlin/pkg/A.kt",
            "lang_id": "kotlin",
            "raw_imports": [],
            "functions": [{"name": "helper"}],
        },
        {
            "path": "src/main/kotlin/pkg/B.kt",
            "lang_id": "kotlin",
            "raw_imports": [],
            "functions": [{"name": "helper"}],
        },
        {
            "path": "src/test/kotlin/pkg/TestHelper.kt",
            "lang_id": "kotlin",
            "raw_imports": [],
            "functions": [{"name": "helper"}],
        },
    ]
    edges = NetworkRiskSensor()._resolve_edges(files)
    assert set(edges) == {
        ("src/main/kotlin/app/Main.kt", "src/main/kotlin/pkg/A.kt"),
        ("src/main/kotlin/app/Main.kt", "src/main/kotlin/pkg/B.kt"),
    }


def test_kotlin_test_importer_prefers_production_over_test_decoy():
    files = [
        {
            "path": "src/jvmTest/kotlin/app/SpecTest.kt",
            "lang_id": "kotlin",
            "raw_imports": ["pkg.asTypeName"],
        },
        {
            "path": "src/jvmMain/kotlin/pkg/TypeName.kt",
            "lang_id": "kotlin",
            "raw_imports": [],
            "functions": [{"name": "asTypeName"}],
        },
        {
            "path": "src/jvmTest/kotlin/pkg/TypeNameTest.kt",
            "lang_id": "kotlin",
            "raw_imports": [],
            "functions": [{"name": "asTypeName"}],
        },
    ]
    edges = NetworkRiskSensor()._resolve_edges(files)
    assert set(edges) == {
        ("src/jvmTest/kotlin/app/SpecTest.kt", "src/jvmMain/kotlin/pkg/TypeName.kt"),
    }
