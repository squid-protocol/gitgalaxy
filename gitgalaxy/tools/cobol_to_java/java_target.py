# ==============================================================================
# GitGalaxy Tool: COBOL -> Java target configuration (#3613)
#
# PURPOSE:
# What kind of Java the generator writes: the project coordinates, the Java and
# Spring Boot versions, the build tool, how data classes are written (Lombok,
# plain classes, records), the database, and which parts to generate. A YAML (or
# JSON) file overrides the defaults section by section:
#
#     cobol-to-java <staging dir> --config modernize.yaml
#     cobol-to-java --init-config modernize.yaml     # an annotated starting file
#
# The defaults reproduce the generator's historic output byte for byte, so a run
# without --config is unchanged. Every key is validated: an unknown key or an
# unsupported value is an error naming it, never silently ignored.
# ==============================================================================
from __future__ import annotations

import codecs
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gitgalaxy.core.ebcdic_codecs import register
from gitgalaxy.standards.yaml_reader import YamlError, load_yaml

# Supported values. Each combination is compile-checked (see tests/tools/java_target_matrix.py).
JAVA_VERSIONS = (17, 21)
BUILD_TOOLS = ("maven", "gradle")
DATA_CLASSES = ("lombok", "plain")  # entities and DTOs: Lombok @Data, or explicit accessors
DTO_STYLES = ("class", "record")  # a transient record (DFHCOMMAREA): a class, or a Java record
DATABASES = ("postgresql", "db2", "oracle", "mysql", "h2")
DDL_AUTO = ("none", "validate", "update", "create", "create-drop")
UI_FLAVOURS = ("none", "thymeleaf", "openapi-only")  # #3619: what the BMS screens become beyond view models
MESSAGING = ("in-memory", "jms", "kafka")  # #3620: the adapter behind the TD / MQ message port
REMOTE_CALLS = ("http", "local")  # a DPL LINK to another region: an HTTP client, or the in-process bean
# #3987: the order right-to-left text (Arabic, Hebrew) is stored in: logical (reading order), or visual as a
# 3270 showed it -- visual_ltr with the record's first byte at the screen's left (IBM's host default),
# visual_rtl at its right (a screen-reverse terminal). auto = visual_ltr on VISUAL_BIDI_PAGES, else logical.
BIDI_LAYOUTS = ("auto", "logical", "visual_ltr", "visual_rtl")
# The JDK names of the pages whose data is visual by IBM's convention (CDRA): a 3270 had no BiDi engine, so
# the host stored the characters left to right as the screen showed them. EBCDIC Arabic / Hebrew, PC Arabic /
# Hebrew. The Windows and ISO pages (1255 / 1256, 8859-6 / -8) are logical by default.
VISUAL_BIDI_PAGES = ("IBM420", "IBM424", "IBM864", "IBM862")
# #3819: the culture section. The first value of each is COBOL's own behaviour (the default);
# anything else is a business choice the run declares as a deviation.
ROUNDING = ("cobol", "half_even")  # ROUNDED: half away from zero (ROUNDED MODE honoured) | banker's
OVERFLOW = ("cobol", "error")  # a result too long for its PICTURE: high-order digits lost | an exception
DECIMAL_POINTS = ("auto", "period", "comma")  # auto = SPECIAL-NAMES DECIMAL-POINT IS COMMA, else period
KEY_COLLATIONS = ("ebcdic", "binary", "database")  # key order: the code page's bytes | UTF-8 bytes | the DB's
DB2_DATE_FORMATS = ("iso", "eur", "usa", "jis", "local")  # the DB2 subsystem's DATE/TIME character format

# Per database: (Maven groupId, artifactId) of the JDBC driver -- versions come from the
# Spring Boot BOM -- the driver class, the Hibernate dialect, and a JDBC URL template.
DATABASE_DRIVERS = {
    "postgresql": ("org.postgresql", "postgresql", "org.postgresql.Driver",
                   "org.hibernate.dialect.PostgreSQLDialect", "jdbc:postgresql://localhost:5432/{db}"),
    "db2": ("com.ibm.db2", "jcc", "com.ibm.db2.jcc.DB2Driver",
            "org.hibernate.dialect.DB2Dialect", "jdbc:db2://localhost:50000/{db}"),
    "oracle": ("com.oracle.database.jdbc", "ojdbc11", "oracle.jdbc.OracleDriver",
               "org.hibernate.dialect.OracleDialect", "jdbc:oracle:thin:@localhost:1521/{db}"),
    "mysql": ("com.mysql", "mysql-connector-j", "com.mysql.cj.jdbc.Driver",
              "org.hibernate.dialect.MySQLDialect", "jdbc:mysql://localhost:3306/{db}"),
    "h2": ("com.h2database", "h2", "org.h2.Driver", "org.hibernate.dialect.H2Dialect", "jdbc:h2:mem:{db}"),
}  # fmt: skip


