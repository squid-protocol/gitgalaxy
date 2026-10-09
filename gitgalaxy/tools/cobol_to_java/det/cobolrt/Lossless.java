package __PACKAGE__.cobolrt;

import java.nio.ByteBuffer;
import java.nio.CharBuffer;
import java.nio.charset.Charset;
import java.nio.charset.CharsetDecoder;
import java.nio.charset.CharsetEncoder;
import java.nio.charset.CoderResult;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;

/**
 * The record charset with every byte value kept (#4698). A COBOL item holds bytes; the runtime views them as text
 * through the record charset. A single-byte charset can leave a byte unmapped (windows-1252 has no X'81', X'8D',
 * X'8F', X'90', X'9D'): Java then decodes U+FFFD and encodes '?', and the byte is lost. Here a byte the charset leaves
 * unmapped is its latin-1 character (U+0081 ...), and that character encodes back to that one byte, so
 * bytes -> text -> bytes is the identity for all 256 values. The name is the charset's own. A charset of more than
 * one byte per character (UTF-8) is returned as it is.
 */
public final class Lossless extends Charset {
    private final Charset base;
    private final char[] decode = new char[256];
    private final java.util.Map<Character, Byte> encode = new java.util.HashMap<>();

    private Lossless(Charset base) {
        super(base.name(), null);
        this.base = base;
        for (int b = 0; b < 256; b++) {
            String s = new String(new byte[] {(byte) b}, base);
            char c = s.length() == 1 && s.charAt(0) != '�' ? s.charAt(0) : (char) b;
            decode[b] = c;
        }
        for (int b = 255; b >= 0; b--) {
            encode.put(decode[b], (byte) b);
        }
    }

    /** The charset itself, or the one that keeps every byte when it is a single-byte charset. */
    public static Charset of(Charset cs) {
        if (cs instanceof Lossless || cs.newEncoder().maxBytesPerChar() != 1.0f) {
            return cs;
        }
        return new Lossless(cs);
    }

    @Override
    public boolean contains(Charset cs) {
        return cs == this || base.contains(cs);
    }

    @Override
    public CharsetDecoder newDecoder() {
        return new CharsetDecoder(this, 1.0f, 1.0f) {
            @Override
            protected CoderResult decodeLoop(ByteBuffer in, CharBuffer out) {
                while (in.hasRemaining()) {
                    if (!out.hasRemaining()) {
                        return CoderResult.OVERFLOW;
                    }
                    out.put(decode[in.get() & 0xFF]);
                }
                return CoderResult.UNDERFLOW;
            }
        };
    }

    @Override
    public CharsetEncoder newEncoder() {
        return new CharsetEncoder(this, 1.0f, 1.0f, new byte[] {encode.getOrDefault('?', (byte) '?')}) {
            @Override
            protected CoderResult encodeLoop(CharBuffer in, ByteBuffer out) {
                while (in.hasRemaining()) {
                    if (!out.hasRemaining()) {
                        return CoderResult.OVERFLOW;
                    }
                    Byte b = encode.get(in.get(in.position()));
                    if (b == null) {
                        return CoderResult.unmappableForLength(1);
                    }
                    in.get();
                    out.put(b);
                }
                return CoderResult.UNDERFLOW;
            }
        };
    }

    /** A hexadecimal literal X'hh..': exactly those bytes (IBM: no code-page translation), as the text that
     *  encodes back to them. {@code latin1} holds one character per byte. */
    static String hex(String latin1, Charset cs) {
        return new String(latin1.getBytes(StandardCharsets.ISO_8859_1), cs);
    }
}
