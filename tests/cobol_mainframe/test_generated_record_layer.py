"""The generated Java record layer, as the mainframe behaves:

- #3945: a batch program's sequential READ of a VSAM file reads it in the file's order -- a KSDS in key order
  (a String key under key_collation ebcdic by its code-page sort column, any other key by itself), an RRDS by
  relative record number, an ESDS in entry order -- never a bare findAll() in the database's order;
- #3946: Db2Dates.parseTimestamp takes the digits 0-9 only, as DB2 does (-180 / -181 otherwise);
- #3949: invalid packed decimal (a digit nibble above 9, a sign nibble below A) is a data exception (S0C7),
  in EbcdicDecoderUtil.unpackComp3 and in CobolRecords.packed, never a zero;
- #3950: a BigDecimal column of a VSAM entity carries its PICTURE's precision and scale.

The Java is compiled and run with the JDK, as the Cultural Gauntlet's --run layer does (its `jdk()`).
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import pytest

from gitgalaxy.tools.cobol_to_java.cobol_to_java_common import parse_pic_precision
from gitgalaxy.tools.cobol_to_java.cobol_to_java_db2_forge import db2_dates_source
from gitgalaxy.tools.cobol_to_java.cobol_to_java_decoder_forge import generate_decoder_util
from gitgalaxy.tools.cobol_to_java.cobol_to_java_repository_forge import RepositoryForge
from gitgalaxy.tools.cobol_to_java.cobol_to_java_spring_forge import generate_java_entity
from gitgalaxy.tools.cobol_to_java.java_target import target_from_dict

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from cultural_gauntlet import _maven_jar, entity_ddl, jdk  # noqa: E402

PKG = "com.test"


# ---- a synthetic VSAM store ---------------------------------------------------------------------------------
def _fld(name: str, pic: str, offset: int, size: int, cls: str, usage: Optional[str] = None) -> dict:
    return {"name": name, "level": "05", "pic": pic, "usage": usage, "class": cls, "offset": offset,
            "bytes": size, "occurs": None}  # fmt: skip


def _forge(fields: list[dict], *, org: str = "INDEXED", key: Optional[tuple] = (0, 8), config=None,
           access: str = "SEQUENTIAL") -> RepositoryForge:  # fmt: skip
    width = sum(f["bytes"] for f in fields)
    layout = {"bytes": width, "fields": fields}
    raw = {"name": "CUSTF", "dataset": "APP.CUST.KSDS", "organization": org, "record_max": width,
           "key_offset": key[0] if key else None, "key_length": key[1] if key else None,
           "alternate_indexes": [], "cics_files": [],
           "users": [{"program": "cbl/CUSTBAT.cbl", "kind": "batch", "name": "CUST-FILE", "modes": ["INPUT"],
                      "access_mode": access, "records": [{"record": "CUST-REC", "file": "cpy/CUSTREC.cpy",
                                                          "layout": layout}]}]}  # fmt: skip
    estate = {"sections": {"vsam_stores": {"facts": [raw]}}}
    skeletons = {"CUSTBAT": {"program": {"file": "cbl/CUSTBAT.cbl"}}}
    return RepositoryForge(estate, skeletons, PKG, target_from_dict(config))


def _read_all(forge: RepositoryForge) -> str:
    methods = "\n".join(forge.service_extras("CUSTBAT")["methods"])
    body = methods.split("public List<CustRec> readAllCustFile() {", 1)[1]
    return body.split(";", 1)[0].strip()


TEXT_KEY = [_fld("CUST-KEY", "X(8)", 0, 8, "X"), _fld("CUST-NAME", "X(12)", 8, 12, "X")]
NUMERIC_KEY = [_fld("CUST-ID", "9(8)", 0, 8, "9"), _fld("CUST-NAME", "X(12)", 8, 12, "X")]


def test_a_ksds_text_key_reads_in_its_code_page_order():
    """#3945: under key_collation ebcdic (the default) the sort column -- the key's code-page bytes (#3822)."""
    forge = _forge(TEXT_KEY)
    assert _read_all(forge) == 'return custRecRepository.findAll(org.springframework.data.domain.Sort.by("custKeySort"))'
    assert "private String custKeySort;" in forge.entity_source(forge.stores[0])