def record_charset_java(name: str) -> str:
    """#4060: the JDK name of data.record_charset (latin-1 -> ISO-8859-1, cp037 -> IBM037, utf-8 -> UTF-8);
    an unknown charset is a config error."""
    from gitgalaxy.core.ebcdic_codecs import java_charset_name

    try:
        return java_charset_name(name)
    except LookupError as e:
        raise ConfigError(f"data.record_charset {name!r}: not a known code page") from e


def visual_bidi(data: dict[str, Any] | None) -> bool:
    """#3987: whether the record bytes keep right-to-left text in visual order -- data.bidi_layout visual_ltr /
    visual_rtl, or auto with a record charset that is visual by convention (VISUAL_BIDI_PAGES). CobolRecords decides the same
    way at run time, per Charset."""
    d = data or {}
    layout = str(d.get("bidi_layout") or "auto")
    if layout != "auto":
        return layout.startswith("visual")
    try:
        return record_charset_java(str(d.get("record_charset") or "latin-1")) in VISUAL_BIDI_PAGES
    except ConfigError:
        return False


def zoned_sign_characters(code_page: str = "cp037") -> tuple[str, str]:
    """#3826: the zoned-decimal sign overpunch characters of an EBCDIC or ASCII code page.
    Under EBCDIC, these are bytes 0xC0-0xC9 (positive 0-9) and 0xD0-0xD9 (negative 0-9).
    cp037 gives the US `{ABCDEFGHI` / `}JKLMNOPQR`; a national code page gives its own
    zero signs (cp273: `ä...` / `ü...`). Under ASCII (e.g. shift_jis, cp1252), these
    are the standard PC-COBOL overpunches `{ABCDEFGHI` and `}JKLMNOPQR`."""
    cp = code_page.lower()
    register()  # #3816: cp277 / cp278 / cp280 / cp284 / cp285 / cp297 / cp1047, beside Python's own
    try:
        codecs.lookup(cp)
    except LookupError as e:
        raise ConfigError(f"data.code_page {code_page!r}: not a known EBCDIC or ASCII code page") from e
    try:
        if bytes([0xF0]).decode(cp) == "0":
            return bytes(range(0xC0, 0xCA)).decode(cp), bytes(range(0xD0, 0xDA)).decode(cp)
    except UnicodeDecodeError:
        pass  # Expected for non-EBCDIC encodings during probing; fall through to ASCII probe.
    try:
        if bytes([0x30]).decode(cp) == "0":
            return "{ABCDEFGHI", "}JKLMNOPQR"
    except UnicodeDecodeError:
        pass  # Expected for non-ASCII-compatible encodings during probing; report unsupported below.
    raise ConfigError(f"data.code_page {code_page!r}: not a known EBCDIC or ASCII code page")


_PACKAGE = re.compile(r"[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)*")
_LOCALE_TAG = re.compile(r"ROOT|[a-z]{2,3}(?:-[A-Z][a-z]{3})?(?:-(?:[A-Z]{2}|[0-9]{3}))?")  # BCP-47: de-DE, zh-Hant-TW
_ZONE_ID = re.compile(r"UTC|[A-Za-z_]{1,30}(?:/[A-Za-z0-9_+-]{1,30}){1,2}")  # an IANA id's shape
_BOOT_VERSION = re.compile(r"3\.\d+\.\d+")
_ARTIFACT = re.compile(r"[a-z0-9][a-z0-9._-]*")


class ConfigError(ValueError):
    """An invalid target configuration; the message names the offending key."""


@dataclass
class Project:
    package: str = "com.gitgalaxy.modernized"
    group_id: str | None = None  # default: the package
    artifact_id: str | None = None  # default: derived from the staging directory's name
    version: str = "1.0.0-SNAPSHOT"
    description: str = "GitGalaxy Auto-Generated Microservice"
    header_file: str | None = None  # a licence / compliance header for every .java file


