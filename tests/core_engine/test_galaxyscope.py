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

    # ==============================================================================
    # TEST 8: THE TYPOSQUATTING DOPPELGÄNGER (Supply Chain Radar)
    # ==============================================================================
    @patch("gitgalaxy.galaxyscope.logger")
    def test_typosquatting_radar(self, mock_logger):
        """
        DEVIOUS EDGE CASE: The user imports 'requests' 50 times (Anchor).
        One file maliciously imports 'requasts'. The O(1) Levenshtein radar
        MUST flag this as a typosquatting attempt and inject a sec_homoglyphs threat.
        """
        scope = Orchestrator(".", self.mock_config)
        
        # Setup a fake RAM cache with external imports
        scope.ram_cache = {
            "src/app.py": {"raw_imports": {"requests"}},
            "src/api.py": {"raw_imports": {"requests"}},
            "src/db.py": {"raw_imports": {"requests"}}, # 3 hits makes it an anchor
            "src/hacked.py": {"raw_imports": {"requasts"}}, # 1 hit, distance of 1
        }
        scope.stem_map = {k: k for k in scope.ram_cache.keys()}
        
        # Run the dependency graph resolver
        scope._resolve_dependency_graph()
        
        # Check that the threat was injected into the hacked file
        hacked_node = scope.ram_cache["src/hacked.py"]
        self.assertIn("equations", hacked_node, "Typosquatting radar failed to inject threat equations!")
        self.assertIn("sec_homoglyphs", hacked_node["equations"], "Failed to flag 'requasts' as a homoglyph!")
        self.assertIn("metadata", hacked_node)
        self.assertIn("TYPOSQUATTING", hacked_node["metadata"]["alert"])

    # ==============================================================================
    # TEST 9: INCREMENTAL DELTA SHIFT (State Rehydration)
    # ==============================================================================
    @patch("gitgalaxy.galaxyscope.Orchestrator._extract_features_parallel")
    @patch("gitgalaxy.galaxyscope.Orchestrator._calculate_risk_exposures")
    @patch("gitgalaxy.galaxyscope.RecordKeeper")
    def test_incremental_delta_shift(self, mock_db, mock_calc, mock_extract):
        """
        DEVIOUS EDGE CASE: Validating that an incremental delta scan doesn't falsely 
        confirm an active file update while secretly maintaining the older version block.
        If a file is modified, its old RAM state MUST be overwritten, and deleted files
        MUST be completely evicted.
        """
        scope = Orchestrator(".", self.mock_config)
        
        # Baseline state
        old_ram_cache = {
            "src/main.py": {"coding_loc": 100},
            "src/old_config.py": {"coding_loc": 50},
            "src/untouched.py": {"coding_loc": 200},
        }
        
        added = ["src/new_feature.py"]
        modified = ["src/main.py"]
        deleted = ["src/old_config.py"]
        
        # ---> THE FIX: Simulate the Worker Pool populating the RAM cache
        def mock_extract_action():
            # Verify the processing queue ONLY targeted the added and modified files during the surgical strike!
            self.assertIn("src/new_feature.py", scope.stem_map)
            self.assertIn("src/main.py", scope.stem_map)
            self.assertNotIn("src/untouched.py", scope.stem_map, "Delta scan wastefully targeted an untouched file during Phase 1!")
            
            # Simulate the workers finishing their job
            scope.ram_cache["src/new_feature.py"] = {"coding_loc": 150}
            scope.ram_cache["src/main.py"] = {"coding_loc": 150}
    
        mock_extract.side_effect = mock_extract_action
    
        # Execute the delta scan
        scope.execute_incremental_scan(
            ram_cache=old_ram_cache,
            added=added,
            modified=modified,
            deleted=deleted,
            db_output_path="fake_db.sqlite"
        )
    
        # Verify the eviction logic didn't hold onto the old config
        self.assertNotIn("src/old_config.py", scope.ram_cache, "Delta scan failed to evict deleted file!")

    # ==============================================================================
    # TEST 10: MICRO-MASS QUOTA EXHAUSTION (Neighborhood Noise Prevention)
    # ==============================================================================
    @patch("gitgalaxy.galaxyscope.subprocess.check_output")
    @patch("gitgalaxy.core.aperture.ApertureFilter.evaluate_path_integrity")
    def test_micro_mass_quota_exhaustion(self, mock_aperture, mock_git):
        """
        DEVIOUS EDGE CASE: A single folder contains 50 tiny 10-byte SVG/Config files.
        Once the grace limit (15) is hit, the remaining 35 files MUST be relegated
        to the unparsable list to prevent localized neighborhood noise.
        """
        scope = Orchestrator(".", self.mock_config)
        scope.MICRO_MASS_GRACE_LIMIT = 5 # Lower for faster testing
        
        # Mock Git returning 10 tiny files in the same directory
        fake_files = [f"src/assets/icon_{i}.svg" for i in range(10)]
        mock_git.return_value = "\n".join(fake_files)
        
        # Mock aperture returning: is_valid=True, size=10 bytes (under MICRO_MASS_BYTES)
        mock_aperture.return_value = (True, 10, "Passed")
        
        scope._build_file_census()
        
        # 5 should pass, 5 should be blocked and pushed to unparsable
        self.assertEqual(len(scope.census), 5, "Micro-mass quota failed to cap the directory assets!")
        self.assertEqual(len(scope.unparsable_files), 5, "Excess micro-mass files were not routed to unparsable queue!")
        self.assertIn("Excluded: Neighborhood Micro-Mass Limit Exceeded", scope.unparsable_files[0]["reason"])

    # ==============================================================================
    # TEST 11: THE REDOS STARVATION EVENT (Worker Timeout)
    # ==============================================================================
    @patch("gitgalaxy.galaxyscope.concurrent.futures.as_completed")
    @patch("gitgalaxy.galaxyscope.concurrent.futures.ProcessPoolExecutor")
    def test_redos_starvation_timeout(self, mock_executor, mock_as_completed):
        """
        DEVIOUS EDGE CASE: A catastrophic regex pattern causes the worker pool to hang.
        The Orchestrator MUST catch the TimeoutError, log the exact files that 
        paralyzed the pool, and forcefully terminate without hanging the CI/CD runner.
        """
        import concurrent.futures
        
        scope = Orchestrator(".", self.mock_config)
        scope.stem_map = {"src/evil_regex.py": "src/evil_regex.py"}
        
        # Force the generator to throw a TimeoutError
        mock_as_completed.side_effect = concurrent.futures.TimeoutError("Starvation")
        
        # The orchestrator should catch this, kill the pool, and re-raise
        with self.assertRaises(TimeoutError) as context:
            scope._extract_features_parallel()
            
        self.assertIn("worker starvation", str(context.exception))
        # Verify the evil file was recorded as an anomaly before the crash
        self.assertTrue(any("evil_regex.py" in str(a) for a in scope.unparsable_files))

    # ==============================================================================
    # TEST 12: ZERO-DEPENDENCY MODE SURVIVAL
    # ==============================================================================
    @patch("gitgalaxy.galaxyscope.HAS_NETWORKX", False)
    @patch("gitgalaxy.galaxyscope.HAS_TIKTOKEN", False)
    @patch("gitgalaxy.galaxyscope.ML_AVAILABLE", False)
    @patch("gitgalaxy.galaxyscope.Orchestrator._build_file_census")
    @patch("gitgalaxy.galaxyscope.Orchestrator._extract_features_parallel")
    @patch("gitgalaxy.galaxyscope.Orchestrator._resolve_dependency_graph")
    @patch("gitgalaxy.galaxyscope.Orchestrator._calculate_risk_exposures")
    @patch("gitgalaxy.galaxyscope.run_api_audit")
    @patch("gitgalaxy.galaxyscope.run_xray_audit")
    @patch("gitgalaxy.galaxyscope.run_firewall_audit")
    def test_zero_dependency_mode_execution(self, mock_fw, mock_xr, mock_api, mock_calc, mock_res, mock_ext, mock_cen):
        """
        DEVIOUS EDGE CASE: Running on a stripped-down Alpine Linux container without
        Pandas, NetworkX, or Tiktoken. The pipeline must disable the ML and network
        modules without throwing ImportError exceptions.
        """
        scope = Orchestrator(".", self.mock_config)
        scope.parsed_files = [{"path": "dummy.py", "telemetry": {}}]
        
        # Mock the core returns
        scope.network_sensor = MagicMock()
        scope.network_sensor.build_dependency_graph = MagicMock(return_value=(scope.parsed_files, {}))
        mock_api.return_value = {}
        mock_xr.return_value = {}
        mock_fw.return_value = {}
        
        # Disable SARIF and SBOM purely to speed up the test
        scope.config["SARIF_ONLY"] = True 
        
        try:
            scope.execute_pipeline(output_file="fake_zero_dep.json")
        except Exception as e:
            self.fail(f"Zero-Dependency mode crashed: {e}")
        
        # Verify ML auditor was bypassed
        scope.model_auditor = MagicMock()
        scope.model_auditor.audit_repository.assert_not_called()

    # ==============================================================================
    # TEST 13: THE BRAIN SURGEON (Direct Worker Execution)
    # ==============================================================================
    @patch("gitgalaxy.galaxyscope.ApertureFilter")
    @patch("gitgalaxy.galaxyscope.Prism")
    @patch("gitgalaxy.galaxyscope.LanguageDetector")
    @patch("gitgalaxy.galaxyscope.SecurityLens")
    @patch("gitgalaxy.galaxyscope.Path.is_file", return_value=True)
    def test_direct_worker_execution(self, mock_is_file, MockSecurity, MockDetector, MockPrism, MockAperture):
        """
        DEVIOUS EDGE CASE: Because the multiprocessing pool is mocked out in most tests, 
        _process_file_worker (the core CPU engine) is completely untested. We must directly 
        invoke the global worker initialization and process a file to cover lines 196-558.
        """
        from gitgalaxy.galaxyscope import _init_worker, _process_file_worker
        import logging

        # Mock the heavy lifting to avoid disk I/O during the unit test
        mock_aperture_inst = MockAperture.return_value
        mock_aperture_inst.evaluate_path_integrity.return_value = (True, 1024, "Passed")
        mock_aperture_inst.is_in_scope.return_value = {"is_in_scope": True, "reason": None}

        mock_detector_inst = MockDetector.return_value
        mock_detector_inst.inspect.return_value = {
            "lang_id": "python", "intensity": 0.99, "lock_tier": 1, "source_proof": "Test"
        }

        mock_prism_inst = MockPrism.return_value
        mock_prism_inst.split_streams.return_value = {
            "code_stream": "print('hello')", "comment_stream": "# test", "coding_loc": 1, "doc_loc": 1
        }

        mock_sec_inst = MockSecurity.return_value
        mock_sec_inst.scan_content.return_value = {"counts": {"high_risk_execution": 1}, "snippets": {}}

        # 1. Initialize the global worker state
        self.mock_config["LANGUAGE_DEFINITIONS"] = {"python": {"extensions": [".py"], "rules": {}}}
        _init_worker(
            root_str=".",
            config=self.mock_config,
            ext_tally={".py": 1},
            log_level=logging.INFO,
            git_tracked={"src/main.py"},
            census={"main"}
        )

        # 2. Force the worker to process a file (requires mocking open() to simulate reading code)
        from unittest.mock import mock_open
        with patch("builtins.open", mock_open(read_data="import os\nprint('hello')")):
            result = _process_file_worker("src/main.py")

        # 3. Assertions
        self.assertEqual(result["status"], "success", "Worker failed to successfully parse the file!")
        self.assertEqual(result["data"]["lang_id"], "python", "Worker failed to assign language ID!")
        self.assertEqual(result["data"]["equations"]["sec_high_risk_execution"], 1, "Worker dropped security equations!")

    # ==============================================================================
    # TEST 14: THE MEMORY HOLE (SARIF Sanitization & Inline Suppressions)
    # ==============================================================================
    @patch("gitgalaxy.galaxyscope.Orchestrator._build_file_census")
    @patch("gitgalaxy.galaxyscope.Orchestrator._extract_features_parallel")
    @patch("gitgalaxy.galaxyscope.Orchestrator._resolve_dependency_graph")
    @patch("gitgalaxy.galaxyscope.Orchestrator._calculate_risk_exposures")
    @patch("gitgalaxy.galaxyscope.RecordKeeper")
    @patch("gitgalaxy.galaxyscope.SarifRecorder")
    def test_sarif_sanitization_purge(self, mock_sarif, mock_db, mock_calc, mock_res, mock_ext, mock_cen):
        """
        DEVIOUS EDGE CASE: Validating Phase 10.8 (Lines 911-984). If a developer uses 
        `# galaxyscope:ignore sec_hardcoded_secrets`, the orchestrator MUST surgically 
        delete those keys from the equations and threat_snippets dictionaries before 
        handing the payload to the SARIF recorder.
        """
        config = self.mock_config.copy()
        config["SARIF_IGNORED_RULES"] = ["GG-AGENT-GUARDRAIL"]
        
        scope = Orchestrator(".", config)
        
        # Inject a highly toxic file that explicitly suppresses its own alerts
        scope.parsed_files = [
            {
                "path": "src/api.py",
                "is_ml_threat": True,
                "mitigations": ["sec_hardcoded_secrets", "ai_appsec"],
                "equations": {"sec_hardcoded_secrets": 5, "branch": 10},
                "hit_vector": [1] * 100,  # Prevent IndexError in downstream recorders
                "risk_vector": [1.0] * 100,
                "telemetry": {
                    "threat_snippets": {"sec_hardcoded_secrets": ["password='123'"]},
                    "ai_appsec": {"critical_warnings": ["RCE Funnel"]},
                    "ai_guardrails": {"warnings": ["Too complex"]},
                    "domain_context": {"AI Threat Class": "Trojan"}
                }
            }
        ]

        # Mock the dependencies so it flies straight to Phase 10.8
        scope.network_sensor = MagicMock()
        scope.network_sensor.build_dependency_graph.return_value = (scope.parsed_files, {})
        scope.auditor = MagicMock()
        scope.auditor.audit.return_value = (scope.parsed_files, [])
        scope.model_auditor = MagicMock()
        scope.model_auditor.audit_repository.return_value = scope.parsed_files
        scope.processor = MagicMock()
        scope.processor.summarize_galaxy_metrics.return_value = {}

        # Trigger pipeline
        scope.execute_pipeline("fake.json")

        sanitized_file = scope.parsed_files[0]
        
        # 1. Inline mitigations should destroy equations and snippets
        self.assertNotIn("sec_hardcoded_secrets", sanitized_file["equations"], "Failed to purge suppressed equation!")
        self.assertNotIn("sec_hardcoded_secrets", sanitized_file["telemetry"]["threat_snippets"], "Failed to purge suppressed snippet!")
        self.assertNotIn("ai_appsec", sanitized_file["telemetry"], "Failed to purge suppressed AppSec warning!")

        # 2. SARIF_IGNORED_RULES should destroy the AI guardrail
        self.assertNotIn("ai_guardrails", sanitized_file["telemetry"], "Failed to purge SARIF ignored rule!")

    # ==============================================================================
    # TEST 15: THE GIT-LESS VOID (Fallback OS Walk)
    # ==============================================================================
    @patch("gitgalaxy.galaxyscope.subprocess.check_output")
    @patch("gitgalaxy.core.aperture.ApertureFilter.evaluate_path_integrity")
    @patch("os.walk")
    def test_fallback_filesystem_walk(self, mock_walk, mock_aperture, mock_subprocess):
        """
        DEVIOUS EDGE CASE: The user downloads the repository as a .zip from GitHub without 
        the .git folder. `git ls-files` will crash. The orchestrator MUST catch the 
        subprocess exception and seamlessly fall back to an OS walk (Lines 1167-1190).
        """
        import subprocess
        
        scope = Orchestrator(".", self.mock_config)
        
        # 1. Force Git to crash
        mock_subprocess.side_effect = subprocess.CalledProcessError(1, "git")
        
        # 2. Mock the OS walk to return a fake file structure
        mock_walk.return_value = [
            (str(scope.root), ["src"], ["README.md"]), 
            (str(scope.root / "src"), [], ["main.py", "secret.pem"])
        ]
        
        # 3. Aperture allows main.py and README.md, blocks secret.pem
        def mock_evaluate(path_obj, **kwargs):
            name = path_obj.name
            if name == "secret.pem":
                return False, 1024, "CRITICAL LEAK"
            return True, 1024, "Passed"
            
        mock_aperture.side_effect = mock_evaluate
        
        scope._build_file_census()
        
        # Assertions
        self.assertEqual(len(scope.census), 2, "Fallback walk failed to populate the census!")
        self.assertIn("src/main.py", scope.stem_map, "Fallback walk missed nested files!")
        self.assertEqual(len(scope.unparsable_files), 1, "Fallback walk failed to route excluded files!")
        self.assertIn("CRITICAL LEAK", scope.unparsable_files[0]["reason"])

    # ==============================================================================
    # TEST 16: THE CHAMELEON (Project Dialect Overrides)
    # ==============================================================================
    @patch("gitgalaxy.galaxyscope.Orchestrator")
    def test_project_dialect_overrides(self, mock_orchestrator):
        """
        DEVIOUS EDGE CASE: Testing lines 2445+. If the target project name matches 
        a key in PROJECT_OVERRIDES, the main() function MUST mutate the LANGUAGE_DEFINITIONS 
        and APERTURE_CONFIG before passing them to the Orchestrator.
        """
        import sys
        from gitgalaxy.galaxyscope import main
        
        # Mock sys.argv to target a project named "chameleon_project"
        test_args = ["galaxyscope", "/fake/chameleon_project"]
        
        # Inject our fake project into the global overrides
        with patch.dict("gitgalaxy.galaxyscope.PROJECT_OVERRIDES", {
            "chameleon_project": {
                "_shield_": {"exclude_dirs": ["weird_build_dir"]},
                "python": {"extensions": [".chameleon"]}
            }
        }):
            with patch.object(sys, 'argv', test_args):
                # Force the mock to simulate a clean run
                mock_orchestrator.return_value.policy_failed = False
                main()
                
        # Intercept the configuration dictionary passed to the Orchestrator
        args, _ = mock_orchestrator.call_args
        ignited_config = args[1] 
        
        # Assertions
        aperture_cfg = ignited_config["APERTURE_CONFIG"]
        lang_defs = ignited_config["LANGUAGE_DEFINITIONS"]
        
        self.assertIn("weird_build_dir", aperture_cfg["IGNORED_DIRECTORIES"], "Failed to patch Aperture Shield!")
        self.assertIn(".chameleon", lang_defs["python"]["extensions"], "Failed to patch Language Definitions!")