"""Tree-sitter oracle specs for C#, Kotlin, Swift and Scala (keyword-family validity tool, #8863).

Usage:  import specs_A; specs_A.register()   # adds the four languages to family_oracle_ts.SPECS / get_oracle
The base TreeSitterOracle.count hardcodes `binary_expression` + `operator`, Java-style name lookup and Java/Rust decorator
and doc rules, so these languages use OracleA, which reads the same Spec plus the SpecA extension fields.

Callee lists are the oracle's own reading of the contracts in gitgalaxy/standards/signal_contracts.py.
Pattern syntax (see _match): "name" = bare call only; "A.b" = the exact dotted callee or a dotted suffix of it;
"A." = any call whose dotted path starts with A (at a segment boundary); "*.m" = method m on any receiver.
"""

from __future__ import annotations

import collections
import re
from dataclasses import dataclass, field

import family_oracle_ts as fots
from family_oracle_ts import Spec, TreeSitterOracle, _fs, _text


@dataclass(frozen=True)
class SpecA(Spec):
    lang: str = ""  # our key: csharp / kotlin / swift / scala
    # nodes carrying an operator token: (node types, field names the operator may sit in)
    binary_types: frozenset[str] = frozenset()
    op_fields: tuple[str, ...] = ("operator", "op")
    bit_ops: frozenset[str] = frozenset()  # operator-position bitwise tokens
    compound_bit_ops: frozenset[str] = frozenset()  # <<= >>= ^= &= |=
    branch_ops: frozenset[str] = frozenset()  # short-circuit / value-selection operators that open a choice
    unary_types: frozenset[str] = frozenset()  # prefix operator nodes, `~` is the complement
    doc_prefixes: tuple[str, ...] = ("/**",)
    attr_types: frozenset[str] = frozenset()  # node types that are one annotation / attribute each
    duration_units: frozenset[str] = frozenset()  # `5.seconds` style duration literals (Kotlin, Scala)
    bit_idents: frozenset[str] = frozenset()  # Kotlin infix functions that are bitwise
    bailout_idents: frozenset[str] = frozenset()  # bare identifiers that are an unreachable marker (Scala `???`)
    skip_in: dict = field(default_factory=dict)  # branch node type -> ancestor type that disqualifies it


# --------------------------------------------------------------------------------------------------------------------
# callee lists
# --------------------------------------------------------------------------------------------------------------------
_CS_CALLS = {
    # Console / Debug are the ad-hoc channels; Trace and ILogger are listeners/telemetry, so left out.
    "print": (
        "Console.WriteLine",  # stdout line
        "Console.Write",  # stdout
        "Console.Error.WriteLine",  # stderr line
        "Console.Error.Write",  # stderr
        "Console.Out.WriteLine",  # explicit stdout writer property of Console
        "Console.Out.Write",
        "Debug.WriteLine",  # System.Diagnostics.Debug: debug-only output
        "Debug.Write",
        "Debug.Print",
    ),
    "sleep": (
        "Thread.Sleep",  # System.Threading.Thread.Sleep
        "Task.Delay",  # System.Threading.Tasks.Task.Delay: timed async wait
    ),
    "regex": (
        "Regex.",  # static System.Text.RegularExpressions.Regex.IsMatch/Match/Replace/Split/Escape
        "Regex",  # `new Regex(...)` constructor
        "*.IsMatch",  # Regex instance method (name is Regex specific in the BCL)
        "*.EnumerateMatches",  # Regex instance method (.NET 7)
    ),
    "time": (
        "DateTime.",  # DateTime.Now/UtcNow/Parse/...
        "DateTime",  # new DateTime(...)
        "DateTimeOffset.",  # BCL calendar type
        "DateTimeOffset",
        "DateOnly.",  # BCL (.NET 6)
        "DateOnly",
        "TimeOnly.",
        "TimeOnly",
        "TimeSpan.",  # durations: FromSeconds, Parse, Zero ...
        "TimeSpan",  # new TimeSpan(...)
        "TimeZoneInfo.",  # timezone calls
        "Stopwatch.",  # System.Diagnostics clock reads
        "Stopwatch",
        "Environment.TickCount",  # clock read
        "Environment.TickCount64",
        "Calendar.",
    ),
    "io": (
        "File.",  # System.IO.File static API
        "Directory.",  # System.IO.Directory static API
        "FileStream",  # new FileStream
        "StreamReader",  # new StreamReader(path|stream)
        "StreamWriter",
        "BinaryReader",
        "BinaryWriter",
        "FileInfo",  # file metadata object: filesystem facing
        "DirectoryInfo",
        "HttpClient",  # new HttpClient
        "*.GetAsync",  # HttpClient verbs
        "*.PostAsync",
        "*.PutAsync",
        "*.DeleteAsync",
        "*.SendAsync",
        "*.GetStreamAsync",
        "*.GetStringAsync",
        "*.GetByteArrayAsync",
        "TcpClient",  # System.Net.Sockets
        "TcpListener",
        "UdpClient",
        "Socket",
        "WebRequest.Create",
        "Console.ReadLine",  # stdin
        "Console.Read",
        "Console.OpenStandardInput",
        "Console.OpenStandardOutput",
        "*.ReadAsync",  # Stream methods
        "*.WriteAsync",
        "*.CopyToAsync",
    ),
    "bailout": ("Environment.Exit", "Environment.FailFast"),  # process-exit calls; `throw` is a node type
}

