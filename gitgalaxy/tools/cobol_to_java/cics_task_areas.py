#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: CicsTask's terminal id and system-area accessors (termid / TWA / TCTUA / CWA, split out by #5274)
#
# PURPOSE:
# The EIBTRMID accessors (withTermid, withTermidIfStated, termid) and the ADDRESS TWA / TCTUA / CWA support (#5079, X59:
# the area fields, withTwaSize / withTctua / withCwa, the three handles) of the CICS task runtime the transaction forge
# emits (CICS_TASK_JAVA). The forge splices it into CicsTask where it always sat, so the class is byte-identical.
# ==============================================================================

AREAS_JAVA = """\
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

    // #5079 (X59): ADDRESS TWA / TCTUA (IBM CICS TS, EXEC CICS ADDRESS: "the address of the task's transaction work area" /
    // "of the terminal control table user area"). Each area's size is a fact of the definition (TRANSACTION TWASIZE,
    // TYPETERM USERAREALEN) that whoever runs the task states; an area of size 0 or unstated does not exist. The TWA is the
    // task's (every program it LINKs to sees the same bytes); the TCTUA is the terminal's, so the caller keeps one array per
    // terminal and hands it to each task that terminal starts.
    private byte[] twa;                                     // the task's root's
    private byte[] tctua;                                   // the task's root's (the caller's array: it outlives the task)
    private byte[] cwa;                                     // the task's root's (the caller's array: one for the whole region)

    /** TRANSACTION TWASIZE(n): the task's transaction work area is `size` bytes; 0 means none. */
    public CicsTask withTwaSize(int size) {
        this.twa = size > 0 ? new byte[size] : null;
        return this;
    }

    /** The terminal's TCTUA, USERAREALEN bytes the caller keeps across the terminal's tasks; null means none. */
    public CicsTask withTctua(byte[] area) {
        this.tctua = area != null && area.length > 0 ? area : null;
        return this;
    }

    /** The region's CWA (IBM, SIT WRKAREA: "the number of bytes ... for the common work area"), one array the caller keeps for
     *  every task of the region; null or empty means none. */
    public CicsTask withCwa(byte[] area) {
        this.cwa = area != null && area.length > 0 ? area : null;
        return this;
    }

    /** ADDRESS TWA: the handle of the TWA's bytes, the same one each time and at every LINK level; 0 for a task with none. */
    public long twaHandle() {
        byte[] a = root().twa;
        return a == null ? 0 : addressOf(a);
    }

    /** ADDRESS TCTUA: the handle of the terminal's user area; 0 for a task with none. */
    public long tctuaHandle() {
        byte[] a = root().tctua;
        return a == null ? 0 : addressOf(a);
    }

    /** ADDRESS CWA: the handle of the region's common work area; 0 for a task with none. */
    public long cwaHandle() {
        byte[] a = root().cwa;
        return a == null ? 0 : addressOf(a);
    }

"""
