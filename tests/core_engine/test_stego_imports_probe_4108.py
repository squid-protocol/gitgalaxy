# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# ==============================================================================
"""#4108 slice 9: per-signal probe of Non-Standard / Steganographic Imports (`shadow_imports`).

Loader calls that name a non-code payload container and used to read 0, with near-miss controls (bundler asset
imports, code-file loads, dynamic paths) that must stay at zero, and a ReDoS control.
"""

import time

import pytest

from gitgalaxy.core.prism import Prism
from gitgalaxy.security.security_lens import SecurityLens
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

PRISM = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)

FIRES = {
    "ruby_require_relative": ("ruby", 'require_relative "payload.png"\n'),
    "lua_loadfile": ("lua", 'loadfile("blob.dat")\n'),
    "py_import_module": ("python", 'importlib.import_module("x.dat")\n'),
    "py_run_path": ("python", 'runpy.run_path("p.png")\n'),
    "js_backtick_require": ("javascript", "require(`./x.png`)\n"),
    "php_dir_prefix": ("php", '<?php\nrequire_once __DIR__ . "/x.png";\n'),
    "php_dirname_prefix": ("php", '<?php\ninclude(dirname(__FILE__)."/x.jpg");\n'),
    "ext_bmp": ("javascript", 'require("./x.bmp")\n'),
    "ext_webp": ("javascript", 'require("./x.webp")\n'),
    "ext_bin": ("javascript", 'require("./x.bin")\n'),
    "ext_ogg_upper": ("php", '<?php\ninclude("x.OGG");\n'),
}
QUIET = {
    "bundler_asset_import": ("javascript", 'import logo from "./logo.png";\n'),
    "load_code_file": ("ruby", 'require_relative "helper"\n'),
    "import_module_code": ("python", 'importlib.import_module("pkg.mod")\n'),
    "run_path_script": ("python", 'runpy.run_path("tool.py")\n'),
    "dynamic_backtick": ("javascript", "require(`./${name}`)\n"),
    "php_dir_code": ("php", '<?php\nrequire_once __DIR__ . "/lib.php";\n'),
    "bare_name": ("python", "loadfile = 1\nrun_path = 2\n"),
    "gradle_copy_spec_archive": ("groovy", 'include "jdk-${v}_linux-${a}_bin.tar.gz"\n'),
    "archive_extensions": ("php", '<?php\ninclude("x.gz");\ninclude("x.7z");\ninclude("x.rar");\n'),
    "commented": ("c", '// loadfile("x.png");\n'),
}


@pytest.fixture(scope="module")
def lens():
    return SecurityLens()


def _count(lens, lang, text):
    code = PRISM.split_streams(text, lang)["code_stream"]
    return lens.scan_content(text, code_stream=code, prose=False)["counts"]["shadow_imports"]


@pytest.mark.parametrize("lang,text", list(FIRES.values()), ids=list(FIRES))
def test_missed_loader_forms_fire(lens, lang, text):
    assert _count(lens, lang, text) == 1, text


@pytest.mark.parametrize("lang,text", list(QUIET.values()), ids=list(QUIET))
def test_near_misses_stay_quiet(lens, lang, text):
    assert _count(lens, lang, text) == 0, text


def test_redos_immune(lens):
    text = "require_relative " * 3000 + "\n" + 'import_module("' + "a" * 5000 + "\n"
    t = time.perf_counter()
    _count(lens, "ruby", text)
    assert time.perf_counter() - t < 5
