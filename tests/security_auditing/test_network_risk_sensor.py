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
    assert telemetry["ecosystem_role"] == "Isolated/Orphan", (
        "Failed to identify the isolated island!"
    )
    assert telemetry["producer_ratio"] == 0.0, (
        "Divide by zero occurred on producer_ratio!"
    )


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
    assert metrics["cyclic_density"] > 0.0, (
        "Failed to register macro-level cyclic density!"
    )


# ==============================================================================
# TEST 3: ECOSYSTEM ROLES
# ==============================================================================
@pytest.mark.skipif(not HAS_NETWORKX, reason="Requires NetworkX")
def test_network_ecosystem_roles(sensor, parsed_files_universe):
    """Proves the engine accurately classifies Producers, Consumers, and Transceivers."""
    mapped_files, metrics = sensor.build_dependency_graph(parsed_files_universe)

    foundation = next(f for f in mapped_files if f["path"] == "/src/core/foundation.py")
    assert (
        foundation["telemetry"]["network_metrics"]["ecosystem_role"]
        == "Pure Producer (Foundation)"
    )

    orchestrator = next(
        f for f in mapped_files if f["path"] == "/src/main/orchestrator.py"
    )
    assert (
        orchestrator["telemetry"]["network_metrics"]["ecosystem_role"]
        == "Pure Consumer (Orchestrator)"
    )

    transceiver = next(
        f for f in mapped_files if f["path"] == "/src/utils/transceiver.py"
    )
    assert (
        transceiver["telemetry"]["network_metrics"]["ecosystem_role"]
        == "Transceiver (Middle-Tier)"
    )


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
    assert (
        foundation["telemetry"]["network_metrics"]["is_algorithmic_bottleneck"] is False
    )

    # 2. Heavy Calc has high gravity AND extreme logic (Big O 4 + Recursive). Should be True!
    heavy_calc = next(f for f in mapped_files if f["path"] == "/src/math/heavy_calc.py")
    assert heavy_calc["telemetry"]["network_metrics"]["normalized_blast_radius"] > 1.0
    assert (
        heavy_calc["telemetry"]["network_metrics"]["is_algorithmic_bottleneck"] is True
    )


# ==============================================================================
# TEST 5: ZERO-DEPENDENCY FALLBACK
# ==============================================================================
def test_network_fallback_mode(sensor, parsed_files_universe):
    """Proves the fallback mode safely maps roles without NetworkX installed."""
    with patch("gitgalaxy.core.network_risk_sensor.HAS_NETWORKX", False):
        mapped_files, metrics = sensor.build_dependency_graph(parsed_files_universe)

        # It should still calculate basic in/out degrees and roles using pure Python dicts
        foundation = next(
            f for f in mapped_files if f["path"] == "/src/core/foundation.py"
        )
        assert (
            foundation["telemetry"]["network_metrics"]["ecosystem_role"]
            == "Pure Producer (Foundation)"
        )
        assert (
            foundation["telemetry"]["network_metrics"]["pagerank_score"] == 0.0
        )  # Math is disabled


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
def test_network_duplicate_filename_ambiguous_import_skipped(
    sensor, ambiguous_only_universe
):
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
def test_network_duplicate_filename_path_qualified_import_resolves(
    sensor, duplicate_filename_universe
):
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

        service_a_utils = next(
            f for f in mapped_files if f["path"] == "/src/service_a/utils.py"
        )
        service_b_utils = next(
            f for f in mapped_files if f["path"] == "/src/service_b/utils.py"
        )

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