"""One COBOL program -> one Java service (a deterministic port), plus the runtime it runs on.

    translate(program, copy_dirs, stub, package) -> Result(java, stats)

`stub` is the generated service the port replaces: its class name, and -- for each SELECT -- the repository the
generator mapped the file to (the javadoc "... as BATCH SELECT <name> ..." over the method that uses it)."""

from __future__ import annotations

import base64
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gitgalaxy.core.aperture import DET_PORT_MARKER
from gitgalaxy.tools.cobol_to_java.det import cics as C
from gitgalaxy.tools.cobol_to_java.det import expr as E
from gitgalaxy.tools.cobol_to_java.det import gen as G
from gitgalaxy.tools.cobol_to_java.det import layout as L
from gitgalaxy.tools.cobol_to_java.det import stmt as S
from gitgalaxy.tools.cobol_to_java.det.source import Line, engine_copies_from_ticket, program_lines

RUNTIME = Path(__file__).parent / "cobolrt"


@dataclass
class Result:
    java: str
    service: str  # the class name
    stats: dict


IMAGE_PIECE = 400  # base64 characters per line of a storage image


def has_batch(project: Path | None) -> bool:
    """Whether the generated project has its batch package (CobolFiles, Sysout, ...): a CICS-only estate has none."""
    return project is None or any(project.glob("src/main/java/**/batch/CobolFiles.java"))


def runtime_files(package: str, batch: bool = True) -> dict[str, str]:
    """The runtime's sources, relative to the package directory (cobolrt/...), with the package filled in: the
    batch adapters for a project with a batch package, the standalone Sysout / CobolAbend for one without."""
    out = {}
    for f in sorted(RUNTIME.rglob("*.java")):
        rel = f.relative_to(RUNTIME).as_posix()
        if rel.startswith("batch/" if not batch else "standalone/"):
            continue
        out["cobolrt/" + rel] = f.read_text(encoding="utf-8").replace("__PACKAGE__", package)
    return out


# ---- FILE-CONTROL ----------------------------------------------------------------------------------------------
def file_control(lines: list[Line]) -> list[dict]:
    text = " ".join(ln.text for ln in lines)
    m = re.search(r"\bFILE-CONTROL\s*\.(.*?)(?:\bI-O-CONTROL\b|\bDATA\s+DIVISION\b)", text, re.I | re.S)
    if not m:
        return []
    out = []
    for entry in re.split(r"\bSELECT\b", m.group(1), flags=re.I)[1:]:
        e = " " + entry.strip().rstrip(".") + " "
        words = e.split()
        d: dict[str, Any] = {"select": words[0].upper().rstrip("."), "organization": "SEQUENTIAL", "access": "SEQUENTIAL",
             "status": None, "record_key": None}  # fmt: skip
        a = re.search(r"\bASSIGN\s+(?:TO\s+)?(\S+)", e, re.I)
        d["assign"] = a.group(1).upper().strip("'\"").rstrip(".") if a else d["select"]
        d["assign"] = d["assign"].split("-")[-1] if d["assign"].startswith(("UT-S-", "S-")) else d["assign"]
        o = re.search(r"\bORGANIZATION\s+(?:IS\s+)?(\S+)", e, re.I)
        if o:
            d["organization"] = o.group(1).upper()
        elif re.search(r"\bINDEXED\b", e, re.I):
            d["organization"] = "INDEXED"
        ac = re.search(r"\bACCESS\s+(?:MODE\s+)?(?:IS\s+)?(\S+)", e, re.I)
        if ac:
            d["access"] = ac.group(1).upper()
        k = re.search(r"(?<!ALTERNATE )\bRECORD\s+KEY\s+(?:IS\s+)?(\S+(?:\s+(?:OF|IN)\s+\S+)*)", e, re.I)
        if k:
            d["record_key"] = k.group(1).upper().split()
        st = re.search(r"\bFILE\s+STATUS\s+(?:IS\s+)?(\S+(?:\s+(?:OF|IN)\s+\S+)*)", e, re.I)
        if st:
            d["status"] = [w for w in st.group(1).upper().split() if w not in ("OF", "IN")]
        out.append(d)
    return out


def fd_entries(lines: list[Line]) -> dict[str, dict[str, Any]]:
    """FD name -> its variable-length clauses: `varying` (RECORD IS VARYING [IN SIZE] [FROM m] [TO n]
    [DEPENDING ON item]) as {min, max, depending}, and `mode_v` (RECORDING MODE IS V)."""
    text = " ".join(ln.text for ln in lines)
    m = re.search(r"\bFILE\s+SECTION\s*\.(.*?)(?:\bWORKING-STORAGE\s+SECTION\b|\bLOCAL-STORAGE\s+SECTION\b|"
                  r"\bLINKAGE\s+SECTION\b|\bPROCEDURE\s+DIVISION\b|\Z)", text, re.I | re.S)  # fmt: skip
    out: dict[str, dict[str, Any]] = {}
    if not m:
        return out
    for fd in re.finditer(r"\b([FS])D\s+([A-Z0-9-]+)(.*?)(?=\s0?1\s+[A-Z0-9-]+|\s[FS]D\s|\Z)", m.group(1), re.I | re.S):
        e = fd.group(3)
        d: dict[str, Any] = {
            "varying": None,
            "mode_v": bool(re.search(r"\bRECORDING\s+(?:MODE\s+)?(?:IS\s+)?V\b", e, re.I)),
            "sd": fd.group(1).upper() == "S",  # a sort-merge file description
        }
        v = re.search(r"\bRECORD\s+(?:IS\s+)?VARYING\b(.*?)(?:\.\s*$|$)", e, re.I | re.S)
        if v:
            lo = re.search(r"\bFROM\s+(\d+)", v.group(1), re.I)
            hi = re.search(r"\bTO\s+(\d+)", v.group(1), re.I)
            dep = re.search(r"\bDEPENDING\s+(?:ON\s+)?([A-Z0-9-]+)", v.group(1), re.I)
            d["varying"] = {"min": int(lo.group(1)) if lo else None, "max": int(hi.group(1)) if hi else None,
                            "depending": dep.group(1).upper().rstrip(".") if dep else None}  # fmt: skip
        out[fd.group(2).upper()] = d
    return out


def alphabets(lines: list[Line]) -> tuple[dict[str, str], str | None]:
    """SPECIAL-NAMES: alphabet-name -> its definition's first word (STANDARD-1, NATIVE, EBCDIC, a literal ...), and
    OBJECT-COMPUTER's PROGRAM COLLATING SEQUENCE alphabet-name (or None)."""
    text = " ".join(ln.text for ln in lines)
    m = re.search(r"\bPROCEDURE\s+DIVISION\b", text, re.I)
    head = text[: m.start()] if m else text
    names = {a.group(1).upper(): a.group(2).upper().rstrip(".")
             for a in re.finditer(r"\bALPHABET\s+([A-Z0-9-]+)\s+(?:IS\s+)?(\S+)", head, re.I)}  # fmt: skip
    pc = re.search(r"\bPROGRAM\s+COLLATING\s+SEQUENCE\s+(?:IS\s+)?([A-Z0-9-]+)", head, re.I)
    return names, pc.group(1).upper() if pc else None


def stub_files(stub: str) -> dict[str, str]:
    """SELECT name -> the repository field the generated stub uses for it."""
    out = {}
    for m in re.finditer(r"as BATCH SELECT (\S+) at .*?\*/(.*?)(?=/\*\*|\Z)", stub, re.S):
        r = re.search(r"\b(\w+Repository)\.", m.group(2))
        if r:
            out[m.group(1).upper()] = r.group(1)
    return out


def stub_imports(stub: str) -> dict[str, str]:
    return {m.group(2): m.group(1) for m in re.finditer(r"^import ([\w.]+\.(\w+));", stub, re.M)}


