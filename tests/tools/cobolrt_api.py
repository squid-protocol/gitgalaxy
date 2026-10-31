#!/usr/bin/env python
"""The cobolrt public API contract (#4718): what generated code and ports may call, checked against the real sources.

Source of truth: ``docs/language_status/cobolrt_api.json``; the promise it carries: ``docs/cobolrt_api_contract.md``.

The surface is read, never hand-listed: the Java files under det/cobolrt, CicsSpec.java and the classes the forges emit
(`forge_units`). It is parsed with tree-sitter-java, Java's own accessibility rules deciding what is in scope (public or
protected on a public type; an interface's implicit public; enum constants; a record's canonical constructor and
accessors; a class's implicit default constructor). A forge's text is what the forge emits, its template placeholders
filled by the forge's own function where it has one.

Callers are every committed port (`committed_callers`), a det_port.py --translate-only work directory (`--generated`),
and the translator's Python itself (`emitter_refs`: the `Cobol.x` strings it writes). A caller's references are resolved
by a small type inference: imports, fields, locals, parameters, `var` initialisers, casts, `new`, and a runtime call's
declared return type, including the one type argument of a `List<Field>` or `Optional<Field>`.

What it cannot see, stated rather than hidden:
- an overload is told by name and argument count, not by argument types: a call binds every overload of that count, so
  a promotion promotes them all and none of them may stay internal;
- a receiver the inference cannot type (a lambda parameter, the result of a non-runtime call) is not checked;
- the emitter scan reads string constants: a name built at run time (f"Cobol.{op}") is seen only through generated
  output, which is why `--generated` exists and why the scan of committed ports is not the whole check;
- reflection: nothing in the runtime or the ports uses it to reach a member, and it would not be seen.

  cobolrt_api.py --check [--generated DIR ...]     exit 1 when manifest, sources and callers disagree
  cobolrt_api.py generate [--generated DIR ...] [--promote-used]
                                                   rewrite the manifest from the sources, keeping every classification;
                                                   a new member starts internal, --promote-used makes what callers use
                                                   public and refreshes the evidence
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess  # noqa: S404 -- `git ls-files`, a fixed argv
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO))

from det_port import java_segments  # noqa: E402 -- the one Java lexer
from gitgalaxy.core.source_text import decode_bytes  # noqa: E402

MANIFEST = REPO / "docs" / "language_status" / "cobolrt_api.json"
TRANSLATOR = REPO / "gitgalaxy" / "tools" / "cobol_to_java"
RT = TRANSLATOR / "det" / "cobolrt"
SCHEMA = "cobolrt-api/1"
PUBLIC, INTERNAL = "public", "internal"

# Where a variant ships (program.runtime_files, cobol_to_java_batch_forge._sort_sources, the forges' own gates).
DET_BATCH, DET_STANDALONE, SORT_JOB = "det-batch", "det-standalone", "sort-job"
FORGE_CICS, FORGE_BATCH, FORGE_FILES, FORGE_ALWAYS, FORGE_DB2, FORGE_CALL = (
    "forge-cics", "forge-batch-jobs", "forge-batch-files", "forge-always", "forge-db2", "forge-call",
)  # fmt: skip
# The batch forge's classes a no-JCL batch estate does not get (_SPRING_BATCH_RUNTIME)
SPRING_ONLY = ("JclSteps", "JclJobLauncher")

# Evidence labels. RUNTIME_ONLY and HARNESS only explain an internal member; the others make one public.
DET_PORT, MODEL_PORT, FROZEN, GENERATED = "det-port", "model-port", "frozen-overlay", "generated"
EMITTER, EMITTER_DYNAMIC, SIGNATURE = "emitter", "emitter-dynamic", "signature"
COMPUTED = "computed-receiver"  # (a working list, `scan_tree` files what survives under EMITTER_DYNAMIC)
RUNTIME_ONLY, HARNESS = "runtime", "harness"
CALLER_KINDS = (DET_PORT, MODEL_PORT, FROZEN, GENERATED)  # the Java files `committed_callers` hands out

# Every committed .java file is one of these (`classify_java`): a new place fails the test instead of going unscanned.
# (the harness's adapters to other vendors' output and the referees: they name no runtime class)
NOT_PORTS = ("tests/tools/devin/", "tests/tools/ibm_wca4z/", "tests/tools/thirdparty/", "tests/tools/referees/")

# Methods every class inherits from the JDK: never a surface member.
OBJECT_METHODS = {"toString", "equals", "hashCode", "getClass", "notify", "notifyAll", "wait"}
ENUM_METHODS = {"values", "valueOf", "name", "ordinal", "compareTo", "getDeclaringClass"}

# A container's single type argument, for a call on `List<Field>` / `Optional<Field>`.
ELEMENT_CALLS = {
    "get",
    "getFirst",
    "getLast",
    "orElse",
    "orElseThrow",
    "next",
    "remove",
    "poll",
    "peek",
    "pop",
    "first",
}


# ---- the surface ----------------------------------------------------------------------------------------------
def java_parser() -> Any:
    from tree_sitter_language_pack import get_parser

    return get_parser("java")


def parse(parser: Any, text: str) -> Any:
    """The tree of a Java text. A real NUL inside a char literal (CicsTask: the forge's Python string writes '\\0' as the
    byte) costs the grammar the whole class, so literals are masked first: nothing here reads a literal's content."""
    try:
        segments = java_segments(text)
    except ValueError:  # (it does not lex: has_error will say so)
        return parser.parse(text.encode("utf-8")).root_node
    masked = "".join(re.sub(r"[^\x20-\x7e\n]", " ", t) if k == "literal" else t for k, t in segments)
    return parser.parse(masked.encode("utf-8")).root_node


def arg_count(call: Any) -> int:
    """How many arguments a call passes (a comment between them is a named node too)."""
    args = call.child_by_field_name("arguments")
    return sum(not c.type.endswith("_comment") for c in args.named_children) if args is not None else 0


@dataclass
class Unit:
    """One runtime compilation unit, as emitted."""

    origin: str  # repo-relative: the file, or the forge module holding its text
    text: str
    variants: tuple[str, ...]


@dataclass
class Member:
    id: str  # Type.name(param types), Type.<init>(...), Type.NAME
    kind: str  # method, constructor, field, constant
    name: str
    arity: int
    varargs: bool
    static: bool
    returns: str  # the declared type, a runtime type by its id
    abstract: bool = False
    names: tuple[str, ...] = ()  # the runtime types its signature names


@dataclass
class JType:
    id: str  # cobolrt.Cobol, cobolrt.Cobol.Dc, cics.CicsTask
    kind: str  # class, interface, enum, record, annotation
    origin: str
    variants: tuple[str, ...]
    supers: list[str] = field(default_factory=list)  # as written, resolved to ids where they are runtime types
    members: list[Member] = field(default_factory=list)


def _file_variants(rel: str) -> tuple[str, ...]:
    if rel.startswith("batch/"):
        return (DET_BATCH, SORT_JOB)
    if rel.startswith("standalone/"):
        return (DET_STANDALONE,)
    if rel.startswith(("cics/", "sql/")):
        return (DET_BATCH, DET_STANDALONE)
    return (DET_BATCH, DET_STANDALONE, SORT_JOB)


