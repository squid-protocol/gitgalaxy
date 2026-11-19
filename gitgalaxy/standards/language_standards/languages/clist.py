# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================

from typing import Any

from gitgalaxy.standards.language_standards import _lazy_re as re  # #3914: compiled on first use

from .._shared_patterns import GLOBAL_FRAGILE_DEBT, GLOBAL_PLANNED_DEBT

# #8625: CLIST -- the z/OS TSO/E Command List language (z/OS TSO/E CLISTs). A CLIST member is a
# PDS member read by `EXEC` / `%name`; its statements are TSO commands plus the CLIST control
# language (`PROC`, `SET &x = ...`, `IF ... THEN`, `DO`/`END`, `SELECT`/`WHEN`, `GOTO`, `READ`,
# `WRITE`, `OPENFILE`/`GETFILE`/`PUTFILE`, `SYSCALL`). Variables are `&NAME`, a built-in function
# is `&SYSxxx(...)` or `&STR(...)`. It is a separate language from REXX (which `ADDRESS`es the
# same host commands): the control language, comments (`/* */`, never nested) and variable
# syntax all differ. A CLIST member carries no extension on z/OS; a repository checkout that
# keeps one names it `.clist`.
#
# A CLIST symbol is letters, digits and `@ # $ _`; `\w` covers letters/digits/`_` and the
# national characters are regex non-word characters, so bare keywords carry explicit guards.
_NAME = r"[\w@#$]"
_L = r"(?<![\w@#$&])"
_R = r"(?![\w@#$])"
# A statement starts at a line start, after a label (`LOOP: `), or after THEN / ELSE / DO.
_STMT_START = r"(?:^[ \t]*(?:" + _NAME + r"{1,64}:[ \t]*)?|" + _L + r"(?:THEN|ELSE|DO)" + _R + r"[ \t]+)"

