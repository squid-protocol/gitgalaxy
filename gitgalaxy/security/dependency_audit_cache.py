# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# ==============================================================================
# GitGalaxy - Dependency Audit Cache
# Purpose: Persistent, content-hash-keyed cache of physical dependency-file
#          audit verdicts, enabling incremental (delta) verification across
#          scans instead of permanently partial sampling.
#
# LIFECYCLE NOTE (deliberately different from record_keeper.py's tables):
# This cache is keyed by CONTENT HASH and persists ACROSS commits, scans, and
# repos. It is never wiped per-run — only appended to (new hash observed) or
# read from (hash already verified). Wiping it per (repo, commit) like the
# telemetry tables would defeat incremental verification entirely.
# ==============================================================================
import hashlib
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional


class DependencyAuditCache:
    """
    SQLite-backed cache mapping (ecosystem, package, file, content-hash) to a
    previously computed audit verdict. A cache hit means the exact bytes of
    that file were already verified on some prior run; a miss means the file
    is new or its content changed and it must be freshly scanned.
    """

    def __init__(self, db_path: str, parent_logger: Optional[logging.Logger] = None):
        self.logger = (
            parent_logger.getChild("dep_audit_cache") if parent_logger else logging.getLogger("dep_audit_cache")
        )
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute("PRAGMA journal_mode = WAL;")
        self._conn.execute("PRAGMA synchronous = NORMAL;")
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS dependency_audit_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ecosystem TEXT NOT NULL,
                package_name TEXT NOT NULL,
                file_relpath TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                trust_status TEXT NOT NULL,
                anomaly_notes TEXT,
                first_seen_at TEXT,
                last_seen_at TEXT,
                UNIQUE(ecosystem, package_name, file_relpath, content_hash)
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_dep_cache_lookup
            ON dependency_audit_cache(ecosystem, package_name, file_relpath, content_hash)
        """)
        self._conn.commit()

    @staticmethod
    def hash_file(file_path: Path) -> Optional[str]:
        """
        sha256 of the file's FULL byte content. Hashing the whole file (not a
        truncated prefix) guarantees any modification anywhere in the file —
        including past any scan-depth limit — invalidates the cached verdict.
        Returns None if the file can't be read.
        """
        try:
            h = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(chunk)
            return h.hexdigest()
        except OSError:
            return None

    def lookup(self, ecosystem: str, package_name: str, file_relpath: str, content_hash: str) -> Optional[Dict[str, str]]:
        """Returns the cached verdict for these exact bytes, or None on miss."""
        row = self._conn.execute(
            """
            SELECT trust_status, anomaly_notes FROM dependency_audit_cache
            WHERE ecosystem = ? AND package_name = ? AND file_relpath = ? AND content_hash = ?
            """,
            (ecosystem, package_name, file_relpath, content_hash),
        ).fetchone()

        if row is None:
            return None

        # Refresh last_seen so stale-entry pruning (future work) has real data
        self._conn.execute(
            """
            UPDATE dependency_audit_cache SET last_seen_at = ?
            WHERE ecosystem = ? AND package_name = ? AND file_relpath = ? AND content_hash = ?
            """,
            (datetime.now(timezone.utc).isoformat(), ecosystem, package_name, file_relpath, content_hash),
        )
        return {"trust_status": row[0], "anomaly_notes": row[1] or ""}

    def record(
        self,
        ecosystem: str,
        package_name: str,
        file_relpath: str,
        content_hash: str,
        trust_status: str,
        anomaly_notes: str,
    ) -> None:
        """Stores a fresh verdict. Idempotent on the unique key."""
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """
            INSERT INTO dependency_audit_cache
                (ecosystem, package_name, file_relpath, content_hash, trust_status, anomaly_notes, first_seen_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ecosystem, package_name, file_relpath, content_hash)
            DO UPDATE SET trust_status = excluded.trust_status,
                          anomaly_notes = excluded.anomaly_notes,
                          last_seen_at = excluded.last_seen_at
            """,
            (ecosystem, package_name, file_relpath, content_hash, trust_status, anomaly_notes, now, now),
        )

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        try:
            self._conn.commit()
            self._conn.close()
        except sqlite3.Error as e:
            self.logger.warning(f"Dependency cache close failed: {e}")