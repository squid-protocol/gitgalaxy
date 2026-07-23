# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

"""
config_resolver.py
Phase 1 of the config-override rework (issue #333; decisions in #332).

Single entry point for merging gitgalaxy_config.py defaults with
.galaxyscope.yaml overrides and CLI overrides, replacing the 3 previously
independent, inconsistent inline mechanisms in galaxyscope.py's main()
(a generic args.* interceptor that reached nothing, a hand-coded merge
covering only 4 of APERTURE_CONFIG's keys, and no path at all for the
other ~15 gitgalaxy_config.py constants).

Precedence (decided in #332): CLI overrides > .galaxyscope.yaml > the
gitgalaxy_config.py default. An unrecognized key -- in either the YAML
file's `galaxyscope:` section or in `cli_overrides` -- is a hard
ConfigError, not a warning: a typo'd security-policy key (e.g.
STRICT_IMPORT_MDOE) must not silently no-op. This is distinct from a
malformed/unreadable YAML *file*, which degrades to defaults with a logged
warning (matching pre-existing CLI behavior).

PROJECT_OVERRIDES (in language_standards.py) is deliberately NOT handled
here. Per #332 it is a separate, Python-only, maintainer-curated
per-project dialect-patch mechanism (it also patches LANGUAGE_DEFINITIONS,
which is outside gitgalaxy_config.py's domain entirely) -- callers apply it
as its own step, after this resolver has run, not as a 4th precedence tier.
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from gitgalaxy.standards import gitgalaxy_config as _defaults

logger = logging.getLogger("GalaxyScope.config_resolver")


class ConfigError(ValueError):
    """Raised when a config source names a key this resolver doesn't recognize."""


# ------------------------------------------------------------------
# Merge semantics registry
# ------------------------------------------------------------------
# "replace" -- the highest-precedence source that sets this key wins
#              outright (scalars, booleans, thresholds).
# "extend"  -- sources are unioned/merged rather than replacing each other:
#              sets union, lists concatenate, dicts update key-by-key. This
#              is the right default for policy allow/deny lists -- a user
#              adding one entry to BLACKLISTED_IMPORTS should not silently
#              wipe out the built-in ones.
# A nested dict (see APERTURE_CONFIG_SPEC / GUIDESTAR_CONFIG_SPEC) declares
# its own sub-key registry, so a typo'd sub-key is caught too, not just a
# typo'd top-level key.

REPLACE = "replace"
EXTEND = "extend"

APERTURE_CONFIG_SPEC: Dict[str, str] = {
    "SECRETS_EXTENSIONS": EXTEND,
    "SECRETS_EXACT": EXTEND,
    "IGNORED_DIRECTORIES": EXTEND,
    "IGNORED_EXTENSIONS": EXTEND,
    "CONTRABAND_PATTERNS": EXTEND,
    "VENDOR_MINIFICATION_PATHS": EXTEND,
    "MAX_LINE_LENGTH": REPLACE,
    "MINIFICATION_SCAN_LIMIT": REPLACE,
    "MAX_FILE_SIZE_MB": REPLACE,
    # BANDS is an internal label taxonomy, not user-overridable -- omitted
    # on purpose so a YAML BANDS key raises ConfigError.
}

GUIDESTAR_CONFIG_SPEC: Dict[str, str] = {
    "MANIFEST_MAP": EXTEND,
    "INTENT_BIASED_SECTORS": EXTEND,
    "EXEC_PREFIX_MAP": EXTEND,
    # IGNORED_DIRECTORIES is a same-object reference to APERTURE_CONFIG's
    # copy (see gitgalaxy_config.py) -- override it via APERTURE_CONFIG so
    # the two can't drift out of sync.
}

