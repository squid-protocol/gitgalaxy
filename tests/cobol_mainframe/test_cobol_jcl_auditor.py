import json
import sys
from unittest.mock import patch

# IMPORTANT: Adjust this path to match exactly where your file is located
import gitgalaxy.tools.cobol_to_cobol.cobol_jcl_auditor as auditor_module


# ==============================================================================
# TEST 1: The Raw Intent Parsing Engine
# ==============================================================================
def test_parse_jcl_intent(tmp_path):
    """
    Proves that the JCL parser correctly counts LOC while ignoring comments,
    and successfully strips out IBM System Programs and System DDs to isolate
    true business intent.
    """
    mock_jcl = tmp_path / "LEGACY.jcl"

    # 7 active lines of code, 1 comment line
    jcl_content = (
        "//TESTJOB JOB (1234),CLASS=A\n"
        "//* THIS IS A COMMENT AND SHOULD BE IGNORED\n"
        "//STEP01  EXEC PGM=IEBGENER\n"  # System PGM (Should be ignored)
        "//SYSOUT  DD SYSOUT=*\n"  # System DD (Should be ignored)
        "//STEP02  EXEC PGM=BUSINESS01\n"  # Custom PGM (Should be captured)
        "//INPUT   DD DSN=PROD.DATA.IN,DISP=SHR\n"  # Custom DD (Should be captured)
        "//OUTPUT  DD DSN=PROD.DATA.OUT,DISP=NEW\n"  # Custom DD (Should be captured)
        "//SYSUDUMP DD SYSOUT=*\n"  # System DD (Should be ignored)
    )
    mock_jcl.write_text(jcl_content, encoding="utf-8")

    metrics = auditor_module.parse_jcl_intent(mock_jcl)

    # 1. Assert LOC
    assert metrics["lines_of_code"] == 7, "Failed to correctly count active LOC!"

    # 2. Assert Program filtering
    assert "BUSINESS01" in metrics["exec_pgms"]
    assert "IEBGENER" not in metrics["exec_pgms"], "Failed to filter out IBM System Programs!"

    # 3. Assert DD filtering
    assert "INPUT" in metrics["data_definitions"]
    assert "OUTPUT" in metrics["data_definitions"]
    assert "SYSOUT" not in metrics["data_definitions"], "Failed to filter out System DDs!"
    assert "SYSUDUMP" not in metrics["data_definitions"]


# ==============================================================================
# TEST 2: The Audit Engine and Bloat Math
# ==============================================================================
def test_audit_zero_trust_jcls(tmp_path):
    """
    Proves that the core audit loop correctly maps forged JCLs to their legacy
    counterparts and accurately calculates Bloat Reduction % and I/O shedding.
    """
    legacy_dir = tmp_path / "legacy"
    forged_dir = tmp_path / "forged"
    legacy_dir.mkdir()
    forged_dir.mkdir()

    # LEGACY JCL: 5 Lines of Code, 3 Custom DDs
    (legacy_dir / "OLDJOB.txt").write_text(
        "//STEP1 EXEC PGM=MYPGM\n//DD1 DD DSN=FILE1\n//DD2 DD DSN=FILE2\n//DD3 DD DSN=FILE3\n//SYSPRINT DD SYSOUT=*\n",
        encoding="utf-8",
    )

    # FORGED JCL: 2 Lines of Code, 1 Custom DD
    # (We shed 3 LOC and 2 Over-Permissioned DDs)
    (forged_dir / "MYPGM.jcl").write_text("//STEP1 EXEC PGM=MYPGM\n//DD1 DD DSN=FILE1\n", encoding="utf-8")

    report = auditor_module.audit_zero_trust_jcls(forged_dir, legacy_dir)

    assert report["audited"] == 1
    assert report["original_loc"] == 5
    assert report["forged_loc"] == 2
    assert report["excess_dds_blocked"] == 2, "Failed to calculate shed DDs!"

    # Bloat Reduction = ((5 - 2) / 5) * 100 = 60.0%
    assert report["bloat_reduction_pct"] == 60.0, "Bloat math is mathematically incorrect!"
    assert "MYPGM" in report["program_breakdown"]


# ==============================================================================
# TEST 3: The CI/CD Pipeline Wrapper (--json flag)
# ==============================================================================
def test_auditor_cli_json_output(tmp_path, capsys):
    """
    Proves the CLI wrapper correctly handles the --json flag, outputting pure
    parseable JSON and exiting successfully without printing ASCII art.
    """
    legacy_dir = tmp_path / "legacy"
    forged_dir = tmp_path / "forged"
    legacy_dir.mkdir()
    forged_dir.mkdir()

    (legacy_dir / "OLD.jcl").write_text("//STEP EXEC PGM=PGMA\n//DD1 DD DSN=A\n", encoding="utf-8")
    (forged_dir / "NEW.jcl").write_text("//STEP EXEC PGM=PGMA\n//DD1 DD DSN=A\n", encoding="utf-8")

    test_args = ["cobol_jcl_auditor.py", str(forged_dir), str(legacy_dir), "--json"]

    with patch.object(sys, "argv", test_args):
        try:
            auditor_module.main()
        except SystemExit as e:
            assert e.code == 0, "CLI exited with error!"

    captured = capsys.readouterr()

    # 1. Assert no ASCII art or CLI vibes polluted the stdout
    assert "GitGalaxy Spoke" not in captured.out

    # 2. Assert the output is pure JSON
    parsed_output = json.loads(captured.out)
    assert parsed_output["audited"] == 1
    assert parsed_output["bloat_reduction_pct"] == 0.0
