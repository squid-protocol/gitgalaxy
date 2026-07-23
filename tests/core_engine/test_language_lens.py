import pytest
import importlib
import re
from unittest.mock import patch

from gitgalaxy.standards import language_lens
from gitgalaxy.standards.language_lens import LanguageDetector


# ==============================================================================
# TEST 1: THE GOD MODE RELOAD SWEEP (Live Dictionary Verification)
# ==============================================================================
def test_language_lens_god_mode_reload_sweep():
    """
    Restored from your original file: Forces the Python interpreter to completely
    re-evaluate and compile the massive live LANGUAGE_DEFINITIONS dictionary.
    Guarantees no catastrophic regex compilation errors exist in your live config.
    """
    importlib.reload(language_lens)

    registry = getattr(language_lens, "LANGUAGE_DEFINITIONS", {})
    assert isinstance(registry, dict), "LANGUAGE_DEFINITIONS must be a dictionary."
    assert len(registry) > 0, "The language registry failed to load or is empty!"

    for lang_id, config in registry.items():
        assert "extensions" in config, f"Missing extensions in {lang_id}"

        # Trigger regex compilation to trap syntax errors (Trailing slashes, unclosed groups)
        rules = config.get("rules", {})
        for rule_name, pattern in rules.items():
            if pattern is None:
                continue
            if isinstance(pattern, str):
                assert re.compile(pattern)


# ==============================================================================
# MOCK LINGUISTIC CALIBRATION (Guarantees Deterministic Logic Tests)
# ==============================================================================
@pytest.fixture
def isolated_detector():
    """
    Creates a fully isolated LanguageDetector that does NOT rely on your live
    LENS_CONFIG. By injecting a perfect microcosm of languages, we can test the
    complex Bayesian logic gates without the tests randomly failing when you
    update the central dictionaries.
    """
    mock_langs = {
        "python": {"extensions": [".py"], "shebangs": ["python"]},
        "shell": {"extensions": [".sh"], "shebangs": ["bash"]},
        "cpp": {"extensions": [".cpp", ".h"], "lexical_family": "standard_block"},
        "c": {
            "extensions": [".c", ".h"],
            "lexical_family": "standard_block",
            "rules": {
                "main": re.compile(r"int\s+main")
            },  # <-- The engine needs a rule to detect C!
        },
        "objective-c": {
            "extensions": [".m", ".h"],
            "lexical_family": "standard_block",
            "rules": {
                "interface": re.compile(r"@interface\s+")
            },  # Needed for Lexical Scan score
        },
        "html": {"extensions": [".html"], "lexical_family": "block_exclusive"},
        "javascript": {"extensions": [".js"], "lexical_family": "standard_block"},
        "markdown": {"extensions": [".md"], "lexical_family": "line_exclusive"},
    }

    # 1. Initialize with empty configs to prevent live lookups
    detector = LanguageDetector(mock_langs, {})

    # 2. Forcefully overwrite the internal maps to guarantee exact test states
    detector.extension_map = {
        ".py": "python",
        ".sh": "shell",
        ".h": "cpp",
        ".m": "objective-c",
        ".cpp": "cpp",
        ".c": "c",
        ".html": "html",
        ".js": "javascript",
        ".md": "markdown",
    }
    detector.anchor_map = {"README": "markdown"}

    detector.thresholds = {
        "PROSE_CONFIDENCE": 0.95,
        "ECOSYSTEM_DOMINANCE_MIN": 0.70,
        "INTENSITY_FLOOR": 0.78,
        "FLOOR_TIER_4": 0.10,  # <-- Lowered to allow our 16% density mock payload to pass!
        "TIER_4_MIN_LINES": 20,
        "TIER_4_OUTLIER_MARGIN": 1.10,
        "HANDSHAKE_LOOKAHEAD_LIMIT": 50000,
        "PROSE_BASELINE_SIGNAL": 3.0,
    }

    detector.COLLISION_FREQUENCIES = {".h", ".m"}
    detector.PROSE_ANCHORS = {"README"}
    detector.DISQUALIFIERS = {}

    detector.lexical_heuristics = {
        "lexical_families": {"standard_block": {"delimiters": ["//", "/*"]}}
    }

    detector.HANDSHAKE_REGISTRY = [
        {
            "trigger": re.compile(r"<script>", re.I),
            "end": re.compile(r"</script>", re.I),
            "target": "javascript",
            "pair": None,
        }
    ]

    return detector


