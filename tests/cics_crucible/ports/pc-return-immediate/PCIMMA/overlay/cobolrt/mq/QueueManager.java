package com.gitgalaxy.modernized.cobolrt.mq;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** #4892 (register W1-W8): the queue manager a CICS task's MQI calls reach -- MQOPEN, MQGET, MQPUT, MQPUT1, MQCLOSE --
 *  over the queues the case states (mq.cfg, tests/tools/equivalence_mq.py). The twin of tests/equivalence/mq/ggmq.c:
 *  the same rules, IBM's reason codes, and the same refusals (an UnsupportedOperationException "... is not modelled"
 *  where the stub exits 98). Every structure is read and written in the caller's bytes (an MQLONG big-endian, as z/OS
 *  and GnuCOBOL's BINARY hold it), so a port and the COBOL run see the same MQMD. */
public final class QueueManager {
    /** An argument: the caller's bytes from `at`. */
    public record Ref(byte[] b, int at) {
    }

    /** Where the calls are recorded: the task's event stream (CicsTask.resourceEvent). */
    public interface Sink {
        void event(String kind, Object... kv);
    }

    static final int MDLEN = 324;  // MQMD_LENGTH_1
    private static final int AVAIL = 0;
    private static final int PUT_PENDING = 1;
    private static final int GET_PENDING = 2;
    private static final int GONE = 3;
    private static final int OO_INPUT = 1 | 2 | 4;
    private static final int OO_OUTPUT = 16;
    private static final int OO_SAVE_ALL = 128;
    private static final int OO_PASS = 256 | 512;
    private static final int OO_MODELLED = OO_INPUT | OO_OUTPUT | OO_SAVE_ALL | OO_PASS | 8192;
    private static final int GMO_WAIT = 1;
    private static final int GMO_SYNC = 2;
    private static final int GMO_NOSYNC = 4;
    private static final int GMO_TRUNC = 64;
    private static final int GMO_CONVERT = 16384;
    private static final int GMO_MODELLED = GMO_WAIT | GMO_SYNC | GMO_NOSYNC | GMO_TRUNC | 8192 | GMO_CONVERT;
    private static final int PMO_SYNC = 2;
    private static final int PMO_NOSYNC = 4;
    private static final int PMO_DEFAULT = 32;
    private static final int PMO_NOCONTEXT = 16384;
    private static final int PMO_MODELLED = PMO_SYNC | PMO_NOSYNC | PMO_DEFAULT | 8192 | PMO_NOCONTEXT;
    private static final HexFormat HEX = HexFormat.of().withUpperCase();

    private static final class Msg {
        int q;
        int state;
        long seq;
        byte[] md;
        byte[] data;
    }

    private record Handle(int q, int opts, boolean[] open) {
    }

    private final List<String> qnames = new ArrayList<>();
    private final List<int[]> qdefaults = new ArrayList<>();  // {priority, persistence}
    private String qmgr = "";
    private int qmgrCcsid = 37;
    private final List<Msg> msgs = new ArrayList<>();
    private final List<Handle> handles = new ArrayList<>();
    private final List<String[]> faults = new ArrayList<>();  // {verb, nth, reason}: the calls the case plans to fail
    private final Map<String, Integer> calls = new HashMap<>();
    private long seqc;
    private long msgidc;
    private final Sink sink;
    private final String putDate;
    private final String putTime;

