import pytest
import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import gitgalaxy.tools.supply_chain_security.supply_chain_firewall as firewall_module

# ==============================================================================
# TEST 1: Dependency Graph Import Verification
# ==============================================================================
def test_zero_trust_import_verification(monkeypatch):
    """
    Validates that the firewall correctly segregates imports into approved,
    unknown, and blacklisted categories based on enterprise policy constraints.
    """
    monkeypatch.setattr(firewall_module, "APPROVED_IMPORTS", ["react", "express"])
    monkeypatch.setattr(
        firewall_module, "BLACKLISTED_IMPORTS", ["event-stream-malware"]
    )

    mock_ram_graph = [
        {
            "path": "app.js",
            "raw_imports": ["react", "event-stream-malware"],
            "equations": {},
            "coding_loc": 50,
        },
        {
            "path": "main.py",
            "raw_imports": ["django"],
            "equations": {},
            "coding_loc": 20,
        },
    ]

    result = firewall_module.run_firewall_audit(mock_ram_graph)
    assert result["imports_whitelisted"] == 1, "Failed to identify approved package."
    assert result["imports_blacklisted"] == 1, "Failed to identify blacklisted package."
    assert result["imports_unknown"] == 1, "Failed to identify unknown package."
    assert result["threats_found"] == 1, "Blacklisted package did not increment threat counter."

# ==============================================================================
# TEST 2: Local Path and Sub-Module Truncation Shield
# ==============================================================================
def test_import_truncation_and_local_shield(monkeypatch):
    """
    Ensures that local relative imports are ignored, and deeply nested
    scoped packages (@org/pkg/module) are properly truncated for evaluation.
    """
    monkeypatch.setattr(firewall_module, "APPROVED_IMPORTS", ["@angular/core", "lodash"])
    monkeypatch.setattr(firewall_module, "BLACKLISTED_IMPORTS", [])

    mock_ram_graph = [
        {
            "path": "component.ts",
            # .local should be ignored. @angular/core/testing should truncate to @angular/core
            "raw_imports": ["./local-service", "@angular/core/testing", "lodash/fp"],
            "equations": {},
            "coding_loc": 50,
        }
    ]

    result = firewall_module.run_firewall_audit(mock_ram_graph)
    assert result["imports_whitelisted"] == 2, "Failed to truncate and match scoped/nested dependencies."
    assert result["imports_unknown"] == 0, "Local relative import was erroneously evaluated."

# ==============================================================================
# TEST 3: Alias Spoofing Detection
# ==============================================================================
def test_alias_spoofing_detection(monkeypatch, caplog):
    """
    Validates that the firewall correctly detects when a safe alias is mapped
    to a blacklisted upstream package via the alias_map.
    """
    monkeypatch.setattr(firewall_module, "APPROVED_IMPORTS", [])
    monkeypatch.setattr(firewall_module, "BLACKLISTED_IMPORTS", ["malicious-core"])

    mock_ram_graph = [
        {
            "path": "package.json",
            "raw_imports": ["safe-utils"],
            "equations": {},
            "coding_loc": 10,
        }
    ]
    
    # Simulate an npm alias: "safe-utils": "npm:malicious-core@1.0"
    # Namespaced to the current directory (".")
    mock_alias_map = {".": {"safe-utils": "malicious-core"}}

    result = firewall_module.run_firewall_audit(mock_ram_graph, alias_map=mock_alias_map)
    
    assert result["imports_blacklisted"] == 1, "Failed to dereference spoofed alias."
    assert result["threats_found"] == 1, "Spoofed alias did not increment threat counter."
    assert "Spoofed alias blocked" in caplog.text, "Missing spoofed alias log output."

# ==============================================================================
# TEST 4: Strict Policy Enforcement Mode (Updated Schema)
# ==============================================================================
def test_strict_mode_enforcement(tmp_path, monkeypatch):
    """
    Ensures that when STRICT_IMPORT_MODE is enabled, any unknown dependency
    causes the pipeline to fail with a SystemExit.
    """
    monkeypatch.setattr(firewall_module, "APPROVED_IMPORTS", ["react"])
    monkeypatch.setattr(firewall_module, "BLACKLISTED_IMPORTS", [])
    monkeypatch.setattr(firewall_module, "STRICT_IMPORT_MODE", True)

    mock_ram_graph = {
        "6. Parsed Files (Scanned Artifacts)": {
            "root": {
                "Files": {
                    "server.js": {
                        "raw_imports": ["shadow-library"],
                        "equations": {},
                        "coding_loc": 50
                    }
                }
            }
        }
    }

    graph_file = tmp_path / "results.json"
    graph_file.write_text(json.dumps(mock_ram_graph), encoding="utf-8")

    test_args = ["supply_chain_firewall.py", str(graph_file)]
    with patch.object(sys, "argv", test_args):
        with pytest.raises(SystemExit) as exc:
            firewall_module.main()
        assert exc.value.code == 1, "Strict import policy enforcement failed to block an unknown package."