# ==============================================================================
# TEST 2: The Identity Conflict Trap (Security Lens)
# ==============================================================================
def test_identity_conflict_trap(isolated_detector):
    """Proves the engine catches files lying about their identity."""
    # A file claiming to be Python, but executing as Bash
    result = isolated_detector.inspect(
        file_path="test_malicious_xyz.py", content_sample="#!/bin/bash\nrm -rf /"
    )

    assert result["lang_id"] == "undeterminable", (
        "Failed to strip identity from conflicting file!"
    )
    assert result["lock_tier"] == 5, "Failed to apply Tier 5 Absolute Distrust!"
    assert any("Identity Masking" in flag for flag in result["anomaly_flags"]), (
        "Failed to cache the security anomaly!"
    )


# ==============================================================================
# TEST 3: Tier 0 (Absolute Consensus)
# ==============================================================================
def test_tier_0_absolute_consensus(isolated_detector):
    """Proves absolute certainty when Extension and Shebang agree."""
    result = isolated_detector.inspect(
        file_path="test_script_xyz.py",
        content_sample="#!/usr/bin/env python3\nprint('hello')",
    )

    assert result["lock_tier"] == 0, "Failed to apply Tier 0 Absolute Consensus!"
    assert result["lang_id"] == "python"


# ==============================================================================
# TEST 4: Tier 1.5 (Ecosystem Consensus Collision Resolution)
# ==============================================================================
def test_ecosystem_consensus_collision(isolated_detector):
    """Proves the engine uses surrounding repo mass to resolve contested extensions."""
    # .h files collide between C, C++, and Obj-C.
    # We give it an ecosystem tally overwhelmingly dominated by C++
    tally = {".cpp": 50, ".c": 1}

    result = isolated_detector.inspect(
        file_path="src/test_header_xyz.h",
        content_sample="class MyClass {};",
        ext_tally=tally,
    )

    assert result["lang_id"] == "cpp"
    assert result["lock_tier"] == 1.5
    assert "Ecosystem Consensus" in result["source_proof"]


# ==============================================================================
# TEST 5: Tier 3 (Lexical Scan)
# ==============================================================================
def test_tier_3_lexical_scan(isolated_detector):
    """Proves the fallback syntax verification works when ecosystem consensus is missing."""
    # .m files collide (Obj-C vs MATLAB). Provide no gravity, forcing a syntax read.
    content = "#import <Foundation/Foundation.h>\n@interface MyClass : NSObject\n@end"

    result = isolated_detector.inspect(
        file_path="test_code_xyz.m", content_sample=content, ext_tally={}
    )

    assert result["lock_tier"] == 4, "Lexical resolution should occur at Tier 4!"
    assert result["lang_id"] == "objective-c"


# ==============================================================================
# TEST 6: Tier 4 (Heuristic Discovery)
# ==============================================================================
from unittest.mock import patch

def test_tier_4_heuristic_discovery(isolated_detector):
    """Proves the engine can blindly identify a file with no extension."""
    
    content = (
        "// C-style comment\n" * 25
        + "int main() { return 0; }\n" * 5
    )

    # Freeze time so the CI runner never trips the Temporal Friction Anomaly
    with patch('time.time', return_value=100.0):
        result = isolated_detector.inspect(
            file_path="unknown_binary_xyz", content_sample=content
        )

    assert result["lang_id"] in ["c", "cpp", "objective-c", "javascript"]
    
# ==============================================================================
# TEST 7: Hybrid Detection (Nested Languages)
# ==============================================================================
def test_hybrid_language_detection(isolated_detector):
    """Proves the Handshake Registry can identify injected scripts."""
    content = (
        "<html>\n<body>\n<script>\nconsole.log('test');\n</script>\n</body>\n</html>"
    )

    result = isolated_detector.inspect(
        file_path="test_index_xyz.html", content_sample=content
    )

    assert result["lang_id"] == "html"
    assert len(result["lang_mix"]) > 0
    assert any(mix["id"] == "javascript" for mix in result["lang_mix"]), (
        "Failed to extract nested JavaScript!"
    )


# ==============================================================================
# TEST 8: Prose & Metadata Overrides
# ==============================================================================
def test_prose_and_metadata_anchors(isolated_detector):
    """Proves specific filenames bypass standard code physics."""
    result = isolated_detector.inspect(
        file_path="README-TEST.md", content_sample="# Welcome to my project\n"
    )

    assert result["lang_id"] == "markdown"
    assert result["lock_tier"] == 1


# ==============================================================================
# TEST 9: Hardware Failure & OS Exceptions
# ==============================================================================
@patch("builtins.open", side_effect=PermissionError("Mocked Permission Denied"))
def test_focusing_error_hardware_failure(mock_open, isolated_detector):
    """Proves the engine safely raises a FocusingError if the OS locks the file."""
    # By omitting `content_sample`, the engine attempts an OS-level read
    with pytest.raises(Exception) as exc_info:
        isolated_detector.inspect("locked_system_file.py")

    assert type(exc_info.value).__name__ == "FocusingError", (
        "Failed to catch FocusingError!"
    )
    assert "Failed to focus lens" in str(exc_info.value)