_KT_CALLS = {
    "print": (
        "println",  # kotlin.io.println
        "print",  # kotlin.io.print
        "System.out.println",  # java console
        "System.out.print",
        "System.err.println",
        "System.err.print",
    ),
    "sleep": (
        "Thread.sleep",  # java.lang.Thread
        "*.sleep",  # TimeUnit.SECONDS.sleep(1) and friends
        "delay",  # kotlinx.coroutines.delay (not stdlib, but the ecosystem's sleep)
        "LockSupport.parkNanos",  # timed wait
        "LockSupport.parkUntil",
    ),
    "regex": (
        "Regex",  # kotlin.text.Regex constructor
        "Regex.",  # Regex.escape / fromLiteral
        "*.toRegex",  # String.toRegex()
        "*.matchEntire",  # Regex members
        "*.containsMatchIn",
        "Pattern.compile",  # java.util.regex
        "Pattern.matches",
        "Pattern.quote",
        "*.matcher",  # Pattern.matcher
    ),
    "time": (
        "System.currentTimeMillis",  # clock reads
        "System.nanoTime",
        "measureTimeMillis",  # kotlin.system
        "measureNanoTime",
        "measureTime",  # kotlin.time
        "Clock.",  # kotlin.time / java.time clocks
        "Instant.",
        "Duration.",
        "LocalDate.",
        "LocalDateTime.",
        "LocalTime.",
        "ZonedDateTime.",
        "OffsetDateTime.",
        "Period.",
        "ChronoUnit.",
        "DateTimeFormatter.",
        "*.toNanos",  # duration conversion on TimeUnit / Duration (a bare TimeUnit.SECONDS constant is not time logic)
        "*.toMillis",
        "*.toSeconds",
        "*.toMinutes",
        "TimeSource.",
        "Calendar.",
        "Date",  # java.util.Date()
        "SimpleDateFormat",
        "TimeZone.",
        "ZoneId.",
        "*.toDuration",  # kotlin.time.Duration conversion
    ),
    "io": (
        "File",  # java.io.File(...): the filesystem handle
        "*.readText",  # kotlin.io.File extensions
        "*.readBytes",
        "*.readLines",
        "*.writeText",
        "*.writeBytes",
        "*.appendText",
        "*.appendBytes",
        "*.useLines",
        "*.bufferedReader",
        "*.bufferedWriter",
        "*.inputStream",
        "*.outputStream",
        "*.listFiles",
        "*.openConnection",  # java.net.URL
        "*.openStream",
        "Files.",  # java.nio.file
        "FileInputStream",
        "FileOutputStream",
        "FileReader",
        "FileWriter",
        "RandomAccessFile",
        "Socket",
        "ServerSocket",
        "URL",
        "HttpURLConnection",
        "readLine",  # stdin
        "readln",
        "readlnOrNull",
    ),
    "bailout": (
        "TODO",  # kotlin.TODO(): throws NotImplementedError, an unreachable marker
        "error",  # kotlin.error(): throws IllegalStateException
        "exitProcess",  # kotlin.system.exitProcess
        "System.exit",
        "Runtime.getRuntime().exit",
        "Runtime.getRuntime().halt",
    ),
}

