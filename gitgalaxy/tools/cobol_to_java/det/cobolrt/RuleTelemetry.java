package __PACKAGE__.cobolrt;

import java.util.Map;
import java.util.TreeMap;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.LongAdder;

/**
 * Optional, low-overhead runtime rule/quirk telemetry (#4713, #4716).
 *
 * <p>Off by default ({@link #isEnabled()} is {@code false}): when off, {@link #hit(String)} is a single volatile
 * read and returns immediately with zero allocations. When enabled, records execution counts keyed by
 * {@code cobolrt_rules.json} rule IDs so evidence reports (#4713) can list exercised rules and exit-route reports
 * (#4716) can identify COBOL quirks that never fired.
 */
public final class RuleTelemetry {
    private static volatile boolean enabled = false;
    private static final ConcurrentHashMap<String, LongAdder> COUNTS = new ConcurrentHashMap<>();

    private RuleTelemetry() {}

    /** Whether rule telemetry is currently enabled (default: {@code false}). */
    public static boolean isEnabled() {
        return enabled;
    }

    /** Enables or disables rule telemetry, returning the previous state. */
    public static boolean swapEnabled(boolean on) {
        boolean before = enabled;
        enabled = on;
        return before;
    }

    /** Clears all recorded rule counts. */
    public static void reset() {
        COUNTS.clear();
    }

    /** Records one execution of {@code ruleId} when telemetry is enabled. */
    public static void hit(String ruleId) {
        if (!enabled) {
            return;
        }
        LongAdder adder = COUNTS.get(ruleId);
        if (adder == null) {
            adder = COUNTS.computeIfAbsent(ruleId, k -> new LongAdder());
        }
        adder.increment();
    }

    /** Returns a sorted snapshot of {@code ruleId -> count}. */
    public static Map<String, Long> snapshot() {
        TreeMap<String, Long> out = new TreeMap<>();
        for (Map.Entry<String, LongAdder> e : COUNTS.entrySet()) {
            out.put(e.getKey(), e.getValue().sum());
        }
        return out;
    }

    /** Formats the current {@link #snapshot()} as a JSON object string. */
    public static String toJson() {
        StringBuilder sb = new StringBuilder("{");
        boolean first = true;
        for (Map.Entry<String, Long> e : snapshot().entrySet()) {
            if (!first) sb.append(',');
            first = false;
            sb.append('"').append(e.getKey()).append("\":").append(e.getValue());
        }
        sb.append('}');
        return sb.toString();
    }
}
