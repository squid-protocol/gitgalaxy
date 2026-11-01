/* #5274: the named counters: GET, DEFINE, DELETE, QUERY, REWIND and UPDATE, fullword and doubleword -- split out of ggcics.c, which includes it here. */
static int counters_read(counter_row *rows) {
    char path[4096], line[256];
    int n = 0;
    snprintf(path, sizeof path, "%s/counters.cfg", dir_in());
    FILE *f = fopen(path, "r");
    while (f && n < MAXCNT && fgets(line, sizeof line, f))
    {
        int got = sscanf(line, "%63s %63s %llu %llu %llu", rows[n].pool, rows[n].name, &rows[n].value, &rows[n].min, &rows[n].max);
        rows[n].limited = got == 5;
        if (got == 3 || got == 5) n++;
    }
    if (f) fclose(f);
    return n;
}

static void counters_write(const counter_row *rows, int n) {
    char path[4096];
    snprintf(path, sizeof path, "%s/counters.cfg", dir_in());
    FILE *f = fopen(path, "w");
    for (int i = 0; f && i < n; i++) {
        if (rows[i].limited)
            fprintf(f, "%s %s %llu %llu %llu\n", rows[i].pool, rows[i].name, rows[i].value, rows[i].min, rows[i].max);
        else
            fprintf(f, "%s %s %llu\n", rows[i].pool, rows[i].name, rows[i].value);
    }
    if (f) fclose(f);
}

static int counter_find(const counter_row *rows, int n, const char *pool, const char *name) {
    for (int i = 0; i < n; i++)
        if (strcmp(rows[i].pool, pool) == 0 && strcmp(rows[i].name, name) == 0) return i;
    return -1;
}

/* The INVREQ RESP2 IBM gives a name outside its rules (EXEC CICS DEFINE / GET COUNTER): 403 for the pool (A-Z 0-9 $ @ # _,
 * no embedded spaces), 404 for the counter (A-Z $ @ # first, then also 0-9 and _; no embedded spaces); 0 for a valid pair.
 * A counter name of blanks only is not covered by IBM's rules: refused. */
static int counter_name_resp2(const char *pool, const char *name) {
    for (const char *q = pool; *q; q++)
        if (!((*q >= 'A' && *q <= 'Z') || (*q >= '0' && *q <= '9') || *q == '$' || *q == '@' || *q == '#' || *q == '_'))
            return 403;
    if (!name[0]) refuse("a named counter with a blank name");
    for (const char *q = name; *q; q++) {
        int ok = (*q >= 'A' && *q <= 'Z') || *q == '$' || *q == '@' || *q == '#' ||
                 (q > name && ((*q >= '0' && *q <= '9') || *q == '_'));
        if (!ok) return 404;
    }
    return 0;
}

static void counter_names(gg_cics *c, char *want, char *pool, char *shown) {
    trim(c->qname, 16, want);
    trim(c->name1, 8, pool);
    strcpy(shown, pool);
    if (!pool[0]) strcpy(pool, "-");
}

/* #5039 (X53): the value a GET hands out meets COMPAREMIN / COMPAREMAX (`has_*`: given): at or above the one, at or below the
 * other, either when COMPAREMAX is below COMPAREMIN. As CicsTask.counterInRange. */
static int counter_in_range(unsigned long long v, int has_min, unsigned long long cmin, int has_max, unsigned long long cmax) {
    int ge = !has_min || v >= cmin, le = !has_max || v <= cmax;
    return has_min && has_max && cmax < cmin ? (ge || le) : (ge && le);
}

/* GET with #5039 (X53)'s REDUCE ("the request succeeds with the current value set to the maximum plus 1": an INCREMENT that would
 * carry the counter past MAXIMUM + 1 leaves it there) and COMPAREMIN / COMPAREMAX (2: SUPPRESSED RESP2 103, the counter unchanged).
 * Refused, as CicsTask.getCounter: REDUCE with WRAP, REDUCE or a compare at a counter already at its limit, a negative compare
 * value of a fullword counter (`full`). */