DEFINITION: dict[str, Any] = {
    "_meta": {
        "target_version": "z/OS TSO/E CLIST",
        "last_updated": "2026-11-18",
        "blueprint_version": "v6.3",
        "status": "production",
    },
    # `.clist` is the repository spelling of a CLIST member (the z/OS member has no extension).
    # #8625: an extensionless member is routed by its dataset-qualifier directory (`USER.CLIST/MEMBER`) plus
    # `language_lens._CLIST_MEMBER_SHAPES`, or by that body evidence alone in an ordinary directory.
    "extensions": [".clist"],
    "library_directory_suffixes": ["clist", "clistlib", "sysproc"],
    "exact_matches": [],
    # ECOSYSTEM ANCHORS: the JCL that runs a CLIST (IKJEFT01 SYSTSIN) and sibling members.
    "discriminators": [".clist", ".jcl", ".rexx", ".exec"],
    "disqualifiers": [],
    "shebangs": [],
    # `/* ... */` comments, not nested; the PL/I family's morphology.
    "lexical_family": "standard_block",
    # CLIST names are case-insensitive, but declaring `identifier_case` joins the pinned lexicon set in
    # test_unreferenced_by_name_contract_2806.py (a sixth file): left to the next slice of #8625.
    "case_insensitive_imports": True,
    # invocation_model: DEFAULT (by_name): a CLIST label is reached by `GOTO label` and a
    # sub-procedure by `SYSCALL name`; both name the unit func_start extracts.
    "rules": {
        # `%name` runs another CLIST / REXX member and `SYSCALL name` runs an internal
        # sub-procedure: each names its callee in the first group.
        "calls_out": re.compile(
            r"(?:(?<![\w@#$&%])%|" + _L + r"SYSCALL[ \t]+)(" + _NAME + r"{1,64})",
            re.I,
        ),
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # branch: IF / ELSE and the SELECT group's WHEN / OTHERWISE arms; the loop openers
        # `DO WHILE` / `DO UNTIL` / the iterative `DO &I = ...`. A plain `DO` is a group.
        "branch": re.compile(
            _L
            + r"(?:IF|ELSE|WHEN|OTHERWISE)"
            + _R
            + r"|"
            + _L
            + r"DO[ \t]+(?:(?:WHILE|UNTIL)"
            + _R
            + r"|&"
            + _NAME
            + r"{1,64}[ \t]*=)",
            re.I | re.M,
        ),
        # args: the `PROC n positional keyword(default)` statement declares the parameters;
        # the group is the parameter list so the per-function count is the real one.
        "args": re.compile(_STMT_START + r"PROC[ \t]+\d{1,3}[ \t]*([^\n]{0,200})", re.I | re.M),
        "structural_boundaries": re.compile(_L + r"(?:PROC|END|RETURN|SYSCALL)" + _R, re.I),
        # func_start: a label -- `name:` at a line start -- is the unit GOTO and SYSCALL reach.
        "func_start": re.compile(r"^[ \t]*(" + _NAME + r"{1,250})[ \t]*:", re.I | re.M),
        # class_start: no named-type declaration.
        "class_start": None,
        # --- PHASE 2: SAFETY & EXECUTION RISK ---
        # safety: `ERROR DO` / `ATTN DO` / `ERROR ACTION` install the error and attention
        # handlers (CLIST's try/catch) and `&LASTCC` / `&SYSOUTTRAP` read the response.
        "safety": re.compile(
            _L + r"(?:ERROR|ATTN)[ \t]+(?:DO|ACTION|[A-Z]+[ \t]*\()" + r"|&(?:LASTCC|MAXCC)" + _R,
            re.I,
        ),
        # safety_bypasses: `CONTROL NOFLUSH` / `ERROR OFF` / `ATTN OFF` disable the handler;
        # `GOTO` is the unstructured jump (the GO TO ruling).
        "safety_bypasses": re.compile(
            _L
            + r"(?:ERROR|ATTN)[ \t]+OFF"
            + _R
            + r"|"
            + _L
            + r"CONTROL[ \t]+[^\n]{0,60}?NOFLUSH"
            + _R
            + r"|"
            + _L
            + r"GOTO"
            + _R,
            re.I,
        ),
        # high_risk_execution: `EXIT` ends the whole member, even from a sub-procedure;
        # `SYSCALL` / `%name` run other code.
        "high_risk_execution": re.compile(_L + r"EXIT" + _R + r"(?![ \t]*:)", re.I),
        # io: the terminal and file verbs -- READ / READDVAL / WRITE / WRITENR, the dataset
        # I/O OPENFILE / GETFILE / PUTFILE / CLOSFILE, and `ALLOC` / `FREE` for the datasets.
        "io": re.compile(
            _STMT_START + r"(?:READDVAL|READ|WRITENR|WRITE|OPENFILE|GETFILE|PUTFILE|CLOSFILE)" + _R,
            re.I | re.M,
        ),
        "api": None,
        # state_mutation: `SET &x = ...` is the write (CLIST's only assignment).
        "state_mutation": re.compile(_STMT_START + r"SET[ \t]+&" + _NAME + r"{1,64}", re.I | re.M),
        "dead_code": re.compile(
            r"/\*[ \t]*(?:SET[ \t]+&"
            + _NAME
            + r"{1,64}[ \t]*=|IF[ \t]+[^\n]{0,120}?THEN|GOTO[ \t]+"
            + _NAME
            + r"|SYSCALL[ \t]+"
            + _NAME
            + r")",
            re.I,
        ),
        "doc": re.compile(r"^[ \t]*/\*+[ \t]*(?:PURPOSE|DESCRIPTION|ABSTRACT|REMARKS|FUNCTION)[ \t]*:", re.I | re.M),
        "test": None,
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        "concurrency": None,
        # ui_framework: the ISPF dialog services a CLIST drives.
        "ui_framework": re.compile(
            _L + r"ISPEXEC[^\n]{0,120}?" + _L + r"(?:DISPLAY|ADDPOP|REMPOP|SETMSG|PQUERY|LMDDISP|TBDISPL)" + _R,
            re.I,
        ),
        "closures": None,
        # globals: `GLOBAL` names the variables shared across nested CLISTs, and
        # `&SYSDSN` / `&SYSUID` style system variables read ambient state.
        "globals": re.compile(_L + r"GLOBAL" + _R + r"|&SYS[A-Z]{2,12}" + _R, re.I),
        "decorators": None,
        "generics": None,
        "comprehensions": None,
        "scientific": None,
        "reflection_metaprogramming": None,
        "import": None,
        "_dependency_capture": None,
        "ownership": re.compile(
            r"^[ \t]*/\*+[ \t]*(?:Authors?|Created[ \t]+by|Maintainers?|Owners?|Developers?|Contact)"
            r"[ \t]*:(?![:=])[ \t]*(\S[^\n]*?)[ \t]*(?:\*/)?[ \t]*$",
            re.I | re.M,
        ),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        "planned_debt": GLOBAL_PLANNED_DEBT,
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        # the security lens's own detector covers CLIST credentials (mainframe_secrets).
        "hardcoded_secrets": None,
        "spec_exposure": re.compile(r"\[(?:[ \t]*SPEC[ \t]*-[ \t]*[0-9]{1,10}|spec|audit)\]", re.I),
        "ssr_boundaries": None,
        "events": None,
        "dependency_injection": None,
        "macros": None,
        "pointers": None,
        "memory_alloc": None,
        "inline_asm": None,
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        "telemetry": re.compile(_L + r"CONTROL[ \t]+[^\n]{0,60}?(?:LIST|CONLIST|SYMLIST|MSG)" + _R, re.I),
        # debug_prints: WRITE / WRITENR print to the terminal.
        "debug_prints": re.compile(_STMT_START + r"WRITE(?:NR)?" + _R, re.I | re.M),
        "explicit_casts": None,
        "panics_and_aborts": re.compile(_L + r"EXIT" + _R + r"(?![ \t]*:)", re.I),
        "thread_sleeps": None,
        "bitwise_ops": None,
        "sync_locks": None,
        "immutability_locks": None,
        # cleanup: `FREE` releases allocated datasets, `CLOSFILE` closes a file, `DELETE`
        # removes a dataset.
        "cleanup": re.compile(_STMT_START + r"(?:FREE|CLOSFILE)" + _R, re.I | re.M),
        "encapsulation": None,
        "listeners": None,
        "test_skip": None,
        # --- HYBRID DOMAIN SENSORS ---
        "auth_middleware": None,
        "serialization_parsing": None,
        "regex_execution": None,
        "time_date_logic": re.compile(r"&SYS(?:DATE|TIME|JDATE|SDATE)" + _R, re.I),
        # ipc_rpc_bridges: `%name` / `EXEC` hand control to another member.
        "ipc_rpc_bridges": re.compile(
            r"(?<![\w@#$&%])%" + _NAME + r"{1,64}|" + _STMT_START + r"EXEC" + _R, re.I | re.M
        ),
        "system_config_mutation": None,
    },
}
