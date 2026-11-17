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

from .._shared_patterns import CALLS_OUT_UNSUPPORTED, GLOBAL_FRAGILE_DEBT, GLOBAL_PLANNED_DEBT

# A Nim identifier (style-insensitive, but written with letters, digits and `_`).
_NAME = r"[" + ID_START + r"][" + ID_CONTINUE + r"]*"
# A routine name: an identifier or a backticked operator (`` `+` ``, `` `[]=` ``).
_ROUTINE_NAME = r"(?:`[^`\n]{1,30}`|" + _NAME + r")"
# The keyword that opens a routine definition.
_ROUTINE = r"(?:proc|func|method|iterator|template|macro|converter)"

DEFINITION: dict[str, Any] = {
    "_meta": {
        "target_version": "Nim 2.x (procs, templates, macros, ARC / ORC, async, Nimble)",
        "last_updated": "2026-11-11",
        "blueprint_version": "v5.0",
        "status": "production",
    },
    # Source, script / config and package files. No other profile claims these.
    "extensions": [".nim", ".nims", ".nimble"],
    "exact_matches": [],
    "discriminators": [".nimble", ".nims"],
    "shebangs": ["nim", "nimscript"],
    # `#` line comments. A `#[ ... ]#` block comment stays in the code stream for the rules (the family has no
    # nested-block form); `import_capture_blank` keeps an import inside one, or inside a string, from counting.
    "lexical_family": "line_exclusive",
    # #6572: a `#[ ... ]#` block (one level, lazy with a fixed terminator), a `"""` string, a `#` line comment and a
    # one-line `"..."` string hold no imports. The block form is first so `#[` is not read as a line comment.
    "import_capture_blank": r"#\[[\s\S]*?\]#"
    + "|"
    + r'"""[\s\S]*?"""'
    + "|"
    + r"#[^\n]*"
    + "|"
    + r'"(?:[^"\\\n]|\\.){0,20000}"',
    "rules": {
        # A call-graph extractor is not built yet (#6572 sibling): declare it unsupported rather than guess.
        "calls_out": CALLS_OUT_UNSUPPORTED,
        # A keyword inside a string literal is not a decision.
        "_scope_filters": {"branch": "outside_literals"},
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # branch: if / elif / else / when / case / of arms / loops / try-except-finally. An `of` counts only as a
        # case arm (line-leading): `object of RootObj` is inheritance.
        "branch": re.compile(
            r"\b(?:if|elif|else|when|case|for|while|try|except|finally)\b|^[ \t]*of\b",
            re.M,
        ),
        # args: group 1 is the parenthesised parameter list of a routine, after an optional `*` export mark and
        # generic parameters.
        "args": re.compile(
            r"\b" + _ROUTINE + r"[ \t]+" + _ROUTINE_NAME + r"\*?[ \t]*(?:\[[^\]\n]{0,200}\])?[ \t]*\(([^)\n]*)\)"
        ),
        "structural_boundaries": re.compile(
            r"\b(?:proc|func|method|iterator|template|macro|converter|type|object|enum|tuple|concept|import|from|include"
            r"|export|const|let|var|block|when)\b"
        ),
        # func_start: a routine definition at any indent. Group 1 is the name (a backticked operator keeps its
        # backticks). A `proc` type (`proc (x: int)`) names nothing, so it never matches.
        "func_start": re.compile(r"^[ \t]*" + _ROUTINE + r"[ \t]+(" + _ROUTINE_NAME + r")(?=[ \t]*[*(\[=:{])", re.M),
        # class_start: a `type` section entry that declares an `object`, `enum`, `tuple`, `concept` or `distinct`
        # type, with or without the `type` keyword on the line (`ref object` / `ptr object` allowed). Group 1 is
        # the name. A plain alias (`type A = int`) is not a class.
        "class_start": re.compile(
            r"^[ \t]*(?:type[ \t]+)?("
            + _NAME
            + r")\*?[ \t]*(?:\[[^\]\n]{0,200}\])?[ \t]*(?:\{\.[^}\n]{0,100}\.\})?[ \t]*=[ \t]*"
            r"(?:(?:ref|ptr)[ \t]+)?(?:object|enum|tuple|concept|distinct)\b",
            re.M,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        "safety": re.compile(
            r"\b(?:try|except|finally|isSome|isNone|isNil|doAssert|assert|require)\b|\bOption\[|\bresult\.isOk\b"
        ),
        "safety_bypasses": re.compile(
            r"\b(?:cast\[|unsafeAddr|unsafeGet|unsafeNew|unsafeRef)|\{\.(?:push[ \t]+)?"
            r"(?:checks|boundChecks|overflowChecks|rangeChecks|nilChecks|assertions|stackTrace|warning\[[^\]\n]{0,60}\]"
            r"|hint\[[^\]\n]{0,60}\])[ \t]*:[ \t]*off\b|\{\.emit\b"
        ),
        "high_risk_execution": re.compile(
            r"\b(?:execCmd|execCmdEx|execProcess|execProcesses|execShellCmd|startProcess|staticExec|gorgeEx?|loadLib|dlopen)\b"
        ),
        "io": re.compile(
            r"\b(?:readFile|writeFile|readLine|readAll|writeLine|newFileStream|openFileStream|readBuffer|writeBuffer"
            r"|copyFile|moveFile|removeFile|createDir|walkDir|walkFiles|newSocket|newAsyncSocket|openAsync|stdin|stdout"
            r"|stderr)\b"
        ),
        "api": re.compile(
            r"\b(?:newHttpClient|newAsyncHttpClient|newAsyncHttpServer|AsyncHttpServer|HttpClient|AsyncHttpClient"
            r"|Jester|Prologue)\b|^[ \t]*(?:get|post|put|delete|patch)[ \t]+\"/",
            re.M,
        ),
        "state_mutation": re.compile(
            r"[+\-*/&]=(?!=)|\b(?:inc|dec|incl|excl)\b|\.(?:add|delete|insert|setLen|clear|reset|del|pop)\("
        ),
        "dead_code": re.compile(
            r"^[ \t]*#[ \t]*(?:proc|func|method|template|macro|let|var|const|echo|import|when|if|for|while)\b", re.M
        ),
        # doc: `##` doc comments and `##[` block doc comments (not a `###` banner).
        "doc": re.compile(r"(?<!#)##(?!#)"),
        "test": re.compile(
            r"\bimport[ \t]+(?:std/)?unittest\b|^[ \t]*(?:suite|test)[ \t]+\"|\bdoAssert\b|^[ \t]*(?:check|expect)\b|\btestament\b",
            re.M,
        ),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        "concurrency": re.compile(
            r"\b(?:spawn|createThread|joinThread|initLock|withLock|asyncCheck|waitFor|await|async|Atomic|Channel|FlowVar"
            r"|AsyncEvent|newFuture|Future)\b"
        ),
        "ui_framework": re.compile(r"\b(?:nigui|owlkettle|wNim|nimx|illwill|karax|gintro|sdl2|raylib|nimgl|imgui)\b"),
        "closures": re.compile(r"\b(?:proc|func)[ \t]*\(|[ \t]=>[ \t]|\bdo[ \t]*(?:\(|:)"),
        "globals": re.compile(r"^var\b|\{\.global\.\}|\bgetEnv\b", re.M),
        "decorators": re.compile(r"\{\.[ \t]*" + _NAME),
        # generics: a routine or type declared with a `[T, ...]` parameter list.
        "generics": re.compile(
            r"\b" + _ROUTINE + r"[ \t]+[^\s(\[=]{1,60}\[[^\]\n]{1,100}\]"
            r"|^[ \t]*(?:type[ \t]+)?[A-Z]\w*\*?\[[^\]\n]{1,100}\][ \t]*=[ \t]*(?:(?:ref|ptr)[ \t]+)?"
            r"(?:object|tuple|enum|distinct)\b",
            re.M,
        ),
        "comprehensions": re.compile(
            r"\b(?:mapIt|filterIt|anyIt|allIt|foldl|foldr|collect|toSeq|applyIt|keepItIf|zip|apply)\b"
        ),
        "scientific": re.compile(
            r"\b(?:arraymancer|numericalnim|nimpy|linalg|Tensor|sqrt|ln|arctan2?|arcsin|arccos|sinh|cosh|tanh|fmod)\b"
            r"|\bimport[ \t]+(?:std/)?math\b"
        ),
        "reflection_metaprogramming": re.compile(
            r"\b(?:getAst|newNimNode|newIdentNode|parseExpr|parseStmt|getTypeImpl|getTypeInst|astToStr|bindSym|genSym"
            r"|NimNode|typedesc|compiles|declared|hasCustomPragma)\b|\bnnk[A-Z]\w*|\bquote[ \t]+do\b"
        ),
        "import": re.compile(r"^[ \t]*(?:import|from|include)[ \t]+[./A-Za-z_]", re.M),
        # Group 1 is the first module of an `import a, b`, the module of a `from m import x`, or an `include`d path
        # (`std/os`, `../util/strs`). A `std/[os, strutils]` bracket group reads as its base (`std`).
        "_dependency_capture": re.compile(
            r"^[ \t]*(?:import|from|include)[ \t]+((?:\.{1,2}/)*["
            + ID_START
            + r"]["
            + ID_CONTINUE
            + r"]*(?:/["
            + ID_START
            + r"]["
            + ID_CONTINUE
            + r"]*)*)",
            re.M,
        ),
        "ownership": re.compile(
            r"#[ \t]*(?:@author|Authors?|Created[ \t]+by|Maintainers?|Owners?)[ \t]*:?[ \t]*(\S[^\n]*?)[ \t]*$",
            re.I | re.M,
        ),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        "planned_debt": GLOBAL_PLANNED_DEBT,
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        "spec_exposure": re.compile(r"\[(?:\s*SPEC\s*-\s*\d{1,10}|spec|audit)[^\]]{0,300}\]", re.I),
        "events": re.compile(
            r"\b(?:AsyncEvent|newAsyncEvent|addTimer|addEvent|addSignal|addProcess|setControlCHook|onSignal)\b"
        ),
        "dependency_injection": re.compile(r"\bconcept\b"),
        "macros": re.compile(r"^[ \t]*(?:template|macro)\b|\bstatic:|\bquote[ \t]+do\b", re.M),
        "pointers": re.compile(r"\b(?:ptr|addr|unsafeAddr|pointer|cstring|ref)\b"),
        "memory_alloc": re.compile(
            r"\b(?:alloc|alloc0|allocShared|allocShared0|createShared|realloc|reallocShared|newSeq|newSeqOfCap|newString"
            r"|newStringOfCap|newSeqUninitialized|GC_fullCollect|GC_disable|GC_enable|GC_ref|GC_unref)\b"
        ),
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        "telemetry": re.compile(
            r"\b(?:newConsoleLogger|newFileLogger|newRollingFileLogger|logScope|chronicles)\b"
            r"|\b(?:info|debug|notice|warn|fatal)[ \t]*\("
        ),
        "debug_prints": re.compile(r"\b(?:echo|debugEcho|writeStackTrace|dump)\b"),
        "explicit_casts": re.compile(
            r"\b(?:int|int8|int16|int32|int64|uint|uint8|uint16|uint32|uint64|float|float32|float64|char|byte|cstring"
            r"|string|bool)\(|\b(?:parseInt|parseFloat|parseBiggestInt|parseBiggestUInt|parseUInt|parseHexInt|toInt"
            r"|toFloat|toBiggestInt)\b|\bcast\["
        ),
        "panics_and_aborts": re.compile(r"\b(?:raise|quit|raiseAssert|sysFatal|panic|abort|unreachable)\b"),
        "thread_sleeps": re.compile(r"\b(?:sleep|sleepAsync|usleep|nanosleep)[ \t]*\(?[ \t]*[0-9]"),
        "bitwise_ops": re.compile(r"\b(?:shl|shr|ashr|xor|rotateLeftBits|rotateRightBits|countSetBits|popcount)\b"),
        "sync_locks": re.compile(
            r"\b(?:withLock|initLock|deinitLock|tryAcquire|initCond|deinitCond|AtomicFlag|Lock|Cond|MultiLock|RwLock)\b"
            r"|\.(?:acquire|release|wait|signal|broadcast)\("
        ),
        "immutability_locks": re.compile(r"\b(?:let|const|func)\b|\{\.noSideEffect\.\}"),
        "cleanup": re.compile(
            r"\b(?:close|closeFile|closeSocket|defer|dealloc|deallocShared|deinitLock|deinitCond|finally|destroy)\b"
            r"|=destroy"
        ),
        # encapsulation: a `distinct` type, or a routine defined without the `*` export mark (private to its module).
        "encapsulation": re.compile(
            r"\bdistinct\b|^[ \t]*" + _ROUTINE + r"[ \t]+[^\s*(\[=:`]+[ \t]*[(\[]",
            re.M,
        ),
        "listeners": re.compile(
            r"\b(?:listen|accept|acceptAddr|bindAddr|bindUnix|serve|runForever)[ \t]*\(|\bnewAsyncHttpServer\b"
        ),
        "test_skip": re.compile(r"^[ \t]*skip\b|\{\.disabled\b", re.M),
        # --- PHASE 3: HYBRID DOMAIN SENSORS (Nim specifics) ---
        "auth_middleware": re.compile(
            r"\b(?:bcrypt|argon2|jwt|nimcrypto|libsodium|bearer|authenticate|authorize|hmac|pbkdf2|oauth2?|scram)\b",
            re.I,
        ),
        "serialization_parsing": re.compile(
            r"\b(?:parseJson|parseXml|parseCsv|parseCfg|parseToml|toJson|fromJson|jsony|msgpack4nim|protobuf|flatty"
            r"|packedjson|marshal|loadToml|loadYaml|newJObject|JsonNode)\b"
        ),
        "regex_execution": re.compile(
            r"\b(?:nre|regex|pegs|re)\.[a-z]\w*|\bre\"|\bpeg\"|=~|\b(?:findAll|findAllBounds|replacef|matchLen)\b"
            r"|\bimport[ \t]+(?:std/)?(?:re|nre|pegs|regex)\b"
        ),
        "time_date_logic": re.compile(
            r"\b(?:getTime|epochTime|cpuTime|getMonoTime|initDuration|initDateTime|parseTime|toTime|fromUnix|toUnix"
            r"|fromUnixFloat|getLocalTime|getGMTime|DateTime|Duration|MonoTime|Timezone|inSeconds|inMilliseconds)\b"
            r"|\bnow\(\)|\bimport[ \t]+(?:std/)?times\b"
        ),
        "ipc_rpc_bridges": re.compile(
            r"\b(?:grpc|zmq|zeromq|nanomsg|nng|jsonrpc|nimqtt|dbus|socketpair|createPipe|newAsyncPipe|asyncPipe"
            r"|RpcClient|RpcServer)\b|\bnewRpc\w+"
        ),
        "system_config_mutation": re.compile(
            r"\b(?:putEnv|delEnv|setCurrentDir|setFilePermissions|setLastModificationTime|createSymlink|createHardlink"
            r"|removeDir|removeFile|moveFile|moveDir|createDir|setFileAttrs|chdir|chmod|chown|umask|setuid|setgid"
            r"|setrlimit|setLocale)\b"
        ),
    },
}