_SW_CALLS = {
    "print": (
        "print",  # Swift.print
        "debugPrint",  # Swift.debugPrint
        "dump",  # Swift.dump
    ),
    "sleep": (
        "sleep",  # Glibc/Darwin
        "usleep",
        "nanosleep",
        "*.sleep",  # Thread.sleep, Task.sleep, ContinuousClock.sleep
        "*.asyncAfter",  # DispatchQueue.asyncAfter: timed deferral
        "Timer.scheduledTimer",  # Foundation timeout-driven deferral
        "*.usleep",
    ),
    "regex": (
        "NSRegularExpression",  # Foundation
        "Regex",  # Swift 5.7 Regex(...)
        "*.firstMatch",  # NSRegularExpression.firstMatch(in:...)
        "*.numberOfMatches",
        "*.stringByReplacingMatches",
        "*.wholeMatch",  # Swift Regex methods
        "*.prefixMatch",
    ),
    "time": (
        "Date",  # Foundation Date(); Date.init
        "Date.",
        "DispatchTime.",  # clock reads
        "DispatchWallTime.",
        "DispatchTimeInterval.",
        "ContinuousClock",  # Swift 5.7 clocks
        "SuspendingClock",
        "Duration.",
        "Calendar.",
        "Calendar",
        "DateComponents",
        "DateFormatter",
        "ISO8601DateFormatter",
        "DateInterval",
        "TimeZone.",
        "TimeZone",
        "CFAbsoluteTimeGetCurrent",
        "time",  # Glibc time()
        "clock_gettime",
        "gettimeofday",
        "mach_absolute_time",
        "*.timeIntervalSinceNow",  # Date arithmetic
        "*.timeIntervalSince1970",
        "*.timeIntervalSince",
        "*.addingTimeInterval",
    ),
    "io": (
        "FileManager.",  # Foundation: FileManager.default.*
        "FileHandle",
        "FileHandle.",
        "URLSession",
        "URLSession.",
        "InputStream",
        "OutputStream",
        "readLine",  # stdin
        "fopen",  # Glibc stdio
        "fread",
        "fwrite",
        "fclose",
        "fgets",
        "*.contentsOfDirectory",
        "*.createFile",
        "*.dataTask",
        "*.downloadTask",
        "*.uploadTask",
    ),
    "bailout": (
        "fatalError",  # Swift.fatalError
        "preconditionFailure",  # Swift.preconditionFailure
        "exit",  # Glibc exit
        "abort",
        "_exit",
    ),
}

