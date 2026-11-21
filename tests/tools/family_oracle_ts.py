"""Tree-sitter oracles for the keyword-family validity tool (#8863): what a function does, read from a real parser, per language.

`family_oracle.py` scores a scan's family columns against an oracle. Python's is the `ast` module; the languages here use tree-sitter
(`tree_sitter_language_pack`, the `translator` extra). Each language is one `Spec`: which node types are functions, branches, closures and
throws, how to read a function's name and parameters, and which callee names mean print, sleep, regex, clock, file/network I/O or process exit.
Those callee lists are the oracle's own reading of what the family names promise, written here and kept apart from the rules in `standards/`
so the two can disagree. Every list is provisional until the family definitions (#8862) are settled.

Only constructs that mean the same thing in every language are scored: branches, parameters, closures, annotations/attributes/decorators, throws
and exits, bitwise operators in operator position, print, sleep, regex, clock, I/O, and a preceding doc comment. A language gains an oracle by
adding a Spec and running the scan of one real repository through `family_oracle.py`.
"""

from __future__ import annotations

import collections
from dataclasses import dataclass, field
from typing import Any, NamedTuple

_COMMON_FAMILIES = (
    (
        "struct_branch",
        "branch",
        "decision points: if/else arms, loops, case/default arms, conditional expressions, && and || (not catch handlers, goto, return or break: contract corollaries 1 and 3)",
        "branch",
    ),
    ("args", "args", "declared parameters", "args"),
    (
        "struct_closures",
        "closures",
        "anonymous callables: function literals, lambdas, arrow functions, closures",
        "closures",
    ),
    ("struct_decorators", "decorators", "annotations, attributes or decorators on the function", "decorators"),
    ("state_bailout_hits", "bailout", "throw / panic / unreachable marker / process exit", "panics_and_aborts"),
    (
        "bitwise_ops",
        "bitwise",
        "bitwise operators in operator position: << >> ^ & | ~ (and the compound assignments)",
        "bitwise_ops",
    ),
    ("state_print_hits", "print", "ad-hoc debug output to the console", "debug_prints"),
    ("state_halt_hits", "sleep", "sleeps and timed waits", "thread_sleeps"),
    ("arch_regex", "regex", "evaluates or builds a regular expression", "regex_execution"),
    (
        "arch_time",
        "time",
        "instantiates or computes with a clock or calendar value: now/time/date constructors, durations, formatting",
        "time_date_logic",
    ),
    ("arch_io", "io", "opens or reads/writes a file or a network connection", "io"),
    ("is_documented", "doc", "structured documentation directly above (/** */, ///, godoc)", "doc"),
)


class Family(NamedTuple):
    column: str
    oracle: str
    sentence: str
    rule: str


@dataclass(frozen=True)
class Spec:
    ts_name: str
    exts: tuple[str, ...]
    func_types: frozenset[str]
    closure_types: frozenset[str]
    branch_types: frozenset[str]
    throw_types: frozenset[str]
    call_types: frozenset[str]
    calls: dict[str, tuple[str, ...]] = field(default_factory=dict)  # oracle key -> callee patterns
    regex_node_types: frozenset[str] = frozenset()  # a regex literal is itself an execution site (JavaScript)
    skip_families: frozenset[str] = frozenset()  # columns the language has no oracle for


def _fs(*xs: str) -> frozenset[str]:
    return frozenset(xs)


_JS_CALLS = {
    "print": (
        "console.log",
        "console.info",
        "console.warn",
        "console.error",
        "console.debug",
        "console.table",
        "console.trace",
    ),
    "sleep": ("setTimeout", "setInterval", "setImmediate", "sleep", "delay"),
    "regex": ("RegExp", "test", "exec", "match", "matchAll"),
    "time": (
        "Date.",
        "Date",
        "performance.now",
        "process.hrtime",
        "moment",
        "dayjs",
        "Intl.DateTimeFormat",
        "console.time",
        "console.timeEnd",
    ),
    "io": (
        "fs.",
        "fetch",
        "XMLHttpRequest",
        "http.request",
        "https.request",
        "http.get",
        "https.get",
        "axios.",
        "readFile",
        "writeFile",
        "createReadStream",
        "createWriteStream",
    ),
    "bailout": ("process.exit", "process.abort"),
}