# ---- the program -----------------------------------------------------------------------------------------------
def estate_files(project: Path) -> dict[str, str]:
    """DD name -> repository field, across the generated estate: where a DD name is bound to one dataset in every
    job (the job configs' Dd lists) and that dataset to one repository (the stubs' "<DSN> as BATCH SELECT"
    javadocs). For a program no generated job runs, whose stub maps no file."""
    base = next(project.glob("src/main/java/**/batch"), None)
    svc = next(project.glob("src/main/java/**/service"), None)
    if base is None or svc is None:
        return {}
    dsn_of: dict[str, set] = {}
    for f in base.glob("*.java"):
        for m in re.finditer(r'new Dd\("([A-Z0-9#@$]+)", "([^"]+)"', f.read_text(encoding="utf-8")):
            dsn_of.setdefault(m.group(1), set()).add(m.group(2))
    repo_of: dict[str, set] = {}
    for f in svc.glob("*.java"):
        text = f.read_text(encoding="utf-8")
        for m in re.finditer(r"(\S+) as BATCH SELECT \S+ at .*?\*/(.*?)(?=/\*\*|\Z)", text, re.S):
            r = re.search(r"\b(\w+Repository)\.", m.group(2))
            if r:
                repo_of.setdefault(m.group(1), set()).add(r.group(1))
    out = {}
    for dd, dsns in dsn_of.items():
        if len(dsns) == 1:
            repos = repo_of.get(next(iter(dsns)), set())
            if len(repos) == 1:
                out[dd] = next(iter(repos))
    return out


def eib_records() -> list:
    """DFHEIBLK, the EXEC interface block a CICS program sees (det/copy/DFHEIBLK.cpy)."""
    from gitgalaxy.tools.cobol_to_java.det.source import logical_lines

    raw = [
        "       IDENTIFICATION DIVISION.",
        "       PROGRAM-ID. GGEIB.",
        "       DATA DIVISION.",
        "       WORKING-STORAGE SECTION.",
        *(C.COPY / "DFHEIBLK.cpy").read_text(encoding="latin-1").splitlines(),
    ]
    return L.parse(logical_lines(raw, "DFHEIBLK.cpy"))  # fmt: skip


def structurable(proc: S.Procedure) -> bool:
    """Whether paragraphs can be plain methods called in order: no GO TO (nor ALTER), no EXEC CICS HANDLE (its
    exits transfer control like a GO TO), no SECTION. Then PERFORM a THRU b is a, ..., b in turn, and falling off a
    paragraph is falling into the next -- exactly COBOL's flow, with no dispatcher."""
    for p in proc.paragraphs:
        if p.section == p.name:
            return False
        for s in S.walk(p.body):
            if s.kind == "GOTO" or (s.kind == "EXEC" and re.search(r"(?i)\bHANDLE\b", s.text)):
                return False
            if s.kind == "HOLE" and re.match(r"(?i)\s*ALTER\b", s.text):
                return False
    return True


def _dto_size(gp, cls: str) -> int:
    """A generated DTO's record length, or 0 when the class has no DTO layout (its own record's size stands)."""
    try:
        return gp.dto(cls).size
    except Exception:
        return 0


def write_only_pointers(records: list, proc) -> set[str]:
    """The POINTER items no statement reads (GenApp's SET WS-ADDR-DFHCOMMAREA TO ADDRESS OF DFHCOMMAREA, never used):
    named only as a SET ... TO ADDRESS OF target, and inside groups named only by INITIALIZE, with no REDEFINES over
    the pointer or its groups. Such a pointer's value cannot reach an output, so its SET and its INITIALIZE need no
    model of addresses. Any other mention -- a read, a group MOVE, a CALL / LINK of its record -- leaves it out."""
    items = [x for r in records for x in r.walk()]
    redefined = {x.redefines.upper() for x in items if x.redefines}
    out = set()
    for x in items:
        if x.usage != "POINTER" or x.occurs > 1:
            continue
        chain, p = [x], x.parent
        while p is not None:
            chain.append(p)
            p = p.parent
        names = {c.name.upper() for c in chain}
        if names & redefined or any(c.redefines for c in chain):
            continue
        ok = True
        for para in proc.paragraphs:
            for s in S.walk(para.body):
                words = set(re.findall(r"[A-Z0-9][A-Z0-9-]*", s.text.upper()))
                if not words & names:
                    continue
                if s.kind == "SET-POINTER" and s.data["target"] == x.name.upper():
                    continue
                if s.kind == "INITIALIZE" and {r.name.upper() for r in s.data["refs"]} <= names - {x.name.upper()}:
                    continue
                ok = False
        if ok:
            out.add(x.name.upper())
    return out


def translate(program: Path, copy_dirs: list[Path], stub: str, package: str,
              estate: dict[str, str] | None = None, project: Path | None = None,
              style: str = "dispatch", typed: bool = False, groups: bool = False,
              options: list[str] | None = None) -> Result:  # fmt: skip
    """`style`: "dispatch" (paragraphs numbered, run by a PERFORM / GO TO dispatcher) or "structured" (paragraphs
    as named methods called directly, fields by their COBOL names) -- structured only where `structurable`.
    `typed` (B3): standalone WORKING-STORAGE items held as typed Java fields -- an alphanumeric item a String of
    its length, a binary integer a long -- where every use of the item has a typed form; an item used any other way
    (a reference modification, a STRING target, arithmetic, a file status ...) stays byte storage: translation
    stops at that use (LiftViolation) and is repeated without the item, so a lift never changes behaviour.    `groups` (with `typed`): items inside a group the program also uses whole (a COMMAREA, a record READ INTO) are
    typed too -- the group's bytes stay for those uses, packed from the typed fields before one and unpacked after
    a write; a typed number in a written group, or a write that can transfer control first, keeps byte storage.
    """
    excluded: set[str] = set()
    while True:
        out = _attempt(program, copy_dirs, stub, package, estate, project, style, typed, excluded, groups, options)
        if isinstance(out, Result):
            return out
        if out.names <= excluded:
            raise out
        excluded |= out.names


def trunc_std(program: Path, options: list[str] | None = None) -> bool:
    """Whether binary items keep only their PICTURE's digits (#4102): the TRUNC option in effect -- the program's
    CBL / PROCESS cards over `options` (the compile step's PARM, as a case states it), else IBM's default, STD."""
    from gitgalaxy.core.compiler_options import DEFAULTS, compiler_options, effective, parse_options
    from gitgalaxy.core.source_text import read_source

    rows = [{"option": o, "value": v} for text in options or [] for o, v, _ in parse_options(text)]
    rows += compiler_options(read_source(program).text)
    return str(effective(rows).get("TRUNC") or DEFAULTS["TRUNC"]).upper() == "STD"


def numproc_pfd(program: Path, options: list[str] | None = None) -> bool:
    """Whether the program runs under NUMPROC(PFD) (#4271): the NUMPROC option in effect -- its CBL / PROCESS cards over
    `options` (the compile step's PARM), else IBM's default, NOPFD. NUMPROC(MIG) is NOPFD: Enterprise COBOL 5 and 6 no
    longer support it and compile the default instead (Enterprise COBOL 6.4 Migration Guide, GC27-8715-03, Table 18;
    the equivalence harness refuses MIG for a case built by an earlier compiler: oracle_assumptions.md C5)."""
    from gitgalaxy.core.compiler_options import compiler_options, effective, parse_options
    from gitgalaxy.core.source_text import read_source

    rows = [{"option": o, "value": v} for text in options or [] for o, v, _ in parse_options(text)]
    rows += compiler_options(read_source(program).text)
    return str(effective(rows).get("NUMPROC") or "").upper() == "PFD"


