import pytest
from unittest.mock import patch
import copy

# Adjust this import to match your project structure
from gitgalaxy.core.network_risk_sensor import NetworkRiskSensor, HAS_NETWORKX

# ==============================================================================
# MOCK STELLAR TOPOLOGY
# ==============================================================================
# We create a controlled, mini-universe of 6 files to perfectly test every
# graph edge-case (Islands, Cycles, Producers, Consumers, and Bottlenecks).

MOCK_PARSED_FILES = [
    {
        "path": "/src/core/foundation.py",
        "raw_imports": [],  # Imports nothing. Pure Producer.
        "risk_vector": [10.0] * 18,
        "functions": [{"big_o_depth": 1, "is_recursive": False}],
    },
    {
        "path": "/src/utils/transceiver.py",
        "raw_imports": ["/src/core/foundation.py", "/src/math/heavy_calc.py"],
        "risk_vector": [20.0] * 18,
    },
    {
        "path": "/src/main/orchestrator.py",
        "raw_imports": [
            "/src/utils/transceiver.py",
            "/src/core/foundation.py",
        ],  # Pure Consumer.
        "risk_vector": [5.0] * 18,
    },
    {
        "path": "/src/cycle_a.py",
        "raw_imports": ["/src/cycle_b.py"],  # Cyclic Loop Part 1
    },
    {
        "path": "/src/cycle_b.py",
        "raw_imports": ["/src/cycle_a.py"],  # Cyclic Loop Part 2
    },
    {
        "path": "/src/island.py",
        "raw_imports": [],  # Zero edges in or out.
    },
    {
        "path": "/src/math/heavy_calc.py",
        "raw_imports": [],
        "risk_vector": [50.0] * 18,
        # Extreme algorithmic complexity (Recursive + Big O 4)
        "functions": [{"big_o_depth": 4, "is_recursive": True}],
    },
]


@pytest.fixture
def sensor():
    """Initializes the Network Risk Sensor."""
    return NetworkRiskSensor()


@pytest.fixture
def parsed_files_universe():
    """Returns a fresh copy of the mock universe for each test."""
    return copy.deepcopy(MOCK_PARSED_FILES)


# ==============================================================================
# TEST 1: ISOLATED ISLAND RESILIENCE
# ==============================================================================
@pytest.mark.skipif(not HAS_NETWORKX, reason="Requires NetworkX")
def test_network_isolated_island(sensor, parsed_files_universe):
    """Proves that a node with 0 edges does not trigger divide-by-zero math."""
    mapped_files, metrics = sensor.build_dependency_graph(parsed_files_universe)

    island = next(f for f in mapped_files if f["path"] == "/src/island.py")
    telemetry = island["telemetry"]["network_metrics"]

    assert telemetry["in_degree"] == 0
    assert telemetry["out_degree"] == 0
    assert telemetry["ecosystem_role"] == "Isolated/Orphan", "Failed to identify the isolated island!"
    assert telemetry["producer_ratio"] == 0.0, "Divide by zero occurred on producer_ratio!"


# ==============================================================================
# TEST 2: CYCLIC DEPENDENCY RESILIENCE
# ==============================================================================
@pytest.mark.skipif(not HAS_NETWORKX, reason="Requires NetworkX")
def test_network_cyclic_loop_resilience(sensor, parsed_files_universe):
    """Proves that A -> B -> A loops do not crash the PageRank / Graph traversal."""
    # If the algorithm gets stuck in infinite recursion, this test will timeout/crash.
    mapped_files, metrics = sensor.build_dependency_graph(parsed_files_universe)

    cycle_a = next(f for f in mapped_files if f["path"] == "/src/cycle_a.py")
    telemetry = cycle_a["telemetry"]["network_metrics"]

    # Prove the cycle was mathematically registered
    assert telemetry["in_degree"] == 1
    assert telemetry["out_degree"] == 1
    assert metrics["cyclic_density"] > 0.0, "Failed to register macro-level cyclic density!"


