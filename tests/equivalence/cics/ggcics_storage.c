/* #5274: the storage block: GETMAIN, FREEMAIN, LOAD, RELEASE, BLL cells and ADDRESS -- split out of ggcics.c, which includes it here. */
/* Where the platform cannot place a block low (macOS arm64 reserves the low 4 GiB; its mmap with MAP_32BIT fails) the block comes
 * from calloc: GETMAIN still answers, only a 4-byte copy of the address is then not the address. GGCICS_NO_LOW_BLOCKS forces that. */
static void *blk_alloc(size_t n) {
#if defined(GGCICS_NO_LOW_BLOCKS)
    return calloc(n, 1);
#elif defined(_WIN32)
    static size_t cursor = 0x10000000U; /* zero-filled; the 64 KiB allocation granularity is the step */
    size_t step = 0x10000U, size = (n + step - 1) / step * step, at;
    void *p;
    if (size < 0x60000000U) {
        for (at = cursor; at + size < 0x7ff00000U; at += step) {
            p = VirtualAlloc((void *)at, n, 0x3000UL /* MEM_COMMIT | MEM_RESERVE */, 0x04UL /* PAGE_READWRITE */);
            if (p) { cursor = at + size; return p; }
        }
    }
    return calloc(n, 1);
#elif defined(MAP_32BIT)
    void *p = mmap(NULL, n, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_32BIT, -1, 0);
    return p == MAP_FAILED ? calloc(n, 1) : p;
#else
    return calloc(n, 1);
#endif
}

static void *blk_new(size_t n, int kind) {
    void *p;
    if (nblks >= 8192) refuse("more than 8192 blocks of task storage");
    p = blk_alloc(n ? n : 1);
    if (!p) refuse("GETMAIN length beyond the limit");
    blks[nblks].p = p;
    blks[nblks].kind = kind;
    blks[nblks].n = n;
    blks[nblks].key[0] = '\0';
    nblks++;
    return p;
}

/* #6839: the bytes from `p` to the end of the live GETMAIN / received block that holds it (0: no block does). A WEB command reads
 * its FROM / PATH / QUERY from the address, so a record SET onto a larger block may carry a length past its declared area (IBM). */
static size_t blk_room(const void *p) {
    for (int i = 0; i < nblks; i++) {
        if (blks[i].kind != BLK_FREED && (const char *)p >= (const char *)blks[i].p
            && (const char *)p < (const char *)blks[i].p + blks[i].n)
            return (size_t)((const char *)blks[i].p + blks[i].n - (const char *)p);
    }
    return 0;
}

/* #5042 (register X58): ends the validity of the SET(ptr) blocks of `key`. IBM says only that the pointer is then "no longer
 * valid"; the storage reads as zeros through any record already addressing it (ASSUMED), as CicsTask.invalidateSet. */
static void blk_invalidate(const char *key) {
    for (int i = 0; key && i < nblks; i++) {
        if (blks[i].kind == BLK_RECEIVED && strcmp(blks[i].key, key) == 0) {
            memset(blks[i].p, 0, blks[i].n);
            blks[i].key[0] = '\0';
        }
    }
}

/* A SYNCPOINT ends the blocks IBM says it does (READ UPDATE SET, READNEXT / READPREV SET); as CicsTask.invalidateSyncSet. */
static void blk_invalidate_sync(void) {
    for (int i = 0; i < nblks; i++) {
        if (blks[i].kind == BLK_RECEIVED && blks[i].key[0] && blks[i].sync) {
            memset(blks[i].p, 0, blks[i].n);
            blks[i].key[0] = '\0';
        }
    }
}

static void blk_invalidate_prefix(const char *prefix) {
    for (int i = 0; i < nblks; i++) {
        if (blks[i].kind == BLK_RECEIVED && blks[i].key[0] && strncmp(blks[i].key, prefix, strlen(prefix)) == 0) {
            memset(blks[i].p, 0, blks[i].n);
            blks[i].key[0] = '\0';
        }
    }
}

static int blk_held(const char *key) {
    for (int i = 0; i < nblks; i++) {
        if (blks[i].kind == BLK_RECEIVED && blks[i].key[0] && strcmp(blks[i].key, key) == 0) return 1;
    }
    return 0;
}

/* A SET(ptr) block of RECEIVE, RETRIEVE, READQ TS, GET CONTAINER or a file read, holding the n bytes of `data`: the earlier one
 * of the same `key` ends first (a NULL key: valid to the task's end). As CicsTask.acquireSet. */
