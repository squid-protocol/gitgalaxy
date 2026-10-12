"""#4547: the typosquat radar tests package names, never system headers or in-project paths."""

import json
from unittest.mock import patch

import pytest

from gitgalaxy.galaxyscope import Orchestrator
from gitgalaxy.standards.system_headers import is_system_header

CONFIG = {
    "LANGUAGE_DEFINITIONS": {},
    "APERTURE_CONFIG": {},
    "PARANOID_MODE": False,
    "FAIL_ON_SECRETS": False,
    "FAIL_ON_MALWARE": False,
    "MAX_RISK_EXPOSURE": 0.0,
}

# Every unique hit the Doom study logged (issue #4547) as (orphan, anchor, importer extension, include form).
DOOM_HEADER_PAIRS = [
    ("strings.h", "string.h", ".c"),
    ("dirent.h", "direct.h", ".c"),
    ("cstring", "string", ".cpp"),
    ("string", "cstring", ".cpp"),
    ("xinput.h", "dinput.h", ".cpp"),
    ("winsock.h", "winsock2.h", ".c"),
    ("mmintrin.h", "emmintrin.h", ".c"),
    ("xmmintrin.h", "emmintrin.h", ".c"),
    ("sys/timeb.h", "sys/time.h", ".c"),
    ("utime.h", "time.h", ".c"),
    ("GL/glx.h", "GL/gl.h", ".c"),
    ("limits", "climits", ".cpp"),
    ("alloc.h", "malloc.h", ".c"),
    ("cwctype", "cctype", ".cpp"),
    ("istream", "fstream", ".cpp"),
    ("windowsx.h", "windows.h", ".cpp"),
    ("xstring", "cstring", ".cpp"),
]


def _scan(files):
    scope = Orchestrator(".", CONFIG)
    scope.ram_cache = {path: {"raw_imports": set(imports)} for path, imports in files.items()}
    scope.stem_map = {k: k for k in scope.ram_cache}
    scope.ext_tally = {".h": 1, ".c": 1, ".cpp": 1}  # a real scan's census: `strings.h` keeps its dot
    with patch("gitgalaxy.galaxyscope.logger") as log:
        scope._resolve_dependency_graph()
    return scope, log


def _pair_files(orphan, anchor, ext, fmt):
    files = {f"src/a{i}{ext}": {fmt.format(anchor)} for i in range(3)}
    files[f"src/orphan{ext}"] = {fmt.format(orphan)}
    return files


@pytest.mark.parametrize(("orphan", "anchor", "ext"), DOOM_HEADER_PAIRS)
@pytest.mark.parametrize("fmt", ["#include <{}>", '#include "{}"'])
def test_system_header_pair_is_not_a_typosquat(orphan, anchor, ext, fmt):
    scope, log = _scan(_pair_files(orphan, anchor, ext, fmt))
    assert scope.typosquat_hits == 0
    assert not log.critical.called
    assert "sec_homoglyphs" not in scope.ram_cache[f"src/orphan{ext}"].get("equations", {})


@pytest.mark.parametrize(
    ("orphan", "anchor"),
    [
        ("math::set_prndindex", "math::get_prndindex"),
        ("sound_common::SndServerRx", "sound_common::SndServerTx"),
    ],
)
def test_rust_item_paths_are_not_typosquats(orphan, anchor):
    files = {f"src/a{i}.rs": {f"use {anchor};"} for i in range(3)}
    files["src/orphan.rs"] = {f"use {orphan};"}
    scope, log = _scan(files)
    assert scope.typosquat_hits == 0
    assert not log.critical.called


def test_action_version_pins_are_not_typosquats():
    files = {f".github/workflows/w{i}.yml": {"uses: actions/checkout@v6"} for i in range(3)}
    files[".github/workflows/old.yml"] = {"uses: actions/checkout@v3"}
    scope, log = _scan(files)
    assert scope.typosquat_hits == 0
    assert not log.critical.called


def test_extensionless_cxx_names_stay_eligible_outside_c_family():
    # `string`/`strings` are ordinary package names in Python; only a C++ importer makes them headers.
    assert is_system_header("string", ".cpp")
    assert not is_system_header("string", ".py")
    assert is_system_header("strings.h", ".py")
    assert not is_system_header("requests", ".py")


def test_real_typosquat_import_still_fires_but_not_critical_without_manifest():
    files = {f"src/m{i}.py": {"requests"} for i in range(3)}
    files["src/hacked.py"] = {"requasts"}
    scope, log = _scan(files)
    assert scope.typosquat_hits == 1
    assert "TYPOSQUATTING" in scope.ram_cache["src/hacked.py"]["metadata"]["alert"]
    assert not log.critical.called
    assert log.warning.called


def test_manifest_declared_typosquat_is_critical(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"dependencies": {"requasts": "1.0.0"}}))
    scope = Orchestrator(str(tmp_path), CONFIG)
    scope.ram_cache = {f"m{i}.py": {"raw_imports": {"requests"}} for i in range(3)}
    scope.ram_cache["hacked.py"] = {"raw_imports": {"requasts"}}
    scope.stem_map = {k: k for k in scope.ram_cache}
    scope.stem_map["package"] = "package.json"
    with patch("gitgalaxy.galaxyscope.logger") as log:
        scope._resolve_dependency_graph()
    assert scope.typosquat_hits == 1
    assert log.critical.called