# ==============================================================================
# TEST 3: ECOSYSTEM ROLES
# ==============================================================================
@pytest.mark.skipif(not HAS_NETWORKX, reason="Requires NetworkX")
def test_network_ecosystem_roles(sensor, parsed_files_universe):
    """Proves the engine accurately classifies Producers, Consumers, and Transceivers."""
    mapped_files, metrics = sensor.build_dependency_graph(parsed_files_universe)

    foundation = next(f for f in mapped_files if f["path"] == "/src/core/foundation.py")
    assert foundation["telemetry"]["network_metrics"]["ecosystem_role"] == "Pure Producer (Foundation)"

    orchestrator = next(f for f in mapped_files if f["path"] == "/src/main/orchestrator.py")
    assert orchestrator["telemetry"]["network_metrics"]["ecosystem_role"] == "Pure Consumer (Orchestrator)"

    transceiver = next(f for f in mapped_files if f["path"] == "/src/utils/transceiver.py")
    assert transceiver["telemetry"]["network_metrics"]["ecosystem_role"] == "Transceiver (Middle-Tier)"


# ==============================================================================
# TEST 4: THE ALGORITHMIC BOTTLENECK SENSOR
# ==============================================================================
@pytest.mark.skipif(not HAS_NETWORKX, reason="Requires NetworkX")
def test_network_algorithmic_bottleneck(sensor, parsed_files_universe):
    """
    Proves that a file requires BOTH high network gravity (PageRank > 1.0)
    AND extreme internal logic (Big-O >= 3) to be flagged as a systemic bottleneck.
    """
    # Artificially pump up the gravity of heavy_calc by making Orchestrator and Cycle A import it too
    parsed_files_universe[2]["raw_imports"].append("/src/math/heavy_calc.py")
    parsed_files_universe[3]["raw_imports"].append("/src/math/heavy_calc.py")

    mapped_files, metrics = sensor.build_dependency_graph(parsed_files_universe)

    # 1. Foundation has high gravity (PageRank), but simple internal logic (Big O 1). Should be False.
    foundation = next(f for f in mapped_files if f["path"] == "/src/core/foundation.py")
    assert foundation["telemetry"]["network_metrics"]["normalized_blast_radius"] > 1.0
    assert foundation["telemetry"]["network_metrics"]["is_algorithmic_bottleneck"] is False

    # 2. Heavy Calc has high gravity AND extreme logic (Big O 4 + Recursive). Should be True!
    heavy_calc = next(f for f in mapped_files if f["path"] == "/src/math/heavy_calc.py")
    assert heavy_calc["telemetry"]["network_metrics"]["normalized_blast_radius"] > 1.0
    assert heavy_calc["telemetry"]["network_metrics"]["is_algorithmic_bottleneck"] is True

    # 3. #372: max_big_o itself must be copied onto the file dict, not just used
    # internally to compute is_algorithmic_bottleneck -- dev_agent_firewall.py
    # reads file_data.get("max_big_o") directly, a different object than this
    # function's own G.nodes[path].
    assert foundation["max_big_o"] == 1
    assert heavy_calc["max_big_o"] == 4


# ==============================================================================
# TEST 5: ZERO-DEPENDENCY FALLBACK
# ==============================================================================
def test_network_fallback_mode(sensor, parsed_files_universe):
    """Proves the fallback mode safely maps roles without NetworkX installed."""
    with patch("gitgalaxy.core.network_risk_sensor.HAS_NETWORKX", False):
        mapped_files, metrics = sensor.build_dependency_graph(parsed_files_universe)

        # It should still calculate basic in/out degrees and roles using pure Python dicts
        foundation = next(f for f in mapped_files if f["path"] == "/src/core/foundation.py")
        assert foundation["telemetry"]["network_metrics"]["ecosystem_role"] == "Pure Producer (Foundation)"
        assert foundation["telemetry"]["network_metrics"]["pagerank_score"] == 0.0  # Math is disabled

        # #372: max_big_o computation is pure Python (off "functions"), so it
        # must still work in Zero-Dependency Mode, not just the networkx path.
        heavy_calc = next(f for f in mapped_files if f["path"] == "/src/math/heavy_calc.py")
        assert foundation["max_big_o"] == 1
        assert heavy_calc["max_big_o"] == 4


# ==============================================================================
# MOCK: DUPLICATE FILENAME TOPOLOGY (Regression tests for #261)
# ==============================================================================
# Two files share the stem "utils" in different directories — the exact
# "last file wins" scenario from #261. Resolution must never silently
# misattribute an edge to the wrong file just because a bare import token
# happens to collide with another file's name.