@dataclass
class Java:
    version: int = 17
    build_tool: str = "maven"
    data_classes: str = "lombok"
    dto_style: str = "class"


@dataclass
class SpringBoot:
    version: str = "3.2.4"


@dataclass
class Database:
    engine: str = "postgresql"
    ddl_auto: str = "update"
    username: str = "postgres"
    show_sql: bool = True


@dataclass
class Features:
    rest_controllers: bool = True  # a REST controller per program
    services: bool = True  # a @Service skeleton per program
    batch: bool = True  # Spring Batch on the classpath (JCL job flow -> jobs is #3622)
    ebcdic_decoder: bool = True  # the EBCDIC / COMP-3 decoder utility
    mock_services: bool = True  # mock services for unresolved external calls
    agent_tickets: bool = True  # bounded AI-agent tickets for the business logic


@dataclass
class Integration:
    remote_calls: str = "http"  # #3616: a LINK the CSD routes to another region (REMOTESYSTEM / SYSID)
    messaging: str = "in-memory"  # #3620: TD intrapartition + MQ queues -> in-process | JMS (Artemis) | Kafka


@dataclass
class Ui:
    flavour: str = "none"  # #3619: view models only | + Thymeleaf pages | + REST endpoints with OpenAPI docs


@dataclass
class Data:
    code_page: str = "cp037"
    dbcs_code_page: str | None = None
    # #4060: the code page the migrated system's record bytes are in -- the datasets, files and COMMAREAs the
    # ported Java reads and writes. A deployment fact, never a port's guess: CobolRecords.charset() returns it.
    # ISO-8859-1 (latin-1) is what an ASCII transfer of a single-byte estate gives, and what ran before.
    record_charset: str = "latin-1"
    # #3987: the order the record bytes keep right-to-left text in (BIDI_LAYOUTS). Visual: as a 3270 showed it;
    # CobolRecords turns it into logical (reading-order) Unicode and back.
    bidi_layout: str = "auto"


@dataclass
class Culture:
    """#3819: the program's cultural and regional assumptions. Every default reproduces what the COBOL
    program does on its mainframe; a non-default is a business decision, listed by JavaTarget.deviations()
    in the migration audit. This section declares; the behaviour behind each option lands in its issue."""

    rounding: str = "cobol"  # TODO(#3825): ROUNDED / ROUNDED MODE in generated arithmetic and porting rules
    overflow: str = "cobol"  # TODO(#3825): high-order truncation vs ON SIZE ERROR
    zone: str = "UTC"  # #3824: MainframeClock's zone and CURRENT-DATE's UTC offset
    format_locale: str = "ROOT"  # generated formatting / case mapping (#3823 made it Locale.ROOT)
    display_locale: str = "ROOT"  # TODO(#3819): screens only -- never used for stored data
    decimal_point: str = "auto"  # #3827: DECIMAL-POINT IS COMMA in edited PICTUREs and schemas
    currency: str = "auto"  # TODO(#3820): CURRENCY SIGN / PICTURE SYMBOL in edited PICTUREs
    key_collation: str = "ebcdic"  # #3822: key order and comparison of generated repositories
    db2_date_format: str = "iso"  # #3828: the DB2 subsystem's DATE/TIME format for character dates (Db2Dates)


