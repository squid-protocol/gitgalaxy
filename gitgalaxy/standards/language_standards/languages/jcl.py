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
    # #2806: JCL is the one corpus language whose callable units cannot be
    # invoked by name. A job's EXEC steps -- what `func_start` above extracts
    # -- run in the order they are written, top to bottom, on every
    # submission; the language has no syntax that references a step to make
    # it run. (The unit that CAN be named is the PROC, which the `api` rule
    # counts and the slicer does not extract as a function.) So the
    # `unreferenced_by_name` census, which is a name-reference test and can
    # be nothing else from one file's text, is unanswerable here and is not
    # computed. Measured on the language-crucible before the declaration:
    # 334 of 376 steps (89%) read unreferenced, and the 42 that cleared did
    # so by ACCIDENT rather than by being invoked -- a step named CREATE
    # beside inline SQL, COBOL beside the word in a DSN, CRTABS repeated
    # seven times in one job. Both the 89% and the 11% were noise.
    #
    # This is a TOP-LEVEL language property, not a rule: `language_lens.py`'s
    # regex pre-compiler compiles every STRING value inside `rules` (a
    # defensive guard for definitions loaded from external JSON), so
    # "positional" would arrive at the detector as `re.compile("positional")`
    # and silently read as "not positional".
    "invocation_model": "positional",
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
        # Danger (execution of arbitrary programs). #2751: the rule used to be a
        # bare `PGM=<anything>`, which counted every step -- running a program
        # is what a JCL step IS, so the metric read "how many steps name a
        # program" rather than "how many steps execute something arbitrary".
        # On the language-crucible corpus that was 188 hits over 376 EXEC
        # statements: IKJEFT01 60, IEFBR14 26 (a program that does NOTHING --
        # run only for its DD allocation/deletion side effects), IDCAMS 16,
        # compilers and the linker 26, copy utilities 12, application programs
        # 38. A compile-link-go job scored three high-risk executions for
        # compiling. No other language's high_risk_execution counts "runs a
        # command" (shell/dockerfile/python count eval/exec/os.system, not every
        # command line), so the same planted intent read differently in JCL.
        # Narrowed to the programs whose purpose is to execute CALLER-SUPPLIED
        # commands: TSO/E batch (IKJEFT01 and its IKJEFT1A/IKJEFT1B variants,
        # which run whatever SYSTSIN carries -- TSO commands, CLISTs, REXX, DB2
        # DSN RUN PROGRAM), the z/OS UNIX shell and program launchers
        # (BPXBATCH/BPXBATSL/BPXBATA2/BPXBATA8, AOPBATCH), the REXX
        # interpreter (IRXJCL) and batch SDSF (its ISFIN stream issues MVS
        # operator commands). Compilers, copy/catalog utilities and IEFBR14 are
        # steps, not arbitrary execution; IDCAMS/IEHPROGM/ADRDSSU are
        # destructive-capable utilities but execute a fixed command language,
        # so they are left out on the same reasoning that keeps `rm` (not
        # `rm -rf /`) out of shell's rule. Unanchored like the other operand
        # rules: PGM= can sit on a `//` continuation line (the #2482 shape).
        "high_risk_execution": re.compile(
            r"\bPGM=(?:IKJEFT01|IKJEFT1[AB]|BPXBATCH|BPXBATSL|BPXBATA[28]|AOPBATCH|IRXJCL|SDSF)\b",
            re.I,
        ),
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
        # #2748: a cataloged or in-stream procedure is JCL's callable surface --
        # `//name PROC` declares what `EXEC name` / `EXEC PROC=name` in other
        # members invoke, which is the api contract's definition (a declaration
        # that makes a named unit visible outside the file it is declared in;
        # docs/api_rule_contract.md, fallback family). On the language-crucible
        # corpus 185 of the 376 EXEC statements invoke a procedure and 13
        # members declare one (10 of them in the member's first seven lines --
        # the member IS the procedure). Corollary 1 keeps the call site out:
        # `EXEC name` is a reference. Name optional like the other statement
        # rules (a cataloged PROC statement may be unnamed); `PEND` only closes
        # an in-stream proc and is not a second declaration. A PROC that carries
        # parameter defaults (`//BATCH PROC MEMBER=`) also matches args' `PROC`
        # alternative -- a declaration with its parameter list, the same
        # api+args pair every `def f(x)` produces.
        "api": re.compile(r"^[ \t]*//([A-Za-z0-9_#$@]*)[ \t]+PROC\b", re.M | re.I),
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
        # #2733: dataset disposition IS z/OS's serialization primitive.
        # `DISP=OLD` and `DISP=MOD` request an exclusive system ENQ on the
        # dataset; `DISP=SHR` requests shared access. In a batch shop that is
        # the construct engineers reason about when two jobs contend for a
        # resource -- a lock acquisition declared in the job deck -- which is
        # what sync_locks measures through each language's own idiom elsewhere
        # (cobol's `EXEC CICS ENQ`, abap's `ENQUEUE_`/`DEQUEUE_`, solidity's
        # `nonReentrant`).
        # Narrowed to OLD/MOD deliberately: SHR is the shared-access default
        # every job asks for, and NEW is an allocation rather than contention
        # over an already-existing resource -- neither declares a
        # serialization decision. On the language-crucible corpus that is 48
        # hits across 15 of 186 files, ~9% of the 525 `DISP=` occurrences; of
        # the remaining 477, 429 are `DISP=SHR` and 48 allocate (`DISP=(NEW,`,
        # or an omitted first positional -- `DISP=(,PASS)` -- that defaults to
        # it).
        # The residual overlap with `io` (which counts the bare `DISP=`
        # keyword) is accepted, not avoided. #2610 rejected a `cleanup` rule on
        # `DISP=(...,DELETE/CATLG)` because a second-positional disposition
        # rides along on essentially every `DISP=`, so that rule would have
        # re-counted the whole operand; this shape is a small, semantically
        # distinct subset instead. The engine already tolerates deliberate
        # overlaps where the meanings genuinely differ -- jcl's own
        # `COND=((4,LT),EVEN)` counts safety AND safety_bypasses, and haskell's
        # `finally` counts cleanup and safety.
        # Unanchored like the other operand rules (io/safety/telemetry): a DD
        # statement's DISP= routinely sits on a `//` continuation line rather
        # than the line carrying the ddname, the same real-corpus shape the
        # args rule's #2482 note documents.
        "sync_locks": re.compile(r"\bDISP=\(?(?:OLD|MOD)\b", re.I),
        # #2749: DELETE as a dataset's normal-termination disposition is JCL's
        # teardown idiom -- `//S EXEC PGM=IEFBR14` + `DD DSN=X,DISP=(MOD,DELETE,
        # DELETE)` is THE way a batch job deletes a dataset (a no-op program run
        # purely for the allocation side effect), and `DISP=(OLD,DELETE)` on a
        # `&&TEMP` dataset frees it once the step is done. That is what cleanup
        # measures through each language's own idiom elsewhere (shell's `rm -f`
        # / `trap ... EXIT`, dockerfile's `apt-get clean`, yaml's `docker
        # compose down`, #2647).
        # #2610 declined this for the `io` overlap; #2733 (PR #2742) reversed
        # that posture for the same operand's OLD/MOD subset, and the same
        # measurement applies here: on the language-crucible corpus 36 of 533
        # `DISP=` occurrences (13 of 186 files) carry DELETE in the
        # normal-termination position. Narrowed to that position deliberately:
        # the abnormal-termination positional (`DISP=(NEW,CATLG,DELETE)`, 12
        # more) is a conditional disposition on an ALLOCATION -- the step's
        # intent is to create the dataset and keep it, and only discard it if
        # the step abends -- so it is excluded, the way `DISP=SHR`/`NEW` stay
        # out of sync_locks. `[^,()\n]*` for the status positional accepts the
        # omitted form `DISP=(,DELETE)` (a scratch dataset created and dropped
        # in one step) and cannot cross a newline or a paren, so the scan is
        # bounded to one operand (ReDoS-safe: the class excludes `,`, so the
        # comma partitions at exactly one position).
        # The overlap is accepted, not avoided, on #2742's terms: every hit is
        # also an `io` hit (the DD's `DSN=`; `DISP=(` itself does not match
        # io's `\bDISP=\b` -- no word boundary between `=` and `(`), and the
        # `(OLD,DELETE)` / `(MOD,DELETE,DELETE)` forms are also sync_locks hits,
        # because they hold an exclusive ENQ on the dataset they then drop.
        # Pinned by test_jcl_cleanup_overlaps_io_and_sync_locks_by_design.
        "cleanup": re.compile(r"\bDISP=\([^,()\n]*,[ \t]*DELETE\b", re.I),
        "ui_framework": None,
        "closures": None,
        # #2750: JCL does have a scoped-vs-global distinction, in three places:
        # `//JOBLIB DD` is the program search library for EVERY step of the job
        # (its step-scoped twin, `//STEPLIB DD`, applies to one step and is not
        # counted -- crucible: JOBLIB in 32 files, STEPLIB 70 lines in 59); a
        # `// SET SYM=value` symbol is readable by every later statement in the
        # job (its scoped twin is a `PROC` parameter -- SET 39 lines in 12
        # files); `// EXPORT SYMLIST=` makes symbols visible inside in-stream
        # data (2). That is the global-vs-local pair globals measures elsewhere
        # (a python module-level name vs a def-local, dockerfile's image-wide
        # `ENV` vs a RUN-local export, yaml's `${{ env.X }}`).
        # SET is also `state_mutation`, and that is dockerfile's `ENV` shape
        # exactly -- dual globals + state_mutation, ledgered in the rosetta
        # corpus as batch4-dual-keyword-overlaps: a declaration that creates a
        # job-wide symbol is both the creation of global state and a mutation
        # of it. JOBLIB's DD line is also an `io` hit (its DSN) and a
        # `_dependency_capture` edge, which is right -- a JOBLIB is a dependency
        # of every step. Same anchoring as state_mutation (a real statement
        # line, never inline SYSIN payload); the JOBLIB alternative is named
        # exactly so a `//JOBLIBX` or `//SYSPROC` ddname cannot match.
        "globals": re.compile(
            r"^[ \t]*//JOBLIB[ \t]+DD\b"
            r"|^[ \t]*//[A-Za-z0-9_#$@]*[ \t]+(?:SET[ \t]+[A-Za-z0-9_#$@]+=|EXPORT[ \t]+SYMLIST\b)",
            re.M | re.I,
        ),
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
        # #2732: the other half of the #2610 leftover. Turning a statement's `//`
        # into `//*` is THE way JCL comments a step out -- 13 of the 443 licensed
        # .jcl/.prc files in the pool do it (16 occurrences), including whole JOB
        # cards -- but until #2610 routed `//*` lines into comment_analysis the
        # stream was structurally empty, so #2610 added the debt/ownership rules
        # and never came back for this one.
        # The operand guard (a keyword must be followed by operand-shaped text,
        # not prose) is load-bearing, not decoration: banner comments in real
        # decks open with these same keywords as English words. Measured in
        # cics-genapp's CICSTS56.jcl, which contains BOTH shapes -- `//* SET THE
        # RETURN CODE TO CONTROL...` and `//* EXECUTE DUMP UTILITY PROGRAM...`
        # (prose, excluded: "THE" is not `NAME=` and "EXECUTE" leaves no space
        # after `EXEC`) sitting a few lines from `//*        DD DSN=CSQ901.
        # SCSQLOAD,DISP=SHR` (a genuinely commented-out DD, matched). A bare
        # `(?:EXEC|DD|JOB|SET|INCLUDE)\b` would have counted all of them.
        # ReDoS: the name class excludes space/tab, so `[A-Za-z0-9_#$@]*[ \t]+`
        # partitions at exactly one position -- no ambiguity to backtrack over.
        "dead_code": re.compile(
            r"^//\*[A-Za-z0-9_#$@]*[ \t]+"
            r"(?:EXEC[ \t]+\S|DD[ \t]+\S|JOB[ \t]*[,(]|SET[ \t]+[A-Za-z0-9_#$@]+=|INCLUDE[ \t]+MEMBER=)",
            re.M | re.I,
        ),
        # #2732: the generic `[SPEC-n]`/`[spec]`/`[audit]` traceability tag, but
        # anchored to `//*` rather than copied bare from python/go/java/js.
        # Anchoring matters because comment rules are NOT comment-stream-only:
        # coding_analysis applies every non-underscore rule to the code stream
        # and comment_analysis then adds a second pass over the comments, so an
        # unanchored bracket rule also scores brackets in code -- here, whatever
        # sits in an inline `//SYSIN DD *` payload, which is arbitrary non-JCL
        # text. `//*` can never appear in jcl's code stream (prism strips those
        # lines out), so the anchor makes the rule structurally comment-only.
        # Same anchoring precedent as this file's own `ownership` rule.
        # `\b` after the alternation keeps the bare `spec` branch off "specified"
        # / "species" -- see yaml.py's copy of this rule for the pool evidence.
        "spec_exposure": re.compile(
            r"^//\*[^\n\[]{0,200}\[(?:[ \t]*SPEC[ \t]*-[ \t]*\d{1,10}|spec|audit)\b[^\]\n]{0,300}\]",
            re.M | re.I,
        ),
    },
}
