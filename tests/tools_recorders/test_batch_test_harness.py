import pytest
import subprocess
import sys
from unittest.mock import patch, MagicMock

# Import your orchestrator script
from gitgalaxy.tools.cobol_to_java import batch_test_harness


@pytest.fixture
def mock_env(tmp_path):
    """
    Sets up a fake directory structure in the OS temp folder.
    This ensures the harness doesn't exit early when it globs for output folders.
    """
    corpus = tmp_path / "legacy_corpus"
    corpus.mkdir()

    # Create one target repository
    repo1 = corpus / "alpha_repo"
    repo1.mkdir()

    # Create the fake output folders the harness globs for in Steps 1 and 2
    (corpus / "alpha_repo_gitgalaxy_clean_v1").mkdir()
    (corpus / "alpha_repo_gitgalaxy_java_spring_v1").mkdir()

    return corpus


@patch("gitgalaxy.tools.cobol_to_java.batch_test_harness.subprocess.run")
def test_happy_path(mock_run, mock_env):
    """
    Simulates a flawless run where Refractor, Java Forge, and Maven all succeed.
    """
    # 1. Setup the mock to always return a successful execution
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "Process completed successfully."
    mock_result.stderr = ""
    mock_run.return_value = mock_result

    # 2. Patch sys.argv to simulate running the script from the CLI
    test_args = ["batch_test_harness.py", str(mock_env)]
    with patch.object(sys, "argv", test_args):
        batch_test_harness.main()

    # 3. Assert subprocess was called exactly 3 times for our 1 repo
    assert mock_run.call_count == 3

    # 4. Verify the master log was created and contains the correct sample size
    reports = list(mock_env.glob("batch_test_reports/master_batch_run_*.txt"))
    assert len(reports) == 1
    content = reports[0].read_text(encoding="utf-8")
    assert "Sample Size: 1" in content


@patch("gitgalaxy.tools.cobol_to_java.batch_test_harness.subprocess.run")
def test_maven_failure_path(mock_run, mock_env):
    """
    Simulates Steps 1 & 2 succeeding, but Step 3 (Maven) failing with a compile error.
    """
    # 1. Create two distinct mock objects
    success_mock = MagicMock(returncode=0, stdout="OK", stderr="")
    failure_mock = MagicMock(returncode=1, stdout="[ERROR] COMPILATION ERROR", stderr="Fatal flaw in Java")

    # 2. Use side_effect to return them in sequence (Success, Success, Fail)
    mock_run.side_effect = [success_mock, success_mock, failure_mock]

    test_args = ["batch_test_harness.py", str(mock_env)]
    with patch.object(sys, "argv", test_args):
        batch_test_harness.main()

    # 3. Verify the specific repo error log was created and caught the Maven stdout
    error_logs = list(mock_env.glob("batch_test_reports/alpha_repo_error_*.log"))
    assert len(error_logs) == 1
    error_content = error_logs[0].read_text(encoding="utf-8")

    assert "--- MAVEN STDERR/STDOUT ---" in error_content
    assert "[ERROR] COMPILATION ERROR" in error_content


@patch("gitgalaxy.tools.cobol_to_java.batch_test_harness.subprocess.run")
def test_timeout_path(mock_run, mock_env):
    """
    Simulates the external script hanging and triggering the 5-minute kill switch.
    """
    # 1. Force subprocess.run to raise the specific Timeout exception
    mock_run.side_effect = subprocess.TimeoutExpired(
        cmd="python cobol_refractor_controller.py",
        timeout=300,
        output=b"Partial refactor log before the freeze...",
    )

    test_args = ["batch_test_harness.py", str(mock_env)]
    with patch.object(sys, "argv", test_args):
        batch_test_harness.main()

    # 2. Verify the harness caught the timeout safely and wrote it to the error log
    error_logs = list(mock_env.glob("batch_test_reports/alpha_repo_error_*.log"))
    assert len(error_logs) == 1
    error_content = error_logs[0].read_text(encoding="utf-8")

    assert "TIMEOUT: Command exceeded 5 minutes" in error_content
    # Ensure it successfully decoded the partial output byte string
    assert "Partial refactor log before the freeze..." in error_content
