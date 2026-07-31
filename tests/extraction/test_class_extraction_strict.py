import pytest
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

# ==============================================================================
# THE ENTITY EXTRACTION GAUNTLET
# Proves that the `class_start` spawner accurately isolates EXACTLY the class/entity
# name ("TargetEntity") across major object-oriented languages.
#
# FORMAT:
# "lang": {
#     "valid": [ ("Payload String", "Expected Extracted Name") ],
#     "invalid": [ "Strings that look like classes but MUST NOT match" ],
#     "pathological": [ "Frankenstein formatting designed to break the regex" ]
# }
# ==============================================================================
CLASS_EXTRACTION_CASES = {
    "csharp": {
        "valid": [
            ("public class TargetEntity", "TargetEntity"),
            ("internal record TargetEntity", "TargetEntity"),
            ("public interface TargetEntity<T>", "TargetEntity"),
        ],
        "invalid": [
            "var obj = new TargetEntity();",
            "public classList",
            "typeof(TargetEntity)",
        ],
        "pathological": [
            # Vertical attribute stacking, modifiers, and inheritance interfaces
            (
                '[Serializable]\n[Route("api/v1")]\npublic \n sealed \n class \n TargetEntity \n : \n IDisposable \n , \n ICloneable',
                "TargetEntity",
            )
        ],
    },
    "cpp": {
        "valid": [
            ("class TargetEntity {", "TargetEntity"),
            ("struct TargetEntity : public Base {", "TargetEntity"),
            ("template <typename T> class TargetEntity", "TargetEntity"),
        ],
        "invalid": ["enum classy {", "TargetEntity obj;", "friend class TargetEntity;"],
        "pathological": [
            # Vertical template definitions and C++ attributes
            (
                "template \n < \n typename T \n > \n class \n [[nodiscard]] \n TargetEntity \n : \n public Base",
                "TargetEntity",
            )
        ],
    },
    "php": {
        "valid": [
            ("class TargetEntity {", "TargetEntity"),
            ("abstract class TargetEntity extends Base", "TargetEntity"),
            ("interface TargetEntity", "TargetEntity"),
        ],
        "invalid": [
            "$obj = new TargetEntity();",
            "class_exists('TargetEntity')",
            "::class",
        ],
        "pathological": [
            # PHP 8 attributes and vertical spacing
            (
                "#[Attribute]\n#[Table(name: 'users')]\nfinal \n class \n TargetEntity \n implements \n Serializable",
                "TargetEntity",
            )
        ],
    },
    "swift": {
        "valid": [
            ("class TargetEntity {", "TargetEntity"),
            ("public struct TargetEntity: Protocol", "TargetEntity"),
            ("actor TargetEntity", "TargetEntity"),
        ],
        "invalid": [
            "let obj = TargetEntity()",
            "func classMethod()",
            "guard let x = TargetEntity else",
        ],
        "pathological": [
            # Swift attributes and vertical modifier stacking
            (
                "@available(iOS 14.0, *)\npublic \n final \n actor \n TargetEntity \n : \n Base",
                "TargetEntity",
            )
        ],
    },
    "kotlin": {
        "valid": [
            ("class TargetEntity {", "TargetEntity"),
            ("data class TargetEntity(", "TargetEntity"),
            ("sealed interface TargetEntity", "TargetEntity"),
        ],
        "invalid": [
            "val x = TargetEntity()",
            "fun classLike()",
            "object: TargetEntity",
        ],
        "pathological": [
            # Kotlin annotations and vertical modifier stacking
            ("@JvmInline\npublic \n data \n class \n TargetEntity \n (", "TargetEntity")
        ],
    },
    "scala": {
        "valid": [
            ("class TargetEntity {", "TargetEntity"),
            ("sealed trait TargetEntity", "TargetEntity"),
            ("case object TargetEntity", "TargetEntity"),
        ],
        "invalid": [
            "val x = new TargetEntity()",
            "def classMethod()",
            "type TargetEntity = String",
        ],
        "pathological": [
            # Scala 3 modifiers and vertical spacing
            (
                "@deprecated\nsealed \n abstract \n class \n TargetEntity \n extends \n Base",
                "TargetEntity",
            )
        ],
    },
    "dart": {
        "valid": [
            ("class TargetEntity {", "TargetEntity"),
            ("abstract class TargetEntity extends Base", "TargetEntity"),
            ("mixin TargetEntity on Base", "TargetEntity"),
        ],
        "invalid": [
            "var x = TargetEntity();",
            "import 'TargetEntity.dart';",
            "TargetEntity.fromJson()",
        ],
        "pathological": [
            # Dart 3 modifiers and vertical spacing
            (
                "abstract \n base \n mixin \n class \n TargetEntity \n extends \n Base",
                "TargetEntity",
            )
        ],
    },
    "ruby": {
        "valid": [
            ("class TargetEntity", "TargetEntity"),
            ("module TargetEntity", "TargetEntity"),
            ("class TargetEntity < Base", "TargetEntity"),
        ],
        "invalid": ["def class_method", "TargetEntity.new", "include TargetEntity"],
        "pathological": [
            # Ruby module nesting and vertical spacing
            ("class \n TargetEntity \n < \n Base", "TargetEntity")
        ],
    },
    "apex": {
        "valid": [
            ("public class TargetEntity {", "TargetEntity"),
            ("global abstract class TargetEntity implements Base", "TargetEntity"),
            ("public interface TargetEntity", "TargetEntity"),
        ],
        "invalid": [
            "TargetEntity obj = new TargetEntity();",
            "delete TargetEntity;",
            "public void classMethod()",
        ],
        "pathological": [
            # Apex sharing modifiers and vertical spacing
            (
                "@isTest\npublic \n with \n sharing \n class \n TargetEntity \n extends \n Base",
                "TargetEntity",
            )
        ],
    },
}


