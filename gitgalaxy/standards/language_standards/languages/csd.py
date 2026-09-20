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

# #3211-followup: CSD/RDO -- the CICS resource-definition language. A CSD deck is
# the output of (or the input to) DFHCSDUP/CEDA: a stream of
# `DEFINE TRANSACTION(xxxx) ... PROGRAM(yyyy)` and `DEFINE PROGRAM(yyyy) ...`
# records, grouped by GROUP(...) and installed via ADD ... LIST(...). It is the
# CICS transaction map -- which 4-char transaction ID a terminal user submits
# and which program CICS routes it to -- the external entry points a modernizer
# turns into service/API boundaries. Before this handler the definitions shipped
# in the corpora (carddemo's CARDDEMO.CSD, CBSA's BANK.csd) were never read.
#
# The structured transaction -> program map is NOT produced here; the DEFINITION
# below is the classification/census layer only. The named channel that yields
# transaction resources into the master DB is the boundary extractor
# (core/mainframe_boundary.py, dialect "csd"), opted into by the top-level
# `boundary_extraction` key -- the #3200/#3201 pattern, exactly as cobol/jcl do.
#
# SYNTAX SURFACES (all three appear in the pinned corpora):
#   1. CEDA/DFHCSDUP EXTRACT dumps (carddemo `.CSD`): a leading blank column,
#      `DEFINE`, then `KEYWORD(value)` operands continued across indented lines
#      with NO continuation character, plus audit trailers (DEFINETIME/CHANGE*).
#   2. Hand-written DFHCSDUP SYSIN members (CBSA `BANK.csd`): `*` column-1
#      comments, quoted DESCRIPTIONs, `DELETE GROUP`/`ADD GROUP ... LIST(...)`.
#   3. Inline SYSIN inside JCL (`//SYSIN DD *`): handled by the jcl dialect,
#      which hands its DFHCSDUP deck to the same csd extractor.
#
# A CICS resource name is up to 8 chars (a transaction ID is capped at 4); the
# permissive union is taken here -- an over-long name is DFHCSDUP's diagnostic.
_NAME = r"[A-Za-z0-9@#$]{1,8}"
# A `DEFINE`/`DELETE`/`ALTER`/`ADD` command may start in column 1 (BANK.csd), after
# one leading blank (CARDDEMO.CSD), or indented (inline JCL SYSIN); anchor on the
# statement, tolerating leading whitespace, and fire on every line (re.M).
_STMT = r"^[ \t]*"
# The resource-type keywords a CSD command names. TRANSACTION and PROGRAM are the
# transaction map; the rest are the surrounding resource inventory.
_RESOURCE = r"(?:TRANSACTION|PROGRAM|MAPSET|FILE|TDQUEUE|TSMODEL|LIBRARY|DB2ENTRY|DB2TRAN|DB2CONN|CONNECTION|TERMINAL|TYPETERM|PROFILE|PARTITIONSET|GROUP|LIST)"

