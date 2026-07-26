import os
import pytest
import json
from unittest.mock import patch

# Adjust this import to match your project structure
from gitgalaxy.core.guidestar_lens import GuideStarLens

# ==============================================================================
# MOCK HARDWARE CALIBRATION
# ==============================================================================
MOCK_GUIDESTAR_CONFIG = {
    "MANIFEST_MAP": {
        "package.json": "javascript",
        "Makefile": "unknown",
        "pyproject.toml": "python",
    },
    "INTENT_BIASED_SECTORS": ["src", "lib", "core", "api"],
    "EXEC_PREFIX_MAP": {"python": "python", "node": "javascript"},
}


@pytest.fixture
def guidestar(tmp_path):
    """Initializes the GuideStar Lens with a mocked configuration."""
    return GuideStarLens(root_path=tmp_path, guidestar_config=MOCK_GUIDESTAR_CONFIG)


# ==============================================================================
# TEST 1: THE ROADMAP SCOUT (Manifest Parsing & AI Detection)
# ==============================================================================
def test_guidestar_manifest_and_ai_detection(guidestar, tmp_path):
    """
    Proves that package.json is parsed for entry points, and that AI
    dependencies trigger the synthetic ecosystem prior.
    """
    # Create a mock package.json
    pkg_path = tmp_path / "package.json"
    pkg_data = {
        "main": "src/server.js",
        "scripts": {"start": "node dist/index.js"},
        "dependencies": {"langchain": "^0.0.1"},  # The AI trigger keyword!
    }
    pkg_path.write_text(json.dumps(pkg_data), encoding="utf-8")

    # Run the alignment phase
    guidestar.scan_project_config()

    # 1. Test standard manifest extraction
    found, lock = guidestar.get_intent_status("src/server.js")
    assert found is True
    assert lock["lang_id"] == "javascript"
    assert lock["intensity"] == 0.95
    assert "Manifest Entry" in lock["source_proof"]

    # 2. Test script extraction
    found, lock = guidestar.get_intent_status("dist/index.js")
    assert found is True
    assert lock["intensity"] == 0.85

    # 3. Test AI Ecosystem Detection
    found, lock = guidestar.get_intent_status("__gitgalaxy_meta__.json")
    assert found is True
    assert lock["intensity"] == 1.0
    assert "AI Ecosystem Lock" in lock["source_proof"]


# ==============================================================================
# TEST 2: THE AUTHORITY SCOUT (.gitattributes)
# ==============================================================================
def test_guidestar_gitattributes_authority(guidestar, tmp_path):
    """
    Proves that .gitattributes pattern rules override normal logic with
    a 0.99 confidence lock.
    """
    attr_path = tmp_path / ".gitattributes"
    # Force all .h files to be classified as C++ instead of C
    attr_path.write_text("*.h linguist-language=C++\n", encoding="utf-8")

    guidestar.scan_project_config()

    # Test a file that matches the pattern
    found, lock = guidestar.get_intent_status("include/math_ops.h")

    assert found is True
    assert lock["lang_id"] == "cpp"  # Ensure it translated C++ to cpp
    assert lock["intensity"] == 0.99
    assert "Authoritative Override" in lock["source_proof"]


# ==============================================================================
# TEST 3: THE EVASION SCOUT (.gitignore)
# ==============================================================================
def test_guidestar_gitignore_evasion_tactics(guidestar, tmp_path):
    """
    Proves that force-including a compiled binary in .gitignore triggers
    a max-priority evasion alarm (1.0 confidence).
    """
    ignore_path = tmp_path / ".gitignore"
    ignore_path.write_text(
        "node_modules/\nbuild/\n!malicious_payload.so\n", encoding="utf-8"
    )

    guidestar.scan_project_config()

    found, lock = guidestar.get_intent_status("malicious_payload.so")

    assert found is True
    assert lock["intensity"] == 1.0
    assert "Hostile Gitignore Force-Include" in lock["source_proof"]


