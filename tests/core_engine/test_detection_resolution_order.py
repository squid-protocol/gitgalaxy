# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

"""Detection resolution-order pins (#3118).

Both content-evidence loops in `_tier_2_fingerprint_check` iterate
`self.languages.items()`, so `LANGUAGE_DEFINITIONS` insertion order silently
arbitrates ties -- for `internal_discriminator`s sharing an extension, and
(before #3116) for shebang triggers. Nothing asserted the intended outcome, so
adding or reordering a language could change classification with no test
failing. The `.cmd` case from #2504 is the worked example: batch's
discriminator is deliberately checked before rexx's, and that requirement
existed only as a comment in `batch.py`.

These tests pin the resolution surface three ways:
  1. the claimant list per contested extension, in registry order (a literal,
     so adding/reordering a claimant is an explicit, reviewable test diff);
  2. the invariant that any extension with two or more claimant languages is
     registered in `COLLISION_FREQUENCIES` (an unregistered collision lets
     Tier 1 lock on the last registrant, and can raise a FALSE identity
     conflict against the other claimant's discriminator -> Tier 5);
  3. the behavioural outcome -- realistic content for each claimant resolving
     to that claimant -- which is what the order actually exists to protect.
"""

from collections import defaultdict

import pytest

from gitgalaxy.standards.language_lens import (
    LanguageDetector,
    _shebang_interpreter,
    _shebang_trigger_matches,
)
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS, LENS_CONFIG

# Registry order, captured 2026-09-17 on main (64 languages, post-#2504).
# "D" = the language declares an internal_discriminator; "-" = it does not.
# Order within each list IS the registry iteration order and is load-bearing
# wherever two entries both carry "D".
_EXPECTED_CLAIMANTS: dict[str, list[tuple[str, str]]] = {
    ".asm": [("assembly", "-"), ("hlasm", "D")],
    ".c": [("c", "-")],
    ".cmd": [("batch", "D"), ("rexx", "D")],
    ".cshtml": [("csharp", "-"), ("html", "-")],
    ".ddl": [("sqlite", "-"), ("db2_sql", "D")],
    ".dml": [("sqlite", "-"), ("db2_sql", "D")],
    ".h": [("c", "-"), ("objective-c", "D")],
    ".inc": [("cpp", "-"), ("c", "-"), ("php", "-"), ("fortran", "-"), ("assembly", "-")],
    ".m": [("matlab", "D"), ("objective-c", "D")],
    ".map": [("bms", "D")],
    ".py": [("python", "D"), ("embedded_python", "D")],
    ".sql": [("sqlite", "-"), ("db2_sql", "D")],
    ".y": [("c", "-"), ("yacc", "D")],
}

# The extensions where TWO claimants both carry a discriminator, i.e. where
# registry order decides which content check runs first. Kept as its own pin
# because this is the set that needs re-adjudicating when a language is added.
_ORDER_CRITICAL_EXTENSIONS = {".cmd", ".m", ".py"}


def _claimants_in_registry_order(ext: str) -> list[tuple[str, str]]:
    return [
        (lang_id, "D" if data.get("internal_discriminator") else "-")
        for lang_id, data in LANGUAGE_DEFINITIONS.items()
        if ext in data.get("extensions", [])
    ]


def test_contested_extension_set_is_pinned():
    assert set(LENS_CONFIG["COLLISION_FREQUENCIES"]) == set(_EXPECTED_CLAIMANTS), (
        "COLLISION_FREQUENCIES changed; update _EXPECTED_CLAIMANTS in the same commit "
        "so the new/removed collision is reviewed, not absorbed"
    )


@pytest.mark.parametrize("ext", sorted(_EXPECTED_CLAIMANTS))
def test_claimants_and_their_order_are_pinned(ext):
    assert _claimants_in_registry_order(ext) == _EXPECTED_CLAIMANTS[ext], (
        f"the claimant list or registry order for {ext!r} moved. Both matter: order decides "
        f"which internal_discriminator is consulted first in _tier_2_fingerprint_check"
    )


def test_order_critical_extensions_are_pinned():
    """Which extensions have competing discriminators, derived from the registry."""
    actual = {ext for ext, claims in _EXPECTED_CLAIMANTS.items() if sum(1 for _, d in claims if d == "D") > 1}
    assert actual == _ORDER_CRITICAL_EXTENSIONS