    /** The queue manager mq.cfg states; `putDate` / `putTime` the run's pinned clock (YYYYMMDD, HHMMSSTH, as GMT: W8). */
    public QueueManager(Path cfg, Sink sink, String putDate, String putTime) throws IOException {
        this.sink = sink;
        this.putDate = putDate;
        this.putTime = putTime;
        for (String line : Files.readAllLines(cfg, StandardCharsets.US_ASCII)) {
            String[] w = line.trim().split(" +");
            if (w[0].equals("QMGR") && w.length == 3) {
                qmgr = w[1];
                qmgrCcsid = Integer.parseInt(w[2]);
            } else if (w[0].equals("Q") && w.length == 4) {
                qnames.add(w[1]);
                qdefaults.add(new int[] {Integer.parseInt(w[2]), Integer.parseInt(w[3])});
            } else if (w[0].equals("FAULT") && w.length == 4) {
                faults.add(new String[] {w[1], w[2], w[3]});
            } else if (w[0].equals("M") && w.length == 4) {
                int q = qnames.indexOf(w[1]);
                byte[] md = HEX.parseHex(w[2]);
                if (q < 0 || md.length != MDLEN) {
                    throw refused("MQ", "a malformed mq.cfg message line");
                }
                add(q, md, w[3].equals("-") ? new byte[0] : HEX.parseHex(w[3]), AVAIL);
            }
        }
    }

    /** The reason code the case plans for this call of `verb` (the nth, counting every call of that verb), or 0. The
     *  planned call is not performed: the caller answers the reason. The twin of ggmq.c's planned(). */
    private int planned(String verb) {
        int n = calls.merge(verb, 1, Integer::sum);
        for (String[] f : faults) {
            if (f[0].equals(verb) && Integer.parseInt(f[1]) == n) {
                return Integer.parseInt(f[2]);
            }
        }
        return 0;
    }

    private static UnsupportedOperationException refused(String call, String what) {
        return new UnsupportedOperationException(call + ": " + what + " is not modelled");
    }

    static int be32(Ref r, int off) {
        byte[] b = r.b();
        int p = r.at() + off;
        return (b[p] & 0xFF) << 24 | (b[p + 1] & 0xFF) << 16 | (b[p + 2] & 0xFF) << 8 | (b[p + 3] & 0xFF);
    }

    static void put32(Ref r, int off, int v) {
        byte[] b = r.b();
        int p = r.at() + off;
        b[p] = (byte) (v >>> 24);
        b[p + 1] = (byte) (v >>> 16);
        b[p + 2] = (byte) (v >>> 8);
        b[p + 3] = (byte) v;
    }

    private static boolean bytesAre(Ref r, int off, String ascii) {
        byte[] want = ascii.getBytes(StandardCharsets.US_ASCII);
        return Arrays.equals(r.b(), r.at() + off, r.at() + off + want.length, want, 0, want.length);
    }

    /** `len` bytes from the caller's bytes; a BufferLength past the end of the field reads zeros there (the Java
     *  runtime cannot see the storage that follows the field), the same bytes in the stored message and the event. */
    private static byte[] bytesAt(Ref r, int len) {
        byte[] out = new byte[len];
        System.arraycopy(r.b(), r.at(), out, 0, Math.max(0, Math.min(len, r.b().length - r.at())));
        return out;
    }

    private static boolean zero(Ref r, int off, int n) {
        for (int i = 0; i < n; i++) {
            if (r.b()[r.at() + off + i] != 0) {
                return false;
            }
        }
        return true;
    }

    private static void fill(Ref r, int off, int n, int v) {
        Arrays.fill(r.b(), r.at() + off, r.at() + off + n, (byte) v);
    }

    private static void pad(Ref r, int off, String s, int n) {
        fill(r, off, n, ' ');
        byte[] v = s.getBytes(StandardCharsets.ISO_8859_1);
        System.arraycopy(v, 0, r.b(), r.at() + off, Math.min(v.length, n));
    }

    /** an MQCHAR48 name: trailing blanks and nulls dropped */
    private static String name48(Ref r, int off) {
        int n = 48;
        while (n > 0 && (r.b()[r.at() + off + n - 1] == ' ' || r.b()[r.at() + off + n - 1] == 0)) {
            n--;
        }
        return new String(r.b(), r.at() + off, n, StandardCharsets.ISO_8859_1);
    }

