#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: VSAM files -> Spring Data repositories (#3617)
#
# PURPOSE:
# Each VSAM data store (GalaxyIR.vsam_stores: a base cluster, with the CSD FILEs
# on it, its alternate indexes and every CICS and batch program that touches it)
# becomes one JPA entity and one Spring Data repository:
#
#   - the entity follows the record layout the programs read and write, its @Id
#     the field at the cluster's KEYS(length offset) (IDCAMS), else at the
#     RIDFLD / RECORD KEY the programs use;
#   - the repository adds what the programs do beyond JpaRepository's
#     findById / save / deleteById: STARTBR + READNEXT / READPREV browses as
#     ordered range queries, and a finder per alternate index (AIX via PATH);
#   - each program's @Service gains read / write / rewrite / delete / browse
#     methods for exactly the verbs it uses (CICS) or the OPEN modes the JCL
#     gives it (batch), each naming its lines.
#
# The IDCAMS define, CSD FILE and call sites are cited on every class and method.
# Where the key is not one field, the layout is unknown, or a program's record
# differs from the entity's, the code says so in a TODO; nothing is guessed.
# ==============================================================================
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from gitgalaxy.tools.cobol_to_java.cobol_to_java_common import (
    ClassNames,
    TraceLog,
    java_identifier,
    java_path,
    java_type,
    parse_pic_precision,
    status_text,
)
from gitgalaxy.tools.cobol_to_java.cobol_to_java_names import java_class_base
from gitgalaxy.tools.cobol_to_java.cobol_to_java_spring_forge import _accessors, _declared_fields
from gitgalaxy.tools.cobol_to_java.java_target import JavaTarget

ENTITY_SUBPACKAGE = "entity.vsam"
REPOSITORY_SUBPACKAGE = "repository.vsam"
_BROWSE_FORWARD = {"STARTBR", "READNEXT", "RESETBR"}
_NOISE_QUALIFIERS = {"VSAM", "KSDS", "ESDS", "RRDS", "LDS", "CLUSTER", "DATA", "INDEX", "CICS"}


def _signature(layout: dict) -> tuple:
    return tuple((f.get("name"), f.get("pic"), f.get("usage"), f.get("offset"), f.get("bytes"), f.get("occurs"))
                 for f in layout.get("fields", []))  # fmt: skip


def _qualifier(store: dict) -> str:
    """A readable name for a store: the dataset's most specific meaningful qualifier (ACCTDATA)."""
    if not store.get("dataset"):
        return store.get("name") or "FILE"
    parts = [p for p in re.split(r"[.]", store["dataset"]) if p and not re.search(r"[@<>]", p)]
    meaningful = [p for p in parts if p.upper() not in _NOISE_QUALIFIERS]
    return (meaningful or parts or ["FILE"])[-1]


# ---- #3624: the entity record codec ------------------------------------------------------
_BINARY_USAGES = frozenset(
    {"COMP", "COMP-4", "COMP-5", "BINARY", "COMPUTATIONAL", "COMPUTATIONAL-4", "COMPUTATIONAL-5"}
)
_PACKED_USAGES = frozenset({"COMP-3", "PACKED-DECIMAL", "COMPUTATIONAL-3"})


def _pic_numeric(pic: str) -> tuple[bool, int, int] | None:
    """(signed, digits, scale) of a plain numeric PIC (`S9(10)V99`), None for text or an edited PIC."""
    p = re.sub(r"(.)\((\d+)\)", lambda m: m.group(1) * int(m.group(2)), pic.upper())
    if not p or re.search(r"[^S9V]", p):
        return None
    whole, _, frac = p.partition("V")
    return p.startswith("S"), whole.count("9") + frac.count("9"), frac.count("9")


def _codec_kind(f: Field) -> str | None:
    """text / zoned / packed / binary, or None when the codec cannot encode the item."""
    if not f.pic:
        return None
    num = _pic_numeric(f.pic)
    usage = (f.usage or "DISPLAY").upper()
    if usage == "NATIONAL":
        return "national"
    if usage == "DISPLAY-1":
        return "display1"
    if num is None:
        return "text" if usage in ("DISPLAY", "") else None
    if usage in _PACKED_USAGES:
        return "packed"
    if usage in _BINARY_USAGES:
        return "binary"
    return "zoned" if usage in ("DISPLAY", "") else None


def _codec_get(f: Field, dbcs_page: str | None = None) -> str:
    kind = _codec_kind(f)
    if kind == "national":
        return f'CobolRecords.text(rec, {f.offset}, {f.bytes}, java.nio.charset.Charset.forName("UTF-16BE"))'
    if kind == "display1":
        if dbcs_page:
            return f'CobolRecords.text(rec, {f.offset}, {f.bytes}, java.nio.charset.Charset.forName("{dbcs_page}"))'
        return f"/* TODO: declare data.dbcs_code_page in java_target to decode DISPLAY-1 */ CobolRecords.text(rec, {f.offset}, {f.bytes}, text)"
    if kind == "text":
        return f"CobolRecords.text(rec, {f.offset}, {f.bytes}, text)"
    signed, _digits, scale = _pic_numeric(f.pic or "") or (False, 0, 0)
    if kind == "zoned":
        dec = f"CobolRecords.zoned(rec, {f.offset}, {f.bytes}, {scale}, text)"
    elif kind == "packed":
        dec = f"CobolRecords.packed(rec, {f.offset}, {f.bytes}, {scale})"
    else:
        dec = f"CobolRecords.binary(rec, {f.offset}, {f.bytes}, {scale}, {str(signed).lower()})"
    return {"Integer": f"CobolRecords.toInteger({dec})", "Long": f"CobolRecords.toLong({dec})",
            "Double": f"{dec}.doubleValue()", "String": f"{dec}.toPlainString()"}.get(f.jtype, dec)  # fmt: skip


def _codec_put(f: Field, value: str, dbcs_page: str | None = None) -> str:
    kind = _codec_kind(f)
    if kind == "national":
        return (
            f'CobolRecords.putText(rec, {f.offset}, {f.bytes}, {value}, java.nio.charset.Charset.forName("UTF-16BE"))'
        )
    if kind == "display1":
        if dbcs_page:
            return f'CobolRecords.putText(rec, {f.offset}, {f.bytes}, {value}, java.nio.charset.Charset.forName("{dbcs_page}"))'
        return f"/* TODO: declare data.dbcs_code_page in java_target to encode DISPLAY-1 */ CobolRecords.putText(rec, {f.offset}, {f.bytes}, {value}, text)"
    if kind == "text":
        return f"CobolRecords.putText(rec, {f.offset}, {f.bytes}, {value}, text)"
    signed, digits, scale = _pic_numeric(f.pic or "") or (False, 0, 0)
    dec = f"CobolRecords.decimal({value})"
    if kind == "zoned":
        return f"CobolRecords.putZoned(rec, {f.offset}, {digits}, {scale}, {str(signed).lower()}, {dec}, text)"
    if kind == "packed":
        return f"CobolRecords.putPacked(rec, {f.offset}, {f.bytes}, {scale}, {str(signed).lower()}, {dec})"
    return f"CobolRecords.putBinary(rec, {f.offset}, {f.bytes}, {scale}, {str(signed).lower()}, {dec})"


