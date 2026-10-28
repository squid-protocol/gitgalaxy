#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: CicsTask's task / interval control (#4006, #4270, split out by #5274)
#
# PURPOSE:
# The task and interval control family of the CICS task runtime the transaction forge emits
# (CICS_TASK_JAVA): START (and its request builder), RETRIEVE, RUN TRANSID, FETCH, FREE CHILD, DELAY, POST,
# WAIT EVENT and CANCEL. The forge splices TASKCONTROL_JAVA into CicsTask at the place it always sat, so the
# class is byte-identical.
# ==============================================================================

TASKCONTROL_JAVA = """\

    /** The FROM data of the START requests this task was started for, in expiry order (#4006). */
    public CicsTask withRetrieveData(List<byte[]> data) {
        List<StartData> records = new ArrayList<>();
        if (data != null) {
            data.forEach(d -> records.add(new StartData(d, null, null, null)));
        }
        return withStartData(records);
    }

    /** #4270: the data records of the START requests this task was started for, in expiry order -- each one's FROM
     *  data and RTRANSID / RTERMID / QUEUE values, null where its START did not give one. A START that gave none of
     *  them stored no record (IBM, EXEC CICS RETRIEVE: ENDDATA for "a START command that did not specify any of the
     *  data options FROM, RTRANSID, RTERMID, or QUEUE"). */
    public CicsTask withStartData(List<StartData> records) {
        this.retrieveData = records == null ? List.of() : records;
        return this;
    }

    /** #4270: one START request's data record: FROM's bytes and the RTRANSID / RTERMID / QUEUE values (each null
     *  when the START did not give it). */
    public record StartData(byte[] from, String rtransid, String rtermid, String queue) {
    }

    /** The region's unexpired interval-control requests by REQID (#4006: what CANCEL can still find). */
    public CicsTask withRequests(Map<String, LocalDateTime> unexpired) {
        this.unexpired = unexpired == null ? Map.of() : unexpired;
        return this;
    }

    private static final DateTimeFormatter ISO = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss");

    /** START TRANSID(transid) [TERMID] INTERVAL(hhmmss) [FROM] [REQID] [PROTECT] (#4006, IBM EXEC CICS START):
     *  the request expires at now + INTERVAL; the harness's scheduler runs it once the starting task has
     *  ended (a PROTECT request only if it ended normally). `termid`, `from` and `reqid` may be null. */
    public StartResult start(String transid, String termid, int interval, byte[] from, String reqid, boolean protect) {
        return startRequest(transid).termid(termid).interval(interval).from(from).reqid(reqid).protect(protect).issue();
    }

    /** START ... TIME(hhmmss): see StartRequest.time. */
    public StartResult startAt(String transid, String termid, int time, byte[] from, String reqid, boolean protect) {
        return startRequest(transid).termid(termid).time(time).from(from).reqid(reqid).protect(protect).issue();
    }

    /** #4270: a START TRANSID(transid) request, its options set one by one, then issued (IBM CICS TS, EXEC CICS
     *  START). Without INTERVAL / TIME / AFTER / AT it is INTERVAL(0). */
    public StartRequest startRequest(String transid) {
        return new StartRequest(this, transid);
    }

    /** #4270: the options of one START. */
    public static final class StartRequest {
        private final CicsTask task;
        private final String transid;
        private String termid;
        private String reqid;
        private String rtransid;
        private String rtermid;
        private String queue;
        private byte[] from;
        private boolean protect;
        private String when = "INTERVAL";
        private int hhmmss;
        private Integer hours;
        private Integer minutes;
        private Integer seconds;
        private String channel;

        private StartRequest(CicsTask task, String transid) {
            this.task = task;
            this.transid = transid;
        }

        /** INTERVAL(hhmmss): now + hh hours, mm minutes, ss seconds; mm / ss above 59 is INVREQ RESP2 5 / 6. */
        public StartRequest interval(int hhmmss) {
            this.when = "INTERVAL";
            this.hhmmss = hhmmss;
            return this;
        }

        /** TIME(hhmmss): "If you specify a time with an hours component that is greater than 23, you are specifying
         *  a time on a day following the current one"; a time of today not later than now but within the preceding
         *  six hours expires at once ("If you specify a task to start at any time within the previous six hours,
         *  it starts immediately"), an earlier one tomorrow (IBM CICS TS, "Expiration times"). */
        public StartRequest time(int hhmmss) {
            this.when = "TIME";
            this.hhmmss = hhmmss;
            return this;
        }

        /** AFTER HOURS / MINUTES / SECONDS (null: not given): "A combination of at least two of HOURS(0 - 99),
         *  MINUTES(0 - 59), and SECONDS(0 - 59)", or "one of HOURS(0 - 99), MINUTES(0 - 5999), or SECONDS(0 -
         *  359999)"; out of range, INVREQ RESP2 4 / 5 / 6. The interval it amounts to. */
        public StartRequest after(Integer hours, Integer minutes, Integer seconds) {
            return hms("AFTER", hours, minutes, seconds);
        }

        /** AT HOURS / MINUTES / SECONDS: the time of day they amount to, as TIME. */
        public StartRequest at(Integer hours, Integer minutes, Integer seconds) {
            return hms("AT", hours, minutes, seconds);
        }

        private StartRequest hms(String how, Integer h, Integer m, Integer s) {
            if (h == null && m == null && s == null) {
                throw new UnsupportedOperationException("START " + how + " with none of HOURS / MINUTES / SECONDS");
            }
            this.when = how;
            this.hours = h;
            this.minutes = m;
            this.seconds = s;
            return this;
        }

        public StartRequest termid(String termid) {
            this.termid = termid;
            return this;
        }

        public StartRequest reqid(String reqid) {
            this.reqid = reqid;
            return this;
        }

        /** FROM's bytes (null: no FROM). */
        public StartRequest from(byte[] from) {
            this.from = from;
            return this;
        }

        public StartRequest protect(boolean protect) {
            this.protect = protect;
            return this;
        }

        /** RTRANSID / RTERMID / QUEUE: values the started task RETRIEVEs (null: not given). */
        public StartRequest rtransid(String rtransid) {
            this.rtransid = rtransid;
            return this;
        }

        public StartRequest rtermid(String rtermid) {
            this.rtermid = rtermid;
            return this;
        }

        public StartRequest queue(String queue) {
            this.queue = queue;
            return this;
        }

        /** #4950: CHANNEL(name): the started task gets a copy of the channel's containers as they are at the START,
         *  as its current channel (IBM, EXEC CICS START CHANNEL). */
        public StartRequest channel(String channel) {
            this.channel = channel;
            return this;
        }

        public StartResult issue() {
            return task.issueStart(this);
        }
    }

    /** #4270: AFTER / AT's HOURS, MINUTES, SECONDS as hhmmss, or -4 / -5 / -6 (INVREQ's RESP2, negated) for the
     *  first one out of range (IBM, EXEC CICS START, AFTER). */
    static int hhmmss(Integer h, Integer m, Integer s) {
        int given = (h != null ? 1 : 0) + (m != null ? 1 : 0) + (s != null ? 1 : 0);
        if (h != null && (h < 0 || h > 99)) {
            return -4;
        }
        if (m != null && (m < 0 || m > (given == 1 ? 5999 : 59))) {
            return -5;
        }
        if (s != null && (s < 0 || s > (given == 1 ? 359999 : 59))) {
            return -6;
        }
        int total = (h == null ? 0 : h) * 3600 + (m == null ? 0 : m) * 60 + (s == null ? 0 : s);
        return total / 3600 * 10000 + total / 60 % 60 * 100 + total % 60;
    }

    private StartResult issueStart(StartRequest q) {
        CicsTask task = root();
        String transid = q.transid;
        String how = q.when;
        int hhmmss = q.hhmmss;
        int resp2 = 0;
        if ("AFTER".equals(how) || "AT".equals(how)) {
            hhmmss = hhmmss(q.hours, q.minutes, q.seconds);
            if (hhmmss < 0) {
                resp2 = -hhmmss;
            }
        } else if (hhmmss < 0 || hhmmss / 10000 > 99) {
            resp2 = 4;
        } else if (hhmmss / 100 % 100 > 59) {
            resp2 = 5;
        } else if (hhmmss % 100 > 59) {
            resp2 = 6;
        }
        boolean isTime = "TIME".equals(how) || "AT".equals(how);
        int hh = hhmmss / 10000, mm = hhmmss / 100 % 100, ss = hhmmss % 100;
        LocalDateTime clock = now();
        LocalDateTime at = null;
        String resp = "NORMAL";
        int[] planned;
        if (q.reqid != null && (task.ownRequests.containsKey(q.reqid) || task.unexpired.containsKey(q.reqid))) {
            // IBM: IOERR when "A START operation uses a REQID name that exists. This condition occurs only when the
            // FROM option is also used" -- a REQID this task already used with FROM; any other reuse is not settled
            if (q.from == null || !task.ownWithData.contains(q.reqid)) {
                throw new UnsupportedOperationException("START REQID(" + q.reqid + ") of a request that exists"
                        + (q.from == null ? ", without FROM" : ", not this task's own with FROM") + ": not modelled");
            }
        }
        int range = resp2;
        String chan = q.channel == null ? null : handedChannel(q.channel);  // #4950: START CHANNEL
        Channel copy = null;
        if (q.channel != null && chan == null && programs != null && !programs.transaction(q.transid)) {
            throw new UnsupportedOperationException("START TRANSID(" + q.transid + ") of a transaction not defined, "
                    + "with an incorrect CHANNEL name: which condition IBM raises is not documented, not modelled");
        }
        if (chan != null) {
            Channel ch = scopeHanded(chan, false);
            if (ch == null) {
                throw new UnsupportedOperationException("START CHANNEL(" + chan + ") of a channel not in the "
                        + "program's scope: not modelled");
            }
            copy = copyOf(ch, chan);
        }
        if (q.channel != null && chan == null) {
            resp = "CHANNELERR";
            resp2 = 1;
        } else if (range != 0) {
            resp = "INVREQ";
        } else if (q.from != null && q.from.length < 1) {  // IBM: LENGERR "if LENGTH is not greater than zero"
            resp = "LENGERR";
        } else if (q.from != null && q.from.length > 32763) {
            resp = "LENGERR";
        } else if (programs != null && !programs.transaction(q.transid)) {
            resp = "TRANSIDERR";
        } else if (q.termid != null && programs != null && !programs.terminal(q.termid)) {
            resp = "TERMIDERR";
        } else if ((planned = task.injected("START", transid.stripTrailing())) != null) {
            resp = respName(planned[0]);  // #4049: a planned condition; nothing is started
            resp2 = planned[1];
        } else if (q.reqid != null && q.from != null && task.ownWithData.contains(q.reqid)) {
            resp = "IOERR";
        } else if (isTime) {
            at = clock.toLocalDate().atStartOfDay().plusHours(hh).plusMinutes(mm).plusSeconds(ss);
            if (hh <= 23 && !at.isAfter(clock)) {
                at = at.isBefore(clock.minusHours(6)) ? at.plusDays(1) : clock;
            }
        } else {
            at = clock.plusSeconds(hh * 3600L + mm * 60L + ss);
        }
        Map<String, Object> e = new LinkedHashMap<>();
        e.put("event", "START");
        e.put("transid", q.transid);
        e.put("termid", q.termid);
        // an AFTER / AT is recorded as the interval / time it amounts to; out of range, it amounts to none
        e.put(isTime ? "time" : "interval", hhmmss < 0 ? null : String.format(java.util.Locale.ROOT, "%06d", hhmmss));
        e.put("from", q.from == null ? null : q.from.clone());
        if (q.reqid != null) {
            e.put("reqid", q.reqid);
            if (at != null) {
                task.ownRequests.put(q.reqid, at);
                if (q.from != null) {
                    task.ownWithData.add(q.reqid);
                }
            }
        }
        // #4270: the data options, only those the program named
        if (q.rtransid != null) {
            e.put("rtransid", q.rtransid);
        }
        if (q.rtermid != null) {
            e.put("rtermid", q.rtermid);
        }
        if (q.queue != null) {
            e.put("queue", q.queue);
        }
        if (copy != null && "NORMAL".equals(resp)) {  // #4950: the copy the started task gets, its containers' bytes
            Map<String, String> data = new LinkedHashMap<>();
            copy.containers().forEach((n, v) -> data.put(n, java.util.HexFormat.of().withUpperCase().formatHex(v)));
            Map<String, Object> handed = new LinkedHashMap<>();
            handed.put("name", chan);
            handed.put("containers", data);
            e.put("channel", handed);
        }
        e.put("protect", q.protect);
        e.put("resp", resp);
        if (range != 0) {
            e.put("resp2", range);  // (SPEC 6.2: where IBM documents it -- INVREQ RESP2 4 / 5 / 6)
        } else if ("CHANNELERR".equals(resp)) {
            e.put("resp2", 1);
        }
        e.put("expires", at == null ? null : at.format(ISO));
        if ("NORMAL".equals(resp)) {
            task.releasePost();  // #5079 (X63): IBM, POST: a local START ends the POST's timer-event control area
        }
        add(e);
        return new StartResult(resp, at, resp2);
    }

    /** A START's outcome: its condition, when the request expires (null unless NORMAL) and RESP2 (#4270). */
    public record StartResult(String resp, LocalDateTime expires, int resp2) {
        public StartResult(String resp, LocalDateTime expires) {
            this(resp, expires, 0);
        }
    }

    /** #4270: the task is a RUN TRANSID child: IBM documents no RETRIEVE for it (its data comes by channel), so
     *  one is refused. */
    public CicsTask withRunChild(boolean child) {
        this.runChild = child;
        return this;
    }

    /** #4270 slice 2: RUN TRANSID(transid) CHILD (IBM CICS TS, EXEC CICS RUN TRANSID): it "starts a task on the
     *  local system ... The started task (child task) runs asynchronously with the starting task", and CICS places
     *  "the child token that represents the child task" in CHILD's 16-character area. TRANSIDERR RESP2 1 for a
     *  transaction not defined. #4950 (X18): the child runs at this task's next wait (delay, fetch); a task that
     *  never waits ends with it not run. The token's bytes are the harness's own (IBM does not document them), the
     *  same on both sides. */
    public RunResult runTransid(String transid) {
        return runTransid(transid, null);
    }

    /** #4884, #4950: RUN TRANSID CHANNEL(channel) (IBM: "if the channel does not exist, it is created"; the child
     *  "receives a copy of the channel's containers" when RUN is issued, and that copy is its current channel). A name
     *  with a character IBM does not list is CHANNELERR RESP2 1 (handedChannel). */
    public RunResult runTransid(String transid, String channel) {
        CicsTask task = root();
        if (task.depth >= MAX_RUN_DEPTH) {  // #5089 (X18): a child may RUN children of its own, to a stated depth
            throw new UnsupportedOperationException("RUN TRANSID in a RUN TRANSID child task " + MAX_RUN_DEPTH
                    + " levels below a task (a great-great-grandchild): the depth the harness models ends here");
        }
        int[] planned = task.injected("RUN-TRANSID", "-");  // #6882 (X18): a planned condition; no child is started
        if (planned != null) {
            Map<String, Object> p = new LinkedHashMap<>();
            p.put("event", "RUN");
            p.put("transid", transid);
            p.put("resp", respName(planned[0]));
            if (planned[1] != 0) {
                p.put("resp2", planned[1]);
            }
            add(p);
            return new RunResult(respName(planned[0]), planned[1], null);
        }
        String name = channel == null ? null : handedChannel(channel);
        boolean badName = channel != null && name == null;
        boolean undefined = programs != null && !programs.transaction(transid);
        if (badName && undefined) {
            throw new UnsupportedOperationException("RUN TRANSID(" + transid + ") of a transaction not defined, with "
                    + "an incorrect CHANNEL name: which condition IBM raises is not documented, not modelled");
        }
        String resp = "NORMAL";
        int resp2 = 0;
        String child = null;
        if (badName) {
            resp = "CHANNELERR";
            resp2 = 1;
        } else if (undefined) {
            resp = "TRANSIDERR";
            resp2 = 1;
        } else {
            child = String.format(java.util.Locale.ROOT, "GGCHILD%09d", ++task.children);
            task.kids.add(new Child(child, transid, name == null ? null : copyOf(scopeHanded(name, true), name),
                    task.children));
        }
        Map<String, Object> e = new LinkedHashMap<>();
        e.put("event", "RUN");
        e.put("transid", transid);
        e.put("resp", resp);
        if (resp2 != 0) {
            e.put("resp2", resp2);
        }
        add(e);
        return new RunResult(resp, resp2, child);
    }

    // #4950: the characters IBM allows in the name of a channel RUN TRANSID / START hands on (EXEC CICS RUN TRANSID,
    // CHANNEL: "The acceptable characters are A-Z a-z 0-9 $ @ # . / - _ % & ? ! : | " = \\u00ac , ; < >. Leading and
    // embedded blank characters are not permitted"); the spec's CHANNEL_NAME_CHARS, as ggcics.c's channel_chars
    private static final String CHANNEL_CHARS =
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789$@#./-_%&?!:|\\"=\\u00ac,;<>";

    /** #4950: the channel name RUN / START CHANNEL gives, without its trailing blanks; null when it holds a character
     *  IBM does not allow (a blank before its end included: CHANNELERR RESP2 1). An all-blank name is refused, as a
     *  name starting DFH (CICS's own channels, DFHTRANSACTION, are not modelled). */
    private static String handedChannel(String channel) {
        String n = channel;
        int end = n.length();
        while (end > 0 && (n.charAt(end - 1) == ' ' || n.charAt(end - 1) == 0)) {
            end--;
        }
        n = n.substring(0, end);
        if (n.isEmpty()) {
            throw new UnsupportedOperationException("a CHANNEL() with a blank name: not modelled");
        }
        if (n.startsWith("DFH")) {
            throw new UnsupportedOperationException("CHANNEL(" + n + "), a channel whose name starts DFH: not modelled");
        }
        for (int i = 0; i < n.length(); i++) {
            if (CHANNEL_CHARS.indexOf(n.charAt(i)) < 0) {
                return null;
            }
        }
        return n.length() > 16 ? null : n;
    }

    /** #4950: a copy of a channel's containers, under `name`. */
    private static Channel copyOf(Channel from, String name) {
        Channel ch = new Channel(name);
        from.containers.forEach((k, v) -> ch.containers.put(k, new Container(v.data.clone(), v.bit, v.ccsid)));
        return ch;
    }

    /** #4950: a RUN TRANSID child: its token, transaction, copy of the RUN's channel, number (RUN order), and what
     *  the scheduler made of it. */
    private static final class Child {
        private final String token;
        private final String transid;
        private final Channel channel;
        private final int number;
        private boolean dispatched;
        private boolean fetched;
        private boolean freed;
        private long completes;
        private String abcode;
        private Channel reply;

        private Child(String token, String transid, Channel channel, int number) {
            this.token = token;
            this.transid = transid;
            this.channel = channel;
            this.number = number;
        }
    }

    private Child kid(String token) {
        for (Child k : root().kids) {
            if (k.token.equals(token)) {
                return k;
            }
        }
        return null;
    }

    // #4950: the events a dispatched child may record -- any other is a region resource or a terminal's (R1). #5089:
    // its own RUN / FETCH / FREE CHILD and the CHILD events of its own children concern only the tasks it started
    private static final java.util.Set<Object> CHILD_EVENTS =
            java.util.Set.of("RETURN", "ABEND", "LINK", "XCTL", "RUN", "FETCH", "FREE-CHILD", "CHILD");
    /** #5089: how many generations below a task RUN children go: a child (1), its children (2), theirs (3); a RUN
     *  one level further is refused. A bound the harness states (IBM states none), the same in the C stub. */
    static final int MAX_RUN_DEPTH = 3;

    /** #4950 (X18, ASSUMED): this task waits (a DELAY, or a FETCH that waits): the RUN children not yet dispatched
     *  run now, in RUN order, each to its end before this task resumes (one quasi-reentrant TCB: a task keeps control
     *  until it waits; a task takes no processor time, X4). A child completes at its dispatch plus its own DELAYs. It
     *  is a non-terminal task: EIBTASKN this task's plus its RUN number (a stated fact, as the stub's), no COMMAREA, its
     *  current channel the copy RUN made. What it does is recorded as one CHILD event, compared as a whole. */
    private void dispatchChildren() {
        CicsTask task = root();
        for (Child k : task.kids) {
            if (k.dispatched || k.freed) {
                continue;
            }
            k.dispatched = true;
            String program = task.programs == null ? null : task.programs.program(k.transid);
            if (program == null) {
                throw new UnsupportedOperationException("child transaction " + k.transid + ": its program is not one "
                        + "the case runs, not modelled");
            }
            CicsTask c = new CicsTask(k.transid, "DFHNULL", null, null, Map.of())
                    .withClock(task.now)
                    .withPrograms(task.programs)
                    .withSnapshot(task.snapshot)
                    .withTaskNumber(task.taskNumber + k.number)
                    .withRunChild(true);
            c.applid = task.applid;
            c.sysid = task.sysid;
            c.dispatched = true;
            c.depth = task.depth + 1;
            if (k.channel != null) {
                c.withChannel(copyOf(k.channel, k.channel.name));
            }
            c.run(program);
            Map<String, Object> last = null;
            for (Map<String, Object> e : c.events) {
                if ("ABEND".equals(e.get("event"))) {
                    last = e;
                }
            }
            if (last != null && "terminated".equals(last.get("outcome"))) {
                k.abcode = (String) last.get("abcode");
            } else if (!c.abcode.isBlank()) {
                throw new UnsupportedOperationException("a RUN TRANSID child that went on after an abend (HANDLE "
                        + "ABEND): its completion status is not documented, not modelled");
            }
            k.completes = task.waited + c.waited;
            k.reply = c.currentChannel;
            List<Map<String, Object>> did = new ArrayList<>();
            for (Map<String, Object> e : c.events) {
                did.add(new LinkedHashMap<>(e));
            }
            if (c.currentChannel != null) {  // the containers it leaves, as the harness records a task's (X24)
                Map<String, Object> left = new LinkedHashMap<>();
                left.put("event", "CONTAINERS");
                left.put("channel", c.currentChannel.name);
                Map<String, String> data = new LinkedHashMap<>();
                c.currentChannel.containers().forEach((n, v) -> data.put(n,
                        java.util.HexFormat.of().withUpperCase().formatHex(v)));
                left.put("containers", data);
                did.add(left);
            }
            event("CHILD", "child", k.token, "transid", k.transid, "events", did);
        }
    }

    /** #4950: DELAY (IBM CICS TS, EXEC CICS DELAY) for `millis` milliseconds (delayMillis), -1 for a DELAY TIME or a
     *  value out of range. A task takes no time (X4): the delay ends at once, after the RUN children it dispatches;
     *  the scheduler's clock moves by it. In a task with RUN children, or in a child, a DELAY that is not a length
     *  of time is refused (what it means for the children's order is not modelled). */
    public void delay(long millis, String what) {
        CicsTask task = root();
        task.releasePost();  // #5079 (X63): IBM, POST: a subsequent DELAY ends the POST's timer-event control area
        if (millis < 0) {
            if (!task.kids.isEmpty() || task.dispatched) {
                throw new UnsupportedOperationException("DELAY in a task with RUN TRANSID children (or in a child): "
                        + what + ", not modelled");
            }
            return;
        }
        task.dispatchChildren();
        task.waited += millis;
    }

    /** #4950: a DELAY's length in milliseconds, -1 out of IBM's ranges (EXEC CICS DELAY): INTERVAL(hhmmss) with mm
     *  and ss 0 - 59; FOR HOURS(0 - 99) MINUTES(0 - 59) SECONDS(0 - 59) MILLISECS(0 - 999), or one of them alone:
     *  MINUTES(0 - 5999), SECONDS(0 - 359999), MILLISECS(0 - 359999999). `interval` null: the FOR form (each
     *  null: not given). */
    public static long delayMillis(Long interval, Long hours, Long minutes, Long seconds, Long millisecs) {
        if (interval != null) {
            long v = interval;
            if (v < 0 || v / 10000 > 99 || v / 100 % 100 > 59 || v % 100 > 59) {
                return -1;
            }
            return (v / 10000 * 3600 + v / 100 % 100 * 60 + v % 100) * 1000;
        }
        int given = (hours != null ? 1 : 0) + (minutes != null ? 1 : 0) + (seconds != null ? 1 : 0)
                + (millisecs != null ? 1 : 0);
        boolean one = given == 1;
        if (hours != null && (hours < 0 || hours > 99)
                || minutes != null && (minutes < 0 || minutes > (one ? 5999 : 59))
                || seconds != null && (seconds < 0 || seconds > (one ? 359999 : 59))
                || millisecs != null && (millisecs < 0 || millisecs > (one ? 359999999 : 999))) {
            return -1;
        }
        return ((hours == null ? 0 : hours) * 3600 + (minutes == null ? 0 : minutes) * 60
                + (seconds == null ? 0 : seconds)) * 1000 + (millisecs == null ? 0 : millisecs);
    }

    /** #4884: FETCH CHILD(token) / FETCH ANY NOSUSPEND, as fetch(child, "NOSUSPEND", 0, false). */
    public FetchResult fetch(String child) {
        return fetch(child, "NOSUSPEND", 0, false);
    }

    /** #4884, #4950: FETCH ANY / FETCH CHILD(token) (IBM CICS TS, EXEC CICS FETCH); `child` null: FETCH ANY. `mode`
     *  NOSUSPEND, WAIT (neither NOSUSPEND nor TIMEOUT) or TIMEOUT (`timeout` milliseconds). INVREQ 52 for FETCH ANY in
     *  a task with no children, INVREQ 50 for a token that is not a child's or was freed. A FETCH that waits dispatches
     *  the children not yet run (dispatchChildren). At the scheduler's time T a child that completed before T is
     *  fetched -- FETCH ANY the first to complete, RUN order on a tie (ASSUMED) -- else NOSUSPEND is NOTFINISHED 52,
     *  WAIT resumes when it completes, TIMEOUT is NOTFINISHED 53 when none completes before T + timeout. A completion
     *  at the very instant the answer turns on is a tie IBM does not order: refused. On NORMAL: the token (ANY), the
     *  completion status (NORMAL / ABEND, with the abend code), and with `wantChannel` the child's channel as it left
     *  it, under a name of the harness's own in this program's scope (IBM generates it). */
    public FetchResult fetch(String child, String mode, long timeout, boolean wantChannel) {
        CicsTask task = root();
        if ("TIMEOUT".equals(mode) && (timeout < 0 || timeout > 4080000)) {
            throw new UnsupportedOperationException("FETCH TIMEOUT(" + timeout + "): outside 0 to 4080000 "
                    + "milliseconds (IBM's FETCH ANY and FETCH CHILD pages give different maximums), not modelled");
        }
        int[] planned = child == null ? task.injected("FETCH-ANY", "-") : null;  // #6882 (X18): nothing is fetched
        if (planned != null) {
            return fetched(respName(planned[0]), planned[1], null, null);
        }
        Child one = null;
        if (child != null) {
            one = kid(child);
            if (one == null || one.freed) {
                return fetched("INVREQ", 50, null, null);
            }
            if (one.fetched) {
                throw new UnsupportedOperationException("FETCH CHILD of a child already fetched (INVREQ 51 is for its "
                        + "channel, fetched again): what IBM answers is not documented, not modelled");
            }
        } else if (task.children == 0) {
            return fetched("INVREQ", 52, null, null);
        }
        if (!"NOSUSPEND".equals(mode)) {
            task.dispatchChildren();
        }
        Child first = null;
        boolean any = false;
        for (Child k : task.kids) {
            if (one != null ? k != one : k.fetched || k.freed) {
                continue;
            }
            any = true;
            if (k.dispatched && (first == null || k.completes < first.completes)) {
                first = k;
            }
        }
        if (!any) {
            return fetched("NOTFND", 1, null, null);
        }
        long now = task.waited;
        if ("NOSUSPEND".equals(mode)) {
            if (first == null || first.completes > now) {
                return fetched("NOTFINISHED", 52, null, null);
            }
            if (first.completes == now) {
                throw tie();
            }
        } else if ("TIMEOUT".equals(mode)) {
            if (first.completes == now + timeout) {
                throw tie();
            }
            if (first.completes > now + timeout) {
                task.waited = now + timeout;
                return fetched("NOTFINISHED", 53, null, null);
            }
            task.waited = Math.max(now, first.completes);
        } else {
            task.waited = Math.max(now, first.completes);
        }
        first.fetched = true;
        String reply = null;
        if (wantChannel) {
            if (first.reply == null) {
                throw new UnsupportedOperationException("FETCH CHANNEL of a child that left no current channel: not "
                        + "modelled");
            }
            reply = String.format(java.util.Locale.ROOT, "GGREPLY%09d", ++task.replies);
            channels.put(reply, copyOf(first.reply, reply));
        }
        return fetched("NORMAL", 0, first, reply);
    }

    private static UnsupportedOperationException tie() {
        return new UnsupportedOperationException("a FETCH whose answer turns on a child completing at the instant its "
                + "parent resumed from a wait (a tie IBM does not order): not modelled");
    }

    private FetchResult fetched(String resp, int resp2, Child k, String reply) {
        Map<String, Object> e = new LinkedHashMap<>();
        e.put("event", "FETCH");
        e.put("resp", resp);
        e.put("resp2", resp2);
        if (k != null) {
            e.put("child", k.token);
            e.put("compstatus", k.abcode == null ? "NORMAL" : "ABEND");
            e.put("abcode", k.abcode);
            e.put("channel", reply);
        }
        add(e);
        return k == null ? new FetchResult(resp, resp2)
                : new FetchResult(resp, resp2, k.token, reply, k.abcode, k.abcode == null ? 1016 : 900);
    }

    /** #4884, #4950: a FETCH's condition and RESP2; on NORMAL the child's token, the reply channel's name (null when
     *  not asked), its abend code (null: it completed normally) and COMPSTATUS's CVDA (NORMAL 1016, ABEND 900). */
    public record FetchResult(String resp, int resp2, String child, String channel, String abcode, int compstatus) {
        public FetchResult(String resp, int resp2) {
            this(resp, resp2, null, null, null, 0);
        }
    }

    /** #4950: FREE CHILD(token) (IBM CICS TS, EXEC CICS FREE CHILD): the token is freed -- a later FETCH CHILD of it
     *  is INVREQ 50 and FETCH ANY passes it by. INVREQ 50 for a token that is not a child's or was freed; freeing a
     *  child already fetched is refused (IBM does not say). */
    public FetchResult freeChild(String child) {
        Child k = kid(child);
        String resp = "NORMAL";
        int resp2 = 0;
        if (k == null || k.freed) {
            resp = "INVREQ";
            resp2 = 50;
        } else if (k.fetched) {
            throw new UnsupportedOperationException("FREE CHILD of a child already fetched: not modelled");
        } else {
            k.freed = true;
        }
        event("FREE-CHILD", "resp", resp, "resp2", resp2);
        return new FetchResult(resp, resp2);
    }

    /** #4270: a RUN TRANSID's outcome: its condition, RESP2 and the child token (null unless NORMAL). */
    public record RunResult(String resp, int resp2, String child) {
    }

    /** RETRIEVE INTO LENGTH(maxLength) (#4006, IBM EXEC CICS RETRIEVE): the next data record of the requests
     *  the task was started for, truncated with LENGERR when longer (the length is then the record's own);
     *  ENDDATA when none is left, as for a task no START started. */
    public RetrieveResult retrieve(int maxLength) {
        return retrieve(Integer.valueOf(maxLength), false, false, false);
    }

    /** #4270: RETRIEVE [INTO LENGTH(maxLength)] [RTRANSID] [RTERMID] [QUEUE] (IBM CICS TS, EXEC CICS RETRIEVE):
     *  `maxLength` null without INTO. The next data record: ENDDATA when none is left; ENVDEFERR when the command
     *  names RTRANSID / RTERMID / QUEUE and the record's START did not give it ("occurs when a RETRIEVE command
     *  specifies an option not specified by the corresponding START command"); else FROM's data truncated to
     *  maxLength with LENGERR, and the values asked for. What IBM does not say is refused: INTO for a record whose
     *  START gave no FROM, and any RETRIEVE after an ENVDEFERR (whether that record was used up). */
    public RetrieveResult retrieve(Integer maxLength, boolean rtransid, boolean rtermid, boolean queue) {
        CicsTask task = root();
        if (task.runChild) {
            throw new UnsupportedOperationException("RETRIEVE in a RUN TRANSID child task: not documented");
        }
        if (task.retrieveRefused) {
            throw new UnsupportedOperationException("RETRIEVE after ENVDEFERR: whether the record is still there is "
                    + "not documented");
        }
        int[] planned = task.injected("RETRIEVE", "-");  // #4049: a planned condition; nothing is retrieved
        if (planned != null) {
            event("RETRIEVE", "resp", respName(planned[0]), "length", null, "data", null);
            return new RetrieveResult(respName(planned[0]), -1, null);
        }
        if (task.retrieved >= task.retrieveData.size()) {
            event("RETRIEVE", "resp", "ENDDATA", "length", null, "data", null);
            return new RetrieveResult("ENDDATA", -1, null);
        }
        StartData record = task.retrieveData.get(task.retrieved);
        if (maxLength != null && record.from() == null) {
            throw new UnsupportedOperationException("RETRIEVE INTO the record of a START with no FROM: whether that "
                    + "is ENVDEFERR is not documented");
        }
        if ((rtransid && record.rtransid() == null) || (rtermid && record.rtermid() == null)
                || (queue && record.queue() == null)) {
            task.retrieveRefused = true;
            event("RETRIEVE", "resp", "ENVDEFERR", "length", null, "data", null);
            return new RetrieveResult("ENVDEFERR", -1, null);
        }
        task.retrieved++;
        byte[] stored = record.from();
        byte[] data = null;
        String resp = "NORMAL";
        if (maxLength != null) {
            data = stored.length > maxLength ? Arrays.copyOf(stored, Math.max(maxLength, 0)) : stored.clone();
            resp = stored.length > maxLength ? "LENGERR" : "NORMAL";
        }
        Map<String, Object> e = new LinkedHashMap<>();
        e.put("event", "RETRIEVE");
        e.put("resp", resp);
        e.put("length", maxLength == null ? null : stored.length);
        e.put("data", data);
        if (rtransid) {
            e.put("rtransid", record.rtransid());
        }
        if (rtermid) {
            e.put("rtermid", record.rtermid());
        }
        if (queue) {
            e.put("queue", record.queue());
        }
        add(e);
        return new RetrieveResult(resp, maxLength == null ? -1 : stored.length, data,
                rtransid ? record.rtransid() : null, rtermid ? record.rtermid() : null, queue ? record.queue() : null);
    }

    /** A RETRIEVE's outcome: its condition, the LENGTH it sets (-1 when none), the data moved INTO, and (#4270) the
     *  RTRANSID / RTERMID / QUEUE values it returns (null when not asked for or not returned). */
    public record RetrieveResult(String resp, int length, byte[] data, String rtransid, String rtermid, String queue) {
        public RetrieveResult(String resp, int length, byte[] data) {
            this(resp, length, data, null, null, null);
        }
    }

    /** CANCEL REQID(reqid) (#4006, IBM EXEC CICS CANCEL): NORMAL for a request that has not expired yet (the
     *  harness then drops it), NOTFND when none matches "an unexpired interval control command". */
    public String cancel(String reqid) {
        CicsTask task = root();
        int[] planned = task.injected("CANCEL", reqid.stripTrailing());  // #4049: a planned condition
        if (planned != null) {
            event("CANCEL", "reqid", reqid, "resp", respName(planned[0]));
            return respName(planned[0]);
        }
        LocalDateTime at = task.ownRequests.containsKey(reqid) ? task.ownRequests.get(reqid) : task.unexpired.get(reqid);
        String resp = at != null && at.isAfter(now()) ? "NORMAL" : "NOTFND";
        if ("NORMAL".equals(resp)) {
            task.ownRequests.remove(reqid);
            if (reqid.equals(task.postReqid)) {
                task.postCancelled();  // #5079 (X63): IBM, POST: a CANCEL of the POST posts its area
            }
        }
        event("CANCEL", "reqid", reqid, "resp", resp);
        return resp;
    }

    // ---- #5079 (register X63): POST and WAIT EVENT -- a timer-event control area, on the stated clock -------------------
    private long postBlock;  // the live POST's area (a block of task storage), 0 when none
    private LocalDateTime postAt;  // when it expires
    private String postReqid;  // its REQID
    private int postSeq;  // the REQIDs CICS generated (POST with no REQID)
    private final java.util.Set<Long> postAreas = new java.util.HashSet<>();  // every area a POST made
    private final java.util.Set<Long> postReleased = new java.util.HashSet<>();  // those a later command ended

    /** A POST's outcome: its condition, RESP2, the handle of the new area (0: none) and the REQID it runs under. */
    public record PostResult(String resp, int resp2, long handle, String reqid) {
    }

    /** POST INTERVAL(hhmmss) | TIME(hhmmss) | AFTER / AT HOURS MINUTES SECONDS [SET(ptr)] [REQID] (IBM CICS TS, EXEC CICS
     *  POST): "This 4-byte control area is initialized to binary zeros" and posted ("its first byte is set to X'40' and
     *  its third byte to X'80'") when the time expires or the POST is CANCELled. `how` INTERVAL, TIME, AFTER or AT
     *  (the hours, minutes, seconds null when not given). INVREQ RESP2 4 / 5 / 6 for hours, minutes, seconds out of
     *  range; EXPIRED for a TIME already past (nothing is made). A task takes no time (X4), so the area is posted only
     *  by a WAIT EVENT, which runs the clock to the expiry, or by a CANCEL. A POST with no REQID runs under POSTnnnn
     *  (ASSUMED: IBM "generates one"). A task has one live POST: a later POST, a local START or a DELAY ends it. */
    public PostResult post(String how, int hhmmss, Integer hours, Integer minutes, Integer seconds, String reqid) {
        CicsTask task = root();
        int resp2 = 0;
        if ("AFTER".equals(how) || "AT".equals(how)) {
            hhmmss = hhmmss(hours, minutes, seconds);
            if (hhmmss < 0) {
                resp2 = -hhmmss;
            }
        } else if (hhmmss < 0 || hhmmss / 10000 > 99) {
            resp2 = 4;
        } else if (hhmmss / 100 % 100 > 59) {
            resp2 = 5;
        } else if (hhmmss % 100 > 59) {
            resp2 = 6;
        }
        if (resp2 != 0) {
            return new PostResult("INVREQ", resp2, 0, reqid);
        }
        LocalDateTime clock = now();
        int hh = hhmmss / 10000, mm = hhmmss / 100 % 100, ss = hhmmss % 100;
        LocalDateTime at;
        if ("TIME".equals(how) || "AT".equals(how)) {
            at = clock.toLocalDate().atStartOfDay().plusHours(hh).plusMinutes(mm).plusSeconds(ss);
            if (hh <= 23 && at.isBefore(clock)) {
                return new PostResult("EXPIRED", 0, 0, reqid);
            }
        } else {
            at = clock.plusSeconds(hh * 3600L + mm * 60L + ss);
        }
        String id = reqid == null ? String.format(java.util.Locale.ROOT, "POST%04d", ++task.postSeq) : reqid;
        task.releasePost();
        task.postBlock = acquireSet(null, new byte[4]);
        task.postAt = at;
        task.postReqid = id;
        task.postAreas.add(task.postBlock);
        task.ownRequests.put(id, at);
        return new PostResult("NORMAL", 0, task.postBlock, id);
    }

    private void releasePost() {
        if (postBlock != 0) {
            postReleased.add(postBlock);
            ownRequests.remove(postReqid);
            postBlock = 0;
            postReqid = null;
        }
    }

    private void postArea(long handle) {
        byte[] b = blocks.get(handle).bytes;
        b[0] = 0x40;
        b[2] = (byte) 0x80;
    }

    private void postCancelled() {
        postArea(postBlock);
        releasePost();
    }

    /** WAIT EVENT ECADDR(ptr) (IBM CICS TS, EXEC CICS WAIT EVENT): {RESP, RESP2}. INVREQ RESP2 2 for a null pointer. An
     *  area not yet posted is posted at its expiry: the RUN children not yet run are dispatched and the scheduler's
     *  clock runs to the expiry (a task takes no time, X4). An area already posted returns at once (ASSUMED: IBM does
     *  not say). Refused: an address that is no POST's area, an area a later POST, CANCEL, local START or DELAY ended
     *  (IBM: "unpredictable"). */
    public int[] waitEvent(long handle) {
        CicsTask task = root();
        if (handle == 0) {
            return new int[] {16, 2};
        }
        if (!task.postAreas.contains(handle)) {
            throw refused("WAIT EVENT on an address that is no POST's timer-event control area");
        }
        if (task.postReleased.contains(handle)) {
            throw refused("WAIT EVENT on a timer-event control area a later POST, CANCEL, START or DELAY ended");
        }
        if (task.blocks.get(handle).bytes[0] != 0x40) {
            task.dispatchChildren();
            task.waited += Math.max(0L, java.time.Duration.between(now(), task.postAt).toMillis());
            task.postArea(handle);
            task.ownRequests.remove(task.postReqid);
        }
        return new int[] {0, 0};
    }

"""
