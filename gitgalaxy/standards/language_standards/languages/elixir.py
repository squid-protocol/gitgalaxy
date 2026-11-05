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

# An Elixir name: lowercase or `_` start, then word characters, with an optional `?` / `!` suffix.
_FN = r"[a-z_][" + ID_CONTINUE + r"]*[?!]?"
# A module alias: `Foo`, `Foo.Bar.Baz`, `__MODULE__`.
_MOD = r"[A-Z][" + ID_CONTINUE + r"]*(?:\.[A-Z][" + ID_CONTINUE + r"]*)*"

DEFINITION: dict[str, Any] = {
    "_meta": {
        "target_version": "Elixir 1.x (modules, protocols, macros, GenServer/OTP behaviours, Phoenix/Ecto)",
        "last_updated": "2026-11-05",
        "blueprint_version": "v5.0",
        "status": "production",
    },
    "extensions": [".ex", ".exs"],
    "exact_matches": [],
    # `mix.exs` / `mix.lock` anchor an Elixir project (the Mix build tool's project file and lockfile).
    "discriminators": ["mix.exs", "mix.lock"],
    "shebangs": ["elixir"],
    # `#` line comments only; `@doc` / `@moduledoc` heredocs are string literals, shielded with the strings.
    "lexical_family": "line_exclusive",
    "rules": {
        # A call-graph extractor is not built yet (#6572 sibling): declare it unsupported rather than guess.
        "calls_out": CALLS_OUT_UNSUPPORTED,
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        "branch": re.compile(
            r"\b(?:if|unless|else|case|cond|with|for|try|rescue|catch|receive)\b|->|&&|\|\||\band\b|\bor\b"
        ),
        # args: group 1 is the parenthesised parameter list of a `def` / `defp` / `defmacro` / `defmacrop`.
        "args": re.compile(
            r"\b(?:def|defp|defmacro|defmacrop|defguard|defguardp)[ \t]+" + _FN + r"[ \t]*\(([^)\n]*)\)"
        ),
        "structural_boundaries": re.compile(
            r"\b(?:defmodule|defprotocol|defimpl|def|defp|defmacro|defmacrop|defguard|defguardp|defstruct|defdelegate"
            r"|import|alias|require|use|end)\b"
        ),
        # func_start: a function, private function, macro or guard clause head. Clauses of one function each match.
        "func_start": re.compile(
            r"^[ \t]*(?:def|defp|defmacro|defmacrop|defguard|defguardp)[ \t]+(?:unquote\()?(" + _FN + r")(?=[ \t(,]|$)",
            re.M,
        ),
        # class_start: a module, protocol or protocol implementation. Group 1 is the module name.
        "class_start": re.compile(
            r"^[ \t]*(?:defmodule|defprotocol|defimpl)[ \t]+(" + _MOD + r")",
            re.M,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        "safety": re.compile(
            r"\b(?:rescue|catch|after|with)\b|\{:ok,|\{:error,|\bis_(?:nil|binary|integer|atom|map|list)\("
        ),
        "safety_bypasses": re.compile(
            r"\bString\.to_atom\(|\bBinary\.to_term\(|:erlang\.binary_to_term\(|\bCode\.(?:eval_string|eval_quoted)\("
            r"|@dialyzer[ \t]+\{:nowarn_function"
        ),
        "high_risk_execution": re.compile(
            r"\b(?:System\.(?:cmd|shell|halt)|Code\.(?:eval_string|eval_file|compile_string)|:os\.cmd|Port\.open)\b"
        ),
        "io": re.compile(r"\b(?:File|IO|Path|Port|Stream\.resource)\.[a-z_]+|\b(?::gen_tcp|:gen_udp|:file)\."),
        "api": re.compile(
            r"^[ \t]*(?:get|post|put|patch|delete|resources|live|forward|pipe_through)[ \t]+[\"':/]", re.M
        ),
        "state_mutation": re.compile(
            r"\b(?:Agent\.(?:update|get_and_update|cast)|:ets\.(?:insert|delete|update_counter|new)|Process\.put"
            r"|:persistent_term\.put|Application\.put_env|Repo\.(?:insert|update|delete)!?)\b"
        ),
        # dead_code: a commented-out definition or call, not prose that starts with the word.
        "dead_code": re.compile(r"^[ \t]*#[ \t]*(?:defp?|defmodule|IO\.inspect|IO\.puts)[ \t]+[\w.(\"]", re.M),
        "doc": re.compile(r"^[ \t]*@(?:doc|moduledoc|typedoc)[ \t]+(?:\"\"\"|~[sS]\"\"\"|\"|false)", re.M),
        "test": re.compile(
            r"^[ \t]*(?:describe|test|setup|setup_all)[ \t(]+[\"':]?|\buse[ \t]+(?:ExUnit\.Case|[A-Z]\w*\.(?:ConnCase|DataCase))"
            r"|\b(?:assert|refute|assert_receive|assert_raise)\b",
            re.M,
        ),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        "concurrency": re.compile(
            r"\b(?:spawn(?:_link|_monitor)?|Task\.(?:async|await|Supervisor)|GenServer|Agent|Supervisor|Registry"
            r"|DynamicSupervisor|GenStage|Flow)\b|\bsend\("
        ),
        "ui_framework": re.compile(
            r"\b(?:Phoenix\.(?:LiveView|Component|HTML)|LiveView|Phoenix\.LiveComponent|Scenic)\b"
        ),
        "closures": re.compile(r"\bfn\b|&\(|&[A-Za-z_.]+/\d+|&\d"),
        "globals": re.compile(
            r"\b(?:System\.get_env|Application\.(?:get_env|fetch_env!?)|:persistent_term)\b|@[a-z_]+[ \t]+[^\n]"
        ),
        "decorators": re.compile(
            r"^[ \t]*@(?:impl|spec|callback|behaviour|type|typep|opaque|derive|deprecated)\b", re.M
        ),
        "generics": re.compile(
            r"^[ \t]*@(?:spec|callback|type|typep|opaque)[ \t]+[^\n]*\b(?:list|map|keyword|tuple)\(", re.M
        ),
        "comprehensions": re.compile(r"\bfor[ \t]+[a-z_][\w]*[ \t]*<-|\bEnum\.(?:map|filter|reduce|flat_map|reject)\b"),
        "scientific": re.compile(r"\b(?:Nx|Axon|Explorer|Scholar|Decimal|:math)\b"),
        "reflection_metaprogramming": re.compile(
            r"\b(?:quote|unquote|unquote_splicing|defmacrop?|__using__|__before_compile__|__CALLER__|Macro\.[a-z_]+"
            r"|Module\.(?:create|put_attribute|get_attribute)|apply|function_exported\?|Code\.ensure_loaded\??)\b"
        ),
        "import": re.compile(r"^[ \t]*(?:import|alias|require|use)[ \t]+[A-Z:]", re.M),
        # Group 1 is the module; a multi-alias `alias Foo.{Bar, Baz}` names its prefix `Foo`.
        "_dependency_capture": re.compile(r"^[ \t]*(?:import|alias|require|use)[ \t]+(" + _MOD + r")", re.M),
        "ownership": re.compile(
            r"^[ \t]*#+[ \t]*(?:Authors?|Created[ \t]+by|Maintainers?|Owners?|Contact)[ \t]*:(?![:=])[ \t]*(\S[^\n]*?)[ \t]*$",
            re.I | re.M,
        ),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        "planned_debt": GLOBAL_PLANNED_DEBT,
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d{1,10}|spec|audit)[^\]]{0,300}\]", re.I),
        "ssr_boundaries": re.compile(
            r"\b(?:Phoenix\.(?:Controller|Endpoint|Router)|Plug\.(?:Router|Conn|Builder)|use[ \t]+Phoenix\.LiveView)\b"
        ),
        "events": re.compile(r"\b(?:Phoenix\.PubSub|:telemetry\.execute|GenEvent|Registry\.dispatch|broadcast!?)\b"),
        "dependency_injection": re.compile(
            r"\bApplication\.(?:get_env|compile_env)\b|\bMox\.(?:defmock|expect|stub)\b"
        ),
        "macros": re.compile(r"^[ \t]*defmacrop?[ \t]", re.M),
        "pointers": None,
        "memory_alloc": None,
        "inline_asm": None,
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        "telemetry": re.compile(
            r"\bLogger\.(?:debug|info|notice|warning|warn|error|critical|alert|emergency)\b|:telemetry\."
        ),
        "debug_prints": re.compile(r"\bIO\.(?:inspect|puts)\b|\bdbg\(|\bIEx\.pry\b"),
        "explicit_casts": re.compile(
            r"\b(?:String\.to_(?:integer|float|atom|existing_atom)|Integer\.parse|Float\.parse|to_string)\b"
        ),
        "panics_and_aborts": re.compile(r"\b(?:raise|exit|throw)\b|\bSystem\.halt\b"),
        "thread_sleeps": re.compile(r"\b(?:Process\.sleep|:timer\.sleep)\([ \t]*[0-9_]+"),
        "bitwise_ops": re.compile(r"\b(?:band|bor|bxor|bsl|bsr|bnot)\b|&&&|\|\|\||<<<|>>>|\^\^\^"),
        "sync_locks": re.compile(r"\b(?::global\.(?:set_lock|trans)|:sys\.suspend|Registry\.lock|:pg\.join)\b"),
        "immutability_locks": re.compile(r"^[ \t]*@enforce_keys\b|\bdefstruct\b", re.M),
        "cleanup": re.compile(r"\bdef[ \t]+terminate\(|\bon_exit\(|\bProcess\.(?:flag|exit)\b|\bafter\b"),
        "encapsulation": re.compile(r"\bdefp\b|\bdefmacrop\b|@moduledoc[ \t]+false"),
        "listeners": re.compile(r"\bdef[ \t]+handle_(?:call|cast|info|event|continue)\(|\breceive[ \t]+do\b"),
        "test_skip": re.compile(r"^[ \t]*@(?:tag[ \t]+:skip|moduletag[ \t]+:skip)\b", re.M),
        # --- PHASE 3: HYBRID DOMAIN SENSORS (Elixir specifics) ---
        "auth_middleware": re.compile(
            r"\b(?:Guardian|Pow|Bcrypt|Argon2|Pbkdf2|Plug\.BasicAuth|Phoenix\.Token|require_authenticated)\b"
        ),
        "serialization_parsing": re.compile(
            r"\b(?:Jason|Poison|Jsonrs|Phoenix\.Param|YamlElixir|CSV|Floki|SweetXml)\.[a-z_]+!?"
        ),
        "regex_execution": re.compile(r"\bRegex\.[a-z_]+|~r[/|({\[]|=~"),
        "time_date_logic": re.compile(
            r"\b(?:DateTime|NaiveDateTime|Date|Time|Calendar)\.[a-z_]+|~[UDNT]\[|:timer\.[a-z_]+"
        ),
        "ipc_rpc_bridges": re.compile(
            r"\b(?:Node\.(?:connect|spawn)|:rpc\.call|GRPC|Port\.open|System\.cmd|:gen_tcp|HTTPoison|Tesla|Finch|Req)\b"
        ),
        "system_config_mutation": re.compile(
            r"(?:\b(?:System\.put_env|Application\.put_env|File\.(?:chmod|chown|rm_rf))|(?<![\w:]):os\.putenv)\b"
        ),
    },
}