def _rel(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def forge_units() -> list[Unit]:
    """The runtime classes the forges emit into a project, by the forges' own constants and functions."""
    from gitgalaxy.tools.cobol_to_java import (
        cobol_to_java_batch_forge as batch,
        cobol_to_java_call_forge as call,
        cobol_to_java_compare_forge as compare,
        cobol_to_java_db2_forge as db2,
        cobol_to_java_repository_forge as repo,
        cobol_to_java_transaction_forge as tx,
    )

    def origin(module: Any) -> str:
        return _rel(Path(module.__file__))

    pkg = "__PACKAGE__"
    units = [
        Unit(origin(tx), tx.CICS_TASK_JAVA, (FORGE_CICS,)),
        Unit(origin(repo), repo.COBOL_RECORDS_JAVA.replace(f"package {pkg};", f"package {pkg}.entity.vsam;"),
             (FORGE_ALWAYS,)),
        Unit(origin(repo), repo.cobol_edit_source(f"{pkg}"), (FORGE_ALWAYS,)),
        Unit(origin(compare), compare.generate_compare_util(pkg), (FORGE_ALWAYS,)),
        Unit(origin(db2), db2.db2_dates_source(pkg, "ISO"), (FORGE_DB2,)),
        Unit(origin(call), call.CallForge.ref_sources(SimpleNamespace(_refs=True, package=pkg))["CobolRef"],
             (FORGE_CALL,)),
    ]  # fmt: skip
    for name, text in sorted(batch._RUNTIME.items()):
        variants = (FORGE_BATCH,) if name in SPRING_ONLY else (FORGE_BATCH, FORGE_FILES)
        units.append(Unit(origin(batch), text.replace("{pkg}", f"{pkg}.{batch.SUBPACKAGE}"), variants))
    return units


def runtime_units() -> list[Unit]:
    units = [Unit(_rel(f), f.read_text(encoding="utf-8"), _file_variants(f.relative_to(RT).as_posix()))
             for f in sorted(RT.rglob("*.java"))]  # fmt: skip
    spec = TRANSLATOR / "CicsSpec.java"
    units.append(Unit(_rel(spec), spec.read_text(encoding="utf-8"), (FORGE_CICS,)))
    return units + forge_units()


def _mods(node: Any) -> set[str]:
    for c in node.children:
        if c.type == "modifiers":
            return {m.text.decode() for m in c.children if not m.type.endswith("annotation")}
    return set()


def _text(node: Any) -> str:
    return re.sub(r"\s+", " ", node.text.decode()).strip() if node is not None else ""


def _strip_generics(text: str) -> str:
    out, depth = [], 0
    for ch in text:
        depth += ch == "<"
        if depth == 0:
            out.append(ch)
        depth -= ch == ">"
    return "".join(out).replace(" ", "")


def _param_type(p: Any) -> tuple[str, bool]:
    """A formal parameter's type as `id`s show it, and whether it is a varargs one."""
    if p.type == "spread_parameter":
        t = next(c for c in p.named_children if c.type not in ("modifiers", "variable_declarator"))
        return _strip_generics(_text(t)) + "...", True
    extra = _text(p.child_by_field_name("dimensions"))
    return _strip_generics(_text(p.child_by_field_name("type"))) + extra.replace(" ", ""), False


TYPE_DECLS = {"class_declaration": "class", "interface_declaration": "interface", "enum_declaration": "enum",
              "record_declaration": "record", "annotation_type_declaration": "annotation"}  # fmt: skip


def _base_name(text: str) -> str:
    return _strip_generics(text).replace("[]", "").replace("...", "")


class Surface:
    """Every in-scope type and member of the given units, with name resolution across them."""

    def __init__(self, units: list[Unit]) -> None:
        self.parser = java_parser()
        self.types: dict[str, JType] = {}
        self._pending: list[tuple[JType, dict[str, str], str]] = []
        trees = [(u, parse(self.parser, u.text)) for u in units]
        broken = [u.origin for u, root in trees if root.has_error]
        if broken:  # (a part of a type would read as a shrunken surface)
            raise ValueError(f"not parsable as Java: {sorted(set(broken))}")
        for u, root in trees:
            self._unit(u, root)
        for t, imports, package in self._pending:
            self._resolve(t, imports, package)

    @staticmethod
    def _package(root: Any) -> str:
        for n in root.named_children:
            if n.type == "package_declaration":
                return _text(n.named_children[-1]).replace("__PACKAGE__.", "").replace(" ", "")
        return ""

    def _unit(self, u: Unit, root: Any) -> None:
        package = self._package(root)
        imports: dict[str, str] = {}
        for n in root.named_children:
            if n.type == "import_declaration":
                name = _text(n).removeprefix("import ").removesuffix(";").replace("__PACKAGE__.", "").strip()
                if not name.endswith("*"):
                    imports[name.rsplit(".", 1)[-1]] = name
        for n in root.named_children:
            if n.type in TYPE_DECLS and "public" in _mods(n):
                self._type(n, f"{package}.{_text(n.child_by_field_name('name'))}", u, imports, package)

    def _type(self, n: Any, tid: str, u: Unit, imports: dict[str, str], package: str) -> None:
        kind = TYPE_DECLS[n.type]
        t = JType(tid, kind, u.origin, u.variants)
        self.types[tid] = t
        self._pending.append((t, imports, package))
        for f in ("superclass", "interfaces"):
            c = n.child_by_field_name(f)
            if c is not None:
                t.supers += [_text(x) for x in self._type_nodes(c)]
        for c in n.named_children:
            if c.type in ("extends_interfaces", "super_interfaces"):
                t.supers += [_text(x) for x in self._type_nodes(c)]
        t.supers = list(dict.fromkeys(t.supers))
        ctors = 0
        body = n.child_by_field_name("body")
        if kind == "record":
            params = [p for p in n.child_by_field_name("parameters").named_children
                      if p.type in ("formal_parameter", "spread_parameter")]  # fmt: skip
            sig = [_param_type(p) for p in params]
            t.members.append(self._ctor(tid, sig))
            for p in params:
                pname = _text(p.child_by_field_name("name")) or _text(p.named_children[-1])
                t.members.append(Member(f"{tid}.{pname}()", "method", pname, 0, False, False, _param_type(p)[0]))
            ctors = 1
        for m in self._body_items(body):
            if m.type in TYPE_DECLS:
                mods = _mods(m)
                nested_public = "public" in mods or (kind in ("interface", "annotation") and "private" not in mods)
                if nested_public:
                    self._type(m, f"{tid}.{_text(m.child_by_field_name('name'))}", u, imports, package)
            elif m.type == "enum_constant":
                cname = _text(m.child_by_field_name("name"))
                t.members.append(Member(f"{tid}.{cname}", "constant", cname, 0, False, True, tid))
            elif m.type in ("method_declaration", "constructor_declaration", "compact_constructor_declaration"):
                ctors += self._callable(t, m)
            elif m.type in ("field_declaration", "constant_declaration"):
                self._field(t, m)

        if kind == "class" and not ctors:  # the implicit default constructor
            t.members.append(self._ctor(tid, []))
        t.members = sorted({m.id: m for m in t.members}.values(), key=lambda m: m.id)

    @staticmethod
    def _type_nodes(node: Any) -> list[Any]:
        out = []
        for c in node.named_children:
            if c.type in ("type_identifier", "scoped_type_identifier", "generic_type"):
                out.append(c)
            elif c.type == "type_list":
                out += Surface._type_nodes(c)
        return out

    @staticmethod
    def _body_items(body: Any) -> list[Any]:
        out = []
        for c in body.named_children if body is not None else []:
            if c.type == "enum_body_declarations":
                out += c.named_children
            else:
                out.append(c)
        return out

    @staticmethod
    def _ctor(tid: str, sig: list[tuple[str, bool]]) -> Member:
        params = ",".join(p for p, _ in sig)
        varargs = bool(sig and sig[-1][1])
        return Member(f"{tid}.<init>({params})", "constructor", "<init>", len(sig), varargs, False, tid)

    def _callable(self, t: JType, m: Any) -> int:
        """Add one method or constructor when in scope; 1 when it is a constructor at all (a declared one, whatever its
        access, removes the implicit default)."""
        mods = _mods(m)
        is_ctor = m.type != "method_declaration"
        in_interface = t.kind in ("interface", "annotation")
        visible = "public" in mods or "protected" in mods or (in_interface and "private" not in mods)
        name = _text(m.child_by_field_name("name"))
        if not visible:
            return int(is_ctor)
        pnode = m.child_by_field_name("parameters")
        params = (
            [p for p in pnode.named_children if p.type in ("formal_parameter", "spread_parameter")] if pnode else []
        )
        sig = [_param_type(p) for p in params]
        if is_ctor:
            t.members.append(self._ctor(t.id, sig))
            return 1
        ptext = ",".join(p for p, _ in sig)
        ret = _text(m.child_by_field_name("type"))
        abstract = "abstract" in mods or (in_interface and "default" not in mods and "static" not in mods)
        t.members.append(Member(f"{t.id}.{name}({ptext})", "method", name, len(sig), bool(sig and sig[-1][1]),
                                "static" in mods, ret, abstract))  # fmt: skip
        return 0

    @staticmethod
    def _field(t: JType, m: Any) -> None:
        mods = _mods(m)
        in_interface = t.kind in ("interface", "annotation")
        visible = "public" in mods or "protected" in mods or in_interface
        ftype = _text(m.child_by_field_name("type"))
        for d in m.named_children:
            if d.type == "variable_declarator":
                fname = _text(d.child_by_field_name("name"))
                if visible:
                    t.members.append(Member(f"{t.id}.{fname}", "field", fname, 0, False,
                                            "static" in mods or in_interface, ftype))  # fmt: skip

    def _resolve(self, t: JType, imports: dict[str, str], package: str) -> None:
        def resolve(text: str) -> str:
            return re.sub(
                r"[A-Za-z_][\w.]*", lambda m: self._name(m.group(0), t.id, imports, package) or m.group(0), text
            )

        t.supers = [resolve(s) for s in t.supers]
        for m in t.members:
            if m.kind != "constructor" and m.kind != "constant":
                m.returns = resolve(m.returns)
            params = m.id[m.id.find("(") + 1 : m.id.rfind(")")] if "(" in m.id else ""
            written = re.findall(r"[A-Za-z_][\w.]*", f"{params},{m.returns}")
            m.names = tuple(sorted({n for n in (self._name(w, t.id, imports, package) or w for w in written)
                                    if n in self.types}))  # fmt: skip

    def _name(self, name: str, within: str, imports: dict[str, str], package: str) -> str | None:
        """A type name as written inside `within` -> its runtime id, or None."""
        name = name.replace("__PACKAGE__.", "")
        head, _, rest = name.partition(".")
        scope = within
        while scope.count(".") and scope != package:  # an enclosing type's nested name (or the enclosing type itself)
            if scope.rsplit(".", 1)[-1] == head:
                tid = scope + (f".{rest}" if rest else "")
                return tid if tid in self.types else None
            cand = f"{scope}.{name}"
            if cand in self.types:
                return cand
            scope = scope.rsplit(".", 1)[0]
        if head in imports:
            full = imports[head] + (f".{rest}" if rest else "")
            return self.suffix_id(full)
        cand = f"{package}.{name}"
        return cand if cand in self.types else self.suffix_id(name) if "." in name else None

    def suffix_id(self, dotted: str) -> str | None:
        """com.acme.cobolrt.Cobol.Dc -> cobolrt.Cobol.Dc: whatever the project's base package is."""
        parts = dotted.split(".")
        for i in range(len(parts)):
            cand = ".".join(parts[i:])
            if cand in self.types:
                return cand
        return None

    def lookup(self, tid: str, name: str, arity: int | None, kinds: tuple[str, ...]) -> list[Member]:
        """The members of `tid` (with its runtime supertypes) of that name and argument count."""
        seen, todo, found = set(), [tid], []
        while todo:
            t = self.types.get(todo.pop())
            if t is None or t.id in seen:
                continue
            seen.add(t.id)
            for m in t.members:
                if m.name == name and m.kind in kinds and (
                    arity is None or m.arity == arity or (m.varargs and arity >= m.arity - 1)):  # fmt: skip
                    found.append(m)
            todo += [s.split("<")[0] for s in t.supers]
        return found

    def has_jdk_super(self, tid: str) -> bool:
        t = self.types.get(tid)
        if t is None:
            return False
        for s in t.supers:
            base = s.split("<")[0]
            if base not in self.types or self.has_jdk_super(base):
                return True
        return False

    def inherited(self, tid: str, name: str) -> bool:
        """A name a caller gets from the JDK, not from the surface."""
        t = self.types[tid]
        return (name in OBJECT_METHODS or (t.kind == "enum" and name in ENUM_METHODS)
                or (t.kind == "annotation") or self.has_jdk_super(tid))  # fmt: skip


# ---- the callers: reference resolution ------------------------------------------------------------------------
@dataclass(frozen=True)
class Ref:
    """One use of the surface: a member (name, arity) or the type itself (name None)."""

    type: str
    name: str | None
    arity: int | None
    kind: str  # call, field, new, type, implements
    path: str
    line: int


@dataclass(frozen=True)
class Ty:
    id: str | None  # the runtime type, None for any other
    elem: Ty | None = None  # of `Field[]` or `List<Field>`


CLASS_LIKE = ("class_declaration", "interface_declaration", "enum_declaration", "record_declaration",
              "annotation_type_declaration")  # fmt: skip
SCOPED = ("block", "method_declaration", "constructor_declaration", "lambda_expression", "for_statement",
          "enhanced_for_statement", "try_with_resources_statement", "catch_clause", "switch_block",
          "static_initializer", "compact_constructor_declaration")  # fmt: skip


class FileScan:
    """The references one Java file makes to the surface."""

    def __init__(self, api: Surface, path: str, text: str, own: list[str] | None = None) -> None:
        self.api = api
        self.path = path
        self.refs: list[Ref] = []
        self.own = own or []  # a runtime unit's own top-level types: unqualified calls resolve to them
        self.imports: dict[str, str] = {}
        self.wild: list[str] = []
        self.package = ""
        self.scopes: list[dict[str, Ty | None]] = [{}]
        self.declared: set[str] = set()
        self.class_stack: list[list[str]] = []
        self.root = parse(api.parser, text)
        self.broken = self.root.has_error
        self._header()
        self._declared(self.root)
        self._visit_children(self.root)

    def _header(self) -> None:
        for n in self.root.named_children:
            if n.type == "package_declaration":
                self.package = _text(n.named_children[-1]).replace(" ", "")
            elif n.type == "import_declaration":
                name = _text(n).removeprefix("import ").removesuffix(";").strip()
                if name.startswith("static "):
                    owner, _, member = name.removeprefix("static ").rpartition(".")
                    tid = self.api.suffix_id(owner)
                    if tid is not None:
                        self._ref(tid, None if member == "*" else member, None, "type" if member == "*" else "call", n)
                elif name.endswith(".*"):
                    self.wild.append(name[:-2])
                    tid = self.api.suffix_id(name[:-2])
                    if tid is not None:
                        self._ref(tid, None, None, "type", n)
                else:
                    self.imports[name.rsplit(".", 1)[-1]] = name
                    tid = self.api.suffix_id(name)
                    if tid is not None:
                        self._ref(tid, None, None, "type", n)

    def _declared(self, node: Any) -> None:
        """A type this file declares hides a runtime type of that name."""
        for c in node.named_children:
            if c.type in CLASS_LIKE:
                self.declared.add(_text(c.child_by_field_name("name")))

    def _ref(self, tid: str, name: str | None, arity: int | None, kind: str, node: Any) -> None:
        self.refs.append(Ref(tid, name, arity, kind, self.path, node.start_point[0] + 1))

    def name_id(self, name: str) -> str | None:
        """A dotted type name as this file writes it -> its runtime id."""
        name = _base_name(name)
        head, _, rest = name.partition(".")
        if head in self.declared:
            return None
        suffix = f".{rest}" if rest else ""
        if head in self.imports:
            return self.api.suffix_id(self.imports[head] + suffix)
        for scope in self.class_stack:
            for tid in scope:
                if f"{tid}.{name}" in self.api.types:
                    return f"{tid}.{name}"
        if "." in name and head.islower():  # package-qualified
            return self.api.suffix_id(name)
        for pkg in (*self.wild, self.package):
            hit = self.api.suffix_id(f"{pkg}.{name}") if pkg else None
            if hit is not None:
                return hit
        return None

    def ty_of_type(self, text: str) -> Ty | None:
        text = text.strip()
        if text.endswith("[]"):
            return Ty(None, elem=self.ty_of_type(text[:-2]))
        if text.endswith("..."):
            return Ty(None, elem=self.ty_of_type(text[:-3]))
        if text.endswith(">") and "<" in text:
            base, arg = text.split("<", 1)
            tid = self.name_id(base)
            args = arg[:-1]
            inner = self.ty_of_type(args) if "," not in args else None
            return Ty(tid, elem=inner)
        tid = self.name_id(text)
        return Ty(tid) if tid else None

    def _api_ty(self, text: str) -> Ty | None:
        """A manifest type string (runtime names already ids) -> Ty."""
        text = text.strip()
        if text.endswith("[]"):
            return Ty(None, elem=self._api_ty(text[:-2]))
        if text.endswith(">") and "<" in text:
            base, arg = text.split("<", 1)
            args = arg[:-1]
            return Ty(base if base in self.api.types else None, elem=self._api_ty(args) if "," not in args else None)
        return Ty(text) if text in self.api.types else None

    # (scopes)
    def _lookup(self, name: str) -> tuple[bool, Ty | None]:
        for s in reversed(self.scopes):
            if name in s:
                return True, s[name]
        return False, None

    def _bind(self, name: str, ty: Ty | None) -> None:
        self.scopes[-1][name] = ty

    def _member_ty(self, ty: Ty, node_name: str, arity: int | None, kinds: tuple[str, ...]) -> Ty | None:
        if ty.id is None:
            return None
        found = self.api.lookup(ty.id, node_name, arity, kinds)
        return self._api_ty(found[0].returns) if found else None

    def type_of(self, n: Any) -> Ty | None:
        t = n.type
        if t == "identifier":
            bound, ty = self._lookup(_text(n))
            if bound:
                return ty
            tid = self.name_id(_text(n))
            return Ty(tid) if tid else None
        if t == "field_access":
            return self._field_ty(n)
        if t == "method_invocation":
            return self._call_ty(n)
        if t == "object_creation_expression":
            return self.ty_of_type(_text(n.child_by_field_name("type")))
        if t == "cast_expression":
            return self.ty_of_type(_text(n.child_by_field_name("type")))
        if t == "parenthesized_expression":
            return self.type_of(n.named_children[0])
        if t == "ternary_expression":
            return self.type_of(n.child_by_field_name("consequence")) or self.type_of(
                n.child_by_field_name("alternative")
            )
        if t == "array_access":
            base = self.type_of(n.child_by_field_name("array"))
            return base.elem if base else None
        if t == "assignment_expression":
            return self.type_of(n.child_by_field_name("left"))
        return None

    def _field_ty(self, n: Any) -> Ty | None:
        text = re.sub(r"\s", "", n.text.decode())
        if n.child_by_field_name("object").type == "this":
            bound, ty = self._lookup(_text(n.child_by_field_name("field")))
            return ty if bound else None
        tid = self.name_id(text) if re.fullmatch(r"[\w.$]+", text) and not self._lookup(text.split(".")[0])[0] else None
        if tid:
            return Ty(tid)
        base = self.type_of(n.child_by_field_name("object"))
        if base is None or base.id is None:
            return None
        return self._member_ty(base, _text(n.child_by_field_name("field")), None, ("field", "constant"))

    def _call_ty(self, n: Any) -> Ty | None:
        obj = n.child_by_field_name("object")
        name = _text(n.child_by_field_name("name"))
        count = arg_count(n)
        if obj is None:
            for scope in reversed(self.class_stack):
                for tid in scope:
                    r = self._member_ty(Ty(tid), name, count, ("method",))
                    if r is not None:
                        return r
            return None
        base = self.type_of(obj)
        if base is None:
            return None
        if base.id is None or not self.api.lookup(base.id, name, count, ("method",)):
            return base.elem if name in ELEMENT_CALLS else None
        return self._member_ty(base, name, count, ("method",))

    # (the walk)
    def _visit_children(self, n: Any) -> None:
        for c in n.named_children:
            self._visit(c)

    def _record_call(self, n: Any) -> None:
        obj = n.child_by_field_name("object")
        name = _text(n.child_by_field_name("name"))
        count = arg_count(n)
        if obj is None:
            for scope in reversed(self.class_stack):
                for tid in scope:
                    if self.api.lookup(tid, name, None, ("method",)):
                        self._ref(tid, name, count, "call", n)
                        return
            return
        base = self.type_of(obj)
        if base is not None and base.id is not None:
            self._ref(base.id, name, count, "call", n)

    def _visit(self, n: Any) -> None:
        t = n.type
        if t in CLASS_LIKE or (t == "object_creation_expression" and n.child_by_field_name("type") is not None
                               and any(c.type == "class_body" for c in n.named_children)):  # fmt: skip
            self._class(n)
            return
        if t == "method_invocation":
            self._record_call(n)
        elif t == "object_creation_expression":
            self._record_new(n)
        elif t == "field_access":
            self._record_field(n)
            obj = n.child_by_field_name("object")
            if obj.type not in ("identifier", "this"):
                self._visit(obj)
            return
        elif t == "method_reference":
            self._record_method_ref(n)
        elif t in ("type_identifier", "scoped_type_identifier"):
            tid = self.name_id(_text(n))
            if tid:
                self._ref(tid, None, None, "type", n)
            return
        if t in SCOPED:
            self.scopes.append({})
            self._bind_header(n)
            self._visit_children(n)
            self.scopes.pop()
            return
        if t == "local_variable_declaration":
            self._local(n)
            return
        self._visit_children(n)

    def _bind_header(self, n: Any) -> None:
        t = n.type
        if t in ("method_declaration", "constructor_declaration"):
            params = n.child_by_field_name("parameters")
            for p in params.named_children if params else []:
                self._bind_param(p)
        elif t == "lambda_expression":
            ps = n.child_by_field_name("parameters")
            if ps is not None and ps.type == "identifier":
                self._bind(_text(ps), None)
            elif ps is not None:
                for p in ps.named_children:
                    if p.type == "identifier":
                        self._bind(_text(p), None)
                    else:
                        self._bind_param(p)
        elif t == "enhanced_for_statement":
            tt = _text(n.child_by_field_name("type"))
            value = n.child_by_field_name("value")
            ty = self.ty_of_type(tt)
            if tt == "var":
                seq = self.type_of(value)
                ty = seq.elem if seq else None
            self._bind(_text(n.child_by_field_name("name")), ty)
        elif t == "catch_clause":
            for p in n.named_children:
                if p.type == "catch_formal_parameter":
                    self._bind(_text(p.child_by_field_name("name")), self.ty_of_type(_text(p.named_children[-2])))
        elif t == "try_with_resources_statement":
            spec = n.child_by_field_name("resources")
            for r in spec.named_children if spec else []:
                if r.type == "resource" and r.child_by_field_name("name") is not None:
                    self._bind(
                        _text(r.child_by_field_name("name")), self.ty_of_type(_text(r.child_by_field_name("type")))
                    )

    def _bind_param(self, p: Any) -> None:
        if p.type == "formal_parameter":
            self._bind(_text(p.child_by_field_name("name")), self.ty_of_type(_text(p.child_by_field_name("type"))))
        elif p.type == "spread_parameter":
            typ = next(c for c in p.named_children if c.type not in ("modifiers", "variable_declarator"))
            decl = next(c for c in p.named_children if c.type == "variable_declarator")
            self._bind(_text(decl.child_by_field_name("name")), self.ty_of_type(_text(typ) + "..."))

    def _local(self, n: Any) -> None:
        declared = _text(n.child_by_field_name("type"))
        for c in n.named_children:
            if c.type == "variable_declarator":
                value = c.child_by_field_name("value")
                if value is not None:
                    self._visit(value)
                ty = self.type_of(value) if declared == "var" and value is not None else self.ty_of_type(declared)
                self._bind(_text(c.child_by_field_name("name")), ty)
            else:
                self._visit(c)

    def _class(self, n: Any) -> None:
        anon = n.type == "object_creation_expression"
        supers: list[str] = []
        if anon:
            self._record_new(n)
            sup = self.name_id(_text(n.child_by_field_name("type")))
            if sup:
                supers.append(sup)
                self._ref(sup, None, None, "implements", n)
        else:
            for f in n.named_children:
                if f.type in ("superclass", "super_interfaces", "extends_interfaces"):
                    for tn in Surface._type_nodes(f):
                        sup = self.name_id(_text(tn))
                        if sup:
                            supers.append(sup)
                            self._ref(sup, None, None, "implements", tn)
                        else:
                            self._visit(tn)
        name = None if anon else _text(n.child_by_field_name("name"))
        here = [*supers]
        if name is not None:
            here += [o for o in self.own if o.rsplit(".", 1)[-1] == name or o.endswith(f".{name}")]
        self.class_stack.append(here)
        self.scopes.append({})
        body = next((c for c in n.named_children if c.type in ("class_body", "interface_body", "enum_body",
                                                               "annotation_type_body")), None)  # fmt: skip
        if n.type == "record_declaration":
            for p in n.child_by_field_name("parameters").named_children:
                self._bind_param(p)
        for m in Surface._body_items(body):
            if m.type in ("field_declaration", "constant_declaration"):
                declared = self.ty_of_type(_text(m.child_by_field_name("type")))
                for d in m.named_children:
                    if d.type == "variable_declarator":
                        self._bind(_text(d.child_by_field_name("name")), declared)
            elif m.type in CLASS_LIKE:
                self.declared.add(_text(m.child_by_field_name("name")))
        if anon:
            self._visit_children(n.child_by_field_name("arguments"))
        if body is not None:
            for m in Surface._body_items(body):
                self._visit(m)
        self.scopes.pop()
        self.class_stack.pop()

    def _record_new(self, n: Any) -> None:
        tid = self.name_id(_text(n.child_by_field_name("type")))
        if tid:
            self._ref(tid, "<init>", arg_count(n), "new", n)

    def _record_field(self, n: Any) -> None:
        field_name = _text(n.child_by_field_name("field"))
        text = re.sub(r"\s", "", n.text.decode())
        obj = n.child_by_field_name("object")
        if obj.type == "this":
            return
        if re.fullmatch(r"[\w.$]+", text) and not self._lookup(text.split(".")[0])[0] and self.name_id(text):
            self._ref(self.name_id(text), None, None, "type", n)
            return
        base = self.type_of(obj)
        if base is not None and base.id is not None and base.id in self.api.types:
            self._ref(base.id, field_name, None, "field", n)

    def _record_method_ref(self, n: Any) -> None:
        first = n.named_children[0]
        target = _text(n.named_children[-1]) if len(n.named_children) > 1 else "new"
        base = self.type_of(first) if first.type in ("identifier", "field_access", "this") else None
        if base is None and first.type in ("type_identifier", "scoped_type_identifier", "generic_type"):
            base = self.ty_of_type(_text(first))
        if base is not None and base.id is not None:
            self._ref(base.id, "<init>" if target == "new" else target, None, "call", n)


# ---- the callers: where they are ------------------------------------------------------------------------------
def classify_java(rel: str, head: str = "") -> str | None:
    """A committed .java file's role: an evidence label, "runtime", "external", or None for a place nobody decided."""
    if rel.startswith(_rel(RT) + "/") or rel == _rel(TRANSLATOR / "CicsSpec.java"):
        return RUNTIME_ONLY
    if rel.startswith(NOT_PORTS):
        return "external"
    if re.match(r"tests/cics_crucible/ports/[^/]+/[^/]+/overlay/cobolrt/", rel):
        return FROZEN
    port = (re.match(r"tests/equivalence/[^/]+/port/service/", rel)
            or re.match(r"tests/cics_crucible/(fixture/)?(det-)?ports/[^/]+/[^/]+/overlay/service/", rel)
            or re.match(r"tests/cobol_mainframe/port_invariance/[^/]+/java/", rel)
            or re.match(r"docs/benchmarks/det-refine-[^/]+/", rel))  # fmt: skip
    if port:
        return DET_PORT if "gitgalaxy-det-port" in head else MODEL_PORT
    return None


def tracked_java() -> list[str]:
    argv = ["git", "-C", str(REPO), "ls-files", "*.java"]
    return subprocess.run(argv, capture_output=True, text=True, check=True).stdout.split()  # noqa: S603, S607


def committed_callers() -> tuple[list[tuple[str, str, str]], list[str]]:
    """((evidence label, repo path, text) of every committed port, committed files nobody classified)."""
    callers, unknown = [], []
    for rel in tracked_java():
        path = REPO / rel
        if not path.is_file():  # (deleted in the working tree, still in the index)
            continue
        text = path.read_text(encoding="utf-8")
        role = classify_java(rel, text[:200])
        if role is None:
            unknown.append(rel)
        elif role in CALLER_KINDS:
            callers.append((role, rel, text))
    return callers, unknown


def generated_callers(work: Path, api: Surface) -> list[tuple[str, str, str]]:
    """Every distinct generated .java file of a det_port.py --translate-only work directory, runtime copies aside."""
    runtime = {t.id.replace(".", "/") + ".java" for t in api.types.values()}  # a project's copies of the runtime
    mention = re.compile(r"\b(?:" + "|".join(sorted({t.split(".")[-1] for t in api.types})) + r")\b")
    seen, out = set(), []
    for f in sorted(work.rglob("*.java")):
        rel = f.relative_to(work).as_posix()
        if "/cobolrt/" in f"/{rel}" or any(rel.endswith("/" + r) for r in runtime):
            continue
        data = f.read_bytes()
        digest = hashlib.sha256(data).digest()
        if digest in seen:
            continue
        seen.add(digest)
        text = decode_bytes(data)
        if mention.search(text):
            out.append((GENERATED, rel, text))
    return out


def scan(api: Surface, callers: list[tuple[str, str, str]]) -> tuple[dict[str, list[Ref]], list[str]]:
    """({evidence label: its references}, the files that do not parse). A frozen runtime copy binds to itself, so only
    its calls out of cobolrt, to the classes a project generates afresh, reach the live surface."""
    out: dict[str, list[Ref]] = defaultdict(list)
    broken = []
    for kind, rel, text in callers:
        file = FileScan(api, rel, text)
        out[kind] += [r for r in file.refs if kind != FROZEN or not r.type.startswith("cobolrt.")]
        if file.broken:
            broken.append(rel)
    return out, broken


def runtime_refs(api: Surface, units: list[Unit]) -> list[Ref]:
    """What the runtime itself calls, across and inside its units."""
    refs: list[Ref] = []
    for u in units:
        package = Surface._package(parse(api.parser, u.text))
        own = [t for t in api.types if t.startswith(package + ".")]
        refs += FileScan(api, u.origin, u.text, own).refs
    return refs


# ---- the emitter's strings --------------------------------------------------------------------------------------
def _python_strings(tree: ast.AST) -> list[tuple[str, int]]:
    """The string constants of a Python module, docstrings aside: what it can write into a Java file."""
    docs: set[int] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            first = n.body[0] if n.body else None
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                docs.add(id(first.value))
    return [(n.value, n.lineno) for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs]  # fmt: skip


def _dynamic_owners(tree: ast.AST, owner: re.Pattern[str]) -> set[str]:
    """The runtime classes a module calls by a computed name: f"Cobol.{fn}(...)", "Cobol." + fn."""
    out: set[str] = set()

    def tail(n: Any) -> None:
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            out.update(m.group(1) for m in owner.finditer(n.value[-40:]))

    for n in ast.walk(tree):
        if isinstance(n, ast.JoinedStr):
            for a, b in zip(n.values, n.values[1:], strict=False):
                if isinstance(b, ast.FormattedValue):
                    tail(a)
        elif isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add):
            tail(n.left)
    return out