# ==============================================================================
# TEST 4: SECTOR BIAS (The Dynamic Priority Queue)
# ==============================================================================
def test_guidestar_sector_bias(guidestar, tmp_path):
    """
    Proves that files located in structurally important directories get a
    baseline priority boost, even if they aren't explicitly in a manifest.
    """
    # /src/ is in the mocked INTENT_BIASED_SECTORS
    found, lock = guidestar.get_intent_status("src/utils/helper.js")

    assert found is True
    assert lock["lang_id"] == "unknown"  # It doesn't know the lang yet
    assert lock["intensity"] == 0.75
    assert lock["source_proof"] == "Sector Bias"

    # /temp/ is not in the biased sectors
    found, lock = guidestar.get_intent_status("temp/cache.log")
    assert found is False


# ==============================================================================
# TEST 5: DOCUMENTATION COVERAGE PRUNES IGNORED DIRECTORIES (ISSUE #256)
# ==============================================================================
def test_guidestar_documentation_coverage_prunes_ignored_dirs(tmp_path):
    """
    Proves that _calculate_documentation_coverage actually stops os.walk from
    descending into IGNORED_DIRECTORIES (e.g. node_modules), rather than just
    filtering the results after a full recursive traversal, and that the
    match is case-insensitive.

    Before the fix, `continue` only skipped file processing for the current
    directory -- os.walk still recursed into and enumerated every file under
    an ignored directory first. This spies on os.walk to assert nothing
    beneath the ignored directory is ever yielded, which only holds if
    `dirs[:]` is mutated in place. The config also deliberately mismatches
    case ("Node_Modules" vs. the on-disk "node_modules") to prove the
    comparison is lowercased on both sides.
    """
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "README.md").write_text("x" * 500, encoding="utf-8")

    ignored_dir = tmp_path / "node_modules"
    nested_dir = ignored_dir / "some-pkg"
    nested_dir.mkdir(parents=True)
    (nested_dir / "README.md").write_text("y" * 500, encoding="utf-8")

    lens = GuideStarLens(
        root_path=tmp_path,
        guidestar_config={**MOCK_GUIDESTAR_CONFIG, "IGNORED_DIRECTORIES": {"Node_Modules"}},
    )

    visited_roots = []
    real_walk = os.walk

    def spy_walk(root, *args, **kwargs):
        for root_dir, dirs, files in real_walk(root, *args, **kwargs):
            visited_roots.append(root_dir)
            yield root_dir, dirs, files

    with patch("gitgalaxy.core.guidestar_lens.os.walk", side_effect=spy_walk):
        lens._calculate_documentation_coverage()

    # os.walk must never descend into node_modules/some-pkg -- proving dirs
    # was pruned in place, not just filtered after the fact.
    assert not any(str(nested_dir) == v for v in visited_roots)

    # The ignored directory's own README must not count toward coverage.
    assert "node_modules" not in lens.documentation_coverage
    assert "src" in lens.documentation_coverage


# ==============================================================================
# TEST 6: LOCK INJECTION EDGE CASES (_inject_intent_lock / _inject_pattern_lock)
# ==============================================================================
def test_inject_intent_lock_ignores_falsy_filename(guidestar):
    """An empty/None filename must be a no-op, not crash on .strip()."""
    guidestar._inject_intent_lock("", "python", 0.9, "test")
    guidestar._inject_intent_lock(None, "python", 0.9, "test")
    assert guidestar.intent_locks == {}


def test_inject_intent_lock_whitelist_bonus(tmp_path):
    """A file on the priority whitelist gets a +0.1 confidence bonus, capped at 0.99."""
    lens = GuideStarLens(root_path=tmp_path, priority_whitelist=["main.py"], guidestar_config=MOCK_GUIDESTAR_CONFIG)
    lens._inject_intent_lock("main.py", "python", 0.95, "Some Proof")

    found, lock = lens.get_intent_status("main.py")
    assert found is True
    assert lock["intensity"] == 0.99, "Whitelist bonus should push 0.95 + 0.1, capped at 0.99!"
    assert "Whitelist Bonus" in lock["source_proof"]