@pytest.mark.parametrize("collation", ["binary", "database"])
def test_a_ksds_text_key_without_a_sort_column_reads_by_the_key(collation):
    forge = _forge(TEXT_KEY, config={"culture": {"key_collation": collation}})
    assert _read_all(forge).endswith('Sort.by("custKey"))')
    assert "custKeySort" not in forge.entity_source(forge.stores[0])


def test_a_numeric_key_reads_by_the_key_itself():
    assert _read_all(_forge(NUMERIC_KEY)).endswith('Sort.by("custId"))')


def test_a_group_key_reads_by_its_parts_in_order():
    fields = [_fld("CUST-TYPE", "X(2)", 0, 2, "X"), _fld("CUST-NO", "9(6)", 2, 6, "9"),
              _fld("CUST-NAME", "X(12)", 8, 12, "X")]  # fmt: skip
    forge = _forge(fields)
    assert _read_all(forge).endswith('Sort.by("id.custType", "id.custNo"))')
    methods = "\n".join(forge.service_extras("CUSTBAT")["methods"])
    assert "TODO: its text parts order by the database's collation, not the code page's bytes" in methods


@pytest.mark.parametrize("org, why", [("NUMBERED", "relative record number order"), ("NONINDEXED", "entry (RBA)")])
def test_an_rrds_and_an_esds_read_in_their_own_order(org, why):
    forge = _forge(TEXT_KEY, org=org, key=None)
    assert _read_all(forge).endswith('Sort.by("id"))')
    assert why in "\n".join(forge.service_extras("CUSTBAT")["methods"])


def test_no_generated_sequential_read_is_a_bare_find_all():
    for forge in (_forge(TEXT_KEY), _forge(NUMERIC_KEY), _forge(TEXT_KEY, org="NUMBERED", key=None)):
        assert "findAll()" not in "\n".join(forge.service_extras("CUSTBAT")["methods"])
    # a random-access file reads by key, one record at a time
    methods = "\n".join(_forge(TEXT_KEY, access="RANDOM").service_extras("CUSTBAT")["methods"])
    assert "findById(key)" in methods and "readAll" not in methods


# ---- #3950: precision and scale ---------------------------------------------------------------------------
def _column(entity: str, field: str) -> str:
    before = entity.split(f" {field};", 1)[0]
    return before.rsplit("@Column(", 1)[1].split(")\n", 1)[0]


def test_a_vsam_bigdecimal_column_carries_its_pictures_precision_and_scale():
    fields = [_fld("CUST-ID", "9(8)", 0, 8, "9"), _fld("CUST-RATE", "S9(5)V9(4)", 8, 9, "9"),
              _fld("CUST-BAL", "S9(7)V99", 17, 5, "P", "COMP-3"), _fld("CUST-BIG", "S9(20)", 22, 20, "9"),
              _fld("CUST-SCALED", "SVPP9(3)", 42, 3, "9"),
              _fld("CUST-SHOWN", "$$$,$$9.99", 45, 10, "9"), _fld("CUST-COUNT", "9(4)", 55, 4, "9")]  # fmt: skip
    forge = _forge(fields)
    entity = forge.entity_source(forge.stores[0])
    assert _column(entity, "custRate") == 'name = "CUST_RATE", precision = 9, scale = 4'
    assert _column(entity, "custBal") == 'name = "CUST_BAL", precision = 9, scale = 2'  # COMP-3
    assert _column(entity, "custBig") == 'name = "CUST_BIG", precision = 20, scale = 0'  # no default scale 2
    assert _column(entity, "custScaled") == 'name = "CUST_SCALED", precision = 5, scale = 5'  # .00nnn
    # a currency-edited PICTURE is its display text: a String column of its width, no precision
    assert _column(entity, "custShown") == 'name = "CUST_SHOWN", length = 10'
    assert "private String custShown;" in entity
    assert _column(entity, "custCount") == 'name = "CUST_COUNT"'  # an Integer needs none
    assert "@Column(name = \"CUST_ID\")" in entity  # the key keeps its attributes
    # the same precision the schema forge (and the Spring entity) computes from the PICTURE
    assert parse_pic_precision("S9(5)V9(4)", False) == (9, 4)


