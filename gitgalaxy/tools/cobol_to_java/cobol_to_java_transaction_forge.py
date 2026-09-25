#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: CICS transactions + COMMAREA / channels -> REST endpoints (#3615)
#
# PURPOSE:
# Builds a CICS program's REST controller from the engine's verified skeleton
# (06_skeleton, #3614) instead of the generic per-program controller:
#
#   - each CSD transaction that enters the program -> POST /transactions/<transid>
#   - a program other programs LINK / XCTL to        -> POST /link
#   - GET / PUT CONTAINER on a channel               -> POST /channel
#
# The request / response body is the COMMAREA DTO, generated from the layout the
# engine resolved (GalaxyIR.program_interfaces): the record the program's
# resolved callers pass it, else its own fixed-length DFHCOMMAREA. Container
# records become the fields of a channel-in / channel-out DTO. Every class,
# endpoint and field names the fact it came from (file, line, offset, bytes),
# and the field-testing status of that fact's ledger field. Where the engine
# resolved no layout the endpoint takes no body, and a TODO states why.
# Nothing is guessed from names.
# ==============================================================================
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gitgalaxy.tools.cobol_to_java.cobol_to_java_common import (
    ClassNames,
    container_var,
    java_identifier,
    java_type,
    status_text,
)
from gitgalaxy.tools.cobol_to_java.cobol_to_java_names import java_class_base, java_url_segment
from gitgalaxy.tools.cobol_to_java.cobol_to_java_spring_forge import render_dto_class
from gitgalaxy.tools.cobol_to_java.java_target import JavaTarget

# The records programs exchange -- COMMAREA, channel containers (#3615), CALL USING parameters (#3616).
DTO_SUBPACKAGE = "dto.contract"


def _field_lines(layout: dict) -> tuple[list[str], bool]:
    """The DTO field lines for a record layout: one per named elementary item, with its
    PIC, offset and width; FILLERs are skipped (their bytes stay in the offsets)."""
    lines: list[str] = []
    seen: dict[str, int] = {}
    requires_list = False
    for fld in layout.get("fields", []):
        name = fld.get("name")
        if not name or name.upper() == "FILLER":
            continue
        base = java_identifier(name)
        seen[base] = seen.get(base, 0) + 1
        var = base if seen[base] == 1 else f"{base}{seen[base]}"
        jtype = java_type(fld)
        pic = f"PIC {fld['pic']}" if fld.get("pic") else (fld.get("usage") or "no PIC")
        usage = f" {fld['usage']}" if fld.get("usage") and fld.get("pic") else ""
        lines.append(f"    // {name}: {pic}{usage}, offset {fld['offset']}, {fld['bytes']} bytes ({fld['file']})")
        if fld.get("occurs"):
            requires_list = True
            lines.append(f"    // OCCURS {fld['occurs']} TIMES")
            lines.append(f"    private List<{jtype}> {var};\n")
        else:
            lines.append(f"    private {jtype} {var};\n")
    return lines, requires_list


@dataclass
class Dto:
    name: str
    javadoc: list[str]  # the record: its first line, then its notes
    body: list[str]
    requires_list: bool
    uses: list[str] = field(default_factory=list)  # one line per program that receives it
    methods: Any = None  # (is_record) -> method lines, e.g. a composite COMMAREA's fromPrefix (#3655)

    def doc(self) -> list[str]:
        return self.javadoc[:1] + self.uses + self.javadoc[1:]


@dataclass
class CicsProgram:
    """One CICS program's REST surface, from its skeleton."""

    key: str
    cls: str
    path: str
    program_ids: list[str]
    transactions: list[dict] = field(default_factory=list)  # {transid, segment, method, definitions}
    links: list[dict] = field(default_factory=list)  # incoming LINK / XCTL sites: {caller, line, verb, via}
    commarea: dict | None = None
    commarea_dto: str | None = None
    commarea_gap: str | None = None
    segment_dtos: list[str] = field(default_factory=list)  # an unpacked COMMAREA's parts, in offset order (#3655)
    channel_in: str | None = None
    channel_out: str | None = None
    containers: list[dict] = field(default_factory=list)
    status: dict[str, str] = field(default_factory=dict)  # section -> field-testing text


