# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

from typing import Any

from gitgalaxy.standards.language_standards import _lazy_re as re  # #3914: compiled on first use
from gitgalaxy.standards.language_standards.identifiers import ID_CONTINUE, ID_START

from .._shared_patterns import GLOBAL_FRAGILE_DEBT, GLOBAL_PLANNED_DEBT, commented_keyword_statement

# #5909: a `switch` arm is `label body`. The label is a pattern, not a command, and a one-line body
# (`x { doX }`) is not at command position. `_rewrite_tcl_calls` blanks each label and puts the body on
# its own line, with `;` as a line break. It also blanks `proc` parameter lists (whose default-value
# braces `{a ""}` `{b ""}` otherwise trigger `} {`), joins `\` line continuations, blanks braced data
# values of `set` and `foreach`/`lmap` lists, and exposes one-line `{body}` blocks of `foreach`/`lmap`,
# `after <ms|idle>`, and `uplevel <level>`.
_WS = " \t\r\n"
_QUOTE_BEFORE = frozenset(" \t\r\n[{;(,=")


def _scan_tcl_quoted(text: str, start: int, out: list[str]) -> int:
    r"""Scan a Tcl double-quoted string starting at `start` (`text[start] == '"'`).

    If a matching closing `"` is found:
    - When it contains unescaped `[...]` command substitutions, blank the outer quotes and literal
      bytes while preserving `[...]` (recursively processing nested `"..."` inside them).
    - When it contains no `[...]`, blank the interior (keeping newlines and the outer `"..."`
      delimiters) so `_apply_literal_shield` and `_rewrite_tcl_calls` still see a single quoted
      word token (e.g. a `switch` arm label `"a b"`).
    If unmatched, leave `out` untouched and return `start + 1`.
    """
    n = len(text)
    i = start + 1
    # Collect interior indices to blank so an unmatched `"` (e.g. inside `{"}`) leaves `out` unchanged.
    to_blank: list[int] = []
    nested_quotes: list[tuple[int, int]] = []
    bracket_depth = 0
    has_subst = False
    while i < n:
        ch = text[i]
        if ch == "\\":
            if bracket_depth == 0:
                to_blank.append(i)
                if i + 1 < n and text[i + 1] != "\n":
                    to_blank.append(i + 1)
            i += 2
            continue
        if bracket_depth == 0:
            if ch == '"':
                if has_subst:
                    out[start] = " "
                    out[i] = " "
                for idx in to_blank:
                    if out[idx] != "\n":
                        out[idx] = " "
                for q_start, q_end in nested_quotes:
                    for idx in range(q_start, q_end):
                        if out[idx] != "\n":
                            out[idx] = " "
                return i + 1
            if ch == "[":
                bracket_depth = 1
                has_subst = True
                i += 1
                continue
            if ch != "\n":
                to_blank.append(i)
            i += 1
        else:
            if ch == "[":
                bracket_depth += 1
                i += 1
            elif ch == "]":
                bracket_depth -= 1
                i += 1
            elif ch == '"' and (i == 0 or text[i - 1] in _QUOTE_BEFORE):
                # Recursively scan a double-quoted string inside `[...]` command substitution.
                sub_out = list(text)
                end_q = _scan_tcl_quoted(text, i, sub_out)
                if end_q > i + 1:
                    nested_quotes.extend(
                        (idx, idx + 1) for idx in range(i, end_q) if sub_out[idx] == " " and text[idx] != " "
                    )
                    i = end_q
                else:
                    i += 1
            else:
                i += 1
    return start + 1


