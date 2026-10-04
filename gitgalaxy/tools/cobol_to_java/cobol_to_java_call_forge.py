#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: LINK / XCTL / CALL -> service-to-service calls (#3616)
#
# PURPOSE:
# Turns the program-to-program calls the engine resolved (the verified skeleton,
# #3614) into calls between the generated @Service beans:
#
#   - a resolved LINK / XCTL  -> link<Target>(...) / xctl<Target>(...), calling the
#                                target's handleLink (the #3615 /link contract)
#   - a resolved CALL         -> call<Target>(...), calling the target's
#                                handleCall(...) -- typed by the target's
#                                PROCEDURE DIVISION USING parameters
#   - a data-driven target    -> dispatch<Operand>L<line>(String program, ...): a
#                                switch over the candidates the engine found (VALUE,
#                                table, MOVEd literals); any other name throws
#   - a remote (DPL) LINK     -> with `integration.remote_calls: http`, a
#                                <Region>RemoteClient (RestTemplate) per CICS region
#                                the CSD routes to; `local` calls the bean in-process
#
# Targets are injected as ObjectProvider<...>: CICS screens XCTL to each other in
# cycles (menu <-> detail), which plain constructor injection cannot start.
# Every method names the call sites (file:line) and the field-testing status of
# the facts it rests on. A target outside the repository is left to the existing
# mock services; nothing is guessed.
# ==============================================================================
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from gitgalaxy.tools.cobol_to_java.cobol_to_java_common import TraceLog, java_path, java_type, status_text
from gitgalaxy.tools.cobol_to_java.cobol_to_java_names import java_class_base, java_url_segment
from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import DTO_SUBPACKAGE, CicsForge
from gitgalaxy.tools.cobol_to_java.java_target import JavaTarget

_LINK_VERBS = ("LINK", "XCTL")
_OBJECT_PROVIDER = "import org.springframework.beans.factory.ObjectProvider;"


def _camel(name: str) -> str:
    base = java_class_base(name)
    return base[0].lower() + base[1:]


@dataclass
class Param:
    """One USING parameter of a CALLed program, as its Java type."""

    position: int
    name: str
    mode: str
    jtype: str
    note: str = ""


@dataclass
class Extras:
    imports: set[str] = field(default_factory=set)
    fields: dict[str, str] = field(default_factory=dict)  # name -> type
    methods: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"imports": sorted(self.imports), "fields": [(t, n) for n, t in self.fields.items()],
                "methods": self.methods}  # fmt: skip


@dataclass
class RemoteClient:
    system: str
    cls: str
    methods: dict[str, list[str]] = field(default_factory=dict)  # method name -> lines
    imports: set[str] = field(default_factory=set)


