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
    TraceLog,
    container_var,
    java_identifier,
    java_path,
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
        if fld.get("dialect") == "pli" and fld.get("pic"):
            pic, usage = f"PIC '{fld['pic']}'", ""  # #3720: PL/I's picture, as written
        where = f"offset {fld['offset']}, {fld['bytes']} bytes"
        if fld.get("bits") is not None:  # #3720: an unaligned PL/I bit string
            where = f"offset {fld['offset']} bit {fld['bit_offset'] % 8}, {fld['bits']} bits"
        lines.append(f"    // {name}: {pic}{usage}, {where} ({fld['file']})")
        if fld.get("occurs"):
            requires_list = True
            lines.append(f"    // OCCURS {fld['occurs']} TIMES")
            lines.append(f"    private List<{jtype}> {var};\n")
        else:
            lines.append(f"    private {jtype} {var};\n")
    return lines, requires_list


def _mismatch_text(mismatches: list) -> str:
    parts = []
    for m in mismatches:
        if m["kind"] == "length":
            parts.append(f"{m['caller']} vs {m['callee']} bytes")
        elif m["kind"] == "shape":
            parts.append(f"fields first differ at {m['caller']} / {m['callee']}")
        else:
            parts.append(m["kind"])
    return "; ".join(parts)


def commarea_alternative_todos(commarea: dict) -> list[str]:
    """One TODO per other record callers pass. #3688: when the program's own declared
    DFHCOMMAREA won over the callers' (`mismatches` rides on each alternative), each says
    how that caller disagrees, or that its width is unknown -- a conflict to settle."""
    out = []
    for alt in commarea.get("alternatives", []):
        sites = ", ".join(f"{s['caller']}:{s['line']}" for s in alt["sources"])
        if alt.get("view") == "coarser":
            continue  # the same bytes as the declaration, some as one block: nothing to settle
        if "mismatches" not in alt:
            out.append(f"TODO: callers also pass {alt['record']} ({alt['file']}, {alt['bytes']} bytes) at {sites}.")
        elif alt["bytes"] is None or alt.get("variable"):
            size = f", variable, up to {alt['bytes']} bytes" if alt.get("variable") and alt["bytes"] else ""
            out.append(f"TODO: {alt['record']} ({alt['file']}{size}), passed at {sites}, has no known width; this program's "
                       f"declared {commarea['record']} ({commarea['bytes']} bytes) is used -- confirm the callers pass it.")  # fmt: skip
        else:
            out.append(f"TODO: {alt['record']} ({alt['file']}, {alt['bytes']} bytes), passed at {sites}, disagrees "
                       f"with this program's declared {commarea['record']} ({commarea['bytes']} bytes: "
                       f"{_mismatch_text(alt['mismatches'])}) -- confirm which layout the program reads.")  # fmt: skip
    return out