SPECS: dict[str, Spec] = {
    "go": Spec(
        "go",
        (".go",),
        _fs("function_declaration", "method_declaration"),
        _fs("func_literal"),
        _fs("if_statement", "for_statement", "expression_case", "type_case", "communication_case"),
        _fs(),
        _fs("call_expression"),
        {
            "print": ("fmt.Print", "fmt.Printf", "fmt.Println", "println", "print"),
            "sleep": ("time.Sleep", "time.After", "time.Tick", "time.NewTimer", "time.NewTicker"),
            "regex": ("regexp.",),
            "time": ("time.",),
            "io": (
                "os.Open",
                "os.Create",
                "os.ReadFile",
                "os.WriteFile",
                "os.OpenFile",
                "os.Mkdir",
                "os.MkdirAll",
                "os.Remove",
                "os.RemoveAll",
                "os.ReadDir",
                "os.Stat",
                "ioutil.",
                "bufio.",
                "net.Dial",
                "net.Listen",
                "http.Get",
                "http.Post",
                "filepath.Walk",
                "filepath.WalkDir",
            ),
            "bailout": ("panic", "os.Exit", "log.Fatal", "log.Fatalf", "log.Fatalln", "log.Panic", "log.Panicf"),
        },
    ),
    "rust": Spec(
        "rust",
        (".rs",),
        _fs("function_item"),
        _fs("closure_expression"),
        _fs("if_expression", "for_expression", "while_expression", "loop_expression", "match_arm"),
        _fs(),
        _fs("call_expression", "macro_invocation"),
        {
            "print": ("println!", "print!", "eprintln!", "eprint!", "dbg!"),
            "sleep": ("thread::sleep", "std::thread::sleep", "tokio::time::sleep", "time::sleep", "sleep"),
            "regex": ("Regex::new", "RegexSet::new", "RegexBuilder::new", "Regex::"),
            "time": (
                "Instant::",
                "SystemTime::",
                "Utc::",
                "Local::",
                "Duration::",
                "chrono::",
                "DateTime::",
                "NaiveDate::",
            ),
            "io": (
                "File::open",
                "File::create",
                "OpenOptions::new",
                "fs::read",
                "fs::write",
                "fs::read_to_string",
                "fs::create_dir",
                "fs::create_dir_all",
                "fs::remove_file",
                "fs::read_dir",
                "fs::copy",
                "TcpStream::connect",
                "TcpListener::bind",
                "io::stdin",
                "io::stdout",
                "stdin",
                "stdout",
            ),
            "bailout": (
                "panic!",
                "unreachable!",
                "todo!",
                "unimplemented!",
                "process::exit",
                "std::process::exit",
                "exit",
            ),
        },
    ),
    "javascript": Spec(
        "javascript",
        (".js", ".mjs", ".cjs", ".jsx"),
        _fs("function_declaration", "generator_function_declaration", "method_definition"),
        _fs("arrow_function", "function_expression", "generator_function"),
        _fs(
            "if_statement",
            "for_statement",
            "for_in_statement",
            "while_statement",
            "do_statement",
            "switch_case",
            "ternary_expression",
        ),
        _fs("throw_statement"),
        _fs("call_expression", "new_expression"),
        _JS_CALLS,
        regex_node_types=_fs("regex"),
    ),
    "typescript": Spec(
        "typescript",
        (".ts", ".mts", ".cts"),
        _fs("function_declaration", "generator_function_declaration", "method_definition"),
        _fs("arrow_function", "function_expression", "generator_function"),
        _fs(
            "if_statement",
            "for_statement",
            "for_in_statement",
            "while_statement",
            "do_statement",
            "switch_case",
            "ternary_expression",
        ),
        _fs("throw_statement"),
        _fs("call_expression", "new_expression"),
        _JS_CALLS,
        regex_node_types=_fs("regex"),
    ),
    "java": Spec(
        "java",
        (".java",),
        _fs("method_declaration", "constructor_declaration"),
        _fs("lambda_expression"),
        _fs(
            "if_statement",
            "for_statement",
            "enhanced_for_statement",
            "while_statement",
            "do_statement",
            "switch_block_statement_group",
            "switch_rule",
            "ternary_expression",
        ),
        _fs("throw_statement"),
        _fs("method_invocation", "object_creation_expression"),
        {
            "print": (
                "System.out.print",
                "System.out.println",
                "System.out.printf",
                "System.err.print",
                "System.err.println",
                "System.err.printf",
            ),
            "sleep": (
                "Thread.sleep",
                "TimeUnit.SECONDS.sleep",
                "TimeUnit.MILLISECONDS.sleep",
                "SECONDS.sleep",
                "MILLISECONDS.sleep",
            ),
            "regex": ("Pattern.compile", "Pattern.matches", "Pattern.quote"),
            "time": (
                "System.currentTimeMillis",
                "System.nanoTime",
                "Instant.",
                "Duration.",
                "LocalDate.",
                "LocalDateTime.",
                "LocalTime.",
                "ZonedDateTime.",
                "OffsetDateTime.",
                "Period.",
                "Clock.",
                "TimeUnit.",
                "ChronoUnit.",
                "DateTimeFormatter.",
                "Date",
                "Calendar.",
                "SimpleDateFormat",
            ),
            "io": (
                "Files.",
                "Paths.get",
                "FileReader",
                "FileWriter",
                "FileInputStream",
                "FileOutputStream",
                "BufferedReader",
                "BufferedWriter",
                "Socket",
                "ServerSocket",
                "URL",
                "HttpURLConnection",
                "RandomAccessFile",
            ),
            "bailout": ("System.exit", "Runtime.getRuntime().exit", "Runtime.getRuntime().halt"),
        },
    ),
    "c": Spec(
        "c",
        (".c", ".h"),
        _fs("function_definition"),
        _fs(),
        _fs(
            "if_statement",
            "for_statement",
            "while_statement",
            "do_statement",
            "case_statement",
            "conditional_expression",
        ),
        _fs(),
        _fs("call_expression"),
        {
            "print": (
                "printf",
                "fprintf",
                "puts",
                "putchar",
                "perror",
                "vprintf",
                "vfprintf",
                "fputs",
                "fputc",
                "putc",
            ),
            "sleep": ("sleep", "usleep", "nanosleep", "Sleep", "thrd_sleep"),
            "regex": ("regcomp", "regexec", "regfree", "pcre_compile", "pcre_exec", "pcre2_compile", "pcre2_match"),
            "time": (
                "time",
                "clock",
                "gettimeofday",
                "clock_gettime",
                "localtime",
                "gmtime",
                "strftime",
                "strptime",
                "difftime",
                "mktime",
                "timegm",
                "ctime",
                "asctime",
                "localtime_r",
                "gmtime_r",
            ),
            "io": (
                "fopen",
                "fread",
                "fwrite",
                "fclose",
                "open",
                "read",
                "write",
                "close",
                "socket",
                "send",
                "recv",
                "connect",
                "accept",
                "bind",
                "listen",
                "fgets",
                "fscanf",
                "fseek",
                "mmap",
            ),
            "bailout": ("exit", "abort", "_exit", "_Exit", "quick_exit"),
        },
        skip_families=_fs("struct_closures"),
    ),
}


