#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: CicsTask's fault injection (#4023, #4623, #6271, split out by #5274)
#
# PURPOSE:
# The faults family of the CICS task runtime the transaction forge emits (CICS_TASK_JAVA): withFaults (the equivalence
# harness's injected conditions), injected (the plan lookup, counted per command and resource), the planned DUPKEY
# held back for the read (dupkeyOr), the fault / abend log (logFault, logAbend) and planned (the {RESP, RESP2} of a
# SEND-MAP / RECEIVE-MAP / SYNCPOINT / ROLLBACK). The forge splices FAULTS_JAVA into CicsTask as one span, so the class
# holds the same members in a different order.
# ==============================================================================

FAULTS_JAVA = """\
    /** #4023 follow-up: the equivalence harness's injected conditions for this task, as its stub reads them
     *  (faults.cfg: `CMD FILE NTH RESP [RESP2]`, NTH `*` = every one; DFHRESP numbers), and the file each one
     *  that fires is appended to (`CMD FILE NTH RESP RESP2`). Commands are counted per task. */
    public CicsTask withFaults(List<String> plan, java.nio.file.Path log) {
        List<String[]> parsed = new ArrayList<>();
        for (String line : plan) {
            String[] w = line.trim().split("[ ]+");
            if (w.length >= 4) {
                parsed.add(w);
            }
        }
        this.faultPlan = List.copyOf(parsed);
        this.faultLog = log;
        return this;
    }

    /** #4623: a planned DUPKEY (15) is not a failure of the read: IBM retrieves the record through the non-unique
     *  alternate index and answers DUPKEY (RESP2 140) because another with the same key follows. So `injected`
     *  holds it back (the read runs), and a read that did find a record asks here for its outcome. */
    private int[] deferredDupkey;  // {n, resp, resp2} of the plan line, and its command and file
    private String deferredWhat;

    private int[] dupkeyOr() {
        if (deferredDupkey == null) {
            return new int[] {0, 0};
        }
        int[] d = deferredDupkey;
        deferredDupkey = null;
        logFault(deferredWhat, d[0], d[1], d[2]);
        return new int[] {d[1], d[2]};
    }

    private void logFault(String what, int n, int resp, int resp2) {
        if (faultLog != null) {
            try {
                java.nio.file.Files.writeString(faultLog, what + " " + n + " " + resp + " " + resp2
                        + System.lineSeparator(), java.nio.file.StandardOpenOption.CREATE,
                        java.nio.file.StandardOpenOption.APPEND);
            } catch (java.io.IOException e) {
                throw new java.io.UncheckedIOException(e);
            }
        }
    }

    private void logAbend(String what, int n, String code) {
        if (faultLog != null) {
            try {
                java.nio.file.Files.writeString(faultLog, what + " " + n + " ABEND " + code
                        + System.lineSeparator(), java.nio.file.StandardOpenOption.CREATE,
                        java.nio.file.StandardOpenOption.APPEND);
            } catch (java.io.IOException e) {
                throw new java.io.UncheckedIOException(e);
            }
        }
    }

    private int[] injected(String cmd, String file) {
        if (faultPlan.isEmpty()) {
            return null;
        }
        int n = faultSeen.merge(cmd + " " + file, 1, Integer::sum);
        deferredDupkey = null;
        for (String[] f : faultPlan) {
            if (f[0].equals(cmd) && f[1].equals(file) && ("*".equals(f[2]) || Integer.parseInt(f[2]) == n)) {
                int resp = Integer.parseInt(f[3]);
                int resp2 = f.length > 4 ? Integer.parseInt(f[4]) : 0;
                if (resp == -1 && f.length > 5) {  // #6271 (X70): `CMD FILE NTH -1 0 ABCODE` abends the task, as the stub
                    CicsTask at = running == null ? this : running;  // #6882: the level of the program that issued it
                    String exit = at.abend(f[5], "system", null, false);
                    if (exit != null) {
                        at.unwoundTo = exit;  // the exit at this level: the port reads it with abendExit()
                    }
                    logAbend(cmd + " " + file, n, f[5]);
                    return new int[] {0, 0};
                }
                if (resp == 15) {  // DUPKEY: the read goes on, see dupkeyOr
                    deferredDupkey = new int[] {n, resp, resp2};
                    deferredWhat = cmd + " " + file;
                    return null;
                }
                logFault(cmd + " " + file, n, resp, resp2);
                return new int[] {resp, resp2};
            }
        }
        return null;
    }

    /** #6271 (register X71): the {RESP, RESP2} a scenario's fault plan gives this SEND-MAP / RECEIVE-MAP (`name` the map),
     *  SYNCPOINT or ROLLBACK (`name` "-") -- {0, 0} when none: the command then runs, and a planned one is not performed. */
    public int[] planned(String cmd, String name) {
        int[] p = root().injected(cmd, name);
        return p == null ? new int[] {0, 0} : p;
    }

"""
