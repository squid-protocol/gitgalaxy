"""
Per-language conventions of the SCIP call-graph adapter for C#, Kotlin and PHP (#8161, PR 5).

The LAWS language-admission survey (engine-tuning-study/lang-survey, scripts/survey.py) measured
these three languages against scip-dotnet, scip-java's Kotlin indexer and scip-php; this module is
that survey's adapter conventions, ported into the gate so its lanes score what the survey scored:

  * extents: scip-dotnet and scip-php write no `enclosing_range` and no symbol kinds, so a
    definition's extent is read from the source (as the gate does for rust-analyzer):
    `source_extent()` scans from the end of the declared name to the end of its body -- a `{...}`
    block, a C# `=> expr;` -- and gives a bodyless declaration none (it is not a def).
  * names follow the engine: a C# `.ctor` / `.cctor` is its class's name (as Java's `<init>`); a C#
    explicit interface implementation `System.Collections.IList.Add` is `IList.Add`; PHP keeps
    `__construct`; a Kotlin constructor is `constructor`.
  * a C# definition's line is its first attribute line (`[CLSCompliant(false)]`), the engine's start.
  * Kotlin (scip-java 0.13): each def's typed enclosing range starts at its KDoc and its range is the
    name token -- except a constructor's, which is the whole declaration. A def's line becomes the
    first line after the KDoc; a constructor is its `constructor` keyword, and one without the keyword
    (an implicit primary constructor, an object) or a synthesized member (a property accessor, a data
    class's componentN) is not a def. A reference is a call only when its source token is the
    callee's name -- not a property read through a getter, an operator or a delegate -- and it is a
    call without a `(` too (a trailing lambda, an infix call), except a `::f` reference or a KDoc
    `[f]` link.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import scip_callgraph as sc

from gitgalaxy.core.source_text import read_source

LANGS = frozenset({"csharp", "kotlin", "php"})
# each language's constructor names in its SCIP symbols (scip-java's Kotlin: `<init>`, as Java)
CONSTRUCTOR_NAMES = {"csharp": frozenset({".ctor", ".cctor"}), "php": frozenset({"__construct"})}


# ----------------------------------------------------------------------------- extents


def _skip_string(lines: list[str], ln: int, c: int, lang: str) -> tuple[int, int]:
    """(ln, c) at an opening quote or string prefix: the position just past the literal."""
    t = lines[ln]
    if lang == "kotlin" and t.startswith('"""', c):
        c += 3
        while ln < len(lines):
            k = lines[ln].find('"""', c)
            if k >= 0:
                k += 3
                while k < len(lines[ln]) and lines[ln][k] == '"':
                    k += 1
                return ln, k
            ln, c = ln + 1, 0
        return ln, 0
    if lang == "csharp" and (t.startswith('@"', c) or t.startswith('$@"', c) or t.startswith('@$"', c)):
        c = t.index('"', c) + 1  # a verbatim string: `""` is a quote, and it may span lines
        while ln < len(lines):
            s = lines[ln]
            while c < len(s):
                if s[c] == '"':
                    if s[c + 1 : c + 2] == '"':
                        c += 2
                        continue
                    return ln, c + 1
                c += 1
            ln, c = ln + 1, 0
        return ln, 0
    if lang == "php" and t.startswith("<<<", c):
        m = re.match(r"<<<\s*['\"]?(\w+)", t[c:])
        if m:  # a heredoc / nowdoc ends at its identifier
            ident = m.group(1)
            ln += 1
            while ln < len(lines):
                if re.match(rf"\s*{ident}\b", lines[ln]):
                    return ln, lines[ln].index(ident) + len(ident)
                ln += 1
            return ln, 0
    if lang == "csharp" and t.startswith('$"', c):
        c += 1
    q = t[c]
    c += 1
    multiline = lang == "php"  # PHP '..' and ".." may span lines
    template = 0  # Kotlin "${ ... }" nesting
    while ln < len(lines):
        s = lines[ln]
        while c < len(s):
            ch = s[c]
            if ch == "\\":
                c += 2
                continue
            if lang == "kotlin" and q == '"' and s.startswith("${", c):
                template += 1
                c += 2
                continue
            if template and ch == "{":
                template += 1
            elif template and ch == "}":
                template -= 1
            elif ch == q and not template:
                return ln, c + 1
            c += 1
        if not multiline:
            return ln, len(s)
        ln, c = ln + 1, 0
    return ln, 0