def test_a_group_key_class_column_carries_precision_and_scale():
    fields = [_fld("CUST-TYPE", "X(2)", 0, 2, "X"), _fld("CUST-AMT", "9(4)V99", 2, 6, "9"),
              _fld("CUST-NAME", "X(12)", 8, 12, "X")]  # fmt: skip
    forge = _forge(fields)
    key = forge.key_source(forge.stores[0])
    assert '@Column(name = "CUST_AMT", precision = 6, scale = 2)' in key
    assert '@Column(name = "CUST_TYPE", columnDefinition = "varchar(2) COLLATE \\"C\\"")' in key  # as before


def test_a_currency_edited_spring_entity_field_keeps_3910s_precision():
    """The clean-room entity (the Spring forge) already sized edited fields by #3910's currency-aware precision;
    the VSAM entity reads the same PICTUREs through the same function."""
    schema = {"title": "PAY-REC", "currency_symbols": ["U"],
              "properties": {"PAY_AMT": {"type": "number", "description": "Legacy PIC: UUU,UU9.99"}}}  # fmt: skip
    assert '@Column(name = "PAY_AMT", precision = 7, scale = 2)' in generate_java_entity(schema, PKG)


@pytest.mark.skipif(jdk() is None or _maven_jar("com.h2database", "h2") is None, reason="no JDK or H2 jar")
def test_four_decimals_survive_a_round_trip_through_the_generated_column(tmp_path):
    """The generated @Column as Hibernate's DDL renders it (the Cultural Gauntlet's entity_ddl: precision and
    scale verbatim, numeric(38, 2) without them) in a real H2: 12345.6789 comes back whole."""
    forge = _forge([_fld("CUST-KEY", "X(8)", 0, 8, "X"), _fld("CUST-RATE", "S9(5)V9(4)", 8, 9, "9")],
                   config={"database": {"engine": "h2"}})
    table, ddl = entity_ddl(forge.entity_source(forge.stores[0]))
    assert "CUST_RATE numeric(9, 4)" in ddl
    ddl_java = ddl.replace('"', '\\"')  # escaped for a Java string literal (no backslash in an f-string on 3.9)
    got = _run(tmp_path, {}, "Trip", f"""
import java.sql.*;
public class Trip {{
    public static void main(String[] a) throws Exception {{
        try (Connection c = DriverManager.getConnection("jdbc:h2:mem:t", "sa", "")) {{
            c.createStatement().execute("{ddl_java}");
            c.createStatement().execute("INSERT INTO {table} (CUST_KEY, CUST_KEY_SORT, CUST_RATE) "
                    + "VALUES ('K', 'D2', 12345.6789)");
            ResultSet r = c.createStatement().executeQuery("SELECT CUST_RATE FROM {table}");
            r.next();
            System.out.println(r.getBigDecimal(1).toPlainString());
        }}
    }}
}}
""", classpath=_maven_jar("com.h2database", "h2") or "")
    assert got == ["12345.6789"]


# ---- the JDK -------------------------------------------------------------------------------------------------
_SLF4J = {
    "org/slf4j/Logger.java": "package org.slf4j;\npublic interface Logger { void error(String m, Throwable t); }\n",
    "org/slf4j/LoggerFactory.java": "package org.slf4j;\npublic final class LoggerFactory {\n"
    "    public static Logger getLogger(Class<?> c) { return (m, t) -> { }; }\n}\n",
}