class CallForge:
    """Plans every program's outbound calls, the handlers its callers need, and the remote clients."""

    def __init__(self, skeletons: dict[str, dict], cics: CicsForge, package: str,
                 target: JavaTarget | None = None, trace: TraceLog | None = None) -> None:  # fmt: skip
        self.cics = cics
        self.package = package
        self.target = target or JavaTarget()
        self.trace = trace
        self.skeletons = skeletons
        self.key_of = {sk["program"]["file"]: key for key, sk in skeletons.items()}
        self.cls_of = {key: java_class_base(key) for key in skeletons}
        self.extras: dict[str, Extras] = {key: Extras() for key in skeletons}
        self.clients: dict[str, RemoteClient] = {}
        # What the audit reports, counted as the methods are emitted (#3657).
        self.counts = {"link": 0, "xctl": 0, "call": 0, "dispatch": 0, "remote": 0}
        self._params: dict[str, list[Param]] = {}
        self._call_handlers: set[str] = set()
        for key in sorted(skeletons):
            self._plan(key)

    # ---- the callee side ----------------------------------------------------
    def params(self, key: str) -> list[Param]:
        """The Java parameters of a CALLed program's handleCall: its USING items, in order."""
        if key in self._params:
            return self._params[key]
        sk = self.skeletons[key]
        cls = self.cls_of[key]
        interface = (sk["sections"].get("interface") or {}).get("facts") or {}
        status = status_text(sk["sections"].get("interface"))
        out: list[Param] = []
        for p in interface.get("parameters", []):
            layout = p.get("layout")
            fields = (layout or {}).get("fields", [])
            if layout and len(fields) == 1 and fields[0].get("name") == p["record"]:
                jtype, note = java_type(fields[0]), f"PIC {fields[0].get('pic')}"  # an elementary item
                if p["mode"] == "REFERENCE":  # the callee's changes reach the caller, as shared storage does
                    jtype = f"CobolRef<{jtype}>"
            elif layout:
                doc = self.cics._record_doc(p["record"], p["file"], layout, status)
                use = f"USING parameter {p['position']} of {cls}."
                jtype, note = self.cics._dto_for(p["record"], p["file"], layout, cls, doc, use), ""
            else:
                jtype, note = "String", f"TODO: {p['name']} was not found in the DATA DIVISION; carried as text"
                if p["mode"] == "REFERENCE":
                    jtype = "CobolRef<String>"
            out.append(Param(p["position"], p["name"], p["mode"], jtype, note))
        self._params[key] = out
        return out

    def is_called(self, key: str) -> bool:
        """Whether the program is CALLed by another program of the estate: it has a handleCall (#4342: its entry)."""
        return key in self._call_handlers

    def _need_call_handler(self, key: str) -> None:
        if key in self._call_handlers:
            return
        self._call_handlers.add(key)
        params = self.params(key)
        ex = self.extras[key]
        ex.imports |= {self._dto_import(p.jtype) for p in params} - {""}
        sig = ", ".join(f"{p.jtype} {_camel(p.name)}" for p in params)
        using = ", ".join(f"{p.name}" + ("" if p.mode == "REFERENCE" else f" (BY {p.mode})") for p in params)
        ex.methods.append(f"    /** CALLed by another program{f' USING {using}' if using else ''}; returns its RETURN-CODE. "
                          "A BY REFERENCE item is a CobolRef: set() it where the program changes it -- the caller "
                          "sees the change. TODO: [AI AGENT] implement from the program's business rules. */")  # fmt: skip
        for p in params:
            if p.note:
                ex.methods.append(f"    // {p.name}: {p.note}")
        ex.methods += [f"    public int handleCall({sig}) {{", f'        log.info("{self.cls_of[key]}: handleCall");',
                       "        return 0;", "    }\n"]  # fmt: skip

    def _dto_import(self, jtype: str) -> str:
        if jtype.startswith("CobolRef<"):
            self._refs = True
            inner = self._dto_import(jtype[len("CobolRef<") : -1])
            return f"import {self.package}.call.CobolRef;" + (f"\n{inner}" if inner else "")
        if jtype in self.cics.dtos:
            return f"import {self.package}.{DTO_SUBPACKAGE}.{jtype};"
        if jtype == "BigDecimal":
            return "import java.math.BigDecimal;"
        return ""

    def _link_types(self, key: str) -> tuple[str | None, str | None]:
        prog = self.cics.programs.get(key)
        return self.cics.link_types(prog) if prog is not None else (None, None)

    def _prefix_type(self, passed: str | None, callee: str) -> str | None:
        """#3655: the leading segment's DTO when the site passes exactly the record an unpacked
        COMMAREA starts with (CardDemo's menu passes CARDDEMO-COMMAREA to every screen)."""
        prog = self.cics.programs.get(callee)
        if not passed or prog is None or len(prog.segment_dtos) < 2 or not prog.commarea:
            return None
        name = passed.split("(")[0].split(" OF ")[0].strip().upper()
        return prog.segment_dtos[0] if name == prog.commarea["segments"][0]["record"].upper() else None

    def _mismatch(self, passed: str | None, callee: str, caller: str | None = None) -> str | None:
        """A note when the record a site passes is not the one the target was resolved to receive.
        #3688: judged by LAYOUT when the callee kept its own declaration over this caller's record
        (its alternatives say how they differ) -- two areas both named DFHCOMMAREA can differ."""
        prog = self.cics.programs.get(callee)
        commarea = prog.commarea if prog is not None else None
        receives = commarea.get("record") if commarea else None
        if not passed or not commarea or not receives:
            return None
        name = passed.split("(")[0].split(" OF ")[0].strip().upper()
        mine = next((a for a in commarea.get("alternatives", []) if "mismatches" in a and a.get("view") != "coarser"
                     and a["record"].upper() == name and a["file"] == caller), None)  # fmt: skip
        if mine is not None:
            size = (
                f"{mine['bytes']} bytes" if mine["bytes"] is not None and not mine.get("variable") else "no known width"
            )
            return (f"TODO: this site passes {name} ({size}); {self.cls_of[callee].upper()} declares {receives} "
                    f"({commarea['file']}, {commarea['bytes']} bytes) -- map one layout onto the other")  # fmt: skip
        if name == receives.upper() or self._prefix_type(passed, callee):
            return None
        if any(a.get("view") == "coarser" and a["record"].upper() == name for a in commarea.get("alternatives", [])):
            return None  # #3688: this site passes the same bytes the callee declares, some as one block
        if commarea.get("basis") == "unpack" and name in {s["record"].upper() for s in commarea["segments"][:1]}:
            return None  # a single unpacked record: the site passes it as is
        if commarea.get("basis") == "unpack":
            receives = " + ".join(s["record"] for s in commarea["segments"])
        return (
            f"TODO: this site passes {name}; {self.cls_of[callee].upper()} receives {receives} "
            f"({commarea['file']}) -- map one layout onto the other"
        )

    def _has_link(self, key: str) -> bool:
        prog = self.cics.programs.get(key)
        return prog is not None and self.cics.has_link_handler(prog)

    # ---- the caller side ----------------------------------------------------
    def _inject(self, caller: str, callee: str) -> str:
        """The expression reaching callee's service from caller's: `this` for itself."""
        if caller == callee:
            return "this"
        ex = self.extras[caller]
        cls = self.cls_of[callee]
        name = cls[0].lower() + cls[1:] + "Service"
        ex.fields[name] = f"ObjectProvider<{cls}Service>"
        ex.imports.add(_OBJECT_PROVIDER)
        return f"{name}.getObject()"

    def _plan(self, key: str) -> None:
        sk = self.skeletons[key]
        sections = sk["sections"]
        path = sk["program"]["file"]
        ex = self.extras[key]
        status = {
            n: status_text(sections.get(n)) for n in ("calls", "dynamic_call_targets", "remote_calls", "call_contracts")
        }
        remote = {r["line"]: r for r in (sections.get("remote_calls") or {}).get("facts", []) if r.get("file") == path}

        static: dict[tuple[str, str], list[dict]] = {}
        for c in (sections.get("calls") or {}).get("facts", []):
            if c.get("verb") not in (*_LINK_VERBS, "CALL"):
                continue
            callee = self.key_of.get(c.get("resolves_to") or "")
            region = self._region(remote.get(c["line"]))
            if region and self.target.integration.remote_calls == "http" and c["verb"] == "LINK":
                self._remote(key, c, region, remote[c["line"]], status["remote_calls"])
                continue
            if callee is None or c.get("form") == "identifier":
                continue  # outside the repository (the mock services), or data-driven (the dispatch below)
            static.setdefault((c["verb"], callee), []).append(c)

        for (verb, callee), sites in sorted(static.items()):
            where = ", ".join(f"{path}:{s['line']}" for s in sites)
            written = (sites[0].get("target") or self.cls_of[callee]).upper()  # the name as the COBOL writes it
            gaps = sorted({g for s in sites if (g := self._mismatch(s.get("commarea"), callee, path))})
            target = self.cls_of[callee]
            ref = self._inject(key, callee)
            if verb in _LINK_VERBS:
                req, resp = self._link_types(callee)
                if not self._has_link(callee):
                    continue  # no handleLink to call: the target is not a CICS program the forge saw
                self._imports(ex, req, resp)
                note = " XCTL transfers control: nothing after it runs in the caller." if verb == "XCTL" else ""
                ex.methods.append(f"    /** EXEC CICS {verb} PROGRAM({written}) at {where}.{note}")
                ex.methods.append(f"     *  Call targets field testing: {status['calls']}. */")
                ex.methods += [f"    // {g}" for g in gaps]
                prefix = {self._prefix_type(s.get("commarea"), callee) for s in sites}
                if len(prefix) == 1 and None not in prefix and req:
                    # every site passes the leading record: take it, and build the COMMAREA the callee reads
                    (lead,) = prefix
                    self._imports(ex, lead)
                    ex.methods += [f"    public {resp or 'void'} {verb.lower()}{target}({lead} request) {{",
                                   f"        {'return ' if resp else ''}{ref}.handleLink({req}.fromPrefix(request));",
                                   "    }\n"]  # fmt: skip
                else:
                    ex.methods += self._delegate(f"{verb.lower()}{target}", ref, "handleLink", req, resp)
                self.counts[verb.lower()] += 1
                if self.trace:
                    facts = [
                        {
                            "source": f"{s.get('file', path)}:{s['line']}",
                            "section": "calls",
                            "ledger_field": "calls",
                            "field_testing": status["calls"],
                        }
                        for s in sites
                    ]
                    self.trace.record(
                        java_path(self.package, "service", f"{self.cls_of[key]}Service"),
                        f"{self.cls_of[key]}Service#{verb.lower()}{target}",
                        f"service-{verb.lower()}",
                        facts,
                        gaps,
                    )
            else:
                self._need_call_handler(callee)
                params = self.params(callee)
                ex.imports |= {self._dto_import(p.jtype) for p in params} - {""}
                sig = ", ".join(f"{p.jtype} {_camel(p.name)}" for p in params)
                args = ", ".join(_camel(p.name) for p in params)
                ex.methods.append(f"    /** CALL '{written}' at {where}; the parameters are {target}'s USING items.")
                ex.methods.append(f"     *  Call targets {status['calls']}; CALL USING {status['call_contracts']}. */")
                ex.methods += [
                    f"    public int call{target}({sig}) {{",
                    f"        return {ref}.handleCall({args});",
                    "    }\n",
                ]
                self.counts["call"] += 1
                if self.trace:
                    facts = [
                        {
                            "source": f"{s.get('file', path)}:{s['line']}",
                            "section": "calls",
                            "ledger_field": "calls",
                            "field_testing": status["calls"],
                        }
                        for s in sites
                    ]
                    self.trace.record(
                        java_path(self.package, "service", f"{self.cls_of[key]}Service"),
                        f"{self.cls_of[key]}Service#call{target}",
                        "service-call",
                        facts,
                        [],
                    )

        for d in (sections.get("dynamic_call_targets") or {}).get("facts", []):
            if d.get("file") == path and d.get("verb") in (*_LINK_VERBS, "CALL"):
                self._dispatch(key, d, status["dynamic_call_targets"])

    def _imports(self, ex: Extras, *types: str | None) -> None:
        ex.imports |= {self._dto_import(t) for t in types if t} - {""}

    @staticmethod
    def _delegate(method: str, ref: str, handler: str, req: str | None, resp: str | None) -> list[str]:
        params = f"{req} request" if req else ""
        arg = "request" if req else ""
        if resp:
            return [f"    public {resp} {method}({params}) {{", f"        return {ref}.{handler}({arg});", "    }\n"]
        return [f"    public void {method}({params}) {{", f"        {ref}.{handler}({arg});", "    }\n"]

    def _dispatch(self, key: str, d: dict, status: str) -> None:
        ex = self.extras[key]
        site: dict = next(
            (c for c in (self.skeletons[key]["sections"].get("calls") or {}).get("facts", [])
             if c.get("line") == d["line"] and c.get("verb") == d["verb"]),
            {},
        )  # fmt: skip
        passed = site.get("commarea")
        operand = d["operand"].split("(")[0].split(" OF ")[0].strip()
        method = f"dispatch{java_class_base(operand)}L{d['line']}"
        link = d["verb"] in _LINK_VERBS
        where = f"{d['verb']} {'PROGRAM(' + operand + ')' if link else operand} at {d['file']}:{d['line']}"
        cands = ", ".join(f"{c['program']} ({c['via']})" for c in d.get("candidates", [])) or "none found"
        if link and key in self.cics.programs:
            self._task_dispatch(key, d, status, method, where, cands, passed, site)
            return
        ex.methods.append(f"    /** {where}: the target is data-driven. Candidates: {cands}.")
        if d.get("other_sources"):
            ex.methods.append(f"     *  Also MOVEd from {', '.join(d['other_sources'])}, whose content is not known "
                              "statically: those names reach the default branch.")  # fmt: skip
        ex.methods.append(f"     *  Dynamic call targets field testing: {status}. */")
        sig = "String program, Object request" if link else "String program, Object... args"
        ex.methods.append(f"    public Object {method}({sig}) {{")
        self.counts["dispatch"] += 1
        ex.imports.add("import java.util.Locale;")
        ex.methods.append("        switch (program.trim().toUpperCase(Locale.ROOT)) {")
        for c in d.get("candidates", []):
            callee = self.key_of.get(c.get("resolves_to") or "")
            label = f'            case "{c["program"].upper()}":'
            if callee is None:
                ex.methods += [label, f'                throw new UnsupportedOperationException("{c["program"]} is not '
                               'in this repository");']  # fmt: skip
                continue
            ref = self._inject(key, callee)
            if link:
                if not self._has_link(callee):
                    ex.methods += [label, f'                throw new UnsupportedOperationException("{c["program"]} '
                                   'has no LINK entry");']  # fmt: skip
                    continue
                req, resp = self._link_types(callee)
                self._imports(ex, req, resp)
                gap = self._mismatch(passed, callee)
                if gap:
                    label += f"\n                // {gap}"
                lead = self._prefix_type(passed, callee)
                if lead and req:
                    self._imports(ex, lead)
                    call = f"{ref}.handleLink({req}.fromPrefix(({lead}) request))"
                else:
                    call = f"{ref}.handleLink({f'({req}) request' if req else ''})"
            else:
                self._need_call_handler(callee)
                params = self.params(callee)
                ex.imports |= {self._dto_import(p.jtype) for p in params} - {""}
                call = f"{ref}.handleCall({', '.join(f'({p.jtype}) args[{i}]' for i, p in enumerate(params))})"
                resp = None
            if link and resp:
                ex.methods += [label, f"                return {call};"]
            else:
                ex.methods += [label, f"                {call};", "                return null;"]
        ex.methods += ["            default:",
                       f'                throw new IllegalArgumentException("{where}: no known target " + program);',
                       "        }", "    }\n"]  # fmt: skip
        if self.trace:
            facts = [
                {
                    "source": f"{d['file']}:{d['line']}",
                    "section": "dynamic_call_targets",
                    "ledger_field": "dynamic_call_targets",
                    "field_testing": status,
                }
            ]
            self.trace.record(
                java_path(self.package, "service", f"{self.cls_of[key]}Service"),
                f"{self.cls_of[key]}Service#{method}",
                "dispatch",
                facts,
                [],
            )

    def _task_dispatch(self, key: str, d: dict, status: str, method: str, where: str, cands: str,
                       passed: str | None, site: dict) -> None:  # fmt: skip
        """#4342: a data-driven LINK / XCTL of a CICS program. The program runs as a CicsTask (runTask), and CICS
        resolves the name when the command runs -- the program the region defines by that name, PGMIDERR when it
        defines none -- so the dispatcher is the command itself, through the task: the path the proof drives (the
        port's runTask calls it). No switch over the candidates: CICS program names are case-sensitive and any
        defined program is a valid target, so refusing other names, or case-mapping them, would differ from CICS."""
        ex = self.extras[key]
        ex.imports.add(f"import {self.package}.cics.CicsTask;")
        verb = d["verb"]
        length = site.get("commarea_length")
        what = (f"COMMAREA({passed})" + (f" LENGTH({length})" if length else "")) if passed else "no COMMAREA"
        ex.methods.append(f"    /** EXEC CICS {where}, {what}: the target is data-driven (candidates the engine found: "
                          f"{cands}).")  # fmt: skip
        if d.get("other_sources"):
            ex.methods.append(f"     *  Also MOVEd from {', '.join(d['other_sources'])}, whose content is not known "
                              "statically.")  # fmt: skip
        for c in d.get("candidates", []):  # the record a candidate receives, when it is not the one this site passes
            callee = self.key_of.get(c.get("resolves_to") or "")
            gap = self._mismatch(passed, callee) if callee is not None else None
            if gap:
                ex.methods.append(f"     *  {c['program']}: {gap}.")
        ex.methods += ["     *  CICS resolves the name when the command runs (#4342): `program` is the PROGRAM field as the",
                       "     *  COBOL holds it, its trailing blanks the name's padding. Returns the command's condition",
                       "     *  (NORMAL, PGMIDERR, ...).",
                       f"     *  Dynamic call targets field testing: {status}. */"]  # fmt: skip
        name = "program.stripTrailing()"
        if verb == "XCTL":
            if passed and length:
                sig, call = "Object commarea, Integer length", f"task.xctl({name}, commarea, length)"
            elif passed:
                sig, call = "Object commarea", f"task.xctl({name}, commarea)"
            else:
                sig, call = "", f"task.xctl({name}, null)"
        elif passed:
            sig, call = "Object commarea, int length", f"task.link({name}, commarea, length)"
        else:
            sig, call = "", f"task.link({name})"
        ex.methods += [f"    public String {method}(CicsTask task, String program{', ' + sig if sig else ''}) {{",
                       f"        return {call};", "    }\n"]  # fmt: skip
        self.counts["dispatch"] += 1
        if self.trace:
            self.trace.record(
                java_path(self.package, "service", f"{self.cls_of[key]}Service"),
                f"{self.cls_of[key]}Service#{method}",
                "dispatch",
                [{"source": f"{d['file']}:{d['line']}", "section": "dynamic_call_targets",
                  "ledger_field": "dynamic_call_targets", "field_testing": status}],
                [],
            )  # fmt: skip

    # ---- remote regions -----------------------------------------------------
    @staticmethod
    def _region(row: dict | None) -> str | None:
        """The one CICS region a LINK ships to: its SYSID, else the CSD's REMOTESYSTEM."""
        if not row:
            return None
        systems = {row["sysid"]} if row.get("sysid") else {r.get("system") for r in row.get("remote", [])}
        systems.discard(None)
        return systems.pop() if len(systems) == 1 else None

    def _remote(self, key: str, c: dict, region: str, row: dict, status: str) -> None:
        cls = java_class_base(region) + "RemoteClient"
        if region not in self.clients:
            self.cics.names.claim(cls)
        client = self.clients.setdefault(region, RemoteClient(region, cls))
        program = (row.get("program") or c.get("target") or "").upper()
        callee = self.key_of.get(c.get("resolves_to") or "")
        req, resp = self._link_types(callee) if callee else (None, None)
        name = f"link{java_class_base(program)}"
        if name not in client.methods:
            defs = "; ".join(
                f"{r.get('defined_in')}:{r.get('line')} group {r.get('group')}" for r in row.get("remote", [])
            )
            remote_name = next((r.get("remote_name") for r in row.get("remote", []) if r.get("remote_name")), program)
            url = f'baseUrl + "/api/v1/{java_url_segment(remote_name)}/link"'
            body = "request" if req else "null"
            lines = [f"    /** LINK to {remote_name} on {region} (CSD {defs or 'SYSID ' + region}). */"]
            if resp:
                lines += [f"    public {resp} {name}({f'{req} request' if req else ''}) {{",
                          f"        return rest.postForObject({url}, {body}, {resp}.class);", "    }\n"]  # fmt: skip
            else:
                lines += [f"    public void {name}({f'{req} request' if req else ''}) {{",
                          f"        rest.postForObject({url}, {body}, Void.class);", "    }\n"]  # fmt: skip
            client.methods[name] = lines
            client.imports |= {self._dto_import(t) for t in (req, resp) if t} - {""}
        ex = self.extras[key]
        field_name = cls[0].lower() + cls[1:]
        ex.fields[field_name] = cls
        ex.imports.add(f"import {self.package}.client.{cls};")
        self._imports(ex, req, resp)
        ex.methods.append(f"    /** EXEC CICS LINK PROGRAM({program}) at {c.get('file', '')}{':' if c.get('file') else ''}"
                          f"{c.get('line')}: the CSD routes it to region "
                          f"{region} (distributed program link).")  # fmt: skip
        ex.methods.append(f"     *  Remote calls field testing: {status}. */")
        method_name = f"remote{java_class_base(program)}L{c['line']}"
        ex.methods += self._delegate(method_name, field_name, name, req, resp)
        self.counts["remote"] += 1
        if self.trace:
            facts = [
                {
                    "source": f"{c.get('file', '')}:{c['line']}",
                    "section": "remote_calls",
                    "ledger_field": "remote_calls",
                    "field_testing": status,
                }
            ]
            self.trace.record(
                java_path(self.package, "service", f"{self.cls_of[key]}Service"),
                f"{self.cls_of[key]}Service#{method_name}",
                "remote",
                facts,
                [],
            )
            self.trace.record(java_path(self.package, "client", cls), f"{cls}#{name}", "remote-client", facts, [])
            self.trace.record(java_path(self.package, "client", cls), "Class", "remote-client", facts, [])

    def ref_sources(self) -> dict[str, str]:
        """#4023 follow-up: CobolRef (package <pkg>.call), when a CALLed program takes a BY REFERENCE item."""
        if not getattr(self, "_refs", False):
            return {}
        return {"CobolRef": "\n".join([
            f"package {self.package}.call;\n",
            "/**",
            " * A CALL's BY REFERENCE item: the caller and the called program share its storage, so what the called",
            " * program stores in it (set) is what the caller reads back (get) -- a Java String or number could not.",
            " */",
            "public final class CobolRef<T> {\n",
            "    private T value;\n",
            "    public CobolRef(T value) {",
            "        this.value = value;",
            "    }\n",
            "    public static <T> CobolRef<T> of(T value) {",
            "        return new CobolRef<>(value);",
            "    }\n",
            "    public T get() {",
            "        return value;",
            "    }\n",
            "    public void set(T value) {",
            "        this.value = value;",
            "    }\n",
            "    @Override",
            "    public String toString() {",
            "        return String.valueOf(value);",
            "    }",
            "}",
        ]) + "\n"}  # fmt: skip

    def client_sources(self) -> dict[str, str]:
        """Remote client class name -> Java source (package <pkg>.client)."""
        out = {}
        for region, client in sorted(self.clients.items()):
            prop = re.sub(r"[^a-z0-9]+", "-", region.lower()).strip("-") or "region"
            java = [f"package {self.package}.client;\n",
                    "import org.springframework.beans.factory.annotation.Value;",
                    "import org.springframework.stereotype.Component;",
                    "import org.springframework.web.client.RestTemplate;",
                    *sorted(client.imports), "",
                    "/**",
                    f" * CICS region {region}: the programs the CSD routes there (distributed program link), called",
                    f" * over HTTP. Point gitgalaxy.remote.{prop}.url at the service that hosts them.",
                    " */",
                    "@Component",
                    f"public class {client.cls} {{\n",
                    "    private final RestTemplate rest = new RestTemplate();",
                    "    private final String baseUrl;\n",
                    f'    public {client.cls}(@Value("${{gitgalaxy.remote.{prop}.url:http://localhost:8080}}") '
                    "String baseUrl) {",
                    "        this.baseUrl = baseUrl;",
                    "    }\n"]  # fmt: skip
            for name in sorted(client.methods):
                java += client.methods[name]
            java.append("}")
            out[client.cls] = "\n".join(java)
        return out

    def service_extras(self, key: str) -> dict[str, Any]:
        return self.extras[key].as_dict()
