#!/usr/bin/env python3
# ==============================================================================
# galaxyscope:ignore sec_db_hooks, sec_io, sec_high_risk_execution
# GitGalaxy Tool: Galaxy IR Reader (#3120)
#
# PURPOSE:
# Reads the engine's `<repo>_galaxy_master.db` as an Intermediate Representation
# source for the refraction pipeline, so the modernization suite consumes what
# the audited engine already extracted instead of re-parsing it.
#
# SCOPE (read before extending):
# The master DB now carries almost everything the forge parsers derive. Taken
# from the DB here: the per-language file inventory, PROGRAM-ID (class_data),
# the paragraph/section inventory (function_data), resolved COPY/INCLUDE edges
# (edge_data, edge_kind 'import'), subsystem hit counts, since #3200/#3201 the
# mainframe call graph (call_site_data, plus edge_data kinds 'call'/'exec') and
# dataset boundary (dataset_data), since #3246 the DATA DIVISION item tree + FD
# record layouts (record_data; since #3250 also PL/I DECLAREd structures, with
# their full attribute text in `attributes`), and since #3211-followup the CICS transaction
# map (transaction_data: which transaction id entry-points into which program,
# plus the in-source routing verbs 'RETURN/START/RUN TRANSID' carried in
# call_site_data), since #3344 the DB2 table shapes programs bind to
# (sql_table_data: every `EXEC SQL DECLARE <table> TABLE (...)` column -- SQL
# type, length/scale, nullability -- inline or DCLGEN-generated, per
# EngineFile.sql_tables), since #3446 what programs DO to those tables
# (sql_statement_data: every embedded SQL statement with its verb, the tables
# it reads/inserts/updates/deletes, cursor and host variables, per
# EngineFile.sql_statements, joined into GalaxyIR.sql_table_access()),
# since #3347 the BMS screen-field layouts
# (screen_field_data: every mapset/map/field with POS, LENGTH, ATTRB,
# PICIN/PICOUT, INITIAL, OCCURS -- the source of the symbolic-map copybooks, per
# EngineFile.screen_fields), and since #3345 each JCL DD's DSN with its symbolic
# parameters (SET / PROC defaults / EXEC overrides) resolved where one file
# determines it (dataset_data.dsn_resolved + dsn_resolution; cross-member
# cataloged-PROC callers are left `unresolved`/`proc_default`, never guessed),
# and since #3356 every CSD resource definition beyond the transaction map
# (csd_resource_data: FILE -> DSNAME, TDQUEUE TYPE/DDNAME/DSNAME, DB2TRAN ->
# DB2ENTRY -> PLAN, MAPSET, LIBRARY, URIMAP/WEBSERVICE..., per
# EngineFile.csd_resources; joined by cics_file_datasets (CICS file -> dataset
# -> the batch lineage), tdqueue_datasets and transaction_db2_plans),
# and since #3355 the COMMAREA contract: each CICS LINK/XCTL/RETURN TRANSID
# site's `COMMAREA(x)` and `LENGTH(...)`/`DATALENGTH(...)` operands as written
# (call_site_data.commarea/commarea_length/commarea_datalength, per
# EngineCall), plus the COPY member(s) expanding after each data entry
# (record_data.copy_members). The join itself -- the caller's record x, COPY
# expanded, against the callee's LINKAGE DFHCOMMAREA, with byte lengths and a
# field-shape comparison -- is computed HERE (GalaxyIR.commarea_contracts), not
# stored: a length or shape mismatch is reported as data, never adjudicated,
# and since #3351-#3354 every EXEC CICS command that names a resource
# (cics_resource_data, per EngineFile.cics_resources): FILE I/O, SEND/RECEIVE
# MAP (joined to the BMS map's screen fields by GalaxyIR.screen_bindings), TS/TD
# queues and channels/containers (producer -> consumer programs by
# GalaxyIR.queue_flows / container_flows; FILE and TD-queue operations joined to
# the #3356 CSD DSNAME and on to batch lineage by cics_file_lineage /
# tdqueue_lineage), each name read through its VALUE (or a single MOVEd
# literal) the way LINK targets are, and since #3449 CICS task control
# (cics_task_data, per EngineFile.cics_tasks): RUN/START children with their
# transid -- or the fnmatch pattern a STRING builds it from (`OCR[0-9]`) -- the
# channel and CHILD/REQID token, FETCH/FREE joins, RETRIEVE, DELAY, POST, WAIT
# and ENQ/DEQ; GalaxyIR.async_tasks joins each spawn to the CSD transactions and
# programs it reaches, the containers it passes and the FETCHes that collect it.
# Since #3448, job submission through the internal reader (job_submit_data, per
# EngineFile.job_submits): the JCL JOB/EXEC cards a COBOL program holds as
# literals and the JCL DDs routed to SYSOUT=(x,INTRDR); GalaxyIR.job_submissions
# joins a CICS `WRITEQ TD` to an extrapartition TDQUEUE and on to the job it
# submits, and a batch INTRDR step to the JCL member it copies there.
# Since #3447, IBM MQ calls (mq_call_data, per EngineFile.mq_calls): each
# MQOPEN/MQPUT/MQPUT1/MQGET/MQCLOSE with the queue read through its object
# descriptor (or the MQOPEN its handle came from), the direction and options;
# GalaxyIR.mq_queues lists every program's queue endpoints -- `trigger` and
# `reply_to` named as runtime queues -- and mq_flows pairs producers with
# consumers of the same named queue.
# Since #3453, units of work and error handling (uow_handler_data, per
# EngineFile.uow_handlers): SYNCPOINT / SQL COMMIT / ROLLBACK points, HANDLE
# CONDITION / ABEND / AID handlers, explicit ABENDs and the DFHRESP conditions
# each RESP-coded command's result is tested for; GalaxyIR.units_of_work,
# error_handlers and unchecked_responses place them in their owning paragraph.
# tdq_trigger_starts joins a WRITEQ TD to a CSD TDQUEUE with TRIGGERLEVEL and
# TRANSID -- the transaction CICS starts when the queue fills.
# Since #3455, file definitions: each FILE-CONTROL SELECT's organisation,
# access mode and keys (file_control_data, per EngineFile.file_control) and each
# IDCAMS DEFINE CLUSTER / AIX / PATH in JCL (vsam_define_data, per
# EngineFile.vsam_defines); GalaxyIR.vsam_files puts a SELECT's RECORD KEY at its
# byte offset in the FD record and checks it against the KEYS(l o) of the cluster
# (or the AIX behind a PATH) its DD is bound to, and against the CSD FILE.
# Since #3451, JCL job flow (job_flow_data, per EngineFile.job_flow): each job's
# steps in order with COND= / IF conditions and PROC calls, and each DSN DD's
# DISP and GDG generation; GalaxyIR.job_steps expands PROC calls into the
# procedure's steps and job_dataset_flow pairs the DDs that create a dataset with
# the DDs (of later steps, or of other jobs) that read it. Scheduler order is not
# in the repository, so cross-job edges are candidates.
# Since #3454, batch CALL USING contracts: each CALL's USING list
# (call_site_data.using_args) and each program's PROCEDURE DIVISION / ENTRY USING
# parameters (entry_point_data, per EngineFile.entry_points); GalaxyIR.call_contracts
# pairs them by position -- arity, and each argument's byte length through
# record_layout -- the batch counterpart of commarea_contracts.
# Since #3450, IMS DL/I calls (dli_call_data, per EngineFile.dli_calls): EXEC DLI
# commands and CALL 'CBLTDLI' with their operands as written; GalaxyIR.ims_calls
# resolves a CBLTDLI function code and each SSA's segment / qualification
# through the COPY-expanded working-storage VALUEs, and ims_segment_access is the
# program x segment matrix (the IMS counterpart of sql_table_access).
# Since #3477, IMS PSB / DBD generation macros and JCL IMS region steps
# (ims_gen_data, per EngineFile.ims_gen); GalaxyIR.ims_access_check joins each
# program's segment access to its PSB (the DFSRRC00 PARM, or an EXEC DLI SCHD
# PSB), the PCB whose SENSEGs include the segment, that PCB's DBD and PROCOPT.
# Since #3452, field-level data movement (data_move_data, per
# EngineFile.data_moves): GalaxyIR.data_flows resolves each MOVE / COMPUTE /
# STRING ... operand to its storage span (record, offset, bytes -- so group moves
# and REDEFINES overlays meet by storage, not by name), and field_lineage follows
# a field through the program, across CALL USING / COMMAREA storage, to the
# channel endpoints (FD records, SQL host variables, DL/I I/O areas, CICS
# FILE / MAP / QUEUE / CONTAINER records).
# Since #3490, a COBOL `COPY <mapset>` that no real copybook answers gets the
# symbolic map its BMS source generates (core/bms_symbolic.py, parsed by the
# record parser; EngineFile.symbolic_copies, never in `files`), so screen fields
# resolve to storage; GalaxyIR.symbolic_map_layouts lists every generated map.
# Since #3496, the web-services assistant JCL (web_service_data, per
# EngineFile.web_services): GalaxyIR.api_surface joins each service's program
# and request / response copybooks, with the CSD's URIMAP / PIPELINE /
# WEBSERVICE / TCPIPSERVICE definitions.
# Since #3494, the CSD's REMOTESYSTEM definitions and call sites' SYSID
# (call_site_data.sysid): GalaxyIR.remote_programs / remote_calls (DPL, remote
# START) / remote_resources (function-shipped FILE / TD / TS queues).
# Since #3493, GalaxyIR.dynamic_call_targets lists the programs a data-name LINK /
# XCTL / CALL can name (its VALUE, an OCCURS table over a VALUE-filled REDEFINES,
# MOVEd literals), GalaxyIR.navigation is the CICS program-to-program flow, and
# completeness counts a data-name site as resolved when a candidate is here.
# Since #3492 the file-I/O verbs are data moves too (READ INTO: the FD record ->
# the area; WRITE FROM: the area -> the record), an FD's 01 records share one
# storage key, and they carry a field's offset as a group MOVE does.
# NOT in the DB, so still owned by the forge tools:
# reachability-based dead code. `usage_status` is a same-file "name mentioned
# elsewhere" test, not reachability -- it is carried as data and must not be fed
# to dead-code masking. See docs/refraction_engine_differential.md for the
# measured deltas.
# ==============================================================================
import fnmatch
import os
import re
import sqlite3
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Subsystem hit columns carried per file. They are rule-hit counts, not block
# counts: arch_io/arch_ipc mix EXEC SQL, EXEC DLI, CICS verbs and CALL.
SIGNAL_COLUMNS = ("arch_io", "arch_ipc", "arch_ui_framework", "arch_concurrency", "def_listeners")

# The IBM mainframe language family (#2516). hlasm is detected but is a
# wrap-or-retire boundary, not a migration target (#3122 scope note 1).
MAINFRAME_LANGUAGES = ("cobol", "jcl", "bms", "pli", "db2_sql", "rexx", "hlasm", "csd")

# #3211-followup: the call_site_data verbs whose target is a TRANSACTION, not a
# program. They ride in call_site_data next to program invocations, so
# unresolved_calls() must not count them as unresolved program calls -- their
# target resolves through the transaction map, never the PROGRAM-ID index.
# Kept local (not imported from gitgalaxy.core) so this reader stays loadable
# against any master DB without pulling in the engine; the producer's canonical
# copy is mainframe_boundary.TRANSACTION_ROUTING_VERBS.
TRANSACTION_ROUTING_VERBS = ("RETURN TRANSID", "START TRANSID", "RUN TRANSID")


@dataclass
class EngineUnit:
    name: str
    start_line: int
    loc: int
    usage_status: int


@dataclass
class EngineCall:
    """One invocation site (#3200): COBOL CALL, CICS LINK/XCTL, JCL EXEC PGM=.

    `target` is the program NAME (a literal as written, or an identifier read
    through its working-storage VALUE clause) and is None when even the name
    could not be determined. `resolves_to` is the repository file declaring that
    PROGRAM-ID, and is None for a Language Environment service, a system utility
    or any program that simply is not in this repository. Both Nones are data,
    not gaps: they are what the old pipeline's `unresolved_calls` was about.
    """

    verb: str
    form: str
    operand: Optional[str]
    target: Optional[str]
    resolves_to: Optional[str]
    line: int
    # #3355: the COMMAREA contract operands of a CICS LINK/XCTL/RETURN TRANSID
    # site, as written (upper-cased, whitespace-collapsed): the record passed and
    # the LENGTH/DATALENGTH expressions. None when the site states none, and on a
    # DB written before the columns existed.
    commarea: Optional[str] = None
    commarea_length: Optional[str] = None
    commarea_datalength: Optional[str] = None
    # #3454: a batch CALL's USING list, comma-joined by position (call_using.py).
    using_args: Optional[str] = None
    # #3494: a CICS LINK / START's SYSID(...) as written (the region it ships to).
    sysid: Optional[str] = None

    @property
    def using(self) -> list:
        """The USING arguments in order (`CONTENT:X` / `VALUE:X` keep their mode)."""
        return [a for a in (self.using_args or "").split(",") if a]


@dataclass
class EngineEntryPoint:
    """A program entry point (#3454), from `entry_point_data`: the PROCEDURE
    DIVISION or an `ENTRY 'X'`, with its USING `params` (comma-joined, or None)."""

    kind: str
    entry_name: Optional[str]
    params: Optional[str]
    line: int

    @property
    def parameters(self) -> list:
        return [p for p in (self.params or "").split(",") if p]


@dataclass
class EngineDataset:
    """One dataset boundary fact (#3201).

    A COBOL row is a `SELECT ... ASSIGN` with the OPEN modes actually used
    (`internal_name`, `dd_name`, `modes`); a JCL row is a DD binding
    (`step_name`, `dd_name`, `dsn`). Joining the two on `dd_name` is the
    dataset lineage -- see `GalaxyIR.dataset_lineage`.
    """

    step_name: Optional[str]
    internal_name: Optional[str]
    assign_name: Optional[str]
    dd_name: str
    modes: list
    dsn: Optional[str]
    line: int
    # #3345: the JCL DSN with its symbols resolved (None unless every one did) and
    # how -- literal / resolved / proc_default / ambiguous / unresolved. Both None
    # on a COBOL row and on a DB written before the columns existed.
    dsn_resolved: Optional[str] = None
    dsn_resolution: Optional[str] = None

    @property
    def is_binding(self) -> bool:
        """True for a JCL DD -> dataset binding, False for a COBOL SELECT."""
        return self.dsn is not None

    @property
    def dataset_name(self) -> Optional[str]:
        """The dataset this binding names, for joining bindings ACROSS jobs (#3345).

        The resolved DSN when this file determined it (`literal`/`resolved`), the
        raw DSN when it names no symbol (a DB written before #3345), and None
        otherwise: a `proc_default`, `ambiguous` or `unresolved` DSN is not a name
        two jobs can be said to share -- a caller elsewhere may bind something else.
        """
        if not self.is_binding:
            return None
        if self.dsn_resolution in ("literal", "resolved"):
            return self.dsn_resolved
        if self.dsn_resolution is None and "&" not in (self.dsn or ""):
            return self.dsn
        return None


@dataclass
class EngineDataItem:
    """One DATA DIVISION data description entry (#3246).

    A flat record straight out of `record_data`, plus the `children` the reader
    threads onto it so callers can walk the `01/05/10/...` tree. `section` is the
    owning DATA DIVISION section (WORKING-STORAGE / LINKAGE / LOCAL-STORAGE /
    FILE); `fd_name` is the FILE SECTION `FD`/`SD` a `01` binds to, None outside
    the FILE SECTION. `pic`/`usage`/`value` are None on a group item; `occurs_max`
    is None when the item is not a table, and `occurs_depending_on` names the
    controlling item of a variable-length OCCURS. `redefines` names the item this
    one overlays. Levels 66/88 describe the item above them and never carry
    children.

    PL/I DECLAREd structures (#3250) ride the same shape: `usage` is the data type
    as written (`FIXED DEC(7,2)`, `CHAR(10) VARYING`), `section` the root's storage
    class, `redefines` the DEFINED base, `occurs_depending_on` the REFER name, and
    `attributes` the item's full attribute text (None for COBOL).
    """

    ordinal: int
    parent_ordinal: Optional[int]
    level: int
    name: str
    section: Optional[str]
    fd_name: Optional[str]
    pic: Optional[str]
    usage: Optional[str]
    occurs_min: Optional[int]
    occurs_max: Optional[int]
    occurs_depending_on: Optional[str]
    redefines: Optional[str]
    value: Optional[str]
    line: int
    children: list = field(default_factory=list)  # EngineDataItem
    attributes: Optional[str] = None  # #3250: PL/I attribute text; None for COBOL
    # #3355: the COPY member(s) that expand right after this entry, comma-separated
    # (`01 DFHCOMMAREA.` + `COPY INQCUST.` -> 'INQCUST'); None when no COPY follows.
    copy_members: Optional[str] = None

    @property
    def is_group(self) -> bool:
        """A group item has subordinate items and no PIC or data type of its own.

        A PL/I elementary item carries its type in `usage` with no PIC
        (`2 NAME CHAR(17)`, #3250), so a missing PIC alone does not make a group;
        a childless root with no type of its own (`01 REC.` + COPY, a PL/I
        `1 B01 BASED(P), %INCLUDE ...`) still does.
        """
        if self.level in (66, 88):
            return False
        return bool(self.children) or not (self.pic or self.usage)

    @property
    def occurs(self) -> Optional[int]:
        """The (max) table size, or None when the item is not a table."""
        return self.occurs_max


@dataclass
class EngineTransaction:
    """One CICS transaction definition (#3211-followup).

    A `DEFINE TRANSACTION(TTTT) ... PROGRAM(PPPP)` in a CSD deck (or a PROGRAM
    autoinstall `TRANSID(...)` pairing). `transid` is the 4-char id a user
    submits; `program` is the PROGRAM-ID it routes to as written; `resolves_to`
    is the repository file declaring that PROGRAM-ID, or None for a program this
    repository does not contain (a system transaction or an external module).
    This dataclass hangs off the DEFINING deck's EngineFile; the join to the
    program it entry-points is `GalaxyIR.transaction_map`.
    """

    transid: str
    program: Optional[str]
    group: Optional[str]
    profile: Optional[str]
    resolves_to: Optional[str]
    line: int


@dataclass
class EngineSqlColumn:
    """One column of a DB2 `EXEC SQL DECLARE <table> TABLE (...)` (#3344).

    `colno` is the 1-based column position (SYSCOLUMNS.COLNO). `sql_type` is the
    type as written (`DECIMAL`, `VARCHAR`, `TIMESTAMP WITH TIME ZONE`); `length`
    the length/precision (LOB K/M/G applied) and `scale` the DECIMAL scale, both
    None when the source writes none. `attributes` is the column-option text
    after the type (`NOT NULL WITH DEFAULT`, `FOR BIT DATA`).
    """

    colno: int
    name: str
    sql_type: str
    length: Optional[int]
    scale: Optional[int]
    nullable: bool
    attributes: Optional[str]
    line: int


@dataclass
class EngineSqlTable:
    """One declared DB2 table (#3344): its name as declared and its columns in order.

    Hangs off the file that DECLAREs it -- usually a DCLGEN copybook/include
    member, which a program reaches through its `EXEC SQL INCLUDE` edge
    (copy_deps); joining the two is the consumer's job, as for record layouts.
    """

    name: str
    line: int
    columns: list = field(default_factory=list)  # EngineSqlColumn


@dataclass
class EngineSqlStatement:
    """One (embedded SQL statement, table) row (#3446), flat out of
    `sql_statement_data`. `table` is None for a statement naming none (OPEN /
    FETCH / CLOSE a cursor, COMMIT, CALL); `access` is read / insert / update /
    delete / merge / lock. Rows of one statement share `ordinal`."""

    ordinal: int
    verb: str
    table: Optional[str]
    access: Optional[str]
    cursor: Optional[str]
    host_variables: list
    line: int


@dataclass
class EngineScreenField:
    """One BMS macro statement of a map source (#3347): a DFHMSD mapset, a DFHMDI
    map or a DFHMDF field, flat out of `screen_field_data`.

    `kind` is 'mapset' | 'map' | 'field'; `parent_ordinal` is a map's mapset and a
    field's map. `name` is None for an unnamed field -- a screen literal, which
    occupies a position but never reaches the symbolic map (`is_symbolic`).
    `pos_line`/`pos_column` come from `POS=(line,col)` (a scalar `POS=n` stays in
    `attributes`), `attrb` is the ATTRB list without parentheses, `initial` the
    INITIAL literal's content. `attributes` keeps every other operand as written
    (COLOR=, HILIGHT=, a map's SIZE=, a mapset's MODE=/LANG=, ...).
    """

    kind: str
    ordinal: int
    parent_ordinal: Optional[int]
    name: Optional[str]
    pos_line: Optional[int]
    pos_column: Optional[int]
    length: Optional[int]
    attrb: Optional[str]
    picin: Optional[str]
    picout: Optional[str]
    initial: Optional[str]
    occurs: Optional[int]
    attributes: Optional[str]
    line: int

    @property
    def is_symbolic(self) -> bool:
        """A named field: one that becomes `<name>L/F/A/I/O` in the symbolic map."""
        return self.kind == "field" and bool(self.name)


@dataclass
class EngineCsdResource:
    """One CSD `DEFINE <type>(<name>)` record, of any resource type (#3356).

    Hangs off the DEFINING deck (a `.csd` file, or a JCL job carrying a DFHCSDUP
    SYSIN deck inline). The attributes that join the online system to something
    else are lifted out -- `dsname` (FILE/TDQUEUE DSNAME, LIBRARY DSNAME01),
    `ddname` (TDQUEUE), `record_format`/`key_length`/`record_size`, `queue_type`
    (TDQUEUE TYPE), `plan` (DB2ENTRY/DB2CONN), `db2_entry` (DB2TRAN ENTRY),
    `transid` and `program` -- and `attributes` is the record's full operand text.
    Nothing is resolved: the joins are `GalaxyIR.cics_file_datasets`,
    `tdqueue_datasets` and `transaction_db2_plans`.
    """

    resource_type: str
    name: str
    group: Optional[str]
    dsname: Optional[str]
    ddname: Optional[str]
    record_format: Optional[str]
    key_length: Optional[int]
    record_size: Optional[int]
    queue_type: Optional[str]
    plan: Optional[str]
    db2_entry: Optional[str]
    transid: Optional[str]
    program: Optional[str]
    attributes: Optional[str]
    line: int


@dataclass
class EngineCicsResource:
    """One EXEC CICS command that names a resource (#3351-#3354), from `cics_resource_data`.

    `kind` is FILE | MAP | QUEUE | CONTAINER | CHANNEL -- or WEB | SERVICE |
    TRANSFORM (#3512; a WEB row's qualifier is CLIENT | SERVER) -- and `access` its
    direction (read | write | update | delete | browse | unlock | move | pass;
    open | converse | close | invoke | encode | decode). `operand` is
    the name operand as written; `name` its resolved value -- the literal, the
    data-name's VALUE, or the single literal MOVEd to it (`resolution` says which)
    -- and None when that is `ambiguous` (the MOVEd literals are in `candidates`),
    `unresolved` or an `expression`. `qualifier` is a MAP's mapset, a QUEUE's
    TS/TD, a CONTAINER's channel, or the program/transaction a CHANNEL is passed
    to; `qualifier_operand` the same operand as written (None for a QUEUE).
    `record` is the INTO/FROM/SET data area (`record_clause` says which).
    """

    verb: str
    kind: str
    access: str
    operand: Optional[str]
    name: Optional[str]
    resolution: Optional[str]
    candidates: Optional[str]
    qualifier_operand: Optional[str]
    qualifier: Optional[str]
    record_clause: Optional[str]
    record: Optional[str]
    attributes: Optional[str]
    line: int

    @property
    def names(self) -> set:
        """Every name this command can touch: its resolved name, or its MOVE candidates."""
        if self.name:
            return {self.name.upper()}
        return {c.upper() for c in (self.candidates or "").split(",") if c}

    @property
    def mapset(self) -> Optional[str]:
        """A MAP's mapset: MAPSET as resolved, or -- when the command writes no
        MAPSET -- the map name itself, which is the CICS default."""
        if self.kind != "MAP":
            return None
        return self.qualifier if self.qualifier_operand else self.name


