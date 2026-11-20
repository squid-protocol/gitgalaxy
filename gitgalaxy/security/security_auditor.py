# ==============================================================================
# security_auditor.py
# GitGalaxy Phase 7.8: Transitive Dependency Resolution
# ==============================================================================
# #8430: the XGBoost malware classifier was removed (owner decision 2026-11-19: research
# pending, no model ships). What stays works without a model: the transitive
# upstream/downstream counts and the manual --shadow-patch-detected alert (#8431).
import logging
from pathlib import Path

from gitgalaxy.core.graph_engine import GraphIndex, WorkBudget, WorkBudgetExceeded, reach_counts
from gitgalaxy.core.network_risk_sensor import PATH_METRICS_WORK_BUDGET


class SecurityAuditor:
    """
    Transitive Dependency Resolver.

    Calculates deep N-th degree dependency graphs to map the systemic Dependency Impact
    of every artifact (`total_upstream` / `total_downstream`), and applies the manual
    shadow-patch hint when the caller asserts one.
    """

    def __init__(self, parent_logger=None):
        self.logger = (
            parent_logger.getChild("security_auditor") if parent_logger else logging.getLogger("security_auditor")
        )

    MANUAL_SHADOW_PATCH_ALERT = (
        "SHADOW PATCH (manually asserted via --shadow-patch-detected; no hash or version was compared)"
    )

    def _apply_manual_shadow_patch_hint(self, artifacts):
        """
        Annotates structurally heavy files when the caller asserted a shadow patch.
        The flag is a human claim: nothing is hashed or compared, so this assigns
        no threat class and no score, and (#8431).
        """
        for artifact in artifacts:
            if artifact.get("file_impact", 0.0) > 0.5:
                ctx = artifact.setdefault("telemetry", {}).setdefault("domain_context", {})
                ctx["alert"] = self.MANUAL_SHADOW_PATCH_ALERT

    def audit_repository(self, artifacts, is_shadow_patch=False):
        """Resolves each artifact's transitive dependency counts; no model runs."""
        if not artifacts:
            return artifacts

        self.logger.info("Resolving N-th degree dependency graphs...")
        try:
            artifacts = self._resolve_dependency_graph(artifacts)
        except Exception as e:
            self.logger.error(
                f"❌ Catastrophic failure during dependency graph resolution: {e}",
                exc_info=True,
            )

        if is_shadow_patch:
            self._apply_manual_shadow_patch_hint(artifacts)

        return artifacts

    def _resolve_dependency_graph(self, artifacts):
        """
        Resolves each file's transitive fragility and Downstream Exposure.
        `total_upstream` counts every file it depends on, directly or
        transitively. `total_downstream` counts every file that depends on it.

        #3040: one native implementation, the same in both modes, exact, with
        no 500-file cap. graph_engine.reach_counts condenses the graph's
        cycles and ORs reachability bitsets along the condensation. It gives
        the same counts as `len(nx.descendants(G, f))` /
        `len(nx.ancestors(G, f))`.

        It replaced two implementations:
        - networkx's calls, capped at 500
        - a pure-Python BFS fallback that disagreed with them: it counted a
          file on a cycle as its own dependency, and its cap check could
          overshoot 500

        Past PATH_METRICS_WORK_BUDGET, both totals and their ratios are None
        ("not computed"), never a placeholder 0.
        """
        resolution_map = {}
        for artifact in artifacts:
            p = artifact.get("path", "")
            name = artifact.get("name", Path(p).name)
            stem = Path(p).stem
            if p:
                resolution_map[p] = p
            if name:
                resolution_map[name] = p
            if stem:
                resolution_map[stem] = p

        total_repo_files = max(len(artifacts), 1)

        edges: dict[tuple[str, str], float] = {}
        for artifact in artifacts:
            curr = artifact.get("path", "")
            for imp in artifact.get("raw_imports", []):
                if imp in resolution_map:
                    target = resolution_map[imp]
                    if target != curr:
                        edges.setdefault((curr, target), 1.0)
        index = GraphIndex(
            (artifact.get("path", "") for artifact in artifacts),
            ((src, dst, weight) for (src, dst), weight in edges.items()),
        )
        try:
            descendants, ancestors = reach_counts(index, WorkBudget(PATH_METRICS_WORK_BUDGET))
            reach = {path: (descendants[i], ancestors[i]) for i, path in enumerate(index.nodes)}
        except WorkBudgetExceeded as e:
            self.logger.info(f"Reach counts past their work budget, leaving them unset (None): {e}")
            reach = {}

        for artifact in artifacts:
            path = artifact.get("path", "")
            tot_up, tot_down = reach.get(path, (None, None))
            artifact["dependency_network"] = {
                "direct_upstream": len(artifact.get("raw_imports", [])),
                "direct_downstream": artifact.get("telemetry", {}).get("popularity", 0),
                "total_upstream": tot_up,
                "total_downstream": tot_down,
                "upstream_ratio": None if tot_up is None else round(tot_up / total_repo_files, 4),
                "downstream_ratio": None if tot_down is None else round(tot_down / total_repo_files, 4),
            }

        return artifacts