def languages() -> list[str]:
    return sorted(SPECS)


def _text(node) -> str:
    return node.text.decode("utf-8", "surrogateescape") if node is not None else ""


def _name(spec: Spec, node) -> str:
    if spec.ts_name == "c":
        d = node.child_by_field_name("declarator")
        while d is not None and d.type in (
            "pointer_declarator",
            "function_declarator",
            "parenthesized_declarator",
            "attributed_declarator",
        ):
            d = d.child_by_field_name("declarator")
        return _text(d)
    return _text(node.child_by_field_name("name"))


def _callee(node) -> str:
    """The callee's text with whitespace removed: `fmt.Println`, `println!`, `System.out.println`, `FileReader`."""
    t = node.type
    if t == "method_invocation":
        obj, name = node.child_by_field_name("object"), node.child_by_field_name("name")
        full = f"{_text(obj)}.{_text(name)}" if obj is not None else _text(name)
    elif t == "macro_invocation":
        full = _text(node.child_by_field_name("macro")) + "!"
    elif t == "object_creation_expression":
        full = _text(node.child_by_field_name("type"))
    elif t == "new_expression":
        full = _text(node.child_by_field_name("constructor"))
    else:
        full = _text(node.child_by_field_name("function"))
    return "".join(full.split())


def _matches(full: str, patterns: tuple[str, ...]) -> str | None:
    """The pattern `full` matches: a prefix ending in `.` or `::`, `Name.` forms, the exact callee, or the last segment of a bare name."""
    last = full.replace("::", ".").split(".")[-1]
    for p in patterns:
        if p.endswith((".", "::")):
            if full.startswith(p) or ("::" + p) in full or ("." + p) in full:
                return p
        elif full == p or full.endswith(("." + p, "::" + p)) or (("." not in p and "::" not in p) and last == p):
            return p
    return None