def _indent(s: str) -> int:
    return len(s) - len(s.lstrip())


def _next_code_line(lines: list[str], ln: int) -> int:
    k = ln + 1
    while k < len(lines) and (not lines[k].strip() or lines[k].strip().startswith(("//", "*", "/*", "@"))):
        k += 1
    return k


def _starts_string(s: str, c: int, lang: str) -> bool:
    ch = s[c]
    return (
        ch in "\"'"
        or (lang == "csharp" and ch in "@$" and re.match(r'[@$]{1,2}"', s[c:]) is not None)
        or (lang == "php" and s.startswith("<<<", c))
    )


def source_extent(lines: list[str], after: tuple[int, int], lang: str, def_line: int) -> list[int]:
    """[l0, c0, l1, c1] from the end of the declared name (`after`) to the end of its body; [] when
    the declaration has none (an abstract or interface member, a Kotlin `fun f(): T` with no body)."""
    ln, c = after
    depth = 0  # () and []
    braces = 0
    mode = "sig"  # sig | block | expr
    block_comment = 0
    base_indent = _indent(lines[def_line]) if def_line < len(lines) else 0
    while ln < len(lines):
        s = lines[ln]
        while c < len(s):
            ch, two = s[c], s[c : c + 2]
            if block_comment:
                if two == "*/":
                    block_comment -= 1
                    c += 2
                elif lang == "kotlin" and two == "/*":
                    block_comment += 1  # Kotlin block comments nest
                    c += 2
                else:
                    c += 1
                continue
            if two == "//" or (lang == "php" and ch == "#" and s[c + 1 : c + 2] != "["):
                break
            if two == "/*":
                block_comment = 1
                c += 2
                continue
            if _starts_string(s, c, lang):
                if ch == "'" and lang in ("csharp", "kotlin"):  # a char literal
                    m = re.match(r"'(\\u[0-9a-fA-F]{4}|\\.|[^\\'])'", s[c:])
                    c += m.end() if m else 1
                    continue
                l2, c2 = _skip_string(lines, ln, c, lang)
                if l2 != ln:
                    ln, c = l2, c2
                    s = lines[ln] if ln < len(lines) else ""
                else:
                    c = c2
                continue
            if ch in "([":
                depth += 1
            elif ch in ")]":
                depth -= 1
            elif ch == "{":
                if mode == "sig" and depth <= 0:
                    mode = "block"
                braces += 1
            elif ch == "}":
                braces -= 1
                if mode == "block" and braces == 0 and depth <= 0:
                    return [after[0], after[1], ln, c + 1]
                if braces < 0:  # left the enclosing scope: a bodyless member, or the expression ended
                    return [after[0], after[1], ln, c] if mode == "expr" else []
            elif ch == ";" and depth <= 0 and braces == 0:
                return [after[0], after[1], ln, c + 1] if mode == "expr" else []
            elif mode == "sig" and depth <= 0 and braces == 0:
                if lang == "csharp" and two == "=>":
                    mode = "expr"
                    c += 2
                    continue
                if lang == "kotlin" and ch == "=" and s[c + 1 : c + 2] not in ("=", ">") and s[c - 1 : c] not in "<>!=":
                    mode = "expr"
            c += 1
        if lang == "kotlin" and depth <= 0 and braces == 0 and mode in ("sig", "expr"):
            # Kotlin has no `;`: a signature or an expression body ends with its line unless it continues
            k = _next_code_line(lines, ln)
            nxt = lines[k].lstrip() if k < len(lines) else ""
            tail = s.split("//")[0].rstrip()
            if mode == "sig":
                cont = tail.endswith((",", ":", "=", "(", "<", "->")) or nxt.startswith(
                    ("{", "=", ":", "where", ".", "?.", "?:", ",", ")", ">")
                )
                if not cont:
                    return []
            elif not tail.endswith("=") and (k >= len(lines) or _indent(lines[k]) <= base_indent):
                return [after[0], after[1], ln, len(s)]
        ln, c = ln + 1, 0
    return []