static void *blk_set_new(const char *key, const void *data, size_t n, int sync) {
    void *p;
    if (n > 268435456U) refuse("SET(ptr) data beyond the limit");
    blk_invalidate(key);
    p = blk_new(n, BLK_RECEIVED);
    memcpy(p, data, n);
    if (key) snprintf(blks[nblks - 1].key, sizeof blks[0].key, "%s", key);
    blks[nblks - 1].sync = sync;
    return p;
}

/* GETMAIN SET(ptr) FLENGTH / LENGTH INITIMG(byte) (IBM CICS TS, EXEC CICS GETMAIN): GG-NUM the length, GG-FLAGS "SHORT" for the
 * LENGTH form; LENGERR RESP2 1 for FLENGTH below 1 / LENGTH zero (ptr set to zero). Refused: a length above the limit, a LENGTH
 * above 65520, an INITIMG that is not one byte. No INITIMG (#6876, imglen 0; IBM: "There is no default initialization", the contents
 * are undefined): LENGERR as above, any valid length refused by name, as CicsTask.getmain. */
int GGCGETM(gg_cics *c, void **slot, char *img, int imglen) {
    char flags[41];
    long long n = c->num;
    trim(c->flags, 40, flags);
    if (imglen > 1) refuse("GETMAIN INITIMG is not one byte");
    c->resp = NORMAL;
    c->resp2 = 0;
    if (n < 1) { c->resp = LENGERR; c->resp2 = 1; *slot = NULL; return 0; }
    if (imglen == 0) refuse("GETMAIN without INITIMG acquired storage");
    if (n > 268435456LL || (strcmp(flags, "SHORT") == 0 && n > 65520)) refuse("GETMAIN length beyond the limit");
    *slot = blk_new((size_t)n, BLK_GETMAIN);
    memset(*slot, (unsigned char)img[0], (size_t)n);
    return 0;
}

/* LOAD PROGRAM(name1) [SET(ptr)] [LENGTH(halfword)] (#6876, X65; IBM, EXEC CICS LOAD): PGMIDERR RESP2 1 for a program the CSD does not
 * define (the pointer and LENGTH are not written); else the program is loaded by this task, the pointer takes the address of a
 * non-null image and LENGTH (GG-FLAGS LENGTH: the area is given) the image's length, a halfword written big-endian. IBM states no
 * image bytes or length, so a program that reads them is outside the proof. RELEASE PROGRAM(name1): PGMIDERR RESP2 1 for an undefined
 * program, INVREQ for one this task did not load, else NORMAL (IBM lists no other condition). */
#define LOADED_MAX 32
static char loaded[LOADED_MAX][9];
static char load_image[256];

int GGCLDPG(gg_cics *c, void **slot, unsigned char *len) {
    char program[9], flags[41];
    int i, free_at = -1;
    trim(c->name1, 8, program);
    trim(c->flags, 40, flags);
    c->resp = NORMAL;
    c->resp2 = 0;
    if (!program_defined(program)) { c->resp = PGMIDERR; c->resp2 = 1; return 0; }
    for (i = 0; i < LOADED_MAX; i++) {
        if (strcmp(loaded[i], program) == 0) { free_at = i; break; }
        if (free_at < 0 && loaded[i][0] == 0) free_at = i;
    }
    if (free_at < 0) refuse("LOAD of more than 32 programs at once");
    snprintf(loaded[free_at], sizeof loaded[free_at], "%s", program);
    if (strstr(flags, "SET") != NULL) *slot = load_image;
    if (strstr(flags, "LENGTH") != NULL) { len[0] = (unsigned char)(sizeof load_image >> 8); len[1] = (unsigned char)(sizeof load_image & 255); }
    return 0;
}

int GGCRLPG(gg_cics *c) {
    char program[9];
    int i;
    trim(c->name1, 8, program);
    c->resp = NORMAL;
    c->resp2 = 0;
    if (!program_defined(program)) { c->resp = PGMIDERR; c->resp2 = 1; return 0; }
    for (i = 0; i < LOADED_MAX; i++)
        if (strcmp(loaded[i], program) == 0) { loaded[i][0] = 0; return 0; }
    c->resp = INVREQ;
    return 0;
}

/* The release both FREEMAIN forms share: the block that starts at `addr`, INVREQ RESP2 1 when none does. */
static int free_block_at(gg_cics *c, void *addr) {
    int i;
    c->resp = NORMAL;
    c->resp2 = 0;
    for (i = 0; i < nblks; i++) {
        if (blks[i].p == addr) {
            if (blks[i].kind != BLK_GETMAIN) refuse("FREEMAIN of storage already freed or received");
            blks[i].kind = BLK_FREED;
            return 0;
        }
    }
    c->resp = INVREQ;
    c->resp2 = 1;
    return 0;
}

