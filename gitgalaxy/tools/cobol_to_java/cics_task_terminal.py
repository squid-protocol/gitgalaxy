#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: CicsTask's terminal support (RECEIVE MAP, terminal RECEIVE, CONVERSE, SEND CONTROL, split out by #5274)
#
# PURPOSE:
# The terminal part of the CICS task runtime the transaction forge emits (CICS_TASK_JAVA): RECEIVE MAP, the task's terminal
# input (withTerminalInput, withEndOfChain), the unformatted and NOTRUNCATE RECEIVE (#4005, #4413), CONVERSE (#5079, X63),
# SEND CONTROL and the Received record. The forge splices it into CicsTask where it always sat, so the class is byte-identical.
# ==============================================================================

TERMINAL_JAVA = """\
    /** RECEIVE MAP: the screen the user sent, or empty (MAPFAIL) when nothing was received. */
    public <T> Optional<T> receive(String map, Class<T> type) {
        return receive(map, null, type);
    }

    /** RECEIVE MAP(map) MAPSET(mapset), recorded as an event with its RESP (NORMAL, or MAPFAIL when empty). */
    public <T> Optional<T> receive(String map, String mapset, Class<T> type) {
        mapInputAfterUctranstSet();
        Optional<T> screen = Optional.ofNullable(received.get(map)).map(type::cast);
        event("RECEIVE-MAP", "map", map, "mapset", mapset, "resp", screen.isPresent() ? "NORMAL" : "MAPFAIL");
        return screen;
    }

    /** What the operator typed on a cleared screen with the key that started the task (#4005), which an
     *  unformatted RECEIVE returns; null when nothing was transmitted. */
    public CicsTask withTerminalInput(String text) {
        this.terminalInput = text;
        return this;
    }

    /** The task's terminal input was already read by an earlier program of the task (#4005). */
    public void terminalInputRead() {
        this.terminalRead = true;
    }

    /** #4413: the terminal is an SNA 3270 display logical unit (CSD DEVICE(LUTYPE2)), not a 3270 logical unit: the
     *  input message it sends is one chain, so the RECEIVE that returns its last byte raises EOC (IBM, EXEC CICS
     *  RECEIVE (LUTYPE2/LUTYPE3): EOC "occurs when a request/response unit (RU) is received with end-of-chain-
     *  indicator set"; RECEIVE (3270 logical) has no EOC). EOC's default action is to ignore it. */
    public CicsTask withEndOfChain(boolean lutype2) {
        this.endOfChain = lutype2;
        return this;
    }

    /** RECEIVE INTO LENGTH(maxLength) (#4005): the terminal input, unformatted, read once per task. Input
     *  longer than maxLength is truncated to it and raises LENGERR, and the length is then the input's full
     *  length (IBM, EXEC CICS RECEIVE: "the data area specified in the LENGTH option is set to the original
     *  length of data"). */
    public Received receiveText(int maxLength) {
        return receive(maxLength, false);
    }

    /** #4413: a terminal RECEIVE [INTO | SET] [LENGTH] [MAXLENGTH] [NOTRUNCATE] (IBM, EXEC CICS RECEIVE (3270
     *  logical) and (LUTYPE2/LUTYPE3)). `maxLength` is the most the program takes -- MAXLENGTH, else LENGTH's value,
     *  else INTO's length; below zero, zero ("If the value specified is less than zero, zero is assumed"). Longer
     *  input: under NOTRUNCATE the first maxLength bytes, NORMAL, the length the data returned, and "CICS retains the
     *  remaining data and uses it to satisfy subsequent RECEIVE commands"; else truncated, LENGERR, and the length the
     *  original one. The operator's input is read once per task: a RECEIVE with nothing retained would wait for more
     *  input, which a task here cannot get (refused). On an LUTYPE2 terminal (withEndOfChain) the RECEIVE returning
     *  the input's last byte raises EOC instead of NORMAL; whether one that leaves data retained does is not
     *  documented, and is refused. */
    public Received receive(int maxLength, boolean notruncate) {
        inputAfterUctranstSet();
        CicsTask task = root();  // the terminal is the task's, whichever level reads it
        String text;
        if (task.terminalRest != null) {
            text = task.terminalRest;
            task.terminalRest = null;
        } else if (task.terminalRead) {
            throw new IllegalStateException("a second terminal RECEIVE waits for more input from the operator");
        } else {
            task.terminalRead = true;
            text = task.terminalInput == null ? "" : task.terminalInput;
        }
        int max = Math.max(maxLength, 0);
        String data = text.length() > max ? text.substring(0, max) : text;
        String resp;
        int length;
        if (text.length() > max && notruncate) {
            if (task.endOfChain) {
                throw new IllegalStateException("RECEIVE NOTRUNCATE on an LUTYPE2 terminal leaving data retained: "
                        + "whether it raises EOC is not documented");
            }
            task.terminalRest = text.substring(max);
            resp = "NORMAL";
            length = max;
        } else if (text.length() > max) {
            resp = "LENGERR";
            length = text.length();
        } else {
            resp = task.endOfChain ? "EOC" : "NORMAL";
            length = text.length();
        }
        event("RECEIVE", "resp", resp, "length", length, "data", data);
        return new Received(resp, length, data);
    }

    /** #5079 (X63): CONVERSE FROM FROMLENGTH INTO ... (IBM, EXEC CICS CONVERSE (default)): the data written to the terminal,
     *  recorded as a plain SEND records it (`text`, `length` as the program gave them), then the terminal RECEIVE of the
     *  reply (`maxLength`, `notruncate` as receive). A negative FROMLENGTH is LENGERR with nothing sent and nothing read
     *  (ASSUMED: IBM calls the value out of range; the length it returns is -1: no TOLENGTH is set). Refused: an LUTYPE2
     *  terminal (its reply's last byte raises EOC, which IBM does not list for CONVERSE). */
    public Received converse(String text, int length, int maxLength, boolean notruncate) {
        if (root().endOfChain) {
            throw refused("CONVERSE on an LUTYPE2 terminal (the reply would raise EOC, which IBM does not list for CONVERSE)");
        }
        if (length < 0) {
            return new Received("LENGERR", -1, null);
        }
        sendText(text, length);
        return receive(maxLength, notruncate);
    }

    /** #4413: SEND CONTROL with its options (ERASE, ERASEAUP, FREEKB, ALARM, FRSET; CURSOR with `cursor`, its
     *  offset, else null). It sends device controls only; none of its conditions (IBM, EXEC CICS SEND CONTROL:
     *  INVREQ for a BMS logical message, partitions, LDCs, SET / PAGING) can arise for a task's plain terminal. */
    public void sendControl(Integer cursor, String... options) {
        List<String> opts = new ArrayList<>(List.of(options));
        Collections.sort(opts);
        event("SEND-CONTROL", "options", opts, "cursor", cursor);
    }

    /** A terminal RECEIVE's outcome: its condition, the LENGTH it sets, and the data it moved INTO. */
    public record Received(String resp, int length, String data) {
    }

"""