# Every gitgalaxy_config.py constant this resolver knows how to merge, and
# how. A key not listed here is not user-overridable: an attempt to set it
# from YAML or CLI raises ConfigError rather than silently doing nothing.
#
# LEXICAL_FAMILY_HEURISTICS is intentionally omitted -- it's a fixed
# heuristic table, not a user-facing policy knob, and nothing has ever
# asked to override it.
TOP_LEVEL_SPEC: Dict[str, Any] = {
    "STRICT_IMPORT_MODE": REPLACE,
    "APPROVED_IMPORTS": EXTEND,
    "BLACKLISTED_IMPORTS": EXTEND,
    "FIREWALL_NETWORK_WEIGHTING": REPLACE,
    "DENYLIST_PATTERNS": EXTEND,
    "ALLOWLIST_PATHS": EXTEND,
    "XRAY_BYPASS_EXTENSIONS": EXTEND,
    "XRAY_BYPASS_PATHS": EXTEND,
    "APERTURE_CONFIG": APERTURE_CONFIG_SPEC,
    "PRIORITY_WHITELIST": EXTEND,
    "GUIDESTAR_CONFIG": GUIDESTAR_CONFIG_SPEC,
    "EXACT_FILE_MATCH": EXTEND,
    "TEST_NAMING_CONVENTIONS": EXTEND,
    "CHRONOMETER_CONFIG": EXTEND,
    "PROJECT_STORIES": EXTEND,
    # These two have no gitgalaxy_config.py default at all -- they're
    # YAML-only, matching the pre-existing precedent already in this
    # repo's own .galaxyscope.yaml (main() has read them straight out of
    # config_file_data with no compiled-in default since before this
    # resolver existed).
    "SARIF_IGNORED_RULES": EXTEND,
    "SARIF_IGNORED_PATHS": EXTEND,
}

# Keys with no gitgalaxy_config.py constant backing them (see comment above).
_NO_DEFAULT_KEYS = {"SARIF_IGNORED_RULES", "SARIF_IGNORED_PATHS"}

# Which top-level keys a CLI flag may set. CLI flags only make sense for
# scalars/booleans -- list/dict-valued policy keys are YAML-only (#332).
# Empty for now: no argparse flag maps to a gitgalaxy_config.py key yet.
# Phase 2 adds the flags and extends this set; resolve_config() enforces it
# either way so a miswired future flag fails loudly instead of silently
# matching nothing (the original bug this whole effort started from).
CLI_OVERRIDABLE_KEYS: set = {
    "STRICT_IMPORT_MODE",
    "FIREWALL_NETWORK_WEIGHTING",
}