# ==============================================================================
# TEST 5: Behavioral Threat Density Evaluation (Updated Schema)
# ==============================================================================
def test_behavioral_threat_evaluation(tmp_path, monkeypatch):
    """
    Validates that artifacts exhibiting high-density threat indicators
    (calculated during Phase 1) trigger a firewall block.
    """
    monkeypatch.setattr(firewall_module, "STRICT_IMPORT_MODE", False)
    monkeypatch.setattr(firewall_module, "BLACKLISTED_IMPORTS", [])

    mock_ram_graph_threat = {
        "6. Parsed Files (Scanned Artifacts)": {
            "root": {
                "Files": {
                    "logic.js": {
                        "raw_imports": [],
                        "equations": {"sec_homoglyphs": 500, "sec_high_risk_execution": 50},
                        "coding_loc": 50,
                    }
                }
            }
        }
    }

    graph_file = tmp_path / "results.json"
    graph_file.write_text(json.dumps(mock_ram_graph_threat), encoding="utf-8")

    test_args = ["supply_chain_firewall.py", str(graph_file)]

    with patch.object(sys, "argv", test_args):
        with pytest.raises(SystemExit) as exc:
            firewall_module.main()
        assert exc.value.code == 1, "Behavioral threat density evaluation failed to trigger pipeline failure."

# ==============================================================================
# TEST 6: Build-Time Execution Multiplier (Static Sandbox)
# ==============================================================================
def test_build_time_execution_multiplier(monkeypatch):
    """
    Ensures that critical build files (like setup.py) have their risk equations
    artificially multiplied to make them hyper-sensitive to anomalous logic.
    """
    monkeypatch.setattr(firewall_module, "STRICT_IMPORT_MODE", False)
    
    mock_ram_graph = [
        {
            "path": "setup.py",
            "raw_imports": [],
            "equations": {"sec_high_risk_execution": 20},
            "coding_loc": 1000,
        },
        {
            "path": "standard_app.py",
            "raw_imports": [],
            "equations": {"sec_high_risk_execution": 20},
            "coding_loc": 1000,
        }
    ]

    result = firewall_module.run_firewall_audit(mock_ram_graph)
    assert result["threats_found"] == 1, "Build-time multiplier failed to amplify threat in setup.py."

# ==============================================================================
# TEST 7: CLI Main - Missing Target Validation
# ==============================================================================
def test_main_missing_target(capsys):
    """Proves the CLI catches invalid directories and exits safely."""
    with patch("sys.argv", ["supply_chain_firewall.py", "non_existent_graph.json"]):
        with pytest.raises(SystemExit) as exc_info:
            firewall_module.main()

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Error: Target" in captured.out

# ==============================================================================
# TEST 8: CLI Main - Corrupted JSON Handling
# ==============================================================================
def test_main_corrupted_json(tmp_path, capsys):
    """Ensures the firewall gracefully exits if the input graph is malformed."""
    broken_graph = tmp_path / "broken.json"
    broken_graph.write_text("{ broken_json: ", encoding="utf-8")

    with patch("sys.argv", ["supply_chain_firewall.py", str(broken_graph)]):
        with pytest.raises(SystemExit) as exc_info:
            firewall_module.main()

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Failed to parse RAM graph:" in captured.out

