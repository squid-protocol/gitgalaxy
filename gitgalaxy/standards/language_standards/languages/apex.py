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

from .._shared_patterns import GLOBAL_FRAGILE_DEBT, GLOBAL_PLANNED_DEBT

DEFINITION: dict[str, Any] = {
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
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch: decisions that split flow. Includes switch on/when and DML try-catch.
        "branch": re.compile(
            r"\b(if|else|switch\s+on|when|for|while|do|try|catch|finally|break|continue|return)\b|&&|\|\||\?|\?\?",
            re.I,
        ),
        # 2. args: Parameters / Coupling. Captures method parameters and trigger event signatures.
        # #1209: parameter-list span wrapped in its own capture group in
        # both alternatives (was only reachable via group(0), the whole
        # match including the decorator/modifier/return-type/name prefix,
        # or for triggers the "trigger name on object" prefix) so
        # detector.py's counter isolates just "(...)" -- the whole-match
        # fallback overcounted every zero/one-arg signature by +1 the same
        # way Python's did (#1199). Name groups added too, purely so
        # existing extraction tests keep passing.
        "args": re.compile(
            # #1963: `new` is a reserved instantiation keyword, never a real return
            # type/modifier -- excluded from the optional prefix-consuming group so a
            # line-leading `new ClassName(...)` constructor-call argument (common in
            # multi-line SObject-builder calls) can't be parsed as "return type = new,
            # name = ClassName". Mirrors csharp's own GHOST ARGS SHIELD, which already
            # excludes `new` from its equivalent prefix group.
            r"^[ \t]*(?:@[\w.]+\b(?:\s*\((?:[^)(]|\([^)(]*\))*\))?\s*){0,5}"
            r"(?:(?:public|private|global|protected|static|override|virtual|abstract|testMethod)\s+){0,5}"
            r"(?:(?!new\b)[a-zA-Z_][\w.]*(?:\s*<(?:[^<>]|<(?:[^<>]|<(?:[^<>]|<[^<>]*>)*>)*>)*>)?(?:\s*\[\s*\])*\s+)?(?!(?:class|interface|enum|if|for|while|switch|catch)\b)([a-zA-Z_]\w*)\s*(\([^)]*\))|"
            r"^[ \t]*trigger\s+([a-zA-Z_]\w*)\s+on\s+[a-zA-Z_]\w*\s*(\([^)]*\))",
            re.M | re.I,
        ),
        # 3. linear: Sequential I/O & Network Boundaries. Structural boundaries. EXCLUDES access modifiers and sharing keywords.
        "structural_boundaries": re.compile(
            r"\b(class|interface|trigger|enum|final|transient|implements|extends|virtual|abstract|return)\b",
            re.I,
        ),
        # 4. func_start (Executable Logic Anchors)
        # ReDoS clamped to {0,5}. Strict capture groups and lookaheads for both Methods and Triggers.
        "func_start": re.compile(
            # #1221: the method branch used to have no requirement that
            # ANY of the annotation/modifier/return-type prefixes
            # actually be present -- all three are individually
            # optional/zero-allowed, so a bare call statement
            # (`next();`) with none of them satisfied the rest of the
            # branch identically to a real signature, since this
            # branch (like csharp's/apex's siblings) never verifies a
            # trailing `{`/`;` terminator either (that's left entirely
            # to the pipeline's own post-hoc brace search, same
            # historical shape #789 diagnosed for csharp). A real Apex
            # method/constructor always carries at least one of an
            # annotation, a modifier, or a return type before its name
            # (a bare call statement carries none of the three) -- so
            # gate the whole branch on seeing at least one of those
            # three shapes before letting the existing (unchanged)
            # optional-repeat groups consume them. Mirrors this same
            # regex's own `args` sibling ("GHOST ARGS SHIELD") pattern
            # of demanding structural proof before treating text as a
            # definition rather than an invocation.
            #
            # #1963: `new` is a reserved instantiation keyword, never a real return
            # type/modifier -- excluded from both the initial gating lookahead's
            # bare-identifier alternative and the optional prefix-consuming group so a
            # line-leading `new ClassName(...)` constructor-call argument (common in
            # multi-line SObject-builder calls) can't satisfy the #1221 gate as
            # "return type = new, name = ClassName". Mirrors csharp's own GHOST ARGS
            # SHIELD, which already excludes `new` from its equivalent prefix group.
            r"^[ \t]*(?=@|(?:public|private|global|protected|static|override|virtual|abstract|testMethod)\b|(?!new\b)[a-zA-Z_][\w.]*[ \t\n]+)"
            r"(?:@[\w.]+\b(?:\s*\((?:[^)(]|\([^)(]*\))*\))?\s*){0,5}"
            r"(?:(?:public|private|global|protected|static|override|virtual|abstract|testMethod)\s+){0,5}"
            r"(?:(?!new\b)[a-zA-Z_][\w.]*(?:\s*<(?:[^<>]|<(?:[^<>]|<(?:[^<>]|<[^<>]*>)*>)*>)*>)?(?:\s*\[\s*\])*\s+)?(?!(?:class|interface|enum|if|for|while|switch|catch)\b)([a-zA-Z_]\w*)(?=\s*\()|"
            r"^[ \t]*trigger\s+([a-zA-Z_]\w*)(?=\s+on\b)",
            re.M,
        ),
        # 5. class_start (Object / Entity Declarations)
        # ReDoS clamped. Strict capture group and positive lookahead applied.
        "class_start": re.compile(
            r"^[ \t]*(?:@[\w.]+\b(?:\s*\((?:[^)(]|\([^)(]*\))*\))?\s*){0,5}"
            r"(?:(?:public|private|global|virtual|abstract|with\s+sharing|without\s+sharing|inherited\s+sharing)\s+){0,5}"
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
        # BUG FIX: `@SuppressWarnings` is `@`-prefixed -- the shared
        # leading \b could only fire when a word char immediately
        # preceded the `@`, never true for how annotations are actually
        # written. Never matched at all.
        "safety_bypasses": re.compile(
            r"\b(?:without\s+sharing|Database\.query(?!\s*\(.*?WITH\s+SECURITY_ENFORCED))\b"
            r"|@SuppressWarnings|\(\s*[A-Z_]\w*\s*\)\s*[a-z_]\w*",
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
        # QUADRATIC BLOWUP FIX: the two `\w+` prefixes before the
        # required-but-often-absent `__c.getInstance`/`__mdt.getInstance`
        # suffixes were unbounded with no preceding \b anchor -- O(n^2)
        # on a long run of word characters with neither suffix present.
        # Bounded to {1,100}; real custom-object/metadata-type names
        # don't get remotely that long.
        "globals": re.compile(
            r"\b(UserInfo|System\.Label|Organization|Cache\.Org|Cache\.Session)\b|\w{1,100}__c\.getInstance\b|\w{1,100}__mdt\.getInstance\b",
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
            r"\bType\s*\.\s*forName\s*\(\s*['\"]([^'\"]+)['\"](?:[ \t\n]*,[ \t\n]*['\"]([^'\"]+)['\"])?\s*\)",
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
        # BUG FIX: `@SuppressWarnings` is `@`-prefixed -- same
        # leading-\b bug as safety_bypasses above.
        "test_skip": re.compile(r"\b(?:StubProvider|Test\.setMock)\b|@SuppressWarnings", re.I),
    },
}
