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

from gitgalaxy.tools.cobol_to_java.cics_task_conditions import CONDITIONS_JAVA
from gitgalaxy.tools.cobol_to_java.cics_task_containers import CONTAINERS_JAVA
from gitgalaxy.tools.cobol_to_java.cics_task_faults import FAULTS_JAVA
from gitgalaxy.tools.cobol_to_java.cics_task_filecontrol import FILECONTROL_JAVA
from gitgalaxy.tools.cobol_to_java.cics_task_taskcontrol import TASKCONTROL_JAVA
from gitgalaxy.tools.cobol_to_java.cics_task_tdqueues import TDQUEUES_JAVA
from gitgalaxy.tools.cobol_to_java.cics_task_time import TIME_JAVA
from gitgalaxy.tools.cobol_to_java.cics_task_tsqueues import TSQUEUES_JAVA
from gitgalaxy.tools.cobol_to_java.cics_task_web import WEB_REQUEST_JAVA, WEB_SESSION_JAVA
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


def commarea_codec(cls: str, layout: dict, records: str, dbcs_page: str | None = None) -> Any:
    """#4449: `toCommarea()` / `fromCommarea(byte[])` -- the COMMAREA DTO as the bytes of its layout, each field at its
    COBOL offset, through the entities' CobolRecords (`records`: its qualified name) in the record charset -- as a
    `methods(is_record)` callable, or None when the layout cannot be laid out exactly: its width unknown, an OCCURS
    table, a PL/I item, an item the codec does not encode (COMP-1 / COMP-2 / POINTER, DISPLAY-1 without a code page),
    or items that overlap (REDEFINES: which one holds the bytes is the program's choice, not the layout's).
    fromCommarea reads the first bytes of a record at least as wide -- what a program reading the passed bytes
    through its own record sees -- and refuses a shorter one: those bytes were never passed."""
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_repository_forge import (
        RepositoryForge,
        _codec_get,
        _codec_kind,
        _codec_put,
    )

    width = layout.get("bytes")
    raw = layout.get("fields", [])
    if not width or not raw or any(f.get("dialect") == "pli" or f.get("bits") is not None for f in raw):
        return None
    fields = RepositoryForge._fields(layout)
    if not fields:
        return None
    end = 0
    for f in sorted(fields, key=lambda f: f.offset if f.offset is not None else -1):
        kind = _codec_kind(f) if f.offset is not None and f.bytes else None
        if f.occurs or kind is None or (kind == "display1" and not dbcs_page) or f.offset < end:
            return None
        end = f.offset + f.bytes
    if end > width:
        return None

    def q(code: str) -> str:
        return code.replace("CobolRecords.", f"{records}.")

    def methods(is_record: bool) -> list[str]:
        store = [f"        java.nio.charset.Charset text = {records}.charset();",
                 f"        byte[] rec = {records}.blank({width}, text);"]  # fmt: skip
        for f in fields:
            put = q(_codec_put(f, f.java, dbcs_page))
            store.append(f"        {put};" if f.jtype == "String" else f"        if ({f.java} != null) {{ {put}; }}")
        # a number left unset is stored as spaces (no digits to write), and read back as unset: never decoded
        gets = [q(_codec_get(f, dbcs_page)) if f.jtype == "String"
                else f"unset(rec, {f.offset}, {f.bytes}, text) ? null : {q(_codec_get(f, dbcs_page))}"
                for f in fields]  # fmt: skip
        if is_record:
            load = [
                f"        return new {cls}(",
                *[f"                {g}," for g in gets[:-1]],
                f"                {gets[-1]});",
            ]
        else:
            load = [f"        {cls} r = new {cls}();", *[f"        r.{f.java} = {g};" for f, g in zip(fields, gets, strict=True)],
                    "        return r;"]  # fmt: skip
        return [
            "",
            f"    /** #4449: this COMMAREA as the {width} bytes of its layout -- each field at its COBOL offset, FILLER and",
            "     *  an unset field as spaces -- in the record charset (CobolRecords.charset()). */",
            "    public byte[] toCommarea() {",
            *store,
            "        return rec;",
            "    }",
            "",
            f"    /** #4449: the COMMAREA these bytes are, read through this layout: the first {width} of `rec` -- what a",
            "     *  program reading another program's record through its own sees (a number of spaces is unset: null).",
            "     *  Fewer were never passed: refused. */",
            f"    public static {cls} fromCommarea(byte[] rec) {{",
            f"        if (rec.length < {width}) {{",
            f'            throw new IllegalArgumentException(rec.length + " bytes do not fill {cls}\'s {width}-byte record");',
            "        }",
            f"        java.nio.charset.Charset text = {records}.charset();",
            *load,
            "    }",
            "",
            "    /** Whether `length` bytes at `offset` are all spaces: a number toCommarea left unset. */",
            "    private static boolean unset(byte[] rec, int offset, int length, java.nio.charset.Charset text) {",
            '        byte space = " ".getBytes(text)[0];',
            "        for (int i = offset; i < offset + length; i++) {",
            "            if (rec[i] != space) {",
            "                return false;",
            "            }",
            "        }",
            "        return true;",
            "    }",
        ]  # fmt: skip

    return methods


def _expanded_pic(pic: str | None) -> str:
    """`X(08)` -> `XXXXXXXX`: a PICTURE as the characters it repeats, so equal pictures compare equal."""
    p = re.sub(r"\s+", "", (pic or "").upper())
    return re.sub(r"(.)\((\d+)\)", lambda m: m.group(1) * int(m.group(2)), p)


def layout_partition(layout: dict) -> tuple:
    """#4449: how a record layout cuts its bytes -- its width, and each item's offset, width, PICTURE, USAGE, SIGN and
    OCCURS (FILLER as FILLER), names left out: two records with the same partition are the same bytes read the same
    way, so a conversion between them by layout loses nothing."""
    items = sorted(
        (f.get("offset") or 0, f.get("bytes") or 0, _expanded_pic(f.get("pic")),
         (f.get("usage") or "DISPLAY").upper(), f.get("sign"), f.get("occurs"),
         (f.get("name") or "FILLER").upper() == "FILLER")
        for f in layout.get("fields", [])
    )  # fmt: skip
    return (layout.get("bytes"), tuple(items))


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


# #4270 spec PR 4: the CICS command spec's tables (RESP values, abend codes), generated and committed beside this
# file by `python -m gitgalaxy.standards.cics regen`; emitted next to CicsTask, whose respName / abcodeFor (and
# DetCics's condition / resp) delegate to it.
CICS_SPEC_JAVA = Path(__file__).with_name("CicsSpec.java").read_text(encoding="utf-8")