def test_inject_intent_lock_does_not_downgrade_existing_higher_confidence_lock(guidestar):
    """A lower-confidence claim must never overwrite an existing higher-confidence lock."""
    guidestar._inject_intent_lock("main.py", "python", 0.95, "Authoritative Source")
    guidestar._inject_intent_lock("main.py", "javascript", 0.5, "Weak Guess")

    found, lock = guidestar.get_intent_status("main.py")
    assert found is True
    assert lock["lang_id"] == "python", "A weaker claim overwrote a stronger, pre-existing intent lock!"


def test_inject_pattern_lock_ignores_falsy_pattern(guidestar):
    """An empty pattern must be a no-op."""
    guidestar._inject_pattern_lock("", "python", 0.9, "test")
    assert guidestar.pattern_locks == {}


def test_inject_pattern_lock_does_not_downgrade_existing_higher_confidence_lock(guidestar):
    """Same non-downgrade guarantee as intent locks, for pattern locks."""
    guidestar._inject_pattern_lock("*.h", "objective-c", 0.99, "Authoritative")
    guidestar._inject_pattern_lock("*.h", "cpp", 0.5, "Weak Guess")

    assert guidestar.pattern_locks["*.h"]["lang_id"] == "objective-c"


# ==============================================================================
# TEST 7: MAKEFILE PARSING (never previously exercised -- Makefile is in
# MOCK_GUIDESTAR_CONFIG's MANIFEST_MAP, but no existing test ever creates one)
# ==============================================================================
def test_guidestar_makefile_parsing(guidestar, tmp_path):
    """
    Proves both Makefile parsing strategies: variable assignments
    (SRCS = main.c helper.c) and target lines (build: main.o), while
    correctly excluding the standard phony targets (all/clean/test/install).
    """
    makefile_path = tmp_path / "Makefile"
    makefile_path.write_text(
        "SRCS = main.c helper.c\n"
        "\n"
        "all: build\n"
        "clean:\n"
        "\trm -f *.o\n"
        "build: main.o helper.o\n"
        "\tgcc -o build main.o helper.o\n",
        encoding="utf-8",
    )

    guidestar.scan_project_config()

    found, lock = guidestar.get_intent_status("main.c")
    assert found is True
    assert lock["source_proof"] == "Manifest Source (Makefile)"

    found, lock = guidestar.get_intent_status("helper.c")
    assert found is True

    # "build" is a real target line, not a phony one -- should get locked.
    found, lock = guidestar.get_intent_status("build")
    assert found is True
    assert lock["source_proof"] == "Makefile Target"

    # "all" and "clean" are phony targets and must be excluded.
    found, _ = guidestar.get_intent_status("all")
    assert found is False
    found, _ = guidestar.get_intent_status("clean")
    assert found is False


# ==============================================================================
# TEST 8: TOML-STYLE MANIFEST PARSING (pyproject.toml / Cargo.toml / requirements.txt)
# ==============================================================================
def test_guidestar_toml_style_manifest_parsing(guidestar, tmp_path):
    """
    Proves the regex-based TOML parser extracts both `path = "..."` entries
    (Cargo-style) and `entry_point = "module.sub:func"` style Python entry
    points from pyproject.toml.
    """
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(
        '[tool.poetry.dependencies]\n'
        'mylib = { path = "libs/mylib" }\n'
        '\n'
        '[project.scripts]\n'
        'mycli = "mypackage.cli:main"\n',
        encoding="utf-8",
    )

    guidestar.scan_project_config()

    found, lock = guidestar.get_intent_status("libs/mylib")
    assert found is True
    assert "Manifest Roadmap" in lock["source_proof"]


def test_guidestar_manifest_parsers_survive_malformed_input(guidestar, tmp_path):
    """
    Stress test: package.json with invalid JSON, and a Makefile/pyproject.toml
    that exist but can't be meaningfully parsed, must not crash
    scan_project_config -- each parser's own try/except should swallow the
    error and let the scan continue.
    """
    (tmp_path / "package.json").write_text("{ not valid json !!!", encoding="utf-8")
    (tmp_path / "Makefile").write_bytes(b"\xff\xfe\x00\x01 binary garbage, not text")

    # Must not raise.
    guidestar.scan_project_config()
    assert guidestar.intent_locks.get("package.json") is not None, (
        "The manifest itself should still get a baseline lock even if its contents fail to parse."
    )