# ----------------------------------------------------------------------------- definitions and references

_COMMENT_LINE = re.compile(r"\s*(/\*|\*|//|$)")


def _kotlin_ref(lines: list[str], o: sc.Occurrence) -> None:
    """A Kotlin reference counts only as a NAMED call: its source token is the callee's name (a
    constructor's: its class, `constructor`, `this` or `super`). A property read (`x.name` ->
    `name.get()`), an operator (`a + b` -> `plus`) or a delegate is not one -- the engine's calls_out
    holds named calls -- so its symbol is cleared (neither an edge nor external)."""
    if o.symbol.startswith("local ") or not o.symbol:
        return
    desc = sc._descriptors(o.symbol)
    if not desc or desc[-1][1] != "().":
        return
    text = sc._text(lines, sc._span(o.range)).strip().strip("`")
    name = desc[-1][0]
    if name == "<init>":
        owner = [n for n, s in desc[:-1] if s == "#"]
        ok = bool(owner) and text in (owner[-1], "constructor", "this", "super")
    else:
        ok = text == name
    if not ok:
        o.symbol = ""


def _kotlin_def(lines: list[str], o: sc.Occurrence) -> None:
    """A scip-java 0.13 Kotlin def, brought to the engine's convention (see the module docstring). A
    non-def keeps its definition role with no extent, so a call to it is neither an edge nor external."""
    if o.symbol.startswith("local "):
        return
    desc = sc._descriptors(o.symbol)
    if not desc or desc[-1][1] != "()." or not o.enclosing:
        return
    span, enc = sc._span(o.range), sc._span(o.enclosing)
    name = desc[-1][0]
    if name != "<init>" and sc._text(lines, (span[0], span[1], span[0], span[1] + len(name))) != name:
        o.enclosing = []  # a synthesized member: a property accessor, a data class's componentN / copy
        return
    start = enc[0]
    while start < span[0] and _COMMENT_LINE.match(lines[start] if start < len(lines) else ""):
        start += 1
    if name == "<init>":
        for ln in range(span[0], min(enc[2], len(lines) - 1) + 1):
            if _COMMENT_LINE.match(lines[ln]):
                continue
            m = re.search(r"\bconstructor\b", lines[ln])
            if m:
                first = enc[0]
                while first < ln and _COMMENT_LINE.match(lines[first]):
                    first += 1
                o.range = [first, 0, ln, m.end()]
                return
            if "{" in lines[ln] or "=" in lines[ln]:
                break
        o.enclosing = []  # an implicit primary constructor, an object or companion: no code of its own
        return
    o.range = [min(start, span[0]), 0, span[2], span[3]]


def normalize(docs: list[sc.Document], sources: dict[str, list[str]], lang: str) -> None:
    """Bring `lang`'s definitions and references to the engine's conventions, in place."""
    for d in docs:
        lines = sources[d.path]
        for o in d.occurrences:
            if lang == "kotlin":
                (_kotlin_def if o.is_definition else _kotlin_ref)(lines, o)
                continue
            if not o.is_definition or o.enclosing:
                continue
            span = sc._span(o.range)
            o.enclosing = source_extent(lines, (span[2], span[3]), lang, span[0])
            if lang == "csharp" and o.enclosing:
                start = span[0]  # the engine's start_line is the first attribute line above the name
                while (
                    start > 0 and lines[start - 1].strip().startswith("[") and lines[start - 1].rstrip().endswith("]")
                ):
                    start -= 1
                if start != span[0]:
                    o.range = [start, 0, span[2], span[3]]


def name(symbol: str, lang: str) -> str | None:
    """The engine's name for a global callable symbol of `lang`, or None to take the shared rule."""
    desc = sc._descriptors(symbol)
    if not desc:
        return None
    last, suffix = desc[-1]
    if lang == "php" and (last, suffix) == ("__construct", "()."):
        return "__construct"  # the engine keeps PHP's constructor name
    if lang == "csharp" and suffix == "()." and last in CONSTRUCTOR_NAMES["csharp"]:
        owner = [n for n, s in desc[:-1] if s == "#"]
        return owner[-1] if owner else None
    if lang == "csharp" and "." in last and suffix in ("().", "."):
        # an explicit interface implementation `System.Collections.IList.Add` -> `IList.Add`
        return ".".join(re.sub(r"<[^<>]*(<[^<>]*>[^<>]*)*>", "", last).split(".")[-2:])
    return None