_ENTRIES = re.compile(r"^    public (?:void runTask\(CicsTask task\)|int runBatch\(List<Dd> dds, String parm\)|"
                      r"int handleCall\([^)]*\)) \{$", re.M)  # fmt: skip


_FIELD_DECL = re.compile(r"^    private final Field (f\d+_\w+) = .*\n", re.M)
_FIELD_REF = re.compile(r"\bf\d+_\w+\b")


def drop_unused_fields(java: str) -> str:
    """Drop the Field of every item nothing in the class names (most are a copybook's or a map's items the program
    never touches). A Field is a view of its storage, built with no side effect, so the storage keeps every byte --
    its image, its length, every group move and record I/O -- and only the dead view goes. Repeated until nothing
    changes, so a Field named only by another dropped Field's declaration goes too."""
    while True:
        uses = Counter(_FIELD_REF.findall(java))
        out = "".join(
            ln if (m := _FIELD_DECL.fullmatch(ln)) is None or uses[m.group(1)] > 1 else ""
            for ln in java.splitlines(keepends=True)
        )
        if out == java:
            return out
        java = out


def with_trunc(java: str, std: bool, pfd: bool = False) -> str:
    """Each entry (runTask / runBatch / handleCall) run with this program's TRUNC (Cobol.swapTruncBinary) and NUMPROC
    (Cobol.swapNumprocPfd, #4271), the caller's restored after it -- a LINK or CALL into a program compiled otherwise
    leaves the caller's as it was."""
    out, at = [], 0
    for m in _ENTRIES.finditer(java):
        end = _method_end(java, m.end())
        if end is None:
            continue
        body = java[m.end() : end]
        out.append(java[at : m.end()])
        out.append(
            f"\n        boolean truncBefore = Cobol.swapTruncBinary({'true' if std else 'false'});  // TRUNC"
            f"({'STD' if std else 'BIN'})"
            f"\n        boolean pfdBefore = Cobol.swapNumprocPfd({'true' if pfd else 'false'});  // NUMPROC"
            f"({'PFD' if pfd else 'NOPFD'})\n        try {{"
        )
        out.append("\n".join(("    " + ln) if ln.strip() else ln for ln in body.split("\n")))
        out.append(
            "    } finally {\n            Cobol.swapTruncBinary(truncBefore);\n"
            "            Cobol.swapNumprocPfd(pfdBefore);\n        }\n    "
        )
        at = end
    out.append(java[at:])
    return "".join(out)


def _method_end(java: str, start: int) -> int | None:
    """The offset of the `}` closing the method whose body starts at `start` (string and char literals skipped)."""
    depth, i, n = 1, start, len(java)
    while i < n:
        ch = java[i]
        if ch in "\"'":
            j = i + 1
            while j < n and java[j] != ch:
                j += 2 if java[j] == "\\" else 1
            i = j + 1
            continue
        if ch == "/" and java.startswith("//", i):
            i = java.find("\n", i)
            if i < 0:
                return None
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def _attempt(*args) -> Result | G.LiftViolation:
    """One translation, or the lift that stopped it."""
    try:
        return _translate(*args)
    except G.LiftViolation as v:
        return v


def liftable(records: list, excluded: set[str], rc: L.Item) -> dict[int, str]:
    """The WORKING-STORAGE items a typed field can hold: elementary, named, its name its own, no OCCURS above or at
    it, no REDEFINES at, above or overlapping it, not JUSTIFIED -- PIC X (a String) or a binary integer (a long).
    An item inside a group qualifies too: any use of the group as a whole is a LiftViolation (gen.field_expr)."""
    from collections import Counter

    names = Counter(it.name for r in records for it in r.walk())
    out: dict[int, str] = {}
    images: dict[int, bytes] = {}
    for rec in records:
        if rec is rc or rec.section != "WORKING-STORAGE" or rec.name in ("DFHAID", "DFHBMSCA", "DFHEIBLK"):
            continue
        if rec.redefines or any(r.redefines == rec.name for r in records):
            continue  # a whole record shared with another
        spans = [(x.offset, x.offset + x.size * x.occurs) for x in rec.walk() if x.redefines]
        for it in rec.walk():
            if it.children or not it.pic or it.name == "FILLER" or it.justified or names[it.name] > 1:
                continue
            if it.name in excluded or it.depending:
                continue
            a, chain = it, []
            while a is not None:
                chain.append(a)
                a = a.parent
            if any(x.occurs > 1 or x.redefines for x in chain):
                continue
            lo, hi = it.offset, it.offset + it.size
            if any(s < hi and lo < e for s, e in spans):  # overlapped by (or overlapping) a REDEFINES
                continue
            if it.category == "ALPHANUMERIC" and it.usage == "DISPLAY":
                out[id(it)] = "X"
            elif it.category == "NUMERIC" and it.usage in ("BINARY", "COMP-5") and it.scale == 0:
                out[id(it)] = "BIN"
            elif it.category == "NUMERIC" and (
                it.usage == "PACKED" or (it.usage == "DISPLAY" and not it.sign_separate)
            ):
                image = images.setdefault(id(rec), L.image(rec))
                if L.decode_number(it, image[it.offset : it.offset + it.size]) is not None:
                    out[id(it)] = "NUM"  # (initial bytes that are no number of it: not lifted)
    return out


