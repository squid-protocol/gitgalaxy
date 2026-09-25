"""COBOL -> Java target config (#3613): the defaults, validation, the CLI's precedence,
and what each option changes in the generated project. That every option combination
COMPILES is checked by tests/tools/java_target_matrix.py (a JDK + Maven / Gradle run)."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from gitgalaxy.standards.yaml_reader import load_yaml
from gitgalaxy.tools.cobol_to_java.cobol_to_java_build_forge import (
    generate_application_yml,
    generate_build_gradle,
    generate_pom_xml,
)
from gitgalaxy.tools.cobol_to_java.cobol_to_java_spring_forge import generate_java_dto, generate_java_entity
from gitgalaxy.tools.cobol_to_java.java_target import (
    DEFAULT_CONFIG,
    ConfigError,
    JavaTarget,
    load_target,
    target_from_dict,
)

SCHEMA = {
    "title": "DFHCOMMAREA",
    "properties": {
        "CA-ACCT-ID": {"type": "string", "description": "PIC X(11)"},
        "CA-BALANCE": {"type": "number", "description": "PIC S9(9)V99 COMP-3"},
    },
}


def test_the_annotated_default_file_is_the_defaults():
    assert target_from_dict(load_yaml(DEFAULT_CONFIG)) == JavaTarget()
    assert load_target(None) == JavaTarget()


@pytest.mark.parametrize(
    "config, message",
    [
        ({"jav": {}}, "unknown section 'jav'"),
        ({"java": {"versoin": 21}}, "unknown key java.versoin"),
        ({"java": {"version": 11}}, "java.version 11 is not supported"),
        ({"java": {"build_tool": "ant"}}, "java.build_tool"),
        ({"database": {"engine": "sybase"}}, "database.engine"),
        ({"spring_boot": {"version": "2.7.18"}}, "Spring Boot 3.x.y"),
        ({"project": {"package": "Com.Acme"}}, "project.package"),
        ({"features": {"batch": "yes"}}, "features.batch must be true or false"),
        ({"features": {"services": False}}, "rest_controllers needs features.services"),
        ({"database": {"password": "hunter2"}}, "credentials do not belong in the config"),
    ],
)
def test_invalid_configs_name_the_key(config, message):
    with pytest.raises(ConfigError, match=message):
        target_from_dict(config)


def test_a_yaml_file_is_read_without_pyyaml(tmp_path, monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "yaml", None)  # PyYAML unavailable
    cfg = tmp_path / "t.yaml"
    cfg.write_text("java:\n  version: 21\n  dto_style: record\ndatabase:\n  engine: db2\n", encoding="utf-8")
    t = load_target(cfg)
    assert (t.java.version, t.java.dto_style, t.database.engine, t.project.package) == (
        21,
        "record",
        "db2",
        "com.gitgalaxy.modernized",
    )


def test_the_build_follows_the_target():
    t = target_from_dict(
        {
            "java": {"version": 21, "data_classes": "plain"},
            "spring_boot": {"version": "3.3.5"},
            "database": {"engine": "db2"},
            "features": {"batch": False},
        }  # fmt: skip
    )
    pom = generate_pom_xml("com.acme", "app", t)
    assert "<version>3.3.5</version>" in pom and "<java.version>21</java.version>" in pom
    assert "<artifactId>jcc</artifactId>" in pom and "postgresql" not in pom
    assert "lombok" not in pom and "starter-batch" not in pom
    yml = generate_application_yml("app", t)
    assert "jdbc:db2://localhost:50000/app" in yml and "DB2Dialect" in yml and "batch:" not in yml
    gradle = generate_build_gradle("com.acme", t)
    assert "JavaLanguageVersion.of(21)" in gradle and "runtimeOnly 'com.ibm.db2:jcc'" in gradle
    assert "io.spring.dependency-management' version '1.1.6'" in gradle


def test_data_classes_and_dto_style():
    plain = target_from_dict({"java": {"data_classes": "plain"}})
    entity = generate_java_entity({**SCHEMA, "title": "ACCOUNT"}, "com.acme", target=plain)
    assert "lombok" not in entity and "public Long getSysId()" in entity
    assert "public void setCaBalance(BigDecimal caBalance)" in entity
    record = generate_java_dto(SCHEMA, "com.acme", target=target_from_dict({"java": {"dto_style": "record"}}))
    assert "public record DfhcommareaDto(" in record and "String caAcctId," in record
    assert "BigDecimal caBalance\n) {" in record and "lombok" not in record
    lombok_dto = generate_java_dto(SCHEMA, "com.acme")
    assert "@Data" in lombok_dto and "public class DfhcommareaDto" in lombok_dto


def _run(argv: list[str]) -> None:
    from gitgalaxy import cobol_to_java_controller

    with patch("sys.argv", ["cobol-to-java", *argv]):
        cobol_to_java_controller.main()


def test_init_config_writes_the_annotated_default_and_never_overwrites(tmp_path, capsys):
    out = tmp_path / "modernize.yaml"
    _run(["--init-config", str(out)])
    assert out.read_text(encoding="utf-8") == DEFAULT_CONFIG
    with pytest.raises(SystemExit):
        _run(["--init-config", str(out)])
    assert "already exists" in capsys.readouterr().out


def _clean_room(tmp_path: Path) -> Path:
    clean = tmp_path / "demo_gitgalaxy_clean_20260101_000000"
    (clean / "02_cloud_schemas").mkdir(parents=True)
    (clean / "02_cloud_schemas" / "PROG_schema.json").write_text(json.dumps(SCHEMA), encoding="utf-8")
    return clean


def test_the_cli_applies_the_config_and_an_explicit_pkg_wins(tmp_path):
    clean = _clean_room(tmp_path)
    cfg = tmp_path / "t.yaml"
    cfg.write_text(
        "project:\n  package: com.acme.cfg\n  artifact_id: acme-app\njava:\n  build_tool: gradle\n",
        encoding="utf-8",
    )
    _run([str(clean), "--config", str(cfg), "--pkg", "com.acme.cli", "--header", str(tmp_path / "none.txt")])
    out = next(tmp_path.glob("demo_gitgalaxy_java_spring_*"))
    assert (out / "build.gradle").is_file() and not (out / "pom.xml").exists()
    assert "rootProject.name = 'acme-app'" in (out / "settings.gradle").read_text(encoding="utf-8")
    assert (out / "src/main/java/com/acme/cli/dto/ProgDfhcommareaDto.java").is_file()  # --pkg beats the config
    audit = (out / "java_migration_audit.txt").read_text(encoding="utf-8")
    assert "Target Config              : t.yaml" in audit and "17 / 3.2.4 / gradle" in audit


def test_an_invalid_config_stops_the_run(tmp_path, capsys):
    cfg = tmp_path / "bad.yaml"
    cfg.write_text("java:\n  version: 8\n", encoding="utf-8")
    with pytest.raises(SystemExit) as err:
        _run([str(_clean_room(tmp_path)), "--config", str(cfg)])
    assert err.value.code == 2 and "java.version 8 is not supported" in capsys.readouterr().out