def _computed_receiver_calls(tree: ast.AST) -> list[tuple[str, int]]:
    """Methods called on a computed receiver: f"{var}.nextInput();" (Sort), f"{lane}.copyPointer(...)"."""
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.JoinedStr):
            for a, b in zip(n.values, n.values[1:], strict=False):
                if isinstance(a, ast.FormattedValue) and isinstance(b, ast.Constant) and isinstance(b.value, str):
                    m = re.match(r"\.([A-Za-z_]\w*)\(", b.value)
                    if m:
                        out.append((m.group(1), n.lineno))
    return out


def _camel(cobol_name: str) -> str:
    """det/gen.py's name of an intrinsic function: CURRENT-DATE -> currentDate."""
    first, *rest = cobol_name.lower().split("-")
    return first + "".join(w.title() for w in rest)


def emitter_refs(api: Surface, units: list[Unit], roots: list[Path]) -> dict[str, list[Ref]]:
    """`Cobol.x` and `task.x(` as a generator or harness writes them. Only members that exist are reported: a string is
    not Java, so `Cobol.java` in a comment names no member; the template text of the runtime itself is skipped.

    A computed name (f"Cobol.{fn}") has no literal to find, so a module with such a site answers for every string
    constant it holds that names a member of that class (EMITTER_DYNAMIC); a computed receiver (f"{var}.nextInput()")
    for that method of every type (COMPUTED: `scan_tree` keeps the types callers can reach). Both over-approximate on
    purpose: a table of names can sit anywhere in the module, and a wrongly public member is a cheap mistake where a
    wrongly internal one is not."""
    tops: dict[str, list[str]] = defaultdict(list)
    for tid in api.types:
        if tid.rsplit(".", 2)[-2][0].islower():  # a top-level type
            tops[tid.rsplit(".", 1)[-1]].append(tid)
    tops["task"] = ["cics.CicsTask"]
    alternatives = "|".join(sorted(tops, key=len, reverse=True))
    pat = re.compile(rf"(?<![\w$])({alternatives})\.([A-Za-z_]\w*)(\()?")
    dynamic_site = re.compile(rf"(?<![\w$])({alternatives})\.$")
    runtime_text = "\n".join(u.text for u in units if not u.origin.endswith(".java"))
    plain: list[Ref] = []
    dynamic: list[Ref] = []
    computed: list[Ref] = []
    for root in roots:
        for path in sorted(root.rglob("*.py")) if root.is_dir() else [root]:
            rel, tree = _rel(path), ast.parse(path.read_text(encoding="utf-8"))
            strings = _python_strings(tree)
            for s, line in strings:
                if "\n" in s and s[:400] in runtime_text:
                    continue
                for m in pat.finditer(s):
                    before = s[: m.start()]
                    if before.endswith(".") and not re.search(r"cobolrt(\.\w+)*\.$|__PACKAGE__\.\w*\.?$", before):
                        continue
                    owner, name, call = m.group(1), m.group(2), m.group(3)
                    for tid in tops[owner]:
                        if f"{tid}.{name}" in api.types:
                            plain.append(Ref(tid, None, None, "type", rel, line))
                        elif api.lookup(tid, name, None, ("method", "field", "constant")):
                            plain.append(Ref(tid, name, None, "call" if call else "field", rel, line))
            for owner in sorted(_dynamic_owners(tree, dynamic_site)):
                for tid in tops[owner]:
                    for s, line in strings:
                        if re.fullmatch(r"[A-Za-z][\w-]*", s):
                            for name in {s, _camel(s)}:
                                if api.lookup(tid, name, None, ("method",)):
                                    dynamic.append(Ref(tid, name, None, "call", rel, line))
            for name, line in _computed_receiver_calls(tree):
                if name not in OBJECT_METHODS:
                    computed += [Ref(t.id, name, None, "call", rel, line) for t in api.types.values()
                                 if any(m.name == name and m.kind == "method" for m in t.members)]  # fmt: skip
    return {EMITTER: plain, EMITTER_DYNAMIC: dynamic, COMPUTED: computed}


