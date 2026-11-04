#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: CicsTask's task-storage support (GETMAIN / FREEMAIN / BLL cells, split out by #5274)
#
# PURPOSE:
# The storage part of the CICS task runtime the transaction forge emits (CICS_TASK_JAVA): the #4771 (register X47) task
# blocks and their pointers (GETMAIN, FREEMAIN, SET ADDRESS OF), the #6876 (X65) LOADed programs and the #5119 (X56) BLL
# tokens. The forge splices it into CicsTask where it always sat, so the class is byte-identical.
# ==============================================================================

STORAGE_JAVA = """\
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
     *  a length above the limit (IBM's NOSTG), a LENGTH above 65520, no INITIMG (initimg -1) for a valid length: IBM gives the
     *  storage no default contents. `halfword`: the LENGTH form. */
    public long[] getmain(long length, boolean halfword, int initimg) {
        if (length < 1) {
            return new long[] {22, 1, 0};
        }
        if (initimg < 0) {
            throw refused("GETMAIN without INITIMG acquired storage");
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

    /** FREEMAIN DATA(record) (IBM, EXEC CICS FREEMAIN; #6876, X47): the block whose bytes the record views, at `base`, as
     *  freemain(handle). A record no block names (its own storage, no pointer ever addressed it) and an address inside a
     *  GETMAIN block are refused: IBM leaves what such an address holds undefined. */
    public int[] freemainData(byte[] bytes, int base) {
        long found = 0;
        for (java.util.Map.Entry<Long, Block> e : root().blocks.entrySet()) {
            Block b = e.getValue();
            if (b.bytes != bytes) {
                continue;
            }
            boolean own = b.kind == 0 || b.kind == 3;  // (an address taken of GETMAIN storage is a kind 2 block on its bytes)
            if (b.off == base && (own || found == 0)) {
                found = e.getKey();
            } else if (own) {
                throw refused("FREEMAIN DATA of an address inside a GETMAIN block");
            }
        }
        if (found == 0) {
            throw refused("FREEMAIN DATA of a record no pointer addresses");
        }
        return freemain(found);
    }

    // ---- #6876 (register X65): programs LOADed into storage, addressed by a pointer ---------------------------------
    private final java.util.Set<String> loaded = new java.util.HashSet<>();
    private static final int PROGRAM_IMAGE = 256;  // IBM states no image length: the stub's (ASSUMED, X65)

    /** LOAD PROGRAM (IBM, EXEC CICS LOAD; X65): {resp, resp2, handle, length}. PGMIDERR 1 for a program the CSD does not
     *  define (nothing is set). Else a block of PROGRAM_IMAGE bytes (kind 4: no program may read it) and its length. */
    public long[] loadProgram(String program) {
        String name = program.stripTrailing();
        if (root().programs == null || !root().programs.defined(name)) {
            return new long[] {27, 1, 0, 0};
        }
        root().loaded.add(name);
        return new long[] {0, 0, newBlock(new byte[PROGRAM_IMAGE], 4), PROGRAM_IMAGE};
    }

    /** RELEASE PROGRAM (X65): {resp, resp2}: PGMIDERR 1 undefined; NORMAL for a program this task loaded; INVREQ else. */
    public int[] releaseProgram(String program) {
        String name = program.stripTrailing();
        if (root().programs == null || !root().programs.defined(name)) {
            return new int[] {27, 1};
        }
        return root().loaded.remove(name) ? new int[] {0, 0} : new int[] {16, 0};
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
        if (b.kind == 4) {
            throw refused("SET ADDRESS OF a LOADed program's image: IBM's bytes are not modelled (X65)");
        }
        if (b.bytes.length - b.off < need) {
            if (b.kind == 2 && ownedByTaskBlock(b.bytes)) {
                growShared(b.bytes, b.off + need);  // #6839: a window advanced over GETMAIN / received storage
            } else if (b.kind == 2 || b.bound) {
                throw refused("SET ADDRESS OF a record longer than its storage");
            } else {
                b.bytes = java.util.Arrays.copyOf(b.bytes, need);
            }
        }
        b.bound = true;
        return b.bytes;
    }

    /** #6839: `bytes` is the array of a GETMAIN or received block (not a record's own storage). */
    private boolean ownedByTaskBlock(byte[] bytes) {
        for (Block o : root().blocks.values()) {
            if (o.bytes == bytes && (o.kind == 0 || o.kind == 1)) {
                return true;
            }
        }
        return false;
    }

    /** #6839 (X47): zero-extend a task block's array to `size`; every block and record index naming the old array follows. */
    private void growShared(byte[] old, int size) {
        byte[] grown = java.util.Arrays.copyOf(old, size);
        for (Block o : root().blocks.values()) {
            if (o.bytes == old) {
                o.bytes = grown;
            }
        }
        Long h = root().addressed.remove(old);
        if (h != null) {
            root().addressed.put(grown, h);
        }
        java.util.Map<Integer, Long> at = root().addressedAt.remove(old);
        if (at != null) {
            root().addressedAt.put(grown, at);
        }
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
