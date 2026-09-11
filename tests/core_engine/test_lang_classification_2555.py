"""
#2555 -- Language-classification consistency regression tests.

Covers the three defects reported against a single `galaxyscope --llm-only` scan of
expressjs/express:

  1. Dominant-language inconsistency: the MACRO STATE "Dominant Lang" named a
     documentation language (PLAINTEXT) while the COMPOSITION table showed a code
     language (JAVASCRIPT 53.8%) as the clear majority.
  2. `.js` over-exclusion: the aperture's Semantic Infrastructure & Test Target Shield
     dropped a real project's own lib/test/examples source because a recognized manifest
     did not confer project scope.
  3. Extension quoting artifact: a `git ls-files` quotepath artifact leaked a stray
     trailing `"` into the extracted extension and the exclusion reason string.
"""

import json

import pytest

from gitgalaxy.core.aperture import ApertureFilter
from gitgalaxy.core.guidestar_lens import GuideStarLens
from gitgalaxy.metrics.signal_processor import SignalProcessor

# ==============================================================================
# MOCK CALIBRATION
# ==============================================================================
MOCK_REGISTRY = {
    "javascript": {"extensions": [".js"], "exact_matches": []},
    "python": {"extensions": [".py"], "exact_matches": []},
    "markdown": {"extensions": [".md"], "exact_matches": ["README.md"]},
}

MOCK_APERTURE_CONFIG = {
    "SECRETS_EXACT": set(),
    "SECRETS_EXTENSIONS": set(),
    "MAX_FILE_SIZE_MB": 10,
    "MAX_FILE_SIZE_HARD_MB": 100,
    "MAX_LINE_LENGTH": 500,
    "IGNORED_DIRECTORIES": {"node_modules", ".git"},
    "IGNORED_EXTENSIONS": {".exe", ".dll"},
    "CONTRABAND_PATTERNS": ["*-min.js", "*.bundle.js"],
}

MOCK_GUIDESTAR_CONFIG = {
    "MANIFEST_MAP": {
        "package.json": "javascript",
        "pyproject.toml": "python",
    },
    "INTENT_BIASED_SECTORS": ["src"],
    "EXEC_PREFIX_MAP": {},
}


@pytest.fixture
def filter_engine(tmp_path):
    return ApertureFilter(
        root_dir=tmp_path,
        language_definitions=MOCK_REGISTRY,
        aperture_config=MOCK_APERTURE_CONFIG,
    )


# ==============================================================================
# DEFECT 1: DOMINANT LANG MUST NOT BE A DOCUMENTATION LANGUAGE OVER REAL CODE
# ==============================================================================
def test_dominant_lang_ignores_documentation_when_code_present():
    """
    A handful of large plaintext files can out-rank code on summed structural `impact`
    (docs get impact from a full-line-count basis). The dominant language of a codebase
    that contains code must be a code language, matching the COMPOSITION table.
    """
    proc = SignalProcessor()
    composition = {
        # plaintext wins on raw impact, but is documentation
        "plaintext": {"files": 5, "loc": 1, "impact": 500.0},
        # javascript is the real majority (highest files/loc), lower impact
        "javascript": {"files": 43, "loc": 1167, "impact": 120.0},
        "python": {"files": 2, "loc": 40, "impact": 30.0},
    }
    assert proc._get_dominant_lang(composition) == "javascript"


def test_dominant_lang_picks_highest_impact_code_lang():
    """Among code languages the deliberate impact-weighting still decides the winner."""
    proc = SignalProcessor()
    composition = {
        "markdown": {"files": 10, "loc": 9000, "impact": 999.0},  # docs -> excluded
        "python": {"files": 3, "loc": 50, "impact": 5.0},
        "c": {"files": 2, "loc": 30, "impact": 50.0},  # highest-impact code lang
    }
    assert proc._get_dominant_lang(composition) == "c"


def test_dominant_lang_falls_back_to_docs_when_no_code():
    """An all-documentation repo may legitimately report a documentation language."""
    proc = SignalProcessor()
    composition = {
        "plaintext": {"files": 4, "loc": 10, "impact": 40.0},
        "markdown": {"files": 6, "loc": 20, "impact": 90.0},
    }
    assert proc._get_dominant_lang(composition) == "markdown"


