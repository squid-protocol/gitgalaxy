"""
SCIP -> call-graph contract: one adapter for every language with a SCIP indexer (#3783,
epic #3772).

A SCIP index (https://github.com/sourcegraph/scip) records every definition and every
reference of a symbol, resolved by the language's own compiler, and -- for the indexers
that emit it -- each definition's `enclosing_range` (its whole extent). A call edge is
then a reference IN CALL POSITION that sits inside a named callable definition's extent:

    caller  = the innermost callable definition (with a body) whose extent holds the
              reference -- an anonymous function's calls belong to the named unit around
              it, as the engine's calls_out rule C8 says;
    callee  = the referenced symbol, when the repo defines it with a body;
    external= the referenced symbol is callable and defined outside the repo (the JDK,
              an npm package): the call resolved ONLY outside the repo;
    a reference is a call when the next source character is `(` (after a `<...>` type
    argument list), or it is `new X(`. A method reference (`Foo::bar`), a type or a
    field reference is not a call.

Names follow the engine (callgraph-language-onboarding, "Name units the way the engine
names them"): an overload's `(+1)` disambiguator is dropped (each overload stays its own
def, at its own line); a Java constructor is its class's name, a TypeScript one is
`constructor`; a method of an anonymous class is a local symbol carrying its name. A
bodyless declaration (an abstract or interface method, an overload signature) is not a
def: no code runs there (#3757). Lines are the 1-based line of the declared name.

The reader is a dependency-free protobuf decoder for the fields used here; the schema
is scip.proto (Index 1 metadata, 2 documents; Document 1 relative_path, 2 occurrences,
3 symbols; Occurrence 1 range, 2 symbol, 3 symbol_roles, 7 enclosing_range;
SymbolInformation 1 symbol, 5 kind, 6 display_name; Metadata 2 tool_info {1 name, 2
version}).

    python tests/tools/scip_callgraph.py contract <index.scip> <source-root>   # contract JSON
    python tests/tools/scip_callgraph.py compare <a.json> <b.json>              # edge agreement
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Optional

# ----------------------------------------------------------------------------- protobuf


def _varint(b: bytes, i: int) -> tuple[int, int]:
    x = s = 0
    while True:
        c = b[i]
        i += 1
        x |= (c & 0x7F) << s
        if c < 0x80:
            return x, i
        s += 7


def _fields(b: bytes) -> Iterator[tuple[int, int, Any]]:
    i, n = 0, len(b)
    while i < n:
        key, i = _varint(b, i)
        num, wire = key >> 3, key & 7
        if wire == 0:
            v, i = _varint(b, i)
        elif wire == 2:
            ln, i = _varint(b, i)
            v, i = b[i : i + ln], i + ln
        elif wire == 5:
            v, i = b[i : i + 4], i + 4
        elif wire == 1:
            v, i = b[i : i + 8], i + 8
        else:
            raise ValueError(f"scip_callgraph: unsupported protobuf wire type {wire}")
        yield num, wire, v


def _ints(wire: int, v: Any, acc: list[int]) -> list[int]:
    """A repeated int32: packed (wire 2) or one element at a time (wire 0)."""
    if wire == 0:
        return acc + [v]
    out, i = list(acc), 0
    while i < len(v):
        x, i = _varint(v, i)
        out.append(x)
    return out


@dataclass
class Occurrence:
    range: list[int]
    symbol: str
    roles: int
    enclosing: list[int]

    @property
    def is_definition(self) -> bool:
        return bool(self.roles & 1)


@dataclass
class Document:
    path: str
    occurrences: list[Occurrence] = field(default_factory=list)
    symbols: dict[str, tuple[int, str]] = field(default_factory=dict)  # symbol -> (kind, display_name)


def read_index(data: bytes) -> tuple[dict[str, str], list[Document]]:
    """(tool info, documents) of a serialized SCIP Index."""
    tool: dict[str, str] = {}
    docs: list[Document] = []
    for num, _w, v in _fields(data):
        if num == 1:
            for mnum, _mw, mv in _fields(v):
                if mnum == 2:
                    for tnum, _tw, tv in _fields(mv):
                        if tnum in (1, 2):
                            tool[{1: "name", 2: "version"}[tnum]] = tv.decode()
        elif num == 2:
            doc = Document("")
            for dnum, _dw, dv in _fields(v):
                if dnum == 1:
                    doc.path = dv.decode().replace("\\", "/")
                elif dnum == 2:
                    occ = Occurrence([], "", 0, [])
                    for onum, ow, ov in _fields(dv):
                        if onum == 1:
                            occ.range = _ints(ow, ov, occ.range)
                        elif onum == 2:
                            occ.symbol = ov.decode()
                        elif onum == 3:
                            occ.roles = ov
                        elif onum == 7:
                            occ.enclosing = _ints(ow, ov, occ.enclosing)
                    doc.occurrences.append(occ)
                elif dnum == 3:
                    sym, kind, display = "", 0, ""
                    for snum, _sw, sv in _fields(dv):
                        if snum == 1:
                            sym = sv.decode()
                        elif snum == 5:
                            kind = sv
                        elif snum == 6:
                            display = sv.decode()
                    doc.symbols[sym] = (kind, display)
            docs.append(doc)
    return tool, docs


# ----------------------------------------------------------------------------- symbols

# SymbolInformation.Kind values that run code when called; AbstractMethod (66) is bodyless.
CALLABLE_KINDS = frozenset({9, 17, 26, 80})  # Constructor, Function, Method, StaticMethod
ABSTRACT_KIND = 66
_CONSTRUCTOR_NAMES = {"<init>", "<constructor>", "constructor"}


def _descriptors(symbol: str) -> list[tuple[str, str]]:
    """(name, suffix) of each descriptor of a global SCIP symbol; suffix is one of
    `/` namespace, `#` type, `.` term, `().` method, `:` meta, `!` macro, `[]` type
    parameter, `()` parameter. Names may be `backtick`-quoted."""
    # scheme, manager, package name, version, then the descriptors ("  " escapes a space)
    parts = re.split(r"(?<! ) (?! )", symbol, maxsplit=4)
    text = parts[-1] if len(parts) == 5 else ""
    out: list[tuple[str, str]] = []
    i = 0
    while i < len(text):
        if text[i] == "`":
            j = i + 1
            while j < len(text) and not (text[j] == "`" and text[j + 1 : j + 2] != "`"):
                j += 2 if text[j] == "`" else 1
            name, i = text[i + 1 : j].replace("``", "`"), j + 1
        elif text[i] in "[(":
            close = "]" if text[i] == "[" else ")"
            j = text.index(close, i)
            out.append((text[i + 1 : j], "[]" if close == "]" else "()"))
            i = j + 1
            continue
        else:
            m = re.match(r"[\w$+\-<>]+", text[i:])
            if not m:
                i += 1
                continue
            name, i = m.group(0), i + m.end()
        if text[i : i + 1] == "(":  # a method: name(disambiguator).
            j = text.index(")", i)
            out.append((name, "()."))
            i = j + 2
        elif i < len(text):
            out.append((name, text[i]))
            i += 1
    return out


def _name(symbol: str, display: str, lang: str) -> Optional[str]:
    """The engine's name for a callable symbol, or None if it is not one we name."""
    if symbol.startswith("local "):
        return display or None
    desc = _descriptors(symbol)
    if not desc:
        return None
    name, suffix = desc[-1]
    if suffix not in ("().", "."):
        return None
    if name in _CONSTRUCTOR_NAMES:
        if lang == "java":  # the engine names a Java constructor after its class
            owner = [n for n, s in desc[:-1] if s == "#"]
            return owner[-1] if owner else None
        return "constructor"
    return name