def _translate(program: Path, copy_dirs: list[Path], stub: str, package: str, estate: dict[str, str] | None,
               project: Path | None, style: str, typed: bool, excluded: set[str],
               groups: bool = False, options: list[str] | None = None) -> Result:  # fmt: skip
    # #4467: a COPY the translator resolves otherwise than the engine did refuses the program (CopyDisagrees)
    engine = engine_copies_from_ticket(project, program) if project is not None else None
    lines = program_lines(program, [*copy_dirs, C.COPY], engine)
    records = L.parse(lines)
    is_cics = "runTask(CicsTask" in stub
    batch = has_batch(project)
    if is_cics:
        records += eib_records()
    # RETURN-CODE: the special register, S9(4) BINARY
    rc = L.Item(1, "GG-RETURN-CODE", "WORKING-STORAGE", pic="S9(4)", usage="BINARY")
    L.layout(rc)
    records.append(rc)
    proc = S.parse(lines)
    # SORT-RETURN: the special register, S9(4) BINARY (IBM: 0 after a successful SORT / MERGE) -- only in a program
    # that sorts or names it, so no other port's storage changes
    sorts = any(s.kind in ("SORT", "MERGE") for p in proc.paragraphs for s in S.walk(p.body))
    named = any(re.search(r"\bSORT-RETURN\b", ln.text, re.I) for ln in lines)
    if (sorts or named) and not any(it.name == "SORT-RETURN" for r in records for it in r.walk()):
        srt = L.Item(1, "GG-SORT-RETURN", "WORKING-STORAGE", pic="S9(4)", usage="BINARY")
        L.layout(srt)
        records.append(srt)
    svc_m = re.search(r"public class (\w+)", stub)
    if svc_m is None:
        raise ValueError("the stub has no public class")
    service = svc_m.group(1)
    prog = G.Program(program.stem.upper(), service, package, records, proc)

    # storages: each 01 / 77 that is not a REDEFINES of another; the FD's records share the first one's
    roots: dict[int, L.Item] = {}
    fd_first: dict[str, L.Item] = {}
    for rec in records:
        if rec.record is not None and rec.record is not rec:
            roots[id(rec)] = rec.record
        elif rec.section == "FILE" and rec.fd:
            first = fd_first.setdefault(rec.fd, rec)
            roots[id(rec)] = first
        else:
            roots[id(rec)] = rec
    sizes: dict[int, int] = {}
    for rec in records:
        r = roots[id(rec)]
        sizes[id(r)] = max(sizes.get(id(r), 0), rec.size * rec.occurs)

    structured = style == "structured" and structurable(proc)
    gen = G.Gen(prog, structured)
    gen.write_only_pointers = write_only_pointers(records, proc)
    if typed:
        gen.sync_groups = groups
        gen.lifted = liftable(records, excluded | {"GG-SORT-RETURN"}, rc)
    gen.alphabets, gen.program_collating = alphabets(lines)
    gen.copy_dirs = [program.parent, *copy_dirs, C.COPY]
    gen.java_root = (project / "src/main/java") if project is not None else None
    gen.clock = "clock.currentDate()" if batch else "Funcs.currentDate(java.time.LocalDateTime.now())"
    if is_cics:
        if project is None:
            raise ValueError("a CICS program needs the generated project")
        gen.cics = C.Cics(gen, C.Generated(project, stub), package)
    if gen.cics is not None:
        gen.dto_codecs = gen.cics
    elif project is not None:
        gen.dto_codecs_factory = lambda: C.Cics(gen, C.Generated(project, stub), package)
    if any(re.match(r"(?is)\s*EXEC\s+SQL\b", s.text) for p in proc.paragraphs for s in S.walk(p.body)
           if s.kind == "EXEC"):  # fmt: skip
        from gitgalaxy.tools.cobol_to_java.det.sql import Sql

        gen.sql = Sql(gen, prog.name, gen.java_root)
    repos = stub_files(stub)
    imports = stub_imports(stub)
    # programs this one CALLs that have a service: the stub's ObjectProvider<XService> ... .handleCall(
    providers = []
    inferred: list[str] = []

    def callee_types(cls: str) -> list[str]:
        """The CALLed service's handleCall parameter types, from the estate (a contract DTO for a group item)."""
        svc = next(project.glob(f"src/main/java/**/service/{cls}Service.java"), None) if project is not None else None
        hc = re.search(r"public int handleCall\(([^)]*)\)", svc.read_text(encoding="utf-8")) if svc else None
        return [x.strip().rsplit(" ", 1)[0] for x in hc.group(1).split(",") if x.strip()] if hc else []

    for m in re.finditer(r"private final ObjectProvider<(\w+)Service> (\w+);", stub):
        if re.search(rf"\b{m.group(2)}\.getObject\(\)\.handleCall\(", stub):
            gen.callees[m.group(1).upper()] = m.group(2)
            gen.callee_types[m.group(1).upper()] = callee_types(m.group(1))
            providers.append((f"ObjectProvider<{m.group(1)}Service>", m.group(2)))
    # a CALLed program the stub does not wire (the CALL sits in a procedure copybook): its service in the estate,
    # when it has the CALL entry
    if project is not None:
        called = {s.data["program"] for p in proc.paragraphs for s in S.walk(p.body) if s.kind == "CALL"}
        for prog_name in sorted(called - set(gen.callees)):
            from gitgalaxy.tools.cobol_to_java.cobol_to_java_names import java_class_base

            cls = java_class_base(prog_name)
            svc = next(project.glob(f"src/main/java/**/service/{cls}Service.java"), None)
            if svc is not None and "public int handleCall(" in svc.read_text(encoding="utf-8"):
                field = cls[0].lower() + cls[1:] + "Service"
                gen.callees[prog_name] = field
                gen.callee_types[prog_name] = callee_types(cls)
                providers.append((f"ObjectProvider<{cls}Service>", field))
                inferred.append(f"CALL {prog_name} -> {cls}Service.handleCall: the estate's service for it")
    file_decls, file_inits, ctor_repos = [], [], []
    fds = fd_entries(lines)
    for fc in file_control(lines):
        fd = G.FileDef(fc["select"], fc["assign"], fc["organization"], fc["access"], fc["status"],
                       " ".join(fc["record_key"]) if fc["record_key"] else None)  # fmt: skip
        fd.fd = fc["select"]
        recs = [r for r in records if r.section == "FILE" and r.fd == fc["select"]]
        if not recs:
            # the FD names the file by its SELECT name: match FD entries
            recs = [r for r in records if r.section == "FILE" and (r.fd or "").upper() == fc["select"]]
        if recs:
            fd.record = recs[0]
            fd.fd = recs[0].fd
        prog.files[fc["select"]] = fd
        if fds.get((fd.fd or fd.select).upper(), {}).get("sd"):
            # a sort file: no dataset, only SORT / MERGE / RELEASE / RETURN, through the active Sort
            fd.sort = True
            fd.why = "a sort file (SD): SORT / MERGE / RELEASE / RETURN only"
            if fd.record is not None:
                lengths = {r.size for r in records if r.section == "FILE" and r.fd == fd.fd}
                fd.sort_length = lengths.pop() if len(lengths) == 1 else None
            file_decls.append(f"    private Sort sort_{G.jname(fd.select)};")
            continue
        if fd.record is None:
            fd.why = "no FD record"
            continue
        if fc["record_key"]:
            try:
                fd.key_item = gen.resolve(
                    E.Ref(fc["record_key"][0], [q for q in fc["record_key"][1:] if q not in ("OF", "IN")])
                )
            except G.Untranslatable:
                fd.key_item = None
        if not batch:
            fd.why = "the generated project has no batch package (CobolFiles) to run files through"
            continue
        storage = _storage_name(roots[id(fd.record)])
        v = G.jname(fd.select)
        reclen = sizes[id(roots[id(fd.record)])]
        clauses = fds.get((fd.fd or fd.select).upper(), {})
        varying = clauses.get("varying")
        if varying is not None or clauses.get("mode_v"):
            # variable-length records: written at the DEPENDING ON item's length, framed as GnuCOBOL frames them
            if fd.organization != "SEQUENTIAL" or varying is None or varying["depending"] is None:
                fd.why = ("variable-length records without RECORD VARYING ... DEPENDING ON" if fd.organization ==
                          "SEQUENTIAL" else f"variable-length records, ORGANIZATION {fd.organization}")  # fmt: skip
                continue
            fd.varying = varying
            file_decls.append(f"    private DetFiles.DetFile {v};")
            fd.handle = (f"new DetFiles.VarSequential(files, {G.jstr(fd.dd)}, () -> datasets.path(dd(dds, "
                         f"{G.jstr(fd.dd)})), {storage}, 0, {varying['min'] or 1}, {varying['max'] or reclen})")  # fmt: skip
            file_inits.append(f"        {v} = {fd.handle};")
            continue
        file_decls.append(f"    private DetFiles.DetFile {v};")
        if fd.organization in ("SEQUENTIAL", "LINE"):
            fd.handle = (f"new DetFiles.Sequential(files, {G.jstr(fd.dd)}, () -> datasets.path(dd(dds, {G.jstr(fd.dd)})), "
                         f"{storage}, 0, {reclen})")  # fmt: skip
        elif fd.organization == "INDEXED":
            repo = repos.get(fd.select)
            if repo is None and estate and fd.dd in estate:
                repo = estate[fd.dd]  # the DD's dataset's repository elsewhere in the estate
                inferred.append(f"{fd.select} (DD {fd.dd}) -> {repo}: the dataset other jobs bind {fd.dd} to")
            if repo is None or fd.key_item is None:
                fd.why = (
                    "no repository for this file in the generated project" if repo is None else "no RECORD KEY item"
                )
                if _record_io(proc, fd, records):
                    continue
                # opened and closed, never read or written: its OPEN / CLOSE statuses are all the program sees
                fd.handle = f"new DetFiles.Unbound(files, {G.jstr(fd.dd)})"
                inferred.append(f"{fd.select}: no store bound; the program only opens and closes it")
                file_inits.append(f"        {v} = {fd.handle};")
                continue
            repo_cls = repo[0].upper() + repo[1:]
            entity = repo_cls[: -len("Repository")]
            fd.entity, fd.repository = entity, repo
            ctor_repos.append((repo_cls, repo))
            fd.handle = (f"new DetFiles.Indexed<{entity}>(files, {G.jstr(fd.dd)}, {storage}, 0, {reclen}, "
                         f"{fd.key_item.offset}, {fd.key_item.size}, {repo}::findAll, e -> e.toRecord(CS), "
                         f"b -> {entity}.fromRecord(b, CS), {repo}::save, CS)"
                + gen.find_by_id(entity, repo))  # fmt: skip
        else:
            fd.why = f"ORGANIZATION {fd.organization}"
            continue
        file_inits.append(f"        {v} = {fd.handle};")

    # paragraphs
    para_code = []
    for i, p in enumerate(proc.paragraphs):
        gen.cur = i
        body = [x.replace("__PACKAGE__", package) for x in gen.paragraph(p, "        ")]
        if structured:
            para_code.append(
                f"    /** {p.name}. */\n    private void {gen.method(i)}() {{\n" + "\n".join(body) + "\n    }\n"
            )
        else:
            para_code.append(f"    /** {p.name}. */\n    private int p{i}() {{\n" + "\n".join(body) +
                             f"\n        return {i + 1};\n    }}\n")  # fmt: skip

    if gen.violations:  # a lifted item used through its bytes: translate again without lifting it
        raise G.LiftViolation(gen.violations)

    # a LINKed program's COMMAREA storage is its caller's: as long as the longest record a caller may pass (GenApp's
    # LGSTSQ declares 90 bytes, its callers pass their 99-byte error message, and the DTO fills all 99)
    if gen.cics is not None:
        dfh = next((r for r in records if r.section == "LINKAGE" and r.name == "DFHCOMMAREA"), None)
        if dfh is not None:
            classes = [x for x in dict.fromkeys([gen.cics.gp.contract, *gen.cics.gp.records.values()]) if x]
            longest = max([_dto_size(gen.cics.gp, c) for c in classes], default=0)
            sizes[id(roots[id(dfh)])] = max(sizes.get(id(roots[id(dfh)]), 0), longest)
    # fields (after the paragraphs: gen.ids is complete from the start; the constants come from the statements)
    storages = []
    seen = set()
    for rec in records:
        r = roots[id(rec)]
        if id(r) in seen or id(r) in gen.lifted:  # a lifted item is a typed field, not storage
            continue
        seen.add(id(r))
        img = L.image(r) if r.section != "FILE" else b" " * sizes[id(r)]
        img = img.ljust(sizes[id(r)], b"\x00" if r.section != "FILE" else b" ")
        storages.append((_storage_name(r), base64.b64encode(img).decode("ascii")))
    field_lines, inits = [], []
    lifted_decls: list[str] = []
    sync_methods = sync_code(gen, records, roots)
    for rec in records:
        if not any(id(it) in gen.lifted for it in rec.walk()):
            continue
        image = L.image(rec)
        for it in rec.walk():
            kind = gen.lifted.get(id(it))
            if kind is None:
                continue
            name = gen.ids[id(it)]
            img = image[it.offset : it.offset + it.size]
            if kind == "X":
                lifted_decls.append(f"    private String {name};  // {it.name} PIC {it.pic}")
                inits.append(f"        {name} = {G.jstr(img.decode('latin-1'))};")
            elif kind == "NUM":  # the VALUE's number (a numeric item lifted holds numbers only)
                value = L.decode_number(it, img)
                lifted_decls.append(f"    private BigDecimal {name};  // {it.name} PIC {it.pic} {it.usage}")
                inits.append(f'        {name} = new BigDecimal("{value}");')
            else:
                ivalue = int.from_bytes(img, "little" if it.usage == "COMP-5" else "big", signed=it.signed)
                lifted_decls.append(f"    private long {name};  // {it.name} PIC {it.pic} {it.usage}")
                inits.append(f"        {name} = {ivalue}L;")
    for rec in records:
        if id(rec) in gen.lifted:
            continue
        st = _storage_name(roots[id(rec)])
        for it in rec.walk():
            fid = gen.ids.get(id(it))
            if fid is None or it.category == "FLOAT" or it.usage in ("POINTER", "INDEX") or id(it) in gen.lifted:
                continue
            try:
                field_lines.append(f"        {fid} = {gen.factory(it, st, str(it.offset))};")
            except G.Untranslatable:
                continue
        for it in L.runtime_init(rec):
            fid = gen.ids.get(id(it))
            if fid:
                inits.append(f"        Cobol.moveFigurative(Figurative.ZEROS, {fid}, CS);")

    linkage = [r for r in records if r.section == "LINKAGE" and r.level == 1]
    extra_imports: list[str] = []
    using = [u for u in proc.using if u != "BY"]
    parm_code = []
    if using:
        u0 = next((r for r in linkage if r.name == using[0]), None)
        if u0 is not None:
            st = _storage_name(roots[id(u0)])
            # the PARM: a halfword length and the text (z/OS: the job step's PARM= string)
            parm_code = [
                '        byte[] parmText = (parm == null ? "" : parm).getBytes(CS);',
                f"        {st}.bytes[0] = (byte) (parmText.length >> 8);",
                f"        {st}.bytes[1] = (byte) parmText.length;",
                f"        System.arraycopy(parmText, 0, {st}.bytes, 2, Math.min(parmText.length, {st}.bytes.length - 2));",
            ]

    # the CALL entry: the stub's handleCall signature -- a CobolRef<String> the text of a PIC X USING item, a
    # contract DTO (the call forge's type for a group USING item, IBM DBB EPSNBRVL's EPS-NUMBER-VALIDATION) carried
    # in and out of the item's storage by the COMMAREA codec a LINK uses (det/cics.py): BY REFERENCE, the caller's
    # object is filled with what the program left
    call_entry: list[str] = []
    call_codecs: list[str] = []
    hc = re.search(r"public int handleCall\(([^)]*)\)", stub)
    if hc:
        params = [p.strip() for p in hc.group(1).split(",") if p.strip()]
        signature = ", ".join(f"{p.rsplit(' ', 1)[0]} arg{k + 1}" for k, p in enumerate(params))
        body_in: list[str] | None = None
        ins: list[str] = []
        body_out: list[str] = []
        for k, prm in enumerate(params):
            typ, _ = prm.rsplit(" ", 1)
            name = f"arg{k + 1}"  # the stub's own names may be a field's (LS-DATE -> lsDate): only the type matters
            item = next((r for r in linkage if k < len(using) and r.name == using[k]), None)
            if item is None:
                break
            f = gen.ids[id(item)]
            if typ == "CobolRef<String>":
                ins.append(f'        Cobol.move({name}.get() == null ? "" : {name}.get(), {f}, CS);')
                body_out.append(f"        {name}.set(Cobol.text({f}, CS));")
                continue
            if project is None or not re.fullmatch(r"[A-Z]\w*", typ):
                break
            try:
                cls = gen.codec_for(typ)
            except G.Untranslatable:
                break
            ins.append(f"        in_{cls}({name}, {f}.storage(), {f}.offset());")
            body_out.append(f"        fill_{cls}({name}, {f}.storage(), {f}.offset());")
        else:
            body_in = ins

        if body_in is None:
            call_entry = [
                f"    public int handleCall({signature}) {{",
                '        throw new Hole("the CALL entry\'s parameters are not CobolRef<String>");',
                "    }",
                "",
            ]
        else:
            call_entry = [f"    public int handleCall({signature}) {{", *body_in,
                          "        try {", f"            {'runAll()' if gen.structured else f'perform(0, {len(proc.paragraphs) - 1})'};",
                          "        } catch (Goback g) {", "            // GOBACK", "        }", *body_out,
                          f"        return Cobol.num({gen.ids[id(rc)]}, CS).intValue();", "    }", ""]  # fmt: skip
        if "CobolRef" in hc.group(1):
            imports.setdefault("CobolRef", f"{package}.call.CobolRef")
            extra_imports.append(imports["CobolRef"])

    if gen.dto_codecs is not None and gen.dto_codecs is not gen.cics:
        for code in gen.dto_codecs.codecs.values():
            call_codecs += code
        if gen.dto_codecs.codecs:
            extra_imports.append(f"{package}.dto.contract.*")
    if providers:
        ctor_repos += providers
        extra_imports.append("org.springframework.beans.factory.ObjectProvider")
        # CobolRef only where a CALL passes text: a callee taking DTOs only has no `call` package in the estate
        if any(not ts or "CobolRef<String>" in ts for ts in (gen.callee_types.get(p, []) for p in gen.callees)):
            extra_imports.append(f"{package}.call.CobolRef")
    if not is_cics and any(gen.id_methods.values()):
        extra_imports.append(f"{package}.entity.vsam.*")  # an entity's composite id class, for findById
    cics_members: list[str] = []
    cics_entry: list[str] = []
    if is_cics:
        if gen.cics is None:
            raise ValueError("a CICS program has no CICS translator")
        cics_members, cics_entry = _cics_parts(gen, records, roots, proc, stub)
        inferred += gen.cics.gp.inferred
        ctor_repos += list(gen.cics.repos.items())
        # the codecs added constants: none (they use their own literals)

    if any(f.sort for f in prog.files.values()):
        extra_imports.append(f"{package}.cobolrt.Sort")
    if gen.sql is not None:  # the generated Db2 repositories the statements run on
        ctor_repos += [(c, f) for c, f in gen.sql.repos.items()]
        extra_imports.append(f"{package}.cobolrt.sql.DetSql")
    consts = [f'    private static final BigDecimal {n} = new BigDecimal("{v}");' for v, n in gen.consts.items()]
    n_para = len(proc.paragraphs)
    pkg = package
    imp = sorted({imports.get(c, f"{package}.repository.vsam.{c}") for c, _ in ctor_repos if c.endswith("Repository")} |
                 {imports.get(f.entity, f"{package}.entity.vsam.{f.entity}")
                  for f in prog.files.values() if f.entity})  # fmt: skip
    ctor_params = ", ".join(
        [f"{c} {f}" for c, f in dict.fromkeys(ctor_repos)]
        + (["DatasetResolver datasets", "CobolFiles files", "MainframeClock clock"] if batch else [])
    )
    dispatcher = [
        "    /** The active PERFORMs' last paragraphs, outermost first. */",
        "    private int[] performThru = new int[64];",
        "    private int performDepth = 0;",
        "",
        "    /** Control reached the end of an outer active PERFORM's range: that PERFORM returns (`depth`). */",
        "    private static final class PerformExit extends RuntimeException {",
        "        private static final long serialVersionUID = 1L;",
        "        final int depth;",
        "",
        "        PerformExit(int depth) {",
        "            super(null, null, false, false);",
        "            this.depth = depth;",
        "        }",
        "    }",
        "",
        "    /** PERFORM from THRU thru. When control falls off the end of a paragraph, the innermost active PERFORM",
        "     *  whose range ends there returns -- this one, or an outer one a GO TO reached the end of, abandoning",
        "     *  the PERFORMs inside it (GnuCOBOL, as IBM: test_det_programs.py, GOTOOUT). */",
        "    private void perform(int from, int thru) {",
        "        int mine = performDepth;",
        "        if (mine == performThru.length) {",
        "            performThru = java.util.Arrays.copyOf(performThru, mine * 2);",
        "        }",
        "        performThru[performDepth++] = thru;",
        "        try {",
        "            int i = from;",
        "            while (true) {",
        "                int next = run(i);",
        "                boolean jumped = (next & GOTO) != 0;",
        "                next &= ~GOTO;",
        "                if (!jumped) {",
        "                    if (i == thru) {",
        "                        return;",
        "                    }",
        "                    for (int d = mine - 1; d >= 0; d--) {",
        "                        if (performThru[d] == i) {",
        "                            throw new PerformExit(d);",
        "                        }",
        "                    }",
        "                }",
        f"                if (next >= {n_para}) {{",
        "                    throw new Goback();",
        "                }",
        "                i = next;",
        "            }",
        "        } catch (PerformExit e) {",
        "            if (e.depth != mine) {",
        "                throw e;",
        "            }",
        "        } finally {",
        "            performDepth = mine;",
        "        }",
        "    }",
        "",
        "    private int run(int i) {",
        "        switch (i) {",
        *[f"            case {i}: return p{i}();" for i in range(n_para)],
        '            default: throw new IllegalStateException("paragraph " + i);',
        "        }",
        "    }",
        "",
    ]
    out = [
        # a comment only: it declares the file a deterministic port, which GitGalaxy's aperture admits to a scan
        f"{DET_PORT_MARKER} COBOL {prog.name} ({program.name}), translated by rule, statement for statement",
        f"package {pkg}.service;",
        "",
        *(
            [
                f"import {pkg}.batch.CobolAbend;",
                f"import {pkg}.batch.CobolFiles;",
                f"import {pkg}.batch.DatasetResolver;",
                f"import {pkg}.batch.Dd;",
                f"import {pkg}.batch.MainframeClock;",
                f"import {pkg}.batch.Sysout;",
                f"import {pkg}.cobolrt.batch.DetFiles;",
            ]
            if batch
            else [f"import {pkg}.cobolrt.standalone.CobolAbend;", f"import {pkg}.cobolrt.standalone.Sysout;"]
        ),
        f"import {pkg}.cobolrt.Cobol;",
        f"import {pkg}.cobolrt.Field;",
        f"import {pkg}.cobolrt.Figurative;",
        f"import {pkg}.cobolrt.Funcs;",
        f"import {pkg}.cobolrt.Hole;",
        f"import {pkg}.cobolrt.Storage;",
        f"import {pkg}.entity.vsam.CobolRecords;",
        *(
            [
                f"import {pkg}.cics.CicsTask;",
                f"import {pkg}.cobolrt.cics.DetCics;",
                f"import {pkg}.dto.screen.*;",
                f"import {pkg}.dto.contract.*;",
                f"import {pkg}.entity.vsam.*;",
                f"import {pkg}.repository.vsam.*;",
            ]
            if is_cics
            else []
        ),
        *[f"import {i};" for i in sorted(set(imp) | set(extra_imports))],
        "import java.math.BigDecimal;",
        "import java.nio.charset.Charset;",
        "import java.util.Base64;",
        "import java.util.List;",
        "import org.springframework.stereotype.Service;",
        "",
        "/**",
        f" * {prog.name}: a deterministic port (gitgalaxy/tools/cobol_to_java/det). Storage is the program's own bytes;",
        " * each statement is the runtime's (cobolrt) rule for it; untranslated statements throw Hole.",
        f" * Statements: {gen.stats['statements']}, translated {gen.stats['translated']}, holes {len(gen.stats['holes'])}.",
        *[f" * Inferred: {x}." for x in inferred],
        " */",
        "@Service",
        f"public class {service} {{",
        "",
        "    private static final Charset CS = CobolRecords.charset();",
        "    private static final int GOTO = 1 << 20;",
        *consts,
        "",
        # (a string constant holds at most 65535 bytes: a large image is joined from pieces at class load; the
        # pieces sit one per line so no line outgrows a reader's or a scanner's line limit)
        *[
            f'    private static final byte[] IMAGE_{n} = Base64.getDecoder().decode(String.join("",\n            '
            + ",\n            ".join(f'"{b[i : i + IMAGE_PIECE]}"' for i in range(0, max(len(b), 1), IMAGE_PIECE))
            + "));"
            for n, b in storages
        ],
        *[f"    private final Storage {n} = new Storage(IMAGE_{n}.length);" for n, _ in storages],
        "",
        # each item declared and bound to its storage in one line, in record order (the storages are declared above)
        *[f"    private final Field {ln.strip()}" for ln in dict.fromkeys(field_lines)],
        *lifted_decls,
        *sync_methods,
        "",
        *[ln for code in gen.id_methods.values() if code for ln in code],
        *cics_members,
        *call_codecs,
        *file_decls,
        "",
        *[f"    private final {c} {f};" for c, f in dict.fromkeys(ctor_repos)],
        *(
            [
                "    private final DatasetResolver datasets;",
                "    private final CobolFiles files;",
                "    private final MainframeClock clock;",
            ]
            if batch
            else []
        ),
        "",
        f"    public {service}({ctor_params}) {{",
        *[f"        this.{f} = {f};" for _, f in dict.fromkeys(ctor_repos)],
        *(
            ["        this.datasets = datasets;", "        this.files = files;", "        this.clock = clock;"]
            if batch
            else []
        ),
        # a CALLed program's WORKING-STORAGE is set once and keeps its values from call to call
        *(["        initialState();"] if hc else []),
        "    }",
        "",
    ]
    out += [
        "    /** WORKING-STORAGE (and every storage) as its VALUE clauses set it: each entry point starts from here. */",
        "    private void initialState() {",
        *[f"        System.arraycopy(IMAGE_{n}, 0, {n}.bytes, 0, IMAGE_{n}.length);" for n, _ in storages],
        *inits,
        "    }",
        "",
    ]
    out += [
        "    /** The program run on its own (no JCL step, no CICS task, no caller): the PROCEDURE DIVISION from its",
        "     *  initial storage; RETURN-CODE. */",
        "    public int runProgram() {",
        "        initialState();",
        *([] if structured else ["        performDepth = 0;"]),
        "        try {",
        f"            {'runAll()' if structured else f'perform(0, {n_para - 1})'};",
        "        } catch (Goback g) {",
        "            // the program ended",
        "        }",
        f"        return Cobol.num({gen.ids[id(rc)]}, CS).intValue();",
        "    }",
        "",
        *call_entry,
        *cics_entry,
        "",
        "    /** GOBACK / STOP RUN. */",
        "    private static final class Goback extends RuntimeException {",
        "        private static final long serialVersionUID = 1L;",
        "",
        "        Goback() {",
        "            super(null, null, false, false);",
        "        }",
        "    }",
        "",
        *(
            [
                "    private static Dd dd(List<Dd> dds, String name) {",
                "        return dds.stream().filter(d -> name.equals(d.name())).findFirst().orElse(null);",
                "    }",
                "",
                "    /** The batch entry. */",
                "    public int runBatch(List<Dd> dds, String parm) {",
                *(["        DetSql.closeAll();  // a step's cursors are its own"] if gen.sql is not None else []),
                "        initialState();",
                *parm_code,
                *file_inits,
                "        try {",
                f"            {'runAll()' if structured else f'perform(0, {n_para - 1})'};",
                "        } catch (Goback g) {",
                "            // the program ended",
                "        }",
                f"        return Cobol.num({gen.ids[id(rc)]}, CS).intValue();",
                "    }",
                "",
            ]
            if batch
            else []
        ),
        *(
            dispatcher
            if not structured
            else [
                "    /** The PROCEDURE DIVISION: its paragraphs in order (each falls into the next). */",
                "    private void runAll() {",
                *[f"        {gen.method(k)}();" for k in range(n_para)],
                "    }",
                "",
            ]
        ),
        *para_code,
        *gen.cond_method_lines(),
        "}",
        "",
    ]
    stats = dict(gen.stats)
    stats["program"] = prog.name
    stats["inferred"] = inferred
    java = drop_unused_fields("\n".join(out))
    return Result(with_trunc(java, trunc_std(program, options), numproc_pfd(program, options)), service, stats)


