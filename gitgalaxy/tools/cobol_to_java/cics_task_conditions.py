#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: CicsTask's conditions (#4003, #3989, #4270, split out by #5274)
#
# PURPOSE:
# The conditions family of the CICS task runtime the transaction forge emits (CICS_TASK_JAVA): the ASSIGN accessors
# (APPLID, SYSID, STARTCODE, USERID, FACILITY, SCRNHT / SCRNWD, INVOKINGPROG, ABCODE), HANDLE ABEND (LABEL, CANCEL,
# RESET), PUSH / POP HANDLE, ABEND and the abends of an unhandled condition, and the RESP / abend-code names. These
# were scattered through the class; the forge splices CONDITIONS_JAVA into CicsTask as one span, so the class holds
# the same members in a different order.
# ==============================================================================

CONDITIONS_JAVA = """\
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
        statedTerminal();
        return termid() == null ? 16 : 0;
    }

    /** #5126: whether the task has a terminal is a fact whoever runs the task states (withTermid; null states "none",
     *  as the stub's empty $GGCICS_FACILITY); unstated it is refused, as the stub refuses, never guessed. */
    private void statedTerminal() {
        if (!root().termidStated) {
            throw new IllegalStateException("ASSIGN FACILITY / TERMCHK: the task's terminal is not stated (withTermid)");
        }
    }

    /** ASSIGN FACILITY: the principal facility, the task's terminal, 4 characters. */
    public String assignFacility() {
        statedTerminal();
        if (termid() == null) {
            throw new IllegalStateException("ASSIGN FACILITY: the task has no terminal (assignTerminalResp is INVREQ)");
        }
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

    /** ASSIGN INVOKINGPROG: the program that LINKed or XCTLed to this one (IBM CICS TS, ASSIGN), 8 characters;
     *  blanks for a task's first program. */
    public String invokingProgram() {
        return String.format(java.util.Locale.ROOT, "%-8s", invoker == null ? "" : invoker);
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

    /** SEND MAP / RECEIVE MAP naming a map its mapset does not hold (#4270, register X31): IBM abend ABM0 "The map
     *  specified for a basic mapping support (BMS) request could not be located", the transaction "abnormally
     *  terminated with a CICS transaction dump". CICS raises no condition for it, so RESP / HANDLE CONDITION do not
     *  see it; a HANDLE ABEND exit does (cause "system": an abend CICS itself raises). Same result as abend. */
    public String abendMapNotFound(String map, String mapset) {
        return abend("ABM0", "system", null, false);
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
            tdUowEnd(true);  // #5168: a LOGICAL TD queue goes back to the last SYNCPOINT, as the stub's uow_end(1)
            resourceUowEnd(true);  // #4892: and an MQ unit of work (W5)
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
"""