# ---- the verdict ------------------------------------------------------------------------------------------------
@dataclass
class Resolution:
    used: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))  # member or type id -> evidence labels
    missing: list[Ref] = field(default_factory=list)  # names no in-scope member of the type carries


def resolve(api: Surface, by_kind: dict[str, list[Ref]]) -> Resolution:
    r = Resolution()
    for kind, refs in by_kind.items():
        for ref in refs:
            r.used[ref.type].add(kind)
            if ref.kind == "implements":
                for m in api.types[ref.type].members:  # an implementer is held to every abstract method
                    if m.abstract:
                        r.used[m.id].add(kind)
                continue
            if ref.name is None:
                continue
            kinds = ("constructor",) if ref.name == "<init>" else ("method", "field", "constant")
            found = api.lookup(ref.type, ref.name, ref.arity, kinds)
            if not found and ref.kind == "field":
                found = api.lookup(ref.type, ref.name, None, ("field", "constant"))
            if found:
                for m in found:
                    r.used[m.id].add(kind)
            elif not api.inherited(ref.type, ref.name) and not (ref.name == "<init>" and api.has_jdk_super(ref.type)):
                r.missing.append(ref)
    _close_over_types(api, r)
    _spread_to_overrides(api, r)
    return r


def _close_over_types(api: Surface, r: Resolution) -> None:
    """A type a caller must be able to name: what a used member's signature names, an enclosing type, a supertype."""
    by_id = {m.id: m for t in api.types.values() for m in t.members}
    todo = [i for i in r.used if i in api.types]
    for mid in [i for i in r.used if i in by_id]:
        todo += [n for n in by_id[mid].names if n not in r.used]
        r.used.update({n: r.used.get(n, set()) | {SIGNATURE} for n in by_id[mid].names})
    seen = set()
    while todo:
        tid = todo.pop()
        if tid in seen:
            continue
        seen.add(tid)
        outer = tid.rsplit(".", 1)[0]
        above = [outer] if outer in api.types else []
        above += [s.split("<")[0] for s in api.types[tid].supers if s.split("<")[0] in api.types]
        for up in above:
            r.used[up] = r.used.get(up, set()) | {SIGNATURE}
            todo.append(up)


