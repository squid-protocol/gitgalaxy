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
GLOBAL_PLANNED_DEBT = re.compile(f"{_SPACED_PLANNED}|{_DENSE_PLANNED}", re.I)


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
GLOBAL_FRAGILE_DEBT = re.compile(f"{_SPACED_FRAGILE}|{_DENSE_FRAGILE}", re.I)


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
