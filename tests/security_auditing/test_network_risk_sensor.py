import copy
from unittest.mock import patch

import pytest

# Adjust this import to match your project structure
from gitgalaxy.core.network_risk_sensor import HAS_NETWORKX, NetworkRiskSensor

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


# ==============================================================================
# MOCK: CASE-INSENSITIVE IMPORT RESOLUTION (Regression tests for #2540)
# ==============================================================================
# Fortran, COBOL, and Haskell resolve import/module references
# case-insensitively (or with mandatory casing that need not match the file
# name on disk). With dominant legacy style (`USE A`, `COPY A.`, `import A`)
# an exact-case lookup misses `a.f90`/`a.cpy`/`a.hs` entirely: popularity
# stays 0 and the orphan->api conversion never fires. The resolver must
# case-fold the lookup for these languages ONLY -- case-sensitive languages
# (e.g. python) must never gain cross-case resolution.

CASE_FOLD_FILES = [
    {
        "path": "/src/orbit_math.f90",
        "lang_id": "fortran",
        "raw_imports": [],
    },
    {
        "path": "/src/main.f90",
        "lang_id": "fortran",
        # `USE ORBIT_MATH` -- _dependency_capture yields the module name
        # verbatim, uppercase, while the module lives in lowercase
        # orbit_math.f90.
        "raw_imports": ["ORBIT_MATH"],
    },
    {
        "path": "/hs/parser.hs",
        "lang_id": "haskell",
        "raw_imports": [],
    },
    {
        "path": "/hs/Main.hs",
        "lang_id": "haskell",
        # Haskell module names are necessarily capitalized: `import Parser`.
        "raw_imports": ["Parser"],
    },
    {
        "path": "/cbl/payroll.cpy",
        "lang_id": "cobol",
        "raw_imports": [],
    },
    {
        "path": "/cbl/prog.cbl",
        "lang_id": "cobol",
        # `COPY PAYROLL.` -- _dependency_capture yields "PAYROLL".
        "raw_imports": ["PAYROLL"],
    },
]


@pytest.fixture
def case_fold_universe():
    """Returns a fresh copy of the case-insensitive-language mock universe."""
    return copy.deepcopy(CASE_FOLD_FILES)


# ==============================================================================
# TEST 15: CASE-FOLDED RESOLUTION FOR CASE-INSENSITIVE LANGUAGES (#2540)
# ==============================================================================
@pytest.mark.skipif(not HAS_NETWORKX, reason="Requires NetworkX")
def test_network_fortran_uppercase_use_resolves(sensor, case_fold_universe):
    """
    Regression test for #2540: fortran `USE A` must resolve to a.f90 even
    though the captured token's case doesn't match the file stem -- fortran
    is case-insensitive and uppercase USE is the dominant legacy style.
    """
    mapped_files, _ = sensor.build_dependency_graph(case_fold_universe)

    a_f90 = next(f for f in mapped_files if f["path"] == "/src/orbit_math.f90")
    telemetry = a_f90["telemetry"]["network_metrics"]

    assert telemetry["in_degree"] == 1, "Uppercase `USE A` failed to resolve to a.f90 -- import chain invisible!"
    assert telemetry["ecosystem_role"] != "Isolated/Orphan", (
        "a.f90 is imported by main.f90 and must not be classified an orphan."
    )
    assert a_f90["telemetry"]["popularity"] == 1


@pytest.mark.skipif(not HAS_NETWORKX, reason="Requires NetworkX")
def test_network_haskell_capitalized_import_resolves(sensor, case_fold_universe):
    """
    Regression test for #2540 (issue comment): haskell module names are
    necessarily capitalized (`import A`), so a lowercase a.hs on disk must
    still receive the edge.
    """
    mapped_files, _ = sensor.build_dependency_graph(case_fold_universe)

    a_hs = next(f for f in mapped_files if f["path"] == "/hs/parser.hs")
    assert a_hs["telemetry"]["network_metrics"]["in_degree"] == 1, (
        "`import A` failed to resolve to a.hs -- haskell DAG invisible!"
    )