def test_dominant_lang_empty_is_mixed():
    assert SignalProcessor()._get_dominant_lang({}) == "mixed"


# ==============================================================================
# DEFECT 2: MANIFEST-AWARE PROJECT SCOPE
# ==============================================================================
def test_root_manifest_grants_project_scope(tmp_path):
    """A manifest at the scan root flips has_manifest_scope."""
    (tmp_path / "package.json").write_text(json.dumps({"main": "index.js"}), encoding="utf-8")
    lens = GuideStarLens(root_path=tmp_path, guidestar_config=MOCK_GUIDESTAR_CONFIG)
    lens.scan_project_config()
    assert lens.has_manifest_scope is True


def test_nested_manifest_does_not_grant_project_scope(tmp_path):
    """A manifest buried in a subdirectory must NOT confer whole-scan project scope --
    this is what keeps manifest-less corpus scans (e.g. language-crucible's data/ root)
    fully shielded."""
    nested = tmp_path / "packages" / "widget"
    nested.mkdir(parents=True)
    (nested / "package.json").write_text(json.dumps({"main": "index.js"}), encoding="utf-8")
    lens = GuideStarLens(root_path=tmp_path, guidestar_config=MOCK_GUIDESTAR_CONFIG)
    lens.scan_project_config()
    assert lens.has_manifest_scope is False


def test_project_scope_stands_down_infra_shield_but_keeps_ignored_dirs(filter_engine):
    """With project scope, a real project's own lib/test/examples source survives the
    infra/test shield, but node_modules/vendor are still dropped by IGNORED_DIRECTORIES."""
    shielded_source = ("lib/index.js", "test/app.test.js", "examples/mvc/lib/boot.js", "spec/foo_spec.js")

    # Default (no manifest scope): the shield drops first-class source.
    for path in shielded_source:
        assert filter_engine._check_ignore_rules(path) is False, path

    # Project scope stands the shield down.
    filter_engine.manifest_project_scope = True
    for path in shielded_source:
        assert filter_engine._check_ignore_rules(path) is True, path

    # ...but hard-ignored directories are still excluded (independent gate).
    for still_blocked in ("node_modules/express/index.js", "src/app.bundle.js"):
        assert filter_engine._check_ignore_rules(still_blocked) is False, still_blocked


# ==============================================================================
# DEFECT 3: EXTENSION QUOTING ARTIFACT MUST NOT LEAK INTO THE REASON STRING
# ==============================================================================
def test_malformed_extension_not_leaked_into_reason(filter_engine, tmp_path):
    """A path carrying a stray quote (quotepath artifact) must not surface a malformed
    extension like `.txt"` in the human-readable exclusion reason."""
    # #2961: do NOT create the file on disk -- `"` is a legal filename char on
    # POSIX (where a git quotepath artifact can actually produce this name) but
    # illegal on Windows, so `write_text` raised OSError: [Errno 22] on the
    # Windows CI legs before any assertion ran. evaluate_path_integrity is
    # "Gate 1: Zero-I/O Path Evaluation" -- the malformed-extension sanitization
    # is pure string analysis of the path and size_bytes falls back to 0 when the
    # file is absent, so evaluating the constructed Path alone keeps this test
    # meaningful (and cross-platform) without touching the filesystem.
    bad = tmp_path / 'naive.txt"'

    is_valid, _, reason = filter_engine.evaluate_path_integrity(bad, has_intent=False)
    assert is_valid is False
    assert '"' not in reason, reason
    assert "no_extension" in reason, reason


def test_clean_extension_still_reported(filter_engine, tmp_path):
    """A genuinely unsupported but well-formed extension is reported verbatim."""
    f = tmp_path / "notes.xyz"
    f.write_text("data", encoding="utf-8")

    is_valid, _, reason = filter_engine.evaluate_path_integrity(f, has_intent=False)
    assert is_valid is False
    assert ".xyz" in reason
