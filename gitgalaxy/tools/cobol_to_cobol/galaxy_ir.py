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
# The master DB does NOT yet carry everything the forge parsers derive. Taken
# from the DB here: the per-language file inventory, PROGRAM-ID (class_data),
# the paragraph/section inventory (function_data), resolved COPY/INCLUDE edges
# (edge_data) and subsystem hit counts. NOT in the DB, so still owned by the
# forge tools: SELECT/ASSIGN DD names, OPEN modes, CALL targets, data-division
# items, and reachability-based dead code. `usage_status` is a same-file
# "name mentioned elsewhere" test, not reachability -- it is carried as data
# and must not be fed to dead-code masking. See
# docs/refraction_engine_differential.md for the measured deltas.
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
class EngineFile:
    file_path: str
    language: str
    total_loc: int
    program_ids: list[str] = field(default_factory=list)
    units: list[EngineUnit] = field(default_factory=list)
    copy_deps: list[str] = field(default_factory=list)
    signals: dict[str, int] = field(default_factory=dict)

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

    def lookup(self, path: Path, target_root: Path) -> Optional[EngineFile]:
        try:
            rel = path.resolve().relative_to(target_root.resolve()).as_posix()
        except ValueError:
            return None
        return self.files.get(rel)


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
                file_path=rec[1],
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

        for src, dst in cur.execute(
            "SELECT src_file_id, dst_file_id FROM edge_data WHERE repo_name = ? AND commit_hash = ?",
            (repo_name, commit_hash),
        ):
            if src in by_id and dst in by_id:
                by_id[src].copy_deps.append(by_id[dst].file_path)
        for ef in files.values():
            ef.copy_deps.sort()
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