def _decimal_attrs(f: Field) -> list[str]:
    """#3950: `precision` / `scale` of a BigDecimal column, from the PICTURE as the schema forge reads it
    (parse_pic_precision) -- with none, Hibernate's DDL makes it numeric(38, 2) and a V9(4) field loses two
    decimals. Only a plain numeric PICTURE (9 / S / V / P) is a BigDecimal here, where neither DECIMAL-POINT IS
    COMMA nor a currency symbol (#3910) moves a digit (P scaling positions widen it); an edited PICTURE is
    its display text (a String column of its width). A PL/I item: its picture, or FIXED DEC(p,q); FIXED BIN
    and a negative scale get none."""
    if f.jtype != "BigDecimal":
        return []
    if f.pli_type is not None or (f.pic or "").startswith("'"):
        usage = (f.pli_type or "").upper()
        m = re.search(r"\b(?:FIXED|DEC(?:IMAL)?)\s{0,4}\(\s{0,4}(\d{1,3})(?:\s{0,4},\s{0,4}([+-]?\d{1,3}))?", usage)
        if f.pic:  # a PL/I picture repeats by prefix: `(5)9V99`
            p = re.sub(r"\((\d{1,4})\)(.)", lambda r: r.group(2) * int(r.group(1)), f.pic.strip("'").upper())
            if re.search(r"[^9SV]", p):
                return []
            whole, _, frac = p.partition("V")
            digits, scale = whole.count("9") + frac.count("9"), frac.count("9")
        elif m and not re.search(r"\bBIN", usage):
            digits, scale = int(m.group(1)), int(m.group(2) or 0)
        else:
            return []
    elif f.pic:
        digits, scale = parse_pic_precision(f.pic, False)
        p = re.sub(r"(.)\((\d{1,4})\)", lambda r: r.group(1) * int(r.group(2)), f.pic.upper())
        if "P" in p:  # scaling positions: before the digits more decimals (SVPP999), after them a larger integer
            digits += p.count("P")
            scale = digits if p.find("P") < p.find("9") else scale
    else:
        return []
    if digits <= 0 or not 0 <= scale <= digits:
        return []
    return [f"precision = {digits}", f"scale = {scale}"]


COBOL_RECORDS_JAVA = """package __PACKAGE__;

import java.math.BigDecimal;
import java.math.BigInteger;
import java.math.RoundingMode;
import java.nio.charset.Charset;
import java.util.Arrays;
import java.util.Locale;

/**
 * #3624: COBOL storage for the entities' record codecs (fromRecord / toRecord) -- DISPLAY text, zoned
 * decimal (a DISPLAY numeric: the sign overpunched on the last digit, `{` / `A`-`I` positive, `}` /
 * `J`-`R` negative, as z/OS writes it and an ASCII transfer keeps it; an unsigned field plain digits),
 * COMP-3 packed decimal and COMP binary (big-endian). Storing follows COBOL MOVE: a value too long for
 * the field loses its high-order digits, decimals beyond the scale are truncated, an unsigned field
 * keeps the magnitude. Invalid data (a space in a numeric field) is an error, not a zero.
 *
 * #3831: a digit is `0`-`9` and nothing else. Java's own parsers take any Unicode decimal digit --
 * BigInteger, BigDecimal and Integer.parseInt read Arabic-Indic, Devanagari and full-width digits as
 * numbers -- where COBOL's NUMERIC test and NUMVAL reject them, so every parse here checks the
 * characters itself before handing them to BigInteger / BigDecimal.
 */
public final class CobolRecords {

    private static final String POSITIVE = "__POSITIVE__";
    private static final String NEGATIVE = "__NEGATIVE__";

    private CobolRecords() {
    }

    public static byte[] blank(int length, Charset text) {
        byte[] rec = new byte[length];
        Arrays.fill(rec, " ".getBytes(text)[0]);
        return rec;
    }

    public static String text(byte[] rec, int offset, int length, Charset text) {
        return new String(rec, offset, length, text);
    }

    public static void putText(byte[] rec, int offset, int length, String value, Charset text) {
        byte[] v = (value == null ? "" : value).getBytes(text);
        byte space = " ".getBytes(text)[0];
        for (int i = 0; i < length; i++) {
            rec[offset + i] = i < v.length ? v[i] : space;
        }
    }

    public static BigDecimal zoned(byte[] rec, int offset, int length, int scale, Charset text) {
        String s = new String(rec, offset, length, text);
        if (s.length() != length) {  // #3831: a multi-byte character is no zoned digit
            throw new NumberFormatException("invalid zoned digits '" + s + "' at offset " + offset);
        }
        char last = s.charAt(length - 1);
        boolean negative = false;
        int digit;
        if (last >= '0' && last <= '9') {
            digit = last - '0';
        } else if (POSITIVE.indexOf(last) >= 0) {
            digit = POSITIVE.indexOf(last);
        } else if (NEGATIVE.indexOf(last) >= 0) {
            digit = NEGATIVE.indexOf(last);
            negative = true;
        } else {
            throw new NumberFormatException("invalid zoned sign '" + last + "' at offset " + (offset + length - 1));
        }
        String digits = s.substring(0, length - 1) + digit;
        if (!isAsciiDigits(digits)) {
            throw new NumberFormatException("invalid zoned digits '" + s + "' at offset " + offset);
        }
        BigDecimal v = new BigDecimal(new BigInteger(digits), scale);
        return negative ? v.negate() : v;
    }

    public static void putZoned(byte[] rec, int offset, int digits, int scale, boolean signed, BigDecimal value,
                                Charset text) {
        BigInteger unscaled = value.setScale(scale, RoundingMode.DOWN).unscaledValue();
        boolean negative = signed && unscaled.signum() < 0;
        String s = unscaled.abs().toString();
        s = s.length() > digits ? s.substring(s.length() - digits) : "0".repeat(digits - s.length()) + s;
        if (signed) {
            int last = s.charAt(digits - 1) - '0';
            s = s.substring(0, digits - 1) + (negative ? NEGATIVE : POSITIVE).charAt(last);
        }
        byte[] b = s.getBytes(text);
        System.arraycopy(b, 0, rec, offset, digits);
    }

    /** #3949: a digit nibble above 9, or a sign nibble below A, is invalid packed data -- on the mainframe a
     *  data exception (S0C7), never a number: a NumberFormatException naming the byte, as zoned does. */
    public static BigDecimal packed(byte[] rec, int offset, int length, int scale) {
        StringBuilder digits = new StringBuilder();
        for (int i = 0; i < length; i++) {
            int b = rec[offset + i] & 0xFF;
            int lo = b & 0x0F;
            boolean badDigit = b >> 4 > 9 || (i < length - 1 && lo > 9);
            if (badDigit || (i == length - 1 && lo < 0x0A)) {
                throw new NumberFormatException("invalid packed decimal (S0C7): byte X'"
                        + Integer.toHexString(b | 0x100).substring(1).toUpperCase(Locale.ROOT) + "' at offset "
                        + (offset + i) + (badDigit ? ", a digit nibble above 9" : ", a sign nibble below A"));
            }
            digits.append(b >> 4);
            if (i < length - 1) {
                digits.append(lo);
            }
        }
        int sign = rec[offset + length - 1] & 0x0F;
        BigDecimal v = new BigDecimal(new BigInteger(digits.toString()), scale);
        return sign == 0x0D || sign == 0x0B ? v.negate() : v;
    }

    public static void putPacked(byte[] rec, int offset, int length, int scale, boolean signed, BigDecimal value) {
        BigInteger unscaled = value.setScale(scale, RoundingMode.DOWN).unscaledValue();
        int digits = length * 2 - 1;
        String s = unscaled.abs().toString();
        s = s.length() > digits ? s.substring(s.length() - digits) : "0".repeat(digits - s.length()) + s;
        int sign = !signed ? 0x0F : unscaled.signum() < 0 ? 0x0D : 0x0C;
        for (int i = 0; i < length; i++) {
            int hi = s.charAt(2 * i) - '0';
            int lo = i < length - 1 ? s.charAt(2 * i + 1) - '0' : sign;
            rec[offset + i] = (byte) ((hi << 4) | lo);
        }
    }

    public static BigDecimal binary(byte[] rec, int offset, int length, int scale, boolean signed) {
        byte[] b = Arrays.copyOfRange(rec, offset, offset + length);
        BigInteger v = signed ? new BigInteger(b) : new BigInteger(1, b);
        return new BigDecimal(v, scale);
    }

    public static void putBinary(byte[] rec, int offset, int length, int scale, boolean signed, BigDecimal value) {
        BigInteger v = value.setScale(scale, RoundingMode.DOWN).unscaledValue();
        if (!signed) {
            v = v.abs();
        }
        byte[] b = v.toByteArray();
        byte fill = (byte) (v.signum() < 0 ? 0xFF : 0x00);
        for (int i = 0; i < length; i++) {
            int from = b.length - length + i;
            rec[offset + i] = from >= 0 ? b[from] : fill;
        }
    }

    public static BigDecimal decimal(Object value) {
        return decimal(value, '.');
    }

    /** A value as a decimal; text is read as NUMVAL reads it, with the program's DECIMAL-POINT. */
    public static BigDecimal decimal(Object value, char decimalPoint) {
        if (value == null) {
            return BigDecimal.ZERO;
        }
        if (value instanceof BigDecimal d) {
            return d;
        }
        if (value instanceof Number n) {
            return new BigDecimal(n.toString());
        }
        return numval(value.toString(), decimalPoint);
    }

    public static BigDecimal numval(String text) {
        return numval(text, '.');
    }

    /**
     * #3831: COBOL's FUNCTION NUMVAL. Leading and trailing spaces; one sign, either leading (`+` / `-`)
     * or trailing (`+` / `-` / `CR` / `DB`), spaces allowed between it and the number; ASCII digits with
     * at most one decimal point -- `decimalPoint`, which is `,` in a program that codes DECIMAL-POINT IS
     * COMMA (so `1,5` is one and a half there, and `1.5` is invalid). Anything else is invalid data: a
     * NumberFormatException, never a best guess.
     */
    public static BigDecimal numval(String text, char decimalPoint) {
        if (text == null) {
            throw new NumberFormatException("invalid numeric: null");
        }
        String s = text.strip();
        boolean negative = false;
        String upper = s.toUpperCase(Locale.ROOT);
        if (upper.endsWith("CR") || upper.endsWith("DB")) {
            negative = true;
            s = s.substring(0, s.length() - 2).stripTrailing();
        } else if (s.endsWith("-") || s.endsWith("+")) {
            negative = s.endsWith("-");
            s = s.substring(0, s.length() - 1).stripTrailing();
        } else if (s.startsWith("-") || s.startsWith("+")) {
            negative = s.startsWith("-");
            s = s.substring(1).stripLeading();
        }
        int point = s.indexOf(decimalPoint);
        String whole = point < 0 ? s : s.substring(0, point);
        String frac = point < 0 ? "" : s.substring(point + 1);
        boolean valid = !(whole.isEmpty() && frac.isEmpty())
                && (whole.isEmpty() || isAsciiDigits(whole))
                && (frac.isEmpty() || isAsciiDigits(frac));
        if (!valid) {
            throw new NumberFormatException("invalid numeric '" + text + "'");
        }
        BigDecimal v = new BigDecimal(new BigInteger((whole.isEmpty() ? "0" : whole) + frac), frac.length());
        return negative ? v.negate() : v;
    }

    private static boolean isAsciiDigits(String s) {
        if (s.isEmpty()) {
            return false;
        }
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c < '0' || c > '9') {
                return false;
            }
        }
        return true;
    }

    /** #3822: a key as its code page's bytes in upper-case hex (`A001` in IBM037 -> `C1F0F0F1`), so a
     *  database orders and compares it exactly as VSAM orders the EBCDIC key: lower case before upper,
     *  letters before digits. Two hex characters per byte keep the byte order under any collation. */
    public static String sortKey(String key, String codePage) {
        if (key == null) {
            return null;
        }
        byte[] bytes = key.getBytes(Charset.forName(codePage));
        StringBuilder hex = new StringBuilder(bytes.length * 2);
        for (byte b : bytes) {
            hex.append(Character.toUpperCase(Character.forDigit((b >> 4) & 0xF, 16)))
               .append(Character.toUpperCase(Character.forDigit(b & 0xF, 16)));
        }
        return hex.toString();
    }

    public static Integer toInteger(BigDecimal v) {
        return v.intValue();
    }

    public static Long toLong(BigDecimal v) {
        return v.longValue();
    }
}
"""


