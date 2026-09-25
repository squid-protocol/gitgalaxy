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

# ------------------------------------------------------------------------------
# 3. UNIVERSAL DOMAIN SENSORS (Applied to ALL languages)
# Consumed by: detector.py (LogicSplicer)
# ------------------------------------------------------------------------------
# ==============================================================================
# GLOBAL LOCALIZATION DICTIONARIES (Cross-Cultural Tech Debt)
# Consumed by: All languages in LANGUAGE_DEFINITIONS
# ==============================================================================

# --- 1. PLANNED DEBT (TODOs, WIPs, Promises) ---
_SPACED_PLANNED = (
    r"\b("
    r"TODO|WIP|STUB|IMPLEMENT|@todo|"  # English
    r"POR HACER|A IMPLEMENTAR|PENDIENTE|"  # Spanish
    r"A FAZER|PENDENTE|TAREFA|"  # Portuguese
    r"A FAIRE|A IMPLEMENTER|EN ATTENTE|"  # French
    r"ZU ERLEDIGEN|MACHEN|OFFEN|IMPLEMENTIEREN|"  # German
    r"СДЕЛАТЬ|ДОДЕЛАТЬ|ПЛАН|РЕАЛИЗОВАТЬ|"  # Russian
    r"DA FARE|DA IMPLEMENTARE|"  # Italian
    r"DO ZROBIENIA|DO POPRAWY|"  # Polish
    r"TE DOEN|NOG DOEN|"  # Dutch
    r"HARUS DIBUAT|UNTUK DIBUAT"  # Indonesian
    r")\b"
)
_DENSE_PLANNED = (
    r"(?:"
    r"待办|未完成|将来做|需要优化|暂未实现|"  # Mandarin
    r"後でやる|未実装|実装予定|"  # Japanese
    r"할일|할 일|미구현|나중에|"  # Korean
    r"करना है|बाद में|"  # Hindi (Devanagari)
    r"للقيام به|لاحقا|يجب عمله"  # Arabic
    r")"
)
# #2537: `-` is a regex word boundary, so the bare `\b(...)\b` alternations
# matched debt keywords EMBEDDED INSIDE hyphenated code identifiers -- COBOL
# data items (`HACK-LEVEL`, `BUG-COUNT`), COBOL/Lisp-family paragraph and
# symbol names (`PROBE-TODO`, `probe-todo`), css classes (`.bug-icon`) --
# inflating tech-debt scoring from ordinary code in exactly the hyphenated-
# identifier ecosystems (COBOL/JCL, Lisp, css) where debt measurement matters
# most. Python's `HACK_LEVEL` was inert only by tokenization luck (`_` is a
# word char, so `\bHACK\b` can't fire mid-identifier).
# THE GUARD: refuse a match glued to a hyphen-plus-alphanumeric on either
# side -- the shape of an identifier CONTINUING through the hyphen. Real
# comment markers keep counting, including hyphen-adjacent ones whose
# neighbor char is NOT alphanumeric: `-- TODO x` (Ada/Haskell/SQL comments),
# a glued `--TODO`, or a trailing `TODO--` (the char beside the hyphen is
# another `-`, not a letter/digit). Deliberately scoped to the SPACED
# (Latin/Cyrillic) alternation only: the DENSE CJK/RTL alternation has no
# hyphenated-identifier idiom to guard against.
_HYPHEN_IDENT_PRE = r"(?<![A-Za-z0-9]-)"
_HYPHEN_IDENT_POST = r"(?!-[A-Za-z0-9])"

GLOBAL_PLANNED_DEBT = re.compile(f"{_HYPHEN_IDENT_PRE}{_SPACED_PLANNED}{_HYPHEN_IDENT_POST}|{_DENSE_PLANNED}", re.I)


