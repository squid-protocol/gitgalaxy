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

from .._shared_patterns import CALLS_OUT_UNSUPPORTED, GLOBAL_FRAGILE_DEBT, GLOBAL_PLANNED_DEBT

# #2505: BMS (Basic Mapping Support) -- the CICS 3270 screen-definition language.
# A BMS map source is HLASM macro code: a name field starting in column 1, an
# operation field (the DFHMSD / DFHMDI / DFHMDF macros), and a KEYWORD=value
# operand list, continued by a non-blank column 72 onto a line resuming at
# column 16. `.bms` used to be an extension of the *jcl* profile, which was
# structurally wrong -- JCL is batch orchestration, BMS is a UI surface -- and
# meant every map read through job-control rules that could never match it.
#
# The HLASM name field: an ordinary symbol -- letters (plus @#$) then
# alphanumerics. CICS caps mapset/map names at 7 characters and field names at
# 30; the classes below take the permissive union (an over-long name is the
# assembler's diagnostic to make, not the classifier's).
_NAME = r"[A-Za-z@#$][A-Za-z0-9@#$]{0,30}"
# The name field is optional on a macro statement line (an unnamed DFHMDF is a
# screen literal; the closing DFHMSD TYPE=FINAL is frequently unnamed too), so
# statement-position rules anchor on "column 1 name-or-nothing, then blanks".
# The name class contains no whitespace, so `{0,31}` + `[ \t]+` partitions at
# exactly one position (no backtracking ambiguity, how_to Rule 5/14).
_STMT = r"^[A-Za-z0-9@#$]{0,31}[ \t]+"


