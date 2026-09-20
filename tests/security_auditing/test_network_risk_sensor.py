import copy
from unittest.mock import patch

import pytest

# Adjust this import to match your project structure
from gitgalaxy.core.network_risk_sensor import NetworkRiskSensor

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
def test_every_graph_metric_is_computed(sensor, parsed_files_universe):
    """
    #3041: one builder, no optional package. Every graph metric is computed --
    no 0.0 placeholder and no None -- on every install.
    """
    mapped_files, metrics = sensor.build_dependency_graph(parsed_files_universe)

    foundation = next(f for f in mapped_files if f["path"] == "/src/core/foundation.py")
    assert foundation["telemetry"]["network_metrics"]["ecosystem_role"] == "Pure Producer (Foundation)"
    assert foundation["telemetry"]["network_metrics"]["pagerank_score"] > 0.0
    assert foundation["telemetry"]["network_metrics"]["closeness_score"] > 0.0
    # orchestrator -> transceiver -> heavy_calc is the only path between them.
    transceiver = next(f for f in mapped_files if f["path"] == "/src/utils/transceiver.py")
    assert transceiver["telemetry"]["network_metrics"]["betweenness_score"] > 0.0
    assert metrics["cyclic_density"] > 0.0
    for key in ("modularity", "assortativity", "avg_path_length", "articulation_points"):
        assert metrics[key] is not None, key


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
    Regression test for #261, through the degree counts: the ambiguity-safe
    resolution wires only the path-qualified import.
    """
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
def test_betweenness_is_computed_for_every_file(sensor, parsed_files_universe):
    """#3038: exact betweenness for every file, and repeat builds give the same floats."""
    first = {
        f["path"]: f["telemetry"]["network_metrics"] for f in sensor.build_dependency_graph(parsed_files_universe)[0]
    }
    again = {
        f["path"]: f["telemetry"]["network_metrics"]
        for f in sensor.build_dependency_graph(copy.deepcopy(MOCK_PARSED_FILES))[0]
    }
    for path, metrics in first.items():
        assert metrics["betweenness_score"] is not None, path
        assert again[path]["betweenness_score"] == metrics["betweenness_score"], path
    # Degree is exact and never depended on the centrality math.
    assert first["/src/core/foundation.py"]["ecosystem_role"] == "Pure Producer (Foundation)"


def test_betweenness_past_its_work_budget_is_none(sensor, parsed_files_universe):
    """A graph too large for the budget leaves betweenness "not computed" -- None, never 0.0."""
    with patch("gitgalaxy.core.network_risk_sensor.PATH_METRICS_WORK_BUDGET", 0):
        mapped_files, _ = sensor.build_dependency_graph(parsed_files_universe)

    foundation = next(f for f in mapped_files if f["path"] == "/src/core/foundation.py")
    metrics = foundation["telemetry"]["network_metrics"]
    assert metrics["betweenness_score"] is None
    assert metrics["pagerank_score"] is not None
    assert metrics["ecosystem_role"] == "Pure Producer (Foundation)"


def test_pagerank_failure_degrades_to_none(sensor, parsed_files_universe):
    """#3027: a PageRank that fails to converge is None ("not computed") for the PageRank family only."""
    with patch("gitgalaxy.core.network_risk_sensor.pagerank", side_effect=RuntimeError("no convergence")):
        mapped_files, _ = sensor.build_dependency_graph(parsed_files_universe)

    foundation = next(f for f in mapped_files if f["path"] == "/src/core/foundation.py")
    metrics = foundation["telemetry"]["network_metrics"]
    assert metrics["pagerank_score"] is None
    assert metrics["normalized_blast_radius"] is None
    assert metrics["systemic_threat_vector"] is None
    assert metrics["ecosystem_role"] == "Pure Producer (Foundation)"


# ==============================================================================
# TEST 13: MACRO NETWORK MATH RESILIENCE — INDIVIDUAL METRIC FAILURES
# ==============================================================================
def test_macro_metrics_are_all_computed(sensor, parsed_files_universe):
    """
    #3035-#3039: every macro metric is native, so none is ever None on a graph with
    imports (the engine never imports networkx: test_no_networkx_runtime.py).
    """
    _, macro_metrics = sensor.build_dependency_graph(parsed_files_universe)

    assert macro_metrics["cyclic_density"] > 0.0  # the universe has a cycle
    for key in ("modularity", "assortativity", "cyclic_density", "avg_path_length", "articulation_points"):
        assert macro_metrics[key] is not None, key


