# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""The `unreferenced_by_name` contract (#2806), pinned in one cross-language module.

The sentence, from `docs/unreferenced_by_name_contract.md`:

    One hit is one extracted callable unit whose name occurs nowhere in the
    file outside its own definition.

and its corollaries, one test each. The signal used to be called `orphaned_logic`
and recorded as `state_slop_orphans`; both names asserted the count was dead
weight, which is a claim the measurement cannot make -- #2806 renamed it to what
it measures and declared the one language where even that question is
unanswerable.

Everything here is a cross-language table, not a per-language test: the point of
a contract is that the same construct counts the same way in every registry, so
a language that disagrees shows up as a row, not as a missing file.
"""

from __future__ import annotations

import pytest

from gitgalaxy.core.detector import INVOCATION_BY_NAME, INVOCATION_MODELS, INVOCATION_POSITIONAL, StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _census(lang: str, code: str) -> int:
    return StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")["equations"].get("unreferenced_by_name", 0)


def _declared_model(lang: str) -> str:
    return LANGUAGE_DEFINITIONS[lang].get("invocation_model", INVOCATION_BY_NAME)


# The languages that declare they cannot be asked. Kept as a literal so ADDING a
# language to the family is a deliberate edit reviewed against the contract's
# corollary 4, never a side effect of a registry tweak.
POSITIONAL_LANGUAGES = {"jcl"}


def test_invocation_model_values_are_a_closed_set():
    """A typo in a registry must not silently mean `by_name`.

    `invocation_model` is read with a default, so a misspelt `"positonal"`
    would take the default branch and the language would go on being censused
    with nobody noticing. The set is closed here instead.
    """
    for lang, defn in LANGUAGE_DEFINITIONS.items():
        model = defn.get("invocation_model", INVOCATION_BY_NAME)
        assert model in INVOCATION_MODELS, f"{lang} declares an unknown invocation_model {model!r}"


def test_exactly_the_declared_family_skips_the_census():
    declared = {lang for lang in LANGUAGE_DEFINITIONS if _declared_model(lang) == INVOCATION_POSITIONAL}
    assert declared == POSITIONAL_LANGUAGES, (
        "the positional family changed; read docs/unreferenced_by_name_contract.md corollary 4 "
        "before widening it -- four of the five languages #2806 first proposed for it (abap, m4, "
        "makefile, objective-c) DO name their callees, and their 100% census was a corpus plant gap"
    )


# --- corollary 1: one callable unit is at most one hit ------------------------


def test_one_unit_is_one_hit_however_often_the_name_recurs():
    """A function is counted once, or not at all -- never once per occurrence."""
    two_uncalled = "def probe_globals(env):\n    return env\n\n\ndef probe_io(path):\n    return path\n"
    assert _census("python", two_uncalled) == 2

    # The same two functions, one of them named three more times: still a census
    # of units, and the named one simply leaves it.
    partly_called = two_uncalled + "\n\nprobe_globals(1)\nprobe_globals(2)\nprobe_globals(3)\n"
    assert _census("python", partly_called) == 1


# --- corollary 2: a declaration is not a reference ----------------------------


@pytest.mark.parametrize(
    ("lang", "code", "why"),
    [
        (
            "ada",
            "procedure Probe_Globals (Env : Integer) is\nbegin\n   null;\nend Probe_Globals;\n",
            "Ada closes a subprogram by repeating its name",
        ),
        (
            "shell",
            'make_module()\n{\n        MODULES="${MODULES} ${1}"\n}\n',
            "a K&R shell declaration sits outside the slicer's own span",
        ),
        (
            "tcl",
            "proc probe_globals {env} {\n    return $env\n}\nnamespace export probe_globals\n",
            "an export statement is a visibility declaration, not a call (#2774)",
        ),
        (
            "scheme",
            "(export probe-globals)\n\n(define (probe-globals env)\n  env)\n",
            "a Scheme export clause is a declaration too (#2823)",
        ),
        (
            "haskell",
            "module A (probeGlobals) where\n\nprobeGlobals :: Int -> Int\nprobeGlobals env = env\n",
            "a Haskell module export list is a declaration too (#2823)",
        ),
    ],
)
def test_a_declaration_of_the_name_does_not_clear_the_flag(lang: str, code: str, why: str):
    assert _census(lang, code) == 1, why


# --- corollary 2, the plural form: one construct, many declared names (#2823) --


def test_an_export_construct_declaring_many_names_covers_all_of_them():
    """#2774's `_visibility_export` captures ONE name per match, which is the
    whole statement for `export -f foo` and its four siblings and cannot express
    a construct that names every exported function at once.

    Both of #2823's languages write exactly that, and both read 0.25 unreferenced
    per keyword-rosetta file against a 2.50 corpus median before
    `_visibility_export_list`: 12 of 13 probe functions cleared the flag on their
    own export declaration while nothing called any of them.
    """
    haskell = (
        "module A (probeGlobals, probeTest, probeSafety) where\n"
        "\n"
        "probeGlobals :: Int -> Int\n"
        "probeGlobals env = env\n"
        "\n"
        "probeTest :: Int -> Int\n"
        "probeTest kit = kit\n"
        "\n"
        "probeSafety :: Int -> Int\n"
        "probeSafety value = value\n"
    )
    assert _census("haskell", haskell) == 3, "every name in the list is declared, not referenced"

    scheme = (
        "(export probe-globals probe-test)\n"
        "\n"
        "(define (probe-globals env)\n  env)\n"
        "\n"
        "(define (probe-test kit)\n  kit)\n"
    )
    assert _census("scheme", scheme) == 2, "one clause, two declared names, two hits"


def test_the_plural_export_form_still_lets_a_real_call_clear_the_flag():
    """The discount is per NAME OFFSET, never per line or per construct: only the
    occurrences inside the export region stop counting, so an ordinary call
    elsewhere in the file clears the flag exactly as it always did.
    """
    called = (
        "module A (probeGlobals, probeTest) where\n"
        "\n"
        "probeTest :: Int -> Int\n"
        "probeTest kit = probeGlobals kit\n"
        "\n"
        "probeGlobals :: Int -> Int\n"
        "probeGlobals env = env\n"
    )
    assert _census("haskell", called) == 1, "probeGlobals is called by probeTest; only probeTest is unreferenced"

    scheme_called = (
        "(export probe-globals probe-test)\n"
        "\n"
        "(define (probe-test kit)\n  (probe-globals kit))\n"
        "\n"
        "(define (probe-globals env)\n  env)\n"
    )
    assert _census("scheme", scheme_called) == 1


def test_a_haskell_module_header_with_no_export_list_declares_nothing():
    """`module Main where` exports everything implicitly and names nobody, so the
    rule must not match it -- and the census must go on answering normally.
    """
    code = "module Main where\n\nprobeGlobals :: Int -> Int\nprobeGlobals env = env\n"
    assert _census("haskell", code) == 1, "nothing names it, and the header does not either"

    code_called = code + "\nprobeTest :: Int -> Int\nprobeTest kit = probeGlobals kit\n"
    assert _census("haskell", code_called) == 1, "probeGlobals is called; probeTest is the one left"


# --- corollary 3: any other occurrence clears it, and that is the whole claim --


def test_any_other_occurrence_clears_the_flag_including_a_non_call():
    """The signal is named for what it measures, and this is the reason.

    A mention in a string literal is not a call -- no rule in this engine shields
    string literals (#2535) -- but it IS another occurrence of the name, so it
    clears the flag. Under the old name that read as "this function is alive";
    under this one it reads as "something else in the file names it", which is
    exactly what happened.
    """
    uncalled = "def probe_globals(env):\n    return env\n"
    assert _census("python", uncalled) == 1

    mentioned = uncalled + '\nDOC = "probe_globals is deprecated"\n'
    assert _census("python", mentioned) == 0, "a mention is not a call, and the census cannot tell"


# --- corollary 4: no invoke-by-name form means no census ----------------------


def test_positional_languages_record_no_census_at_all():
    """jcl: three EXEC steps, nothing anywhere referencing any of them.

    Every by-name language reports 3 for the same shape. JCL reports nothing,
    because a JCL step is reached by being written where it is, and the question
    "does anything name this step" has no bearing on whether it runs.
    """
    job = (
        "//ROSETTA JOB\n"
        "//PROBEGLOB EXEC PGM=BPXBATCH,PARM='G'\n"
        "//PROBEIO   EXEC PGM=BPXBATCH,PARM='I'\n"
        "//PROBERISK EXEC PGM=IKJEFT01,PARM='R'\n"
    )
    assert _census("jcl", job) == 0

    equivalent_python = "def probeglob():\n    pass\n\n\ndef probeio():\n    pass\n\n\ndef proberisk():\n    pass\n"
    assert _census("python", equivalent_python) == 3, "the same shape in a by-name language is a full census"


def test_positional_languages_are_also_immune_to_the_accidental_collision():
    """The 11% that used to clear the flag were noise, not invocations.

    On the language-crucible, 42 of 376 JCL steps read as referenced. None were
    invoked -- JCL cannot invoke a step. They collided with unrelated text: a
    step named CREATE beside inline SQL, COBOL beside the word inside a DSN.
    Suppressing the census removes both halves of the noise, not just the 89%.
    """
    colliding = "//ROSETTA JOB\n//CREATE   EXEC PGM=IKJEFT01\n//SYSIN    DD *\n  CREATE TABLE ACCOUNTS (ID INT);\n/*\n"
    assert _census("jcl", colliding) == 0

    # The declaration alone is inert too: no census means no census, in either
    # direction, so a JCL file can never contribute to the metric.
    lone = "//ROSETTA JOB\n//STEP1 EXEC PGM=BPXBATCH\n"
    assert _census("jcl", lone) == 0


def test_the_family_is_opt_in_and_leaves_every_other_language_untouched():
    """Corollary 4 is a declaration, not a heuristic over the file.

    A language joins by writing one registry key. Nothing about the text -- how
    few names recur, how positional the code looks -- can move a language in or
    out of the family, which is what keeps the other 45 unchanged by
    construction.
    """
    steps = "def a():\n    pass\n\n\ndef b():\n    pass\n"
    assert _census("python", steps) == 2

    patched = {**LANGUAGE_DEFINITIONS["python"], "invocation_model": INVOCATION_POSITIONAL}
    suppressed = StructuralExtractor("python", {**LANGUAGE_DEFINITIONS, "python": patched})
    assert suppressed.splice(steps, "")["equations"].get("unreferenced_by_name", 0) == 0


# --- corollary 5: the census is intra-file ------------------------------------


def test_the_census_sees_one_file_and_says_so():
    """A call from another file is not visible here, and must not be guessed at.

    galaxyscope.py's Contextual Baseline Fix is the layer that knows whether
    anything imports this file; the census below it deliberately answers a
    smaller question over one file's text.
    """
    library = "def probe_globals(env):\n    return env\n"
    assert _census("python", library) == 1, "an exported-but-uncalled library function is unreferenced HERE"


# --- corollary 6: a synthetic slicer bucket is not a callable unit ------------


def test_synthetic_slicer_buckets_are_not_censused():
    """#2547/#2728: a keyword cannot be unreferenced, because it is not a name."""
    docker = "FROM scratch\nRUN echo one\nRUN echo two\n"
    assert _census("dockerfile", docker) == 0