# ==============================================================================
# TEST 9: PACKAGE.JSON 'bin' FIELD VARIATIONS (string vs. dict)
# ==============================================================================
def test_guidestar_package_json_bin_as_string(guidestar, tmp_path):
    """A package.json with `"bin": "cli.js"` (single string, not a dict) must still lock."""
    pkg_path = tmp_path / "package.json"
    pkg_path.write_text(json.dumps({"bin": "cli.js"}), encoding="utf-8")

    guidestar.scan_project_config()

    found, lock = guidestar.get_intent_status("cli.js")
    assert found is True
    assert "Manifest Binary" in lock["source_proof"]


def test_guidestar_package_json_bin_as_dict_multiple_entries(guidestar, tmp_path):
    """A package.json with multiple named bin entries must lock every target."""
    pkg_path = tmp_path / "package.json"
    pkg_path.write_text(
        json.dumps({"bin": {"tool-a": "bin/tool-a.js", "tool-b": "bin/tool-b.js"}}), encoding="utf-8"
    )

    guidestar.scan_project_config()

    for target in ("bin/tool-a.js", "bin/tool-b.js"):
        found, lock = guidestar.get_intent_status(target)
        assert found is True, f"{target} should have been locked from the bin dict!"


# ==============================================================================
# TEST 10: .gitattributes MALFORMED / COMMENT LINES
# ==============================================================================
def test_guidestar_gitattributes_skips_comments_and_malformed_lines(guidestar, tmp_path):
    """
    Comment lines, blank lines, and lines without at least a pattern + one
    attribute must be safely skipped, not crash the parser.
    """
    attr_path = tmp_path / ".gitattributes"
    attr_path.write_text(
        "# this is a comment\n"
        "\n"
        "*.h linguist-language=C++\n"
        "just_a_pattern_with_no_attrs\n",
        encoding="utf-8",
    )

    guidestar.scan_project_config()

    found, lock = guidestar.get_intent_status("include/math_ops.h")
    assert found is True
    assert lock["lang_id"] == "cpp"


def test_guidestar_gitattributes_survives_unreadable_file(guidestar, tmp_path):
    """A .gitattributes that raises on open() (e.g. a directory, not a file) must not crash the scan."""
    attr_path = tmp_path / ".gitattributes"
    attr_path.mkdir()  # A directory named .gitattributes can't be opened as a file.

    guidestar.scan_project_config()  # Must not raise.


# ==============================================================================
# TEST 11: .gitignore SURVIVES UNREADABLE FILE
# ==============================================================================
def test_guidestar_gitignore_survives_unreadable_file(guidestar, tmp_path):
    """A .gitignore that can't be opened must not crash the scan."""
    ignore_path = tmp_path / ".gitignore"
    ignore_path.mkdir()

    guidestar.scan_project_config()  # Must not raise.


# ==============================================================================
# TEST 12: DOCUMENTATION COVERAGE -- SCAN ROOT ITSELF INSIDE AN IGNORED DIR
# ==============================================================================
def test_guidestar_documentation_coverage_root_inside_ignored_dir(tmp_path):
    """
    Edge case: if the scan root itself is nested inside a directory whose
    name matches IGNORED_DIRECTORIES, os.walk's dirs[:] pruning can't help
    (it only prevents further descent, the root itself was never a
    candidate for pruning) -- the explicit `dir_path.parts` check exists
    specifically to catch this.
    """
    nested_root = tmp_path / "vendor" / "some_project"
    nested_root.mkdir(parents=True)
    (nested_root / "README.md").write_text("z" * 500, encoding="utf-8")

    lens = GuideStarLens(
        root_path=nested_root,
        guidestar_config={**MOCK_GUIDESTAR_CONFIG, "IGNORED_DIRECTORIES": {"vendor"}},
    )
    lens._calculate_documentation_coverage()

    assert lens.documentation_coverage == {}, (
        "A scan root nested inside an ignored directory name should contribute no documentation coverage."
    )


