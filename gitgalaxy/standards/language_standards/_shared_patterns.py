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

from gitgalaxy.standards.language_standards.identifiers import ID_CONTINUE, ID_START

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
#
# #4137 / #4150: every AI/ML import-pack rule is anchored on the library's
# TOP-LEVEL package, not on any path segment that happens to share its name.
# The old shared shape `\b(?:import|require|from)\b.*?(?:{names})\b` (the name
# anywhere later on an import line) fired on
# `from airflow.providers.openai.hooks.openai import OpenAIHook` and
# `from airflow.providers.pinecone.hooks import PineconeHook` -- airflow-internal
# modules that never import the SDK -- on `from myproj.models.torch import Net`,
# and on JS/TS relative paths such as `from './openai/client'` or
# `require('../sklearn')`. The two families spell "the package" differently, so
# each gets its own builder; every rule uses the same two shapes:
#
# * Python (`_py_package_import`): the module right after `from` / each item
#   after `import` must BE the package, optionally followed by a submodule
#   (`from openai.types import X`). Anchored at a statement start (line start or
#   `;`), so `from airflow.providers import openai` and `from . import openai`
#   are not package imports. The anchor also excludes a doctest
#   `>>> import openai` / `... import openai` line: decided NOT to count it (#4250), as for
#   the general python `import` rule (#2875 C5); pinned by test_doctest_import_policy_4250. Pieces are adjacent-disjoint (`[\w.]+` / `[ \t]` /
#   `,`) and the item list is bounded, so there is no Rule-14 split ambiguity.
# * JS/TS (`_js_package_import`): the module SPECIFIER (the quoted string after
#   `from` / `import` / `require(` / `import(`) must name the package. A relative
#   (`./`, `../`), absolute or alias (`@/`, `~/`) path is never a package, so it
#   never matches.


def _py_package_import(packages: str) -> "re.Pattern[str]":
    return re.compile(
        r"(?:^|;)[ \t]*(?:"
        r"from[ \t]+(?:" + packages + r")(?!\w)[\w.]*[ \t]+import\b"
        r"|import[ \t]+(?:[\w.]+(?:[ \t]+as[ \t]+\w+)?[ \t]*,[ \t]*){0,16}(?:" + packages + r")(?!\w)"
        r")",
        re.M,
    )


def _js_package_import(packages: str) -> "re.Pattern[str]":
    return re.compile(r"\b(?:from|import|require)[ \t]*(?:\([ \t]*)?['\"`](?:" + packages + r")(?=['\"`/])")


# llm_api (#4137): `openai`, `anthropic`, or langchain's per-provider
# `langchain_openai` / `langchain_anthropic` distributions. JS/TS: the official
# `@openai/*` and `@anthropic-ai/*` scopes, or a scoped provider adapter
# `@scope/openai` / `@scope/anthropic` (`@ai-sdk/openai`, `@azure/openai`,
# `@langchain/anthropic`).
_LLM_API_PY_PACKAGES = r"openai|anthropic|langchain_openai|langchain_anthropic"
PY_LLM_API = _py_package_import(_LLM_API_PY_PACKAGES)
_LLM_API_JS_PACKAGES = r"openai|anthropic|@(?:openai|anthropic-ai)/[\w.-]+|@[\w.-]+/(?:openai|anthropic)"
JS_LLM_API = _js_package_import(_LLM_API_JS_PACKAGES)

