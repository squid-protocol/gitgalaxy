from gitgalaxy.standards.language_standards._shared_patterns import (
    CALLS_OUT_C_STYLE,
    CALLS_OUT_CALL_VERB,
    CALLS_OUT_COMMAND_POSITION,
    CALLS_OUT_LISP_FAMILY,
)

from _strict_harness import assert_redos_immune


def test_calls_out_c_style_strict():
    """
    Epic #3264: Validate the universal C-style invocation pattern.
    """
    assert CALLS_OUT_C_STYLE is not None

    # 1. Valid matches
    assert CALLS_OUT_C_STYLE.findall("foo()") == ["foo"]
    assert CALLS_OUT_C_STYLE.findall("foo (  )") == ["foo"]
    assert CALLS_OUT_C_STYLE.findall("my_func(x, y)") == ["my_func"]
    assert CALLS_OUT_C_STYLE.findall("Class.method(") == ["method"]

    # 2. ReDoS immunity
    # Create a long string that ALMOST matches but fails at the end.
    # The pattern is: \b([a-zA-Z_]\w*)\s*\(
    # Adversarial payload: a valid identifier, followed by 10,000 spaces, but NO parenthesis.
    payload = "foo" + (" " * 10000) + "x"
    assert_redos_immune(CALLS_OUT_C_STYLE, payload)

    # Another payload: 10,000 valid identifier characters, then a space, then no parenthesis
    payload2 = "a" * 10000 + " " + "x"
    assert_redos_immune(CALLS_OUT_C_STYLE, payload2)


def test_calls_out_call_verb_strict():
    """
    Epic #3264 Phase 3: Validate the verb-invocation paradigm
    (FORTRAN/PL/I/REXX/DB2 SQL/assembly `CALL name`).
    """
    assert CALLS_OUT_CALL_VERB.groups == 1

    # 1. Valid matches: parenthesized, paren-less (rexx), quoted (pli/db2 literals),
    # case-insensitive mnemonics (nasm), mainframe identifier charset.
    assert CALLS_OUT_CALL_VERB.findall("CALL PROBE_BRANCH(ARGV)") == ["PROBE_BRANCH"]
    assert CALLS_OUT_CALL_VERB.findall("call probe_branch 1") == ["probe_branch"]
    assert CALLS_OUT_CALL_VERB.findall("CALL 'SUBPROG' USING X") == ["SUBPROG"]
    assert CALLS_OUT_CALL_VERB.findall("    call    probe_io") == ["probe_io"]
    assert CALLS_OUT_CALL_VERB.findall("CALL SYS$#@-LIB") == ["SYS$#@-LIB"]
    # #3520: a Unicode or national first character (navikt/DSF `CALL ÅPNE_DATABASE`).
    assert CALLS_OUT_CALL_VERB.findall("CALL ÅPNE_DATABASE;") == ["ÅPNE_DATABASE"]
    assert CALLS_OUT_CALL_VERB.findall("CALL OVERFØR_TIL_MAP;") == ["OVERFØR_TIL_MAP"]
    assert CALLS_OUT_CALL_VERB.findall("CALL $X") == ["$X"]

    # 2. Negatives: no bare-word capture, no partial-word CALL, no numeric labels.
    assert CALLS_OUT_CALL_VERB.findall("PROBE_BRANCH(ARGV)") == []
    assert CALLS_OUT_CALL_VERB.findall("RECALL HISTORY") == []
    assert CALLS_OUT_CALL_VERB.findall("CALLED BY MAIN") == []
    assert CALLS_OUT_CALL_VERB.findall("GO TO 100") == []
    assert CALLS_OUT_CALL_VERB.findall("CALL 100") == []

    # 3. ReDoS immunity: CALL followed by a huge run of spaces and a non-identifier.
    assert_redos_immune(CALLS_OUT_CALL_VERB, "CALL" + (" " * 10000) + "1")
    assert_redos_immune(CALLS_OUT_CALL_VERB, "CALL " + ("a" * 10000))


def test_calls_out_lisp_family_strict():
    """
    Epic #3264 Phase 3: Validate the lisp-family paradigm (scheme): the callee
    is the first symbol after an open paren, including lisp punctuation names.
    """
    assert CALLS_OUT_LISP_FAMILY.groups == 1

    # 1. Valid matches, including nested application and punctuation identifiers.
    assert CALLS_OUT_LISP_FAMILY.findall("(probe-branch argv)") == ["probe-branch"]
    assert CALLS_OUT_LISP_FAMILY.findall("(probe-io (probe-branch x))") == [
        "probe-io",
        "probe-branch",
    ]
    assert CALLS_OUT_LISP_FAMILY.findall("(null? lst)") == ["null?"]
    assert CALLS_OUT_LISP_FAMILY.findall("(set! counter 1)") == ["set!"]
    assert CALLS_OUT_LISP_FAMILY.findall("( display x)") == ["display"]

    # 2. Negatives: numbers and bare words are not applications.
    assert CALLS_OUT_LISP_FAMILY.findall("(123 x)") == []
    assert CALLS_OUT_LISP_FAMILY.findall("probe-branch argv") == []
    assert CALLS_OUT_LISP_FAMILY.findall("()") == []

    # 3. ReDoS immunity: open paren, huge whitespace run, then a non-symbol.
    assert_redos_immune(CALLS_OUT_LISP_FAMILY, "(" + (" " * 10000) + "1")
    assert_redos_immune(CALLS_OUT_LISP_FAMILY, "(" + ("a" * 10000))


def test_calls_out_command_position_strict():
    """
    Epic #3264 Phase 3: Validate the command-position paradigm
    (tcl/powershell/livecode): the callee is the first word on a line.
    """
    assert CALLS_OUT_COMMAND_POSITION.groups == 1

    # 1. Valid matches: bare commands, indented commands, interior-colon tcl
    # namespaces, powershell Verb-Noun.
    sample = "probe_branch $argv\n    probe_io $argv\nns::probe_risk 1\nInvoke-Probe -Arg 1\n"
    assert CALLS_OUT_COMMAND_POSITION.findall(sample) == [
        "probe_branch",
        "probe_io",
        "ns::probe_risk",
        "Invoke-Probe",
    ]

    # 2. Negatives: comment lines, variable lines and leading-:: qualified
    # calls (documented recall gap) are not captured.
    assert CALLS_OUT_COMMAND_POSITION.findall("# probe_branch\n") == []
    assert CALLS_OUT_COMMAND_POSITION.findall("$var = 1\n") == []
    assert CALLS_OUT_COMMAND_POSITION.findall("::global_probe 1\n") == []

    # 3. Statement keywords in command position ARE captured -- filtering them
    # is the consuming language's calls_out_ignore contract, not the regex's.
    assert CALLS_OUT_COMMAND_POSITION.findall("if {$x} {\n") == ["if"]

    # 4. ReDoS immunity: long indentation run, then a non-word; long word run.
    assert_redos_immune(CALLS_OUT_COMMAND_POSITION, (" " * 10000) + "$")
    assert_redos_immune(CALLS_OUT_COMMAND_POSITION, "a" * 10000)
