# ==============================================================================
# GitGalaxy Tool: CICS TS / TD queues and IBM MQ -> messaging ports (#3620)
#
# PURPOSE:
# What the verified skeleton says each queue IS decides what it becomes:
#
#   TS queues      scratchpad state (numbered items, re-readable, rewritable, deleted
#                  whole -- GENAPP's GENACNTL passes state between four programs):
#                  a TempStorage port, in-memory (one store per application, as one
#                  CICS region shares its TS queues);
#   TD queues      routed by their destination: a CICS-supplied log (CSSL, CSMT, ...)
#                  -> an SLF4J logger; an extrapartition destination the CSD binds to
#                  a DD / dataset (tdqueue_datasets) -> a file sink, flagged when it is
#                  the internal reader (the records are JCL: a job submission, #3622);
#                  any other (intrapartition) -> the message port; the CSD's TYPEFILE /
#                  OPENTIME / INDIRECTNAME decide how each answers (#5168, X61: NOTOPEN,
#                  INVREQ, an input data set read first in first out, INDIRECT chains);
#   MQ             the MessageQueue port: MQPUT / MQPUT1 send, MQGET receives. A
#                  program whose MQGET reads the queue its TRIGGER message names is a
#                  triggered service: it gets `handleMqMessage(request, replyTo)` and,
#                  with the jms / kafka adapter, a listener that calls it. A reply to
#                  the request's reply-to queue (MQMD ReplyToQ) goes to `replyTo`.
#
# `integration.messaging` picks the MessageQueue adapter: in-memory | jms (Spring's
# Artemis starter; JmsTemplate, @JmsListener) | kafka (KafkaTemplate, @KafkaListener).
# Each program's service gets one helper per EXEC CICS / MQ site, citing its line,
# record, producer / consumer peers and route; a data-driven queue name becomes a
# parameter with a TODO, an installation symbol (`@tdq@`) a TODO to set it.
# Payloads are the COBOL record as text; mapping it onto a DTO is the service's job.
# ==============================================================================
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from gitgalaxy.tools.cobol_to_java.cobol_to_java_common import TraceLog, java_path, status_text
from gitgalaxy.tools.cobol_to_java.cobol_to_java_names import java_class_base
from gitgalaxy.tools.cobol_to_java.java_target import JavaTarget

SUBPACKAGE = "messaging"
# CICS-supplied transient data destinations (DFHDCTG): logs, not application queues.
SYSTEM_LOG_QUEUES = frozenset({
    "CSSL", "CSMT", "CSML", "CSSH", "CSDL", "CSFL", "CSKL", "CSNE", "CSOO", "CSPL", "CSQL", "CSRL", "CSTL",
    "CSZL", "CSCS", "CSBR", "CSCC", "CSDE", "CSDH", "CSJE", "CSLB", "CSMI", "CSNC", "CSPS", "CSRS", "CSSC",
    "CESE", "CESO", "CCPI", "CDBC", "CPLI", "CPLD", "CMIG", "CRPO", "CADL", "CAIL", "CRDI", "CSPK", "CEJL",
})  # fmt: skip
_INTERNAL_READERS = ("INREADER", "INTRDR")
_TD_ATTR = re.compile(r"\b(TYPEFILE|OPENTIME|INDIRECTNAME|SYSID|REMOTENAME)\(\s*([^)\s]*)\s*\)", re.IGNORECASE)
_INDIRECT_HOPS = 8  # a longer INDIRECTNAME chain is taken as a loop, as the CicsTask runtime does
_SYMBOL = re.compile(r"^@\w*@$|^&\w+")  # an installation-time symbol, not a queue's name


def _q(name: str) -> str:
    return f'"{name}"'


@dataclass
class Site:
    key: str
    file: str
    line: int
    kind: str  # TS | TD | MQ
    verb: str
    queue: str | None  # resolved name, None when data-driven
    operand: str | None
    record: str | None
    attributes: str
    resolution: str | None = None


@dataclass
class TdRoute:
    queue: str
    kind: str  # log | dataset | reader | queue | symbol
    detail: str = ""
    target: str = ""  # the queue that holds the records: the INDIRECTNAME chain's end (#5168, X61)
    mode: str = ""  # an extrapartition queue's TYPEFILE: INPUT | OUTPUT | "" (none stated, or RDBACK)
    closed: bool = False  # OPENTIME(DEFERRED): the data set stays closed
    refusal: str = ""  # why the forge refuses to model this queue, by name


@dataclass
class MessagingPlan:
    ts: list[Site] = field(default_factory=list)
    td: list[Site] = field(default_factory=list)
    mq: list[Site] = field(default_factory=list)
    triggered: dict[str, dict] = field(default_factory=dict)  # program key -> {line, transids, reply_to}


