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

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gitgalaxy.standards.yaml_reader import YamlError, load_yaml

# Supported values. Each combination is compile-checked (see tests/tools/java_target_matrix.py).
JAVA_VERSIONS = (17, 21)
BUILD_TOOLS = ("maven", "gradle")
DATA_CLASSES = ("lombok", "plain")  # entities and DTOs: Lombok @Data, or explicit accessors
DTO_STYLES = ("class", "record")  # a transient record (DFHCOMMAREA): a class, or a Java record
DATABASES = ("postgresql", "db2", "oracle", "mysql", "h2")
DDL_AUTO = ("none", "validate", "update", "create", "create-drop")
REMOTE_CALLS = ("http", "local")  # a DPL LINK to another region: an HTTP client, or the in-process bean

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

_PACKAGE = re.compile(r"[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)*")
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


@dataclass
class JavaTarget:
    project: Project = field(default_factory=Project)
    java: Java = field(default_factory=Java)
    spring_boot: SpringBoot = field(default_factory=SpringBoot)
    database: Database = field(default_factory=Database)
    features: Features = field(default_factory=Features)
    integration: Integration = field(default_factory=Integration)

    @property
    def lombok(self) -> bool:
        return self.java.data_classes == "lombok"

    def group_id(self) -> str:
        return self.project.group_id or self.project.package

    def driver(self) -> tuple[str, str, str, str, str]:
        return DATABASE_DRIVERS[self.database.engine]


_SECTIONS = {
    "project": Project,
    "java": Java,
    "spring_boot": SpringBoot,
    "database": Database,
    "features": Features,
    "integration": Integration,
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
    ):
        if value not in allowed:
            raise ConfigError(f"{key} {value!r} is not supported; choose one of {', '.join(map(str, allowed))}")
    if target.features.rest_controllers and not target.features.services:
        raise ConfigError(
            "features.rest_controllers needs features.services: each controller calls its program's service"
        )
    if not _BOOT_VERSION.fullmatch(str(s.version)):
        raise ConfigError(f"spring_boot.version {s.version!r}: a Spring Boot 3.x.y version (jakarta namespace)")


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
"""  # noqa: S608 -- a YAML template: "update | create" are ddl-auto values, not SQL
