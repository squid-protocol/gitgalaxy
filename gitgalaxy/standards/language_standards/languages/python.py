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
from typing import Any

from .._shared_patterns import (
    GLOBAL_DL_FRAMEWORKS,
    GLOBAL_FRAGILE_DEBT,
    GLOBAL_LLM_API,
    GLOBAL_LLM_ORCHESTRATOR,
    GLOBAL_LLM_VECTOR_STORE,
    GLOBAL_ML_TRADITIONAL,
    GLOBAL_PLANNED_DEBT,
)

DEFINITION: dict[str, Any] = {
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
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch (Control Flow / Branching)
        # Includes match/case (3.10+) and logical short-circuits. EXCLUDES exceptions.
        "branch": re.compile(r"\b(if|elif|else|for|while|with|try|finally|match|case|and|or)\b"),
        # 2. args (Parameters / Coupling)
        # Signatures for def/lambda. Bounded generics and params [^)]*.
        # RULE 11 FIX (epic #813/#818): the PEP 695 (3.12+) generic-parameter step-over was a
        # flat `[^\]]*`, truncating at the FIRST `]` and breaking any type param with a
        # nested-bracket bound (e.g. `def Foo[T: Sequence[int]](x: T) -> T:`, a realistic bounded
        # generic). Widened to the established one-level-nesting idiom (square-bracket variant).
        # #1199: the parameter list is now captured in its own group
        # (group 1 for def/lambda-with-parens, group 2 for bare
        # lambda params) instead of only ever being reachable via
        # group(0), which used to include the "def name"/"lambda"
        # keyword prefix -- that prefix supplied a spurious extra
        # whitespace-split token that overcounted every zero/one-arg
        # signature by +1 downstream in detector.py's args-counter.
        # Group 1's body also steps over one level of nested parens
        # (the same bounded one-level-nesting idiom RULE 11 already
        # uses for square brackets above) so a default value that's
        # itself a call, e.g. `def f(x=foo(1, 2), y=3):`, doesn't
        # truncate the capture at the default's own closing paren and
        # silently drop every parameter after it.
        "args": re.compile(
            r"(?:async[ \t]+)?def[ \t]+(\w+)(?:\[(?:[^\[\]]|\[[^\[\]]*\])*\])?[ \t]*(\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\))|"
            r"\blambda\b[ \t]*([^:]*):|"
            r"^[ \t]*cp?def[ \t]+(?!(?:class|struct|enum|union|extern|packed|fused)\b)"
            r"(?:(?:inline|public|readonly|api)[ \t]+){0,3}"
            r"(?:(?:[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*|\{\{[ \t]*[A-Za-z_]\w*[ \t]*\}\})[ \t]+){0,2}"
            r"\*{0,2}[ \t]*(\w+)[ \t]*(\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\))",
            re.M,
        ),
        # 3. linear (Sequential Boundaries)
        # Structural boundaries. EXCLUDES: _private (encapsulation) and Final (freeze_hits).
        "structural_boundaries": re.compile(
            r"\b(def|class|return|import|from|as|pass|continue|break|await|assert|del|global|nonlocal|type)\b"
        ),
        # 4. func_start (Executable Logic Anchors)
        # Anchors executable logic. Steps safely over decorators.
        # RULE 11 FIX (epic #813/#818): see args' comment above -- same PEP 695 nested-bracket
        # gap, same fix (widened generic-parameter step-over).
        # tri-comparison-ledger-sweep (2026-08-20): second alternative adds Cython's
        # `cdef`/`cpdef` module-level function definitions (`.pyx`/`.pxd`/`.pxi` are
        # deliberately routed to "python" -- see `extensions` above -- for exactly this
        # comprehensive-Cython-surface reason). These have no `def` keyword at all
        # (`cdef int _allocate_buffer(array self) except -1:`), so the first alternative
        # never saw them -- confirmed as a real, complete recall gap (68 real functions
        # across `cython/MemoryView.pyx`/`.pxd` in the crucible corpus, ctags-corroborated,
        # 0 found by GitGalaxy). Excludes `cdef class`/`struct`/`enum`/`union`/`extern`/
        # `packed`/`fused` up front (declarations, not functions -- `class_start` above
        # already owns `cdef class`) and tolerates up to 2 return-type words plus an
        # optional pointer star before the name (`cdef char *pybuffer_index(...)`), mirroring
        # the same bounded-repetition discipline as the decorator step-over rather than an
        # unbounded quantifier. A bare `cdef`-prefixed variable/attribute declaration (no
        # trailing `(` on the same line, e.g. `cdef bint broadcasting`) never matches either
        # branch since both require the literal `(` to close the match.
        # tri-comparison-ledger-sweep follow-up (2026-08-21): a return-type token can also be
        # a Cython Tempita codegen placeholder (`cdef {{memviewslice_name}} *get_slice_from_
        # memview(...)`, cython/MemoryView.pyx -- Cython's own source templates specialized
        # copies of this file per element type). The plain-identifier alternative can't start
        # with `{`, so this was the one remaining real function this rule missed on the
        # crucible corpus. Added as a second, bounded alternative in the same repeated
        # return-type group (`\{\{...\}\}`, one identifier only -- no nested unbounded
        # quantifier, same ReDoS discipline as everything else in this rule).
        "func_start": re.compile(
            r"^[ \t]*(?:@[\w.]+(?:\([^)]*\))?[ \t]+){0,5}(?:async[ \t]+)?def[ \t]+\w+(?:\[(?:[^\[\]]|\[[^\[\]]*\])*\])?[ \t]*\("
            r"|"
            r"^[ \t]*cp?def[ \t]+(?!(?:class|struct|enum|union|extern|packed|fused)\b)"
            r"(?:(?:inline|public|readonly|api)[ \t]+){0,3}"
            r"(?:(?:[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*|\{\{[ \t]*[A-Za-z_]\w*[ \t]*\}\})[ \t]+){0,2}"
            r"\*{0,2}[ \t]*\w+[ \t]*\(",
            re.M,
        ),
        # 5. class_start (Object / Entity Declarations)
        # RULE 11 FIX (epic #813/#818): same PEP 695 nested-bracket gap as func_start/args above,
        # here it silently dropped the base-class capture (group 2) rather than failing the whole
        # match, since the class NAME (group 1) is captured before the generic step-over -- an
        # easy miss for the same reason java's #816 class_start bug was (name looks fine,
        # inheritance info silently vanishes).
        "class_start": re.compile(
            r"^[ \t]*(?:@[\w.]+(?:\([^)]*\))?[ \t]+){0,5}(?:cdef[ \t]+|cpdef[ \t]+)?class[ \t]+([a-zA-Z_]\w*)(?:\[(?:[^\[\]]|\[[^\[\]]*\])*\])?(?:[ \t]*\(([^)]*)\))?",
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
        # #2593: `os\.`/`sys\.` used to match ANY `os.x`/`sys.x` attribute access, which
        # overlaps the `globals` rule's `os.environ`/`sys.argv`/`sys.path` (those are shared
        # process state, not an I/O boundary) -- one planted `os.environ` or `sys.argv` read
        # was double-counted as both `globals` and `io`. Negative lookaheads carve out exactly
        # those three tokens so `os.path`/`os.open`/`sys.stdin`/etc. still count as `io`.
        "io": re.compile(
            r"\b(open|requests|httpx|aiohttp|boto3|pathlib|socket|sqlalchemy|psycopg2?|asyncpg)\b"
            r"|\bos\.(?!environ\b)|\bsys\.(?!argv\b|path\b)"
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
        "doc": re.compile(r'"""|\'\'\'|:param|:return|:raises|:type|\b(?:Args|Returns|Yields|Raises|Attributes):\b'),
        # 14. test (Testing & Assertions)
        # #2593: `assert` is a general-purpose validation keyword already owned by `safety`
        # (see that rule above) -- it isn't itself a testing signal, so a runtime invariant
        # check in production code (`assert isinstance(value, int)`, no test framework in
        # sight) was being double-counted as `test` too. Removed; `def test_`/unittest/pytest/
        # fixture/patch/Mock already cover real testing idioms without it.
        "test": re.compile(r"\b(unittest|pytest|TestCase|fixture|patch)\b|def[ \t]+test_|\bMock\b"),
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
        # BUG FIX: `globals\(\)`/`locals\(\)` both end on `)`
        # (non-word), so the shared trailing \b could never fire --
        # whatever follows a function call (`;`, a newline, `.method`,
        # end of string) is never a word character. Neither builtin
        # ever matched in any real usage.
        "globals": re.compile(r"\b(?:os\.environ|sys\.argv|sys\.path)\b|\bglobals\(\)|\blocals\(\)"),
        # 19. decorators (Decorators / Annotations)
        "decorators": re.compile(r"^[ \t]*@[\w.]+", re.M),
        # 20. generics (Generics / Type Parameters)
        "generics": re.compile(
            r"\b(List|Dict|Set|Tuple|Optional|Union|TypeVar|Generic|Any|Callable|Mapping)\b\[[^\]]*\]|\b(list|dict|set|tuple|type)\[[^\]]*\]|->"
        ),
        # 21. comprehensions (Iterators / Comprehensions)
        # Was `\.(?:map|filter|reduce|...)\s*\(` -- JavaScript's Array-method
        # idiom, copy-pasted in by mistake (that pattern correctly belongs
        # to javascript/typescript's own comprehensions rule, not this
        # one). Python doesn't have `.map(`/`.filter(` as builtin list
        # methods; it has comprehension syntax (`[x for x in y]`,
        # `{k: v for k, v in items}`, generator expressions). The old
        # pattern never matched a single real Python comprehension and
        # only fired incidentally on unrelated methods that happen to
        # share a name (e.g. a Django queryset's `.filter(active=True)`).
        # Matches embedded_python's (correct, already ReDoS-bounded)
        # comprehension pattern.
        "comprehensions": re.compile(
            r"\[[^\]]{0,500}\bfor\b[^\]]{0,500}\]|\{[^}]{0,500}\bfor\b[^}]{0,500}\}|\([^)]{0,500}\bfor\b[^)]{0,500}\)"
        ),
        "scientific": re.compile(r"\b(?:import|require|from)\b.*?(?:numpy|pandas|scipy|matplotlib|opencv|cv2)\b"),
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
        # --- AI & LLM SDK SENSORS (GLOBAL_, see #322) ---
        "llm_api": GLOBAL_LLM_API,
        "llm_orchestrator": GLOBAL_LLM_ORCHESTRATOR,
        "llm_vector_store": GLOBAL_LLM_VECTOR_STORE,
        "ml_traditional": GLOBAL_ML_TRADITIONAL,
        "dl_frameworks": GLOBAL_DL_FRAMEWORKS,
        # 24. import (Dependency Inclusions)
        "import": re.compile(
            r"\b(?:from[ \t]+[a-zA-Z0-9_.]+[ \t]+import\b|import[ \t]+[a-zA-Z0-9_., \t]+|\b__import__[ \t]*\(|\bimportlib\.import_module[ \t]*\()",
            re.M,
        ),
        "_dependency_capture": re.compile(
            r"\bfrom[ \t]+([a-zA-Z0-9_.]+)[ \t]+import\b|"
            r"\bimport[ \t]+([a-zA-Z0-9_.]+(?:[ \t]*,[ \t]*[a-zA-Z0-9_.]+)*)|"
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
        # BUG FIX (Rule 14, #713): adjacent unbounded quantifiers with
        # overlapping character sets (`\d+` next to `[^\]]*`) -- the
        # same ReDoS shape already found and fixed independently in
        # embedded_python, css, tcl, matlab, scheme, typescript, rust, c,
        # cpp, csharp, groovy, shell, and sqlite earlier in this epic.
        # Bounded both quantifiers.
        "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d{1,10}|spec|audit)[^\]]{0,300}\]", re.I),
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
}
