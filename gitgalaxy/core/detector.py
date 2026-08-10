# ==============================================================================

# galaxyscope:ignore sec_high_risk_execution
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

# galaxyscope:ignore sec_high_risk_execution

# galaxyscope:ignore sec_high_risk_execution

import bisect
import logging
import math
import re
import time
from typing import Any, ClassVar, Optional, TypedDict, cast

from gitgalaxy.core.spatial_correlation import (
    apply_amplifier_correlations,
    apply_dampener_correlations,
)
from gitgalaxy.core.spatial_correlation import (
    correlate_signals as _correlate_signals_impl,
)
from gitgalaxy.standards.analysis_lens import RECORDING_SCHEMAS
from gitgalaxy.standards.language_standards import LENS_CONFIG

HAS_TIKTOKEN = False
try:
    import tiktoken

    HAS_TIKTOKEN = True
    # cl100k_base is the standard for GPT-4, o1, and a highly accurate proxy for Claude
    ENCODER = tiktoken.get_encoding("cl100k_base")
except ImportError:
    pass


def get_token_mass(text: str) -> Optional[int]:
    """Calculates context window footprint. Returns None if tiktoken is missing to prevent dataset poisoning."""
    if not text:
        return 0
    if HAS_TIKTOKEN:
        return len(ENCODER.encode(text, disallowed_special=()))
    return None


# ==============================================================================

# galaxyscope:ignore sec_high_risk_execution
# GitGalaxy Phase 2.5 & 7.5: Logic Splicer & Topological Mapper
# Strategy Protocol: Fluid-State Counters, Language Sliding & Semantic Modes
# ==============================================================================

# galaxyscope:ignore sec_high_risk_execution


class ClassInfo(TypedDict):
    """A regex-extracted class/struct/interface/trait/enum, with its linked methods' physics."""

    name: str
    inheritance: list[str]
    method_count: int
    state_entanglement: float


class _ClassInfoWithBounds(ClassInfo, total=False):
    # _start_line/_end_line are spatial scratch state, deleted once function
    # linkage is done (see "Erase the temporary spatial boundaries" below) --
    # split into a total=False subclass so those two `del`s stay valid: mypy
    # rejects deleting a key from a `total=True` TypedDict.
    _start_line: int
    _end_line: int


class FunctionNode(TypedDict, total=False):
    """Metadata for a surgically extracted functional logic block."""

    name: str
    parent_class_name: str
    usage_status: int

    # Dual-Key mapping to ensure compatibility with all pipeline versions
    semantic_type: str
    texture: str
    type_id: str

    loc: int
    coding_loc: int
    keyword_density: float

    branch_count: int
    branch: int

    args: int
    args_count: int

    control_flow_angle: float
    logic_angle: float
    angle: float

    control_flow_ratio: float
    cf_ratio: float

    structural_weight: float
    magnitude: float
    mag: float
    impact: float

    start_line: int
    end_line: int
    start_idx: int
    end_idx: int

    docstring: str
    calls_out_to: list[str]
    hit_vector: dict[str, int]
    token_mass: Optional[int]


class LogicData(TypedDict, total=False):
    """The standardized output schema for Strategy compliance."""

    equations: dict[str, int]
    functions: list[FunctionNode]
    logic_density: float
    total_functional_impact: float
    total_control_flow_ratio: float
    raw_imports: list
    metadata: dict[str, str]
    token_mass: int
    financial_read_cost: float


# ==============================================================================

# galaxyscope:ignore sec_high_risk_execution
# THE STRUCTURAL SIGNATURE CONFIGURATION MATRIX
# ==============================================================================