def _run(root: Path, sources: dict, main: str, driver: str, classpath: str = "") -> list[str]:
    """javac `sources` ({path: text}) and the driver, run it; its stdout lines."""
    javac, java = jdk()  # type: ignore[misc]
    files = {**sources, f"{main}.java": driver}
    for rel, text in files.items():
        (root / "src" / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / "src" / rel).write_text(text, encoding="utf-8")
    cp = os.pathsep.join([str(root / "classes")] + ([classpath] if classpath else []))
    built = subprocess.run([javac, "-encoding", "UTF-8", "-cp", cp, "-d", str(root / "classes"),  # noqa: S603
                            *(str(root / "src" / f) for f in files)], capture_output=True, text=True, check=False)  # fmt: skip
    assert built.returncode == 0, built.stderr
    ran = subprocess.run([java, "-Dfile.encoding=UTF-8", "-cp", cp, main],  # noqa: S603
                         capture_output=True, text=True, encoding="utf-8", check=False)  # fmt: skip
    assert ran.returncode == 0, ran.stderr
    return ran.stdout.splitlines()


_ATTEMPT = """
    static String attempt(java.util.concurrent.Callable<Object> f) {
        try {
            return String.valueOf(f.call());
        } catch (Exception e) {
            return e.getClass().getSimpleName() + ": " + e.getMessage();
        }
    }
"""


# ---- #3946 ---------------------------------------------------------------------------------------------------
TIMESTAMPS = [
    ("2026-09-26-14.30.05.123456", "2026-09-26T14:30:05.123456"),
    ("2026-09-26-14.30.05", "2026-09-26T14:30:05"),
    ("2026-09-26-9.30.05.5", "2026-09-26T09:30:05.500"),  # DB2 lets the hour's leading zero go
    ("2026-09-26-14.30.05.123456789012", "2026-09-26T14:30:05.123456789"),  # 12 fraction digits, nanos kept
    ("2026-09-26-١٤.٣٠.05.000000", "invalid"),  # Arabic-Indic hour and minute (#3946)
    ("2026-09-26-14.30.０５", "invalid"),  # full-width seconds
    ("2026-09-26-14.30.05.12٣", "invalid"),  # an Arabic-Indic fraction digit
    ("2026-09-26-14.30.05.1234567890123", "invalid"),  # 13 fraction digits
    ("2026-09-26-+1.30.05", "invalid"),  # a sign parseInt would take
    ("2026-09-26-25.30.05", "invalid"),  # out of range (-181)
    ("2026-09-26-14.3.05", "invalid"),
    ("2026-09-26", "invalid"),  # no time at all
    ("٢٠٢٦-09-26-14.30.05", "invalid"),  # the date part: parseDate's own rejection
]


@pytest.mark.skipif(jdk() is None, reason="no JDK (javac + java)")
def test_parse_timestamp_takes_ascii_digits_only(tmp_path):
    src = {"com/test/repository/db2/Db2Dates.java": db2_dates_source(PKG, "iso")}
    calls = "\n".join(f'        System.out.println(attempt(() -> Db2Dates.parseTimestamp("{t}")));'
                      for t, _ in TIMESTAMPS)  # fmt: skip
    got = _run(tmp_path, src, "Ts", "import com.test.repository.db2.Db2Dates;\npublic class Ts {\n"
               f"    public static void main(String[] a) {{\n{calls}\n    }}\n{_ATTEMPT}}}\n")  # fmt: skip
    for (text, want), line in zip(TIMESTAMPS, got):
        if want == "invalid":
            # the way parseDate reports an invalid value: a DateTimeParseException (DB2's -180 / -181)
            assert line.startswith("DateTimeParseException: not a DB2 "), (text, line)
        else:
            assert line == want, text