def incoming_links(skeleton: dict) -> list[dict]:
    """Every LINK / XCTL that reaches this program: a resolved COMMAREA contract, or a
    `navigation` row -- which includes the data-driven sites whose candidates name it (#3616)."""
    sections = skeleton.get("sections", {})
    path = skeleton["program"]["file"]
    rows: dict[tuple, dict] = {}
    for r in (sections.get("commarea_contracts") or {}).get("facts", []):
        if r.get("callee") == path and r.get("verb") in ("LINK", "XCTL"):
            rows.setdefault((r["caller"], r["line"]), {"caller": r["caller"], "line": r["line"], "verb": r["verb"],
                                                       "via": "static"})  # fmt: skip
    for r in (sections.get("navigation") or {}).get("facts", []):
        if r.get("to") == path and r.get("verb") in ("LINK", "XCTL"):
            rows.setdefault((r["from"], r["line"]), {"caller": r["from"], "line": r["line"], "verb": r["verb"],
                                                     "via": r.get("via")})  # fmt: skip
    return [rows[k] for k in sorted(rows)]


def is_cics_program(skeleton: dict) -> bool:
    """A program the engine saw CICS evidence for: an entry transaction, an EXEC CICS resource,
    a COMMAREA contract, a container, or a LINK / XCTL reaching it."""
    sections = skeleton.get("sections", {})
    interface = (sections.get("interface") or {}).get("facts") or {}
    return bool(
        (sections.get("entry_transactions") or {}).get("facts")
        or (sections.get("cics_resources") or {}).get("facts")
        or (sections.get("commarea_contracts") or {}).get("facts")
        or interface.get("containers")
        or incoming_links(skeleton)
    )


def _segment(transid: str) -> str:
    """A URL / method-safe form of a transaction id: `CA00` -> `CA00`, `A$1` -> `Ax241`."""
    return re.sub(r"[^A-Za-z0-9]", lambda m: f"x{ord(m.group()):02x}", transid)


