# ==============================================================================

# galaxyscope:ignore sec_high_risk_execution, sec_hardcoded_secrets, sec_io
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

# galaxyscope:ignore sec_high_risk_execution, sec_hardcoded_secrets, sec_io

# galaxyscope:ignore sec_high_risk_execution, sec_hardcoded_secrets, sec_io

import logging
import statistics
from typing import Any, Optional

# ==============================================================================

# galaxyscope:ignore sec_high_risk_execution, sec_hardcoded_secrets, sec_io
# GitGalaxy Phase 7: Spectral Auditor (Quality Control)
# Strategy Protocol: Bayesian Accountability & Unparsable Artifacts
# ==============================================================================

# galaxyscope:ignore sec_high_risk_execution, sec_hardcoded_secrets, sec_io


class StatisticalAuditor:
    """
    GitGalaxy Statistical Auditor.

    PURPOSE: Acts as the 3rd-gate quality control filter to catch structural anomalies
    and data dumps using language-specific Median Absolute Deviation (MAD) outliers
    and explicit hard-floor density checks.

    ARCHITECTURE:
    1. Heuristic Consensus: Resolves ambiguous file extensions (.h, .m) based on repo-wide trends.
    2. Polyglot Baseline Defense: Bypasses strict statistical checks for heavily blended files.
    3. Noise Rejection: Outliers are stripped of logic claims and moved to the exclusion queue.

    NOTE: the per-language outlier loop only runs when `lang_defs` is supplied (it needs
    each language's rule set to tell a genuinely-inert data format apart from real code).
    The orchestrator MUST pass it (#2325 -- it previously did not, so every language hit
    the inert bypass and the MAD / density floors never fired). A former "Low-Sample
    Threshold Guard" that reverted small-footprint languages to plaintext was removed with
    the same fix; see the note in `audit()`.
    """

    def __init__(
        self,
        parent_logger: Optional[logging.Logger] = None,
        lang_defs: Optional[dict[str, Any]] = None,
    ):
        """Initializes the statistical auditor and synchronizes telemetry."""

        if parent_logger:
            self.logger = parent_logger.getChild("statistical_auditor")
            self.logger.setLevel(parent_logger.level)
        else:
            self.logger = logging.getLogger("statistical_auditor")
            self.logger.setLevel(logging.INFO)

        self.logger.debug("Initializing Statistical Auditor (Data Quality Gating)...")

        # Save the language definitions so we can check for execution topology later
        self.lang_defs = lang_defs or {}

        # SCHEMA CONSTANTS (32 Signal Keys representing pure active logic)
        self.SIGNAL_KEYS = [
            "branch",
            "args",
            "structural_boundaries",
            "func_start",
            "class_start",
            "import",
            "api",
            "decorators",
            "safety",
            "safety_bypasses",
            "high_risk_execution",
            "state_mutation",
            "reflection_metaprogramming",
            "keyword_debt",
            "hardcoded_secrets",
            "io",
            "concurrency",
            "ui_framework",
            "events",
            "ssr_boundaries",
            "dependency_injection",
            "scientific",
            "generics",
            "comprehensions",
            "closures",
            "globals",
            "telemetry",
            "test",
            "macros",
            "pointers",
            "memory_alloc",
            "inline_asm",
        ]

    def audit(self, parsed_files: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Executes statistical gating to identify data-dumps and structural outliers."""
        import os  # Required for extension splitting in Consensus Engine

        if not parsed_files:
            self.logger.debug("Statistical Audit skipped: Empty file roster provided.")
            return [], []

        self.logger.info(f"Scanning {len(parsed_files)} artifacts for structural anomalies and data dumps...")

        verified_files, unparsable_files = [], []

        # ======================================================================
        # DEFENSIVE ARCHITECTURE: Heuristic Extension Consensus
        # Certain file extensions (like .h or .m) are ambiguous across languages
        # (C vs C++ vs Objective-C). If the regex parser lacked high confidence,
        # we check the macro-state of the repository. If 80% of the repository's
        # confidently parsed .h files are C++, we force the ambiguous file to align.
        # ======================================================================
        confident_artifacts = []
        ambiguous_artifacts = []

        # 1. The Triage
        for artifact in parsed_files:
            telemetry = artifact.get("telemetry", {})
            tier = telemetry.get("identity_lock_tier", artifact.get("lock_tier", 4))
            proof = telemetry.get("identity_source_proof", artifact.get("source_proof", ""))

            # If the engine had to guess, or confidence was terrible, hold it back.
            if tier >= 4 or "Collision" in proof:
                ambiguous_artifacts.append(artifact)
            else:
                confident_artifacts.append(artifact)

        # 2. Build the Ecosystem Consensus Map
        # Structure: { ".ext": { "lang1": count, "lang2": count } }
        consensus_map: dict[str, dict[str, int]] = {}
        global_lang_counts: dict[str, int] = {}

        for artifact in confident_artifacts:
            ext = os.path.splitext(artifact.get("path", ""))[1].lower()
            lang = artifact.get("lang_id")

            if lang:
                global_lang_counts[lang] = global_lang_counts.get(lang, 0) + 1

            if ext and lang:
                if ext not in consensus_map:
                    consensus_map[ext] = {}
                consensus_map[ext][lang] = consensus_map[ext].get(lang, 0) + 1

        # 3. The Heuristic Loop-Back
        resolved_count = 0
        for artifact in ambiguous_artifacts:
            ext = os.path.splitext(artifact.get("path", ""))[1].lower()
            current_lang = artifact.get("lang_id", "unknown")

            if ext in consensus_map:
                lang_counts = consensus_map[ext]
                total_for_ext = sum(lang_counts.values())

                if total_for_ext > 0:
                    # Find the dominant language for this extension in THIS repository
                    winner_lang = max(lang_counts, key=lambda k: lang_counts[k])
                    winner_count = lang_counts[winner_lang]

                    # If the winner claims >= 80% of the confident files, it is the Ecosystem Truth.
                    if (winner_count / total_for_ext) >= 0.80:
                        artifact["lang_id"] = winner_lang
                        if "telemetry" not in artifact:
                            artifact["telemetry"] = {}
                        artifact["telemetry"]["identity_source_proof"] = (
                            f"Heuristic Loop-Back (Consensus: {winner_lang})"
                        )
                        artifact["telemetry"]["identity_lock_tier"] = 2  # Elevate it to a strong Ecosystem Lock

                        self.logger.debug(
                            f"[Consensus] Resolved ambiguous '{artifact.get('name')}': {current_lang} -> {winner_lang}"
                        )
                        confident_artifacts.append(artifact)
                        resolved_count += 1
                        continue

            # ---> THE GLOBAL C-FAMILY HEADER FALLBACK <---
            # If the 80% threshold fails (e.g., a 3-way tie), look at the macro-state of the entire repo.
            if ext in {".h", ".hpp", ".inc"}:
                c_counts = {
                    "c": global_lang_counts.get("c", 0),
                    "cpp": global_lang_counts.get("cpp", 0),
                    "objective-c": global_lang_counts.get("objective-c", 0),
                }

                # If there is ANY C-family presence in the confident core, give the header to the dominant one.
                if sum(c_counts.values()) > 0:
                    winner_lang = max(c_counts, key=lambda k: c_counts[k])
                    artifact["lang_id"] = winner_lang

                    if "telemetry" not in artifact:
                        artifact["telemetry"] = {}
                    artifact["telemetry"]["identity_source_proof"] = (
                        f"Heuristic Loop-Back (Global C-Family Dominance: {winner_lang})"
                    )
                    artifact["telemetry"]["identity_lock_tier"] = 2

                    self.logger.debug(
                        f"[Consensus] Global C-Family Tie-Breaker triggered for '{artifact.get('name')}': Defaulting to {winner_lang}."
                    )
                    confident_artifacts.append(artifact)
                    resolved_count += 1
                    continue

            # ---> DECISIVE COLLISION-RESOLUTION KEEP <---
            # The ecosystem consensus above can only rescue an ambiguous file when the repo
            # has OTHER, confidently-parsed files of the same extension to vote. For an
            # extension that is *always* a collision (e.g. `.y`, claimed by both `c` and
            # `yacc`), no such vote can ever exist, so a real grammar file that classified
            # correctly and extracted real structure was still being silently deleted here
            # (#1926). A file that (a) came in via a genuine extension collision -- not a
            # bare Tier-4 lexical guess with no extension support -- (b) resolved decisively
            # (high identity confidence) and (c) actually produced extracted structure is
            # not a hallucination; keep it rather than banish it.
            proof_str = artifact.get("telemetry", {}).get("identity_source_proof", artifact.get("source_proof", ""))
            confidence = artifact.get("telemetry", {}).get("identity_confidence", artifact.get("intensity", 0.0))
            equations = artifact.get("equations", {})
            signal_hits = sum(v for k, v in equations.items() if k in self.SIGNAL_KEYS and isinstance(v, (int, float)))
            has_structure = len(artifact.get("functions", [])) > 0 or signal_hits >= 5

            if (
                "Collision" in proof_str
                and current_lang not in ("", "unknown", "undeterminable", "plaintext")
                and confidence >= 0.85
                and has_structure
            ):
                artifact.setdefault("telemetry", {})
                artifact["telemetry"]["identity_source_proof"] = (
                    f"Collision Resolved (Lexically Decisive: {current_lang})"
                )
                artifact["telemetry"]["identity_lock_tier"] = 3
                self.logger.debug(
                    f"[Consensus] Kept decisively-resolved '{artifact.get('name')}' "
                    f"({current_lang}): collision + conf {confidence:.2f} + "
                    f"{len(artifact.get('functions', []))} functions / {signal_hits} signals."
                )
                confident_artifacts.append(artifact)
                resolved_count += 1
                continue

            # If we reach here, the file was ambiguous and the ecosystem couldn't save it.
            # Banish it to unparsable_files immediately to prevent hallucinations.
            reason = "Unresolved Ambiguity (Tier 4 Fallback failed Ecosystem Consensus)"
            unparsable_files.append(self._format_for_exclusion(artifact, reason))

        if resolved_count > 0:
            self.logger.info(
                f"Consensus Engine: Stabilized {resolved_count} ambiguous extensions based on repository trends."
            )
        # =================================================================

        by_lang: dict[str, list[dict[str, Any]]] = {}

        # 4. Group artifacts by linguistic species for localized statistics
        for artifact in confident_artifacts:
            lid = artifact.get("lang_id", "undeterminable")
            if lid not in by_lang:
                by_lang[lid] = []
            by_lang[lid].append(artifact)

        # 5. Process each species independently
        for lid, group in by_lang.items():
            if lid in ("undeterminable", "unknown"):
                unparsable_files.extend(
                    self._format_for_exclusion(artifact, "Pre-filtered Noise (Pre-Audit)") for artifact in group
                )
                self.logger.debug(f"[{lid}] Bypassed {len(group)} artifacts (already excluded).")
                continue

            # ==================================================================
            # DEFENSIVE ARCHITECTURE: Dynamic Auditability Check
            # Prevent pure data files (YAML, JSON, CSV) from triggering the
            # statistical outliers by checking if their language definition
            # even contains executable logic signals.
            # ==================================================================
            is_inert = False

            if hasattr(self, "lang_defs") and lid in self.lang_defs:
                rules = self.lang_defs[lid].get("rules", {})

                # POSITIVE COUNT: How many actual, active logic sensors exist?
                active_signals = sum(1 for key in self.SIGNAL_KEYS if rules.get(key) is not None)

                if active_signals == 0:
                    is_inert = True
            else:
                is_inert = True  # Unknown/Undefined languages are inert by default

            # Immediately bypass static assets from all statistical checks
            if is_inert:
                verified_files.extend(group)
                self.logger.debug(f"[{lid}] Bypassed {len(group)} artifact(s) (Static Asset: 0 Active Signals).")
                continue

            # NOTE: a "Low-Sample Threshold Guard" (GATE C) used to sit here -- it reverted
            # any language with <= orphan_threshold files to plaintext unless every file had
            # a Tier-0 "Absolute Consensus" lock. Removed with #2325: this auditor never
            # actually ran in production (it was constructed without `lang_defs`, so every
            # group hit the inert bypass above), and the guard's core assumption is wrong --
            # a clean single-extension file (`foo.css`, `foo.kt`, `foo.nix`) locks at Tier 2
            # "Single Indicator (Ext)", never Tier 0, so turning the guard on would have
            # erased ~13 legitimately-classified languages (css, kotlin, nix, objective-c,
            # scheme, proto, tcl, yacc, ...) from any repo with a small footprint of them.
            # Small-sample hallucination is already handled upstream by the Heuristic
            # Extension Consensus triage and the Tier-4/undeterminable pre-filters.

            # ==================================================================
            # GATE D: STATISTICAL OUTLIER DETECTION (MAD & Density Floors)
            # ==================================================================
            rhos = []

            # Calculate logic density (rho) for all artifacts in this language
            for artifact in group:
                try:
                    equations = artifact.get("equations", {})
                    signal_hits = sum(equations.get(k, 0) for k in self.SIGNAL_KEYS)
                    # Denominator MUST be total physical lines to detect 'hollowness'
                    total_physical_loc = max(artifact.get("total_loc", artifact.get("coding_loc", 1)), 1)
                    artifact["_rho"] = signal_hits / total_physical_loc

                    # Polyglot Defense: Only add pure files to the statistical baseline
                    if not self._is_highly_blended(artifact):
                        rhos.append(artifact["_rho"])
                except Exception as e:
                    self.logger.warning(
                        f"Failed to calculate signal density for '{artifact.get('name', 'unknown')}': {e}"
                    )
                    artifact["_rho"] = 0.0
                    rhos.append(0.0)

            # --- GATE D.1: STATISTICAL READINESS CHECK ---
            # 1. Population Density (N >= 50)
            has_mass = len(rhos) >= 50

            # 2. Confidence Anchor (At least one file with C > 0.85)
            has_anchor = any(
                artifact.get("telemetry", {}).get("identity_confidence", artifact.get("intensity", 0.0)) > 0.85
                for artifact in group
            )

            use_stats = has_mass and has_anchor
            median_rho = 0.0
            mad = 0.00001

            if use_stats:
                try:
                    median_rho = statistics.median(rhos)
                    mad = statistics.median([abs(r - median_rho) for r in rhos])
                    mad = max(mad, 0.00001)  # Prevent division by zero

                    # 3. Cohesion Metric (R-MAD < 1.0)
                    r_mad = mad / max(median_rho, 0.00001)
                    if r_mad >= 1.0:
                        self.logger.debug(
                            f"[{lid}] Baseline skipped: Heterogeneous Population (R-MAD {r_mad:.2f} >= 1.0)."
                        )
                        use_stats = False
                    else:
                        self.logger.debug(
                            f"[{lid}] Statistical Baseline -> Median Rho: {median_rho:.4f} | MAD: {mad:.4f} | R-MAD: {r_mad:.2f}"
                        )
                except statistics.StatisticsError as e:
                    self.logger.warning(
                        f"[{lid}] Statistical failure during MAD calculation: {e}. Falling back to Zero-Density Thresholds only."
                    )
                    use_stats = False
            else:
                self.logger.debug(
                    f"[{lid}] Baseline skipped (N={len(rhos)}, Anchor={has_anchor}). Defaulting to Zero-Density Thresholds."
                )

            relegated_count = 0
            dead_code_count = 0

            # 3. Evaluate each artifact against the baseline
            for artifact in group:
                rho = artifact.pop("_rho", 0.0)
                is_outlier = False
                relegation_reason = ""

                loc = artifact.get("coding_loc", 0)
                name = artifact.get("name", "unknown")
                path = artifact.get("path", "unknown")
                is_blended = self._is_highly_blended(artifact)
                is_minified = artifact.get("is_minified", False)

                # Extract telemetry from Phase 1 OR fallback to root meta keys
                telemetry = artifact.get("telemetry", {})
                lock_tier = telemetry.get("identity_lock_tier", artifact.get("lock_tier", 4))
                source_proof = telemetry.get("identity_source_proof", artifact.get("source_proof", "Discovery"))
                confidence = telemetry.get("identity_confidence", artifact.get("intensity", 0.0))

                # ZERO-DENSITY THRESHOLD: Hard Floor check for data dumps disguised as code
                if loc > 50 and rho == 0 and not is_minified:
                    is_outlier = True
                    relegation_reason = f"Zero-Density Threshold (LOC: {loc}, Signals: 0)"

                # ---> NEW: PACKED PAYLOAD GUARD (Impossible Density Law) <---
                # Normal human code rarely sustains > 1.5 logic hits per physical line.
                # If a file sustains > 3.0 across 30+ lines, it is mathematically guaranteed
                # to be minified, obfuscated, or packed with embedded binaries.
                elif loc > 30 and rho > 3.0 and not is_minified:
                    is_outlier = True
                    relegation_reason = f"Packed Payload Guard (Impossible Density: {rho:.2f} hits/line)"

                # THE ROBUST Z-SCORE (MAD)
                # Bypassed if the file is a heavy polyglot (its density is blended)
                elif use_stats and not is_blended:
                    mi = (0.6745 * (rho - median_rho)) / mad

                    # 4. Probabilistic Threshold Gating (T_adj = -3.5 * Ci)
                    t_adj = -5 * max(confidence, 0.1)  # Floor confidence to prevent 0 threshold

                    if mi < t_adj:
                        is_outlier = True
                        relegation_reason = f"Statistical Anomaly (Z-Score: {mi:.2f} < {t_adj:.2f})"

                # 4. Routing logic for Outliers
                if is_outlier:
                    if self._is_dead_code(artifact):
                        # SPEC ALIGNMENT: Grant Bypass without mutating lang_id
                        artifact["is_necrotic"] = True
                        self.logger.debug(
                            f"[{lid}] Dead Code Guard: '{name}' failed audit ({relegation_reason}) but granted a Bypass Exclusion."
                        )
                        verified_files.append(artifact)
                        dead_code_count += 1

                    elif self._is_threat(artifact):
                        # --- ACTIVE THREAT QUARANTINE ---
                        # If a file is heavily obfuscated malware, its standard logic density will crash to 0,
                        # making it look like a data dump. This guard explicitly saves it from the trash
                        # and forces it onto the map so the auditor can see the threat.
                        artifact["is_quarantined"] = True
                        self.logger.critical(
                            f"[{lid}] 🚨 THREAT QUARANTINE: '{name}' failed structural audit ({relegation_reason}) but contains ACTIVE THREAT SIGNATURES. Forcing to Visible Map!"
                        )
                        verified_files.append(artifact)

                    else:
                        # --- CLASSIFICATION REFUTATION ---
                        # If the file had a strong prior (Tier 0 or 1), hold the prediction to account.
                        if lock_tier <= 1:
                            self.logger.warning(
                                f"CLASSIFICATION REFUTATION: '{path}' was claimed as '{lid}' via {source_proof} (Tier {lock_tier}), "
                                f"but its Intent Density is an outlier ({relegation_reason}). Rejected."
                            )
                        elif loc > 1000:
                            # SIZE-AWARE WARNING: If a massive file is dropped, alert the engineer.
                            self.logger.warning(
                                f"Massive Data Dump Excluded: '{path}' (LOC: {loc}) stripped to unparsable. Reason: {relegation_reason}"
                            )
                        else:
                            self.logger.debug(
                                f"[{lid}] Excluded: '{name}' stripped to unparsable. Reason: {relegation_reason}"
                            )

                        # Format it as Noise to save memory and ensure schema consistency
                        unparsable_files.append(self._format_for_exclusion(artifact, relegation_reason))
                        relegated_count += 1
                else:
                    verified_files.append(artifact)

            if relegated_count > 0 or dead_code_count > 0:
                self.logger.info(
                    f"[{lid}] Audit complete: {relegated_count} relegated to Exclusion Queue, {dead_code_count} flagged as Dead Code."
                )

        self.logger.info(
            f"Anomaly sweep concluded | Stable Files Mapped: {len(verified_files)} | Collapsed to Exclusion Queue: {len(unparsable_files)}"
        )
        return verified_files, unparsable_files

    def _is_highly_blended(self, artifact: dict[str, Any]) -> bool:
        """Determines if a file is a Polyglot where the primary language is < 80% of the mass."""
        lang_mix = artifact.get("lang_mix", [])
        if not lang_mix:
            return False

        primary_lang = artifact.get("lang_id")
        for mix in lang_mix:
            if mix.get("id") == primary_lang:
                # If the primary language makes up less than 80% of the file, it's blended.
                return mix.get("pct", 100.0) < 80.0

        return True  # Primary language wasn't even in the mix (Extreme anomaly)

    def _is_dead_code(self, artifact: dict[str, Any]) -> bool:
        """Determines if an artifact is predominantly dead code or comments."""
        try:
            doc_loc = artifact.get("doc_loc", 0)
            coding_loc = max(artifact.get("coding_loc", 1), 1)

            # Condition 1: Massive comment-to-code ratio (5-to-1)
            if doc_loc > (coding_loc * 5):
                return True

            equations = artifact.get("equations", {})
            total_signals = sum(equations.values())

            # Condition 2: Over 50% of the active signals are commented-out structural logic
            if total_signals > 0 and equations.get("dead_code", 0) > (total_signals * 0.5):
                return True

        except Exception as e:
            self.logger.debug(f"Dead code evaluation failed safely: {e}")

        return False

    def _format_for_exclusion(self, artifact: dict[str, Any], reason: str) -> dict[str, Any]:
        """
        Formats an audited artifact to match the Orchestrator's Exclusion Queue schema.
        This ensures structural inertia and prevents the JSON archive from bloating.
        """
        telemetry = artifact.get("telemetry", {})

        return {
            "path": artifact.get("path", "unknown"),
            "reason": reason,
            "size_bytes": artifact.get("size_bytes", 0),
            # Preserve Phase 1 Telemetry for SBOM Traceability
            "failed_claim": artifact.get("lang_id", "unknown"),
            "identity_confidence": telemetry.get("identity_confidence", artifact.get("intensity", 0.0)),
            "identity_lock_tier": telemetry.get("identity_lock_tier", artifact.get("lock_tier", 4)),
            "identity_source_proof": telemetry.get("identity_source_proof", artifact.get("source_proof", "Discovery")),
        }

    def _is_threat(self, artifact: dict[str, Any]) -> bool:
        """
        Determines if an artifact contains active security threat signatures.
        Used by the Quarantine Guard to prevent obfuscated malware from
        using its low structural density to hide in the Noise Exclusion Queue.
        """
        try:
            equations = artifact.get("equations", {})

            # Sum the mass of all keys starting with 'sec_'
            threat_mass = sum(val for key, val in equations.items() if key.startswith("sec_"))

            # If the file has even a single threat signature, it cannot be discarded.
            if threat_mass > 0:
                return True

        except Exception as e:
            self.logger.debug(f"Threat evaluation failed safely: {e}")

        return False