_SC_CALLS = {
    "print": (
        "println",  # Predef.println
        "print",
        "printf",
        "Console.println",  # scala.Console
        "Console.print",
        "Console.printf",
        "Console.err.println",
        "Console.err.print",
        "System.out.println",
        "System.out.print",
        "System.err.println",
        "System.err.print",
    ),
    "sleep": (
        "Thread.sleep",  # java.lang.Thread
        "*.sleep",  # TimeUnit.X.sleep, IO.sleep
        "Await.result",  # scala.concurrent: blocks with a timeout
        "Await.ready",
        "LockSupport.parkNanos",
    ),
    "regex": (
        "Regex",  # scala.util.matching.Regex
        "*.findFirstIn",  # Regex methods
        "*.findAllIn",
        "*.findFirstMatchIn",
        "*.findAllMatchIn",
        "*.replaceAllIn",
        "*.replaceFirstIn",
        "Pattern.compile",
        "Pattern.matches",
        "Pattern.quote",
        "*.matcher",
    ),
    "time": (
        "System.currentTimeMillis",
        "System.nanoTime",
        "Instant.",
        "Duration",  # scala.concurrent.duration.Duration(...) and java.time.Duration
        "Duration.",
        "FiniteDuration",
        "Deadline",
        "Deadline.",
        "LocalDate.",
        "LocalDateTime.",
        "LocalTime.",
        "ZonedDateTime.",
        "OffsetDateTime.",
        "Period.",
        "Clock.",
        "ChronoUnit.",
        "DateTimeFormatter.",
        "*.toNanos",  # duration conversion on TimeUnit / Duration (a bare TimeUnit.SECONDS constant is not time logic)
        "*.toMillis",
        "*.toSeconds",
        "*.toMinutes",
        "Date",
        "Calendar.",
        "SimpleDateFormat",
        "ZoneId.",
        "TimeZone.",
    ),
    "io": (
        "Source.",  # scala.io.Source.fromFile / fromURL / stdin
        "StdIn.",  # scala.io.StdIn
        "Files.",
        "FileReader",
        "FileWriter",
        "FileInputStream",
        "FileOutputStream",
        "RandomAccessFile",
        "Socket",
        "ServerSocket",
        "URL",
        "HttpURLConnection",
        "*.listFiles",
        "*.openStream",
        "*.openConnection",
        "readLine",  # scala.io.StdIn.readLine imported
    ),
    "bailout": (
        "sys.exit",  # scala.sys.exit
        "System.exit",
        "sys.error",  # scala.sys.error: throws RuntimeException
        "Runtime.getRuntime.exit",
        "Runtime.getRuntime.halt",
        "Runtime.getRuntime().exit",
        "Runtime.getRuntime().halt",
    ),
}

_DUR = _fs(
    "nanoseconds",
    "microseconds",
    "milliseconds",
    "seconds",
    "minutes",
    "hours",
    "days",
    "nanos",
    "micros",
    "millis",
    "second",
    "minute",
    "hour",
    "day",
)

