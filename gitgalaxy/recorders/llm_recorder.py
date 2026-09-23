# ==============================================================================

# galaxyscope:ignore sec_high_risk_execution, sec_db_hooks
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

# galaxyscope:ignore sec_high_risk_execution, sec_db_hooks

# galaxyscope:ignore sec_high_risk_execution, ai_guardrails, sec_db_hooks

import logging
import sqlite3
import statistics
from pathlib import Path
from typing import Any, Optional

from gitgalaxy.standards import analysis_lens as config

# ==============================================================================

# galaxyscope:ignore sec_high_risk_execution, sec_db_hooks
# GitGalaxy Phase 10: LLM Recorder (The AI Translation Layer)
# Strategy Protocol: Token Density, Distribution Topology & Context Graphs
# ==============================================================================

# galaxyscope:ignore sec_high_risk_execution, sec_db_hooks


class LLMRecorder:
    """
    PURPOSE: Translates raw GitGalaxy telemetry into AI-optimized artifacts.

    FEATURES:
    1. Statistical Topologies: Calculates Min/Max/Mean/Median/Mode for all risks.
    2. Syntactic Bottlenecks: Isolates I/O and Dependency choke points.
    3. High-Impact Functions: Ranks top 10 functions by structural magnitude.
    4. Relational Knowledge Graph: Builds a SQLite DB for autonomous agents.
    5. Markdown Brief: Token-compressed text for standard LLM context windows.
    """

    def __init__(
        self,
        parent_logger: Optional[logging.Logger] = None,
        scan_config: Optional[dict[str, Any]] = None,
    ):
        if parent_logger:
            self.logger = parent_logger.getChild("llm_recorder")
            self.logger.setLevel(parent_logger.level)
        else:
            self.logger = logging.getLogger("llm_recorder")
            self.logger.setLevel(logging.INFO)

        # --- DYNAMIC SCHEMA FETCH ---
        schemas = getattr(config, "RECORDING_SCHEMAS", {})
        self.RISK_SCHEMA = schemas.get("RISK_SCHEMA", [])
        self.SIGNAL_SCHEMA = schemas.get("SIGNAL_SCHEMA", [])
        # gitgalaxy#2991 (Option A): canonical new-name -> legacy risk_* name.
        # Used ONLY to translate this recorder's human-readable brief labels
        # (the markdown narrative auto-committed to
        # docs/gitgalaxy_architecture_brief.md) to the new descriptive
        # vocabulary. Nothing keyed by RISK_SCHEMA/risk_vector positions
        # above changes -- the brief is generated text, not a schema.
        self.VECTOR_NAMES = schemas.get("VECTOR_NAMES", {})
        self._legacy_to_new = {legacy: new for new, legacy in self.VECTOR_NAMES.items()}
        # gitgalaxy#2994: Tier-1 declarative family map, bound the same way
        # as RISK_SCHEMA/SIGNAL_SCHEMA above -- not part of RECORDING_SCHEMAS
        # itself (a standalone top-level constant). Drives section 6b of the
        # markdown brief (display-only; never golden-mastered).
        self.SURFACE_FAMILIES = getattr(config, "SURFACE_FAMILIES", {})
        # gitgalaxy#3111/#3114: which vectors this scan may narrate, and how.
        # inactive = measured on no file this run, so it appears nowhere
        # (absent, not a 0.0 that would read as a measurement). context =
        # measured and tabled, but barred from the risk-driver narrative.
        self.inactive_vectors = config.inactive_vectors(scan_config)
        self.CONTEXT_VECTORS = getattr(config, "CONTEXT_VECTORS", {})

    def _format_new_vector_name(self, new_name: str) -> str:
        """Renders a VECTOR_NAMES canonical name (e.g. 'concurrency_surface')
        as a display label (e.g. 'Concurrency Surface').

        `hist_*` entries are the PROMOTE-flagged predictive-layer family
        (gitgalaxy#2991's disposition table): currently inert in every scan
        (GITGALAXY_DISABLE_GIT_HISTORY ablates them to zero) pending
        temporal-crucible#29's history-enabled mode and gitgalaxy#2987's
        defect-lift promotion gate. Say so on the label itself so an LLM
        reading the brief doesn't treat a current stability/churn value as a
        live predictor.
        """
        if new_name.startswith("hist_"):
            rest = new_name[len("hist_") :].replace("_", " ").title()
            return f"Historical {rest} (predictive layer, promotion pending #2987)"
        return new_name.replace("_", " ").title()

    def _surface_label(self, bare_slug: str, old_label: str) -> str:
        """Translates a risk_* vector's legacy display label to the new
        descriptive vocabulary from gitgalaxy#2991, noting the alias on
        first use. Falls back to `old_label` untouched when no mapping is
        bound (e.g. tests that stub RECORDING_SCHEMAS without VECTOR_NAMES)
        or for entries VECTOR_NAMES doesn't cover.
        """
        new_name = self._legacy_to_new.get(f"risk_{bare_slug}")
        if not new_name:
            return old_label
        return f"{self._format_new_vector_name(new_name)} (formerly {old_label})"

    def _driver_labels(self, risk_vector: list[Any], limit: int = 4) -> list[str]:
        """The highest surface vectors for one file, as display strings.

        Excludes two classes of vector (#3111/#3114), which is the whole
        point: this line is meant to DISCRIMINATE between files, and a vector
        that reads at ceiling everywhere cannot. Measured on the
        zopeneditor-sample scan, spec_match and documentation took 2 of the 4
        slots on all ten top-10 entries before this filter existed.

        - inactive vectors were not measured at all this run;
        - context vectors (documentation coverage) are reported in section 6
          and beside program length, but are not fragility drivers.
        """
        drivers: list[tuple[str, float]] = []
        for i, value in enumerate(risk_vector):
            if i >= len(self.RISK_SCHEMA):
                break
            slug = self.RISK_SCHEMA[i]
            if slug in self.inactive_vectors or slug in self.CONTEXT_VECTORS:
                continue
            if isinstance(value, (int, float)) and value > 0:
                drivers.append((slug, float(value)))

        drivers.sort(key=lambda kv: kv[1], reverse=True)
        # Rounded for reading: the raw sigmoid carries noise digits (99.9999%)
        # that imply a precision the meter does not have, and section 6's
        # table already reports these to one decimal.
        return [
            f"{self._surface_label(slug, slug.replace('_', ' ').title())} ({round(value, 1)}%)"
            for slug, value in drivers[:limit]
        ]

    def _coverage_labels(self, risk_vector: list[Any]) -> list[str]:
        """Context-family vectors for one file, phrased as coverage (#3114).

        Reported so nothing is lost by removing them from the driver line --
        the ask was to reframe the vector, not to hide it.
        """
        labels = []
        for i, value in enumerate(risk_vector):
            if i >= len(self.RISK_SCHEMA):
                break
            slug = self.RISK_SCHEMA[i]
            if slug in self.CONTEXT_VECTORS and isinstance(value, (int, float)):
                labels.append(f"{value}% of unit weight undocumented")
        return labels

    def _blast_radius_sentence(self, file_data: dict[str, Any]) -> str:
        """What a change to this file would reach, in words (#3113).

        The brief already computed every number here; it just never stated
        the consequence. Reads the dependency edges rather than any risk
        vector, so it says something verifiable.

        Outbound count comes from raw_imports, matching section 7's
        `_outbound` and the executive summary rather than the resolved
        `out_degree`: the two disagree (a file listing two imports can carry
        out_degree 0 when neither resolves to an in-repo artifact), and
        reporting "depends on 0" directly above a line that names two imports
        reads as a bug.
        """
        net_metrics = file_data.get("telemetry", {}).get("network_metrics", {})
        raw_imports = file_data.get("raw_imports", [])
        in_degree = net_metrics.get("in_degree", 0) or 0
        out_degree = len(raw_imports) if isinstance(raw_imports, list) else 0
        blast = net_metrics.get("normalized_blast_radius")
        role = net_metrics.get("ecosystem_role", "Unknown")

        if in_degree == 0 and out_degree == 0:
            return "isolated in the scanned graph -- no in-repo artifact imports it and it imports none"
        parts = []
        if in_degree:
            parts.append(f"changing it is visible to **{in_degree}** in-repo importer(s)")
        else:
            parts.append("nothing in-repo imports it (entrypoint or orphan)")
        if out_degree:
            parts.append(f"it depends on **{out_degree}**")
        if blast is not None:
            parts.append(f"blast radius {blast}")
        if role and role != "Unknown":
            parts.append(f"role: {role}")
        return "; ".join(parts)

    def _parse_threat_score(self, artifact: dict) -> tuple[float, str]:
        """Safely extracts and converts the AI threat score string to a float."""
        score_str = artifact.get("telemetry", {}).get("domain_context", {}).get("AI Threat Score", "0.0%")
        try:
            return float(score_str.replace("%", "")), score_str
        except ValueError:
            return 0.0, score_str

    def generate_artifacts(
        self,
        parsed_files: list[dict[str, Any]],
        unparsable_files: list[dict[str, Any]],
        summary: dict[str, Any],
        session_meta: dict[str, Any],
        output_dir: str,
        forensic_report: Optional[dict[str, Any]] = None,
    ):
        """Generates the dual-output AI artifacts: Markdown and SQLite."""
        if forensic_report is None:
            forensic_report = {}

        target_name = session_meta.get("target", "unknown_project")
        safe_dir = Path(output_dir)

        output_path_md = safe_dir / f"{target_name}_galaxy_llm.md"
        output_path_db = safe_dir / f"{target_name}_galaxy_graph.sqlite"

        self.logger.info(f"Initiating LLM Artifact Generation for '{target_name}'...")

        # --- REVERSE DEPENDENCY RESOLUTION ---
        resolution_map = {}
        for s in parsed_files:
            path = s.get("path", "")
            name = s.get("name", Path(path).name)
            stem = Path(path).stem
            if path:
                resolution_map[path] = path
            if name:
                resolution_map[name] = path
            if stem:
                resolution_map[stem] = path

        from collections import defaultdict

        inbound_set_map = defaultdict(set)
        outbound_set_map = defaultdict(set)

        for s in parsed_files:
            curr = s.get("path", "")
            for imp in s.get("raw_imports", []):
                if imp in resolution_map:
                    target_path = resolution_map[imp]
                    if target_path != curr:
                        inbound_set_map[target_path].add(curr)
                        outbound_set_map[curr].add(target_path)

        inbound_map = {k: list(v) for k, v in inbound_set_map.items()}

        # 1. Build the Relational Knowledge Graph (SQLite)
        self._generate_sqlite_graph(
            parsed_files,
            summary,
            session_meta,
            output_path_db,
            inbound_map,
        )

        # 2. Build the Token-Optimized Markdown Brief
        md_content = self._build_markdown(
            parsed_files,
            unparsable_files,
            summary,
            session_meta,
            forensic_report,
        )

        try:
            with open(output_path_md, "w", encoding="utf-8") as f:
                f.write(md_content)
            self.logger.info(
                f"AI Artifact Generation Complete:\n -> Markdown: {output_path_md}\n -> SQLite: {output_path_db}"
            )
        except Exception as e:
            self.logger.error(f"Failed to seal LLM brief: {e}", exc_info=True)

    def _executive_summary_lines(
        self,
        parsed_files: list[dict[str, Any]],
        sum_data: dict[str, Any],
        comp: dict[str, Any],
    ) -> list[str]:
        """The answer-first section (#3113).

        The brief's most verifiable and most differentiated content is the
        cross-language dependency graph, and it used to sit in section 7,
        behind ~170 lines of lexicon and statistics tables. On the
        zopeneditor-sample audit that graph was independently confirmed
        correct against the source (the most-depended-on copybook really had
        three inbound PL/I includes; the top orchestrator really was the
        compile-and-link-everything JCL job), so it earns the lead.

        Every number here is already computed elsewhere in the brief; this
        section assembles them into the two questions a reader actually
        arrives with -- what is this, and what holds it up.

        Reuses section 7's zero-guard discipline (#2556): with no resolvable
        imports anywhere, a "most depended upon" ranking is just scan order
        wearing a superlative, so say the graph is flat instead.
        """
        lines = ["## 1. EXECUTIVE SUMMARY"]

        visible = sum_data.get("verified_files", len(parsed_files))
        total_loc = sum_data.get("total_loc") or sum(f.get("total_loc", 0) for f in parsed_files)

        langs = comp.get("languages") if isinstance(comp.get("languages"), dict) else comp
        lang_parts = []
        if isinstance(langs, dict):
            ranked = sorted(
                ((k, v) for k, v in langs.items() if isinstance(v, (int, float))),
                key=lambda kv: kv[1],
                reverse=True,
            )[:4]
            lang_parts = [f"{name} ({value})" for name, value in ranked]
        lines.append(
            f"- **Scope:** {visible} analyzed artifact(s), {total_loc} LOC."
            + (f" Dominant languages: {', '.join(lang_parts)}." if lang_parts else "")
        )

        def _inbound(file_data: dict[str, Any]) -> int:
            return file_data.get("telemetry", {}).get("popularity", 0) or 0

        def _outbound(file_data: dict[str, Any]) -> int:
            raw = file_data.get("raw_imports", [])
            return len(raw) if isinstance(raw, list) else 0

        if any(_inbound(f) > 0 for f in parsed_files):
            top = max(parsed_files, key=_inbound)
            lines.append(
                f"- **Load-bearing artifact:** `{top.get('path', 'unknown')}` -- {_inbound(top)} in-repo "
                "importer(s) depend on it. Changes here propagate furthest."
            )
        else:
            lines.append(
                "- **Load-bearing artifact:** none identifiable. No file in this repository is imported by "
                "another that GitGalaxy could resolve, so there is no dependency hierarchy to report. That is "
                "itself a finding: either this is a collection of independent scripts/documents rather than a "
                "coupled system, or the import style is one the engine does not resolve for these languages."
            )

        if any(_outbound(f) > 0 for f in parsed_files):
            orchestrator = max(parsed_files, key=_outbound)
            lines.append(
                f"- **Top orchestrator:** `{orchestrator.get('path', 'unknown')}` -- pulls in "
                f"{_outbound(orchestrator)} dependencies, the widest assembly point in the scan."
            )

        if parsed_files:
            heaviest = max(parsed_files, key=lambda f: f.get("file_impact", 0.0) or 0.0)
            lines.append(
                f"- **Heaviest artifact:** `{heaviest.get('path', 'unknown')}` at magnitude "
                f"{heaviest.get('file_impact', 0.0)} (structural weight, not risk)."
            )

        lines.append(
            "- **How to read this brief:** section 11 ranks artifacts by structural magnitude with a blast-radius "
            "line each; section 7 has the full dependency graph. The surface vectors in section 6 describe what is "
            "present in a file, not the probability of a defect -- Appendix A has the equations and the validation "
            "record behind that distinction."
        )
        lines.append("")
        return lines

    def _lexicon_lines(self) -> list[str]:
        """The vector lexicon and the non-predictive disclaimer (#3113).

        Was section 2, ~75 lines of formula exposition sitting between the
        reader and every finding in the brief. #3113 asked for it to be
        KEPT but moved: the honesty is an asset and deliberately survives
        verbatim -- it is simply no longer the first thing a reader wades
        through to reach the dependency story.
        """
        lines: list[str] = []
        # --- APPENDIX A (was section 2): the vector lexicon ---
        lines.append("## APPENDIX A. STRUCTURAL SURFACE LEXICON (EQUATIONS & CONTEXT)")
        lines.append(
            "> **How the SAST Engine Calculates the Structural Surface Profile (Lower 0 - Higher Surface Presence 100%):**"
        )
        lines.append(
            "> Most scores use a Sigmoid curve based on density (Hits / LOC) to prevent massive files from mathematically hiding their flaws. These 13 vectors are activity/content surface meters -- they describe what is present in a file, not the probability of a defect. The temporal-crucible validation record (gitgalaxy#2982, ~3,550 scanned snapshots, two repositories, pre-registered) tested the per-file-standing-risk claim to exhaustion and found it does not hold; see docs/vectors.md for the full record and gitgalaxy#2991 for the rename this drove. `risk_*` names remain the underlying column/key names for schema compatibility -- see the 'formerly' aliases below."
        )
        lines.append("> ")
        lines.append(
            "> 1. **Complexity Load** (formerly Cognitive Load Exposure)**:** Measures the mental effort required for a developer to read and understand the file. `Density(Branches + (Flux * 2) + Async/Danger)` mitigated by `Doc Coverage`."
        )
        lines.append(
            "> 2. **Guard Balance** (formerly Error & Exception Risk Exposure)**:** Measures structural integrity and resilience against runtime errors. `Net Exposure = (Danger + Safety_Neg + Flux) - (Safety + Tests + Docs)`."
        )
        lines.append(
            "> 3. **Debt Markers** (formerly Tech Debt Exposure)**:** Measures the density of developer-annotated structural stress. `Density(TODOs [1x] + FIXMEs/Hacks [3x] + Empty Stubs [0.5x])`."
        )
        lines.append(
            "> 4. **Test Surface** (formerly Verification Risk Exposure)**:** Evaluates test coverage by comparing a function's structural complexity against the scope of the tests validating it."
        )
        lines.append(
            "> 5. **Connectivity** (formerly API Risk Exposure)**:** Measures the public surface area of a module. `Ratio(API Hits / Total Functions & Classes)`."
        )
        lines.append(
            "> 6. **Concurrency Surface** (formerly Concurrency Risk Exposure)**:** Measures the density of asynchronous operations, threading, and parallel execution logic."
        )
        lines.append(
            "> 7. **Mutation Surface** (formerly State Flux Risk Exposure)**:** Measures the frequency of data mutation and variable reassignment."
        )
        lines.append(
            "> 8. **Dead Code Surface** (formerly Commented Logic (dead code))**:** Measures the presence of abandoned, commented-out logic blocks."
        )
        lines.append(
            "> 9. **Spec Alignment** (formerly Spec Match Risk Exposure)**:** Measures how closely code aligns with formal specifications or architectural requirements."
        )
        lines.append(
            "> 10. **Historical Stability** (formerly Stability; predictive layer, promotion pending #2987)**:** Measures the recency of edits relative to the repository's entire lifespan. Part of the family the validation record actually supports as predictive -- currently ablated to zero in every scan (`GITGALAXY_DISABLE_GIT_HISTORY`, temporal-crucible#29)."
        )
        lines.append(
            "> 11. **Historical Churn** (formerly Deep Churn; predictive layer, promotion pending #2987)**:** Measures the historical volatility and frequency of modification. Same predictive-layer status and ablation caveat as Historical Stability above."
        )
        lines.append(
            "> 12. **Documentation Surface** (formerly Documentation Risk Exposure)**:** Of the units extracted from a file, the weight-share a reader cannot recover from documentation -- public units count double, runtime-dynamic units count more, and a folder-level documentation umbrella shields the whole file. A ratio over units, not a density over lines; files with no extracted units have no value."
        )
        lines.append(
            "> 13. **Indentation Consistency:** Measures formatting alignment (Tabs vs. Spaces). Provided for codebase standardization context, not a functional risk."
        )
        lines.append("> ")
        lines.append("> **--- THE SECURITY & VULNERABILITY LENS ---**")
        lines.append(
            "> 14. **Obfuscation & Evasion Risk:** Measures the density of obfuscated logic, packed strings, and non-standard encoding."
        )
        lines.append(
            "> 15. **Logic Bomb / Sabotage Risk:** Measures condition-heavy execution leading to destructive OS, memory, or process commands."
        )
        lines.append(
            "> 16. **Injection Surface Risk Exposure:** Measures external network/I/O input flowing directly into dynamic execution contexts (XSS, SQLi, RCE)."
        )
        lines.append(
            "> 17. **Memory Corruption Risk Exposure:** Measures the density of raw pointer math and manual memory allocations (Buffer Overflows, UAF)."
        )
        lines.append(
            "> 18. **Credential Material** (formerly Secrets Risk Exposure)**:** Measures the presence of hardcoded credentials exposed to logs or globals."
        )
        lines.append("> ")
        lines.append("> **--- STRUCTURAL MAGNITUDE (NOT RISK) ---**")
        lines.append(
            "> **19. Function Magnitude (Impact Score):** Measures the physical footprint and 'heaviness' of a specific function. `((BranchHits + 1) * (Args + 1) + (0.05 * LOC)) * 10`. This is NOT a risk score."
        )
        lines.append(
            "> **20. File Magnitude (Total Impact):** Measures the total structural impact of a file. `Sum(Function Impacts) + API + Concurrency + Flux + (LOC / 50)`. This is NOT a risk score."
        )
        lines.append("")
        return lines

    def _idiom_wrapper_lines(self, parsed_files: list[dict[str, Any]]) -> list[str]:
        """Project-local idiom wrappers (#3313 step 3) -- ABSENT unless one resolved.

        A literal rule counts calls to a primitive by name, so a project's own
        helper (`wrf_error_fatal`, curl's `curlx_malloc`) hides every call site
        behind it. This names the busiest wrappers so a reader does not mistake a
        low literal count for an absence. Top 12 by call sites, one line each.
        """
        rows = [w for f in parsed_files for w in (f.get("idiom_wrappers") or [])]
        if not rows:
            return []
        # #3313 step 4: repo-wide literal vs wrapper-aware totals per rule.
        totals = {}
        for rule in sorted({w.get("rule") for w in rows if w.get("rule")}):
            literal = sum(int((f.get("equations") or {}).get(rule, 0) or 0) for f in parsed_files)
            wrapped = sum(int((f.get("wrapped_sites") or {}).get(rule, 0) or 0) for f in parsed_files)
            totals[rule] = (literal, wrapped)
        rows.sort(key=lambda w: (-int(w.get("call_sites", 0) or 0), w.get("name") or "", w.get("rule") or ""))
        lines = ["## 14. PROJECT IDIOM WRAPPERS (Hidden Literal Vocabulary)"]
        lines.append(
            "> **AI CONTEXT:** Project-local helpers that wrap a literal primitive (print, abort, "
            "allocation). Their call sites are NOT in the literal signal counts above -- read a low "
            "`debug_prints`/`panics_and_aborts`/`memory_alloc` count together with this list. Full "
            "detail in `wrapper_data`.\n"
        )
        lines.extend(
            f"- **`{rule}`:** {literal} literal sites + {wrapped} sites through wrappers = {literal + wrapped}"
            for rule, (literal, wrapped) in totals.items()
        )
        lines.append("")
        lines.extend(
            f"- `{w.get('name')}` ({w.get('kind')}, {w.get('rule')}, {w.get('via')}): "
            f"{w.get('call_sites', 0)} call sites in {w.get('calling_files', 0)} files -- `{w.get('path')}`"
            for w in rows[:12]
        )
        if len(rows) > 12:
            lines.append(f"*(+{len(rows) - 12} more in `wrapper_data`.)*")
        lines.append("")
        return lines

    def _mainframe_facts_lines(self, parsed_files: list[dict[str, Any]]) -> list[str]:
        """The Named System Facts section (#3200/#3201/#3246) -- ABSENT unless a
        file carries them.

        These are the named mainframe relations/schemas the per-file signal
        counts flatten: the call graph, the dataset boundary, and DATA DIVISION
        record layouts. They exist only for COBOL/JCL programs, so for the vast
        majority of repositories this section renders nothing at all -- an
        occasional, opt-in section keyed purely on data presence (the same way
        the macro-network topology section only appears when there is a graph).

        Token-conscious like the rest of the brief: per file it summarises the
        distinct call targets, the DD/dataset bindings, and the record layout
        ROOTS with a field count -- never the full item tree (a single COBOL
        program can carry hundreds of items). Files are capped and ordered by
        fact volume, the same top-N discipline sections 7-11 use.
        """

        def _volume(f: dict[str, Any]) -> int:
            return (
                len(f.get("call_sites") or [])
                + len(f.get("dataset_bindings") or [])
                + len(f.get("record_layouts") or [])
                + len(f.get("sql_tables") or [])  # #3344
            )

        carriers = sorted((f for f in parsed_files if _volume(f) > 0), key=_volume, reverse=True)
        if not carriers:
            return []

        total_calls = sum(len(f.get("call_sites") or []) for f in carriers)
        total_ds = sum(len(f.get("dataset_bindings") or []) for f in carriers)
        total_items = sum(len(f.get("record_layouts") or []) for f in carriers)

        lines = ["## 13. MAINFRAME SYSTEM FACTS (Named Relations & Record Layouts)"]
        lines.append(
            "> **AI CONTEXT:** Named mainframe relations the structural signal counts flatten -- "
            "the call graph (`CALL`/CICS `LINK`·`XCTL`/JCL `EXEC PGM=`), the dataset boundary "
            "(`SELECT…ASSIGN` + `OPEN` modes, JCL `DD`→dataset), and record layouts (COBOL DATA "
            "DIVISION items, PL/I `DECLARE`d structures). "
            "These are the schema of the system: use them to trace which program runs which, which "
            "dataset a job binds, and the shape of the records that flow between them. Extracted by "
            "the engine (`core/mainframe_boundary.py`) and carried in the master DB "
            "(`call_site_data`/`dataset_data`/`record_data`); resolution to files is redone per scan.\n"
        )
        lines.append(
            f"- **Coverage:** `{len(carriers)}` files carry mainframe facts -- "
            f"`{total_calls}` call sites, `{total_ds}` dataset bindings, `{total_items}` record items.\n"
        )

        # #3344: named only when present, so a scan without DB2 declarations is unchanged.
        total_sql = sum(len(f.get("sql_tables") or []) for f in carriers)
        if total_sql:
            lines.append(
                f"- **DB2 schemas:** `{total_sql}` columns of `EXEC SQL DECLARE ... TABLE` "
                "(inline or DCLGEN members), full shape in `sql_table_data`.\n"
            )

        for f in carriers[:20]:
            path = f.get("path", "UNK")
            lang = f.get("lang_id", "UNK").upper()
            lines.append(f"### `{path}` ({lang})")

            calls = f.get("call_sites") or []
            if calls:
                seen: list[str] = []
                for c in calls:
                    label = f"{c.get('verb', 'CALL')} {c.get('operand') or c.get('target') or '?'}".strip()
                    if label not in seen:
                        seen.append(label)
                more = f" … (+{len(seen) - 12})" if len(seen) > 12 else ""
                lines.append(f"- **Calls:** {', '.join(f'`{s}`' for s in seen[:12])}{more}")

            datasets = f.get("dataset_bindings") or []
            if datasets:
                parts = []
                for d in datasets:
                    dd = d.get("dd_name") or d.get("internal_name") or "?"
                    if d.get("dsn"):  # a JCL DD -> dataset binding
                        parts.append(f"{dd}→{d['dsn']}")
                    else:  # a COBOL SELECT with its OPEN modes
                        modes = "/".join(d.get("modes") or []) or "declared"
                        parts.append(f"{dd}({modes})")
                more = f" … (+{len(parts) - 12})" if len(parts) > 12 else ""
                lines.append(f"- **Datasets:** {', '.join(f'`{p}`' for p in parts[:12])}{more}")

            items = f.get("record_layouts") or []
            if items:
                # Field counts per top-level record (01/77 or FD-bound), by
                # walking parent_ordinal to the root -- roots are the schema, the
                # full item tree is in record_data for anything that needs it.
                by_ord = {it.get("ordinal"): it for it in items}

                # `_by` is bound as a default arg (not captured) so the closure is
                # tied to THIS file's item map, not the loop variable (ruff B023).
                def _root(it: dict[str, Any], _by: dict = by_ord) -> dict[str, Any]:
                    guard = 0
                    while it.get("parent_ordinal") is not None and it["parent_ordinal"] in _by and guard < 1000:
                        it = _by[it["parent_ordinal"]]
                        guard += 1
                    return it

                # Keyed by ordinal, which is Any off a payload dict -- dict[Any, int]
                # so the ordinal key type does not fight mypy.
                counts: dict[Any, int] = {}
                for it in items:
                    root = _root(it)
                    counts[root.get("ordinal")] = counts.get(root.get("ordinal"), 0) + 1
                roots = sorted(
                    (by_ord[o] for o in counts),
                    key=lambda r: counts[r.get("ordinal")],
                    reverse=True,
                )
                labels = []
                for r in roots[:12]:
                    name = r.get("name", "?")
                    fd = f"⟵{r['fd_name']}" if r.get("fd_name") else ""
                    labels.append(f"{name}{fd} ({counts[r.get('ordinal')]})")
                more = f" … (+{len(roots) - 12} more)" if len(roots) > 12 else ""
                lines.append(
                    f"- **Record layouts ({len(items)} items):** {', '.join(f'`{lbl}`' for lbl in labels)}{more}"
                )
            # #3344: DB2 DECLARE TABLE schemas -- table name + column count only.
            sql_cols = f.get("sql_tables") or []
            if sql_cols:
                per_table: dict[str, int] = {}
                for c in sql_cols:
                    per_table[c.get("table") or "?"] = per_table.get(c.get("table") or "?", 0) + 1
                sql_labels = [f"`{t} ({n} cols)`" for t, n in per_table.items()]
                lines.append(f"- **DB2 tables declared:** {', '.join(sql_labels[:12])}")
            lines.append("")

        if len(carriers) > 20:
            lines.append(
                f"*(+{len(carriers) - 20} more files with mainframe facts; full detail in `record_data`/`call_site_data`/`dataset_data`.)*"
            )
            lines.append("")
        return lines

    def _build_markdown(
        self,
        parsed_files: list[dict[str, Any]],
        unparsable_files: list[dict[str, Any]],
        summary: dict[str, Any],
        session_meta: dict[str, Any],
        forensic_report: dict[str, Any],
    ) -> str:
        """Constructs a high-density, context-rich Markdown brief for LLM agents."""
        target = session_meta.get("target", "Project")
        sum_data = summary.get("summary", {})
        comp = summary.get("composition", {})
        git_audit = session_meta.get("git_audit", {})

        total_excluded = len(unparsable_files)
        visible_count = sum_data.get("verified_files", len(parsed_files))

        lines = []
        lines.append(f"# ARCHITECTURAL_BRIEF: {target}")
        lines.append(
            "> INSTRUCTION: Deterministic Syntactic Analysis. Base architectural insights on Structural Magnitude, Extracted Signatures, and Risk overlays.\n"
        )

        # --- 0. FORENSIC TRACEABILITY ---
        lines.append("## 0. FORENSIC TRACEABILITY")
        lines.append("| Metadata | Value |")
        lines.append("|---|---|")
        # This brief is committed to docs/gitgalaxy_architecture_brief.md by a
        # scheduled CI scan of main. Only fields that change when the repo's
        # *architecture* changes belong here -- anything that varies between two
        # scans of the same commit (Timestamp, Scan Duration, the absolute
        # Target Path, the current Git Branch, the HEAD commit hash) made every
        # scan produce a diff, and its PR auto-merges, so a per-scan field was a
        # ~21-commits/day treadmill. Freshness lives in `git log` of the file.
        lines.append(f"| **Engine** | `{session_meta.get('engine', 'Unknown')}` |")
        lines.append(f"| **Git Remote** | `{git_audit.get('remote_url', 'N/A')}` |")
        lines.append(
            f"| **Zero-Dependency Mode** | `{'ACTIVE (Degraded Precision)' if session_meta.get('zero_dependency_mode') else 'Inactive (Full Precision)'}` |"
        )
        # Archetype-brain provenance (#3124). Static per engine version -- a brain
        # changes only when it is refrozen, never between two scans of the same
        # commit -- so it satisfies section 0's "no per-scan field" rule (the
        # constraint documented at the top of this method) while making every
        # composition-archetype verdict traceable to the corpus that produced it.
        for _label, _brain in (
            ("File Archetype Brain", config.FILE_ARCHETYPE_BRAIN),
            ("Repo Archetype Brain", config.REPO_ARCHETYPE_BRAIN),
        ):
            _p = (_brain or {}).get("provenance") or {}
            if _p:
                lines.append(
                    f"| **{_label}** | corpus `{_p.get('corpus', '?')}` @ `{_p.get('corpus_sha256', '?')}` · "
                    f"trainer `{_p.get('trainer_commit', '?')}` · engine `{_p.get('engine_commit', '?')}` · "
                    f"contract `{_p.get('feature_contract_sha', '?')}` · trained `{_p.get('trained_at', '?')}` |"
                )
            elif _brain:
                lines.append(f"| **{_label}** | `unversioned (no provenance baked -- see #3124)` |")
        lines.append("")

        if session_meta.get("zero_dependency_mode"):
            lines.append("> **⚠️ ZERO-DEPENDENCY MODE ACTIVE:**")
            missing = [pkg for pkg, gone in session_meta.get("missing_dependencies", {}).items() if gone]
            lines.append(
                f"> Optional engines missing during this scan: {', '.join(f'`{p}`' for p in missing) or 'unknown'}. "
                "Metrics that need them were NOT computed -- shown as `n/a` or omitted, and no value shown for them "
                "is a measurement: Token Mass and Financial Read Cost (`tiktoken`); AI threat classification "
                "(`xgboost`/`pandas`/`numpy`). Every graph metric (PageRank / Blast Radius, the centralities, the "
                "repo network table, connection counts) is computed natively and matches full precision. Do not "
                "infer values for the missing metrics."
            )
            lines.append("")

        # ---> HARVEST AI THREAT SCORES <---
        ml_threats = []
        for s in parsed_files:
            score_val, score_str = self._parse_threat_score(s)
            if s.get("is_ml_threat", False) or score_val >= 50.0:
                ml_threats.append((s, score_val, score_str))

        ml_threats.sort(key=lambda x: x[1], reverse=True)

        lines.append("## 0.5 AI THREAT AUDIT STATUS")
        if ml_threats:
            lines.append("> **🚨 ML_CONFIRMED_THREAT_DETECTED**")
            lines.append(f"> XGBoost Structural Signatures model identified {len(ml_threats)} malicious artifacts.")
        else:
            lines.append("> **✅ SECURE_NO_THREATS_DETECTED**")
            lines.append("> XGBoost Structural Signatures model found no malicious artifacts.")
        lines.append("")

        # --- 1. EXECUTIVE SUMMARY (#3113: answer first) ---
        lines.extend(self._executive_summary_lines(parsed_files, sum_data, comp))

        # --- 1.5 CRITICAL SYSTEM INSTRUCTIONS ---
        lines.append("## 1.5 SYSTEM ROLE & PHILOSOPHY")
        lines.append(
            "> You are a Senior Technical Storyteller and Codebase Architect. GitGalaxy has translated the non-visual architecture of this repository into measurable Structural Signatures (regex-derived counts, not an AST or compiler pass). Your job is to weave those signatures into a coherent, factual narrative about how this system is built -- its architecture, design patterns, and complexity -- not to render a verdict."
        )
        lines.append("> ")
        lines.append("> **CORE DIRECTIVES:**")
        lines.append(
            "> 1. **Narrate the Architecture, Don't Judge the Author:** Frame every observation as a blameless description of the system's physical reality. A high Structural Surface Profile reading (formerly called Risk Exposure; e.g., Complexity Load, formerly Cognitive Load Exposure) describes where the architecture may be drifting into fragile territory, not developer incompetence -- it is a prompt to investigate, never a verdict. These are activity/content surface meters, not defect-probability estimates (gitgalaxy#2991, evidence in #2982) -- describe what is there, don't imply it predicts a bug."
        )
        lines.append(
            "> 2. **The Physical Reality Rule:** Base your narrative strictly on the provided Structural Signatures and the numbers derived from them. Do not hallucinate meaning, and do not restate a heuristic's raw label (e.g. a 'Logic Bomb' or 'O(2^N)' flag) as a confirmed finding of malice or a guaranteed defect -- explain what the signature actually measures, weave it into the story of the file, and let the reader draw their own conclusion."
        )
        lines.append(
            "> 3. **Risk vs. Defense:** Code is a balance. A file with high `flux` (state mutation) is risky unless balanced by `freeze_hits` (immutability). High `danger` is brittle unless wrapped in `safety`. Tell that balance as part of the narrative, not as an isolated alarm."
        )
        lines.append("> ")
        lines.append("> **THE STRUCTURAL SIGNATURE LEXICON:**")
        lines.append(
            "> * **Structure & Mass:** `branch` (splits), `linear` (paths), `args` (coupling), `func_start` (entry points)."
        )
        lines.append(
            "> * **Risk & Volatility:** `danger` (dynamic execution), `flux` (state mutation), `graveyard` (commented-out logic), `safety_neg` (security bypasses)."
        )
        lines.append(
            "> * **Architecture & Domain:** `io` (network latency), `concurrency` (async orchestration), `api` (public surface), `import` (dependencies)."
        )
        lines.append(
            "> * **Defensive Guardrails:** `safety` (Error handling), `freeze_hits` (immutability), `cleanup` (state destruction)."
        )

        # --- 2. (MOVED) VECTOR LEXICON -> APPENDIX A ---
        # #3113: the 13-point equation exposition used to sit here, ahead of
        # every actual finding. It is unchanged and still in this brief --
        # see _lexicon_lines(), emitted as Appendix A at the end. The pointer
        # below exists so a reader going in order is not left wondering what
        # happened to section 2.
        lines.append(
            "> *(Section 2, the structural-surface lexicon and its equations, is now **Appendix A** at the end "
            "of this brief -- the findings come first.)*"
        )
        lines.append("")
        # --- 3. MACRO ECOSYSTEM ---
        lines.append("## 3. MACRO STATE")
        lines.append("| Metric | Value |")
        lines.append("|---|---|")
        lines.append(f"| Total Artifacts | {sum_data.get('total_files', 0)} |")
        lines.append(f"| Analyzed Artifacts (Scanned) | {visible_count} |")
        lines.append(f"| Excluded Artifacts (Unparsable data, binaries, unsupported formats) | {total_excluded} |")
        lines.append(f"| Total LOC | {sum_data.get('total_loc', 0)} |")
        lines.append(f"| Volatility Index | {sum_data.get('volatility_index', 0.0)} |")
        lines.append(f"| % Scanned of codebase = | {sum_data.get('Percent_Visible', 0)}% |")
        lines.append(f"| Dominant Lang | {sum_data.get('dominant_language', 'UNK').upper()} |")
        lines.append("")

        # --- 3.5 MACRO-NETWORK TOPOLOGY ---
        net_macro = summary.get("network_macro", {})
        if net_macro:
            lines.append("## 3.5 MACRO-NETWORK TOPOLOGY (Resilience & Coupling)")
            lines.append("| Metric | Value | Interpretation |")
            lines.append("|---|---|---|")

            # #3027 (and #473's contract): None = not computed -- failed, or past
            # its work budget. Render it as such; `or 0.0` here used to print
            # "Modularity 0.0 / Cyclic Density 0.0%" for a scan that measured nothing.
            def _macro(key: str, fmt: Any = str) -> str:
                value = net_macro.get(key)
                return "n/a (not computed)" if value is None else fmt(value)

            lines.append(
                f"| Modularity | {_macro('modularity')} | High = Clean micro-boundaries. Low = Spaghetti coupling. |"
            )
            lines.append(
                f"| Assortativity | {_macro('assortativity')} | Positive = Resilient core. Negative = Fragile single-points-of-failure. |"
            )
            lines.append(
                f"| Cyclic Density | {_macro('cyclic_density', lambda v: f'{v * 100:.1f}%')} | % of files trapped in dependency loops (Static Friction). |"
            )
            lines.append(
                f"| Avg Path Length | {_macro('avg_path_length')} | Mean import hops from a file to each file it transitively depends on. Higher = Longer dependency chains. |"
            )
            lines.append(
                f"| Articulation Pts | {_macro('articulation_points')} | Number of single files that, if removed, shatter the network. |"
            )
            lines.append("")

        # --- 4. LINGUISTIC COMPOSITION ---
        lines.append("## 4. COMPOSITION")
        if comp:
            lines.append("| Lang | Files | LOC | Share |")
            lines.append("|---|---|---|---|")
            total_visible = max(visible_count, 1)
            for lang, stats in sorted(comp.items(), key=lambda x: x[1].get("files", 0), reverse=True):
                pct = (stats.get("files", 0) / total_visible) * 100
                lines.append(f"| {lang.upper()} | {stats.get('files', 0)} | {stats.get('loc', 0)} | {pct:.1f}% |")
        lines.append("")

        # --- 4.5 REPOSITORY ECOSYSTEM BASELINE ---
        lines.append("## 4.5 REPOSITORY ECOSYSTEM BASELINE (GLOBAL ARCHITECTURE)")
        macro = summary.get("repo_macro_species", {})
        macro_name = macro.get("name", "Unclassified")
        z_score = macro.get("z_score", 0.0)

        lines.append(f"> **Assigned Ecosystem Baseline:** `{macro_name}`")
        lines.append(f"> **Architectural Drift Z-Score:** `{z_score}`")

        # Composition archetype (function-stoichiometry taxonomy): repo archetype + the
        # file-archetype mix that composes it.
        repo_comp = sum_data.get("repo_composition_archetype")
        if repo_comp:
            rz = sum_data.get("repo_composition_z", 0.0) or 0.0
            lines.append(
                f"> **Composition Archetype:** `{repo_comp}` (z {rz:+.2f}; from the repo's file-archetype mix)"
            )
        fcd = sum_data.get("file_composition_distribution", {})
        fcd_total = sum(fcd.values())
        if fcd_total:
            top = list(fcd.items())[:5]
            share = ", ".join(f"{fa} {round(100 * ct / fcd_total)}%" for fa, ct in top)
            lines.append(f"> **File Composition:** {share}")

        if z_score > 2.0:
            lines.append(
                "> **⚠️ UNIQUE INTERPRETATION:** This repository has a high Z-Score. While it maps closest to this archetype, its internal structure is a highly unique or hybrid interpretation of the pattern."
            )
        elif z_score < -1.0:
            lines.append(
                "> **✅ STANDARD INTERPRETATION:** This repository has a negative Z-Score, meaning it is a textbook, highly standard interpretation of this archetype's structural patterns."
            )
        else:
            lines.append(
                "> **ℹ️ TYPICAL INTERPRETATION:** This repository falls within standard variance (Z-Score between -1.0 and 2.0), representing a typical implementation of this archetype."  # noqa: RUF001
            )
        lines.append("")

        lines.append("## 4.6 FILE ARCHETYPES & STATIC ASSETS")
        fingerprint = summary.get("ecosystem_fingerprint", {})
        ml_clusters = fingerprint.get("ml_clusters", {})
        static_mass = fingerprint.get("static_mass", {})

        if ml_clusters:
            lines.append("### Active Execution Logic (ML Clusters)")
            lines.append("| Archetype | Count | Repo % |")
            lines.append("|---|---|---|")
            for arch, data in ml_clusters.items():
                lines.append(f"| {arch} | {data['count']} | {data['pct']}% |")
            lines.append("")

        if static_mass:
            lines.append("### Inert Structural Mass (Static Categories)")
            lines.append("| Category | Count | Repo % |")
            lines.append("|---|---|---|")
            for arch, data in static_mass.items():
                lines.append(f"| {arch} | {data['count']} | {data['pct']}% |")
            lines.append("")

        # --- 5. EXCLUDED ARTIFACTS ---
        lines.append("## 5. EXCLUDED ARTIFACTS (Unparsable or Shielded Files)")
        lines.append(f"*Total Excluded Artifacts: {total_excluded}*\n")

        comp_breakdown = summary.get("unparsable_files", {}).get("composition_by_extension_and_reason", {})

        if comp_breakdown:
            lines.append("**Composition by Extension & Reason:**")
            for ext, reasons in list(comp_breakdown.items())[:15]:
                clean_reasons = []
                for rsn, count in list(reasons.items())[:3]:
                    safe_rsn = (
                        rsn.replace("Unparsable", "Unrecognized Syntax")
                        .replace("Structural Saturation", "Dense Structure")
                        .replace("Necrosis", "Parser Bypass")
                        .replace("Blocked", "Excluded")
                    )
                    clean_reasons.append(f"{count}x {safe_rsn.strip()}")

                reason_str = ", ".join(clean_reasons)
                lines.append(f"- `{ext}`: {reason_str}")
        lines.append("")

        # --- 6. RISK DISTRIBUTIONS ---
        lines.append("## 6. STRUCTURAL SURFACE PROFILE (formerly Risk Exposure) ANALYSIS (0-100%)")
        lines.append("| Structural Surface Vector | Min | Max | Mean | Med | Mode |")
        lines.append("|---|---|---|---|---|---|")

        schemas = getattr(config, "RECORDING_SCHEMAS", {})
        exposure_labels = schemas.get("EXPOSURE_LABELS", {})

        for i, risk_slug in enumerate(self.RISK_SCHEMA):
            # #3111: an unmeasured vector is omitted from the table entirely.
            # Printing its slot would report 0.0 across the repo, which reads
            # as "perfectly aligned" -- the opposite of "not measured".
            if risk_slug in self.inactive_vectors:
                continue
            vals = [s.get("risk_vector", [])[i] for s in parsed_files if len(s.get("risk_vector", [])) > i]
            old_label = exposure_labels.get(risk_slug, risk_slug.replace("_", " ").title())
            risk_label = self._surface_label(risk_slug, old_label)
            # #3114: mark the coverage-family rows in the table itself, so the
            # reframing is visible at the point of reading and not only in the
            # ranked-file section that now excludes them.
            if risk_slug in self.CONTEXT_VECTORS:
                risk_label = f"{risk_label} _(coverage)_"

            if vals:
                v_min, v_max = round(min(vals), 1), round(max(vals), 1)
                v_mean, v_med = (
                    round(statistics.mean(vals), 1),
                    round(statistics.median(vals), 1),
                )
                try:
                    v_mode = round(statistics.mode(vals), 1)
                except statistics.StatisticsError:
                    v_mode = "N/A"
                lines.append(f"| {risk_label} | {v_min} | {v_max} | {v_mean} | {v_med} | {v_mode} |")
            else:
                lines.append(f"| {risk_label} | - | - | - | - | - |")
        lines.append("")

        # #3114 / #3111: say plainly what the table does and does not contain.
        for ctx_slug, ctx_reason in self.CONTEXT_VECTORS.items():
            ctx_label = self._surface_label(ctx_slug, exposure_labels.get(ctx_slug, ctx_slug))
            lines.append(
                f"> `{ctx_label}` is **{ctx_reason}**. It is reported for context beside program length, and is "
                "deliberately excluded from the ranked-file drivers in this brief: it measures the share of a "
                "file's unit weight a reader cannot recover from documentation, so on a codebase that documents "
                "little it sits near ceiling everywhere and describes the repo rather than distinguishing files "
                "within it."
            )
        optional_vectors = getattr(config, "OPTIONAL_VECTORS", {})
        for off_slug in sorted(self.inactive_vectors):
            off_label = self._surface_label(off_slug, exposure_labels.get(off_slug, off_slug))
            # Derive the CLI spelling from the config key the vector is gated
            # on, so a second optional vector needs no edit here.
            flag = "--" + optional_vectors.get(off_slug, off_slug).lower().replace("_", "-")
            lines.append(
                f"> `{off_label}` was **not measured** on this scan and is therefore absent above rather "
                f"than reported as 0 (which would assert full alignment). Enable it with `{flag}` if this "
                "codebase uses the corresponding convention."
            )
        if self.CONTEXT_VECTORS or self.inactive_vectors:
            lines.append("")

        # --- 6b. SURFACE FAMILY PROFILE (gitgalaxy#2994, Tier 1/2/3) ---
        # Display-only: nothing here is golden-mastered (section 6 above
        # reads risk_vector, the audit-recorder's hashed contract; this
        # reads telemetry["surface_families"/"surface_percentiles"/
        # "surface_relations"], which audit_recorder never touches).
        lines.append("## 6b. SURFACE FAMILY PROFILE (Tier 1/2/3 -- gitgalaxy#2994)")
        lines.append(
            "> Percentile columns elsewhere in this brief that come from the Tier-2 snapshot "
            'percentiles are SNAPSHOT-RELATIVE: "87" means this file\'s value sits at the 87th '
            "percentile of THIS repo's files for that surface -- true by construction (Hazen "
            "average-rank), not a calibrated 0-100 risk threshold like the section 6 sigmoid "
            "scores above. An all-zero surface across the whole repo reads as 0.0 for every "
            "file, never a false-median 50."
        )
        lines.append("| Family | Repo Total | Files w/ Signal | P90 File Value | Top File |")
        lines.append("|---|---|---|---|---|")

        for family in self.SURFACE_FAMILIES:
            per_file = [
                (f.get("telemetry", {}).get("surface_families", {}).get(family, 0), f.get("path", "unknown"))
                for f in parsed_files
            ]
            if per_file:
                total = sum(v for v, _ in per_file)
                files_with_signal = sum(1 for v, _ in per_file if v > 0)
                sorted_vals = sorted(v for v, _ in per_file)
                p90_idx = max(0, min(len(sorted_vals) - 1, round(0.9 * (len(sorted_vals) - 1))))
                p90_val = sorted_vals[p90_idx]
                top_val, top_path = max(per_file, key=lambda pair: pair[0])
                top_display = f"`{top_path}`" if top_val > 0 else "-"
                lines.append(f"| {family} | {total} | {files_with_signal} | {p90_val} | {top_display} |")
            else:
                lines.append(f"| {family} | - | - | - | - |")
        lines.append("")

        guard_balance_vals = [
            f.get("telemetry", {}).get("surface_relations", {}).get("guard_balance_ratio", 0.0) for f in parsed_files
        ]
        alloc_cleanup_vals = [
            f.get("telemetry", {}).get("surface_relations", {}).get("alloc_cleanup_pairing", 0.0) for f in parsed_files
        ]
        gb_median = round(statistics.median(guard_balance_vals), 4) if guard_balance_vals else 0.0
        ac_median = round(statistics.median(alloc_cleanup_vals), 4) if alloc_cleanup_vals else 0.0
        lines.append("**Relations (repo medians):**")
        lines.append(f"- `guard_balance_ratio` (guards / (danger + 1)): **{gb_median}**")
        lines.append(f"- `alloc_cleanup_pairing` (cleanup / (memory + 1)): **{ac_median}**")
        lines.append("")

        # --- 7. ARCHITECTURAL CHOKE POINTS & DEPENDENCIES ---
        lines.append("## 7. ARCHITECTURAL CHOKE POINTS & DEPENDENCIES")

        io_idx = self.SIGNAL_SCHEMA.index("io") if "io" in self.SIGNAL_SCHEMA else -1
        if io_idx >= 0:
            top_io = sorted(
                parsed_files,
                key=lambda x: x.get("hit_vector", [])[io_idx] if len(x.get("hit_vector", [])) > io_idx else 0,
                reverse=True,
            )[:3]
            lines.append("### Top I/O Latency Risks")
            lines.extend(f"- `{s.get('path')}` (Hits: {s.get('hit_vector', [])[io_idx]})" for s in top_io)
            lines.append("")

        pillars = sorted(
            parsed_files,
            key=lambda x: x.get("telemetry", {}).get("popularity", 0),
            reverse=True,
        )[:5]
        lines.append("### Top 5 Structural Pillars (Highest 'Imported By' / Blast Radius)")
        # #2556: ranking by popularity is meaningless when the maximum is 0 --
        # the sort is stable, so an all-zero graph just emits the first five
        # files in scan order (documentation, usually) under a heading that
        # calls them "the most interconnected files". An LLM consuming this
        # brief repeats that as fact. A flat graph is a real finding; say so
        # instead of dressing scan order up as a ranking.
        if not any(f.get("telemetry", {}).get("popularity", 0) > 0 for f in pillars):
            lines.append(
                "No file in this repository is imported by another file that GitGalaxy could resolve, so there is "
                "no blast-radius ranking to report. That is itself a finding: either the codebase genuinely has no "
                "internal dependency structure (a collection of scripts, documents or configuration rather than a "
                "coupled system), or its import style is one the engine does not resolve for this language. Do not "
                "infer that any file is load-bearing from this section.\n"
            )
        else:
            lines.append(
                "These are the most interconnected files relative to the rest of this repository. On a repo with "
                "dense internal coupling, that means core load-bearing infrastructure -- changes carry real "
                "cascading-break risk. On a repo with a flatter internal architecture, the gap between #1 and #5 may "
                "be small, and this list is a weaker signal accordingly; compare the connection counts below before "
                "treating it as a verdict.\n"
            )
            for rank, file_data in enumerate(pillars, 1):
                name = file_data.get("name", "Unknown")
                path = file_data.get("path", "Unknown")
                count = file_data.get("telemetry", {}).get("popularity", 0)
                lines.append(f"{rank}. **{name}** (`{path}`) — {count} inbound connections")
        lines.append("")

        orchestrators = sorted(
            parsed_files,
            key=lambda x: len(x.get("raw_imports", [])) if isinstance(x.get("raw_imports"), list) else 0,
            reverse=True,
        )[:5]
        lines.append("### Top 5 Orchestrators (Highest 'Imports' / Fragility Index)")

        def _outbound(file_data):
            raw = file_data.get("raw_imports", [])
            return len(raw) if isinstance(raw, list) else 0

        # #2556: the same zero-guard as the pillar list above. This section had
        # the identical defect and the issue did not mention it -- with no
        # resolvable imports anywhere it called five files with 0 outbound
        # dependencies "highly coupled and fragile to API changes".
        if not any(_outbound(f) > 0 for f in orchestrators):
            lines.append(
                "No file in this repository declares an import that GitGalaxy resolved, so there is no coupling "
                "ranking to report. See the note above -- the same caveat applies.\n"
            )
        else:
            lines.append(
                "These files pull in the most external dependencies. They are highly coupled and fragile to API "
                "changes.\n"
            )
            for rank, file_data in enumerate(orchestrators, 1):
                name = file_data.get("name", "Unknown")
                path = file_data.get("path", "Unknown")
                lines.append(f"{rank}. **{name}** (`{path}`) — {_outbound(file_data)} outbound dependencies")
        lines.append("")

        import heapq

        # --- 8. CORE FUNCTION HITLIST ---
        lines.append("## 8. CORE FUNCTION HITLIST (Heaviest Functions)")
        lines.append(
            "> *Note: The 'Impact' metric below represents Structural Magnitude (complexity, arguments, and length), NOT operational risk. These are the load-bearing pillars of the logic.*\n"
        )

        all_functions: list[tuple[dict, str]] = []
        for s in parsed_files:
            file_path = s.get("path", "Unknown")
            all_functions.extend((func, file_path) for func in s.get("functions", []))

        top_impact = heapq.nlargest(10, all_functions, key=lambda x: x[0].get("impact", 0))

        if top_impact:
            for f, file_path in top_impact:
                arch = f.get("archetype", "Unclassified")
                lines.append(
                    f"- `{f.get('name')}` **({arch})** (@ `{file_path}`) -> Impact: **{f.get('impact')}** | LOC: {f.get('loc')}"
                )
                doc = f.get("docstring", "").strip()
                if doc:
                    clean_doc = " ".join(doc.split())[:150] + ("..." if len(doc) > 150 else "")
                    lines.append(f"  * *Intent:* {clean_doc}")
            # Legend: define only the archetypes that actually appear above, so the
            # inline "(archetype)" tags are self-explanatory without a full glossary.
            shown = sorted({f.get("archetype", "Unclassified") for f, _ in top_impact})
            defs = getattr(config, "FUNCTION_ARCHETYPE_DEFINITIONS", {})
            lines.append("")
            lines.append("*Function archetypes referenced above:*")
            lines.extend(f"  * **{a}**: {defs.get(a, 'n/a')}" for a in shown)
        else:
            lines.append("*No complex functions detected.*")
        lines.append("")

        # --- 9. DIRECTORY GROUPS ---
        lines.append("## 9. DIRECTORY GROUPS (Top 10 Heaviest Modules)")
        dir_groups = summary.get("directory_groups", {})
        if dir_groups:
            lines.append("| Folder Path | Files | Total Impact | Avg Complexity Load | Avg Debt Markers |")
            lines.append("|---|---|---|---|---|")

            sorted_groups = sorted(
                dir_groups.items(),
                key=lambda x: x[1].get("total_mass", 0.0),
                reverse=True,
            )[:10]

            for c_name, c_data in sorted_groups:
                mass = c_data.get("total_mass", 0.0)
                count = c_data.get("file_count", 0)
                exposures = c_data.get("avg_exposures", {})
                cog = exposures.get("cognitive_load", 0.0)
                debt = exposures.get("tech_debt", 0.0)
                lines.append(f"| `{c_name}` | {count} | {mass} | {cog}% | {debt}% |")
        else:
            lines.append("*No deep folder structures detected.*")
        lines.append("")

        # --- 10. TARGETED RISK VECTORS ---
        lines.append("## 10. TARGETED STRUCTURAL SURFACE VECTORS (formerly Risk Vectors, Top 5 by Surface)")

        debt_idx = self.RISK_SCHEMA.index("tech_debt") if "tech_debt" in self.RISK_SCHEMA else -1
        if debt_idx >= 0:
            high_debt = sorted(
                [s for s in parsed_files if len(s.get("risk_vector", [])) > debt_idx],
                key=lambda x: x.get("risk_vector", [])[debt_idx],
                reverse=True,
            )[:5]
            if high_debt and high_debt[0].get("risk_vector", [])[debt_idx] > 0:
                lines.append("### Highest Debt Markers (formerly Tech Debt; Fragile/Planned)")
                lines.extend(
                    f"- `{s.get('path')}` -> **{s.get('risk_vector', [])[debt_idx]}%** Exposure"
                    for s in high_debt
                    if s.get("risk_vector", [])[debt_idx] > 0
                )

        flux_idx = self.RISK_SCHEMA.index("state_flux") if "state_flux" in self.RISK_SCHEMA else -1
        if flux_idx >= 0:
            high_flux = sorted(
                [s for s in parsed_files if len(s.get("risk_vector", [])) > flux_idx],
                key=lambda x: x.get("risk_vector", [])[flux_idx],
                reverse=True,
            )[:5]
            if high_flux and high_flux[0].get("risk_vector", [])[flux_idx] > 0:
                lines.append("### Highest Mutation Surface (formerly State Flux; Mutation/Volatility)")
                lines.extend(
                    f"- `{s.get('path')}` -> **{s.get('risk_vector', [])[flux_idx]}%** Exposure"
                    for s in high_flux
                    if s.get("risk_vector", [])[flux_idx] > 0
                )

        orphan_idx = (
            self.SIGNAL_SCHEMA.index("unreferenced_by_name") if "unreferenced_by_name" in self.SIGNAL_SCHEMA else -1
        )
        dup_idx = self.SIGNAL_SCHEMA.index("duplicate_logic") if "duplicate_logic" in self.SIGNAL_SCHEMA else -1

        if orphan_idx >= 0 and dup_idx >= 0:
            high_slop = sorted(
                [s for s in parsed_files if len(s.get("hit_vector", [])) > max(orphan_idx, dup_idx)],
                key=lambda x: x.get("hit_vector", [])[orphan_idx] + x.get("hit_vector", [])[dup_idx],
                reverse=True,
            )[:5]

            if (
                high_slop
                and (high_slop[0].get("hit_vector", [])[orphan_idx] + high_slop[0].get("hit_vector", [])[dup_idx]) > 0
            ):
                lines.append("### Highest Design Slop (Dead & Duplicated Logic)")
                for s in high_slop:
                    o_hits = s.get("hit_vector", [])[orphan_idx]
                    d_hits = s.get("hit_vector", [])[dup_idx]
                    if o_hits > 0 or d_hits > 0:
                        lines.append(
                            f"- `{s.get('path')}` -> **{o_hits}** Orphaned Functions | **{d_hits}** Duplicates"
                        )
        lines.append("")

        # --- 10.5 AI THREAT INTELLIGENCE ---
        lines.append("## 10.5 AI THREAT INTELLIGENCE (XGBoost)")
        if ml_threats:
            lines.append(
                "> **CRITICAL THREATS DETECTED.** The following files possess the structural signatures of known vulnerabilities.\n"
            )
            cutoff = max(10, int(len(ml_threats) * 0.10))
            for i, (s, _val, string_val) in enumerate(ml_threats[:cutoff]):
                lines.append(f"{i + 1}. **`{s.get('path')}`** -> AI Confidence: **{string_val}**")
        else:
            lines.append("*No files met the threshold for malicious structural signatures.*")
        lines.append("")

        # --- 10.6 CRITICAL VULNERABILITY EXPOSURES (RULE-BASED) ---
        lines.append("## 10.6 WEAPONIZABLE SURFACE EXPOSURES (RULE-BASED SAST)")
        lines.append(
            "> Secondary Evidence: The following files tripped specific static threat signatures. Use these to explain *why* the XGBoost model flagged the files above.\n"
        )

        vuln_keys = [
            "secrets_risk",
        ]
        vuln_found = False
        for v_key in vuln_keys:
            if v_key in self.RISK_SCHEMA:
                v_idx = self.RISK_SCHEMA.index(v_key)
                v_files = sorted(
                    [
                        s
                        for s in parsed_files
                        if len(s.get("risk_vector", [])) > v_idx and s.get("risk_vector", [])[v_idx] > 0.0
                    ],
                    key=lambda x: x.get("risk_vector", [])[v_idx],
                    reverse=True,
                )

                if v_files:
                    vuln_found = True
                    old_label = exposure_labels.get(v_key, v_key.replace("_", " ").title())
                    label = self._surface_label(v_key, old_label)
                    lines.append(f"### {label}")
                    lines.extend(
                        f"- `{s.get('path')}` -> **{s.get('risk_vector', [])[v_idx]}%** Exposure" for s in v_files[:5]
                    )

        if not vuln_found:
            lines.append("*No critical vulnerabilities or security lens thresholds breached.*")
        lines.append("")

        # ======================================================================
        # 10.7 ECOSYSTEM SECURITY AUDITS
        # ======================================================================
        audits = summary.get("ecosystem_audits", {})
        lines.append("## 10.7 ECOSYSTEM SECURITY AUDITS")
        lines.append(
            "> **AI CONTEXT:** High-level perimeter defense metrics from the X-Ray, Supply Chain Firewall, and API Network Mapper."
        )
        lines.append("")

        # 1. API Network Mapper
        api = audits.get("api_mapper", {})
        if api.get("status") == "success":
            lines.append("### 📡 API Network Audit (Set Theory)")
            lines.append(
                f"- **Shadow APIs (Critical):** `{api.get('shadow_count', 0)}` undocumented endpoints actively listening."
            )
            lines.append(
                f"- **Ghost APIs (Bloat):** `{api.get('ghost_count', 0)}` endpoints documented but missing from code."
            )
            if api.get("shadow_apis"):
                lines.append("- **Known Shadow Routes:** " + ", ".join([f"`{r}`" for r in api.get("shadow_apis")[:5]]))
            lines.append("")

        # 2. X-Ray & Firewall
        xray = audits.get("xray", {})
        fw = audits.get("firewall", {})

        lines.append("### ☢️ X-Ray & 🧱 Supply Chain Firewall")
        lines.append(
            f"- **Binary Anomalies (X-Ray):** `{xray.get('anomalies_found', 0)}` (High entropy, packed payloads, or magic byte mismatches)."
        )
        lines.append(
            f"- **Blacklisted Dependencies:** `{fw.get('imports_blacklisted', 0)}` explicitly banned packages imported."
        )
        lines.append(
            f"- **Unknown Dependencies:** `{fw.get('imports_unknown', 0)}` packages imported that bypass the Zero-Trust whitelist."
        )
        lines.append("")

        # ==============================================================================

        # galaxyscope:ignore sec_high_risk_execution, sec_db_hooks
        # --- 11. (REMOVED) CUMULATIVE RISK HITLIST ---
        # ==============================================================================
        # #3112/#3113: section 11 ranked the top 10 files by the Cumulative
        # Risk composite and then reprinted archetype, magnitude and heaviest
        # functions -- all of which section 11's successor below already
        # carries for a wider set of files. Two sections answered the same
        # question ("which files deserve attention first") in two formats, and
        # the one that ranked did so on a unitless sum that #3112 removed.
        #
        # The question survives; the ranked list below is now the single
        # answer, ordered by structural magnitude and annotated with the blast
        # radius that says what a change would reach.
        # ==============================================================================

        # galaxyscope:ignore sec_high_risk_execution, sec_db_hooks
        # --- 11. RANKED ARTIFACTS (was 12; absorbs the old section 11) ---
        # ==============================================================================

        # galaxyscope:ignore sec_high_risk_execution, sec_db_hooks
        lines.append("## 11. RANKED ARTIFACTS (Top 25 by Structural Magnitude)")
        lines.append(
            "> Ranked by Structural Magnitude: the file's structural weight and centralization within the "
            "system. Magnitude is **not** a risk score and is independent of the surface vectors in section 6. "
            "Each entry carries a **Blast Radius** line stating what a change to it would reach -- that, not "
            "the vector percentages, is the actionable part.\n"
        )

        sorted_files = sorted(parsed_files, key=lambda x: x.get("file_impact", 0.0), reverse=True)[:25]

        structure_keys = {"branch", "structural_boundaries", "args", "func_start", "class_start"}
        risk_keys = {
            "high_risk_execution",
            "state_mutation",
            "dead_code",
            "safety_bypasses",
            "planned_debt",
            "fragile_debt",
            "unreferenced_by_name",
            "duplicate_logic",
        }
        arch_keys = {"io", "concurrency", "api", "import"}
        defense_keys = {"safety", "immutability_locks", "cleanup", "test", "sync_locks", "doc"}

        for s in sorted_files:
            p = s.get("path", "UNK")
            l = s.get("lang_id", "UNK").upper()
            m = s.get("file_impact", 0.0)
            loc = s.get("total_loc", 0)

            rv = s.get("risk_vector", [])
            tel = s.get("telemetry", {})

            lock_tier = s.get("lock_tier", tel.get("identity_lock_tier", 4))
            purpose = tel.get("domain_context", {}).get("purpose", "")

            ai_score_val, ai_score_str = self._parse_threat_score(s)
            threat_flag = f" | 🚨 AI THREAT: {ai_score_str}" if ai_score_val >= 50.0 else f" | AI Safe: {ai_score_str}"

            lines.append(f"### `{p}` ({l} | Tier {lock_tier}{threat_flag})")
            if purpose:
                lines.append(f"> **System Purpose:** *{purpose}*")

            arch = tel.get("archetype", "Unknown Archetype")
            g_drift = tel.get("global_drift", "N/A")
            l_arch = tel.get("local_archetype")
            l_drift = tel.get("local_drift", "N/A")

            lines.append(f"- **Global Archetype:** `{arch}` (Drift: {g_drift} IQR)")
            if l_arch and l_arch != "N/A":
                lines.append(f"- **Local Micro-Species:** `{l_arch}` (Drift: {l_drift} IQR)")

            fingerprint = tel.get("archetype_fingerprint", {})
            if fingerprint:
                fp_strs = [f"{k.split(':')[0]}: {v}" for k, v in sorted(fingerprint.items(), key=lambda x: x[1])[:3]]
                lines.append(f"- **Top Global Matches:** {', '.join(fp_strs)}")

            lines.append(
                f"- **Magnitude:** {m} | **LOC:** {loc} | **CtrlFlow:** {round(tel.get('control_flow_ratio', 0.0) * 100, 1)}% | **Authorship Centralization:** {round(tel.get('author_distribution', 0.0), 1)}%"
            )
            # #3113: state the consequence, from the dependency edges the
            # brief already computes. This is the "what does it affect" line
            # the old Primary-Risk-Drivers line never provided.
            lines.append(f"- **Blast Radius:** {self._blast_radius_sentence(s)}")

            # #3111/#3114: top surface vectors, ceiling-pinned ones excluded.
            driver_labels = self._driver_labels(rv)
            lines.append(f"- **Top Surface Vectors:** {', '.join(driver_labels) if driver_labels else 'None above 0%'}")
            coverage_labels = self._coverage_labels(rv)
            if coverage_labels:
                lines.append(f"- **Documentation Coverage:** {', '.join(coverage_labels)}")

            hv = s.get("hit_vector", [])
            struct_hits, risk_hits, arch_hits, def_hits = [], [], [], []

            for i, val in enumerate(hv):
                if val > 0 and i < len(self.SIGNAL_SCHEMA):
                    key = self.SIGNAL_SCHEMA[i]
                    hit_string = f"`{key}: {val}`"
                    if key in structure_keys:
                        struct_hits.append(hit_string)
                    elif key in risk_keys:
                        risk_hits.append(hit_string)
                    elif key in arch_keys:
                        arch_hits.append(hit_string)
                    elif key in defense_keys:
                        def_hits.append(hit_string)

            sats = sorted(s.get("functions", []), key=lambda x: x.get("impact", 0), reverse=True)[:5]
            if sats:
                lines.append("**Top Internal Functions/Classes:**")
                for sat in sats:
                    arch = sat.get("archetype", "Unclassified")
                    lines.append(f"  * `{sat.get('name')}` **({arch})** (Impact: {sat.get('impact')})")
                    doc = sat.get("docstring", "").strip()
                    if doc:
                        clean_doc = " ".join(doc.split())[:100] + ("..." if len(doc) > 100 else "")
                        lines.append(f"    * *Intent:* {clean_doc}")

            mitigations = tel.get("mitigation_telemetry", {})

            # THE FIX: Cast suppression lists to dictionary tallies to support inline galaxyscope:ignores
            if isinstance(mitigations, list):
                mitigations = dict.fromkeys(mitigations, 1)

            active_mitigations = {k: v for k, v in mitigations.items() if v > 0}
            weighted = tel.get("weighted_signals", {}) or {}
            if active_mitigations or weighted:
                lines.append("**Contextual Mitigations & Amplifications:**")
                for m_key, m_val in active_mitigations.items():
                    clean_key = m_key.replace("_", " ").title()
                    lines.append(f"* *{clean_key}:* {m_val} instances")
                # #2813: the signature lines below are raw counts; the proximity-weighted
                # figure they used to carry is listed here beside its tally.
                for w_key, w_val in weighted.items():
                    lines.append(f"* *{w_key.replace('_', ' ').title()} (weighted view):* {w_val}")

            lines.append("**Structural Signatures (Net Mitigated Signals):**")
            lines.append(f"* *Structure:* {', '.join(struct_hits) if struct_hits else 'None'}")
            lines.append(f"* *Risk/State:* {', '.join(risk_hits) if risk_hits else 'None'}")
            lines.append(f"* *Architecture:* {', '.join(arch_hits) if arch_hits else 'None'}")
            lines.append(f"* *Defense:* {', '.join(def_hits) if def_hits else 'None'}")

            outbound = s.get("raw_imports", [])
            net_mets = tel.get("network_metrics", {})
            in_d = net_mets.get("in_degree", 0)
            out_d = net_mets.get("out_degree", 0)
            # #3027: None = not computed; say so rather than print a placeholder 0.0.
            blast_rad = net_mets.get("normalized_blast_radius")
            between_score = net_mets.get("betweenness_score")
            close_score = net_mets.get("closeness_score")
            blast_rad, between_score, close_score = (
                "n/a" if v is None else v for v in (blast_rad, between_score, close_score)
            )
            eco_role = net_mets.get("ecosystem_role", "Unknown")

            out_names = ", ".join([Path(x).name for x in outbound[:8]]) + ("..." if len(outbound) > 8 else "")

            lines.append("* *Network Topology:*")
            lines.append(f"  * `Ecosystem Role:` {eco_role} | `Dependency Blast Radius (PageRank):` {blast_rad}")
            lines.append(
                f"  * `Choke Point (Betweenness):` {between_score} | `Ripple Effect (Closeness):` {close_score}"
            )
            lines.append(f"  * `Imports (Out-Degree: {out_d}):` {out_names if out_names else 'None'}")
            lines.append(
                f"  * `Imported By (In-Degree: {in_d}):` {'(Excluded from Brief to save tokens)' if in_d > 0 else 'None (Orphan / Entrypoint)'}"
            )
            lines.append("")

        # ==============================================================================

        # galaxyscope:ignore sec_high_risk_execution, sec_db_hooks
        # --- 12. ARCHITECTURAL DRIFT ANOMALIES & ANTI-PATTERNS ---
        # ==============================================================================

        # galaxyscope:ignore sec_high_risk_execution, sec_db_hooks
        lines.append("## 12. ARCHITECTURAL DRIFT ANOMALIES & ANTI-PATTERNS")
        lines.append(
            "> **AI CONTEXT:** Pay close attention to 'Anti-Pattern' files. These files blend in globally (Low Global Drift), but heavily violate the standard conventions of their native programming language (High Local Drift). 'Mixed-Responsibility' files sit perfectly between two global archetypes (Delta <= 0.9 IQR), indicating a violation of the Single Responsibility Principle.\n"
        )

        drifting_files = []
        trojan_files = []

        for s in parsed_files:
            tel = s.get("telemetry", {})

            # 1. Anti-Pattern Check
            g_drift = tel.get("global_drift", 0.0)
            l_drift = tel.get("local_drift", 0.0)

            if g_drift > 0 and l_drift > 0:
                biaxial_ratio = l_drift / g_drift
                if biaxial_ratio > 1.5:
                    trojan_files.append(
                        {
                            "file_data": s,
                            "ratio": biaxial_ratio,
                            "g_drift": g_drift,
                            "l_drift": l_drift,
                            "g_arch": tel.get("archetype"),
                            "l_arch": tel.get("local_archetype"),
                        }
                    )

            # 2. Mixed-Responsibility Architecture Check
            fingerprint = tel.get("archetype_fingerprint", {})
            if len(fingerprint) >= 2:
                sorted_archs = sorted(fingerprint.items(), key=lambda x: x[1])
                primary_arch, primary_dist = sorted_archs[0]
                secondary_arch, secondary_dist = sorted_archs[1]
                delta = secondary_dist - primary_dist

                if delta <= 0.9:
                    drifting_files.append(
                        {
                            "file_data": s,
                            "delta": delta,
                            "primary": (primary_arch, primary_dist),
                            "secondary": (secondary_arch, secondary_dist),
                        }
                    )

        if trojan_files:
            lines.append("### 🚨 Severe Anti-Patterns (Language Convention Violations)")
            trojan_files.sort(key=lambda x: x["ratio"], reverse=True)
            for t in trojan_files[:5]:
                s = t["file_data"]
                lines.append(
                    f"- `{s.get('path')}` ({s.get('lang_id', 'UNK').upper()}) | **Drift Ratio: {round(t['ratio'], 2)}x**"
                )
                lines.append(f"  * **Global Archetype:** `{t['g_arch']}` (Drift: {t['g_drift']} IQR)")
                lines.append(f"  * **Local Reality:** `{t['l_arch']}` (Drift: {t['l_drift']} IQR)")
            lines.append("")

        if drifting_files:
            from collections import defaultdict

            drift_by_cluster = defaultdict(list)

            for drift in drifting_files:
                drift_by_cluster[drift["primary"][0]].append(drift)

            for cluster_name, files in sorted(drift_by_cluster.items()):
                lines.append(f"### Mixed-Responsibility Refactoring Targets for: {cluster_name}")
                files.sort(key=lambda x: x["delta"])

                for drift in files[:5]:
                    s = drift["file_data"]
                    p = s.get("path", "UNK")
                    l = s.get("lang_id", "UNK").upper()
                    m = s.get("file_impact", 0.0)
                    sec_a, _sec_d = drift["secondary"]

                    lines.append(
                        f"- `{p}` ({l}) | Magnitude: {m} | Delta: **{round(drift['delta'], 3)} IQR** | Secondary Pull: `{sec_a}`"
                    )

                    struct_signal_hits = [
                        (self.SIGNAL_SCHEMA[i], val)
                        for i, val in enumerate(s.get("hit_vector", []))
                        if val > 0 and i < len(self.SIGNAL_SCHEMA)
                    ]
                    struct_signal_hits.sort(key=lambda x: x[1], reverse=True)
                    top_hits = ", ".join([f"{k}: {v}" for k, v in struct_signal_hits[:4]])

                    lines.append(f"  * Top Architectural Signatures: {top_hits if top_hits else 'None'}")
                lines.append("")
        else:
            lines.append("*No highly conflicted/drifting files detected within the 0.9 IQR threshold.*")
            lines.append("")

        # ==============================================================================

        # galaxyscope:ignore sec_high_risk_execution, sec_db_hooks
        # --- 13.5 STRATEGIC REFACTORING TARGETS ---
        # ==============================================================================

        # galaxyscope:ignore sec_high_risk_execution, sec_db_hooks
        lines.append("## 12.5 STRATEGIC REFACTORING TARGETS (Volatility & Authorship Centralization)")
        lines.append(
            "> **AI CONTEXT:** Use these intersections to recommend pragmatic next steps. Risk is exponentially worse when combined with high churn (frequent edits) or high authorship centralization (single points of failure).\n"
        )

        churn_idx = self.RISK_SCHEMA.index("churn") if "churn" in self.RISK_SCHEMA else -1
        if churn_idx >= 0:
            cog_idx = self.RISK_SCHEMA.index("cognitive_load")
            debt_idx = self.RISK_SCHEMA.index("tech_debt")

            hotspots = []
            for s in parsed_files:
                rv = s.get("risk_vector", [])
                if (
                    len(rv) > max(churn_idx, cog_idx, debt_idx)
                    and rv[churn_idx] > 50.0
                    and (rv[cog_idx] > 50.0 or rv[debt_idx] > 50.0)
                ):
                    hotspots.append(s)

            if hotspots:
                lines.append("### 🔥 The Hotspot Matrix (High Volatility + High Risk)")
                lines.append(
                    "These files are messy, complex, and modified frequently. They are the primary source of developer friction.\n"
                )
                hotspots.sort(key=lambda x: x.get("risk_vector", [])[churn_idx], reverse=True)
                for s in hotspots[:5]:
                    rv = s.get("risk_vector", [])
                    lines.append(
                        f"- `{s.get('path')}` -> Churn: **{rv[churn_idx]}%** | Cog Load: {rv[cog_idx]}% | Debt: {rv[debt_idx]}%"
                    )
                lines.append("")

        siloed_pillars = [
            s
            for s in parsed_files
            if s.get("telemetry", {}).get("author_distribution", 0.0) > 80.0 and s.get("file_impact", 0.0) > 50.0
        ]

        if siloed_pillars:
            lines.append("### 👤 Key Person Dependencies (High Impact + Siloed Knowledge)")
            lines.append(
                "These are massive, load-bearing files written almost entirely by a single developer. They represent severe 'Bus Factor' risk.\n"
            )
            siloed_pillars.sort(key=lambda x: x.get("file_impact", 0.0), reverse=True)
            for s in siloed_pillars[:5]:
                owner = s.get("telemetry", {}).get("ownership", "Unknown")
                silo_score = s.get("telemetry", {}).get("author_distribution", 0.0)
                lines.append(
                    f"- `{s.get('path')}` -> **{owner}** ({silo_score}% isolated ownership) | Magnitude: {s.get('file_impact')}"
                )
            lines.append("")

        # ==============================================================================

        # galaxyscope:ignore sec_high_risk_execution, sec_db_hooks
        # --- 13.8 SYSTEMIC NETWORK BOTTLENECKS (N-Dimensional Physics) ---
        # ==============================================================================

        # galaxyscope:ignore sec_high_risk_execution, sec_db_hooks
        sys_bots = forensic_report.get("systemic_bottlenecks", {})
        if any(v and v[0]["score"] > 0 for v in sys_bots.values()):
            lines.append("## 12.8 SYSTEMIC NETWORK BOTTLENECKS (N-Dimensional Topology)")
            lines.append(
                "> **AI CONTEXT:** These metrics cross-multiply Network Graph Theory against Risk Exposure to identify the exact mechanisms of runtime failure.\n"
            )

            cm = sys_bots.get("cascading_state_mutation", [])
            if cm and cm[0]["score"] > 0:
                lines.append("### ☣️ Cascading State Flux (Betweenness * State Flux)")
                lines.append(
                    "These files act as structural bridges between components, but possess highly volatile, mutating state. They cause unpredictable side-effects for all downstream consumers.\n"
                )
                lines.extend(
                    f"- `{c['path']}` -> **Severity: {c['score']}** (Bridge: {c['btw']} * Flux: {c['state_mutation']}%)"
                    for c in cm
                    if c["score"] > 0
                )
                lines.append("")

            # #370: the real bottleneck-detector key is "fragile_dependency_chain"
            # (signal_processor.py) -- "house_of_cards" was never a real key, just
            # this section's own display name mistakenly used as the lookup too.
            hoc = sys_bots.get("fragile_dependency_chain", [])
            if hoc and hoc[0]["score"] > 0:
                lines.append("### 🃏 House of Cards (Closeness * Error Risk)")
                lines.append(
                    "These files are deeply embedded (1 or 2 hops from the entire codebase) but possess high error exposure. A runtime exception here will cascade instantly across the application.\n"
                )
                lines.extend(
                    f"- `{h['path']}` -> **Severity: {h['score']}** (Embedded: {h['close']} * Error Risk: {h['err']}%)"
                    for h in hoc
                    if h["score"] > 0
                )
                lines.append("")

            bb = sys_bots.get("undocumented_critical_path", [])
            if bb and bb[0]["score"] > 0:
                lines.append("### 🙈 Opaque Critical Nodes (Dependency Blast Radius * Doc Risk)")
                lines.append(
                    "These are 'Core Architecture Nodes' that the entire ecosystem relies upon, but they lack human intent, documentation, or ownership metadata. Modifying them is flying blind.\n"
                )
                lines.extend(
                    f"- `{b['path']}` -> **Severity: {b['score']}** (Blast Radius: {b['pr']} * Doc Risk: {b['doc']}%)"
                    for b in bb
                    if b["score"] > 0
                )
                lines.append("")

        # ==============================================================================

        # galaxyscope:ignore sec_high_risk_execution, sec_db_hooks
        # --- 13. MAINFRAME SYSTEM FACTS (#3200/#3201/#3246) ---
        # Optional: renders only when a file carries named mainframe facts, so it
        # is absent from every non-mainframe brief.
        # ==============================================================================
        lines.extend(self._mainframe_facts_lines(parsed_files))

        # --- 14. PROJECT IDIOM WRAPPERS (#3313 step 3) ---
        # Optional: renders only when the scan resolved at least one wrapper.
        lines.extend(self._idiom_wrapper_lines(parsed_files))

        # ==============================================================================

        # galaxyscope:ignore sec_high_risk_execution, sec_db_hooks
        # --- 14. SYSTEM PROMPT: HOW TO RESPOND ---
        # ==============================================================================

        # galaxyscope:ignore sec_high_risk_execution, sec_db_hooks
        # #3113: the lexicon, verbatim but demoted from section 2 to here.
        # Placed before the output-format directive so that directive stays
        # the last thing the consuming model reads.
        lines.extend(self._lexicon_lines())

        lines.append("## AI SYSTEM INSTRUCTIONS (OUTPUT FORMAT)")
        lines.append(
            "> **CRITICAL TONE DIRECTIVE:** Stay in the Senior Technical Storyteller persona from Section 1. Use grounded, professional software engineering terminology (e.g., coupling, cohesion, technical debt, single responsibility) woven into a cohesive narrative -- not a dry, disconnected bullet-point audit. DO NOT use sci-fi, dramatic, or sensational jargon (e.g., 'Trojan', 'violently violates', 'parasitic', 'chimeric'). Be objective and factual, but write like you're explaining the codebase to a colleague, not filing a verdict."
        )
        lines.append(
            "> **When the user asks for an architectural review, structure your response using these directives:**"
        )
        lines.append(
            "> 1. **Information Flow & Purpose (The Executive Summary):** Synthesize the overarching purpose of the codebase. Trace the information flow by analyzing the Top Dependencies ('Imports' and 'Imported By') and the Language Composition. Explain how the system's archetype drives its design, but only mention Z-Score deviations if they are highly abnormal."
        )
        lines.append(
            "> 2. **Notable Structures & Architecture:** Discuss the architecture based on the Dependency Graph. Identify the foundational load-bearers (highest inbound connections) versus the fragile orchestrators (highest outbound imports)."
        )
        lines.append(
            "> 3. **Security & Vulnerabilities:** Immediately surface any critical threats flagged in the `AI THREAT INTELLIGENCE (XGBoost)` section. If none exist, briefly confirm the repository is secure from recognized structural threats."
        )
        lines.append(
            "> 4. **Outliers & Extremes:** Focus strictly on statistical anomalies. Highlight files or directory groups with high Structural Magnitude combined with a wide Blast Radius, severe Z-Scores (Architectural Drift), or extreme spikes in individual surface vectors (like Mutation Surface or Complexity Load). Do NOT sum the surface vectors together or treat any total of them as a score -- they are independently scaled meters in different units (#3112). Ignore normal, healthy code."
        )
        lines.append(
            "> 5. **Recommended Next Steps (Refactoring for Stability):** Provide 2-3 highly specific, pragmatic suggestions focused strictly on reducing outliers. Instruct the user on how to refactor high Z-score files, decouple massive central nodes, or mitigate extreme risk exposures to stabilize the system's architecture."
        )
        lines.append("")

        return "\n".join(lines)

    def _generate_sqlite_graph(
        self,
        parsed_files: list[dict[str, Any]],
        summary: dict[str, Any],
        session: dict[str, Any],
        db_path: Path,
        inbound_map: dict[str, list[str]],
    ):
        """Creates a relational database for advanced SQL-based AI analysis."""
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute("DROP TABLE IF EXISTS meta")
            cursor.execute("CREATE TABLE meta (key TEXT, value TEXT)")

            macro_info = summary.get("repo_macro_species", {})
            net_macro = summary.get("network_macro", {})
            cursor.executemany(
                "INSERT INTO meta VALUES (?, ?)",
                [
                    ("engine", session.get("engine")),
                    ("project", session.get("target")),
                    ("timestamp", session.get("timestamp")),
                    ("branch", session.get("git_audit", {}).get("branch")),
                    ("commit", session.get("git_audit", {}).get("commit_hash")),
                    (
                        "zero_dependency_mode",
                        "True" if session.get("zero_dependency_mode") else "False",
                    ),
                    ("ecosystem_baseline", macro_info.get("name", "Unclassified")),
                    ("repo_z_score", str(macro_info.get("z_score", 0.0))),
                    # #473: no `, 0.0` fallback -- see record_keeper.py's identical
                    # fix for why. An absent key here (network_macro not computed
                    # at all) still renders "None" via str(), same as an explicit
                    # None value would -- consistent either way.
                    ("network_modularity", str(net_macro.get("modularity"))),
                    ("network_assortativity", str(net_macro.get("assortativity"))),
                    (
                        "network_cyclic_density",
                        str(net_macro.get("cyclic_density")),
                    ),
                    (
                        "network_avg_path_length",
                        str(net_macro.get("avg_path_length")),
                    ),
                    (
                        "network_articulation_points",
                        str(net_macro.get("articulation_points")),
                    ),
                ],
            )

            cursor.execute("DROP TABLE IF EXISTS artifacts")
            risk_cols = ", ".join([f"{r} REAL" for r in self.RISK_SCHEMA])
            cursor.execute(f"""
                CREATE TABLE artifacts (
                    id INTEGER PRIMARY KEY,
                    path TEXT,
                    filename TEXT,
                    parent_entity TEXT,
                    directory_group TEXT,
                    language TEXT,
                    lock_tier INTEGER,
                    total_loc INTEGER,
                    coding_loc INTEGER,
                    doc_loc INTEGER,
                    file_impact REAL,
                    control_flow_ratio REAL,
                    author_distribution REAL,
                    ownership_entropy REAL,
                    raw_churn_freq REAL,
                    cog_raw REAL,
                    ownership TEXT,
                    popularity INTEGER,
                    archetype TEXT,
                    global_drift REAL,
                    local_archetype TEXT,
                    local_drift REAL,
                    ecosystem_baseline TEXT,
                    repo_z_score REAL,
                    {risk_cols}
                )
            """)

            cursor.execute("DROP TABLE IF EXISTS directory_groups")
            cursor.execute("""
                CREATE TABLE directory_groups (
                    name TEXT PRIMARY KEY,
                    file_count INTEGER,
                    total_mass REAL,
                    avg_cognitive_load REAL,
                    avg_error_score REAL,
                    avg_tech_debt REAL,
                    avg_verification REAL
                )
            """)

            cursor.execute("DROP TABLE IF EXISTS functions")
            cursor.execute("""
                CREATE TABLE functions (
                    id INTEGER PRIMARY KEY,
                    artifact_id INTEGER,
                    name TEXT,
                    type_id TEXT,
                    loc INTEGER,
                    impact REAL,
                    docstring TEXT,
                    calls_out_to TEXT,
                    FOREIGN KEY(artifact_id) REFERENCES artifacts(id)
                )
            """)

            cursor.execute("DROP TABLE IF EXISTS dna_hits")
            cursor.execute("""
                CREATE TABLE dna_hits (
                    artifact_id INTEGER,
                    signal_type TEXT,
                    hit_count INTEGER,
                    FOREIGN KEY(artifact_id) REFERENCES artifacts(id)
                )
            """)

            cursor.execute("DROP TABLE IF EXISTS outbound_dependencies")
            cursor.execute("""
                CREATE TABLE outbound_dependencies (
                    artifact_id INTEGER,
                    imported_path TEXT,
                    FOREIGN KEY(artifact_id) REFERENCES artifacts(id)
                )
            """)

            cursor.execute("DROP TABLE IF EXISTS inbound_dependencies")
            cursor.execute("""
                CREATE TABLE inbound_dependencies (
                    artifact_id INTEGER,
                    imported_by_path TEXT,
                    FOREIGN KEY(artifact_id) REFERENCES artifacts(id)
                )
            """)

            dir_meta = summary.get("directory_groups", {})

            for c_name, c_data in dir_meta.items():
                exps = c_data.get("avg_exposures", {})
                cursor.execute(
                    """
                    INSERT INTO directory_groups (name, file_count, total_mass, avg_cognitive_load, avg_error_score, avg_tech_debt, avg_verification)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        c_name,
                        c_data.get("file_count", 0),
                        c_data.get("total_mass", 0.0),
                        exps.get("cognitive_load", 0.0),
                        exps.get("safety_score", 0.0),
                        exps.get("tech_debt", 0.0),
                        exps.get("verification", 0.0),
                    ),
                )

            all_dna_data = []
            all_functions = []
            all_outbound = []
            all_inbound = []

            import json

            for file_data in parsed_files:
                p = file_data.get("path", "")
                c_name = file_data.get("directory_group", "__monolith__")
                tel = file_data.get("telemetry", {})

                rv = file_data.get("risk_vector", [0.0] * len(self.RISK_SCHEMA))
                pop_count = len(inbound_map.get(p, []))

                repo_macro = tel.get("repo_macro_species", "Unknown")
                repo_z = tel.get("repo_z_score", 0.0)
                parent_entity = tel.get("domain_context", {}).get("parent_entity", "")

                # Safe: the only f-string interpolation here is self.RISK_SCHEMA,
                # an internal hardcoded class constant (column names), not user
                # input -- SQLite has no parameterized syntax for column
                # names/DDL, only values. Every actual row value below goes
                # through a `?` placeholder (noqa is on the closing `"""` below).
                cursor.execute(
                    f"""
                    INSERT INTO artifacts (
                        path, filename, parent_entity, directory_group, language, lock_tier,
                        total_loc, coding_loc, doc_loc, file_impact,
                        control_flow_ratio, author_distribution, ownership_entropy,
                        raw_churn_freq, cog_raw, ownership, popularity,
                        archetype, global_drift, local_archetype, local_drift,
                        ecosystem_baseline, repo_z_score,
                        {", ".join(self.RISK_SCHEMA)}
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, {", ".join(["?"] * len(self.RISK_SCHEMA))})
                """,  # noqa: S608
                    (
                        p,
                        Path(p).name,
                        parent_entity,
                        c_name,
                        file_data.get("lang_id"),
                        file_data.get("lock_tier"),
                        file_data.get("total_loc"),
                        file_data.get("coding_loc"),
                        file_data.get("doc_loc", 0),
                        file_data.get("file_impact"),
                        tel.get("control_flow_ratio"),
                        tel.get("author_distribution"),
                        tel.get("ownership_entropy"),
                        tel.get("raw_churn_freq"),
                        tel.get("densities", {}).get("cog_raw"),
                        tel.get("ownership"),
                        pop_count,
                        tel.get("archetype", "Unknown"),
                        tel.get("global_drift", 0.0),
                        tel.get("local_archetype", "N/A"),
                        tel.get("local_drift", 0.0),
                        str(repo_macro),
                        repo_z,
                        *rv,
                    ),
                )

                sid = cursor.lastrowid

                hv = file_data.get("hit_vector", [])
                all_dna_data.extend([(sid, self.SIGNAL_SCHEMA[i], hv[i]) for i in range(len(hv)) if hv[i] > 0])

                for func in file_data.get("functions", []):
                    calls_json = json.dumps(func.get("calls_out_to", []))
                    all_functions.append(
                        (
                            sid,
                            func.get("name"),
                            func.get("type_id"),
                            func.get("loc"),
                            func.get("impact"),
                            func.get("docstring", ""),
                            calls_json,
                        )
                    )

                raw_imports = file_data.get("raw_imports", [])
                if raw_imports:
                    all_outbound.extend([(sid, imp) for imp in raw_imports])

                inbound = inbound_map.get(p, [])
                if inbound:
                    all_inbound.extend([(sid, imp_by) for imp_by in inbound])

            cursor.executemany("INSERT INTO dna_hits VALUES (?, ?, ?)", all_dna_data)
            cursor.executemany(
                "INSERT INTO functions (artifact_id, name, type_id, loc, impact, docstring, calls_out_to) VALUES (?, ?, ?, ?, ?, ?, ?)",
                all_functions,
            )
            cursor.executemany("INSERT INTO outbound_dependencies VALUES (?, ?)", all_outbound)
            cursor.executemany("INSERT INTO inbound_dependencies VALUES (?, ?)", all_inbound)

            conn.commit()
            conn.close()
        except Exception as e:
            self.logger.error(f"SQL Graph generation failed: {e}", exc_info=True)