static int counter_step_x(counter_row *r, unsigned long long incr, int wrap, int reduce, int has_min, unsigned long long cmin,
                          int has_max, unsigned long long cmax, int full, unsigned long long *out) {
    unsigned long long v = r->value, next;
    if (reduce && wrap) refuse("GET COUNTER with both REDUCE and WRAP");
    if (full && ((has_min && ((cmin >> 31) & 1)) || (has_max && ((cmax >> 31) & 1)))) refuse("GET COUNTER COMPAREMIN / COMPAREMAX below zero");
    if (!r->limited) {
        if (!counter_in_range(v, has_min, cmin, has_max, cmax)) return 2;
        if (incr > 4294967295ULL || v + incr > 4294967295ULL) refuse("GET COUNTER past 4294967295: the counter's maximum is not stated");
        *out = v;
        r->value = v + incr;
        return 0;
    }
    if (incr > r->max - r->min) refuse("GET COUNTER with an INCREMENT beyond the counter's range");
    if (r->max != ~0ULL && v > r->max) { /* at its limit: the counter is MAXIMUM + 1 */
        if (reduce) refuse("GET COUNTER REDUCE at a counter already at its limit");
        if (has_min || has_max) refuse("GET COUNTER COMPAREMIN / COMPAREMAX at a counter already at its limit");
        if (!wrap) return 1;
        *out = r->min;
        r->value = r->min + incr;
        return 0;
    }
    if (!counter_in_range(v, has_min, cmin, has_max, cmax)) return 2;
    next = v + incr;
    if (next < v) refuse("GET COUNTER past a doubleword");
    if (next > r->max && next - r->max > 1) {
        if (!reduce) refuse("GET COUNTER with an INCREMENT past MAXIMUM + 1");
        next = r->max + 1;
    }
    *out = v;
    r->value = next;
    return 0;
}

/* One GET of the counter at rows[at] (as CicsTask.getCounter(pool, name, increment, wrap)): the value it hands back in *out and
 * the counter `incr` more; 1 (SUPPRESSED RESP2 101, the counter unchanged) for a DEFINE DCOUNTER counter at its limit without
 * WRAP. #4770 (X45): such a counter has the limits it was given (unsigned doublewords): at its limit (MAXIMUM + 1) WRAP
 * "resets the current value ... equal to the minimum value" and the GET returns that; an INCREMENT beyond MAXIMUM - MINIMUM, or
 * past MAXIMUM + 1 (IBM's 406 / REDUCE boundaries are not stated), and a counter past a doubleword are refused. A counter with
 * no limits has none the run states: WRAP changes nothing and one past 4294967295 is refused, as before. */
static int counter_step(counter_row *r, unsigned long long incr, int wrap, unsigned long long *out) {
    return counter_step_x(r, incr, wrap, 0, 0, 0, 0, 0, 0, out);
}

static void put32(unsigned char *p, unsigned long long v) {
    for (int i = 3; i >= 0; i--) { p[i] = (unsigned char)(v & 255); v >>= 8; }
}

/* LENGERR RESP2 of a fullword (COUNTER) command whose counter holds v (#4770, X30; IBM, GET COUNTER and QUERY COUNTER): 0 when v fits
 * a signed fullword or the counter is at its limit (v past MAXIMUM: "LENGERR can't occur at counter-at-limit"); else 1 (no bit above
 * the low word: the sign bit), 2 (the high word is 1), 3 (above 1). The operation completes: VALUE is the low 32 bits. As
 * CicsTask.fullwordLengerr. */
static int counter_lengerr(const counter_row *r, unsigned long long v) {
    if (v <= 2147483647ULL) return 0;
    if (r->limited && r->max != ~0ULL && v > r->max) return 0;
    return (v >> 32) == 0 ? 1 : (v >> 32) == 1 ? 2 : 3;
}

/* GET COUNTER(qname) POOL(name1) VALUE(value) INCREMENT(inc) [WRAP] (IBM CICS TS, GET COUNTER; X30, #5039, X50): the
 * value before the increment is written big-endian (signed fullword) into `value`, after which the counter is the
 * increment more; `wrap` is WRAP. See counter_step for the limits. As CicsTask.getCounter(pool, name, increment, wrap). */
