from unittest.mock import patch

import pytest

from gitgalaxy.core.aperture import ApertureFilter

# ==============================================================================
# MOCK HARDWARE CALIBRATION
# ==============================================================================

MOCK_REGISTRY = {
    "python": {"extensions": [".py"], "exact_matches": []},
    "c": {"extensions": [".c", ".h"], "exact_matches": []},
    "javascript": {"extensions": [".js"], "exact_matches": []},
    "html": {"extensions": [".html"], "exact_matches": []},
    "markdown": {"extensions": [".md"], "exact_matches": ["README.md"]},
    "json": {"extensions": [".json"], "exact_matches": []},
}

MOCK_CONFIG = {
    "SECRETS_EXACT": {"id_rsa", ".env"},
    "SECRETS_EXTENSIONS": {".pem", ".key"},
    "MAX_FILE_SIZE_MB": 10,
    "MAX_FILE_SIZE_HARD_MB": 100,
    "MAX_LINE_LENGTH": 500,
    "IGNORED_DIRECTORIES": {"node_modules", ".git"},
    "IGNORED_EXTENSIONS": {".exe", ".dll"},
    "CONTRABAND_PATTERNS": ["*-min.js", "*.bundle.js"],
}


@pytest.fixture
def filter_engine(tmp_path):
    """Initializes the Aperture Filter with a temporary directory."""
    return ApertureFilter(
        root_dir=tmp_path,
        language_definitions=MOCK_REGISTRY,
        aperture_config=MOCK_CONFIG,
    )


# ==============================================================================
# TEST 1: THE LEAD SHIELD (Secrets & AI Weights)
# ==============================================================================
def test_aperture_lead_shield(filter_engine, tmp_path):
    """
    Proves that critical leaks and AI model weights bypass standard optical
    logic and are immediately shunted to dark matter/alert status.
    """
    # 1. Exposed Secret
    secret_file = tmp_path / "private_key.pem"
    secret_file.write_text("-----BEGIN RSA PRIVATE KEY-----", encoding="utf-8")

    is_valid, _, reason = filter_engine.evaluate_path_integrity(secret_file)
    assert is_valid is False
    assert "CRITICAL LEAK" in reason

    # 2. Massive Neural Weights (Should drop out before reading the file)
    weights_file = tmp_path / "model.safetensors"
    weights_file.write_bytes(b"\x00" * 10)  # Mock binary

    is_valid, _, reason = filter_engine.evaluate_path_integrity(weights_file)
    assert is_valid is False
    assert "AI MODEL WEIGHTS" in reason


# ==============================================================================
# TEST 2: THE SEMANTIC PATH GATE & INTENT LOCK
# ==============================================================================
def test_aperture_semantic_path_and_intent(filter_engine, tmp_path):
    """
    Proves that infrastructure paths (vendor/build/test) are blocked by default,
    but can be bypassed using the GuideStar Intent Lock.
    """
    vendor_dir = tmp_path / "vendor" / "lib"
    vendor_dir.mkdir(parents=True)
    vendor_file = vendor_dir / "library.py"
    vendor_file.write_text("def run(): pass", encoding="utf-8")

    # 1. Default Behavior: Blocked by infra_path_shield
    is_valid, _, reason = filter_engine.evaluate_path_integrity(vendor_file, has_intent=False)
    assert is_valid is False
    assert "Blocked" in reason

    # 2. GuideStar Intent Lock: Bypassed!
    is_valid, _, reason = filter_engine.evaluate_path_integrity(vendor_file, has_intent=True)
    assert is_valid is True
    assert "GuideStar Intent Lock" in reason