def test_assortativity_needs_no_numpy(sensor, parsed_files_universe):
    """
    #3036: networkx's assortativity imports numpy, which networkx does not
    install, so a scan with networkx but no numpy silently lost the metric. The
    native one needs neither.
    """
    with patch.dict("sys.modules", {"numpy": None}):
        _, macro = sensor.build_dependency_graph(parsed_files_universe)
    assert macro["assortativity"] is not None


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
    Regression test for #2540, through the degree counts: case-folded
    resolution reaches the fortran module and the cobol copybook.
    """
    mapped_files, _ = sensor.build_dependency_graph(case_fold_universe)

    a_f90 = next(f for f in mapped_files if f["path"] == "/src/orbit_math.f90")
    assert a_f90["telemetry"]["network_metrics"]["in_degree"] == 1
    a_cpy = next(f for f in mapped_files if f["path"] == "/cbl/payroll.cpy")
    assert a_cpy["telemetry"]["network_metrics"]["in_degree"] == 1


# ==============================================================================
# TEST 19: THE FOLD NEVER INVENTS A CROSS-LANGUAGE EDGE (#2540)
# ==============================================================================
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


# #perf: Stage-2 import disambiguation used to strip each candidate's extension
# with pathlib.Path(c).with_suffix(""), constructed once per candidate. On a
# generated SDK a single token matches thousands of same-stem candidates, so
# that ran into the millions and dominated the whole graph phase. _stem_path
# replaces it with the existing pure-string _without_extension, memoized per
# path. These guard the equivalence the swap relies on.
def test_stem_path_matches_pathlib_with_suffix(sensor):
    from pathlib import Path

    for c in [
        "src/models/account.ts",
        "src/models/account.d.ts",
        "a/b.c/index.js",  # dotted directory: only the final component's ext comes off
        "src/util",  # no extension
        "src/.eslintrc",  # leading dot is a hidden-file marker, not an extension
        "deep/nested/path/to/File.TSX",
    ]:
        expected = str(Path(c).with_suffix("")).replace("\\", "/")
        assert sensor._stem_path(c) == expected, c


def test_stem_path_is_memoized(sensor):
    first = sensor._stem_path("src/models/account.ts")
    assert sensor._stem_cache["src/models/account.ts"] == first
    # a second call returns the cached value, not a recomputation
    assert sensor._stem_path("src/models/account.ts") is first


def test_stage2_disambiguation_survives_the_memo(sensor):
    # Two files share the stem "utils"; a path-qualified token must still
    # resolve to exactly one, using the extension-stripped candidate compare.
    files = [
        {"path": "/repo/core/utils.ts", "raw_imports": [], "lang_id": "typescript"},
        {"path": "/repo/web/utils.ts", "raw_imports": [], "lang_id": "typescript"},
        {"path": "/repo/main.ts", "raw_imports": ["./core/utils"], "lang_id": "typescript"},
    ]
    mapped = {f["path"]: f["telemetry"]["network_metrics"] for f in sensor.build_dependency_graph(files)[0]}
    assert mapped["/repo/core/utils.ts"]["in_degree"] == 1
    assert mapped["/repo/web/utils.ts"]["in_degree"] == 0


# ==============================================================================
# TEST 21: AMBIGUOUS IMPORT TARGETS (#3199)
# ==============================================================================
# Before #3199 an import token matching more than one file produced NO edge.
# On real mainframe repositories that threw away most copybook dependencies:
# all 12 COPY statements in IBM's zopeneditor-sample (every copybook ships
# twice, under COPYBOOK/ and multiroot/copybooks/) and 36 of CBSA's 119
# (`COPY ACCTCTRL` matches ACCTCTRL.cpy AND the ACCTCTRL.cbl program, .jcl and
# .lked beside it). The fixtures below are those two shapes, reduced.
def _cobol(path, imports=(), classes=()):
    return {
        "path": path,
        "lang_id": "cobol",
        "raw_imports": list(imports),
        "classes": [{"name": c} for c in classes],
    }


def _resolve(sensor, files, src_path, token):
    """`_resolve_target` with the Stage-3 inputs the real graph builder passes."""
    src = next(f for f in files if f["path"] == src_path)
    return sensor._resolve_target(
        token,
        sensor._build_resolution_map(files),
        src_path,
        folded_maps=sensor._build_folded_resolution_map(files),
        fold_lang=sensor._fold_lang(src),
        src_lang=str(src.get("lang_id", "")).lower(),
        file_facts=sensor._build_file_facts(files),
    )


def test_copy_prefers_the_member_over_the_program_of_the_same_name(sensor):
    """CBSA: `COPY ACCTCTRL` in BANKDATA is the copybook, never the program.

    The nearest same-named file is the .cbl in BANKDATA's own directory, so
    proximity alone gets this wrong -- the PROGRAM-ID is what disqualifies it.
    """
    files = [
        _cobol("src/base/cobol_src/BANKDATA.cbl", imports=["ACCTCTRL"], classes=["BANKDATA"]),
        _cobol("src/base/cobol_src/ACCTCTRL.cbl", classes=["ACCTCTRL"]),
        _cobol("src/base/cobol_copy/ACCTCTRL.cpy"),
        {"path": "etc/install/base/buildjcl/ACCTCTRL.jcl", "lang_id": "jcl", "raw_imports": []},
    ]
    assert _resolve(sensor, files, "src/base/cobol_src/BANKDATA.cbl", "ACCTCTRL") == "src/base/cobol_copy/ACCTCTRL.cpy"


def test_copy_of_its_own_name_is_the_copybook_not_the_program_itself(sensor):
    """CBSA's CREACC.cbl copies CREACC: the .cpy, and not a self-edge."""
    files = [
        _cobol("src/base/cobol_src/CREACC.cbl", imports=["CREACC"], classes=["CREACC"]),
        _cobol("src/base/cobol_copy/CREACC.cpy"),
    ]
    assert _resolve(sensor, files, "src/base/cobol_src/CREACC.cbl", "CREACC") == "src/base/cobol_copy/CREACC.cpy"


