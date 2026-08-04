import pytest
import sys
import json
import multiprocessing
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock

import gitgalaxy.tools.supply_chain_security.supply_chain_firewall as firewall_module
from gitgalaxy.metrics.signal_processor import SignalProcessor
from gitgalaxy.standards.config_resolver import ResolvedConfig, resolve_config


def _risk_vector(**scores):
    """Builds a risk_vector fixture, e.g. _risk_vector(secrets_risk=70.0)."""
    vector = [0.0] * len(SignalProcessor.RISK_SCHEMA)
    for key, value in scores.items():
        vector[SignalProcessor.RISK_SCHEMA.index(key)] = value
    return vector


def _make_config(**overrides):
    """
    Builds a ResolvedConfig for direct run_firewall_audit() calls (#335):
    starts from real gitgalaxy_config.py defaults (via resolve_config()) and
    overlays just the keys a given test cares about, replacing the old
    monkeypatch.setattr(firewall_module, "X", ...) pattern now that the
    firewall reads config off a passed-in object instead of module globals.
    """
    values = resolve_config().to_dict()
    values.update(overrides)
    return ResolvedConfig(_values=values)


def _write_config_yaml(tmp_path, **overrides):
    """
    Writes a .galaxyscope.yaml for main()-based tests that need a
    non-default gitgalaxy_config.py key. Exercises the real --config path
    end-to-end (the same resolve_config() galaxyscope.py's main() uses)
    instead of monkeypatching module internals that no longer exist.
    """
    yaml_path = tmp_path / ".galaxyscope.yaml"
    yaml_path.write_text(yaml.dump({"galaxyscope": overrides}))
    return str(yaml_path)