def _spread_to_overrides(api: Surface, r: Resolution) -> None:
    """A call through DetFile reaches Sequential's override: what binds a supertype's member binds its overrides."""
    for t in api.types.values():
        for sup in t.supers:
            parent = api.types.get(sup.split("<")[0])
            for m in t.members if parent is not None else []:
                tail = m.id[len(t.id) :]
                for p in parent.members:
                    if t.id in r.used and p.id in r.used and p.id[len(parent.id) :] == tail:
                        r.used[m.id] |= r.used[p.id]


def _member_row(m: Member, old: dict[str, dict]) -> dict[str, Any]:
    prior = old.get(m.id, {})
    row: dict[str, Any] = {"id": m.id, "kind": m.kind}
    if m.static:
        row["static"] = True
    if m.kind in ("method", "field"):
        row["returns"] = m.returns
    row["visibility"] = prior.get("visibility", INTERNAL)
    row["evidence"] = prior.get("evidence", [])
    return row


def build(api: Surface, old: dict[str, Any] | None, usage: Resolution | None, promote: bool,
          runtime: Resolution | None = None, harness: Resolution | None = None) -> dict[str, Any]:  # fmt: skip
    """The manifest for the surface: classifications carried from `old`; evidence and promotions from `usage`."""
    old_types = {t["id"]: t for t in (old or {}).get("types", [])}
    types = []
    for t in sorted(api.types.values(), key=lambda x: x.id):
        prior = old_types.get(t.id, {})
        prior_members = {m["id"]: m for m in prior.get("members", [])}
        rows = [_member_row(m, prior_members) for m in t.members]
        row = {"id": t.id, "kind": t.kind, "source": t.origin, "variants": list(t.variants), "supers": t.supers,
               "visibility": prior.get("visibility", INTERNAL), "evidence": prior.get("evidence", []), "members": rows}  # fmt: skip
        if usage is not None:
            for item in (row, *rows):
                ev = sorted(usage.used.get(item["id"], ()))
                if promote and ev:
                    item["visibility"] = PUBLIC
                if runtime is not None and harness is not None:
                    item["evidence"] = ev + sorted(
                        ({RUNTIME_ONLY} if item["id"] in runtime.used else set())
                        | ({HARNESS} if item["id"] in harness.used else set())
                    )
        types.append(row)
    out: dict[str, Any] = {
        "schema": SCHEMA,
        "about": [
            "The cobolrt public API (#4718). Written by tests/tools/cobolrt_api.py generate: edit only a `visibility`, "
            "to public or internal; docs/cobolrt_api_contract.md says what they promise.",
            "`evidence` records who called the item when it was last refreshed, and is never checked: det-port, "
            "model-port (committed ports), frozen-overlay (a frozen runtime copy's call to a live class), generated "
            "(translator output), emitter (a translator string), emitter-dynamic (a name a computed emission may "
            "take), runtime, harness; empty: no caller was found.",
        ],
    }
    out["summary"] = summary_of({"types": types})
    out["types"] = types
    return out


