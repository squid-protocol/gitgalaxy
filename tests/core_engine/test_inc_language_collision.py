# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

"""#4973 / #4974: a `.inc` is PHP/Fortran only on positive evidence (siblings of #4546).

Class: every `.inc` file (shared C / C++ / PHP / Fortran / Assembly extension in
COLLISION_FREQUENCIES) containing PHP or Fortran evidence must resolve to that
language wherever it sits (alone, beside C, C++, Fortran, Assembly, or PHP files).
Non-PHP `.inc` files must never be called PHP, and non-Fortran `.inc` files must
never be called Fortran.
Uses the REAL registry, not the isolated mock in test_language_lens.py.
"""

import pytest

from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_lens import LanguageDetector
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

PHP_SAMPLES = {
    "func_helper": "<?php\nfunction helper($a) {\n    if ($a) { return 1; }\n    return 0;\n}\n",
    "class_def": "<?php\nnamespace App;\nclass Helper {\n    public function run() {}\n}\n",
    "short_echo": "<?= $greeting ?>\n",
    "html_template": "<!DOCTYPE html>\n<html>\n<?php echo 'hello'; ?>\n</html>\n",
    "leading_whitespace": "\n\n    <?php\n$foo = 1;\n",
    "case_insensitive": "<?PHP\n$config = array('db' => 'main');\n",
    "minimal_php": "<?php\n$a = 1;\n",
    "require_stmt": "<?php\nrequire_once 'config.php';\n",
    "procedural_drupal": "<?php\n/**\n * @file\n * Sample Drupal include file.\n */\nfunction mymodule_help() {\n    return 'help';\n}\n",
}

NON_PHP_SAMPLES = {
    "c_header": (
        "#ifndef FOO_H\n#define FOO_H\nint helper(int a);\nint add(int a, int b);\n#endif\n",
        "c",
    ),
    "c_macro_heavy": (
        "#pragma once\n#define MAX(a,b) ((a)>(b)?(a):(b))\nstatic inline int dot(int x, int y) { return x*y; }\n",
        "c",
    ),
    "cpp_namespace": (
        "#pragma once\n#include <vector>\nnamespace a { class B { public: virtual ~B(); }; }\n",
        "cpp",
    ),
    "cpp_template": (
        "#pragma once\ntemplate <typename T>\nT twice(T x) { return x + x; }\n",
        "cpp",
    ),
    "fortran_common": (
        "      INTEGER, PARAMETER :: MAX_N = 100\n      COMMON /MYBLOCK/ A, B\n",
        "fortran",
    ),
    "fortran_subroutine": (
        "      SUBROUTINE HELPER(X, Y)\n      INTEGER X, Y\n      Y = X + 1\n      END\n",
        "fortran",
    ),
    "assembly_nasm": (
        "%define BUFFER_SIZE 1024\nsection .data\nmsg: db 'hello', 0\n",
        "assembly",
    ),
}

NEIGHBOURHOODS = {
    "alone": (),
    "beside_c": ("zz_impl.c", "zz_impl2.c"),
    "beside_cpp": ("zz_impl.cpp", "zz_impl2.cpp"),
    "beside_fortran": ("zz_mod.f", "zz_mod2.f90"),
    "beside_assembly": ("zz_boot.s", "zz_boot.asm"),
    "beside_php": ("zz_app.php", "zz_index.php", "zz_main.php"),
}


def _classify(tmp_path, name, text, extras):
    (tmp_path / name).write_text(text)
    for extra in extras:
        (tmp_path / extra).write_text("// placeholder\n")
    tally: dict[str, int] = {}
    for child in tmp_path.iterdir():
        tally[child.suffix.lower()] = tally.get(child.suffix.lower(), 0) + 1
        tally[child.name.lower()] = 1
    detector = LanguageDetector(LANGUAGE_DEFINITIONS, LEXICAL_FAMILY_HEURISTICS)
    return detector.inspect(tmp_path / name, text, ext_tally=tally)


@pytest.mark.parametrize("hood", sorted(NEIGHBOURHOODS))
@pytest.mark.parametrize("style", sorted(PHP_SAMPLES))
def test_inc_with_php_evidence_resolves_to_php(tmp_path, style, hood):
    res = _classify(tmp_path, "a.inc", PHP_SAMPLES[style], NEIGHBOURHOODS[hood])
    assert res["lang_id"] == "php"
    assert res["lock_tier"] == 2
    assert res["source_proof"] == "Single Indicator (Internal Signature)"


@pytest.mark.parametrize("hood", sorted(NEIGHBOURHOODS))
@pytest.mark.parametrize("style", sorted(NON_PHP_SAMPLES))
def test_inc_without_php_evidence_is_never_php(tmp_path, style, hood):
    text, _expected = NON_PHP_SAMPLES[style]
    res = _classify(tmp_path, "a.inc", text, NEIGHBOURHOODS[hood])
    assert res["lang_id"] != "php", f"non-PHP {style} in hood {hood} was misclassified as php"