# #3754: one CICS task, the runtime a program's runTask is written against.
CICS_TASK_JAVA = """package __PACKAGE__.cics;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.function.UnaryOperator;

/**
 * One CICS task (#3754): what a transaction receives -- its TRANSID, the key the user pressed (EIBAID), the
 * COMMAREA it was started with and its length (none on a first entry, EIBCALEN = 0) and the screens it
 * RECEIVEs -- and, in order, what the program does with it: RECEIVE, RECEIVE MAP, SEND MAP / SEND TEXT,
 * READQ / WRITEQ TS, RETURN TRANSID with a COMMAREA, LINK, XCTL, ABEND. A program's service ports its
 * PROCEDURE DIVISION into runTask(CicsTask); the equivalence harness runs the same task through the original
 * COBOL and compares every event, field by field.
 * A LINK (#4004) runs the target program at the next level, as a CicsTask of its own that shares this
 * task's events, terminal and temporary storage and gets the caller's COMMAREA object itself (by reference).
 */
public class CicsTask {

    private final String transid;
    private final String aid;
    private final Object commarea;
    private final Integer eibcalen;
    private final Map<String, Object> received;
    private final List<Map<String, Object>> events;
    private boolean ended;
    private final CicsTask parent;   // the linking program's level (#4004); null at level 1
    private final int level;
    private final Object linkCommarea;
    private Integer linkLength;                             // #3989: the LENGTH of the LINK that started this level
    private String program;
    private String invoker = "";                                            // ASSIGN INVOKINGPROG: who LINKed / XCTLed here
    private Programs programs;
    private UnaryOperator<Object> snapshot = o -> o;
    private String xctlTarget;
    private Object xctlCommarea;
    private Integer xctlLength;
    private LocalDateTime now;                              // #4006: the virtual clock (the task's root)
    private List<byte[]> retrieveData = List.of();
    private int retrieved;
    private Map<String, LocalDateTime> unexpired = Map.of();
    private final Map<String, LocalDateTime> ownRequests = new HashMap<>();
    private String terminalInput;
    private boolean terminalRead;
    private TempStorage tempStorage = new TempStorage();
    private String abcode = "    ";
    private String termid;                                  // #3989: EIBTRMID (the task's root); null without one
    private String exitLabel;                               // #3989: this level's HANDLE ABEND LABEL
    private boolean exitActive;
    private final java.util.ArrayDeque<Object[]> pushedExits = new java.util.ArrayDeque<>();
    private String unwoundTo;                               // an abend below went to this level's exit
    private List<String[]> faultPlan = List.of();           // #4023 follow-up: injected conditions (the task's root)
    private java.nio.file.Path faultLog;
    private final java.util.Set<String> held = new java.util.HashSet<>();  // files a readForUpdate holds (the root's)
    private boolean syncpointed;                                            // a SYNCPOINT committed (the root's)
    private Runnable rollbackHook;                                          // how a rollback undoes (the root's)
    private final Map<String, Integer> faultSeen = new HashMap<>();

    /** `aid` is ENTER, CLEAR, PF1-PF24 or PA1-PA3; `received` maps a map name to its input screen. The
     *  COMMAREA, if any, is its whole record (as long as its DTO's layout). */
    public CicsTask(String transid, String aid, Object commarea, Map<String, Object> received) {
        this(transid, aid, commarea, null, received);
    }

    /** As above, with EIBCALEN (#4009): the length of the COMMAREA the task receives, which may be shorter
     *  or longer than its DTO's record (a caller passing LENGTH(100) to a program declaring 500 bytes).
     *  Null means the whole record; with no COMMAREA it is 0. */
    public CicsTask(String transid, String aid, Object commarea, Integer eibcalen, Map<String, Object> received) {
        this.transid = transid;
        this.aid = aid;
        this.commarea = commarea;
        this.eibcalen = commarea == null ? Integer.valueOf(0) : eibcalen;
        this.received = received == null ? Map.of() : received;
        this.events = new ArrayList<>();
        this.parent = null;
        this.level = 1;
        this.linkCommarea = null;
    }

    /** A program level below `caller` (#4004), running `program` on `commarea` (EIBCALEN `length`). */
    private CicsTask(CicsTask caller, int level, String program, Object commarea, Integer length, Object linkCommarea) {
        this.transid = caller.transid;
        this.aid = caller.aid;
        this.commarea = commarea;
        this.eibcalen = commarea == null ? Integer.valueOf(0) : length;
        this.received = caller.received;
        this.events = caller.events;
        this.parent = caller;
        this.level = level;
        this.linkCommarea = linkCommarea;
        this.program = program;
        this.programs = caller.programs;
        this.snapshot = caller.snapshot;
        this.tempStorage = caller.tempStorage;
    }

    /** The programs a LINK or XCTL can reach (#4004): whether the CSD defines one (program autoinstall is
     *  off, so any other is PGMIDERR), and how to run one at a level -- its service's runTask. */
    public interface Programs {
        boolean defined(String program);

        void run(String program, CicsTask task);

        /** Whether the CSD defines a transaction (START's TRANSIDERR, #4006). */
        default boolean transaction(String transid) {
            return true;
        }

        /** Whether the region has a terminal (START's TERMIDERR, #4006). */
        default boolean terminal(String termid) {
            return true;
        }
    }

    /** How LINK / XCTL reach other programs (#4004). */
    public CicsTask withPrograms(Programs programs) {
        this.programs = programs;
        return this;
    }

    /** The program this level runs (#4004): its events name it as their issuer. */
    public CicsTask withProgram(String program) {
        this.program = program;
        return this;
    }

    /** How an event keeps a COMMAREA (#4004): a copy of it as it is when the command is issued -- a LINK
     *  COMMAREA is shared with the callee, which may change it afterwards. The default keeps the object. */
    public CicsTask withSnapshot(UnaryOperator<Object> snapshot) {
        this.snapshot = snapshot;
        return this;
    }

    /** The logical level this program runs at: 1 for the task's first program, +1 per LINK (#4004). */
    public int level() {
        return level;
    }

    /** LINK PROGRAM(program) COMMAREA(commarea) LENGTH(length) (#4004, IBM EXEC CICS LINK): LENGERR (RESP2
     *  11) for a length outside 0-32763, PGMIDERR (RESP2 1) for a program the CSD does not define; else the
     *  program runs at the next level on `commarea` itself -- what it changes, the caller sees -- then any
     *  program it XCTLs to, and control returns here. The handlers of this program are not the callee's. */
    public String link(String program, Object commarea, int length) {
        String resp = "NORMAL";
        Integer resp2 = null;
        int len = commarea == null ? 0 : length;
        if (commarea != null && (length < 0 || length > 32763)) {
            resp = "LENGERR";
            resp2 = 11;
        } else if (programs == null || !programs.defined(program)) {
            resp = "PGMIDERR";
            resp2 = 1;
        }
        event("LINK", "target", program, "length", len, "commarea", snapshot.apply(commarea), "resp", resp,
                "resp2", resp2);
        if (!"NORMAL".equals(resp)) {
            return resp;
        }
        CicsTask callee = new CicsTask(this, level + 1, program, commarea, len, commarea);
        callee.invoker = this.program;
        callee.linkLength = len;
        for (int hop = 0; callee != null && hop < 32; hop++) {
            programs.run(callee.program, callee);
            if (callee.xctlTarget != null) {
                String by = callee.program;
                callee = new CicsTask(this, level + 1, callee.xctlTarget, callee.xctlCommarea, callee.xctlLength,
                        commarea);
                callee.invoker = by;
                callee.linkLength = len;
            } else {
                if (!callee.ended) {
                    callee.returnTransid(null, null);  // a GOBACK is a RETURN
                }
                callee = null;
            }
        }
        return resp;
    }

    /** Runs the task (#4004): `program` at level 1 through the Programs given, then any program it XCTLs
     *  to, each on the COMMAREA the XCTL passed; they share this task's events, terminal and storage. */
    public void run(String program) {
        this.program = program;
        CicsTask current = this;
        for (int hop = 0; current != null && hop < 32; hop++) {
            programs.run(current.program, current);
            CicsTask next = current.xctlTarget == null ? null
                    : new CicsTask(this, 1, current.xctlTarget, current.xctlCommarea, current.xctlLength, null);
            if (next != null) {
                next.invoker = current.program;
            }
            current = next;
        }
    }

    /** The virtual time the task was dispatched at (#4006): a task takes no time (EIBTIME, ASKTIME). */
    public CicsTask withClock(LocalDateTime now) {
        this.now = now;
        return this;
    }

    public LocalDateTime now() {
        return root().now;
    }

    private String applid;
    private String sysid;
    private java.util.Set<String> tdQueues;

    /** The region's identity (ASSIGN APPLID / SYSID): a deployment fact, set by whoever runs the task. */
    public CicsTask withRegion(String applid, String sysid) {
        this.applid = applid;
        this.sysid = sysid;
        return this;
    }

    /** ASSIGN APPLID: the region's application id, 8 characters. */
    public String assignApplid() {
        String a = root().applid;
        if (a == null) {
            throw new IllegalStateException("ASSIGN APPLID: no region configured (withRegion)");
        }
        return String.format(java.util.Locale.ROOT, "%-8.8s", a);
    }

    /** ASSIGN SYSID: the region's system id, 4 characters. */
    public String assignSysid() {
        String s = root().sysid;
        if (s == null) {
            throw new IllegalStateException("ASSIGN SYSID: no region configured (withRegion)");
        }
        return String.format(java.util.Locale.ROOT, "%-4.4s", s);
    }

    /** The transient-data queues the CSD defines; null, every queue is defined. */
    public CicsTask withTdQueues(java.util.Set<String> queues) {
        this.tdQueues = queues;
        return this;
    }

    /** WRITEQ TD QUEUE(queue) FROM(record) (IBM CICS TS): one record on a transient-data queue -- recorded, with the
     *  record's text, and compared (CardDemo's CORPT00C submits JCL through JOBS). QIDERR (44) for a queue the
     *  CSD does not define, or the condition the harness planned; then nothing is written. */
    public int writeqTd(String queue, String record) {
        String q = queue.strip();
        int[] planned = root().injected("WRITEQ-TD", q);
        int resp = planned != null ? planned[0]
                : root().tdQueues != null && !root().tdQueues.contains(q) ? 44 : 0;
        event("WRITEQ-TD", "queue", q, "text", resp == 0 ? record : null, "resp", resp);
        return resp;
    }

    private static final LocalDateTime ABSTIME_EPOCH = LocalDateTime.of(1900, 1, 1, 0, 0);

    /** ASKTIME ABSTIME (IBM CICS TS): milliseconds since 00:00 on 1 January 1900, at the task's clock. */
    public long asktime() {
        return java.time.Duration.between(ABSTIME_EPOCH, now()).toMillis();
    }

    /** FORMATTIME ABSTIME(t) YYYYMMDD / MMDDYYYY / DDMMYYYY / YYMMDD / MMDDYY / DDMMYY: the date of t in that form,
     *  its parts joined by `datesep` ("" for no DATESEP; DATESEP with no value is "/"). */
    public static String formatDate(long abstime, String form, String datesep) {
        LocalDateTime t = ABSTIME_EPOCH.plus(java.time.Duration.ofMillis(abstime));
        String y4 = String.format(java.util.Locale.ROOT, "%04d", t.getYear()), y2 = y4.substring(2);
        String m = String.format(java.util.Locale.ROOT, "%02d", t.getMonthValue()), d = String.format(java.util.Locale.ROOT, "%02d", t.getDayOfMonth());
        List<String> parts = switch (form) {
            case "YYYYMMDD" -> List.of(y4, m, d);
            case "MMDDYYYY" -> List.of(m, d, y4);
            case "DDMMYYYY" -> List.of(d, m, y4);
            case "YYMMDD" -> List.of(y2, m, d);
            case "MMDDYY" -> List.of(m, d, y2);
            case "DDMMYY" -> List.of(d, m, y2);
            default -> throw new IllegalArgumentException("FORMATTIME " + form + " is not modelled");
        };
        return String.join(datesep, parts);
    }

    /** FORMATTIME ABSTIME(t) TIME: hhmmss of t, joined by `timesep` ("" for no TIMESEP; TIMESEP alone is ":"). */
    public static String formatTime(long abstime, String timesep) {
        LocalDateTime t = ABSTIME_EPOCH.plus(java.time.Duration.ofMillis(abstime));
        return String.join(timesep, String.format(java.util.Locale.ROOT, "%02d", t.getHour()), String.format(java.util.Locale.ROOT, "%02d", t.getMinute()),
                String.format(java.util.Locale.ROOT, "%02d", t.getSecond()));
    }

    /** The terminal the task is attached to (#3989): EIBTRMID, or null for a task no terminal started. */
    public CicsTask withTermid(String termid) {
        this.termid = termid;
        return this;
    }

    /** EIBTRMID (#3989): the task's terminal, the same at every LINK / XCTL level; null for a non-terminal task. */
    public String termid() {
        return root().termid;
    }

    /** The FROM data of the START requests this task was started for, in expiry order (#4006). */
    public CicsTask withRetrieveData(List<byte[]> data) {
        this.retrieveData = data == null ? List.of() : data;
        return this;
    }

    /** The region's unexpired interval-control requests by REQID (#4006: what CANCEL can still find). */
    public CicsTask withRequests(Map<String, LocalDateTime> unexpired) {
        this.unexpired = unexpired == null ? Map.of() : unexpired;
        return this;
    }

    private static final DateTimeFormatter ISO = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss");

    /** START TRANSID(transid) [TERMID] INTERVAL(hhmmss) [FROM] [REQID] [PROTECT] (#4006, IBM EXEC CICS START):
     *  the request expires at now + INTERVAL; the harness's scheduler runs it once the starting task has
     *  ended (a PROTECT request only if it ended normally). `termid`, `from` and `reqid` may be null. */
    public StartResult start(String transid, String termid, int interval, byte[] from, String reqid, boolean protect) {
        return start(transid, termid, interval, false, from, reqid, protect);
    }

    /** START ... TIME(hhmmss): today at that time; a TIME not later than now but within the preceding six hours
     *  expires at once ("if the START gets triggered at any time within 6 hours after the time specified on
     *  the START, it runs immediately"), an earlier one tomorrow. */
    public StartResult startAt(String transid, String termid, int time, byte[] from, String reqid, boolean protect) {
        return start(transid, termid, time, true, from, reqid, protect);
    }

    private StartResult start(String transid, String termid, int hhmmss, boolean isTime, byte[] from, String reqid,
            boolean protect) {
        int hh = hhmmss / 10000, mm = hhmmss / 100 % 100, ss = hhmmss % 100;
        LocalDateTime clock = now();
        LocalDateTime at = null;
        String resp = "NORMAL";
        if (hhmmss < 0 || mm > 59 || ss > 59 || hh > (isTime ? 23 : 99)) {
            resp = "INVREQ";
        } else if (from != null && (from.length < 1 || from.length > 32763)) {
            resp = "LENGERR";
        } else if (programs != null && !programs.transaction(transid)) {
            resp = "TRANSIDERR";
        } else if (termid != null && programs != null && !programs.terminal(termid)) {
            resp = "TERMIDERR";
        } else if (isTime) {
            at = clock.toLocalDate().atTime(hh, mm, ss);
            if (!at.isAfter(clock)) {
                at = at.isBefore(clock.minusHours(6)) ? at.plusDays(1) : clock;
            }
        } else {
            at = clock.plusSeconds(hh * 3600L + mm * 60L + ss);
        }
        Map<String, Object> e = new LinkedHashMap<>();
        e.put("event", "START");
        e.put("transid", transid);
        e.put("termid", termid);
        e.put(isTime ? "time" : "interval", String.format(java.util.Locale.ROOT, "%06d", hhmmss));
        e.put("from", from == null ? null : from.clone());
        if (reqid != null) {
            e.put("reqid", reqid);
            if (at != null) {
                root().ownRequests.put(reqid, at);
            }
        }
        e.put("protect", protect);
        e.put("resp", resp);
        e.put("expires", at == null ? null : at.format(ISO));
        add(e);
        return new StartResult(resp, at);
    }

    /** A START's outcome: its condition and when the request expires (null unless NORMAL). */
    public record StartResult(String resp, LocalDateTime expires) {
    }

    /** RETRIEVE INTO LENGTH(maxLength) (#4006, IBM EXEC CICS RETRIEVE): the next data record of the requests
     *  the task was started for, truncated with LENGERR when longer (the length is then the record's own);
     *  ENDDATA when none is left, as for a task no START started. */
    public RetrieveResult retrieve(int maxLength) {
        CicsTask task = root();
        if (task.retrieved >= task.retrieveData.size()) {
            event("RETRIEVE", "resp", "ENDDATA", "length", null, "data", null);
            return new RetrieveResult("ENDDATA", -1, null);
        }
        byte[] stored = task.retrieveData.get(task.retrieved++);
        byte[] data = stored.length > maxLength ? Arrays.copyOf(stored, Math.max(maxLength, 0)) : stored.clone();
        String resp = stored.length > maxLength ? "LENGERR" : "NORMAL";
        event("RETRIEVE", "resp", resp, "length", stored.length, "data", data);
        return new RetrieveResult(resp, stored.length, data);
    }

    /** A RETRIEVE's outcome: its condition, the LENGTH it sets (-1 when none) and the data moved INTO. */
    public record RetrieveResult(String resp, int length, byte[] data) {
    }

    /** CANCEL REQID(reqid) (#4006, IBM EXEC CICS CANCEL): NORMAL for a request that has not expired yet (the
     *  harness then drops it), NOTFND when none matches "an unexpired interval control command". */
    public String cancel(String reqid) {
        CicsTask task = root();
        LocalDateTime at = task.ownRequests.containsKey(reqid) ? task.ownRequests.get(reqid) : task.unexpired.get(reqid);
        String resp = at != null && at.isAfter(now()) ? "NORMAL" : "NOTFND";
        if ("NORMAL".equals(resp)) {
            task.ownRequests.remove(reqid);
        }
        event("CANCEL", "reqid", reqid, "resp", resp);
        return resp;
    }

    /** LINK PROGRAM(program) with no COMMAREA: the callee's EIBCALEN is 0. */
    public String link(String program) {
        return link(program, null, 0);
    }

    private java.util.Map<String, Long> counters = new java.util.HashMap<>();  // the region's named counters (root's)

    /** The region's named counters, "POOL/NAME" -> the value the next GET COUNTER returns. */
    public CicsTask withCounters(java.util.Map<String, Long> counters) {
        this.counters = counters;
        return this;
    }

    /** GET COUNTER (IBM CICS TS): the named counter's current value, after which it is one more; null (NOTFND)
     *  for a counter the region does not have. */
    public Long getCounter(String pool, String name) {
        java.util.Map<String, Long> all = root().counters;
        String key = (pool == null ? "" : pool.strip()) + "/" + (name == null ? "" : name.strip());
        Long v = all.get(key);
        if (v != null) {
            all.put(key, v + 1);
        }
        return v;
    }

    /** ASSIGN INVOKINGPROG: the program that LINKed or XCTLed to this one (IBM CICS TS, ASSIGN), 8 characters;
     *  blanks for a task's first program. */
    public String invokingProgram() {
        return String.format(java.util.Locale.ROOT, "%-8s", invoker == null ? "" : invoker);
    }

    public String transid() {
        return transid;
    }

    public String aid() {
        return aid;
    }

    /** False on a first entry (EIBCALEN = 0). */
    public boolean hasCommarea() {
        return commarea != null;
    }

    /** EIBCALEN: 0 without a COMMAREA, else its length as passed; null when it came as its whole record. */
    public Integer eibcalen() {
        return eibcalen;
    }

    public <T> T commarea(Class<T> type) {
        return type.cast(commarea);
    }

    /** RECEIVE MAP: the screen the user sent, or empty (MAPFAIL) when nothing was received. */
    public <T> Optional<T> receive(String map, Class<T> type) {
        return receive(map, null, type);
    }

    /** RECEIVE MAP(map) MAPSET(mapset), recorded as an event with its RESP (NORMAL, or MAPFAIL when empty). */
    public <T> Optional<T> receive(String map, String mapset, Class<T> type) {
        Optional<T> screen = Optional.ofNullable(received.get(map)).map(type::cast);
        event("RECEIVE-MAP", "map", map, "mapset", mapset, "resp", screen.isPresent() ? "NORMAL" : "MAPFAIL");
        return screen;
    }

    /** What the operator typed on a cleared screen with the key that started the task (#4005), which an
     *  unformatted RECEIVE returns; null when nothing was transmitted. */
    public CicsTask withTerminalInput(String text) {
        this.terminalInput = text;
        return this;
    }

    /** The task's terminal input was already read by an earlier program of the task (#4005). */
    public void terminalInputRead() {
        this.terminalRead = true;
    }

    /** RECEIVE INTO LENGTH(maxLength) (#4005): the terminal input, unformatted, read once per task. Input
     *  longer than maxLength is truncated to it and raises LENGERR, and the length is then the input's full
     *  length (IBM, EXEC CICS RECEIVE: "the data area specified in the LENGTH option is set to the original
     *  length of data"). */
    public Received receiveText(int maxLength) {
        CicsTask task = root();  // the terminal is the task's, whichever level reads it
        if (task.terminalRead) {
            throw new IllegalStateException("a second terminal RECEIVE waits for more input from the operator");
        }
        task.terminalRead = true;
        String text = task.terminalInput == null ? "" : task.terminalInput;
        String data = text.length() > maxLength ? text.substring(0, Math.max(maxLength, 0)) : text;
        String resp = text.length() > maxLength ? "LENGERR" : "NORMAL";
        event("RECEIVE", "resp", resp, "length", text.length(), "data", data);
        return new Received(resp, text.length(), data);
    }

    /** A terminal RECEIVE's outcome: its condition, the LENGTH it sets, and the data it moved INTO. */
    public record Received(String resp, int length, String data) {
    }

    /** #4023 follow-up: the equivalence harness's injected conditions for this task, as its stub reads them
     *  (faults.cfg: `CMD FILE NTH RESP [RESP2]`, NTH `*` = every one; DFHRESP numbers), and the file each one
     *  that fires is appended to (`CMD FILE NTH RESP RESP2`). Commands are counted per task. */
    public CicsTask withFaults(List<String> plan, java.nio.file.Path log) {
        List<String[]> parsed = new ArrayList<>();
        for (String line : plan) {
            String[] w = line.trim().split("[ ]+");
            if (w.length >= 4) {
                parsed.add(w);
            }
        }
        this.faultPlan = List.copyOf(parsed);
        this.faultLog = log;
        return this;
    }

    /** READ FILE(file) (#4023 follow-up): `lookup` is the service's generated read method. RESP NORMAL (0) and the
     *  record, or NOTFND (13) without one -- or the condition the harness planned, and then nothing is read. */
    public <T> FileRead<T> read(String file, java.util.function.Supplier<Optional<T>> lookup) {
        int[] planned = root().injected("READ", file);
        if (planned != null) {
            return new FileRead<>(planned[0], planned[1], null);
        }
        T record = lookup.get().orElse(null);
        return new FileRead<>(record != null ? 0 : 13, 0, record);
    }

    /** READ FILE(file) UPDATE: as read, and the file's record is held for a REWRITE. */
    public <T> FileRead<T> readForUpdate(String file, java.util.function.Supplier<Optional<T>> lookup) {
        FileRead<T> r = read(file, lookup);
        if (r.normal()) {
            root().held.add(file);
        }
        return r;
    }

    /** WRITE FILE(file) RIDFLD FROM: `exists` says whether the key is there already (DUPREC, 14, as CICS answers);
     *  else `store` saves the record (the service's generated repository save) and RESP is NORMAL -- or the
     *  condition the harness planned, and nothing is written. */
    public int write(String file, boolean exists, Runnable store) {
        int[] planned = root().injected("WRITE", file);
        if (planned != null) {
            return planned[0];
        }
        if (exists) {
            return 14;
        }
        store.run();
        return 0;
    }

    /** REWRITE FILE(file) FROM: replaces the record a readForUpdate holds (INVREQ, 16, when none is held). */
    public int rewrite(String file, Runnable store) {
        int[] planned = root().injected("REWRITE", file);
        if (planned != null) {
            return planned[0];
        }
        if (!root().held.remove(file)) {
            return 16;
        }
        store.run();
        return 0;
    }

    /** DELETE FILE(file) RIDFLD: `exists` says whether the key is there (NOTFND, 13, when not); else `remove`
     *  deletes it (the service's generated repository delete) -- or the condition the harness planned. */
    public int delete(String file, boolean exists, Runnable remove) {
        int[] planned = root().injected("DELETE", file);
        if (planned != null) {
            return planned[0];
        }
        if (!exists) {
            return 13;
        }
        remove.run();
        return 0;
    }

    /** DELETE FILE(file) without RIDFLD: the record a readForUpdate holds (INVREQ, 16, when none is held). */
    public int deleteHeld(String file, Runnable remove) {
        int[] planned = root().injected("DELETE", file);
        if (planned != null) {
            return planned[0];
        }
        if (!root().held.remove(file)) {
            return 16;
        }
        remove.run();
        return 0;
    }

    /** One file's browse: its keys (asked again on every command, so a record written meanwhile is seen), how it
     *  started, and the last key read and in which direction (0: none yet). */
    private static final class Browse {
        java.util.function.Supplier<java.util.NavigableSet<String>> keys;
        boolean equal;
        String start;
        String last;
        int dir;
    }

    private final Map<String, Browse> browses = new java.util.HashMap<>();

    /** What a READNEXT / READPREV found: its RESP and the key read (null when none; then look nothing up). */
    public record Browsed(int resp, String key) {
        public boolean normal() {
            return resp == 0;
        }
    }

    private static boolean highValues(String key) {
        return !key.isEmpty() && key.chars().allMatch(ch -> ch == '\u00ff');
    }

    /** STARTBR FILE(file) RIDFLD(key) [GTEQ | EQUAL] (IBM CICS TS): positions a browse on the first key >= `key`
     *  (GTEQ, the default) or on `key` itself (EQUAL); NOTFND (13) when there is none. A key of all X'FF'
     *  (HIGH-VALUES) positions at the end, for READPREV. A second STARTBR on the file: INVREQ (16). `keys`: the
     *  file's keys, in key order (e.g. the repository's ids as a TreeSet). */
    public int startbr(String file, String key, boolean equal,
                       java.util.function.Supplier<java.util.NavigableSet<String>> keys) {
        int[] planned = root().injected("STARTBR", file);
        if (planned != null) {
            return planned[0];
        }
        Map<String, Browse> all = root().browses;
        if (all.containsKey(file)) {
            return 16;
        }
        java.util.NavigableSet<String> k = keys.get();
        if (!highValues(key) && (equal ? !k.contains(key) : k.ceiling(key) == null)) {
            return 13;
        }
        Browse b = new Browse();
        b.keys = keys;
        b.equal = equal;
        b.start = key;
        all.put(file, b);
        return 0;
    }

    /** READNEXT FILE(file) RIDFLD(ridfld): the key of the next record -- the one STARTBR positioned on first; set
     *  RIDFLD to it and look the record up by it. A RIDFLD the program changed, or a READNEXT after a READPREV,
     *  repositions at the first key >= RIDFLD. ENDFILE (20) past the last; INVREQ (16) with no browse. */
    public Browsed readnext(String file, String ridfld) {
        int[] planned = root().injected("READNEXT", file);
        if (planned != null) {
            return new Browsed(planned[0], null);
        }
        Browse b = root().browses.get(file);
        if (b == null) {
            return new Browsed(16, null);
        }
        java.util.NavigableSet<String> k = b.keys.get();
        boolean changed = !ridfld.equals(b.last != null ? b.last : b.start);
        String at;
        if (b.dir == 1 && !changed) {
            at = k.higher(ridfld);
        } else if (highValues(ridfld)) {
            at = null;
        } else {
            at = b.equal ? (k.contains(ridfld) ? ridfld : null) : k.ceiling(ridfld);
        }
        if (at == null) {
            return new Browsed(20, null);
        }
        b.last = at;
        b.dir = 1;
        return new Browsed(0, at);
    }

    /** READPREV FILE(file) RIDFLD(ridfld): the key of the previous record. Right after STARTBR the STARTBR key must
     *  exist (else NOTFND, 13); after a READNEXT, or with RIDFLD changed, it repositions to RIDFLD and reads that
     *  record -- so it reads again the record READNEXT just read; after a HIGH-VALUES STARTBR, the last record.
     *  ENDFILE (20) before the first; INVREQ (16) with no browse. */
    public Browsed readprev(String file, String ridfld) {
        int[] planned = root().injected("READPREV", file);
        if (planned != null) {
            return new Browsed(planned[0], null);
        }
        Browse b = root().browses.get(file);
        if (b == null) {
            return new Browsed(16, null);
        }
        java.util.NavigableSet<String> k = b.keys.get();
        boolean changed = !ridfld.equals(b.last != null ? b.last : b.start);
        String at;
        int none;
        if (highValues(ridfld) && (b.dir == 0 || changed)) {
            at = k.isEmpty() ? null : k.last();
            none = 20;
        } else if (b.dir == -1 && !changed) {
            at = k.lower(ridfld);
            none = 20;
        } else {
            at = k.contains(ridfld) ? ridfld : null;
            none = 13;
        }
        if (at == null) {
            return new Browsed(none, null);
        }
        b.last = at;
        b.dir = -1;
        return new Browsed(0, at);
    }

    /** ENDBR FILE(file): the browse ends; INVREQ (16) when none is active. */
    public int endbr(String file) {
        int[] planned = root().injected("ENDBR", file);
        if (planned != null) {
            return planned[0];
        }
        return root().browses.remove(file) != null ? 0 : 16;
    }

    /** SYNCPOINT: the unit of work is committed; a later rollback() cannot undo it. */
    public void syncpoint() {
        root().held.clear();
        root().syncpointed = true;
        event("SYNCPOINT");
    }

    /** SYNCPOINT ROLLBACK: the task's file changes are undone -- the transaction the task runs in is marked for
     *  rollback (the hook, set by whoever runs the task). A rollback after a syncpoint would undo only part of
     *  the task's work, which this runtime does not model: it refuses rather than undo too much. */
    public void rollback() {
        if (root().syncpointed) {
            throw new UnsupportedOperationException("SYNCPOINT ROLLBACK after a SYNCPOINT is not modelled");
        }
        root().held.clear();
        if (root().rollbackHook != null) {
            root().rollbackHook.run();
        }
        event("SYNCPOINT-ROLLBACK");
    }

    /** Who runs the task says how a rollback undoes its changes (e.g. a TransactionStatus's setRollbackOnly). */
    public CicsTask onRollback(Runnable hook) {
        this.rollbackHook = hook;
        return this;
    }

    /** INQUIRE PROGRAM(program) (#4023 follow-up): its RESP -- NORMAL (0) for a program the region defines, else
     *  PGMIDERR (27) -- or the condition the harness planned. It changes nothing else a task can see. */
    public int inquireProgram(String program) {
        String name = program == null ? "" : program.trim();
        int[] planned = root().injected("INQUIRE", name);
        if (planned != null) {
            return planned[0];
        }
        Programs known = programs != null ? programs : root().programs;
        return known == null || known.defined(name) ? 0 : 27;
    }

    /** A file command's outcome: RESP and RESP2 (DFHRESP numbers) and the record read, when there is one. */
    public record FileRead<T>(int resp, int resp2, T record) {
        public boolean normal() {
            return resp == 0;
        }
    }

    private int[] injected(String cmd, String file) {
        if (faultPlan.isEmpty()) {
            return null;
        }
        int n = faultSeen.merge(cmd + " " + file, 1, Integer::sum);
        for (String[] f : faultPlan) {
            if (f[0].equals(cmd) && f[1].equals(file) && ("*".equals(f[2]) || Integer.parseInt(f[2]) == n)) {
                int resp = Integer.parseInt(f[3]);
                int resp2 = f.length > 4 ? Integer.parseInt(f[4]) : 0;
                if (faultLog != null) {
                    try {
                        java.nio.file.Files.writeString(faultLog, cmd + " " + file + " " + n + " " + resp + " " + resp2
                                + System.lineSeparator(), java.nio.file.StandardOpenOption.CREATE,
                                java.nio.file.StandardOpenOption.APPEND);
                    } catch (java.io.IOException e) {
                        throw new java.io.UncheckedIOException(e);
                    }
                }
                return new int[] {resp, resp2};
            }
        }
        return null;
    }

    /** The region's temporary storage this task works on (#4002): one store is shared by every task of a
     *  conversation, the way a region's TS queues outlive the task that writes them. */
    public CicsTask withTempStorage(TempStorage storage) {
        this.tempStorage = storage;
        return this;
    }

    /** WRITEQ TS QUEUE(queue) FROM(data) (#4002): appends an item, creating the queue with its first write;
     *  the result's item is the number assigned. An item is the bytes the program wrote, in the region's code
     *  page (EBCDIC). LENGERR when data is empty or longer than 32763 bytes. */
    public TsResult writeqTs(String queue, byte[] data) {
        return tempStorage.write(this, queue, 0, data);
    }

    /** WRITEQ TS QUEUE(queue) FROM(data) ITEM(item) REWRITE (#4002): QIDERR without the queue, ITEMERR outside it. */
    public TsResult rewriteqTs(String queue, int item, byte[] data) {
        return tempStorage.write(this, queue, item, data);
    }

    /** READQ TS QUEUE(queue) INTO LENGTH(maxLength) ITEM(item) (#4002, IBM EXEC CICS READQ TS): QIDERR when
     *  the queue does not exist, ITEMERR for an item outside it; else the item, truncated to maxLength with
     *  LENGERR when longer, and the result's length is the item's own. */
    public TsResult readqTs(String queue, int item, int maxLength) {
        return tempStorage.read(this, queue, item, maxLength);
    }

    /** READQ TS QUEUE(queue) NEXT: the item after the last one read by any task (ITEMERR past the end). */
    public TsResult readqTsNext(String queue, int maxLength) {
        return tempStorage.read(this, queue, 0, maxLength);
    }

    /** A TS command's outcome: its condition, the item (number assigned or read), the LENGTH it sets (READQ;
     *  -1 when it sets none), the data moved INTO (READQ; null when none) and NUMITEMS. */
    public record TsResult(String resp, int item, int length, byte[] data, int numItems) {
    }

    /** A region's temporary storage (#4002): TS queues by name, each a list of items, and the READQ NEXT
     *  position of each queue (which counts a read by ITEM too). */
    public static final class TempStorage {
        private final Map<String, List<byte[]>> queues = new LinkedHashMap<>();
        private final Map<String, Integer> next = new HashMap<>();

        /** A queue as it is before the conversation starts. */
        public TempStorage seed(String queue, List<byte[]> items) {
            queues.put(queue, new ArrayList<>(items));
            return this;
        }

        /** Every queue and its items, in the order the queues were created. */
        public Map<String, List<byte[]>> queues() {
            Map<String, List<byte[]>> out = new LinkedHashMap<>();
            queues.forEach((q, items) -> out.put(q, List.copyOf(items)));
            return out;
        }

        TsResult write(CicsTask task, String queue, int rewrite, byte[] data) {
            List<byte[]> items = queues.get(queue);
            String resp = "NORMAL";
            int item = 0;
            if (data == null || data.length < 1 || data.length > 32763) {
                resp = "LENGERR";
            } else if (rewrite > 0 && items == null) {
                resp = "QIDERR";
            } else if (rewrite > 0 && rewrite > items.size()) {
                resp = "ITEMERR";
            } else {
                if (items == null) {
                    items = new ArrayList<>();
                    queues.put(queue, items);
                }
                if (rewrite > 0) {
                    items.set(rewrite - 1, data.clone());
                    item = rewrite;
                } else {
                    items.add(data.clone());
                    item = items.size();
                }
            }
            task.event("WRITEQ-TS", "queue", queue, "data", data, "resp", resp, "item", item == 0 ? null : item);
            return new TsResult(resp, item, -1, null, items == null ? 0 : items.size());
        }

        TsResult read(CicsTask task, String queue, int item, int maxLength) {
            List<byte[]> items = queues.get(queue);
            int want = item > 0 ? item : next.getOrDefault(queue, 0) + 1;
            Object shown = item > 0 ? (Object) item : "NEXT";
            if (items == null || want < 1 || want > items.size()) {
                String resp = items == null ? "QIDERR" : "ITEMERR";
                task.event("READQ-TS", "queue", queue, "item", shown, "resp", resp, "length", null, "data", null);
                return new TsResult(resp, want, -1, null, 0);
            }
            next.put(queue, want);
            byte[] stored = items.get(want - 1);
            byte[] data = stored.length > maxLength ? Arrays.copyOf(stored, Math.max(maxLength, 0)) : stored.clone();
            String resp = stored.length > maxLength ? "LENGERR" : "NORMAL";
            task.event("READQ-TS", "queue", queue, "item", shown, "resp", resp, "length", stored.length, "data", data);
            return new TsResult(resp, want, stored.length, data, items.size());
        }
    }

    public void sendMap(String map, Object screen) {
        event("SEND-MAP", "map", map, "screen", screen);
    }

    /** SEND MAP(map) MAPSET(mapset) FROM(screen) with its options (ERASE, DATAONLY, MAPONLY, CURSOR, ...;
     *  #4001). `screen` holds each field's data (`<f>O`; null under MAPONLY, a value starting with a
     *  null character leaves the map's INITIAL); `subfields` what the symbolic map's other subfields
     *  hold. BMS decides from them and the map what is sent. */
    public void sendMap(String map, String mapset, Object screen, MapSubfields subfields, String... options) {
        List<String> opts = new ArrayList<>(List.of(options));
        Collections.sort(opts);
        MapSubfields sub = subfields == null ? new MapSubfields() : subfields;
        event("SEND-MAP", "map", map, "mapset", mapset, "screen", screen, "options", opts, "subfields", sub.fields,
                "cursor", sub.cursorOffset);
    }

    public void sendMap(String map, String mapset, Object screen, String... options) {
        sendMap(map, mapset, screen, null, options);
    }

    /** The symbolic map's subfields besides the data (#4001), as the program sets them: the attribute byte
     *  (`<f>A`), extended colour and highlight (`<f>C`, `<f>H`) -- the EBCDIC byte values (DFHBMPRO = 0x60,
     *  DFHRED = 0xF2), never characters -- and the length (`<f>L`: -1 asks for the cursor, with the CURSOR
     *  option). `cursorAt` is CURSOR(offset). */
    public static final class MapSubfields {
        private final Map<String, Map<String, Integer>> fields = new LinkedHashMap<>();
        private Integer cursorOffset;

        public MapSubfields attr(String field, int value) {
            return set(field, "attr", value & 0xFF);
        }

        public MapSubfields color(String field, int value) {
            return set(field, "color", value & 0xFF);
        }

        public MapSubfields hilight(String field, int value) {
            return set(field, "hilight", value & 0xFF);
        }

        public MapSubfields length(String field, int value) {
            return set(field, "length", value);
        }

        /** MOVE -1 TO the field's length: symbolic cursor positioning. */
        public MapSubfields cursor(String field) {
            return length(field, -1);
        }

        public MapSubfields cursorAt(int offset) {
            this.cursorOffset = offset;
            return this;
        }

        private MapSubfields set(String field, String key, int value) {
            fields.computeIfAbsent(field, f -> new LinkedHashMap<>()).put(key, value);
            return this;
        }
    }

    /** SEND TEXT FROM(text): LENGTH is the text's own, no options. */
    public void sendText(String text) {
        sendText(text, text == null ? 0 : text.length());
    }

    /** SEND TEXT FROM(text) LENGTH(length) with its options (ERASE, FREEKB, ALARM, ...), as the program
     *  passed them: `text` is the FROM data, not the formatted screen. */
    public void sendText(String text, int length, String... options) {
        List<String> opts = new ArrayList<>(List.of(options));
        Collections.sort(opts);
        event("SEND-TEXT", "text", text, "length", length, "options", opts);
    }

    /** RETURN TRANSID(transid) COMMAREA(commarea): the task ends; `transid` null for a plain RETURN. The
     *  COMMAREA is its whole record. */
    public void returnTransid(String transid, Object commarea) {
        returnTransid(transid, commarea, null);
    }

    /** RETURN TRANSID(transid) COMMAREA(commarea) LENGTH(length): the next task's EIBCALEN is `length`
     *  (null: the whole record). Below level 1 (#4004) it returns to the linking program instead: the event
     *  shows the LINK COMMAREA as that program now sees it. */
    public void returnTransid(String transid, Object commarea, Integer length) {
        if (level > 1) {
            event("RETURN", "level", level, "caller_commarea", snapshot.apply(linkCommarea), "length", linkLength);
        } else {
            event("RETURN", "transid", transid, "commarea", snapshot.apply(commarea), "length",
                    commarea == null ? null : length);
        }
        ended = true;
    }

    /** XCTL PROGRAM(program) COMMAREA(commarea), the COMMAREA being its whole record. */
    public String xctl(String program, Object commarea) {
        return xctl(program, commarea, null);
    }

    /** XCTL PROGRAM(program) COMMAREA(commarea) LENGTH(length) (IBM, EXEC CICS XCTL): the program ends, and the
     *  target runs at the same level (#4004) on a copy of LENGTH bytes -- all of them, even past the end of the
     *  item (#4008). It fails, and the program goes on, with LENGERR (RESP2 11) for a LENGTH outside 0-32763 or
     *  PGMIDERR (RESP2 1) for a program the CSD does not define; the result is the condition. */
    public String xctl(String program, Object commarea, Integer length) {
        String resp = "NORMAL";
        Integer resp2 = null;
        if (commarea != null && length != null && (length < 0 || length > 32763)) {
            resp = "LENGERR";
            resp2 = 11;
        } else if (programs != null && !programs.defined(program)) {
            resp = "PGMIDERR";
            resp2 = 1;
        }
        event("XCTL", "program", program, "length", commarea == null ? Integer.valueOf(0) : length, "commarea",
                snapshot.apply(commarea), "resp", resp, "resp2", resp2);
        if ("NORMAL".equals(resp)) {
            xctlTarget = program;
            xctlCommarea = commarea;
            xctlLength = commarea == null ? Integer.valueOf(0) : length;
            ended = true;
        }
        return resp;
    }

    /** HANDLE ABEND LABEL(label) (#3989, IBM EXEC CICS HANDLE ABEND): this program level's abend exit, active
     *  from now on. An abend at this level or below it (a program it LINKs to) goes to the first active exit
     *  from the abending level upward; see abend. */
    public void handleAbend(String label) {
        exitLabel = label;
        exitActive = true;
    }

    /** HANDLE ABEND CANCEL: this level's exit is deactivated. */
    public void handleAbendCancel() {
        exitActive = false;
    }

    /** HANDLE ABEND RESET: the exit cancelled, or taken, is active again. */
    public void handleAbendReset() {
        if (exitLabel != null) {
            exitActive = true;
        }
    }

    /** PUSH HANDLE (#3989): saves this level's HANDLE ABEND state and suspends it (the program saves its own
     *  HANDLE CONDITION / IGNORE CONDITION state, which it ports itself). NORMAL. */
    public String pushHandle() {
        pushedExits.push(new Object[] {exitLabel, exitActive});
        exitLabel = null;
        exitActive = false;
        return "NORMAL";
    }

    /** POP HANDLE: restores the HANDLE ABEND state last pushed; INVREQ when none was. */
    public String popHandle() {
        if (pushedExits.isEmpty()) {
            return "INVREQ";
        }
        Object[] saved = pushedExits.pop();
        exitLabel = (String) saved[0];
        exitActive = (Boolean) saved[1];
        return "NORMAL";
    }

    /** EXEC CICS ABEND ABCODE(abcode) (#3989: with the exit search): CICS looks for an active HANDLE ABEND exit
     *  from this level upward. Returns the label to go on at when this program's own exit takes the abend (it
     *  is deactivated as it gets control); null when the program must stop now -- `return` from runTask --
     *  because an exit of a linking program takes it (that program's link then reports it: abendExit()) or
     *  none does and the task is terminated. */
    public String abend(String abcode) {
        return abend(abcode, "command", null, false);
    }

    /** EXEC CICS ABEND ABCODE(abcode) CANCEL: no exit is taken, the task is terminated. Returns null. */
    public String abendCancel(String abcode) {
        return abend(abcode, "command", null, true);
    }

    /** A condition the program neither handled nor ignored (#4003): CICS's default action abends the task
     *  with the condition's code (abcodeFor), with the same exit search and result as abend. */
    public String abendOnCondition(String condition) {
        return abend(abcodeFor(condition), "condition", condition, false);
    }

    /** An abend that a HANDLE ABEND LABEL exit took (#4003), named by the port itself: `label` in `program`;
     *  the task goes on there. Prefer handleAbend + abend / abendOnCondition, which search the exits. */
    public void abendToExit(String abcode, String cause, String condition, String program, String label) {
        record(abcode, cause, condition, program, label);
    }

    /** After a LINK returned (#3989): the label of this program's HANDLE ABEND exit when an abend below took
     *  it -- go on at that label -- else null. Read once: it is cleared. When the LINK returns with neither
     *  this nor NORMAL completion (ended() is true), the task was terminated or unwound past this level. */
    public String abendExit() {
        String label = unwoundTo;
        unwoundTo = null;
        return label;
    }

    private String abend(String code, String cause, String condition, boolean cancel) {
        CicsTask at = null;
        for (CicsTask t = this; t != null && !cancel; t = t.parent) {
            if (t.exitActive) {
                at = t;
                break;
            }
        }
        if (at == null) {
            record(code, cause, condition, null, null);
            for (CicsTask t = this; t != null; t = t.parent) {
                t.ended = true;
            }
            return null;
        }
        at.exitActive = false;  // "the exit is deactivated when it gets control"
        record(code, cause, condition, at.program, at.exitLabel);
        if (at == this) {
            return exitLabel;
        }
        for (CicsTask t = this; t != at; t = t.parent) {
            t.ended = true;  // the levels below the exit are gone
        }
        at.unwoundTo = at.exitLabel;
        return null;
    }

    /** ASSIGN ABCODE: the task's current abend code, blanks while there has been none. */
    public String abcode() {
        return root().abcode;
    }

    private CicsTask root() {
        return parent == null ? this : parent.root();
    }

    /** The abend code of an unhandled condition (IBM's AEIx / AEYx codes, the AEIA topic). */
    public static String abcodeFor(String condition) {
        return switch (condition) {
            case "NOTFND" -> "AEIM";
            case "LENGERR" -> "AEIV";
            case "ITEMERR" -> "AEIZ";
            case "QIDERR" -> "AEYH";
            case "MAPFAIL" -> "AEI9";
            case "ENDDATA" -> "AEI2";
            case "PGMIDERR" -> "AEI0";
            case "INVREQ" -> "AEIP";
            default -> throw new IllegalArgumentException("no abend code known for condition " + condition);
        };
    }

    private void record(String code, String cause, String condition, String program, String label) {
        root().abcode = code;
        Map<String, Object> e = new LinkedHashMap<>();
        e.put("event", "ABEND");
        e.put("abcode", code);
        e.put("cause", cause);
        if (condition != null) {
            e.put("condition", condition);
        }
        e.put("outcome", program == null ? "terminated" : "exit");
        if (program != null) {
            e.put("exit", Map.of("program", program, "label", label));
        } else {
            ended = true;
        }
        add(e);
    }

    public boolean ended() {
        return ended;
    }

    public List<Map<String, Object>> events() {
        return Collections.unmodifiableList(events);
    }

    private void event(String kind, Object... kv) {
        Map<String, Object> e = new LinkedHashMap<>();
        e.put("event", kind);
        for (int i = 0; i < kv.length; i += 2) {
            e.put((String) kv[i], kv[i + 1]);
        }
        add(e);
    }

    private void add(Map<String, Object> e) {
        if (program != null) {
            e.put("issuer", program);  // #4004: the program issuing the command, at whichever level
        }
        events.add(e);
    }
}
"""