    private Msg add(int q, byte[] md, byte[] data, int state) {
        Msg m = new Msg();
        m.q = q;
        m.state = state;
        m.seq = ++seqc;
        m.md = md;
        m.data = data;
        msgs.add(m);
        return m;
    }

    private static int mdInt(byte[] md, int off) {
        return be32(new Ref(md, 0), off);
    }

    /** The unit of work ends (W5): SYNCPOINT (false); SYNCPOINT ROLLBACK, or the backout of an abend (true). */
    // [rule RT-MQ-UNIT-OF-WORK]
    public void uowEnd(boolean rollback) {
        for (Msg m : msgs) {
            if (m.state == PUT_PENDING) {
                m.state = rollback ? GONE : AVAIL;
            } else if (m.state == GET_PENDING) {
                if (rollback) {
                    m.state = AVAIL;  // IBM MQMD BackoutCount: returned under a unit of work, and backed out
                    put32(new Ref(m.md, 0), 96, mdInt(m.md, 96) + 1);
                } else {
                    m.state = GONE;
                }
            }
        }
    }

    /** delivery order: priority, then first in first out (MSGDLVSQ(PRIORITY), W3) */
    private static boolean before(Msg a, Msg b) {
        int pa = mdInt(a.md, 40);
        int pb = mdInt(b.md, 40);
        return pa != pb ? pa > pb : a.seq < b.seq;
    }

    /** The task ends normally: its unit of work is committed, and the queues it leaves -- each queue's messages in
     *  delivery order, "MQMD-hex data-hex" (data "-" when empty) -- as the stub's mq.out. */
    public Map<String, List<String>> end() {
        uowEnd(false);
        Map<String, List<String>> out = new LinkedHashMap<>();
        for (int q = 0; q < qnames.size(); q++) {
            List<Msg> on = new ArrayList<>();
            for (Msg m : msgs) {
                if (m.q == q && m.state == AVAIL) {
                    on.add(m);
                }
            }
            on.sort((a, b) -> before(a, b) ? -1 : before(b, a) ? 1 : 0);
            List<String> lines = new ArrayList<>();
            for (Msg m : on) {
                lines.add(HEX.formatHex(m.md) + " " + (m.data.length == 0 ? "-" : HEX.formatHex(m.data)));
            }
            out.put(qnames.get(q), lines);
        }
        return out;
    }

    // [rule RT-MQ-CONNECTION]
    private static void hconnOk(String call, Ref hconn) {
        if (be32(hconn, 0) != 0) {  // MQHC_DEF_HCONN: CICS needs no MQCONN, W6
            throw refused(call, "an Hconn other than MQHC_DEF_HCONN (0) (MQCONN)");
        }
    }

    /** IBM: MQCC_WARNING for the two truncation reasons modelled, MQCC_FAILED for every other reason */
    private static int comp(int r) {
        return r == 0 ? 0 : (r == 2079 || r == 2080) ? 1 : 2;
    }

    private static void done(Ref cc, Ref rc, int r) {
        put32(cc, 0, comp(r));
        put32(rc, 0, r);
    }

    private String qname(int q) {
        return q >= 0 ? qnames.get(q) : "";
    }

    private int handle(Ref hobj) {
        int h = be32(hobj, 0);
        return h >= 1 && h <= handles.size() && handles.get(h - 1).open()[0] ? h - 1 : -1;
    }

    /** MQOD checks shared by MQOPEN and MQPUT1: the queue's index, or -1 (MQRC_UNKNOWN_OBJECT_NAME) */
    private int resolveOd(String call, Ref od, String[] name) {
        if (!bytesAre(od, 0, "OD  ")) {
            throw refused(call, "an MQOD whose StrucId is not 'OD  ' (MQRC_OD_ERROR)");
        }
        if (be32(od, 4) != 1) {
            throw refused(call, "an MQOD version other than 1");
        }
        if (be32(od, 8) != 1) {
            throw refused(call, "an ObjectType other than MQOT_Q");
        }
        name[0] = name48(od, 12);
        String qm = name48(od, 60);
        if (!qm.isEmpty() && !qm.equals(qmgr)) {
            throw refused(call, "a queue on another queue manager (ObjectQMgrName)");
        }
        return qnames.indexOf(name[0]);
    }

