#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: CobolCompare -- alphanumeric comparison as the mainframe does it (#3986)
#
# PURPOSE:
# COBOL compares two alphanumeric operands by the program's collating sequence:
# on z/OS the EBCDIC code page's bytes, where lower case sorts before upper case
# and letters before digits (`a` 0x81 < `A` 0xC1 < `0` 0xF0). Java's
# String.compareTo compares UTF-16 code units, where digits sort before letters,
# so a ported `IF CUST-ID > 'A'` takes the opposite branch for '1001'. COBOL also
# pads the shorter operand with spaces, so 'AB' = 'AB  ', which String.equals
# denies.
#
# CobolCompare compares the operands' bytes in the conversion's data.code_page,
# the shorter padded with that page's space. Every generated project gets it
# (util/), and the port tickets require it for every alphanumeric relation
# condition.
#
# NON-SCOPE:
#   - A PROGRAM COLLATING SEQUENCE / ALPHABET clause (a custom order) is not
#     modelled; the port ticket rule tells the porter to flag it.
#   - Numeric comparisons stay BigDecimal.compareTo (they compare values, not
#     bytes); national (PIC N) operands compare by UTF-16, as Java does.
# ==============================================================================
from gitgalaxy.core.ebcdic_codecs import java_charset_name


def generate_compare_util(package_name: str, code_page: str = "cp037") -> str:
    """The CobolCompare runtime for `data.code_page` (its JDK name: cp037 -> IBM037)."""
    charset = java_charset_name(code_page)
    return f"""package {package_name}.util;

import java.nio.ByteBuffer;
import java.nio.CharBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.Charset;
import java.nio.charset.CodingErrorAction;
import java.util.Arrays;

/**
 * #3986: alphanumeric comparison as COBOL does it -- by the code page's bytes ({charset}), not by
 * String.compareTo. In EBCDIC lower case sorts before upper case and letters before digits, so
 * `IF CUST-ID > 'A'` is true for "1001" here and false by compareTo. The shorter operand is padded with
 * spaces, so "AB" equals "AB  ". A null operand is empty (all spaces); a character the code page cannot
 * encode throws, as it never came from the mainframe's data.
 */
public final class CobolCompare {{

    /** The code page the comparisons use: the conversion's data.code_page. */
    public static final Charset CODE_PAGE = Charset.forName("{charset}");

    private CobolCompare() {{
    }}

    /** Negative, zero or positive as {{@code a}} is less than, equal to or greater than {{@code b}}. */
    public static int compare(String a, String b) {{
        return compare(a, b, CODE_PAGE);
    }}

    public static int compare(String a, String b, Charset codePage) {{
        byte[] x = bytes(a, codePage);
        byte[] y = bytes(b, codePage);
        int space = bytes(" ", codePage)[0] & 0xFF;
        for (int i = 0, n = Math.max(x.length, y.length); i < n; i++) {{
            int p = i < x.length ? x[i] & 0xFF : space;
            int q = i < y.length ? y[i] & 0xFF : space;
            if (p != q) {{
                return p < q ? -1 : 1;
            }}
        }}
        return 0;
    }}

    public static boolean eq(String a, String b) {{
        return compare(a, b) == 0;
    }}

    public static boolean gt(String a, String b) {{
        return compare(a, b) > 0;
    }}

    public static boolean ge(String a, String b) {{
        return compare(a, b) >= 0;
    }}

    public static boolean lt(String a, String b) {{
        return compare(a, b) < 0;
    }}

    public static boolean le(String a, String b) {{
        return compare(a, b) <= 0;
    }}

    /** HIGH-VALUES of {{@code length}} characters: X'FF' bytes in the code page, the greatest value. */
    public static String highValues(int length) {{
        return filled(length, (byte) 0xFF);
    }}

    /** LOW-VALUES of {{@code length}} characters: X'00' bytes in the code page, the least value. */
    public static String lowValues(int length) {{
        return filled(length, (byte) 0x00);
    }}

    private static String filled(int length, byte b) {{
        byte[] bytes = new byte[length];
        Arrays.fill(bytes, b);
        return new String(bytes, CODE_PAGE);
    }}

    private static byte[] bytes(String s, Charset codePage) {{
        if (s == null || s.isEmpty()) {{
            return new byte[0];
        }}
        try {{
            ByteBuffer out = codePage.newEncoder()
                    .onMalformedInput(CodingErrorAction.REPORT)
                    .onUnmappableCharacter(CodingErrorAction.REPORT)
                    .encode(CharBuffer.wrap(s));
            byte[] bytes = new byte[out.remaining()];
            out.get(bytes);
            return bytes;
        }} catch (CharacterCodingException e) {{
            throw new IllegalArgumentException("not encodable in " + codePage + ": " + s, e);
        }}
    }}
}}
"""
