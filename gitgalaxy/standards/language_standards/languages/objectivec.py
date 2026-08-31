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
    # #377: the symmetric counterpart to matlab's disqualifiers above -- heavy
    # presence of MATLAB's own ecosystem anchors elsewhere in the repo is
    # direct evidence AGAINST an ambiguous .m file being Objective-C.
    "disqualifiers": [".mat", ".fig", ".mlx", "project.prj"],
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
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch: Decisions that split flow. Includes Obj-C specific @try/@catch blocks.
        # BUG FIX: @try/@catch/@finally were inside the shared \b(...)\b
        # group. \b requires a word/non-word transition, but `@` is
        # non-word, so the leading \b could never match once `@` was
        # preceded by anything else non-word (a space, line start) --
        # meaning these 3 alternatives never actually matched real code.
        "branch": re.compile(
            r"\b(if|else|switch|case|default|for|while|do|break|continue|return|goto)\b|@(try|catch|finally)\b|&&|\|\||\?"
        ),
        # 2. args: Parameters / Coupling. Captures method parameters (colons), C-style args, and Blocks (^).
        "args": re.compile(
            # =====================================================================
            # [ THE GHOST ARGS & BLOCK SHIELD (OBJECTIVE-C) ]
            # Objective-C functions look like standard C functions. The previous regex
            # `\b[a-zA-Z_]\w*\s*\([^)]*\)\s*(?:\{|;)` hallucinated `if (a) {` as a function.
            # FIX: Injected `(?!(?:if|for|while|switch|catch|return)\b)` to block control flow.
            # =====================================================================
            # #1209: branch 1 (keyword-message selectors) now captures
            # the WHOLE repeated `label:(Type)name label:(Type)name ...`
            # span in one group instead of matching just the FIRST
            # segment on its own -- the old single-segment match had no
            # way to represent "this method takes 2+ parameters" at all
            # (no commas exist in this syntax to count), so every
            # multi-param method silently undercounted to 1 regardless of
            # its real arity, and the unanchored single-segment form
            # could even false-match a `:(Type)` cast expression sitting
            # inside a DIFFERENT method's body. detector.py's
            # `_count_colon_selector_segments` counts the real parameter
            # count from this span by counting top-level `:`
            # occurrences (one per segment) instead of commas. Branches
            # 2/3 (Blocks and plain C-style functions) get the same
            # capture-group treatment as every other C-family language.
            #
            # #1335: the `(Type)` cast used to be REQUIRED after every
            # `label:`, so older, still-valid untyped keyword-message
            # style (`- back:sender`, defaulting to `id`, common in
            # 1990s NeXTSTEP-era code -- language-crucible/data/
            # objective-c/worldwideweb/HyperManager.m has ~20 of these
            # in one file) matched zero segments here and silently
            # undercounted to args=0. Added a SECOND, separate
            # alternative for this shape rather than loosening the
            # existing typed one in place -- the original
            # `(?:label)?:(Type)name` (label optional, type mandatory)
            # stays completely unchanged (every pre-#1335 valid/invalid
            # case for it is untouched), and the new
            # `label:name` (label MANDATORY, no type) alternative is
            # additive. The label is mandatory here specifically because
            # every real keyword-message parameter has one -- this loses
            # no real match, only narrows what an untyped segment can be.
            #
            # This still can't structurally tell a real untyped param
            # (`back:sender`) apart from a body-only lookalike with the
            # exact same shape -- a goto label followed by a statement
            # (`label: statement;`) or a ternary's true-branch read as a
            # label (`cond ? isOn : isOff`, "isOn" here IS a syntactically
            # valid label) -- because those are lexically identical to a
            # real untyped parameter; no local, bounded regex can
            # distinguish them without knowing it's inside a method
            # signature already. That's WHY this alternative is safe only
            # because detector.py's `_slice_by_braces` now bounds the
            # whole `args` search to the method's own signature text for
            # objc specifically (never the body), making a body-only
            # lookalike structurally unreachable in the real pipeline --
            # see `_calculate_block_metrics`'s `args_search_text` param
            # and tests/core_engine/test_detector.py's
            # test_objectivec_args_body_lookalikes_excluded_by_signature_bound.
            # In ISOLATION (the regex alone, as the adversarial test
            # gauntlet in tests/extraction/languages/test_objectivec.py
            # exercises it) these lookalikes DO still match -- a
            # documented, pipeline-shielded limitation, the same shape as
            # the pre-existing comment/string-lookalike one just below in
            # this same file's test suite.
            r"((?:(?:[a-zA-Z_]\w{0,80}[ \t\n]*)?:\s*\([^()]*(?:\([^()]*(?:\([^()]*\)[^()]*)*\)[^()]*)*\)\s*[a-zA-Z_]\w*[ \t\n]*|[a-zA-Z_]\w{0,80}[ \t\n]*:\s*[a-zA-Z_]\w*[ \t\n]*)+)|\^[ \t]*([a-zA-Z_]\w*\s*)?(\([^()]*(?:\([^()]*(?:\([^()]*\)[^()]*)*\)[^()]*)*\))|(?!(?:if|for|while|switch|catch|return|sizeof)\b)\b([a-zA-Z_]\w*)[ \t\n]*(\([^()]*(?:\([^()]*(?:\([^()]*\)[^()]*)*\)[^()]*)*\))[ \t\n]*(?:\{|;)",
            re.M,
        ),
        # Which `args` capture-group index represents an objc
        # keyword-message colon-selector span (routes to
        # `_count_colon_selector_segments` in detector.py rather than
        # the generic comma/whitespace counters) -- see the comment on
        # `args` above. Leading underscore excludes this from the
        # structural-signal scan loop, same convention as haskell's
        # `_args_arrow_count_groups`.
        "_args_colon_selector_groups": {1},
        # 3. linear: Sequential I/O & Network Boundaries. Structural boundaries defining interface, implementation, and memory types.
        # BUG FIX: the 8 @-prefixed alternatives never matched -- same
        # \b-before-@ shape as branch's fix above.
        "structural_boundaries": re.compile(
            r"@(interface|implementation|protocol|end|synthesize|dynamic|class|import)\b|\b(typedef|struct|enum|union|__block|__weak|__strong)\b"
        ),
        # 4. func_start: Executable Logic Anchors. Anchors executable logic.
        # The Critical Fix: Compiled with re.M and optional return types for TBL / NeXTSTEP syntax
        # #1336: injected a "not a function" shield -- `(?!(?:if|for|...)\b)` -- right before
        # the C-style alternative's (?:type-token)+ loop. Without it, this alternative already
        # matched bare two-token call/return statements like `return foo(x);` (any single
        # leading word satisfies the loop as a fake "return type") -- previously "harmless"
        # only because detector.py's brace-only fallback silently dropped the match when no
        # `{` followed nearby, but a `{` from unrelated later code (e.g. a neighboring
        # `@interface` block's own ivar-list braces) could still get wrongly attributed as
        # this phantom "function"'s body. `_slice_by_braces`'s objc branch now explicitly
        # detects and rejects the bodyless-`;` case for this alternative (prototypes have no
        # body to score, so they're out of func_start's scope, not a recall gap) instead of
        # falling through to that blind forward search -- this shield is what makes a bare
        # statement safe to have reach that rejection path at all, rather than being
        # misidentified as a genuine prototype. Blocks exactly the same control-flow-keyword
        # set `branch` above already treats as non-function-starting, so real prototypes
        # (`extern void foo(T x);`, whose leading token is always a type/modifier, never a
        # keyword) are unaffected.
        "func_start": re.compile(
            r"^[ \t]*(?:[A-Z_0-9]+\s+|__attribute__\s*\([^()]*(?:\([^()]*\)[^()]*)*\)\s+)*[-+][ \t\n]*(?:\([^()]*(?:\([^()]*(?:\([^()]*\)[^()]*)*\)[^()]*)*\)[ \t\n]*|(?:[a-zA-Z_]\w*[ \t\n]+){1,3})?([a-zA-Z_]\w*)(?=[ \t\n]*(?:__attribute__\s*\([^()]*(?:\([^()]*\)[^()]*)*\)|[A-Z_0-9]+(?:\([^)]*\))?)*[ \t\n]*[:\{;]|$)|"
            r"^[ \t]*(?:(?:static|inline|extern|__attribute__\s*\([^()]*(?:\([^()]*\)[^()]*)*\)|template\s*<[^>]*>)[ \t\n]+)*"
            r"(?!(?:if|for|while|switch|return|else|case|default|do|break|continue|goto|sizeof|catch)\b)"
            r"(?:(?:\b[a-zA-Z_]\w*\b|extern\s+\"C\")[ \t\n]*(?:\*[ \t\n]*)*)+([a-zA-Z_]\w*)(?=[ \t\n]*\()",
            re.M,
        ),
        # 5. class_start: Object / Entity Declarations. Defines OO boundaries.
        "class_start": re.compile(
            r"^[ \t]*@\s*(?:interface|implementation|protocol)(?:\\?\s)+([a-zA-Z_]\w*)(?=(?:\\?\s)*(?:[:(<{/\n]|$))",
            re.M,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        # 6. safety: Defensive Programming. ARC memory qualifiers and Cocoa/NeXT Assertions.
        # BUG FIX: @try/@catch/@finally never matched -- same \b-before-@
        # shape as branch's fix above.
        "safety": re.compile(
            r"@(try|catch|finally)\b|\b(__weak|__strong|__auto_type|NSAssert|NSParameterAssert|NSError|nil|Nil)\b"
        ),
        # 7. safety_neg: Safety Bypasses. Bypassing ARC, raw void pointers, and dangerous dynamic selectors.
        # BUG FIX: `void\s*\*` (trailing \b after a literal `*`) and
        # `performSelector:` (trailing \b after a literal `:`) only
        # matched when immediately followed by another non-word char
        # (rare -- an identifier or `@selector(...)` almost always
        # follows in real code). Dropped the trailing \b for both;
        # also dropped the now-redundant "performSelector:withObject:"
        # alternative, since "performSelector:" already matches as its
        # prefix (alternation tries left-to-right and returns first hit).
        "safety_bypasses": re.compile(
            r"\b(__unsafe_unretained|unsafe_unretained|id)\b|void\s*\*|performSelector:|!\s*[;,\]\)\.]|#pragma\s+clang\s+diagnostic\s+ignored"
        ),
        # 8. danger: High-Risk Execution. Process killers.
        "high_risk_execution": re.compile(r"\b(abort|exit)\b"),
        # 9. io: I/O & Network Boundaries. Disk, Network, and URL fetching (Includes NeXTSTEP NX prefixes & TBL WWW wrappers).
        "io": re.compile(
            r"\b(NSFileHandle|NSFileManager|NSURLSession|NSURLConnection|NSData|NXNetPath|NXSocket|NXStream|NXFile|HTLoad|HyperText|HTGet|socket|connect|send|recv)\b"
        ),
        # 10. api: Public Surface Area. Exposed interface/C-level exports and Interface Builder hooks.
        "api": re.compile(r"\b(FOUNDATION_EXPORT|UIKIT_EXTERN|OBJC_EXPORT|extern)\b|@(property)\b|IBOutlet|IBAction"),
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
        # BUG FIX: @synchronized never matched -- same \b-before-@ shape
        # as branch's fix above.
        "concurrency": re.compile(
            r"\b(dispatch_async|dispatch_sync|dispatch_once|dispatch_queue_t|NSOperation|NSThread|NSLock|NXConditionLock)\b|@(synchronized)\b"
        ),
        # 16. ui_framework: UI / View Components. Cocoa, UIKit, and AppKit hierarchies (Includes legacy NX classes).
        "ui_framework": re.compile(
            r"\b(UIView|UIViewController|UIWindow|NSView|NSWindow|NXWindow|NXApp|NXBrowser|NXText|Text|ScrollView|HyperText|WorldWideWeb|SGML)\b"
        ),
        # 17. closures: Closures / Anonymous Functions. Objective-C Blocks.
        "closures": re.compile(r"\^[ \t]*(?:[a-zA-Z_]\w*\s*)?\s*\([^)]*\)[ \t]*\{"),
        # 18. globals: Global / Shared State. Singleton/Shared instance access.
        # BUG FIX: the two bracket-message alternatives never matched --
        # `\b` requires a word/non-word transition, but `[`/`]` are both
        # non-word, so both the leading and trailing \b could never
        # match once flanked by anything else non-word (a space,
        # semicolon, line start). Split them out of the shared wrapper.
        "globals": re.compile(
            r"\b(extern|NSUserDefaults|NXDefaults|NXApp)\b|\[UIApplication\s+sharedApplication\]|\[NSWorkspace\s+sharedWorkspace\]"
        ),
        # 19. decorators: Decorators / Annotations. Attributes and Property decorators.
        "decorators": re.compile(r"\b__attribute__\s*\(\([^)]*\)\)|@property\s*\([^)]+\)"),
        # 20. generics: Generics / Type Parameters. Lightweight generics (introduced in Xcode 7).
        "generics": re.compile(r"<\s*[A-Z][^>]*\s*\*?\s*>"),
        # 21. comprehensions: Iterators / Comprehensions. Block-based array/set enumeration.
        # BUG FIX: the trailing \b (after a literal `:`) never matched --
        # `:` is non-word, so the boundary only worked when followed by
        # another non-word char, which is rare in real Obj-C selector
        # syntax (a block or argument almost always follows). Moved the
        # \b to before the colon instead, where it correctly applies to
        # the preceding word character.
        "comprehensions": re.compile(
            r"\b(?:enumerateObjectsUsingBlock|filteredArrayUsingPredicate|makeObjectsPerformSelector)\b:"
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
            r"^[ \t]*(?:#\s*import|#\s*include)\s*(?:\\?\n\s*)?(?:<([^>]+)>|[\"']([^\"']+)[\"'])|^[ \t]*@\s*import\s+([\w.]+)",
            re.M,
        ),
        # 25. ownership: Authorship metadata.
        # BUG FIX: `@author` (leading \b before non-word `@`) and
        # `Author:` (trailing \b after non-word `:`) never matched --
        # same shape as branch's @try fix above.
        "ownership": re.compile(r"\b(?:Created by|Copyright|Tim Berners-Lee)\b|@author|\bAuthor:", re.I),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        "planned_debt": GLOBAL_PLANNED_DEBT,
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        # BUG FIX (Rule 14, #713): adjacent unbounded quantifiers with
        # overlapping character sets (`\d+` next to `[^\]]*`) -- the
        # same ReDoS shape already found and fixed independently in
        # embedded_python, css, tcl, matlab, scheme, typescript, rust, c,
        # cpp, csharp, groovy, shell, and sqlite earlier in this epic.
        # Bounded both quantifiers.
        "spec_exposure": re.compile(
            r"\[(?:\s*SPEC\s*-\s*\d{1,10}|spec|audit|RFC|W3C|CERN|TBL|ENQUIRE)[^\]]{0,300}\]|\b(?:WorldWideWeb|HyperText\s+Proposal|NeXTSTEP\s+Docs)\b",
            re.I,
        ),
        "ssr_boundaries": re.compile(r"\b(WOComponent|WOResponse|WOContext|WOApplication|WODirectAction|WebObjects)\b"),
        "events": re.compile(r"\b(NSNotificationCenter|addObserver|postNotification|NXApp\s+run|sendEvent)\b"),
        # BUG FIX: `inject:`/`initWithDependency:` (trailing \b after a
        # literal `:`) only matched when immediately followed by another
        # non-word char -- true for a plain identifier argument, but
        # false for the equally common `@selector(...)` argument form.
        # Moved the \b to before the colon instead.
        "dependency_injection": re.compile(
            r"\b(TyphoonComponentFactory|TyphoonDefinition|JSObjection)\b|\b(?:inject|initWithDependency)\b:"
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
        # BUG FIX: @throw never matched -- same \b-before-@ shape as
        # branch's fix above.
        "panics_and_aborts": re.compile(r"@(throw)\b|\b(abort|exit)\b"),
        # 42. thread_sleeps (Thread Blocking / Synchronous Pauses) Forcing threads to sleep.
        "thread_sleeps": re.compile(r"\b(sleep|usleep|nanosleep)\s*\("),
        # 43. bitwise_ops (Bitwise Operations)
        "bitwise_ops": re.compile(r"(?<!&)&(?!&)|(?<!\|)\|(?!\|)|<<|>>|\^|~"),
        # 44. sync_locks (Resource Management & Stability) Coordinated threading logic.
        # BUG FIX: @synchronized never matched -- same \b-before-@ shape
        # as branch's fix above.
        "sync_locks": re.compile(
            r"@(synchronized)\b|\b(NSLock|NSRecursiveLock|NSConditionLock|dispatch_semaphore_wait)\b"
        ),
        # 45. immutability_locks (Immutability Constraints) Immutability.
        "immutability_locks": re.compile(r"\b(const|readonly|immutable)\b"),
        # 46. cleanup (Resource Cleanup / Teardown) Resource release (Crucial for MRC NeXT era).
        "cleanup": re.compile(r"\b(dealloc|release|autorelease|free|NX_FREE)\b"),
        # 47. encapsulation Hiding logic from the application.
        # BUG FIX: the leading \b before `@` never matched (same shape as
        # branch's fix above). The trailing \b is fine as-is (each
        # keyword ends in a letter).
        "encapsulation": re.compile(r"@(?:private|protected|package)\b"),
        # 48. listeners (Event Listeners / Observers) Waiting for state broadcasts.
        # BUG FIX: trailing \b after a literal `:` only matched when
        # immediately followed by another non-word char -- true for a
        # plain identifier argument, false for the equally common
        # `@selector(...)` argument form. Moved the \b to before the colon.
        "listeners": re.compile(r"\b(?:addObserver|observeValueForKeyPath|subscribeNext)\b:"),
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
        "ipc_rpc_bridges": re.compile(r"\b(NSXPCConnection|NSTask|NSPipe|NSURLConnection|NSURLSession|NSMachPort)\b"),
    },
}
