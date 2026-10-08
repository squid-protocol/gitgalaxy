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
    private Channel currentChannel;                         // #4270: the channel this program was passed
    private Map<String, Channel> channels = new HashMap<>();  // #4270: the channels in this program's scope, by name
    private java.util.Set<String> droppedChannels = java.util.Set.of();  // #4270: left behind by an XCTL
    private LocalDateTime now;                              // #4006: the virtual clock (the task's root)
    private List<StartData> retrieveData = List.of();
    private int retrieved;
    private boolean retrieveRefused;                        // #4270: a RETRIEVE raised ENVDEFERR (the root's)
    private boolean runChild;                               // #4270: a RUN TRANSID child task (the root's)
    private int children;                                   // #4270: the RUN TRANSID children it attached
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
    private long taskNumber;                                 // #4270: EIBTASKN (the task's root), a stated fact
    private boolean exactCommarea;                          // #4270 (X23): the COMMAREA is EIBCALEN bytes, no more
    private String exitLabel;                               // #3989: this level's HANDLE ABEND LABEL
    private boolean exitActive;
    private final java.util.ArrayDeque<Object[]> pushedExits = new java.util.ArrayDeque<>();
    private String unwoundTo;                               // an abend below went to this level's exit
    private List<String[]> faultPlan = List.of();           // #4023 follow-up: injected conditions (the task's root)
    private java.nio.file.Path faultLog;
    private final java.util.Set<String> held = new java.util.HashSet<>();  // files a readForUpdate holds (the root's)
    private boolean syncpointed;                                            // a SYNCPOINT committed (the root's)
    private boolean dplServer;                          // #4437: LINKed from outside the region (the root's)
    private Runnable rollbackHook;                                          // how a rollback undoes (the root's)
    private final Map<String, Integer> faultSeen = new HashMap<>();
    private Object returnedArea;                                             // #4343: the level-1 RETURN's COMMAREA
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
        return link(program, commarea, length, null);
    }

    /** LINK with the COMMAREA's bytes as well (#4181 follow-up): the area is passed by reference, so a program
     *  given `area` reads and writes those bytes as its DFHCOMMAREA -- every byte, the ones its contract DTO does
     *  not name too (a caller's record laid out unlike the target's contract). The event carries them (base64). */
    public String link(String program, Object commarea, int length, byte[] area) {
        return link(program, commarea, length, area, null);
    }

    private String link(String program, Object commarea, int length, byte[] area, Channel linkChannel) {
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
        if (area != null) {
            events.get(events.size() - 1).put("area", java.util.Base64.getEncoder().encodeToString(
                    java.util.Arrays.copyOf(area, Math.max(0, Math.min(len, area.length)))));
        }
        if (!"NORMAL".equals(resp)) {
            return resp;
        }
        CicsTask callee = new CicsTask(this, level + 1, program, commarea, len, commarea);
        callee.invoker = this.program;
        callee.linkLength = len;
        callee.linkArea = area;
        callee.passChannel(linkChannel, java.util.Set.of());  // #4270: LINK CHANNEL (none: the callee has no channel)
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
                next.passChannel(current.xctlChannel, current.inScope());  // #4270
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

    /** ASSIGN STARTCODE, 2 characters. A RUN TRANSID child's is not among IBM's codes: refused. */
    public String assignStartcode() {
        CicsTask r = root();
        if (r.runChild) {
            throw refused("ASSIGN STARTCODE in a RUN TRANSID child task (IBM lists no code for one)");
        }
        if (r.startcode == null) {
            throw new IllegalStateException("ASSIGN STARTCODE: how the task was started is not stated (withStartcode)");
        }
        return String.format(java.util.Locale.ROOT, "%-2.2s", r.startcode);
    }

    /** ASSIGN USERID, 8 characters. */
    public String assignUserid() {
        String u = root().userid;
        if (u == null) {
            throw new IllegalStateException("ASSIGN USERID: the task's user is not stated (withUserid)");
        }
        return String.format(java.util.Locale.ROOT, "%-8.8s", u);
    }

    /** ASSIGN FACILITY / SCRNHT / SCRNWD's condition: INVREQ (16) for a task with no terminal (RESP2 5, "The task is
     *  not associated with a terminal; or the task has no principal facility"), else 0. */
    public int assignTerminalResp() {
        return termid() == null ? 16 : 0;
    }

    /** ASSIGN FACILITY: the principal facility, the task's terminal, 4 characters. */
    public String assignFacility() {
        return String.format(java.util.Locale.ROOT, "%-4.4s", termid());
    }

    /** ASSIGN SCRNHT (`width` false) / SCRNWD (true): the terminal's screen, a halfword. */
    public int assignScreen(boolean width) {
        int[] s = root().screen;
        if (s == null) {
            throw new IllegalStateException("ASSIGN SCRNHT / SCRNWD: the terminal's screen is not stated (withScreen)");
        }
        return width ? s[1] : s[0];
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

    /** The FROM data of the START requests this task was started for, in expiry order (#4006). */
    public CicsTask withRetrieveData(List<byte[]> data) {
        List<StartData> records = new ArrayList<>();
        if (data != null) {
            data.forEach(d -> records.add(new StartData(d, null, null, null)));
        }
        return withStartData(records);
    }

    /** #4270: the data records of the START requests this task was started for, in expiry order -- each one's FROM
     *  data and RTRANSID / RTERMID / QUEUE values, null where its START did not give one. A START that gave none of
     *  them stored no record (IBM, EXEC CICS RETRIEVE: ENDDATA for "a START command that did not specify any of the
     *  data options FROM, RTRANSID, RTERMID, or QUEUE"). */
    public CicsTask withStartData(List<StartData> records) {
        this.retrieveData = records == null ? List.of() : records;
        return this;
    }

    /** #4270: one START request's data record: FROM's bytes and the RTRANSID / RTERMID / QUEUE values (each null
     *  when the START did not give it). */
    public record StartData(byte[] from, String rtransid, String rtermid, String queue) {
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
        return startRequest(transid).termid(termid).interval(interval).from(from).reqid(reqid).protect(protect).issue();
    }

    /** START ... TIME(hhmmss): see StartRequest.time. */
    public StartResult startAt(String transid, String termid, int time, byte[] from, String reqid, boolean protect) {
        return startRequest(transid).termid(termid).time(time).from(from).reqid(reqid).protect(protect).issue();
    }

    /** #4270: a START TRANSID(transid) request, its options set one by one, then issued (IBM CICS TS, EXEC CICS
     *  START). Without INTERVAL / TIME / AFTER / AT it is INTERVAL(0). */
    public StartRequest startRequest(String transid) {
        return new StartRequest(this, transid);
    }

    /** #4270: the options of one START. */
    public static final class StartRequest {
        private final CicsTask task;
        private final String transid;
        private String termid;
        private String reqid;
        private String rtransid;
        private String rtermid;
        private String queue;
        private byte[] from;
        private boolean protect;
        private String when = "INTERVAL";
        private int hhmmss;
        private Integer hours;
        private Integer minutes;
        private Integer seconds;

        private StartRequest(CicsTask task, String transid) {
            this.task = task;
            this.transid = transid;
        }

        /** INTERVAL(hhmmss): now + hh hours, mm minutes, ss seconds; mm / ss above 59 is INVREQ RESP2 5 / 6. */
        public StartRequest interval(int hhmmss) {
            this.when = "INTERVAL";
            this.hhmmss = hhmmss;
            return this;
        }

        /** TIME(hhmmss): "If you specify a time with an hours component that is greater than 23, you are specifying
         *  a time on a day following the current one"; a time of today not later than now but within the preceding
         *  six hours expires at once ("If you specify a task to start at any time within the previous six hours,
         *  it starts immediately"), an earlier one tomorrow (IBM CICS TS, "Expiration times"). */
        public StartRequest time(int hhmmss) {
            this.when = "TIME";
            this.hhmmss = hhmmss;
            return this;
        }

        /** AFTER HOURS / MINUTES / SECONDS (null: not given): "A combination of at least two of HOURS(0 - 99),
         *  MINUTES(0 - 59), and SECONDS(0 - 59)", or "one of HOURS(0 - 99), MINUTES(0 - 5999), or SECONDS(0 -
         *  359999)"; out of range, INVREQ RESP2 4 / 5 / 6. The interval it amounts to. */
        public StartRequest after(Integer hours, Integer minutes, Integer seconds) {
            return hms("AFTER", hours, minutes, seconds);
        }

        /** AT HOURS / MINUTES / SECONDS: the time of day they amount to, as TIME. */
        public StartRequest at(Integer hours, Integer minutes, Integer seconds) {
            return hms("AT", hours, minutes, seconds);
        }

        private StartRequest hms(String how, Integer h, Integer m, Integer s) {
            if (h == null && m == null && s == null) {
                throw new UnsupportedOperationException("START " + how + " with none of HOURS / MINUTES / SECONDS");
            }
            this.when = how;
            this.hours = h;
            this.minutes = m;
            this.seconds = s;
            return this;
        }

        public StartRequest termid(String termid) {
            this.termid = termid;
            return this;
        }

        public StartRequest reqid(String reqid) {
            this.reqid = reqid;
            return this;
        }

        /** FROM's bytes (null: no FROM). */
        public StartRequest from(byte[] from) {
            this.from = from;
            return this;
        }

        public StartRequest protect(boolean protect) {
            this.protect = protect;
            return this;
        }

        /** RTRANSID / RTERMID / QUEUE: values the started task RETRIEVEs (null: not given). */
        public StartRequest rtransid(String rtransid) {
            this.rtransid = rtransid;
            return this;
        }

        public StartRequest rtermid(String rtermid) {
            this.rtermid = rtermid;
            return this;
        }

        public StartRequest queue(String queue) {
            this.queue = queue;
            return this;
        }

        public StartResult issue() {
            return task.issueStart(this);
        }
    }

    /** #4270: AFTER / AT's HOURS, MINUTES, SECONDS as hhmmss, or -4 / -5 / -6 (INVREQ's RESP2, negated) for the
     *  first one out of range (IBM, EXEC CICS START, AFTER). */
    static int hhmmss(Integer h, Integer m, Integer s) {
        int given = (h != null ? 1 : 0) + (m != null ? 1 : 0) + (s != null ? 1 : 0);
        if (h != null && (h < 0 || h > 99)) {
            return -4;
        }
        if (m != null && (m < 0 || m > (given == 1 ? 5999 : 59))) {
            return -5;
        }
        if (s != null && (s < 0 || s > (given == 1 ? 359999 : 59))) {
            return -6;
        }
        int total = (h == null ? 0 : h) * 3600 + (m == null ? 0 : m) * 60 + (s == null ? 0 : s);
        return total / 3600 * 10000 + total / 60 % 60 * 100 + total % 60;
    }

    private StartResult issueStart(StartRequest q) {
        CicsTask task = root();
        String transid = q.transid;
        String how = q.when;
        int hhmmss = q.hhmmss;
        int resp2 = 0;
        if ("AFTER".equals(how) || "AT".equals(how)) {
            hhmmss = hhmmss(q.hours, q.minutes, q.seconds);
            if (hhmmss < 0) {
                resp2 = -hhmmss;
            }
        } else if (hhmmss < 0 || hhmmss / 10000 > 99) {
            resp2 = 4;
        } else if (hhmmss / 100 % 100 > 59) {
            resp2 = 5;
        } else if (hhmmss % 100 > 59) {
            resp2 = 6;
        }
        boolean isTime = "TIME".equals(how) || "AT".equals(how);
        int hh = hhmmss / 10000, mm = hhmmss / 100 % 100, ss = hhmmss % 100;
        LocalDateTime clock = now();
        LocalDateTime at = null;
        String resp = "NORMAL";
        int[] planned;
        if (q.reqid != null && (task.ownRequests.containsKey(q.reqid) || task.unexpired.containsKey(q.reqid))) {
            // IBM: IOERR when "A START operation uses a REQID name that exists. This condition occurs only when the
            // FROM option is also used" -- a REQID this task already used with FROM; any other reuse is not settled
            if (q.from == null || !task.ownWithData.contains(q.reqid)) {
                throw new UnsupportedOperationException("START REQID(" + q.reqid + ") of a request that exists"
                        + (q.from == null ? ", without FROM" : ", not this task's own with FROM") + ": not modelled");
            }
        }
        int range = resp2;
        if (range != 0) {
            resp = "INVREQ";
        } else if (q.from != null && q.from.length < 1) {  // IBM: LENGERR "if LENGTH is not greater than zero"
            resp = "LENGERR";
        } else if (q.from != null && q.from.length > 32763) {
            resp = "LENGERR";
        } else if (programs != null && !programs.transaction(q.transid)) {
            resp = "TRANSIDERR";
        } else if (q.termid != null && programs != null && !programs.terminal(q.termid)) {
            resp = "TERMIDERR";
        } else if ((planned = task.injected("START", transid.stripTrailing())) != null) {
            resp = respName(planned[0]);  // #4049: a planned condition; nothing is started
            resp2 = planned[1];
        } else if (q.reqid != null && q.from != null && task.ownWithData.contains(q.reqid)) {
            resp = "IOERR";
        } else if (isTime) {
            at = clock.toLocalDate().atStartOfDay().plusHours(hh).plusMinutes(mm).plusSeconds(ss);
            if (hh <= 23 && !at.isAfter(clock)) {
                at = at.isBefore(clock.minusHours(6)) ? at.plusDays(1) : clock;
            }
        } else {
            at = clock.plusSeconds(hh * 3600L + mm * 60L + ss);
        }
        Map<String, Object> e = new LinkedHashMap<>();
        e.put("event", "START");
        e.put("transid", q.transid);
        e.put("termid", q.termid);
        // an AFTER / AT is recorded as the interval / time it amounts to; out of range, it amounts to none
        e.put(isTime ? "time" : "interval", hhmmss < 0 ? null : String.format(java.util.Locale.ROOT, "%06d", hhmmss));
        e.put("from", q.from == null ? null : q.from.clone());
        if (q.reqid != null) {
            e.put("reqid", q.reqid);
            if (at != null) {
                task.ownRequests.put(q.reqid, at);
                if (q.from != null) {
                    task.ownWithData.add(q.reqid);
                }
            }
        }
        // #4270: the data options, only those the program named
        if (q.rtransid != null) {
            e.put("rtransid", q.rtransid);
        }
        if (q.rtermid != null) {
            e.put("rtermid", q.rtermid);
        }
        if (q.queue != null) {
            e.put("queue", q.queue);
        }
        e.put("protect", q.protect);
        e.put("resp", resp);
        if (range != 0) {
            e.put("resp2", range);  // (SPEC 6.2: where IBM documents it -- INVREQ RESP2 4 / 5 / 6)
        }
        e.put("expires", at == null ? null : at.format(ISO));
        add(e);
        return new StartResult(resp, at, resp2);
    }

    /** A START's outcome: its condition, when the request expires (null unless NORMAL) and RESP2 (#4270). */
    public record StartResult(String resp, LocalDateTime expires, int resp2) {
        public StartResult(String resp, LocalDateTime expires) {
            this(resp, expires, 0);
        }
    }

    /** #4270: the task is a RUN TRANSID child: IBM documents no RETRIEVE for it (its data comes by channel), so
     *  one is refused. */
    public CicsTask withRunChild(boolean child) {
        this.runChild = child;
        return this;
    }

    /** #4270 slice 2: RUN TRANSID(transid) CHILD (IBM CICS TS, EXEC CICS RUN TRANSID): it "starts a task on the
     *  local system ... The started task (child task) runs asynchronously with the starting task", and CICS places
     *  "the child token that represents the child task" in CHILD's 16-character area. TRANSIDERR RESP2 1 for a
     *  transaction not defined. The harness's scheduler runs the child as a non-terminal task once this task has
     *  ended: a parent that never FETCHes it cannot tell when it ran (SPEC section 4, no ties). The token's bytes are
     *  the harness's own (IBM does not document them), the same on both sides. */
    public RunResult runTransid(String transid) {
        CicsTask task = root();
        String resp = "NORMAL";
        int resp2 = 0;
        String child = null;
        if (programs != null && !programs.transaction(transid)) {
            resp = "TRANSIDERR";
            resp2 = 1;
        } else {
            child = String.format(java.util.Locale.ROOT, "GGCHILD%09d", ++task.children);
        }
        Map<String, Object> e = new LinkedHashMap<>();
        e.put("event", "RUN");
        e.put("transid", transid);
        e.put("resp", resp);
        if (resp2 != 0) {
            e.put("resp2", resp2);
        }
        add(e);
        return new RunResult(resp, resp2, child);
    }

    /** #4270: a RUN TRANSID's outcome: its condition, RESP2 and the child token (null unless NORMAL). */
    public record RunResult(String resp, int resp2, String child) {
    }

    /** RETRIEVE INTO LENGTH(maxLength) (#4006, IBM EXEC CICS RETRIEVE): the next data record of the requests
     *  the task was started for, truncated with LENGERR when longer (the length is then the record's own);
     *  ENDDATA when none is left, as for a task no START started. */
    public RetrieveResult retrieve(int maxLength) {
        return retrieve(Integer.valueOf(maxLength), false, false, false);
    }

    /** #4270: RETRIEVE [INTO LENGTH(maxLength)] [RTRANSID] [RTERMID] [QUEUE] (IBM CICS TS, EXEC CICS RETRIEVE):
     *  `maxLength` null without INTO. The next data record: ENDDATA when none is left; ENVDEFERR when the command
     *  names RTRANSID / RTERMID / QUEUE and the record's START did not give it ("occurs when a RETRIEVE command
     *  specifies an option not specified by the corresponding START command"); else FROM's data truncated to
     *  maxLength with LENGERR, and the values asked for. What IBM does not say is refused: INTO for a record whose
     *  START gave no FROM, and any RETRIEVE after an ENVDEFERR (whether that record was used up). */
    public RetrieveResult retrieve(Integer maxLength, boolean rtransid, boolean rtermid, boolean queue) {
        CicsTask task = root();
        if (task.runChild) {
            throw new UnsupportedOperationException("RETRIEVE in a RUN TRANSID child task: not documented");
        }
        if (task.retrieveRefused) {
            throw new UnsupportedOperationException("RETRIEVE after ENVDEFERR: whether the record is still there is "
                    + "not documented");
        }
        int[] planned = task.injected("RETRIEVE", "-");  // #4049: a planned condition; nothing is retrieved
        if (planned != null) {
            event("RETRIEVE", "resp", respName(planned[0]), "length", null, "data", null);
            return new RetrieveResult(respName(planned[0]), -1, null);
        }
        if (task.retrieved >= task.retrieveData.size()) {
            event("RETRIEVE", "resp", "ENDDATA", "length", null, "data", null);
            return new RetrieveResult("ENDDATA", -1, null);
        }
        StartData record = task.retrieveData.get(task.retrieved);
        if (maxLength != null && record.from() == null) {
            throw new UnsupportedOperationException("RETRIEVE INTO the record of a START with no FROM: whether that "
                    + "is ENVDEFERR is not documented");
        }
        if ((rtransid && record.rtransid() == null) || (rtermid && record.rtermid() == null)
                || (queue && record.queue() == null)) {
            task.retrieveRefused = true;
            event("RETRIEVE", "resp", "ENVDEFERR", "length", null, "data", null);
            return new RetrieveResult("ENVDEFERR", -1, null);
        }
        task.retrieved++;
        byte[] stored = record.from();
        byte[] data = null;
        String resp = "NORMAL";
        if (maxLength != null) {
            data = stored.length > maxLength ? Arrays.copyOf(stored, Math.max(maxLength, 0)) : stored.clone();
            resp = stored.length > maxLength ? "LENGERR" : "NORMAL";
        }
        Map<String, Object> e = new LinkedHashMap<>();
        e.put("event", "RETRIEVE");
        e.put("resp", resp);
        e.put("length", maxLength == null ? null : stored.length);
        e.put("data", data);
        if (rtransid) {
            e.put("rtransid", record.rtransid());
        }
        if (rtermid) {
            e.put("rtermid", record.rtermid());
        }
        if (queue) {
            e.put("queue", record.queue());
        }
        add(e);
        return new RetrieveResult(resp, maxLength == null ? -1 : stored.length, data,
                rtransid ? record.rtransid() : null, rtermid ? record.rtermid() : null, queue ? record.queue() : null);
    }

    /** A RETRIEVE's outcome: its condition, the LENGTH it sets (-1 when none), the data moved INTO, and (#4270) the
     *  RTRANSID / RTERMID / QUEUE values it returns (null when not asked for or not returned). */
    public record RetrieveResult(String resp, int length, byte[] data, String rtransid, String rtermid, String queue) {
        public RetrieveResult(String resp, int length, byte[] data) {
            this(resp, length, data, null, null, null);
        }
    }

    /** CANCEL REQID(reqid) (#4006, IBM EXEC CICS CANCEL): NORMAL for a request that has not expired yet (the
     *  harness then drops it), NOTFND when none matches "an unexpired interval control command". */
    public String cancel(String reqid) {
        CicsTask task = root();
        int[] planned = task.injected("CANCEL", reqid.stripTrailing());  // #4049: a planned condition
        if (planned != null) {
            event("CANCEL", "reqid", reqid, "resp", respName(planned[0]));
            return respName(planned[0]);
        }
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

    // ---- #4270: channels and containers (IBM CICS TS: PUT / GET / DELETE CONTAINER (CHANNEL), LINK / XCTL CHANNEL,
    // ASSIGN CHANNEL, "Scope of a channel"). A container holds bytes, exactly as the program put them: a BIT container
    // is never converted, and a CHAR one put and got with no FROMCCSID / INTOCCSID is in the region's CCSID both ways
    // (GET CONTAINER: "If INTOCCSID and INTOCODEPAGE are not specified, the value for conversion defaults to the CCSID
    // of the region"), so it is not converted either. The CCSID options are refused by the translator.

    /** A channel: its name and its containers, in creation order. */
    public static final class Channel {
        private final String name;
        private final Map<String, Container> containers = new LinkedHashMap<>();

        public Channel(String name) {
            this.name = name;
        }

        public String name() {
            return name;
        }

        /** #4270 (X24): a container this channel holds before any program runs -- what the parent of a RUN TRANSID
         *  CHANNEL, or a LINK CHANNEL caller outside the region, put there (BIT or CHAR, as its PUT gave it). */
        public Channel with(String container, byte[] data, boolean bit) {
            containers.put(channelName(container, "container"), new Container(data.clone(), bit));
            return this;
        }

        /** The containers, by name (a copy). */
        public Map<String, byte[]> containers() {
            Map<String, byte[]> out = new LinkedHashMap<>();
            containers.forEach((k, v) -> out.put(k, v.data.clone()));
            return out;
        }
    }

    private static final class Container {
        private byte[] data;
        private final boolean bit;

        private Container(byte[] data, boolean bit) {
            this.data = data;
            this.bit = bit;
        }
    }

    /** A container command's outcome: its condition and RESP2, the container's length (GET: FLENGTH's value on
     *  NORMAL / LENGERR, else -1) and the bytes it moves INTO (GET, else null). */
    public record ContainerResult(String resp, int resp2, int length, byte[] data) {
        public boolean normal() {
            return "NORMAL".equals(resp);
        }
    }

    /** A channel or container name as CICS compares it: the 16-character value without its trailing blanks. One
     *  with nothing else, or with an embedded blank, is refused (CHANNELERR / CONTAINERERR "illegal character"
     *  is IBM's, but which characters its names allow is not modelled). */
    private static String channelName(String name, String what) {
        String n = name == null ? "" : name;
        int end = n.length();
        while (end > 0 && (n.charAt(end - 1) == ' ' || n.charAt(end - 1) == 0)) {
            end--;
        }
        n = n.substring(0, end);
        if (n.isEmpty() || n.contains(" ") || n.length() > 16) {
            throw new UnsupportedOperationException(what + " name '" + name + "': not modelled");
        }
        return n;
    }

    private java.util.Set<String> inScope() {
        java.util.Set<String> all = new java.util.HashSet<>(channels.keySet());
        all.addAll(droppedChannels);
        return all;
    }

    /** This program's channel: `passed` (LINK / XCTL CHANNEL), the only one in its scope; `before` the names in
     *  the XCTLing program's scope, which an XCTL leaves behind. IBM shows a channel passed on XCTL in the scope of
     *  both programs ("Scope of a channel") but says nothing of the others: naming one is refused, never guessed. */
    private void passChannel(Channel passed, java.util.Set<String> before) {
        currentChannel = passed;
        channels = new HashMap<>();
        if (passed != null) {
            channels.put(passed.name, passed);
        }
        java.util.Set<String> dropped = new java.util.HashSet<>(before);
        if (passed != null) {
            dropped.remove(passed.name);
        }
        droppedChannels = dropped;
    }

    /** The channel `name` names in this program's scope; `create`: a new, empty one when there is none (PUT
     *  CONTAINER: "If the channel does not exist, it is created"; LINK / XCTL CHANNEL: "a new empty channel is
     *  created"); else null. */
    private Channel scopeChannel(String name, boolean create) {
        String n = channelName(name, "channel");
        if (droppedChannels.contains(n)) {
            throw new UnsupportedOperationException("channel " + n + " after an XCTL that did not pass it: its scope "
                    + "is not documented, not modelled");
        }
        Channel ch = channels.get(n);
        if (ch == null && create) {
            ch = new Channel(n);
            channels.put(n, ch);
        }
        return ch;
    }

    /** PUT CONTAINER(container) [CHANNEL(channel)] FROM FLENGTH [BIT | CHAR | no data type] [APPEND] (IBM, EXEC
     *  CICS PUT CONTAINER (CHANNEL)). `channel` null: the current channel, INVREQ RESP2 4 without one (1 when a data
     *  type was named). FLENGTH below zero: LENGERR RESP2 1. A new container takes the data type given, else BIT
     *  ("the default value, unless FROMCCSID or FROMCODEPAGE option is specified"); an existing one keeps its own.
     *  Naming the other type for an existing container is refused: IBM says both that DATATYPE "applies only to new
     *  containers" and that "an attempt ... to change the data-type of an existing container" is INVREQ RESP2 33.
     *  The data replaces the container's, or with APPEND follows it. */
    public ContainerResult putContainer(String channel, String container, byte[] data, int flength, String type,
                                        boolean append) {
        Channel ch = channel == null ? currentChannel : scopeChannel(channel, true);
        String name = channelName(container, "container");
        if (ch == null) {
            return new ContainerResult("INVREQ", type == null ? 4 : 1, -1, null);
        }
        if (flength < 0) {
            return new ContainerResult("LENGERR", 1, -1, null);
        }
        Container c = ch.containers.get(name);
        if (c != null && type != null && c.bit != "BIT".equals(type)) {
            throw new UnsupportedOperationException("PUT CONTAINER " + type + " on an existing container of the other "
                    + "data type: ignored or INVREQ RESP2 33 is not settled by IBM's documentation, not modelled");
        }
        if (c == null) {
            ch.containers.put(name, new Container(data.clone(), !"CHAR".equals(type)));
        } else if (append) {
            byte[] joined = Arrays.copyOf(c.data, c.data.length + data.length);
            System.arraycopy(data, 0, joined, c.data.length, data.length);
            c.data = joined;
        } else {
            c.data = data.clone();
        }
        return new ContainerResult("NORMAL", 0, -1, null);
    }

    /** GET CONTAINER(container) [CHANNEL(channel)] INTO FLENGTH | NODATA FLENGTH (IBM, EXEC CICS GET CONTAINER
     *  (CHANNEL)). `maxLength` is the most INTO takes -- FLENGTH's value, else INTO's length -- or -1 for NODATA.
     *  CHANNELERR RESP2 2 for a channel not in scope, INVREQ RESP2 4 with no CHANNEL and no current channel,
     *  CONTAINERERR RESP2 10 for a container the channel does not have. Longer data is truncated to INTO with
     *  LENGERR RESP2 11; FLENGTH "returns the length of the data in the container" (NORMAL, LENGERR). */
    public ContainerResult getContainer(String channel, String container, int maxLength) {
        Channel ch = channel == null ? currentChannel : scopeChannel(channel, false);
        String name = channelName(container, "container");
        if (ch == null) {
            return channel == null ? new ContainerResult("INVREQ", 4, -1, null)
                    : new ContainerResult("CHANNELERR", 2, -1, null);
        }
        Container c = ch.containers.get(name);
        if (c == null) {
            return new ContainerResult("CONTAINERERR", 10, -1, null);
        }
        if (maxLength < 0) {
            return new ContainerResult("NORMAL", 0, c.data.length, null);
        }
        if (c.data.length > maxLength) {
            return new ContainerResult("LENGERR", 11, c.data.length, Arrays.copyOf(c.data, maxLength));
        }
        return new ContainerResult("NORMAL", 0, c.data.length, c.data.clone());
    }

    /** DELETE CONTAINER(container) [CHANNEL(channel)] (IBM, EXEC CICS DELETE CONTAINER (CHANNEL)): CHANNELERR
     *  RESP2 2, INVREQ RESP2 4 ("issued outside the scope of a currently-active channel"), CONTAINERERR RESP2 10. */
    public ContainerResult deleteContainer(String channel, String container) {
        Channel ch = channel == null ? currentChannel : scopeChannel(channel, false);
        String name = channelName(container, "container");
        if (ch == null) {
            return channel == null ? new ContainerResult("INVREQ", 4, -1, null)
                    : new ContainerResult("CHANNELERR", 2, -1, null);
        }
        if (ch.containers.remove(name) == null) {
            return new ContainerResult("CONTAINERERR", 10, -1, null);
        }
        return new ContainerResult("NORMAL", 0, -1, null);
    }

    /** ASSIGN CHANNEL: "the 16-character name of the current channel of the program, if one exists; otherwise,
     *  blanks". */
    public String assignChannel() {
        return String.format(java.util.Locale.ROOT, "%-16s", currentChannel == null ? "" : currentChannel.name);
    }

    /** The current channel (null: none), for a caller that drives the task (#4270). */
    public Channel currentChannel() {
        return currentChannel;
    }

    /** Starts this level with `channel` as its current channel: what a program LINKed with a channel from outside
     *  the region, or started with one, receives (#4270). */
    public CicsTask withChannel(Channel channel) {
        passChannel(channel, java.util.Set.of());
        return this;
    }

    /** LINK PROGRAM(program) CHANNEL(channel) (IBM, EXEC CICS LINK: "the name ... of a channel that is to be made
     *  available to the called program"; one that does not exist is created empty): the callee's current channel,
     *  and the only one in its scope; what it puts there, the caller sees. EIBCALEN 0. */
    public String linkChannel(String program, String channel) {
        return link(program, null, 0, null, scopeChannel(channel, true));
    }

    /** XCTL PROGRAM(program) CHANNEL(channel): as LINK CHANNEL, at the same level. */
    public String xctlChannel(String program, String channel) {
        return xctl(program, null, null, scopeChannel(channel, true));
    }

    /** The bytes of the COMMAREA this program was LINKed with, when its caller passed them (by reference: what it
     *  writes there its caller sees); null otherwise. */
    public byte[] linkArea() {
        return linkArea;
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

    /** #4270 READ FILE(file) GTEQ / GENERIC [UPDATE] (oracle_assumptions.md X22): `lookup` searches the file (the
     *  det port's DetCics.Store.search). RESP NORMAL and the record found, or NOTFND (13) with IBM's RESP2 80 ("An
     *  attempt to retrieve a record based on the search argument provided is unsuccessful") -- or the condition the
     *  harness planned, and then nothing is read. With `update` the file's record is held for a REWRITE. */
    public <T> FileRead<T> readSearch(String file, boolean update, java.util.function.Supplier<Optional<T>> lookup) {
        int[] planned = root().injected("READ", file);
        if (planned != null) {
            return new FileRead<>(planned[0], planned[1], null);
        }
        T record = lookup.get().orElse(null);
        if (record == null) {
            return new FileRead<>(13, 80, null);
        }
        if (update) {
            root().held.add(file);
        }
        return new FileRead<>(0, 0, record);
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
            return done(planned[0], planned[1]);
        }
        if (!exists) {
            return done(13, 80);
        }
        remove.run();
        return done(0, 0);
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
     *  started, and the last key read and in which direction (0: none yet). An RBA browse (#4213) keeps RBAs. */
    private static final class Browse {
        java.util.function.Supplier<java.util.NavigableSet<String>> keys;
        boolean equal;
        String start;
        String last;
        int dir;
        boolean rba;
        long rbaStart;
        long rbaLast = -1;
    }

    private final Map<String, Browse> browses = new java.util.HashMap<>();

    /** What a READNEXT / READPREV found: its RESP and the key read (null when none; then look nothing up). */
    public record Browsed(int resp, int resp2, String key) {
        public boolean normal() {
            return resp == 0;
        }
    }

    private static boolean highValues(String key) {
        return !key.isEmpty() && key.chars().allMatch(ch -> ch == '\\u00ff');  // ASCII escape: javac reads source as cp1252 on Windows
    }

    private int lastResp2;

    /** The RESP2 of the last STARTBR / ENDBR / DELETE by key (those that return only their RESP, an int): IBM's
     *  documented value where the command states one (#4657) -- STARTBR INVREQ 33 (a browse is active) and NOTFND 80,
     *  ENDBR INVREQ 35 (no browse), DELETE NOTFND 80 -- else 0, or the planned fault's. */
    public int resp2() {
        return root().lastResp2;
    }

    private int done(int resp, int resp2) {
        root().lastResp2 = resp2;
        return resp;
    }

    /** STARTBR FILE(file) RIDFLD(key) [GTEQ | EQUAL] (IBM CICS TS): positions a browse on the first key >= `key`
     *  (GTEQ, the default) or on `key` itself (EQUAL); NOTFND (13) when there is none. A key of all X'FF'
     *  (HIGH-VALUES) positions at the end, for READPREV. A second STARTBR on the file: INVREQ (16). `keys`: the
     *  file's keys, in key order (e.g. the repository's ids as a TreeSet). */
    public int startbr(String file, String key, boolean equal,
                       java.util.function.Supplier<java.util.NavigableSet<String>> keys) {
        int[] planned = root().injected("STARTBR", file);
        if (planned != null) {
            return done(planned[0], planned[1]);
        }
        if (root().esds.containsKey(file)) {
            throw refused("STARTBR by key on " + file + ", an ESDS");
        }
        Map<String, Browse> all = root().browses;
        if (all.containsKey(file)) {
            return done(16, 33);
        }
        java.util.NavigableSet<String> k = keys.get();
        if (!highValues(key) && (equal ? !k.contains(key) : k.ceiling(key) == null)) {
            return done(13, 80);
        }
        Browse b = new Browse();
        b.keys = keys;
        b.equal = equal;
        b.start = key;
        all.put(file, b);
        return done(0, 0);
    }

    /** READNEXT FILE(file) RIDFLD(ridfld): the key of the next record -- the one STARTBR positioned on first; set
     *  RIDFLD to it and look the record up by it. A RIDFLD the program changed, or a READNEXT after a READPREV,
     *  repositions at the first key >= RIDFLD. ENDFILE (20) past the last; INVREQ (16) with no browse. */
    public Browsed readnext(String file, String ridfld) {
        int[] planned = root().injected("READNEXT", file);
        if (planned != null) {
            return new Browsed(planned[0], planned.length > 1 ? planned[1] : 0, null);
        }
        Browse b = root().browses.get(file);
        if (b == null) {
            return new Browsed(16, 34, null);
        }
        if (b.rba) {
            throw refused("READNEXT by key in an RBA browse of " + file);
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
            return new Browsed(20, 90, null);
        }
        b.last = at;
        b.dir = 1;
        return new Browsed(0, 0, at);
    }

    /** READPREV FILE(file) RIDFLD(ridfld): the key of the previous record. Right after STARTBR the STARTBR key must
     *  exist (else NOTFND, 13); after a READNEXT, or with RIDFLD changed, it repositions to RIDFLD and reads that
     *  record -- so it reads again the record READNEXT just read; after a HIGH-VALUES STARTBR, the last record.
     *  ENDFILE (20) before the first; INVREQ (16) with no browse. */
    public Browsed readprev(String file, String ridfld) {
        int[] planned = root().injected("READPREV", file);
        if (planned != null) {
            return new Browsed(planned[0], planned.length > 1 ? planned[1] : 0, null);
        }
        Browse b = root().browses.get(file);
        if (b == null) {
            return new Browsed(16, 34, null);
        }
        if (b.rba) {
            throw refused("READPREV by key in an RBA browse of " + file);
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
            return new Browsed(none, none == 20 ? 90 : 80, null);
        }
        b.last = at;
        b.dir = -1;
        return new Browsed(0, 0, at);
    }

    // ---- #4213: an ESDS browsed by relative byte address (STARTBR / READNEXT / READPREV ... RBA) ----------------
    // IBM CICS TS, EXEC CICS STARTBR / READNEXT / READPREV, option RBA: RIDFLD "contains a relative byte address",
    // and READNEXT / READPREV "return the relative byte address of each retrieved record". EQUAL is "the default for a
    // direct ESDS browse"; a RIDFLD of X'FF's positions at the end, for READPREV. The records are fixed-length, in
    // arrival order, and a record's RBA is its byte offset (oracle_assumptions.md X13); the browse moves as the keyed
    // one does, in RBA order. Refused (UnsupportedOperationException, "... not modelled"), as the COBOL side's stub
    // refuses them: an RBA that addresses no record, RBA on a file that is not an ESDS, a browse mixing RBA and keys.

    /** An ESDS of the region: its records in arrival order, each `reclen` bytes. */
    private record Esds(int reclen, List<byte[]> records) {
    }

    private final Map<String, Esds> esds = new java.util.HashMap<>();

    /** The region's ESDS `file` (a case's dataset): its records in arrival order, each `reclen` bytes. */
    public CicsTask withEsds(String file, int reclen, List<byte[]> records) {
        root().esds.put(file, new Esds(reclen, new ArrayList<>(records)));
        return this;
    }

    /** The ESDS `file`'s records, as the task leaves them. */
    public List<byte[]> esdsRecords(String file) {
        return root().esds.get(file).records();
    }

    /** A fullword RIDFLD's RBA: its first four bytes, big-endian, unsigned. */
    public static long rba(byte[] ridfld) {
        long v = 0;
        for (int i = 0; i < 4; i++) {
            v = (v << 8) | (ridfld[i] & 0xFF);
        }
        return v;
    }

    /** An RBA as the fullword CICS returns in RIDFLD. */
    public static byte[] rbaBytes(long rba) {
        return new byte[] {(byte) (rba >>> 24), (byte) (rba >>> 16), (byte) (rba >>> 8), (byte) rba};
    }

    private static final long RBA_END = 0xFFFFFFFFL;

    private static UnsupportedOperationException refused(String what) {
        return new UnsupportedOperationException(what + ": not modelled");
    }

    private Esds esdsOf(String file) {
        Esds e = root().esds.get(file);
        if (e == null) {
            throw refused("STARTBR RBA on " + file + ", not an ESDS");
        }
        return e;
    }

    /** The record (0-based) at `rba`; refused when no record starts there. */
    private static int rbaRecord(String verb, String file, Esds e, long rba) {
        if (rba % e.reclen() == 0 && rba / e.reclen() < e.records().size()) {
            return (int) (rba / e.reclen());
        }
        throw refused(verb + " RBA " + rba + " on " + file + ": no record starts there");
    }

    /** What a READNEXT / READPREV ... RBA found: its RESP and RESP2, and the record and its RBA (null: none). A record
     *  longer than INTO is LENGERR (22) with the record still returned (CICS copies what INTO takes). */
    public record BrowsedRba(int resp, int resp2, long rba, byte[] record) {
        public boolean normal() {
            return resp == 0;
        }
    }

    /** STARTBR FILE(file) RIDFLD(rba) RBA [EQUAL]: positions on the record at `rba`, or at the end for X'FFFFFFFF'.
     *  INVREQ (16) when a browse of the file is active. */
    public int startbrRba(String file, long rba) {
        int[] planned = root().injected("STARTBR", file);
        if (planned != null) {
            return done(planned[0], planned[1]);
        }
        Esds e = esdsOf(file);
        Map<String, Browse> all = root().browses;
        if (all.containsKey(file)) {
            return done(16, 33);
        }
        if (rba != RBA_END) {
            rbaRecord("STARTBR", file, e, rba);
        }
        Browse b = new Browse();
        b.rba = true;
        b.equal = true;
        b.rbaStart = rba;
        all.put(file, b);
        return done(0, 0);
    }

    /** READNEXT FILE(file) RIDFLD(ridfld) RBA: the record STARTBR positioned on, then each next; a RIDFLD the program
     *  changed, or a READNEXT after a READPREV, repositions at that RBA. ENDFILE (20) past the last; INVREQ (16) with
     *  no browse. `intoLength`: INTO's length (LENGERR past it). */
    public BrowsedRba readnextRba(String file, long ridfld, int intoLength) {
        return rbaRead("READNEXT", 1, file, ridfld, intoLength);
    }

    /** READPREV FILE(file) RIDFLD(ridfld) RBA: right after STARTBR the STARTBR's record (or, after X'FFFFFFFF', the
     *  last); after a READNEXT, or with RIDFLD changed, the record at RIDFLD -- the one READNEXT just read, again;
     *  then each previous. ENDFILE (20) before the first; INVREQ (16) with no browse. */
    public BrowsedRba readprevRba(String file, long ridfld, int intoLength) {
        return rbaRead("READPREV", -1, file, ridfld, intoLength);
    }

    private BrowsedRba rbaRead(String verb, int dir, String file, long ridfld, int intoLength) {
        int[] planned = root().injected(verb, file);
        if (planned != null) {
            return new BrowsedRba(planned[0], planned.length > 1 ? planned[1] : 0, ridfld, null);
        }
        Browse b = root().browses.get(file);
        if (b == null) {
            return new BrowsedRba(16, 34, ridfld, null);
        }
        if (!b.rba) {
            throw refused(verb + " by RBA in a keyed browse of " + file);
        }
        Esds e = root().esds.get(file);
        int n = e.records().size();
        boolean changed = ridfld != (b.rbaLast >= 0 ? b.rbaLast : b.rbaStart);
        long at;
        if (dir > 0) {
            if (b.dir == 0 && b.rbaStart != RBA_END && !changed) {
                at = rbaRecord(verb, file, e, ridfld);
            } else if (b.dir == 1 && !changed) {
                at = ridfld / e.reclen() + 1;
            } else if (ridfld == RBA_END) {
                at = -1;
            } else {
                at = rbaRecord(verb, file, e, ridfld);
            }
            if (at >= n) {
                at = -1;
            }
        } else {
            if (ridfld == RBA_END && (b.dir == 0 || changed)) {
                at = n - 1;
            } else if (b.dir == -1 && !changed) {
                at = ridfld / e.reclen() - 1;
            } else {
                at = rbaRecord(verb, file, e, ridfld);
            }
        }
        if (at < 0) {
            return new BrowsedRba(20, 90, ridfld, null);
        }
        byte[] rec = e.records().get((int) at);
        long rba = at * e.reclen();
        b.rbaLast = rba;
        b.dir = dir;
        return rec.length > intoLength ? new BrowsedRba(22, 11, rba, rec) : new BrowsedRba(0, 0, rba, rec);
    }

    /** ENDBR FILE(file): the browse ends; INVREQ (16) when none is active. */
    public int endbr(String file) {
        int[] planned = root().injected("ENDBR", file);
        if (planned != null) {
            return done(planned[0], planned[1]);
        }
        return root().browses.remove(file) != null ? done(0, 0) : done(16, 35);
    }

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
        root().syncpointed = true;
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
            int[] planned = task.root().injected("WRITEQ-TS", queue.stripTrailing());  // #4049: nothing is written
            if (planned != null) {
                resp = respName(planned[0]);
            } else if (data == null || data.length < 1 || data.length > 32763) {
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
            root().returnedArea = commarea;
            root().returnedLength = commarea == null ? null : length;
        }
        ended = true;
    }

    /** The COMMAREA the task's level-1 RETURN passed on (#4343: what handleTransaction answers), as `type`; null when
     *  the task RETURNed none, or has not RETURNed. A COMMAREA of another class is converted by layout (#4449) when
     *  both are laid out as bytes (the generator writes toCommarea / fromCommarea into the DTOs a facade converts
     *  between): the bytes passed -- the record's, or its first LENGTH -- read through `type`, as the program reading
     *  them through its own record sees them. Anything else is refused, never guessed: a class with no layout, or
     *  fewer bytes than `type`'s record (never passed). */
    public <T> T returned(Class<T> type) {
        Object area = root().returnedArea;
        if (area == null || type.isInstance(area)) {
            return type.cast(area);
        }
        String refused = "the task RETURNed a " + area.getClass().getName() + ", not a " + type.getName();
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

        /** The program level `program` runs at when another program LINKs (or XCTLs) to it with `commarea` (null:
         *  none) -- the whole record, passed by reference: what the program changes in it, the caller sees. */
        CicsTask linked(String program, Object commarea);

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
        return xctl(program, commarea, length, null);
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
        event("XCTL", "program", program, "length", commarea == null ? Integer.valueOf(0) : length, "commarea",
                snapshot.apply(commarea), "resp", resp, "resp2", resp2);
        if ("NORMAL".equals(resp)) {
            xctlTarget = program;
            xctlCommarea = commarea;
            xctlLength = commarea == null ? Integer.valueOf(0) : length;
            xctlChannel = pendingChannel;
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
            // the task terminates abnormally: CICS backs out its unit of work (recoverable resources)
            if (!root().syncpointed && root().rollbackHook != null) {
                root().rollbackHook.run();
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

    /** #4049: a DFHRESP number a fault plan names, as the condition's name (IBM CICS "RESP values"; the spec's
     *  table, CicsSpec). */
    static String respName(int resp) {
        String name = CicsSpec.name(resp);
        if (name == null) {
            throw new IllegalArgumentException("no condition name known for RESP " + resp);
        }
        return name;
    }

    /** The abend code of an unhandled condition (IBM's AEIx / AEYx codes, the AEIA topic; the spec's table,
     *  CicsSpec). */
    public static String abcodeFor(String condition) {
        return CicsSpec.abcodeFor(condition);
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