@dataclass
class ResolvedConfig:
    """
    Final, merged configuration for a single scan run.

    Exposes every key both as an attribute (`getattr(config, "X", default)`)
    and as a dict item (`config["X"]` / `config.get("X")`), so it is a
    drop-in replacement for both calling conventions currently in use
    across the codebase: the `from gitgalaxy.standards import
    gitgalaxy_config as config` + `getattr(config, ...)` pattern (
    chronometer.py, gpu_recorder.py) and the `full_config` plain-dict
    pattern galaxyscope.py's main() builds today.
    """

    _values: Dict[str, Any] = field(default_factory=dict)

    def __getattr__(self, name: str) -> Any:
        # Only called when normal attribute lookup fails, i.e. never for
        # `_values` itself -- safe against recursion.
        try:
            return self._values[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def get(self, name: str, default: Any = None) -> Any:
        return self._values.get(name, default)

    def __getitem__(self, name: str) -> Any:
        return self._values[name]

    def __contains__(self, name: str) -> bool:
        return name in self._values

    def to_dict(self) -> Dict[str, Any]:
        return copy.deepcopy(self._values)


def _get_default(key: str) -> Any:
    if key in _NO_DEFAULT_KEYS:
        return {} if isinstance(TOP_LEVEL_SPEC[key], dict) else []
    if not hasattr(_defaults, key):
        raise ConfigError(
            f"config_resolver.TOP_LEVEL_SPEC references '{key}', but "
            f"gitgalaxy_config.py defines no such constant."
        )
    return copy.deepcopy(getattr(_defaults, key))


def _merge_collection(base: Any, override: Any) -> Any:
    if isinstance(base, set):
        return base | set(override)
    if isinstance(base, dict):
        merged = dict(base)
        merged.update(override)
        return merged
    if isinstance(base, list):
        return [*base, *override]
    # Shouldn't happen for real gitgalaxy_config.py values, but degrade
    # sensibly for a no-default key whose shape isn't known ahead of time.
    if isinstance(override, dict):
        return {**(base or {}), **override}
    return [*(base or []), *override]


def _merge_value(base: Any, override: Any, spec: Any, *, path: str) -> Any:
    if isinstance(spec, dict):
        if not isinstance(override, dict):
            raise ConfigError(
                f"'{path}' must be a mapping in .galaxyscope.yaml, got "
                f"{type(override).__name__}."
            )
        merged = copy.deepcopy(base) if isinstance(base, dict) else {}
        for sub_key, sub_val in override.items():
            if sub_key not in spec:
                raise ConfigError(
                    f"Unrecognized key '{sub_key}' under '{path}' in "
                    f".galaxyscope.yaml. Known keys: {sorted(spec)}"
                )
            merged[sub_key] = (
                sub_val if spec[sub_key] == REPLACE
                else _merge_collection(merged.get(sub_key), sub_val)
            )
        return merged

    if spec == REPLACE:
        return override
    return _merge_collection(base, override)


def _load_yaml_section(yaml_path: str) -> Dict[str, Any]:
    """
    Returns the `galaxyscope:` section of the YAML file, or {} if the file
    is missing, unreadable, or contains malformed YAML syntax -- that class
    of failure degrades to defaults with a logged error rather than
    raising, matching the pre-existing CLI behavior (see
    test_yaml_config_load_failure). It is NOT the same thing as an
    unrecognized *key* inside an otherwise-valid file, which is a
    ConfigError raised by the caller.
    """
    try:
        import yaml
    except ImportError:
        logger.warning("pyyaml not installed -- ignoring --config %s", yaml_path)
        return {}

    try:
        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f) or {}
    except Exception as exc:
        logger.error("Failed to load config file %s: %s", yaml_path, exc)
        return {}

    section = data.get("galaxyscope", {}) if isinstance(data, dict) else {}
    return section or {}


def resolve_config(
    yaml_path: Optional[str] = None,
    cli_overrides: Optional[Dict[str, Any]] = None,
) -> ResolvedConfig:
    """
    Merge, in the precedence decided in #332:
        gitgalaxy_config.py defaults -> .galaxyscope.yaml -> cli_overrides

    `cli_overrides` should contain only keys the user actually specified on
    the command line (the tri-state fix from #332/#334 -- omit a key
    entirely rather than passing its argparse default, so this function can
    tell "not specified" from "explicitly set").

    Raises ConfigError for any key in `yaml_path`'s `galaxyscope:` section
    or in `cli_overrides` that isn't in TOP_LEVEL_SPEC (or, for nested
    dict-valued keys, isn't in that key's own sub-key spec).
    """
    resolved: Dict[str, Any] = {key: _get_default(key) for key in TOP_LEVEL_SPEC}

    if yaml_path:
        yaml_data = _load_yaml_section(yaml_path)
        for key, val in yaml_data.items():
            if key not in TOP_LEVEL_SPEC:
                raise ConfigError(
                    f"Unrecognized key '{key}' in .galaxyscope.yaml's "
                    f"'galaxyscope:' section. Known keys: "
                    f"{sorted(TOP_LEVEL_SPEC)}"
                )
            resolved[key] = _merge_value(
                resolved[key], val, TOP_LEVEL_SPEC[key], path=key
            )

    if cli_overrides:
        for key, val in cli_overrides.items():
            if key not in CLI_OVERRIDABLE_KEYS:
                raise ConfigError(
                    f"'{key}' is not a CLI-overridable config key. Known "
                    f"CLI keys: {sorted(CLI_OVERRIDABLE_KEYS)}"
                )
            resolved[key] = val

    return ResolvedConfig(_values=resolved)