# ==============================================================================
# TEST 1: Dependency Graph Import Verification
# ==============================================================================
def test_zero_trust_import_verification():
    """
    Validates that the firewall correctly segregates imports into approved,
    unknown, and blacklisted categories based on enterprise policy constraints.
    """
    config = _make_config(
        APPROVED_IMPORTS=["react", "express"],
        BLACKLISTED_IMPORTS=["event-stream-malware"],
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

    result = firewall_module.run_firewall_audit(mock_ram_graph, config=config)
    assert result["imports_whitelisted"] == 1, "Failed to identify approved package."
    assert result["imports_blacklisted"] == 1, "Failed to identify blacklisted package."
    assert result["imports_unknown"] == 1, "Failed to identify unknown package."
    assert result["threats_found"] == 1, "Blacklisted package did not increment threat counter."


# ==============================================================================
# TEST 2: Local Path and Sub-Module Truncation Shield
# ==============================================================================
def test_import_truncation_and_local_shield():
    """
    Ensures that local relative imports are ignored, and deeply nested
    scoped packages (@org/pkg/module) are properly truncated for evaluation.
    """
    config = _make_config(APPROVED_IMPORTS=["@angular/core", "lodash"])

    mock_ram_graph = [
        {
            "path": "component.ts",
            # .local should be ignored. @angular/core/testing should truncate to @angular/core
            "raw_imports": ["./local-service", "@angular/core/testing", "lodash/fp"],
            "equations": {},
            "coding_loc": 50,
        }
    ]

    result = firewall_module.run_firewall_audit(mock_ram_graph, config=config)
    assert result["imports_whitelisted"] == 2, "Failed to truncate and match scoped/nested dependencies."
    assert result["imports_unknown"] == 0, "Local relative import was erroneously evaluated."


# ==============================================================================
# TEST 2.5: Semantic Miswiring Fix (Issue #711)
# ==============================================================================
def test_threats_found_counts_unique_files_only():
    """
    Validates that the threats_found counter increments exactly once per file,
    even if the file contains multiple risk occurrences (e.g. multiple blacklisted
    imports or a combination of blacklisted imports and a structural threat).
    """
    config = _make_config(
        BLACKLISTED_IMPORTS=["malware-one", "malware-two"],
    )

    mock_ram_graph = [
        {
            "path": "infected_file.js",
            "raw_imports": ["malware-one", "malware-two"],
            # Also add a structural threat to ensure it doesn't double count
            "risk_vector": _risk_vector(secrets_risk=80.0),
            "equations": {},
            "coding_loc": 50,
        },
        {
            "path": "another_infected_file.js",
            "raw_imports": ["malware-one"],
            "risk_vector": _risk_vector(),
            "equations": {},
            "coding_loc": 20,
        },
    ]

    result = firewall_module.run_firewall_audit(mock_ram_graph, config=config)

    # 3 blacklisted imports were found
    assert result["imports_blacklisted"] == 3
    # But only 2 unique files contained threats
    assert result["threats_found"] == 2, "threats_found counted per-occurrence rather than per-file!"


# ==============================================================================
# TEST 3: Alias Spoofing Detection
# ==============================================================================
def test_alias_spoofing_detection(caplog):
    """
    Validates that the firewall correctly detects when a safe alias is mapped
    to a blacklisted upstream package via the alias_map.
    """
    config = _make_config(BLACKLISTED_IMPORTS=["malicious-core"])

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

    result = firewall_module.run_firewall_audit(mock_ram_graph, alias_map=mock_alias_map, config=config)

    assert result["imports_blacklisted"] == 1, "Failed to dereference spoofed alias."
    assert result["threats_found"] == 1, "Spoofed alias did not increment threat counter."
    assert "Spoofed alias blocked" in caplog.text, "Missing spoofed alias log output."


# ==============================================================================
# TEST 4: Strict Policy Enforcement Mode (Updated Schema)
# ==============================================================================
def test_strict_mode_enforcement(tmp_path):
    """
    Ensures that when STRICT_IMPORT_MODE is enabled, any unknown dependency
    causes the pipeline to fail with a SystemExit.
    """
    config_path = _write_config_yaml(tmp_path, APPROVED_IMPORTS=["react"], STRICT_IMPORT_MODE=True)

    mock_ram_graph = {
        "6. Parsed Files (Scanned Artifacts)": {
            "root": {"Files": {"server.js": {"raw_imports": ["shadow-library"], "equations": {}, "coding_loc": 50}}}
        }
    }

    graph_file = tmp_path / "results.json"
    graph_file.write_text(json.dumps(mock_ram_graph), encoding="utf-8")

    test_args = ["supply_chain_firewall.py", str(graph_file), "--config", config_path]
    with patch.object(sys, "argv", test_args):
        with pytest.raises(SystemExit) as exc:
            firewall_module.main()
        assert exc.value.code == 1, "Strict import policy enforcement failed to block an unknown package."


# ==============================================================================
# TEST 5: Behavioral Threat Score Evaluation (risk_vector Schema)
# ==============================================================================
def test_behavioral_threat_evaluation(tmp_path):
    """
    Validates that a file whose Phase 3 risk_vector score for a gated category
    is at/above the firewall's block threshold (50.0, SignalProcessor's own
    sigmoid midpoint) triggers a firewall block.

    STRICT_IMPORT_MODE=False and BLACKLISTED_IMPORTS=[] are gitgalaxy_config.py's
    real defaults, so no --config override is needed here (#335) -- this test
    only cares about the behavioral risk_vector path.
    """
    mock_ram_graph_threat = {
        "6. Parsed Files (Scanned Artifacts)": {
            "root": {
                "Files": {
                    "logic.js": {
                        "raw_imports": [],
                        "risk_vector": _risk_vector(secrets_risk=70.0),
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
        assert exc.value.code == 1, "Behavioral threat score evaluation failed to trigger pipeline failure."


# ==============================================================================
# TEST 6: Build-Time Execution Multiplier (Static Sandbox)
# ==============================================================================
def test_build_time_execution_multiplier():
    """
    Ensures that critical build files (like setup.py) have their already-computed
    risk_vector score scaled by the 10x build-time multiplier post-hoc, making
    them hyper-sensitive to anomalous logic that a normal file would not block on.

    secrets_risk=8.0 is chosen deliberately: below the 50.0 block threshold
    on its own (8.0 < 50.0), but 8.0 * 10.0 = 80.0 clears it. This is a real
    numeric re-verification of the post-hoc-scalar design (scaling the sigmoid
    OUTPUT), not a mechanical port of the old pre-sigmoid density multiplier.

    STRICT_IMPORT_MODE=False is gitgalaxy_config.py's real default, so no
    config override is needed here (#335).
    """
    mock_ram_graph = [
        {
            "path": "setup.py",
            "raw_imports": [],
            "risk_vector": _risk_vector(secrets_risk=8.0),
            "coding_loc": 1000,
        },
        {
            "path": "standard_app.py",
            "raw_imports": [],
            "risk_vector": _risk_vector(secrets_risk=8.0),
            "coding_loc": 1000,
        },
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
def test_monorepo_contextual_alias_resolution(caplog):
    """
    Proves that the firewall resolves package aliases contextually based on the
    physical directory of the audited file, traversing upwards to find the nearest
    authoritative manifest and preventing monorepo alias clobbering.
    """
    config = _make_config(BLACKLISTED_IMPORTS=["malicious-core", "rogue-ui"])

    mock_alias_map = {
        "frontend": {"lodash": "rogue-ui"},
        "backend/src": {"lodash": "malicious-core"},
        "backend": {"express": "safe-express"},
    }

    mock_ram_graph = [
        {"path": "frontend/component.jsx", "raw_imports": ["lodash"], "equations": {}, "coding_loc": 10},
        {"path": "backend/src/server.js", "raw_imports": ["lodash"], "equations": {}, "coding_loc": 10},
        {"path": "backend/src/utils/helper.js", "raw_imports": ["lodash"], "equations": {}, "coding_loc": 10},
        {"path": "backend/src/utils/router.js", "raw_imports": ["express"], "equations": {}, "coding_loc": 10},
        {"path": "scripts/deploy.js", "raw_imports": ["lodash"], "equations": {}, "coding_loc": 10},
    ]

    result = firewall_module.run_firewall_audit(mock_ram_graph, alias_map=mock_alias_map, config=config)

    assert result["imports_blacklisted"] == 3, "Failed to resolve contextual aliases correctly!"
    assert result["threats_found"] == 3, "Failed to increment threats for contextually spoofed packages!"
    assert "'lodash' -> 'rogue-ui'" in caplog.text, "Failed to resolve exact directory alias (Frontend)!"
    assert "'lodash' -> 'malicious-core'" in caplog.text, "Failed to traverse upwards to authoritative manifest!"


def _run_firewall_audit_with_absolute_path(result_queue):
    """
    Multiprocessing target for test_absolute_path_does_not_infinite_loop_
    in_alias_resolution below. Rebuilds everything inside the child
    process rather than pickling fixtures across the process boundary.
    """
    import gitgalaxy.tools.supply_chain_security.supply_chain_firewall as fm
    from gitgalaxy.standards.config_resolver import ResolvedConfig, resolve_config

    config = ResolvedConfig(_values=resolve_config().to_dict())
    mock_ram_graph = [
        {"path": "/opt/app/src/main.py", "raw_imports": ["lodash"], "equations": {}, "coding_loc": 10},
    ]
    result = fm.run_firewall_audit(mock_ram_graph, alias_map={}, config=config)
    result_queue.put(result["imports_unknown"])


def test_absolute_path_does_not_infinite_loop_in_alias_resolution():
    """
    Regression test for #710: run_firewall_audit's contextual alias
    resolution traverses upward via Path(rel_path_str).parent looking for
    the nearest authoritative manifest, terminating when current_dir == ".".
    That check only catches a strictly RELATIVE path. If rel_path_str is
    instead absolute (e.g. "/opt/app/src/main.py"), current_dir climbs to
    the filesystem root ("/"), and Python's pathlib defines
    Path("/").parent == Path("/") -- it never becomes ".", so the old code
    looped forever, permanently stalling the firewall in a real CPU
    deadlock on any absolute-path input.

    Run in an isolated, timeout-killed subprocess (mirroring this
    codebase's own assert_redos_immune pattern for "prove this doesn't
    hang" tests) so a regression fails cleanly with a clear timeout error
    instead of hanging the whole test suite indefinitely.
    """
    ctx = multiprocessing.get_context("spawn")
    result_queue = ctx.Queue()
    p = ctx.Process(target=_run_firewall_audit_with_absolute_path, args=(result_queue,))
    p.start()
    p.join(timeout=10)

    if p.is_alive():
        p.terminate()
        p.join()
        raise AssertionError(
            "run_firewall_audit hung on an absolute file path -- the alias-resolution "
            "traversal never reached its root-barrier termination condition"
        )

    assert p.exitcode == 0, f"subprocess crashed with exit code {p.exitcode}"
    assert not result_queue.empty(), "subprocess exited without reporting a result"
    assert result_queue.get() == 1, "lodash should have resolved as an unknown (unmapped) import, not crashed"


# ==============================================================================
# TEST 10: THE ALLOWLIST LOOPHOLE GUARD (UNHAPPY PATH)
# ==============================================================================
def test_firewall_allowlist_loophole_guard():
    """
    Proves that a file residing in an ALLOWLIST_PATH can bypass strict mode
    for unknown imports, but is STILL blocked if it imports a known BLACKLISTED package.
    """
    config = _make_config(
        ALLOWLIST_PATHS=["experiments/"],
        BLACKLISTED_IMPORTS=["known-malware"],
        STRICT_IMPORT_MODE=True,
    )

    mock_ram_graph = [
        {
            "path": "experiments/test_script.js",
            "raw_imports": ["unknown-package", "known-malware"],
            "equations": {},
            "coding_loc": 10,
        }
    ]

    result = firewall_module.run_firewall_audit(mock_ram_graph, config=config)
    assert result["imports_unknown"] == 1
    assert result["imports_blacklisted"] == 1
    assert result["threats_found"] == 1, "Blacklisted import bypassed the firewall via the Allowlist Loophole!"


# ==============================================================================
# TEST 12: ISSUE #157 - THE TUPLE CRASH
# ==============================================================================
def test_tuple_import_handling(tmp_path):
    """Proves the firewall safely unpacks Phase 2 entity tuples from the imports array."""
    mock_ram_graph = {
        "6. Parsed Files (Scanned Artifacts)": {
            "root": {
                "Files": {
                    "app.py": {
                        "raw_imports": [("express", "Router"), "normal-string"],
                        "equations": {},
                        "coding_loc": 100,
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
def test_directory_execution_and_globbing(mock_subprocess_run, tmp_path):
    """Proves passing a directory triggers the orchestrator and globs correctly."""
    target_dir = tmp_path / "mock_repo"
    target_dir.mkdir()

    def mock_run_side_effect(*args, **kwargs):
        # Correctly extract the target output path from the subprocess call arguments
        call_args = args[0]
        out_target = Path(call_args[call_args.index("--output") + 1])
        audit_file = out_target.parent / "firewall_temp_audit.json"

        mock_audit_content = {
            "6. Parsed Files (Scanned Artifacts)": {
                "root": {"Files": {"app.js": {"raw_imports": [], "equations": {}, "coding_loc": 10}}}
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
def test_directory_group_schema_parsing(tmp_path, capsys):
    """Proves the firewall iterates nested directory groups to extract files."""
    mock_ram_graph = {
        "6. Parsed Files (Scanned Artifacts)": {
            "src/backend": {"Files": {"server.py": {"raw_imports": [], "equations": {}, "coding_loc": 10}}},
            "src/frontend": {"Files": {"ui.jsx": {"raw_imports": [], "equations": {}, "coding_loc": 10}}},
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
# TEST 15: BUILD-TIME MULTIPLIER ON A SMALL BUILD SCRIPT (END-TO-END)
# ==============================================================================
def test_density_dilution_fix_for_build_scripts(tmp_path):
    """
    Proves a small build-time script still blocks via main()'s full JSON-loading
    path, not just via run_firewall_audit() directly (TEST 6 covers that unit).

    Historically this guarded against LOC-padding diluting a small file's raw
    hit density. LOC-based dilution is now internal to SignalProcessor's own
    sigmoid scoring (out of the firewall's scope) -- the firewall-level concern
    that remains is that build_time_multiplier still amplifies a below-threshold
    score (secrets_risk=7.0, below 50.0) past the block threshold (7.0 * 10.0 =
    70.0) for a recognized build-time filename, even at tiny file sizes.
    """
    mock_ram_graph = {
        "6. Parsed Files (Scanned Artifacts)": {
            "root": {
                "Files": {
                    "postinstall.js": {
                        "raw_imports": [],
                        "risk_vector": _risk_vector(secrets_risk=7.0),
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
# TEST 17: NETWORK-CENTRALITY WEIGHTING IS OFF BY DEFAULT
# ==============================================================================
def test_network_weighting_disabled_by_default():
    """
    Proves FIREWALL_NETWORK_WEIGHTING defaults to False, so a file with an
    enormous blast radius but a below-threshold raw score does NOT block.
    This is the regression guard for the opt-in rollout decision: existing
    pipelines must see unchanged behavior until they explicitly flip the flag.
    """
    assert resolve_config().FIREWALL_NETWORK_WEIGHTING is False, (
        "FIREWALL_NETWORK_WEIGHTING must default to False -- this feature was "
        "previously inert in production and ships opt-in, not silently live."
    )

    mock_ram_graph = [
        {
            "path": "hub.py",
            "raw_imports": [],
            # 40.0 alone is well under the 50.0 block threshold.
            "risk_vector": _risk_vector(secrets_risk=40.0),
            "telemetry": {"network_metrics": {"normalized_blast_radius": 9.0, "betweenness_score": 0.5}},
            "coding_loc": 50,
        }
    ]

    result = firewall_module.run_firewall_audit(mock_ram_graph)
    assert result["threats_found"] == 0, "Network weighting fired despite being disabled by default."


# ==============================================================================
# TEST 18: NETWORK-CENTRALITY WEIGHTING AMPLIFIES HUB FILES (OPT-IN)
# ==============================================================================
def test_network_weighting_amplifies_high_centrality_hub():
    """
    With FIREWALL_NETWORK_WEIGHTING enabled, a highly central "hub" file
    (normalized_blast_radius=3.0 > 1.0) gets its risk score amplified enough
    to cross the block threshold, while a peripheral file with the identical
    raw score (normalized_blast_radius=0.5 <= 1.0) does not.

    secrets_risk=40.0 alone stays under 50.0. The hub's multiplier is
    1.0 + (3.0 * 0.5) = 2.5, so 40.0 * 2.5 = 100.0 (capped) clears it. This is
    the "only-amplify" design: a low-centrality file is never given a
    discount, it just isn't boosted.
    """
    config = _make_config(FIREWALL_NETWORK_WEIGHTING=True)

    mock_ram_graph = [
        {
            "path": "hub.py",
            "raw_imports": [],
            "risk_vector": _risk_vector(secrets_risk=40.0),
            "telemetry": {"network_metrics": {"normalized_blast_radius": 3.0, "betweenness_score": 0.0}},
            "coding_loc": 50,
        },
        {
            "path": "leaf.py",
            "raw_imports": [],
            "risk_vector": _risk_vector(secrets_risk=40.0),
            "telemetry": {"network_metrics": {"normalized_blast_radius": 0.5, "betweenness_score": 0.0}},
            "coding_loc": 50,
        },
    ]

    result = firewall_module.run_firewall_audit(mock_ram_graph, config=config)
    assert result["threats_found"] == 1, "Hub-file amplification failed to isolate the high-centrality file."


# ==============================================================================
# TEST 19: NETWORK-CENTRALITY WEIGHTING - BETWEENNESS BONUS (OPT-IN)
# ==============================================================================
def test_network_weighting_betweenness_bonus():
    """
    With FIREWALL_NETWORK_WEIGHTING enabled, a file that sits on many shortest
    paths between other files (betweenness_score=0.1 > 0.05) gets a flat +0.5
    multiplier bonus even when its blast radius alone (0.5 <= 1.0) would not
    have amplified it.

    secrets_risk=40.0 alone stays under 50.0. Multiplier here is 1.0 + 0.5 = 1.5,
    so 40.0 * 1.5 = 60.0 clears the threshold. The identical file without the
    high betweenness score stays unblocked.
    """
    config = _make_config(FIREWALL_NETWORK_WEIGHTING=True)

    mock_ram_graph = [
        {
            "path": "bridge.py",
            "raw_imports": [],
            "risk_vector": _risk_vector(secrets_risk=40.0),
            "telemetry": {"network_metrics": {"normalized_blast_radius": 0.5, "betweenness_score": 0.1}},
            "coding_loc": 50,
        },
        {
            "path": "isolated.py",
            "raw_imports": [],
            "risk_vector": _risk_vector(secrets_risk=40.0),
            "telemetry": {"network_metrics": {"normalized_blast_radius": 0.5, "betweenness_score": 0.0}},
            "coding_loc": 50,
        },
    ]

    result = firewall_module.run_firewall_audit(mock_ram_graph, config=config)
    assert result["threats_found"] == 1, "Betweenness bonus failed to isolate the high-betweenness bridge file."


# ==============================================================================
# TEST 20: #335 -- .galaxyscope.yaml ACTUALLY REACHES STANDALONE MAIN()
# ==============================================================================
def test_yaml_config_flag_actually_changes_standalone_firewall_behavior(tmp_path):
    """
    Before #335, supply_chain_firewall.py imported BLACKLISTED_IMPORTS as a
    module-level constant at load time -- no YAML file, no --config flag,
    nothing could ever change what it saw, in standalone CLI mode or
    otherwise. This proves the gap is actually closed: the IDENTICAL RAM
    graph, run through the IDENTICAL standalone `main()` CLI entrypoint,
    produces a clean pass with no --config and a hard block once a
    .galaxyscope.yaml blacklists the offending package.
    """
    mock_ram_graph = {
        "6. Parsed Files (Scanned Artifacts)": {
            "root": {
                "Files": {
                    "app.js": {
                        "raw_imports": ["totally-innocuous-package"],
                        "equations": {},
                        "coding_loc": 10,
                    }
                }
            }
        }
    }
    graph_file = tmp_path / "results.json"
    graph_file.write_text(json.dumps(mock_ram_graph), encoding="utf-8")

    # BEFORE: no --config at all -- unknown package, audit mode, clean pass.
    with patch.object(sys, "argv", ["supply_chain_firewall.py", str(graph_file)]):
        try:
            firewall_module.main()
        except SystemExit:
            pytest.fail("Firewall blocked an unlisted package with no config applied.")

    # AFTER: identical graph, identical CLI entrypoint, but a .galaxyscope.yaml
    # now blacklists the exact package -- must hard-block via SystemExit(1).
    config_path = _write_config_yaml(tmp_path, BLACKLISTED_IMPORTS=["totally-innocuous-package"])
    with patch.object(sys, "argv", ["supply_chain_firewall.py", str(graph_file), "--config", config_path]):
        with pytest.raises(SystemExit) as exc:
            firewall_module.main()
        assert exc.value.code == 1, (
            "YAML BLACKLISTED_IMPORTS override never reached standalone "
            "supply_chain_firewall.py main() -- the #332/#335 reachability "
            "gap is still open."
        )