@dataclass
class Field:
    cobol: str
    java: str
    jtype: str
    offset: int
    bytes: int
    pic: str | None
    occurs: int | None
    pli_type: str | None = None  # #3720: a PL/I item's data type as written, when it has no picture
    usage: str | None = None  # #3624: a COBOL item's USAGE (COMP-3, COMP, ...), None for DISPLAY

    @property
    def described(self) -> str:
        return f"PIC {self.pic}" if self.pic else self.pli_type or "no PIC"


@dataclass
class Store:
    raw: dict
    entity: str
    table: str
    record: str
    record_file: str
    layout: dict
    fields: list[Field]
    key: Field | None  # the single field the key is, or None
    composite: list[Field]  # the adjacent fields a group key spans (an @EmbeddedId), else []
    key_type: str
    key_note: str  # how the key was found, or why there is no single-field key
    alternates: list[dict] = field(default_factory=list)  # {aix, paths, field: Field|None, unique}
    browse_forward: bool = False
    browse_back: bool = False

    @property
    def repository(self) -> str:
        return self.entity + "Repository"


class RepositoryForge:
    """Plans every VSAM store once, then the repository methods each program needs."""

    def __init__(self, estate: dict, skeletons: dict[str, dict], package: str,
                 target: JavaTarget | None = None, names: ClassNames | None = None, trace: TraceLog | None = None) -> None:  # fmt: skip
        self.package = package
        self.names = names if names is not None else ClassNames()  # shared with the other forges
        self.target = target or JavaTarget()
        self.trace = trace
        section = (estate.get("sections") or {}).get("vsam_stores") or {}
        self.status = status_text(section)
        self.key_of = {sk["program"]["file"]: key for key, sk in skeletons.items()}
        self.cls_of = {key: java_class_base(key) for key in skeletons}
        self.stores: list[Store] = []
        self.unmapped: list[tuple[str, str]] = []  # (store, why) -- no entity generated
        used_entities = self.names
        used_tables: set[str] = set()
        for raw in section.get("facts", []):
            plan = self._plan(raw, used_entities, used_tables)
            if plan is not None:
                self.stores.append(plan)
        self.extras: dict[str, dict[str, Any]] = {}
        for st in self.stores:
            for user in st.raw["users"]:
                key = self.key_of.get(user["program"])
                if key is not None:
                    self._service_methods(key, st, user)

    # ---- the store ----------------------------------------------------------
    def _plan(self, raw: dict, used_entities: ClassNames, used_tables: set[str]) -> Store | None:
        label = raw.get("dataset") or f"CICS FILE {raw.get('name')}"
        if not raw.get("users"):
            self.unmapped.append((label, "no program in the repository touches it"))
            return None
        if not any(u["program"] in self.key_of for u in raw["users"]):
            langs = sorted({u["program"].rsplit(".", 1)[-1].lower() for u in raw["users"]})
            self.unmapped.append((label, f"used only by programs this generator does not convert ({', '.join(langs)})"))
            return None
        # The layout: every record the programs use, grouped by shape; the one of the cluster's
        # RECORDSIZE first, then the one most programs use, then by name.
        options: dict[tuple, dict] = {}
        for u in raw["users"]:
            if u.get("via"):
                continue  # a path read returns the base record too; the base users decide
            for rec in u.get("records", []):
                if rec.get("layout") and rec["layout"].get("fields"):
                    o = options.setdefault(_signature(rec["layout"]), {"rec": rec, "users": 0})
                    o["users"] += 1
        if not options:
            self.unmapped.append((label, "no program's record layout for it was resolved"))
            return None
        # The key: IDCAMS first, else the RIDFLD / RECORD KEY the programs use.
        offset, length, source = raw.get("key_offset"), raw.get("key_length"), "IDCAMS KEYS"
        if offset is None or length is None:
            seen: dict[tuple, int] = {}
            for u in raw["users"]:
                if u.get("via"):
                    continue
                for r in u.get("ridflds", []):
                    if r.get("offset") is not None:
                        seen[(r["offset"], r["length"])] = seen.get((r["offset"], r["length"]), 0) + 1
                if u.get("key_offset") is not None:
                    seen[(u["key_offset"], u["key_length"])] = seen.get((u["key_offset"], u["key_length"]), 0) + 1
            if seen:
                offset, length = min(seen, key=lambda k: (-seen[k], k))  # the most used; ties by position
                source = "the programs' RIDFLD / RECORD KEY"

        # The layout, of the records the programs use: the one of the cluster's RECORDSIZE; then
        # the one in which the most keys (primary + alternate) are fields -- a batch FD often
        # folds an AIX key into a FILLER the CICS copybook names; then the most-used; then by name.
        size = raw.get("record_max")
        keys = [(offset, length)] + [
            (a.get("key_offset"), a.get("key_length")) for a in raw.get("alternate_indexes", [])
        ]

        def key_hits(o: dict) -> int:
            fl = self._fields(o["rec"]["layout"])
            hits = 0
            for off, ln in keys:
                if off is None or ln is None:
                    continue
                if any(f.offset == off and f.bytes == ln and not f.occurs for f in fl) or self._span(fl, off, ln):
                    hits += 1
            return hits

        best = sorted(options.values(), key=lambda o: (o["rec"]["layout"].get("bytes") != size, -key_hits(o),
                                                        -o["users"], o["rec"]["record"]))[0]["rec"]  # fmt: skip
        layout = best["layout"]
        fields = self._fields(layout)
        key = next((f for f in fields if f.offset == offset and f.bytes == length and not f.occurs), None)
        composite = [] if key is not None or offset is None or length is None else self._span(fields, offset, length)
        org = (raw.get("organization") or "").upper()
        base = java_class_base(best["record"])
        entity = base if base not in used_entities else java_class_base(_qualifier(raw)) + base
        while entity in used_entities or entity + "Repository" in used_entities or entity + "Key" in used_entities:
            entity += "X"
        used_entities.claim(entity)
        used_entities.claim(entity + "Repository")
        if key is not None:
            key_type, note = key.jtype, f"{key.cobol} (offset {offset}, {length} bytes, from {source})"
        elif composite:
            key_type = entity + "Key"
            note = (f"{', '.join(f.cobol for f in composite)} together (offset {offset}, {length} bytes, from "
                    f"{source}): the @EmbeddedId {key_type}")  # fmt: skip
        elif org in ("NONINDEXED", "NUMBERED"):
            key_type = "Long"
            note = ("an ESDS has no key: the relative byte address becomes a generated id" if org == "NONINDEXED"
                    else "an RRDS is keyed by relative record number: a Long id")  # fmt: skip
        elif offset is not None:
            key_type = "String"
            note = (f"TODO: the key (offset {offset}, {length} bytes, from {source}) is not one field of "
                    f"{best['record']}: carried as the String vsamKey -- keep it in step with the record")  # fmt: skip
        else:
            key_type = "String"
            note = "TODO: no key is known (no IDCAMS DEFINE, RIDFLD or RECORD KEY): carried as the String vsamKey"

        table = "vsam_" + re.sub(r"[^a-z0-9]+", "_", _qualifier(raw).lower()).strip("_")
        while table in used_tables:
            table += "_x"
        used_tables.add(table)

        if composite:
            used_entities.claim(key_type)
        st = Store(raw, entity, table, best["record"], best["file"], layout, fields, key, composite, key_type, note)
        for aix in raw.get("alternate_indexes", []):
            alt = next((f for f in fields if f.offset == aix.get("key_offset") and f.bytes == aix.get("key_length")
                        and not f.occurs), None)  # fmt: skip
            st.alternates.append({**aix, "field": alt})
        for u in raw["users"]:
            verbs = set(u.get("verbs", []))
            st.browse_forward |= bool(verbs & _BROWSE_FORWARD)
            st.browse_back |= "READPREV" in verbs
        return st

    @staticmethod
    def _span(fields: list[Field], offset: int, length: int) -> list[Field]:
        """The adjacent elementary fields that exactly cover [offset, offset + length): a group key."""
        run: list[Field] = []
        pos = offset
        for f in fields:
            if f.offset < offset:
                continue
            if f.offset != pos or f.occurs:
                break
            run.append(f)
            pos += f.bytes
            if pos >= offset + length:
                break
        return run if len(run) > 1 and pos == offset + length else []

    @staticmethod
    def _fields(layout: dict) -> list[Field]:
        out: list[Field] = []
        seen: dict[str, int] = {}
        for f in layout.get("fields", []):
            name = f.get("name")
            if not name or name.upper() == "FILLER":
                continue
            base = java_identifier(name)
            seen[base] = seen.get(base, 0) + 1
            java = base if seen[base] == 1 else f"{base}{seen[base]}"
            pic = f.get("pic")
            pli = f.get("dialect") == "pli"
            out.append(Field(name, java, java_type(f), f["offset"], f["bytes"], f"'{pic}'" if pli and pic else pic,
                             f.get("occurs"), f.get("usage") if pli else None,
                             None if pli else f.get("usage")))  # fmt: skip
        return out

    def _sorted_by_code_page(self, st: Store) -> bool:
        """#3822: whether browses order by the key's code-page bytes (a sort column) rather than the key."""
        k = st.key
        return self.target.culture.key_collation == "ebcdic" and k is not None and k.jtype == "String" and not k.occurs

    def _key_attrs(self, attrs: list[str], width: int | None) -> list[str]:
        """#3822: a String key column compared byte by byte. The databases' default collations fold case and
        accents (MySQL utf8mb4_0900_ai_ci makes `ABC` = `abc` = `ÀBC`), so distinct COBOL keys collide on the
        primary key and browse out of order. H2 compares code points by default; DB2 and Oracle's defaults
        (the table's code page, NLS_SORT=BINARY) are binary already."""
        if self.target.culture.key_collation == "database":
            return attrs
        n = max(width or 255, 1)
        engine = self.target.database.engine
        if engine == "postgresql":
            return [a for a in attrs if not a.startswith("length")] + [
                f'columnDefinition = "varchar({n}) COLLATE \\"C\\""'
            ]
        if engine == "mysql":
            return [a for a in attrs if not a.startswith("length")] + [
                f'columnDefinition = "varchar({n}) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin"'
            ]
        return attrs

    # ---- Java: entity + repository -------------------------------------------
    def entity_source(self, st: Store) -> str:
        if self.trace:
            facts = [
                {
                    "source": f"{st.raw.get('defined_in')}:{st.raw.get('line')}" if st.raw.get("defined_in") else "",
                    "section": "vsam_stores",
                    "ledger_field": "vsam_stores",
                    "field_testing": self.status,
                }
            ]
            todos = [st.key_note] if "TODO" in st.key_note else []
            self.trace.record(
                java_path(self.package, ENTITY_SUBPACKAGE, st.entity), "Class", "vsam-entity", facts, todos
            )
        t = self.target
        pkg = f"{self.package}.{ENTITY_SUBPACKAGE}"
        raw = st.raw
        java = [f"package {pkg};\n", "import jakarta.persistence.*;"]
        if t.lombok:
            java += ["import lombok.Data;", "import lombok.NoArgsConstructor;"]
        java += ["import java.math.BigDecimal;", "import java.util.List;", ""]
        java.append("/**")
        where = f"{raw['defined_in']}:{raw['line']}" if raw.get("defined_in") else "no IDCAMS DEFINE in the repository"
        java.append(f" * VSAM {raw.get('organization') or 'file'} {raw.get('dataset') or raw.get('name')} ({where}),")
        defined_by = raw.get("defined_by") or {}
        if defined_by.get("match") == "symbolic":
            java.append(
                f" * IDCAMS define matched by installation-symbol pattern {defined_by.get('pattern')} (a candidate join: {'; '.join(defined_by.get('evidence', []))})."
            )
        java.append(f" * record {st.record} ({st.record_file}, {st.layout.get('bytes')} bytes"
                    f"{', RECORDSIZE ' + str(raw['record_max']) if raw.get('record_max') else ''}).")  # fmt: skip
        java.append(f" * Key: {st.key_note}.")
        if raw.get("cics_files"):
            java.append(" * CICS files: " + ", ".join(sorted({c["file"] + (f" (path {c['via']})" if c.get("via") else "")
                                                            for c in raw["cics_files"]})) + ".")  # fmt: skip
        java.append(f" * Generated from GitGalaxy's verified skeleton; VSAM defines field testing: {self.status}.")
        java.append(" */")
        java.append(f'@Entity(name = "Vsam{st.entity}")')
        java.append(f'@Table(name = "{st.table}")')
        if t.lombok:
            java += ["@Data", "@NoArgsConstructor"]
        java.append(f"public class {st.entity} {{\n")
        body: list[str] = []
        if st.composite:
            body += [f"    // {st.key_note}", "    @EmbeddedId", f"    private {st.key_type} id;\n"]
        elif st.key is None:
            org = (raw.get("organization") or "").upper()
            if org in ("NONINDEXED", "NUMBERED"):
                body += ["    // " + st.key_note, "    @Id", "    @GeneratedValue", "    private Long id;\n"]
            else:
                attrs = self._key_attrs(['name = "VSAM_KEY"'], None)
                body += [
                    "    // " + st.key_note,
                    "    @Id",
                    f"    @Column({', '.join(attrs)})",
                    "    private String vsamKey;\n",
                ]
        for f in st.fields:
            if f in st.composite:
                continue  # in the key class
            body.append(f"    // {f.cobol}: {f.described}, offset {f.offset}, {f.bytes} bytes")
            if f is st.key:
                body.append("    @Id")
            column = f.cobol.upper().replace("-", "_")
            if f.occurs:
                body.append("    @ElementCollection")
                body.append(f'    @CollectionTable(name = "{st.table}_{column.lower()}")')
                body.append(f"    private List<{f.jtype}> {f.java};\n")
                continue
            attrs = [f'name = "{column}"', *_decimal_attrs(f)]
            if f.jtype == "String" and f.bytes is not None:  # a width not known: the JPA default
                attrs.append(f"length = {max(f.bytes, 1)}")
            if f is st.key and f.jtype == "String":
                attrs = self._key_attrs(attrs, f.bytes)
            body.append(f"    @Column({', '.join(attrs)})")
            body.append(f"    private {f.jtype} {f.java};\n")
        sort_hook: list[str] = []
        k = st.key
        if k is not None and self._sorted_by_code_page(st):
            cp = self.target.data.code_page
            column = k.cobol.upper().replace("-", "_") + "_SORT"
            attrs = self._key_attrs([f'name = "{column}"', f"length = {2 * max(k.bytes or 1, 1)}"],
                                    2 * max(k.bytes or 1, 1))  # fmt: skip
            body += [f"    // #3822: {k.cobol} as {cp} bytes in hex -- browses order by it, as VSAM orders the key",
                     f"    @Column({', '.join(attrs)})", f"    private String {k.java}Sort;\n"]  # fmt: skip
            sort_hook = ["    @PrePersist", "    @PreUpdate", "    void codePageSortKey() {",
                         f'        this.{k.java}Sort = CobolRecords.sortKey({k.java}, "{cp}");', "    }\n"]  # fmt: skip
        java += body
        if not t.lombok:
            java += _accessors(st.entity, _declared_fields(body))
        java += sort_hook
        java += self._codec(st)
        java.append("}")
        return "\n".join(java)

    # ---- #3624: the record codec -------------------------------------------------------
    def _codec(self, st: Store) -> list[str]:
        """`fromRecord(byte[], Charset)` / `toRecord(Charset)`: the entity from and to its fixed-width
        VSAM record (as REPRO unloads it), field by field at the COBOL offsets -- DISPLAY text,
        zoned decimal with its sign overpunched, COMP-3, COMP. `text` is the record's character set
        (ISO-8859-1 for an ASCII transfer, IBM037 on z/OS). A record with an item the codec cannot
        represent (an OCCURS table, COMP-1 / COMP-2, a PL/I item) gets none, saying why."""
        reclen = st.layout.get("bytes")
        why = None
        if not reclen:
            why = "the record's width is not known"
        elif any(f.pli_type or (f.pic or "").startswith("'") for f in st.fields):
            why = "a PL/I record (its types are not COBOL PICTUREs)"
        elif any(f.occurs for f in st.fields):
            why = "an OCCURS table (a List field) is not laid out by it"
        elif any(f.offset is None or f.bytes is None or not _codec_kind(f) for f in st.fields):
            why = "an item with no PICTURE or width (COMP-1 / COMP-2 / POINTER) is not encoded by it"
        if why:
            return ["", f"    // #3624: no record codec: {why}."]
        cls, key = st.entity, (lambda f: f"id.get{f.java[0].upper()}{f.java[1:]}()")
        load = [f"        {cls} r = new {cls}();"]
        store = [f"        byte[] rec = CobolRecords.blank({reclen}, text);"]
        if st.composite:
            load.append(f"        r.id = new {st.key_type}();")
        elif st.key is None and (st.raw.get("organization") or "").upper() not in ("NONINDEXED", "NUMBERED"):
            off, ln = st.raw.get("key_offset"), st.raw.get("key_length")
            if off is not None and ln:
                load.append(f"        r.vsamKey = CobolRecords.text(rec, {off}, {ln}, text);")
        for f in st.fields:
            dbcs_page = getattr(self.target.data, "dbcs_code_page", None)
            get = _codec_get(f, dbcs_page)
            if f in st.composite:
                load.append(f"        r.id.set{f.java[0].upper()}{f.java[1:]}({get});")
                store.append(f"        {_codec_put(f, key(f), dbcs_page)};")
            else:
                load.append(f"        r.{f.java} = {get};")
                store.append(f"        {_codec_put(f, f.java, dbcs_page)};")
        return [
            "",
            f"    /** #3624: this record from its fixed-width VSAM form ({reclen} bytes, as REPRO unloads it), each",
            "     *  field at its COBOL offset; `text` is the record's character set (ISO-8859-1 for an ASCII",
            "     *  transfer, IBM037 on z/OS). FILLER bytes are not kept. */",
            f"    public static {cls} fromRecord(byte[] rec, java.nio.charset.Charset text) {{",
            *load,
            "        return r;",
            "    }",
            "",
            "    /** #3624: the fixed-width VSAM record of this entity (FILLER as spaces). */",
            "    public byte[] toRecord(java.nio.charset.Charset text) {",
            *store,
            "        return rec;",
            "    }",
        ]

    def edit_source(self) -> str | None:
        """#3827: the CobolEdit runtime (numeric-edited PICTUREs), beside CobolRecords, or None without an
        entity."""
        if not self.stores:
            return None
        return cobol_edit_source(self.target.project.package)

    def records_source(self) -> str | None:
        """#3624: the CobolRecords runtime the record codecs share, or None without an entity."""
        if not self.stores:
            return None
        from gitgalaxy.tools.cobol_to_java.java_target import zoned_sign_characters

        pos, neg = zoned_sign_characters(self.target.data.code_page)

        def escape(s: str) -> str:
            return "".join(c if 32 <= ord(c) <= 126 and c not in '\\"' else f"\\u{ord(c):04x}" for c in s)

        return (
            COBOL_RECORDS_JAVA.replace("__PACKAGE__", f"{self.package}.{ENTITY_SUBPACKAGE}")
            .replace("__POSITIVE__", escape(pos))
            .replace("__NEGATIVE__", escape(neg))
        )

    def key_source(self, st: Store) -> str | None:
        """The @Embeddable key class of a group key, or None."""
        if not st.composite:
            return None
        if self.trace:
            facts = [
                {
                    "source": f"{st.raw.get('defined_in')}:{st.raw.get('line')}" if st.raw.get("defined_in") else "",
                    "section": "vsam_stores",
                    "ledger_field": "vsam_stores",
                    "field_testing": self.status,
                }
            ]
            self.trace.record(java_path(self.package, ENTITY_SUBPACKAGE, st.key_type), "Class", "vsam-key", facts, [])
        t = self.target
        pkg = f"{self.package}.{ENTITY_SUBPACKAGE}"
        java = [f"package {pkg};\n", "import jakarta.persistence.*;", "import java.io.Serializable;",
                "import java.math.BigDecimal;", "import java.util.Objects;"]  # fmt: skip
        if t.lombok:
            java += ["import lombok.Data;", "import lombok.NoArgsConstructor;"]
        java += ["", "/**", f" * The key of {st.entity}: {st.key_note}.", " */", "@Embeddable"]
        if t.lombok:
            java += ["@Data", "@NoArgsConstructor"]
        java.append(f"public class {st.key_type} implements Serializable {{\n")
        body: list[str] = []
        for f in st.composite:
            column = f.cobol.upper().replace("-", "_")
            attrs = [f'name = "{column}"', *_decimal_attrs(f)] + (
                [f"length = {max(f.bytes, 1)}"] if f.jtype == "String" and f.bytes is not None else []
            )
            if f.jtype == "String":
                attrs = self._key_attrs(attrs, f.bytes)
            body += [f"    // {f.cobol}: {f.described}, offset {f.offset}, {f.bytes} bytes",
                     f"    @Column({', '.join(attrs)})", f"    private {f.jtype} {f.java};\n"]  # fmt: skip
        java += body
        if not t.lombok:  # a composite id needs value equality
            java += _accessors(st.key_type, _declared_fields(body))
            names = [f.java for f in st.composite]
            java += ["    @Override", "    public boolean equals(Object o) {",
                     "        if (this == o) return true;",
                     f"        if (!(o instanceof {st.key_type} other)) return false;",
                     "        return " + " && ".join(f"Objects.equals({n}, other.{n})" for n in names) + ";",
                     "    }\n", "    @Override", "    public int hashCode() {",
                     f"        return Objects.hash({', '.join(names)});", "    }\n"]  # fmt: skip
        java.append("}")
        return "\n".join(java)

    def _id_field(self, st: Store) -> str | None:
        return st.key.java if st.key is not None else None

    def repository_source(self, st: Store) -> str:
        if self.trace:
            facts = [
                {
                    "source": f"{st.raw.get('defined_in')}:{st.raw.get('line')}" if st.raw.get("defined_in") else "",
                    "section": "vsam_stores",
                    "ledger_field": "vsam_stores",
                    "field_testing": self.status,
                }
            ]
            self.trace.record(
                java_path(self.package, REPOSITORY_SUBPACKAGE, st.repository), "Class", "vsam-repository", facts, []
            )
        pkg = f"{self.package}.{REPOSITORY_SUBPACKAGE}"
        java = [f"package {pkg};\n",
                "import org.springframework.data.domain.Pageable;",
                "import org.springframework.data.jpa.repository.JpaRepository;",
                "import org.springframework.stereotype.Repository;",
                "import java.math.BigDecimal;", "import java.util.List;", "import java.util.Optional;",
                f"import {self.package}.{ENTITY_SUBPACKAGE}.{st.entity};",
                *([f"import {self.package}.{ENTITY_SUBPACKAGE}.{st.key_type};"] if st.composite else []), ""]  # fmt: skip
        users = sorted(
            {f"{u['program']} ({','.join(u.get('verbs') or u.get('modes') or [])})" for u in st.raw["users"]}
        )
        java += ["/**",
                 f" * {st.raw.get('dataset') or st.raw.get('name')}: READ / WRITE / REWRITE / DELETE are JpaRepository's",
                 " * findById / save / deleteById. Used by " + "; ".join(users) + ".",
                 " */", "@Repository",
                 f"public interface {st.repository} extends JpaRepository<{st.entity}, {st.key_type}> {{\n"]  # fmt: skip
        key = self._id_field(st)
        if key and self._sorted_by_code_page(st):
            by = key[0].upper() + key[1:] + "Sort"
            if st.browse_forward:
                java += ["    /** EXEC CICS STARTBR + READNEXT: records from a key onward, in the key's code-page order",
                         "     *  (#3822: pass CobolRecords.sortKey(key, codePage)). */",
                         f"    List<{st.entity}> findBy{by}GreaterThanEqualOrderBy{by}Asc(String {key}Sort, Pageable page);\n"]  # fmt: skip
            if st.browse_back:
                java += ["    /** EXEC CICS READPREV: records from a key backward, in reverse code-page order",
                         "     *  (#3822: pass CobolRecords.sortKey(key, codePage)). */",
                         f"    List<{st.entity}> findBy{by}LessThanEqualOrderBy{by}Desc(String {key}Sort, Pageable page);\n"]  # fmt: skip
        elif key:
            cap = key[0].upper() + key[1:]
            if st.browse_forward:
                java += ["    /** EXEC CICS STARTBR + READNEXT: records from a key onward, in key order. */",
                         f"    List<{st.entity}> findBy{cap}GreaterThanEqualOrderBy{cap}Asc({st.key_type} {key}, Pageable page);\n"]  # fmt: skip
            if st.browse_back:
                java += ["    /** EXEC CICS READPREV: records from a key backward, in reverse key order. */",
                         f"    List<{st.entity}> findBy{cap}LessThanEqualOrderBy{cap}Desc({st.key_type} {key}, Pageable page);\n"]  # fmt: skip
        elif st.composite and (st.browse_forward or st.browse_back):
            order = "".join(f"Id{f.java[0].upper() + f.java[1:]}Asc" for f in st.composite)
            java += ["    /** EXEC CICS STARTBR / READNEXT over a group key: every record in key order. TODO: start",
                     "     *  from a key -- a range over an @EmbeddedId is not a derived query. */",
                     f"    List<{st.entity}> findAllByOrderBy{order}(Pageable page);\n"]  # fmt: skip
        elif st.browse_forward or st.browse_back:
            java.append(
                f"    // TODO: STARTBR / READNEXT / READPREV browse the key, which is not one field ({st.key_note}).\n"
            )
        declared: set[str] = set()
        for alt in st.alternates:
            f = alt["field"]
            paths = ", ".join(alt.get("paths") or []) or "no PATH"
            if f is None:
                java.append(f"    // TODO: alternate index {alt['aix']} (path {paths}): its key (offset "
                            f"{alt.get('key_offset')}, {alt.get('key_length')} bytes) is not one field.\n")  # fmt: skip
                continue
            cap = f.java[0].upper() + f.java[1:]
            ret = f"Optional<{st.entity}>" if alt.get("unique") else f"List<{st.entity}>"
            if f"findBy{cap}" in declared:
                java.append(
                    f"    // Alternate index {alt['aix']} (path {paths}) is on {f.cobol} too: findBy{cap} above.\n"
                )
                continue
            declared.add(f"findBy{cap}")
            java += [f"    /** Alternate index {alt['aix']} (path {paths}) on {f.cobol}, "
                     f"{'unique' if alt.get('unique') else 'non-unique'}. */",
                     f"    {ret} findBy{cap}({f.jtype} {f.java});\n"]  # fmt: skip
            if self.trace:
                facts = [
                    {
                        "source": f"{st.raw.get('defined_in')}:{st.raw.get('line')}"
                        if st.raw.get("defined_in")
                        else "",
                        "section": "vsam_stores",
                        "ledger_field": "alternate_indexes",
                        "field_testing": self.status,
                    }
                ]
                self.trace.record(
                    java_path(self.package, REPOSITORY_SUBPACKAGE, st.repository),
                    f"{st.repository}#findBy{cap}",
                    "repository-finder",
                    facts,
                    [],
                )
        java.append("}")
        return "\n".join(java)

    # ---- Java: the programs' services -----------------------------------------
    def _service_methods(self, key: str, st: Store, user: dict) -> None:
        ex = self.extras.setdefault(key, {"imports": set(), "fields": {}, "methods": []})
        repo_var = st.repository[0].lower() + st.repository[1:]
        ex["fields"][repo_var] = st.repository
        ex["imports"] |= {f"import {self.package}.{REPOSITORY_SUBPACKAGE}.{st.repository};",
                          f"import {self.package}.{ENTITY_SUBPACKAGE}.{st.entity};",
                          "import java.util.List;", "import java.util.Optional;",
                          "import java.math.BigDecimal;"}  # fmt: skip
        if st.composite:
            ex["imports"].add(f"import {self.package}.{ENTITY_SUBPACKAGE}.{st.key_type};")
        name = java_class_base(user["name"])
        lines = ", ".join(str(n) for n in user.get("lines", [])) or "its FD"
        where = f"{user['program']}:{lines}" if user.get("lines") else f"{user['program']} (SELECT {user['name']})"
        notes = []
        mine = [r for r in user.get("records", []) if r.get("layout")]
        if mine and all(_signature(r["layout"]) != _signature(st.layout) for r in mine):
            r = mine[0]
            notes.append(f"TODO: this program uses {r['record']} ({r['layout'].get('bytes')} bytes); the entity "
                         f"follows {st.record} ({st.layout.get('bytes')} bytes) -- map one onto the other")  # fmt: skip
        k, kt = self._id_field(st), st.key_type
        ops: list[tuple[str, list[str]]] = []
        if user["kind"] == "cics":
            verbs = set(user.get("verbs", []))
            if user.get("via"):
                alt = next(
                    (a for a in st.alternates if user["via"] in (a.get("paths") or []) or user["via"] == a["aix"]), None
                )
                f = alt["field"] if alt is not None else None
                if alt is not None and f is not None and verbs & {"READ", "STARTBR", "READNEXT", "READPREV"}:
                    cap = f.java[0].upper() + f.java[1:]
                    ret = f"Optional<{st.entity}>" if alt.get("unique") else f"List<{st.entity}>"
                    ops.append((f"read{name}", [f"    public {ret} read{name}({f.jtype} {f.java}) {{",
                                                f"        return {repo_var}.findBy{cap}({f.java});", "    }\n"]))  # fmt: skip
                else:
                    notes.append(f"TODO: {user['name']} reads through path {user['via']}, whose key is not one field")
            else:
                if "READ" in verbs:
                    ops.append((f"read{name}", [f"    public Optional<{st.entity}> read{name}({kt} key) {{",
                                                f"        return {repo_var}.findById(key);", "    }\n"]))  # fmt: skip
                if "WRITE" in verbs:
                    ops.append((f"write{name}", self._save(f"write{name}", st, repo_var)))
                if "REWRITE" in verbs:
                    ops.append((f"rewrite{name}", self._save(f"rewrite{name}", st, repo_var)))
                if "DELETE" in verbs:
                    ops.append((f"delete{name}", [f"    public void delete{name}({kt} key) {{",
                                                  f"        {repo_var}.deleteById(key);", "    }\n"]))  # fmt: skip
                sort = ""
                if k and self._sorted_by_code_page(st) and verbs & (_BROWSE_FORWARD | {"READPREV"}):
                    ex["imports"].add(f"import {self.package}.{ENTITY_SUBPACKAGE}.CobolRecords;")
                    sort = "Sort"
                arg = f'CobolRecords.sortKey(from, "{self.target.data.code_page}")' if sort else "from"
                if k and verbs & _BROWSE_FORWARD:
                    cap = k[0].upper() + k[1:] + sort
                    ops.append((f"browse{name}", [
                        f"    public List<{st.entity}> browse{name}({kt} from, int count) {{",
                        f"        return {repo_var}.findBy{cap}GreaterThanEqualOrderBy{cap}Asc({arg}, "
                        "org.springframework.data.domain.PageRequest.of(0, count));", "    }\n"]))  # fmt: skip
                if k and "READPREV" in verbs:
                    cap = k[0].upper() + k[1:] + sort
                    ops.append((f"browseBack{name}", [
                        f"    public List<{st.entity}> browseBack{name}({kt} from, int count) {{",
                        f"        return {repo_var}.findBy{cap}LessThanEqualOrderBy{cap}Desc({arg}, "
                        "org.springframework.data.domain.PageRequest.of(0, count));", "    }\n"]))  # fmt: skip
        else:
            modes = set(user.get("modes", []))
            sequential = (user.get("access_mode") or "SEQUENTIAL").upper() == "SEQUENTIAL"
            if modes & {"INPUT", "I-O"}:
                if sequential:
                    order, why = self._file_order(st)
                    by = ", ".join(f'"{p}"' for p in order)
                    ops.append((f"readAll{name}", [
                        f"    // {why}",
                        f"    public List<{st.entity}> readAll{name}() {{",
                        f"        return {repo_var}.findAll(org.springframework.data.domain.Sort.by({by}));",
                        "    }\n"]))  # fmt: skip
                else:
                    ops.append((f"read{name}", [f"    public Optional<{st.entity}> read{name}({kt} key) {{",
                                                f"        return {repo_var}.findById(key);", "    }\n"]))  # fmt: skip
            if modes & {"OUTPUT", "EXTEND"}:
                ops.append((f"write{name}", self._save(f"write{name}", st, repo_var)))
            if "I-O" in modes:
                ops.append((f"rewrite{name}", self._save(f"rewrite{name}", st, repo_var)))
            if not modes:
                notes.append("TODO: no OPEN mode for this DD is known (no JCL step in the repository runs it): "
                             "no access method generated")  # fmt: skip
        taken = set(ex.setdefault("names", set()))
        head = (f"    /** {st.raw.get('dataset') or st.raw.get('name')} as {user['kind'].upper()} "
                f"{'file' if user['kind'] == 'cics' else 'SELECT'} {user['name']} at {where}; "
                f"VSAM defines field testing: {self.status}. */")  # fmt: skip
        fresh = [(m, b) for m, b in ops if m not in taken]
        if fresh or notes:
            ex["methods"].append(head)
            ex["methods"] += [f"    // {n}" for n in notes]
        for method, body in fresh:
            taken.add(method)
            ex["methods"] += body
            if self.trace:
                facts = [
                    {
                        "source": f"{user['program']}:{line}",
                        "section": "vsam_stores",
                        "ledger_field": "users",
                        "field_testing": self.status,
                    }
                    for line in user.get("lines", [])
                ]
                if not facts:
                    facts = [
                        {
                            "source": f"{user['program']}",
                            "section": "vsam_stores",
                            "ledger_field": "users",
                            "field_testing": self.status,
                        }
                    ]
                self.trace.record(
                    java_path(self.package, "service", f"{self.cls_of[key]}Service"),
                    f"{self.cls_of[key]}Service#{method}",
                    "service-file-op",
                    facts,
                    notes,
                )
        ex["names"] = taken

    def _file_order(self, st: Store) -> tuple[list[str], str]:
        """#3945: the entity properties a sequential READ of the file orders by, and why -- a bare findAll()
        sends no ORDER BY, so records came back in the database's order (heap order on PostgreSQL), not the
        file's. A KSDS reads in ascending key order: a String key under key_collation ebcdic by its sort column
        (the key's code-page bytes, #3822), any other key by itself. An RRDS reads in relative record number
        order (its Long id); an ESDS in entry (RBA) order, which its generated id follows as rows are added."""
        k = st.key
        if k is not None and self._sorted_by_code_page(st):
            return [k.java + "Sort"], (f"Sequential READ: in key order, {k.cobol} as {self.target.data.code_page} "
                                       "bytes (#3945, #3822).")  # fmt: skip
        if k is not None:
            return [k.java], f"Sequential READ: in key order ({k.cobol}, #3945)."
        if st.composite:
            text = any(f.jtype == "String" for f in st.composite) and self.target.culture.key_collation == "ebcdic"
            todo = " TODO: its text parts order by the database's collation, not the code page's bytes." if text else ""
            return (["id." + f.java for f in st.composite],
                    f"Sequential READ: in key order ({', '.join(f.cobol for f in st.composite)}, #3945).{todo}")  # fmt: skip
        org = (st.raw.get("organization") or "").upper()
        if org == "NUMBERED":
            return ["id"], "Sequential READ of an RRDS: in relative record number order (#3945)."
        if org == "NONINDEXED":
            return ["id"], ("Sequential READ of an ESDS: in entry (RBA) order, which the generated id follows as "
                            "records are added (#3945).")  # fmt: skip
        todo = (" TODO: the key is not one field, so it orders by its text, not the code page's bytes."
                if self.target.culture.key_collation == "ebcdic" else "")  # fmt: skip
        return ["vsamKey"], f"Sequential READ: in key order (the vsamKey, #3945).{todo}"

    @staticmethod
    def _save(method: str, st: Store, repo_var: str) -> list[str]:
        return [f"    public {st.entity} {method}({st.entity} record) {{", f"        return {repo_var}.save(record);",
                "    }\n"]  # fmt: skip

    def service_extras(self, key: str) -> dict | None:
        ex = self.extras.get(key)
        if not ex:
            return None
        return {"imports": sorted(ex["imports"]), "fields": [(t, n) for n, t in ex["fields"].items()],
                "methods": ex["methods"]}  # fmt: skip