int GGCGCNT(gg_cics *c, unsigned char *value, int valuelen, unsigned char *inc, int inclen, int wrap) {
    char want[17], pool[9], shown[9];
    counter_row rows[MAXCNT];
    unsigned long long incr = 0;
    int i;
    counter_names(c, want, pool, shown);
    int bad = counter_name_resp2(shown, want);
    if (inclen == 8 && inc[0] == 0 && inc[1] == 0 && inc[2] == 0 && inc[3] == 0) {
        inc += 4;
        inclen = 4;
    }
    if (inclen > 4 || valuelen != 4) refuse("GET COUNTER with a VALUE or INCREMENT that is not a fullword");
    for (i = 0; i < inclen; i++) incr = incr * 256 + inc[i];
    if (incr == 0) refuse("GET COUNTER with an INCREMENT not above zero");
    int n = counters_read(rows), at = bad ? -1 : counter_find(rows, n, pool, want);
    c->resp = NORMAL;
    c->resp2 = 0;
    if (bad) {
        c->resp = INVREQ;
        c->resp2 = bad;
    } else if (at < 0) {
        c->resp = INVREQ;
        c->resp2 = 201;
    } else {
        unsigned long long v;
        if (counter_step(&rows[at], incr, wrap, &v)) {
            c->resp = SUPPRESSED;
            c->resp2 = 101;
            return 0;
        }
        put32(value, v);
        counters_write(rows, n);
        if ((c->resp2 = counter_lengerr(&rows[at], v))) c->resp = LENGERR;
    }
    return 0;
}

/* GET DCOUNTER(qname) POOL(name1) VALUE(value) INCREMENT(inc) [WRAP] (IBM CICS TS, GET COUNTER and GET DCOUNTER; X30, X45): the
 * value before the increment is written big-endian (unsigned doubleword) into `value`, after which the counter is the
 * increment more; `wrap` is WRAP. See counter_step for the limits. As CicsTask.getCounter(pool, name, increment, wrap). */
int GGCGDCN(gg_cics *c, unsigned char *value, int valuelen, unsigned char *inc, int inclen, int wrap) {
    char want[17], pool[9], shown[9];
    counter_row rows[MAXCNT];
    unsigned long long incr = 0;
    int i;
    counter_names(c, want, pool, shown);
    int bad = counter_name_resp2(shown, want);
    if (inclen > 8 || valuelen != 8) refuse("GET DCOUNTER with a VALUE or INCREMENT that is not a doubleword");
    for (i = 0; i < inclen; i++) incr = incr * 256 + inc[i];
    if (incr == 0) refuse("GET COUNTER with an INCREMENT not above zero");
    int n = counters_read(rows), at = bad ? -1 : counter_find(rows, n, pool, want);
    c->resp = NORMAL;
    c->resp2 = 0;
    if (bad) {
        c->resp = INVREQ;
        c->resp2 = bad;
    } else if (at < 0) {
        c->resp = INVREQ;
        c->resp2 = 201;
    } else {
        unsigned long long v;
        if (counter_step(&rows[at], incr, wrap, &v)) {
            c->resp = SUPPRESSED;
            c->resp2 = 101;
            return 0;
        }
        for (i = 7; i >= 0; i--) { value[i] = (unsigned char)(v & 255); v >>= 8; }
        counters_write(rows, n);
    }
    return 0;
}

static unsigned long long be64(const unsigned char *p, int len) {
    unsigned long long v = 0;
    for (int i = 0; i < len; i++) v = v * 256 + p[i];
    return v;
}

static void put64(unsigned char *p, unsigned long long v) {
    for (int i = 7; i >= 0; i--) { p[i] = (unsigned char)(v & 255); v >>= 8; }
}

/* GET COUNTER / DCOUNTER with REDUCE, COMPAREMIN, COMPAREMAX (#5039, register X53; IBM, EXEC CICS GET COUNTER and GET DCOUNTER):
 * as GGCGCNT / GGCGDCN with `reduce` and the bounds, each an area of the counter's width (length 0: not given). SUPPRESSED RESP2 103
 * when the value handed out is out of range. As CicsTask.getCounter(pool, name, increment, wrap, reduce, cmpMin, cmpMax, fullword). */
