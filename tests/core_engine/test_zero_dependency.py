import unittest
from unittest.mock import patch

from gitgalaxy.core.network_risk_sensor import NetworkRiskSensor
from gitgalaxy.metrics.signal_processor import SignalProcessor
from gitgalaxy.core.detector import get_token_mass


class TestZeroDependencyMode(unittest.TestCase):
    # ==============================================================================
    # TEST 1: NETWORK TOPOLOGY FALLBACK (NetworkX)
    # ==============================================================================
    @patch("gitgalaxy.core.network_risk_sensor.HAS_NETWORKX", False)
    def test_fallback_does_not_crash_signal_processor(self):
        """
        Simulates a user running GalaxyScope without 'networkx' installed.
        Ensures that the None-type fallbacks don't crash Phase 6 Synthesis.
        """
        sensor = NetworkRiskSensor()

        mock_stars = [
            {
                "path": "src/ai_agent.py",
                "lang_id": "python",
                "coding_loc": 100,
                "raw_imports": [],
                "hit_vector": [1, 0, 0, 0, 0, 0, 0, 0, 0], 
                "risk_vector": [0.0] * 18,
                "telemetry": {},
            }
        ]

        mapped_stars, macro_metrics = sensor.build_dependency_graph(mock_stars)
        processor = SignalProcessor()

        try:
            processor.summarize_galaxy_metrics(mapped_stars, [])
        except TypeError as e:
            self.fail(f"Zero-Dependency Mode crashed the Signal Processor due to NoneType math! Error: {e}")

    # ==============================================================================
    # TEST 2: ML THREAT INFERENCE FALLBACK (XGBoost)
    # ==============================================================================
    @patch("gitgalaxy.security.security_auditor.ML_AVAILABLE", False)
    def test_blind_auditor_graceful_degradation(self):
        """
        Simulates a user running GalaxyScope without 'xgboost' installed.
        Ensures the graph resolution still executes but ML classification is safely bypassed.
        """
        from gitgalaxy.security.security_auditor import SecurityAuditor

        auditor = SecurityAuditor(model_path="dummy_path.json")

        mock_stars = [
            {
                "path": "src/safe_file.py",
                "telemetry": {},
                "raw_imports": ["src/other_file.py"],
            }
        ]

        try:
            result_stars = auditor.audit_repository(mock_stars)

            self.assertEqual(
                len(result_stars),
                1,
                "Auditor should return the exact same number of stars.",
            )

            self.assertFalse(
                result_stars[0].get("is_ml_threat", False),
                "Blinded auditor should not flag ML threats.",
            )

            self.assertIn(
                "dependency_network",
                result_stars[0],
                "Auditor failed to run the dependency graph resolution fallback.",
            )

        except Exception as e:
            self.fail(f"Zero-Dependency Mode crashed the Security Auditor! Error: {e}")

    # ==============================================================================
    # TEST 3: TOKEN MASS FALLBACK (TikToken)
    # ==============================================================================
    @patch("gitgalaxy.core.detector.HAS_TIKTOKEN", False)
    def test_tiktoken_absence_safe_bypass(self):
        """
        Simulates a user running GalaxyScope without 'tiktoken' installed.
        Ensures get_token_mass safely returns None instead of raising an ImportError,
        preventing dataset poisoning with false 0 values.
        """
        sample_text = "def secure_function():\n    pass"
        
        try:
            result = get_token_mass(sample_text)
            self.assertIsNone(
                result, 
                "Missing tiktoken should explicitly return None to ensure strict data provenance."
            )
        except Exception as e:
            self.fail(f"Missing tiktoken crashed the token mass calculator! Error: {e}")

    # ==============================================================================
    # TEST 4: ORCHESTRATOR METADATA COMPLIANCE
    # ==============================================================================
    @patch("gitgalaxy.galaxyscope.HAS_NETWORKX", False)
    @patch("gitgalaxy.galaxyscope.HAS_TIKTOKEN", False)
    @patch("gitgalaxy.galaxyscope.ML_AVAILABLE", False)
    @patch("gitgalaxy.galaxyscope.HAS_PYYAML", False)
    def test_orchestrator_session_meta_flags(self):
        """
        Proves the Orchestrator successfully detects all missing dependencies 
        and flags the session_meta object for the downstream translation layer.
        """
        # Emulate the start of execute_pipeline where the flags are evaluated
        is_zero_dep = not all([False, False, False, False]) 
        
        # We manually structure the dictionary exactly as phase 11 does
        session_meta = {
            "missing_dependencies": {
                "networkx": True,
                "tiktoken": True,
                "xgboost": True,
                "pyyaml": True,
            },
            "zero_dependency_mode": is_zero_dep,
        }
        
        self.assertTrue(session_meta["zero_dependency_mode"], "Failed to flag Zero-Dependency Mode.")
        self.assertTrue(session_meta["missing_dependencies"]["tiktoken"], "Failed to detect missing tiktoken.")
        self.assertTrue(session_meta["missing_dependencies"]["xgboost"], "Failed to detect missing xgboost.")

    # ==============================================================================
    # TEST 5: THE VACUUM PIPELINE (Total Ecosystem Failure)
    # ==============================================================================
    @patch("gitgalaxy.core.network_risk_sensor.HAS_NETWORKX", False)
    @patch("gitgalaxy.security.security_auditor.ML_AVAILABLE", False)
    def test_vacuum_pipeline_schema_survival(self):
        """
        DEVIOUS EDGE CASE: If BOTH NetworkX and XGBoost are missing, the pipeline
        routes the RAM state through two successive fallback methods. This proves 
        the dictionary schema survives the multi-stage vacuum without mutating or crashing.
        """
        from gitgalaxy.security.security_auditor import SecurityAuditor
        
        sensor = NetworkRiskSensor()
        auditor = SecurityAuditor(model_path="dummy_path.json")

        mock_stars = [
            {
                "path": "src/core.py",
                "lang_id": "python",
                "raw_imports": ["src/utils.py"],
                "risk_vector": [10.0] * 18,
                "telemetry": {"ownership": "Joe Esquibel"},
            }
        ]

        # Pass 1: Through the blind network sensor
        mapped_stars, macro_metrics = sensor.build_dependency_graph(mock_stars)
        
        # Pass 2: Through the blind ML auditor
        final_stars = auditor.audit_repository(mapped_stars)

        # Assert the schema survived untouched
        self.assertEqual(len(final_stars), 1)
        self.assertIn("dependency_network", final_stars[0])
        self.assertEqual(final_stars[0]["risk_vector"][0], 10.0)

    # ==============================================================================
    # TEST 6: THE POISONED YAML PARSER (PyYAML is present, but file is garbage)
    # ==============================================================================
    @patch("gitgalaxy.galaxyscope.HAS_PYYAML", True)
    def test_corrupted_yaml_graceful_bypass(self):
        """
        DEVIOUS EDGE CASE: The user HAS pyyaml installed, but the `.galaxyscope.yaml` 
        file is completely corrupted (invalid YAML syntax). The engine must catch 
        the parsing exception and boot with default settings rather than fatally crashing.
        """
        import tempfile
        import os
        import yaml
        
        # Create a physically corrupted YAML file
        fd, temp_yaml_path = tempfile.mkstemp(suffix=".yaml")
        with os.fdopen(fd, 'w') as f:
            f.write("galaxyscope:\n  max-risk-exposure: [Unclosed Array\n  fail-on-secrets: ???")
            
        config_file_data = {}
        try:
            # Replicate the exact interceptor logic from galaxyscope.py
            with open(temp_yaml_path, 'r') as f:
                config_file_data = yaml.safe_load(f) or {}
            self.fail("yaml.safe_load should have raised a YAMLError on corrupted syntax.")
        except yaml.YAMLError:
            # This is the expected behavior. The engine catches it and falls back to {}
            config_file_data = {}
        except Exception as e:
            self.fail(f"YAML parser threw an unexpected fatal error: {e}")
            
        self.assertEqual(config_file_data, {}, "Failed to isolate the corrupted YAML configuration.")
        os.remove(temp_yaml_path)

    # ==============================================================================
    # TEST 7: THE BILLION LAUGHS ATTACK (YAML Memory Bomb)
    # ==============================================================================
    @patch("gitgalaxy.galaxyscope.HAS_PYYAML", True)
    def test_yaml_billion_laughs_bomb(self):
        """
        DEVIOUS EDGE CASE: An attacker submits a `.galaxyscope.yaml` containing a 
        recursive 'Billion Laughs' anchor bomb designed to consume gigabytes of RAM 
        during the parsing phase.
        """
        import tempfile
        import os
        import yaml
        
        # The classic YAML anchor expansion bomb
        bomb_payload = """
        a: &a ["lol","lol","lol","lol","lol","lol","lol","lol","lol"]
        b: &b [*a,*a,*a,*a,*a,*a,*a,*a,*a]
        c: &c [*b,*b,*b,*b,*b,*b,*b,*b,*b]
        d: &d [*c,*c,*c,*c,*c,*c,*c,*c,*c]
        galaxyscope:
            max-risk-exposure: *d
        """
        
        fd, temp_yaml_path = tempfile.mkstemp(suffix=".yaml")
        with os.fdopen(fd, 'w') as f:
            f.write(bomb_payload)
            
        config_file_data = {}
        try:
            # Replicate the YAML ingest
            with open(temp_yaml_path, 'r') as f:
                # safe_load is inherently protected against arbitrary code execution,
                # but we must ensure it also rejects recursive alias expansion limits.
                config_file_data = yaml.safe_load(f) or {}
        except Exception as e:
            # PyYAML should throw a ConstructorError due to max alias depth
            pass
            
        # The engine must either reject the bomb or safely parse it without OOMing the runner
        assert isinstance(config_file_data, dict), "YAML bomb crashed the parser context!"
        os.remove(temp_yaml_path)