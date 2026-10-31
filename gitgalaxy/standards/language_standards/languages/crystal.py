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
from gitgalaxy.standards.language_standards.identifiers import ID_CONTINUE, ID_START

from .._shared_patterns import CALLS_OUT_RUBY, GLOBAL_FRAGILE_DEBT, GLOBAL_PLANNED_DEBT, commented_keyword_statement

_NAME = r"[^\W\d][" + ID_CONTINUE + r"]*"
_PATH = _NAME + r"(?:::" + _NAME + r")*"
# A method name: an identifier with an optional `=` / `?` / `!`, or an operator method (`def [](i)`, `def <=>(o)`).
_METHOD = r"(" + _NAME + r"[=!?]?|\[\]=?\??|<<|>>|<=>|===?|!=|=~|!~|<=?|>=?|\*\*|[+\-*/%&|^~!])"
_PARAMS = (
    r"\((?:(?:[^()\'\"]|'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")"
    r"|\((?:[^()\'\"]|'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"|\([^()\n]*\))*\))*\)"
)
_MODS = r"(?:(?:private|protected)[ \t]+)?"

DEFINITION: dict[str, Any] = {
    "_meta": {
        "target_version": "Crystal 1.x (macros, annotations, lib/fun C bindings, fibers and channels)",
        "last_updated": "2026-10-20",
        "blueprint_version": "v5.0",
        "status": "production",
    },
    "extensions": [".cr"],
    "exact_matches": [],
    # `shard.yml` / `shard.lock` anchor a Crystal project (the shards package manager's manifest and lockfile).
    "discriminators": ["shard.yml", "shard.lock"],
    "shebangs": ["crystal"],
    # `#` line comments only (no `=begin` / `=end` block); `#{}` interpolation is shielded with the strings.
    "lexical_family": "line_exclusive",
    # `require "./x"` names a file beside the requiring one (ruby's #3553 shape).
    "imports_resolve_from_importer_dir": True,
    "rules": {
        "calls_out": CALLS_OUT_RUBY,
        # Crystal keywords the shared ruby pattern's own keyword list lacks: never calls.
        "_calls_out_ignore": frozenset(
            {
                "elsif",
                "abstract",
                "annotation",
                "as",
                "enum",
                "fun",
                "lib",
                "macro",
                "private",
                "protected",
                "require",
                "select",
                "struct",
                "uninitialized",
                "with",
                "yield",
                "typeof",
                "sizeof",
                "instance_sizeof",
                "pointerof",
                "include",
                "extend",
                "getter",
                "setter",
                "property",
                "class_getter",
                "class_setter",
                "class_property",
                "raise",
                "super",
            }
        ),
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # branch: decisions, `case` / `when` / `in`, loops and the `?:` ternary (a `foo?` method name is not one).
        "branch": re.compile(
            r"\b(?:if|unless|elsif|else|case|when|in|while|until|select)\b|&&|\|\||(?<!["
            + ID_CONTINUE
            + r"])\?(?=[ \t])"
        ),
        # args: group 1 is a `def` / `macro` parameter list (type restrictions and `Hash(K, V)` generics nest inside
        # it), group 2 block parameters (`do |a, b|`, `{ |x| }`), group 3 a proc literal's list (`->(x : Int32) { }`).
        "args": re.compile(
            r"\b(?:def|macro)[ \t]+(?:(?:" + _PATH + r"|self)\.)?" + _METHOD + r"[ \t]*(" + _PARAMS + r")"
            r"|\A(?![ \t]*\b(?:def|macro)\b)[\s\S]*?(?:\bdo[ \t]*\|([^|]*)\||\{[ \t]*\|([^|]*)\|)"
            r"|->[ \t]*(" + _PARAMS + r")"
        ),
        "structural_boundaries": re.compile(
            r"\b(?:class|struct|module|enum|lib|annotation|def|macro|fun|yield|return|next|break|require|include|extend"
            r"|alias|begin|abstract)\b"
        ),
        # func_start: a `def` or `macro` (optionally `private` / `protected`, `self.` or `Type.` qualified). An
        # `abstract def` has no body and does not start a unit; an indented `fun` inside a `lib` is a bodiless C declaration, not a unit.
        "func_start": re.compile(
            r"^[ \t]*"
            + _MODS
            + r"(?:def|macro)[ \t]+(?:(?:"
            + _PATH
            + r"|self)\.[ \t]*)?"
            + _METHOD
            + r"(?=[ \t\n(]|$)"
            # A COLUMN-0 `fun name(...) ... end` is a top-level C-callable body (#5623).
            r"|^fun[ \t]+" + _METHOD + r"(?=[ \t\n(]|$)",
            re.M,
        ),
        # class_start: class / struct / module / enum / lib / annotation, optionally `abstract` / `private`.
        # Group 1 is the (namespaced) name; a `class << self` is not a named declaration.
        "class_start": re.compile(
            r"^[ \t]*(?:(?:abstract|private)[ \t]+)*(?:class|struct|module|enum|lib|annotation)[ \t]+(?:::)?("
            + _PATH
            + r")",
            re.M,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        "safety": re.compile(r"&\.|\b(?:rescue|ensure|try|is_a\?|responds_to\?|as\?)\b|\.as\?"),
        # safety_bypasses: a nilable asserted away, and the `unsafe_*` / `uninitialized` escapes.
        "safety_bypasses": re.compile(
            r"\bnot_nil!|\b(?:unsafe_as|unsafe_fetch|unsafe_chr|unsafe_shl|unsafe_shr|uninitialized)\b"
        ),
        "high_risk_execution": re.compile(
            r"\b(?:abort|exit|system|Process\.(?:run|exec|fork|kill|new))\b|(?<!\$)`[^`\n]+`|%x[\[({]"
        ),
        "io": re.compile(
            r"\b(?:File|Dir|IO|FileUtils|Socket|TCPSocket|TCPServer|UDPSocket|UNIXSocket|HTTP::(?:Client|Server)"
            r"|STDIN|STDOUT|STDERR|DB)\b"
        ),
        # api: a column-0 `fun` (a C-callable export) and the web frameworks' route macros.
        "api": re.compile(r"^fun[ \t]+[a-z_]|^[ \t]*(?:get|post|put|patch|delete)[ \t]+[\"']", re.M),
        "state_mutation": re.compile(
            r"(?:^|;)[ \t]*[a-z_]["
            + ID_CONTINUE
            + r"]*(?:\.["
            + ID_START
            + r"]["
            + ID_CONTINUE
            + r"]*|\[[^\]\n]{0,80}\])*[ \t]+(?:[-+*/|&^]|\|\||&&|<<|>>)?=(?![=~>])"
            r"|@@?[" + ID_START + r"][" + ID_CONTINUE + r"]*[ \t]*(?:\+|-|\*|/|\|\||&&)?=(?![=~>])"
            r"|\.(?:push|pop|shift|unshift|delete|delete_at|delete_if|clear|concat|insert|replace|add|<<)\b(?![?!])"
            r"|[ \t]<<[ \t]"
            r"|\b(?:map!|select!|reject!|sort!|sort_by!|uniq!|compact!|flatten!|reverse!|shuffle!|rotate!|reject!)",
            re.M,
        ),
        # #7207: a statement's shape (`(...)`, an assignment, a bare `def name` / `class Name [< Base]`, a comparison or
        # method call after `if|unless|while`, a quoted or dotted `puts` argument), not just the keyword.
        "dead_code": re.compile(
            commented_keyword_statement(
                "def|class|struct|module|if|unless|while|puts|p",
                marker=r"#",
                extra=r"(?<=def)[ \t]+[\w.?!]+[ \t]*(?m:$)"
                r"|(?:(?<=class)|(?<=struct)|(?<=module))[ \t]+[A-Z]\w*(?:::\w+)*(?:[ \t]*<[ \t]*[A-Z][\w:(),]*)?[ \t]*(?m:$)"
                r"|(?:(?<=if)|(?<=unless)|(?<=while))[ \t]+[^\n]{0,300}?(?:[<>]|==|!=|&&|\|\||\w\.\w+\?)"
                r"|(?:(?<=puts)|(?<=p))[ \t]+(?:[\"'@:]|\w+\.\w)",
            )
        ),
        # doc: Crystal's `crystal doc` markdown comment conventions (a fenced `crystal` example, a section label).
        "doc": re.compile(
            r"^[ \t]*#[ \t]*(?:```crystal|(?:Returns|Raises|Yields|Params|Example|Examples)[ \t]*:)", re.M
        ),
        "test": re.compile(
            r"\b(?:describe|context)[ \t(]+(?:[\"']|[A-Z])"
            r"|\bit[ \t(]+[\"']"
            r"|\.should(?:_not)?\b"
            r"|\bexpect_raises\b"
            r"|\b(?:before|after)_(?:each|all)\b"
            r"|\brequire[ \t]+\"spec\""
        ),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        "concurrency": re.compile(r"\b(?:spawn|Fiber|Channel|Mutex|WaitGroup|Atomic|Future|Thread)\b"),
        "ui_framework": re.compile(r"\b(?:Gtk|Gdk|Glimmer|Crystal::UI|ECR\.embed|embed_ecr)\b"),
        "closures": re.compile(r"\bdo\b|\{[ \t]*\|[^|\n]*\||->[ \t]*(?:\([^)\n]*\))?[ \t]*\{|&\.[a-z_]"),
        "globals": re.compile(r"\b(?:ENV|ARGV|ARGF|PROGRAM_NAME|STDIN|STDOUT|STDERR)\b|\$[~?]"),
        # decorators: annotations, `@[Link("c")]`, `@[Flags]`.
        "decorators": re.compile(r"@\[[A-Z][^\]\n]{0,200}\]"),
        "generics": re.compile(
            r"\b(?:Array|Hash|Set|Slice|StaticArray|Pointer|Tuple|NamedTuple|Channel|Deque|Range|Proc|Enumerable|Iterator"
            r"|Indexable|Comparable)\((?:[^()\n]|\([^()\n]*\)){1,100}\)"
            r"|\b(?:class|struct|module)[ \t]+[A-Z][\w:]*\([A-Z]\w*(?:,[ \t]*[A-Z]\w*)*\)"
        ),
        "comprehensions": re.compile(
            r"\.(?:map|select|reject|reduce|inject|flat_map|each_with_object|partition|group_by|sum|compact_map)\b"
            r"(?:[ \t]*\{|\s*do|\()"
        ),
        "scientific": re.compile(r"\b(?:Math|Complex|BigDecimal|BigInt|BigFloat|BigRational|Random)\b"),
        # reflection_metaprogramming: macro expansion (`{% %}` / `{{ }}`), the hook macros and `@type` introspection.
        "reflection_metaprogramming": re.compile(
            r"\{%|\{\{|\b(?:method_missing|macro_missing|inherited|included|extended|finished|forward_missing_to|typeof)\b"
            r"|@type\b|\.(?:instance_vars|annotation|methods)\b|responds_to\?"
        ),
        "import": re.compile(r"^[ \t]*require[ \t]+\"", re.M),
        "_dependency_capture": re.compile(r"^[ \t]*require[ \t]+\"([^\"\n]+)\"", re.M),
        "ownership": re.compile(
            r"^[ \t]*#+[ \t]*(?:Authors?|Created[ \t]+by|Maintainers?|Owners?|Developers?|Contact)[ \t]*:(?![:=])[ \t]*(\S[^\n]*?)[ \t]*$"
            r"|@author:?[ \t]+(\S[^\n]*?)[ \t]*$",
            re.I | re.M,
        ),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        "planned_debt": GLOBAL_PLANNED_DEBT,
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d{1,10}|spec|audit)[^\]]{0,300}\]", re.I),
        "ssr_boundaries": re.compile(
            r"\b(?:Kemal|Amber::Controller|Lucky::Action|ATH::Controller|ART::Controller|Grip::Controllers"
            r"|HTTP::Server::Context)\b"
        ),
        "events": re.compile(r"\b(?:subscribe|publish|broadcast|EventHandler|EventEmitter)\b|\bSignal::[A-Z]+\.trap\b"),
        "dependency_injection": re.compile(r"\bADI::Register\b|@\[ADI::|\bAthena::DependencyInjection\b|\binject\b"),
        # macros: a `macro` definition and the stdlib's declaration macros (`getter`, `record`, `delegate`).
        "macros": re.compile(
            r"^[ \t]*(?:(?:private|protected)[ \t]+)?(?:macro[ \t]|(?:class_)?(?:getter|setter|property)[!?]?[ \t]"
            r"|record[ \t]|delegate[ \t]|forward_missing_to[ \t]|def_(?:equals|hash|clone|equals_and_hash)\b)",
            re.M,
        ),
        "pointers": re.compile(r"\b(?:Pointer|pointerof|to_unsafe)\b"),
        "memory_alloc": re.compile(
            r"\b(?:Pointer\.malloc|Slice\.malloc|GC\.[a-z_]+|LibC\.(?:malloc|calloc|realloc|free))\b|\.realloc\("
        ),
        "inline_asm": re.compile(r"\basm[ \t]*\("),
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        "telemetry": re.compile(
            r"\b(?:Log|logger|log)\.(?:trace|debug|info|notice|warn|error|fatal)\b|\bLog\.(?:for|setup|builder)\b"
        ),
        "debug_prints": re.compile(r"\b(?:puts|print|printf|pp|p)\b|\bp!|\bpp!"),
        "explicit_casts": re.compile(
            r"\.as\??\(|\.unsafe_as\(|\.to_(?:i8|i16|i32|i64|u8|u16|u32|u64|f32|f64|[ifusc])\b[!?]?"
        ),
        "panics_and_aborts": re.compile(r"\b(?:raise|abort|exit)\b|\bunreachable!"),
        "thread_sleeps": re.compile(r"\bsleep\b[ \t(]*[0-9.]+"),
        "bitwise_ops": re.compile(r"\^|(?<![=!])~|>>|&<<|[ \t]&[ \t]"),
        "sync_locks": re.compile(r"\b(?:Mutex|Atomic|WaitGroup|Semaphore)\b|\.(?:synchronize|lock|unlock)\b"),
        "immutability_locks": re.compile(r"\bfreeze\b|^[ \t]*record[ \t]+[A-Z]", re.M),
        "cleanup": re.compile(r"\bdef[ \t]+finalize\b|\bat_exit\b|\.(?:close|shutdown|dispose|cleanup)\b"),
        "encapsulation": re.compile(r"\b(?:private|protected)\b"),
        "listeners": re.compile(r"\.(?:subscribe|on)\(|\bSignal::[A-Z]+\.trap\b"),
        "test_skip": re.compile(r"\bpending(?:!|[ \t(]+[\"'])"),
        # --- PHASE 3: HYBRID DOMAIN SENSORS (Crystal specifics) ---
        "auth_middleware": re.compile(
            r"\b(?:Kemal::(?:BasicAuth|Session)|basic_auth|Authentic|Authorizable|Crypto::Bcrypt|JWT\.(?:encode|decode)"
            r"|require_sign_in)\b|\bauthenticate!"
        ),
        "serialization_parsing": re.compile(
            r"\b(?:JSON|YAML|XML|CSV|INI|MessagePack)(?:\.(?:parse|parse_raw|build|from_\w+)|::(?:Serializable|Any|PullParser|Builder))\b"
            r"|\.(?:to|from)_(?:json|yaml|msgpack)\b"
        ),
        "regex_execution": re.compile(r"\bRegex\b|\.(?:match|match!|scan|gsub|sub|matches\?)\b|=~|!~"),
        "time_date_logic": re.compile(
            r"\b(?:Time\.(?:utc|local|now|monotonic|measure|instant)|Time::(?:Span|Format|Location)|sleep)\b"
            r"|\.(?:milliseconds|seconds|minutes|hours|days)\b"
        ),
        # ipc_rpc_bridges: child processes, sockets and the C FFI (`@[Link]`).
        "ipc_rpc_bridges": re.compile(
            r"\b(?:Process\.(?:run|new|exec|fork)|HTTP::(?:Client|WebSocket)|TCPSocket|UNIXSocket|UDPSocket|GRPC|AMQP)\b"
            r"|\bsystem[ \t]*\(|%x\{|@\[Link\b"
        ),
        "system_config_mutation": re.compile(
            r"\bENV\[[^\]\n]{1,100}\][ \t]*=(?![=~])|\bDir\.cd\b|\bENV\.(?:delete|clear)\b|\bFile\.(?:chmod|chown)\b"
            r"|\bProcess\.chroot\b"
        ),
    },
}
