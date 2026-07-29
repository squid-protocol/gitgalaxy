# IMPORTANT: Adjust this path to match exactly where your file is located
import gitgalaxy.tools.cobol_to_cobol.cobol_lexical_patcher as patcher_module


# ==============================================================================
# TEST 1: The Dialect Sensor
# ==============================================================================
def test_detect_cobol_dialect():
    """
    Proves the sensor correctly dates the compiler era by scanning for
    post-1974 structural keywords and scope terminators.
    """
    # 1. COBOL-74 Baseline (Strict, no terminators)
    assert patcher_module.detect_cobol_dialect("IF A = B NEXT SENTENCE.") == "COBOL-74"
    assert patcher_module.detect_cobol_dialect("PERFORM PARA-A THRU PARA-B.") == "COBOL-74"

    # 2. COBOL-85 Modern Signatures
    assert patcher_module.detect_cobol_dialect("IF A = B CONTINUE END-IF.") == "COBOL-85"
    assert patcher_module.detect_cobol_dialect("EVALUATE WS-STATUS") == "COBOL-85"
    assert patcher_module.detect_cobol_dialect("INITIALIZE WS-DATA") == "COBOL-85"
    assert patcher_module.detect_cobol_dialect("*> This is an inline comment") == "COBOL-85"


# ==============================================================================
# TEST 2: The COBOL-85 Modernization Patch
# ==============================================================================
def test_patch_cobol85_modernization(tmp_path):
    """
    Proves that in a modern environment, the dangerous NEXT SENTENCE trap
    is fully eradicated and replaced with a safe CONTINUE block.
    """
    pgm = tmp_path / "PGM85.cbl"
    # Contains END-IF, triggering the COBOL-85 sensor
    pgm.write_text("IF X = Y NEXT SENTENCE END-IF.", encoding="utf-8")

    was_modified = patcher_module.patch_lexical_traps(pgm)

    assert was_modified is True, "Patcher failed to modify the infected file!"

    content = pgm.read_text(encoding="utf-8")
    assert "CONTINUE *> GitGalaxy Patch" in content, "Failed to inject the safe modern patch!"
    assert "NEXT SENTENCE" not in content, "The dangerous lexical trap survived!"


# ==============================================================================
# TEST 3: The COBOL-74 Strict Mode Bypass
# ==============================================================================
def test_patch_cobol74_strict_mode(tmp_path):
    """
    Proves that in a legacy environment, the engine normalizes the casing and
    spacing of the trap for the AST slicer, but DOES NOT inject modern syntax
    that would cause a compiler crash.
    """
    pgm = tmp_path / "PGM74.cbl"
    # Uses weird casing/spacing to ensure the regex normalization triggers a file write.
    # No COBOL-85 terminators present.
    pgm.write_text("IF X = Y nExt    sEntEnce.", encoding="utf-8")

    was_modified = patcher_module.patch_lexical_traps(pgm)

    assert was_modified is True, "Patcher failed to normalize the spacing/casing!"

    content = pgm.read_text(encoding="utf-8")
    assert "NEXT SENTENCE" in content, "Failed to enforce strict mode normalization!"
    assert "CONTINUE" not in content, "FATAL: Injected modern code into a COBOL-74 file!"
    assert "*>" not in content, "FATAL: Injected modern comment into a COBOL-74 file!"


# ==============================================================================
# TEST 4: The Fast-Exit Optimization Guard
# ==============================================================================
def test_fast_exit_clean_file(tmp_path):
    """
    Proves that files without the lexical trap are instantly skipped,
    saving heavy Regex compilation and File I/O overhead.
    """
    pgm = tmp_path / "CLEAN.cbl"
    pgm.write_text("IF A = B DISPLAY 'SAFE CODE'.", encoding="utf-8")

    # Check the modification timestamp before scanning
    initial_mtime = pgm.stat().st_mtime

    was_modified = patcher_module.patch_lexical_traps(pgm)

    assert was_modified is False, "False positive! Patcher modified a clean file."

    # Ensure the file was absolutely not touched on disk
    assert pgm.stat().st_mtime == initial_mtime, "Patcher performed an unnecessary disk write!"