def test_dot_php_files_unaffected(tmp_path):
    text = "<?php\nfunction foo() { return 1; }\n"
    res = _classify(tmp_path, "a.php", text, ())
    assert res["lang_id"] == "php"


# #4974: Fortran include files (.inc) with Fortran evidence
FORTRAN_SAMPLES = {
    "fixed_common": "      INTEGER I\n      COMMON /BLK/ I\n",
    "fixed_subroutine": "      SUBROUTINE HELPER(X, Y)\n      INTEGER X, Y\n      Y = X + 1\n      END SUBROUTINE\n",
    "fixed_parameter": "      PARAMETER (MAX_N = 100)\n      INTEGER ITEMS(MAX_N)\n      COMMON /BLK/ ITEMS\n",
    "fixed_double_precision": "      DOUBLE PRECISION X, Y, Z\n      COMMON /COORDS/ X, Y, Z\n",
    "fixed_implicit_none": "      IMPLICIT NONE\n      INTEGER N\n      COMMON /MYBLK/ N\n",
    "fixed_equivalence": "      INTEGER A(10)\n      REAL B(10)\n      EQUIVALENCE (A(1), B(1))\n",
    "fixed_dimension": "      INTEGER I\n      DIMENSION ARR(100)\n      COMMON /DATA/ ARR\n",
    "fixed_character": "      CHARACTER*80 TITLE\n      COMMON /INFO/ TITLE\n",
    "fixed_types_star": "      INTEGER*4 COUNT\n      REAL*8 VALUE\n      COMMON /C1/ COUNT, VALUE\n",
    "free_declaration_colon": "INTEGER :: x, y\nCOMMON /blk/ x, y\n",
    "free_parameter": "INTEGER, PARAMETER :: MAX_SIZE = 1024\nREAL, DIMENSION(MAX_SIZE) :: buffer\n",
    "free_type_def": "TYPE :: Point\n  REAL :: x, y\nEND TYPE Point\n",
    "free_interface": "INTERFACE\n  SUBROUTINE compute(val)\n    REAL, INTENT(INOUT) :: val\n  END SUBROUTINE compute\nEND INTERFACE\n",
}

NON_FORTRAN_SAMPLES = {
    "c_header": (
        "#ifndef FOO_H\n#define FOO_H\nint helper(int a);\nint add(int a, int b);\n#endif\n",
        "c",
    ),
    "c_macro_heavy": (
        "#pragma once\n#define MAX(a,b) ((a)>(b)?(a):(b))\nstatic inline int dot(int x, int y) { return x*y; }\n",
        "c",
    ),
    "cpp_namespace": (
        "#pragma once\n#include <vector>\nnamespace a { class B { public: virtual ~B(); }; }\n",
        "cpp",
    ),
    "cpp_template": (
        "#pragma once\ntemplate <typename T>\nT twice(T x) { return x + x; }\n",
        "cpp",
    ),
    "assembly_nasm": (
        "%define BUFFER_SIZE 1024\nsection .data\nmsg: db 'hello', 0\n",
        "assembly",
    ),
    "assembly_nasm_common": (
        "common counter 4\nsection .bss\n",
        "assembly",
    ),
    "php_helper": (
        "<?php\nfunction helper($a) {\n    if ($a) { return 1; }\n    return 0;\n}\n",
        "php",
    ),
}


@pytest.mark.parametrize("hood", sorted(NEIGHBOURHOODS))
@pytest.mark.parametrize("style", sorted(FORTRAN_SAMPLES))
def test_inc_with_fortran_evidence_resolves_to_fortran(tmp_path, style, hood):
    res = _classify(tmp_path, "a.inc", FORTRAN_SAMPLES[style], NEIGHBOURHOODS[hood])
    assert res["lang_id"] == "fortran"
    assert res["lock_tier"] == 2
    assert res["source_proof"] == "Single Indicator (Internal Signature)"


@pytest.mark.parametrize("hood", sorted(NEIGHBOURHOODS))
@pytest.mark.parametrize("style", sorted(NON_FORTRAN_SAMPLES))
def test_inc_without_fortran_evidence_is_never_fortran(tmp_path, style, hood):
    text, _expected = NON_FORTRAN_SAMPLES[style]
    res = _classify(tmp_path, "a.inc", text, NEIGHBOURHOODS[hood])
    assert res["lang_id"] != "fortran", f"non-Fortran {style} in hood {hood} was misclassified as fortran"


def test_dot_f_files_unaffected(tmp_path):
    text = "      PROGRAM HELLO\n      PRINT *, 'HI'\n      END PROGRAM\n"
    res = _classify(tmp_path, "a.f", text, ())
    assert res["lang_id"] == "fortran"
