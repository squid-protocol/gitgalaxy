# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

import re
from typing import Any

from .._shared_patterns import GLOBAL_FRAGILE_DEBT, GLOBAL_PLANNED_DEBT

DEFINITION: dict[str, Any] = {
    "_meta": {
        "target_version": "IBM z/OS JCL",
        "status": "production",
    },
    "extensions": [".jcl", ".prc", ".bms"],
    "exact_matches": [],
    "discriminators": [".cbl", ".cob", ".cpy"],
    "shebangs": [],
    "lexical_family": "line_exclusive",
    "rules": {
        # Control flow in JCL (IF/THEN/ELSE/ENDIF)
        "branch": re.compile(r"^[ \t]*//[A-Za-z0-9_#$@]*[ \t]+(?:IF|ELSE|ENDIF)\b", re.M | re.I),
        # Extract arguments from EXEC PARM= strings or PROC symbolics definitions.
        # #2482: PARM= routinely sits on a JCL continuation line, not the EXEC
        # line itself -- a trailing comma on a `//` statement line means "this
        # statement keeps going on the next `//` line," and real corpus JCL
        # chains this more than once before PARM= appears (cics-genapp's
        # CICSTS56.jcl: EXEC line ends in a comma, then a COND=(...) continuation
        # line ALSO ends in a comma, and only the third line carries PARM=).
        # `(?:\n//[ \t]*(?:[^\n]*,[ \t]*\n//[ \t]*){0,7})?` models this: the whole
        # thing is optional (same-line PARM=, the common case, is untouched), but
        # once triggered it crosses at least one continuation boundary
        # (`\n//[ \t]*`) and then allows up to 7 more hops, each of which must
        # itself end in a real trailing comma (`[^\n]*,` -- greedy, so it lands on
        # the LAST comma on that line, the actual continuation indicator, not an
        # incidental earlier one) before crossing again. Every repeated unit is
        # bounded to a single physical line (`[^\n]*` cannot cross a newline), so
        # this cannot backtrack catastrophically even on adversarial input -- see
        # test_jcl_args_parm_continuation_line_regression's ReDoS case. The value
        # capture itself (`\([^)]*\)` / `'...'`) already spanned newlines before
        # this fix (`[^)]*`/`[^']*` don't exclude `\n`), so a PARM=(...) that
        # keeps going across further continuation lines (cics-genapp's
        # defdrep.jcl, 5 more lines after the opening paren) is captured whole --
        # EXCEPT when the value itself contains a nested, unquoted `(...)` (e.g.
        # `'AMODE(31)'` inside a larger PARM=(...) list), where the capture still
        # stops at that inner `)` -- a separate, pre-existing limitation this
        # issue doesn't attempt to fix (nested-paren balancing isn't expressible
        # in a single bounded regex pass the way this engine requires).
        "args": re.compile(
            r"^[ \t]*//[A-Za-z0-9_#$@]*[ \t]+"
            r"(?:EXEC(?:[ \t].*?)?,[ \t]*(?:\n//[ \t]*(?:[^\n]*,[ \t]*\n//[ \t]*){0,7})?"
            r"PARM=('(?:[^']|'')*'|\([^)]*\)|[^ \t\n,]+)"
            r"|PROC[ \t]+(\S.*))",
            re.M | re.I,
        ),
        # Structural boundaries (Any line starting with // and a command)
        # BUG FIX (2 issues): (1) the name segment was required (`+`), missing
        # the very common unnamed continuation-DD form (`//         DD DSN=...`,
        # concatenating a dataset onto the preceding DD with no ddname of its
        # own) -- a real, everyday JCL idiom, not an edge case. Name is now
        # optional (`*`). (2) the gap before the keyword was `\s+`, which
        # includes `\n` under re.M -- confirmed this lets a name on one line
        # falsely bind to a keyword starting a *different* line with no `//`
        # prefix of its own (e.g. "//STEP01\nEXEC PGM=FOO" incorrectly reads as
        # a real EXEC step). JCL statements don't span a physical line via bare
        # whitespace, so bounded to `[ \t]+` instead.
        "structural_boundaries": re.compile(
            r"^[ \t]*//[A-Za-z0-9_#$@]*[ \t]+(?:DD|INCLUDE|SET|PROC|PEND)\b", re.M | re.I
        ),
        # Functions (EXEC steps). Same `\s+` -> `[ \t]+` cross-line fix as above.
        # BUG FIX: stepname is optional (`*` not `+`), unnamed EXEC steps are valid.
        "func_start": re.compile(r"^[ \t]*//([A-Za-z0-9_#$@]*)[ \t]+EXEC\b", re.M | re.I),
        # Classes/Entities (JOB cards). Same `\s+` -> `[ \t]+` cross-line fix as above.
        "class_start": re.compile(r"^[ \t]*//([A-Za-z0-9_#$@]+)[ \t]+JOB\b", re.M | re.I),
        # Danger (Execution of arbitrary programs)
        "high_risk_execution": re.compile(r"\bPGM=[A-Za-z0-9_#$@]+\b", re.I),
        # I/O (Data Set Names and Sysouts)
        "io": re.compile(r"\b(DSN|DSNAME|SYSOUT|SYSPRINT|DISP=)\b", re.I),
        # #2610: JCL's error handling is the COND= operand -- a return-code
        # test deciding whether a step runs after a prior step's outcome.
        # Unanchored (like io's DISP=/PGM= operands) because COND= routinely
        # sits on a `//` continuation line, not the EXEC line itself (the same
        # real-corpus shape the args rule's #2482 note documents). The negative
        # lookahead keeps the plain bypass forms (COND=EVEN / COND=ONLY) out of
        # safety: those are the *absence* of a return-code test and belong to
        # safety_bypasses below. A combined form like COND=((4,LT),EVEN)
        # deliberately counts BOTH -- it carries a real RC test and a run-even-
        # after-abend bypass at once.
        "safety": re.compile(r"\bCOND=(?!(?:EVEN|ONLY)\b)", re.I),
        "api": None,
        # #2610: COND=EVEN ("run even if a prior step abended") and COND=ONLY
        # ("run only after an abend") execute a step in spite of upstream
        # failure -- JCL's native ignore-the-error idiom. Two alternatives:
        # the bare form, and the parenthesized combined form
        # (COND=((4,LT),EVEN)), whose scan is the bounded one-level-paren
        # idiom -- the two branches are disjoint on their first character
        # ("(" vs not) and the inner star sits inside literal parens, so no
        # position ever partitions ambiguously (ReDoS-safe), and neither
        # branch can cross a newline or escape the COND value's own parens to
        # reach an unrelated EVEN/ONLY later on the line.
        "safety_bypasses": re.compile(
            r"\bCOND=(?:EVEN|ONLY)\b|\bCOND=\((?:[^\n()]|\([^\n()]*\))*?\b(?:EVEN|ONLY)\b",
            re.I,
        ),
        # BUG FIX: unanchored -- `\bSET\s+NAME=` matched "SET" anywhere in the
        # file, including inline SYSIN card data (`//SYSIN DD *` ... `/*`) that
        # isn't a JCL statement at all (e.g. an embedded SQL/shell/config
        # payload that happens to contain "SET X=1"). Anchored to a real JCL
        # statement line, mirroring structural_boundaries' own SET handling;
        # both `\s+` gaps bounded to `[ \t]+` for the same cross-line reason.
        "state_mutation": re.compile(r"^[ \t]*//[A-Za-z0-9_#$@]*[ \t]+SET[ \t]+[A-Za-z0-9_#$@]+=", re.M | re.I),
        "concurrency": None,
        "ui_framework": None,
        "closures": None,
        "globals": None,
        "decorators": None,
        "generics": None,
        "comprehensions": None,
        "scientific": None,
        "reflection_metaprogramming": None,
        # BUG FIX: name segment was required (`+`); INCLUDE statements, like DD,
        # are commonly written unnamed (`//         INCLUDE MEMBER=...`). Name
        # now optional (`*`); `\s+` -> `[ \t]+` for the same cross-line reason as
        # structural_boundaries/func_start/class_start above.
        "import": re.compile(r"^[ \t]*//[A-Za-z0-9_#$@]*[ \t]+INCLUDE\b", re.M | re.I),
        # _dependency_capture was missing entirely for jcl (unlike nearly every
        # other language with a non-None `import`), so the dependency graph never
        # captured which member a JCL job/proc pulls in via INCLUDE. Captures the
        # MEMBER= name for the network/blast-radius graph. Also captures dataset
        # names in DD statements and JCLLIB orders, ignoring temporary/internal ptrs (&&, *).
        "_dependency_capture": re.compile(
            r"^[ \t]*//[A-Za-z0-9_#$@]*[ \t]+(?:INCLUDE[ \t]+MEMBER=([A-Za-z0-9_#$@]+)|JCLLIB[ \t]+ORDER=\(?([A-Za-z0-9_#$@.]+)\)?|DD[ \t]+(?:.*?[ \t,])?DSN(?:AME)?=(?!(?:&&|\*))([A-Za-z0-9_#$@.&()]+))",
            re.M | re.I,
        ),
        # BUG FIX: `\s+` before the capture group could cross a newline (re.M),
        # so an Author line with the value wrapped to the next physical line
        # captured garbage from that *different* line (including its own "//*"
        # prefix) instead of correctly failing to match. Bounded to `[ \t]+`.
        "ownership": re.compile(r"^//\*[ \t]*(?:Author|Created by|Maintainer):[ \t]+(.*)", re.I | re.M),
        # #2610: MSGLEVEL= (what the job log records: statements/allocations)
        # and MSGCLASS= (where the log goes) are JCL's observability dials --
        # the closest native equivalent of configuring a logger. Unanchored
        # like the other operand rules (JOB-card operands continue across `//`
        # lines the same way EXEC's do).
        "telemetry": re.compile(r"\bMSG(?:LEVEL|CLASS)=", re.I),
        "debug_prints": None,
        # #2610: comment-anchored debt markers. Dead rules before the #2610
        # prism fix (jcl's comment stream was always empty); now that `//*`
        # lines reach comment_analysis, a `//* TODO ...` banner in a real job
        # deck counts the same way it does in cobol. Shared global patterns,
        # same as cobol.py.
        "planned_debt": GLOBAL_PLANNED_DEBT,
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
    },
}