def is_call(lines: list[str], span: tuple[int, int, int, int], lang: str) -> bool:
    """Kotlin: a call needs no `(` (a trailing lambda, an infix call); a `::f` reference and a KDoc
    `[f]` link are not calls. Other languages: the shared rule only."""
    if lang != "kotlin":
        return False
    head = lines[span[0]][: span[1]] if span[0] < len(lines) else ""
    tail = lines[span[2]][span[3] :] if span[2] < len(lines) else ""
    return not head.rstrip().endswith("::") and not (head.endswith("[") and tail.startswith("]"))


# ----------------------------------------------------------------------------- scope (LAWS M3)

EXTENSIONS = {"csharp": (".cs",), "kotlin": (".kt", ".kts"), "php": (".php",)}
_TEST_DIRS = {"test", "tests", "testing", "__tests__", "spec", "testdata", "fixtures"}
_EXAMPLE_DIRS = {"examples", "example", "samples", "benchmarks", "bench", "docs", "doc"}
_VENDOR_DIRS = {"vendor", "third_party", "node_modules"}
_GENERATED = re.compile(r"(?i)(code generated|autogenerated|auto-generated|do not edit)")


def m3_excluded(path: str, head: str) -> bool:
    """LAWS M3's out-of-scope code, as the admission survey read it for these languages: a test,
    example, doc, bench or vendored directory; a test project or source set (`Newtonsoft.Json.Tests`,
    `.FuzzTests`, `.TestConsole`, `jvmTest`, `test-processor`, `src/test`); a file named `*Test`,
    `*Tests` or `*TestCase`; or a file whose first five lines (`head`) say it is generated."""
    parts = path.split("/")
    for comp in parts[:-1]:
        low = comp.lower()
        if low in _TEST_DIRS or low in _EXAMPLE_DIRS or low in _VENDOR_DIRS:
            return True
        if (
            re.search(r"(?i)(^|[.\-_])tests?($|[.\-_])", comp)
            or re.search(r"(Test|Tests)$", comp)
            or "TestConsole" in comp
        ):
            return True
    if "src/test" in path:
        return True
    if re.search(r"(Test|Tests|TestCase)$", parts[-1].rsplit(".", 1)[0]):
        return True
    return bool(_GENERATED.search(head))


def scope(contract: dict[str, Any], lang: str, head_of: Any) -> dict[str, Any]:
    """`contract` without M3's out-of-scope code (`head_of(path)` -> the file's first five lines), with
    `indexed`: the files the reference has a def in, in scope. An engine function anywhere else (a
    non-JVM Kotlin source set the reference never compiled) cannot be judged, so the gate scores it
    as out of scope too."""
    cache: dict[str, bool] = {}

    def out(path: str) -> bool:
        if path not in cache:
            cache[path] = m3_excluded(path, head_of(path))
        return cache[path]

    exts = EXTENSIONS[lang]
    defs = [d for d in contract["defs"] if not out(d[0]) and d[0].endswith(exts)]
    return {
        **contract,
        "defs": defs,
        "edges": [e for e in contract["edges"] if not out(e[0][0]) and not out(e[1][0])],
        "external": [x for x in contract["external"] if not out(x[0][0])],
        "indexed": sorted({d[0] for d in defs}),
    }


# ----------------------------------------------------------------------------- builds
#
# Each reference is pinned as the survey ran it (lang-survey/report.md, "Results"). A corpus entry's
# `callgraph_build` (tests/import_graph_corpus.json) holds what is particular to its repo: the C# project
# and MSBuild environment, the Gradle arguments. Every build runs on a copy of the corpus checkout, so it
# stays clean (callgraph_refs.content_id), and the contract is scoped to M3 before it is cached.