# llm_orchestrator (#4150): langchain and LlamaIndex. Every langchain
# distribution is the orchestration framework (`langchain_core`,
# `langchain_community`, ...), matching js/ts where the whole `@langchain/*`
# scope always counted; so the per-provider `langchain_openai` /
# `@langchain/openai` count here AND under llm_api. The bounded `_\w{1,64}`
# suffix is followed by `(?!\w)`, so it cannot split ambiguously.
# Agent frameworks that are not named langchain/llama_index count too (#4108): python `langgraph`, `crewai`, `autogen`,
# `haystack`, `semantic_kernel`, `dspy`, `pydantic_ai`, `smolagents`; npm Vercel's AI SDK (`ai`, `@ai-sdk/*`) and `@mastra/*`.
# The bare `ai` is safe only because the specifier must END at the name (or a `/`): `'ai-utils'`, `'./ai'` never match.
PY_LLM_ORCHESTRATOR = _py_package_import(
    r"langchain(?:_\w{1,64})?|llama_index|langgraph|crewai|autogen|haystack|semantic_kernel|dspy|pydantic_ai|smolagents"
)
JS_LLM_ORCHESTRATOR = _js_package_import(r"langchain|llamaindex|ai|@(?:langchain|llamaindex|ai-sdk|mastra)/[\w.-]+")
# llm_vector_store (#4150): Chroma and Pinecone (npm: `@pinecone-database/*`).
PY_LLM_VECTOR_STORE = _py_package_import(r"chromadb|pinecone")
JS_LLM_VECTOR_STORE = _js_package_import(r"chromadb|@pinecone-database/[\w.-]+")
# ml_traditional (#4150, #4252): scikit-learn and the gradient-boosting
# libraries (`xgboost`, `lightgbm`, `catboost`). There is no js/ts equivalent, so
# the javascript/typescript rule is the stated absence (None, #4251): a pattern
# for the literal specifier `'sklearn'` matched nothing real on npm.
PY_ML_TRADITIONAL = _py_package_import(r"sklearn|xgboost|lightgbm|catboost")
# dl_frameworks (#4150, #4252): TensorFlow, PyTorch, Keras and their companion
# distributions (`torchvision`, `torchaudio`, `torchtext`, `tensorflow_hub`,
# `tensorflow_datasets`, `tensorflow_text`), plus Hugging Face `transformers`.
# Each is a top-level package of its own: the `(?!\w)` anchor means `torch` never
# matches `torchvision`, so every companion is named. Generic names (`datasets`,
# `accelerate`, `peft`) are left out: they appear in non-ML code. On npm
# TensorFlow.js ships as the `@tensorflow/*` and `@tensorflow-models/*` scopes and
# Transformers.js as `@huggingface/transformers` / `@xenova/transformers`; the bare
# names are kept so a literal `from 'tensorflow'` still counts.
PY_DL_FRAMEWORKS = _py_package_import(
    r"tensorflow|torch|keras|transformers|torchvision|torchaudio|torchtext"
    r"|tensorflow_hub|tensorflow_datasets|tensorflow_text"
)
JS_DL_FRAMEWORKS = _js_package_import(
    r"tensorflow|torch|keras|transformers|@tensorflow(?:-models)?/[\w.-]+|@(?:huggingface|xenova)/transformers"
)

# hardware_bridge / cryptography (#4238): the last two import-anchored rules had the
# same `\b(?:import|require|from)\b.*?(?:names)\b` shape (library name ANYWHERE on
# an import line) and fired on `from myproj.crypto.utils import X`,
# `from .ssl_helpers import y`, `import { Foo } from './usb/driver'`. They now use the
# same builders as the AI/ML pack. Names are unchanged except the deliberate
# additions noted inline.
# python: `cryptography` and `OpenSSL` are added so `from cryptography import x509` and
# `from OpenSSL import crypto` (which the old rule caught only through the incidental
# `x509` / `crypto` tokens) still count; `socket.io` is
# dropped (not a python module name) and `webgl` kept as before.
# python's serial library is `pyserial`, imported as `serial` (#4108); `bleak` is its bluetooth-LE client.
PY_HARDWARE_BRIDGE = _py_package_import(r"serialport|serial|pyserial|usb|bluetooth|bleak|websocket|printer|webgl")
PY_CRYPTOGRAPHY = _py_package_import(
    r"cryptography|OpenSSL|crypto|bcrypt|x509|tls|ssl|jsonwebtoken|argon2|hashlib|hmac"
)
# js/ts: `node:`-prefixed builtins, `crypto-*` (`crypto-js`) and the `@serialport/*`,
# `@socket.io/*` and `@scope/x509` scoped packages all counted under the old
# anywhere-on-the-line shape, so they are named explicitly.
JS_HARDWARE_BRIDGE = _js_package_import(
    r"serialport|@serialport/[\w.-]+|usb|bluetooth|socket\.io(?:-client)?|@socket\.io/[\w.-]+|websocket|printer"
)
JS_CRYPTOGRAPHY = _js_package_import(
    r"(?:node:)?(?:crypto|tls)|crypto-[\w.-]+|bcrypt|ssl|jsonwebtoken|argon2|x509|@[\w.-]+/x509"
)

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
CALLS_OUT_C_STYLE = re.compile(rf"\b([{ID_START}][{ID_CONTINUE}]*)\s*\(")

