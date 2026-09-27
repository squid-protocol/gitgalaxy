#!/usr/bin/env python3
"""
#3816 (part 3a): generate the mixed single/double-byte EBCDIC tables GitGalaxy decodes with.

Python ships none of IBM's host CJK code pages. The JDK does (the `jdk.charsets` module), so -- as
part 1 did for the Western European single-byte pages -- the tables are taken from it once and
committed, with this script as their provenance:

    python tests/tools/gen_ebcdic_dbcs.py            # needs a JDK 17+ (`javac`, `java`) on PATH

    cp930  Japanese Katakana-Kanji (SBCS: IBM 290 + Latin lower case)   x-IBM930
    cp939  Japanese Latin-Kanji    (SBCS: IBM 1027)                        x-IBM939
    cp935  Simplified Chinese      (SBCS: IBM 836)                         x-IBM935
    cp937  Traditional Chinese     (SBCS: IBM 037)                         x-IBM937
    cp933  Korean                  (SBCS: IBM 833)                         x-IBM933

A mixed page is stateful: bytes are single-byte until Shift-Out (0x0E), then pairs (lead and trail
0x40-0xFE, 0x4040 the ideographic space) until Shift-In (0x0F). For each page the script records
the single-byte table (256 entries) and the double-byte table (every lead x trail pair the JDK
decodes), plus, for each character, the pair the JDK itself ENCODES it as -- where several pairs
decode to one character (IBM's duplicates), writing must pick the one the host would.

One deliberate difference from the JDK, as in part 1: the JDK maps 0x15 (NL) to LF for USS
convenience; these tables keep CDRA's NEL (U+0085), which `source_text` treats as a line end.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "gitgalaxy" / "core" / "ebcdic_dbcs"
PAGES = {"cp930": "x-IBM930", "cp939": "x-IBM939", "cp935": "x-IBM935", "cp937": "x-IBM937", "cp933": "x-IBM933"}

# One line per mapping: `S <byte> <codepoint>` (single-byte), `D <pair> <codepoint>` (double-byte),
# `E <codepoint> <pair>` (the pair the JDK encodes that character as). Hex, -1 for unmapped.
_JAVA = r"""
import java.nio.*;
import java.nio.charset.*;

public class DumpDbcs {
    public static void main(String[] args) throws Exception {
        Charset cs = Charset.forName(args[0]);
        CharsetDecoder dec = cs.newDecoder()
            .onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT);
        CharsetEncoder enc = cs.newEncoder()
            .onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT);
        StringBuilder out = new StringBuilder();
        for (int b = 0; b < 256; b++) {
            if (b == 0x0E || b == 0x0F) continue;
            int cp = one(dec, new byte[]{(byte) b});
            out.append("S ").append(Integer.toHexString(b)).append(' ').append(cp < 0 ? "-1" : Integer.toHexString(cp)).append('\n');
        }
        java.util.TreeSet<Integer> seen = new java.util.TreeSet<>();
        for (int lead = 0x40; lead <= 0xFE; lead++) {
            for (int trail = 0x40; trail <= 0xFE; trail++) {
                int cp = one(dec, new byte[]{0x0E, (byte) lead, (byte) trail, 0x0F});
                if (cp < 0) continue;
                out.append("D ").append(Integer.toHexString(lead * 256 + trail)).append(' ').append(Integer.toHexString(cp)).append('\n');
                seen.add(cp);
            }
        }
        for (int cp : seen) {
            try {
                enc.reset();
                ByteBuffer bb = enc.encode(CharBuffer.wrap(Character.toChars(cp)));
                byte[] b = new byte[bb.remaining()];
                bb.get(b);
                if (b.length == 4 && b[0] == 0x0E && b[3] == 0x0F) {
                    out.append("E ").append(Integer.toHexString(cp)).append(' ')
                       .append(Integer.toHexString(((b[1] & 0xFF) << 8) | (b[2] & 0xFF))).append('\n');
                }
            } catch (CharacterCodingException e) { /* decodes but does not encode: leave it to the inverse */ }
        }
        System.out.print(out);
    }

    static int one(CharsetDecoder dec, byte[] bytes) {
        try {
            dec.reset();
            CharBuffer c = dec.decode(ByteBuffer.wrap(bytes));
            if (c.length() == 0) return -1;
            int cp = Character.codePointAt(c, 0);
            return (cp == 0xFFFD || c.length() != Character.charCount(cp)) ? -1 : cp;
        } catch (CharacterCodingException e) {
            return -1;
        }
    }
}
"""


def dump(java_name: str, work: Path) -> dict:
    out = subprocess.run(  # noqa: S603 -- a fixed class on a temp classpath
        ["java", "-cp", str(work), "DumpDbcs", java_name],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    sbcs = [-1] * 256
    dbcs: dict[int, int] = {}
    encode: dict[int, int] = {}
    for line in out.splitlines():
        kind, a, b = line.split()
        if kind == "S":
            sbcs[int(a, 16)] = int(b, 16) if b != "-1" else -1
        elif kind == "D":
            dbcs[int(a, 16)] = int(b, 16)
        elif kind == "E":
            encode[int(a, 16)] = int(b, 16)
    sbcs[0x15] = 0x85  # CDRA NEL, not the JDK's USS-convenience LF (see the module docstring)
    # Store only the encode choices the plain inverse (lowest pair per character) would get wrong.
    inverse: dict[int, int] = {}
    for pair in sorted(dbcs):
        inverse.setdefault(dbcs[pair], pair)
    overrides = {cp: pair for cp, pair in encode.items() if inverse.get(cp) != pair}
    return {"sbcs": sbcs, "dbcs": dbcs, "encode_overrides": overrides}


def main() -> int:
    if not (shutil.which("javac") and shutil.which("java")):
        print("gen_ebcdic_dbcs: needs a JDK 17+ (javac, java) on PATH", file=sys.stderr)
        return 2
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        (work / "DumpDbcs.java").write_text(_JAVA, encoding="utf-8")
        subprocess.run(["javac", "-d", str(work), str(work / "DumpDbcs.java")], check=True)  # noqa: S603,S607
        version = subprocess.run(["java", "-version"], capture_output=True, text=True).stderr  # noqa: S603,S607
        jdk = next((ln for ln in version.splitlines() if "version" in ln), "").strip()
        for page, java_name in PAGES.items():
            t = dump(java_name, work)
            doc = {
                "page": page,
                "source": f"JDK charset {java_name} ({jdk}); generated by tests/tools/gen_ebcdic_dbcs.py",
                "sbcs": "".join("�" if cp < 0 else chr(cp) for cp in t["sbcs"]),
                # lead byte (hex) -> 191 characters for trail bytes 0x40..0xFE, U+FFFD where unmapped
                "dbcs": {
                    f"{lead:02x}": "".join(chr(t["dbcs"].get(lead * 256 + tr, 0xFFFD)) for tr in range(0x40, 0xFF))
                    for lead in range(0x40, 0xFF)
                    if any(lead * 256 + tr in t["dbcs"] for tr in range(0x40, 0xFF))
                },
                "encode_overrides": {chr(cp): f"{pair:04x}" for cp, pair in sorted(t["encode_overrides"].items())},
            }
            path = OUT_DIR / f"{page}.json"
            path.write_text(json.dumps(doc, ensure_ascii=False, indent=0, sort_keys=True) + "\n", encoding="utf-8")
            print(
                f"{page}: {sum(cp >= 0 for cp in t['sbcs'])} single-byte, {len(t['dbcs'])} double-byte, "
                f"{len(doc['encode_overrides'])} encode overrides -> {path.relative_to(REPO_ROOT)}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