static int get_counter_x(gg_cics *c, int width, unsigned char *value, int valuelen, unsigned char *inc, int inclen, int wrap, int reduce,
                         unsigned char *cmin, int cminlen, unsigned char *cmax, int cmaxlen) {
    char want[17], pool[9], shown[9];
    counter_row rows[MAXCNT];
    counter_names(c, want, pool, shown);
    int bad = counter_name_resp2(shown, want);
    if (width == 4 && inclen == 8 && be64(inc, 8) <= 4294967295ULL) {
        inc += 4;
        inclen = 4;
    }
    if (inclen > width || valuelen != width || cminlen > width || cmaxlen > width) refuse("GET COUNTER with a VALUE, INCREMENT or compare value that is not the counter's width");
    unsigned long long incr = be64(inc, inclen);
    if (incr == 0) refuse("GET COUNTER with an INCREMENT not above zero");
    int n = counters_read(rows), at = bad ? -1 : counter_find(rows, n, pool, want);
    c->resp = NORMAL;
    c->resp2 = 0;
    if (bad) {
        c->resp = INVREQ;
        c->resp2 = bad;
    } else if (at < 0) {
        c->resp = INVREQ;
        c->resp2 = 201;
    } else {
        unsigned long long v;
        int st = counter_step_x(&rows[at], incr, wrap, reduce, cminlen > 0, be64(cmin, cminlen), cmaxlen > 0, be64(cmax, cmaxlen), width == 4, &v);
        if (st) {
            c->resp = SUPPRESSED;
            c->resp2 = st == 1 ? 101 : 103;
            return 0;
        }
        unsigned long long got = v;
        for (int i = width - 1; i >= 0; i--) { value[i] = (unsigned char)(v & 255); v >>= 8; }
        counters_write(rows, n);
        if (width == 4 && (c->resp2 = counter_lengerr(&rows[at], got))) c->resp = LENGERR;
    }
    return 0;
}

int GGCGCNX(gg_cics *c, unsigned char *value, int valuelen, unsigned char *inc, int inclen, int wrap, int reduce,
            unsigned char *cmin, int cminlen, unsigned char *cmax, int cmaxlen) {
    return get_counter_x(c, 4, value, valuelen, inc, inclen, wrap, reduce, cmin, cminlen, cmax, cmaxlen);
}

int GGCGDCX(gg_cics *c, unsigned char *value, int valuelen, unsigned char *inc, int inclen, int wrap, int reduce,
            unsigned char *cmin, int cminlen, unsigned char *cmax, int cmaxlen) {
    return get_counter_x(c, 8, value, valuelen, inc, inclen, wrap, reduce, cmin, cminlen, cmax, cmaxlen);
}

/* REWIND COUNTER / DCOUNTER(qname) POOL(name1) INCREMENT(inc) (#5039, X53; IBM, EXEC CICS REWIND COUNTER and REWIND DCOUNTER): a
 * counter that has reached its limit (MAXIMUM + 1, where a GET leaves it) is reset to its minimum; SUPPRESSED RESP2 102 for one
 * that has not; INVREQ 406 for an INCREMENT beyond (maximum - minimum) + 1; 201 / 403 / 404. `inc` length 0: INCREMENT omitted (1).
 * Refused, as CicsTask.rewindCounter: an INCREMENT of zero or above 1 within the range, a counter with no limits. */
static int rewind_counter(gg_cics *c, int width, unsigned char *inc, int inclen) {
    char want[17], pool[9], shown[9];
    counter_row rows[MAXCNT];
    counter_names(c, want, pool, shown);
    int bad = counter_name_resp2(shown, want);
    if (inclen > width) refuse("REWIND COUNTER with an INCREMENT that is not the counter's width");
    unsigned long long incr = inclen ? be64(inc, inclen) : 1;
    c->resp = NORMAL;
    c->resp2 = 0;
    if (bad) {
        c->resp = INVREQ;
        c->resp2 = bad;
        return 0;
    }
    if (incr == 0) refuse("REWIND COUNTER with an INCREMENT not above zero");
    int n = counters_read(rows), at = counter_find(rows, n, pool, want);
    if (at < 0) {
        c->resp = INVREQ;
        c->resp2 = 201;
        return 0;
    }
    counter_row *r = &rows[at];
    if (!r->limited) refuse("REWIND COUNTER of a counter whose limits the run does not state");
    unsigned long long range = r->max - r->min + 1; /* 0: a full doubleword, which no INCREMENT exceeds */
    if (range != 0 && incr > range) {
        c->resp = INVREQ;
        c->resp2 = 406;
        return 0;
    }
    if (incr != 1) refuse("REWIND COUNTER with an INCREMENT above 1");
    if (r->max == ~0ULL || r->value <= r->max) {
        c->resp = SUPPRESSED;
        c->resp2 = 102;
        return 0;
    }
    r->value = r->min;
    counters_write(rows, n);
    return 0;
}

int GGCRCNT(gg_cics *c, unsigned char *inc, int inclen) { return rewind_counter(c, 4, inc, inclen); }
int GGCRDCN(gg_cics *c, unsigned char *inc, int inclen) { return rewind_counter(c, 8, inc, inclen); }