    /** MQOPEN (Hconn, ObjDesc, Options, Hobj, CompCode, Reason) */
    // [rule RT-MQ-OPEN]
    public void mqopen(Ref hconn, Ref od, Ref options, Ref hobj, Ref cc, Ref rc) {
        hconnOk("MQOPEN", hconn);
        int o = be32(options, 0);
        int fr = planned("MQOPEN");
        if (fr != 0) {
            done(cc, rc, fr);
            sink.event("MQOPEN", "queue", name48(od, 12), "cc", comp(fr), "rc", fr, "options", o, "hobj", 0);
            return;
        }
        if ((o & ~OO_MODELLED) != 0) {
            throw refused("MQOPEN", "an option other than INPUT-*, OUTPUT, SAVE-ALL-CONTEXT, PASS-*-CONTEXT, "
                    + "FAIL-IF-QUIESCING");
        }
        String[] name = new String[1];
        int q = resolveOd("MQOPEN", od, name);
        int inputs = ((o & 1) != 0 ? 1 : 0) + ((o & 2) != 0 ? 1 : 0) + ((o & 4) != 0 ? 1 : 0);
        int r = 0;
        // IBM MQOPEN Options: one MQOO_INPUT_* at most; an input or output option here; SAVE_ALL_CONTEXT needs an
        // input option, PASS_*_CONTEXT needs MQOO_OUTPUT (MQRC_OPTIONS_ERROR 2046)
        if (inputs > 1 || (inputs == 0 && (o & OO_OUTPUT) == 0) || ((o & OO_SAVE_ALL) != 0 && inputs == 0)
                || ((o & OO_PASS) != 0 && (o & OO_OUTPUT) == 0)) {
            r = 2046;
        } else if (q < 0) {
            r = 2085;  // MQRC_UNKNOWN_OBJECT_NAME
        }
        if (r == 0 && inputs > 0) {
            for (Handle h : handles) {
                if (h.open()[0] && h.q() == q && ((h.opts() | o) & 4) != 0 && (h.opts() & OO_INPUT) != 0) {
                    throw refused("MQOPEN", "a queue opened for input twice with MQOO_INPUT_EXCLUSIVE "
                            + "(MQRC_OBJECT_IN_USE)");
                }
            }
        }
        if (r == 0) {
            if (handles.size() == 64) {
                throw refused("MQOPEN", "more than 64 object handles in a task");
            }
            handles.add(new Handle(q, o, new boolean[] {true}));
            put32(hobj, 0, handles.size());  // W4: handles are 1, 2, 3 ... in the order opened
        }
        done(cc, rc, r);
        sink.event("MQOPEN", "queue", name[0], "cc", comp(r), "rc", r, "options", o, "hobj", r != 0 ? 0 : handles.size());
    }

    /** MQCLOSE (Hconn, Hobj, Options, CompCode, Reason) */
    // [rule RT-MQ-CLOSE]
    public void mqclose(Ref hconn, Ref hobj, Ref options, Ref cc, Ref rc) {
        hconnOk("MQCLOSE", hconn);
        int fr = planned("MQCLOSE");
        if (fr != 0) {
            int fh = handle(hobj);
            done(cc, rc, fr);
            sink.event("MQCLOSE", "queue", qname(fh >= 0 ? handles.get(fh).q() : -1), "cc", comp(fr), "rc", fr);
            return;
        }
        if (be32(options, 0) != 0) {
            throw refused("MQCLOSE", "an option other than MQCO_NONE");
        }
        int h = handle(hobj);
        int q = h >= 0 ? handles.get(h).q() : -1;
        int r = h < 0 ? 2019 : 0;  // MQRC_HOBJ_ERROR
        if (h >= 0) {
            handles.get(h).open()[0] = false;
            put32(hobj, 0, -1);  // MQHO_UNUSABLE_HOBJ
        }
        done(cc, rc, r);
        sink.event("MQCLOSE", "queue", qname(q), "cc", comp(r), "rc", r);
    }