# ----------------------------------------------------------------------------- contract

# a definition's key in the contract: (path, name, line)
DefKey = tuple[str, str, int]


def _span(r: list[int]) -> tuple[int, int, int, int]:
    """SCIP range [line, char, end_char] or [line, char, end_line, end_char], 0-based."""
    return (r[0], r[1], r[0], r[2]) if len(r) == 3 else (r[0], r[1], r[2], r[3])


def _within(pos: tuple[int, int], span: tuple[int, int, int, int]) -> bool:
    return (span[0], span[1]) <= pos <= (span[2], span[3])


def _text(lines: list[str], span: tuple[int, int, int, int]) -> str:
    if span[0] == span[2]:
        return lines[span[0]][span[1] : span[3]] if span[0] < len(lines) else ""
    body = [lines[span[0]][span[1] :]] + lines[span[0] + 1 : span[2]] + [lines[min(span[2], len(lines) - 1)][: span[3]]]
    return "\n".join(body)


def _has_body(lines: list[str], enclosing: list[int], after: tuple[int, int]) -> bool:
    """Code runs there: a `{` block or an arrow `=>` after the declared name."""
    if not enclosing:
        return False
    span = _span(enclosing)
    rest = _text(lines, (after[0], after[1], span[2], span[3]))
    return "{" in rest or "=>" in rest