# #3359 (contract C1): the C-style pattern for languages whose `@Name(...)` is a
# metadata annotation -- a declaration, never an invocation (java, kotlin, swift,
# dart, groovy, scala). NOT for python/typescript/javascript, where a decorator
# factory `@retry(3)` really is a call to `retry`. A dotted annotation
# (`@javax.annotation.Generated(`) still leaks its last segment, a known gap:
# the lookbehind is fixed-width on purpose (Rule 5). detector.py treats this
# pattern exactly like CALLS_OUT_C_STYLE (qualifier capture included).
CALLS_OUT_C_STYLE_NO_ANNOTATION = re.compile(rf"(?<!@)\b([{ID_START}][{ID_CONTINUE}]*)\s*\(")

# #3644 (contract C3): the C-style pattern for languages that write a type-argument
# list between a callee and its `(` -- C++ `static_cast<int>(`,
# `Object::cast_to<T>(`, `back_inserter<vector<wstring> >(`, TypeScript/C#
# `new Array<T>()`. The list is optional, opens right after the name (no blank,
# so a spaced comparison `a < b` never starts one), nests one level, stays on
# one line, holds no `( ) ; { } = | ! ?` or quote, and ends in `>` then `(`.
# Every quantifier is bounded and the two alternatives start on disjoint
# characters (Rules 1-3). detector.py treats it exactly like CALLS_OUT_C_STYLE.
#
# #6266: a function-pointer type argument is a third element of the list, `function_cast<int (*)(Node &, void *)>(cb)`,
# `reinterpret_cast<void (Foo::*)(int)>(p)`: `(`, a declarator holding `*` or `&`, `)`, then the parameter list.
# It starts on `(`, which the other two alternatives exclude, and its two runs are bounded.
#
# #6266: the list may be empty, `DLList_Reverse<>(&head)` (every template argument deduced, eternity): `<>` then `(`.
# `a <> (b)` is no C++/TypeScript/C# comparison, and the list still opens right after the name.
#
# #6266: a type operator's operand is a fourth element, `de::map<decltype(segments)>(src, fn)`, `f<sizeof(T)>(x)`
# (doomsday): the keyword, then one flat `(...)`. It starts on a letter, as a plain argument character does, but it
# ends only on `)`, which no other element takes, so a run of letters is read one way.
_GENERIC_ARG_CHAR = r"[^<>()\n;{}=|!?\"']"
_GENERIC_FNPTR = r"\([ \t]*[^<>()\n;{}=|!?\"'*&]{0,100}[*&][ \t]*\)[ \t]*\(" + _GENERIC_ARG_CHAR + r"{0,200}\)"
_GENERIC_TYPE_OPERATOR = r"\b(?:decltype|sizeof|alignof|typeof|__typeof__)[ \t]*\(" + _GENERIC_ARG_CHAR + r"{0,200}\)"
CALLS_OUT_C_STYLE_GENERIC = re.compile(
    rf"\b([{ID_START}][{ID_CONTINUE}]*)"
    r"(?:<(?:"
    + _GENERIC_ARG_CHAR
    + r"|<"
    + _GENERIC_ARG_CHAR
    + r"{0,200}>|"
    + _GENERIC_FNPTR
    + r"|"
    + _GENERIC_TYPE_OPERATOR
    + r"){0,200}>[ \t]*)?"
    r"\s*\("
)

# #4124 (contract C3): the generic-aware pattern for the JVM languages (java, kotlin, groovy).
# It adds the C1 `@Name(` annotation guard and accepts an empty list, the Java diamond
# `new ArrayList<>(`. Without it, `new HashMap<K, V>()`, `ArrayDeque<T>()` and
# `register<Copy>("x")` were missed. The list rules are CALLS_OUT_C_STYLE_GENERIC's.
# detector.py treats it exactly like CALLS_OUT_C_STYLE.
CALLS_OUT_C_STYLE_GENERIC_NO_ANNOTATION = re.compile(
    rf"(?<!@)\b([{ID_START}][{ID_CONTINUE}]*)"
    r"(?:<(?:" + _GENERIC_ARG_CHAR + r"|<" + _GENERIC_ARG_CHAR + r"{0,200}>){0,200}>[ \t]*)?"
    r"\s*\("
)