DEFINITION: dict[str, Any] = {
    "_meta": {
        "target_version": "IBM CICS TS 6.x CSD (DFHCSDUP / CEDA resource definitions)",
        "last_updated": "2026-09-20",
        "blueprint_version": "v6.3",
        "status": "production",
    },
    # `.csd` is the universal convention for a CSD extract or DFHCSDUP input deck
    # (aws-mainframe-modernization-carddemo, cics-banking-sample-application-cbsa).
    # It is not a contested extension in the wild, so no COLLISION_FREQUENCIES
    # entry is needed; the internal_discriminator below still locks a `.csd` that
    # a future collision might contest.
    "extensions": [".csd"],
    "exact_matches": [],
    # ECOSYSTEM ANCHORS: a CSD deck lives beside the COBOL programs it names, the
    # BMS maps its MAPSETs assemble, and the JCL that runs DFHCSDUP to install it.
    "discriminators": [".csd", ".cbl", ".cpy", ".bms", ".jcl"],
    # A `.csd` is never a build-output or a source map; nothing toxic claims it,
    # so the disqualifier set is empty (unlike bms's contested `.map`).
    "disqualifiers": [],
    # No interpreter shebang: a CSD deck is read by DFHCSDUP, not executed.
    "shebangs": [],
    # Collision resolution for a contested `.csd`: a real CSD deck carries a CICS
    # resource-definition command (DEFINE/DELETE/ADD/ALTER a TRANSACTION/PROGRAM/
    # GROUP/...) on a meaningful line; nothing else does. Strictly a known-collision
    # discriminator, never a global scanner (language_lens.py Tier 2 guard).
    "internal_discriminator": re.compile(
        _STMT + r"(?:DEFINE|DELETE|ALTER|ADD|UPGRADE|REMOVE|LIST|COPY)[ \t]+" + _RESOURCE + r"\b",
        re.M | re.I,
    ),
    # #2806/#2866 family: a CSD resource cannot be invoked BY NAME from within the
    # CSD. A transaction is reached when a terminal user (or an EXEC CICS
    # RETURN/START/RUN TRANSID in a COBOL program) submits its 4-char id, never by
    # any syntax inside the deck itself -- the records install in the order
    # written. So the `unreferenced_by_name` census (a one-file name-reference
    # test) is unanswerable here and is not computed. TOP-LEVEL key, not a rule:
    # language_lens.py's pre-compiler would otherwise re.compile("positional")
    # and silently read it as "not positional" (the jcl.py precedent, verbatim).
    "invocation_model": "positional",
    # A CSD command is fixed-ish form: a `*` in column 1 is a full-line comment
    # (DFHCSDUP SYSIN); there is no inline comment marker. The shared
    # positional_anchored family fits, but its anchor set ({'*','/','C','c','!'})
    # must NOT apply -- a program named CUSTPROG puts a real 'C' in column 1 --
    # so, like bms, only the `*` full-line comment is honoured.
    "lexical_family": "positional_anchored",
    # #3200/#3201/#3211-followup: opts csd into the named mainframe boundary
    # channel. The extractor reads the DEFINE TRANSACTION(...) PROGRAM(...) records
    # and yields the transaction -> program map into transaction_data. Top level,
    # not inside `rules` -- see the language_lens.py string-compilation trap
    # (#2806) noted on jcl.py/cobol.py.
    "boundary_extraction": "csd",
    # Resource names resolve to PDS members / CICS resources, case-insensitive.
    "case_insensitive_imports": True,
    "rules": {
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # branch: a resource definition makes no runtime choice.
        "branch": None,
        # args (#2773 fallback family): a CSD record has no formal parameter list;
        # the construct that stands in for one is the KEYWORD(value) attribute --
        # the declared knobs of a resource (PROGRAM, PROFILE, TWASIZE, STATUS...).
        # Deliberate dual with api/func_start: one record is both a resource and
        # its own attribute surface. Anchored to a DEFINE statement so a KEYWORD
        # in a DESCRIPTION('...') literal cannot match.
        "args": re.compile(_STMT + r"DEFINE[ \t]+" + _RESOURCE + r"[ \t]*\(", re.M | re.I),
        # structural_boundaries: DFHCSDUP's own structural vocabulary -- the
        # commands that open/close a group or list rather than define a resource
        # (ADD ... TO a LIST, DELETE/REMOVE a GROUP, the terminal LIST command).
        "structural_boundaries": re.compile(
            _STMT + r"(?:ADD|REMOVE|DELETE|LIST|UPGRADE)[ \t]+(?:GROUP|LIST)\b",
            re.M | re.I,
        ),
        # func_start: the TRANSACTION -- `DEFINE TRANSACTION(TTTT)` opens the named
        # entry point a user (or a COBOL RETURN/START TRANSID) reaches. Every
        # transaction is named, so the name is required. The transactions-per-group
        # rollup reads the way maps-per-mapset does in bms.
        "func_start": re.compile(_STMT + r"DEFINE[ \t]+TRANSACTION[ \t]*\((" + _NAME + r")\)", re.M | re.I),
        # class_start: the PROGRAM -- the deployable module a transaction routes
        # to (`DEFINE PROGRAM(PPPP)`), the file's compilation-unit container
        # analogue (cobol PROGRAM-ID / bms DFHMSD family).
        "class_start": re.compile(_STMT + r"DEFINE[ \t]+PROGRAM[ \t]*\((" + _NAME + r")\)", re.M | re.I),
        # --- PHASE 2: SAFETY & EXECUTION RISK ---
        "safety": None,
        "safety_bypasses": None,
        # high_risk_execution: a definition executes nothing (the bms/#2878
        # reasoning: no site hands control out of the record's own semantics).
        "high_risk_execution": None,
        "io": None,
        # api (#2730): the declarations that make names visible outside this deck
        # -- the TRANSACTION and PROGRAM names are exactly what a terminal submits
        # and what an EXEC CICS transfer reaches from a COBOL program. Deliberate
        # dual with func_start/class_start (the dockerfile FROM shape).
        "api": re.compile(_STMT + r"DEFINE[ \t]+(?:TRANSACTION|PROGRAM)[ \t]*\(" + _NAME + r"\)", re.M | re.I),
        # state_mutation: purely declarative; nothing is written twice.
        "state_mutation": None,
        # dead_code: a `*`-commented DEFINE -- the way a resource is commented out
        # of a deck. The operand guard (`(name)`) is load-bearing (jcl's #2732
        # reasoning verbatim): banner prose naming the verbs as English words
        # ("* THE DEFINE COMMANDS BELOW ...") must not count.
        "dead_code": re.compile(
            r"^[ \t]*(?:\*|//\*)[ \t]*(?:DEFINE|DELETE|ALTER)[ \t]+" + _RESOURCE + r"[ \t]*\(" + _NAME,
            re.M | re.I,
        ),
        "doc": None,
        "test": None,
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        "concurrency": None,
        # ui_framework: a CSD deck declares no UI surface itself. The 3270 maps its
        # MAPSET records name are BMS's (`.bms`); the deck only points at them.
        "ui_framework": None,
        "closures": None,
        "globals": None,
        "decorators": None,
        "generics": None,
        "comprehensions": None,
        "scientific": None,
        "reflection_metaprogramming": None,
        # import: a DEFINE TRANSACTION binds the PROGRAM it routes to (and a MAPSET
        # a program SENDs); the PROGRAM(...) attribute is the cross-resource edge.
        # One attribute, one hit.
        "import": re.compile(r"\bPROGRAM[ \t]*\(" + _NAME + r"\)", re.M | re.I),
        # _dependency_capture: the routed-to program name, for the dependency graph
        # -- the transaction map's edge in classification terms (the boundary
        # channel carries the resolved, resource-typed form).
        "_dependency_capture": re.compile(r"\bPROGRAM[ \t]*\((" + _NAME + r")\)", re.M | re.I),
        # ownership (#2882 C1): an author/maintainer tag on a `*` comment line.
        "ownership": re.compile(
            r"^[ \t]*\*+[ \t]*(?:Authors?|Created[ \t]+by|Maintainers?|Owners?|Developers?|Contact)"
            r"[ \t]*:(?![:=])[ \t]*(\S[^\n]*?)[ \t]*$"
            r"|@author:?[ \t]+(\S[^\n]*?)[ \t]*$",
            re.I | re.M,
        ),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        "planned_debt": GLOBAL_PLANNED_DEBT,
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        "hardcoded_secrets": None,
        # spec_exposure: the generic `[SPEC-n]`/`[spec]`/`[audit]` tag anchored to
        # a `*` comment line (jcl's #2732 anchoring reasoning).
        "spec_exposure": re.compile(
            r"^[ \t]*\*[^\n\[]{0,200}\[(?:[ \t]*SPEC[ \t]*-[ \t]*[0-9]{1,10}|spec|audit)\b[^\]\n]{0,300}\]",
            re.M | re.I,
        ),
        "ssr_boundaries": None,
        "events": None,
        "dependency_injection": None,
        "macros": None,
        "pointers": None,
        "memory_alloc": None,
        "inline_asm": None,
        # --- PHASE 5: RESOURCE MANAGEMENT & STABILITY ---
        "telemetry": None,
        "debug_prints": None,
        "explicit_casts": None,
        "panics_and_aborts": None,
        "thread_sleeps": None,
        "bitwise_ops": None,
        "sync_locks": None,
        "immutability_locks": None,
        "cleanup": None,
        "encapsulation": None,
        "listeners": None,
        "test_skip": None,
        # --- HYBRID DOMAIN SENSORS ---
        # auth_middleware (#3004): contract-level absence. A resource-definition
        # deck declares STATUS/PROFILE/RESSEC/CMDSEC attributes but performs no
        # executable auth act (the SIGNON a transaction fronts is the program's
        # EXEC CICS SIGNON to own).
        "auth_middleware": None,
        "serialization_parsing": None,
        "regex_execution": None,
        "time_date_logic": None,
        "ipc_rpc_bridges": None,
        # system_config_mutation (#3084): THE signal. DFHCSDUP's whole purpose is
        # to mutate the CICS system definition file -- every DEFINE/DELETE/ALTER/
        # ADD/UPGRADE command changes the installed resource inventory. This is the
        # same intent family jcl.py flags on `PGM=DFHCSDUP` (the step); here it is
        # the deck body that step runs. Statement-anchored so the words in a `*`
        # banner or a DESCRIPTION literal cannot match.
        "system_config_mutation": re.compile(
            _STMT + r"(?:DEFINE|DELETE|ALTER|ADD|UPGRADE|REMOVE)[ \t]+" + _RESOURCE + r"\b",
            re.M | re.I,
        ),
    },
}