@pytest.mark.skipif(not HAS_NETWORKX, reason="Requires NetworkX")
def test_network_cobol_copy_statement_resolves(sensor, case_fold_universe):
    """
    Regression test for #2540 (issue comment): cobol `COPY A.` captures "A"
    and must resolve to the lowercase copybook a.cpy.
    """
    mapped_files, _ = sensor.build_dependency_graph(case_fold_universe)

    a_cpy = next(f for f in mapped_files if f["path"] == "/cbl/payroll.cpy")
    assert a_cpy["telemetry"]["network_metrics"]["in_degree"] == 1, (
        "`COPY A.` failed to resolve to a.cpy -- cobol copybook edge lost!"
    )


# ==============================================================================
# TEST 16: CASE-SENSITIVE LANGUAGES MUST NOT CROSS-CASE RESOLVE (#2540)
# ==============================================================================
@pytest.mark.skipif(not HAS_NETWORKX, reason="Requires NetworkX")
def test_network_python_does_not_cross_case_resolve(sensor):
    """
    Guard for #2540's chosen design (per-language flag, not an unconditional
    fold): python is case-sensitive, so `import Foo` must NOT suddenly
    resolve to foo.py just because the fold exists for fortran/cobol/haskell.
    """
    files = [
        {"path": "/src/foo.py", "lang_id": "python", "raw_imports": []},
        {"path": "/src/app.py", "lang_id": "python", "raw_imports": ["Foo"]},
    ]

    mapped_files, _ = sensor.build_dependency_graph(files)

    foo = next(f for f in mapped_files if f["path"] == "/src/foo.py")
    assert foo["telemetry"]["network_metrics"]["in_degree"] == 0, (
        "Case-sensitive python `import Foo` must not cross-case resolve to foo.py!"
    )


@pytest.mark.skipif(not HAS_NETWORKX, reason="Requires NetworkX")
def test_network_unknown_language_stays_case_sensitive(sensor):
    """A file with no lang_id at all (mock/legacy dicts) keeps exact-case resolution."""
    files = [
        {"path": "/src/foo.js", "raw_imports": []},
        {"path": "/src/app.js", "raw_imports": ["FOO"]},
    ]

    mapped_files, _ = sensor.build_dependency_graph(files)

    foo = next(f for f in mapped_files if f["path"] == "/src/foo.js")
    assert foo["telemetry"]["network_metrics"]["in_degree"] == 0


# ==============================================================================
# TEST 17: EXACT-CASE MATCH WINS BEFORE THE FOLD (#2540)
# ==============================================================================
@pytest.mark.skipif(not HAS_NETWORKX, reason="Requires NetworkX")
def test_network_exact_case_match_wins_over_folded(sensor):
    """
    When both A.hs and a.hs exist, `import A` from a folding language must
    take the exact-case match (A.hs) -- the fold is a fallback for when the
    exact lookup misses, never a replacement for it.
    """
    files = [
        {"path": "/hs/A.hs", "lang_id": "haskell", "raw_imports": []},
        {"path": "/hs/a.hs", "lang_id": "haskell", "raw_imports": []},
        {"path": "/hs/Main.hs", "lang_id": "haskell", "raw_imports": ["A"]},
    ]

    mapped_files, _ = sensor.build_dependency_graph(files)

    exact = next(f for f in mapped_files if f["path"] == "/hs/A.hs")
    folded = next(f for f in mapped_files if f["path"] == "/hs/a.hs")
    assert exact["telemetry"]["network_metrics"]["in_degree"] == 1, "Exact-case A.hs must win the lookup."
    assert folded["telemetry"]["network_metrics"]["in_degree"] == 0, (
        "The folded candidate must not steal an edge that resolved exactly."
    )


# ==============================================================================
# TEST 18: CASE-FOLDED RESOLUTION — FALLBACK (ZERO-DEPENDENCY) MODE (#2540)
# ==============================================================================
def test_network_case_fold_fallback_mode(sensor, case_fold_universe):
    """
    Regression test for #2540 in the pure-Python fallback path
    (_fallback_build_graph): the same case-folded resolution must apply
    even when NetworkX isn't installed.
    """
    with patch("gitgalaxy.core.network_risk_sensor.HAS_NETWORKX", False):
        mapped_files, _ = sensor.build_dependency_graph(case_fold_universe)

        a_f90 = next(f for f in mapped_files if f["path"] == "/src/orbit_math.f90")
        assert a_f90["telemetry"]["network_metrics"]["in_degree"] == 1
        a_cpy = next(f for f in mapped_files if f["path"] == "/cbl/payroll.cpy")
        assert a_cpy["telemetry"]["network_metrics"]["in_degree"] == 1