def _record_io(proc: S.Procedure, fd: G.FileDef, records: list) -> bool:
    """Whether any READ / WRITE / REWRITE / START / DELETE touches the file (by its SELECT name or its records)."""
    names = {r.name for r in records if r.section == "FILE" and r.fd == fd.fd}
    for p in proc.paragraphs:
        for s in S.walk(p.body):
            if s.kind in ("READ", "START") and s.data.get("file") == fd.select:
                return True
            if s.kind in ("WRITE", "REWRITE") and s.data["record"].name in names:
                return True
            if s.kind == "HOLE" and re.match(rf"(?i)\s*DELETE\s+{re.escape(fd.select)}\b", s.text):
                return True
    return False


def sync_code(gen: G.Gen, records: list, roots: dict) -> list[str]:
    """pack_<group>() / unpack_<group>() for every group whose bytes a statement uses while items in it are typed:
    pack writes the typed fields into the bytes (and returns the group's field), unpack reads them back."""
    owner = {id(x): rec for rec in records for x in rec.walk()}
    out: list[str] = []
    for gid, g in gen.synced.items():
        inside = [x for x in g.walk() if id(x) in gen.lifted]
        if not inside:
            continue
        fid = gen.ids[gid]
        st = _storage_name(roots[id(owner[gid])])
        pack, unpack = [], []
        for x in inside:
            name, f = gen.ids[id(x)], gen.factory(x, st, str(x.offset))
            kind = gen.lifted[id(x)]
            if kind == "X":
                pack.append(f"        Cobol.putText({f}, {name}, CS);")
                unpack.append(f"        {name} = Cobol.text({f}, CS);")
            elif kind == "BIN":
                pack.append(f"        Cobol.store({f}, BigDecimal.valueOf({name}), false, CS);")
                unpack.append(f"        {name} = Cobol.num({f}, CS).longValue();")
            else:  # NUM: packed for a read; never unpacked (a written group's numbers stay byte storage)
                pack.append(f"        Cobol.store({f}, {name}, false, CS);")
        out += [f"    /** {g.name}'s bytes, its typed fields written into them first. */",
                f"    private Field pack_{fid}() {{", *pack, f"        return {fid};", "    }", ""]  # fmt: skip
        if unpack:
            out += [f"    /** {g.name}'s typed fields, read back from its bytes (after a statement wrote them). */",
                    f"    private void unpack_{fid}() {{", *unpack, "    }", ""]  # fmt: skip
    return out


