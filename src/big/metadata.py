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
    work_root_id: str = ""
    workspace_id: str = ""
    user_name: str = ""
    flow: str = ""


@dataclass(frozen=True)
class FileRef:
    role: str
    path: str
    cas_hash: str
    size: int
    semantic_role: str
    format_hint: str


@dataclass(frozen=True)
class BranchRecord:
    name: str
    head_version_id: str | None
    kind: str
    created_at: str
    source_ref: str
    source_version_id: str
    owner: str


@dataclass(frozen=True)
class BranchEvent:
    id: int
    branch: str
    event_type: str
    old_head_version_id: str
    new_head_version_id: str
    actor: str
    created_at: str
    reason: str


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
                    head_version_id TEXT,
                    kind TEXT NOT NULL DEFAULT 'named',
                    created_at TEXT NOT NULL DEFAULT '',
                    source_ref TEXT NOT NULL DEFAULT '',
                    source_version_id TEXT NOT NULL DEFAULT '',
                    owner TEXT NOT NULL DEFAULT ''
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
                    retention_state TEXT NOT NULL,
                    work_root_id TEXT NOT NULL DEFAULT '',
                    workspace_id TEXT NOT NULL DEFAULT '',
                    user_name TEXT NOT NULL DEFAULT '',
                    flow TEXT NOT NULL DEFAULT ''
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

                CREATE TABLE IF NOT EXISTS branch_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    branch TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    old_head_version_id TEXT NOT NULL,
                    new_head_version_id TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    reason TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_versions_branch_created
                    ON versions(branch, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_file_refs_hash
                    ON file_refs(cas_hash);
                CREATE INDEX IF NOT EXISTS idx_branch_events_branch_created
                    ON branch_events(branch, created_at DESC);
                """
            )
            _ensure_column(conn, "branches", "kind", "TEXT NOT NULL DEFAULT 'named'")
            _ensure_column(conn, "branches", "created_at", "TEXT NOT NULL DEFAULT ''")
            _ensure_column(conn, "branches", "source_ref", "TEXT NOT NULL DEFAULT ''")
            _ensure_column(
                conn,
                "branches",
                "source_version_id",
                "TEXT NOT NULL DEFAULT ''",
            )
            _ensure_column(conn, "branches", "owner", "TEXT NOT NULL DEFAULT ''")
            conn.execute(
                """
                INSERT OR IGNORE INTO branches(
                    name, head_version_id, kind, created_at
                ) VALUES (?, NULL, 'main', '')
                """,
                ("main",),
            )
            conn.execute("UPDATE branches SET kind = 'main' WHERE name = 'main'")
            conn.execute(
                "UPDATE branches SET kind = 'workspace' WHERE name LIKE 'workspace/%'"
            )
            _ensure_column(conn, "versions", "work_root_id", "TEXT NOT NULL DEFAULT ''")
            _ensure_column(conn, "versions", "workspace_id", "TEXT NOT NULL DEFAULT ''")
            _ensure_column(conn, "versions", "user_name", "TEXT NOT NULL DEFAULT ''")
            _ensure_column(conn, "versions", "flow", "TEXT NOT NULL DEFAULT ''")

    def get_branch_head(self, branch: str) -> str | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT head_version_id FROM branches WHERE name = ?", (branch,)
            ).fetchone()
            return None if row is None else row["head_version_id"]

    def get_branch(self, branch: str) -> BranchRecord | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM branches WHERE name = ?", (branch,)
            ).fetchone()
        return None if row is None else _branch_from_row(row)

    def create_branch(
        self,
        name: str,
        head_version_id: str,
        kind: str,
        created_at: str,
        source_ref: str,
        source_version_id: str,
        owner: str,
    ) -> None:
        with self.connect() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO branches(
                        name, head_version_id, kind, created_at, source_ref,
                        source_version_id, owner
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        name,
                        head_version_id,
                        kind,
                        created_at,
                        source_ref,
                        source_version_id,
                        owner,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"Branch already exists: {name}") from exc

    def list_branches(self, include_workspace: bool = False) -> list[BranchRecord]:
        with self.connect() as conn:
            if include_workspace:
                rows = conn.execute(
                    "SELECT * FROM branches ORDER BY kind, name"
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM branches
                    WHERE kind != 'workspace'
                    ORDER BY kind, name
                    """
                ).fetchall()
        return [_branch_from_row(row) for row in rows]

    def reset_branch_head(
        self,
        branch: str,
        expected_old_head: str,
        new_head: str,
        actor: str,
        created_at: str,
        reason: str,
    ) -> None:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                UPDATE branches
                SET head_version_id = ?
                WHERE name = ? AND head_version_id = ?
                """,
                (new_head, branch, expected_old_head),
            )
            if cursor.rowcount != 1:
                raise ValueError(f"Branch head changed before reset: {branch}")
            conn.execute(
                """
                INSERT INTO branch_events(
                    branch, event_type, old_head_version_id, new_head_version_id,
                    actor, created_at, reason
                ) VALUES (?, 'reset', ?, ?, ?, ?, ?)
                """,
                (branch, expected_old_head, new_head, actor, created_at, reason),
            )

    def list_branch_events(self, branch: str) -> list[BranchEvent]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM branch_events
                WHERE branch = ?
                ORDER BY created_at DESC, id DESC
                """,
                (branch,),
            ).fetchall()
        return [_branch_event_from_row(row) for row in rows]

    def create_version(
        self,
        record: VersionRecord,
        files: Iterable[FileRef],
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO branches(
                    name, head_version_id, kind, created_at, owner
                ) VALUES (?, NULL, ?, ?, ?)
                """,
                (
                    record.branch,
                    _branch_kind(record.branch),
                    record.created_at,
                    record.author,
                ),
            )
            conn.execute(
                """
                INSERT INTO versions(
                    id, branch, parent_id, step, message, author, created_at,
                    recipe_hash, manifest_hash, capture_mode, review_state,
                    retention_state, work_root_id, workspace_id, user_name, flow
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    record.work_root_id,
                    record.workspace_id,
                    record.user_name,
                    record.flow,
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
            head = conn.execute(
                "SELECT head_version_id FROM branches WHERE name = ?",
                (branch,),
            ).fetchone()
            if head is None or head["head_version_id"] is None:
                return []

            rows: list[sqlite3.Row] = []
            current_id: str | None = head["head_version_id"]
            visited: set[str] = set()
            while current_id is not None and len(rows) < limit and current_id not in visited:
                visited.add(current_id)
                row = conn.execute(
                    "SELECT * FROM versions WHERE id = ?",
                    (current_id,),
                ).fetchone()
                if row is None:
                    break
                rows.append(row)
                current_id = row["parent_id"]
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
        work_root_id=_row_value(row, "work_root_id"),
        workspace_id=_row_value(row, "workspace_id"),
        user_name=_row_value(row, "user_name"),
        flow=_row_value(row, "flow"),
    )


def _branch_from_row(row: sqlite3.Row) -> BranchRecord:
    return BranchRecord(
        name=row["name"],
        head_version_id=row["head_version_id"],
        kind=_row_value(row, "kind", "named"),
        created_at=_row_value(row, "created_at"),
        source_ref=_row_value(row, "source_ref"),
        source_version_id=_row_value(row, "source_version_id"),
        owner=_row_value(row, "owner"),
    )


def _branch_event_from_row(row: sqlite3.Row) -> BranchEvent:
    return BranchEvent(
        id=row["id"],
        branch=row["branch"],
        event_type=row["event_type"],
        old_head_version_id=row["old_head_version_id"],
        new_head_version_id=row["new_head_version_id"],
        actor=row["actor"],
        created_at=row["created_at"],
        reason=row["reason"],
    )


def _branch_kind(branch_name: str) -> str:
    if branch_name == "main":
        return "main"
    if branch_name.startswith("workspace/"):
        return "workspace"
    return "named"


def _ensure_column(
    conn: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_definition: str,
) -> None:
    columns = {
        row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})")
    }
    if column_name not in columns:
        conn.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
        )


def _row_value(row: sqlite3.Row, column_name: str, default: str = "") -> str:
    return row[column_name] if column_name in row.keys() else default
