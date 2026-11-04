#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: CicsTask's URIMAP browse and WRITE OPERATOR (split out by #5274)
#
# PURPOSE:
# The installed-URIMAP facts and INQUIRE URIMAP's browse (#4270, register X32) and WRITE OPERATOR (the console message
# event and its TEXTLENGTH / ROUTECODES checks) of the CICS task runtime the transaction forge emits (CICS_TASK_JAVA).
# The forge splices it into CicsTask where it always sat, so the class is byte-identical.
# ==============================================================================

URIMAP_JAVA = """\
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
        return writeOperator(text, null, null, null)[0];
    }

    /** The same with TEXTLENGTH (the first n bytes of the area are the text; IBM: 0-690 without REPLY, else INVREQ RESP2 1)
     *  and ROUTECODES / NUMROUTES (each of the first numRoutes bytes a code of 1-28, else INVREQ RESP2 3). A null argument
     *  is an option not given. IBM leaves a NUMROUTES below 1 open (refused); the routes are no observable here (the
     *  console is not modelled, the event is the text), and EVENTUAL changes only when the operator acts. Returns
     *  {RESP, RESP2}. */
    public int[] writeOperator(String text, Integer textLength, String routes, Integer numRoutes) {
        if (textLength != null && (textLength < 0 || textLength > 690)) {
            return new int[] {16, 1};
        }
        if (textLength != null) {
            if (textLength > text.length()) {
                throw refused("WRITE OPERATOR TEXTLENGTH past the text area");
            }
            text = text.substring(0, textLength);
        }
        if (routes != null) {
            if (numRoutes < 1 || numRoutes > routes.length()) {
                throw refused("WRITE OPERATOR NUMROUTES IBM leaves open");
            }
            for (int i = 0; i < numRoutes; i++) {
                int code = routes.charAt(i) & 0xFF;
                if (code < 1 || code > 28) {
                    return new int[] {16, 3};
                }
            }
        }
        String t = text.stripTrailing();
        if (text.length() > 113 || t.matches("(?s)DFH([A-Za-z]{2})?[0-9]{4}.*")) {
            throw refused("WRITE OPERATOR text IBM reformats");
        }
        event("WRITE-OPERATOR", "text", text, "resp", "NORMAL");
        return new int[] {0, 0};
    }

"""