/* UPDATE COUNTER / DCOUNTER(qname) POOL(name1) VALUE(val) (#5039, X53; IBM, EXEC CICS UPDATE COUNTER and UPDATE DCOUNTER): the new
 * current value; INVREQ 406 for a VALUE below MINIMUM or above MAXIMUM + 1; 201 / 403 / 404. Refused, as CicsTask.updateCounter: a
 * negative fullword VALUE, a counter with no limits. */
static int update_counter(gg_cics *c, int width, unsigned char *val, int vallen) {
    char want[17], pool[9], shown[9];
    counter_row rows[MAXCNT];
    counter_names(c, want, pool, shown);
    int bad = counter_name_resp2(shown, want);
    if (vallen != width) refuse("UPDATE COUNTER with a VALUE that is not the counter's width");
    unsigned long long value = be64(val, vallen);
    c->resp = NORMAL;
    c->resp2 = 0;
    if (bad) {
        c->resp = INVREQ;
        c->resp2 = bad;
        return 0;
    }
    if (width == 4 && ((value >> 31) & 1)) refuse("UPDATE COUNTER with a VALUE below zero");
    int n = counters_read(rows), at = counter_find(rows, n, pool, want);
    if (at < 0) {
        c->resp = INVREQ;
        c->resp2 = 201;
        return 0;
    }
    counter_row *r = &rows[at];
    if (!r->limited) refuse("UPDATE COUNTER of a counter whose limits the run does not state");
    if (value < r->min || (r->max != ~0ULL && value > r->max + 1)) {
        c->resp = INVREQ;
        c->resp2 = 406;
        return 0;
    }
    r->value = value;
    counters_write(rows, n);
    return 0;
}

int GGCUCNT(gg_cics *c, unsigned char *val, int vallen) { return update_counter(c, 4, val, vallen); }
int GGCUDCN(gg_cics *c, unsigned char *val, int vallen) { return update_counter(c, 8, val, vallen); }

/* DEFINE DCOUNTER(qname) POOL(name1) VALUE MINIMUM MAXIMUM (#4770, register X45; IBM, EXEC CICS DEFINE COUNTER and DEFINE
 * DCOUNTER): unsigned doublewords, each area passed with its length (0: omitted -- IBM's defaults MINIMUM zero, MAXIMUM a doubleword
 * of X'FF', VALUE zero). INVREQ 407 when MAXIMUM is below MINIMUM, 406 when VALUE is below MINIMUM or above MAXIMUM + 1 (checked
 * before 202, 403 / 404 first: the page gives no order), 202 for a duplicate. As CicsTask.defineDcounter. */
int GGCDDCN(gg_cics *c, unsigned char *val, int vallen, unsigned char *lo, int lolen, unsigned char *hi, int hilen) {
    char want[17], pool[9], shown[9];
    counter_row rows[MAXCNT];
    counter_names(c, want, pool, shown);
    int bad = counter_name_resp2(shown, want);
    int n = counters_read(rows);
    if (vallen > 8 || lolen > 8 || hilen > 8) refuse("DEFINE DCOUNTER with a VALUE, MINIMUM or MAXIMUM that is not a doubleword");
    unsigned long long v = vallen ? be64(val, vallen) : 0, mn = lolen ? be64(lo, lolen) : 0, mx = hilen ? be64(hi, hilen) : ~0ULL;
    c->resp = NORMAL;
    c->resp2 = 0;
    if (bad) {
        c->resp = INVREQ;
        c->resp2 = bad;
    } else if (mx < mn) {
        c->resp = INVREQ;
        c->resp2 = 407;
    } else if (v < mn || (mx != ~0ULL && v > mx + 1)) {
        c->resp = INVREQ;
        c->resp2 = 406;
    } else if (counter_find(rows, n, pool, want) >= 0) {
        c->resp = INVREQ;
        c->resp2 = 202;
    } else if (n >= MAXCNT) {
        refuse("DEFINE COUNTER past the stub's 64 counters");
    } else {
        snprintf(rows[n].pool, sizeof rows[n].pool, "%s", pool);
        snprintf(rows[n].name, sizeof rows[n].name, "%s", want);
        rows[n].value = v;
        rows[n].limited = 1;
        rows[n].min = mn;
        rows[n].max = mx;
        counters_write(rows, n + 1);
    }
    return 0;
}

