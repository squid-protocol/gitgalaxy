/*
 * ggfault.c -- the equivalence harness's file-status fault injector for GnuCOBOL (#4023 follow-up).
 *
 * Preloaded (LD_PRELOAD) into a GnuCOBOL program, it stands in front of libcob's file I/O entry points.
 * GGFAULT_PLAN names a plan file, one fault per line:
 *
 *     <DD> <OP> <NTH> <STATUS>        e.g.  XREFFILE READ 2 23
 *
 * DD is the file's ASSIGN name, OP one of OPEN CLOSE READ WRITE REWRITE DELETE START (READ counts random and
 * sequential READs alike), NTH the occurrence of that operation on that file (1 = the first; `*` = every one),
 * STATUS the two-character FILE STATUS to give it. The planned operation is NOT performed: it only returns
 * its status -- the file's FILE STATUS field and libcob's I/O exception (AT END for 1x, INVALID KEY for 2x,
 * PERMANENT ERROR for 3x, LOGIC ERROR for 4x, implementor-defined for 9x) are set as libcob sets them for a
 * real failure, so the program's own FILE STATUS tests, AT END / INVALID KEY phrases and error handling run.
 * The Java side (the generated CobolFiles) reads the same plan with the same meaning.
 *
 * GGFAULT_LOG names a file each fault that fires is appended to (`<DD> <OP> <NTH> <STATUS>`): a planned fault
 * the run never reaches is a scenario that tested nothing, and the harness reports it.
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <libcob.h>

#define MAX_FAULTS 64

static struct {
    char dd[32];
    char op[8];
    int nth; /* 0: every occurrence */
    char status[3];
    int seen;
} plan[MAX_FAULTS];
static int planned = -1;

static void load_plan(void) {
    if (planned >= 0) {
        return;
    }
    planned = 0;
    const char *path = getenv("GGFAULT_PLAN");
    FILE *f = path ? fopen(path, "r") : NULL;
    char nth[16];
    while (f && planned < MAX_FAULTS &&
           fscanf(f, "%31s %7s %15s %2s", plan[planned].dd, plan[planned].op, nth, plan[planned].status) == 4) {
        plan[planned].nth = nth[0] == '*' ? 0 : atoi(nth);
        plan[planned].seen = 0;
        planned++;
    }
    if (f) {
        fclose(f);
    }
}

/* The file's ASSIGN name (the DD), blanks trimmed. */
static void dd_name(cob_file *f, char *out, size_t cap) {
    out[0] = 0;
    if (f->assign && f->assign->data) {
        size_t n = f->assign->size < cap - 1 ? f->assign->size : cap - 1;
        memcpy(out, f->assign->data, n);
        out[n] = 0;
        while (n > 0 && (out[n - 1] == ' ' || out[n - 1] == 0)) {
            out[--n] = 0;
        }
    }
}

/* The planned status of this operation, or NULL: every occurrence is counted, whether or not it faults. */
static const char *planned_status(cob_file *f, const char *op) {
    load_plan();
    if (!planned) {
        return NULL;
    }
    char dd[32];
    dd_name(f, dd, sizeof dd);
    const char *hit = NULL;
    for (int i = 0; i < planned; i++) {
        if (strcmp(plan[i].dd, dd) != 0 || strcmp(plan[i].op, op) != 0) {
            continue;
        }
        plan[i].seen++;
        if (!hit && (plan[i].nth == 0 || plan[i].nth == plan[i].seen)) {
            hit = plan[i].status;
            const char *log = getenv("GGFAULT_LOG");
            FILE *l = log ? fopen(log, "a") : NULL;
            if (l) {
                fprintf(l, "%s %s %d %s\n", dd, op, plan[i].seen, plan[i].status);
                fclose(l);
            }
        }
    }
    return hit;
}