    /** MQGET (Hconn, Hobj, MsgDesc, GetMsgOpts, BufferLength, Buffer, DataLength, CompCode, Reason) */
    // [rule RT-MQ-GET]
    public void mqget(Ref hconn, Ref hobj, Ref md, Ref gmo, Ref buflen, Ref buffer, Ref datalen, Ref cc, Ref rc) {
        hconnOk("MQGET", hconn);
        int fr = planned("MQGET");
        if (fr != 0) {
            int fh = handle(hobj);
            done(cc, rc, fr);
            sink.event("MQGET", "queue", qname(fh >= 0 ? handles.get(fh).q() : -1), "cc", comp(fr), "rc", fr, "len", -1,
                    "data", "");
            return;
        }
        if (!bytesAre(md, 0, "MD  ") || be32(md, 4) != 1) {
            throw refused("MQGET", "an MQMD other than version 1");
        }
        if (!bytesAre(gmo, 0, "GMO ") || be32(gmo, 4) != 1) {
            throw refused("MQGET", "an MQGMO other than version 1");
        }
        int o = be32(gmo, 8);
        int h = handle(hobj);
        int q = h >= 0 ? handles.get(h).q() : -1;
        int bl = be32(buflen, 0);
        int r = 0;
        if ((o & ~GMO_MODELLED) != 0) {
            throw refused("MQGET", "an option other than WAIT, SYNCPOINT, NO-SYNCPOINT, ACCEPT-TRUNCATED-MSG, "
                    + "FAIL-IF-QUIESCING, CONVERT");
        }
        Msg m = null;
        if (h < 0) {
            r = 2019;  // MQRC_HOBJ_ERROR
        } else if ((handles.get(h).opts() & OO_INPUT) == 0) {
            r = 2037;  // MQRC_NOT_OPEN_FOR_INPUT
        } else if ((o & GMO_SYNC) != 0 && (o & GMO_NOSYNC) != 0) {
            r = 2046;  // MQRC_OPTIONS_ERROR
        } else if (bl < 0) {
            r = 2005;  // MQRC_BUFFER_LENGTH_ERROR
        } else {
            // a version-1 MQGMO matches on the MQMD's MsgId and CorrelId (IBM MQGMO MatchOptions)
            if (!zero(md, 48, 24) || !zero(md, 72, 24)) {
                throw refused("MQGET", "a get matching a MsgId or CorrelId (MQMI_NONE / MQCI_NONE expected)");
            }
            for (Msg x : msgs) {
                if (x.q == q && x.state == AVAIL && (m == null || before(x, m))) {
                    m = x;
                }
            }
            if (m == null) {
                if ((o & GMO_WAIT) != 0 && be32(gmo, 12) == -1) {
                    throw refused("MQGET", "MQWI_UNLIMITED on a queue no producer fills (W2)");
                }
                if ((o & GMO_WAIT) != 0 && be32(gmo, 12) < -1) {
                    throw refused("MQGET", "a negative WaitInterval (MQRC_WAIT_INTERVAL_ERROR)");
                }
                r = 2033;  // MQRC_NO_MSG_AVAILABLE: no other producer during the task, so a wait ends empty (W2)
            }
        }
        int copied = 0;
        if (m != null) {
            if ((o & GMO_CONVERT) != 0) {  // MQGMO_CONVERT: a no-op where the message already is as asked (W7)
                int want = be32(md, 28);
                if ((want != 0 ? want : qmgrCcsid) != mdInt(m.md, 28) || be32(md, 24) != mdInt(m.md, 24)) {
                    throw refused("MQGET", "MQGMO_CONVERT to another CCSID or encoding");
                }
            }
            copied = Math.min(m.data.length, bl);
            System.arraycopy(m.md, 0, md.b(), md.at(), MDLEN);
            System.arraycopy(m.data, 0, buffer.b(), buffer.at(), copied);
            put32(datalen, 0, m.data.length);
            pad(gmo, 24, qnames.get(q), 48);  // ResolvedQName
            if (m.data.length > bl && (o & GMO_TRUNC) == 0) {
                r = 2080;  // MQRC_TRUNCATED_MSG_FAILED: the message stays on the queue
            } else {
                r = m.data.length > bl ? 2079 : 0;  // MQRC_TRUNCATED_MSG_ACCEPTED
                // on z/OS a get with neither SYNCPOINT option is in the unit of work (IBM MQGMO_SYNCPOINT)
                m.state = (o & GMO_NOSYNC) != 0 ? GONE : GET_PENDING;
            }
        }
        done(cc, rc, r);
        sink.event("MQGET", "queue", qname(q), "cc", comp(r), "rc", r, "len", m != null ? m.data.length : -1,
                "data", HEX.formatHex(buffer.b(), buffer.at(), buffer.at() + copied));
    }

