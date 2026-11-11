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

# An Erlang atom: lowercase start, then word characters or `@`; or a quoted atom.
_ATOM = r"(?:[a-z][" + ID_CONTINUE + r"@]*|'[^'\n]+')"
# A parameter list: one level of nested parentheses (`f({A, B}, g(X))`), no newline.
_PARAMS = r"(?:[^()\n]|\([^()\n]*\))*"

DEFINITION: dict[str, Any] = {
    "_meta": {
        "target_version": "Erlang/OTP 2x (modules, behaviours, gen_server / gen_statem / supervisor, EUnit, Common Test)",
        "last_updated": "2026-11-11",
        "blueprint_version": "v5.0",
        "status": "production",
    },
    "extensions": [".erl", ".hrl", ".escript"],
    "exact_matches": [],
    # `rebar.config` / `rebar.lock` anchor a rebar3 project.
    "discriminators": ["rebar.config", "rebar.lock"],
    "shebangs": ["escript"],
    # `%` line comments only.
    "lexical_family": "line_exclusive",
    # #6572: a `%` comment and a "..." string (which may span lines) hold no imports. A comment is consumed first
    # so a stray `"` in it cannot open a string; escapes are honoured; capped, so linear. Only a string spanning
    # lines is blanked: a one-line `-include("x.hrl").` keeps its quoted path.
    "import_capture_blank": r"%[^\n]*" + r'|"(?:[^"\\]|\\[\s\S]){0,20000}"',
    "import_capture_multiline_only": True,
    # Mode E units are clause/statement buckets, not named routines (#2866 corollary 4).
    "invocation_model": "positional",
    "rules": {
        # A call-graph extractor is not built yet (#6572 sibling): declare it unsupported rather than guess.
        "calls_out": CALLS_OUT_UNSUPPORTED,
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        "branch": re.compile(r"\b(?:if|case|of|try|catch|after|receive|andalso|orelse)\b|->"),
        # args: group 1 is the parameter list of a function clause head at the start of a line.
        "args": re.compile(r"^" + _ATOM + r"[ \t]*\((" + _PARAMS + r")\)[ \t]*(?:when\b|->|$)", re.M),
        "structural_boundaries": re.compile(
            r"^-(?:module|behaviou?r|record|include|include_lib|import|export|define|spec|callback)\b|^"
            + _ATOM
            + r"[ \t]*\(",
            re.M,
        ),
        # func_start: a clause head at column 0 (`name(Args) ->`, `name(Args) when Guard ->`). Attributes start with
        # `-`, so they never match. Clauses of one function each match.
        "func_start": re.compile(r"^(" + _ATOM + r")[ \t]*\(" + _PARAMS + r"\)[ \t]*(?:when\b|->|$)", re.M),
        # class_start: `-module(x).`, `-behaviour(x).` and `-record(x,`. Group 1 is the name.
        "class_start": re.compile(r"^-(?:module|behaviou?r|record)[ \t]*\([ \t]*(" + _ATOM + r")", re.M),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        "safety": re.compile(
            r"\b(?:try|catch|after)\b|\{ok,|\{error,|\bis_(?:atom|binary|integer|list|map|tuple|pid)\("
        ),
        "safety_bypasses": re.compile(
            r"\berlang:halt\(|\bbinary_to_term\((?![^)\n]*safe)|\bbinary_to_atom\(|\blist_to_atom\("
            r"|^-dialyzer\([ \t]*\{?no_",
            re.M,
        ),
        "high_risk_execution": re.compile(
            r"\b(?:os:cmd|erl_eval:\w+|erlang:apply|apply|open_port|code:load_\w+|compile:file|erl_scan:string)\("
        ),
        "io": re.compile(
            r"\b(?:file:(?:read|write|open|close|delete|consult|read_file|write_file|rename|copy)\w*"
            r"|gen_tcp:\w+|gen_udp:\w+|ssl:\w+|io:(?:format|fwrite|put_chars|get_line|read)|filelib:\w+|disk_log:\w+)\("
        ),
        "api": re.compile(
            r"\b(?:cowboy_req:\w+|cowboy:start_\w+|httpc:request|inets:start|mochiweb\w*:\w+|elli:\w+)\("
        ),
        "state_mutation": re.compile(
            r"\b(?:ets:(?:insert|delete|update_\w+)|put|erase|persistent_term:put|mnesia:(?:write|delete))\("
        ),
        "dead_code": re.compile(r"^[ \t]*%+[ \t]*(?:-?(?:export|module|include)|io:format)[ \t(]", re.M),
        "doc": re.compile(r"^[ \t]*(?:%%[ \t]*@(?:doc|spec|end)|-(?:doc|moduledoc)[ \t(])", re.M),
        "test": re.compile(
            r"\?(?:assert\w*|_assert\w*)\(|\b(?:eunit|ct|meck|proper|triq):\w+|_test_?\(|^all\(\)", re.M
        ),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        "concurrency": re.compile(
            r"\b(?:spawn|spawn_link|spawn_monitor|spawn_opt|monitor|link|process_flag|pg:\w+|global:\w+|pool:\w+)\("
            r"|\breceive\b|\bgen_(?:server|statem|event|fsm):\w+|\bsupervisor:\w+|![ \t]*[A-Za-z{(]"
        ),
        "ui_framework": re.compile(r"\b(?:wx\w*:\w+|wxFrame|nitrogen:\w+|wf:\w+)\("),
        "closures": re.compile(r"\bfun[ \t]*\(|\bfun[ \t]+[a-z]\w*(?::[a-z]\w*)?/\d+"),
        "globals": re.compile(r"\b(?:application:get_env|application:set_env|persistent_term:\w+|get_env)\("),
        "decorators": re.compile(r"^-(?:spec|callback|opaque|type|dialyzer|compile|on_load)\b", re.M),
        "generics": re.compile(r"^-(?:spec|callback|type|opaque)\b", re.M),
        "comprehensions": re.compile(r"\blists:(?:map|filter|foldl|foldr|flatmap|filtermap|foreach)\(|\|\|"),
        "scientific": re.compile(r"\b(?:math|rand|crypto):\w+\("),
        "reflection_metaprogramming": re.compile(
            r"\b(?:erlang:(?:function_exported|module_info|get_module_info)|module_info|apply|code:\w+|erl_parse:\w+"
            r"|parse_transform)\b"
        ),
        "import": re.compile(r"^-(?:include|include_lib|import|behaviou?r)[ \t]*\(", re.M),
        # Group 1 is the header file or module: `-include("x.hrl").`, `-include_lib("app/include/x.hrl").`,
        # `-import(lists, [map/2]).`, `-behaviour(gen_server).`.
        "_dependency_capture": re.compile(
            r"^-(?:include|include_lib)[ \t]*\([ \t]*\"([^\"\n]+)\"|^-(?:import|behaviou?r)[ \t]*\([ \t]*("
            + _ATOM
            + r")",
            re.M,
        ),
        "ownership": re.compile(
            r"^[ \t]*%+[ \t]*(?:@author|Authors?|Created[ \t]+by|Maintainers?|Owners?)[ \t]*:?[ \t]*(\S[^\n]*?)[ \t]*$",
            re.I | re.M,
        ),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        "planned_debt": GLOBAL_PLANNED_DEBT,
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d{1,10}|spec|audit)[^\]]{0,300}\]", re.I),
        "events": re.compile(r"\b(?:gen_event:\w+|gen_statem:\w+|handle_event|handle_info|handle_cast|handle_call)\b"),
        "dependency_injection": re.compile(r"\b(?:meck:(?:new|expect)|application:get_env)\("),
        "macros": re.compile(r"\?[A-Z_][A-Z0-9_]*|^-define[ \t]*\(", re.M),
        "pointers": re.compile(r"\b(?:erlang:(?:make_ref|ref_to_list)|enif_\w+)\b|\bmake_ref\("),
        "memory_alloc": re.compile(r"\b(?:ets:new|binary:copy|array:new|erlang:garbage_collect)\("),
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        "telemetry": re.compile(r"\b(?:logger:\w+|error_logger:\w+|telemetry:execute|\?LOG_\w+|lager:\w+)\b"),
        "debug_prints": re.compile(r"\b(?:io:format|io:fwrite|erlang:display|dbg:\w+)\("),
        "explicit_casts": re.compile(
            r"\b(?:list_to_\w+|\w+_to_list|\w+_to_binary|binary_to_\w+|integer_to_\w+|float_to_\w+)\("
        ),
        "panics_and_aborts": re.compile(r"\b(?:erlang:error|erlang:exit|exit|error|erlang:halt|init:stop)\("),
        "thread_sleeps": re.compile(r"\btimer:sleep\([ \t]*[0-9]"),
        "bitwise_ops": re.compile(r"\b(?:band|bor|bxor|bnot|bsl|bsr)\b"),
        "sync_locks": re.compile(r"\b(?:global:set_lock|global:trans|mnesia:(?:lock|transaction)|sys:suspend)\("),
        "immutability_locks": re.compile(r"\bets:setopts\([^)\n]*protected|\b(?:protected|private)\b[ \t]*[,\]]"),
        "cleanup": re.compile(r"\b(?:after|terminate|ets:delete|file:close|gen_tcp:close|erlang:demonitor|unlink)\b"),
        "encapsulation": re.compile(r"^-export(?:_type)?[ \t]*\(", re.M),
        "listeners": re.compile(r"\b(?:gen_tcp:(?:listen|accept)|ranch:start_\w+|cowboy:start_\w+|gen_udp:open)\("),
        "test_skip": re.compile(r"\{skip,|\bct:(?:skip|comment)\(|_skip_|^-ifdef\(TEST", re.M),
        # --- PHASE 3: HYBRID DOMAIN SENSORS (Erlang specifics) ---
        "auth_middleware": re.compile(
            r"\b(?:cowboy_basic_auth|oauth2?\w*:\w+|jwt:\w+|jose_\w+:\w+|bcrypt:\w+|pbkdf2:\w+)\b"
        ),
        "serialization_parsing": re.compile(
            r"\b(?:jsx|jiffy|json|thoas|term_to_binary|binary_to_term|xmerl_scan|yamerl|erlang:(?:term|binary)_to_\w+)\b"
        ),
        "regex_execution": re.compile(r"\bre:(?:run|replace|split|compile)\("),
        "time_date_logic": re.compile(
            r"\b(?:calendar:\w+|erlang:(?:system_time|monotonic_time|timestamp|localtime|universaltime)|os:timestamp"
            r"|timer:(?:send_after|apply_after|tc))\b"
        ),
        "ipc_rpc_bridges": re.compile(r"\b(?:rpc:\w+|erpc:\w+|net_kernel:\w+|net_adm:\w+|gen_rpc:\w+|erl_ddll:\w+)\("),
        "system_config_mutation": re.compile(
            r"\b(?:application:set_env|os:putenv|os:unsetenv|code:(?:add_path|add_patha|add_pathz|del_path)|erlang:system_flag"
            r"|init:restart)\("
        ),
    },
}