def _expose_tcl_quoted_substitutions(text: str) -> str:
    r"""Pre-shield rewrite for Tcl: expose `[...]` command substitutions inside `"..."` strings
    before `_apply_literal_shield` blanks quoted literals, and cleanly blank multi-line `"..."`
    strings with escaped `\"` / `\[` / `\\\n`."""
    if '"' not in text:
        return text
    out = list(text)
    n = len(text)
    i = 0
    at_line_start = True
    while i < n:
        ch = text[i]
        if ch == "\n":
            at_line_start = True
            i += 1
            continue
        if at_line_start and ch in " \t":
            i += 1
            continue
        if at_line_start and ch == "#":
            # Skip `#` comment line (including `\\\n` continuations) so `"` in comments doesn't open a string.
            while i < n and text[i] != "\n":
                if text[i] == "\\" and i + 1 < n and text[i + 1] == "\n":
                    i += 2
                    continue
                i += 1
            continue
        at_line_start = False
        if ch == "\\":
            i += 2
            continue
        if ch == '"' and (i == 0 or text[i - 1] in _QUOTE_BEFORE):
            i = _scan_tcl_quoted(text, i, out)
            continue
        i += 1
    return "".join(out)


def _word_end(text: str, i: int, stop: str) -> int:
    """Index just past the Tcl word at `i`: a braced / quoted / bracketed word, or a bare one up to `stop`."""
    close = {"{": "}", '"': '"', "[": "]"}.get(text[i])
    n = len(text)
    if close is None:
        while i < n and text[i] not in stop:
            i += 2 if text[i] == "\\" else 1
        return min(i, n)
    opener, depth, i = text[i], 1, i + 1
    while i < n:
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        depth += ch == opener != close
        depth -= ch == close
        i += 1
        if depth == 0:
            return i
    return n


def _skip_blank(text: str, i: int, newlines: bool) -> int:
    ws = _WS if newlines else " \t"
    while i < len(text) and (text[i] in ws or text.startswith("\\\n", i)):
        i += 2 if text[i] == "\\" else 1
    return i


def _blank_span(out: list[str], start: int, end: int) -> None:
    for q in range(start, end):
        if out[q] != "\n":
            out[q] = " "


def _is_cmd_pos(text: str, at: int) -> bool:
    before = text[:at].rstrip(" \t")[-1:]
    return not before or before in "\n[{;"


def _expose_braced_body(text: str, out: list[str], start: int, end: int) -> None:
    if start < end and text[start] == "{" and end - 1 > start and text[end - 1] == "}":
        out[start] = "\n"
        out[end - 1] = " "


def _join_line_continuations(text: str) -> str:
    """Replace Tcl backslash-newline continuations (`\\\n`) with two spaces (same length)."""
    if "\\\n" not in text:
        return text
    out = list(text)
    n = len(text)
    i = 0
    while i < n - 1:
        if text[i] == "\\" and text[i + 1] == "\n":
            # Count consecutive preceding backslashes: only an odd total continues the line.
            bs = 1
            j = i - 1
            while j >= 0 and text[j] == "\\":
                bs += 1
                j -= 1
            if bs % 2 == 1:
                out[i] = " "
                out[i + 1] = " "
            i += 2
        else:
            i += 1
    return "".join(out)


