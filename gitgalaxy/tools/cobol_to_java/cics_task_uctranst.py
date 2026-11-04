#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: CicsTask's UCTRANST support (INQUIRE / SET TERMINAL UCTRANST, split out by #5274)
#
# PURPOSE:
# The UCTRANST part of the CICS task runtime the transaction forge emits (CICS_TASK_JAVA): the terminal's stated UCTRANST
# (withUctranst), the CVDA table, the terminal check, INQUIRE / SET TERMINAL UCTRANST (#4415, X26) and the two guards
# the terminal RECEIVE methods call after a SET (#6271). The forge splices it into CicsTask where it always sat, so the
# class is byte-identical.
# ==============================================================================

UCTRANST_JAVA = """\
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

    /** #6271 (X26): a RECEIVE MAP after a SET reads the input under the terminal's new UCTRANST. NOUCTRAN and TRANIDONLY
     *  (only the transaction id is translated) leave the typed data as recorded; UCTRAN would upper-case it, which is
     *  not modelled (refused). */
    private void mapInputAfterUctranstSet() {
        if (root().uctranstSet && "UCTRAN".equals(root().uctranst)) {
            throw refused("RECEIVE MAP after SET TERMINAL UCTRANST(UCTRAN): the upper-case translation of typed input is not modelled");
        }
    }

    private void inputAfterUctranstSet() {
        if (root().uctranstSet) {
            throw refused("a terminal RECEIVE after SET TERMINAL UCTRANST (IBM does not say when the change takes effect)");
        }
    }

"""
