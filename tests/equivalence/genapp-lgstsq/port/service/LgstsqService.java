package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.dto.contract.LgstsqDfhcommarea;
import com.gitgalaxy.modernized.messaging.TempStorage;
import com.gitgalaxy.modernized.messaging.TransientData;
import org.springframework.transaction.annotation.Transactional;

/**
 * Response handling (field testing: field-tested (6 public / 0 private estates)):
 * COBOL: the RESP of ASSIGN at line 60 (paragraph MAINLINE) is never tested
 * COBOL: the RESP of ASSIGN at line 64 (paragraph MAINLINE) is never tested
 * COBOL: the RESP of RECEIVE at line 73 (paragraph MAINLINE) is never tested
 * COBOL: the RESP of WRITEQ at line 94 (paragraph MAINLINE) is never tested
 * COBOL: the RESP of WRITEQ at line 105 (paragraph MAINLINE) is never tested
 */
@Service
@Transactional
@RequiredArgsConstructor
public class LgstsqService {

    private static final Logger log = LoggerFactory.getLogger(LgstsqService.class);

    /** Register X6: a WRITEQ LENGTH that runs past its FROM area (the equivalence runner matches the name). */
    static final class PastFrom extends UnsupportedOperationException {
        PastFrom(String message) {
            super(message);
        }
    }

    private final TempStorage tempStorage;
    private final TransientData transientData;

    /** This program's run at a LINK / XCTL level (#4004): task.level(), task.eibcalen(). */
    public void runTask(CicsTask task) {
        log.info("Lgstsq: runTask");

        // WS-RECV-LEN PIC S9(4) COMP VALUE 80
        int wsRecvLen = 80;
        char flag;
        String stdqName = "CSMT";

        // MAINLINE: MOVE SPACES TO WRITE-MSG / WS-RECV
        String sysid;
        String msg;               // WRITE-MSG-MSG, PIC X(90)
        String fillerX = " ";     // FILLER-X, PIC X

        // MAINLINE: EXEC CICS ASSIGN SYSID(WRITE-MSG-SYSID) RESP(WS-RESP) -- RESP never tested
        sysid = pad(task.assignSysid(), 4);

        // MAINLINE: EXEC CICS ASSIGN INVOKINGPROG(WS-INVOKEPROG) RESP(WS-RESP) -- RESP never tested
        String invokeProg = pad(task.invokingProgram(), 8);

        // MAINLINE: IF WS-INVOKEPROG NOT = SPACES
        if (!invokeProg.isBlank()) {
            flag = 'C';
            // MOVE COMMA-DATA TO WRITE-MSG-MSG
            String commaData = "";
            if (task.hasCommarea()) {
                LgstsqDfhcommarea ca = task.commarea(LgstsqDfhcommarea.class);
                commaData = ca == null ? "" : ca.getCaData();
            }
            msg = pad(commaData, 90);
            // MOVE EIBCALEN TO WS-RECV-LEN (null: the whole record, 99 bytes per the DTO)
            Integer calen = task.eibcalen();
            wsRecvLen = trunc4(calen == null ? 99 : calen);
        } else {
            // MAINLINE: EXEC CICS RECEIVE INTO(WS-RECV) LENGTH(WS-RECV-LEN) RESP(WS-RESP) -- RESP never tested
            CicsTask.Received rcv = task.receive(wsRecvLen, false);
            String data = rcv.data() == null ? "" : rcv.data();
            wsRecvLen = trunc4(rcv.length());
            // WS-RECV is 79 bytes: TRANID X(5) + DATA X(74)
            String recv = pad(data, 79);
            flag = 'R';
            // MOVE WS-RECV-DATA TO WRITE-MSG-MSG
            msg = pad(recv.substring(5), 90);
            // SUBTRACT 5 FROM WS-RECV-LEN
            wsRecvLen = trunc4(wsRecvLen - 5);
        }

        // MAINLINE: MOVE 'GENAERRS' TO STSQ-NAME
        String stsqName = "GENAERRS";
        // MAINLINE: IF WRITE-MSG-MSG(1:2) = 'Q='
        if (msg.startsWith("Q=")) {
            // MOVE WRITE-MSG-MSG(3:4) TO STSQ-EXT
            stsqName = "GENA" + msg.substring(2, 6);
            // MOVE WRITE-MSG-REST TO TEMPO (WRITE-MSG-REST = bytes 13-95 of WRITE-MSG = MSG(8:83))
            String tempo = pad(msg.substring(7, 90), 90);
            // MOVE TEMPO TO WRITE-MSG-MSG
            msg = tempo;
            // SUBTRACT 7 FROM WS-RECV-LEN
            wsRecvLen = trunc4(wsRecvLen - 7);
        }

        // MAINLINE: ADD 5 TO WS-RECV-LEN
        wsRecvLen = trunc4(wsRecvLen + 5);

        String writeMsg = sysid + fillerX + msg;   // WRITE-MSG, 95 bytes
        // LENGTH(WS-RECV-LEN) bytes of WRITE-MSG. A LENGTH past the 95 bytes writes WRITE-MSG and then spaces up to
        // LENGTH, as the oracle's stub does (register X6, ASSUMED: CICS writes the storage that follows).
        String sent = wsRecvLen <= 0 ? "" : pad(writeMsg, wsRecvLen);

        // MAINLINE: EXEC CICS WRITEQ TD QUEUE(STDQ-NAME) FROM(WRITE-MSG) LENGTH(WS-RECV-LEN) -- RESP never tested
        // TODO: LENGTH below 1 is LENGERR on CICS (nothing written); writeqTd cannot express that, "" is passed.
        task.writeqTd(stdqName, sent);

        // MAINLINE: EXEC CICS WRITEQ TS QUEUE(STSQ-NAME) FROM(WRITE-MSG) NOSUSPEND LENGTH(WS-RECV-LEN) -- RESP never tested
        // A TS item is the region's bytes: CICS's default CCSID 037, as the oracle's stub writes it (#4528)
        task.writeqTs(stsqName, sent.getBytes(java.nio.charset.Charset.forName("IBM037")));

        // MAINLINE: IF WS-FLAG = 'R' EXEC CICS SEND TEXT FROM(FILLER-X) WAIT ERASE LENGTH(1) FREEKB
        if (flag == 'R') {
            task.sendText(fillerX, 1, "WAIT", "ERASE", "FREEKB");
        }

        // MAINLINE: EXEC CICS RETURN
        task.returnTransid(null, null);
        // A-EXIT: EXIT / GOBACK are never reached after RETURN.
    }