# ==============================================================================
# TEST 9: Monorepo Contextual Alias Resolution
# ==============================================================================
def test_monorepo_contextual_alias_resolution(monkeypatch, caplog):
    """
    Proves that the firewall resolves package aliases contextually based on the 
    physical directory of the audited file, traversing upwards to find the nearest
    authoritative manifest and preventing monorepo alias clobbering.
    """
    monkeypatch.setattr(firewall_module, "APPROVED_IMPORTS", [])
    monkeypatch.setattr(firewall_module, "BLACKLISTED_IMPORTS", ["malicious-core", "rogue-ui"])

    mock_alias_map = {
        "frontend": {"lodash": "rogue-ui"},
        "backend/src": {"lodash": "malicious-core"},
        "backend": {"express": "safe-express"} 
    }

    mock_ram_graph = [
        {"path": "frontend/component.jsx", "raw_imports": ["lodash"], "equations": {}, "coding_loc": 10},
        {"path": "backend/src/server.js", "raw_imports": ["lodash"], "equations": {}, "coding_loc": 10},
        {"path": "backend/src/utils/helper.js", "raw_imports": ["lodash"], "equations": {}, "coding_loc": 10},
        {"path": "backend/src/utils/router.js", "raw_imports": ["express"], "equations": {}, "coding_loc": 10},
        {"path": "scripts/deploy.js", "raw_imports": ["lodash"], "equations": {}, "coding_loc": 10}
    ]

    result = firewall_module.run_firewall_audit(mock_ram_graph, alias_map=mock_alias_map)

    assert result["imports_blacklisted"] == 3, "Failed to resolve contextual aliases correctly!"
    assert result["threats_found"] == 3, "Failed to increment threats for contextually spoofed packages!"
    assert "'lodash' -> 'rogue-ui'" in caplog.text, "Failed to resolve exact directory alias (Frontend)!"
    assert "'lodash' -> 'malicious-core'" in caplog.text, "Failed to traverse upwards to authoritative manifest!"

# ==============================================================================
# TEST 10: THE ALLOWLIST LOOPHOLE GUARD (UNHAPPY PATH)
# ==============================================================================
def test_firewall_allowlist_loophole_guard(monkeypatch):
    """
    Proves that a file residing in an ALLOWLIST_PATH can bypass strict mode 
    for unknown imports, but is STILL blocked if it imports a known BLACKLISTED package.
    """
    monkeypatch.setattr(firewall_module, "ALLOWLIST_PATHS", ["experiments/"])
    monkeypatch.setattr(firewall_module, "BLACKLISTED_IMPORTS", ["known-malware"])
    monkeypatch.setattr(firewall_module, "STRICT_IMPORT_MODE", True)

    mock_ram_graph = [
        {
            "path": "experiments/test_script.js",
            "raw_imports": ["unknown-package", "known-malware"],
            "equations": {},
            "coding_loc": 10,
        }
    ]

    result = firewall_module.run_firewall_audit(mock_ram_graph)
    assert result["imports_unknown"] == 1
    assert result["imports_blacklisted"] == 1
    assert result["threats_found"] == 1, "Blacklisted import bypassed the firewall via the Allowlist Loophole!"


# ==============================================================================
# TEST 11: ISSUE #156 - THE 'SEC_' PREFIX STRIPPING BUG
# ==============================================================================
def test_behavioral_threat_evaluation_strips_prefix(tmp_path, monkeypatch):
    """Proves the firewall correctly strips the 'sec_' prefix from Phase 1 equations."""
    monkeypatch.setattr(firewall_module, "STRICT_IMPORT_MODE", False)

    mock_ram_graph = {
        "6. Parsed Files (Scanned Artifacts)": {
            "src": {
                "Files": {
                    "logic.js": {
                        "raw_imports": [],
                        "equations": {"sec_logic_bomb": 100, "sec_high_risk_execution": 50},
                        "coding_loc": 50,
                    }
                }
            }
        }
    }

    graph_file = tmp_path / "results.json"
    graph_file.write_text(json.dumps(mock_ram_graph), encoding="utf-8")
    
    with patch.object(sys, "argv", ["supply_chain_firewall.py", str(graph_file)]):
        with pytest.raises(SystemExit):
            firewall_module.main()

# ==============================================================================
# TEST 12: ISSUE #157 - THE TUPLE CRASH
# ==============================================================================
def test_tuple_import_handling(tmp_path, monkeypatch):
    """Proves the firewall safely unpacks Phase 2 entity tuples from the imports array."""
    monkeypatch.setattr(firewall_module, "STRICT_IMPORT_MODE", False)
    
    mock_ram_graph = {
        "6. Parsed Files (Scanned Artifacts)": {
            "root": {
                "Files": {
                    "app.py": {
                        "raw_imports": [("express", "Router"), "normal-string"],
                        "equations": {},
                        "coding_loc": 100
                    }
                }
            }
        }
    }

    graph_file = tmp_path / "results.json"
    graph_file.write_text(json.dumps(mock_ram_graph), encoding="utf-8")
    
    with patch.object(sys, "argv", ["supply_chain_firewall.py", str(graph_file)]):
        try:
            firewall_module.main()
        except SystemExit:
            pytest.fail("Firewall triggered SystemExit on safe tuple imports.")

