"""#3819: the conversion config's `culture:` section -- faithful to the COBOL program by default,
every departure a declared deviation.

The defaults reproduce the program's own behaviour and change nothing in the generated project;
each bad value names its key; a non-default reaches application.yml (`gitgalaxy.culture.*`, where
generated code reads it), the migration audit's "Declared cultural deviations" and every porting
ticket's target config; `--init-config` documents every option.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from gitgalaxy.standards.yaml_reader import load_yaml
from gitgalaxy.tools.cobol_to_java.cobol_to_java_build_forge import generate_application_yml
from gitgalaxy.tools.cobol_to_java.java_target import (
    DEFAULT_CONFIG,
    ConfigError,
    Culture,
    JavaTarget,
    target_from_dict,
)

SCHEMA = {"title": "DFHCOMMAREA", "properties": {"CA-ID": {"type": "string", "description": "PIC X(11)"}}}


def test_the_defaults_are_faithful_and_change_nothing():
    target = JavaTarget()
    assert target.culture == Culture() and target.deviations() == []
    assert generate_application_yml("app", target) == generate_application_yml("app")  # no culture block
    assert "gitgalaxy:" not in generate_application_yml("app", target)


@pytest.mark.parametrize(
    "culture, message",
    [
        ({"rounding": "up"}, "culture.rounding 'up' is not supported"),
        ({"overflow": "wrap"}, "culture.overflow"),
        ({"zone": "Mars/Olympus_Mons"}, "culture.zone"),
        ({"zone": "IST"}, "culture.zone"),  # an abbreviation is ambiguous (India / Ireland / Israel)
        ({"format_locale": "german"}, "culture.format_locale"),
        ({"display_locale": "de_DE"}, "culture.display_locale"),  # BCP-47 uses a hyphen
        ({"decimal_point": "dot"}, "culture.decimal_point"),
        ({"currency": ""}, "culture.currency"),
        ({"key_collation": "icu"}, "culture.key_collation"),
        ({"db2_date_format": "iso8601"}, "culture.db2_date_format"),
        ({"calendar": "gregorian"}, "unknown key culture.calendar"),
    ],
)
def test_each_bad_value_names_its_key(culture, message):
    with pytest.raises(ConfigError, match=message):
        target_from_dict({"culture": culture})


def test_national_settings_that_describe_the_environment_are_not_deviations():
    t = target_from_dict({"culture": {"zone": "Asia/Kolkata", "display_locale": "hi-IN", "decimal_point": "comma",
                                      "currency": "₹", "db2_date_format": "eur"}})  # fmt: skip
    assert t.deviations() == []


def test_each_business_choice_is_a_declared_deviation():
    t = target_from_dict({"culture": {"rounding": "half_even", "overflow": "error", "format_locale": "de-DE",
                                      "key_collation": "database"}})  # fmt: skip
    got = t.deviations()
    assert [d.split(":")[0] for d in got] == ["culture.rounding", "culture.overflow", "culture.format_locale",
                                              "culture.key_collation"]  # fmt: skip
    assert "banker's rounding" in got[0] and "cp037 byte order" in got[3]


def test_init_config_documents_every_option():
    culture = DEFAULT_CONFIG.split("\nculture:\n", 1)[1]
    for key in Culture.__dataclass_fields__:
        assert f"\n  {key}: " in "\n" + culture, key
    assert target_from_dict(load_yaml(DEFAULT_CONFIG)) == JavaTarget()


def _run(argv: list[str]) -> None:
    from gitgalaxy import cobol_to_java_controller

    with patch("sys.argv", ["cobol-to-java", *argv]):
        cobol_to_java_controller.main()


def test_a_config_reaches_application_yml_and_the_audit(tmp_path):
    clean = tmp_path / "demo_gitgalaxy_clean_20260101_000000"
    (clean / "02_cloud_schemas").mkdir(parents=True)
    (clean / "02_cloud_schemas" / "PROG_schema.json").write_text(json.dumps(SCHEMA), encoding="utf-8")
    cfg = tmp_path / "india.yaml"
    cfg.write_text("culture:\n  rounding: half_even\n  zone: Asia/Kolkata\n", encoding="utf-8")
    _run([str(clean), "--config", str(cfg), "--header", str(tmp_path / "none.txt")])
    out: Path = next(tmp_path.glob("demo_gitgalaxy_java_spring_*"))
    yml = (out / "src/main/resources/application.yml").read_text(encoding="utf-8")
    assert '\ngitgalaxy:\n  culture:\n    rounding: "half_even"\n' in yml and 'zone: "Asia/Kolkata"' in yml
    audit = (out / "java_migration_audit.txt").read_text(encoding="utf-8")
    section = audit.split("DECLARED CULTURAL DEVIATIONS", 1)[1].split("[1]", 1)[0]
    assert "culture.rounding: half_even" in section and "zone" not in section  # a zone is not a deviation