# --- 2. FRAGILE DEBT (Hacks, FIXMEs, Code Smells) ---
_SPACED_FRAGILE = (
    r"\b("
    r"HACK|FIXME|XXX|BUG|KLUDGE|UGLY|WTF|"  # English
    r"PARCHE|ARREGLAR|TRUCO|FEO|CHAPUZA|"  # Spanish (Chapuza = Shoddy fix)
    r"GAMBIARRA|CONSERTAR|REPARAR|FEIO|REMENDO|"  # Portuguese (Gambiarra = Duct-tape hack)
    r"BIDOUILLE|A CORRIGER|REPARER|MOCHE|"  # French (Bidouille = Hack)
    r"KAPUTT|REPARIEREN|PFUSCH|MÜLL|"  # German (Pfusch = Botch job)
    r"КОСТЫЛЬ|ИСПРАВИТЬ|УБРАТЬ|ФИКС|ГРЯЗНО|"  # Russian (Kostyl = Crutch/Workaround)
    r"SISTEMARE|PEZZA|ORRIBILE|DA FIXARE|"  # Italian (Pezza = Patch)
    r"OBEJŚCIE|TYMCZASOWE|NAPRAWIĆ|"  # Polish (Obejście = Workaround)
    r"FIXEN|TIJDELIJK|LELIJK|OPLOSSING|"  # Dutch
    r"PERBAIKI|SEMENTARA|JELEK"  # Indonesian
    r")\b"
)
_DENSE_FRAGILE = (
    r"(?:"
    r"修复|临时代码|黑客做法|丑陋|坑|写死|硬编码|"  # Mandarin
    r"修正|ハック|一時的|汚い|やばい|"  # Japanese
    r"수정|임시|꼼수|버그|"  # Korean
    r"जुगाड़|ठीक करना|अस्थाई|"  # Hindi (Jugaad = Hack/Workaround)
    r"مؤقت|إصلاح|ترقيع"  # Arabic (Tarqie = Patching/Hacking)
    r")"
)
# #2537: same hyphenated-identifier guard as GLOBAL_PLANNED_DEBT above.
GLOBAL_FRAGILE_DEBT = re.compile(f"{_HYPHEN_IDENT_PRE}{_SPACED_FRAGILE}{_HYPHEN_IDENT_POST}|{_DENSE_FRAGILE}", re.I)


# --- 3. AI / LLM & ML SDK DETECTION (split by SIGNAL_SCHEMA category) ---
# Mirrors GLOBAL_PLANNED_DEBT/GLOBAL_FRAGILE_DEBT: compiled once here and
# referenced identically by every language block that wants it, instead of
# being hand-pasted per-language (see #322).
_IMPORT_WRAPPER = r"\b(?:import|require|from)\b.*?(?:{names})\b"

_LLM_API_NAMES = r"openai|anthropic"
_LLM_ORCHESTRATOR_NAMES = r"langchain|llama_index"
_LLM_VECTOR_STORE_NAMES = r"chromadb|pinecone"
_ML_TRADITIONAL_NAMES = r"sklearn"
_DL_FRAMEWORKS_NAMES = r"tensorflow|torch|keras"

GLOBAL_LLM_API = re.compile(_IMPORT_WRAPPER.format(names=_LLM_API_NAMES))
GLOBAL_LLM_ORCHESTRATOR = re.compile(_IMPORT_WRAPPER.format(names=_LLM_ORCHESTRATOR_NAMES))
GLOBAL_LLM_VECTOR_STORE = re.compile(_IMPORT_WRAPPER.format(names=_LLM_VECTOR_STORE_NAMES))
GLOBAL_ML_TRADITIONAL = re.compile(_IMPORT_WRAPPER.format(names=_ML_TRADITIONAL_NAMES))
GLOBAL_DL_FRAMEWORKS = re.compile(_IMPORT_WRAPPER.format(names=_DL_FRAMEWORKS_NAMES))