def summary_of(manifest: dict[str, Any]) -> dict[str, int]:
    members = [m for t in manifest["types"] for m in t["members"]]
    return {
        "types": len(manifest["types"]),
        "types_public": sum(t["visibility"] == PUBLIC for t in manifest["types"]),
        "members": len(members),
        "members_public": sum(m["visibility"] == PUBLIC for m in members),
        "members_internal": sum(m["visibility"] == INTERNAL for m in members),
    }


def dumps(manifest: dict[str, Any]) -> str:
    """Stable, one member per line: a surface change is a one-line diff."""
    lines = ["{"]
    for key in ("schema", "about", "summary"):
        lines.append(f"  {json.dumps(key)}: {json.dumps(manifest[key], ensure_ascii=False)},")
    lines.append('  "types": [')
    for i, t in enumerate(manifest["types"]):
        head = {k: v for k, v in t.items() if k != "members"}
        lines.append("    " + json.dumps(head, ensure_ascii=False)[:-1] + ', "members": [')
        rows = [json.dumps(m, ensure_ascii=False) for m in t["members"]]
        lines += [f"      {r}{',' if j < len(rows) - 1 else ''}" for j, r in enumerate(rows)]
        lines.append(f"    ]}}{',' if i < len(manifest['types']) - 1 else ''}")
    lines += ["  ]", "}", ""]
    return "\n".join(lines)