DUPLICATE_FILENAME_FILES = [
    {
        "path": "/src/service_a/utils.py",
        "raw_imports": [],
    },
    {
        "path": "/src/service_b/utils.py",
        "raw_imports": [],
    },
    {
        "path": "/src/service_a/handler.py",
        # Bare stem import — genuinely ambiguous between the two "utils.py"
        # files. Must NOT silently resolve to either one.
        "raw_imports": ["utils"],
    },
    {
        "path": "/src/service_b/router.py",
        # Path-qualified import — enough context to disambiguate to
        # service_b/utils.py specifically, even though "utils" alone is
        # ambiguous.
        "raw_imports": ["service_b/utils"],
    },
]


@pytest.fixture
def duplicate_filename_universe():
    """Returns a fresh copy of the duplicate-filename mock universe for each test."""
    return copy.deepcopy(DUPLICATE_FILENAME_FILES)


# Isolated universe for the pure-ambiguity test — deliberately excludes
# router.py's path-qualified import, which legitimately resolves and would
# otherwise contaminate service_b/utils.py's in_degree count.
AMBIGUOUS_ONLY_FILES = [
    {
        "path": "/src/service_a/utils.py",
        "raw_imports": [],
    },
    {
        "path": "/src/service_b/utils.py",
        "raw_imports": [],
    },
    {
        "path": "/src/service_a/handler.py",
        "raw_imports": ["utils"],  # bare, genuinely ambiguous stem
    },
]


@pytest.fixture
def ambiguous_only_universe():
    """Returns a fresh copy of the pure-ambiguity mock universe for each test."""
    return copy.deepcopy(AMBIGUOUS_ONLY_FILES)


# ==============================================================================
# TEST 6: DUPLICATE FILENAME — AMBIGUOUS BARE IMPORT IS SKIPPED, NOT GUESSED (#261)
# ==============================================================================
@pytest.mark.skipif(not HAS_NETWORKX, reason="Requires NetworkX")
def test_network_duplicate_filename_ambiguous_import_skipped(sensor, ambiguous_only_universe):
    """
    Regression test for #261: when a bare import token ("utils") matches
    multiple files sharing that stem across directories, the resolver must
    refuse to guess — not silently wire the edge to whichever file happened
    to be processed last.
    """
    mapped_files, metrics = sensor.build_dependency_graph(ambiguous_only_universe)

    service_a_utils = next(f for f in mapped_files if f["path"] == "/src/service_a/utils.py")
    service_b_utils = next(f for f in mapped_files if f["path"] == "/src/service_b/utils.py")

    assert service_a_utils["telemetry"]["network_metrics"]["in_degree"] == 0, (
        "Ambiguous 'utils' import was silently misattributed to service_a/utils.py!"
    )
    assert service_b_utils["telemetry"]["network_metrics"]["in_degree"] == 0, (
        "Ambiguous 'utils' import was silently misattributed to service_b/utils.py!"
    )


# ==============================================================================
# TEST 7: DUPLICATE FILENAME — PATH-QUALIFIED IMPORT DISAMBIGUATES CORRECTLY (#261)
# ==============================================================================
@pytest.mark.skipif(not HAS_NETWORKX, reason="Requires NetworkX")
def test_network_duplicate_filename_path_qualified_import_resolves(sensor, duplicate_filename_universe):
    """
    Regression test for #261: when the import token carries enough path
    context ("service_b/utils"), the resolver must wire the edge to the
    correct file, not the other file sharing the same bare stem.
    """
    mapped_files, metrics = sensor.build_dependency_graph(duplicate_filename_universe)

    service_a_utils = next(f for f in mapped_files if f["path"] == "/src/service_a/utils.py")
    service_b_utils = next(f for f in mapped_files if f["path"] == "/src/service_b/utils.py")

    assert service_b_utils["telemetry"]["network_metrics"]["in_degree"] == 1, (
        "Path-qualified 'service_b/utils' import failed to resolve to the correct file!"
    )
    assert service_a_utils["telemetry"]["network_metrics"]["in_degree"] == 0, (
        "Path-qualified 'service_b/utils' import was incorrectly wired to service_a/utils.py!"
    )