/* GGCPTRADV: `ADD|SUBTRACT n TO|FROM view` over the PIC S9(8) COMP view of a POINTER (#6839 slice 3, X47), lowered by
 * equivalence_cics_pointer.py. GnuCOBOL's POINTER is 8 bytes little-endian and the view 4 bytes big-endian, so the ADD on the
 * view itself corrupts the address. The pointer moves n bytes inside the block it addresses, as DetCics.advancePointer: a
 * null pointer, one no block holds, a freed block, or a result below the block's first byte or past its end (one past the
 * last byte is allowed) is refused. */
int GGCPTRADV(void **slot, int n) {
    unsigned char *at = (unsigned char *)*slot;
    int i, hit = -1;
    if (!at) refuse("pointer arithmetic on a null pointer");
    for (i = 0; i < nblks; i++)
        if (at >= (unsigned char *)blks[i].p && at < (unsigned char *)blks[i].p + blks[i].n) { hit = i; break; }
    for (i = 0; hit < 0 && i < nblks; i++)
        if (at == (unsigned char *)blks[i].p + blks[i].n) hit = i; /* one past the last byte */
    if (hit < 0) refuse("pointer arithmetic on an address no block of task storage holds");
    if (blks[hit].kind == BLK_FREED) refuse("pointer arithmetic on freed storage");
    at += n;
    if (at < (unsigned char *)blks[hit].p || at > (unsigned char *)blks[hit].p + blks[hit].n)
        refuse("pointer arithmetic leaves the storage the pointer addresses");
    *slot = at;
    return 0;
}

/* GGCFREM: FREEMAIN DATAPOINTER(ptr): INVREQ RESP2 1 for an address GETMAIN did not return (a null pointer, a record's address). Refused:
 * storage already freed, a WEB RECEIVE SET body (IBM does not say whether FREEMAIN is allowed). */
int GGCFREM(gg_cics *c, void **slot) {
    return free_block_at(c, *slot);
}

/* GGCFRED: FREEMAIN DATA(record) (#6876, X47): `area` is the LINKAGE record, whose address is the storage a SET ADDRESS OF gave it.
 * As GGCFREM for that address; refused besides: a record with no address (IBM: undefined), an address inside a GETMAIN block that is
 * not its start (IBM does not say what releasing the middle of a block does), as CicsTask.freemainData. */
int GGCFRED(gg_cics *c, void *area) {
    int i;
    if (area == NULL) refuse("FREEMAIN DATA of a record no pointer addresses");
    for (i = 0; i < nblks; i++) {
        if (blks[i].kind == BLK_GETMAIN && (char *)area > (char *)blks[i].p && (char *)area < (char *)blks[i].p + blks[i].n)
            refuse("FREEMAIN DATA of an address inside a GETMAIN block");
    }
    return free_block_at(c, area);
}

/* ---- #5119 (register X56): an OS/VS COBOL address held in data (a chained storage area's fullword). `MOVE cell TO fullword` is
 * CALL 'GGCBLLP' USING cell fullword, `MOVE fullword TO cell` CALL 'GGCBLLG' USING fullword cell. A real address does not fit a
 * fullword here, so the fullword holds a token (ASSUMED): 0 for NULL, the n-th distinct address moved into data n * 65536 (at most
 * 1525: 8 digits), 4 bytes big-endian, numbered as CicsTask.bllToken. A block is never reused (blk_new), so one address is one block. */
static void *bll_tok[1525];
static int nbll_tok = 0;

int GGCBLLP(void **cell, unsigned char *data) {
    unsigned int v = 0;
    int i;
    if (*cell) {
        for (i = 0; i < nbll_tok && bll_tok[i] != *cell; i++) {
        }
        if (i == nbll_tok) {
            if (nbll_tok >= 1525) refuse("more than 1525 BLL addresses held in data");
            bll_tok[nbll_tok++] = *cell;
        }
        v = (unsigned int)(i + 1) * 65536U;
    }
    for (i = 3; i >= 0; i--) {
        data[i] = (unsigned char)(v & 0xFF);
        v >>= 8;
    }
    return 0;
}

int GGCBLLG(unsigned char *data, void **cell) {
    long long v = (long long)(signed char)data[0];
    int i;
    for (i = 1; i < 4; i++) v = (v << 8) | data[i];
    if (v == 0) {
        *cell = NULL;
        return 0;
    }
    if (v < 0 || v % 65536 != 0 || v / 65536 > nbll_tok) refuse("an address in data that no BLL cell gave");
    *cell = bll_tok[v / 65536 - 1];
    return 0;
}