def _rewrite_tcl_calls(text: str) -> str:
    """Same-length structural rewrite for Tcl `calls_out` extraction."""
    text = _join_line_continuations(text)
    out = list(text)
    n = len(text)

    # 1. Blank `proc <name> {<args>}` parameter lists so default-value braces `{v ""}` never fire `} {`,
    # and expose the proc's `{body}` so one-line procs (`proc f {args} { uplevel ... }`) stay at command position.
    pos = 0
    while True:
        at = text.find("proc", pos)
        if at < 0:
            break
        pos = at + 4
        if not _is_cmd_pos(text, at) or text[pos : pos + 1] not in (" ", "\t"):
            continue
        i = _skip_blank(text, pos, False)
        if i >= n or text[i] in "\n;]":
            continue
        i = _skip_blank(text, _word_end(text, i, _WS + ";]"), False)  # proc name
        if i < n and text[i] == "{":
            args_end = _word_end(text, i, _WS)
            _blank_span(out, i, args_end)
            body_i = _skip_blank(text, args_end, False)
            if body_i < n and text[body_i] == "{":
                body_end = _word_end(text, body_i, _WS)
                _expose_braced_body(text, out, body_i, body_end)

    # 2. `switch`: blank arm labels and expose braced arm bodies.
    pos = 0
    while True:
        at = text.find("switch", pos)
        if at < 0:
            break
        pos = at + 6
        if not _is_cmd_pos(text, at) or text[pos : pos + 1] not in (" ", "\t"):
            continue
        i = _skip_blank(text, pos, False)
        while i < n and text[i] == "-":  # options, then `--`
            i = _skip_blank(text, _word_end(text, i, _WS), False)
        if i >= n or text[i] in "\n;]":
            continue
        i = _skip_blank(text, _word_end(text, i, _WS + ";]"), False)  # the subject
        if text[i : i + 1] == "{":
            end = _word_end(text, i, _WS)
            i, newlines = i + 1, True
            end -= 1
            word_stop = _WS  # inside `{ ... }`, `]` in a regex pattern does not end a label
        else:
            end, newlines = n, False
            word_stop = _WS + ";]"
        while True:
            i = _skip_blank(text, i, newlines)
            if i >= end or text[i] in "\n;]":
                break
            label_end = _word_end(text, i, word_stop)
            _blank_span(out, i, label_end)
            i = _skip_blank(text, label_end, newlines)
            if i >= end or text[i] in "\n;]":
                break
            body_end = _word_end(text, i, word_stop)
            if text[i] == "{":
                _expose_braced_body(text, out, i, body_end)
            i = body_end

    # 3. `foreach` / `lmap`: blank braced list arguments and expose the trailing braced body.
    for kw in ("foreach", "lmap"):
        klen = len(kw)
        pos = 0
        while True:
            at = text.find(kw, pos)
            if at < 0:
                break
            pos = at + klen
            if not _is_cmd_pos(text, at) or text[pos : pos + 1] not in (" ", "\t"):
                continue
            words: list[tuple[int, int]] = []
            i = _skip_blank(text, pos, False)
            while i < n and text[i] not in "\n;]":
                w_end = _word_end(text, i, _WS + ";]")
                words.append((i, w_end))
                i = _skip_blank(text, w_end, False)
            if len(words) >= 3:
                # Words are (varlist1, list1, [varlist2, list2, ...], body).
                body_s, body_e = words[-1]
                if text[body_s] == "{":
                    _expose_braced_body(text, out, body_s, body_e)
                for idx in range(1, len(words) - 1, 2):
                    ls, le = words[idx]
                    if text[ls] == "{":
                        _blank_span(out, ls, le)

    # 4. `after <ms|idle> {body}` and `uplevel <level> {body}`: expose braced script body.
    for kw in ("after", "uplevel"):
        klen = len(kw)
        pos = 0
        while True:
            at = text.find(kw, pos)
            if at < 0:
                break
            pos = at + klen
            if not _is_cmd_pos(text, at) or text[pos : pos + 1] not in (" ", "\t"):
                continue
            i = _skip_blank(text, pos, False)
            if i >= n or text[i] in "\n;]":
                continue
            w1_end = _word_end(text, i, _WS + ";]")
            w1 = text[i:w1_end]
            if kw == "after" and not (w1.isdigit() or w1 == "idle"):
                continue
            if kw == "uplevel" and not (w1.isdigit() or (w1.startswith("#") and w1[1:].isdigit())):
                continue
            i = _skip_blank(text, w1_end, False)
            if i < n and text[i] == "{":
                body_end = _word_end(text, i, _WS + ";]")
                _expose_braced_body(text, out, i, body_end)

    # 5. `set <var> {data}`: a braced value assigned by `set` is literal data, never executed here.
    pos = 0
    while True:
        at = text.find("set", pos)
        if at < 0:
            break
        pos = at + 3
        if not _is_cmd_pos(text, at) or text[pos : pos + 1] not in (" ", "\t"):
            continue
        i = _skip_blank(text, pos, False)
        if i >= n or text[i] in "\n;]":
            continue
        i = _skip_blank(text, _word_end(text, i, _WS + ";]"), False)  # varName
        if i < n and text[i] == "{":
            val_end = _word_end(text, i, _WS + ";]")
            _blank_span(out, i, val_end)

    return "".join(out)