def test_every_multi_claimant_extension_is_a_registered_collision():
    """An unregistered collision is a latent false-Tier-5 trap.

    `_tier_1_metadata_lock` refuses to lock a COLLISION_FREQUENCIES member on
    extension alone. For an UNregistered extension claimed by two languages it
    locks the last registrant (`_calibrate_lookup_maps` overwrites), and if the
    other claimant's discriminator then matches the content, ext_lang !=
    shebang_lang and the Identity Conflict Trap forces the file to Tier 5 --
    the #3116 failure shape, reached by a different route.
    """
    claims: dict[str, set[str]] = defaultdict(set)
    for lang_id, data in LANGUAGE_DEFINITIONS.items():
        for ext in data.get("extensions", []):
            claims[ext.lower()].add(lang_id)

    unregistered = {
        ext: sorted(langs)
        for ext, langs in claims.items()
        if len(langs) > 1 and ext not in LENS_CONFIG["COLLISION_FREQUENCIES"]
    }
    assert unregistered == {}, (
        f"these extensions are claimed by multiple languages but are not registered collisions: {unregistered}"
    )


# Realistic content per claimant -- the behavioural half. Each snippet is the
# shape a real file of that language has, not a synthetic string built to match.
_COLLISION_CONTENT: dict[str, str] = {
    "hlasm": "ACCTPGM  CSECT\n         USING ACCTPGM,15\n         LA    1,4\n         BR    14\n         END\n",
    "assembly": "; x86-64 bootstrap\nsection .text\nglobal _start\n_start:\n    mov rax, 60\n    xor rdi, rdi\n    syscall\n",
    "rexx": "/* REXX */\nparse arg dsn\nsay 'starting'\nexit 0\n",
    "batch": "@echo off\r\nsetlocal\r\nset TARGET=build\r\nif exist out.txt del out.txt\r\ngoto :done\r\n:done\r\n",
    "db2_sql": "--#SET TERMINATOR @\nCREATE PROCEDURE P1() LANGUAGE SQL\nBEGIN\n  DECLARE v INT;\n  SET v = 1;\nEND@\n",
    "sqlite": "PRAGMA foreign_keys=ON;\nCREATE TABLE t (id INTEGER PRIMARY KEY, n TEXT);\nINSERT INTO t VALUES (1,'a');\n",
    "c": '#include <stdio.h>\nint add(int a, int b) { return a + b; }\nint main(void) { printf("%d", add(1,2)); return 0; }\n',
    "objective-c": (
        "#import <Foundation/Foundation.h>\n@interface Foo : NSObject\n- (void)doThing:(NSString *)s;\n@end\n"
        '@implementation Foo\n- (void)doThing:(NSString *)s { NSLog(@"%@", s); }\n@end\n'
    ),
    "matlab": "%% Analysis\nfunction r = compute(x)\n  r = sum(x) / numel(x);\nend\n",
    "python": "import os\n\n\ndef main():\n    for k in os.environ:\n        print(k)\n\n\nif __name__ == '__main__':\n    main()\n",
    "embedded_python": (
        "from machine import Pin\nimport utime\n\nled = Pin(2, Pin.OUT)\nwhile True:\n"
        "    led.value(1)\n    utime.sleep_ms(500)\n"
    ),
    "yacc": "%token NUM\n%%\nexpr: expr '+' NUM { $$ = $1 + $3; }\n    | NUM\n    ;\n%%\n",
}

# (extension, content-language, expected winner). Only the pairs whose correct
# answer is independently verifiable from the content are asserted; `.inc`
# (five claimants, no discriminators) and `.cshtml` are deliberately omitted --
# they resolve through the Tier 3 lexical scan, and pinning a winner there
# would pin scan tuning rather than a routing decision.
_COLLISION_CASES = [
    (".asm", "hlasm", "hlasm"),
    (".asm", "assembly", "assembly"),
    (".cmd", "rexx", "rexx"),
    (".cmd", "batch", "batch"),
    (".sql", "db2_sql", "db2_sql"),
    (".sql", "sqlite", "sqlite"),
    (".ddl", "db2_sql", "db2_sql"),
    (".ddl", "sqlite", "sqlite"),
    (".dml", "db2_sql", "db2_sql"),
    (".dml", "sqlite", "sqlite"),
    (".h", "c", "c"),
    (".h", "objective-c", "objective-c"),
    (".m", "matlab", "matlab"),
    (".m", "objective-c", "objective-c"),
    (".py", "python", "python"),
    (".py", "embedded_python", "embedded_python"),
    (".y", "yacc", "yacc"),
    (".y", "c", "c"),
]


