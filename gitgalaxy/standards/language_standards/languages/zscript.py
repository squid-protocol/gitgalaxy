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

# One method header: scope/virtual modifiers, then a return type (`void`, `Class<Actor>`, `Array<int>`,
# or a multi-value `int, bool`), then the name. Shared by `func_start`, `args` and `api` so the three agree.
_MODS = (
    r"(?:(?:override|virtual|static|action|play|ui|clearscope|virtualscope|native|final|private|protected|"
    r"abstract|vararg|internal|transient|readonly|const|latent|meta|"
    r"(?:deprecated|version)[ \t]*\((?:\"[^\"\n]{0,80}\"|[^)\n\"]){0,120}\))[ \t]+){0,8}"
)
_RET = (
    r"(?!(?:else|return|new|if|for|foreach|while|until|do|switch|case|default|class(?![ \t]*<)|struct|enum|extend|mixin)\b)"
    r"[A-Za-z_][\w.]*(?:[ \t]*<(?:[^<>\n]|<(?:[^<>\n]|<[^<>\n]*>)*>){1,80}>)?"
    r"(?:[ \t]*,[ \t]*[A-Za-z_][\w.]*(?:[ \t]*<[^<>\n]{1,60}>)?){0,4}[ \t]+"
)

DEFINITION: dict[str, Any] = {
    "_meta": {
        "target_version": "ZScript 4.x (GZDoom object scripting)",
        "last_updated": "2026-10-18",
        "blueprint_version": "v5.0",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: ZScript source files. The root `zscript.txt` lump and DECORATE / MAPINFO
    # data-definition lumps are out of scope (data DSLs, no extension to anchor on; #5465).
    "extensions": [".zs"],
    "exact_matches": [],
    "discriminators": [".zs"],
    "shebangs": [],
    # Rationale: C-style `//` and `/* */` comments.
    "lexical_family": "standard_block",
    # ZScript identifiers are case-insensitive (`Actor` == `actor`), as in apex.
    "identifier_case": "insensitive",
    "rules": {
        "_scope_filters": {"branch": "outside_literals"},
        "calls_out": CALLS_OUT_C_STYLE,
        # keywords and special forms, never calls
        "_calls_out_ignore": frozenset({"if", "while", "until", "for", "foreach", "switch", "return", "new", "states"}),
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # 1. branch: decisions that split flow (`?:`, `&&`, `||` included; `case` labels are arms).
        "branch": re.compile(r"\b(?:if|else|switch|case|while|until|for|foreach|do)\b|&&|\|\||\?", re.I),
        # 2. args: the parameter list a method DECLARES (a call site consumes, it does not publish).
        "args": re.compile(
            r"^[ \t]*" + _MODS + _RET + r"([A-Za-z_]\w*)[ \t]*"
            r"(\((?:[^)(]|\((?:[^)(]|\([^)(]*\))*\))*\))(?=[ \t\n]*(?:const[ \t\n]+)?\{)",
            re.M | re.I,
        ),
        # 3. structural_boundaries: unconditional transfers. Access modifiers excluded.
        "structural_boundaries": re.compile(r"\b(?:return|break|continue)\b", re.I),
        # 4. func_start: methods with a body. Bodiless `native`/`abstract` declarations end in `;` and are not
        # executable logic; a call statement never has a `{` after its `)`.
        "func_start": re.compile(
            r"^[ \t]*" + _MODS + _RET + r"([A-Za-z_]\w*)(?=[ \t]*\((?:[^)(\n]|\((?:[^)(\n]|\([^)(\n]*\))*\)){0,300}\)"
            r"[ \t\n]*(?:const[ \t\n]+)?\{)",
            re.M | re.I,
        ),
        # 5. class_start: `class`, `struct`, `enum` and the `extend`/`mixin` forms.
        "class_start": re.compile(
            r"^[ \t]*(?:(?:extend|mixin|abstract|final|native|ui|play|clearscope|version[ \t]*\([^)\n]{0,60}\))[ \t]+){0,4}"
            r"(?:class|struct|enum)[ \t]+([A-Za-z_]\w*)\b",
            re.M | re.I,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        # 6. safety: range clamps and validity guards.
        "safety": re.compile(r"\b(?:clamp|isValid|isActorPlayer)[ \t]*\(", re.I),
        # 7. safety_bypasses: stepping out of the play/ui scope sandbox.
        "safety_bypasses": re.compile(r"\b(?:clearscope|virtualscope)\b", re.I),
        # 8. high_risk_execution: no process, shell or dynamic-eval facility exists in the sandboxed VM.
        "high_risk_execution": None,
        # 9. io: the only persistent reads: console variables and WAD lumps.
        "io": re.compile(r"\bCVar\.(?:GetCVar|FindCVar)\b|\bWads\.(?:ReadLump|FindLump|CheckNumForName)\b", re.I),
        # 10. api: implicitly public; a method header not marked private/protected.
        "api": re.compile(
            r"^(?![ \t]*(?:[\w()\"., ]{0,80}?\b)?(?:private|protected)\b)[ \t]*"
            + _MODS
            + _RET
            + r"([A-Za-z_]\w*)(?=[ \t]*\()",
            re.M | re.I,
        ),
        # 11. state_mutation: a statement writing into existing state (a typed declaration is not a write).
        "state_mutation": re.compile(
            r"(?:^|[;{}])[ \t]*[A-Za-z_]\w*(?:\.[A-Za-z_]\w*|\[[^\]\n]{0,80}\])*"
            r"[ \t]*(?:[-+*/%&|^]|<<|>>>?)?=(?![=>])(?![^\n(]{0,300},[ \t]*$)"
            r"|[\w)\]][ \t]*(?:\+\+|--)|(?:\+\+|--)[ \t]*[A-Za-z_(*]",
            re.M,
        ),
        # 12. dead_code: commented-out statements.
        # #7207: a statement's shape (`if (...)`, `return x;`, `virtual void Tick()`, `class Foo : Actor`, `A_Chase();`),
        # not just the keyword: `// return value is ignored` and `// class of the monster` are prose.
        "dead_code": re.compile(
            commented_keyword_statement(
                "if|for|while|return|override|virtual|class",
                block=False,
                extra=r"(?<=class)[ \t]+\w{1,64}[ \t]*:[ \t]*\w[^\n]{0,100}(?m:$)",
            )
            + r"|(?<![/*])//[ \t]*A_\w+[ \t]*\(",
            re.I,
        ),
        # 13. doc: no documentation-comment convention in the language.
        "doc": None,
        # 14. test: no test framework.
        "test": None,
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # 15. concurrency: single-threaded tick VM; no threads or async.
        "concurrency": None,
        # 16. ui_framework: menu, HUD and status-bar classes and draw calls.
        "ui_framework": re.compile(
            r"\b(?:OptionMenu\w*|GenericMenu|ListMenu\w*|BaseStatusBar|StatusBarCore|HUDFont|Screen\.Draw\w+|"
            r"DrawString|DrawImage|DrawTexture)\b",
            re.I,
        ),
        # 17. closures: no lambdas.
        "closures": None,
        # 18. globals: engine-global state reached by name.
        "globals": re.compile(
            r"\bLevel\.\w+|\bplayers[ \t]*\[|\b(?:playeringame|consoleplayer|gametic|deathmatch|multiplayer)\b"
        ),
        # 19. decorators: `deprecated("2.4")` / `version("4.0")` attributes.
        "decorators": re.compile(r"\b(?:deprecated|version)[ \t]*\([^)\n]{0,60}\)", re.I),
        # 20. generics: `Array<T>`, `Map<K,V>`, `Class<T>`.
        "generics": re.compile(r"\b(?:Array|Map|MapIterator|Class)[ \t]*<[^<>\n]{1,80}>", re.I),
        # 21. comprehensions: the world-iterator classes.
        "comprehensions": re.compile(
            r"\b(?:ThinkerIterator|BlockThingsIterator|BlockLinesIterator|ActorIterator|LineIdIterator|SectorTagIterator)\b",
            re.I,
        ),
        # 22. scientific: math builtins and vector constructors.
        "scientific": re.compile(
            r"\b(?:sin|cos|tan|asin|acos|atan|atan2|sqrt|exp|log|log10|pow|deltaangle|vectorangle)[ \t]*\(|\bVec[234][ \t]*\(",
            re.I,
        ),
        # 23. reflection_metaprogramming: class-table lookups.
        "reflection_metaprogramming": re.compile(
            r"\b(?:GetClassName|GetParentClass|GetReplacement|GetReplacee|FindClass|GetClass)[ \t]*\(|\b(?:AllClasses|AllActorClasses)\b",
            re.I,
        ),
        # 24. import: `#include "path"` and `version "4.0"` is a pragma, not a dependency.
        "import": re.compile(r"^[ \t]*#include\b", re.M | re.I),
        "_dependency_capture": re.compile(r"^[ \t]*#include[ \t]+\"([^\"\n]+)\"", re.M | re.I),
        # 25. ownership
        "ownership": re.compile(
            r"@author:?[ \t]+(\S[^\n]*?)[ \t]*(?:\*/|-->)?[ \t]*$|^[ \t]*(?:/\*+|\*+|//+!?)[ \t]*(?:Authors?|Created[ \t]+by|Maintainers?|Owners?|Developers?|Contact)[ \t]*:(?![:=])[ \t]*(\S[^\n]*?)[ \t]*(?:\*/|-->)?[ \t]*$|^[ \t]*(?-i:(?:Author|AUTHOR)(?:s|S)?|Created[ \t]+by|CREATED[ \t]+BY|Maintainer(?:s)?|MAINTAINER(?:S)?|Owner(?:s)?|OWNER(?:S)?|Developer(?:s)?|DEVELOPER(?:S)?|Contact|CONTACT)[ \t]*:(?![:=])[ \t]*(\S[^\n]*?)(?<![,;{(])[ \t]*(?:\*/|-->)?[ \t]*$",
            re.I | re.M,
        ),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        "planned_debt": GLOBAL_PLANNED_DEBT,
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d+|spec|audit)\]", re.I),
        "ssr_boundaries": None,
        # 32. events: network/interface event dispatch.
        "events": re.compile(r"\b(?:EventHandler\.Send\w+|Send(?:Network|Interface)Event)\b", re.I),
        "dependency_injection": None,
        "macros": None,
        "pointers": None,  # object references only; no address arithmetic
        "memory_alloc": re.compile(r"\bnew[ \t]*\(", re.I),
        "inline_asm": None,
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        "telemetry": None,
        "debug_prints": re.compile(r"\b(?:A_Log(?:Int|Float)?|A_PrintBold|Printf(?:Ex)?|DPrintf)[ \t]*\(", re.I),
        # 40. explicit_casts: primitive conversions and `Class<T>(x)`.
        "explicit_casts": re.compile(
            r"\b(?:int|uint|float|double|bool|name|string|sound|color|state)[ \t]*\(|\bClass[ \t]*<[^<>\n]{1,40}>[ \t]*\(",
            re.I,
        ),
        "panics_and_aborts": re.compile(r"\bThrowAbortException\b", re.I),
        "thread_sleeps": None,
        # 43. bitwise_ops: shifts need surrounding space (`Array<Array<int>>` closes with `>>`).
        "bitwise_ops": re.compile(r"[ \t]>>>?=?[ \t]|<<=?|(?<!&)&(?!&)|(?<!\|)\|(?!\|)|\^|~"),
        "sync_locks": None,
        "immutability_locks": re.compile(r"\b(?:const|readonly)\b", re.I),
        # 46. cleanup: object teardown calls (a `void Destroy(` declaration is not a site).
        "cleanup": re.compile(
            r"(?<!void )\b(?:Destroy|A_RemoveChildren|A_RemoveSiblings|A_RemoveTarget|A_Remove)[ \t]*\(", re.I
        ),
        "encapsulation": re.compile(r"\b(?:private|protected)\b", re.I),
        # 48. listeners: EventHandler callbacks.
        "listeners": re.compile(
            r"^[ \t]*(?:(?:override|virtual)[ \t]+)?(?:ui[ \t]+|play[ \t]+)?void[ \t]+(?:World(?:Loaded|Unloaded|Tick|ThingSpawned|ThingDied|ThingDamaged|ThingDestroyed|LinePreActivated|LineActivated)|"
            r"Player(?:Entered|Respawned|Died|Disconnected)|NetworkProcess|UiProcess|InputProcess|ConsoleProcess|RenderOverlay|"
            r"RenderUnderlay|OnRegister|OnUnregister|UiTick|PostUiTick)[ \t]*\(",
            re.M | re.I,
        ),
        "test_skip": None,
        # --- HYBRID DOMAIN SENSORS ---
        "auth_middleware": None,
        "serialization_parsing": None,
        "regex_execution": None,
        "time_date_logic": re.compile(r"\bLevel\.(?:time|maptime|totaltime)\b|\bGetAge[ \t]*\(", re.I),
        "ipc_rpc_bridges": re.compile(r"\b(?:CallACS|ACS_Execute\w*)[ \t]*\(", re.I),
        "system_config_mutation": re.compile(r"\.Set(?:Int|Float|String|Bool)[ \t]*\(", re.I),
    },
}
