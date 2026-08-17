import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Adjust the import path if necessary based on your actual module structure
from gitgalaxy.metrics.chronometer import Chronometer


class TestChronometerTimeout(unittest.TestCase):
    @patch("gitgalaxy.metrics.chronometer.subprocess.Popen")
    @patch.object(Chronometer, "_initialize_history_scan")  # Skip the heavy init sequence
    def test_zombie_process_kill_switch(self, mock_calibrate, mock_popen):
        """
        Simulates an infinite, hanging Git stream.
        Verifies that the Chronometer respects the timeout and successfully
        reaps the zombie process at the OS level via kill() and communicate().
        """

        # 1. Setup the Infinite Stream
        def infinite_git_log():
            while True:
                # Yields a valid line so the internal logic has to do work
                yield "@@GIT_COMMIT@@|mock_hash|1700000000|TestAuthor\n"
                yield "src/main.py\n"

        # We attach the generator to a MagicMock so we can assert .close() is called on it later
        mock_stdout = MagicMock()
        mock_stdout.__iter__.return_value = infinite_git_log()
        mock_stderr = MagicMock()

        # 2. Setup the Mock Process
        mock_process = MagicMock()
        mock_process.stdout = mock_stdout
        mock_process.stderr = mock_stderr
        mock_popen.return_value = mock_process

        # 3. Initialize Chronometer (calibration is bypassed)
        chrono = Chronometer(Path("/mock/repo"))

        # 4. Ignite the stream with a tiny timeout (50ms)
        timeout_limit = 0.05
        start_time = time.time()

        processed_lines, reached_target = chrono._stream_git_log(
            cmd=["git", "log", "mock_args"],
            ignored_hashes=set(),
            tracked_files=set(),
            required_files=10000,
            timeout_limit=timeout_limit,
            start_time=start_time,
        )

        # =====================================================================
        # 5. INVARIANT ASSERTIONS (The Proof)
        # =====================================================================

        # Check that it actually processed lines, but was interrupted by the timeout
        self.assertTrue(
            processed_lines > 0,
            "The stream should have processed lines before timing out.",
        )
        self.assertFalse(
            reached_target,
            "The stream should have aborted before reaching the file target.",
        )

        # --- THE ZOMBIE KILL SWITCH VERIFICATION ---
        # Did we send the SIGKILL?
        mock_process.kill.assert_called_once()

        # Did we flush the pipes? (Crucial: kill() without communicate() leaves a zombie)
        mock_process.communicate.assert_called_once()

        # Did we close the file descriptors to prevent FD leaks?
        mock_stdout.close.assert_called_once()
        mock_stderr.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
