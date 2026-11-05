#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: CicsTask's INQUIRE ASSOCIATION support (origin data, ODFACILTYPE; split out by #5274)
#
# PURPOSE:
# The association part of the CICS task runtime the transaction forge emits (CICS_TASK_JAVA): the task's stated origin
# data (withOrigin), IBM's ODFACILTYPE CVDA table and INQUIRE ASSOCIATION (#4415 slice 2, X29). The forge splices it
# into CicsTask where it always sat, so the class is byte-identical.
# ==============================================================================

ASSOCIATION_JAVA = """\
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

"""