@pytest.mark.parametrize(("ext", "content_lang", "expected"), _COLLISION_CASES)
def test_contested_extension_resolves_to_the_content_language(ext, content_lang, expected):
    detector = LanguageDetector(LANGUAGE_DEFINITIONS, {})
    lang, _conf, _family = detector.focus(f"probe{ext}", _COLLISION_CONTENT[content_lang])
    assert lang == expected, f"{content_lang} content named probe{ext} resolved to {lang!r}"


# ==============================================================================
# SHEBANG RESOLUTION (#3116's fix, pinned so it cannot regress)
# ==============================================================================
def test_every_unambiguous_shebang_trigger_resolves_to_its_own_language():
    """Order-independence invariant.

    For every trigger declared by exactly one language, a shebang naming that
    interpreter must resolve to the declaring language. This asserts the
    property rather than the mechanism, so it holds regardless of registry
    order. It is also how the `deno`/`bun`/`csi` ambiguities below were found.
    """
    detector = LanguageDetector(LANGUAGE_DEFINITIONS, {})
    misrouted = []
    for lang_id, data in LANGUAGE_DEFINITIONS.items():
        for raw_trigger in data.get("shebangs", []):
            trigger = raw_trigger.rsplit("/", 1)[-1].lower()
            if trigger in detector._ambiguous_shebangs:
                continue
            resolved, kind = detector._tier_2_fingerprint_check(f"#!/usr/bin/{trigger}\n", "")
            if resolved != lang_id or kind != "Shebang":
                misrouted.append((raw_trigger, lang_id, resolved))
    assert misrouted == [], f"shebang triggers claimed by the wrong language: {misrouted}"


def test_ambiguous_shebang_triggers_are_pinned_and_non_discriminating():
    """A trigger two languages both claim yields NO shebang verdict.

    `deno` and `bun` run TypeScript and JavaScript alike; `csi` is both
    Chicken Scheme's interpreter and the C# script runner. Resolving such a
    trigger to either claimant makes the other claimant's files contradict
    their own extension and land at Tier 5. Measured before the fix:
    `.ts` + `#!/usr/bin/env deno run` and `.scm` + `#!/usr/bin/csi -s` both
    returned `undeterminable` with an "Identity Masking" anomaly flag.
    """
    detector = LanguageDetector(LANGUAGE_DEFINITIONS, {})
    assert detector._ambiguous_shebangs == {"deno", "bun", "csi"}, (
        "the set of non-discriminating shebang triggers moved; a new one means two languages "
        "now claim the same interpreter and the extension must be left to decide"
    )
    for trigger in sorted(detector._ambiguous_shebangs):
        resolved, kind = detector._tier_2_fingerprint_check(f"#!/usr/bin/env {trigger}\n", "")
        assert (resolved, kind) == (None, ""), f"{trigger!r} must not produce a shebang verdict, got {resolved!r}"


@pytest.mark.parametrize(
    ("path", "content", "expected"),
    [
        # Both claimants of an ambiguous trigger resolve by extension instead
        # of colliding -- neither is forced to Tier 5.
        ("a.ts", "#!/usr/bin/env deno run\nconst x: number = 1\n", "typescript"),
        ("b.js", "#!/usr/bin/env bun\nconst x = 1\n", "javascript"),
        ("c.scm", "#!/usr/bin/csi -s\n(display 1)\n", "scheme"),
        ("e.csx", "#!/usr/bin/csi\nvar x = 1;\n", "csharp"),
    ],
)
def test_ambiguous_trigger_files_are_not_forced_to_tier_5(path, content, expected):
    detector = LanguageDetector(LANGUAGE_DEFINITIONS, {})
    result = detector.inspect(path, content)
    assert result["lang_id"] == expected
    assert result["lock_tier"] != 5, f"{path} was forced into Absolute Distrust: {result['source_proof']}"
    assert result["anomaly_flags"] == []