def _storage_name(rec: L.Item) -> str:
    return "s_" + G.jname(rec.name)


def _cics_parts(gen: G.Gen, records: list, roots: dict, proc: S.Procedure,
                stub: str) -> tuple[list[str], list[str]]:  # fmt: skip
    """A CICS program's members (task, handlers, file stores, COMMAREA codecs) and its entries: runTask, and the
    stub's handleTransaction / handleLink kept for their callers."""
    cx = gen.cics
    if cx is None:
        raise ValueError("a CICS program has no CICS translator")
    aid = next((r for r in records if r.name == "DFHAID"), None)
    aid_cases: list[str] = []
    if aid is not None:
        aid_cases.extend(
            f'            case "{c.name[3:]}" -> Cobol.move({gen.ids[id(c)]}, {gen.eib("EIBAID")}, CS);'
            for c in aid.children
            if c.name.startswith("DFH") and gen.ids.get(id(c))
        )
    dfhca = next((r for r in records if r.section == "LINKAGE" and r.name == "DFHCOMMAREA"), None)
    ca_in: list[str] = []
    if dfhca is not None:
        st = _storage_name(roots[id(dfhca)])
        for cls in [x for x in dict.fromkeys([cx.gp.contract, *cx.gp.records.values()]) if x]:
            # the DTO the task may carry: the program's contract, or a record's own DTO the harness passes
            if cls != cx.gp.contract and cls not in cx.codecs:
                continue
            try:
                cx.codec(cls)
            except C.CicsError as e:
                if cls != cx.gp.contract:
                    continue
                # the program's own COMMAREA cannot be carried (INQACCCU: data after a POINTER, register C9): the task
                # stops by name when it gets one, rather than run as if there were no COMMAREA
                kw = "if" if not ca_in else "} else if"
                ca_in += [f"        {kw} (ca instanceof {cls}) {{",
                          f"            throw new Hole({G.jstr(f'the COMMAREA {cls}: {e}')});"]  # fmt: skip
                continue
            kw = "if" if not ca_in else "} else if"
            ca_in += [f"        {kw} (ca instanceof {cls} x) {{", f"            in_{cls}(x, {st}, 0);",
                      f"            caBack = () -> fill_{cls}(x, {st}, 0);",
                      f"            calen = cx(task, {cx.gp.dto(cls).size});"]  # fmt: skip
        if ca_in:
            ca_in.append("        }")
        # #4181 follow-up: a det caller's LINK passes its COMMAREA's bytes (by reference): they are DFHCOMMAREA, every
        # byte -- the ones the contract DTO does not name too -- and what the program leaves there goes back to them
        ca_in += ["        byte[] raw = task.linkArea();",
                  "        if (raw != null) {",
                  f"            System.arraycopy(raw, 0, {st}.bytes, 0, Math.min(raw.length, {st}.bytes.length));",
                  "            Runnable typed = caBack;",
                  f"            caBack = () -> {{ typed.run(); System.arraycopy({st}.bytes, 0, raw, 0, "
                  f"Math.min(raw.length, {st}.bytes.length)); }};",
                  "        }"]  # fmt: skip
    store_cases = [f'            case "{n}" -> {e};' for n, e in cx.stores.items()]
    members = [
        "    private CicsTask task;",
        "    private final java.util.Map<String, Integer> handlers = new java.util.HashMap<>();",
        "    private final java.util.Map<String, DetCics.Store<?>> stores = new java.util.HashMap<>();",
        "    private final java.util.Map<String, byte[]> heldKey = new java.util.HashMap<>();",
        "    /** Writes the COMMAREA's bytes back into the object the task carries (a LINKed program's is its caller's). */",
        "    private Runnable caBack = () -> { };",
        "",
        '    @SuppressWarnings("unchecked")',
        "    private <E> DetCics.Store<E> store(String name) {",
        *(
            [
                "        return (DetCics.Store<E>) stores.computeIfAbsent(name, n -> switch (n) {",
                *store_cases,
                '            default -> throw new Hole("CICS file " + n + ": no store in the generated project");',
                "        });",
            ]
            if store_cases
            else [
                '        throw new Hole("CICS file " + name + ": the program names no file the generated project stores");'
            ]
        ),
        "    }",
        "",
        "    private static final java.util.Map<String, Integer> PARAGRAPHS = java.util.Map.ofEntries(",
        # a name declared twice (COACTVWC's 0000-MAIN-EXIT) cannot be referenced unqualified: its first one
        ",\n".join(
            f'            java.util.Map.entry("{n}", {i})'
            for n, i in {p.name: i for i, p in reversed(list(enumerate(proc.paragraphs)))}.items()
        ),
        "    );",
        "",
        "    private static int paragraph(String name) {",
        "        Integer i = PARAGRAPHS.get(name);",
        "        if (i == null) {",
        '            throw new IllegalStateException("no paragraph " + name);',
        "        }",
        "        return i;",
        "    }",
        "",
        "    /** A condition the command neither returned in RESP nor ignored: its HANDLE CONDITION label, or CICS's",
        "     *  default action -- an abend, to this program's HANDLE ABEND exit or ending the task. */",
        "    private int condition(String cond) {",
        "        Integer h = handlers.get(cond);",
        "        if (h != null) {",
        "            return h;",
        "        }",
        "        String label = task.abendOnCondition(cond);",
        "        if (label == null) {",
        "            throw new Goback();",
        "        }",
        "        return paragraph(label);",
        "    }",
        "",
        "    private static int cx(CicsTask task, int whole) {",
        "        return task.eibcalen() == null ? whole : task.eibcalen();",
        "    }",
        "",
    ]
    for code in cx.codecs.values():
        members += code
    entry = [
        "    /** One task of the program: the EIB and COMMAREA from the task, then the PROCEDURE DIVISION. */",
        "    public void runTask(CicsTask task) {",
        "        this.task = task;",
        *(["        DetSql.closeAll();  // a task's cursors are its own"] if gen.sql is not None else []),
        "        caBack = () -> { };",
        "        handlers.clear();",
        "        heldKey.clear();",
        "        initialState();",
        f"        Cobol.move(task.transid(), {gen.eib('EIBTRNID')}, CS);",
        "        java.time.LocalDateTime now = task.now();",
        f"        Cobol.store({gen.eib('EIBDATE')}, BigDecimal.valueOf((now.getYear() - 1900) * 1000L + now.getDayOfYear()), false, CS);",
        f"        Cobol.store({gen.eib('EIBTIME')}, BigDecimal.valueOf(now.getHour() * 10000L + now.getMinute() * 100L + now.getSecond()), false, CS);",
        '        switch (task.aid() == null ? "" : task.aid()) {',
        *aid_cases,
        "            default -> { }",
        "        }",
        "        Object ca = task.hasCommarea() ? task.commarea(Object.class) : null;",
        "        int calen = 0;",
        *ca_in,
        f"        Cobol.store({gen.eib('EIBCALEN')}, BigDecimal.valueOf(calen), false, CS);",
        "        try {",
        f"            {'runAll()' if gen.structured else f'perform(0, {len(proc.paragraphs) - 1})'};",
        "        } catch (Goback g) {",
        "            // RETURN / XCTL / an abend ended the program",
        "        }",
        "        if (!task.ended()) {",
        "            caBack.run();",
        "            task.returnTransid(null, null);  // a GOBACK is a RETURN",
        "        }",
        "    }",
        "",
    ]
    return members, entry + facades(stub)