# ==============================================================================
# TEST 13: ORPHANED FEATURE -- _extract_execution_triggers is never called
# from anywhere in the codebase (see the filed GitHub issue). Tested here in
# isolation so the logic itself has coverage regardless of the wiring
# decision.
# ==============================================================================
def test_extract_execution_triggers_in_isolation(guidestar):
    """
    Direct unit test of _extract_execution_triggers's own regex/dispatch
    logic, since nothing in the production pipeline currently calls it.
    """
    text = "Run the demo with `python demo.py` or `./run.sh` or `node server.js`."
    guidestar._extract_execution_triggers(text)

    found, lock = guidestar.get_intent_status("demo.py")
    assert found is True
    assert lock["lang_id"] == "python"
    assert "Execution Trigger" in lock["source_proof"]

    # "./run.sh" -- the "./" prefix forces predicted_lang to "unknown"
    # regardless of EXEC_PREFIX_MAP, per the explicit override in the method.
    found, lock = guidestar.get_intent_status("run.sh")
    assert found is True
    assert lock["lang_id"] == "unknown"

    found, lock = guidestar.get_intent_status("server.js")
    assert found is True
    assert lock["lang_id"] == "javascript"


# ==============================================================================
# TEST 14: PARENT LOGGER PROPAGATION
# ==============================================================================
def test_guidestar_uses_parent_logger_when_provided(tmp_path):
    """A parent_logger should be adopted (child logger, same level), not ignored."""
    import logging

    parent = logging.getLogger("test_parent_guidestar")
    parent.setLevel(logging.WARNING)

    lens = GuideStarLens(root_path=tmp_path, parent_logger=parent, guidestar_config=MOCK_GUIDESTAR_CONFIG)

    assert lens.logger.parent is parent
    assert lens.logger.level == logging.WARNING


# ==============================================================================
# TEST 15: DEEP MANIFEST INSPECTION -- OUTER EXCEPTION HANDLER
# ==============================================================================
def test_guidestar_deep_inspect_manifest_survives_unopenable_file(guidestar, tmp_path):
    """
    A manifest path that can't even be opened (e.g. package.json exists as a
    directory, not a file) must be caught by _deep_inspect_manifest's own
    try/except, not crash the whole scan. The per-parser try/excepts can't
    catch this since it fails before any parser is even reached.
    """
    (tmp_path / "package.json").mkdir()

    guidestar.scan_project_config()  # Must not raise.

    # The manifest-level lock (from _scan_package_manifests, before deep
    # inspection) should still have been applied.
    found, _ = guidestar.get_intent_status("package.json")
    assert found is True


# ==============================================================================
# TEST 16: DOCUMENTATION COVERAGE -- ROOT-LEVEL DOC FILE & UNSTATABLE FILE
# ==============================================================================
def test_guidestar_documentation_coverage_root_level_and_broken_symlink(tmp_path):
    """
    A doc file directly in the scan root must be keyed as '__root__', and a
    broken symlink (stat() raises OSError) must be silently skipped rather
    than crashing the coverage scan.
    """
    (tmp_path / "README.md").write_text("root doc content " * 20, encoding="utf-8")

    broken_link = tmp_path / "BROKEN_LINK.md"
    broken_link.symlink_to(tmp_path / "does_not_exist.md")

    lens = GuideStarLens(root_path=tmp_path, guidestar_config=MOCK_GUIDESTAR_CONFIG)
    lens._calculate_documentation_coverage()  # Must not raise on the broken symlink.

    assert "__root__" in lens.documentation_coverage


def test_toml_parser_survives_unopenable_file_directly(guidestar, tmp_path):
    """
    Direct unit test of _parse_toml_style_manifest's own try/except: called
    with a path that can't be opened, it must swallow the error rather than
    raise. (Going through scan_project_config() can't isolate this specific
    handler -- _deep_inspect_manifest's outer open() on the same path fails
    first and is caught by its own, already-covered except block instead.)
    """
    guidestar._parse_toml_style_manifest(tmp_path / "does_not_exist" / "pyproject.toml", "python")