SCIP_DOTNET_VERSION = "0.2.16"  # NuGet `scip-dotnet`
DOTNET_SDK_VERSION = "10.0.403"
# scip-java 0.13.x is not on Maven Central: the GitHub release binary (it reports 0.0.0-SNAPSHOT, so it is
# identified by its sha256), with its bundled scip-kotlinc plugin; run under a JDK 21
SCIP_JAVA_KOTLIN_VERSION = "0.13.2"
SCIP_JAVA_KOTLIN_SHA256 = "5248136592d19ea2c468f64ebd18587d32de7c961536ff19346f8a025af1d13c"
SCIP_JAVA_KOTLIN_URL = (
    f"https://github.com/sourcegraph/scip-java/releases/download/v{SCIP_JAVA_KOTLIN_VERSION}/scip-java"
)
# scip-php's only release (2023-04; main @71a5b11 resolves more phpdoc-typed receivers: a sensitivity run only)
SCIP_PHP_VERSION = "0.0.2"
PHP_VERSION = "8.4"
SCIP_PHP_HOME = Path(
    os.environ.get("GITGALAXY_SCIP_PHP_HOME", Path.home() / ".cache" / "gitgalaxy" / f"scip-php-{SCIP_PHP_VERSION}")
)
_BUILD_TIMEOUT = 3600


