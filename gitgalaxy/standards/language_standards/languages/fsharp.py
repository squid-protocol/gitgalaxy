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
from gitgalaxy.standards.language_standards.identifiers import CAPITAL, ID_CONTINUE, ID_START

from .._shared_patterns import CALLS_OUT_C_STYLE, GLOBAL_FRAGILE_DEBT, GLOBAL_PLANNED_DEBT, commented_keyword_statement

_NAME = r"([" + ID_START + r"][" + ID_CONTINUE + r"']*)"
_MODS = (
    r"(?:(?:rec|inline|private|internal|public|mutable)[ \t]+)*(?!(?:rec|inline|private|internal|public|mutable)[ \t])"
)
_GENERIC = r"(?:<[^>\n]{0,200}>)?"
# What opens a named, parameterised unit: `let` / `and` (module functions and local helpers; a capitalised
# name there is a type's `and Foo(x) =`, never a function) or a `member` / `override` / `default`
# (an optional self identifier, `this.`, steps over; `member val` is a field, not a method).
_UNIT_PREFIX = (
    r"(?:(?:let|and)[ \t]+"
    + _MODS
    + r"(?!["
    + CAPITAL
    + r"])"
    + r"|(?:static[ \t]+)?(?:member|override|default)[ \t]+(?!val\b)"
    + _MODS
    + r"(?:["
    + ID_START
    + r"]["
    + ID_CONTINUE
    + r"']*\.)?)"
)
_DOTTED = r"[" + ID_START + r"][" + ID_CONTINUE + r"'.]*"
_TRIVIA = r"(?:[ \t]|//[^\n]*)*"

