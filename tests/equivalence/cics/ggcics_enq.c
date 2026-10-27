/* #5089, #5274: the ENQ stub (GGCENQ) -- split out of ggcics.c, which includes it where the block sat. DEQ has no stub: the
 * harness translates it inline (NORMAL, one task in the region). */
/* ENQ RESOURCE (#5089, IBM EXEC CICS ENQ): one task in the region, so the resource is free (NORMAL) -- or ENQBUSY when
 * faults.cfg plans it. IBM raises ENQBUSY only "when an ENQ command specifies a resource that is unavailable and the
 * NOSUSPEND option is specified" (or a HANDLE CONDITION ENQBUSY is active); without NOSUSPEND the task would be
 * suspended, which is not modelled. IBM states no RESP2 for ENQBUSY: 0. GG-FLAGS holds the resource as the program
 * writes it (the fault's name), GG-NAME1 'NOSUSPEND' when given. */
int GGCENQ(gg_cics *c) {
    char res[41], ev[96];
    int fresp, fresp2;
    c->resp = NORMAL;
    c->resp2 = 0;
    trim(c->flags, 40, res);
    /* X60: GG-NAME2 'L' = LENGTH written (GG-LEN), 'M' = MAXLIFETIME written (GG-NUM, a CVDA: UOW 246, TASK 233).
     * LENGTH outside 1-255 is LENGERR RESP2 1; a CVDA that is neither is INVREQ RESP2 2; both at once is refused. */
    int bad_len = memchr(c->name2, 'L', 8) && (c->len < 1 || c->len > 255);
    int bad_life = memchr(c->name2, 'M', 8) && c->num != 246 && c->num != 233;
    if (bad_len && bad_life) refuse("ENQ with LENGTH outside 1-255 and an invalid MAXLIFETIME (IBM states no order)");
    if (bad_len || bad_life) {
        c->resp = bad_len ? LENGERR : INVREQ;
        c->resp2 = bad_len ? 1 : 2;
        snprintf(ev, sizeof ev, "ENQ resource=%s resp=%d resp2=%d", res, c->resp, c->resp2);
        event(ev, NULL, 0);
        return 0;
    }
    if (!injected("ENQ", res, &fresp, &fresp2)) return 0;
    if (strncmp(c->name1, "NOSUSPEN", 8) != 0) {
        snprintf(ev, sizeof ev, "ENQ on a planned-busy resource without NOSUSPEND: %s (the task would be suspended)", res);
        refuse(ev);
    }
    c->resp = fresp;
    c->resp2 = fresp2;
    snprintf(ev, sizeof ev, "ENQ resource=%s resp=%d", res, c->resp);
    event(ev, NULL, 0);
    return 0;
}
