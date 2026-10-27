/* #5274: the faults family -- the planned-fault state and lookup (faults.cfg: injected_at, the injected() macro, DUPKEY held back
 * by dupkey_apply), the ABM0 map check and the AD2Z marker GGCSQLAB -- split out of ggcics.c, which includes it where the
 * state sat. It includes nothing itself: ggcics.c supplies the headers, trim(), dir_in() and dir_out() above the include. */
/* #4023 follow-up: the planned condition of this command on this file, if faults.cfg plans one. Every
 * command counts (per task: a task is one process), whether or not it faults. */
static int fault_counts[32];
static char fault_keys[32][40];
/* #4623: a planned DUPKEY is not a failure of the read. IBM retrieves the record through the non-unique alternate
 * index and answers DUPKEY (RESP2 140) because another record with the same key follows. So injected() holds it
 * back (the read runs) and dupkey_apply() turns the NORMAL of a read that found its record into it. */
static struct { int on, n, resp, resp2; char cmd[16], file[32]; } dupkey;
/* #6271 (X70): a planned ABEND line (`CMD FILE NTH ABEND 0 ABCODE`, RESP field -1) is not a condition: the command
 * abends the task with ABCODE (cause "system", an abend CICS itself raises), so the HANDLE ABEND exit gets control (c->go_to)
 * or the task ends, and the command does nothing else (RESP / RESP2 NORMAL). Every call site has the task's `c`. */
static void abend(gg_cics *c, const char *code, const char *cause, int cond, int cancel);
static int injected_at(gg_cics *c, const char *cmd, const char *file, int *resp, int *resp2);
#define injected(cmd, file, resp, resp2) injected_at(c, cmd, file, resp, resp2)
static int injected_at(gg_cics *c, const char *cmd, const char *file, int *resp, int *resp2) {
    char path[3000], line[256], pcmd[16], pfile[32], nth[16], pcode[16];
    int presp, presp2, n = 0, slot = -1, hit = 0;
    char key[40];
    snprintf(key, sizeof key, "%.15s %.16s", cmd, file);
    for (int i = 0; i < 32; i++) {
        if (fault_keys[i][0] == 0 || strcmp(fault_keys[i], key) == 0) { slot = i; break; }
    }
    if (slot < 0) return 0;
    if (fault_keys[slot][0] == 0) snprintf(fault_keys[slot], sizeof fault_keys[slot], "%s", key);
    n = ++fault_counts[slot];
    dupkey.on = 0;
    snprintf(path, sizeof path, "%s/faults.cfg", dir_in());
    FILE *f = fopen(path, "r");
    while (f && !hit && fgets(line, sizeof line, f)) {
        presp2 = 0;
        pcode[0] = '\0';
        if (sscanf(line, "%15s %31s %15s %d %d %15s", pcmd, pfile, nth, &presp, &presp2, pcode) < 4) continue;
        if (strcmp(pcmd, cmd) != 0 || strcmp(pfile, file) != 0) continue;
        if (nth[0] != '*' && atoi(nth) != n) continue;
        *resp = presp;
        *resp2 = presp2;
        hit = 1;
        if (presp == -1 && pcode[0]) {
            char code[5] = "    ";
            memcpy(code, pcode, strlen(pcode) < 4 ? strlen(pcode) : 4);
            snprintf(path, sizeof path, "%s/faults.txt", dir_out());
            FILE *log = fopen(path, "a");
            if (log) { fprintf(log, "%s %s %d ABEND %s\n", cmd, file, n, pcode); fclose(log); }
            *resp = NORMAL;
            *resp2 = 0;
            fclose(f);
            abend(c, code, "system", 0, 0);
            return 1;
        }
    }
    if (f) fclose(f);
    if (hit && *resp == DFHRESP_DUPKEY) {
        dupkey.on = 1; dupkey.n = n; dupkey.resp = *resp; dupkey.resp2 = *resp2;
        snprintf(dupkey.cmd, sizeof dupkey.cmd, "%s", cmd);
        snprintf(dupkey.file, sizeof dupkey.file, "%s", file);
        return 0;
    }
    if (hit) {
        snprintf(path, sizeof path, "%s/faults.txt", dir_out());
        FILE *log = fopen(path, "a");
        if (log) { fprintf(log, "%s %s %d %d %d\n", cmd, file, n, *resp, *resp2); fclose(log); }
    }
    return hit;
}

static void dupkey_apply(gg_cics *c) {
    if (!dupkey.on) return;
    dupkey.on = 0;
    if (c->resp != NORMAL) return;  /* no record was retrieved: nothing for DUPKEY to qualify */
    c->resp = dupkey.resp;
    c->resp2 = dupkey.resp2;
    char path[3000];
    snprintf(path, sizeof path, "%s/faults.txt", dir_out());
    FILE *log = fopen(path, "a");
    if (log) { fprintf(log, "%s %s %d %d %d\n", dupkey.cmd, dupkey.file, dupkey.n, c->resp, c->resp2); fclose(log); }
}

/* #4270 (X31): SEND MAP / RECEIVE MAP for a map the mapset does not hold. IBM CICS TS, abend ABM0: "The map specified for
 * a basic mapping support (BMS) request could not be located"; "The transaction is abnormally terminated with a CICS
 * transaction dump". Neither command lists a condition for it, so RESP / HANDLE CONDITION do not see it (a HANDLE ABEND
 * exit does). The mapsets and their maps are a fact the run states, $GGCICS_MAPSETS = `MAPSET=MAP,MAP;MAPSET=MAP`
 * (the cics-crucible runner takes them from the case's maps); a mapset not stated is not checked. 1: the task
 * abended -- c->go_to says where to go on (an exit label at this level, else -1: leave the program). */

static int map_not_found(gg_cics *c, const char *map, const char *mapset) {
    const char *env = getenv("GGCICS_MAPSETS");
    size_t ml = strlen(mapset), nl = strlen(map);
    c->go_to = 0;
    for (const char *p = env; p && *p;) {
        const char *end = strchr(p, ';');
        size_t len = end ? (size_t)(end - p) : strlen(p);
        if (len > ml && strncmp(p, mapset, ml) == 0 && p[ml] == '=') {
            int held = 0;
            for (const char *q = p + ml + 1; q < p + len;) {
                const char *comma = memchr(q, ',', (size_t)(p + len - q));
                size_t n = comma ? (size_t)(comma - q) : (size_t)(p + len - q);
                if (n == nl && strncmp(q, map, nl) == 0) held = 1;
                q += n + 1;
            }
            if (held) return 0;
            abend(c, "ABM0", "system", 0, 0);
            return 1;
        }
        p = end ? end + 1 : NULL;
    }
    return 0;
}

/* #6271 (X73): the marker the harness plants after a Db2 statement a scenario plans an AD2Z abend for (GG-FLAGS = PROGRAM:LINE,
 * the SQL fault's own key). IBM: a deadlock (-911) makes the CICS-Db2 attach attempt a syncpoint rollback, which fails, and the
 * task abends AD2Z. A planned `SQL PROGRAM:LINE NTH -1 0 AD2Z` line abends the task here (injected_at); no line, no effect. */
int GGCSQLAB(gg_cics *c) {
    char key[41];
    int fresp, fresp2;
    c->resp = NORMAL;
    c->resp2 = 0;
    trim(c->flags, 40, key);
    injected("SQL", key, &fresp, &fresp2);
    return 0;
}
