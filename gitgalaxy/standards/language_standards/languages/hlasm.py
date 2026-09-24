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

# #2503: HLASM (IBM High Level Assembler) -- full z/Architecture assembler
# source, the language bms.py's mapset macros are a dialect of. An HLASM
# statement is name field (column 1), operation field, operand field, remarks;
# continuation is a non-blank column 72 with the line resuming at column 16.
#
# The name field: an ordinary symbol -- a letter (plus @#$) then alphanumerics,
# 63 characters max (HLASM Language Reference, "Symbols"). Conditional-assembly
# statements may instead carry a sequence symbol (`.SKIP`) or a SET symbol
# (`&X`) in the name field -- the macro-directive rules widen to those.
_ID = r"[A-Za-z0-9@#$]"
_NAME = r"[A-Za-z@#$]" + _ID + r"{0,62}"
# Statement position: "column 1 name-or-nothing, then blanks" (bms.py's shape).
# The name class contains no whitespace, so `{0,63}` + `[ \t]+` partitions at
# exactly one position (no backtracking ambiguity, how_to Rule 5/14).
_STMT = r"^" + _ID + r"{0,63}[ \t]+"
# An operation field ends at blanks or end-of-line, NEVER at `=`: a keyword
# operand on a continuation line (`               WAIT=YES`) sits in statement
# position too (empty name field + column-16 indent), and only this lookahead
# keeps it from reading as a WAIT statement. `\b` cannot do this job -- it
# fires happily between `WAIT` and `=`.
_OPEND = r"(?=[ \t]|$)"

# The CICS command-level vocabulary is cobol's/pli's verbatim (#2990): a CICS
# assembler program writes the same `EXEC CICS <verb>` the translator expands
# (into DFHECALL) that the COBOL and PL/I hosts write, so the three mainframe
# hosts count the same commands the same way.