    /** MOVE to PIC X(n): pad with spaces or truncate on the right. */
    private static String pad(String s, int n) {
        String v = s == null ? "" : s;
        if (v.length() >= n) {
            return v.substring(0, n);
        }
        return v + " ".repeat(n - v.length());
    }

    /** Store in PIC S9(4) COMP: high-order digits are lost, the sign is kept. */
    private static int trunc4(int v) {
        return v % 10000;
    }

    /** Another program LINKed / XCTLed to this one (#4343): the program at that level in the region
     *  (CicsTask.region()), run through runTask on `request`, passed by reference -- what it changes, the caller sees. */
    public LgstsqDfhcommarea handleLink(LgstsqDfhcommarea request) {
        log.info("Lgstsq: handleLink");
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.linked("LGSTSQ", request);
        region.run(task, "LGSTSQ", this::runTask);
        return request;
    }

    /** #5053: handleLink with the raw bytes of the LINK's COMMAREA (passed by address: what the program
     *  leaves there the caller sees); lastLinkBytes() then answers the bytes it left. */
    public LgstsqDfhcommarea handleLink(LgstsqDfhcommarea request, byte[] area) {
        log.info("Lgstsq: handleLink (bytes)");
        CicsTask.Region region = CicsTask.region();
        CicsTask task = region.linked("LGSTSQ", request, area);
        region.run(task, "LGSTSQ", this::runTask);
        byte[] left = task.linkAreaView();
        lastLinkBytes = task.linkAreaTaken() && left != null ? java.util.Arrays.copyOf(left, left.length) : null;
        return request;
    }

    // @facade-helper: the bytes the last byte-carrying handleLink's program left in the COMMAREA
    private byte[] lastLinkBytes;

    /** The bytes the last byte-carrying handleLink's program left in the LINK COMMAREA (a copy; null: it took
     *  none -- its DTO is the COMMAREA). @facade-helper */
    public byte[] lastLinkBytes() {
        return lastLinkBytes == null ? null : java.util.Arrays.copyOf(lastLinkBytes, lastLinkBytes.length);
    }

    /** EXEC CICS WRITEQ TS QUEUE(STSQ-NAME) FROM(WRITE-MSG) at base/src/lgstsq.cbl:105 (#3620).
     *  CICS resources field testing: open (5 public / 0 private estates). */
    protected int writeqTsGenaerrsL105(String record) {
        return tempStorage.writeItem("GENAERRS", record);
    }

    /** EXEC CICS WRITEQ TD QUEUE(STDQ-NAME) FROM(WRITE-MSG) at base/src/lgstsq.cbl:94 (#3620).
     *  Route: log -- a CICS-supplied log destination.
     *  CICS resources field testing: open (5 public / 0 private estates). */
    protected void writeqTdCsmtL94(String record) {
        transientData.write("CSMT", record);
    }

}