def _assigned_name(node) -> tuple[str, list[int]]:
    """`const f = () => {}`, `exports.f = function () {}`, `{ f: () => {} }`: the name a function expression is bound to, and the lines to key it by."""
    p = node.parent
    if p is None:
        return "", []
    if p.type == "variable_declarator":
        name = _text(p.child_by_field_name("name"))
    elif p.type == "assignment_expression":
        name = _text(p.child_by_field_name("left")).split(".")[-1]
    elif p.type == "pair":
        name = _text(p.child_by_field_name("key"))
    elif p.type in ("public_field_definition", "field_definition"):
        name = _text(p.child_by_field_name("name") or p.child_by_field_name("property"))
    else:
        return "", []
    lines = {node.start_point[0] + 1, p.start_point[0] + 1}
    if p.parent is not None:
        lines.add(p.parent.start_point[0] + 1)
    return name, sorted(lines)


def _params(spec: Spec, node) -> int:
    params = node.child_by_field_name("parameters")
    if params is None and spec.ts_name == "c":
        d = node.child_by_field_name("declarator")
        while d is not None and d.type != "function_declarator":
            d = d.child_by_field_name("declarator")
        params = d.child_by_field_name("parameters") if d is not None else None
    if params is None:
        return 0
    n = 0
    for c in params.named_children:
        if "comment" in c.type:
            continue
        if spec.ts_name == "go" and c.type in ("parameter_declaration", "variadic_parameter_declaration"):
            n += max(1, len(c.children_by_field_name("name")))
        elif spec.ts_name == "c":
            if (c.type == "parameter_declaration" and _text(c).strip() != "void") or c.type == "variadic_parameter":
                n += 1
        else:
            n += 1
    return n


def _decorators(node) -> list[str]:
    out: list[str] = []
    for c in node.children:
        if c.type == "modifiers":  # Java: annotations sit inside the modifiers
            out.extend(_text(m).split("(")[0] for m in c.children if m.type in ("marker_annotation", "annotation"))
        elif c.type == "decorator":
            out.append(_text(c).split("(")[0])
    prev = node.prev_named_sibling
    while prev is not None and (prev.type in ("attribute_item", "decorator") or "comment" in prev.type):
        if prev.type in ("attribute_item", "decorator"):
            out.append(_text(prev).split("(")[0])
        prev = prev.prev_named_sibling
    return out


def _documented(spec: Spec, node) -> bool:
    """A doc comment directly above, in the language's structured style: `/** */` (C, Java, JS, TS), `///` / `//!` / `/** */` (Rust), any comment (Go: godoc)."""
    prev = node.prev_named_sibling
    while prev is not None and prev.type in ("attribute_item", "decorator"):
        prev = prev.prev_named_sibling
    if prev is None or "comment" not in prev.type or prev.end_point[0] < node.start_point[0] - 1:
        return False
    text = _text(prev).lstrip()
    if spec.ts_name == "go":
        return True
    if spec.ts_name == "rust":
        return text.startswith(("///", "//!", "/**", "/*!"))
    return text.startswith(("/**", "/*!"))