# ==============================================================================
# TEST 8: DUPLICATE FILENAME — FALLBACK (ZERO-DEPENDENCY) MODE (#261)
# ==============================================================================
def test_network_duplicate_filename_fallback_mode(sensor, duplicate_filename_universe):
    """
    Regression test for #261 in the pure-Python fallback path
    (_fallback_build_graph): the same ambiguity-safe resolution must apply
    even when NetworkX isn't installed.
    """
    with patch("gitgalaxy.core.network_risk_sensor.HAS_NETWORKX", False):
        mapped_files, metrics = sensor.build_dependency_graph(duplicate_filename_universe)

        service_a_utils = next(f for f in mapped_files if f["path"] == "/src/service_a/utils.py")
        service_b_utils = next(f for f in mapped_files if f["path"] == "/src/service_b/utils.py")

        assert service_a_utils["telemetry"]["network_metrics"]["in_degree"] == 0
        assert service_b_utils["telemetry"]["network_metrics"]["in_degree"] == 1


# ==============================================================================
# TEST 9: DUPLICATE FILENAME — TEST COVERAGE MAPPING (#261)
# ==============================================================================
def test_coverage_mapping_duplicate_filename_ambiguous(sensor):
    """
    Regression test for #261 in extract_test_coverage_mapping: an ambiguous
    bare import from a test file must not misattribute coverage to the
    wrong production file sharing the same stem.
    """
    files = [
        {"path": "/src/service_a/utils.py", "raw_imports": []},
        {"path": "/src/service_b/utils.py", "raw_imports": []},
        {
            "path": "/tests/test_utils.py",
            "raw_imports": ["utils"],  # ambiguous bare stem
            "functions": [
                {
                    "calls_out_to": ["helper_fn"],
                    "impact": 1.0,
                    "hit_vector": {"test": 1, "test_skip": 0, "decorators": 0},
                }
            ],
        },
    ]

    coverage_map = sensor.extract_test_coverage_mapping(files)

    assert "/src/service_a/utils.py" not in coverage_map, (
        "Ambiguous 'utils' import misattributed test coverage to service_a/utils.py!"
    )
    assert "/src/service_b/utils.py" not in coverage_map, (
        "Ambiguous 'utils' import misattributed test coverage to service_b/utils.py!"
    )


# ==============================================================================
# TEST 10: TEST COVERAGE MAPPING — HAPPY PATH (unambiguous resolution)
# ==============================================================================
def test_coverage_mapping_happy_path(sensor):
    """
    Proves extract_test_coverage_mapping actually populates the coverage map
    end-to-end when a test file has an unambiguous import and calls_out_to
    data -- the success path was previously untested (only the ambiguous
    rejection path had coverage), even though it's the whole point of the
    function: mapping test->production calls for the verification-risk
    dampener in signal_processor.py.
    """
    files = [
        {"path": "/src/payments/charge.py", "raw_imports": []},
        {
            "path": "/tests/test_charge.py",
            "raw_imports": ["/src/payments/charge.py"],
            "functions": [
                {
                    "calls_out_to": ["run_charge", "refund_charge"],
                    "impact": 12.5,
                    "hit_vector": {"test": 3, "test_skip": 0, "decorators": 1},
                },
                {
                    # A second test function targeting the same production file
                    # and one overlapping function name -- proves multiple test
                    # payloads accumulate in a list rather than overwriting.
                    "calls_out_to": ["run_charge"],
                    "impact": 4.0,
                    "hit_vector": {"test": 1, "test_skip": 1, "decorators": 0},
                },
            ],
        },
    ]

    coverage_map = sensor.extract_test_coverage_mapping(files)

    assert "/src/payments/charge.py" in coverage_map, "Unambiguous test coverage mapping was dropped entirely!"
    target = coverage_map["/src/payments/charge.py"]

    assert "run_charge" in target and "refund_charge" in target
    assert len(target["run_charge"]) == 2, "Both test functions targeting run_charge should accumulate, not overwrite."
    assert len(target["refund_charge"]) == 1

    first_payload = target["run_charge"][0]
    assert first_payload["impact"] == 12.5
    assert first_payload["target_count"] == 2
    assert first_payload["test_hits"] == 3
    assert first_payload["decorators"] == 1

    second_payload = target["run_charge"][1]
    assert second_payload["test_skip_hits"] == 1


