package __PACKAGE__.cobolrt;

/**
 * Runtime version and compatibility contract (#4718).
 *
 * <p>Every translated port stamps the {@code cobolrt} version it was generated against. Semantic versioning:
 * {@code 0.Y.Z} requires exact {@code 0.Y} and {@code Z >= requiredPatch}; {@code X.Y.Z} ({@code X >= 1}) requires
 * {@code currentMajor == X} and {@code (currentMinor, currentPatch) >= (Y, Z)}.
 */
public final class CobolRuntime {
    public static final String VERSION = "0.1.0";
    public static final int API_SCHEMA = 1;

    private CobolRuntime() {}

    /** Whether this runtime satisfies a port generated against {@code requiredVersion}. */
    public static boolean isCompatible(String requiredVersion) {
        if (requiredVersion == null || requiredVersion.isEmpty()) {
            return false;
        }
        int[] cur = parseSemver(VERSION);
        int[] req = parseSemver(requiredVersion);
        if (cur[0] != req[0]) {
            return false;
        }
        if (cur[0] == 0) {
            return cur[1] == req[1] && cur[2] >= req[2];
        }
        return cur[1] > req[1] || (cur[1] == req[1] && cur[2] >= req[2]);
    }

    /** Fails loudly if this runtime is incompatible with {@code requiredVersion}. */
    public static void requireCompatible(String requiredVersion) {
        if (!isCompatible(requiredVersion)) {
            throw new IllegalStateException(
                    "cobolrt " + VERSION + " is incompatible with port target " + requiredVersion);
        }
    }

    private static int[] parseSemver(String v) {
        String[] parts = v.split("\\.", -1);
        if (parts.length != 3) {
            throw new IllegalArgumentException("invalid cobolrt semver: " + v);
        }
        return new int[] {
            Integer.parseInt(parts[0]),
            Integer.parseInt(parts[1]),
            Integer.parseInt(parts[2]),
        };
    }
}
