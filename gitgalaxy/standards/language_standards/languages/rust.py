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
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch (Control Flow / Branching)
        # Decisions and logical jumps. EXCLUDES panic!/throw (bailout_hits).
        "branch": re.compile(
            r"(?<!r#)(?<!')\b(if|else|match|for|while|loop|break|continue)\b|(?<=[a-zA-Z0-9_)\]}])\?(?!Sized\b)|&&|\|\|"
        ),
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
            # RULE 11 FIX (epic #813/#819): the generic step-over was still the flat
            # `<[^>]*>`, unlike func_start's own two-level-nesting idiom below (fixed earlier)
            # -- broke on any nested trait bound (`fn foo<T: Into<String>>(x: T) {`), a
            # realistic, common Rust pattern. Widened to match func_start's already-proven
            # two-level idiom.
            # =====================================================================
            # #1209: parameter-list span wrapped in its own capture group
            # in all three alternatives (was only reachable via group(0),
            # the whole match including the "fn"/"move"/name prefix) so
            # detector.py's counter isolates just the real parameter text
            # -- the whole-match fallback overcounted every zero/one-arg
            # signature by +1 the same way Python's did (#1199), including
            # a genuinely empty closure `|| ...`. Name group added to the
            # first alternative too, purely so existing extraction tests
            # keep passing.
            r"\bfn[ \t\n]+([a-zA-Z_]\w*)(?:[ \t\n]*<(?:[^<>-]|-(?!>)|->|<(?:[^<>-]|-(?!>)|->|<(?:[^<>-]|-(?!>)|->){0,100}>){0,100}>){0,100}>)?[ \t\n]*(\((?:[^)(]|\([^)]*\))*\))|\bmove[ \t\n]*\|([^|]*)\||(?:^|[=(,\[{<>;:])[ \t\n]*\|([^|]*)\|",
            re.M,
        ),
        # 3. linear (Sequential Boundaries)
        # Structural boundaries. EXCLUDES: Access modifiers (pub) and Immutability (const/static).
        "structural_boundaries": re.compile(
            r"(?<!r#)(?<!')\b(let|struct|enum|union|trait|impl|use|mod|type|yield|await|where|mut|ref|move|return)\b"
        ),
        # 4. func_start (Executable Logic Anchors)
        # ONLY executable logic blocks. EXCLUDES structs/traits to prevent False Positives.
        # BUG FIX (Rule 11, nested-delimiter coverage): the flat `[^>]*`
        # generic step-over broke on nested angle brackets in a trait
        # bound (`fn foo<T: Into<String>>` -- one level -- and
        # `fn foo<T: Clone + Into<Vec<u8>>>` -- two levels), both common
        # realistic Rust patterns -- func_start silently failed to match
        # the WHOLE function. Widened to tolerate two levels of
        # self-nesting (still non-overlapping alternatives, no new ReDoS
        # risk per the doc's own Rule 11 example).
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
            r"fn[ \t\n]+(?:r#)?([a-zA-Z_]\w*)(?:[ \t\n]*<(?:[^<>-]|-(?!>)|->|<(?:[^<>-]|-(?!>)|->|<(?:[^<>-]|-(?!>)|->){0,100}>){0,100}>){0,100}>)?[ \t\n]*(?=\()",
            re.M,
        ),
        # 5. class_start (Object / Entity Declarations)
        "class_start": re.compile(
            r"^[ \t]*(?:pub(?:\([^)]*\))?[ \t]+){0,3}(?:unsafe[ \t]+)?(?:auto[ \t]+)?(?:struct|enum|union|trait)\s+(?:r#)?([a-zA-Z_]\w*)",
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
        # BUG FIX: `panic!`/`todo!`/`unimplemented!` shared a trailing `\b`
        # with word-ending siblings, but all three end in `!` -- Rust
        # macro-invocation syntax is always immediately followed by `(` or
        # whitespace, both non-word, so `\b` could never fire. None of
        # these three -- among the most common constructs in any real Rust
        # file -- ever matched. Pulled out of the shared boundary group.
        "high_risk_execution": re.compile(r"panic!|todo!|unimplemented!|\b(?:process::exit|abort)\b"),
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
        # BUG FIX (Engine Rule 12, Comment-Style Completeness): rust is
        # `recursive_block` (both `//` and nested `/* */` are real
        # comment styles), but this only ever checked `//` -- a block-
        # commented-out function/struct (`/* fn foo() {} */`) was
        # invisible.
        "dead_code": re.compile(r"(?://|/\*)[ \t]*(?:fn|let|struct|impl|mod|use|match|for|while|loop|if|return)\b"),
        # 13. doc (Structured Documentation)
        "doc": re.compile(r"///|//!|#!?\[doc\b[^\]]*\]"),
        # 14. test (Testing & Assertions)
        # Triggers indicating internal verification. Anchors standard testing macros and prevents prose collisions for BDD frameworks (rstest/spec).
        # BUG FIX: `assert!`/`assert_eq!`/`assert_ne!` shared a trailing
        # `\b` with the word-ending `describe`/`it`/`test` group -- all
        # three end in `!`, always followed by `(` in real usage (never a
        # word char), so none of these extremely common assertion macros
        # ever matched.
        "test": re.compile(
            r"#\[(?:tokio::)?test\]|#\[cfg\(test\)\]|assert!|assert_eq!|assert_ne!|\b(?:describe|it|test)\s*\("
        ),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # 15. concurrency (Asynchronous Execution)
        "concurrency": re.compile(
            r"\b(async|await|std::thread|spawn|tokio::spawn|mpsc::|async_trait|Future|Stream|Send|Sync)\b"
        ),
        # 16. ui_framework (UI / View Components)
        # BUG FIX: `html!`/`rsx!`/`view!` shared a trailing `\b` with
        # word-ending siblings, but all three end in `!` -- these macro
        # invocations are always followed by `{`/`(`, never a word char,
        # so none of them -- Yew's/Dioxus's/Leptos's canonical templating
        # macros -- ever matched.
        "ui_framework": re.compile(r"\b(?:yew::|dioxus::|iced::|slint|leptos::|tauri::)\b|html!|rsx!|view!"),
        # 17. closures (Closures / Anonymous Functions)
        "closures": re.compile(r"\|[^|]*\|[ \t]*\{"),
        # 18. globals (Global / Shared State)
        # BUG FIX: `lazy_static!` shared a trailing `\b` with word-ending
        # siblings, but ends in `!` -- always followed by whitespace/`{`
        # in real usage (`lazy_static! { ... }`), never a word char.
        "globals": re.compile(r"\bstatic\s+mut\b|lazy_static!|\b(?:OnceCell|OnceLock|LazyLock|std::env::var)\b"),
        # 19. decorators (Decorators / Annotations)
        "decorators": re.compile(r"^[ \t]*#!?\[[^\]]*\]", re.M),
        # 20. generics (Generics / Type Parameters)
        "generics": re.compile(r"<\s*[A-Z\'][^>]*>|\bwhere\b|\'[a-z]+\b|\bimpl\s+[A-Z]\w+"),
        # 21. comprehensions (Iterators / Comprehensions)
        "comprehensions": re.compile(r"\.(?:map|filter|fold|collect|flat_map|any|all|reduce|for_each|find|zip)\s*\("),
        # 22. scientific (Numerical / Compute Libraries)
        "scientific": re.compile(r"\b(ndarray::|nalgebra::|num::|f32|f64|std::simd)\b"),
        # 23. heat_triggers (Metaprogramming & Reflection)
        # Metaprogramming and memory transmutation.
        # BUG FIX: `macro_rules!` shared a trailing `\b` with word-ending
        # siblings, but ends in `!` -- always followed by whitespace/`{`
        # in real usage (`macro_rules! foo { ... }`), never a word char.
        "reflection_metaprogramming": re.compile(
            r"macro_rules!|\b(?:std::mem::transmute|Pin::|PhantomData|UnsafeCell)\b"
        ),
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
            # GLOB IMPORT FIX (epic #813/#819): the character class was missing `*`, so a glob
            # import (`use std::io::*;`, extremely common Rust for re-exporting a module's
            # entire public surface) didn't match at all -- the whole `use` statement was
            # invisible to the dependency graph.
            # =====================================================================
            r"\b(?:pub[ \t]+)?use\s+([a-zA-Z0-9_:{},*\s]+);",
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
        # BUG FIX: adjacent unbounded quantifiers with overlapping
        # character sets (`\d+` next to `[^\]]*`) -- the same ReDoS
        # shape already found and fixed independently in
        # embedded_python, css, tcl, matlab, scheme, and typescript
        # earlier in this epic. Bounded both quantifiers.
        "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d{1,10}|spec|audit)[^\]]{0,300}\]", re.I),
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
        # BUG FIX: same `macro_rules!` trailing-`\b`-after-`!` defect as
        # reflection_metaprogramming's copy above.
        "macros": re.compile(r"macro_rules!|\b(?:proc_macro|proc_macro_derive|proc_macro_attribute)\b"),
        # 35. pointers (Pointer Arithmetic / Memory Addressing)
        # Raw memory addressing. Shielded from standard multiplication by explicitly mapping to native Rust unsafe pointer primitives and dereferencing.
        "pointers": re.compile(r"\*const\b|\*mut\b|\bNonNull\b|\bstd::ptr\b|->"),
        # 36. memory_alloc (Manual Memory Management)
        "memory_alloc": re.compile(
            r"\b(Box::new|Rc::new|Arc::new|Vec::with_capacity|String::with_capacity|alloc::|GlobalAlloc)\b"
        ),
        # 37. inline_asm (The Bare Metal)
        # BUG FIX: all four alternatives end in `!` (Rust macro-invocation
        # syntax), but shared a trailing `\b` -- `asm!(...)` is always
        # followed by `(`, never a word char, so none of these -- the
        # ONLY way to write inline assembly in Rust -- ever matched.
        "inline_asm": re.compile(r"\bcore::arch::asm!|\bstd::arch::asm!|\basm!|\bglobal_asm!"),
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # 38. telemetry (Structured Logging / Telemetry)
        # BUG FIX: `info!`/`warn!`/`error!`/`debug!`/`trace!`/`span!` all
        # end in `!` but shared a trailing `\b` with `instrument` -- Rust
        # macro-invocation syntax is always followed by `(`, never a word
        # char, so none of the tracing/log macros ever matched.
        "telemetry": re.compile(r"\b(?:log::|tracing::)?(?:info|warn|error|debug|trace|span)!|\binstrument\b"),
        # 39. debug_prints (Debug Artifacts / Unstructured Outputs) (Standard Output / Debug Prints)
        # BUG FIX: all five alternatives end in `!` but shared a trailing
        # `\b` -- `println!("...")` is always followed by `(`, never a
        # word char, so none of these -- arguably the single most common
        # construct in any real Rust codebase -- ever matched.
        "debug_prints": re.compile(r"\b(?:println|print|eprintln|eprint|dbg)!"),
        # # 40. explicit_casts (Explicit Type Casting)
        # Forceful type coercion bypassing the safety engine. Enforces strict mapping to the `as` keyword followed by standard primitive types.
        "explicit_casts": re.compile(
            r"\bas\s+(?:i8|i16|i32|i64|i128|isize|u8|u16|u32|u64|u128|usize|f32|f64|bool|char)\b"
        ),
        # 41. panics_and_aborts (Execution Interrupts / Fatal Aborts)
        # BUG FIX: same `panic!` trailing-`\b`-after-`!` defect as
        # high_risk_execution's copy above.
        "panics_and_aborts": re.compile(r"panic!|\b(?:abort|process::exit|fatalError)\b"),
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
}