/* QUERY DCOUNTER(qname) POOL(name1) VALUE MINIMUM MAXIMUM (#4770, X45): the counter's value and limits, unsigned doublewords
 * written big-endian into the areas given (length 0: not asked for); the value is unchanged. MINIMUM / MAXIMUM of a counter with no
 * limits are refused. As CicsTask.queryDcounter. */
int GGCQDCN(gg_cics *c, unsigned char *val, int vallen, unsigned char *lo, int lolen, unsigned char *hi, int hilen) {
    char want[17], pool[9], shown[9];
    counter_row rows[MAXCNT];
    counter_names(c, want, pool, shown);
    int bad = counter_name_resp2(shown, want);
    int n = counters_read(rows), at = bad ? -1 : counter_find(rows, n, pool, want);
    if ((vallen && vallen != 8) || (lolen && lolen != 8) || (hilen && hilen != 8))
        refuse("QUERY DCOUNTER with a VALUE, MINIMUM or MAXIMUM that is not a doubleword");
    c->resp = NORMAL;
    c->resp2 = 0;
    if (bad) {
        c->resp = INVREQ;
        c->resp2 = bad;
    } else if (at < 0) {
        c->resp = INVREQ;
        c->resp2 = 201;
    } else {
        if ((lolen || hilen) && !rows[at].limited)
            refuse("QUERY DCOUNTER MINIMUM / MAXIMUM of a counter whose limits the run does not state");
        if (vallen) put64(val, rows[at].value);
        if (lolen) put64(lo, rows[at].min);
        if (hilen) put64(hi, rows[at].max);
    }
    return 0;
}

/* QUERY COUNTER(qname) POOL(name1) VALUE MINIMUM MAXIMUM (IBM CICS TS, EXEC CICS QUERY COUNTER; #4415 slice 2, X29; #5039, X50):
 * the named counter's value and limits, signed fullwords written big-endian into the areas given (length 0: not asked for);
 * the value is unchanged. A counter not there is INVREQ RESP2 201 "Named counter not found". MINIMUM / MAXIMUM of a counter with
 * no limits, and limits beyond a fullword, are refused; a value beyond a fullword is IBM's LENGERR (#4770, X30): RESP2 1 / 2 / 3, the
 * low 32 bits written. As CicsTask.queryCounter. */
int GGCQCNT(gg_cics *c, unsigned char *val, int vallen, unsigned char *lo, int lolen, unsigned char *hi, int hilen) {
    char want[17], pool[9], shown[9];
    counter_row rows[MAXCNT];
    counter_names(c, want, pool, shown);
    int bad = counter_name_resp2(shown, want);
    int n = counters_read(rows), at = bad ? -1 : counter_find(rows, n, pool, want);
    if ((vallen && vallen != 4) || (lolen && lolen != 4) || (hilen && hilen != 4))
        refuse("QUERY COUNTER with a VALUE, MINIMUM or MAXIMUM that is not a fullword");
    c->resp = NORMAL;
    c->resp2 = 0;
    if (bad) {
        c->resp = INVREQ;
        c->resp2 = bad;
    } else if (at < 0) {
        c->resp = INVREQ;
        c->resp2 = 201;
    } else {
        if ((lolen || hilen) && !rows[at].limited)
            refuse("QUERY COUNTER MINIMUM / MAXIMUM of a counter whose limits the run does not state");
        if ((lolen && rows[at].min > 2147483647ULL) || (hilen && rows[at].max > 2147483647ULL))
            refuse("QUERY COUNTER MINIMUM / MAXIMUM of a counter whose limits are beyond a fullword");
        if ((c->resp2 = counter_lengerr(&rows[at], rows[at].value))) c->resp = LENGERR;
        if (vallen) put32(val, rows[at].value);
        if (lolen) put32(lo, rows[at].min);
        if (hilen) put32(hi, rows[at].max);
    }
    return 0;
}

/* DEFINE COUNTER(qname) POOL(name1) VALUE MINIMUM MAXIMUM (#4270, register X30; #5039, X50; IBM, EXEC CICS DEFINE COUNTER):
 * fullwords, each area passed with its length (0: omitted -- IBM's defaults MINIMUM zero, MAXIMUM X'7FFFFFFF' = 2147483647,
 * VALUE zero). INVREQ 407 when MAXIMUM is below MINIMUM or beyond X'7FFFFFFF', 406 when VALUE is below MINIMUM or above MAXIMUM + 1,
 * 202 for a duplicate, 403 / 404 for a name outside IBM's rules (407 / 406 checked first: the page gives no order). A VALUE or
 * MINIMUM below zero is refused. As CicsTask.defineCounter. */
