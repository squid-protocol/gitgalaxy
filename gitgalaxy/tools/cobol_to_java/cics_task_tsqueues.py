#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: CicsTask's temporary-storage queue support (#4002, split out by #5274)
#
# PURPOSE:
# The TS queue family of the CICS task runtime the transaction forge emits (CICS_TASK_JAVA): withTempStorage, WRITEQ /
# REWRITEQ / READQ TS (readqTs, readqTsNext), the TsResult record and the region's TempStorage store. The forge
# splices it into CicsTask where it always sat, so the class is byte-identical.
# ==============================================================================

TSQUEUES_JAVA = """\
    /** The region's temporary storage this task works on (#4002): one store is shared by every task of a
     *  conversation, the way a region's TS queues outlive the task that writes them. */
    public CicsTask withTempStorage(TempStorage storage) {
        this.tempStorage = storage;
        return this;
    }

    /** WRITEQ TS QUEUE(queue) FROM(data) (#4002): appends an item, creating the queue with its first write;
     *  the result's item is the number assigned. An item is the bytes the program wrote, in the region's code
     *  page (EBCDIC). LENGERR when data is empty or longer than 32763 bytes. */
    public TsResult writeqTs(String queue, byte[] data) {
        return tempStorage.write(this, queue, 0, data);
    }

    /** WRITEQ TS QUEUE(queue) FROM(data) ITEM(item) REWRITE (#4002): QIDERR without the queue, ITEMERR outside it. */
    public TsResult rewriteqTs(String queue, int item, byte[] data) {
        return tempStorage.write(this, queue, item, data);
    }

    /** READQ TS QUEUE(queue) INTO LENGTH(maxLength) ITEM(item) (#4002, IBM EXEC CICS READQ TS): QIDERR when
     *  the queue does not exist, ITEMERR for an item outside it; else the item, truncated to maxLength with
     *  LENGERR when longer, and the result's length is the item's own. */
    public TsResult readqTs(String queue, int item, int maxLength) {
        return tempStorage.read(this, queue, item, maxLength);
    }

    /** DELETEQ TS QUEUE(queue) (#4415 slice 2, IBM EXEC CICS DELETEQ TS): the whole queue and its READQ NEXT position;
     *  QIDERR (44) when it does not exist, INVREQ (16) for a name of binary zeros only. Returns RESP (RESP2 is 0: IBM
     *  lists none). */
    public int deleteqTs(String queue) {
        return tempStorage.delete(queue);
    }

    /** READQ TS QUEUE(queue) NEXT: the item after the last one read by any task (ITEMERR past the end). */
    public TsResult readqTsNext(String queue, int maxLength) {
        return tempStorage.read(this, queue, 0, maxLength);
    }

    /** A TS command's outcome: its condition, the item (number assigned or read), the LENGTH it sets (READQ;
     *  -1 when it sets none), the data moved INTO (READQ; null when none) and NUMITEMS. */
    public record TsResult(String resp, int item, int length, byte[] data, int numItems) {
    }

    /** A region's temporary storage (#4002): TS queues by name, each a list of items, and the READQ NEXT
     *  position of each queue (which counts a read by ITEM too). */
    public static final class TempStorage {
        private final Map<String, List<byte[]>> queues = new LinkedHashMap<>();
        private final Map<String, Integer> next = new HashMap<>();
        /** The intrapartition transient-data queues' records (#5079): first in first out. */
        final Map<String, java.util.ArrayDeque<String>> td = new HashMap<>();
        /** The run-time open state SET TDQUEUE OPENSTATUS left on an extrapartition queue (#5168, X61): true open, false closed. */
        final Map<String, Boolean> tdOpen = new HashMap<>();
        /** The queues SET TDQUEUE ENABLESTATUS(DISABLED) left disabled (#5168 round 5, X66). */
        final java.util.Set<String> tdDisabled = new java.util.HashSet<>();
        /** The levels SET TDQUEUE TRIGGERLEVEL left (#5168 round 7, X66). */
        final java.util.Map<String, Integer> tdTrigger = new java.util.HashMap<>();
        /** The extrapartition queues a READQ TD has taken a record from (reopening an input queue would restart it). */
        final java.util.Set<String> tdRead = new java.util.HashSet<>();

        /** A transient-data queue's records as they are before the conversation starts (#5168). */
        public TempStorage seedTd(String queue, List<String> records) {
            td.put(queue, new java.util.ArrayDeque<>(records));
            return this;
        }

        /** A queue as it is before the conversation starts. */
        public TempStorage seed(String queue, List<byte[]> items) {
            queues.put(queue, new ArrayList<>(items));
            return this;
        }

        /** Every queue and its items, in the order the queues were created. */
        public Map<String, List<byte[]>> queues() {
            Map<String, List<byte[]>> out = new LinkedHashMap<>();
            queues.forEach((q, items) -> out.put(q, List.copyOf(items)));
            return out;
        }

        int delete(String queue) {
            if (!queue.isEmpty() && queue.chars().allMatch(c -> c == 0)) {
                return 16;
            }
            if (queues.remove(queue) == null) {
                return 44;
            }
            next.remove(queue);
            return 0;
        }

        TsResult write(CicsTask task, String queue, int rewrite, byte[] data) {
            List<byte[]> items = queues.get(queue);
            String resp = "NORMAL";
            int item = 0;
            int[] planned = task.root().injected("WRITEQ-TS", queue.stripTrailing());  // #4049: nothing is written
            if (planned != null) {
                resp = respName(planned[0]);
            } else if (data == null || data.length < 1 || data.length > 32763) {
                resp = "LENGERR";
            } else if (rewrite > 0 && items == null) {
                resp = "QIDERR";
            } else if (rewrite > 0 && rewrite > items.size()) {
                resp = "ITEMERR";
            } else {
                if (items == null) {
                    items = new ArrayList<>();
                    queues.put(queue, items);
                }
                if (rewrite > 0) {
                    items.set(rewrite - 1, data.clone());
                    item = rewrite;
                } else {
                    items.add(data.clone());
                    item = items.size();
                }
            }
            task.event("WRITEQ-TS", "queue", queue, "data", data, "resp", resp, "item", item == 0 ? null : item);
            return new TsResult(resp, item, -1, null, items == null ? 0 : items.size());
        }

        TsResult read(CicsTask task, String queue, int item, int maxLength) {
            List<byte[]> items = queues.get(queue);
            int want = item > 0 ? item : next.getOrDefault(queue, 0) + 1;
            Object shown = item > 0 ? (Object) item : "NEXT";
            if (items == null || want < 1 || want > items.size()) {
                String resp = items == null ? "QIDERR" : "ITEMERR";
                task.event("READQ-TS", "queue", queue, "item", shown, "resp", resp, "length", null, "data", null);
                return new TsResult(resp, want, -1, null, 0);
            }
            next.put(queue, want);
            byte[] stored = items.get(want - 1);
            byte[] data = stored.length > maxLength ? Arrays.copyOf(stored, Math.max(maxLength, 0)) : stored.clone();
            String resp = stored.length > maxLength ? "LENGERR" : "NORMAL";
            task.event("READQ-TS", "queue", queue, "item", shown, "resp", resp, "length", stored.length, "data", data);
            return new TsResult(resp, want, stored.length, data, items.size());
        }
    }

"""
