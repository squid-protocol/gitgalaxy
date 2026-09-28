#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: EBCDIC & COMP-3 Decoder Generator
#
# PURPOSE:
# Auto-generates the utility class necessary to translate raw mainframe byte
# streams into modern Java data structures (UTF-8 Strings and BigDecimals).
#
# ARCHITECTURAL DECISION:
# Mainframe datasets do not natively map to modern ASCII/UTF-8 strings or IEEE 754
# floating-point numbers. IBM's Packed Decimal (COMP-3) and EBCDIC encodings
# require precise, bit-level translation. By auto-generating a dedicated, thoroughly
# tested decoding utility within the Spring Boot architecture, we prevent the AI
# agent from hallucinating flawed byte-shifting logic and ensure enterprise-grade
# data integrity during binary ingestion.
# ==============================================================================

# galaxyscope:ignore sec_hardcoded_secrets, secrets_risk

from gitgalaxy.core.ebcdic_codecs import java_charset_name


def generate_decoder_util(package_name: str, code_page: str = "cp037") -> str:
    """Generates the EBCDIC and Packed Decimal (COMP-3) decoder utility with strict bounds validation.
    #3949: invalid packed data throws (S0C7), as the mainframe abends, rather than decoding to zero.
    #3908: text decodes with the conversion's `data.code_page` (its JDK name: cp037 -> IBM037,
    cp277 -> IBM277), not a hard-coded Cp1047 -- the default page is cp037."""
    charset = java_charset_name(code_page)
    java = f"""package {package_name}.util;

import java.math.BigDecimal;
import java.nio.charset.Charset;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class EbcdicDecoderUtil {{

    private static final Logger log = LoggerFactory.getLogger(EbcdicDecoderUtil.class);

    // The estate's EBCDIC code page (data.code_page: {code_page}); national letters and [ ] ! ^ | move per page
    private static final Charset EBCDIC_CHARSET = Charset.forName("{charset}");

    /**
     * Decodes a raw EBCDIC byte array into a standard Java UTF-8 String.
     */
    public static String decodeEbcdicString(byte[] ebcdicBytes) {{
        if (ebcdicBytes == null) return null;
        try {{
            return new String(ebcdicBytes, EBCDIC_CHARSET).trim();
        }} catch (Exception e) {{
            log.error("Failed to decode EBCDIC string", e);
            return "";
        }}
    }}

    /**
     * #3949: packed-decimal (COMP-3) bytes that are not valid packed data -- a digit nibble above 9, or a
     * sign nibble below A -- which on the mainframe raise a data exception (S0C7) and abend the step. The
     * decoder throws it rather than turn corrupt money into zero and keep going.
     */
    public static final class PackedDecimalDataException extends NumberFormatException {{
        private static final long serialVersionUID = 1L;

        public PackedDecimalDataException(String message) {{
            super(message);
        }}
    }}

    /**
     * Unpacks a COBOL COMP-3 (Packed Decimal) byte array into a Java BigDecimal.
     * #3949: invalid packed data throws PackedDecimalDataException (S0C7), never a zero.
     */
    public static BigDecimal unpackComp3(byte[] packedBytes, int scale) {{
        return unpackComp3(packedBytes, scale, null);
    }}

    /** As unpackComp3(byte[], int); `field` (the COBOL item's name, or null) names it in the exception. */
    public static BigDecimal unpackComp3(byte[] packedBytes, int scale, String field) {{
        if (packedBytes == null || packedBytes.length == 0) {{
            return BigDecimal.ZERO;
        }}

        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < packedBytes.length; i++) {{
            int b = packedBytes[i] & 0xFF;

            // Extract the high and low nibbles (4 bits each)
            int highNibble = b >>> 4;
            int lowNibble = b & 0x0F;

            // The high nibble is always a digit (0-9)
            if (highNibble > 9) {{
                throw invalid(field, packedBytes.length, i, "digit", highNibble);
            }}
            sb.append(highNibble);

            // The low nibble is a digit EXCEPT in the very last byte, where it is the sign: A-F
            // (B / D negative, A / C / E / F positive)
            if (i == packedBytes.length - 1) {{
                if (lowNibble < 0x0A) {{
                    throw invalid(field, packedBytes.length, i, "sign", lowNibble);
                }}
                if (lowNibble == 0x0D || lowNibble == 0x0B) {{
                    sb.insert(0, "-");
                }}
            }} else {{
                if (lowNibble > 9) {{
                    throw invalid(field, packedBytes.length, i, "digit", lowNibble);
                }}
                sb.append(lowNibble);
            }}
        }}
        return new BigDecimal(sb.toString()).movePointLeft(scale);
    }}

    private static PackedDecimalDataException invalid(String field, int length, int index, String kind,
                                                      int nibble) {{
        return new PackedDecimalDataException("invalid packed decimal (S0C7 data exception)"
                + (field == null ? "" : " in " + field) + ": " + kind + " nibble "
                + Integer.toHexString(nibble).toUpperCase(java.util.Locale.ROOT) + " at byte " + index
                + " of " + length);
    }}
}}
"""
    return java