SPECS: dict[str, SpecA] = {
    "csharp": SpecA(
        "c_sharp",
        (".cs",),
        _fs(
            "method_declaration",
            "constructor_declaration",
            "local_function_statement",
            "operator_declaration",
            "destructor_declaration",
            "conversion_operator_declaration",
        ),
        _fs("lambda_expression", "anonymous_method_expression"),
        _fs(
            "if_statement",
            "for_statement",
            "foreach_statement",
            "while_statement",
            "do_statement",
            "switch_section",
            "switch_expression_arm",
            "conditional_expression",
        ),
        _fs("throw_statement", "throw_expression"),
        _fs("invocation_expression", "object_creation_expression", "member_access_expression"),
        _CS_CALLS,
        lang="csharp",
        binary_types=_fs("binary_expression", "assignment_expression"),
        bit_ops=_fs("<<", ">>", ">>>", "^", "&", "|"),
        compound_bit_ops=_fs("<<=", ">>=", ">>>=", "^=", "&=", "|="),
        branch_ops=_fs("&&", "||", "??", "??="),
        unary_types=_fs("prefix_unary_expression"),
        doc_prefixes=("///", "/**"),
        attr_types=_fs("attribute"),
    ),
    "kotlin": SpecA(
        "kotlin",
        (".kt", ".kts"),
        _fs("function_declaration", "secondary_constructor", "anonymous_initializer"),
        _fs("lambda_literal", "anonymous_function"),
        _fs(
            "if_expression",
            "for_statement",
            "while_statement",
            "do_while_statement",
            "when_entry",
            "elvis_expression",
            "conjunction_expression",
            "disjunction_expression",
        ),
        _fs(),
        _fs("call_expression", "navigation_expression"),
        _KT_CALLS,
        lang="kotlin",
        doc_prefixes=("/**",),
        attr_types=_fs("annotation"),
        duration_units=_DUR,
        bit_idents=_fs("shl", "shr", "ushr", "and", "or", "xor"),
    ),
    "swift": SpecA(
        "swift",
        (".swift",),
        _fs(
            "function_declaration",
            "init_declaration",
            "deinit_declaration",
            "protocol_function_declaration",
            "subscript_declaration",
        ),
        _fs("lambda_literal"),
        _fs(
            "if_statement",
            "guard_statement",
            "for_statement",
            "while_statement",
            "repeat_while_statement",
            "switch_entry",
            "ternary_expression",
            "nil_coalescing_expression",
            "conjunction_expression",
            "disjunction_expression",
        ),
        _fs(),
        _fs("call_expression", "navigation_expression"),
        _SW_CALLS,
        regex_node_types=_fs("regex_literal"),
        lang="swift",
        binary_types=_fs("bitwise_operation", "infix_expression"),
        bit_ops=_fs("<<", ">>", "^", "&", "|"),
        compound_bit_ops=_fs("<<=", ">>=", "^=", "&=", "|="),
        unary_types=_fs("prefix_expression"),
        doc_prefixes=("///", "/**"),
        attr_types=_fs("attribute"),
    ),
    "scala": SpecA(
        "scala",
        (".scala", ".sc"),
        _fs("function_definition", "function_declaration"),
        _fs("lambda_expression"),
        _fs(
            "if_expression",
            "for_expression",
            "while_expression",
            "do_while_expression",
            "case_clause",
        ),
        _fs("throw_expression"),
        _fs("call_expression", "instance_expression", "field_expression"),
        _SC_CALLS,
        lang="scala",
        binary_types=_fs("infix_expression"),
        bit_ops=_fs("<<", ">>", ">>>", "^", "&", "|"),
        compound_bit_ops=_fs("<<=", ">>=", ">>>=", "^=", "&=", "|="),
        branch_ops=_fs("&&", "||"),
        unary_types=_fs("prefix_expression"),
        attr_types=_fs("annotation"),
        duration_units=_DUR,
        bailout_idents=_fs("???"),
        skip_in={"case_clause": "catch_clause"},  # a catch handler is not a decision (branch contract, corollary 1)
    ),
}

# ----------------------------------------------------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------------------------------------------------
_GENERIC = re.compile(r"<[^<>]*>")


def _clean(s: str) -> str:
    s = "".join(s.split())
    while True:
        t = _GENERIC.sub("", s)
        if t == s:
            break
        s = t
    return s.replace("?.", ".").replace("!!.", ".").replace("!.", ".").rstrip("!?")


def _match(full: str, patterns: tuple[str, ...]) -> str | None:
    """See module docstring for the pattern forms."""
    for p in patterns:
        if p.startswith("*."):
            if full.endswith(p[1:]):
                return p
        elif p.endswith("."):
            if full.startswith(p) or ("." + p) in full:
                return p
        elif "." in p:
            if full == p or full.endswith("." + p):
                return p
        elif full == p:
            return p
    return None


def _kids(node, typ):
    return [c for c in node.children if c.type == typ]


def _op(spec: SpecA, node) -> str:
    for f in spec.op_fields:
        o = node.child_by_field_name(f)
        if o is not None:
            return _text(o)
    return ""


