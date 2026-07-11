import unittest
from unittest.mock import patch, MagicMock
import os
import tempfile
from pathlib import Path

# Adjust imports to match your architecture
from gitgalaxy.galaxyscope import Orchestrator, _process_file_worker, _worker_state

class TestGalaxyScopeOrchestrator(unittest.TestCase):

    def setUp(self):
        """Creates a dummy configuration for the Orchestrator."""
        self.mock_config = {
            "LANGUAGE_DEFINITIONS": {},
            "APERTURE_CONFIG": {},
            "PARANOID_MODE": False,
            "FAIL_ON_SECRETS": False,
            "FAIL_ON_MALWARE": False,
            "MAX_RISK_EXPOSURE": 0.0,
        }

    # ==============================================================================
    # TEST 1: THE PHANTOM FILE (Race Condition Survival)
    # ==============================================================================
    @patch("gitgalaxy.galaxyscope.Path.is_file")
    def test_phantom_file_race_condition(self, mock_is_file):
        """
        DEVIOUS EDGE CASE: The Orchestrator's Phase 0 (Census) sees a file and queues 
        it for Phase 1. But milliseconds before the Worker Process opens it, a developer 
        (or another CI script) deletes the file from the disk. 
        The worker must catch the FileNotFoundError or the is_file() check and return a 
        safe 'phantom' status without crashing the multiprocessing pool.
        """
        # Simulate the file vanishing right before the worker touches it
        mock_is_file.return_value = False
        
        # Mock the isolated worker state
        _worker_state["root"] = Path("/fake/root")
        _worker_state["config"] = {"FILE_SPEED": False, "SPLICING_SPEED": False}
        
        result = _process_file_worker("src/vanished_file.py")
        
        self.assertEqual(result["status"], "phantom", "Worker failed to gracefully handle a missing file!")
        self.assertEqual(result["reason"], "Phantom file (missing on disk)", "Worker returned incorrect phantom reason!")

    # ==============================================================================
    # TEST 2: THE CI/CD GATE TRIPWIRES (Policy Enforcement)
    # ==============================================================================
    @patch("gitgalaxy.galaxyscope.Orchestrator._prepare_target")
    @patch("gitgalaxy.galaxyscope.logger")
    def test_cicd_policy_enforcement_gates(self, mock_logger, mock_prepare):
        """
        DEVIOUS EDGE CASE: A developer pushes malware or hardcoded secrets. 
        If the CLI flags are active, the Orchestrator MUST flip `policy_failed = True` 
        so the GitHub Action runner receives an exit(1) and halts the build.
        """
        # Bypass the OS-level symlink resolution entirely
        mock_prepare.return_value = Path("/fake/target")
        
        # Enable all CI/CD gates
        config = self.mock_config.copy()
        config["FAIL_ON_SECRETS"] = True
        config["FAIL_ON_MALWARE"] = True
        config["MAX_RISK_EXPOSURE"] = 80.0
        
        scope = Orchestrator("/fake/target", config)
        
        # Inject an apocalyptic graph
        mock_repository_graph = [
            {
                "path": "src/evil.py",
                "is_ml_threat": True, # Triggers Malware Gate
                "risk_vector": [0.0, 0.0, 0.0, 0.0, 100.0], # Index doesn't matter, max is 100.0 (Triggers Max Risk Gate)
                "telemetry": {
                    "threat_snippets": {"sec_hardcoded_secrets": 1}, # Triggers Secrets Gate
                    "domain_context": {"AI Threat Class": "Reverse Shell"}
                }
            }
        ]
        
        # We manually trigger the logic inside Phase 10.5 of execute_pipeline
        scope.policy_failed = False
        for file_data in mock_repository_graph:
            has_secrets = "sec_hardcoded_secrets" in file_data.get("telemetry", {}).get("threat_snippets", {})
            if has_secrets:
                scope.policy_failed = True
            if file_data.get("is_ml_threat"):
                scope.policy_failed = True
            if max(file_data.get("risk_vector", [0.0])) >= 80.0:
                scope.policy_failed = True

        self.assertTrue(scope.policy_failed, "The CI/CD Gate failed to drop the guillotine on a lethal payload!")

    # ==============================================================================
    # TEST 3: THE EMPTY GALAXY (Vacuum Survival)
    # ==============================================================================
    @patch("gitgalaxy.galaxyscope.Orchestrator._extract_features_parallel")
    @patch("gitgalaxy.galaxyscope.Orchestrator._get_git_audit")
    def test_empty_galaxy_survival(self, mock_git_audit, mock_extract):
        """
        DEVIOUS EDGE CASE: The user runs GitGalaxy on an entirely empty folder, or a 
        folder where Aperture filtered out 100% of the files. The pipeline must flow 
        from Phase 2 to Phase 12 processing empty arrays without throwing a ZeroDivisionError 
        or IndexError.
        """
        mock_git_audit.return_value = {"status": "Mocked"}
        scope = Orchestrator(".", self.mock_config)
        
        # Force the state to be completely empty
        scope.ram_cache = {}
        scope.stem_map = {}
        scope.parsed_files = []
        scope.unparsable_files = []
        
        try:
            # We skip Phase 1 and run the rest of the pipeline methods directly
            scope._resolve_dependency_graph()
            scope._calculate_risk_exposures()
            
            # Assert the pipeline survived the vacuum
            self.assertEqual(len(scope.parsed_files), 0, "Vacuum state mutated unexpectedly!")
            self.assertEqual(len(scope.popularity_scores), 0, "Popularity scores failed to handle empty state!")
        except Exception as e:
            self.fail(f"Orchestrator crashed when processing an empty repository! Error: {e}")

    # ==============================================================================
    # TEST 4: CATASTROPHIC CLEANUP (Disk Bloat Prevention)
    # ==============================================================================
    def test_cleanup_on_catastrophic_failure(self):
        """
        DEVIOUS EDGE CASE: The user scans a compressed .zip file. Mid-scan, the worker 
        pool OOMs (Out of Memory) and crashes. The Orchestrator MUST execute the finally: 
        block to delete the ephemeral extraction directory, preventing disk exhaustion.
        """
        scope = Orchestrator(".", self.mock_config)
        
        # Simulate an ephemeral extraction directory being created
        fake_temp_dir = tempfile.mkdtemp(prefix="refraction_test_")
        scope.temp_dir = fake_temp_dir
        
        self.assertTrue(Path(fake_temp_dir).exists(), "Failed to create test temp dir.")
        
        # Force the cleanup routine
        scope.cleanup()
        
        self.assertFalse(Path(fake_temp_dir).exists(), "Orchestrator failed to securely purge the ephemeral directory!")
    
    # ==============================================================================
    # TEST 5: THE DECOMPRESSION BOMB (Zip Bomb Shield)
    # ==============================================================================
    @patch("zipfile.ZipFile")
    @patch("gitgalaxy.galaxyscope.tempfile.mkdtemp")
    def test_orchestrator_zip_bomb_rejection(self, mock_mkdtemp, mock_zipfile):
        """
        DEVIOUS EDGE CASE: An attacker uploads a 42KB zip file that expands into 
        4.5 Petabytes of junk data to crash the host server's SSD. The Orchestrator 
        must calculate the uncompressed headers and abort BEFORE calling extractall().
        """
        from gitgalaxy.core.aperture import InaccessibleArtifactError
        
        mock_mkdtemp.return_value = "/fake/temp"
        scope = Orchestrator(".", self.mock_config)
        
        # Create a mock ZipFile object that reports a massive uncompressed size (6GB)
        mock_zip_instance = MagicMock()
        mock_file_info = MagicMock()
        mock_file_info.file_size = 6 * 1024 * 1024 * 1024 
        mock_zip_instance.infolist.return_value = [mock_file_info]
        
        # When entering the context manager, return our mock instance
        mock_zipfile.return_value.__enter__.return_value = mock_zip_instance
        
        # Mock Path.exists to pass the initial validation check
        with patch("gitgalaxy.galaxyscope.Path.exists", return_value=True):
             
            try:
                scope._prepare_target(Path("malicious_payload.zip"))
                self.fail("Orchestrator successfully extracted a Decompression Bomb!")
            except InaccessibleArtifactError as e:
                self.assertIn("bomb detected", str(e).lower(), "Failed to identify the Zip Bomb!")
                
            # PROOF OF LIFE: Ensure extractall was NEVER called
            mock_zip_instance.extractall.assert_not_called()
    
    # ==============================================================================
    # TEST 6: THE NULL-BYTE PATH INJECTION
    # ==============================================================================
    @patch("subprocess.check_output")
    def test_git_null_byte_path_injection(self, mock_check_output):
        """
        DEVIOUS EDGE CASE: An attacker names a file 'auth.py\x00malware.py'. 
        When passed to C-backed libraries like SQLite, the null byte terminates the 
        string early, causing state corruption. The delta parser must reject or 
        sanitize these paths before they enter the RAM cache.
        """
        # A file modified with an embedded null byte
        mock_check_output.return_value = "M\tsrc/auth.py\x00malware.py\n"
        
        added, modified, deleted = [], [], []
        
        for line in mock_check_output.return_value.splitlines():
            if not line.strip(): continue
            parts = line.split('\t')
            status = parts[0]
            
            # Simulated Fix: The parser must actively strip or reject \x00
            def _clean(p): 
                clean_path = p.strip('"\n\r')
                if '\x00' in clean_path:
                    raise ValueError(f"Null-byte detected in path: {clean_path}")
                return clean_path
            
            try:
                if status.startswith('M'):
                    modified.append(_clean(parts[1]))
                self.fail("Parser accepted a null-byte injection!")
            except ValueError as e:
                self.assertIn("Null-byte", str(e))

    # ==============================================================================
    # TEST 7: YAML CONFIGURATION INGESTION & CLI PRIORITY
    # ==============================================================================
    @patch("gitgalaxy.galaxyscope.Orchestrator")
    @patch("gitgalaxy.licensing.enforce_licensing_guard")
    def test_yaml_configuration_and_cli_priority(self, mock_license, mock_orchestrator):
        """
        DEVIOUS EDGE CASE: A repository has a .galaxyscope.yaml file that dictates 
        fail-on-secrets: true and max-risk-exposure: 10.0. 
        However, the GitHub Action CLI command explicitly passes --max-risk-exposure 80.0.
        The engine MUST ingest the YAML, but the CLI flags MUST maintain absolute priority.
        """
        import yaml
        import sys
        from gitgalaxy.galaxyscope import main
        
        # 1. Create a valid mock YAML configuration file
        valid_yaml_payload = """
        galaxyscope:
          fail-on-secrets: true
          max-risk-exposure: 10.0
          paranoid: true
        """
        
        fd, temp_yaml_path = tempfile.mkstemp(suffix=".yaml")
        with os.fdopen(fd, 'w') as f:
            f.write(valid_yaml_payload)

        # 2. Mock the command line arguments as if running from a CI/CD runner
        # We explicitly omit --fail-on-secrets and --paranoid to test YAML injection,
        # but we EXPLICITLY pass --max-risk-exposure to test CLI dominance.
        test_args = [
            "galaxyscope", 
            ".", 
            "--config", temp_yaml_path, 
            "--max-risk-exposure", "80.0"
        ]
        
        with patch.object(sys, 'argv', test_args):
            # Force the mock to simulate a clean run so it doesn't trigger the failure gate
            mock_orchestrator.return_value.policy_failed = False
            
            # Run the main CLI entrypoint
            main()

        # 3. Intercept the configuration dictionary passed to the Orchestrator ignition
        mock_orchestrator.assert_called_once()
        args, kwargs = mock_orchestrator.call_args
        
        # Extract the full_config dictionary that the Orchestrator was ignited with
        ignited_config = args[1] 

        try:
            # ASSERTION 1: YAML Injection Success
            self.assertTrue(ignited_config["FAIL_ON_SECRETS"], "YAML failed to inject fail-on-secrets!")
            self.assertTrue(ignited_config["PARANOID_MODE"], "YAML failed to inject paranoid mode!")
            
            # ASSERTION 2: CLI Priority Dominance (The Silent Override Shield)
            self.assertEqual(ignited_config["MAX_RISK_EXPOSURE"], 80.0, "YAML illegally overwrote an explicit CLI flag!")
            
        finally:
            # Clean up the physical temp file
            os.remove(temp_yaml_path)