def facades(stub: str) -> list[str]:
    """The stub's handleTransaction / handleLink, kept for their callers (#4465): each runs the program -- one task of
    it in the region, as the generator's own facades do (#4343: CicsTask.region(), region.transaction / region.linked,
    region.run(task, NAME, this::runTask)) -- and returns what the generated signature says: the COMMAREA its RETURN
    passes on (task.returned) for a transaction, the caller's own `request`, changed by reference, for a LINK.

    A stub whose entry has no region facade (a channel program's handler, #4343) is one no task runtime carries: the
    entry stops by name rather than return as if the program had run (#4342: no generated entry that does nothing)."""
    name = re.search(r'region\.run\(task, ("(?:[^"\\]|\\.)*"), this::runTask\)', stub)
    out: list[str] = []
    for meth in ("handleTransaction", "handleLink"):
        m = re.search(rf"public (\S+) {meth}\(([^)]*)\)", stub)
        if not m:
            continue
        ret, params = m.group(1), m.group(2)
        req = re.search(r"(\w+) request\b", params)
        arg = "request" if req else "null"
        if name is None:
            body = [f'        throw new UnsupportedOperationException("{meth}: the program has no task facade (a channel '
                    'program); it runs as runTask");']  # fmt: skip
        else:
            task = (f"region.transaction(transid, {arg})" if meth == "handleTransaction"
                    else f"region.linked({name.group(1)}, {arg})")  # fmt: skip
            body = ["        CicsTask.Region region = CicsTask.region();",
                    f"        CicsTask task = {task};",
                    f"        region.run(task, {name.group(1)}, this::runTask);"]  # fmt: skip
            if ret != "void":
                body.append("        return request;" if meth == "handleLink" and req and ret == req.group(1)
                            else f"        return task.returned({ret}.class);")  # fmt: skip
        out += [f"    public {ret} {meth}({params}) {{", *body, "    }", ""]
    return out
