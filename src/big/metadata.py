from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Iterable


@dataclass(frozen=True)
class VersionRecord:
    id: str
    branch: str
    parent_id: str | None
    step: str
    message: str
    author: str
    created_at: str
    recipe_hash: str
    manifest_hash: str
    capture_mode: str
    review_state: str
    retention_state: str


@dataclass(frozen=True)
class FileRef:
    role: str
    path: str
    cas_hash: str
    size: int
    semantic_role: str
    format_hint: str


class MetadataRepository:
    def init_schema(self) -> None:
        raise NotImplementedError


class SQLiteMetadataRepository(MetadataRepository):
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.OperationalError:
            # Some local/sandboxed paths cannot create WAL sidecar files.
            # The prototype can safely fall back to SQLite's default journal mode.
            pass
        return conn

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS branches (
                    name TEXT PRIMARY KEY,
                    head_version_id TEXT
                );

                CREATE TABLE IF NOT EXISTS versions (
                    id TEXT PRIMARY KEY,
                    branch TEXT NOT NULL,
                    parent_id TEXT,
                    step TEXT NOT NULL,
                    message TEXT NOT NULL,
                    author TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    recipe_hash TEXT NOT NULL,
                    manifest_hash TEXT NOT NULL,
                    capture_mode TEXT NOT NULL,
                    review_state TEXT NOT NULL,
                    retention_state TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS file_refs (
                    version_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    path TEXT NOT NULL,
                    cas_hash TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    semantic_role TEXT NOT NULL,
                    format_hint TEXT NOT NULL,
                    PRIMARY KEY (version_id, role, path),
                    FOREIGN KEY (version_id) REFERENCES versions(id)
                );

                CREATE INDEX IF NOT EXISTS idx_versions_branch_created
                    ON versions(branch, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_file_refs_hash
                    ON file_refs(cas_hash);
                """
            )
            conn.execute(
                "INSERT OR IGNORE INTO branches(name, head_version_id) VALUES (?, NULL)",
                ("main",),
            )

    def get_branch_head(self, branch: str) -> str | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT head_version_id FROM branches WHERE name = ?", (branch,)
            ).fetchone()
            return None if row is None else row["head_version_id"]

    def create_version(
        self,
        record: VersionRecord,
        files: Iterable[FileRef],
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO branches(name, head_version_id) VALUES (?, NULL)",
                (record.branch,),
            )
            conn.execute(
                """
                INSERT INTO versions(
                    id, branch, parent_id, step, message, author, created_at,
                    recipe_hash, manifest_hash, capture_mode, review_state,
                    retention_state
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.branch,
                    record.parent_id,
                    record.step,
                    record.message,
                    record.author,
                    record.created_at,
                    record.recipe_hash,
                    record.manifest_hash,
                    record.capture_mode,
                    record.review_state,
                    record.retention_state,
                ),
            )
            conn.executemany(
                """
                INSERT INTO file_refs(
                    version_id, role, path, cas_hash, size, semantic_role,
                    format_hint
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        record.id,
                        item.role,
                        item.path,
                        item.cas_hash,
                        item.size,
                        item.semantic_role,
                        item.format_hint,
                    )
                    for item in files
                ],
            )
            conn.execute(
                "UPDATE branches SET head_version_id = ? WHERE name = ?",
                (record.id, record.branch),
            )

    def list_versions(self, branch: str, limit: int = 20) -> list[VersionRecord]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM versions
                WHERE branch = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (branch, limit),
            ).fetchall()
        return [_version_from_row(row) for row in rows]

    def get_version(self, version_ref: str) -> VersionRecord | None:
        with self.connect() as conn:
            exact = conn.execute(
                "SELECT * FROM versions WHERE id = ?", (version_ref,)
            ).fetchone()
            if exact:
                return _version_from_row(exact)
            rows = conn.execute(
                "SELECT * FROM versions WHERE id LIKE ? ORDER BY created_at DESC",
                (f"{version_ref}%",),
            ).fetchall()
        if len(rows) == 1:
            return _version_from_row(rows[0])
        return None

    def get_file_refs(self, version_id: str) -> list[FileRef]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT role, path, cas_hash, size, semantic_role, format_hint
                FROM file_refs
                WHERE version_id = ?
                ORDER BY role, path
                """,
                (version_id,),
            ).fetchall()
        return [
            FileRef(
                role=row["role"],
                path=row["path"],
                cas_hash=row["cas_hash"],
                size=row["size"],
                semantic_role=row["semantic_role"],
                format_hint=row["format_hint"],
            )
            for row in rows
        ]


def _version_from_row(row: sqlite3.Row) -> VersionRecord:
    return VersionRecord(
        id=row["id"],
        branch=row["branch"],
        parent_id=row["parent_id"],
        step=row["step"],
        message=row["message"],
        author=row["author"],
        created_at=row["created_at"],
        recipe_hash=row["recipe_hash"],
        manifest_hash=row["manifest_hash"],
        capture_mode=row["capture_mode"],
        review_state=row["review_state"],
        retention_state=row["retention_state"],
    )
