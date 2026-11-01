package com.gitgalaxy.modernized.cobolrt;

import java.nio.charset.Charset;
import java.util.ArrayList;
import java.util.List;

/**
 * #5856 (register A2): the z/OS control blocks a batch program walks to read its own job, step and DD names (CardDemo
 * CBSTM03A: PSA -> TCB -> TIOT), as a stand-in built from the job step the run states -- never from a guess. IBM, z/OS
 * MVS Data Areas: the PSA is at address 0, PSATNEW (X'218') holds the TCB's address, TCBTIO (TCB + X'0C') the TIOT's;
 * the TIOT is a 24-byte header (TIOCNJOB, TIOCSTPN, TIOCJSTP: job, step, procedure step) and one 20-byte DD entry per
 * DD (TIOELNGH 20, TIOEDDNM at +4, TIOEFSRT the UCB address at +17), ended by a fullword of zeros.
 *
 * <p>The step is the system property {@code gitgalaxy.mvs.step}: {@code TIOCNJOB;TIOCSTPN;TIOCJSTP;DD:UCB,DD:NOUCB,...}:
 * the header's three names in IBM's order, as the run states them, then the DDs in the JCL's order (UCB for a DD on a
 * device, NOUCB for SYSOUT / DUMMY / in-stream). A pointer holds a handle, as in the
 * CICS lane (X47): block in the high word, offset in the low one, block 0 the PSA, so a NULL pointer is the PSA's
 * address -- what IBM's address 0 is. Only the bytes the walk reads are laid: the PSA up to PSATNEW, the TCB up to
 * TCBTIO; a record longer than what follows its address in its block is refused, so no other PSA / TCB field is read.
 */
public final class DetMvs {
    /** PSATNEW, the TCB pointer in the PSA (X'218'). */
    static final int PSATNEW = 0x218;

    /** TCBTIO, the TIOT pointer in the TCB (X'0C'). */
    static final int TCBTIO = 0x0C;

    /** The TIOT header: TIOCNJOB, TIOCSTPN, TIOCJSTP. */
    static final int TIOT_HEADER = 24;

    /** One single-unit DD entry (TIOELNGH). */
    static final int TIOT_ENTRY = 20;

    /** A POINTER's bytes in a port (GnuCOBOL's on x86-64, register C9). */
    static final int POINTER = 8;

    private static List<byte[]> blocks;

    private DetMvs() {
    }

    /** SET ADDRESS OF record TO ptr: the record's bytes are the control block's from the handle's offset on. */
    // [rule RT-MVS-CONTROL-BLOCKS]
    public static void setAddress(Field record, Field ptr, Charset cs) {
        if (record.offset() != record.storage().base) {
            throw new UnsupportedOperationException("SET ADDRESS OF an item that is not a whole 01 record: not modelled");
        }
        long handle = pointerValue(ptr);
        byte[] block = block(handle, cs);
        int at = (int) handle;
        if (at < 0 || block.length - at < record.length()) {
            throw new UnsupportedOperationException("SET ADDRESS OF " + record.length() + " bytes at offset " + at
                + " of a " + block.length + "-byte control block: past the fields the stand-in lays (register A2)");
        }
        record.storage().bytes = block;
        record.storage().base = at;
    }

    /** `ADD n TO view` / `COMPUTE view = view + n` over a numeric item a POINTER shares bytes with: the pointer addresses
     *  the same control block n bytes further on (or back). Refused: a result outside the block. */
    public static void advancePointer(Field ptr, long n, Charset cs) {
        long handle = pointerValue(ptr);
        byte[] block = block(handle, cs);
        long at = (int) handle + n;
        if (at < 0 || at > block.length) {
            throw new UnsupportedOperationException(
                "pointer arithmetic leaves the control block the pointer addresses (" + at + " of " + block.length + " bytes)");
        }
        setPointer(ptr, (handle & 0xFFFFFFFF00000000L) | at);
    }

    /** `MOVE view TO view`: the address is copied, as the handle is. */
    public static void copyPointer(Field to, Field from) {
        setPointer(to, pointerValue(from));
    }

    private static byte[] block(long handle, Charset cs) {
        List<byte[]> b = blocks(cs);
        long n = handle >>> 32;
        if (n >= b.size()) {
            throw new UnsupportedOperationException("a pointer to no z/OS control block the stand-in lays (register A2)");
        }
        return b.get((int) n);
    }

    private static synchronized List<byte[]> blocks(Charset cs) {
        if (blocks == null) {
            blocks = build(System.getProperty("gitgalaxy.mvs.step", ""), cs);
        }
        return blocks;
    }

    /** The PSA, TCB and TIOT of the stated step: blocks 0, 1 and 2. */
    static List<byte[]> build(String step, Charset cs) {
        String[] f = step.split(";", -1);
        if (step.isEmpty() || f.length != 4) {
            throw new UnsupportedOperationException(
                "z/OS control blocks (PSA / TCB / TIOT): no job step stated (gitgalaxy.mvs.step; register A2)");
        }
        String[] dds = f[3].isEmpty() ? new String[0] : f[3].split(",");
        byte[] psa = new byte[PSATNEW + POINTER];
        byte[] tcb = new byte[TCBTIO + POINTER];
        byte[] tiot = new byte[TIOT_HEADER + TIOT_ENTRY * dds.length + 4];
        put(psa, PSATNEW, 1L << 32);
        put(tcb, TCBTIO, 2L << 32);
        name(tiot, 0, f[0], cs);
        name(tiot, 8, f[1], cs);
        name(tiot, 16, f[2], cs);
        for (int i = 0; i < dds.length; i++) {
            String[] dd = dds[i].split(":", -1);
            if (dd.length != 2 || !(dd[1].equals("UCB") || dd[1].equals("NOUCB"))) {
                throw new UnsupportedOperationException("gitgalaxy.mvs.step: a DD is NAME:UCB or NAME:NOUCB, not " + dds[i]);
            }
            int e = TIOT_HEADER + TIOT_ENTRY * i;
            tiot[e] = TIOT_ENTRY;
            name(tiot, e + 4, dd[0], cs);
            if (dd[1].equals("UCB")) {  // a token, not an address: only "not zero" is stated
                int token = i + 1;
                tiot[e + 17] = (byte) (token >>> 16);
                tiot[e + 18] = (byte) (token >>> 8);
                tiot[e + 19] = (byte) token;
            }
        }
        List<byte[]> out = new ArrayList<>();
        out.add(psa);
        out.add(tcb);
        out.add(tiot);
        return out;
    }

    private static void name(byte[] b, int at, String s, Charset cs) {
        if (s.length() > 8) {
            throw new UnsupportedOperationException("gitgalaxy.mvs.step: a name longer than 8 characters: " + s);
        }
        byte[] t = String.format("%-8s", s).getBytes(cs);
        System.arraycopy(t, 0, b, at, 8);
    }

    private static void put(byte[] b, int at, long handle) {
        for (int i = POINTER - 1; i >= 0; i--) {
            b[at + i] = (byte) handle;
            handle >>>= 8;
        }
    }

    private static long pointerValue(Field ptr) {
        long h = 0;
        for (int i = 0; i < POINTER; i++) {
            h = (h << 8) | (ptr.storage().bytes[ptr.offset() + i] & 0xFF);
        }
        return h;
    }

    private static void setPointer(Field ptr, long handle) {
        for (int i = POINTER - 1; i >= 0; i--) {
            ptr.storage().bytes[ptr.offset() + i] = (byte) handle;
            handle >>>= 8;
        }
    }
}
