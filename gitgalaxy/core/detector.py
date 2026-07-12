# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

# galaxyscope:ignore sec_high_risk_execution

import re
import math
import logging
import time
import bisect
from typing import Dict, List, Any, TypedDict, Optional, Tuple
from gitgalaxy.standards.analysis_lens import RECORDING_SCHEMAS

HAS_TIKTOKEN = False
try:
    import tiktoken

    HAS_TIKTOKEN = True
    # cl100k_base is the standard for GPT-4, o1, and a highly accurate proxy for Claude
    ENCODER = tiktoken.get_encoding("cl100k_base")
except ImportError:
    pass


def get_token_mass(text: str, deep_scan: bool = False) -> Optional[int]:
    """Calculates context window footprint. Returns None if tiktoken is missing to prevent dataset poisoning."""
    if not text:
        return 0
    if HAS_TIKTOKEN:
        return len(ENCODER.encode(text, disallowed_special=()))
    return None


# ==============================================================================
# GitGalaxy Phase 2.5 & 7.5: Logic Splicer & Topological Mapper
# Strategy v6.3.0 Protocol: Fluid-State Counters, Language Sliding & Semantic Modes
# ==============================================================================


class FunctionNode(TypedDict, total=False):
    """Metadata for a surgically extracted functional logic block."""

    name: str

    # Dual-Key mapping to ensure compatibility with all pipeline versions
    semantic_type: str
    type_id: str

    loc: int
    coding_loc: int
    keyword_density: float

    branch_count: int
    branch: int

    args: int
    args_count: int

    control_flow_angle: float
    angle: float

    control_flow_ratio: float
    cf_ratio: float

    structural_weight: float
    mag: float
    impact: float

    start_line: int
    end_line: int

    big_o_depth: int
    is_recursive: bool
    db_complexity: int
    docstring: str
    calls_out_to: List[str]
    hit_vector: Dict[str, int]
    token_mass: int


class LogicData(TypedDict, total=False):
    """The standardized output schema for Strategy v6.2.0+ compliance."""

    equations: Dict[str, int]
    functions: List[FunctionNode]
    logic_density: float
    total_functional_impact: float
    total_control_flow_ratio: float
    raw_imports: list
    metadata: Dict[str, str]
    token_mass: int
    financial_read_cost: float


# ==============================================================================
# THE STRUCTURAL SIGNATURE CONFIGURATION MATRIX
# ==============================================================================


class ScopeParsingRegistry:
    """
    The Structural Signature Calibration Matrix for GalaxyScope's Primary Detector.
    Defines the structural heuristics required to slice non-brace languages.

    DEFENSIVE ARCHITECTURE:
    By categorizing languages into integration modes, the engine avoids building
    heavy Abstract Syntax Trees (ASTs). It visualizes functional intent across
    50+ languages natively without requiring the codebase to compile.

    - MODE D: Keyword Scope Tracking (Depth tracking via language-specific keywords)
    - MODE E: Terminator Delimiting (Hard slicing via line-ending tokens)
    """

    # Internal aliases to route variations to their base optical physics
    _ALIASES = {
        "bash": "shell",
        "sh": "shell",
        "zsh": "shell",
        "t-sql": "sql",
        "plpgsql": "sql",
        "mysql": "sql",
        "psql": "sql",
        "sqlite": "sql",
        "visualbasic": "vb",
        "vba": "vb",
    }

    DEFINITIONS = {
        # ==========================================
        # 🔴 INTEGRATION MODE D: The Handshake Stack
        # ==========================================
        "shell": {
            "mode": "mode_d",
            "openers": [
                r"\bif\b",
                r"\bwhile\b",
                r"\buntil\b",
                r"\bfor\b",
                r"\bcase\b",
                r"\{",  # Shell functions use braces for scope
            ],
            "closers": [r"\bfi\b", r"\bdone\b", r"\besac\b", r"\}"],
        },
        "ruby": {
            "mode": "mode_d",
            "openers": [
                r"(?<![:.])\bdef\b(?!:)",
                r"(?<![:.])\bclass\b(?!:)",
                r"(?<![:.])\bmodule\b(?!:)",
                r"(?<![:.])\bif\b(?!:)",
                r"(?<![:.])\bunless\b(?!:)",
                r"(?<![:.])\bwhile\b(?!:)",
                r"(?<![:.])\buntil\b(?!:)",
                r"(?<![:.])\bfor\b(?!:)",
                r"(?<![:.])\bcase\b(?!:)",
                r"(?<![:.])\bdo\b(?!:)",
                r"(?<![:.])\bbegin\b(?!:)",
            ],
            "closers": [r"(?<![:.])\bend\b(?!:)"],
        },
        "lua": {
            "mode": "mode_d",
            "openers": [
                r"\bfunction\b",
                r"\bif\b",
                r"\bwhile\b",
                r"\bfor\b",
                r"\brepeat\b",
            ],
            "closers": [r"\bend\b", r"\buntil\b"],
        },
        "elixir": {
            "mode": "mode_d",
            "openers": [
                r"\bdef\b",
                r"\bdefmodule\b",
                r"\bdefmacro\b",
                r"\bdefp\b",
                r"\bif\b",
                r"\bunless\b",
                r"\bcase\b",
                r"\bcond\b",
                r"\breceive\b",
                r"\bfn\b",
                r"\bdo\b",
            ],
            "closers": [r"\bend\b"],
        },
        "vb": {
            "mode": "mode_d",
            "openers": [
                r"\bsub\b",
                r"\bfunction\b",
                r"\bif\b",
                r"\bwhile\b",
                r"\bselect\b",
                r"\bfor\b",
                r"\bwith\b",
                r"\bproperty\b",
                r"\bclass\b",
            ],
            "closers": [r"\bend\b", r"\bnext\b", r"\bloop\b", r"\bwend\b"],
            "ignore_case": True,
        },
        # ==========================================
        # 🪓 INTEGRATION MODE E: Terminator Cleaving
        # ==========================================
        "sql": {
            "mode": "mode_e",
            "terminator": r";",
            "igniter": r"\b(SELECT|CREATE|UPDATE|DELETE|INSERT|ALTER|DROP|GRANT|REVOKE|WITH|DECLARE|TRUNCATE)\b",
        },
        "erlang": {
            "mode": "mode_e",
            "terminator": r"\.",
            "igniter": r"^[a-z_][a-zA-Z0-9_]*\s*(?:\(|->)",
        },
        "prolog": {
            "mode": "mode_e",
            "terminator": r"\.",
            "igniter": r"^[a-z_][a-zA-Z0-9_]*\s*(?:\(|:-)",
        },
    }

    @classmethod
    def get_config(cls, lang_id: str) -> Optional[dict]:
        """Resolves aliases and returns the structural signature config for the language."""
        if not lang_id:
            return None
        normalized_id = lang_id.lower()
        base_id = cls._ALIASES.get(normalized_id, normalized_id)
        return cls.DEFINITIONS.get(base_id)

    @classmethod
    def get_mode(cls, lang_id: str) -> Optional[str]:
        """Returns the specific integration mode required for the language."""
        config = cls.get_config(lang_id)
        return config["mode"] if config else None


# ------------------------------------------------------------------------------
# THE DETECTOR (Structural Detector)
# ------------------------------------------------------------------------------