DEFINITION: dict[str, Any] = {
    "_meta": {
        "target_version": "F# 9 (nullness, computation expressions, units of measure, active patterns)",
        "last_updated": "2026-10-19",
        "blueprint_version": "v5.0",
        "status": "production",
    },
    # Source, signature files and F# Interactive scripts. ".fs" is also a GLSL fragment shader and a Forth
    # file, so it is listed in extensions_needing_discriminator below and in COLLISION_FREQUENCIES
    # (_lens_config.py): F# owns it only on proof.
    "extensions": [".fs", ".fsi", ".fsx"],
    # Claims ".fs" only on content proof (internal_discriminator, tried at Tier 2). It is neither a lexical nor a
    # gravity candidate for it, so a GLSL or Forth ".fs" stays unmapped exactly as before (#5622's precedent).
    "extensions_needing_discriminator": [".fs"],
    "exact_matches": [],
    # ".fsproj" is the project manifest that anchors an F# ecosystem (csharp's ".csproj" precedent).
    "discriminators": [".fsi", ".fsx", ".fsproj"],
    # COLLISION RESOLUTION ONLY, for ".fs": declarations GLSL and Forth never write. A column-0 `module X` /
    # `namespace X`, an `open A.B`, a `let name args =` binding, `match ... with`, a `type T =` header, an
    # attribute line, or the pipe / reverse-pipe operators. `: name ... ;` (Forth) and `void main()` (GLSL)
    # match none of them.
    "internal_discriminator": re.compile(
        r"^(?:module|namespace)[ \t]+(?:rec[ \t]+|private[ \t]+|internal[ \t]+|public[ \t]+)*[A-Za-z_][\w.]*[ \t]*(?:=[ \t]*)?\r?$"
        r"|^[ \t]*open[ \t]+(?:type[ \t]+)?[A-Z][\w.]*[ \t]*\r?$"
        r"|^[ \t]*let[ \t]+(?:(?:rec|inline|private|internal|public|mutable)[ \t]+)*[a-z_][\w']*[^\n=;]{0,200}="
        r"|^[ \t]*match[ \t][^\n]{1,200}[ \t]with[ \t]*\r?$"
        r"|^[ \t]*type[ \t]+(?:private[ \t]+|internal[ \t]+)?[A-Za-z_][\w']*(?:<[^>\n]{0,100}>)?[^\n=]{0,100}=[ \t]*\r?$"
        r"|^[ \t]*\[<[A-Z]\w*[^\n]{0,100}>\]"
        r"|[ \t]\|>[ \t]|[ \t]<\|[ \t]",
        re.M,
    ),
    "shebangs": [],
    # F# uses `//` line comments and nested `(* *)` blocks. No family has the `(*` `*)` pair yet, so `//` is
    # stripped and a `(* *)` block stays in the code stream (docs/language_status/fsharp.md, limitations).
    "lexical_family": "recursive_block",
    "rules": {
        "calls_out": CALLS_OUT_C_STYLE,
        # Keywords that take a parenthesised operand: never calls.
        "_calls_out_ignore": frozenset(
            {
                "if",
                "elif",
                "then",
                "else",
                "match",
                "with",
                "when",
                "while",
                "for",
                "to",
                "downto",
                "do",
                "in",
                "of",
                "let",
                "use",
                "fun",
                "function",
                "type",
                "new",
                "member",
                "override",
                "default",
                "abstract",
                "static",
                "inherit",
                "yield",
                "return",
                "lazy",
                "assert",
                "upcast",
                "downcast",
                "and",
                "or",
                "not",
                "begin",
                "end",
                "try",
                "finally",
                "exception",
                "module",
                "namespace",
                "open",
                "val",
                "mutable",
            }
        ),
        # A keyword, `->` or `|` inside a string literal is not a decision.
        "_scope_filters": {"branch": "outside_literals"},
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # branch: if/elif, match, guards, loops, and match ARMS (a leading `|` whose line carries the arrow;
        # a union case `| A of int` has none, so a type declaration is not counted as a decision).
        "branch": re.compile(r"\b(?:if|elif|match|when|for|while)\b|^[ \t]*\|(?![|\]}])[^\n]*->", re.M),
        # args: group 1 is a parenthesised, comma-separated parameter list (`member x.Add(a, b)`,
        # `let f(a, b) =`), counted by commas; group 2 is a curried list (`let f a (b: int) =`,
        # `member _.Run x y =`), routed to the shared pattern-list counter (a parenthesised pattern is one).
        "args": re.compile(
            r"^[ \t]*"
            + _UNIT_PREFIX
            + _NAME
            + _GENERIC
            + r"\(((?:[^()\n]|\([^()\n]*\))*)\)"
            + r"|^[ \t]*"
            + _UNIT_PREFIX
            + _NAME
            + _GENERIC
            + r"[ \t]+((?:\([^()\n]+\)|[^\s=:|()]+)(?:[ \t]+(?:\([^()\n]+\)|[^\s=:|()]+))*)[ \t]*(?::[^=\n]*)?=(?!=)",
            re.M,
        ),
        "_args_bare_body_groups": {2},
        "_args_pattern_list_groups": {4},
        "structural_boundaries": re.compile(
            r"\b(?:module|namespace|type|let|in|and|do|begin|end|then|of|with|exception|inherit|interface|class|struct)\b"
        ),
        # func_start: a `let` / `let rec` / `let inline` / `and` binding, or a `member` / `override` / `default`,
        # that takes at least one parameter (a bare `let x = 1` and `member val` are values; a `let x : int = 3`
        # annotation and a property's `with get` are not parameter lists). Capitalised `let` / `and` names are a
        # type's primary constructor. Multi-line parameter lists and operator names (`let (+) a b`) are not seen.
        "func_start": re.compile(
            r"^[ \t]*" + _UNIT_PREFIX + _NAME + r"(?=" + _GENERIC + r"(?![ \t]+with\b)(?:\(|[ \t]+[^\s=:|]))",
            re.M,
        ),
        # class_start: `type` (record, union, class, interface, abbreviation), `module`, `namespace`,
        # `exception`, and the `and` of a mutually recursive type group.
        "class_start": re.compile(
            r"^[ \t]*(?:(?:type|module|namespace|exception)[ \t]+(?:rec[ \t]+|private[ \t]+|internal[ \t]+|public[ \t]+|inline[ \t]+)*"
            r"|and[ \t]+(?=[" + CAPITAL + r"]))" + r"(" + _DOTTED + r")",
            re.M,
        ),
        # --- PHASE 2: RISK & STRUCTURAL INTEGRITY ---
        # safety: try, the handled-absence arm (`None ->`) and the Option / Result / TryX combinators.
        "safety": re.compile(
            r"\b(?:try|TryParse|TryGetValue|tryParse|tryFind|tryHead|tryItem|tryPick|"
            r"Option\.(?:defaultValue|defaultWith|bind|map|orElse|ofObj)|Result\.(?:bind|map|mapError))\b"
            r"|\bNone[ \t]*->"
        ),
        # safety_bypasses: partial accessors, a defaulted null and warning suppression.
        "safety_bypasses": re.compile(
            r"\b(?:Option\.get|List\.(?:head|tail|last|item|exactlyOne)|Seq\.(?:head|last|item|exactlyOne)"
            r"|Array\.(?:head|last|exactlyOne)|Unchecked\.defaultof)\b|^[ \t]*#nowarn\b",
            re.M,
        ),
        # high_risk_execution: forceful aborts of the process.
        "high_risk_execution": re.compile(r"\b(?:exit|Environment\.Exit|failwith|failwithf)\b"),
        "io": re.compile(
            r"\b(?:File|Directory)\.[A-Z]\w*|\b(?:StreamReader|StreamWriter|FileStream|BinaryReader|BinaryWriter"
            r"|HttpClient|WebClient|TcpClient|TcpListener|Socket|SqlConnection|NpgsqlConnection|stdin|stdout|stderr)\b"
        ),
        # api: file-level `module` / `namespace` headers, and `val` declarations of a signature file.
        "api": re.compile(
            r"^(?:module|namespace)[ \t]+(?:rec[ \t]+)?"
            + _DOTTED
            + r"|^[ \t]*val[ \t]+(?:(?:inline|mutable|private|internal|public)[ \t]+)*"
            r"[" + ID_START + r"][" + ID_CONTINUE + r"']*[ \t]*:",
            re.M,
        ),
        # state_mutation: a statement that writes into existing state: `x <- v`, `this.X <- v`, `a.[i] <- v`,
        # a ref cell's `x := v`. A `let mutable` declaration is not a write.
        "state_mutation": re.compile(
            r"^[ \t]*["
            + ID_START
            + r"]["
            + ID_CONTINUE
            + r"'.]*(?:\.?\[[^\]\n]{1,100}\]["
            + ID_CONTINUE
            + r"'.]*)?[ \t]*(?:<-(?![-<])|:=(?!=))"
            r"|\b(?:incr|decr)\b",
            re.M,
        ),
        # #7207: a statement's shape (`(...)`, an assignment, `if .. then`, `match .. with`, `printfn "..."`, a trailing `=`
        # after `let`/`type`/`module Name`, a dotted or capitalised `open Ns`), not just the keyword; `///` is a doc line.
        "dead_code": re.compile(
            commented_keyword_statement(
                "let|type|module|open|member|printfn|match|if",
                block=False,
                extra=r"(?<=if)[^\n]{0,300}?[ \t]then[ \t]*(?m:$)"
                r"|(?<=match)[^\n]{0,300}?[ \t]with[ \t]*(?m:$)"
                r'|(?<=printfn)[ \t]+"'
                r"|(?<=let)[^\n]{0,300}?=[ \t]*(?m:$)"
                r"|(?:(?<=type)|(?<=module))[ \t]+[A-Z]\w*(?:<[^>\n]{0,100}>)?[ \t]*=?[ \t]*(?m:$)"
                r"|(?<=open)[ \t]+[A-Z]\w*(?:\.\w+)*[ \t]*(?m:$)",
            ),
            re.M,
        ),
        # doc: XML doc comments and the `(** *)` doc block.
        "doc": re.compile(r"^[ \t]*///|\(\*\*(?=[ \t\r\n])", re.M),
        "test": re.compile(
            r"\[<(?:Fact|Theory|Test|TestCase|TestFixture|Property)\b[^\]\n]*>\]"
            r"|\b(?:testCase|testList|testProperty|testAsync|Expect\.[a-z]\w*|Assert\.[A-Z]\w*|FsCheck)\b|\bCheck\.Quick"
        ),
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        "concurrency": re.compile(
            r"\b(?:async|task|backgroundTask)[ \t]*\{|\b(?:MailboxProcessor|Async\.[A-Z]\w*|Task\.[A-Z]\w*"
            r"|Parallel\.[A-Z]\w*|Thread|ThreadPool|Interlocked|SemaphoreSlim)\b"
        ),
        "ui_framework": re.compile(
            r"\b(?:Elmish|Feliz|Fabulous|Bolero|FuncUI|Avalonia|ReactDOM|System\.Windows\.Forms|Giraffe\.ViewEngine)\b"
        ),
        # closures: `fun x -> ...`, `function | ...` and the F# 8 `_.Prop` shorthand.
        "closures": re.compile(r"\bfun\b(?=[^\n]{0,200}->)|\bfunction\b|\(_\.[" + ID_START + r"]"),
        "globals": re.compile(
            r"^let[ \t]+(?:(?:private|internal)[ \t]+)?mutable\b"
            r"|\bEnvironment\.(?:GetEnvironmentVariables?|GetCommandLineArgs|CurrentDirectory)\b|\bfsi\.CommandLineArgs\b",
            re.M,
        ),
        "decorators": re.compile(r"\[<[A-Za-z_][^\]\n]{0,200}>\]"),
        # generics: type variables (`'T`, `^T`); a character literal `'a'` is excluded by the closing quote.
        "generics": re.compile(
            r"(?<!["
            + ID_CONTINUE
            + r"'])'[A-Za-z_]["
            + ID_CONTINUE
            + r"]*(?!["
            + ID_CONTINUE
            + r"'])|\^[A-Z]["
            + ID_CONTINUE
            + r"]*\b"
        ),
        "comprehensions": re.compile(
            r"\[\|?[ \t]*(?:for|yield)\b|\bseq[ \t]*\{|\b(?:List|Seq|Array)\.(?:map|collect|choose|filter)\b|\|>"
        ),
        "scientific": re.compile(
            r"\b(?:MathNet|Math\.[A-Z]\w*|Complex|Matrix|Vector|Numerics|sin|cos|tan|exp|sqrt|log|log10|sinh|cosh|tanh|atan2?|asin|acos)\b"
        ),
        "reflection_metaprogramming": re.compile(
            r"\b(?:typeof|typedefof|nameof|Reflection|GetType|Activator\.CreateInstance|FSharpType|FSharpValue|Quotations"
            r"|ReflectedDefinition|MakeGenericType|MakeGenericMethod)\b|<@@?|@@?>"
        ),
        "import": re.compile(r"^[ \t]*open[ \t]+(?:type[ \t]+)?" + _DOTTED, re.M),
        "_dependency_capture": re.compile(r"^[ \t]*open[ \t]+(?:type[ \t]+)?(" + _DOTTED + r")", re.M),
        "ownership": re.compile(
            r"^[ \t]*(?:///?|\(\*+)[ \t]*(?:Authors?|Created[ \t]+by|Maintainers?|Owners?|Developers?|Contact)[ \t]*:(?![:=])[ \t]*(\S[^\n]*?)[ \t]*(?:\*\))?[ \t]*$"
            r"|@author:?[ \t]+(\S[^\n]*?)[ \t]*(?:\*\))?[ \t]*$",
            re.I | re.M,
        ),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        "planned_debt": GLOBAL_PLANNED_DEBT,
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        "spec_exposure": re.compile(r"\[(?:spec-[0-9]+|audit|rfc)\]", re.I),
        "ssr_boundaries": re.compile(
            r"\b(?:Giraffe|Saturn|Suave|Falco|Bolero|HttpHandler|HttpContext|WebPart|WebHostBuilder|routef?)\b"
        ),
        "events": re.compile(
            r"\b(?:Event|IEvent|IObservable|Observable|AddHandler|RemoveHandler|CLIEvent|MailboxProcessor)\b"
        ),
        "dependency_injection": re.compile(
            r"\b(?:IServiceProvider|AddSingleton|AddScoped|AddTransient|GetRequiredService|GetService|ServiceCollection|IOptions|Autofac)\b"
        ),
        # macros: F# has no macros; the preprocessor and script directives are its compile-time surface.
        "macros": re.compile(r"^[ \t]*#(?:if|else|elif|endif|nowarn|warnon|light|r|load|I|time)\b", re.M),
        "pointers": re.compile(
            r"\b(?:nativeptr|NativePtr|nativeint|byref|inref|outref|voidptr|IntPtr|UIntPtr|Marshal|fixed|stackalloc)\b"
        ),
        "memory_alloc": re.compile(
            r"\b(?:stackalloc|Marshal\.(?:AllocHGlobal|FreeHGlobal|AllocCoTaskMem|FreeCoTaskMem)|NativeMemory\.[A-Z]\w*"
            r"|ArrayPool|Array\.zeroCreate|GC\.Collect)\b"
        ),
        # inline_asm: FSharp.Core's inline IL, `(# "ldlen" arr : int #)`.
        "inline_asm": re.compile(r"\(#[ \t]*\"[^\"\n]{0,200}\""),
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        "telemetry": re.compile(
            r"\b(?:ILogger|Serilog|ActivitySource|TelemetryClient|Log\.(?:Information|Warning|Error|Debug|Verbose|Fatal)"
            r"|logger\.Log\w*|LogInformation|LogWarning|LogError|LogDebug|LogCritical)\b"
        ),
        "debug_prints": re.compile(
            r"\b(?:printfn|printf|eprintfn|eprintf|dprintfn|Console\.Write(?:Line)?|Debug\.Write(?:Line)?|Trace\.Write\w*)\b"
        ),
        "explicit_casts": re.compile(
            r"\b(?:unbox|downcast|upcast|box)\b|:\?>|:>"
            r"|\b(?:int|int8|int16|int32|int64|uint8|uint16|uint32|uint64|float|float32|double|single|decimal|byte|sbyte|char|nativeint|unativeint|bigint)[ \t]*\("
        ),
        "panics_and_aborts": re.compile(
            r"\b(?:failwithf?|raise|reraise|invalidOp|invalidArg|nullArg|exit|Environment\.Exit)\b"
        ),
        "thread_sleeps": re.compile(r"\b(?:Thread\.Sleep|Async\.Sleep|Task\.Delay|Thread\.SpinWait)\b"),
        "bitwise_ops": re.compile(r"&&&|\|\|\||\^\^\^|~~~|<<<|>>>"),
        "sync_locks": re.compile(
            r"\b(?:Monitor\.(?:Enter|Exit|TryEnter)|Mutex|SemaphoreSlim|ReaderWriterLockSlim|Interlocked\.[A-Z]\w*|SpinLock)\b"
            r"|\block[ \t]*(?:\(|[" + ID_START + r"])"
        ),
        # immutability_locks: bindings are immutable by default (the ambient guarantee has no site); the explicit
        # forms are `[<Literal>]`, `[<IsReadOnly>]` and the read-only collection interfaces.
        "immutability_locks": re.compile(r"\[<(?:Literal|IsReadOnly)>\]|\bIReadOnly[A-Za-z]+\b"),
        "cleanup": re.compile(r"\b(?:use|using|finally|IDisposable)\b|\.(?:Dispose|Close)\b"),
        "encapsulation": re.compile(r"\b(?:private|internal)\b"),
        "listeners": re.compile(r"\b(?:AddHandler|RemoveHandler|Subscribe|SubscribeOn|ObserveOn|addEventListener)\b"),
        "test_skip": re.compile(r"\[<Ignore\b|\bSkip[ \t]*=|\b(?:ptestCase|ptestList|ptestProperty|ptestAsync)\b"),
        # --- PHASE 3: HYBRID DOMAIN SENSORS (F# specifics) ---
        "auth_middleware": re.compile(
            r"\b(?:requiresAuthentication|requiresRole|requiresRoleOf|mustBeAdmin|authorize|JwtBearer|UseAuthentication"
            r"|UseAuthorization|SignInAsync|SignOutAsync|ClaimsPrincipal|PasswordHasher|Rfc2898DeriveBytes|BCrypt)\b"
            r"|\[<Authorize\b"
        ),
        "serialization_parsing": re.compile(
            r"\b(?:JsonSerializer|JsonConvert|JsonProvider|CsvProvider|XmlProvider|XmlSerializer|BinaryFormatter"
            r"|Thoth\.Json|System\.Text\.Json|Newtonsoft\.Json|MessagePack|Decode\.fromString|JsonValue|XDocument)\b"
        ),
        "regex_execution": re.compile(r"\b(?:Regex|RegularExpressions|MatchCollection)\b"),
        "time_date_logic": re.compile(
            r"\b(?:DateTime|DateTimeOffset|TimeSpan|TimeZoneInfo|Stopwatch|DateOnly|TimeOnly|NodaTime)\b"
        ),
        "ipc_rpc_bridges": re.compile(
            r"\b(?:Process\.Start|ProcessStartInfo|NamedPipeServerStream|NamedPipeClientStream|WebSocket|ClientWebSocket"
            r"|DllImport|Grpc|SignalR|HubConnection|RabbitMQ|Kafka)\b"
        ),
        "system_config_mutation": re.compile(
            r"\b(?:Environment\.SetEnvironmentVariable|Directory\.SetCurrentDirectory|Registry\.SetValue|RegistryKey\.SetValue)\b"
        ),
    },
}
