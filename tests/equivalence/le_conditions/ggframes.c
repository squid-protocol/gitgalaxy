/*
 * ggframes.c -- the GnuCOBOL frame source for the LE condition model ceecond.c (#8062, register L8).
 *
 * ceecond.c keeps handler registrations per stack frame and needs to know which frames are live. GnuCOBOL has no
 * activation record: libcob keeps one cob_module per PROGRAM (the same address for every activation of B, whoever
 * called it), so the module address is not an identity -- a second CALL "B" after the first returned would inherit
 * the first one's registrations. This file gives each activation its own identity:
 *   - cob_module_global_enter / cob_module_leave are interposed (dlsym RTLD_NEXT, as tests/equivalence/faults/ggfault.c
 *     sits in front of libcob's file I/O): every entry that libcob accepts pushes (module, serial) with a serial that
 *     is never reused, every leave pops that activation and any above it;
 *   - gg_le_frames walks libcob's own chain (cob_current_module, ->next) and names each module by the serial of its
 *     topmost activation. The identity handed to ceecond.c is that serial, so an activation that returned can never be
 *     mistaken for a later one at the same address.
 * Refused by name (exit 98, "... is not modelled"): a recursive activation (one module twice in the chain; the model
 * keeps one queue per identity and IBM's per-frame order across a recursion is not stated in what L8 cites), a chain
 * libcob and this stack disagree on, and more frames than ceecond.c holds.
 * The handler call: a handler is a COBOL entry reached through a function pointer, not through CALL, so nothing sets
 * libcob's argument count. the hook gg_le_set_handler_hook installs makes ceecond.c's dispatch store cob_call_params = 4 (c_ctok, token,
 * result_code, new_condition: IBM's user-written condition handler interface) before it enters the handler.
 *
 * Link with ceecond.c after the program, under its own evidence component; tests/equivalence/le/ is not touched.
 * ASSUMED (IBM-documented) like ceecond.c; GnuCOBOL's own frames are the instrument, z/OS is the reference.
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <libcob.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef int (*gg_le_frames_fn)(void **chain, int max);
void gg_le_set_frames(gg_le_frames_fn fn);
void gg_le_set_handler_hook(void (*hook)(int nparams));

#define GG_ACT_MAX 4096

static struct act {
    cob_module *module;
    uintptr_t serial;
} acts[GG_ACT_MAX];
static int nacts;
static uintptr_t next_serial = 1;

static void refuse(const char *what) {
    fprintf(stderr, "ggframes: %s is not modelled\n", what);
    fflush(stdout);
    exit(98);
}

/* cob_module_global_enter returns nonzero when libcob refuses the entry (it then runs no program text): not an activation. */
int cob_module_global_enter(cob_module **module, cob_global **mglobal, const int auto_init, const int entry,
                            const unsigned int *name_hash) {
    static int (*real)(cob_module **, cob_global **, const int, const int, const unsigned int *);
    if (!real) real = (int (*)(cob_module **, cob_global **, const int, const int, const unsigned int *))dlsym(RTLD_NEXT, "cob_module_global_enter");
    int rc = real(module, mglobal, auto_init, entry, name_hash);
    if (rc) return rc;
    if (nacts == GG_ACT_MAX) refuse("more than 4096 live activations");
    acts[nacts].module = *module;
    acts[nacts].serial = next_serial++;
    nacts++;
    return rc;
}

void cob_module_leave(cob_module *module) {
    static void (*real)(cob_module *);
    if (!real) real = (void (*)(cob_module *))dlsym(RTLD_NEXT, "cob_module_leave");
    for (int i = nacts - 1; i >= 0; i--) {
        if (acts[i].module != module) continue;
        nacts = i; /* this activation and any above it (a longjmp out of them) are gone */
        break;
    }
    real(module);
}

static int frames(void **chain, int max) {
    cob_global *g = cob_get_global_ptr();
    int n = 0, top = nacts;
    for (cob_module *m = g ? g->cob_current_module : NULL; m; m = m->next) {
        int found = -1;
        for (int i = top - 1; i >= 0 && found < 0; i--) found = acts[i].module == m ? i : -1;
        if (found < 0) refuse("a frame that no activation entered (the chain and the activation stack disagree)");
        /* a program twice in the chain is a recursion, whether libcob shares its module (the same address) or not */
        for (cob_module *o = g->cob_current_module; o != m; o = o->next)
            if (o == m || (o->module_name && m->module_name && !strcmp(o->module_name, m->module_name)))
                refuse("a recursive activation");
        if (n == max) refuse("more frames than the model holds");
        chain[n++] = (void *)acts[found].serial;
        top = found; /* the caller's activation entered before this one */
    }
    return n;
}

static void handler_params(int nparams) {
    cob_global *g = cob_get_global_ptr();
    if (g) g->cob_call_params = nparams;
}

/* Runs at load, so the model has its frame source before the first CALL "CEEHDLR". */
__attribute__((constructor)) static void install(void) {
    gg_le_set_frames(frames);
    gg_le_set_handler_hook(handler_params);
}