# ==============================================================================
# TEST 13: ISSUES #158 & #162 - STANDALONE DIRECTORY CRASH & GLOB MISMATCH
# ==============================================================================
@patch("subprocess.run")
def test_directory_execution_and_globbing(mock_subprocess_run, tmp_path, monkeypatch):
    """Proves passing a directory triggers the orchestrator and globs correctly."""
    monkeypatch.setattr(firewall_module, "STRICT_IMPORT_MODE", False)
    target_dir = tmp_path / "mock_repo"
    target_dir.mkdir()
    
    def mock_run_side_effect(*args, **kwargs):
        # Correctly extract the target output path from the subprocess call arguments
        call_args = args[0]
        out_target = Path(call_args[call_args.index("--output") + 1])
        audit_file = out_target.parent / "firewall_temp_audit.json"
        
        mock_audit_content = {
            "6. Parsed Files (Scanned Artifacts)": {
                "root": {
                    "Files": {"app.js": {"raw_imports": [], "equations": {}, "coding_loc": 10}}
                }
            }
        }
        audit_file.write_text(json.dumps(mock_audit_content))
        return MagicMock(returncode=0)

    mock_subprocess_run.side_effect = mock_run_side_effect

    with patch.object(sys, "argv", ["supply_chain_firewall.py", str(target_dir)]):
        try:
            firewall_module.main()
        except SystemExit:
            pytest.fail("Firewall crashed during standalone directory execution.")
            
    called_args = mock_subprocess_run.call_args[0][0]
    assert "--output" in called_args
    output_target = called_args[called_args.index("--output") + 1]
    assert output_target.endswith("firewall_temp.json")

# ==============================================================================
# TEST 14: ISSUE #159 - SILENT "0 FILES SCANNED" FAILURE (SCHEMA MISMATCH)
# ==============================================================================
def test_directory_group_schema_parsing(tmp_path, monkeypatch, capsys):
    """Proves the firewall iterates nested directory groups to extract files."""
    monkeypatch.setattr(firewall_module, "STRICT_IMPORT_MODE", False)

    mock_ram_graph = {
        "6. Parsed Files (Scanned Artifacts)": {
            "src/backend": {
                "Files": {
                    "server.py": {"raw_imports": [], "equations": {}, "coding_loc": 10}
                }
            },
            "src/frontend": {
                "Files": {
                    "ui.jsx": {"raw_imports": [], "equations": {}, "coding_loc": 10}
                }
            }
        }
    }

    graph_file = tmp_path / "results.json"
    graph_file.write_text(json.dumps(mock_ram_graph), encoding="utf-8")
    
    with patch.object(sys, "argv", ["supply_chain_firewall.py", str(graph_file)]):
        try:
            firewall_module.main()
        except SystemExit:
            pytest.fail("Failed on clean schema test.")
            
    captured = capsys.readouterr()
    assert "Files Evaluated      : 2" in captured.out

# ==============================================================================
# TEST 15: ISSUE #160 - DENSITY DILUTION BUG
# ==============================================================================
def test_density_dilution_fix_for_build_scripts(tmp_path, monkeypatch):
    """Proves that small build scripts are NOT diluted by +150 LOC padding."""
    monkeypatch.setattr(firewall_module, "STRICT_IMPORT_MODE", False)

    mock_ram_graph = {
        "6. Parsed Files (Scanned Artifacts)": {
            "root": {
                "Files": {
                    "postinstall.js": {
                        "raw_imports": [],
                        "equations": {"sec_high_risk_execution": 10},
                        "coding_loc": 5, 
                    }
                }
            }
        }
    }

    graph_file = tmp_path / "results.json"
    graph_file.write_text(json.dumps(mock_ram_graph), encoding="utf-8")
    
    with patch.object(sys, "argv", ["supply_chain_firewall.py", str(graph_file)]):
        with pytest.raises(SystemExit):
            firewall_module.main()

# ==============================================================================
# TEST 16: ISSUE #161 - MISSING THREAT VECTORS (MEMORY CORRUPTION)
# ==============================================================================
def test_memory_corruption_detection(tmp_path, monkeypatch):
    """Proves 'Memory Corruption Risk' triggers a blocking action when detected."""
    monkeypatch.setattr(firewall_module, "STRICT_IMPORT_MODE", False)

    mock_ram_graph = {
        "6. Parsed Files (Scanned Artifacts)": {
            "root": {
                "Files": {
                    "payload.c": {
                        "raw_imports": [],
                        "equations": {"sec_memory_corruption": 500},
                        "coding_loc": 50,
                    }
                }
            }
        }
    }

    graph_file = tmp_path / "results.json"
    graph_file.write_text(json.dumps(mock_ram_graph), encoding="utf-8")
    
    with patch.object(sys, "argv", ["supply_chain_firewall.py", str(graph_file)]):
        with pytest.raises(SystemExit):
            firewall_module.main()