def test_copy_prefers_the_importers_own_language(sensor):
    """CBSA: `COPY CUSTOMER` matches CUSTOMER.cpy and an exact-case CUSTOMER.java."""
    files = [
        _cobol("src/base/cobol_src/INQCUST.cbl", imports=["CUSTOMER"], classes=["INQCUST"]),
        _cobol("src/base/cobol_copy/CUSTOMER.cpy"),
        {"path": "src/webui/src/main/java/datainterfaces/CUSTOMER.java", "lang_id": "java", "raw_imports": []},
    ]
    assert _resolve(sensor, files, "src/base/cobol_src/INQCUST.cbl", "CUSTOMER") == "src/base/cobol_copy/CUSTOMER.cpy"


def test_copy_takes_the_library_its_own_workspace_root_owns(sensor):
    """zopeneditor: the same copybook exists under two roots.

    `COBOL/SAM1.cbl` takes the shallower repository-wide `COPYBOOK/`, and
    `multiroot/sam/SAM1.cbl` takes the one inside its own subtree -- which is
    what the zapp.yaml library search order resolves to, per the answer key.
    """
    files = [
        _cobol("COBOL/SAM1.cbl", imports=["CUSTCOPY"], classes=["SAM1"]),
        _cobol("multiroot/sam/SAM1.cbl", imports=["CUSTCOPY"], classes=["SAM1"]),
        _cobol("COPYBOOK/CUSTCOPY.cpy"),
        _cobol("multiroot/copybooks/cust/CUSTCOPY.cpy"),
    ]
    assert _resolve(sensor, files, "COBOL/SAM1.cbl", "CUSTCOPY") == "COPYBOOK/CUSTCOPY.cpy"
    assert _resolve(sensor, files, "multiroot/sam/SAM1.cbl", "CUSTCOPY") == "multiroot/copybooks/cust/CUSTCOPY.cpy"


