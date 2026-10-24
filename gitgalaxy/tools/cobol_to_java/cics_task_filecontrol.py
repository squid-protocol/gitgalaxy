#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: CicsTask's file control (#4023, #4213, split out by #5274)
#
# PURPOSE:
# The file-control family of the CICS task runtime the transaction forge emits
# (CICS_TASK_JAVA): READ / READ UPDATE / GTEQ / GENERIC, WRITE, REWRITE, DELETE,
# UNLOCK, and the browse (STARTBR / READNEXT / READPREV / RESETBR / ENDBR, keyed
# and by RBA of an ESDS). The forge splices FILECONTROL_JAVA into CicsTask at the
# place it always sat, so the class is byte-identical.
# ==============================================================================

FILECONTROL_JAVA = """\
    /** READ FILE(file) (#4023 follow-up): `lookup` is the service's generated read method. RESP NORMAL (0) and the
     *  record, or NOTFND (13) without one -- or the condition the harness planned, and then nothing is read. */
    public <T> FileRead<T> read(String file, java.util.function.Supplier<Optional<T>> lookup) {
        int[] planned = root().injected("READ", file);
        if (planned != null) {
            return new FileRead<>(planned[0], planned[1], null);
        }
        T record = lookup.get().orElse(null);
        if (record == null) {
            return new FileRead<>(13, 80, null);  // #5092 (X52): IBM, EXEC CICS READ: NOTFND RESP2 80
        }
        int[] o = root().dupkeyOr();  // #4623: a planned DUPKEY follows the read that found the record
        return new FileRead<>(o[0], o[1], record);
    }

    /** READ FILE(file) UPDATE: as read, and the file's record is held for a REWRITE. */
    public <T> FileRead<T> readForUpdate(String file, java.util.function.Supplier<Optional<T>> lookup) {
        if (root().held.contains(file)) {
            return new FileRead<>(16, 28, null);  // #5092: a second READ UPDATE without a token, nothing released between
        }
        FileRead<T> r = read(file, lookup);
        if (r.normal()) {
            root().held.add(file);
        }
        return r;
    }

    /** #5092 (X52) READ FILE(file) KEYLENGTH(n) that IBM answers INVREQ: `resp2` 25 / 42 (a GENERIC KEYLENGTH not shorter than
     *  the key / below zero) or 26 (a KEYLENGTH without GENERIC that is not the key's length). Nothing is read or held; a
     *  second READ UPDATE on a held file is INVREQ 28 first, a planned condition next, as the stub orders them. */
    public <T> FileRead<T> readInvalid(String file, boolean update, int resp2) {
        if (update && root().held.contains(file)) {
            return new FileRead<>(16, 28, null);
        }
        int[] planned = root().injected("READ", file);
        if (planned != null) {
            return new FileRead<>(planned[0], planned[1], null);
        }
        return new FileRead<>(16, resp2, null);
    }

    /** #4270 READ FILE(file) GTEQ / GENERIC [UPDATE] (oracle_assumptions.md X22): `lookup` searches the file (the
     *  det port's DetCics.Store.search). RESP NORMAL and the record found, or NOTFND (13) with IBM's RESP2 80 ("An
     *  attempt to retrieve a record based on the search argument provided is unsuccessful") -- or the condition the
     *  harness planned, and then nothing is read. With `update` the file's record is held for a REWRITE. */
    public <T> FileRead<T> readSearch(String file, boolean update, java.util.function.Supplier<Optional<T>> lookup) {
        if (update && root().held.contains(file)) {
            return new FileRead<>(16, 28, null);  // #5092
        }
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
        int[] o = root().dupkeyOr();
        return new FileRead<>(o[0], o[1], record);
    }

    /** WRITE FILE(file) RIDFLD FROM: `exists` says whether the key is there already (DUPREC, 14, as CICS answers);
     *  else `store` saves the record (the service's generated repository save) and RESP is NORMAL -- or the
     *  condition the harness planned, and nothing is written. */
    public int write(String file, boolean exists, Runnable store) {
        int[] planned = root().injected("WRITE", file);
        if (planned != null) {
            return done(planned[0], planned[1]);  // #5044: the plan's RESP2 (IBM's), as the stub's WRITE sets it
        }
        if (exists) {
            return done(14, 0);
        }
        store.run();
        return done(0, 0);
    }

    /** REWRITE FILE(file) FROM: replaces the record a readForUpdate holds (INVREQ, 16, when none is held). */
    public int rewrite(String file, Runnable store) {
        int[] planned = root().injected("REWRITE", file);
        if (planned != null) {
            return done(planned[0], planned[1]);  // #5044
        }
        if (!root().held.remove(file)) {
            return done(16, 30);  // #5092: no READ UPDATE without a token before it
        }
        store.run();
        invalidateSet("READ " + file);  // IBM: a READ SET pointer is valid "until completion of a corresponding REWRITE"
        return done(0, 0);
    }

    /** DELETE FILE(file) RIDFLD: `exists` says whether the key is there (NOTFND, 13, when not); else `remove`
     *  deletes it (the service's generated repository delete) -- or the condition the harness planned. */
    public int delete(String file, boolean exists, Runnable remove) {
        int[] planned = root().injected("DELETE", file);
        if (planned != null) {
            return done(planned[0], planned[1]);
        }
        if (root().esds.containsKey(file)) {
            return done(16, 21);  // #5092 (X22): IBM, EXEC CICS DELETE: INVREQ RESP2 21, a file that refers to a VSAM ESDS
        }
        return deleteRecord(file, exists, remove);
    }

    /** DELETE FILE(file) GENERIC (#5092, X22): as `delete` over every record with the generic key; a file that is not a
     *  KSDS (an ESDS here) is INVREQ RESP2 22 (IBM: "A generic delete is issued for a file that is not a VSAM KSDS"). */
    public int deleteGeneric(String file, boolean exists, Runnable remove) {
        int[] planned = root().injected("DELETE", file);
        if (planned != null) {
            return done(planned[0], planned[1]);
        }
        if (root().esds.containsKey(file)) {
            return done(16, 22);
        }
        return deleteRecord(file, exists, remove);
    }

    /** DELETE FILE(file) [GENERIC] KEYLENGTH(n) that IBM answers INVREQ (#5092, X22): `resp2` 25 / 42 (a GENERIC KEYLENGTH
     *  not shorter than the key / below zero) or 26 (a KEYLENGTH without GENERIC that is not the key's length). Nothing is
     *  deleted; a planned condition comes first, then an ESDS (21, generic 22), as the stub orders them. */
    public int deleteInvalid(String file, boolean generic, int resp2) {
        int[] planned = root().injected("DELETE", file);
        if (planned != null) {
            return done(planned[0], planned[1]);
        }
        return done(16, root().esds.containsKey(file) ? (generic ? 22 : 21) : resp2);
    }

    private int deleteRecord(String file, boolean exists, Runnable remove) {
        if (!exists) {
            return done(13, 80);
        }
        remove.run();
        invalidateSet("READ " + file);  // IBM: "until completion of a corresponding ... DELETE"
        return done(0, 0);
    }

    /** DELETE FILE(file) without RIDFLD: the record a readForUpdate holds (INVREQ, 16, when none is held). */
    public int deleteHeld(String file, Runnable remove) {
        int[] planned = root().injected("DELETE", file);
        if (planned != null) {
            return done(planned[0], planned[1]);  // #5044
        }
        if (root().esds.containsKey(file)) {
            return done(16, 21);  // #5092 (X22): an ESDS
        }
        if (!root().held.remove(file)) {
            return done(16, 31);  // #5092: no RIDFLD and no READ UPDATE without a token before it
        }
        remove.run();
        invalidateSet("READ " + file);
        return done(0, 0);
    }

    /** READ FILE(file) UPDATE TOKEN(d) (#5078, X52; IBM, EXEC CICS READ): the record whose key is `key` is held under a
     *  token of its own, however many are held; returns the token (the task's 1, 2, ...: IBM leaves the value open,
     *  ASSUMED). */
    public int holdToken(String file, byte[] key) {
        int id = root().nextToken++;
        root().updateTokens.put(id, new Object[] {file, key});
        return id;
    }

    /** A token's {file, key}, spent; null when it matches no token in use for `file` (never issued, spent, or the
     *  token of another file's record): INVREQ, RESP2 47 ("a token whose value cannot be matched against any token in
     *  use for an existing read for UPDATE"). */
    private Object[] spendToken(String file, int token) {
        Object[] t = root().updateTokens.get(token);
        if (t == null || !t[0].equals(file)) {
            return null;
        }
        root().updateTokens.remove(token);
        return t;
    }

    /** REWRITE FILE(file) FROM TOKEN(token): replaces the record the token holds; `key` is FROM's record's key (a key
     *  other than the held record's is refused: IBM does not say). */
    public int rewriteToken(String file, int token, byte[] key, Runnable store) {
        int[] planned = root().injected("REWRITE", file);
        if (planned != null) {
            return done(planned[0], planned[1]);
        }
        Object[] t = root().updateTokens.get(token);
        if (t == null || !t[0].equals(file)) {
            return done(16, 47);
        }
        if (!java.util.Arrays.equals((byte[]) t[1], key)) {
            throw new UnsupportedOperationException("REWRITE TOKEN FROM: a key other than the held record's: not modelled");
        }
        spendToken(file, token);
        store.run();
        invalidateSet("READ " + file);
        return done(0, 0);
    }

    /** DELETE FILE(file) TOKEN(token), no RIDFLD: deletes the record the token holds (`remove` is given its key). */
    public int deleteToken(String file, int token, java.util.function.Consumer<byte[]> remove) {
        int[] planned = root().injected("DELETE", file);
        if (planned != null) {
            return done(planned[0], planned[1]);
        }
        if (root().esds.containsKey(file)) {
            return done(16, 21);  // #5092 (X22): an ESDS
        }
        Object[] t = spendToken(file, token);
        if (t == null) {
            return done(16, 47);
        }
        remove.accept((byte[]) t[1]);
        invalidateSet("READ " + file);
        return done(0, 0);
    }

    /** UNLOCK FILE(file) without TOKEN (#5079, X52): releases the record the file's readForUpdate holds; none held: no action, NORMAL (IBM). */
    public int unlockHeld(String file) {
        root().held.remove(file);
        invalidateSet("READ " + file);  // IBM: "until completion of a corresponding ... UNLOCK"
        return done(0, 0);
    }

    /** UNLOCK FILE(file) TOKEN(token): releases the record the token holds, unchanged (IBM, EXEC CICS UNLOCK). */
    public int unlockToken(String file, int token) {
        if (spendToken(file, token) == null) {
            return done(16, 47);
        }
        invalidateSet("READ " + file);
        return done(0, 0);
    }

    /** #4443 READ FILE(file) INTO LENGTH(intoLength) RIDFLD(ridfld) [UPDATE], recorded as the SPEC 6.2 READ event: as
     *  read / readForUpdate on the record's bytes, and a record longer than `intoLength` is LENGERR (22) RESP2 11
     *  (IBM, EXEC CICS READ), the whole record returned for the port to move its leading bytes INTO. Refused, as
     *  DetCics.readInto refuses them: a negative LENGTH and LENGERR on READ UPDATE (IBM does not say whether the
     *  record is then held). The event carries `length` (the record's) whenever a record was read, `data` on NORMAL. */
    public FileRead<byte[]> readInto(String file, byte[] ridfld, boolean update, int intoLength,
                                     java.util.function.Supplier<Optional<byte[]>> lookup) {
        if (intoLength < 0) {
            throw new UnsupportedOperationException("READ LENGTH " + intoLength + " (negative): not modelled");
        }
        FileRead<byte[]> r = update ? readForUpdate(file, lookup) : read(file, lookup);
        byte[] record = r.record();
        if (record != null && record.length > intoLength) {
            if (update) {
                throw new UnsupportedOperationException("READ UPDATE LENGERR (whether the record is held): not modelled");
            }
            r = new FileRead<>(22, 11, record);
        }
        event("READ", "file", file, "ridfld", ridfld, "update", update ? Boolean.TRUE : null, "resp", respName(r.resp()),
                "resp2", r.resp() == 0 ? null : r.resp2(), "length", record == null ? null : record.length,
                "data", r.resp() == 0 ? record : null);
        return r;
    }

    /** #6262 READ FILE(file) SET(ptr) RIDFLD(ridfld) [UPDATE], recorded as the SPEC 6.2 READ event with `set`: as read /
     *  readForUpdate. The event carries no `length` (INTO's LENGTH is not on the SET form) and, on NORMAL, `data` the
     *  record the pointer addresses; the caller acquires the block (acquireSet) from the returned record. */
    public FileRead<byte[]> readSetEvent(String file, byte[] ridfld, boolean update,
                                         java.util.function.Supplier<Optional<byte[]>> lookup) {
        FileRead<byte[]> r = update ? readForUpdate(file, lookup) : read(file, lookup);
        event("READ", "file", file, "ridfld", ridfld, "update", update ? Boolean.TRUE : null, "set", Boolean.TRUE,
                "resp", respName(r.resp()), "resp2", r.resp() == 0 ? null : r.resp2(),
                "data", r.resp() == 0 ? r.record() : null);
        return r;
    }

    /** #4443 REWRITE FILE(file) FROM(from), recorded as the SPEC 6.2 REWRITE event: as rewrite; `store` saves `from`. */
    public int rewriteFrom(String file, byte[] from, Runnable store) {
        int resp = rewrite(file, store);
        event("REWRITE", "file", file, "data", from, "resp", respName(resp), "resp2", resp == 0 ? null : resp2());
        return resp;
    }

    /** #4443 UNLOCK FILE(file) without TOKEN, recorded as the SPEC 6.2 UNLOCK event: as unlockHeld. */
    public int unlock(String file) {
        int resp = unlockHeld(file);
        event("UNLOCK", "file", file, "resp", respName(resp), "resp2", resp == 0 ? null : resp2());
        return resp;
    }

    /** #6262 STARTBR FILE(file) RIDFLD(ridfld) [GTEQ | EQUAL], recorded as the SPEC 6.2 STARTBR event: as startbr;
     *  `mode` is GTEQ or EQUAL, `ridfld` the key on entry, RESP2 where the command is not NORMAL. */
    public int startbrEvent(String file, byte[] ridfld, String key, boolean equal,
                            java.util.function.Supplier<java.util.NavigableSet<String>> keys) {
        int resp = startbr(file, key, equal, keys);
        event("STARTBR", "file", file, "ridfld", ridfld, "mode", equal ? "EQUAL" : "GTEQ", "resp", respName(resp),
                "resp2", resp == 0 ? null : resp2());
        return resp;
    }

    /** #6262 READNEXT / READPREV FILE(file) RIDFLD(ridfld) INTO LENGTH(intoLength), recorded as the SPEC 6.2 event of
     *  that name: as readnext / readprev, then `lookup` fetches the record of the key read. `ridfld` is the key on
     *  entry; the event carries `length` (the record's) and `data` when the read delivered the record, RESP2 where it
     *  is not NORMAL. A record longer than `intoLength` is LENGERR (22) RESP2 11, as readInto; a negative LENGTH is refused. */
    public Browsed readnextInto(String file, byte[] ridfld, String key, int intoLength,
                                java.util.function.Function<String, Optional<byte[]>> lookup) {
        return browseEvent("READNEXT", readnext(file, key), file, ridfld, intoLength, lookup, false);
    }

    /** #6262 READNEXT / READPREV FILE(file) SET(ptr) RIDFLD(ridfld): as readnextInto / readprevInto, recorded with `set`
     *  and no `length`; `data` is the record the pointer addresses. The caller acquires the block from `lookup`'s record. */
    public Browsed readnextSetEvent(String file, byte[] ridfld, String key,
                                    java.util.function.Function<String, Optional<byte[]>> lookup) {
        return browseEvent("READNEXT", readnext(file, key), file, ridfld, Integer.MAX_VALUE, lookup, true);
    }

    public Browsed readprevSetEvent(String file, byte[] ridfld, String key,
                                    java.util.function.Function<String, Optional<byte[]>> lookup) {
        return browseEvent("READPREV", readprev(file, key), file, ridfld, Integer.MAX_VALUE, lookup, true);
    }

    public Browsed readprevInto(String file, byte[] ridfld, String key, int intoLength,
                                java.util.function.Function<String, Optional<byte[]>> lookup) {
        return browseEvent("READPREV", readprev(file, key), file, ridfld, intoLength, lookup, false);
    }

    private Browsed browseEvent(String kind, Browsed b, String file, byte[] ridfld, int intoLength,
                                java.util.function.Function<String, Optional<byte[]>> lookup, boolean set) {
        if (intoLength < 0) {
            throw new UnsupportedOperationException(kind + " LENGTH " + intoLength + " (negative): not modelled");
        }
        byte[] record = b.normal() ? lookup.apply(b.key()).orElse(null) : null;
        int resp = b.resp();
        int resp2 = b.resp2();
        if (record != null && record.length > intoLength) {
            resp = 22;
            resp2 = 11;
        }
        boolean normal = resp == 0 || resp == 15;
        event(kind, "file", file, "ridfld", ridfld, "resp", respName(resp), "resp2", resp == 0 ? null : resp2,
                "set", set ? Boolean.TRUE : null, "length", set || record == null ? null : record.length,
                "data", normal ? record : null);
        return new Browsed(resp, resp2, b.key());
    }

    /** #6262 ENDBR FILE(file), recorded as the SPEC 6.2 ENDBR event: as endbr. */
    public int endbrEvent(String file) {
        int resp = endbr(file);
        event("ENDBR", "file", file, "resp", respName(resp), "resp2", resp == 0 ? null : resp2());
        return resp;
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
            // #4623: DUPKEY (15) delivers the record too; #6271 (X70): an injected abend answers 0 with no key and delivers none
            return key != null && (resp == 0 || resp == 15);
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
        int[] o = root().dupkeyOr();
        return new Browsed(o[0], o[1], at);
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
        int[] o = root().dupkeyOr();
        return new Browsed(o[0], o[1], at);
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
            // #4623: DUPKEY (15) delivers the record too; #6271 (X70): an injected abend answers 0 with no record
            return record != null && (resp == 0 || resp == 15);
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
        if (rec.length > intoLength) {
            return new BrowsedRba(22, 11, rba, rec);
        }
        int[] o = root().dupkeyOr();
        return new BrowsedRba(o[0], o[1], rba, rec);
    }

    /** ENDBR FILE(file): the browse ends; INVREQ (16) when none is active. */
    public int endbr(String file) {
        int[] planned = root().injected("ENDBR", file);
        if (planned != null) {
            return done(planned[0], planned[1]);
        }
        if (root().browses.remove(file) == null) {
            return done(16, 35);
        }
        invalidateSet("BROWSE " + file);  // IBM: "no longer valid after an ENDBR"
        return done(0, 0);
    }

"""
