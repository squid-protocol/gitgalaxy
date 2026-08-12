import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

# ==============================================================================
# THE COUPLING MASS GAUNTLET
# Proves that the `args` spawner accurately isolates parameter blocks
# across major languages without triggering ReDoS on complex nested types.
# ==============================================================================
# ==============================================================================
# THE COUPLING MASS GAUNTLET
# Proves that the `args` spawner accurately isolates parameter blocks
# across major languages without triggering ReDoS on complex nested types.
# ==============================================================================
ARGS_EXTRACTION_CASES = {
    "php": {
        "valid": [
            ("function TargetFunc(int $a, ?string $b) {", "TargetFunc"),
            ("public function TargetFunc(array $items): void", "TargetFunc"),
        ],
        "invalid": ["TargetFunc($a, $b);", "if ($a == $b) {"],
        "pathological": [
            # Vertical spacing with default arrays and closure callbacks
            (
                "public \n function \n TargetFunc \n (\n  ?ArrayObject $items = [],\n  Closure $cb = fn($x) => $x\n)",
                "TargetFunc",
            )
        ],
    },
    # objective-c: removed from this legacy monolithic file (#1335) -- fully
    # superseded by tests/extraction/languages/test_objectivec.py, which
    # covers the args gauntlet in far more depth (per epic #813's migration
    # of per-language cases out of these four old dict files) and reflects
    # #1335's fix (untyped keyword-message params, e.g. `back:sender`, are
    # now recognized). This file's stale `"invalid": ["[self
    # TargetFunc:a withB:b];", ...]` case encoded a pre-#1335 assumption
    # that's no longer true in isolation -- see test_objectivec.py's
    # test_objc_args_known_limitation_body_lookalikes_shielded_by_pipeline
    # for why a keyword-message SEND (indistinguishable in isolation from a
    # keyword-message method SIGNATURE) is a documented, pipeline-shielded
    # limitation of the regex now, not a live bug.
    "dart": {
        "valid": [
            ("void TargetFunc(String a, int b) {", "TargetFunc"),
            ("Future<int> TargetFunc(List<T> items) async {", "TargetFunc"),
        ],
        "invalid": ["TargetFunc(a, b);", "if (a > b) {"],
        "pathological": [
            # Vertical formatting with nested function type parameters
            # FIX: Added `\n {` to complete the structural definition
            (
                "Future<void> \n TargetFunc \n <T> \n (\n  List<T> items,\n  void Function(int, String) callback\n) \n {",
                "TargetFunc",
            )
        ],
    },
}


class TestArgsExtraction:
    @pytest.mark.parametrize("lang_id", ARGS_EXTRACTION_CASES.keys())
    def test_positive_args_extraction(self, lang_id):
        cases = ARGS_EXTRACTION_CASES.get(lang_id, {})
        if "valid" not in cases:
            pytest.skip(f"No valid cases defined for {lang_id}")

        pattern = LANGUAGE_DEFINITIONS[lang_id]["rules"].get("args")
        if not pattern:
            pytest.skip(f"No args pattern defined for {lang_id}")

        for payload, expected_name in cases["valid"]:
            match = pattern.search(payload)
            assert match is not None, f"[{lang_id}] Iron Wall Blocked Valid Args: '{payload}'"

    @pytest.mark.parametrize("lang_id", ARGS_EXTRACTION_CASES.keys())
    def test_negative_args_extraction(self, lang_id):
        cases = ARGS_EXTRACTION_CASES.get(lang_id, {})
        if "invalid" not in cases:
            pytest.skip(f"No invalid cases defined for {lang_id}")

        pattern = LANGUAGE_DEFINITIONS[lang_id]["rules"].get("args")
        if not pattern:
            pytest.skip(f"No args pattern defined for {lang_id}")

        for payload in cases["invalid"]:
            match = pattern.search(payload)
            assert match is None, f"[{lang_id}] 👻 GHOST ARGS HALLUCINATED! Erroneously matched args on: '{payload}'"

    @pytest.mark.parametrize("lang_id", ARGS_EXTRACTION_CASES.keys())
    def test_pathological_args_extraction(self, lang_id):
        cases = ARGS_EXTRACTION_CASES.get(lang_id, {})
        if "pathological" not in cases:
            pytest.skip(f"No pathological cases defined for {lang_id}")

        pattern = LANGUAGE_DEFINITIONS[lang_id]["rules"].get("args")
        if not pattern:
            pytest.skip(f"No args pattern defined for {lang_id}")

        for payload, expected_name in cases["pathological"]:
            match = pattern.search(payload)
            assert match is not None, f"[{lang_id}] 💥 Engine choked on pathological args formatting: '{payload}'"
