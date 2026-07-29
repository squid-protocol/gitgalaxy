import sys
from unittest.mock import patch

# IMPORTANT: Adjust this path to match exactly where your file is located
import gitgalaxy.tools.cobol_to_cobol.cobol_compiler_forge as forge_module


# ==============================================================================
# TEST 1: The Dialect Compiler Router
# ==============================================================================
def test_dialect_router_jcl_generation():
    """
    Proves the JCL generation engine dynamically routes to the correct
    Mainframe compiler (COBUCL vs IGYWCL) based on the detected dialect.
    """
    mock_source = "PROGRAM-ID. HELLO."

    # 1. COBOL-74 Path (Legacy)
    jcl_74 = forge_module.generate_build_jcl(mock_source, "PGM1", set(), "COBOL-74")
    assert "EXEC COBUCL" in jcl_74, "Failed to route COBOL-74 to the legacy compiler!"
    assert "EXEC IGYWCL" not in jcl_74

    # 2. COBOL-85 Path (Modern)
    jcl_85 = forge_module.generate_build_jcl(mock_source, "PGM2", set(), "COBOL-85")
    assert "EXEC IGYWCL" in jcl_85, "Failed to route COBOL-85 to the modern enterprise compiler!"
    assert "EXEC COBUCL" not in jcl_85


# ==============================================================================
# TEST 2: The Infinite Loop Failsafe
# ==============================================================================
def test_flatten_copybooks_cyclic_failsafe(tmp_path):
    """
    Proves the engine mathematically breaks infinite copybook recursion loops
    (e.g., A imports B, B imports A) without causing a StackOverflow crash.
    """
    repo_dir = tmp_path / "cyclic_repo"
    repo_dir.mkdir()

    # Create two copybooks that import each other
    (repo_dir / "CYCLE-A.cpy").write_text("COPY CYCLE-B.", encoding="utf-8")
    (repo_dir / "CYCLE-B.cpy").write_text("COPY CYCLE-A.", encoding="utf-8")

    # A root program that triggers the trap
    root_code = "PROGRAM-ID. BOOM.\nCOPY CYCLE-A."

    # Run the flattener
    inlined_code = forge_module.flatten_copybooks(root_code, repo_dir)

    # If the test finishes without crashing with a RecursionError, the failsafe worked.
    # We verify it successfully nested multiple times before pulling the emergency brake.
    assert inlined_code.count("INLINED COPYBOOK: CYCLE-A") >= 1, "Failed to recurse at all!"
    assert "PROGRAM-ID. BOOM." in inlined_code, "Root AST was destroyed by the cycle!"


# ==============================================================================
# TEST 3: The E2E Flattener & JCL Provisioning
# ==============================================================================
def test_compiler_forge_e2e(tmp_path):
    """
    Proves the E2E pipeline correctly discovers a COBOL file, inlines its
    local copybook, provisions physical datasets via IEFBR14, and saves the JCL.
    """
    src_dir = tmp_path / "src"
    out_dir = tmp_path / "out"
    src_dir.mkdir()

    # 1. The Copybook
    (src_dir / "MYDATA.cpy").write_text("       01 MY-VAR PIC X.", encoding="utf-8")

    # 2. The Main Program (Requires modern COBOL-85 compiler due to END-IF)
    (src_dir / "MAINPGM.cbl").write_text(
        "       PROGRAM-ID. MAINPGM.\n"
        "       SELECT FILE-IN ASSIGN TO UT-S-INPUT01.\n"
        "       DATA DIVISION.\n"
        "       COPY MYDATA.\n"
        "       PROCEDURE DIVISION.\n"
        "           IF 1 = 1 CONTINUE END-IF.",  # END-IF triggers COBOL-85
        encoding="utf-8",
    )

    # 3. Execute the Forge
    test_args = ["cobol_compiler_forge.py", str(src_dir), str(out_dir)]
    with patch.object(sys, "argv", test_args):
        try:
            forge_module.main()
        except SystemExit as e:
            assert e.code == 0

    # 4. Verify Output Structure
    jcl_file = out_dir / "BUILD_MAINPGM.jcl"
    assert jcl_file.exists(), "Forge failed to create the target JCL file!"

    jcl_content = jcl_file.read_text(encoding="utf-8")

    # A) Verify Infrastructure Provisioning
    assert "EXEC PGM=IEFBR14" in jcl_content
    assert "//INPUT01 DD DSN=HERC01.DATA.INPUT01" in jcl_content, "Failed to map SELECT ASSIGN to DSN!"

    # B) Verify Dialect Routing
    assert "EXEC IGYWCL" in jcl_content, "Failed to dynamically route to modern compiler!"

    # C) Verify Copybook Inlining
    assert "INLINED COPYBOOK: MYDATA" in jcl_content
    assert "01 MY-VAR PIC X." in jcl_content, "Failed to inline the actual copybook data!"