def test_path_shaped_trigger_matches_its_interpreter():
    """tcl declares `bin/expect`; basename matching must still honour it.

    A path-shaped registry entry only worked under the old substring match by
    accident. Normalising triggers to a basename at boot keeps it working --
    and upgrades it, since `#!/usr/bin/expect` on a `.tcl` file now reaches
    Tier 0 consensus rather than extension-only Tier 2.
    """
    detector = LanguageDetector(LANGUAGE_DEFINITIONS, {})
    resolved, kind = detector._tier_2_fingerprint_check("#!/usr/bin/expect -f\nspawn ssh host\n", "")
    assert (resolved, kind) == ("tcl", "Shebang")


@pytest.mark.parametrize(
    ("shebang", "expected"),
    [
        # The six #3116 regressions: shell's "sh" and javascript's "node" used
        # to win these as substrings, contradicting the extension and forcing
        # a false Tier 5 "Identity Masking" verdict on ordinary scripts.
        ("#!/usr/bin/tclsh", "tcl"),
        ("#!/usr/bin/wish", "tcl"),
        ("#!/usr/bin/env jimsh", "tcl"),
        ("#!/usr/bin/env swift-sh", "swift"),
        ("#!/usr/bin/env racketsh", "scheme"),
        ("#!/usr/bin/env ts-node", "typescript"),
        # Controls: the short triggers must still win their own interpreters.
        ("#!/bin/sh", "shell"),
        ("#!/bin/bash", "shell"),
        ("#!/bin/sh -e", "shell"),
        ("#!/usr/bin/env node", "javascript"),
        ("#!/usr/bin/pwsh", "powershell"),
        ("#!/usr/bin/perl -w", "perl"),
        # Version suffixes belong to the same interpreter; a different word does not.
        ("#!/usr/bin/env python3", "python"),
        ("#!/usr/bin/python3.12", "python"),
        ("#!/usr/bin/env -S python3 -u", "python"),
        ("#!/usr/bin/micropython", "embedded_python"),
    ],
)
def test_shebang_interpreter_routing(shebang, expected):
    detector = LanguageDetector(LANGUAGE_DEFINITIONS, {})
    resolved, kind = detector._tier_2_fingerprint_check(f"{shebang}\nprint(1)\n", "")
    assert resolved == expected, f"{shebang!r} resolved to {resolved!r}"
    assert kind == "Shebang"


@pytest.mark.parametrize(
    ("first_line", "expected"),
    [
        ("#!/bin/bash", "bash"),
        ("#!/usr/bin/tclsh", "tclsh"),
        ("#!/usr/bin/env python3", "python3"),
        ("#!/usr/bin/env -S python3 -u", "python3"),
        ("#!/usr/bin/env VAR=1 python3", "python3"),
        ("#!/usr/bin/env ts-node --esm", "ts-node"),
        ("#!/bin/sh -e", "sh"),
        ("#!/usr/bin/env", ""),
        ("#!", ""),
        ("not a shebang", ""),
    ],
)
def test_shebang_interpreter_extraction(first_line, expected):
    assert _shebang_interpreter(first_line) == expected


@pytest.mark.parametrize(
    ("trigger", "interpreter", "matches"),
    [
        ("python", "python", True),
        ("python", "python3", True),
        ("python", "python3.12", True),
        ("python", "micropython", False),  # a different word, not a version
        ("sh", "sh", True),
        ("sh", "tclsh", False),
        ("sh", "swift-sh", False),
        ("node", "ts-node", False),
        ("go", "cargo", False),
        ("rexx", "rexx64", True),
        ("perl", "perl5.36", True),
        ("", "python", False),
        ("python", "", False),
    ],
)
def test_shebang_trigger_matching_rule(trigger, interpreter, matches):
    assert _shebang_trigger_matches(trigger, interpreter) is matches