@dataclass
class EngineCicsTask:
    """One CICS task-control command (#3449), flat out of `cics_task_data`.

    `verb` is RUN | START | START ATTACH | FETCH CHILD | FETCH ANY | FREE CHILD |
    RETRIEVE | CANCEL | DELAY | POST | WAIT EVENT | WAIT EXTERNAL | WAITCICS |
    ENQ | DEQ. `target_kind` is TRANSID or RESOURCE; `name` the target resolved
    (literal / VALUE / MOVE / the one literal a STRING builds) and None when
    `resolution` is `pattern` / `ambiguous` / `unresolved` / `expression` --
    `candidates` then holds the MOVEd literals and STRING-built fnmatch patterns.
    `channel` is CHANNEL resolved (passed by RUN/START, returned by FETCH),
    `token` the CHILD / ANY / REQID data-name, `record` the FROM/INTO/SET area.
    """

    verb: str
    target_kind: Optional[str]
    operand: Optional[str]
    name: Optional[str]
    resolution: Optional[str]
    candidates: Optional[str]
    channel_operand: Optional[str]
    channel: Optional[str]
    token: Optional[str]
    record_clause: Optional[str]
    record: Optional[str]
    timing: Optional[str]
    attributes: Optional[str]
    line: int

    def matches(self, name: str) -> bool:
        """Whether `name` can be this command's target: the resolved name, or a
        candidate literal / fnmatch pattern."""
        want = name.upper()
        if self.name:
            return self.name.upper() == want
        return any(fnmatch.fnmatchcase(want, c.upper()) for c in (self.candidates or "").split(",") if c)


@dataclass
class EngineJobSubmit:
    """One piece of job-submission evidence (#3448), from `job_submit_data`.

    `kind` JOB: a COBOL literal job card, `name` the job name. `kind` EXEC: a
    COBOL literal EXEC card, `step` its step and `target` the PROC / PGM
    (`target_kind`). `kind` INTRDR: a JCL DD routed to the internal reader,
    `step` / `name` its step and ddname, `target` the step's SYSUT1 DSN.
    """

    kind: str
    step: Optional[str]
    name: Optional[str]
    target_kind: Optional[str]
    target: Optional[str]
    line: int


@dataclass
class EngineMqCall:
    """One IBM MQ call (#3447), from `mq_call_data`.

    `queue` is the queue name when one literal determines it; otherwise
    `resolution` says why not -- `trigger` (the queue whose MQ trigger started the
    transaction, MQTM-QNAME), `reply_to` (the requester's MQMD-REPLYTOQ),
    `ambiguous` (`candidates`) or `unresolved`. A PUT/GET/CLOSE inherits both from
    the MQOPEN its `handle` was matched to (`open_line`).
    """

    verb: str
    direction: Optional[str]
    operand: Optional[str]
    queue: Optional[str]
    resolution: Optional[str]
    candidates: Optional[str]
    handle: Optional[str]
    open_line: Optional[int]
    options: Optional[str]
    line: int


@dataclass
class EngineUowHandler:
    """One unit-of-work point, handler, explicit ABEND or RESP check (#3453),
    from `uow_handler_data` (see core/uow_handlers.py for the kinds).

    `condition` is the handled condition / AID key, an ABEND's ABCODE, or a
    RESP_CHECK's tested DFHRESP names comma-joined (None: the result is never
    tested). `target` is a handler paragraph (`target_kind` LABEL) or program.
    """

    kind: str
    source: str
    verb: str
    condition: Optional[str]
    target: Optional[str]
    target_kind: Optional[str]
    resp_var: Optional[str]
    attributes: Optional[str]
    line: int


@dataclass
class EngineFileControl:
    """One FILE-CONTROL SELECT (#3455), from `file_control_data`. `organization`
    is None when the clause is absent (COBOL's default is SEQUENTIAL);
    `alternate_keys` is a list of (data-name, with_duplicates)."""

    select_name: str
    assign: Optional[str]
    organization: Optional[str]
    access_mode: Optional[str]
    record_key: Optional[str]
    alternate_keys: list
    relative_key: Optional[str]
    file_status: Optional[str]
    fd_copies: list
    line: int


@dataclass
class EngineVsamDefine:
    """One IDCAMS DEFINE CLUSTER / AIX / PATH (#3455), from `vsam_define_data`.
    `related` is an AIX's RELATE base cluster or a PATH's PATHENTRY."""

    kind: str
    name: Optional[str]
    organization: Optional[str]
    key_length: Optional[int]
    key_offset: Optional[int]
    record_avg: Optional[int]
    record_max: Optional[int]
    related: Optional[str]
    unique_key: Optional[str]
    upgrade: Optional[str]
    step: Optional[str]
    line: int


@dataclass
class EngineJobFlow:
    """One JOB / STEP / DD row of a JCL file's job flow (#3451), from `job_flow_data`
    (see core/job_flow.py). `dsn` is as written without its GDG `generation`."""

    kind: str
    name: Optional[str]
    step_ordinal: Optional[int]
    step_name: Optional[str]
    program: Optional[str]
    proc: Optional[str]
    cond: Optional[str]
    if_cond: Optional[str]
    in_proc: Optional[str]
    dd_name: Optional[str]
    dsn: Optional[str]
    disp: Optional[str]
    generation: Optional[str]
    line: int


@dataclass
class EngineDliCall:
    """One IMS DL/I call (#3450), from `dli_call_data`, operands as written
    (see core/dli_calls.py); resolution is GalaxyIR.ims_calls'."""

    interface: str
    function: Optional[str]
    function_operand: Optional[str]
    pcb: Optional[str]
    io_area: Optional[str]
    segments: Optional[str]
    ssas: Optional[str]
    where: Optional[str]
    psb: Optional[str]
    line: int


@dataclass
class EngineDataMove:
    """One source -> target pair of a data-moving statement (#3452), from
    `data_move_data` (see core/data_moves.py for the verbs and operand forms)."""

    verb: str
    source: Optional[str]
    source_kind: Optional[str]
    target: str
    corresponding: bool
    source_refmod: bool
    target_refmod: bool
    line: int


_WEB_FIELDS = ("assistant", "direction", "program", "uri", "request", "response", "interface", "container", "binding",
               "document", "transaction")  # fmt: skip


@dataclass
class EngineWebService:
    """One web-services assistant step (#3496), from `web_service_data` (see
    core/web_services.py): the program a provider exposes at `uri` (or a requester
    calls out from), its request / response copybook members, and the rest."""

    assistant: Optional[str]
    direction: Optional[str]
    program: Optional[str]
    uri: Optional[str]
    request: Optional[str]
    response: Optional[str]
    interface: Optional[str]
    container: Optional[str]
    binding: Optional[str]
    document: Optional[str]
    transaction: Optional[str]
    line: int


@dataclass
class EngineImsGen:
    """One IMS PSB / DBD macro statement or JCL IMS region step (#3477), from
    `ims_gen_data` (see core/ims_gen.py for the kinds)."""

    kind: str
    name: Optional[str]
    parent: Optional[str]
    owner: Optional[str]
    dbd_name: Optional[str]
    procopt: Optional[str]
    pcb_type: Optional[str]
    access: Optional[str]
    bytes: Optional[int]
    start: Optional[int]
    psb_name: Optional[str]
    program: Optional[str]
    attributes: Optional[str]
    line: int


@dataclass
class EngineFile:
    file_path: str
    language: str
    total_loc: int
    program_ids: list[str] = field(default_factory=list)
    units: list[EngineUnit] = field(default_factory=list)
    copy_deps: list[str] = field(default_factory=list)
    signals: dict[str, int] = field(default_factory=dict)
    calls: list = field(default_factory=list)  # EngineCall, #3200
    datasets: list = field(default_factory=list)  # EngineDataset, #3201
    data_items: list = field(default_factory=list)  # EngineDataItem, flat source order, #3246
    records: list = field(default_factory=list)  # EngineDataItem tree roots (01/77), #3246
    transactions: list = field(default_factory=list)  # EngineTransaction, #3211-followup
    sql_tables: list = field(default_factory=list)  # EngineSqlTable, #3344
    sql_statements: list = field(default_factory=list)  # EngineSqlStatement, source order, #3446
    screen_fields: list = field(default_factory=list)  # EngineScreenField, flat source order, #3347
    csd_resources: list = field(default_factory=list)  # EngineCsdResource, source order, #3356
    cics_resources: list = field(default_factory=list)  # EngineCicsResource, source order, #3351-#3354
    cics_tasks: list = field(default_factory=list)  # EngineCicsTask, source order, #3449
    job_submits: list = field(default_factory=list)  # EngineJobSubmit, source order, #3448
    mq_calls: list = field(default_factory=list)  # EngineMqCall, source order, #3447
    uow_handlers: list = field(default_factory=list)  # EngineUowHandler, source order, #3453
    file_control: list = field(default_factory=list)  # EngineFileControl, source order, #3455
    vsam_defines: list = field(default_factory=list)  # EngineVsamDefine, source order, #3455
    job_flow: list = field(default_factory=list)  # EngineJobFlow, source order, #3451
    entry_points: list = field(default_factory=list)  # EngineEntryPoint, source order, #3454
    dli_calls: list = field(default_factory=list)  # EngineDliCall, source order, #3450
    ims_gen: list = field(default_factory=list)  # EngineImsGen, source order, #3477
    data_moves: list = field(default_factory=list)  # EngineDataMove, source order, #3452
    web_services: list = field(default_factory=list)  # EngineWebService, source order, #3496
    # #3490: symbolic maps generated from BMS source for COPY members no real
    # copybook answers (EngineFile, file_path `<bms>#<MAPSET>`); never in `files`.
    symbolic_copies: list = field(default_factory=list)

    @property
    def is_program(self) -> bool:
        """A program carries a PROGRAM-ID (class_data). Units alone are not enough: a
        procedure copybook has paragraphs but is compiled into its includer."""
        return bool(self.program_ids)