def load() -> dict[str, Any]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def check_surface(api: Surface, manifest: dict[str, Any]) -> list[str]:
    """Sources against manifest: every declared item listed, none invented, and a visibility on each."""
    problems = []
    want = build(api, manifest, None, False)
    have_t = {t["id"]: t for t in manifest["types"]}
    want_t = {t["id"]: t for t in want["types"]}
    for tid in sorted(set(want_t) - set(have_t)):
        problems.append(f"type {tid} is in the sources, not in the manifest: run cobolrt_api.py generate")
    for tid in sorted(set(have_t) - set(want_t)):
        word = "PUBLIC type" if have_t[tid]["visibility"] == PUBLIC else "type"
        problems.append(f"{word} {tid} is in the manifest, not in the sources: a removal (contract: how to change it)")
    for tid in sorted(set(want_t) & set(have_t)):
        for key in ("kind", "source", "variants", "supers"):
            if have_t[tid][key] != want_t[tid][key]:
                problems.append(f"type {tid}: {key} is {want_t[tid][key]!r}, the manifest says {have_t[tid][key]!r}")
        have_m = {m["id"]: m for m in have_t[tid]["members"]}
        want_m = {m["id"]: m for m in want_t[tid]["members"]}
        for mid in sorted(set(want_m) - set(have_m)):
            problems.append(f"member {mid} is in the sources, not in the manifest: run cobolrt_api.py generate")
        for mid in sorted(set(have_m) - set(want_m)):
            word = "PUBLIC member" if have_m[mid]["visibility"] == PUBLIC else "member"
            problems.append(f"{word} {mid} is in the manifest, not in the sources: a change of the surface")
        for mid in sorted(set(have_m) & set(want_m)):
            for key in ("kind", "static", "returns"):
                if have_m[mid].get(key) != want_m[mid].get(key):
                    problems.append(
                        f"member {mid}: {key} changed: {have_m[mid].get(key)!r} -> {want_m[mid].get(key)!r}"
                    )
    for item in (*manifest["types"], *(m for t in manifest["types"] for m in t["members"])):
        if item.get("visibility") not in (PUBLIC, INTERNAL):
            problems.append(f"{item['id']}: visibility {item.get('visibility')!r} is neither public nor internal")
    if manifest.get("summary") != summary_of(manifest):
        problems.append("the manifest's summary does not count its entries: run cobolrt_api.py generate")
    return problems