# ==============================================================================
# TEST 3: THE AUTO-GEN SHIELD & DYNAMIC INFECTION
# ==============================================================================
def test_aperture_auto_gen_shield(filter_engine, tmp_path):
    """
    Proves the engine detects machine-generated signatures and dynamically
    infects the parent directory to save future I/O reads.
    """
    doc_dir = tmp_path / "public_web" / "html"
    doc_dir.mkdir(parents=True)

    # 1. Evaluate the first auto-generated file
    doc_file_1 = doc_dir / "index.html"
    doc_file_1.write_text(
        '<html>\n<head>\n<meta name="generator" content="Doxygen 1.9.1">\n</head>\n</html>',
        encoding="utf-8",
    )

    result1 = filter_engine.is_in_scope(doc_file_1, content=doc_file_1.read_text())
    assert result1["is_in_scope"] is False
    assert result1["classification"] == "generated_noise"

    # Prove the directory was dynamically infected!
    rel_parent = str(doc_dir.relative_to(tmp_path))
    assert rel_parent in filter_engine.dynamic_ignore_dirs

    # 2. Evaluate a second, clean file in the same infected directory
    doc_file_2 = doc_dir / "clean.html"
    doc_file_2.write_text("<html>Clean file</html>", encoding="utf-8")

    # It should fail at the path gate before ever reading the content
    is_valid, _, reason = filter_engine.evaluate_path_integrity(doc_file_2)
    assert is_valid is False
    assert "Dynamic Ignored Dir" in reason


# ==============================================================================
# TEST 4: THE EMBEDDED HEX ARRAY SHIELD
# ==============================================================================
@pytest.mark.xfail(reason="Engine currently allows hex arrays if has_intent=True. Pending engine patch.")
def test_aperture_embedded_hex_shield(filter_engine, tmp_path):
    """
    Proves that massive C-header data payloads (hex arrays) are dropped to protect
    the regex engine, EVEN IF the file has a VIP intent lock.
    """
    hex_lines = ["const int data[] = {"] + ["    0x00, 0x01, 0x02, 0x03, 0x04," for _ in range(300)] + ["};"]
    hex_content = "\n".join(hex_lines)

    c_file = tmp_path / "data_payload.c"
    c_file.write_text(hex_content, encoding="utf-8")

    result = filter_engine.is_in_scope(c_file, content=hex_content, has_intent=True)
    assert result["is_in_scope"] is False
    assert result["classification"] == "binary_payload"
    assert "Embedded Data Payload" in result["reason"]


# ==============================================================================
# TEST 5: THE INFRARED GATE (Minification Saturation)
# ==============================================================================
def test_aperture_infrared_saturation_gate(filter_engine, tmp_path):
    """
    Proves that absurdly long lines of code (minified JS) are shunted to Infrared,
    but prose files (.md, .json) are granted an exemption.
    """
    # 1. Minified JS (Should be blocked)
    js_file = tmp_path / "app.js"
    massive_line = "var a=1;" * 200  # 1600 characters
    js_file.write_text(massive_line, encoding="utf-8")

    result_js = filter_engine.is_in_scope(js_file, content=massive_line)
    assert result_js["is_in_scope"] is False
    assert result_js["classification"] == "oversized_minified"

    # 2. Prose Exemption (Should pass)
    md_file = tmp_path / "README.md"
    md_file.write_text(massive_line, encoding="utf-8")

    result_md = filter_engine.is_in_scope(md_file, content=massive_line)
    assert result_md["is_in_scope"] is True


