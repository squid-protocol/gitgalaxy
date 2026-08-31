# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
import logging
import re
from typing import Any, Optional, TypedDict

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
    mitigations: list[str]


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
        comment_definitions: dict[str, Any],
        language_definitions: dict[str, Any],
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

        # #386: was "mechanical_families", a key nothing ever wrote (see #378's
        # dead key audit finding) -- the real key in LEXICAL_FAMILY_HEURISTICS
        # (gitgalaxy_config.py) is "lexical_families". This alone was only half
        # the bug: the family NAMES used below and in _compile_regex_matrix()
        # also didn't match the real per-language "lexical_family" values
        # (standard_block/line_exclusive/recursive_block/positional_anchored),
        # so comment stripping never actually ran for ANY language even before
        # this fix -- see the family-name renames below and in
        # _compile_regex_matrix().
        self.lexical_families = comment_definitions.get("lexical_families", {})
        self.languages = language_definitions

        self.logger.debug("Initializing Prism and warming up regex matrix...")

        # --- TIER 1: STRING LITERAL MASKING ---
        # Defends against catastrophic backtracking and logic erosion inside strings
        self.LITERAL_MASK_PATTERN = PRISM_CONFIG.get("SHIELD_PATTERN", "")

        # #1718: C++ (C++14+) uses a single quote as a digit separator inside
        # numeric literals (512'000, 1'000'000'000, 0xDE'AD). The shared
        # SHIELD_PATTERN's single-quote branch is unbounded, so a separator
        # `'` is mistaken for the opening quote of a char literal and pairs
        # with the NEXT unrelated `'` anywhere later in the file (re.S lets
        # [^'\\] span newlines), swallowing every real // and /* */ comment
        # in between as one giant "literal" -- the code stream then carries
        # comment text into the detector and coding_loc is inflated.
        # C++ char literals are short, but C++23 named escapes (\\N{...}) can
        # run much longer than 10 chars, so the branch is bounded to 64 -- wide
        # enough for any real literal, still far too short for a cross-file
        # cascade. Kept per-language because the shared pattern must stay
        # unbounded for JS/PHP single-quoted strings.
        self.CPP_LITERAL_MASK_PATTERN = (
            r'((?<!\\)"(?:\\.|[^"\\])*"'
            r"|[0-9a-fA-F]'[0-9a-fA-F]"
            r"|(?<!\\)'(?:\\.|[^'\\]){0,64}'"
            r"|(?<!\\)`(?:\\.|[^`\\])*`)"
        )

        # #2419: LiveCode (`multi_style_live`) string literals have NO backslash
        # escapes -- `\` is an ordinary character, and `"` is the only string
        # delimiter (`'` and backtick are not string delimiters in either
        # dialect). The shared SHIELD_PATTERN's C-style, escape-aware,
        # newline-unbounded `"(?:\\.|[^"\\])*"` misreads `"\"` (a real one-char
        # LiveCode string containing a backslash, e.g. `replace quote with "\" &
        # quote`) as an escaped-quote-opening a string that runs -- under
        # `re.S` -- to the next `"` many lines away, desynchronizing every
        # subsequent quote pair and eventually exposing a `/*` inside a later
        # string literal as a bogus block-comment opener (confirmed:
        # revsaveasandroidstandalone.livecodescript, `filter ... with
        # "Android/*"`, swallowed ~17 handlers). Single-line, no-escape.
        self.MULTI_STYLE_LIVE_LITERAL_MASK_PATTERN = r'("[^"\r\n]*")'

        # #259: ABAP's `"` is a comment delimiter, never a string quote -- ABAP
        # string literals are `'...'` and string templates use backtick. Masking
        # with the shared SHIELD_PATTERN's `"..."` branch in _strip_positional_
        # comments would swallow an ABAP comment that happens to contain an inner
        # `"..."` pair as if it were a live literal, so ABAP's positional stripper
        # masks single-quote / backtick literals only.
        self.ABAP_LITERAL_MASK_PATTERN = r"((?<!\\)'(?:\\.|[^'\\])*'|(?<!\\)`(?:\\.|[^`\\])*`)"

        # #1271: detects a quote that opens but never closes before end-of-
        # line -- a backslash-newline-continued literal (legal in both Ruby
        # and Python) -- so _strip_single_line_comments can carry that
        # open-quote state to the next line instead of treating the
        # continuation as fresh code (see that method's docstring for the
        # full failure shape this closes).
        #
        # Deliberately just a bare character class, not an escape-aware
        # "opens but doesn't close" pattern: CodeQL flagged an earlier
        # `(?:\\.|(?!\1).)*$`-shaped version for exponential backtracking
        # (`.` in the second alternative doesn't exclude the backslash, so a
        # run of `\x` pairs partitions ambiguously between "one \\. escape"
        # vs "two separate chars" -- confirmed: a 26-char adversarial
        # payload alone took >8s), and a follow-up fix that excluded the
        # backslash from that alternative (matching SHIELD_PATTERN's own
        # `(?:\\.|[^"\\])*"` idiom) closed the ReDoS hole but silently broke
        # the one case that actually matters here -- a line ending in a bare
        # trailing backslash (real line continuation, e.g. Ruby's
        # `"...text \`) has no partner character for `\\.` to pair with and
        # isn't matchable by an alternative that excludes bare backslashes
        # either, so the whole match failed exactly for the payloads this
        # existed to catch. This class is simpler AND correct: by the time
        # `_mask_line_literals` hands back `code_part`, every COMPLETE
        # quoted literal on the line has already been consumed into a
        # `__MASK_N__` placeholder -- any raw quote character still present
        # is, by construction, not part of any complete pair, so it doesn't
        # need its own escape-parsing to prove that; finding its position is
        # enough to know a literal opened here and never closed on this
        # line. A trivial single-char-class search can't backtrack at all.
        self.UNTERMINATED_QUOTE_TAIL_PATTERN = re.compile(r"[\"'`]")
        self.CARRY_QUOTE_CLOSE_PATTERNS: dict[str, re.Pattern] = {
            q: re.compile(rf"(?:\\.|[^{re.escape(q)}\\])*{re.escape(q)}") for q in ('"', "'", "`")
        }

        # --- TIER 2: REGEX PRE-COMPILATION ---
        self.REGEX_MATRIX: dict[str, re.Pattern] = self._compile_regex_matrix()

        # #1718: C++ digit separators (512'000) must not pair with a later
        # `'` as a char literal, so C++ uses a bounded single-quote shield
        # in the generic standard_block stripper (see _strip_segment_comments).
        self.CPP_REGEX_MATRIX: dict[str, re.Pattern] = self._compile_regex_matrix(
            literal_pattern=self.CPP_LITERAL_MASK_PATTERN
        )

        # #697: _strip_single_line_comments() used to hardcode `#|--|;|//`
        # regardless of what a given family's real delimiters are. #1193:
        # a single shared pattern for the whole "line_exclusive" family was
        # its own bug -- `;`/`%` are only real delimiters for a couple of
        # the ~20 member languages, so they falsely truncated ordinary code
        # (`100 % 7`, CLI `--` args) for the rest. Precompile one pattern
        # PER LANGUAGE instead, keyed off each language's own real delimiter
        # set (gitgalaxy_config.py's "language_delimiters"), same pattern as
        # REGEX_MATRIX.
        self.SINGLE_LINE_DELIMITER_PATTERNS: dict[str, re.Pattern] = self._compile_single_line_delimiter_patterns()

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
        code_parts: list[str] = []
        comment_parts: list[str] = []

        try:
            # 3. THE SLIDING LOOP (Phase 6)
            # We partition the file so embedded languages get their native comment rules applied.
            segments = self._partition_embedded_languages(body, primary_lang)

            if len(segments) > 1:
                self.logger.info(
                    f"Multi-language file detected in [{primary_lang}]. - Engaging dynamic syntax rule swap across {len(segments)} distinct file sections."
                )

            for lang_id, segment_text in segments:
                # #386: default fallback renamed to match the real taxonomy
                # ("standard_block" is what "c_style_comment" always meant here).
                family = self.languages.get(lang_id, {}).get("lexical_family", "standard_block")
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
            raise PrismError(f"Prism failure: {e}") from e

    def _strip_segment_comments(self, text: str, lang_id: str, family: str) -> tuple[str, str]:
        """Surgically strips documentation using an ordered, additive pipeline."""
        lits = []

        # 1. PRE-PROCESSING: Extract documentation surface BEFORE any early returns
        if lang_id in ("python", "micropython", "ruby"):
            text, python_lits = self._strip_python_docstrings(text)
            lits.extend(python_lits)
        elif lang_id == "php":
            text, php_lits = self._strip_php_string_mass(text)
            lits.extend(php_lits)
        elif lang_id == "powershell":
            text, ps_lits = self._strip_powershell_herestrings(text)
            lits.extend(ps_lits)
        elif lang_id == "groovy":
            text, groovy_lits = self._strip_groovy_triple_quoted_strings(text)
            lits.extend(groovy_lits)
        elif lang_id == "assembly":
            text, asm_lits = self._strip_asm_block_comments(text)
            lits.extend(asm_lits)

        # 2. SPECIALIZED LEXICAL FAMILY ROUTING
        # #386: these three used to check "recursive_c_style"/"column_sensitive"/
        # "single_line_only" -- names that never matched any real per-language
        # "lexical_family" value (the real taxonomy is standard_block/
        # line_exclusive/recursive_block/positional_anchored/block_exclusive/
        # non_lexical), so none of these branches, nor the generic REGEX_MATRIX
        # stripper below, ever actually ran for any language.
        if family in ("recursive_block", "recursive_block_haskell", "recursive_block_lisp"):
            # #621: recursive_block_haskell added because Haskell's {- -}
            # blocks genuinely nest (unlike the standard_block family's flat
            # delimiters) but use -- for line comments and {- -} rather than
            # recursive_block's C-style // /* */ -- same nesting algorithm,
            # different token set, so this reads its own family's delimiters
            # instead of assuming "recursive_block" specifically.
            # #770: recursive_block_lisp added the same way for Scheme's ;
            # line comments and genuinely-nestable #| |# block comments --
            # scheme was previously misclassified "line_exclusive" (stateless,
            # no cross-line tracking), which only ever stripped a #| block
            # comment's opening line.
            code, nested_lits = self._strip_nested_comments(text, family)
            lits.extend(nested_lits)
            return code, "\n".join(lits)

        if family in ("positional_anchored", "positional_abap"):
            code, pos_lits = self._strip_positional_comments(
                text, abap_mode=(family == "positional_abap"), cobol_mode=(lang_id == "cobol")
            )
            if pos_lits:
                lits.extend(pos_lits.splitlines())
            return code, "\n".join(lits)

        if family == "line_exclusive":
            code, single_lits = self._strip_single_line_comments(text, lang_id)
            if single_lits:
                lits.extend(single_lits.splitlines())
            return code, "\n".join(lits)

        # 3. GENERIC STRIPPER
        pattern = self.REGEX_MATRIX.get(family)
        if lang_id == "cpp" and family == "standard_block":
            # #1718: C++ digit separators (512'000) use `'` as a digit
            # separator, which the unbounded shared single-quote branch
            # misreads as a char literal opener that pairs with the next
            # unrelated `'` anywhere later in the file -- swallowing every
            # real comment in between. Route C++ through the bounded
            # CPP_REGEX_MATRIX so separators can't cascade into a false
            # literal (JS/PHP keep the unbounded shared pattern).
            pattern = self.CPP_REGEX_MATRIX.get(family) or pattern
        if not pattern:
            return text, "\n".join(lits)

        def strip_callback(m: re.Match) -> str:
            # If group 1 (literal shield) matched, pass it through unharmed
            if m.group(1) is not None:
                return m.group(0)

            # If group 2 (comment) matched, add it to lits and replace with exact number of newlines
            if m.group(2) is not None:
                lits.append(m.group(2).strip())
            return "\n" * m.group(0).count("\n")

        code = pattern.sub(strip_callback, text)
        return code, "\n".join(lits)

    def _compile_regex_matrix(self, literal_pattern: Optional[str] = None) -> dict[str, re.Pattern]:
        """Safely pre-compiles the standard regex matrix based on dynamic config lengths."""
        matrix = {}

        # #386: fam_key now matches the real per-language "lexical_family"
        # values. "recursive_block"/"recursive_block_haskell"/
        # "positional_anchored" are excluded here because
        # _strip_segment_comments() already special-cases and fully handles
        # them above, before this matrix is ever consulted.
        #
        # #621: "standard_block" used to carry 9 delimiter tokens covering 3
        # incompatible comment conventions shared across one regex for all 29
        # "standard_block" languages, which corrupted real C-family code
        # (`i-- > 0` and `#include <vector>` both got swallowed as comments).
        # Split into "multi_style_dash" (sqlite/lua), "embedded_syntax"
        # (powershell), and "recursive_block_haskell" (haskell) instead --
        # see gitgalaxy_config.py's LEXICAL_FAMILY_HEURISTICS. perl moved to
        # the existing "line_exclusive" family (needed no new family at all).
        for fam_key, data in self.lexical_families.items():
            if fam_key in (
                "recursive_block",
                "recursive_block_haskell",
                "recursive_block_lisp",
                "positional_anchored",
                "positional_abap",
            ):
                continue

            delims = data.get("delimiters", [])
            if not delims:
                continue

            # Secure array escape
            d = [re.escape(x) for x in delims]
            p = ""

            # Dynamically build regex based on family type and safe bounds checks
            if fam_key == "standard_block" and len(d) >= 3:
                p = rf"({d[0]}[^\n]*|{d[1]}.*?{d[2]})"
            elif fam_key == "line_exclusive" and len(d) >= 1:
                p = rf"({d[0]}[^\n]*)"
            elif fam_key == "line_exclusive_dash" and len(d) >= 1:
                # #76: unlike "line_exclusive" above (whose single-delimiter
                # form here is actually dead code -- _strip_segment_comments
                # intercepts "line_exclusive" via _strip_single_line_comments
                # before this matrix is ever consulted), "line_exclusive_dash"
                # has no such interception, so this branch is the real,
                # active stripping path for it. Same shape (one delimiter,
                # runs to end of line) since Ada's `--` behaves identically.
                p = rf"({d[0]}[^\n]*)"
            elif fam_key == "embedded_syntax" and len(d) >= 3:
                # If len is 4, include d[3], otherwise just [0,1,2]
                if len(d) >= 4:
                    p = rf"({d[1]}.*?{d[2]}|{d[0]}[^\n]*|{d[3]}[^\n]*)"
                else:
                    p = rf"({d[1]}.*?{d[2]}|{d[0]}[^\n]*)"
            elif fam_key == "block_exclusive" and len(d) >= 2:
                p = rf"({d[0]}.*?{d[1]})"
            elif fam_key == "multi_style_dash" and len(d) >= 5:
                p = rf"({d[1]}.*?{d[2]}|{d[3]}.*?{d[4]}|{d[0]}[^\n]*)"
            elif fam_key == "multi_style_dash" and len(d) >= 3:  # Fallback
                p = rf"({d[1]}.*?{d[2]}|{d[0]}[^\n]*)"
            elif fam_key == "multi_style_live" and len(d) >= 5:
                p = rf"({d[3]}.*?{d[4]}|{d[0]}[^\n]*|{d[1]}[^\n]*|{d[2]}[^\n]*)"
            elif fam_key == "line_exclusive":
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
                    literal_mask = literal_pattern or self.LITERAL_MASK_PATTERN
                    # #2419: LiveCode has no `\` string escapes -- see
                    # MULTI_STYLE_LIVE_LITERAL_MASK_PATTERN's own comment.
                    if fam_key == "multi_style_live" and literal_pattern is None:
                        literal_mask = self.MULTI_STYLE_LIVE_LITERAL_MASK_PATTERN
                    full_pattern = f"{literal_mask}|{p}"

                    flags = re.S | re.M
                    if fam_key == "line_exclusive":
                        flags |= re.IGNORECASE

                    matrix[fam_key] = re.compile(full_pattern, flags)
                    self.logger.debug(f"Regex matrix compiled for family: {fam_key}")
                except re.error as e:
                    self.logger.error(f"Regex compilation failed for family '{fam_key}': {e}")

        return matrix

    def _compile_single_line_delimiter_patterns(self) -> dict[str, re.Pattern]:
        """
        Builds one delimiter alternation PER "line_exclusive" LANGUAGE,
        keyed by language id, from gitgalaxy_config.py's real
        "language_delimiters" map. #1193: this used to be a single pattern
        shared across all ~20 member languages, built from one flat
        "delimiters" list -- but `;` is only a real delimiter for
        assembly, and `%` only for matlab, so sharing one pattern falsely
        truncated ordinary code (`100 % 7`, CLI `--` args, `;`-terminated
        statements) for every other member. Falls back to the family's
        top-level "delimiters" list for any line_exclusive language without
        its own "language_delimiters" entry (defensive only -- every
        language currently in the family has one).

        Word-boundary-correct per Rule 9 (how_to_add_a_language.md): symbol-
        only tokens (#, ;, %, //, ::) are self-delimiting and get no \\b.
        `dnl`/`REM` are fully word-shaped and get \\b on both sides.
        `=begin`/`=end` start with a symbol but end in a word char -- a
        leading \\b would never fire at a real line start (same trap as
        PowerShell's `-Parallel` in the epic's recurring-bug-class list), so
        they only get a trailing \\b.
        """
        family = self.lexical_families.get("line_exclusive", {})
        fallback_delimiters = family.get("delimiters", [])
        language_delimiters = family.get("language_delimiters", {})

        patterns: dict[str, re.Pattern] = {}
        for lang_id, lang_data in self.languages.items():
            if lang_data.get("lexical_family") != "line_exclusive":
                continue
            delimiters = language_delimiters.get(lang_id, fallback_delimiters)
            patterns[lang_id] = self._compile_delimiter_alternation(delimiters, lang_id=lang_id)

        return patterns

    def _compile_delimiter_alternation(self, delimiters: list[str], lang_id: str = "") -> re.Pattern:
        """Compiles a single ReDoS-safe alternation over a flat delimiter list, applying Rule 9's word-boundary handling per token."""
        alternatives = []
        for token in delimiters:
            if not token:
                continue

            # In shell and makefile, '#' is only a comment if it is the start of a word (preceded by whitespace or start of line).
            # This protects POSIX parameter expansions like `${var##prefix}` from being falsely stripped.
            if token == "#" and lang_id in ("shell", "makefile"):  # noqa: S105
                alternatives.append(r"(?:^|(?<=\s))#")
                continue

            escaped = re.escape(token)
            starts_word = token[0].isalnum() or token[0] == "_"
            ends_word = token[-1].isalnum() or token[-1] == "_"
            if starts_word and ends_word:
                alternatives.append(rf"\b{escaped}\b")
            elif ends_word:
                alternatives.append(rf"{escaped}\b")
            elif starts_word:
                alternatives.append(rf"\b{escaped}")
            else:
                alternatives.append(escaped)

        if not alternatives:
            # Defensive fallback if config is ever empty -- matches nothing
            # rather than silently reintroducing the old hardcoded set.
            return re.compile(r"(?!)")

        return re.compile("(" + "|".join(alternatives) + ")", re.IGNORECASE)

    def _strip_python_docstrings(self, text: str) -> tuple[str, list[str]]:
        """Extracts triple-quoted strings as documentation."""
        docs = []

        def callback(m: re.Match) -> str:
            if m.group("triple") is None:
                # Either an ordinary single/double-quoted string literal
                # (e.g. the `'"""'` inside `nxt.endswith('"""')`) or a `#`
                # comment -- pass it through untouched. They're only in
                # this alternation so their contents can atomically claim
                # their own span and never get reconsidered by the triple-
                # quote branch below. Without the plain-string branch, a
                # `'"""'`-shaped literal could false-open a "docstring"
                # that only closed at the next real `"""` many lines later,
                # silently swallowing every real line (including a `def`)
                # in between. Without the `#`-comment branch, an English
                # contraction apostrophe inside a comment (isn't, doesn't)
                # would false-open the single-quote branch instead and pair
                # with whatever `'` came next anywhere later in the file --
                # both are the same bug class #1184 already fixed in
                # `_apply_literal_shield` (#1198).
                return m.group(0)
            docs.append(m.group(0).strip())
            # Replace with exactly as many newlines as the match itself
            # spans -- a fixed single "\n" (the previous behavior) only
            # preserved line count by coincidence for a 2-line docstring;
            # every other length desynced every line number downstream of
            # it (off by +1 for a 1-line docstring, -1 for 3 lines, -2 for
            # 4, ...), which accumulates across a whole file and can shift
            # `def` lines out of any per-line boundary tracking entirely
            # (#1198).
            return "\n" * m.group(0).count("\n")

        # Using re.DOTALL ensures [\s\S] matches newlines correctly. The
        # plain-string and comment alternatives are ordered alongside the
        # triple-quote ones (not stripped separately beforehand, and not
        # deferred to the later per-family comment stripper) so whichever
        # construct actually starts first at a given position atomically
        # wins the match -- mirrors _apply_literal_shield's single-pass
        # design. Only "#" is needed here (not "--"/"//") since python,
        # micropython, and ruby -- the only lang_ids routed to this
        # function -- all use "#" for line comments.
        #
        # #1271: the plain-string alternatives' escape handling is `\\[\s\S]`
        # (was `\\.`, which cannot match a literal newline without re.DOTALL
        # on the whole pattern). A backslash-newline line continuation --
        # legal inside a plain double/single-quoted string in both Ruby and
        # Python -- previously broke the plain-string alternative's ability
        # to consume the whole string as one atomic span: the `\\.` branch
        # couldn't cross the newline, and `[^"\\]`/[^'\\]` explicitly exclude
        # the backslash itself, so the match stalled right at the `\`. The
        # regex then fell through to the bare-comment alternative for the
        # continuation line(s), which -- for Ruby specifically -- can
        # false-match a `#{...}` string-interpolation opener as if it were a
        # `#` comment (confirmed via the language-crucible corpus: a
        # `system "... \` continuation in `rails/generator.rb` blanked out
        # several real `def` lines further down the file). `\\[\s\S]`
        # consumes the backslash-newline pair as part of the escaped-char
        # alternative instead, closing the gap for both quote styles.
        pattern = re.compile(
            r'(?P<triple>"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')|'
            r'"(?:\\[\s\S]|[^"\\])*"|'
            r"'(?:\\[\s\S]|[^'\\])*'|"
            r"(?:^|(?<=[ \t]))#[^\n]*",
            re.MULTILINE,
        )
        clean = pattern.sub(callback, text)
        return clean, docs

    def _strip_php_string_mass(self, text: str) -> tuple[str, list[str]]:
        """Surgically extracts PHP Heredoc and multi-line strings to prevent structural hallucinations."""
        lits = []

        def capture_lit(m: re.Match) -> str:
            # Save the literal into the Documentation stream
            lits.append(m.group(0).strip())
            # Replace with a safe, empty string literal to preserve PHP array syntax
            return '""'

        # 1. Extract Heredoc/Nowdoc
        text = self.PHP_HEREDOC_PATTERN.sub(capture_lit, text)

        return text, lits

    # #2450: PowerShell here-strings -- `@"` (only whitespace after, then a newline)
    # ... `"@` at the start of a line, and the literal `@'` ... `'@` form. Their
    # bodies routinely carry code-shaped text (this file generates a C#/IDL
    # interface from a `Write-Output @"namespace ... enum ProviderType { ... }"@`
    # here-string), and PowerShell's `embedded_syntax` lexical family strips only
    # `#` / `<# #>` comments -- nothing shields string mass -- so `class_start` /
    # `func_start` matched `enum ProviderType` inside the here-string as a real
    # declaration. Blanked to same-length filler (newlines kept) so byte offsets
    # and line numbers are unchanged, same idiom as `_mask_lua_long_brackets`.
    _PS_HERESTRING_RE = re.compile(r"@\"[^\n]*\n.*?\n\"@|@'[^\n]*\n.*?\n'@", re.DOTALL)

    def _strip_powershell_herestrings(self, text: str) -> tuple[str, list[str]]:
        """Blanks PowerShell here-string bodies (`@\" ... \"@` / `@' ... '@`) so their
        code-shaped contents can't be mis-read as real declarations, capturing each
        to the documentation stream. Newline-count preserving."""
        lits: list[str] = []

        def _repl(m: "re.Match[str]") -> str:
            lits.append(m.group(0).strip())
            return "".join("\n" if ch == "\n" else " " for ch in m.group(0))

        return self._PS_HERESTRING_RE.sub(_repl, text), lits

    # Tri-comparison manual verification (2026-08-31): Groovy triple-quoted strings
    # (`"""..."""` / `'''...'''`) routinely carry code-shaped fixture text -- Gradle
    # integration-test build-script snippets (`buildFile '''class Circular { ... }'''`),
    # Spock's own compiler-smoke-test source samples (`compiler.compileSpecBody("""def
    # m1() { ... }""")`) -- and groovy's `standard_block` lexical family only strips
    # `//`/`/* */` comments, nothing shields multi-line string mass. The shared
    # SHIELD_PATTERN's single/double-quote branches can't help either: matched against
    # a `"""`  open, the double-quote branch's `(?:\\.|[^"\\])*"` immediately hits the
    # second `"` (excluded from its own negated class) and closes on it, consuming just
    # `""` as one empty string and leaving the third quote as a stray unshielded
    # character -- the real triple-quoted span is never treated as one unit, so
    # `class_start`/`func_start` matched real-looking text inside it directly, and a
    # stray/mismatched leftover quote could desync brace-counting for the rest of the
    # file. Non-greedy so back-to-back triple-quoted strings don't merge into one span.
    # Blanked to same-length filler (newlines kept) so byte offsets and line numbers
    # are unchanged, same idiom as `_strip_powershell_herestrings`/
    # `_mask_lua_long_brackets`.
    _GROOVY_TRIPLE_QUOTED_RE = re.compile(r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'')

    def _strip_groovy_triple_quoted_strings(self, text: str) -> tuple[str, list[str]]:
        """Blanks Groovy triple-quoted string bodies (`\"\"\"...\"\"\"` / `'''...'''`)
        so their code-shaped contents can't be mis-read as real declarations, capturing
        each to the documentation stream. Newline-count preserving."""
        lits: list[str] = []

        def _repl(m: "re.Match[str]") -> str:
            lits.append(m.group(0).strip())
            return "".join("\n" if ch == "\n" else " " for ch in m.group(0))

        return self._GROOVY_TRIPLE_QUOTED_RE.sub(_repl, text), lits

    def _strip_asm_block_comments(self, text: str) -> tuple[str, list[str]]:
        """Strips C-style `/* ... */` block comments before assembly's own `line_exclusive`
        family (`;`/`#` line comments only, per its own docstring: "The language possesses no
        native multi-line block syntax") ever runs. Real gap, not theoretical: `.S` files are
        routed through the C preprocessor before assembling, so both GAS and NASM `.S`/`.asm`
        sources routinely carry genuine `/* */` blocks (BSD/FreeBSD kernel license headers, Emacs
        modelines, register-usage doc comments) that `line_exclusive` never recognized at all --
        confirmed real corpus false positives (`func_start` matching label-shaped text INSIDE an
        unstripped block comment): `Result:` (linux_1_0_kernel/drivers_FPU-emu_reg_u_div.S, a
        stack-layout doc comment) and `r9:`/`r10:`/`r11:` (freebsd_kernel_arch/amd64_amd64_
        kexec_tramp.S, a register-usage doc comment), 5 occurrences total across the corpus.

        Runs BEFORE `;`/`#` line-stripping, not after -- deliberately, confirmed by direct corpus
        measurement rather than assumed either way. 121 real `/* ... */` blocks in this same
        corpus contain a bare `;` or `#` (copyright-header prose, URLs, Emacs modelines like
        `/*-*- mode:unix-assembly; indent-tabs-mode:t; ... -*-*/`, and `/* #define ... */`-style
        commented-out-code notes) -- stripping line comments FIRST would truncate every one of
        those blocks at its first internal `;`/`#`, corrupting the search for the block's real
        closing `*/` (silently swallowing everything up to the next UNRELATED `*/` later in the
        file, or the whole rest of the file if none exists). The reverse direction was also
        checked and found clean: zero lines in this corpus have a `;`/`#` line comment containing
        an unclosed `/*` that could similarly mis-pair with a later real `*/`. Same shielded-
        alternation idiom as the generic REGEX_MATRIX stripper (LITERAL_MASK_PATTERN tried first
        so a `/*`-shaped byte sequence inside a real string literal, e.g. `.ascii "a /* b"`,
        passes through unharmed), same non-greedy-bounded-by-two-fixed-delimiters shape already
        accepted as ReDoS-safe for every "standard_block" C-family language's own `/\\*.*?\\*/`.
        """
        lits: list[str] = []
        pattern = re.compile(rf"{self.LITERAL_MASK_PATTERN}|(/\*.*?\*/)", re.DOTALL)

        def _repl(m: "re.Match[str]") -> str:
            if m.group(1) is not None:
                return m.group(0)
            comment = m.group(2)
            lits.append(comment.strip())
            return "\n" * comment.count("\n")

        return pattern.sub(_repl, text), lits

        return self._PS_HERESTRING_RE.sub(_repl, text), lits

    _LUA_LONG_BRACKET_RE = re.compile(r"(?:--)?\[(=*)\[.*?\]\1\]", re.DOTALL)

    @staticmethod
    def _lua_lb_opener_in_string(text: str, opener_start: int) -> bool:
        """#2437: a `[[` / `[=[` inside a single-line `"..."` / `'...'` string
        literal (`t("[=[alo]]")`, `"[[\\n...]]"` escape-test data) is string
        content, not a real long-bracket opener -- blanking it would corrupt the
        enclosing real string. Detected via an unclosed quote in the line
        prefix."""
        seg = text[text.rfind("\n", 0, opener_start) + 1 : opener_start]
        in_q: Optional[str] = None
        i = 0
        while i < len(seg):
            c = seg[i]
            if c == "\\":
                i += 2
                continue
            if in_q is not None:
                if c == in_q:
                    in_q = None
            elif c in ('"', "'"):
                in_q = c
            i += 1
        return in_q is not None

    def _mask_lua_long_brackets(self, text: str) -> str:
        """Blanks Lua long-bracket literals -- strings `[[ ... ]]` / `[=[ ... ]=]`
        and long comments `--[[ ... ]]` -- to same-length filler, preserving every
        newline so byte offsets and line numbers are unchanged. Used only to build
        the embedded-language TRIGGER scan view: `<script>` / `<style>` sitting
        inside a `Write([[<!doctype html> ... ]])` heredoc is string data, not a
        real embedded segment, and must not split the enclosing Lua function
        (#2440)."""

        def _repl(m: "re.Match[str]") -> str:
            if self._lua_lb_opener_in_string(m.string, m.start()):
                return m.group(0)
            return "".join("\n" if ch == "\n" else " " for ch in m.group(0))

        return self._LUA_LONG_BRACKET_RE.sub(_repl, text)

    def _partition_embedded_languages(self, content: str, primary_id: str) -> list[tuple[str, str]]:
        """Splits content into language segments based on embedded language triggers."""
        segments = []
        last_idx = 0

        # #2440: detect triggers against a view where Lua long-bracket string
        # bodies are blanked (offsets preserved); segment slicing below still
        # uses the untouched `content`.
        scan_view = self._mask_lua_long_brackets(content) if primary_id == "lua" else content

        triggers: list[dict[str, Any]] = []
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
                    content_lower = scan_view.lower()  # One fast C-level allocation
                if hint not in content_lower:
                    continue  # Skip the expensive regex entirely!

            triggers.extend(
                {
                    "start": m.start(),
                    "end_pattern": t_config["end"],
                    "target": t_config["target"],
                    "pair": t_config["pair"],
                    "trigger_end": m.end(),
                }
                for m in t_config["trigger"].finditer(scan_view)
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
                end_match = t["end_pattern"].search(scan_view, pos=t["trigger_end"], endpos=search_limit)
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
        limit = int(min(start_pos + self.EMBEDDED_LOOKAHEAD_LIMIT, len(text)))

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

    def _strip_nested_comments(self, text: str, family: str = "recursive_block") -> tuple[str, list[str]]:
        """
        Iterative Peel loop for recursively nested block comments (e.g. Rust/Swift/Scala,
        or Haskell via the "recursive_block_haskell" family -- #621).
        Hardened with active string-masking to prevent logic erosion.
        """
        # #386 follow-up: was "recursive_c_style" -- missed in the original
        # rename pass. Currently harmless by coincidence (the fallback default
        # below matches "recursive_block"'s real delimiters exactly today),
        # but was silently ignoring the real config, not reading it.
        delims = self.lexical_families.get(family, {}).get("delimiters", ["//", "/*", "*/"])
        if len(delims) < 3:
            return text, []

        s_line, b_start, b_end = delims[0], delims[1], delims[2]
        lits = []

        # 1. Protect Strings AND single-line comments via ONE atomic pass.
        # Masking prevents the `.rfind` mathematical loop from tearing apart string literals.
        #
        # BUG FIX (#1302, found while investigating #1266): this used to be the shared
        # `LITERAL_MASK_PATTERN`'s single-quote branch, unbounded (`'(?:\\.|[^'\\])*'`),
        # matching from ANY unpaired `'` to the NEXT unrelated `'` anywhere later in the
        # file -- run as its own pass, BEFORE single-line comments were stripped. Every
        # language routed through this function has a common source of unpaired single
        # quotes that are NOT real char literals: an English contraction inside a
        # `//`/`--`/`;` comment ("it's", "don't"), Scala's Symbol literals (`'foo`, no
        # closing quote), Haskell's idiomatic trailing-apostrophe identifiers (`x'`,
        # `map'`), and Scheme's pervasive quote syntax (`'expr`) -- and the identical shape
        # recurred for the backtick branch too (Scala/Kotlin-style backtick-quoted
        # identifiers are always short, but a single stray, unpaired backtick inside an
        # ordinary comment -- a real upstream typo, confirmed on a live Kafka corpus file:
        # `// 'protected` to allow override for testing` -- paired with the next unrelated
        # backtick anywhere later, e.g. a completely separate `` `counts` `` reference).
        # Either could mask out real characters (confirmed on real corpus files: one Scala
        # file's code_stream dropped to 13.75% of its original size, one Swift file to
        # 11.06%) -- silently misclassifying real functions as "string content" before
        # `func_start` ever sees them.
        #
        # Bounding each quote branch's width (single-quote to 10 chars, matching char
        # literals; backtick to 200, matching `func_start`'s own established identifier
        # bound) closes the WORST (multi-thousand-character) cascades, but doesn't fully
        # close the gap on its own: two unrelated backtick-marked references inside
        # nearby comments (a realistic, even common, distance in real files) can still
        # fall within that same bound and falsely pair with each other. The real fix,
        # matching the same atomic-pass idiom already proven for detector.py's Mode
        # C/D/E shields and prism.py's own generic REGEX_MATRIX stripper (#1184/#1192/
        # #1222) and Mode B's `_build_brace_safe_stream` (which already includes `//`/`/*`
        # as alternatives IN the same combined pattern): fold single-line-comment
        # recognition into this SAME pass as the quote alternatives, so whichever
        # construct starts first at a given position atomically claims its whole span.
        # Since a `//` marker always appears at or before any quote character later on
        # the same physical line, the comment alternative -- being the leftmost possible
        # match start -- claims the entire line before the scanner ever reaches an
        # apostrophe/backtick inside it, regardless of how far away an unrelated
        # real quote/backtick happens to sit.
        combined_pattern = re.compile(
            r'(?<!\\)"(?:\\.|[^"\\])*"'
            r"|(?<!\\)'(?![a-zA-Z_]\w*[=<>(),&|\]\s])(?:\\.|[^'\\]){0,10}'"
            r"|(?<!\\)`(?:\\.|[^`\\]){0,200}`"
            rf"|{re.escape(s_line)}[^\n]*",
            re.S | re.M,
        )
        string_cache: dict[str, str] = {}

        def _combined_replacer(m: re.Match) -> str:
            matched = m.group(0)
            if matched.startswith(s_line):
                lits.append(matched.strip())
                return ""
            key = f"__GALAXY_STR_MASK_{len(string_cache)}__"
            string_cache[key] = matched
            return key

        protected_code = combined_pattern.sub(_combined_replacer, text)

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

        # 2. Iteratively peel nested blocks from the inside out
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

            # #1532: replace with an equal count of newlines rather than deleting the
            # span outright -- this used to drop every line the comment itself spanned,
            # so every function AFTER even one multi-line block comment anywhere in the
            # file got attributed to the wrong (too-early) start_line, cumulative for
            # each such comment. Mirrors the generic REGEX_MATRIX stripper's own
            # `strip_callback` (`"\n" * m.group(0).count("\n")`, this same file) and
            # detector.py's index-aligned shields, which already preserve line counts
            # the same way.
            protected_code = (
                protected_code[:start_idx] + ("\n" * block_content.count("\n")) + protected_code[end_match.end() :]
            )
            safety += 1

        if safety >= self.NESTED_PEEL_LIMIT:
            self.logger.warning(f"Nested Peel Guard triggered: Reached max iteration limit ({self.NESTED_PEEL_LIMIT}).")

        # 3. Final Logic Unmasking
        return unmask(protected_code), lits

    def _strip_positional_comments(
        self, text: str, abap_mode: bool = False, cobol_mode: bool = False
    ) -> tuple[str, str]:
        """Column-anchored and Inline stripping for legacy languages (COBOL/Fortran/ABAP)."""
        code, lits = [], []

        # #1898: ABAP is free-form except for its OWN column-1 `*` full-line-comment
        # rule -- it has no column-7 indicator area and no `C`/`c`/`/`/`!` column-1
        # markers at all, unlike Fortran (`C` in column 1) and COBOL (fixed-form
        # column-7 markers), which the shared POSITIONAL_ANCHORS set was built for.
        # Real ABAP class headers are conventionally written flush-left (`CLASS foo
        # DEFINITION`), so column 1 is a literal "C" -- sharing Fortran/COBOL's
        # anchor set silently erased every real class declaration as a bogus
        # comment before class_start ever ran. ABAP gets its own anchor set (just
        # `*`) and skips the column-7 check entirely.
        anchors = {"*"} if abap_mode else self.POSITIONAL_ANCHORS

        for line in text.split("\n"):
            # 1. Legacy Column-1 (Fortran/COBOL) or Column-7 (COBOL only) anchors
            # (Fixed Form). Column 7 is COBOL's indicator area ('*' = comment) --
            # real fixed-form Fortran 77 has no such convention (its only comment
            # marker is column 1; column 6 is a continuation flag, not a comment
            # one). Confirmed real (tri-comparison-ledger-sweep, fortran, 2026-08-21):
            # applying the column-7 check to Fortran too silently erased any real
            # statement whose 7th character happened to coincide with an anchor
            # char -- e.g. a 3-space-indented `   FUNCTION foo(...)` puts the 'C'
            # of FUNCTION at column 7, wiping the whole declaration line as a
            # bogus comment before func_start ever saw it (wrf/module_configure.F:353
            # `in_use_for_config`, wrf/module_domain.F:1693 `first_loc_integer`).
            if (len(line) >= 1 and line[0] in anchors) or (cobol_mode and len(line) >= 7 and line[6] in anchors):
                code.append("")
                lits.append(line)
                continue

            # 2. Modern Inline Fortran (!), COBOL (*>), and ABAP (") comments.
            # #259: mask string/char literals first -- per line, the same bounded
            # discipline _strip_single_line_comments adopted for #1184 -- so a
            # delimiter-shaped character INSIDE a literal (`DISPLAY "Rate *> 5%"`,
            # `PRINT *, "Warning!"`, ABAP `x = 'he said "hi"'`) isn't mistaken for
            # a real inline-comment marker, truncating the statement mid-literal
            # and leaving code_stream with a dangling unterminated quote. Every
            # other stripping path in this file already shields this way; this one
            # didn't. ABAP masks single-quote/backtick only (its `"` is the
            # comment delimiter, not a quote -- see ABAP_LITERAL_MASK_PATTERN).
            # A literal continued onto a later line via a fixed-form column-7 `-`
            # indicator is out of scope: masking is deliberately line-bounded, so
            # a delimiter in the continuation half stays unshielded (#1184).
            mask_pat = self.ABAP_LITERAL_MASK_PATTERN if abap_mode else self.LITERAL_MASK_PATTERN
            masked_line, masked_lits = self._mask_line_literals(line, mask_pat)

            if "*>" in masked_line:
                head, tail = masked_line.split("*>", 1)
                code.append(self._restore_masked_literals(head, masked_lits))
                lits.append(self._restore_masked_literals("*>" + tail, masked_lits))
            elif abap_mode and '"' in masked_line:
                head, tail = masked_line.split('"', 1)
                code.append(self._restore_masked_literals(head, masked_lits))
                lits.append(self._restore_masked_literals('"' + tail, masked_lits))
            elif not abap_mode and "!" in masked_line:
                # #1911: `!` has no comment meaning in ABAP at all (its only
                # real markers are `*` in column 1 and `"` inline) -- it's
                # the classic ABAP formal-parameter-name escape prefix
                # (`!iv_url TYPE string`), extremely common in every method
                # signature's IMPORTING/EXPORTING/CHANGING clause. Without
                # this gate every `!param` line was truncated at the `!`,
                # erasing the parameter name and its TYPE clause.
                head, tail = masked_line.split("!", 1)
                code.append(self._restore_masked_literals(head, masked_lits))
                lits.append(self._restore_masked_literals("!" + tail, masked_lits))
            else:
                code.append(line)
                lits.append("")

        return "\n".join(code), "\n".join(lits)

    def _guard_metadata_signal(self, content: str) -> tuple[str, str]:
        """Protects shebangs and preprocessor headers from the stripping engine."""
        lines = content.split("\n", 1)
        if not lines:
            return "", ""

        first = lines[0]
        # Explicit guard for #! and early PHP/XML execution tags
        if first.startswith(("#!", "<?php", "<?xml")):
            return first + "\n", lines[1] if len(lines) > 1 else ""

        return "", content

    def _strip_single_line_comments(self, text: str, lang_id: str) -> tuple[str, str]:
        """
        Single-line comment stripper for the "line_exclusive" family, driven
        by each language's own real delimiter list (see
        _compile_single_line_delimiter_patterns) rather than one guess
        shared across the whole family. #697: this used to hardcode
        `#|--|;|//`, which incorrectly included `--` (never a configured
        line_exclusive delimiter). #1193: a shared delimiter list across all
        ~20 member languages was its own bug (`;`/`%` falsely truncating
        code in languages that don't use them as comment markers), and the
        delimiter search ran directly against raw text with zero string-
        literal shielding, so a delimiter character appearing INSIDE a
        string literal (e.g. Python's `"SELECT 1;"`) truncated the literal
        itself.

        Masks string/char literals with LITERAL_MASK_PATTERN before
        searching for the delimiter -- but PER LINE, not as one pass over
        the whole multi-line text. Masking the whole text in one pass
        reopens the exact hazard #1184 just fixed elsewhere: an unmatched
        quote inside a real comment (e.g. "# don't stop") pairs with a real
        string's quote many lines later and the mask swallows every real
        line of code in between. Bounding the mask to one line at a time
        means a stray quote can, at worst, mis-pair with another quote on
        that SAME line -- always fully recoverable on restore -- and can
        never reach into a different line.

        #1271: the one deliberate exception to "never reach into a
        different line" above -- a literal that opens on one line and only
        closes on a LATER one via backslash-newline continuation (legal in
        both Ruby and Python). Without tracking that, the continuation
        line(s) look like fresh code to this per-line scan, and a comment-
        delimiter-shaped token inside them (Ruby's `#{...}` string
        interpolation, most visibly) gets misread as a real comment,
        corrupting everything after it. Carrying the open quote char
        forward is safe against reintroducing #1184's hazard specifically
        because the carry is only ever opened from the CODE portion of a
        line (never the comment portion, split off first below) -- a stray
        quote inside a real comment can still only mis-pair within that
        same line, exactly as #1184 intended.

        Gated to `lang_id in ("python", "micropython", "ruby")` -- the same
        set already routed through `_strip_python_docstrings` above, whose
        `"`/`'` are always genuine string delimiters. Confirmed unsafe to
        widen to the rest of the "line_exclusive" family: Perl's `y///`,
        `tr///`, `s///`, and `m//` quote-like operators can contain a bare
        `"`/`'` that is NOT a string delimiter at all (e.g. `y/"//d`, a
        real idiom that transliterates away literal double-quotes) --
        without the gate, that bare quote false-opened a carry that
        persisted for hundreds of lines until an unrelated later quote
        happened to close it, corrupting every real comment in between
        (confirmed via language-crucible's perl/mojo/Template.pm).
        """
        pattern = self.SINGLE_LINE_DELIMITER_PATTERNS.get(lang_id) or re.compile(r"(?!)")
        carry_aware = lang_id in ("python", "micropython", "ruby", "shell")
        code, comments = [], []
        carry_quote: Optional[str] = None

        if lang_id == "perl":
            perl_bare_regex_preceding = re.compile(
                r"(?:(?:=~|!~|\(|,|;|\{|&&|\|\|)[ \t]*$)|(?:\b(?:if|unless|while|split|grep|map|return)[ \t]+$)"
            )
            perl_candidate_pattern = re.compile(r"\b(?:qw|qq|qx|qr|tr|q|m|s|y)[ \t]*[\{/]|/")

            def _mask_perl_line(line: str, masked_literals: list[str]) -> str:
                pos = 0
                parts = []
                while pos < len(line):
                    match = perl_candidate_pattern.search(line, pos)
                    if not match:
                        parts.append(line[pos:])
                        break
                    start = match.start()
                    parts.append(line[pos:start])
                    matched_str = match.group(0)
                    is_brace_op = matched_str.endswith("{")
                    is_slash_op = matched_str.endswith("/") and len(matched_str) > 1
                    is_bare_slash = matched_str == "/"
                    if is_bare_slash and not perl_bare_regex_preceding.search(line[:start]):
                        parts.append("/")
                        pos = start + 1
                        continue
                    op_start_idx = start
                    if is_brace_op:
                        depth = 1
                        idx = match.end()
                        while idx < len(line):
                            ch = line[idx]
                            if ch == "\\":
                                idx += 2
                                continue
                            if ch == "{":
                                depth += 1
                            elif ch == "}":
                                depth -= 1
                                if depth == 0:
                                    break
                            idx += 1
                        op_keyword = matched_str[:-1].strip()
                        end_idx = min(idx + 1, len(line))
                        if op_keyword in ("s", "tr", "y") and end_idx < len(line):
                            ws_match = re.match(r"[ \t]*", line[end_idx:])
                            ws_len = len(ws_match.group(0)) if ws_match else 0
                            second_start = end_idx + ws_len
                            if second_start < len(line) and line[second_start] == "{":
                                depth = 1
                                idx2 = second_start + 1
                                while idx2 < len(line):
                                    ch = line[idx2]
                                    if ch == "\\":
                                        idx2 += 2
                                        continue
                                    if ch == "{":
                                        depth += 1
                                    elif ch == "}":
                                        depth -= 1
                                        if depth == 0:
                                            break
                                    idx2 += 1
                                end_idx = min(idx2 + 1, len(line))
                        span_text = line[op_start_idx:end_idx]
                        masked_literals.append(span_text)
                        parts.append(f"__MASK_{len(masked_literals) - 1}__")
                        pos = end_idx
                    else:
                        idx = match.end()
                        while idx < len(line):
                            ch = line[idx]
                            if ch == "\\":
                                idx += 2
                                continue
                            if ch == "/":
                                break
                            idx += 1
                        end_idx = min(idx + 1, len(line))
                        op_keyword = matched_str[:-1].strip() if is_slash_op else ""
                        if op_keyword in ("s", "tr", "y") and end_idx < len(line):
                            idx2 = end_idx
                            while idx2 < len(line):
                                ch = line[idx2]
                                if ch == "\\":
                                    idx2 += 2
                                    continue
                                if ch == "/":
                                    break
                                idx2 += 1
                            end_idx = min(idx2 + 1, len(line))
                        span_text = line[op_start_idx:end_idx]
                        masked_literals.append(span_text)
                        parts.append(f"__MASK_{len(masked_literals) - 1}__")
                        pos = end_idx
                return "".join(parts)

        # #1954: split on real newlines only. str.splitlines() also breaks
        # on vertical tab, form feed, the file/group/record separators, NEL
        # and the Unicode line/paragraph separators -- so a form feed inside
        # a comment (Cosmopolitan libc's ape.S uses form feed as a page-break
        # idiom) turned into a literal newline on rejoin, drifting every
        # downstream start_line by the running count of such characters.
        # CR / CRLF is still normalised the way splitlines() did.
        normalized_text = text.replace("\r\n", "\n").replace("\r", "\n")
        for line in normalized_text.split("\n"):
            head = ""
            if carry_quote is not None:
                close_pattern = self.CARRY_QUOTE_CLOSE_PATTERNS[carry_quote]
                m = close_pattern.match(line)
                if not m:
                    # Still inside the carried-over literal for its entire
                    # length -- not code to search for a delimiter at all.
                    code.append(line)
                    continue
                head, line, carry_quote = line[: m.end()], line[m.end() :], None

            masked_line, masked_literals = self._mask_line_literals(line)

            if lang_id == "perl":
                masked_line = _mask_perl_line(masked_line, masked_literals)

            if pattern.search(masked_line):
                parts = pattern.split(masked_line, 1)
                code_part = parts[0]
                comment_part = parts[1] + (parts[2] if len(parts) > 2 else "")
            else:
                code_part = masked_line
                comment_part = None

            if carry_aware:
                # Only the code portion (never comment_part) may open a new
                # carry -- see the docstring note above on why this can't
                # reintroduce #1184.
                tail_match = self.UNTERMINATED_QUOTE_TAIL_PATTERN.search(code_part)
                if tail_match:
                    # Everything from the unpaired quote to end-of-line is
                    # the (so-far) unterminated literal's own text.
                    masked_literals.append(code_part[tail_match.start() :])
                    code_part = code_part[: tail_match.start()] + f"__MASK_{len(masked_literals) - 1}__"
                    carry_quote = tail_match.group(0)

            code.append(head + self._restore_masked_literals(code_part, masked_literals))
            if comment_part is not None:
                comments.append(self._restore_masked_literals(comment_part, masked_literals))

        return "\n".join(code), "\n".join(comments)

    def _mask_line_literals(self, line: str, pattern: Optional[str] = None) -> tuple[str, list[str]]:
        """Replaces each string/char literal on a single line with a `__MASK_N__` placeholder, returning the masked line and the literals in match order. `pattern` overrides the default LITERAL_MASK_PATTERN (e.g. #259's ABAP mask, which must not treat `"` as a quote)."""
        masked_literals: list[str] = []

        def shield_callback(m: re.Match) -> str:
            masked_literals.append(m.group(0))
            return f"__MASK_{len(masked_literals) - 1}__"

        return re.sub(pattern or self.LITERAL_MASK_PATTERN, shield_callback, line), masked_literals

    def _restore_masked_literals(self, masked: str, masked_literals: list[str]) -> str:
        """Reverses _mask_line_literals, substituting each `__MASK_N__` placeholder back for its original literal text."""
        prev = None
        while masked != prev:
            prev = masked
            masked = re.sub(r"__MASK_(\d+)__", lambda m: masked_literals[int(m.group(1))], masked)
        return masked
