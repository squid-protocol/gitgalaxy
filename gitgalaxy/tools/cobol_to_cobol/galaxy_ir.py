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
# dataset boundary (dataset_data), and since #3246 the DATA DIVISION item tree +
# FD record layouts (record_data). NOT in the DB, so still owned by the forge
# tools: reachability-based dead code. `usage_status` is a same-file "name
# mentioned elsewhere" test, not reachability -- it is carried as data and must
# not be fed to dead-code masking. See docs/refraction_engine_differential.md
# for the measured deltas.
# ==============================================================================
import os
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
MAINFRAME_LANGUAGES = ("cobol", "jcl", "bms", "pli", "db2_sql", "rexx", "hlasm")


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

    @property
    def is_binding(self) -> bool:
        """True for a JCL DD -> dataset binding, False for a COBOL SELECT."""
        return self.dsn is not None


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

    @property
    def is_group(self) -> bool:
        """A group item has subordinate items and no PIC of its own."""
        return not self.pic and self.level not in (66, 88)

    @property
    def occurs(self) -> Optional[int]:
        """The (max) table size, or None when the item is not a table."""
        return self.occurs_max


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
        `program`, `dd_name`, `modes`, `job`, `step` and `dsn`. A program DD
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
                    bindings.setdefault((f.file_path, ds.step_name, ds.dd_name), []).append(ds.dsn)

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
                    for (bj, bstep, bdd), dsns in bindings.items():
                        if bj != job_path or bdd != ds.dd_name:
                            continue
                        for dsn in dsns:
                            matched = True
                            out.append(
                                {
                                    "program": f.file_path,
                                    "dd_name": ds.dd_name,
                                    "modes": list(ds.modes),
                                    "job": bj,
                                    "step": bstep,
                                    "dsn": dsn,
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
                        }
                    )
        return out

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

    def lookup(self, path: Path, target_root: Path) -> Optional[EngineFile]:
        try:
            rel = path.resolve().relative_to(target_root.resolve()).as_posix()
        except ValueError:
            return None
        return self.files.get(rel)


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
            for file_id, verb, form, operand, target, dst_id, line in cur.execute(
                "SELECT src_file_id, verb, form, operand, target, dst_file_id, line_number "
                "FROM call_site_data WHERE repo_name = ? AND commit_hash = ? ORDER BY src_file_id, line_number, id",
                (repo_name, commit_hash),
            ):
                if file_id not in by_id:
                    continue
                resolved = by_id[dst_id].file_path if dst_id in by_id else None
                by_id[file_id].calls.append(
                    EngineCall(verb or "", form or "", operand, target, resolved, int(line or 0))
                )

        # #3201: the dataset boundary, both the COBOL and the JCL half.
        if _has_table(cur, "dataset_data"):
            for file_id, step, internal, assign, dd, modes, dsn, line in cur.execute(
                "SELECT file_id, step_name, internal_name, assign_name, dd_name, access_modes, dsn, line_number "
                "FROM dataset_data WHERE repo_name = ? AND commit_hash = ? ORDER BY file_id, line_number, id",
                (repo_name, commit_hash),
            ):
                if file_id not in by_id:
                    continue
                by_id[file_id].datasets.append(
                    EngineDataset(
                        step, internal, assign, dd or "", (modes or "").split(",") if modes else [], dsn, int(line or 0)
                    )
                )

        # #3246: the DATA DIVISION item tree + FD record layouts. A pre-#3246
        # database has no such table, so a missing table is "no records", never
        # an error -- the same back-compat rule as call_site_data/dataset_data.
        # Rows arrive in source order (ORDER BY ordinal); the tree is rethreaded
        # from parent_ordinal, which the extractor computed with a level stack.
        if _has_table(cur, "record_data"):
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
            ) in cur.execute(
                "SELECT file_id, ordinal, parent_ordinal, level_number, item_name, section, fd_name, pic, "
                "usage, occurs_min, occurs_max, occurs_depending_on, redefines, value_literal, line_number "
                "FROM record_data WHERE repo_name = ? AND commit_hash = ? ORDER BY file_id, ordinal",
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
    finally:
        conn.close()

    return GalaxyIR(db_path, repo_name, commit_hash, files)


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