class CicsForge:
    """Plans every CICS program first, so one DTO class serves every program passing the same layout."""

    def __init__(
        self,
        skeletons: dict[str, dict],
        package: str,
        target: JavaTarget | None = None,
        names: ClassNames | None = None,
    ) -> None:
        self.package = package
        self.names = names if names is not None else ClassNames()  # shared with the other forges
        self.target = target or JavaTarget()
        self.program_files = {sk["program"]["file"] for sk in skeletons.values()}
        self._file_cls = {sk["program"]["file"]: java_class_base(key) for key, sk in skeletons.items()}
        self.dtos: dict[str, Dto] = {}
        self._by_signature: dict[tuple, str] = {}
        self.programs = {key: self._plan(key, sk) for key, sk in sorted(skeletons.items()) if is_cics_program(sk)}

    # ---- DTOs ---------------------------------------------------------------
    def _dto_for(self, record: str, file: str, layout: dict, owner_cls: str, javadoc: list[str], use: str = "") -> str:
        signature = (record, file, tuple((f.get("name"), f.get("pic"), f.get("usage"), f.get("offset"), f.get("bytes"),
                                          f.get("occurs")) for f in layout.get("fields", [])))  # fmt: skip
        if signature in self._by_signature:
            name = self._by_signature[signature]
            if use:
                self.dtos[name].uses.append(use)
            return name
        shared = file not in self.program_files and not layout.get("extended") and record.upper() != "DFHCOMMAREA"
        # A copybook record is named alone; a program's own record after the program declaring it
        # (MENU's WS-COMM -> MenuWsComm, whichever program receives it); an extended copy after its owner.
        declarer = self._file_cls.get(file) if not layout.get("extended") else None
        name = java_class_base(record) if shared else (declarer or owner_cls) + java_class_base(record)
        base, n = name, 1
        while name in self.dtos or name in self.names:
            n += 1
            name = f"{base}{n}"
        self.names.claim(name)
        body, requires_list = _field_lines(layout)
        self.dtos[name] = Dto(name, javadoc, body, requires_list, [use] if use else [])
        self._by_signature[signature] = name
        return name

    def _record_doc(self, record: str, file: str, layout: dict, status: str) -> list[str]:
        width = f"{layout['bytes']} bytes" if layout.get("bytes") is not None else "width unknown"
        doc = [f"COBOL record {record} ({file}), {width}, from GitGalaxy's verified skeleton."]
        if layout.get("extended"):
            doc.append("The program continues this copied record past its COPY: the layout is the program's own.")
        if layout.get("unexpanded"):
            doc.append(f"TODO: COPY members not found in the repository: {', '.join(layout['unexpanded'])}.")
        named = sum(f.get("bytes") or 0 for f in layout.get("fields", []))
        if layout.get("bytes") is not None and named != layout["bytes"]:
            doc.append("Fields inside an OCCURS group appear once; the offsets and the width count every occurrence.")
        doc.append(f"Record fields field testing: {status}.")
        return doc

    def _unpacked_commarea(self, prog: CicsProgram, commarea: dict, status: str) -> str:
        """#3655: the COMMAREA as the program itself reads it -- a DTO per unpacked record,
        and, for two or more, a composite whose fields are those DTOs in offset order, with
        `fromPrefix(first)` for callers that pass only the leading record."""
        cls = prog.cls
        for sg in commarea["segments"]:
            doc = self._record_doc(sg["record"], sg["file"], sg["layout"], status)
            end = sg["offset"] + sg["bytes"] - 1
            use = (f"Bytes {sg['offset']}-{end} of the COMMAREA {cls} reads: MOVE DFHCOMMAREA"
                   f"{'(' + sg['refmod'] + ')' if sg.get('refmod') else ''} at {prog.path}:{sg['line']}.")  # fmt: skip
            prog.segment_dtos.append(self._dto_for(sg["record"], sg["file"], sg["layout"], cls, doc, use))
        if len(prog.segment_dtos) == 1:
            return prog.segment_dtos[0]
        name = f"{cls}Commarea"
        base, n = name, 1
        while name in self.dtos or name in self.names:
            n += 1
            name = f"{base}{n}"
        self.names.claim(name)
        body: list[str] = []
        fields: list[str] = []
        for sg, dto in zip(commarea["segments"], prog.segment_dtos):
            var = java_identifier(sg["record"])
            fields.append(var)
            body.append(f"    // DFHCOMMAREA({sg.get('refmod') or 'whole'}) at line {sg['line']}: offset {sg['offset']}, "
                        f"{sg['bytes']} bytes -> {sg['record']} ({sg['file']})")  # fmt: skip
            body.append(f"    private {dto} {var};\n")
        first_type, first = prog.segment_dtos[0], fields[0]

        def methods(is_record: bool) -> list[str]:
            head = [f"    /** A caller that passes only {commarea['segments'][0]['record']} (the leading "
                    f"{commarea['segments'][0]['bytes']} bytes): the rest is not supplied. */",
                    f"    public static {name} fromPrefix({first_type} {first}) {{"]  # fmt: skip
            if is_record:
                args = ", ".join([first, *["null"] * (len(fields) - 1)])
                return [*head, f"        return new {name}({args});", "    }"]
            return [*head, f"        {name} commarea = new {name}();", f"        commarea.{first} = {first};",
                    "        return commarea;", "    }"]  # fmt: skip

        lines = ", ".join(f"{sg['line']}" for sg in commarea["segments"])
        doc = [f"The COMMAREA {cls} reads, as {prog.path} unpacks DFHCOMMAREA at lines {lines}: "
               f"{' + '.join(sg['record'] for sg in commarea['segments'])} = {commarea['bytes']} bytes.",
               f"Record fields field testing: {status}."]  # fmt: skip
        self.dtos[name] = Dto(name, doc, body, False, methods=methods)
        return name

    # ---- planning -----------------------------------------------------------
    def _plan(self, key: str, sk: dict) -> CicsProgram:
        sections = sk.get("sections", {})
        cls = java_class_base(key)
        path = sk["program"]["file"]
        prog = CicsProgram(key, cls, path, list(sk["program"].get("program_ids", [])))
        prog.status = {name: status_text(sec) for name, sec in sections.items()}

        by_transid: dict[str, list[dict]] = {}
        for row in (sections.get("entry_transactions") or {}).get("facts", []):
            if row.get("transid"):
                by_transid.setdefault(row["transid"], []).append(row)
        used: set[str] = set()
        for transid in sorted(by_transid):
            seg = _segment(transid)
            while seg in used:
                seg += "_"
            used.add(seg)
            prog.transactions.append({"transid": transid, "segment": seg, "definitions": by_transid[transid]})

        prog.links = incoming_links(sk)

        interface = (sections.get("interface") or {}).get("facts") or {}
        record_status = prog.status.get("interface", "untested")
        commarea = interface.get("commarea")
        if commarea and commarea.get("basis") == "unpack":
            prog.commarea = commarea
            prog.commarea_dto = self._unpacked_commarea(prog, commarea, record_status)
        elif commarea:
            prog.commarea = commarea
            doc = self._record_doc(commarea["record"], commarea["file"], commarea, record_status)
            if commarea.get("basis") == "caller_record":
                sites = ", ".join(f"{s['verb']} at {s['caller']}:{s['line']}" for s in commarea.get("sources", []))
                use = f"The COMMAREA {cls} receives, as passed by {sites}."
            else:
                use = f"The DFHCOMMAREA {cls} declares in its LINKAGE SECTION."
            prog.commarea_dto = self._dto_for(commarea["record"], commarea["file"], commarea, cls, doc, use)
        else:
            prog.commarea_gap = interface.get("commarea_gap")

        prog.containers = list(interface.get("containers", []))
        for direction in ("in", "out"):
            items = [c for c in prog.containers if c["direction"] == direction]
            if not items:
                continue
            body: list[str] = []
            seen: dict[str, int] = {}
            for c in items:
                if c.get("layout"):
                    doc = self._record_doc(c["record"], path, c["layout"], record_status)
                    ftype = self._dto_for(c["record"], path, c["layout"], cls, doc)
                else:
                    ftype = "String"
                var = container_var(c["container"])
                if var in seen:
                    continue  # the same container read (or written) twice: one field
                seen[var] = 1
                where = f"{c['verb']} CONTAINER({c['container']}) at line {c['line']}"
                chan = f" on channel {c['channel']}" if c.get("channel") else " on the current channel"
                rec = f", {'INTO' if direction == 'in' else 'FROM'} {c['record']}" if c.get("record") else ""
                body.append(f"    // {where}{chan}{rec}")
                if ftype == "String" and c.get("record"):
                    body.append(f"    // TODO: the layout of {c['record']} was not found; carried as text.")
                body.append(f"    private {ftype} {var};\n")
            name = self.names.claim(f"{cls}Channel{'In' if direction == 'in' else 'Out'}")
            doc = [f"The containers {cls} {'reads' if direction == 'in' else 'writes'} (CICS resources field testing: "
                   f"{prog.status.get('cics_resources', 'untested')})."]  # fmt: skip
            self.dtos[name] = Dto(name, doc, body, False)
            if direction == "in":
                prog.channel_in = name
            else:
                prog.channel_out = name
        return prog

    # ---- Java ---------------------------------------------------------------
    def dto_sources(self) -> dict[str, str]:
        """DTO class name -> Java source (package <pkg>.dto.contract)."""
        return {
            name: render_dto_class(
                f"{self.package}.{DTO_SUBPACKAGE}",
                name,
                d.body,
                d.requires_list,
                self.target,
                javadoc=d.doc(),
                methods=d.methods,
            )
            for name, d in sorted(self.dtos.items())
        }

    def _body(self, prog: CicsProgram) -> tuple[str | None, str | None]:
        """(request type, response type) of a transaction / link endpoint."""
        if prog.commarea_dto:
            return prog.commarea_dto, prog.commarea_dto
        return None, None

    def link_types(self, prog: CicsProgram) -> tuple[str | None, str | None]:
        """(request, response) of the program's handleLink: its COMMAREA, else its channel."""
        req, resp = self._body(prog)
        if not req and prog.channel_in:
            req, resp = prog.channel_in, prog.channel_out
        return req, resp

    @staticmethod
    def has_link_handler(prog: CicsProgram) -> bool:
        return bool(prog.links or not prog.transactions)

    def controller(self, prog: CicsProgram) -> str:
        t, pkg, cls = self.target, self.package, prog.cls
        svc = cls[0].lower() + cls[1:] + "Service"
        imports = {f"{pkg}.service.{cls}Service"}
        imports |= {f"{pkg}.{DTO_SUBPACKAGE}.{n}" for n in (prog.commarea_dto, prog.channel_in, prog.channel_out) if n}
        java = [f"package {pkg}.controller;\n", "import org.springframework.web.bind.annotation.*;",
                "import org.springframework.http.ResponseEntity;"]  # fmt: skip
        if t.lombok:
            java.append("import lombok.RequiredArgsConstructor;")
        java += [f"import {i};" for i in sorted(imports)]
        java.append("")
        java.append("/**")
        java.append(f" * CICS program {', '.join(prog.program_ids) or cls} ({prog.path}), generated from GitGalaxy's")
        java.append(" * verified skeleton (06_skeleton). Each endpoint names the fact it came from.")
        if prog.commarea:
            c = prog.commarea
            java.append(f" * COMMAREA: {c['record']} ({c['file']}, {c['bytes']} bytes) -> {prog.commarea_dto}.")
            for alt in c.get("alternatives", []):
                sites = ", ".join(f"{s['caller']}:{s['line']}" for s in alt["sources"])
                java.append(
                    f" * TODO: callers also pass {alt['record']} ({alt['file']}, {alt['bytes']} bytes) at {sites}."
                )
        elif prog.channel_in or prog.channel_out:
            java.append(" * No COMMAREA: the program exchanges its data through its channel's containers.")
        elif prog.commarea_gap:
            java.append(f" * TODO: no COMMAREA layout: {prog.commarea_gap}.")
        java.append(f" * Field testing: entry transactions {prog.status.get('entry_transactions', 'untested')};")
        java.append(f" * record fields {prog.status.get('interface', 'untested')}.")
        java.append(" */")
        java.append("@RestController")
        java.append(f'@RequestMapping("/api/v1/{java_url_segment(prog.key)}")')
        if t.lombok:
            java.append("@RequiredArgsConstructor")
        java.append(f"public class {cls}Controller {{\n")
        java.append(f"    private final {cls}Service {svc};\n")
        if not t.lombok:
            java += [f"    public {cls}Controller({cls}Service {svc}) {{", f"        this.{svc} = {svc};", "    }\n"]

        req, resp = self.link_types(prog)
        for txn in prog.transactions:
            defs = "; ".join(
                f"{d.get('defined_in')}:{d.get('line')}" + (f" group {d['group']}" if d.get("group") else "")
                for d in txn["definitions"]
            )
            java.append(f"    /** CICS transaction {txn['transid']} -> {cls} (CSD {defs}). */")
            java.append(f'    @PostMapping("/transactions/{txn["segment"]}")')
            java += self._endpoint(f"transaction{txn['segment']}", svc, "handleTransaction",
                                   json.dumps(txn["transid"]), req, resp)  # fmt: skip
        if prog.links or not prog.transactions:
            if prog.links:
                sites = ", ".join(
                    f"{r['verb']} at {r['caller']}:{r['line']}"
                    + ("" if r["via"] == "static" else f" (data-driven, {r['via']})")
                    for r in prog.links
                )
                java.append(f"    /** Program-to-program entry: {sites}. */")
            else:
                java.append("    /** Program-to-program entry: no CSD transaction enters this program. */")
            java.append('    @PostMapping("/link")')
            java += self._endpoint("link", svc, "handleLink", None, req, resp)
        if (prog.channel_in or prog.channel_out) and (req, resp) != (prog.channel_in, prog.channel_out):
            java.append("    /** The program's channel: its GET CONTAINERs in, its PUT CONTAINERs out. */")
            java.append('    @PostMapping("/channel")')
            java += self._endpoint("channel", svc, "handleChannel", None, prog.channel_in, prog.channel_out)
        java.append("}")
        return "\n".join(java)

    @staticmethod
    def _endpoint(method: str, svc: str, call: str, arg: str | None, req: str | None,
                  resp: str | None) -> list[str]:  # fmt: skip
        args = ", ".join(a for a in (arg, "request" if req else None) if a)
        params = f"@RequestBody {req} request" if req else ""
        if resp:
            return [f"    public ResponseEntity<{resp}> {method}({params}) {{",
                    f"        return ResponseEntity.ok({svc}.{call}({args}));", "    }\n"]  # fmt: skip
        return [f"    public ResponseEntity<Void> {method}({params}) {{", f"        {svc}.{call}({args});",
                "        return ResponseEntity.noContent().build();", "    }\n"]  # fmt: skip

    def service_extras(self, prog: CicsProgram) -> dict:
        """The imports and methods the program's @Service gains: the handlers its endpoints call."""
        req, resp = self.link_types(prog)
        names = {n for n in (req, resp, prog.channel_in, prog.channel_out) if n}
        imports = [f"import {self.package}.{DTO_SUBPACKAGE}.{n};" for n in sorted(names)]
        methods: list[str] = []

        def handler(name: str, first: str | None, rq: str | None, rs: str | None, what: str) -> None:
            params = ", ".join(p for p in (first, f"{rq} request" if rq else None) if p)
            methods.append(f"    /** {what} TODO: [AI AGENT] implement from the program's business rules. */")
            methods.append(f"    public {rs or 'void'} {name}({params}) {{")
            methods.append(f'        log.info("{prog.cls}: {name}");')
            if rs:
                methods.append(
                    "        return request;" if rs == rq else "        return null; // TODO: build the response"
                )
            methods.append("    }\n")

        if prog.transactions:
            handler("handleTransaction", "String transid", req, resp, "A CICS transaction entered the program.")
        if self.has_link_handler(prog):
            handler("handleLink", None, req, resp, "Another program LINKed / XCTLed to this one.")
        if (prog.channel_in or prog.channel_out) and (req, resp) != (prog.channel_in, prog.channel_out):
            handler("handleChannel", None, prog.channel_in, prog.channel_out, "The program's channel.")
        return {"imports": imports, "fields": [], "methods": methods}


def load_skeletons(skeleton_dir: Path) -> dict[str, dict[str, Any]]:
    """Clean-room key -> the program's skeleton, from 06_skeleton."""
    return {
        p.name[: -len("_skeleton.json")]: json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(skeleton_dir.glob("*_skeleton.json"))
    }