    /** the put both MQPUT and MQPUT1 make: the reason code, the message stored */
    private int put(String call, int q, Ref md, Ref pmo, Ref buflen, Ref buffer) {
        if (!bytesAre(md, 0, "MD  ") || be32(md, 4) != 1) {
            throw refused(call, "an MQMD other than version 1");
        }
        if (!bytesAre(pmo, 0, "PMO ") || be32(pmo, 4) != 1) {
            throw refused(call, "an MQPMO other than version 1");
        }
        int o = be32(pmo, 8);
        int bl = be32(buflen, 0);
        if ((o & ~PMO_MODELLED) != 0) {
            throw refused(call, "an option other than SYNCPOINT, NO-SYNCPOINT, DEFAULT-CONTEXT, NO-CONTEXT, "
                    + "FAIL-IF-QUIESCING");
        }
        if ((o & PMO_SYNC) != 0 && (o & PMO_NOSYNC) != 0) {
            return 2046;
        }
        if ((o & PMO_DEFAULT) != 0 && (o & PMO_NOCONTEXT) != 0) {
            return 2046;
        }
        if (bl < 0) {
            return 2005;
        }
        if (be32(md, 8) != 0) {
            throw refused(call, "Report options (MQRO_*)");
        }
        int pri = be32(md, 40);
        int per = be32(md, 44);
        if (pri < -1 || pri > 9) {
            throw refused(call, "a Priority outside -1..9 (MQRC_PRIORITY_ERROR)");
        }
        if (per < 0 || per > 2) {
            throw refused(call, "a Persistence other than 0, 1, 2 (MQRC_PERSISTENCE_ERROR)");
        }
        if (zero(md, 48, 24)) {  // MQMI_NONE: the queue manager makes a unique MsgId (W4)
            byte[] id = String.format("GGMQ%020d", ++msgidc).getBytes(StandardCharsets.US_ASCII);
            System.arraycopy(id, 0, md.b(), md.at() + 48, 24);
        }
        if ((o & PMO_NOCONTEXT) != 0) {  // IBM MQPMO_NO_CONTEXT: both kinds of context are blank
            fill(md, 196, 12, ' ');
            fill(md, 208, 32, 0);
            fill(md, 240, 32, ' ');
            put32(md, 272, 0);  // MQAT_NO_CONTEXT
            fill(md, 276, 28 + 8 + 8 + 4, ' ');
        } else {  // MQPMO_DEFAULT_CONTEXT (also when no context option is given) -- returned in the MQMD (W8)
            fill(md, 196, 12, ' ');  // UserIdentifier: the placeholder, W8
            fill(md, 208, 32, 0);  // AccountingToken: the placeholder, W8
            fill(md, 240, 32, ' ');  // ApplIdentityData: blank
            put32(md, 272, 1);  // PutApplType MQAT_CICS
            fill(md, 276, 28, ' ');  // PutApplName: the placeholder, W8
            pad(md, 304, putDate, 8);
            pad(md, 312, putTime, 8);
            fill(md, 320, 4, ' ');  // ApplOriginData: blank
        }
        byte[] stored = Arrays.copyOfRange(md.b(), md.at(), md.at() + MDLEN);
        Ref s = new Ref(stored, 0);
        if (pri == -1) {
            put32(s, 40, qdefaults.get(q)[0]);  // MQPRI_PRIORITY_AS_Q_DEF
        }
        if (per == 2) {
            put32(s, 44, qdefaults.get(q)[1]);  // MQPER_PERSISTENCE_AS_Q_DEF
        }
        if (be32(md, 28) == 0) {
            put32(s, 28, qmgrCcsid);  // MQCCSI_Q_MGR
        }
        put32(s, 96, 0);  // BackoutCount
        add(q, stored, bytesAt(buffer, bl),
                (o & PMO_NOSYNC) != 0 ? AVAIL : PUT_PENDING);  // z/OS: in the unit of work by default
        pad(pmo, 32, qnames.get(q), 48);  // ResolvedQName, ResolvedQMgrName
        pad(pmo, 80, qmgr, 48);
        return 0;
    }