@dataclass
class JavaTarget:
    project: Project = field(default_factory=Project)
    java: Java = field(default_factory=Java)
    spring_boot: SpringBoot = field(default_factory=SpringBoot)
    database: Database = field(default_factory=Database)
    features: Features = field(default_factory=Features)
    integration: Integration = field(default_factory=Integration)
    ui: Ui = field(default_factory=Ui)
    data: Data = field(default_factory=Data)
    culture: Culture = field(default_factory=Culture)

    @property
    def lombok(self) -> bool:
        return self.java.data_classes == "lombok"

    def group_id(self) -> str:
        return self.project.group_id or self.project.package

    def driver(self) -> tuple[str, str, str, str, str]:
        return DATABASE_DRIVERS[self.database.engine]

    def deviations(self) -> list[str]:
        """#3819: every culture choice that departs from the COBOL program's own behaviour, in words."""
        c, out = self.culture, []
        if c.rounding == "half_even":
            out.append(
                "culture.rounding: half_even -- ROUNDED uses banker's rounding (COBOL rounds half away from zero)"
            )
        if c.overflow == "error":
            out.append("culture.overflow: error -- a result too long for its PICTURE throws (COBOL keeps the "
                       "low-order digits unless ON SIZE ERROR)")  # fmt: skip
        if c.format_locale != "ROOT":
            out.append(f"culture.format_locale: {c.format_locale} -- generated formatting and case mapping follow "
                       "a locale (COBOL's are fixed; digits and case can change)")  # fmt: skip
        if c.key_collation != "ebcdic":
            out.append(f"culture.key_collation: {c.key_collation} -- keys order by "
                       f"{'UTF-8 bytes' if c.key_collation == 'binary' else 'the database default collation'}, "
                       f"not {self.data.code_page} byte order (browses and sorts can differ)")  # fmt: skip
        return out


_SECTIONS = {
    "project": Project,
    "java": Java,
    "spring_boot": SpringBoot,
    "database": Database,
    "features": Features,
    "integration": Integration,
    "ui": Ui,
    "data": Data,
    "culture": Culture,
}


def _check(target: JavaTarget) -> None:
    p, j, s, d = target.project, target.java, target.spring_boot, target.database
    if not _PACKAGE.fullmatch(p.package):
        raise ConfigError(f"project.package {p.package!r} is not a lower-case Java package name")
    if p.group_id is not None and not _PACKAGE.fullmatch(p.group_id):
        raise ConfigError(f"project.group_id {p.group_id!r} is not a valid Maven groupId")
    if p.artifact_id is not None and not _ARTIFACT.fullmatch(p.artifact_id):
        raise ConfigError(f"project.artifact_id {p.artifact_id!r} must be lower case: letters, digits, . _ -")
    for key, value, allowed in (
        ("java.version", j.version, JAVA_VERSIONS),
        ("java.build_tool", j.build_tool, BUILD_TOOLS),
        ("java.data_classes", j.data_classes, DATA_CLASSES),
        ("java.dto_style", j.dto_style, DTO_STYLES),
        ("database.engine", d.engine, DATABASES),
        ("database.ddl_auto", d.ddl_auto, DDL_AUTO),
        ("integration.remote_calls", target.integration.remote_calls, REMOTE_CALLS),
        ("integration.messaging", target.integration.messaging, MESSAGING),
        ("ui.flavour", target.ui.flavour, UI_FLAVOURS),
    ):
        if value not in allowed:
            raise ConfigError(f"{key} {value!r} is not supported; choose one of {', '.join(map(str, allowed))}")
    if target.features.rest_controllers and not target.features.services:
        raise ConfigError(
            "features.rest_controllers needs features.services: each controller calls its program's service"
        )
    if target.ui.flavour != "none" and not (target.features.services and target.features.rest_controllers):
        raise ConfigError(
            f"ui.flavour {target.ui.flavour!r} needs features.services and features.rest_controllers: "
            "each screen's controller calls its program's service"
        )
    if not _BOOT_VERSION.fullmatch(str(s.version)):
        raise ConfigError(f"spring_boot.version {s.version!r}: a Spring Boot 3.x.y version (jakarta namespace)")
    zoned_sign_characters(target.data.code_page)  # #3826: an unknown code page fails at load, not mid-generation
    record_charset_java(target.data.record_charset)  # #4060: likewise an unknown record charset
    if target.data.bidi_layout not in BIDI_LAYOUTS:
        raise ConfigError(f"data.bidi_layout {target.data.bidi_layout!r} is not supported; "
                          f"choose one of {', '.join(BIDI_LAYOUTS)}")  # fmt: skip
    _check_culture(target.culture)


def _known_zone(zone: str) -> bool:
    """An IANA time zone the system knows -- by shape alone where Python has no tz database (zero-dep)."""
    if zone == "UTC":
        return True
    try:
        import zoneinfo  # Python 3.9+
    except ImportError:
        return bool(_ZONE_ID.fullmatch(zone))
    if not zoneinfo.available_timezones():
        return bool(_ZONE_ID.fullmatch(zone))
    try:
        zoneinfo.ZoneInfo(zone)
        return True
    except (KeyError, ValueError, OSError):  # ZoneInfoNotFoundError is a KeyError; a malformed key a ValueError
        return False