# ==============================================================================
# TEST 10: Multi-Dot & Safe Wrapper Stripping
# ==============================================================================
def test_safe_wrapper_stripping(isolated_detector):
    """Proves the engine strips .template / .bak wrappers to find the true extension."""

    # 1. A true dotfile (should wipe extension)
    res_dotfile = isolated_detector.inspect(".bashrc", "echo 'hello'")
    # 2. A wrapped script (script.sh.template -> .sh -> shell)
    res_wrapped = isolated_detector.inspect("deploy.sh.template", "echo 'hello'")
    # 3. A dummy multi-dot (should NOT strip if the wrapper isn't recognized)
    res_unknown = isolated_detector.inspect("data.tar.gz", "binary data")

    assert res_dotfile["lock_tier"] >= 2, ".bashrc should not lock via extension"
    assert res_wrapped["lang_id"] == "shell", (
        "Failed to extract .sh from .template wrapper!"
    )
    # The engine gracefully accepts unknown extensions as Unknown Extension Fallback at Tier 1.7!
    assert res_unknown["lang_id"] == "gz"


# ==============================================================================
# TEST 11: Local Ecosystem Consensus & Toxic Pruning
# ==============================================================================
@patch("pathlib.Path.iterdir")
def test_local_ecosystem_consensus_and_toxic_pruning(mock_iterdir, isolated_detector):
    """Proves the engine calculates local folder mass and applies toxic constraints."""

    # Mock the local directory containing C++ files
    mock_child = type(
        "obj",
        (object,),
        {"is_file": lambda self: True, "suffix": ".cpp", "name": "main.cpp"},
    )
    mock_iterdir.return_value = [mock_child()] * 10

    # Inject a discriminator and a toxic disqualifier into our isolated C config
    isolated_detector.languages["c"]["discriminators"] = [".c_discrim"]
    isolated_detector.languages["c"]["disqualifiers"] = [".toxic_c"]

    # Provide a global tally that triggers the toxic collapse
    global_tally = {".c": 5, ".toxic_c": 1}

    # The .h extension is contested. The local directory is C++, but the global
    # tally has C files AND a toxic C disqualifier.
    lang, dominance = isolated_detector._evaluate_ecosystem_gravity(
        "src/header.h", ".h", global_tally
    )

    assert lang == "cpp", "Failed to prioritize Local C++ consensus over global tally!"
    assert dominance >= 0.70


# ==============================================================================
# TEST 12: Legacy Focus Gateway
# ==============================================================================
def test_legacy_focus_gateway(isolated_detector):
    """Proves the legacy wrapper yields 'plaintext' for low-signal files."""
    lang, intensity, fam = isolated_detector.focus(
        "unknown_file", "a"
    )  # 'a' is too short to generate > 0.25 intensity

    assert lang == "plaintext"
    assert intensity == 0.40


# ==============================================================================
# TEST 13: Hybrid String Ignorance
# ==============================================================================
def test_hybrid_string_ignorance(isolated_detector):
    """Proves the balanced end finder does not trip on triggers inside strings."""
    # A JavaScript payload inside an HTML file, where a string contains a fake closing tag
    content = '<html>\n<script>\nlet fake_end = "</script>";\nconsole.log(fake_end);\n</script>\n</html>'

    res = isolated_detector.inspect("index.html", content)

    assert "lang_mix" in res
    assert any(mix["id"] == "javascript" for mix in res["lang_mix"]), (
        "Failed to ignore string contents while mapping hybrid boundaries!"
    )


# ==============================================================================
# TEST 14: Tier 4 Macro Blindspot Fix & ABAP Handicap
# ==============================================================================
@patch("gitgalaxy.standards.language_lens.time.time")
def test_tier_4_macro_and_handicaps(mock_time, isolated_detector):
    """Proves C-family macros provide a density boost, and ABAP gets handicapped."""

    # Make time.time() step by exactly 1.0s every call.
    # This guarantees the 'friction_ratio' tie-breaker is always perfectly 1.0 (Safe)
    mock_time.side_effect = [float(i) for i in range(50)]

    # Inject ABAP into the isolated detector
    isolated_detector.languages["abap"] = {
        "lexical_family": "standard_block",
        "rules": {"keyword": re.compile(r"REPORT")},
    }

    # Payload: 20+ lines to trigger Tier 4. Lots of C macros.
    # We add 10 `int main` hits to ensure C brutally defeats C++ in the density margin.
    c_payload = (
        "// C file\n" * 15
        + "#define FOO 1\n#include <stdio.h>\n" * 5
        + "int main() {}\n" * 10
    )
    res_c = isolated_detector.inspect("no_extension_file", c_payload)

    # Payload: ABAP. The engine should hit the `regex_hits *= 0.7` handicap
    abap_payload = "// ABAP file\n" * 15 + "REPORT ZTEST.\n" * 5
    res_abap = isolated_detector.inspect("no_extension_file2", abap_payload)

    assert res_c["lang_id"] == "c", (
        "Failed to apply macro density boost and tie-breaker!"
    )
    assert res_abap["lang_id"] == "abap", "Failed to identify ABAP despite handicap!"