# #6266: Kotlin's form of the #4124 pattern. A call may omit its parentheses when its last argument is a lambda
# (`ev.withKey { sc -> .. }`, `pool.submit { .. }`): the name follows a receiver dot and the `{` follows the name.
# Only the dotted form is read (a bare `name {` is `else {`, `class C {`, `init {`), and not the stdlib
# scope and iteration functions (`x.let { }`, `xs.map { }`, `x.apply { }`): by name they collide with a port's own
# `run()` or `map()`, and the engine cannot resolve a receiver's type. Their parenthesised form `x.let(f)` stays a call.
# Group 1 is the callee (the optional group 2, a zero-width "a dot comes before" mark, sits inside it), so detector.py
# reads it like the C-style family.
_KOTLIN_STDLIB_LAMBDA = "run|with|apply|let|also|takeIf|takeUnless|repeat|times|map|filter|forEach"
CALLS_OUT_KOTLIN = re.compile(
    rf"(?<!@)\b((?P<lambda_ok>(?<=\.)(?!(?:{_KOTLIN_STDLIB_LAMBDA})\b))?[{ID_START}][{ID_CONTINUE}]*)"
    r"(?:<(?:" + _GENERIC_ARG_CHAR + r"|<" + _GENERIC_ARG_CHAR + r"{0,200}>){0,200}>[ \t]*)?"
    r"(?:\s*\(|(?(lambda_ok)[ \t]*\{|(?!)))"
)