def check_shape(api: Surface, manifest: dict[str, Any]) -> list[str]:
    """A public member needs a public type, and a public signature names no internal type."""
    vis = {t["id"]: t["visibility"] for t in manifest["types"]}
    by_id = {m.id: m for t in api.types.values() for m in t.members}
    problems = []
    for t in manifest["types"]:
        for m in t["members"]:
            if m["visibility"] != PUBLIC:
                continue
            if t["visibility"] != PUBLIC:
                problems.append(f"{m['id']} is public on the internal type {t['id']}")
            for name in by_id[m["id"]].names if m["id"] in by_id else ():
                if vis.get(name) == INTERNAL:
                    problems.append(f"{m['id']} is public but its signature names the internal type {name}")
    return problems


def check_callers(manifest: dict[str, Any], usage: Resolution) -> list[str]:
    """No caller uses an internal item, nor a name the surface does not have."""
    vis = {t["id"]: t["visibility"] for t in manifest["types"]}
    vis.update({m["id"]: m["visibility"] for t in manifest["types"] for m in t["members"]})
    problems = []
    for ref_id, kinds in sorted(usage.used.items()):
        if vis.get(ref_id) == INTERNAL:
            problems.append(f"{ref_id} is internal, and {'/'.join(sorted(kinds))} code uses it")
    return problems + [f"{x.path}:{x.line}: {x.type} has no in-scope member {x.name}" for x in usage.missing]


def scan_tree(api: Surface, units: list[Unit], generated: list[Path]) -> tuple[Resolution, list[str]]:
    """Every caller's references, resolved, and what could not be scanned."""
    callers, unknown = committed_callers()
    for work in generated:
        callers += generated_callers(work, api)
    by_kind, broken = scan(api, callers)
    emitted = emitter_refs(api, units, [TRANSLATOR])
    computed = emitted.pop(COMPUTED)
    by_kind.update(emitted)
    reachable = {i for i in resolve(api, by_kind).used if i in api.types}
    by_kind[EMITTER_DYNAMIC] = by_kind[EMITTER_DYNAMIC] + [r for r in computed if r.type in reachable]
    gaps = [f"{p}: a committed .java file no rule classifies" for p in unknown]
    return resolve(api, by_kind), gaps + [f"{p}: does not parse as Java, so it was not scanned whole" for p in broken]


def harness_refs(api: Surface) -> dict[str, list[Ref]]:
    """Evidence only, read by `generate`, never by --check: the Java the proof harness and the tests write, and the
    CICS spec's harness-fact names (`java="withStartcode"`), by method name, whatever the receiver."""
    names: dict[str, list[str]] = defaultdict(list)
    for t in api.types.values():
        for m in t.members:
            if m.kind == "method" and m.name not in OBJECT_METHODS:
                names[m.name].append(t.id)
    refs: list[Ref] = []
    roots = [REPO / "tests" / "tools", REPO / "tests" / "cics_crucible", REPO / "tests" / "cobol_mainframe",
             REPO / "gitgalaxy" / "standards" / "cics"]  # fmt: skip
    for root in roots:
        for path in sorted(root.rglob("*.py")):
            if path.name == Path(__file__).name:
                continue
            for s, line in _python_strings(ast.parse(path.read_text(encoding="utf-8"))):
                found = {s} if s in names else set(re.findall(r"\.([A-Za-z_]\w*)\(", s))
                refs += [
                    Ref(tid, name, None, "call", _rel(path), line) for name in found for tid in names.get(name, ())
                ]
    return {HARNESS: refs}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", nargs="?", choices=("generate",))
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--generated", type=Path, action="append", default=[],
                    help="a det_port.py --translate-only work directory (repeatable)")  # fmt: skip
    ap.add_argument("--promote-used", action="store_true")
    args = ap.parse_args()
    units = runtime_units()
    api = Surface(units)
    usage, unknown = scan_tree(api, units, args.generated)
    if args.cmd == "generate":
        old = load() if MANIFEST.is_file() else None
        runtime = resolve(api, {RUNTIME_ONLY: runtime_refs(api, units)})
        harness = resolve(api, harness_refs(api))
        new = build(api, old, usage, args.promote_used, runtime, harness)
        MANIFEST.write_text(dumps(new), encoding="utf-8")
        print(json.dumps(new["summary"]))
        return 0
    manifest = load()
    problems = check_surface(api, manifest) + check_shape(api, manifest) + check_callers(manifest, usage) + unknown
    print("\n".join(problems) if problems else f"cobolrt API contract holds: {json.dumps(manifest['summary'])}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