# A `<script>` whose `type` attribute is any of these carries NO executable logic
# -- a browser treats every `type` outside the JS-MIME / `module` / bare set as an
# inert data block and never runs it. Real corpus cases: reveal.js
# `text/template` slide samples (literal `function` text shown as a code listing),
# `x-shader/x-vertex` / `x-shader/x-fragment` GLSL sources, `math/tex` (MathJax),
# JSON `application/ld+json`. GitGalaxy's polyglot detector must not descend into
# them and its html `func_start` must not anchor a function-analog on them (#2492).
# The list is the denylist complement of tree_sitter_accuracy_audit.py's own
# `_EXECUTABLE_SCRIPT_TYPES` allowlist -- keep the two in sync.
_HTML_NONEXECUTABLE_SCRIPT_TYPES = (
    r"text/template|text/x-template|text/x-handlebars-template|text/html|"
    r"application/json|application/ld\+json|x-shader/x-[a-z]+|math/tex"
)
# Matches a `<script ...>` OPEN TAG carrying a non-executable `type`. Used by
# detector.py's Mode B slicer to drop such a match after `_build_brace_safe_stream`
# has blanked the quoted `type` value out of the stream `func_start` is matched
# against (so `func_start`'s own negative lookahead below can't see it there).
# `[^>]*` stays inside the tag (Rule 5 negated class); one unbounded quantifier.
HTML_NONEXECUTABLE_SCRIPT_TAG = re.compile(
    r"<script\b[^>]*?\btype[ \t\n\r\f]*=[ \t\n\r\f]*[\"']?(?:" + _HTML_NONEXECUTABLE_SCRIPT_TYPES + r")",
    re.IGNORECASE,
)

# ------------------------------------------------------------------------------
# 4. LANGUAGE DEFINITIONS (The Structural Signature Matrix)
# Consumed by: detector.py, language_lens.py, prism.py
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
# 5. STRUCTURAL INVOCATION PARADIGMS (Epic #3264)
# Consumed by: detector.py (calls_out_to extraction)
# ------------------------------------------------------------------------------

# C-Family / Algol-Family (name followed by optional space and open parenthesis)
CALLS_OUT_C_STYLE = re.compile(r"\b([a-zA-Z_]\w*)\s*\(")

# #3359 (contract C1): the C-style pattern for languages whose `@Name(...)` is a
# metadata annotation -- a declaration, never an invocation (java, kotlin, swift,
# dart, groovy, scala). NOT for python/typescript/javascript, where a decorator
# factory `@retry(3)` really is a call to `retry`. A dotted annotation
# (`@javax.annotation.Generated(`) still leaks its last segment, a known gap:
# the lookbehind is fixed-width on purpose (Rule 5). detector.py treats this
# pattern exactly like CALLS_OUT_C_STYLE (qualifier capture included).
CALLS_OUT_C_STYLE_NO_ANNOTATION = re.compile(r"(?<!@)\b([a-zA-Z_]\w*)\s*\(")

# #3644 (contract C3): the C-style pattern for languages that write a type-argument
# list between a callee and its `(` -- C++ `static_cast<int>(`,
# `Object::cast_to<T>(`, `back_inserter<vector<wstring> >(`, TypeScript/C#
# `new Array<T>()`. The list is optional, opens right after the name (no blank,
# so a spaced comparison `a < b` never starts one), nests one level, stays on
# one line, holds no `( ) ; { } = | ! ?` or quote, and ends in `>` then `(`.
# Every quantifier is bounded and the two alternatives start on disjoint
# characters (Rules 1-3). detector.py treats it exactly like CALLS_OUT_C_STYLE.
_GENERIC_ARG_CHAR = r"[^<>()\n;{}=|!?\"']"
CALLS_OUT_C_STYLE_GENERIC = re.compile(
    r"\b([a-zA-Z_]\w*)"
    r"(?:<(?:" + _GENERIC_ARG_CHAR + r"|<" + _GENERIC_ARG_CHAR + r"{0,200}>){1,200}>[ \t]*)?"
    r"\s*\("
)

