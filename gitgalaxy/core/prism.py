# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
import re
import logging
from typing import Dict, List, Optional, Tuple, Any, TypedDict
from gitgalaxy.standards.language_standards import LENS_CONFIG, PRISM_CONFIG

# ==============================================================================
# GitGalaxy Phase 2: Payload & Surface Splitter (The Prism)
# Strategy Protocol: Safe Delimiter Extraction & Format Bypasses
# ==============================================================================


class PrismResult(TypedDict):
    """
    The dual-output of the Prism.

    Attributes:
        code_stream (str): The executable payload.
        comment_stream (str): The documentation surface.
        coding_loc (int): Lines of code (non-empty, non-comment).
        doc_loc (int): Lines of comments/documentation.
        mitigations (List[str]): Extracted inline suppressions.
    """

    code_stream: str
    comment_stream: str
    coding_loc: int
    doc_loc: int
    mitigations: List[str]


class PrismError(Exception):
    """Exception raised for structural failures during the lexical scan."""

    pass


class Prism:
    """
    GitGalaxy Phase 2: The Prism (Payload & Surface Splitter)

    PURPOSE: Just as a physical prism splits a unified beam of light into distinct
    spectrums, this class performs high-speed structural scanning to separate a unified
    file into a pure executable payload and documentation surface while preserving string literals.

    DEFENSIVE ARCHITECTURE (Why Regex over AST?):
    Standard Abstract Syntax Trees (ASTs) are brittle, language-specific, and require
    compilable code. To achieve polyglot velocity and prioritize functional intent across
    50+ languages, the Prism utilizes highly bounded, ReDoS-proof regular expressions.

    PIPELINE RULES:
    1. Format Bypass: Respects 'undeterminable' files by passing them untouched to prevent pipeline stalls.
    2. Dynamic Regex Matrix: Pre-compiles standard comment rules at runtime based on the JSON configuration.
    3. O(1) String Literal Masking: Temporarily masks string literals to prevent the scanner from
       accidentally mutating URLs or string contents that mimic comment delimiters.
    4. Polyglot Delegation: Defers embedded language-mixing resolution to the primary Detector.
    """

    def __init__(
        self,
        comment_definitions: Dict[str, Any],
        language_definitions: Dict[str, Any],
        parent_logger: Optional[logging.Logger] = None,
    ):
        """Initializes the Prism and pre-compiles the regex matrix."""

        # --- TELEMETRY SYNC ---
        if parent_logger:
            self.logger = parent_logger.getChild("prism")
            self.logger.setLevel(parent_logger.level)
        else:
            self.logger = logging.getLogger("prism")
            self.logger.setLevel(logging.INFO)

        self.lexical_families = comment_definitions.get("mechanical_families", {})
        self.languages = language_definitions

        self.logger.debug("Initializing Prism and warming up regex matrix...")

        # --- TIER 1: STRING LITERAL MASKING ---
        # Defends against catastrophic backtracking and logic erosion inside strings
        self.LITERAL_MASK_PATTERN = PRISM_CONFIG.get("SHIELD_PATTERN", "")

        # --- TIER 2: REGEX PRE-COMPILATION ---
        self.REGEX_MATRIX: Dict[str, re.Pattern] = self._compile_regex_matrix()

        # Phase 6.1 Handshake Registry (Synchronized securely via Language Standards)
        self.EMBEDDED_TRIGGERS = []
        for trigger_config in LENS_CONFIG.get("HANDSHAKE_REGISTRY", []):
            self.EMBEDDED_TRIGGERS.append(
                {
                    "trigger": re.compile(trigger_config["trigger"], re.I),
                    "end": re.compile(trigger_config["end"], re.I),
                    "target": trigger_config["target"],
                    "pair": trigger_config["pair"],
                }
            )

        # Performance Constants
        self.EMBEDDED_LOOKAHEAD_LIMIT = LENS_CONFIG.get("THRESHOLDS", {}).get("HANDSHAKE_LOOKAHEAD_LIMIT", 50000)
        self.NESTED_PEEL_LIMIT = PRISM_CONFIG.get("THRESHOLDS", {}).get("NESTED_PEEL_LIMIT", 500)
        self.POSITIONAL_ANCHORS = PRISM_CONFIG.get("POSITIONAL_ANCHORS", {"*", "C", "c", "/", "!"})

        # Hardened Language Specific Extractors
        self.PYTHON_DOC_PATTERN = re.compile(PRISM_CONFIG.get("PYTHON_DOC_PATTERN", ""), re.M)
        self.PHP_HEREDOC_PATTERN = re.compile(PRISM_CONFIG.get("PHP_HEREDOC_PATTERN", ""), re.M)
        self.PHP_MULTILINE_STRING = re.compile(PRISM_CONFIG.get("PHP_MULTILINE_STRING", ""), re.M)

        self.logger.info(f"Structural Scanner Online | Calibrated {len(self.REGEX_MATRIX)} syntax rules.")

    def split_streams(self, content: str, primary_lang: str) -> PrismResult:
        """Decouples the file into mutually exclusive components (Executable Payload vs Documentation Surface)."""
        if not content:
            self.logger.debug("Structural Scan skipped: Empty content buffer.")
            return {
                "code_stream": "",
                "comment_stream": "",
                "coding_loc": 0,
                "doc_loc": 0,
                "mitigations": [],
            }

        # ---> INLINE SUPPRESSION EXTRACTION <---
        mitigations = []
        for match in re.finditer(r"galaxyscope:ignore\s+([a-zA-Z0-9_-]+)", content, re.IGNORECASE):
            mitigations.append(match.group(1).lower())
            self.logger.debug(f"Extracted inline suppression for: {match.group(1)}")

        # --- THE UNPARSABLE BYPASS (Spec 2.3.4.A.1) ---
        if primary_lang in ("undeterminable", "unknown"):
            self.logger.debug(f"Unparsable Bypass: '{primary_lang}' signal routed to Executable Logic intact.")
            coding_loc = len([l for l in content.split("\n") if l.strip()])
            return {
                "code_stream": content,
                "comment_stream": "",
                "coding_loc": coding_loc,
                "doc_loc": 0,
                "mitigations": mitigations,
            }

        # --- THE PROSE BYPASS ---
        # Simply add "xml" to the tuple!
        if primary_lang in ("markdown", "plaintext", "xml"):
            self.logger.debug(f"Prose Bypass: '{primary_lang}' signal routed to Documentation intact.")
            doc_loc = len([l for l in content.split("\n") if l.strip()])
            return {
                "code_stream": "",
                "comment_stream": content,
                "coding_loc": 0,
                "doc_loc": doc_loc,
                "mitigations": mitigations,
            }

        # 1. METADATA GUARD
        header, body = self._guard_metadata_signal(content)

        # 2. STATE INITIALIZATION
        code_parts: List[str] = []
        comment_parts: List[str] = []

        try:
            # 3. THE SLIDING LOOP (Phase 6)
            # We partition the file so embedded languages get their native comment rules applied.
            segments = self._partition_embedded_languages(body, primary_lang)

            if len(segments) > 1:
                self.logger.info(
                    f"Multi-language file detected in [{primary_lang}]. - Engaging dynamic syntax rule swap across {len(segments)} distinct file sections."
                )

            for lang_id, segment_text in segments:
                family = self.languages.get(lang_id, {}).get("lexical_family", "c_style_comment")
                self.logger.debug(f"Scanning segment [{lang_id}] using syntax family '{family}'...")

                # Strip comments from the segment
                seg_code, seg_comments = self._strip_segment_comments(segment_text, lang_id, family)

                code_parts.append(seg_code)
                comment_parts.append(seg_comments)

            # 4. OUTPUT SYNTHESIS
            final_code = header + "".join(code_parts)
            final_comments = "\n".join(comment_parts).strip()

            # --- THE FIX: Prevent the "Inline Comment Double-Dip" ---
            # 1. Count the total non-blank lines in the original un-split file
            total_active_lines = len([l for l in content.split("\n") if l.strip()])

            # 2. Count the pure coding lines
            coding_loc = len([l for l in final_code.split("\n") if l.strip()])

            # 3. Derive the documentation lines by subtracting code from the active total.
            # This forces mutual exclusivity: if a line has code and a comment, it counts as Code.
            doc_loc = max(0, total_active_lines - coding_loc)

            self.logger.debug(f"Structural Scan Complete: {coding_loc} Executable LOC | {doc_loc} Documentation LOC.")

            return {
                "code_stream": final_code,
                "comment_stream": final_comments,
                "coding_loc": coding_loc,
                "doc_loc": doc_loc,
                "mitigations": mitigations,
            }

        except Exception as e:
            self.logger.error(
                f"Catastrophic structural failure during structural scan: {e}",
                exc_info=True,
            )
            raise PrismError(f"Prism failure: {e}")

    def _strip_segment_comments(self, text: str, lang_id: str, family: str) -> Tuple[str, str]:
        """Surgically strips documentation using an ordered, additive pipeline."""
        lits = []

        # 1. PRE-PROCESSING: Extract documentation surface BEFORE any early returns
        if lang_id in ("python", "micropython", "ruby"):
            text, python_lits = self._strip_python_docstrings(text)
            lits.extend(python_lits)
        elif lang_id == "php":
            text, php_lits = self._strip_php_string_mass(text)
            lits.extend(php_lits)

        # 2. SPECIALIZED LEXICAL FAMILY ROUTING
        if family == "recursive_c_style":
            code, nested_lits = self._strip_nested_comments(text)
            lits.extend(nested_lits)
            return code, "\n".join(lits)

        if family == "column_sensitive":
            code, pos_lits = self._strip_positional_comments(text)
            if pos_lits:
                lits.extend(pos_lits.splitlines())
            return code, "\n".join(lits)

        if family == "single_line_only":
            code, single_lits = self._strip_single_line_comments(text)
            if single_lits:
                lits.extend(single_lits.splitlines())
            return code, "\n".join(lits)

        # 3. ATOMIC SHIELDING: Mask literals to prevent generic stripping
        masked_literals = []

        def shield_callback(m: re.Match) -> str:
            masked_literals.append(m.group(0))
            return f"__MASK_{len(masked_literals) - 1}__"

        text = re.sub(self.LITERAL_MASK_PATTERN, shield_callback, text, flags=re.S | re.M)

        # 4. GENERIC STRIPPER
        pattern = self.REGEX_MATRIX.get(family)
        if not pattern:
            # Restore mask tokens before returning if no pattern is registered
            code = re.sub(r"__MASK_(\d+)__", lambda m: masked_literals[int(m.group(1))], text)
            return code, "\n".join(lits)

        def strip_callback(m: re.Match) -> str:
            if m.group(2):  # Match group 2 is your documentation group
                lits.append(m.group(2).strip())
            return ""

        code = pattern.sub(strip_callback, text)

        # 5. RESTORE SHIELDED LITERALS
        code = re.sub(r"__MASK_(\d+)__", lambda m: masked_literals[int(m.group(1))], code)

        return code, "\n".join(lits)

    def _compile_regex_matrix(self) -> Dict[str, re.Pattern]:
        """Safely pre-compiles the standard regex matrix based on dynamic config lengths."""
        matrix = {}

        for fam_key, data in self.lexical_families.items():
            if fam_key in ("recursive_c_style", "column_sensitive"):
                continue

            delims = data.get("delimiters", [])
            if not delims:
                continue

            # Secure array escape
            d = [re.escape(x) for x in delims]
            p = ""

            # Dynamically build regex based on family type and safe bounds checks
            if fam_key == "c_style_comment" and len(d) >= 3:
                p = rf"({d[0]}[^\n]*|{d[1]}.*?{d[2]})"
            elif fam_key == "single_line_only" and len(d) >= 1:
                p = rf"({d[0]}[^\n]*)"
            elif fam_key == "embedded_syntax" and len(d) >= 3:
                # If len is 4, include d[3], otherwise just [0,1,2]
                if len(d) >= 4:
                    p = rf"({d[1]}.*?{d[2]}|{d[0]}[^\n]*|{d[3]}[^\n]*)"
                else:
                    p = rf"({d[1]}.*?{d[2]}|{d[0]}[^\n]*)"
            elif fam_key == "multi_style_dash" and len(d) >= 5:
                p = rf"({d[1]}.*?{d[2]}|{d[3]}.*?{d[4]}|{d[0]}[^\n]*)"
            elif fam_key == "multi_style_dash" and len(d) >= 3:  # Fallback
                p = rf"({d[1]}.*?{d[2]}|{d[0]}[^\n]*)"
            elif fam_key == "single_line_only":
                # =====================================================================
                # THE FIX: Neutralized the Zero-Width ReDoS Bomb.
                #
                # HISTORICAL CONTEXT FOR FUTURE MAINTAINERS & LLMS:
                # A previous iteration of this regex started with `(|^[ \t]...`.
                # The leading `|` (OR) without a preceding token created a zero-width
                # assertion. This told Python's `re.sub` engine that matching an "empty
                # string" was a valid success state. Consequently, `re.sub` would
                # evaluate and trigger a callback at EVERY SINGLE CHARACTER BOUNDARY
                # in the file. For a 1MB Assembly file, this caused 1,000,000 redundant
                # Python loop executions, freezing the pipeline.
                #
                # DO NOT ADD A LEADING OR TRAILING `|` TO THIS CAPTURE GROUP.
                #
                # REGEX TOKEN BREAKDOWN:
                # This pattern explicitly maps a grab-bag of legacy/singular comment
                # tokens safely. It evaluates sequentially:
                #
                # 1. `^[ \t]*%\{.*?%\}` : Matlab block comments. Matches start of line,
                #                         optional whitespace, then %{ ... %} natively.
                #                         (Relies on re.M and re.S flags applied later).
                # 2. `;[^\n]*`          : Assembly, Lisp, and INI single-line comments.
                # 3. `//[^\n]*`         : C-style single-line comments.
                # 4. `(?i)\bdnl\b[^\n]*`: M4 macro comments ("Discard to Next Line").
                #                         (?i) sets case-insensitivity, \b ensures exact
                #                         word match.
                # 5. `%[^\n]*`          : TeX and Matlab single-line comments.
                # =====================================================================
                p = r"(//[^\n]*|;[^\n]*|%[^\n]*|^[ \t]*%\{.*?%\}|(?i)\bdnl\b[^\n]*)"

            if p:
                try:
                    # ---> THE FIX: Strip any rogue inline flags injected by the config <---
                    p = p.replace("(?i)", "").replace("(?m)", "").replace("(?s)", "")
                    full_pattern = f"{self.LITERAL_MASK_PATTERN}|{p}"

                    flags = re.S | re.M
                    if fam_key == "single_line_only":
                        flags |= re.IGNORECASE

                    matrix[fam_key] = re.compile(full_pattern, flags)
                    self.logger.debug(f"Regex matrix compiled for family: {fam_key}")
                except re.error as e:
                    self.logger.error(f"Regex compilation failed for family '{fam_key}': {e}")

        return matrix

    def _strip_python_docstrings(self, text: str) -> Tuple[str, List[str]]:
        """Extracts triple-quoted strings as documentation."""
        docs = []

        # Use the relaxed pattern
        def callback(m: re.Match) -> str:
            docs.append(m.group(0).strip())
            return "\n"  # Maintain line count stability

        # Using re.DOTALL ensures [\s\S] matches newlines correctly
        clean = re.sub(r'(?:"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')', callback, text)
        return clean, docs

    def _strip_php_string_mass(self, text: str) -> Tuple[str, List[str]]:
        """Surgically extracts PHP Heredoc and multi-line strings to prevent structural hallucinations."""
        lits = []

        def capture_lit(m: re.Match) -> str:
            # Save the literal into the Documentation stream
            lits.append(m.group(0).strip())
            # Replace with a safe, empty string literal to preserve PHP array syntax
            return '""'

        # 1. Extract Heredoc/Nowdoc
        text = self.PHP_HEREDOC_PATTERN.sub(capture_lit, text)

        # 2. Extract massive Multi-line Strings
        text = self.PHP_MULTILINE_STRING.sub(capture_lit, text)

        return text, lits

    def _partition_embedded_languages(self, content: str, primary_id: str) -> List[Tuple[str, str]]:
        """Splits content into language segments based on embedded language triggers."""
        segments = []
        last_idx = 0

        triggers = []
        # --- FAST PATH: The Universal Web Tax Shield ---
        # Bypasses expensive case-insensitive regex scans unless the trigger literal is actually present.
        content_lower = None

        for t_config in self.EMBEDDED_TRIGGERS:
            # Extract a reliable literal hint (e.g., 'script', 'style', 'asm')
            hint = (
                t_config["trigger"]
                .pattern.lower()
                .replace("\\s*", "")
                .replace("\\b", "")
                .replace("__", "")
                .split("<")[-1]
                .split("(")[0]
                .split("!")[0]
                .strip()
            )

            if len(hint) >= 3:
                if content_lower is None:
                    content_lower = content.lower()  # One fast C-level allocation
                if hint not in content_lower:
                    continue  # Skip the expensive regex entirely!

            for m in t_config["trigger"].finditer(content):
                triggers.append(
                    {
                        "start": m.start(),
                        "end_pattern": t_config["end"],
                        "target": t_config["target"],
                        "pair": t_config["pair"],
                        "trigger_end": m.end(),
                    }
                )

        triggers.sort(key=lambda x: x["start"])

        for t in triggers:
            if t["start"] < last_idx:
                continue

            self.logger.debug(
                f"Embedded Trigger: Embedded Language Block '{t['target']}' discovered at offset {t['start']}."
            )

            if t["start"] > last_idx:
                segments.append((primary_id, content[last_idx : t["start"]]))

            if t["pair"]:
                open_char, close_char = t["pair"]
                end_idx = self._find_balanced_end(content, t["start"], open_char, close_char)
            else:
                search_limit = min(t["trigger_end"] + self.EMBEDDED_LOOKAHEAD_LIMIT, len(content))
                end_match = t["end_pattern"].search(content, pos=t["trigger_end"], endpos=search_limit)
                end_idx = end_match.end() if end_match else len(content)
                if not end_match and end_idx == search_limit:
                    self.logger.warning("Scanner Scope Guard: Failed to find closure within limit. Forcing clip.")

            segments.append((t["target"], content[t["start"] : end_idx]))
            last_idx = end_idx

        if last_idx < len(content):
            segments.append((primary_id, content[last_idx:]))

        return segments if segments else [(primary_id, content)]

    def _find_balanced_end(self, text: str, start_pos: int, opener: str, closer: str) -> int:
        """Balanced scoping implementation for paired-bracket embedded segments."""
        depth = 0
        in_string: Optional[str] = None
        limit = min(start_pos + self.EMBEDDED_LOOKAHEAD_LIMIT, len(text))

        i = start_pos
        while i < limit:
            char = text[i]

            # 1. EXACT Escape Handling
            if char in ('"', "'", "`"):
                # Count consecutive backslashes preceding the quote
                bs_count = 0
                j = i - 1
                while j >= start_pos and text[j] == "\\":
                    bs_count += 1
                    j -= 1

                # If backslashes are EVEN, the quote is real. If ODD, it is escaped.
                if bs_count % 2 == 0:
                    if not in_string:
                        in_string = char
                    elif in_string == char:
                        in_string = None

            # 2. Scope Tracking (Only active when NOT trapped inside a string)
            elif not in_string:
                if char == opener:
                    depth += 1
                elif char == closer:
                    depth -= 1
                    if depth <= 0:
                        self.logger.debug(f"Balanced scoping closed at offset +{i - start_pos} chars.")
                        return i + 1

            i += 1

        self.logger.warning(f"Scanner Scope Guard: Failed to find balanced '{opener}{closer}'. Forcing closure.")
        return limit

    def _strip_nested_comments(self, text: str) -> Tuple[str, List[str]]:
        """
        Iterative Peel loop for recursively nested block comments (e.g. Rust/Swift/Scala).
        Hardened with active string-masking to prevent logic erosion.
        """
        delims = self.lexical_families.get("recursive_c_style", {}).get("delimiters", ["//", "/*", "*/"])
        if len(delims) < 3:
            return text, []

        s_line, b_start, b_end = delims[0], delims[1], delims[2]
        lits = []

        # 1. Protect Strings via Safe Masking
        # Masking prevents the `.rfind` mathematical loop from tearing apart string literals
        shield = re.compile(self.LITERAL_MASK_PATTERN, re.S | re.M)
        string_cache = {}

        def _shield_replacer(m: re.Match) -> str:
            if m.group(1):
                key = f"__GALAXY_STR_MASK_{len(string_cache)}__"
                string_cache[key] = m.group(1)
                return key
            return ""

        protected_code = shield.sub(_shield_replacer, text)

        # --- FAST O(1) UNMASKING ROUTINE ---
        def unmask(chunk: str) -> str:
            if "__GALAXY_STR_MASK_" not in chunk:
                return chunk
            # Instantly find masks via regex and retrieve the original string via O(1) dictionary lookup
            return re.sub(
                r"__GALAXY_STR_MASK_\d+__",
                lambda match: string_cache.get(match.group(0), match.group(0)),
                chunk,
            )

        # 2. Peel single-line comments safely
        s_line_pattern = re.compile(rf"{re.escape(s_line)}[^\n]*")

        def single_callback(m: re.Match) -> str:
            comment = m.group(0)
            lits.append(unmask(comment).strip())
            return ""

        protected_code = s_line_pattern.sub(single_callback, protected_code)

        # 3. Iteratively peel nested blocks from the inside out
        safety = 0
        while b_start in protected_code and safety < self.NESTED_PEEL_LIMIT:
            end_match = re.search(re.escape(b_end), protected_code)
            if not end_match:
                break

            start_idx = protected_code.rfind(b_start, 0, end_match.start())
            if start_idx == -1:
                break

            block_content = protected_code[start_idx : end_match.end()]

            # Unmask any strings safely captured within the comment block using O(1) lookup
            lits.append(unmask(block_content).strip())

            # Remove from logic stream
            protected_code = protected_code[:start_idx] + protected_code[end_match.end() :]
            safety += 1

        if safety >= self.NESTED_PEEL_LIMIT:
            self.logger.warning(f"Nested Peel Guard triggered: Reached max iteration limit ({self.NESTED_PEEL_LIMIT}).")

        # 4. Final Logic Unmasking
        return unmask(protected_code), lits

    def _strip_positional_comments(self, text: str) -> Tuple[str, str]:
        """Column-anchored and Inline stripping for legacy languages (COBOL/Fortran)."""
        code, lits = [], []

        for line in text.split("\n"):
            # 1. Legacy Column-1 or Column-7 anchors (Fixed Form)
            if (len(line) >= 1 and line[0] in self.POSITIONAL_ANCHORS) or (
                len(line) >= 7 and line[6] in self.POSITIONAL_ANCHORS
            ):
                lits.append(line)
                continue

            # 2. Modern Inline Fortran (!) and COBOL (*>) comments
            if "*>" in line:
                parts = line.split("*>", 1)
                code.append(parts[0])
                lits.append("*>" + parts[1])
            elif "!" in line:
                parts = line.split("!", 1)
                code.append(parts[0])
                lits.append("!" + parts[1])
            else:
                code.append(line)

        return "\n".join(code), "\n".join(lits)

    def _guard_metadata_signal(self, content: str) -> Tuple[str, str]:
        """Protects shebangs and preprocessor headers from the stripping engine."""
        lines = content.split("\n", 1)
        if not lines:
            return "", ""

        first = lines[0]
        # Explicit guard for #! and early PHP/XML execution tags
        if first.startswith(("#!", "<?php", "<?xml")):
            return first + "\n", lines[1] if len(lines) > 1 else ""

        return "", content

    def _strip_single_line_comments(self, text: str) -> Tuple[str, str]:
        """Generic single-line comment stripper (for '#' or ';' or '--')."""
        lines = text.splitlines()
        code, comments = [], []
        pattern = re.compile(r"(#|--|;|//)")

        for line in lines:
            if pattern.search(line):
                parts = pattern.split(line, 1)
                code.append(parts[0])
                comments.append(parts[1] + (parts[2] if len(parts) > 2 else ""))
            else:
                code.append(line)
        return "\n".join(code), "\n".join(comments)