class TreeSitterOracle:
    def __init__(self, spec: Spec) -> None:
        self.spec = spec
        self.exts = spec.exts
        self.families = tuple(Family(*f) for f in _COMMON_FAMILIES if f[0] not in spec.skip_families)
        self._parser: Any = None

    def index(self, text: str) -> dict:
        import tree_sitter_language_pack

        if self._parser is None:
            self._parser = tree_sitter_language_pack.get_parser(self.spec.ts_name)
        root = self._parser.parse(text.encode("utf-8", "surrogateescape")).root_node
        index: dict = {}
        stack = [root]
        while stack:
            node = stack.pop()
            if node.type in self.spec.func_types:
                name = _name(self.spec, node)
                if name:
                    index.setdefault((name, node.start_point[0] + 1), node)
                    nm = node.child_by_field_name("name")
                    if nm is not None:
                        index.setdefault((name, nm.start_point[0] + 1), node)
                    prev = (
                        node.prev_named_sibling
                    )  # a scan may key a decorated function by its first attribute or doc-comment line
                    while prev is not None and (prev.type in ("attribute_item", "decorator") or "comment" in prev.type):
                        index.setdefault((name, prev.start_point[0] + 1), node)
                        prev = prev.prev_named_sibling
            elif node.type in self.spec.closure_types and self.spec.ts_name in ("javascript", "typescript"):
                name, lines = _assigned_name(node)
                if not name:
                    nm = node.child_by_field_name("name")  # a named function expression
                    name, lines = _text(nm), [node.start_point[0] + 1]
                for line in lines if name else []:
                    index.setdefault((name, line), node)
            stack.extend(node.children)
        return index

    def count(self, fn) -> tuple[collections.Counter, dict]:
        spec = self.spec
        n: collections.Counter[str] = collections.Counter()
        tokens: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)

        def add(key: str, tok: str | None = None) -> None:
            n[key] += 1
            if tok:
                tokens[key][tok] += 1

        stack = list(fn.children)
        while stack:
            node = stack.pop()
            stack.extend(node.children)
            if not node.is_named:  # keyword and operator tokens (the `function` keyword is not a function)
                continue
            t = node.type
            if t in spec.branch_types:
                add("branch", t)
            elif t in ("binary_expression", "boolean_operator"):
                op = _text(node.child_by_field_name("operator"))
                if op in ("&&", "||", "and", "or"):
                    add("branch", op)
                if op in ("<<", ">>", "^", "&^", "&", "|"):
                    add("bitwise", op)
            elif t == "unary_expression" and _text(node.child_by_field_name("operator")) == "~":
                add("bitwise", "~")
            elif "assignment" in t and _text(node.child_by_field_name("operator")) in (
                "<<=",
                ">>=",
                "^=",
                "&=",
                "|=",
                "&^=",
            ):
                add("bitwise", _text(node.child_by_field_name("operator")))
            if t in spec.closure_types:
                add("closures")
            if t in spec.throw_types:
                add("bailout", "throw")
            if t in spec.regex_node_types:
                add("regex", "regex-literal")
            if t in spec.call_types:
                full = _callee(node)
                for key, pats in spec.calls.items():
                    hit = _matches(full, pats)
                    if hit:
                        add(key, hit)
        n["args"] = _params(spec, fn)
        deco = _decorators(fn)
        if deco:
            n["decorators"] = len(deco)
            for d in deco:
                tokens["decorators"][d] += 1
        n["doc"] = 1 if _documented(spec, fn) else 0
        return n, tokens


_ORACLES: dict[str, TreeSitterOracle] = {}


def get_oracle(lang: str) -> TreeSitterOracle | None:
    if lang not in SPECS:
        return None
    if lang not in _ORACLES:
        _ORACLES[lang] = TreeSitterOracle(SPECS[lang])
    return _ORACLES[lang]