int GGCDCNT(gg_cics *c, unsigned char *val, int vallen, unsigned char *lo, int lolen, unsigned char *hi, int hilen) {
    char want[17], pool[9], shown[9];
    counter_row rows[MAXCNT];
    counter_names(c, want, pool, shown);
    int bad = counter_name_resp2(shown, want);
    int n = counters_read(rows);
    if (vallen > 4 || lolen > 4 || hilen > 4) refuse("DEFINE COUNTER with a VALUE, MINIMUM or MAXIMUM that is not a fullword");
    c->resp = NORMAL;
    c->resp2 = 0;
    if (bad) {
        c->resp = INVREQ;
        c->resp2 = bad;
        return 0;
    }
    if (vallen && (val[0] & 0x80)) refuse("DEFINE COUNTER with a VALUE below zero");
    if (lolen && (lo[0] & 0x80)) refuse("DEFINE COUNTER with a MINIMUM below zero");
    unsigned long long v = vallen ? be64(val, vallen) : 0;
    unsigned long long mn = lolen ? be64(lo, lolen) : 0;
    unsigned long long mx = hilen ? be64(hi, hilen) : 2147483647ULL;
    if (mx < mn || mx > 2147483647ULL) {
        c->resp = INVREQ;
        c->resp2 = 407;
    } else if (v < mn || v > mx + 1) {
        c->resp = INVREQ;
        c->resp2 = 406;
    } else if (counter_find(rows, n, pool, want) >= 0) {
        c->resp = INVREQ;
        c->resp2 = 202;
    } else if (n >= MAXCNT) {
        refuse("DEFINE COUNTER past the stub's 64 counters");
    } else {
        snprintf(rows[n].pool, sizeof rows[n].pool, "%s", pool);
        snprintf(rows[n].name, sizeof rows[n].name, "%s", want);
        rows[n].value = v;
        rows[n].limited = 1;
        rows[n].min = mn;
        rows[n].max = mx;
        counters_write(rows, n + 1);
    }
    return 0;
}

/* DELETE COUNTER(qname) POOL(name1) (#4270, register X30; IBM, EXEC CICS DELETE COUNTER): the counter removed; INVREQ
 * RESP2 201 "Named counter not found" (the page lists no NOTFND), 403 for a pool outside IBM's rules. */
int GGCXCNT(gg_cics *c) {
    char want[17], pool[9], shown[9];
    counter_row rows[MAXCNT];
    counter_names(c, want, pool, shown);
    int bad = counter_name_resp2(shown, want);
    int n = counters_read(rows), at = bad == 403 ? -1 : counter_find(rows, n, pool, want);
    c->resp = NORMAL;
    c->resp2 = 0;
    if (bad == 403) {
        c->resp = INVREQ;
        c->resp2 = 403;
    } else if (at < 0) {
        c->resp = INVREQ;
        c->resp2 = 201;
    } else {
        for (int i = at; i + 1 < n; i++) rows[i] = rows[i + 1];
        counters_write(rows, n - 1);
    }
    return 0;
}

/* ---- #4270 zECS: INQUIRE URIMAP's browse, WRITE OPERATOR (IBM CICS TS, INQUIRE URIMAP, "Browsing resource definitions",
 * WRITE OPERATOR; register X32) ----
 * The URIMAP definitions installed in the region, in the order it browses them, are a fact the runner states: the file
 * $GGCICS_URIMAPS names, one `NAME TRANSACTION PATH` per line ('-' for no transaction); unstated, refused. GG-FLAGS names
 * the browse step: START (ILLOGIC RESP2 1 when one is already in progress), NEXT (END RESP2 2 past the last; the
 * definition it returns is read by GGCURIP) or END. NEXT / END with no browse started are refused: IBM gives that ILLOGIC
 * no RESP2 of its own. #4768 (X34): DIRECT, the direct form INQUIRE URIMAP(name): the definition GG-NAME1 names, read by
 * GGCURIP as NEXT's; NOTFND RESP2 3 when it is not installed. */
static int urimap_at = -1; /* -1: no browse; else the next definition's index */
static char urimap_now[3][300];