def test_internal_signature_resolution_is_not_reported_as_a_shebang():
    """#3116 follow-up: `source_proof` must name the mechanism that fired.

    A file resolved by its internal discriminator carries no `#!` at all, and
    used to be reported as `Single Indicator (Shebang)`.
    """
    detector = LanguageDetector(LANGUAGE_DEFINITIONS, {})
    result = detector.inspect("acct.asm", _COLLISION_CONTENT["hlasm"])
    assert result["lang_id"] == "hlasm"
    assert "Internal Signature" in result["source_proof"]
    assert "Shebang" not in result["source_proof"]


# ==============================================================================
# #3133 / #3134: two fixes found by the #3117 detection-accuracy harness
# ==============================================================================
_TCL_TRAMPOLINE = (
    "#!/bin/sh\n"
    "# the next line restarts using tclsh \\\n"
    'exec tclsh "$0" ${1+"$@"}\n'
    "#\n"
    "set testdir [file dirname $argv0]\n"
    "source $testdir/tester.tcl\n"
)


def test_trampoline_bootstrap_is_not_an_identity_conflict():
    """#3133: `#!/bin/sh` + `exec tclsh "$0"` is the canonical Tcl portability
    idiom (this snippet is sqlite's own test-harness header). The shebang
    really IS `sh`, so it legitimately contradicts the `.tcl` extension -- and
    the Identity Conflict Trap used to refuse the file at Tier 5 with an
    "Identity Masking" flag, i.e. report a stock sqlite script as masquerading.
    """
    detector = LanguageDetector(LANGUAGE_DEFINITIONS, {})
    result = detector.inspect("speedtest.tcl", _TCL_TRAMPOLINE)
    assert result["lang_id"] == "tcl"
    assert result["lock_tier"] != 5
    assert result["anomaly_flags"] == []
    assert "Trampoline Exec" in result["source_proof"]


def test_trampoline_suppression_requires_the_extension_to_claim_the_interpreter():
    """The escape hatch is narrow: only an interpreter the EXTENSION's own
    language claims clears the conflict, so a genuinely mislabelled executable
    still trips the trap."""
    detector = LanguageDetector(LANGUAGE_DEFINITIONS, {})
    # A .tcl that re-execs python is NOT a Tcl trampoline.
    result = detector.inspect("suspicious.tcl", '#!/bin/sh\nexec python3 "$0" "$@"\nprint(1)\n')
    assert result["lock_tier"] == 5
    assert result["lang_id"] == "undeterminable"


def test_trampoline_needs_a_generic_shell_shebang():
    """A conflict raised against a SPECIFIC interpreter is never a bootstrap:
    only the shell family is a portable-launcher vehicle."""
    from gitgalaxy.standards.language_lens import _BOOTSTRAP_SHELL_LANGS, _trampoline_interpreter

    assert _BOOTSTRAP_SHELL_LANGS == {"shell"}
    assert _trampoline_interpreter(_TCL_TRAMPOLINE) == "tclsh"
    assert _trampoline_interpreter("#!/bin/sh\necho hi\n") == ""
    # bounded to the opening lines -- an `exec` deep in the body is not a bootstrap
    assert _trampoline_interpreter("#!/bin/sh\n" + "\n" * 40 + "exec tclsh\n") == ""


@pytest.mark.parametrize(
    ("name", "expected", "why"),
    [
        ("BUILD.mk", "makefile", "a real extension outranks the Bazel BUILD prefix"),
        ("Makefile.pre.in", "makefile", "a TEMPLATE extension does not outrank the Makefile prefix"),
        ("Makefile", "makefile", "an exact filename match still wins outright"),
    ],
)
def test_prefix_anchor_yields_to_a_real_extension_but_not_a_template_one(name, expected, why):
    """#3134: `BUILD.mk` locked to python at Tier 1 via `Prefix Anchor (BUILD)`
    before its own `.mk` was consulted. The fix is scoped so that a template
    wrapper (`.in`, whose real language is whatever sits inside) does NOT
    outrank a prefix -- otherwise `Makefile.pre.in`, which IS Makefile syntax,
    would follow `.in` to m4."""
    detector = LanguageDetector(LANGUAGE_DEFINITIONS, {})
    sample = "CC = gcc\nall: main.o\n\t$(CC) -o app main.o\n"
    lang, _conf, _family = detector.focus(name, sample)
    assert lang == expected, why
