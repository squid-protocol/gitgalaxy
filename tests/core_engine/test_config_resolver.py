import pytest

from gitgalaxy.standards import gitgalaxy_config as defaults
from gitgalaxy.standards.config_resolver import (
    ConfigError,
    resolve_config,
)


# ==============================================================================
# DEFAULTS ONLY (no yaml, no CLI)
# ==============================================================================


def test_defaults_only_mirrors_gitgalaxy_config():
    resolved = resolve_config()

    assert resolved.STRICT_IMPORT_MODE == defaults.STRICT_IMPORT_MODE
    assert resolved.APERTURE_CONFIG["IGNORED_DIRECTORIES"] == defaults.APERTURE_CONFIG["IGNORED_DIRECTORIES"]
    assert resolved.PRIORITY_WHITELIST == defaults.PRIORITY_WHITELIST


def test_defaults_only_does_not_mutate_source_module(tmp_path):
    # Regression guard: the resolver must deep-copy, not alias, the
    # gitgalaxy_config.py collections -- otherwise one run's YAML merge
    # would permanently pollute the process-wide default for every run
    # after it (import-time singletons are shared across the whole process).
    yaml_path = tmp_path / ".galaxyscope.yaml"
    yaml_path.write_text(
        "galaxyscope:\n"
        "  APERTURE_CONFIG:\n"
        "    IGNORED_DIRECTORIES:\n"
        "      - some_totally_new_dir\n"
    )
    before = set(defaults.APERTURE_CONFIG["IGNORED_DIRECTORIES"])

    resolved = resolve_config(yaml_path=str(yaml_path))

    assert "some_totally_new_dir" in resolved.APERTURE_CONFIG["IGNORED_DIRECTORIES"]
    assert defaults.APERTURE_CONFIG["IGNORED_DIRECTORIES"] == before


# ==============================================================================
# PRECEDENCE: CLI > YAML > default
# ==============================================================================


def test_yaml_overrides_default(tmp_path):
    yaml_path = tmp_path / ".galaxyscope.yaml"
    yaml_path.write_text("galaxyscope:\n  STRICT_IMPORT_MODE: true\n")

    resolved = resolve_config(yaml_path=str(yaml_path))

    assert resolved.STRICT_IMPORT_MODE is True


def test_cli_overrides_yaml(tmp_path):
    yaml_path = tmp_path / ".galaxyscope.yaml"
    yaml_path.write_text("galaxyscope:\n  STRICT_IMPORT_MODE: true\n")

    resolved = resolve_config(
        yaml_path=str(yaml_path),
        cli_overrides={"STRICT_IMPORT_MODE": False},
    )

    # This is the store_true-can't-force-False footgun #332 was raised to
    # fix: an explicit CLI False must be able to beat a YAML True.
    assert resolved.STRICT_IMPORT_MODE is False


def test_cli_overrides_default_with_no_yaml():
    resolved = resolve_config(cli_overrides={"FIREWALL_NETWORK_WEIGHTING": True})

    assert resolved.FIREWALL_NETWORK_WEIGHTING is True


# ==============================================================================
# MERGE SEMANTICS: extend vs. replace
# ==============================================================================


def test_yaml_extends_set_valued_key_instead_of_replacing(tmp_path):
    yaml_path = tmp_path / ".galaxyscope.yaml"
    yaml_path.write_text(
        "galaxyscope:\n"
        "  APERTURE_CONFIG:\n"
        "    IGNORED_DIRECTORIES:\n"
        "      - my_custom_build_dir\n"
    )

    resolved = resolve_config(yaml_path=str(yaml_path))
    merged = resolved.APERTURE_CONFIG["IGNORED_DIRECTORIES"]

    assert "my_custom_build_dir" in merged
    # The large built-in default set must still be present -- extend, not
    # replace. node_modules is one of the original entries.
    assert "node_modules" in merged


def test_yaml_extends_list_valued_key(tmp_path):
    yaml_path = tmp_path / ".galaxyscope.yaml"
    yaml_path.write_text(
        "galaxyscope:\n"
        "  BLACKLISTED_IMPORTS:\n"
        "    - evil-pkg\n"
    )

    resolved = resolve_config(yaml_path=str(yaml_path))

    assert "evil-pkg" in resolved.BLACKLISTED_IMPORTS


def test_yaml_replaces_scalar_valued_key(tmp_path):
    yaml_path = tmp_path / ".galaxyscope.yaml"
    yaml_path.write_text(
        "galaxyscope:\n"
        "  APERTURE_CONFIG:\n"
        "    MAX_LINE_LENGTH: 123\n"
    )

    resolved = resolve_config(yaml_path=str(yaml_path))

    # Replace, not extend -- there's no sensible way to "merge" a threshold.
    assert resolved.APERTURE_CONFIG["MAX_LINE_LENGTH"] == 123


def test_yaml_extends_dict_valued_key(tmp_path):
    yaml_path = tmp_path / ".galaxyscope.yaml"
    yaml_path.write_text(
        "galaxyscope:\n"
        "  GUIDESTAR_CONFIG:\n"
        "    MANIFEST_MAP:\n"
        "      mix.exs: elixir\n"
    )

    resolved = resolve_config(yaml_path=str(yaml_path))
    manifest_map = resolved.GUIDESTAR_CONFIG["MANIFEST_MAP"]

    assert manifest_map["mix.exs"] == "elixir"
    # Built-in entries survive -- dict.update semantics, not replacement.
    assert manifest_map["package.json"] == "javascript"