def _check_culture(c: Culture) -> None:
    for key, value, allowed in (
        ("culture.rounding", c.rounding, ROUNDING),
        ("culture.overflow", c.overflow, OVERFLOW),
        ("culture.decimal_point", c.decimal_point, DECIMAL_POINTS),
        ("culture.key_collation", c.key_collation, KEY_COLLATIONS),
        ("culture.db2_date_format", c.db2_date_format, DB2_DATE_FORMATS),
    ):
        if value not in allowed:
            raise ConfigError(f"{key} {value!r} is not supported; choose one of {', '.join(allowed)}")
    if not isinstance(c.zone, str) or not _known_zone(c.zone):
        raise ConfigError(f"culture.zone {c.zone!r}: an IANA time zone id such as UTC, Europe/Oslo, Asia/Kolkata")
    for key, value in (("culture.format_locale", c.format_locale), ("culture.display_locale", c.display_locale)):
        if not isinstance(value, str) or not _LOCALE_TAG.fullmatch(value):
            raise ConfigError(f"{key} {value!r}: ROOT or a BCP-47 language tag such as de-DE, hi-IN, zh-Hant-TW")
    if not isinstance(c.currency, str) or not c.currency or len(c.currency) > 8 or "\n" in c.currency:
        raise ConfigError(f"culture.currency {c.currency!r}: auto, or the symbol / string itself (1-8 characters)")


def target_from_dict(data: dict[str, Any] | None) -> JavaTarget:
    """A JavaTarget from a parsed config: every section optional, every key checked."""
    target = JavaTarget()
    for section, values in (data or {}).items():
        if section not in _SECTIONS:
            raise ConfigError(f"unknown section {section!r}; sections are {', '.join(_SECTIONS)}")
        if not isinstance(values, dict):
            raise ConfigError(f"section {section!r} must be a mapping")
        obj = getattr(target, section)
        for key, value in values.items():
            if section == "database" and key == "password":
                raise ConfigError(
                    "database.password: credentials do not belong in the config (it is stored with the "
                    "project); the generated application.yml carries a placeholder -- set "
                    "SPRING_DATASOURCE_PASSWORD at runtime"
                )
            if not hasattr(obj, key):
                known = ", ".join(obj.__dataclass_fields__)
                raise ConfigError(f"unknown key {section}.{key}; {section} keys are {known}")
            default = getattr(obj, key)
            if isinstance(default, bool) and not isinstance(value, bool):
                raise ConfigError(f"{section}.{key} must be true or false")
            setattr(obj, key, str(value) if section == "spring_boot" else value)
    _check(target)
    return target


def target_as_dict(target: JavaTarget) -> dict[str, dict[str, Any]]:
    """The target as plain config sections (the inverse of target_from_dict)."""
    return {name: dict(vars(getattr(target, name))) for name in _SECTIONS}


def load_target(path: Path | None) -> JavaTarget:
    """The target a YAML / JSON config file describes, or the defaults when `path` is None."""
    if path is None:
        return JavaTarget()
    text = Path(path).read_text(encoding="utf-8")
    if Path(path).suffix.lower() == ".json":
        data = json.loads(text)
    else:
        try:
            data = load_yaml(text)  # GitGalaxy's own reader: no PyYAML needed
        except YamlError as e:
            raise ConfigError(f"{path}: {e}") from e
    if data is not None and not isinstance(data, dict):
        raise ConfigError(f"{path}: the config must be a mapping of sections")
    return target_from_dict(data)