@dataclass
class GalaxyIR:
    db_path: Path
    repo_name: str
    commit_hash: str
    files: dict[str, EngineFile]

    def programs(self, language: str = "cobol") -> list[EngineFile]:
        return sorted(
            (f for f in self.files.values() if f.language == language and f.is_program),
            key=lambda f: f.file_path,
        )

    def inventory(self, languages: tuple[str, ...] = MAINFRAME_LANGUAGES) -> dict[str, dict[str, int]]:
        """Per-language file and unit counts over `languages`, for files the engine extracted units from."""
        out: dict[str, dict[str, int]] = {}
        for f in self.files.values():
            if f.language not in languages or (not f.units and not f.program_ids):
                continue
            row = out.setdefault(f.language, {"files": 0, "units": 0})
            row["files"] += 1
            row["units"] += len(f.units)
        return dict(sorted(out.items(), key=lambda kv: -kv[1]["units"]))

    def dataset_lineage(self, language: str = "cobol") -> list:
        """Program P opens DD X for MODE; job J step S binds DD X to dataset D.

        #3201's question, answered from the DB alone. Each entry is a dict with
        `program`, `dd_name`, `modes`, `job`, `step` and `dsn`, plus (#3345)
        `dsn_resolved`/`dsn_resolution` and `dataset` -- the joinable name
        (`EngineDataset.dataset_name`), None unless this job determined it. A program DD
        that no job in the repository binds still appears, with `job`/`dsn`
        None: an unbound DD is a real finding (the dataset is allocated by a
        job that is not in this repository), not something to drop silently.

        The job is found through the `EXEC PGM=` call sites that resolve to the
        program, so this only reports a binding a real step actually made.
        """
        # ddname -> the JCL bindings for it, per (job path, step).
        bindings: dict[tuple[str, Optional[str], str], list] = {}
        for f in self.files.values():
            for ds in f.datasets:
                if ds.is_binding:
                    bindings.setdefault((f.file_path, ds.step_name, ds.dd_name), []).append(ds)

        # program path -> the (job, step) pairs that EXEC PGM= it.
        runners: dict[str, list] = {}
        for f in self.files.values():
            for call in f.calls:
                if call.verb == "EXEC PGM" and call.resolves_to:
                    runners.setdefault(call.resolves_to, []).append((f.file_path, None))

        out = []
        for f in sorted(self.files.values(), key=lambda x: x.file_path):
            if f.language != language:
                continue
            for ds in f.datasets:
                if ds.is_binding:
                    continue
                matched = False
                for job_path, _ in runners.get(f.file_path, []):
                    for (bj, bstep, bdd), bound in bindings.items():
                        if bj != job_path or bdd != ds.dd_name:
                            continue
                        for b in bound:
                            matched = True
                            out.append(
                                {
                                    "program": f.file_path,
                                    "dd_name": ds.dd_name,
                                    "modes": list(ds.modes),
                                    "job": bj,
                                    "step": bstep,
                                    "dsn": b.dsn,
                                    "dsn_resolved": b.dsn_resolved,
                                    "dsn_resolution": b.dsn_resolution,
                                    "dataset": b.dataset_name,
                                }
                            )
                if not matched:
                    out.append(
                        {
                            "program": f.file_path,
                            "dd_name": ds.dd_name,
                            "modes": list(ds.modes),
                            "job": None,
                            "step": None,
                            "dsn": None,
                            "dsn_resolved": None,
                            "dsn_resolution": None,
                            "dataset": None,
                        }
                    )
        return out

    def shared_datasets(self) -> dict[str, list]:
        """Dataset -> every JCL binding of it, for datasets bound by 2+ jobs (#3345).

        The job-to-job half of lineage: `JOB1 //OUT DD DSN=&HLQ..DAILY` and `JOB2
        //IN DD DSN=PROD.DAILY` are the same dataset once JOB1's HLQ resolves, and
        only then. Keyed by the dataset NAME with any member/generation suffix
        dropped (`LIB(SAM1)` and `LIB(SAM2)` are one library; `X(+1)`/`X(0)` one
        GDG). Each binding: `job`, `step`, `dd_name`, `dsn` (as written) and
        `dsn_resolved`. Only joinable names take part (`EngineDataset.dataset_name`).
        """
        by_name: dict[str, list] = {}
        for f in sorted(self.files.values(), key=lambda x: x.file_path):
            for ds in f.datasets:
                name = ds.dataset_name
                if name:
                    by_name.setdefault(name.split("(", 1)[0], []).append(
                        {
                            "job": f.file_path,
                            "step": ds.step_name,
                            "dd_name": ds.dd_name,
                            "dsn": ds.dsn,
                            "dsn_resolved": ds.dsn_resolved,
                        }
                    )
        return {n: b for n, b in sorted(by_name.items()) if len({x["job"] for x in b}) > 1}

    def dataset_flows(self, language: str = "cobol") -> list:
        """Program -> program data flow through a shared dataset (#3345).

        Writer W opens a DD for OUTPUT/EXTEND/I-O and its job binds that DD to
        dataset D; reader R opens a DD for INPUT/I-O and ITS job binds that DD to
        the same D. Built on `dataset_lineage`, joined on the resolved dataset
        name, so two programs whose jobs spell D through different symbols
        (`&HLQ..DAILY` under `SET HLQ=PROD`, and `PROD.DAILY`) are linked, and two
        whose DSNs could not be resolved are not. Each flow: `dataset`, `writer`,
        `reader`, and the `writer_job`/`reader_job` that made each binding.
        """
        writers: dict[str, list] = {}
        readers: dict[str, list] = {}
        for e in self.dataset_lineage(language):
            if not e["dataset"]:
                continue
            name = e["dataset"].split("(", 1)[0]
            modes = set(e["modes"])
            if modes & {"OUTPUT", "EXTEND", "I-O"}:
                writers.setdefault(name, []).append(e)
            if modes & {"INPUT", "I-O"}:
                readers.setdefault(name, []).append(e)
        flows = []
        for name in sorted(writers):
            for w in writers[name]:
                for r in readers.get(name, []):
                    if w["program"] == r["program"]:
                        continue
                    flows.append(
                        {
                            "dataset": name,
                            "writer": w["program"],
                            "writer_job": w["job"],
                            "reader": r["program"],
                            "reader_job": r["job"],
                        }
                    )
        return flows

    def unresolved_calls(self) -> list:
        """Every call site that did not reach a file in this repository (#3200).

        Each entry carries `file`, `verb`, `form`, `operand`, `target` and
        `line`. `target is None` means the program name itself was unreadable (a
        dynamic CALL whose VALUE clause is in a copybook); a `target` with no
        resolution is an external program -- an LE service, a system utility, or
        a module this repository does not contain.
        """
        out = []
        for f in sorted(self.files.values(), key=lambda x: x.file_path):
            for call in f.calls:
                if call.resolves_to:
                    continue
                # A TRANSID-routing verb's target is a transaction, not a
                # program: it is never an unresolved PROGRAM call. Its
                # transaction is joined by transaction_map, not counted here.
                if call.verb in TRANSACTION_ROUTING_VERBS:
                    continue
                out.append(
                    {
                        "file": f.file_path,
                        "verb": call.verb,
                        "form": call.form,
                        "operand": call.operand,
                        "target": call.target,
                        "line": call.line,
                    }
                )
        return out

    def transaction_map(self, language: str = "cobol") -> list:
        """The CICS transaction map: which transaction entry-points into which program.

        #3211-followup's question, answered from the DB alone. Each entry is a
        dict with `transid`, `program` (the PROGRAM-ID as the CSD wrote it),
        `resolves_to` (the program's file, or None when the program is not in
        this repository), `group`, `profile`, `defined_in` (the CSD/JCL deck the
        DEFINE lives in) and `line`.

        `language` filters the RESOLVED program's language: with the default a
        transaction whose program is a COBOL file in the repo is reported, and so
        is one whose program does not resolve at all (an external module is still
        a real front door). A transaction that resolves to a non-`language` file
        is dropped. The COBOL in-source routing (RETURN/START/RUN TRANSID) is the
        other half and reads directly off each program's `EngineFile.calls`.
        """
        out = []
        for f in sorted(self.files.values(), key=lambda x: x.file_path):
            for txn in f.transactions:
                if txn.resolves_to is not None:
                    target = self.files.get(txn.resolves_to)
                    if target is not None and target.language != language:
                        continue
                out.append(
                    {
                        "transid": txn.transid,
                        "program": txn.program,
                        "resolves_to": txn.resolves_to,
                        "group": txn.group,
                        "profile": txn.profile,
                        "defined_in": f.file_path,
                        "line": txn.line,
                    }
                )
        out.sort(key=lambda t: (t["transid"], t["program"] or "", t["defined_in"]))
        return out

    def csd_resources(self, resource_type: Optional[str] = None) -> list:
        """Every CSD resource definition in the repository (#3356), optionally one type.

        Each entry is a dict of the EngineCsdResource fields plus `defined_in` (the
        deck). `resource_type` is matched upper-case (`"FILE"`, `"DB2TRAN"`).
        """
        want = resource_type.upper() if resource_type else None
        return [
            {**r.__dict__, "defined_in": f.file_path}
            for f in sorted(self.files.values(), key=lambda x: x.file_path)
            for r in f.csd_resources
            if want is None or r.resource_type == want
        ]

    def _bindings_by_dataset(self) -> dict[str, list]:
        """Joinable dataset name (member/generation suffix dropped) -> its JCL DD bindings."""
        by_name: dict[str, list] = {}
        for f in sorted(self.files.values(), key=lambda x: x.file_path):
            for ds in f.datasets:
                name = ds.dataset_name
                if name:
                    by_name.setdefault(name.split("(", 1)[0], []).append(
                        {
                            "job": f.file_path,
                            "step": ds.step_name,
                            "dd_name": ds.dd_name,
                            "dsn": ds.dsn,
                            "dsn_resolved": ds.dsn_resolved,
                        }
                    )
        return by_name

    def _programs_by_dataset(self) -> dict[str, list]:
        """Joinable dataset name -> the batch programs whose lineage reaches it."""
        by_name: dict[str, list] = {}
        for e in self.dataset_lineage():
            if e["dataset"]:
                by_name.setdefault(e["dataset"].split("(", 1)[0], []).append(
                    {"program": e["program"], "dd_name": e["dd_name"], "modes": e["modes"], "job": e["job"]}
                )
        return by_name

    def cics_file_datasets(self) -> list:
        """CICS file name -> dataset, joined to the batch dataset lineage (#3356).

        A CSD `DEFINE FILE(F) ... DSNAME(D)` is how CICS names a dataset: an
        online program's `EXEC CICS READ FILE('F')` reads D. Each entry carries the
        CICS side (`file`, `group`, `dsname`, `record_format`, `key_length`,
        `record_size`, `defined_in`, `line`) and the batch side joined on the
        dataset NAME (`dataset_data`, #3201, through the #3345 resolved DSN):
        `bindings` -- every JCL DD that binds D (`job`, `step`, `dd_name`, `dsn`,
        `dsn_resolved`) -- and `batch_programs` -- every program whose
        `dataset_lineage` reaches D (`program`, `dd_name`, `modes`, `job`). A FILE
        no job in the repository binds still appears with both lists empty: the
        dataset is maintained outside this repository, a real finding. A FILE
        with no DSNAME (resolved at run time from the region's DD) has
        `dsname` None and joins nothing.
        """
        bindings = self._bindings_by_dataset()
        programs = self._programs_by_dataset()
        out = []
        for r in self.csd_resources("FILE"):
            key = (r["dsname"] or "").split("(", 1)[0]
            out.append(
                {
                    "file": r["name"],
                    "group": r["group"],
                    "dsname": r["dsname"],
                    "record_format": r["record_format"],
                    "key_length": r["key_length"],
                    "record_size": r["record_size"],
                    "defined_in": r["defined_in"],
                    "line": r["line"],
                    "bindings": list(bindings.get(key, [])) if key else [],
                    "batch_programs": list(programs.get(key, [])) if key else [],
                }
            )
        return out

    def tdqueue_datasets(self) -> list:
        """Extrapartition transient-data queue -> dataset (#3356).

        A `DEFINE TDQUEUE(Q) TYPE(EXTRA)` is a sequential dataset CICS writes or
        reads: either named outright (`DSNAME(D)`, `via` "dsname", joined to JCL
        bindings of D exactly as `cics_file_datasets` does) or through a DD of the
        CICS region's own startup JCL (`DDNAME(X)`, `via` "ddname"). For the
        latter, `bindings` lists every JCL DD in the repository named X -- CANDIDATE
        region bindings, since nothing in the CSD says which job starts the region;
        empty when the region JCL is not in the repository (the usual case). Only
        TYPE(EXTRA) queues: an intrapartition queue lives in CICS's own DFHINTRA
        and an INDIRECT one names another queue, not a dataset.
        """
        by_name = self._bindings_by_dataset()
        by_dd: dict[str, list] = {}
        for f in sorted(self.files.values(), key=lambda x: x.file_path):
            for ds in f.datasets:
                if ds.is_binding:
                    by_dd.setdefault(ds.dd_name.upper(), []).append(
                        {
                            "job": f.file_path,
                            "step": ds.step_name,
                            "dd_name": ds.dd_name,
                            "dsn": ds.dsn,
                            "dsn_resolved": ds.dsn_resolved,
                        }
                    )
        out = []
        for r in self.csd_resources("TDQUEUE"):
            if r["queue_type"] != "EXTRA":
                continue
            if r["dsname"]:
                via, bound = "dsname", by_name.get(r["dsname"].split("(", 1)[0], [])
            elif r["ddname"]:
                via, bound = "ddname", by_dd.get(r["ddname"], [])
            else:
                via, bound = None, []
            out.append(
                {
                    "queue": r["name"],
                    "group": r["group"],
                    "dsname": r["dsname"],
                    "ddname": r["ddname"],
                    "record_format": r["record_format"],
                    "record_size": r["record_size"],
                    "via": via,
                    "bindings": list(bound),
                    "defined_in": r["defined_in"],
                    "line": r["line"],
                }
            )
        return out

    def transaction_db2_plans(self) -> list:
        """Transaction -> DB2 plan, through DB2TRAN -> DB2ENTRY (#3356).

        `DEFINE DB2TRAN(N) ENTRY(E) TRANSID(T)` assigns transaction T to the
        DB2ENTRY E, and `DEFINE DB2ENTRY(E) PLAN(P)` gives E its plan; a DB2ENTRY
        may also name one transaction itself (`DB2ENTRY(E) TRANSID(T) PLAN(P)`,
        `via` "db2entry" -- `db2tran` None). Each entry: `transid` (possibly
        generic: `*` any run, `+` one character, as CICS matches them), `db2tran`,
        `db2_entry`, `plan` (None when no DB2ENTRY of that name is defined, or it
        names its plan through PLANEXITNAME), `programs` -- the programs the
        matching transactions route to per `transaction_map` (empty when none is
        defined in this repository) -- and `group`/`defined_in`/`line` of the
        assigning record. A DB2ENTRY of the same GROUP is preferred when names
        collide across groups. A transaction with no DB2TRAN/DB2ENTRY runs on the
        DB2CONN pool thread; that plan is not attributed here -- which
        transactions issue SQL at all is not a CSD fact.
        """
        entries: dict[str, list] = {}
        for r in self.csd_resources("DB2ENTRY"):
            entries.setdefault(r["name"], []).append(r)
        routes: dict[str, list] = {}
        for t in self.transaction_map():
            if t["program"] and t["program"] not in routes.setdefault(t["transid"], []):
                routes[t["transid"]].append(t["program"])

        def _programs(transid: Optional[str]) -> list:
            if not transid:
                return []
            if "*" not in transid and "+" not in transid:
                return list(routes.get(transid, []))
            pattern = transid.replace("+", "?")  # CICS `+` is fnmatch `?`; `*` is the same
            matched: list = []
            for tid in sorted(routes):
                if fnmatch.fnmatchcase(tid, pattern):
                    matched += [p for p in routes[tid] if p not in matched]
            return matched

        out = []
        assignments = [(r, "db2tran", r["db2_entry"]) for r in self.csd_resources("DB2TRAN")]
        assignments += [(r, "db2entry", r["name"]) for r in self.csd_resources("DB2ENTRY") if r["transid"]]
        for r, via, entry_name in assignments:
            candidates = entries.get(entry_name or "", [])
            same_group = [e for e in candidates if e["group"] == r["group"]]
            entry = (same_group or candidates or [None])[0]
            out.append(
                {
                    "transid": r["transid"],
                    "via": via,
                    "db2tran": r["name"] if via == "db2tran" else None,
                    "db2_entry": entry_name,
                    "plan": entry["plan"] if entry else None,
                    "programs": _programs(r["transid"]),
                    "group": r["group"],
                    "defined_in": r["defined_in"],
                    "line": r["line"],
                }
            )
        out.sort(key=lambda e: (e["transid"] or "", e["defined_in"], e["line"]))
        return out

    # ---- #3355: the COMMAREA contract ----------------------------------------
    def _copybook_file(self, member: str, *contexts: EngineFile) -> Optional[EngineFile]:
        """The copybook file a `COPY member` in one of `contexts` resolved to.

        Read off each context's resolved COPY edges (copy_deps) by file stem, in
        order -- the file holding the COPY first, then the program it expands
        into. None when no edge names it (a system copybook, or one not in the
        repository): the layout is then reported unexpanded, never guessed.
        """
        for ctx in contexts:
            hits = [p for p in ctx.copy_deps if Path(p).stem.upper() == member]
            if len(hits) == 1 and hits[0] in self.files:
                return self.files[hits[0]]
        for ctx in contexts:  # #3490: a symbolic map generated from BMS source
            for sym in ctx.symbolic_copies:
                if sym.file_path.rsplit("#", 1)[-1] == member:
                    return sym
        return None

    # ---- #3498: skeleton completeness -------------------------------------------
    def completeness(self) -> dict:
        """How complete this scan's mainframe skeleton is, channel by channel (#3498).

        Each channel counts facts that resolved against everything else the scan
        holds, and splits the rest into `system` (a name the runtime or IBM
        supplies -- IDCAMS, DFHAID, EIBCALEN: not a gap) and named `gaps`:

          program calls   CALL / LINK / XCTL / EXEC PGM sites reaching a program in
                          the repository (a data-item target counts when a candidate
                          it can hold does, #3493); gaps: missing program, dynamic target,
                          non-COBOL program not linked (an engine gap)
          copybooks       COBOL COPY members answered by a copybook (or a generated
                          symbolic map, #3490); gap: missing copybook
          transactions    CICS programs a transaction, a LINK / XCTL / START or a
                          web service (#3496) reaches, and CSD transactions whose
                          program exists;
                          gaps: CICS program no transaction reaches, transaction to
                          a missing program
          screens         SEND / RECEIVE MAP commands whose BMS source is scanned;
                          gaps: missing BMS source, dynamic map name
          data flows      data moves (#3452) with both operands resolved to storage
          IMS PSBs        DL/I programs whose PSB is defined in the repository
          batch entry     batch main programs (no CICS, not CALLed) a JCL step runs

        `missing_inputs` turns the gaps into what to ask the estate owner for
        (docs/mainframe_ingestion_checklist.md): per input the gap count and up to
        five examples. `score` is the mean of the channel ratios (channels with no
        facts are left out), a coarse 0-1 summary -- read the channels.
        """
        cobol = [f for f in self.files.values() if f.language == "cobol"]
        programs = [f for f in cobol if f.is_program]
        channels: dict = {}
        examples: dict = {}

        def note(inp: str, example: str) -> None:
            examples.setdefault(inp, []).append(example)

        # Program calls (JCL EXEC PGM included).
        calls = [(f, c) for f in self.files.values() for c in f.calls if c.verb not in TRANSACTION_ROUTING_VERBS]
        # A callee in a language calls are not resolved to (not a copybook or JCL
        # of the same name -- CBSA ships NEWACCNO.cpy and NEWACCNO.jcl, not the program).
        any_stem = {Path(p).stem.upper() for p, f in self.files.items() if f.language in _CALLEE_LANGUAGES}
        dynamic = self.dynamic_call_targets()
        # A data-item target resolves when some candidate it can hold is a program here (#3493).
        dyn_ok = {
            (d["copybook"] or d["file"], d["line"]) for d in dynamic if any(c["resolves_to"] for c in d["candidates"])
        }
        ch: dict = {"resolved": 0, "total": 0, "system": 0,
              "gaps": {"missing program": 0, "dynamic target": 0, "non-COBOL program not linked": 0}}  # fmt: skip
        for f, c in calls:
            if c.resolves_to:
                ch["resolved"] += 1
            elif c.target and _SYSTEM_PROGRAM.match(c.target.upper()):
                ch["system"] += 1
                continue
            elif c.target and c.target.upper() in any_stem:
                # The program IS in the repository, in a language calls are not
                # resolved to (assembler, PL/I): an engine gap, not a missing input.
                ch["gaps"]["non-COBOL program not linked"] += 1
            elif c.target:
                ch["gaps"]["missing program"] += 1
                note("application programs (source or load-module list)", f"{c.target} ({f.file_path}:{c.line})")
            elif (f.file_path, c.line) in dyn_ok:
                ch["resolved"] += 1
            else:
                ch["gaps"]["dynamic target"] += 1
            ch["total"] += 1
        channels["program calls"] = ch

        # Copybooks.
        stems = {Path(p).stem.upper() for p, f in self.files.items() if f.language == "cobol"}
        ch = {"resolved": 0, "total": 0, "system": 0, "gaps": {"missing copybook": 0}}
        for f in cobol:
            members = {m for it in f.data_items for m in (it.copy_members or "").split(",") if m}
            sym = {s.file_path.rsplit("#", 1)[-1] for s in f.symbolic_copies}
            for m in sorted(members):
                if m in stems or m in sym:
                    ch["resolved"] += 1
                elif _SYSTEM_COPYBOOK.match(m):
                    ch["system"] += 1
                    continue
                else:
                    ch["gaps"]["missing copybook"] += 1
                    note("copybook libraries", f"{m} ({f.file_path})")
                ch["total"] += 1
        channels["copybooks"] = ch

        # Transactions: CICS programs reachable, CSD programs present.
        tmap = self.transaction_map()
        reached = {t["resolves_to"] for t in tmap if t["resolves_to"]}
        reached |= {c.resolves_to for f in self.files.values() for c in f.calls if c.resolves_to and c.verb != "CALL"}
        reached |= {
            c["resolves_to"] for d in dynamic if d["verb"] != "CALL" for c in d["candidates"] if c["resolves_to"]
        }
        # #3496: a program a web / JSON service exposes is a front door too.
        reached |= {
            s["program_file"]
            for s in self.api_surface()["services"]
            if s["program_file"] and s["direction"] == "provider"
        }
        for c in (c for f in self.files.values() for c in f.calls if c.verb in TRANSACTION_ROUTING_VERBS):
            prog = self._transaction_program(c.target) if c.target else None
            if prog:
                reached.add(prog)
        cics = [f for f in programs if f.cics_resources or f.cics_tasks or any(c.verb in _CONTRACT_VERBS for c in f.calls)
                or any(r.name == "DFHCOMMAREA" for r in f.records)]  # fmt: skip
        ch = {"resolved": 0, "total": 0, "system": 0,
              "gaps": {"CICS program no transaction reaches": 0, "transaction to a missing program": 0}}  # fmt: skip
        for f in cics:
            ch["total"] += 1
            if f.file_path in reached:
                ch["resolved"] += 1
            else:
                ch["gaps"]["CICS program no transaction reaches"] += 1
                note("CSD extract (DFHCSDUP LIST / CICSPlex SM), or the web / API layer that LINKs it", f.file_path)
        for t in tmap:
            ch["total"] += 1
            if t["resolves_to"]:
                ch["resolved"] += 1
            elif t["program"] and _SYSTEM_PROGRAM.match(t["program"].upper()):
                ch["system"] += 1
                ch["total"] -= 1
            else:
                ch["gaps"]["transaction to a missing program"] += 1
                note(
                    "application programs (source or load-module list)", f"{t['program']} (transaction {t['transid']})"
                )
        channels["transactions"] = ch

        # Screens.
        ops = self.screen_bindings()
        ch = {"resolved": sum(1 for o in ops if o["bms_file"]), "total": len(ops), "system": 0,
              "gaps": {"missing BMS source": 0, "dynamic map name": 0}}  # fmt: skip
        for o in ops:
            if o["bms_file"]:
                continue
            if not o["map"]:
                ch["gaps"]["dynamic map name"] += 1  # MAP(ws-item): nothing to ask for
            else:
                ch["gaps"]["missing BMS source"] += 1
                note("BMS map sources", f"{o['mapset']}/{o['map']} ({o['program']}:{o['line']})")
        channels["screens"] = ch

        # Data flows.
        flows = self.data_flows()
        status = {k: sum(1 for fl in flows if fl["status"] == k) for k in ("resolved", "system")}
        ch = {"resolved": status["resolved"], "total": len(flows) - status["system"], "system": status["system"],
              "gaps": {"unresolved operand": sum(1 for fl in flows if fl["status"] not in ("resolved", "system"))}}  # fmt: skip
        channels["data flows"] = ch

        # IMS PSBs.
        checks = self.ims_access_check()
        progs: dict = {}
        for c in checks:
            progs[c["file"]] = progs.get(c["file"], True) and c["status"] != "no_psb"
        ch = {"resolved": sum(1 for ok in progs.values() if ok), "total": len(progs), "system": 0,
              "gaps": {"DL/I program with no PSB": sum(1 for ok in progs.values() if not ok)}}  # fmt: skip
        for path, ok in sorted(progs.items()):
            if not ok:
                note("PSB / DBD generation sources", path)
        channels["IMS PSBs"] = ch

        # Batch entry: batch main programs a JCL step runs.
        run = set()
        for job in self.job_steps():
            for st in job["steps"]:
                for step in [st, *(st.get("expands_to") or [])]:
                    if step.get("program"):
                        run.add(step["program"].upper())
        called = {c.resolves_to for f in self.files.values() for c in f.calls if c.resolves_to and c.verb == "CALL"}
        batch = [f for f in programs if f not in cics and f.file_path not in called]
        ch = {"resolved": 0, "total": 0, "system": 0, "gaps": {"batch program no JCL step runs": 0}}
        for f in batch:
            ch["total"] += 1
            if any(pid.upper() in run for pid in f.program_ids):
                ch["resolved"] += 1
            else:
                ch["gaps"]["batch program no JCL step runs"] += 1
                note("JCL and PROC libraries", f.file_path)
        channels["batch entry"] = ch

        for ch in channels.values():
            ch["ratio"] = round(ch["resolved"] / ch["total"], 4) if ch["total"] else None
        ratios = [c["ratio"] for c in channels.values() if c["ratio"] is not None]
        missing = [
            {"input": inp, "count": len(ex), "examples": sorted(set(ex))[:5]}
            for inp, ex in sorted(examples.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        ]
        if len(self.job_steps()) > 1:
            missing.append({"input": "scheduler export (CA-7 / Control-M / TWS)", "count": len(self.job_steps()),
                            "examples": ["cross-job order is not in the repository"]})  # fmt: skip
        return {
            "score": round(sum(ratios) / len(ratios), 4) if ratios else None,
            "channels": channels,
            "missing_inputs": missing,
        }

    # ---- #3496: the web / API surface --------------------------------------------
    def api_surface(self) -> dict:
        """The estate's web / API surface (#3496).

        `services`: one entry per web-services assistant step (core/web_services.py)
        -- `defined_in`, `line`, `assistant`, `direction` (provider | requester),
        `uri`, `program` and `program_file` (the PROGRAM-ID's file, or None),
        `request` / `response` (copybook members) with `request_file` /
        `response_file` (the copybook, or None), `interface`, `binding`,
        `document`. `csd`: the CSD definitions that serve HTTP -- every URIMAP,
        PIPELINE, WEBSERVICE and TCPIPSERVICE, with `name`, `group`, `defined_in`
        and its kept `attributes` (a URIMAP's PATH / PROGRAM / PIPELINE).

        #3512, the program side. `invocations`: one per EXEC CICS INVOKE SERVICE /
        WEBSERVICE -- `defined_in`, `line`, `verb`, `service` (resolved, else None),
        `operand`, `channel`, `requester` (the `defined_in:line` of every requester
        step whose WSBIND file is named after the service: an installed web service
        takes its wsbind file's name) and `csd` (the file defining a CSD WEBSERVICE
        of that name, or None). Each service carries `invoked_by`, the files that
        INVOKE it (a requester's callers; empty for a provider). `http`: one per
        program and side of a hand-coded EXEC CICS WEB exchange -- `file`, `side`
        (SERVER: a hand-written HTTP provider; CLIENT: an outbound session),
        `commands` and the resolved `endpoints` (URIMAP / HOST / PATH / header names)."""
        by_pid = {pid.upper(): f.file_path for f in self.files.values() if f.is_program for pid in f.program_ids}
        copybooks: dict = {}
        for path, f in self.files.items():
            if f.language == "cobol" and not f.is_program:
                copybooks.setdefault(Path(path).stem.upper(), []).append(path)

        def book(member: Optional[str]) -> Optional[str]:
            hits = copybooks.get((member or "").upper(), [])
            return hits[0] if len(hits) == 1 else None

        services = [
            {"defined_in": f.file_path, "line": w.line, "assistant": w.assistant, "direction": w.direction,
             "uri": w.uri, "program": w.program, "program_file": by_pid.get((w.program or "").upper()),
             "request": w.request, "request_file": book(w.request), "response": w.response,
             "response_file": book(w.response), "interface": w.interface, "binding": w.binding,
             "document": w.document, "invoked_by": []}
            for f in sorted(self.files.values(), key=lambda x: x.file_path)
            for w in f.web_services
        ]  # fmt: skip
        csd = [
            {
                "type": r.resource_type,
                "name": r.name,
                "group": r.group,
                "defined_in": f.file_path,
                "attributes": r.attributes,
            }
            for f in sorted(self.files.values(), key=lambda x: x.file_path)
            for r in f.csd_resources
            if (r.resource_type or "").upper() in ("URIMAP", "PIPELINE", "WEBSERVICE", "TCPIPSERVICE")
        ]
        requesters: dict = {}
        for svc in services:
            if svc["direction"] == "requester" and svc["binding"]:
                stem = re.split(r"[/\\]", svc["binding"])[-1].rsplit(".", 1)[0].upper()
                requesters.setdefault(stem, []).append(svc)
        csd_ws = {(c["name"] or "").upper(): c["defined_in"] for c in csd if (c["type"] or "").upper() == "WEBSERVICE"}
        invocations = []
        http: dict = {}
        for f in sorted(self.files.values(), key=lambda x: x.file_path):
            for op in f.cics_resources:
                if op.kind == "WEB":
                    entry = http.setdefault((f.file_path, op.qualifier), {"commands": 0, "endpoints": set()})
                    entry["commands"] += 1
                    if op.name:
                        entry["endpoints"].add(op.name)
                if op.kind != "SERVICE":
                    continue
                key = (op.name or "").upper()
                steps = requesters.get(key, []) if key else []
                for svc in steps:
                    if f.file_path not in svc["invoked_by"]:
                        svc["invoked_by"].append(f.file_path)
                invocations.append(
                    {
                        "defined_in": f.file_path,
                        "line": op.line,
                        "verb": op.verb,
                        "service": op.name,
                        "operand": op.operand,
                        "channel": op.qualifier,
                        "requester": [f"{s['defined_in']}:{s['line']}" for s in steps],
                        "csd": csd_ws.get(key) if key else None,
                    }
                )
        http_rows = [
            {"file": path, "side": side, "commands": e["commands"], "endpoints": sorted(e["endpoints"])}
            for (path, side), e in sorted(http.items(), key=lambda kv: (kv[0][0], kv[0][1] or ""))
        ]
        return {"services": services, "csd": csd, "invocations": invocations, "http": http_rows}

    def symbolic_map_layouts(self) -> dict:
        """Mapset -> {`file` (the BMS source), `items`: sorted `NAME @offset+bytes`}
        of every generated COBOL symbolic map (#3490): each named item, the I / O
        records included, at its byte offset from the start of the map record (an
        O item overlays the I record it REDEFINES; an OCCURS item's first
        occurrence, its group the whole array)."""
        out: dict = {}
        for mapset, sym in sorted(_symbolic_map_files(self.files).items()):
            spans = self._storage_spans(sym)
            items = {
                f"{it.name} @{spans[id(it)][1]}+{spans[id(it)][2]}"
                for it in sym.data_items
                if it.name != "FILLER" and it.level not in (66, 88) and id(it) in spans
            }
            out[mapset] = {"file": sym.file_path.rsplit("#", 1)[0], "items": sorted(items)}
        return out

    def _copy_files(self, ef: EngineFile) -> list:
        """The copybooks program `ef` COPYs: its resolved COPY edges, then the
        symbolic maps generated for the BMS mapsets it COPYs (#3490)."""
        return [self.files[p] for p in ef.copy_deps if p in self.files] + ef.symbolic_copies

    def _copy_roots(self, member: str, ef: EngineFile, origin: EngineFile, depth: int) -> tuple:
        """(copybook file, its record roots) for `COPY member`, or (None, [])."""
        cb = self._copybook_file(member, ef, origin) if depth < _COPY_DEPTH else None
        if cb is None:
            return None, []
        return cb, [r for r in cb.records if r.level not in (66, 88)]

    def _expanded_children(self, ef: EngineFile, item: EngineDataItem, origin: EngineFile, depth: int) -> list:
        """(file, item) children of `item` with every COPY member expanded in place.

        A COPY in a group's own window expands before that group's children
        (`01 DFHCOMMAREA.` + `COPY INQCUST.`); a COPY after an elementary child
        expands as that child's following siblings. Only copybook roots deeper
        than `item` join it. A COPY of records at `item`'s level or above CLOSES
        it: the copybook opened a new record, so the entries after the COPY
        belong to that record, not to `item` -- carddemo's `COPY COCOM01Y.` +
        `05 CDEMO-CPVD-INFO.` below `WS-FRAUD-DATA`, which the engine's same-file
        level stack (it cannot see the copybook's levels) threads under
        WS-FRAUD-DATA. A member that did not resolve comes back as (None, member)
        when it sits in `item`'s own window, so the caller can report it.
        """
        kids: list = []

        def _copies(owner: EngineDataItem) -> bool:
            """Append `owner`'s COPY members; True when one closes `item`."""
            for member in (owner.copy_members or "").split(","):
                if not member:
                    continue
                cb, roots = self._copy_roots(member, ef, origin, depth)
                if cb is None:
                    if owner is item:
                        kids.append((None, member))
                    continue
                if roots and all(r.level > item.level for r in roots):
                    kids.extend((cb, root) for root in roots)
                elif roots:
                    return True
            return False

        if not _is_elementary(item) and _copies(item):
            return kids
        for child in item.children:
            kids.append((ef, child))
            if _is_elementary(child) and _copies(child):
                break
        return kids

    def _copy_extension(self, ef: EngineFile, cb: EngineFile) -> list:
        """The entries of program `ef` that continue copybook `cb`'s LAST record.

        `COPY COCOM01Y.` (whose `01 CARDDEMO-COMMAREA` ends mid-record) followed
        by `05 CDEMO-CPVD-INFO.` in the program: the 05 continues the copied
        record. The engine threads it under whatever group was open before the
        COPY; this finds the entries after the closing COPY (see
        `_expanded_children`) so the copied record's layout can carry them.
        """
        member = Path(cb.file_path).stem.upper()
        roots = [r for r in cb.records if r.level not in (66, 88)]
        if not roots:
            return []
        by_ordinal = {it.ordinal: it for it in ef.data_items}
        for it in ef.data_items:
            if member not in (it.copy_members or "").split(","):
                continue
            group = it if not _is_elementary(it) else by_ordinal.get(it.parent_ordinal)
            if group is None or not all(r.level <= group.level for r in roots):
                continue
            if group is it:
                return [(ef, c) for c in it.children]
            siblings = group.children
            return [(ef, c) for c in siblings[siblings.index(it) + 1 :]] if it in siblings else []
        return []

    def record_layout(self, ef: EngineFile, item: EngineDataItem, extension: Optional[list] = None) -> dict:
        """One record's storage layout, COPY-expanded, from the DB alone (#3355).

        Returns `bytes` (None when any width is unknown), `variable` (an OCCURS
        DEPENDING ON inside it), `fields` (every elementary item in storage order:
        `name`, `level`, `pic`, `usage`, `class`, `offset`, `bytes`, `occurs`,
        `file`), `unexpanded` (COPY members that did not resolve to a copybook in
        the repository) and `copybooks` (the ones that did). A REDEFINES item
        overlays storage and is skipped, like 66/88 entries. Fields inside an
        OCCURS group are listed once; the group's width carries the repetition.
        `extension` is (file, item) entries appended to the record's own children
        (a copied record continued in the program -- `_copy_extension`).
        """
        fields: list = []
        unexpanded: list = []
        copybooks: list = []
        state = {"variable": False, "unknown": False}
        extension_files = sorted({f.file_path for f, _ in extension or []})

        def _walk(owner: EngineFile, it: EngineDataItem, offset: int, depth: int) -> int:
            if it.level in (66, 88):
                return 0
            if it.occurs_depending_on:
                state["variable"] = True
            times = it.occurs_max or 1
            # An elementary item's only children are its 88/66 conditions.
            kids = [] if _is_elementary(it) else self._expanded_children(owner, it, ef, depth)
            if it is item and extension:
                kids = kids + list(extension)
            if kids:
                size = 0
                for kid_file, kid in kids:
                    if kid_file is None:
                        unexpanded.append(kid)
                        state["unknown"] = True
                        continue
                    if kid_file is not owner and kid_file.file_path not in copybooks + extension_files:
                        copybooks.append(kid_file.file_path)
                    if kid.redefines or kid.level in (66, 88):
                        continue
                    size += _walk(kid_file, kid, offset + size, depth + (kid_file is not owner))
                return size * times
            width = _elementary_bytes(it)
            if width is None:
                state["unknown"] = True
                width = 0
            fields.append(
                {
                    "name": it.name,
                    "level": it.level,
                    "pic": it.pic,
                    "usage": it.usage,
                    "class": _item_class(it),
                    "offset": offset,
                    "bytes": width * times,
                    "occurs": it.occurs_max,
                    "file": owner.file_path,
                }
            )
            return width * times

        total = _walk(ef, item, 0, 0)
        return {
            "bytes": None if state["unknown"] else total,
            "variable": state["variable"],
            "fields": fields,
            "unexpanded": unexpanded,
            "copybooks": copybooks,
        }

    def _find_item(self, ef: EngineFile, name: str, qualifier: Optional[str]) -> list:
        """Every (file, item, extension) named `name` visible to program `ef`: its
        own DATA DIVISION first, then the copybooks it COPYs (an 01-level COPY
        carries the record's name only in the copybook -- carddemo's `COPY
        COCOM01Y`), with the entries `ef` continues that record with
        (`_copy_extension`) or None."""

        def _matches(owner: EngineFile) -> list:
            by_ordinal = {it.ordinal: it for it in owner.data_items}
            out = []
            for it in owner.data_items:
                if it.name != name or it.level in (66, 88):
                    continue
                if qualifier:
                    parent, seen = by_ordinal.get(it.parent_ordinal), 0
                    while parent is not None and parent.name != qualifier and seen < 64:
                        parent, seen = by_ordinal.get(parent.parent_ordinal), seen + 1
                    if parent is None:
                        continue
                out.append((owner, it, None))
            return out

        found = _matches(ef)
        if found:
            return found
        for cb in self._copy_files(ef):
            for owner, it, _ in _matches(cb):
                # The copied record the program continues past the COPY (its last root).
                last = [r for r in cb.records if r.level not in (66, 88)][-1:]
                found.append((owner, it, self._copy_extension(ef, cb) if last == [it] else None))
        return found

    def _dfhcommarea(self, callee: EngineFile) -> Optional[EngineDataItem]:
        """The callee's LINKAGE SECTION `01 DFHCOMMAREA`, or None."""
        for it in callee.records:
            if it.name == "DFHCOMMAREA" and (it.section or "LINKAGE") == "LINKAGE":
                return it
        return None

    def _transaction_program(self, transid: Optional[str]) -> Optional[str]:
        """The one program file a transaction id routes to, via the CSD map."""
        if not transid:
            return None
        hits = {t["resolves_to"] for t in self.transaction_map() if t["transid"] == transid and t["resolves_to"]}
        return hits.pop() if len(hits) == 1 else None

    def commarea_contracts(self, language: str = "cobol") -> list:
        """The COMMAREA contract of every CICS LINK/XCTL (and RETURN TRANSID) site (#3355).

        The caller passes record x (`COMMAREA(x)`); the callee receives it as its
        LINKAGE `DFHCOMMAREA`. Both are read from record_data with COPY members
        expanded (`record_layout`), and the callee is the site's existing call
        resolution (`EngineCall.resolves_to`; for RETURN TRANSID the transaction's
        program through the CSD map). One entry per site:

          caller, line, verb, target, callee, commarea, commarea_length,
          commarea_datalength,
          status          -- paired | no_commarea | callee_unresolved |
                             caller_record_unresolved | callee_no_dfhcommarea
          caller_record / callee_record
                          -- {name, file, bytes, variable, fields, unexpanded,
                             copybooks} (fields = elementary-item count), or None
          declared_length -- the LENGTH operand's byte count when it is a literal
          same_copybook   -- both layouts expand the same copybook(s)
          mismatches      -- [{kind, caller, callee}], kind in length |
                             declared_length | shape

        `paired` means both layouts were found; a mismatch is DATA for a
        modernizer to read, not a verdict -- a callee that declares
        `PIC X OCCURS 1 TO 32767 DEPENDING ON EIBCALEN` legitimately accepts any
        length, which is why `variable` rides beside every byte count and no
        length/shape mismatch is claimed against a variable-length side.
        """
        out = []
        for f in sorted(self.files.values(), key=lambda x: x.file_path):
            if f.language != language:
                continue
            for call in f.calls:
                if call.verb not in _CONTRACT_VERBS:
                    continue
                if call.verb == "RETURN TRANSID" and not call.commarea:
                    continue
                callee_path = (
                    self._transaction_program(call.target) if call.verb == "RETURN TRANSID" else call.resolves_to
                )
                entry: dict = {
                    "caller": f.file_path,
                    "line": call.line,
                    "verb": call.verb,
                    "target": call.target,
                    "callee": callee_path,
                    "commarea": call.commarea,
                    "commarea_length": call.commarea_length,
                    "commarea_datalength": call.commarea_datalength,
                    "status": None,
                    "caller_record": None,
                    "callee_record": None,
                    "declared_length": None,
                    "same_copybook": None,
                    "mismatches": [],
                }
                out.append(entry)
                name, qualifier = _operand_name(call.commarea)
                caller_layout = None
                if name:
                    found = self._find_item(f, name, qualifier)
                    if found:
                        owner, item, extension = found[0]
                        caller_layout = self.record_layout(owner, item, extension)
                        entry["caller_record"] = {
                            "name": item.name,
                            "file": owner.file_path,
                            **{k: caller_layout[k] for k in ("bytes", "variable", "unexpanded", "copybooks")},
                            "fields": len(caller_layout["fields"]),
                        }
                callee = self.files.get(callee_path) if callee_path else None
                callee_item = self._dfhcommarea(callee) if callee is not None else None
                callee_layout = None
                if callee is not None and callee_item is not None:
                    callee_layout = self.record_layout(callee, callee_item)
                    entry["callee_record"] = {
                        "name": callee_item.name,
                        "file": callee.file_path,
                        **{k: callee_layout[k] for k in ("bytes", "variable", "unexpanded", "copybooks")},
                        "fields": len(callee_layout["fields"]),
                    }
                if not call.commarea:
                    entry["status"] = "no_commarea"
                elif callee is None:
                    entry["status"] = "callee_unresolved"
                elif caller_layout is None:
                    entry["status"] = "caller_record_unresolved"
                elif callee_layout is None:
                    entry["status"] = "callee_no_dfhcommarea"
                else:
                    entry["status"] = "paired"

                declared, _ = _declared_length(call.commarea_length, name)
                entry["declared_length"] = declared
                if caller_layout and declared is not None and caller_layout["bytes"] not in (None, declared):
                    entry["mismatches"].append(
                        {"kind": "declared_length", "caller": caller_layout["bytes"], "callee": declared}
                    )
                if caller_layout is not None and callee_layout is not None and entry["status"] == "paired":
                    entry["same_copybook"] = bool(caller_layout["copybooks"]) and (
                        caller_layout["copybooks"] == callee_layout["copybooks"]
                    )
                    entry["mismatches"] += _layout_mismatches(caller_layout, callee_layout)
        return out

    # ---- #3351-#3354: CICS resource joins ------------------------------------
    def cics_resource_users(self, kind: str) -> dict[str, dict[str, list]]:
        """Resource name -> access -> the files that touch it, for one CICS `kind`
        (FILE | MAP | QUEUE | CONTAINER | CHANNEL). A QUEUE is keyed `TS:NAME` /
        `TD:NAME` (the two are separate namespaces). An `ambiguous` name counts
        under each of its MOVE candidates; an unresolved one under no name."""
        out: dict[str, dict[str, list]] = {}
        for f in sorted(self.files.values(), key=lambda x: x.file_path):
            for op in f.cics_resources:
                if op.kind != kind:
                    continue
                for name in sorted(op.names):
                    key = f"{op.qualifier}:{name}" if kind == "QUEUE" else name
                    users = out.setdefault(key, {}).setdefault(op.access, [])
                    if f.file_path not in users:
                        users.append(f.file_path)
        return dict(sorted(out.items()))

    def screen_bindings(self) -> list:
        """Program -> BMS map: every SEND/RECEIVE MAP joined to the map's screen fields.

        Each entry: `program`, `verb`, `map`, `mapset` (MAPSET, or the map name when
        the command writes none -- the CICS default), `record` (the FROM/INTO
        symbolic map), `line`, `bms_file` (the one BMS source defining that
        mapset's map, else None), `bms_candidates` (every such source) and
        `fields` (that map's EngineScreenField rows when `bms_file` is set). A map
        whose name did not resolve, or whose mapset no scanned BMS source defines,
        still appears with `bms_file` None -- that is a finding, not noise.
        """
        index: dict[tuple[str, str], list] = {}
        for f in sorted(self.files.values(), key=lambda x: x.file_path):
            if not f.screen_fields:
                continue
            by_ordinal = {sf.ordinal: sf for sf in f.screen_fields}
            for sf in f.screen_fields:
                if sf.kind != "map":
                    continue
                parent = by_ordinal.get(sf.parent_ordinal)
                mapset = (parent.name or "") if parent is not None and parent.kind == "mapset" else ""
                fields = [x for x in f.screen_fields if x.kind == "field" and x.parent_ordinal == sf.ordinal]
                index.setdefault((mapset.upper(), (sf.name or "").upper()), []).append((f.file_path, fields))
        out = []
        for f in sorted(self.files.values(), key=lambda x: x.file_path):
            for op in f.cics_resources:
                if op.kind != "MAP":
                    continue
                mapset = op.mapset
                hits = index.get(((mapset or "").upper(), (op.name or "").upper()), []) if op.name and mapset else []
                out.append(
                    {
                        "program": f.file_path,
                        "verb": op.verb,
                        "map": op.name,
                        "mapset": mapset,
                        "record": op.record,
                        "line": op.line,
                        "bms_file": hits[0][0] if len(hits) == 1 else None,
                        "bms_candidates": [h[0] for h in hits],
                        "fields": hits[0][1] if len(hits) == 1 else [],
                    }
                )
        return out

    def sql_table_access(self) -> list:
        """The program x DB2 table read/write matrix (#3446).

        One entry per (file, table): `file`, `table`, `accesses` (sorted: read /
        insert / update / delete / merge / lock), `lines` and `via_cursor` (the
        cursors through which the file reads it). A cursor's reads are counted
        where it is DECLAREd; an OPEN / FETCH of that cursor in the same file adds
        its lines. Statements in a copybook stay on the copybook, and joining
        them to the includer is the consumer's job (copy_deps), as for records.
        """
        out: list[dict] = []
        for f in self.files.values():
            if not f.sql_statements:
                continue
            cursor_tables: dict[str, list[str]] = {}
            for st in f.sql_statements:
                if st.verb == "DECLARE CURSOR" and st.cursor and st.table:
                    cursor_tables.setdefault(st.cursor, []).append(st.table)
            by_table: dict[str, dict] = {}
            for st in f.sql_statements:
                targets = [(st.table, st.access)] if st.table else []
                if not st.table and st.verb in ("OPEN", "FETCH") and st.cursor in cursor_tables:
                    targets = [(t, "read") for t in cursor_tables[st.cursor]]
                for table, access in targets:
                    row = by_table.setdefault(
                        table,
                        {"file": f.file_path, "table": table, "accesses": set(), "lines": [], "via_cursor": set()},
                    )
                    if access:
                        row["accesses"].add(access)
                    row["lines"].append(st.line)
                    if st.cursor and access == "read":
                        row["via_cursor"].add(st.cursor)
            for row in by_table.values():
                row["accesses"] = sorted(row["accesses"])
                row["via_cursor"] = sorted(row["via_cursor"])
                row["lines"] = sorted(set(row["lines"]))
                out.append(row)
        return out

    def queue_flows(self) -> list:
        """Program -> program data flow through a CICS TS/TD queue (#3353).

        Producer P WRITEQs queue Q and consumer C READQs the same queue of the same
        type (TS and TD are separate namespaces); P != C. Each flow: `queue`,
        `queue_type`, `producer`, `consumer`. Joined on the resolved name (or a
        MOVE candidate), so an unresolved queue name draws no flow."""
        flows: list[dict] = []
        for key, users in self.cics_resource_users("QUEUE").items():
            qtype, name = key.split(":", 1)
            # `users` is keyed by access direction: writers produce, readers consume.
            producers = [f for access, files in users.items() if access == "write" for f in files]
            consumers = [f for access, files in users.items() if access == "read" for f in files]
            flows.extend(
                {"queue": name, "queue_type": qtype, "producer": producer, "consumer": consumer}
                for producer in producers
                for consumer in consumers
                if producer != consumer
            )
        return flows

    def _cics_ops_lineage(self, kind: str, csd_join: str, key: str) -> list:
        """Program -> CICS resource of `kind` -> the CSD join `csd_join` (#3356).

        One entry per (program, resource name): `program`, `name`, `accesses` and
        `verbs` (sorted), `lines`, and `definitions` -- the `csd_join` rows whose
        `key` names this resource (their DSNAME, JCL `bindings` and, for files,
        `batch_programs`). `definitions` is empty when no CSD DEFINE in the
        repository names the resource.
        """
        by_name: dict[str, list] = {}
        for d in getattr(self, csd_join)():
            by_name.setdefault(str(d.get(key) or "").upper(), []).append(d)
        grouped: dict[tuple[str, str], dict] = {}
        for f in sorted(self.files.values(), key=lambda x: x.file_path):
            for op in f.cics_resources:
                if op.kind != kind or (kind == "QUEUE" and op.qualifier != "TD"):
                    continue
                for name in sorted(op.names):
                    entry = grouped.setdefault(
                        (f.file_path, name),
                        {"program": f.file_path, "name": name, "accesses": set(), "verbs": set(), "lines": []},
                    )
                    entry["accesses"].add(op.access)
                    entry["verbs"].add(op.verb)
                    entry["lines"].append(op.line)
        out = []
        for (_, name), e in sorted(grouped.items()):
            out.append(
                {
                    **e,
                    "accesses": sorted(e["accesses"]),
                    "verbs": sorted(e["verbs"]),
                    "definitions": list(by_name.get(name, [])),
                }
            )
        return out

    def cics_file_lineage(self) -> list:
        """Online program -> CICS FILE -> dataset -> batch jobs and programs (#3351 + #3356).

        Every program's EXEC CICS file operations, grouped per (program, file),
        joined on the file name to `cics_file_datasets()` (the CSD `DEFINE FILE ...
        DSNAME` and, through the dataset name, the JCL bindings and batch programs
        that touch the same dataset). This closes transaction -> program -> file ->
        dataset. A file no CSD defines keeps `definitions` empty.
        """
        return self._cics_ops_lineage("FILE", "cics_file_datasets", "file")

    def tdqueue_lineage(self) -> list:
        """Online program -> TD queue -> extrapartition dataset (#3353 + #3356).

        Every WRITEQ/READQ/DELETEQ TD grouped per (program, queue), joined on the
        queue name to `tdqueue_datasets()` (TYPE(EXTRA) queues: DSNAME, or the
        region DDNAME with candidate JCL bindings). Intrapartition and undefined
        queues keep `definitions` empty.
        """
        return self._cics_ops_lineage("QUEUE", "tdqueue_datasets", "queue")

    def _program_file(self, name: Optional[str]) -> Optional[str]:
        """The file declaring PROGRAM-ID `name`, when exactly one does."""
        if not name:
            return None
        hits = [f.file_path for f in self.files.values() if name.upper() in {p.upper() for p in f.program_ids}]
        return hits[0] if len(hits) == 1 else None

    def _transaction_file(self, transid: Optional[str]) -> Optional[str]:
        """The program file a transaction id routes to (CSD map), when exactly one."""
        if not transid:
            return None
        hits = {
            t.resolves_to
            for f in self.files.values()
            for t in f.transactions
            if t.resolves_to and t.transid.upper() == transid.upper()
        }
        return next(iter(hits)) if len(hits) == 1 else None

    def container_flows(self) -> list:
        """Program -> program data flow through a CICS channel's containers (#3354).

        Producer P PUTs (or MOVEs) container K and consumer C GETs K; P != C. Each
        flow: `container`, `channel`, `producer`, `consumer` and `match`, how sure
        the channel side is:
          - `channel`: both commands name the same resolved channel;
          - `handoff`: C reads its CURRENT channel (no CHANNEL operand) and P hands
            a channel to C by LINK/XCTL PROGRAM(...) or START/RUN/RETURN TRANSID(...)
            with that channel -- or, the return leg, P writes its current channel
            and C handed P that channel; the invocation is resolved via PROGRAM-ID
            / the CSD transaction map;
          - `unverified`: the container names match but a channel is unresolved,
            or C reads its current channel and no handoff from P was resolved.
        Two resolved channels that differ never match. Containers match on the
        resolved name or a MOVE candidate (an `ambiguous` producer that PUTs one
        of CIPA..CIPI in a loop reaches every consumer of one of them).
        """
        handoffs: set[tuple[str, str, Optional[str]]] = set()
        for f in self.files.values():
            for op in f.cics_resources:
                if op.kind != "CHANNEL":
                    continue
                if op.verb in ("LINK", "XCTL"):
                    target = self._program_file(op.qualifier)
                else:
                    target = self._transaction_file(op.qualifier)
                if target:
                    handoffs.add((f.file_path, target, (op.name or "").upper() or None))
        puts, gets = [], []
        for f in sorted(self.files.values(), key=lambda x: x.file_path):
            for op in f.cics_resources:
                if op.kind != "CONTAINER" or not op.names:
                    continue
                channel = (op.qualifier or "").upper() or None
                entry = (f.file_path, op.names, channel, op.qualifier_operand is not None)
                if op.access in ("write", "move"):
                    puts.append(entry)
                elif op.access == "read":
                    gets.append(entry)
        rank = {"channel": 0, "handoff": 1, "unverified": 2}
        best: dict[tuple[str, str, str], dict] = {}

        def handed(src: str, dst: str, chan: Optional[str]) -> bool:
            return any(a == src and b == dst and (chan is None or c in (None, chan)) for a, b, c in handoffs)

        for p_file, p_names, p_chan, p_explicit in puts:
            for c_file, c_names, c_chan, c_explicit in gets:
                if p_file == c_file:
                    continue
                common = p_names & c_names
                if not common:
                    continue
                if p_chan and c_chan:
                    if p_chan != c_chan:
                        continue
                    match = "channel"
                elif (not c_explicit and handed(p_file, c_file, p_chan)) or (
                    not p_explicit and handed(c_file, p_file, c_chan)
                ):
                    match = "handoff"
                else:
                    match = "unverified"
                for name in common:
                    # One flow per (container, producer, consumer): the strongest match wins.
                    prior = best.get((name, p_file, c_file))
                    if prior is None or rank[match] < rank[prior["match"]]:
                        best[(name, p_file, c_file)] = {
                            "container": name,
                            "channel": p_chan or c_chan,
                            "producer": p_file,
                            "consumer": c_file,
                            "match": match,
                        }
        return [best[k] for k in sorted(best)]

    def async_tasks(self) -> list:
        """Every RUN / START / START ATTACH of a child transaction, joined (#3449).

        Each entry: `parent` (file), `verb`, `line`, `operand`, `resolution` and
        `candidates` as extracted, then
          - `children`: the CSD transactions the target can be -- the resolved
            name, or every defined transaction a candidate literal / pattern
            matches (`OCR[0-9]` -> OCR1..OCR5, never OCRA) -- each with its
            `transid`, `program` and `resolves_to` (the program's file or None);
          - `channel` and `containers`: the channel passed and the containers the
            parent PUTs/MOVEs on it (same resolved channel name);
          - `token` and `joins`: the FETCH CHILD / FREE CHILD with the same token,
            and every FETCH ANY in the parent (it can collect any child it RAN);
          - `retrieves`: for a START / START ATTACH, each child program's
            RETRIEVE (file, line, record) -- the other end of the START's data.
        A target no transaction matches keeps `children` empty: the child is
        outside this repository, or its id is not determined by the source.
        """
        txns = [(t, f) for f in self.files.values() for t in f.transactions]
        out = []
        for f in sorted(self.files.values(), key=lambda x: x.file_path):
            for op in f.cics_tasks:
                if op.verb not in ("RUN", "START", "START ATTACH"):
                    continue
                children = []
                seen = set()
                for t, _deck in sorted(txns, key=lambda x: (x[0].transid, x[1].file_path)):
                    key = (t.transid.upper(), (t.program or "").upper())
                    if key in seen or not op.matches(t.transid):
                        continue
                    seen.add(key)
                    children.append({"transid": t.transid, "program": t.program, "resolves_to": t.resolves_to})
                channel = (op.channel or "").upper() or None
                containers = sorted(
                    {
                        n
                        for r in f.cics_resources
                        if r.kind == "CONTAINER"
                        and r.access in ("write", "move")
                        and channel
                        and (r.qualifier or "").upper() == channel
                        for n in r.names
                    }
                )
                joins = []
                for j in f.cics_tasks:
                    if j.verb == "FETCH ANY" and op.verb == "RUN":
                        joins.append({"verb": j.verb, "line": j.line, "token": j.token, "match": "any"})
                    elif j.verb in ("FETCH CHILD", "FREE CHILD") and op.token and j.token == op.token:
                        joins.append({"verb": j.verb, "line": j.line, "token": j.token, "match": "token"})
                retrieves: list[dict] = []
                if op.verb != "RUN":
                    for c in children:
                        cf = self.files.get(c["resolves_to"] or "")
                        if cf is not None:
                            retrieves.extend(
                                {"file": cf.file_path, "line": r.line, "record": r.record}
                                for r in cf.cics_tasks
                                if r.verb == "RETRIEVE"
                            )
                out.append(
                    {
                        "parent": f.file_path,
                        "verb": op.verb,
                        "line": op.line,
                        "operand": op.operand,
                        "resolution": op.resolution,
                        "candidates": op.candidates,
                        "children": children,
                        "channel": op.channel,
                        "containers": containers,
                        "token": op.token,
                        "joins": joins,
                        "retrieves": retrieves,
                    }
                )
        return out

    def _jcl_member(self, name: Optional[str], proc: bool) -> tuple[Optional[str], list]:
        """(the one JCL file named `name`, every candidate). A PROC prefers a
        procedure member (`.prc`/`.proc`, or a `proc` directory); a job the rest."""
        if not name:
            return None, []
        hits = sorted(
            f.file_path
            for f in self.files.values()
            if f.language == "jcl" and Path(f.file_path).stem.upper() == name.upper()
        )

        def is_proc(p: str) -> bool:
            return Path(p).suffix.lower() in (".prc", ".proc") or "proc" in {x.lower() for x in Path(p).parts[:-1]}

        preferred = [p for p in hits if is_proc(p) == proc] or hits
        return (preferred[0] if len(preferred) == 1 else None), hits

    def job_submissions(self) -> list:
        """Every job submission to the internal reader the repository shows (#3448).

        Online -> batch (`via` 'tdq'): program P writes (`WRITEQ TD`) queue Q, and
        the CSD defines Q as an extrapartition TDQUEUE (TYPE(EXTRA)). That is a
        submission when either
          - `region_jcl`: some JCL in the repository routes Q's DDNAME to
            SYSOUT=(x,INTRDR) (the CICS region's own startup JCL), or
          - `job_card`: P holds a literal JCL job card -- it builds the job it
            writes (CardDemo CORPT00C: `//TRNRPT00 JOB`, `EXEC PROC=TRANREPT`).
        An extrapartition queue with neither is an ordinary output queue and is
        not reported.
        Batch -> batch (`via` 'intrdr_dd'): a JCL step routes a DD to
        SYSOUT=(x,INTRDR); the job it submits is the member of that step's SYSUT1
        library (`LIB(INTRDRJ2)`), resolved to the JCL file of that name.

        Each entry: `submitter` (file), `via`, `line`, `queue` / `ddname` (tdq) or
        `step` / `dd` / `source` (intrdr_dd), `transactions` (the CSD transactions
        that enter the submitter), `jobs` (job names), `runs` (each EXEC target
        with `kind`, `name`, `resolves_to`, `candidates`) and `evidence`.
        """
        intrdr_ddnames = {
            (j.name or "").upper() for f in self.files.values() for j in f.job_submits if j.kind == "INTRDR"
        }
        tdqs = {
            r.name.upper(): r
            for f in self.files.values()
            for r in f.csd_resources
            if r.resource_type == "TDQUEUE" and (r.queue_type or "").upper().startswith("EXTRA")
        }
        entry: dict[str, set[str]] = {}
        for f in self.files.values():
            for t in f.transactions:
                if t.resolves_to:
                    entry.setdefault(t.resolves_to, set()).add(t.transid.upper())
        out = []
        for f in sorted(self.files.values(), key=lambda x: x.file_path):
            jobs = [j.name for j in f.job_submits if j.kind == "JOB" and j.name]
            runs = []
            for j in f.job_submits:
                if j.kind == "EXEC":
                    one, cands = self._jcl_member(j.target, j.target_kind == "PROC")
                    runs.append({"kind": j.target_kind, "name": j.target, "resolves_to": one, "candidates": cands})
            for op in f.cics_resources:
                if op.kind != "QUEUE" or op.access != "write" or (op.qualifier or "").upper() != "TD":
                    continue
                for qname in sorted(op.names & set(tdqs)):
                    tdq = tdqs[qname]
                    evidence = []
                    if (tdq.ddname or "").upper() in intrdr_ddnames:
                        evidence.append("region_jcl")
                    if jobs:
                        evidence.append("job_card")
                    if not evidence:
                        continue
                    out.append(
                        {
                            "submitter": f.file_path,
                            "via": "tdq",
                            "line": op.line,
                            "queue": qname,
                            "ddname": tdq.ddname,
                            "transactions": sorted(entry.get(f.file_path, set())),
                            "jobs": jobs,
                            "runs": runs,
                            "evidence": evidence,
                        }
                    )
            for j in f.job_submits:
                if j.kind != "INTRDR":
                    continue
                member = None
                if j.target and "(" in j.target and j.target.endswith(")"):
                    member = j.target.rsplit("(", 1)[1][:-1]
                    member = None if member.lstrip("+-").isdigit() else member  # a GDG generation
                one, cands = self._jcl_member(member, False)
                out.append(
                    {
                        "submitter": f.file_path,
                        "via": "intrdr_dd",
                        "line": j.line,
                        "step": j.step,
                        "dd": j.name,
                        "source": j.target,
                        "transactions": [],
                        "jobs": [member] if member else [],
                        "runs": [{"kind": "JOB", "name": member, "resolves_to": one, "candidates": cands}]
                        if member
                        else [],
                        "evidence": ["sysout_intrdr"],
                    }
                )
        return out

    def mq_queues(self) -> list:
        """Every program's MQ queue endpoints (#3447): one entry per (file, queue,
        direction) for the calls that move messages -- MQPUT / MQPUT1 (`put`) and
        MQGET (`get`, or `browse` when opened for browse). `queue` is the name, or
        `<trigger>` / `<reply_to>` / `<ambiguous>` / `<unresolved>` for a queue the
        source does not name; `lines` are the calls."""
        out: dict[tuple[str, str, str], dict] = {}
        for f in sorted(self.files.values(), key=lambda x: x.file_path):
            opened = {q.line: q for q in f.mq_calls if q.verb == "MQOPEN"}
            for q in f.mq_calls:
                if q.verb not in ("MQPUT", "MQPUT1", "MQGET"):
                    continue
                direction = q.direction or ""
                if q.verb == "MQGET" and q.open_line in opened and opened[q.open_line].direction == "browse":
                    direction = "browse"
                name = q.queue or f"<{q.resolution or 'unresolved'}>"
                e = out.setdefault(
                    (f.file_path, name, direction),
                    {
                        "file": f.file_path,
                        "queue": name,
                        "direction": direction,
                        "resolution": q.resolution,
                        "lines": [],
                    },
                )
                e["lines"].append(q.line)
        return [out[k] for k in sorted(out)]

    def mq_flows(self) -> list:
        """Producer -> consumer pairs through a NAMED queue (#3447): a program that
        puts to Q and a different program that gets (or browses) Q. Runtime queues
        (`<trigger>`, `<reply_to>`) never pair: their names are not in the source."""
        ends = [e for e in self.mq_queues() if not e["queue"].startswith("<")]
        return [
            {"queue": p["queue"], "producer": p["file"], "consumer": c["file"], "mode": c["direction"]}
            for p in ends
            if p["direction"] == "put"
            for c in ends
            if c["direction"] in ("get", "browse") and c["queue"] == p["queue"] and c["file"] != p["file"]
        ]

    @staticmethod
    def _owning_unit(ef: EngineFile, line: int) -> Optional[str]:
        """The paragraph / section a line belongs to: the last unit starting at or before it."""
        owner = None
        for u in sorted(ef.units, key=lambda x: x.start_line):
            if u.start_line > line:
                break
            owner = u.name
        return owner

    def units_of_work(self) -> list:
        """Every commit / rollback point (#3453): `file`, `kind` (COMMIT |
        ROLLBACK), `source` (CICS | SQL), `verb`, `line` and the owning `unit`.
        The implicit commit at task end (EXEC CICS RETURN) is not a row."""
        return [
            {
                "file": f.file_path,
                "kind": u.kind,
                "source": u.source,
                "verb": u.verb,
                "line": u.line,
                "unit": self._owning_unit(f, u.line),
            }
            for f in sorted(self.files.values(), key=lambda x: x.file_path)
            for u in f.uow_handlers
            if u.kind in ("COMMIT", "ROLLBACK")
        ]

    def error_handlers(self) -> list:
        """Every HANDLE CONDITION / HANDLE ABEND / HANDLE AID (#3453) and PL/I ON unit (#3491): `file`,
        `kind`, `condition`, `target`, `target_kind`, `line`, the owning `unit`,
        and `handler_found` -- whether a LABEL target is a paragraph / section of
        the same program (None for a non-LABEL target)."""
        out = []
        for f in sorted(self.files.values(), key=lambda x: x.file_path):
            names = {u.name.upper() for u in f.units}
            for u in f.uow_handlers:
                # #3491: a PL/I ON unit is a handler too (target_kind SYSTEM / NULL /
                # BLOCK / PROCEDURE / LABEL / STATEMENT).
                if u.kind not in ("HANDLE_CONDITION", "HANDLE_ABEND", "HANDLE_AID", "ON_UNIT"):
                    continue
                # A PROCEDURE target, or a COBOL LABEL, is a unit; PL/I statement labels
                # are not, and nothing else has a target to look up.
                if u.target_kind == "PROCEDURE" or (u.target_kind == "LABEL" and f.language != "pli"):
                    found = (u.target or "").upper() in names
                else:
                    found = None
                out.append(
                    {
                        "file": f.file_path,
                        "kind": u.kind,
                        "condition": u.condition,
                        "target": u.target,
                        "target_kind": u.target_kind,
                        "line": u.line,
                        "unit": self._owning_unit(f, u.line),
                        "handler_found": found,
                    }
                )
        return out

    def unchecked_responses(self) -> list:
        """RESP-coded CICS commands whose result is never tested (#3453): `file`,
        `verb`, `resp_var`, `line` and the owning `unit`."""
        return [
            {
                "file": f.file_path,
                "verb": u.verb,
                "resp_var": u.resp_var,
                "line": u.line,
                "unit": self._owning_unit(f, u.line),
            }
            for f in sorted(self.files.values(), key=lambda x: x.file_path)
            for u in f.uow_handlers
            if u.kind == "RESP_CHECK" and not u.condition
        ]

    def tdq_trigger_starts(self) -> list:
        """Transactions CICS starts because a TD queue fills (#3453 add-on).

        A CSD `DEFINE TDQUEUE(Q) TRIGGERLEVEL(n) TRANSID(T)` makes CICS start T
        once n records sit on intrapartition queue Q, so every program that
        `WRITEQ TD`s Q implicitly starts T. Each entry: `writer` (file), `line`
        (the WRITEQ), `queue`, `trigger_level`, `transid`, `program` (the CSD
        transaction's program) and `resolves_to` (its file, or None).
        """
        triggered: dict[str, tuple[str, Optional[int]]] = {}
        for f in self.files.values():
            for r in f.csd_resources:
                if r.resource_type != "TDQUEUE" or not r.transid:
                    continue
                found = re.search(r"TRIGGERLEVEL\(\s*(\d+)\s*\)", r.attributes or "", re.I)
                triggered[r.name.upper()] = (r.transid.upper(), int(found.group(1)) if found else None)
        programs: dict[str, tuple] = {}
        for f in self.files.values():
            for t in f.transactions:
                programs.setdefault(t.transid.upper(), (t.program, t.resolves_to))
        out = []
        for f in sorted(self.files.values(), key=lambda x: x.file_path):
            for op in f.cics_resources:
                if op.kind != "QUEUE" or op.access != "write" or (op.qualifier or "").upper() != "TD":
                    continue
                for q in sorted(op.names & set(triggered)):
                    transid, level = triggered[q]
                    program, resolves_to = programs.get(transid, (None, None))
                    out.append(
                        {
                            "writer": f.file_path,
                            "line": op.line,
                            "queue": q,
                            "trigger_level": level,
                            "transid": transid,
                            "program": program,
                            "resolves_to": resolves_to,
                        }
                    )
        return out

    def _key_position(
        self, ef: EngineFile, fd_name: str, key: Optional[str], copies: Optional[list] = None
    ) -> tuple[Optional[int], Optional[int]]:
        """(byte offset, length) of data-name `key` inside the FD `fd_name`'s record:
        a 01 of the FD in the program, or a record of a COPY member inside the FD
        entry (`FD X. COPY Y.`). Offsets are from the record's start."""
        if not key:
            return None, None
        want = key.upper()
        roots = [(ef, r) for r in ef.records if (r.fd_name or "").upper() == fd_name.upper()]
        for member in copies or []:
            cb = self._copybook_file(member, ef)
            if cb is not None:
                roots += [(cb, r) for r in cb.records if r.level == 1]
        for owner, root in roots:
            layout = self.record_layout(owner, root)
            hit = next((x for x in layout["fields"] if x["name"].upper() == want), None)
            if hit:
                return hit["offset"], hit["bytes"]
            # A group key: the span of its elementary items.
            stack, target = [root], None
            while stack and target is None:
                it = stack.pop()
                if it.name.upper() == want:
                    target = it
                stack.extend(it.children)
            if target is None:
                continue
            names, stack = set(), list(target.children)
            while stack:
                it = stack.pop()
                names.add(it.name.upper())
                stack.extend(it.children)
            parts = [x for x in layout["fields"] if x["name"].upper() in names]
            if parts and all(x["bytes"] is not None for x in parts):
                return min(x["offset"] for x in parts), sum(x["bytes"] for x in parts)
            return None, None
        return None, None

    def vsam_files(self) -> list:
        """Every keyed FILE-CONTROL SELECT, checked against the VSAM it reads (#3455).

        For each SELECT with a RECORD KEY or RELATIVE KEY: `program`, `select`,
        `dd`, `organization`, `access_mode`, `record_key` with its `key_offset` /
        `key_length` in the FD record (None when unknown), `key_in_record` (False
        when the FD's record is known and the key is not one of its fields --
        a definition COBOL does not allow), `alternate_keys`
        (name, duplicates, offset, length), `datasets` (the datasets the DD is
        bound to by a job that runs the program), `defines` (every IDCAMS object of
        that name -- a PATH resolved to the AIX it opens), `key_match` (True / False
        when a CLUSTER or AIX key and the program key are both known, else None)
        and `csd_files` (CSD FILEs on that dataset with their key length).
        """
        defines: dict[str, list] = {}
        for f in self.files.values():
            for d in f.vsam_defines:
                if d.name:
                    defines.setdefault(d.name.upper(), []).append((d, f.file_path))
        csd_by_dsn: dict[str, list] = {}
        for f in self.files.values():
            for r in f.csd_resources:
                if r.resource_type == "FILE" and r.dsname:
                    csd_by_dsn.setdefault(r.dsname.upper(), []).append(r)
        lineage: dict[tuple[str, str], set] = {}
        for e in self.dataset_lineage():
            if e["dataset"]:
                lineage.setdefault((e["program"], e["dd_name"].upper()), set()).add(e["dataset"].upper())
        out = []
        for f in sorted(self.files.values(), key=lambda x: x.file_path):
            for sel in f.file_control:
                key = sel.record_key or sel.relative_key
                if not key:
                    continue
                offset, length = self._key_position(f, sel.select_name, key, sel.fd_copies)
                # COBOL requires the RECORD KEY to be a field of the file's own record.
                # False: the FD record is known and the key is not in it (CardDemo
                # CBEXPORT keys EXPORT-OUTPUT on a WORKING-STORAGE item).
                fd_known = any((r.fd_name or "").upper() == sel.select_name.upper() for r in f.records) or bool(
                    sel.fd_copies
                )
                key_in_record = True if offset is not None else (False if fd_known else None)
                alternates = []
                for name, dup in sel.alternate_keys:
                    a_off, a_len = self._key_position(f, sel.select_name, name, sel.fd_copies)
                    alternates.append({"name": name, "duplicates": dup, "offset": a_off, "length": a_len})
                datasets = sorted(lineage.get((f.file_path, (sel.assign or "").upper()), set()))
                found = []
                for ds in datasets:
                    for d, where in defines.get(ds, []):
                        # A PATH opens its AIX: its key is the AIX's key.
                        keyed = d
                        if d.kind == "PATH" and d.related:
                            keyed = next((a for a, _ in defines.get(d.related.upper(), []) if a.kind == "AIX"), d)
                        found.append(
                            {
                                "kind": d.kind,
                                "name": d.name,
                                "defined_in": where,
                                "key_length": keyed.key_length,
                                "key_offset": keyed.key_offset,
                            }
                        )
                comparable = [x for x in found if x["key_length"] is not None and length is not None]
                key_match = (
                    all(x["key_length"] == length and x["key_offset"] == offset for x in comparable)
                    if comparable
                    else None
                )
                csd = [
                    {
                        "file": r.name,
                        "key_length": r.key_length,
                        "match": (r.key_length == length) if r.key_length and length else None,
                    }
                    for ds in datasets
                    for r in csd_by_dsn.get(ds, [])
                ]
                out.append(
                    {
                        "program": f.file_path,
                        "select": sel.select_name,
                        "dd": sel.assign,
                        "organization": sel.organization,
                        "access_mode": sel.access_mode,
                        "record_key": key,
                        "key_in_record": key_in_record,
                        "key_offset": offset,
                        "key_length": length,
                        "alternate_keys": alternates,
                        "datasets": datasets,
                        "defines": found,
                        "key_match": key_match,
                        "csd_files": csd,
                    }
                )
        return out

    def _proc_steps(self, ef: EngineFile, proc: str) -> tuple[Optional[str], list]:
        """(defining file, STEP rows) of procedure `proc`: in-stream in `ef`, else the
        cataloged member of that name (a procedure member preferred)."""
        own = [r for r in ef.job_flow if r.kind == "STEP" and (r.in_proc or "").upper() == proc.upper()]
        if own:
            return ef.file_path, own
        member, _cands = self._jcl_member(proc, True)
        mf = self.files.get(member or "")
        if mf is None:
            return None, []
        return mf.file_path, [r for r in mf.job_flow if r.kind == "STEP" and r.in_proc]

    def job_steps(self) -> list:
        """Every job's steps in order (#3451): per JCL file with a JOB card, `file`,
        `job`, `cond` (JOB COND=) and `steps` -- `ordinal`, `step`, `program`, `proc`,
        `cond`, `if_cond`, `line`, and for a PROC call `proc_file` plus `expands_to`
        (the procedure's own steps with their program and conditions)."""
        out = []
        for f in sorted(self.files.values(), key=lambda x: x.file_path):
            job = next((r for r in f.job_flow if r.kind == "JOB"), None)
            if job is None:
                continue
            steps = []
            for r in f.job_flow:
                if r.kind != "STEP" or r.in_proc:
                    continue
                entry = {
                    "ordinal": r.step_ordinal,
                    "step": r.step_name,
                    "program": r.program,
                    "proc": r.proc,
                    "cond": r.cond,
                    "if_cond": r.if_cond,
                    "line": r.line,
                }
                if r.proc:
                    where, inner = self._proc_steps(f, r.proc)
                    entry["proc_file"] = where
                    entry["expands_to"] = [
                        {"step": s_.step_name, "program": s_.program, "cond": s_.cond, "if_cond": s_.if_cond}
                        for s_ in inner
                    ]
                steps.append(entry)
            out.append({"file": f.file_path, "job": job.name, "cond": job.cond, "steps": steps})
        return out

    def job_dataset_flow(self) -> list:
        """Dataset producer -> consumer edges across steps and jobs (#3451).

        A DD CREATES its dataset when DISP is NEW / MOD (the default with a DSN);
        it READS it when DISP is SHR / OLD -- whatever its GDG generation: a later
        step's `X(+1),DISP=SHR` reads the generation the job created. Edges
        join a creating DD to every reading DD of the same dataset (the resolved
        DSN from dataset_data where the engine resolved it; generation and member
        dropped), within a job only when the reader's step comes later. Temporary
        `&&` datasets and names with unresolved symbols are not joined. Each edge:
        `dataset`, `producer` / `consumer` (`file`, `step`, `dd`, `disp`,
        `generation`, `line`) and `same_job`.
        """
        resolved: dict[tuple[str, int], str] = {}
        for f in self.files.values():
            for ds in f.datasets:
                if ds.dsn_resolved:
                    resolved[(f.file_path, ds.line)] = ds.dsn_resolved.upper()
        creates, reads = [], []
        for f in sorted(self.files.values(), key=lambda x: x.file_path):
            for r in f.job_flow:
                if r.kind != "DD" or not r.dsn or r.dsn.startswith("&&"):
                    continue
                name = resolved.get((f.file_path, r.line), r.dsn)
                name = re.sub(r"\([+-]?[0-9]{1,3}\)$", "", name)
                if "&" in name:
                    continue
                end = {
                    "file": f.file_path,
                    "step": r.step_name,
                    "dd": r.dd_name,
                    "disp": r.disp,
                    "generation": r.generation,
                    "line": r.line,
                }
                # DISP decides, not the generation: a later step's `X(+1),DISP=SHR`
                # READS the generation an earlier step of the job created.
                if r.disp in ("NEW", "MOD"):
                    creates.append((name, end))
                elif r.disp in ("SHR", "OLD"):
                    reads.append((name, end))
        out = []
        for name, p in creates:
            for rname, c in reads:
                if rname != name:
                    continue
                same = p["file"] == c["file"]
                if same and c["line"] <= p["line"]:
                    continue
                out.append({"dataset": name, "producer": p, "consumer": c, "same_job": same})
        return out

    def _item_bytes(self, ef: EngineFile, operand: str) -> tuple[Optional[int], bool, Optional[str]]:
        """(bytes, variable, name) of one USING operand as seen from `ef`: a data
        item (COPY-expanded record_layout), a literal's own length, or (None, False,
        None) for ADDRESS OF / LENGTH OF / OMITTED and names not found."""
        text = operand.split(":", 1)[1] if operand.split(":", 1)[0] in ("CONTENT", "VALUE") else operand
        if text[:1] in "'\"":
            return len(text) - 2, False, text
        if text.startswith(("ADDRESS OF", "LENGTH OF")) or text == "OMITTED":
            return None, False, text
        name, _, qual = text.partition(" OF ")
        found = self._find_item(ef, name, qual.split(" OF ")[0] or None)
        if not found:
            return None, False, name
        owner, item, extension = found[0]
        layout = self.record_layout(owner, item, extension)
        return layout["bytes"], bool(layout["variable"]), name

    def call_contracts(self, language: str = "cobol") -> list:
        """Every batch CALL paired with its callee's USING parameters (#3454).

        One entry per CALL site that passes a USING list or reaches a program in the
        repository: `caller`, `line`, `target`, `callee` (file), `entry` (PROCEDURE,
        or the ENTRY literal the target names), `status` -- paired | arity_mismatch |
        callee_unresolved | callee_no_using | caller_no_using -- and `args`, one per
        position: `argument` / `parameter` as written with their `caller_bytes` /
        `callee_bytes` (None when not computable) and `length_match` (True / False
        when both are fixed-length and known, else None). A length difference is
        data for a modernizer, not a verdict: a callee may declare a larger area
        than the caller passes and only read part of it.
        """
        out = []
        for f in sorted(self.files.values(), key=lambda x: x.file_path):
            if f.language != language:
                continue
            for call in f.calls:
                if call.verb != "CALL" or not (call.using or call.resolves_to):
                    continue
                callee = self.files.get(call.resolves_to or "")
                entry = None
                if callee is not None:
                    named = [
                        e
                        for e in callee.entry_points
                        if e.kind == "ENTRY" and e.entry_name == (call.target or "").upper()
                    ]
                    entry = named[0] if named else next((e for e in callee.entry_points if e.kind == "PROCEDURE"), None)
                params = entry.parameters if entry else []
                if callee is None:
                    status = "callee_unresolved"
                elif not params and call.using:
                    status = "callee_no_using"
                elif params and not call.using:
                    status = "caller_no_using"
                elif len(params) != len(call.using):
                    status = "arity_mismatch"
                else:
                    status = "paired"
                args = []
                for i in range(max(len(call.using), len(params))):
                    a = call.using[i] if i < len(call.using) else None
                    p = params[i] if i < len(params) else None
                    a_bytes, a_var, _ = self._item_bytes(f, a) if a else (None, False, None)
                    p_bytes, p_var, _ = (
                        self._item_bytes(callee, p) if (p and callee is not None) else (None, False, None)
                    )
                    known = a_bytes is not None and p_bytes is not None and not a_var and not p_var
                    args.append(
                        {
                            "position": i + 1,
                            "argument": a,
                            "parameter": p,
                            "caller_bytes": a_bytes,
                            "callee_bytes": p_bytes,
                            "length_match": (a_bytes == p_bytes) if known else None,
                        }
                    )
                out.append(
                    {
                        "caller": f.file_path,
                        "line": call.line,
                        "target": call.target,
                        "callee": callee.file_path if callee is not None else None,
                        "entry": (entry.entry_name or entry.kind) if entry else None,
                        "status": status,
                        "args": args,
                    }
                )
        return out

    def _value_text(self, ef: EngineFile, name: Optional[str]) -> Optional[str]:
        """The text data-name `name` holds at load: its VALUE literal, or for a group
        its elementary children's VALUEs in order, each padded / cut to its width
        (`?` for a child with no VALUE). None when the item or a width is unknown."""
        if not name:
            return None
        found = self._find_item(ef, name.split(" OF ")[0], None)
        if not found:
            return None
        _owner, item, _ext = found[0]

        def lit(v: Optional[str], width: int) -> str:
            if v is None:
                return "?" * width
            u = v.strip()
            if u.upper() in ("SPACE", "SPACES"):
                return " " * width
            if u.upper() in ("ZERO", "ZEROS", "ZEROES"):
                return "0" * width
            if len(u) >= 2 and u[0] in "'\"" and u[-1] == u[0]:
                u = u[1:-1]
            return u.ljust(width)[:width]

        if not item.children:
            width = _elementary_bytes(item)
            return lit(item.value, width) if width else (item.value or "").strip("'\"") or None
        parts: list[str] = []

        def walk(it: EngineDataItem) -> bool:
            for child in it.children:
                if child.level in (66, 88) or child.redefines:
                    continue
                if child.children:
                    if not walk(child):
                        return False
                    continue
                width = _elementary_bytes(child)
                if width is None:
                    return False
                parts.append(lit(child.value, width))
            return True

        return "".join(parts) if walk(item) else ("".join(parts) or None)

    # ---- #3493: data-driven LINK / XCTL / CALL targets --------------------------
    def _table_values(self, ef: EngineFile, name: str) -> list:
        """The per-occurrence VALUEs of `name` when it is an element of an OCCURS
        table that REDEFINES a VALUE-filled group (carddemo COMEN02Y's
        CDEMO-MENU-OPT-PGMNAME over CDEMO-MENU-OPTIONS-DATA), else []."""
        found = self._find_item(ef, name, None)
        if len(found) != 1:
            return []
        owner, item, _ = found[0]
        by_ordinal = {it.ordinal: it for it in owner.data_items}
        chain, cur = [item], by_ordinal.get(item.parent_ordinal)
        while cur is not None and len(chain) < 64:
            chain.append(cur)
            cur = by_ordinal.get(cur.parent_ordinal)
        table = next((it for it in chain if it.occurs_max), None)
        base = next((it for it in chain[chain.index(table) :] if it.redefines), None) if table else None
        if table is None or base is None:
            return []
        text = self._value_text(owner, base.redefines)
        if not text:
            return []

        def width(it: EngineDataItem) -> Optional[int]:
            if not it.children:
                return _elementary_bytes(it)
            total = 0
            for c in it.children:
                if c.level in (66, 88) or c.redefines:
                    continue
                w = width(c)
                if w is None:
                    return None
                total += w * (c.occurs_max or 1)
            return total

        def offset_in(group: EngineDataItem, target: EngineDataItem) -> Optional[int]:
            off = 0
            for c in group.children:
                if c.level in (66, 88) or c.redefines:
                    continue
                if c is target:
                    return off
                if target in _descendants(c):
                    inner = offset_in(c, target)
                    return None if inner is None else off + inner
                w = width(c)
                if w is None:
                    return None
                off += w * (c.occurs_max or 1)
            return None

        per, size = width(table), _elementary_bytes(item)
        start = 0 if table is base else offset_in(base, table)
        inner = offset_in(table, item)
        if not per or not size or start is None or inner is None:
            return []
        out = []
        for i in range(table.occurs_max or 0):
            piece = text[start + i * per + inner : start + i * per + inner + size]
            if len(piece) == size and piece.strip() and "?" not in piece:
                out.append(piece.strip())
        return out

    # ---- #3494: remote programs and function shipping (DPL, SYSID, REMOTESYSTEM) --
    def _remote_definitions(self) -> dict:
        """(resource type, name) -> the CSD definitions that make it remote: each
        `system` (REMOTESYSTEM), `remote_name` (REMOTENAME / REMOTETRANSID, else
        the name), `group`, `defined_in` (the CSD / JCL deck), `line`."""
        out: dict = {}
        for f in sorted(self.files.values(), key=lambda x: x.file_path):
            for r in f.csd_resources:
                attrs = r.attributes or ""
                system = _csd_operand(attrs, "REMOTESYSTEM")
                if not system:
                    continue
                remote = _csd_operand(attrs, "REMOTENAME") or _csd_operand(attrs, "REMOTETRANSID") or r.name
                out.setdefault(((r.resource_type or "").upper(), (r.name or "").upper()), []).append(
                    {
                        "system": system,
                        "remote_name": remote,
                        "group": r.group,
                        "defined_in": f.file_path,
                        "line": r.line,
                    }
                )
        return out

    def remote_programs(self) -> dict:
        """Program name -> its remote CSD definitions (#3494): a LINK to it from a
        region that installs one of those groups is a Distributed Program Link to
        `system`. The same program is often local in the region that owns it (the
        AOR / DOR) and remote in the region that routes to it (the TOR), so both
        can be true -- which region a caller runs in is the CICS topology's (the
        SIT GRPLIST), not the source's."""
        return {name: defs for (kind, name), defs in sorted(self._remote_definitions().items()) if kind == "PROGRAM"}

    def remote_calls(self) -> list:
        """Every LINK / XCTL / START that can leave the region (#3494): the site names
        a SYSID, or its program (static, or a data-driven candidate, #3493) or its
        transaction has a REMOTESYSTEM definition. Each: `file`, `line`, `verb`,
        `program`, `sysid` (as written, or None), `remote` (the CSD definitions)."""
        defs = self._remote_definitions()
        out = []

        def add(file: str, line: int, verb: str, program: Optional[str], sysid: Optional[str], kind: str) -> None:
            remote = defs.get((kind, (program or "").upper()), [])
            if sysid or remote:
                out.append(
                    {"file": file, "line": line, "verb": verb, "program": program, "sysid": sysid, "remote": remote}
                )

        for f in sorted(self.files.values(), key=lambda x: x.file_path):
            for c in f.calls:
                if c.verb in ("LINK", "XCTL") and c.form != "identifier":
                    add(f.file_path, c.line, c.verb, c.target, c.sysid, "PROGRAM")
                elif c.verb in ("START TRANSID", "RUN TRANSID"):
                    add(f.file_path, c.line, c.verb, c.target, c.sysid, "TRANSACTION")
        sysids = {(f.file_path, c.line): c.sysid for f in self.files.values() for c in f.calls if c.sysid}
        for d in self.dynamic_call_targets():
            if d["verb"] in ("LINK", "XCTL"):
                for cand in d["candidates"]:
                    add(d["file"], d["line"], d["verb"], cand["program"], sysids.get((d["file"], d["line"])), "PROGRAM")
        return out

    def remote_resources(self) -> list:
        """Function shipping (#3494): every CICS FILE / queue operation whose
        resource has a REMOTESYSTEM definition (FILE, TDQUEUE, TSMODEL). Each:
        `file`, `line`, `verb`, `kind`, `name`, `remote` (the CSD definitions)."""
        defs = self._remote_definitions()
        ts_models = [(name, d) for (kind, name), d in defs.items() if kind == "TSMODEL"]
        out = []
        for f in sorted(self.files.values(), key=lambda x: x.file_path):
            for op in f.cics_resources:
                name = (op.name or "").upper()
                if not name:
                    continue
                if op.kind == "FILE":
                    remote = defs.get(("FILE", name), [])
                elif op.kind == "QUEUE" and (op.qualifier or "").upper() == "TD":
                    remote = defs.get(("TDQUEUE", name), [])
                elif op.kind == "QUEUE":
                    # A TS queue is remote through the TSMODEL whose prefix it matches.
                    remote = [x for model, d in ts_models for x in d if name.startswith(model.rstrip("*"))]
                else:
                    continue
                if remote:
                    out.append({"file": f.file_path, "line": op.line, "verb": op.verb, "kind": op.kind, "name": name,
                                "remote": remote})  # fmt: skip
        return out

    def navigation(self) -> list:
        """The CICS program-to-program flow (#3493): one edge per LINK / XCTL site
        and RETURN / START TRANSID routing, static or data-driven. Each: `from`,
        `line`, `verb`, `to` (a file, or None), `program` (the name), `via` --
        static | transaction (TRANSID through the CSD) | value | table | moves --
        and `remote_systems` (#3494: the REMOTESYSTEMs the CSD defines the program
        with; a LINK from a region installing that definition is a DPL)."""
        out = []
        for f in sorted(self.files.values(), key=lambda x: x.file_path):
            for c in f.calls:
                if c.verb in TRANSACTION_ROUTING_VERBS and c.target:
                    out.append({"from": f.file_path, "line": c.line, "verb": c.verb, "program": c.target,
                                "to": self._transaction_program(c.target), "via": "transaction"})  # fmt: skip
                elif c.verb in ("LINK", "XCTL") and c.form != "identifier" and (c.resolves_to or c.target):
                    # A data-name site (even one bound through its VALUE) comes from
                    # dynamic_call_targets below, so no edge is listed twice.
                    out.append({"from": f.file_path, "line": c.line, "verb": c.verb, "program": c.target,
                                "to": c.resolves_to, "via": "static"})  # fmt: skip
        out.extend(
            {"from": d["file"], "line": d["line"], "verb": d["verb"], "program": cand["program"],
             "to": cand["resolves_to"], "via": cand["via"]}
            for d in self.dynamic_call_targets()
            if d["verb"] in ("LINK", "XCTL")
            for cand in d["candidates"]
        )  # fmt: skip
        # #3494: the regions a LINK may ship the program to (its REMOTESYSTEMs).
        remote = self.remote_programs()
        for e in out:
            e["remote_systems"] = sorted({d["system"] for d in remote.get((e["program"] or "").upper(), [])})
        return out

    def dynamic_call_targets(self) -> list:
        """Every LINK / XCTL / CALL whose program is a data item, with the programs
        it can name (#3493) -- a site the call resolver already bound through a VALUE
        is listed too, its VALUE one candidate. Per site: `file`, `copybook` (a procedure copybook's
        site, resolved in `file`), `line`, `verb`, `operand`, `candidates` -- each
        `program`, `resolves_to` (its file, or None), `via` (value | table | moves) --
        and `other_sources`: items MOVEd into the operand whose content is not known
        here (a COMMAREA field such as CDEMO-FROM-PROGRAM: "back to the caller")."""
        by_pid = {pid.upper(): f.file_path for f in self.files.values() if f.is_program for pid in f.program_ids}
        includers: dict = {}
        for f in self.files.values():
            for dep in f.copy_deps:
                includers.setdefault(dep, []).append(f)
        moves: dict = {}
        for fl in self.data_flows():
            key = (fl["file"], fl["target"].split(" OF ")[0])
            moves.setdefault(key, []).append(fl)
        out = []
        for home in sorted(self.files.values(), key=lambda x: x.file_path):
            for c in home.calls:
                if c.form != "identifier" or not c.operand:
                    continue  # a literal target is static; every data-name site is listed
                if c.verb in TRANSACTION_ROUTING_VERBS:
                    continue
                name = c.operand.split("(")[0].split(" OF ")[0].strip().upper()
                scopes = [home] if home.is_program or not includers.get(home.file_path) else includers[home.file_path]
                for f in sorted(scopes, key=lambda x: x.file_path):
                    cands: dict = {}
                    others: set = set()
                    value = self._value_text(f, name)
                    if value and value.strip() and "?" not in value:
                        cands.setdefault(value.strip(), "value")
                    for v in self._table_values(f, name):
                        cands.setdefault(v, "table")
                    for fl in moves.get((f.file_path, name), []):
                        if fl["source_kind"] == "literal" and (fl["source"] or "")[:1] in "'\"":
                            cands.setdefault(fl["source"].strip("'\"").strip().upper(), "moves")
                        elif fl["source_kind"] == "item":
                            v = self._value_text(f, fl["source"].split(" OF ")[0])
                            if v and v.strip() and "?" not in v:
                                cands.setdefault(v.strip().upper(), "moves")
                            else:
                                others.add(fl["source"])
                    out.append(
                        {
                            "file": f.file_path,
                            "copybook": None if f is home else home.file_path,
                            "line": c.line,
                            "verb": c.verb,
                            "operand": c.operand,
                            "candidates": [
                                {"program": p, "resolves_to": by_pid.get(p.upper()), "via": via}
                                for p, via in sorted(cands.items())
                            ],
                            "other_sources": sorted(others),
                        }
                    )
        return out

    def ims_calls(self) -> list:
        """Every IMS DL/I call, resolved (#3450). Each: `file`, `line`, `interface`,
        `function` (the EXEC command, or a CBLTDLI function operand's VALUE -- GU,
        ISRT, ... -- None when unresolved), `access` (read / insert / update /
        delete / control), `pcb`, `io_area`, and `segments`: per SEGMENT / SSA the
        `segment` name and its `qualification` (an EXEC WHERE, or an SSA's
        `(FIELD OP` -- the key field and operator), `command_codes` (an SSA's `*..`)
        and `ssa` (the SSA data-name)."""
        access = {
            "GU": "read", "GHU": "read", "GN": "read", "GHN": "read", "GNP": "read", "GHNP": "read",
            "ISRT": "insert", "REPL": "update", "DLET": "delete",
        }  # fmt: skip
        out = []
        for f in sorted(self.files.values(), key=lambda x: x.file_path):
            for d in f.dli_calls:
                function = d.function
                if d.interface == "CALL" and d.function_operand:
                    value = self._value_text(f, d.function_operand)
                    function = value.strip() or None if value and "?" not in value else None
                segments = []
                if d.interface == "EXEC":
                    wheres = (d.where or "").split(";") if d.where else []
                    for i, seg in enumerate([x for x in (d.segments or "").split(",") if x]):
                        # A WHERE qualifies the SEGMENT before it; a path call's
                        # last WHEREs line up with its last segments.
                        offset = len([x for x in (d.segments or "").split(",") if x]) - len(wheres)
                        qual = wheres[i - offset] if 0 <= i - offset < len(wheres) else None
                        segments.append({"segment": seg, "qualification": qual, "command_codes": None, "ssa": None})
                else:
                    for ssa in [x for x in (d.ssas or "").split(",") if x]:
                        text = self._value_text(f, ssa) or ""
                        seg = text[:8].strip() or None
                        mark = text[8:9]
                        qual = codes = None
                        if mark == "*":
                            codes = text[9 : text.find("(", 9) if "(" in text[9:] else len(text)].strip() or None
                            rest = text[text.find("(", 9) :] if "(" in text[9:] else ""
                        else:
                            rest = text[8:]
                        if rest.startswith("("):
                            qual = f"{rest[1:9].strip()} {rest[9:11].strip()}".strip() or None
                        segments.append(
                            {"segment": seg if seg and "?" not in seg else None, "qualification": qual,
                             "command_codes": codes, "ssa": ssa}
                        )  # fmt: skip
                out.append(
                    {
                        "file": f.file_path,
                        "line": d.line,
                        "interface": d.interface,
                        "function": function,
                        "access": access.get(function or "", "control" if function else None),
                        "pcb": d.pcb,
                        "io_area": d.io_area,
                        "psb": d.psb,
                        "segments": segments,
                    }
                )
        return out

    def ims_segment_access(self) -> list:
        """The program x IMS segment matrix (#3450): one entry per (file, segment)
        with its sorted `accesses` (read / insert / update / delete) and `pcbs`. A
        path call acts on its last segment and reads the parents it positions
        through; an unqualified GN / GNP with no
        segment reaches the PCB's database, which needs the PSB (not scanned)."""
        by: dict[tuple[str, str], dict] = {}
        for c in self.ims_calls():
            if c["access"] in (None, "control"):
                continue
            named = [s_ for s_ in c["segments"] if s_["segment"]]
            for i, s_ in enumerate(named):
                e = by.setdefault(
                    (c["file"], s_["segment"]),
                    {"file": c["file"], "segment": s_["segment"], "accesses": set(), "pcbs": set()},
                )
                # A path call acts on its LAST segment; the parents before it are
                # only located (read) to position there.
                e["accesses"].add(c["access"] if i == len(named) - 1 else "read")
                if c["pcb"]:
                    e["pcbs"].add(c["pcb"])
        return [dict(e, accesses=sorted(e["accesses"]), pcbs=sorted(e["pcbs"])) for _, e in sorted(by.items())]

    # ---- #3452: field-level data movement --------------------------------------
    def _storage_spans(self, ef: EngineFile) -> dict:
        """id(EngineDataItem) -> (record key, offset, bytes, one occurrence's bytes) for every item program
        `ef` can see, COPY-expanded: its own 01 / 77 records, then the records of
        the copybooks it COPYs that no own record already reached. The record key
        is (defining file, root name). A REDEFINES item takes the offset of the
        item it overlays; bytes is None when a width inside is unknown. Cached."""
        cache = self.__dict__.setdefault("_span_cache", {})
        # Keyed by the object too: a synthetic symbolic map (#3490) is rebuilt per call.
        if (ef.file_path, id(ef)) in cache:
            return cache[(ef.file_path, id(ef))][0]
        spans: dict = {}
        paths: dict = {}  # id(item) -> the names of its storage ancestors, innermost first
        items: dict = {}  # record key -> [(offset, bytes, depth, name)]

        def walk(
            owner: EngineFile, it: EngineDataItem, key: tuple, offset: int, depth: int, ext: Optional[list], path: tuple
        ):
            if it.level in (66, 88) or depth > 12:
                return 0
            times = it.occurs_max or 1
            kids = [] if _is_elementary(it) else self._expanded_children(owner, it, ef, depth)
            if ext:
                kids = kids + list(ext)
            if kids:
                size: Optional[int] = 0
                at: dict = {}
                for kid_file, kid in kids:
                    if kid_file is None:
                        size = None
                        continue
                    if kid.level in (66, 88):
                        continue
                    if kid.redefines:
                        base = at.get(kid.redefines.upper())
                        at_base = base if base is not None else offset + (size or 0)
                        walk(kid_file, kid, key, at_base, depth + 1, None, (it.name, *path))
                        continue
                    at[kid.name.upper()] = offset + (size or 0)
                    width = walk(kid_file, kid, key, offset + (size or 0), depth + 1, None, (it.name, *path))
                    size = None if size is None or width is None else size + width
                total = None if size is None else size * times
            else:
                width = _elementary_bytes(it)
                total = None if width is None else width * times
            # One occurrence's width rides along: a subscripted reference moves one.
            spans[id(it)] = (key, offset, total, None if total is None else total // times)
            paths[id(it)] = path
            items.setdefault(key, []).append((offset, total, len(path), it.name))
            return total

        fd_first: dict = {}
        for root in ef.records:
            if id(root) not in spans:
                # `01 B REDEFINES A` overlays record A: same storage, same record key;
                # so do the 01 records of one FD, whose buffer they share (#3492).
                name = root.redefines or (fd_first.setdefault(root.fd_name, root.name) if root.fd_name else root.name)
                walk(ef, root, (ef.file_path, name), 0, 0, None, ())
        for cb in self._copy_files(ef):
            roots = [r for r in cb.records if r.level not in (66, 88)]
            for root in roots:
                if id(root) not in spans:
                    ext = self._copy_extension(ef, cb) if roots[-1:] == [root] else None
                    walk(cb, root, (cb.file_path, root.name), 0, 0, ext, ())
        cache[(ef.file_path, id(ef))] = (spans, ef)  # ef held so its id is never reused
        self.__dict__.setdefault("_span_paths", {})[ef.file_path] = paths
        self.__dict__.setdefault("_span_items", {})[ef.file_path] = items
        return spans

    def _name_at(self, file_path: str, span: dict) -> Optional[str]:
        """The most specific item of program `file_path` at `span`: the deepest one
        with exactly its offset and width, else the smallest one containing it."""
        self._storage_spans(self.files[file_path])
        entries = self.__dict__["_span_items"][file_path].get((span["record_file"], span["record"]), [])
        exact = [e for e in entries if e[0] == span["offset"] and e[1] == span["bytes"]]
        if exact:
            return max(exact, key=lambda e: e[2])[3]
        end = span["offset"] + (span["bytes"] or 1)
        inside = [e for e in entries if e[1] is not None and e[0] <= span["offset"] and end <= e[0] + e[1]]
        return min(inside, key=lambda e: (e[1], -e[2]))[3] if inside else None

    def _operand_span(self, ef: EngineFile, operand: Optional[str]) -> tuple[Optional[dict], str]:
        """(span, status) of one data-name operand as seen from `ef`: span is
        {record, record_file, offset, bytes (the whole table for an OCCURS item),
        occurrence_bytes, item, item_class (_item_class, or group)}, status resolved | unresolved | ambiguous (several
        items answer to the name and its qualifiers) | system (an unresolved name
        the runtime supplies: EIB / DIB / SQLCA fields, DFH constants, special
        registers)."""
        if not operand:
            return None, "unresolved"
        parts = operand.upper().split(" OF ")
        spans = self._storage_spans(ef)
        paths = self.__dict__["_span_paths"][ef.file_path]
        found = self._find_item(ef, parts[0], None)
        if len(parts) > 1:
            # Qualifiers are matched against the STORAGE ancestors, so a copybook
            # item expanded under the program's own group (`01 DFHCOMMAREA.` + `COPY
            # PAYDBCR.`) answers to that group, which its copybook never names. Every
            # same-named item is a candidate, the program's own and each copybook's.
            owners = [ef, *self._copy_files(ef)]
            found = [
                (o, it, None)
                for o in owners
                for it in o.data_items
                if it.name == parts[0] and it.level not in (66, 88) and _in_order(parts[1:], paths.get(id(it), ()))
            ]
        if not found:
            return None, ("system" if _SYSTEM_NAME.match(parts[0]) else "unresolved")
        hits = {spans[id(it)]: it for _, it, _ in found if id(it) in spans}
        if len(hits) != 1:
            return None, ("ambiguous" if len(hits) > 1 else "unresolved")
        (key, offset, size, unit), item = next(iter(hits.items()))
        span = {"record": key[1], "record_file": key[0], "offset": offset, "bytes": size, "item": parts[0]}
        cls = _item_class(item) if _is_elementary(item) else "group"
        return dict(span, occurrence_bytes=unit, item_class=cls), "resolved"

    def data_flows(self, language: str = "cobol") -> list:
        """Every data move (#3452) with both operands resolved to storage.

        A copybook of procedure statements (`COPY CSUTLDPY.` in the PROCEDURE
        DIVISION) acts on its includer's data, so its moves are resolved once per
        including program, with `file` the program and `copybook` the member
        (None for a program's own statements; `line` is the member's line).

        One entry per source -> target pair: `file`, `copybook`, `line`, `verb`, `source`,
        `source_kind`, `target`, `corresponding`, `source_span` / `target_span`
        ({record, record_file, offset, bytes, item}, None when not an item or not
        resolved), `status` -- resolved | source_unresolved | target_unresolved |
        ambiguous | system (an operand is a runtime-supplied name) -- and `truncates`: True when a MOVE into an alphanumeric or group
        target is shorter than its item or literal source (no reference
        modification), False when it is not, None when that cannot be told (a
        numeric target, an unknown width)."""
        out = []
        includers: dict = {}
        for f in self.files.values():
            for dep in f.copy_deps:
                includers.setdefault(dep, []).append(f)
        scopes = []  # (the program whose storage resolves the names, the statement's file)
        for g in sorted(self.files.values(), key=lambda x: x.file_path):
            if g.language != language or not g.data_moves:
                continue
            if g.is_program or not includers.get(g.file_path):
                scopes.append((g, g))
            else:  # a copybook of procedure statements acts on each includer's data
                scopes.extend((h, g) for h in sorted(includers[g.file_path], key=lambda x: x.file_path))
        for f, home in sorted(scopes, key=lambda x: (x[0].file_path, x[1] is not x[0], x[1].file_path)):
            for m in home.data_moves:
                target, t_status = self._operand_span(f, m.target)
                if m.source_kind == "item":
                    source, s_status = self._operand_span(f, m.source)
                elif m.source_kind == "file":  # READ / RETURN INTO: the file's FD record (#3492)
                    fd = next((r for r in f.records if (r.fd_name or "").upper() == (m.source or "").upper()), None)
                    source, s_status = self._operand_span(f, fd.name) if fd is not None else (None, "unresolved")
                else:
                    source, s_status = None, "resolved"
                status = "resolved"
                if "ambiguous" in (t_status, s_status):
                    status = "ambiguous"
                elif s_status == "unresolved":
                    status = "source_unresolved"
                elif t_status == "unresolved":
                    status = "target_unresolved"
                elif "system" in (t_status, s_status):
                    status = "system"
                truncates = None
                if (
                    m.verb == "MOVE"
                    and target
                    and target["occurrence_bytes"]
                    and not (m.source_refmod or m.target_refmod)
                ):
                    t_class = target["item_class"]
                    s_bytes = source["occurrence_bytes"] if source else (
                        len(m.source) - 2 if m.source_kind == "literal" and (m.source or "")[:1] in "'\"" else None
                    )  # fmt: skip
                    if t_class in ("X", "group") and s_bytes and not m.corresponding:
                        truncates = s_bytes > target["occurrence_bytes"]
                out.append(
                    {
                        "file": f.file_path,
                        "copybook": None if home is f else home.file_path,
                        "line": m.line,
                        "verb": m.verb,
                        "source": m.source,
                        "source_kind": m.source_kind,
                        "target": m.target,
                        "corresponding": m.corresponding,
                        "source_span": source,
                        "target_span": target,
                        "status": status,
                        "truncates": truncates,
                    }
                )
        return out

    def _lineage_endpoints(self, ef: EngineFile) -> list:
        """(span, endpoint label) pairs of program `ef`: FD records, SQL host
        variables, DL/I I/O areas, and CICS FILE / MAP / QUEUE / CONTAINER records."""
        out = []
        for root in ef.records:
            if root.fd_name:
                span, _ = self._operand_span(ef, root.name)
                if span:
                    out.append((span, f"file FD {root.fd_name}"))
        for st in ef.sql_statements:
            for hv in st.host_variables if isinstance(st.host_variables, list) else []:
                parts = hv.lstrip(":").split(":")[0].split(".")  # :GROUP.ITEM:INDICATOR
                span, _ = self._operand_span(ef, " OF ".join(reversed(parts)))
                if span:
                    out.append((span, f"sql {st.verb} {st.table or '-'}"))
        for d in ef.dli_calls:
            if d.io_area:
                span, _ = self._operand_span(ef, d.io_area)
                if span:
                    out.append((span, f"ims {d.function or d.function_operand} {d.segments or d.ssas or '-'}"))
        for op in ef.cics_resources:
            if op.record and op.kind in ("FILE", "MAP", "QUEUE", "CONTAINER"):
                span, _ = self._operand_span(ef, op.record)
                if span:
                    out.append((span, f"cics {op.kind} {op.name or op.operand or '-'} {op.access}"))
        return out

    def field_lineage(self, file_path: str, item: str, direction: str = "forward", max_hops: int = 400) -> list:
        """Where the data in `item` of program `file_path` goes (`forward`) or comes
        from (`backward`), following storage, not names (#3452).

        A MOVE of a group carries a field inside it to the same offset of the
        target, so a field moved as part of a record keeps its identity; every
        other statement (COMPUTE, STRING, arithmetic, a reference-modified MOVE)
        taints the whole target. Across programs, a CALL USING argument and its
        callee parameter, and a COMMAREA record and the callee's DFHCOMMAREA, are
        the same storage. Each hop: `file`, `record`, `record_file`, `offset`,
        `bytes`, `depth`, `via` ({kind: move|call|commarea, verb, line, file} of
        the edge that reached it; None for the start), `item` (the most specific
        data item at that storage), `endpoints` (labels of the channel endpoints
        whose storage overlaps it) and `resolved`. A move whose other operand is not
        declared in the repository (a generated BMS symbolic map, an EIB field)
        ends the trail in a hop with `resolved` False, `item` that name and no
        storage. Returns [] when `item` does not resolve."""
        ef = self.files.get(file_path)
        if ef is None:
            return []
        start, _ = self._operand_span(ef, item)
        if start is None:
            return []
        forward = direction == "forward"

        def overlap(a: dict, b: dict) -> bool:
            if (a["record_file"], a["record"]) != (b["record_file"], b["record"]):
                return False
            a_end = a["offset"] + (a["bytes"] or 1)
            b_end = b["offset"] + (b["bytes"] or 1)
            return a["offset"] < b_end and b["offset"] < a_end

        def carried(node: dict, whole_from: dict, to: dict) -> dict:
            """`node`'s slice of `whole_from` at the same offset inside `to`."""
            if whole_from["bytes"] is None or node["bytes"] is None:
                return dict(to)
            lo = max(node["offset"], whole_from["offset"]) - whole_from["offset"]
            hi = min(node["offset"] + node["bytes"], whole_from["offset"] + whole_from["bytes"]) - whole_from["offset"]
            if to["bytes"] is not None and lo >= to["bytes"]:
                return dict(to)
            size = hi - lo if to["bytes"] is None else min(hi, to["bytes"]) - lo
            return dict(to, offset=to["offset"] + lo, bytes=max(size, 1))

        flows: dict = {}
        for fl in self.data_flows():
            if fl["source_span"] or fl["target_span"]:
                flows.setdefault(fl["file"], []).append(fl)
        # file -> [(this side span, other file, other side span, via)]: the shared
        # storage of a CALL USING BY REFERENCE / COMMAREA, walked both ways.
        links: dict = {}
        for c in self.call_contracts():
            if c.get("status") != "paired" or not c.get("callee"):
                continue
            caller, callee = self.files.get(c["caller"]), self.files.get(c["callee"])
            if caller is None or callee is None:
                continue
            for a in c.get("args", []):
                arg, param = a.get("argument") or "", a.get("parameter") or ""
                by_ref = ":" not in arg
                a_span, _ = self._operand_span(caller, arg.split(":")[-1])
                p_span, _ = self._operand_span(callee, param.split(":")[-1])
                if not (a_span and p_span):
                    continue
                via = {"kind": "call", "verb": "CALL", "line": c["line"], "file": c["caller"]}
                links.setdefault(c["caller"], []).append((a_span, c["callee"], p_span, via))
                if by_ref:  # BY CONTENT / VALUE storage does not come back
                    links.setdefault(c["callee"], []).append((p_span, c["caller"], a_span, via))
        for c in self.commarea_contracts():
            if c.get("status") != "paired" or not c.get("commarea"):
                continue
            caller, callee = self.files.get(c["caller"]), self.files.get(c["callee"])
            if caller is None or callee is None:
                continue
            a_span, _ = self._operand_span(caller, c["commarea"])
            p_span, _ = self._operand_span(callee, "DFHCOMMAREA")
            if a_span and p_span:
                via = {"kind": "commarea", "verb": c["verb"], "line": c["line"], "file": c["caller"]}
                links.setdefault(c["caller"], []).append((a_span, c["callee"], p_span, via))
                links.setdefault(c["callee"], []).append((p_span, c["caller"], a_span, via))
        endpoints: dict = {}

        def tag(file: str, span: dict) -> list:
            if file not in endpoints:
                endpoints[file] = self._lineage_endpoints(self.files[file])
            return sorted({label for sp, label in endpoints[file] if overlap(sp, span)})

        def key(file: str, span: dict) -> tuple:
            return (file, span["record_file"], span["record"], span["offset"], span["bytes"])

        start = {k: start[k] for k in ("record", "record_file", "offset", "bytes", "item")}
        hops = [dict(start, file=file_path, depth=0, via=None, endpoints=tag(file_path, start), resolved=True)]
        seen = {key(file_path, start)}
        queue = [hops[0]]
        while queue and len(hops) < max_hops:
            node = queue.pop(0)
            nxt = []
            for fl in flows.get(node["file"], []):
                src, dst = (fl["source_span"], fl["target_span"]) if forward else (fl["target_span"], fl["source_span"])
                if src is None or not overlap(src, node):
                    continue
                via = {"kind": "move", "verb": fl["verb"], "line": fl["line"], "file": node["file"]}
                if dst is None:
                    # The other operand is a name this repository does not declare (a
                    # generated symbolic map, a system field): the trail ends there.
                    name = fl["target"] if forward else fl["source"]
                    if (forward or fl["source_kind"] == "item") and (node["file"], None, name) not in seen:
                        seen.add((node["file"], None, name))
                        hops.append(
                            {"record": None, "record_file": None, "offset": None, "bytes": None, "item": name,
                             "file": node["file"], "depth": node["depth"] + 1, "via": via, "endpoints": [],
                             "resolved": False}
                        )  # fmt: skip
                    continue
                # A MOVE of an item and the whole-record file I/O (#3492) keep a field's offset.
                exact = not fl["corresponding"] and (
                    (fl["verb"] == "MOVE" and fl["source_kind"] == "item") or fl["verb"] in _RECORD_IO_VERBS
                )
                span = carried(node, src, dst) if exact else dict(dst)
                nxt.append((node["file"], span, via))
            for this, other, that, via in links.get(node["file"], []):
                if overlap(this, node):
                    nxt.append((other, carried(node, this, that), via))
            for file, span, via in nxt:
                span = {k: span.get(k) for k in ("record", "record_file", "offset", "bytes", "item")}
                k = key(file, span)
                if k in seen:
                    continue
                seen.add(k)
                span["item"] = self._name_at(file, span) or span["item"]
                hop = dict(span, file=file, depth=node["depth"] + 1, via=via, endpoints=tag(file, span), resolved=True)
                hops.append(hop)
                queue.append(hop)
        return hops

    def ims_psbs(self) -> dict:
        """PSB name -> {`file`, `pcbs`: [{`pcb`, `type`, `dbd`, `procopt`, `sensegs`
        (segment names)}]} from the PSBGEN sources (#3477)."""
        out: dict = {}
        for f in sorted(self.files.values(), key=lambda x: x.file_path):
            gen = [g for g in f.ims_gen if g.kind in ("PCB", "SENSEG", "PSBGEN")]
            psb = next((g.name for g in gen if g.kind == "PSBGEN" and g.name), None)
            if not psb:
                continue
            pcbs = [
                {
                    "pcb": g.name,
                    "type": g.pcb_type,
                    "dbd": g.dbd_name,
                    "procopt": g.procopt,
                    "sensegs": [x.name for x in gen if x.kind == "SENSEG" and x.owner == g.name and x.name],
                }
                for g in gen
                if g.kind == "PCB"
            ]
            out[psb] = {"file": f.file_path, "pcbs": pcbs}
        return out

    def ims_databases(self) -> dict:
        """DBD name -> {`file`, `access`, `segments`: [{`segment`, `parent`, `bytes`,
        `key` (the SEQ field)}]} from the DBDGEN sources (#3477)."""
        out: dict = {}
        for f in sorted(self.files.values(), key=lambda x: x.file_path):
            for g in f.ims_gen:
                if g.kind == "DBD" and g.name:
                    out[g.name] = {"file": f.file_path, "access": g.access, "segments": []}
            for g in f.ims_gen:
                if g.kind == "SEGM" and g.owner in out and g.name:
                    key = next(
                        (x.name for x in f.ims_gen if x.kind == "FIELD" and x.parent == g.name and x.access == "SEQ"),
                        None,
                    )
                    out[g.owner]["segments"].append(
                        {"segment": g.name, "parent": g.parent, "bytes": g.bytes, "key": key}
                    )
        return out

    def ims_program_psbs(self) -> dict:
        """Program file -> the PSB names it runs under: a JCL DFSRRC00 region step
        naming its PROGRAM-ID, and each EXEC DLI SCHD PSB resolved through VALUE."""
        by_pid: dict[str, str] = {}
        for f in self.files.values():
            for pid in f.program_ids:
                by_pid.setdefault(pid.upper(), f.file_path)
        out: dict[str, set] = {}
        for f in self.files.values():
            for g in f.ims_gen:
                if g.kind == "REGION" and g.program and g.psb_name and g.program in by_pid:
                    out.setdefault(by_pid[g.program], set()).add(g.psb_name)
            for d in f.dli_calls:
                if d.function == "SCHD" and d.psb:
                    value = d.psb if d.psb[:1] in "'\"" else self._value_text(f, d.psb)
                    name = (value or "").strip(" '\"").upper()
                    if name and "?" not in name:
                        out.setdefault(f.file_path, set()).add(name)
        return {k: sorted(v) for k, v in out.items()}

    def ims_access_check(self) -> list:
        """Each program x segment access (#3450) checked against the IMS definitions
        (#3477). Per entry: `file`, `segment`, `accesses`, `databases` (the DBDs
        defining the segment), `psbs` (the program's PSBs), and `pcbs` -- for each
        PSB PCB sensitive to the segment: `psb`, `pcb`, `dbd`, `procopt` and
        `denied` (accesses its PROCOPT does not allow). `status`: ok | denied (a
        sensitive PCB's PROCOPT refuses an access) | not_sensitive (no PCB of the
        program's PSBs has the segment as a SENSEG) | no_psb (none is known)."""
        letters = {"read": "G", "insert": "I", "update": "R", "delete": "D"}
        psbs, dbds, program_psbs = self.ims_psbs(), self.ims_databases(), self.ims_program_psbs()
        out = []
        for e in self.ims_segment_access():
            names = program_psbs.get(e["file"], [])
            pcbs = []
            for psb in names:
                for pcb in psbs.get(psb, {}).get("pcbs", []):
                    if e["segment"] not in pcb["sensegs"]:
                        continue
                    opt = (pcb["procopt"] or "").upper()
                    denied = [
                        a for a in e["accesses"]
                        if "A" not in opt and letters[a] not in opt and not (a == "insert" and "L" in opt)
                    ]  # fmt: skip
                    pcbs.append(
                        {"psb": psb, "pcb": pcb["pcb"], "dbd": pcb["dbd"], "procopt": pcb["procopt"], "denied": denied}
                    )
            if not names or not any(n in psbs for n in names):
                status = "no_psb"
            elif not pcbs:
                status = "not_sensitive"
            elif all(p["denied"] for p in pcbs):
                status = "denied"
            else:
                status = "ok"
            out.append(
                {
                    "file": e["file"],
                    "segment": e["segment"],
                    "accesses": e["accesses"],
                    "databases": sorted(
                        n for n, d in dbds.items() if any(s["segment"] == e["segment"] for s in d["segments"])
                    ),
                    "psbs": names,
                    "pcbs": pcbs,
                    "status": status,
                }
            )
        return out

    def lookup(self, path: Path, target_root: Path) -> Optional[EngineFile]:
        try:
            rel = path.resolve().relative_to(target_root.resolve()).as_posix()
        except ValueError:
            return None
        return self.files.get(rel)


# ---- #3355: the COMMAREA contract join -------------------------------------
# Byte widths, computed HERE from the record_data tree (the engine deliberately
# computes none -- mainframe_boundary SCOPE). IBM Enterprise COBOL storage rules:
# DISPLAY is one byte per picture position (S is an embedded sign, V/P take no
# storage); PACKED-DECIMAL/COMP-3 is digits//2 + 1; BINARY/COMP/COMP-4/COMP-5 is
# 2/4/8 bytes for 1-4/5-9/10-18 digits; COMP-1/COMP-2 are 4/8; POINTER/INDEX 4;
# N/G (national/DBCS) positions are 2 bytes. Anything else is None -- unknown,
# never guessed -- and an unknown width makes the enclosing record's width None.
_CONTRACT_VERBS = ("LINK", "XCTL", "RETURN TRANSID")
_COPY_DEPTH = 8  # nested COPY expansion bound (a copybook that COPYs itself ends here)


def _pic_positions(pic: str) -> Optional[list]:
    """The picture string expanded to one symbol per position (`X(3)9` -> X X X 9)."""
    out: list = []
    i, text = 0, pic.upper()
    while i < len(text):
        ch = text[i]
        if ch == "(" and out:
            close = text.find(")", i)
            if close == -1 or not text[i + 1 : close].isdigit():
                return None
            out.extend(out[-1:] * (int(text[i + 1 : close]) - 1))
            i = close + 1
            continue
        if text.startswith(("CR", "DB"), i):
            out.extend([ch, ch])
            i += 2
            continue
        out.append(ch)
        i += 1
    return out


# The USAGEs that make an item elementary with no PIC. Any other PIC-less item is
# a group, even with a USAGE of its own (`01 X USAGE DISPLAY.` applies to its
# children) -- and even when the engine read a stray USAGE into it.
_PICLESS_USAGES = ("COMP-1", "COMPUTATIONAL-1", "COMP-2", "COMPUTATIONAL-2", "POINTER", "INDEX")


# #3498: languages a CALL / LINK can reach that the call resolver does not link to.
_CALLEE_LANGUAGES = frozenset({"hlasm", "assembly", "pli", "rexx", "c", "cpp", "java", "easytrieve"})

# #3498: programs and copybooks IBM or the runtime supply -- never a gap.
_SYSTEM_PROGRAM = re.compile(
    r"(?:IDCAMS|IEB|IEF|IEH|IKJ|ICE|SORT|DFSORT|SYNCSORT|IEW|IGY|ASMA|IBMZ|CEE|DFH|DSN|DFS|ADR|IDC|IRX|EZA|IGZ|ILBO"
    r"|CSQ|IOEAGFMT|BPXBATCH|AMASPZAP|IMS|DLI|CBLTDLI|AIBTDLI|PLITDLI|MQ)[A-Z0-9@#$]*$"
)
_SYSTEM_COPYBOOK = re.compile(r"(?:DFH|CMQ|SQLCA|SQLDA|DSN|CEE|IGZ|DLI|DFS)[A-Z0-9@#$]*$")

# #3492: file I/O that moves a whole record between the FD buffer and an area.
_RECORD_IO_VERBS = frozenset({"READ", "RETURN", "WRITE", "REWRITE", "RELEASE"})

# #3452: data names the runtime supplies, never declared in the repository: the
# CICS EIB and IMS DIB fields, the SQLCA, the DFHBMSCA / DFHAID constants, and
# the COBOL special registers.
_SYSTEM_NAME = re.compile(
    r"(?:EIB|DIB|DFH)[A-Z0-9-]*$|SQL(?:CODE|STATE|ERRM|ERRMC|ERRML|ERRD|ERRP|WARN[0-9A]?|CA|EXT)$"
    r"|(?:RETURN-CODE|SORT-RETURN|TALLY|WHEN-COMPILED|DEBUG-ITEM|XML-CODE|JSON-CODE)$"
)


def _csd_operand(attributes: str, key: str) -> Optional[str]:
    """`KEY(value)` out of a CSD definition's kept attribute text (case-insensitive)."""
    m = re.search(rf"(?<![A-Z0-9]){key}\(\s*([^)\s]+)\s*\)", attributes, re.I)
    return m.group(1).upper() if m else None


def _descendants(item: EngineDataItem) -> list:
    out, stack = [], list(item.children)
    while stack:
        it = stack.pop()
        out.append(it)
        stack.extend(it.children)
    return out


def _in_order(wanted: list, path: tuple) -> bool:
    """Every name of `wanted` appears in `path`, in the same (outward) order."""
    at = 0
    for name in path:
        if at < len(wanted) and name == wanted[at]:
            at += 1
    return at == len(wanted)


def _is_elementary(item: EngineDataItem) -> bool:
    return bool(item.pic) or (item.usage or "").upper() in _PICLESS_USAGES


def _item_class(item: EngineDataItem) -> str:
    """A coarse storage class for shape comparison: X alnum, 9 zoned, P packed,
    B binary, F float, N national, A address; `?` when unknown."""
    usage = (item.usage or "DISPLAY").upper()
    if usage in ("COMP-3", "COMPUTATIONAL-3", "PACKED-DECIMAL"):
        return "P"
    if usage in ("COMP", "COMPUTATIONAL", "COMP-4", "COMPUTATIONAL-4", "COMP-5", "COMPUTATIONAL-5", "BINARY"):
        return "B"
    if usage in ("COMP-1", "COMPUTATIONAL-1", "COMP-2", "COMPUTATIONAL-2"):
        return "F"
    if usage in ("POINTER", "INDEX"):
        return "A"
    pic = (item.pic or "").upper()
    if not pic:
        return "?"
    if "N" in pic or "G" in pic or usage == "DISPLAY-1":
        return "N"
    if set(pic) & set("XA"):
        return "X"
    return "9"


def _elementary_bytes(item: EngineDataItem) -> Optional[int]:
    """One occurrence's storage width of an elementary item, or None when unknown."""
    usage = (item.usage or "DISPLAY").upper()
    if usage in ("COMP-1", "COMPUTATIONAL-1", "POINTER", "INDEX"):
        return 4
    if usage in ("COMP-2", "COMPUTATIONAL-2"):
        return 8
    if not item.pic:
        return None
    positions = _pic_positions(item.pic)
    if positions is None:
        return None
    digits = sum(1 for p in positions if p == "9")
    cls = _item_class(item)
    if cls == "P":
        return digits // 2 + 1
    if cls == "B":
        if not digits or digits > 18:
            return None
        return 2 if digits <= 4 else 4 if digits <= 9 else 8
    storage = [p for p in positions if p not in ("S", "V", "P")]
    width = sum(2 if p in ("N", "G") else 1 for p in storage)
    return width or None


def _layout_mismatches(caller: dict, callee: dict) -> list:
    """Length and field-shape differences between two `record_layout`s, as data.

    Nothing is claimed against a variable-length side (an OCCURS DEPENDING ON:
    the carddemo `PIC X OCCURS 1 TO 32767 DEPENDING ON EIBCALEN` idiom accepts
    any length by design). `shape` compares each elementary field's (offset,
    width, storage class) in order -- names differ legitimately between caller
    and callee -- and points at the first diverging field on each side.
    """
    if caller["variable"] or callee["variable"]:
        return []
    out = []
    if None not in (caller["bytes"], callee["bytes"]) and caller["bytes"] != callee["bytes"]:
        out.append({"kind": "length", "caller": caller["bytes"], "callee": callee["bytes"]})
    shape_a = [(x["offset"], x["bytes"], x["class"]) for x in caller["fields"]]
    shape_b = [(x["offset"], x["bytes"], x["class"]) for x in callee["fields"]]
    if shape_a and shape_b and shape_a != shape_b:
        at = next((i for i, (a, b) in enumerate(zip(shape_a, shape_b)) if a != b), min(len(shape_a), len(shape_b)))
        out.append(
            {
                "kind": "shape",
                "caller": caller["fields"][at]["name"] if at < len(shape_a) else None,
                "callee": callee["fields"][at]["name"] if at < len(shape_b) else None,
            }
        )
    return out


def _operand_name(operand: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """`COMMAREA(x)`'s data-name and its qualifier: `A OF B(1)` -> ('A', 'B')."""
    if not operand:
        return None, None
    tokens = operand.replace("(", " ( ").split()
    name = tokens[0] if tokens and tokens[0][:1].isalpha() else None
    qual = None
    if len(tokens) >= 3 and tokens[1] in ("OF", "IN") and tokens[2][:1].isalpha():
        qual = tokens[2]
    return name, qual


def _declared_length(expr: Optional[str], record: Optional[str]) -> tuple[Optional[int], Optional[str]]:
    """The byte count a LENGTH/DATALENGTH operand states, and how it states it.

    `+100` / `100` -> (100, 'literal'); `LENGTH OF <the passed record>` ->
    (None, 'length_of_record') -- equal to the record by construction; anything
    else (a data-name, `LENGTH OF` another item) -> (None, 'expression').
    """
    if not expr:
        return None, None
    text = expr.strip().lstrip("+")
    if text.isdigit():
        return int(text), "literal"
    parts = text.split()
    if len(parts) >= 3 and parts[0] == "LENGTH" and parts[1] == "OF" and record and parts[2] == record:
        return None, "length_of_record"
    return None, "expression"


def _has_column(cur: sqlite3.Cursor, table: str, column: str) -> bool:
    """Whether `table` carries `column` (#3250: record_data.attributes), so a DB
    written before the column existed still loads, with the value as None."""
    return any(row[1] == column for row in cur.execute(f"PRAGMA table_info({table})"))


def _has_table(cur: sqlite3.Cursor, name: str) -> bool:
    """Whether this database carries `name`, so an older scan still loads.

    A master DB written before #3200 has no call_site_data / dataset_data. The
    refraction tools read whatever scan they are pointed at, so a missing table
    means "this snapshot predates the channel", not a failure.
    """
    return cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def load_galaxy_ir(db_path: Path, repo_name: Optional[str] = None) -> GalaxyIR:
    """Loads the latest snapshot of one repo from a master DB, opened read-only."""
    db_path = Path(db_path)
    if not db_path.is_file():
        raise FileNotFoundError(f"No galaxy master DB at {db_path}")

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cur = conn.cursor()
        # Same baseline rule as state_rehydrator: newest by commit_date. A master
        # DB normally holds one forward lineage; a multi-repo DB needs repo_name.
        if repo_name is None:
            names = [r[0] for r in cur.execute("SELECT DISTINCT repo_name FROM repo_data")]
            if len(names) != 1:
                raise ValueError(f"{db_path} holds {len(names)} repos; pass repo_name explicitly: {names}")
            repo_name = names[0]
        row = cur.execute(
            "SELECT commit_hash FROM repo_data WHERE repo_name = ? ORDER BY commit_date DESC LIMIT 1",
            (repo_name,),
        ).fetchone()
        if row is None:
            raise ValueError(f"No snapshot for repo '{repo_name}' in {db_path}")
        commit_hash = row[0]

        signal_sql = ", ".join(f"COALESCE({c}, 0)" for c in SIGNAL_COLUMNS)
        files: dict[str, EngineFile] = {}
        by_id: dict[int, EngineFile] = {}
        for rec in cur.execute(
            f"SELECT id, file_path, language, COALESCE(total_loc, 0), {signal_sql} "  # noqa: S608 -- columns are the SIGNAL_COLUMNS constant; values are bound
            "FROM file_data WHERE repo_name = ? AND commit_hash = ?",
            (repo_name, commit_hash),
        ):
            ef = EngineFile(
                # The engine records OS-native separators (backslashes on
                # Windows); key everything by POSIX form so lookup() and
                # `target / file_path` agree on every platform.
                file_path=(rec[1] or "").replace("\\", "/"),
                language=rec[2] or "",
                total_loc=int(rec[3]),
                signals={c: int(v) for c, v in zip(SIGNAL_COLUMNS, rec[4:])},
            )
            files[ef.file_path] = ef
            by_id[rec[0]] = ef

        if not by_id:
            return GalaxyIR(db_path, repo_name, commit_hash, files)

        # class_data/function_data carry no snapshot key of their own; they hang
        # off file_data ids, which were filtered to this snapshot above.
        for file_id, class_name in cur.execute("SELECT file_id, class_name FROM class_data ORDER BY id"):
            if file_id in by_id and class_name:
                by_id[file_id].program_ids.append(class_name)

        for file_id, name, start, loc, status in cur.execute(
            "SELECT file_id, func_name, start_line, loc, usage_status FROM function_data ORDER BY file_id, start_line"
        ):
            if file_id in by_id:
                by_id[file_id].units.append(EngineUnit(name or "", int(start or 0), int(loc or 0), int(status or 0)))

        # #3200: edge_kind is load-bearing now. edge_data carries 'call' and
        # 'exec' rows alongside the 'import' ones, and copy_deps means COPY /
        # EXEC SQL INCLUDE only -- without this filter a CICS LINK would read as
        # a copybook dependency.
        for src, dst in cur.execute(
            "SELECT src_file_id, dst_file_id FROM edge_data "
            "WHERE repo_name = ? AND commit_hash = ? AND COALESCE(edge_kind, 'import') = 'import'",
            (repo_name, commit_hash),
        ):
            if src in by_id and dst in by_id:
                by_id[src].copy_deps.append(by_id[dst].file_path)
        for ef in files.values():
            ef.copy_deps.sort()

        # #3200: the call sites, resolved and unresolved alike. A pre-#3200
        # database has no such table, so a missing table is "no data", never an
        # error -- the refraction tools must keep reading an older scan.
        if _has_table(cur, "call_site_data"):
            # #3355: the COMMAREA contract operands are NULL on a DB written before them.
            commarea_cols = (
                "commarea, commarea_length, commarea_datalength"
                if _has_column(cur, "call_site_data", "commarea")
                else "NULL, NULL, NULL"
            )
            # #3454: the USING list is NULL on a DB written before it.
            using_col = "using_args" if _has_column(cur, "call_site_data", "using_args") else "NULL"
            # #3494: SYSID likewise.
            sysid_col = "sysid" if _has_column(cur, "call_site_data", "sysid") else "NULL"
            for (
                file_id,
                verb,
                form,
                operand,
                target,
                dst_id,
                line,
                commarea,
                c_len,
                c_dlen,
                using,
                sysid,
            ) in cur.execute(
                "SELECT src_file_id, verb, form, operand, target, dst_file_id, line_number, "  # noqa: S608 -- commarea_cols / using_col / sysid_col are fixed literals; values are bound
                f"{commarea_cols}, {using_col}, {sysid_col} FROM call_site_data WHERE repo_name = ? AND commit_hash = ? "
                "ORDER BY src_file_id, line_number, id",
                (repo_name, commit_hash),
            ):
                if file_id not in by_id:
                    continue
                resolved = by_id[dst_id].file_path if dst_id in by_id else None
                by_id[file_id].calls.append(
                    EngineCall(
                        verb or "",
                        form or "",
                        operand,
                        target,
                        resolved,
                        int(line or 0),
                        commarea,
                        c_len,
                        c_dlen,
                        using,
                        sysid,
                    )
                )

        # #3201: the dataset boundary, both the COBOL and the JCL half.
        if _has_table(cur, "dataset_data"):
            # #3345: the resolved-DSN pair is NULL on a DB written before it existed.
            resolved_cols = (
                "dsn_resolved, dsn_resolution" if _has_column(cur, "dataset_data", "dsn_resolution") else "NULL, NULL"
            )
            for file_id, step, internal, assign, dd, modes, dsn, line, dsn_resolved, dsn_resolution in cur.execute(
                "SELECT file_id, step_name, internal_name, assign_name, dd_name, access_modes, dsn, line_number, "  # noqa: S608 -- resolved_cols is one of two literals; values are bound
                f"{resolved_cols} FROM dataset_data WHERE repo_name = ? AND commit_hash = ? "
                "ORDER BY file_id, line_number, id",
                (repo_name, commit_hash),
            ):
                if file_id not in by_id:
                    continue
                by_id[file_id].datasets.append(
                    EngineDataset(
                        step,
                        internal,
                        assign,
                        dd or "",
                        (modes or "").split(",") if modes else [],
                        dsn,
                        int(line or 0),
                        dsn_resolved,
                        dsn_resolution,
                    )
                )

        # #3246: the DATA DIVISION item tree + FD record layouts. A pre-#3246
        # database has no such table, so a missing table is "no records", never
        # an error -- the same back-compat rule as call_site_data/dataset_data.
        # Rows arrive in source order (ORDER BY ordinal); the tree is rethreaded
        # from parent_ordinal, which the extractor computed with a level stack.
        if _has_table(cur, "record_data"):
            # #3250: `attributes` is NULL on a DB written before the column existed.
            attributes_col = "attributes" if _has_column(cur, "record_data", "attributes") else "NULL"
            # #3355: `copy_members` likewise.
            copy_col = "copy_members" if _has_column(cur, "record_data", "copy_members") else "NULL"
            for (
                file_id,
                ordinal,
                parent,
                level,
                name,
                section,
                fd,
                pic,
                usage,
                omin,
                omax,
                dep,
                redef,
                val,
                line,
                attrs,
                copies,
            ) in cur.execute(
                "SELECT file_id, ordinal, parent_ordinal, level_number, item_name, section, fd_name, pic, "  # noqa: S608 -- attributes_col is one of two literals; values are bound
                "usage, occurs_min, occurs_max, occurs_depending_on, redefines, value_literal, line_number, "
                f"{attributes_col}, {copy_col} FROM record_data WHERE repo_name = ? AND commit_hash = ? "
                "ORDER BY file_id, ordinal",
                (repo_name, commit_hash),
            ):
                if file_id not in by_id:
                    continue
                by_id[file_id].data_items.append(
                    EngineDataItem(
                        ordinal=int(ordinal or 0),
                        parent_ordinal=parent,
                        level=int(level or 0),
                        name=name or "",
                        section=section,
                        fd_name=fd,
                        pic=pic,
                        usage=usage,
                        occurs_min=omin,
                        occurs_max=omax,
                        occurs_depending_on=dep,
                        redefines=redef,
                        value=val,
                        line=int(line or 0),
                        attributes=attrs,
                        copy_members=copies,
                    )
                )
            # Thread children onto parents and collect the roots. `data_items` is
            # ordered by ordinal, so a parent is always seen before its children.
            for ef in files.values():
                if not ef.data_items:
                    continue
                by_ordinal = {item.ordinal: item for item in ef.data_items}
                for item in ef.data_items:
                    if item.parent_ordinal is not None and item.parent_ordinal in by_ordinal:
                        by_ordinal[item.parent_ordinal].children.append(item)
                    else:
                        ef.records.append(item)

        # #3211-followup: the CICS transaction map. Hangs off the DEFINING deck's
        # file (the .csd/JCL), with dst_file_id resolved to the program's file.
        # A pre-#3211-followup database has no such table, so a missing table is
        # "no data", never an error.
        if _has_table(cur, "transaction_data"):
            for file_id, transid, program, group_name, profile, dst_id, line in cur.execute(
                "SELECT file_id, transid, program, group_name, profile, dst_file_id, line_number "
                "FROM transaction_data WHERE repo_name = ? AND commit_hash = ? ORDER BY file_id, line_number, id",
                (repo_name, commit_hash),
            ):
                if file_id not in by_id:
                    continue
                resolved = by_id[dst_id].file_path if dst_id in by_id else None
                by_id[file_id].transactions.append(
                    EngineTransaction(transid or "", program, group_name, profile, resolved, int(line or 0))
                )

        # #3344: DB2 DECLARE TABLE / DCLGEN schemas. A pre-#3344 database has no
        # such table, so a missing table is "no data", never an error. Rows are
        # grouped back into tables by (table_line, table_name) -- the same name
        # declared twice in one file stays two declarations.
        if _has_table(cur, "sql_table_data"):
            for file_id, tname, tline, colno, cname, stype, length, scale, nullable, attrs, line in cur.execute(
                "SELECT file_id, table_name, table_line, colno, column_name, sql_type, length, scale, nullable, "
                "attributes, line_number FROM sql_table_data WHERE repo_name = ? AND commit_hash = ? "
                "ORDER BY file_id, table_line, colno, id",
                (repo_name, commit_hash),
            ):
                if file_id not in by_id:
                    continue
                tables = by_id[file_id].sql_tables
                if not tables or tables[-1].name != (tname or "") or tables[-1].line != int(tline or 0):
                    tables.append(EngineSqlTable(tname or "", int(tline or 0)))
                tables[-1].columns.append(
                    EngineSqlColumn(
                        int(colno or 0),
                        cname or "",
                        stype or "",
                        length,
                        scale,
                        bool(nullable),
                        attrs,
                        int(line or 0),
                    )
                )
        # #3446: embedded SQL statements. A pre-#3446 database has no such table,
        # so a missing table is "no data", never an error.
        if _has_table(cur, "sql_statement_data"):
            for file_id, ordinal, verb, tname, access, cursor_name, host, line in cur.execute(
                "SELECT file_id, stmt_ordinal, verb, table_name, access, cursor_name, host_variables, line_number "
                "FROM sql_statement_data WHERE repo_name = ? AND commit_hash = ? ORDER BY file_id, id",
                (repo_name, commit_hash),
            ):
                if file_id in by_id:
                    by_id[file_id].sql_statements.append(
                        EngineSqlStatement(
                            int(ordinal or 0),
                            verb or "",
                            tname,
                            access,
                            cursor_name,
                            [h for h in (host or "").split(",") if h],
                            int(line or 0),
                        )
                    )
        # #3347: BMS screen-field layouts. A pre-#3347 database has no such table,
        # so a missing table is "no screen fields", never an error.
        if _has_table(cur, "screen_field_data"):
            for row in cur.execute(
                "SELECT file_id, kind, ordinal, parent_ordinal, field_name, pos_line, pos_column, length, attrb, "
                "picin, picout, initial_value, occurs, attributes, line_number "
                "FROM screen_field_data WHERE repo_name = ? AND commit_hash = ? ORDER BY file_id, ordinal",
                (repo_name, commit_hash),
            ):
                if row[0] not in by_id:
                    continue
                by_id[row[0]].screen_fields.append(
                    EngineScreenField(
                        kind=row[1] or "",
                        ordinal=int(row[2] or 0),
                        parent_ordinal=row[3],
                        name=row[4],
                        pos_line=row[5],
                        pos_column=row[6],
                        length=row[7],
                        attrb=row[8],
                        picin=row[9],
                        picout=row[10],
                        initial=row[11],
                        occurs=row[12],
                        attributes=row[13],
                        line=int(row[14] or 0),
                    )
                )
        # #3356: CSD resource definitions. A pre-#3356 database has no such table,
        # so a missing table is "no data", never an error.
        if _has_table(cur, "csd_resource_data"):
            for row in cur.execute(
                "SELECT file_id, resource_type, resource_name, group_name, dsname, ddname, record_format, "
                "key_length, record_size, queue_type, plan, db2_entry, transid, program, attributes, line_number "
                "FROM csd_resource_data WHERE repo_name = ? AND commit_hash = ? ORDER BY file_id, line_number, id",
                (repo_name, commit_hash),
            ):
                if row[0] not in by_id:
                    continue
                by_id[row[0]].csd_resources.append(
                    EngineCsdResource(
                        resource_type=row[1] or "",
                        name=row[2] or "",
                        group=row[3],
                        dsname=row[4],
                        ddname=row[5],
                        record_format=row[6],
                        key_length=row[7],
                        record_size=row[8],
                        queue_type=row[9],
                        plan=row[10],
                        db2_entry=row[11],
                        transid=row[12],
                        program=row[13],
                        attributes=row[14],
                        line=int(row[15] or 0),
                    )
                )
        # #3351-#3354: CICS resource operations. A pre-channel database has no such
        # table, so a missing table is "no CICS resources", never an error.
        if _has_table(cur, "cics_resource_data"):
            for row in cur.execute(
                "SELECT file_id, verb, resource_kind, access, name_operand, resource_name, name_resolution, "
                "name_candidates, qualifier_operand, qualifier, record_clause, record_name, attributes, line_number "
                "FROM cics_resource_data WHERE repo_name = ? AND commit_hash = ? ORDER BY file_id, line_number, id",
                (repo_name, commit_hash),
            ):
                if row[0] not in by_id:
                    continue
                by_id[row[0]].cics_resources.append(
                    EngineCicsResource(
                        verb=row[1] or "",
                        kind=row[2] or "",
                        access=row[3] or "",
                        operand=row[4],
                        name=row[5],
                        resolution=row[6],
                        candidates=row[7],
                        qualifier_operand=row[8],
                        qualifier=row[9],
                        record_clause=row[10],
                        record=row[11],
                        attributes=row[12],
                        line=int(row[13] or 0),
                    )
                )
        # #3496: web-services assistant steps. A pre-#3496 database has none.
        if _has_table(cur, "web_service_data"):
            for row in cur.execute(
                "SELECT file_id, assistant, direction, program, uri, request, response, interface, container, binding, document, transaction_id, line_number FROM web_service_data "
                "WHERE repo_name = ? AND commit_hash = ? ORDER BY file_id, id",
                (repo_name, commit_hash),
            ):
                if row[0] in by_id:
                    fields = dict(zip(_WEB_FIELDS, row[1:-1]))
                    by_id[row[0]].web_services.append(EngineWebService(**fields, line=int(row[-1] or 0)))
        # #3452: field-level data movement. A pre-#3452 database has none.
        if _has_table(cur, "data_move_data"):
            for row in cur.execute(
                "SELECT file_id, verb, source, source_kind, target, corresponding, source_refmod, target_refmod, "
                "line_number FROM data_move_data WHERE repo_name = ? AND commit_hash = ? ORDER BY file_id, id",
                (repo_name, commit_hash),
            ):
                if row[0] in by_id:
                    by_id[row[0]].data_moves.append(
                        EngineDataMove(
                            verb=row[1] or "",
                            source=row[2],
                            source_kind=row[3],
                            target=row[4] or "",
                            corresponding=bool(row[5]),
                            source_refmod=bool(row[6]),
                            target_refmod=bool(row[7]),
                            line=int(row[8] or 0),
                        )
                    )
        # #3477: IMS PSB / DBD macros and region steps. A pre-#3477 database has none.
        if _has_table(cur, "ims_gen_data"):
            for row in cur.execute(
                "SELECT file_id, kind, name, parent, owner, dbd_name, procopt, pcb_type, access, bytes, start_pos, "
                "psb_name, program, attributes, line_number FROM ims_gen_data "
                "WHERE repo_name = ? AND commit_hash = ? ORDER BY file_id, line_number, id",
                (repo_name, commit_hash),
            ):
                if row[0] in by_id:
                    by_id[row[0]].ims_gen.append(
                        EngineImsGen(
                            kind=row[1] or "",
                            name=row[2],
                            parent=row[3],
                            owner=row[4],
                            dbd_name=row[5],
                            procopt=row[6],
                            pcb_type=row[7],
                            access=row[8],
                            bytes=int(row[9]) if row[9] is not None else None,
                            start=int(row[10]) if row[10] is not None else None,
                            psb_name=row[11],
                            program=row[12],
                            attributes=row[13],
                            line=int(row[14] or 0),
                        )
                    )
        # #3450: IMS DL/I calls. A pre-#3450 database has none.
        if _has_table(cur, "dli_call_data"):
            for row in cur.execute(
                "SELECT file_id, interface, function, function_operand, pcb, io_area, segments, ssas, where_text, psb, "
                "line_number FROM dli_call_data WHERE repo_name = ? AND commit_hash = ? ORDER BY file_id, line_number, id",
                (repo_name, commit_hash),
            ):
                if row[0] in by_id:
                    by_id[row[0]].dli_calls.append(
                        EngineDliCall(
                            interface=row[1] or "",
                            function=row[2],
                            function_operand=row[3],
                            pcb=row[4],
                            io_area=row[5],
                            segments=row[6],
                            ssas=row[7],
                            where=row[8],
                            psb=row[9],
                            line=int(row[10] or 0),
                        )
                    )
        # #3454: program entry points. A pre-#3454 database has none.
        if _has_table(cur, "entry_point_data"):
            for file_id, kind, name, params, line in cur.execute(
                "SELECT file_id, kind, entry_name, params, line_number FROM entry_point_data "
                "WHERE repo_name = ? AND commit_hash = ? ORDER BY file_id, line_number, id",
                (repo_name, commit_hash),
            ):
                if file_id in by_id:
                    by_id[file_id].entry_points.append(EngineEntryPoint(kind or "", name, params, int(line or 0)))
        # #3451: JCL job flow. A pre-#3451 database has none.
        if _has_table(cur, "job_flow_data"):
            for row in cur.execute(
                "SELECT file_id, kind, job_name, step_ordinal, step_name, program, proc_name, cond, if_cond, in_proc, "
                "dd_name, dsn, disp, generation, line_number FROM job_flow_data "
                "WHERE repo_name = ? AND commit_hash = ? ORDER BY file_id, line_number, id",
                (repo_name, commit_hash),
            ):
                if row[0] in by_id:
                    by_id[row[0]].job_flow.append(
                        EngineJobFlow(
                            kind=row[1] or "",
                            name=row[2],
                            step_ordinal=int(row[3]) if row[3] is not None else None,
                            step_name=row[4],
                            program=row[5],
                            proc=row[6],
                            cond=row[7],
                            if_cond=row[8],
                            in_proc=row[9],
                            dd_name=row[10],
                            dsn=row[11],
                            disp=row[12],
                            generation=row[13],
                            line=int(row[14] or 0),
                        )
                    )
        # #3455: file definitions. A pre-#3455 database has neither table.
        if _has_table(cur, "file_control_data"):
            for row in cur.execute(
                "SELECT file_id, select_name, assign_name, organization, access_mode, record_key, alternate_keys, "
                "relative_key, file_status, fd_copies, line_number FROM file_control_data "
                "WHERE repo_name = ? AND commit_hash = ? ORDER BY file_id, line_number, id",
                (repo_name, commit_hash),
            ):
                if row[0] in by_id:
                    alternates = [
                        (a[:-4], True) if a.endswith("+DUP") else (a, False) for a in (row[6] or "").split(",") if a
                    ]
                    by_id[row[0]].file_control.append(
                        EngineFileControl(
                            select_name=row[1] or "",
                            assign=row[2],
                            organization=row[3],
                            access_mode=row[4],
                            record_key=row[5],
                            alternate_keys=alternates,
                            relative_key=row[7],
                            file_status=row[8],
                            fd_copies=[c for c in (row[9] or "").split(",") if c],
                            line=int(row[10] or 0),
                        )
                    )
        if _has_table(cur, "vsam_define_data"):
            for row in cur.execute(
                "SELECT file_id, kind, cluster_name, organization, key_length, key_offset, record_avg, record_max, "
                "related, unique_key, upgrade, step_name, line_number FROM vsam_define_data "
                "WHERE repo_name = ? AND commit_hash = ? ORDER BY file_id, line_number, id",
                (repo_name, commit_hash),
            ):
                if row[0] in by_id:

                    def _int(v):
                        return int(v) if v is not None else None

                    by_id[row[0]].vsam_defines.append(
                        EngineVsamDefine(
                            kind=row[1] or "",
                            name=row[2],
                            organization=row[3],
                            key_length=_int(row[4]),
                            key_offset=_int(row[5]),
                            record_avg=_int(row[6]),
                            record_max=_int(row[7]),
                            related=row[8],
                            unique_key=row[9],
                            upgrade=row[10],
                            step=row[11],
                            line=int(row[12] or 0),
                        )
                    )
        # #3453: units of work and error handling. A pre-#3453 database has none.
        if _has_table(cur, "uow_handler_data"):
            for row in cur.execute(
                "SELECT file_id, kind, source, verb, condition_name, target, target_kind, resp_var, attributes, "
                "line_number FROM uow_handler_data WHERE repo_name = ? AND commit_hash = ? "
                "ORDER BY file_id, line_number, id",
                (repo_name, commit_hash),
            ):
                if row[0] in by_id:
                    by_id[row[0]].uow_handlers.append(
                        EngineUowHandler(
                            kind=row[1] or "",
                            source=row[2] or "",
                            verb=row[3] or "",
                            condition=row[4],
                            target=row[5],
                            target_kind=row[6],
                            resp_var=row[7],
                            attributes=row[8],
                            line=int(row[9] or 0),
                        )
                    )
        # #3447: IBM MQ calls. A pre-#3447 database has none.
        if _has_table(cur, "mq_call_data"):
            for row in cur.execute(
                "SELECT file_id, verb, direction, queue_operand, queue_name, queue_resolution, queue_candidates, "
                "handle, open_line, options, line_number "
                "FROM mq_call_data WHERE repo_name = ? AND commit_hash = ? ORDER BY file_id, line_number, id",
                (repo_name, commit_hash),
            ):
                if row[0] in by_id:
                    by_id[row[0]].mq_calls.append(
                        EngineMqCall(
                            verb=row[1] or "",
                            direction=row[2],
                            operand=row[3],
                            queue=row[4],
                            resolution=row[5],
                            candidates=row[6],
                            handle=row[7],
                            open_line=int(row[8]) if row[8] is not None else None,
                            options=row[9],
                            line=int(row[10] or 0),
                        )
                    )
        # #3448: job-submission evidence. A pre-#3448 database has none.
        if _has_table(cur, "job_submit_data"):
            for file_id, kind, step, name, tkind, target, line in cur.execute(
                "SELECT file_id, kind, step_name, submit_name, target_kind, target, line_number "
                "FROM job_submit_data WHERE repo_name = ? AND commit_hash = ? ORDER BY file_id, line_number, id",
                (repo_name, commit_hash),
            ):
                if file_id in by_id:
                    by_id[file_id].job_submits.append(
                        EngineJobSubmit(kind or "", step, name, tkind, target, int(line or 0))
                    )
        # #3449: CICS task control. A pre-#3449 database has no such table, so a
        # missing table is "no task commands", never an error.
        if _has_table(cur, "cics_task_data"):
            for row in cur.execute(
                "SELECT file_id, verb, target_kind, target_operand, target_name, target_resolution, "
                "target_candidates, channel_operand, channel_name, token, record_clause, record_name, timing, "
                "attributes, line_number "
                "FROM cics_task_data WHERE repo_name = ? AND commit_hash = ? ORDER BY file_id, line_number, id",
                (repo_name, commit_hash),
            ):
                if row[0] not in by_id:
                    continue
                by_id[row[0]].cics_tasks.append(
                    EngineCicsTask(
                        verb=row[1] or "",
                        target_kind=row[2],
                        operand=row[3],
                        name=row[4],
                        resolution=row[5],
                        candidates=row[6],
                        channel_operand=row[7],
                        channel=row[8],
                        token=row[9],
                        record_clause=row[10],
                        record=row[11],
                        timing=row[12],
                        attributes=row[13],
                        line=int(row[14] or 0),
                    )
                )
    finally:
        conn.close()

    _attach_symbolic_maps(files)
    return GalaxyIR(db_path, repo_name, commit_hash, files)


def _attach_symbolic_maps(files: dict[str, EngineFile]) -> None:
    """#3490: a COBOL program's `COPY <mapset>` with no real copybook in the
    repository gets the symbolic map its BMS source generates (core/bms_symbolic),
    parsed by the engine's record parser as any copybook is. A mapset defined by
    several BMS sources resolves only to the one whose file stem is the mapset."""
    stems = {Path(p).stem.upper() for p, f in files.items() if f.language == "cobol"}  # real copybooks
    maps = _symbolic_map_files(files)
    for f in files.values():
        if f.language != "cobol" or not f.data_items:
            continue
        members = {m for it in f.data_items for m in (it.copy_members or "").split(",") if m}
        for member in sorted(members):
            if member not in stems and member in maps:  # no real copybook answers the COPY
                f.symbolic_copies.append(maps[member])


def _symbolic_map_files(files: dict[str, EngineFile]) -> dict[str, EngineFile]:
    """Mapset -> its generated symbolic map as a synthetic EngineFile (#3490),
    for every mapset exactly one BMS source defines (or whose file stem is it)."""
    from gitgalaxy.core.bms_symbolic import symbolic_maps
    from gitgalaxy.core.mainframe_boundary import _cobol_records

    by_mapset: dict[str, list] = {}
    for f in sorted(files.values(), key=lambda x: x.file_path):
        if f.screen_fields:
            for mapset, text in symbolic_maps(f.screen_fields).items():
                by_mapset.setdefault(mapset, []).append((f.file_path, text))
    made: dict[str, EngineFile] = {}
    for mapset, cands in by_mapset.items():
        if len(cands) > 1:
            cands = [c for c in cands if Path(c[0]).stem.upper() == mapset]
        if len(cands) != 1:
            continue
        sym = EngineFile(file_path=f"{cands[0][0]}#{mapset}", language="cobol", total_loc=0)
        for r in _cobol_records(cands[0][1]):
            sym.data_items.append(
                EngineDataItem(
                    ordinal=r["ordinal"], parent_ordinal=r["parent_ordinal"], level=r["level"],
                    name=r["name"], section=None, fd_name=None, pic=r["pic"], usage=r["usage"],
                    occurs_min=r["occurs_min"], occurs_max=r["occurs_max"], occurs_depending_on=None,
                    redefines=r["redefines"], value=None, line=r["line"],
                )
            )  # fmt: skip
        by_ordinal = {it.ordinal: it for it in sym.data_items}
        for it in sym.data_items:
            parent = by_ordinal.get(it.parent_ordinal) if it.parent_ordinal is not None else None
            (parent.children if parent is not None else sym.records).append(it)
        made[mapset] = sym
    return made


def scan_to_db(target: Path, out_dir: Path, timeout: int = 3600) -> Path:
    """Runs a `galaxyscope --db-only` scan of `target` and returns the master DB path."""
    target = Path(target).resolve()
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    # Plain directory walk: the refraction target is often not a git checkout.
    env.setdefault("GITGALAXY_DISABLE_GIT_HISTORY", "1")
    subprocess.run(  # noqa: S603 -- this interpreter + fixed module; target/out_dir are argv entries, no shell
        [sys.executable, "-m", "gitgalaxy.galaxyscope", str(target), "--db-only", "--output", str(out_dir)],
        check=True,
        env=env,
        timeout=timeout,
    )
    db_path = out_dir / f"{target.name}_galaxy_master.db"
    if not db_path.is_file():
        raise FileNotFoundError(f"Scan finished but {db_path} was not written")
    return db_path