DEFINITION: dict[str, Any] = {
    "_meta": {
        "target_version": "IBM CICS TS 6.x BMS (DFHMSD/DFHMDI/DFHMDF assembler macros)",
        "last_updated": "2026-09-15",
        "blueprint_version": "v6.3",
        "status": "production",
    },
    # COMPREHENSIVE SURFACE AREA: `.bms` is the universal convention (cics-genapp,
    # cics-banking-sample, Zowe samples). `.map` is claimed too (#2505 names both)
    # but is heavily contested in the wild -- JavaScript source maps and linker
    # maps end in `.map` -- so it is listed in COLLISION_FREQUENCIES
    # (_lens_config.py) and only ever locks to bms through the
    # internal_discriminator below or ecosystem gravity, never on extension alone.
    "extensions": [".bms", ".map"],
    "exact_matches": [],
    # ECOSYSTEM ANCHORS: the mainframe sources a BMS map lives beside -- the JCL
    # that assembles it and the COBOL programs (and copybooks) that SEND/RECEIVE it.
    "discriminators": [".bms", ".jcl", ".cbl", ".cpy"],
    # TOXIC NEIGHBORS (#377's matlab/objective-c mechanism): a `.map` sitting in
    # a web build output or a linker's output directory is a JS/CSS source map
    # or a linker map, never a BMS screen -- ecosystem gravity must collapse
    # bms's claim there rather than let the single-candidate `.map` fallback
    # self-support it. (Tier 2's internal_discriminator still wins for a real
    # BMS map wherever it lives; disqualifiers only gate the gravity path.)
    "disqualifiers": [".js", ".mjs", ".cjs", ".ts", ".css", ".o", ".elf", "package.json"],
    # EXECUTION SIGNATURES: assembled by DFHMAPS/DFHASMVS; no interpreter shebang.
    "shebangs": [],
    # Collision resolution for `.map` (the objective-c-vs-matlab `.m` mechanism):
    # a real BMS map source carries a DFH macro in operation-field position on
    # nearly every meaningful line; a JS source map (JSON) or linker map never
    # does. Strictly consulted for known extension collisions, never as a global
    # scanner (language_lens.py's Tier 2 guard).
    "internal_discriminator": re.compile(r"^[A-Za-z0-9@#$]{0,31}[ \t]+DFH(?:MSD|MDI|MDF)\b", re.M | re.I),
    # #2806/#2866 family: a BMS file's units cannot be invoked by name FROM BMS.
    # A map is reached by `EXEC CICS SEND MAP('MAP1') MAPSET('SET1')` in the
    # COBOL/PL/I program, never by any syntax inside the map source itself --
    # the macros assemble in the order written, top to bottom. So the
    # `unreferenced_by_name` census (a one-file name-reference test) is
    # unanswerable here and is not computed. TOP-LEVEL key, not a rule:
    # language_lens.py's pre-compiler would otherwise turn the string into
    # re.compile("positional") and silently read it as "not positional" (the
    # jcl.py precedent, verbatim).
    "invocation_model": "positional",
    # Rationale (how_to Step 4 item 8): HLASM is fixed-form -- a `*` in column 1
    # is a full-line comment and `.*` in column 1 is a macro comment; there is
    # no inline comment marker (trailing "remarks" are positional, not
    # delimited, and stay in the code stream as a known bound). The shared
    # positional_anchored anchor set ({'*','/','C','c','!'}) must NOT apply:
    # a map named CUSTMAP puts a real 'C' in column 1 (the exact #1898 ABAP
    # class-header bug). prism.py's `_strip_positional_comments` therefore
    # takes a bms mode ('*' and '.*' only, no column-7 check, no inline split).
    "lexical_family": "positional_anchored",
    # #3347: the screen-field fact channel -- every DFHMSD/DFHMDI/DFHMDF as a
    # mapset -> map -> field row (POS, LENGTH, ATTRB, PICIN/PICOUT, INITIAL,
    # OCCURS) in screen_field_data. TOP LEVEL, beside lexical_family, never in
    # `rules` (#2806: rules strings are re.compile()d and would extract nothing).
    "boundary_extraction": "bms",
    # COPY members resolve to PDS members, which are case-insensitive.
    "case_insensitive_imports": True,
    # #3199: this language's import statement names a library MEMBER that the
    # compiler pastes into the importing compilation unit (BMS `COPY`). A member is
    # source in this same language by construction, so when a copied name is
    # ambiguous the resolver only ever chooses a candidate in it, and drops the
    # edge when there is none. Without that, CBSA's `COPY BNK1CAM` -- a BMS
    # symbolic map, generated at build time and absent from the repository --
    # resolved to whichever same-named file happened to be nearest, which is the
    # map's own build JCL. Every other language keeps unconstrained
    # cross-language resolution (an HTML page importing a .css file).
    "imports_are_source_members": True,
    "rules": {
        # Epic #3264: Explicitly declare the structural invocation paradigm
        "calls_out": CALLS_OUT_UNSUPPORTED,
        # --- PHASE 1: LOGIC TOPOLOGY & STRUCTURE ---
        # branch: a screen definition makes no runtime choice. HLASM conditional
        # assembly (AIF/AGO) is compile-time and is macros' below (#2822's
        # preprocessor exclusion, the same split pli draws for %IF).
        "branch": None,
        # args (#2773 fallback family): BMS has no formal parameter list; the
        # construct that stands in for one is the NAMED field. A named DFHMDF is
        # exactly what becomes a data field in the generated symbolic map
        # copybook (FIELDI/FIELDO) -- the declared data interface the program
        # fills -- while an unnamed DFHMDF is a screen literal and declares
        # nothing. Deliberate dual with ui_framework (the jcl SET
        # globals+state_mutation shape): one macro is both a screen construct
        # and the declaration of the map's parameter surface.
        "args": re.compile(r"^(" + _NAME + r")[ \t]+DFHMDF\b", re.M | re.I),
        # structural_boundaries: the assembler's own structural vocabulary -- the
        # END statement that closes the source member, the listing directives
        # (TITLE/PRINT/EJECT/SPACE), and the DFHMSD TYPE=FINAL closer (the
        # mapset's closing bracket; a closer is a boundary token, not a second
        # declaration -- class_start excludes it below). The FINAL lookahead is
        # bounded to the statement's first physical line.
        "structural_boundaries": re.compile(
            _STMT + r"(?:END|TITLE|PRINT|EJECT|SPACE)\b" r"|" + _STMT + r"DFHMSD\b(?=[^\n]{0,200}\bTYPE=FINAL\b)",
            re.M | re.I,
        ),
        # func_start: the map -- `name DFHMDI` opens the named unit a program
        # reaches with SEND MAP. Every sendable map is named, so the name is
        # required (unlike jcl's optional stepname). The mapset rollup treats
        # maps-per-mapset the way steps-per-job reads in jcl.
        "func_start": re.compile(r"^(" + _NAME + r")[ \t]+DFHMDI\b", re.M | re.I),
        # class_start: the mapset -- the file's compilation-unit container
        # (#2856's cobol PROGRAM-ID / jcl JOB card family). `name DFHMSD
        # TYPE=...` declares it; the TYPE=FINAL statement (which may repeat the
        # name) closes it and is structural_boundaries' alone. The lookahead is
        # first-line-bounded: real initial DFHMSD statements carry TYPE= as the
        # first operand (TYPE=&SYSPARM / TYPE=(DSECT,...) / TYPE=MAP).
        "class_start": re.compile(r"^(" + _NAME + r")[ \t]+DFHMSD\b(?![^\n]{0,200}\bTYPE=FINAL\b)", re.M | re.I),
        # --- PHASE 2: SAFETY & EXECUTION RISK ---
        # safety: no runtime failure handling exists in a screen definition.
        "safety": None,
        # safety_bypasses: no type system or error channel to bypass.
        "safety_bypasses": None,
        # high_risk_execution: a map executes nothing (#2878: no site hands
        # control out of the program's own semantics -- there is no program).
        "high_risk_execution": None,
        # io: the terminal I/O happens at EXEC CICS SEND/RECEIVE in the hosting
        # program (cobol/pli own that vocabulary); the map itself moves no data.
        "io": None,
        # api (#2730): the declarations that make names visible outside this
        # file -- the mapset (DFHMSD) and map (DFHMDI) names are exactly what
        # SEND MAP / MAPSET reach from other members. Deliberate dual with
        # class_start/func_start (the dockerfile FROM shape). The TYPE=FINAL
        # closer re-states a name already declared and is excluded.
        "api": re.compile(
            r"^(" + _NAME + r")[ \t]+(?:DFHMDI\b|DFHMSD\b(?![^\n]{0,200}\bTYPE=FINAL\b))",
            re.M | re.I,
        ),
        # state_mutation: purely declarative; nothing is written twice.
        "state_mutation": None,
        # dead_code: a `*` (or `.*` macro-comment) line whose text is a real
        # macro statement -- the way a field or map is commented out of a
        # mapset. The operand guard (`KEYWORD=`) is load-bearing, jcl's #2732
        # reasoning verbatim: banner prose mentions the macro names as English
        # words ("* THE DFHMDF FIELDS BELOW ...") and must not count.
        "dead_code": re.compile(
            r"^(?:\.\*|\*)[A-Za-z0-9@#$]{0,31}[ \t]+DFH(?:MSD|MDI|MDF)[ \t]+[A-Z]{1,12}=",
            re.M | re.I,
        ),
        # doc: no generator-read documentation convention exists for BMS.
        "doc": None,
        # test: no framework executes a BMS map as a test case (#2852 ledger
        # absence, yacc's family).
        "test": None,
        # --- PHASE 3: ARCHITECTURE & DOMAIN SENSORS ---
        "concurrency": None,
        # ui_framework: THE signal (#2505's whole point) -- every BMS macro
        # statement builds the 3270 UI surface: DFHMSD (mapset), DFHMDI (map),
        # DFHMDF (field). Statement-position anchored so the words in a `*`
        # banner comment (stripped from the code stream anyway) or inside an
        # INITIAL='...' literal mid-line cannot match; one macro statement is
        # one hit, whatever its continuation lines carry.
        "ui_framework": re.compile(_STMT + r"DFH(?:MSD|MDI|MDF)\b", re.M | re.I),
        "closures": None,
        # globals: HLASM global SET symbols (GBLA/GBLB/GBLC) exist in the
        # assembler but not in application map sources; the macros rule counts
        # the directive family compile-time-wise. Stated absence for the
        # program-lifetime-binding axis.
        "globals": None,
        "decorators": None,
        "generics": None,
        "comprehensions": None,
        "scientific": None,
        "reflection_metaprogramming": None,
        # import (#2875): the assembler's COPY statement binds a shared member
        # (common for shared field groups / attribute equates) into the map
        # source. One statement, one hit.
        "import": re.compile(_STMT + r"COPY[ \t]+[A-Za-z@#$]", re.M | re.I),
        # _dependency_capture: the copied member name, for the dependency graph.
        "_dependency_capture": re.compile(_STMT + r"COPY[ \t]+([A-Za-z0-9@#$]{1,8})\b", re.M | re.I),
        # ownership (#2882 C1): an author/maintainer tag keyed on a `*` comment
        # line, jcl's rule reshaped to HLASM's column-1 comment marker.
        "ownership": re.compile(
            r"^\*+[ \t]*(?:Authors?|Created[ \t]+by|Maintainers?|Owners?|Developers?|Contact)"
            r"[ \t]*:(?![:=])[ \t]*(\S[^\n]*?)[ \t]*$"
            r"|@author:?[ \t]+(\S[^\n]*?)[ \t]*$",
            re.I | re.M,
        ),
        # --- PHASE 4: SPECIALIZED SUB-SYSTEMS ---
        "planned_debt": GLOBAL_PLANNED_DEBT,
        "fragile_debt": GLOBAL_FRAGILE_DEBT,
        # hardcoded_secrets: baseline rule in three languages only; the security
        # lens's own detector covers bms.
        "hardcoded_secrets": None,
        # spec_exposure: the generic `[SPEC-n]`/`[spec]`/`[audit]` tag anchored
        # to a `*` comment line (jcl's #2732 anchoring reasoning: comment rules
        # also sweep the code stream, and a `*` line can never appear there).
        "spec_exposure": re.compile(
            r"^\*[^\n\[]{0,200}\[(?:[ \t]*SPEC[ \t]*-[ \t]*[0-9]{1,10}|spec|audit)\b[^\]\n]{0,300}\]",
            re.M | re.I,
        ),
        "ssr_boundaries": None,
        "events": None,
        "dependency_injection": None,
        # macros: BMS maps ARE macro invocations, but the *definition/
        # conditional-compilation* directives this key owns are HLASM's
        # conditional assembly and macro-definition statements, which real map
        # sources do carry around &SYSPARM handling (AIF/AGO skips, SET
        # symbols). The name field here may be a sequence symbol (`.SKIP ANOP`)
        # or a SET symbol (`&X SETA 1`), so the class widens to `.`/`&`.
        "macros": re.compile(
            r"^(?:[.&]?[A-Za-z@#$][A-Za-z0-9@#$]{0,30})?[ \t]+"
            r"(?:MACRO|MEND|MEXIT|AIF|AGO|ANOP|SETA|SETB|SETC|GBLA|GBLB|GBLC|LCLA|LCLB|LCLC)\b",
            re.M | re.I,
        ),
        "pointers": None,
        "memory_alloc": None,
        # inline_asm: BMS *is* assembler macro source; nothing is inline in
        # anything (the assembly/agc_assembly ledger absence, verbatim).
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
        # auth_middleware (#3004): contract-level absence. Declarative 3270
        # screen maps: field positions and attributes, no executable auth act
        # (the SIGNON screen a map draws is cobol's EXEC CICS SIGNON to own).
        "auth_middleware": None,
        "serialization_parsing": None,
        "regex_execution": None,
        "time_date_logic": None,
        "ipc_rpc_bridges": None,
        # system_config_mutation (#3084): contract-level absence. a screen-map
        # definition language: it declares UI maps and mutates nothing beyond
        # its own assembly output.
        "system_config_mutation": None,
    },
}