class OracleA(TreeSitterOracle):
    def __init__(self, spec: SpecA) -> None:
        super().__init__(spec)
        self.spec: SpecA = spec

    # ---- names ----------------------------------------------------------------------------------------------
    def _name_node(self, node):
        if self.spec.lang == "kotlin":
            return next((c for c in node.children if c.type == "simple_identifier"), None)
        return node.child_by_field_name("name")

    def _names(self, node) -> list[str]:
        """The names a scan may give the function: its identifier, plus the scan's own spellings (Swift `init?`, Kotlin backticked test names read as `fun`)."""
        t = node.type
        if t == "anonymous_initializer":
            return ["init"]
        if t == "subscript_declaration":
            return ["subscript"]
        if t == "secondary_constructor":
            return ["constructor"]
        nm = self._name_node(node)
        name = _text(nm)
        if not name:
            return []
        out = [name]
        if t == "init_declaration" and any(c.type == "?" for c in node.children):
            out.append(name + "?")
        if self.spec.lang == "kotlin" and name.startswith("`"):
            out.append("fun")
        return out

    # ---- index ----------------------------------------------------------------------------------------------
    def index(self, text: str) -> dict:
        """{(name, line): Fn}. A function is reachable by its first line, its name line, and every annotation / doc-comment
        line directly above it (a scan may key a decorated or documented function by its first such line)."""
        if self._parser is None:
            self._parser = fots.get_parser(self.spec.ts_name)
        root = self._parser.parse(text.encode("utf-8", "surrogateescape")).root_node
        lines = text.split("\n")
        index: dict = {}
        stack = [root]
        while stack:
            node = stack.pop()
            if node.type in self.spec.func_types:
                row = node.start_point[0]
                fn = Fn(node, self._doc_above(lines, row))
                nm = self._name_node(node)
                for name in self._names(node):
                    index.setdefault((name, row + 1), fn)
                    if nm is not None:
                        index.setdefault((name, nm.start_point[0] + 1), fn)
                    for c in node.children:
                        if c.type in ("modifiers", "attribute_list", "annotation", "attribute"):
                            index.setdefault((name, c.start_point[0] + 1), fn)
                    r = row - 1
                    while r >= 0 and _ABOVE.match(lines[r]):  # comment / annotation lines directly above
                        index.setdefault((name, r + 1), fn)
                        r -= 1
            stack.extend(node.children)
        return index

    def _doc_above(self, lines: list[str], row: int) -> bool:
        """Structured documentation directly above the function: `///` lines (C#, Swift) or a `/** ... */` block; plain comments do not count."""
        r = row - 1
        if r < 0:
            return False
        ln = lines[r].strip()
        if self.spec.lang in ("csharp", "swift") and ln.startswith("///"):
            return True
        if ln.endswith("*/"):
            while r >= 0 and "/*" not in lines[r]:
                r -= 1
            return r >= 0 and lines[r].lstrip().startswith("/**")
        return False

    # ---- per-language pieces --------------------------------------------------------------------------------
    def _params(self, fn) -> int:
        lang = self.spec.lang
        if lang == "swift":
            return len(_kids(fn, "parameter"))
        if lang == "scala":
            return sum(len(_kids(p, "parameter")) for p in fn.children_by_field_name("parameters"))
        if lang == "kotlin":
            fvp = next((c for c in fn.children if c.type == "function_value_parameters"), None)
            return len(_kids(fvp, "parameter")) if fvp is not None else 0
        if lang == "csharp":
            pl = fn.child_by_field_name("parameters")
            if pl is None:
                return 0
            n = len(_kids(pl, "parameter"))
            # grammar quirk: `params T[] x` parses as loose type/name children of the list rather than a `parameter`
            n += sum(
                1 for c in pl.children if c.type == "identifier" and pl.field_name_for_child(_idx(pl, c)) == "name"
            )
            return n
        return 0

    def _decorators(self, fn) -> list[str]:
        out: list[str] = []
        t = self.spec.attr_types
        for c in fn.children:
            if c.type in ("attribute_list", "modifiers"):
                out.extend(_text(a).split("(")[0] for a in c.children if a.type in t)
            elif c.type in t:
                out.append(_text(c).split("(")[0])
        return out

    def _documented(self, fn) -> bool:
        prev = fn.prev_sibling
        if prev is None or "comment" not in prev.type or prev.end_point[0] < fn.start_point[0] - 1:
            return False
        return _text(prev).lstrip().startswith(self.spec.doc_prefixes)

    def _callee(self, node) -> str:
        lang, t = self.spec.lang, node.type
        if lang == "csharp":
            if t == "invocation_expression":
                return _clean(_text(node.child_by_field_name("function")))
            if t == "member_access_expression":
                return _clean(_text(node))
            return _clean(_text(node.child_by_field_name("type")))
        if lang == "scala":
            if t == "call_expression":
                return _clean(_text(node.child_by_field_name("function")))
            if t == "field_expression":
                return _clean(_text(node))
            return _clean(_text(next((c for c in node.children if c.is_named), None)))  # instance_expression
        if t == "navigation_expression":
            return _clean(_text(node))
        first = node.children[0] if node.children else None  # kotlin / swift call_expression
        return _clean(_text(first))

    def _operator(self, node, add) -> None:
        spec, t = self.spec, node.type
        lang = spec.lang
        if t in spec.binary_types:
            op = _op(spec, node)
            if lang == "swift" and t == "infix_expression":
                if op in spec.compound_bit_ops:
                    add("bitwise", op)
                return
            if op in spec.branch_ops:
                add("branch", op)
            elif op in spec.bit_ops or op in spec.compound_bit_ops:
                add("bitwise", op)
        elif t in spec.unary_types:
            first = node.children[0] if node.children else None
            if (first is not None and first.type == "~") or (
                lang == "swift" and _text(node.child_by_field_name("operation")) == "~"
            ):
                add("bitwise", "~")
        elif lang == "kotlin" and t == "infix_expression" and node.named_child_count == 3:
            mid = node.named_children[1]
            if mid.type == "simple_identifier" and _text(mid) in spec.bit_idents:
                add("bitwise", _text(mid))

    def count(self, fn):
        doc = fn.doc if isinstance(fn, Fn) else self._documented(fn)
        fn = fn.node if isinstance(fn, Fn) else fn
        spec = self.spec
        lang = spec.lang
        n: collections.Counter[str] = collections.Counter()
        tokens: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)

        def add(key: str, tok: str | None = None) -> None:
            n[key] += 1
            if tok:
                tokens[key][tok] += 1

        row0, col0 = fn.start_point
        stack = list(fn.children)
        while stack:
            node = stack.pop()
            if lang == "scala" and node.is_named and node.start_point[0] > row0 and node.start_point[1] <= col0:
                continue  # scala-3 grammar quirk: an indented_block swallows the following sibling definitions; they are not this body
            stack.extend(node.children)
            if not node.is_named:
                continue
            t = node.type
            if (
                lang == "scala"
                and t == "wildcard"
                and node.parent is not None
                and node.parent.type in _SC_PLACEHOLDER_PARENTS
            ):
                add("closures", "placeholder")  # `_ + 1`, `_.name`, `f(_, 2)`: an anonymous function without `=>`
            if t in spec.branch_types:
                bad = spec.skip_in.get(t)
                if not (bad and _under(node, bad)):
                    add("branch", t)
            self._operator(node, add)
            if t in spec.closure_types:
                add("closures", t)
            elif (
                lang == "scala"
                and t == "case_block"
                and node.parent is not None
                and node.parent.type not in ("match_expression", "catch_clause")
            ):
                add("closures", "case-block")  # `{ case ... }` is a pattern-matching function literal
            if t in spec.throw_types:
                add("bailout", "throw")
            if (
                lang == "swift"
                and t == "control_transfer_statement"
                and any(c.type == "throw_keyword" for c in node.children)
            ):
                add("bailout", "throw")
            if lang == "kotlin" and t == "jump_expression" and any(c.type == "throw" for c in node.children):
                add("bailout", "throw")
            if t in spec.regex_node_types:
                add("regex", "regex-literal")
            if lang == "scala" and t == "identifier" and _text(node) in spec.bailout_idents:
                add("bailout", "???")
            if lang == "scala" and t == "operator_identifier" and _text(node) in spec.bailout_idents:
                add("bailout", "???")
            if t in spec.call_types and not _is_callee(node):
                full = self._callee(node)
                for key, pats in spec.calls.items():
                    hit = _match(full, pats)
                    if hit:
                        add(key, hit)
                self._special_call(node, full, add)
            self._special_node(node, add)
        n["args"] = self._params(fn)
        deco = self._decorators(fn)
        if deco:
            n["decorators"] = len(deco)
            for d in deco:
                tokens["decorators"][d] += 1
        n["doc"] = 1 if doc else 0
        return n, tokens

    def _special_call(self, node, full: str, add) -> None:
        lang = self.spec.lang
        if lang == "kotlin" and full.endswith(".inv"):
            add("bitwise", "inv")
        if lang == "swift" and full in ("Data", "String"):
            labels = [_text(x) for x in node.children[1:] for x in _walk_types(x, "value_argument_label")]
            if any(lb in ("contentsOf", "contentsOfFile") for lb in labels):
                add("io", "contentsOf")

    def _special_node(self, node, add) -> None:
        lang, t = self.spec.lang, node.type
        if lang == "kotlin" and t == "navigation_expression" and node.child_count >= 2:
            tgt, suf = node.children[0], node.children[-1]
            if (
                tgt.type in ("integer_literal", "real_literal")
                and suf.type == "navigation_suffix"
                and _text(suf).lstrip(".") in self.spec.duration_units
            ):
                add("time", "duration-literal")
        if lang == "scala" and t == "field_expression":
            val, fld = node.child_by_field_name("value"), node.child_by_field_name("field")
            if val is not None and fld is not None:
                if val.type in ("integer_literal", "floating_point_literal") and _text(fld) in self.spec.duration_units:
                    add("time", "duration-literal")
                if _text(fld) == "r" and val.type in ("string", "interpolated_string_expression"):
                    add("regex", ".r")


