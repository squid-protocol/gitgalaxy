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

"""
language_standards.py
Phase 2 & 3: The Lexical Registry & Syntax Dictionaries.

This file contains the compiled regular expressions, mechanical delimiters, 
and language-specific rules used to physically slice, parse, and identify 
source code across the repository.
"""

# ------------------------------------------------------------------------------
# 1. STRUCTURAL SIGNATURE CONFIGURATION (Language Identification & Disambiguation)
# Consumed by: language_lens.py
# ------------------------------------------------------------------------------
LENS_CONFIG = {
    "COLLISION_FREQUENCIES": {".inc", ".h", ".py", ".cshtml", ".c", ".y", ".m"},
    "PROSE_ANCHORS": {
        "README",
        "LICENSE",
        "LICENCE",
        "CONTRIBUTING",
        "CHANGELOG",
        "AUTHORS",
        "INSTALL",
        "NOTICE",
        "COPYING",
        "TODO",
        "FAQ",
        "NOTES",
        "CREDITS",
        "HISTORY",
        "MANIFEST",
        "FILES",
        "FILES2",
        "ACKNOWLEDGEMENTS",
        "AGREEMENT",
        "CONTRIBUTORS",
        "HACKING",
        "HACKERS",
        "AUTHOR",
        "CHANGES",
        "NEWS",
        "RELEASE_NOTES",
        "RELEASENOTES",
        "UPGRADE",
        "UPGRADING",
        "VERSION",
        "BUGS",
        "FEATURES",
        "ARCHITECTURE",
        "DESIGN",
        "GUIDE",
        "USAGE",
        "TUTORIAL",
        "DOCS",
        "CODE_OF_CONDUCT",
        "SECURITY",
        "SUPPORT",
        "COPYRIGHT",
        "PATENTS",
        "LEGAL",
        "THANKS",
        "OWNERS",
        "CODEOWNERS",
        "MAINTAINERS",
        "POSTAMBLE",
        "README_BUFRLIB",
    },
    "DISQUALIFIERS": {
        "single_line_only": r"(?:^\s*using\s+namespace\b|^\s*public\s+(?:class|interface)\b|<\?php)",
        "column_sensitive": r"(?:^\s*(?:import|export)\s+\{|<html\b|<\?php|^\s*namespace\s+\w+)",
        "c_style_comment": r"(?:<\?php|^\s*IDENTIFICATION\s*DIVISION\.)",
        "recursive_c_style": r"(?:<\?php|<html\b|^\s*IDENTIFICATION\s*DIVISION\.)",
        "multi_style_dash": r"(?:^\s*public\s+class\b|<\?php|<html\b)",
        "embedded_syntax": r"^\s*IDENTIFICATION\s*DIVISION\.",
    },
    "HANDSHAKE_REGISTRY": [
        {
            "trigger": r"^[ \t]*<script\b",
            "end": r"</script>",
            "target": "javascript",
            "pair": None,
        },
        {
            "trigger": r"^[ \t]*<style\b",
            "end": r"</style>",
            "target": "css",
            "pair": None,
        },
        {
            "trigger": r"asm!\s*\(|__asm__",
            "end": r"\)",
            "target": "assembly",
            "pair": ("(", ")"),
        },
    ],
    "THRESHOLDS": {
        "INTENSITY_FLOOR": 0.78,
        "FLOOR_TIER_4": 0.92,
        "PROSE_CONFIDENCE": 0.95,
        "MIN_OUTLIER_MARGIN": 1.15,
        "PROSE_BASELINE_SIGNAL": 3.0,
        "HANDSHAKE_LOOKAHEAD_LIMIT": 50000,
        "ECOSYSTEM_DOMINANCE_MIN": 0.70,
        "TIER_4_MIN_LINES": 100,
        "TIER_4_OUTLIER_MARGIN": 1.3,
    },
}

# ------------------------------------------------------------------------------
# 2. PRISM CONFIGURATION (Structural Refraction & String Shielding)
# Consumed by: prism.py
# ------------------------------------------------------------------------------
PRISM_CONFIG = {
    "SHIELD_PATTERN": r'((?<!\\)"(?:\\.|[^"\\])*"|(?<!\\)\'(?:\\.|[^\'\\])*\'|(?<!\\)`(?:\\.|[^`\\])*`)',
    "PYTHON_DOC_PATTERN": r'(?m)^\s*(?:"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')',
    "PHP_HEREDOC_PATTERN": r'<<<[ \t]*([\'"]?)([a-zA-Z_]\w*)\1[ \t]*\r?\n[\s\S]*?\n[ \t]*\2;?',
    "PHP_MULTILINE_STRING": r'(?<!\\)"(?:\\.|[^"\\])*\n(?:\\.|[^"\\])*"|(?<!\\)\'(?:\\.|[^\'\\])*\n(?:\\.|[^\'\\])*\'',
    "POSITIONAL_ANCHORS": {"*", "C", "c", "/", "!"},
    "THRESHOLDS": {"NESTED_PEEL_LIMIT": 500},
}


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

# ------------------------------------------------------------------------------
# 4. LANGUAGE DEFINITIONS (The Structural Signature Matrix)
# Consumed by: detector.py, language_lens.py, prism.py
# ------------------------------------------------------------------------------
LANGUAGE_DEFINITIONS = {
    "python": {
        "_meta": {
            "target_version": "Python 3.14",
            "last_updated": "2026-03-11",
            "blueprint_version": "6.30",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard modern suffixes, legacy formats, typed stubs, Cython, and build-tooling dialects.
        "extensions": [
            ".py",
            ".py3",
            ".py2",
            ".pyw",
            ".pyi",
            ".pyx",
            ".pxd",
            ".pxi",
            ".pyz",
            ".pyzw",
            ".bzl",
            ".gyp",
            ".gypi",
            ".vpython",
            ".vpython3",
            ".rpy",
            ".smk",
        ],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: Extensionless build/config scripts and tooling configs that are secretly pure code.
        "exact_matches": [
            "setup.py",
            "SConstruct",
            "SConscript",
            "BUCK",
            "BUILD",
            "wscript",
            "Snakefile",
        ],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions, package manifests, and lockfiles to resolve ambiguous files.
        "discriminators": [
            ".py",
            "requirements.txt",
            "pyproject.toml",
            "Pipfile",
            "Pipfile.lock",
            "tox.ini",
            "poetry.lock",
            "setup.cfg",
        ],
        "internal_discriminator": re.compile(
            r"^[ \t]*(?:import|from)\s+(?:subprocess|multiprocessing|threading|requests|pandas|numpy|django|flask|fastapi|sqlalchemy|boto3|httpx|matplotlib|scipy|tensorflow|torch)\b",
            re.M,
        ),
        # EXECUTION SIGNATURES: Interpreters found on Line 1.
        "shebangs": ["python", "python3", "python2", "pypy", "pypy3", "jython"],
        # UPGRADED: Maps to Family 3 (Pure Hash)
        # Rationale: Uses '#' for line-level literature; multi-line literature
        # (docstrings) is handled by the Section 2.3.C.3 Heuristic Pass.
        "lexical_family": "line_exclusive",
        "rules": {
            # =====================================================================
            # [ CRITICAL ROADMAP: JSONC/JSON5 LEXICAL DELIMITERS & THE RE.COMPILE TRAP ]
            # 1. THE LEXICAL MAPPING: JSON with comments (.jsonc, .json5) strictly
            #    uses C-style comments (// and /* */), NOT Python/Ruby hashes (#).
            #    This is why JSON must map to the 'std_c' lexical_family, not 'pure_hash' or 'inert'.
            # 2. THE RE.COMPILE TRAP: Every rule here MUST be wrapped in re.compile().
            #    If passed as raw strings, the engine's physics loop will crash with
            #    "'str' object has no attribute 'pattern'" during the Commented / Non-Executable Text extraction.
            # =====================================================================
            # JSON has no concept of a "column 1" or line-start-only comment anchor.
            "_line_anchor": None,
            # JSONC/JSON5 inline comments use standard C-style slashes.
            "_inline_comment": re.compile(r"//"),
            # JSONC/JSON5 multi-line blocks use standard C-style delimiters.
            "_block_start": re.compile(r"/\*"),
            "_block_end": re.compile(r"\*/"),
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # 1. branch (Control Flow / Branching)
            # Includes match/case (3.10+) and logical short-circuits. EXCLUDES exceptions.
            "branch": re.compile(r"\b(if|elif|else|for|while|with|try|finally|match|case|and|or)\b"),
            # 2. args (Parameters / Coupling)
            # Signatures for def/lambda. Bounded generics [^\]]* and params [^)]*.
            "args": re.compile(
                r"(?:async[ \t]+)?def\s+\w+(?:\[[^\]]*\])?\s*\([^)]*\)|\blambda\s+[^:]+:",
                re.M,
            ),
            # 3. linear (Sequential Boundaries)
            # Structural boundaries. EXCLUDES: _private (encapsulation) and Final (freeze_hits).
            "structural_boundaries": re.compile(
                r"\b(def|class|return|import|from|as|pass|continue|break|await|assert|del|global|nonlocal|type)\b"
            ),
            # 4. func_start (Executable Logic Anchors)
            # Anchors executable logic. Steps safely over decorators.
            "func_start": re.compile(
                r"^[ \t]*(?:@[\w.]+(?:\([^)]*\))?[ \t]+){0,5}(?:async[ \t]+)?def\s+\w+(?:\[[^\]]*\])?\s*\(",
                re.M,
            ),
            # 5. class_start (Object / Entity Declarations)
            "class_start": re.compile(
                r"^[ \t]*(?:@[\w.]+(?:\([^)]*\))?[ \t]+){0,5}class\s+([a-zA-Z_]\w*)(?:\[[^\]]*\])?(?:\s*\(\s*([a-zA-Z0-9_., \t]*)\s*\))?",
                re.M,
            ),
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            # 6. safety (Defensive Programming / Validation)
            "safety": re.compile(
                r"\b(try|except(?:\*)?|finally|assert|isinstance|issubclass|hasattr|getattr|dataclass|BaseModel|Field|TypeGuard|override)\b"
            ),
            # 7. safety_neg (Safety Bypasses / Unchecked Types)
            # Swallowed errors, wildcard imports, and Any bypasses.
            "safety_bypasses": re.compile(
                r"\bpass\b[ \t]*$|except\s*[:(]|except\s+(?:Base)?Exception|from\s+[\w.]+\s+import\s+\*|#\s*type:\s*ignore|\b(Any|cast)\b|=\s*\[\s*\]|=[ \t]*\{\s*\}",
                re.M,
            ),
            # 8. danger (High-Risk Execution / System Calls)
            # Process killers and un-sanitized deserialization. EXCLUDES TODO/print.
            "high_risk_execution": re.compile(
                r"\b(eval|exec|subprocess\.(?:call|Popen|run)|os\.system|pickle\.loads?|yaml\.unsafe_load|shell=True)\b"
            ),
            # 9. io (I/O & Network Boundaries)
            "io": re.compile(
                r"\b(open|requests|httpx|aiohttp|boto3|os\.|sys\.|pathlib|socket|sqlalchemy|psycopg2?|asyncpg)\b"
            ),
            # 10. api (Public Surface Area)
            # Implicit public defaults (undercased root definitions) + explicit __all__.
            "api": re.compile(
                r"^[ \t]*(?:async[ \t]+)?def\s+[^_]\w+|^[ \t]*class\s+[^_]\w+|^__all__[ \t]*=|@(?:app|router|blueprint)\.(?:get|post|put|delete)",
                re.M,
            ),
            # 11. flux (State Mutation)
            # State mutation. Includes Walrus operator and collection mutators.
            "state_mutation": re.compile(
                r"\bglobal\b|\bnonlocal\b|\b(?:self|cls)\.\w+[ \t]*=|:=|(?:\.\w+)?\.(?:append|extend|update|pop|remove|insert|clear)\s*\("
            ),
            # 12. dead_code (Commented Logic / Deprecated Trails)
            "dead_code": re.compile(r"#[ \t]*(?:def|class|import|if|for|while|try|return)\b"),
            # 13. doc (Structured Documentation)
            "doc": re.compile(
                r'"""|\'\'\'|:param|:return|:raises|:type|\b(?:Args|Returns|Yields|Raises|Attributes):\b'
            ),
            # 14. test (Testing & Assertions)
            "test": re.compile(r"\b(unittest|pytest|TestCase|fixture|patch)\b|def[ \t]+test_|\bassert\b|\bMock\b"),
            # --- PHASE 3: SPECIALIZED SENSORS (Architecture & Hidden Complexity) ---
            # 15. concurrency (Asynchronous Execution)
            "concurrency": re.compile(
                r"\b(async|await|asyncio|threading|multiprocessing|ThreadPoolExecutor|TaskGroup|gather|create_task)\b"
            ),
            # 16. ui_framework (UI / View Components)
            "ui_framework": re.compile(
                r"\b(streamlit|django\.shortcuts|flask\.render_template|gradio|dash|fasthtml|jinja2|render)\b"
            ),
            # 17. closures (Closures / Anonymous Functions)
            "closures": re.compile(r"\blambda\b"),
            # 18. globals (Global / Shared State)
            "globals": re.compile(r"\b(os\.environ|sys\.argv|sys\.path|globals\(\)|locals\(\))\b"),
            # 19. decorators (Decorators / Annotations)
            "decorators": re.compile(r"^[ \t]*@[\w.]+", re.M),
            # 20. generics (Generics / Type Parameters)
            "generics": re.compile(
                r"\b(List|Dict|Set|Tuple|Optional|Union|TypeVar|Generic|Any|Callable|Mapping)\b\[[^\]]*\]|\b(list|dict|set|tuple|type)\[[^\]]*\]|->"
            ),
            # 21. comprehensions (Iterators / Comprehensions)
            "comprehensions": re.compile(r"\.(?:map|filter|reduce|flatMap|some|every|find|forEach|groupBy)\s*\("),
            # Expanded to include LLM orchestration tools for the Agentic Shield
            "scientific": re.compile(
                r"\b(?:import|require|from)\b.*?(?:tensorflow|torch|keras|numpy|pandas|scipy|sklearn|matplotlib|opencv|cv2|langchain|openai|anthropic|llama_index|chromadb|pinecone)\b"
            ),
            "hardware_bridge": re.compile(
                r"\b(?:import|require|from)\b.*?(?:serialport|usb|bluetooth|socket\.io|websocket|printer|webgl)\b"
            ),
            "cryptography": re.compile(
                r"\b(?:import|require|from)\b.*?(?:crypto|bcrypt|x509|tls|ssl|jsonwebtoken|argon2)\b"
            ),
            # 23. heat_triggers (Metaprogramming & Reflection)
            # Metaprogramming and class-level binding.
            "reflection_metaprogramming": re.compile(
                r"__(?:getattr|setattr|del|call|new|metaclass|dict|dir|import)__|@(?:staticmethod|classmethod|property)|\b(?:getattr|setattr|inspect\.)\b"
            ),
            # 24. import (Dependency Inclusions)
            "import": re.compile(
                r"\b(?:from\s+[a-zA-Z0-9_.]+\s+import\b|import\s+[a-zA-Z0-9_., \t]+|\b__import__\s*\(|\bimportlib\.import_module\s*\()",
                re.M,
            ),
            "_dependency_capture": re.compile(
                r"\bfrom\s+([a-zA-Z0-9_.]+)\s+import\b|"
                r"\bimport\s+([a-zA-Z0-9_.]+(?:[ \t]*,[ \t]*[a-zA-Z0-9_.]+)*)|"
                r"\b(?:__import__|importlib\.import_module)\s*\(\s*['\"]([a-zA-Z0-9_.]+)['\"]",
                re.M,
            ),
            "_named_token_capture": re.compile(r"^[ \t]*from\s+[\w.]+\s+import\s+([^({\n]+)", re.M),
            # 25. ownership (Authorship Metadata)
            "ownership": re.compile(r"(?:__author__[ \t]*=|Author:|Created by:)\s*(.*)", re.I),
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            # 26. planned_debt (Annotated Debt / TODOs)
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            # 29. spec_exposure (Spec / Audit Traceability)
            "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]", re.I),
            # 30. tabs_vs_spaces (Formatting Inconsistencies) 
            "tabs_vs_spaces": None,
            # 31. ssr_boundaries (Server-Side Rendering)
            "ssr_boundaries": re.compile(
                r"\b(render_template|HttpResponse|JSONResponse|TemplateResponse|WSGIApplication|ASGIApplication)\b"
            ),
            # 32. events (Event Emitters / Pub-Sub)
            "events": re.compile(
                r"\b(Signal|receiver|post_save|pre_save|asyncio\.Event|EventDispatcher|emit|send|blinker)\b"
            ),
            # 33. dependency_injection (Dependency Injection / IoC)
            "dependency_injection": re.compile(
                r"\b(Depends|Provide|Inject|Container|dependency_injector|fastapi\.Depends)\b"
            ),
            # 34. macros
            "macros": None,  # Python lacks a C-style preprocessor.
            # 35. pointers (Pointer Arithmetic / Memory Addressing)
            "pointers": re.compile(r"\b(ctypes\.POINTER|c_void_p|byref)\b"),
            # 36. memory_alloc (Manual Memory Management)
            "memory_alloc": None,  # Managed by GC.
            # 37. inline_asm
            "inline_asm": None,
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # 38. telemetry (Structured Logging / Telemetry)
            "telemetry": re.compile(
                r"\b(logging|logger|structlog|sentry_sdk|datadog|loguru)\.(?:info|error|warn|warning|debug|trace|log|exception|critical)\b"
            ),
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
            "debug_prints": re.compile(r"\b(print|input)\s*\("),
            # # 40. explicit_casts (Explicit Type Casting)
            "explicit_casts": re.compile(r"\b(int|str|float|list|dict|set|tuple|bool|bytes|cast)\b\s*\("),
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
            "panics_and_aborts": re.compile(r"\b(raise|quit|exit|sys\.exit|abort)\b"),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
            "thread_sleeps": re.compile(r"\b(time\.sleep|asyncio\.sleep|Thread\.join)\b"),
            # 43. bitwise_ops (Bitwise Operations)
            "bitwise_ops": re.compile(r"<<|>>|\^|~"),
            # 44. sync_locks (Resource Management & Stability)
            "sync_locks": re.compile(r"\b(Lock|RLock|Semaphore|BoundedSemaphore|Event|Condition|Barrier)\b"),
            # 45. immutability_locks (Immutability Constraints)
            "immutability_locks": re.compile(r"\b(Final|frozenset|mappingproxy|immutable)\b"),
            # 46. cleanup (Resource Cleanup / Teardown)
            "cleanup": re.compile(r"\b(close|__exit__|del|shutdown|cleanup)\b\s*\("),
            # 47. encapsulation (Access Modifiers / Encapsulation)
            # Captures protected/private members via underscore convention.
            "encapsulation": re.compile(r"\b_[a-zA-Z_]\w*\b"),
            # 48. listeners (Event Listeners / Observers)
            "listeners": re.compile(r"\b(on_event|add_listener|subscribe|callback|handler)\b"),
            # 49. test_skip (Bypassed Tests / Ignored Specs)
            "test_skip": re.compile(r"\b(pytest\.mark\.skip|unittest\.skip|mock\.|MagicMock)\b"),
            # --- NEW: ADVANCED ALGORITHMIC SENSORS ---
            "lazy_evaluation": re.compile(r"\b(yield|yield\s+from|Generator|AsyncGenerator|Iterator|AsyncIterator)\b"),
            "vectorized_math": re.compile(
                r"\b(einsum|matmul|tensordot|vdot|bmm)\b|\.dot\s*\(|(?<=[a-zA-Z0-9_\]\)])\s*@\s*(?=[a-zA-Z0-9_\[\(])"
            ),
            # --- PHASE 3: HYBRID DOMAIN SENSORS (Python Specifics) ---
            "serialization_parsing": re.compile(
                r"\b(pickle\.loads?|pickle\.Unpickler|marshal\.loads?|ast\.literal_eval)\b"
            ),
            "regex_execution": re.compile(r"\b(re\.compile|re\.search|re\.match|re\.sub|re\.findall|re\.split)\b"),
            "time_date_logic": re.compile(r"\b(datetime\.datetime|timedelta|time\.sleep|time\.time|calendar)\b"),
            "ipc_rpc_bridges": re.compile(r"\b(multiprocessing|subprocess|xmlrpc|socketserver)\b"),
            # --- PHASE 4: APPSEC & AI SENSORS (Zero-Trust Pipelines) ---
            "memory_scraping": re.compile(r"['\"]/proc/['\"]\s*\+\s*(?:str\([^)]*\)|f?['\"]\{[^}]*\})|/proc/\w+/mem"),
            "exfiltration_camouflage": re.compile(
                r"\b(requests\.post|urllib\.request|httpx\.post)\s*\([^)]*(?:checkmarx|telemetry|metrics|audit|log)\b",
                re.I,
            ),
        },
    },
    "javascript": {
        "_meta": {
            "target_version": "ES2025 / React 19 / Node 22+",
            "last_updated": "2026-02-18",
            "blueprint_version": "v5.0",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard modern suffixes, legacy server-side formats, UI extensions, and embedded scripts.
        "extensions": [
            ".js",
            ".mjs",
            ".cjs",
            ".jsx",
            ".es6",
            ".es",
            ".pac",
            ".sjs",
            ".ssjs",
            ".xsjs",
            ".xsjslib",
            ".jsm",
            "._js",
            ".bones",
            ".gs",
        ],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: Extensionless build/config scripts and tooling configs that are secretly pure code.
        "exact_matches": ["Jakefile"],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions, package manifests, and lockfiles to resolve ambiguous files.
        "discriminators": [
            ".js",
            "package.json",
            "package-lock.json",
            "yarn.lock",
            "pnpm-lock.yaml",
            "bower.json",
            ".eslintrc",
            ".prettierrc",
        ],
        # EXECUTION SIGNATURES: Interpreters found on Line 1.
        "shebangs": ["node", "nodejs", "deno", "bun", "zx", "phantomjs", "casperjs"],
        # UPGRADED: Maps to Family 1 (Standard C)
        # Rationale: Uses '//' for line-level literature; multi-line literature
        # (/* */) is handled by the Section 2.3.C.3 Heuristic Pass.
        "lexical_family": "standard_block",
        "rules": {
            # --- LEXICAL DELIMITER CONTROLS ---
            # Standard C-family line comment token (Includes JSDoc // style)
            "_line_anchor": re.compile(r"//"),
            # Inline comments follow the standard '//' delimiter.
            "_inline_comment": re.compile(r"//"),
            # Block comment start: /* (Standard non-recursive delimiter)
            "_block_start": re.compile(r"/\*"),
            # Block comment end: */
            "_block_end": re.compile(r"\*/"),
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # 1. branch (Control Flow / Branching)
            # Decisions and logical jumps. EXCLUDES throw (bailout_hits).
            "branch": re.compile(
                r"\b(if|else|switch|case|default|for|while|do|catch|finally|continue|break|try)\b|&&|\|\||\?|\?\?"
            ),
            # 2. args (Parameters / Coupling)
            # Parameter blocks. Bounded to prevent ReDoS on massive positional/destructured sets.
            "args": re.compile(
                # =====================================================================
                # [ THE GHOST ARGS SHIELD (JAVASCRIPT) ]
                # JS class methods (e.g., `TargetFunc(config) {`) lack the `function` keyword.
                # Without an anchor, the engine hallucinated standard invocations as definitions.
                # FIX 1 (Invocation Shield): Injected `(?=[ \t\n]*\{)` at the end of the class
                # method branch, demanding structural proof that the signature opens a logic block.
                # FIX 2 (Control Flow Shield): `while (i < 10) {` structurally mimics a method.
                # Injected `(?!(?:if|for|while|switch|catch|return)\b)` to prevent reserve words
                # from being mapped as method names.
                # =====================================================================
                r"(?:"
                r"\b(?:async[ \t\n]+)?function[ \t\n]*\w*[ \t\n]*\([^)]*\)|"
                r"(?:\([^)]*\)|[a-zA-Z_$][\w$]*)[ \t\n]*=>|"
                r"^[ \t]*(?:static[ \t\n]+)?(?:async[ \t\n]+)?(?:get[ \t\n]+|set[ \t\n]+)?(?!(?:if|for|while|switch|catch|return)\b)(?:#?[a-zA-Z_$][\w$]*)[ \t\n]*\([^)]*\)(?=[ \t\n]*\{)"
                r")",
                re.M,
            ),
            # 3. linear (Sequential Boundaries)
            # Structural declaration boundaries. EXCLUDES: Access modifiers (encapsulation) and const (freeze_hits).
            "structural_boundaries": re.compile(r"\b(let|var|import|export|return|class|extends|super|await|delete)\b|=>"),
            # 4. func_start (Executable Logic Anchors)
            # Uses positive lookaheads (?=) to stop the match exactly at the identifier name.
            # Captures standard functions, namespace assignments (foo.bar = function),
            # object literal methods (foo: function), and ES6 methods.
            "func_start": re.compile(
                r"(?:"
                r"\b(?:async\s+)?function\s*\*?\s+[a-zA-Z_$][\w$]*(?=\s*\()|"
                # =====================================================================
                # [ THE VERTICAL ASSIGNMENT SHIELD ] (Hard-learned lesson from Pathological Fuzzer)
                # PURPOSE: JavaScript developers frequently format complex asynchronous
                # fat-arrow functions across multiple lines (e.g., `export const \n foo \n = \n async () =>`).
                # THE FIX: We replaced horizontal-only spaces `[ \t]*` with `[ \t\n]*`
                # around the `=` and `:` assignment operators, as well as the `=>` arrow.
                # This allows the lookahead to safely cross vertical line breaks without
                # resorting to an unbounded `\s*` which causes ReDoS.
                # =====================================================================
                r"\b[a-zA-Z_$][\w$]*(?=[ \t\n]*=[ \t\n]*(?:async\s*)?(?:function(?:\s*\*)?\b|\([^)]*\)[ \t\n]*=>|[a-zA-Z_$][\w$]*[ \t\n]*=>))|"
                r"^[ \t]*[a-zA-Z_$][\w$]*(?=[ \t\n]*:[ \t\n]*(?:async\s*)?(?:function(?:\s*\*)?\b|\([^)]*\)[ \t\n]*=>|[a-zA-Z_$][\w$]*[ \t\n]*=>))|"
                r"^[ \t]*(?:static[ \t\n]+)?(?:async[ \t\n]+)?(?:get\s+|set\s+)?(?!(?:if|for|while|switch|catch|return|throw|new|typeof|jQuery|function)\b|\$)#?[a-zA-Z_$][\w$]*(?=\s*\()"
                r")",
                re.M,
            ),
            # 5. class_start (Object / Entity Declarations)
            "class_start": re.compile(
                r"^[ \t]*(?:export[ \t]+)?(?:default[ \t]+)?class\s+([a-zA-Z_$][\w$]*)(?:\s+extends\s+([a-zA-Z_$][\w$]*))?",
                re.M,
            ),
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            # 6. safety (Defensive Programming / Validation)
            "safety": re.compile(
                r"\b(try|catch|finally|typeof|instanceof|Array\.isArray|Number\.(?:isFinite|isNaN)|Object\.hasOwn)\b|===|!==|\?\?|\?\."
            ),
            # 7. safety_neg (Safety Bypasses / Unchecked Types)
            # Loose equality and bypasses.
            "safety_bypasses": re.compile(r"==(?!=)|!=(?!=)|\b(with|void)\b|eslint-disable|@ts-nocheck"),
            # 8. danger (High-Risk Execution / System Calls)
            # Catastrophic vulnerabilities. EXCLUDES console.log (print_hits) and TODO (debt).
            "high_risk_execution": re.compile(
                r"\b(eval|document\.write|innerHTML|outerHTML|dangerouslySetInnerHTML|debugger|alert|process\.exit)\b"
            ),
            # 9. io (I/O & Network Boundaries)
            "io": re.compile(
                r"\b(fetch|axios|http|https|fs|path|database|sql|localStorage|sessionStorage|indexedDB|document\.cookie|XMLHttpRequest|child_process)\b"
            ),
            # 10. api (Public Surface Area)
            # Exposure surface. Explicit exports + implicit architectural defaults.
            "api": re.compile(r"\b(export|module\.exports|exports\.)\b|@(Controller|Resolver|Get|Post|Put|Delete)\b"),
            # 11. flux (State Mutation)
            # Mutation of state. EXCLUDES const (freeze_hits).
            "state_mutation": re.compile(
                r"\b(let|var|this\.|setState|mut|push|pop|shift|unshift|splice|sort|reverse|\.current[ \t]*=|\.set\(|\.delete\(|\.add\()\b"
            ),
            # 12. dead_code (Commented Logic / Deprecated Trails)
            "dead_code": re.compile(r"//[ \t]*(?:if|for|while|function|class|return|var|const|let|import)\b"),
            # 13. doc (Structured Documentation)
            "doc": re.compile(r"/\*\*|@param|@return|@throws|@deprecated|@typedef|@type|@template"),
            # 14. test (Testing & Assertions)
            "test": re.compile(
                r"\b(describe|expect|assert|beforeEach|afterEach|jest|mocha|vitest|cy\.)\b|\b(?:it|test)\s*\("
            ),
            # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
            # 15. concurrency (Asynchronous Execution)
            "concurrency": re.compile(
                r"\b(async|await|Promise|requestAnimationFrame|setImmediate|setTimeout|setInterval|queueMicrotask|Worker|postMessage)\b|\.then\(|\.catch\("
            ),
            # 16. ui_framework (UI / View Components)
            "ui_framework": re.compile(
                r'<[A-Z]\w+|className=|use(?:State|Effect|Context|Reducer|Ref|Memo|Callback|Transition)|props\.|this\.state|document\.(?:getElementById|querySelector|addEventListener)|["\']use\s+(?:client|server)["\']'
            ),
            # 17. closures (Closures / Anonymous Functions)
            "closures": re.compile(r"=>[ \t]*\{|\(\)[ \t]*=>|function\s*\([^)]*\)[ \t]*\{"),
            # 18. globals (Global / Shared State)
            "globals": re.compile(r"\b(window\.|global\.|process\.env|document\.|navigator\.|self\.|globalThis\.)\b"),
            # 19. decorators (Decorators / Annotations)
            "decorators": re.compile(r"@\w+"),
            # 20. generics (Generics / Type Parameters)
            # Simulated/JSDoc generics in JS.
            "generics": re.compile(r"@template\s+\w+|/\*\*\s*@type\s*(?:\{|<\w+)"),
            # 21. comprehensions (Iterators / Comprehensions)
            "comprehensions": re.compile(r"\.(?:map|filter|reduce|flatMap|some|every|find|forEach|groupBy)\s*\("),
            # Expanded to include LLM orchestration tools for the Agentic Shield
            "scientific": re.compile(
                r"\b(?:import|require|from)\b.*?(?:tensorflow|torch|keras|numpy|pandas|scipy|sklearn|matplotlib|opencv|cv2|langchain|openai|anthropic|llama_index|chromadb|pinecone)\b"
            ),
            "hardware_bridge": re.compile(
                r"\b(?:import|require|from)\b.*?(?:serialport|usb|bluetooth|socket\.io|websocket|printer|webgl)\b"
            ),
            "cryptography": re.compile(
                r"\b(?:import|require|from)\b.*?(?:crypto|bcrypt|x509|tls|ssl|jsonwebtoken|argon2)\b"
            ),
            # 23. heat_triggers (Metaprogramming & Reflection)
            "reflection_metaprogramming": re.compile(
                r"\b(arguments\.|prototype|__proto__|Object\.assign|Reflect|Proxy|Object\.defineProperty|\.bind\(|\.call\(|\.apply\()\b"
            ),
            # 24. import (Dependency Inclusions)
            "import": re.compile(
                r"\b(?:import|export)\b[^;]*?\bfrom\b|\brequire\s*\(|\bimport\s*\(",
                re.M,
            ),
            "_dependency_capture": re.compile(
                # =====================================================================
                # [ FUTURE LLM CONTEXT: THE DYNAMIC EXECUTION SHIFT (JAVASCRIPT) ]
                # PURPOSE: Extracts external dependencies for the Network Graph and Supply Chain Firewall.
                #
                # HISTORICAL BUG: Originally, the `import` regex was anchored to the start of the
                # line `^[ \t]*`. While this perfectly prevented the engine from hallucinating
                # commented-out imports, it completely blinded the firewall to dynamic/inline execution.
                # If an attacker tucked an import inside a function (e.g., `const payload = require('malware')`
                # or `await import('trojan')`), it bypassed the sensors entirely.
                #
                # THE FIX: The `^` anchor has been stripped across both the counter and the capture regex.
                # We now rely on the `\b` word boundary to find the keywords anywhere in the file.
                # (Note: The engine's optical comment-stripper runs BEFORE this regex, naturally preventing
                # the commented-out hallucination issue without needing strict line anchors).
                #
                # [ THE VERTICAL DESTRUCTURING SHIELD ]
                # We enforce `[ \t\n]*` near the `from` and inside the `require()` parentheses to safely
                # leap across vertical multi-line destructured imports (e.g., `import \n { \n Component \n } \n from`).
                # =====================================================================
                r"(?:import|export)\b[^;]*?\bfrom\s*['\"]([^'\"]+)['\"]|\b(?:require|import)\s*\(\s*['\"]([^'\"]+)['\"]",
                re.M,
            ),
            "_named_token_capture": re.compile(r"(?:import|export)\s+\{([^}]+)\}", re.M),
            # 25. ownership (Authorship Metadata)
            "ownership": re.compile(r"(?:@author|Created by)\s+(.*)", re.I),
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            # 26. planned_debt (Annotated Debt / TODOs)
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            # 29. spec_exposure (Spec / Audit Traceability)
            "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]", re.I),
            # 30. tabs_vs_spaces (Formatting Inconsistencies) 
            "tabs_vs_spaces": None,
            # 31. ssr_boundaries (Server-Side Rendering)
            "ssr_boundaries": re.compile(
                r"\b(getServerSideProps|getStaticProps|getInitialProps|renderToString|hydrateRoot)\b"
            ),
            # 32. events (Event Emitters / Pub-Sub)
            "events": re.compile(r"\b(emit|on|once|off|dispatchEvent|EventEmitter|EventTarget)\b"),
            # 33. dependency_injection (Dependency Injection / IoC)
            "dependency_injection": re.compile(r"\b(Inject|Injectable|Container|resolve|register|inversify)\b"),
            # 34. macros
            "macros": None,
            # 35. pointers
            "pointers": None,
            # 36. memory_alloc
            "memory_alloc": re.compile(r"\bnew\s+[A-Z]\w*"),
            # 37. inline_asm
            "inline_asm": None,
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # 38. telemetry (Structured Logging / Telemetry)
            "telemetry": re.compile(
                r"\b(logger|winston|pino|morgan|datadog|prometheus|newrelic|sentry)\.(?:info|error|warn|debug|trace|log)\b"
            ),
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
            "debug_prints": re.compile(r"\bconsole\.(?:log|warn|error|dir|trace|info|table|time)\b"),
            # # 40. explicit_casts (Explicit Type Casting)
            "explicit_casts": re.compile(r"\b(Number|String|Boolean|BigInt|Symbol|Array\.from)\b\s*\("),
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
            "panics_and_aborts": re.compile(r"\b(throw|abort|process\.exit)\b"),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
            "thread_sleeps": re.compile(r"\b(sleep|delay|setTimeout|setInterval|Atomics\.wait)\b"),
            # 43. bitwise_ops (Bitwise Operations)
            "bitwise_ops": re.compile(r"<<|>>>?|\^|~"),
            # 44. sync_locks (Resource Management & Stability)
            "sync_locks": re.compile(
                r"\b(mutex|lock|synchronized|Semaphore|Atomics\.lock|Atomics\.wait)\b",
                re.I,
            ),
            # 45. immutability_locks (Immutability Constraints)
            "immutability_locks": re.compile(r"\b(const|readonly|final|Object\.freeze|Object\.seal)\b"),
            # 46. cleanup (Resource Cleanup / Teardown)
            "cleanup": re.compile(r"\b(dispose|close|destroy|clearTimeout|clearInterval|removeEventListener|delete)\b"),
            # 47. encapsulation (Access Modifiers / Encapsulation)
            # JS private fields and keywords.
            "encapsulation": re.compile(r"\b(private|protected|internal|#)\b"),
            # 48. listeners (Event Listeners / Observers)
            "listeners": re.compile(r"\b(on|addEventListener|subscribe|watch|effect)\b"),
            # 49. test_skip (Bypassed Tests / Ignored Specs)
            "test_skip": re.compile(r"\b(test\.skip|it\.skip|describe\.skip|xit|xdescribe|mock|stub)\b"),
            # --- NEW: ADVANCED ALGORITHMIC SENSORS ---
            "lazy_evaluation": re.compile(r"\b(yield|yield\s*\*|function\s*\*)\b"),
            "vectorized_math": re.compile(r"\b(matmul|dot|cross|multiply)\s*\("),
            # --- PHASE 3: HYBRID DOMAIN SENSORS (JS/TS Specifics) ---
            "serialization_parsing": re.compile(r"\b(JSON\.parse|JSON\.stringify)\b"),
            "regex_execution": re.compile(r"\bnew\s+RegExp\b|\.(match|replace|search|split)\s*\("),
            "time_date_logic": re.compile(
                r"\b(Date\.now|new\s+Date|setTimeout|setInterval|clearTimeout|clearInterval|performance\.now)\b"
            ),
            "ipc_rpc_bridges": re.compile(
                r"\b(postMessage|Worker|MessageChannel|child_process|worker_threads|cluster)\b"
            ),
            # --- PHASE 4: APPSEC & AI SENSORS (Zero-Trust Pipelines) ---
            "rce_funnel": re.compile(
                r"child_process\.(?:spawn|exec|execSync)\s*\(\s*['\"](?:python|bash|sh|bun|node)\b"
            ),
            "exfiltration_camouflage": re.compile(
                r"\b(fetch|axios\.post|https\.request)\s*\([^)]*(?:checkmarx|telemetry|metrics|audit|log)\b",
                re.I,
            ),
        },
    },
    "typescript": {
        "_meta": {
            "target_version": "TypeScript 6.0 / ES2026",
            "last_updated": "2026-03-12",
            "blueprint_version": "v6.3.1",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard modern suffixes, JSX variants, and ambient declaration boundaries.
        "extensions": [
            ".ts",
            ".tsx",
            ".mts",
            ".cts",
            ".d.ts",
            ".d.mts",
            ".d.cts",  # Ambient declarations
        ],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: Extensionless build/config scripts and tooling configs that are secretly pure code.
        "exact_matches": [],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions, package manifests, and lockfiles to resolve ambiguous files.
        "discriminators": [
            ".ts",
            "tsconfig.json",
            "tslint.json",
            "package.json",
            "yarn.lock",
            "pnpm-lock.yaml",
            "deno.json",
        ],
        # EXECUTION SIGNATURES: Interpreters found on Line 1.
        "shebangs": ["ts-node", "deno", "bun", "tsx"],
        # UPGRADED: Maps to Family 1 (Standard C)
        # Rationale: Uses '//' for line-level literature; multi-line literature
        # (/* */) is handled by the Section 2.3.C.3 Heuristic Pass.
        "lexical_family": "standard_block",
        "rules": {
            # --- LEXICAL DELIMITER CONTROLS ---
            # Standard C-family line comment token (Includes TSDoc /// references)
            "_line_anchor": re.compile(r"//"),
            # Inline comments follow the standard '//' delimiter.
            "_inline_comment": re.compile(r"//"),
            # Block comment start: /* (Standard non-recursive delimiter)
            "_block_start": re.compile(r"/\*"),
            # Block comment end: */
            "_block_end": re.compile(r"\*/"),
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # 1. branch (Control Flow / Branching)
            # EXCLUDES: Exceptions (throw). Includes control flow and logical short-circuits.
            "branch": re.compile(
                r"\b(if|else|switch|case|default|for|while|do|catch|finally|continue|break|try)\b|&&|\|\||\?|\?\?"
            ),
            # 2. args (Parameters / Coupling)
            # CRITICAL FIX: Added negative lookahead for control flow, and `[^=;{]*` to support TypeScript return types.
            "args": re.compile(
                r"function\s+\w*(?:<[^>]*>)?\s*\([^)]*\)|\([^)]*\)[^=;{]*=>|[a-zA-Z_$][\w$]*[ \t]*=>|^[ \t]*(?:(?:public|private|protected|static|override|abstract)[ \t]+){0,3}(?:async[ \t]+)?(?:get\s+|set[ \t]+)?(?!(?:if|for|while|switch|catch)\b)[a-zA-Z_$][\w$]*\s*\([^)]*\)",
                re.M,
            ),
            # 3. linear (Sequential Boundaries)
            # Structural boundaries. EXCLUDES: Access modifiers (public/private) and Immutability (const).
            "structural_boundaries": re.compile(
                r"\b(var|return|class|interface|type|enum|import|export|await|satisfies|using|namespace|module|implements|extends|declare)\b|=>"
            ),
            # 4. func_start (Executable Logic Anchors)
            # Captures standard functions, assignments, object properties, and class methods.
            # Safely steps over TypeScript Generics <T> and explicit return types in the lookaheads.
            "func_start": re.compile(
                r"(?:"
                # =====================================================================
                # [ THE FLOATING GENERIC SHIELD ] (Hard-learned lesson from Pathological Fuzzer)
                # PURPOSE: In TypeScript, a function name and its generic type `<T>`
                # can be separated by a vertical newline (e.g., `function TargetFunc \n <T>`).
                # THE FIX: Injected `\s*` immediately before the generic step-over `(?:<[^>]*>)?`
                # across all branches. This explicitly permits vertical spacing between
                # the isolated function name and the generic parameters.
                # Note: We also migrated the JS Vertical Assignment fixes here (`[ \t\n]*`).
                # =====================================================================
                r"\b(?:async\s+)?function\s*\*?\s+[a-zA-Z_$][\w$]*(?=\s*(?:<[^>]*>)?\s*\()|"
                r"\b[a-zA-Z_$][\w$]*(?=[ \t\n]*=[ \t\n]*(?:async\s*)?(?:<[^>]*>\s*)?(?:function(?:\s*\*)?\b|\([^)]*\)[^=;{]*=>|[a-zA-Z_$][\w$]*[ \t\n]*=>))|"
                r"^[ \t]*[a-zA-Z_$][\w$]*(?=[ \t\n]*:[ \t\n]*(?:async\s*)?(?:<[^>]*>\s*)?(?:function(?:\s*\*)?\b|\([^)]*\)[^=;{]*=>|[a-zA-Z_$][\w$]*[ \t\n]*=>))|"
                r"^[ \t]*(?:(?:public|private|protected|static|override|abstract|readonly)[ \t\n]+){0,4}(?:async[ \t\n]+)?(?:get\s+|set\s+)?(?!(?:class|interface|type|enum|if|for|while|switch|catch|return|throw|new|typeof|jQuery|function)\b|\$)#?[a-zA-Z_$][\w$]*(?=\s*(?:<[^>]*>)?\s*\()"
                r")",
                re.M,
            ),
            # 5. class_start (Object / Entity Declarations)
            # =====================================================================
            # [ THE VERTICAL MODIFIER SHIELD (TYPESCRIPT) ]
            # TypeScript allows modifiers like `export`, `default`, and `abstract`
            # to appear in various orders and across multiple lines.
            # FIX: Grouped the modifiers into a flexible, bounded set `(?:(?:export|default|abstract|declare)[ \t\n]+){0,4}`.
            # Upgraded all internal spaces to `[ \t\n]+` to seamlessly leap over vertical gaps.
            # =====================================================================
            "class_start": re.compile(
                r"^[ \t]*(?:(?:export|default|abstract|declare)[ \t\n]+){0,4}(?:class|enum|interface)[ \t\n]+([a-zA-Z_$][\w$]*)(?:[ \t\n]+(?:extends|implements)[ \t\n]+([a-zA-Z_$][\w_$, \t\n]*))?",
                re.M,
            ),
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            # 6. safety (Defensive Programming / Validation)
            "safety": re.compile(
                r"\b(try|catch|finally|satisfies|unknown|never|void|Object\.freeze|z\.(?:string|object|parse)|v\.(?:string|parse))\b|\?\?|\?\.|\b(?:is|asserts)\s+\w+\b"
            ),
            # 7. safety_neg (Safety Bypasses / Unchecked Types)
            # Force unwrapping, any, and linter bypasses.
            "safety_bypasses": re.compile(
                r"\b(any)\b|as\s+any|!\s*[;,\n)\]\.]|!\.|@ts-ignore|@ts-expect-error|@ts-nocheck|eslint-disable|as\s+unknown\s+as|<any>"
            ),
            # 8. danger (High-Risk Execution / System Calls)
            # Process killers and catastrophic vulnerabilities. EXCLUDES TODO (debt) and console.log (print).
            "high_risk_execution": re.compile(
                r"\b(eval|document\.write|innerHTML|outerHTML|dangerouslySetInnerHTML|debugger|alert|process\.exit)\b"
            ),
            # 9. io (I/O & Network Boundaries)
            "io": re.compile(
                r"\b(fetch|axios|http|https|fs|path|database|sql|localStorage|sessionStorage|indexedDB|document\.cookie|XMLHttpRequest|child_process|fs/promises)\b"
            ),
            # 10. api (Public Surface Area)
            # Captures explicit exports and public visibility.
            "api": re.compile(
                r"\b(export|public|module\.exports|exports\.)\b|@(Controller|Resolver|Get|Post|Put|Delete)\b"
            ),
            # 11. flux (State Mutation)
            # Mutation of state. EXCLUDES const (freeze_hits).
            "state_mutation": re.compile(
                r"\b(let|var|this\.|setState|push|pop|shift|unshift|splice|sort|reverse|\.current[ \t]*=|\.set\(|\.delete\(|\.add\()\b"
            ),
            # 12. dead_code (Commented Logic / Deprecated Trails)
            "dead_code": re.compile(r"//[ \t]*(?:if|for|while|function|class|return|export|import)\b"),
            # 13. doc (Structured Documentation)
            "doc": re.compile(r"/\*\*|@param|@return|@throws|@deprecated|@typedef|@type|@template|@callback"),
            # 14. test (Testing & Assertions)
            # CRITICAL FIX: Negative lookbehind (?<!\.) prevents matching 'regex.test()' as an assertion.
            "test": re.compile(
                r"\b(?:describe|expect|beforeEach|afterEach|jest|vitest|playwright)\s*\(|(?<!\.)\b(?:it|test|assert)\s*\("
            ),
            # --- PHASE 3: SPECIALIZED SENSORS (Architecture & Hidden Complexity) ---
            # 15. concurrency (Asynchronous Execution)
            "concurrency": re.compile(
                r"\b(async|await|Promise|requestAnimationFrame|setImmediate|setTimeout|setInterval|Worker|postMessage|Observable|Subject|Subscription)\b"
            ),
            # 16. ui_framework (UI / View Components)
            "ui_framework": re.compile(
                r'<[A-Z]\w+|className=|use(?:State|Effect|Context|Reducer|Ref|Memo|Callback|Transition|Id)|props\.|this\.state|@Component|@Injectable|document\.(?:getElementById|querySelector)|["\']use\s+(?:client|server)["\']'
            ),
            # 17. closures (Closures / Anonymous Functions)
            "closures": re.compile(r"=>[ \t]*\{|\(\)[ \t]*=>|function\s*\([^)]*\)[ \t]*\{"),
            # 18. globals (Global / Shared State)
            "globals": re.compile(r"\b(window\.|global\.|process\.env|document\.|navigator\.|self\.|globalThis\.)\b"),
            # 19. decorators (Decorators / Annotations)
            "decorators": re.compile(r"@\w+(?:\([^)]*\))?"),
            # 20. generics (Generics / Type Parameters)
            "generics": re.compile(
                r"<\s*[A-Z][^>]*>|\b(?:keyof|infer|extends|Omit|Pick|Partial|Record|Required|Awaited|ReturnType|Parameters|NonNullable)\b"
            ),
            # 21. comprehensions (Iterators / Comprehensions)
            "comprehensions": re.compile(r"\.(?:map|filter|reduce|flatMap|some|every|find|forEach|groupBy)\s*\("),
            # 22. scientific (Numerical / Compute Libraries)
            "scientific": re.compile(r"\b(Math\.|tf\.|THREE\.|d3\.|gl-matrix|random)\b"),
            # 23. heat_triggers (Metaprogramming & Reflection)
            "reflection_metaprogramming": re.compile(
                r"\b(arguments\.|prototype|__proto__|Object\.assign|Reflect|Proxy|Object\.defineProperty|\.bind\(|\.call\(|\.apply\()\b"
            ),
            # 24. import (Dependency Inclusions)
            "import": re.compile(
                r"\b(?:import(?:\s+type)?|export(?:\s+type)?)\b[^;]*?\bfrom\b|\brequire\s*\(|\bimport\s*\(",
                re.M,
            ),
            "_dependency_capture": re.compile(
                # =====================================================================
                # [ FUTURE LLM CONTEXT: THE DYNAMIC EXECUTION SHIFT (TYPESCRIPT) ]
                # PURPOSE: Extracts external dependencies for the Network Graph and Supply Chain Firewall.
                #
                # HISTORICAL BUG: Originally, this regex was anchored to the start of the
                # line `^[ \t]*`. While this perfectly prevented the engine from hallucinating
                # commented-out imports (`// import { x }`), it completely blinded the firewall
                # to dynamic/inline execution. If an attacker tucked an import inside a function
                # (e.g., `const payload = require('malware')` or `await import('trojan')`),
                # it sailed right past the sensors.
                #
                # THE FIX: The `^` anchor has been stripped. We now rely on the `\b` word
                # boundary to find the keywords anywhere in the file. (Note: The engine's
                # optical comment-stripper runs BEFORE this regex, naturally preventing the
                # commented-out hallucination issue without needing strict line anchors).
                #
                # [ THE VERTICAL DESTRUCTURING SHIELD ]
                # We retain `[ \t\n]+` to safely leap across massive vertical multi-line
                # destructured imports: `import type \n { \n ASTNode \n } \n from`
                # =====================================================================
                r"\b(?:import(?:[ \t\n]+type)?|export(?:[ \t\n]+type)?)\b[^;]*?\bfrom[ \t\n]*['\"]([^'\"]+)['\"]|\b(?:require|import)[ \t\n]*\([ \t\n]*['\"]([^'\"]+)['\"]",
                re.M,
            ),
            "_named_token_capture": re.compile(
                r"(?:import(?:[ \t\n]+type)?|export(?:[ \t\n]+type)?)\s+\{([^}]+)\}",
                re.M,
            ),
            # 25. ownership (Authorship Metadata)
            "ownership": re.compile(r"(?:@author|Created by)\s+(.*)", re.I),
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            # 26. planned_debt (Annotated Debt / TODOs)
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            # 29. spec_exposure (Spec / Audit Traceability)
            "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]", re.I),
            # 30. tabs_vs_spaces (Formatting Inconsistencies) 
            "tabs_vs_spaces": None,
            # 31. ssr_boundaries (Server-Side Rendering)
            "ssr_boundaries": re.compile(
                r"\b(getServerSideProps|getStaticProps|generateStaticParams|LoaderFunction|ActionFunction)\b"
            ),
            # 32. events (Event Emitters / Pub-Sub)
            "events": re.compile(r"\b(emit|on|once|off|dispatchEvent|EventEmitter|EventTarget)\b"),
            # 33. dependency_injection (Dependency Injection / IoC)
            "dependency_injection": re.compile(
                r"\b(Inject|Injectable|Container|resolve|register|tsyringe|inversify)\b"
            ),
            # 34. macros
            "macros": None,  # TypeScript uses transformer plugins/pre-processors, not standard inline macros.
            # 35. pointers
            "pointers": None,  # Managed memory environment.
            # 36. memory_alloc
            "memory_alloc": re.compile(r"\bnew\s+[A-Z]\w*"),
            # 37. inline_asm
            "inline_asm": None,
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # 38. telemetry (Structured Logging / Telemetry)
            "telemetry": re.compile(
                r"\b(logger|winston|pino|morgan|datadog|prometheus|newrelic|sentry)\.(?:info|error|warn|debug|trace|log)\b"
            ),
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs)
            "debug_prints": re.compile(r"\bconsole\.(?:log|warn|error|dir|trace|info|table|time)\b"),
            # # 40. explicit_casts (Explicit Type Casting)
            "explicit_casts": re.compile(r"\bas\s+[A-Z]\w*|<\s*[A-Z]\w*\s*>\s*[a-zA-Z_]"),
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
            "panics_and_aborts": re.compile(r"\b(throw|fatalError|abort|process\.exit)\b"),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
            "thread_sleeps": re.compile(r"\b(sleep|delay|setTimeout|setInterval|Atomics\.wait)\b"),
            # 43. bitwise_ops (Bitwise Operations)
            "bitwise_ops": re.compile(r"<<|>>|\^|~"),
            # 44. sync_locks (Resource Management & Stability)
            "sync_locks": re.compile(
                r"\b(mutex|lock|synchronized|Semaphore|Atomics\.lock|Atomics\.wait)\b",
                re.I,
            ),
            # 45. immutability_locks (Immutability Constraints)
            "immutability_locks": re.compile(r"\b(const|readonly|final|Object\.freeze|Object\.seal)\b"),
            # 46. cleanup (Resource Cleanup / Teardown)
            "cleanup": re.compile(r"\b(dispose|close|destroy|clearTimeout|clearInterval|removeEventListener|delete)\b"),
            # 47. encapsulation (Access Modifiers / Encapsulation)
            "encapsulation": re.compile(r"\b(private|protected|internal|#)\b"),
            # 48. listeners (Event Listeners / Observers)
            "listeners": re.compile(r"\b(on|addEventListener|subscribe|watch|effect)\b"),
            # 49. test_skip (Bypassed Tests / Ignored Specs)
            "test_skip": re.compile(r"\b(test\.skip|it\.skip|describe\.skip|xit|xdescribe|mock|stub)\b"),
            # --- NEW: ADVANCED ALGORITHMIC SENSORS ---
            "lazy_evaluation": re.compile(
                r"\b(yield|yield\s*\*|function\s*\*|Generator|AsyncGenerator|Iterable|AsyncIterable)\b"
            ),
            "vectorized_math": re.compile(r"\b(matmul|dot|cross|multiply)\s*\("),
            # --- PHASE 3: HYBRID DOMAIN SENSORS (JS/TS Specifics) ---
            "serialization_parsing": re.compile(r"\b(JSON\.parse|JSON\.stringify)\b"),
            "regex_execution": re.compile(r"\bnew\s+RegExp\b|\.(match|replace|search|split)\s*\("),
            "time_date_logic": re.compile(
                r"\b(Date\.now|new\s+Date|setTimeout|setInterval|clearTimeout|clearInterval|performance\.now)\b"
            ),
            "ipc_rpc_bridges": re.compile(
                r"\b(postMessage|Worker|MessageChannel|child_process|worker_threads|cluster)\b"
            ),
            # --- PHASE 4: APPSEC & AI SENSORS (Zero-Trust Pipelines) ---
            "rce_funnel": re.compile(
                r"child_process\.(?:spawn|exec|execSync)\s*\(\s*['\"](?:python|bash|sh|bun|node)\b"
            ),
            "exfiltration_camouflage": re.compile(
                r"\b(fetch|axios\.post|https\.request)\s*\([^)]*(?:checkmarx|telemetry|metrics|audit|log)\b",
                re.I,
            ),
        },
    },
    "java": {
        "_meta": {
            "target_version": "Java 25 (Project Loom, Panama, Amber) / Spring Boot 3.4+",
            "last_updated": "2026-02-18",
            "blueprint_version": "v5.0",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard modern suffixes, server-side templates, and embedded scripting formats.
        "extensions": [".java", ".jav", ".jsp", ".jspf", ".jspx", ".jws", ".bsh"],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: Extensionless build/config scripts and tooling configs that are secretly pure code.
        "exact_matches": [],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: Sibling extensions, package manifests, and lockfiles to resolve ambiguous files.
        "discriminators": [
            ".java",
            "pom.xml",
            "build.gradle",
            "build.gradle.kts",
            "settings.gradle",
            "build.xml",
            "mvnw",
            "gradlew",
            ".classpath",
            ".project",
        ],
        # EXECUTION SIGNATURES: Interpreters found on Line 1.
        "shebangs": ["java", "jshell"],
        # UPGRADED: Maps to Family 1 (Standard C)
        # Rationale: Uses '//' for line-level literature; multi-line literature
        # (/* */) is handled by the Section 2.3.C.3 Heuristic Pass.
        "lexical_family": "standard_block",
        "rules": {
            # --- LEXICAL DELIMITER CONTROLS ---
            # Standard C-family line comment token (Includes Javadoc /**)
            "_line_anchor": re.compile(r"//"),
            # Inline comments follow the standard '//' delimiter.
            "_inline_comment": re.compile(r"//"),
            # Block comment start: /* (Standard non-recursive delimiter)
            "_block_start": re.compile(r"/\*"),
            # Block comment end: */
            "_block_end": re.compile(r"\*/"),
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # 1. branch (Control Flow / Branching)
            # Includes modern switch expressions (yield) and pattern guards (when).
            # EXCLUDES: Exceptions (throw) - moved to bailout_hits.
            "branch": re.compile(
                r"\b(if|else|switch|case|default|for|while|do|catch|finally|continue|break|yield|try|when)\b|\?|:"
            ),
            # 2. args (Parameters / Coupling)
            # Captures method/constructor params and lambdas. Bounded to prevent ReDoS.
            "args": re.compile(
                # =====================================================================
                # [ THE GHOST ARGS SHIELD (JAVA) ]
                # Same architectural fix as C#. Demands structural proof to separate
                # definitions from invocations.
                # Branch 1: Standard Methods MUST have a return type.
                # Branch 2: Constructors MUST be anchored to `{` or `throws`.
                # Branch 3: Standard lambdas and method references `::`.
                # =====================================================================
                r"(?:"
                # 1. Standard Methods
                r"^[ \t]*(?:@[\w.]+(?:\([^)]*\))?[ \t\n]*){0,5}(?:(?:public|protected|private|static|final|abstract|synchronized|native|default|strictfp|<[^>]*>)[ \t\n]+){0,5}(?:[\w<>\[\]?]+[ \t\n]+)\w+[ \t\n]*\([^)]*\)|"
                # 2. Constructors
                r"^[ \t]*(?:@[\w.]+(?:\([^)]*\))?[ \t\n]*){0,5}(?:(?:public|protected|private|static)[ \t\n]+)?[A-Z]\w*[ \t\n]*\([^)]*\)[ \t\n]*(?:throws[ \t\n]+[\w., \t\n]+)?[{]|"
                # 3. Lambdas & Method Refs
                r"(?:\([^)]*\)|[a-zA-Z_$][\w_$]*)[ \t\n]*->|::"
                r")",
                re.M,
            ),
            # 3. linear (Sequential Boundaries)
            # Structural boundaries. EXCLUDES: Access modifiers (encapsulation) and final (freeze_hits).
            "structural_boundaries": re.compile(
                r"\b(void|return|import|package|class|interface|enum|record|extends|implements|var|sealed|non-sealed|permits|new|throws|module|requires|exports|opens|provides|uses)\b"
            ),
            # 4. func_start (Executable Logic Anchors)
            # ONLY executable logic blocks. EXCLUDES classes/interfaces. Steps over annotations.
            "func_start": re.compile(
                r"^[ \t]*(?:@[\w.]+(?:\([^)]*\))?[ \t]+){0,10}"
                # =====================================================================
                # [THE EXECUTION SHIELD]: AST-FREE HALLUCINATION PREVENTION
                # Previously, the "Instantiation Shield" only stopped `new`. However,
                # execution verbs like `return TargetFunc();` or `throw TargetFunc();`
                # were being blindly swallowed by the return-type matcher, treating
                # 'return' as the data type and 'TargetFunc' as the function name!
                # FIX: Expanded the shield to explicitly abort on ALL control flow and
                # execution keywords at the start of the sequence.
                # =====================================================================
                r"(?!(?:new|return|throw|if|else|while|for|switch|catch)\b)"
                r"(?:(?:public|protected|private|static|final|abstract|synchronized|native|default|<[^>]*>)[ \t]+){0,5}"
                r"(?:[a-zA-Z_$][\w<>$\[\]?,]*[ \t]+){0,5}"
                r"(?!(?:if|for|while|switch|catch|new|return|class|interface|enum|record)\b)([A-Za-z_$][\w_$]*)\s*\(",
                re.M,
            ),
            # 5. class_start (Object / Entity Declarations)
            "class_start": re.compile(
                r"^[ \t]*(?:@[\w.]+(?:\([^)]*\))?[ \t]*){0,5}(?:(?:public|protected|private|static|final|sealed|non-sealed|abstract|strictfp)[ \t]+){0,5}(?:class|interface|enum|record)\s+([A-Za-z_$][\w_$]*)(?:\s+(?:extends|implements)\s+([A-Za-z_$][\w_$, \t<>\?]*))?",
                re.M,
            ),
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            # 6. safety (Defensive Programming / Validation)
            "safety": re.compile(
                r"\b(try|catch|finally|assert|Optional|Objects\.requireNonNull|instanceof)\b|@(Valid|Validated|NotNull|NonNull|NotBlank|Immutable|Transactional)\b"
            ),
            # 7. safety_neg (Safety Bypasses / Unchecked Types)
            "safety_bypasses": re.compile(
                r"\b(null)\b|return\s+null|\([A-Z]\w+\)\s*(?!->)[a-zA-Z_$]|catch\s*\(\s*(?:Exception|Throwable)\b|@SuppressWarnings|@SneakyThrows|\.get\(\)"
            ),
            # 8. danger (High-Risk Execution / System Calls)
            # Process killers and raw memory/execution risks. EXCLUDES prints (Phase 5).
            "high_risk_execution": re.compile(
                r"\b(Runtime\.getRuntime\(\)\.exec|ProcessBuilder|System\.exit|Thread\.stop|Unsafe)\b"
            ),
            # 9. io (I/O & Network Boundaries)
            "io": re.compile(
                r"\b(File|InputStream|OutputStream|Reader|Writer|Scanner|Files\.|Path|Socket|RestTemplate|WebClient|RestClient|HttpClient|Connection|ResultSet|Statement|EntityManager|DataSource|Repository)\b"
            ),
            # 10. api (Public Surface Area)
            "api": re.compile(
                r"\b(public|protected)\b|@(RestController|Controller|Service|Component|Bean|Produces|Consumes|RequestMapping|GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping|Endpoint|WebFilter)\b"
            ),
            # 11. flux (State Mutation)
            # Mutation of state. EXCLUDES final (freeze_hits).
            "state_mutation": re.compile(
                r"\b(volatile|Atomic\w+)\b|^[ \t]*(?:this\.)?\w+[ \t]*=|@(?:Setter|Data)\b|(?:\w+\.)?(?:set[A-Z]\w+|add|put|remove|clear|addAll|replace|computeIfAbsent)\s*\("
            ),
            # 12. dead_code (Commented Logic / Deprecated Trails)
            "dead_code": re.compile(r"//[ \t]*(?:public|private|protected|class|void|if|for|while|return|import)\b"),
            # 13. doc (Structured Documentation)
            "doc": re.compile(
                r"/\*\*|@param|@return|@throws|@deprecated|@see|@since|@apiNote|@implSpec|@Operation|@Schema"
            ),
            # 14. test (Testing & Assertions)
            "test": re.compile(
                r"@(?:Test|ParameterizedTest|Before|After|BeforeEach|AfterEach|Mock|InjectMocks)|assert[A-Za-z0-9_]*\s*\(|\b(?:verify|expect|given|when)\s*\("
            ),
            # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
            # 15. concurrency (Asynchronous Execution)
            "concurrency": re.compile(
                r"\b(synchronized|Thread|Runnable|Future|CompletableFuture|ExecutorService|Semaphore|Atomic\w+|VirtualThread|StructuredTaskScope|ScopedValue|Mono|Flux|Publisher)\b|@(?:Async|Scheduled)"
            ),
            # 16. ui_framework (UI / View Components)
            "ui_framework": re.compile(
                r"\b(SwingUtilities|JFrame|JPanel|javafx\.|ModelAndView|ModelMap|Model|@ModelAttribute|VaadinSession|FacesContext|UIComponent)\b"
            ),
            # 17. closures (Closures / Anonymous Functions)
            "closures": re.compile(r"->|::"),
            # 18. globals (Global / Shared State)
            "globals": re.compile(
                r"\b(System\.getProperty|System\.getenv|public\s+static\s+(?:final[ \t]+)?\w+\s+[A-Z_0-9]+[ \t]*=|ThreadLocal|ScopedValue)\b|@(?:Value|ConfigurationProperties)"
            ),
            # 19. decorators (Decorators / Annotations)
            "decorators": re.compile(r"^[ \t]*@[\w.]+(?:\([^)]*\))?", re.M),
            # 20. generics (Generics / Type Parameters)
            "generics": re.compile(r"<\s*[A-Z?][^>]*>"),
            # 21. comprehensions (Iterators / Comprehensions)
            "comprehensions": re.compile(
                r"\.(?:stream|parallelStream|map|filter|reduce|collect|flatMap|forEach|anyMatch|noneMatch|gather)\("
            ),
            # 22. scientific (Numerical / Compute Libraries)
            "scientific": re.compile(
                r"\b(Math\.|BigDecimal|BigInteger|Random|SecureRandom|StrictMath|VectorSpecies|FloatVector|IntVector)\b"
            ),
            # 23. heat_triggers (Metaprogramming & Reflection)
            # Reflection and dynamic proxies.
            "reflection_metaprogramming": re.compile(
                r"\b(reflect\.|native|Class\.forName|Method\.invoke|Field\.setAccessible|Proxy\.newProxyInstance|ClassLoader|MethodHandles|VarHandle|Linker\.nativeLinker)\b|@SneakyThrows"
            ),
            # 24. import (Dependency Inclusions)
            "import": re.compile(r"^[ \t]*import\s+(?:static[ \t]+)?[\w.]+;", re.M),
            "_dependency_capture": re.compile(r"^[ \t]*import[ \t\n]+(?:static[ \t\n]+)?([\w.*]+)[ \t\n]*;", re.M),
            # 25. ownership (Authorship Metadata)
            "ownership": re.compile(r"@author\s+(.*)", re.I),
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            # 26. planned_debt (Annotated Debt / TODOs)
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            # 29. spec_exposure (Spec / Audit Traceability)
            "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]", re.I),
            # 30. tabs_vs_spaces (Formatting Inconsistencies) 
            "tabs_vs_spaces": None,
            # 31. ssr_boundaries (Server-Side Rendering)
            "ssr_boundaries": re.compile(
                r"\b(ModelAndView|FacesServlet|HttpServletRequest|HttpServletResponse|@ResponseBody|@ResponseStatus|JspWriter|ThymeleafViewResolver)\b"
            ),
            # 32. events (Event Emitters / Pub-Sub)
            "events": re.compile(
                r"\b(ApplicationEvent|ApplicationEventPublisher|ApplicationListener|@EventListener|@KafkaListener|@RabbitListener|@JmsListener|EventObject|publishEvent)\b"
            ),
            # 33. dependency_injection (Dependency Injection / IoC)
            "dependency_injection": re.compile(
                r"\b(@Autowired|@Inject|@Qualifier|@Primary|@Component|@Service|@Repository|@Bean|@Configuration|ApplicationContext|BeanFactory|@Provides)\b"
            ),
            # 34. macros
            "macros": None,  # Java lacks preprocessor macros.
            # 35. pointers (Pointer Arithmetic / Memory Addressing)
            # Project Panama (Java 22+) bridging to native memory.
            "pointers": re.compile(r"\b(MemorySegment|MemoryLayout|ValueLayout|AddressLayout|SymbolLookup)\b"),
            # 36. memory_alloc
            "memory_alloc": re.compile(
                r"\b(Arena\.ofConfined|Arena\.ofShared|Arena\.ofAuto|Arena\.global|SegmentAllocator|allocateFrom|ByteBuffer\.allocateDirect)\b"
            ),
            # 37. inline_asm
            "inline_asm": None,
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # 38. telemetry (Structured Logging / Telemetry)
            "telemetry": re.compile(
                r"\b(log|logger|LOGGER|LoggerFactory|LogManager|MDC|Tracer|Span)\.(?:info|error|warn|warning|debug|trace|log)\b|@Slf4j|@Log4j2"
            ),
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs)
            "debug_prints": re.compile(
                r"\b(System\.out\.(?:print|println|printf)|System\.err\.(?:print|println|printf)|\.printStackTrace\(\))\b"
            ),
            # # 40. explicit_casts (Explicit Type Casting)
            "explicit_casts": re.compile(
                r"\(\s*(?:int|long|short|byte|char|float|double|boolean|[A-Z][A-Za-z0-9_]*)\s*\)\s*[a-zA-Z_$]"
            ),
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
            "panics_and_aborts": re.compile(r"\b(throw|abort|System\.exit|halt)\b"),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
            "thread_sleeps": re.compile(r"\b(Thread\.sleep|TimeUnit\.[A-Z_]+\.sleep|delay|CountDownLatch\.await)\b"),
            # 43. bitwise_ops (Bitwise Operations)
            "bitwise_ops": re.compile(r"<<|>>>?|\^|~"),
            # 44. sync_locks (Resource Management & Stability)
            "sync_locks": re.compile(
                r"\b(mutex|lock|synchronized|Semaphore|ReentrantLock|ReadWriteLock|Condition)\b",
                re.I,
            ),
            # 45. immutability_locks (Immutability Constraints)
            "immutability_locks": re.compile(r"\b(final|immutable|unmodifiable[A-Z]\w*|Object\.freeze)\b"),
            # 46. cleanup (Resource Cleanup / Teardown)
            "cleanup": re.compile(r"\b(close|dispose|shutdown|free|release|cleaner\.register)\b\s*\("),
            # 47. encapsulation (Access Modifiers / Encapsulation)
            "encapsulation": re.compile(r"\b(private|protected|internal)\b"),
            # 48. listeners (Event Listeners / Observers)
            "listeners": re.compile(r"\b(on[A-Z]\w*|addEventListener|subscribe|@KafkaListener|@RabbitListener)\b"),
            # 49. test_skip (Bypassed Tests / Ignored Specs)
            "test_skip": re.compile(r"@(?:Ignore|Disabled)|test\.skip\(|mock\(|spy\(|verifyZeroInteractions"),
            # --- PHASE 3: HYBRID DOMAIN SENSORS (Java Specifics) ---
            "serialization_parsing": re.compile(
                r"\b(ObjectMapper|readValue|readTree|fromJson|ObjectInputStream|DocumentBuilder|SAXParser)\b"
            ),
            "regex_execution": re.compile(r"\b(Pattern\.compile|Matcher\.find|\.matches\()\b"),
            "time_date_logic": re.compile(
                r"\b(LocalDate(?:Time)?|ZonedDateTime|Instant|Duration|System\.currentTimeMillis|Calendar\.getInstance)\b"
            ),
            "ipc_rpc_bridges": re.compile(r"\b(ProcessBuilder|KafkaTemplate|RabbitTemplate|JmsTemplate|java\.rmi)\b"),
        },
    },
    "csharp": {
        "_meta": {
            "target_version": "C# 14 / .NET 10 / Modern ASP.NET Core & Blazor",
            "last_updated": "2026-02-18",
            "blueprint_version": "v5.0",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard modern suffixes, legacy ASP.NET, and build-tooling formats.
        "extensions": [
            ".cs",
            ".csx",
            ".razor",
            ".cshtml",
            ".cake",
            ".linq",
            ".ashx",
            ".asmx",
            ".ascx",
            ".svc",
        ],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: Extensionless build/config scripts and tooling configs that are secretly pure code.
        "exact_matches": ["build.cake"],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: Sibling extensions, package manifests, and lockfiles to resolve ambiguous files.
        "discriminators": [
            ".cs",
            ".csproj",
            ".sln",
            "packages.config",
            "nuget.config",
            "global.json",
            "App.config",
            "Web.config",
            "project.json",
        ],
        # EXECUTION SIGNATURES: Interpreters found on Line 1.
        "shebangs": ["dotnet-script", "csi"],
        # UPGRADED: Maps to Family 1 (Standard C)
        # Rationale: Uses '//' for line-level literature; multi-line literature
        # (/* */) is handled by the Section 2.3.C.3 Heuristic Pass.
        "lexical_family": "standard_block",
        "rules": {
            # --- LEXICAL DELIMITER CONTROLS ---
            # Standard C-family line comment token (Includes XML Doc ///)
            "_line_anchor": re.compile(r"//"),
            # Inline comments follow the standard '//' delimiter.
            "_inline_comment": re.compile(r"//"),
            # Block comment start: /* (Standard non-recursive delimiter)
            "_block_start": re.compile(r"/\*"),
            # Block comment end: */
            "_block_end": re.compile(r"\*/"),
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # 1. branch (Control Flow / Branching)
            # Decisions and logical jumps. EXCLUDES throw (bailout_hits).
            # Includes pattern matching (and, or, not) and null-coalescing.
            "branch": re.compile(
                r"\b(if|else|switch|case|default|for|foreach|while|do|catch|finally|continue|break|goto|try|yield\s+return|yield\s+break|and|or|not)\b|\?\?|\?"
            ),
            # 2. args (Parameters / Coupling)
            # Parameter blocks for methods, primary constructors, and lambdas.
            "args": re.compile(
                # =====================================================================
                # [ THE GHOST ARGS SHIELD (C#) ]
                # To prevent hallucinating standard function invocations, we demand structural proof.
                # Branch 1: Standard Methods MUST have a return type (e.g., `Task<T> Foo(...)`).
                # Branch 2: Constructors lack return types, so they MUST be anchored to `:` or `{`.
                # Branch 3: Standard fat-arrow lambdas.
                # Upgraded all spaces to `[ \t\n]+` to support Pathological vertical parameters.
                # =====================================================================
                r"(?:"
                # 1. Standard Methods
                r"^[ \t]*(?:\[[^\]]*\][ \t\n]*){0,5}(?:(?:public|private|protected|internal|static|virtual|override|abstract|sealed|async|unsafe|partial|new|extern|file|ref|scoped|readonly)[ \t\n]+){0,5}(?:[\w<>\[\]?]+[ \t\n]+)\w+[ \t\n]*\([^)]*\)|"
                # 2. Constructors
                r"^[ \t]*(?:(?:public|private|protected|internal|static|unsafe)[ \t\n]+)?[A-Z]\w*[ \t\n]*\([^)]*\)[ \t\n]*(?::[ \t\n]*(?:base|this)|[{])|"
                # 3. Lambdas
                r"(?:\([^)]*\)|[a-zA-Z_$][\w_$]*)[ \t\n]*=>"
                r")",
                re.M,
            ),
            # 3. linear (Sequential Boundaries)
            # Structural boundaries. EXCLUDES: Access modifiers (encapsulation) and const/readonly (freeze_hits).
            "structural_boundaries": re.compile(
                r"\b(var|return|class|interface|struct|record|enum|using|namespace|yield|await|delegate|event|init|required|field|implements|extends|declare)\b|=>"
            ),
            # 4. func_start (Executable Logic Anchors)
            # ONLY executable logic blocks. EXCLUDES types/classes.
            #
            # =====================================================================
            # [ CONTEXT: C# "IRON WALL" FUNCTION EXTRACTOR & REDOS SHIELD ]
            # PURPOSE: Anchors executable logic blocks (methods) in C# up to C# 14.
            # VULNERABILITY: C# allows massive return types (e.g., nested tuples),
            #   generics, and explicit interface implementations. If spaces are allowed
            #   freely inside unbounded quantifiers, massive Roslyn test strings cause
            #   Catastrophic Backtracking, locking the Python GIL at the C-level.
            # THE FIX: Strict character exclusion, numeric bounding, and mutual
            #   exclusivity between word characters and spaces.
            #
            # [ THE VERTICAL IRON WALL UPDATE ] (Hard-learned from Pathological Fuzzer):
            #   Developers often place attributes, modifiers, return types, and names
            #   on completely separate lines. We replaced horizontal spaces `[ \t]+`
            #   with strictly bounded multi-line spaces `[ \t\n]+`. We EXPLICITLY DO NOT
            #   use `\s+` because unbounded wildcards with newlines trigger ReDoS.
            # =====================================================================
            "func_start": re.compile(
                # 1. THE HORIZONTAL ANCHOR & ATTRIBUTE SHIELD
                # Anchors to the line start. Steps over C# attributes [Obsolete], [Fact], etc.
                # [REDOS ARMOR]: `[^\]]{0,250}` prevents a missing closing bracket from spiraling
                # across the entire file. `{0,5}` caps the max number of stacked attributes.
                # [VERTICAL FIX]: `[ \t\n]*` allows attributes to sit on lines above the function.
                r"^[ \t]*(?:\[[^\]]{0,250}\][ \t\n]*){0,5}"
                # =====================================================================
                # [THE INSTANTIATION SHIELD]: AST-FREE HALLUCINATION PREVENTION
                # If an object instantiation `new TargetFunc()` is poorly indented against
                # the left margin, the engine will hallucinate it as a constructor definition
                # (because constructors naturally lack return types).
                # FIX: Forcefully abort matching if the sequence begins with the 'new' keyword
                # followed immediately by an identifier and an opening parenthesis.
                # =====================================================================
                r"(?!new[ \t\n]+[@A-Za-z_$][\w_$.]*(?:<[^>]{0,100}>)?[ \t\n]*\()"
                # 2. MODIFIERS (Linkage, Storage, & Access)
                # Matches `public async`, `protected internal static`, etc.
                # [VERTICAL FIX]: `[ \t\n]+` allows modifiers to wrap across newlines.
                r"(?:(?:public|private|protected|internal|static|virtual|override|abstract|sealed|async|unsafe|partial|new|extern|file|ref|readonly)[ \t\n]+){0,5}"
                # 3. THE "IRON WALL" RETURN TYPE
                # Safely captures complex modern C# return types before the function name.
                # Supports: standard types `int`, arrays `int[]`, generics `List<T>`,
                # namespaces `System.Threading.Tasks.Task`, tuples `(int, string)`, and nullables `string?`.
                # [REDOS ARMOR 1]: `(?![ \t]*#)` prevents the engine from crossing into a #region or #if block.
                # [REDOS ARMOR 2]: The character class `[...]+` STRICTLY FORBIDS spaces/tabs. The `[ \t\n]+`
                # follows it outside the group. This mutual exclusivity guarantees O(N) parsing.
                # [REDOS ARMOR 3]: Explicitly prevents return types from eating modifiers during a backtrack,
                # sealing the overlapping permutation leak that caused Catastrophic Backtracking.
                r"(?:(?![ \t]*#)(?!(?:public|private|protected|internal|static|virtual|override|abstract|sealed|async|unsafe|partial|new|extern|file|ref|readonly)\b)[a-zA-Z0-9_<>\[\]?,.()]+[ \t\n]+){0,10}"
                # 4. THE "NOT A FUNCTION" SHIELD
                # Negative lookahead ensuring we don't accidentally capture control flow,
                # primitive type keywords, or object instantiations as function names.
                r"(?!(?:if|for|foreach|while|switch|catch|using|lock|new|return|class|interface|struct|record|enum|yield|throw|await|sizeof|typeof|nameof)\b)"
                # 5. THE IDENTIFIER CAPTURE (GROUP 1) & GENERIC STEPPER
                # Captures the actual satellite name:
                # - `[@A-Za-z_$]` supports C# verbatim identifiers (e.g., `@class`).
                # - `[\w_$.]*` supports explicit interface implementations (e.g., `IMyInterface.DoWork`).
                # - `(?:[ \t\n]*<[^>]{0,100}>)?` safely steps over method-level generic definitions
                #   like `<T, U>` BEFORE hitting the opening parenthesis.
                # [VERTICAL FIX]: Removed `\n` exclusion from the generic stepper to support multi-line generics.
                r"([@A-Za-z_$][\w_$.]*)(?:[ \t\n]*<[^>]{0,100}>)?[ \t\n]*\(",
                re.M,
            ),
            # 5. class_start (Object / Entity Declarations)
            "class_start": re.compile(
                r"^[ \t]*(?:\[[^\]]*\][ \t]*){0,5}(?:(?:public|internal|private|protected|static|sealed|abstract|partial|file|unsafe|new)[ \t]+){0,5}(?:class|interface|struct|record|enum)\s+([A-Za-z_$][\w_$]*)(?:\s*:\s*([A-Za-z_$][\w_$, \t<>\?]*))?",
                re.M,
            ),
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            # 6. safety (Defensive Programming / Validation)
            "safety": re.compile(
                r"\b(try|catch|finally|checked|is|as|nameof|required|ArgumentNullException|ThrowIfNull|ThrowIfNullOrWhiteSpace)\b|\[(?:Required|NotNull|Authorize)\]|\?\?|\?\."
            ),
            # 7. safety_neg (Safety Bypasses / Unchecked Types)
            # Null-forgiving operator, dynamic, and unsafe bypasses.
            "safety_bypasses": re.compile(r"!\.|\bnull!|#pragma\s+warning\s+disable|\.Result\b|\.Wait\(\)|\b(dynamic)\b"),
            # 8. danger (High-Risk Execution / System Calls)
            # Extreme tech debt/vulnerabilities. EXCLUDES TODO (debt) and Console (print).
            "high_risk_execution": re.compile(r"\b(Thread\.Abort|Process\.Start|Environment\.FailFast|Environment\.Exit|goto)\b"),
            # 9. io (I/O & Network Boundaries)
            "io": re.compile(
                r"\b(File|Directory|Stream|HttpClient|Path|SqlConnection|SqlCommand|DbContext|DbSet|HttpRequest|HttpResponse)\b\.|\[Table\("
            ),
            # 10. api (Public Surface Area)
            # Public exposure surface. Explicit visibility + Controller mapping.
            "api": re.compile(
                r"\b(public|internal)\b|\[(?:HttpGet|HttpPost|HttpPut|HttpDelete|Route|ApiController|HubMethodName)\]|\bapp\.Map(?:Get|Post|Put|Delete|Group)\b"
            ),
            # 11. flux (State Mutation)
            # Mutation of state. EXCLUDES const/readonly (freeze_hits).
            "state_mutation": re.compile(
                r"\b(set|field)\s*[{;]|volatile|ref\s|out\s|^[ \t]*(?:this\.)?\w+[ \t]*=|(?:\w+\.)?(?:Add|Remove|Clear|Insert|Push|Pop|Update)\s*\("
            ),
            # 12. dead_code (Commented Logic / Deprecated Trails)
            "dead_code": re.compile(
                r"//[ \t]*(?:public|private|protected|internal|class|void|if|for|foreach|while|return|using)\b"
            ),
            # 13. doc (Structured Documentation)
            "doc": re.compile(r"///|///\s*<summary>|///\s*<param|///\s*<returns>|///\s*<remarks>"),
            # 14. test (Testing & Assertions)
            "test": re.compile(
                r"\[(?:Test|Fact|Theory|TestMethod|TestClass|SetUp|TearDown)\]|\b(?:Assert\.|Should\(\)|Mock\.|Substitute\.For)\b"
            ),
            # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
            # 15. concurrency (Asynchronous Execution)
            "concurrency": re.compile(
                r"\b(async|await|Task|ValueTask|Thread|Parallel|SemaphoreSlim|Mutex|Channel|IAsyncEnumerable|Interlocked)\b"
            ),
            # 16. ui_framework (UI / View Components)
            "ui_framework": re.compile(
                r"\b(ControllerBase|IActionResult|Binding|ObservableCollection|DependencyProperty|ComponentBase|RenderFragment|MonoBehaviour)\b"
            ),
            # 17. closures (Closures / Anonymous Functions)
            "closures": re.compile(r"=>|delegate[ \t]*\{"),
            # 18. globals (Global / Shared State)
            "globals": re.compile(
                r"\b(ConfigurationManager|Environment\.|public\s+static\s+(?:readonly[ \t]+)?[\w<>]+\s+[A-Z_0-9]+[ \t]*=|AsyncLocal)\b|\[ThreadStatic\]"
            ),
            # 19. decorators (Decorators / Annotations)
            "decorators": re.compile(r"^[ \t]*\[[A-Za-z_][^\]]*\]", re.M),
            # 20. generics (Generics / Type Parameters)
            "generics": re.compile(r"<\s*[A-Z][^>]*>|\bwhere\s+\w+\s*:"),
            # 21. comprehensions (Iterators / Comprehensions)
            "comprehensions": re.compile(
                r"\.(?:Select|Where|OrderBy|GroupBy|Aggregate|Any|All|ToList|ToArray|SelectMany)\(|^[ \t]*from\s+\w+\s+in\s+",
                re.M,
            ),
            # 22. scientific (Numerical / Compute Libraries)
            "scientific": re.compile(
                r"\b(Math\.|MathF\.|Vector[234]|Matrix4x4|Random|Complex|Tensor|TensorPrimitives)\b"
            ),
            # 23. heat_triggers (Metaprogramming & Reflection)
            # Reflection and dynamic Emit.
            "reflection_metaprogramming": re.compile(
                r"\b(System\.Reflection|DllImport|LibraryImport|MethodInfo|Activator|Marshal\.|Emit|ILGenerator)\b"
            ),
            # 24. import (Dependency Inclusions)
            "import": re.compile(r"^[ \t]*(?:global[ \t]+)?using\s+(?:static[ \t]+)?[\w.]+;", re.M),
            "_dependency_capture": re.compile(
                r"^[ \t]*(?:global[ \t\n]+)?using[ \t\n]+(?:static[ \t\n]+)?([\w.]+)[ \t\n]*;",
                re.M,
            ),
            # 25. ownership (Authorship Metadata)
            "ownership": re.compile(r"(?:<author>|Author:|Created by)\s*(.*)", re.I),
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            # 26. planned_debt (Annotated Debt / TODOs)
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            # 29. spec_exposure (Spec / Audit Traceability)
            "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]", re.I),
            # 30. tabs_vs_spaces (Formatting Inconsistencies) 
            "tabs_vs_spaces": None,
            # 31. ssr_boundaries (The Blazor/Razor Horizon)
            "ssr_boundaries": re.compile(
                r"@(?:page|rendermode|code|layout)|\[(?:Route|CascadingParameter)\]|\b(RenderFragment|ComponentBase|IViewComponentResult)\b"
            ),
            # 32. events (Event Emitters / Pub-Sub)
            "events": re.compile(
                r"\b(event\s+[\w<>]+\s+\w+|EventHandler|\+=\s*|-=\s*|Invoke|Raise|MediatR|INotification|IRequest|Publish)\b"
            ),
            # 33. dependency_injection (Dependency Injection / IoC)
            "dependency_injection": re.compile(
                r"\b(IServiceCollection|AddTransient|AddScoped|AddSingleton|AddKeyed|\[Inject\]|FromServices|IServiceProvider)\b"
            ),
            # 34. macros (Preprocessor Directives / Macros)
            "macros": re.compile(
                r"^[ \t]*#(?:define|undef|if|elif|else|endif|region|endregion|pragma|warning|error)\b",
                re.M,
            ),
            # 35. pointers (Pointer Arithmetic / Memory Addressing)
            # Native pointers and modern memory structures (Span/Memory).
            "pointers": re.compile(r"\b(?:fixed|stackalloc|Unsafe\.AsPointer|IntPtr|UIntPtr|nint|nuint)\b|->"),
            # 36. memory_alloc (Manual Memory Management)
            "memory_alloc": re.compile(
                r"\b(Marshal\.AllocHGlobal|GC\.AllocateArray|MemoryPool|ArrayPool<[^>]*>\.Shared\.Rent|ref\s+struct|scoped\s+ref)\b"
            ),
            # 37. inline_asm
            "inline_asm": None,
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # 38. telemetry (Structured Logging / Telemetry)
            "telemetry": re.compile(
                r"\b(?:ILogger|_logger|Log|TelemetryClient|ActivitySource)\.(?:LogInformation|LogError|LogWarning|LogDebug|StartActivity|TrackEvent)\b|\[LoggerMessage"
            ),
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs)
            "debug_prints": re.compile(r"\b(Console\.(?:Write|WriteLine|Error)|Debug\.(?:Write|WriteLine|Print))\b"),
            # # 40. explicit_casts (Explicit Type Casting)
            "explicit_casts": re.compile(
                r"\bas\s+[A-Z]\w*|\(\s*(?:int|long|short|byte|char|float|double|decimal|bool|string|[A-Z][A-Za-z0-9_]*)\s*\)\s*[a-zA-Z_$]"
            ),
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
            "panics_and_aborts": re.compile(r"\b(throw|abort|FailFast|Environment\.Exit)\b"),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
            "thread_sleeps": re.compile(r"\b(sleep|delay|Wait\(\)|Task\.Delay|Thread\.Sleep)\b"),
            # 43. bitwise_ops (Bitwise Operations)
            # Low-level byte manipulation. Safely maps to C# bitwise operators without overlapping language-specific pipelines.
            "bitwise_ops": re.compile(r"<<|>>|\^|~"),
            # 44. sync_locks (Resource Management & Stability)
            "sync_locks": re.compile(
                r"\b(mutex|lock|Monitor|Semaphore|Interlocked|SpinLock|ReaderWriterLockSlim)\b",
                re.I,
            ),
            # 45. immutability_locks (Immutability Constraints)
            "immutability_locks": re.compile(r"\b(const|readonly|init|Immutable[A-Z]\w*)\b"),
            # 46. cleanup (Resource Cleanup / Teardown)
            "cleanup": re.compile(r"\b(dispose|close|free|delete|GC\.Collect|GC\.SuppressFinalize)\b\s*\("),
            # 47. encapsulation (Access Modifiers / Encapsulation)
            "encapsulation": re.compile(r"\b(private|protected|internal|file)\b"),
            # 48. listeners (Event Listeners / Observers)
            "listeners": re.compile(r"\b(on|addEventListener|subscribe|EventHandler)\b|\+="),
            # 49. test_skip (Bypassed Tests / Ignored Specs)
            "test_skip": re.compile(r"\[(?:Ignore|Skipped)\]|test\.skip\(|mock\(|stub\(|Substitute\.For"),
            # --- PHASE 3: HYBRID DOMAIN SENSORS (C# Specifics) ---
            "serialization_parsing": re.compile(
                r"\b(JsonSerializer\.Deserialize|JsonConvert\.DeserializeObject|XmlSerializer|BinaryFormatter)\b"
            ),
            "regex_execution": re.compile(r"\b(Regex\.Match(?:es)?|Regex\.Replace|Regex\.IsMatch|new\s+Regex)\b"),
            "time_date_logic": re.compile(
                r"\b(DateTime\.Now|DateTime\.UtcNow|DateTimeOffset|TimeSpan|Stopwatch\.StartNew)\b"
            ),
            "ipc_rpc_bridges": re.compile(r"\b(Process\.Start|NamedPipeServerStream|ChannelFactory|GrpcChannel)\b"),
        },
    },
    "go": {
        "_meta": {
            "target_version": "Go 1.22+ (Generics, Slog, Workspace paradigms)",
            "last_updated": "2026-02-18",
            "blueprint_version": "v5.0",
            "status": "production",
        },
        "extensions": [".go"],
        "exact_matches": [],
        "discriminators": [
            ".go",
            "go.mod",
            "go.sum",
            "go.work",
            "Gopkg.toml",
            "Gopkg.lock",
            "glide.yaml",
            "vendor/modules.txt",
        ],
        "shebangs": ["go", "gorun", "yaegi"],
        "lexical_family": "standard_block",
        "rules": {
            # --- LEXICAL DELIMITER CONTROLS ---
            # Standard C-family line comment token.
            "_line_anchor": re.compile(r"//"),
            # Inline comments follow the standard '//' delimiter.
            "_inline_comment": re.compile(r"//"),
            # Block comment start: /* (Standard non-recursive delimiter).
            "_block_start": re.compile(r"/\*"),
            # Block comment end: */
            "_block_end": re.compile(r"\*/"),
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # 1. branch (Control Flow / Branching)
            # Includes select/case and range-based loops. EXCLUDES panic (bailout_hits).
            "branch": re.compile(
                r"\b(if|else|switch|case|default|for|range|select|goto|break|continue|fallthrough)\b|&&|\|\|"
            ),
            # 2. args (Parameters / Coupling)
            # Parameter blocks for functions and methods. Bounded generics [^\]]* and params [^)]*.
            "args": re.compile(r"func\s+(?:\([^)]*\)[ \t]+)?\w*(?:\[[^\]]*\])?\s*\([^)]*\)", re.M),
            # 3. linear (Sequential Boundaries)
            # Structural boundaries. EXCLUDES: const/var (freeze_hits) and Capitalization (encapsulation).
            "structural_boundaries": re.compile(r"\b(package|import|return|type|go|defer|chan|map|interface|struct)\b"),
            # 4. func_start (Executable Logic Anchors)
            # ONLY executable logic blocks.
            # Bypasses the 'func' keyword, skips optional method receivers (e.g. (s *Server)),
            # and strictly captures the actual identifier name. Ignores anonymous functions.
            "func_start": re.compile(
                # =====================================================================
                # [ THE VERTICAL RECEIVER SHIELD ]
                # Go developers occasionally format complex struct receivers across multiple lines.
                # FIX: Replaced horizontal spaces `[ \t]+` with `[ \t\n]+` around the `func`
                # keyword, receiver block, and function name to safely leap across vertical gaps.
                # =====================================================================
                r"^[ \t]*func(?:[ \t\n]+\([^)]+\))?[ \t\n]+([A-Za-z_$][\w_$]*)[ \t\n]*\(",
                re.M,
            ),
            # 5. class_start (Object / Entity Declarations)
            # =====================================================================
            # [ THE VERTICAL GENERICS SHIELD (GO) ]
            # Go 1.18+ introduces generic type parameters `[T any]` which can be
            # vertically formatted before the `struct` or `interface` keyword.
            # FIX: Injected a capture group `([a-zA-Z_]\w*)` for exact entity name
            # extraction. Upgraded the `\s+` to explicitly bounded `[ \t\n]+` and
            # decoupled the generic stepper `(?:[ \t\n]*\[[^\]]*\])?` to safely
            # leap across vertical boundaries.
            # =====================================================================
            "class_start": re.compile(
                r"^[ \t]*type[ \t\n]+([a-zA-Z_]\w*)(?:[ \t\n]*\[[^\]]*\])?[ \t\n]+(?:struct|interface)",
                re.M,
            ),
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            # 6. safety (Defensive Programming / Validation)
            "safety": re.compile(
                r"err\s*!=\s*nil|\b(errors\.(?:Is|As|New|Join)|sync\.(?:Once|WaitGroup)|context\.Context|recover\(\))\b"
            ),
            # 7. safety_neg (Safety Bypasses / Unchecked Types)
            # Explicitly ignoring errors via blank identifier.
            "safety_bypasses": re.compile(r'_\s*,\s*err[ \t]*=|_[ \t]*=\s*\w+|\bimport\s+(?:\.[ \t]+)?"'),
            # 8. danger (High-Risk Execution / System Calls)
            # Process-killing commands and direct syscalls. EXCLUDES TODO (debt) and fmt.Print (print_hits).
            "high_risk_execution": re.compile(r"\b(os\.Exit|syscall\.Kill|syscall\.RawSyscall|log\.Fatal(?:f|ln)?)\b"),
            # 9. io (I/O & Network Boundaries)
            "io": re.compile(
                r"\b(os\.(?:Open|Create|ReadFile)|io\.(?:Reader|Writer|Copy)|net/http|database/sql|bufio\.|grpc\.|sqlx\.|pgx\.)\b"
            ),
            # 10. api (Public Surface Area)
            # Implicit Public Reality: Capitalized top-level identifiers in Go are public.
            "api": re.compile(
                r"^[ \t]*(?:func\s+(?:\([^)]*\)[ \t]+)?)?[A-Z]\w+|^[ \t]*(?:type|var|const)\s+[A-Z]\w+",
                re.M,
            ),
            # 11. flux (State Mutation)
            # Mutation of state. Reassignment and channel sends.
            "state_mutation": re.compile(r":=|(?<![=!<>])=(?![=])|<-|\bappend\(|\batomic\.(?:Add|Store|Swap)"),
            # 12. dead_code (Commented Logic / Deprecated Trails)
            "dead_code": re.compile(r"//[ \t]*(?:func|type|var|const|import|if|for|switch|select|return)\b"),
            # 13. doc (Structured Documentation)
            # GoDoc standard: comments immediately preceding a declaration.
            "doc": re.compile(r"^[ \t]*//\s+[A-Z][a-zA-Z0-9_]+\s+.*|^[ \t]*//\s*Package\s+", re.M),
            # 14. test (Testing & Assertions)
            "test": re.compile(r"\b(?:Test|Benchmark|Fuzz)[A-Z]\w*\b|t\.Run\b|\b(?:assert|require|mock)\.\w+\("),
            # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
            # 15. concurrency (Asynchronous Execution)
            "concurrency": re.compile(
                r"\b(go\s+func|go\s+\w+|chan\s+|select[ \t]*\{|context\.(?:WithTimeout|WithCancel)|errgroup\.Group)\b"
            ),
            # 16. ui_framework (UI / View Components)
            # Go is primarily backend; targets templates and web handlers.
            "ui_framework": re.compile(
                r"\b(html/template|text/template|http\.HandleFunc|ServeHTTP|gin\.|echo\.|fiber\.)\b"
            ),
            # 17. closures (Closures / Anonymous Functions)
            "closures": re.compile(r"func\s*\([^)]*\)\s*(?:\[[^\]]*\])?\s*(?:\([^)]*\))?[ \t]*\{"),
            # 18. globals (Global / Shared State)
            "globals": re.compile(
                r"^[ \t]*var\s+[a-zA-Z_]\w*\s*(?:[a-zA-Z_]\w*\s*)?=|os\.Getenv|os\.Environ",
                re.M,
            ),
            # 19. decorators (Decorators / Annotations)
            # Go lacks @decorators; uses Struct Tags and Build Tags.
            "decorators": re.compile(r'`[^`]*?(?:json|xml|yaml|gorm|db|bson):"[^"]*"[^`]*?`|//go:build|//\s*\+build'),
            # 20. generics (Generics / Type Parameters)
            "generics": re.compile(r"\[[^\]]*\b(?:any|comparable|~[a-zA-Z_]\w*)\b[^\]]*\]|\bany\b"),
            # 21. comprehensions (Iterators / Comprehensions)
            # Functional iteration helpers from the slices/maps packages.
            "comprehensions": re.compile(r"\b(slices\.(?:Delete|Filter|Sort|Compact)|maps\.(?:Keys|Values))\b"),
            # 22. scientific (Numerical / Compute Libraries)
            "scientific": re.compile(r"\b(math\.|math/cmplx\.|math/rand\.|crypto/rand\.|gonum\.)\b"),
            # 23. heat_triggers (Metaprogramming & Reflection)
            # Reflection, CGO, and Unsafe triggers.
            "reflection_metaprogramming": re.compile(r'import\s+"C"|\b(reflect\.|unsafe\.|cgo|go:linkname)\b'),
            # 24. import (Dependency Inclusions)
            "import": re.compile(r'^[ \t]*import\s*(?:\(|"[^"]+")', re.M),
            # ---> THE FIX: Strictly bounded to valid Go import path characters <---
            # Prevents raw HTTP string literals in test files from being hallucinated as packages.
            "_dependency_capture": re.compile(
                r'^[ \t]*(?:import\s+)?(?:\(\s*)?(?:[a-zA-Z0-9_.]+\s+)?["`]([a-zA-Z0-9_.\-/]+)["`]',
                re.M,
            ),
            # 25. ownership (Authorship Metadata)
            "ownership": re.compile(
                r"(?://|#|/\*)\s*(?:Author|Maintainer|Created by|Owner):?\s+([a-zA-Z0-9_ -]+)",
                re.I,
            ),
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            # 26. planned_debt (Annotated Debt / TODOs)
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            # 29. spec_exposure (Spec / Audit Traceability)
            "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]", re.I),
            # 30. tabs_vs_spaces (Formatting Inconsistencies) 
            # Gofmt mandates tabs; finding spaces at start signals structural friction.
            "tabs_vs_spaces": None,
            # 31. ssr_boundaries (Server-Side Rendering)
            "ssr_boundaries": re.compile(
                r"\b(html/template|ExecuteTemplate|http\.ResponseWriter|Render|gin\.Context)\b"
            ),
            # 32. events (Event Emitters / Pub-Sub)
            "events": re.compile(r"\b(EventBus|Publish|Subscribe|kafka\.|rabbitmq\.|Emit|OnEvent)\b"),
            # 33. dependency_injection (Dependency Injection / IoC)
            "dependency_injection": re.compile(
                r"\b(wire\.Build|wire\.NewSet|fx\.New|fx\.Provide|fx\.Invoke|dig\.Provide|do\.Provide)\b"
            ),
            # 34. macros (Preprocessor Directives / Macros)
            # Go lacks a preprocessor; //go: directives act as compile-time hooks.
            "macros": re.compile(r"^//go:(?:generate|build|noinline|nosplit|noescape|linkname)\b", re.M),
            # 35. pointers (Pointer Arithmetic / Memory Addressing)
            # Explicit pointer addressing and dereferencing.
            "pointers": re.compile(
                r"\b(?:uintptr|unsafe\.Pointer)\b|&\w+|\*(?:[A-Z]\w*|int\d*|uint\d*|float\d*|byte|rune|string|bool)\b"
            ),
            # 36. memory_alloc (Manual Memory Management)
            "memory_alloc": re.compile(r"\b(make|new)\s*\(|sync\.Pool\b"),
            # 37. inline_asm
            "inline_asm": None,  # Go handles ASM in separate .s files.
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # 38. telemetry (Structured Logging / Telemetry)
            "telemetry": re.compile(
                r"\b(slog|logrus|zap|zerolog|log)\.(?:Info|Warn|Error|Debug|Trace)(?:f|ln)?\b|\btrace\.Span\b"
            ),
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
            "debug_prints": re.compile(r"\b(fmt\.Print|fmt\.Println|fmt\.Printf|println|print)\b"),
            # # 40. explicit_casts (Explicit Type Casting)
            # Type assertions and conversions.
            "explicit_casts": re.compile(
                r"\.\([a-zA-Z_]\w*\)|\b(?:int|int8|int16|int32|int64|uint|uint8|uint16|uint32|uint64|float32|float64|byte|rune|uintptr|string)\s*\("
            ),
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
            "panics_and_aborts": re.compile(r"\b(panic|os\.Exit|log\.Fatal)\b"),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
            "thread_sleeps": re.compile(r"\b(time\.Sleep|time\.After|runtime\.Gosched)\b"),
            # 43. bitwise_ops (Bitwise Operations)
            "bitwise_ops": re.compile(r"<<|>>|\^|&\^"),
            # 44. sync_locks (Resource Management & Stability)
            "sync_locks": re.compile(r"\b(Mutex|RWMutex|Lock|Unlock|RLock|RUnlock|atomic\.|sync\.Map|sync\.Pool)\b"),
            # 45. immutability_locks (Immutability Constraints)
            "immutability_locks": re.compile(r"\bconst\b"),
            # 46. cleanup (Resource Cleanup / Teardown)
            "cleanup": re.compile(r"\b(defer|Close|Unlock|RUnlock|Stop|Cleanup)\b\s*\("),
            # 47. encapsulation (Access Modifiers / Encapsulation)
            # Unexported identifiers (lowercase) in Go are private/internal.
            "encapsulation": re.compile(
                r"^[ \t]*(?:func\s+(?:\([^)]*\)[ \t]+)?)?[a-z]\w+|^[ \t]*(?:type|var|const)\s+[a-z]\w+",
                re.M,
            ),
            # 48. listeners (Event Listeners / Observers)
            "listeners": re.compile(r"<-chan\b|\.On\(|\.Subscribe\("),
            # 49. test_skip (Bypassed Tests / Ignored Specs)
            "test_skip": re.compile(r"\bt\.Skip(?:f|Now)?\(|mock\.|gomock\."),
            # --- PHASE 3: HYBRID DOMAIN SENSORS (Go Specifics) ---
            "serialization_parsing": re.compile(
                r"\b(json\.Unmarshal|json\.Marshal|xml\.Unmarshal|xml\.Marshal|gob\.NewEncoder)\b"
            ),
            "regex_execution": re.compile(r"\b(regexp\.Compile|regexp\.MustCompile|\.MatchString)\b"),
            "time_date_logic": re.compile(r"\b(time\.Now\(\)|time\.Parse|time\.Duration|time\.Sleep|time\.Since)\b"),
            "ipc_rpc_bridges": re.compile(r"\b(net/rpc|grpc\.Dial|grpc\.NewServer|exec\.Command|syscall)\b"),
        },
    },
    "rust": {
        "_meta": {
            "target_version": "Rust 1.93.1 / Edition 2024 / Modern Async & Macro Stacks",
            "last_updated": "2026-02-18",
            "blueprint_version": "v5.0",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard modern suffixes, libraries, and metadata formats.
        "extensions": [".rs", ".rlib", ".rmeta"],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: Extensionless build/config scripts and tooling configs that are secretly pure code.
        "exact_matches": ["build.rs"],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: Sibling extensions, package manifests, and lockfiles to resolve ambiguous files.
        "discriminators": [
            ".rs",
            "Cargo.toml",
            "Cargo.lock",
            "rust-toolchain",
            "rust-toolchain.toml",
            "rustfmt.toml",
            "clippy.toml",
        ],
        # EXECUTION SIGNATURES: Interpreters found on Line 1.
        "shebangs": ["rustc", "cargo", "rust-script", "cargo-script", "evcxr"],
        # UPGRADED: Maps to Family 2 (Nested C)
        # Rationale: Rust explicitly allows nested block comments (/* /* */ */),
        # unlike standard C/C++. Standard C parsing would prematurely terminate here.
        "lexical_family": "recursive_block",
        "rules": {
            # --- LEXICAL DELIMITER CONTROLS ---
            # Standard C-family line comment token (Includes /// and //!)
            "_line_anchor": re.compile(r"//"),
            # Inline comments follow the same '//' delimiter.
            "_inline_comment": re.compile(r"//"),
            # REQUIRED for Family 2: Recursive logic markers
            "_block_start": re.compile(r"/\*"),
            # REQUIRED for Family 2: Recursive logic markers
            "_block_end": re.compile(r"\*/"),
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # 1. branch (Control Flow / Branching)
            # Decisions and logical jumps. EXCLUDES panic!/throw (bailout_hits).
            "branch": re.compile(r"\b(if|else|match|for|while|loop|break|continue)\b|\?|&&|\|\|"),
            # 2. args (Parameters / Coupling)
            # Parameter blocks of functions and closures. Bounded to prevent ReDoS on complex types.
            "args": re.compile(
                # =====================================================================
                # [ THE VERTICAL NESTING SHIELD (RUST) ]
                # Rust closures `impl FnOnce(i32)` introduce nested parentheses inside the
                # parameter block, instantly breaking `[^)]*`.
                # FIX: Replaced `[^)]*` with `(?:[^)(]|\([^)]*\))*` to swallow 1-level deep
                # closures and strictly removed the `+` to mathematically prevent ReDoS
                # on deeply nested Bevy ECS queries.
                # =====================================================================
                r"\bfn[ \t\n]+[a-zA-Z_]\w*(?:[ \t\n]*<[^>]*>)?[ \t\n]*\((?:[^)(]|\([^)]*\))*\)|\|[^|]*\|",
                re.M,
            ),
            # 3. linear (Sequential Boundaries)
            # Structural boundaries. EXCLUDES: Access modifiers (pub) and Immutability (const/static).
            "structural_boundaries": re.compile(
                r"\b(let|struct|enum|union|trait|impl|use|mod|type|yield|await|where|mut|ref|move|return)\b"
            ),
            # 4. func_start (Executable Logic Anchors)
            # ONLY executable logic blocks. EXCLUDES structs/traits to prevent False Positives.
            "func_start": re.compile(
                # =====================================================================
                # [ THE VERTICAL MACRO & GENERICS SHIELD ]
                # Rust functions can be preceded by multiple attribute macros (#[inline])
                # and have decoupled generics `<T>`.
                # FIX: Injected the Macro Shield `(?:#\[[^\]]*\][ \t\n]*){0,5}`, upgraded
                # modifier spaces to `[ \t\n]+`, and detached the generic stepper `(?:[ \t\n]*<[^>]*>)?`
                # so the parser can trace the name through massive vertical formatting.
                # =====================================================================
                r"^[ \t]*(?:#\[[^\]]*\][ \t\n]*){0,5}"
                r"(?:pub(?:\([^)]*\))?[ \t\n]+){0,3}"
                r"(?:(?:const|async|unsafe|extern(?:[ \t\n]+\"[^\"]*\")?)[ \t\n]+){0,3}"
                r"fn[ \t\n]+([a-zA-Z_]\w*)(?:[ \t\n]*<[^>]*>)?[ \t\n]*(?=\()",
                re.M,
            ),
            # 5. class_start (Object / Entity Declarations)
            "class_start": re.compile(
                r"^[ \t]*(?:pub(?:\([^)]*\))?[ \t]+){0,3}(?:struct|enum|union|trait)\s+[a-zA-Z_]\w*",
                re.M,
            ),
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            # 6. safety (Defensive Programming / Validation)
            "safety": re.compile(
                r"\b(Option|Result|Mutex|RwLock|Arc|Rc|Box|RefCell|match|if\s+let|while\s+let|let\s+else|Ok|Err|Some|None)\b"
            ),
            # 7. safety_neg (Safety Bypasses / Unchecked Types)
            # Actively bypasses type safety (unwraps and forced expectations).
            "safety_bypasses": re.compile(r"\b(unwrap|expect|unwrap_err|unwrap_unchecked)\b"),
            # 8. danger (High-Risk Execution / System Calls)
            # Process-killing commands. EXCLUDES TODO (debt) and println! (print_hits).
            "high_risk_execution": re.compile(r"\b(panic!|todo!|unimplemented!|process::exit|abort)\b"),
            # 9. io (I/O & Network Boundaries)
            "io": re.compile(
                r"\b(std::fs|File::|std::net|tokio::net|tokio::fs|reqwest|std::io|hyper::|sqlx::|diesel::|sea_orm::)\b"
            ),
            # 10. api (Public Surface Area)
            # Code exposed to the outside world.
            "api": re.compile(r"\bpub(?:\([^)]*\))?\b"),
            # 11. flux (State Mutation)
            # Mutation of state. EXCLUDES const (freeze_hits).
            "state_mutation": re.compile(r"\bmut\b|\.borrow_mut\(\)|\.write\(\)|Cell::|RefCell::|Atomic[A-Za-z0-9]+"),
            # 12. dead_code (Commented Logic / Deprecated Trails)
            "dead_code": re.compile(r"//[ \t]*(?:fn|let|struct|impl|mod|use|match|for|while|loop|if|return)\b"),
            # 13. doc (Structured Documentation)
            "doc": re.compile(r"///|//!|#!?\[doc\b[^\]]*\]"),
            # 14. test (Testing & Assertions)
            # Triggers indicating internal verification. Anchors standard testing macros and prevents prose collisions for BDD frameworks (rstest/spec).
            "test": re.compile(
                r"#\[(?:tokio::)?test\]|#\[cfg\(test\)\]|\b(?:assert!|assert_eq!|assert_ne!)\b|\b(?:describe|it|test)\s*\("
            ),
            # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
            # 15. concurrency (Asynchronous Execution)
            "concurrency": re.compile(
                r"\b(async|await|std::thread|spawn|tokio::spawn|mpsc::|async_trait|Future|Stream|Send|Sync)\b"
            ),
            # 16. ui_framework (UI / View Components)
            "ui_framework": re.compile(r"\b(yew::|dioxus::|iced::|html!|rsx!|view!|slint|leptos::|tauri::)\b"),
            # 17. closures (Closures / Anonymous Functions)
            "closures": re.compile(r"\|[^|]*\|[ \t]*\{"),
            # 18. globals (Global / Shared State)
            "globals": re.compile(r"\b(static\s+mut|lazy_static!|OnceCell|OnceLock|LazyLock|std::env::var)\b"),
            # 19. decorators (Decorators / Annotations)
            "decorators": re.compile(r"^[ \t]*#!?\[[^\]]*\]", re.M),
            # 20. generics (Generics / Type Parameters)
            "generics": re.compile(r"<\s*[A-Z\'][^>]*>|\bwhere\b|\'[a-z]+\b|\bimpl\s+[A-Z]\w+"),
            # 21. comprehensions (Iterators / Comprehensions)
            "comprehensions": re.compile(
                r"\.(?:map|filter|fold|collect|flat_map|any|all|reduce|for_each|find|zip)\s*\("
            ),
            # 22. scientific (Numerical / Compute Libraries)
            "scientific": re.compile(r"\b(ndarray::|nalgebra::|num::|f32|f64|std::simd)\b"),
            # 23. heat_triggers (Metaprogramming & Reflection)
            # Metaprogramming and memory transmutation.
            "reflection_metaprogramming": re.compile(r"\b(macro_rules!|std::mem::transmute|Pin::|PhantomData|UnsafeCell)\b"),
            # 24. import (Dependency Inclusions)
            "import": re.compile(r"\b(?:pub[ \t]+)?use\s+[^;]+;", re.M),
            "_dependency_capture": re.compile(
                # =====================================================================
                # [ FUTURE LLM CONTEXT: THE DYNAMIC EXECUTION SHIFT (RUST) ]
                # PURPOSE: Extracts external dependencies for the Network Graph and Supply Chain Firewall.
                #
                # HISTORICAL BUG: Originally, this regex was anchored to the start of the
                # line `^[ \t]*`. While Rust doesn't evaluate dependencies dynamically at
                # runtime like scripting languages, it heavily utilizes locally scoped imports
                # inside functions or trait implementations (e.g., `fn do_work() { use std::fs; }`).
                # The anchored regex completely missed these localized dependencies.
                #
                # THE FIX: The `^` anchor has been stripped. We now rely on the `\b` word
                # boundary to locate the `use` keyword anywhere in the file.
                #
                # [ THE COMMA-SEPARATED DESTRUCTURING SHIELD ]
                # Previously, `_dependency_capture` stopped at the first non-word character,
                # which meant for `use std::collections::{HashMap, HashSet};` it only captured
                # `std::collections`. The expanded capture group `([a-zA-Z0-9_:{},\s]+)` now
                # explicitly swallows the entire comma-separated bracket block up to the semicolon.
                # NOTE: The downstream parser MUST flatten and split this string on commas and
                # brackets to accurately register the individual nodes.
                # =====================================================================
                r"\b(?:pub[ \t]+)?use\s+([a-zA-Z0-9_:{},\s]+);",
                re.M,
            ),
            # 25. ownership (Authorship Metadata)
            "ownership": re.compile(r"//\s*(?:Author|Maintainer|Copyright):\s+(.*)", re.I),
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            # 26. planned_debt (Annotated Debt / TODOs)
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            # 29. spec_exposure (Spec / Audit Traceability)
            "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]", re.I),
            # 30. tabs_vs_spaces (Formatting Inconsistencies) 
            "tabs_vs_spaces": None,
            # 31. ssr_boundaries (Server-Side Rendering)
            "ssr_boundaries": re.compile(
                r"\b(actix_web|axum|rocket|HttpResponse|Responder|IntoResponse|Html|askama::|tera::)\b"
            ),
            # 32. events (Event Emitters / Pub-Sub)
            "events": re.compile(r"\b(tokio::sync::broadcast|std::sync::mpsc|crossbeam_channel|Sender|Receiver)\b"),
            # 33. dependency_injection (Dependency Injection / IoC)
            "dependency_injection": re.compile(
                r"\b(axum::extract::State|actix_web::web::Data|Extension|Provider|shaku::)\b"
            ),
            # 34. macros (Preprocessor Directives / Macros)
            "macros": re.compile(r"\b(macro_rules!|proc_macro|proc_macro_derive|proc_macro_attribute)\b"),
            # 35. pointers (Pointer Arithmetic / Memory Addressing)
            # Raw memory addressing. Shielded from standard multiplication by explicitly mapping to native Rust unsafe pointer primitives and dereferencing.
            "pointers": re.compile(r"\*const\b|\*mut\b|\bNonNull\b|\bstd::ptr\b|->"),
            # 36. memory_alloc (Manual Memory Management)
            "memory_alloc": re.compile(
                r"\b(Box::new|Rc::new|Arc::new|Vec::with_capacity|String::with_capacity|alloc::|GlobalAlloc)\b"
            ),
            # 37. inline_asm (The Bare Metal)
            "inline_asm": re.compile(r"\b(?:core::arch::asm!|std::arch::asm!|asm!|global_asm!)\b"),
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # 38. telemetry (Structured Logging / Telemetry)
            "telemetry": re.compile(r"\b(?:log::|tracing::)?(?:info!|warn!|error!|debug!|trace!|span!|instrument)\b"),
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
            "debug_prints": re.compile(r"\b(println!|print!|eprintln!|eprint!|dbg!)\b"),
            # # 40. explicit_casts (Explicit Type Casting)
            # Forceful type coercion bypassing the safety engine. Enforces strict mapping to the `as` keyword followed by standard primitive types.
            "explicit_casts": re.compile(
                r"\bas\s+(?:i8|i16|i32|i64|i128|isize|u8|u16|u32|u64|u128|usize|f32|f64|bool|char)\b"
            ),
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
            "panics_and_aborts": re.compile(r"\b(panic!|abort|process::exit|fatalError)\b"),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
            "thread_sleeps": re.compile(r"\b(std::thread::sleep|tokio::time::sleep|Duration::from)\b"),
            # 43. bitwise_ops (Bitwise Operations)
            # Low-level byte manipulation. CRITICAL: Removed the pipe '|' (used for closures `|x| x+1` and patterns), ampersand '&' (used for references), and exclamation '!' (used for macros and logical NOT).
            "bitwise_ops": re.compile(r"<<|>>|\^"),
            # 44. sync_locks (Resource Management & Stability)
            "sync_locks": re.compile(r"\b(Mutex|RwLock|lock|barrier|atomic|Semaphore)\b", re.I),
            # 45. immutability_locks (Immutability Constraints)
            "immutability_locks": re.compile(r"\b(const|static|immutable|readonly)\b"),
            # 46. cleanup (Resource Cleanup / Teardown)
            "cleanup": re.compile(r"\b(drop|free|delete|close|shutdown)\b\s*\("),
            # 47. encapsulation (Access Modifiers / Encapsulation)
            # Visibility variant tracking.
            "encapsulation": re.compile(r"\bpub(?:\(crate\)|\(super\)|\(self\))?\b"),
            # 48. listeners (Event Listeners / Observers)
            "listeners": re.compile(r"\.subscribe\(|\.on\(|addEventListener"),
            # 49. test_skip (Bypassed Tests / Ignored Specs)
            "test_skip": re.compile(r"#\[ignore\]|test\.skip\(|mock\(|fake\("),
            # --- PHASE 3: HYBRID DOMAIN SENSORS (Rust Specifics) ---
            "serialization_parsing": re.compile(
                r"\b(serde_json::from_str|serde_json::to_string|serde_json::from_slice|bincode::deserialize|toml::from_str)\b"
            ),
            "regex_execution": re.compile(r"\b(Regex::new)\b"),
            "time_date_logic": re.compile(
                r"\b(std::time::Duration|std::time::Instant|std::time::SystemTime|chrono::Utc::now|chrono::Local::now)\b"
            ),
            "ipc_rpc_bridges": re.compile(
                r"\b(std::process::Command|tokio::process|tonic::transport::Server|mpsc::channel)\b"
            ),
        },
    },
    "cpp": {
        "_meta": {
            "target_version": "C++23 (Modules, Concepts, Coroutines, Ranges, std::print)",
            "last_updated": "2026-02-18",
            "blueprint_version": "v5.0",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard sources, headers, template implementations, inline implementations, and legacy UNIX casing conventions.
        "extensions": [
            ".cpp",
            ".cc",
            ".cxx",
            ".c++",
            ".hpp",
            ".hh",
            ".hxx",
            ".h++",
            ".tpp",
            ".inc",
            ".inl",
            ".ipp",
            ".cp",
            ".C",
            ".H",
        ],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: Extensionless build/config scripts and tooling configs that are secretly pure code.
        "exact_matches": [],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions, package manifests, and lockfiles to resolve ambiguous files (like .h or .inc).
        "discriminators": [
            ".cpp",
            ".cc",
            ".cxx",
            "CMakeLists.txt",
            "conanfile.txt",
            "vcpkg.json",
            "Makefile",
            "BUILD.bazel",
            "WORKSPACE",
        ],
        # EXECUTION SIGNATURES: Interpreters found on Line 1.
        "shebangs": ["cling", "cint"],
        # UPGRADED: Maps to Family 1 (Standard C)
        # Rationale: Uses '//' for line-level literature; multi-line literature
        # (/* */) is handled by the Section 2.3.C.3 Heuristic Pass.
        "lexical_family": "standard_block",
        "rules": {
            # --- LEXICAL DELIMITER CONTROLS ---
            # C++ uses '//' for standard line-level Literature (Commented / Non-Executable Text).
            "_line_anchor": re.compile(r"//"),
            # Inline comments follow the standard '//' delimiter.
            "_inline_comment": re.compile(r"//"),
            # Block comment start: /* (Standard non-recursive delimiter).
            "_block_start": re.compile(r"/\*"),
            # Block comment end: */
            "_block_end": re.compile(r"\*/"),
            # 1. branch (Control Flow / Branching)
            # Control flow jumps. Includes modern coroutine jumps (co_yield, co_await).
            # EXCLUDES exceptions (bailout_hits).
            "branch": re.compile(
                r"\b(if|else|switch|case|default|for|while|do|catch|break|continue|goto|co_yield|co_await)\b|&&|\|\||\?"
            ),
            # 2. args (Parameters / Coupling)
            # Parameter blocks of functions and lambdas. Bounded to prevent ReDoS on massive signatures.
            "args": re.compile(
                r"\b[a-zA-Z_]\w*(?:::[a-zA-Z_]\w*)*(?:<[^>]*>)?\s*\(\s*(?:const\s+|volatile\s+)?(?:int|char|void|float|double|bool|long|short|unsigned|signed|struct|class|std::|[A-Z]\w*)\b[^)]*\)|\[[^\]]*\]\s*\([^)]*\)"
            ),
            # 3. linear (Sequential Boundaries)
            # Structural boundaries. EXCLUDES: Access modifiers (encapsulation) and const (freeze_hits).
            "structural_boundaries": re.compile(
                r"\b(namespace|using|class|struct|enum|union|template|typename|concept|requires|auto|return|void|inline|virtual|explicit|friend|module|export|import|typedef)\b"
            ),
            "func_start": re.compile(
                # =====================================================================
                # [ CONTEXT: C++ FUNCTION AST EXTRACTOR & REDOS SHIELD]
                # PURPOSE: Anchors executable logic blocks (methods/functions) in C++.
                # VULNERABILITY: C++ allows multi-line function signatures and complex
                #   return types (e.g., `std::vector<int> \n myFunc()`). In files with
                #   massive macro lists (like hardware register maps), the `[ \t\n]+`
                #   allowances cause catastrophic backtracking (ReDoS).
                # THE "IRON WALL" FIX: `(?![ \t]*#)` is a negative lookahead injected at
                #   high-risk multi-line boundaries. It explicitly forbids the regex engine
                #   from crossing into preprocessor directives, capping the permutation tree.
                # =====================================================================
                # 1. THE HORIZONTAL ANCHOR (Stops O(N^2) vertical spirals)
                r"^[ \t]*"
                # 2. LINKAGE & STORAGE MODIFIERS (Now supports vertical formatting)
                r"(?:(?:static|inline|extern|virtual|_Noreturn|constexpr|consteval|constinit|__inline__|__forceinline)[ \t\n]+){0,5}"
                # 3. COMPILER ATTRIBUTES PRE-TYPE (Includes C23 [[...]])
                r"(?:(?:__attribute__[ \t]*\([^)]*\)|\[\[[^\]]*\]\]|__declspec[ \t]*\([^)]*\))[ \t\n]*){0,5}"
                # 4. THE RETURN TYPE (Pointers/references explicitly bound)
                # [IRON WALL]: Prevents the engine from reading a `#define` on the next line as a return type.
                # [POINTER AMBIGUITY FIX]: Strictly enforces sequential evaluation of pointers and spaces.
                r"(?:(?:struct|union|enum)[ \t\n]+)?"
                r"(?:(?![ \t]*#)[a-zA-Z_]\w*(?:::[a-zA-Z_]\w*)*(?:<[^>]*>)?[*&]*[ \t\n]+){0,5}"
                # 5. THE "NOT A FUNCTION" SHIELD
                # Prevents control flow (if, while) and primitive types from being captured as function names.
                r"(?!(?:if|for|while|switch|return|catch|else|elif|sizeof|new|delete|ARGS\d+|NOARGS|int|float|double|char|void|long|short|unsigned|signed|bool|INTEGER|LOGICAL|real|__attribute__|__declspec|__asm__)\b)"
                # 6. THE IDENTIFIER CAPTURE (FUNCTION IDENTIFIER - GROUP 1)
                # [IRON WALL]: Ensures the actual function/operator name isn't hijacked by a macro definition.
                r"(?![ \t]*#)((?:[a-zA-Z_]\w*::)*[~a-zA-Z_]\w*|operator[ \t]*[^a-zA-Z_\s(]+|operator[ \t]+(?:new|delete)(?:\[\])?)"
                # 7. THE PARAMETER BLOCK (Supports vertical gap)
                # [NESTED PARENTHESIS FIX]: Uses 1-Level Nesting Trick to swallow function pointers without ReDoS.
                r"[ \t\n]*(?:ARGS\d+\s*\([^)]*\)|\((?:[^)(]|\([^)]*\))*\)|NOARGS)"
                # 8. POST-PARAMETER MODIFIERS & TRAILING RETURN TYPES
                # [OVERLAP PREVENTION]: Removed ambiguous \s* inside attribute matcher.
                r"(?:[ \t\n]+(?:const|volatile|noexcept|override|final|&{1,2}|__attribute__\([^)]*\)|\[\[[^\]]*\]\])){0,10}"
                r"(?:[ \t\n]*->[ \t]*[a-zA-Z_:\w*<>]+)?"
                # 9. THE K&R C AND C++ CONSTRUCTOR GAP (ReDoS mitigated via Strict Bounding)
                # Handles C++ initializer lists (e.g., `MyClass() : a(1) {`) and legacy K&R declarations.
                # [IRON WALL - CATASTROPHIC BACKTRACKING FIX]:
                # We enforce strict numeric bounds (`{0,500}` and `{0,100}`) instead of `+` or `*`.
                # This caps the permutation tree instantly.
                r"(?:[ \t\n]*(?![ \t]*#):[^{;]{0,500}|(?:[ \t\n]+(?![ \t]*#)[a-zA-Z_][^(){};]{0,100};){1,20})?"
                # 10. THE IGNITION (The opening brace confirming it is a definition, not a declaration)
                r"[ \t\n]*\{",
                re.M,
            ),
            # 5. class_start (Object / Entity Declarations)
            # =====================================================================
            # [ THE C++ ATTRIBUTE & TEMPLATE SHIELD ]
            # C++ entity declarations can be preceded by massive, multi-line templates
            # and C++20 `[[attributes]]` wedged directly before the class name.
            # FIX 1 (Negative Test): Dropped standard C-style `enum` to avoid hallucinating
            # minor constants; restricted to strongly-typed `enum class` / `enum struct`.
            # FIX 2 (Pathological): Injected `(?:\[\[[^\]]*\]\][ \t\n]*){0,5}` to step
            # over attributes, converted `\s*` to `[ \t\n]*` for the template wrapper,
            # and added the exact capture group `([a-zA-Z_]\w*)`.
            # =====================================================================
            "class_start": re.compile(
                r"^[ \t]*(?:export[ \t\n]+)?(?:template[ \t\n]*<[^>]*>[ \t\n]*)?(?:class|struct|union|enum[ \t\n]+class|enum[ \t\n]+struct)[ \t\n]+(?:\[\[[^\]]*\]\][ \t\n]*){0,5}([a-zA-Z_]\w*)",
                re.M,
            ),
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            # 6. safety (Defensive Programming / Validation)
            "safety": re.compile(
                r"\b(try|catch|finally|std::unique_ptr|std::shared_ptr|std::weak_ptr|override|final|noexcept|static_assert|assert|std::optional|std::expected|std::span|std::variant|std::lock_guard|std::atomic)\b"
            ),
            # 7. safety_neg (Safety Bypasses / Unchecked Types)
            # Swallowing errors or bypassing types. EXCLUDES standard casting (Phase 5).
            "safety_bypasses": re.compile(r"\b(std::any|void\s*\*)\b|catch\s*\(\s*\.\.\.\s*\)"),
            # 8. danger (High-Risk Execution / System Calls)
            # Process killers and low-level blits. EXCLUDES prints (Phase 5).
            "high_risk_execution": re.compile(r"\b(system|memcpy|memset|abort|exit|std::terminate|longjmp|setjmp)\b"),
            # 9. io (I/O & Network Boundaries)
            "io": re.compile(
                r"\b(std::fstream|std::ifstream|std::ofstream|std::filesystem|fopen|fclose|fread|fwrite|socket|recv|send|asio::|curl_easy_perform|std::cin)\b"
            ),
            # 10. api (Public Surface Area)
            # Code exposed to the world. Explicit visibility and module exports.
            "api": re.compile(
                r'\b(public:|export\s+module|export\s+import|export\s+class|__declspec\(dllexport\)|__attribute__\(\(visibility\("default"\)\)\))\b|^[ \t]*export\b(?!\s*module)',
                re.M,
            ),
            # 11. flux (State Mutation)
            # Mutation of state. Includes moves and increments.
            "state_mutation": re.compile(
                r"\b(mutable|std::move|std::exchange|std::swap|std::atomic)\b|(?<![=!<>])=(?![=])|&(?!\s*const)|\+\+|--|(?:\+=|-=|\*=|/=|%=|<<=|>>=|&=|\|=|\^=)"
            ),
            # 12. dead_code (Commented Logic / Deprecated Trails)
            # Commented-out execution logic indicating dead features. MUST enforce that the structural keyword immediately follows the comment token.
            "dead_code": re.compile(
                r"//[ \t]*(?:if|for|while|auto|class|struct|std::cout|std::print|printf|void|int|return)\b"
            ),
            # 13. doc (Structured Documentation)
            "doc": re.compile(
                r"///|/\*\*|@param|@return|@brief|@details|@tparam|\\param|\\return|\\brief|\\details|\\tparam"
            ),
            # 14. test (Testing & Assertions)
            # Triggers indicating internal verification. Anchors explicit GTest/Catch2 macros and prevents prose collisions.
            "test": re.compile(
                r"\b(?:TEST|TEST_F|TEST_CASE|SECTION|REQUIRE|CHECK|EXPECT_[A-Z_]+|ASSERT_[A-Z_]+|Catch::|GTest)\b"
            ),
            # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
            # 15. concurrency (Asynchronous Execution)
            "concurrency": re.compile(
                r"\b(std::thread|std::jthread|std::mutex|std::future|std::promise|std::async|std::latch|std::barrier|std::condition_variable|std::semaphore|co_await|std::coroutine_handle)\b"
            ),
            # 16. ui_framework (UI / View Components)
            "ui_framework": re.compile(r"\b(Q_OBJECT|slots:|signals:|QWidget|wxFrame|ImGui::|Fl_Window)\b"),
            # 17. closures (Closures / Anonymous Functions)
            "closures": re.compile(
                r"\[[^\]]*\]\s*(?:<[^>]*>\s*)?(?:\([^)]*\))?\s*(?:(?:mutable|constexpr|consteval|noexcept)\s+)*(?:mutable|constexpr|consteval|noexcept)?\s*(?:->\s*[\w:<>_]+)?[ \t]*\{"
            ),
            # 18. globals (Global / Shared State)
            "globals": re.compile(
                r"\b(extern|static(?!\s*assert)|thread_local|inline\s+constexpr)\b|^[ \t]*(?:static|extern)\s+[\w:<>_]+\s+[a-zA-Z_]\w*[ \t]*=",
                re.M,
            ),
            # 19. decorators (Decorators / Annotations)
            "decorators": re.compile(r"\[\[\s*[a-zA-Z_:][^\]]*\]\]"),
            # 20. generics (Generics / Type Parameters)
            "generics": re.compile(r"\btemplate\s*<[^>]*>|\b(?:concept|requires)\b"),
            # 21. comprehensions (Iterators / Comprehensions)
            # Range pipelines acting as functional mappers.
            "comprehensions": re.compile(
                r"\b(std::ranges::|std::views::|views::|std::transform|std::accumulate|std::reduce|std::for_each|std::filter)\b|\|\s*std::views::"
            ),
            # 22. scientific (Numerical / Compute Libraries)
            "scientific": re.compile(
                r"\b(std::cmath|std::complex|std::linalg|std::mdspan|Eigen::|blaze::|std::simd|__m128|__m256|__m512|std::numbers::)\b"
            ),
            # 23. heat_triggers (Metaprogramming & Reflection)
            # SFINAE, compile-time reflection, and macros.
            "reflection_metaprogramming": re.compile(
                r"\b(if\s+constexpr|if\s+consteval|std::enable_if|std::is_same|std::any_cast|std::bit_cast|decltype|sizeof\.\.\.)\b|#define\s+[a-zA-Z_]"
            ),
            # 24. import (Dependency Inclusions)
            "import": re.compile(
                r'^[ \t]*(?:#include\s*[<"][^>"]+[>"]|import\s+[a-zA-Z_][\w.:]*\s*;|export\s+import\s+[a-zA-Z_][\w.:]*\s*;)',
                re.M,
            ),
            "_dependency_capture": re.compile(
                r'^[ \t]*(?:#\s*include\s*[<"]([^>"]+)[>"]|(?:export\s+)?import\s+([a-zA-Z_][\w.:]*)\s*;)',
                re.M,
            ),
            # 25. ownership (Authorship Metadata)
            "ownership": re.compile(r"(?:@author|\\author|Author:|Created by:|Copyright)\s+(.*)", re.I),
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            # 26. planned_debt (Annotated Debt / TODOs)
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            # 29. spec_exposure (Spec / Audit Traceability)
            "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]", re.I),
            # 30. tabs_vs_spaces (Formatting Inconsistencies) 
            "tabs_vs_spaces": None,
            # 31. ssr_boundaries (Server-Side Rendering)
            "ssr_boundaries": re.compile(r"\b(FCGI_Accept|render_template|Inja::|ctemplate::)\b"),
            # 32. events (Event Emitters / Pub-Sub)
            "events": re.compile(r"\b(emit|signal|slot|notify|publish|subscribe|boost::signals2)\b"),
            # 33. dependency_injection (Dependency Injection / IoC)
            "dependency_injection": re.compile(r"\b(boost\.di|fruit::|[I]nject|IServiceCollection)\b"),
            # 34. macros (Preprocessor Directives / Macros)
            "macros": re.compile(
                r"^[ \t]*#(?:define|undef|if|elif|else|endif|pragma|warning|error)\b",
                re.M,
            ),
            # 35. pointers (Pointer Arithmetic / Memory Addressing)
            # Raw memory addressing and pointer manipulation. CRITICAL: Uses lookbehinds `(?<=[=\s,(])` to strictly capture pointer dereferences `*ptr` and memory addresses `&var` without flagging standard multiplication `a * b` or logical AND `a & b`.
            "pointers": re.compile(
                r"->|\b(?:uintptr_t|intptr_t|ptrdiff_t|size_t)\b|(?<=[=\s,(])&\w+|(?<=[=\s,(])\*(?:\s*const\s*)?\w+"
            ),
            # 36. memory_alloc (Manual Memory Management)
            "memory_alloc": re.compile(r"\b(new|malloc|calloc|realloc|aligned_alloc|mmap|alloca)\b"),
            # 37. inline_asm (The Bare Metal)
            "inline_asm": re.compile(
                r"\b(?:__asm__|asm|__asm)\b(?:\s+(?:volatile|__volatile__))?\s*\(|\b(?:__asm__|asm|__asm)\b[ \t]*\{"
            ),
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # 38. telemetry (Structured Logging / Telemetry)
            "telemetry": re.compile(r"\b(log|logger|LOGGER|spdlog|glog|syslog)\.(?:info|error|warn|debug|trace)\b"),
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
            "debug_prints": re.compile(
                r"\b(std::cout|std::cerr|std::clog|printf|fprintf|vprintf|puts|putchar|std::print|std::println)\b"
            ),
            # # 40. explicit_casts (Explicit Type Casting)
            # Forceful type coercion bypassing the safety engine. Captures modern explicitly named casts and strict C-style groupings.
            "explicit_casts": re.compile(
                r"\b(?:static_cast|dynamic_cast|reinterpret_cast|const_cast|bit_cast)\b|<\s*[A-Za-z_]\w*\s*>|\(\s*(?:int|float|double|char|bool|long|short|unsigned|signed)\s*\)\s*[a-zA-Z_]"
            ),
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
            "panics_and_aborts": re.compile(r"\b(throw|abort|exit|_Exit|quick_exit|std::terminate|longjmp)\b"),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
            # Admission of race conditions or lazy polling.
            "thread_sleeps": re.compile(r"\b(sleep|delay|usleep|nanosleep|std::this_thread::sleep_for)\b"),
            # 43. bitwise_ops (Bitwise Operations)
            # Low-level byte manipulation. CRITICAL: Removed bare `<<` and `>>` to prevent catastrophic false positives on `std::cout` and `std::cin` streams. Explicit bitwise assignments (`<<=`, `&=`) are retained as they are unambiguous.
            "bitwise_ops": re.compile(r"\^|(?<![=!])~|<<=|>>=|&=|\|=|\^="),
            # 44. sync_locks (Resource Management & Stability)
            "sync_locks": re.compile(
                r"\b(mutex|lock|synchronized|Semaphore|std::lock_guard|std::scoped_lock|std::unique_lock|mtx_lock)\b",
                re.I,
            ),
            # 45. immutability_locks (Immutability Constraints)
            "immutability_locks": re.compile(r"\b(const|constexpr|consteval|constinit|final|readonly|Immutable)\b"),
            # 46. cleanup (Resource Cleanup / Teardown)
            "cleanup": re.compile(r"\b(delete|free|close|fclose|dispose|shutdown|std::destroy|reset)\b\s*\("),
            # 47. encapsulation (Access Modifiers / Encapsulation)
            "encapsulation": re.compile(r"\b(private:|protected:|internal:)\b"),
            # 48. listeners (Event Listeners / Observers)
            "listeners": re.compile(r"\b(on|addEventListener|subscribe|connect|handler|callback)\b"),
            # 49. test_skip (Bypassed Tests / Ignored Specs)
            "test_skip": re.compile(r"\b(GTEST_SKIP|test\.skip|it\.skip|mock\(|fake\()\b"),
            # --- PHASE 3: HYBRID DOMAIN SENSORS (C++ Specifics) ---
            "serialization_parsing": re.compile(
                r"\b(nlohmann::json|rapidjson|boost::archive|ParseFromString|SerializeToString)\b"
            ),
            "regex_execution": re.compile(r"\b(std::regex|std::regex_match|std::regex_search|std::regex_replace)\b"),
            "time_date_logic": re.compile(
                r"\b(std::chrono::(?:system_clock|steady_clock|duration)|std::time_t|std::localtime)\b"
            ),
            "ipc_rpc_bridges": re.compile(r"\b(boost::interprocess|mmap|shm_open|pipe|fork|grpc::ServerBuilder)\b"),
        },
    },
    "c": {
        "_meta": {
            "target_version": "C23 (ISO/IEC 9899:2024 - constexpr, #embed, [[attributes]], nullptr, typeof)",
            "last_updated": "2026-02-18",
            "blueprint_version": "v5.0",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard sources, headers, OpenCL kernels, Yacc grammars, and C-like scripting/ATS language files.
        # THE FIX: Added .dts and .dtsi (Device Tree Source) to parse hardware maps.
        "extensions": [
            ".c",
            ".h",
            ".cl",
            ".inc",
            ".y",
            ".idc",
            ".cats",
            ".dts",
            ".dtsi",
        ],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: Extensionless build/config scripts and tooling configs that are secretly pure code.
        "exact_matches": [],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions, package manifests, and lockfiles to resolve ambiguous files (like .h or .inc).
        "discriminators": [
            ".c",
            "Makefile",
            "configure.ac",
            "configure.in",
            "configure",
            "CMakeLists.txt",
            "Kconfig",
        ],
        # EXECUTION SIGNATURES: Interpreters found on Line 1.
        "shebangs": ["tcc", "picoc", "cscript"],
        # UPGRADED: Maps to Family 1 (Standard C)
        # Rationale: Uses '//' for line-level literature; multi-line literature
        # (/* */) is handled by the Section 2.3.C.3 Heuristic Pass.
        "lexical_family": "standard_block",
        "rules": {
            # --- LEXICAL DELIMITER CONTROLS ---
            # Modern C (C99+) uses '//' for standard line-level Commented / Non-Executable Text.
            "_line_anchor": re.compile(r"//"),
            # Inline comments follow the standard '//' delimiter.
            "_inline_comment": re.compile(r"//"),
            # Block comment start: /* (The primary literature delimiter for all C eras).
            "_block_start": re.compile(r"/\*"),
            # Block comment end: */
            "_block_end": re.compile(r"\*/"),
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # 1. branch (Control Flow / Branching)
            # Decisions and jumps. EXCLUDES exit/abort (bailout_hits).
            "branch": re.compile(r"\b(if|else|switch|case|default|for|while|do|break|continue|goto)\b|&&|\|\||\?"),
            # 2. args (Parameters / Coupling)
            # Parameter blocks. Bounded negation [^)]* to prevent ReDoS on massive param lists.
            "args": re.compile(
                # =====================================================================
                # [ THE NESTED POINTER SHIELD (C) ]
                # Standard parameter capture `[^)]*` fails instantly on function pointers
                # like `void (*cb)(int)`.
                # FIX: Replaced `[^)]*` with the 1-Level Nesting Trick `(?:[^)(]+|\([^)]*\))*`
                # to safely swallow function pointer parameters without triggering ReDoS.
                # Upgraded horizontal `[ \t*]*` to `[ \t\n*]*` to support vertical signatures.
                # =====================================================================
                r"(?!(?:if|for|while|switch|return)\b)\b[a-zA-Z_]\w*[ \t\n*]*\(\s*(?:const\s+|volatile\s+)?(?:int|char|void|float|double|long|short|unsigned|signed|struct|enum)\b(?:[^)(]|\([^)]*\))*\)",
                re.M,
            ),
            # 3. linear (Sequential Boundaries)
            # Structural boundaries. EXCLUDES: Access modifiers (encapsulation) and const (freeze_hits).
            "structural_boundaries": re.compile(
                r"\b(struct|union|enum|typedef|return|void|restrict|auto|bool|true|false|_BitInt|alignas|alignof)\b"
            ),
            "func_start": re.compile(
                # =====================================================================
                # [ CRITICAL ROADMAP FOR FUTURE LLMs & MAINTAINERS: THE REDOS IRON WALL ]
                # PURPOSE: Anchors executable logic blocks (functions) in C.
                #
                # 1. THE K&R AMBIGUITY TRAP (The Original Fix):
                #    The engine was consuming `BEGIN` as a parameter type (e.g. `BEGIN i;`).
                #    When it failed to find a semicolon, it backtracked through 15 loops of
                #    whitespace combinations causing 34-second ReDoS hangs.
                #    RULE: The K&R gap MUST use `(?!(?:BEGIN...)\b)[a-zA-Z_]` to instantly reject.
                #    RULE: NO OVERLAPPING WHITESPACE: `\s+` exclusively owns all spaces.
                #
                # 2. [ THE COMPILER ATTRIBUTE SHIELD ] (Hard-learned from Pathological Fuzzer):
                #    Kernel and embedded C code frequently stack `__attribute__((...))`
                #    definitions across multiple vertical lines before the function signature.
                #    FIX: Injected a dedicated, bounded `__attribute__` scanner `(?:__attribute__\s*\([^)]*\)\s*){0,5}`
                #    at the start of the pipeline. This explicitly permits multi-line `\s*` traversal
                #    without triggering Catastrophic Backtracking against the modifiers.
                # =====================================================================
                # 1. The Horizontal Anchor
                r"^[ \t]*"
                # [ THE COMPILER ATTRIBUTE SHIELD ]: Safely consumes GCC/Clang attributes across newlines.
                r"(?:__attribute__\s*\([^)]*\)\s*){0,5}"
                # 2. Modifiers (Strictly bounded)
                r"(?:(?:static|inline|extern|_Noreturn|__inline__|__forceinline|constexpr)\s+){0,3}"
                # 3. Complex types
                r"(?:(?:struct|union|enum)\s+)?"
                # 4. Return type (Strictly linear)
                r"(?:[a-zA-Z_]\w+\s+){0,3}[a-zA-Z_]\w*(?:\s*[*&]+\s*|\s+)"
                # 5. The "Not a Function" Shield
                r"(?!(?:if|for|while|switch|return|sizeof)\b)"
                # 6. The Identifier Capture (Satellite Name - Group 1)
                r"([a-zA-Z_]\w*)"
                # 7. The Parameter Block
                r"\s*\([^)]*\)"
                # 8. The K&R C Parameter Gap (Legacy support for DOOM/MS-DOS)
                # [IRON WALL FIX]: Forces instant failure if it encounters BEGIN or control flow.
                r"(?:\s+(?!(?:BEGIN|if|for|while|switch|return)\b)[a-zA-Z_][^;{]{0,150};){0,15}"
                # 9. The Ignition (Includes the MS-DOS 'BEGIN' macro)
                r"\s*(?:\{|BEGIN\b)",
                re.M,
            ),
            # 5. class_start (Object / Entity Declarations)
            # C uses structs/unions/enums as the primary entity entities.
            "class_start": re.compile(r"^[ \t]*(?:typedef[ \t]+)?(?:struct|union|enum)\s+[a-zA-Z_]\w*", re.M),
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            # 6. safety (Defensive Programming / Validation)
            "safety": re.compile(
                r"\b(assert|static_assert|_Static_assert|size_t|snprintf|strncat|strncpy|calloc|nullptr|unreachable|ckd_add|ckd_sub|ckd_mul)\b"
            ),
            # 7. safety_neg (Safety Bypasses / Unchecked Types)
            # Dangerous legacy functions and raw void manipulation.
            "safety_bypasses": re.compile(r"\b(strcpy|strcat|sprintf|gets|alloca)\b|\([a-zA-Z_]\w*\s*\*\)\s*[a-zA-Z_]\w*"),
            # 8. danger (High-Risk Execution / System Calls)
            # Process killers and context switches. EXCLUDES prints (Phase 5).
            "high_risk_execution": re.compile(r"\b(system|popen|execl|execv|fork|longjmp|setjmp)\b"),
            # 9. io (I/O & Network Boundaries)
            "io": re.compile(
                r"\b(fopen|fclose|fread|fwrite|fscanf|sscanf|socket|recv|send|open|read|write|close|stat|fseek|remove|rename)\b"
            ),
            # 10. api (Public Surface Area)
            # Linker-visible global exports.
            "api": re.compile(
                # =====================================================================
                # [ROADMAP: AMBIGUITY OVERLAP AVOIDANCE]
                # Previously used `[ \t*]+` between words. If a string failed to match,
                # the engine backtracked to see if it should assign spaces to the left
                # word, right word, or the wildcard.
                # FIX: We now use strict O(1) alternation `(?:\s*[*&]+\s*|\s+)` which
                # forces the engine to choose exactly one path and never backtrack.
                # =====================================================================
                r'\b(extern|__declspec\(dllexport\)|__attribute__\(\(visibility\("default"\)\)\))\b|'
                r"^[ \t]*(?!static\b)[a-zA-Z_]\w*(?:\s*[*&]+\s*|\s+)[a-zA-Z_]\w*(?:\[[^\]]*\])?\s*=?|"
                r"^[ \t]*[a-zA-Z_]\w*(?:\s*[*&]+\s*|\s+)[a-zA-Z_]\w*\s*\([^)]*\)\s*;",
                re.M,
            ),
            # 11. flux (State Mutation)
            # Mutation of state. EXCLUDES const/constexpr (freeze_hits).
            "state_mutation": re.compile(r"(?<![=!<>])=(?![=])|\*(?!\s*const)\w+[ \t]*=|(?:\+\+|--)"),
            # 12. dead_code (Commented Logic / Deprecated Trails)
            "dead_code": re.compile(r"(?://|/\*)[ \t]*(?:if|for|while|struct|union|enum|void|int|return)\b"),
            # 13. doc (Structured Documentation)
            "doc": re.compile(r"///|/\*\*|@param|@return|@brief|@details|\\param|\\return|\\brief|\\details"),
            # 14. test (Testing & Assertions)
            "test": re.compile(
                r"\b(?:TEST|TEST_F|TEST_CASE|CU_ASSERT|RUN_TEST|EXPECT_[A-Z_]+|ASSERT_[A-Z_]+)\b|\bassert\s*\("
            ),
            # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
            # 15. concurrency (Asynchronous Execution)
            "concurrency": re.compile(
                r"\b(thrd_create|thrd_join|mtx_lock|pthread_create|pthread_mutex_lock|atomic_int|_Atomic|memory_order_[a-z]+|thread_local)\b"
            ),
            # 16. ui_framework (UI / View Components)
            "ui_framework": re.compile(
                r"\b(GtkWidget|CreateWindow|MessageBox|XOpenDisplay|gtk_window_new|Fl_Window|initscr|wprintw)\b"
            ),
            # 17. closures
            "closures": None,  # Strict C23 lacks native closures (blocks are non-standard).
            # 18. globals (Global / Shared State)
            "globals": re.compile(
                # =====================================================================
                # [ROADMAP: AMBIGUITY OVERLAP AVOIDANCE]
                # Same strict O(1) alternation fix applied here as in the `api` rule
                # to prevent exponential space/asterisk evaluation.
                # =====================================================================
                r"^[ \t]*(?:static\s+|extern[ \t]+)?[a-zA-Z_]\w*(?:\s*[*&]+\s*|\s+)[a-zA-Z_]\w*(?:\[[^\]]*\])?\s*=(?![ \t]*==)",
                re.M,
            ),
            # 19. decorators (Decorators / Annotations)
            "decorators": re.compile(r"\[\[\s*[a-zA-Z_:][^\]]*\s*\]\]"),
            # 20. generics (Generics / Type Parameters)
            "generics": re.compile(r"\b_Generic\s*\([^)]*\)"),
            # 21. comprehensions
            "comprehensions": None,
            # 22. scientific (Numerical / Compute Libraries)
            "scientific": re.compile(
                r"\b(math\.h|tgmath\.h|complex\.h|cblas_|dgemm|sin|cos|tan|exp|log|sqrt|complex|I|_Float\d+|__m\d+)\b"
            ),
            # 23. heat_triggers (Metaprogramming & Reflection)
            # Macros with args and unstructured jumps.
            "reflection_metaprogramming": re.compile(r"^#\s*define\s+[a-zA-Z_]\w*\([^)]*\)|\bgoto\b", re.M),
            # 24. import (Dependency Inclusions)
            "import": re.compile(r'^[ \t]*#[ \t]*(?:include|embed)\s*[<"][^>"]+[>"]', re.M),
            "_dependency_capture": re.compile(r'^[ \t]*#[ \t\n]*(?:include|embed)[ \t\n]*[<"]([^>"]+)[>"]', re.M),
            # 25. ownership (Authorship Metadata)
            "ownership": re.compile(r"(?:@author|\\author|Author:|Created by:|Copyright)\s+(.*)", re.I),
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            # 26. planned_debt (Annotated Debt / TODOs)
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            # 29. spec_exposure (Spec / Audit Traceability)
            "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]", re.I),
            # 30. tabs_vs_spaces (Formatting Inconsistencies) 
            "tabs_vs_spaces": None,
            # 31. ssr_boundaries (Server-Side Rendering)
            "ssr_boundaries": re.compile(r"\b(FCGI_Accept|khttp_parse|MHD_start_daemon|facil\.io)\b"),
            # 32. events (Event Emitters / Pub-Sub)
            "events": re.compile(r"\b(epoll_wait|epoll_ctl|kqueue|kevent|select|poll|libev|libuv)\b"),
            # 33. dependency_injection (Dependency Injection / IoC)
            "dependency_injection": re.compile(r"\b(plugin_register|vtable|struct\s+[a-zA-Z_]\w*_ops)\b"),
            # 34. macros (Preprocessor Directives / Macros)
            "macros": re.compile(
                r"^[ \t]*#[ \t]*(?:define|undef|if|elif|else|endif|pragma|warning|error)\b",
                re.M,
            ),
            # 35. pointers (Pointer Arithmetic / Memory Addressing)
            "pointers": re.compile(
                r"->|\b(?:uintptr_t|intptr_t|ptrdiff_t|size_t)\b|(?<=[=\s,(])&\w+|(?<=[=\s,(])\*(?:\s*const\s*)?\w+"
            ),
            # 36. memory_alloc (Manual Memory Management)
            "memory_alloc": re.compile(r"\b(malloc|calloc|realloc|free|aligned_alloc|mmap|alloca)\b"),
            # 37. inline_asm (The Bare Metal)
            "inline_asm": re.compile(
                r"\b(?:__asm__|asm|__asm)\b(?:\s+(?:volatile|__volatile__))?\s*\(|\b(?:__asm__|asm|__asm)\b[ \t]*\{"
            ),
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # 38. telemetry (Structured Logging / Telemetry)
            "telemetry": re.compile(r"\b(?:syslog|openlog|log_info|log_error|log_warn|log_debug|vsyslog)\b"),
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
            "debug_prints": re.compile(r"\b(printf|fprintf|vprintf|puts|putchar|perror)\b"),
            # # 40. explicit_casts (Explicit Type Casting)
            "explicit_casts": re.compile(
                # =====================================================================
                # [ROADMAP: NESTED OPTIONAL SPACES (ReDoS TRAP)]
                # FIX 2: `\s*[*]*\s*` is highly vulnerable to ReDoS if the payload 
                # is spaced asterisks like `(int * * *)`. Flattened to strictly linear
                # `[ \t\n]*(?:\*[ \t\n]*)*` to prevent any overlapping whitespace matching.
                # =====================================================================
                r"\(\s*(?:int|float|double|char|bool|long|short|unsigned|signed|void)[ \t\n]*(?:\*[ \t\n]*)*\)\s*[a-zA-Z_]"
            ),
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
            "panics_and_aborts": re.compile(r"\b(abort|exit|_Exit|quick_exit|return\s+-1)\b"),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
            "thread_sleeps": re.compile(r"\b(sleep|usleep|nanosleep|thrd_sleep)\b"),
            # 43. bitwise_ops (Bitwise Operations)
            "bitwise_ops": re.compile(r"<<|>>|\^|(?<![=!])~|<<=|>>=|&=|\|=|\^="),
            # 44. sync_locks (Resource Management & Stability)
            "sync_locks": re.compile(
                r"\b(mtx_lock|mtx_unlock|pthread_mutex_lock|atomic_flag_test_and_set|atomic_store)\b"
            ),
            # 45. immutability_locks (Immutability Constraints)
            "immutability_locks": re.compile(r"\b(const|constexpr|alignas|restrict)\b"),
            # 46. cleanup (Resource Cleanup / Teardown)
            "cleanup": re.compile(r"\b(free|fclose|close|munmap|destroy|shutdown)\b\s*\("),
            # 47. encapsulation (Access Modifiers / Encapsulation)
            # Physical Reality: Static functions/variables are internal/private to the translation unit.
            "encapsulation": re.compile(r"^[ \t]*static\b", re.M),
            # 48. listeners (Event Listeners / Observers)
            "listeners": re.compile(r"\b(on_event|handler|callback|signal\(|sigaction\()"),
            # 49. test_skip (Bypassed Tests / Ignored Specs)
            "test_skip": re.compile(r"\b(IGNORE_TEST|test\.skip|mock\(|fake\()\b"),
            # --- PHASE 3: HYBRID DOMAIN SENSORS (C Specifics) ---
            "serialization_parsing": re.compile(r"\b(cJSON_Parse|json_loads|xmlReadMemory|xmlParseFile|jansson)\b"),
            "regex_execution": re.compile(r"\b(regcomp|regexec|regfree)\b"),
            "time_date_logic": re.compile(r"\b(time_t|clock_gettime|gettimeofday|localtime_r?|strftime)\b"),
            "ipc_rpc_bridges": re.compile(r"\b(fork|pipe|shmget|shmat|mmap|socket|bind|listen|accept)\b"),
        },
    },
    "php": {
        "_meta": {
            "target_version": "PHP 8.5.x / Modern Laravel 11+, Symfony 7+, & PSR-12 Paradigms",
            "last_updated": "2026-02-18",
            "blueprint_version": "v5.0",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Merged standard suffixes, legacy formats, UI templates (.phtml, .ctp), and CMS "unparsable artifacts" (.module, .inc).
        "extensions": [
            ".php",
            ".phtml",
            ".php3",
            ".php4",
            ".php5",
            ".php7",
            ".php8",
            ".phps",
            ".ctp",
            ".module",
            ".inc",
            ".theme",
            ".install",
            ".profile",
            ".engine",
            ".aw",
        ],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: Extensionless framework CLI entry points that are secretly pure PHP code.
        "exact_matches": ["artisan", "composer.phar", "drush", "wp-cli", "phpunit"],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions, package manifests, and lockfiles to resolve ambiguous files (like .inc).
        "discriminators": [
            ".php",
            "composer.json",
            "composer.lock",
            "phpunit.xml",
            "phpunit.xml.dist",
            "phpcs.xml",
            ".php_cs",
            ".php_cs.dist",
        ],
        # EXECUTION SIGNATURES: Interpreters found on Line 1.
        "shebangs": ["php", "php-cli", "php-cgi", "hhvm"],
        # UPGRADED: Maps to Family 6 (Polyglot)
        # Rationale: PHP fundamentally operates within an HTML context, requiring the parser
        # to explicitly hunt for <?php execution boundaries. It also supports multiple
        # comment styles (//, #, and /* */).
        "lexical_family": "standard_block",
        "rules": {
            # --- LEXICAL DELIMITER CONTROLS ---
            # PHP supports both '//' and '#' for line-level Commented / Non-Executable Text.
            "_line_anchor": re.compile(r"//|#"),
            # Inline comments follow the same dual-token logic.
            "_inline_comment": re.compile(r"//|#"),
            # Block comment start: /* '_block_start': re.compile(r'/\*'),
            # Block comment end: */
            "_block_end": re.compile(r"\*/"),
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # 1. branch (Control Flow / Branching)
            # Control flow. Includes modern match expression. EXCLUDES throw (bailout_hits).
            "branch": re.compile(
                r"\b(if|else|elseif|switch|case|default|foreach|for|while|do|try|catch|finally|break|continue|match|goto)\b|&&|\|\||\?\?|\?"
            ),
            # 2. args (Parameters / Coupling)
            # Signatures for functions and arrow functions. Bounded to prevent ReDoS.
            "args": re.compile(
                r"\b(?:function|fn)\s*(?:&\s*)?[a-zA-Z_\x80-\xff][a-zA-Z0-9_\x80-\xff]*\s*\([^)]*\)|\bfunction\s*\([^)]*\)|fn\s*\([^)]*\)[ \t]*=>",
                re.M,
            ),
            # 3. linear (Sequential Boundaries)
            # Structural boundaries. EXCLUDES: Access modifiers (encapsulation) and const/readonly (freeze_hits).
            "structural_boundaries": re.compile(
                r"\b(namespace|use|class|interface|trait|enum|function|return|yield|declare|require|require_once|include|include_once|as|implements|extends|clone|new)\b"
            ),
            "func_start": re.compile(
                r"(?:^|[^a-zA-Z0-9_])(?:#\[[^\]]*\][ \t]*){0,5}"
                r"(?:(?:public(?:\s*\(\s*set\s*\))?|protected(?:\s*\(\s*set\s*\))?|private(?:\s*\(\s*set\s*\))?|static|final|abstract|readonly)[ \t]+){0,5}"
                r"function\s+(?:&\s*)?([a-zA-Z_\x80-\xff][a-zA-Z0-9_\x80-\xff]*)(?=\s*\()",
                re.M,
            ),
            "class_start": re.compile(
                r"^[ \t]*(?:#\[[^\]]*\][ \t]*){0,5}(?:(?:abstract|final|readonly)[ \t]+){0,3}(?:class|interface|trait|enum)\s+([a-zA-Z_\x80-\xff][a-zA-Z0-9_\x80-\xff]*)(?:\s+(?:extends|implements)\s+([a-zA-Z_\x80-\xff][a-zA-Z0-9_\x80-\xff\\]*))?",
                re.M,
            ),
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            # 6. safety (Defensive Programming / Validation)
            "safety": re.compile(
                r"\b(try|catch|finally|declare\s*\(\s*strict_types[ \t]*=\s*1\s*\)|readonly|Throwable|Exception|assert|isset|empty|is_null|instanceof)\b|\?\?|\?->|#\[Override\]"
            ),
            # 7. safety_neg (Safety Bypasses / Unchecked Types)
            # Error suppression, dangerous eval, and loose equality.
            "safety_bypasses": re.compile(
                r"@(?:[a-zA-Z_\x80-\xff])|\b(unserialize|extract|parse_str|phpinfo)\b|error_reporting\s*\(\s*0\s*\)|==(?!=)|!=(?!=)"
            ),
            # 8. danger (High-Risk Execution / System Calls)
            # Shell execution and process killers. EXCLUDES prints (Phase 5).
            "high_risk_execution": re.compile(r"\b(exec|shell_exec|system|passthru|proc_open|popen)\b|`[^`]+`"),
            # 9. io (I/O & Network Boundaries)
            "io": re.compile(
                r"\b(fopen|fread|fwrite|file_get_contents|file_put_contents|PDO|mysqli|curl_exec|socket|header|setcookie)\b|\$_(?:GET|POST|FILES|REQUEST|COOKIE)"
            ),
            # 10. api (Public Surface Area)
            # Exposed surface. Explicit public markers + attribute routes.
            "api": re.compile(r"\b(public)\b|#\[(?:ApiResource|Route|Get|Post|Put|Delete|Patch)[^\]]*\]"),
            # 11. flux (State Mutation)
            # Mutation of state. Variable reassignments and array mutators.
            "state_mutation": re.compile(
                r"\$[a-zA-Z_\x80-\xff][a-zA-Z0-9_\x80-\xff]*\s*(?:[-+*./%&|])?=|&\$|\bglobal\s+\$|(?:\w+)?(?:->|::)[a-zA-Z_\x80-\xff][a-zA-Z0-9_\x80-\xff]*[ \t]*=|array_(?:push|pop|shift|unshift|splice)\b|(?:\+\+|--)"
            ),
            # 12. dead_code (Commented Logic / Deprecated Trails)
            "dead_code": re.compile(
                r"//\s*[;{}]|/\*\s*(?:function|class|namespace|use|if|foreach)\s|#\s*\$|//\s*(?:echo|print|\$|return|var_dump)"
            ),
            # 13. doc (Structured Documentation)
            "doc": re.compile(r"/\*\*|@param|@return|@throws|@var|@deprecated|@property|@method"),
            # 14. test (Testing & Assertions)
            "test": re.compile(
                r"\b(PHPUnit|TestCase|assertSame|assertEquals|assertTrue|assertFalse|mock|spy|expects|toBe|test|it)\b|#\[Test\]"
            ),
            # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
            # 15. concurrency (Asynchronous Execution)
            "concurrency": re.compile(
                r"\b(Fiber|yield|Swoole|React\\|Amp\\|Coroutine|go\(|await|suspend|resume|pcntl_fork)\b"
            ),
            # 16. ui_framework (UI / View Components)
            "ui_framework": re.compile(
                r'\b(view\s*\(|render\s*\(|renderView|extends\s+Controller|Blade::|Twig\\Environment)\b|@(?:if|foreach|yield|section|extends)\b|<\?=|echo\s+[\'"]<|\{\{[^}]*\}\}|\{%\s*[^%]*\s*%\}'
            ),
            # 17. closures (Closures / Anonymous Functions)
            "closures": re.compile(r"\b(?:function\s*\([^)]*\)\s*(?:use\s*\([^)]*\)\s*)?\{|fn\s*\([^)]*\)[ \t]*=>)"),
            # 18. globals (Global / Shared State)
            "globals": re.compile(r"\b(\$_SERVER|\$_SESSION|\$_ENV|\$GLOBALS)\b|\bglobal\s+\$"),
            # 19. decorators (Decorators / Annotations)
            "decorators": re.compile(r"#\[\s*[a-zA-Z0-9_:\\]+[^\]]*\]", re.M),
            # 20. generics (Generics / Type Parameters)
            # Simulated/Docblock generics.
            "generics": re.compile(
                r"@(?:template|implements|extends|use)\s+[a-zA-Z0-9_\\]+(?:<[^>]*>)?|\b(?:array|iterable|Collection)<[^>]*>"
            ),
            # 21. comprehensions (Iterators / Comprehensions)
            "comprehensions": re.compile(
                r"\b(array_map|array_filter|array_reduce|array_walk|array_column|array_find|array_any|array_all)\b"
            ),
            # 22. scientific (Numerical / Compute Libraries)
            "scientific": re.compile(r"\b(bcadd|bcsub|bcmul|bcdiv|gmp_add|gmp_mul|abs|cos|sin|tan|sqrt|log|exp|pow)\b"),
            # 23. heat_triggers (Metaprogramming & Reflection)
            # Magic methods, reflection, and variable variables.
            "reflection_metaprogramming": re.compile(
                r"\b(__(?:get|set|call|callStatic|invoke|destruct|clone)|Reflection(?:Class|Method|Property)|call_user_func(?:_array)?)\b|\$\$[a-zA-Z_\x80-\xff]"
            ),
            # 24. import (Dependency Inclusions)
            "import": re.compile(
                r"\b(?:use\s+(?:function|const[ \t]+)?[\w\\]+|require|include|require_once|include_once)\b",
                re.M,
            ),
            "_dependency_capture": re.compile(
                # =====================================================================
                # [ FUTURE LLM CONTEXT: THE DYNAMIC EXECUTION SHIFT (PHP) ]
                # PURPOSE: Extracts external dependencies for the Network Graph and Supply Chain Firewall.
                #
                # HISTORICAL BUG: Originally, this regex was anchored to the start of the
                # line `^[ \t]*`. This blinded the firewall to PHP's dynamic execution
                # patterns. PHP applications (especially legacy frameworks) frequently
                # lazy-load files inside controllers, `if` statements, or assign the result
                # of a file inclusion directly to a variable (e.g., `$config = require 'cfg.php';`).
                #
                # THE FIX: The `^` anchor has been stripped. We now rely on the `\b` word
                # boundary to find the inclusion keywords anywhere in the file.
                #
                # [ THE ASSIGNMENT SHIELD SIMPLIFICATION ]
                # Because the regex is no longer anchored to the start of the line, we were
                # able to completely delete the bloated, ReDoS-prone assignment capture group
                # `(?:\$[a-zA-Z_]...=)?`. The engine now effortlessly ignores the `$var = `
                # portion and skips straight to the `require` boundary.
                #
                # [ THE PARENTHESIS SHIELD ]
                # PHP allows `require 'file.php'` and `require('file.php')`. The `\(?` safely
                # bridges both syntaxes while capturing the target path.
                # =====================================================================
                r"\b(?:use[ \t\n]+(?:function[ \t\n]+|const[ \t\n]+)?([\w\\]+)|(?:require|require_once|include|include_once)[ \t\n]*\(?[ \t\n]*['\"]([^'\"]+)['\"])",
                re.M,
            ),
            # 25. ownership (Authorship Metadata)
            "ownership": re.compile(r"@(?:author|copyright)\s+(.*)|(?:Created by|Maintainer):?\s+(.*)", re.I),
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            # 26. planned_debt (Annotated Debt / TODOs)
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            # 29. spec_exposure (Spec / Audit Traceability)
            "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]", re.I),
            # 30. tabs_vs_spaces (Formatting Inconsistencies) 
            "tabs_vs_spaces": None,
            # 31. ssr_boundaries (Server-Side Rendering)
            "ssr_boundaries": re.compile(
                r"\b(Response|JsonResponse|HtmlResponse|RedirectResponse|Symfony\\Component\\HttpFoundation|Illuminate\\Http\\Response)\b"
            ),
            # 32. events (Event Emitters / Pub-Sub)
            "events": re.compile(
                r"\b(EventDispatcher|dispatchEvent|Listener|dispatch|broadcast|notify|Event::|listen)\b"
            ),
            # 33. dependency_injection (Dependency Injection / IoC)
            "dependency_injection": re.compile(
                r"\b(ContainerInterface|Container|getContainer|inject|bind|singleton|app\(|make\()\b|#\[(?:Inject|Autowire)[^\]]*\]"
            ),
            # 34. macros (Preprocessor Directives / Macros)
            "macros": re.compile(r"\b(?:Macroable|macro\s*\(|mixin\s*\()\b"),
            # 35. pointers (Pointer Arithmetic / Memory Addressing)
            "pointers": re.compile(r"\b(FFI::cast|FFI::addr|FFI::scope|FFI::new)\b"),
            # 36. memory_alloc
            "memory_alloc": re.compile(r"\bnew\s+[a-zA-Z_\x80-\xff][a-zA-Z0-9_\x80-\xff]*"),
            # 37. inline_asm
            "inline_asm": None,
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # 38. telemetry (Structured Logging / Telemetry)
            "telemetry": re.compile(
                r"\b(?:Log::|LoggerInterface|logger\(|Monolog\\|error_log|Psr\\Log)\b.*?(?:info|error|warning|debug|trace|notice|critical|alert|emergency)\b",
                re.I,
            ),
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
            "debug_prints": re.compile(r"\b(echo|print|var_dump|print_r|printf|vprintf|var_export|die|exit|dd|dump)\b"),
            # # 40. explicit_casts (Explicit Type Casting)
            "explicit_casts": re.compile(
                r"\((?:int|integer|bool|boolean|float|double|string|array|object|unset)\)\s*|\bsettype\s*\("
            ),
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
            "panics_and_aborts": re.compile(r"\b(throw|die|exit|abort)\b"),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
            "thread_sleeps": re.compile(r"\b(sleep|usleep|time_nanosleep|time_sleep_until)\b"),
            # 43. bitwise_ops (Bitwise Operations)
            "bitwise_ops": re.compile(r"<<|>>|(?<!&)&(?!&)|(?<!\|)\|(?!\|)|\^|~"),
            # 44. sync_locks (Resource Management & Stability)
            "sync_locks": re.compile(r"\b(mutex|lock|synchronized|Semaphore|flock|sem_acquire)\b", re.I),
            # 45. immutability_locks (Immutability Constraints)
            "immutability_locks": re.compile(r"\b(const|readonly|final)\b"),
            # 46. cleanup (Resource Cleanup / Teardown)
            "cleanup": re.compile(r"\b(unset|fclose|mysql_close|mysqli_close|PDO::null|dispose|cleanup)\b\s*\("),
            # 47. encapsulation (Access Modifiers / Encapsulation)
            "encapsulation": re.compile(r"\b(private|protected|internal)\b"),
            # 48. listeners (Event Listeners / Observers)
            "listeners": re.compile(r"\.on\(|addEventListener|subscribe|@KafkaListener|@RabbitListener"),
            # 49. test_skip (Bypassed Tests / Ignored Specs)
            "test_skip": re.compile(r"\b(markTestSkipped|test\.skip|it\.skip|mock\(|fake\()\b"),
            # --- PHASE 3: HYBRID DOMAIN SENSORS (PHP Specifics) ---
            "serialization_parsing": re.compile(
                r"\b(unserialize|serialize|json_decode|json_encode|simplexml_load_(?:string|file)|DOMDocument)\b"
            ),
            "regex_execution": re.compile(
                r"\b(preg_match(?:_all)?|preg_replace(?:_callback)?|preg_split|preg_filter)\b"
            ),
            "time_date_logic": re.compile(r"\b(strtotime|DateTime(?:Immutable)?|date_create|time\s*\(|date\s*\()\b"),
            "ipc_rpc_bridges": re.compile(r"\b(shell_exec|exec|system|passthru|proc_open|curl_exec|fsockopen)\b"),
        },
    },
    "powershell": {
        "_meta": {
            "target_version": "PowerShell 7.5.4 (Core / Cross-Platform / PSClasses)",
            "last_updated": "2026-02-18",
            "blueprint_version": "v5.0",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard scripts (.ps1), modules (.psm1), data files evaluated as AST (.psd1), and type formatting files.
        "extensions": [".ps1", ".psm1", ".psd1", ".ps1xml", ".psc1", ".pssc", ".cdxml"],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: PowerShell rarely uses extensionless execution scripts; its conventions demand extensions.
        "exact_matches": [],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions and analyzer settings to lock in context.
        "discriminators": [
            ".ps1",
            ".psm1",
            "PSScriptAnalyzerSettings.psd1",
            "psake.ps1",
        ],
        # EXECUTION SIGNATURES: Modern cross-platform and legacy Windows interpreters found on Line 1.
        "shebangs": ["pwsh", "powershell"],
        # UPGRADED: Maps to Family 4 (Hybrid Hash)
        # Rationale: PowerShell uses '#' for single-line comments but relies on
        # a unique '<# #>' syntax for multi-line block comments, requiring hybrid parsing logic.
        "lexical_family": "standard_block",
        "rules": {
            # --- LEXICAL DELIMITER CONTROLS ---
            # PowerShell uses '#' for standard line-level literature.
            "_line_anchor": re.compile(r"#"),
            # Inline comments are also triggered by the '#' token.
            "_inline_comment": re.compile(r"#"),
            # Block comment start: <#
            "_block_start": re.compile(r"<#"),
            # Block comment end: #>
            "_block_end": re.compile(r"#>"),
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # branch: decisions that split flow. Includes ternary operators (?) and null-coalescing (??).
            "branch": re.compile(
                r"\b(if|else|elseif|switch|for|foreach|while|do|until|try|catch|finally|throw|trap|break|continue|return)\b|-and|-or|-not|-xor|\?|\?\?",
                re.I,
            ),
            # args: Parameters / Coupling. Captures the param block mass of functions and script files.
            "args": re.compile(r"\bparam\s*\([^)]*\)|\bfunction\s+[a-zA-Z0-9_-]+\s*\([^)]*\)", re.I),
            # linear: Sequential I/O & Network Boundaries. Structural boundaries defining scope (process, begin, end).
            # EXCLUDES access modifiers (hidden, static) to prevent Structural Complexity Inflation.
            "structural_boundaries": re.compile(
                r"\b(function|filter|workflow|configuration|class|enum|process|begin|end|clean|return|exit|using|namespace)\b",
                re.I,
            ),
            # func_start: Executable Logic Anchors. Anchors executable logic blocks.
            # EXCLUDES class/enum to fix False Positives.
            "func_start": re.compile(
                r"^[ \t]*(?:function|filter|workflow)\s+([a-zA-Z0-9_-]+)|^[ \t]*\[[^\]]+\]\s+([a-zA-Z_]\w*)(?=\s*\()",
                re.I | re.M,
            ),
            # class_start: Object / Entity Declarations. Defines OO boundaries (Classes and Enums).
            "class_start": re.compile(r"^[ \t]*(?:class|enum)\s+[a-zA-Z_]\w*", re.I | re.M),
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            # safety: Defensive Programming. Strict mode, validation attributes, and null-conditional access (?.).
            "safety": re.compile(
                r"\b(try|catch|finally|trap|Set-StrictMode|ValidateNotNull|ValidateSet|ValidateRange|ValidatePattern)\b|-ErrorAction\s+Stop|\$\?|\?\.",
                re.I,
            ),
            # safety_neg: Safety Bypasses. Actively bypassing errors or type checks (Out-Null, SilentlyContinue).
            "safety_bypasses": re.compile(
                r"-ErrorAction\s+SilentlyContinue|-WarningAction\s+SilentlyContinue|Out-Null|\[void\]|ExecutionPolicy\s+Bypass|\bIgnore\b",
                re.I,
            ),
            # danger: High-Risk Execution. Dynamic code execution and process terminators.
            "high_risk_execution": re.compile(r"\b(Invoke-Expression|iex|Stop-Process|kill|Exit)\b", re.I),
            # io: I/O & Network Boundaries. Disk, Network, and URL fetching (Includes CERN/TBL legacy emulation triggers).
            "io": re.compile(
                r"\b(Get-Content|Set-Content|Out-File|Invoke-WebRequest|iwr|Invoke-RestMethod|irm|TcpClient|HttpListener|HTLoad|HTGet|ENQUIRE)\b",
                re.I,
            ),
            # api: Public Surface Area. Exposed surface area (Module exports and non-hidden functions).
            "api": re.compile(
                r"\b(Export-ModuleMember|New-Alias|CmdletBinding)\b|^[ \t]*(?!hidden\s+)[a-zA-Z_]\w*\s*\(",
                re.I | re.M,
            ),
            # 11. flux (State Mutation)
            # Mutation of state. Captures assignments, scoped variables, array indexing, and anchored increments.
            "state_mutation": re.compile(
                # PATH A: EXPLICIT CMDLET MUTATION
                r"\bSet-Variable\b|"
                # PATH B: STANDARD ASSIGNMENT (Variables, Scopes, Properties, and Arrays)
                # Safely captures $var, $global:var, $env:PATH
                r"\$(?:[a-zA-Z]+:)?[a-zA-Z_]\w*"
                # The Chain: Safely captures .Property OR ['Index'], clamped to {0,4} to prevent runaway depth
                r"(?:\.[a-zA-Z_]\w*|\[[^\]\n]+\]){0,4}"
                # The Operator: Uses [ \t]* instead of \s* to prevent O(N^2) vertical newline bleeding
                r"[ \t]*(?:\+|-|\*|/|%)?=|"
                # PATH C: PRE-INCREMENT / PRE-DECREMENT
                # Anchored to a variable to prevent matching "C++" in strings
                r"(?:\+\+|--)[ \t]*\$(?:[a-zA-Z]+:)?[a-zA-Z_]\w*|"
                # PATH D: POST-INCREMENT / POST-DECREMENT
                # Includes property/array chaining before the increment (e.g. $arr[0]++)
                r"\$(?:[a-zA-Z]+:)?[a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*|\[[^\]\n]+\]){0,4}[ \t]*(?:\+\+|--)",
                re.I,
            ),
            # 12. dead_code (Commented Logic / Deprecated Trails)
            # Commented-out execution logic indicating dead features. Supports both `//` and `#` style comments.
            "dead_code": re.compile(r"(?:#|<#)[ \t]*(?:function|class|if|foreach|while|return)\b", re.I),
            # doc: Structured Documentation. Get-Help comment-based documentation.
            "doc": re.compile(
                r"\.(?:SYNOPSIS|DESCRIPTION|PARAMETER|EXAMPLE|NOTES|LINK|INPUTS|OUTPUTS|ROLE)\b",
                re.I,
            ),
            # 14. test (Testing & Assertions)
            # Triggers indicating internal verification. MUST strictly anchor 'it', 'test', and 'toBe' with opening parentheses to prevent triggering on prose inside Pest/PHPUnit tests.
            "test": re.compile(
                r'\b(?:Mock|Assert-MockCalled|BeforeAll|AfterAll|BeforeEach|AfterEach|Should)\b|\b(?:Describe|Context|It)\s+[\'"]',
                re.I,
            ),
            # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
            # concurrency: Temporal Static. Jobs, Runspaces, and PS7 Parallel pipelines.
            "concurrency": re.compile(
                r"\b(Start-Job|Wait-Job|Receive-Job|Start-ThreadJob|-Parallel|RunspaceFactory|PowerShell\.Create)\b",
                re.I,
            ),
            # ui_framework: UI / View Components. WinForms/WPF bridges (Includes TBL WWW rendering emulation triggers).
            "ui_framework": re.compile(
                r"\[System\.Windows\.(?:Forms|Controls|Markup)\]|New-Object\s+System\.Windows\.|Out-GridView|HtmlDocument|WebBrowser|SGML|WorldWideWeb",
                re.I,
            ),
            # closures: Closures / Anonymous Functions. ScriptBlocks (The foundation of PS closures).
            "closures": re.compile(r"\{\s*(?:param\s*\([^)]*\))?[^}]*\}", re.I),
            # globals: Global / Shared State. Environment and global/script scope variables.
            "globals": re.compile(
                r"\$(?:global|env|script):[a-zA-Z_]\w*|\b(?:ErrorActionPreference|WarningPreference|ConfirmPreference)\b",
                re.I,
            ),
            # decorators: Decorators / Annotations. Cmdlet and Parameter attributes.
            "decorators": re.compile(
                r"\[(?:CmdletBinding|Parameter|Alias|OutputType|AllowNull|AllowEmptyString)\s*\([^)]*\)\]",
                re.I,
            ),
            # generics: Generics / Type Parameters. .NET generic type invocations.
            "generics": re.compile(r"\[[a-zA-Z_.]+(?:`\d+)?\[[^\]]*\]\]", re.I),
            # comprehensions: Iterators / Comprehensions. Pipeline filtering and projection.
            "comprehensions": re.compile(
                r"\|\s*(?:Where-Object|\?|Select-Object|select|ForEach-Object|%)[ \t]*\{",
                re.I,
            ),
            # scientific: Numerical / Compute Libraries. .NET Math primitives.
            "scientific": re.compile(
                r"\[Math\]::(?:Abs|Acos|Asin|Atan|Ceiling|Cos|Exp|Floor|Log|Max|Min|Pow|Round|Sin|Sqrt|Tan|PI)\b",
                re.I,
            ),
            # heat_triggers: Metaprogramming & Reflection. Reflection and on-the-fly C# compilation via Add-Type.
            "reflection_metaprogramming": re.compile(
                r"\b(Add-Type|System\.Reflection|System\.Management\.Automation\.Language|Invoke-Expression|iex)\b|&\s*\$[a-zA-Z_]\w*",
                re.I,
            ),
            # import: Dependency Inclusions. Module and assembly loading.
            "import": re.compile(
                r"\b(Import-Module|using\s+module|using\s+namespace|using\s+assembly|\.\s+[\w.\/\\]+\.ps1)\b",
                re.I,
            ),
            # --- UPDATED LINE FOR THE ORCHESTRATOR ---
            "_dependency_capture": re.compile(
                r"^[ \t]*(?:Import-Module|using[ \t\n]+(?:module|namespace|assembly))[ \t\n]+['\"]?([^'\"\s;]+)['\"]?|^[ \t]*\.[ \t\n]+['\"]?([^'\"\s;]+\.ps1)['\"]?",
                re.I | re.M,
            ),
            # ownership: Authorship indicators in comments or metadata.
            "ownership": re.compile(
                r"^[ \t]*#\s*(?:Author|Created by|Maintainer|Copyright):\s+([^\n]+)|\.AUTHOR\s+([^\n]+)",
                re.I | re.M,
            ),
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            "planned_debt": GLOBAL_PLANNED_DEBT,
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)\]", re.I),
            # 30. tabs_vs_spaces (Formatting Inconsistencies) 
            # Structural formatting violating norms. Handled natively by the GitGalaxy Signal Processor.
            "tabs_vs_spaces": None,
            "ssr_boundaries": re.compile(
                r"\b(New-PodeServer|Add-PodeRoute|Write-PodeHtmlResponse|New-UDEndpoint|New-UDPage)\b",
                re.I,
            ),
            "events": re.compile(
                r"\b(Register-ObjectEvent|Register-EngineEvent|Register-WmiEvent|Unregister-Event|Wait-Event)\b",
                re.I,
            ),
            "dependency_injection": re.compile(
                r"\b(InversionOfControl|DependencyInjection|Register-Service|Get-Service|Resolve-Dependency)\b",
                re.I,
            ),
            "macros": None,  # PowerShell lacks a preprocessor
            # 35. pointers (Pointer Arithmetic / Memory Addressing)
            # PHP natively lacks pointers, but FFI (Foreign Function Interface) memory bounds are safely captured.
            "pointers": re.compile(r"\[(?:IntPtr|UIntPtr)\]|\[ref\]\s*\$[a-zA-Z_]\w*", re.I),
            "memory_alloc": re.compile(
                r"\[System\.Runtime\.InteropServices\.Marshal\]::(?:AllocHGlobal|AllocCoTaskMem)",
                re.I,
            ),
            "inline_asm": None,
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # telemetry: Professional observers. Structured pipeline logging.
            "telemetry": re.compile(
                r"\b(Write-Verbose|Write-Debug|Write-Information|Write-Warning|Start-Transcript|Write-Log)\b",
                re.I,
            ),
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs)
            "debug_prints": re.compile(r"\b(Write-Host|echo)\b", re.I),
            # # 40. explicit_casts (Explicit Type Casting)
            # Forceful type coercion. PHP has a strict, built-in casting syntax which prevents false positives naturally.
            "explicit_casts": re.compile(
                r"\[(?:int|long|string|char|byte|bool|double|float|decimal|array|hashtable)\]\s*[\$\(]",
                re.I,
            ),
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
            "panics_and_aborts": re.compile(r"\b(throw|Exit)\b|-ErrorAction\s+Stop", re.I),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
            "thread_sleeps": re.compile(r"\b(Start-Sleep|sleep)\b", re.I),
            # 43. bitwise_ops (Bitwise Operations)
            # Low-level byte manipulation. CRITICAL: Removed the pipe '|' (PHP 8 Union Types), ampersand '&' (Pass-by-reference `&$var`), and used lookarounds for `<<` to prevent triggering on Heredocs (`<<<EOF`).
            "bitwise_ops": re.compile(r"-(?:band|bor|bxor|bnot|shl|shr)\b", re.I),
            # sync_locks: Barricades. Coordinated threading logic.
            "sync_locks": re.compile(r"\b(lock|Monitor|Mutex|Semaphore|atomic|WaitOne)\b", re.I),
            # 45. immutability_locks (Immutability Constraints)
            "immutability_locks": re.compile(r"New-Variable\s+[^;]*?-Option\s+Constant|readonly", re.I),
            # 46. cleanup (Resource Cleanup / Teardown) Resource release.
            "cleanup": re.compile(
                r"\b(dispose|Remove-Variable|Remove-Item|Remove-Module|Stop-Transcript)\b",
                re.I,
            ),
            # 47. encapsulation (Encapsulation / Access Modifiers)
            "encapsulation": re.compile(r"\b(hidden|private)\b", re.I),
            # 48. listeners (Event Listeners / Observers)
            "listeners": re.compile(r"\b(Register-ObjectEvent|on_|Connect-)\b", re.I),
            # 49. test_skip (Bypassed Tests / Ignored Specs) Safety Theater.
            "test_skip": re.compile(r"\b(pending|skip|Ignore)\b", re.I),
            # --- PHASE 3: HYBRID DOMAIN SENSORS (PowerShell Specifics) ---
            "serialization_parsing": re.compile(
                r"(?i)\b(ConvertFrom-Json|ConvertTo-Json|Import-Clixml|ConvertFrom-Csv|Import-Csv)\b"
            ),
            "regex_execution": re.compile(
                r"(?i)\b(-match|-replace|-split|Select-String|\[regex\]::(?:Match|Replace|Matches))\b"
            ),
            "time_date_logic": re.compile(r"(?i)\b(Get-Date|New-TimeSpan|Start-Sleep|Measure-Command)\b"),
            "ipc_rpc_bridges": re.compile(
                r"(?i)\b(Invoke-Command|Invoke-RestMethod|Invoke-WebRequest|Start-Process|Start-Job|Enter-PSSession)\b"
            ),
        },
    },
    "shell": {
        "_meta": {
            "target_version": "Bash 5.2 / Zsh 5.9 / Modern DevOps Scripts",
            "last_updated": "2026-02-18",
            "blueprint_version": "v5.0",
            "status": "production",
        },
        "extensions": [
            ".sh",
            ".bash",
            ".zsh",
            ".ksh",
            ".dash",
            ".command",
            ".csh",
            ".tcsh",
            ".fish",
            ".bats",
        ],
        # Thorough Exact Match List: Captures hidden configuration and profile scripts.
        "exact_matches": [
            ".bashrc",
            ".zshrc",
            ".profile",
            ".bash_profile",
            ".bash_logout",
            ".inputrc",
            "bash_completion",
            "PKGBUILD",
        ],
        # Thorough Shebang mapping: Essential for identifying extensionless scripts.
        "shebangs": ["bash", "sh", "zsh", "ksh", "dash", "ash", "rbash"],
        # UPGRADED: Maps to Family 3 (Pure Hash)
        # Rationale: Relies strictly on '#' for line-level Commented / Non-Executable Text; no native block delimiters.
        "lexical_family": "line_exclusive",
        "rules": {
            # --- LEXICAL DELIMITER CONTROLS ---
            # Shell uses '#' for standard line-level literature.
            "_line_anchor": re.compile(r"#"),
            # Inline comments are also triggered by the '#' token.
            "_inline_comment": re.compile(r"#"),
            # EXPLICIT: Shell lacks native multi-line block comment delimiters.
            "_block_start": None,
            "_block_end": None,
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # 1. branch (Control Flow / Branching)
            # Decisions and logic jumps. Includes test constructs [[ ]] and [ ].
            # CRITICAL: Excluded bare '((' and '))' to prevent ReDoS on massive subshell nesting.
            "branch": re.compile(
                r"\b(if|then|else|elif|fi|case|esac|for|while|do|done|until|select|break|continue)\b|&&|\|\||\[\[|\]\]"
            ),
            # 2. args (Parameters / Coupling)
            # Positional parameters and expansion markers.
            "args": re.compile(r'\$(?:[1-9]|\{[1-9]\w*\}|@|\*|#)|"\$@"|"\$\*"'),
            # 3. linear (Sequential Boundaries)
            # Structural boundaries and straight-line execution verbs.
            "structural_boundaries": re.compile(
                r"\b(local|readonly|export|declare|typeset|return|exit|source|\.|read|cd|pwd|ls|cp|mv|rm|mkdir|touch)\b|\|(?!\s*\|)"
            ),
            # Anchors executable logic blocks. Captures `function foo` or `foo()`.
            # Handled by Mode D (Semantic Handshake) in detector.py.
            "func_start": re.compile(
                # =====================================================================
                # [ THE VERTICAL FUNCTION SHIELD (SHELL) ]
                # Bash/Zsh allow extreme spacing and newlines between the `function`
                # keyword and the identifier name.
                # FIX: Upgraded horizontal spaces `[ \t]+` to `[ \t\n]+` for the
                # `function` keyword path, allowing it to easily consume weird formatting.
                # =====================================================================
                r"^[ \t]*(?:function[ \t\n]+([a-zA-Z_][a-zA-Z0-9_.-]*)|(?!(?:if|while|for|case|until)\b)([a-zA-Z_][a-zA-Z0-9_.-]*)[ \t\n]*\(\))",
                re.M,
            ),
            # 5. class_start
            # Shell is strictly procedural.
            "class_start": None,
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            # 6. safety (Defensive Programming / Validation)
            # Shell hardening: strict modes, traps, and robust quoting.
            "safety": re.compile(
                r'\b(set\s+-(?:[a-zA-Z]*e[a-zA-Z]*|u|o\s+pipefail)|trap\s+[^\n]*(?:ERR|EXIT|INT|TERM))\b|"\$[@*]"|"\$\{[^}]+\}"|\bcommand\s+-v\b|\$\{[a-zA-Z0-9_]+:[-=?][^}]*\}'
            ),
            # 7. safety_neg (Safety Bypasses / Unchecked Types)
            # Unquoted variables, dynamic evaluation, and blind network-to-shell piping.
            # 7. safety_neg (Safety Bypasses / Unchecked Types)
            # Unquoted variables, dynamic evaluation, and blind network-to-shell piping.
            "safety_bypasses": re.compile(
                r'\b(eval)\b(?!\s*\()|(?<!")\$(?![\(?])\w+(?!")|\|\|\s*true\b|>\s*/dev/null(?:\s*2>&1)?|\bcurl\s+[^|\n]{1,200}\|[ \t]*(?:bash|sh|zsh)\b'
            ),
            # 8. danger (High-Risk Execution / System Calls)
            # Destructive commands and privilege elevation. EXCLUDES echo (Phase 5).
            "high_risk_execution": re.compile(
                r"\b(rm\s+-[rR]f|sudo|chmod\s+(?:-R[ \t]+)?777|chown\s+(?:-R[ \t]+)?root|mkfs|dd|kill(?:all)?)\b"
            ),
            # 9. io (I/O & Network Boundaries)
            # Redirections, pipes, and network clients.
            "io": re.compile(r">|>>|<|\|(?:&)?|\b(curl|wget|nc|ssh|scp|ftp|rsync|cat|tail|grep|find|xargs|jq)\b"),
            # 10. api (Public Surface Area)
            # Exported variables and identifiers modifying the global environment.
            "api": re.compile(r"^[ \t]*export\s+[a-zA-Z_]\w*", re.M),
            # 11. flux (State Mutation)
            # Mutation of state via assignment or arithmetic.
            "state_mutation": re.compile(
                r"^[ \t]*[a-zA-Z_]\w*(?:\[[^\]]+\])?=(?![=~])|\b(?:let|declare)\s+[a-zA-Z_]\w*=|\[\+\]=|\(\([^)]*(?:\+\+|--|[-+*/%]=)[^)]*\)\)",
                re.M,
            ),
            # 12. dead_code (Commented Logic / Deprecated Trails)
            # Commented-out execution logic indicating dead features.
            "dead_code": re.compile(r"#[ \t]*(?:if|for|while|function|export|echo|printf|cd|rm|sudo|ls)\b"),
            # 13. doc (Structured Documentation)
            "doc": re.compile(
                r"^[ \t]*#\s*(?:@param|@return|Usage:|Description:|Examples:|Options:)|#\s*shellcheck\s+disable",
                re.M | re.I,
            ),
            # 14. test (Testing & Assertions)
            # Triggers indicating internal verification. Anchored to shell-specific testing framework commands.
            "test": re.compile(
                r"\b(assert_?eq|assertTrue|assertFalse|assert_?match|bats|shunit2)\b|^@test\s+|\brun\s+[a-zA-Z0-9_-]+",
                re.M,
            ),
            # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
            # 15. concurrency (Asynchronous Execution)
            "concurrency": re.compile(
                r"&[ \t]*$|\b(wait(?:\s+-n)?|coproc|nohup|parallel|jobs|fg|bg|disown|xargs\s+-P)\b|&\s*\|\||<\([^)]*\)|>\([^)]*\)",
                re.M,
            ),
            # 16. ui_framework (UI / View Components)
            # Terminal UI builders and ANSI sequences.
            "ui_framework": re.compile(
                r"\b(dialog|whiptail|zenity|kdialog|notify-send|tput|gum|tmux)\b|\\033\[[0-9;]+m|\\e\[[0-9;]+m"
            ),
            # 17. closures
            "closures": None,  # Shell lacks native anonymous lambdas.
            # 18. globals (Global / Shared State)
            "globals": re.compile(
                r"\b(PATH|HOME|USER|SHELL|EDITOR|PWD|OLDPWD|TERM|LANG|OSTYPE|MACHTYPE|UID|EUID|GROUPS)\b"
            ),
            # 19. decorators
            "decorators": None,
            # 20. generics
            "generics": None,
            # 21. comprehensions (Iterators / Comprehensions)
            # Brace expansions acting as inline loops.
            "comprehensions": re.compile(r"\{[0-9]+(?:\.\.|,)[0-9]+(?:\.\.[0-9]+)?\}|\{[a-zA-Z]\.\.[a-zA-Z]\}"),
            # 22. scientific (Numerical / Compute Libraries)
            "scientific": re.compile(r"\b(bc|awk|dc|expr|jq|RANDOM|SRANDOM)\b|\$\(\("),
            # 23. heat_triggers (Metaprogramming & Reflection)
            # Sub-languages and indirect expansion. (ReDoS Shielded)
            "reflection_metaprogramming": re.compile(
                r'\$\([^)]+\)|`[^`]+`|\b(?:awk|sed|perl|python[23]?|ruby)\s+[\'"][^\'"]{0,500}|\beval\s+\$|\$\{!?[a-zA-Z0-9_]+\}'
            ),
            # 24. import (Dependency Inclusions)
            "import": re.compile(r"(?:^|[ \t;|&])(?:source\b|\.(?=[ \t]))[ \t]+[^\s;]+", re.M),
            "_dependency_capture": re.compile(
                # =====================================================================
                # [ FUTURE LLM CONTEXT: THE DYNAMIC EXECUTION SHIFT (SHELL) ]
                # PURPOSE: Extracts external dependencies for the Network Graph and Supply Chain Firewall.
                #
                # HISTORICAL BUG: Originally, this regex was anchored to the start of the
                # line `^[ \t]*`. This blinded the firewall to dynamic or conditional shell
                # execution. Shell scripts frequently source environment files inside `if`
                # blocks (e.g., `if [ -f .env ]; then source .env; fi`) or after logical
                # operators (e.g., `test -f lib.sh && . lib.sh`). The anchored regex missed
                # these entirely.
                #
                # THE FIX: The `^` anchor has been replaced with a Shell Statement Boundary:
                # `(?:^|[ \t;|&])`. This allows the engine to recognize a `source` or `.`
                # command immediately following a pipe `|`, a background task `&`, a logic
                # gate `&&`, a command separator `;`, or standard whitespace, without
                # triggering false positives on prose in echo statements.
                #
                # [ THE DOT-OPERATOR WORD BOUNDARY TRAP ]
                # We CANNOT use a standard `\b` word boundary for the entire group because
                # the dot operator (`.`) is a non-word character. `\b\.` will fail.
                # Therefore, we explicitly branch: `source` gets a word boundary `\b`,
                # and `.` gets a positive lookahead for whitespace `(?=[ \t])`.
                # =====================================================================
                r"(?:^|[ \t;|&])(?:source\b|\.(?=[ \t]))[ \t]+['\"]?([^'\"\s;]+)['\"]?",
                re.M,
            ),
            # 25. ownership (Authorship Metadata)
            "ownership": re.compile(
                r"^[ \t]*#\s*(?:Author|Created by|Maintainer|Copyright):?\s+(.*)",
                re.M | re.I,
            ),
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            # 26. planned_debt (Annotated Debt / TODOs)
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            # 29. spec_exposure (Spec / Audit Traceability)
            "spec_exposure": re.compile(r"#\s*\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]", re.I),
            # 30. tabs_vs_spaces (Formatting Inconsistencies) 
            "tabs_vs_spaces": None,
            # 31. ssr_boundaries (Server-Side Rendering)
            # Legacy CGI shell environments.
            "ssr_boundaries": re.compile(
                r'\b(?:CONTENT_TYPE|QUERY_STRING|HTTP_USER_AGENT)\b|echo\s+"Content-type:\s*text/(?:html|plain|json)'
            ),
            # 32. events (Event Emitters / Pub-Sub)
            # Named pipes and OS signal handlers.
            "events": re.compile(
                r"\b(mkfifo|mknod|inotifywait|inotifywatch|fswatch|tail\s+-f|kill\s+-(?:SIG)?(?:USR1|USR2|HUP|TERM))\b"
            ),
            # 33. dependency_injection (Dependency Injection / IoC)
            "dependency_injection": re.compile(r"\$\{1:-\w+\}|\$\{2:-\w+\}|\b(?:command\s+-v|type\s+-p)\b"),
            # 34. macros (Preprocessor Directives / Macros)
            "macros": re.compile(r"^[ \t]*(?:alias|shopt)\b", re.M),
            # 35. pointers (Pointer Arithmetic / Memory Addressing)
            # Raw memory addressing. Shell uses namerefs and indirect expansion.
            "pointers": re.compile(r"\b(?:declare\s+-n|typeset\s+-n)\b|\$\{\!"),
            # 36. memory_alloc
            "memory_alloc": None,
            # 37. inline_asm
            "inline_asm": None,
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # 38. telemetry (Structured Logging / Telemetry)
            "telemetry": re.compile(
                r"\b(?:logger|syslog|log_info|log_err|log_warn|log_debug)\b|>\s*/dev/(?:stderr|console)"
            ),
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
            "debug_prints": re.compile(r"\b(echo|printf|print|read)\b"),
            # 40. explicit_casts (Explicit Type Casting)
            "explicit_casts": None,
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
            "panics_and_aborts": re.compile(r"\b(exit|kill|abort|halt|return\s+[1-9][0-9]*)\b"),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
            "thread_sleeps": re.compile(r"\b(sleep|read\s+-t)\b"),
            # 43. bitwise_ops (Bitwise Operations)
            "bitwise_ops": None,
            # 44. sync_locks (Resource Management & Stability)
            "sync_locks": re.compile(r"\b(flock|mkdir|mkfifo|lockfile|sem)\b"),
            # 45. immutability_locks (Immutability Constraints)
            "immutability_locks": re.compile(r"\b(readonly|declare\s+-r|typeset\s+-r)\b"),
            # 46. cleanup (Resource Cleanup / Teardown)
            "cleanup": re.compile(r"\b(rm\s+-f|trap\s+.*EXIT|unset|exit|logout)\b"),
            # 47. encapsulation (Access Modifiers / Encapsulation)
            # Physical Reality: local variables represent internal state scope.
            "encapsulation": re.compile(r"\b(local|typeset|declare)\b"),
            # 48. listeners (Event Listeners / Observers)
            "listeners": re.compile(r"\b(read|inotifywait|nc\s+-l|while\s+read)\b"),
            # 49. test_skip (Bypassed Tests / Ignored Specs)
            "test_skip": re.compile(r"\b(test\.skip|bats_skip|#\s*SKIP|mock|stub)\b"),
            # --- PHASE 3: HYBRID DOMAIN SENSORS (Shell Specifics) ---
            "serialization_parsing": re.compile(r"\b(jq|yq|awk|sed|xmlstarlet)\b"),
            "regex_execution": re.compile(r"\b(grep|egrep|sed|awk)\b|=~"),
            "time_date_logic": re.compile(r"\b(date\s+|sleep\s+|uptime|times)\b"),
            "ipc_rpc_bridges": re.compile(r"\b(curl|wget|nc|netcat|ssh|scp|xargs|socat)\b"),
        },
    },
    "ruby": {
        "_meta": {
            "target_version": "Ruby 4.0 Paradigms (Ruby 3.4+ / Ractors / Sorbet / Pattern Matching)",
            "last_updated": "2026-02-18",
            "blueprint_version": "v5.0",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard suffixes, rack configs (.ru), gem specs, and various templating/DSL extensions.
        "extensions": [
            ".rb",
            ".rbw",
            ".rake",
            ".rbi",
            ".gemspec",
            ".rbx",
            ".builder",
            ".ru",
            ".podspec",
            ".jbuilder",
            ".rabl",
        ],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: Extensionless infrastructure-as-code and dependency configurations that are secretly pure Ruby.
        "exact_matches": [
            "Gemfile",
            "Rakefile",
            "Vagrantfile",
            "Guardfile",
            "Capfile",
            "Thorfile",
            "Berksfile",
            "Cheffile",
            "Podfile",
            "Fastfile",
            "Appraisals",
        ],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions, lockfiles, and environment pins to lock in context.
        "discriminators": [
            ".rb",
            "Gemfile.lock",
            ".ruby-version",
            ".ruby-gemset",
            "config.ru",
        ],
        # EXECUTION SIGNATURES: Interpreters found on Line 1.
        "shebangs": ["ruby", "macruby", "jruby", "rbx"],
        # UPGRADED: Maps to Family 4 (Hybrid Hash)
        # Rationale: Uses '#' for single-line comments, but multi-line literature
        # utilizes the `=begin ... =end` block syntax, requiring hybrid parsing rules.
        "lexical_family": "line_exclusive",
        "rules": {
            # --- LEXICAL DELIMITER CONTROLS ---
            # Ruby uses '#' for standard line-level literature (Commented / Non-Executable Text).
            "_line_anchor": re.compile(r"#"),
            # Inline comments are also triggered by the '#' token.
            "_inline_comment": re.compile(r"#"),
            # Block comment start: =begin (Must be at the absolute start of the line).
            "_block_start": re.compile(r"^=begin", re.M),
            # Block comment end: =end (Must be at the absolute start of the line).
            "_block_end": re.compile(r"^=end", re.M),
            # 1. branch (Control Flow / Branching)
            # Decisions and logical jumps. EXCLUDES raise/throw (bailout_hits).
            "branch": re.compile(
                r"\b(if|unless|elsif|else|case|when|in|for|while|until|begin|rescue|ensure|break|next|redo|retry)\b|&&|\|\||\?|=>"
            ),
            # 2. args (Parameters / Coupling)
            # Parameter blocks of methods, lambdas, and blocks. Bounded to prevent ReDoS.
            "args": re.compile(
                r"\bdef\s+(?:self\.)?[a-zA-Z_]\w*[=!?]?\s*\([^)]*\)|\bdo\s*\|[^|]*\||\{\s*\|[^|]*\||->\s*\([^)]*\)",
                re.M,
            ),
            # 3. linear (Sequential Boundaries)
            # Structural boundaries. EXCLUDES: Access modifiers (encapsulation) and const (freeze_hits).
            "structural_boundaries": re.compile(
                r"\b(class|module|def|yield|return|super|alias|undef|require|require_relative|include|extend|prepend|attr_reader|attr_writer|attr_accessor|Data\.define)\b"
            ),
            # 4. func_start (Executable Logic Anchors)
            # ONLY executable logic blocks. EXCLUDES class/module definitions.
            "func_start": re.compile(
                # =====================================================================
                # [ THE VERTICAL CLASS-METHOD SHIELD (RUBY) ]
                # Ruby allows 'def', 'self.', the function name, and the argument list
                # to be separated by vertical newlines.
                # FIX: Replaced `\s+` with `[ \t\n]+` and explicitly allowed `[ \t\n]*`
                # after `self.` so the parser doesn't break when tracking singleton methods.
                # Upgraded the trailing lookahead to safely handle newlines before `(`.
                # =====================================================================
                r'^[ \t]*(?:def[ \t\n]+(?:self\.[ \t\n]*)?|define_method[ \t\n]*\(?[ \t\n]*[:\'"]?)([a-zA-Z_]\w*[=!?]?)(?=[ \t\n]*[)\(]|[\'"]?[ \t\n]*(?:\{|do)|[ \t\n]|$)',
                re.M,
            ),
            # 5. class_start (Object / Entity Declarations)
            "class_start": re.compile(
                r"^[ \t]*(?:class|module)\s+([A-Z]\w*(?:::[A-Z]\w*)*)(?:\s*<\s*([A-Z]\w*(?:::[A-Z]\w*)*))?",
                re.M,
            ),
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            # 6. safety (Defensive Programming / Validation)
            "safety": re.compile(
                r"\&\.|\b(rescue|ensure|fetch|frozen_string_literal|freeze|catch|throw|safe_load|T\.must|T\.let|T\.cast|T\.bind)\b"
            ),
            # 7. safety_neg (Safety Bypasses / Unchecked Types)
            # Dynamic logic bypasses and Sorbet escape hatches.
            "safety_bypasses": re.compile(
                r"\b(eval|class_eval|instance_eval|module_eval|send|__send__|public_send|binding|instance_variable_set|unsafe_load|T\.unsafe|T\.untyped)\b"
            ),
            # 8. danger (High-Risk Execution / System Calls)
            # Process killers and shell execution. EXCLUDES puts (Phase 5).
            "high_risk_execution": re.compile(r"\b(abort|exit|exit!|system|exec|spawn|fork)\b|`[^`]+`|IO\.popen"),
            # 9. io (I/O & Network Boundaries)
            "io": re.compile(
                r"\b(File|Dir|IO|Net::HTTP|URI\.open|Socket|TCPSocket|FileUtils|ActiveRecord::Base|find|where|create|update|destroy)\b"
            ),
            # 10. api (Public Surface Area)
            # Implicit public defaults (undercased defs) + explicit module functions.
            "api": re.compile(
                r'\b(module_function)\b|^[ \t]*(?:get|post|put|patch|delete|resources?)\s+[:\'"]',
                re.M,
            ),
            # 11. flux (State Mutation)
            # Mutation of state. EXCLUDES const (freeze_hits).
            "state_mutation": re.compile(
                r"@[a-zA-Z_]\w*\s*(?:\+|-|\*|/)?=|@@[a-zA-Z_]\w*\s*(?:\+|-|\*|/)?=|\b(?:push|pop|shift|unshift|delete|clear|merge!|update!|gsub!|map!|select!|reject!)\b|<<"
            ),
            # 12. dead_code (Commented Logic / Deprecated Trails)
            "dead_code": re.compile(r"#[ \t]*(?:def|class|module|if|unless|while|puts|p)\b"),
            # 13. doc (Structured Documentation)
            # Captures YARD tags, Sorbet signatures, RDoc blocks/modifiers, and standard documentation headers.
            "doc": re.compile(
                r"^[ \t]*#\s*@(?:param|return|api|yield|raise|see|abstract|deprecated|note|example)|^[ \t]*sig[ \t]*\{|^=begin\s+(?:rdoc|pod)\b|^[ \t]*#\s*(?::nodoc:|:yields:|:args:|:return:)|^[ \t]*#\s*(?:Description|Usage|Example|Summary):\s+",
                re.M | re.I,
            ),
            # 14. test (Testing & Assertions)
            "test": re.compile(
                r'\b(describe|context|expect|assert[a-zA-Z_]*|refute[a-zA-Z_]*|setup|teardown|before|after|let|subject)\b|\b(?:it|test)\s+[\'"]'
            ),
            # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
            # 15. concurrency (Asynchronous Execution)
            "concurrency": re.compile(
                r"\b(Thread|Mutex|Monitor|ConditionVariable|Ractor|Fiber|Async|await|Concurrent)\b"
            ),
            # 16. ui_framework (UI / View Components)
            "ui_framework": re.compile(
                r"\b(ActionView|render|render_to_string|ViewComponent::Base|Phlex::HTML|form_with|form_for|link_to|stylesheet_link_tag|Turbo|Stimulus|Hotwire)\b|<%|%>"
            ),
            # 17. closures (Closures / Anonymous Functions)
            "closures": re.compile(r"\b(?:do\s*\|[^|]*\||do\b|\{\s*\|[^|]*\||->\s*(?:\([^)]*\))?[ \t]*\{)"),
            # 18. globals (Global / Shared State)
            "globals": re.compile(r"\$[a-zA-Z_]\w*|\b(ENV|ARGV|ARGF|STDIN|STDOUT|STDERR|RUBY_VERSION)\b"),
            # 19. decorators (Decorators / Annotations)
            # Rails class macros acting as metadata descriptors.
            "decorators": re.compile(
                r"^[ \t]*(?:before_action|after_action|around_action|before_save|after_commit|validates|has_many|belongs_to|has_one)\b",
                re.M,
            ),
            # 20. generics (Generics / Type Parameters)
            # Sorbet parameterized types.
            "generics": re.compile(r"\b(?:T::|::T::)?(?:Array|Hash|Set|Enumerable|Class)\[[^\]]*\]"),
            # 21. comprehensions (Iterators / Comprehensions)
            "comprehensions": re.compile(
                r"\.(?:map|collect|select|reject|reduce|inject|filter_map|flat_map|each_with_object|partition|group_by)\b(?:[ \t]*\{|\s*do)"
            ),
            # 22. scientific (Numerical / Compute Libraries)
            "scientific": re.compile(r"\b(Math|Complex|Rational|Matrix|Vector|Numo::NArray|BigDecimal)\b"),
            # 23. heat_triggers (Metaprogramming & Reflection)
            # Metaprogramming and runtime object extensions.
            "reflection_metaprogramming": re.compile(
                r"\b(method_missing|define_method|const_missing|respond_to_missing\?|included|extended|prepended|class\s*<<\s*self)\b"
            ),
            # 24. import (Dependency Inclusions)
            "import": re.compile(r"\b(?:require|require_relative|load|autoload)\b[^'\"]*['\"]", re.M),
            "_dependency_capture": re.compile(
                # =====================================================================
                # [ FUTURE LLM CONTEXT: THE DYNAMIC EXECUTION SHIFT (RUBY) ]
                # PURPOSE: Extracts external dependencies for the Network Graph and Supply Chain Firewall.
                #
                # HISTORICAL BUG: Originally, this regex was anchored to the start of the
                # line `^[ \t]*`. While this perfectly prevented hallucinations on commented-out
                # imports, it completely blinded the firewall to Ruby's highly dynamic execution
                # patterns. Ruby developers frequently lazy-load dependencies inside methods
                # (e.g., `def parse; require 'json'; end`) or behind conditionals. The anchored
                # regex missed these entirely, allowing Trojans to slip through.
                #
                # THE FIX: The `^` anchor has been stripped. We now rely on the `\b` word
                # boundary to find the keywords anywhere in the file.
                #
                # [ THE OPTIONAL PARENTHESIS & AUTOLOAD SHIELD ]
                # Ruby methods do not require parentheses (e.g., `require 'json'` vs `require('json')`).
                # Additionally, `autoload` takes a symbol before the path (e.g., `autoload :MyMod, 'path'`).
                # By injecting `[^'\"]*` between the keyword and the string delimiter, the engine
                # safely bridges across optional parentheses, whitespace, and `autoload` symbol arguments
                # to securely capture the target string.
                # =====================================================================
                r"\b(?:require|require_relative|load|autoload)\b[^'\"]*['\"]([^'\"]+)['\"]",
                re.M,
            ),
            # 25. ownership (Authorship Metadata)
            "ownership": re.compile(r"#\s*(?:Author|Created by|Maintainer|Copyright):\s+(.*)", re.I),
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            # 26. planned_debt (Annotated Debt / TODOs)
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            # 29. spec_exposure (Spec / Audit Traceability)
            "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]", re.I),
            # 30. tabs_vs_spaces (Formatting Inconsistencies) 
            "tabs_vs_spaces": None,
            # 31. ssr_boundaries (Server-Side Rendering)
            "ssr_boundaries": re.compile(
                r"\b(ActionController::Base|ActionController::API|Sinatra::Base|Hanami::Action|respond_to|format\.html|format\.json)\b"
            ),
            # 32. events (Event Emitters / Pub-Sub)
            "events": re.compile(r"\b(Wisper|broadcast|subscribe|ActiveSupport::Notifications\.instrument|publish)\b"),
            # 33. dependency_injection (Dependency Injection / IoC)
            "dependency_injection": re.compile(r"\b(Dry::Container|Dry::AutoInject|include\s+Import|inject)\b"),
            # 34. macros (Preprocessor Directives / Macros)
            # Ruby DSL macros.
            "macros": re.compile(
                r"^[ \t]*(?:attr_accessor|attr_reader|attr_writer|scope|delegate)\b",
                re.M,
            ),
            # 35. pointers (Pointer Arithmetic / Memory Addressing)
            "pointers": re.compile(r"\b(FFI::Pointer|Fiddle::Pointer|Fiddle::Function)\b"),
            # 36. memory_alloc (Manual Memory Management)
            "memory_alloc": re.compile(r"\b(ObjectSpace|GC\.start|GC\.disable|GC\.enable|FFI::MemoryPointer)\b"),
            # 37. inline_asm
            "inline_asm": None,
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # 38. telemetry (Structured Logging / Telemetry)
            "telemetry": re.compile(
                r"\b(?:Rails\.logger|Logger\.new|SemanticLogger|[a-zA-Z_]\w*logger)\.(?:debug|info|warn|error|fatal|unknown)\b"
            ),
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
            "debug_prints": re.compile(r"\b(puts|print|p|pp|warn)\b"),
            # # 40. explicit_casts (Explicit Type Casting)
            "explicit_casts": re.compile(r"\b(Integer|Float|String|Array|Hash|Complex|Rational)\b\s*\("),
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
            "panics_and_aborts": re.compile(r"\b(raise|fail|abort|exit!)\b"),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
            "thread_sleeps": re.compile(r"\bsleep\b\s*[0-9.]+"),
            # 43. bitwise_ops (Bitwise Operations)
            "bitwise_ops": re.compile(r"\^|(?<![=!])~"),
            # 44. sync_locks (Resource Management & Stability)
            "sync_locks": re.compile(r"\b(mutex|lock|synchronized|Semaphore|Monitor|Atomic[A-Z]\w*)\b", re.I),
            # 45. immutability_locks (Immutability Constraints)
            "immutability_locks": re.compile(r"\b(freeze|frozen_string_literal|immutable)\b"),
            # 46. cleanup (Resource Cleanup / Teardown)
            "cleanup": re.compile(r"\b(close|GC\.start|dispose|shutdown|cleanup)\b\s*\("),
            # 47. encapsulation (Access Modifiers / Encapsulation)
            # Visibility modifiers in Ruby.
            "encapsulation": re.compile(r"\b(private|protected)\b"),
            # 48. listeners (Event Listeners / Observers)
            "listeners": re.compile(r"\.subscribe\(|\.on\(|addEventListener"),
            # 49. test_skip (Bypassed Tests / Ignored Specs)
            "test_skip": re.compile(r"\b(skip|xit|xdescribe|mock|stub|double)\b"),
            # --- PHASE 3: HYBRID DOMAIN SENSORS (Ruby Specifics) ---
            "serialization_parsing": re.compile(r"\b(JSON\.parse|YAML\.load|Marshal\.load|Nokogiri::(?:XML|HTML))\b"),
            "regex_execution": re.compile(r"\b(Regexp\.new)\b|\.(match|scan|gsub|sub)\b|=~"),
            "time_date_logic": re.compile(r"\b(Time\.now|Date\.today|DateTime\.now|sleep)\b"),
            "ipc_rpc_bridges": re.compile(r"\b(Open3|system\s*\(|IO\.popen|Net::HTTP|TCPSocket|%x\{)\b"),
        },
    },
    "swift": {
        "_meta": {
            "target_version": "Swift 6.2 / iOS 18+ / Strict Concurrency, Macros & Swift Testing",
            "last_updated": "2026-02-18",
            "blueprint_version": "v5.0",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard sources and module interface declarations.
        "extensions": [".swift", ".swiftinterface"],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: Tooling configurations that are secretly pure Swift code.
        "exact_matches": ["Package.swift"],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions and package manager lockfiles to resolve ambiguous files in mixed Apple environments.
        "discriminators": [".swift", "Package.resolved", "project.pbxproj"],
        # EXECUTION SIGNATURES: Interpreters found on Line 1 for Swift-based scripting and automation.
        "shebangs": ["swift", "swift-sh"],
        # UPGRADED: Maps to Family 2 (Nested C)
        # Rationale: Supports nested block comments (/* /* */ */), necessitating depth-aware stripping
        # rather than standard C-style early termination.
        "lexical_family": "recursive_block",
        "rules": {
            # --- LEXICAL DELIMITER CONTROLS ---
            # Standard C-family line comment token
            "_line_anchor": re.compile(r"//"),
            # Inline comments follow the same '//' delimiter.
            "_inline_comment": re.compile(r"//"),
            # REQUIRED for Family 2: Recursive logic markers
            "_block_start": re.compile(r"/\*"),
            # REQUIRED for Family 2: Recursive logic markers
            "_block_end": re.compile(r"\*/"),
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # 1. branch (Control Flow / Branching)
            # Decisions and logical jumps. Includes modern typed throws (throws(Error)).
            # EXCLUDES throw/rethrows (bailout_hits).
            "branch": re.compile(
                r"\b(if|else|guard|switch|case|default|for|while|repeat|do|catch|break|continue|defer|try)\b|&&|\|\||\?|\?\?"
            ),
            # 2. args (Parameters / Coupling)
            # Parameter blocks. Bounded negation [^)]* and <[^>]*> to prevent ReDoS.
            "args": re.compile(
                # =====================================================================
                # [ THE ESCAPING CLOSURE SHIELD (SWIFT) ]
                # Swift functions often take escaping closures `(Result<Void, Error>) -> Void`
                # as parameters. The inner `()` breaks the `[^)]*` matcher.
                # FIX: Upgraded horizontal spaces to `[ \t\n]+` to allow vertical jumps,
                # and injected the 1-Level Nesting Trick `(?:[^)(]+|\([^)]*\))*` to safely
                # capture the entire parameter block without ReDoS.
                # =====================================================================
                r"\b(?:func|init\??|subscript)[ \t\n]*(?:[a-zA-Z_]\w*)?(?:[ \t\n]*<[^>]*>)?[ \t\n]*\((?:[^)(]|\([^)]*\))*\)|\{[ \t\n]*(?:\[[^\]]*\][ \t\n]*)?(?:\([^)]*\)|[a-zA-Z_]\w*(?:[ \t\n]*,[ \t\n]*[a-zA-Z_]\w*){0,50})[ \t\n]+in\b",
                re.M,
            ),
            # 3. linear (Sequential Boundaries)
            # Structural boundaries. EXCLUDES: Access modifiers (encapsulation) and let (freeze_hits).
            "structural_boundaries": re.compile(
                r"\b(var|struct|class|enum|protocol|extension|actor|macro|import|typealias|associatedtype|some|any|consume|borrow|discard|mutating|nonmutating|isolated|nonisolated|return|yield|await|inout)\b|~Copyable"
            ),
            # 4. func_start (Executable Logic Anchors)
            # ONLY executable logic blocks. EXCLUDES types/classes. Steps over Concurrency modifiers.
            "func_start": re.compile(
                # =====================================================================
                # [ THE VERTICAL ATTRIBUTE & GENERICS SHIELD ]
                # Swift allows heavy modifier stacking and disconnected generics.
                # FIX: Upgraded horizontal `[ \t]+` spaces to vertical `[ \t\n]+` across
                # decorators and modifiers, and safely detached the generic stepper
                # `(?:[ \t\n]*<[^>]*>)?` from the function name capture.
                # =====================================================================
                r"^[ \t]*(?:@[\w.]+(?:\([^)]*\))?[ \t\n]*){0,5}"
                r"(?:(?:public|private|fileprivate|internal|open|package|override|final|static|class|mutating|nonmutating|isolated|nonisolated(?:\(unsafe\))?|distributed|required|convenience)[ \t\n]+){0,5}"
                r"(?:func[ \t\n]+([a-zA-Z_]\w*)(?:[ \t\n]*<[^>]*>)?|(init\??)|(subscript))(?=[ \t\n]*\()",
                re.M,
            ),
            # 5. class_start (Object / Entity Declarations)
            "class_start": re.compile(
                r"^[ \t]*(?:@[\w.]+(?:\([^)]*\))?[ \t]*){0,5}(?:(?:public|private|fileprivate|internal|open|package|final|distributed)[ \t]+){0,5}(?:class|struct|enum|protocol|actor|extension|macro)\s+[a-zA-Z_]\w*",
                re.M,
            ),
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            # 6. safety (Defensive Programming / Validation)
            "safety": re.compile(
                r"\b(guard\s+let|if\s+let|guard\s+var|if\s+var|try\?|as\?|catch|is|Sendable|Result|assert|precondition|Mutex)\b|@MainActor|\?\?"
            ),
            # 7. safety_neg (Safety Bypasses / Unchecked Types)
            # Unsafe pointers and linter bypasses. EXCLUDES forced unwraps (moved to friction).
            "safety_bypasses": re.compile(
                r"\bunowned(?:\(unsafe\))?\b|\bnonisolated\(unsafe\)|\bunsafeDowncast\b|//\s*swiftlint:disable"
            ),
            # 8. danger (High-Risk Execution / System Calls)
            # Fatal traps and process killers. EXCLUDES TODO (debt) and print (print_hits).
            "high_risk_execution": re.compile(r"\b(fatalError|preconditionFailure|assertionFailure|abort|exit)\b"),
            # 9. io (I/O & Network Boundaries)
            "io": re.compile(
                r"\b(URLSession|FileManager|FileHandle|Data\(contentsOf:|write\(to:|UserDefaults|CoreData|SwiftData|NWConnection)\b"
            ),
            # 10. api (Public Surface Area)
            # Exposed surface area. Explicit visibility and Objective-C bridges.
            "api": re.compile(
                r"\b(public|open|package|@usableFromInline|@objc|@objcMembers|@_exported|@IBAction|@IBOutlet|@Published)\b"
            ),
            # 11. flux (State Mutation)
            # Mutation of state. EXCLUDES let (freeze_hits).
            "state_mutation": re.compile(
                r"\b(var|inout|mutating|didSet|willSet|_modify)\b|@(?:State|Binding|FocusState|Bindable|Observable)|^[ \t]*(?:self\.)?[a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*){0,5}\s*[-+*/]?=|\.(?:append|insert|remove|toggle|updateValue)\("
            ),
            # 12. dead_code (Commented Logic / Deprecated Trails)
            "dead_code": re.compile(r"//[ \t]*(?:let|var|func|class|struct|actor|extension|if|guard|return)\b"),
            # 13. doc (Structured Documentation)
            "doc": re.compile(r"///|/\*\*|-\s*parameter|-\s*returns:|-\s*throws:|-\s*warning:"),
            # 14. test (Testing & Assertions)
            "test": re.compile(
                r"\b(?:XCTest|XCTestCase|XCTAssert[A-Za-z]*|setUp|tearDown)\b|@(?:Test|Suite)\b|#(?:expect|require)\b"
            ),
            # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
            # 15. concurrency (Asynchronous Execution)
            "concurrency": re.compile(
                r"\b(async|await|actor|Task|TaskGroup|DispatchQueue|OperationQueue|MainActor|Sendable|isolated|nonisolated|continuation)\b"
            ),
            # 16. ui_framework (UI / View Components)
            "ui_framework": re.compile(
                r"\b(View|Body|ZStack|VStack|HStack|Text|Image|Button|SwiftUI|UIKit|AppKit|UIView|UIViewController|NSView|NSWindow|@State|@Binding|@Environment)\b"
            ),
            # 17. closures (Closures / Anonymous Functions)
            "closures": re.compile(
                r"completion:[ \t]*\{|\{\s*(?:\[[^\]]*\]\s*)?(?:\([^)]*\)|[a-zA-Z_]\w*(?:[ \t\n]*,[ \t\n]*[a-zA-Z_]\w*){0,50})[ \t\n]+in\b"
            ),
            # 18. globals (Global / Shared State)
            "globals": re.compile(
                r"\b(?:static\s+let|static\s+var|shared|standard|default|NotificationCenter\.default|UserDefaults\.standard|FileManager\.default)\b|@Environment\b"
            ),
            # 19. decorators (Decorators / Annotations)
            "decorators": re.compile(r"@[a-zA-Z_]\w*(?:\([^)]*\))?"),
            # 20. generics (Generics / Type Parameters)
            "generics": re.compile(r"<\s*[A-Z][^>]*>|\bwhere\s+[a-zA-Z_]\w*\s*:|\b(?:some|any|each)\s+[A-Z]\w*"),
            # 21. comprehensions (Iterators / Comprehensions)
            "comprehensions": re.compile(
                r"\.(?:map|compactMap|flatMap|filter|reduce|forEach|allSatisfy|contains)\s*(?:\(|\{)"
            ),
            # 22. scientific (Numerical / Compute Libraries)
            "scientific": re.compile(
                r"\b(simd|Accelerate|Double|Float|Float16|CGFloat|Decimal|CoreML|CreateML|vDSP|sqrt|pow|sin|cos|tan)\b"
            ),
            # 23. heat_triggers (Metaprogramming & Reflection)
            # Reflection and Dynamic Dispatch.
            "reflection_metaprogramming": re.compile(
                r"\b(@objc|dynamic|Mirror\(|unsafeBitCast|withUnsafe\w+|KeyPath|WritableKeyPath)\b|\\\.[\w.]+"
            ),
            # 24. import (Dependency Inclusions)
            "import": re.compile(r"^[ \t]*(?:@_exported[ \t]+)?import\s+[a-zA-Z_]\w*", re.M),
            "_dependency_capture": re.compile(
                r"^[ \t]*(?:@_exported[ \t]+)?import\s+(?:(?:typealias|struct|class|enum|protocol|let|var|func)\s+)?([a-zA-Z_][\w.]+)",
                re.M,
            ),
            # 25. ownership (Authorship Metadata)
            "ownership": re.compile(r"//\s*(?:Created by|Author:|Copyright):\s+(.*)", re.I),
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            # 26. planned_debt (Annotated Debt / TODOs)
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            # 29. spec_exposure (Spec / Audit Traceability)
            "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]", re.I),
            # 30. tabs_vs_spaces (Formatting Inconsistencies) 
            "tabs_vs_spaces": None,
            # 31. ssr_boundaries (Server-Side Rendering)
            "ssr_boundaries": re.compile(
                r"\b(Vapor|Hummingbird|Request|Response|Route|app\.get|app\.post|EventLoopFuture)\b"
            ),
            # 32. events (Event Emitters / Pub-Sub)
            "events": re.compile(
                r"\b(NotificationCenter|Combine|Publisher|Subscriber|CurrentValueSubject|PassthroughSubject|AnyCancellable|\.sink|\.assign|@Published|ObservableObject|Observation)\b"
            ),
            # 33. dependency_injection (Dependency Injection / IoC)
            "dependency_injection": re.compile(
                r"\b(@Environment|@EnvironmentObject|@Inject|@Dependency|Swinject|Container|Resolver|Factory)\b"
            ),
            # 34. macros (Preprocessor Directives / Macros)
            "macros": re.compile(
                r"#(?:Preview|Predicate|OptionSet|Rule|warning|error)\b|@(?:freestanding|attached)|#[A-Z]\w*"
            ),
            # 35. pointers (Pointer Arithmetic / Memory Addressing)
            "pointers": re.compile(
                r"\b(?:Unsafe(?:Mutable)?(?:Raw|Buffer)?Pointer|OpaquePointer|CVaListPointer|Unmanaged)\b|\.pointee\b|(?<=[=\s,(])&\w+"
            ),
            # 36. memory_alloc (Manual Memory Management)
            "memory_alloc": re.compile(
                r"\b(?:malloc|calloc|free|\.allocate\(capacity:|\.deallocate\(\)|ManagedBuffer)\b"
            ),
            # 37. inline_asm
            "inline_asm": None,  # Swift delegates ASM to C-headers.
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # 38. telemetry (Structured Logging / Telemetry)
            "telemetry": re.compile(
                r"\b(?:Logger|OSLog|os_log)\b|\bLogger\([^)]*\)\.(?:info|error|warning|debug|trace|notice|critical|fault)\b",
                re.I,
            ),
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
            "debug_prints": re.compile(r"\b(print|debugPrint|dump)\b"),
            # # 40. explicit_casts (Explicit Type Casting)
            "explicit_casts": re.compile(
                r"\bas[!?]?\s+[A-Z]\w*|\bis\s+[A-Z]\w*|\b(?:Int|Double|Float|Float16|CGFloat|String|Bool)\s*\("
            ),
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
            "panics_and_aborts": re.compile(r"\b(throw|fatalError|abort|exit|preconditionFailure)\b"),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
            "thread_sleeps": re.compile(r"\b(sleep|delay|Task\.sleep)\b"),
            # 43. bitwise_ops (Bitwise Operations)
            "bitwise_ops": re.compile(r"<<|>>|\^|(?<![=!])~|<<=|>>=|\^="),
            # 44. sync_locks (Resource Management & Stability)
            "sync_locks": re.compile(
                r"\b(mutex|lock|synchronized|Semaphore|OSAllocatedUnfairLock|MainActor|distributed)\b",
                re.I,
            ),
            # 45. immutability_locks (Immutability Constraints)
            "immutability_locks": re.compile(r"\b(let|final|static|readonly|Immutable|Sendable)\b"),
            # 46. cleanup (Resource Cleanup / Teardown)
            "cleanup": re.compile(r"\b(deinit|close|free|dispose|shutdown|removeAll)\b\s*\("),
            # 47. encapsulation (Access Modifiers / Encapsulation)
            "encapsulation": re.compile(r"\b(private|fileprivate|internal)\b"),
            # 48. listeners (Event Listeners / Observers)
            "listeners": re.compile(r"\.onAppear\(|\.onChange\(|\.sink\(|addObserver|subscribe"),
            # 49. test_skip (Bypassed Tests / Ignored Specs)
            "test_skip": re.compile(r"\b(XCTSkip|mock\(|stub\(|fake\(|double\()\b"),
            # --- PHASE 3: HYBRID DOMAIN SENSORS (Swift Specifics) ---
            "serialization_parsing": re.compile(
                r"\b(JSONDecoder|JSONEncoder|PropertyListSerialization|NSKeyedUnarchiver|XMLParser)\b"
            ),
            "regex_execution": re.compile(
                r"\b(NSRegularExpression|Regex|try\s+Regex|\.range\(of:.*\.regularExpression)\b"
            ),
            "time_date_logic": re.compile(
                r"\b(Date\(\)|Calendar\.current|DateFormatter|DispatchTime\.now|Timer\.scheduledTimer)\b"
            ),
            "ipc_rpc_bridges": re.compile(
                r"\b(URLSession|NSXPCConnection|Process\(\)|NotificationCenter|DispatchQueue)\b"
            ),
        },
    },
    "kotlin": {
        "_meta": {
            "target_version": "Kotlin 2.3.10 (K2 Compiler / Wasm / Java 25 Support)",
            "last_updated": "2026-03-12",
            "blueprint_version": "v6.3.1",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard sources, Kotlin script files (heavily used in modern Gradle), and module declarations.
        "extensions": [".kt", ".kts", ".ktm"],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: Kotlin rarely uses extensionless execution scripts.
        "exact_matches": [],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions and Kotlin-DSL Gradle build files to lock in context.
        "discriminators": [
            ".kt",
            "build.gradle.kts",
            "settings.gradle.kts",
            "gradle.properties",
        ],
        # EXECUTION SIGNATURES: Interpreters found on Line 1 for Kotlin scripting.
        "shebangs": ["kotlin", "kotlinc", "kscript"],
        # UPGRADED: Maps to Family 2 (Nested C)
        # Rationale: (CORRECTION) While Kotlin uses // and /* */, it officially allows nested
        # block comments (/* /* */ */). Using standard C parsing would cause early termination here.
        "lexical_family": "standard_block",
        "rules": {
            # --- LEXICAL DELIMITER CONTROLS ---
            # Standard C-family line comment token
            "_line_anchor": re.compile(r"//"),
            # Inline comments follow the same '//' delimiter.
            "_inline_comment": re.compile(r"//"),
            # Block comment start: /*
            "_block_start": re.compile(r"/\*"),
            # Block comment end: */
            "_block_end": re.compile(r"\*/"),
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # 1. branch (Control Flow / Branching)
            # Decisions and logical jumps. Includes modern 'when' and Elvis operator.
            # EXCLUDES throw (bailout_hits).
            "branch": re.compile(
                r"\b(if|else|when|for|while|do|try|catch|finally|break|continue|return)\b|\?:|&&|\|\|"
            ),
            # 2. args (Parameters / Coupling)
            # OPTIMIZED: Removed overlapping whitespace quantifiers to fix Regex Sludge.
            "args": re.compile(
                # =====================================================================
                # [ THE LAMBDA PARAMETER SHIELD (KOTLIN) ]
                # Kotlin default arguments `emptyList()` and lambda parameters `(Result<T>) -> Unit`
                # contain parentheses that shatter standard `[^)]*` boundaries.
                # FIX: Implemented the 1-Level Nesting Trick `(?:[^)(]+|\([^)]*\))*` to
                # absorb the inner parentheses. Upgraded spaces to `[ \t\n]*` for vertical layouts.
                # =====================================================================
                r"\b(?:fun|constructor)(?:[ \t\n]*<[^>]{0,100}>)?[ \t\n]*(?:[a-zA-Z_]\w*\.)?[a-zA-Z_]\w*[ \t\n]*\((?:[^)(]|\([^)]*\))*\)|\{[ \t\n]*[a-zA-Z_][a-zA-Z0-9_ \t\n:<>,.?]{0,150}?->",
                re.M,
            ),
            # 4. func_start (Executable Logic Anchors)
            # OPTIMIZED: Bound annotation parenthesis scanning to prevent multi-line bleeding.
            "func_start": re.compile(
                # =====================================================================
                # [ THE VERTICAL MODIFIER & GENERIC SHIELD (KOTLIN) ]
                # Kotlin allows annotations, modifiers, the 'fun' keyword, generics,
                # and the function name to be split across multiple lines.
                # FIX: Upgraded `[ \t]+` to `[ \t\n]+` across the decorator and modifier
                # stacks. Modified the generic stepper to `(?:<[^>]{0,100}>[ \t\n]*)?`
                # (removing the `\n` restriction) and updated the trailing lookahead
                # to `[ \t\n]*[\(\{]` so it can safely jump vertical gaps to the parameters.
                # =====================================================================
                r"^[ \t]*(?:@[\w.]+(?:\([^)\{]{0,300}\))?[ \t\n]*){0,10}"
                r"(?:(?:public|private|protected|internal|open|override|abstract|final|suspend|inline|tailrec|infix|operator|external|expect|actual)[ \t\n]+){0,5}"
                r"(?:context\s*\([^)]*\)\s*)?"
                r"(?:fun[ \t\n]+(?:<[^>]{0,100}>[ \t\n]*)?(?:[a-zA-Z_]\w*\.)?([a-zA-Z_]\w*)|(init)|(constructor))(?=[ \t\n]*[\(\{])",
                re.M,
            ),
            # 5. class_start (Object / Entity Declarations)
            # OPTIMIZED: Applied the same 300-char bounds to class annotations.
            "class_start": re.compile(
                r"^[ \t]*(?:@[\w.]+(?:\([^)\{]{0,300}\))?[ \t]*){0,10}(?:(?:public|private|protected|internal|open|abstract|final|sealed|data|value|annotation|expect|actual|inner)[ \t]+){0,5}(?:class|interface|object|enum\s+class)\s+[a-zA-Z_]\w*",
                re.M,
            ),
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            # 6. safety (Defensive Programming / Validation)
            "safety": re.compile(
                r"\?\.(?!.)|as\?|\b(require|requireNotNull|check|checkNotNull|error|sealed|is|!is|Result|onSuccess|onFailure|fold|runCatching)\b|\?:"
            ),
            # 7. safety_neg (Safety Bypasses / Unchecked Types)
            # Force unwrapping, unsafe casts, and suppression.
            "safety_bypasses": re.compile(r"!!|as(?!\?)\b|\blateinit\s+var\b|@Suppress\b"),
            # 8. danger (High-Risk Execution / System Calls)
            # Process killers and raw system triggers. EXCLUDES println (Phase 5).
            "high_risk_execution": re.compile(r"\b(System\.exit|exitProcess|Runtime\.getRuntime|Thread\.stop)\b"),
            # 9. io (I/O & Network Boundaries)
            "io": re.compile(
                r"\b(File|InputStream|OutputStream|Retrofit|OkHttpClient|Ktor|HttpClient|RoomDatabase|Dao|SharedPreferences|DataStore|java\.nio)\b"
            ),
            # 10. api (Public Surface Area)
            # Exposed surface. Implicit public/internal defaults + Ktor/Spring routes.
            "api": re.compile(
                r"\b(public|internal)\b|@(RestController|Controller|Service|Component|RequestMapping|GetMapping|PostMapping|Route)\b"
            ),
            # 11. flux (State Mutation)
            # CRITICAL FIX: Added re.M so it scans every line, not just the first line of the file!
            "state_mutation": re.compile(
                r"\b(var|MutableList|MutableMap|MutableSet|MutableState|MutableStateFlow|Atomic[A-Za-z0-9]+)\b|^[ \t]*(?:this\.)?[a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)*\s*[-+*/%]?=|\.(?:add|addAll|remove|put|set|update)\(",
                re.M,
            ),
            # 12. dead_code (Commented Logic / Deprecated Trails)
            "dead_code": re.compile(r"//[ \t]*(?:val|var|fun|class|interface|object|if|when|for|return|import)\b"),
            # 13. doc (Structured Documentation)
            "doc": re.compile(r"/\*\*|@param|@return|@property|@receiver|@constructor|@throws|@see|@since"),
            # 14. test (Testing & Assertions)
            "test": re.compile(
                r"@(?:Test|ParameterizedTest|BeforeTest|AfterTest)|\b(?:assert[A-Za-z0-9_]*|mockk|spyk|test)\s*\(|\b(?:shouldBe|shouldNotBe)\b|\b(?:every|verify)\s*\{"
            ),
            # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
            # 15. concurrency (Asynchronous Execution)
            "concurrency": re.compile(
                r"\b(suspend|launch|async|CoroutineScope|GlobalScope|Dispatchers|Flow|StateFlow|SharedFlow|Channel|yield|runBlocking|withContext|Mutex)\b"
            ),
            # 16. ui_framework (UI / View Components)
            "ui_framework": re.compile(
                r"@Composable|Modifier|\b(Column|Row|Box|Text|Image|Button|Scaffold|LazyColumn|LazyRow|Surface|remember|mutableStateOf|findViewById|View|Activity|Fragment)\b"
            ),
            # 17. closures (Closures / Anonymous Functions)
            # OPTIMIZED: Removed overlapping whitespace quantifiers to fix ReDoS.
            "closures": re.compile(r"\{[ \t\n]*[a-zA-Z_][a-zA-Z0-9_ \t\n:<>,.?]{0,150}?->"),
            # 18. globals (Global / Shared State)
            "globals": re.compile(
                r"\b(object|companion\s+object)\b|^[ \t]*(?:const[ \t]+)?val\s+[A-Z_0-9]+[ \t]*=",
                re.M,
            ),
            # 19. decorators (Decorators / Annotations)
            # OPTIMIZED: Bounded arguments.
            "decorators": re.compile(r"@[a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)*(?:\([^)\{]{0,300}\))?"),
            # 20. generics (Generics / Type Parameters)
            # Prevented catastrophic backtracking across newlines.
            "generics": re.compile(r"<\s*(?:in|out)?\s*[A-Z][^>\n]{0,100}>|\breified\b|\bwhere\b"),
            # 21. comprehensions (Iterators / Comprehensions)
            # Functional collection transformations.
            "comprehensions": re.compile(
                r"\.(?:map|mapNotNull|filter|filterNot|reduce|fold|flatMap|zip|associate|groupBy|forEach|any|all|none|find)\b"
            ),
            # 22. scientific (Numerical / Compute Libraries)
            "scientific": re.compile(
                r"\b(kotlin\.math\.|java\.lang\.Math\.|StrictMath\.|Random\.|sin|cos|tan|sqrt|exp|log|abs|BigDecimal|BigInteger)\b"
            ),
            # 23. heat_triggers (Metaprogramming & Reflection)
            # Reflection and optimization hooks.
            "reflection_metaprogramming": re.compile(
                r"::class|javaClass|@JvmOverloads|@JvmStatic|@JvmField|@JvmName|\b(inline|crossinline|noinline|invoke|context|tailrec)\b"
            ),
            # 24. import (Dependency Inclusions)
            "import": re.compile(r"^[ \t]*import\s+(?:static[ \t]+)?[\w.]+;?", re.M),
            "_dependency_capture": re.compile(r"^[ \t]*import[ \t\n]+(?:static[ \t\n]+)?([\w.*]+)", re.M),
            # 25. ownership (Authorship Metadata)
            "ownership": re.compile(
                r"@(?:author|since)\s+(.*)|//\s*(?:Created by|Maintainer|Copyright):\s+(.*)",
                re.I,
            ),
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            # 26. planned_debt (Annotated Debt / TODOs)
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            # 29. spec_exposure (Spec / Audit Traceability)
            "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]", re.I),
            # 30. tabs_vs_spaces (Formatting Inconsistencies) 
            "tabs_vs_spaces": None,
            # 31. ssr_boundaries (Server-Side Rendering)
            "ssr_boundaries": re.compile(
                r"\b(ApplicationCall|call\.respond|call\.respondText|call\.respondHtml|ServerResponse|ModelAndView)\b"
            ),
            # 32. events (Event Emitters / Pub-Sub)
            "events": re.compile(
                r"\.(?:collect|collectLatest|observe|subscribe|onNext)\(|\b(LiveData|Observer|Observable|FlowCollector)\b"
            ),
            # 33. dependency_injection (Dependency Injection / IoC)
            "dependency_injection": re.compile(
                r"@(?:Inject|Module|Provides|Binds|HiltViewModel|AndroidEntryPoint|Component|Autowired)|(?:koin|get|inject)\(\)"
            ),
            # 34. macros (Preprocessor Directives / Macros)
            "macros": re.compile(r"@(?:OptIn|RequiresOptIn|Suppress|SuppressWarnings)\b"),
            # 35. pointers (Pointer Arithmetic / Memory Addressing)
            # Kotlin/Native FFI boundaries.
            "pointers": re.compile(r"\b(?:CPointer|COpaquePointer|CFunction|CValue|CPointed)\b"),
            # 36. memory_alloc (Manual Memory Management)
            "memory_alloc": re.compile(r"\b(?:memScoped|alloc|allocArray|nativeHeap\.alloc|nativeHeap\.free)\b"),
            # 37. inline_asm
            "inline_asm": None,  # Usually bridged via C-headers in Native.
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # 38. telemetry (Structured Logging / Telemetry)
            "telemetry": re.compile(
                r"\b(?:Timber|Log|Logger|LoggerFactory)\.(?:i|e|w|d|v|info|error|warn|warning|debug|trace|verbose)\b|@Slf4j"
            ),
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
            "debug_prints": re.compile(r"\b(println|print)\b\s*\("),
            # # 40. explicit_casts (Explicit Type Casting)
            "explicit_casts": re.compile(
                r"\bas\??\s+[A-Z]\w*|\.to(?:Int|Long|Short|Byte|Double|Float|String|Boolean|UInt|ULong|UShort|UByte)\(\)"
            ),
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
            "panics_and_aborts": re.compile(r"\b(throw|raise|exitProcess|return|panic)\b"),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
            "thread_sleeps": re.compile(r"\b(delay|Thread\.sleep|yield)\b"),
            # 43. bitwise_ops (Bitwise Operations)
            "bitwise_ops": re.compile(r"\.(?:shl|shr|ushr|and|or|xor|inv)\(|\b(?:shl|shr|ushr|xor)\b"),
            # 44. sync_locks (Resource Management & Stability)
            "sync_locks": re.compile(r"\b(mutex|lock|synchronized|Semaphore|Atomic[A-Z]\w*)\b", re.I),
            # 45. immutability_locks (Immutability Constraints)
            "immutability_locks": re.compile(r"\b(val|const|immutable|readonly)\b"),
            # 46. cleanup (Resource Cleanup / Teardown)
            "cleanup": re.compile(r"\b(close|dispose|shutdown|use|cleanup)\b\s*\("),
            # 47. encapsulation (Access Modifiers / Encapsulation)
            "encapsulation": re.compile(r"\b(private|protected|internal)\b"),
            # 48. listeners (Event Listeners / Observers)
            "listeners": re.compile(r"\.(?:collect|observe|subscribe|on[A-Z]\w*|set[A-Z]\w*Listener)\("),
            # 49. test_skip (Bypassed Tests / Ignored Specs)
            "test_skip": re.compile(r"@(?:Ignore|Disabled)|test\.skip\(|mockk|spyK|fake\("),
            # --- PHASE 3: HYBRID DOMAIN SENSORS (Kotlin Specifics) ---
            "serialization_parsing": re.compile(
                r"\b(Json\.decodeFromString|Json\.encodeToString|Gson\(\)|Moshi|ObjectMapper)\b"
            ),
            "regex_execution": re.compile(r"\b(Regex\(\)|\.toRegex\(\)|\.matches\(|\.find\()\b"),
            "time_date_logic": re.compile(
                r"\b(Clock\.System\.now|Instant\.now|System\.currentTimeMillis|Duration\.minutes|LocalDate)\b"
            ),
            "ipc_rpc_bridges": re.compile(r"\b(Intent\(|BroadcastReceiver|HttpClient\(|ProcessBuilder|bindService)\b"),
        },
    },
    "sqlite": {
        "_meta": {
            "target_version": "SQLite 3.51.2+ (STRICT Tables, JSONB, RETURNING, Math & CTEs)",
            "last_updated": "2026-02-18",
            "blueprint_version": "v5.0",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard SQL scripts, data definition, and data manipulation files.
        "extensions": [".sql", ".ddl", ".dml"],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: Standard SQLite configuration and history files that consist of CLI commands/SQL.
        "exact_matches": [".sqliterc"],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: Binary database files acting as gravitational anchors to prove a .sql file is SQLite and not Postgres/MySQL.
        "discriminators": [
            ".sql",
            ".db",
            ".sqlite",
            ".sqlite3",
            ".db3",
            ".s3db",
            ".sl3",
        ],
        # EXECUTION SIGNATURES: Interpreters found on Line 1.
        "shebangs": ["sqlite3", "sqlite"],
        # UPGRADED: Maps to Family 5 (Hybrid Dash)
        # Rationale: Uses '--' for line-level and '/*' '*/' for block-level Commented / Non-Executable Text.
        "lexical_family": "standard_block",
        "rules": {
            # --- LEXICAL DELIMITER CONTROLS ---
            # SQLite uses '--' for standard line-level literature.
            "_line_anchor": re.compile(r"--"),
            # Inline comments are also triggered by the '--' token.
            "_inline_comment": re.compile(r"--"),
            # Block comment start: /*
            "_block_start": re.compile(r"/\*"),
            # Block comment end: */
            "_block_end": re.compile(r"\*/"),
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # 1. branch (Control Flow / Branching)
            # Decisions and logical filters. Includes case logic and modern IIF().
            "branch": re.compile(
                r"\b(CASE|WHEN|THEN|ELSE|END|IFNULL|NULLIF|COALESCE|IIF|FILTER|WHERE|HAVING)\b",
                re.I,
            ),
            # 2. args (Parameters / Coupling)
            # Parameter blocks and input coupling. Bounded to prevent ReDoS on massive IN clauses.
            # Now explicitly captures CTE scoped arguments: cte_name (col1, col2)
            "args": re.compile(
                r"\?[0-9]*|[:@$][a-zA-Z_]\w*|\b(?:VALUES|IN)\s*\([^)]*\)|^[ \t]*[a-zA-Z_]\w*[ \t\n]*\([^)]*\)[ \t\n]*AS[ \t\n]*\(",
                re.I | re.M,
            ),
            # 3. linear (Sequential Boundaries)
            # Structural boundaries defining query execution flow.
            "structural_boundaries": re.compile(
                r"\b(SELECT|FROM|JOIN|INNER\s+JOIN|LEFT\s+JOIN|CROSS\s+JOIN|GROUP\s+BY|ORDER\s+BY|LIMIT|OFFSET|UNION|INTERSECT|EXCEPT|RETURNING|AS|INTO|WINDOW|STRICT|WITHOUT\s+ROWID|PARTITION\s+BY|PRECEDING|FOLLOWING|UNBOUNDED|CURRENT\s+ROW)\b",
                re.I,
            ),
            # 4. func_start (Executable Logic Anchors)
            # Executable logic wrappers. EXCLUDES tables to avoid False Positives.
            "func_start": re.compile(
                # =====================================================================
                # [ THE VERTICAL MODIFIER SHIELD (SQLITE) ]
                # SQL developers frequently format DDL statements across multiple lines,
                # stacking `CREATE`, `TEMPORARY TRIGGER`, and `IF NOT EXISTS` vertically.
                # FIX: Upgraded the `\s+` and `[ \t]+` modifier bounds to `[ \t\n]+`.
                # Critically, the `IF NOT EXISTS` block previously failed to capture
                # the vertical gap, causing the engine to capture `IF` as the target name.
                # =====================================================================
                r"^[ \t]*CREATE[ \t\n]+(?:TEMP|TEMPORARY)?[ \t\n]*(?:UNIQUE[ \t\n]+)?(?:TRIGGER|VIEW|INDEX)[ \t\n]+"
                r"(?:IF[ \t\n]+NOT[ \t\n]+EXISTS[ \t\n]+)?([a-zA-Z_]\w*)(?=[ \t\(\n;]|$)",
                re.I | re.M,
            ),
            # 5. class_start (Object / Entity Declarations)
            # Physical entity instantiation (Tables).
            "class_start": re.compile(
                r"^[ \t]*CREATE\s+(?:TEMP|TEMPORARY)?\s*(?:VIRTUAL[ \t]+)?TABLE\s+"
                r"(?:IF\s+NOT\s+EXISTS[ \t]+)?([a-zA-Z_]\w*)(?=[ \t\(\n;])",
                re.I | re.M,
            ),
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            # 6. safety (Defensive Programming / Validation)
            "safety": re.compile(
                r"\b(TRANSACTION|COMMIT|ROLLBACK|SAVEPOINT|RELEASE|CONSTRAINT|CHECK|UNIQUE|PRIMARY\s+KEY|FOREIGN\s+KEY|STRICT|IF\s+NOT\s+EXISTS|ON\s+DELETE\s+CASCADE|PRAGMA\s+foreign_keys[ \t]*=\s*(?:1|ON))\b",
                re.I,
            ),
            # 7. safety_neg (Safety Bypasses / Unchecked Types)
            # Bypassing safety checks and structural removals.
            "safety_bypasses": re.compile(
                r"\b(DROP\s+TABLE|DROP\s+VIEW|DROP\s+INDEX|PRAGMA\s+foreign_keys[ \t]*=\s*(?:0|OFF)|PRAGMA\s+writable_schema[ \t]*=\s*(?:1|ON)|PRAGMA\s+ignore_check_constraints[ \t]*=\s*(?:1|ON)|IF\s+EXISTS)\b",
                re.I,
            ),
            # 8. danger (High-Risk Execution / System Calls)
            # Destructive schema actions and system bypasses.
            "high_risk_execution": re.compile(r"\b(PRAGMA\s+legacy_alter_table|DROP\s+DATABASE|\.shell|\.system|\.exit|\.quit)\b"),
            # 9. io (I/O & Network Boundaries)
            "io": re.compile(
                r"\b(SELECT|INSERT|UPDATE|DELETE|REPLACE|ATTACH\s+DATABASE|DETACH\s+DATABASE|\.import|\.output|\.dump|\.read|readfile|writefile)\b",
                re.I,
            ),
            # 10. api (Public Surface Area)
            # Exposed surface area (Views and Virtual Tables).
            "api": re.compile(
                r"^[ \t]*CREATE\s+(?:TEMP|TEMPORARY)?\s*(?:VIEW|VIRTUAL\s+TABLE)\s+",
                re.I | re.M,
            ),
            # 11. flux (State Mutation)
            # Mutation of state. Includes UPSERT.
            "state_mutation": re.compile(
                r"\b(UPDATE|SET|ALTER\s+TABLE|ADD\s+COLUMN|DROP\s+COLUMN|RENAME\s+TO|UPSERT|ON\s+CONFLICT\s+DO\s+UPDATE|ON\s+CONFLICT\s+DO\s+NOTHING|REPLACE\s+INTO|EXCLUDED\.[a-zA-Z_]\w*|jsonb?_(?:insert|replace|set|remove|patch))\b",
                re.I,
            ),
            # 12. dead_code (Commented Logic / Deprecated Trails)
            "dead_code": re.compile(
                r"--[ \t]*(?:SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|PRAGMA)\b",
                re.I,
            ),
            # 13. doc (Structured Documentation)
            "doc": re.compile(r"--\s*@(?:param|return|brief|table|column)|/\*\*|--\s*Description:"),
            # 14. test (Testing & Assertions)
            "test": re.compile(
                r"\b(?:EXPLAIN[ \t]+QUERY[ \t]+PLAN|PRAGMA[ \t]+integrity_check|PRAGMA[ \t]+foreign_key_check|\.testcase|\.lint)\b",
                re.I,
            ),
            # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
            # 15. concurrency (Asynchronous Execution)
            "concurrency": re.compile(
                r"\b(BEGIN\s+EXCLUSIVE|BEGIN\s+IMMEDIATE|PRAGMA\s+journal_mode[ \t]*=\s*WAL|PRAGMA\s+busy_timeout|PRAGMA\s+synchronous|PRAGMA\s+wal_checkpoint)\b",
                re.I,
            ),
            # 16. ui_framework
            "ui_framework": None,
            # 17. closures (Closures / Anonymous Functions)
            # SQLite does not support functional closures/lambdas. (CTEs are structural boundaries/loops).
            "closures": None,
            # 18. globals (Global / Shared State)
            "globals": re.compile(
                r"\b(sqlite_master|sqlite_schema|sqlite_sequence|sqlite_temp_schema|sqlite_stat\d+|PRAGMA\s+global_)\b",
                re.I,
            ),
            # 19. decorators (Decorators / Annotations)
            # Optimizer hints.
            "decorators": re.compile(
                r"\b(?:INDEXED\s+BY|NOT\s+INDEXED|MATERIALIZED|NOT\s+MATERIALIZED)\b",
                re.I,
            ),
            # 20. generics (Generics / Type Parameters)
            "generics": re.compile(r"\bANY\b|\bCAST\s*\([^)]*\)", re.I),
            # 21. comprehensions (Iterators / Comprehensions)
            # JSON iterations and windowing.
            "comprehensions": re.compile(
                r"\b(json_each|json_tree|json_group_array|json_group_object|OVER\s*\([^)]*\))\b",
                re.I,
            ),
            # 22. scientific (Numerical / Compute Libraries)
            "scientific": re.compile(
                r"\b(abs|acos|asin|atan|ceil|cos|degrees|exp|floor|ln|log|pi|pow|radians|sin|sqrt|tan|random|match|bm25|snippet|highlight|rtree|geopoly_[a-z_]+)\b",
                re.I,
            ),
            # 23. heat_triggers (Metaprogramming & Reflection)
            # Recursive logic and JSON paths.
            "reflection_metaprogramming": re.compile(
                r"\b(WITH\s+RECURSIVE|GENERATED\s+ALWAYS\s+AS|STORED|VIRTUAL)\b|->>|->|\b(?:json_extract|jsonb_extract)\b",
                re.I,
            ),
            # 24. import (Dependency Inclusions)
            "import": re.compile(
                r"\b(ATTACH\s+DATABASE|load_extension)\b|^[ \t]*\.(?:read|load|import)\s+",
                re.I | re.M,
            ),
            "_dependency_capture": re.compile(
                r"\bATTACH\s+(?:DATABASE\s+)?['\"]?([^'\"\s;]+)['\"]?\s+AS|\bload_extension\s*\(\s*['\"]([^'\"]+)['\"]|^[ \t]*\.(?:read|load|import)\s+['\"]?([^'\"\s]+)['\"]?",
                re.I | re.M,
            ),
            # 25. ownership (Authorship Metadata)
            "ownership": re.compile(r"--\s*(?:Author|Created by|Maintainer|Copyright):\s+(.*)", re.I),
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            # 26. planned_debt (Annotated Debt / TODOs)
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            # 29. spec_exposure (Spec / Audit Traceability)
            "spec_exposure": re.compile(r"--\s*\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]", re.I),
            # 30. tabs_vs_spaces (Formatting Inconsistencies) 
            "tabs_vs_spaces": None,
            # 31. ssr_boundaries
            "ssr_boundaries": None,
            # 32. events (Event Emitters / Pub-Sub)
            "events": re.compile(
                r"\b(CREATE\s+TRIGGER|AFTER\s+UPDATE|AFTER\s+INSERT|AFTER\s+DELETE|BEFORE\s+UPDATE|BEFORE\s+INSERT|BEFORE\s+DELETE|INSTEAD\s+OF)\b",
                re.I,
            ),
            # 33. dependency_injection (Dependency Injection / IoC)
            "dependency_injection": re.compile(
                r"\b(?:sqlite3_load_extension|SELECT\s+load_extension)\b|^[ \t]*\.load\b",
                re.I | re.M,
            ),
            # 34. macros (Preprocessor Directives / Macros)
            "macros": re.compile(
                r"\b(PRAGMA\s+compile_options|sqlite_compileoption_used)\b|^[ \t]*\.parameter\s+(?:set|init)\b",
                re.I | re.M,
            ),
            # 35. pointers (Pointer Arithmetic / Memory Addressing)
            "pointers": None,
            # 36. memory_alloc (Manual Memory Management)
            "memory_alloc": re.compile(
                r"\bPRAGMA\s+(?:mmap_size|cache_size|temp_store|page_size|shrink_memory)\b",
                re.I,
            ),
            # 37. inline_asm
            "inline_asm": None,
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # 38. telemetry (Structured Logging / Telemetry)
            "telemetry": re.compile(
                r"\b(?:sqlite_stat1|sqlite_stat4|ANALYZE)\b|^[ \t]*\.(?:trace|log|show|stats|timer)\b",
                re.I | re.M,
            ),
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
            "debug_prints": re.compile(
                r"\b(?:disp|warning|fprintf(?![ \t]*\([ \t]*[a-zA-Z_]))\b|^\.print\b|^\.echo\b",
                re.I | re.M,
            ),
            # # 40. explicit_casts (Explicit Type Casting)
            "explicit_casts": re.compile(r"\bCAST[ \t]*\([^)]+[ \t]+AS[ \t]+[a-zA-Z_]+\s*\)", re.I),
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
            "panics_and_aborts": re.compile(r"\b(ABORT|RAISE|EXIT|QUIT)\b|\.exit|\.quit", re.I),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
            "thread_sleeps": re.compile(r"\bPRAGMA\s+busy_timeout\b|\.pause", re.I),
            # 43. bitwise_ops (Bitwise Operations)
            "bitwise_ops": re.compile(r"<<|>>|\^|~|(?<!\|)\|(?!\|)"),
            # 44. sync_locks (Resource Management & Stability)
            "sync_locks": re.compile(r"\b(BEGIN\s+EXCLUSIVE|BEGIN\s+IMMEDIATE|PRAGMA\s+synchronous)\b", re.I),
            # 45. immutability_locks (Immutability Constraints)
            "immutability_locks": re.compile(r"\b(STRICT|WITHOUT\s+ROWID|CONSTANT|READONLY)\b", re.I),
            # 46. cleanup (Resource Cleanup / Teardown)
            "cleanup": re.compile(r"\b(DROP\s+TABLE|VACUUM|DETACH|CLOSE|CLEAR|DELETE\s+FROM)\b", re.I),
            # 47. encapsulation (Access Modifiers / Encapsulation)
            # Temporary/Local scopes and hidden columns.
            "encapsulation": re.compile(r"\b(TEMP|TEMPORARY|HIDDEN)\b", re.I),
            # 48. listeners (Event Listeners / Observers)
            "listeners": re.compile(r"\b(BEFORE\s+|AFTER\s+|INSTEAD\s+OF)\b", re.I),
            # 49. test_skip (Bypassed Tests / Ignored Specs)
            "test_skip": re.compile(r"\.testcase\s+skip|\bPRAGMA\s+ignore_check_constraints\b", re.I),
            # --- PHASE 3: HYBRID DOMAIN SENSORS (SQLite / SQL Specifics) ---
            "serialization_parsing": re.compile(
                r"(?i)\b(json_extract|json_tree|json_each|json_object|json_array|json_type)\b"
            ),
            "regex_execution": re.compile(r"(?i)\b(REGEXP|GLOB|LIKE|MATCH)\b"),
            "time_date_logic": re.compile(
                r"(?i)\b(strftime|datetime|julianday|unixepoch|current_timestamp|current_date|current_time)\b"
            ),
            "ipc_rpc_bridges": re.compile(r"(?i)\b(ATTACH\s+DATABASE|DETACH\s+DATABASE|PRAGMA)\b"),
        },
    },
    "html": {
        "_meta": {
            "target_version": "Modern HTML Living Standard (2025) & Web Components",
            "last_updated": "2026-02-18",
            "blueprint_version": "v5.0",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard markup, XML-based HTML, and modern JS/server-side UI component frameworks.
        "extensions": [
            ".html",
            ".htm",
            ".xhtml",
            ".cshtml",
            ".vue",
            ".svelte",
            ".astro",
            ".ejs",
            ".hbs",
            ".twig",
            ".erb",
        ],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: Standardized routing and entry points.
        "exact_matches": ["index.html", "404.html"],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions and frontend build tools to prove context.
        "discriminators": [
            ".html",
            "package.json",
            "vite.config.js",
            "webpack.config.js",
            "nuxt.config.js",
        ],
        # EXECUTION SIGNATURES: HTML is a declarative markup language; no shebangs exist.
        "shebangs": [],
        # UPGRADED: Maps to Family 8 (Singular/Unique)
        # Rationale: Uses SGML-style block delimiters () exclusively; no single-line anchor.
        "lexical_family": "line_exclusive",
        "rules": {
            # --- LEXICAL DELIMITER CONTROLS ---
            # EXPLICIT: HTML has no native single-line comment anchor.
            "_line_anchor": None,
            # EXPLICIT: HTML has no native inline comment token.
            "_inline_comment": None,
            # Block comment start: Standard SGML/XML literature delimiter.
            "_block_start": re.compile(r"<!--"),
            # Block comment end: Accept both --> and permissive HTML parser form --!>.
            "_block_end": re.compile(r"--!?>"),
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # 1. branch (Control Flow / Branching)
            # User-driven branching and declarative framework conditionals.
            "branch": re.compile(
                r'<(?:details|summary|noscript)\b|\b(?:v-if|ng-if|\*ngIf|x-if|hx-swap)="[^"]*"|\{%\s*(?:if|elif|else|endif)\s*[^%]*%\}|\{\{#if\s+[^}]+\}\}',
                re.I,
            ),
            # 2. args (Parameters / Coupling)
            # Attribute signatures defining input coupling. Bounded to prevent ReDoS on massive data attrs.
            "args": re.compile(
                r'\b(?:data-[a-zA-Z0-9_-]+|aria-[a-z]+|name|value|placeholder|for|alt|step|min|max)="[^"]*"',
                re.I,
            ),
            # 3. linear (Sequential Boundaries)
            # Structural document flow tags. Includes 1990 CERN tags (<nextid>, <address>) alongside modern semantic ones.
            "structural_boundaries": re.compile(
                r"<(?:html|head|body|main|section|article|header|footer|div|span|p|h[1-6]|ul|ol|li|dl|dt|dd|nav|aside|figure|figcaption|search|address|nextid|hp[1-2]|dir|menu)\b",
                re.I,
            ),
            # 4. func_start (Executable Logic Anchors)
            # ONLY executable behavior blocks.
            "func_start": re.compile(r"<([Ss]cript|[Ss]tyle)(?=[ \t>])"),
            # 5. class_start (Object / Entity Declarations)
            # Defines structural entities, Web Components, and template boundaries.
            "class_start": re.compile(
                r"<([Ff]orm|[Tt]able|[Ss]vg|[Cc]anvas|[Pp]icture|[Vv]ideo|[Aa]udio|[Dd]ialog|[Tt]emplate|[Ff]ieldset|[Ll]egend|[a-zA-Z0-9]+-[a-zA-Z0-9-]+)(?=[ \t>])"
            ),
            # --- PHASE 2: RISK ENGINE (Structural Integrity & Debt) ---
            # 6. safety (Defensive Programming / Validation)
            # Browser security and validation constraints.
            "safety": re.compile(
                r'\b(?:required|readonly|disabled|pattern="[^"]*"|sandbox="[^"]*"|rel="noopener(?: noreferrer)?"|integrity="[^"]*")\b|<meta\s+http-equiv="Content-Security-Policy"',
                re.I,
            ),
            # 7. safety_neg (Safety Bypasses / Unchecked Types)
            # Actively bypasses standard browser safety (e.g. target="_blank" without noopener).
            "safety_bypasses": re.compile(
                r'target="_blank"(?!\s+rel="noopener")|href="javascript:[^"]*"|on[a-z]+="[^"]*(?:eval\(|document\.write\()',
                re.I,
            ),
            # 8. danger (High-Risk Execution / System Calls)
            # HTML is declarative markup. Execution dangers (eval, setTimeout) belong in JS.
            "high_risk_execution": None,
            # 9. io (I/O & Network Boundaries)
            # Hyperlink navigation and resource fetching. (The core of the Web).
            "io": re.compile(
                r'\b(?:src|href|action|poster|data)="[^"]*"|<(?:a|form|iframe|audio|video|object|embed|source|track|img)\b',
                re.I,
            ),
            # 10. api (Public Surface Area)
            # Exposed identifiers and metadata consumption surface.
            "api": re.compile(
                r'\b(?:id|name|role|exportparts|part|itemprop|itemscope|itemtype)="[^"]*"|<slot\b|<meta\s+(?:property="og:|name="twitter:)',
                re.I,
            ),
            # 11. flux (State Mutation)
            # HTML is declarative markup. State mutation (DOM manipulation) belongs in JS.
            "state_mutation": None,
            # 12. dead_code (Commented Logic / Deprecated Trails)
            # Commented-out structural logic.
            "dead_code": re.compile(
                r"<!--[ \t]*<(?:div|script|style|form|table|a|p|section|span|img|ul|li|nav|header|footer|main)\b",
                re.I,
            ),
            # 13. doc (Structured Documentation)
            # Structured intent for crawlers and accessibility.
            "doc": re.compile(
                r'<title>[^<]*</title>|<meta\s+name="(?:description|keywords|author)"\s+content="[^"]*"|\baria-(?:description|label|labelledby|describedby|details)="[^"]*"',
                re.I,
            ),
            # 14. test (Testing & Assertions)
            "test": re.compile(r"\bdata-(?:testid|cy|test|test-id|qa)[ \t]*=", re.I),
            # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
            # 15. concurrency (Asynchronous Execution)
            # Prioritization and asynchronous fetching logic.
            "concurrency": re.compile(
                r'\b(?:async|defer|loading="lazy"|fetchpriority="(?:high|low)"|decoding="async")\b|<link\s+rel="(?:preload|prefetch|preconnect|modulepreload|prerender)"',
                re.I,
            ),
            # 16. ui_framework (UI / View Components)
            # Formatting tags and Tailwind/Bootstrap utility density.
            "ui_framework": re.compile(
                r'<(?:b|i|u|strong|em|mark|small|del|ins|sub|sup)\b|\bclass="[^"]*(?:flex|grid|absolute|relative|block|inline-block|container|row|col-[0-9]+|justify-center|items-center|w-full|h-full)[^"]*"',
                re.I,
            ),
            # 17. closures (Closures / Anonymous Functions)
            # DOM encapsulation via Shadow DOM.
            "closures": re.compile(
                r'<template\s+shadowrootmode="[^"]*">|<template\s+shadowroot="[^"]*">',
                re.I,
            ),
            # 18. globals (Global / Shared State)
            # HTML is declarative markup. Browser globals (window, document) belong in JS.
            "globals": None,
            # 19. decorators (Decorators / Annotations)
            # Directive-based logic mutation (HTMX, Vue, Alpine).
            "decorators": re.compile(
                r'\b(?:class|style|hidden|inert|tabindex|draggable|spellcheck|dir|lang|translate)[ \t]*=|hx-[a-z-]+="[^"]*"|x-[a-z-]+="[^"]*"|v-[a-z-]+="[^"]*"',
                re.I,
            ),
            # 20. generics (Generics / Type Parameters)
            "generics": re.compile(r"<slot\b[^>]*>", re.I),
            # 21. comprehensions (Iterators / Comprehensions)
            # Declarative array iteration in markup.
            "comprehensions": re.compile(
                r'\b(?:v-for|ng-repeat|\*ngFor|x-for)="[^"]*"|\{%\s*for\b[^%]*%\}|\{\{#each\b[^}]*\}\}',
                re.I,
            ),
            # 22. scientific (Numerical / Compute Libraries)
            # MathML and SVG path math.
            "scientific": re.compile(
                r'<(?:math|mfrac|mi|mo|svg|canvas|path|circle|rect|polygon|polyline)\b|\bd=["\'][MmLlHhVvCcSsQqTtAaZz0-9\s,.-]+["\']',
                re.I,
            ),
            # 23. heat_triggers (Metaprogramming & Reflection)
            # Extreme logic heat: heavy inline styles and JS pollution.
            "reflection_metaprogramming": re.compile(r'style="[^"]*;"|\bon[a-z]+="[^"]*"', re.I),
            # 24. import (Dependency Inclusions)
            "import": re.compile(
                r'<script\s+type="(?:importmap|module)"|<link\s+(?:rel="stylesheet"|rev="[^"]*")',
                re.I,
            ),
            "_dependency_capture": re.compile(r'<(?:script[^>]+src|link[^>]+href)\s*=\s*["\']([^"\']+)["\']', re.I),
            # 25. ownership (Authorship Metadata)
            "ownership": re.compile(
                r'<meta\s+name="(?:author|creator|publisher)"\s+content="([^"]+)"|<link\s+rev="made"\s+href="mailto:[^"]+"',
                re.I,
            ),
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            # 26. planned_debt (Annotated Debt / TODOs)
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            # 29. spec_exposure (Spec / Audit Traceability)
            "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit|RFC|W3C|CERN|TBL)[^\]]*\]", re.I),
            # 30. tabs_vs_spaces (Formatting Inconsistencies) 
            "tabs_vs_spaces": None,
            # 31. ssr_boundaries (Server-Side Rendering)
            # Back-end template engine hydration.
            "ssr_boundaries": re.compile(
                r'<\?php|<%|<%=|\{\{\s*[^}]+\s*\}\}|\{%\s*[^%]+\s*%\}|\b(?:data-reactroot|data-server-rendered|ng-version|nuxt-ssr)="[^"]*"',
                re.I,
            ),
            # 32. events (Event Emitters / Pub-Sub)
            # Declarative event dispatchers.
            "events": re.compile(
                r'\bhx-trigger="[^"]*"|@[a-z]+="[^"]*"|v-on:[a-z]+="[^"]*"|\([a-z]+\)="[^"]*"',
                re.I,
            ),
            # 33. dependency_injection (Dependency Injection / IoC)
            "dependency_injection": re.compile(r'<script\s+type="importmap"\b', re.I),
            # 34. macros (Preprocessor Directives / Macros)
            # Server Side Includes (SSI).
            "macros": re.compile(r"<!--#\s*(?:include|exec|echo|config|if|else|endif)\b", re.I),
            # 35. pointers (Pointer Arithmetic / Memory Addressing)
            # Fragment identifiers and original name pointers.
            "pointers": None,
            # 36. memory_alloc
            "memory_alloc": None,
            # 37. inline_asm
            "inline_asm": None,
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # 38. telemetry (Structured Logging / Telemetry)
            # Professional analytics trackers.
            "telemetry": re.compile(
                r'<script[^>]*src="[^"]*(?:analytics|gtag|gtm|segment|plausible|mixpanel)[^"]*"|\bdata-layer\b|\bnavigator\.sendBeacon\b',
                re.I,
            ),
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
            # Ad-hoc debug statements in scripts.
            "debug_prints": re.compile(
                r"\b(?:document\.write|alert|confirm|prompt|console\.(?:log|error|warn|dir|trace|info))\s*\(",
                re.I,
            ),
            # 40. explicit_casts (Explicit Type Casting)
            "explicit_casts": None,
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
            "panics_and_aborts": re.compile(r"\b(?:process\.exit|history\.back|window\.close)\s*\(", re.I),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
            "thread_sleeps": re.compile(r"\b(?:setTimeout|setInterval)\s*\(", re.I),
            # 43. bitwise_ops (Bitwise Operations)
            "bitwise_ops": None,
            # 44. sync_locks (Resource Management & Stability)
            "sync_locks": None,
            # 45. immutability_locks (Immutability Constraints)
            "immutability_locks": re.compile(r'\b(?:readonly|disabled|inert|aria-disabled="true")\b', re.I),
            # 46. cleanup (Resource Cleanup / Teardown)
            "cleanup": re.compile(
                r'\b(?:removeEventListener|clearInterval|clearTimeout|remove|innerHTML\s*=\s*[\'"][\'"])\s*\(',
                re.I,
            ),
            # 47. encapsulation (Access Modifiers / Encapsulation)
            # Declarative and Shadow DOM boundaries.
            "encapsulation": re.compile(r"<(?:template|shadowrootmode|slot)\b", re.I),
            # 48. listeners (Event Listeners / Observers)
            # Event sinks waiting for state broadcast.
            "listeners": re.compile(r"\bhx-trigger|v-on:|@[a-z]+=|addEventListener|on[a-z]+=", re.I),
            # 49. test_skip (Bypassed Tests / Ignored Specs)
            "test_skip": re.compile(r"\b(?:data-skip|data-ignore|mock-data|test-skip)\b", re.I),
        },
    },
    "css": {
        "_meta": {
            "target_version": "Modern CSS (2025 Baseline) / Native Nesting / Container Queries",
            "last_updated": "2026-02-18",
            "blueprint_version": "v5.0",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard stylesheets, preprocessors (Sass/Less), and PostCSS files.
        "extensions": [".css", ".scss", ".sass", ".less", ".styl", ".pcss"],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: CSS rarely uses extensionless configurations.
        "exact_matches": [],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: CSS linting, PostCSS, and utility framework configurations acting as disambiguation anchors.
        "discriminators": [
            ".css",
            "postcss.config.js",
            "tailwind.config.js",
            ".stylelintrc",
            ".stylelintignore",
        ],
        # EXECUTION SIGNATURES: CSS is a declarative stylesheet language; no shebangs exist.
        "shebangs": [],
        # UPGRADED: Maps to Family 1 (Standard C-Style)
        # Rationale: Uses '/*' and '*/' for blocks; preprocessors add '//' for lines.
        "lexical_family": "standard_block",
        "rules": {
            # --- LEXICAL DELIMITER CONTROLS ---
            # Standard C-family line comment token (Supported in SCSS/SASS/LESS).
            "_line_anchor": re.compile(r"//"),
            # Inline comments follow the same '//' delimiter.
            "_inline_comment": re.compile(r"//"),
            # Block comment start: /* (Native vanilla CSS literature delimiter).
            "_block_start": re.compile(r"/\*"),
            # Block comment end: */
            "_block_end": re.compile(r"\*/"),
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # 1. branch (Control Flow / Branching)
            # Decisions and logical gating. Includes Container/Media queries and logic-gating pseudo-selectors.
            "branch": re.compile(
                r"\b(@media|@supports|@container|@starting-style)\b|:(?:has|is|where|not)\s*\([^)]*\)",
                re.I,
            ),
            # 2. args (Parameters / Coupling)
            # Signatures defining input coupling. Bounded to prevent ReDoS on massive calculations.
            "args": re.compile(
                r"\b(?:calc|clamp|min|max|var|env|url|rgba?|hsla?|lch|oklch|color-mix|light-dark)\s*\([^)]*\)",
                re.I,
            ),
            # 3. linear (Sequential Boundaries)
            # Structural boundaries. EXCLUDES: Access modifiers (none in CSS) and !important (freeze_hits).
            "structural_boundaries": re.compile(
                r"\b(@layer|@scope|@property|@font-face|@keyframes|@page|@charset|@namespace)\b",
                re.I,
            ),
            # 4. func_start (Executable Logic Anchors)
            # ONLY executable logic blocks (Selectors). EXCLUDES classes/IDs to avoid False Positives.
            "func_start": re.compile(
                r"^[ \t]*(@(?:media|supports|container|layer|keyframes)\b)(?=[^{]*\{)",
                re.M | re.I,
            ),
            # 5. class_start (Object / Entity Declarations)
            # Defines discrete visual entities via Class and ID selectors.
            "class_start": re.compile(
                r"^[ \t]*(\.[a-zA-Z_][\w-]*|#[a-zA-Z_][\w-]*)(?=[ \t,>+~:]*[^{]*\{)",
                re.M,
            ),
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            # 6. safety (Defensive Programming / Validation)
            # Defensive fallbacks and mathematical clamps.
            "safety": re.compile(
                r"@supports\b|\bvar\([^,]+,\s*[^)]+\)|\b(?:minmax|clamp)\s*\([^)]*\)|\bcontain\s*:\s*(?:strict|content|paint|layout)\b",
                re.I,
            ),
            # 7. safety_neg (Safety Bypasses / Unchecked Types)
            # Universal selectors and high-specificity ID overrides.
            "safety_bypasses": re.compile(r"^[ \t]*\*|^[ \t]*#[\w-]+\s*(?:[:.[>+~][^{;]*)?\{", re.M | re.I),
            # 8. danger (High-Risk Execution / System Calls)
            # Extreme tech debt and legacy engine thrashing.
            "high_risk_execution": re.compile(r"\b(?:expression|behavior|-ms-filter)\b"),
            # 9. io (I/O & Network Boundaries)
            # =====================================================================
            # THE FIX: Prevent False I/O Latency Flags.
            # HISTORICAL CONTEXT FOR FUTURE LLMS: CSS is a declarative language.
            # Using `url()` or `@import` fetches a visual asset during browser paint;
            # it does NOT block a computational thread to read from a database or
            # write to a file system. If given a regex, the engine will hallucinate
            # severe I/O bottlenecks on standard stylesheets. Must remain `None`.
            # =====================================================================
            "io": None,
            # 10. api (Public Surface Area)
            # Design Tokens and global properties exposed for script/component consumption.
            "api": re.compile(r":root\b|@property\b|--[a-zA-Z0-9_-]+\s*:|::part\s*\([^)]*\)", re.I),
            # 11. flux (State Mutation)
            # =====================================================================
            # THE FIX: Prevent 'Declarative Hallucination' of State Flux.
            # HISTORICAL CONTEXT FOR FUTURE LLMS: Defining a CSS custom property
            # (`--color: red;`) is a static declaration, not a sequential state
            # mutation (like `x = x + 1` in Turing-complete languages). Treating it
            # as flux causes stylesheets to mathematically outrank complex controllers
            # in volatility. Must remain `None`.
            # =====================================================================
            "state_mutation": None,
            # 12. dead_code (Commented Logic / Deprecated Trails)
            # Commented-out structural rules.
            "dead_code": re.compile(
                r"/\*[ \t]*(?:@media|@container|@supports|@keyframes|\.[a-zA-Z]|#[a-zA-Z]|[a-zA-Z][\w-]*[ \t]*{)\b",
                re.I,
            ),
            # 13. doc (Structured Documentation)
            "doc": re.compile(
                r"/\*\*\s*|/\*\s*@(?:param|return|author|example|prop|define|theme)",
                re.I,
            ),
            # 14. test (Testing & Assertions)
            "test": re.compile(r"\[[ \t]*data-(?:testid|cy|test|test-id|qa)[ \t]*[=\]]", re.I),
            # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
            # 15. concurrency (Asynchronous Execution)
            # Logic executing concurrently on the GPU.
            "concurrency": None,
            # 16. ui_framework (UI / View Components)
            # Density of layout primitives and Tailwind utilities.
            "ui_framework": re.compile(
                r"\b(?:display:\s*flex|display:\s*grid|justify-content|align-items|gap|grid-template-columns|absolute|relative)\b|@apply\b",
                re.I,
            ),
            # 17. closures (Closures / Anonymous Functions)
            # Native CSS Nesting (&).
            "closures": re.compile(r"(?:^[ \t]*|\s+|,)&\s*(?:[:.\[>+~][^{;]*)?\{", re.M),
            # 18. globals (Global / Shared State)
            "globals": re.compile(r"^[ \t]*(?::root|html|body|\*)\s*(?:{[^}]*}|[,{])", re.M | re.I),
            # 19. decorators
            "decorators": None,
            # 20. generics
            "generics": None,
            # 21. comprehensions
            "comprehensions": None,
            # 22. scientific (Numerical / Compute Libraries)
            # Modern CSS trigonometry and rendering math.
            "scientific": re.compile(
                r"\b(?:sin|cos|tan|asin|acos|atan|atan2|hypot|abs|sign|mod|rem|round|pow|sqrt|exp|log)\s*\([^)]*\)",
                re.I,
            ),
            # 23. heat_triggers (Metaprogramming & Reflection)
            # Catastrophic specificity graphs and recursively nested logic.
            "reflection_metaprogramming": re.compile(
                r"&(?:\s*&)+|:(?:has|is|not)\s*\([^)]*:(?:has|is|not)\s*\([^)]*\)|calc\([^)]*calc\([^)]*\)",
                re.I,
            ),
            # 24. import (Dependency Inclusions)
            "import": re.compile(r"@import\b", re.I),
            "_dependency_capture": re.compile(
                r"^[ \t]*@import[ \t\n]+(?:url\(\s*['\"]?|['\"])([^'\"\)]+)",
                re.I | re.M,
            ),
            # 25. ownership (Authorship Metadata)
            "ownership": re.compile(
                r"/\*\s*(?:@author|Author:|Created by|Maintainer|Copyright):?\s+([^*]*)\*/",
                re.I | re.S,
            ),
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            # 26. planned_debt (Annotated Debt / TODOs)
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            # 29. spec_exposure (Spec / Audit Traceability)
            "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]|\bfigma\.com/file/", re.I),
            # 30. tabs_vs_spaces (Formatting Inconsistencies) 
            "tabs_vs_spaces": None,
            # 31. ssr_boundaries
            "ssr_boundaries": None,
            # 32. events (Event Emitters / Pub-Sub)
            # Modern Scroll-Driven animation timelines.
            "events": re.compile(
                r"@(?:scroll-timeline|view-timeline)|animation-timeline:\s*(?:scroll|view)\([^)]*\)",
                re.I,
            ),
            # 33. dependency_injection
            "dependency_injection": None,
            # 34. macros
            "macros": None,
            # 35. pointers
            "pointers": None,
            # 36. memory_alloc
            "memory_alloc": None,
            # 37. inline_asm
            "inline_asm": None,
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # 38. telemetry
            "telemetry": None,
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
            # =====================================================================
            # THE FIX: Prevent String Literal Hallucinations.
            # HISTORICAL CONTEXT FOR FUTURE LLMS: CSS does not possess a runtime
            # console or a `console.log` function. If a regex here triggers, it is
            # guaranteed to be a false positive hallucinating on a string literal
            # (e.g., `content: "console.log";`). Must remain `None`.
            # =====================================================================
            "debug_prints": None,
            # 40. explicit_casts (Explicit Type Casting)
            "explicit_casts": None,
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
            # Execution resets.
            "panics_and_aborts": re.compile(r"\b(unset|initial|revert|revert-layer)\b", re.I),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
            "thread_sleeps": re.compile(r"\b(?:transition-delay|animation-delay)\b", re.I),
            # 43. bitwise_ops (Bitwise Operations)
            "bitwise_ops": None,
            # 44. sync_locks (Resource Management & Stability)
            # Coordinating cascade layers and containment.
            "sync_locks": None,
            # 45. immutability_locks (Immutability Constraints)
            # Explicit locks on data mutation.
            "immutability_locks": re.compile(r"!important\b|\bconstant\b", re.I),
            # 46. cleanup (Resource Cleanup / Teardown)
            # =====================================================================
            # THE FIX: Prevent False Memory Management Flags.
            # HISTORICAL CONTEXT FOR FUTURE LLMS: In CSS, `clear: both;` is a
            # layout formatting property used to push elements below floats. It
            # does absolutely nothing to destroy variables, clear cache, or free up
            # RAM. Giving this a regex tricks the physics engine into thinking the
            # stylesheet is performing active memory management. Must remain `None`.
            # =====================================================================
            "cleanup": None,
            # 47. encapsulation (Access Modifiers / Encapsulation)
            # Scoping and part boundaries.
            "encapsulation": re.compile(r"@scope\b|::part|::slotted", re.I),
            # 48. listeners (Event Listeners / Observers)
            # Subscribing to external timelines.
            "listeners": re.compile(r"animation-timeline|@scroll-timeline", re.I),
            # 49. test_skip (Bypassed Tests / Ignored Specs)
            "test_skip": re.compile(r"\b(?:data-skip|data-ignore)\b", re.I),
        },
    },
    "fortran": {
        "_meta": {
            "target_version": "Fortran 2018 (Backwards compatible with Legacy Fortran 77)",
            "last_updated": "2026-03-01",
            "blueprint_version": "v7.0",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard fixed-format, free-format, legacy dialects, and preprocessor files.
        "extensions": [
            ".f",
            ".f90",
            ".f77",
            ".for",
            ".fpp",
            ".f95",
            ".f03",
            ".f08",
            ".f18",
            ".ftn",
            ".inc",
        ],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: Fortran rarely uses extensionless configurations.
        "exact_matches": [],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions, package manifests (fpm), and build files to resolve ambiguous files like .inc.
        "discriminators": [
            ".f90",
            ".f77",
            ".f",
            "fpm.toml",
            "CMakeLists.txt",
            "Makefile",
        ],
        # EXECUTION SIGNATURES: Interpreters found on Line 1 for modern Fortran "scripting" wrappers.
        "shebangs": ["fortran", "f90", "f77", "gfortran"],
        # UPGRADED: Maps to Family 7 (The Positional Ancients)
        # Rationale: Fixed-format requires Column 1 monitoring ('C' or '*'); Free-format uses '!'.
        "lexical_family": "positional_anchored",
        "rules": {
            # --- LEXICAL DELIMITER CONTROLS ---
            # Line Anchor Logic:
            # Matches Column 1 indicators for Legacy (C, c, *, d, D)
            # and start-of-line '!' for Modern/Free-form.
            "_line_anchor": re.compile(r"^[Cc*!dD](?!\$)"),
            # Inline Comment Logic:
            # Modern Fortran (90+) uses '!' for trailing literature/Commented / Non-Executable Text.
            "_inline_comment": re.compile(r"!(?!\$)"),
            # EXPLICIT: Fortran does not support standard multi-line block comment delimiters.
            "_block_start": None,
            "_block_end": None,
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # 1. branch (Control Flow / Branching)
            # Control flow that forces the CPU to make a decision or jump. High density creates jagged shapes.
            # Includes standard conditional blocks, legacy computed GO TO, and modern SELECT TYPE / SELECT RANK.
            "branch": re.compile(
                r"\b(IF|ELSEIF|ELSE|DO|WHILE|SELECT\s+CASE|CASE|DEFAULT|WHERE|ELSEWHERE|GO\s*TO|GOTO|SELECT\s+TYPE|SELECT\s+RANK|EXIT|CYCLE)\b|\.AND\.|\.OR\.",
                re.I,
            ),
            # 2. args (Parameters / Coupling)
            # Signatures defining input parameters. Drives the physical size/mass of the function.
            # Upgraded to capture both the declaration block and explicit INTENT binding markers
            # that act as the true coupling mass in legacy Fortran.
            "args": re.compile(
                r"\b(?:SUBROUTINE|FUNCTION|ENTRY)\s+[A-Za-z_]\w*(?:\s*\([^)]*\))?|\bINTENT\s*\(\s*(?:IN|OUT|INOUT)\s*\)",
                re.I,
            ),
            # 3. linear (Sequential Boundaries)
            # Structural boundaries defining straight-line execution and data types.
            # CRITICAL GUARDRAIL: Access modifiers (PUBLIC, PRIVATE, PROTECTED) do not belong here. Explicitly omitted to prevent the Structural Complexity Inflation Bug
            "structural_boundaries": re.compile(
                r"\b(PROGRAM|MODULE|SUBMODULE|BLOCK\s+DATA|CONTAINS|END\s+(?:PROGRAM|MODULE|SUBROUTINE|FUNCTION|BLOCK|TYPE|ASSOCIATE)|RETURN|IMPLICIT|USE|ASSOCIATE|BLOCK|INTEGER|REAL|COMPLEX|LOGICAL|CHARACTER|DOUBLE\s+PRECISION|CLASS)\b",
                re.I,
            ),
            # 4. func_start (Executable Logic Anchors)
            # =====================================================================
            # [ CONTEXT: FORTRAN FUNCTION AST EXTRACTOR & REDOS SHIELD]
            # PURPOSE: Anchors executable logic blocks (Program, Subroutine, Function, Entry)
            #   across 60+ years of Fortran dialects (F77 through F2018).
            # VULNERABILITY: Fortran allows extreme signature variability: prefix stacking
            #   (PURE RECURSIVE), legacy memory sizing (REAL*8), modern kinds (INTEGER(KIND=4)),
            #   derived types (TYPE(MyStruct)), object-oriented classes (CLASS(Obj)), and
            #   trailing attributes (RESULT, BIND(C)). Using unbounded `\s+` across these
            #   permutations causes Catastrophic Backtracking (ReDoS) on large legacy files.
            # THE "IRON WALL" FIX:
            #   1. Strict `[ \t\n]` bounds prevent horizontal/vertical bleeding.
            #   2. Negative lookahead `(?!\bEND\b)` prevents ghosting `END SUBROUTINE FOO`.
            #   3. Clamped quantifiers `{0,5}` on prefixes stop runaway recursion.
            #   4. Added `CLASS` to the base types to support modern Object-Oriented Fortran.
            #   5. Positive lookaheads on the tail `(?=...)` safely handle line continuations (`&`)
            #      and F90 comments (`!`) without consuming them into the capture group.
            # =====================================================================
            "func_start": re.compile(
                # 1. THE HORIZONTAL ANCHOR & END SHIELD
                # Stops O(N^2) vertical spirals. Explicitly blocks "END SUBROUTINE FOO" from triggering.
                r"^[ \t]*(?!\bEND\b)"
                # =====================================================================
                # [ THE VERTICAL LEGACY SHIELD ] (Hard-learned from Pathological Fuzzer):
                # Fortran allows extreme prefix stacking (e.g., `PURE RECURSIVE REAL*8`).
                # We previously restricted this to `[ \t]+` to avoid newline spirals.
                # FIX: Fortran developers frequently use line continuations (`&`) or split types.
                # We carefully upgraded `[ \t]` to `[ \t\n]` inside the rigidly bounded
                # `{0,5}` modifier limits so the engine can safely leap over vertical lines
                # without resorting to unbounded `\s+` which triggers ReDoS.
                # =====================================================================
                # 2. THE PREFIX STACK
                # F95/F2008 allows stacking prefixes. Capped at {0,5} to prevent ReDoS.
                r"(?:(?:PURE|ELEMENTAL|RECURSIVE|IMPURE|MODULE)[ \t\n]+){0,5}"
                # 3. THE RETURN TYPE
                # Optional for Subroutines/Programs, mandatory for explicit Functions.
                r"(?:"
                # 3a. Base Types (Primitives + Derived + Classes + Legacy)
                r"(?:INTEGER|REAL|COMPLEX|LOGICAL|CHARACTER|TYPE|CLASS|DOUBLE[ \t\n]+PRECISION)"
                # 3b. Legacy Sizing (*8) or Modern Kinds/Lengths ((KIND=4, LEN=*))
                r"(?:[ \t\n]*(?:\*[ \t\n]*\d+|\([^)]*\)))?"
                r"[ \t\n]+"
                r")?"
                # 4. THE EXECUTION BLOCK KEYWORD
                r"(?:FUNCTION|SUBROUTINE|PROGRAM|ENTRY)[ \t\n]+"
                # 5. THE IDENTIFIER CAPTURE (FUNCTION IDENTIFIER - GROUP 1)
                # Extracts the actual block name.
                r"([A-Za-z_]\w*)"
                # 6. THE TRAILING ANCHOR (Lookahead)
                # Confirms the boundary without consuming it. Handles opening parens `(`, comments `!`,
                # line continuations `&`, EOF `$`, or explicit F2003+ modifiers (RESULT, BIND).
                r"(?=[ \t\n]*(?:[\(!&]|$|\bRESULT\b|\bBIND\b))",
                re.I | re.M,
            ),
            # 5. class_start (Object / Entity Declarations)
            # Defines object-oriented and structural boundaries. Drives API Surface Area math.
            # Maps to Fortran MODULEs, SUBMODULEs, INTERFACEs, and structural TYPE definitions (Fortran's struct/class equivalent).
            "class_start": re.compile(
                r"^[ \t]*(?!\bEND\b)(?:MODULE|SUBMODULE|BLOCK\s+DATA|INTERFACE)\s+([A-Za-z_]\w*)|"
                r"^[ \t]*(?!\bEND\b)TYPE(?:,[^:]*::\s*|\s+)([A-Za-z_]\w*)(?=[ \t]*\n|[ \t]*$)",
                re.I | re.M,
            ),
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            # 6. safety (Defensive Programming)
            # Fortification markers establishing strict boundaries: explicit typing (`IMPLICIT NONE`),
            # explicit intent (`INTENT(IN)`), bounds safety (`ALLOCATABLE`), and fatal assertions (`ERROR STOP`).
            "safety": re.compile(
                r"\b(IMPLICIT\s+NONE|INTENT\s*\(\s*(?:IN|OUT|INOUT)\s*\)|ALLOCATABLE|SAVE|PARAMETER|VALUE|ERROR\s+STOP|ASYNCHRONOUS|ASSOCIATED|ALLOCATED|PRESENT)\b",
                re.I,
            ),
            # 7. safety_neg (Safety Bypasses)
            # Actively bypasses memory safety and compiler predictability.
            # Legacy memory sharing (`COMMON`, `EQUIVALENCE`), dangerous implicit typing rules, and unprotected legacy array `DIMENSION` bounds.
            "safety_bypasses": re.compile(
                r"\b(COMMON|EQUIVALENCE|IMPLICIT\s+(?:REAL|INTEGER|CHARACTER|COMPLEX|LOGICAL|DOUBLE))\b",
                re.I,
            ),
            # 8. danger (High-Risk Execution)
            # Extreme tech debt, unconstrained legacy jumps (`GO TO`, `ASSIGN`), and raw terminal output.
            # CRITICAL GUARDRAIL: Terminal prints (`PRINT`, `WRITE(*,...)`) strictly routed here, away from `io` and `telemetry`.
            "high_risk_execution": re.compile(r"\b(GO\s*TO|GOTO|ASSIGN|RETURN\s+\d+)\b", re.I),
            # 9. io (I/O & Network Boundaries)
            # File operations, hardware inquiries, and disk boundaries.
            # Negatively asserts `*` or `6` to ensure raw standard-out terminal prints do not trigger IO.
            "io": re.compile(
                r"\b(OPEN|CLOSE|READ|WRITE\s*\(\s*(?!\*|6\b)[^,]+,|INQUIRE|REWIND|BACKSPACE|ENDFILE|FLUSH|FORMAT)\b",
                re.I,
            ),
            # 10. api (Public Surface Area)
            # Code exposed to the outside world. Visibility exports (`PUBLIC`) and FFI bridges (`BIND(C)`).
            "api": re.compile(
                r"\b(PUBLIC|BIND\s*\(\s*C\s*\))\b|"
                r"^[ \t]*(?:(?:PURE|ELEMENTAL|RECURSIVE)[ \t]+){0,5}(?:TYPE\s*\([^)]*\)[ \t]+)?(?:SUBROUTINE|FUNCTION)\s+[A-Za-z_]\w*",
                re.M | re.I,
            ),
            # 11. flux (State Mutation)
            # Mutation of state. Variable assignments and standard memory manipulations.
            # Captures standard `=` (avoiding `==`, `<=`, etc.)
            "state_mutation": re.compile(
                r"(?!\b(?:KIND|LEN|UNIT|FMT|FILE|STATUS|ACTION)\s*=)[A-Za-z0-9_%\(\)]+[ \t]*=[^=>]",
                re.I,
            ),
            # 12. dead_code (Commented Logic / Deprecated Trails)
            # Commented-out logic, commented-out structural code. Supports both Fortran 90+ (`!`) and legacy F77 (`C`/`*` in column 1).
            "dead_code": re.compile(r"(?i)(?:!|^[cC*])[ \t]*(?:if|do|where|call|function|subroutine|allocate)\b"),
            # 13. doc (Structured Documentation)
            # Documentation meant to be parsed by generators (Doxygen style `!>`, `!<`, or `! @`).
            "doc": re.compile(
                r"^[Cc*!dD][ \t]*[@><\\]|^[ \t]*![ \t]*(?:Author|Description|Param|Return):",
                re.I | re.M,
            ),
            # 14. test (Testing & Assertions)
            # Test frameworks like pFUnit, generic assertions, and verification routines.
            "test": re.compile(
                r"\b(?:@test|@assertEqual|@assertTrue|@assertFalse|@assertException)\b|call[ \t]+assert_[a-z_]+",
                re.I,
            ),
            # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
            # 15. concurrency (Asynchronous Execution)
            # Fortran 2008/2018 Coarrays (distributed shared memory programming natively in the language) and OpenMP pragmas.
            "concurrency": re.compile(
                r"\b(COARRAY|SYNC\s+ALL|SYNC\s+IMAGES|SYNC\s+MEMORY|CRITICAL|LOCK|UNLOCK|FAIL\s+IMAGE|FORM\s+TEAM|MPI_[A-Za-z_]+)\b|!\$(?:OMP|ACC)\b",
                re.I,
            ),
            # 16. ui_framework (UI / View Components)
            # Fortran handles math and background computing. No native UI frameworks exist.
            "ui_framework": None,
            # 17. closures (Closures / Anonymous Functions)
            # Fortran does not natively support closures, lambdas, or anonymous functions.
            "closures": None,
            # 18. globals (Global / Shared State)
            # Persistent application state across scopes. F77 `COMMON` blocks, `SAVE` variables, and `EXTERNAL` procedures.
            "globals": re.compile(r"\b(COMMON|SAVE|EXTERNAL)\b", re.I),
            # 19. decorators (Decorators / Annotations)
            # Fortran does not have Python-style decorators, but compiler directives heavily modify block execution behaviors.
            "decorators": re.compile(r"^[ \t]*(?:!DIR\$|cDEC\$|!\$OMP|!\$ACC)\b", re.I | re.M),
            # 20. generics (Generics / Type Parameters)
            # Fortran Generic Interfaces overriding operators/assignments, and Parameterized Derived Types (PDTs).
            # CRITICAL GUARDRAIL: Safely bounds `<[^>]*>` and parentheses `\([^)]*\)` to avoid ReDoS.
            "generics": re.compile(
                r"\b(INTERFACE\s+ASSIGNMENT|INTERFACE\s+OPERATOR|GENERIC\s*::|TYPE\s+[A-Za-z_]\w*\s*\([^)]*\)|EXTENDS\s*\([^)]*\))\b",
                re.I,
            ),
            # 21. comprehensions (Iterators / Comprehensions)
            # Modern Fortran implicit loops, array constructors (`[...]`, `(/.../)`), and parallel execution syntax (`DO CONCURRENT`, `FORALL`).
            "comprehensions": re.compile(r"\b(?:FORALL|DO\s+CONCURRENT)\b|\[[^\]]+\]|\(\/[^/]+\/\)", re.I),
            # 22. scientific (Numerical / Compute Libraries)
            # Native Fortran superpower: Vectorized matrix operations, tensor reductions, and strict scientific primitive typing.
            "scientific": re.compile(
                r"\b(MATMUL|DOT_PRODUCT|TRANSPOSE|SUM|PRODUCT|MAXVAL|MINVAL|MAXLOC|MINLOC|RESHAPE|SQRT|EXP|LOG|LOG10|SIN|COS|TAN|ASIN|ACOS|ATAN|ATAN2|SINH|COSH|TANH|KIND=|CEILING|FLOOR|MOD|MODULO)\b",
                re.I,
            ),
            # 23. heat_triggers (Metaprogramming & Reflection)
            # High Cognitive Load: Memory aliasing (`EQUIVALENCE`), multiple entry points (`ENTRY`), Object-Oriented runtime dispatch (`CLASS DEFAULT`, `%`), and unstructured `NAMELIST` loading.
            "reflection_metaprogramming": re.compile(
                r"\b(EQUIVALENCE|ENTRY|SELECT\s+TYPE|CLASS\s+DEFAULT|NAMELIST|VOLATILE)\b",
                re.I,
            ),
            # 24. import (Dependency Inclusions)
            # Dependency linkage across Fortran modules and files.
            "import": re.compile(r"\b(USE|INCLUDE|IMPORT)\b", re.I),
            "_dependency_capture": re.compile(
                r"^[ \t]*(?:USE(?:\s*,\s*\w+\s*::)?\s+([a-zA-Z0-9_]+)|INCLUDE[ \t\n]*['\"]([^'\"]+)['\"])",
                re.I | re.M,
            ),
            # 25. ownership (Authorship Metadata)
            # Identifying the developer, maintainer, or copyright holder natively.
            "ownership": re.compile(
                r"^[cCdD*!][ \t]*(?:Author|Created by|Maintainer|Developer):\s+(.*)",
                re.I | re.M,
            ),
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            # 26. planned_debt (Annotated Debt / TODOs)
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            # 29. spec_exposure (Spec / Audit Traceability)
            # Audit tags establishing traceability of intent back to physics papers or architectural specifications.
            # CRITICAL: Removed (?i) to enforce strict uppercase [SPEC-XYZ] tags and prevent prose collisions.
            "spec_exposure": re.compile(r"\[\s*(?:SPEC\s*-\s*\d+|AUDIT-[A-Z0-9_-]+)\s*\]"),
            # 30. tabs_vs_spaces (Formatting Inconsistencies) 
            # Identifies Tab indentation. In Legacy Fortran 77, columns strictly dictate syntax (1-5 label, 6 continuation, 7+ code).
            # Using tabs violates strict standard constraints, establishing heavy tech debt/formatter civil wars.
            "tabs_vs_spaces": None,
            # 31. ssr_boundaries (Server-Side Rendering)
            # Fortran does not perform Server-Side Rendering.
            "ssr_boundaries": None,
            # 32. events (Event Emitters / Pub-Sub)
            # Fortran 2018 natively introduced Event-Driven programming primitives for Coarray synchronization.
            "events": re.compile(r"\b(EVENT\s+POST|EVENT\s+WAIT|EVENT_QUERY)\b", re.I),
            # 33. dependency_injection (Dependency Injection / IoC)
            # Fortran handles linkages procedurally or via modules. No native DI containers or decorators exist.
            "dependency_injection": None,
            # Low-level systems language concepts mapped to Fortran paradigms.
            # 34. macros (Preprocessor Directives / Macros)
            # Fortran utilizes the standard C Preprocessor (cpp) allowing for structural `#define`, `#ifdef` pathing (e.g., `#ifdef MPI`).
            "macros": re.compile(
                r"^[ \t]*#(?:define|undef|if|ifdef|ifndef|elif|else|endif|include|pragma)\b",
                re.M | re.I,
            ),
            # 35. pointers (Pointer Arithmetic / Memory Addressing)
            # Explicit memory mapping. Includes native Fortran `POINTER` logic, assignments `=>`, and C-FFI pointer bridges (`C_PTR`).
            "pointers": re.compile(r"(?i)\bpointer\b|[ \t]*=>[ \t]*"),
            # 36. memory_alloc (Manual Memory Management)
            # Dynamic memory allocation managed explicitly by the developer on the heap.
            "memory_alloc": re.compile(r"\b(ALLOCATE|DEALLOCATE|MOVE_ALLOC|MALLOC|FREE)\b", re.I),
            # 37. inline_asm (The Bare Metal)
            # Fortran delegates assembly to standard C linkage. Inline ASM is explicitly not supported natively in Fortran code.
            "inline_asm": None,
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # 38. telemetry (The Structured Observers)
            # CRITICAL GUARDRAIL: Isolates structured diagnostic output (custom Fortran loggers) away from raw terminal prints.
            "telemetry": re.compile(
                r"\b(?:call[ \t]+)?(?:log_info|log_error|log_warn|log_debug|logger%info|logger%error|logger%warn|logger%debug|flog)\b",
                re.I,
            ),
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
            # Raw terminal output natively dumping to stdout.
            "debug_prints": re.compile(r"\b(?:PRINT\b|WRITE\s*\(\s*(?:\*|6)\s*[,)])", re.I),
            # # 40. explicit_casts (Explicit Type Casting)
            # Forceful type coercion bypassing the safety engine. Strictly defining known Fortran intrinsic type conversion functions.
            "explicit_casts": re.compile(r"(?i)\b(?:int|real|cmplx|dble|achar|char|iachar|ichar)[ \t]*\([^)]*\)"),
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
            # Hard execution destruction and unrecoverable exceptions.
            "panics_and_aborts": re.compile(r"(?i)\b(?:stop|error[ \t]+stop|return)\b"),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
            # Forcing threads to sleep.
            "thread_sleeps": re.compile(r"(?i)\bcall[ \t]+(?:sleep|usleep)\b"),
            # 43. bitwise_ops (Bitwise Operations)
            # Low-level byte manipulation utilizing Fortran's explicit intrinsic bitwise functions.
            "bitwise_ops": re.compile(r"(?i)\b(?:iand|ior|ieor|not|ishft|ishftc|btest|ibset|ibclr|ibits)\b"),
            # 44. sync_locks (Resource Management & Stability)
            # Explicit coordination to prevent race conditions .
            "sync_locks": re.compile(
                r"(?i)\b(?:lock|unlock|critical|sync[ \t]+all|sync[ \t]+images|sync[ \t]+memory)\b"
            ),
            # 45. immutability_locks (Immutability Constraints)
            # Explicit locking of data to prevent mutation .
            "immutability_locks": re.compile(r"(?i)\b(?:parameter|intent[ \t]*\([ \t]*in[ \t]*\))\b"),
            # 46. cleanup (Resource Cleanup / Teardown)
            # Explicit destruction of state or closing of streams .
            "cleanup": re.compile(r"(?i)\b(?:close|deallocate|nullify)\b"),
            # 47. encapsulation (Access Modifiers / Encapsulation)
            # Logic hidden from view via visibility modifiers .
            "encapsulation": re.compile(r"(?i)\bprivate\b"),
            # 48. listeners (Event Listeners / Observers)
            # Waiting to receive state from an external broadcast .
            "listeners": None,
            # 49. test_skip (Bypassed Tests / Ignored Specs)
            # Framework code that explicitly bypasses verification.
            "test_skip": None,
            # --- PHASE 3: HYBRID DOMAIN SENSORS (Fortran Specifics) ---
            "serialization_parsing": re.compile(r"(?i)\b(NAMELIST|READ\s*\(|WRITE\s*\(|FORMAT|OPEN\s*\()\b"),
            "regex_execution": re.compile(
                r"(?i)\b(SCAN|INDEX|VERIFY|ADJUSTL|ADJUSTR)\b"
            ),  # Relies on intrinsic string processing
            "time_date_logic": re.compile(r"(?i)\b(DATE_AND_TIME|SYSTEM_CLOCK|CPU_TIME)\b"),
            "ipc_rpc_bridges": re.compile(r"(?i)\b(MPI_Init|MPI_Send|MPI_Recv|MPI_Bcast|EXECUTE_COMMAND_LINE|OMP_)\b"),
        },
    },
    "assembly": {
        "_meta": {
            "target_version": "x86-64 (NASM/GAS) & ARMv8 (AArch64) - Backwards Compatible",
            "last_updated": "2026-02-18",
            "blueprint_version": "v5.0",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard assembly, GNU Assembler, NASM, MASM, and architecture-specific extensions.
        "extensions": [
            ".asm",
            ".s",
            ".S",
            ".inc",
            ".nasm",
            ".s64",
            ".masm",
            ".arm",
            ".a51",
        ],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: Assembly is assembled directly to machine code; no extensionless exact configurations exist.
        "exact_matches": [],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions, linker scripts (.ld), and build systems acting as disambiguation anchors to resolve .inc or .s files.
        "discriminators": [
            ".asm",
            ".s",
            ".S",
            ".c",
            ".cpp",
            ".ld",
            "Makefile",
            "CMakeLists.txt",
        ],
        # EXECUTION SIGNATURES: Assembly is compiled/assembled to binary; no shebangs exist.
        "shebangs": [],
        # UPGRADED: Maps to Family 8 (Singular/Unique)
        # Rationale: Uses unique line delimiters ';' (NASM/Intel) and '#' (GAS/ARM).
        "lexical_family": "line_exclusive",
        "rules": {
            # --- LEXICAL DELIMITER CONTROLS ---
            # Assembly uses ';' or '#' for standard line-level literature.
            # (Note: '//' is occasionally used in modern GAS but ';' remains the anchor).
            "_line_anchor": re.compile(r"[;#]"),
            # Inline comments are triggered by the same ';' or '#' tokens.
            "_inline_comment": re.compile(r"[;#]"),
            # EXPLICIT: Standard Assembly does not support multi-line block comment delimiters.
            "_block_start": None,
            "_block_end": None,
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # 1. branch (Control Flow / Branching)
            # Decisions and logical jumps. EXCLUDES system exits/halts (bailout_hits).
            "branch": re.compile(
                r"\b(jmp|je|jne|jz|jnz|ja|jb|jl|jg|jge|jle|jae|jbe|call|ret|b|bl|bx|blr|cbz|cbnz|tbz|tbnz|beq|bne|loop)\b",
                re.I,
            ),
            # 2. args (Parameters / Coupling)
            # Assembly uses ABI registers for parameter coupling.
            "args": re.compile(
                r"\b([er]di|[er]si|[er]dx|[er]cx|[er][89]|x[0-7]|w[0-7]|v[0-7]|xmm[0-7])\b",
                re.I,
            ),
            # 3. linear (Sequential Boundaries)
            # Data movement and arithmetic primitives. EXCLUDES: Linker visibility (api) and sections (globals).
            "structural_boundaries": re.compile(
                r"\b(mov|mov[bwlq]|lea|ldr|str|push|pop|add|sub|inc|dec|mul|imul|div|idiv|nop|ldp|stp)\b",
                re.I,
            ),
            # 4. func_start (Executable Logic Anchors)
            # Subroutine entry points. EXCLUDES data labels or local loop markers.
            "func_start": re.compile(
                r"^[ \t]*(?!\.L|\.LC|\d|\.text|\.data|\.bss)([a-zA-Z_][a-zA-Z0-9_.$]*)(?=\s*:)",
                re.M,
            ),
            # 5. class_start (Object / Entity Declarations)
            # Maps to assembler structure definition macros.
            "class_start": re.compile(r"^[ \t]*(?:struc|STRUCT|\.struct)\s+[a-zA-Z_]\w*", re.M | re.I),
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            # 6. safety (Defensive Programming / Validation)
            # Stack preservation and defensive frame setups.
            "safety": re.compile(
                r"\b(enter|leave|endbr64|paciasp|autiasp|bti|retab|\.align|\.p2align)\b|\b(?:stp|ldp)\s+x29,\s*x30",
                re.I,
            ),
            # 7. safety_neg (Safety Bypasses / Unchecked Types)
            # Indirect jumps and hardware interrupt disabling.
            "safety_bypasses": re.compile(
                r"\b(?:jmp|call)\s+(?:\*|\[|[er]?[abcd]x|r\d+)\b|\bbr\s+[xw]\d+\b|\b(cli|msr\s+daifclr)\b",
                re.I,
            ),
            # 8. danger (High-Risk Execution / System Calls)
            # CPU halts and debug traps. EXCLUDES prints (Phase 5).
            "high_risk_execution": re.compile(r"\b(hlt|int\s+3|brk|ud2|sys_exit|sys_kill)\b", re.I),
            # 9. io (I/O & Network Boundaries)
            # System calls and hardware I/O ports.
            "io": re.compile(
                r"\b(in|out|ins[bdw]|outs[bdw]|syscall|svc\b|int\s+0x80|sys_read|sys_open)\b",
                re.I,
            ),
            # 10. api (Public Surface Area)
            # Linker-visible global exports.
            "api": re.compile(
                r"^[ \t]*(?:\.global|\.globl|global|EXPORT|PUBLIC|EXTERN|IMPORT)\b",
                re.M | re.I,
            ),
            # 11. flux (State Mutation)
            # Explicit memory/register swaps and atomic increments.
            "state_mutation": re.compile(r"\b(xchg|cmpxchg|inc|dec)\b", re.I),
            # 12. dead_code (Commented Logic / Deprecated Trails)
            "dead_code": re.compile(r"(?i)(?:;|#|//)[ \t]*(?:jmp|call|mov|push|pop|cmp|add|sub)\b"),
            # 13. doc (Structured Documentation)
            "doc": re.compile(r"^[;#@/|]+\s*@(?:param|return|brief|author|note)", re.M | re.I),
            # 14. test (Testing & Assertions)
            "test": re.compile(r"(?i)\b(?:describe|expect|assert|TestCase)\b|\bit[ \t]*\("),
            # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
            # 15. concurrency (Asynchronous Execution)
            "concurrency": re.compile(
                r"\b(lock|xadd|mfence|lfence|sfence|dmb|dsb|isb|ldxr|stxr|ldaxr|stlxr)\b",
                re.I,
            ),
            # 16. ui_framework
            "ui_framework": None,
            # 17. closures
            "closures": None,
            # 18. globals (Global / Shared State)
            "globals": re.compile(
                r"^[ \t]*(?:\.data|\.bss|\.rodata|\.comm|section\s+\.data|section\s+\.bss)\b",
                re.M | re.I,
            ),
            # 19. decorators
            "decorators": None,
            # 20. generics
            "generics": None,
            # 21. comprehensions (Iterators / Comprehensions)
            # Instruction repetition prefixes.
            "comprehensions": re.compile(
                r"^[ \t]*(?:%rep|\.rept|\.irp)\b|\b(?:rep|repe|repne|repz|repnz)\b",
                re.M | re.I,
            ),
            # 22. scientific (Numerical / Compute Libraries)
            # FPU, SSE, AVX, and NEON instructions.
            "scientific": re.compile(
                r"\b(fadd|fsub|fmul|fdiv|fsqrt|vadd[ps][sd]|vsub[ps][sd]|vmul[ps][sd]|fmla|fmov)\b",
                re.I,
            ),
            # 23. heat_triggers (Metaprogramming & Reflection)
            # Complex SIB addressing and block replication.
            "reflection_metaprogramming": re.compile(r"\[\s*[a-zA-Z0-9_]+\s*\+\s*[a-zA-Z0-9_]+\s*\*\s*\d+", re.I),
            # 24. import (Dependency Inclusions)
            "import": re.compile(r"^[ \t]*(?:%include|\.include|\.incbin)\b", re.M | re.I),
            "_dependency_capture": re.compile(
                r"^[ \t]*(?:%include|\.include|\.incbin)\s+(?:['\"]([^'\"]+)['\"]|([^'\"\s]+))",
                re.M | re.I,
            ),
            # 25. ownership (Authorship Metadata)
            "ownership": re.compile(
                r"^[;#@/|]+\s*(?:Author|Created by|Maintainer|Copyright):\s+(.*)",
                re.M | re.I,
            ),
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            # 26. planned_debt (Annotated Debt / TODOs)
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            # 29. spec_exposure (Spec / Audit Traceability)
            "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit|rfc)[^\]]*\]", re.I),
            # 30. tabs_vs_spaces (Formatting Inconsistencies) 
            "tabs_vs_spaces": None,
            # 31. ssr_boundaries
            "ssr_boundaries": None,
            # 32. events (Event Emitters / Pub-Sub)
            # Interrupt vectors and exception handlers.
            "events": re.compile(
                r"\b(int\s+(?:0x)?[0-9a-fA-F]+|iret[qd]?|reti|svc|hvc|smc)\b|^[ \t]*(?:vector|handler|isr)_[a-zA-Z0-9_]+:",
                re.M | re.I,
            ),
            # 33. dependency_injection
            "dependency_injection": None,
            # 34. macros (Preprocessor Directives / Macros)
            "macros": re.compile(
                r"^[ \t]*(?:%macro|\.macro|%endmacro|\.endm|%define|\.equ|\.set|#define)\b",
                re.M | re.I,
            ),
            # 35. pointers (Pointer Arithmetic / Memory Addressing)
            # Raw memory addressing and dereferencing.
            "pointers": re.compile(r"(?i)(?:byte|word|dword|qword)[ \t]+ptr[ \t]*\[[^\]]*\]|\[[^\]]+\]"),
            # 36. memory_alloc (Manual Memory Management)
            "memory_alloc": re.compile(
                r"\b(?:call|bl)\s+(?:_?malloc|_?calloc)\b|\b(?:sys_mmap|sys_brk)\b",
                re.I,
            ),
            # 37. inline_asm
            "inline_asm": None,  # This is base assembly.
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # 38. telemetry (Structured Logging / Telemetry)
            "telemetry": re.compile(
                r"\b(?:call|bl)\s+(?:log_info|log_error|log_warn|log_debug|syslog)\b",
                re.I,
            ),
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
            "debug_prints": re.compile(r"\b(?:call|bl)\s+(?:printf|puts|sys_write)\b", re.I),
            # # 40. explicit_casts (Explicit Type Casting)
            "explicit_casts": re.compile(r"(?i)\b(?:byte|word|dword|qword)[ \t]+ptr\b"),
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
            # Hard execution destruction and unrecoverable hardware exceptions. [cite: 780]
            "panics_and_aborts": re.compile(r"(?i)\b(?:hlt|ud2|brk|svc|int[ \t]+3)\b"),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
            # Forcing hardware threads to sleep or pause execution. [cite: 781]
            "thread_sleeps": re.compile(r"(?i)\b(?:pause|hlt|wfi|wfe)\b"),
            # 43. bitwise_ops (Bitwise Operations)
            # Low-level byte manipulation natively supported by the instruction set. [cite: 782]
            "bitwise_ops": re.compile(r"(?i)\b(?:and|or|xor|not|shl|shr|sal|sar|rol|ror|lsl|lsr|asr)\b"),
            # 44. sync_locks (Resource Management & Stability)
            # Explicit hardware coordination to prevent race conditions (e.g., atomic instructions, memory barriers). [cite: 783]
            "sync_locks": re.compile(r"(?i)\b(?:lock|xchg|cmpxchg|stxr|ldxr|dmb|dsb|isb)\b"),
            # 45. immutability_locks (Immutability Constraints)
            # Explicit locking of data to prevent mutation (e.g., read-only data sections or constants). [cite: 784]
            "immutability_locks": re.compile(r"(?i)\b(?:equ|\.rodata|\.rdata)\b"),
            # 46. cleanup (Resource Cleanup / Teardown)
            # Assembly relies on manual memory management via standard instructions, lacking dedicated cleanup APIs. [cite: 785]
            "cleanup": re.compile(r"\b(?:call|bl)\s+_?free\b", re.I),
            # 47. encapsulation (Access Modifiers / Encapsulation)
            # Logic hidden from view via visibility directives. [cite: 786]
            "encapsulation": re.compile(r"(?i)\b(?:\.local|\.private)\b"),
            # 48. listeners (Event Listeners / Observers)
            # Assembly relies on hardware interrupts rather than high-level listener subscriptions. [cite: 787]
            "listeners": None,
            # 49. test_skip (Bypassed Tests / Ignored Specs)
            # Framework code that explicitly bypasses verification. [cite: 788]
            "test_skip": None,
            # --- PHASE 3: HYBRID DOMAIN SENSORS (Lua Specifics) ---
            "serialization_parsing": re.compile(r"\b(string\.dump|loadstring|load|cjson\.decode|cjson\.encode)\b"),
            "regex_execution": re.compile(r"\b(string\.match|string\.gmatch|string\.find|string\.gsub)\b"),
            "time_date_logic": re.compile(r"\b(os\.time|os\.clock|os\.date|os\.difftime)\b"),
            "ipc_rpc_bridges": re.compile(
                r"\b(os\.execute|io\.popen|coroutine\.create|coroutine\.resume|coroutine\.yield)\b"
            ),
        },
    },
    "agc_assembly": {
        "_meta": {
            "target_version": "Apollo Guidance Computer (Luminary 099 / Comanche 055 - Apollo 11)",
            "last_updated": "2026-02-18",
            "blueprint_version": "v5.0",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard Apollo Guidance Computer digitized source files.
        "extensions": [".agc"],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: AGC code is hardware-level; no extensionless exact configurations exist.
        "exact_matches": [],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions and emulator/assembler tools to lock in the historical context.
        "discriminators": [".agc", "yaYUL"],
        # EXECUTION SIGNATURES: AGC code is hardware-level or emulator-resident; no shebangs exist.
        "shebangs": [],
        # UPGRADED: Maps to Family 3 (Pure Hash)
        # UPGRADED: Maps to Family 3 (Pure Hash)
        # Rationale: Digitized source uses '#' for line-level Commented / Non-Executable Text.
        "lexical_family": "line_exclusive",
        "rules": {
            # --- LEXICAL DELIMITER CONTROLS ---
            # AGC digitized source uses '#' for standard line-level literature.
            "_line_anchor": re.compile(r"#"),
            # Inline comments are also triggered by the '#' token.
            "_inline_comment": re.compile(r"#"),
            # EXPLICIT: AGC Assembly does not support multi-line block comment delimiters.
            "_block_start": None,
            "_block_end": None,
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # 1. branch (Control Flow / Branching)
            # Decisions and logical jumps. EXCLUDES fatal alarms (bailout_hits).
            "branch": re.compile(
                r"\b(TC|TCF|BZF|BZE|BMN|BPL|CCS|RESUME|RETURN|TCR|OVSK|BVBZ|CALL|GOTO)\b",
                re.I,
            ),
            # 2. args (Parameters / Coupling)
            # Safely captures hardware registers (A, Q, L, Z) ONLY when they are
            # explicitly coupled to an AGC mathematical/memory opcode.
            # Also captures the Bank assignment declarations.
            "args": re.compile(
                r"\b(?:[EFB]BANK)="
                r"|"
                r"\b(?:CA|CS|TS|AD|SU|MULT|DV|MASK|DXCH|LXCH|QXCH|XCH|INDEX)[ \t]+(?:A|Q|L|Z)\b",
                re.I,
            ),
            # 3. linear (Sequential Boundaries)
            # Standard instruction flow and data markers.
            "structural_boundaries": re.compile(
                r"\b(CA|CS|TS|DXCH|LXCH|QXCH|XCH|AD|SU|MULT|DV|MASK|SETLOC|BANK|COUNT|ADRES|OCTAL|2OCT|DEC|2DEC|BLOCK|ERASE)\b",
                re.I,
            ),
            # 4. func_start (Executable Logic Anchors)
            # Subroutine entry points anchoring logic blocks.
            "func_start": re.compile(
                r"^([A-Z0-9_-]+)(?=\s+(?:TC|CA|CS|TS|DXCH|CCS|DLOAD|STORE|CALL|INDEX|EXTEND|INHINT|BZF|BZMF|BPL|BMI)\b)",
                re.M | re.I,
            ),
            # 5. class_start
            # AGC lacks native objects.
            "class_start": None,
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            # 6. safety (Defensive Programming / Validation)
            # Real-time safety guards and interrupt control.
            "safety": re.compile(
                r"\b(INHINT|RELINT|TC\s+DOWNRUPT|CS\s+ERESTORE|MUST\s+RESTORE|EDRUPT)\b",
                re.I,
            ),
            # 7. safety_neg (Safety Bypasses / Unchecked Types)
            # Bypassing predictable flow or task management risks.
            "safety_bypasses": re.compile(r"\b(TC\s+JOBSLEEP|TC\s+JOBWAKE|TCF\s+2|TASKOVER|TCF\s+ADRERR)\b", re.I),
            # 8. danger (High-Risk Execution / System Calls)
            # High-risk failure states and alarms. EXCLUDES MOD history (Phase 2 debt).
            "high_risk_execution": re.compile(r"\b(CURTAINS|SOFTWARE\s+RESTART|SYSTEM_FAILURE|WHIMPER|HALT)\b", re.I),
            # 9. io (I/O & Network Boundaries)
            # Hardware I/O bridging to the Command/Lunar Module.
            "io": re.compile(r"\b(DSKY|CHANNEL|READ|WRITE|V\d+N\d+|OUT\d+|IN\d+)\b", re.I),
            # 10. api (Public Surface Area)
            # Global labels and externally visible entry points.
            "api": re.compile(
                r"^[A-Z0-9_-]+\s+EQUALS|^[ \t]*(?:SUBROUTINE|BEXT|EXTEND)\b",
                re.M | re.I,
            ),
            # 11. flux (State Mutation)
            # Direct state mutation and register storage.
            "state_mutation": re.compile(
                r"\b(TS|DXCH|LXCH|QXCH|XCH|INCR|AUG|DIM|WRSUB|AUGMENT|DIMINISH|STORE|STQ|STCALL|DAS)\b",
                re.I,
            ),
            # 12. dead_code (Commented Logic / Deprecated Trails)
            "dead_code": re.compile(r"(?i)#[ \t]*(?:TCF|CCS|INDEX|BZF|BZN|CA|CS)\b"),
            # 13. doc (Structured Documentation)
            "doc": re.compile(
                r"^#\s*(?:Page|MOD\s+(?:BY|NO)|FUNCTIONAL\s+DESCRIPTION|SUBROUTINE|PURPOSE|CALLING\s+SEQUENCE|AUTHOR|PROGRAM|REVISION)",
                re.M | re.I,
            ),
            # 14. test (Testing & Assertions)
            # System integrity verifications and self-checks.
            "test": re.compile(
                r"\b(TC\s+ALARM2|SELFCHECK|ROPECHK|ERASCHK|CNTRCHK|CHECK|TC\s+BANKJUMP)\b",
                re.I,
            ),
            # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
            # 15. concurrency (Asynchronous Execution)
            # Priority multitasking scheduler and task management.
            "concurrency": re.compile(
                r"\b(PRIO[1-9]|EXEC|TC\s+NOVAC|TC\s+WAITLIST|TC\s+FINDVAC|ENDOFJOB|PHASCHNG|AWAKE|SLEEP|VARDELAY)\b",
                re.I,
            ),
            # 16. ui_framework (UI / View Components)
            # DSKY (Display/Keyboard) UI verbs and nouns.
            "ui_framework": re.compile(r"\b(V\s+\d+|N\s+\d+|NOUN|VERB|ENTER|PROCEED)\b", re.I),
            # 17. closures
            "closures": None,
            # 18. globals (Global / Shared State)
            # Memory division markers.
            "globals": re.compile(
                r"\b(ERASABLE\s+MEMORY|FIXED\s+MEMORY|WORKING-STORAGE|COMMON|FLAGWRD\d+|BIT\d+)\b",
                re.I,
            ),
            # 19. decorators
            "decorators": None,
            # 20. generics
            "generics": None,
            # 21. comprehensions
            "comprehensions": None,
            # 22. scientific (Numerical / Compute Libraries)
            # Vector math and orbital navigation interpreter routines.
            "scientific": re.compile(
                r"\b(VAD|VSUB|BDSU|DDV|DMP|DSU|SQRT|NORM|SIGN|ABS|SIN|COS|ASIN|ACOS|SPCOS|SPSIN|DOT|CROSS|UNIT|ABVAL|VXV|VXM|MXV)\b",
                re.I,
            ),
            # 23. heat_triggers (Metaprogramming & Reflection)
            # Self-modifying logic and VM entry.
            "reflection_metaprogramming": re.compile(r"\b(INDEX|TC\s+INTPRET|DXCH\s+0000|RVQ)\b", re.I),
            # 24. import (Dependency Inclusions)
            "import": re.compile(r"\b(BANK|SETLOC|EBANK=)\b", re.I),
            "_dependency_capture": re.compile(
                r"^[ \t]*(?:BANK[ \t\n]+|SETLOC[ \t\n]+|EBANK=[ \t\n]*)([A-Za-z0-9_]+)",
                re.I | re.M,
            ),
            # 25. ownership (Authorship Metadata)
            "ownership": re.compile(
                r"^#\s*(?:MOD\s+BY|AUTHOR|CREATED\s+BY|MAINTAINER|Contact)\s*[:\-]\s*(.*)",
                re.M | re.I,
            ),
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            # 26. planned_debt (Annotated Debt / TODOs)
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            # 29. spec_exposure (Spec / Audit Traceability)
            # Linkage to MIT GSOP or mission versions.
            "spec_exposure": re.compile(
                r"\b(GSOP|LUMINARY|COMANCHE|COLOSSUS|SUNDISK|SUNBURST|PCR\s*\d+|PCN\s*\d+|SPEC\s*-\s*\d+|#\s*REF:)\b",
                re.I,
            ),
            # 30. tabs_vs_spaces (Formatting Inconsistencies) 
            "tabs_vs_spaces": None,
            # 31. ssr_boundaries
            "ssr_boundaries": None,
            # 32. events (Event Emitters / Pub-Sub)
            # Hardware interrupt vectors (Rupts).
            "events": re.compile(
                r"\b(RUPT|TIME1|TIME2|KEYRUPT|UPRUPT|DOWNRUPT|RADAR|OPTIC|HANDRUPT|ERRUPT)\b",
                re.I,
            ),
            # 33. dependency_injection
            "dependency_injection": None,
            # 34. macros (Preprocessor Directives / Macros)
            "macros": re.compile(r"^[ \t]*(?:MACRO|ENDMAC|DEFINE)\b", re.M | re.I),
            # 35. pointers (Pointer Arithmetic / Memory Addressing)
            "pointers": re.compile(r"\b(?:INDEX|INDIRECT|POINTER|CADR|FCADR|ECADR)\b|\*[A-Z0-9_-]+", re.I),
            # 36. memory_alloc (Manual Memory Management)
            "memory_alloc": re.compile(r"\b(?:ERASABLE|FIXED|EQUALS|SHARE)\b", re.I),
            # 37. inline_asm
            "inline_asm": None,
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # 38. telemetry (Structured Logging / Telemetry)
            # Spacecraft downlink routines.
            "telemetry": re.compile(r"\b(DNTM|DOWNLINK|TELEM|TM|DUMPTEL|TM\s+WORD)\b", re.I),
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs)
            "debug_prints": re.compile(r"\b(?:FLASH|PINBALL|OUT\d+)\b", re.I),
            # 40. explicit_casts (Explicit Type Casting)
            "explicit_casts": re.compile(r"\bEXTEND\b", re.I),
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
            "panics_and_aborts": re.compile(r"\b(POODOO|BAILOUT|TC\s+ALARM|ABORT)\b", re.I),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
            "thread_sleeps": re.compile(r"\b(TC\s+JOBSLEEP|VARDELAY)\b", re.I),
            # 43. bitwise_ops (Bitwise Operations)
            "bitwise_ops": re.compile(r"\b(MASK|AD|SU|MULT|DV)\b", re.I),
            # 44. sync_locks (Resource Management & Stability)
            "sync_locks": re.compile(r"\b(INHINT|RELINT|LOCK|UNLOCK)\b", re.I),
            # 45. immutability_locks (Immutability Constraints)
            "immutability_locks": re.compile(r"\bFIXED\s+MEMORY\b", re.I),
            # 46. cleanup (Resource Cleanup / Teardown)
            "cleanup": re.compile(r"\b(ENDOFJOB|RESUME|EXIT)\b", re.I),
            # 47. encapsulation (Access Modifiers / Encapsulation)
            # Internal task-local labels or non-global tags.
            "encapsulation": re.compile(r"^[ \t]*[a-z0-9_][a-zA-Z0-9_.]*", re.M),
            # 48. listeners (Event Listeners / Observers)
            "listeners": re.compile(r"\b(EVENT\s+WAIT|TC\s+WAITLIST)\b", re.I),
            # 49. test_skip (Bypassed Tests / Ignored Specs)
            "test_skip": None,
        },
    },
    "lua": {
        "_meta": {
            "target_version": "Lua 5.5 / Luau / LuaLS Annotations / LuaJIT",
            "last_updated": "2026-02-18",
            "blueprint_version": "v5.0",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard scripts, Luau (Roblox), Nmap Scripting Engine (.nse), and LuaRocks package specs (.rockspec).
        "extensions": [".lua", ".luau", ".nse", ".pd_lua", ".wlua", ".rockspec"],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: Tooling and documentation configurations that are secretly pure Lua code.
        "exact_matches": ["config.ld"],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions, package manifests, and linting configs to resolve ambiguous files.
        "discriminators": [".lua", ".luacheckrc", "stylua.toml", ".rockspec"],
        # EXECUTION SIGNATURES: Interpreters found on Line 1 for CLI, Game-Engine, and embedded scripts.
        "shebangs": ["lua", "luajit", "luau", "texlua"],
        # UPGRADED: Maps to Family 5 (Hybrid Dash)
        # Rationale: Uses '--' for lines and '--[[ ... ]]' for blocks.
        "lexical_family": "standard_block",
        "rules": {
            # --- LEXICAL DELIMITER CONTROLS ---
            # Lua uses '--' for standard line-level literature.
            "_line_anchor": re.compile(r"--"),
            # Inline comments are also triggered by the '--' token.
            "_inline_comment": re.compile(r"--"),
            # Block comment start: --[[
            # (Note: Lua supports long-brackets, but --[[ is the standard signature)
            "_block_start": re.compile(r"--\[=*\["),
            # Block comment end: Catches standard ]] and long-bracket ]=] styles
            "_block_end": re.compile(r"\]=*\]"),
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # 1. branch: decisions that split flow. Includes standard loops and Lua 5.2+ goto.
            "branch": re.compile(r"\b(if|then|elseif|else|for|in|while|do|repeat|until|break|goto|and|or|not)\b"),
            # 2. args: Parameters / Coupling. Captures parameters in named and anonymous function signatures.
            "args": re.compile(r"\bfunction\s*(?:[a-zA-Z_][\w.:]*\s*)?\([^)]*\)"),
            # 3. linear: Sequential I/O & Network Boundaries. Structural boundaries defining scope and data definitions.
            "structural_boundaries": re.compile(r"\b(local|end|require|module|return)\b|<\s*(?:const|close|toclose)\s*>"),
            # 4. func_start: Executable Logic Anchors. Anchors executable logic blocks (named functions).
            "func_start": re.compile(
                # =====================================================================
                # [ THE VERTICAL FUNCTION SHIELD (LUA) ]
                # Lua developers frequently split the `local`, `function`, and identifier
                # across newlines.
                # FIX: Upgraded horizontal `[ \t]+` bounds to `[ \t\n]+` across the
                # modifier stack, and securely allowed `[ \t\n]*` in the positive
                # lookahead for the parenthesis.
                # =====================================================================
                r"^[ \t]*(?:local[ \t\n]+)?(?:export[ \t\n]+)?function[ \t\n]+([a-zA-Z_][\w.:]*)(?=[ \t\n]*\()",
                re.M,
            ),
            # 5. class_start: Object / Entity Declarations. Captures proto-tables or EmmyLua class definitions.
            "class_start": re.compile(
                r"^[ \t]*---@class\s+([a-zA-Z_]\w*)|^[ \t]*(?:local[ \t]+)?(?:export[ \t]+)?([A-Z][a-zA-Z0-9_]*)(?=[ \t]*=[ \t]*\{)",
                re.M,
            ),
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            # 6. safety: Defensive Programming. Protected calls, assertions, and type checks.
            "safety": re.compile(
                r"\b(pcall|xpcall|assert|error|type|getmetatable|rawequal|ipairs|pairs|next)\b|<\s*(?:const|close|toclose)\s*>"
            ),
            # 7. safety_neg: Safety Bypasses. Actively bypassing safety (environment manipulation/raw access).
            "safety_bypasses": re.compile(
                r"\b(rawget|rawset|rawlen|debug\.[a-zA-Z0-9_]+|collectgarbage|_G|_ENV|getfenv|setfenv)\b"
            ),
            # 8. danger: High-Risk Execution. Dynamic evaluation and OS-level execution hooks.
            "high_risk_execution": re.compile(r"\b(os\.execute|os\.exit|os\.remove|os\.rename|load|loadstring|loadfile)\b"),
            # 9. io: I/O & Network Boundaries. Standard IO library and environment inquiries.
            "io": re.compile(r"\b(io\.open|io\.read|io\.lines|io\.close|io\.input|io\.output|io\.popen|os\.getenv)\b"),
            # 10. api: Public Surface Area. Functions NOT marked local or explicit module returns.
            "api": re.compile(
                r"^[ \t]*function\s+[^_][\w.:]*|^[ \t]*return\s+[a-zA-Z_]\w*[ \t]*$|---@public|\bexport\b",
                re.M,
            ),
            # 11. flux: State Mutation. State mutation (assignments and table mutators).
            "state_mutation": re.compile(
                r"\b[a-zA-Z_]\w*(?:\[[^\]]+\]|\.[a-zA-Z_]\w*)?\s*(?<![=<>~])=(?![=])|\btable\.(?:insert|remove|move|sort|concat)\b"
            ),
            # 12. dead_code (Commented Logic / Deprecated Trails) Commented out structural code trails.
            "dead_code": re.compile(
                r"(?:--|--\[=*\[)[ \t]*(?:if|local|function|for|while|print|return)\b",
                re.M,
            ),
            # 13. doc: Structured Documentation. LDoc/EmmyLua style documentation.
            "doc": re.compile(
                r"---@(?:param|return|field|see|alias|private|protected|diagnostic)|---\s*[A-Z]",
                re.M,
            ),
            # 14. test: Testing & Assertions. Busted, LuaUnit, and custom verification markers.
            "test": re.compile(
                r'\b(?:setup|teardown|busted|luassert|assert|mock|stub|spy|luaunit|Test[A-Z]\w*)\b|\b(?:describe|it)\s*[\'"(]'
            ),
            # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
            # 15. concurrency: Temporal Static. Lua coroutines and task schedulers.
            "concurrency": re.compile(
                r"\b(coroutine\.(?:create|resume|yield|wrap|status|isyieldable|close)|task\.(?:spawn|wait|defer|delay)|uv\.[a-zA-Z0-9_]+)\b"
            ),
            # 16. ui_framework: UI / View Components. Game engine hooks (LÖVE, Solar2D, Defold, Roblox).
            "ui_framework": re.compile(
                r"\b(love\.[a-zA-Z0-9_]+|display\.new[a-zA-Z0-9_]+|gui\.[a-zA-Z0-9_]+|Roact\.[a-zA-Z0-9_]+|Instance\.new)\b"
            ),
            # 17. closures: Closures / Anonymous Functions. Anonymous function depth.
            "closures": re.compile(r"(?:^|[(=,\s])function\s*\([^)]*\)", re.M),
            # 18. globals: Global / Shared State. Access to global registries.
            "globals": re.compile(r"\b(_G|_ENV|_VERSION|arg)\b|^[ \t]*[A-Z][A-Z0-9_]*[ \t]*=(?![=])", re.M),
            # 19. decorators: Decorators / Annotations. EmmyLua annotations.
            "decorators": re.compile(r"^[ \t]*---@[a-zA-Z_]\w*", re.M),
            # 20. generics: Generics / Type Parameters. EmmyLua generic type annotations.
            "generics": re.compile(r"---@(?:generic|type)\s+[a-zA-Z_]\w*(?:<[^>]*>)?"),
            # 21. comprehensions: Iterators / Comprehensions. Functional iterator patterns.
            "comprehensions": re.compile(
                r"\b(?:pairs|ipairs|next|string\.gmatch)\b|\b(?:lume|moses|_\.)(?:map|filter|reduce|each|find|any|all)\b"
            ),
            # 22. scientific: Numerical / Compute Libraries. Standard math library.
            "scientific": re.compile(r"\b(math\.[a-zA-Z0-9_]+|bit32\.[a-zA-Z0-9_]+)\b|<<|>>|//"),
            # 23. heat_triggers: Metaprogramming & Reflection. Metatable overrides and Dunder methods.
            "reflection_metaprogramming": re.compile(
                r"\b(__index|__newindex|__call|__add|__sub|__mul|__div|__mod|__pow|__unm|__idiv|__band|__bor|__bxor|__bnot|__shl|__shr|__concat|__len|__eq|__lt|__le|__gc|__close|__mode)\b"
            ),
            # 24. import (Dependency Inclusions)
            "import": re.compile(r"\b(?:require|dofile)\b[ \t\n]*\(?[ \t\n]*['\"]", re.M),
            "_dependency_capture": re.compile(
                # =====================================================================
                # [ FUTURE LLM CONTEXT: THE DYNAMIC EXECUTION SHIFT (LUA) ]
                # PURPOSE: Extracts external dependencies for the Network Graph and Firewall.
                #
                # HISTORICAL BUG: Anchored to `^[ \t]*`. In Lua, modules are simply tables
                # returned by the `require` function. They are frequently lazy-loaded
                # inside local functions or conditionally assigned. Furthermore, because
                # the regex demanded the assignment (`local x = require...`) to touch the
                # left margin, it missed indented conditionals and inline evaluations entirely.
                #
                # THE FIX: Stripped the `^` anchor and completely deleted the bloated
                # variable-assignment capture group. We now scan directly for the `require`
                # or `dofile` boundary.
                #
                # [ THE PARENTHESIS SHIELD ]
                # Lua allows calling functions with a single string argument without
                # parentheses: `require "math"` vs `require("math")`. The `\(?` safely
                # bridges both syntaxes.
                # =====================================================================
                r"\b(?:require|dofile)[ \t\n]*\(?[ \t\n]*['\"]([^'\"]+)['\"]",
                re.M,
            ),
            # 25. ownership: Authorship metadata in comments.
            "ownership": re.compile(
                r"--\s*(?:Author|Copyright|License|Maintainer):\s+([^\n]+)|---\s*@author\s+([^\n]+)",
                re.I | re.M,
            ),
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            # 26. planned_debt: The Promise. Future work markers.
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt: The Fracture. Admitted fragility or hacks.
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            # 29. spec_exposure: Map vs. Territory. Audit tags.
            "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)\]", re.I),
            # 30. tabs_vs_spaces (Formatting Inconsistencies): Indentation Tracker. Tabs vs Spaces density.
            "tabs_vs_spaces": None,
            # 31. ssr_boundaries: View Horizon. Server-side rendering (Lapis/OpenResty).
            "ssr_boundaries": re.compile(
                r"\b(ngx\.say|ngx\.print|ngx\.exit|ngx\.req|lapis\.Serve|lapis\.Application)\b"
            ),
            # 32. events: Pub/Sub Network. Signal handlers and event brokers.
            "events": re.compile(
                r"\b(addEventListener|removeEventListener|dispatchEvent|on|emit|EventEmitter|Connect|FireServer|FireClient)\b"
            ),
            # 33. dependency_injection: Inversion of Control. Service locator patterns.
            "dependency_injection": re.compile(r"\b(inject|container:get|container:resolve|Locator)\b"),
            # 34. macros: Preprocessor Hooks. (Lua lacks a native preprocessor).
            "macros": None,
            # 35. pointers: Memory Map. FFI raw memory interactions.
            "pointers": re.compile(
                r"\b(ffi\.cast|ffi\.new|ffi\.cdef|ffi\.typeof|ffi\.sizeof|ffi\.alignof|ffi\.offsetof|ffi\.string|ffi\.copy|ffi\.fill)\b"
            ),
            # 36. memory_alloc: Manual Memory Management. Garbage collection triggers and FFI malloc.
            "memory_alloc": re.compile(
                r"\b(ffi\.C\.malloc|ffi\.C\.free|ffi\.C\.calloc|ffi\.C\.realloc|collectgarbage)\b"
            ),
            # 37. inline_asm: Bare Metal.
            "inline_asm": None,
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # 38. telemetry: Professional diagnostics.
            "telemetry": re.compile(r"\b(?:log\.(?:info|warn|error|debug|trace)|ngx\.log|ngx\.ERR|ngx\.INFO)\b"),
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs): Standard output.
            "debug_prints": re.compile(r"\b(print|warn|io\.write)\b"),
            # 40. explicit_casts (Explicit Type Casting): "Trust Me" Tax.
            "explicit_casts": re.compile(r"\b(ffi\.cast|tonumber|tostring)\b"),
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
            "panics_and_aborts": re.compile(r"\b(error|assert|os\.exit)\b"),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
            "thread_sleeps": re.compile(r'\b(task\.wait|os\.execute\s*\(?[\'"]sleep)\b'),
            # 43. bitwise_ops (Bitwise Operations)
            "bitwise_ops": re.compile(r"<<|>>|&|\||\^|~(?!=)"),
            # 44. sync_locks (Resource Management & Stability)
            "sync_locks": re.compile(r"\b(mutex|lock|semaphore|critical_section|uv\.mutex)\b", re.I),
            # 45. immutability_locks (Immutability Constraints)
            "immutability_locks": re.compile(r"<\s*const\s*>"),
            # 46. cleanup (Resource Cleanup / Teardown)
            "cleanup": re.compile(
                r"\b(ffi\.C\.free|collectgarbage|io\.close|:[ \t]*close)\b|<\s*(?:close|toclose)\s*>"
            ),
            # 47. encapsulation
            "encapsulation": re.compile(r"\b(local|_ENV)\b|---@private", re.M),
            # 48. listeners (Event Listeners / Observers)
            "listeners": re.compile(r"\b(on\s*\(|subscribe|Connect|addEventListener)\b"),
            # 49. test_skip (Bypassed Tests / Ignored Specs)
            "test_skip": re.compile(r"\b(xdescribe|xit|skip)\b"),
            # --- PHASE 3: HYBRID DOMAIN SENSORS (Lua Specifics) ---
            "serialization_parsing": re.compile(r"\b(string\.dump|loadstring|load|cjson\.decode|cjson\.encode)\b"),
            "regex_execution": re.compile(r"\b(string\.match|string\.gmatch|string\.find|string\.gsub)\b"),
            "time_date_logic": re.compile(r"\b(os\.time|os\.clock|os\.date|os\.difftime)\b"),
            "ipc_rpc_bridges": re.compile(
                r"\b(os\.execute|io\.popen|coroutine\.create|coroutine\.resume|coroutine\.yield)\b"
            ),
        },
    },
    "perl": {
        "_meta": {
            "target_version": "Perl 5.42.0 (Corinna Native OOP, Signatures, Try/Catch, Defer)",
            "last_updated": "2026-02-18",
            "blueprint_version": "v5.0",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard scripts, modules, tests, POD docs, and legacy CGI web scripts.
        "extensions": [".pl", ".pm", ".t", ".pod", ".plx", ".cgi", ".al", ".ph"],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: Core build scripts that are purely executed Perl code.
        "exact_matches": ["Makefile.PL", "Build.PL"],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions and CPAN metadata to resolve .pl (Prolog collision) and .t.
        "discriminators": [
            ".pm",
            ".pod",
            ".pl",
            "cpanfile",
            "cpanfile.snapshot",
            "META.json",
            "META.yml",
        ],
        # EXECUTION SIGNATURES: Interpreters found on Line 1.
        "shebangs": ["perl", "perl5", "perl6"],
        # UPGRADED: Maps to Family 6 (Polyglot)
        # Rationale: Perl’s interaction with POD documentation blocks (=head, =cut) and embedded regex makes it a true polyglot lexical engine.
        "lexical_family": "standard_block",
        "rules": {
            # --- LEXICAL DELIMITER CONTROLS ---
            # Perl uses '#' for standard line-level literature.
            "_line_anchor": re.compile(r"#"),
            # Inline comments are also triggered by the '#' token.
            "_inline_comment": re.compile(r"#"),
            # Block comment start: Perl uses POD (Plain Old Documentation) blocks.
            "_block_start": re.compile(r"^=\w+", re.M),
            # Block comment end: POD blocks are explicitly closed by '=cut'.
            "_block_end": re.compile(r"^=cut", re.M),
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # 1. branch: Decisions that split the flow. Includes modern try/catch/finally and defer.
            "branch": re.compile(
                r"\b(if|unless|elsif|else|while|until|for|foreach|given|when|next|last|redo|try|catch|finally|defer|goto|continue|default)\b|&&|\|\||//|\?|:"
            ),
            # 2. args: Parameters / Coupling. Captures modern signatures, traditional @_ unpacking, and shift.
            "args": re.compile(
                r"\b(?:sub|method)\s+(?:[a-zA-Z_]\w*\s*)?\([^)]*\)|\bmy\s*\([^)]*\)[ \t]*=\s*@_|\bshift\b"
            ),
            # 3. linear: Sequential I/O & Network Boundaries. Structural boundaries. EXCLUDES access modifiers and immutability.
            "structural_boundaries": re.compile(
                r"\b(my|our|state|local|field|class|role|package|return|yield|use|require|undef|do|true|false|await)\b"
            ),
            # 4. func_start (Executable Logic Anchors)
            # Anchors executable logic blocks. MUST HAVE EXACTLY ONE CAPTURE GROUP for the name.
            #
            # LLM/MAINTAINER CONTEXT & DOMAIN KNOWLEDGE:
            # 1. THE KEYWORDS: Captures standard `sub` and Perl 5.38+ Corinna OOP `method`.
            # 2. THE CAPTURE: `([a-zA-Z_]\w*)` isolates the exact function name.
            # 3. THE LOOKAHEAD GUARDRAILS `(?= ... )`: Perl allows a lot of junk between the name and the code block.
            #    - `\(` : Safely steps over legacy Prototypes `sub foo ($$)` and modern Signatures `sub foo ($a, $b)`.
            #    - `:`  : Safely steps over Subroutine Attributes `sub foo : lvalue : method {`.
            #    - `\{` : Matches standard immediate block openings `sub foo {`.
            #    - `\n|$`: Handles K&R style newline brace placements.
            "func_start": re.compile(
                # =====================================================================
                # [ THE VERTICAL SUBROUTINE SHIELD (PERL) ]
                # Perl 5 (and modern Corinna OOP) allows newlines between the `sub`/`method`
                # keyword and the function name.
                # FIX: Exchanged `\s+` (which triggers ReDoS if unbounded) with a strictly
                # controlled `[ \t\n]+` to allow vertical jumps. Upgraded the trailing
                # lookahead to safely handle vertical gaps before the opening `{` or `(`.
                # =====================================================================
                r"^[ \t]*(?:sub|method)[ \t\n]+"
                r"([a-zA-Z_]\w*)"
                r"(?=[ \t\n]*[:\(\{]|$)",
                re.M,
            ),
            # 5. class_start: Object / Entity Declarations. Defines object-oriented and structural boundaries.
            "class_start": re.compile(
                r"^[ \t]*(?:package|class|role)\s+([a-zA-Z_]\w*(?:::[a-zA-Z_]\w*)*)(?=[ \t]*[;\{]|\n|$)",
                re.M,
            ),
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            # 6. safety: Defensive Programming. Defensive constructs (strict, warnings, safe exceptions).
            "safety": re.compile(
                r"\b(use\s+strict|use\s+warnings|use\s+v5\.\d+|croak|confess|try|catch|finally|eval[ \t]*\{|defer|isa|DOES)\b|->isa\b|->DOES\b"
            ),
            # 7. safety_neg: Safety Bypasses. Actively bypassing safety (no strict, string eval).
            "safety_bypasses": re.compile(r'\b(no\s+strict|no\s+warnings|eval\s*["\']|eval\s+(?!\w|{)|goto\s+\&)\b'),
            # 8. danger: High-Risk Execution. Process killers and raw shell execution.
            "high_risk_execution": re.compile(r"\b(system|exec|exit|qx|CORE::dump)\b|`[^`]+`"),
            # 9. io: I/O & Network Boundaries. Disk, Network, DBI, and standard handles.
            "io": re.compile(
                r"\b(open|close|sysopen|sysread|syswrite|opendir|closedir|DBI->connect|Mojo::UserAgent|HTTP::Tiny|LWP::UserAgent|socket|connect|bind)\b|<[A-Z_0-9]+>|<>"
            ),
            # 10. api: Public Surface Area. Exposed surface area (Exports and modern routing).
            "api": re.compile(
                r'\b(?:get|post|put|del|any|patch)\s+[\'"]/[^\'"]*[\'"]|@(?:EXPORT|EXPORT_OK|EXPORT_TAGS|ISA)\b|use\s+(?:Exporter|parent|base)\b|:\s*(?:reader|writer|param)\b'
            ),
            # 11. flux: State Mutation. State mutation (assignments, array mutators, substitutions).
            # UPDATED: Removed '.=' and '=~' / '!~' to prevent massive string-builder false positives.
            "state_mutation": re.compile(
                r"\b(?:push|pop|shift|unshift|splice|delete)\b|[\$@%][a-zA-Z_]\w*(?:->|\[|\{){0,5}\s*(?:\+|-|\*|/|\||&|\^|%|x)?=(?!=)|(?:\+\+|--)|\bs/"
            ),
            # 12. dead_code (Commented Logic / Deprecated Trails) Commented out structural logic.
            "dead_code": re.compile(
                r"^[ \t]*#\s*(?:my|our|state|sub|method|class|package|if|unless|while|print|say)\b",
                re.M,
            ),
            # 13. doc: Structured Documentation. Structured POD documentation.
            "doc": re.compile(r"^=(?:pod|head[1-6]|item|over|back|cut|begin|end|encoding|for)\b", re.M),
            # 14. test: Testing & Assertions. Assertions and Test frameworks.
            "test": re.compile(
                r"\b(?:Test2::V0|Test::More|cmp_ok|is_deeply|subtest|done_testing|BAIL_OUT)\b|\b(?:ok|is|isnt|like|unlike|plan|diag|note)\s*\("
            ),
            # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
            # 15. concurrency: Temporal Static. Async, forks, and threads.
            "concurrency": re.compile(
                r"\b(async|await|fork|waitpid|threads(?:->create)?|threads::shared|AnyEvent|Coro|Mojo::IOLoop|Mojo::Promise|Future|Parallel::ForkManager)\b"
            ),
            # 16. ui_framework: UI / View Components. GUI libraries and template engines.
            "ui_framework": re.compile(
                r"\b(Tk::|Wx::|Gtk2::|Gtk3::|Prima::|Template|HTML::Mason|Mojolicious::Plugin::TagHelpers)\b|\brender(?:_to_string)?\b|<%|%>|\[%|%\]"
            ),
            # 17. closures: Closures / Anonymous Functions. Anonymous subroutines.
            "closures": re.compile(r"\bsub\s*(?:\([^)]*\))?[ \t]*\{"),
            # 18. globals: Global / Shared State. Magic variables and system globals.
            "globals": re.compile(
                r"(?:\$a|\$b|\$_|\$\$|\$@|\$!|\$\?|\$0|%ENV|%SIG|@ARGV|@INC)\b|^[ \t]*our\s+[\$@%]",
                re.M,
            ),
            # 19. decorators: Decorators / Annotations. Subroutine and variable attributes.
            "decorators": re.compile(r":\s*[a-zA-Z_]\w*(?:\([^)]*\))?"),
            # 20. generics: Generics / Type Parameters. Parameterized types (via Type::Tiny/Moose).
            "generics": re.compile(r"\b(?:ArrayRef|HashRef|Map|Tuple|Dict|Maybe|InstanceOf|ConsumerOf|Enum)\[[^\]]*\]"),
            # 21. comprehensions: Iterators / Comprehensions. Map and Grep.
            "comprehensions": re.compile(r"\b(?:map|grep|reduce|any|all|none|notall|first|List::Util)\b"),
            # 22. scientific: Numerical / Compute Libraries. PDL and Math::BigInt.
            "scientific": re.compile(
                r"\b(Math::Trig|Math::BigInt|Math::BigFloat|Math::Complex|PDL|sin|cos|exp|log|sqrt|atan2|abs|int|rand|srand)\b"
            ),
            # 23. heat_triggers: Metaprogramming & Reflection. Metaprogramming and Symbol table hacks.
            "reflection_metaprogramming": re.compile(
                r"\b(AUTOLOAD|DESTROY|BEGIN|UNITCHECK|CHECK|INIT|END|tie|untie|bless|overload)\b|\*[a-zA-Z_]\w*[ \t]*=\s*(?:\\|&)|goto\s+&"
            ),
            # 24. import (Dependency Inclusions)
            "import": re.compile(r"\b(?:use|require|no)\s+[a-zA-Z_]\w*(?:::[a-zA-Z_]\w*)*", re.M),
            "_dependency_capture": re.compile(
                # =====================================================================
                # [ FUTURE LLM CONTEXT: THE DYNAMIC EXECUTION SHIFT (PERL) ]
                # PURPOSE: Extracts external dependencies for the Network Graph and Firewall.
                #
                # HISTORICAL BUG: Anchored to `^[ \t]*`. While `use` is evaluated at
                # compile-time and is typically top-level, `require` is evaluated at
                # runtime and is very frequently scoped inside `if` statements or
                # subroutines to defer loading heavy modules. The line anchor blinded
                # the engine to these runtime inclusions.
                #
                # THE FIX: Stripped the `^` anchor and rely on the `\b` word boundary
                # to capture module loading anywhere in the execution path.
                # =====================================================================
                r"\b(?:use|require|no)\s+([a-zA-Z_]\w*(?:::[a-zA-Z_]\w*)*)",
                re.M,
            ),
            # 25. ownership: Authorship metadata.
            "ownership": re.compile(
                r"^=head1\s+(?:AUTHOR|COPYRIGHT|LICENSE)|#\s*(?:Author|Maintainer|Created by):\s+([^\n]+)",
                re.I | re.M,
            ),
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            # 26. planned_debt: The Promise. Future work markers.
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt: The Fracture. Admitted fragility or hacks.
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            # 29. spec_exposure: Map vs. Territory. Audit tags.
            "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]", re.I),
            # 30. tabs_vs_spaces (Formatting Inconsistencies): Indentation Tracker. Tabs vs 4-Spaces density markers.
            "tabs_vs_spaces": None,
            # 31. ssr_boundaries: View Horizon. Server-Side Rendering computation boundaries.
            "ssr_boundaries": re.compile(
                r"\b(Mojolicious::Controller|Dancer2|Catalyst::Controller|render|template|reply->|to_app)\b"
            ),
            # 32. events: Pub/Sub Network. Event-driven architecture signatures and message brokers.
            "events": re.compile(
                r'\b(?:emit|once|unsubscribe|catch|Mojo::EventEmitter|AnyEvent->condvar)\b|\b(?:on|subscribe)\s+[\'"]'
            ),
            # 33. dependency_injection: Inversion of Control. Inversion of Control (IoC) injection markers.
            "dependency_injection": re.compile(r"\b(Bread::Board|Beam::Wire|IOC|container|resolve|inject|service)\b"),
            # 34. macros: Preprocessor Hooks. Compiler pragmas or source filters.
            "macros": re.compile(
                r"\b(Filter::Simple|Filter::Util::Call|Devel::Declare|Keyword::Declare)\b|^[ \t]*BEGIN[ \t]*\{",
                re.M,
            ),
            # 35. pointers: Memory Map. Explicit tracking of memory addressing or references.
            # UPDATED: Removed '\\[$@%&*]\w+' to stop flagging standard pass-by-reference variables.
            "pointers": re.compile(r"->(?:\[[^\]]*\]|\{[^\}]*\})|@\$|%\$|\$\$|\&\$"),
            # 36. memory_alloc: Manual Memory Management. Explicit heap manipulations or reference count controls.
            "memory_alloc": re.compile(
                r"\b(Scalar::Util::weaken|Scalar::Util::isweak|Internals::SvREFCNT|Internals::SvREADONLY|undef|Devel::Peek)\b"
            ),
            # 37. inline_asm: Bare Metal. Direct architecture bridging via Inline modules.
            "inline_asm": re.compile(r'\buse\s+Inline\s+[\'"](?:C|CPP|ASM)[\'"]'),
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # 38. telemetry: The Professional. Structured logging and observability frameworks.
            "telemetry": re.compile(
                r"\b(?:Log::Log4perl|Log::Any|Mojo::Log|log_(?:info|debug|warn|error|fatal))\b|->(?:debug|info|warn|error|fatal|trace)\b",
                re.I,
            ),
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs): The Amateur / Space Debris. Ad-hoc debug statements.
            "debug_prints": re.compile(r"\b(print|say|printf|sprintf|warn)\b"),
            # 40. explicit_casts (Explicit Type Casting): The "Trust Me" Tax. Explicitly bypassing the type-checker or manual blessing.
            # UPDATED: Removed the pointer/reference overlap.
            "explicit_casts": re.compile(r"\b(int|oct|hex|vec|ref|bless)\b"),
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts): The Detonators. Forcefully destroying the current execution context.
            "panics_and_aborts": re.compile(r"\b(die|confess|croak|exit|BAIL_OUT)\b"),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses) Forcing a thread to sleep or blocking waits.
            "thread_sleeps": re.compile(r"\bsleep\b"),
            # 43. bitwise_ops (Bitwise Operations) Manipulating raw bytes and memory registers.
            # UPDATED: Added negative lookbehinds '(?<![=!])~' to ignore Perl regex operators.
            "bitwise_ops": re.compile(r"(?<!&)&(?!&)|(?<!\|)\|(?!\|)|<<|>>|\^|(?<![=!])~"),
            # 44. sync_locks (Resource Management & Stability)
            "sync_locks": re.compile(r"\b(lock|threads::shared|Thread::Semaphore)\b"),
            # 45. immutability_locks (Immutability Constraints) Explicitly locking data so it cannot be mutated.
            "immutability_locks": re.compile(r"\b(Readonly|Const::Fast|Internals::SvREADONLY)\b"),
            # 46. cleanup (Resource Cleanup / Teardown) Explicitly destroying state or releasing resources.
            "cleanup": re.compile(r"\b(DESTROY|undef|close|closedir|finish)\b|^[ \t]*END[ \t]*\{", re.M),
            # 47. encapsulation Explicitly hiding logic from the rest of the application.
            "encapsulation": re.compile(r"\b(my|state|local)\b|:private\b"),
            # 48. listeners (Event Listeners / Observers) Waiting to receive state from an external broadcast.
            "listeners": re.compile(r"\b(on\s*\(|subscribe\s*\(|add_listener)\b"),
            # 49. test_skip (Bypassed Tests / Ignored Specs) Code that bypasses test verification.
            "test_skip": re.compile(r"\b(skip|todo_skip)\b"),
            # --- PHASE 3: HYBRID DOMAIN SENSORS (Perl Specifics) ---
            "serialization_parsing": re.compile(
                r"\b(Storable::(?:thaw|fd_retrieve)|JSON::(?:decode_json|from_json)|YAML::(?:Load|LoadFile))\b"
            ),
            "regex_execution": re.compile(
                r"(=~|!~|\b(?:qr|m|s|tr|y)\b\s*[/\W])"
            ),  # Catches Perl's native binding operators and regex quotes
            "time_date_logic": re.compile(r"\b(localtime|gmtime|Time::HiRes|sleep|time)\b"),
            "ipc_rpc_bridges": re.compile(
                r"\b(system\s*\(|exec\s*\(|fork|IPC::Open[23]|qx\b|`.*`)\b"
            ),  # Backticks and qx// are shell executions
        },
    },
    "haskell": {
        "_meta": {
            "target_version": "GHC 9.14.1+ (Linear Types, cases, Type Abstractions, RecordDotSyntax)",
            "last_updated": "2026-02-18",
            "blueprint_version": "v5.0",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard source, literate Haskell, and C-preprocessor Haskell.
        "extensions": [".hs", ".lhs", ".hsc", ".ghci"],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: Cabal custom setup scripts that evaluate as pure Haskell.
        "exact_matches": ["Setup.hs", "Setup.lhs"],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions, Stack configs, and Cabal manifests to anchor the ecosystem.
        "discriminators": [".hs", ".lhs", "stack.yaml", "cabal.project", ".cabal"],
        # EXECUTION SIGNATURES: Interpreters found on Line 1 for script-based Haskell execution.
        "shebangs": ["runhaskell", "runghc", "stack", "ghci"],
        # UPGRADED: Maps to Family 5 (Hybrid Dash)
        # Rationale: Uses '--' for lines and '{- -}' for blocks, which strictly supports recursive nesting.
        "lexical_family": "standard_block",
        "rules": {
            # --- LEXICAL DELIMITER CONTROLS ---
            # Haskell uses '--' for line-level Commented / Non-Executable Text.
            # CRITICAL GUARDRAIL: Negative lookahead ensures we don't accidentally split on custom operators like '-->'
            "_line_anchor": re.compile(r"--+(?![!#$%&*+./<=>?@\\^|~-])"),
            # Inline comments follow the same highly-specific symbol guard
            "_inline_comment": re.compile(r"--+(?![!#$%&*+./<=>?@\\^|~-])"),
            # Block comment start: {-
            "_block_start": re.compile(r"\{-"),
            # Block comment end: -}
            "_block_end": re.compile(r"-\}"),
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # branch: decisions that split flow. Includes guards (|) and modern \cases.
            "branch": re.compile(r"\b(if|then|else|case|of|MultiWayIf)\b|\\cases?|^[ \t]*\|", re.M),
            # args: Parameters / Coupling. Captures type signatures, lambda bindings, and explicit @type apps.
            "args": re.compile(r"::\s*[^=\n]+(?:->|=>|⊸)|\\[a-zA-Z0-9_\'\s,()\[\]]+->|@[A-Z][a-zA-Z0-9_\']*"),
            # linear: Sequential I/O & Network Boundaries. Structural boundaries defining scope and data definitions.
            "structural_boundaries": re.compile(
                r"\b(module|data|type|newtype|class|instance|let|in|where|do|mdo|deriving|family|pattern)\b|%1\s*->|⊸"
            ),
            # 4. func_start: Executable Logic Anchors. Anchors executable logic (Type Signatures).
            # EXCLUDES data/type/class declarations to fix False Positives.
            "func_start": re.compile(
                # =====================================================================
                # THE HASKELL UPPERCASE TRAP:
                # While Haskell idiomatic convention strongly enforces lowercase `[a-z_]`
                # for function names, enforcing this strictly at the regex level caused
                # the engine to miss valid (but non-standard) functions or FFI exports.
                # FIX: Opened the leading character class to `[a-zA-Z_]`. The negative
                # lookahead `(?!(?:data|type...))` already prevents collisions with types.
                # =====================================================================
                r"^[ \t]*(?!(?:data|type|newtype|class|instance)\b)([a-zA-Z_][a-zA-Z0-9_\']*)(?=\s*::)",
                re.M,
            ),
            # class_start: Object / Entity Declarations. Defines structural entities and typeclass boundaries.
            "class_start": re.compile(
                r"^[ \t]*(?:data|newtype|class|type(?:\s+family)?)\s+([A-Z][a-zA-Z0-9_\']*)(?=\s*[=|]|\n|$)",
                re.M,
            ),
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            # safety: Defensive Programming. Functional safety (Maybe/Either) and exception brackets.
            "safety": re.compile(
                r"\b(Maybe|Either|Just|Nothing|Right|Left|try|catch|bracket|finally|onException|SafeT|mask|pure|return)\b"
            ),
            # safety_neg: Safety Bypasses. Bypassing purity (unsafePerformIO) and partial functions.
            "safety_bypasses": re.compile(
                r"\b(unsafePerformIO|unsafeCoerce|error|undefined|fromJust|head|tail|init|last|throw|unsafeFixIO)\b"
            ),
            # danger: High-Risk Execution. Forceful aborts and Debug-trace leaks in production.
            "high_risk_execution": re.compile(r"\b(die|exitWith|exitFailure|Debug\.Trace|trace|traceShow|traceIO|traceM)\b"),
            # io: I/O & Network Boundaries. IO Monad and hardware interactions.
            "io": re.compile(
                r"\b(IO|readFile|writeFile|appendFile|hGetContents|hPutStr|openFile|withFile|getLine|getChar|Socket|Connection|runDB)\b"
            ),
            # api: Public Surface Area. Captured via module headers. Captures both explicit lists and implicit "all" exports.
            "api": re.compile(
                r"^[ \t]*module\s+[A-Z][a-zA-Z0-9_.]*(?:\s*\([^)]*\))?\s*where|\bforeign\s+export\b",
                re.M,
            ),
            # flux: State Mutation. State mutation (IORef/MVar) and monadic binds (<-).
            "state_mutation": re.compile(
                r"\b(IORef|STRef|TVar|MVar|TMVar|modifyIORef\'?|writeIORef|putMVar|modify|put|StateT)\b|<-"
            ),
            # 12. dead_code (Commented Logic / Deprecated Trails)
            "dead_code": re.compile(
                r"--\s*(?:data|type|newtype|class|instance|let|where|import|putStrLn)\b",
                re.M,
            ),
            # doc: Structured Documentation. Haddock documentation markers.
            "doc": re.compile(r"--\s*\||--\s*\^|\{-\||--\s*@(?:param|return|author)"),
            # test: Testing & Assertions. Verification framework keywords (QuickCheck/Hspec).
            "test": re.compile(
                r'\b(?:hspec|QuickCheck|prop_[a-zA-Z0-9_\']+|assertEqual|shouldBe|testGroup|testCase)\b|\b(?:describe|it|property)\s+"'
            ),
            # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
            # concurrency: Temporal Static. STM, async, and thread forking.
            "concurrency": re.compile(r"\b(forkIO|forkOS|async|wait|cancel|MVar|TVar|STM|atomically|threadDelay)\b"),
            # ui_framework: UI / View Components. Functional reactive GUI and web components.
            "ui_framework": re.compile(r"\b(Threepenny|Brick|Reflex|Miso|Gtk|widget|vBox|hBox|Lucid|Blaze|Monomer)\b"),
            # closures: Closures / Anonymous Functions. Anonymous lambda depth.
            "closures": re.compile(r"\\[a-zA-Z0-9_\'\s(),\[\]]+\s*->|\\cases?"),
            # globals: Global / Shared State. Top-level state hacks (typically MVars using unsafePerformIO).
            "globals": re.compile(
                r"^[ \t]*[a-z_][a-zA-Z0-9_\']*\s*::\s*(?:IORef|TVar|MVar)[^=]*unsafePerformIO",
                re.M,
            ),
            # decorators: Decorators / Annotations. GHC pragmas (INLINE, LANGUAGE).
            "decorators": re.compile(r"\{-#\s*(?:INLINE|NOINLINE|LANGUAGE|OPTIONS_GHC|RULES|MINIMAL)\s+[^#]*#-\}"),
            # generics: Generics / Type Parameters. forall quantification and constraints.
            "generics": re.compile(
                r"\bforall\s+[^.]+\.|\b(?:[A-Z][a-zA-Z0-9_\']*\s+[a-z][a-zA-Z0-9_\']*[ \t]*=>)|\([^)]+\)[ \t]*=>"
            ),
            # comprehensions: Iterators / Comprehensions. List comprehensions and dense monad applicatives.
            "comprehensions": re.compile(r"\[\s*[^|\]]+\s*\|[^\]]+\]|<\$>|<\*>|>>="),
            # scientific: Numerical / Compute Libraries. Advanced Math and Linear Algebra.
            "scientific": re.compile(
                r"\b(Complex|RealFloat|Floating|Numeric\.LinearAlgebra|Matrix|Vector|ad|grad|jacobian|sin|cos|tan|exp|log|pi)\b"
            ),
            # heat_triggers: Metaprogramming & Reflection. QuasiQuotes and Template Haskell.
            "reflection_metaprogramming": re.compile(
                r"\b(TemplateHaskell|QuasiQuotes|TypeFamilies|GHC\.Generics|Generic)\b|\[[a-z_]+\||\$\([a-zA-Z0-9_\']+\)"
            ),
            # import: Dependency Inclusions. Module resolution.
            "import": re.compile(r"^[ \t]*import\s+(?:qualified[ \t]+)?[A-Z][a-zA-Z0-9_.]*", re.M),
            "_dependency_capture": re.compile(r"^[ \t]*import\s+(?:qualified\s+)?([A-Z][a-zA-Z0-9_.]*)", re.M),
            # ownership: Authorship indicators in comments.
            "ownership": re.compile(r"--\s*\|?\s*(?:Author|Maintainer|Copyright|License):\s+([^\n]+)", re.I),
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            "planned_debt": GLOBAL_PLANNED_DEBT,
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            "spec_exposure": re.compile(r"\[(?:spec-[0-9]+|audit|rfc)\]", re.I),
            "tabs_vs_spaces": None,
            "ssr_boundaries": re.compile(
                r"\b(Yesod|Servant|ScottyM|ActionM|lucid|blaze-html|ToJSON|FromJSON|Handler|respond)\b"
            ),
            "events": re.compile(
                r"\b(Event|Behavior|Dynamic|reactive-banana|reflex|frp|stepper|accumE|conduit|Pipes|Stream)\b"
            ),
            "dependency_injection": re.compile(r"\b(ReaderT|MonadReader|Has[A-Z][a-zA-Z0-9_\']+|ask|asks|local)\b"),
            "macros": re.compile(
                r"\{-#\s*LANGUAGE\s+[^#]*#-\}|\$[(a-z_A-Z0-9\']|^[ \t]*#(?:define|undef|if|ifdef|ifndef|elif|else|endif|include)\b",
                re.M,
            ),
            "pointers": re.compile(r"\b(Ptr|ForeignPtr|FunPtr|StablePtr|peek|poke|castPtr|plusPtr|nullPtr|Storable)\b"),
            "memory_alloc": re.compile(r"\b(malloc|mallocBytes|alloca|allocaBytes|free|Foreign\.Marshal)\b"),
            "inline_asm": re.compile(r"\bforeign\s+import\s+(?:ccall|cplusplus|prim|capi)\b"),
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # telemetry: Professional structured logging.
            "telemetry": re.compile(r"\b(?:logDebug|logInfo|logWarn|logError|logOther|katip|MonadLogger|LoggerT)\b"),
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs)
            "debug_prints": re.compile(r"\b(putStr|putStrLn|print|putChar)\b"),
            # # # 40. explicit_casts (Explicit Type Casting) "Trust Me" Tax.
            "explicit_casts": re.compile(r"\b(unsafeCoerce|coerce|fromIntegral|realToFrac|floor|ceiling|truncate|round)\b"),
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
            "panics_and_aborts": re.compile(r"\b(throw|throwIO|panic|error)\b"),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
            "thread_sleeps": re.compile(r"\b(threadDelay)\b"),
            # 43. bitwise_ops (Bitwise Operations)
            "bitwise_ops": re.compile(
                r"\b(?:shift[LR]?|rotate[LR]?|xor|complement|testBit|setBit|clearBit|complementBit)\b|\.&&\.|\|\.\|\|\."
            ),
            # sync_locks: Barricades preventing races.
            "sync_locks": re.compile(r"\b(takeMVar|putMVar|readMVar|swapMVar|atomically|STM|Mutex|lock|unlock)\b"),
            # 45. immutability_locks (Immutability Constraints)
            "immutability_locks": re.compile(r"\b(pure|return|frozen|immutable|const)\b"),
            # 46. cleanup (Resource Cleanup / Teardown)
            "cleanup": re.compile(r"\b(hClose|close|free|bracket|finally|onException)\b"),
            # 47. encapsulation (Encapsulation / Access Modifiers)
            "encapsulation": re.compile(
                r"^[ \t]*module\s+[A-Z][a-zA-Z0-9_.]*\s*\([^)]*\)\s*where", re.M
            ),
            # 48. listeners (Event Listeners / Observers)
            "listeners": re.compile(r"\b(subscribe|onEvent|addEventListener|watch)\b"),
            # 49. test_skip (Bypassed Tests / Ignored Specs) Safety Theater.
            "test_skip": re.compile(r"\b(ignore|pending|skip|xit|xdescribe)\b"),
            # --- PHASE 3: HYBRID DOMAIN SENSORS (Haskell Specifics) ---
            "serialization_parsing": re.compile(
                r"\b(Data\.Aeson|decode|decodeStrict|fromJSON|Data\.Binary|Data\.Serialize)\b"
            ),
            "regex_execution": re.compile(r"\b(Text\.Regex|makeRegex|matchRegex|=~)\b"),
            "time_date_logic": re.compile(r"\b(getCurrentTime|diffUTCTime|addUTCTime|System\.Time|threadDelay)\b"),
            "ipc_rpc_bridges": re.compile(
                r"\b(System\.Process|createProcess|callProcess|callCommand|forkIO|Control\.Concurrent)\b"
            ),
        },
    },
    "embedded_python": {
        "_meta": {
            "target_version": "Embedded Python (MicroPython / CircuitPython / Bare-Metal)",
            "last_updated": "2026-02-18",
            "blueprint_version": "v5.0",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard Python suffixes and pre-compiled MicroPython bytecode (.mpy).
        "extensions": [".py", ".mpy"],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: The strict execution entry points for microcontroller boot sequences.
        "exact_matches": ["boot.py"],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions, boot sequence files, and the MicroPython package installer (mip) configs.
        "discriminators": ["boot.py", "mip.json", "upip"],
        # EXECUTION SIGNATURES: Interpreters found on Line 1 for embedded discovery and cross-compilation.
        "shebangs": ["micropython", "mpy-cross"],
        # Instantly claims any .py file utilizing embedded electronics networking or GPIO libraries
        "internal_discriminator": re.compile(
            r"^[ \t]*(?:import|from)\s+(?:machine|board|microcontroller|busio|digitalio|analogio|usb_hid|neopixel|rp2|esp32|pyb|wifi|socketpool)\b",
            re.M,
        ),
        # UPGRADED: Maps to Family 3 (Pure Hash)
        # Rationale: Uses '#' for line-level literature; multi-line literature
        # (docstrings) is handled by the Section 2.3.C.3 Heuristic Pass.
        "lexical_family": "line_exclusive",
        "rules": {
            # --- LEXICAL DELIMITER CONTROLS ---
            # MicroPython uses '#' for line-level Commented / Non-Executable Text.
            "_line_anchor": re.compile(r"#"),
            # Inline comments are also triggered by the '#' token.
            "_inline_comment": re.compile(r"#"),
            # EXPLICIT: MicroPython lacks native multi-line block comment delimiters.
            # (Note: Multi-line strings used as docs are handled by the 2.3.C Python Heuristic).
            "_block_start": None,
            "_block_end": None,
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # 1. branch (Control Flow / Branching)
            # Decisions and logical jumps. EXCLUDES raise (bailout_hits).
            "branch": re.compile(r"\b(if|elif|else|for|while|with|try|finally|match|case|and|or)\b"),
            # 2. args (Parameters / Coupling)
            # Parameter blocks of functions/lambdas. Bounded negation to prevent ReDoS.
            "args": re.compile(
                r"(?:async[ \t]+)?def\s+[a-zA-Z_]\w*\s*\([^)]*\)|\blambda\s+[^:]+:",
                re.M,
            ),
            # 3. linear (Sequential Boundaries)
            # Structural boundaries. EXCLUDES: _private (encapsulation) and Final (freeze_hits).
            "structural_boundaries": re.compile(
                r"\b(def|class|return|import|from|as|pass|continue|break|yield|await|assert|del|global|nonlocal|type)\b"
            ),
            # 4. func_start (Executable Logic Anchors)
            # ONLY executable logic blocks. EXCLUDES classes. Steps safely over hardware decorators.
            "func_start": re.compile(
                r"^[ \t]*(?:@[\w.]+(?:\([^)]*\))?[ \t]+){0,5}(?:async[ \t]+)?def\s+([a-zA-Z_]\w*)(?=\s*\()",
                re.M,
            ),
            # 5. class_start (Object / Entity Declarations)
            "class_start": re.compile(
                r"^[ \t]*(?:@[\w.]+(?:\([^)]*\))?[ \t]+){0,5}class\s+([a-zA-Z_]\w*)(?=[ \t]*[\(:]|\n|$)",
                re.M,
            ),
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            # 6. safety (Defensive Programming / Validation)
            # Hardware watchdogs and standard Python safety checks.
            "safety": re.compile(
                r"\b(try|except|finally|assert|machine\.WDT|isinstance|issubclass|hasattr|getattr|alloc_emergency_exception_buf)\b"
            ),
            # 7. safety_neg (Safety Bypasses / Unchecked Types)
            # Bare excepts and blocking the event loop (detrimental in embedded async).
            "safety_bypasses": re.compile(
                r"\bpass\b[ \t]*$|except\s*[:\n]|except\s+(?:Base)?Exception|from\s+[\w.]+\s+import\s+\*|\btime\.sleep(?:_ms|_us)?\b",
                re.M,
            ),
            # 8. danger (High-Risk Execution / System Calls)
            # Hardware resets and raw memory pokes. EXCLUDES TODO (debt) and print (print_hits).
            "high_risk_execution": re.compile(
                r"\b(machine\.reset|machine\.deepsleep|machine\.bootloader|machine\.disable_irq|eval|exec|sys\.exit)\b"
            ),
            # 9. io (I/O & Network Boundaries)
            # Hardware Peripherals (I2C, SPI, UART, Pin) and Networking.
            "io": re.compile(
                r"\b(open|Pin|I2C|SPI|UART|ADC|PWM|RTC|SDCard|I2S|WLAN|LAN|socket|usocket|uos\.mount|aiohttp)\b"
            ),
            # 10. api (Public Surface Area)
            # Implicit public defaults (undercased root defs) + explicit exports.
            "api": re.compile(
                r"^[ \t]*(?:async[ \t]+)?def\s+[^_]\w+|^[ \t]*class\s+[^_]\w+|^__all__[ \t]*=",
                re.M,
            ),
            # 11. flux (State Mutation)
            # State mutation including hardware value toggling.
            "state_mutation": re.compile(
                r"\bglobal\b|\bnonlocal\b|\b(?:self|cls)\.\w+[ \t]*=|:=|(?:\.\w+)?\.(?:append|extend|update|pop|remove|insert|clear)\s*\(|\.(?:value|on|off|high|low|toggle)\s*\("
            ),
            # 12. dead_code (Commented Logic / Deprecated Trails)
            "dead_code": re.compile(r"#[ \t]*(?:def|class|import|if|for|while|try|print|machine\.Pin)\b"),
            # 13. doc (Structured Documentation)
            "doc": re.compile(r'"""|\'\'\'|:param|:return|:raises|:type|#\s*Pin[ \t]*=|#\s*GPIO'),
            # 14. test (Testing & Assertions)
            "test": re.compile(r"\b(unittest|pytest|assert|test_|setUp|tearDown|Mock)\b"),
            # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
            # 15. concurrency (Asynchronous Execution)
            "concurrency": re.compile(
                r"\b(async|await|uasyncio|asyncio|Timer\.init|_thread|start_new_thread|allocate_lock|gather|create_task|Event|Lock)\b"
            ),
            # 16. ui_framework (UI / View Components)
            # Framebuffers and embedded OLED/TFT drivers.
            "ui_framework": re.compile(
                r"\b(framebuf|ssd1306|st7789|ili9341|epaper|lvgl|display|text|fill|pixel|show|scroll)\b"
            ),
            # 17. closures (Closures / Anonymous Functions)
            "closures": re.compile(r"\blambda\b"),
            # 18. globals (Global / Shared State)
            "globals": re.compile(r"\bglobal\b|\bglobals\(\)|\blocals\(\)|\b(sys\.path|sys\.modules|os\.environ)\b"),
            # 19. decorators (Decorators / Annotations)
            # Generic decorators. (Specific ASM/Viper optimizations moved to heat_triggers/inline_asm).
            "decorators": re.compile(
                r"^[ \t]*@(?!(?:micropython\.viper|micropython\.asm|micropython\.native))[\w.]+",
                re.M,
            ),
            # 20. generics (Generics / Type Parameters)
            "generics": re.compile(
                r"\b(?:List|Dict|Set|Tuple|Optional|Union|Any|Callable|Sequence|Iterable)\[[^\]]*\]|->"
            ),
            # 21. comprehensions (Iterators / Comprehensions)
            "comprehensions": re.compile(r"\[[^\]]*\bfor\b[^\]]*\]|\{[^}]*\bfor\b[^}]*\}|\([^)]*\bfor\b[^)]*\)"),
            # 22. scientific (Numerical / Compute Libraries)
            # Math, complex arrays, and ulab (MicroPython's NumPy).
            "scientific": re.compile(
                r"\b(math|cmath|ulab|numpy|ndarray|struct\.pack|struct\.unpack|bin|hex|oct|abs|sin|cos|tan)\b"
            ),
            # 23. heat_triggers (Metaprogramming & Reflection)
            # High Cognitive Load: Dunder methods and Viper/Native emitters.
            "reflection_metaprogramming": re.compile(
                r"__(?:getattr|setattr|new|call|dict|dir|import)__|@(?:staticmethod|classmethod|property)|@micropython\.(?:viper|native)\b|\b(?:getattr|setattr|hasattr)\b"
            ),
            # 24. import (Dependency Inclusions)
            "import": re.compile(r"^[ \t]*(?:import|from)\b\s+[\w.]+", re.M),
            "_dependency_capture": re.compile(r"^[ \t]*(?:import|from)\b\s+([\w.]+)", re.M),
            # 25. ownership (Authorship Metadata)
            "ownership": re.compile(r"(?:__author__[ \t]*=|Author:|Created by:)\s*(.*)", re.I),
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            # 26. planned_debt (Annotated Debt / TODOs)
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            # 29. spec_exposure (Spec / Audit Traceability)
            "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]", re.I),
            # 30. tabs_vs_spaces (Formatting Inconsistencies) 
            "tabs_vs_spaces": None,
            # 31. ssr_boundaries (Server-Side Rendering)
            # Lightweight web servers (Microdot, Picoweb).
            "ssr_boundaries": re.compile(
                r"\b(microdot|picoweb|MicroWebSrv|tinyweb|render_template|Response|@app\.get|@app\.post)\b"
            ),
            # 32. events (Event Emitters / Pub-Sub)
            # Hardware interrupts and async event flags.
            "events": re.compile(
                r"\b(irq|Pin\.irq|Timer\.irq|machine\.enable_irq|trigger|set_callback|Event\.set|schedule)\b"
            ),
            # 33. dependency_injection
            "dependency_injection": None,  # MicroPython strictly follows imperative wiring due to RAM limits.
            # 34. macros
            # MicroPython's const() acts as a compile-time macro.
            "macros": re.compile(r"\bconst\s*\([^)]+\)"),
            # 35. pointers (Pointer Arithmetic / Memory Addressing)
            # Pointer manipulation enabled by Viper/uctypes.
            "pointers": re.compile(
                r"\b(uctypes\.addressof|uctypes\.bytearray_at|ptr8|ptr16|ptr32|machine\.mem8|machine\.mem16|machine\.mem32)\b"
            ),
            # 36. memory_alloc
            "memory_alloc": re.compile(r"\b(bytearray|memoryview|alloc_emergency_exception_buf)\b"),
            # 37. inline_asm (The Bare Metal)
            "inline_asm": re.compile(r"@(?:micropython\.asm_thumb|micropython\.asm_xtensa|rp2\.asm_pio)\b"),
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # 38. telemetry (Structured Logging / Telemetry)
            "telemetry": re.compile(
                r"\b(logging|logger|ulogging|syslog)\.(?:info|error|warn|warning|debug|trace|critical|exception)\b"
            ),
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
            "debug_prints": re.compile(r"\b(print|input)\s*\("),
            # # 40. explicit_casts (Explicit Type Casting)
            "explicit_casts": re.compile(r"\b(int|str|float|list|dict|set|tuple|bool|bytes|cast)\b\s*\("),
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
            "panics_and_aborts": re.compile(r"\b(raise|quit|exit|sys\.exit|abort)\b"),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
            "thread_sleeps": re.compile(r"\b(time\.sleep|asyncio\.sleep|Thread\.join)\b"),
            # 43. bitwise_ops (Bitwise Operations)
            "bitwise_ops": re.compile(r"<<|>>|(?<!&)&(?!&)|(?<!\|)\|(?!\|)|\^|~"),
            # 44. sync_locks (Resource Management & Stability)
            "sync_locks": re.compile(r"\b(Lock|RLock|Semaphore|Event|Condition|allocate_lock)\b"),
            # 45. immutability_locks (Immutability Constraints)
            "immutability_locks": re.compile(r"\b(Final|frozenset|mappingproxy|immutable)\b"),
            # 46. cleanup (Resource Cleanup / Teardown)
            "cleanup": re.compile(r"\b(close|__exit__|del|gc\.collect|cleanup)\b\s*\("),
            # 47. encapsulation (Access Modifiers / Encapsulation)
            "encapsulation": re.compile(r"\b_[a-zA-Z_]\w*\b"),
            # 48. listeners (Event Listeners / Observers)
            # Waiting for state broadcast via hardware IRQs or event listeners.
            "listeners": re.compile(r"\.irq\(|handler=|callback="),
            # 49. test_skip (Bypassed Tests / Ignored Specs)
            "test_skip": re.compile(r"\b(pytest\.mark\.skip|unittest\.skip|mock\.|MagicMock)\b"),
            # --- PHASE 3: HYBRID DOMAIN SENSORS (Embedded Python Specifics) ---
            "serialization_parsing": re.compile(r"\b(ujson\.loads?|ujson\.dumps?|ustruct\.pack|ustruct\.unpack)\b"),
            "regex_execution": re.compile(r"\b(ure\.compile|ure\.search|ure\.match|ure\.sub)\b"),
            "time_date_logic": re.compile(r"\b(utime\.sleep_ms|utime\.ticks_ms|utime\.ticks_diff|machine\.RTC)\b"),
            "ipc_rpc_bridges": re.compile(
                r"\b(machine\.Pin|machine\.I2C|machine\.UART|network\.WLAN|usocket\.socket|busio\.I2C)\b"
            ),
        },
    },
    "cobol": {
        "_meta": {
            "target_version": "Enterprise COBOL 6.4 (IBM) & GnuCOBOL 3.2",
            "last_updated": "2026-03-10",
            "blueprint_version": "v5.1",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard COBOL source files and copybooks (.cpy) which act as legacy header files.
        "extensions": [".cbl", ".cob", ".cpy", ".cobol", ".pco", ".cut"],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: Mainframe environments do not typically use extensionless execution scripts.
        "exact_matches": [],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions and Job Control Language (.jcl) files which orchestrated legacy COBOL execution.
        "discriminators": [".cbl", ".cob", ".cpy", ".jcl"],
        # EXECUTION SIGNATURES: Interpreters found on Line 1 (primarily for modern GnuCOBOL scripting).
        "shebangs": ["cobc"],
        # UPGRADED: Maps to Family 7 (The Positional Ancients)
        # Rationale: Strictly fixed-format. The engine must monitor Column 7 for an asterisk '*'
        # or slash '/' to identify line-level Commented / Non-Executable Text.
        "lexical_family": "positional_anchored",
        "rules": {
            # --- LEXICAL DELIMITER CONTROLS ---
            # Fixed Format Logic: Column 7 is the 'Indicator Area'.
            # An asterisk '*' or forward-slash '/' in Col 7 marks the line as Literature (Commented / Non-Executable Text).
            # Regex translates to: Start of line, skip 6 chars, match indicator.
            "_line_anchor": re.compile(r"^.{6}[*/dD]"),
            # Modern COBOL (GnuCOBOL/IBM 6+) supports floating inline comments via '*>'.
            "_inline_comment": re.compile(r"\*>"),
            # EXPLICIT: COBOL does not support multi-line block comment delimiters.
            "_block_start": None,
            "_block_end": None,
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # 1. branch: Entscheidungslogik. Control flow that splits execution paths.
            "branch": re.compile(
                r"\b(IF|ELSE|EVALUATE|WHEN|PERFORM|UNTIL|VARYING|TIMES|DEPENDING\s+ON|ON\s+EXCEPTION|AT\s+END|INVALID\s+KEY|ON\s+SIZE\s+ERROR|ON\s+OVERFLOW)\b",
                re.I,
            ),
            # 2. args: Parameters / Coupling. Captures USING and RETURNING signatures in PROCEDURE division or CALLs.
            "args": re.compile(
                r"\b(?:USING|RETURNING)\s+((?:(?:BY\s+(?:REFERENCE|CONTENT|VALUE)[ \t]+)?[A-Z0-9_-]+[ \t]*,?){0,20})",
                re.I,
            ),
            # 3. linear: Sequential I/O & Network Boundaries. Structural boundaries defining straight-line execution flow.
            # EXCLUDES access modifiers (GLOBAL, EXTERNAL) to prevent Structural Complexity Inflation.
            "structural_boundaries": re.compile(
                r"\b(DIVISION|SECTION|EXIT|CONTINUE|GOBACK|ACCEPT|XML\s+PARSE|JSON\s+GENERATE|DISPLAY|STOP\s+RUN)\b",
                re.I,
            ),
            # 4. func_start: Executable Logic Anchors. Anchors logic blocks (Paragraphs and Sections).
            # =====================================================================
            # [ CONTEXT: COBOL FUNCTION/PARAGRAPH AST EXTRACTOR & REDOS SHIELD]
            # PURPOSE: Anchors executable logic blocks (Paragraphs and Sections) in COBOL.
            # VULNERABILITY: COBOL spans 60 years of formatting rules (Fixed vs Free format).
            #   Without strict column boundaries, standard verbs or data definitions
            #   (like 01 levels) resting against the margin will hallucinate False Positives.
            # THE "IRON WALL" FIX: Combines strict leading-margin allowances with
            #   comprehensive negative lookaheads to explicitly ban COBOL reserved words,
            #   data structures, and Division headers.
            # =====================================================================
            # 4. func_start: Executable Logic Anchors. Anchors logic blocks (Paragraphs and Sections).
            "func_start": re.compile(
                # =====================================================================
                # [ CONTEXT: COBOL FUNCTION/PARAGRAPH AST EXTRACTOR & REDOS SHIELD ]
                # PURPOSE: Anchors executable logic blocks (Paragraphs and Sections) in COBOL.
                #
                # [ THE GREEDY MARGIN TRAP ] (Hard-learned from Pathological Fuzzer):
                # Legacy COBOL uses a 6-character sequence area. Our regex optionally
                # eats these 6 characters: `(?:[0-9a-zA-Z \t]{6}[ \-]?)?`.
                # If a free-format developer writes a paragraph flush against the left
                # margin (e.g., `TargetFunc.`), the regex greedily eats the first 6
                # characters (`Target`) as the sequence number, and captures `Func` as
                # the paragraph name!
                # THE FIX: We injected a strict word boundary `\b` right before the
                # identifier capture group. If the margin-eater chops a word in half,
                # the `\b` fails, forcing the regex engine to backtrack, skip the
                # optional margin-eater, and correctly capture the full word `TargetFunc`.
                # =====================================================================
                # 1. THE HORIZONTAL ANCHOR & FORMAT SHIELD
                # Safely handles strict 80-column punched card formats (6-char sequence)
                # and modern free-format code. Upgraded to `[ \t\n]*` to allow vertical gaps.
                r"^(?:[0-9a-zA-Z \t]{6}[ \-]?)?[ \t\n]*"
                # 2. THE DATA DIVISION SHIELD
                # Explicitly bans data level indicators (01 through 88).
                # Prevents massive "01 POLICY." data structures from being hallucinated as paragraphs.
                r"(?!(?:01|02|03|04|05|10|15|20|66|77|88)\s+)"
                # 3. THE RESERVED VERB & SCOPE TERMINATOR SHIELD
                # Explicitly bans standard COBOL execution verbs, divisions, and scope terminators (`END-*`).
                # Prevents rogue commands like "PERFORM." from spawning false positive logic anchors.
                r"(?!(?:WORKING-STORAGE|DATA|ENVIRONMENT|IDENTIFICATION|ID|LINKAGE|FILE|DECLARATIVES|"
                r"AUTHOR|DATE-WRITTEN|DATE-COMPILED|INSTALLATION|REMARKS|SECURITY|"
                r"INPUT-OUTPUT|CONFIGURATION|DISPLAY|CALL|MOVE|COMPUTE|PERFORM|ADD|SUBTRACT|MULTIPLY|"
                r"DIVIDE|INITIALIZE|SET|IF|ELSE|GOBACK|EXIT|STOP|EVALUATE|WHEN|READ|WRITE|REWRITE|"
                r"DELETE|OPEN|CLOSE|PROGRAM-ID|CLASS-ID|END-[A-Za-z0-9_-]+)\b)"
                # 4. THE DIVISION/SECTION HEADER SHIELD
                # Bans any word followed immediately by DIVISION (e.g., "PROCEDURE DIVISION").
                # Upgraded to `[ \t\n]+` to prevent vertical ghosting.
                r"(?![A-Za-z0-9_-]+[ \t\n]+DIVISION\b)"
                # 5. THE IDENTIFIER CAPTURE (FUNCTION IDENTIFIER - GROUP 1)
                # [ THE GREEDY MARGIN SHIELD ]: The `\b` forces the engine to evaluate the whole word,
                # preventing the 6-character margin-eater from splitting flush-left identifiers.
                r"\b([A-Za-z0-9_-]+)"
                # 6. THE IGNITION & TRAILING ANCHOR (Lookahead)
                # Confirms paragraph/section by looking for an optional "SECTION", then a mandatory ".".
                # Upgraded to `[ \t\n]+` to allow vertical separation between the name and SECTION.
                # THE "SQL GHOST" FIX: `(?:\s|$)` blocks SQL qualifiers (e.g., "POLICY.CUSTOMERNUMBER").
                r"(?=(?:[ \t\n]+SECTION)?[ \t]*\.(?:[ \t\n]|$))",
                re.I | re.M,
            ),
            # 5. class_start: Object / Entity Declarations. Defines structural program and modern OO boundaries.
            "class_start": re.compile(
                r"^(?:[0-9a-zA-Z \t]{6}[ \-]?)?[ \t]*(?:PROGRAM-ID|CLASS-ID|INTERFACE-ID|FACTORY|OBJECT)\.\s+([A-Za-z0-9_-]+)(?=[ \t]*\.|\n|$)",
                re.I | re.M,
            ),
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            # 6. safety: Defensive Programming. Defensive scope terminators and declarative blocks.
            "safety": re.compile(
                r"\b(END-IF|END-PERFORM|END-EVALUATE|END-READ|END-WRITE|END-COMPUTE|END-CALL|DECLARATIVES|VALIDATE|CHECK)\b",
                re.I,
            ),
            # 7. safety_neg: Safety Bypasses. Bypassing logic or unpredictable jumps.
            "safety_bypasses": re.compile(
                r"\b(NEXT\s+SENTENCE|GO\s+TO|CORRESPONDING|ANY\s+LENGTH|OMITTED)\b",
                re.I,
            ),
            # 8. danger: High-Risk Execution. Process-stopping commands and self-modifying code (ALTER).
            "high_risk_execution": re.compile(r"\b(STOP\s+RUN|ALTER|CANCEL)\b", re.I),
            # 9. io: I/O & Network Boundaries. Disk, Database (SQL), and CICS communication.
            "io": re.compile(
                r"\b(READ|WRITE|REWRITE|OPEN|CLOSE|START|DELETE|EXEC\s+SQL|EXEC\s+CICS\s+(?:READ|WRITE|REWRITE|DELETE))\b",
                re.I,
            ),
            # 10. api: Public Surface Area. Exposed linkage points and external entries.
            "api": re.compile(r"\b(ENTRY|LINKAGE\s+SECTION|CALL|INVOKE|EXPORT)\b", re.I),
            # 11. flux: State Mutation. State mutation (The core of COBOL data manipulation).
            "state_mutation": re.compile(
                r"\b(MOVE|COMPUTE|ADD|SUBTRACT|MULTIPLY|DIVIDE|SET|INITIALIZE|REPLACE|STRING|UNSTRING)\b",
                re.I,
            ),
            # 12. dead_code (Commented Logic / Deprecated Trails) Commented out structural logic (Column 7 indicator).
            "dead_code": re.compile(
                r"^(?:.{6}\*|[ \t]*\*>)[ \t]*(?:MOVE|COMPUTE|IF|PERFORM|CALL|EXEC)\b",
                re.I | re.M,
            ),
            # 13. doc: Structured Documentation. Identification metadata and structured comments.
            "doc": re.compile(
                r"^(?:[0-9a-zA-Z \t]{6}[ \-]?)?[ \t]*(?:AUTHOR|DATE-WRITTEN|DATE-COMPILED|REMARKS|INSTALLATION)\.|\*>\s*@(?:param|return|author)",
                re.I | re.M,
            ),
            # 14. test: Testing & Assertions. Unit testing framework markers (ZUnit).
            "test": re.compile(r"\b(ZUNIT|CBLUNIT|ASSERT|TEST-CASE|READY\s+TRACE)\b", re.I),
            # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
            # 15. concurrency: Temporal Static. CICS Task and resource coordination.
            "concurrency": re.compile(r"\bEXEC\s+CICS\s+(?:ENQ|DEQ|WAIT|START|DELAY)\b", re.I),
            # 16. ui_framework: UI / View Components. Screen sections and CICS maps.
            "ui_framework": re.compile(
                r"\b(SCREEN\s+SECTION|EXEC\s+CICS\s+SEND\s+MAP|DFHMDF|DFHMDI|DFHMSD)\b",
                re.I,
            ),
            # 17. closures: Closures / Anonymous Functions. (COBOL lacks native lambdas).
            "closures": None,
            # 18. globals: Global / Shared State. Global storage and external linkages.
            "globals": re.compile(r"\b(WORKING-STORAGE\s+SECTION|COMMON|GLOBAL|EXTERNAL)\b", re.I),
            # 19. decorators: Decorators / Annotations. (COBOL uses compiler directives).
            "decorators": re.compile(
                r"^(?:[0-9a-zA-Z \t]{6}[ \-]?)?[ \t]*>>\s*(?:IF|ELSE|END-IF|DEFINE|CALL-CONVENTION)",
                re.I | re.M,
            ),
            # 20. generics: Generics / Type Parameters. Parameterized classes (Modern COBOL).
            "generics": re.compile(r"\bCLASS-ID\.\s+[A-Za-z0-9_-]+\s+USING\s+[A-Za-z0-9_-]+", re.I),
            # 21. comprehensions: Iterators / Comprehensions. (Not native to COBOL).
            "comprehensions": None,
            # 22. scientific: Numerical / Compute Libraries. Intrinsic math functions.
            "scientific": re.compile(
                r"\bFUNCTION\s+(?:ACOS|ASIN|ATAN|COS|EXP|FACTORIAL|LOG|LOG10|MOD|RANDOM|SQRT|TAN|VARIANCE)\b",
                re.I,
            ),
            # 23. heat_triggers: Metaprogramming & Reflection. Metaprogramming and memory aliasing.
            "reflection_metaprogramming": re.compile(
                r"\b(REDEFINES|RENAMES|OCCURS\s+DEPENDING\s+ON|EVALUATE\s+TRUE|EXEC\s+CICS|EXEC\s+SQL)\b",
                re.I,
            ),
            "_dependency_capture": re.compile(
                r"^(?:[0-9a-zA-Z \t]{6}[ \-]?)?[ \t]*(?:COPY|INCLUDE)[ \t\n]+['\"]?([A-Za-z0-9_-]+)['\"]?",
                re.I | re.M,
            ),
            # 25. ownership: Authorship indicators.
            "ownership": re.compile(r"^(?:[0-9a-zA-Z \t]{6}[ \-]?)?[ \t]*AUTHOR\.\s+([^\n]+)", re.I | re.M),
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            # 26. planned_debt: The Promise. Future work markers.
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt: The Fracture. Admitted fragility or hacks.
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            # 29. spec_exposure: Map vs. Territory. Audit tags.
            "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)\]", re.I),
            # 30. tabs_vs_spaces (Formatting Inconsistencies): Indentation Tracker. Tabs vs spaces conflict.
            "tabs_vs_spaces": None,  # COBOL fixed format strictly forbids Tabs.
            # 31. ssr_boundaries: View Horizon. CICS web endpoints.
            "ssr_boundaries": re.compile(r"\bEXEC\s+CICS\s+(?:WEB\s+SEND|DOCUMENT|WEB\s+READ)\b", re.I),
            # 32. events: Pub/Sub Network. Signal handlers and MQ bindings.
            "events": re.compile(
                r"\b(?:EXEC\s+CICS\s+(?:SIGNAL|HANDLE\s+CONDITION)|CALL\s+\'(?:MQPUT|MQGET)\')\b",
                re.I,
            ),
            # 33. dependency_injection: Inversion of Control.
            "dependency_injection": None,
            # 34. macros: Preprocessor Hooks. DEFINE directives.
            "macros": re.compile(
                r"^(?:[0-9a-zA-Z \t]{6}[ \-]?)?[ \t]*DEFINE\s+[A-Z0-9_-]+\.|>>DEFINE",
                re.I | re.M,
            ),
            # 35. pointers: Memory Map. Explicit pointer tracking.
            "pointers": re.compile(
                r"\b(?:POINTER|PROCEDURE-POINTER|FUNCTION-POINTER)\b|\bADDRESS\s+OF\b",
                re.I,
            ),
            # 36. memory_alloc: Manual Memory Management. Heap and CICS allocation.
            "memory_alloc": re.compile(r"\b(?:ALLOCATE|FREE|EXEC\s+CICS\s+(?:GETMAIN|FREEMAIN))\b", re.I),
            # 37. inline_asm: Bare Metal.
            "inline_asm": None,
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # 38. telemetry: Professional diagnostics.
            "telemetry": re.compile(r"\b(?:EXEC\s+CICS\s+WRITEQ\s+TD|CEE3DMP|CEEMOUT|CEEDUMP)\b", re.I),
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs): Standard output.
            "debug_prints": re.compile(r"\b(DISPLAY)\b", re.I),
            # 40. explicit_casts (Explicit Type Casting): Explicit type coercion/casting.
            "explicit_casts": re.compile(r"\b(REDEFINES)\b", re.I),
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts) Aborting execution.
            "panics_and_aborts": re.compile(r"\b(STOP\s+RUN|EXIT\s+PROGRAM|GOBACK)\b", re.I),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses) (Forced waits).
            "thread_sleeps": re.compile(r"\bEXEC\s+CICS\s+DELAY\b", re.I),
            # 43. bitwise_ops (Bitwise Operations) (Modern intrinsic bitwise).
            "bitwise_ops": re.compile(r"\bFUNCTION\s+(?:BIT-AND|BIT-OR|BIT-XOR|BIT-NOT)\b", re.I),
            # 44. sync_locks (Resource Management & Stability)
            "sync_locks": re.compile(r"\bEXEC\s+CICS\s+ENQ\b", re.I),
            # 45. immutability_locks (Immutability Constraints) Immutability.
            "immutability_locks": re.compile(r"\b(CONSTANT)\b", re.I),
            # 46. cleanup (Resource Cleanup / Teardown) Resource release.
            "cleanup": re.compile(r"\b(CLOSE|FREE|END-DECLARATIVES)\b", re.I),
            # 47. encapsulation (Encapsulation / Access Modifiers)
            "encapsulation": re.compile(r"\b(LOCAL-STORAGE\s+SECTION|PRIVATE)\b", re.I),
            # 48. listeners (Event Listeners / Observers)
            "listeners": re.compile(r"\b(?:MQGET|EXEC\s+CICS\s+RECEIVE)\b", re.I),
            # 49. test_skip (Bypassed Tests / Ignored Specs)
            "test_skip": re.compile(r"\b(IGNORE)\b", re.I),
            # --- PHASE 3: HYBRID DOMAIN SENSORS (COBOL Specifics) ---
            "serialization_parsing": re.compile(
                r"(?i)\b(UNSTRING|STRING|JSON\s+PARSE|JSON\s+GENERATE|XML\s+PARSE|XML\s+GENERATE)\b"
            ),
            "regex_execution": re.compile(
                r"(?i)\b(INSPECT|TALLYING|REPLACING)\b"
            ),  # COBOL's hardware-level string manipulation engine
            "time_date_logic": re.compile(
                r"(?i)\b(ACCEPT\s+.*\s+FROM\s+(?:DATE|TIME|DAY)|CURRENT-DATE|WHEN-COMPILED)\b"
            ),
            "ipc_rpc_bridges": re.compile(r"(?i)\b(CALL\s+|EXEC\s+CICS\s+(?:LINK|XCTL|START|RETURN)|EXEC\s+SQL)\b"),
        },
    },
    "zig": {
        "_meta": {
            "target_version": "Zig 0.15.2 (Modern Comptime, Explicit Allocators, Error Sets)",
            "last_updated": "2026-02-18",
            "blueprint_version": "v5.0",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard sources and Zig Object Notation (ZON) files which are structurally Zig AST.
        "extensions": [".zig", ".zon"],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: The pure-code build scripts that act as the architectural anchors of a Zig project.
        "exact_matches": ["build.zig", "build.zig.zon"],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: Zig's build system files ensure that ambiguous contexts are locked in perfectly.
        "discriminators": [".zig", "build.zig", "build.zig.zon"],
        # EXECUTION SIGNATURES: Zig is compiled, but `zig run` can be invoked via shebang in scripting scenarios.
        "shebangs": ["zig"],
        # UPGRADED: Maps to Family 8 (Singular/Unique)
        # Rationale: Zig intentionally omits multi-line block comments to keep parsing simple, exclusively using '//'.
        "lexical_family": "line_exclusive",
        "rules": {
            # --- LEXICAL DELIMITER CONTROLS ---
            "_line_anchor": re.compile(r"//"),
            "_inline_comment": re.compile(r"//"),
            "_block_start": None,
            "_block_end": None,
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # 1. branch: decisions that split flow. Includes unique 'orelse' and 'catch' patterns.
            "branch": re.compile(r"\b(if|else|switch|while|for|try|catch|orelse|break|continue|return)\b|&&|\|\|"),
            # 2. args: Parameters / Coupling. Captures parameters in function signatures.
            "args": re.compile(r"\bfn\s*(?:[a-zA-Z_]\w*\s*)?\([^)]*\)"),
            # 3. linear: Sequential I/O & Network Boundaries. Structural boundaries. EXCLUDES access modifiers and const (freeze_hits).
            "structural_boundaries": re.compile(
                r"\b(var|return|defer|errdefer|unreachable|resume|suspend|await|nosuspend|usingnamespace)\b"
            ),
            # 4. func_start: Executable Logic Anchors. Anchors logic blocks (fn). EXCLUDES struct/enum/union headers.
            "func_start": re.compile(
                r"^[ \t]*(?:(?:pub|export|extern|inline|noinline|callconv\([^)]*\))[ \t]+){0,5}fn\s+([a-zA-Z_]\w*)(?=\s*\()",
                re.M,
            ),
            # 5. class_start: Object / Entity Declarations. Defines structural entities (struct, enum, union, error, opaque).
            "class_start": re.compile(
                r"^[ \t]*(?:pub[ \t]+)?const[ \t]+([a-zA-Z_]\w*)[ \t]*=[ \t]*(?:packed[ \t]+|extern[ \t]+)?(?:struct|enum|union|error|opaque)(?=[ \t]*[{(])",
                re.M,
            ),
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            # 6. safety: Defensive Programming. Error handling, payload capturing (|val|), and debug assertions.
            "safety": re.compile(r"\b(try|catch|orelse|errdefer|std\.debug\.assert)\b|\|[ \t]*[a-zA-Z_]\w*[ \t]*\|"),
            # 7. safety_neg: Safety Bypasses. Bypassing safety (undefined, unreachable, raw ptr casting).
            "safety_bypasses": re.compile(
                r"\b(undefined|unreachable|@ptrCast|@intCast|@alignCast|@bitCast|@truncate|@enumFromInt)\b"
            ),
            # 8. danger: High-Risk Execution. Forceful panics and process terminations.
            "high_risk_execution": re.compile(r"\b(@panic|panic|std\.process\.exit)\b"),
            # 9. io: I/O & Network Boundaries. Standard library IO, Network, and Filesystem interactions.
            "io": re.compile(r"\b(std\.fs|std\.net|std\.io(?!\.getStdOut)|std\.ChildProcess|std\.posix|std\.os)\b"),
            # 10. api: Public Surface Area. Exposed boundaries via 'pub' and 'export' (C ABI).
            "api": re.compile(r"\b(pub|export)\b"),
            # 11. flux: State Mutation. State mutation (var) and pointer dereference assignments (.* =).
            "state_mutation": re.compile(r"\bvar\b|\.\*[ \t]*=[^=]"),
            # 12. dead_code (Commented Logic / Deprecated Trails) Commented out structural code.
            "dead_code": re.compile(r"//[ \t]*(?:fn|const|var|pub|if|for|while|try|catch)\b"),
            # 13. doc: Structured Documentation. Structured documentation (/// and //!).
            "doc": re.compile(r"///|//!"),
            # 14. test: Testing & Assertions. Native test framework blocks.
            "test": re.compile(
                r'\b(test\s+"[^"]*"|test\s+[a-zA-Z_]\w*|std\.testing\.expect|std\.testing\.expectEqual)\b'
            ),
            # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
            # 15. concurrency: Temporal Static. Suspend/resume and thread primitives.
            "concurrency": re.compile(
                r"\b(std\.Thread|std\.Thread\.Mutex|std\.Thread\.RwLock|std\.atomic|@atomicLoad|@atomicStore|@atomicRmw|suspend|resume|await)\b"
            ),
            # 16. ui_framework: UI / View Components. (Zig lacks native UI; targets common bindings like Mach/zgui).
            "ui_framework": re.compile(r"\b(mach\.|zgui\.|zopengl\.|capy\.|vaxis\.|raylib\.)\b"),
            # 17. closures: Closures / Anonymous Functions. (Zig lacks traditional anonymous closures).
            "closures": None,
            # 18. globals: Global / Shared State. Top-level file-scoped state.
            "globals": re.compile(
                r"^[ \t]*(?:pub[ \t]+)?(?:threadlocal[ \t]+)?(?:comptime[ \t]+)?(?:const|var)\s+[a-zA-Z_]\w*\s*(?::[^=]+)?=",
                re.M,
            ),
            # 19. decorators: Decorators / Annotations. (Zig uses @builtins instead).
            "decorators": None,
            # 20. generics: Generics / Type Parameters. Comptime parameters and 'anytype' duck typing.
            "generics": re.compile(r"\b(anytype|type)\b|\bcomptime\s+[a-zA-Z_]\w*\s*:\s*type\b"),
            # 21. comprehensions: Iterators / Comprehensions. (Not native to Zig).
            "comprehensions": None,
            # 22. scientific: Numerical / Compute Libraries. Math intrinsics and SIMD @Vector support.
            "scientific": re.compile(r"\b(std\.math|@Vector|f16|f32|f64|f80|f128|@sqrt|@sin|@cos|@splat|@reduce)\b"),
            # 23. heat_triggers: Metaprogramming & Reflection. Comptime metaprogramming and reflection.
            "reflection_metaprogramming": re.compile(
                r"\b(comptime[ \t]*\{|inline\s+for|inline\s+while|@Type|@typeInfo|@compileLog|@hasDecl|@hasField)\b"
            ),
            # 24. import: Dependency Inclusions. Module and C-header bridges.
            "import": re.compile(r"\b(@import|@cImport|@cInclude)\b"),
            "_dependency_capture": re.compile(
                r"^[ \t]*(?:const[ \t]+[a-zA-Z_]\w*[ \t]*=[ \t]*)?(?:@import|@cInclude)[ \t\n]*\([ \t\n]*['\"]([^'\"]+)['\"]",
                re.M,
            ),
            # 25. ownership: Authorship indicators in comments.
            "ownership": re.compile(r"//\s*(?:Author|Created by|Maintainer|Copyright):\s+([^\n]+)", re.I),
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            # 26. planned_debt: The Promise. Future work markers.
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt: The Fracture. Admitted fragility or hacks.
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            # 29. spec_exposure: Map vs. Territory. Audit tags.
            "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)\]", re.I),
            # 30. tabs_vs_spaces (Formatting Inconsistencies): Indentation Tracker. Tabs vs 4-space standardization.
            "tabs_vs_spaces": None,
            # 31. ssr_boundaries: View Horizon. Zap/httpz response handlers.
            "ssr_boundaries": re.compile(r"\b(zap\.Endpoint|zap\.Request|httpz\.Request|std\.http\.Server\.Request)\b"),
            # 32. events: Pub/Sub Network. OS-level event loops.
            "events": re.compile(r"\b(std\.posix\.epoll_wait|std\.posix\.kevent|xev\.Loop)\b"),
            # 33. dependency_injection: Inversion of Control.
            "dependency_injection": None,
            # 34. macros: Preprocessor Hooks. (Zig lacks macros).
            "macros": None,
            # 35. pointers: Memory Map. Explicit pointer tracking.
            "pointers": re.compile(
                r"(?<=[=\s,(])\*(?:const\s+|volatile\s+|allowzero[ \t]+)?[a-zA-Z_]\w*|\[\*c?\][a-zA-Z_]\w*|\.\*"
            ),
            # 36. memory_alloc: Manual Memory Management. Allocators bypassing the GC.
            "memory_alloc": re.compile(
                r"\b(std\.mem\.Allocator|allocator\.alloc|allocator\.free|allocator\.create|ArenaAllocator|c_allocator|page_allocator)\b"
            ),
            # 37. inline_asm: Bare Metal.
            "inline_asm": re.compile(r"\basm\b(?:\s+volatile)?\s*\([^)]+\)"),
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # 38. telemetry: Professional diagnostics.
            "telemetry": re.compile(r"\b(?:std\.log\.(?:info|err|warn|debug)|std\.log\.scoped)\b"),
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs): Standard output.
            "debug_prints": re.compile(r"\b(std\.debug\.print)\b"),
            # 40. explicit_casts (Explicit Type Casting): "Trust Me" Tax. Explicit casting.
            "explicit_casts": re.compile(r"\b(@ptrCast|@intCast|@alignCast|@bitCast|@as)\b"),
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts) Aborting context.
            "panics_and_aborts": re.compile(r"\b(@panic|unreachable|return)\b"),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses) (Forced waits/sleep).
            "thread_sleeps": re.compile(r"\b(std\.time\.sleep)\b"),
            # 43. bitwise_ops (Bitwise Operations)
            "bitwise_ops": re.compile(r"(?<!&)&(?!&)|(?<!\|)\|(?!\|)|<<|>>|\^|~"),
            # 44. sync_locks (Resource Management & Stability) Coordinated threading.
            "sync_locks": re.compile(r"\b(Mutex|RwLock|Semaphore|lock|unlock)\b"),
            # 45. immutability_locks (Immutability Constraints) Immutability.
            "immutability_locks": re.compile(r"\bconst\b"),
            # 46. cleanup (Resource Cleanup / Teardown) Resource release.
            "cleanup": re.compile(r"\b(deinit|free|destroy|allocator\.free)\b"),
            # 47. encapsulation Scope hiding (Lack of pub).
            "encapsulation": re.compile(r"^[ \t]*(?!(?:pub|export|extern)\b)(?:const|var|fn)\s+", re.M),
            # 48. listeners (Event Listeners / Observers)
            "listeners": None,
            # 49. test_skip (Bypassed Tests / Ignored Specs)
            "test_skip": re.compile(r"\b(std\.testing\.expect|assume|expectError)\b"),
            # --- PHASE 3: HYBRID DOMAIN SENSORS (Zig Specifics) ---
            "serialization_parsing": re.compile(
                r"\b(std\.json\.parseFrom(?:Slice|TokenSource)|std\.json\.stringify)\b"
            ),
            "regex_execution": re.compile(
                r"\b(std\.mem\.(?:indexOf|tokenize(?:Any)?|split(?:Sequence|Any)?|replace))\b"
            ),  # Zig has no native regex!
            "time_date_logic": re.compile(r"\b(std\.time\.(?:nanoTimestamp|milliTimestamp|Timer|sleep))\b"),
            "ipc_rpc_bridges": re.compile(
                r"\b(std\.process\.Child|std\.net\.tcpConnectToHost|std\.Thread\.spawn|std\.posix|std\.os\.execve)\b"
            ),
        },
    },
    "apex": {
        "_meta": {
            "target_version": "Salesforce Apex 24.2 (API v62.0+)",
            "last_updated": "2026-02-18",
            "blueprint_version": "v5.0",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard Salesforce classes and database triggers.
        "extensions": [".cls", ".trigger"],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: Apex code lives and executes on the Salesforce platform; no extensionless configurations exist.
        "exact_matches": [],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: .cls is highly contested. Salesforce metadata XMLs and SFDX configs act as absolute gravity anchors.
        "discriminators": [
            ".cls-meta.xml",
            ".trigger-meta.xml",
            "sfdx-project.json",
            "package.xml",
        ],
        # EXECUTION SIGNATURES: Executed exclusively on the Salesforce platform; no shebangs exist.
        "shebangs": [],
        # Rationale: Uses standard '//' for lines and '/*' '*/' for block-level Commented / Non-Executable Text.
        "lexical_family": "standard_block",
        "rules": {
            # --- LEXICAL DELIMITER CONTROLS ---
            "_line_anchor": re.compile(r"//"),
            "_inline_comment": re.compile(r"//"),
            "_block_start": re.compile(r"/\*"),
            "_block_end": re.compile(r"\*/"),
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # 1. branch: decisions that split flow. Includes switch on/when and DML try-catch.
            "branch": re.compile(
                r"\b(if|else|switch\s+on|when|for|while|do|try|catch|finally|break|continue|return)\b|&&|\|\||\?|\?\?",
                re.I,
            ),
            # 2. args: Parameters / Coupling. Captures method parameters and trigger event signatures.
            "args": re.compile(
                r"\b[a-z_]\w*(?:<[^>]*>)?\s+[a-z_]\w*\s*\([^)]*\)|\btrigger\s+[a-z_]\w*\s+on\s+[a-z_]\w*\s*\([^)]*\)",
                re.I,
            ),
            # 3. linear: Sequential I/O & Network Boundaries. Structural boundaries. EXCLUDES access modifiers and sharing keywords.
            "structural_boundaries": re.compile(
                r"\b(class|interface|trigger|enum|final|transient|implements|extends|virtual|abstract|return)\b",
                re.I,
            ),
            # 4. func_start (Executable Logic Anchors)
            # ReDoS clamped to {0,5}. Strict capture groups and lookaheads for both Methods and Triggers.
            "func_start": re.compile(
                r"^[ \t]*(?:@[\w.]+(?:\([^)]*\))?[ \t]+){0,5}"
                r"(?:(?:public|private|global|protected|static|override|virtual|abstract|testMethod)[ \t]+){0,5}"
                r"(?:[\w<>\[\]?]+[ \t]+)?(?!(?:class|interface|enum|if|for|while|switch|catch)\b)([a-zA-Z_]\w*)(?=\s*\()|"
                r"^[ \t]*trigger\s+([a-zA-Z_]\w*)(?=\s+on\b)",
                re.M,
            ),
            # 5. class_start (Object / Entity Declarations)
            # ReDoS clamped. Strict capture group and positive lookahead applied.
            "class_start": re.compile(
                r"^[ \t]*(?:@[\w.]+(?:\([^)]*\))?[ \t]+){0,5}"
                r"(?:(?:public|private|global|virtual|abstract|with\s+sharing|without\s+sharing|inherited\s+sharing)[ \t]+){0,5}"
                r"(?:class|interface|enum)\s+([a-zA-Z_]\w*)(?=\s+implements|\s+extends|\s*\{|\n|$)",
                re.M,
            ),
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            # 6. safety: Defensive Programming. Sharing rules, FLS checks, and null-safe navigation.
            "safety": re.compile(
                r"\b(with\s+sharing|inherited\s+sharing|isAccessible|isCreateable|isUpdateable|isDeletable|StripInaccessible|try|catch|finally|LIMIT\s+\d+|Security\.stripInaccessible)\b|\?\.",
                re.I,
            ),
            # 7. safety_neg: Safety Bypasses. Actively bypassing safety (without sharing, raw casting).
            "safety_bypasses": re.compile(
                r"\b(without\s+sharing|Database\.query(?!\s*\(.*?WITH\s+SECURITY_ENFORCED)|@SuppressWarnings)\b|\(\s*[A-Z_]\w*\s*\)\s*[a-z_]\w*",
                re.I,
            ),
            # 8. danger: High-Risk Execution. Dynamic SOQL, mass deletion, and hardcoded IDs.
            "high_risk_execution": re.compile(
                r"\b(Database\.query|delete|undelete|emptyRecycleBin|purgeOldAsyncJobs)\b|\'[a-z0-9]{15,18}\'",
                re.I,
            ),
            # 9. io: I/O & Network Boundaries. SOQL/SOSL queries, HTTP callouts, and batch boundaries.
            "io": re.compile(
                r"\[\s*(?:SELECT|FIND)\b[^\]]*\]|\b(Http|HttpRequest|HttpResponse|Database\.executeBatch|HTLoad|HTGet|ENQUIRE)\b",
                re.I,
            ),
            # 10. api: Public Surface Area. Exposed global interfaces, REST resources, and UI hooks.
            "api": re.compile(
                r"\b(global|webservice)\b|@(?:RestResource|HttpGet|HttpPost|HttpPut|HttpDelete|HttpPatch|AuraEnabled|InvocableMethod|RemoteAction)\b",
                re.I,
            ),
            # 11. flux: State Mutation. State mutation (DML operations and standard assignments).
            "state_mutation": re.compile(
                r"\b(insert|update|upsert|delete|merge)\b|^[ \t]*(?:this\.)?[a-z_]\w*\s*[-+*/%]?=|\.(?:add|addAll|remove|put|clear|set)\s*\(",
                re.I | re.M,
            ),
            # 12. dead_code (Commented Logic / Deprecated Trails) Commented out structural code or queries.
            "dead_code": re.compile(
                r"//[ \t]*(?:class|trigger|public|private|if|for|while|System\.debug|\[\s*SELECT|insert|update)\b|/\*[ \t]*(?:class|trigger|\[\s*SELECT)",
                re.I | re.M,
            ),
            # 13. doc: Structured Documentation. ApexDoc annotations and metadata blocks.
            "doc": re.compile(r"/\*\*|@description|@param|@return|@author|@date|@example", re.I),
            # 14. test: Testing & Assertions. Salesforce test execution and assertion markers.
            "test": re.compile(
                r"@isTest|@TestSetup|@TestVisible|\b(?:Test\.startTest|Test\.stopTest|System\.assert|Assert\.(?:isTrue|isNotNull|areEqual)|Test\.setMock)\b",
                re.I,
            ),
            # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
            # 15. concurrency: Temporal Static. Asynchronous Apex (Future, Queueable, Batch).
            "concurrency": re.compile(
                r"@future|\b(Queueable|Schedulable|Batchable|System\.enqueueJob|Database\.executeBatch|System\.schedule)\b",
                re.I,
            ),
            # 16. ui_framework: UI / View Components. Visualforce and LWC bridge components.
            "ui_framework": re.compile(
                r"\b(ApexPages|PageReference|StandardController|Dom\.Document|SGML|HyperText|WorldWideWeb|BrowserView)\b",
                re.I,
            ),
            # 17. closures: Closures / Anonymous Functions. (Apex lacks true anonymous closures).
            "closures": None,
            # 18. globals: Global / Shared State. Custom Settings, Organization data, and User context.
            "globals": re.compile(
                r"\b(UserInfo|System\.Label|Organization|Cache\.Org|Cache\.Session)\b|\w+__c\.getInstance\b|\w+__mdt\.getInstance\b",
                re.I,
            ),
            # 19. decorators: Decorators / Annotations. Execution context annotations.
            "decorators": re.compile(r"@[a-z_]\w*(?:\([^)]*\))?", re.I),
            # 20. generics: Generics / Type Parameters. Parameterized collections (List, Map, Set).
            "generics": re.compile(r"\b(?:List|Set|Map|Iterable|Iterator)\s*<\s*[a-z_][^>]*>", re.I),
            # 21. comprehensions: Iterators / Comprehensions. Inline SOQL for-loops act as mappers.
            "comprehensions": re.compile(r"\bfor\s*\([^)]+:\s*\[\s*SELECT[^\]]+\]\s*\)", re.I),
            # 22. scientific: Numerical / Compute Libraries. Standard numerical and currency math.
            "scientific": re.compile(
                r"\b(Math\.(?:abs|sin|cos|tan|exp|log|pow|sqrt)|Decimal|setScale|setRoundingMode)\b",
                re.I,
            ),
            # 23. heat_triggers: Metaprogramming & Reflection. Dynamic SOQL, Reflection, and Describe calls.
            "reflection_metaprogramming": re.compile(
                r"\b(Database\.query|Type\.forName|Schema\.getGlobalDescribe|Schema\.describeSObjects|SObject\.put|SObject\.get|JSON\.deserializeUntyped)\b",
                re.I,
            ),
            # 24. import: Dependency Inclusions.
            # Apex lacks a native import keyword. Cross-package dependencies are established via
            # reflection (Type.forName) or explicitly namespaced static invocations.
            "import": re.compile(
                r"\bType\.forName\b|(?!(?:System|Database|Schema|Auth|Cache|Chatter|EventBus|Limits|Messaging|RestContext|Test)\b)\b[a-zA-Z_]\w*\.[A-Z]\w*\b",
                re.I,
            ),
            "_dependency_capture": re.compile(
                r"\bType\.forName\s*\(\s*['\"]([^'\"]+)['\"](?:[ \t\n]*,[ \t\n]*['\"]([^'\"]+)['\"])?\s*\)",
                re.I,
            ),
            # 25. ownership: Authorship indicators.
            "ownership": re.compile(
                r"(?:@author|Author|Created by|Maintainer|Copyright|Tim Berners-Lee):\s+([^\n]+)",
                re.I | re.M,
            ),
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            # 26. planned_debt: The Promise. Future work markers.
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt: The Fracture. Admitted fragility or hacks.
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            # 29. spec_exposure: Map vs. Territory. Audit tags and architecture specs.
            "spec_exposure": re.compile(
                r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)\]|\b(?:WorldWideWeb|RFC|W3C|CERN|TBL|ENQUIRE)\b",
                re.I,
            ),
            # 30. tabs_vs_spaces (Formatting Inconsistencies): Indentation Tracker. Tabs vs 4-space standardization.
            "tabs_vs_spaces": None,
            # 31. ssr_boundaries: View Horizon. REST and Visualforce response handlers.
            "ssr_boundaries": re.compile(
                r"\b(RestContext\.request|RestContext\.response|RestRequest|RestResponse|renderAs)\b",
                re.I,
            ),
            # 32. events: Pub/Sub Network. Platform Events and Trigger context.
            "events": re.compile(
                r"\b(EventBus\.publish|PlatformEvent)\b|trigger\s+[a-zA-Z_]\w+\s+on\s+[a-zA-Z_]\w+Event__e",
                re.I,
            ),
            # 33. dependency_injection: Inversion of Control. Mocking and injection frameworks.
            "dependency_injection": re.compile(
                r"\b(fflib_ApexMocks|fflib_SObjectUnitOfWork|Injector|di_Injector|Application\.Service|Type\.newInstance)\b",
                re.I,
            ),
            # 34. macros: Preprocessor Hooks. (Apex lacks a preprocessor).
            "macros": None,
            # 35. pointers: Memory Map. (Apex is fully managed with no pointers).
            "pointers": None,
            # 36. memory_alloc: Manual Memory Management. Heap observations.
            "memory_alloc": re.compile(
                r"\b(Limits\.getHeapSize|Limits\.getLimitHeapSize|new\s+[a-z_]\w*)\b",
                re.I,
            ),
            # 37. inline_asm: Bare Metal.
            "inline_asm": None,
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # 38. telemetry: Professional diagnostics (Structured logs).
            "telemetry": re.compile(
                r"\b(Logger|Log|AppLog|NebulaLogger)\.(?:info|error|warn|debug|trace)\b|\binsert\s+new\s+Log__c\b",
                re.I,
            ),
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs): Standard output.
            "debug_prints": re.compile(r"\b(System\.debug)\b", re.I),
            # 40. explicit_casts (Explicit Type Casting): "Trust Me" Tax. Explicit type coercion.
            "explicit_casts": re.compile(
                r"\(\s*(?:[A-Z]\w*|int|Id|String|Decimal|Boolean|Double|Long|Blob|Date|Datetime|Time)\s*\)\s*[a-zA-Z_$]"
            ),
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts) Aborting execution or rollback.
            "panics_and_aborts": re.compile(r"\b(throw|Database\.rollback|purgeOldAsyncJobs)\b", re.I),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses) (Apex has no native sleep/delay).
            "thread_sleeps": None,
            # 43. bitwise_ops (Bitwise Operations)
            "bitwise_ops": re.compile(r"(?<!&)&(?!&)|(?<!\|)\|(?!\|)|<<|>>|\^|~"),
            # 44. sync_locks (Resource Management & Stability) Row-level SOQL locking.
            "sync_locks": re.compile(r"\bFOR\s+UPDATE\b", re.I),
            # 45. immutability_locks (Immutability Constraints) Immutability (constants).
            "immutability_locks": re.compile(r"\b(static\s+final|final|const)\b", re.I),
            # 46. cleanup (Resource Cleanup / Teardown) Recycle bin management.
            "cleanup": re.compile(r"\b(emptyRecycleBin|Database\.rollback|clear)\s*\(", re.I),
            # 47. encapsulation (Encapsulation / Access Modifiers)
            "encapsulation": re.compile(r"\b(private|protected)\b", re.I),
            # 48. listeners (Event Listeners / Observers) Triggers listening for events.
            "listeners": re.compile(r"^[ \t]*trigger\s+[a-z_]\w*\s+on\b", re.I | re.M),
            # 49. test_skip (Bypassed Tests / Ignored Specs)
            "test_skip": re.compile(r"\b(StubProvider|Test\.setMock|@SuppressWarnings)\b", re.I),
        },
    },
    "dart": {
        "_meta": {
            "target_version": "Dart 3.11 (Records, Patterns, Class Modifiers, Macros, FFI)",
            "last_updated": "2026-02-18",
            "blueprint_version": "v5.0",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard Dart sources.
        "extensions": [".dart"],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: Dart rarely uses extensionless configurations.
        "exact_matches": [],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions, pub package manifests, and analyzer configurations to anchor Flutter/Dart projects.
        "discriminators": [
            ".dart",
            "pubspec.yaml",
            "pubspec.lock",
            "analysis_options.yaml",
            ".metadata",
        ],
        # EXECUTION SIGNATURES: Interpreters found on Line 1 for standalone Dart scripting.
        "shebangs": ["dart"],
        # UPGRADED: Maps to Family 2 (Nested C)
        # Rationale: (CORRECTION) Like Swift and Rust, Dart officially supports nested multi-line
        # comments (/* /* */ */). Standard C parsing would prematurely terminate here causing geometry failure.
        "lexical_family": "standard_block",
        "rules": {
            "_block_start": re.compile(r"/\*"),
            "_block_end": re.compile(r"\*/"),
            "_line_anchor": re.compile(r"//"),
            "_inline_comment": re.compile(r"//"),
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # 1. branch: decisions that split flow. Includes modern pattern guards (when) and null-coalescing.
            "branch": re.compile(
                r"\b(if|else|switch|case|default|for|while|do|try|catch|finally|break|continue|when)\b|&&|\|\||\?|\?\?",
                re.I,
            ),
            # 2. args (Parameters / Coupling)
            # Captures parameters in function, method, and lambda signatures.
            "args": re.compile(
                # =====================================================================
                # [ THE GHOST ARGS & STRICT NESTING SHIELD (DART) ]
                # Dart functions can take inline typed callbacks like `void Function(int)`.
                # FIX 1 (Catastrophic Backtracking): Used strictly linear nesting `[^()]*(?:\([^()]*\)[^()]*)*`.
                # FIX 2 (Ghost Args): `if (a > b) {` matched the anonymous block lambda branch.
                # Because block lambdas `(a) {` are structurally identical to `while (a) {`,
                # we restrict the lambda branch EXCLUSIVELY to arrow functions `=>` to
                # mathematically prevent Ghost Args and ReDoS spirals.
                # =====================================================================
                r"(?!(?:if|for|while|switch|catch)\b)\b[A-Za-z_$][\w$]*(?:[ \t\n]*<[^>]*>)?[ \t\n]*\([^()]*(?:\([^()]*\)[^()]*)*\)(?=[ \t\n]*(?:\{|=>|:|async|sync))|\([^()]*(?:\([^()]*\)[^()]*)*\)[ \t\n]*=>",
                re.I | re.M,
            ),
            # 3. linear: Sequential I/O & Network Boundaries. Structural boundaries. EXCLUDES access modifiers and const/final.
            "structural_boundaries": re.compile(
                r"\b(var|late|return|yield|await|class|mixin|extension|enum|typedef|import|export|part|library|base|sealed|interface|macro)\b|=>",
                re.I,
            ),
            # 4. func_start (Executable Logic Anchors)
            # ReDoS clamped to {0,5}. Strict capture group and positive lookahead applied.
            "func_start": re.compile(
                r"^[ \t]*(?:@[\w.]+(?:\([^)]*\))?[ \t]+){0,5}"
                r"(?:(?:static|external|abstract|covariant|late)[ \t]+){0,5}"
                r"(?:[\w<>\[\]?]+[ \t]+)?(?!(?:class|mixin|enum|extension|typedef|if|for|while|switch|catch)\b)"
                r"(?:get\s+|set\s+|factory\s+|operator\s+\S+\s*)?([a-zA-Z_]\w*)(?=\s*\()",
                re.M,
            ),
            # 5. class_start (Object / Entity Declarations)
            # =====================================================================
            # [ THE VERTICAL MODIFIER & INHERITANCE SHIELD (DART) ]
            # Dart allows modifiers to stack (e.g., `abstract base mixin class`)
            # and extends/implements declarations that broke the rigid trailing lookahead.
            # FIX: Grouped the class modifiers into a bounded set `(?:(?:abstract|sealed|base|interface|final|macro)[ \t\n]+){0,5}`.
            # Upgraded all internal spaces to `[ \t\n]+` to jump vertical gaps, and
            # swapped the rigid lookahead for an optional non-capturing inheritance
            # group `(?:[ \t\n]+(?:extends|implements|with).*?)?` to handle inheritance paths.
            # =====================================================================
            "class_start": re.compile(
                r"^[ \t]*(?:@[\w.]+(?:\([^)]*\))?[ \t\n]*){0,5}"
                r"(?:(?:abstract|sealed|base|interface|final|macro)[ \t\n]+){0,5}"
                r"(?:class|mixin|enum|extension[ \t\n]+type|extension)[ \t\n]+([A-Z_]\w*)(?:[ \t\n]+(?:extends|implements|with)[ \t\n]+[A-Za-z_$][\w_<>, \t\n]*)?",
                re.M,
            ),
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            # 6. safety: Defensive Programming. Null safety boundaries, type assertions, and required parameters.
            "safety": re.compile(
                r"\b(try|catch|finally|on\s+[A-Z]\w*|assert|required|late|is|!is|SafeArea|@immutable|@mustCallSuper)\b|\?\?|\?.",
                re.I,
            ),
            # 7. safety_neg: Safety Bypasses. Actively bypassing sound null safety or static analysis.
            "safety_bypasses": re.compile(r"!\s*[;,\n)\.\]]|\bdynamic\b|//\s*ignore(?:_for_file)?:\s*\w+"),
            # 8. danger: High-Risk Execution. Process killers and catastrophic exit commands.
            "high_risk_execution": re.compile(r"\b(exit|exitCode|Process\.killPid)\b", re.I),
            # 9. io: I/O & Network Boundaries. Disk, Network, WebSockets, and Uri parsing (Includes legacy CERN triggers).
            "io": re.compile(
                r"\b(File|Directory|HttpClient|HttpServer|ServerSocket|WebSocket|Uri\.parse|HtmlDocument|HttpRequest|HttpResponse|HTRequest|Nexus|ENQUIRE)\b",
                re.I,
            ),
            # 10. api: Public Surface Area. Exposed visibility (Lack of _ prefix) and routing decorators.
            "api": re.compile(
                r"\b(export|part\s+of)\b|@(Route|Get|Post|Mapping|visibleForTesting|pragma)\b|^[ \t]*(?:class|mixin|enum|extension|typedef)\s+(?![_])[A-Za-z]\w*",
                re.I | re.M,
            ),
            # 11. flux: State Mutation. State mutation (setState and reactive collection mutators).
            "state_mutation": re.compile(
                r"\b(setState|notifyListeners|markNeedsBuild|StreamController\.add)\b|[^!=<>\+\-\*\/%&\|\s]=\s*[^=]|(?:\+\+|--)|\.(?:add|addAll|remove|insert|clear|update)\s*\(",
                re.I,
            ),
            # 12. dead_code (Commented Logic / Deprecated Trails) Commented out structural code or dead widgets.
            "dead_code": re.compile(
                r"//[ \t]*(?:class|mixin|void|if|for|while|print|Widget|return)\b|/\*[ \t]*(?:class|mixin|void|Widget|if|for)"
            ),
            # 13. doc: Structured Documentation. dartdoc annotations and structured comments.
            "doc": re.compile(r"///|/\*\*|@param|@return"),
            # 14. test: Testing & Assertions. Flutter test frameworks and standard expect/verify markers.
            "test": re.compile(
                r"\b(?:test|testWidgets|group|setUp|tearDown|pumpWidget|pumpAndSettle|find\.(?:byType|text|byKey))\b|\b(?:expect|verify|when)\s*\("
            ),
            # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
            # 15. concurrency: Temporal Static. Event Loop primitives (Future, Stream, Isolate).
            "concurrency": re.compile(
                r"\b(async|async\*|sync\*|await|Future|Stream|Isolate|ReceivePort|SendPort|Completer|Timer|StreamSubscription)\b",
                re.I,
            ),
            # 16. ui_framework: UI / View Components. Flutter Component trees and DOM nodes (Includes TBL triggers).
            "ui_framework": re.compile(
                r"\b(Widget|BuildContext|StatefulWidget|Scaffold|Container|Text|HtmlElementView|RichText|Hyperlink|SGML|HyperText|Browser)\b",
                re.I,
            ),
            # 17. closures: Closures / Anonymous Functions. Fat-arrows and anonymous function blocks.
            "closures": re.compile(r"=>|\(\s*[^)]*\)\s*(?:async\*?|sync\*?)?[ \t]*\{"),
            # 18. globals: Global / Shared State. Static class fields and environmental bindings.
            "globals": re.compile(
                r"\b(static\s+final|static\s+const|Platform\.environment|window\.|Zone\.current)\b|^[ \t]*(?:final|const|var)\s+[A-Za-z_$][\w$]*[ \t]*=",
                re.I | re.M,
            ),
            # 19. decorators: Decorators / Annotations. Annotations applied to methods/classes.
            "decorators": re.compile(r"@[A-Za-z_$][\w$]*(?:\([^)]*\))?"),
            # 20. generics: Generics / Type Parameters. Parameterized collections and generic classes.
            "generics": re.compile(r"<\s*[A-Z][^>]*>"),
            # 21. comprehensions: Iterators / Comprehensions. Collection for/if and functional pipelines.
            "comprehensions": re.compile(
                r"\[\s*(?:for|if)\s*\([^)]*\)|\{\s*(?:for|if)\s*\([^)]*\)|\.(?:map|where|reduce|fold|expand|every|any)\s*\("
            ),
            # 22. scientific: Numerical / Compute Libraries. math.pi, typed binary arrays, and Matrix4 vectors.
            "scientific": re.compile(
                r"\b(math\.sin|math\.cos|math\.sqrt|math\.pi|dart:math|Float64List|Float32List|Int32List|Uint8List|Vector2|Vector3|Matrix4)\b",
                re.I,
            ),
            # 23. heat_triggers: Metaprogramming & Reflection. Reflection, Native Bridges, and code generation markers.
            "reflection_metaprogramming": re.compile(
                r'\b(MethodChannel|EventChannel|dart:mirrors|reflect|reflectClass|noSuchMethod|dart:js_interop)\b|part\s+[\'"][^\'"]+\.(?:g|freezed)\.dart[\'"]',
                re.I,
            ),
            # 24. import: Dependency Inclusions. Dependency resolution and library partitions.
            "import": re.compile(r'^[ \t]*(?:import|export|part|part\s+of)\b\s*[\'"][^\'"]+[\'"]', re.M),
            "_dependency_capture": re.compile(
                r"^[ \t]*(?:import|export|part(?:[ \t\n]+of)?)\b[ \t\n]*['\"]([^'\"]+)['\"]",
                re.M,
            ),
            # 25. ownership: Authorship indicators.
            "ownership": re.compile(r"//\s*(?:Author|Created by|Maintainer|Copyright):\s+([^\n]+)", re.I),
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            # 26. planned_debt: The Promise. Future work markers.
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt: The Fracture. Admitted fragility or hacks.
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            # 29. spec_exposure: Map vs. Territory. Audit tags and architecture specs.
            "spec_exposure": re.compile(
                r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit|RFC|W3C|CERN|TBL|ENQUIRE)[^\]]*\]|\b(?:Tim\s+Berners-Lee|WorldWideWeb|HyperText\s+Proposal)\b",
                re.I,
            ),
            # 30. tabs_vs_spaces (Formatting Inconsistencies): Indentation Tracker. Tabs vs 2-space standardization.
            "tabs_vs_spaces": None,
            # 31. ssr_boundaries: View Horizon. shelf/Serverpod response handlers.
            "ssr_boundaries": re.compile(
                r"\b(shelf|dart_frog|Serverpod|Response\.(?:ok|internalServerError)|RequestContext|Router\(\)|Handler|Serve|renderHtml)\b",
                re.I,
            ),
            # 32. events: Pub/Sub Network. Stream subscriptions and broadcast observables.
            "events": re.compile(
                r"\b(StreamController|EventBus|Subject|BehaviorSubject|PublishSubject|EventEmitter|BlocProvider|notifyListeners)\b|\.listen\s*\(",
                re.I,
            ),
            # 33. dependency_injection: Inversion of Control. GetIt, Provider, and Injectable markers.
            "dependency_injection": re.compile(
                r"\b(GetIt\.I|GetIt\.instance|Provider\.of|ConsumerWidget|ref\.watch|ref\.read|Injector|@injectable)\b",
                re.I,
            ),
            # 34. macros: Preprocessor Hooks. Modern macros and JsonSerializable generators.
            "macros": re.compile(
                r"\bmacro\s+class\b|@(?!(?:override|deprecated|required|protected|visibleForTesting|pragma|immutable))[A-Z]\w*Macro\(\)|@JsonSerializable|@freezed",
                re.I,
            ),
            # 35. pointers: Memory Map. dart:ffi bridging to native memory space.
            "pointers": re.compile(
                r"\b(dart:ffi|Pointer<|NativeFunction<|Opaque|ffi\.cast|IntPtr|ffi\.Pointer)\b",
                re.I,
            ),
            # 36. memory_alloc: Manual Memory Management. Allocators bypassing the GC.
            "memory_alloc": re.compile(
                r"\b(ffi\.Allocator|malloc\.allocate|calloc\.allocate|malloc\.free|Arena|using\s*\(\s*\(Arena)\b",
                re.I,
            ),
            # 37. inline_asm: Bare Metal.
            "inline_asm": None,
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # 38. telemetry: Professional diagnostics (Structured logs).
            "telemetry": re.compile(
                r"\b(developer\.log|Logger|log|FirebaseCrashlytics|Sentry)\.(?:info|error|warn|severe|debug|trace|recordError)\b|\bdart:developer\b",
                re.I,
            ),
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs): Standard output.
            "debug_prints": re.compile(r"\b(print|debugPrint)\s*\(", re.I),
            # 40. explicit_casts (Explicit Type Casting): "Trust Me" Tax. Explicit casting.
            "explicit_casts": re.compile(r"\bas\s+[A-Z]\w*|\(\s*[A-Z]\w*\s*\)\s*[a-zA-Z_$]"),
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts) Aborting context.
            "panics_and_aborts": re.compile(r"\b(throw|rethrow|exit|exitCode|Process\.killPid)\b", re.I),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses) (Forced waits/delays).
            "thread_sleeps": re.compile(r"\b(sleep|delay|setTimeout|setInterval)\s*\(", re.I),
            # 43. bitwise_ops (Bitwise Operations)
            "bitwise_ops": re.compile(r"(?<!&)&(?!&)|(?<!\|)\|(?!\|)|<<|>>|\^|~(?!=|/)"),
            # 44. sync_locks (Resource Management & Stability) Coordinated threading.
            "sync_locks": re.compile(r"\b(Mutex|Lock|synchronized|Semaphore|Completer)\b", re.I),
            # 45. immutability_locks (Immutability Constraints) Immutability.
            "immutability_locks": re.compile(r"\b(const|final|readonly|@immutable)\b", re.I),
            # 46. cleanup (Resource Cleanup / Teardown) Resource release.
            "cleanup": re.compile(r"\b(dispose|close|cleanup|cancel|drop|free)\s*\(", re.I),
            # 47. encapsulation Scope hiding (Underscore prefix).
            "encapsulation": re.compile(r"\b(_[a-zA-Z0-9_$]+)\b|@protected|@private"),
            # 48. listeners (Event Listeners / Observers) Waiting for state broadcasts.
            "listeners": re.compile(r"\b(on\(|addEventListener|subscribe|watch|useEffect|listen)\b", re.I),
            # 49. test_skip (Bypassed Tests / Ignored Specs)
            "test_skip": re.compile(r"\b(@Ignore|test\.skip|t\.Skip|xit|mock)\b", re.I),
            # --- PHASE 3: HYBRID DOMAIN SENSORS (Dart Specifics) ---
            "serialization_parsing": re.compile(
                r"\b(jsonDecode|jsonEncode|json\.decode|json\.encode|Utf8Decoder|Utf8Encoder)\b"
            ),
            "regex_execution": re.compile(r"\b(RegExp\s*\()|\.(hasMatch|allMatches|stringMatch)\b"),
            "time_date_logic": re.compile(r"\b(DateTime\.now|Duration\s*\(|Timer\.run|Timer\.periodic|Stopwatch)\b"),
            "ipc_rpc_bridges": re.compile(
                r"\b(Isolate\.spawn|ReceivePort|SendPort|Process\.run|Process\.start|HttpClient)\b"
            ),
        },
    },
    "scala": {
        "_meta": {
            "target_version": "Scala 3 (Dotty / Braceless Syntax / Contextual Abstractions)",
            "last_updated": "2026-02-18",
            "blueprint_version": "v5.0",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard sources, worksheet files (.sc), and pure-Scala build tool configurations (.sbt).
        "extensions": [".scala", ".sc", ".sbt", ".kojo"],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: Scala build definitions are typically handled by .sbt extensions rather than extensionless files.
        "exact_matches": [],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions, build files, and Play framework configurations to anchor the ecosystem.
        "discriminators": [
            ".scala",
            "build.sbt",
            "application.conf",
            "Dependencies.scala",
            "project/build.properties",
            "project/plugins.sbt",
        ],
        # EXECUTION SIGNATURES: Interpreters found on Line 1 for Scala scripting and the Ammonite REPL.
        "shebangs": ["scala", "amm", "scala-cli"],
        # UPGRADED: Maps to Family 2 (Nested C)
        # Rationale: Scala explicitly supports nested multi-line comments (/* /* */ */),
        # requiring depth-aware stripping to prevent premature termination.
        "lexical_family": "recursive_block",
        "rules": {
            "_line_anchor": re.compile(r"//"),
            "_inline_comment": re.compile(r"//"),
            "_block_start": re.compile(r"/\*"),
            "_block_end": re.compile(r"\*/"),
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # 1. branch: decisions that split flow. Includes Scala 3 if-then and match-case.
            "branch": re.compile(
                r"\b(if|then|else|match|case|try|catch|finally|for|while|do|throw|yield)\b|&&|\|\|",
                re.I,
            ),
            # 2. args: Parameters / Coupling. Captures parameters in method signatures and lambdas.
            "args": re.compile(
                r"\bdef\s+[a-zA-Z_]\w*(?:\[[^\]]*\])?\s*\([^)]*\)|\([^)]*\)[ \t]*=>|\b[a-zA-Z_]\w*[ \t]*=>"
            ),
            # 3. linear: Sequential I/O & Network Boundaries. Structural boundaries. EXCLUDES access modifiers and val/var.
            "structural_boundaries": re.compile(
                r"\b(lazy|type|opaque|class|trait|object|enum|extension|import|export|return|extends|with|derives|new|given|using)\b"
            ),
            # 4. func_start: Executable Logic Anchors. Anchors executable logic. EXCLUDES structural headers.
            "func_start": re.compile(
                # =====================================================================
                # [ THE VERTICAL MODIFIER SHIELD (SCALA) ]
                # Scala 3 developers frequently stack modifiers (inline, transparent)
                # and annotations across multiple lines before the `def` keyword.
                # FIX: Upgraded horizontal spaces `[ \t]+` to vertical spaces `[ \t\n]+`
                # across the attribute stepper and modifier capture, explicitly allowing
                # the engine to wrap lines without triggering ReDoS.
                # =====================================================================
                r"^[ \t]*(?:@[\w.]+(?:\([^)]*\))?[ \t\n]*){0,5}"
                r"(?:(?:override|private|protected|final|implicit|inline|transparent|open|lazy)[ \t\n]+){0,3}"
                r"def[ \t\n]+([a-zA-Z_]\w*)(?=[ \t\n]*[\[(:=]|$)",
                re.M,
            ),
            # 5. class_start: Object / Entity Declarations. Defines structural entities and OO boundaries.
            "class_start": re.compile(
                r"^[ \t]*(?:@[\w.]+(?:\([^)]*\))?[ \t]+){0,5}"
                r"(?:(?:sealed|abstract|final|case|open|opaque|transparent)[ \t]+){0,3}"
                r"(?:class|trait|object|enum)\s+([A-Za-z_]\w*)(?=[ \t]*[\[({]|\s+extends|\n|$)",
                re.M,
            ),
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            # 6. safety: Defensive Programming. Monadic error handling (Option/Try) and assertions.
            "safety": re.compile(
                r"\b(Option|Some|None|Try|Success|Failure|Either|Left|Right|sealed|require|assert|assume)\b|\|\s*Null\b"
            ),
            # 7. safety_neg: Safety Bypasses. Actively bypassing type safety (asInstanceOf, .get).
            "safety_bypasses": re.compile(r"\b(null|asInstanceOf|isInstanceOf|\.get\b(?!Class)|@unchecked|Any|AnyRef)\b"),
            # 8. danger: High-Risk Execution. Process killers and catastrophic exit commands.
            "high_risk_execution": re.compile(r"\b(System\.exit|sys\.exit|Thread\.stop|Runtime\.getRuntime\.exec)\b"),
            # 9. io: I/O & Network Boundaries. Filesystem, Network, and Http Clients (Includes CERN triggers).
            "io": re.compile(
                r"\b(Source|java\.io|java\.nio|Files\.|Socket|ServerSocket|sttp|Http|WSClient|HTLoad|HTGet|ENQUIRE)\b"
            ),
            # 10. api: Public Surface Area. Implicit public visibility and Scala 3 @main entry points.
            "api": re.compile(
                r"\b(export)\b|@(?:main|GetMapping|PostMapping|Endpoint|Path)\b|^[ \t]*(?:override\s+|inline\s+|transparent[ \t]+)?def\s+[^_]\w+",
                re.M,
            ),
            # 11. flux: State Mutation. State mutation (var and mutable collection updates).
            "state_mutation": re.compile(
                r"\b(var|scala\.collection\.mutable|AtomicReference|AtomicInteger)\b|^[ \t]*[a-zA-Z_]\w*[ \t]*=",
                re.M,
            ),
            # 12. dead_code (Commented Logic / Deprecated Trails) Commented out structural code or logic trails.
            "dead_code": re.compile(
                r"//[ \t]*(?:def|val|var|class|object|trait|if|match|println|import)\b|/\*[ \t]*(?:def|val|class|object)"
            ),
            # 13. doc: Structured Documentation. Scaladoc documentation (/**) and annotations.
            "doc": re.compile(r"/\*\*|@param|@return|@tparam|@throws|@see|@note"),
            # 14. test: Testing & Assertions. ScalaTest, MUnit, and standard expect/verify markers.
            "test": re.compile(
                r"\b(test\s*\(|it\s+should|assertEquals|assertThrows|AnyFunSuite|WordSpec|munit|weaver)\b|\b(?:must|expect|assert)\s*[\(\{]"
            ),
            # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
            # 15. concurrency: Temporal Static. Effect systems and Actor paradigms (ZIO, Cats Effect, Akka).
            "concurrency": re.compile(
                r"\b(Future|Promise|Await|Actor|Behavior|ZIO|UIO|Task|RIO|cats\.effect\.IO|Fiber|FiberRef|Ref|Deferred|Semaphore)\b"
            ),
            # 16. ui_framework: UI / View Components. Scala.js DOM and XML literals (Includes TBL triggers).
            "ui_framework": re.compile(
                r"\b(dom\.|Laminar|Tyrian|HtmlElement|Document|Node|SGML|HyperLink|scala\.xml|Elem|XML|WorldWideWeb|BrowserView)\b"
            ),
            # 17. closures: Closures / Anonymous Functions. Anonymous function fat-arrows and underscores.
            "closures": re.compile(r"=>|(?<=\()\s*_\s*(?=[\),])|(?<=\W)_\s*(?=\W)"),
            # 18. globals: Global / Shared State. Singletons (objects) and JVM environment bindings.
            "globals": re.compile(
                r"\b(object\s+[A-Z]\w*|sys\.env|sys\.props|System\.getProperty|scala\.util\.Properties)\b"
            ),
            # 19. decorators: Decorators / Annotations. Method and class annotations.
            "decorators": re.compile(r"@[A-Za-z_]\w*(?:\([^)]*\))?"),
            # 20. generics: Generics / Type Parameters. Type parameterization and HKT constraints.
            "generics": re.compile(r"\[\s*[+-]?[A-Z][^\]]*\]|\bF\[_\]|<:|>:|\[[ \t]*_\s*\]"),
            # 21. comprehensions: Iterators / Comprehensions. For-comprehensions and monadic chains.
            "comprehensions": re.compile(
                r"\bfor\s*(?:\{[^}]*\}|\([^)]*\))\s*yield\b|\.(?:map|flatMap|filter|withFilter|foldLeft|reduce|collect)\s*[\(\{]"
            ),
            # 22. scientific: Numerical / Compute Libraries. Math library and linear algebra wrappers.
            "scientific": re.compile(
                r"\b(scala\.math|breeze\.|spire\.|algebird|Math\.|StrictMath\.|DenseMatrix|DenseVector)\b"
            ),
            # 23. heat_triggers: Metaprogramming & Reflection. Contextual abstractions and implicit resolution.
            "reflection_metaprogramming": re.compile(
                r"\b(implicit|given|using|inline|extension|TypeTag|ClassTag|scala\.reflect|Typeable|Dynamic|summon|derives)\b"
            ),
            # 24. import (Dependency Inclusions)
            "import": re.compile(r"\b(?:import|export)\s+[\w.{}\s,]+", re.M),
            "_dependency_capture": re.compile(
                # =====================================================================
                # [ FUTURE LLM CONTEXT: THE DYNAMIC EXECUTION SHIFT (SCALA) ]
                # PURPOSE: Extracts external dependencies for the Network Graph and Firewall.
                #
                # HISTORICAL BUG: Anchored to the start of the line `^[ \t]*`. Scala
                # developers frequently scope imports locally inside methods, classes,
                # or traits to prevent namespace pollution. The anchored regex missed
                # all of these local dependencies.
                #
                # THE FIX: Stripped the `^` anchor and rely on the `\b` word boundary.
                #
                # [ THE BLOCK DESTRUCTURING SHIELD ]
                # Scala relies heavily on bracketed block imports: `import java.util.{List, Map}`.
                # The capture group `([\w.{}\s,]+)` is expanded to swallow the entire
                # comma-separated block. The downstream parser must flatten this string
                # and split on commas/brackets to extract the individual modules.
                # =====================================================================
                r"\b(?:import|export)\s+([\w.{}\s,]+)",
                re.M,
            ),
            # 25. ownership: Authorship indicators.
            "ownership": re.compile(
                r"(?:@author|Created by|Maintainer|Copyright|Tim Berners-Lee):\s+([^\n]+)",
                re.I,
            ),
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            # 26. planned_debt: The Promise. Future work markers.
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt: The Fracture. Admitted fragility or hacks.
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            # 29. spec_exposure: Map vs. Territory. Audit tags and architecture specs.
            "spec_exposure": re.compile(
                r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)\]|\b(?:WorldWideWeb|HyperText\s+Proposal|NeXTSTEP)\b",
                re.I,
            ),
            # 30. tabs_vs_spaces (Formatting Inconsistencies): Indentation Tracker. Tabs vs 2-space standardization.
            "tabs_vs_spaces": None,
            # 31. ssr_boundaries: View Horizon. Play Framework and twirl template endpoints.
            "ssr_boundaries": re.compile(
                r"\b(Action|Controller|HttpRoutes|ServerEndpoint|twirl|html\.[a-zA-Z_]\w*|Ok\(|BadRequest\()\b"
            ),
            # 32. events: Pub/Sub Network. Stream processing and event bus signatures.
            "events": re.compile(r"\b(Source|Flow|Sink|fs2\.Stream|ZStream|EventBus|system\.eventStream|Observable)\b"),
            # 33. dependency_injection: Inversion of Control. ZLayer and ReaderT patterns.
            "dependency_injection": re.compile(
                r"\b(@Inject|wire\[|ZLayer|ZLayer\.from|provide|provideSome|ReaderT|Kleisli|requires)\b"
            ),
            # 34. macros: Preprocessor Hooks. Scala 3 inline and quoted metaprogramming.
            "macros": re.compile(
                r"\b(inline\s+def|transparent\s+inline|macro|scala\.quoted|Expr|Type|Quotes)\b|\$\{.*?\}|\'\{"
            ),
            # 35. pointers: Memory Map. Scala Native C-Interop pointers.
            "pointers": re.compile(r"\b(Ptr\[[^\]]+\]|scala\.scalanative\.unsafe|!ptr|ptr\.|CFuncPtr|CStruct\d+)\b"),
            # 36. memory_alloc: Manual Memory Management. Heap and Native allocations.
            "memory_alloc": re.compile(
                r"\b(Zone|zone[ \t]*\{|alloc\[[^\]]+\]|malloc|calloc|free|scala\.scalanative\.libc\.stdlib)\b"
            ),
            # 37. inline_asm: Bare Metal.
            "inline_asm": None,
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # 38. telemetry: Professional diagnostics (Structured logs).
            "telemetry": re.compile(
                r"\b(?:logger|log|ZIO\.log|LoggerFactory|log4cats|slf4j)\.(?:info|error|warn|debug|trace)\b|@Slf4j"
            ),
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs): Standard output.
            "debug_prints": re.compile(r"\b(println|print|Console\.println)\b"),
            # 40. explicit_casts (Explicit Type Casting): "Trust Me" Tax. Explicit type coercion.
            "explicit_casts": re.compile(r"\basInstanceOf\[[^\]]*\]|\.(?:toInt|toLong|toFloat|toDouble|toByte|toShort)\b"),
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts) Aborting context.
            "panics_and_aborts": re.compile(r"\b(throw|panic|abort|sys\.error|exit)\b"),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses) (Forced waits/sleep).
            "thread_sleeps": re.compile(r"\b(Thread\.sleep|delay|setTimeout|setInterval)\s*\("),
            # 43. bitwise_ops (Bitwise Operations)
            "bitwise_ops": re.compile(r"(?<!&)&(?!&)|(?<!\|)\|(?!\|)|<<|>>|\^|~"),
            # 44. sync_locks (Resource Management & Stability) Coordinated threading.
            "sync_locks": re.compile(r"\b(synchronized|volatile|Semaphore|Mutex|lock|unlock)\b"),
            # 45. immutability_locks (Immutability Constraints) Immutability.
            "immutability_locks": re.compile(r"\b(val|final|sealed|readonly|Object\.freeze|immutable)\b"),
            # 46. cleanup (Resource Cleanup / Teardown) Resource release.
            "cleanup": re.compile(r"\b(dispose|close|cleanup|cancel|free|bracket|finally|onException)\b"),
            # 47. encapsulation (Encapsulation / Access Modifiers)
            "encapsulation": re.compile(r"\b(private|protected)\b|private\[[^\]]+\]"),
            # 48. listeners (Event Listeners / Observers) Waiting for state broadcasts.
            "listeners": re.compile(r"\b(on\(|addEventListener|subscribe|watch|useEffect|listen)\b"),
            # 49. test_skip (Bypassed Tests / Ignored Specs)
            "test_skip": re.compile(r"\b(ignore|pending|skip|xit|xdescribe)\b"),
            # --- PHASE 3: HYBRID DOMAIN SENSORS (Scala Specifics) ---
            "serialization_parsing": re.compile(
                r"\b(io\.circe|decode\[|asJson|Json\.parse|Json\.toJson|upickle\.default)\b"
            ),
            "regex_execution": re.compile(r'"[^"]+"\.r\b|\bRegex\s*\(|\.(findAllIn|findFirstIn|replaceAllIn)\b'),
            "time_date_logic": re.compile(
                r"\b(Duration\s*\(|FiniteDuration|System\.currentTimeMillis|LocalDate\.now)\b"
            ),
            "ipc_rpc_bridges": re.compile(r"\b(ActorSystem|ActorRef|sys\.process\._|Process\s*\(|Future\.apply)\b"),
        },
    },
    "dockerfile": {
        "_meta": {
            "target_version": "Dockerfile (BuildKit)",
            "last_updated": "2026-02-27",
            "blueprint_version": "v6.2.2",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard extensions for container definitions across Docker and Podman ecosystems.
        "extensions": [".dockerfile", ".containerfile"],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: The universally recognized, extensionless architectural anchors of containerized environments.
        "exact_matches": [
            "Dockerfile",
            "Containerfile",
            "Dockerfile.prod",
            "Dockerfile.dev",
            "Dockerfile.build",
            "Dockerfile.test",
            "Dockerfile.local",
        ],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: Compose files and ignore manifests acting as contextual baselines.
        "discriminators": [
            "docker-compose.yml",
            "docker-compose.yaml",
            ".dockerignore",
            "compose.yaml",
        ],
        # EXECUTION SIGNATURES: Docker natively uses BuildKit syntax directives instead of traditional shebangs.
        "shebangs": [],
        # UPGRADED: Maps to Family 3 (Pure Hash)
        # Rationale: Docker natively uses '#' exclusively for line-level comments and parser directives.
        "lexical_family": "line_exclusive",
        "rules": {
            "_line_anchor": re.compile(r"#"),
            "_inline_comment": re.compile(r"#"),
            "_block_start": None,
            "_block_end": None,
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # 1. branch (Control Flow / Branching)
            # Control flow executing inside RUN shell blocks. High density indicates complex embedded shell scripts.
            "branch": re.compile(
                r"\b(?:if|elif|else|fi|case|esac|for|while|do|done|until)\b|&&|\|\|",
                re.I,
            ),
            # 2. args (Parameters / Coupling)
            # Build arguments (`ARG`) passed into the container acting as input parameters to the satellite.
            "args": re.compile(r"^[ \t]*ARG[ \t]+[a-zA-Z0-9_-]+", re.M | re.I),
            # 3. linear (Sequential Boundaries)
            # Structural boundaries defining straight-line execution and environment contexts.
            # CRITICAL GUARDRAIL: EXCLUDES `FROM` and `RUN`/`CMD` to maintain geometric stability.
            "structural_boundaries": re.compile(r"^[ \t]*(?:WORKDIR|USER|VOLUME|STOPSIGNAL|SHELL|LABEL)\b", re.M | re.I),
            # 4. func_start (Executable Logic Anchors)
            # CRITICAL GUARDRAIL: Anchors logic blocks. ONLY executable logic blocks.
            # In Docker, `RUN`, `CMD`, and `ENTRYPOINT` execute logic, generating discrete intermediate image layers.
            "func_start": re.compile(r"^[ \t]*(RUN|CMD|ENTRYPOINT|HEALTHCHECK)(?=[ \t])", re.M | re.I),
            # 5. class_start (Object / Entity Declarations)
            # Defines object-oriented and structural boundaries. Drives API Surface Area math.
            # `FROM` instantiates a discrete build stage/image boundary, acting as a class wrapper.
            "class_start": re.compile(r"^[ \t]*(FROM)(?=[ \t])", re.M | re.I),
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            # 6. safety (Defensive Programming)
            # Hardening the container. Dropping root privileges (`USER nonroot`), explicit `HEALTHCHECK`,
            # setting explicit shell crash flags (`set -e`), and safe file ownership (`--chown`).
            "safety": re.compile(
                r"^[ \t]*HEALTHCHECK\b|--chown=|^[ \t]*USER[ \t]+(?!root\b|0\b)[a-zA-Z0-9_-]+|\bset[ \t]+-[exuo]\b",
                re.M | re.I,
            ),
            # 7. safety_neg (Safety Bypasses)
            # Actively bypassing isolation or safety logic.
            # Using `:latest`, running as root, setting permissions to 777, or blindly curling directly into bash.
            # CRITICAL GUARDRAIL: Safely bounds the curl/wget pipe `[^|\n]{1,200}` to prevent ReDoS on massive RUN chains.
            "safety_bypasses": re.compile(
                r":latest\b|^[ \t]*USER[ \t]+(?:root|0)\b|chmod[ \t]+777|--privileged|--allow-unauthenticated|\b(?:curl|wget)[ \t]+[^|\n]{1,200}\|[ \t]*(?:bash|sh|zsh)\b",
                re.M | re.I,
            ),
            # 8. danger (High-Risk Execution)
            # Extreme space debris. Destructive recursive removes targeting root, and dangerous dynamic eval.
            # CRITICAL GUARDRAIL: Raw terminal prints (`echo`) strictly routed to print_hits.
            "high_risk_execution": re.compile(r"\b(?:rm[ \t]+-rf[ \t]+/(?![A-Za-z])|eval|exec)\b", re.M | re.I),
            # 9. io (I/O & Network Boundaries)
            # Interaction with external networks, copying files from host, or executing package managers.
            "io": re.compile(
                r"^[ \t]*(?:COPY|ADD)[ \t]+|\b(?:wget|curl|apt-get|apk|yum|dnf|git[ \t]+clone|tar[ \t]+-[cx]f|unzip|pip[ \t]+install|npm[ \t]+install)\b",
                re.M | re.I,
            ),
            # 10. api (Public Surface Area)
            # Code exposed to the outside world. Ports explicitly exposed to the host network (`EXPOSE`).
            "api": re.compile(r"^[ \t]*EXPOSE[ \t]+[0-9]+", re.M | re.I),
            # 11. flux (State Mutation)
            # Mutation of state. Setting Environment variables that permanently alter the image layer state.
            "state_mutation": re.compile(
                r"^[ \t]*ENV[ \t]+[a-zA-Z0-9_]+|export[ \t]+[a-zA-Z0-9_]+[ \t]*=",
                re.M | re.I,
            ),
            # 12. dead_code (Commented Logic / Deprecated Trails)
            # Commented-out logic, commented-out structural Dockerfile commands.
            "dead_code": re.compile(
                r"^[ \t]*#[ \t]*(?:RUN|COPY|ADD|ENV|EXPOSE|FROM|CMD|ENTRYPOINT|WORKDIR)\b",
                re.M | re.I,
            ),
            # 13. doc (Structured Documentation)
            # Intent documentation meant for developers or image registries.
            "doc": re.compile(
                r"^[ \t]*LABEL[ \t]+(?:maintainer|org\.opencontainers|version|description)=|^[ \t]*#[ \t]*(?:Description|Usage|Author|Maintainer):",
                re.M | re.I,
            ),
            # 14. test (Testing & Assertions)
            # Explicit test runner executions inside the build layer (often used in CI multi-stage pipelines).
            "test": re.compile(
                r"\b(?:npm[ \t]+test|yarn[ \t]+test|pytest|go[ \t]+test|cargo[ \t]+test|make[ \t]+test)\b",
                re.M | re.I,
            ),
            # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
            # 15. concurrency (Asynchronous Execution)
            # Parallelism executed inside the build shell (e.g. compiling with all cores).
            "concurrency": re.compile(r"&[ \t]*$|\b(?:nohup|parallel|make[ \t]+-j|xargs[ \t]+-P)\b", re.M),
            # 16. ui_framework (UI / View Components)
            # Containerizing GUI applications (X11, Wayland, GTK).
            "ui_framework": re.compile(r"\b(?:xvfb|x11|wayland|gtk|qt5?|libgl1-mesa)\b", re.I),
            # 17. closures (Closures / Anonymous Functions)
            # Dockerfiles are purely declarative structurally; closures do not exist.
            "closures": None,
            # 18. globals (Global / Shared State)
            # Global environment variables mapping structurally.
            "globals": re.compile(r"^[ \t]*ENV[ \t]+[a-zA-Z0-9_]+", re.M | re.I),
            # 19. decorators (Decorators / Annotations)
            # Not natively applicable to Dockerfile architecture.
            "decorators": None,
            # 20. generics (Generics / Type Parameters)
            "generics": None,
            # 21. comprehensions (Iterators / Comprehensions)
            "comprehensions": None,
            # 22. scientific (Numerical / Compute Libraries)
            # Installing data science, ML base dependencies, or GPU drivers natively into the image.
            "scientific": re.compile(
                r"\b(?:nvidia/cuda|pytorch/pytorch|tensorflow/tensorflow|jupyter/)\b",
                re.I,
            ),
            # 23. heat_triggers (Metaprogramming & Reflection)
            # High Cognitive Load: Advanced BuildKit logic. Mounting caches, secrets, cross-platform builds, or `ONBUILD` (which defers execution to downstream images).
            "reflection_metaprogramming": re.compile(
                r"^[ \t]*ONBUILD\b|--mount=type=(?:cache|secret|bind|ssh)|--platform=|<<EOF",
                re.M | re.I,
            ),
            # 24. import (Dependency Inclusions)
            # Base images or dependencies pulled from other build stages (`COPY --from=`).
            "import": re.compile(r"^[ \t]*FROM[ \t]+[a-zA-Z0-9_./:-]+|--from=[a-zA-Z0-9_-]+", re.M | re.I),
            "_dependency_capture": re.compile(
                r"^[ \t]*FROM\s+(?:--[\w-]+=[^\s]+\s+)?([a-zA-Z0-9_./:-]+)|--from=([a-zA-Z0-9_-]+)",
                re.M | re.I,
            ),
            # 25. ownership (Authorship Metadata)
            # Standard metadata tracing image ownership (legacy MAINTAINER or modern LABEL).
            "ownership": re.compile(
                r"^[ \t]*(?:MAINTAINER|LABEL[ \t]+maintainer=|LABEL[ \t]+org\.opencontainers\.image\.authors=)[ \t]*(.*)",
                re.M | re.I,
            ),
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            # 26. planned_debt (Annotated Debt / TODOs)
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            # 29. spec_exposure (Spec / Audit Traceability)
            "spec_exposure": re.compile(
                r"\[(?:[ \t]*SPEC[ \t]*-[ \t]*\d+|spec|audit|CVE-\d{4}-\d+)[^\]]*\]",
                re.I,
            ),
            # 30. tabs_vs_spaces (Formatting Inconsistencies) 
            # Dockerfiles strictly use spaces for formatting continuations. Tabs indicate formatter disruption.
            "tabs_vs_spaces": None,
            # 31. ssr_boundaries (Server-Side Rendering)
            "ssr_boundaries": None,
            # 32. events (Event Emitters / Pub-Sub)
            # Container lifecycle events explicitly bound to the host OS.
            "events": re.compile(r"^[ \t]*STOPSIGNAL[ \t]+", re.M | re.I),
            # 33. dependency_injection (Dependency Injection / IoC)
            # BuildKit secret and SSH mounts injecting external state at compile time securely.
            "dependency_injection": re.compile(r"--mount=type=(?:secret|ssh)", re.I),
            # 34. macros (Preprocessor Directives / Macros)
            # Docker BuildKit `# syntax=` directives which change the parser dynamically at compile-time (just like C-macros).
            "macros": re.compile(r"^[ \t]*#[ \t]*(?:syntax|escape)[ \t]*=", re.M | re.I),
            # 35. pointers (Pointer Arithmetic / Memory Addressing)
            "pointers": None,
            # 36. memory_alloc (Manual Memory Management)
            # Explicit memory limits defined in ENV vars that configure Java/Node runtime heaps natively.
            "memory_alloc": re.compile(
                r"\b(?:--memory=|JAVA_OPTS|JAVA_TOOL_OPTIONS|NODE_OPTIONS|--max-old-space-size|-Xmx|-Xms)\b",
                re.I,
            ),
            # 37. inline_asm (The Bare Metal)
            "inline_asm": None,
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # 38. telemetry (Structured Logging / Telemetry)
            # Forcing specific logging outputs at the container level or symlinking to stdout for daemon parsing.
            "telemetry": re.compile(
                r"\b(?:LOG_LEVEL|--log-level[ \t]+(?:debug|info|warn|error)|ln[ \t]+-sf[ \t]+/dev/stdout)\b",
                re.I,
            ),
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
            # Shell echos used for ad-hoc debugging in the build output log.
            "debug_prints": re.compile(r"\b(?:echo|printf)\b", re.I),
            # # 40. explicit_casts (Explicit Type Casting)
            "explicit_casts": None,
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
            # Hard execution aborts forcing the build to fail dynamically.
            "panics_and_aborts": re.compile(r"\b(?:exit[ \t]+[1-9]|kill[ \t]+-[0-9]+)\b", re.I),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
            # Forcing the build thread to sleep (often a hack to wait for a daemon/network).
            "thread_sleeps": re.compile(r"\bsleep[ \t]+[0-9]+\b", re.I),
            # 43. bitwise_ops (Bitwise Operations)
            "bitwise_ops": None,
            # 44. sync_locks (Resource Management & Stability)
            # Utilizing file locking to prevent parallel build collisions.
            "sync_locks": re.compile(r"\bflock\b", re.I),
            # 45. immutability_locks (Immutability Constraints)
            # Pinning dependencies to immutable SHAs rather than mutable tags. .
            "immutability_locks": re.compile(r"@[a-f0-9]{64}\b|--read-only|:ro\b", re.I),
            # 46. cleanup (Resource Cleanup / Teardown)
            # Explicitly purging apt/apk caches to reduce final container bloat. .
            "cleanup": re.compile(
                r"\b(?:apt-get[ \t]+clean|rm[ \t]+-rf[ \t]+/var/lib/apt/lists|apk[ \t]+(?:cache[ \t]+)?clean|yum[ \t]+clean[ \t]+all|npm[ \t]+cache[ \t]+clean)\b",
                re.I,
            ),
            # 47. encapsulation (Access Modifiers / Encapsulation)
            # Explicitly encapsulating logic in multi-stage builds (`AS builder`). Hides intermediate build layers.
            "encapsulation": re.compile(r"^[ \t]*FROM[ \t]+[^\n]+[ \t]+AS[ \t]+[a-zA-Z0-9_-]+", re.M | re.I),
            # 48. listeners (Event Listeners / Observers)
            # Exposing ports for network consumption. .
            "listeners": re.compile(r"^[ \t]*EXPOSE[ \t]+[0-9]+", re.M | re.I),
            # 49. test_skip (Bypassed Tests / Ignored Specs)
            # Bypassing package manager tests/audits or using logical OR to ignore failures (`|| true`).
            "test_skip": re.compile(
                r"\|\|[ \t]*true\b|\b(?:--passWithNoTests|skipTests|Dmaven\.test\.skip=true|--no-audit)\b",
                re.I,
            ),
            # --- PHASE 3: HYBRID DOMAIN SENSORS (Dockerfile Specifics) ---
            "serialization_parsing": re.compile(
                r"(?i)^(?:ADD|COPY)\s+.*\.(?:tar\.gz|zip|tgz|tar)\b"
            ),  # ADD auto-extracts archives
            "regex_execution": re.compile(r"(?i)^RUN\s+.*(?:grep|sed|awk)\b"),  # Catches shell-delegated regex
            "time_date_logic": re.compile(r"(?i)^(?:HEALTHCHECK.*(?:--interval|--timeout)|RUN\s+.*sleep)\b"),
            "ipc_rpc_bridges": re.compile(r"(?i)^(?:EXPOSE|VOLUME|ENTRYPOINT|CMD|STOPSIGNAL)\b"),
        },
    },
    "matlab": {
        "_meta": {
            "target_version": "MATLAB R2024b",
            "last_updated": "2026-02-27",
            "blueprint_version": "v6.2.2",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard scripts, functions, and modern Live Scripts (.mlx).
        "extensions": [".m", ".mlx"],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: MATLAB and Octave rely strictly on extensions for execution.
        "exact_matches": [],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: Critical for resolving the massive .m collision with Objective-C. Binary workspace and figure files act as absolute anchors.
        "discriminators": [".m", ".mat", ".fig", ".mlx", "project.prj"],
        # Instantly claims any .m file that uses MATLAB's unique comment character (%)
        # or the MATLAB function declaration syntax. Defeats Objective-C gravity theft.
        # Instantly claims any .m file via a definitive MATLAB section break (%%)
        # or properly formatted comment. (Removed 'function' to prevent stealing extensionless shell scripts).
        "internal_discriminator": re.compile(r"^[ \t]*(?:%[ \t]+|%%)", re.M),
        # EXECUTION SIGNATURES: Interpreters found on Line 1 for GNU Octave or headless MATLAB CLI scripts.
        "shebangs": ["octave", "matlab"],
        # UPGRADED: Maps to Family 8 (Singular/Unique)
        # Rationale: (CORRECTION) Uses '%' for lines and '%{ %}' for blocks. Mapping this to
        # hybrid_dash would cause the engine to look for '--', missing the math entirely.
        "lexical_family": "line_exclusive",
        "rules": {
            "_line_anchor": re.compile(r"%"),
            "_inline_comment": re.compile(r"%"),
            "_block_start": re.compile(r"^[ \t]*%\{", re.M),
            "_block_end": re.compile(r"^[ \t]*%\}", re.M),
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # branch: MATLAB control flow. EXCLUDES 'error' and 'rethrow' (bailout_hits).
            "branch": re.compile(r"\b(?:if|elseif|else|switch|case|otherwise|for|while|try|catch)\b|&&|\|\||~="),
            # args: Captures standard function inputs and return signatures `function [out1, out2] = myFun(in1, in2)`.
            # CRITICAL GUARDRAIL: Safely bounds `\([^)]*\)` and `\[[^\]]*\]`.
            "args": re.compile(
                r"\bfunction[ \t]+(?:\[[^\]]*\][ \t]*=[ \t]*|[a-zA-Z_]\w*[ \t]*=[ \t]*)?[a-zA-Z_]\w*[ \t]*\([^)]*\)|@[ \t]*\([^)]*\)"
            ),
            # linear: Structural boundaries defining straight-line execution.
            # CRITICAL GUARDRAIL: Access modifiers (private, protected) explicitly omitted.
            "structural_boundaries": re.compile(
                r"\b(?:classdef|properties|methods|events|enumeration|return|global|persistent|continue|break|end)\b"
            ),
            # func_start: Anchors logic blocks. Exactly anchors executable blocks.
            # Negative lookahead explicitly prevents control flow or OOP structures from generating false positive logic anchors.
            "func_start": re.compile(
                # =====================================================================
                # [ THE VERTICAL OUTPUT ARRAY SHIELD (MATLAB) ]
                # MATLAB functions define their return types *before* the function name
                # (e.g., `function [out1, out2] = myFunc()`). Developers will frequently
                # wrap these output arrays across multiple vertical lines.
                # FIX: Exchanged horizontal `[ \t]*` constraints with `[ \t\n]*` inside
                # the optional `(?:\[[^\]]*\]...)?` output array matcher, allowing the
                # regex to crawl down to the assignment operator `=` and map the name.
                # =====================================================================
                r"^[ \t]*(?!(?:if|for|while|switch|catch|classdef)\b)function[ \t\n]+(?:\[[^\]]*\][ \t\n]*=[ \t\n]*|[a-zA-Z_]\w*[ \t\n]*=[ \t\n]*)?([a-zA-Z_]\w*)(?=[ \t\n]*\(|$)",
                re.M,
            ),
            # class_start: Defines an object-oriented boundary.
            # Safely steps over optional class attributes like `classdef (ConstructOnLoad) MyClass`
            "class_start": re.compile(
                r"^[ \t]*classdef(?:[ \t]*\([^)]*\))?[ \t]+([a-zA-Z_]\w*)(?=[ \t\n]|$)",
                re.M,
            ),
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            # safety: Defensive programming, modern argument validation (`arguments` block), and type/shape checks.
            "safety": re.compile(
                r"\b(?:try|catch|narginchk|nargoutchk|validateattributes|validatestring|mustBe[A-Za-z_]\w*|assert|isa|isempty|isnumeric|ischar|isstruct|isfield|iscell|islogical|arguments)\b"
            ),
            # safety_neg: Actively bypasses safety via dynamic strings or manipulating the caller workspace.
            "safety_bypasses": re.compile(r'\b(?:eval|evalin|assignin|evalc)\b|\bwarning[ \t]*\([ \t]*[\'"]off[\'"]'),
            # danger: Destructive workspace actions and OS bypasses.
            # CRITICAL GUARDRAIL: Raw terminal prints (`disp`) strictly routed to print_hits.
            "high_risk_execution": re.compile(
                r"\b(?:clear[ \t]+all|clc|system|dos|unix|exit|quit|keyboard)\b|^[ \t]*![ \t]*[a-zA-Z_]",
                re.M | re.I,
            ),
            # io: Interactions with disk, hardware, or web.
            "io": re.compile(
                r"\b(?:load|save|fopen|fclose|fread|fwrite|fscanf|webread|webwrite|urlread|urlwrite|readtable|writetable|readmatrix|writematrix|serialport|imread|imwrite|audioread)\b"
            ),
            # api: Public APIs. We track explicit Methods blocks that don't declare private access.
            "api": re.compile(
                r"^[ \t]*methods(?:[ \t]*\([ \t]*Access[ \t]*=[ \t]*public[ \t]*\))?",
                re.M | re.I,
            ),
            # flux: Mutation of state via assignment.
            # Safely clamped with `[ \t]*=[ \t]*` to avoid newline spirals. Bounded nested fields `{0,5}`.
            "state_mutation": re.compile(
                r"^[ \t]*[a-zA-Z_]\w*(?:\([^)]*\)|\{[^}]*\}|\.[a-zA-Z_]\w*){0,5}[ \t]*=[ \t]*[^=]|\b(?:clear|clearvars)\b",
                re.M,
            ),
            # 12. dead_code (Commented Logic / Deprecated Trails)
            "dead_code": re.compile(r"^[ \t]*%[ \t]*(?:if|for|while|function|classdef)\b", re.M),
            # doc: Standard MATLAB Help text (`%%` sections) or typed annotations.
            "doc": re.compile(
                r"^[ \t]*%[ \t]*@(?:param|return|author)|^[ \t]*%%[ \t]*[A-Z][A-Z0-9_]*",
                re.M,
            ),
            # test: MATLAB unit testing framework keywords.
            "test": re.compile(
                r"\b(?:matlab\.unittest|TestCase|verifyEqual|assertEqual|assertGreaterThan|verifyTrue|verifyFalse|verifyError)\b"
            ),
            # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
            # concurrency: Parallel Computing Toolbox (parallel loops and batch jobs).
            "concurrency": re.compile(
                r"\b(?:parfor|parfeval|spmd|batch|createJob|createTask|BackgroundPool|parpool|fetchOutputs)\b"
            ),
            # ui_framework: MATLAB UI Figures and App Designer interfaces.
            "ui_framework": re.compile(
                r"\b(?:uifigure|uicontrol|uiaxes|uilabel|uibutton|appdesigner|guide|drawnow|msgbox|errordlg|warndlg|figure|plot|scatter|surf)\b"
            ),
            # closures: Anonymous functions (MATLAB's lambdas).
            "closures": re.compile(r"@[ \t]*\([^)]*\)"),
            # globals: Globals and persistent memory retaining state across calls.
            "globals": re.compile(r"\b(?:global|persistent|setenv|getenv)\b"),
            # decorators: MATLAB Property/Method attribute blocks (e.g., `methods (Access = private)`).
            # Safely bounded with `\([^)]*\)` to avoid ReDoS.
            "decorators": re.compile(r"^[ \t]*(?:properties|methods|events)[ \t]*\([^)]*\)", re.M),
            # generics: MATLAB is dynamically typed. Generics do not exist natively.
            "generics": None,
            # comprehensions: MATLAB array mapping functions (the closest equivalent to list comprehensions).
            "comprehensions": re.compile(r"\b(?:arrayfun|cellfun|structfun|rowfun|varfun)\b"),
            # scientific: The core of MATLAB. High-density built-in numerical solvers and DSP operations.
            "scientific": re.compile(
                r"\b(?:fft|ifft|svd|eig|inv|det|polyfit|ode45|ode15s|integral|cross|dot)\b|\.\*|\./|\.\^"
            ),
            # heat_triggers: Metaprogramming (feval), implicit expansion (bsxfun), and reflection.
            "reflection_metaprogramming": re.compile(
                r"\b(?:feval|bsxfun|cell2mat|mat2cell|num2cell|struct2cell|str2func|func2str|meta\.class|metaclass)\b|\?[a-zA-Z_]\w*"
            ),
            # import: Namespace/Class loading.
            "import": re.compile(r"^[ \t]*import[ \t]+[a-zA-Z0-9_.*]+", re.M),
            "_dependency_capture": re.compile(r"^[ \t]*import[ \t\n]+([a-zA-Z0-9_.*]+)", re.M),
            # ownership: Standard MATLAB comment authorship signatures.
            "ownership": re.compile(r"^[ \t]*%[ \t]*(?:Author|Created by|Copyright)[ \t]*:(.*)", re.M | re.I),
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            # 26. planned_debt (Annotated Debt / TODOs)
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            "spec_exposure": re.compile(r"\[(?:[ \t]*SPEC[ \t]*-[ \t]*\d+|spec|audit)[^\]]*\]", re.I),
            # civil_war: MATLAB default is 4 spaces. Raw tabs indicate formatter disruption.
            "tabs_vs_spaces": None,
            # ssr_boundaries: Web App compiler hooks.
            "ssr_boundaries": re.compile(r"\b(?:webwindow|htmlTree)\b"),
            # events: MATLAB Object-Oriented Event triggering.
            "events": re.compile(r"\b(?:notify|event\.EventData|event\.PropertyEvent)\b"),
            "dependency_injection": None,
            "macros": None,
            # pointers: C/C++ FFI pointer manipulation via MATLAB's `libpointer` or `handle` class.
            "pointers": re.compile(r"\b(?:libpointer|calllib)\b|<[ \t]*handle\b"),
            # memory_alloc: Explicit pre-allocation (a critical MATLAB performance mechanism to avoid array resizing).
            "memory_alloc": re.compile(
                r"\b(?:zeros|ones|nan|NaN|false|true|cell|struct|prealloc)[ \t]*\([^)]*\)",
                re.I,
            ),
            "inline_asm": None,
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # telemetry: Custom structured logging frameworks.
            "telemetry": re.compile(
                r"\b(?:log4m|logger\.(?:info|debug|warn|error)|logDebug|logInfo|logWarn|logError)\b",
                re.I,
            ),
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs)
            "debug_prints": re.compile(r"\b(?:disp|warning|fprintf(?![ \t]*\([ \t]*[a-zA-Z_]))\b"),
            # # 40. explicit_casts (Explicit Type Casting)
            "explicit_casts": re.compile(
                r"\b(?:cast|typecast|int8|uint8|int16|uint16|int32|uint32|int64|uint64|single|double|logical)\s*\("
            ),
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
            "panics_and_aborts": re.compile(r"\b(?:error|throw|rethrow|MException|throwAsCaller)\b"),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
            "thread_sleeps": re.compile(r"\bpause[ \t]*\("),
            # 43. bitwise_ops (Bitwise Operations)
            "bitwise_ops": re.compile(r"\b(?:bitand|bitor|bitxor|bitcmp|bitshift|bitset|bitget)\b"),
            # sync_locks: Managing parallel data queues and thread pooling barriers.
            "sync_locks": re.compile(r"\b(?:labBarrier|labSend|labReceive|labBroadcast)\b"),
            # 45. immutability_locks (Immutability Constraints)
            "immutability_locks": re.compile(r"\bConstant\b"),
            # cleanup: Garbage collection and explicit file/handle destruction.
            "cleanup": re.compile(r"\b(?:clear|clearvars|delete|close|fclose|onCleanup)\b"),
            # 47. encapsulation (Encapsulation / Access Modifiers)
            "encapsulation": re.compile(r"Access[ \t]*=[ \t]*(?:private|protected)"),
            # 48. listeners (Event Listeners / Observers)
            "listeners": re.compile(r"\b(?:addlistener|event\.listener|event\.proplistener)\b"),
            # 49. test_skip (Bypassed Tests / Ignored Specs) Safety Theater bypasses.
            "test_skip": re.compile(r"\b(?:assume|assumeFail|assumeTrue|assumeFalse)\b"),
            # --- PHASE 3: HYBRID DOMAIN SENSORS (MATLAB Specifics) ---
            "serialization_parsing": re.compile(r"\b(jsondecode|jsonencode|xmlread|xmlwrite|load|save|readtable)\b"),
            "regex_execution": re.compile(r"\b(regexp|regexpi|regexprep)\b"),
            "time_date_logic": re.compile(r"\b(tic|toc|datetime|clock|now|pause|cputime)\b"),
            "ipc_rpc_bridges": re.compile(
                r"\b(system|dos|unix|tcpclient|tcpserver|parpool|parfor)\b|^\s*!"
            ),  # '!' is MATLAB's native shell escape
        },
    },
    "livecode": {
        "_meta": {
            "target_version": "LiveCode 9.6 / 10.0 (Current Stable/DP)",
            "last_updated": "2026-02-19",
            "blueprint_version": "v5.0",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Includes modern server scripts, builder files, binary stacks, and legacy Revolution stacks.
        "extensions": [".lc", ".livecodescript", ".lcb", ".livecode", ".stack", ".rev"],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: LiveCode environments rarely use extensionless execution scripts.
        "exact_matches": [],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions to anchor the LiveCode server/builder environment.
        "discriminators": [".lc", ".livecode", ".lcb", ".livecodescript"],
        # EXECUTION SIGNATURES: Interpreters found on Line 1 for LiveCode Server environments.
        "shebangs": ["livecode-server"],
        # UPGRADED: Maps to Family 6 (Polyglot)
        # Rationale: Accepts '--', '//', '#', and '/* */' to support both its legacy HyperTalk roots and modern C-style syntax.
        "lexical_family": "standard_block",
        "rules": {
            # --- LEXICAL DELIMITER CONTROLS ---
            # Handles all three line-comment styles found in the xTalk family.
            "_line_anchor": re.compile(r"--|//|#"),
            # Inline comments follow the same tri-token logic.
            "_inline_comment": re.compile(r"--|//|#"),
            # Block comment start: /* (Adopted in modern LiveCode)
            "_block_start": re.compile(r"/\*"),
            # Block comment end: */
            "_block_end": re.compile(r"\*/"),
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # 1. branch: decisions that split flow. Includes English-like loops and try-catch.
            "branch": re.compile(
                r"\b(if|then|else|switch|case|default|repeat|while|until|times|try|catch|finally|throw|next\s+repeat|and|or|not)\b",
                re.I,
            ),
            # 2. args: Parameters / Coupling. Captures parameters in handlers (on, command, function).
            "args": re.compile(
                r"(?:on|command|function|getprop|setprop)\s+[a-zA-Z0-9_-]+\s+([^\n]+)",
                re.I,
            ),
            # 3. linear: Sequential I/O & Network Boundaries. Structural boundaries and state transformation verbs.
            "structural_boundaries": re.compile(
                r"\b(put|get|set|go|send|dispatch|pass|return|add|subtract|multiply|divide|constant|visual\s+effect|play|sort|find|replace)\b",
                re.I,
            ),
            # 4. func_start: Executable Logic Anchors. Anchors executable logic blocks (handlers).
            "func_start": re.compile(
                r"^[ \t]*(?:private\s+|public[ \t]+)?(?:on|command|function|getprop|setprop)\s+([a-zA-Z0-9_-]+)(?=[ \t\n]|$)",
                re.I | re.M,
            ),
            # 5. class_start: Object / Entity Declarations. Defines structural entities (Stacks, Behaviors, Widgets).
            "class_start": re.compile(
                r'^[ \t]*(?:script|behavior|widget|module|library)\s+(["\'a-zA-Z_]\w*)(?=[ \t\n]|$)',
                re.I | re.M,
            ),
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            # 6. safety: Defensive Programming. Defensive programming and screen/message locking.
            "safety": re.compile(
                r"\b(try|catch|finally|throw|lock\s+screen|lock\s+messages|lock\s+errordialogs|assert|strict\s+compilation|is\s+a|is\s+strictly)\b",
                re.I,
            ),
            # 7. safety_neg: Safety Bypasses. Actively bypassing safety (disabling messages, raw do).
            "safety_bypasses": re.compile(
                r"\b(disable\s+messages|unlock\s+(?:screen|messages)|global\s+|do\s+(?![a-zA-Z_]\w*\b))\b",
                re.I,
            ),
            # 8. danger: High-Risk Execution. Process killers and blocking UI alerts in execution flow.
            "high_risk_execution": re.compile(
                r"\b(answer|ask|do(?!\s+(?:AppleScript|VBScript))|delete\s+(?:file|folder|url)|quit|exit\s+to\s+top)\b",
                re.I,
            ),
            # 9. io: I/O & Network Boundaries. Disk, Network, and URL fetching.
            "io": re.compile(
                r"\b(open\s+(?:file|socket|process)|read\s+from|write\s+to|close\s+(?:file|socket|process)|post\s+[^ \t\n]+?\s+to\s+url|get\s+url|put\s+url|load\s+url)\b",
                re.I,
            ),
            # 10. api: Public Surface Area. Exposed surface area (Any non-private handler).
            "api": re.compile(
                r"^[ \t]*(?:public[ \t]+)?(?!(?:private)\s+)(?:on|command|function|getprop|setprop)\s+[a-zA-Z0-9_-]+",
                re.I | re.M,
            ),
            # 11. flux: State Mutation. State mutation (The 'put into' core of xTalk).
            "state_mutation": re.compile(
                r"\b(?:put\s+[^ \t\n]+?\s+(?:into|after|before)|set\s+(?:the[ \t]+)?[a-zA-Z0-9_.]+\s+to|add\s+[^ \t\n]+?\s+to|subtract\s+[^ \t\n]+?\s+from)\b",
                re.I,
            ),
            # 12. dead_code (Commented Logic / Deprecated Trails) Commented out structural code.
            "dead_code": re.compile(
                r"^[ \t]*(?:--|#|//)[ \t]*(?:on|command|function|put|get|set|if|repeat|try|end)\b",
                re.I | re.M,
            ),
            # 13. doc: Structured Documentation. Structured documentation (/** or --@ tags).
            "doc": re.compile(
                r"^[ \t]*(?:--\||--@|/\*\*|//!).*(?:@param|@return|@author)|\b(?:Description|Purpose|Author|Summary):\b",
                re.I | re.M,
            ),
            # 14. test: Testing & Assertions. Unit testing framework markers.
            "test": re.compile(
                r"\b(command\s+test[a-zA-Z0-9_]*|pass\s+test|fail\s+test|Levure|LcU|runTests)\b",
                re.I,
            ),
            # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
            # 15. concurrency: Temporal Static. Message scheduling and non-blocking waits.
            "concurrency": re.compile(
                r"\b(send\s+[^ \t\n]+?\s+in\s+[^ \t\n]+?\s+(?:seconds|milliseconds|ticks)|wait\s+(?:for[ \t]+)?\d+\s+[^ \t\n]+?\s+with\s+messages|dispatch|pendingMessages|cancel)\b",
                re.I,
            ),
            # 16. ui_framework: UI / View Components. HyperCard-descendant object hierarchy.
            "ui_framework": re.compile(
                r"\b(card|stack|background|bg|button|btn|field|fld|group|grp|graphic|grc|image|img|scrollbar|browser|data\s+grid|widget)\b",
                re.I,
            ),
            # 17. closures: Closures / Anonymous Functions. (LiveCode Script lacks native lambdas).
            "closures": None,
            # 18. globals: Global / Shared State. Global state and environmental bindings.
            "globals": re.compile(
                r"\b(global\s+|the\s+global|the\s+environment|the\s+platform|\$ENV|it)\b",
                re.I,
            ),
            # 19. decorators: Decorators / Annotations. LCB attributes.
            "decorators": re.compile(r"^[ \t]*@(?:metadata|property|type|name|title)\b", re.M),
            # 20. generics: Generics / Type Parameters. (LCS is dynamically typed).
            "generics": None,
            # 21. comprehensions: Iterators / Comprehensions. Implicit list processing.
            "comprehensions": re.compile(
                r"\brepeat\s+for\s+each\s+(?:item|line|word|char|key|element)\b|\bfilter\s+[^ \t\n]+?\s+(?:with|without)\b",
                re.I,
            ),
            # 22. scientific: Numerical / Compute Libraries. Native math commands.
            "scientific": re.compile(
                r"\b(sqrt|exp|ln|log2|log10|sin|cos|tan|asin|acos|atan|atan2|abs|round|trunc|random|any|average|max|min)\b",
                re.I,
            ),
            # 23. heat_triggers: Metaprogramming & Reflection. Dynamic execution and path hijacking.
            "reflection_metaprogramming": re.compile(
                r"\b(do\s+|value\(|the\s+params|the\s+paramcount|evaluate\(|frontscripts|backscripts|insert\s+script)\b",
                re.I,
            ),
            # 24. import: Dependency Inclusions. Library and stack loading.
            "import": re.compile(r"\b(start\s+using\s+(?:stack|behavior)|require|include|module)\b", re.I),
            "_dependency_capture": re.compile(
                r"^[ \t]*(?:start[ \t\n]+using[ \t\n]+(?:stack[ \t\n]+|behavior[ \t\n]+)?|require[ \t\n]+|include[ \t\n]+|module[ \t\n]+)(?:['\"]([^'\"]+)['\"]|([^'\"\s]+))",
                re.I | re.M,
            ),
            # 25. ownership: Authorship metadata in comments.
            "ownership": re.compile(
                r"^[ \t]*(?:--|//|#)\s*(?:Author|Created by|Maintainer|Copyright):\s+([^\n]+)",
                re.I | re.M,
            ),
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            # 26. planned_debt: The Promise. Future work markers.
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt: The Fracture. Admitted fragility or hacks.
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            # 29. spec_exposure: Map vs. Territory. Audit tags.
            "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)\]", re.I),
            # 30. tabs_vs_spaces (Formatting Inconsistencies): Indentation Tracker. Tabs vs Spaces density.
            "tabs_vs_spaces": None,
            # 31. ssr_boundaries: View Horizon. Server-side rendering.
            "ssr_boundaries": re.compile(
                r"\b(<\?lc|\?>|\$_POST|\$_GET|\$_SERVER|\$_COOKIE|\$_SESSION|put\s+header)\b",
                re.I,
            ),
            # 32. events: Pub/Sub Network. Signal handlers and event brokers.
            "events": re.compile(
                r"^[ \t]*on\s+(?:mouseUp|mouseDown|openCard|closeCard|preOpenCard|openStack|closeStack|resizeStack|rawKeyDown|textChanged)\b",
                re.I | re.M,
            ),
            # 33. dependency_injection: Inversion of Control. Service locator patterns.
            "dependency_injection": re.compile(
                r"\b(?:set\s+the\s+behavior\s+of|start\s+using\s+(?:stack|behavior)|insert\s+script\s+into\s+(?:front|back))\b",
                re.I,
            ),
            # 34. macros: Preprocessor Hooks.
            "macros": None,
            # 35. pointers: Memory Map. Pass by reference in params.
            "pointers": re.compile(r"\b@[a-zA-Z_]\w*\b", re.I),
            # 36. memory_alloc: Manual Memory Management.
            "memory_alloc": None,
            # 37. inline_asm: Bare Metal.
            "inline_asm": None,
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # 38. telemetry: Professional diagnostics.
            "telemetry": re.compile(
                r"\b(revLog|syslog|logError|logInfo|logWarn|logDebug|mergLog|rreLog|lcLog)\b",
                re.I,
            ),
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs): Raw terminal output (puts to message box without target).
            "debug_prints": re.compile(r'^[ \t]*put\s+(?:"[^"]*"|[a-zA-Z0-9_]+)[ \t]*$', re.I | re.M),
            # 40. explicit_casts (Explicit Type Casting): English-style type checking.
            "explicit_casts": re.compile(r"\bis\s+(?:not\s+)?a\b|\bis\s+strictly\b", re.I),
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts): Hard detonations.
            "panics_and_aborts": re.compile(r"\b(exit\s+to\s+top|quit|throw|abort)\b", re.I),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses): Temporal Duct Tape (Blocking wait).
            "thread_sleeps": re.compile(r"\bwait\s+(?:for[ \t]+)?\d+\s+[^ \t\n]+?(?!\s+with\s+messages)\b", re.I),
            # 43. bitwise_ops (Bitwise Operations)
            "bitwise_ops": re.compile(r"\b(bitAnd|bitOr|bitXor|bitNot|bitShiftLeft|bitShiftRight)\b", re.I),
            # 44. sync_locks (Resource Management & Stability)
            "sync_locks": re.compile(r"\b(lock\s+screen|lock\s+messages|lock\s+errordialogs)\b", re.I),
            # 45. immutability_locks (Immutability Constraints)
            "immutability_locks": re.compile(r"\b(constant\s+)\b", re.I),
            # 46. cleanup (Resource Cleanup / Teardown)
            "cleanup": re.compile(
                r"\b(delete\s+variable|close\s+file|stop\s+using|remove\s+script)\b",
                re.I,
            ),
            # 47. encapsulation
            "encapsulation": re.compile(r"\b(private\s+)\b", re.I),
            # 48. listeners (Event Listeners / Observers)
            "listeners": re.compile(r"^[ \t]*on\s+[a-zA-Z0-9_-]+", re.I | re.M),
            # 49. test_skip (Bypassed Tests / Ignored Specs)
            "test_skip": re.compile(r"\b(skip\s+test)\b", re.I),
            # --- PHASE 3: HYBRID DOMAIN SENSORS (LiveCode Specifics) ---
            "serialization_parsing": re.compile(
                r"(?i)\b(jsonImport|jsonExport|arrayEncode|arrayDecode|revXMLCreateTree)\b"
            ),
            "regex_execution": re.compile(r"(?i)\b(matchText|matchChunk|replaceText|filter\s+.*\s+with\s+regex)\b"),
            "time_date_logic": re.compile(
                r"(?i)\b(the\s+(?:seconds|ticks|time|date|internet date)|wait\s+(?:for|until))\b"
            ),
            "ipc_rpc_bridges": re.compile(
                r"(?i)\b(open\s+socket|read\s+from\s+socket|post\s+.*to|get\s+url|shell\s*\(|open\s+process)\b"
            ),
        },
    },
    "solidity": {
        "_meta": {
            "target_version": "Solidity 0.8.20+ (Smart Contracts / Foundry / Hardhat)",
            "last_updated": "2026-04-01",
            "blueprint_version": "v6.3.2",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard Solidity contracts and library files.
        "extensions": [".sol"],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: Solidity compiles to EVM bytecode; no extensionless scripts exist.
        "exact_matches": [],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: Hardhat, Truffle, and Foundry configurations acting as gravitational anchors.
        "discriminators": [
            "hardhat.config.js",
            "hardhat.config.ts",
            "truffle-config.js",
            "foundry.toml",
            "remappings.txt",
        ],
        # EXECUTION SIGNATURES: Smart contracts are compiled; no shebangs exist.
        "shebangs": [],
        # UPGRADED: Maps to Family 1 (Standard C-Style)
        # Rationale: Solidity strictly adheres to C-style line (//) and block (/* */) comments.
        "lexical_family": "standard_block",
        "rules": {
            # --- LEXICAL DELIMITER CONTROLS ---
            "_line_anchor": re.compile(r"//"),
            "_inline_comment": re.compile(r"//"),
            "_block_start": re.compile(r"/\*"),
            "_block_end": re.compile(r"\*/"),
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # 1. branch: Decisions that split flow. Includes Solidity 0.6+ try/catch.
            "branch": re.compile(r"\b(if|else|for|while|do|break|continue|return|try|catch)\b|\?|:"),
            # 2. args: Parameters / Coupling. Captures parameters for functions, errors, events, and modifiers.
            # Bounded `{0,50}` to prevent ReDoS on massive tuple returns or complex signatures.
            "args": re.compile(
                r"\b(?:function|modifier|error|event|constructor)\s+(?:[a-zA-Z_]\w*[ \t]*)?\([^)]{0,500}\)"
            ),
            # 3. linear: Sequential I/O & Network Boundaries. Structural boundaries defining scope and data definitions.
            "structural_boundaries": re.compile(
                r"\b(pragma|import|contract|interface|library|struct|enum|type|mapping|address|uint\d*|int\d*|bytes\d*|bool|string)\b"
            ),
            # 4. func_start: Executable Logic Anchors. Anchors executable logic (Functions, Modifiers, Custom Errors, Events).
            # LOOKAHEAD MANDATE APPLIED: Stops exactly at the identifier name before the parenthesis.
            "func_start": re.compile(
                r"^[ \t]*(?:function|modifier|error|event)\s+([a-zA-Z_]\w*)(?=\s*\()",
                re.M,
            ),
            # 5. class_start: Object / Entity Declarations. Defines structural entities (Contracts, Interfaces, Libraries).
            "class_start": re.compile(
                r"^[ \t]*(?:abstract\s+)?(?:contract|interface|library)\s+([a-zA-Z_]\w*)(?=\s*(?:is|\{))",
                re.M,
            ),
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            # 6. safety: Defensive Programming. State reversion, assertions, and defensive modifier usage.
            "safety": re.compile(r"\b(require|assert|revert|modifier|nonReentrant|onlyOwner)\b"),
            # 7. safety_neg: Safety Bypasses. Bypassing overflow checks (0.8+) or dangerous delegation.
            "safety_bypasses": re.compile(r"\b(unchecked|assembly|delegatecall)\b"),
            # 8. danger: High-Risk Execution. Contract destruction and absolute value termination.
            "high_risk_execution": re.compile(r"\b(selfdestruct|suicide)\b"),
            # 9. io: I/O & Network Boundaries. EVM blockchains are closed systems. (Cross-contract calls are mapped as API/Generics).
            "io": None,
            # 10. api: Public Surface Area. Exposed boundaries to external wallets or contracts.
            "api": re.compile(r"\b(external|public)\b"),
            # 11. flux: State Mutation. State mutation. Captures array mutators, payable states, and explicit assignment.
            "state_mutation": re.compile(r"\b(payable|push|pop)\b|(?<![=<>!])=(?![=])|\+\+|--|\+=|-=|\*=|/="),
            # 12. dead_code (Commented Logic / Deprecated Trails) Commented out execution flow or structural definitions.
            "dead_code": re.compile(r"//[ \t]*(?:function|contract|if|require|uint|address)\b"),
            # 13. doc: Structured Documentation. NatSpec (Ethereum Natural Specification Format).
            "doc": re.compile(r"///|/\*\*|@(?:param|return|dev|notice|custom|title|author)"),
            # 14. test: Testing & Assertions. Foundry/Forge testing hooks and assertions.
            "test": re.compile(
                r"\b(?:setUp|test[A-Za-z0-9_]*|assertEq|assertTrue|assertFalse|assertGt|assertLt|vm\.expectRevert)\b"
            ),
            # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
            # 15. concurrency: Temporal Static. EVM execution is strictly synchronous per transaction.
            "concurrency": None,
            # 16. ui_framework: UI / View Components. Solidity has no UI rendering capacity.
            "ui_framework": None,
            # 17. closures: Closures / Anonymous Functions. Solidity lacks native closures/lambdas.
            "closures": None,
            # 18. globals: Global / Shared State. Global transaction, block, and message state context variables.
            "globals": re.compile(
                r"\b(msg\.(?:sender|value|data|sig)|block\.(?:timestamp|number|chainid|coinbase|difficulty)|tx\.(?:gasprice|origin))\b"
            ),
            # 19. decorators: Decorators / Annotations. Modifiers act structurally similar to decorators.
            "decorators": None,  # Modifiers are inline in Solidity, not on preceding lines.
            # 20. generics: Generics / Type Parameters. Parameterized K/V associations.
            # Deeply supports nested mapping structures across vertical lines.
            "generics": re.compile(
                r"\bmapping\s*\([ \t\n]*[a-zA-Z0-9_]+\s*=>\s*(?:mapping\s*\([^)]+\)|[a-zA-Z0-9_]+)[ \t\n]*\)"
            ),
            # 21. comprehensions: Iterators / Comprehensions. Solidity lacks native comprehensions.
            "comprehensions": None,
            # 22. scientific: Numerical / Compute Libraries. Cryptographic hashing and elliptic curve recovery.
            "scientific": re.compile(r"\b(keccak256|sha256|ripemd160|ecrecover|addmod|mulmod)\b"),
            # 23. heat_triggers: Metaprogramming & Reflection. Low-level assembly injections and fallback routers.
            "reflection_metaprogramming": re.compile(r"\b(fallback|receive|assembly|delegatecall|call|staticcall)\b"),
            # 24. import: Dependency Inclusions. Resolving dependencies across files.
            "import": re.compile(r"^[ \t]*import\s+(?:\{[^}]+\}\s+from\s+)?[\"'][^\"']+[\"'];", re.M),
            # 24b. _dependency_capture: Graph resolution extracting exactly ONE path string.
            "_dependency_capture": re.compile(r"^[ \t]*import\s+(?:\{[^}]+\}\s+from\s+)?[\"']([^\"']+)[\"'];", re.M),
            # 25. ownership: Authorship indicators. Strictly targets SPDX license tags and authorship notes.
            "ownership": re.compile(r"//[ \t]*SPDX-License-Identifier:|(?:@author|Created by):\s+(.*)", re.I),
            # --- 🌌 PHASE 4: EXTENDED DIMENSIONS (Specialized Sub-Equations) ---
            # 26. planned_debt (Annotated Debt / TODOs)
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            # 28. private_info: Hardcoded credentials or private keys. Requires assignment.
            "hardcoded_secrets": re.compile(r"\b(private_key|secret|mnemonic|api_key)\b[ \t]*[:=]", re.I),
            # 29. spec_exposure: Map vs. Territory. ERC/EIP standards and audit tags.
            "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|audit)[^\]]*\]|\b(ERC-\d+|EIP-\d+)\b", re.I),
            # 30. tabs_vs_spaces (Formatting Inconsistencies): Indentation Tracker. Handled natively.
            "tabs_vs_spaces": None,
            # 31. ssr_boundaries: View Horizon.
            "ssr_boundaries": None,
            # 32. events: Pub/Sub Network. Logging state to the blockchain EVM logs.
            "events": re.compile(r"\b(emit|event)\b"),
            # 33. dependency_injection: Inversion of Control.
            "dependency_injection": None,
            # 34. macros: Preprocessor Hooks. (Solidity lacks macros).
            "macros": None,
            # 35. pointers: Memory Map. Explicit storage vs memory pointer semantics.
            "pointers": re.compile(r"\b(memory|storage|calldata)\b"),
            # 36. memory_alloc: Explicit heap generation inside arrays or structs.
            "memory_alloc": re.compile(r"\b(new)\b"),
            # 37. inline_asm: Bare Metal Yul integration.
            "inline_asm": re.compile(r"\bassembly\s*\{"),
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # 38. telemetry: Professional diagnostics. (Hardhat console logging).
            "telemetry": re.compile(r"\b(console\.log[a-zA-Z0-9_]*)\b"),
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs): Standard output. (Solidity lacks native printing outside Hardhat).
            "debug_prints": None,
            # 40. explicit_casts (Explicit Type Casting)
            "explicit_casts": re.compile(r"\b(address|uint\d*|int\d*|bytes\d*|uint|int|bytes)\s*\("),
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts) Aborting transaction state.
            "panics_and_aborts": re.compile(r"\b(revert)\b"),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses) (EVM cannot sleep).
            "thread_sleeps": None,
            # 43. bitwise_ops (Bitwise Operations) Bitwise operations for gas optimization.
            "bitwise_ops": re.compile(r"<<|>>|\^|~|(?<!&)&(?!&)|(?<!\|)\|(?!\|)"),
            # 44. sync_locks (Resource Management & Stability) Native Reentrancy guards.
            "sync_locks": re.compile(r"\b(nonReentrant)\b"),
            # 45. immutability_locks (Immutability Constraints) Gas-saving immutability constraints.
            "immutability_locks": re.compile(r"\b(constant|immutable|view|pure)\b"),
            # 46. cleanup (Resource Cleanup / Teardown) Deleting state variables to claim gas refunds.
            "cleanup": re.compile(r"\b(delete)\b"),
            # 47. encapsulation Access limitation to prevent external calls.
            "encapsulation": re.compile(r"\b(private|internal)\b"),
            # 48. listeners (Event Listeners / Observers) (Contracts cannot actively listen asynchronously).
            "listeners": None,
            # 49. test_skip (Bypassed Tests / Ignored Specs)
            "test_skip": None,
            # --- PHASE 3: HYBRID DOMAIN SENSORS (Solidity Specifics) ---
            "serialization_parsing": re.compile(r"\b(abi\.encode|abi\.encodePacked|abi\.decode)\b"),
            "regex_execution": re.compile(
                r"\b(keccak256\s*\(\s*abi\.encodePacked)\b"
            ),  # Hashes are used instead of regex for complex string matching
            "time_date_logic": re.compile(r"\b(block\.timestamp|now|\d+\s+(?:days|weeks|years|hours|minutes))\b"),
            "ipc_rpc_bridges": re.compile(r"\b(delegatecall|staticcall|\.call\{value:|emit\s+[A-Z]|selfdestruct)\b"),
        },
    },
    "objective-c": {
        "_meta": {
            "target_version": "Objective-C 2.0 (ARC) & Modern Runtime",
            "last_updated": "2026-02-18",
            "blueprint_version": "v5.0",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard sources, Objective-C++ files (.mm), and shared C/C++ headers.
        "extensions": [".m", ".mm", ".h"],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: Objective-C executes natively on Apple platforms; no extensionless configurations exist.
        "exact_matches": [],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: The ultimate defense against MATLAB. Apple UI components and Xcode project files act as massive gravity anchors.
        "discriminators": [
            ".m",
            ".mm",
            "project.pbxproj",
            ".storyboard",
            ".xib",
            ".xcworkspace",
            "Podfile",
            "Cartfile",
        ],
        # EXECUTION SIGNATURES: Compiled natively via LLVM/Clang; no shebangs exist.
        "shebangs": [],
        "internal_discriminator": re.compile(
            r'^[ \t]*#import\s+[<"][^>"]+\.h[>"]|'
            r"^[ \t]*@(?:interface|implementation|protocol|property|class)\b",
            re.M,
        ),
        # UPGRADED: Maps to Family 1 (Standard C-Style)
        # Rationale: Uses standard '//' for line-level literature and '/*' '*/' for blocks.
        "lexical_family": "standard_block",
        "rules": {
            # --- LEXICAL DELIMITER CONTROLS ---
            "_line_anchor": re.compile(r"//"),
            "_inline_comment": re.compile(r"//"),
            "_block_start": re.compile(r"/\*"),
            "_block_end": re.compile(r"\*/"),
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # 1. branch: Decisions that split flow. Includes Obj-C specific @try/@catch blocks.
            "branch": re.compile(
                r"\b(if|else|switch|case|default|for|while|do|break|continue|return|goto|@try|@catch|@finally)\b|&&|\|\||\?"
            ),
            # 2. args: Parameters / Coupling. Captures method parameters (colons), C-style args, and Blocks (^).
            "args": re.compile(
                # =====================================================================
                # [ THE GHOST ARGS & BLOCK SHIELD (OBJECTIVE-C) ]
                # Objective-C functions look like standard C functions. The previous regex
                # `\b[a-zA-Z_]\w*\s*\([^)]*\)\s*(?:\{|;)` hallucinated `if (a) {` as a function.
                # FIX: Injected `(?!(?:if|for|while|switch|catch|return)\b)` to block control flow.
                # =====================================================================
                r":\s*\([^)]+\)\s*[a-zA-Z_]\w*|\^[ \t]*(?:[a-zA-Z_]\w*\s*)?\([^)]*\)|(?!(?:if|for|while|switch|catch|return)\b)\b[a-zA-Z_]\w*[ \t\n]*\([^)]*\)[ \t\n]*(?:\{|;)",
                re.M,
            ),
            # 3. linear: Sequential I/O & Network Boundaries. Structural boundaries defining interface, implementation, and memory types.
            "structural_boundaries": re.compile(
                r"\b(@interface|@implementation|@protocol|@end|@synthesize|@dynamic|@class|@import|typedef|struct|enum|union|__block|__weak|__strong)\b"
            ),
            # 4. func_start: Executable Logic Anchors. Anchors executable logic.
            # The Critical Fix: Compiled with re.M and optional return types for TBL / NeXTSTEP syntax
            "func_start": re.compile(
                # =====================================================================
                # [ THE VERTICAL RETURN TYPE SHIELD (OBJECTIVE-C) ]
                # Objective-C developers (and macros) can fragment the method sign `-`,
                # the return type `(NSDictionary *)`, the name, and the colon `:`
                # across multiple lines.
                # FIX: `\s*` already covers newlines in the prefix, but the trailing
                # positive lookahead `(?=[ \t]*[:\{;])` blocked newlines before the colon.
                # Upgraded the lookahead to `(?=[ \t\n]*[:\{;]|$)` to clear the vertical gap.
                # =====================================================================
                r"^[ \t]*[-+][ \t\n]*(?:\([^)]+\))?[ \t\n]*([a-zA-Z_]\w*)(?=[ \t\n]*[:\{;]|$)|"
                r"^[ \t]*(?:static[ \t\n]+|inline[ \t\n]+)?(?:[a-zA-Z_]\w*(?:[ \t\n]*\*+)?[ \t\n]+)+([a-zA-Z_]\w*)(?=[ \t\n]*\()",
                re.M,
            ),
            # 5. class_start: Object / Entity Declarations. Defines OO boundaries.
            "class_start": re.compile(
                r"^[ \t]*(?:@interface|@implementation|@protocol)\s+([a-zA-Z_]\w*)(?=[ \t]*[:(<{\n]|$)",
                re.M,
            ),
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            # 6. safety: Defensive Programming. ARC memory qualifiers and Cocoa/NeXT Assertions.
            "safety": re.compile(
                r"\b(@try|@catch|@finally|__weak|__strong|__auto_type|NSAssert|NSParameterAssert|NSError|nil|Nil)\b"
            ),
            # 7. safety_neg: Safety Bypasses. Bypassing ARC, raw void pointers, and dangerous dynamic selectors.
            "safety_bypasses": re.compile(
                r"\b(__unsafe_unretained|unsafe_unretained|id|void\s*\*|performSelector:|performSelector:withObject:)\b|!\s*[;,\]\)\.]|#pragma\s+clang\s+diagnostic\s+ignored"
            ),
            # 8. danger: High-Risk Execution. Process killers.
            "high_risk_execution": re.compile(r"\b(abort|exit)\b"),
            # 9. io: I/O & Network Boundaries. Disk, Network, and URL fetching (Includes NeXTSTEP NX prefixes & TBL WWW wrappers).
            "io": re.compile(
                r"\b(NSFileHandle|NSFileManager|NSURLSession|NSURLConnection|NSData|NXNetPath|NXSocket|NXStream|NXFile|HTLoad|HyperText|HTGet|socket|connect|send|recv)\b"
            ),
            # 10. api: Public Surface Area. Exposed interface/C-level exports and Interface Builder hooks.
            "api": re.compile(r"\b(FOUNDATION_EXPORT|UIKIT_EXTERN|OBJC_EXPORT|extern)\b|@property|IBOutlet|IBAction"),
            # 11. flux: State Mutation. State mutation (Property setters and raw assignments).
            "state_mutation": re.compile(r"\b(?:self\.)?[a-zA-Z_]\w*[ \t]*=|\[self\s+set[A-Z]\w*:|(?:\+\+|--)"),
            # 12. dead_code (Commented Logic / Deprecated Trails) Commented out structural code.
            "dead_code": re.compile(
                r"//[ \t]*(?:@interface|@implementation|\[|if|NSLog|- \()|/\*[ \t]*(?:@interface|@implementation|\[|if|NSLog|- \()"
            ),
            # 13. doc: Structured Documentation. Structured documentation (Includes NeXT style).
            "doc": re.compile(r"/\*\*|///|/\*!|@param|@return|@brief|@discussion"),
            # 14. test: Testing & Assertions. Unit testing framework markers (OCUnit/XCTest).
            "test": re.compile(
                r"\b(XCTest|XCTestCase|XCTAssert[A-Za-z]*|SenTestCase|STAssert[A-Za-z]*)\b|\b(?:setUp|tearDown)\s*\("
            ),
            # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
            # 15. concurrency: Temporal Static. GCD (Grand Central Dispatch), NSOperation, and Locks.
            "concurrency": re.compile(
                r"\b(dispatch_async|dispatch_sync|dispatch_once|dispatch_queue_t|NSOperation|NSThread|@synchronized|NSLock|NXConditionLock)\b"
            ),
            # 16. ui_framework: UI / View Components. Cocoa, UIKit, and AppKit hierarchies (Includes legacy NX classes).
            "ui_framework": re.compile(
                r"\b(UIView|UIViewController|UIWindow|NSView|NSWindow|NXWindow|NXApp|NXBrowser|NXText|Text|ScrollView|HyperText|WorldWideWeb|SGML)\b"
            ),
            # 17. closures: Closures / Anonymous Functions. Objective-C Blocks.
            "closures": re.compile(r"\^[ \t]*(?:[a-zA-Z_]\w*\s*)?\s*\([^)]*\)[ \t]*\{"),
            # 18. globals: Global / Shared State. Singleton/Shared instance access.
            "globals": re.compile(
                r"\b(extern|NSUserDefaults|NXDefaults|\[UIApplication\s+sharedApplication\]|\[NSWorkspace\s+sharedWorkspace\]|NXApp)\b"
            ),
            # 19. decorators: Decorators / Annotations. Attributes and Property decorators.
            "decorators": re.compile(r"\b__attribute__\s*\(\([^)]*\)\)|@property\s*\([^)]+\)"),
            # 20. generics: Generics / Type Parameters. Lightweight generics (introduced in Xcode 7).
            "generics": re.compile(r"<\s*[A-Z][^>]*\s*\*?\s*>"),
            # 21. comprehensions: Iterators / Comprehensions. Block-based array/set enumeration.
            "comprehensions": re.compile(
                r"\b(enumerateObjectsUsingBlock:|filteredArrayUsingPredicate:|makeObjectsPerformSelector:)\b"
            ),
            # 22. scientific: Numerical / Compute Libraries. C-Math and CoreGraphics structs.
            "scientific": re.compile(
                r"\b(math\.h|sin|cos|tan|sqrt|exp|log|abs|NSDecimalNumber|CGVector|CGAffineTransform|CGPoint|CGRect|CGSize|NXRect|NXSize)\b"
            ),
            # 23. heat_triggers: Metaprogramming & Reflection. Objective-C Runtime Swizzling and dynamic messaging.
            "reflection_metaprogramming": re.compile(
                r"\b(objc_msgSend|performSelector|method_exchangeImplementations|class_addMethod|objc_allocateClassPair|isa|object_setClass)\b|<objc/runtime\.h>"
            ),
            # 24. import: Dependency Inclusions. Module and header inclusion.
            "import": re.compile(r"^[ \t]*(?:#import|#include|@import)\b", re.M),
            "_dependency_capture": re.compile(
                r"^[ \t]*(?:#import|#include)\s*(?:<([^>]+)>|[\"']([^\"']+)[\"'])|^[ \t]*@import\s+([\w.]+)",
                re.M,
            ),
            # 25. ownership: Authorship metadata.
            "ownership": re.compile(r"\b(?:Created by|@author|Author:|Copyright|Tim Berners-Lee)\b", re.I),
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            "planned_debt": GLOBAL_PLANNED_DEBT,
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            "spec_exposure": re.compile(
                r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit|RFC|W3C|CERN|TBL|ENQUIRE)[^\]]*\]|\b(?:WorldWideWeb|HyperText\s+Proposal|NeXTSTEP\s+Docs)\b",
                re.I,
            ),
            "tabs_vs_spaces": None,
            "ssr_boundaries": re.compile(
                r"\b(WOComponent|WOResponse|WOContext|WOApplication|WODirectAction|WebObjects)\b"
            ),
            "events": re.compile(r"\b(NSNotificationCenter|addObserver|postNotification|NXApp\s+run|sendEvent)\b"),
            "dependency_injection": re.compile(
                r"\b(TyphoonComponentFactory|TyphoonDefinition|JSObjection|inject:|initWithDependency:)\b"
            ),
            "macros": re.compile(
                r"^[ \t]*#(?:define|undef|ifdef|ifndef|if|elif|else|endif|pragma)\b",
                re.M,
            ),
            "pointers": re.compile(r"->|&\w+|\b(?:id|Class|SEL|IMP)\b|(?<=[=(,])[ \t]*\*[a-zA-Z_]\w*"),
            "memory_alloc": re.compile(
                r"\b(alloc|init|new|copy|mutableCopy|retain|malloc|calloc|NX_MALLOC|NX_ZONEMALLOC|NSZoneMalloc)\b"
            ),
            "inline_asm": re.compile(r"\b(?:__asm__|asm|__asm)\b(?:\s+volatile)?\s*\([^)]*\)"),
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # 38. telemetry: Professional diagnostics.
            "telemetry": re.compile(r"\b(os_log|OSLog|DDLogInfo|DDLogError|DDLogWarn|DDLogDebug|syslog)\b"),
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs): Standard output.
            "debug_prints": re.compile(r"\b(printf|fprintf|NXPrintf|NSLog)\b"),
            # 40. explicit_casts (Explicit Type Casting): "Trust Me" Tax. Explicit type coercion.
            "explicit_casts": re.compile(r"\(\s*[A-Za-z_]\w*\s*\*?\s*\)\s*[a-zA-Z_$]|typeof\b"),
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts) Aborting execution context.
            "panics_and_aborts": re.compile(r"\b(@throw|abort|exit)\b"),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses) Forcing threads to sleep.
            "thread_sleeps": re.compile(r"\b(sleep|usleep|nanosleep)\s*\("),
            # 43. bitwise_ops (Bitwise Operations)
            "bitwise_ops": re.compile(r"(?<!&)&(?!&)|(?<!\|)\|(?!\|)|<<|>>|\^|~"),
            # 44. sync_locks (Resource Management & Stability) Coordinated threading logic.
            "sync_locks": re.compile(
                r"\b(@synchronized|NSLock|NSRecursiveLock|NSConditionLock|dispatch_semaphore_wait)\b"
            ),
            # 45. immutability_locks (Immutability Constraints) Immutability.
            "immutability_locks": re.compile(r"\b(const|readonly|immutable)\b"),
            # 46. cleanup (Resource Cleanup / Teardown) Resource release (Crucial for MRC NeXT era).
            "cleanup": re.compile(r"\b(dealloc|release|autorelease|free|NX_FREE)\b"),
            # 47. encapsulation Hiding logic from the application.
            "encapsulation": re.compile(r"\b(@private|@protected|@package)\b"),
            # 48. listeners (Event Listeners / Observers) Waiting for state broadcasts.
            "listeners": re.compile(r"\b(addObserver:|observeValueForKeyPath:|subscribeNext:)\b"),
            # 49. test_skip (Bypassed Tests / Ignored Specs)
            "test_skip": re.compile(r"\b(XCTSkip|xit|xdescribe)\b"),
            # --- PHASE 3: HYBRID DOMAIN SENSORS (Objective-C Specifics) ---
            "serialization_parsing": re.compile(
                r"\b(NSJSONSerialization|NSKeyedUnarchiver|NSKeyedArchiver|NSXMLParser|NSPropertyListSerialization)\b"
            ),
            "regex_execution": re.compile(r"\b(NSRegularExpression|NSRegularExpressionSearch)\b"),
            "time_date_logic": re.compile(
                r"\b(NSDate|NSDateFormatter|NSTimer|CFAbsoluteTimeGetCurrent|NSDateComponents)\b"
            ),
            "ipc_rpc_bridges": re.compile(
                r"\b(NSXPCConnection|NSTask|NSPipe|NSURLConnection|NSURLSession|NSMachPort)\b"
            ),
        },
    },
    "makefile": {
        "_meta": {
            "target_version": "GNU Make 4.4+",
            "last_updated": "2026-02-28",
            "blueprint_version": "v6.2.2",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard make extensions, definitions, and includes.
        "extensions": [".mk", ".mak", ".make", ".def"],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: The universally recognized, extensionless build configurations that are executed as pure code.
        "exact_matches": [
            "Makefile",
            "makefile",
            "GNUmakefile",
            "Kbuild",
            "Makeconf",
            "Makevars",
        ],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: Sibling configurations acting as disambiguation anchors to resolve ambiguous .mk includes.
        "discriminators": ["Makefile", "makefile", "configure.ac", "CMakeLists.txt"],
        # EXECUTION SIGNATURES: Interpreters found on Line 1 for executable make scripts.
        "shebangs": ["make", "gmake"],
        # UPGRADED: Maps to Family 3 (Pure Hash)
        # Rationale: Make natively uses '#' exclusively for line-level comments.
        "lexical_family": "line_exclusive",
        "rules": {
            # Makefiles natively use '#' for both line and inline comments.
            "_line_anchor": re.compile(r"#"),
            "_inline_comment": re.compile(r"#"),
            # EXPLICIT: Makefiles lack native multi-line block comment delimiters.
            "_block_start": None,
            "_block_end": None,
            # --------------------------------------------------------------------------
            # 1. GEOMETRY & SHAPE (Geometry & Shape)
            # --------------------------------------------------------------------------
            # Captures Make conditionals and typical inline shell conditional branches.
            "branch": re.compile(
                r"^[ \t]*(?:ifeq|ifneq|ifdef|ifndef|else|endif)\b|\b(?:if|elif|for|while|case)\b|&&|\|\|",
                re.M,
            ),
            # Make dynamically accesses arguments within $(call macro, args...) or positional $1, $2 inside recipes.
            "args": re.compile(r"\$\([0-9]+\)|\$[0-9]\b|\$\(call[ \t]+[a-zA-Z0-9_.-]+"),
            # Smooth structural boundaries: variable assignments (:=, =, ?=) and native structural controls like vpath.
            # Explicitly excludes the append operator `+=` which belongs in flux.
            "structural_boundaries": re.compile(
                r"^[ \t]*[a-zA-Z0-9_.-]+[ \t]*(?::|\?|::)?=(?![ \t]*=)|^[ \t]*(?:vpath|undefine)\b",
                re.M,
            ),
            # 4. func_start (Executable Logic Anchors)
            # Strict capture group and positive lookahead applied for both Obj-C methods and C-functions.
            "func_start": re.compile(
                r"^[ \t]*(?!\.(?:PHONY|POSIX|SECONDARY|PRECIOUS|DELETE_ON_ERROR|KEEP_STATE|NOTPARALLEL|WAIT|SILENT|EXPORT_ALL_VARIABLES|IGNORE|SUFFIXES|DEFAULT|PRECIOUS|INTERMEDIATE|SECONDARY|SECONDEXPANSION)\b)"
                r"([a-zA-Z0-9_./%-]+)(?=[ \t]*::?)",
                re.M,
            ),
            # 5. class_start (Object / Entity Declarations)
            # Defines OO boundaries. Strict capture group and positive lookahead applied.
            "class_start": None,
            # --------------------------------------------------------------------------
            # 2. STRUCTURAL INTEGRITY & TECH DEBT (Structural Integrity & Tech Debt)
            # --------------------------------------------------------------------------
            # Defensive programming: Executing internal logic checks, asserting tool paths, or using safety system states.
            "safety": re.compile(
                r"^[ \t]*\.(?:POSIX|SECONDARY|PRECIOUS|DELETE_ON_ERROR|KEEP_STATE)\b|\bcommand[ \t]+-v\b|\$\((?:if|or|and)[ \t]+",
                re.M,
            ),
            # Bypassing safety: Prefixing recipes with `-` to swallow errors, or forcefully exiting true via shell logic.
            "safety_bypasses": re.compile(r"^\t[ \t]*-[a-zA-Z0-9_./$]|\|\|[ \t]*(?:true|exit[ \t]+0)\b", re.M),
            # Heavily destructive sequence patterns or overriding permissions. (Eval is categorized under heat_triggers).
            "high_risk_execution": re.compile(r"\bsudo[ \t]+|\brm[ \t]+-[rR]?[fF][ \t]+(?:/|\$[{(])|\bkill[ \t]+-9\b"),
            # Interacting directly with outputs, networks, or the disk filesystem.
            "io": re.compile(
                r"\$\((?:file|wildcard)[ \t]+|\b(?:curl|wget|scp|rsync|tar|unzip|mkdir|cp|mv)\b|>>?[ \t]*[^ \t\n/]+"
            ),
            # Exposed architecture limits (Exporting variables globally or explicit lifecycle public endpoints).
            "api": re.compile(
                r"^[ \t]*(?:\.PHONY|export\b|(?:all|install|build|clean|test|run)[ \t]*::?)",
                re.M,
            ),
            # Mutating variable state by appending (+=) or shell assignment (!=). .
            "state_mutation": re.compile(r"^[ \t]*[a-zA-Z0-9_.-]+[ \t]*(?:\+|!)=", re.M),
            # Commented-out targets, commented out shell logic, or commented conditional Make directives.
            "dead_code": re.compile(
                r"^[ \t]*#[ \t]*(?:[a-zA-Z0-9_./%-]+[ \t]*::?|[a-zA-Z0-9_.-]+[ \t]*(?::|\?|::)?=|\b(?:ifeq|ifneq|ifdef|ifndef|include)\b)",
                re.M,
            ),
            # Structured self-documenting makefile comments typically utilizing a double hash block.
            "doc": re.compile(r"^[ \t]*##[ \t]+[^ \t\n]+", re.M),
            # Testing endpoints natively executing verifications or launching language-specific test suites.
            "test": re.compile(
                r"\b(?:npm[ \t]+test|yarn[ \t]+test|pytest|go[ \t]+test|cargo[ \t]+test|make[ \t]+test)\b",
                re.M | re.I,
            ),
            # --------------------------------------------------------------------------
            # 3. DOMAIN & ARCHITECTURE (Architectural Style and Abstractions)
            # --------------------------------------------------------------------------
            # Setting explicitly threaded job pipelines, detaching processes to background, or asserting waits.
            "concurrency": re.compile(
                r"\b(?:make[ \t]+-j|xargs[ \t]+-P|wait)\b|&[ \t]*$|\$\(MAKE\)[ \t]+-j",
                re.M,
            ),
            "ui_framework": None,
            "closures": None,
            # Core global state built-in environments spanning the build system.
            "globals": re.compile(r"\$\((?:MAKE|MAKEFLAGS|MAKECMDGOALS|CURDIR|SHELL|PATH|USER|HOME|PWD|\.VARIABLES)\)"),
            "decorators": None,
            "generics": None,
            # High-density text manipulating algorithms native to GNU Make iterating through variable spaces.
            "comprehensions": re.compile(
                r"\$\((?:foreach|filter|filter-out|patsubst|subst|addprefix|addsuffix|words|firstword|lastword|sort|findstring|join)[ \t]+"
            ),
            # Launching explicit calculation boundaries outside the Make environment natively.
            "scientific": re.compile(r"\b(?:bc|expr|awk)\b|\$\(shell[ \t]+expr[ \t]+"),
            # Extremely dense meta-programming manipulations drastically raising cognitive load during debugging.
            "reflection_metaprogramming": re.compile(r"\$\((?:eval|call|value|origin|flavor|shell)[ \t]+|\.SECONDEXPANSION:"),
            # Linking isolated segments of the graph execution via modular file resolution.
            "import": re.compile(r"^[ \t]*-?(?:include|sinclude)[ \t]+[^ \t\n]+", re.M),
            "_dependency_capture": re.compile(r"^[ \t]*-?(?:include|sinclude)[ \t\n]+([^\s#]+)", re.M),
            # Metadata anchoring authorship and structural domain owners.
            "ownership": re.compile(
                r"^[ \t]*#[ \t]*(?:@author\b|author:|maintainer:|created by:)",
                re.I | re.M,
            ),
            # --------------------------------------------------------------------------
            # 4. SPECIALIZED EXTRACTIONS (Sub-Equations and Low-Level/System)
            # --------------------------------------------------------------------------
            # 26. planned_debt (Annotated Debt / TODOs)
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            "spec_exposure": re.compile(r"\[(?:spec-[0-9]+|audit|spec)\]", re.I),
            # Strict tracking of Indentation structural boundaries. (Make strictly demands Tabs, mapping space usage catches severe fragmentation).
            "tabs_vs_spaces": None,
            "ssr_boundaries": None,
            "events": None,
            "dependency_injection": None,
            # Expanding structural blocks dynamically into recipes prior to runtime evaluation.
            "macros": re.compile(r"^[ \t]*define[ \t]+[a-zA-Z0-9_.-]+", re.M),
            "pointers": None,
            "memory_alloc": None,
            "inline_asm": None,
            # --------------------------------------------------------------------------
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # --------------------------------------------------------------------------
            # Emitting pure, safe structural observability that does not risk halting or crashing the graph execution.
            "telemetry": re.compile(r"\$\(info[ \t]+[^)\n]*\)"),
            # Standard output commands echoing transient debris to the shell execution log.
            "debug_prints": re.compile(r"^[ \t]*@?(?:echo|printf)[ \t]+|\$\(warning[ \t]+[^)\n]*\)", re.M),
            "explicit_casts": None,
            # System detonators specifically intended to abort the build flow if preconditions are failed natively or via shell.
            "panics_and_aborts": re.compile(r"\$\(error[ \t]+[^)\n]*\)|\bexit[ \t]+[1-9][0-9]*\b|\bfalse\b"),
            # Temporal duct tape strictly applying forced pausing.
            "thread_sleeps": re.compile(r"\bsleep[ \t]+[0-9]+"),
            "bitwise_ops": None,  # Kept null as Bash pipe IPC limits logic math precision.
            # Explicit locks halting temporal thread races. .
            "sync_locks": re.compile(r"^[ \t]*\.(?:NOTPARALLEL|WAIT)[ \t]*::?|\bflock[ \t]+", re.M),
            # Enforcing strict immutability bounds on state configuration. .
            "immutability_locks": re.compile(r"^[ \t]*override[ \t]+[a-zA-Z0-9_.-]+", re.M),
            # Janitor routines ripping apart build artifacts and cleanly tearing down output paths. .
            "cleanup": re.compile(r"^[ \t]*(?:dist)?clean[ \t]*::?|\brm[ \t]+-[a-zA-Z]*f[a-zA-Z]*\b", re.M),
            # The Vault explicitly hiding scope logic away from external API leakage boundaries. .
            "encapsulation": re.compile(
                r"^[ \t]*(?:unexport[ \t]+[a-zA-Z0-9_.-]+|[a-zA-Z0-9_.-]+[ \t]*:[ \t]*private[ \t]+|\.SILENT[ \t]*:)",
                re.M,
            ),
            # Subscribing the file system to continuous native observation hooks.
            "listeners": re.compile(r"\b(?:inotifywait|watch)[ \t]+"),
            # Safety theater actively bypassing execution verifications during a test endpoint invocation.
            "test_skip": re.compile(
                r"\b(?:SKIP(?:_TESTS?)?|XFAIL)[ \t]*=[ \t]*[1TtYy]|\bpytest[ \t]+-k[ \t]+not\b|--skip",
                re.I,
            ),
            # --- PHASE 3: HYBRID DOMAIN SENSORS (Makefile Specifics) ---
            "serialization_parsing": re.compile(r"(?m)^\s*(?:@|-)?(?:tar|unzip|gunzip|jq|sed|awk)\b"),
            "regex_execution": re.compile(r"(?m)\$\((?:filter|filter-out|patsubst)\b|^\s*(?:@|-)?(?:grep|egrep|sed)\b"),
            "time_date_logic": re.compile(r"(?m)\$\(shell\s+date\b|^\s*(?:@|-)?(?:sleep|date)\b"),
            "ipc_rpc_bridges": re.compile(r"(?m)\$\(shell\b|^\s*(?:@|-)?(?:curl|wget|ssh|scp|docker|kubectl)\b"),
        },
    },
    "abap": {
        "_meta": {
            "target_version": "ABAP 2025 (ABAP Cloud / RAP / Modern 7.5x+ Syntax)",
            "last_updated": "2026-02-18",
            "blueprint_version": "v5.0",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard Advanced Business Application Programming sources and modern Core Data Services.
        "extensions": [".abap", ".asddls"],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: ABAP is executed within the SAP environment; no extensionless exact configurations exist.
        "exact_matches": [],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: SAP deployment artifacts acting as disambiguation anchors.
        "discriminators": [".abap", "package.devc.xml", ".apc"],
        # EXECUTION SIGNATURES: Executed exclusively within the SAP NetWeaver/ABAP platform; no shebangs exist.
        "shebangs": [],
        # UPGRADED: Maps to Family 7 (The Positional Ancients)
        # Rationale: Strictly fixed-format legacy constraints. The engine must monitor Column 1
        # for an asterisk '*' to identify line-level Commented / Non-Executable Text, while allowing '"' for inline.
        "lexical_family": "positional_anchored",
        "rules": {
            "_line_anchor": re.compile(r"^\*"),
            "_inline_comment": re.compile(r"\""),
            "_block_start": None,  # ABAP has no standard multi-line block comments
            "_block_end": None,
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # 1. branch: decisions that split flow. Includes modern COND/SWITCH expressions.
            "branch": re.compile(
                r"^[ \t]*(IF|ELSE|ELSEIF|CASE|WHEN|WHILE|DO|LOOP\s+AT|TRY|CATCH|CLEANUP|CHECK|EXIT|CONTINUE|RETURN|COND|SWITCH)\b",
                re.I | re.M,
            ),
            # 2. args: Parameters / Coupling. Captures explicit parameter binding keywords.
            "args": re.compile(
                r"\b(IMPORTING|EXPORTING|CHANGING|RETURNING|RECEIVING|EXCEPTIONS)\s+(?:VALUE\s*\([^)]*\)[ \t]+)?[a-zA-Z_][a-zA-Z0-9_-]*",
                re.I,
            ),
            # 3. linear: Sequential I/O & Network Boundaries. Structural boundaries. EXCLUDES access modifiers and constants.
            "structural_boundaries": re.compile(
                r"^[ \t]*(DATA|TYPES|FIELD-SYMBOLS|CLASS|INTERFACE|METHOD|FORM|FUNCTION|MODULE|REPORT|PROGRAM|IMPORT|EXPORT)\b",
                re.I | re.M,
            ),
            # 4. func_start: Executable Logic Anchors. Anchors executable logic. EXCLUDES structural headers.
            "func_start": re.compile(
                r"^[ \t]*(?!(?:CLASS|INTERFACE|DATA|TYPES|CONSTANTS)\b)(?:METHOD|FORM|FUNCTION|MODULE)\s+([a-zA-Z0-9_~-]+)(?=[ \t\n\.]|$)",
                re.I | re.M,
            ),
            # 5. class_start: Object / Entity Declarations. Defines OO boundaries and RAP CDS Entities.
            "class_start": re.compile(
                r"^[ \t]*(?:CLASS|INTERFACE)\s+([a-zA-Z0-9_-]+)(?=[ \t]+DEFINITION|[ \t\n\.]|$)|^[ \t]*DEFINE\s+(?:ROOT[ \t]+)?(?:VIEW|ENTITY|PROJECTION\s+VIEW|BEHAVIOR)\s+([a-zA-Z0-9_-]+)",
                re.I | re.M,
            ),
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            # 6. safety: Defensive Programming. Binding checks and authorization boundaries.
            "safety": re.compile(
                r"\b(TRY|CATCH|CLEANUP|ASSERT|AUTHORITY-CHECK|IS\s+BOUND|IS\s+ASSIGNED|IS\s+NOT\s+INITIAL|FINAL|READ-ONLY)\b",
                re.I,
            ),
            # 7. safety_neg: Safety Bypasses. Actively bypassing safety (casting/unchecked generics).
            "safety_bypasses": re.compile(
                r"\b(UNASSIGNED|TYPE\s+ANY|TYPE\s+REF\s+TO\s+DATA|IGNORE\s+ERRORS)\b|ASSIGN\s+[^\n;]+\s+TO\s+<[^>]+>\s+CASTING",
                re.I,
            ),
            # 8. danger: High-Risk Execution. Raw SQL/Kernel bypasses and mass deletion.
            "high_risk_execution": re.compile(
                r"\b(SYSTEM-CALL|EXEC\s+SQL|DELETE\s+FROM|TRUNCATE|GENERATE\s+SUBROUTINE\s+POOL)\b",
                re.I,
            ),
            # 9. io: I/O & Network Boundaries. Database interaction and File datasets.
            "io": re.compile(
                r"^[ \t]*(SELECT|INSERT\s+(?:INTO\b)?|UPDATE\b|MODIFY\b|OPEN\s+DATASET|TRANSFER|READ\s+DATASET|CLOSE\s+DATASET|CL_HTTP_CLIENT|CL_WEB_HTTP_CLIENT)\b",
                re.I | re.M,
            ),
            # 10. api: Public Surface Area. Exposed RFCs, OData publishing, and Public sections.
            "api": re.compile(
                r"\b(REMOTE\s+FUNCTION|@OData\.publish|DEFINE\s+VIEW|DEFINE\s+SERVICE|EXPOSED|PUBLIC\s+SECTION)\b",
                re.I,
            ),
            # 11. flux: State Mutation. State mutation (The core of ABAP data manipulation).
            "state_mutation": re.compile(
                r"^[ \t]*(MOVE|MOVE-CORRESPONDING|APPEND|MODIFY\s+TABLE|DELETE\s+TABLE)\b|^[ \t]*INSERT\s+[^\n;]+\s+INTO\s+TABLE",
                re.I | re.M,
            ),
            # 12. dead_code (Commented Logic / Deprecated Trails) Commented out structural logic (supports * and ").
            "dead_code": re.compile(
                r'^[ \t]*\*[ \t]*(?:DATA|METHOD|IF|SELECT|WRITE)\b|"[ \t]*(?:DATA|METHOD|IF|SELECT|WRITE)\b',
                re.I | re.M,
            ),
            # 13. doc: Structured Documentation. ABAP Doc annotations and metadata headers.
            "doc": re.compile(
                r'^"!\s*@(?:parameter|raising|return)|\b(?:AUTHOR|DESCRIPTION|PURPOSE|REMARKS):\b',
                re.I | re.M,
            ),
            # 14. test: Testing & Assertions. ABAP Unit markers and test-injection.
            "test": re.compile(
                r"\b(FOR\s+TESTING|RISK\s+LEVEL|DURATION\s+SHORT|CL_ABAP_UNIT_ASSERT|ZCL_ABAP_UNIT)\b",
                re.I,
            ),
            # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
            # 15. concurrency: Temporal Static. Async RFCs and background tasks.
            "concurrency": re.compile(
                r"\b(STARTING\s+NEW\s+TASK|ENQUEUE_|DEQUEUE_|WAIT\s+UP\s+TO)\b|CALL\s+FUNCTION\s+[^\n;]+\s+IN\s+BACKGROUND\s+TASK",
                re.I,
            ),
            # 16. ui_framework: UI / View Components. Screen programming and HTML viewers.
            "ui_framework": re.compile(
                r"\b(CALL\s+SCREEN|SELECTION-SCREEN|PARAMETERS|WDDOMODIFYVIEW|CL_GUI_HTML_VIEWER|CL_SALV_TABLE)\b",
                re.I,
            ),
            # 17. closures: Closures / Anonymous Functions. (ABAP lacks anonymous closures).
            "closures": None,
            # 18. globals: Global / Shared State. Global program data and the system registry.
            "globals": re.compile(r"\b(TABLES|STATICS|CLASS-DATA|SY-[A-Z0-9_]+)\b", re.I),
            # 19. decorators: Decorators / Annotations. CDS and class annotations.
            "decorators": re.compile(r"@[A-Za-z0-9_.]+(?:\([^)]*\))?", re.I),
            # 20. generics: Generics / Type Parameters. Generic data references and field symbols.
            "generics": re.compile(
                r"\b(TYPE\s+ANY(?:\s+TABLE)?|TYPE\s+INDEX\s+TABLE|TYPE\s+STANDARD\s+TABLE|TYPE\s+REF\s+TO\s+DATA)\b",
                re.I,
            ),
            # 21. comprehensions: Iterators / Comprehensions. Modern constructor expressions.
            "comprehensions": re.compile(
                r"\b(?:VALUE|REDUCE|FILTER|CORRESPONDING|NEW)\s+#?\s*\(|\bFOR\s+[a-zA-Z_]\w*\s+IN\b",
                re.I,
            ),
            # 22. scientific: Numerical / Compute Libraries. Standard numerical built-ins.
            "scientific": re.compile(
                r"\b(ABS|SQRT|LOG|EXP|SIN|COS|TAN|ROUND|CEIL|FLOOR|DECFLOAT16|DECFLOAT34)\b",
                re.I,
            ),
            # 23. heat_triggers: Metaprogramming & Reflection. RTTS and Dynamic assignment logic.
            "reflection_metaprogramming": re.compile(
                r"\b(CL_ABAP_TYPEDESCR|CL_ABAP_CLASSDESCR|ASSIGN\s+\([a-zA-Z0-9_-]+\)\s+TO|GENERATE\s+SUBROUTINE\s+POOL)\b",
                re.I,
            ),
            # 24. import: Dependency Inclusions. Includes and type pools.
            "import": re.compile(r"\b(INCLUDE|TYPE-POOLS)\b", re.I),
            "_dependency_capture": re.compile(r"^[ \t]*(?:INCLUDE|TYPE-POOLS)[ \t\n]+([A-Za-z0-9_/]+)", re.I | re.M),
            # 25. ownership: Authorship indicators.
            "ownership": re.compile(
                r"(?:AUTHOR|CREATED\s+BY|MAINTAINER|Tim Berners-Lee):\s+([^\n]+)",
                re.I | re.M,
            ),
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            # 26. planned_debt: The Promise. Future work markers.
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt: The Fracture. Admitted fragility or hacks.
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            # 29. spec_exposure: Map vs. Territory. Audit tags and architecture docs.
            "spec_exposure": re.compile(
                r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)\]|\b(?:WorldWideWeb|RFC|W3C|CERN|TBL|ENQUIRE)\b",
                re.I,
            ),
            # 30. tabs_vs_spaces (Formatting Inconsistencies): Indentation Tracker. Tabs vs 2-space standardization.
            "tabs_vs_spaces": None,
            # 31. ssr_boundaries: View Horizon. ICF and BSP request handlers.
            "ssr_boundaries": re.compile(
                r"\b(IF_HTTP_EXTENSION~HANDLE_REQUEST|CL_BSP_CONTEXT|CL_BSP_RUNTIME|IF_HTTP_REQUEST|IF_HTTP_RESPONSE|HTML_STRING)\b",
                re.I,
            ),
            # 32. events: Pub/Sub Network. Native OO event architecture.
            "events": re.compile(r"\b(RAISE\s+EVENT|SET\s+HANDLER)\b|FOR\s+EVENT\s+[^\n;]+\s+OF", re.I),
            # 33. dependency_injection: Inversion of Control. BAdIs and Test Doubles.
            "dependency_injection": re.compile(r"\b(GET\s+BADI|CALL\s+BADI|CL_BADI_BASE|CL_ABAP_TESTDOUBLE)\b", re.I),
            # 34. macros: Preprocessor Hooks. ABAP macro definitions.
            "macros": re.compile(
                r"^[ \t]*DEFINE\s+[a-zA-Z0-9_-]+\.|^[ \t]*END-OF-DEFINITION\s*\.",
                re.I | re.M,
            ),
            # 35. pointers: Memory Map. Field-Symbols and data references.
            "pointers": re.compile(r"<[A-Za-z0-9_-]+>|->\*|\b(?:GET\s+REFERENCE\s+OF|REF\s+TO)\b", re.I),
            # 36. memory_alloc: Manual Memory Management. Heap allocations.
            "memory_alloc": re.compile(r"\b(CREATE\s+OBJECT|CREATE\s+DATA|FREE|CLEAR)\b", re.I),
            # 37. inline_asm: Bare Metal.
            "inline_asm": None,
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # 38. telemetry: Professional diagnostics.
            "telemetry": re.compile(r"\b(BAL_LOG_CREATE|BAL_DB_SAVE|CL_BALI_LOG|CL_BALI_MSG_SETTER)\b", re.I),
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs): Standard output.
            "debug_prints": re.compile(r"^[ \t]*(WRITE)\b", re.I | re.M),
            # 40. explicit_casts (Explicit Type Casting): "Trust Me" Tax. Explicit casting and conversions.
            "explicit_casts": re.compile(
                r"\b(?:CAST|CONV)\s*[a-zA-Z0-9_~-]*\s*#?\s*\(|ASSIGNING\s+<[^>]+>\s+CASTING",
                re.I,
            ),
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts) Aborting execution or error messages.
            "panics_and_aborts": re.compile(
                r'\b(RAISE\s+EXCEPTION|MESSAGE\s+[^\n;]+\s+TYPE\s+[\'"][EX][\'"]|LEAVE\s+PROGRAM)\b',
                re.I,
            ),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses) Thread sleep.
            "thread_sleeps": re.compile(r"\bWAIT\s+UP\s+TO\b", re.I),
            # 43. bitwise_ops (Bitwise Operations)
            "bitwise_ops": re.compile(r"\b(BIT-AND|BIT-OR|BIT-XOR|BIT-NOT)\b", re.I),
            # 44. sync_locks (Resource Management & Stability)
            "sync_locks": re.compile(r"\b(ENQUEUE_|DEQUEUE_)\b", re.I),
            # 45. immutability_locks (Immutability Constraints) Immutability (constants).
            "immutability_locks": re.compile(r"\b(CONSTANTS|FINAL|READ-ONLY)\b", re.I),
            # 46. cleanup (Resource Cleanup / Teardown)
            "cleanup": re.compile(r"^[ \t]*(FREE|CLEAR|CLOSE\s+DATASET)\b", re.I | re.M),
            # 47. encapsulation (Encapsulation / Access Modifiers)
            "encapsulation": re.compile(r"\b(PRIVATE\s+SECTION|PROTECTED\s+SECTION)\b", re.I),
            # 48. listeners (Event Listeners / Observers)
            "listeners": re.compile(r"\bFOR\s+EVENT\s+[^\n;]+\s+OF\b", re.I),
            # 49. test_skip (Bypassed Tests / Ignored Specs)
            "test_skip": re.compile(r"\b(IGNORE)\b", re.I),
        },
    },
    "xml": {
        "_meta": {
            "target_version": "Standard XML 1.0 / UI Layouts",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard data, schemas, stylesheets, vector graphics, Apple UI, and config files.
        "extensions": [
            ".xml",
            ".xsd",
            ".xsl",
            ".xslt",
            ".svg",
            ".storyboard",
            ".xib",
            ".plist",
            ".wsdl",
            ".config",
            ".jelly",
        ],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: Universally recognized XML architectural and build manifests.
        "exact_matches": ["pom.xml", "build.xml", "AndroidManifest.xml", "phpunit.xml"],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: Primary sibling extensions to anchor standard data serialization and frameworks.
        "discriminators": [".xml", ".xsd", ".xsl", "pom.xml", "build.xml"],
        # EXECUTION SIGNATURES: XML is declarative data/markup; no shebangs exist.
        "shebangs": [],
        # UPGRADED: Maps to Family 8 (Singular/Unique)
        # Rationale: (CORRECTION) Consolidated 'xml_angle' into 'singular'. Like HTML, XML
        # exclusively uses SGML-style block delimiters () for its Commented / Non-Executable Text.
        "lexical_family": "block_exclusive",
        "rules": {},
    },
    "markdown": {
        "_meta": {
            "target_version": "CommonMark / GitHub Flavored / AsciiDoc",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard modern suffixes, legacy extensions, MDX, and AsciiDoc formats.
        "extensions": [
            ".md",
            ".markdown",
            ".mdown",
            ".mkd",
            ".mdx",
            ".adoc",
            ".asciidoc",
        ],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: The universally recognized, extensionless repository documentation anchors.
        "exact_matches": ["README", "LICENSE", "CHANGELOG", "CONTRIBUTING", "SECURITY"],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: Static site generators and documentation build configs acting as disambiguation anchors.
        "discriminators": [
            ".md",
            ".mdx",
            "mkdocs.yml",
            "_config.yml",
            "docusaurus.config.js",
        ],
        # EXECUTION SIGNATURES: Markdown is declarative text; no shebangs exist.
        "shebangs": [],
        # UPGRADED: Maps to Family 8 (Singular/Unique)
        # Rationale: (CORRECTION) Markdown relies entirely on HTML's SGML-style block comments ().
        # Mapping this to 'hybrid_dash' would cause the engine to miss hidden documentation mass.
        "lexical_family": "line_exclusive",
        "rules": {
            "lit_code_blocks": re.compile(r"^```[a-zA-Z0-9]*$", re.M),
            "lit_diagrams": re.compile(r"^```(?:mermaid|plantuml)$", re.M),
            "lit_headers": re.compile(r"^#{1,6}\s+", re.M),
            "lit_links": re.compile(r"\[[^\]]+\]\([^)]+\)"),
        },
    },
    "csv": {
        "_meta": {"target_version": "Comma Separated Values", "status": "production"},
        # COMPREHENSIVE SURFACE AREA: Comma, tab, and pipe-separated value formats.
        "extensions": [".csv", ".tsv", ".psv"],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: Delimited data relies strictly on extensions.
        "exact_matches": [],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: Sibling datasets and data-science logic files acting as disambiguation anchors.
        "discriminators": [".csv", ".tsv", ".py", ".ipynb", ".R", ".m"],
        # EXECUTION SIGNATURES: CSV is purely static data; no shebangs exist.
        "shebangs": [],
        # UPGRADED: Maps to Family 3 (Pure Hash)
        # Rationale: While strictly data, when CSVs *do* contain comments (supported by
        # parsers like Pandas or DuckDB), they almost exclusively use the '#' symbol at the start of a line.
        "lexical_family": "line_exclusive",
        "rules": {},
    },
    "yaml": {
        "_meta": {
            "target_version": "YAML CI/CD (GitHub Actions / GitLab CI)",
            "status": "production",
        },
        "extensions": [".yml", ".yaml", ".yamllint"],
        "exact_matches": [
            ".prettierrc",
            ".stylelintrc",
            "clang-format",
            ".clang-format",
        ],
        "discriminators": [
            "docker-compose.yml",
            ".gitlab-ci.yml",
            "kubernetes.yaml",
            "openapi.yaml",
            ".github/workflows",
        ],
        "shebangs": [],
        "lexical_family": "line_exclusive",
        "rules": {
            "_line_anchor": re.compile(r"#"),
            "_inline_comment": re.compile(r"#"),
            "_block_start": None,
            "_block_end": None,
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            "branch": re.compile(r"\b(?:if|else|elif|fi|case|esac|for|while|do|done)\b|&&|\|\|", re.I),
            "args": re.compile(r"^[ \t]*with:[ \t]*\n(?:[ \t]+[a-zA-Z0-9_-]+:[ \t]*.*)+", re.M | re.I),
            "structural_boundaries": re.compile(r"^[ \t]*(?:env|needs|runs-on|steps|strategy|matrix):", re.M | re.I),
            # Executable Logic Anchors: Explicit execution blocks
            "func_start": re.compile(
                r"^[ \t]*(?:-?[ \t]*run:|script:|before_script:|after_script:)[ \t]*[|>]*",
                re.M | re.I,
            ),
            "class_start": re.compile(
                r"^[ \t]*(?:jobs:|workflow_call:|[a-zA-Z0-9_-]+:[ \t]*\n[ \t]+(?:uses|image):)",
                re.M | re.I,
            ),
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            "safety": re.compile(
                r"^[ \t]*continue-on-error:[ \t]*false|^[ \t]*permissions:[ \t]*\n(?:[ \t]+(?:contents|id-token|actions|security-events):[ \t]*read)",
                re.M | re.I,
            ),
            # Catches the classic curl-to-bash supply chain dropper inside a run block
            "safety_bypasses": re.compile(
                r"^[ \t]*continue-on-error:[ \t]*true|chmod[ \t]+777|\b(?:curl|wget)[ \t]+[^|\n]{1,200}\|[ \t]*(?:bash|sh|zsh)\b",
                re.M | re.I,
            ),
            "high_risk_execution": re.compile(r"\b(?:rm[ \t]+-rf[ \t]+/(?![A-Za-z])|eval|exec)\b", re.M | re.I),
            "io": re.compile(
                r"\b(?:wget|curl|apt-get|apk|yum|git[ \t]+clone|npm[ \t]+install|pip[ \t]+install)\b",
                re.M | re.I,
            ),
            # Webhook/Workflow triggers
            "api": re.compile(
                r"^[ \t]*on:[ \t]*\n(?:[ \t]+(?:push|pull_request|workflow_dispatch|issues):)",
                re.M | re.I,
            ),
            "state_mutation": re.compile(
                r"^[ \t]*env:[ \t]*\n(?:[ \t]+[a-zA-Z0-9_-]+:[ \t]*.*)+|export[ \t]+[a-zA-Z0-9_]+[ \t]*=",
                re.M | re.I,
            ),
            "dead_code": re.compile(
                r"^[ \t]*#[ \t]*(?:-?[ \t]*run:|uses:|jobs:|steps:|script:)",
                re.M | re.I,
            ),
            "doc": re.compile(r"^[ \t]*name:[ \t]+.*|^[ \t]*description:[ \t]+.*", re.M | re.I),
            "test": re.compile(
                r"\b(?:npm[ \t]+test|pytest|make[ \t]+test|cargo[ \t]+test|go[ \t]+test)\b",
                re.M | re.I,
            ),
            # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
            "concurrency": re.compile(
                r"^[ \t]*strategy:[ \t]*\n[ \t]+matrix:|^[ \t]*concurrency:",
                re.M | re.I,
            ),
            "ui_framework": None,
            "closures": None,
            "globals": re.compile(
                r"\$\{\{[ \t]*(?:github|env|runner|secrets)\.[a-zA-Z0-9_]+[ \t]*\}\}|\$[A-Z_]+",
                re.M,
            ),
            "decorators": None,
            "generics": None,
            "comprehensions": None,
            "scientific": None,
            # Catching complex GitHub Expression injection logic
            "reflection_metaprogramming": re.compile(r"\$\{\{[ \t]*fromJson\(|to[A-Z][a-zA-Z]+\(", re.M),
            # The Gravity Links: External dependencies
            "import": re.compile(
                r"^[ \t]*(?:-?[ \t]*uses:|image:)[ \t]+([a-zA-Z0-9_./@:-]+)",
                re.M | re.I,
            ),
            "_dependency_capture": re.compile(
                r"^[ \t]*(?:-?[ \t]*uses:|image:)[ \t\n]+([a-zA-Z0-9_./@:-]+)",
                re.M | re.I,
            ),
            "ownership": None,
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            # 26. planned_debt (Annotated Debt / TODOs)
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            "hardcoded_secrets": re.compile(
                r"\b(?:password|secret|token|api[_-]?key|client[_-]?secret|private[_-]?key)[ \t]*:[ \t]*[\"'][A-Za-z0-9\-_+/=]{16,}[\"']",
                re.I,
            ),
            "spec_exposure": None,
            "tabs_vs_spaces": None,
            "ssr_boundaries": None,
            "events": re.compile(
                r"^[ \t]*repository_dispatch:|schedule:|^[ \t]*-?[ \t]*cron:",
                re.M | re.I,
            ),
            # Secrets injection
            "dependency_injection": re.compile(r"\$\{\{[ \t]*secrets\.[a-zA-Z0-9_]+[ \t]*\}\}", re.M),
            "macros": None,
            "pointers": None,
            "memory_alloc": None,
            "inline_asm": None,
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            "telemetry": re.compile(r"^[ \t]*::(?:debug|warning|error)[ \t]+.*", re.M),
            "debug_prints": re.compile(r"\b(?:echo|printf)\b", re.I),
            "explicit_casts": None,
            # GitHub action specific bailout outputs
            "panics_and_aborts": re.compile(
                r"\b(?:exit[ \t]+[1-9]|kill[ \t]+-[0-9]+)\b|^[ \t]*::error::",
                re.M | re.I,
            ),
            "thread_sleeps": re.compile(r"\bsleep[ \t]+[0-9]+\b", re.I),
            "bitwise_ops": None,
            "sync_locks": None,
            # Strict SHA-1 pinning for immutable security
            "immutability_locks": re.compile(r"@[a-f0-9]{40}\b", re.I),
            "cleanup": None,
            "encapsulation": None,
            "listeners": re.compile(r"^[ \t]*webhook:", re.M | re.I),
            "test_skip": re.compile(r"\|\|[ \t]*true\b|\b(?:--passWithNoTests|skipTests|--no-audit)\b", re.I),
        },
    },
    "pbtxt": {
        "_meta": {
            "target_version": "Protobuf Text Format",
            "last_updated": "2026-03-11",
            "blueprint_version": "6.30",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard Protobuf text and binary message formats used heavily in Google/Bazel ecosystems.
        "extensions": [".pbtxt", ".textproto", ".textpb", ".pb"],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: PBTXT strictly relies on its extensions.
        "exact_matches": [],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: Standard .proto schema definitions and Bazel build files acting as disambiguation anchors.
        "discriminators": [".proto", "WORKSPACE", "BUILD.bazel", "BUILD"],
        # EXECUTION SIGNATURES: PBTXT is purely serialized message data; no shebangs exist.
        "shebangs": [],
        # UPGRADED: Maps to Family 3 (Pure Hash)
        # Rationale: While standard .proto schemas use C-style (//) comments, the instantiated
        # Text Format (.pbtxt) strictly uses '#' for comments.
        "lexical_family": "line_exclusive",
        "rules": {},
    },
    "yacc": {
        "_meta": {
            "target_version": "GNU Bison / Yacc / Flex",
            "last_updated": "2026-03-11",
            "blueprint_version": "v5.1",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Yacc/Bison parser grammars (.y) and Lex/Flex tokenizers (.l), plus their C++ variants (.ypp, .lpp).
        "extensions": [".y", ".yy", ".ypp", ".l", ".ll", ".lpp"],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: Parser generators rely strictly on extensions.
        "exact_matches": [],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: The generated C/C++ outputs and standard build systems acting as disambiguation anchors.
        "discriminators": [
            ".c",
            ".cpp",
            ".h",
            "Makefile",
            "CMakeLists.txt",
            "configure.ac",
        ],
        # EXECUTION SIGNATURES: Grammars are compiled into C/C++ state machines; no shebangs exist.
        "shebangs": [],
        # UPGRADED: Maps to Family 1 (Standard C-Style)
        # Rationale: Yacc and Lex files interleave grammar definitions with pure C/C++ code
        # blocks (enclosed in %{ %}), relying entirely on standard '/* */' and '//' comments.
        "lexical_family": "standard_block",
        "rules": {
            "_line_anchor": re.compile(r"//"),
            "_inline_comment": re.compile(r"//"),
            "_block_start": re.compile(r"/\*"),
            "_block_end": re.compile(r"\*/"),
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            "branch": re.compile(r"\b(if|else|switch|case|for|while|do)\b|\|"),
            "args": re.compile(r"\$\d+|\$\$"),
            "structural_boundaries": re.compile(r"\b(return|goto|break|continue|%token|%type|%left|%right|%nonassoc)\b"),
            # Executable Logic Anchor: Anchors specifically onto Grammar Rules
            # Matches "rule_name :" or "rule_name:" at the start of a line
            "func_start": re.compile(r"^[ \t]*([a-zA-Z_]\w*)(?=[ \t]*:)", re.M),
            "class_start": None,
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            "safety": re.compile(r"\b(assert|YYABORT|YYACCEPT|YYERROR)\b"),
            "safety_bypasses": re.compile(r"\b(goto|void\s*\*)\b"),
            "high_risk_execution": re.compile(r"\b(abort|exit|YYNOMEM)\b"),
            "io": re.compile(r"\b(fopen|fclose|fread|fwrite|yyin|yyout|fprintf)\b"),
            "api": re.compile(r"\b(%define|%code|%provides|%requires)\b"),
            "state_mutation": re.compile(r"(?<![=!<>])=(?![=])|\+\+|--"),
            "dead_code": re.compile(r"//[ \t]*(?:if|for|while|return|%token)\b|/\*[ \t]*(?:if|for|while|%token)"),
            "doc": re.compile(r"/\*\*|@param|@return"),
            "test": None,
            # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
            "concurrency": None,
            "ui_framework": None,
            "closures": None,
            "globals": re.compile(r"\b(yylval|yylloc|yynerrs|yydebug)\b"),
            "decorators": None,
            "generics": re.compile(r"<[a-zA-Z_][a-zA-Z0-9_]*>"),  # Captures %type <val>
            "comprehensions": None,
            "scientific": None,
            "reflection_metaprogramming": re.compile(r"%\{|%\}|%%"),
            "import": re.compile(r'^[ \t]*#(?:include)\s*[<"][^>"]+[>"]', re.M),
            "ownership": re.compile(r"(?:@author|Author:|Created by:|Copyright)\s+(.*)", re.I),
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            "planned_debt": GLOBAL_PLANNED_DEBT,
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]", re.I),
            "tabs_vs_spaces": None,
            "ssr_boundaries": None,
            "events": None,
            "dependency_injection": None,
            "macros": re.compile(r"^[ \t]*#(?:define|undef|if|elif|else|endif|pragma)\b", re.M),
            "pointers": re.compile(r"->|&\w+|(?<=[=(,])[ \t]*\*(?:\s*const\s*)?[a-zA-Z_]\w*"),
            "memory_alloc": re.compile(r"\b(malloc|calloc|realloc|free|YYMALLOC|YYFREE)\b"),
            "inline_asm": None,
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            "telemetry": re.compile(r"\b(?:syslog|openlog|log_info|YYDPRINTF)\b"),
            "debug_prints": re.compile(r"\b(printf|fprintf|vprintf|puts|yyerror)\b"),
            "explicit_casts": re.compile(
                r"\(\s*(?:int|char|short|long|float|double|void|unsigned|signed|[A-Z]\w*)\s*\*?\s*\)\s*[a-zA-Z_$]"
            ),
            "panics_and_aborts": re.compile(r"\b(abort|exit|YYABORT)\b"),
            "thread_sleeps": None,
            "bitwise_ops": re.compile(r"<<|>>|(?<!&)&(?!&)|(?<!\|)\|(?!\|)|\^|~"),
            "sync_locks": None,
            "immutability_locks": re.compile(r"\bconst\b"),
            "cleanup": re.compile(r"\b(free|YYFREE|fclose|destroy)\b\s*\("),
            "encapsulation": re.compile(r"^[ \t]*static\b", re.M),
            "listeners": None,
            "test_skip": None,
        },
    },
    "m4": {
        "_meta": {
            "target_version": "GNU M4 1.4+ / Autoconf 2.71+",
            "last_updated": "2026-03-11",
            "blueprint_version": "v5.1",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard macros, Autotest suites (.at), Autoconf logic (.ac), and template stubs (.in).
        "extensions": [".m4", ".at", ".ac", ".in"],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: The undeniable structural anchors of the GNU build system.
        "exact_matches": ["configure.ac", "configure.in"],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: Automake configurations and standard Makefiles acting as contextual baselines for ambiguous .in templates.
        "discriminators": [
            ".m4",
            "Makefile.am",
            "Makefile.in",
            "aclocal.m4",
            "config.h.in",
        ],
        # EXECUTION SIGNATURES: M4 is a macro processor; no traditional shebangs exist.
        "shebangs": [],
        # UPGRADED: Maps to Family 8 (Singular/Unique)
        # Rationale: M4 uniquely uses the `dnl` (Delete to NewLine) macro to act as its
        # line-level Commented / Non-Executable Text.
        "lexical_family": "line_exclusive",
        "rules": {
            # --- LEXICAL DELIMITER CONTROLS ---
            "_line_anchor": re.compile(r"\bdnl\b"),
            "_inline_comment": re.compile(r"\bdnl\b"),
            "_block_start": None,
            "_block_end": None,
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # 1. branch (Control Flow / Branching)
            # M4 branching logic and Autoconf shell-generation branches.
            "branch": re.compile(r"\b(?:ifelse|ifdef|AS_IF|AS_CASE|m4_if|m4_case|m4_cond|m4_ifval|m4_ifblank)\b"),
            # 2. args (Parameters / Coupling)
            # M4 positional arguments.
            "args": re.compile(r"\$[0-9]+|\$[@*#]"),
            # 3. linear (Sequential Boundaries)
            # Execution flow diversion and dependency signaling.
            "structural_boundaries": re.compile(r"\b(?:divert|undivert|m4_divert|m4_undivert|m4_require|AC_REQUIRE)\b"),
            # 4. func_start (Executable Logic Anchors)
            # Defining a macro establishes an executable logic block in M4.
            "func_start": re.compile(
                r"^[ \t]*(m4_define|define|AC_DEFUN|AC_DEFUN_ONCE|AU_DEFUN|m4_defun)(?=\s*\()",
                re.M,
            ),
            # 5. class_start (Object / Entity Declarations)
            "class_start": None,  # M4 is a macro processor, lacking objects.
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            # 6. safety (Defensive Programming / Validation)
            # Autoconf environment checks and M4 assertions.
            "safety": re.compile(
                r"\b(?:m4_assert|AS_VERSION_COMPARE|AC_CHECK_PROG|AC_CHECK_LIB|AC_CHECK_HEADER|AC_CHECK_FUNC|m4_warn)\b"
            ),
            # 7. safety_neg (Safety Bypasses / Unchecked Types)
            # Dynamically altering the quote characters or comment strings breaks the parser context completely.
            "safety_bypasses": re.compile(r"\b(?:changequote|changecom|m4_changequote|m4_changecom|m4_ignore)\b"),
            # 8. danger (High-Risk Execution / System Calls)
            # Executing raw shell commands during macro expansion (not generation).
            "high_risk_execution": re.compile(r"\b(?:syscmd|esyscmd|m4_syscmd|m4_esyscmd)\b"),
            # 9. io (I/O & Network Boundaries)
            # Reading system values, creating temp files, or emitting generated configurations.
            "io": re.compile(r"\b(?:sysval|mkstemp|maketemp|m4_mkstemp|m4_maketemp|AC_CONFIG_FILES|AC_OUTPUT)\b"),
            # 10. api (Public Surface Area)
            # M4 macros are inherently public, but these explicitly export state into the generated Makefile/C headers.
            "api": re.compile(r"\b(?:AC_SUBST|AC_DEFINE|AC_PROVIDE|m4_provide)\b"),
            # 11. flux (State Mutation)
            # Stack-based macro overriding and list appending.
            "state_mutation": re.compile(r"\b(?:pushdef|popdef|m4_pushdef|m4_popdef|m4_append|m4_append_uniq|m4_combine)\b"),
            # 12. dead_code (Commented Logic / Deprecated Trails)
            # Commented-out macro definitions.
            "dead_code": re.compile(r"^[ \t]*dnl[ \t]+(?:m4_define|define|AC_DEFUN|ifelse|AS_IF)\b", re.M),
            # 13. doc (Structured Documentation)
            # Documentation blocks or explicit copyright insertions into the output script.
            "doc": re.compile(r"^[ \t]*dnl[ \t]+@(?:param|return|brief)|AC_COPYRIGHT\b", re.M),
            # 14. test (Testing & Assertions)
            # The GNU Autotest framework.
            "test": re.compile(r"\b(?:AT_SETUP|AT_CHECK|AT_CLEANUP|AT_INIT|AT_DATA)\b"),
            # --- 🔬 PHASE 3: SPECIALIZED SENSORS (Architecture & Complexity) ---
            # 15. concurrency
            "concurrency": None,
            # 16. ui_framework
            "ui_framework": None,
            # 17. closures
            "closures": None,
            # 18. globals (Global / Shared State)
            # Environment variables mapped into the configure script.
            "globals": re.compile(r"\b(?:AC_ARG_VAR|AC_ENV_VAR|m4_divert_text)\b"),
            # 19. decorators
            "decorators": None,
            # 20. generics
            "generics": None,
            # 21. comprehensions (Iterators / Comprehensions)
            # M4 map and foreach iterative constructs.
            "comprehensions": re.compile(r"\b(?:m4_foreach|m4_foreach_w|m4_map|m4_map_sep)\b"),
            # 22. scientific (Numerical / Compute Libraries)
            # M4's native integer arithmetic evaluator.
            "scientific": re.compile(r"\b(?:eval|m4_eval)\b"),
            # 23. heat_triggers (Metaprogramming & Reflection)
            # Advanced string metaprogramming and regex substitutions.
            "reflection_metaprogramming": re.compile(
                r"\b(?:translit|patsubst|regexp|m4_translit|m4_bpatsubst|m4_bregexp|m4_pattern_allow)\b"
            ),
            # 24. import (Dependency Inclusions)
            # File inclusions.
            "import": re.compile(r"^[ \t]*(?:include|sinclude|m4_include|m4_sinclude)\b", re.M),
            # 25. ownership (Authorship Metadata)
            "ownership": re.compile(
                r"^[ \t]*dnl[ \t]+(?:Author|Maintainer|Copyright|License):|AC_COPYRIGHT",
                re.I | re.M,
            ),
            # --- 🌌 PHASE 4: EXTENDED DIMENSIONS (Specialized Sub-Equations) ---
            # 26. planned_debt (Annotated Debt / TODOs)
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            # 29. spec_exposure
            "spec_exposure": re.compile(r"\[(?:[ \t]*SPEC[ \t]*-[ \t]*\d+|spec|audit)[^\]]*\]", re.I),
            # 30. tabs_vs_spaces (Formatting Inconsistencies) 
            "tabs_vs_spaces": None,
            # 31. ssr_boundaries
            "ssr_boundaries": None,
            # 32. events
            "events": None,
            # 33. dependency_injection
            # M4 dependency chaining to ensure macros execute in the correct order.
            "dependency_injection": re.compile(r"\b(?:AC_REQUIRE|m4_require)\b"),
            # 34. macros (Preprocessor Directives / Macros)
            # M4 is the macro engine, but this tracks configuring C-level preprocessor hooks.
            "macros": re.compile(r"\b(?:AC_DEFINE|AC_DEFINE_UNQUOTED|AH_TEMPLATE)\b"),
            # 35. pointers
            "pointers": None,
            # 36. memory_alloc
            "memory_alloc": None,
            # 37. inline_asm
            "inline_asm": None,
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # 38. telemetry (Structured Logging / Telemetry)
            # Logging configure progress securely to stdout and config.log.
            "telemetry": re.compile(r"\b(?:AC_MSG_CHECKING|AC_MSG_RESULT|AC_MSG_WARN|AC_MSG_NOTICE)\b"),
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
            # Raw M4 error printing.
            "debug_prints": re.compile(r"\b(?:errprint|m4_errprint)\b"),
            # 40. explicit_casts (Explicit Type Casting)
            "explicit_casts": None,
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
            # Hard aborts.
            "panics_and_aborts": re.compile(r"\b(?:m4_fatal|AC_MSG_ERROR|AC_MSG_FAILURE|AS_EXIT)\b"),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
            # Raw sleeps in generated scripts.
            "thread_sleeps": re.compile(r"\b(?:sleep)\b"),
            # 43. bitwise_ops (Bitwise Operations)
            "bitwise_ops": None,
            # 44. sync_locks
            "sync_locks": None,
            # 45. immutability_locks (Immutability Constraints)
            "immutability_locks": None,  # M4 macros are mutable by design.
            # 46. cleanup (Resource Cleanup / Teardown)
            # Macro unloading and Autotest tear-downs.
            "cleanup": re.compile(r"\b(?:m4_popdef|popdef|AT_CLEANUP)\b"),
            # 47. encapsulation (Access Modifiers / Encapsulation)
            # Forbidding specific patterns from reaching the output script.
            "encapsulation": re.compile(r"\b(?:m4_pattern_forbid)\b"),
            # 48. listeners
            "listeners": None,
            # 49. test_skip (Bypassed Tests / Ignored Specs)
            # Skipping tests in the Autotest framework.
            "test_skip": re.compile(r"\b(?:AT_SKIP_IF)\b"),
        },
    },
    "scheme": {
        "_meta": {
            "target_version": "R5RS / R6RS / Guile (GnuPG gpgscm)",
            "last_updated": "2026-03-11",
            "blueprint_version": "v6.2.2",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard Scheme, legacy PLT/Chez suffixes, and Racket sources.
        "extensions": [".scm", ".ss", ".rkt", ".sch", ".sld", ".sls", ".sps"],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: Scheme rarely uses extensionless configurations.
        "exact_matches": [],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: Guile build definitions, Racket manifests, and Lisp package formats.
        "discriminators": [".scm", ".rkt", "info.rkt", "guix.scm"],
        # EXECUTION SIGNATURES: Interpreters found on Line 1 for shell wrappers invoking Scheme/Guile/Racket.
        "shebangs": ["guile", "scheme", "csi", "racket", "racketsh"],
        # UPGRADED: Maps to Family 9 (Lisp_Semi) - *NEW FAMILY*
        # Rationale: Perfectly captures the Lisp ecosystem's reliance on ';' for line-level
        # comments and `#| |#` for nested block-level Commented / Non-Executable Text.
        "lexical_family": "line_exclusive",
        "rules": {
            # --- LEXICAL DELIMITER CONTROLS ---
            # Scheme uses ';' for standard line-level literature.
            "_line_anchor": re.compile(r";"),
            "_inline_comment": re.compile(r";"),
            # Scheme block comments (SRFI 30) use #| and |#
            "_block_start": re.compile(r"#\|"),
            "_block_end": re.compile(r"\|#"),
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # 1. branch (Control Flow / Branching)
            # Lisp control flow branches. Uses custom S-expression boundaries.
            "branch": re.compile(r"(?<=[ \t(\[])(if|cond|case|and|or|when|unless)(?=[ \t)\]\n\r])"),
            # 2. args (Parameters / Coupling)
            # Captures the parameter list inside a standard function definition: (define (func arg1 arg2) ...)
            "args": re.compile(
                # =====================================================================
                # [ THE S-EXPRESSION ARGS SHIELD (SCHEME) ]
                # Scheme arguments are inside the same parenthesis as the function name.
                # FIX 1 (Pathological): Upgraded horizontal spaces to `[ \t\n]*` for vertical layouts.
                # FIX 2 (Positive): The previous regex strictly required a space and arguments.
                # Made the argument capture group `(?:[ \t\n]+[^)]*)?` optional so
                # parameter-less functions like `(define (func))` cleanly pass.
                # =====================================================================
                r"^[ \t\n]*\([ \t\n]*define[ \t\n]+\([ \t\n]*[^ \t\n()]+(?:[ \t\n]+[^)]*)?[ \t\n]*\)",
                re.M,
            ),
            # 3. linear (Sequential Boundaries)
            # Structural boundaries defining scope and sequential execution.
            "structural_boundaries": re.compile(r"(?<=[ \t(\[])(let|let\*|letrec|letrec\*|begin|do)(?=[ \t)\]\n\r])"),
            # 4. func_start (Executable Logic Anchors)
            # Anchors logic blocks. Captures the function name immediately following the parenthesis.
            "func_start": re.compile(
                # =====================================================================
                # [ THE S-EXPRESSION SHIELD (SCHEME/LISP) ]
                # S-expressions format heavily around parentheses, often pushing the
                # `define`, the inner parenthesis `(`, and the identifier onto separate lines.
                # FIX: Replaced `\s+` and `\s*` with `[ \t\n]+` and `[ \t\n]*` inside
                # the S-expression structure to ensure the parser can track the
                # identifier no matter how deeply it is vertically nested.
                # =====================================================================
                r"^[ \t\n]*\([ \t\n]*define[ \t\n]+\([ \t\n]*([a-zA-Z0-9_!?-]+)(?=[ \t\n)\]\r])",
                re.M,
            ),
            # 5. class_start (Object / Entity Declarations)
            # Scheme lacks traditional objects; SRFI-9 Records serve as structural entities.
            "class_start": re.compile(
                r"^[ \t]*\([ \t]*define-record-type\s+([a-zA-Z0-9_!?-]+)(?=[ \t)\]\n\r])",
                re.M,
            ),
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            # 6. safety (Defensive Programming / Validation)
            # Continuations, exception guards, and dynamic-wind state protectors.
            "safety": re.compile(
                r"(?<=[ \t(\[])(guard|dynamic-wind|with-exception-handler|call-with-current-continuation|call/cc|assert|check)(?=[ \t)\]\n\r])"
            ),
            # 7. safety_neg (Safety Bypasses / Unchecked Types)
            # Explicit, raw manipulation of cons cells or unrestricted environments.
            "safety_bypasses": re.compile(r"(?<=[ \t(\[])(set-car!|set-cdr!|interaction-environment)(?=[ \t)\]\n\r])"),
            # 8. danger (High-Risk Execution / System Calls)
            # Dynamic code execution and emergency system exits.
            "high_risk_execution": re.compile(r"(?<=[ \t(\[])(eval|exit|emergency-exit|quit)(?=[ \t)\]\n\r])"),
            # 9. io (I/O & Network Boundaries)
            # File operations and output ports.
            "io": re.compile(
                r"(?<=[ \t(\[])(open-input-file|open-output-file|read|read-char|write|display|newline|call-with-input-file|call-with-output-file|load|format)(?=[ \t)\]\n\r])"
            ),
            # 10. api (Public Surface Area)
            # Module exports defining the public surface.
            "api": re.compile(r"^[ \t]*\([ \t]*(?:export|define-public)(?=[ \t)\]\n\r])", re.M),
            # 11. flux (State Mutation)
            # Mutation of state. In Scheme, all mutating functions end with a bang (!).
            "state_mutation": re.compile(
                r"(?<=[ \t(\[])(set!|vector-set!|string-set!|hash-table-set!|bytevector-u8-set!)(?=[ \t)\]\n\r])"
            ),
            # 12. dead_code (Commented Logic / Deprecated Trails)
            # Commented out S-expressions.
            "dead_code": re.compile(
                r"^[ \t]*;+[ \t]*\([ \t]*(?:define|let|if|cond|lambda)(?=[ \t)\]\n\r])",
                re.M,
            ),
            # 13. doc (Structured Documentation)
            # Scheme documentation standards (triple semicolons or texinfo).
            "doc": re.compile(r"^[ \t]*;;;|^[ \t]*;[ \t]*@(?:param|return|author)", re.M),
            # 14. test (Testing & Assertions)
            # SRFI-64 and Guile testing frameworks (essential for mapping gpgscm tests).
            "test": re.compile(
                r"(?<=\()(test-begin|test-end|test-assert|test-eqv|test-equal|test-eq|check-equal\?|check-true|test)(?=[ \t)\]\n\r])"
            ),
            # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
            # 15. concurrency (Asynchronous Execution)
            # SRFI-18 Multithreading primitives.
            "concurrency": re.compile(
                r"(?<=[ \t(\[])(make-thread|thread-start!|thread-yield!|mutex-lock!|mutex-unlock!|condition-variable-signal!)(?=[ \t)\]\n\r])"
            ),
            # 16. ui_framework
            "ui_framework": None,
            # 17. closures (Closures / Anonymous Functions)
            # Anonymous function depth.
            "closures": re.compile(r"(?<=[ \t(\[])lambda(?=[ \t)\]\n\r])"),
            # 18. globals (Global / Shared State)
            # Top-level state bindings (defines that are NOT functions).
            "globals": re.compile(r"^[ \t]*\([ \t]*define\s+[a-zA-Z0-9_!?-]+\s+[^(\s]", re.M),
            # 19. decorators
            "decorators": None,
            # 20. generics
            "generics": None,
            # 21. comprehensions (Iterators / Comprehensions)
            # Functional list operations (SRFI-1).
            "comprehensions": re.compile(
                r"(?<=[ \t(\[])(map|for-each|filter|fold|reduce|fold-right|fold-left)(?=[ \t)\]\n\r])"
            ),
            # 22. scientific (Numerical / Compute Libraries)
            # Scheme's native mathematical tower.
            "scientific": re.compile(
                r"(?<=[ \t(\[])(sin|cos|tan|asin|acos|atan|exp|log|sqrt|expt|abs|gcd|lcm|numerator|denominator|floor|ceiling|truncate|round|exact->inexact)(?=[ \t)\]\n\r])"
            ),
            # 23. heat_triggers (Metaprogramming & Reflection)
            # Metaprogramming and syntactic abstractions.
            "reflection_metaprogramming": re.compile(
                r"(?<=[ \t(\[])(define-macro|define-syntax|syntax-rules|syntax-case|let-syntax|letrec-syntax)(?=[ \t)\]\n\r])"
            ),
            # 24. import (Dependency Inclusions)
            # Scheme module resolution dependencies.
            "import": re.compile(r"^[ \t]*\([ \t]*(?:import|use-modules|require)(?=[ \t)\]\n\r])", re.M),
            # 25. ownership (Authorship Metadata)
            "ownership": re.compile(
                r"^[ \t]*;+\s*(?:Author|Created by|Maintainer|Copyright):\s+(.*)",
                re.I | re.M,
            ),
            # --- 🌌 PHASE 4: EXTENDED DIMENSIONS (Specialized Sub-Equations) ---
            # 26. planned_debt
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            # 29. spec_exposure
            "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]", re.I),
            # 30. tabs_vs_spaces (Formatting Inconsistencies)
            # Lisp/Scheme relies entirely on uniform space alignment. Tabs are highly destructive here.
            "tabs_vs_spaces": None,
            # 31. ssr_boundaries
            "ssr_boundaries": None,
            # 32. events (Event Emitters / Pub-Sub)
            # Hook paradigms common in Guile/Emacs environments.
            "events": re.compile(r"(?<=[ \t(\[])(hook|add-hook!|run-hooks)(?=[ \t)\]\n\r])"),
            # 33. dependency_injection
            "dependency_injection": None,
            # 34. macros (Preprocessor Directives / Macros)
            "macros": re.compile(r"(?<=[ \t(\[])(define-syntax|define-macro|syntax-rules|syntax-case)(?=[ \t)\]\n\r])"),
            # 35. pointers
            "pointers": None,
            # 36. memory_alloc
            # Explicit heap instantiations.
            "memory_alloc": re.compile(
                r"(?<=[ \t(\[])(make-vector|make-string|make-bytevector|make-hash-table|cons|list)(?=[ \t)\]\n\r])"
            ),
            # 37. inline_asm
            "inline_asm": None,
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # 38. telemetry (Structured Logging / Telemetry)
            "telemetry": re.compile(r"(?<=[ \t(\[])(log-info|log-error|log-warn|log-debug|syslog)(?=[ \t)\]\n\r])"),
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
            "debug_prints": re.compile(r"(?<=[ \t(\[])(display|write|newline|format\s+#t)(?=[ \t)\]\n\r])"),
            # # 40. explicit_casts (Explicit Type Casting)
            # Type coercions crossing memory boundaries.
            "explicit_casts": re.compile(
                r"(?<=[ \t(\[])(number->string|string->number|symbol->string|string->symbol|list->vector|vector->list|char->integer|integer->char)(?=[ \t)\]\n\r])"
            ),
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
            "panics_and_aborts": re.compile(r"(?<=[ \t(\[])(error|abort|exit|emergency-exit)(?=[ \t)\]\n\r])"),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
            "thread_sleeps": re.compile(r"(?<=[ \t(\[])(sleep|usleep|thread-sleep!)(?=[ \t)\]\n\r])"),
            # 43. bitwise_ops (Bitwise Operations)
            "bitwise_ops": re.compile(
                r"(?<=[ \t(\[])(bitwise-and|bitwise-ior|bitwise-xor|bitwise-not|arithmetic-shift|ash)(?=[ \t)\]\n\r])"
            ),
            # 44. sync_locks (Resource Management & Stability)
            "sync_locks": re.compile(r"(?<=[ \t(\[])(mutex-lock!|make-mutex)(?=[ \t)\]\n\r])"),
            # 45. immutability_locks (Immutability Constraints)
            # Immutable strings and explicit quotations (meaning the list cannot be mutated safely).
            "immutability_locks": re.compile(r"(?<=[ \t(\[])(quote|string->immutable-string)(?=[ \t)\]\n\r])|\'(?=\()"),
            # 46. cleanup (Resource Cleanup / Teardown)
            "cleanup": re.compile(r"(?<=[ \t(\[])(close-input-port|close-output-port|close-port)(?=[ \t)\]\n\r])"),
            # 47. encapsulation (Access Modifiers / Encapsulation)
            # Module-internal definitions.
            "encapsulation": re.compile(r"^[ \t]*\([ \t]*define-private(?=[ \t)\]\n\r])", re.M),
            # 48. listeners (Event Listeners / Observers)
            "listeners": re.compile(r"(?<=[ \t(\[])(add-hook!)(?=[ \t)\]\n\r])"),
            # 49. test_skip (Bypassed Tests / Ignored Specs)
            "test_skip": re.compile(r"(?<=[ \t(\[])(test-skip|test-expect-fail)(?=[ \t)\]\n\r])"),
        },
    },
    "mlir": {
        "_meta": {
            "target_version": "LLVM MLIR",
            "last_updated": "2026-03-11",
            "blueprint_version": "1.0",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: The standard dialect and transformation format for MLIR.
        "extensions": [".mlir"],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: IR files strictly rely on their extensions.
        "exact_matches": [],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: LLVM TableGen definitions, core LLVM IR, and CMake configs anchoring the compiler toolchain.
        "discriminators": [".mlir", ".td", ".ll", "CMakeLists.txt"],
        # EXECUTION SIGNATURES: MLIR is ingested by tools like mlir-opt; no shebangs exist.
        "shebangs": [],
        # UPGRADED: Maps to Family 1 (Standard C-Style)
        # Rationale: MLIR intentionally adopts standard LLVM assembly syntax conventions,
        # using '//' exclusively for line comments to maintain C++ ecosystem familiarity.
        "lexical_family": "standard_block",
        "rules": {
            "_line_anchor": re.compile(r"//"),
            "_inline_comment": re.compile(r"//"),
            "_block_start": None,
            "_block_end": None,
        },
    },
    "proto": {
        "_meta": {
            "target_version": "Protocol Buffers 3 (proto3)",
            "last_updated": "2026-03-11",
            "blueprint_version": "1.0",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard Protocol Buffer schema definition files.
        "extensions": [".proto"],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: Schemas strictly rely on their extensions.
        "exact_matches": [],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: Buf configuration files, Bazel build files, and generated code markers acting as anchors.
        "discriminators": [
            ".proto",
            "buf.yaml",
            "buf.gen.yaml",
            "WORKSPACE",
            "BUILD.bazel",
            "BUILD",
        ],
        # EXECUTION SIGNATURES: Protobuf is a declarative schema language; no shebangs exist.
        "shebangs": [],
        # UPGRADED: Maps to Family 1 (Standard C-Style)
        # Rationale: Protobuf schemas strictly use standard '//' and '/* */' comments.
        "lexical_family": "standard_block",
        "rules": {
            "_line_anchor": re.compile(r"//"),
            "_inline_comment": re.compile(r"//"),
            "_block_start": re.compile(r"/\*"),
            "_block_end": re.compile(r"\*/"),
        },
    },
    "hlo": {
        "_meta": {
            "target_version": "XLA High-Level Optimizer IR",
            "last_updated": "2026-03-11",
            "blueprint_version": "1.0",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard XLA HLO intermediate representation text formats.
        "extensions": [".hlo"],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: IR text files strictly rely on their extensions.
        "exact_matches": [],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: JAX, TensorFlow, and MLIR toolchain markers acting as disambiguation anchors for ML compilers.
        "discriminators": [".hlo", ".mlir", ".pbtxt", ".py", "BUILD.bazel", "BUILD"],
        # EXECUTION SIGNATURES: HLO is compiler intermediate representation; no shebangs exist.
        "shebangs": [],
        # UPGRADED: Maps to Family 1 (Standard C-Style)
        # Rationale: HLO text format exclusively utilizes '//' for line-level comments, maintaining C++ ecosystem alignment.
        "lexical_family": "standard_block",
        "rules": {
            "_line_anchor": re.compile(r"//"),
            "_inline_comment": re.compile(r"//"),
            "_block_start": None,
            "_block_end": None,
        },
    },
    "td": {
        "_meta": {
            "target_version": "LLVM TableGen",
            "last_updated": "2026-03-11",
            "blueprint_version": "1.0",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard LLVM TableGen record definition files.
        "extensions": [".td"],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: TableGen relies entirely on its extensions.
        "exact_matches": [],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION: LLVM/Clang core C++ source files, generated includes (.inc), and CMake configs anchoring the compiler backend.
        "discriminators": [
            ".td",
            ".cpp",
            ".h",
            ".inc",
            "CMakeLists.txt",
            "LLVMBuild.txt",
        ],
        # EXECUTION SIGNATURES: TableGen is processed by the llvm-tblgen backend during build time; no shebangs exist.
        "shebangs": [],
        # UPGRADED: Maps to Family 1 (Standard C-Style)
        # Rationale: TableGen was built to integrate seamlessly into LLVM's C++ codebase, natively supporting '//' and '/* */' comments.
        "lexical_family": "standard_block",
        "rules": {
            "_line_anchor": re.compile(r"//"),
            "_inline_comment": re.compile(r"//"),
            "_block_start": re.compile(r"/\*"),
            "_block_end": re.compile(r"\*/"),
        },
    },
    "plaintext": {
        "_meta": {
            "target_version": "Universal Plaintext & ASCII Secrets",
            "last_updated": "2026-04-01",
            "blueprint_version": "1.1",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard text, log outputs, and UNIX man pages.
        # FIX: Removed JCL/BMS (executable) and p12/pfx/jks/kdbx (lethal binary blobs).
        "extensions": [
            ".txt",
            ".text",
            ".log",
            ".out",
            ".err",
            ".nfo",
            ".golden",
            ".properties",
            ".1",
            ".2",
            ".3",
            ".4",
            ".5",
            ".6",
            ".7",
            ".8",
            ".9",
            # --- THE SECRETS SHUNT (ASCII ONLY) ---
            ".pem",
            ".key",
            ".pub",
            ".crt",
            ".cer",
            ".asc",
            ".gpg",
            ".sig",
            ".ovpn",
        ],
        # ABSOLUTE IDENTITY: The universally recognized, extensionless plaintext anchors.
        # FIX: Added ubiquitous community files. Removed binary keystore exact matches.
        "exact_matches": [
            "AUTHORS",
            "NOTICE",
            "COPYING",
            "INSTALL",
            "acknowledgements",
            "CHANGELOG",
            "CONTRIBUTING",
            "CODE_OF_CONDUCT",
            "SECURITY",
            "MAINTAINERS",
            # --- THE SECRETS SHUNT (ASCII ONLY) ---
            "id_rsa",
            "id_dsa",
            "id_ed25519",
            "id_ecdsa",
            ".env",
            ".env.local",
            ".env.production",
            ".npmrc",
            ".htpasswd",
            ".pypirc",
            "credentials.json",
            "client_secret.json",
            "auth.json",
            "shadow",
        ],
        # ECOSYSTEM ANCHORS: Universal fallback discriminators.
        "discriminators": [".txt", ".md", "README", "LICENSE"],
        # EXECUTION SIGNATURES: Plaintext is unexecuted raw string data.
        "shebangs": [],
        # THE FIX: Plaintext is mathematically inert. It has no lexical family.
        "lexical_family": "non_lexical",
        "rules": {
            "_line_anchor": None,
            "_inline_comment": None,
            "_block_start": None,
            "_block_end": None,
        },
    },
    "tcl": {
        "_meta": {
            "target_version": "Tcl 8.6 / SQLite Test Suite",
            "last_updated": "2026-03-11",
            "blueprint_version": "v6.3.0",
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
        "rules": {
            # --- LEXICAL DELIMITER CONTROLS ---
            "_line_anchor": re.compile(r"#"),
            "_inline_comment": re.compile(r"#"),
            "_block_start": None,
            "_block_end": None,
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # 1. branch (Control Flow / Branching)
            # Tcl control flow keywords.
            "branch": re.compile(r"\b(?:if|elseif|else|switch|while|for|foreach|catch|try|trap|finally)\b"),
            # 2. args (Parameters / Coupling)
            # Safely captures the parameter list `{...}` immediately following a proc name.
            "args": re.compile(
                # =====================================================================
                # [ THE VERTICAL PROC SHIELD (TCL) ]
                # Tcl developers can break the `proc`, name, and argument brace `{}`
                # across newlines.
                # FIX: Upgraded horizontal `[ \t]+` constraints to vertical `[ \t\n]+`.
                # =====================================================================
                r"^[ \t]*proc[ \t\n]+[a-zA-Z0-9_:]+[ \t\n]+\{([^}]*)\}",
                re.M,
            ),
            # 3. linear (Sequential Boundaries)
            # Structural boundaries. EXCLUDES: global/upvar (globals/heat).
            "structural_boundaries": re.compile(r"\b(?:proc|return|break|continue|namespace|variable|yield)\b"),
            # 4. func_start (Executable Logic Anchors)
            # MUST HAVE EXACTLY ONE CAPTURE GROUP.
            # Captures standard procs and namespaced procs (e.g., `proc ::my::func`).
            "func_start": re.compile(r"^[ \t]*proc[ \t]+([a-zA-Z0-9_:]+)(?=[ \t]*\{|[ \t\n]|$)", re.M),
            # 5. class_start (Object / Entity Declarations)
            # Captures TclOO, Snit, and Itcl class definitions.
            "class_start": re.compile(
                r"^[ \t]*(?:oo::class[ \t]+create|snit::type|itcl::class)[ \t]+([a-zA-Z0-9_:]+)(?=[ \t]*\{|[ \t\n]|$)",
                re.M,
            ),
            # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
            # 6. safety (Defensive Programming / Validation)
            # Safe evaluation and error catching.
            "safety": re.compile(r"\b(?:catch|try|trap|finally|info[ \t]+exists|assert)\b"),
            # 7. safety_neg (Safety Bypasses / Unchecked Types)
            # Unrestricted evaluation and context manipulation.
            "safety_bypasses": re.compile(r"\b(?:eval|uplevel|upvar)\b"),
            # 8. danger (High-Risk Execution / System Calls)
            # OS command execution and process termination.
            "high_risk_execution": re.compile(r"\b(?:exec|exit)\b|file[ \t]+delete[ \t]+-force"),
            # 9. io (I/O & Network Boundaries)
            # File system, sockets, and configuration. (Excludes puts which is mapped to print_hits).
            "io": re.compile(r"\b(?:open|close|read|gets|socket|fconfigure|file|source|vfs::)\b"),
            # 10. api (Public Surface Area)
            # Exposing packages or namespace exports.
            "api": re.compile(r"^[ \t]*(?:package[ \t]+provide|namespace[ \t]+export)\b", re.M),
            # 11. flux (State Mutation)
            # Variable state mutations.
            "state_mutation": re.compile(r"\b(?:set|lappend|dict[ \t]+set|array[ \t]+set|incr|append)\b[ \t]+[a-zA-Z0-9_:]+"),
            # 12. dead_code (Commented Logic / Deprecated Trails)
            # Commented out structural code.
            "dead_code": re.compile(r"^[ \t]*#[ \t]*(?:proc|set|if|while|foreach|return)\b", re.M),
            # 13. doc (Structured Documentation)
            # Tcl doc blocks.
            "doc": re.compile(r"^[ \t]*#[ \t]*@(?:param|return|brief|author)", re.M),
            # 14. test (Testing & Assertions)
            # *THE SQLITE MEGA-SENSOR*: Accurately maps the SQLite custom test harnesses alongside standard tcltest.
            "test": re.compile(
                r"\b(?:do_test|do_execsql_test|do_catchsql_test|do_eqp_test|do_ioerr_test|do_faultsim_test|test\s+[a-zA-Z0-9_-]+|tcltest::|finish_test)\b"
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
            "globals": re.compile(r"\b(?:global|::env)\b|upvar[ \t]+#0"),
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
            # 23. heat_triggers (Metaprogramming & Reflection)
            # High Cognitive Load: Intercepting variables, tracking execution, and runtime aliasing.
            "reflection_metaprogramming": re.compile(r"\b(?:trace[ \t]+add|rename|interp[ \t]+create|interp[ \t]+alias)\b"),
            # 24. import (Dependency Inclusions)
            # Package and module loading.
            "import": re.compile(r"^[ \t]*(?:package[ \t]+require|source|load)\b", re.M),
            # 25. ownership (Authorship Metadata)
            "ownership": re.compile(
                r"^[ \t]*#[ \t]*(?:Author|Created by|Maintainer|Copyright):\s+(.*)",
                re.I | re.M,
            ),
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            # 26. planned_debt (Annotated Debt / TODOs)
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            "spec_exposure": re.compile(r"\[(?:[ \t]*SPEC[ \t]*-[ \t]*\d+|spec|audit)[^\]]*\]", re.I),
            # 30. tabs_vs_spaces (Formatting Inconsistencies) 
            # Tcl standardizes on spaces. Tabs indicate formatter friction.
            "tabs_vs_spaces": None,
            "ssr_boundaries": None,
            # 32. events (Event Emitters / Pub-Sub)
            # Tcl event bindings and file event handlers.
            "events": re.compile(r"\b(?:bind|fileevent|vwait|trace[ \t]+add)\b"),
            "dependency_injection": None,
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
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
            "panics_and_aborts": re.compile(r"\b(?:error|exit)\b"),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
            "thread_sleeps": re.compile(r"\bafter[ \t]+[0-9]+\b"),
            # 43. bitwise_ops (Bitwise Operations)
            "bitwise_ops": re.compile(r"(?<!&)&(?!&)|(?<!\|)\|(?!\|)|\^|~|<<|>>"),
            # 44. sync_locks (Resource Management & Stability)
            "sync_locks": re.compile(r"\b(?:thread::mutex|thread::rwmutex|thread::cond)\b"),
            # 45. immutability_locks (Immutability Constraints)
            # Tcl lacks `const`, but setting a trace to prevent writes is the Tcl idiom for freezing.
            "immutability_locks": re.compile(r"\btrace[ \t]+add[ \t]+variable[ \t]+[a-zA-Z0-9_:]+[ \t]+write\b"),
            # 46. cleanup (Resource Cleanup / Teardown)
            "cleanup": re.compile(r'\b(?:close|unset)\b|rename[ \t]+[a-zA-Z0-9_:]+[ \t]+""'),
            # 47. encapsulation (Access Modifiers / Encapsulation)
            # Internal namespaces and private `_` prefixed procs.
            "encapsulation": re.compile(r"\bnamespace[ \t]+eval\b|^[ \t]*proc[ \t]+_[a-zA-Z0-9_:]+", re.M),
            # 48. listeners (Event Listeners / Observers)
            "listeners": re.compile(r"\b(?:bind|fileevent)\b"),
            # 49. test_skip (Bypassed Tests / Ignored Specs)
            # Using TclTest constraints to silently skip tests on certain OS environments.
            "test_skip": re.compile(r"-constraints[ \t]+[a-zA-Z0-9_]+\b|\btestConstraint\b"),
        },
    },
    "groovy": {
        "_meta": {
            "target_version": "Groovy 4.0 / Gradle 8+",
            "last_updated": "2026-03-12",
            "blueprint_version": "v5.0",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA
        "extensions": [".groovy", ".gradle", ".gvy", ".gy", ".gsh"],
        # ABSOLUTE IDENTITY & EXACT FILENAMES
        "exact_matches": ["Jenkinsfile"],
        # ECOSYSTEM ANCHORS & DISAMBIGUATION
        "discriminators": [
            "build.gradle",
            "settings.gradle",
            "gradle.properties",
            "pom.xml",
            ".java",
        ],
        # EXECUTION SIGNATURES
        "shebangs": ["groovy"],
        # LEXICAL FAMILY
        "lexical_family": "standard_block",
        "rules": {
            # --- LEXICAL DELIMITER CONTROLS ---
            "_line_anchor": re.compile(r"//"),
            "_inline_comment": re.compile(r"//"),
            "_block_start": re.compile(r"/\*"),
            "_block_end": re.compile(r"\*/"),
            # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
            # 1. branch (Control Flow / Branching)
            "branch": re.compile(r"\b(if|else|switch|case|default|for|while|in|try|catch|finally)\b|\?|:"),
            # 2. args (Parameters / Coupling)
            # Captures standard method arguments and Groovy closures (x, y ->)
            # CRITICAL FIX: Anchored the parenthesis capture to method signatures so it
            # doesn't hallucinate every standard method call or if-statement in the file.
            "args": re.compile(
                r"^[ \t]*(?:(?:public|private|protected|static|final|def|abstract)[ \t]+){0,5}(?:[A-Z][a-zA-Z0-9_<>\[\]?]*[ \t]+){0,2}[A-Za-z_$][\w_$]*\s*\([^)]*\)|(?:\([^)]*\)|[a-zA-Z_$][\w_$]*)\s*->",
                re.M,
            ),
            # 3. linear (Sequential Boundaries)
            "structural_boundaries": re.compile(
                r"\b(def|class|interface|trait|enum|record|import|package|extends|implements|return|yield)\b"
            ),
            # 4. func_start (Executable Logic Anchors)
            # HIGHLY TUNED: Uses Negative Lookahead to explicitly ignore Gradle DSL keywords (implementation, api, task)
            # Uses Positive Lookahead (?=[ \t]*\() to stop exactly at the function name without consuming punctuation.
            "func_start": re.compile(
                r"^[ \t]*(?:(?:public|private|protected|static|final|def)[ \t]+){0,5}(?:[A-Z][a-zA-Z0-9_<>\[\]?]*[ \t]+){0,2}(?!(?:if|for|while|switch|catch|new|return|class|interface|enum|trait|implementation|testImplementation|api|compileOnly|runtimeOnly|classpath|dependency|from|file|mavenCentral|plugins|dependencies|repositories|task|project|allprojects|subprojects|ext)\b)([A-Za-z_$][\w_$]*)(?=[ \t]*\()",
                re.M,
            ),
            # 5. class_start (Object / Entity Declarations)
            "class_start": re.compile(
                r"^[ \t]*(?:(?:public|private|protected|static|final|abstract)[ \t]+){0,5}(?:class|interface|trait|enum|record)\s+[A-Za-z_$][\w_$]*",
                re.M,
            ),
            # --- PHASE 2: RISK ENGINE (Structural Integrity) ---
            # 6. safety (Defensive Programming / Validation)
            "safety": re.compile(
                r"\b(try|catch|finally|assert|instanceof|Optional)\b|@(?:Valid|Validated|NotNull|NonNull|Immutable)"
            ),
            # 7. safety_neg (Safety Bypasses / Unchecked Types)
            "safety_bypasses": re.compile(
                r"\b(null)\b|return\s+null|catch\s*\(\s*(?:Exception|Throwable)\b|@SuppressWarnings|@SneakyThrows|\.get\(\)"
            ),
            # 8. danger (High-Risk Execution / System Calls)
            "high_risk_execution": re.compile(r"\b(System\.exit|Runtime\.getRuntime\(\)\.exec|execute)\b"),
            # 9. io (I/O & Network Boundaries)
            "io": re.compile(
                r"\b(File|Files|Paths|FileReader|FileWriter|file|copy|sync|uri|url|Socket|Connection|ResultSet)\b"
            ),
            # 10. api (Public Surface Area)
            # Groovy classes/methods are implicitly public by default, making the whole file highly exposed.
            "api": re.compile(
                r"\b(public)\b|@(RestController|Controller|Service|Component|Bean|RequestMapping|GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping)\b"
            ),
            # 11. flux (State Mutation)
            "state_mutation": re.compile(r"^[ \t]*\w+(?:\.\w+)*[ \t]*=|@(?:Setter|Data)\b", re.M),
            # 12. dead_code (Commented Logic / Deprecated Trails)
            # Tuned to catch dead Gradle definitions and Groovy logic.
            "dead_code": re.compile(
                r"//[ \t]*(?:def|class|void|if|for|while|import|implementation|compile|api|testImplementation)\b"
            ),
            # 13. doc (Structured Documentation)
            "doc": re.compile(r"/\*\*|@param|@return|@throws|@deprecated|@see"),
            # 14. test (Testing & Assertions)
            # Integrates Spock Framework keywords (given:, when:, then:, expect:) alongside JUnit.
            "test": re.compile(
                r"@(?:Test|Before|After|BeforeEach|AfterEach|Mock)|assert\w*\s*\(|^\s*(?:given|when|then|expect|setup|cleanup|where):",
                re.M,
            ),
            # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
            # 15. concurrency (Asynchronous Execution)
            "concurrency": re.compile(
                r"\b(synchronized|Thread|Runnable|Future|ExecutorService|Promise|Atomic\w+|task)\b|@(?:Async|Scheduled)"
            ),
            # 16. ui_framework (UI / View Components)
            "ui_framework": re.compile(r"\b(SwingBuilder|JFrame|JPanel|ModelAndView|ModelMap|Model|UIComponent)\b"),
            # 17. closures (Closures / Anonymous Functions)
            "closures": re.compile(r"->|\{\s*(?:it|[\w\s,]+)\s*->"),
            # 18. globals (Global / Shared State)
            "globals": re.compile(r"\b(System\.getProperty|System\.getenv|project\.ext)\b|@Value"),
            # 19. decorators (Decorators / Annotations)
            "decorators": re.compile(r"^[ \t]*@[\w.]+(?:\([^)]*\))?", re.M),
            # 20. generics (Generics / Type Parameters)
            "generics": re.compile(r"<\s*[A-Z?][^>]*>"),
            # 21. comprehensions (Iterators / Comprehensions)
            "comprehensions": re.compile(
                r"\.(?:collect|find|findAll|grep|inject|each|eachWithIndex|map|filter|reduce)\("
            ),
            # 22. scientific (Numerical / Compute Libraries)
            "scientific": re.compile(r"\b(Math\.|BigDecimal|BigInteger|Random|SecureRandom)\b"),
            # 23. heat_triggers (Metaprogramming & Reflection)
            # Groovy's highly dynamic Meta-Object Protocol (MOP).
            "reflection_metaprogramming": re.compile(
                r"\b(invokeMethod|getProperty|setProperty|methodMissing|propertyMissing|ExpandoMetaClass|metaClass)\b"
            ),
            # 24. import (Dependency Inclusions)
            "import": re.compile(r"^[ \t]*import\s+(?:static[ \t]+)?[\w.]+;?", re.M),
            # 25. ownership (Authorship Metadata)
            "ownership": re.compile(r"@author\s+(.*)", re.I),
            # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
            # 26. planned_debt (Annotated Debt / TODOs)
            "planned_debt": GLOBAL_PLANNED_DEBT,
            # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
            "fragile_debt": GLOBAL_FRAGILE_DEBT,
            # 29. spec_exposure (Spec / Audit Traceability)
            "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)[^\]]*\]", re.I),
            # 30. tabs_vs_spaces (Formatting Inconsistencies) 
            "tabs_vs_spaces": None,
            # 31. ssr_boundaries (Server-Side Rendering)
            "ssr_boundaries": re.compile(
                r"\b(MarkupBuilder|StreamingMarkupBuilder|TemplateEngine|HttpServletRequest|HttpServletResponse|@ResponseBody)\b"
            ),
            # 32. events (Event Emitters / Pub-Sub)
            "events": re.compile(r"\b(ApplicationEvent|ApplicationListener|@EventListener|publishEvent)\b"),
            # 33. dependency_injection (Dependency Injection / IoC)
            # Heavily captures Gradle plugin and dependency architecture.
            "dependency_injection": re.compile(
                r"\b(@Autowired|@Inject|@Component|@Service|@Repository|@Bean|@Configuration|apply\s+plugin|plugins\s*\{|dependencies\s*\{)\b"
            ),
            # 34. macros
            "macros": None,
            # 35. pointers (Pointer Arithmetic / Memory Addressing)
            "pointers": None,
            # 36. memory_alloc
            "memory_alloc": None,
            # 37. inline_asm
            "inline_asm": None,
            # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
            # 38. telemetry (Structured Logging / Telemetry)
            "telemetry": re.compile(
                r"\b(log|logger|LOGGER|LoggerFactory)\.(?:info|error|warn|warning|debug|trace)\b|@Slf4j|@Log4j2|@Log"
            ),
            # 39. debug_prints (Debug Artifacts / Unstructured Outputs)
            "debug_prints": re.compile(
                r"\b(println|print|printf|System\.out\.print|System\.err\.print|\.printStackTrace\(\))\b"
            ),
            # # 40. explicit_casts (Explicit Type Casting)
            "explicit_casts": re.compile(
                r"\bas\s+[A-Z]\w*|\(\s*(?:int|long|short|byte|char|float|double|boolean|[A-Z][A-Za-z0-9_]*)\s*\)\s*[a-zA-Z_$]"
            ),
            # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
            "panics_and_aborts": re.compile(r"\b(throw|System\.exit|GradleException)\b"),
            # 42. thread_sleeps (Thread Blocking / Synchronous Pauses)
            "thread_sleeps": re.compile(r"\b(Thread\.sleep|sleep)\b"),
            # 43. bitwise_ops (Bitwise Operations)
            # EXCLUDES `<<` and `>>` because Groovy heavily overloads `<<` for list/stream appending.
            "bitwise_ops": re.compile(r"\^|~"),
            # 44. sync_locks (Resource Management & Stability)
            "sync_locks": re.compile(r"\b(synchronized|ReentrantLock|ReadWriteLock|Semaphore|Lock|Mutex)\b"),
            # 45. immutability_locks (Immutability Constraints)
            "immutability_locks": re.compile(r"\b(final|@Immutable)\b"),
            # 46. cleanup (Resource Cleanup / Teardown)
            "cleanup": re.compile(r"\b(close|dispose|shutdown)\b\s*\("),
            # 47. encapsulation (Access Modifiers / Encapsulation)
            "encapsulation": re.compile(r"\b(private|protected)\b"),
            # 48. listeners (Event Listeners / Observers)
            "listeners": re.compile(r"\b(addListener|on[A-Z]\w*|subscribe)\b"),
            # 49. test_skip (Bypassed Tests / Ignored Specs)
            "test_skip": re.compile(r"@(?:Ignore|Disabled|PendingFeature)\b|mock\s*\(|spy\s*\("),
        },
    },
    "json": {
        "_meta": {
            "target_version": "Modern JSON & Configuration Ecosystem",
            "status": "production",
        },
        # COMPREHENSIVE SURFACE AREA: Standard, commented, line-delimited, and geospatial JSON.
        "extensions": [
            ".json",
            ".arb",
            ".jsonc",
            ".json5",
            ".jsonl",
            ".ndjson",
            ".geojson",
            ".topojson",
        ],
        # ABSOLUTE IDENTITY & EXACT FILENAMES: Extended modern web/node tooling.
        "exact_matches": [
            ".prettierrc",
            ".eslintrc",
            ".babelrc",
            ".stylelintrc",
            ".bowerrc",
            ".hintrc",
            ".nycrc",
            ".lintstagedrc",
            ".swcrc",
        ],
        "discriminators": [".json", ".jsonc", ".json5", ".arb"],
        "shebangs": [],
        # THE FIX: JSON with comments relies on C-style comment structures, not Python/Ruby hashes.
        "lexical_family": "standard_block",
        "rules": {
            # =====================================================================
            # [ CRITICAL ROADMAP: JSONC/JSON5 LEXICAL DELIMITERS & THE RE.COMPILE TRAP ]
            # 1. THE LEXICAL MAPPING: JSON with comments (.jsonc, .json5) strictly
            #    uses C-style comments (// and /* */), NOT Python/Ruby hashes (#).
            #    This is why JSON must map to the 'std_c' lexical_family, not 'pure_hash' or 'inert'.
            # 2. THE RE.COMPILE TRAP: Every rule here MUST be wrapped in re.compile().
            #    If passed as raw strings, the engine's physics loop will crash with
            #    "'str' object has no attribute 'pattern'" during the Commented / Non-Executable Text extraction.
            # =====================================================================
            # JSON has no concept of a "column 1" or line-start-only comment anchor.
            "_line_anchor": None,
            # JSONC/JSON5 inline comments use standard C-style slashes.
            "_inline_comment": re.compile(r"//"),
            # JSONC/JSON5 multi-line blocks use standard C-style delimiters.
            "_block_start": re.compile(r"/\*"),
            "_block_end": re.compile(r"\*/"),
        },
    },
    "glsl": {
        "_meta": {"target_version": "OpenGL Shading Language", "status": "production"},
        "extensions": [".glsl", ".vert", ".frag", ".geom", ".comp"],
        "exact_matches": [],
        "discriminators": [".glsl", ".vert", ".frag"],
        "shebangs": [],
        "lexical_family": "standard_block",
        "rules": {
            "_line_anchor": re.compile(r"//"),
            "_inline_comment": re.compile(r"//"),
            "_block_start": re.compile(r"/\*"),
            "_block_end": re.compile(r"\*/"),
        },
    },
    "nix": {
        "_meta": {"target_version": "Nix Expression Language", "status": "production"},
        "extensions": [".nix"],
        "exact_matches": [],
        "discriminators": ["flake.nix", "default.nix", "shell.nix"],
        "shebangs": [],
        "lexical_family": "line_exclusive",
        "rules": {
            "_line_anchor": re.compile(r"#"),
            "_inline_comment": re.compile(r"#"),
            "_block_start": None,
            "_block_end": None,
        },
    },
    "blp": {
        "_meta": {"target_version": "Blueprint UI Markup", "status": "production"},
        "extensions": [".blp"],
        "exact_matches": [],
        "discriminators": [".blp", ".ui"],
        "shebangs": [],
        "lexical_family": "standard_block",
        "rules": {
            "_line_anchor": re.compile(r"//"),
            "_inline_comment": re.compile(r"//"),
            "_block_start": re.compile(r"/\*"),
            "_block_end": re.compile(r"\*/"),
        },
    },
    "batch": {
        "_meta": {"target_version": "Windows CMD/Batch", "status": "production"},
        "extensions": [".bat", ".cmd"],
        "exact_matches": [],
        "discriminators": [],
        "shebangs": [],
        "lexical_family": "line_exclusive",
        "rules": {
            # Uses REM or :: for comments. No active logic rules needed (Inert Matter Bypass).
            "_line_anchor": re.compile(r"^[ \t]*(?:REM|::)", re.I | re.M),
            "_inline_comment": None,
            "_block_start": None,
            "_block_end": None,
        },
    },
    "jcl": {
        "_meta": {
            "target_version": "IBM z/OS JCL",
            "status": "production",
        },
        "extensions": [".jcl", ".prc", ".bms"],
        "exact_matches": [],
        "discriminators": [".cbl", ".cob", ".cpy"],
        "shebangs": [],
        "lexical_family": "line_exclusive",
        "rules": {
            # JCL comments strictly start with //*
            "_line_anchor": re.compile(r"^//\*"),
            "_inline_comment": None,
            "_block_start": None,
            "_block_end": None,
            
            # Control flow in JCL (IF/THEN/ELSE/ENDIF)
            "branch": re.compile(r"\b(IF|THEN|ELSE|ENDIF)\b", re.I),
            "args": None,
            
            # Structural boundaries (Any line starting with // and a command)
            "structural_boundaries": re.compile(r"^[ \t]*//[A-Za-z0-9_#$@]+\s+(?:DD|INCLUDE|SET|PROC|PEND)\b", re.M | re.I),
            
            # Functions (EXEC steps)
            "func_start": re.compile(r"^[ \t]*//([A-Za-z0-9_#$@]+)\s+EXEC\b", re.M | re.I),
            
            # Classes/Entities (JOB cards)
            "class_start": re.compile(r"^[ \t]*//([A-Za-z0-9_#$@]+)\s+JOB\b", re.M | re.I),
            
            # Danger (Execution of arbitrary programs)
            "high_risk_execution": re.compile(r"\bPGM=[A-Za-z0-9_#$@]+\b", re.I),
            
            # I/O (Data Set Names and Sysouts)
            "io": re.compile(r"\b(DSN|DSNAME|SYSOUT|SYSPRINT|DISP=)\b", re.I),
            
            # JCL doesn't have traditional code equivalents for these, keep them null to prevent crashes
            "safety": None,
            "api": None,
            "state_mutation": re.compile(r"\bSET\s+[A-Za-z0-9_#$@]+=", re.I),
            "concurrency": None,
            "ui_framework": None,
            "closures": None,
            "globals": None,
            "decorators": None,
            "generics": None,
            "comprehensions": None,
            "scientific": None,
            "reflection_metaprogramming": None,
            "import": re.compile(r"^[ \t]*//[A-Za-z0-9_#$@]+\s+INCLUDE\b", re.M | re.I),
            "ownership": re.compile(r"^//\*\s*(?:Author|Created by|Maintainer):\s+(.*)", re.I | re.M),
            "telemetry": None,
            "debug_prints": None,
        },
    },
}

# ------------------------------------------------------------------------------
# DIALECTS (Project-Specific Overrides)
# ------------------------------------------------------------------------------
PROJECT_OVERRIDES = {
    "freebsd-src": {
        "objective-c": {"extensions": [".mm", ".h"]},
        "c": {
            "extensions": [
                ".c",
                ".h",
                ".cl",
                ".inc",
                ".y",
                ".idc",
                ".cats",
                ".m",
                ".dts",
                ".dtsi",
            ]
        },
    },
    "wrf-fortran": {
        "_shield_": {"unban_directories": ["var", "external", "test"]},
        "fortran": {
            "concurrency": re.compile(
                r"\b(COARRAY|SYNC\s+ALL|CRITICAL|MPI_[A-Za-z_]+|wrf_dm[A-Za-z0-9_]*|RSL[A-Za-z0-9_]*)\b|!\$(?:OMP|ACC)\b",
                re.I,
            )
        },
    },
    "Apollo-11": {
        "agc_assembly": {
            "_meta_purpose_block": re.compile(r"^[ \t]*(?:FUNCTIONAL|PROGRAM)\s+DESCRIPTION\b", re.I),
            "_meta_purpose_line": re.compile(r"^[ \t]*Purpose[\s:\-]*(.*)", re.I),
            "_meta_boundary": re.compile(
                r"^[ \t]*(?:Assembler|Filename|Pages|Website|Mod history|Copyright|Reference|PROGRAM NAME)[\s:\-]+",
                re.I,
            ),
        }
    },
    "cpython": {
        "_shield_": {
            "exclude_paths": ["Lib/pydoc_data/topics.py", "configure"],
            "exclude_dirs": ["Modules/clinic"],
        }
    },
    "AppFlowy": {
        "_shield_": {
            "exclude_dirs": ["scripts", "integration_test"],
            "exclude_paths": ["install.sh"],
        }
    },
    "ansible": {"_shield_": {"exclude_dirs": [".azure-pipelines", ".github"]}},
    "bugzilla": {
        "html": {
            "extensions": [
                ".html",
                ".htm",
                ".xhtml",
                ".cshtml",
                ".vue",
                ".svelte",
                ".astro",
                ".ejs",
                ".hbs",
                ".twig",
                ".erb",
                ".tmpl",
            ]
        }
    },
    "bun": {"_shield_": {"exclude_dirs": ["scripts"]}},
    "curl": {
        "plaintext": {
            "extensions": [
                ".txt",
                ".text",
                ".log",
                ".out",
                ".err",
                ".nfo",
                ".1",
                ".3",
                ".d",
            ]
        }
    },
    "discourse": {
        "_shield_": {"exclude_paths": ["config/unicorn_launcher", "pnpm-lock.yaml", "yarn.lock"]},
        "javascript": {"extensions": [".js", ".jsx", ".mjs", ".cjs", ".gjs"]},
    },
    "elasticsearch": {"plaintext": {"extensions": [".txt", ".text", ".log", ".json", ".yaml", ".yml"]}},
    "exiftool": {"plaintext": {"extensions": [".txt", ".text", ".out", ".args", ".fmt", ".xmp"]}},
    "express": {"html": {"extensions": [".html", ".htm", ".ejs", ".tmpl"]}},
    "fieldtrip": {"_shield_": {"exclude_dirs": ["external"]}},
    "jenkins": {"_shield_": {"exclude_paths": ["translation-tool.pl", "core/report-l10n.rb"]}},
    "redis": {"_shield_": {"exclude_dirs": ["deps/lua", "deps/jemalloc", "deps/hiredis"]}},
}