# ==============================================================================
# TEST 6: EXTREME MATTERS (Missing Files, Protocol Violations & Massive Sizes)
# ==============================================================================
def test_aperture_system_guardrails(filter_engine, tmp_path):
    """
    Tests edge cases regarding OS-level errors and protocol violations.
    """
    # 1. Missing File
    ghost_file = tmp_path / "nonexistent.py"
    result = filter_engine.is_in_scope(ghost_file, content="def foo(): pass")
    assert result["is_in_scope"] is False
    assert "Internal Exception: Artifact missing" in result["reason"]

    # 2. Missing Content Buffer
    real_file = tmp_path / "real.py"
    real_file.write_text("def foo(): pass")
    result = filter_engine.is_in_scope(real_file, content=None)
    assert result["is_in_scope"] is False
    assert "Protocol Violation: Missing content buffer" in result["reason"]

    # 3. Size Cap Exceeded (Mocking stat to simulate a 15MB file, no Intent Lock)
    big_file = tmp_path / "huge.py"
    big_file.write_text("x")

    with patch("pathlib.Path.stat") as mock_stat:
        mock_stat.return_value.st_size = 15 * 1024 * 1024  # 15MB
        result = filter_engine.is_in_scope(big_file, content="x")

        assert result["is_in_scope"] is False
        assert result["classification"] == "oversized_minified"
        assert "File size exceeds 10MB limit without Intent Lock" in result["reason"]


# ==============================================================================
# TEST 13: TIERED MASS CEILING (SOFT vs. HARD, ISSUE #245-followup)
# ==============================================================================
def test_aperture_tiered_mass_ceiling(filter_engine, tmp_path):
    """
    Proves the file-size gate is no longer a single flat cutoff:
      - Below the soft ceiling (MAX_FILE_SIZE_MB): always passes.
      - Above the soft ceiling but below the hard ceiling: blocked UNLESS the
        file carries a GuideStar Intent Lock, in which case it's handed to the
        content-based classifiers instead of being excluded on size alone.
      - Above the hard ceiling (MAX_FILE_SIZE_HARD_MB): blocked unconditionally,
        even with an Intent Lock, and rejected at evaluate_path_integrity
        (zero-I/O, pre-read) rather than is_in_scope.
    """
    mid_file = tmp_path / "generated_schema.py"
    mid_file.write_text("x", encoding="utf-8")

    # 1. Above soft (10MB), below hard (100MB), NO intent -> blocked
    with patch("pathlib.Path.stat") as mock_stat:
        mock_stat.return_value.st_size = 20 * 1024 * 1024  # 20MB
        result = filter_engine.is_in_scope(mid_file, content="x", has_intent=False)
        assert result["is_in_scope"] is False
        assert "without Intent Lock" in result["reason"]

    # 2. Above soft (10MB), below hard (100MB), WITH intent -> passes the size
    #    gate and reaches content classification
    with patch("pathlib.Path.stat") as mock_stat:
        mock_stat.return_value.st_size = 20 * 1024 * 1024  # 20MB
        result = filter_engine.is_in_scope(mid_file, content="x", has_intent=True)
        assert result["is_in_scope"] is True

    # 3. Above hard ceiling (100MB) -> blocked even WITH intent, and caught by
    #    the zero-I/O pre-read gate (evaluate_path_integrity), not is_in_scope.
    with patch("pathlib.Path.stat") as mock_stat:
        mock_stat.return_value.st_size = 150 * 1024 * 1024  # 150MB
        is_valid, _, reason = filter_engine.evaluate_path_integrity(mid_file, has_intent=True)
        assert is_valid is False
        assert "absolute 100MB safety ceiling" in reason

        result = filter_engine.is_in_scope(mid_file, content="x", has_intent=True)
        assert result["is_in_scope"] is False
        assert "safety ceiling" in result["reason"]


# ==============================================================================
# TEST 7: BINARY DEBRIS & MONOLITHS
# ==============================================================================
def test_aperture_binary_and_monolith_shields(filter_engine, tmp_path):
    """
    Ensures opaque binaries (null bytes) and >30,000 LOC monoliths are blocked.
    """
    # 1. Opaque Binary Detected
    bin_file = tmp_path / "script.py"
    content = "print('hello')\x00\x00"
    bin_file.write_text(content, encoding="utf-8")

    result = filter_engine.is_in_scope(bin_file, content=content)
    assert result["is_in_scope"] is False
    assert "Binary Format Detected" in result["reason"]

    # 2. Monolith Amalgamation Shield
    mono_file = tmp_path / "sqlite3.c"
    mono_content = "int main() {\n" + "    return 0;\n" * 30005 + "}"
    mono_file.write_text(mono_content, encoding="utf-8")

    result = filter_engine.is_in_scope(mono_file, content=mono_content)
    assert result["is_in_scope"] is False
    assert result["classification"] == "oversized_minified"
    assert "Monolithic Amalgamation" in result["reason"]