class MessagingForge:
    """Plans every TS / TD / MQ site of the converted programs and the ports they share."""

    def __init__(self, skeletons: dict[str, dict], estate: dict, package: str, target: JavaTarget,
                 trace: TraceLog | None = None) -> None:  # fmt: skip
        self.package, self.target, self.trace = package, target, trace
        self.adapter = target.integration.messaging
        self.plan = MessagingPlan()
        self.status: dict[str, dict[str, str]] = {}
        sections = estate.get("sections") or {}
        self.flows = list((sections.get("queue_flows") or {}).get("facts", []))
        self.mq_flows = list((sections.get("mq_flows") or {}).get("facts", []))
        datasets = {d["queue"].upper(): d for d in (sections.get("tdqueue_datasets") or {}).get("facts", [])}
        # #3622: programs whose internal-reader writes the engine resolved to a job submission --
        # the batch forge gives them a submit helper, so the route needs no TODO of its own.
        self.submitters = {
            key for key, sk in skeletons.items()
            if any(s.get("via") == "tdq" for s in ((sk.get("sections") or {}).get("job_submissions") or {}).get("facts", []))
        }  # fmt: skip
        for key, sk in sorted(skeletons.items()):
            secs = sk.get("sections") or {}
            path = sk["program"]["file"]
            self.status[key] = {n: status_text(secs.get(n)) for n in ("cics_resources", "mq_calls")}
            for r in (secs.get("cics_resources") or {}).get("facts", []):
                if r.get("kind") != "QUEUE" or r.get("qualifier") not in ("TS", "TD"):
                    continue
                site = Site(key, path, int(r.get("line") or 0), r["qualifier"], r.get("verb", ""), r.get("name"),
                            r.get("operand"), r.get("record"), r.get("attributes") or "", r.get("resolution"))  # fmt: skip
                (self.plan.ts if r["qualifier"] == "TS" else self.plan.td).append(site)
            for r in (secs.get("mq_calls") or {}).get("facts", []):
                if r.get("verb") not in ("MQPUT", "MQPUT1", "MQGET"):
                    continue
                self.plan.mq.append(Site(key, path, int(r.get("line") or 0), "MQ", r["verb"], r.get("queue"),
                                         r.get("operand"), None, "", r.get("resolution")))  # fmt: skip
                if r["verb"] == "MQGET" and r.get("resolution") == "trigger":
                    entries = (secs.get("entry_transactions") or {}).get("facts", [])
                    self.plan.triggered.setdefault(key, {
                        "line": int(r.get("line") or 0), "operand": r.get("operand"), "file": path,
                        "transids": sorted({e.get("transid") for e in entries if e.get("transid")}),
                        "reply_to": False})  # fmt: skip
            if key in self.plan.triggered:
                self.plan.triggered[key]["reply_to"] = any(
                    s.key == key and s.resolution == "reply_to" for s in self.plan.mq
                )
        # #5168 (X61): each TDQUEUE's TYPE and the attributes that decide how READQ / WRITEQ / DELETEQ TD answer
        self.defs: dict[str, dict[str, str]] = {}
        for r in (sections.get("csd_resources") or {}).get("facts", []):
            if (r.get("resource_type") or "").upper() == "TDQUEUE" and r.get("name"):
                attrs = {k.upper(): v.upper() for k, v in _TD_ATTR.findall(r.get("attributes") or "")}
                self.defs.setdefault(r["name"].upper(), {"TYPE": (r.get("queue_type") or "").upper(), **attrs})
        self.routes = {q: self._resolved_route(q, datasets) for q in sorted({s.queue for s in self.plan.td if s.queue})}

    def _resolved_route(self, queue: str, datasets: dict[str, dict]) -> TdRoute:
        """The route of `queue` after its INDIRECTNAME chain (X61): the target's route, keyed by the name the COBOL uses.

        Refused by name (the route carries the reason; the generated port throws it): an INDIRECT queue with no
        INDIRECTNAME, a target the CSD does not define, a chain that loops, a REMOTE queue or one with a SYSID.
        A queue the CSD does not define keeps its old route (an intrapartition queue, or a log).
        """
        at, refusal = queue, ""
        for hops in range(_INDIRECT_HOPS + 1):
            d = self.defs.get(at.upper())
            if d is None or d["TYPE"] != "INDIRECT":
                break
            nxt = d.get("INDIRECTNAME")
            if not nxt:
                refusal = "an INDIRECT TD queue without INDIRECTNAME"
            elif hops == _INDIRECT_HOPS:
                refusal = "a chain of INDIRECT TD queues that loops"
            elif nxt not in self.defs:
                refusal = "an INDIRECT TD queue whose target the CSD does not define"
            if refusal:
                break
            at = str(nxt)
        d = self.defs.get(at.upper()) or {}
        if not refusal and (d.get("TYPE") == "REMOTE" or d.get("SYSID")):
            refusal = "a REMOTE TD queue (SYSID / TYPE REMOTE)"
        r = self._route(at, datasets.get(at.upper()))
        mode = d.get("TYPEFILE", "") if d.get("TYPEFILE") in ("INPUT", "OUTPUT") else ""
        return TdRoute(queue, r.kind, r.detail, target=at, mode=mode if r.kind in ("dataset", "reader") else "",
                       closed=d.get("OPENTIME") == "DEFERRED" and r.kind in ("dataset", "reader"), refusal=refusal)  # fmt: skip

    @staticmethod
    def _route(queue: str, dataset: dict | None) -> TdRoute:
        if _SYMBOL.match(queue):
            return TdRoute(queue, "symbol", "an installation symbol, not the queue's name")
        if dataset is not None:
            dd = (dataset.get("ddname") or "").upper()
            where = dataset.get("dsname") or f"DD {dd}"
            if dd in _INTERNAL_READERS or (dataset.get("dsname") or "").upper() in _INTERNAL_READERS:
                return TdRoute(queue, "reader", f"the internal reader ({where}): its records are JCL")
            return TdRoute(queue, "dataset", f"{where}, {dataset.get('record_format') or '?'} "
                                              f"{dataset.get('record_size') or '?'}-byte records")  # fmt: skip
        if queue.upper() in SYSTEM_LOG_QUEUES:
            return TdRoute(queue, "log", "a CICS-supplied log destination")
        return TdRoute(queue, "queue", "an intrapartition queue")

    # ---- what is needed ----------------------------------------------------------------
    @property
    def needs_ts(self) -> bool:
        return bool(self.plan.ts)

    @property
    def needs_td(self) -> bool:
        return bool(self.plan.td)

    @property
    def needs_mq(self) -> bool:
        return (
            bool(self.plan.mq)
            or any(r.kind in ("queue", "symbol") for r in self.routes.values())
            or (self.needs_td and any(s.queue is None for s in self.plan.td))
        )

    def _pkg(self) -> str:
        return f"{self.package}.{SUBPACKAGE}"

    # ---- shared sources ------------------------------------------------------------------
    def sources(self) -> dict[tuple[str, ...], dict[str, str]]:
        out: dict[str, str] = {}
        pkg = self._pkg()
        if self.needs_ts:
            out["TempStorage"] = _TEMP_STORAGE.format(pkg=pkg)
            out["InMemoryTempStorage"] = _IN_MEMORY_TS.format(pkg=pkg)
        if self.needs_mq:
            out["MessageQueue"] = _MESSAGE_QUEUE.format(pkg=pkg)
            out[_ADAPTER_CLASS[self.adapter]] = _ADAPTERS[self.adapter].format(pkg=pkg)
        if self.needs_td:
            out["TransientData"] = _TRANSIENT_DATA.format(pkg=pkg)
            out["RoutingTransientData"] = self._routing_td()
        for key in self.plan.triggered if self.adapter != "in-memory" else ():
            cls = f"{java_class_base(key)}MqListener"
            out[cls] = self._listener(key, cls)
        return {("base_pkg", SUBPACKAGE): out} if out else {}

    def _routing_td(self) -> str:
        pkg = self._pkg()
        rows = []
        for q, r in self.routes.items():
            rows.append(f'        ROUTES.put({_q(q)}, "{r.kind}");  // {r.detail or r.kind}')
            if r.target and r.target != q:
                rows.append(f"        TARGETS.put({_q(q)}, {_q(r.target)});  // INDIRECTNAME chain (X61)")
            if r.mode:
                rows.append(f'        MODES.put({_q(q)}, "{r.mode}");  // TYPEFILE')
            if r.closed:
                rows.append(f"        CLOSED.add({_q(q)});  // OPENTIME(DEFERRED): the data set stays closed")
            if r.refusal:
                rows.append(f"        REFUSED.put({_q(q)}, {_q(r.refusal)});")
        mq = self.needs_mq
        ctor_args = "MessageQueue messages" if mq else ""
        return f"""package {pkg};

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * Transient data, routed by each destination's facts (#3620): a CICS-supplied log destination
 * (CSSL, CSMT, ...) goes to the log `cics.td.<queue>`; an extrapartition destination the CSD binds
 * to a DD / dataset appends to `<gitgalaxy.td.directory>/<queue>.txt` (the internal reader's JCL
 * too, flagged: submitting it is #3622); an intrapartition queue{" is the message port" if mq else ""}.
 * A destination missing below is treated as intrapartition. The CSD's TYPEFILE / OPENTIME / INDIRECTNAME decide
 * how it answers, as the CICS runtimes do (#5168, X61): an INDIRECT queue is its INDIRECTNAME's; an extrapartition
 * queue that is closed (OPENTIME DEFERRED) answers NOTOPEN, an input one is read first in first out (nothing left:
 * empty, QZERO) and written INVREQ, an output one is read INVREQ; DELETEQ TD of an extrapartition queue is INVREQ.
 * A REMOTE queue, a broken INDIRECT chain and an extrapartition queue with no TYPEFILE read are refused by name.
 */
@Component
public class RoutingTransientData implements TransientData {{

    static final Map<String, String> ROUTES = new HashMap<>();
    static final Map<String, String> TARGETS = new HashMap<>();
    static final Map<String, String> MODES = new HashMap<>();
    static final Map<String, String> REFUSED = new HashMap<>();
    static final Set<String> CLOSED = new HashSet<>();
    private final Map<String, Integer> cursor = new HashMap<>();

    /** A CICS condition the command would raise (NOTOPEN, INVREQ): RESP has no place in a port, so it is thrown. */
    public static class TdCondition extends RuntimeException {{
        public final String condition;

        public TdCondition(String condition, String message) {{
            super(message);
            this.condition = condition;
        }}
    }}

    static {{
{chr(10).join(rows)}
    }}
{"" if not mq else chr(10) + "    private final MessageQueue messages;" + chr(10)}    private final Path directory;

    public RoutingTransientData({ctor_args}{", " if mq else ""}@Value("${{gitgalaxy.td.directory:td-out}}") String directory) {{
{"        this.messages = messages;" + chr(10) if mq else ""}        this.directory = Path.of(directory);
    }}

    /** The queue that holds `queue`'s records, after the checks the CICS runtimes make for `verb` (X61). */
    private static String resolve(String queue, String verb) {{
        String refused = REFUSED.get(queue);
        if (refused != null) {{
            throw new UnsupportedOperationException(refused + ": not modelled");
        }}
        String route = ROUTES.getOrDefault(queue, "queue");
        if (route.equals("dataset") || route.equals("reader")) {{
            if (verb.equals("DELETEQ")) {{
                throw new TdCondition("INVREQ", "DELETEQ TD " + queue + ": an extrapartition queue");
            }}
            if (CLOSED.contains(queue)) {{
                throw new TdCondition("NOTOPEN", verb + " TD " + queue + ": the data set is closed");
            }}
            String mode = MODES.get(queue);
            if (verb.equals("WRITEQ") && "INPUT".equals(mode)) {{
                throw new TdCondition("INVREQ", "WRITEQ TD " + queue + ": open for input");
            }}
            if (verb.equals("READQ") && mode == null) {{
                throw new UnsupportedOperationException("READQ TD " + queue + " with no TYPEFILE INPUT / OUTPUT: not modelled");
            }}
            if (verb.equals("READQ") && mode.equals("OUTPUT")) {{
                throw new TdCondition("INVREQ", "READQ TD " + queue + ": open for output");
            }}
        }}
        return TARGETS.getOrDefault(queue, queue);
    }}

    @Override
    public void write(String queue, String record) {{
        String target = resolve(queue, "WRITEQ");
        switch (ROUTES.getOrDefault(queue, "queue")) {{
            case "log" -> LoggerFactory.getLogger("cics.td." + target).info(record);
            case "dataset", "reader" -> append(target, record);
            default -> {self._intra("send(target, record)", mq)}
        }}
    }}

    @Override
    public synchronized Optional<String> read(String queue) {{
        String target = resolve(queue, "READQ");
        String route = ROUTES.getOrDefault(queue, "queue");
        if (route.equals("queue") || route.equals("symbol")) {{
            {"return messages.receive(target);" if mq else "return Optional.empty();"}
        }}
        if (MODES.containsKey(queue)) {{
            return nextRecord(target);
        }}
        throw new UnsupportedOperationException("TD " + queue + " is a " + route + " destination: it is written, not read");
    }}

    @Override
    public void delete(String queue) {{
        String target = resolve(queue, "DELETEQ");
        {"messages.purge(target);" if mq else "// no intrapartition queue in this application"}
    }}

    /** READQ TD of an input data set: its records first in first out; none left (or no data set) is QZERO. */
    private Optional<String> nextRecord(String queue) {{
        try {{
            Path file = directory.resolve(queue + ".txt");
            if (!Files.exists(file)) {{
                return Optional.empty();
            }}
            List<String> lines = Files.readAllLines(file, StandardCharsets.UTF_8);
            int at = cursor.getOrDefault(queue, 0);
            if (at >= lines.size()) {{
                return Optional.empty();
            }}
            cursor.put(queue, at + 1);
            return Optional.of(lines.get(at));
        }} catch (IOException e) {{
            throw new UncheckedIOException(e);
        }}
    }}

    private void append(String queue, String record) {{
        try {{
            Files.createDirectories(directory);
            Files.write(directory.resolve(queue + ".txt"), List.of(record), StandardCharsets.UTF_8,
                    StandardOpenOption.CREATE, StandardOpenOption.APPEND);
        }} catch (IOException e) {{
            throw new UncheckedIOException(e);
        }}
    }}

    private static final Logger LOG = LoggerFactory.getLogger(RoutingTransientData.class);
}}
"""

    @staticmethod
    def _intra(call: str, mq: bool) -> str:
        return f"messages.{call};" if mq else 'LOG.warn("TD {} has no message port", queue);'

    def _listener(self, key: str, cls: str) -> str:
        t = self.plan.triggered[key]
        svc = f"{java_class_base(key)}Service"
        var = svc[0].lower() + svc[1:]
        prop = f"gitgalaxy.mq.{java_class_base(key).lower()}.request-queue"
        default = f"{key.upper()}.REQUEST"
        started = ", ".join(t["transids"]) or "the trigger monitor"
        doc = [f"/** The MQ trigger of {key.upper()} (#3620): its MQGET at line {t['line']} reads the queue its trigger",
               f" *  message names ({t['operand']}), started by {started}. Set `{prop}` to that queue",
               f" *  (the default, {default}, is a placeholder). */"]  # fmt: skip
        if self.adapter == "jms":
            return f"""package {self._pkg()};

import {self.package}.service.{svc};
import jakarta.jms.JMSException;
import jakarta.jms.Message;
import jakarta.jms.Queue;
import jakarta.jms.TextMessage;
import org.springframework.jms.annotation.JmsListener;
import org.springframework.stereotype.Component;

{chr(10).join(doc)}
@Component
public class {cls} {{

    private final {svc} {var};

    public {cls}({svc} {var}) {{
        this.{var} = {var};
    }}

    @JmsListener(destination = "${{{prop}:{default}}}")
    public void onMessage(Message message) throws JMSException {{
        String body = message instanceof TextMessage text ? text.getText() : message.getBody(String.class);
        String replyTo = message.getJMSReplyTo() instanceof Queue queue ? queue.getQueueName() : null;
        {var}.handleMqMessage(body, replyTo);
    }}
}}
"""
        return f"""package {self._pkg()};

import {self.package}.service.{svc};
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.support.KafkaHeaders;
import org.springframework.messaging.handler.annotation.Header;
import org.springframework.stereotype.Component;

{chr(10).join(doc)}
@Component
public class {cls} {{

    private final {svc} {var};

    public {cls}({svc} {var}) {{
        this.{var} = {var};
    }}

    /** Kafka has no reply-to queue: a reply to it goes to the topic `<request topic>.reply`. */
    @KafkaListener(topics = "${{{prop}:{default}}}", groupId = "gitgalaxy")
    public void onMessage(String body, @Header(KafkaHeaders.RECEIVED_TOPIC) String topic) {{
        {var}.handleMqMessage(body, topic + ".reply");
    }}
}}
"""

    # ---- per program ---------------------------------------------------------------------
    def service_extras(self, key: str) -> dict[str, Any] | None:
        ts = [s for s in self.plan.ts if s.key == key]
        td = [s for s in self.plan.td if s.key == key]
        mq = [s for s in self.plan.mq if s.key == key]
        if not (ts or td or mq):
            return None
        pkg = self._pkg()
        imports, fields, methods = [], [], []
        if ts:
            imports.append(f"import {pkg}.TempStorage;")
            fields.append(("TempStorage", "tempStorage"))
        if td:
            imports.append(f"import {pkg}.TransientData;")
            fields.append(("TransientData", "transientData"))
        if mq:
            imports.append(f"import {pkg}.MessageQueue;")
            fields.append(("MessageQueue", "messageQueue"))
        if any(s.verb == "READQ" for s in ts + td) or any(s.verb == "MQGET" for s in mq):
            imports.append("import java.util.Optional;")
        status = self.status.get(key, {})
        used: set[str] = set()
        for s in ts + td:
            methods += self._cics_method(s, status.get("cics_resources", "untested"), used)
        for s in mq:
            methods += self._mq_method(s, status.get("mq_calls", "untested"), used)
        if key in self.plan.triggered:
            methods += self._handler(key, status.get("mq_calls", "untested"))
        return {"imports": imports, "fields": fields, "methods": methods}

    def _name(self, s: Site, stem: str, used: set[str]) -> str:
        base = f"{stem}{java_class_base(s.queue) if s.queue and not _SYMBOL.match(s.queue) else ''}L{s.line}"
        name = base
        while name in used:
            name += "X"
        used.add(name)
        return name

    def _peers(self, s: Site) -> str:
        if not s.queue:
            return ""
        me = s.file
        prod = sorted({f["producer"] for f in self.flows if f["queue"] == s.queue and f["queue_type"] == s.kind
                       and f["consumer"] == me})  # fmt: skip
        cons = sorted({f["consumer"] for f in self.flows if f["queue"] == s.queue and f["queue_type"] == s.kind
                       and f["producer"] == me})  # fmt: skip
        parts = ([f"written by {', '.join(prod)}"] if prod else []) + ([f"read by {', '.join(cons)}"] if cons else [])
        return f" Shared through {s.kind} {s.queue}: {'; '.join(parts)}." if parts else ""

    def _cics_method(self, s: Site, status: str, used: set[str]) -> list[str]:
        port = "tempStorage" if s.kind == "TS" else "transientData"
        attrs = s.attributes.upper()
        clause = f" {'FROM' if s.verb == 'WRITEQ' else 'INTO'}({s.record})" if s.record else ""
        head = f"EXEC CICS {s.verb} {s.kind} QUEUE({s.operand or s.queue}){clause}"
        if s.kind == "TS" and "ITEM(" in attrs:
            head += " " + re.search(r"ITEM\([^)]*\)", attrs).group(0)  # type: ignore[union-attr]
        if "REWRITE" in attrs:
            head += " REWRITE"
        doc = [f"    /** {head} at {s.file}:{s.line} (#3620).{self._peers(s)}"]
        todo = None
        qparam, qexpr = "", _q(s.queue) if s.queue else "queue"
        if not s.queue:
            qparam = "String queue, "
            todo = f"TODO: the queue name is data-driven (QUEUE({s.operand})): pass it"
        elif _SYMBOL.match(s.queue):
            todo = f"TODO: {s.queue} is an installation symbol: set the real queue name"
        if s.kind == "TD" and s.queue and s.queue in self.routes:
            r = self.routes[s.queue]
            doc.append(f"     *  Route: {r.kind} -- {r.detail or r.kind}.")
            if r.kind == "reader" and self.target.features.batch and s.key in self.submitters:
                doc.append("     *  The job submission itself is this service's submit helper (#3622).")
            elif r.kind == "reader":
                todo = "TODO: this program submits a job through the internal reader: launch it (#3622)"
        if todo:
            doc.append(f"     *  {todo}.")
        doc.append(f"     *  CICS resources field testing: {status}. */")
        stem = s.verb.lower() + s.kind.capitalize()
        name = self._name(s, stem, used)
        fixed = re.search(r"ITEM\(\s*(\d+)\s*\)", attrs)  # ITEM(1): the COBOL fixes it; ITEM(WS-N) is a parameter
        item_param, item_expr = ("", fixed.group(1)) if fixed else ("int item", "item")
        if s.verb == "WRITEQ":
            if s.kind == "TS" and "REWRITE" in attrs:
                params = ", ".join(p for p in (qparam.rstrip(", "), item_param, "String record") if p)
                sig, body = f"void {name}({params})", f"{port}.rewriteItem({qexpr}, {item_expr}, record);"
            elif s.kind == "TS":
                sig, body = f"int {name}({qparam}String record)", f"return {port}.writeItem({qexpr}, record);"
            else:
                sig, body = f"void {name}({qparam}String record)", f"{port}.write({qexpr}, record);"
        elif s.verb == "READQ":
            if s.kind == "TS" and "ITEM(" in attrs:
                params = ", ".join(p for p in (qparam.rstrip(", "), item_param) if p)
                sig, body = f"Optional<String> {name}({params})", f"return {port}.readItem({qexpr}, {item_expr});"
            elif s.kind == "TS":
                sig, body = f"Optional<String> {name}({qparam.rstrip(', ')})", f"return {port}.readNext({qexpr});"
            else:
                sig, body = f"Optional<String> {name}({qparam.rstrip(', ')})", f"return {port}.read({qexpr});"
        else:  # DELETEQ
            sig, body = f"void {name}({qparam.rstrip(', ')})", f"{port}.delete({qexpr});"
        if self.trace:
            self.trace.record(java_path(self.package, "service", f"{java_class_base(s.key)}Service"),
                              f"{java_class_base(s.key)}Service#{name}", "queue-op",
                              [{"source": f"{s.file}:{s.line}", "section": "cics_resources",
                                "item": f"{s.verb} {s.kind} {s.queue or s.operand}"}], [todo] if todo else [])  # fmt: skip
        return [*doc, f"    protected {sig} {{", f"        {body}", "    }\n"]

    def _mq_method(self, s: Site, status: str, used: set[str]) -> list[str]:
        todo = None
        if s.verb == "MQGET" and s.resolution == "trigger":
            return []  # the triggered request arrives through handleMqMessage
        if s.resolution == "reply_to":
            qparam, qexpr, where = "String replyTo, ", "replyTo", "the request's reply-to queue (MQMD ReplyToQ)"
        elif s.queue and not s.queue.startswith("<"):
            qparam, qexpr, where = "", _q(s.queue), f"queue {s.queue} ({s.resolution})"
        else:
            qparam, qexpr, where = "String queue, ", "queue", f"a data-driven queue ({s.operand})"
            todo = f"TODO: the queue name is data-driven ({s.operand}): pass it"
        peers = ""
        if s.queue and not s.queue.startswith("<"):
            other = sorted({f["consumer"] if s.verb != "MQGET" else f["producer"] for f in self.mq_flows
                            if f["queue"] == s.queue and (f["producer"] if s.verb != "MQGET" else f["consumer"]) == s.file})  # fmt: skip
            if other:
                peers = f" {'Read' if s.verb != 'MQGET' else 'Written'} by {', '.join(other)}."
        doc = (
            [f"    /** {s.verb} to {where} at {s.file}:{s.line} (#3620).{peers}"]
            if s.verb != "MQGET"
            else [f"    /** MQGET from {where} at {s.file}:{s.line} (#3620).{peers}"]
        )
        if todo:
            doc.append(f"     *  {todo}.")
        doc.append(f"     *  MQ calls field testing: {status}. */")
        name = self._name(s, s.verb.lower(), used)
        if s.verb == "MQGET":
            sig, body = f"Optional<String> {name}({qparam.rstrip(', ')})", f"return messageQueue.receive({qexpr});"
        else:
            sig, body = f"void {name}({qparam}String message)", f"messageQueue.send({qexpr}, message);"
        if self.trace:
            self.trace.record(java_path(self.package, "service", f"{java_class_base(s.key)}Service"),
                              f"{java_class_base(s.key)}Service#{name}", "mq-op",
                              [{"source": f"{s.file}:{s.line}", "section": "mq_calls",
                                "item": f"{s.verb} {s.queue or s.operand}"}], [todo] if todo else [])  # fmt: skip
        return [*doc, f"    protected {sig} {{", f"        {body}", "    }\n"]

    def _handler(self, key: str, status: str) -> list[str]:
        t = self.plan.triggered[key]
        started = ", ".join(t["transids"]) or "the MQ trigger monitor"
        via = {"in-memory": "call it directly (in-memory adapter: no listener)",
               "jms": f"{java_class_base(key)}MqListener (JMS) calls it",
               "kafka": f"{java_class_base(key)}MqListener (Kafka) calls it"}[self.adapter]  # fmt: skip
        todo = "TODO: port the logic that handles the MQ request"
        if self.trace:
            self.trace.record(java_path(self.package, "service", f"{java_class_base(key)}Service"),
                              f"{java_class_base(key)}Service#handleMqMessage", "mq-trigger",
                              [{"source": f"{t['file']}:{t['line']}", "section": "mq_calls"}], [todo])  # fmt: skip
        return [
            f"    /** The MQ request this triggered program serves (#3620): its MQGET at line {t['line']} reads the",
            f"     *  queue its trigger message names ({t['operand']}), started by {started}; {via}.",
            "     *  `replyTo` is the request's reply-to queue"
            + (" (MQPUT1 to it answers)." if t["reply_to"] else "."),
            f"     *  {todo}, and reply through this program's MQPUT helpers.",
            f"     *  MQ calls field testing: {status}. */",
            "    public void handleMqMessage(String request, String replyTo) {",
            "    }\n",
        ]

    # ---- audit -----------------------------------------------------------------------------
    def audit_line(self) -> str:
        kinds = [r.kind for r in self.routes.values()]
        routes = ", ".join(
            f"{kinds.count(k)} {k}" for k in ("log", "dataset", "reader", "queue", "symbol") if k in kinds
        )
        return (f"  • Messaging (#3620)        : {len(self.plan.ts)} TS / {len(self.plan.td)} TD / {len(self.plan.mq)} MQ "
                f"sites; TD routes: {routes or 'none'}; {len(self.plan.triggered)} MQ-triggered programs; "
                f"adapter: {self.adapter}\n")  # fmt: skip


