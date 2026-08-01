from gitgalaxy.tools.cobol_to_java.cobol_to_java_decoder_forge import (
    generate_decoder_util,
)

# ==============================================================================
# GOLDEN IMAGE (The "Perfect" Expected Output)
# ==============================================================================
GOLDEN_DECODER_UTIL = """package com.gitgalaxy.modernized.util;

import java.math.BigDecimal;
import java.nio.charset.Charset;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class EbcdicDecoderUtil {

    private static final Logger log = LoggerFactory.getLogger(EbcdicDecoderUtil.class);

    // Cp1047 is the standard IBM EBCDIC character set (US/Canada)
    private static final Charset EBCDIC_CHARSET = Charset.forName("Cp1047");

    /**
     * Decodes a raw EBCDIC byte array into a standard Java UTF-8 String.
     */
    public static String decodeEbcdicString(byte[] ebcdicBytes) {
        if (ebcdicBytes == null) return null;
        try {
            return new String(ebcdicBytes, EBCDIC_CHARSET).trim();
        } catch (Exception e) {
            log.error("Failed to decode EBCDIC string", e);
            return "";
        }
    }

    /**
     * Unpacks a COBOL COMP-3 (Packed Decimal) byte array into a Java BigDecimal.
     * Includes strict hex-boundary validation to prevent runtime crashes from dirty legacy data.
     */
    public static BigDecimal unpackComp3(byte[] packedBytes, int scale) {
        if (packedBytes == null || packedBytes.length == 0) {
            return BigDecimal.ZERO;
        }

        try {
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < packedBytes.length; i++) {
                int b = packedBytes[i] & 0xFF;

                // Extract the high and low nibbles (4 bits each)
                int highNibble = b >>> 4;
                int lowNibble = b & 0x0F;

                // DEFENSIVE DESIGN: The high nibble MUST be a valid base-10 digit (0-9).
                // Values above 9 indicate corrupted memory or shifted byte boundaries.
                if (highNibble > 9) {
                    log.warn("Corrupt COMP-3 high nibble '{}' at byte index {}. Defaulting to ZERO.", Integer.toHexString(highNibble), i);
                    return BigDecimal.ZERO;
                }
                sb.append(highNibble);

                // The low nibble is a number EXCEPT in the very last byte, where it acts as the sign flag
                if (i == packedBytes.length - 1) {
                    boolean isNegative = (lowNibble == 0x0D || lowNibble == 0x0B);
                    if (isNegative) {
                        sb.insert(0, "-");
                    } else if (lowNibble < 0x0A) {
                        // The sign nibble should be A-F. If it's a number, the data is likely shifted or corrupt.
                        log.warn("Suspicious COMP-3 sign nibble '{}' at end of byte array.", Integer.toHexString(lowNibble));
                    }
                } else {
                    if (lowNibble > 9) {
                        log.warn("Corrupt COMP-3 low nibble '{}' at byte index {}. Defaulting to ZERO.", Integer.toHexString(lowNibble), i);
                        return BigDecimal.ZERO;
                    }
                    sb.append(lowNibble);
                }
            }

            BigDecimal result = new BigDecimal(sb.toString());
            return result.movePointLeft(scale);

        } catch (Exception e) {
            log.error("Critical failure unpacking COMP-3 bytes. Defaulting to ZERO.", e);
            return BigDecimal.ZERO;
        }
    }
}"""

# ==============================================================================
# THE TESTS
# ==============================================================================


def test_ebcdic_comp3_decoder_golden_image():
    """
    Verifies that the generated EBCDIC and COMP-3 decoding logic perfectly matches
    the mathematically proven Golden Image. This prevents fatal regressions in
    mainframe bitwise unpacking logic.
    """
    # 1. Generate the code
    generated_java = generate_decoder_util("com.gitgalaxy.modernized")

    # 2. Compare against the Golden Image
    # Using strip() to neutralize OS-level newline differences (CRLF vs LF)
    assert generated_java.strip() == GOLDEN_DECODER_UTIL.strip(), (
        "FATAL REGRESSION: The Mainframe Decoder utility drifted from the Golden Image! Check bitwise math and hex boundaries."
    )