# #6454: Dart's form of the C3 generic pattern. A Dart type argument may be nullable
# (`ValueNotifier<String?>(null)`, `Completer<T?>()`), so `?` is allowed inside the list; `:` is
# not (no Dart type-argument list holds one), which keeps a ternary `a<b ? c : d>(e)` out.
# Everything else is CALLS_OUT_C_STYLE_GENERIC_NO_ANNOTATION's, bounds included.
_DART_GENERIC_ARG_CHAR = r"[^<>()\n;{}=|!:\"']"
CALLS_OUT_DART = re.compile(
    rf"(?<!@)\b([{ID_START}][{ID_CONTINUE}]*)"
    r"(?:<(?:" + _DART_GENERIC_ARG_CHAR + r"|<" + _DART_GENERIC_ARG_CHAR + r"{0,200}>\??){0,200}>[ \t]*)?"
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
# #3814: every name class is UAX #31 (a receiver `பெயர்.save` ends in a virama, not `\w`); the
# cheap `(?<=\.)` runs first so the wide class is only tried after a dot.
_RUBY_KEYWORD = (
    r"(?:alias|and|begin|break|case|class|def|defined\?|do|else|elsif|end|ensure|false|for|if|in|module"
    r"|next|nil|not|or|redo|rescue|retry|return|self|super|then|true|undef|unless|until|when|while|yield)"
    r"(?![" + ID_CONTINUE + r"?!])"
)
_RUBY_CALLEE = rf"[{ID_START}][{ID_CONTINUE}]*(?:[?!](?![=~:]))?"
CALLS_OUT_RUBY = re.compile(
    r"(?:(?<=\.)(?<=["
    + ID_CONTINUE
    + r")\]}?!\"'`]\.)|(?<=&\.)(?<=["
    + ID_CONTINUE
    + r")\]}?!\"'`]&\.)|(?<=[ \t\n]\.)|(?<=\A\.)|(?<=::)(?<=["
    + ID_CONTINUE
    + r"]::)(?=[a-z_])"
    r"|(?<![@$.:])\b(?!"
    + _RUBY_KEYWORD
    + r")(?="
    + _RUBY_CALLEE
    + r"[ \t]*\(|["
    + ID_START
    + r"]["
    + ID_CONTINUE
    + r"]*[?!](?![=~:]))"
    r"|^[ \t]*(?!" + _RUBY_KEYWORD + r")(?=[a-z_][" + ID_CONTINUE + r"]*!?[ \t]+"
    r"(?!(?:if|unless|while|until|rescue|and|or|then|do|in)\b)[" + ID_CONTINUE + r":\"'@$\[%]))"
    r"(" + _RUBY_CALLEE + r")",
    re.M,
)

# #6433: Perl calls without parentheses. `name(` alone missed `$obj->method`, `shift`,
# `blessed $x`, `delete $h->{k}` and `plan tests => 4`. Group 1 is the callee, so
# detector.py runs it exactly like CALLS_OUT_C_STYLE (qualifier capture, C5 header
# check). A name is a call when it:
#   - follows `->` (`$o->save`, `$class->SUPER::new`): a method call, parens or not;
#   - is followed by `(` and no sigil precedes it (`$x(` is a variable);
#   - is a unary/list built-in written bare (`shift`, `delete $h->{k}`, `keys %h`),
#     unless it is a hash key (`{shift}`, `shift =>`);
#   - opens a statement, or follows `=`, `(`, `!`, `,`, `&&`, `||` or `return`, with an
#     argument start after blanks (`$ @ \ " '`, a heredoc `<<`, or `word =>`):
#     `blessed $x`, `plan tests => 4`, `my $v = fetch $k;`. Keywords and word
#     operators are excluded.
# A bare word with no `->`, paren or argument (`foo`) is never matched: without a
# symbol table Perl cannot tell a bareword from a call. Quantifiers are bounded or run
# over characters their neighbours cannot start with.
_PERL_NAME = rf"[{ID_START}][{ID_CONTINUE}]*"
_PERL_KEYWORD = (
    r"(?:my|our|local|state|sub|use|no|package|require|return|if|elsif|else|unless|while|until|for|foreach"
    r"|do|eval|and|or|not|xor|x|lt|gt|le|ge|eq|ne|cmp|last|next|redo|goto|when|given|default|continue)"
    rf"(?![{ID_CONTINUE}])"
)
# #6433 slice 6: no-argument and optional-argument built-ins (`time`, `wantarray`, `fork`, `eof FH`); the
# `sub` guard keeps a definition (`sub wait {`) from reading as a call.
_PERL_BUILTIN = (
    r"(?<!sub )(?<!sub\t)"
    r"(?:shift|pop|delete|defined|exists|ref|scalar|lc|uc|lcfirst|ucfirst|length|chomp|chop|chr|ord|int|abs|hex"
    r"|oct|sqrt|log|exp|sin|cos|keys|values|each|caller|undef|rmdir|readlink|chdir|quotemeta|sleep|rand|srand"
    r"|exit|localtime|gmtime|close|readdir|closedir|stat|lstat|umask|fc|lock|select"
    r"|time|times|wait|wantarray|fork|getppid|getlogin|eof|pos|study|fileno|readline|chroot|rewinddir|telldir)"
    rf"(?![{ID_CONTINUE}])(?![ \t]*=>)(?!\}})"
)
# #6433: a block (`first { $_ > 0 } @l`, `bless {}, $c`), a `%hash`, a `qq{..}` string, or an
# upper-case file handle (`print OUT $x`) also opens an argument list.
_PERL_ARG = (
    rf"(?:[$@\\\"']|%[{ID_START}$]|<<[\"'A-Z_~]|{_PERL_NAME}[ \t]*=>|q[qwx]?[{{(\[<]"
    r"|\{[^{}\n]{0,200}\}[ \t]*[@$(,]|[A-Z][A-Z0-9_]*[ \t]+[$\"'@]"
    # #6433: `open FH, ...` (a bareword handle then a comma) and `open my $fh, ...`.
    r"|[A-Z][A-Z0-9_]*[ \t]*,|my[ \t]+[$@%]"
    # #6433 slice 5: a digit-first argument, `plan 4;`, `skip 3, 'why';`, `fetch -1;`.
    r"|-?[0-9])"
)
_PERL_NOT_CALL = rf"(?:map|grep|sort)(?![{ID_CONTINUE}])"
CALLS_OUT_PERL = re.compile(
    r"(?:(?<=->)(?:SUPER::)?"
    rf"|(?<![$@%{ID_CONTINUE}>-])(?={_PERL_NAME}[ \t]*\()"
    rf"|(?<![$@%&{ID_CONTINUE}>:-])(?={_PERL_BUILTIN})"
    rf"|(?<![$@%&{ID_CONTINUE}>:-])(?=(?:print|printf|say)(?![{ID_CONTINUE}])[ \t]+(?:[A-Z][A-Z0-9_]*|\{{[^{{}}\n]{{0,100}}\}})[ \t]+[a-z0-9$\"'@])"
    rf"|(?<![$@%&{ID_CONTINUE}>:-])(?=split(?![{ID_CONTINUE}])[ \t]*/)"
    # #6433: an indirect-object constructor, `new Foo;`, and a qualified command, `Foo::bar $x;`.
    rf"|(?<![$@%&{ID_CONTINUE}>:-])(?=new[ \t]+[{ID_START}][{ID_CONTINUE}:]*[ \t]*[;,)])"
    rf"|(?:^[ \t]*|(?<==[ \t]))(?:{_PERL_NAME}::){{1,6}}(?={_PERL_NAME}[ \t]+{_PERL_ARG})"
    rf"|(?:^[ \t]*|(?<==[ \t])|(?<=\()|(?<=!)|(?<=,[ \t])|(?<=&&[ \t])|(?<=\|\|[ \t])|(?<=return[ \t])"
    # #6433: after a block opener, a statement end, `?`, `.`, a file handle or a `{$fh}` block.
    r"|(?<=[{;?.][ \t])|(?<=[A-Z]{2}[ \t])|(?<=\}[ \t])"
    rf"|(?<![$@%&{ID_CONTINUE}>:-])(?:or|and|xor|not)[ \t]+)"
    rf"(?!{_PERL_KEYWORD})(?!{_PERL_NOT_CALL})(?={_PERL_NAME}[ \t]+{_PERL_ARG}))"
    rf"({_PERL_NAME})",
    re.M,
)

# #3643 (contracts C3, and C3's 2026-09-25 pattern amendment): rust's own calls_out.
# Group 1 is the callee, so detector.py treats it like CALLS_OUT_C_STYLE (qualifier,
# C5 header check). Three shapes the C-style pattern gets wrong:
#   - a macro is a call to its name: `format!(`, `vec![`, `quote!{` (never
#     `macro_rules! name {`, whose `!` is not followed by the delimiter);
#   - a turbofish sits between the name and `(`: `collect::<Vec<_>>()`,
#     `query::<&A>()` -- two nesting levels, one line, no `( ) { }` or quote inside;
#   - a tuple-struct PATTERN is not a call: `Data::Struct(x) =>`, `Ok(t) =>`,
#     `Some(1) | None =>`, `if let Some(x) =`, `let Wrapper(inner) = w;`. The name is
#     capitalised (a variant or tuple struct; a guard's `if valid(x) =>` is a real
#     call and stays), its balanced one-line argument list is followed -- after any
#     closing `)`/`]` of an enclosing pattern, `Err(X::Gone(e)) =>` -- by `=>`, a
#     pattern `|`, a binding `=` (never `==`, `=>`'s own `=` or `||`/`|=`), or a
#     match guard's `if` (an expression never puts `if` after a call: no postfix `if`).
#     Only the `|` may sit on the next line, as a multi-line arm writes it
#     (`Type::Array(_)\n| Type::Tuple(_) =>`).
# Every quantifier is bounded or runs over characters its neighbours cannot start
# with (Rules 1-3); the pattern check runs only at a capitalised word start.
# #3814: the pattern's name continues through combining marks (UAX #31).
_RUST_GENERIC_CHAR = r"[^<>(){}\n\"]"
_RUST_TURBOFISH = (
    r"::<(?:" + _RUST_GENERIC_CHAR + r"|<(?:" + _RUST_GENERIC_CHAR + r"|<" + _RUST_GENERIC_CHAR + r"{0,200}>){0,200}>)"
    r"{1,200}>"
)
_RUST_BALANCED_ARGS = r"\((?:[^()\n]|\((?:[^()\n]|\([^()\n]{0,200}\)){0,200}\)){0,200}\)"
_RUST_PATTERN_TAIL = r"(?:[ \t]{0,8}[)\]]){0,8}(?:[ \t]{0,8}(?:=>|=(?![=>])|if\b)|\s{0,16}\|(?![|=]))"
CALLS_OUT_RUST = re.compile(
    r"\b(?![A-Z][" + ID_CONTINUE + r"]{0,63}[ \t]{0,8}" + _RUST_BALANCED_ARGS + _RUST_PATTERN_TAIL + r")"
    rf"([{ID_START}][{ID_CONTINUE}]*)"
    r"(?:![ \t]{0,8}[(\[{]|(?:" + _RUST_TURBOFISH + r")?\s*\()"
)

# #3645 (contract C3): Go writes a conversion to a pointer or qualified type in
# parentheses -- `(*gcBgMarkWorkerNode)(nodep)`, `(*uintptr)(unsafe.Pointer(p))`,
# `(*unsafe.Pointer)(p)` -- and a conversion is a call. `\b(name)\s*\(` cannot see
# the `)` between the type and its `(`. The first lookahead captures the callee (group 1,
# so detector.py treats this like CALLS_OUT_C_STYLE; `pkg` becomes the qualifier)
# either after a `(`/`(*`/`(pkg.` prefix or at the match start, and only where a
# word starts (`(?<!\w)`: never re-scanned from inside one). The prefix form
# needs `name)(`, the plain form `name(` -- and leaves its `(` unconsumed, so in
# `return (*m)(p)` the conversion's `(` is still there to open a prefix. The prefix
# also takes `**T` and an array type, `(*[2]Timeval)(p)`. A `(` that closes a call
# (`h(next)(w)`, a call of the returned func) is no prefix: the `(` may not follow a
# name, `)` or `]`. Every quantifier is bounded or runs over disjoint characters
# (Rules 1-3).
_GO_CONVERSION_PREFIX = (
    r"(?<![\w)\]])\(\*{0,2}(?:\[[^\]\n]{0,64}\])?(?:[" + ID_START + r"][" + ID_CONTINUE + r"]{0,63}\.)?"
)
# #5634: a generic instantiation call, `F[*T](x)`, `Map[int, string](xs)`, `New[pkg.T]()`, sits between
# the name and `(` as `[type args]`. `fns[i](x)` (an index, then a call of the element) is the same
# shape, so the bracket must READ as type arguments: a pointer, slice, map, func or predeclared type
# first, a `,` between two, or a qualified `pkg.T`. One level of nested `[...]`; bounded, disjoint.
_GO_TYPE_ARG_BODY = r"[^\[\]\n]{0,64}(?:\[[^\[\]\n]{0,64}\][^\[\]\n]{0,64}){0,2}"
_GO_PREDECLARED_TYPE = (
    r"(?:u?int(?:8|16|32|64)?|uintptr|float(?:32|64)|complex(?:64|128)|string|bool|byte|rune|error|any|comparable)\b"
)
_GO_TYPE_ARGS = (
    r"\[(?:[*]|\[\]|map(?=\[)|func\b|chan\b|"
    + _GO_PREDECLARED_TYPE
    + r"|[^\[\]\n,]{1,64},|["
    + ID_START
    + r"]["
    + ID_CONTINUE
    + r"]{0,63}\.["
    + ID_START
    + r"])"
    + _GO_TYPE_ARG_BODY
    + r"\]"
)
CALLS_OUT_GO = re.compile(
    r"(?=(?:" + _GO_CONVERSION_PREFIX + r")?(?<!\w)([" + ID_START + r"][" + ID_CONTINUE + r"]*))"
    r"(?:"
    + _GO_CONVERSION_PREFIX
    + r"["
    + ID_START
    + r"]["
    + ID_CONTINUE
    + r"]{0,63}\)\(|\b["
    + ID_START
    + r"]["
    + ID_CONTINUE
    + r"]*(?=(?:"
    + _GO_TYPE_ARGS
    + r")?\s*\())"
)

# The invocation patterns detector.py treats as the C-style family: group 1 is
# the callee, the receiver chain before it is its qualifier (#3329), and a
# capture on a nested `func_start` header is a declaration (#3360).
QUALIFIED_CALLS_OUT_PATTERNS = (
    CALLS_OUT_C_STYLE,
    CALLS_OUT_C_STYLE_NO_ANNOTATION,
    CALLS_OUT_C_STYLE_GENERIC,
    CALLS_OUT_C_STYLE_GENERIC_NO_ANNOTATION,
    CALLS_OUT_DART,
    CALLS_OUT_KOTLIN,
    CALLS_OUT_RUBY,
    CALLS_OUT_PERL,
    CALLS_OUT_RUST,
    CALLS_OUT_GO,
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
# #3814: the letters and digits are UAX #31's (`probe-नाम`), the punctuation stays.
# #5640: `/ . : ~ $ % & ^` too, the set scheme's func_start already names with (`bytevector-copy/range` was read
# as the call `bytevector-copy`).
CALLS_OUT_LISP_FAMILY = re.compile(r"\(\s*([" + ID_START + r"][" + ID_CONTINUE + r"!?*<>=+/.:~$%&^-]*)")

# Command-position family (tcl, powershell, livecode): the callee is the first
# word on a statement line. Charset covers tcl `ns::proc` interior colons and
# PS `Verb-Noun`; a leading-`::` fully-qualified tcl call is a known recall gap
# (the first character must be a letter/underscore for precision).
# Consumers MUST pair this with a `calls_out_ignore` set of the language's
# statement keywords, since those also appear in command position.
# #3814: UAX #31 letters, digits and marks (`Get-नाम`). The trailing `\b` became what it meant
# here -- the name ends on a name character and no name character follows -- in the same class,
# so a name is never cut after a combining mark.
CALLS_OUT_COMMAND_POSITION = re.compile(
    r"(?m)^[ \t]*([" + ID_START + r"][" + ID_CONTINUE + r":-]*)(?<=[" + ID_CONTINUE + r"])(?![" + ID_CONTINUE + r"])"
)

# #4171: dead_code in a `;`-terminated C-family language -- a commented-out STATEMENT, not only a keyword-led line:
# a call, an assignment, or a declaration, ending in `;` (prose rarely does). A capitalised type needs an
# initializer (`// Load data;` stays prose); a primitive or inferred type may stand alone (`// int x;`).
# Each alternative is bounded by the line (no `\n`), so the pattern stays linear. Placed after a comment marker.
COMMENTED_STATEMENT = (
    r"(?:[A-Za-z_$][\w$]*(?:(?:\.|->|::)[A-Za-z_$][\w$]*)*\([^\n;]*\)"
    r"|[A-Za-z_$][\w$]*(?:(?:\.|->)[A-Za-z_$][\w$]*|\[[^\n\]]*\])*[ \t]*[-+*/%&|^]?=(?!=)[^\n;]+"
    r"|[A-Z][\w$]*(?:<[^\n>;]*>)?(?:\[\])*[ \t]+[a-z_$][\w$]*[ \t]*=(?!=)[^\n;]+"
    r"|(?:int|long|short|byte|char|boolean|bool|float|double|var|let|const|auto|string|unsigned)"
    r"(?:\[\])*[ \t]+[a-z_$][\w$]*[ \t]*(?:=(?!=)[^\n;]+)?"
    r")[ \t]*;"
)
COMMENTED_STATEMENT_C_FAMILY = r"(?<![/*])(?://|/\*)[ \t]*" + COMMENTED_STATEMENT  # (not a `///` doc line)


# ------------------------------------------------------------------------------
# #5461: C/C++ function-defining macros (`CCMD(map) {`, `DEFINE_ACTION_FUNCTION(AActor, A_Look) {`,
# `TEST(Suite, Name) {`, odamex `FUNC(LS_Door_Open) {`). Pattern SOURCE (an alternative of `func_start`; the macro's name lands in group 2 and the detector's `lastindex` read
# picks it up). Name rule: the only argument; of several, the second (`Class, name` /
# `Type, name` / `Suite, Name`), except the `C_MACRO_FIRST_ARG_NAMES` macros, which name the first. Anchors: an ALL-CAPS macro of 3+ chars at column 0 whose
# argument list holds plain identifiers (no nested call, no operators) and is followed by `{`.
# Column 0, not "after indentation": an indented `MACRO(x) {` sits inside a body, where it is a
# statement macro (godot `OPCODE(OPCODE_JUMP) {` = `case`, `OPCODE_WHILE(true) {` = `while`).
# Excluded: control-flow shouts, `BEGIN`/`END`, and class-like macros (`DE_PIMPL`, `*NAMESPACE*`) and `*MODULE` binders (`NB_MODULE(name, m)`: `m` is a variable).
# The `#define` lookup (odamex FUNC) lives in `detector._slice_by_braces`: a macro whose in-file define is not a signature is dropped.
# ------------------------------------------------------------------------------
# The identifier is not always the second argument. These macros name the FIRST (`DEFINE_PROPERTY(name, Type, Class)`,
# `DEFINE_MAP_OPTION(name, true)`): the exact names only, so `DEFINE_CLASS_PROPERTY_PREFIX(prefix, name, Type, Class)`
# and `DEFINE_PROPERTYKEY` keep the general rule (`;`-terminated, so the latter never reaches the `{`).
# `DEFINE_CLASS_PROPERTY*` is exempt from the class-like exclusion below: it defines a property, not a class.
C_MACRO_FIRST_ARG_NAMES = r"DEFINE_(?:(?:CLASS|INFO)_)?PROPERTY|DEFINE_MAP_OPTION"


def _c_macro_func_start(name_open: str) -> str:
    return (
        r"^(?!(?!DEFINE_CLASS_PROPERTY)[A-Z0-9_]{0,40}(?:PIMPL|NAMESPACE|CLASS|STRUCT|ENUM|TEMPLATE|UNION|MODULE)|"
        r"(?:IF|FOR|WHILE|SWITCH|ELSE|DO|BEGIN|END|ASSERT|CASE|RETURN)\b)"
        rf"(?:(?:{C_MACRO_FIRST_ARG_NAMES})[ \t]*\([ \t]*"
        rf"|(?!(?:{C_MACRO_FIRST_ARG_NAMES})[ \t]*\()[A-Z][A-Z0-9_]{{2,}}[ \t]*\([ \t]*"
        rf"(?:[{ID_START}][{ID_CONTINUE}]{{0,60}}[ \t]*,[ \t]*)?)"
        rf"{name_open}[{ID_START}][{ID_CONTINUE}]{{0,100}})[ \t]*"
        r"(?:,[^()\n;{}]{0,200})?\)[ \t\n]{0,200}\{"
    )


# The capturing form is the SECOND alternative of `func_start` (so the generic branch keeps group 1); `_GUARD` is
# the same shape without a group, for a rule whose generic branch would otherwise name the macro itself (C++).
C_MACRO_FUNC_START_SOURCE = _c_macro_func_start("(")
C_MACRO_FUNC_START_GUARD = _c_macro_func_start("(?:")