def _is_call(lines: list[str], span: tuple[int, int, int, int]) -> bool:
    """The reference is followed by an argument list: `f(`, `f<T>(`, or preceded by `new`."""
    line, end = span[2], span[3]
    tail = lines[line][end:] if line < len(lines) else ""
    rest = tail + "".join("\n" + x for x in lines[line + 1 : line + 3])
    s = rest.lstrip()
    if s.startswith("<"):  # explicit type arguments: skip a balanced <...>
        depth = 0
        for k, ch in enumerate(s):
            depth += {"<": 1, ">": -1}.get(ch, 0)
            if depth == 0:
                s = s[k + 1 :].lstrip()
                break
        else:
            return False
    return s.startswith("(")


def contract_from_index(data: bytes, root: Path, lang: str) -> dict[str, Any]:
    """The call-graph contract (callgraph_refs.py) of a SCIP index whose relative paths are
    under `root` (the source root the indexer ran on)."""
    tool, docs = read_index(data)
    sources: dict[str, list[str]] = {}
    for d in docs:
        try:
            sources[d.path] = (root / d.path).read_text(encoding="utf-8", errors="replace").splitlines() or [""]
        except OSError:
            sources[d.path] = [""]

    # every symbol the repo DEFINES, callable or not: a reference to a symbol defined here
    # that is not a def (a field, an abstract method) is neither an edge nor external
    defined: set[str] = {o.symbol for d in docs for o in d.occurrences if o.is_definition}
    kinds: dict[str, int] = {}
    for d in docs:
        for sym, (kind, _display) in d.symbols.items():
            kinds.setdefault(sym, kind)

    defs_by_symbol: dict[str, DefKey] = {}
    scopes: dict[str, list[tuple[tuple[int, int, int, int], DefKey]]] = collections.defaultdict(list)
    for d in docs:
        lines = sources[d.path]
        for o in d.occurrences:
            if not o.is_definition:
                continue
            kind, display = d.symbols.get(o.symbol, (0, ""))
            if kind == ABSTRACT_KIND or (kind and kind not in CALLABLE_KINDS):
                continue
            if not kind and o.symbol.startswith("local "):
                continue  # an untyped local (a variable, a parameter)
            name = _name(o.symbol, display, lang)
            if not name:
                continue
            is_term = not o.symbol.startswith("local ") and _descriptors(o.symbol)[-1][1] == "."
            if is_term and kind not in CALLABLE_KINDS and not _binds_function(lines, o):
                continue  # a term is a def only when it is bound to a function (`const f = () =>`)
            span = _span(o.range)
            if not _has_body(lines, o.enclosing, (span[2], span[3])):
                continue
            key: DefKey = (d.path, name, span[0] + 1)
            if o.symbol.startswith("local "):
                defs_by_symbol[f"{d.path}\0{o.symbol}"] = key
            else:
                defs_by_symbol[o.symbol] = key
            scopes[d.path].append((_span(o.enclosing), key))

    edges: dict[tuple[DefKey, DefKey], int] = {}
    external: set[tuple[DefKey, str]] = set()
    classes = _constructors_by_class(defs_by_symbol, lang)
    for d in docs:
        lines = sources[d.path]
        spans = sorted(scopes[d.path], key=lambda s: (s[0][0], s[0][1]))
        for o in d.occurrences:
            if o.is_definition or not o.symbol:
                continue
            span = _span(o.range)
            pos = (span[0], span[1])
            holders = [(s, k) for s, k in spans if _within(pos, s)]
            if not holders:
                continue
            caller = max(holders, key=lambda h: (h[0][0], h[0][1]))[1]  # innermost: latest start
            sym = f"{d.path}\0{o.symbol}" if o.symbol.startswith("local ") else o.symbol
            callee = defs_by_symbol.get(sym)
            if callee is None and o.symbol in classes and _after_new(lines, span):
                callee = classes[o.symbol]  # TypeScript `new X(`: the reference is to the class
            if callee is not None:
                if _is_call(lines, span) and callee != caller:
                    edges.setdefault((caller, callee), span[0] + 1)
                continue
            if o.symbol.startswith("local ") or o.symbol in defined:
                continue
            ext = _external_name(o.symbol, kinds.get(o.symbol, 0), lang)
            if ext and _is_call(lines, span):
                external.add((caller, ext))

    all_defs = sorted(set(defs_by_symbol.values()))
    return {
        "tool": tool.get("name", "scip"),
        "version": tool.get("version", ""),
        "files": len(docs),
        "defs": [list(k) for k in all_defs],
        "edges": [[list(a), list(b), line] for (a, b), line in sorted(edges.items())],
        "external": [[list(a), n] for a, n in sorted(external)],
    }


