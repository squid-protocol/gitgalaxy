#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: CicsTask's named-counter support (GET / UPDATE / REWIND / DEFINE / QUERY / DELETE COUNTER and
# DCOUNTER, split out by #5274)
#
# PURPOSE:
# The named-counter part of the CICS task runtime the transaction forge emits (CICS_TASK_JAVA): withCounters, the
# counter limits, getCounter and its overloads, the DEFINE / UPDATE / REWIND / DELETE / QUERY commands and the
# fullword checks. The forge splices it into CicsTask where it always sat, so the class is byte-identical.
# ==============================================================================

COUNTERS_JAVA = """\
    private java.util.Map<String, Long> counters = new java.util.HashMap<>();  // the region's named counters (root's)
    /** #4770 (X45): the {minimum, maximum} (unsigned doublewords) of a counter DEFINE DCOUNTER made; a counter with no entry
     *  (DEFINE COUNTER's, or one a scenario states) has limits the run does not state. */
    private java.util.Map<String, long[]> counterLimits = new java.util.HashMap<>();
    /** #7589: the counters in IBM's counter-at-limit condition, a flag beside the value (which is then MAXIMUM): the MAXIMUM + 1
     *  marker overflows for the default doubleword maximum. */
    private java.util.Set<String> counterAtLimit = new java.util.HashSet<>();

    /** Whether the counter is at its limit. A value past MAXIMUM (a scenario's seed in the old MAXIMUM + 1 form) is read as the
     *  flag with the value MAXIMUM. */
    private boolean atLimit(String key, long[] lim) {
        Long v = counters.get(key);
        if (lim != null && lim[1] != -1L && v != null && Long.compareUnsigned(v, lim[1]) > 0) {
            counters.put(key, lim[1]);
            counterAtLimit.add(key);
        }
        return counterAtLimit.contains(key);
    }

    /** Store a counter's value after a command: MAXIMUM + 1 is the counter at its limit (the value MAXIMUM and the flag). */
    private void storeCounter(String key, long[] lim, long value) {
        if (lim != null && lim[1] != -1L && value == lim[1] + 1) {
            counters.put(key, lim[1]);
            counterAtLimit.add(key);
        } else {
            counters.put(key, value);
            counterAtLimit.remove(key);
        }
    }

    /** The region's named counters, "POOL/NAME" -> the value the next GET COUNTER returns. */
    public CicsTask withCounters(java.util.Map<String, Long> counters) {
        this.counters = counters;
        return this;
    }

    /** The INVREQ RESP2 IBM gives a counter or pool name outside its rules (X30): 403 for the pool (A-Z 0-9 $ @ # _, no
     *  embedded spaces), 404 for the counter (A-Z 0-9 _ $ # @, not starting with a digit or an underscore, no embedded
     *  spaces); 0 for a valid pair. A counter name of blanks only is not covered by IBM's rules: refused. */
    private static int counterNameResp2(String pool, String name) {
        String p = pool == null ? "" : pool.stripTrailing();
        for (int i = 0; i < p.length(); i++) {
            char c = p.charAt(i);
            if (!((c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '$' || c == '@' || c == '#' || c == '_')) {
                return 403;
            }
        }
        String n = name == null ? "" : name.stripTrailing();
        if (n.isEmpty()) {
            throw refused("a named counter with a blank name");
        }
        for (int i = 0; i < n.length(); i++) {
            char c = n.charAt(i);
            boolean ok = (c >= 'A' && c <= 'Z') || c == '$' || c == '@' || c == '#' || (i > 0 && ((c >= '0' && c <= '9') || c == '_'));
            if (!ok) {
                return 404;
            }
        }
        return 0;
    }

    private static String counterKey(String pool, String name) {
        return (pool == null ? "" : pool.strip()) + "/" + (name == null ? "" : name.strip());
    }

    /** GET COUNTER (IBM CICS TS): {RESP, RESP2, value} -- the named counter's current value, after which it is one more;
     *  INVREQ (16) RESP2 201 "Named counter not found" (the page lists no NOTFND; X30), 403 / 404 for a name outside
     *  IBM's rules. */
    public long[] getCounter(String pool, String name) {
        return getCounter(pool, name, 1);
    }

    /** GET DCOUNTER COUNTER VALUE INCREMENT(n) [WRAP] (IBM CICS TS, GET COUNTER and GET DCOUNTER; X30): the value
     *  before the increment, after which the counter is `increment` more (IBM: "incremented after the current number has been
     *  assigned"). WRAP changes nothing here: it acts only at the counter's maximum, which the run does not state, so a
     *  counter that would pass 4294967295 -- the smallest maximum IBM's page leaves open -- is refused, as is an INCREMENT
     *  not above zero (IBM gives it no meaning). */
    public long[] getCounter(String pool, String name, long increment) {
        return getCounter(pool, name, increment, false);
    }

    /** GET DCOUNTER ... INCREMENT(n) [WRAP] (X30; #4770, X45): {RESP, RESP2, value}, the INCREMENT an unsigned doubleword.
     *  A counter DEFINE DCOUNTER made has the limits it was given (unsigned): at its limit (the value past MAXIMUM, which a
     *  GET leaves it at when it reaches it) WRAP "resets the current value ... equal to the minimum value" and the GET
     *  returns that, and without WRAP the GET is SUPPRESSED (72) RESP2 101 and "the current number is not changed". An
     *  INCREMENT beyond MAXIMUM - MINIMUM, or one that carries the counter past MAXIMUM + 1 (IBM's REDUCE / 406 boundaries
     *  are not stated), is refused; so is a counter that would pass a doubleword. A counter with no limits entry is as
     *  before: WRAP changes nothing and one that would pass 4294967295 is refused. */
    public long[] getCounter(String pool, String name, long increment, boolean wrap) {
        return getCounter(pool, name, increment, wrap, false, null, null, false);
    }

    /** GET COUNTER / DCOUNTER ... [REDUCE] [COMPAREMIN(n)] [COMPAREMAX(m)] (#5039, X53): as above, with IBM's REDUCE ("the
     *  server may reduce the increment, and the request succeeds with the current value set to the maximum plus 1": an
     *  INCREMENT that would carry the counter past MAXIMUM + 1 leaves it at MAXIMUM + 1) and the value handed out compared with
     *  the bounds: both given and COMPAREMAX below COMPAREMIN, in range when it meets either; out of range is SUPPRESSED (72)
     *  RESP2 103 and the counter is unchanged (ASSUMED: IBM does not say). `fullword`: a COUNTER, whose compare values are
     *  signed fullwords (a negative one is refused). Refused: REDUCE with WRAP, REDUCE or a compare at a counter already at its
     *  limit (101 or 103 first, REDUCE with nothing left to reduce: not stated). */
    public long[] getCounter(String pool, String name, long increment, boolean wrap, boolean reduce, Long cmpMin, Long cmpMax,
            boolean fullword) {
        int bad = counterNameResp2(pool, name);
        if (bad != 0) {
            return new long[] {16, bad, 0};
        }
        if (increment == 0) {
            throw refused("GET COUNTER with an INCREMENT not above zero");
        }
        CicsTask r = root();
        String key = counterKey(pool, name);
        Long v = r.counters.get(key);
        if (v == null) {
            return new long[] {16, 201, 0};
        }
        long[] lim = r.counterLimits.get(key);
        if (reduce && wrap) {
            throw refused("GET COUNTER with both REDUCE and WRAP");
        }
        if ((cmpMin != null && cmpMin < 0 && fullword) || (cmpMax != null && cmpMax < 0 && fullword)) {
            throw refused("GET COUNTER COMPAREMIN / COMPAREMAX below zero");
        }
        if (lim == null) {
            if (!counterInRange(v, cmpMin, cmpMax)) {
                return new long[] {72, 103, 0};
            }
            if (increment < 0 || v + increment > 4294967295L) {
                throw refused(increment < 0 ? "GET COUNTER past a doubleword" : "GET COUNTER past 4294967295: the counter's maximum is not stated");
            }
            r.counters.put(key, v + increment);
            return new long[] {0, 0, v};
        }
        long min = lim[0], max = lim[1];
        if (Long.compareUnsigned(increment, max - min) > 0) {
            throw refused("GET COUNTER with an INCREMENT beyond the counter's range");
        }
        if (r.atLimit(key, lim)) {  // #7589: at its limit, a flag (the value is MAXIMUM)
            if (reduce) {
                throw refused("GET COUNTER REDUCE at a counter already at its limit");
            }
            if (cmpMin != null || cmpMax != null) {
                throw refused("GET COUNTER COMPAREMIN / COMPAREMAX at a counter already at its limit");
            }
            if (!wrap) {
                return new long[] {72, 101, 0};
            }
            r.counters.put(key, min + increment);
            r.counterAtLimit.remove(key);
            return new long[] {0, 0, min};
        }
        if (!counterInRange(v, cmpMin, cmpMax)) {
            return new long[] {72, 103, 0};
        }
        long next = v + increment;
        boolean over = Long.compareUnsigned(next, v) < 0;
        // the counter reaches its limit when it would be MAXIMUM + 1 (for the default maximum: 2^64, so next wraps to 0)
        boolean hit = max == -1L ? over && next == 0 : !over && next == max + 1;
        boolean beyond = max == -1L ? over && next != 0 : over || Long.compareUnsigned(next, max + 1) > 0;
        if (over && !hit) {
            throw refused("GET COUNTER past a doubleword");
        }
        if (!hit && beyond) {
            if (!reduce) {
                throw refused("GET COUNTER with an INCREMENT past MAXIMUM + 1");
            }
            hit = true;
        }
        if (hit) {
            r.counters.put(key, max);
            r.counterAtLimit.add(key);
        } else {
            r.counters.put(key, next);
        }
        return new long[] {0, 0, v};
    }

    /** Whether the value a GET hands out meets COMPAREMIN / COMPAREMAX (null: not given): at or above the one, at or below the
     *  other; with COMPAREMAX below COMPAREMIN, either (IBM). */
    private static boolean counterInRange(long v, Long cmpMin, Long cmpMax) {
        boolean geMin = cmpMin == null || Long.compareUnsigned(v, cmpMin) >= 0;
        boolean leMax = cmpMax == null || Long.compareUnsigned(v, cmpMax) <= 0;
        return cmpMin != null && cmpMax != null && Long.compareUnsigned(cmpMax, cmpMin) < 0 ? geMin || leMax : geMin && leMax;
    }

    /** REWIND COUNTER / DCOUNTER [INCREMENT(n)] (IBM CICS TS, REWIND COUNTER and REWIND DCOUNTER; #5039, X53): {RESP, RESP2}.
     *  "Resets a named counter that has reached its limit" to its minimum; SUPPRESSED (72) RESP2 102 for one that has not.
     *  A counter has reached its limit at MAXIMUM + 1 (where a GET leaves it). INVREQ 406 for an INCREMENT beyond (maximum -
     *  minimum) + 1 (stated), 201 / 403 / 404 as GET. Refused: an INCREMENT of zero or above 1 within the range (how the limit
     *  test applies it is not stated), a counter with no limits entry. */
    public int[] rewindCounter(String pool, String name, long increment) {
        int bad = counterNameResp2(pool, name);
        if (bad != 0) {
            return new int[] {16, bad};
        }
        if (increment == 0) {
            throw refused("REWIND COUNTER with an INCREMENT not above zero");
        }
        CicsTask r = root();
        String key = counterKey(pool, name);
        Long v = r.counters.get(key);
        if (v == null) {
            return new int[] {16, 201};
        }
        long[] lim = r.counterLimits.get(key);
        if (lim == null) {
            throw refused("REWIND COUNTER of a counter whose limits the run does not state");
        }
        long min = lim[0], max = lim[1], range = max - min + 1;  // (0: a full doubleword, which no INCREMENT exceeds)
        if (range != 0 && Long.compareUnsigned(increment, range) > 0) {
            return new int[] {16, 406};
        }
        if (increment != 1) {
            throw refused("REWIND COUNTER with an INCREMENT above 1");
        }
        if (!r.atLimit(key, lim)) {
            return new int[] {72, 102};
        }
        r.counters.put(key, min);
        r.counterAtLimit.remove(key);
        return new int[] {0, 0};
    }

    /** UPDATE COUNTER / DCOUNTER VALUE(n) (IBM CICS TS, UPDATE COUNTER and UPDATE DCOUNTER; #5039, X53): {RESP, RESP2} -- the
     *  new current value. INVREQ 406 for a VALUE below MINIMUM or above MAXIMUM + 1, 201 / 403 / 404 as GET. `fullword` (a
     *  COUNTER): a VALUE below zero is refused, as DEFINE's; a counter with no limits entry is refused. */
    public int[] updateCounter(String pool, String name, long value, boolean fullword) {
        int bad = counterNameResp2(pool, name);
        if (bad != 0) {
            return new int[] {16, bad};
        }
        if (fullword && value < 0) {
            throw refused("UPDATE COUNTER with a VALUE below zero");
        }
        CicsTask r = root();
        String key = counterKey(pool, name);
        if (r.counters.get(key) == null) {
            return new int[] {16, 201};
        }
        long[] lim = r.counterLimits.get(key);
        if (lim == null) {
            throw refused("UPDATE COUNTER of a counter whose limits the run does not state");
        }
        if (Long.compareUnsigned(value, lim[0]) < 0 || (lim[1] != -1L && Long.compareUnsigned(value, lim[1] + 1) > 0)) {
            return new int[] {16, 406};
        }
        r.storeCounter(key, lim, value);
        return new int[] {0, 0};
    }

    /** DEFINE DCOUNTER (IBM CICS TS, DEFINE COUNTER and DEFINE DCOUNTER; #4770, X45): {RESP, RESP2} -- unsigned doublewords:
     *  the caller passes MINIMUM 0, MAXIMUM -1 (a doubleword of X'FF', IBM's defaults) and VALUE 0 for what the command
     *  omits. INVREQ 407 when MAXIMUM is below MINIMUM, 406 when VALUE is below MINIMUM or above MAXIMUM + 1, 202 for a
     *  duplicate, 403 / 404 for a name outside IBM's rules (407 / 406 are checked first: the page gives no order). */
    public int[] defineDcounter(String pool, String name, long value, long min, long max) {
        int bad = counterNameResp2(pool, name);
        if (bad != 0) {
            return new int[] {16, bad};
        }
        if (Long.compareUnsigned(max, min) < 0) {
            return new int[] {16, 407};
        }
        if (Long.compareUnsigned(value, min) < 0 || (max != -1L && Long.compareUnsigned(value, max + 1) > 0)) {
            return new int[] {16, 406};
        }
        CicsTask r = root();
        String key = counterKey(pool, name);
        if (r.counters.containsKey(key)) {
            return new int[] {16, 202};
        }
        r.counterLimits.put(key, new long[] {min, max});
        r.storeCounter(key, new long[] {min, max}, value);
        return new int[] {0, 0};
    }

    /** QUERY DCOUNTER (#4770, X45): {RESP, RESP2, value, minimum, maximum} -- the counter's value, which stays, and its
     *  limits (unsigned doublewords). `limits`: the command asks for MINIMUM or MAXIMUM, which a counter with no limits entry
     *  (DEFINE COUNTER's, or a scenario's) has none the run states for: refused. */
    public long[] queryDcounter(String pool, String name, boolean limits) {
        int bad = counterNameResp2(pool, name);
        if (bad != 0) {
            return new long[] {16, bad, 0, 0, 0};
        }
        CicsTask r = root();
        String key = counterKey(pool, name);
        Long v = r.counters.get(key);
        if (v == null) {
            return new long[] {16, 201, 0, 0, 0};
        }
        long[] lim = r.counterLimits.get(key);
        if (lim == null && limits) {
            throw refused("QUERY DCOUNTER MINIMUM / MAXIMUM of a counter whose limits the run does not state");
        }
        if (r.atLimit(key, lim)) {
            if (lim[1] == -1L) {
                throw refused("QUERY DCOUNTER of a counter at its limit");
            }
            v = lim[1] + 1;
        }
        return new long[] {0, 0, v, lim == null ? 0 : lim[0], lim == null ? 0 : lim[1]};
    }

    /** DEFINE COUNTER (IBM CICS TS, DEFINE COUNTER; X30, #5039, X50): {RESP, RESP2} -- fullwords: the caller passes
     *  MINIMUM 0, MAXIMUM 2147483647 (X'7FFFFFFF', IBM's defaults) and VALUE 0 for what the command omits. INVREQ 407
     *  when MAXIMUM is below MINIMUM or beyond X'7FFFFFFF', 406 when VALUE is below MINIMUM or above MAXIMUM + 1,
     *  202 for a duplicate, 403 / 404 for a name outside IBM's rules. A VALUE or MINIMUM below zero is refused. */
    public int[] defineCounter(String pool, String name, long value, long min, long max) {
        int bad = counterNameResp2(pool, name);
        if (bad != 0) {
            return new int[] {16, bad};
        }
        if (value < 0) {
            throw refused("DEFINE COUNTER with a VALUE below zero");
        }
        if (min < 0) {
            throw refused("DEFINE COUNTER with a MINIMUM below zero");
        }
        if (max < min || max > 2147483647L) {
            return new int[] {16, 407};
        }
        if (value < min || value > max + 1) {
            return new int[] {16, 406};
        }
        CicsTask r = root();
        String key = counterKey(pool, name);
        if (r.counters.containsKey(key)) {
            return new int[] {16, 202};
        }
        r.counterLimits.put(key, new long[] {min, max});
        r.storeCounter(key, new long[] {min, max}, value);
        return new int[] {0, 0};
    }

    public int[] defineCounter(String pool, String name, int value) {
        return defineCounter(pool, name, (long) value, 0L, 2147483647L);
    }

    /** DELETE COUNTER (IBM CICS TS, DELETE COUNTER; X30): {RESP, RESP2} -- INVREQ 201 "Named counter not found"
     *  (the page lists no NOTFND), 403 for a pool outside IBM's rules. */
    public int[] deleteCounter(String pool, String name) {
        int bad = counterNameResp2(pool, name);
        if (bad == 403) {
            return new int[] {16, bad};
        }
        root().counterLimits.remove(counterKey(pool, name));
        root().counterAtLimit.remove(counterKey(pool, name));
        java.util.Map<String, Long> all = root().counters;
        return all.remove(counterKey(pool, name)) == null ? new int[] {16, 201} : new int[] {0, 0};
    }

    /** QUERY COUNTER (IBM CICS TS, QUERY COUNTER; #4415 slice 2, X29; #5039, X50): {RESP, RESP2, value, minimum, maximum} --
     *  the counter's value, which stays, and its limits (fullwords). `limits`: the command asks for MINIMUM or MAXIMUM, which a
     *  counter with no limits entry has none the run states for: refused. */
    public int[] queryCounter(String pool, String name, boolean limits) {
        int bad = counterNameResp2(pool, name);
        if (bad != 0) {
            return new int[] {16, bad, 0, 0, 0};
        }
        CicsTask r = root();
        String key = counterKey(pool, name);
        Long v = r.counters.get(key);
        if (v == null) {
            return new int[] {16, 201, 0, 0, 0};
        }
        long[] lim = r.counterLimits.get(key);
        if (lim == null && limits) {
            throw refused("QUERY COUNTER MINIMUM / MAXIMUM of a counter whose limits the run does not state");
        }
        if (lim != null && limits && (lim[0] < 0 || lim[0] > 2147483647L || lim[1] < 0 || lim[1] > 2147483647L)) {
            throw refused("QUERY COUNTER MINIMUM / MAXIMUM of a counter whose limits are beyond a fullword");
        }
        boolean atLimit = r.atLimit(key, lim);
        if (atLimit) {
            if (lim[1] == -1L) {
                throw refused("QUERY COUNTER of a counter at its limit");
            }
            v = lim[1] + 1;
        }
        int le = fullwordLengerr(atLimit, v);
        return new int[] {le == 0 ? 0 : 22, le, v.intValue(), lim == null ? 0 : (int) lim[0], lim == null ? 0 : (int) lim[1]};
    }

    /** LENGERR RESP2 of a fullword (COUNTER) command whose counter holds `v`, an unsigned doubleword (IBM CICS TS, GET COUNTER and
     *  QUERY COUNTER; #4770, X30): 0 when v fits a signed fullword, or when the counter is at its limit (MAXIMUM + 1: "LENGERR can't
     *  occur at counter-at-limit", the value is the maximum plus one in 32 bits). Else LENGERR for a counter DCOUNTER made too
     *  large: RESP2 1 the value overflowed into the sign bit (no bit above the low word), 2 "too large ... by only 1 bit; the
     *  overflow value is exactly 1" (the high word is 1), 3 greater than 1 (ASSUMED: IBM does not say how a value that is both
     *  is numbered; the high word decides). The operation completes: VALUE is the low-order 32 bits. */
    private static int fullwordLengerr(boolean atLimit, long v) {
        if (v >= 0 && v <= 2147483647L) {
            return 0;
        }
        if (atLimit) {
            return 0;
        }
        long high = v >>> 32;
        return high == 0 ? 1 : high == 1 ? 2 : 3;
    }

    /** The result {RESP, RESP2, value} of a GET COUNTER (fullword form) as IBM's LENGERR warning has it (#4770, X30): RESP 22 with
     *  RESP2 1 / 2 / 3 and VALUE the low-order 32 bits (a signed number) for a counter that holds more than a fullword; any other
     *  result as it is. The counter has been advanced: "the named counter server completes the operation". */
    public long[] fullwordGet(String pool, String name, long[] r) {
        if (r[0] != 0) {
            return r;
        }
        int le = fullwordLengerr(false, r[2]);
        return le == 0 ? r : new long[] {22, le, (int) r[2]};
    }

    public int[] queryCounter(String pool, String name) {
        int[] r = queryCounter(pool, name, false);
        return new int[] {r[0], r[1], r[2]};
    }

"""