# #3754: one CICS task, the runtime a program's runTask is written against.
CICS_TASK_JAVA = """package __PACKAGE__.cics;

import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.function.Consumer;
import java.util.function.Supplier;
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
    private byte[] linkArea;  // #4181 follow-up: the LINK COMMAREA's bytes, when the linking program passed them
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
    private Channel xctlChannel;                            // #4270: the channel an XCTL passed (null: none)
    private byte[] xctlArea;                                // #4806: the XCTL COMMAREA's bytes, when passed
    private Channel currentChannel;                         // #4270: the channel this program was passed
    private Map<String, Channel> channels = new HashMap<>();  // #4270: the channels in this program's scope, by name
    private java.util.Set<String> droppedChannels = java.util.Set.of();  // #4270: left behind by an XCTL
    private LocalDateTime now;                              // #4006: the virtual clock (the task's root)
    private List<StartData> retrieveData = List.of();
    private int retrieved;
    private boolean retrieveRefused;                        // #4270: a RETRIEVE raised ENVDEFERR (the root's)
    private boolean runChild;                               // #4270: a RUN TRANSID child task (the root's)
    private final Map<String, Object> resources = new HashMap<>();  // #4892: resource managers joined (the root's)
    private final List<Consumer<Boolean>> uowParticipants = new ArrayList<>();  // #4892: told as its unit of work ends
    private int children;                                   // #4270: the RUN TRANSID children it attached
    private final List<Child> kids = new ArrayList<>();     // #4950: those children, in RUN order (the root's)
    private long waited;                                    // #4950 (X18): the scheduler's clock, ms of waits (root's)
    private boolean dispatched;                             // #4950: a child its parent's wait dispatched (root's)
    private int depth;                                      // #5089: 0 for a task, its parent's + 1 for a RUN child (root's)
    private int replies;                                    // #4950: the reply channels FETCH CHANNEL named (root's)
    private final java.util.Set<String> ownWithData = new java.util.HashSet<>();  // #4270: own REQIDs with FROM
    private Map<String, LocalDateTime> unexpired = Map.of();
    private final Map<String, LocalDateTime> ownRequests = new HashMap<>();
    private String terminalInput;
    private boolean terminalRead;
    private String terminalRest;                            // #4413: input a RECEIVE NOTRUNCATE left (the task's root)
    private boolean endOfChain;                             // #4413: an LUTYPE2 terminal: input ends a chain (EOC)
    private TempStorage tempStorage = new TempStorage();
    private String abcode = "    ";
    private String termid;                                  // #3989: EIBTRMID (the task's root); null without one
    private boolean termidStated;                           // #5126: withTermid was called (null = stated: no terminal)
    private long taskNumber;                                 // #4270: EIBTASKN (the task's root), a stated fact
    private boolean exactCommarea;                          // #4270 (X23): the COMMAREA is EIBCALEN bytes, no more
    private String exitLabel;                               // #3989: this level's HANDLE ABEND LABEL
    private boolean exitActive;
    private final java.util.ArrayDeque<Object[]> pushedExits = new java.util.ArrayDeque<>();
    private String unwoundTo;                               // an abend below went to this level's exit
    private List<String[]> faultPlan = List.of();           // #4023 follow-up: injected conditions (the task's root)
    private java.nio.file.Path faultLog;
    private final java.util.Set<String> held = new java.util.HashSet<>();  // files a readForUpdate holds (the root's)
    private final Map<Integer, Object[]> updateTokens = new HashMap<>();  // #5078 (X52): token -> {file, key} (the root's)
    private int nextToken = 1;
    private boolean syncpointed;                                            // a SYNCPOINT committed (the root's)
    private boolean dplServer;                          // #4437: LINKed from outside the region (the root's)
    private Runnable rollbackHook;                                          // how a rollback undoes (the root's)
    private final Map<String, Integer> faultSeen = new HashMap<>();
    private Object returnedArea;                                             // #4343: the level-1 RETURN's COMMAREA
    private boolean bytesTaken;                                              // #4817: returnedBytes() was read
    private byte[] returnedBytes;                                            // #4817: its raw bytes
    private Integer returnedLength;                                          // #4449: its LENGTH (null: the whole record)

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

        /** #4950: the program a transaction runs -- a RUN TRANSID child's -- or null when the case does not run it
         *  (the child is then refused when its parent's wait would dispatch it). */
        default String program(String transid) {
            return null;
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

    private int transferResp2;  // #4986: the RESP2 of this program's last LINK / XCTL, as its event carries it

    /** #4986: EIBRESP2 / RESP2 after this program's last LINK or XCTL: the event's, so a planned fault's (PGMIDERR
     *  RESP2 3, NOTAUTH 101 ...) as well as the natural LENGERR 11 / PGMIDERR 1. */
    public int transferResp2() {
        return transferResp2;
    }

    /** LINK PROGRAM(program) COMMAREA(commarea) LENGTH(length) (#4004, IBM EXEC CICS LINK): LENGERR (RESP2
     *  11) for a length outside 0-32763, PGMIDERR (RESP2 1) for a program the CSD does not define; else the
     *  program runs at the next level on `commarea` itself -- what it changes, the caller sees -- then any
     *  program it XCTLs to, and control returns here. The handlers of this program are not the callee's. */
    public String link(String program, Object commarea, int length) {
        return link(program, commarea, length, null);
    }

    /** LINK with the COMMAREA's bytes as well (#4181 follow-up): the area is passed by reference, so a program
     *  given `area` reads and writes those bytes as its DFHCOMMAREA -- every byte, the ones its contract DTO does
     *  not name too (a caller's record laid out unlike the target's contract). The event carries them (base64). */
    public String link(String program, Object commarea, int length, byte[] area) {
        return link(program, commarea, length, area, null);
    }

    private String link(String program, Object commarea, int length, byte[] area, Channel linkChannel) {
        linkAreaBack = false;
        boolean abendedHere = false;
        String resp = "NORMAL";
        Integer resp2 = null;
        int len = commarea == null ? 0 : length;
        if (commarea != null && (length < 0 || length > 32763)) {
            resp = "LENGERR";
            resp2 = 11;
        } else if (programs == null || !programs.defined(program)) {
            resp = "PGMIDERR";
            resp2 = 1;
        } else {
            int[] planned = root().injected("LINK", program.stripTrailing());  // #4648: as an XCTL's (#4049)
            if (planned != null) {
                resp = respName(planned[0]);
                resp2 = planned[1];
                abendedHere = root().ended || root().unwoundTo != null;  // #6271 (X70): `LINK PROGRAM 1 -1 0 ABCODE`
            }
        }
        transferResp2 = resp2 == null ? 0 : resp2;  // #4986: EIBRESP2 is the event's, a planned fault's too
        event("LINK", "target", program, "length", len, "commarea", snapshot.apply(commarea), "resp", resp,
                "resp2", resp2);
        if (area != null) {
            events.get(events.size() - 1).put("area", java.util.Base64.getEncoder().encodeToString(
                    java.util.Arrays.copyOf(area, Math.max(0, Math.min(len, area.length)))));
        }
        if (!"NORMAL".equals(resp) || abendedHere) {  // a planned abend: the task is at the exit or gone; the callee never runs
            return resp;
        }
        CicsTask callee = new CicsTask(this, level + 1, program, commarea, len, commarea);
        callee.invoker = this.program;
        callee.linkLength = len;
        callee.linkArea = area;
        callee.callerArea = area != null;  // #4816: that area is the caller's own storage, not a copy
        callee.linkedDto = commarea != null;  // #4956: its DTO is the caller's own object, not a copy
        callee.passChannel(linkChannel, java.util.Set.of());  // #4270: LINK CHANNEL (none: the callee has no channel)
        CicsTask linked = callee;
        for (int hop = 0; callee != null && hop < 32; hop++) {
            programs.run(callee.program, callee);
            if (callee.xctlTarget != null) {
                CicsTask prev = callee;
                String by = callee.program;
                callee = new CicsTask(this, level + 1, callee.xctlTarget, callee.xctlCommarea, callee.xctlLength,
                        commarea);
                callee.invoker = by;
                callee.passChannel(prev.xctlChannel, prev.inScope());  // #4270
                callee.linkLength = len;
                callee.linkArea = prev.xctlArea;  // #4806: the XCTL COMMAREA's bytes, the target's DFHCOMMAREA
            } else {
                if (!callee.ended) {
                    callee.returnTransid(null, null);  // a GOBACK is a RETURN
                }
                callee = null;
            }
        }
        // #4806: a program that took the bytes (linkArea) wrote back what it left in them, every byte -- the ones
        // its DTO cannot decode too (a PIC 9 holding spaces): they are the caller's COMMAREA as they are
        linkAreaBack = area != null && linked.linkAreaTaken;
        return resp;
    }

    private boolean linkAreaBack;  // #4806: whether the last LINK's program took the COMMAREA's bytes

    /** #4806: whether the program the last LINK ran took the COMMAREA's bytes (linkArea): then those bytes are what
     *  it left in the caller's COMMAREA (IBM: the area is passed by address), and its DTO -- which reads a numeric
     *  field holding spaces as a number -- is not written back over them. */
    public boolean linkAreaBack() {
        return linkAreaBack;
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
                next.passChannel(current.xctlChannel, current.inScope());  // #4270
                next.linkArea = current.xctlArea;  // #4806: the XCTL COMMAREA's bytes, the target's DFHCOMMAREA
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
    private java.util.Map<String, String> tdTypes;
    private java.util.Map<String, java.util.Map<String, String>> tdAttrs;  // #5168: each queue's other CSD attributes
    private final java.util.Map<String, java.util.ArrayDeque<String>> tdUow = new java.util.LinkedHashMap<>();  // #5168
    private final java.util.Set<String> tdPhysical = new java.util.LinkedHashSet<>();

    /** The region's identity (ASSIGN APPLID / SYSID): a deployment fact, set by whoever runs the task. */
    public CicsTask withRegion(String applid, String sysid) {
        this.applid = applid;
        this.sysid = sysid;
        return this;
    }

    // #4270 slice 3: ASSIGN STARTCODE / USERID / FACILITY / SCRNHT / SCRNWD (IBM CICS TS, EXEC CICS ASSIGN), each
    // from a fact whoever runs the task states; unstated, the option is refused, never guessed.
    private String startcode;
    private String userid;
    private int[] screen;

    /** How the task was started (ASSIGN STARTCODE): "TD" terminal input or permanent transid, "S" a START that
     *  "did not pass data in the FROM option", "SD" one that did; null, not stated (refused). */
    public CicsTask withStartcode(String startcode) {
        this.startcode = startcode;
        return this;
    }

    /** The task's user (ASSIGN USERID): with no user "explicitly signed on, CICS returns the default user ID". */
    public CicsTask withUserid(String userid) {
        this.userid = userid;
        return this;
    }

    /** The 3270 screen of the task's terminal (ASSIGN SCRNHT / SCRNWD): rows, columns. */
    public CicsTask withScreen(int height, int width) {
        this.screen = new int[] {height, width};
        return this;
    }

    // #4415 slice 1: INQUIRE / SET TERMINAL UCTRANST (IBM CICS TS, EXEC CICS INQUIRE TERMINAL, SET TERMINAL): the CVDAs
    // UCTRAN 450, NOUCTRAN 451, TRANIDONLY 452. The terminal's value comes "from the UCTRAN option of the associated
    // TYPETERM definition" -- a fact whoever runs the task states, never guessed (register X26).
    private String uctranst;
    private boolean uctranstSet;

    /** The task's terminal's UCTRANST (UCTRAN, NOUCTRAN or TRANIDONLY); null, not stated (INQUIRE is refused). */
    public CicsTask withUctranst(String uctranst) {
        if (uctranst != null && !UCTRANST_NAMES.contains(uctranst)) {
            throw new IllegalArgumentException("UCTRANST " + uctranst + " is not UCTRAN, NOUCTRAN or TRANIDONLY");
        }
        this.uctranst = uctranst;
        return this;
    }

    // IBM's CVDAs for UCTRANST, in order: UCTRAN 450, NOUCTRAN 451, TRANIDONLY 452
    private static final List<String> UCTRANST_NAMES = List.of("UCTRAN", "NOUCTRAN", "TRANIDONLY");
    private static final int[] UCTRANST_CVDAS = {450, 451, 452};

    private static int uctranstCvda(String name) {
        return UCTRANST_CVDAS[UCTRANST_NAMES.indexOf(name)];
    }

    /** The terminal INQUIRE / SET TERMINAL names, as {RESP, RESP2} when it is no terminal of the region (TERMIDERR,
     *  RESP2 `resp2`); refused (not modelled) for a defined terminal other than the task's, whose UCTRANST nobody
     *  stated; null for the task's own. */
    private int[] terminalCheck(String terminal, int resp2) {
        String t = terminal.strip();
        CicsTask r = root();
        Programs known = programs != null ? programs : r.programs;
        if (known != null && !known.terminal(t)) {
            return new int[] {11, resp2};
        }
        if (!t.equals(r.termid)) {
            throw refused("UCTRANST of terminal " + t + ", not the task's terminal");
        }
        return null;
    }

    /** INQUIRE TERMINAL(t) UCTRANST(area): {RESP, RESP2, CVDA}. TERMIDERR RESP2 1 for "The named terminal cannot be
     *  found". Unstated, refused. */
    public int[] inquireUctranst(String terminal) {
        int[] bad = terminalCheck(terminal, 1);
        if (bad != null) {
            return new int[] {bad[0], bad[1], 0};
        }
        if (root().uctranst == null) {
            throw new IllegalStateException("INQUIRE TERMINAL UCTRANST: the terminal's UCTRANST is not stated (withUctranst)");
        }
        return new int[] {0, 0, uctranstCvda(root().uctranst)};
    }

    /** SET TERMINAL(t) UCTRANST(cvda): {RESP, RESP2}. TERMIDERR RESP2 23 ("The named terminal cannot be found"); INVREQ
     *  RESP2 43 for an invalid CVDA. The change is the task's view of its terminal from then on; a terminal RECEIVE
     *  after it is refused (IBM does not say when the change takes effect). */
    public int[] setUctranst(String terminal, long cvda) {
        int[] bad = terminalCheck(terminal, 23);
        if (bad != null) {
            return bad;
        }
        int at = -1;
        for (int i = 0; i < UCTRANST_CVDAS.length; i++) {
            if (UCTRANST_CVDAS[i] == cvda) {
                at = i;
            }
        }
        if (at < 0) {
            return new int[] {16, 43};
        }
        CicsTask r = root();
        r.uctranst = UCTRANST_NAMES.get(at);
        r.uctranstSet = true;
        return new int[] {0, 0};
    }

    private void inputAfterUctranstSet() {
        if (root().uctranstSet) {
            throw refused("a terminal RECEIVE after SET TERMINAL UCTRANST (IBM does not say when the change takes effect)");
        }
    }

    /** EXEC CICS BIF DEEDIT FIELD(f) LENGTH(n)'s condition: LENGERR (22) "if the LENGTH value is less than 1"; IBM lists
     *  no RESP2 (0). */
    public static int deeditResp(int length) {
        return length < 1 ? 22 : 0;
    }

    // #4415 slice 2 (register X29): INQUIRE ASSOCIATION(EIBTASKN) ODAPPLID / ODUSERID / ODFACILNAME / ODNETWORKID /
    // ODFACILTYPE (IBM CICS TS, INQUIRE ASSOCIATION). IBM's pages do not say what the origin of a terminal-started
    // task holds, so the five values are a fact whoever runs the task states, never guessed.
    private String[] origin;

    // IBM's CVDAs for ODFACILTYPE (API Reference, "CVDAs and numeric values"; det/cvda.py)
    private static final Map<String, Integer> FACILTYPE_CVDAS = Map.ofEntries(
            Map.entry("APPC", 124), Map.entry("ASRUNTRAN", 1209), Map.entry("BRIDGE", 935), Map.entry("EVENT", 334),
            Map.entry("IIOP", 1097), Map.entry("IPECI", 936), Map.entry("IPIC", 1089), Map.entry("JVMSERVER", 1193),
            Map.entry("LU61", 125), Map.entry("MRO", 938), Map.entry("NODEJSAPP", 1215), Map.entry("NONE", 496),
            Map.entry("RRSUR", 939), Map.entry("RZINSTOR", 940), Map.entry("SCHEDULER", 941), Map.entry("SOCKET", 942),
            Map.entry("START", 635), Map.entry("STARTTERM", 943), Map.entry("TERMINAL", 213), Map.entry("TRANDATA", 944),
            Map.entry("WEB", 945), Map.entry("XMRUNTRAN", 946));

    /** The origin data of the task's association data: 8-character values and the facility type's CVDA. */
    public record Origin(String applid, String userid, String facilname, String networkid, int faciltype) {
    }

    /** The task's origin data (INQUIRE ASSOCIATION ODAPPLID, ODUSERID, ODFACILNAME, ODNETWORKID, ODFACILTYPE): the
     *  facility type is one of IBM's CVDA names. Not stated (never called), INQUIRE ASSOCIATION is refused. */
    public CicsTask withOrigin(String applid, String userid, String facilname, String networkid, String faciltype) {
        if (!FACILTYPE_CVDAS.containsKey(faciltype)) {
            throw new IllegalArgumentException("ODFACILTYPE " + faciltype + " is not one of IBM's facility types");
        }
        this.origin = new String[] {applid, userid, facilname, networkid, faciltype};
        return this;
    }

    /** INQUIRE ASSOCIATION(EIBTASKN) ...: the task's own origin data (the task exists and no security is checked, so
     *  neither TASKIDERR nor NOTAUTH arises). Unstated, refused. */
    public Origin inquireAssociation() {
        String[] o = root().origin;
        if (o == null) {
            throw new IllegalStateException("INQUIRE ASSOCIATION: the task's origin data is not stated (withOrigin)");
        }
        java.util.function.Function<String, String> pad = v -> String.format(java.util.Locale.ROOT, "%-8.8s", v);
        return new Origin(pad.apply(o[0]), pad.apply(o[1]), pad.apply(o[2]), pad.apply(o[3]), FACILTYPE_CVDAS.get(o[4]));
    }

    // #4270 zECS (register X32): INQUIRE URIMAP's browse and WRITE OPERATOR (IBM CICS TS, INQUIRE URIMAP, "Browsing
    // resource definitions", WRITE OPERATOR). The installed URIMAP definitions, in the region's order, are a fact whoever
    // runs the task states, never guessed; the browse cursor belongs to the task.
    private java.util.List<String[]> urimaps;
    private int urimapBrowse = -1;
    private String[] urimapNow;

    /** The URIMAP definitions installed in the region, each {name, transaction, path}, in the order the region browses
     *  them. Not stated (never called), INQUIRE URIMAP is refused. */
    public CicsTask withUrimaps(java.util.List<String[]> defs) {
        this.urimaps = defs;
        return this;
    }

    private java.util.List<String[]> installedUrimaps() {
        java.util.List<String[]> d = root().urimaps;
        if (d == null) {
            throw refused("the installed URIMAP definitions are not stated (withUrimaps)");
        }
        return d;
    }

    /** INQUIRE URIMAP START: {RESP, RESP2} -- ILLOGIC (21) RESP2 1 when a browse is already in progress. */
    public int[] inquireUrimapStart() {
        CicsTask r = root();
        r.installedUrimaps();
        if (r.urimapBrowse >= 0) {
            return new int[] {21, 1};
        }
        r.urimapBrowse = 0;
        r.urimapNow = null;
        return new int[] {0, 0};
    }

    /** INQUIRE URIMAP NEXT: {RESP, RESP2}; the definition it returns is read by urimapName / urimapPath /
     *  urimapTransaction. END (83) RESP2 2 when there are no more. */
    public int[] inquireUrimapNext() {
        CicsTask r = root();
        java.util.List<String[]> d = r.installedUrimaps();
        if (r.urimapBrowse < 0) {
            throw refused("INQUIRE URIMAP NEXT or END with no browse started");
        }
        if (r.urimapBrowse >= d.size()) {
            return new int[] {83, 2};
        }
        r.urimapNow = d.get(r.urimapBrowse++);
        return new int[] {0, 0};
    }

    /** INQUIRE URIMAP(name), the direct form (#4768, X34): {RESP, RESP2} -- NOTFND (13) RESP2 3 "The URIMAP cannot be
     *  found" when the run states no installed definition of that name; the one found is read by urimapPath /
     *  urimapTransaction, as a browse NEXT's. */
    public int[] inquireUrimap(String name) {
        CicsTask r = root();
        String n = name == null ? "" : name.strip();
        for (String[] d : r.installedUrimaps()) {
            if (d[0].equals(n)) {
                r.urimapNow = d;
                return new int[] {0, 0};
            }
        }
        return new int[] {13, 3};
    }

    /** INQUIRE URIMAP END: {RESP, RESP2}; the browse is over. */
    public int[] inquireUrimapEnd() {
        CicsTask r = root();
        r.installedUrimaps();
        if (r.urimapBrowse < 0) {
            throw refused("INQUIRE URIMAP NEXT or END with no browse started");
        }
        r.urimapBrowse = -1;
        r.urimapNow = null;
        return new int[] {0, 0};
    }

    /** The URIMAP the last NEXT returned, blank-padded to IBM's lengths: the 8-character name, the 255-character PATH
     *  and the 4-character TRANSACTION (IBM does not state the padding of a short value: blanks). */
    public String urimapName() {
        return String.format(java.util.Locale.ROOT, "%-8.8s", root().urimapNow[0]);
    }

    public String urimapPath() {
        return String.format(java.util.Locale.ROOT, "%-255.255s", root().urimapNow[2]);
    }

    public String urimapTransaction() {
        return String.format(java.util.Locale.ROOT, "%-4.4s", root().urimapNow[1]);
    }

    /** WRITE OPERATOR TEXT(text) (IBM CICS TS, WRITE OPERATOR): a message to the system console, recorded with its text.
     *  A text IBM reformats (DFHnnnn / DFHaannnn: a CICS message) or splits into lines (over 113 characters) is refused.
     *  Returns the RESP (always NORMAL here: the WTO cannot fail in this region). */
    public int writeOperator(String text) {
        String t = text.stripTrailing();
        if (text.length() > 113 || t.matches("(?s)DFH([A-Za-z]{2})?[0-9]{4}.*")) {
            throw refused("WRITE OPERATOR text IBM reformats");
        }
        event("WRITE-OPERATOR", "text", text, "resp", "NORMAL");
        return 0;
    }

    // #4769 zECS (register X33): the document handler's DOCUMENT CREATE and DOCUMENT RETRIEVE (IBM CICS TS, EXEC CICS
    // DOCUMENT CREATE, DOCUMENT RETRIEVE). A document is the bytes the task built, named by a 16-byte DOCTOKEN CICS gives;
    // it lives as long as the task (every program the task LINKs to shares it). The installed DOCTEMPLATEs (name and the
    // text each yields) are a fact whoever runs the task states, never guessed.
    private java.util.Map<String, String> doctemplates;
    private final java.util.Map<String, byte[]> documents = new LinkedHashMap<>();
    private int documentSeq;

    /** The DOCTEMPLATE definitions installed in the region: name -> the text the template yields (whoever states it has
     *  applied the definition's own attributes, APPENDCRLF and TYPE). Not stated (never called), a CREATE of a TEMPLATE is
     *  refused. */
    public CicsTask withDoctemplates(java.util.Map<String, String> templates) {
        this.doctemplates = templates;
        return this;
    }

    /** DOCUMENT CREATE's outcome: RESP, RESP2 and the DOCTOKEN (null unless NORMAL). */
    public record DocumentCreated(int resp, int resp2, String doctoken) {
    }

    /** DOCUMENT RETRIEVE's outcome: RESP, RESP2, the LENGTH it returns (-1: none) and the data moved INTO (null: none). */
    public record DocumentData(int resp, int resp2, int length, byte[] data) {
    }

    private DocumentCreated newDocument(byte[] data) {
        CicsTask r = root();
        String token = String.format(java.util.Locale.ROOT, "GGDOC%011d", ++r.documentSeq);
        r.documents.put(token, data.clone());
        return new DocumentCreated(0, 0, token);
    }

    /** DOCUMENT CREATE DOCTOKEN with no source: an empty document. */
    public DocumentCreated documentCreateEmpty() {
        return newDocument(new byte[0]);
    }

    /** DOCUMENT CREATE TEXT / BINARY(data) LENGTH(length): the document is the data, unchanged. LENGERR RESP2 1 for a
     *  negative LENGTH (data is null then). */
    public DocumentCreated documentCreateData(byte[] data, int length) {
        if (length < 0 || data == null) {
            return new DocumentCreated(22, 1, null);
        }
        return newDocument(data);
    }

    /** DOCUMENT CREATE TEMPLATE(name): the text the installed DOCTEMPLATE of that name yields (a 48-byte name is
     *  blank-padded, so trailing blanks are not part of it), in the program's code page `cs`. NOTFND RESP2 3 for a
     *  template that is not installed. Symbols (&name;) and template commands (#set, #include, #echo) in the text are
     *  refused: the template language is not modelled. */
    public DocumentCreated documentCreateTemplate(String name, java.nio.charset.Charset cs) {
        java.util.Map<String, String> t = root().doctemplates;
        if (t == null) {
            throw refused("the installed document templates are not stated (withDoctemplates)");
        }
        String text = t.get(name.stripTrailing());
        if (text == null) {
            return new DocumentCreated(13, 3, null);
        }
        if (java.util.regex.Pattern.compile("(?is)#(set|include|echo)|&[A-Za-z][A-Za-z0-9._-]*;").matcher(text).find()) {
            throw refused("DOCUMENT CREATE TEMPLATE text with symbols or template commands");
        }
        return newDocument(text.getBytes(cs));
    }

    /** DOCUMENT RETRIEVE DOCTOKEN INTO MAXLENGTH(maxLength) DATAONLY: the document, truncated to maxLength with LENGERR
     *  RESP2 2 when longer (LENGTH is then the length the whole document needs); NOTFND RESP2 1 for a token CICS did not
     *  give; LENGERR RESP2 1 for a negative MAXLENGTH (no LENGTH). */
    public DocumentData documentRetrieve(String doctoken, int maxLength) {
        byte[] doc = root().documents.get(doctoken.stripTrailing());
        if (doc == null) {
            return new DocumentData(13, 1, -1, null);
        }
        if (maxLength < 0) {
            return new DocumentData(22, 1, -1, null);
        }
        if (doc.length > maxLength) {
            return new DocumentData(22, 2, doc.length, Arrays.copyOf(doc, maxLength));
        }
        return new DocumentData(0, 0, doc.length, doc.clone());
    }

"""
# #5274: the web family's methods live in their own module (cics_task_web.py).
CICS_TASK_JAVA += WEB_SESSION_JAVA
CICS_TASK_JAVA += """\
    // ---- #4771 (register X47): storage CICS acquires for the task, addressed by a pointer ----------------------------
    /** One block of task storage: GETMAIN (kind 0), a WEB RECEIVE SET body (1), the bytes of a LINKAGE record whose
     *  ADDRESS OF a pointer was set to (2), or a block FREEMAIN released (3). */
    private static final class Block {
        byte[] bytes;
        int off;  // #4771: where the block starts in `bytes` (an item inside a larger storage)
        int kind;
        boolean bound;
        String key;  // #5042: what a later command of the same kind ends (null: valid to the task's end)
        boolean syncEnds;  // #5042: a SYNCPOINT ends it too
        Block(byte[] bytes, int kind) {
            this.bytes = bytes;
            this.kind = kind;
        }
    }

    private final java.util.Map<Long, Block> blocks = new java.util.HashMap<>();
    private final java.util.IdentityHashMap<byte[], Long> addressed = new java.util.IdentityHashMap<>();
    private final java.util.IdentityHashMap<byte[], java.util.Map<Integer, Long>> addressedAt = new java.util.IdentityHashMap<>();
    private long nextBlock = 1;

    private long newBlock(byte[] bytes, int kind) {
        long h = root().nextBlock++;
        root().blocks.put(h, new Block(bytes, kind));
        return h;
    }

    /** GETMAIN SET(ptr) FLENGTH(n) | LENGTH(n) INITIMG(byte) (IBM CICS TS, EXEC CICS GETMAIN; register X47): {resp, resp2,
     *  handle}. LENGERR 1 for FLENGTH below 1 or a LENGTH of zero (the handle is then 0, "ptr-ref is set to zero"). Refused:
     *  a length above the limit (IBM's NOSTG), a LENGTH above 65520. `halfword`: the LENGTH form. */
    public long[] getmain(long length, boolean halfword, int initimg) {
        if (length < 1) {
            return new long[] {22, 1, 0};
        }
        if (length > 268435456L || (halfword && length > 65520)) {
            throw refused("GETMAIN length beyond the limit");
        }
        byte[] b = new byte[(int) length];
        java.util.Arrays.fill(b, (byte) initimg);
        return new long[] {0, 0, newBlock(b, 0)};
    }

    /** FREEMAIN DATAPOINTER(ptr) (IBM, EXEC CICS FREEMAIN; X47): INVREQ 1 for storage GETMAIN did not return (a null or
     *  unknown pointer, a record's address). Refused: storage already freed, a WEB RECEIVE SET body. */
    public int[] freemain(long handle) {
        Block b = root().blocks.get(handle);
        if (b == null || b.kind == 2) {
            return new int[] {16, 1};
        }
        if (b.kind != 0) {
            throw refused("FREEMAIN of storage already freed or received");
        }
        b.kind = 3;
        return new int[] {0, 0};
    }

    /** The body WEB RECEIVE SET hands the program (X47): a new block, whose handle goes into the pointer. */
    public long acquireReceived(byte[] body) {
        if (body.length > 268435456L) {
            throw refused("WEB RECEIVE SET body beyond the limit");
        }
        return newBlock(body.clone(), 1);
    }

    /** #5042 (X58): a SET(ptr) of a RECEIVE, RETRIEVE, READQ TS, GET CONTAINER or file read: a new block holding `data`.
     *  `key` names what IBM says ends the pointer's validity ("valid until the next receive command", "until the next
     *  READ command for the same file"): the next acquireSet of that key, or invalidateSet(key). A null key: valid to
     *  the task's end. Refused: a block above 256 MiB. FREEMAIN of the block is refused like a WEB RECEIVE SET body. */
    public long acquireSet(String key, byte[] data) {
        return acquireSet(key, data, false);
    }

    /** As acquireSet; `syncEnds`: a SYNCPOINT ends the pointer too (IBM: a READ UPDATE SET's, a browse SET's). */
    public long acquireSet(String key, byte[] data, boolean syncEnds) {
        if (data.length > 268435456L) {
            throw refused("SET(ptr) data beyond the limit");
        }
        invalidateSet(key);
        long h = newBlock(data.clone(), 1);
        root().blocks.get(h).key = key;
        root().blocks.get(h).syncEnds = syncEnds;
        return h;
    }

    /** #5042: ends the validity of the SET(ptr) blocks of `key`. IBM says only that the pointer is then "no longer valid", not
     *  what the storage holds; here it reads as zeros through any record already addressing it, as in the stub (ASSUMED, X58:
     *  a program must not read through a pointer past its validity). */
    public void invalidateSet(String key) {
        if (key == null) {
            return;
        }
        for (Block b : root().blocks.values()) {
            if (b.kind == 1 && key.equals(b.key)) {
                java.util.Arrays.fill(b.bytes, (byte) 0);
                b.key = null;
            }
        }
    }

    /** #5042: a SYNCPOINT ends the SET(ptr) blocks that IBM says it does (READ UPDATE SET, READNEXT / READPREV SET). */
    public void invalidateSyncSet() {
        for (Block b : root().blocks.values()) {
            if (b.kind == 1 && b.key != null && b.syncEnds) {
                java.util.Arrays.fill(b.bytes, (byte) 0);
                b.key = null;
            }
        }
    }

    /** #5042: ends every SET(ptr) block whose key starts with `prefix` (DELETE CHANNEL: its containers' pointers). */
    public void invalidateSetPrefix(String prefix) {
        for (Block b : root().blocks.values()) {
            if (b.kind == 1 && b.key != null && b.key.startsWith(prefix)) {
                java.util.Arrays.fill(b.bytes, (byte) 0);
                b.key = null;
            }
        }
    }

    /** #5042: whether a SET(ptr) block of `key` is still valid (a pointer the program may hold). */
    public boolean heldSet(String key) {
        for (Block b : root().blocks.values()) {
            if (b.kind == 1 && key.equals(b.key)) {
                return true;
            }
        }
        return false;
    }

    /** SET ptr TO ADDRESS OF record: the handle of the record's bytes (the same one each time). */
    public long addressOf(byte[] record) {
        return root().addressed.computeIfAbsent(record, r -> newBlock(r, 2));
    }

    /** SET ptr TO ADDRESS OF item (#4771): the handle of the bytes from `off` on (the same one each time); 0 is the record. */
    public long addressOf(byte[] storage, int off) {
        if (off == 0) {
            return addressOf(storage);
        }
        return root().addressedAt.computeIfAbsent(storage, r -> new java.util.HashMap<>()).computeIfAbsent(off, o -> {
            long h = newBlock(storage, 2);
            root().blocks.get(h).off = o;
            return h;
        });
    }

    /** Where the block `handle` starts in its bytes (0 unless it is an item inside a larger storage). */
    public int offsetAt(long handle) {
        Block b = root().blocks.get(handle);
        return b == null ? 0 : b.off;
    }

    /** `ptr-a = ptr-b` (#5042, X56): two pointers are equal when they address the same storage. One block can have two
     *  handles (a record's ADDRESS OF beside the pointer it was set to), so the handles are equal, or both name blocks
     *  of one byte array. NULL (0) equals only NULL. */
    public boolean samePointer(long a, long b) {
        if (a == b) {
            return true;
        }
        Block x = root().blocks.get(a);
        Block y = root().blocks.get(b);
        return x != null && y != null && x.bytes == y.bytes && x.off == y.off;
    }

    /** SET ADDRESS OF record TO ptr: the bytes the pointer addresses, for a record of `need` bytes. A record longer than
     *  its storage reads zero bytes past it (ASSUMED, X47: IBM's are bytes that are not the program's), the storage
     *  growing once, before a second record is set to it. Refused: a null or unknown pointer, freed storage, a record's own
     *  address that is shorter than the record, storage already addressed by a record that would need to grow. */
    public byte[] storageAt(long handle, int need) {
        Block b = root().blocks.get(handle);
        if (b == null) {
            throw refused("SET ADDRESS OF a null or unknown pointer");
        }
        if (b.kind == 3) {
            throw refused("SET ADDRESS OF storage already freed");
        }
        if (b.bytes.length - b.off < need) {
            if (b.kind == 2 || b.bound) {
                throw refused("SET ADDRESS OF a record longer than its storage");
            }
            b.bytes = java.util.Arrays.copyOf(b.bytes, need);
        }
        b.bound = true;
        return b.bytes;
    }

    // ---- #5119 (register X56): an OS/VS COBOL address held in data (a chained storage area's fullword) -------------------
    private final java.util.List<Long> bllTokens = new java.util.ArrayList<>();

    /** MOVE cell TO fullword: the token standing for the pointer's address (ASSUMED, X56: IBM's is the address itself). 0 for
     *  NULL; the n-th distinct address moved into data is n * 65536 (ADD 4096 to one never makes another; at most 1525, so a
     *  token keeps 8 digits). The stub's GGCBLLP numbers them alike. Refused: more addresses than that. */
    public int bllToken(long handle) {
        if (handle == 0) {
            return 0;
        }
        java.util.List<Long> t = root().bllTokens;
        int i = t.indexOf(handle);
        if (i < 0) {
            if (t.size() >= 1525) {
                throw refused("more than 1525 BLL addresses held in data");
            }
            t.add(handle);
            i = t.size() - 1;
        }
        return (i + 1) * 65536;
    }

    /** MOVE fullword TO cell: the handle a token stands for (0: NULL). Refused: a value no MOVE cell TO data gave (an
     *  address computed in data). */
    public long bllPointer(long token) {
        java.util.List<Long> t = root().bllTokens;
        if (token == 0) {
            return 0;
        }
        if (token < 0 || token % 65536 != 0 || token / 65536 > t.size()) {
            throw refused("an address in data that no BLL cell gave");
        }
        return t.get((int) (token / 65536) - 1);
    }

"""
# #5274: the web family's methods live in their own module (cics_task_web.py).
CICS_TASK_JAVA += WEB_REQUEST_JAVA
CICS_TASK_JAVA += """\
"""
# #5274: the transient-data queue family's methods live in their own module (cics_task_tdqueues.py).
CICS_TASK_JAVA += TDQUEUES_JAVA
# #5274: the time (ASKTIME / FORMATTIME) methods live in their own module (cics_task_time.py).
CICS_TASK_JAVA += TIME_JAVA
CICS_TASK_JAVA += """\
    /** The terminal the task is attached to (#3989): EIBTRMID, or null for a task no terminal started. */
    public CicsTask withTermid(String termid) {
        this.termid = termid;
        this.termidStated = true;
        return this;
    }

    /** #5126: withTermid for a harness that may not state a terminal (a case giving none or ""): leaves it unstated. */
    public CicsTask withTermidIfStated(String termid) {
        return termid == null || termid.isEmpty() ? this : withTermid(termid);
    }

    /** EIBTRMID (#3989): the task's terminal, the same at every LINK / XCTL level; null for a non-terminal task. */
    public String termid() {
        return root().termid;
    }

    /** #4270: EIBTASKN, the task's number -- a fact of the run that whoever runs the task states (as the stub's
     *  $GGCICS_TASKN), never derived here: "the task number assigned to the task by CICS", PIC S9(7) COMP-3, so 0 to
     *  9,999,999. Unstated, 0 (the stub's driver INITIALIZEs the EIB). */
    public CicsTask withTaskNumber(long taskNumber) {
        if (taskNumber < 0 || taskNumber > 9_999_999L) {
            throw new IllegalArgumentException("EIBTASKN: " + taskNumber + " is not a task number (0 to 9999999)");
        }
        this.taskNumber = taskNumber;
        return this;
    }

    /** #4270 (oracle_assumptions.md X23): the level-1 COMMAREA is exactly EIBCALEN bytes -- a scenario's stated
     *  `commarea_length`, shorter than the record -- so a reference past EIBCALEN reaches storage the task was never
     *  given (on z/OS, whatever follows the area). A det port refuses it (DetCics.PastFrom), as the stub does. */
    public CicsTask withExactCommarea() {
        this.exactCommarea = true;
        return this;
    }

    /** Whether this level's COMMAREA is exactly EIBCALEN bytes (X23): level 1 only, when the runner stated it. */
    public boolean exactCommarea() {
        return parent == null && exactCommarea;
    }

    /** EIBTASKN (#4270): the task's number, the same at every LINK / XCTL level. */
    public long taskNumber() {
        return root().taskNumber;
    }
"""
# #5274: the task / interval control family's methods live in their own module (cics_task_taskcontrol.py).
CICS_TASK_JAVA += TASKCONTROL_JAVA
CICS_TASK_JAVA += """\
    /** ENQ RESOURCE(resource) (#5089, IBM EXEC CICS ENQ): one task in the region, so the resource is free (NORMAL) --
     *  or ENQBUSY when the harness planned it. IBM raises ENQBUSY only "when an ENQ command specifies a resource that
     *  is unavailable and the NOSUSPEND option is specified" (or a HANDLE CONDITION ENQBUSY is active); without
     *  NOSUSPEND the task would be suspended, which is not modelled. IBM states no RESP2 for ENQBUSY: 0. */
    public String enq(String resource, boolean nosuspend) {
        int[] planned = root().injected("ENQ", resource);
        if (planned == null) {
            return "NORMAL";
        }
        if (!nosuspend) {
            throw new UnsupportedOperationException("ENQ on a planned-busy resource without NOSUSPEND: " + resource
                    + " (the task would be suspended), not modelled");
        }
        event("ENQ", "resource", resource, "resp", respName(planned[0]));
        return respName(planned[0]);
    }

    /** ENQ's own operands (#5089, register X60): LENGTH outside 1 through 255 is LENGERR RESP2 1 and a MAXLIFETIME that
     *  is no CVDA of ENQ (UOW 246, TASK 233) is INVREQ RESP2 2 (IBM EXEC CICS ENQ "Conditions"); otherwise enq(). A null
     *  length / maxlife is an option the program did not write. Two bad operands at once: IBM names no order, so refused.
     *  Returns {RESP, RESP2}; the failed ENQ records the event with its RESP2. */
    public int[] enqChecked(String resource, boolean nosuspend, Integer length, Integer maxlife) {
        boolean badLength = length != null && (length < 1 || length > 255);
        boolean badLife = maxlife != null && maxlife != 246 && maxlife != 233;
        if (badLength && badLife) {
            throw new UnsupportedOperationException("ENQ with LENGTH outside 1-255 and an invalid MAXLIFETIME: which "
                    + "condition IBM raises first is not stated, not modelled");
        }
        if (badLength || badLife) {
            int resp = badLength ? 22 : 16;
            int resp2 = badLength ? 1 : 2;
            event("ENQ", "resource", resource, "resp", respName(resp), "resp2", resp2);
            return new int[] {resp, resp2};
        }
        return new int[] {CicsSpec.resp(enq(resource, nosuspend)), 0};
    }

    /** LINK PROGRAM(program) with no COMMAREA: the callee's EIBCALEN is 0. */
    public String link(String program) {
        return link(program, null, 0);
    }

"""
# #5274: the channels / containers family's methods live in their own module (cics_task_containers.py).
CICS_TASK_JAVA += CONTAINERS_JAVA
CICS_TASK_JAVA += """\
    /** The bytes of the COMMAREA this program was LINKed with, when its caller passed them (by reference: what it
     *  writes there its caller sees); null otherwise. */
    public byte[] linkArea() {
        linkAreaTaken = true;
        return linkArea;
    }

    private boolean linkAreaTaken;  // #4765: whether the program asked for them (linkArea)

    /** #4765: a level-1 task LINKed with its COMMAREA's bytes as well as its object -- the runner's, as a caller's LINK
     *  passes both (link(program, commarea, length, area)): the area by reference, every byte of the record, a
     *  table's every occurrence too, which a DTO listing them once cannot carry. */
    public CicsTask withLinkArea(byte[] area) {
        this.linkArea = area;
        return this;
    }

    /** #4765: whether the program took its COMMAREA's bytes (linkArea): then they are what it left there. */
    public boolean linkAreaTaken() {
        return linkAreaTaken;
    }

    /** #5053: the LINK COMMAREA's bytes as they are now, without counting as the program taking them (linkArea does):
     *  what a harness hands a byte-carrying handleLink, and reads back after it. Null: the caller passed none. */
    public byte[] linkAreaView() {
        return linkArea;
    }

    /** #5053: whether linkArea is the LINK caller's own storage (the first program a LINK ran: by address), not a copy
     *  (an XCTL target's: IBM gives it a copy of LENGTH bytes). */
    public boolean linkAreaOfCaller() {
        return callerArea;
    }

    private java.util.Map<String, Long> counters = new java.util.HashMap<>();  // the region's named counters (root's)
    /** #4770 (X45): the {minimum, maximum} (unsigned doublewords) of a counter DEFINE DCOUNTER made; a counter with no entry
     *  (DEFINE COUNTER's, or one a scenario states) has limits the run does not state. */
    private java.util.Map<String, long[]> counterLimits = new java.util.HashMap<>();

    /** The region's named counters, "POOL/NAME" -> the value the next GET COUNTER returns. */
    public CicsTask withCounters(java.util.Map<String, Long> counters) {
        this.counters = counters;
        return this;
    }

    /** The INVREQ RESP2 IBM gives a counter or pool name outside its rules (X30): 403 for the pool (A-Z 0-9 $ @ # _, no
     *  embedded spaces), 404 for the counter (A-Z 0-9 _ $ # @, not starting with a digit or an underscore, no embedded
     *  spaces); 0 for a valid pair. A counter name of blanks only is not covered by IBM's rules: refused. */
    private static int counterNameResp2(String pool, String name) {
        String p = pool == null ? "" : pool.stripTrailing();
        for (int i = 0; i < p.length(); i++) {
            char c = p.charAt(i);
            if (!((c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '$' || c == '@' || c == '#' || c == '_')) {
                return 403;
            }
        }
        String n = name == null ? "" : name.stripTrailing();
        if (n.isEmpty()) {
            throw refused("a named counter with a blank name");
        }
        for (int i = 0; i < n.length(); i++) {
            char c = n.charAt(i);
            boolean ok = (c >= 'A' && c <= 'Z') || c == '$' || c == '@' || c == '#' || (i > 0 && ((c >= '0' && c <= '9') || c == '_'));
            if (!ok) {
                return 404;
            }
        }
        return 0;
    }

    private static String counterKey(String pool, String name) {
        return (pool == null ? "" : pool.strip()) + "/" + (name == null ? "" : name.strip());
    }

    /** GET COUNTER (IBM CICS TS): {RESP, RESP2, value} -- the named counter's current value, after which it is one more;
     *  INVREQ (16) RESP2 201 "Named counter not found" (the page lists no NOTFND; X30), 403 / 404 for a name outside
     *  IBM's rules. */
    public long[] getCounter(String pool, String name) {
        return getCounter(pool, name, 1);
    }

    /** GET DCOUNTER COUNTER VALUE INCREMENT(n) [WRAP] (IBM CICS TS, GET COUNTER and GET DCOUNTER; X30): the value
     *  before the increment, after which the counter is `increment` more (IBM: "incremented after the current number has been
     *  assigned"). WRAP changes nothing here: it acts only at the counter's maximum, which the run does not state, so a
     *  counter that would pass 4294967295 -- the smallest maximum IBM's page leaves open -- is refused, as is an INCREMENT
     *  not above zero (IBM gives it no meaning). */
    public long[] getCounter(String pool, String name, long increment) {
        return getCounter(pool, name, increment, false);
    }

    /** GET DCOUNTER ... INCREMENT(n) [WRAP] (X30; #4770, X45): {RESP, RESP2, value}, the INCREMENT an unsigned doubleword.
     *  A counter DEFINE DCOUNTER made has the limits it was given (unsigned): at its limit (the value past MAXIMUM, which a
     *  GET leaves it at when it reaches it) WRAP "resets the current value ... equal to the minimum value" and the GET
     *  returns that, and without WRAP the GET is SUPPRESSED (72) RESP2 101 and "the current number is not changed". An
     *  INCREMENT beyond MAXIMUM - MINIMUM, or one that carries the counter past MAXIMUM + 1 (IBM's REDUCE / 406 boundaries
     *  are not stated), is refused; so is a counter that would pass a doubleword. A counter with no limits entry is as
     *  before: WRAP changes nothing and one that would pass 4294967295 is refused. */
    public long[] getCounter(String pool, String name, long increment, boolean wrap) {
        return getCounter(pool, name, increment, wrap, false, null, null, false);
    }

    /** GET COUNTER / DCOUNTER ... [REDUCE] [COMPAREMIN(n)] [COMPAREMAX(m)] (#5039, X53): as above, with IBM's REDUCE ("the
     *  server may reduce the increment, and the request succeeds with the current value set to the maximum plus 1": an
     *  INCREMENT that would carry the counter past MAXIMUM + 1 leaves it at MAXIMUM + 1) and the value handed out compared with
     *  the bounds: both given and COMPAREMAX below COMPAREMIN, in range when it meets either; out of range is SUPPRESSED (72)
     *  RESP2 103 and the counter is unchanged (ASSUMED: IBM does not say). `fullword`: a COUNTER, whose compare values are
     *  signed fullwords (a negative one is refused). Refused: REDUCE with WRAP, REDUCE or a compare at a counter already at its
     *  limit (101 or 103 first, REDUCE with nothing left to reduce: not stated). */
    public long[] getCounter(String pool, String name, long increment, boolean wrap, boolean reduce, Long cmpMin, Long cmpMax,
            boolean fullword) {
        int bad = counterNameResp2(pool, name);
        if (bad != 0) {
            return new long[] {16, bad, 0};
        }
        if (increment == 0) {
            throw refused("GET COUNTER with an INCREMENT not above zero");
        }
        CicsTask r = root();
        String key = counterKey(pool, name);
        Long v = r.counters.get(key);
        if (v == null) {
            return new long[] {16, 201, 0};
        }
        long[] lim = r.counterLimits.get(key);
        if (reduce && wrap) {
            throw refused("GET COUNTER with both REDUCE and WRAP");
        }
        if ((cmpMin != null && cmpMin < 0 && fullword) || (cmpMax != null && cmpMax < 0 && fullword)) {
            throw refused("GET COUNTER COMPAREMIN / COMPAREMAX below zero");
        }
        if (lim == null) {
            if (!counterInRange(v, cmpMin, cmpMax)) {
                return new long[] {72, 103, 0};
            }
            if (increment < 0 || v + increment > 4294967295L) {
                throw refused(increment < 0 ? "GET COUNTER past a doubleword" : "GET COUNTER past 4294967295: the counter's maximum is not stated");
            }
            r.counters.put(key, v + increment);
            return new long[] {0, 0, v};
        }
        long min = lim[0], max = lim[1];
        if (Long.compareUnsigned(increment, max - min) > 0) {
            throw refused("GET COUNTER with an INCREMENT beyond the counter's range");
        }
        if (max != -1L && Long.compareUnsigned(v, max) > 0) {  // at its limit: the counter is MAXIMUM + 1
            if (reduce) {
                throw refused("GET COUNTER REDUCE at a counter already at its limit");
            }
            if (cmpMin != null || cmpMax != null) {
                throw refused("GET COUNTER COMPAREMIN / COMPAREMAX at a counter already at its limit");
            }
            if (!wrap) {
                return new long[] {72, 101, 0};
            }
            r.counters.put(key, min + increment);
            return new long[] {0, 0, min};
        }
        if (!counterInRange(v, cmpMin, cmpMax)) {
            return new long[] {72, 103, 0};
        }
        long next = v + increment;
        if (Long.compareUnsigned(next, v) < 0) {
            throw refused("GET COUNTER past a doubleword");
        }
        if (Long.compareUnsigned(next, max) > 0 && Long.compareUnsigned(next - max, 1) > 0) {
            if (!reduce) {
                throw refused("GET COUNTER with an INCREMENT past MAXIMUM + 1");
            }
            next = max + 1;
        }
        r.counters.put(key, next);
        return new long[] {0, 0, v};
    }

    /** Whether the value a GET hands out meets COMPAREMIN / COMPAREMAX (null: not given): at or above the one, at or below the
     *  other; with COMPAREMAX below COMPAREMIN, either (IBM). */
    private static boolean counterInRange(long v, Long cmpMin, Long cmpMax) {
        boolean geMin = cmpMin == null || Long.compareUnsigned(v, cmpMin) >= 0;
        boolean leMax = cmpMax == null || Long.compareUnsigned(v, cmpMax) <= 0;
        return cmpMin != null && cmpMax != null && Long.compareUnsigned(cmpMax, cmpMin) < 0 ? geMin || leMax : geMin && leMax;
    }

    /** REWIND COUNTER / DCOUNTER [INCREMENT(n)] (IBM CICS TS, REWIND COUNTER and REWIND DCOUNTER; #5039, X53): {RESP, RESP2}.
     *  "Resets a named counter that has reached its limit" to its minimum; SUPPRESSED (72) RESP2 102 for one that has not.
     *  A counter has reached its limit at MAXIMUM + 1 (where a GET leaves it). INVREQ 406 for an INCREMENT beyond (maximum -
     *  minimum) + 1 (stated), 201 / 403 / 404 as GET. Refused: an INCREMENT of zero or above 1 within the range (how the limit
     *  test applies it is not stated), a counter with no limits entry. */
    public int[] rewindCounter(String pool, String name, long increment) {
        int bad = counterNameResp2(pool, name);
        if (bad != 0) {
            return new int[] {16, bad};
        }
        if (increment == 0) {
            throw refused("REWIND COUNTER with an INCREMENT not above zero");
        }
        CicsTask r = root();
        String key = counterKey(pool, name);
        Long v = r.counters.get(key);
        if (v == null) {
            return new int[] {16, 201};
        }
        long[] lim = r.counterLimits.get(key);
        if (lim == null) {
            throw refused("REWIND COUNTER of a counter whose limits the run does not state");
        }
        long min = lim[0], max = lim[1], range = max - min + 1;  // (0: a full doubleword, which no INCREMENT exceeds)
        if (range != 0 && Long.compareUnsigned(increment, range) > 0) {
            return new int[] {16, 406};
        }
        if (increment != 1) {
            throw refused("REWIND COUNTER with an INCREMENT above 1");
        }
        if (max == -1L || Long.compareUnsigned(v, max) <= 0) {
            return new int[] {72, 102};
        }
        r.counters.put(key, min);
        return new int[] {0, 0};
    }

    /** UPDATE COUNTER / DCOUNTER VALUE(n) (IBM CICS TS, UPDATE COUNTER and UPDATE DCOUNTER; #5039, X53): {RESP, RESP2} -- the
     *  new current value. INVREQ 406 for a VALUE below MINIMUM or above MAXIMUM + 1, 201 / 403 / 404 as GET. `fullword` (a
     *  COUNTER): a VALUE below zero is refused, as DEFINE's; a counter with no limits entry is refused. */
    public int[] updateCounter(String pool, String name, long value, boolean fullword) {
        int bad = counterNameResp2(pool, name);
        if (bad != 0) {
            return new int[] {16, bad};
        }
        if (fullword && value < 0) {
            throw refused("UPDATE COUNTER with a VALUE below zero");
        }
        CicsTask r = root();
        String key = counterKey(pool, name);
        if (r.counters.get(key) == null) {
            return new int[] {16, 201};
        }
        long[] lim = r.counterLimits.get(key);
        if (lim == null) {
            throw refused("UPDATE COUNTER of a counter whose limits the run does not state");
        }
        if (Long.compareUnsigned(value, lim[0]) < 0 || (lim[1] != -1L && Long.compareUnsigned(value, lim[1] + 1) > 0)) {
            return new int[] {16, 406};
        }
        r.counters.put(key, value);
        return new int[] {0, 0};
    }

    /** DEFINE DCOUNTER (IBM CICS TS, DEFINE COUNTER and DEFINE DCOUNTER; #4770, X45): {RESP, RESP2} -- unsigned doublewords:
     *  the caller passes MINIMUM 0, MAXIMUM -1 (a doubleword of X'FF', IBM's defaults) and VALUE 0 for what the command
     *  omits. INVREQ 407 when MAXIMUM is below MINIMUM, 406 when VALUE is below MINIMUM or above MAXIMUM + 1, 202 for a
     *  duplicate, 403 / 404 for a name outside IBM's rules (407 / 406 are checked first: the page gives no order). */
    public int[] defineDcounter(String pool, String name, long value, long min, long max) {
        int bad = counterNameResp2(pool, name);
        if (bad != 0) {
            return new int[] {16, bad};
        }
        if (Long.compareUnsigned(max, min) < 0) {
            return new int[] {16, 407};
        }
        if (Long.compareUnsigned(value, min) < 0 || (max != -1L && Long.compareUnsigned(value, max + 1) > 0)) {
            return new int[] {16, 406};
        }
        CicsTask r = root();
        String key = counterKey(pool, name);
        if (r.counters.containsKey(key)) {
            return new int[] {16, 202};
        }
        r.counters.put(key, value);
        r.counterLimits.put(key, new long[] {min, max});
        return new int[] {0, 0};
    }

    /** QUERY DCOUNTER (#4770, X45): {RESP, RESP2, value, minimum, maximum} -- the counter's value, which stays, and its
     *  limits (unsigned doublewords). `limits`: the command asks for MINIMUM or MAXIMUM, which a counter with no limits entry
     *  (DEFINE COUNTER's, or a scenario's) has none the run states for: refused. */
    public long[] queryDcounter(String pool, String name, boolean limits) {
        int bad = counterNameResp2(pool, name);
        if (bad != 0) {
            return new long[] {16, bad, 0, 0, 0};
        }
        CicsTask r = root();
        String key = counterKey(pool, name);
        Long v = r.counters.get(key);
        if (v == null) {
            return new long[] {16, 201, 0, 0, 0};
        }
        long[] lim = r.counterLimits.get(key);
        if (lim == null && limits) {
            throw refused("QUERY DCOUNTER MINIMUM / MAXIMUM of a counter whose limits the run does not state");
        }
        return new long[] {0, 0, v, lim == null ? 0 : lim[0], lim == null ? 0 : lim[1]};
    }

    /** DEFINE COUNTER (IBM CICS TS, DEFINE COUNTER; X30, #5039, X50): {RESP, RESP2} -- fullwords: the caller passes
     *  MINIMUM 0, MAXIMUM 2147483647 (X'7FFFFFFF', IBM's defaults) and VALUE 0 for what the command omits. INVREQ 407
     *  when MAXIMUM is below MINIMUM or beyond X'7FFFFFFF', 406 when VALUE is below MINIMUM or above MAXIMUM + 1,
     *  202 for a duplicate, 403 / 404 for a name outside IBM's rules. A VALUE or MINIMUM below zero is refused. */
    public int[] defineCounter(String pool, String name, long value, long min, long max) {
        int bad = counterNameResp2(pool, name);
        if (bad != 0) {
            return new int[] {16, bad};
        }
        if (value < 0) {
            throw refused("DEFINE COUNTER with a VALUE below zero");
        }
        if (min < 0) {
            throw refused("DEFINE COUNTER with a MINIMUM below zero");
        }
        if (max < min || max > 2147483647L) {
            return new int[] {16, 407};
        }
        if (value < min || value > max + 1) {
            return new int[] {16, 406};
        }
        CicsTask r = root();
        String key = counterKey(pool, name);
        if (r.counters.containsKey(key)) {
            return new int[] {16, 202};
        }
        r.counters.put(key, value);
        r.counterLimits.put(key, new long[] {min, max});
        return new int[] {0, 0};
    }

    public int[] defineCounter(String pool, String name, int value) {
        return defineCounter(pool, name, (long) value, 0L, 2147483647L);
    }

    /** DELETE COUNTER (IBM CICS TS, DELETE COUNTER; X30): {RESP, RESP2} -- INVREQ 201 "Named counter not found"
     *  (the page lists no NOTFND), 403 for a pool outside IBM's rules. */
    public int[] deleteCounter(String pool, String name) {
        int bad = counterNameResp2(pool, name);
        if (bad == 403) {
            return new int[] {16, bad};
        }
        root().counterLimits.remove(counterKey(pool, name));
        java.util.Map<String, Long> all = root().counters;
        return all.remove(counterKey(pool, name)) == null ? new int[] {16, 201} : new int[] {0, 0};
    }

    /** QUERY COUNTER (IBM CICS TS, QUERY COUNTER; #4415 slice 2, X29; #5039, X50): {RESP, RESP2, value, minimum, maximum} --
     *  the counter's value, which stays, and its limits (fullwords). `limits`: the command asks for MINIMUM or MAXIMUM, which a
     *  counter with no limits entry has none the run states for: refused. */
    public int[] queryCounter(String pool, String name, boolean limits) {
        int bad = counterNameResp2(pool, name);
        if (bad != 0) {
            return new int[] {16, bad, 0, 0, 0};
        }
        CicsTask r = root();
        String key = counterKey(pool, name);
        Long v = r.counters.get(key);
        if (v == null) {
            return new int[] {16, 201, 0, 0, 0};
        }
        long[] lim = r.counterLimits.get(key);
        if (lim == null && limits) {
            throw refused("QUERY COUNTER MINIMUM / MAXIMUM of a counter whose limits the run does not state");
        }
        if (lim != null && limits && (lim[0] < 0 || lim[0] > 2147483647L || lim[1] < 0 || lim[1] > 2147483647L)) {
            throw refused("QUERY COUNTER MINIMUM / MAXIMUM of a counter whose limits are beyond a fullword");
        }
        int le = fullwordLengerr(lim, v);
        return new int[] {le == 0 ? 0 : 22, le, v.intValue(), lim == null ? 0 : (int) lim[0], lim == null ? 0 : (int) lim[1]};
    }

    /** LENGERR RESP2 of a fullword (COUNTER) command whose counter holds `v`, an unsigned doubleword (IBM CICS TS, GET COUNTER and
     *  QUERY COUNTER; #4770, X30): 0 when v fits a signed fullword, or when the counter is at its limit (MAXIMUM + 1: "LENGERR can't
     *  occur at counter-at-limit", the value is the maximum plus one in 32 bits). Else LENGERR for a counter DCOUNTER made too
     *  large: RESP2 1 the value overflowed into the sign bit (no bit above the low word), 2 "too large ... by only 1 bit; the
     *  overflow value is exactly 1" (the high word is 1), 3 greater than 1 (ASSUMED: IBM does not say how a value that is both
     *  is numbered; the high word decides). The operation completes: VALUE is the low-order 32 bits. */
    private static int fullwordLengerr(long[] lim, long v) {
        if (v >= 0 && v <= 2147483647L) {
            return 0;
        }
        if (lim != null && lim[1] != -1L && Long.compareUnsigned(v, lim[1]) > 0) {
            return 0;
        }
        long high = v >>> 32;
        return high == 0 ? 1 : high == 1 ? 2 : 3;
    }

    /** The result {RESP, RESP2, value} of a GET COUNTER (fullword form) as IBM's LENGERR warning has it (#4770, X30): RESP 22 with
     *  RESP2 1 / 2 / 3 and VALUE the low-order 32 bits (a signed number) for a counter that holds more than a fullword; any other
     *  result as it is. The counter has been advanced: "the named counter server completes the operation". */
    public long[] fullwordGet(String pool, String name, long[] r) {
        if (r[0] != 0) {
            return r;
        }
        int le = fullwordLengerr(root().counterLimits.get(counterKey(pool, name)), r[2]);
        return le == 0 ? r : new long[] {22, le, (int) r[2]};
    }

    public int[] queryCounter(String pool, String name) {
        int[] r = queryCounter(pool, name, false);
        return new int[] {r[0], r[1], r[2]};
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
        inputAfterUctranstSet();
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

    /** #4413: the terminal is an SNA 3270 display logical unit (CSD DEVICE(LUTYPE2)), not a 3270 logical unit: the
     *  input message it sends is one chain, so the RECEIVE that returns its last byte raises EOC (IBM, EXEC CICS
     *  RECEIVE (LUTYPE2/LUTYPE3): EOC "occurs when a request/response unit (RU) is received with end-of-chain-
     *  indicator set"; RECEIVE (3270 logical) has no EOC). EOC's default action is to ignore it. */
    public CicsTask withEndOfChain(boolean lutype2) {
        this.endOfChain = lutype2;
        return this;
    }

    /** RECEIVE INTO LENGTH(maxLength) (#4005): the terminal input, unformatted, read once per task. Input
     *  longer than maxLength is truncated to it and raises LENGERR, and the length is then the input's full
     *  length (IBM, EXEC CICS RECEIVE: "the data area specified in the LENGTH option is set to the original
     *  length of data"). */
    public Received receiveText(int maxLength) {
        return receive(maxLength, false);
    }

    /** #4413: a terminal RECEIVE [INTO | SET] [LENGTH] [MAXLENGTH] [NOTRUNCATE] (IBM, EXEC CICS RECEIVE (3270
     *  logical) and (LUTYPE2/LUTYPE3)). `maxLength` is the most the program takes -- MAXLENGTH, else LENGTH's value,
     *  else INTO's length; below zero, zero ("If the value specified is less than zero, zero is assumed"). Longer
     *  input: under NOTRUNCATE the first maxLength bytes, NORMAL, the length the data returned, and "CICS retains the
     *  remaining data and uses it to satisfy subsequent RECEIVE commands"; else truncated, LENGERR, and the length the
     *  original one. The operator's input is read once per task: a RECEIVE with nothing retained would wait for more
     *  input, which a task here cannot get (refused). On an LUTYPE2 terminal (withEndOfChain) the RECEIVE returning
     *  the input's last byte raises EOC instead of NORMAL; whether one that leaves data retained does is not
     *  documented, and is refused. */
    public Received receive(int maxLength, boolean notruncate) {
        inputAfterUctranstSet();
        CicsTask task = root();  // the terminal is the task's, whichever level reads it
        String text;
        if (task.terminalRest != null) {
            text = task.terminalRest;
            task.terminalRest = null;
        } else if (task.terminalRead) {
            throw new IllegalStateException("a second terminal RECEIVE waits for more input from the operator");
        } else {
            task.terminalRead = true;
            text = task.terminalInput == null ? "" : task.terminalInput;
        }
        int max = Math.max(maxLength, 0);
        String data = text.length() > max ? text.substring(0, max) : text;
        String resp;
        int length;
        if (text.length() > max && notruncate) {
            if (task.endOfChain) {
                throw new IllegalStateException("RECEIVE NOTRUNCATE on an LUTYPE2 terminal leaving data retained: "
                        + "whether it raises EOC is not documented");
            }
            task.terminalRest = text.substring(max);
            resp = "NORMAL";
            length = max;
        } else if (text.length() > max) {
            resp = "LENGERR";
            length = text.length();
        } else {
            resp = task.endOfChain ? "EOC" : "NORMAL";
            length = text.length();
        }
        event("RECEIVE", "resp", resp, "length", length, "data", data);
        return new Received(resp, length, data);
    }

    /** #5079 (X63): CONVERSE FROM FROMLENGTH INTO ... (IBM, EXEC CICS CONVERSE (default)): the data written to the terminal,
     *  recorded as a plain SEND records it (`text`, `length` as the program gave them), then the terminal RECEIVE of the
     *  reply (`maxLength`, `notruncate` as receive). A negative FROMLENGTH is LENGERR with nothing sent and nothing read
     *  (ASSUMED: IBM calls the value out of range; the length it returns is -1: no TOLENGTH is set). Refused: an LUTYPE2
     *  terminal (its reply's last byte raises EOC, which IBM does not list for CONVERSE). */
    public Received converse(String text, int length, int maxLength, boolean notruncate) {
        if (root().endOfChain) {
            throw refused("CONVERSE on an LUTYPE2 terminal (the reply would raise EOC, which IBM does not list for CONVERSE)");
        }
        if (length < 0) {
            return new Received("LENGERR", -1, null);
        }
        sendText(text, length);
        return receive(maxLength, notruncate);
    }

    /** #4413: SEND CONTROL with its options (ERASE, ERASEAUP, FREEKB, ALARM, FRSET; CURSOR with `cursor`, its
     *  offset, else null). It sends device controls only; none of its conditions (IBM, EXEC CICS SEND CONTROL:
     *  INVREQ for a BMS logical message, partitions, LDCs, SET / PAGING) can arise for a task's plain terminal. */
    public void sendControl(Integer cursor, String... options) {
        List<String> opts = new ArrayList<>(List.of(options));
        Collections.sort(opts);
        event("SEND-CONTROL", "options", opts, "cursor", cursor);
    }

    /** A terminal RECEIVE's outcome: its condition, the LENGTH it sets, and the data it moved INTO. */
    public record Received(String resp, int length, String data) {
    }

"""
# #5274: the file-control family's methods live in their own module (cics_task_filecontrol.py).
CICS_TASK_JAVA += FILECONTROL_JAVA
CICS_TASK_JAVA += """\
    /** #4437: the task runs a program LINKed from outside the region -- a distributed program link's server. */
    public CicsTask asDplServer() {
        this.dplServer = true;
        return this;
    }

    /** #4437: a DPL server's SYNCPOINT (or ROLLBACK) is INVREQ, RESP2 200, unless the client LINKed with SYNCONRETURN
     *  (IBM CICS TS API Reference, SYNCPOINT / SYNCPOINT ROLLBACK conditions). The region does not know how its client
     *  LINKed, so it refuses rather than answer NORMAL or INVREQ by guess. In the region, NORMAL is the only outcome. */
    private void refuseInDplServer(String command) {
        if (root().dplServer) {
            throw new UnsupportedOperationException(command + " in a program LINKed from outside the region: INVREQ "
                    + "(RESP2 200) unless the client LINKed with SYNCONRETURN, which the region does not know");
        }
    }

    /** SYNCPOINT: the unit of work is committed; a later rollback() cannot undo it. */
    public void syncpoint() {
        refuseInDplServer("SYNCPOINT");
        root().held.clear();
        root().updateTokens.clear();  // a sync point / rollback ends every hold
        invalidateSyncSet();  // #5042: and a READ UPDATE SET's, a browse SET's pointer
        root().containerBrowses.clear();  // #4951: a browse token does not survive a sync point
        root().syncpointed = true;
        tdUowEnd(false);  // #5168
        resourceUowEnd(false);  // #4892
        event("SYNCPOINT");
    }

    /** SYNCPOINT ROLLBACK: the task's file changes are undone -- the transaction the task runs in is marked for
     *  rollback (the hook, set by whoever runs the task). A rollback after a syncpoint would undo only part of
     *  the task's work, which this runtime does not model: it refuses rather than undo too much. */
    public void rollback() {
        refuseInDplServer("SYNCPOINT ROLLBACK");
        if (root().syncpointed) {
            throw new UnsupportedOperationException("SYNCPOINT ROLLBACK after a SYNCPOINT is not modelled");
        }
        root().held.clear();
        root().updateTokens.clear();  // a sync point / rollback ends every hold
        invalidateSyncSet();  // #5042: and a READ UPDATE SET's, a browse SET's pointer
        root().containerBrowses.clear();
        tdUowEnd(true);  // #5168
        resourceUowEnd(true);  // #4892
        if (root().rollbackHook != null) {
            root().rollbackHook.run();
        }
        event("SYNCPOINT-ROLLBACK");
    }

    private java.util.Set<String> nonRecoverable = java.util.Set.of();  // CSD RECOVERY(NONE) files (the root's)
    private java.util.function.Consumer<Runnable> outsideUnitOfWork = Runnable::run;

    /** The files the CSD defines RECOVERY(NONE), and how a change to one is made outside the task's unit of work
     *  (e.g. a REQUIRES_NEW transaction): such a change survives a rollback, as in CICS. */
    public CicsTask withNonRecoverable(java.util.Set<String> files, java.util.function.Consumer<Runnable> outside) {
        this.nonRecoverable = files;
        this.outsideUnitOfWork = outside;
        return this;
    }

    /** A file change: in the task's unit of work, or outside it for a non-recoverable file. */
    public void write(String file, Runnable change) {
        CicsTask r = root();
        if (r.nonRecoverable.contains(file == null ? "" : file.strip())) {
            r.outsideUnitOfWork.accept(change);
        } else {
            change.run();
        }
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

    /** INQUIRE PROGRAM STATUS (#4768, X34): the CVDA of a program the region defines -- ENABLED (23), the DEFINE PROGRAM
     *  default; no run states a DISABLED definition. Read only after inquireProgram answered NORMAL. */
    public int programStatus(String program) {
        return 23;
    }

    /** A file command's outcome: RESP and RESP2 (DFHRESP numbers) and the record read, when there is one. */
    public record FileRead<T>(int resp, int resp2, T record) {
        public boolean normal() {
            return resp == 0 || resp == 15;  // #4623: DUPKEY (15) delivers the record too
        }
    }

"""
# #5274: the faults family's methods (withFaults, injected, logFault, logAbend, planned, the deferred DUPKEY) live in
# their own module (cics_task_faults.py).
CICS_TASK_JAVA += FAULTS_JAVA
# #5274: the temporary-storage queue family (withTempStorage, the TS commands, TsResult, TempStorage) lives in its own
# module (cics_task_tsqueues.py).
CICS_TASK_JAVA += TSQUEUES_JAVA
CICS_TASK_JAVA += """\
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
            root().returnedArea = commarea;
            root().returnedLength = commarea == null ? null : length;
        }
        ended = true;
    }

    /** #4817: same, taking the raw bytes of the COMMAREA to preserve non-decodable bytes. */
    public void returnTransid(String transid, Object commarea, Integer length, byte[] area) {
        returnTransid(transid, commarea, length);
        if (level == 1) {
            root().returnedBytes = areaOf(area, length);
        }
    }

    /** #4817: the bytes a RETURN / XCTL COMMAREA passes on: a copy of the first LENGTH of `area` (null LENGTH: all of
     *  it). IBM passes LENGTH bytes -- the next task's EIBCALEN -- so a record longer than its LENGTH does not carry
     *  its tail across; the DTO's reading (`returned`) is cut at LENGTH the same way. A LINK is not cut: its area is
     *  passed by address, so the callee's storage is the caller's, tail included. */
    private static byte[] areaOf(byte[] area, Integer length) {
        if (area == null) {
            return null;
        }
        return java.util.Arrays.copyOf(area, length == null ? area.length : Math.max(0, Math.min(length, area.length)));
    }

    /** #6271 (X71): a plain RETURN TRANSID the program tests (it codes RESP), as {RESP, RESP2}: {0, 0} and the task
     *  ends as returnTransid does; a planned INVREQ / LENGERR at the highest level leaves the task running, records
     *  the failed RETURN and passes nothing on. */
    public int[] returnTransidResp(String transid, Object commarea, Integer length) {
        int[] planned = level == 1 ? root().injected("RETURN", "-") : null;
        if (planned != null) {
            event("RETURN", "level", level, "transid", transid, "resp", respName(planned[0]), "resp2", planned[1]);
            return new int[] {planned[0], planned[1]};
        }
        returnTransid(transid, commarea, length);
        return new int[] {0, 0};
    }

    /** #4817: same, taking the raw bytes of the COMMAREA to preserve non-decodable bytes. */
    public int[] returnTransidResp(String transid, Object commarea, Integer length, byte[] area) {
        int[] resps = returnTransidResp(transid, commarea, length);
        if (resps[0] == 0 && level == 1) {
            root().returnedBytes = areaOf(area, length);
        }
        return resps;
    }

    /** RETURN TRANSID(transid) [COMMAREA(commarea) LENGTH(length)] IMMEDIATE (#4270, register X27; IBM, EXEC CICS
     *  RETURN): the next task, `transid`, is attached at once -- ahead of any terminal input and any transaction ATI
     *  enqueued for the terminal -- with the COMMAREA, and "appears to the operator as having been started by terminal
     *  data". As {RESP, RESP2}: {0, 0} and the task ends; INVREQ RESP2 1 for a task with no terminal, INVREQ RESP2 2 for
     *  a program below the highest logical level, LENGERR RESP2 11 for a COMMAREA length below 0 or past 32763 -- the
     *  command then returns to the program. IBM does not say which of the two INVREQs a non-terminal task below level 1
     *  gets: refused. */
    public int[] returnImmediate(String transid, Object commarea, Integer length) {
        boolean lower = level > 1;
        boolean noTerminal = termid() == null;
        if (lower && noTerminal) {
            throw new IllegalStateException("RETURN IMMEDIATE below the highest level in a task with no terminal: IBM "
                    + "lists INVREQ RESP2 1 and 2 for it and does not say which: not modelled");
        }
        int resp = 0;
        int resp2 = 0;
        if (lower) {
            resp = 16;
            resp2 = 2;
        } else if (noTerminal) {
            resp = 16;
            resp2 = 1;
        } else if (commarea != null && length != null && (length < 0 || length > 32763)) {
            resp = 22;
            resp2 = 11;
        }
        int[] planned = resp == 0 ? root().injected("RETURN", "-") : null;  // #6271 (X71): a planned INVREQ / LENGERR
        if (planned != null) {
            resp = planned[0];
            resp2 = planned[1];
        }
        if (resp != 0) {
            event("RETURN", "level", level, "immediate", true, "transid", transid, "resp", respName(resp),
                    "resp2", resp2);
            return new int[] {resp, resp2};
        }
        event("RETURN", "transid", transid, "commarea", snapshot.apply(commarea), "length", commarea == null ? null : length,
                "immediate", true);
        root().returnedArea = commarea;
        root().returnedLength = commarea == null ? null : length;
        ended = true;
        return new int[] {0, 0};
    }

    /** #4817: same, taking the raw bytes of the COMMAREA to preserve non-decodable bytes. */
    public int[] returnImmediate(String transid, Object commarea, Integer length, byte[] area) {
        int[] resps = returnImmediate(transid, commarea, length);
        if (resps[0] == 0 && level == 1) {
            root().returnedBytes = areaOf(area, length);
        }
        return resps;
    }

    /** #4817: the RETURN TRANSID COMMAREA bytes, a copy: the first LENGTH of the bytes the program passed beside its
     *  DTO, in its storage page's charset (what the next task takes through linkArea). Null when a RETURN passed none
     *  beside its COMMAREA -- a LENGTH past the DTO passes the COMMAREA itself as a byte[] in the region's EBCDIC
     *  (#4695: `returned(Object.class)`, so a facade's handleTransaction answers that byte[] by design: the Object
     *  answer is the COMMAREA as the next task is given it, and `returned(Dto.class)` refuses it by name). */
    public byte[] returnedBytes() {
        root().bytesTaken = true;
        return returnedBytes == null ? null : java.util.Arrays.copyOf(returnedBytes, returnedBytes.length);
    }

    /** #4817: a DTO-only answer must not change what the RETURN passed. IBM hands the next task the COMMAREA's bytes
     *  as they were; the DTO holds a number it decoded (a numeric DISPLAY field of spaces and digits, invalid content),
     *  and answering it would put digits where the task left something else. When the task's bytes were not taken
     *  (returnedBytes(): the byte-carrying handleTransaction does), the DTO's layout bytes (toCommarea) must hold
     *  every byte the RETURN passed: a byte toCommarea writes that is not a space (FILLER and an unset field are
     *  spaces, in either page) and differs from the passed one is refused by name. A DTO with no layout, or a RETURN
     *  that passed no bytes beside it, is as it was. */
    private void lossless(Object area) {
        byte[] passed = root().returnedBytes;
        if (passed == null) {
            return;
        }
        byte[] laid;
        try {
            java.lang.reflect.Method to = area.getClass().getMethod("toCommarea");
            if (to.getReturnType() != byte[].class) {
                return;
            }
            laid = (byte[]) to.invoke(area);
        } catch (NoSuchMethodException | IllegalAccessException | java.lang.reflect.InvocationTargetException e) {
            return;
        }
        for (int i = 0; i < Math.min(laid.length, passed.length); i++) {
            if (laid[i] != passed[i] && laid[i] != 0x20 && laid[i] != 0x40) {
                throw new IllegalStateException("the task RETURNed a COMMAREA whose byte " + i + " the " + area.getClass().getName()
                        + " DTO cannot hold as it was (a number it decoded): answer it through the byte-carrying"
                        + " handleTransaction(.., byte[]) and lastAnswerBytes() (#4817)");
            }
        }
    }

    /** The COMMAREA the task's level-1 RETURN passed on (#4343: what handleTransaction answers), as `type`; null when
     *  the task RETURNed none, or has not RETURNed. A COMMAREA of another class is converted by layout (#4449) when
     *  both are laid out as bytes (the generator writes toCommarea / fromCommarea into the DTOs a facade converts
     *  between): the bytes passed -- the record's, or its first LENGTH -- read through `type`, as the program reading
     *  them through its own record sees them. Anything else is refused, never guessed: a class with no layout, or
     *  fewer bytes than `type`'s record (never passed). */
    public <T> T returned(Class<T> type) {
        Object area = root().returnedArea;
        if (area != null && !root().bytesTaken) {
            lossless(area);
        }
        if (area == null || type.isInstance(area)) {
            return type.cast(area);
        }
        String refused = "the task RETURNed a " + area.getClass().getName() + ", not a " + type.getName()
                + (area instanceof byte[] ? " (a LENGTH past its DTO passes the COMMAREA's bytes: answer it as Object)" : "");
        java.lang.reflect.Method to;
        java.lang.reflect.Method from;
        try {
            to = area.getClass().getMethod("toCommarea");
            from = type.getMethod("fromCommarea", byte[].class);
        } catch (NoSuchMethodException e) {
            throw new IllegalStateException(refused + " (no layout converts one into the other)");
        }
        if (to.getReturnType() != byte[].class || !java.lang.reflect.Modifier.isStatic(from.getModifiers())) {
            throw new IllegalStateException(refused + " (no layout converts one into the other)");
        }
        try {
            byte[] bytes = (byte[]) to.invoke(area);
            Integer length = root().returnedLength;
            if (length != null && length < bytes.length) {
                bytes = Arrays.copyOf(bytes, Math.max(length, 0));
            }
            return type.cast(from.invoke(null, (Object) bytes));
        } catch (java.lang.reflect.InvocationTargetException e) {
            throw new IllegalStateException(refused + ": " + e.getCause().getMessage(), e.getCause());
        } catch (IllegalAccessException e) {
            throw new IllegalStateException(refused, e);
        }
    }

    // ---- #4343: the region a program's deployed entry points run their task in -----------------------------------
    /** Where a facade -- a program's deployed entry point: handleTransaction, handleLink -- gets its task and runs it:
     *  the region the program runs in, with its temporary storage, the programs a LINK / XCTL reaches, its clock and
     *  terminal. A deployment installs one (deploy, once: the generated CicsRegion bean does). A harness joins one on
     *  its thread (join), so a facade's task is the scenario's own -- the same events, TS, COMMAREA, screens, abend and
     *  condition plumbing -- and is compared with the COBOL like any task the harness starts itself. */
    public interface Region {
        /** A task of transaction `transid` at the region's terminal, ENTER pressed. With no COMMAREA it is the
         *  transaction started from a cleared screen: its terminal input is the transaction id typed. With one (its
         *  whole record: EIBCALEN is the record's length) it goes on with the conversation: ENTER on the screen the
         *  last task sent, nothing typed. */
        CicsTask transaction(String transid, Object commarea);
        /** #4817: same, with the raw bytes of the COMMAREA from the previous task. */
        default CicsTask transaction(String transid, Object commarea, byte[] bytes) {
            byte[] copy = bytes == null ? null : java.util.Arrays.copyOf(bytes, bytes.length);
            return transaction(transid, commarea).withLinkArea(copy);
        }

        /** The program level `program` runs at when another program LINKs (or XCTLs) to it with `commarea` (null:
         *  none) -- the whole record, passed by reference: what the program changes in it, the caller sees. */
        CicsTask linked(String program, Object commarea);
        /** #5053: same, with the raw bytes of the LINK's COMMAREA: its program's DFHCOMMAREA, passed by address (what it
         *  leaves there the caller sees), every byte -- the ones the contract DTO does not name too. */
        default CicsTask linked(String program, Object commarea, byte[] bytes) {
            return linked(program, commarea).withLinkArea(bytes);
        }

        /** Runs `program` on `task`: `self` is the program's own runTask; a LINK / XCTL reaches the region's others. */
        void run(CicsTask task, String program, Consumer<CicsTask> self);
    }

    /** The region joined on this thread until closed (#4343). */
    public interface Joined extends AutoCloseable {
        @Override
        void close();
    }

    private static final ThreadLocal<Region> JOINED = new ThreadLocal<>();
    private static volatile Region deployed;

    /** The region a facade runs its task in (#4343): the one joined on this thread, else the deployed one, else a
     *  region of the program alone (a LINK / XCTL to any other program is PGMIDERR). */
    public static Region region() {
        Region r = JOINED.get();
        if (r != null) {
            return r;
        }
        Region d = deployed;
        return d != null ? d : new LocalRegion(null, null, null);
    }

    /** A deployment's region, from now on (#4343). */
    public static void deploy(Region region) {
        deployed = region;
    }

    /** Joins `region` on this thread (#4343): a facade called before the handle is closed runs its task there. */
    public static Joined join(Region region) {
        Region before = JOINED.get();
        JOINED.set(region);
        return () -> {
            if (before == null) {
                JOINED.remove();
            } else {
                JOINED.set(before);
            }
        };
    }

    /** A region in this JVM (#4343): one temporary storage for every task, the clock `clock` (null: the wall clock in
     *  the mainframe's zone, __ZONE__ -- never the JVM's), the programs `programs` runs (null: none but the program a
     *  facade runs), and the terminal `termid` (null: none). */
    public static class LocalRegion implements Region {
        private final Programs programs;
        private final String termid;
        private final Supplier<LocalDateTime> clock;
        private final TempStorage storage = new TempStorage();

        public LocalRegion(Programs programs, String termid, Supplier<LocalDateTime> clock) {
            this.programs = programs;
            this.termid = termid;
            this.clock = clock != null ? clock : () -> LocalDateTime.now(ZoneId.of("__ZONE__"));
        }

        @Override
        public CicsTask transaction(String transid, Object commarea) {
            CicsTask t = new CicsTask(transid, "ENTER", commarea, null, Map.of()).withTempStorage(storage)
                    .withTermid(termid).withClock(clock.get());
            if (commarea == null) {
                t.withTerminalInput(transid);
            }
            return t;
        }

        /** A LINK from outside the region (a distributed program link): the program runs at level 1 of a task of
         *  its own, the mirror transaction CSMI's, with no terminal. */
        @Override
        public CicsTask linked(String program, Object commarea) {
            return new CicsTask("CSMI", null, commarea, null, Map.of()).withTempStorage(storage)
                    .withClock(clock.get()).withProgram(program).asDplServer();
        }

        @Override
        public void run(CicsTask task, String program, Consumer<CicsTask> self) {
            task.withPrograms(programs != null ? programs : new Programs() {
                public boolean defined(String p) {
                    return program.equals(p);
                }

                public void run(String p, CicsTask t) {
                    self.accept(t);
                }
            });
            task.run(program);
        }
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
        return xctl(program, commarea, length, (Channel) null);
    }

    /** XCTL with the COMMAREA's bytes as well (#4806): the target's DFHCOMMAREA is those bytes, every one -- a
     *  numeric field holding spaces too, which the DTO reads as a number -- as a LINK's (linkArea). */
    public String xctl(String program, Object commarea, Integer length, byte[] area) {
        String resp = xctl(program, commarea, length, (Channel) null);
        if (area != null) {  // #5053: the event carries the bytes the caller sent (base64), as a LINK's does
            events.get(events.size() - 1).put("area", java.util.Base64.getEncoder().encodeToString(areaOf(area, length)));
        }
        if ("NORMAL".equals(resp)) {
            xctlArea = areaOf(area, length);
        }
        return resp;
    }

    private boolean callerArea;      // #4816: linkArea is the LINK caller's storage (not a copy, not a task's own area)
    private boolean xctlOfLinkage;   // #4816: the next XCTL's COMMAREA is inside this program's DFHCOMMAREA
    private boolean linkedDto;       // #4956: the DTO this program was LINKed with is its LINK caller's own object

    /** #4956: whether `o` can be an alias of another object: a value (String, number, enum) is passed as it is. */
    private static boolean aliasable(Object o) {
        return o != null && !(o instanceof Enum || o instanceof String || o instanceof Boolean
                || o instanceof Character || o instanceof java.math.BigDecimal || o instanceof java.math.BigInteger
                || o instanceof Integer || o instanceof Long || o instanceof Short || o instanceof Byte
                || o instanceof Double || o instanceof Float);
    }

    /** #5060: two values are the same when equal, numbers by numeric value whatever their width or scale (an int
     *  field passed as a long, 1.0 and 1.00): refuse, never guess. */
    private static boolean sameValue(Object a, Object b) {
        if (a.equals(b)) {
            return true;
        }
        if (a instanceof Number && b instanceof Number) {
            try {
                return new java.math.BigDecimal(a.toString()).compareTo(new java.math.BigDecimal(b.toString())) == 0;
            } catch (NumberFormatException e) {
                return false;  // NaN, infinity: equals above decided
            }
        }
        return false;
    }

    /** #5060: a String or number `part` cannot be traced by reference, so it counts when it equals a value `whole`
     *  holds (an equal-valued copy is refused too: refuse, never guess).
     *  #4956: whether `part` is `whole` or an object `whole` holds (a nested group, a table, an element, a byte
     *  area), by reference -- what an XCTL of a LINKed program's DTO, or of a part of it, passes. */
    private static boolean within(Object whole, Object part, java.util.IdentityHashMap<Object, Boolean> seen) {
        if (whole == part) {
            return true;
        }
        boolean byValue = part != null && !aliasable(part);  // #5060: a value is traced by equality, not identity
        if (!aliasable(whole)) {
            return byValue && sameValue(part, whole);
        }
        if (seen.put(whole, Boolean.TRUE) != null) {
            return false;
        }
        Class<?> type = whole.getClass();
        java.util.List<Object> held = new ArrayList<>();
        if (type.isArray()) {
            if (type.getComponentType().isPrimitive()) {
                if (byValue) {  // #5060: a numeric table's element is a value of the DTO too
                    for (int i = 0; i < java.lang.reflect.Array.getLength(whole); i++) {
                        if (sameValue(part, java.lang.reflect.Array.get(whole, i))) {
                            return true;
                        }
                    }
                }
                return false;
            }
            held.addAll(Arrays.asList((Object[]) whole));
        } else if (whole instanceof Iterable) {
            for (Object e : (Iterable<?>) whole) {
                held.add(e);
            }
        } else if (whole instanceof Map) {
            held.addAll(((Map<?, ?>) whole).values());
        } else if (!type.getName().startsWith("java.")) {
            for (Class<?> k = type; k != null && k != Object.class; k = k.getSuperclass()) {
                for (java.lang.reflect.Field f : k.getDeclaredFields()) {
                    if (java.lang.reflect.Modifier.isStatic(f.getModifiers()) || (f.getType().isPrimitive() && !byValue)) {
                        continue;
                    }
                    try {
                        f.setAccessible(true);
                        held.add(f.get(whole));
                    } catch (RuntimeException | IllegalAccessException e) {
                        // an unreadable field is not an alias this walk can see
                    }
                }
            }
        }
        for (Object h : held) {
            if (within(h, part, seen)) {
                return true;
            }
        }
        return false;
    }

    /** #4816: the XCTL about to be issued passes (part of) this program's own DFHCOMMAREA. A LINKed program's is its
     *  caller's storage; IBM (EXEC CICS XCTL, COMMAREA: "the contents of the data-area are passed") does not say whether
     *  the target then addresses that storage or a copy, so a successful XCTL of it is refused, never guessed
     *  (register X39). */
    public void xctlOfLinkage() {
        xctlOfLinkage = true;
    }

    private String xctl(String program, Object commarea, Integer length, Channel pendingChannel) {
        String resp = "NORMAL";
        Integer resp2 = null;
        if (commarea != null && length != null && (length < 0 || length > 32763)) {
            resp = "LENGERR";
            resp2 = 11;
        } else if (programs != null && !programs.defined(program)) {
            resp = "PGMIDERR";
            resp2 = 1;
        } else {
            int[] planned = root().injected("XCTL", program.stripTrailing());  // #4049: the program does not end
            if (planned != null) {
                resp = respName(planned[0]);
                resp2 = planned[1];
            }
        }
        transferResp2 = resp2 == null ? 0 : resp2;  // #4986: as LINK's
        event("XCTL", "program", program, "length", commarea == null ? Integer.valueOf(0) : length, "commarea",
                snapshot.apply(commarea), "resp", resp, "resp2", resp2);
        boolean ofLinkage = xctlOfLinkage;
        xctlOfLinkage = false;
        boolean ofDto = linkedDto && commarea != null && within(this.commarea, commarea, new java.util.IdentityHashMap<>());
        if ("NORMAL".equals(resp) && (ofLinkage && callerArea || ofDto)) {
            throw new UnsupportedOperationException("XCTL passing the COMMAREA its LINK caller passed: IBM does not say "
                    + "whether the target addresses the caller's storage or a copy, not modelled");
        }
        if ("NORMAL".equals(resp)) {
            xctlTarget = program;
            xctlCommarea = commarea;
            xctlLength = commarea == null ? Integer.valueOf(0) : length;
            xctlChannel = pendingChannel;
            ended = true;
        }
        return resp;
    }

"""
# #5274: the conditions family's methods (ASSIGN, HANDLE ABEND, PUSH / POP HANDLE, ABEND, RESP and abend-code names) live in
# their own module (cics_task_conditions.py), gathered into this one span.
CICS_TASK_JAVA += CONDITIONS_JAVA
CICS_TASK_JAVA += """\
    private CicsTask root() {
        return parent == null ? this : parent.root();
    }

    public boolean ended() {
        return ended;
    }

    /** The events so far. An ACTION(EVENTUAL) WEB SEND (X37) is sent at the end of the task: its WEB-SEND event is recorded
     *  here, once, after the task's other events (read the events when the task has ended); a task that ended in an abend
     *  with one held is refused (IBM does not say whether the response is sent). */
    public List<Map<String, Object>> events() {
        if (webHeld != null) {
            for (Map<String, Object> e : events) {
                if ("ABEND".equals(e.get("event")) && "terminated".equals(e.get("outcome"))) {
                    throw refused("WEB SEND ACTION(EVENTUAL) response held when the task ended in an abend");
                }
            }
            Object[] fields = webHeld;
            webHeld = null;
            event("WEB-SEND", fields);
        }
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
        if (root().dispatched && !CHILD_EVENTS.contains(e.get("event"))) {  // #4950 (X18, R1)
            throw new UnsupportedOperationException("a RUN TRANSID child's " + e.get("event") + " (a region resource or "
                    + "a terminal): its order against its parent's and its siblings' commands is not modelled");
        }
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
    # #4427: the COMMAREA at the program's transaction boundary -- what handleTransaction takes and answers. The
    # program's own DTO, unless a RETURN TRANSID carries the COMMAREA across programs (`crossings`): then Object.
    txn_request: str | None = None
    txn_response: str | None = None
    crossings: list[str] = field(default_factory=list)  # the RETURN TRANSID flows that cross, as sentences
    txn_converts: list[str] = field(default_factory=list)  # #4449: the other DTOs txn_response is converted from


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
    a COMMAREA contract, a container, or a LINK / XCTL reaching it -- or (#4270) a program nothing in the
    estate starts or LINKs to that is still a CICS program: one that declares DFHCOMMAREA in its LINKAGE SECTION
    (the name the CICS translator gives the COMMAREA it passes; CBSA's ACCTCTRL, called from outside the estate),
    or one whose EXEC CICS handlers / ABENDs / SYNCPOINTs the engine extracted (cics-java-recgen's EDUPGM, LINKed
    from Java). Without it such a program got a plain service and every EXEC CICS in it was a hole."""
    sections = skeleton.get("sections", {})
    interface = (sections.get("interface") or {}).get("facts") or {}
    return bool(
        (sections.get("entry_transactions") or {}).get("facts")
        or (sections.get("cics_resources") or {}).get("facts")
        or (sections.get("commarea_contracts") or {}).get("facts")
        or interface.get("containers")
        or incoming_links(skeleton)
        or any(
            r.get("level") == 1 and r.get("section") == "LINKAGE" and str(r.get("name") or "").upper() == "DFHCOMMAREA"
            for r in (sections.get("records") or {}).get("facts") or []
        )
        or any(r.get("source") == "CICS" for r in (sections.get("uow_handlers") or {}).get("facts") or [])
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
        self._shape: dict[str, tuple] = {}  # DTO name -> (bytes, field count) of the layout it was made from
        self._codecs: dict[str, Any] = {}  # #4449: DTO name -> its layout codec (toCommarea / fromCommarea)
        self._partition: dict[str, tuple] = {}  # #4449: DTO name -> how its layout cuts its bytes (layout_partition)
        self.programs = {key: self._plan(key, sk) for key, sk in sorted(skeletons.items()) if is_cics_program(sk)}
        self._plan_opaque_commareas()
        self._plan_conversations()

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
        records = f"{self.package}.entity.vsam.CobolRecords"
        codec = commarea_codec(name, layout, records, getattr(self.target.data, "dbcs_code_page", None))  # #4449
        self.dtos[name] = Dto(name, javadoc, body, requires_list, [use] if use else [], facts=dto_facts)
        if codec is not None:  # written only into the DTOs a facade converts between (_plan_conversations)
            self._codecs[name] = codec
            self._partition[name] = layout_partition(layout)
        self._by_signature[signature] = name
        self._shape[name] = (layout.get("bytes"), len(layout.get("fields", [])))
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
        for sg, dto in zip(commarea["segments"], prog.segment_dtos, strict=True):
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
            record, file = commarea["record"], commarea["file"]
            if commarea.get("declared_record"):
                # CICS hands a LINKed program only its own LINKAGE: the contract DTO is named after the callee's
                # DFHCOMMAREA (HcsubDfhcommarea), never the record the caller happens to pass (HcsubWsCa)
                record, file = commarea["declared_record"], path
            prog.commarea_dto = self._dto_for(record, file, commarea, cls, doc, use)
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

    @staticmethod
    def _returns_to_itself(prog: CicsProgram, row: dict) -> bool:
        """#4464: a RETURN TRANSID naming one of the program's own transactions re-enters the program -- also when
        the engine leaves the flow's callee unresolved because the estate maps that transaction id ambiguously
        (CardDemo's CSD pairs CC00 with COCRDLIC through a DEFINE PROGRAM ... TRANSID besides its TRANSACTION)."""
        return (row.get("verb") == "RETURN TRANSID" and row.get("caller") == prog.path
                and row.get("callee") in (None, prog.path)
                and row.get("target") in {t["transid"] for t in prog.transactions})  # fmt: skip

    def _flow_callee(self, by_file: dict[str, CicsProgram], row: dict) -> str | None:
        """The program a contract row reaches: its resolved callee, else the sender when it RETURNs to its own
        transaction (#4464)."""
        sender = by_file.get(row.get("caller", ""))
        if not row.get("callee") and sender is not None and self._returns_to_itself(sender, row):
            return sender.path
        return row.get("callee")

    @staticmethod
    def _opaque_dfhcommarea(prog: CicsProgram) -> dict | None:
        """The program's LINKAGE DFHCOMMAREA when it is an opaque byte area -- one alphanumeric item, typically
        `PIC X OCCURS 1 TO n DEPENDING ON EIBCALEN` -- else None: such an area has no record of its own."""
        for rec in (prog.sections.get("records") or {}).get("facts", []):
            if (
                rec.get("section") != "LINKAGE"
                or rec.get("level") != 1
                or str(rec.get("name")).upper() != "DFHCOMMAREA"
            ):
                continue
            leaves, todo = [], [rec]
            while todo:
                item = todo.pop()
                kids = [k for k in item.get("children") or [] if k.get("level") not in (66, 88)]
                if kids:
                    todo += kids
                elif item.get("pic"):
                    leaves.append(item)
            if len(leaves) == 1 and re.fullmatch(r"X+(\(\d+\))?", str(leaves[0]["pic"]).upper().replace(" ", "")):
                return rec
            return None
        return None

    def _plan_opaque_commareas(self) -> None:
        """#4464: a program whose DFHCOMMAREA is opaque (`PIC X OCCURS ... DEPENDING ON EIBCALEN`) still receives a
        COMMAREA: whatever the flows into it pass. The engine pairs none when no resolved LINK / XCTL / RETURN TRANSID
        reaches it (CardDemo's COSGN00C: every XCTL to it is data-driven, and its RETURN TRANSID(CC00) to itself is
        unresolved), so its facade took none and every re-entry was refused. Here the COMMAREA is the record those
        flows pass: the program's RETURN TRANSID to its own transactions (what its next task starts with) and any
        resolved LINK / XCTL / RETURN TRANSID reaching it, as the estate's DTO for that record (name, file, width,
        field count). Data-driven sites into it name a record too (`inbound` passes): one naming another record is
        a conflict. Where the flows disagree, or no single DTO carries the record, the gap says so by name."""
        for prog in self.programs.values():
            if prog.commarea_dto or prog.channel_in or prog.channel_out:
                continue
            area = self._opaque_dfhcommarea(prog)
            if area is None:
                continue
            records: dict[tuple, list[dict]] = {}
            for r in (prog.sections.get("commarea_contracts") or {}).get("facts", []):
                rec = r.get("caller_record") or {}
                if not rec.get("name") or not (self._returns_to_itself(prog, r) or r.get("callee") == prog.path):
                    continue
                key = (str(rec["name"]).upper(), rec.get("file"), rec.get("bytes"), rec.get("fields"))
                records.setdefault(key, []).append(r)
            if not records:
                continue
            sites = {k: ", ".join(f"{r['verb']} at {r['caller']}:{r['line']}" for r in rows)
                     for k, rows in records.items()}  # fmt: skip
            if len(records) > 1:
                passed = "; ".join(f"{k[0]} ({k[1]}, {k[2]} bytes) by {sites[k]}" for k in sorted(records, key=str))
                prog.commarea_gap = (
                    f"DFHCOMMAREA is opaque and the flows into this program pass different records: {passed}"
                )
                continue
            (key,) = records
            name, file, width, count = key
            others = sorted({str(i["passes"]).upper() for i in ((prog.sections.get("interface") or {}).get("facts") or {})
                             .get("inbound", []) if i.get("passes")} - {name})  # fmt: skip
            if others:
                prog.commarea_gap = (f"DFHCOMMAREA is opaque; {sites[key]} pass{'es' if len(records[key]) == 1 else ''} "
                                     f"{name} ({file}), but data-driven sites into it pass {', '.join(others)}")  # fmt: skip
                continue
            dtos = sorted(n for sig, n in self._by_signature.items()
                          if (sig[0].upper(), sig[1]) == (name, file) and self._shape.get(n) == (width, count))  # fmt: skip
            if len(dtos) != 1:
                why = f"several DTOs carry it ({', '.join(dtos)})" if dtos else "no program's COMMAREA DTO carries it"
                prog.commarea_gap = (f"DFHCOMMAREA is opaque; {sites[key]} pass{'es' if len(records[key]) == 1 else ''} "
                                     f"{name} ({file}, {width} bytes), but {why}")  # fmt: skip
                continue
            prog.commarea_dto = dtos[0]
            prog.commarea = {"record": name, "file": file, "basis": "flow_record", "bytes": width, "alternatives": [],
                             "sources": [{"caller": r["caller"], "line": r["line"], "verb": r["verb"]}
                                         for r in records[key]]}  # fmt: skip
            prog.commarea_gap = None
            self.dtos[dtos[0]].uses.append(
                f"The COMMAREA {prog.cls} receives through its opaque DFHCOMMAREA (line {area.get('line')}), as "
                f"passed by {sites[key]}."
            )

    def _plan_conversations(self) -> None:
        """#4427: the COMMAREA a pseudo-conversation carries across programs. `RETURN TRANSID(t) COMMAREA(ws)` starts
        the next task in whichever program owns `t`, and that program reads the same bytes through its own record:
        COBOL passes bytes, never a type. So at a transaction boundary the COMMAREA may arrive -- and leave -- as the
        sending program's record (its RETURN's `ws`) or the receiving program's (its DFHCOMMAREA): a port may present
        it in either. handleTransaction takes the program's own DTO only when every RETURN TRANSID into its
        transactions presents no other class, and answers with it only when every RETURN TRANSID its task can end in
        does the same -- its own, and those of every program an XCTL chain from it reaches (an XCTL keeps the task);
        otherwise that side is Object -- the COMMAREA as whichever record the port passed, read by runTask
        through task.commarea(..). #4449: the answer keeps the program's own DTO where every other record its task can
        RETURN cuts the bytes as its own does (_reads_through): task.returned converts it by layout, losing nothing.
        The flows are the skeleton's commarea_contracts rows (verb RETURN TRANSID)."""
        by_file = {p.path: p for p in self.programs.values()}
        record_dtos: dict[tuple[str, str], set[str]] = {}
        for sig, name in self._by_signature.items():
            record_dtos.setdefault((sig[0].upper(), sig[1]), set()).add(name)

        def classes(row: dict) -> set[str | None]:
            sender, receiver = by_file.get(row.get("caller", "")), by_file.get(row.get("callee", ""))
            if sender is not None and (sender is receiver or self._returns_to_itself(sender, row)):  # its own record
                return {sender.commarea_dto}
            # the sender presents its record as its own COMMAREA DTO when that is one of the record's DTOs, else as
            # the record's only DTO; a record with several DTOs (extended copies) and no planned sender: unknown
            rec = row.get("caller_record") or {}
            dtos = record_dtos.get((str(rec.get("name") or row.get("commarea") or "").upper(), rec.get("file") or ""),
                                   set())  # fmt: skip
            if sender is not None and (sender.commarea_dto in dtos or len(dtos) != 1):
                sent = sender.commarea_dto
            else:
                sent = next(iter(dtos)) if len(dtos) == 1 else None
            return {sent, receiver.commarea_dto if receiver is not None else None}

        # every RETURN TRANSID with a COMMAREA, and every XCTL, the estate's skeletons know (each lists its own sites
        # and those reaching it): an XCTL keeps the task, so the task's RETURN may be any program XCTLed to's
        returns: dict[tuple, dict] = {}
        xctl: dict[str, set[str]] = {}
        for q in self.programs.values():
            for r in (q.sections.get("commarea_contracts") or {}).get("facts", []):
                if r.get("verb") == "RETURN TRANSID":
                    returns.setdefault((r.get("caller", ""), r.get("line") or 0, r.get("target") or ""), r)
            for r in (q.sections.get("navigation") or {}).get("facts", []):
                if r.get("verb") == "XCTL" and r.get("from") and r.get("to"):
                    xctl.setdefault(r["from"], set()).add(r["to"])
        flows = [returns[k] for k in sorted(returns)]

        def task_programs(path: str) -> set[str]:
            """The programs a task started in `path` can end in: itself and every program an XCTL chain reaches."""
            seen, todo = {path}, [path]
            while todo:
                for nxt in sorted(xctl.get(todo.pop(), ())):
                    if nxt not in seen:
                        seen.add(nxt)
                        todo.append(nxt)
            return seen

        for prog in self.programs.values():
            own = prog.commarea_dto
            prog.txn_request = prog.txn_response = own
            if not own or not prog.transactions:
                continue
            ends = task_programs(prog.path)
            sides = (("in", "txn_request", [r for r in flows if r.get("callee") == prog.path
                                             or self._returns_to_itself(prog, r)]),
                     ("out", "txn_response", [r for r in flows if r.get("caller") in ends]))  # fmt: skip
            for side, attr, rows in sides:
                crossed = [(r, classes(r)) for r in rows]
                crossed = [(r, seen) for r, seen in crossed if seen != {own}]
                if not crossed:
                    continue
                # #4449: the answer stays the program's own DTO when every other record its task can RETURN reads
                # through it by layout (task.returned converts); else Object, as #4427 has it
                if side == "out" and all(self._reads_through(own, seen - {own}) for _, seen in crossed):
                    prog.txn_converts = sorted({c for _, seen in crossed for c in seen if c is not None and c != own})
                else:
                    setattr(prog, attr, "Object")
                for r, seen in crossed:
                    rec = (r.get("caller_record") or {}).get("name") or r.get("commarea") or "a COMMAREA"
                    other = sorted(c for c in seen if c and c != own)
                    as_ = f" ({', '.join(other)} besides {own})" if other else f" (no DTO besides {own})"
                    via = "" if side == "in" or r.get("caller") == prog.path else f", after an XCTL from {prog.path}"
                    line = (f"{side}: RETURN TRANSID({r.get('target')}) COMMAREA({rec}) at {r.get('caller')}:"
                            f"{r.get('line')} -> {self._flow_callee(by_file, r) or 'a program the estate does not resolve'}"
                            f"{via}{as_}")  # fmt: skip
                    if line not in prog.crossings:
                        prog.crossings.append(line)
        for prog in self.programs.values():  # #4449: the codecs task.returned converts with, in both DTOs
            if prog.txn_converts and prog.txn_response:
                for name in (prog.txn_response, *prog.txn_converts):
                    self.dtos[name].methods = self._codecs[name]
        # #4803: a LINK passes bytes, so the DTO of the program that LINKs (its own COMMAREA, the area its task holds)
        # and the DTO of the program LINKed to read through each other by layout when both are laid out as bytes and
        # cut the same way (_reads_through): EPSCMORT's EPSMTCOM and EPSCSMRT's own DFHCOMMAREA, a LINK whose PROGRAM is
        # a variable (a candidate row, not a resolved contract). The harness converts the LINK's area with these codecs.
        for prog in self.programs.values():
            callee = prog.commarea_dto
            for r in prog.links:
                sender = by_file.get(r.get("caller", ""))
                own = sender.commarea_dto if sender is not None else None
                if (r.get("verb") == "LINK" and callee in self._codecs and own in self._codecs and own != callee
                        and self._reads_through(callee, {own})):  # fmt: skip
                    for name in (callee, own):
                        self.dtos[name].methods = self._codecs[name]

    def _reads_through(self, own: str, others: set[str | None]) -> bool:
        """#4449: whether every record in `others` reads through `own` with no byte lost: both laid out exactly as
        bytes (commarea_codec), cut the same way (layout_partition: the same width, and each item at the same offset,
        width, PICTURE and USAGE) -- the same COMMAREA under another program's names. A record of another width or
        cut would be truncated, padded, or have bytes that are not a number decoded as one: those stay Object."""
        mine = self._partition.get(own)
        return mine is not None and bool(others) and all(o is not None and self._partition.get(o) == mine
                                                          for o in others)  # fmt: skip

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
            # #4427: the facade answers Object where a RETURN TRANSID carries the COMMAREA across programs; the
            # endpoint's body stays the program's own record (JSON needs a concrete class)
            treq, tresp = (req, prog.txn_response) if resp == req and req and prog.txn_response else (req, resp)
            java += self._endpoint(f"transaction{txn['segment']}", svc, "handleTransaction",
                                   json.dumps(txn["transid"]), treq, tresp)  # fmt: skip
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
        LINK / XCTL level), with CicsSpec (#4270 spec PR 4: its tables); #4343: and CicsRegion, the deployment's
        region the programs' facades run their tasks in."""
        if not self.programs:
            return {}
        out = {"CicsTask": CICS_TASK_JAVA.replace("__PACKAGE__", self.package).replace("__ZONE__", self.zone),
               "CicsSpec": CICS_SPEC_JAVA.replace("__PACKAGE__", self.package)}  # fmt: skip
        if self.target.features.services:  # the region runs the programs' services
            out["CicsRegion"] = self.region_source()
        return out

    @property
    def zone(self) -> str:
        """#3824: the mainframe's time zone (the target's culture.zone), the region's clock -- never the JVM's."""
        return self.target.culture.zone

    @staticmethod
    def program_name(prog: CicsProgram) -> str:
        """The name the CSD and a LINK / XCTL give the program: its PROGRAM-ID, else its key."""
        return (prog.program_ids[0] if prog.program_ids else prog.key).upper()

    def region_source(self) -> str:
        """#4343: the deployment's region (CicsTask.LocalRegion): every CICS program of the estate, run through its
        service's runTask, so a facade's LINK / XCTL reaches the others as CICS does; installed when Spring makes it."""
        progs = sorted(self.programs.values(), key=lambda p: (self.program_name(p), p.path))
        by_name: dict[str, list[CicsProgram]] = {}
        for p in progs:
            by_name.setdefault(self.program_name(p), []).append(p)
        names = ", ".join(json.dumps(n) for n in by_name)
        transids = sorted({t["transid"] for p in progs for t in p.transactions})
        arms = []
        for name, same in by_name.items():
            if len(same) == 1:
                arms.append(
                    f"            case {json.dumps(name)} -> context.getBean({same[0].cls}Service.class).runTask(task);"
                )
                continue
            # two sources under one program name: the region's CSD installs one of them, and the estate does not say
            # which -- so the region runs neither rather than pick one (CICS itself never holds two)
            srcs = ", ".join(p.path for p in same)
            arms.append(
                f"            case {json.dumps(name)} -> throw new IllegalStateException("
                f"{json.dumps(f'program {name} has more than one source ({srcs}); the CSD decides which one runs')});"
            )
        imports = [
            f"import {self.package}.service.{same[0].cls}Service;" for same in by_name.values() if len(same) == 1
        ]
        return "\n".join([
            f"package {self.package}.cics;", "",
            *sorted(set(imports)),
            "import java.time.LocalDateTime;",
            "import java.time.ZoneId;",
            "import java.util.Set;",
            "import org.springframework.beans.factory.annotation.Value;",
            "import org.springframework.context.ApplicationContext;",
            "import org.springframework.stereotype.Component;", "",
            "/**",
            " * The region this application's CICS programs run in (#4343): every program's facade (handleTransaction,",
            " * handleLink) runs its task here -- one temporary storage, and a LINK / XCTL reaching the other programs",
            " * through their services' runTask, as the CSD-defined programs of a CICS region reach each other. Spring makes",
            " * it once, which deploys it (CicsTask.deploy); a test harness joins a region of its own instead (CicsTask.join).",
            " * Its clock is the mainframe's, as MainframeClock's (#3824): `gitgalaxy.clock` (an ISO local date-time) when",
            f" * set, else the wall clock in `gitgalaxy.zone`, else `gitgalaxy.culture.zone`, else {self.zone} -- never the JVM's.",
            " */",
            "@Component",
            "public class CicsRegion implements CicsTask.Programs {", "",
            f"    static final Set<String> PROGRAMS = Set.of({names});",
            f"    static final Set<String> TRANSACTIONS = Set.of({', '.join(json.dumps(t) for t in transids)});", "",
            "    private final ApplicationContext context;", "",
            "    public CicsRegion(ApplicationContext context, @Value(\"${gitgalaxy.clock:}\") String pinned,",
            f"                      @Value(\"${{gitgalaxy.zone:${{gitgalaxy.culture.zone:{self.zone}}}}}\") String zoneId) {{",
            "        this.context = context;",
            f"        ZoneId zone = ZoneId.of(zoneId == null || zoneId.isBlank() ? {json.dumps(self.zone)} : zoneId.trim());",
            "        String at = pinned == null ? \"\" : pinned.trim();",
            "        CicsTask.deploy(new CicsTask.LocalRegion(this, null,",
            "                at.isEmpty() ? () -> LocalDateTime.now(zone) : () -> LocalDateTime.parse(at)));",
            "    }", "",
            "    @Override",
            "    public boolean defined(String program) {",
            "        return PROGRAMS.contains(program);",
            "    }", "",
            "    @Override",
            "    public boolean transaction(String transid) {",
            "        return TRANSACTIONS.contains(transid);",
            "    }", "",
            "    @Override",
            "    public void run(String program, CicsTask task) {",
            "        switch (program) {",
            *arms,
            '            default -> throw new IllegalStateException("no service runs program " + program);',
            "        }",
            "    }",
            "}", "",
        ])  # fmt: skip

    @staticmethod
    def link_bytes_overload(prog: CicsProgram, name: str, req: str, resp: str | None) -> list[str]:
        """#5053: handleLink with the raw bytes of the LINK's COMMAREA, and the lastLinkBytes() accessor beside it."""
        return [
            "    /** #5053: handleLink with the raw bytes of the LINK's COMMAREA (passed by address: what the program",
            "     *  leaves there the caller sees); lastLinkBytes() then answers the bytes it left. */",
            f"    public {req if resp == req else 'void'} handleLink({req} request, byte[] area) {{",
            f'        log.info("{prog.cls}: handleLink (bytes)");',
            "        CicsTask.Region region = CicsTask.region();",
            f"        CicsTask task = region.linked({name}, request, area);",
            f"        region.run(task, {name}, this::runTask);",
            "        byte[] left = task.linkAreaView();",
            "        lastLinkBytes = task.linkAreaTaken() && left != null ? java.util.Arrays.copyOf(left, left.length) : null;",
            *(["        return request;"] if resp == req else []),
            "    }\n",
            "    // @facade-helper: the bytes the last byte-carrying handleLink's program left in the COMMAREA",
            "    private byte[] lastLinkBytes;\n",
            "    /** The bytes the last byte-carrying handleLink's program left in the LINK COMMAREA (a copy; null: it took",
            "     *  none -- its DTO is the COMMAREA). @facade-helper */",
            "    public byte[] lastLinkBytes() {",
            "        return lastLinkBytes == null ? null : java.util.Arrays.copyOf(lastLinkBytes, lastLinkBytes.length);",
            "    }\n",
        ]  # fmt: skip

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

        name = json.dumps(self.program_name(prog))
        facade = not (prog.channel_in or prog.channel_out) or bool(prog.commarea_dto)  # a channel: no task runtime
        if prog.transactions and facade:
            # #4343: the deployed entry point runs the program -- one task of it in the region -- so it is comparable
            # with the COBOL (the CICS crucible drives scenarios through it); #4342: never an entry that does nothing
            # #4427: the COMMAREA the estate's RETURN TRANSID flows carry -- Object where one crosses programs
            treq, tresp = (prog.txn_request, prog.txn_response) if resp == req and req else (req, None)
            params = "String transid" + (f", {treq} request" if treq else "")
            converts = [
                f"     *  It answers {tresp} all the same (#4449): the other records a task of it can RETURN",
                f"     *  ({', '.join(prog.txn_converts)}) cut their bytes as {tresp} does, so task.returned converts",
                "     *  them by layout and loses nothing.",
            ] if prog.txn_converts and tresp else []  # fmt: skip
            carried = [
                "     *  own record, so a port may pass either record -- the facade carries it as Object where a flow",
                "     *  presents another class, and runTask reads it (task.commarea(..))." + ("" if converts else " The flows:"),
            ] if "Object" in (treq, tresp) else ["     *  own record."]  # fmt: skip
            crossing = [
                "     *  The COMMAREA crosses programs (#4427): COBOL passes bytes, and each program reads them through its",
                *carried, *converts, *(["     *  The flows:"] if converts else []),
                *[f"     *  {c}." for c in prog.crossings],
            ] if prog.crossings else []  # fmt: skip
            methods += [
                "    /** A CICS transaction entered the program (#4343): one task of it in the region (CicsTask.region()),",
                "     *  ENTER pressed" + (" -- `request` its COMMAREA, null when started from a cleared screen --" if treq
                                          else ", started from a cleared screen,") + " run through runTask"
                + (". Returns the COMMAREA its RETURN passes on (null: none)." if tresp else ".")
                + ("" if crossing else " */"),
                *crossing, *(["     */"] if crossing else []),
                f"    public {tresp or 'void'} handleTransaction({params}) {{",
                f'        log.info("{prog.cls}: handleTransaction");',
                "        CicsTask.Region region = CicsTask.region();",
                f"        CicsTask task = region.transaction(transid, {'request' if treq else 'null'});",
                f"        region.run(task, {name}, this::runTask);",
                *([f"        return task.returned({tresp}.class);"] if tresp else []),
                "    }\n",
                # #4870: the same entry with the bytes of the COMMAREA the previous task's RETURN passed on in, and
                # the bytes this task's RETURN passes on out (lastAnswerBytes()): a DTO cannot carry a numeric DISPLAY
                # field holding spaces. The signature above is unchanged (the equivalence harness reads it).
                "    /** #4870: handleTransaction with the raw bytes of the previous task's COMMAREA (null: none); the",
                "     *  bytes this task's RETURN passes on are then answered by lastAnswerBytes(). */",
                f"    public {tresp or 'void'} handleTransaction({params}, byte[] area) {{",
                f'        log.info("{prog.cls}: handleTransaction (bytes)");',
                "        CicsTask.Region region = CicsTask.region();",
                f"        CicsTask task = region.transaction(transid, {'request' if treq else 'null'}, area);",
                f"        region.run(task, {name}, this::runTask);",
                "        lastAnswerBytes = task.returnedBytes();",
                *([f"        return task.returned({tresp}.class);"] if tresp else []),
                "    }\n",
                "    // @facade-helper: the bytes the last byte-carrying handleTransaction answered",
                "    private byte[] lastAnswerBytes;\n",
                "    /** The bytes the last byte-carrying handleTransaction's RETURN passed on (a copy; null: none).",
                "     *  @facade-helper */",
                "    public byte[] lastAnswerBytes() {",
                "        return lastAnswerBytes == null ? null : java.util.Arrays.copyOf(lastAnswerBytes, lastAnswerBytes.length);",
                "    }\n",
            ]  # fmt: skip
        elif prog.transactions:
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
        if self.has_link_handler(prog) and facade:
            methods += [
                "    /** Another program LINKed / XCTLed to this one (#4343): the program at that level in the region",
                "     *  (CicsTask.region()), run through runTask on " + ("`request`, passed by reference -- what it changes,"
                                                                       " the caller sees." if req else "no COMMAREA.")
                + " */",
                f"    public {req if resp == req and req else 'void'} handleLink({f'{req} request' if req else ''}) {{",
                f'        log.info("{prog.cls}: handleLink");',
                "        CicsTask.Region region = CicsTask.region();",
                f"        CicsTask task = region.linked({name}, {'request' if req else 'null'});",
                f"        region.run(task, {name}, this::runTask);",
                *(["        return request;"] if resp == req and req else []),
                "    }\n",
                # #5053: the same entry with the bytes of the LINK's COMMAREA (a LINK with none has no bytes to carry:
                # `handleLink(byte[])` would only collide with the DTO form's arity), and the bytes the program left
                # there (lastLinkBytes()): the signature above is unchanged (the equivalence harness reads it).
                *(self.link_bytes_overload(prog, name, req, resp) if req else []),
            ]  # fmt: skip
        elif self.has_link_handler(prog):
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
