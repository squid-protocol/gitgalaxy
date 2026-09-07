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
The `func_start` and `class_start` contracts (#2856, roadmap Phase 3), held
across the corpus languages in one place.

    func_start -- One hit is the syntax that opens an executable block of logic
    under its own name: a function, method, procedure or subroutine
    declaration, or the instruction that begins an executable step in a
    language with no named-callable form.

    class_start -- One hit is the declaration of a named type (class, struct,
    record, interface, enum or object) or the file's compilation-unit container
    where that container is the language's only named-entity declaration.

The #2856 audit changed no rule regex: under the stated sentences the existing
rules already conform, and all five open-defect cells (func_start dockerfile/
html, class_start dockerfile/jcl/kotlin) were collective-entry cross-product
mis-marks, corrected in the corpus ledger. This module pins the two shapes that
made those cells look like defects so a future rule edit cannot reintroduce
them:

  DUALS   the three deliberate one-token-two-constructs overlaps the contract
          keeps (the fortran-COMMON shape): dockerfile FROM (class_start +
          import), dockerfile HEALTHCHECK (func_start + safety), kotlin object
          (class_start + globals). Each rule on both sides must fire.
  BLOCKS  dockerfile's instruction keywords are its func_start morphology
          (RUN/CMD/ENTRYPOINT/HEALTHCHECK), and a reference/call is not a
          func_start declaration.
  ABSENCE the stated class_start None rows stay None, not an empty pattern.
"""

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _rule(lang, signal):
    return LANGUAGE_DEFINITIONS[lang]["rules"].get(signal)


# (lang, signal, text) -> the rule must match at least once.
DUAL_POSITIVES = [
    # dockerfile FROM: class_start (opens a named stage) AND import (base image)
    ("dockerfile", "class_start", "FROM golang:1.22 AS build"),
    ("dockerfile", "import", "FROM golang:1.22 AS build"),
    # dockerfile HEALTHCHECK: func_start (opens an executable block) AND safety
    ("dockerfile", "func_start", "HEALTHCHECK CMD curl -f http://localhost/ || exit 1"),
    ("dockerfile", "safety", "HEALTHCHECK CMD curl -f http://localhost/ || exit 1"),
    # kotlin object: class_start (a singleton type) AND globals (module state)
    ("kotlin", "class_start", "object Region {}"),
    ("kotlin", "globals", "object Region {}"),
]

# dockerfile's executable-block instructions are its func_start morphology.
DOCKERFILE_BLOCKS = [
    "RUN pytest",
    'CMD ["./serve"]',
    'ENTRYPOINT ["/init"]',
    "HEALTHCHECK CMD true",
]

# class_start: the compilation-unit container counts where it is the file's
# only named-entity declaration.
CONTAINER_POSITIVES = [
    ("cobol", "PROGRAM-ID. ROSETTA-MAIN."),
    ("jcl", "//ROSETTA JOB"),
]

# class_start stated absences (contract corollary): the rule is None, not "".
CLASS_START_ABSENT = ["agc_assembly", "m4", "makefile", "markdown", "shell"]


def test_deliberate_duals_fire_on_both_rules():
    for lang, signal, text in DUAL_POSITIVES:
        rule = _rule(lang, signal)
        assert rule is not None, f"{lang}: {signal} rule missing"
        assert rule.search(text), f"{lang}: {signal} lost the deliberate dual: {text!r}"


def test_dockerfile_instruction_blocks_are_func_start():
    rule = _rule("dockerfile", "func_start")
    for text in DOCKERFILE_BLOCKS:
        assert rule.search(text), f"dockerfile func_start dropped its block instruction: {text!r}"


def test_dockerfile_func_start_excludes_prose_and_args():
    """A reference is not a declaration: a bare word in a comment or an ARG
    value does not open an executable block."""
    rule = _rule("dockerfile", "func_start")
    for text in ["# run the tests", "ARG CMD=/bin/sh"]:
        assert not rule.search(text), f"dockerfile func_start matched a non-declaration: {text!r}"


def test_container_declaration_is_class_start():
    for lang, text in CONTAINER_POSITIVES:
        rule = _rule(lang, "class_start")
        assert rule is not None and rule.search(text), f"{lang}: class_start lost its container: {text!r}"


def test_class_start_stated_absences_are_none():
    for lang in CLASS_START_ABSENT:
        assert _rule(lang, "class_start") is None, f"{lang}: class_start should be the stated None absence"