def test_copy_of_a_member_absent_from_the_repo_draws_no_edge(sensor):
    """CBSA: `COPY BNK1CAM` is a BMS symbolic map generated at build time.

    No copybook of that name exists. The nearest same-named files are the BMS
    source and its build JCL, and neither is the member COBOL copies -- a
    copybook is COBOL source by definition, so the edge is dropped (the
    cross-language link belongs to the BMS work, #3122).
    """
    files = [
        _cobol("src/base/cobol_src/BNK1CAC.cbl", imports=["BNK1CAM"], classes=["BNK1CAC"]),
        {"path": "src/base/bms_src/BNK1CAM.bms", "lang_id": "bms", "raw_imports": []},
        {"path": "etc/install/base/buildjcl/BNK1CAM.jcl", "lang_id": "jcl", "raw_imports": []},
    ]
    assert _resolve(sensor, files, "src/base/cobol_src/BNK1CAC.cbl", "BNK1CAM") is None


def test_equally_near_and_equally_shallow_candidates_still_draw_no_edge(sensor):
    """Nothing in the repository separates these two, so the resolver still refuses.

    The proximity tiebreak is deliberately NOT a total order: alphabetical
    order is not a reason to believe an edge.
    """
    files = [
        _cobol("src/PROG.cbl", imports=["SHARED"], classes=["PROG"]),
        _cobol("lib_a/SHARED.cpy"),
        _cobol("lib_b/SHARED.cpy"),
    ]
    assert _resolve(sensor, files, "src/PROG.cbl", "SHARED") is None


def test_a_relative_include_that_matches_nothing_exactly_draws_no_edge(sensor):
    """`%INCLUDE './x.inc'` names one location. If nothing is there, no near miss counts.

    PL/I is the member language whose capture can carry a quoted path, so it
    is the one that can reach Stage 3 with a relative token.
    """
    files = [
        {"path": "pli/MAIN.pli", "lang_id": "pli", "raw_imports": ["./shared.inc"], "classes": []},
        {"path": "pli/lib/shared.inc", "lang_id": "pli", "raw_imports": [], "classes": []},
        {"path": "pli/lib/deep/shared.inc", "lang_id": "pli", "raw_imports": [], "classes": []},
    ]
    assert _resolve(sensor, files, "pli/MAIN.pli", "./shared.inc") is None
    mapped = {f["path"]: f["telemetry"]["network_metrics"] for f in sensor.build_dependency_graph(files)[0]}
    assert mapped["pli/lib/shared.inc"]["in_degree"] == 0


def test_an_ambiguous_bare_stem_outside_the_member_languages_still_draws_no_edge(sensor):
    """#261's contract is untouched: Stage 3 is scoped to the member languages.

    The same shape that now resolves for a COBOL `COPY` -- a bare ambiguous
    stem with a nearest candidate in the importer's own directory -- must
    still draw nothing for an ordinary `import utils`.
    """
    files = [
        {"path": "/src/service_a/handler.py", "lang_id": "python", "raw_imports": ["utils"], "classes": []},
        {"path": "/src/service_a/utils.py", "lang_id": "python", "raw_imports": [], "classes": []},
        {"path": "/src/service_b/utils.py", "lang_id": "python", "raw_imports": [], "classes": []},
    ]
    assert _resolve(sensor, files, "/src/service_a/handler.py", "utils") is None


def test_ambiguous_copybook_edges_reach_the_real_graph_and_edge_data(sensor):
    """End to end: the recovered edges are real DAG edges, not just resolutions."""
    files = [
        _cobol("src/base/cobol_src/BANKDATA.cbl", imports=["ACCTCTRL", "CUSTOMER"], classes=["BANKDATA"]),
        _cobol("src/base/cobol_src/ACCTCTRL.cbl", classes=["ACCTCTRL"]),
        _cobol("src/base/cobol_copy/ACCTCTRL.cpy"),
        _cobol("src/base/cobol_copy/CUSTOMER.cpy"),
    ]
    mapped = {f["path"]: f["telemetry"]["network_metrics"] for f in sensor.build_dependency_graph(files)[0]}
    assert mapped["src/base/cobol_copy/ACCTCTRL.cpy"]["in_degree"] == 1
    assert mapped["src/base/cobol_copy/CUSTOMER.cpy"]["in_degree"] == 1
    assert mapped["src/base/cobol_src/ACCTCTRL.cbl"]["in_degree"] == 0
    assert {(e["src"], e["dst"]) for e in sensor.dependency_edges} == {
        ("src/base/cobol_src/BANKDATA.cbl", "src/base/cobol_copy/ACCTCTRL.cpy"),
        ("src/base/cobol_src/BANKDATA.cbl", "src/base/cobol_copy/CUSTOMER.cpy"),
    }