# ==============================================================================
# TEST 19: THE FOLD NEVER INVENTS A CROSS-LANGUAGE EDGE (#2540)
# ==============================================================================
@pytest.mark.skipif(not HAS_NETWORKX, reason="Requires NetworkX")
def test_network_fold_does_not_cross_language_resolve(sensor):
    """
    Found by the crucible corpus during the #2540 re-bless: haskell's
    `import Text.Pandoc.Generic` case-folded onto go's generic.go purely on
    a stem collision. Folding is a property of the importing language's own
    resolution rules, so the folded fallback only sees that language's files
    -- while a same-language fold in the same universe still resolves.
    """
    files = [
        {"path": "/go/generic.go", "lang_id": "go", "raw_imports": []},
        {"path": "/hs/pandoc.hs", "lang_id": "haskell", "raw_imports": ["Text.Pandoc.Generic"]},
        {"path": "/hs/writer.hs", "lang_id": "haskell", "raw_imports": []},
        {"path": "/hs/Main.hs", "lang_id": "haskell", "raw_imports": ["Writer"]},
    ]

    mapped_files, _ = sensor.build_dependency_graph(files)

    generic_go = next(f for f in mapped_files if f["path"] == "/go/generic.go")
    assert generic_go["telemetry"]["network_metrics"]["in_degree"] == 0, (
        "haskell import must not fold onto a go file on a stem collision!"
    )
    writer_hs = next(f for f in mapped_files if f["path"] == "/hs/writer.hs")
    assert writer_hs["telemetry"]["network_metrics"]["in_degree"] == 1, (
        "Same-language folded resolution must still work alongside the guard."
    )


# ==============================================================================
# TEST 20: RELATIVE IMPORTS THAT CARRY AN EXTENSION (#2668)
# ==============================================================================
# `_resolve_target` rewrote every dot to a slash before taking the token's
# last path component, so "./b.sh" became "//b/sh" and the lookup key was the
# *extension*. shell, powershell, yaml and javascript therefore reported
# dependency_links while building no edges at all: popularity, betweenness,
# closeness and producer_ratio pinned at 0, pagerank at the uniform 1/N of an
# edgeless graph. The token forms below are the real captures taken from
# keyword-rosetta's shell/powershell/yaml/javascript shells.
_EXTENSION_CARRYING_RELATIVE_IMPORTS = [
    ("shell", "./b.sh", "/repo/b.sh"),
    ("powershell", "./b.ps1", "/repo/b.ps1"),
    ("yaml", "./b.yml", "/repo/b.yml"),
    ("javascript", "./c.js", "/repo/c.js"),
    # Deeper relative forms of the same shape.
    ("javascript-parent", "../lib/helper.js", "/repo/lib/helper.js"),
    ("javascript-subdir", "./lib/helper.js", "/repo/lib/helper.js"),
]


@pytest.mark.parametrize("label,token,expected", _EXTENSION_CARRYING_RELATIVE_IMPORTS)
def test_resolve_target_resolves_relative_import_carrying_extension(sensor, label, token, expected):
    """#2668: each of these resolved to None before the literal-path stage."""
    files = [
        {"path": p, "raw_imports": []}
        for p in ("/repo/main.sh", "/repo/b.sh", "/repo/b.ps1", "/repo/b.yml", "/repo/c.js", "/repo/lib/helper.js")
    ]
    resolution_map = sensor._build_resolution_map(files)
    assert sensor._resolve_target(token, resolution_map, "/repo/main.sh") == expected, label


