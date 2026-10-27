#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: CicsTask's transient-data queue support (#5079, X57, split out by #5274)
#
# PURPOSE:
# The transient-data (TD) queue family of the CICS task runtime the transaction forge emits (CICS_TASK_JAVA):
# the CSD facts (withTdQueues, withTdQueueTypes, withTdQueueAttributes), INQUIRE / SET TDQUEUE, WRITEQ / READQ /
# DELETEQ TD and the TdResult record. The forge splices it into CicsTask where it always sat, so the class is
# byte-identical.
# ==============================================================================

TDQUEUES_JAVA = """\
    /** The transient-data queues the CSD defines; null, every queue is defined. */
    public CicsTask withTdQueues(java.util.Set<String> queues) {
        this.tdQueues = queues;
        return this;
    }

    /** Each transient-data queue's TYPE ("" when the CSD states none): INTRA, EXTRA, INDIRECT or REMOTE (#5079, X57).
     *  Without it, a queue is intrapartition. */
    public CicsTask withTdQueueTypes(java.util.Map<String, String> types) {
        this.tdTypes = types;
        return this;
    }

    /** Each queue's CSD attributes beyond its TYPE (#5168, X61), as queue, key, value triples: RECOVSTATUS, TYPEFILE, OPENTIME,
     *  INDIRECTNAME, TRIGGERLEVEL, TRANSID. A queue the case's definition does not state one for has none. */
    public CicsTask withTdQueueAttributes(String... triples) {
        java.util.Map<String, java.util.Map<String, String>> out = new java.util.HashMap<>();
        for (int i = 0; i + 2 < triples.length; i += 3) {
            out.computeIfAbsent(triples[i], k -> new java.util.HashMap<>()).put(triples[i + 1], triples[i + 2]);
        }
        this.tdAttrs = out;
        return this;
    }

    private String tdAttr(String q, String key) {
        CicsTask root = root();
        return root.tdAttrs == null || !root.tdAttrs.containsKey(q) ? null : root.tdAttrs.get(q).get(key);
    }

    /** The queue's kind: 0 the CSD does not define it, 1 intrapartition (TYPE INTRA, or no types given), 2 extrapartition,
     *  3 any other TYPE or none stated -- a queue READQ TD / DELETEQ TD do not model. */
    private int tdKind(String q) {
        CicsTask root = root();
        if (root.tdQueues != null && !root.tdQueues.contains(q)) {
            return 0;
        }
        if (root.tdTypes == null) {
            return 1;
        }
        String type = root.tdTypes.getOrDefault(q, "");
        return type.equals("INTRA") ? 1 : type.equals("EXTRA") ? 2 : 3;
    }

    /** #5168 (X61): an INDIRECT queue routes to the queue its INDIRECTNAME names (which may itself be indirect); the queue
     *  that holds the records. Refused by name: no INDIRECTNAME, a target the CSD does not define, a chain that loops. */
    private String tdResolve(String q) {
        CicsTask root = root();
        String at = q;
        for (int hops = 0; root.tdTypes != null && "INDIRECT".equals(root.tdTypes.get(at)); hops++) {
            String next = tdAttr(at, "INDIRECTNAME");
            if (next == null) {
                throw new UnsupportedOperationException("an INDIRECT TD queue without INDIRECTNAME: not modelled");
            }
            if (hops >= 8) {
                throw new UnsupportedOperationException("a chain of INDIRECT TD queues that loops: not modelled");
            }
            if (!root.tdTypes.containsKey(next)) {
                throw new UnsupportedOperationException("an INDIRECT TD queue whose target the CSD does not define: not modelled");
            }
            at = next;
        }
        return at;
    }

    /** #5168 (X61): an extrapartition queue's state: 0 open for input, 1 open for output, 2 closed (OPENTIME DEFERRED: "the data
     *  set remains closed until you indicate that you want to open it"; INITIAL, or none stated: ASSUMED, open). Refused: a
     *  TYPEFILE other than INPUT / OUTPUT. */
    private int tdExtraState(String q) {
        String file = tdAttr(q, "TYPEFILE");
        if (!"INPUT".equals(file) && !"OUTPUT".equals(file)) {
            throw new UnsupportedOperationException("READQ TD of an extrapartition queue with no TYPEFILE INPUT / OUTPUT: not modelled");
        }
        return tdExtraClosed(q) ? 2 : file.equals("INPUT") ? 0 : 1;
    }

    /** #5168 round 3 (X61): true when an extrapartition queue's data set is closed: the state a SET TDQUEUE OPENSTATUS left, else
     *  OPENTIME DEFERRED; INITIAL, or none stated (ASSUMED), is open. */
    private boolean tdExtraClosed(String q) {
        Boolean set = root().tempStorage.tdOpen.get(q);
        return set != null ? !set : "DEFERRED".equals(tdAttr(q, "OPENTIME"));
    }

    /** #5168 (X61): RECOVSTATUS. LOGICAL: the queue as it was at the end of the last unit of work comes back on a rollback (the
     *  first read, write or delete since the last SYNCPOINT saves it). NO, or none stated (ASSUMED): committed at once, as X57.
     *  PHYSICAL: a rollback after touching one is refused by name. */
    private void tdTouch(String q) {
        CicsTask root = root();
        String recov = tdAttr(q, "RECOVSTATUS");
        if ("LOGICAL".equals(recov)) {
            java.util.ArrayDeque<String> now = tempStorage.td.get(q);
            root.tdUow.computeIfAbsent(q, k -> now == null ? new java.util.ArrayDeque<>() : new java.util.ArrayDeque<>(now));
        } else if ("PHYSICAL".equals(recov)) {
            root.tdPhysical.add(q);
        }
    }

    /** #4892 (register W5): a resource manager the runner joins to the task -- cobolrt.mq's queue manager ("mq") --
     *  found again by resource(name), and told as the task's unit of work ends: SYNCPOINT (false); SYNCPOINT ROLLBACK
     *  and the backout of an abend that ends the task (true), as the stub's uow_end tells tests/equivalence/mq/ggmq.c. */
    public CicsTask withResource(String name, Object manager, Consumer<Boolean> uowEnd) {
        root().resources.put(name, manager);
        if (uowEnd != null) {
            root().uowParticipants.add(uowEnd);
        }
        return this;
    }

    /** #4892: the resource manager joined under `name`, or null. */
    public Object resource(String name) {
        return root().resources.get(name);
    }

    /** #4892: an event a resource manager records in the task's stream (an MQI call, as ggmq.c's ggcics_event). */
    public void resourceEvent(String kind, Object... kv) {
        event(kind, kv);
    }

    private void resourceUowEnd(boolean rollback) {
        for (Consumer<Boolean> p : root().uowParticipants) {
            p.accept(rollback);
        }
    }

    /** The unit of work ends (#5168): committed, or backed out. */
    private void tdUowEnd(boolean rollback) {
        CicsTask root = root();
        if (rollback && !root.tdPhysical.isEmpty()) {
            throw new UnsupportedOperationException("SYNCPOINT ROLLBACK after a READQ / WRITEQ / DELETEQ TD of a PHYSICALLY "
                    + "recoverable queue: not modelled");
        }
        if (rollback) {
            root.tdUow.forEach((q, saved) -> {
                if (saved.isEmpty()) {
                    tempStorage.td.remove(q);
                } else {
                    tempStorage.td.put(q, new java.util.ArrayDeque<>(saved));
                }
            });
        }
        root.tdUow.clear();
        root.tdPhysical.clear();
    }

    /** #5168 (X61): WRITEQ TD to an extrapartition queue: NOTOPEN (19) when closed (OPENTIME DEFERRED), INVREQ (16) when open for
     *  input; a queue with no TYPEFILE (or RDBACK) is taken as open for output (ASSUMED), as before. */
    private int tdExtraWriteResp(String q) {
        if (tdExtraClosed(q)) {
            return 19;
        }
        return "INPUT".equals(tdAttr(q, "TYPEFILE")) ? 16 : 0;
    }

    /** #5168 round 5 (X66): true when SET TDQUEUE ENABLESTATUS(DISABLED) left the queue disabled ("The queue cannot be accessed by
     *  applications"): READQ, WRITEQ and DELETEQ TD then answer DISABLED (84). A queue is ENABLED until a SET says otherwise
     *  (ASSUMED: IBM states no default); the state outlives the task. */
    private boolean tdDisabled(String q) {
        return root().tempStorage.tdDisabled.contains(q);
    }

    /** The queue's TYPE CVDA for INQUIRE TDQUEUE: INTRA 222, EXTRA 221, INDIRECT 122, REMOTE 4; a queue with no TYPE stated is refused. */
    private int tdTypeCvda(String q, int kind) {
        if (kind == 1) {
            return 222;
        }
        if (kind == 2) {
            return 221;
        }
        String type = root().tdTypes == null ? "" : root().tdTypes.getOrDefault(q, "");
        if (type.equals("INDIRECT")) {
            return 122;
        }
        if (type.equals("REMOTE")) {
            return 4;
        }
        throw new UnsupportedOperationException("INQUIRE TDQUEUE of a queue with no TYPE stated: not modelled");
    }

    /** SET TDQUEUE(q) OPENSTATUS(cvda) (#5168 round 3, X61; IBM CICS TS 6.x SET TDQUEUE): an extrapartition queue's data set "is to
     *  be opened" (OPEN 18) or "closed" (CLOSED 19); the state replaces OPENTIME and outlives the task. Returns {RESP, RESP2}:
     *  QIDERR (44) RESP2 1, INVREQ (16) RESP2 9 for an intrapartition queue, RESP2 8 for an invalid CVDA. Setting the state a queue is
     *  in is NORMAL (ASSUMED). Refused: an INDIRECT / REMOTE queue, an invalid CVDA on a queue that is not extrapartition (IBM does
     *  not order the conditions), OPEN with no TYPEFILE INPUT / OUTPUT, OPEN of an input queue already read, RESP2 16 (the DDNAME
     *  is taken as found). */
    public int[] setTdQueueOpenStatus(String queue, long cvda) {
        String q = queue.strip();
        int kind = tdKind(q);
        boolean valid = cvda == 18 || cvda == 19;
        if (!valid && kind != 2) {
            throw new UnsupportedOperationException("SET TDQUEUE OPENSTATUS with an invalid CVDA on a queue that is not extrapartition: "
                    + "IBM does not say which condition comes first: not modelled");
        }
        if (kind == 0) {
            return new int[] {44, 1};
        }
        if (kind == 1) {
            return new int[] {16, 9};
        }
        if (kind == 3) {
            throw new UnsupportedOperationException("SET TDQUEUE OPENSTATUS of an INDIRECT or REMOTE queue: not modelled");
        }
        if (!valid) {
            return new int[] {16, 8};
        }
        if (cvda == 18) {
            String file = tdAttr(q, "TYPEFILE");
            if (!"INPUT".equals(file) && !"OUTPUT".equals(file)) {
                throw new UnsupportedOperationException("SET TDQUEUE OPENSTATUS(OPEN) of an extrapartition queue with no TYPEFILE "
                        + "INPUT / OUTPUT: not modelled");
            }
            if ("INPUT".equals(file) && root().tempStorage.tdRead.contains(q)) {
                throw new UnsupportedOperationException("SET TDQUEUE OPENSTATUS(OPEN) of an input queue that has been read: reopening "
                        + "restarts the data set: not modelled");
            }
        }
        root().tempStorage.tdOpen.put(q, cvda == 18);
        return new int[] {0, 0};
    }

    /** INQUIRE TDQUEUE(q) OPENSTATUS(area) TYPE(area) (#5168 round 3, X61): {RESP, RESP2, OPENSTATUS CVDA, TYPE CVDA}. QIDERR (44)
     *  RESP2 1 "the named queue cannot be found". OPENSTATUS is OPEN 18 / CLOSED 19 for an extrapartition queue, NOTAPPLIC 1
     *  ("the queue is not extrapartition") for the others; a queue with no TYPE stated is refused for either option. */
    public int[] inquireTdQueue(String queue, boolean openStatus, boolean type) {
        return inquireTdQueue(queue, openStatus, type, false);
    }

    /** INQUIRE TDQUEUE ... ENABLESTATUS (#5168 round 5, X66): {RESP, RESP2, OPENSTATUS CVDA, TYPE CVDA, ENABLESTATUS CVDA}; ENABLED 23
     *  or DISABLED 24, the state SET TDQUEUE ENABLESTATUS left (ENABLED before any). An INDIRECT queue answers about itself. */
    public int[] inquireTdQueue(String queue, boolean openStatus, boolean type, boolean enableStatus) {
        return inquireTdQueue(queue, openStatus, type, enableStatus, false, false, false);
    }

    /** INQUIRE TDQUEUE ... TRIGGERLEVEL / RECOVSTATUS / TRANSID (#5168 round 6, X66): {RESP, RESP2, OPENSTATUS, TYPE, ENABLESTATUS,
     *  TRIGGERLEVEL, RECOVSTATUS}; the TRANSID text is tdTransid(queue). The queue's definition: RECOVSTATUS is LOGICAL 216,
     *  PHYSICAL 215 or NOTRECOVABLE 30 for an intrapartition queue (NOTRECOVABLE when none stated: X61 assumption 2), NOTAPPLIC 1
     *  "the queue is not intrapartition" for the others; TRIGGERLEVEL (1 when none stated: IBM's default) and TRANSID (blanks when
     *  none stated: ASSUMED) are those of an intrapartition queue, and are refused for any other (IBM names no value). */
    public int[] inquireTdQueue(String queue, boolean openStatus, boolean type, boolean enableStatus, boolean trigger,
            boolean recov, boolean transid) {
        String q = queue.strip();
        int kind = tdKind(q);
        if (kind == 0) {
            return new int[] {44, 1, 0, 0, 0, 0, 0};
        }
        if ((trigger || transid) && kind != 1) {
            tdTypeCvda(q, kind);
            throw new UnsupportedOperationException("INQUIRE TDQUEUE TRIGGERLEVEL / TRANSID of a queue that is not intrapartition: not modelled");
        }
        int level = 0;
        if (trigger) {
            level = tdTriggerLevel(q);
        }
        int recovCvda = 0;
        if (recov) {
            String stated = kind == 1 ? tdAttr(q, "RECOVSTATUS") : null;
            if (kind != 1) {
                tdTypeCvda(q, kind);
            }
            recovCvda = kind != 1 ? 1 : "LOGICAL".equals(stated) ? 216 : "PHYSICAL".equals(stated) ? 215 : 30;
        }
        int typeCvda = type ? tdTypeCvda(q, kind) : 0;
        int status = 0;
        if (openStatus) {
            if (kind == 2) {
                status = tdExtraClosed(q) ? 19 : 18;
            } else {
                tdTypeCvda(q, kind);
                status = 1;
            }
        }
        return new int[] {0, 0, status, typeCvda, enableStatus ? (tdDisabled(q) ? 24 : 23) : 0, level, recovCvda};
    }

    /** A queue's TRIGGERLEVEL: what SET TDQUEUE TRIGGERLEVEL left, else the definition's, else 1 (IBM's default). #5168 round 7, X66. */
    private int tdTriggerLevel(String q) {
        Integer set = root().tempStorage.tdTrigger.get(q);
        if (set != null) {
            return set;
        }
        String stated = tdAttr(q, "TRIGGERLEVEL");
        return stated == null ? 1 : Integer.parseInt(stated.strip());
    }

    /** SET TDQUEUE(q) TRIGGERLEVEL(n) (#5168 round 7, X66; IBM CICS TS 6.x SET TDQUEUE, intrapartition queues only): the number of
     *  records that starts the queue's ATI transaction; 0 turns automatic task initiation off. Returns {RESP, RESP2}: QIDERR (44)
     *  RESP2 1. Not a unit-of-work resource (a rollback or an abend keeps it). Refused: a queue that is not intrapartition (IBM names
     *  no condition) and a level below zero. */
    public int[] setTdQueueTriggerLevel(String queue, long level) {
        String q = queue.strip();
        int kind = tdKind(q);
        if (kind == 0) {
            return new int[] {44, 1};
        }
        if (kind != 1 || level < 0 || level > Integer.MAX_VALUE) {
            throw new UnsupportedOperationException("SET TDQUEUE TRIGGERLEVEL of a queue that is not intrapartition, or below zero: not modelled");
        }
        root().tempStorage.tdTrigger.put(q, (int) level);
        return new int[] {0, 0};
    }

    /** The TRANSID a queue's definition states (blanks when none): the text INQUIRE TDQUEUE TRANSID stores (#5168 round 6, X66). */
    public String tdTransid(String queue) {
        String stated = tdAttr(queue.strip(), "TRANSID");
        return stated == null ? "" : stated;
    }

    /** SET TDQUEUE(q) ENABLESTATUS(cvda) (#5168 round 5, X66; IBM CICS TS 6.x SET TDQUEUE): ENABLED (23) lets applications access
     *  the queue, DISABLED (24) does not (READQ / WRITEQ / DELETEQ TD then answer DISABLED). For an extrapartition queue only its
     *  availability changes, the data set is not opened or closed. Returns {RESP, RESP2}: QIDERR (44) RESP2 1, INVREQ (16) RESP2 10
     *  for an invalid CVDA. Setting the state a queue is in is NORMAL (ASSUMED). Refused: an invalid CVDA on a queue the CSD does
     *  not define (IBM does not order the two), an INDIRECT / REMOTE queue (its target is what a command reaches). RESP2 30 / 31 / 35
     *  / 40 (disable pending, in doubt, CXRF) do not arise: one task, no recovery. */
    public int[] setTdQueueEnableStatus(String queue, long cvda) {
        String q = queue.strip();
        int kind = tdKind(q);
        boolean valid = cvda == 23 || cvda == 24;
        if (kind == 0) {
            if (!valid) {
                throw new UnsupportedOperationException("SET TDQUEUE ENABLESTATUS with an invalid CVDA on a queue the CSD does not define: "
                        + "IBM does not say which condition comes first: not modelled");
            }
            return new int[] {44, 1};
        }
        if (kind == 3) {
            throw new UnsupportedOperationException("SET TDQUEUE ENABLESTATUS of an INDIRECT or REMOTE queue: not modelled");
        }
        if (!valid) {
            return new int[] {16, 10};
        }
        if (cvda == 24) {
            root().tempStorage.tdDisabled.add(q);
        } else {
            root().tempStorage.tdDisabled.remove(q);
        }
        return new int[] {0, 0};
    }

    /** WRITEQ TD QUEUE(queue) FROM(record) (IBM CICS TS): one record on a transient-data queue -- recorded, with the
     *  record's text, and compared (CardDemo's CORPT00C submits JCL through JOBS) -- and appended to an intrapartition
     *  queue for a READQ TD to read (#5079). QIDERR (44) for a queue the CSD does not define, or the condition the
     *  harness planned; then nothing is written. #5168: an INDIRECT queue holds its records on its target; a write that
     *  brings a queue with a TRANSID to its TRIGGERLEVEL (default 1; 0: ATI off) is refused (ATI is not modelled). */
    public int writeqTd(String queue, String record) {
        String q = queue.strip();
        String t = tdResolve(q);
        int kind = tdKind(t);
        int[] planned = root().injected("WRITEQ-TD", q);
        int resp = planned != null ? planned[0] : kind == 0 ? 44 : tdDisabled(t) ? 84 : kind == 2 ? tdExtraWriteResp(t) : 0;
        event("WRITEQ-TD", "queue", q, "text", resp == 0 ? record : null, "resp", resp);
        if (resp == 0 && kind == 1) {
            tdTouch(t);
            if (tdAttr(t, "TRANSID") != null) {
                int level = tdTriggerLevel(t);
                java.util.ArrayDeque<String> held = tempStorage.td.get(t);
                int after = (held == null ? 0 : held.size()) + 1;
                if (level > 0 && after >= level) {
                    throw new UnsupportedOperationException("WRITEQ TD to a queue that reaches its TRIGGERLEVEL: automatic task "
                            + "initiation is not modelled");
                }
            }
            tempStorage.td.computeIfAbsent(t, k -> new java.util.ArrayDeque<>()).addLast(record);
        }
        return resp;
    }

    /** READQ TD QUEUE(queue) INTO LENGTH(maxLength) (#5079, IBM EXEC CICS READQ TD, X57): a destructive read, first in
     *  first out. QIDERR when the CSD does not define the queue; QZERO when it holds no record; LENGERR for a negative
     *  maxLength (nothing is read) or a record longer than maxLength (the record is read, so lost, and the result holds
     *  its first maxLength characters); the result's length is the record's own. #5168 (X61): an extrapartition queue is
     *  NOTOPEN when closed and INVREQ when open for output; an input one reads like an intrapartition queue, or answers
     *  the IOERR the harness planned (READQ-TD, the record skipped). #5168 (X61): a LOGICAL intrapartition queue holding no
     *  record answers the QBUSY the harness planned (another task is writing it: IBM states no RESP2); that needs NOSUSPEND
     *  (else IBM suspends the task: refused). */
    public TdResult readqTd(String queue, int maxLength) {
        return readqTd(queue, maxLength, false);
    }

    public TdResult readqTd(String queue, int maxLength, boolean noSuspend) {
        String q = queue.strip();
        String t = tdResolve(q);
        int kind = tdKind(t);
        if (kind == 3) {
            throw new UnsupportedOperationException("READQ TD of a queue whose TYPE is not INTRA or EXTRA: not modelled");
        }
        int state = kind == 2 ? tdExtraState(t) : 0;
        java.util.ArrayDeque<String> records = tempStorage.td.get(t);
        String resp = kind == 0 ? "QIDERR" : tdDisabled(t) ? "DISABLED" : state == 2 ? "NOTOPEN" : state == 1 ? "INVREQ" : maxLength < 0 ? "LENGERR"
                : records == null || records.isEmpty() ? "QZERO" : "NORMAL";
        String data = null;
        int length = -1;
        boolean readable = kind != 0 && state == 0 && maxLength >= 0 && !resp.equals("DISABLED");
        if (readable) {
            tdTouch(t);
        }
        boolean busyable = readable && kind == 1 && "LOGICAL".equals(tdAttr(t, "RECOVSTATUS")) && (records == null || records.isEmpty());
        int[] planned = readable && (kind == 2 || busyable) ? root().injected("READQ-TD", q) : null;
        if (planned != null && busyable != (planned[0] == 25)) {
            throw new UnsupportedOperationException("a planned READQ TD " + CicsSpec.name(planned[0]) + " on " + q + ": QBUSY is for a LOGICAL intrapartition queue with no record, IOERR for an extrapartition one");
        }
        if (planned != null && busyable) {  // #5168 (X61): a planned QBUSY, no committed record left
            if (!noSuspend) {
                throw new UnsupportedOperationException("READQ TD on a planned-busy queue without NOSUSPEND: " + q + " (the task would be suspended)");
            }
            resp = CicsSpec.name(planned[0]);
        } else if (planned != null) {  // #5168 (X61): a planned IOERR -- IBM: "the data record in error is skipped", nothing reaches INTO
            if (records != null && !records.isEmpty()) {
                records.removeFirst();
                tempStorage.tdRead.add(t);
            }
            resp = CicsSpec.name(planned[0]);
        } else if (readable && records != null && !records.isEmpty()) {
            String record = records.removeFirst();
            data = record.length() > maxLength ? record.substring(0, maxLength) : record;
            length = record.length();
            if (kind == 2) {
                tempStorage.tdRead.add(t);
            }
            resp = record.length() > maxLength ? "LENGERR" : "NORMAL";
        } else if (resp.equals("LENGERR")) {
            data = "";
        }
        event("READQ-TD", "queue", q, "resp", resp, "data", data);
        return new TdResult(CicsSpec.resp(resp), length, data);
    }

    /** DELETEQ TD QUEUE(queue) (#5079, IBM EXEC CICS DELETEQ TD, X57): every record of an intrapartition queue. QIDERR
     *  (44) when the CSD does not define it, INVREQ (16) for an extrapartition queue. Returns RESP (RESP2 is 0). */
    public int deleteqTd(String queue) {
        String t = tdResolve(queue.strip());
        int kind = tdKind(t);
        if (kind == 3) {
            throw new UnsupportedOperationException("DELETEQ TD of a queue whose TYPE is not INTRA or EXTRA: not modelled");
        }
        if (kind == 0) {
            return 44;
        }
        if (tdDisabled(t)) {
            return 84;
        }
        if (kind != 1) {
            return 16;
        }
        tdTouch(t);
        tempStorage.td.remove(t);
        return 0;
    }

    /** A READQ TD's outcome: RESP, the record's own length (-1 when none was read) and the text moved INTO (null when none). */
    public record TdResult(int resp, int length, String data) {
    }

"""