class TestClassExtraction:
    @pytest.mark.parametrize("lang_id", CLASS_EXTRACTION_CASES.keys())
    def test_positive_class_extraction(self, lang_id):
        """
        Proves that valid class/entity signatures are caught, and the regex
        isolates EXACTLY the entity name, stripping away modifiers and inheritances.
        """
        cases = CLASS_EXTRACTION_CASES.get(lang_id, {})
        if "valid" not in cases:
            pytest.skip(f"No valid cases defined for {lang_id}")

        pattern = LANGUAGE_DEFINITIONS[lang_id]["rules"].get("class_start")
        if not pattern:
            pytest.skip(f"No class_start pattern defined for {lang_id}")

        for payload, expected_name in cases["valid"]:
            match = pattern.search(payload)
            assert match is not None, f"[{lang_id}] Iron Wall Blocked Valid Entity: '{payload}'"

            if pattern.groups > 0:
                captured_groups = [g for g in match.groups() if g is not None]
                assert len(captured_groups) > 0, f"[{lang_id}] Regex matched but captured nothing!"
                assert expected_name in captured_groups, (
                    f"[{lang_id}] Captured dirty modifiers {captured_groups} instead of clean name '{expected_name}' from '{payload}'"
                )
            else:
                assert expected_name in match.group(0), (
                    f"[{lang_id}] Matched string {match.group(0)} failed to contain target '{expected_name}'"
                )

    @pytest.mark.parametrize("lang_id", CLASS_EXTRACTION_CASES.keys())
    def test_negative_class_extraction(self, lang_id):
        """
        Proves that structural lookalikes (instantiations, function calls)
        are explicitly ignored by the entity spawner.
        """
        cases = CLASS_EXTRACTION_CASES.get(lang_id, {})
        if "invalid" not in cases:
            pytest.skip(f"No invalid cases defined for {lang_id}")

        pattern = LANGUAGE_DEFINITIONS[lang_id]["rules"].get("class_start")
        if not pattern:
            pytest.skip(f"No class_start pattern defined for {lang_id}")

        for payload in cases["invalid"]:
            match = pattern.search(payload)
            assert match is None, (
                f"[{lang_id}] 👻 GHOST PLANET HALLUCINATED! Erroneously spawned an entity from: '{payload}'"
            )

    @pytest.mark.parametrize("lang_id", CLASS_EXTRACTION_CASES.keys())
    def test_pathological_class_extraction(self, lang_id):
        """
        Adversarial Engineering: Proves the regex can survive "Frankenstein"
        formatting, including vertical newlines, massive decorators, and
        inheritance stacking, while still cleanly extracting the entity name.
        """
        cases = CLASS_EXTRACTION_CASES.get(lang_id, {})
        if "pathological" not in cases:
            pytest.skip(f"No pathological cases defined for {lang_id}")

        pattern = LANGUAGE_DEFINITIONS[lang_id]["rules"].get("class_start")
        if not pattern:
            pytest.skip(f"No class_start pattern defined for {lang_id}")

        for payload, expected_name in cases["pathological"]:
            match = pattern.search(payload)
            assert match is not None, f"[{lang_id}] 💥 Engine choked on pathological formatting: '{payload}'"

            if pattern.groups > 0:
                captured_groups = [g for g in match.groups() if g is not None]
                assert len(captured_groups) > 0, f"[{lang_id}] Matched but captured nothing!"
                assert expected_name in captured_groups, (
                    f"[{lang_id}] Captured dirty modifiers {captured_groups} instead of clean name '{expected_name}'"
                )
            else:
                assert expected_name in match.group(0), (
                    f"[{lang_id}] Matched string failed to contain target '{expected_name}'"
                )