# ==============================================================================
# TEST 8: MACHINE GENERATED SOURCE & LEXICAL MONOTONY
# ==============================================================================
def test_aperture_machine_gen_and_monotony(filter_engine, tmp_path):
    """
    Tests the engine's ability to identify machine-generated files via headers
    and extreme lexical repetition (unrolled loops, generated arrays).
    """
    # 1. Standard Auto-Generated Header
    gen_file = tmp_path / "proto.py"
    gen_content = "# <auto-generated>\n# Protoc payload\n" + "x = 1\n" * 50
    gen_file.write_text(gen_content, encoding="utf-8")

    result = filter_engine.is_in_scope(gen_file, content=gen_content)
    assert result["is_in_scope"] is False
    assert "Machine-Generated Source Code Signature" in result["reason"]

    # 2. Lexical Monotony Shield
    rep_file = tmp_path / "unrolled.js"
    rep_content = "function loop() {\n" + "    var a = 1;\n" * 2500 + "}"
    rep_file.write_text(rep_content, encoding="utf-8")

    result = filter_engine.is_in_scope(rep_file, content=rep_content)
    assert result["is_in_scope"] is False
    assert "Lexical Monotony" in result["reason"]


# ==============================================================================
# TEST 9: DECLARATIVE BLOB SHIELD (JSON/YAML)
# ==============================================================================
def test_aperture_declarative_blob_shield(filter_engine, tmp_path):
    """
    Ensures massive vector or declarative files are suppressed unless they
    have an explicit Intent Lock (and even then, hard capped at 2500 LOC).
    """
    json_file = tmp_path / "data.json"

    # 1. Over 1000 LOC, No Intent -> Blocked
    content_1500 = "{\n" + '  "key": "value",\n' * 1500 + "}"
    json_file.write_text(content_1500, encoding="utf-8")

    res1 = filter_engine.is_in_scope(json_file, content=content_1500, has_intent=False)
    assert res1["is_in_scope"] is False
    assert "Static Asset Blob without Intent" in res1["reason"]

    # 2. Over 2500 LOC, WITH Intent -> Still Blocked (Absolute Cap)
    content_3000 = "{\n" + '  "key": "value",\n' * 3000 + "}"
    json_file.write_text(content_3000, encoding="utf-8")

    res2 = filter_engine.is_in_scope(json_file, content=content_3000, has_intent=True)
    assert res2["is_in_scope"] is False
    assert "Massive Static Asset Blob" in res2["reason"]


# ==============================================================================
# TEST 10: TEST DATA ARRAY SHIELD (COMMA DENSITY)
# ==============================================================================
def test_aperture_comma_density_shield(filter_engine, tmp_path):
    """
    Proves that massive data arrays compiled into source code are detected
    by extremely high comma density per LOC.
    """
    matrix_file = tmp_path / "matrix.c"
    # > 500 lines, > 3 commas per line
    content = "int data[] = {\n" + "    1, 2, 3, 4, 5,\n" * 600 + "};\n"
    matrix_file.write_text(content, encoding="utf-8")

    result = filter_engine.is_in_scope(matrix_file, content=content)
    assert result["is_in_scope"] is False
    assert "Embedded Array/Matrix Payload" in result["reason"]


