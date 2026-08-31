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
    # Maps to Family 4 (Hybrid Hash) -- #621: this comment always said
    # "Family 4 (Hybrid Hash)" but the value below was "standard_block"
    # until now, meaning PowerShell shared a regex with C-style languages
    # and got zero comment stripping (standard_block never used the `#`
    # token). "embedded_syntax" is the real family for this shape.
    # Rationale: PowerShell uses '#' for single-line comments but relies on
    # a unique '<# #>' syntax for multi-line block comments, requiring hybrid parsing logic.
    "lexical_family": "embedded_syntax",
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # branch: decisions that split flow. Includes ternary operators (?) and null-coalescing (??).
        "branch": re.compile(
            r"(?<![-$.])\b(if|else|elseif|switch|for|foreach|while|do|until|try|catch|finally|throw|trap|break|continue|return)\b|-and|-or|-not|-xor|\?\?|(?<=\s)\?(?=\s|\{)",
            re.I,
        ),
        # args: Parameters / Coupling. Captures the param block mass of functions and script files.
        # RULE 11 FIX (epic #813/#834): both alternatives used the flat `\([^)]*\)`,
        # truncating at the FIRST `)` and breaking on a realistic default-value expression
        # containing its own parens (`param($Config = (Get-DefaultConfig))`, extremely common
        # for computed defaults) -- the paren variant of the same Rule-11 bug class already
        # fixed for angle- and square-bracket generics elsewhere. Widened to the established
        # one-level-nesting idiom.
        # MISSING-DECLARATION-SHAPE FIX (epic #813/#834): PS class constructors
        # (`Foo([string]$name) { ... }`) have no leading `function` keyword and no return-type
        # bracket, so their parameter list was invisible to this rule entirely -- added as a
        # third alternative, anchored to a trailing `{` (not just optional) specifically so it
        # can't also match a bare call statement (`Foo($a, $b)` with no body), which PowerShell
        # constructors/methods always have and bare calls never do immediately on the same line.
        # SCOPE-QUALIFIER FIX (epic #813/#834): PowerShell allows an explicit scope modifier
        # before a function name (`function global:Foo(...)`, also `script:`/`local:`/
        # `private:`, a real idiom for module-authored functions that need global-scope
        # visibility). The identifier class `[a-zA-Z0-9_-]+` doesn't include `:`, so the whole
        # alternative failed to match at all past the scope prefix -- added as an optional
        # non-capturing step-over before the name.
        # NEW-ALTERNATIVE FALSE-POSITIVE FIX (epic #813/#834): the bare-identifier constructor
        # alternative just above, on its own, ALSO matched PowerShell's own control-flow
        # statements -- `if (...) {`, `while (...) {`, `switch (...) {`, `for (...) {`,
        # `foreach (...) {`, `elseif (...) {` all share the exact "identifier, parens, trailing
        # brace" shape a constructor call has. Caught by hand-testing the fix's own "invalid"
        # case (`if ($a -eq $b) {`) before shipping, not by crucible (matches recurring class 21's
        # lesson about a new alternative's own blind spots -- here at authoring time instead of
        # via a corpus diff). Fixed with a negative-lookahead keyword exclusion.
        # #1209: parameter-list span wrapped in its own capture group in
        # all three branches (was only reachable via group(0), the whole
        # match including the "param"/"function"/name prefix) so
        # detector.py's counter isolates just "(...)" -- the whole-match
        # fallback overcounted every zero/one-arg signature by +1 the
        # same way Python's did (#1199). Name groups added to branches
        # 2/3 too, purely so existing extraction tests keep passing.
        "args": re.compile(
            r"\b(param)\s*(\((?:[^()]|\([^()]*\))*\))"
            r"|\bfunction\s+(?:(?:global|script|local|private):)?([a-zA-Z0-9_-]+)\s*(\((?:[^()]|\([^()]*\))*\))"
            r"|^[ \t]*(?:(?:hidden|static)\s+)*(?:\[(?:[^\[\]]|\[[^\[\]]*\])+\]\s+)?"
            r"(?!(?:if|elseif|switch|while|for|foreach|until|trap|catch)\b)"
            r"([A-Za-z_]\w*)\s*(\((?:[^()]|\([^()]*\))*\))\s*[ \t\n]*\{",
            re.I | re.M,
        ),
        # linear: Sequential I/O & Network Boundaries. Structural boundaries defining scope (process, begin, end).
        # EXCLUDES access modifiers (hidden, static) to prevent Structural Complexity Inflation.
        "structural_boundaries": re.compile(
            r"(?<![-$.])\b(?:(?:function|filter|workflow|configuration|class|enum)\s+[a-zA-Z_]"
            r"|(?:process|begin|end|clean)\s*\{"
            r"|(?:return|exit)\b(?![-])"
            r"|using\s+(?:namespace|module)\b)",
            re.I,
        ),
        # func_start: Executable Logic Anchors. Anchors executable logic blocks.
        # EXCLUDES class/enum to fix False Positives.
        # BUG FIX: the return-type bracket class `[^\]]+` couldn't
        # represent one level of nested brackets, so a PS class method
        # with a generic .NET return type (e.g.
        # `[Dictionary[string,int]] GetMap() {` /
        # `[System.Collections.Generic.List[string]] GetItems() {`) --
        # a common real-world form -- never matched at all, unlike the
        # identical non-generic form (`[int] GetValue() {`), which did.
        # MISSING-DECLARATION-SHAPE FIX (epic #813/#834): PS class constructors
        # (`Foo([string]$name) { ... }`) have neither a leading `function` keyword nor a
        # return-type bracket, so they were entirely invisible to this rule (only typed
        # methods and `function`-keyword declarations matched). Added as a third
        # alternative, anchored to a trailing `{` (not just optional) specifically so it
        # can't also match a bare call statement (`Foo($a, $b)` with no body) -- PowerShell
        # constructors/methods always have a body immediately following on the same
        # logical statement, and a bare call never continues into an unrelated `{` like
        # that in realistic code.
        # SCOPE-QUALIFIER FIX (epic #813/#834): PowerShell allows an explicit scope modifier
        # before a function name (`function global:Foo {}`, also `script:`/`local:`/
        # `private:`). The identifier class doesn't include `:`, so the capture greedily
        # consumed only the SCOPE KEYWORD itself (e.g. "global") as if it were the function
        # name, silently returning a wrong name rather than failing to match -- worse than a
        # non-match. Added an optional non-capturing step-over before the name.
        # NEW-ALTERNATIVE FALSE-POSITIVE FIX (epic #813/#834): same as `args` above -- the
        # bare-identifier constructor alternative just below also matched PowerShell's own
        # control-flow statements (`if (...) {`, `while (...) {`, `switch (...) {`, `for (...)
        # {`, `foreach (...) {`, `elseif (...) {`). Fixed with the same negative-lookahead
        # keyword exclusion.
        "func_start": re.compile(
            r"^[ \t]*(?:function|filter|workflow)\s+(?:(?:global|script|local|private):)?([a-zA-Z0-9_-]+)"
            r"|^[ \t]*(?:(?:hidden|static)\s+)*\[(?:[^\[\]]|\[[^\[\]]*\])+\]\s+(?!(?:if|elseif|switch|while|for|foreach|until|trap|catch|param)\b)([a-zA-Z_]\w*)(?=\s*\()"
            r"|^[ \t]*(?:(?:hidden|static)\s+)*(?!(?:if|elseif|switch|while|for|foreach|until|trap|catch|param)\b)"
            r"([A-Za-z_]\w*)\s*\((?:[^()]|\([^()]*\))*\)\s*[ \t\n]*\{",
            re.I | re.M,
        ),
        # class_start: Object / Entity Declarations. Defines OO boundaries (Classes and Enums).
        # #1295-adjacent: no capture group around the name meant every match collapsed into
        # "Anonymous_Class" in the named-extraction path -- powershell has been in
        # _CLASS_START_NAMED_EXTRACTION_LANGS since #1264, but this specific gap was never
        # caught (real_classes=5 in the corpus, found_classes=0). Purely additive change --
        # doesn't alter which lines match or how many, only makes match.groups() richer.
        "class_start": re.compile(r"^[ \t]*(?:class|enum)\s+([a-zA-Z_]\w*)", re.I | re.M),
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
        # BUG FIX: `-Parallel` starts with `-` (non-word), so the
        # shared leading \b could only fire when a word char
        # immediately preceded the `-` -- never true for how this
        # ForEach-Object flag is actually written (preceded by
        # whitespace). PS7's parallel pipeline feature never matched.
        "concurrency": re.compile(
            r"\b(?:Start-Job|Wait-Job|Receive-Job|Start-ThreadJob|RunspaceFactory|PowerShell\.Create)\b|-Parallel\b",
            re.I,
        ),
        # ui_framework: UI / View Components. WinForms/WPF bridges (Includes TBL WWW rendering emulation triggers).
        "ui_framework": re.compile(
            r"\[System\.Windows\.(?:Forms|Controls|Markup)\]|New-Object\s+System\.Windows\.|Out-GridView|HtmlDocument|WebBrowser|SGML|WorldWideWeb",
            re.I,
        ),
        # closures: Closures / Anonymous Functions. ScriptBlocks (The foundation of PS closures).
        # BUG FIX (ReDoS): the unbounded `[^}]*` before the closing `}`,
        # combined with unanchored search, is O(n^2) on payloads with many
        # `{` and no matching `}` (each of the n starting positions scans
        # ~n chars before failing) -- confirmed via scaling measurements
        # (~4x slowdown per input-size doubling). Bounded quantifiers cap
        # the per-position scan cost, same fix shape as go/dart closures.
        "closures": re.compile(r"\{\s{0,20}(?:param\s{0,10}\([^)]{0,300}\))?[^}]{0,500}\}", re.I),
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
        # BUG FIX: the dot-sourcing alternative (`. .\script.ps1`)
        # starts with `.` (non-word), so the shared leading \b could
        # only fire when a word char immediately preceded the `.` --
        # never true for how dot-sourcing is actually written (always
        # preceded by whitespace or a line start). This common
        # PowerShell module-loading idiom never matched at all.
        "import": re.compile(
            r"\b(?:Import-Module|using\s+module|using\s+namespace|using\s+assembly)\b|\.\s+[\w.\/\\]+\.ps1\b",
            re.I,
        ),
        # --- UPDATED LINE FOR THE ORCHESTRATOR ---
        # BUG FIX (epic #813/#834): the quoted-path branches used `['\"]?...['\"]?` -- an
        # OPTIONAL quote pair around a capture class that excludes `\s` regardless of whether
        # a quote is actually present. So a quoted path containing a space (e.g. the extremely
        # common Windows `'C:\Program Files\MyModule\MyModule.psd1'`) silently truncated at the
        # first space, losing everything after it. Replaced the single optional-quote capture
        # with three real alternatives per import form (single-quoted / double-quoted / bare):
        # a quoted capture now allows any character except its own quote (so spaces are fine),
        # while the bare (unquoted) form keeps the original space/semicolon exclusion, since an
        # unquoted PowerShell path genuinely cannot contain a space.
        "_dependency_capture": re.compile(
            r"^[ \t]*(?:Import-Module|using[ \t\n]+(?:module|namespace|assembly))[ \t\n]+"
            r"(?:'([^'\n]+)'|\"([^\"\n]+)\"|([^'\"\s;]+))"
            r"|^[ \t]*\.[ \t\n]+"
            r"(?:'([^'\n]+\.ps1)'|\"([^\"\n]+\.ps1)\"|([^'\"\s;]+\.ps1))",
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
        # BUG FIX: `-match`/`-replace`/`-split` all start with `-`
        # (non-word), so the shared leading \b could only fire when a
        # word char immediately preceded the `-` -- never true for how
        # these operators are actually written (always preceded by
        # whitespace, after the left-hand operand). PowerShell's THREE
        # most common native regex operators never matched at all.
        # Same shape on `[regex]::` (leading `\b` before `[`, a
        # non-word char, requires a preceding word char that's never
        # actually there -- always whitespace, `=`, or line start) --
        # dropped since `[` is already self-delimiting.
        "regex_execution": re.compile(
            r"(?i)-match\b|-replace\b|-split\b|\bSelect-String\b|\[regex\]::(?:Match|Replace|Matches)\b"
        ),
        "time_date_logic": re.compile(r"(?i)\b(Get-Date|New-TimeSpan|Start-Sleep|Measure-Command)\b"),
        "ipc_rpc_bridges": re.compile(
            r"(?i)\b(Invoke-Command|Invoke-RestMethod|Invoke-WebRequest|Start-Process|Start-Job|Enter-PSSession)\b"
        ),
    },
}