def _binds_function(lines: list[str], o: Occurrence) -> bool:
    """`const f = (...) =>` / `= function` / `= async (` on the definition's line."""
    span = _span(o.range)
    tail = lines[span[0]][span[3] :] if span[0] < len(lines) else ""
    return bool(re.match(r"\s*(?::[^=]*)?=\s*(?:async\s+)?(?:function\b|\(|[\w$]+\s*=>|<)", tail))


def _after_new(lines: list[str], span: tuple[int, int, int, int]) -> bool:
    head = lines[span[0]][: span[1]] if span[0] < len(lines) else ""
    return bool(re.search(r"\bnew\s+(?:[\w$]+\s*\.\s*)*$", head))


def _constructors_by_class(defs_by_symbol: dict[str, DefKey], lang: str) -> dict[str, Any]:
    """TypeScript `new X(` references the class `X#`; map it to X's constructor def."""
    out: dict[str, Any] = {}
    for sym, key in defs_by_symbol.items():
        if sym.startswith(("local ",)) or "\0" in sym:
            continue
        desc = _descriptors(sym)
        if desc and desc[-1][0] in _CONSTRUCTOR_NAMES:
            out[sym[: sym.rfind("#") + 1]] = key
    return out


def _external_name(symbol: str, kind: int, lang: str) -> Optional[str]:
    """The name an external callable is reported under, or None if it is not callable."""
    if kind and kind not in CALLABLE_KINDS | {ABSTRACT_KIND}:
        return None
    desc = _descriptors(symbol)
    if not desc or desc[-1][1] != "().":
        return None
    return _name(symbol, "", lang)


# ----------------------------------------------------------------------------- scip-java

# The pinned scip-java the java baseline was measured with, and its javac plugin. Both
# come from Maven Central (com.sourcegraph), fetched once into SCIP_JAVA_HOME.
SCIP_JAVA_VERSION = "0.12.3"
SCIP_JAVA_HOME = Path(
    os.environ.get("GITGALAXY_SCIP_JAVA_HOME", Path.home() / ".cache" / "gitgalaxy" / f"scip-java-{SCIP_JAVA_VERSION}")
)
# Maven Central rate-limits (HTTP 429) bursts of downloads; retry instead of failing.
MAVEN_FLAGS = (
    "-B",
    "-q",
    "-Daether.connector.http.retryHandler.count=10",
    "-Daether.connector.http.retryHandler.interval=3000",
    "-Daether.connector.http.retryHandler.serviceUnavailable=429,503",
)
_FETCH_POM = """<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion>
<groupId>gitgalaxy</groupId><artifactId>scip-java-fetch</artifactId><version>1</version><dependencies>
<dependency><groupId>com.sourcegraph</groupId><artifactId>scip-java_2.13</artifactId><version>{v}</version></dependency>
</dependencies></project>
"""


def _run(cmd: list[str], cwd: Path, what: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)  # noqa: S603 -- fixed tools
    except OSError as exc:
        raise SystemExit(f"scip_callgraph: {what}: {exc}") from exc
    if check and proc.returncode != 0:
        raise SystemExit(f"scip_callgraph: {what} failed ({proc.returncode}):\n{(proc.stdout + proc.stderr)[-3000:]}")
    return proc