@dataclass
class Dto:
    name: str
    javadoc: list[str]  # the record: its first line, then its notes
    body: list[str]
    requires_list: bool
    uses: list[str] = field(default_factory=list)  # one line per program that receives it
    methods: Any = None  # (is_record) -> method lines, e.g. a composite COMMAREA's fromPrefix (#3655)
    facts: list[dict] = field(default_factory=list)

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
    sections: dict[str, Any] = field(default_factory=dict)


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
        trace: TraceLog | None = None,
    ) -> None:
        self.package = package
        self.names = names if names is not None else ClassNames()  # shared with the other forges
        self.target = target or JavaTarget()
        self.trace = trace
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
        # A copybook record continued by a program's own entries (COPY COCOM01Y, then COTRN01C's 05 CDEMO-CT01-INFO)
        # is extended whether or not the layout says so: an unpacked COMMAREA's fields carry the files they come
        # from. Named after its owner it keeps its name whatever else the estate holds -- numbered, it was renamed
        # each time another program's extension appeared, and every port naming it stopped compiling.
        extended = layout.get("extended") or any(f.get("file") not in (None, file) for f in layout.get("fields", []))
        shared = file not in self.program_files and not extended and record.upper() != "DFHCOMMAREA"
        # A copybook record is named alone; a program's own record after the program declaring it
        # (MENU's WS-COMM -> MenuWsComm, whichever program receives it); an extended copy after its owner.
        declarer = self._file_cls.get(file) if not extended else None
        name = java_class_base(record) if shared else (declarer or owner_cls) + java_class_base(record)
        base, n = name, 1
        while name in self.dtos or name in self.names:
            n += 1
            name = f"{base}{n}"
        self.names.claim(name)
        body, requires_list = _field_lines(layout)
        dto_facts = [
            {
                "source": f.get("file"),
                "section": "interface",
                "ledger_field": "commarea",
                "field_testing": "untested",
                "name": f.get("name"),
                "offset": f.get("offset"),
                "bytes": f.get("bytes"),
            }
            for f in layout.get("fields", [])
            if f.get("name") and f.get("name").upper() != "FILLER"
        ]
        self.dtos[name] = Dto(name, javadoc, body, requires_list, [use] if use else [], facts=dto_facts)
        self._by_signature[signature] = name
        return name

    def _record_doc(self, record: str, file: str, layout: dict, status: str) -> list[str]:
        width = f"{layout['bytes']} bytes" if layout.get("bytes") is not None else "width unknown"
        kind = "PL/I structure" if layout.get("dialect") == "pli" else "COBOL record"  # #3720
        doc = [f"{kind} {record} ({file}), {width}, from GitGalaxy's verified skeleton."]
        if layout.get("extended"):
            doc.append("The program continues this copied record past its COPY: the layout is the program's own.")
        if layout.get("unexpanded"):
            missing = ", ".join(layout["unexpanded"])
            if layout.get("dialect") == "pli":  # #3728: a PL/I structure's %INCLUDE inside its declaration
                doc.append(f"TODO: %INCLUDE members not found in the repository: {missing}.")
            else:
                doc.append(f"TODO: COPY members not found in the repository: {missing}.")
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
        prog.sections = sections

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
            elif commarea.get("basis") == "parameter":  # #3720: a PL/I main procedure's parameter area
                use = f"The COMMAREA {cls} receives as its main procedure's parameter ({commarea['record']})."
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
        sources = {}
        for name, d in sorted(self.dtos.items()):
            sources[name] = render_dto_class(
                f"{self.package}.{DTO_SUBPACKAGE}",
                name,
                d.body,
                d.requires_list,
                self.target,
                javadoc=d.doc(),
                methods=d.methods,
            )
            if self.trace:
                file_path = java_path(self.package, DTO_SUBPACKAGE, name)
                # DTO class facts
                class_facts = [
                    {"source": use, "section": "interface", "ledger_field": "commarea", "field_testing": "untested"}
                    for use in d.uses
                ]
                self.trace.record(file_path, "Class", "commarea-dto", class_facts)

                # DTO fields
                for fact in d.facts:
                    # name @offset+bytes and its copybook file
                    field_fact = {
                        "source": fact["source"],
                        "section": fact["section"],
                        "item": f"{fact['name']} @{fact['offset']}+{fact['bytes']}",
                    }
                    field_var = java_identifier(fact["name"])
                    self.trace.record(file_path, f"{name}#{field_var}", "dto-field", [field_fact])
        return sources

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
            java += [f" * {todo}" for todo in commarea_alternative_todos(c)]
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
        todos = []
        if prog.commarea:
            todos += commarea_alternative_todos(prog.commarea)
        elif prog.commarea_gap:
            todos.append(f"TODO: no COMMAREA layout: {prog.commarea_gap}.")

        for txn in prog.transactions:
            defs = "; ".join(
                f"{d.get('defined_in')}:{d.get('line')}" + (f" group {d['group']}" if d.get("group") else "")
                for d in txn["definitions"]
            )
            java.append(f"    /** CICS transaction {txn['transid']} -> {cls} (CSD {defs}). */")
            java.append(f'    @PostMapping("/transactions/{txn["segment"]}")')
            java += self._endpoint(f"transaction{txn['segment']}", svc, "handleTransaction",
                                   json.dumps(txn["transid"]), req, resp)  # fmt: skip
            if self.trace:
                facts = [
                    {
                        "source": f"{d.get('defined_in')}:{d.get('line')}",
                        "section": "entry_transactions",
                        "ledger_field": "entry_transactions",
                        "field_testing": prog.status.get("entry_transactions", "untested"),
                    }
                    for d in txn["definitions"]
                ]
                self.trace.record(
                    java_path(self.package, "controller", f"{cls}Controller"),
                    f"{cls}Controller#transaction{txn['segment']}",
                    "controller-endpoint",
                    facts,
                    todos,
                )
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
            if self.trace:
                facts = [
                    {
                        "source": f"{r['caller']}:{r['line']}",
                        "section": "commarea_contracts",
                        "ledger_field": "link_xctl",
                        "field_testing": "untested",
                    }
                    for r in prog.links
                ]
                self.trace.record(
                    java_path(self.package, "controller", f"{cls}Controller"),
                    f"{cls}Controller#link",
                    "controller-endpoint",
                    facts,
                    todos,
                )
        if (prog.channel_in or prog.channel_out) and (req, resp) != (prog.channel_in, prog.channel_out):
            java.append("    /** The program's channel: its GET CONTAINERs in, its PUT CONTAINERs out. */")
            java.append('    @PostMapping("/channel")')
            java += self._endpoint("channel", svc, "handleChannel", None, prog.channel_in, prog.channel_out)
            if self.trace:
                facts = []
                self.trace.record(
                    java_path(self.package, "controller", f"{cls}Controller"),
                    f"{cls}Controller#channel",
                    "controller-endpoint",
                    facts,
                    todos,
                )
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

    def runtime_sources(self) -> dict[str, str]:
        """#3754: CicsTask (package <pkg>.cics), when there is a CICS program to run as a task (#4004: or at a
        LINK / XCTL level)."""
        if not self.programs:
            return {}
        return {"CicsTask": CICS_TASK_JAVA.replace("__PACKAGE__", self.package)}

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
        # #3754: the whole task -- the port's target, and what the equivalence harness drives; #4004: a program
        # reached only by LINK / XCTL runs the same way, at its level
        imports.append(f"import {self.package}.cics.CicsTask;")
        what = ("One pseudo-conversational task of this program (#3754)" if prog.transactions
                else "This program's run at a LINK / XCTL level (#4004): task.level(), task.eibcalen()")  # fmt: skip
        methods += [
            f"    /** {what}. TODO: [AI AGENT] port the PROCEDURE",
            "     *  DIVISION: read task.hasCommarea() / task.commarea(..) / task.aid() / task.receive(map, ..),",
            "     *  and record what the program does through the task -- sendMap, sendText, returnTransid,",
            "     *  link, xctl, abend -- in the order it does it. */",
            "    public void runTask(CicsTask task) {",
            f'        log.info("{prog.cls}: runTask");',
            "        // TODO: [AI AGENT] port the PROCEDURE DIVISION into this task",
            "    }\n",
        ]
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