# galaxyscope:ignore sec_high_risk_execution


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
    _ALIASES: ClassVar[dict[str, str]] = {
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

    DEFINITIONS: ClassVar[dict[str, dict[str, Any]]] = {
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

    # #1183: this used to be a hand-maintained duplicate of LENS_CONFIG's
    # HANDSHAKE_REGISTRY (gitgalaxy/standards/language_standards.py) that had
    # drifted out of sync -- it dropped the "^[ \t]*...\b" line-anchoring the
    # canonical config uses, so an unanchored "<script"/"<style" substring
    # matched even inside a string/regex literal (e.g. Python test fixture
    # data describing an embedded-JS trigger), permanently misrouting every
    # function for the rest of the file to the wrong language's rules.
    # Deriving directly from LENS_CONFIG keeps the two in permanent sync.
    # re.M is required for the "^" anchor to match at the start of any line
    # rather than only the start of the whole file -- without it, a genuine
    # mid-file "<script>" (the normal case) would never match either.
    HANDSHAKE_REGISTRY: ClassVar[list[dict[str, Any]]] = [
        {
            "trigger": re.compile(h["trigger"], re.I | re.M),
            "end": re.compile(h["end"], re.I | re.M),
            "target": h["target"],
            "pair": h["pair"],
        }
        for h in LENS_CONFIG["HANDSHAKE_REGISTRY"]
    ]

    def __init__(
        self,
        lang_id: str,
        language_definitions: dict[str, Any],
        parent_logger: Optional[logging.Logger] = None,
    ):
        if parent_logger:
            self.logger = parent_logger.getChild("splicer")
            self.logger.setLevel(parent_logger.level)
        else:
            self.logger = logging.getLogger("splicer")
            self.logger.setLevel(logging.INFO)

        self.primary_lang_id = lang_id.lower() if lang_id else "unknown"
        # Pinned explicitly: LANGUAGE_DEFINITIONS (assigned to this same
        # attribute below, in the AUTO-HEAL branch) has no module-level
        # annotation, so mypy infers its instance-attribute type from that
        # massive nested literal instead of this constructor's declared
        # Dict[str, Any] param -- which doesn't support the plain .get()
        # calls this class relies on throughout.
        self.languages: dict[str, Any] = language_definitions

        lang_config: dict[str, Any] = self.languages.get(self.primary_lang_id, {})
        self.primary_rules: dict[str, Any] = lang_config.get("rules", {})
        self.primary_family = lang_config.get("lexical_family", "c_style_comment")

        self.assembly_returns = re.compile(
            r"\b(?:TC\s+Q|TCF\s+Q|RETURN|RESUME|RELINT|RET|RTS|JMP\s+LR|BLR|END-PERFORM|END-IF|GOBACK|EXIT)\b",
            re.IGNORECASE,
        )

        # #1145: universal (not per-language) variable-declaration-shaped assignment
        # matcher -- same "one regex for every language" precedent as indent_tabs/
        # indent_spaces in coding_analysis(), since identifier casing is a lexical/
        # formatting property, not a language-semantic one that needs 59 hand-tuned
        # per-language regexes. Captures the identifier immediately before an
        # unguarded `=` (`(?!=)` excludes `==`), tolerating an optional bounded,
        # whitespace-terminated prefix -- this reaches the declared name whether
        # it's bare (`x = 5`), keyword-led (`let x = 5`), or C-style typed
        # (`Map<String,Integer> counterMap = ...`) without needing a type-keyword
        # enumeration. `[^=\n]{0,80}` is capped so its overlap with the adjacent
        # `[ \t]+` run (Rule 14) stays a small bounded constant, not unbounded --
        # confirmed linear (not quadratic) via a manual ReDoS scaling sweep.
        self._var_decl_pattern = re.compile(
            r"^[ \t]*(?:[^=\n]{0,80}[ \t]+)?([A-Za-z_]\w{0,63})[ \t]*=(?!=)",
            re.M,
        )

        self.CORE_MAPPING = {
            "branching": "branch",
            "io_ops": "io",
            "safety": "safety",
            "high_risk_execution": "high_risk_execution",
            "concurrency": "concurrency",
            "logic_flux": "state_mutation",
        }

        self.MAX_DEPTH = 50
        self.HANDSHAKE_LOOKAHEAD_LIMIT = 50000

        if self.primary_lang_id not in self.languages or "rules" not in self.languages.get(self.primary_lang_id, {}):
            try:
                from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

                # Apply the healed definitions to the instance state. cast():
                # despite self.languages being pinned to Dict[str, Any] above,
                # reassigning it from LANGUAGE_DEFINITIONS here re-narrows it
                # to LANGUAGE_DEFINITIONS' own (unannotated, wide) inferred
                # type for the rest of this branch -- confirmed via
                # reveal_type that .get() on it then returns `object`, not
                # Any. The cast forces it back to the declared type instead
                # of fighting that narrowing.
                self.languages = cast(dict[str, Any], LANGUAGE_DEFINITIONS)
                # renamed (not reusing lang_config): mypy rejects
                # re-annotating the same name twice in one scope.
                healed_lang_config: dict[str, Any] = self.languages.get(self.primary_lang_id, {})
                self.primary_rules = healed_lang_config.get("rules", {})
                self.primary_family = healed_lang_config.get("lexical_family", "c_style_comment")

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
    ) -> dict[str, Any]:
        """Executes the structural regex pass over refracted code streams."""
        self.raw_content_lines = raw_content.splitlines() if raw_content else []
        regex_telemetry: dict[str, float] = {}

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
        # #694: yaml/json/csv used to sit here too, treated like pure prose --
        # but unlike plaintext (empty rules dict, genuinely nothing to gain),
        # they have real non-empty rules dicts AND prism.py already populates
        # their code_stream correctly (none of the three go through prism.py's
        # Prose Bypass, unlike markdown -- see #691). signal_processor.py's own
        # doc_languages set already excludes all three, correctly treating them
        # as real structured content that can carry genuine risk signal (a
        # malicious package.json postinstall script, a `rm -rf /` in a CI
        # yaml). This gate was the one place still treating them as prose;
        # removing them lets them fall through to the normal code_stream path
        # below, same as every real code language.
        if confidence < 0.42 or self.primary_lang_id in ("plaintext",):
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

        # 1b. Markdown Prose Deflection (Issue #691)
        # Markdown has no functions/control-flow to run coding_analysis against
        # (prism.py's Prose Bypass always routes its entire content into
        # comment_stream, leaving code_stream empty), but it DOES have real
        # structural signatures (lit_code_blocks/lit_diagrams/lit_headers/
        # lit_links) that live in comment_stream. Route it through
        # comment_analysis instead of the blanket empty-return the other
        # prose/structured-data languages above still get -- this leaves
        # coding_loc/doc_loc semantics (and everything downstream of them)
        # completely untouched, since we never touch code_stream here.
        if self.primary_lang_id == "markdown":
            counts = dict.fromkeys(self.UNIVERSAL_METRICS_SCHEMA, 0)
            counts = self.comment_analysis(comment_stream, self.primary_lang_id, counts)
            return {
                "equations": counts,
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

            equations, mitigation_telemetry, segment_spatial_maps, extracted_parents, threat_locations = (
                self.coding_analysis(segments, regex_telemetry if profile_regex else None)
            )

            if extracted_parents:
                # Store the top 3 parent entities to prevent massive string bloat on huge files
                ghost_meta["parent_entity"] = ", ".join(list(dict.fromkeys(extracted_parents))[:3])

            equations = self.comment_analysis(comment_stream, self.primary_lang_id, equations)

            functions, sum_fxn_impact = self._function_slice(
                segments,
                segment_spatial_maps,
                equations,
                mitigation_telemetry,
                regex_telemetry if profile_regex else None,
            )

            # ---> NEW: FAST CLASS EXTRACTOR & FUNCTION LINKAGE <---
            classes: list[_ClassInfoWithBounds] = []
            # Upgraded regex to catch standard OOP entities across polyglot languages
            class_pattern = re.compile(
                r"^\s*(?:export\s+|public\s+|abstract\s+)?(?:class|struct|interface|trait|enum)\s+([a-zA-Z0-9_]+)(?:\s*(?:\(|extends\s+|implements\s+|:\s*)([a-zA-Z0-9_]+))?",
                re.MULTILINE,
            )

            class_matches = list(class_pattern.finditer(code_stream))

            # #1040: a flat "ends at the next class match" boundary truncates
            # an outer class's scope the instant it contains a nested class,
            # since the nested class's own `class` keyword becomes that "next
            # match". Resolve each class's real end via brace-depth (or, for
            # indentation-scoped languages, dedent-depth) tracking instead --
            # same dispatch this engine already uses for Mode B vs Mode C
            # function slicing -- so a nested class's body is correctly
            # consumed as part of its enclosing class rather than cutting it
            # off early. Computed unconditionally (not just when class_matches
            # is non-empty) so class_safe_stream/use_indentation_scoping are
            # never referenced uninitialized below.
            lang_family = self.languages.get(self.primary_lang_id, {}).get("lexical_family", "c_style_comment")
            use_indentation_scoping = self.primary_lang_id in ("python", "yaml") or lang_family in (
                "single_line_only",
                "multi_style_dash",
            )
            class_safe_stream = (
                self._build_indentation_safe_stream(code_stream)
                if use_indentation_scoping
                else self._build_brace_safe_stream(code_stream, self.primary_lang_id)
            )

            for i, match in enumerate(class_matches):
                # Anchored on the class NAME's own position (group 1), not
                # match.start(0): class_pattern's leading `\s*` can itself
                # swallow a blank line sitting before "class", landing
                # match.start(0) on that blank line instead of the
                # declaration's real line -- which would corrupt the
                # brace/indent-depth math below. The name always sits on the
                # class's own line, so it's a reliable anchor regardless.
                start_idx = match.start(1)
                # Old flat boundary, now used only as a fallback for brace-less
                # forward declarations where no real body can be located.
                fallback_end_idx = class_matches[i + 1].start() if i + 1 < len(class_matches) else len(code_stream)
                end_idx = self._resolve_class_scope_end(
                    class_safe_stream, start_idx, fallback_end_idx, use_indentation_scoping
                )

                # Convert raw string indices to line numbers for spatial bounding
                start_line = code_stream.count("\n", 0, start_idx) + 1
                end_line = code_stream.count("\n", 0, end_idx) + 1
                # If end_idx sits exactly at the start of a new line (the
                # indentation resolver's dedent point, or the flat fallback,
                # both land there by construction) that line belongs to
                # whatever comes *next* -- a sibling method after a nested
                # class dedents, or the next class's own header -- not to
                # this class, so don't count it as part of this class's range.
                if 0 < end_idx <= len(code_stream) and code_stream[end_idx - 1] == "\n":
                    end_line -= 1

                classes.append(
                    {
                        "name": match.group(1),
                        "inheritance": [match.group(2)] if match.group(2) else [],
                        "_start_line": start_line,
                        "_end_line": end_line,
                        "method_count": 0,
                        "state_entanglement": 0.0,
                    }
                )

            # ---> LINK FUNCTIONS TO CLASSES & CALCULATE CLASS PHYSICS <---
            # Assign each function to its innermost (most specific) enclosing
            # class first. Nesting-aware scopes mean an outer class's span now
            # correctly contains everything a nested class's span also contains
            # -- so without this step, a nested class's methods would double-
            # count toward every enclosing outer class too, not just the nested
            # class itself.
            class_methods_by_id: dict[int, list[FunctionNode]] = {id(cls): [] for cls in classes}
            for func in functions:
                func_line = func.get("start_line", 0)
                innermost_cls: Optional[_ClassInfoWithBounds] = None
                for cls in classes:
                    if cls["_start_line"] <= func_line <= cls["_end_line"]:
                        if innermost_cls is None or cls["_start_line"] > innermost_cls["_start_line"]:
                            innermost_cls = cls
                if innermost_cls is not None:
                    func["parent_class_name"] = innermost_cls["name"]
                    class_methods_by_id[id(innermost_cls)].append(func)

            for cls in classes:
                class_methods = class_methods_by_id[id(cls)]
                cls["method_count"] = len(class_methods)

                # State Entanglement: Density of state mutations (flux) inside the class methods
                total_flux = sum(m.get("hit_vector", {}).get("state_mutation", 0) for m in class_methods)
                cls["state_entanglement"] = round((total_flux / max(cls["method_count"], 1)) * 5.0, 2)

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
            duplicate_count = 0
            func_names = [f.get("name", "") for f in functions]
            func_name_counts = collections.Counter(func_names)

            for func in functions:
                func_name = func.get("name", "")
                usage_status = 0  # 0 = Normal

                # Check for Duplicates (Defined multiple times in the same file)
                if func_name and func_name_counts[func_name] > 1:
                    usage_status = 2  # 2 = Duplicate
                    duplicate_count += 1
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
            if duplicate_count > 0:
                equations["duplicate_logic"] = duplicate_count

            # --- NEW: NAMING-CONVENTION CLASSIFIER (#1145) ---
            # core_var_decl feeds signal_processor.py's encapsulation_ratio (total_vars)
            # -- until now it was permanently 0, which silently floored that ratio to
            # 0.0 for any file with a single global-state hit. The design_* buckets
            # classify each declared identifier's casing/length for style-consistency
            # and outlier signal.
            for decl_match in self._var_decl_pattern.finditer(code_stream):
                equations["core_var_decl"] += 1
                identifier = decl_match.group(1)

                casing_bucket = self._classify_identifier_casing(identifier)
                if casing_bucket:
                    equations[casing_bucket] += 1

                name_len = len(identifier)
                if name_len <= 2:
                    equations["design_short_vars"] += 1
                elif name_len >= 25:
                    equations["design_long_vars"] += 1

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
                "threat_locations": threat_locations,
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

    @staticmethod
    def _classify_identifier_casing(name: str) -> Optional[str]:
        """Buckets a declared identifier into one mutually-exclusive casing style (#1145)."""
        if re.fullmatch(r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*", name):
            return "design_upper_case"
        if "_" in name and name.islower():
            return "design_snake_case"
        if re.fullmatch(r"[a-z][a-z0-9]*", name):
            # Bare lowercase, no underscore or uppercase (e.g. "count") -- still a
            # valid single-word instance of snake_case, not a distinct style.
            return "design_snake_case"
        if re.fullmatch(r"[A-Z][a-zA-Z0-9]*", name) and not name.isupper():
            return "design_pascal_case"
        if re.fullmatch(r"[a-z][a-zA-Z0-9]*", name):
            return "design_camel_case"
        return None

    def _decode_comment_stream(self, comment_stream: str) -> dict[str, str]:
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
            except Exception as e:
                self.logger.debug(f"Ownership regex extraction failed, leaving 'Unknown Architect': {e}")

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
                except Exception as e:
                    self.logger.debug(f"Purpose-line regex extraction failed, skipping this line: {e}")
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

        doc_buffer: list[str] = []

        # 1. Harvest Above (C, Java, JS, Rust, Go, PHP, C#)
        for j in range(i - 1, max(-1, i - 15), -1):
            prev = self.raw_content_lines[j].strip()
            if not prev:
                continue
            if (
                prev.startswith(("#", "//", "/*", "*", "///", "--", "<!--", "dnl", ";", "%"))
                or prev.endswith("*/")
                or prev.endswith("#>")
            ):
                doc_buffer.insert(0, prev)
            elif prev.startswith("@") or prev.startswith("["):  # Step over decorators safely
                continue
            else:
                break

        # 2. Harvest Below (Python docstrings, MATLAB help, Ruby =begin)
        if lang_id in ("python", "matlab", "ruby", "elixir"):
            in_below_doc = False
            for j in range(i + 1, min(len(self.raw_content_lines), i + 10)):
                nxt = self.raw_content_lines[j].strip()
                if not nxt:
                    continue
                if not in_below_doc:
                    # Only the FIRST non-blank line below the signature is
                    # checked for whether it opens a docstring/comment block.
                    # A subsequent line (e.g. a stand-alone closing '"""')
                    # must never be re-tested against this branch (#246) —
                    # once we're inside the block, only the elif below
                    # applies, regardless of what the line itself starts with.
                    if nxt.startswith(('"""', "'''", "%", "#", "=begin")):
                        doc_buffer.append(nxt)
                        in_below_doc = True
                        # Single-line docstring: opens AND closes on the same
                        # line (e.g. """Summary."""). len(nxt) > 3 excludes a
                        # bare 3-char opening marker with nothing else on it.
                        if len(nxt) > 3 and (nxt.endswith('"""') or nxt.endswith("'''")):
                            break
                    else:
                        break
                else:
                    doc_buffer.append(nxt)
                    if nxt.endswith('"""') or nxt.endswith("'''") or nxt == "=end":
                        break

        return "\n".join(doc_buffer)[:2000]  # Cap at 2000 chars to prevent DB bloat

    def _partition_segments(self, content: str, primary_id: str) -> list[tuple[str, str, int]]:
        """Splits content into language segments based on handshake triggers."""
        segments = []
        last_idx = 0
        current_line_offset = 0

        triggers = [
            {
                "start": m.start(),
                "end_pattern": h["end"],
                "target": h["target"],
                "pair": h["pair"],
                "trigger_end": m.end(),
            }
            for h in self.HANDSHAKE_REGISTRY
            for m in h["trigger"].finditer(content)
        ]

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

    def _resolve_class_scope_end(
        self,
        safe_stream: str,
        header_start: int,
        fallback_end_idx: int,
        use_indentation: bool,
    ) -> int:
        """
        Resolves a class declaration's true end boundary via brace-depth (or,
        for indentation-scoped languages, dedent-depth) tracking, instead of a
        flat "ends at the next class match" boundary -- which truncates an
        outer class's scope the instant it contains a nested class, since the
        nested class's own `class` keyword becomes that "next match" (#1040).
        `fallback_end_idx` -- the old flat boundary -- is used only when no
        real body can be located (e.g. a brace-less forward declaration).
        `safe_stream` must be the same length as the original code_stream
        (shielding preserves newlines), so indices computed here stay valid
        against it.

        Deliberately anchored on `header_start` (`match.start()`) only, never
        `match.end()`: class_pattern's optional inheritance capture
        (`:\\s*([a-zA-Z0-9_]+)`) lets `\\s*` cross a newline, so for a
        brace-less header like `class Inner:` it can walk onto the *next*
        line and capture its first identifier (e.g. the `def` of a nested
        method) as a bogus "inheritance" token -- pushing `match.end()` well
        past the header's own line. Recomputing the header line directly
        from `header_start` sidesteps that pre-existing regex quirk instead
        of relying on a `match.end()` that isn't trustworthy here.
        """
        line_start_idx = safe_stream.rfind("\n", 0, header_start) + 1
        header_line_end = safe_stream.find("\n", header_start)
        header_line_end = len(safe_stream) if header_line_end == -1 else header_line_end

        if use_indentation:
            header_line = safe_stream[line_start_idx:header_line_end]
            base_indent = len(header_line) - len(header_line.lstrip())

            scan_pos = header_line_end + 1 if header_line_end < len(safe_stream) else len(safe_stream)

            while scan_pos < len(safe_stream):
                next_nl = safe_stream.find("\n", scan_pos)
                line_end = len(safe_stream) if next_nl == -1 else next_nl + 1
                line = safe_stream[scan_pos:line_end]
                stripped = line.lstrip()
                if stripped:
                    indent = len(line) - len(stripped)
                    if indent <= base_indent:
                        return scan_pos
                scan_pos = line_end
            return len(safe_stream)

        search_limit = min(header_start + 2000, len(safe_stream))
        brace_idx = safe_stream.find("{", header_start, search_limit)
        if brace_idx == -1:
            return fallback_end_idx
        return self._find_balanced_end(safe_stream, brace_idx, "{", "}")

    def _correlate_signals(self, targets: list[int], dampeners: list[int], max_distance: int = 500) -> tuple[int, int]:
        """
        Sweeps two sorted lists of indices to find how many targets are within
        'max_distance' of a dampener. Runs in O(N) linear time.

        Extracted to gitgalaxy.core.spatial_correlation (#346) so the same
        primitive is reusable outside this class; kept here as a thin
        delegating wrapper for backward compatibility with existing callers.
        """
        return _correlate_signals_impl(targets, dampeners, max_distance)

    def coding_analysis(
        self, segments: list[tuple[str, str, int]], regex_telemetry: Optional[dict] = None
    ) -> tuple[dict[str, int], dict[str, int], list[dict[str, list[int]]], list[str], dict[str, list[int]]]:
        counts: dict[str, int] = dict.fromkeys(self.UNIVERSAL_METRICS_SCHEMA, 0)

        # --- THE FIX: INJECT APPSEC SENSORS ---
        # Force the new Phase 4 sensors into the schema so the LogicSplicer doesn't ignore them
        for appsec_key in ["memory_scraping", "exfiltration_camouflage", "rce_funnel"]:
            if appsec_key not in counts:
                counts[appsec_key] = 0

        mitigations: dict[str, int] = {
            "mitigated_danger": 0,
            "mitigated_memory_allocs": 0,
            "amplified_rce": 0,
            "amplified_race_conditions": 0,
            "amplified_leaks": 0,
        }
        segment_spatial_maps = []
        extracted_parents: list[str] = []
        threat_locations: dict[str, list[int]] = {}

        for seg_lang, seg_code, current_line_offset in segments:
            # 1. Grab the language-specific rules
            rules = self.languages.get(seg_lang, {}).get("rules", {}).copy()

            seg_len = len(seg_code)

            # ---> NEW: Spatial Map for this segment <---
            spatial_map: dict[str, list[int]] = {}

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

                        # ---> NEW: Offset to LOC Conversion <---
                        for m in matches:
                            line_number = current_line_offset + seg_code.count("\n", 0, m.start()) + 1
                            threat_locations.setdefault(mapped_key, []).append(line_number)

                        # ---> THE LINEAGE EXTRACTOR <---
                        # If the regex has 2+ capture groups, group 2 contains the inheritance mapping
                        if rule_name == "class_start" and pattern.groups >= 2:
                            extracted_parents.extend(m.group(2).strip() for m in matches if m.group(2))
                    else:
                        matches = list(re.finditer(str(pattern), seg_code))
                        hit_indices = [m.start() for m in matches]

                        # ---> NEW: Offset to LOC Conversion <---
                        for m in matches:
                            line_number = current_line_offset + seg_code.count("\n", 0, m.start()) + 1
                            threat_locations.setdefault(mapped_key, []).append(line_number)

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

            # galaxyscope:ignore sec_high_risk_execution
            # PHASE 4: AI APPSEC & ZERO-TRUST SENSORS (The Checkmarx/Bitwarden Defense)
            # ==============================================================================

            # galaxyscope:ignore sec_high_risk_execution
            # 0a. The Exfiltration Distance Check has been RELOCATED (#102) to
            # apply_amplifier_correlations() in gitgalaxy.core.spatial_correlation,
            # called from _function_slice() -- it was the one correlate() pair
            # #346/#348 missed when they enumerated and migrated the other six,
            # so it kept running flat/unscoped after everything else had moved
            # to same-function scoping.

            # 0b. The RCE Funnel Amplifier
            if "rce_funnel" in spatial_map:
                # RCE funnels inside JS/TS/Python are fatal structural anomalies. Multiply the mass.
                counts["rce_funnel"] += len(spatial_map["rce_funnel"]) * 50
            # ==============================================================================

            # galaxyscope:ignore sec_high_risk_execution

            # 1. Taint Tracking (RCE Weaponization), 2. The Silencer Region,
            # 3. The Race Condition Radar, 5. The Memory Leak / UAF Tracker, and
            # 6. The OOM Bomb have all been RELOCATED (#346 phase 1, #348 phase 2)
            # to apply_dampener_correlations()/apply_amplifier_correlations() in
            # gitgalaxy.core.spatial_correlation, called from _function_slice()
            # once real satellite/function boundaries exist -- coding_analysis()
            # runs before those boundaries are computed, so none of these six
            # pairs ever had real scope available to them here.
            #
            # 4. The Active Hemorrhage is NOT relocated to that same in-detector
            # correlation step: its target key ("sec_hardcoded_secrets") is the
            # Passive Security Lens Observer name, only ever populated by
            # security_lens.py in galaxyscope.py's Phase 5.5 -- strictly after
            # this function (and _function_slice()) have both already returned.
            # It is instead reimplemented as a genuine post-hoc correlation in
            # galaxyscope.py, against the persisted threat_locations ledger, via
            # spatial_correlation.correlate_against_ledger() (#348).

            # Capture indentation signatures
            counts["indent_tabs"] += len(re.findall(r"^\t+(?=\S)", seg_code, flags=re.MULTILINE))
            counts["indent_spaces"] += len(re.findall(r"^[ ]{2,}(?=\S)", seg_code, flags=re.MULTILINE))
            segment_spatial_maps.append(spatial_map)

        return counts, mitigations, segment_spatial_maps, extracted_parents, threat_locations

    def comment_analysis(self, comment_stream: str, lang_id: str, counts: dict[str, int]) -> dict[str, int]:
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
            # Literate-Programming Extension Pack (#691): these only exist on
            # markdown's rules dict today, so this is a no-op for every other
            # language -- same graceful-fallback shape as the six keys above.
            "lit_code_blocks",
            "lit_diagrams",
            "lit_headers",
            "lit_links",
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

    # galaxyscope:ignore sec_high_risk_execution
    # PRE-PROCESSING HELPERS
    # ==============================================================================

    # galaxyscope:ignore sec_high_risk_execution

    def _apply_literal_shield(self, text: str, lang_id: Optional[str] = None) -> str:
        """
        The Smarter Atomic Literal Shield: Handles C++ Raw Strings, Python Triple Quotes,
        and safely isolates Heredocs to prevent Quote Desynchronization.
        """
        if len(text) > 500000:
            self.logger.warning(f"[DIAGNOSTIC-SHIELD] Extremely long block ({len(text)} chars). Shielding may be slow.")

        t_start = time.time()

        # #1184: comments are folded into the SAME alternation as the quote
        # patterns below (see atomic_string_pattern's trailing "comment"
        # branch) instead of being stripped in a separate later pass -- a
        # separate pass let an English contraction apostrophe inside a "#"/
        # "--"/"//" comment (don't, it's, wasn't) get treated as a real
        # string-open quote by the single-quote alternative, pairing with
        # whatever "'" came next anywhere later in the code and blanking out
        # every real line in between (silently dropping whole functions from
        # extraction downstream in `_slice_by_keywords`). One combined pass
        # lets whichever construct -- string or comment -- starts first at a
        # given position atomically claim its whole span, so an apostrophe
        # already inside a claimed comment is never independently
        # reconsidered as a string delimiter. Mirrors
        # `_build_brace_safe_stream`'s existing single-pass design, and the
        # identical fix in `_build_indentation_safe_stream`.
        def preserve_newlines(m):
            # groupdict().get(...) rather than m.group("comment") -- this
            # closure is also reused below for the Ruby %-literal shield
            # pass, whose pattern has no "comment" group at all, and
            # m.group() on a group name absent from the ORIGINATING pattern
            # raises IndexError rather than returning None.
            if m.groupdict().get("comment") is not None:
                return ""
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
            r"`(?:\\.|[^`\\])*`|"  # Standard Backtick
            # Comment marker must be at line-start or preceded by whitespace
            # (guards against e.g. shell's "$#" positional-arg-count being
            # mistaken for a comment). Same marker set previously stripped
            # by `_slice_by_keywords`'s own post-hoc pass.
            r"(?:^|(?<=[ \t]))(?P<comment>#|--|//)[^\n]*"
        )
        text = re.sub(atomic_string_pattern, preserve_newlines, text, flags=re.DOTALL | re.MULTILINE)
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

    # galaxyscope:ignore sec_high_risk_execution
    # THE MASTER DISPATCHER
    # ==============================================================================

    # galaxyscope:ignore sec_high_risk_execution

    def _function_slice(
        self,
        segments: list[tuple[str, str, int]],
        segment_spatial_maps: list[dict[str, list[int]]],
        counts: dict[str, int],
        mitigations: dict[str, int],
        regex_telemetry: Optional[dict] = None,
    ) -> tuple[list[FunctionNode], float]:
        """The Master Routing Dispatcher: Directs the structural signal into the correct integration mode."""
        all_satellites: list[FunctionNode] = []
        global_impact = 0.0

        for (lang_id, code, offset), spatial_map in zip(segments, segment_spatial_maps):
            lang_config = self.languages.get(lang_id, {})
            rules = lang_config.get("rules", {})
            family = lang_config.get("lexical_family", "c_style_comment")

            integration_mode = ScopeParsingRegistry.get_mode(lang_id)

            t_mode_start = time.perf_counter()
            # NOT dead despite CodeQL's py/multiple-definition flag: the "no
            # func_start rule for this language" fallthrough below leaves this
            # unassigned, and the `mode_name != "Unknown"` check further down
            # relies on that sentinel surviving. Removing this would crash
            # with UnboundLocalError on that path.
            mode_name = "Unknown"
            sats: list[FunctionNode] = []
            impact = 0.0

            if integration_mode == "mode_d":
                mode_name = "Mode_D_Keywords"
                sats, impact = self._slice_by_keywords(code, lang_id, rules, offset, spatial_map)
            elif integration_mode == "mode_e":
                mode_name = "Mode_E_Terminator"
                sats, impact = self._slice_by_terminator(code, lang_id, rules, offset, spatial_map)
            else:
                # Fallback to standard structural heuristics (Modes A, B, C)
                func_start = rules.get("func_start")
                if func_start:
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
                        sats, impact = self._slice_by_braces(code, lang_id, rules, offset, spatial_map)
                # else: no func_start rule for this language at all -- sats stays [],
                # and the dampener correlation below falls back to flat behavior for
                # this segment (see apply_dampener_correlations()).

            # Record the telemetry if profiling is active
            if regex_telemetry is not None and mode_name != "Unknown":
                key = f"{lang_id}::Cartography_{mode_name}"
                regex_telemetry[key] = regex_telemetry.get(key, 0.0) + (time.perf_counter() - t_mode_start)

            # --- SATELLITE-SCOPED CORRELATION (#346 phase 1, #348 phase 2) ---
            # Runs for every segment unconditionally, using THIS segment's own
            # satellite ranges.
            sat_ranges = sorted(
                (sat["start_idx"], sat["end_idx"]) for sat in sats if "start_idx" in sat and "end_idx" in sat
            )
            apply_dampener_correlations(spatial_map, sat_ranges, counts, mitigations)
            apply_amplifier_correlations(spatial_map, sat_ranges, counts, mitigations)

            all_satellites.extend(sats)
            global_impact += impact

        all_satellites.sort(key=lambda x: x.get("mag", 0), reverse=True)
        return all_satellites, global_impact

    # ==============================================================================

    # galaxyscope:ignore sec_high_risk_execution
    # INTEGRATION MODES (Slicers)
    # ==============================================================================

    # galaxyscope:ignore sec_high_risk_execution

    def _slice_by_labels(
        self,
        code: str,
        rules: dict[str, Any],
        offset: int,
        spatial_map: dict[str, list[int]],
    ) -> tuple[list[FunctionNode], float]:
        """[INTEGRATION MODE A] - Greedy Label-Based Scan (Assembly, COBOL)."""
        satellites: list[FunctionNode] = []
        sum_fxn_impact = 0.0
        func_start = rules.get("func_start")

        try:
            # If func_start is None (key missing from rules), .finditer()
            # raises AttributeError, which the except below already handles --
            # mypy just can't see that the try/except is the actual guard here.
            matches = list(func_start.finditer(code))  # type: ignore[union-attr]
        except Exception:
            return [], 0.0

        # --- FAST O(N) LINE TRACKER ---
        current_line_count = offset + 1
        last_counted_idx = 0

        for i, match in enumerate(matches):
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

    def _build_brace_safe_stream(self, code: str, lang_id: str) -> str:
        """
        Shields string/char literals and (for C-family languages) dead
        #if/#else macro branches so a brace-balance scan isn't fooled by a
        literal `{`/`}` inside them. Shared by `_slice_by_braces` and the
        nesting-aware class-boundary scanner (#1040), both of which need a
        text stream whose only real braces are structural code -- same
        length as `code` (shielding preserves newlines) so every index
        computed against it stays valid against the original.
        """

        def fast_shield(m):
            text = m.group(0)
            if "\n" not in text:
                return " " * len(text)
            return "\n".join(" " * len(line) for line in text.split("\n"))

        # Rust uses single quotes for lifetimes (e.g. 'a), so a greedy string match corrupts ASTs.
        single_quote = r"'(?:\\.|[^'\\])*'"
        if lang_id == "rust":
            single_quote = r"'(?:\\.|[^'\\]){0,10}'"

        combined_pattern = (
            r'""".*?"""|@"[^"]*(?:""[^"]*)*"|R"([a-zA-Z0-9_]*)\(.*?\)\1"|'
            r'"(?:\\.|[^"\\])*"|' + single_quote + r"|`(?:\\.|[^`\\])*`|//[^\n]*|/\*.*?\*/"
        )

        safe_code = re.sub(combined_pattern, fast_shield, code, flags=re.DOTALL)

        # Macro Shields (Strictly Gated to C-Family)
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

        return safe_code

    def _slice_by_braces(
        self,
        code: str,
        lang_id: str,
        rules: dict[str, Any],
        offset: int,
        spatial_map: dict[str, list[int]],
    ) -> tuple[list[FunctionNode], float]:
        """[INTEGRATION MODE B] - Global Recursive Scope Analysis (C-Family & Lisp)."""
        satellites: list[FunctionNode] = []
        sum_fxn_impact = 0.0
        func_start = rules.get("func_start")

        if not func_start:
            return [], 0.0

        # Dynamically set scope bounds based on lexical family
        # We now consistently use curly braces for standard block-style languages.
        opener, closer = "{", "}"
        if lang_id == "lisp":
            opener, closer = "(", ")"

        safe_code = self._build_brace_safe_stream(code, lang_id)

        # BUG FIX (epic #813, extraction hardening, #814/#815): func_start
        # used to be matched against the raw, unshielded `code` -- computed
        # above, BEFORE `safe_code` existed. That let a single-line string
        # literal or comment containing function-shaped text (e.g. `let
        # query = "function Foo() {";`) false-positive-match, since
        # javascript's/typescript's func_start regex is `\b`-anchored (not
        # `^`-anchored) and has no way to know it's inside a string/comment
        # on its own. `safe_code` already exists at this point specifically
        # to solve this for the downstream brace search -- matching against
        # it here instead of `code` closes the same gap for the match
        # itself. `safe_code` is guaranteed the same length as `code`
        # (shielding replaces matched spans with same-length whitespace), so
        # every index computed from `matches` below remains valid against
        # the original `code` for slicing.
        #
        # Gated to javascript/typescript only, NOT applied to every Mode B
        # language: verifying this fix against the real crucible corpus
        # surfaced a pre-existing, separate bug in `prism.py`'s comment/
        # string stripping for PHP (#859, FIXED -- the broken
        # PHP_MULTILINE_STRING extraction step was removed entirely) --
        # `combined_pattern`'s shielding already relies on `code_stream`
        # being clean, and for at least two real PHP corpus files it wasn't,
        # causing a multi-thousand-character false shield match. That was
        # harmless before this fix because the brace search's blast radius
        # is naturally bounded (a bounded window, one brace lookup) -- but
        # matching *all* of func_start's positions against a corrupted
        # `safe_code` (this fix's approach) turned that latent corruption
        # into wholesale loss of real functions for those files (confirmed:
        # one file dropped from 1 real function detected to 0, with a 17x
        # structural-magnitude blowup). #859 is now fixed, so broadening
        # this gate to other Mode B languages is unblocked -- but still do
        # it as its own audited PR (confirm no other language has a similar
        # latent prism.py gap first), not as a drive-by expansion here.
        try:
            matches = list(func_start.finditer(safe_code))
        except Exception:
            return [], 0.0

        # #1041: this used to skip any match whose start fell before the
        # previously accepted match's end ("if start_idx < last_end_idx:
        # continue"), on the theory that it must already be inside an
        # in-progress function. But a nested/inner function declaration
        # necessarily starts before its enclosing function's end -- so that
        # guard silently dropped every nested function instead of counting
        # it. It's unnecessary anyway: each match below resolves its own end
        # independently via `_find_balanced_end`'s brace-depth tracking from
        # its OWN opening brace, so a nested match already gets a correctly
        # bounded (and correctly nested) scope on its own, without needing
        # to inherit or compare against any prior match's boundary.
        current_line_count = offset + 1
        last_counted_idx = 0

        for match_idx, match in enumerate(matches):
            start_idx = match.start()

            next_match_start = matches[match_idx + 1].start() if match_idx + 1 < len(matches) else len(code)
            search_limit = min(next_match_start, start_idx + 2000)

            # #789: csharp's func_start regex (unlike every other C-family
            # language here) doesn't consume the parameter list or require
            # a terminator -- it stops matching right at the opening `(`,
            # deferring entirely to the generic brace search below. That
            # search alone has two gaps for csharp specifically: (1) a bare
            # top-level call statement with no enclosing brace at all (C#
            # 9+ top-level statements, e.g. `Environment.Exit(0);`) would
            # get whatever `{` the bounded window found downstream
            # (typically an unrelated later block) hallucinated as its
            # body, and (2) expression-bodied members
            # (`Square(int x) => x * x;`, idiomatic since C# 6) have no `{`
            # at all and were never counted as functions. Both are closed
            # here by finding the parameter list's own closing paren first,
            # then checking whether a `{`, an expression-bodied `=>`, or a
            # bare `;` comes first immediately after it -- a `;` before
            # either means this was never a real function signature.
            # Gated to csharp only; every other Mode-B language keeps the
            # exact original brace-only behavior.
            if lang_id == "csharp":
                params_end_idx = self._find_balanced_end(safe_code, match.end() - 1, "(", ")")
                brace_idx = safe_code.find(opener, params_end_idx, search_limit)
                arrow_idx = safe_code.find("=>", params_end_idx, search_limit)
                semi_idx = safe_code.find(";", params_end_idx, search_limit)

                # Whichever of the three appears first (a -1 "not found"
                # sorts last) decides what this match actually is.
                candidates = [(idx, kind) for idx, kind in ((brace_idx, "brace"), (arrow_idx, "arrow")) if idx != -1]
                if semi_idx != -1 and (not candidates or semi_idx < min(idx for idx, _ in candidates)):
                    continue  # a bare statement -- `;` arrived before any real terminator
                if not candidates:
                    continue  # neither a brace nor an arrow ever showed up in the window
                idx, kind = min(candidates, key=lambda pair: pair[0])
                if kind == "brace":
                    end_idx = self._find_balanced_end(safe_code, idx, opener, closer)
                else:
                    semi_after_arrow = safe_code.find(";", idx, search_limit)
                    if semi_after_arrow == -1:
                        continue
                    end_idx = semi_after_arrow + 1
            else:
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

        return satellites, sum_fxn_impact

    def _build_indentation_safe_stream(self, code: str) -> str:
        """
        Index-aligned shield for indentation-depth scans: blanks out
        triple/single-quoted string and `#`-comment content so a dedented
        line inside a docstring can't be mistaken for the real end of a
        function/class body, while preserving newlines so every index
        still maps 1:1 to `code`. Shared by `_slice_by_indentation` and
        the nesting-aware class-boundary scanner (#1040).

        #1184: strings and comments MUST be shielded in one combined-
        alternation pass, not sequential independent re.sub calls. Stripping
        comments in a separate LAST pass (the old approach) let an English
        contraction apostrophe inside a "#" comment (don't, it's, wasn't)
        get treated as a real string-open quote by the single-quote pass
        that ran before it -- it would then pair with whatever "'" came
        next anywhere later in the file and blank out every real line
        (including "def" lines) in between, silently dropping entire
        contiguous ranges of functions from extraction. A single pass lets
        whichever construct -- string or comment -- starts first at a given
        position atomically claim its whole span, so an apostrophe already
        inside a claimed comment is never independently reconsidered as a
        string delimiter. Mirrors `_build_brace_safe_stream`'s existing
        single-pass design, which never had this bug for the same reason.
        """

        def index_aligned_shield(m):
            text = m.group(0)
            return "".join("\n" if c == "\n" else " " for c in text)

        # Order matters: triple-quote markers must precede the single-char
        # quote patterns, or e.g. the double-quote alternative would match
        # the first two characters of a `"""..."""` as an empty `""` string.
        combined_pattern = (
            r'"""(?:.*?)"""|'
            r"'''(?:.*?)'''|"
            r'"(?:\\.|[^"\\])*"|'
            r"'(?:\\.|[^'\\])*'|"
            r"#[^\n]*"  # Python and YAML both use "#" for comments
        )
        return re.sub(combined_pattern, index_aligned_shield, code, flags=re.DOTALL)

    def _slice_by_indentation(
        self,
        code: str,
        rules: dict[str, Any],
        offset: int,
        spatial_map: dict[str, list[int]],
    ) -> tuple[list[FunctionNode], float]:
        """[INTEGRATION MODE C] - Density Stratification (Python, YAML)."""
        satellites: list[FunctionNode] = []
        sum_fxn_impact = 0.0
        func_start = rules.get("func_start")

        if not func_start:
            return [], 0.0

        # 1. Apply the Index-Aligned Shield
        # Preserves exact character indices and newline counts so safe_code maps 1:1 with code.
        safe_code = self._build_indentation_safe_stream(code)

        # Match against safe_code to prevent triggering on words inside docstrings!
        try:
            matches = list(func_start.finditer(safe_code))
        except Exception:
            return [], 0.0

        # #1041: no longer skips matches whose start falls before the
        # previously accepted match's end -- see the identical fix (and
        # rationale) in `_slice_by_braces` above. Here each match resolves
        # its own end independently via the dedent scan below, from its OWN
        # indent level, so a nested def already gets a correctly bounded
        # (and correctly nested) scope on its own.

        # --- FAST O(N) LINE TRACKER ---
        current_line_count = offset + 1
        last_counted_idx = 0

        for match in matches:
            start_idx = match.start()

            raw_name = match.group(match.lastindex) if match.lastindex else match.group(0)
            if raw_name is None:
                raw_name = match.group(0)
            name = self._extract_name(raw_name)

            # Find base indent level using the safe_code
            line_start_idx = safe_code.rfind("\n", 0, start_idx) + 1
            first_line = safe_code[line_start_idx : match.end()]
            base_indent = len(first_line) - len(first_line.lstrip())

            end_idx = len(safe_code)

            # #1199: func_start's regex ends right at the signature's opening
            # "(" (it never consumes the parameter list), so a signature that
            # wraps onto multiple physical lines leaves that "(" unclosed at
            # match.end(). The old code started the dedent scan on the very
            # next line -- for a wrapped signature, its closing "):" line is
            # typically re-dedented back to the def's own indent level, which
            # looked identical to a sibling statement ending the function and
            # truncated the block before the real body (or even the closing
            # paren) was ever included. Walk the signature's own paren depth
            # back to 0 first so the dedent scan only ever begins on the first
            # line that's genuinely past the signature.
            sig_scan = match.end()
            paren_depth = safe_code.count("(", start_idx, match.end()) - safe_code.count(")", start_idx, match.end())
            while sig_scan < len(safe_code) and paren_depth > 0:
                ch = safe_code[sig_scan]
                if ch == "(":
                    paren_depth += 1
                elif ch == ")":
                    paren_depth -= 1
                sig_scan += 1

            scan_pos = safe_code.find("\n", sig_scan)
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
        rules: dict[str, Any],
        offset: int,
        spatial_map: dict[str, list[int]],
    ) -> tuple[list[FunctionNode], float]:
        """[INTEGRATION MODE D] - Semantic Handshake Stack (Shell, Ruby, Lua)."""
        self.logger.debug(f"[DIAGNOSTIC] Mode D: Initiating _slice_by_keywords for {lang_id}")
        config = ScopeParsingRegistry.get_config(lang_id)
        if not config:
            return self._slice_by_braces(code, lang_id, rules, offset, spatial_map)

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
        # #1184: comment-stripping now happens INSIDE _apply_literal_shield,
        # in the same pass as string-shielding -- see that method's
        # docstring/comments for why a separate later pass was unsafe.
        safe_code = self._apply_literal_shield(code)

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
        for orig_line, safe_line in zip(original_lines, safe_lines):
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
        rules: dict[str, Any],
        offset: int,
        spatial_map: dict[str, list[int]],
    ) -> tuple[list[FunctionNode], float]:
        """[INTEGRATION MODE E] - Terminator Cleaving (SQL, Erlang, Prolog)."""
        config = ScopeParsingRegistry.get_config(lang_id)
        if not config:
            return self._slice_by_braces(code, lang_id, rules, offset, spatial_map)

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
        # #1184: strings and comments are shielded in ONE combined-alternation
        # pass, not sequential independent re.sub calls -- a separate LATER
        # comment-strip pass (the old approach) let an English contraction
        # apostrophe inside a "--"/"%" comment (it's, doesn't) get treated as
        # a real string-open quote by the single-quote pass that ran before
        # it, pairing with whatever "'" came next anywhere later in the code
        # and blanking out entire real statements (including igniter
        # keywords like CREATE PROCEDURE) in between. One combined pass lets
        # whichever construct starts first at a given position atomically
        # claim its whole span, so a comment's apostrophe is never
        # independently reconsidered as a string delimiter. Same fix as
        # `_build_indentation_safe_stream` / `_apply_literal_shield`.
        def preserve_newlines(m):
            if m.groupdict().get("comment") is not None:
                return ""
            return '""' + "\n" * m.group(0).count("\n")

        safe_code = re.sub(
            r'"(?:\\.|[^"\\])*"|'
            r"'(?:\\.|[^'\\])*'|"
            r"`(?:\\.|[^`\\])*`|"
            r"(?P<comment>--|%)[^\n]*",
            preserve_newlines,
            code,
            flags=re.DOTALL,
        )

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

    # galaxyscope:ignore sec_high_risk_execution
    # SHARED FUNCTIONAL METRICS ENGINE
    # ==============================================================================

    # galaxyscope:ignore sec_high_risk_execution

    def _matching_paren_end(self, text: str, open_idx: int) -> int:
        """
        String-aware scan for the index of the "(" at `open_idx`'s matching ")".
        Returns `len(text)` if it never closes within `text` (e.g. a signature
        capture that only includes an opening context paren, like Scheme's
        `(define (...)`). Shared by `_count_top_level_args` and
        `_calculate_block_metrics`'s args-count self-containment check (#1199).
        """
        depth = 0
        in_string = False
        quote_char = ""
        i = open_idx
        while i < len(text):
            ch = text[i]
            if in_string:
                if ch == "\\":
                    i += 2
                    continue
                if ch == quote_char:
                    in_string = False
            elif ch in ("'", '"', "`"):
                in_string = True
                quote_char = ch
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return i
            i += 1
        return len(text)

    def _count_top_level_args(self, args_str: str) -> int:
        """
        Depth- and string-aware argument counter for a captured function signature.

        `args` regexes capture the whole signature (e.g. "def foo(x, y)",
        "(x, y) =>"), so the real argument list sits one bracket level inside the
        first "(...)"; bracket-less forms (Python lambda, Lisp/space-separated)
        have no such wrapper, so top level IS depth 0 for them. Either way, only
        commas at that top level are real argument separators -- commas trapped
        inside nested (), [], {}, <> (generic type hints, default dict/list
        literals, nested callback signatures) or inside string literals must be
        ignored, or a single `data: Dict[str, int]` argument gets miscounted as
        two.

        Returns the actual argument count, not a raw comma tally: an empty
        parameter list is 0 (not 1), a trailing top-level comma -- the
        near-universal `ruff format` style for a multi-line signature with one
        parameter per line -- doesn't create a phantom extra segment, a lone
        `void` segment (C's explicit empty-parameter-list marker, `int f(void)`)
        is 0 arguments not 1, and a bare `*`/`/` segment (Python's keyword-only/
        positional-only markers, e.g. `def f(a, *, b):`) is real signature
        syntax but not itself an argument -- `ast.parse`'s own `FunctionDef.args`
        doesn't count it either, so counting every comma-separated segment as
        one argument overcounts any such signature by exactly one per marker
        (#1199, #1209).
        """
        body = args_str
        open_idx = args_str.find("(")
        if open_idx != -1:
            body = args_str[open_idx + 1 : self._matching_paren_end(args_str, open_idx)]

        if not body.strip():
            return 0

        depth = 0
        in_string = False
        quote_char = ""
        segments: list[str] = []
        seg_start = 0
        i = 0
        while i < len(body):
            ch = body[i]
            if in_string:
                if ch == "\\":
                    i += 2
                    continue
                if ch == quote_char:
                    in_string = False
            elif ch in ("'", '"', "`"):
                in_string = True
                quote_char = ch
            elif ch in "([{<":
                depth += 1
            elif ch in ")]}>":
                if depth > 0:
                    depth -= 1
            elif ch == "," and depth == 0:
                segments.append(body[seg_start:i])
                seg_start = i + 1
            i += 1
        segments.append(body[seg_start:])

        real_segments = [s for s in (seg.strip() for seg in segments) if s and s not in ("*", "/")]
        if real_segments == ["void"]:
            return 0
        return len(real_segments)

    def _calculate_block_metrics(
        self,
        name: str,
        block: str,
        loc: int,
        start_line: int,
        end_line: int,
        rules: dict[str, Any],
        start_idx: int = 0,
        end_idx: int = 0,
        spatial_map: Optional[dict[str, list[int]]] = None,
    ) -> tuple[FunctionNode, float]:
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
            # Both .findall() calls below are guarded by hasattr(), which
            # mypy doesn't narrow None away for the way it would isinstance()
            # -- hence the type: ignore[union-attr] markers on each.
            branch_hits = (
                len(branch_pattern.findall(block))  # type: ignore[union-attr]
                if hasattr(branch_pattern, "findall")
                else (len(re.findall(str(branch_pattern), block)) if branch_pattern else 0)
            )
            linear_hits = (
                len(linear_pattern.findall(block))  # type: ignore[union-attr]
                if hasattr(linear_pattern, "findall")
                else (len(re.findall(str(linear_pattern), block)) if linear_pattern else 0)
            )

        total_hits = branch_hits + linear_hits

        # --- FAST CODING LOC HEURISTIC (Syntax Fixed!) ---
        # Quickly strip out blank lines and standard single-line comments to find the true logic mass
        # THE FIX: Preserve leading whitespace to calculate Big-O nesting depth!
        raw_lines = [l for l in block.splitlines() if l.strip() and not l.lstrip().startswith(("#", "//", "/*", "*"))]
        coding_loc = len(raw_lines)

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
                    stripped = args_str.strip() if args_str else ""
                    # #1199: a capture group whose ENTIRE span is a self-contained
                    # "(...)" pair (true of python's def/lambda-with-parens args
                    # group once it stops sharing group(0) with the "def name"
                    # prefix) is unambiguously the real parameter list -- a
                    # comma-free non-empty body there is exactly ONE argument, not
                    # zero. The old code could only decide via "does args_str
                    # contain a comma", which silently overcounted every
                    # zero/one-arg signature by +1 (the "def name(...)" prefix
                    # itself supplied a spurious extra whitespace-split token).
                    # Signatures that AREN'T self-contained (e.g. Scheme's
                    # `(define (func arg1 arg2)`, whose outer "(define" paren
                    # never closes within the capture) fall through unchanged to
                    # the original comma/whitespace-split heuristics below.
                    if (
                        stripped.startswith("(")
                        and stripped.endswith(")")
                        and self._matching_paren_end(stripped, 0) == len(stripped) - 1
                    ):
                        args_count = self._count_top_level_args(stripped)
                    elif stripped and stripped != "()":
                        if "," in args_str:
                            args_count = self._count_top_level_args(args_str)
                        else:
                            # Handle space-separated arguments (Lisp/Scheme/Shell)
                            args_count = len(args_str.strip().split())
            except Exception as e:
                self.logger.debug(f"Argument-count regex extraction failed, leaving args_count 0: {e}")

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

        # Calculate magnitude using the dampened arguments and logic-bounded length
        magnitude = float((branch_hits + 1) * arg_multiplier + (0.05 * effective_loc))

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
            "name": name,
            "calls_out_to": calls_out,
            "texture": texture_str,
            "type_id": texture_str,
            "loc": loc,
            "branch_count": branch_hits,
            "branch": branch_hits,
            "args": args_count,
            "args_count": args_count,
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
            "start_idx": start_idx,
            "end_idx": end_idx,
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

    def _classify_function(self, name: str, block: str, rules: dict[str, Any]) -> str:
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