def scip_java_tools() -> tuple[Path, Path]:
    """(the scip-java classpath directory, the semanticdb-javac plugin jar), fetched with
    Maven on first use."""
    lib, plugin_dir, done = SCIP_JAVA_HOME / "lib", SCIP_JAVA_HOME / "plugin", SCIP_JAVA_HOME / ".complete"
    if not done.is_file():
        SCIP_JAVA_HOME.mkdir(parents=True, exist_ok=True)
        (SCIP_JAVA_HOME / "pom.xml").write_text(_FETCH_POM.format(v=SCIP_JAVA_VERSION))
        mvn = shutil.which("mvn") or "mvn"
        _run(
            [mvn, *MAVEN_FLAGS, "dependency:copy-dependencies", f"-DoutputDirectory={lib}"],
            SCIP_JAVA_HOME,
            "fetching scip-java",
        )
        _run(
            [
                mvn,
                *MAVEN_FLAGS,
                "dependency:copy",
                f"-Dartifact=com.sourcegraph:semanticdb-javac:{SCIP_JAVA_VERSION}",
                f"-DoutputDirectory={plugin_dir}",
            ],
            SCIP_JAVA_HOME,
            "fetching semanticdb-javac",
        )
        done.write_text(SCIP_JAVA_VERSION)
    return lib, plugin_dir / f"semanticdb-javac-{SCIP_JAVA_VERSION}.jar"


def scip_java_version() -> Optional[str]:
    """The pinned version when java and Maven are on PATH (the jars are fetched on first
    build); None otherwise, so a machine without a JDK skips the java reference."""
    return SCIP_JAVA_VERSION if shutil.which("java") and shutil.which("javac") and shutil.which("mvn") else None


def scip_java_contract(repo: Path) -> dict[str, Any]:
    """scip-java's call graph of a Maven repo.

    Not `scip-java index`: that re-runs the whole Maven build with a forked javac, which
    fails on builds that turn warnings into errors (gson's -Werror) whenever the JVM prints
    anything. Instead:
      1. one reactor `mvn -fae compile dependency:build-classpath` at the root: every
         module's generated sources and compile classpath, with sibling modules resolved to
         their compiled classes (a module that depends on a sibling's unreleased snapshot
         resolves only this way);
      2. per module with main sources, javac with the semanticdb plugin on that classpath;
      3. `scip-java index-semanticdb` over all of it.
    A module whose classpath or compile fails is left out and listed under "skipped". The
    build runs on a copy, so the corpus checkout stays clean. Needs network the first time
    (Maven Central) and a JDK 17+."""
    lib, plugin = scip_java_tools()
    mvn = shutil.which("mvn") or "mvn"
    javac = shutil.which("javac") or "javac"
    with tempfile.TemporaryDirectory(prefix="scip-java-") as tmp:
        tmpdir = Path(tmp)
        work = tmpdir / "src"
        shutil.copytree(repo, work, ignore=shutil.ignore_patterns(".git", "target"))
        if not (work / "pom.xml").is_file():
            raise SystemExit(f"scip_callgraph: {repo} has no root pom.xml (only Maven builds are supported)")
        cp_name = "gitgalaxy-scip-classpath.txt"
        _run(
            [mvn, *MAVEN_FLAGS, "-fae", "compile", "dependency:build-classpath", f"-Dmdep.outputFile={cp_name}"],
            work,
            "resolving the Maven modules",
            check=False,  # -fae: a module that fails is skipped below; the others are indexed
        )
        sdb = tmpdir / "semanticdb"
        indexed, skipped = [], []
        modules = sorted(p.parent for p in work.rglob("pom.xml") if (p.parent / "src" / "main" / "java").is_dir())
        for i, mod in enumerate(modules):
            rel = mod.relative_to(work).as_posix() or "."
            cp_file = mod / cp_name
            if not cp_file.is_file():
                skipped.append(f"{rel} (classpath did not resolve)")
                continue
            main = [mod / "src" / "main" / "java"]
            generated = mod / "target" / "generated-sources"
            main += [g for g in sorted(generated.iterdir()) if g.is_dir()] if generated.is_dir() else []
            test = [mod / "src" / "test" / "java"]
            classpath = [str(plugin), *(c for c in cp_file.read_text().strip().split(os.pathsep) if c)]
            # main and test code together (the engine scans both; the classpath is test scope),
            # falling back to main alone when the tests do not compile here
            for label, roots in (("main+test", main + test), ("main", main)):
                sources = sorted(
                    p for r in roots if r.is_dir() for p in r.rglob("*.java") if p.name != "module-info.java"
                )
                if not sources:
                    break
                argfile = tmpdir / f"sources{i}.txt"
                argfile.write_text("\n".join('"' + str(p).replace("\\", "/") + '"' for p in sources))
                out = tmpdir / "classes" / str(i)
                shutil.rmtree(out, ignore_errors=True)
                proc = _run(
                    [
                        javac,
                        "-d",
                        str(out),
                        "-encoding",
                        "UTF-8",
                        "-nowarn",
                        "-cp",
                        os.pathsep.join(classpath),
                        f"-Xplugin:semanticdb -sourceroot:{work} -targetroot:{sdb}",
                        f"@{argfile}",
                    ],
                    mod,
                    f"javac {rel}",
                    check=False,
                )
                if proc.returncode == 0:
                    indexed.append(f"{rel} ({label})")
                    break
            else:
                skipped.append(f"{rel} (javac failed)")
        if not indexed:
            raise SystemExit(f"scip_callgraph: no Maven module of {repo} compiled; skipped: {skipped}")
        index = tmpdir / "index.scip"
        _run(
            [
                shutil.which("java") or "java",
                "-cp",
                str(lib / "*"),
                "com.sourcegraph.scip_java.ScipJava",
                "index-semanticdb",
                "--output",
                str(index),
                str(sdb),
            ],
            work,
            "scip-java index-semanticdb",
        )
        contract = contract_from_index(index.read_bytes(), work, "java")
        contract["modules"], contract["skipped"] = indexed, skipped
        return contract