DEFINITION: dict[str, Any] = {
    "_meta": {
        "target_version": "Tcl 8.6 / SQLite Test Suite",
        "last_updated": "2026-03-11",
        "blueprint_version": "",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard scripts and Tcl modules.
    "extensions": [".tcl", ".itcl", ".tbc", ".tm"],  # Removed .test
    # ABSOLUTE IDENTITY & EXACT FILENAMES:
    "exact_matches": ["tclIndex", "pkgIndex.tcl"],
    # ECOSYSTEM ANCHORS: Added .test here so it only anchors, but doesn't claim globally.
    "discriminators": [".tcl", "tclIndex", ".test", "Makefile"],
    # EXECUTION SIGNATURES: Standard interpreters found on Line 1.
    "shebangs": ["tclsh", "wish", "bin/expect", "jimsh"],
    # UPGRADED: Maps to Family 3 (Pure Hash)
    # Rationale: Tcl natively uses '#' exclusively for line-level comments. It does not
    # have native block comments (developers sometimes hack `if 0 { ... }`, but `#` is the standard).
    "lexical_family": "line_exclusive",
    "calls_out_namespace_qualifiers": True,
    "rules": {
        # Epic #3264: Explicitly declare the structural invocation paradigm
        # #3359 (contract C7): command position, minus the upper-case SQL keywords
        # that start the lines of a brace-quoted query (`db eval { SELECT ...\n
        # WHERE ... }`). Tcl cannot shield braces, which are also code bodies, so
        # the SQL words are excluded by name, upper-case only: `set`/`update` are
        # real Tcl commands. The lookahead is one bounded alternation (Rule 5).
        # #5640: a one-line brace body is command position too: after `} {` (`if {$a} {foo}`), after `;`
        # (`set x 1; foo`), or after a script-taking word (`catch {qux}`). `after <ms|idle>`, `uplevel <level>`,
        # `foreach`, `lmap`, and `switch` bodies are exposed by `_rewrite_tcl_calls`.
        # Contract C6: `ns::cmd` / `::cmd` emits the leaf callee (`cmd`) with `ns` as its qualifier.
        "calls_out": re.compile(
            r"(?m)(?:^[ \t]*|\[[ \t]*|;[ \t]*|\}[ \t]*\{[ \t]*"
            r"|(?:(?<=\bcatch)|(?<=\belse)|(?<=\btry)|(?<=\bfinally)|(?<=\beval)|(?<=\buplevel))[ \t]+\{[ \t]*)"
            r"(?!(?:SELECT|INSERT|UPDATE|DELETE|REPLACE|FROM|WHERE|SET|VALUES|INTO|AND|OR|NOT"
            r"|UNION|WITH|AS|ON|USING|JOIN|INNER|OUTER|LEFT|CROSS|NATURAL|ORDER|GROUP|HAVING|LIMIT|OFFSET"
            r"|CREATE|DROP|ALTER|TABLE|INDEX|VIEW|TRIGGER|BEGIN|COMMIT|ROLLBACK|PRAGMA|COALESCE|CASE|WHEN"
            r"|THEN|ELSE|END|EXCEPT|INTERSECT|RETURNING|DISTINCT|ALL|IN|IS|NULL|LIKE|BETWEEN)(?!["
            + ID_CONTINUE
            + r":-]))"
            r"(?!::env(?![-" + ID_CONTINUE + r"]))"
            r"(?:(?:::)?(?:[" + ID_START + r"][" + ID_CONTINUE + r"-]*::)+|::)?"
            r"([" + ID_START + r"][" + ID_CONTINUE + r"-]*)(?<=[" + ID_CONTINUE + r"])(?![" + ID_CONTINUE + r":.$,=])"
        ),
        # Expose `[...]` command substitutions inside `"..."` before the literal shield blanks strings.
        "_calls_out_pre_shield": _expose_tcl_quoted_substitutions,
        # #5909: `switch` arms, `proc` param lists, `\` line continuations, `foreach`/`lmap`/`after`/`uplevel`/`set`.
        "_calls_out_rewrite": _rewrite_tcl_calls,
        "_calls_out_ignore": frozenset(
            {
                "proc",
                "namespace",
                "source",
                "elseif",
                "else",
                "foreach",
                "variable",
                "package",
                "global",
                "then",
                "break",
                "continue",
                "error",
            }
        ),
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch (Control Flow / Branching)
        # Tcl control flow keywords.
        "branch": re.compile(r"\b(?:if|elseif|else|switch|while|for|foreach)\b"),
        # 2. args (Parameters / Coupling)
        # Safely captures the parameter list `{...}` immediately following a proc name.
        "args": re.compile(
            # =====================================================================
            # [ THE VERTICAL PROC SHIELD (TCL) ]
            # Tcl developers can break the `proc`, name, and argument brace `{}`
            # across newlines.
            # FIX: Upgraded horizontal `[ \t]+` constraints to vertical `[ \t\n]+`.
            # =====================================================================
            # BUG FIX: Expanded to support 3 levels of nesting to handle deeply nested default values.
            # BUG FIX: Expanded name character set to include -, !, ?
            r"^[ \t]*proc[ \t\n]+["
            + ID_CONTINUE
            + r":\-!?]+[ \t\n]+\{((?:[^{}]|\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\})*)\}",
            re.M,
        ),
        # Tcl default-value argument lists (#1512): opt-in for depth-aware braced parameter parsing.
        "_args_tcl_pattern_list_groups": {1},
        # 3. linear (Sequential Boundaries)
        # Structural boundaries. EXCLUDES: global/upvar (globals/heat).
        "structural_boundaries": re.compile(r"\b(?:proc|return|break|continue|namespace|variable|yield)\b"),
        # 4. func_start (Executable Logic Anchors)
        # MUST HAVE EXACTLY ONE CAPTURE GROUP.
        # Captures standard procs and namespaced procs (e.g., `proc ::my::func`).
        # BUG FIX: Expanded name character set to include -, !, ?
        "func_start": re.compile(
            r"^[ \t]*proc[ \t\n]+(["
            + ID_CONTINUE
            + r":\-!?]+)(?:[ \t\n]+\{(?:[^{}]|\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\})*\})?(?=[ \t\n]*\{|[ \t\n]|$)",
            re.M,
        ),
        # 5. class_start (Object / Entity Declarations)
        # Captures TclOO, Snit, and Itcl class definitions.
        # BUG FIX: Expanded name character set to include -, !, ?
        "class_start": re.compile(
            r"^[ \t]*(?:oo::class[ \t\n]+create|snit::type|itcl::class)[ \t\n]+(["
            + ID_CONTINUE
            + r":\-!?]+)(?=[ \t]*\{|[ \t\n]|$)",
            re.M,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        # 6. safety (Defensive Checks: assert/try/guards, validation)
        # Safe evaluation and error catching.
        "safety": re.compile(r"\b(?:catch|try|trap|finally|info[ \t]+exists|assert)\b"),
        # 7. safety_neg (Safety Bypasses / Unchecked Types)
        # Unrestricted evaluation and context manipulation.
        "safety_bypasses": re.compile(r"\b(?:eval|uplevel|upvar)\b"),
        # 8. danger (High-Risk Execution / System Calls)
        # OS command execution and process termination.
        # #2878 contract C2: hyphen-guarded (`ports_deactivate_no-exec`); C4 `file delete -force`
        # is a path deletion (cleanup's question, #2843).
        "high_risk_execution": re.compile(r"(?<![-" + ID_CONTINUE + r"])(?:exec|exit)(?![-" + ID_CONTINUE + r"])"),
        # 9. io (I/O & Network Boundaries)
        # File system, sockets, and configuration. (Excludes puts which is mapped to print_hits).
        "io": re.compile(
            # #2841 contract: C2 -- `source` is import's hit, `close` is cleanup's;
            # C1 -- everyday words fire only in command position (line start or
            # after `[`), `file` only with a filesystem subcommand.
            r"(?:^[ \t]*|\[)(?:open|read|gets|socket|fconfigure)\b"
            r"|\bvfs::"
            r"|\bfile[ \t]+(?:exists|tail|mkdir|delete|rename|copy|size|isfile|isdirectory|dirname|join|normalize|stat|atime|mtime)\b",
            re.M,
        ),
        # 10. api (Public Surface Area)
        # Exposing packages or namespace exports.
        "api": re.compile(r"^[ \t]*(?:package[ \t]+provide|namespace[ \t]+export)\b", re.M),
        # #2774: the ORPHAN-CENSUS EXEMPTION. `_is_orphan` is a textual
        # name-recurrence test, so naming a function in an export statement --
        # the one place a library is *guaranteed* to name a function it never
        # calls itself -- counted as a use and cleared its orphan flag. Measured
        # on keyword-rosetta/data/shell: 3 orphans per file without the export
        # lines, 0 with them. Five languages publish a FUNCTION (rather than a
        # variable) by naming it, and all five sat at `raw_state_unreferenced`
        # 0.25 against a 2.50 median because of it.
        #
        # This is deliberately NOT the `api` rule, though it overlaps it. `api`
        # matches broad visibility MODIFIERS in most languages (javascript's is
        # a bare `export`, java's a bare `public`), so discounting every line it
        # matched would silently swallow a genuine call in
        # `export const x = foo();`. This rule instead captures the exported
        # NAME, and only that capture's own span is discounted -- so a language
        # opts in by declaring it, and the other 41 are unchanged by
        # construction. Leading `_` keeps it out of `coding_analysis`'s rule
        # loop and the counts schema, the same way `_scope_filters` does.
        "_visibility_export": re.compile(
            r"^[ \t]*namespace[ \t]+export[ \t]+([" + ID_START + r"][" + ID_CONTINUE + r"]*)", re.M
        ),
        # 11. flux (State Mutation)
        # Variable state mutations.
        "state_mutation": re.compile(
            r"\b(?:set|lappend|dict[ \t]+set|array[ \t]+set|incr|append)\b[ \t]+[" + ID_CONTINUE + r":]+"
        ),
        # 12. dead_code (Commented Logic / Deprecated Trails)
        # Commented out structural code.
        # #7207: a statement's shape (`;{}`, `(...)`, an assignment, `set x $y` / `set x 1`, `return $x`), not just the keyword.
        "dead_code": re.compile(
            commented_keyword_statement(
                "proc|set|if|while|foreach|return",
                marker=r"^[ \t]*#",
                extra=r"(?<=set)[ \t]+[\w:()$]+[ \t]+(?:[\"$\[{][^\n]{0,400}|-?\d+(?:\.\d+)?[ \t]*)(?m:$)"
                r"|(?<=return)[ \t]+(?:\$[\w:]+|[\"\[]|-code\b)[^\n]{0,400}(?m:$)",
            ),
            re.M,
        ),
        # 13. doc (Structured Documentation)
        # Tcl doc blocks.
        "doc": re.compile(r"^[ \t]*#[ \t]*@(?:param|return|brief|author)", re.M),
        # 14. test (Testing & Assertions)
        # *THE SQLITE MEGA-SENSOR*: Accurately maps the SQLite custom test harnesses alongside standard tcltest.
        "test": re.compile(
            r"\b(?:do_test|do_execsql_test|do_catchsql_test|do_eqp_test|do_ioerr_test|do_faultsim_test|test\s+["
            + ID_CONTINUE
            + r"-]+|tcltest::|finish_test)\b"
        ),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # 15. concurrency (Asynchronous Execution)
        # Event loops, delays, and threads.
        "concurrency": re.compile(r"\b(?:vwait|after|thread::|coroutine|yield)\b"),
        # 16. ui_framework (UI / View Components)
        # Tkinter/Tk graphical elements.
        "ui_framework": re.compile(r"\b(?:button|pack|grid|place|canvas|frame|label|ttk::)\b"),
        # 17. closures (Closures / Anonymous Functions)
        # Tcl 8.6 anonymous functions.
        "closures": re.compile(r"\bapply[ \t]+\{"),
        # 18. globals (Global / Shared State)
        # Tcl relies heavily on global imports and environment arrays.
        # BUG FIX: `::env` starts with `::` (non-word) inside the
        # shared `\b(...)\b` group. Real usage (`$::env(HOME)`) always
        # precedes it with `$`, also non-word -- `\b` between two
        # non-word chars can never fire, so `::env` never matched.
        # Pulled out with no leading `\b` (self-delimiting on `::`).
        # #2859: `global NAME…` is the statement form; `$global` is an ordinary
        # variable read, so the `(?<!\$)` guard keeps the command and drops the
        # sigil'd identifier an ordinary reference cannot be a declaration.
        "globals": re.compile(r"(?<!\$)\bglobal\b|::env\b|upvar[ \t]+#0"),
        # 19. decorators
        "decorators": None,
        # 20. generics
        "generics": None,
        # 21. comprehensions
        # Tcl 8.6 list map.
        "comprehensions": re.compile(r"\blmap\b"),
        # 22. scientific (Numerical / Compute Libraries)
        # Explicit math invocations via expr.
        "scientific": re.compile(r"\b(?:expr|math::)\b|\b(?:sin|cos|tan|sqrt|exp|log|pow)\b"),
        # reflection_metaprogramming (Metaprogramming: macros, reflection, goto)
        # High Cognitive Load: Intercepting variables, tracking execution, and runtime aliasing.
        "reflection_metaprogramming": re.compile(r"\b(?:trace[ \t]+add|rename|interp[ \t]+create|interp[ \t]+alias)\b"),
        # 24. import (Dependency Inclusions)
        # Package and module loading.
        "import": re.compile(r"^[ \t]*(?:package[ \t]+require|source|load)\b", re.M),
        "dependency_injection": None,
        "_dependency_capture": re.compile(
            r"^[ \t]*(?:package[ \t\n]+require|source|load)[ \t\n]+(?:-exact[ \t\n]+)?(?:\{?[\"']?)([^\"'\s#{}]+)",
            re.M,
        ),
        # 25. ownership (Authorship Metadata)
        # #2882 contract: C2 `Copyright:` out
        "ownership": re.compile(
            r"^[ \t]*(?:#+)[ \t]*(?:Authors?|Created[ \t]+by|Maintainers?|Owners?|Developers?|Contact)[ \t]*:(?![:=])[ \t]*(\S[^\n]*?)[ \t]*(?:\*/|-->)?[ \t]*$|^[ \t]*(?-i:(?:Author|AUTHOR)(?:s|S)?|Created[ \t]+by|CREATED[ \t]+BY|Maintainer(?:s)?|MAINTAINER(?:S)?|Owner(?:s)?|OWNER(?:S)?|Developer(?:s)?|DEVELOPER(?:S)?|Contact|CONTACT)[ \t]*:(?![:=])[ \t]*(\S[^\n]*?)(?<![,;{(])[ \t]*(?:\*/|-->)?[ \t]*$|@author:?[ \t]+(\S[^\n]*?)[ \t]*(?:\*/|-->)?[ \t]*$",
            re.I | re.M,
        ),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        # 26. planned_debt (Annotated Debt / TODOs)
        "planned_debt": GLOBAL_PLANNED_DEBT,
        # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        # BUG FIX: confirmed O(n^2) ReDoS -- the SPEC alternative's
        # unbounded `\d+` sits directly adjacent to the also-unbounded
        # `[^\]]*`, whose charset fully overlaps digits. Same bug shape
        # already found and fixed in embedded_python's and css's
        # independent copies of this pattern. Measured ~4x runtime per
        # doubling. Bounded `\d+` to `\d{1,10}` and `[^\]]*` to
        # `{0,300}`.
        "spec_exposure": re.compile(r"\[(?:[ \t]*SPEC[ \t]*-[ \t]*\d{1,10}|spec|audit)[^\]]{0,300}\]", re.I),
        "ssr_boundaries": None,
        # 32. events (Event Emitters / Pub-Sub)
        # Tcl event bindings and file event handlers.
        "events": re.compile(r"\b(?:bind|fileevent|vwait|trace[ \t]+add)\b"),
        "macros": None,
        "pointers": None,
        "memory_alloc": None,
        "inline_asm": None,
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # 38. telemetry (Structured Logging / Telemetry)
        "telemetry": re.compile(r"\b(?:log::log|logger::|syslog)\b"),
        # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
        "debug_prints": re.compile(r"\bputs\b"),
        # # 40. explicit_casts (Explicit Type Casting)
        "explicit_casts": re.compile(r"\bexpr[ \t]+(?:int|double|wide)\("),
        # 41. panics_and_aborts (Error Exits: error/exit)
        "panics_and_aborts": re.compile(r"\b(?:error|exit)\b"),
        # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
        "thread_sleeps": re.compile(r"\bafter[ \t]+[0-9]+\b"),
        # 43. bitwise_ops (Bitwise Operations)
        "bitwise_ops": re.compile(r"(?<!&)&(?!&)|(?<!\|)\|(?!\|)|\^|~|<<|>>"),
        # 44. sync_locks (Resource Management & Stability)
        "sync_locks": re.compile(r"\b(?:thread::mutex|thread::rwmutex|thread::cond)\b"),
        # 45. immutability_locks (Immutability Constraints)
        # Tcl lacks `const`, but setting a trace to prevent writes is the Tcl idiom for freezing.
        "immutability_locks": re.compile(r"\btrace[ \t]+add[ \t]+variable[ \t]+[" + ID_CONTINUE + r":]+[ \t]+write\b"),
        # 46. cleanup (Resource Cleanup / Teardown)
        "cleanup": re.compile(
            r"\b(?:close|unset)\b|\bfile[ \t]+delete\b|rename[ \t]+[" + ID_CONTINUE + r':]+[ \t]+""'
        ),  # #2888/#2843: file delete destroys external state
        # 47. encapsulation (Access Modifiers / Encapsulation)
        # Internal namespaces and private `_` prefixed procs.
        # #2766: contract-level absence. `namespace eval` defines a namespace
        # boundary (structure, not a per-name visibility marker) and the `proc _x`
        # underscore is convention without probe incidence; tcl names remain
        # reachable via qualified paths.
        "encapsulation": None,
        # 48. listeners (Event Listeners / Observers)
        "listeners": re.compile(r"\b(?:bind|fileevent)\b"),
        # 49. test_skip (Bypassed Tests / Ignored Specs)
        # Using TclTest constraints to silently skip tests on certain OS environments.
        "test_skip": re.compile(
            r"-constraints[ \t]+[" + ID_CONTINUE + r"]+(?![" + ID_CONTINUE + r"])|\btestConstraint\b"
        ),
    },
}