# ==============================================================================
# TEST 11: GITIGNORE AND CONTRABAND SHIELDS
# ==============================================================================
def test_aperture_gitignore_and_contraband(tmp_path):
    """
    Proves that the engine correctly loads .gitignore patterns at runtime and
    blocks files matching contraband vendor patterns.
    """
    # 1. Create a dynamic .gitignore in the root
    ignore_file = tmp_path / ".gitignore"
    ignore_file.write_text("ignored_folder/\n*.log\n", encoding="utf-8")

    # 2. Re-instantiate the filter so it loads the new .gitignore
    engine = ApertureFilter(tmp_path, MOCK_REGISTRY, MOCK_CONFIG)

    # Verify .gitignore blocks
    assert engine._check_ignore_rules("ignored_folder/file.py") is False
    assert engine._check_ignore_rules("src/app.log") is False

    # Verify Contraband Patterns (from MOCK_CONFIG)
    assert engine._check_ignore_rules("src/react-min.js") is False
    assert engine._check_ignore_rules("src/vendor.bundle.js") is False

    # Verify standard files pass
    assert engine._check_ignore_rules("src/valid.py") is True


def test_aperture_gitignore_survives_unreadable_file(tmp_path):
    """A .gitignore that can't be opened (e.g. a directory, not a file) must not crash init."""
    ignore_file = tmp_path / ".gitignore"
    ignore_file.mkdir()

    engine = ApertureFilter(tmp_path, MOCK_REGISTRY, MOCK_CONFIG)  # Must not raise.
    assert engine._check_ignore_rules("src/valid.py") is True


# ==============================================================================
# TEST 12: IGNORED_DIRECTORIES CASE-INSENSITIVITY (ISSUE #255)
# ==============================================================================
def test_aperture_ignored_directories_case_insensitive(tmp_path):
    """
    Proves that mixed-case IGNORED_DIRECTORIES entries (as gitgalaxy_config.py
    deliberately ships them -- Pods, Carthage, CVS, Release, Debug, CMakeFiles,
    TestResults, DerivedData, __MACOSX) still block, even though
    _check_ignore_rules lowercases the path component before comparing.

    Before the fix, self.ignored_directories stored the raw-case config
    entries verbatim, so "pods" (lowercased path part) could never equal
    "Pods" (stored config entry) and iOS/Xcode/CMake vendor directories
    scanned as if they were source.

    Path/file names below are deliberately chosen to avoid the unrelated
    infra_path_pattern shield (which independently matches generic words
    like "build", "lib", "test", "spec") and the dot-prefix shield (which
    blocks any path segment starting with "."), so each assertion isolates
    the IGNORED_DIRECTORIES case-matching logic specifically. Verified by
    temporarily reverting the fix: all 9 assertions below flip to allowed
    (True) without it.
    """
    mixed_case_config = {
        **MOCK_CONFIG,
        "IGNORED_DIRECTORIES": {
            "CVS",
            "Pods",
            "Carthage",
            "Release",
            "Debug",
            "CMakeFiles",
            "TestResults",
            "DerivedData",
            "__MACOSX",
        },
    }
    engine = ApertureFilter(tmp_path, MOCK_REGISTRY, mixed_case_config)

    assert engine._check_ignore_rules("Pods/Alamofire/Alamofire.swift") is False
    assert engine._check_ignore_rules("Carthage/Checkouts/Foo/Foo.swift") is False
    assert engine._check_ignore_rules("project/CMakeFiles/CMakeCache.txt") is False
    assert engine._check_ignore_rules("artifacts/Release/app.bin") is False
    assert engine._check_ignore_rules("artifacts/Debug/app.bin") is False
    assert engine._check_ignore_rules("TestResults/run1.xml") is False
    assert engine._check_ignore_rules("DerivedData/x.log") is False
    assert engine._check_ignore_rules("__MACOSX/file.txt") is False
    assert engine._check_ignore_rules("CVS/Entries") is False

    # Non-matching source files still pass
    assert engine._check_ignore_rules("src/valid.py") is True