class StructuralExtractor:
    """
    GitGalaxy Structural Extractor (Primary Heuristic Logic & Function Mapper).

    PURPOSE: Performs AST-less analysis of executable logic streams to extract
    functional nodes, calculate complexity, and detect structural security signatures.

    DEFENSIVE ARCHITECTURE (Lexical Heuristics vs. AST Parsing):
    AST parsers often fail when encountering non-standard syntax, legacy dialects,
    or partially-broken codebases. This extractor utilizes Fluid State Counters
    and O(1) lexical masking to achieve high-fidelity node extraction at
    ~100,000 LOC/sec, maintaining high performance without requiring
    fully-compilable source code.

    ARCHITECTURE:
    1. Fluid State Counter: Dynamically swaps regex registries mid-file for embedded languages.
    2. Bucket Continuation: Accumulates secondary language hits into the primary vector.
    3. Integration Modes: Labels (A), Braces (B), Indentation (C), Keywords (D), Terminators (E).
    """

    # --- DYNAMIC SCHEMA FETCH ---
    # Directly mirrors the central registry to prevent schema drift
    UNIVERSAL_METRICS_SCHEMA = RECORDING_SCHEMAS.get("SIGNAL_SCHEMA", [])

    HANDSHAKE_REGISTRY = [
        {
            "trigger": re.compile(r"<script", re.I),
            "end": re.compile(r"</script>", re.I),
            "target": "javascript",
            "pair": None,
        },
        {
            "trigger": re.compile(r"<style", re.I),
            "end": re.compile(r"</style>", re.I),
            "target": "css",
            "pair": None,
        },
        {
            "trigger": re.compile(r"asm!\s*\(|__asm__", re.I),
            "end": re.compile(r"\)"),
            "target": "assembly",
            "pair": ("(", ")"),
        },
    ]

    def __init__(
        self,
        lang_id: str,
        language_definitions: Dict[str, Any],
        parent_logger: Optional[logging.Logger] = None,
    ):
        if parent_logger:
            self.logger = parent_logger.getChild("splicer")
            self.logger.setLevel(parent_logger.level)
        else:
            self.logger = logging.getLogger("splicer")
            self.logger.setLevel(logging.INFO)

        self.primary_lang_id = lang_id.lower() if lang_id else "unknown"
        self.languages = language_definitions

        lang_config = self.languages.get(self.primary_lang_id, {})
        self.primary_rules = lang_config.get("rules", {})
        self.primary_family = lang_config.get("lexical_family", "c_style_comment")

        self.assembly_returns = re.compile(
            r"\b(?:TC\s+Q|TCF\s+Q|RETURN|RESUME|RELINT|RET|RTS|JMP\s+LR|BLR|END-PERFORM|END-IF|GOBACK|EXIT)\b",
            re.IGNORECASE,
        )

        self.CORE_MAPPING = {
            "branching": "branch",
            "io_ops": "io",
            "safety": "safety",
            "high_risk_execution": "high_risk_execution",
            "concurrency": "concurrency",
            "logic_flux": "state_mutation",
        }

        self.MAX_SATELLITES = 250
        self.MAX_DEPTH = 50
        self.HANDSHAKE_LOOKAHEAD_LIMIT = 50000

        if self.primary_lang_id not in self.languages or "rules" not in self.languages.get(self.primary_lang_id, {}):
            try:
                from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

                # Apply the healed definitions to the instance state
                self.languages = LANGUAGE_DEFINITIONS
                lang_config = self.languages.get(self.primary_lang_id, {})
                self.primary_rules = lang_config.get("rules", {})
                self.primary_family = lang_config.get("lexical_family", "c_style_comment")

                self.logger.warning(f"[AUTO-HEAL] Re-injected LANGUAGE_DEFINITIONS for '{self.primary_lang_id}'")
            except ImportError:
                pass

    def splice(
        self,
        code_stream: str,
        comment_stream: str,
        confidence: float = 1.0,
        profile_regex: bool = False,
        raw_content: str = "",
    ) -> Dict[str, Any]:
        """Executes the structural regex pass over refracted code streams."""
        self.raw_content_lines = raw_content.splitlines() if raw_content else []
        regex_telemetry = {}

        # We always extract the metadata first, even for Unparsable Artifacts
        ghost_meta = self._decode_comment_stream(comment_stream)

        # ---> THE ECOSYSTEM GRAVITY OVERRIDE <---
        # If the broader ecosystem safely locked a contested file (like a .h header)
        # into a C-family language, we trust the gravity and artificially boost the confidence.
        # This prevents pure-macro headers from falling below the 0.42 floor and vanishing into Unparsable Artifacts.
        if self.primary_lang_id in ["c", "cpp", "objective-c"]:
            confidence = 1.0

        # 1. The Custom Unparsable Artifact Bypass & Prose Deflection
        # Rejects unverified artifacts AND Static Assets before wasting compute
        if confidence < 0.42 or self.primary_lang_id in (
            "plaintext",
            "markdown",
            "json",
            "yaml",
            "csv",
        ):
            self.logger.debug(
                f"[DIAGNOSTIC] Bypass triggered (Conf: {confidence:.2f} | Lang: {self.primary_lang_id}). Relegating to Unparsable Artifacts."
            )
            return {
                "equations": {},
                "functions": [],
                "logic_density": 0.0,
                "sum_fxn_impact": 0.0,
                "total_control_flow_ratio": 0.0,
                "raw_imports": [],
                "metadata": ghost_meta,
            }

        if not code_stream:
            return {
                "equations": {},
                "functions": [],
                "logic_density": 0.0,
                "sum_fxn_impact": 0.0,
                "total_control_flow_ratio": 0.0,
                "raw_imports": [],
                "metadata": ghost_meta,
            }

        # --- THE ANTI-REDOS SHIELD (Line Length Limiter) ---
        # Identifies absurdly long continuous lines (Make .depend files, C hex arrays)
        # and blanks them out before they reach the regex engine. Neutralizes Catastrophic
        # Backtracking while perfectly preserving the file's geometry (mass and LOC).
        safe_lines = []
        for line in code_stream.split("\n"):
            if len(line) > 1500:
                # Preserve indentation and inject a single safe char so it isn't counted as a blank line
                indent = len(line) - len(line.lstrip())
                safe_lines.append(" " * indent + "x" + " " * (len(line) - indent - 1))
            else:
                safe_lines.append(line)
        code_stream = "\n".join(safe_lines)

        try:
            line_count = sum(1 for l in code_stream.splitlines() if l.strip())

            # --- EXISTING STRUCTURAL PIPELINE ---
            segments = self._partition_segments(code_stream, self.primary_lang_id)

            equations, mitigation_telemetry, segment_spatial_maps, extracted_parents = self.coding_analysis(
                segments, regex_telemetry if profile_regex else None
            )

            if extracted_parents:
                # Store the top 3 parent entities to prevent massive string bloat on huge files
                ghost_meta["parent_entity"] = ", ".join(list(dict.fromkeys(extracted_parents))[:3])

            equations = self.comment_analysis(comment_stream, self.primary_lang_id, equations)

            functions, sum_fxn_impact = self._function_slice(
                segments,
                segment_spatial_maps,
                regex_telemetry if profile_regex else None,
            )

            # ---> NEW: FAST CLASS EXTRACTOR & FUNCTION LINKAGE <---
            classes = []
            # Upgraded regex to catch standard OOP entities across polyglot languages
            class_pattern = re.compile(
                r"^\s*(?:export\s+|public\s+|abstract\s+)?(?:class|struct|interface|trait|enum)\s+([a-zA-Z0-9_]+)(?:\s*(?:\(|extends\s+|implements\s+|:\s*)([a-zA-Z0-9_]+))?",
                re.MULTILINE,
            )

            class_matches = list(class_pattern.finditer(code_stream))
            for i, match in enumerate(class_matches):
                start_idx = match.start()
                # Scope ends at the next class declaration, or the end of the file
                end_idx = class_matches[i + 1].start() if i + 1 < len(class_matches) else len(code_stream)

                # Convert raw string indices to line numbers for spatial bounding
                start_line = code_stream.count("\n", 0, start_idx) + 1
                end_line = code_stream.count("\n", 0, end_idx) + 1

                classes.append(
                    {
                        "name": match.group(1),
                        "inheritance": [match.group(2)] if match.group(2) else [],
                        "_start_line": start_line,
                        "_end_line": end_line,
                        "method_count": 0,
                        "state_entanglement": 0.0,
                        "lcom_score": 0.0,
                    }
                )

            # ---> LINK FUNCTIONS TO CLASSES & CALCULATE CLASS PHYSICS <---
            for cls in classes:
                class_methods = []
                for func in functions:
                    # If the function falls within the spatial bounds of the class
                    if cls["_start_line"] <= func.get("start_line", 0) <= cls["_end_line"]:
                        func["parent_class_name"] = cls["name"]
                        class_methods.append(func)

                cls["method_count"] = len(class_methods)

                # State Entanglement: Density of state mutations (flux) inside the class methods
                total_flux = sum(m.get("hit_vector", {}).get("state_mutation", 0) for m in class_methods)
                cls["state_entanglement"] = round((total_flux / max(cls["method_count"], 1)) * 5.0, 2)

                # LCOM (Lack of Cohesion of Methods): Approximation using arguments vs mutations
                total_args = sum(m.get("args", 0) for m in class_methods)
                if cls["method_count"] > 1:
                    cohesion_ratio = total_flux / max(total_args, 1)
                    cls["lcom_score"] = round(max(0.0, min(100.0, 100.0 - (cohesion_ratio * 25.0))), 2)
                else:
                    cls["lcom_score"] = 0.0

                # Erase the temporary spatial boundaries
                del cls["_start_line"]
                del cls["_end_line"]

            branch_hits = equations.get("branch", 0)
            linear_hits = equations.get("structural_boundaries", 0)
            total_control_flow_ratio = round(branch_hits / max(branch_hits + linear_hits, 1), 3)

            # Use the newly standardized keys from the updated coding_analysis
            total_signals = sum(equations.values())
            logic_density = round(total_signals / line_count, 3) if line_count > 0 else 0.0

            # --- NEW: INTRA-FILE ORPHAN & DUPLICATE DETECTOR ---
            import collections

            # Fast, C-backed word frequency counter for the entire file
            token_counts = collections.Counter(re.findall(r"\b\w+\b", code_stream))

            orphan_count = 0
            func_names = [f.get("name", "") for f in functions]
            func_name_counts = collections.Counter(func_names)

            for func in functions:
                func_name = func.get("name", "")
                usage_status = 0  # 0 = Normal

                # Check for Duplicates (Defined multiple times in the same file)
                if func_name and func_name_counts[func_name] > 1:
                    usage_status = 2  # 2 = Duplicate
                elif len(func_name) > 3 and func_name not in {
                    "Unknown_Sat",
                    "Anonymous_Block",
                    "Main",
                    "Declarative_Block",
                }:
                    # If the function name only exists where it was defined, it's an orphan
                    if token_counts[func_name] <= 1:
                        orphan_count += 1
                        usage_status = 1  # 1 = Orphan / Unused

                func["usage_status"] = usage_status

            if orphan_count > 0:
                equations["orphaned_logic"] = orphan_count

            # Calculate total file footprint, preferring the unshielded raw text if available
            file_token_mass = get_token_mass(raw_content if raw_content else code_stream)

            result_payload = {
                "equations": equations,
                "classes": classes,
                "functions": functions,
                "logic_density": logic_density,
                "sum_fxn_impact": sum_fxn_impact,
                "total_control_flow_ratio": total_control_flow_ratio,
                "metadata": ghost_meta,
                "mitigation_telemetry": mitigation_telemetry,
                "token_mass": file_token_mass,
                "financial_read_cost": (
                    round((file_token_mass / 1000000) * 3.00, 5) if file_token_mass is not None else None
                ),
            }
            if profile_regex:
                result_payload["regex_telemetry"] = regex_telemetry
            return result_payload

        except TimeoutError:
            # Let the Hardware Guillotine drop cleanly to the Worker thread!
            raise
        except Exception as e:
            self.logger.error(f"Catastrophic failure during structural splicing: {e}", exc_info=True)
            return {
                "equations": {},
                "functions": [],
                "logic_density": 0.0,
                "sum_fxn_impact": 0.0,
                "total_control_flow_ratio": 0.0,
                "raw_imports": [],
                "metadata": ghost_meta,
            }

    def _decode_comment_stream(self, comment_stream: str) -> Dict[str, str]:
        meta = {"ownership": "Unknown Architect"}
        if not comment_stream:
            return meta

        re_ownership = self.primary_rules.get("ownership")
        ownership_val = None
        if re_ownership:
            try:
                m_owner = re_ownership.search(comment_stream)
                if m_owner:
                    ownership_val = (
                        m_owner.group(m_owner.lastindex).strip() if m_owner.lastindex else m_owner.group(0).strip()
                    )
            except Exception:
                pass

        if ownership_val:
            raw_ownership = re.sub(r"<[^>]+>", "", ownership_val).strip()
            raw_ownership = raw_ownership.rstrip(".,;-")
            if raw_ownership:
                meta["ownership"] = raw_ownership

        # Look for the underscore-prefixed metadata rules
        re_purpose_line = self.primary_rules.get("_meta_purpose_line")
        re_purpose_block = self.primary_rules.get("_meta_purpose_block")
        re_boundary = self.primary_rules.get("_meta_boundary")

        if not (re_purpose_line or re_purpose_block):
            return meta

        # ---> MEMORY CAP <---
        # We only scan the top 500 lines anyway, so hard-cap the string at ~15,000 characters
        # to prevent massive license blocks or generated data from thrashing the regex engine.
        capped_stream = comment_stream[:15000]

        clean_text = re.sub(
            r"^[ \t]*([#/*!\-]+|[Cc][ \t]+)[ \t]*",
            "",
            capped_stream,
            flags=re.MULTILINE,
        )
        lines = clean_text.splitlines()

        active_capture = None
        purpose_buffer = []
        fallback_buffer = []
        has_block_text = False

        for line in lines[:500]:
            line_str = line.strip()

            if active_capture == "block":
                if not line_str:
                    if has_block_text:
                        break
                    else:
                        continue
                if re_boundary and hasattr(re_boundary, "match") and re_boundary.match(line_str):
                    break
                purpose_buffer.append(line_str)
                has_block_text = True
                continue

            if active_capture == "line":
                if (
                    not line_str
                    or (re_boundary and hasattr(re_boundary, "match") and re_boundary.match(line_str))
                    or (re_purpose_block and hasattr(re_purpose_block, "match") and re_purpose_block.match(line_str))
                ):
                    active_capture = None
                else:
                    fallback_buffer.append(line_str)
                    continue

            if re_purpose_block and hasattr(re_purpose_block, "match") and re_purpose_block.match(line_str):
                active_capture = "block"
                purpose_buffer = []
                has_block_text = False
                continue

            if re_purpose_line and hasattr(re_purpose_line, "match") and not purpose_buffer:
                try:
                    m_purpose = re_purpose_line.match(line_str)
                    if m_purpose:
                        active_capture = "line"
                        purpose_text = (
                            m_purpose.group(m_purpose.lastindex).strip()
                            if m_purpose.lastindex
                            else m_purpose.group(0).strip()
                        )
                        if purpose_text:
                            fallback_buffer.append(purpose_text)
                except Exception:
                    pass
                continue

        final_purpose = purpose_buffer if purpose_buffer else fallback_buffer
        if final_purpose:
            p_text = " ".join(final_purpose)
            p_text = re.sub(r"\s+", " ", p_text).strip()
            if p_text:
                meta["purpose"] = p_text[:800] + ("..." if len(p_text) > 800 else "")

        return meta

    def _extract_documentation_tether(self, start_line: int, lang_id: str) -> str:
        """Surgically extracts the human intent (docstring/comments) using exact spatial coordinates."""
        if not hasattr(self, "raw_content_lines") or not self.raw_content_lines:
            return ""

        # Convert the 1-indexed start_line to a 0-indexed array position
        i = start_line - 1
        if i < 0 or i >= len(self.raw_content_lines):
            return ""

        doc_buffer = []

        # 1. Harvest Above (C, Java, JS, Rust, Go, PHP, C#)
        for j in range(i - 1, max(-1, i - 15), -1):
            prev = self.raw_content_lines[j].strip()
            if not prev:
                continue
            if prev.startswith(("#", "//", "/*", "*", "///", "--", "<!--", "dnl", ";", "%")):
                doc_buffer.insert(0, prev)
            elif prev.endswith("*/") or prev.endswith("#>"):
                doc_buffer.insert(0, prev)
            elif prev.startswith("@") or prev.startswith("["):  # Step over decorators safely
                continue
            else:
                break

        # 2. Harvest Below (Python docstrings, MATLAB help, Ruby =begin)
        if lang_id in ("python", "matlab", "ruby", "elixir"):
            for j in range(i + 1, min(len(self.raw_content_lines), i + 10)):
                nxt = self.raw_content_lines[j].strip()
                if not nxt:
                    continue
                if nxt.startswith(('"""', "'''", "%", "#", "=begin")):
                    doc_buffer.append(nxt)
                    if len(nxt) > 3 and (nxt.endswith('"""') or nxt.endswith("'''")):
                        break
                elif len(doc_buffer) > 0:
                    doc_buffer.append(nxt)
                    if nxt.endswith('"""') or nxt.endswith("'''") or nxt == "=end":
                        break
                else:
                    break

        return "\n".join(doc_buffer)[:2000]  # Cap at 2000 chars to prevent DB bloat

    def _partition_segments(self, content: str, primary_id: str) -> List[Tuple[str, str, int]]:
        """Splits content into language segments based on handshake triggers."""
        segments = []
        last_idx = 0
        current_line_offset = 0

        triggers = []
        for h in self.HANDSHAKE_REGISTRY:
            for m in h["trigger"].finditer(content):
                triggers.append(
                    {
                        "start": m.start(),
                        "end_pattern": h["end"],
                        "target": h["target"],
                        "pair": h["pair"],
                        "trigger_end": m.end(),
                    }
                )

        triggers.sort(key=lambda x: x["start"])

        for t in triggers:
            if t["start"] < last_idx:
                continue

            if t["start"] > last_idx:
                chunk = content[last_idx : t["start"]]
                segments.append((primary_id, chunk, current_line_offset))
                current_line_offset += chunk.count("\n")

            if t["pair"]:
                open_char, close_char = t["pair"]
                end_idx = self._find_balanced_end(content, t["start"], open_char, close_char)
            else:
                search_limit = min(t["trigger_end"] + self.HANDSHAKE_LOOKAHEAD_LIMIT, len(content))
                end_match = t["end_pattern"].search(content, pos=t["trigger_end"], endpos=search_limit)
                end_idx = end_match.end() if end_match else len(content)

            chunk = content[t["start"] : end_idx]
            segments.append((t["target"], chunk, current_line_offset))
            current_line_offset += chunk.count("\n")
            last_idx = end_idx

        if last_idx < len(content):
            chunk = content[last_idx:]
            segments.append((primary_id, chunk, current_line_offset))

        return segments if segments else [(primary_id, content, 0)]

    def _find_balanced_end(self, safe_text: str, start_pos: int, opener: str, closer: str) -> int:
        """
        C-Optimized jump-tracking algorithm.
        Expects 'safe_text' where string literals and comments have already been shielded.
        """
        depth = 0
        limit = min(start_pos + self.HANDSHAKE_LOOKAHEAD_LIMIT, len(safe_text))
        pos = start_pos

        while pos < limit:
            # Ask the C-engine to instantly find the next brace, bypassing Python loops
            next_open = safe_text.find(opener, pos, limit)
            next_close = safe_text.find(closer, pos, limit)

            # If there are no more closing braces, the scope is truncated/malformed. Bail out.
            if next_close == -1:
                break

            # If the opener comes next, dive one level deeper
            if next_open != -1 and next_open < next_close:
                depth += 1
                pos = next_open + 1

                if depth > self.MAX_DEPTH:
                    depth = self.MAX_DEPTH

            # If the closer comes next, surface one level
            else:
                depth -= 1
                pos = next_close + 1

                # We have cleanly exited the original scope
                if depth <= 0:
                    return pos

        return limit

    def _correlate_signals(self, targets: List[int], dampeners: List[int], max_distance: int = 500) -> Tuple[int, int]:
        """
        Sweeps two sorted lists of indices to find how many targets are within
        'max_distance' of a dampener. Runs in O(N) linear time.
        """
        if not targets:
            return 0, 0
        if not dampeners:
            return len(targets), 0

        unmitigated_count = 0
        mitigated_count = 0

        damp_idx = 0
        damp_len = len(dampeners)

        for t_pos in targets:
            # Move the dampener pointer forward until it is somewhat near the target
            while damp_idx < damp_len and dampeners[damp_idx] < (t_pos - max_distance):
                damp_idx += 1

            # Check if the closest dampener is within the blast radius
            if damp_idx < damp_len and abs(dampeners[damp_idx] - t_pos) <= max_distance:
                mitigated_count += 1
            else:
                unmitigated_count += 1

        return unmitigated_count, mitigated_count

    def coding_analysis(
        self, segments: List[Tuple[str, str, int]], regex_telemetry: dict = None
    ) -> Tuple[Dict[str, int], Dict[str, int], List[Dict[str, List[int]]], List[str]]:
        counts: Dict[str, int] = {key: 0 for key in self.UNIVERSAL_METRICS_SCHEMA}

        # --- THE FIX: INJECT APPSEC SENSORS ---
        # Force the new Phase 4 sensors into the schema so the LogicSplicer doesn't ignore them
        for appsec_key in ["memory_scraping", "exfiltration_camouflage", "rce_funnel"]:
            if appsec_key not in counts:
                counts[appsec_key] = 0

        mitigations: Dict[str, int] = {
            "mitigated_danger": 0,
            "mitigated_memory_allocs": 0,
            "amplified_rce": 0,
            "amplified_race_conditions": 0,
            "amplified_leaks": 0,
        }
        segment_spatial_maps = []
        extracted_parents = []

        for seg_lang, seg_code, _ in segments:
            # 1. Grab the language-specific rules
            rules = self.languages.get(seg_lang, {}).get("rules", {}).copy()

            seg_len = len(seg_code)

            # ---> NEW: Spatial Map for this segment <---
            spatial_map = {}

            for rule_name, pattern in rules.items():
                if rule_name.startswith("_"):
                    continue

                mapped_key = self.CORE_MAPPING.get(rule_name, rule_name)

                if mapped_key not in counts:
                    self.logger.warning(
                        f"[DIAGNOSTIC] Unregistered rule '{mapped_key}' found in '{seg_lang}'. Ignoring to preserve schema."
                    )
                    continue

                if not pattern:
                    continue

                raw_pat = getattr(pattern, "pattern", str(pattern))
                clean_pat = raw_pat.replace("(?i)", "").replace("(?m)", "").replace("(?s)", "").strip()
                if clean_pat in ("", "()", "(?:)", "^", "$"):
                    continue

                try:
                    t_rule_start = time.perf_counter()

                    # ---> THE UPGRADE: Spatial Mapping instead of raw counting <---
                    if hasattr(pattern, "finditer"):
                        matches = list(pattern.finditer(seg_code))
                        hit_indices = [m.start() for m in matches]

                        # ---> THE LINEAGE EXTRACTOR <---
                        # If the regex has 2+ capture groups, group 2 contains the inheritance mapping
                        if rule_name == "class_start" and pattern.groups >= 2:
                            for m in matches:
                                if m.group(2):
                                    extracted_parents.append(m.group(2).strip())
                    else:
                        hit_indices = [m.start() for m in re.finditer(str(pattern), seg_code)]

                    c = len(hit_indices)

                    t_elapsed = time.perf_counter() - t_rule_start

                    if regex_telemetry is not None:
                        key = f"{seg_lang}::{rule_name}"
                        regex_telemetry[key] = regex_telemetry.get(key, 0.0) + t_elapsed
                    if t_elapsed > 0.5:
                        self.logger.debug(f"[REGEX-TRACE] ^-- SLOW RULE: '{rule_name}' took {t_elapsed:.4f}s")

                    if c > seg_len and seg_len > 0:
                        c = 0
                        hit_indices = []

                    counts[mapped_key] += c
                    spatial_map.setdefault(mapped_key, []).extend(hit_indices)

                except Exception as e:
                    self.logger.error(
                        f"[DIAGNOSTIC] Regex failure in rule '{rule_name}' for language '{seg_lang}': {e}"
                    )

            # ---> NEW: SPATIAL CORRELATION (Runs once per segment) <---

            # ==============================================================================
            # PHASE 4: AI APPSEC & ZERO-TRUST SENSORS (The Checkmarx/Bitwarden Defense)
            # ==============================================================================
            # 0a. The Exfiltration Distance Check
            if "memory_scraping" in spatial_map and "exfiltration_camouflage" in spatial_map:
                # Measures the physical call-path distance between the memory read and the socket
                unmitigated, confirmed_exfiltration = self._correlate_signals(
                    targets=spatial_map["memory_scraping"],
                    dampeners=spatial_map["exfiltration_camouflage"],
                    max_distance=200,  # If they happen within 200 chars of each other, it's a confirmed attack
                )
                counts["memory_scraping"] += confirmed_exfiltration * 100  # Massive penalty multiplier
                mitigations["amplified_leaks"] += confirmed_exfiltration

            # 0b. The RCE Funnel Amplifier
            if "rce_funnel" in spatial_map:
                # RCE funnels inside JS/TS/Python are fatal structural anomalies. Multiply the mass.
                counts["rce_funnel"] += len(spatial_map["rce_funnel"]) * 50
            # ==============================================================================

            # 1. Taint Tracking (RCE Weaponization)
            if "sec_high_risk_execution" in spatial_map and ("sec_io" in spatial_map or "io" in spatial_map):
                io_hits = sorted(spatial_map.get("sec_io", []) + spatial_map.get("io", []))
                _, corroborated_rce = self._correlate_signals(
                    targets=spatial_map["sec_high_risk_execution"],
                    dampeners=io_hits,
                    max_distance=250,
                )
                counts["sec_tainted_injection"] += corroborated_rce
                mitigations["amplified_rce"] += corroborated_rce

            # 2. The Silencer Region (True Safety)
            if "high_risk_execution" in spatial_map and "safety" in spatial_map:
                unmitigated_danger, mitigated_danger = self._correlate_signals(
                    targets=spatial_map["high_risk_execution"],
                    dampeners=spatial_map["safety"],
                    max_distance=500,
                )
                counts["high_risk_execution"] -= mitigated_danger
                mitigations["mitigated_danger"] += mitigated_danger

            # 3. The Race Condition Radar
            if "concurrency" in spatial_map and "state_mutation" in spatial_map:
                unmitigated_flux, _ = self._correlate_signals(
                    targets=spatial_map["state_mutation"],
                    dampeners=spatial_map.get("sync_locks", []),
                    max_distance=300,
                )
                if unmitigated_flux > 0:
                    _, race_conditions = self._correlate_signals(
                        targets=spatial_map["concurrency"],
                        dampeners=spatial_map["state_mutation"],
                        max_distance=150,
                    )
                    counts["concurrency"] += race_conditions * 5
                    mitigations["amplified_race_conditions"] += race_conditions

            # 4. The Active Hemorrhage
            if "sec_hardcoded_secrets" in spatial_map and ("telemetry" in spatial_map or "debug_prints" in spatial_map):
                sinks = sorted(spatial_map.get("telemetry", []) + spatial_map.get("debug_prints", []))
                _, active_leaks = self._correlate_signals(
                    targets=spatial_map["sec_hardcoded_secrets"],
                    dampeners=sinks,
                    max_distance=150,
                )
                counts["sec_hardcoded_secrets"] += active_leaks * 50
                mitigations["amplified_leaks"] += active_leaks

            # 5. The Memory Leak / UAF Tracker
            if "memory_alloc" in spatial_map:
                unmitigated_allocs, _ = self._correlate_signals(
                    targets=spatial_map["memory_alloc"],
                    dampeners=spatial_map.get("cleanup", []),
                    max_distance=800,
                )
                original_allocs = len(spatial_map["memory_alloc"])
                mitigated = original_allocs - unmitigated_allocs

                counts["memory_alloc"] = unmitigated_allocs
                mitigations["mitigated_memory_allocs"] += mitigated

            # 6. The OOM Bomb (Cascading State Flux)
            if "state_mutation" in spatial_map and "branch" in spatial_map:
                # Assuming 'branch' captures while/for loops
                _, cascading_flux = self._correlate_signals(
                    targets=spatial_map["state_mutation"],
                    dampeners=spatial_map["branch"],
                    max_distance=150,  # If state is mutated near heavy branching
                )
                counts["state_mutation"] += cascading_flux * 2  # Double the raw signal
                mitigations["amplified_cascading_flux"] = mitigations.get("amplified_cascading_flux", 0) + cascading_flux

            # Capture indentation signatures
            counts["indent_tabs"] += len(re.findall(r"^\t+(?=\S)", seg_code, flags=re.MULTILINE))
            counts["indent_spaces"] += len(re.findall(r"^[ ]{2,}(?=\S)", seg_code, flags=re.MULTILINE))
            segment_spatial_maps.append(spatial_map)

        return counts, mitigations, segment_spatial_maps, extracted_parents

    def comment_analysis(self, comment_stream: str, lang_id: str, counts: Dict[str, int]) -> Dict[str, int]:
        """
        Analyzes the comment stream for developer intent, technical debt, and traceability.
        Kept strictly separated from active coding analysis to maintain Separation of Concerns.
        """
        if not comment_stream:
            return counts

        rules = self.languages.get(lang_id, {}).get("rules", {})

        # The specific rules designed to extract telemetry from human-readable text
        comment_rules = [
            "dead_code",
            "doc",
            "ownership",
            "planned_debt",
            "fragile_debt",
            "spec_exposure",
        ]

        for rule_name in comment_rules:
            pattern = rules.get(rule_name)
            mapped_key = self.CORE_MAPPING.get(rule_name, rule_name)

            # Ensure the pattern exists and the key is safely in our 51-element schema
            if pattern and mapped_key in counts:
                try:
                    if hasattr(pattern, "findall"):
                        c = len(pattern.findall(comment_stream))
                    else:
                        c = len(re.findall(str(pattern), comment_stream))

                    counts[mapped_key] += c

                except Exception as e:
                    self.logger.error(f"[DIAGNOSTIC] Comment stream regex failure in '{rule_name}': {e}")

        return counts

    # ==============================================================================
    # PRE-PROCESSING HELPERS
    # ==============================================================================

    def _apply_literal_shield(self, text: str, lang_id: str = None) -> str:
        """
        The Smarter Atomic Literal Shield: Handles C++ Raw Strings, Python Triple Quotes,
        and safely isolates Heredocs to prevent Quote Desynchronization.
        """
        if len(text) > 500000:
            self.logger.warning(f"[DIAGNOSTIC-SHIELD] Extremely long block ({len(text)} chars). Shielding may be slow.")

        t_start = time.time()

        def preserve_newlines(m):
            return '""' + "\n" * m.group(0).count("\n")

        # 1. Advanced Atomic Quotes
        # Order is critical: Check multi-char string markers before single quotes.
        # Handles Python ("""), C++ (R"(...)"), and standard strings.
        atomic_string_pattern = (
            r'""".*?"""|'  # Python Triple Double
            r"'''.*?'''|"  # Python Triple Single
            r'R"([a-zA-Z0-9_]*)\(.*?\)\1"|'  # C++ Raw String Literal (e.g. R"EOF(...)EOF")
            r'@"[^"]*(?:""[^"]*)*"|'  # THE FIX: Unrolled C# Verbatim Shield (O(N) safe)
            r'"(?:\\.|[^"\\])*"|'  # Standard Double
            r"'(?:\\.|[^'\\])*'|"  # Standard Single
            r"`(?:\\.|[^`\\])*`"  # Standard Backtick
        )
        text = re.sub(atomic_string_pattern, preserve_newlines, text, flags=re.DOTALL)
        t_quotes = time.time()

        t_heredoc = t_quotes
        t_pct = t_quotes

        # 2. Isolate Heredoc Logic to supported scripting languages
        if lang_id in ["ruby", "perl", "elixir", "shell", "bash"]:
            # State-Machine for Heredocs
            lines = text.split("\n")
            shielded_lines = []
            active_heredoc_delimiter = None

            # In detector.py -> _apply_literal_shield
            heredoc_opener_pattern = re.compile(r'<<[-~]?\s*[\'"]?\\?([a-zA-Z_][a-zA-Z0-9_]*)[\'"]?')

            for line in lines:
                if active_heredoc_delimiter:
                    if line.strip() == active_heredoc_delimiter:
                        shielded_lines.append(line)
                        active_heredoc_delimiter = None
                    else:
                        shielded_lines.append("")
                    continue

                match = heredoc_opener_pattern.search(line)
                if match:
                    delimiter = match.group(1)
                    is_standard_heredoc = (
                        "-" in match.group(0)
                        or "~" in match.group(0)
                        or "'" in match.group(0)
                        or '"' in match.group(0)
                        or delimiter.isupper()
                    )
                    if is_standard_heredoc:
                        active_heredoc_delimiter = delimiter

                shielded_lines.append(line)

            text = "\n".join(shielded_lines)
            t_heredoc = time.time()

            # 3. Shield Ruby % Literals (Strictly gated to Ruby)
            if lang_id == "ruby":
                text = re.sub(r"%[qQwWiIrxs]?\{.*?\}", preserve_newlines, text, flags=re.DOTALL)
                text = re.sub(r"%[qQwWiIrxs]?\[.*?\]", preserve_newlines, text, flags=re.DOTALL)
                text = re.sub(r"%[qQwWiIrxs]?\(.*?\)", preserve_newlines, text, flags=re.DOTALL)
                text = re.sub(r"%[qQwWiIrxs]?\|.*?\|", preserve_newlines, text, flags=re.DOTALL)
                t_pct = time.time()

        if (time.time() - t_start) > 0.5:
            self.logger.warning(
                f"[DIAGNOSTIC-SHIELD] Slow Shield Regex: {time.time() - t_start:.2f}s total "
                f"(Quotes: {t_quotes - t_start:.2f}s | Heredoc: {t_heredoc - t_quotes:.2f}s | "
                f"PCT: {t_pct - t_heredoc:.2f}s)"
            )

        return text

    def _extract_semantic_name(self, line: str, lang_id: str) -> str:
        """Safely extracts function/block names for Mode D logic."""
        lang_key = ScopeParsingRegistry._ALIASES.get(lang_id.lower(), lang_id.lower())
        if lang_key == "shell":
            m = re.search(r"\bfunction\s+([a-zA-Z0-9_.-]+)", line)
            if m:
                return m.group(1)
            m = re.search(r"([a-zA-Z0-9_.-]+)\s*\(\)", line)
            if m:
                return m.group(1)
        elif lang_key in ["ruby", "elixir"]:
            m = re.search(
                r"\b(?:def|class|module|defmacro|defmodule|defp)\s+([a-zA-Z0-9_.:?!]+)",
                line,
            )
            if m:
                return m.group(1)
        elif lang_key == "lua":
            m = re.search(r"\bfunction\s+([a-zA-Z0-9_.:]+)", line)
            if m:
                return m.group(1)
        elif lang_key == "vb":
            m = re.search(
                r"\b(?:sub|function|class|property)\s+([a-zA-Z0-9_]+)",
                line,
                re.IGNORECASE,
            )
            if m:
                return m.group(1)
        return "Anonymous_Block"

    # ==============================================================================
    # THE MASTER DISPATCHER
    # ==============================================================================

    def _function_slice(
        self,
        segments: List[Tuple[str, str, int]],
        segment_spatial_maps: List[Dict[str, List[int]]],
        regex_telemetry: dict = None,
    ) -> Tuple[List[FunctionNode], float]:
        """The Master Routing Dispatcher: Directs the structural signal into the correct integration mode."""
        all_satellites = []
        global_impact = 0.0

        for (lang_id, code, offset), spatial_map in zip(segments, segment_spatial_maps):
            lang_config = self.languages.get(lang_id, {})
            rules = lang_config.get("rules", {})
            family = lang_config.get("lexical_family", "c_style_comment")

            integration_mode = ScopeParsingRegistry.get_mode(lang_id)

            t_mode_start = time.perf_counter()
            mode_name = "Unknown"

            if integration_mode == "mode_d":
                mode_name = "Mode_D_Keywords"
                sats, impact = self._slice_by_keywords(code, lang_id, rules, offset, spatial_map)
            elif integration_mode == "mode_e":
                mode_name = "Mode_E_Terminator"
                sats, impact = self._slice_by_terminator(code, lang_id, rules, offset, spatial_map)
            else:
                # Fallback to standard structural heuristics (Modes A, B, C)
                func_start = rules.get("func_start")
                if not func_start:
                    continue

                # Routed via formal Lexical Family taxonomy
                if lang_id in (
                    "assembly",
                    "agc_assembly",
                    "cobol",
                    "fortran",
                ) or family in ("column_sensitive"):
                    mode_name = "Mode_A_Labels"
                    sats, impact = self._slice_by_labels(code, rules, offset, spatial_map)
                elif family in ("single_line_only", "multi_style_dash") or lang_id in (
                    "python",
                    "yaml",
                ):
                    mode_name = "Mode_C_Indentation"
                    sats, impact = self._slice_by_indentation(code, rules, offset, spatial_map)
                else:
                    mode_name = "Mode_B_Braces"
                    sats, impact = self._slice_by_braces(code, lang_id, rules, offset, spatial_map, family=family)

            # Record the telemetry if profiling is active
            if regex_telemetry is not None and mode_name != "Unknown":
                key = f"{lang_id}::Cartography_{mode_name}"
                regex_telemetry[key] = regex_telemetry.get(key, 0.0) + (time.perf_counter() - t_mode_start)

            all_satellites.extend(sats)
            global_impact += impact

            if len(all_satellites) >= self.MAX_SATELLITES:
                all_satellites = all_satellites[: self.MAX_SATELLITES]
                break

        all_satellites.sort(key=lambda x: x.get("mag", 0), reverse=True)
        return all_satellites, global_impact

    # ==============================================================================
    # INTEGRATION MODES (Slicers)
    # ==============================================================================

    def _slice_by_labels(
        self,
        code: str,
        rules: Dict[str, Any],
        offset: int,
        spatial_map: Dict[str, List[int]],
    ) -> Tuple[List[FunctionNode], float]:
        """[INTEGRATION MODE A] - Greedy Label-Based Scan (Assembly, COBOL)."""
        satellites = []
        sum_fxn_impact = 0.0
        func_start = rules.get("func_start")

        try:
            matches = list(func_start.finditer(code))
        except Exception:
            return [], 0.0

        # --- FAST O(N) LINE TRACKER ---
        current_line_count = offset + 1
        last_counted_idx = 0

        for i, match in enumerate(matches):
            if len(satellites) >= self.MAX_SATELLITES:
                break

            start_idx = match.start()
            greedy_end_idx = matches[i + 1].start() if i + 1 < len(matches) else len(code)

            sandbox = code[start_idx:greedy_end_idx]
            end_offset = len(sandbox)

            if self.assembly_returns:
                ret_matches = list(self.assembly_returns.finditer(sandbox))
                if ret_matches:
                    end_offset = ret_matches[-1].end()

            block = code[start_idx : start_idx + end_offset].strip()
            if not block or len(block.splitlines()) < 2:
                continue

            raw_name = match.group(match.lastindex) if match.lastindex else match.group(0)
            if raw_name is None:
                raw_name = match.group(0)

            if any(m in raw_name for m in ["BOOST_", "TEST", "TEST_F", "TEST_CASE"]):
                raw_name = match.group(0)

            name = self._extract_name(raw_name)

            # --- FAST O(N) LINE TRACKER ---
            current_line_count += code.count("\n", last_counted_idx, start_idx)
            last_counted_idx = start_idx
            start_line = current_line_count

            loc = block.count("\n") + 1
            end_line = start_line + loc - 1

            sat, mag = self._calculate_block_metrics(
                name,
                block,
                loc,
                start_line,
                end_line,
                rules,
                start_idx,
                start_idx + end_offset,
                spatial_map,
            )

            satellites.append(sat)
            sum_fxn_impact += mag

        return satellites, sum_fxn_impact

    def _slice_by_braces(
        self,
        code: str,
        lang_id: str,
        rules: Dict[str, Any],
        offset: int,
        spatial_map: Dict[str, List[int]],
        family: str = "c_style_comment",
    ) -> Tuple[List[FunctionNode], float]:
        """[INTEGRATION MODE B] - Global Recursive Scope Analysis (C-Family & Lisp)."""
        satellites = []
        sum_fxn_impact = 0.0
        func_start = rules.get("func_start")

        if not func_start:
            return [], 0.0

        try:
            matches = list(func_start.finditer(code))
        except Exception:
            return [], 0.0

        # Dynamically set scope bounds based on lexical family
        # We now consistently use curly braces for standard block-style languages.
        opener, closer = "{", "}"
        if lang_id == "lisp":
            opener, closer = "(", ")"

        # 1. High-Performance C-Backed Shield Function
        def fast_shield(m):
            text = m.group(0)
            if "\n" not in text:
                return " " * len(text)
            return "\n".join(" " * len(line) for line in text.split("\n"))

        # 2. The Single-Pass Lexer (Massive I/O Reduction)
        # We use the generic shield pattern for all brace-style and c-style families
        combined_pattern = r'""".*?"""|@"[^"]*(?:""[^"]*)*"|R"([a-zA-Z0-9_]*)\(.*?\)\1"|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`(?:\\.|[^`\\])*`|//[^\n]*|/\*.*?\*/'

        safe_code = re.sub(combined_pattern, fast_shield, code, flags=re.DOTALL)

        # 3. Macro Shields (Strictly Gated to C-Family)
        if lang_id in ("c", "cpp", "objective-c", "cs", "swift"):
            lines = safe_code.splitlines(keepends=True)
            in_dead_branch = False
            dead_nesting_depth = 0
            in_multiline_macro = False

            for i in range(len(lines)):
                line = lines[i]
                stripped = line.lstrip()

                if in_multiline_macro:
                    lines[i] = " " * (len(line) - 1) + "\n" if line.endswith("\n") else " " * len(line)
                    if not stripped.rstrip(" \t\r\n").endswith("\\"):
                        in_multiline_macro = False
                    continue

                if stripped.startswith("#"):
                    if stripped.startswith("#if"):
                        if in_dead_branch:
                            dead_nesting_depth += 1
                    elif stripped.startswith(("#else", "#elif")):
                        if not in_dead_branch and dead_nesting_depth == 0:
                            in_dead_branch = True
                    elif stripped.startswith("#endif"):
                        if in_dead_branch:
                            if dead_nesting_depth > 0:
                                dead_nesting_depth -= 1
                            else:
                                in_dead_branch = False

                    if stripped.startswith("#define"):
                        if stripped.rstrip(" \t\r\n").endswith("\\"):
                            in_multiline_macro = True

                    lines[i] = " " * (len(line) - 1) + "\n" if line.endswith("\n") else " " * len(line)
                    continue

                if in_dead_branch:
                    lines[i] = " " * (len(line) - 1) + "\n" if line.endswith("\n") else " " * len(line)

            safe_code = "".join(lines)

        last_end_idx = 0
        current_line_count = offset + 1
        last_counted_idx = 0

        for match_idx, match in enumerate(matches):
            if len(satellites) >= self.MAX_SATELLITES:
                break

            start_idx = match.start()
            if start_idx < last_end_idx:
                continue

            next_match_start = matches[match_idx + 1].start() if match_idx + 1 < len(matches) else len(code)
            search_limit = min(next_match_start, start_idx + 2000)

            brace_idx = safe_code.find(opener, start_idx, search_limit)
            if brace_idx == -1:
                continue

            end_idx = self._find_balanced_end(safe_code, brace_idx, opener, closer)
            block = code[start_idx:end_idx].strip()
            if not block:
                continue

            raw_name = match.group(match.lastindex) if match.lastindex else match.group(0)
            if any(m in raw_name for m in ["BOOST_", "TEST", "TEST_F", "TEST_CASE"]):
                raw_name = match.group(0)

            name = self._extract_name(raw_name)
            current_line_count += code.count("\n", last_counted_idx, start_idx)
            last_counted_idx = start_idx

            sat, mag = self._calculate_block_metrics(
                name,
                block,
                block.count("\n") + 1,
                current_line_count,
                current_line_count + block.count("\n"),
                rules,
                start_idx,
                end_idx,
                spatial_map,
            )
            satellites.append(sat)
            sum_fxn_impact += mag
            last_end_idx = end_idx

        return satellites, sum_fxn_impact

    def _slice_by_indentation(
        self,
        code: str,
        rules: Dict[str, Any],
        offset: int,
        spatial_map: Dict[str, List[int]],
    ) -> Tuple[List[FunctionNode], float]:
        """[INTEGRATION MODE C] - Density Stratification (Python, YAML)."""
        satellites = []
        sum_fxn_impact = 0.0
        func_start = rules.get("func_start")

        if not func_start:
            return [], 0.0

        # 1. Apply the Index-Aligned Shield
        # Preserves exact character indices and newline counts so safe_code maps 1:1 with code.
        def index_aligned_shield(m):
            text = m.group(0)
            return "".join("\n" if c == "\n" else " " for c in text)

        # Shield Python triple-quotes first to prevent inner-quote collisions
        safe_code = re.sub(r"\"\"\"(.*?)\"\"\"", index_aligned_shield, code, flags=re.DOTALL)
        safe_code = re.sub(r"\'\'\'(.*?)\'\'\'", index_aligned_shield, safe_code, flags=re.DOTALL)

        # Shield standard strings
        safe_code = re.sub(r'"(?:\\.|[^"\\])*"', index_aligned_shield, safe_code, flags=re.DOTALL)
        safe_code = re.sub(r"'(?:\\.|[^'\\])*'", index_aligned_shield, safe_code, flags=re.DOTALL)

        # Shield comments (Python and YAML use #)
        safe_code = re.sub(r"#.*", lambda m: " " * len(m.group(0)), safe_code)

        # Match against safe_code to prevent triggering on words inside docstrings!
        try:
            matches = list(func_start.finditer(safe_code))
        except Exception:
            return [], 0.0

        last_end_idx = 0

        # --- FAST O(N) LINE TRACKER ---
        current_line_count = offset + 1
        last_counted_idx = 0

        for match in matches:
            if len(satellites) >= self.MAX_SATELLITES:
                break

            start_idx = match.start()
            if start_idx < last_end_idx:
                continue

            raw_name = match.group(match.lastindex) if match.lastindex else match.group(0)
            if raw_name is None:
                raw_name = match.group(0)
            name = self._extract_name(raw_name)

            # Find base indent level using the safe_code
            line_start_idx = safe_code.rfind("\n", 0, start_idx) + 1
            first_line = safe_code[line_start_idx : match.end()]
            base_indent = len(first_line) - len(first_line.lstrip())

            end_idx = len(safe_code)
            scan_pos = safe_code.find("\n", match.end())
            if scan_pos == -1:
                scan_pos = len(safe_code)
            else:
                scan_pos += 1

            # --- FAST O(N) INDENT TRACKER ---
            # Replaced O(N^2) array allocations with zero-copy index jumping
            while scan_pos < len(safe_code):
                next_nl = safe_code.find("\n", scan_pos)
                if next_nl == -1:
                    line_end = len(safe_code)
                else:
                    line_end = next_nl + 1

                f_line = safe_code[scan_pos:line_end]
                stripped = f_line.lstrip()

                if stripped:
                    current_indent = len(f_line) - len(stripped)
                    if current_indent <= base_indent:
                        end_idx = scan_pos
                        break

                scan_pos = line_end

            last_end_idx = end_idx

            # Extract the raw payload using the ORIGINAL code to retain the exact executable payload
            block = code[start_idx:end_idx].strip()
            if not block or len(block.splitlines()) < 2:
                continue

            # --- FAST O(N) LINE TRACKER ---
            current_line_count += code.count("\n", last_counted_idx, start_idx)
            last_counted_idx = start_idx
            start_line = current_line_count

            loc = block.count("\n") + 1
            end_line = start_line + loc - 1

            sat, mag = self._calculate_block_metrics(
                name,
                block,
                loc,
                start_line,
                end_line,
                rules,
                start_idx,
                end_idx,
                spatial_map,
            )

            satellites.append(sat)
            sum_fxn_impact += mag

        return satellites, sum_fxn_impact

    def _slice_by_keywords(
        self,
        code: str,
        lang_id: str,
        rules: Dict[str, Any],
        offset: int,
        spatial_map: Dict[str, List[int]],
    ) -> Tuple[List[FunctionNode], float]:
        """[INTEGRATION MODE D] - Semantic Handshake Stack (Shell, Ruby, Lua)."""
        self.logger.debug(f"[DIAGNOSTIC] Mode D: Initiating _slice_by_keywords for {lang_id}")
        config = ScopeParsingRegistry.get_config(lang_id)
        if not config:
            return self._slice_by_braces(code, rules, offset)

        flags = re.IGNORECASE if config.get("ignore_case") else 0
        open_pattern = re.compile("|".join(config["openers"]), flags)
        close_pattern = re.compile("|".join(config["closers"]), flags)

        satellites = []
        sum_fxn_impact = 0.0

        global_dust = []
        current_satellite = []

        stack_depth = 0
        satellite_name = "Main"

        # 1. Apply the comprehensive Atomic Literal Shield
        safe_code = self._apply_literal_shield(code)

        # ---> FAST SINGLE-PASS COMMENT STRIP <---
        # Ensures #var or #foo are not erroneously treated as comments if they are not at the start of a word.
        safe_code = re.sub(r"(^|[ \t])(?:#|--|//).*$", r"\1", safe_code, flags=re.MULTILINE)

        # 2. Split both into parallel arrays
        original_lines = code.splitlines(keepends=True)
        safe_lines = safe_code.splitlines(keepends=True)

        total_lines = len(original_lines)
        self.logger.debug(f"[DIAGNOSTIC] Mode D: Traversing {total_lines} lines...")

        current_line_offset = offset
        sat_start_line = offset + 1
        current_char_offset = 0
        sat_start_char = 0

        lang_key = ScopeParsingRegistry._ALIASES.get(lang_id.lower(), lang_id.lower())

        # 3. Zip them together. We scan the safe_line for triggers, but save the orig_line into the satellite.
        for idx, (orig_line, safe_line) in enumerate(zip(original_lines, safe_lines)):
            opens = len(open_pattern.findall(safe_line))
            closes = len(close_pattern.findall(safe_line))

            # The Ruby/Elixir Inline Modifier Guard
            if lang_key in ["ruby", "elixir"] and opens > 0:
                # Find all valid condition keywords on the line
                inline_mods = len(re.findall(r"(?<![:.])\b(if|unless|while|until)\b(?!:)", safe_line))

                if inline_mods > 0:
                    # Check if one of them is the actual start of the statement
                    if re.search(
                        r"^\s*(?:[a-zA-Z0-9_@.\[\]]+\s*=\s*)?(?:if|unless|while|until)\b",
                        safe_line,
                    ):
                        # Subtract all EXCEPT the one that started the line
                        opens -= inline_mods - 1
                    else:
                        # ALL of them are trailing modifiers (e.g., `return true if x unless y`)
                        opens -= inline_mods

            net_change = opens - closes

            if stack_depth == 0:
                if net_change > 0:
                    satellite_name = self._extract_semantic_name(safe_line, lang_key)
                    current_satellite = [orig_line]
                    stack_depth += net_change
                    sat_start_line = current_line_offset + 1
                    sat_start_char = current_char_offset
                else:
                    global_dust.append(orig_line)
                    stack_depth = max(0, stack_depth + net_change)
            else:
                current_satellite.append(orig_line)
                stack_depth += net_change

                # Check against MAX_DEPTH to prevent infinite saturation overflow
                if stack_depth > self.MAX_DEPTH:
                    self.logger.warning(
                        f"[DIAGNOSTIC] Mode D: Max depth ({self.MAX_DEPTH}) exceeded in {satellite_name}. Clamping."
                    )
                    stack_depth = self.MAX_DEPTH

                if stack_depth <= 0:
                    block = "\n".join(current_satellite).strip()
                    if block:
                        loc = max(len(current_satellite), 1)
                        sat_end_line = current_line_offset + 1
                        sat_end_char = current_char_offset + len(orig_line)
                        sat, mag = self._calculate_block_metrics(
                            satellite_name,
                            block,
                            loc,
                            sat_start_line,
                            sat_end_line,
                            rules,
                            sat_start_char,
                            sat_end_char,
                            spatial_map,
                        )
                        satellites.append(sat)
                        sum_fxn_impact += mag

                    current_satellite = []
                    satellite_name = "Main"
                    stack_depth = 0

            current_line_offset += 1
            current_char_offset += len(orig_line)

        self.logger.debug("[DIAGNOSTIC] Mode D: Finished traversing. Processing remnants...")

        if stack_depth > 0 and current_satellite:
            block = "\n".join(current_satellite).strip()
            if block:
                loc = max(len(current_satellite), 1)
                sat, mag = self._calculate_block_metrics(
                    satellite_name + "_[Truncated]",
                    block,
                    loc,
                    sat_start_line,
                    current_line_offset,
                    rules,
                    sat_start_char,
                    current_char_offset,
                    spatial_map,
                )
                satellites.append(sat)
                sum_fxn_impact += mag

        if global_dust and "".join(global_dust).strip():
            block = "\n".join(global_dust).strip()
            if block:
                loc = max(len(global_dust), 1)
                sat, mag = self._calculate_block_metrics(
                    "__global_context__",
                    block,
                    loc,
                    offset + 1,
                    current_line_offset,
                    rules,
                )
                satellites.append(sat)
                sum_fxn_impact += mag

        self.logger.debug(f"[DIAGNOSTIC] Mode D: Extracted {len(satellites)} satellites.")
        return satellites, sum_fxn_impact

    def _slice_by_terminator(
        self,
        code: str,
        lang_id: str,
        rules: Dict[str, Any],
        offset: int,
        spatial_map: Dict[str, List[int]],
    ) -> Tuple[List[FunctionNode], float]:
        """[INTEGRATION MODE E] - Terminator Cleaving (SQL, Erlang, Prolog)."""
        config = ScopeParsingRegistry.get_config(lang_id)
        if not config:
            return self._slice_by_braces(code, rules, offset)

        terminator_pattern = re.compile(config["terminator"])
        igniter_pattern = re.compile(config["igniter"], re.IGNORECASE)

        satellites = []
        sum_fxn_impact = 0.0
        current_satellite = []
        satellite_name = "Declarative_Block"

        is_orbiting = False
        sat_start_line = offset + 1
        current_line_offset = offset
        current_char_offset = 0
        sat_start_char = 0

        # 1. Apply the shield to the ENTIRE string, preserving newline counts.
        # This prevents multi-line strings from collapsing the parallel line iteration.
        def preserve_newlines(m):
            return '""' + "\n" * m.group(0).count("\n")

        safe_code = re.sub(r'"(?:\\.|[^"\\])*"', preserve_newlines, code, flags=re.DOTALL)
        safe_code = re.sub(r"'(?:\\.|[^'\\])*'", preserve_newlines, safe_code, flags=re.DOTALL)
        safe_code = re.sub(r"`(?:\\.|[^`\\])*`", preserve_newlines, safe_code, flags=re.DOTALL)

        # ---> FAST SINGLE-PASS COMMENT STRIP <---
        # Execute the regex once globally. Prevents 500,000+ regex calls on massive SQL dumps.
        safe_code = re.sub(r"(--|%).*$", "", safe_code, flags=re.MULTILINE)

        # 2. Split both into parallel arrays
        original_lines = code.splitlines(keepends=True)
        safe_lines = safe_code.splitlines(keepends=True)

        # 3. Zip them together. We scan the safe_line for igniters/terminators,
        # but save the orig_line into the satellite block.
        for orig_line, safe_line in zip(original_lines, safe_lines):
            current_line_offset += 1

            if not safe_line.strip() and not is_orbiting:
                sat_start_line = current_line_offset + 1
                current_char_offset += len(orig_line)
                continue

            # Check for block ignition
            if not is_orbiting:
                is_orbiting = True
                sat_start_char = current_char_offset
                match = igniter_pattern.search(safe_line)
                if match:
                    lang_key = ScopeParsingRegistry._ALIASES.get(lang_id.lower(), lang_id.lower())
                    satellite_name = (
                        f"{match.group(1).upper()}_Statement" if "sql" in lang_key else match.group(0).strip()
                    )
                    satellite_name = re.sub(r"[^a-zA-Z0-9_]", "", satellite_name)

            # Build the block using the unaltered original line
            current_satellite.append(orig_line)

            # The Guillotine Drop (Evaluate the safe_line for the terminator)
            if terminator_pattern.search(safe_line):
                block = "\n".join(current_satellite).strip()
                if block:
                    loc = max(len(current_satellite), 1)
                    sat_end_line = current_line_offset
                    sat_end_char = current_char_offset + len(orig_line)
                    sat, mag = self._calculate_block_metrics(
                        satellite_name,
                        block,
                        loc,
                        sat_start_line,
                        sat_end_line,
                        rules,
                        sat_start_char,
                        sat_end_char,
                        spatial_map,
                    )
                    satellites.append(sat)
                    sum_fxn_impact += mag

                # Reset for the next orbit
                current_satellite = []
                satellite_name = "Declarative_Block"
                is_orbiting = False
                sat_start_line = current_line_offset + 1

            current_char_offset += len(orig_line)

        # Process Remnants (Unterminated blocks at the end of the file)
        if current_satellite and "".join(current_satellite).strip():
            block = "\n".join(current_satellite).strip()
            if block:
                loc = max(len(current_satellite), 1)
                sat, mag = self._calculate_block_metrics(
                    satellite_name + "_[Unterminated]",
                    block,
                    loc,
                    sat_start_line,
                    current_line_offset,
                    rules,
                    sat_start_char,
                    current_char_offset,
                    spatial_map,
                )
                satellites.append(sat)
                sum_fxn_impact += mag

        return satellites, sum_fxn_impact

    # ==============================================================================
    # SHARED FUNCTIONAL METRICS ENGINE
    # ==============================================================================

    def _calculate_block_metrics(
        self,
        name: str,
        block: str,
        loc: int,
        start_line: int,
        end_line: int,
        rules: Dict[str, Any],
        start_idx: int = 0,
        end_idx: int = 0,
        spatial_map: Dict[str, List[int]] = None,
    ) -> Tuple[FunctionNode, float]:
        """
        Calculates the structural weight, algorithmic complexity, and hit vector
        for an extracted functional block.

        DEFENSIVE ARCHITECTURE (Big-O without ASTs):
        ASTs require intense compilation overhead to determine cyclomatic nesting depth.
        Because we prioritize functional intent, this engine uses standard indentation
        as a 95% accurate proxy for O(N) complexity at a fraction of the compute cost.
        """
        args_pattern = rules.get("args")

        # --- THE FIX: O(log N) Binary Search for Structural Heuristics ---
        hit_vector = {}
        if spatial_map is not None:
            for key, indices in spatial_map.items():
                left = bisect.bisect_left(indices, start_idx)
                right = bisect.bisect_left(indices, end_idx)
                count = right - left
                if count > 0:
                    hit_vector[key] = count

            branch_hits = hit_vector.get("branch", 0)
            linear_hits = hit_vector.get("structural_boundaries", 0)
        else:
            # Fallback for untested manual calls
            branch_pattern = rules.get("branch")
            linear_pattern = rules.get("structural_boundaries")
            branch_hits = (
                len(branch_pattern.findall(block))
                if hasattr(branch_pattern, "findall")
                else (len(re.findall(str(branch_pattern), block)) if branch_pattern else 0)
            )
            linear_hits = (
                len(linear_pattern.findall(block))
                if hasattr(linear_pattern, "findall")
                else (len(re.findall(str(linear_pattern), block)) if linear_pattern else 0)
            )

        total_hits = branch_hits + linear_hits

        # --- FAST CODING LOC HEURISTIC ---
        # Quickly strip out blank lines and standard single-line comments to find the true logic mass
        total_hits = branch_hits + linear_hits

        # --- FAST CODING LOC HEURISTIC (Syntax Fixed!) ---
        # Quickly strip out blank lines and standard single-line comments to find the true logic mass
        # THE FIX: Preserve leading whitespace to calculate Big-O nesting depth!
        raw_lines = [l for l in block.splitlines() if l.strip() and not l.lstrip().startswith(("#", "//", "/*", "*"))]
        coding_loc = len(raw_lines)

        # --- NEW: BIG-O ALGORITHMIC COMPLEXITY TRACKER ---
        # Uses standard code indentation as a universal proxy for AST nesting depth.
        max_indent = 0
        if raw_lines:
            base_indent = len(raw_lines[0]) - len(raw_lines[0].lstrip())
            for line in raw_lines:
                indent = len(line) - len(line.lstrip())
                # Assume standard 4-space or 1-tab format per scope level
                depth = (indent - base_indent) // 4
                if depth > max_indent:
                    max_indent = depth

        # Clamp between O(1) and O(N^6) to prevent runaway formatting bugs from declaring infinite mass
        big_o_depth = min(max(max_indent, 1), 6)

        # --- NEW: EXPONENTIAL O(2^N) RECURSION TRACKER ---
        # Check if the function's name appears followed by a parenthesis/space inside its own body.
        # We check for > 1 because the first hit is the function definition itself!
        is_recursive = False
        if name and len(name) > 2 and name not in {"Unknown_Sat", "Anonymous_Block", "Main"}:
            # Fast heuristic: Count occurrences. If it appears more than once, it's highly likely recursive.
            occurrence_count = len(re.findall(r"\b" + re.escape(name) + r"\b", block))
            if occurrence_count > 1:
                is_recursive = True

        # --- NEW: FUNCTION-LEVEL DATABASE COMPLEXITY (Data Gravity) ---
        # Mapped to active v6 schemas: 'io' (DB connections/SQL), 'state_mutation' (mutations), and 'serialization_parsing' (JSON/ORMs).
        db_complexity = 0
        if hit_vector:
            db_complexity = (
                (hit_vector.get("io", 0) * 3)
                + (hit_vector.get("serialization_parsing", 0) * 2)
                + (hit_vector.get("state_mutation", 0) * 1)
            )

        # --- NEW: FUNCTION-LEVEL KEYWORD DENSITY (The Micro-Auditor) ---
        # Total structural signals divided by the physical lines of the function.
        total_keyword_hits = sum(hit_vector.values()) if hit_vector else total_hits
        keyword_density = total_keyword_hits / max(loc, 1)

        args_count = 0
        if args_pattern and hasattr(args_pattern, "search"):
            try:
                arg_match = args_pattern.search(block)
                if arg_match:
                    args_str = arg_match.group(arg_match.lastindex) if arg_match.lastindex else arg_match.group(0)
                    if args_str and args_str.strip() != "()":
                        if "," in args_str:
                            args_count = args_str.count(",") + 1
                        else:
                            # Handle space-separated arguments (Lisp/Scheme/Shell)
                            args_count = len(args_str.strip().split())
            except Exception:
                pass

        texture_str = self._classify_function(name, block, rules)

        # ---> THE FIX 1: SIGNAL-ANCHORED LOC <---
        # Cap the 'weight-bearing' lines to 10x the number of actual logic signals.
        # A massive dictionary with 0 signals shrinks to an effective_loc of 10.
        total_signals = branch_hits + linear_hits + args_count
        effective_loc = min(loc, (total_signals + 1) * 10)

        # ---> THE FIX 2: SUB-LINEAR ARGUMENT DAMPENER & BIG-O SCALAR <---
        # Apply a square root to the arguments to prevent combinatorial magnitude explosions
        # on edge-case mega-functions, while preserving the core structural philosophy.
        arg_multiplier = math.sqrt(args_count + 1)

        # Apply Big O Depth as an exponential gravity multiplier.
        # O(N)=1.0x, O(N^2)=1.5x, O(N^3)=2.0x, etc.
        complexity_multiplier = 1.0 + ((big_o_depth - 1) * 0.5)

        # Recursive functions are dangerous and mathematically dense. Double their magnitude.
        if is_recursive:
            complexity_multiplier *= 2.0

        # Calculate magnitude using the dampened arguments, Big-O depth, and logic-bounded length
        magnitude = float((branch_hits + 1) * arg_multiplier * complexity_multiplier + (0.05 * effective_loc))

        # ---> THE FIX: LOGIC TOPOLOGY MATH <---
        # Calculate the Control Flow Ratio and the Fractal Fibonacci Angle (Theta)
        total_cf_signals = branch_hits + linear_hits
        control_flow_ratio = (branch_hits / total_cf_signals) if total_cf_signals > 0 else 0.0
        angle = 22.5 + (1.0 - control_flow_ratio) * 67.5

        # ---> NEW: THE DOCUMENTATION TETHER <---
        # Re-attach the human intent using the exact starting line coordinate!
        docstring = self._extract_documentation_tether(start_line, self.primary_lang_id)

        # ---> NEW: LEVEL 3 WIRING (Function Call Chains) <---
        # We scan the block for any word followed by a parenthesis, minus common language keywords.
        invocation_pattern = re.compile(r"\b([a-zA-Z_]\w*)\s*\(")
        raw_calls = invocation_pattern.findall(block)
        ignore_keywords = {
            "if",
            "for",
            "while",
            "switch",
            "catch",
            "return",
            "sizeof",
            "typeof",
            "alignof",
            "decltype",
            "using",
            "throw",
            "await",
            "import",
            "require",
            "include",
            "def",
            "function",
            "class",
            "print",
            "println",
            "console",
            "log",
            "echo",
            "printf",
            "fmt",
            "assert",
            "expect",
            "require_once",
            "include_once",
            "cast",
            "isinstance",
            "issubclass",
            "hasattr",
            "getattr",
            "setattr",
            "delattr",
            "len",
            "max",
            "min",
            "range",
            "xrange",
            "enumerate",
            "zip",
            "map",
            "filter",
            "list",
            "dict",
            "set",
            "tuple",
            "bool",
            "int",
            "float",
            "str",
            "bytes",
            "bytearray",
            "memoryview",
            "super",
            "try",
            "except",
            "finally",
            "String",
            "Array",
            "Object",
            "Number",
            "Boolean",
        }
        # Deduplicate and filter (excluding the function calling itself recursively)
        calls_out = list(set([c for c in raw_calls if c not in ignore_keywords and c != name]))[:20]

        sat: FunctionNode = {
            "name": name[:40],
            "calls_out_to": calls_out,
            "texture": texture_str,
            "type_id": texture_str,
            "loc": loc,
            "branch_count": branch_hits,
            "branch": branch_hits,
            "args": args_count,
            "args_count": args_count,
            "big_o_depth": big_o_depth,
            "is_recursive": is_recursive,
            "db_complexity": db_complexity,
            "docstring": docstring,
            "logic_angle": round(angle, 2),
            "angle": round(angle, 2),
            "control_flow_ratio": round(control_flow_ratio, 3),
            "cf_ratio": round(control_flow_ratio, 3),
            "magnitude": round(magnitude, 1),
            "mag": round(magnitude, 1),
            "impact": round(magnitude, 1),
            "start_line": start_line,
            "end_line": end_line,
            "hit_vector": hit_vector,
            "keyword_density": round(keyword_density, 3),
            "coding_loc": coding_loc,
            "token_mass": get_token_mass(block),
        }
        return sat, magnitude

    def _extract_name(self, raw_match: str) -> str:
        """
        Heuristic Token Normalizer.
        Safely extracts the functional identifier (function, class, or method name) from a raw
        regex capture block by isolating the last valid alphanumeric token before parameter boundaries.
        """
        match_strip = raw_match.strip()

        # 1. Objective-C Message Passing Normalization
        if match_strip.startswith("-") or match_strip.startswith("+"):
            clean_objc = re.sub(r"^[-+]\s*(?:\([^)]+\))?\s*", "", match_strip)
            clean_objc = clean_objc.split(":")[0].split("(")[0].split("{")[0].strip()
            words = [w for w in re.findall(r"[a-zA-Z0-9_.-]+", clean_objc) if w.strip("_-")]
            return words[0] if words else "Unknown_Block"

        # --- 1.5 Overloaded Operator Extraction (C++) ---
        # Safely extracts overloaded C++ operators before standard token truncation destroys the symbols.
        if "operator" in match_strip:
            # Matches operator symbols, (), [], or type casts like 'operator bool'
            op_match = re.search(
                r"\b(operator\s*(?:\[\s*\]|\(\s*\)|[^a-zA-Z0-9_\s({]+|[a-zA-Z_]\w*(?:\s*\*+)?))",
                match_strip,
            )
            if op_match:
                op_str = op_match.group(1).strip()
                # If it's a symbolic operator (<<, ==, ++, ()), remove all spaces: 'operator <<' -> 'operator<<'
                if not re.search(r"[a-zA-Z]", op_str[8:]):
                    return re.sub(r"\s+", "", op_str)
                else:  # It's a type cast like 'operator int', ensure single spacing standardization
                    return re.sub(r"\s+", " ", op_str)

        # 2. C-Macro Signature Normalization
        clean = re.sub(r"\b(?:ARGS\d+|NOARGS)\b", "", raw_match)

        # ---> 2.5 Test Framework Signature Extraction <---
        # Extracts the actual test name from C++ testing frameworks (BOOST_AUTO_TEST_CASE or GTest's TEST)
        # preventing the engine from logging the macro name itself.
        macro_match = re.search(
            r"(?:BOOST_[A-Z_]+|TEST|TEST_F|TEST_CASE)\s*\(\s*([a-zA-Z0-9_]+)",
            match_strip,
        )
        if macro_match:
            return macro_match.group(1)

        # 3. Standard Token Truncation
        if "$(" in clean:
            # Variable Interpolation Preservation (Makefiles): Do not split variable names by parenthesis
            clean = clean.split(":")[0].strip()
        else:
            # ---> Namespace Resolution Preservation (C++/PHP) <---
            # DEFENSIVE ARCHITECTURE: Rather than utilizing expensive regex lookaheads to ignore
            # double-colons (::) while splitting on single colons (:) for type hints, we utilize
            # a high-speed O(N) string replacement to temporarily mask the namespace operator.
            clean = clean.replace("::", "__NAMESPACE_SCOPE__")

            # Truncate at parameter lists, body openings, or return type hints
            clean = clean.split("(")[0].split("{")[0].split(":")[0].strip()

            # Restore the namespace operator
            clean = clean.replace("__NAMESPACE_SCOPE__", "::")

        # Allow standard characters, plus Makefiles ($/%), and Scopes (:)
        words = [w for w in re.findall(r"[a-zA-Z0-9_./%$():-]+", clean) if w.strip("_-:")]

        return words[-1] if words else "Unknown_Block"

    def _classify_function(self, name: str, block: str, rules: Dict[str, Any]) -> str:
        tag_match = re.search(r"[\@](?:type|gal_type)[:\s]+(\w+)", block, re.IGNORECASE)
        if tag_match:
            return tag_match.group(1).lower()

        name_lower = name.lower()
        if any(v in name_lower for v in ["get", "fetch", "load", "read", "query", "select"]):
            return "io"
        if any(v in name_lower for v in ["set", "write", "save", "update", "delete", "post", "send", "put"]):
            return "mutation"
        if any(v in name_lower for v in ["on", "handle", "click", "submit", "route", "rupt", "task"]):
            return "event"
        if any(
            v in name_lower
            for v in [
                "calc",
                "compute",
                "parse",
                "transform",
                "map",
                "filter",
                "reduce",
                "tcf",
                "ccs",
            ]
        ):
            return "logic"
        if any(v in name_lower for v in ["is", "has", "validate", "check", "ensure"]):
            return "check"
        if any(v in name_lower for v in ["test", "assert", "mock", "stub"]):
            return "verification"

        danger_pattern = rules.get("high_risk_execution")
        io_pattern = rules.get("io")

        if danger_pattern and hasattr(danger_pattern, "search") and danger_pattern.search(block):
            return "high_risk_execution"
        if io_pattern and hasattr(io_pattern, "search") and io_pattern.search(block):
            return "io"

        return "standard"