def test_coverage_mapping_skips_test_functions_with_no_calls(sensor):
    """A test function with an empty calls_out_to shouldn't appear in the map at all."""
    files = [
        {"path": "/src/lib.py", "raw_imports": []},
        {
            "path": "/tests/test_lib.py",
            "raw_imports": ["/src/lib.py"],
            "functions": [{"calls_out_to": [], "impact": 1.0, "hit_vector": {}}],
        },
    ]

    coverage_map = sensor.extract_test_coverage_mapping(files)
    assert coverage_map == {}, "A test function with zero outbound calls should contribute nothing to the map."


# ==============================================================================
# TEST 11: DUPLICATE-EDGE WEIGHT ACCUMULATION
# ==============================================================================
@pytest.mark.skipif(not HAS_NETWORKX, reason="Requires NetworkX")
def test_network_duplicate_edge_weight_accumulates(sensor):
    """
    Two separate imports from the same file to the same target must
    accumulate into a single edge's weight, not silently overwrite it or
    create a second parallel edge (DiGraph can't hold parallel edges anyway,
    but the accumulation logic itself -- G[u][v]["weight"] += weight --
    had no test exercising the "edge already exists" branch at all).
    """
    files = [
        {"path": "/src/shared/helpers.py", "raw_imports": []},
        {
            "path": "/src/app.py",
            # Two distinct entity-imports resolving to the same target file:
            # first import creates the edge (weight 1.5, has an entity), the
            # second must hit the "G.has_edge" branch and add its own weight.
            "raw_imports": [
                ("/src/shared/helpers.py", "format_date"),
                ("/src/shared/helpers.py", "parse_config"),
            ],
        },
    ]

    mapped_files, _ = sensor.build_dependency_graph(files)
    helpers = next(f for f in mapped_files if f["path"] == "/src/shared/helpers.py")

    # Both entity imports carry weight 1.5 each -- accumulated weight should
    # be reflected in in_degree still being 1 (one edge, DiGraph semantics)
    # while the underlying edge weight (not directly exposed in telemetry,
    # but exercised via pagerank/betweenness using it) doesn't crash and the
    # edge count stays correct.
    assert helpers["telemetry"]["network_metrics"]["in_degree"] == 1, (
        "Two imports to the same target should still be exactly one graph edge."
    )


# ==============================================================================
# TEST 12: NETWORK MATH RESILIENCE — CENTRALITY COMPUTATION FAILURE
# ==============================================================================
@pytest.mark.skipif(not HAS_NETWORKX, reason="Requires NetworkX")
def test_network_math_failure_degrades_to_zero(sensor, parsed_files_universe):
    """
    Stress test: if NetworkX's centrality math itself throws (e.g. a future
    NetworkX version changes behavior, or an unexpected graph shape), the
    sensor must degrade every node to a 0.0 score rather than crashing the
    whole pipeline. This exercises the outer `except Exception` fallback in
    build_dependency_graph, never previously triggered by any test.
    """
    with patch("networkx.pagerank", side_effect=RuntimeError("simulated convergence failure")):
        mapped_files, _ = sensor.build_dependency_graph(parsed_files_universe)

    foundation = next(f for f in mapped_files if f["path"] == "/src/core/foundation.py")
    metrics = foundation["telemetry"]["network_metrics"]
    assert metrics["pagerank_score"] == 0.0
    assert metrics["betweenness_score"] == 0.0
    assert metrics["closeness_score"] == 0.0