# ----------------------------------------------------------------------------- compare


def _pairs(contract: dict[str, Any]) -> collections.Counter[tuple[str, str, str, str]]:
    """Edges as (caller path, caller name, callee path, callee name): lines differ between
    references (declaration vs name line), names and paths do not."""
    return collections.Counter((a[0], a[1], b[0], b[1]) for a, b, *_ in contract["edges"])


def compare(a: dict[str, Any], b: dict[str, Any], samples: int = 8) -> str:
    pa, pb = _pairs(a), _pairs(b)
    both, only_a, only_b = pa & pb, pa - pb, pb - pa
    na, nb = f"{a.get('tool')} {a.get('version')}", f"{b.get('tool')} {b.get('version')}"
    n_both = sum(both.values())
    out = [
        f"| | {na} | {nb} |",
        "|---|---|---|",
        f"| defs | {len(a['defs'])} | {len(b['defs'])} |",
        f"| edges | {sum(pa.values())} | {sum(pb.values())} |",
        f"| in both | {n_both} | {n_both} |",
        f"| only here | {sum(only_a.values())} | {sum(only_b.values())} |",
        f"| agreement (both / this side's edges) | {100 * n_both / max(sum(pa.values()), 1):.1f}% | "
        f"{100 * n_both / max(sum(pb.values()), 1):.1f}% |",
    ]
    for label, only in ((f"only {na}", only_a), (f"only {nb}", only_b)):
        out.append(f"\n{label} (first {samples}):")
        out += [f"- {cp}:{cn} -> {dp}:{dn}" for cp, cn, dp, dn in sorted(only)[:samples]]
    return "\n".join(out)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("contract", help="print the contract JSON of a SCIP index")
    c.add_argument("index")
    c.add_argument("root")
    c.add_argument("--lang", required=True)
    m = sub.add_parser("compare", help="edge agreement of two contract JSON files")
    m.add_argument("a")
    m.add_argument("b")
    m.add_argument("--samples", type=int, default=8)
    a = ap.parse_args(argv)
    if a.cmd == "contract":
        print(json.dumps(contract_from_index(Path(a.index).read_bytes(), Path(a.root), a.lang)))
    else:
        print(compare(json.loads(Path(a.a).read_text()), json.loads(Path(a.b).read_text()), a.samples))
    return 0


if __name__ == "__main__":
    sys.exit(main())