/* Give the operation `status` as libcob gives a failed one (fileio.c save_status). */
static void fail(cob_file *f, cob_field *fnstatus, const char *status) {
    if (f->file_status) {
        memcpy(f->file_status, status, 2);
    }
    if (fnstatus && fnstatus->data && fnstatus->size >= 2) {
        memcpy(fnstatus->data, status, 2);
    }
    int ec = status[0] == '1'   ? COB_EC_I_O_AT_END
             : status[0] == '2' ? COB_EC_I_O_INVALID_KEY
             : status[0] == '3' ? COB_EC_I_O_PERMANENT_ERROR
             : status[0] == '4' ? COB_EC_I_O_LOGIC_ERROR
             : status[0] == '9' ? COB_EC_I_O_IMP
                                : 0;
    if (ec) {
        cob_set_exception(ec);
        cob_get_global_ptr()->cob_error_file = f; /* the default error handler reads it */
    }
}

typedef void (*open_fn)(cob_file *, const int, const int, cob_field *);
typedef void (*close_fn)(cob_file *, cob_field *, const int, const int);
typedef void (*read_fn)(cob_file *, cob_field *, cob_field *, const int);
typedef void (*next_fn)(cob_file *, cob_field *, const int);
typedef void (*rewrite_fn)(cob_file *, cob_field *, const int, cob_field *);
typedef void (*delete_fn)(cob_file *, cob_field *);
typedef void (*start_fn)(cob_file *, const int, cob_field *, cob_field *, cob_field *);
typedef void (*write_fn)(cob_file *, cob_field *, const int, cob_field *, const unsigned int);

#define REAL(name, type)                                   \
    static type real_##name;                               \
    if (!real_##name) {                                    \
        real_##name = (type)dlsym(RTLD_NEXT, #name);       \
    }

void cob_open(cob_file *f, const int mode, const int sharing, cob_field *fnstatus) {
    REAL(cob_open, open_fn)
    const char *st = planned_status(f, "OPEN");
    if (st) {
        fail(f, fnstatus, st);
        return;
    }
    real_cob_open(f, mode, sharing, fnstatus);
}

void cob_close(cob_file *f, cob_field *fnstatus, const int opt, const int remfil) {
    REAL(cob_close, close_fn)
    const char *st = planned_status(f, "CLOSE");
    if (st) {
        fail(f, fnstatus, st);
        return;
    }
    real_cob_close(f, fnstatus, opt, remfil);
}

void cob_read(cob_file *f, cob_field *key, cob_field *fnstatus, const int opt) {
    REAL(cob_read, read_fn)
    const char *st = planned_status(f, "READ");
    if (st) {
        fail(f, fnstatus, st);
        return;
    }
    real_cob_read(f, key, fnstatus, opt);
}

void cob_read_next(cob_file *f, cob_field *fnstatus, const int opt) {
    REAL(cob_read_next, next_fn)
    const char *st = planned_status(f, "READ");
    if (st) {
        fail(f, fnstatus, st);
        return;
    }
    real_cob_read_next(f, fnstatus, opt);
}

void cob_rewrite(cob_file *f, cob_field *rec, const int opt, cob_field *fnstatus) {
    REAL(cob_rewrite, rewrite_fn)
    const char *st = planned_status(f, "REWRITE");
    if (st) {
        fail(f, fnstatus, st);
        return;
    }
    real_cob_rewrite(f, rec, opt, fnstatus);
}

void cob_delete(cob_file *f, cob_field *fnstatus) {
    REAL(cob_delete, delete_fn)
    const char *st = planned_status(f, "DELETE");
    if (st) {
        fail(f, fnstatus, st);
        return;
    }
    real_cob_delete(f, fnstatus);
}

void cob_start(cob_file *f, const int cond, cob_field *key, cob_field *keysize, cob_field *fnstatus) {
    REAL(cob_start, start_fn)
    const char *st = planned_status(f, "START");
    if (st) {
        fail(f, fnstatus, st);
        return;
    }
    real_cob_start(f, cond, key, keysize, fnstatus);
}

void cob_write(cob_file *f, cob_field *rec, const int opt, cob_field *fnstatus, const unsigned int check_eop) {
    REAL(cob_write, write_fn)
    const char *st = planned_status(f, "WRITE");
    if (st) {
        fail(f, fnstatus, st);
        return;
    }
    real_cob_write(f, rec, opt, fnstatus, check_eop);
}