    private void putEvent(String call, String queue, int r, Ref md, Ref buffer, int bl) {
        sink.event(call, "queue", queue, "cc", comp(r), "rc", r,
                "msgid", r != 0 ? "-" : HEX.formatHex(md.b(), md.at() + 48, md.at() + 72),
                "data", r != 0 ? "" : HEX.formatHex(bytesAt(buffer, Math.max(bl, 0))));
    }

    /** MQPUT (Hconn, Hobj, MsgDesc, PutMsgOpts, BufferLength, Buffer, CompCode, Reason) */
    // [rule RT-MQ-PUT]
    public void mqput(Ref hconn, Ref hobj, Ref md, Ref pmo, Ref buflen, Ref buffer, Ref cc, Ref rc) {
        hconnOk("MQPUT", hconn);
        int fr = planned("MQPUT");
        if (fr != 0) {
            int fh = handle(hobj);
            done(cc, rc, fr);
            putEvent("MQPUT", qname(fh >= 0 ? handles.get(fh).q() : -1), fr, md, buffer, be32(buflen, 0));
            return;
        }
        int h = handle(hobj);
        int q = h >= 0 ? handles.get(h).q() : -1;
        int r;
        if (h < 0) {
            r = 2019;  // MQRC_HOBJ_ERROR
        } else if ((handles.get(h).opts() & OO_OUTPUT) == 0) {
            r = 2039;  // MQRC_NOT_OPEN_FOR_OUTPUT
        } else {
            r = put("MQPUT", q, md, pmo, buflen, buffer);
        }
        done(cc, rc, r);
        putEvent("MQPUT", qname(q), r, md, buffer, be32(buflen, 0));
    }

    /** MQPUT1 (Hconn, ObjDesc, MsgDesc, PutMsgOpts, BufferLength, Buffer, CompCode, Reason): open, put, close */
    public void mqput1(Ref hconn, Ref od, Ref md, Ref pmo, Ref buflen, Ref buffer, Ref cc, Ref rc) {
        hconnOk("MQPUT1", hconn);
        int fr = planned("MQPUT1");
        if (fr != 0) {
            done(cc, rc, fr);
            putEvent("MQPUT1", name48(od, 12), fr, md, buffer, be32(buflen, 0));
            return;
        }
        String[] name = new String[1];
        int q = resolveOd("MQPUT1", od, name);
        int r = q < 0 ? 2085 : put("MQPUT1", q, md, pmo, buflen, buffer);
        done(cc, rc, r);
        putEvent("MQPUT1", name[0], r, md, buffer, be32(buflen, 0));
    }
}