# ==============================================================================
# UNKNOWN-KEY HANDLING: hard error (#332)
# ==============================================================================


def test_unknown_top_level_yaml_key_raises(tmp_path):
    yaml_path = tmp_path / ".galaxyscope.yaml"
    yaml_path.write_text("galaxyscope:\n  STRICT_IMPORT_MDOE: true\n")  # typo

    with pytest.raises(ConfigError, match="STRICT_IMPORT_MDOE"):
        resolve_config(yaml_path=str(yaml_path))


def test_unknown_nested_yaml_key_raises(tmp_path):
    yaml_path = tmp_path / ".galaxyscope.yaml"
    yaml_path.write_text(
        "galaxyscope:\n"
        "  APERTURE_CONFIG:\n"
        "    IGNORED_DIRECTORES:\n"  # typo: missing an I
        "      - build\n"
    )

    with pytest.raises(ConfigError, match="IGNORED_DIRECTORES"):
        resolve_config(yaml_path=str(yaml_path))


def test_internal_only_key_rejected_from_yaml(tmp_path):
    # BANDS is an internal label taxonomy, deliberately not overridable.
    yaml_path = tmp_path / ".galaxyscope.yaml"
    yaml_path.write_text(
        "galaxyscope:\n"
        "  APERTURE_CONFIG:\n"
        "    BANDS:\n"
        "      IGNORED: nope\n"
    )

    with pytest.raises(ConfigError, match="BANDS"):
        resolve_config(yaml_path=str(yaml_path))


def test_unknown_cli_key_raises():
    with pytest.raises(ConfigError, match="NOT_A_REAL_KEY"):
        resolve_config(cli_overrides={"NOT_A_REAL_KEY": True})


# ==============================================================================
# MALFORMED / MISSING YAML FILE: degrade to defaults, don't raise
# ==============================================================================
# This is a distinct failure mode from an unrecognized *key* above -- a
# corrupted file degrades (matches pre-existing CLI behavior tested by
# test_yaml_config_load_failure in test_galaxyscope.py), it does not raise.


def test_malformed_yaml_file_degrades_to_defaults(tmp_path):
    yaml_path = tmp_path / ".galaxyscope.yaml"
    yaml_path.write_text("[invalid yaml struct {")

    resolved = resolve_config(yaml_path=str(yaml_path))

    assert resolved.STRICT_IMPORT_MODE == defaults.STRICT_IMPORT_MODE


def test_missing_yaml_file_degrades_to_defaults(tmp_path):
    missing_path = tmp_path / "does_not_exist.yaml"

    resolved = resolve_config(yaml_path=str(missing_path))

    assert resolved.STRICT_IMPORT_MODE == defaults.STRICT_IMPORT_MODE


def test_yaml_file_with_no_galaxyscope_section_degrades_to_defaults(tmp_path):
    yaml_path = tmp_path / ".galaxyscope.yaml"
    yaml_path.write_text("unrelated_tool:\n  some_key: 1\n")

    resolved = resolve_config(yaml_path=str(yaml_path))

    assert resolved.STRICT_IMPORT_MODE == defaults.STRICT_IMPORT_MODE


# ==============================================================================
# NO-DEFAULT KEYS (SARIF_IGNORED_RULES / SARIF_IGNORED_PATHS)
# ==============================================================================


def test_no_default_key_defaults_to_empty_list():
    resolved = resolve_config()

    assert resolved.SARIF_IGNORED_RULES == []
    assert resolved.SARIF_IGNORED_PATHS == []


def test_no_default_key_extends_from_yaml(tmp_path):
    yaml_path = tmp_path / ".galaxyscope.yaml"
    yaml_path.write_text(
        "galaxyscope:\n"
        "  SARIF_IGNORED_RULES:\n"
        "    - GH-1022\n"
    )

    resolved = resolve_config(yaml_path=str(yaml_path))

    assert resolved.SARIF_IGNORED_RULES == ["GH-1022"]


# ==============================================================================
# ResolvedConfig ACCESS PATTERNS
# ==============================================================================
# Must support both calling conventions already in use across the codebase:
# getattr(config, "X", default) (chronometer.py, gpu_recorder.py today) and
# dict-style config["X"] / config.get("X") (galaxyscope.py's full_config).


def test_resolved_config_supports_getattr_with_default():
    resolved = resolve_config()

    assert getattr(resolved, "PROJECT_STORIES", "fallback") == defaults.PROJECT_STORIES
    assert getattr(resolved, "NOT_A_KEY", "fallback") == "fallback"


def test_resolved_config_supports_dict_style_access():
    resolved = resolve_config()

    assert resolved["STRICT_IMPORT_MODE"] == defaults.STRICT_IMPORT_MODE
    assert resolved.get("NOT_A_KEY", "fallback") == "fallback"
    assert "APERTURE_CONFIG" in resolved


def test_resolved_config_attribute_access_raises_attribute_error_for_unknown_key():
    resolved = resolve_config()

    with pytest.raises(AttributeError):
        resolved.NOT_A_KEY
