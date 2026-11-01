package com.gitgalaxy.modernized.cobolrt.cics;

import com.gitgalaxy.modernized.cics.CicsTask;
import com.gitgalaxy.modernized.cobolrt.Field;
import com.gitgalaxy.modernized.cobolrt.mq.QueueManager;
import java.io.IOException;
import java.nio.file.Path;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/** #4892: the MQI calls a deterministic port makes (`CALL 'MQGET' USING ...`, every item BY REFERENCE: det/mq.py), each
 *  on the queue manager of the CICS task (cobolrt.mq.QueueManager, the twin of tests/equivalence/mq/ggmq.c). The queue manager is
 *  the task's resource "mq", joined to its unit of work; a task with none refuses the call by name, as the stub does. */
public final class DetMq {
    private DetMq() {
    }

    /** The runner's: the task's queue manager, from the case's mq.cfg, committed and backed out with the task (W5). */
    // [rule RT-MQ-QUEUE-MANAGER]
    public static void attach(CicsTask task, Path cfg) throws IOException {
        LocalDateTime now = task.now();
        String date = String.format("%04d%02d%02d", now.getYear(), now.getMonthValue(), now.getDayOfMonth());
        String time = String.format("%02d%02d%02d%02d", now.getHour(), now.getMinute(), now.getSecond(),
                now.getNano() / 10_000_000);
        QueueManager qm = new QueueManager(cfg, task::resourceEvent, date, time);
        task.withResource("mq", qm, qm::uowEnd);
    }

    /** The runner's: the queues the task leaves (its normal end commits it), or null when the task had no queue manager. */
    public static Map<String, List<String>> end(CicsTask task) {
        Object qm = task.resource("mq");
        return qm == null ? null : ((QueueManager) qm).end();
    }

    private static QueueManager qm(CicsTask task, String call) {
        Object qm = task.resource("mq");
        if (qm == null) {
            throw new UnsupportedOperationException(call + ": a queue manager the case does not state (its \"mq\" "
                    + "section) is not modelled");
        }
        return (QueueManager) qm;
    }

    private static QueueManager.Ref r(Field f) {
        return new QueueManager.Ref(f.storage().bytes, f.offset());
    }

    public static void mqopen(CicsTask task, Field hconn, Field od, Field options, Field hobj, Field cc, Field rc) {
        qm(task, "MQOPEN").mqopen(r(hconn), r(od), r(options), r(hobj), r(cc), r(rc));
    }

    public static void mqclose(CicsTask task, Field hconn, Field hobj, Field options, Field cc, Field rc) {
        qm(task, "MQCLOSE").mqclose(r(hconn), r(hobj), r(options), r(cc), r(rc));
    }

    public static void mqget(CicsTask task, Field hconn, Field hobj, Field md, Field gmo, Field buflen, Field buffer,
            Field datalen, Field cc, Field rc) {
        qm(task, "MQGET").mqget(r(hconn), r(hobj), r(md), r(gmo), r(buflen), r(buffer), r(datalen), r(cc), r(rc));
    }

    public static void mqput(CicsTask task, Field hconn, Field hobj, Field md, Field pmo, Field buflen, Field buffer,
            Field cc, Field rc) {
        qm(task, "MQPUT").mqput(r(hconn), r(hobj), r(md), r(pmo), r(buflen), r(buffer), r(cc), r(rc));
    }

    public static void mqput1(CicsTask task, Field hconn, Field od, Field md, Field pmo, Field buflen, Field buffer,
            Field cc, Field rc) {
        qm(task, "MQPUT1").mqput1(r(hconn), r(od), r(md), r(pmo), r(buflen), r(buffer), r(cc), r(rc));
    }
}
