import inspect
from unittest.mock import patch

import pytest

from gitgalaxy.security import security_auditor as security_auditor_module
from gitgalaxy.security.security_auditor import SecurityAuditor


@pytest.fixture
def mock_artifacts():
    """Provides a baseline payload with a circular dependency to test the graph resolver."""
    return [
        {
            "path": "src/main.py",
            "name": "main.py",
            "raw_imports": ["src/utils.py"],
            "telemetry": {"popularity": 5, "control_flow_ratio": 0.5},
            "hit_vector": [5, 2, 0, 0, 0, 0],  # High danger, some IO
            "file_impact": 0.8,
            "structural_mass": 0.9,  # High mass for shadow patch testing
            "coding_loc": 100,
        },
        {
            "path": "src/utils.py",
            "name": "utils.py",
            "raw_imports": ["src/main.py"],  # Circular loop!
            "telemetry": {"popularity": 1},
            "hit_vector": [0, 0, 0, 0, 0, 0],
            "file_impact": 0.2,
            "coding_loc": 20,
        },
    ]


# ==============================================================================
# TEST 1: DEPENDENCY GRAPH RESOLUTION (exact reach counts, #3040)
# ==============================================================================
def test_dependency_graph_counts_a_cycle_exactly(mock_artifacts):
    """
    #3040: main.py and utils.py import each other, so each has exactly one other
    file upstream and one downstream. A file is never its own dependency. The
    old pure-Python fallback counted 2 here, while networkx counted 1.
    """
    resolved_artifacts = SecurityAuditor()._resolve_dependency_graph(mock_artifacts)

    for artifact in resolved_artifacts:
        network = artifact["dependency_network"]
        assert (network["total_upstream"], network["total_downstream"]) == (1, 1), artifact["name"]
        assert (network["upstream_ratio"], network["downstream_ratio"]) == (0.5, 0.5), artifact["name"]


def test_dependency_graph_matches_networkx_without_a_cap():
    """#3040: exact reach counts, equal to len(nx.descendants / nx.ancestors), with no 500-file cap."""
    nx = pytest.importorskip("networkx")
    names = [f"f{i}.py" for i in range(600)]  # a 600-file chain: the old cap clipped it at 500
    artifacts = [{"path": n, "name": n, "raw_imports": [names[i + 1]] if i < 599 else []} for i, n in enumerate(names)]
    resolved = {a["path"]: a["dependency_network"] for a in SecurityAuditor()._resolve_dependency_graph(artifacts)}
    graph = nx.DiGraph((names[i], names[i + 1]) for i in range(599))
    for n in names:
        assert resolved[n]["total_upstream"] == len(nx.descendants(graph, n)), n
        assert resolved[n]["total_downstream"] == len(nx.ancestors(graph, n)), n
    assert resolved["f0.py"]["total_upstream"] == 599


def test_dependency_graph_past_its_work_budget_is_none():
    """A graph too large for the budget leaves the totals "not computed" -- None, never 0."""
    # A chain (not a single cycle, which condenses to one component and needs no
    # bitset work), so the budget is charged and a zero budget is exceeded.
    names = ["a.py", "b.py", "c.py"]
    artifacts = [{"path": n, "name": n, "raw_imports": names[i + 1 : i + 2]} for i, n in enumerate(names)]
    with patch("gitgalaxy.security.security_auditor.PATH_METRICS_WORK_BUDGET", 0):
        resolved_artifacts = SecurityAuditor()._resolve_dependency_graph(artifacts)

    network = resolved_artifacts[0]["dependency_network"]
    assert (network["total_upstream"], network["total_downstream"], network["upstream_ratio"]) == (None, None, None)
    assert network["direct_upstream"] == 1  # the direct counts never needed the graph


# ==============================================================================


# ==============================================================================
# TEST 2: AUDIT ENTRY POINT (no model, #8430)
# ==============================================================================
def test_audit_repository_resolves_dependency_counts(mock_artifacts):
    audited = SecurityAuditor().audit_repository(mock_artifacts)
    for artifact in audited:
        assert artifact["dependency_network"]["total_upstream"] == 1
        # No classifier ships: nothing is scored or flagged as a threat.
        assert "is_ml_threat" not in artifact
        assert "AI Threat Score" not in artifact.get("telemetry", {}).get("domain_context", {})


def test_audit_repository_empty_state():
    """The auditor exits safely when the repository has 0 artifacts."""
    assert SecurityAuditor().audit_repository([]) == []


def test_the_classifier_is_gone():
    """#8430: the XGBoost classifier and its switches are removed, not dormant."""
    assert not hasattr(security_auditor_module, "ML_AVAILABLE")
    assert not hasattr(SecurityAuditor, "_construct_feature_matrix")
    assert "model_path" not in inspect.signature(SecurityAuditor.__init__).parameters


# ==============================================================================
# TEST 3: MANUAL SHADOW PATCH ALERT (#8431)
# ==============================================================================
def test_shadow_patch_flag_alerts_and_never_unflagged():
    def art(impact):
        return {"path": "a.py", "file_impact": impact, "telemetry": {}}

    auditor = SecurityAuditor()
    heavy, light = art(0.9), art(0.1)
    auditor.audit_repository([heavy, light], is_shadow_patch=True)
    assert "manually asserted" in heavy["telemetry"]["domain_context"]["alert"]
    assert "alert" not in light["telemetry"].get("domain_context", {})
    unflagged = art(0.9)
    auditor.audit_repository([unflagged])
    assert "alert" not in unflagged["telemetry"].get("domain_context", {})