DEFINITION: dict[str, Any] = {
    "_meta": {
        "target_version": "IBM High Level Assembler (HLASM) V1R6 for z/OS (z/Architecture)",
        "last_updated": "2026-09-16",
        "blueprint_version": "v6.3",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA (#2503): `.asm` and `.mac` (macro members) are
    # the issue's ask; `.hlasm` is IBM's own unambiguous convention (Z Open
    # Editor, zAppBuild, DBB). `.asm` is CONTESTED -- the x86/ARM `assembly`
    # profile claims it too -- so it joins COLLISION_FREQUENCIES
    # (_lens_config.py) and never locks at Tier 1 on extension alone; routing
    # resolves through the internal_discriminator below (Tier 2), the
    # mainframe-sibling ecosystem gravity (Tier 1.5), or the lexical scan.
    # #3477: IMS PSB / DBD generation sources are HLASM macro members (PSBGEN,
    # PCB, SENSEG, DBDGEN, SEGM, FIELD ...); nothing else claims `.psb` / `.dbd`.
    "extensions": [".asm", ".hlasm", ".mac", ".psb", ".dbd"],
    "exact_matches": [],
    # ECOSYSTEM ANCHORS (#2503's ask): the mainframe sources HLASM lives
    # beside -- the JCL that assembles and runs it, the COBOL/PL/I programs and
    # copybooks it is called from, the BMS maps it sends. `.mac` (its own macro
    # members) anchors a macro library beside its `.asm` consumers.
    "discriminators": [".mac", ".jcl", ".cbl", ".cob", ".cpy", ".pli", ".pl1", ".bms"],
    # TOXIC NEIGHBORS (#377's mechanism, bms's `.map` reasoning verbatim): an
    # `.asm` sitting beside NASM/MASM sources, linker scripts or a CMake build
    # is x86/ARM assembly, never z/Architecture -- ecosystem gravity must
    # collapse hlasm's claim there. (Tier 2's internal_discriminator still wins
    # for a real HLASM member wherever it lives; disqualifiers only gate the
    # gravity path.)
    "disqualifiers": [".nasm", ".masm", ".s", ".S", ".ld", "CMakeLists.txt"],
    # EXECUTION SIGNATURES: assembled by ASMA90; no interpreter shebang.
    "shebangs": [],
    # Collision resolution for `.asm` (the objective-c-vs-matlab `.m` / bms
    # `.map` mechanism): real HLASM carries CSECT/DSECT/USING/AMODE/RMODE (or
    # the CICS DFHEIENT/DFHEIRET pair, or a MEND closer -- MASM's is ENDM) in
    # operation-field position; x86/ARM assembly never does. Strictly consulted
    # for known extension collisions, never as a global scanner
    # (language_lens.py's Tier 2 guard). Reads RAW text, so a `*` comment line
    # can never satisfy the `^` name-field anchor.
    "internal_discriminator": re.compile(
        r"^"
        + _ID
        + r"{0,63}[ \t]+(?:CSECT|DSECT|RSECT|AMODE|RMODE|USING|LTORG|MEND|DFHEIENT|DFHEIRET)"
        + _OPEND
        + r"|^R[0-9]{1,2}[ \t]+EQU[ \t]+[0-9]{1,2}\b(?:[\s\S]*?^R[0-9]{1,2}[ \t]+EQU[ \t]+[0-9]{1,2}\b){2}",
        re.M | re.I,
    ),
    # Rationale (how_to Step 4 item 8): HLASM is fixed-form -- a `*` in column
    # 1 is a full-line comment and `.*` in column 1 is a macro comment; there
    # is no inline comment marker (trailing "remarks" are positional, not
    # delimited, and stay in the code stream as a known bound -- every rule
    # here anchors the operation field, so a remark can never satisfy one).
    # prism.py's `_strip_positional_comments` bms mode ('*' and '.*' only, no
    # column-7 check, no inline split -- built for exactly this syntax at
    # #2505) now covers hlasm too; the shared positional anchor set's
    # 'C'/'c'/'/'/'!' would erase any real statement whose column-1 name field
    # starts with one of them (`CHECKPT LR ...` -- the #1898 shape).
    "lexical_family": "positional_anchored",
    # #3225: the identifier lexicon of the `unreferenced_by_name` census
    # (docs/unreferenced_by_name_contract.md corollary 7, #3198). HLASM folds lower-case symbols
    # to upper case (COMPAT(NOCASE), the default). Measured: no crucible or keyword-rosetta unit
    # moves. TOP LEVEL, never inside `rules` (#2806).
    "identifier_case": "insensitive",
    # COPY members resolve to PDS members, which are case-insensitive.
    "case_insensitive_imports": True,
    # #3199: this language's import statement names a library MEMBER that the
    # compiler pastes into the importing compilation unit (HLASM `COPY`). A member is
    # source in this same language by construction, so when a copied name is
    # ambiguous the resolver only ever chooses a candidate in it, and drops the
    # edge when there is none. Without that, CBSA's `COPY BNK1CAM` -- a BMS
    # symbolic map, generated at build time and absent from the repository --
    # resolved to whichever same-named file happened to be nearest, which is the
    # map's own build JCL. Every other language keeps unconstrained
    # cross-language resolution (an HTML page importing a .css file).
    "imports_are_source_members": True,
    # #3477: IMS PSB / DBD macros become ims_gen_data rows (core/ims_gen.py) via
    # mainframe_boundary's `hlasm` dialect -- the #3200 boundary_extraction pattern.
    "boundary_extraction": "hlasm",
    # invocation_model: DEFAULT (by_name), deliberately unlike bms/jcl: HLASM
    # reaches the units func_start extracts by writing their names -- `L
    # R15,=V(SUBRTN)` + `BALR 14,15`, the CALL macro, and a DSECT is reached by
    # `USING dsectname,reg`. The #2866 census applies.
    "rules": {
        # Epic #3264: Explicitly declare the structural invocation paradigm
        "calls_out": re.compile(r"(?i)=V\(([A-Z@#$][\w@#$]*)\)"),
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # branch (#2822): the CONDITIONAL branch mnemonics -- branch-on-
        # condition and its extended mnemonics (BE/BNE/BH/BNL/... and register
        # forms), the relative J* family, branch-on-count and branch-on-index
        # loops (BCT/BCTR/BXH/BXLE and 64-bit forms), and the compare-and-
        # branch family (CIJ/CRJ/CLIJ/...). EXCLUDES unconditional transfers
        # (B/BR/J/BAL/BALR/BAS/BASR -- #2764 relocated assembly's identical
        # tokens to structural_boundaries; a call is not a decision) and
        # conditional ASSEMBLY (AIF is compile-time, macros' -- the pli %IF
        # split verbatim).
        "branch": re.compile(
            _STMT + r"(?:B(?:E|NE|H|NH|L|NL|Z|NZ|P|NP|M|NM|O|NO)R?"
            r"|BCR?|BRCT?G?"
            r"|J(?:E|NE|H|NH|L|NL|Z|NZ|P|NP|M|NM|O|NO)"
            r"|BCTG?R?|BXLEG?|BXHG?"
            r"|C(?:L?G?)(?:IJ|RJ|IB|RB))" + _OPEND,
            re.M | re.I,
        ),
        # args (#2773 fallback family): HLASM has no formal parameter list on
        # an executable unit (parameters arrive via the R1 parameter-list
        # convention, undeclared); the construct that stands in for one is the
        # MACRO PROTOTYPE's symbolic-parameter list -- the line after a MACRO
        # directive, whose operand field declares `&PARM1,&KEY=dflt,...`. One
        # prototype is one hit (its continuation lines are the same
        # statement). A macro CALL's operands are actuals and never count
        # (the contract's call-site exclusion); a prototype with no `&`
        # parameters declares nothing.
        "args": re.compile(
            r"^[ \t]{1,71}MACRO[ \t]*\r?\n"
            r"(?:[.&]?" + _NAME + r")?[ \t]+" + _NAME + r"[ \t]+(&[^\n]{0,300})",
            re.M | re.I,
        ),
        # structural_boundaries: the instruction-mnemonic tally of a language
        # whose structure IS its instruction stream (the contract's "an
        # instruction mnemonic in a language with no other structure") -- the
        # load/store/move/compare/arithmetic core, the UNCONDITIONAL transfers
        # and calls (B/BR/J/BAL/BALR/BAS/BASR/BRAS -- #2764's relocation
        # target, assembly.py verbatim: `ret` IS `return`), and the
        # assembler's own structural vocabulary (DC/DS storage definition --
        # a NAMED DC is also globals', a deliberate tally/census dual --
        # USING/DROP addressability, ORG/LTORG/CNOP location control, END,
        # the TITLE/EJECT/SPACE/PRINT listing directives, PUSH/POP, and the
        # EXTRN/WXTRN linkage references #2730 excludes from api). EQU is
        # immutability_locks' alone (one owner).
        "structural_boundaries": re.compile(
            _STMT + r"(?:L|LR|LG|LGR|LGF|LH|LA|LARL|LM|LMG|LT|LTR|LTG"
            r"|ST|STG|STH|STC|STCM|STM|STMG|IC|ICM"
            r"|MVC|MVI|MVCL|MVCLE|MVN|MVZ|MVO"
            r"|CLC|CLI|CLM|CLR|C|CR|CH|CG|CGR|CL|CLG"
            r"|A|AR|AH|AL|ALR|AG|AGR|AFI|AHI|AGHI"
            r"|S|SR|SH|SL|SLR|SG|SGR"
            r"|M|MR|MH|MHI|MS|MSR|D|DR"
            r"|B|BR|J|BRU|BAL|BALR|BAS|BASR|BRAS|BRASL|BSM|BASSM"
            r"|DC|DS|USING|DROP|ORG|LTORG|CNOP|END|TITLE|EJECT|SPACE|PRINT|PUSH|POP|EXTRN|WXTRN)" + _OPEND,
            re.M | re.I,
        ),
        # func_start (#2503's x ask, adjusted to the #2856 contract): `name
        # CSECT` (a control section -- the named executable unit `L
        # R15,=V(name)` / the CALL macro reach), its read-only form `name
        # RSECT`, and `name START` (which opens the first control section
        # under its name). DELIBERATE DEVIATION from #2503's issue text, which
        # asked for DSECT here too: a DSECT is a dummy section -- a storage
        # LAYOUT that assembles no executable logic and emits no object code
        # -- which is #2856's type-declaration exclusion and lands in
        # class_start below (the db2_sql documented-deviation shape). A macro
        # definition is compile-time and is macros' (pli's %name: PROC
        # ruling). The name is required: an unnamed ` CSECT` resumes private
        # code and declares no reachable unit.
        "func_start": re.compile(
            r"^(" + _NAME + r")[ \t]+(?:CSECT|RSECT|START)" + _OPEND,
            re.M | re.I,
        ),
        # class_start (#2856): `name DSECT` -- the dummy section is HLASM's
        # record/struct declaration (a named storage mapping, the contract's
        # "class, struct, record" family), reached by name via `USING
        # name,reg`. See func_start's deviation note.
        "class_start": re.compile(
            r"^(" + _NAME + r")[ \t]+DSECT" + _OPEND,
            re.M | re.I,
        ),
        # --- PHASE 2: SAFETY & EXECUTION RISK ---
        # safety (#2869): the z/OS recovery macros -- ESTAE/ESTAEX and
        # ESPIE/SPIE install a failure handler for the task, SETRP sets the
        # recovery disposition inside one (HLASM's installed-handler family)
        # -- plus the CICS/SQL/DLI handler vocabulary shared verbatim with
        # cobol/pli (#2990): HANDLE CONDITION/ABEND, PUSH/POP HANDLE,
        # SYNCPOINT/RESYNC, SQL COMMIT/ROLLBACK/WHENEVER ... GO TO, DLI
        # checkpoints, and DFHRESP( response tests. `ESTAE 0` CANCELS the
        # handler and is safety_bypasses' -- the operand guard excludes it.
        "safety": re.compile(
            _STMT
            + r"(?:ESTAEX?(?![ \t]+0(?:[ \t,]|$))|ESPIE|SPIE|SETRP)"
            + _OPEND
            + r"|\bEXEC\s+CICS\s+(?:HANDLE\s+(?:CONDITION|ABEND)|PUSH\s+HANDLE|POP\s+HANDLE|SYNCPOINT|RESYNC)\b"
            r"|\bEXEC\s+SQL\s+(?:COMMIT|ROLLBACK|WHENEVER\s+(?:SQLERROR|SQLWARNING|NOT\s+FOUND)\s+GO\s*TO)\b"
            r"|\bEXEC\s+DLI\s+(?:CHKP|SYMCHKP|ROLB|ROLL|ROLS)\b"
            r"|\bDFHRESP[ \t]*\(",
            re.M | re.I,
        ),
        # safety_bypasses: cancelling an installed recovery environment
        # (`ESTAE 0`), and the CICS/SQL error-swallowing forms shared with
        # cobol/pli: IGNORE CONDITION, NOHANDLE, WHENEVER ... CONTINUE.
        # An unconditional branch is NOT one -- B/J is how assembler writes
        # every loop and exit path, the language's standard paradigm (Rule 2),
        # unlike cobol/pli's GO TO inside structured code.
        "safety_bypasses": re.compile(
            _STMT + r"ESTAEX?[ \t]+0(?=[ \t,]|$)" + r"|\bEXEC\s+CICS\s+IGNORE\s+CONDITION\b"
            r"|\bNOHANDLE\b"
            r"|\bEXEC\s+SQL\s+WHENEVER\s+(?:SQLERROR|SQLWARNING|NOT\s+FOUND)\s+CONTINUE\b",
            re.M | re.I,
        ),
        # high_risk_execution (#2878): ABEND ends the task abnormally (the
        # termination family; also panics_and_aborts' -- the #2878 dual) and
        # EXEC CICS ABEND is cobol's verbatim. LOAD/DELETE with an EP=/EPLOC=/
        # DE= operand bring a load module into storage and discard it -- the
        # loading-code family, pli's FETCH/RELEASE precedent (the operand
        # shape keeps CICS `DELETE FILE(...)` and SQL DELETE out). MODESET
        # switches the task into supervisor state or key zero -- the
        # protection-escape family's textbook member. Dynamic SQL is cobol's
        # family-2 alternative, verbatim.
        "high_risk_execution": re.compile(
            _STMT
            + r"ABEND"
            + _OPEND
            + r"|"
            + _STMT
            + r"(?:LOAD|DELETE)[ \t]+(?:EP|EPLOC|DE)="
            + r"|"
            + _STMT
            + r"MODESET"
            + _OPEND
            + r"|\bEXEC\s+CICS\s+ABEND\b"
            r"|\bEXEC\s+SQL\s+(?:PREPARE|EXECUTE(?:\s+IMMEDIATE)?|TRUNCATE|DROP\s+DATABASE)\b",
            re.M | re.I,
        ),
        # io (#2841): the native access-method macros in operation-field
        # position -- OPEN (its operand list is parenthesised: `OPEN
        # (DCB,(INPUT))`), QSAM GET/PUT, BSAM READ/WRITE/CHECK/POINT -- plus
        # the CICS file/queue command surface, `EXEC SQL` (minus the four
        # no-data statements), `EXEC DLI`, and the DL/I call interface
        # (`CALL ASMTDLI,...` -- assembler's PLITDLI). CLOSE is cleanup's
        # (#2841 C2). One statement is one hit; the CICS alternatives consume
        # through the verb first, so `READ` inside `EXEC CICS READ FILE(...)`
        # is never re-read (pli's finditer note verbatim).
        "io": re.compile(
            r"\bEXEC\s+CICS\s+(?:READQ|WRITEQ|DELETEQ)\s+(?:TS|TD)\b"
            r"|\bEXEC\s+CICS\s+(?:READ|WRITE|REWRITE|DELETE|UNLOCK|STARTBR|READNEXT|READPREV|ENDBR|RESETBR"
            r"|SPOOL(?:OPEN|READ|WRITE|CLOSE)|(?:DEFINE|GET|QUERY|UPDATE|REWIND|DELETE)\s+D?COUNTER)\b"
            r"|\bEXEC\s+SQL\b(?!\s+(?:INCLUDE|DECLARE|WHENEVER|BEGIN\s+DECLARE|END\s+DECLARE)\b)"
            r"|\bEXEC\s+DLI\b"
            r"|" + _STMT + r"CALL[ \t]+(?:ASMTDLI|AIBTDLI|CEETDLI)\b"
            r"|" + _STMT + r"OPEN[ \t]+\("
            r"|" + _STMT + r"(?:GET|PUT|READ|WRITE|CHECK|POINT)[ \t]+[A-Za-z@#$(]",
            re.M | re.I,
        ),
        # api (#2730 fallback family): a control section's name IS an external
        # symbol -- public to the linker by default -- so the section
        # declarations count (the deliberate func_start dual, bms's
        # DFHMDI/DFHMSD shape), and the ENTRY statement publishes additional
        # entry points from inside one. EXTRN/WXTRN declare a symbol defined
        # in ANOTHER unit -- the opposite direction -- and are excluded
        # (assembly.py's #2730 ruling verbatim).
        "api": re.compile(
            r"^(?:" + _NAME + r")[ \t]+(?:CSECT|RSECT|START)" + _OPEND + r"|" + _STMT + r"ENTRY[ \t]+[A-Za-z@#$]",
            re.M | re.I,
        ),
        # An ENTRY statement names entries whose executable units are defined
        # elsewhere in the same file; that mention must not clear those units'
        # unreferenced_by_name flag (#2823's export-list shape -- `ENTRY
        # A,B,C` names many at once, so the capture is a REGION).
        # The capture must OPEN on a name character: with a bare `[ \t,]`-
        # bearing class the `[ \t]+` before it and the class overlap (the Rule
        # 14 shape) and a blanks-only tail would "capture" an empty region.
        "_visibility_export_list": re.compile(
            _STMT + r"ENTRY[ \t]+([A-Za-z@#$][A-Za-z0-9@#$, \t]{0,299})",
            re.M | re.I,
        ),
        # state_mutation (#2765 fallback family, assembly.py's ruling): a
        # READ-MODIFY-WRITE mnemonic in instruction position -- the immediate
        # bit-twiddles OI/NI/XI (the flag-byte idiom), their storage-to-
        # storage forms OC/NC/XC, and packed-decimal arithmetic into storage
        # (AP/SP/MP/DP). A plain store (ST/MVC/MVI) is assembler's every
        # second statement -- the language's declaration-and-assignment
        # baseline, not a re-assignment signal (the assembly.py precedent:
        # mov is structural, xchg/inc count).
        "state_mutation": re.compile(
            _STMT + r"(?:OI|NI|XI|OC|NC|XC|AP|SP|MP|DP)" + _OPEND,
            re.M | re.I,
        ),
        # dead_code: a `*` (or `.*`) comment line whose text is a real
        # statement, each arm operand-guarded (bms's #2732 reasoning: banner
        # prose names mnemonics as English words and must not count) -- an
        # instruction with a two-operand shape (the comma is the guard), a
        # commented USING with its comma-joined operands, a commented DC/DS
        # whose operand opens with a real type shape (`X'00'`, `CL8'..'`,
        # `3A(0)`, `0H` -- "* DC POWER SUPPLY NOTES" has none and stays
        # prose), or a commented EXEC CICS/SQL command.
        "dead_code": re.compile(
            r"^(?:\.\*|\*)" + _ID + r"{0,63}[ \t]+"
            r"(?:(?:L|LA|LR|LH|ST|STH|MVC|MVI|CLC|CLI|LM|STM|BAL|BALR|BAS|BASR|BCT|IC|ICM)[ \t]+[\w@#$&=.'()+*-]{1,63},"
            r"|USING[ \t]+[\w@#$*.]{1,63},"
            r"|D[CS][ \t]+[0-9]{0,4}[A-Z](?:L[0-9]{1,3})?(?:['(]|[ \t]*$)"
            r"|EQU[ \t]+[\w@#$*'(]{1,63}[ \t]*$"
            r"|EXEC[ \t]+(?:CICS|SQL)\b)",
            re.M | re.I,
        ),
        # doc: the structured prologue-block convention -- a `*` comment line
        # tagged PURPOSE:/FUNCTION:/DESCRIPTION:/ABSTRACT:/REMARKS: (the
        # cobol REMARKS / pli header-block family, reshaped to HLASM's
        # column-1 comment marker).
        "doc": re.compile(
            r"^\*+[ \t]*(?:PURPOSE|FUNCTION|DESCRIPTION|ABSTRACT|REMARKS)[ \t]*:",
            re.M | re.I,
        ),
        # test (#2852): no framework executes an HLASM unit as a test case --
        # IBM zUnit runs COBOL/PL/I test cases and Test4z is COBOL -- so the
        # stated absence (yacc's ledger family).
        "test": None,
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        # concurrency: z/OS multitasking -- ATTACH/ATTACHX creates a subtask,
        # DETACH ends one, WAIT/POST coordinate through ECBs -- plus the CICS
        # task-coordination vocabulary shared with cobol/pli (#2990).
        "concurrency": re.compile(
            _STMT
            + r"(?:ATTACHX?|DETACH|WAIT|POST)"
            + _OPEND
            + r"|\bEXEC\s+CICS\s+(?:ENQ|DEQ|WAIT|WAITCICS|START|RETRIEVE|CANCEL|POST|DELAY|SUSPEND"
            r"|RUN\s+(?:TRANSID|ACTIVITY|ACQPROCESS)|FETCH\s+(?:CHILD|ANY)|FREE\s+CHILD)\b",
            re.M | re.I,
        ),
        # ui_framework: the CICS terminal surface (cobol/pli verbatim, #2990)
        # plus the BMS macros themselves -- mapsets are HLASM source and are
        # sometimes kept in `.asm` members rather than `.bms` ones.
        "ui_framework": re.compile(
            r"\bEXEC\s+CICS\s+(?:SEND|CONVERSE|ROUTE|PURGE\s+MESSAGE|ISSUE\s+ERASEAUP)\b"
            r"|" + _STMT + r"DFH(?:MSD|MDI|MDF)" + _OPEND,
            re.M | re.I,
        ),
        # closures: no anonymous callable exists; every unit carries a name.
        "closures": None,
        # globals (#2858): named initialized storage -- `name DC ...` defines
        # a program-lifetime binding at its label (assembly.py's labeled-
        # storage ruling). Named `DS` is EXCLUDED by Rule 17's enclosing-form
        # problem: the identical `name DS CL8` line is program storage inside
        # a CSECT and a zero-emission field LAYOUT inside a DSECT, and no
        # anchor can tell them apart -- DSECT fields are near-universally DS,
        # so DC keeps the census honest without a scope filter. GBLA/GBLB/
        # GBLC are compile-time SET symbols and stay macros' (bms's ruling).
        # A section switch (CSECT itself) is a region header, not state
        # (#2805's WORKING-STORAGE precedent).
        "globals": re.compile(
            r"^(" + _NAME + r")[ \t]+DC[ \t]+\S",
            re.M | re.I,
        ),
        # decorators: the attribute directives attached to the section they
        # modify -- AMODE/RMODE addressing attributes and XATTR.
        "decorators": re.compile(
            _STMT + r"(?:AMODE|RMODE|XATTR)" + _OPEND,
            re.M | re.I,
        ),
        # generics: no parametric types.
        "generics": None,
        # comprehensions: no collection-transform form.
        "comprehensions": None,
        # scientific: the floating-point instruction families in operation-
        # field position -- HFP (AE/AD/ME/MD/...), BFP (AEB/ADB/MDB/...),
        # their register forms, and square root.
        "scientific": re.compile(
            _STMT + r"(?:[ASMD](?:E|D|X)B?R?|SQ(?:E|D)B?R?|LDEB?R?|LEDB?R?)" + _OPEND,
            re.M | re.I,
        ),
        # reflection_metaprogramming: EX/EXRL execute a target instruction
        # with a runtime-modified length/operand byte -- the assembler's
        # dynamic-instruction idiom (variable-length MVC/CLC).
        "reflection_metaprogramming": re.compile(
            _STMT + r"(?:EX|EXRL)[ \t]+[\w@#$]",
            re.M | re.I,
        ),
        # import (#2875): the COPY statement binds a library member into the
        # source (bms verbatim). Macro invocation resolves through SYSLIB too,
        # but an invocation is a call, not a dependency statement.
        "import": re.compile(_STMT + r"COPY[ \t]+[A-Za-z@#$]", re.M | re.I),
        # _dependency_capture: the copied member name.
        "_dependency_capture": re.compile(_STMT + r"COPY[ \t]+(" + _ID + r"{1,8})\b", re.M | re.I),
        # ownership (#2882 C1): an author/maintainer tag keyed on a `*`
        # comment line (bms verbatim).
        "ownership": re.compile(
            r"^\*+[ \t]*(?:Authors?|Created[ \t]+by|Maintainers?|Owners?|Developers?|Contact)"
            r"[ \t]*:(?![:=])[ \t]*(\S[^\n]*?)[ \t]*$"
            r"|@author:?[ \t]+(\S[^\n]*?)[ \t]*$",
            re.I | re.M,
        ),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        "planned_debt": GLOBAL_PLANNED_DEBT,
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        # hardcoded_secrets: baseline rule in three languages only; the
        # security lens's own detector covers hlasm.
        "hardcoded_secrets": None,
        # spec_exposure: the generic tag anchored to a `*` comment line (bms
        # verbatim).
        "spec_exposure": re.compile(
            r"^\*[^\n\[]{0,200}\[(?:[ \t]*SPEC[ \t]*-[ \t]*[0-9]{1,10}|spec|audit)\b[^\]\n]{0,300}\]",
            re.M | re.I,
        ),
        # ssr_boundaries: the CICS web / document API (cobol/pli verbatim).
        "ssr_boundaries": re.compile(
            r"\bEXEC\s+CICS\s+(?:WEB\s+[A-Z]+|DOCUMENT\s+[A-Z]+|SOAPFAULT|EXTRACT\s+(?:WEB|TCPIP|CERTIFICATE))\b",
            re.M | re.I,
        ),
        # events: CICS event processing's SIGNAL EVENT (pli verbatim). The
        # receiving side (WAIT/HANDLE AID) is concurrency's/listeners'.
        "events": re.compile(r"\bEXEC\s+CICS\s+SIGNAL\s+EVENT\b", re.I),
        "dependency_injection": None,
        # macros (#2503's z ask): the macro-definition and conditional-
        # assembly directives -- MACRO/MEND/MEXIT, AIF/AGO/ANOP/ACTR, the SET
        # statements and their GBL/LCL declarations, AREAD, and MNOTE (a
        # compile-time diagnostic). The name field here may be a sequence
        # symbol (`.SKIP ANOP`) or a SET symbol (`&X SETA 1`), so the class
        # widens to `.`/`&` (bms's shape).
        "macros": re.compile(
            r"^(?:[.&]?" + _NAME + r")?[ \t]+"
            r"(?:MACRO|MEND|MEXIT|AIF|AGO|ANOP|ACTR|AREAD|MNOTE|SETA|SETB|SETC|GBLA|GBLB|GBLC|LCLA|LCLB|LCLC)" + _OPEND,
            re.M | re.I,
        ),
        # pointers: an address CONSTANT -- `DC A(sym)` / `DC V(external)` and
        # the literal forms `=A(sym)` / `=V(external)` -- takes and stores an
        # address (the address-of family). LA is EXCLUDED: load-address is
        # also assembler's everyday unsigned add (`LA R1,4(,R1)`), so counting
        # it would count increments (Rule 2's paradigm-alignment exclusion).
        "pointers": re.compile(
            r"\bDC[ \t]+[0-9]{0,4}[AV]L?[0-9]{0,2}\("
            r"|=[0-9]{0,4}[AV]L?[0-9]{0,2}\(",
            re.I,
        ),
        # memory_alloc: GETMAIN/FREEMAIN and their modern STORAGE
        # OBTAIN/RELEASE forms, CPOOL cell pools, and the CICS
        # GETMAIN/FREEMAIN commands (cobol/pli verbatim). FREEMAIN/RELEASE
        # are also cleanup's (pli's ALLOCATE/FREE dual).
        "memory_alloc": re.compile(
            _STMT + r"(?:GETMAIN|FREEMAIN|CPOOL)" + _OPEND + r"|" + _STMT + r"STORAGE[ \t]+(?:OBTAIN|RELEASE)\b"
            r"|\bEXEC\s+CICS\s+(?:GETMAIN|FREEMAIN)(?:64)?\b",
            re.M | re.I,
        ),
        # inline_asm: this IS assembly; nothing is inline in anything
        # (the assembly/agc_assembly ledger absence, verbatim).
        "inline_asm": None,
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        # telemetry: SNAP/SNAPX dump a formatted storage snapshot to a data
        # set, WTL writes to the system log, and the CICS diagnostic
        # emissions are cobol/pli verbatim (#2990).
        "telemetry": re.compile(
            _STMT
            + r"(?:SNAPX?|WTL)"
            + _OPEND
            + r"|\bEXEC\s+CICS\s+(?:WRITEQ\s+TD|WRITE\s+JOURNALNAME|WRITE\s+OPERATOR|DUMP\s+TRANSACTION|ENTER\s+TRACENUM)\b",
            re.M | re.I,
        ),
        # debug_prints: WTO/WTOR write a message to the operator console --
        # the operator-dialog family (#2878 routes dialog output here; pli's
        # DISPLAY precedent).
        "debug_prints": re.compile(_STMT + r"(?:WTO|WTOR)" + _OPEND, re.M | re.I),
        # explicit_casts: the format-conversion instructions -- CVB/CVD
        # (binary <-> packed decimal, with Y/G forms) and PACK/UNPK
        # (zoned <-> packed).
        "explicit_casts": re.compile(
            _STMT + r"(?:CVB[YG]?|CVD[YG]?|PACK|UNPK)" + _OPEND,
            re.M | re.I,
        ),
        # panics_and_aborts: ABEND ends the task abnormally (the deliberate
        # high_risk_execution dual, #2878) and EXEC CICS ABEND is cobol's.
        "panics_and_aborts": re.compile(
            _STMT + r"ABEND" + _OPEND + r"|\bEXEC\s+CICS\s+ABEND\b",
            re.M | re.I,
        ),
        # thread_sleeps: `STIMER WAIT,...` blocks the task for the interval
        # (WAIT is the first positional operand of the blocking form; SET and
        # REAL/TASK without WAIT schedule an exit and do not block), and the
        # CICS DELAY/SUSPEND commands (cobol/pli verbatim).
        "thread_sleeps": re.compile(
            _STMT + r"STIMERM?[ \t]+WAIT\b"
            r"|\bEXEC\s+CICS\s+(?:DELAY|SUSPEND)\b",
            re.M | re.I,
        ),
        # bitwise_ops: the REGISTER logical instructions (N/O/X families --
        # the storage RMW forms OI/NI/XI/OC/NC/XC are state_mutation's; one
        # owner per construct) and the shifts.
        "bitwise_ops": re.compile(
            _STMT + r"(?:N|NR|NG|NGR|O|OR|OG|OGR|X|XR|XG|XGR"
            r"|SLL|SRL|SLA|SRA|SLDL|SRDL|SLDA|SRDA|SLLG|SRLG|SLAG|SRAG)" + _OPEND,
            re.M | re.I,
        ),
        # sync_locks: the serialization primitives -- compare-and-swap
        # (CS/CDS and 64-bit forms), TEST AND SET, the ENQ/DEQ/RESERVE
        # resource-serialization macros, and CICS ENQ (pli verbatim).
        "sync_locks": re.compile(
            _STMT + r"(?:CS|CDS|CSG|CDSG|TS|ENQ|DEQ|RESERVE)" + _OPEND + r"|\bEXEC\s+CICS\s+ENQ\b",
            re.M | re.I,
        ),
        # immutability_locks (#2772): `name EQU value` declares a named
        # assembly-time constant -- the restricted constant-declaration form
        # distinct from the general-purpose (DC/DS) binding -- and RSECT
        # marks a control section read-only, where CSECT (the default) would
        # permit store instructions into it.
        "immutability_locks": re.compile(
            r"^(?:" + _NAME + r")[ \t]+(?:EQU[ \t]+\S|RSECT" + _OPEND + r")",
            re.M | re.I,
        ),
        # cleanup (#2888): CLOSE releases the open data set (`CLOSE (DCB)`),
        # FREEMAIN/STORAGE RELEASE return storage (the memory_alloc dual,
        # pli's FREE), FREEPOOL releases buffer pools, and the SQL cursor
        # CLOSE and CICS browse/spool teardown are cobol/pli verbatim.
        "cleanup": re.compile(
            _STMT + r"CLOSE[ \t]+[(A-Za-z@#$]"
            r"|" + _STMT + r"(?:FREEMAIN|FREEPOOL)" + _OPEND + r"|" + _STMT + r"STORAGE[ \t]+RELEASE\b"
            r"|\bEXEC\s+SQL\s+CLOSE\b"
            r"|\bEXEC\s+CICS\s+(?:ENDBR|SPOOLCLOSE|DELETE|FREE\s+CHILD)\b",
            re.M | re.I,
        ),
        # encapsulation (#2766): no declaration-position marker excludes a
        # name from the public surface -- a symbol is external only if a
        # section/ENTRY declares it, and every other label is file-local by
        # LEXICAL SCOPE, which the contract rules out (perl my / shell local
        # precedent). Stated absence.
        "encapsulation": None,
        # listeners: the receiving side of the terminal/session -- CICS
        # RECEIVE/CONVERSE/HANDLE AID (cobol/pli verbatim).
        "listeners": re.compile(
            r"\bEXEC\s+CICS\s+(?:RECEIVE|CONVERSE|HANDLE\s+AID)\b",
            re.I,
        ),
        # test_skip: no test framework, so no skip marker.
        "test_skip": None,
        # --- HYBRID DOMAIN SENSORS ---
        # auth_middleware (#3004): RACROUTE is the SAF interface -- REQUEST=VERIFY
        # builds/destroys a user's ACEE (sign-on) and REQUEST=AUTH asks RACF whether
        # the caller may touch a resource -- and RACHECK/RACINIT/RACDEF/FRACHECK are
        # its pre-SAF ancestors, same statement shape. The CICS command-level auth
        # vocabulary and embedded EXEC SQL GRANT/REVOKE are cobol/pli verbatim.
        "auth_middleware": re.compile(
            _STMT
            + r"(?:RACROUTE|RACHECK|FRACHECK|RACINIT|RACDEF)"
            + _OPEND
            + r"|\bEXEC\s+CICS\s+(?:SIGNON|SIGNOFF|(?:VERIFY|CHANGE)\s+(?:PASSWORD|PHRASE)|QUERY\s+SECURITY)\b"
            r"|\bEXEC\s+SQL\s+(?:GRANT|REVOKE)\b",
            re.M | re.I,
        ),
        # serialization_parsing: the CICS TRANSFORM command (pli verbatim);
        # HLASM itself has no format codec.
        "serialization_parsing": re.compile(r"\bEXEC\s+CICS\s+TRANSFORM\b", re.I),
        # regex_execution: no regular-expression facility -- TR/TRT are table
        # translate/scan operations that take no pattern (pli's INDEX/VERIFY
        # exclusion verbatim).
        "regex_execution": None,
        # time_date_logic: the TIME macro, the store-clock instructions
        # (STCK/STCKF/STCKE) and TOD conversion (CONVTOD), plus CICS
        # ASKTIME/FORMATTIME/CONVERTTIME (cobol/pli verbatim).
        "time_date_logic": re.compile(
            _STMT + r"(?:TIME|STCK[FE]?|CONVTOD)" + _OPEND + r"|\bEXEC\s+CICS\s+(?:ASKTIME|FORMATTIME|CONVERTTIME)\b",
            re.M | re.I,
        ),
        # ipc_rpc_bridges (#2503's y ask): the CICS bridge macros DFHEIENT/
        # DFHEIRET (command-level entry/return -- the translator-managed
        # boundary into CICS), the CICS program-control and channel
        # vocabulary (cobol/pli verbatim), the z/OS LINK/XCTL supervisor
        # macros (running another load module -- CICS LINK/XCTL's native
        # ancestors, same operand shape as LOAD's), the embedded SQL/DLI
        # bridge, and the DL/I call interface. A plain BALR to a local label
        # crosses no boundary and never counts.
        "ipc_rpc_bridges": re.compile(
            _STMT
            + r"DFHEI(?:ENT|RET)"
            + _OPEND
            + r"|"
            + _STMT
            + r"(?:LINK|XCTL)[ \t]+(?:EP|EPLOC|DE|SF)="
            + r"|\bEXEC\s+CICS\s+(?:LINK|XCTL|START|RETURN|RUN\s+TRANSID|INVOKE\s+(?:APPLICATION|SERVICE|WEBSERVICE))\b"
            r"|\bEXEC\s+CICS\s+(?:PUT|GET|MOVE)\s+CONTAINER\b"
            r"|\bEXEC\s+(?:SQL|DLI)\b"
            r"|" + _STMT + r"CALL[ \t]+(?:ASMTDLI|AIBTDLI|CEETDLI)\b",
            re.M | re.I,
        ),
        # system_config_mutation (#3084): contract-level absence. deferred, see
        # 3084: the authorized system-macro surface can rewrite system state,
        # but no anchored idiom has measured corpus incidence yet.
        "system_config_mutation": None,
    },
}