def _run(cmd: list[str], cwd: Path, what: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    try:
        proc = subprocess.run(  # noqa: S603 -- fixed tools on a corpus copy
            cmd, cwd=cwd, env={**os.environ, **(env or {})}, capture_output=True, text=True, timeout=_BUILD_TIMEOUT
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SystemExit(f"scip_lang: {what}: {exc}") from exc
    if proc.returncode != 0:
        raise SystemExit(f"scip_lang: {what} failed ({proc.returncode}):\n{(proc.stdout + proc.stderr)[-3000:]}")
    return proc


def _head(root: Path, path: str) -> str:
    try:
        return "\n".join(read_source(root / path).text.splitlines()[:5])
    except OSError:
        return ""


def _scoped(index: Path, work: Path, lang: str) -> dict[str, Any]:
    if not index.is_file():  # scip-java exits 0 when a build command it was given compiled nothing
        raise SystemExit(f"scip_lang: the {lang} indexer wrote no index ({index.name})")
    contract = sc.contract_from_index(index.read_bytes(), work, lang)
    return scope(contract, lang, lambda p: _head(work, p))


def _copy(repo: Path, dst: Path, keep_git: bool = False) -> Path:
    shutil.copytree(repo, dst, ignore=None if keep_git else shutil.ignore_patterns(".git"), symlinks=True)
    return dst


def _version_out(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False).stdout.strip()  # noqa: S603
    except (OSError, subprocess.TimeoutExpired):
        return ""


def scip_dotnet_version() -> str | None:
    """The pinned scip-dotnet when it and a `dotnet` are on PATH (`--version` prints `0.2.16+<sha>`)."""
    exe = shutil.which("scip-dotnet")
    if not exe or not shutil.which("dotnet"):
        return None
    return _version_out([exe, "--version"]).split("+")[0] or None


def scip_dotnet_contract(repo: Path, build: dict[str, Any] | None = None) -> dict[str, Any]:
    """scip-dotnet's call graph of one project (`build["project"]`, else every solution scip-dotnet finds),
    restored and compiled under `build["env"]` (Newtonsoft.Json: `LibraryFrameworks=net10.0`, the one target
    framework indexed; code under `#if` for the others is invisible to it)."""
    build = build or {}
    with tempfile.TemporaryDirectory(prefix="scip-dotnet-") as tmp:
        work = _copy(repo, Path(tmp) / "src")
        index = Path(tmp) / "index.scip"
        _run(
            [shutil.which("scip-dotnet") or "scip-dotnet", "index", *build.get("projects", ()), "--output", str(index)],
            work,
            "scip-dotnet index",
            {str(k): str(v) for k, v in (build.get("env") or {}).items()},
        )
        return _scoped(index, work, "csharp")


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


_SHA_CACHE: dict[tuple[str, float], str] = {}


def _scip_java_bin() -> str | None:
    return os.environ.get("GITGALAXY_SCIP_JAVA_BIN") or shutil.which("scip-java")


def scip_kotlin_version() -> str | None:
    """The pinned scip-java release when the binary on PATH (or GITGALAXY_SCIP_JAVA_BIN) is that release's
    (by sha256) and a `java` is on PATH."""
    exe = _scip_java_bin()
    if not exe or not os.path.isfile(exe) or not shutil.which("java"):
        return None
    key = (exe, os.path.getmtime(exe))
    if key not in _SHA_CACHE:
        _SHA_CACHE[key] = _sha256(exe)
    return SCIP_JAVA_KOTLIN_VERSION if _SHA_CACHE[key] == SCIP_JAVA_KOTLIN_SHA256 else None


def scip_kotlin_contract(repo: Path, build: dict[str, Any] | None = None) -> dict[str, Any]:
    """scip-java's (scip-kotlinc's) call graph of a Gradle repo: `scip-java index --build-tool=gradle` with
    `build["gradle_args"]` as its build command (kotlinpoet: no daemon, 3 GB heaps, and the tasks scip-java
    runs by default -- a build command replaces them). Only JVM source sets compile, so a Kotlin
    Multiplatform repo's other source sets are out of scope (scope's `indexed`). Needs network the first
    time (Gradle and the repo's dependencies)."""
    build = build or {}
    with tempfile.TemporaryDirectory(prefix="scip-kotlin-") as tmp:
        work = _copy(repo, Path(tmp) / "src")
        index = Path(tmp) / "index.scip"
        _run(
            [
                _scip_java_bin() or "scip-java",
                "index",
                "--build-tool=gradle",
                f"--output={index}",
                "--",
                *build.get("gradle_args", ()),
            ],
            work,
            "scip-java index (gradle)",
        )
        return _scoped(index, work, "kotlin")


def _composer() -> list[str] | None:
    exe = shutil.which("composer")
    if exe:
        return [exe]
    phar = os.environ.get("GITGALAXY_COMPOSER_PHAR")
    php = shutil.which("php")
    return [php, phar] if phar and php and os.path.isfile(phar) else None


def scip_php_tools() -> Path:
    """scip-php's entry point, fetched with composer into SCIP_PHP_HOME on first use."""
    entry, done = SCIP_PHP_HOME / "bin" / "scip-php", SCIP_PHP_HOME / ".complete"
    if not done.is_file():
        composer = _composer()
        if composer is None:
            raise SystemExit("scip_lang: composer is required to fetch scip-php")
        shutil.rmtree(SCIP_PHP_HOME, ignore_errors=True)
        SCIP_PHP_HOME.parent.mkdir(parents=True, exist_ok=True)
        _run(
            [*composer, "create-project", "--no-dev", "--no-interaction", "--no-progress",
             f"davidrjenni/scip-php:{SCIP_PHP_VERSION}", str(SCIP_PHP_HOME)],
            SCIP_PHP_HOME.parent,
            "fetching scip-php",
        )  # fmt: skip
        done.write_text(SCIP_PHP_VERSION)
    return entry


def scip_php_version() -> str | None:
    """The pinned scip-php when php and composer are on PATH (it is fetched on first build), or the version
    a GITGALAXY_SCIP_PHP_HOME install records."""
    if not shutil.which("php"):
        return None
    done = SCIP_PHP_HOME / ".complete"
    if done.is_file():
        return done.read_text().strip() or None
    return SCIP_PHP_VERSION if _composer() else None


def scip_php_contract(repo: Path, build: dict[str, Any] | None = None) -> dict[str, Any]:
    """scip-php's call graph of a Composer repo: `composer install --no-scripts --no-plugins` (scip-php reads
    the autoloader), then scip-php in the repo's root, which also wants its `.git` and `tests/`."""
    build = build or {}
    entry = scip_php_tools()
    composer = _composer()
    if composer is None:
        raise SystemExit("scip_lang: composer is required for the php reference")
    php = shutil.which("php") or "php"
    with tempfile.TemporaryDirectory(prefix="scip-php-") as tmp:
        work = _copy(repo, Path(tmp) / "src", keep_git=True)
        _run(
            [*composer, "install", "--no-scripts", "--no-plugins", "--no-interaction", "--no-progress"],
            work,
            "composer install",
        )
        _run([php, str(entry), f"--memory-limit={build.get('memory_limit', '8G')}"], work, "scip-php")
        return _scoped(work / "index.scip", work, "php")
