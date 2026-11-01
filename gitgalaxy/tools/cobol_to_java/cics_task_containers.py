#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: CicsTask's channels and containers (#4270, split out by #5274)
#
# PURPOSE:
# The channels / containers family of the CICS task runtime the transaction
# forge emits (CICS_TASK_JAVA): PUT / GET / DELETE / MOVE CONTAINER, the
# container browse, DELETE / QUERY CHANNEL, the CCSID conversion, a channel's
# scope and ASSIGN / LINK / XCTL CHANNEL. The forge splices CONTAINERS_JAVA
# into CicsTask at the place it always sat, so the class is byte-identical.
# ==============================================================================

CONTAINERS_JAVA = """\
    // ---- #4270: channels and containers (IBM CICS TS: PUT / GET / DELETE CONTAINER (CHANNEL), LINK / XCTL CHANNEL,
    // ASSIGN CHANNEL, "Scope of a channel"). A container holds bytes, exactly as the program put them: a BIT container
    // is never converted, and a CHAR one put and got with no FROMCCSID / INTOCCSID is in the region's CCSID both ways
    // (GET CONTAINER: "If INTOCCSID and INTOCODEPAGE are not specified, the value for conversion defaults to the CCSID
    // of the region"), so it is not converted either. The CCSID options are refused by the translator.

    /** A channel: its name and its containers, in creation order. */
    public static final class Channel {
        private final String name;
        private final Map<String, Container> containers = new LinkedHashMap<>();
        private int shape;  // #4951: counts the containers added and removed, so a browse can tell the channel changed

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
            shape++;
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
        private final int ccsid;  // a CHAR container's CCSID (the first PUT's, else the region's); 0 for BIT

        private Container(byte[] data, boolean bit) {
            this(data, bit, bit ? 0 : REGION_CCSID);
        }

        private Container(byte[] data, boolean bit, int ccsid) {
            this.data = data;
            this.bit = bit;
            this.ccsid = ccsid;
        }
    }

    // #4270 (X17): the CCSIDs a CHAR container converts between -- the region's 037, 500 and 1140 (single-byte EBCDIC pages
    // that keep a container's length) and 1208 (UTF-8) for ASCII data, one byte a character. The bytes a program holds in its
    // storage are read as the region's page (the port's convention, #4528): an area's byte is the character the region's
    // page gives the byte it encodes to, and a conversion is the character-to-character map between the two pages, applied
    // to the storage's bytes (a 1208 byte is the ASCII character itself, kept in storage as the region's page decodes it). A
    // character the target page lacks (037 / 500 <-> 1140: the currency sign and the euro) is CCSIDERR RESP2 4 ("replaced by
    // a blank"), which IBM does not say what FLENGTH or a PUT then do with: refused, as is a 1208 byte or character beyond
    // ASCII (a multibyte sequence changes the length).
    private static final int REGION_CCSID = 37;
    private int lastContainerCcsid;
    private Channel returnedChannel;  // #5005: the channel a RETURN CHANNEL made available (read on the root)

    private static java.nio.charset.Charset ccsidCharset(int ccsid, String what) {
        switch (ccsid) {
            case 37:
                return java.nio.charset.Charset.forName("Cp037");
            case 500:
                return java.nio.charset.Charset.forName("Cp500");
            case 1140:
                return java.nio.charset.Charset.forName("Cp1140");
            case 1208:
                return java.nio.charset.StandardCharsets.UTF_8;
            default:
                throw refused(what + "(" + ccsid + "): only the CCSIDs 37, 500, 1140 and 1208 are modelled (CCSIDERR RESP2 1 / "
                        + "2 for another)");
        }
    }

    /** `data` (storage bytes holding CCSID `from` data) as CCSID `to` data; the same bytes when the CCSIDs are equal. */
    static byte[] convertContainer(byte[] data, int from, int to, String what) {
        java.nio.charset.Charset f = ccsidCharset(from, what);
        java.nio.charset.Charset t = ccsidCharset(to, what);
        if (from == to) {
            return data;
        }
        java.nio.charset.Charset region = ccsidCharset(REGION_CCSID, what);
        byte[] out = new byte[data.length];
        for (int i = 0; i < data.length; i++) {
            byte real = String.valueOf((char) (data[i] & 0xFF)).getBytes(region)[0];
            if (from == 1208 && real < 0) {
                throw refused(what + " code-page conversion of a CCSID 1208 byte beyond ASCII (a multibyte character)");
            }
            String c = new String(new byte[] {real}, f);
            if ((to == 1208 && c.charAt(0) >= 0x80) || !t.newEncoder().canEncode(c)) {
                throw refused(what + (to == 1208 ? " code-page conversion to CCSID 1208 of a character beyond ASCII (a multibyte "
                        + "sequence)" : " code-page conversion of a character the target CCSID lacks (CCSIDERR RESP2 4: IBM "
                        + "does not say what the command then stores or sets)"));
            }
            out[i] = (byte) new String(c.getBytes(t), region).charAt(0);
        }
        return out;
    }

    /** The CCSID of the container the last GET CONTAINER read (0: a BIT container): GET CONTAINER CCSID(area). */
    public int containerCcsid() {
        return lastContainerCcsid;
    }

    /** A container command's outcome: its condition and RESP2, the container's length (GET: FLENGTH's value on
     *  NORMAL / LENGERR, else -1) and the bytes it moves INTO (GET, else null). #4951: STARTBROWSE's token comes
     *  back as the length, GETNEXT's container name as `name`. */
    public record ContainerResult(String resp, int resp2, int length, byte[] data, String name) {
        public ContainerResult(String resp, int resp2, int length, byte[] data) {
            this(resp, resp2, length, data, null);
        }

        public boolean normal() {
            return "NORMAL".equals(resp);
        }
    }

    // #4950: the characters IBM's PUT CONTAINER page allows in a CONTAINER / CHANNEL name ("The acceptable characters are
    // A-Z a-z 0-9 $ @ # / % ? ! : | " = , ; > . - and _. Leading and embedded blank characters are not permitted").
    // RUN TRANSID's page (CHANNEL_CHARS) lists three more -- & < and the not sign -- which this one omits: a name
    // holding one is refused (the two pages disagree), never accepted or called illegal
    private static final String NAME_CHARS =
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789$@#/%?!:|\\"=,;>.-_";
    private static final String NAME_CHARS_RUN_ONLY = "&<\\u00ac";

    /** A channel or container name as CICS compares it: the 16-character value without its trailing blanks. One
     *  with nothing else, or longer than 16, or holding & < or the not sign, is refused; one with a character outside
     *  IBM's set (a leading or embedded blank included) is refused here too, except by PUT CONTAINER (illegalName),
     *  the one command whose page says what it does (CHANNELERR RESP2 1 / CONTAINERERR RESP2 18). */
    private static String channelName(String name, String what) {
        String n = trimmedName(name, what);
        if (illegalName(name, what)) {
            throw new UnsupportedOperationException(what + " name '" + name + "': not modelled");
        }
        return n;
    }

    private static String trimmedName(String name, String what) {
        String n = name == null ? "" : name;
        int end = n.length();
        while (end > 0 && (n.charAt(end - 1) == ' ' || n.charAt(end - 1) == 0)) {
            end--;
        }
        n = n.substring(0, end);
        if (n.isEmpty() || n.length() > 16) {
            throw new UnsupportedOperationException(what + " name '" + name + "': not modelled");
        }
        return n;
    }

    /** True when the name holds a character outside IBM's set; refuses one that holds only IBM's set and & < or the
     *  not sign (the PUT CONTAINER and RUN TRANSID pages disagree). */
    private static boolean illegalName(String name, String what) {
        String n = trimmedName(name, what);
        boolean disputed = false;
        for (int i = 0; i < n.length(); i++) {
            char ch = n.charAt(i);
            if (NAME_CHARS.indexOf(ch) >= 0) {
                continue;
            }
            if (NAME_CHARS_RUN_ONLY.indexOf(ch) >= 0) {
                disputed = true;
                continue;
            }
            return true;
        }
        if (disputed) {
            throw new UnsupportedOperationException(what + " name '" + name + "' holds & < or a not sign: IBM's RUN "
                    + "TRANSID page allows them, its PUT CONTAINER page does not");
        }
        return false;
    }

    /** IBM's MOVE CONTAINER (INVREQ RESP2 30 / 31, CHANNELERR 3) and DELETE CHANNEL (CHANNELERR 3) pages name CICS-defined
     *  read-only containers and channels and list none. A name beginning DFH may be one, so the command is refused by name
     *  rather than run as on an ordinary one (X42 / X44). */
    private static void refuseCicsDefined(String command, String... names) {
        for (String n : names) {
            if (n != null && n.stripLeading().toUpperCase(java.util.Locale.ROOT).startsWith("DFH")) {
                throw refused(command + " naming a CICS-defined (DFH...) container or channel: it may be read-only, "
                        + "and IBM lists none (INVREQ RESP2 30 / 31, CHANNELERR RESP2 3)");
            }
        }
    }

    /** PUT CONTAINER (X42): IBM's INVREQ RESP2 30 / CHANNELERR RESP2 3 name CICS-defined read-only containers and channels and
     *  list none. The pipeline containers a burned program writes back (DFHREQUEST, DFH-BODY, DFH-DATA) run as ordinary ones;
     *  any other DFH container, and any DFH channel, is refused by name. */
    private static void refuseCicsDefinedPut(String channel, String container) {
        String c = container == null ? "" : container.strip().toUpperCase(java.util.Locale.ROOT);
        boolean pipeline = c.equals("DFHREQUEST") || c.equals("DFH-BODY") || c.equals("DFH-DATA");
        boolean dfhChannel = channel != null && channel.strip().toUpperCase(java.util.Locale.ROOT).startsWith("DFH");
        if ((!pipeline && c.startsWith("DFH")) || dfhChannel) {
            throw refused("PUT CONTAINER naming a CICS-defined (DFH...) container or channel: it may be read-only, "
                    + "and IBM lists none (INVREQ RESP2 30, CHANNELERR RESP2 3)");
        }
    }

    /** LINK / XCTL / RETURN CHANNEL (#5005, X42): IBM's three pages list no read-only condition, but say CHANNEL(DFHTRANSACTION)
     *  is the transaction channel, which never goes out of scope when the link level changes. That scope is not modelled
     *  (it would run as an ordinary channel and drop out), so a channel named DFH... is refused by name, unless it is
     *  already in this program's scope (a channel the harness handed the task, e.g. DFHEP.EVENT: used as is). */
    private void refuseDfhHandedChannel(String command, String channel) {
        if (channel != null && channel.stripLeading().toUpperCase(java.util.Locale.ROOT).startsWith("DFH")
                && !channels.containsKey(channel.strip())) {
            throw refused(command + " CHANNEL naming a DFH... channel not in scope: the transaction channel "
                    + "(DFHTRANSACTION) and any other CICS-defined channel are not modelled");
        }
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
        return scopeNamed(channelName(name, "channel"), create);
    }

    /** A channel RUN / START CHANNEL named, already checked against RUN TRANSID's character set (handedChannel): one
     *  with & < or the not sign is a channel here, though the container commands refuse it (scopeChannel). */
    private Channel scopeHanded(String handed, boolean create) {
        return scopeNamed(handed, create);
    }

    private Channel scopeNamed(String n, boolean create) {
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
        return putContainer(channel, container, data, flength, type, append, -1);
    }

    /** PUT CONTAINER ... FROMCCSID(fromCcsid) / FROMCODEPAGE (`fromCcsid` the CCSID, -1: none): the data is CHAR in that
     *  CCSID ("DATATYPE(DFHVALUE(CHAR)) is implied"). A new container takes it as its CCSID; the data put on an existing CHAR
     *  container is converted to the container's ("converted (if required)"). BIT with FROMCCSID is INVREQ RESP2 34. */
    public ContainerResult putContainer(String channel, String container, byte[] data, int flength, String type,
                                        boolean append, int fromCcsid) {
        return putContainer(channel, container, data, flength, type, append, fromCcsid, false);
    }

    /** #5005 (X17): PUT CONTAINER ... PREPEND (`prepend`; IBM "6.2 and later"): "the data passed to the container is prepended
     *  to the existing data in the container". On a new container it is the data alone. BIT containers only: IBM counts a CHAR
     *  container's data in its code page, so PREPEND with CHAR, FROMCCSID or onto a CHAR container is refused. */
    public ContainerResult putContainer(String channel, String container, byte[] data, int flength, String type,
                                        boolean append, int fromCcsid, boolean prepend) {
        int[] planned = injected("PUT-CONTAINER", "-");  // #6882 (X17): a planned condition; the PUT is not performed
        if (planned != null) {
            return new ContainerResult(respName(planned[0]), planned[1], -1, null);
        }
        refuseCicsDefinedPut(channel, container);
        boolean badChannel = channel != null && illegalName(channel, "channel");
        boolean badContainer = illegalName(container, "container");
        if (badChannel || badContainer) {
            // IBM: CHANNELERR RESP2 1 (CHANNEL), CONTAINERERR RESP2 18 (CONTAINER) "contains an illegal character or
            // combination of characters"; what it raises first of two of them, or of one and another condition, is
            // not documented
            if (badChannel && badContainer) {
                throw new UnsupportedOperationException("PUT CONTAINER with an illegal CONTAINER and CHANNEL name: "
                        + "which condition IBM raises first is not documented, not modelled");
            }
            if (flength < 0) {
                throw new UnsupportedOperationException("PUT CONTAINER with an illegal name and a negative FLENGTH: "
                        + "which condition IBM raises first is not documented, not modelled");
            }
            if (badChannel) {
                return new ContainerResult("CHANNELERR", 1, -1, null);
            }
            if (channel == null ? currentChannel == null : scopeChannel(channel, false) == null) {
                throw new UnsupportedOperationException("PUT CONTAINER with an illegal CONTAINER name and "
                        + (channel == null ? "no channel" : "a channel not in scope")
                        + ": which condition IBM raises first is not documented, not modelled");
            }
            return new ContainerResult("CONTAINERERR", 18, -1, null);
        }
        Channel ch = channel == null ? currentChannel : scopeChannel(channel, true);
        String name = channelName(container, "container");
        if (ch == null && fromCcsid >= 0 && type != null) {
            throw refused("PUT CONTAINER FROMCCSID with a data type and no channel: INVREQ RESP2 1 and RESP2 2 both fit, and "
                    + "IBM ranks neither");
        }
        if (ch == null) {
            return new ContainerResult("INVREQ", fromCcsid >= 0 ? 2 : type == null ? 4 : 1, -1, null);
        }
        if (fromCcsid >= 0) {
            ccsidCharset(fromCcsid, "PUT CONTAINER FROMCCSID");
            if (flength < 0) {
                throw refused("PUT CONTAINER FROMCCSID with a negative FLENGTH: which condition IBM raises first is not "
                        + "documented");
            }
            if ("BIT".equals(type)) {
                return new ContainerResult("INVREQ", 34, -1, null);
            }
        }
        if (flength < 0) {
            return new ContainerResult("LENGERR", 1, -1, null);
        }
        Container c = ch.containers.get(name);
        if (c != null && heldSet(containerKey(ch, name))) {
            throw refused("PUT CONTAINER onto a container a GET CONTAINER SET pointer addresses: IBM does not say what the "
                    + "pointer then sees");
        }
        if (c != null && type != null && c.bit != "BIT".equals(type)) {
            throw new UnsupportedOperationException("PUT CONTAINER " + type + " on an existing container of the other "
                    + "data type: ignored or INVREQ RESP2 33 is not settled by IBM's documentation, not modelled");
        }
        if (c != null && c.bit && fromCcsid >= 0) {
            throw refused("PUT CONTAINER FROMCCSID onto an existing BIT container: IBM does not say");
        }
        boolean chars = "CHAR".equals(type) || fromCcsid >= 0;
        if (prepend && (chars || (c != null && !c.bit))) {
            throw refused("PUT CONTAINER PREPEND on a CHAR container: IBM counts a CHAR container's data in its code page");
        }
        if (c == null) {
            ch.containers.put(name, new Container(data.clone(), !chars, chars ? (fromCcsid >= 0 ? fromCcsid : REGION_CCSID) : 0));
            ch.shape++;
            return new ContainerResult("NORMAL", 0, -1, null);
        }
        byte[] put = c.bit ? data : convertContainer(data, fromCcsid >= 0 ? fromCcsid : REGION_CCSID, c.ccsid,
                "PUT CONTAINER");
        if (prepend) {
            byte[] joined = Arrays.copyOf(put, put.length + c.data.length);
            System.arraycopy(c.data, 0, joined, put.length, c.data.length);
            c.data = joined;
        } else if (append) {
            byte[] joined = Arrays.copyOf(c.data, c.data.length + put.length);
            System.arraycopy(put, 0, joined, c.data.length, put.length);
            c.data = joined;
        } else {
            c.data = put.clone();
        }
        return new ContainerResult("NORMAL", 0, -1, null);
    }

    private static String containerKey(Channel ch, String name) {
        return "CONTAINER " + ch.name + " " + name;
    }

    /** #5042 (X58): GET CONTAINER(container) [CHANNEL(channel)] SET(ptr) FLENGTH(area) (IBM, EXEC CICS GET CONTAINER
     *  (CHANNEL)): the same conditions as getContainer without INTO (no LENGERR: nothing to truncate); on NORMAL the
     *  handle of a new block holding a copy of the container's data and the result's length FLENGTH takes. IBM: "CICS
     *  maintains the data area until" the next GET CONTAINER SET of the same container in the same channel, a DELETE
     *  CONTAINER, a MOVE CONTAINER, the channel leaving scope or a DELETE CHANNEL. Refused: a PUT or MOVE onto the
     *  container while the pointer is held (IBM does not say what the pointer then sees). Handle 0: no block. */
    public SetBlock getContainerSet(String channel, String container) {
        return getContainerSet(channel, container, -1, false);
    }

    /** GET CONTAINER SET with INTOCCSID / INTOCODEPAGE (`intoCcsid`, -1: none) or CONVERTST(NOCONVERT) (`noConvert`). */
    public SetBlock getContainerSet(String channel, String container, int intoCcsid, boolean noConvert) {
        ContainerResult r = getContainer(channel, container, Integer.MAX_VALUE, intoCcsid, noConvert);
        if ("CCSIDERR".equals(r.resp())) {
            throw refused("GET CONTAINER SET INTOCCSID on a BIT container: the data is returned unconverted, and IBM does not say "
                    + "whether a block is then acquired");
        }
        if (!"NORMAL".equals(r.resp())) {
            return new SetBlock(r, 0);
        }
        Channel ch = channel == null ? currentChannel : scopeChannel(channel, false);
        return new SetBlock(r, acquireSet(containerKey(ch, channelName(container, "container")), r.data()));
    }

    /** A GET CONTAINER SET's outcome: the container result and the block's handle (0 when none was acquired). */
    public record SetBlock(ContainerResult result, long handle) {
    }

    /** GET CONTAINER(container) [CHANNEL(channel)] INTO FLENGTH | NODATA FLENGTH (IBM, EXEC CICS GET CONTAINER
     *  (CHANNEL)). `maxLength` is the most INTO takes -- FLENGTH's value, else INTO's length -- or -1 for NODATA.
     *  CHANNELERR RESP2 2 for a channel not in scope, INVREQ RESP2 4 with no CHANNEL and no current channel,
     *  CONTAINERERR RESP2 10 for a container the channel does not have. Longer data is truncated to INTO with
     *  LENGERR RESP2 11; FLENGTH "returns the length of the data in the container" (NORMAL, LENGERR). */
    public ContainerResult getContainer(String channel, String container, int maxLength) {
        return getContainer(channel, container, maxLength, -1, false);
    }

    /** GET CONTAINER ... INTOCCSID(intoCcsid) / INTOCODEPAGE (-1: none) | CONVERTST(NOCONVERT) (`noConvert`): the data as
     *  CCSID `intoCcsid` (else the region's; a CHAR container's own with NOCONVERT) -- "conversion applies only to character
     *  data". A BIT container is returned as it is when INTOCCSID names a CCSID, with CCSIDERR RESP2 3 ("The data was returned
     *  without any code page conversion"); FLENGTH is then left alone (ASSUMED: IBM does not say), and a BIT container longer than
     *  INTO is refused (LENGERR or CCSIDERR first is not documented).
     *  The container's CCSID (0: BIT) is containerCcsid(). */
    public ContainerResult getContainer(String channel, String container, int maxLength, int intoCcsid,
                                        boolean noConvert) {
        int[] planned = injected("GET-CONTAINER", "-");  // #6882 (X17): a planned condition; nothing is read
        if (planned != null) {
            return new ContainerResult(respName(planned[0]), planned[1], -1, null);
        }
        Channel ch = channel == null ? currentChannel : scopeChannel(channel, false);
        String name = channelName(container, "container");
        if (ch == null) {
            return channel == null ? new ContainerResult("INVREQ", intoCcsid >= 0 ? 2 : 4, -1, null)
                    : new ContainerResult("CHANNELERR", 2, -1, null);
        }
        Container c = ch.containers.get(name);
        if (c == null) {
            return new ContainerResult("CONTAINERERR", 10, -1, null);
        }
        lastContainerCcsid = c.bit ? 0 : c.ccsid;
        if (c.bit && intoCcsid >= 0) {
            // IBM: CCSIDERR RESP2 3, "the data was returned without any code page conversion"; FLENGTH is not stated
            if (maxLength >= 0 && c.data.length > maxLength) {
                throw refused("GET CONTAINER INTOCCSID on a BIT container longer than INTO: whether LENGERR or CCSIDERR wins "
                        + "is not documented");
            }
            return new ContainerResult("CCSIDERR", 3, -1, maxLength < 0 ? null : c.data.clone());
        }
        byte[] data = c.bit || noConvert ? c.data
                : convertContainer(c.data, c.ccsid, intoCcsid >= 0 ? intoCcsid : REGION_CCSID, "GET CONTAINER");
        if (maxLength < 0) {
            return new ContainerResult("NORMAL", 0, data.length, null);
        }
        if (data.length > maxLength) {
            return new ContainerResult("LENGERR", 11, data.length, Arrays.copyOf(data, maxLength));
        }
        return new ContainerResult("NORMAL", 0, data.length, data.clone());
    }

    /** #5005 (X17): GET CONTAINER ... INTO FLENGTH BYTEOFFSET(offset) (IBM, EXEC CICS GET CONTAINER (CHANNEL)): "The data
     *  returned begins at the offset"; "If the value specified is less than zero, zero is assumed"; "The maximum length returned is
     *  equal to the length of the data in the container minus the BYTEOFFSET value", and FLENGTH is set to "the length of the data
     *  returned". An offset "greater than, or equal to, the length of the container" is LENGERR RESP2 12 (FLENGTH and INTO left
     *  alone: ASSUMED, IBM states FLENGTH per option, not per condition). Refused: a CHAR container (IBM counts the offset in the
     *  requested code page) and an FLENGTH below the data left (LENGERR RESP2 11, and whether FLENGTH then holds the length
     *  returned or the container's is not said). On NORMAL the result's length is the length returned. */
    public ContainerResult getContainerAt(String channel, String container, int maxLength, int byteOffset) {
        int[] planned = injected("GET-CONTAINER", "-");  // #6882 (X17): as getContainer (the stub plans every GET form)
        if (planned != null) {
            return new ContainerResult(respName(planned[0]), planned[1], -1, null);
        }
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
        lastContainerCcsid = c.bit ? 0 : c.ccsid;
        if (!c.bit) {
            throw refused("GET CONTAINER BYTEOFFSET on a CHAR container: IBM counts the offset in the requested code page");
        }
        int at = Math.max(byteOffset, 0);
        if (at >= c.data.length) {
            return new ContainerResult("LENGERR", 12, -1, null);
        }
        int left = c.data.length - at;
        if (left > maxLength) {
            throw refused("GET CONTAINER BYTEOFFSET with an FLENGTH below the data left: whether FLENGTH then holds the length "
                    + "returned or the container's is not documented");
        }
        return new ContainerResult("NORMAL", 0, left, Arrays.copyOfRange(c.data, at, c.data.length));
    }

    /** DELETE CONTAINER(container) [CHANNEL(channel)] (IBM, EXEC CICS DELETE CONTAINER (CHANNEL)): CHANNELERR
     *  RESP2 2, INVREQ RESP2 4 ("issued outside the scope of a currently-active channel"), CONTAINERERR RESP2 10. IBM's
     *  INVREQ RESP2 30 (a CICS-defined read-only container) and CHANNELERR RESP2 3 (a read-only channel) list no set: a
     *  container or channel named DFH... is refused by name (X42). */
    public ContainerResult deleteContainer(String channel, String container) {
        refuseCicsDefined("DELETE CONTAINER", container, channel);
        Channel ch = channel == null ? currentChannel : scopeChannel(channel, false);
        String name = channelName(container, "container");
        if (ch == null) {
            return channel == null ? new ContainerResult("INVREQ", 4, -1, null)
                    : new ContainerResult("CHANNELERR", 2, -1, null);
        }
        if (ch.containers.remove(name) == null) {
            return new ContainerResult("CONTAINERERR", 10, -1, null);
        }
        invalidateSet(containerKey(ch, name));  // IBM: GET CONTAINER SET's data area is kept until "deleted by a DELETE CONTAINER"
        ch.shape++;
        return new ContainerResult("NORMAL", 0, -1, null);
    }

    /** DELETE CHANNEL(channel) (IBM, EXEC CICS DELETE CHANNEL): the channel and every container it holds go; a later
     *  command naming it finds no channel (CHANNELERR RESP2 2), a PUT CONTAINER makes a new empty one. CHANNELERR
     *  RESP2 2: not in the program's scope. IBM's other RESP2 values name the current channel (4), the transaction
     *  channel (5), a channel not owned by the calling program (6) and a read-only channel (3); a channel the program
     *  is passed is the current one, and is also not its own, so IBM's order among 4 / 5 / 6 decides and it gives none:
     *  the current channel is refused. A channel named DFH... may be CICS-defined and read-only (CHANNELERR RESP2 3): refused
     *  by name (X44; IBM lists no set). A browse of the deleted channel is
     *  refused at its next GETNEXT, as for any change to the channel (X42). */
    public ContainerResult deleteChannel(String channel) {
        refuseCicsDefined("DELETE CHANNEL", channel);
        Channel ch = scopeChannel(channel, false);
        if (ch == null) {
            return new ContainerResult("CHANNELERR", 2, -1, null);
        }
        if (ch == currentChannel) {
            throw refused("DELETE CHANNEL of the current channel");
        }
        invalidateSetPrefix("CONTAINER " + ch.name + " ");  // IBM: until "deleted by a DELETE CHANNEL command"
        ch.containers.clear();
        ch.shape++;
        channels.remove(ch.name);
        return new ContainerResult("NORMAL", 0, -1, null);
    }

    /** QUERY CHANNEL(channel) CONTAINERCNT(count) (IBM, EXEC CICS QUERY CHANNEL): the number of containers the channel
     *  holds, as the result's length. CHANNELERR RESP2 2: not in the program's scope (the count is then not set). */
    public ContainerResult queryChannel(String channel) {
        Channel ch = scopeChannel(channel, false);
        if (ch == null) {
            return new ContainerResult("CHANNELERR", 2, -1, null);
        }
        return new ContainerResult("NORMAL", 0, ch.containers.size(), null);
    }

    /** MOVE CONTAINER(container) AS(as) [CHANNEL(channel)] [TOCHANNEL(toChannel)] (IBM, EXEC CICS MOVE CONTAINER
     *  (CHANNEL)): the container leaves its channel and is `as` in the target channel; "If it already exists, its
     *  contents are overwritten"; the target channel, when absent, "CICS creates". No CHANNEL / TOCHANNEL: the
     *  current channel. Conditions, in this order (IBM gives none): INVREQ RESP2 4 (CHANNEL or TOCHANNEL omitted and
     *  no current channel), CHANNELERR RESP2 2 (CHANNEL not in scope), CONTAINERERR RESP2 10 (no such container). A
     *  move that raises a condition changes nothing, and creates no channel (ASSUMED). The container keeps its data
     *  type; one moved onto an existing container of the other type, or onto itself, is refused, and so is any name
     *  (container, AS, channel) beginning DFH: IBM's INVREQ RESP2 30 / 31 and CHANNELERR RESP2 3 name CICS-defined
     *  read-only containers and channels but give no list of them (X42). */
    public ContainerResult moveContainer(String channel, String container, String as, String toChannel) {
        String name = channelName(container, "container");
        String target = channelName(as, "container");
        refuseCicsDefined("MOVE CONTAINER", name, target, channel, toChannel);
        Channel from = channel == null ? currentChannel : scopeChannel(channel, false);
        Channel to = toChannel == null ? currentChannel : scopeChannel(toChannel, false);
        if ((channel == null || toChannel == null) && currentChannel == null) {
            return new ContainerResult("INVREQ", 4, -1, null);
        }
        if (from == null) {
            return new ContainerResult("CHANNELERR", 2, -1, null);
        }
        Container src = from.containers.get(name);
        if (src == null) {
            return new ContainerResult("CONTAINERERR", 10, -1, null);
        }
        Container dst = to == null ? null : to.containers.get(target);
        if (to == from && name.equals(target)) {
            throw refused("MOVE CONTAINER onto itself");
        }
        if (dst != null && dst.bit != src.bit) {
            throw refused("MOVE CONTAINER onto a container of the other data type");
        }
        if (dst != null && dst.ccsid != src.ccsid) {
            throw refused("MOVE CONTAINER onto a container of another CCSID");
        }
        if (dst != null && heldSet(containerKey(to, target))) {
            throw refused("MOVE CONTAINER onto a container a GET CONTAINER SET pointer addresses: IBM does not say what the "
                    + "pointer then sees");
        }
        if (to == null) {
            to = scopeChannel(toChannel, true);
        }
        invalidateSet(containerKey(from, name));  // IBM: until "moved by a MOVE CONTAINER command"
        if (dst == null) {
            to.containers.put(target, src);
            to.shape++;
        } else {
            dst.data = src.data;
        }
        from.containers.remove(name);
        from.shape++;
        return new ContainerResult("NORMAL", 0, -1, null);
    }

    /** STARTBROWSE CONTAINER [CHANNEL(channel)] BROWSETOKEN (IBM, EXEC CICS STARTBROWSE CONTAINER (CHANNEL)): the
     *  token comes back as the result's length. CHANNELERR RESP2 2 for a channel not in scope. IBM: "The order of
     *  returned containers is undefined": they come in the order they were created (ASSUMED). With no CHANNEL and no
     *  current channel IBM treats it as the BTS form: refused. Tokens are 1, 2, 3 ... per task (ASSUMED: IBM calls
     *  the value a token), valid for this program until its ENDBROWSE or the task's next SYNCPOINT. */
    public ContainerResult startBrowseContainer(String channel) {
        Channel ch = channel == null ? currentChannel : scopeChannel(channel, false);
        if (ch == null) {
            if (channel == null) {
                throw refused("STARTBROWSE CONTAINER with no channel (IBM treats it as the BTS form)");
            }
            return new ContainerResult("CHANNELERR", 2, -1, null);
        }
        CicsTask r = root();
        int token = ++r.browseTokens;
        r.containerBrowses.put(token, new ContainerBrowse(this, ch));
        return new ContainerResult("NORMAL", 0, token, null);
    }

    /** GETNEXT CONTAINER(name) BROWSETOKEN(token): the next container's name, as the 16-character area IBM
     *  describes. END RESP2 2 past the last (and again on a later GETNEXT: the token stays valid until ENDBROWSE);
     *  TOKENERR RESP2 3 for a token that is not a current one of this program's (never started, ended, or taken by
     *  a SYNCPOINT). A container added to or removed from the browsed channel since the start is refused: IBM does
     *  not say what the browse then returns. */
    public ContainerResult getNextContainer(int token) {
        ContainerBrowse b = root().containerBrowses.get(token);
        if (b == null || b.owner != this) {
            return new ContainerResult("TOKENERR", 3, -1, null);
        }
        if (b.channel.shape != b.shape) {
            throw refused("GETNEXT CONTAINER: the browsed channel changed during the browse");
        }
        if (b.next >= b.names.size()) {
            return new ContainerResult("END", 2, -1, null);
        }
        String n = b.names.get(b.next++);
        return new ContainerResult("NORMAL", 0, -1, null, String.format(java.util.Locale.ROOT, "%-16s", n));
    }

    /** ENDBROWSE CONTAINER BROWSETOKEN(token): TOKENERR RESP2 3 for a token that is not a current one of this
     *  program's. */
    public ContainerResult endBrowseContainer(int token) {
        ContainerBrowse b = root().containerBrowses.get(token);
        if (b == null || b.owner != this) {
            return new ContainerResult("TOKENERR", 3, -1, null);
        }
        root().containerBrowses.remove(token);
        return new ContainerResult("NORMAL", 0, -1, null);
    }

    /** One container browse: who started it, the channel, the names then (in creation order) and how far it is. */
    private static final class ContainerBrowse {
        private final CicsTask owner;
        private final Channel channel;
        private final int shape;
        private final List<String> names;
        private int next;

        private ContainerBrowse(CicsTask owner, Channel channel) {
            this.owner = owner;
            this.channel = channel;
            this.shape = channel.shape;
            this.names = new ArrayList<>(channel.containers.keySet());
        }
    }

    private final Map<Integer, ContainerBrowse> containerBrowses = new HashMap<>();  // #4951 (the root's)
    private int browseTokens;

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
        refuseDfhHandedChannel("LINK", channel);
        return link(program, null, 0, null, scopeChannel(channel, true));
    }

    /** RETURN TRANSID(transid) CHANNEL(channel) (#5005, register X17; IBM, EXEC CICS RETURN: the channel "is to be made
     *  available to the next program" as its current channel; one that does not exist is created empty). As {RESP,
     *  RESP2}: {0, 0} and the task ends, `returnedChannel` holding what the program put there; INVREQ RESP2 2 below the
     *  highest logical level -- the command then returns to the program. */
    public int[] returnChannel(String transid, String channel) {
        refuseDfhHandedChannel("RETURN", channel);
        if (level > 1) {
            event("RETURN", "level", level, "transid", transid, "channel", channelName(channel, "channel"), "resp",
                    "INVREQ", "resp2", 2);
            return new int[] {16, 2};
        }
        Channel ch = scopeChannel(channel, true);
        event("RETURN", "transid", transid, "channel", ch.name, "containers", new java.util.TreeSet<>(ch.containers.keySet()));
        root().returnedChannel = ch;
        ended = true;
        return new int[] {0, 0};
    }

    /** The channel the task's RETURN CHANNEL made available to the next task (null: it passed none). */
    public Channel returnedChannel() {
        return root().returnedChannel;
    }

    /** XCTL PROGRAM(program) CHANNEL(channel): as LINK CHANNEL, at the same level. */
    public String xctlChannel(String program, String channel) {
        refuseDfhHandedChannel("XCTL", channel);
        return xctl(program, null, null, scopeChannel(channel, true));
    }

"""
