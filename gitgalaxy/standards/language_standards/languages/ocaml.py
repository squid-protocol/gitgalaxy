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
from gitgalaxy.standards.language_standards.identifiers import ID_CONTINUE, ID_START, SMALL

from .._shared_patterns import CALLS_OUT_UNSUPPORTED, GLOBAL_FRAGILE_DEBT, GLOBAL_PLANNED_DEBT

# A value name starts with a lowercase letter or `_` (a capital is a constructor or module); `'` may continue it.
_VALUE = r"[" + SMALL + r"][" + ID_CONTINUE + r"']*"
# Any name, for a module / type / class / exception.
_NAME = r"[" + ID_START + r"][" + ID_CONTINUE + r"']*"
# `let` / `let rec` / `and`, never `rec` itself as the bound name.
_BINDER = r"^(?:let|and)[ \t]+(?:rec[ \t]+)?(?!rec\b)"
# One parameter: `x`, `(x : int)`, `~lbl`, `~lbl:x`, `?(opt = 1)`, `~(x : t)`.
_PARAM = r"[~?]?(?:\([^()\n]+\)|[^\s=:|()~?]+)(?::(?:\([^()\n]+\)|[^\s=:|()~?]+))?"

DEFINITION: dict[str, Any] = {
    "_meta": {
        "target_version": "OCaml 5 (modules and functors, GADTs, effects, Dune/opam, ppx, Lwt / Eio)",
        "last_updated": "2026-11-11",
        "blueprint_version": "v5.0",
        "status": "production",
    },
    # Implementation, interface, lexer and Menhir grammar. `.ml` is not claimed by another profile.
    "extensions": [".ml", ".mli", ".mll", ".mly"],
    "exact_matches": [],
    # `dune-project` / `dune` / `*.opam` anchor an OCaml project.
    "discriminators": [".mli", ".opam", "dune-project", "dune"],
    "shebangs": ["ocaml", "ocamlrun", "ocamlscript"],
    # `(* ... *)` nested block comments have no lexical family yet (a `(*` `*)` pair is new to prism): like F#,
    # the family strips only `//`, which OCaml never writes, and a comment stays in the code stream
    # (docs/language_status, limitations). `import_capture_blank` keeps an `open` in a comment from being an import.
    "lexical_family": "recursive_block",
    # #6572: an `open` / `include` inside `(* ... *)` (one level, capped, so linear) holds no import.
    "import_capture_blank": r"\(\*(?:[^*]|\*(?!\)))" + r"{0,20000}\*\)",
    "rules": {
        # A call-graph extractor is not built yet (#6572 sibling): declare it unsupported rather than guess.
        "calls_out": CALLS_OUT_UNSUPPORTED,
        # A keyword, `->` or `|` inside a string literal is not a decision.
        "_scope_filters": {"branch": "outside_literals"},
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # branch: if, match, guards, loops, `try`, `function`, and match ARMS (a leading `|` whose line carries the
        # arrow; a variant constructor `| A of int` has none).
        "branch": re.compile(r"\b(?:if|match|when|while|for|try|function)\b|^[ \t]*\|(?![|\]}])[^\n]*->", re.M),
        # args: group 1 is the curried parameter list of a binding that takes at least one parameter.
        "args": re.compile(
            _BINDER + _VALUE + r"[ \t]+(" + _PARAM + r"(?:[ \t]+" + _PARAM + r")*)[ \t]*(?::[^=\n]*)?=(?!=)",
            re.M,
        ),
        "_args_pattern_list_groups": {1},
        "structural_boundaries": re.compile(
            r"\b(?:module|type|let|in|and|val|external|exception|open|include|struct|sig|end|begin|match|with"
            r"|function|class|object|functor)\b"
        ),
        # func_start: a column-0 `let` / `let rec` / `and` binding that takes a parameter (`let f x =`,
        # `let f ~lbl (x : t) =`) or is bound straight to `fun` / `function` (`let f = fun x ->`). A bare
        # `let x = 1`, `let x : int = 3`, `let () =` and `let _ =` are values. Indented (module-body and local) bindings
        # and the `val` of an interface are not units yet.
        "func_start": re.compile(
            _BINDER
            + r"("
            + _VALUE
            + r")(?=[ \t]+[~?(\[{"
            + SMALL
            + r"]|[ \t]*(?::[^=\n]{0,200})?=[ \t]*(?:fun|function)\b)",
            re.M,
        ),
        # class_start: `module X`, `module type S`, `module rec`, `type t` (with parameters `'a t`, `('a, 'b) t`),
        # `class c`, `class type c`, `exception E`.
        "class_start": re.compile(
            r"^[ \t]*(?:module[ \t]+(?:rec[ \t]+|type[ \t]+)?|exception[ \t]+"
            r"|class[ \t]+(?:(?:virtual|type)[ \t]+)*(?:\[[^\]\n]{0,100}\][ \t]+)?"
            r"|type[ \t]+(?:nonrec[ \t]+)?(?:'[a-z_]\w{0,60}[ \t]+|\([^()\n]{0,200}\)[ \t]+)?)"
            r"(" + _NAME + r")",
            re.M,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        "safety": re.compile(
            r"\btry\b|\b(?:List\.find_opt|Hashtbl\.find_opt|Option\.(?:value|bind|map|fold|join|is_some)"
            r"|Result\.(?:bind|map|map_error|value))\b|\bNone[ \t]*->|\b[a-z_]\w*_opt\b"
        ),
        "safety_bypasses": re.compile(
            r"\b(?:Obj\.(?:magic|repr|obj)|Option\.get|List\.(?:hd|tl|nth)|Array\.unsafe_(?:get|set)"
            r"|(?:String|Bytes)\.unsafe_\w+|Marshal\.from_\w+)\b|\bassert[ \t]+false\b|^[ \t]*\[@@@(?:ocaml\.)?warning\b"
            r"|\[@(?:ocaml\.)?warning[ \t]+\"-",
            re.M,
        ),
        "high_risk_execution": re.compile(
            r"\b(?:Sys\.command|Unix\.(?:exec\w*|system|open_process\w*|create_process\w*)|Dynlink\.loadfile\w*"
            r"|Toploop\.\w+)\b"
        ),
        "io": re.compile(
            r"\b(?:open_in(?:_bin)?|open_out(?:_bin)?|input_line|input_char|really_input(?:_string)?|output_string"
            r"|output_char|read_line|In_channel\.\w+|Out_channel\.\w+"
            r"|Unix\.(?:openfile|read|write|socket|connect|bind|listen|accept|send|recv)"
            r"|Lwt_io\.\w+|Lwt_unix\.\w+|Eio\.(?:Path|Flow|Net)\.\w+)\b"
        ),
        "api": re.compile(
            r"\b(?:Cohttp\w*\.\w+|Dream\.(?:get|post|put|delete|patch|router|run|scope)|Opium\.\w+|Piaf\.\w+"
            r"|Resto\w*\.\w+|Httpaf\.\w+|H2\.\w+)\b"
        ),
        "state_mutation": re.compile(
            r"<-(?![-<])|:=(?!=)|\b(?:incr|decr)\b"
            r"|\b(?:Hashtbl\.(?:add|replace|remove|reset|clear)|Array\.(?:set|fill|blit|sort)|Bytes\.(?:set|fill|blit)"
            r"|Buffer\.(?:add_\w+|clear|reset))\b"
        ),
        "dead_code": re.compile(r"^[ \t]*\(\*[ \t]*(?:let|open|module|include|type|print_\w+|Printf\.printf)\b", re.M),
        # doc: `(** ... *)` doc comments (not the empty `(**)`) and `[@@ocaml.doc` attributes.
        "doc": re.compile(r"\(\*\*(?![*)])|\[@@?ocaml\.doc\b"),
        "test": re.compile(
            r"\b(?:Alcotest|OUnit2?|QCheck2?|Crowbar)\b|\blet%(?:test|expect_test|test_unit)\b|%expect_test\b|\[%expect\b"
            r"|\bassert_equal\b"
        ),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        "concurrency": re.compile(
            r"\b(?:Thread\.\w+|Mutex\.\w+|Condition\.\w+|Domain\.\w+|Atomic\.\w+|Event\.\w+"
            r"|Lwt\.(?:async|join|pick|choose|bind|both)|Lwt_main\.run|Eio\.(?:Fiber|Domain|Switch)\.\w+"
            r"|Effect\.\w+|Async\.\w+)\b|\blet%lwt\b|\blet\*"
        ),
        "ui_framework": re.compile(
            r"\b(?:GMain|GtkMisc|Lablgtk\w*|Dom_html|Brr\.\w+|Incr_dom\.\w+|Bonsai\.\w+|Vdom\.\w+|Notty\.\w+|Minttea\.\w+)\b"
        ),
        "closures": re.compile(r"\bfun\b|\bfunction\b"),
        "globals": re.compile(
            r"^let[ \t]+" + _VALUE + r"[ \t]*(?::[^=\n]*)?=[ \t]*ref\b|\bSys\.getenv(?:_opt)?\b", re.M
        ),
        "decorators": re.compile(r"\[@{1,3}[a-z_][a-z_.]*"),
        "generics": re.compile(r"(?<![\w'])'[a-z_]\w{0,40}(?!['\w])"),
        "comprehensions": re.compile(
            r"\b(?:List|Array|Seq|Hashtbl|Option|Result)\."
            r"(?:map|mapi|map2|filter|filter_map|fold_left|fold_right|fold|iter|iteri|concat_map|flat_map|exists|for_all)\b"
        ),
        "scientific": re.compile(
            r"\b(?:Owl\w*|Lacaml\w*|Bigarray|Gsl\w*)\b|\bFloat\.(?:sqrt|exp|log|pow|sin|cos|tan|abs)\b"
        ),
        "reflection_metaprogramming": re.compile(
            r"\b(?:Obj\.\w+|Marshal\.\w+|Dynlink\.\w+|Toploop\.\w+|Printexc\.\w+)\b|\[%+[a-z_]"
        ),
        "import": re.compile(r"^[ \t]*(?:open!?|include)[ \t]+[A-Z]|^#(?:require|use|load)\b", re.M),
        # Group 1 is a module path (`open Core.Std`, `include Foo_bar`), group 2 a toplevel directive's string
        # (`#require "lwt"`).
        "_dependency_capture": re.compile(
            r"^[ \t]*(?:open!?|include)[ \t]+("
            + r"[A-Z]["
            + ID_CONTINUE
            + r"']*(?:\.[A-Z]["
            + ID_CONTINUE
            + r"']*)*)|^#(?:require|use|load)[ \t]+\"([^\"\n]+)\"",
            re.M,
        ),
        "ownership": re.compile(
            r"\(\*+[ \t]*(?:@author|Authors?|Created[ \t]+by|Maintainers?|Owners?)[ \t]*:?[ \t]*(\S[^\n]*?)[ \t]*(?:\*\))?[ \t]*$",
            re.I | re.M,
        ),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        "planned_debt": GLOBAL_PLANNED_DEBT,
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d{1,10}|spec|audit)[^\]]{0,300}\]", re.I),
        "events": re.compile(
            r"\b(?:Lwt_condition\.\w+|Event\.\w+|React\.\w+|Lwt_react\.\w+|Sys\.(?:signal|set_signal))\b"
        ),
        "dependency_injection": re.compile(r"\bfunctor\b|^[ \t]*module[ \t]+[A-Z]\w*[ \t]*\([A-Z]\w*[ \t]*:", re.M),
        "macros": re.compile(r"\[%+[a-z_][\w.]*|\{%[a-z_]\w*|\blet%\w+"),
        "pointers": re.compile(r"\bref[ \t]+[\w(\[{'\"]|\bCtypes\.\w+|\bObj\.(?:magic|repr|obj)\b"),
        "memory_alloc": re.compile(
            r"\b(?:Bytes\.(?:create|make|extend)|Array\.(?:make|create_float|init)|Buffer\.create"
            r"|Bigarray\.\w+\.create|Gc\.\w+|Hashtbl\.create|Weak\.create|Ephemeron\.\w+)\b"
        ),
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        "telemetry": re.compile(
            r"\b(?:Logs\.\w+|Log\.(?:info|debug|warn|err|app)|Lwt_log\w*\.\w+|Prometheus\w*\.\w+|Opentelemetry\w*\.\w+)\b"
        ),
        "debug_prints": re.compile(
            r"\b(?:Printf\.(?:printf|eprintf)|Format\.(?:printf|eprintf)|print_endline|prerr_endline|print_string"
            r"|prerr_string|print_newline|Printexc\.print_backtrace)\b"
        ),
        "explicit_casts": re.compile(
            r"\b(?:int_of_\w+|float_of_\w+|string_of_\w+|bool_of_string|char_of_int|Int\.(?:of_string|to_string)"
            r"|Float\.(?:of_int|to_int|of_string)|Int64\.of_\w+|Int32\.of_\w+|Obj\.magic|truncate)\b"
        ),
        "panics_and_aborts": re.compile(
            r"\b(?:failwith|invalid_arg|raise|raise_notrace|exit|Stdlib\.exit|Unix\._exit)\b|\bassert[ \t]+false\b"
        ),
        "thread_sleeps": re.compile(
            r"\b(?:Unix\.sleepf?|Thread\.delay|Lwt_unix\.sleep|Eio\.Time\.sleep)[ \t]+\(?[ \t]*[0-9]"
        ),
        "bitwise_ops": re.compile(r"\b(?:land|lor|lxor|lnot|lsl|lsr|asr)\b"),
        "sync_locks": re.compile(
            r"\b(?:Mutex\.(?:lock|unlock|protect|try_lock)|Condition\.(?:wait|signal|broadcast)|Semaphore\.\w+"
            r"|Lwt_mutex\.\w+|Eio\.Mutex\.\w+)\b"
        ),
        "immutability_locks": re.compile(r"=[ \t]*private\b|\bBytes\.(?:to_string|sub_string)\b"),
        "cleanup": re.compile(
            r"\b(?:close_in(?:_noerr)?|close_out(?:_noerr)?|Fun\.protect|Unix\.close|Lwt_io\.close|at_exit"
            r"|In_channel\.close|Out_channel\.close|Gc\.finalise|with_open_\w+)\b|~finally\b"
        ),
        "encapsulation": re.compile(r"\bsig\b|^[ \t]*module[ \t]+type\b|=[ \t]*private\b", re.M),
        "listeners": re.compile(
            r"\b(?:Unix\.(?:listen|accept)|Lwt_unix\.(?:listen|accept)|Eio\.Net\.(?:listen|accept\w*|run_server)"
            r"|Dream\.run|Lwt_io\.establish_server\w*|Cohttp_lwt_unix\.Server\.create)\b"
        ),
        "test_skip": re.compile(r"\bAlcotest\.skip\b|\btest_case_skip\b|\bskip_if\b|\[@tags[ \t]+\"disabled\"\]"),
        # --- PHASE 3: HYBRID DOMAIN SENSORS (OCaml specifics) ---
        "auth_middleware": re.compile(
            r"\b(?:Jwto?|Jose|Bcrypt|Argon2|Oauth2?\w*|Mirage_crypto\w*|X509|Dream\.(?:session|csrf)\w*)\b"
        ),
        "serialization_parsing": re.compile(
            r"\b(?:Yojson|Ezjsonm|Jsonm|Sexplib\d*|Sexp|Marshal|Atdgen|Bin_prot|Xmlm|Csv|Angstrom|Cbor)\b"
            r"|\[@@deriving[ \t]+[^\]\n]{0,100}(?:yojson|sexp|bin_io|protobuf)"
        ),
        "regex_execution": re.compile(
            r"\b(?:Str\.\w+|Re\.(?:Perl|Posix|Pcre|Str|compile|exec\w*|execp|replace\w*|split|matches|all)|Re2\.\w+"
            r"|Pcre\.\w+)\b"
        ),
        "time_date_logic": re.compile(
            r"\b(?:Unix\.(?:time|gettimeofday|gmtime|localtime|mktime)|Ptime\w*\.\w+|Sys\.time|Mtime\w*\.\w+"
            r"|Timedesc\.\w+|Time_ns\.\w+|Eio\.Time\.\w+|Calendar\w*\.\w+)\b"
        ),
        "ipc_rpc_bridges": re.compile(
            r"\b(?:Grpc\w*\.\w+|Capnp\w*\.\w+|Async_rpc\w*\.\w+|Rpc\.\w+|Unix\.(?:pipe|socketpair)"
            r"|Lwt_unix\.(?:pipe|socketpair)|Zmq\w*\.\w+)\b"
        ),
        "system_config_mutation": re.compile(
            r"\b(?:Unix\.(?:putenv|chdir|chmod|chown|umask|setuid|setgid|chroot|setsid|unlink|rmdir|mkdir|rename)"
            r"|Sys\.(?:chdir|remove|rename|mkdir|rmdir|putenv)|Gc\.set"
            r"|Lwt_unix\.(?:chdir|unlink|mkdir|rename|rmdir|chmod))\b"
        ),
    },
}