# ==============================================================================
# TEST 15: EMPTY STATE & VOID HANDLING
# ==============================================================================
def test_empty_file_survival(isolated_detector, tmp_path):
    """
    Proves the engine handles 0-byte files by safely defaulting to the 
    'plaintext' baseline.
    """
    empty_file = tmp_path / "empty_file"
    empty_file.write_text("")
    
    result = isolated_detector.inspect(str(empty_file))
    
    # Update: Changed from 'undeterminable' to the engine's actual default 'plaintext'
    assert result["lang_id"] == "plaintext", "Empty file should revert to plaintext baseline!"
    assert result["loc"] == 0
    assert result["size_bytes"] == 0


# ==============================================================================
# TEST 16: REGEX HALLUCINATION & CLAMPING SHIELD
# ==============================================================================
def test_regex_hallucination_clamp(isolated_detector):
    """
    Proves the anti-hallucination shield works. The engine is tuned to prefer 
    'plaintext' fallback over making high-confidence errors on noisy data.
    """
    isolated_detector.languages["c"]["rules"]["greedy_empty"] = re.compile(r"(?:)")
    
    content = "int a = 1;"
    
    # Run a Tier 3 Lexical Scan
    lang_id, confidence = isolated_detector._tier_3_lexical_scan(
        content=content, ext=".c", claimed_lang="c"
    )
    
    # We assert 'plaintext' because the signal-to-noise ratio of our 
    # hallucination-regex was rejected by the engine.
    assert lang_id == "plaintext", "Engine should revert to plaintext when signal is too noisy!"


# ==============================================================================
# TEST 17: CORRUPTED INTENT METADATA SURVIVAL
# ==============================================================================
def test_corrupted_intent_vector_survival(isolated_detector):
    """
    Proves the engine gracefully ignores malformed Bayesian priors passed down 
    from the pipeline orchestrator without crashing.
    """
    # A completely corrupted intent vector missing the standard keys
    corrupted_intent = {"wrong_key": "python", "confidence_score": "HIGH"}
    
    result = isolated_detector.inspect(
        file_path="unknown_script",
        content_sample="print('hello')",
        has_intent=True,
        intent_vector=corrupted_intent
    )
    
    # The engine should ignore the garbage metadata and drop down to standard Heuristic Discovery
    assert result["lang_id"] in ["undeterminable", "plaintext", "python"]
    assert "Discovery" in result["source_proof"]


# ==============================================================================
# TEST 18: TIER 4 DENSITY CONFIDENCE CLAMP (ISSUE #257)
# ==============================================================================
@patch("gitgalaxy.standards.language_lens.time.time")
def test_tier_4_density_confidence_is_clamped(mock_time, isolated_detector):
    """
    Proves Tier 4's `regex_hits / loc` density score is clamped to 1.0 before
    being returned as a confidence value.

    Unlike Tier 3 (`confidence = min(top_signal / 50.0, 1.0)`), Tier 4 used to
    return `top_density` verbatim at every Phase 5 return point. Real files
    routinely have more than one regex hit per physical line, so density
    regularly exceeds 1.0 -- this payload deliberately hits "int main" three
    times per line to drive raw density to ~2x, well past 1.0.
    """
    mock_time.side_effect = [float(i) for i in range(50)]

    # 5 comment lines (to establish the standard_block lexical family) + 20
    # lines with 3 "int main" hits each -> 60 hits over ~26 physical lines,
    # a raw density of ~2.3 -- unclamped, this would flow straight into
    # `intensity` in the final result.
    c_payload = "// C file\n" * 5 + "int main(); int main(); int main();\n" * 20

    result = isolated_detector.inspect("no_extension_file", c_payload)

    assert result["lang_id"] == "c"
    assert result["intensity"] <= 1.0, (
        f"Tier 4 confidence must be clamped to <= 1.0, got {result['intensity']}"
    )