# ==============================================================================
# TEST: SECRETS SHUNT CONFIGURATION DRIFT (#703)
# ==============================================================================
def test_plaintext_language_definition_does_not_duplicate_secrets_shunt_config():
    """
    Regression test for #703: the secrets-extension/exact-match lists used
    to be hardcoded twice -- once as the real source of truth in
    gitgalaxy_config.py's APERTURE_CONFIG (what aperture.py's Gate 1.1
    Credential Exposure Radar actually reads), and again, redundantly,
    inside language_standards.py's "plaintext" language entry under a
    "THE SECRETS SHUNT (ASCII ONLY)" comment block.

    That second copy was provably dead: Gate 1.1 runs unconditionally at
    the top of ApertureFilter.evaluate_path_integrity() and returns early
    (rejecting the file) before Gate 1.5 (Language Registry Validation) --
    the only gate that ever reads a language's "extensions"/"exact_matches"
    -- is reached. A file matching SECRETS_EXTENSIONS/SECRETS_EXACT can
    never fall through to have its extension checked against "plaintext"'s
    list, so the duplicate served no runtime purpose and was pure
    configuration-drift risk (add a new secret extension to one file,
    forget the other).

    Asserts the two configs stay decoupled going forward: no entry from
    gitgalaxy_config.py's real SECRETS_EXTENSIONS/SECRETS_EXACT should ever
    reappear in language_standards.py's "plaintext" extensions/exact_matches.
    """
    from gitgalaxy.standards.gitgalaxy_config import APERTURE_CONFIG
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    plaintext_extensions = set(LANGUAGE_DEFINITIONS["plaintext"]["extensions"])
    plaintext_exact_matches = set(LANGUAGE_DEFINITIONS["plaintext"]["exact_matches"])

    overlapping_extensions = plaintext_extensions & APERTURE_CONFIG["SECRETS_EXTENSIONS"]
    overlapping_exact = plaintext_exact_matches & APERTURE_CONFIG["SECRETS_EXACT"]

    assert not overlapping_extensions, (
        f"plaintext's extensions re-duplicated SECRETS_EXTENSIONS entries: {overlapping_extensions}"
    )
    assert not overlapping_exact, f"plaintext's exact_matches re-duplicated SECRETS_EXACT entries: {overlapping_exact}"


def test_aperture_secrets_shunt_unaffected_by_removing_plaintext_duplication(tmp_path):
    """
    End-to-end regression test for #703: proves removing the duplicated
    entries from language_standards.py's "plaintext" definition did not
    regress the actual secrets-shunt behavior. Uses the REAL
    APERTURE_CONFIG and LANGUAGE_DEFINITIONS (not the minimal mocks used
    elsewhere in this file) to confirm Gate 1.1 still rejects secret
    extensions/filenames purely from gitgalaxy_config.py, with no
    dependency on "plaintext"'s own (now-deduplicated) lists.
    """
    from gitgalaxy.standards.gitgalaxy_config import APERTURE_CONFIG
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    real_engine = ApertureFilter(
        root_dir=tmp_path,
        language_definitions=LANGUAGE_DEFINITIONS,
        aperture_config=APERTURE_CONFIG,
    )

    pem_file = tmp_path / "private_key.pem"
    pem_file.write_text("-----BEGIN RSA PRIVATE KEY-----", encoding="utf-8")
    is_valid, _, reason = real_engine.evaluate_path_integrity(pem_file)
    assert is_valid is False
    assert "CRITICAL LEAK" in reason

    ssh_key_file = tmp_path / "id_rsa"
    ssh_key_file.write_text("-----BEGIN OPENSSH PRIVATE KEY-----", encoding="utf-8")
    is_valid, _, reason = real_engine.evaluate_path_integrity(ssh_key_file)
    assert is_valid is False
    assert "CRITICAL LEAK" in reason

    env_file = tmp_path / ".env"
    env_file.write_text("API_KEY=secret", encoding="utf-8")
    is_valid, _, reason = real_engine.evaluate_path_integrity(env_file)
    assert is_valid is False
    assert "CRITICAL LEAK" in reason
