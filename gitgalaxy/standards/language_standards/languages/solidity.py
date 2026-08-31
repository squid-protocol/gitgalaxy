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
        "target_version": "Solidity 0.8.20+ (Smart Contracts / Foundry / Hardhat)",
        "last_updated": "2026-04-01",
        "blueprint_version": "",
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
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch: Decisions that split flow. Includes Solidity 0.6+ try/catch.
        "branch": re.compile(r"\b(if|else|for|while|do|break|continue|return|try|catch)\b|\?"),
        # 2. args: Parameters / Coupling. Captures parameters for functions, errors, events, and modifiers.
        # Bounded `{0,50}` to prevent ReDoS on massive tuple returns or complex signatures.
        # #1209: parameter-list span wrapped in its own capture group in
        # both alternatives (was only reachable via group(0), the whole
        # match including the "function"/"modifier"/name prefix) so
        # detector.py's counter isolates just "(...)" -- the whole-match
        # fallback overcounted every zero/one-arg signature by +1 the same
        # way Python's did (#1199). Name group added to the first
        # alternative too, purely so existing extraction tests keep
        # passing.
        "args": re.compile(
            r"\b(?:function|modifier|error|event)\s+([a-zA-Z_]\w*\s*)?(\([^)]{0,500}\))|\b(?:constructor|fallback|receive)\s*(\([^)]{0,500}\))"
        ),
        # 3. linear: Sequential I/O & Network Boundaries. Structural boundaries defining scope and data definitions.
        "structural_boundaries": re.compile(
            r"\b(pragma|import|contract|interface|library|struct|enum|type|mapping|address|uint\d*|int\d*|bytes\d*|bool|string)\b"
        ),
        # 4. func_start: Executable Logic Anchors. Anchors executable logic (Functions, Modifiers, Custom Errors, Events).
        # LOOKAHEAD MANDATE APPLIED: Stops exactly at the identifier name before the parenthesis.
        "func_start": re.compile(
            r"^[ \t]*(?:function|modifier|error|event)\s+([a-zA-Z_]\w*)(?=\s*\()|^[ \t]*(constructor|fallback|receive)(?=\s*\()",
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
        # BUG FIX (ReDoS): the nested `[^)]+` was unbounded. Confirmed
        # quadratic scaling (0.18s/0.72s/2.86s/11.4s for n=5k/10k/20k/40k
        # -- ~4x per doubling) against a malformed/adversarial run of
        # `mapping(mapping(uint => ` tokens with no closing paren: at
        # each of the ~n candidate start positions where the outer
        # `mapping(` matches, the inner alternative's unbounded
        # `[^)]+` scans to the end of the string and fails, backtracking
        # across the whole remaining length -- O(n) work at each of
        # O(n) positions. Bounded to `{1,200}`, matching this same fix
        # shape used elsewhere in the sweep (fortran/php/shell/apex/
        # embedded_python) for "unbounded class immediately followed by
        # an often-absent literal suffix" ReDoS.
        "generics": re.compile(
            r"\bmapping\s*\([ \t\n]*[a-zA-Z0-9_]+\s*=>\s*(?:mapping\s*\([^)]{1,200}\)|[a-zA-Z0-9_]+)[ \t\n]*\)"
        ),
        # 21. comprehensions: Iterators / Comprehensions. Solidity lacks native comprehensions.
        "comprehensions": None,
        # 22. scientific: Numerical / Compute Libraries. Cryptographic hashing and elliptic curve recovery.
        "scientific": re.compile(r"\b(keccak256|sha256|ripemd160|ecrecover|addmod|mulmod)\b"),
        # 23. heat_triggers: Metaprogramming & Reflection. Low-level assembly injections and fallback routers.
        "reflection_metaprogramming": re.compile(r"\b(fallback|receive|assembly|delegatecall|call|staticcall)\b"),
        # 24. import: Dependency Inclusions. Resolving dependencies across files.
        "import": re.compile(
            r"^[ \t]*import\s+(?:(?:\{[^}]+\}|\*\s+as\s+[a-zA-Z_]\w*)\s+from\s+)?[\"'][^\"']+[\"'](?:\s+as\s+[a-zA-Z_]\w*)?;",
            re.M,
        ),
        # 24b. _dependency_capture: Graph resolution extracting exactly ONE path string.
        "_dependency_capture": re.compile(
            r"^[ \t]*import\s+(?:(?:\{[^}]+\}|\*\s+as\s+[a-zA-Z_]\w*)\s+from\s+)?[\"']([^\"']+)[\"'](?:\s+as\s+[a-zA-Z_]\w*)?;",
            re.M,
        ),
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
        # BUG FIX (Rule 14, #713): adjacent unbounded quantifiers with
        # overlapping character sets (`\d+` next to `[^\]]*`) -- the
        # same ReDoS shape already found and fixed independently in
        # embedded_python, css, tcl, matlab, scheme, typescript, rust, c,
        # cpp, csharp, groovy, shell, and sqlite earlier in this epic.
        # Bounded both quantifiers.
        "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d{1,10}|audit)[^\]]{0,300}\]|\b(ERC-\d+|EIP-\d+)\b", re.I),
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
        # BUG FIX: `.call{value:` and `emit\s+[A-Z]` were both inside the
        # shared \b(...)\b wrapper.
        # - `.call{value:` ends on `:` (non-word), so the trailing \b
        #   could only fire when a word char immediately followed --
        #   never true for the idiomatic spaced form
        #   `target.call{value: amount}(...)`, which is how this is
        #   always written in real Solidity.
        # - `emit\s+[A-Z]` only ever consumed a SINGLE uppercase letter
        #   (the char class has no `+`/`*`), so for any real
        #   multi-character event name (`emit Transfer(...)`) the char
        #   right after the matched letter is another word char --
        #   word-to-word is not a \b transition, so the trailing \b
        #   failed for every event name longer than one letter, which
        #   is effectively all of them.
        "ipc_rpc_bridges": re.compile(
            r"\b(?:delegatecall|staticcall|selfdestruct)\b|\.call\{value:|\bemit\s+[A-Z]\w*\b"
        ),
    },
}