# ---- #3949 ---------------------------------------------------------------------------------------------------
# (bytes, scale, want): valid packed data decodes; each kind of bad nibble is a data exception (S0C7)
PACKED = [
    ("12345C", 2, "123.45"),
    ("12345D", 2, "-123.45"),
    ("12345B", 0, "-12345"),
    ("12345F", 0, "12345"),  # unsigned
    ("00000A", 0, "0"),  # A / E are positive signs too
    ("1A345C", 2, "digit nibble A"),  # a bad low (digit) nibble
    ("F2345C", 2, "digit nibble F"),  # a bad high nibble
    ("123455", 2, "sign nibble 5"),  # a digit where the sign goes
    ("123450", 2, "sign nibble 0"),  # LOW-VALUES' sign
    ("C0000C", 0, "digit nibble C"),  # a shifted field
]


def _bytes(hexs: str) -> str:
    return "new byte[] {" + ", ".join(f"(byte) 0x{hexs[i:i + 2]}" for i in range(0, len(hexs), 2)) + "}"


@pytest.mark.skipif(jdk() is None, reason="no JDK (javac + java)")
def test_unpack_comp3_throws_on_invalid_packed_data(tmp_path):
    src = {"com/test/util/EbcdicDecoderUtil.java": generate_decoder_util(PKG), **_SLF4J}
    calls = "\n".join(f"        System.out.println(attempt(() -> EbcdicDecoderUtil.unpackComp3({_bytes(h)}, {s}, "
                      '"WS-AMT").toPlainString()));' for h, s, _ in PACKED)  # fmt: skip
    got = _run(tmp_path, src, "Pk", "import com.test.util.EbcdicDecoderUtil;\npublic class Pk {\n"
               f"    public static void main(String[] a) {{\n{calls}\n"
               "        System.out.println(attempt(() -> EbcdicDecoderUtil.unpackComp3(new byte[] {(byte) 0xA1}, 0)));\n"
               "        try {\n            EbcdicDecoderUtil.unpackComp3(new byte[] {(byte) 0xA1}, 0);\n"
               "        } catch (NumberFormatException e) {\n"  # still a NumberFormatException to old catches
               "            System.out.println(e instanceof EbcdicDecoderUtil.PackedDecimalDataException);\n"
               f"        }}\n    }}\n{_ATTEMPT}}}\n")  # fmt: skip
    for (h, _, want), line in zip(PACKED, got):
        if "nibble" in want:
            assert line.startswith("PackedDecimalDataException: invalid packed decimal (S0C7 data exception) in "
                                   f"WS-AMT: {want} at byte "), (h, line)  # fmt: skip
        else:
            assert line == want, h
    # without a field name: still named by its byte
    assert got[len(PACKED)] == ("PackedDecimalDataException: invalid packed decimal (S0C7 data exception): "
                                "digit nibble A at byte 0 of 1")  # fmt: skip
    assert got[-1] == "true"


@pytest.mark.skipif(jdk() is None, reason="no JDK (javac + java)")
def test_the_entity_codec_rejects_invalid_packed_data_too(tmp_path):
    """CobolRecords.packed, which the VSAM entities' fromRecord reads COMP-3 with, had the same flaw."""
    forge = _forge([_fld("CUST-KEY", "X(8)", 0, 8, "X"), _fld("CUST-BAL", "S9(3)V99", 8, 3, "P", "COMP-3")])
    src = {"com/test/entity/vsam/CobolRecords.java": forge.records_source()}
    calls = "\n".join(f"        System.out.println(attempt(() -> CobolRecords.packed({_bytes(h)}, 0, 3, {s})"
                      ".toPlainString()));" for h, s, _ in PACKED)  # fmt: skip
    got = _run(tmp_path, src, "Cr", "import com.test.entity.vsam.CobolRecords;\npublic class Cr {\n"
               f"    public static void main(String[] a) {{\n{calls}\n    }}\n{_ATTEMPT}}}\n")  # fmt: skip
    for (h, _, want), line in zip(PACKED, got):
        if "nibble" in want:
            kind = "a digit nibble above 9" if "digit" in want else "a sign nibble below A"
            assert line.startswith("NumberFormatException: invalid packed decimal (S0C7): byte X'"), (h, line)
            assert line.endswith(kind), (h, line)
        else:
            assert line == want, h