_TEMP_STORAGE = """package {pkg};

import java.util.Optional;

/**
 * CICS temporary storage (#3620): named queues of numbered items (from 1) that any program of the
 * application can write, read by number or in sequence, rewrite, and delete whole -- scratchpad
 * state, not messaging.
 */
public interface TempStorage {{

    /** WRITEQ TS: appends an item; returns its number. */
    int writeItem(String queue, String record);

    /** WRITEQ TS ITEM(n) REWRITE. */
    void rewriteItem(String queue, int item, String record);

    /** READQ TS ITEM(n). */
    Optional<String> readItem(String queue, int item);

    /** READQ TS (NEXT): the item after the last one read. */
    Optional<String> readNext(String queue);

    /** DELETEQ TS: the whole queue. */
    void delete(String queue);

    int numItems(String queue);
}}
"""

_IN_MEMORY_TS = """package {pkg};

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.stereotype.Component;

/**
 * Temporary storage kept in this application's memory (#3620): shared by every program in it, as one
 * CICS region shares its TS queues. Behind several instances, replace it with a shared store (Redis,
 * a table) implementing TempStorage.
 */
@Component
public class InMemoryTempStorage implements TempStorage {{

    private final Map<String, List<String>> queues = new ConcurrentHashMap<>();
    private final Map<String, Integer> cursors = new ConcurrentHashMap<>();

    @Override
    public synchronized int writeItem(String queue, String record) {{
        List<String> items = queues.computeIfAbsent(queue, q -> new ArrayList<>());
        items.add(record);
        return items.size();
    }}

    @Override
    public synchronized void rewriteItem(String queue, int item, String record) {{
        List<String> items = queues.get(queue);
        if (items == null || item < 1 || item > items.size()) {{
            throw new IllegalArgumentException("TS " + queue + " has no item " + item + " (ITEMERR)");
        }}
        items.set(item - 1, record);
    }}

    @Override
    public synchronized Optional<String> readItem(String queue, int item) {{
        List<String> items = queues.get(queue);
        if (items == null || item < 1 || item > items.size()) {{
            return Optional.empty();
        }}
        cursors.put(queue, item);
        return Optional.of(items.get(item - 1));
    }}

    @Override
    public synchronized Optional<String> readNext(String queue) {{
        return readItem(queue, cursors.getOrDefault(queue, 0) + 1);
    }}

    @Override
    public synchronized void delete(String queue) {{
        queues.remove(queue);
        cursors.remove(queue);
    }}

    @Override
    public synchronized int numItems(String queue) {{
        List<String> items = queues.get(queue);
        return items == null ? 0 : items.size();
    }}
}}
"""

