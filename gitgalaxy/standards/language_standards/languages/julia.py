# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

from typing import Any

from gitgalaxy.standards.language_standards import _lazy_re as re  # #3914: compiled on first use
from gitgalaxy.standards.language_standards.identifiers import ID_CONTINUE

from .._shared_patterns import CALLS_OUT_UNSUPPORTED, GLOBAL_FRAGILE_DEBT, GLOBAL_PLANNED_DEBT

# A Julia name: a letter or `_`, then word characters, with an optional `!` suffix (`push!`).
_NAME = r"[^\W\d][" + ID_CONTINUE + r"]*!?"
# A module path as written after `using` / `import`: `Foo`, `Foo.Bar`, `.Local`, `..Parent`.
_MODPATH = r"\.*[^\W\d][" + ID_CONTINUE + r"]*(?:\.[^\W\d][" + ID_CONTINUE + r"]*)*"
# Leading macro calls on a definition line: `@inline function f`, `Base.@propagate_inbounds function f`.
_MACROS = r"(?:(?:[A-Za-z_]\w*\.)?@[A-Za-z_]\w*[ \t]+)*"

DEFINITION: dict[str, Any] = {
    "_meta": {
        "target_version": "Julia 1.x (modules, multiple dispatch, structs, macros, Test / Pkg ecosystem)",
        "last_updated": "2026-11-11",
        "blueprint_version": "v5.0",
        "status": "production",
    },
    "extensions": [".jl"],
    "exact_matches": [],
    "discriminators": [],
    "shebangs": ["julia"],
    # `#` line comments; `#= ... =#` block comments are blanked for import capture below.
    "lexical_family": "line_exclusive",
    # #6572: a `#= ... =#` block comment, a `"""` docstring / string, a `"..."` string (Julia strings may span lines)
    # and a `'x'` char literal (`'"'` must not open a string) hold no imports; a `#` comment is consumed first so a
    # stray quote in it cannot pair with a later one. Lazy with fixed terminators or capped, so linear.
    "import_capture_blank": r"#=[\s\S]*?=#"
    + "|"
    + r'"""[\s\S]*?"""'
    + "|"
    + r"'(?:[^'\\\n]|\\.)'"
    + r"|#[^\n]*"
    + r'|"(?:[^"\\]|\\[\s\S]){0,20000}"',
    "rules": {
        # A call-graph extractor is not built yet (#6572 sibling): declare it unsupported rather than guess.
        "calls_out": CALLS_OUT_UNSUPPORTED,
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        "branch": re.compile(r"\b(?:if|elseif|else|for|while|try|catch|finally)\b|&&|\|\||[ \t]\?[ \t]"),
        # args: group 1 is the parenthesised parameter list of `function name(...)`.
        "args": re.compile(r"\bfunction[ \t]+(?:[\w.]*\.)?" + _NAME + r"(?:\{[^}\n]*\})?[ \t]*\(([^)\n]*)\)"),
        "structural_boundaries": re.compile(
            r"\b(?:module|baremodule|struct|function|macro|abstract[ \t]+type|primitive[ \t]+type|using|import|end)\b"
        ),
        # func_start: a `function` block or a short-form `f(x) = ...` definition. Group 1 is the name.
        "func_start": re.compile(
            r"^[ \t]*"
            + _MACROS
            + r"(?:function[ \t]+(?:[\w.]*\.)?("
            + _NAME
            + r")(?=[ \t({;]|$)"
            + r"|("
            + _NAME
            + r")(?:\{[^}\n]*\})?\([^)\n]*\)[ \t]*(?:::[^=\n]+?)?[ \t]*(?:where[ \t]+[^=\n]+?[ \t]*)?=(?![=>]))",
            re.M,
        ),
        # class_start: a struct, module or abstract / primitive type. Group 1 is the name.
        "class_start": re.compile(
            r"^[ \t]*"
            + _MACROS
            + r"(?:(?:mutable[ \t]+)?struct|(?:bare)?module|abstract[ \t]+type|primitive[ \t]+type)[ \t]+("
            + _NAME
            + r")",
            re.M,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        "safety": re.compile(r"\b(?:try|catch|finally|isnothing|ismissing|isa)\b|@assert\b|\bsomething\("),
        "safety_bypasses": re.compile(
            r"@(?:inbounds|fastmath|simd|propagate_inbounds)\b|\bunsafe_(?:load|store!|wrap|convert|string|pointer)\("
            r"|\breinterpret\("
        ),
        "high_risk_execution": re.compile(
            r"(?<![\w.])(?:run|eval|evalfile|include_string|ccall|pipeline)\(|@eval\b|\bMeta\.parse\(|`[^`\n]+`"
        ),
        "io": re.compile(
            r"(?<![\w.])(?:open|read|write|readlines|readline|readdir|readchomp|eachline|mkdir|mkpath|rm|cp|mv|download"
            r"|filesize|isfile|isdir)\(|\bHTTP\.[a-z_]+|\bSockets\.[a-z_]+|\b(?:stdin|stdout|stderr)\b"
        ),
        "api": re.compile(r"^[ \t]*@(?:get|post|put|patch|delete)[ \t(]|\broute\([ \t]*\"", re.M),
        "state_mutation": re.compile(
            r"\b(?:push|pop|append|empty|delete|insert|splice|setindex|merge|fill|resize|sort|reverse|copyto|deleteat"
            r"|pushfirst|popfirst)!\(|\.=(?!=)"
        ),
        "dead_code": re.compile(r"^[ \t]*#[ \t]*(?:function|println|@show|using|import)[ \t(]", re.M),
        "doc": re.compile(r"^[ \t]*(?:@doc[ \t]+)?\"\"\"", re.M),
        "test": re.compile(
            r"^[ \t]*@(?:testset|test|test_throws|test_broken|test_skip|test_logs|inferred)\b|\busing[ \t]+Test\b",
            re.M,
        ),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        "concurrency": re.compile(
            r"(?:Threads\.)?@(?:spawn|threads|async|sync|distributed)\b|\b(?:Channel|Threads\.[A-Za-z]+|pmap"
            r"|remotecall(?:_fetch)?|Distributed)\b"
        ),
        "ui_framework": re.compile(r"\b(?:Makie|GLMakie|CairoMakie|Gtk|QML|Blink|Pluto|Plots|Gadfly|Stipple)\b"),
        "closures": re.compile(r"->|\bdo\b(?:[ \t]+[\w, ()]+)?[ \t]*$", re.M),
        "globals": re.compile(r"^[ \t]*(?:global|const)[ \t]+[A-Za-z_]|\bENV\[|\bARGS\b|\bglobal[ \t]+\w", re.M),
        "decorators": re.compile(
            r"^[ \t]*@(?:inline|noinline|generated|kwdef|enum|deprecate|propagate_inbounds|assume_effects|nospecialize|doc)\b",
            re.M,
        ),
        "generics": re.compile(r"\bwhere[ \t]+\{?[A-Z]|\b(?:struct|function)[ \t]+\w+\{"),
        "comprehensions": re.compile(r"\[[^\]\n]*\bfor\b[^\]\n]*\]|\b(?:map|filter|mapreduce|foldl|foldr|reduce)\("),
        "scientific": re.compile(
            r"\b(?:LinearAlgebra|DifferentialEquations|OrdinaryDiffEq|Flux|Zygote|DataFrames|Statistics|SparseArrays"
            r"|FFTW|JuMP|Optim|Turing|CUDA|Distributions|StatsBase|ForwardDiff)\b"
        ),
        "reflection_metaprogramming": re.compile(
            r"@(?:eval|generated|macroexpand)\b|\beval\(|\bMeta\.[a-z_]+|\b(?:quote|macro)\b"
            r"|\b(?:fieldnames|fieldtypes|getfield|setfield!|hasmethod|methods|propertynames|invokelatest|nameof)\("
        ),
        "import": re.compile(r"^[ \t]*(?:using|import)[ \t]+\.*[^\W\d]", re.M),
        # Group 1 is the first module path; `using .Local` names `.Local`, `import A: b` names `A`, and
        # `using A, B` names only `A`.
        "_dependency_capture": re.compile(r"^[ \t]*(?:using|import)[ \t]+(" + _MODPATH + r")", re.M),
        "ownership": re.compile(
            r"^[ \t]*#+[ \t]*(?:Authors?|Created[ \t]+by|Maintainers?|Owners?|Contact)[ \t]*:(?![:=])[ \t]*(\S[^\n]*?)[ \t]*$",
            re.I | re.M,
        ),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        "planned_debt": GLOBAL_PLANNED_DEBT,
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d{1,10}|spec|audit)[^\]]{0,300}\]", re.I),
        "ssr_boundaries": re.compile(r"\b(?:Genie\.(?:Router|Renderer)|Oxygen|HTTP\.(?:serve|Router))\b|\bserve\("),
        "events": re.compile(r"\bObservables?\b|\bnotify\(|\b(?:put|take)!\("),
        "dependency_injection": re.compile(r"@load_preference\b|\bScopedValues?\b|\bwith_logger\("),
        "macros": re.compile(r"^[ \t]*macro[ \t]+\w", re.M),
        "pointers": re.compile(r"\b(?:Ptr|Ref|Cstring|Cwstring)\b|\bunsafe_(?:load|store!|wrap|pointer)\(|\bpointer\("),
        "memory_alloc": re.compile(
            r"\bLibc\.(?:malloc|calloc|realloc|free)\(|\b(?:sizehint!|resize!|similar|zeros|ones|fill)\("
            r"|\b(?:Vector|Array)\{[^}\n]*\}\(undef"
        ),
        "inline_asm": re.compile(r"\b(?:Base\.)?llvmcall\("),
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        "telemetry": re.compile(r"@(?:debug|info|warn|error|logmsg)\b|\bwith_logger\b|\bGlobalLogger\b"),
        "debug_prints": re.compile(r"@show\b|@infiltrate\b|@enter\b|\b(?:println|print|display|dump)\("),
        "explicit_casts": re.compile(
            r"\b(?:parse|tryparse|convert|trunc|round|floor|ceil|Int|Int8|Int16|Int32|Int64|UInt|UInt8|UInt16|UInt32"
            r"|UInt64|Float16|Float32|Float64|BigInt|BigFloat|Char|String|Symbol)\("
        ),
        "panics_and_aborts": re.compile(r"(?<![@\w])(?:error|throw|rethrow|exit|quit)\(|@assert\b"),
        "thread_sleeps": re.compile(r"\bsleep\([ \t]*[0-9.]+"),
        "bitwise_ops": re.compile(
            r"\b(?:xor|count_ones|leading_zeros|trailing_zeros|bitrotate)\(|<<|>>>?|(?<![|&])[ \t](?:&|\|)[ \t]"
        ),
        "sync_locks": re.compile(r"\b(?:ReentrantLock|SpinLock|Semaphore|Atomic|lock|unlock|trylock)\(|@lock\b"),
        "immutability_locks": re.compile(r"^[ \t]*(?:const|struct)[ \t]+[A-Za-z_]|\bNamedTuple\b", re.M),
        "cleanup": re.compile(r"\bfinally\b|\b(?:close|finalizer|atexit|unlock)\("),
        "encapsulation": re.compile(r"^[ \t]*(?:export|private|public)[ \t]+[A-Za-z_]", re.M),
        "listeners": re.compile(r"\b(?:listen|accept|serve|take!|wait_readable)\(|@async[ \t]+while\b"),
        "test_skip": re.compile(r"^[ \t]*@(?:test_skip|test_broken)\b", re.M),
        # --- PHASE 3: HYBRID DOMAIN SENSORS (Julia specifics) ---
        "auth_middleware": re.compile(r"\b(?:JSONWebTokens|JWTs?|Bcrypt|OAuth|BasicAuth|authenticate|authorize)\b"),
        "serialization_parsing": re.compile(
            r"\b(?:JSON3?|CSV|YAML|TOML|Serialization|BSON|Arrow|JLD2?|HDF5|EzXML|LightXML)\.[A-Za-z_]+"
        ),
        "regex_execution": re.compile(r"\b(?:match|eachmatch|occursin)\(|\br\"[^\"\n]*\"[a-z]*|\bRegex\("),
        "time_date_logic": re.compile(
            r"\b(?:Dates\.\w+|DateTime|Date|Time|TimeZones|now|today|time_ns|unix2datetime|datetime2unix)\(|@(?:elapsed|time|timed|btime)\b"
        ),
        "ipc_rpc_bridges": re.compile(
            r"\b(?:ccall|PyCall|PythonCall|RCall|JavaCall|JuliaCall|ZMQ|Sockets|addprocs|remotecall(?:_fetch)?"
            r"|HTTP\.(?:get|post|put|request|open))\b|@(?:ccall|pyimport)\b"
        ),
        "system_config_mutation": re.compile(r"\bENV\[[^\]\n]+\][ \t]*=(?!=)|(?<![\w.])(?:cd|chmod|chown|mkpath)\("),
    },
}