DEFAULT_CONFIG = f"""\
# GitGalaxy COBOL -> Java target configuration (#3613).
# Every key is optional; omitted keys keep the default shown. Unknown keys are errors.

project:
  package: com.gitgalaxy.modernized     # base Java package
  group_id: null                        # Maven / Gradle group; null = the package
  artifact_id: null                     # null = derived from the staging directory's name
  version: 1.0.0-SNAPSHOT
  description: GitGalaxy Auto-Generated Microservice
  header_file: null                     # a licence / compliance header prepended to every .java file

java:
  version: 17                           # {" | ".join(map(str, JAVA_VERSIONS))}
  build_tool: maven                     # {" | ".join(BUILD_TOOLS)}
  data_classes: lombok                  # {" | ".join(DATA_CLASSES)}  (plain = explicit getters / setters / constructors)
  dto_style: class                      # {" | ".join(DTO_STYLES)}  (a transient record such as a DFHCOMMAREA)

spring_boot:
  version: 3.2.4                        # a Spring Boot 3.x.y release

database:
  engine: postgresql                    # {" | ".join(DATABASES)}
  ddl_auto: update                      # {" | ".join(DDL_AUTO)}
  username: postgres
  show_sql: true
  # No password here: set SPRING_DATASOURCE_PASSWORD at runtime (a config is stored with the project).

features:
  rest_controllers: true                # a REST controller per program
  services: true                        # a @Service skeleton per program
  batch: true                           # Spring Batch on the classpath
  ebcdic_decoder: true                  # the EBCDIC / COMP-3 decoder utility
  mock_services: true                   # mock services for unresolved external calls
  agent_tickets: true                   # bounded AI-agent tickets for the business logic

integration:
  remote_calls: http                    # {" | ".join(REMOTE_CALLS)}  (a LINK the CSD routes to another region:
                                        #   http = a RestTemplate client per region, local = call the bean in-process)
  messaging: in-memory                  # {" | ".join(MESSAGING)}  (TD intrapartition + MQ queues: an in-process
                                        #   queue, JMS through Spring's Artemis starter, or Kafka topics)

ui:
  flavour: none                         # {" | ".join(UI_FLAVOURS)}  (BMS screens: view models only,
                                        #   + Thymeleaf pages on the 24x80 layout, or + REST endpoints and OpenAPI docs)

data:
  code_page: cp037                      # the EBCDIC code page for zoned-decimal sign overpunch
  record_charset: latin-1               # the code page the migrated record bytes are in (datasets, files,
                                        #   COMMAREAs): latin-1 after an ASCII transfer, cp037 if kept EBCDIC
  bidi_layout: auto                     # {" | ".join(BIDI_LAYOUTS)}  (Arabic / Hebrew text in the records:
                                        #   visual = as the 3270 showed it, the first byte at the screen's left
                                        #   (ltr) or right (rtl, screen reverse), turned into logical Unicode
                                        #   and back; auto = visual_ltr under cp420 / cp424 / cp864 / cp862)

# Cultural and regional assumptions (#3819). Every default is what the COBOL program does on its
# mainframe; anything else is a business choice, listed under "Declared cultural deviations" in
# java_migration_audit.txt and shown to every porting ticket.
culture:
  rounding: cobol                       # {" | ".join(ROUNDING)}  (cobol: ROUNDED is half away from zero, ROUNDED MODE
                                        #   honoured, unrounded results truncate; half_even: banker's rounding -- a deviation)
  overflow: cobol                       # {" | ".join(OVERFLOW)}  (cobol: a result too long for its PICTURE loses its
                                        #   high-order digits unless ON SIZE ERROR; error: throw instead -- a deviation)
  zone: UTC                             # the mainframe's time zone, an IANA id (e.g. Asia/Kolkata, Europe/Oslo):
                                        #   the pinned clock and CURRENT-DATE's UTC offset
  format_locale: ROOT                   # formatting / case mapping in generated code: ROOT keeps digits and case
                                        #   locale-proof; a BCP-47 tag here is a deviation
  display_locale: ROOT                  # screens only (presentation): ROOT or a BCP-47 tag such as de-DE; never stored data
  decimal_point: auto                   # {" | ".join(DECIMAL_POINTS)}  (auto: the program's SPECIAL-NAMES DECIMAL-POINT IS COMMA)
  currency: auto                        # auto (the program's CURRENCY SIGN), or the symbol itself, e.g. "£" or "EUR "
  key_collation: ebcdic                 # {" | ".join(KEY_COLLATIONS)}  (ebcdic: keys order as on the mainframe, the
                                        #   code page's byte order; binary / database: a deviation -- browses can differ)
  db2_date_format: iso                  # {" | ".join(DB2_DATE_FORMATS)}  (the DB2 subsystem's DATE/TIME format,
                                        #   DSNHDECP DATE= / TIME=: a DATE fetched into PIC X(10) reads 26.09.2026
                                        #   under eur; the generated Db2Dates converts in it)
"""  # noqa: S608 -- a YAML template: "update | create" are ddl-auto values, not SQL