_ABOVE = re.compile(r"^\s*(//|/\*|\*|@|\[)")


class Fn:
    """What index() returns: the function node plus facts that need the source text."""

    def __init__(self, node, doc: bool) -> None:
        self.node = node
        self.doc = doc


_SC_PLACEHOLDER_PARENTS = frozenset(
    {"field_expression", "infix_expression", "arguments", "prefix_expression", "postfix_expression"}
)


def _is_callee(node) -> bool:
    """A member / navigation node that is the function part of a call: the call node is tested instead, so a call is counted once."""
    p = node.parent
    if p is None or node.type not in ("member_access_expression", "field_expression", "navigation_expression"):
        return False
    # callee of a call, or the receiver of a longer chain: only the outermost chain is tested
    return bool(
        p.children
        and p.children[0].id == node.id
        and (p.type in ("invocation_expression", "call_expression") or p.type == node.type)
    )


def _idx(parent, child) -> int:
    for i in range(parent.child_count):
        if parent.children[i].id == child.id:
            return i
    return -1


def _under(node, typ: str) -> bool:
    """True when the node's block-level parent (case_clause -> case_block) is `typ`: a catch arm, not a case nested somewhere inside a handler."""
    p = node.parent
    return p is not None and p.parent is not None and p.parent.type == typ


def _walk_types(node, typ):
    st = [node]
    while st:
        x = st.pop()
        if x.type == typ:
            yield x
        st.extend(x.children)


def register() -> None:
    """Add the four languages to family_oracle_ts (idempotent)."""
    for lang, spec in SPECS.items():
        fots.SPECS[lang] = spec
        fots._ORACLES[lang] = OracleA(spec)
