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
        "target_version": "MATLAB R2024b",
        "last_updated": "2026-02-27",
        "blueprint_version": "",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: Standard scripts, functions, and modern Live Scripts (.mlx).
    "extensions": [".m", ".mlx"],
    # ABSOLUTE IDENTITY & EXACT FILENAMES: MATLAB and Octave rely strictly on extensions for execution.
    "exact_matches": [],
    # ECOSYSTEM ANCHORS & DISAMBIGUATION: Critical for resolving the massive .m collision with Objective-C. Binary workspace and figure files act as absolute anchors.
    "discriminators": [".m", ".mat", ".fig", ".mlx", "project.prj"],
    # #377: this is exactly the "massive .m collision with Objective-C" the
    # comment above already calls out -- heavy presence of Objective-C's OWN
    # ecosystem anchors (its own "discriminators", below) elsewhere in the
    # repo is direct evidence AGAINST an ambiguous .m file being MATLAB.
    "disqualifiers": [".mm", "project.pbxproj", ".storyboard", ".xib", ".xcworkspace", "Podfile", "Cartfile"],
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
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # branch: MATLAB control flow. EXCLUDES 'error' and 'rethrow' (bailout_hits).
        "branch": re.compile(r"\b(?:if|elseif|else|switch|case|otherwise|for|while|try|catch)\b|&&|\|\||~="),
        # args: Captures standard function inputs and return signatures `function [out1, out2] = myFun(in1, in2)`.
        # CRITICAL GUARDRAIL: Safely bounds `\([^)]*\)` and `\[[^\]]*\]`.
        # #1209: the trailing input-parameter parens wrapped in its own
        # capture group (was only reachable via group(0), the whole
        # match including the "function [outputs] = name" prefix) so
        # detector.py's counter isolates just the real INPUT arg list --
        # the whole-match fallback both overcounted zero/one-arg
        # signatures by +1 like every other language (#1199) AND, worse,
        # mixed the output-list `[out1, out2]` in as if it were part of
        # the input signature. Name group added too, purely so existing
        # extraction tests keep passing.
        "args": re.compile(
            r"\bfunction(?:[ \t\n]|\.\.\.[^\n]*\n)+(?:\[[^\]]*\](?:[ \t\n]|\.\.\.[^\n]*\n)*=(?:[ \t\n]|\.\.\.[^\n]*\n)*|[a-zA-Z_]\w*(?:[ \t\n]|\.\.\.[^\n]*\n)*=(?:[ \t\n]|\.\.\.[^\n]*\n)*)?([a-zA-Z_]\w*)(?:[ \t\n]|\.\.\.[^\n]*\n)*(\([^)]*\))|@(?:[ \t\n]|\.\.\.[^\n]*\n)*(\([^)]*\))"
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
            r"^[ \t]*(?!(?:if|for|while|switch|catch|classdef)\b)function(?:[ \t\n]|\.\.\.[^\n]*\n)+(?:\[[^\]]*\](?:[ \t\n]|\.\.\.[^\n]*\n)*=(?:[ \t\n]|\.\.\.[^\n]*\n)*|[a-zA-Z_]\w*(?:[ \t\n]|\.\.\.[^\n]*\n)*=(?:[ \t\n]|\.\.\.[^\n]*\n)*)?([a-zA-Z_]\w*)(?=(?:[ \t\n]|\.\.\.[^\n]*\n)*(?:\(|%|;|$))",
            re.M,
        ),
        # class_start: Defines an object-oriented boundary.
        # Safely steps over optional class attributes like `classdef (ConstructOnLoad) MyClass`
        "class_start": re.compile(
            r"^[ \t]*classdef(?:(?:[ \t\n]|\.\.\.[^\n]*\n)*\([^)]*\))?(?:[ \t\n]|\.\.\.[^\n]*\n)+([a-zA-Z_]\w*)(?=(?:[ \t\n]|\.\.\.[^\n]*\n)*(?:<|%|;|$))",
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
        # BUG FIX 1: the bare `methods` literal had no trailing boundary at all
        # (not even `\b`), so it matched as a false-positive prefix of any
        # identifier merely starting with "methods" (e.g. `methodsList = ...`).
        # Added `\b` right after the literal -- "methods" is all word chars, so
        # a plain `\b` is correct here (not the Rule 9 shared-group trap).
        # BUG FIX 2 (Rule 1, Semantic Intent): the Access=public check was an
        # optional *positive* group instead of a *negative* exclusion, so it
        # never actually gated anything -- `methods (Access = private)` and
        # `methods (Access = protected)` both still matched via the bare
        # `methods\b` alone, directly contradicting this rule's own documented
        # purpose ("don't declare private access"). Replaced with a negative
        # lookahead that excludes an explicit private/protected declaration
        # anywhere in a (possibly multi-attribute) attribute list, while still
        # matching bare `methods` (implicitly public by MATLAB default) and
        # explicit `Access = public`. Bounded to 200 chars per Rule 5.
        "api": re.compile(
            r"^[ \t]*methods\b(?![ \t]*\([^)]{0,200}\bAccess[ \t]*=[ \t]*(?:private|protected)\b)",
            re.M | re.I,
        ),
        # flux: Mutation of state via assignment.
        # Safely clamped with `[ \t]*=[ \t]*` to avoid newline spirals. Bounded nested fields `{0,5}`.
        # BUG FIX (Rule 11, nested-delimiter coverage): the flat `[^)]*`/`[^}]*`
        # classes broke on one level of nested indexing, e.g. `data(idx(1)) = v;`
        # -- a common, realistic MATLAB pattern (indexing by another array/
        # function's result). The truncated inner match left a stray closing
        # bracket unconsumed, which then broke the required trailing `=`, so
        # the WHOLE assignment went undetected (a true false negative, unlike
        # a bare boolean-only rule where truncation still finds *a* match).
        # Widened each segment to tolerate one level of self-nesting, same
        # non-overlapping-alternatives shape the doc's Rule 11 example uses.
        "state_mutation": re.compile(
            r"^[ \t]*[a-zA-Z_]\w*"
            r"(?:\((?:[^()]|\([^()]*\))*\)|\{(?:[^{}]|\{[^{}]*\})*\}|\.[a-zA-Z_]\w*){0,5}"
            r"[ \t]*=[ \t]*[^=]|\b(?:clear|clearvars)\b",
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
        "_dependency_capture": re.compile(r"^[ \t]*import(?:[ \t]|\.\.\.[^\n]*\n)+([a-zA-Z0-9_.*]+)", re.M),
        # ownership: Standard MATLAB comment authorship signatures.
        "ownership": re.compile(r"^[ \t]*%[ \t]*(?:Author|Created by|Copyright)[ \t]*:(.*)", re.M | re.I),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        # 26. planned_debt (Annotated Debt / TODOs)
        "planned_debt": GLOBAL_PLANNED_DEBT,
        # 27. fragile_debt (Acknowledged Hacks / FIXMEs)
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        # BUG FIX: adjacent unbounded quantifiers with overlapping character
        # sets (`\d+` immediately followed by `[^\]]*`, which also matches
        # digits) -- the same ReDoS shape already found and fixed
        # independently in embedded_python, css, and tcl in this epic.
        # Confirmed via scaling sweep (~4x per doubling before the fix).
        # Bounded both quantifiers, consistent with the established fix.
        "spec_exposure": re.compile(r"\[(?:[ \t]*SPEC[ \t]*-[ \t]*\d{1,10}|spec|audit)[^\]]{0,300}\]", re.I),
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
        # BUG FIX (Rule 3, Annotation & Execution Isolation): the bare `error`
        # alternative fired on `logger.error(...)`/`log.error(...)` -- a
        # custom logging framework's benign structured-logging call (already
        # captured by `telemetry`), not MATLAB's built-in `error()` function,
        # which actually throws and halts execution. A dot immediately before
        # "error" is always a method-call chain, never the standalone
        # builtin, so excluded via a negative lookbehind.
        "panics_and_aborts": re.compile(r"\b(?:throw|rethrow|MException|throwAsCaller)\b|(?<!\.)\berror\b"),
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
        # BUG FIX: missing `re.M` entirely on this `^`-anchored alternative
        # (epic recurring bug class #6) -- `^` anchored to true string start
        # only, so the shell-escape `!cmd` form could only ever fire if `!`
        # were the very first character of the entire file, never on any
        # later line where a real shell-escape command actually appears in
        # practice. Also switched `\s*` to `[ \t]*` per Rule 5 (horizontal-
        # only spacing must not cross newlines under `re.M`).
        "ipc_rpc_bridges": re.compile(
            r"\b(system|dos|unix|tcpclient|tcpserver|parpool|parfor)\b|^[ \t]*!",
            re.M,
        ),  # '!' is MATLAB's native shell escape
    },
}