_TRANSIENT_DATA = """package {pkg};

import java.util.Optional;

/** CICS transient data (#3620): WRITEQ / READQ / DELETEQ TD, routed per destination (RoutingTransientData). */
public interface TransientData {{

    void write(String queue, String record);

    /** READQ TD: destructive, first in first out; empty when the queue is (QZERO). */
    Optional<String> read(String queue);

    void delete(String queue);
}}
"""

_MESSAGE_QUEUE = """package {pkg};

import java.util.Optional;

/**
 * The message port (#3620): IBM MQ's MQPUT / MQPUT1 / MQGET and intrapartition TD queues. The adapter
 * (integration.messaging) is the one implementation in this application.
 */
public interface MessageQueue {{

    void send(String queue, String message);

    /** A destructive get, without waiting: empty when nothing is queued (MQRC_NO_MSG_AVAILABLE). */
    Optional<String> receive(String queue);

    /** Drops every message queued (DELETEQ TD). */
    void purge(String queue);
}}
"""

_ADAPTER_CLASS = {"in-memory": "InMemoryMessageQueue", "jms": "JmsMessageQueue", "kafka": "KafkaMessageQueue"}
_ADAPTERS = {
    "in-memory": """package {pkg};

import java.util.Map;
import java.util.Optional;
import java.util.Queue;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentLinkedQueue;
import org.springframework.stereotype.Component;

/** Queues in this application's memory (#3620, integration.messaging: in-memory). */
@Component
public class InMemoryMessageQueue implements MessageQueue {{

    private final Map<String, Queue<String>> queues = new ConcurrentHashMap<>();

    @Override
    public void send(String queue, String message) {{
        queues.computeIfAbsent(queue, q -> new ConcurrentLinkedQueue<>()).add(message);
    }}

    @Override
    public Optional<String> receive(String queue) {{
        Queue<String> q = queues.get(queue);
        return Optional.ofNullable(q == null ? null : q.poll());
    }}

    @Override
    public void purge(String queue) {{
        queues.remove(queue);
    }}
}}
""",
    "jms": """package {pkg};

import java.util.Optional;
import org.springframework.jms.core.JmsTemplate;
import org.springframework.stereotype.Component;

/** Queues on the JMS broker Spring's Artemis starter connects to (#3620, integration.messaging: jms). */
@Component
public class JmsMessageQueue implements MessageQueue {{

    private final JmsTemplate jms;

    public JmsMessageQueue(JmsTemplate jms) {{
        this.jms = jms;
        this.jms.setReceiveTimeout(JmsTemplate.RECEIVE_TIMEOUT_NO_WAIT);
    }}

    @Override
    public void send(String queue, String message) {{
        jms.convertAndSend(queue, message);
    }}

    @Override
    public Optional<String> receive(String queue) {{
        return Optional.ofNullable((String) jms.receiveAndConvert(queue));
    }}

    @Override
    public void purge(String queue) {{
        while (jms.receive(queue) != null) {{
            // drain
        }}
    }}
}}
""",
    "kafka": """package {pkg};

import java.time.Duration;
import java.util.ArrayDeque;
import java.util.Deque;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;
import org.apache.kafka.clients.consumer.Consumer;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.springframework.kafka.core.ConsumerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;

/**
 * Queues as Kafka topics (#3620, integration.messaging: kafka). A get reads the topic in the
 * consumer group `gitgalaxy`; unlike MQ, a topic keeps its records -- purge only skips what is
 * queued for this group.
 */
@Component
public class KafkaMessageQueue implements MessageQueue {{

    private final KafkaTemplate<String, String> kafka;
    private final ConsumerFactory<String, String> consumers;
    private final Map<String, Consumer<String, String>> open = new ConcurrentHashMap<>();
    private final Map<String, Deque<String>> buffered = new ConcurrentHashMap<>();

    public KafkaMessageQueue(KafkaTemplate<String, String> kafka, ConsumerFactory<String, String> consumers) {{
        this.kafka = kafka;
        this.consumers = consumers;
    }}

    @Override
    public void send(String queue, String message) {{
        kafka.send(queue, message);
    }}

    @Override
    public synchronized Optional<String> receive(String queue) {{
        Deque<String> ready = buffered.computeIfAbsent(queue, q -> new ArrayDeque<>());
        if (ready.isEmpty()) {{
            Consumer<String, String> consumer = open.computeIfAbsent(queue, q -> {{
                Consumer<String, String> c = consumers.createConsumer("gitgalaxy", null);
                c.subscribe(List.of(q));
                return c;
            }});
            for (ConsumerRecord<String, String> r : consumer.poll(Duration.ofMillis(200))) {{
                ready.add(r.value());
            }}
        }}
        return Optional.ofNullable(ready.poll());
    }}

    @Override
    public synchronized void purge(String queue) {{
        while (receive(queue).isPresent()) {{
            // skip
        }}
    }}
}}
""",
}