/* #5079 slice 2b (X59): the TWA (TRANSACTION TWASIZE, $GGCICS_TWASIZE) is the task's: one zeroed block every program it LINKs to
 * addresses; the TCTUA (TYPETERM USERAREALEN, $GGCICS_USERAREALEN) is the terminal's, so its bytes live in the file $GGCICS_TCTUA that
 * each task reads when it first addresses the area and writes back as it ends. An area of size 0 or unstated is IBM's X'FF000000':
 * the pointer's first four bytes (little-endian 0xFF), so a program's PIC X(4) view of it compares equal. IBM does not state the
 * initial content: zeros, as the port. */
static char *twa_area, *tctua_area, *cwa_area;
static long tctua_len, cwa_len;

static long env_size(const char *name) {
    const char *v = getenv(name);
    long n = v ? atol(v) : 0;
    return n > 0 ? n : 0;
}

static void tctua_save(void) {
    const char *path = getenv("GGCICS_TCTUA");
    FILE *f = path && tctua_area ? fopen(path, "wb") : NULL;
    if (f) { fwrite(tctua_area, 1, (size_t)tctua_len, f); fclose(f); }
}

static void cwa_save(void) {
    const char *path = getenv("GGCICS_CWA");
    FILE *f = path && cwa_area ? fopen(path, "wb") : NULL;
    if (f) { fwrite(cwa_area, 1, (size_t)cwa_len, f); fclose(f); }
}

static void *system_area(const char *kind) {
    if (strcmp(kind, "CWA") == 0) {  /* #5079 slice 2b: SIT WRKAREA ($GGCICS_WRKAREA); one area for the region, so its bytes live in $GGCICS_CWA */
        long n = env_size("GGCICS_WRKAREA");
        const char *path = getenv("GGCICS_CWA");
        if (n == 0 || !path) return (void *)(size_t)0xFF;
        if (!cwa_area) {
            FILE *f = fopen(path, "rb");
            cwa_len = n;
            cwa_area = calloc((size_t)n, 1);
            if (f) { size_t got = fread(cwa_area, 1, (size_t)n, f); (void)got; fclose(f); }
            atexit(cwa_save);
        }
        return cwa_area;
    }
    if (strcmp(kind, "TWA") == 0) {
        long n = env_size("GGCICS_TWASIZE");
        if (n == 0) return (void *)(size_t)0xFF;
        if (!twa_area) twa_area = calloc((size_t)n, 1);
        return twa_area;
    }
    long n = env_size("GGCICS_USERAREALEN");
    const char *path = getenv("GGCICS_TCTUA");
    if (n == 0 || !path) return (void *)(size_t)0xFF;
    if (!tctua_area) {
        FILE *f = fopen(path, "rb");
        tctua_len = n;
        tctua_area = calloc((size_t)n, 1);
        if (f) { size_t got = fread(tctua_area, 1, (size_t)n, f); (void)got; fclose(f); }
        atexit(tctua_save);
    }
    return tctua_area;
}

/* GGCADDR: ADDRESS EIB(ptr) | COMMAREA(ptr) | CWA(ptr) | TWA(ptr) | TCTUA(ptr) (X59). `area` is the EIB or the program's DFHCOMMAREA; the pointer
 * takes its address (NORMAL: the command has no condition). GG-FLAGS COMMAREA with GG-NUM (EIBCALEN) 0: refused -- IBM sets X'FF000000',
 * which is no COBOL NULL, and a LINKAGE item the caller did not pass names no storage. GG-FLAGS CWA / TWA / TCTUA: the system area (`area`
 * is unused). */
int GGCADDR(gg_cics *c, void **slot, void *area) {
    char flags[41];
    trim(c->flags, 40, flags);
    c->resp = NORMAL;
    c->resp2 = 0;
    if (strstr(flags, "COMMAREA") != NULL && c->num == 0) refuse("ADDRESS COMMAREA with no COMMAREA");
    if (strstr(flags, "CWA") != NULL) { *slot = system_area("CWA"); return 0; }
    if (strstr(flags, "TCTUA") != NULL) { *slot = system_area("TCTUA"); return 0; }
    if (strstr(flags, "TWA") != NULL) { *slot = system_area("TWA"); return 0; }
    *slot = area;
    return 0;
}

#define GGCICS_WEB_PART2
#include "ggcics_web.c"  /* #5274: the web family, part 2 (WEB RECEIVE SET) */
#undef GGCICS_WEB_PART2

/* ---- #5042 (register X58): SET(ptr) on RECEIVE, RETRIEVE, READQ TS, GET CONTAINER and the file reads. Each answers as its INTO form
 * does (the same conditions and events), then, where data was delivered, puts a copy in a new block the pointer addresses
 * (blk_set_new; the key says what ends the pointer, as CicsTask.acquireSet). Where nothing was delivered the pointer is as it was
 * (ASSUMED: IBM does not say). */