# ==============================================================================
# TEST 13: MACRO NETWORK MATH RESILIENCE — INDIVIDUAL METRIC FAILURES
# ==============================================================================
@pytest.mark.skipif(not HAS_NETWORKX, reason="Requires NetworkX")
def test_macro_metrics_individual_failures_stay_isolated(sensor, parsed_files_universe):
    """
    Stress test: each macro-ecosystem metric (modularity, assortativity,
    cyclic density, avg path length, articulation points) is computed in
    its own try/except so one metric's failure doesn't take down the
    others. Previously none of these five except-blocks had a single test
    forcing the failure path -- they were trusted by inspection only.
    """
    with (
        patch("networkx.degree_assortativity_coefficient", side_effect=RuntimeError("boom")),
        patch("networkx.average_shortest_path_length", side_effect=RuntimeError("boom")),
        patch("networkx.articulation_points", side_effect=RuntimeError("boom")),
    ):
        _, macro_metrics = sensor.build_dependency_graph(parsed_files_universe)

    assert macro_metrics["assortativity"] is None, (
        "A failed assortativity computation must stay None, not 0.0 or crash."
    )
    assert macro_metrics["avg_path_length"] is None
    assert macro_metrics["articulation_points"] is None
    # Modularity and cyclic_density weren't patched to fail -- they should
    # still have computed normally, proving the try/except isolation really
    # is per-metric and not a single all-or-nothing block.
    assert macro_metrics["modularity"] is not None
    assert macro_metrics["cyclic_density"] is not None


def test_cyclic_density_failure_stays_isolated(sensor, parsed_files_universe):
    """Same isolation guarantee, targeting cyclic density specifically."""
    with patch("networkx.strongly_connected_components", side_effect=RuntimeError("boom")):
        _, macro_metrics = sensor.build_dependency_graph(parsed_files_universe)

    assert macro_metrics["cyclic_density"] is None
    assert macro_metrics["modularity"] is not None, (
        "An unrelated metric's failure shouldn't take modularity down with it."
    )


def test_modularity_falls_back_to_greedy_when_louvain_unavailable(sensor, parsed_files_universe):
    """
    Older NetworkX versions don't have louvain_communities. The code catches
    that specific AttributeError and falls back to greedy_modularity_communities
    -- previously untested, so a NetworkX downgrade could have silently broken
    modularity for anyone on an older pin without a single test noticing.
    """
    with patch(
        "networkx.algorithms.community.louvain_communities",
        side_effect=AttributeError("simulated: old networkx has no louvain_communities"),
    ):
        _, macro_metrics = sensor.build_dependency_graph(parsed_files_universe)

    assert macro_metrics["modularity"] is not None, (
        "Louvain AttributeError should fall back to greedy_modularity_communities, not leave modularity unset."
    )


def test_macro_math_outer_failure_returns_all_none(sensor, parsed_files_universe):
    """
    Stress test for the outermost `except Exception` around the whole macro
    block (e.g. G.to_undirected() itself failing) -- must degrade every
    macro metric to None rather than crashing build_dependency_graph
    entirely and losing the per-file network metrics already computed.
    """
    with patch("networkx.DiGraph.to_undirected", side_effect=RuntimeError("boom")):
        mapped_files, macro_metrics = sensor.build_dependency_graph(parsed_files_universe)

    assert all(v is None for v in macro_metrics.values()), "Outer macro-math failure should leave every metric None."
    # Per-file network metrics (computed earlier in the function, before the
    # macro block) must survive even though the macro block blew up.
    foundation = next(f for f in mapped_files if f["path"] == "/src/core/foundation.py")
    assert "network_metrics" in foundation["telemetry"]


# ==============================================================================
# TEST 14: RESOLUTION MAP / TARGET RESOLUTION EDGE CASES
# ==============================================================================
def test_build_resolution_map_skips_files_with_no_path(sensor):
    """A file dict missing its 'path' key must be skipped, not crash Path("")."""
    files = [{"raw_imports": []}, {"path": "", "raw_imports": []}, {"path": "/src/real.py", "raw_imports": []}]
    resolution_map = sensor._build_resolution_map(files)
    assert list(resolution_map.keys()) == ["/src/real.py", "real.py", "real"]


def test_resolve_target_returns_none_for_external_package_import(sensor):
    """
    An import of a genuinely external package (e.g. `import numpy`) has no
    corresponding file in the repo at all -- _resolve_target must return
    None cleanly rather than raising, since resolution_map.get() will find
    nothing at any stage.
    """
    resolution_map = sensor._build_resolution_map([{"path": "/src/real.py", "raw_imports": []}])
    assert sensor._resolve_target("numpy", resolution_map, "/src/real.py") is None
    assert sensor._resolve_target("some.deeply.nested.external.pkg", resolution_map, "/src/real.py") is None
