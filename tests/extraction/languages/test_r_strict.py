"""
R (#6572): `.r` / `.R` are mapped, a `name <- function(...) {` block is a sliced unit (the three assignment
operators, a `$` receiver chain and a backticked name all bind a name), `setClass` / `R6Class` are class_start hits,
and `library` / `require` name their package in `_dependency_capture` (no import is read from a comment or a
multi-line string). Every snippet is real R.
"""

import re
import sys
from pathlib import Path

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_lens import LanguageDetector
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import assert_redos_immune_all  # noqa: E402 # type: ignore

R = LANGUAGE_DEFINITIONS["r"]
RULES = R["rules"]

SRC = (
    "library(dplyr)\n"
    "# library(hidden)\n"
    "\n"
    "area <- function(s, k = c(1, 2)) {\n"
    "  if (is.null(s)) {\n"
    '    stop("no shape")\n'
    "  }\n"
    "  vapply(s, function(z) z * 2, numeric(1))\n"
    "}\n"
    "\n"
    "total = function(xs) {\n"
    "  sum(xs)\n"
    "}\n"
)


def _route(name: str, content: str) -> str:
    return LanguageDetector(LANGUAGE_DEFINITIONS, {}).focus(name, content)[0]


def _splice(content: str) -> dict:
    return StructuralExtractor("r", LANGUAGE_DEFINITIONS).splice(content, "")


def _hits(rule: str, content: str) -> list[str]:
    return [m.group(0).strip() for m in RULES[rule].finditer(content)]


def _starts(content: str) -> list[str]:
    return [m.group(1) or m.group(2) for m in RULES["func_start"].finditer(content)]


def test_r_and_capital_r_extensions_route_to_r():
    assert _route("analysis.R", SRC) == "r"
    assert _route("tests/testthat/test-area.r", SRC) == "r"


def test_function_blocks_are_units_with_spans_and_args():
    fns = {f["name"]: (f["start_line"], f["end_line"], f["args"]) for f in _splice(SRC)["functions"]}
    # the default `c(1, 2)` holds a comma inside a call, so `k = c(1, 2)` is one argument
    assert fns["area"] == (4, 9, 2)
    assert fns["total"] == (11, 13, 1)


def test_func_start_forms():
    src = (
        "a <- function(x) {\n}\n"
        "b <<- function(x) {\n}\n"
        "c = function(x) {\n}\n"
        "`my fn` <- function() {\n}\n"
        ".hidden <- function() {\n}\n"
        "self$run <- function(x) {\n}\n"
        "  greet = function(who) {\n  }\n"
        "d <- \\(x) x + 1\n"
        "e <- function (x) x\n"
    )
    assert _starts(src) == ["a", "b", "c", "my fn", ".hidden", "run", "greet", "d", "e"]


def test_func_start_ignores_comparisons_calls_and_right_assignment():
    src = (
        "x == function(y) 1\nf(x) <- 2\nprint(function(x) x)\nfunction(x) x -> g\ny <- g(function(a) a)\nif (a = 1) 2\n"
    )
    assert _starts(src) == []


def test_classes_are_found():
    src = (
        'setClass("Shape", representation(name = "character"))\n'
        'Person <- R6Class("Person",\n  public = list(name = NULL)\n)\n'
        'Acc <- setRefClass("Acc", fields = list(b = "numeric"))\n'
        'setClassUnion("NumOrChar", c("numeric", "character"))\n'
    )
    assert [m.group(1) or m.group(2) for m in RULES["class_start"].finditer(src)] == [
        "Shape",
        "Person",
        "Acc",
        "NumOrChar",
    ]


def test_dependencies_capture_the_package():
    src = (
        "library(dplyr)\n"
        'library("ggplot2")\n'
        "require(data.table, quietly = TRUE)\n"
        'requireNamespace("jsonlite")\n'
        'library(package = "stringr")\n'
        "  suppressWarnings(library(hidden))\n"
        "if (!requireNamespace('x')) 1\n"
        "x <- libraryfoo(1)\n"
    )
    assert [m.group(1) for m in RULES["_dependency_capture"].finditer(src)] == [
        "dplyr",
        "ggplot2",
        "data.table",
        "jsonlite",
        "stringr",
    ]


def test_import_capture_blank_hides_comments_and_multiline_strings_only():
    src = (
        "# library(Hidden1)\n"
        'x <- "\nlibrary(Hidden2)\n"\n'
        "y <- '\nlibrary(Hidden3)\n'\n"
        'z <- "# not a comment"\n'
        'library("Real")\n'
        "library(Real2)\n"
    )
    blank = re.compile(R["import_capture_blank"])
    # mirrors galaxyscope: a one-line literal is kept, a literal spanning lines is blanked
    kept = blank.sub(lambda m: m.group() if "\n" not in m.group() else re.sub(r"[^\n]", " ", m.group()), src)
    assert R["import_capture_multiline_only"] is True
    assert [m.group(1) for m in RULES["_dependency_capture"].finditer(kept)] == ["Real", "Real2"]


def test_suppression_and_internals_are_safety_bypasses():
    assert _hits("safety_bypasses", "suppressWarnings(f())\nstats:::internal(x)\nunlockBinding('a', e)\n") == [
        "suppressWarnings(",
        "stats:::internal",
        "unlockBinding(",
    ]


def test_branches_ignore_dotted_names():
    assert _hits("branch", "if (a) b else c\nx <- is.if + a$for\nwhile (TRUE) next\nifelse(a, 1, 2)\n") == [
        "if",
        "else",
        "while",
        "ifelse",
    ]


def test_roxygen_and_testthat_signals():
    assert _hits("doc", "#' Title\n#' @param x y\nx <- 1  # plain\n") == ["#'", "#'"]
    assert _hits("test", 'test_that("a", {\n  expect_equal(1, 1)\n})\n') == ["test_that(", "expect_equal("]


def test_every_rule_survives_pathological_input():
    payloads = [
        "x <- function(" + "a, " * 4000 + "\n",
        "x <- function(" + "(" * 5000 + "\n",
        "a" * 20000 + " <- function(\n",
        "`" + "a" * 20000 + "\n",
        "$" * 5000 + " <- function\n",
        "x <- '" + "\\" * 5000 + "\n",
        '"' + "a\n" * 5000,
        "# " + "function(" * 5000 + "\n",
        "library(" + "a." * 5000 + "\n",
        "R6Class(" + "R6Class(" * 3000 + "\n",
    ]
    pairs = [(rule, p) for rule in [r for r in RULES.values() if hasattr(r, "finditer")] for p in payloads]
    assert_redos_immune_all(pairs)
