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

from .._shared_patterns import CALLS_OUT_C_STYLE, GLOBAL_FRAGILE_DEBT, GLOBAL_PLANNED_DEBT, commented_keyword_statement

# A script name is a number, a quoted string or a bare word (`script 1`, `script "Open Door"`, `script Boom`, the old `script << 1 >>`).
_SCRIPT_NAME = r"(\"[^\"\n]{1,80}\"|<<[ \t]*\d+[ \t]*>>|[A-Za-z_]\w*|\d+)"
# `function int Add(int a, int b)`: ACS return types are `void`, `int`, `str`, `bool`, `fixed`, `float`.
_FUNC_HEAD = r"function[ \t]+[A-Za-z_]\w*[ \t]+([A-Za-z_]\w*)"

DEFINITION: dict[str, Any] = {
    "_meta": {
        "target_version": "ACS (Action Code Script) as compiled by ACC / BCC / GDCC-ACC (Hexen, ZDoom, GZDoom)",
        "last_updated": "2026-10-18",
        "blueprint_version": "v5.0",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: ACS source files. ACS lumps inside WADs / pk3 (`SCRIPTS`, no extension) are
    # out of scope: there is no extension to anchor on (#5465).
    "extensions": [".acs"],
    "exact_matches": [],
    "discriminators": [".acs"],
    "shebangs": [],
    # Rationale: C-style `//` and `/* */` comments.
    "lexical_family": "standard_block",
    "rules": {
        "_scope_filters": {"branch": "outside_literals"},
        "calls_out": CALLS_OUT_C_STYLE,
        # keywords and special forms, never calls
        "_calls_out_ignore": frozenset({"if", "while", "until", "for", "switch", "return", "script", "function"}),
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch: decisions that split flow (`?:`, `&&`, `||` included; `case` labels are arms).
        "branch": re.compile(r"\b(?:if|else|switch|case|while|until|for|do)\b|&&|\|\||\?", re.I),
        # 2. args: the parameter list a script or function DECLARES (`script 1 (int a)` / `function int F(int a)`).
        "args": re.compile(
            r"^[ \t]*(?:script[ \t]+" + _SCRIPT_NAME + r"|" + _FUNC_HEAD + r")[ \t]*"
            r"(\([^)\n]{0,300}\))",
            re.M | re.I,
        ),
        # 3. structural_boundaries: unconditional transfers; `terminate` / `restart` end or rerun a script.
        "structural_boundaries": re.compile(r"\b(?:return|break|continue|goto|terminate|restart)\b", re.I),
        # 4. func_start: a `script` or `function` header. A call statement never starts with either keyword.
        "func_start": re.compile(
            r"^[ \t]*(?:script[ \t]+" + _SCRIPT_NAME + r"(?!\w)|" + _FUNC_HEAD + r"(?=[ \t]*\())",
            re.M | re.I,
        ),
        # 5. class_start: no classes (structs do not exist; scripts are the unit).
        "class_start": None,
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        # 6. safety: range clamps and validity guards.
        "safety": re.compile(
            r"\b(?:Clamp|Min|Max|CheckActorClass|IsTIDUsed|PlayerIsSpectator|GetPlayerInfo)[ \t]*\(", re.I
        ),
        # 7. safety_bypasses: no escape hatch from the VM sandbox exists.
        "safety_bypasses": None,
        # 8. high_risk_execution: no process, shell or dynamic-eval facility exists in the sandboxed VM.
        "high_risk_execution": None,
        # 9. io: console variables and commands, the only channel out of the VM (variable slots are state, not io).
        "io": re.compile(r"\b(?:GetCVar|GetCVarString|SetCVar|GetUserCVar|SetUserCVar|ConsoleCommand)[ \t]*\(", re.I),
        # 10. api: scripts are reachable from outside by number or name; a `function` is file-local unless imported.
        "api": re.compile(r"^[ \t]*script[ \t]+" + _SCRIPT_NAME, re.M | re.I),
        # 11. state_mutation: a statement writing into existing state (a typed declaration is not a write).
        "state_mutation": re.compile(
            r"(?:^|[;{}])[ \t]*[A-Za-z_]\w*(?:\[[^\]\n]{0,80}\])*"
            r"[ \t]*(?:[-+*/%&|^]|<<|>>)?=(?![=>])(?![^\n(]{0,300},[ \t]*(?=\n|\Z))"
            r"|[\w)\]][ \t]*(?:\+\+|--)|(?:\+\+|--)[ \t]*[A-Za-z_(]",
            re.M,
        ),
        # 12. dead_code: commented-out statements.
        # #7207: a statement's shape (`;{}`, `(...)`, an assignment, a `script N OPEN` header), not just the keyword;
        # a call needs its `(...)` and `;`.
        "dead_code": re.compile(
            commented_keyword_statement(
                "if|for|while|return|script|function",
                block=False,
                extra=r"(?<=script)[ \t]+(?:\d+|\"[^\"\n]{1,80}\")[ \t]+(?-i:[A-Z]+)[ \t]*(?m:$)",
            )
            + r"|//[ \t]*[A-Za-z_]\w*[ \t]*\([^)\n]*\)[ \t]*;",
            re.I | re.M,
        ),
        # 13. doc: no documentation-comment convention in the language.
        "doc": None,
        # 14. test: no test framework.
        "test": None,
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # 15. concurrency: scripts run as cooperative tasks the engine schedules; `Delay` yields, `ScriptWait` joins.
        "concurrency": re.compile(
            r"\b(?:Delay|TagWait|PolyWait|ScriptWait|ScriptWaitDirect|ACS_Execute\w*|ACS_NamedExecute\w*)\b", re.I
        ),
        # 16. ui_framework: HUD message output.
        "ui_framework": re.compile(
            r"\b(?:HudMessage\w*|SetHudSize|SetFont|PrintBold|SetHudClipRect|SetHudWrapWidth)\b", re.I
        ),
        # 17. closures: no lambdas.
        "closures": None,
        # 18. globals: `global` / `world` variable declarations and the `GameType` / `PlayerCount` accessors.
        "globals": re.compile(
            r"\b(?:global|world)[ \t]+(?:int|str|bool|fixed)\b|\b(?:GameType|PlayerCount|ConsolePlayerNumber|Timer)[ \t]*\(",
            re.I,
        ),
        # 19. decorators: no attributes.
        "decorators": None,
        # 20. generics: none.
        "generics": None,
        # 21. comprehensions: none.
        "comprehensions": None,
        # 22. scientific: fixed-point math builtins.
        "scientific": re.compile(
            r"\b(?:Sin|Cos|Sqrt|FixedSqrt|VectorAngle|VectorLength|FixedMul|FixedDiv|Random|RandomFixed|Abs)[ \t]*\(",
            re.I,
        ),
        # 23. reflection_metaprogramming: actor-class lookups by name.
        "reflection_metaprogramming": re.compile(
            r"\b(?:CheckActorClass|CheckClass|GetActorClass|GetWeapon|PlayerClass)[ \t]*\(", re.I
        ),
        # 24. import: `#include "file"` (textual) and `#import "file"` (library link).
        "import": re.compile(r"^[ \t]*#(?:include|import)\b", re.M | re.I),
        "_dependency_capture": re.compile(r"^[ \t]*#(?:include|import)[ \t]+\"([^\"\n]+)\"", re.M | re.I),
        # 25. ownership
        "ownership": re.compile(
            r"@author:?[ \t]+(\S[^\n]*?)[ \t]*(?:\*/|-->)?[ \t]*$|^[ \t]*(?:/\*+|\*+|//+!?)[ \t]*(?:Authors?|Created[ \t]+by|Maintainers?|Owners?|Developers?|Contact)[ \t]*:(?![:=])[ \t]*(\S[^\n]*?)[ \t]*(?:\*/|-->)?[ \t]*$",
            re.I | re.M,
        ),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        "planned_debt": GLOBAL_PLANNED_DEBT,
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)\]", re.I),
        "ssr_boundaries": None,
        # 32. events: network / client-side / event-triggered scripts (`script N (...) NET`).
        "events": re.compile(
            r"^[ \t]*script[ \t]+" + _SCRIPT_NAME + r"[ \t]*(?:\([^)\n]{0,200}\))?[ \t]*(?:NET|CLIENTSIDE|EVENT)\b",
            re.M | re.I,
        ),
        "dependency_injection": None,
        "macros": re.compile(r"^[ \t]*#(?:define|libdefine|undef)\b", re.M | re.I),
        "pointers": None,
        "memory_alloc": None,
        "inline_asm": None,
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        "telemetry": None,
        "debug_prints": re.compile(r"\b(?:Print|PrintBold|Log|HudMessage\w*)[ \t]*\(", re.I),
        # 40. explicit_casts: none; the type system is int / fixed / str / bool with implicit conversion.
        "explicit_casts": None,
        "panics_and_aborts": re.compile(r"\bterminate\b", re.I),
        "thread_sleeps": re.compile(r"\b(?:Delay|TagWait|PolyWait)[ \t]*\(", re.I),
        "bitwise_ops": re.compile(r"<<=?|>>=?|(?<!&)&(?!&)|(?<!\|)\|(?!\|)|\^|~"),
        "sync_locks": None,
        "immutability_locks": None,
        "cleanup": re.compile(
            r"\b(?:Thing_Remove|Thing_Destroy|ClearInventory|TakeInventory|TakeActorInventory)[ \t]*\(", re.I
        ),
        "encapsulation": None,
        "listeners": re.compile(
            r"^[ \t]*script[ \t]+"
            + _SCRIPT_NAME
            + r"[ \t]*(?:\([^)\n]{0,200}\))?[ \t]*(?:OPEN|ENTER|RESPAWN|DEATH|LIGHTNING|UNLOADING|DISCONNECT|KILL|REOPEN|RETURN)\b",
            re.M | re.I,
        ),
        "test_skip": None,
        # --- HYBRID DOMAIN SENSORS ---
        "auth_middleware": None,
        "serialization_parsing": None,
        "regex_execution": None,
        "time_date_logic": re.compile(r"\bTimer[ \t]*\(", re.I),
        "ipc_rpc_bridges": re.compile(
            r"\b(?:ACS_Execute\w*|ACS_NamedExecute\w*|ACS_Suspend|ACS_NamedSuspend|ACS_Terminate|ACS_NamedTerminate|ScriptCall|CallFunc)[ \t]*\(",
            re.I,
        ),
        "system_config_mutation": re.compile(
            r"\b(?:SetCVar|SetUserCVar|SetGravity|SetAirControl|SetSkyScrollSpeed|ConsoleCommand)[ \t]*\(", re.I
        ),
    },
}