_RESOLVER_CONTROLS = [
    # (label, token, files, expected) -- forms that already resolved, and
    # must keep resolving by exactly the same route after #2668.
    ("typescript-extensionless-relative", "./c", ["/repo/c.ts"], "/repo/c.ts"),
    ("c-bare-filename", "b.c", ["/repo/b.c"], "/repo/b.c"),
    ("markdown-link", "b.md", ["/repo/b.md"], "/repo/b.md"),
    # The dot-rewrite fallback is what makes a package-style token resolve;
    # #2668 keeps it as the last stage rather than removing it.
    ("python-package-token", "pkg.utils", ["/repo/pkg/utils.py"], "/repo/pkg/utils.py"),
    ("python-deep-package-token", "a.b.utils", ["/repo/a/b/utils.py"], "/repo/a/b/utils.py"),
    # External packages still resolve to nothing.
    ("external-package", "numpy", ["/repo/real.py"], None),
    ("external-dotted", "some.deeply.nested.external.pkg", ["/repo/real.py"], None),
]


@pytest.mark.parametrize("label,token,paths,expected", _RESOLVER_CONTROLS)
def test_resolve_target_controls_unchanged_by_relative_path_stage(sensor, label, token, paths, expected):
    """The controls from #2668's evidence table: extension-only and ./-only
    tokens both already worked; only ./ *plus* an extension was fatal."""
    files = [{"path": p, "raw_imports": []} for p in paths]
    resolution_map = sensor._build_resolution_map(files)
    assert sensor._resolve_target(token, resolution_map, "/repo/main.py") == expected, label


def test_resolve_target_survives_degenerate_relative_tokens(sensor):
    """
    Import tokens are arbitrary captured text, so the relative-path stage
    has to tolerate tokens that are nothing but path syntax -- ".", "..",
    "./" and "" all reach pathlib's `with_suffix("")`, which raises on them.
    """
    files = [{"path": p, "raw_imports": []} for p in ("/repo/main.sh", "/repo/b.sh")]
    resolution_map = sensor._build_resolution_map(files)
    for token in ("", ".", "..", "./", "../", ".././", "/", "..."):
        assert sensor._resolve_target(token, resolution_map, "/repo/main.sh") is None, token


def test_resolve_target_uses_relative_path_context_to_disambiguate(sensor):
    """
    Two files share a filename; the token's own directory context decides,
    and the token's extension must come off before the comparison (candidate
    paths are compared with their suffix stripped).
    """
    files = [{"path": p, "raw_imports": []} for p in ("/repo/lib/helper.js", "/repo/lib/sub/helper.js")]
    resolution_map = sensor._build_resolution_map(files)
    assert sensor._resolve_target("./sub/helper.js", resolution_map, "/repo/main.js") == "/repo/lib/sub/helper.js"
    # Genuinely ambiguous (no path context at all) -- still refuses to guess.
    assert sensor._resolve_target("./helper.js", resolution_map, "/repo/main.js") is None


@pytest.mark.skipif(not HAS_NETWORKX, reason="Requires NetworkX")
def test_relative_extension_imports_produce_a_real_dag(sensor):
    """
    The end-to-end symptom from #2668: keyword-rosetta's shell shell records
    dependency_links 3 with an edgeless graph. Wired through the real graph
    builder, the chain main -> a -> b -> c must now exist.
    """
    files = [
        {"path": "/repo/main.sh", "raw_imports": ["./a.sh"], "lang_id": "shell"},
        {"path": "/repo/a.sh", "raw_imports": ["./b.sh"], "lang_id": "shell"},
        {"path": "/repo/b.sh", "raw_imports": ["./c.sh"], "lang_id": "shell"},
        {"path": "/repo/c.sh", "raw_imports": [], "lang_id": "shell"},
    ]

    mapped_files, _ = sensor.build_dependency_graph(files)

    by_path = {f["path"]: f["telemetry"]["network_metrics"] for f in mapped_files}
    assert by_path["/repo/c.sh"]["in_degree"] == 1
    assert by_path["/repo/main.sh"]["out_degree"] == 1
    assert by_path["/repo/main.sh"]["in_degree"] == 0
    # An edgeless graph gives every node the uniform 1/N pagerank -- the
    # exact fingerprint #2668 was diagnosed from.
    pageranks = {round(m["pagerank_score"], 6) for m in by_path.values()}
    assert len(pageranks) > 1, "uniform pagerank means the graph is still edgeless"