# #3377: Ruby calls without parentheses. `name(` alone found a third of Ruby's
# calls: idiomatic Ruby writes `obj.to_s`, `xs.each do`, `puts x`, and method
# names end in `?`/`!` (`key?(k)`, `command! "brew"`). Group 1 is the callee,
# `?`/`!` included (never the `!=`/`=~` operators, nor a `name?:` hash label),
# so detector.py runs it exactly like CALLS_OUT_C_STYLE (qualifier capture, C5
# header check). A name is a call when it:
#   - follows a receiver dot (`obj.name`, `obj&.name`, `"".name`, a leading-dot
#     chain line) or `Mod::name` (lowercase, so never a constant);
#   - is a non-keyword followed by `(` (`name(`, `name?(`), or ends in `?`/`!`
#     (`quiet?`, `fetch!`): a local variable never does, so it is always a call;
#   - opens a statement as a command with an argument (`puts x`, `raise Foo`,
#     `command! ""`): a lowercase non-keyword, blanks, then an argument start,
#     and not a modifier (`value if cond`) -- no `?` suffix there, so a ternary
#     `ready ? a : b` is not a call.
# A bare word with no dot, paren or argument (`foo`) is never matched: without
# a symbol table Ruby cannot tell a local variable from a call (issue #3377).
_RUBY_KEYWORD = (
    r"(?:alias|and|begin|break|case|class|def|defined\?|do|else|elsif|end|ensure|false|for|if|in|module"
    r"|next|nil|not|or|redo|rescue|retry|return|self|super|then|true|undef|unless|until|when|while|yield)"
    r"(?![\w?!])"
)
_RUBY_CALLEE = r"[a-zA-Z_]\w*(?:[?!](?![=~:]))?"
CALLS_OUT_RUBY = re.compile(
    r"(?:(?<=[\w)\]}?!\"'`]\.)|(?<=[\w)\]}?!\"'`]&\.)|(?<=[ \t\n]\.)|(?<=\A\.)|(?<=\w::)(?=[a-z_])"
    r"|(?<![@$.:])\b(?!" + _RUBY_KEYWORD + r")(?=" + _RUBY_CALLEE + r"[ \t]*\(|[a-zA-Z_]\w*[?!](?![=~:]))"
    r"|^[ \t]*(?!" + _RUBY_KEYWORD + r")(?=[a-z_]\w*!?[ \t]+"
    r"(?!(?:if|unless|while|until|rescue|and|or|then|do|in)\b)[\w:\"'@$\[%]))"
    r"(" + _RUBY_CALLEE + r")",
    re.M,
)

# The invocation patterns detector.py treats as the C-style family: group 1 is
# the callee, the receiver chain before it is its qualifier (#3329), and a
# capture on a nested `func_start` header is a declaration (#3360).
QUALIFIED_CALLS_OUT_PATTERNS = (
    CALLS_OUT_C_STYLE,
    CALLS_OUT_C_STYLE_NO_ANNOTATION,
    CALLS_OUT_C_STYLE_GENERIC,
    CALLS_OUT_RUBY,
)

# Unsupported / AST-Required (Shell, Markup, Data, Config)
# Mapped to None to officially declare intentional blindness rather than extracting garbage.
CALLS_OUT_UNSUPPORTED = None

# Verb-invocation family (FORTRAN, PL/I, REXX, DB2 SQL, assembly): `CALL name`.
# Deliberately NOT cobol's paradigm: PERFORM is cobol-only, and `GO\s+TO` would
# capture numeric statement labels (FORTRAN `GO TO 100`), so cobol keeps its
# language-local rule. Charset admits `$#@` (mainframe identifiers) and `-`.
# #3520: the FIRST character may be any Unicode letter or a national character too
# (`[^\W\d]` = a letter or `_`): navikt/DSF writes `CALL ÅPNE_DATABASE`, which an
# ASCII-only first character skipped entirely.
CALLS_OUT_CALL_VERB = re.compile(r"(?i)\bCALL\s+['\"]?((?:[^\W\d]|[$#@])[\w$#@-]*)")

# Lisp family (scheme): the callee is the first symbol after an open paren.
# Charset includes lisp identifier punctuation (probe-branch, null?, set!).
CALLS_OUT_LISP_FAMILY = re.compile(r"\(\s*([A-Za-z_][A-Za-z0-9_!?*<>=+-]*)")

# Command-position family (tcl, powershell, livecode): the callee is the first
# word on a statement line. Charset covers tcl `ns::proc` interior colons and
# PS `Verb-Noun`; a leading-`::` fully-qualified tcl call is a known recall gap
# (the first character must be a letter/underscore for precision).
# Consumers MUST pair this with a `calls_out_ignore` set of the language's
# statement keywords, since those also appear in command position.
CALLS_OUT_COMMAND_POSITION = re.compile(r"(?m)^[ \t]*([A-Za-z_][\w:-]*)\b")
