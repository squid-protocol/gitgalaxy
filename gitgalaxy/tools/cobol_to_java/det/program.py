"""One COBOL program -> one Java service (a deterministic port), plus the runtime it runs on.

    translate(program, copy_dirs, stub, package) -> Result(java, stats)

`stub` is the generated service the port replaces: its class name, and -- for each SELECT -- the repository the
generator mapped the file to (the javadoc "... as BATCH SELECT <name> ..." over the method that uses it)."""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from pathlib import Path

from gitgalaxy.tools.cobol_to_java.det import expr as E
from gitgalaxy.tools.cobol_to_java.det import gen as G
from gitgalaxy.tools.cobol_to_java.det import layout as L
from gitgalaxy.tools.cobol_to_java.det import stmt as S
from gitgalaxy.tools.cobol_to_java.det.source import Line, program_lines

RUNTIME = Path(__file__).parent / "cobolrt"


@dataclass
class Result:
    java: str
    service: str  # the class name
    stats: dict


def runtime_files(package: str) -> dict[str, str]:
    """The runtime's sources, relative to the package directory (cobolrt/...), with the package filled in."""
    out = {}
    for f in sorted(RUNTIME.rglob("*.java")):
        out["cobolrt/" + f.relative_to(RUNTIME).as_posix()] = f.read_text(encoding="utf-8").replace(
            "__PACKAGE__", package)  # fmt: skip
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
        d = {"select": words[0].upper().rstrip("."), "organization": "SEQUENTIAL", "access": "SEQUENTIAL",
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


def translate(program: Path, copy_dirs: list[Path], stub: str, package: str,
              estate: dict[str, str] | None = None) -> Result:  # fmt: skip
    lines = program_lines(program, copy_dirs)
    records = L.parse(lines)
    # RETURN-CODE: the special register, S9(4) BINARY
    rc = L.Item(1, "GG-RETURN-CODE", "WORKING-STORAGE", pic="S9(4)", usage="BINARY")
    L.layout(rc)
    records.append(rc)
    proc = S.parse(lines)
    service = re.search(r"public class (\w+)", stub).group(1)
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

    gen = G.Gen(prog)
    repos = stub_files(stub)
    imports = stub_imports(stub)
    file_decls, file_inits, ctor_repos, inferred = [], [], [], []
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
        storage = _storage_name(roots[id(fd.record)])
        v = G.jname(fd.select)
        reclen = sizes[id(roots[id(fd.record)])]
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
                         f"b -> {entity}.fromRecord(b, CS), {repo}::save, CS)")  # fmt: skip
        else:
            fd.why = f"ORGANIZATION {fd.organization}"
            continue
        file_inits.append(f"        {v} = {fd.handle};")

    # paragraphs
    para_code = []
    for i, p in enumerate(proc.paragraphs):
        gen.cur = i
        body = [x.replace("__PACKAGE__", package) for x in gen.paragraph(p, "        ")]
        para_code.append(f"    /** {p.name}. */\n    private int p{i}() {{\n" + "\n".join(body) +
                         f"\n        return {i + 1};\n    }}\n")  # fmt: skip

    # fields (after the paragraphs: gen.ids is complete from the start; the constants come from the statements)
    storages = []
    seen = set()
    for rec in records:
        r = roots[id(rec)]
        if id(r) in seen:
            continue
        seen.add(id(r))
        img = L.image(r) if r.section != "FILE" else b" " * sizes[id(r)]
        img = img.ljust(sizes[id(r)], b"\x00" if r.section != "FILE" else b" ")
        storages.append((_storage_name(r), base64.b64encode(img).decode("ascii")))
    field_lines, inits = [], []
    for rec in records:
        st = _storage_name(roots[id(rec)])
        for it in rec.walk():
            fid = gen.ids.get(id(it))
            if fid is None or it.category == "FLOAT" or it.usage in ("POINTER", "INDEX"):
                continue
            try:
                field_lines.append(f"        {fid} = {gen.factory(it, st, str(it.offset))};")
            except G.Untranslatable:
                continue
        for it in L.runtime_init(rec):
            fid = gen.ids.get(id(it))
            if fid:
                inits.append(f"        Cobol.moveFigurative(Figurative.ZEROS, {fid}, CS);")
    declared = sorted({ln.split(" = ")[0].strip() for ln in field_lines})

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

    # the CALL entry: the stub's handleCall signature, each CobolRef<String> the text of a USING item
    call_entry: list[str] = []
    hc = re.search(r"public int handleCall\(([^)]*)\)", stub)
    if hc:
        params = [p.strip() for p in hc.group(1).split(",") if p.strip()]
        body_in, body_out = [], []
        for k, prm in enumerate(params):
            typ, name = prm.rsplit(" ", 1)
            item = next((r for r in linkage if k < len(using) and r.name == using[k]), None)
            if typ != "CobolRef<String>" or item is None:
                body_in = None
                break
            f = gen.ids[id(item)]
            body_in.append(f'        Cobol.move({name}.get() == null ? "" : {name}.get(), {f}, CS);')
            body_out.append(f"        {name}.set(Cobol.text({f}, CS));")
        if body_in is None:
            call_entry = [
                f"    public int handleCall({hc.group(1)}) {{",
                '        throw new Hole("the CALL entry\'s parameters are not CobolRef<String>");',
                "    }",
                "",
            ]
        else:
            call_entry = [f"    public int handleCall({hc.group(1)}) {{", *body_in,
                          "        try {", f"            perform(0, {len(proc.paragraphs) - 1});",
                          "        } catch (Goback g) {", "            // GOBACK", "        }", *body_out,
                          f"        return Cobol.num({gen.ids[id(rc)]}, CS).intValue();", "    }", ""]  # fmt: skip
        if "CobolRef" in hc.group(1):
            imports.setdefault("CobolRef", f"{package}.call.CobolRef")
            extra_imports.append(imports["CobolRef"])

    consts = [f'    private static final BigDecimal {n} = new BigDecimal("{v}");' for v, n in gen.consts.items()]
    n_para = len(proc.paragraphs)
    pkg = package
    imp = sorted({imports.get(c, f"{package}.repository.vsam.{c}") for c, _ in ctor_repos} |
                 {imports.get(f.entity, f"{package}.entity.vsam.{f.entity}")
                  for f in prog.files.values() if f.entity})  # fmt: skip
    chunks = [field_lines[i : i + 300] for i in range(0, len(field_lines), 300)] or [[]]
    out = [
        f"package {pkg}.service;",
        "",
        f"import {pkg}.batch.CobolAbend;",
        f"import {pkg}.batch.CobolFiles;",
        f"import {pkg}.batch.DatasetResolver;",
        f"import {pkg}.batch.Dd;",
        f"import {pkg}.batch.MainframeClock;",
        f"import {pkg}.batch.Sysout;",
        f"import {pkg}.cobolrt.Cobol;",
        f"import {pkg}.cobolrt.Field;",
        f"import {pkg}.cobolrt.Figurative;",
        f"import {pkg}.cobolrt.Funcs;",
        f"import {pkg}.cobolrt.Hole;",
        f"import {pkg}.cobolrt.Storage;",
        f"import {pkg}.cobolrt.batch.DetFiles;",
        f"import {pkg}.entity.vsam.CobolRecords;",
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
        *[f'    private static final byte[] IMAGE_{n} = Base64.getDecoder().decode("{b}");' for n, b in storages],
        *[f"    private final Storage {n} = new Storage(IMAGE_{n}.length);" for n, _ in storages],
        "",
        *[f"    private Field {d};" for d in declared],
        *file_decls,
        "",
        *[f"    private final {c} {f};" for c, f in dict.fromkeys(ctor_repos)],
        "    private final DatasetResolver datasets;",
        "    private final CobolFiles files;",
        "    private final MainframeClock clock;",
        "",
        f"    public {service}({''.join(f'{c} {f}, ' for c, f in dict.fromkeys(ctor_repos))}DatasetResolver datasets, "
        "CobolFiles files, MainframeClock clock) {",
        *[f"        this.{f} = {f};" for _, f in dict.fromkeys(ctor_repos)],
        "        this.datasets = datasets;",
        "        this.files = files;",
        "        this.clock = clock;",
        *[f"        fields{k}();" for k in range(len(chunks))],
        # a CALLed program's WORKING-STORAGE is set once and keeps its values from call to call
        *(
            [f"        System.arraycopy(IMAGE_{n}, 0, {n}.bytes, 0, IMAGE_{n}.length);" for n, _ in storages] + inits
            if hc
            else []
        ),
        "    }",
        "",
    ]
    for k, ch in enumerate(chunks):
        out += [f"    private void fields{k}() {{", *ch, "    }", ""]
    out += [
        f"    public void execute{service[: -len('Service')]}() {{",
        "        runBatch(List.of(), null);",
        "    }",
        "",
        *call_entry,
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
        "    private static Dd dd(List<Dd> dds, String name) {",
        "        return dds.stream().filter(d -> name.equals(d.name())).findFirst().orElse(null);",
        "    }",
        "",
        "    /** The batch entry. */",
        "    public int runBatch(List<Dd> dds, String parm) {",
        *[f"        System.arraycopy(IMAGE_{n}, 0, {n}.bytes, 0, IMAGE_{n}.length);" for n, _ in storages],
        *inits,
        *parm_code,
        *file_inits,
        "        try {",
        f"            perform(0, {n_para - 1});",
        "        } catch (Goback g) {",
        "            // the program ended",
        "        }",
        f"        return Cobol.num({gen.ids[id(rc)]}, CS).intValue();",
        "    }",
        "",
        "    /** PERFORM from THRU thru: returns when control falls off the end of `thru`. */",
        "    private void perform(int from, int thru) {",
        "        int i = from;",
        "        while (true) {",
        "            int next = run(i);",
        "            boolean jumped = (next & GOTO) != 0;",
        "            next &= ~GOTO;",
        "            if (i == thru && !jumped) {",
        "                return;",
        "            }",
        f"            if (next >= {n_para}) {{",
        "                throw new Goback();",
        "            }",
        "            i = next;",
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
        *para_code,
        "}",
        "",
    ]
    stats = dict(gen.stats)
    stats["program"] = prog.name
    stats["inferred"] = inferred
    return Result("\n".join(out), service, stats)


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


def _storage_name(rec: L.Item) -> str:
    return "s_" + G.jname(rec.name)