def cobol_edit_source(package: str) -> str:
    """#3827: the generated CobolEdit class, in `<package>.entity.vsam`."""
    return f"package {package}.entity.vsam;\n\n" + _COBOL_EDIT


_COBOL_EDIT = """import java.math.BigDecimal;
import java.math.RoundingMode;

/** #3827: a number rendered through a numeric-edited PICTURE as COBOL renders it -- Z / * zero suppression,
 *  9, the `.` and `,` insertion characters (which one is the decimal point follows DECIMAL-POINT IS COMMA),
 *  a trailing or leading fixed - / +, CR / DB, the currency sign, B, 0 and /. #3933: floating insertion
 *  strings (`$$$,$$9.99`, `+++9`, `---9`, `III,II9.99`) float the sign or currency string to just left of
 *  the first significant digit. `currency` is the program's CURRENCY SIGN string ('EUR ', 'INR ', 'Rs'):
 *  it replaces `$` or the declared PICTURE SYMBOL (any character that is no editing symbol: U, I, K, or a
 *  one-character sign); null keeps the PICTURE's own character. Porting rules require it for edited fields. */
public final class CobolEdit {
    private CobolEdit() {}

    /** The PICTURE's editing symbols; any other character is its currency symbol (#3933). */
    private static final String EDITING = "9Z*.,+-CRDBV0/$";

    public static String format(String pic, BigDecimal value, boolean decimalComma, String currency) {
        pic = expand(pic);
        if (value == null) return pic.replaceAll("[9Z*]", "0");
        // #3933: the currency symbol -- `$`, or the declared sign / PICTURE SYMBOL -- stands for the whole
        // currency string; it is read as `$` below
        char symbol = '$';
        for (int i = 0; i < pic.length(); i++) {
            if (EDITING.indexOf(pic.charAt(i)) == -1) {
                symbol = pic.charAt(i);
                break;
            }
        }
        String cur = currency != null ? currency : String.valueOf(symbol);
        pic = pic.replace(symbol, '$');
        boolean neg = value.compareTo(BigDecimal.ZERO) < 0;
        BigDecimal abs = value.abs();

        int digits = 0;
        int scale = 0;
        char decChar = decimalComma ? ',' : '.';

        int decIdx = pic.indexOf('V');
        if (decIdx == -1) decIdx = pic.indexOf(decChar);
        if (decIdx == -1) decIdx = pic.length();

        // #3933: a floating insertion string -- two or more of `$`, `+` or `-`, with only the insertion
        // characters , . B 0 / between them (IBM Enterprise COBOL Language Reference, PICTURE clause,
        // "Floating insertion editing"). Its first symbol is the sign / currency position only; each other
        // one is a digit position.
        char floating = 0;
        int floatStart = -1;
        int floatEnd = -1;
        for (char f : new char[] {'$', '+', '-'}) {
            int a = pic.indexOf(f);
            if (a == -1) continue;
            int b = a;
            int n = 1;
            for (int i = a + 1; i < pic.length(); i++) {
                char c = pic.charAt(i);
                if (c == f) {
                    b = i;
                    n++;
                } else if (",.B0/".indexOf(c) == -1) {
                    break;
                }
            }
            if (n >= 2) {
                floating = f;
                floatStart = a;
                floatEnd = b;
                break;
            }
        }

        boolean allFloating = floating != 0;
        for (int i = 0; i < pic.length(); i++) {
            char c = pic.charAt(i);
            boolean floatDigit = floating != 0 && c == floating && i > floatStart && i <= floatEnd;
            if (c == '9' || c == 'Z' || c == '*' || floatDigit) {
                digits++;
                if (i > decIdx) scale++;
                if (!floatDigit) allFloating = false;
            }
        }

        String raw = abs.setScale(scale, RoundingMode.HALF_UP).toPlainString().replace(".", "");
        while (raw.length() < digits) raw = "0" + raw;
        if (raw.length() > digits) raw = raw.substring(raw.length() - digits);

        // one output string per PICTURE position: a floating symbol is placed after the positions it passes
        String[] cells = new String[pic.length()];
        String floatText = floating == '$' ? cur : floating == '+' ? (neg ? "-" : "+") : (neg ? "-" : " ");
        boolean floatSuppression = floating != 0;
        int floatAt = -1;  // the last position blanked in the floating string: where the symbol goes
        int rawIdx = 0;
        boolean zeroSuppression = true;

        for (int i = 0; i < pic.length(); i++) {
            char c = pic.charAt(i);
            if (floatSuppression && i > floatEnd) {
                // every digit of the floating string was a leading zero: the symbol takes its last position
                cells[floatAt] = floatText;
                floatSuppression = false;
            }
            if (floating != 0 && i >= floatStart && i <= floatEnd) {
                if (i == floatStart) {
                    cells[i] = " ";
                    floatAt = i;
                } else if (c == floating) {
                    char d = raw.charAt(rawIdx++);
                    if (floatSuppression && d == '0' && i < decIdx) {
                        cells[i] = " ";
                        floatAt = i;
                    } else {
                        if (floatSuppression) cells[floatAt] = floatText;
                        floatSuppression = false;
                        zeroSuppression = false;
                        cells[i] = String.valueOf(d);
                    }
                } else if (c == decChar && i == decIdx) {
                    // the decimal point ends the suppression: the symbol goes just left of it (`$.05`)
                    if (floatSuppression) cells[floatAt] = floatText;
                    floatSuppression = false;
                    zeroSuppression = false;
                    cells[i] = String.valueOf(c);
                } else if (floatSuppression) {
                    // an insertion character before the first significant digit is blanked, and floated over
                    cells[i] = " ";
                    floatAt = i;
                } else {
                    cells[i] = c == 'B' ? " " : String.valueOf(c);
                }
                continue;
            }
            if (c == '9' || c == 'Z' || c == '*') {
                char d = raw.charAt(rawIdx++);
                if (c == 'Z') {
                    if (d == '0' && zeroSuppression) cells[i] = " ";
                    else { cells[i] = String.valueOf(d); zeroSuppression = false; }
                } else if (c == '*') {
                    if (d == '0' && zeroSuppression) cells[i] = "*";
                    else { cells[i] = String.valueOf(d); zeroSuppression = false; }
                } else {
                    cells[i] = String.valueOf(d);
                    zeroSuppression = false;
                }
            } else if (c == '.' || c == ',') {
                if (zeroSuppression && (pic.indexOf('Z') != -1 || pic.indexOf('*') != -1)) {
                    if (c == decChar) {
                        cells[i] = String.valueOf(c);
                        zeroSuppression = false; // Decimal point cancels zero suppression
                    } else {
                        cells[i] = pic.indexOf('*') != -1 ? "*" : " ";
                    }
                } else {
                    cells[i] = String.valueOf(c);
                }
            } else if (c == '-') {
                cells[i] = neg ? "-" : " ";
            } else if (c == '+') {
                cells[i] = neg ? "-" : "+";
            } else if (c == 'C' && i + 1 < pic.length() && pic.charAt(i + 1) == 'R') {
                cells[i] = neg ? "CR" : "  ";
                cells[++i] = "";
            } else if (c == 'D' && i + 1 < pic.length() && pic.charAt(i + 1) == 'B') {
                cells[i] = neg ? "DB" : "  ";
                cells[++i] = "";
            } else if (c == '$') {
                cells[i] = cur;
            } else if (c == 'B') {
                cells[i] = " ";
            } else if (c == '0' || c == '/') {
                if (zeroSuppression) cells[i] = pic.indexOf('*') != -1 ? "*" : " ";
                else cells[i] = String.valueOf(c);
            } else if (c == 'V') {
                cells[i] = ""; // Implicit, do nothing
            } else {
                cells[i] = String.valueOf(c);
            }
        }
        if (floatSuppression) cells[floatAt] = floatText;
        String out = String.join("", cells);
        // IBM: when every digit position is in the floating string, a zero value edits to all spaces
        if (allFloating && raw.chars().allMatch(ch -> ch == '0')) return " ".repeat(out.length());
        return out;
    }

    /** `Z(3)9(2)` -> `ZZZ99`, upper case, without S and P (a sign and scaling have no display position). */
    private static String expand(String pic) {
        StringBuilder ex = new StringBuilder();
        for (int i = 0; i < pic.length(); i++) {
            char c = Character.toUpperCase(pic.charAt(i));
            if (c == '(' && ex.length() > 0) {
                int j = pic.indexOf(')', i);
                int n = Integer.parseInt(pic.substring(i + 1, j).trim());
                char r = ex.charAt(ex.length() - 1);
                for (int k = 1; k < n; k++) ex.append(r);
                i = j;
            } else if (c != 'S' && c != 'P') {
                ex.append(c);
            }
        }
        return ex.toString();
    }
}
"""
