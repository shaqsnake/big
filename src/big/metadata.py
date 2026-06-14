from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
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


@dataclass(frozen=True)
class LifecycleEvent:
    id: int
    version_id: str
    old_review_state: str
    new_review_state: str
    old_retention_state: str
    new_retention_state: str
    actor: str
    created_at: str
    reason: str


@dataclass(frozen=True)
class AuditEvent:
    id: int
    action: str
    entity_type: str
    entity_id: str
    actor: str
    created_at: str
    payload_json: str
    previous_hash: str
    event_hash: str


@dataclass(frozen=True)
class AuditChainIssue:
    event_id: int
    issue: str


@dataclass(frozen=True)
class RetentionStorageSummary:
    retention_state: str
    versions: int
    logical_bytes: int


@dataclass(frozen=True)
class ReviewStorageSummary:
    review_state: str
    versions: int
    logical_bytes: int


@dataclass(frozen=True)
class StorageSummary:
    versions: int
    file_refs: int
    logical_bytes: int
    unique_referenced_objects: int
    unique_referenced_bytes: int
    by_review: tuple[ReviewStorageSummary, ...]
    by_retention: tuple[RetentionStorageSummary, ...]


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

                CREATE TABLE IF NOT EXISTS lifecycle_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version_id TEXT NOT NULL,
                    old_review_state TEXT NOT NULL,
                    new_review_state TEXT NOT NULL,
                    old_retention_state TEXT NOT NULL,
                    new_retention_state TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    FOREIGN KEY (version_id) REFERENCES versions(id)
                );

                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_versions_branch_created
                    ON versions(branch, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_file_refs_hash
                    ON file_refs(cas_hash);
                CREATE INDEX IF NOT EXISTS idx_branch_events_branch_created
                    ON branch_events(branch, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_lifecycle_events_version_created
                    ON lifecycle_events(version_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_audit_events_created
                    ON audit_events(created_at DESC, id DESC);
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
            _append_audit_event(
                conn,
                action="create_branch",
                entity_type="branch",
                entity_id=name,
                actor=owner,
                created_at=created_at,
                payload={
                    "name": name,
                    "head_version_id": head_version_id,
                    "kind": kind,
                    "source_ref": source_ref,
                    "source_version_id": source_version_id,
                },
            )

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
            _append_audit_event(
                conn,
                action="reset",
                entity_type="branch",
                entity_id=branch,
                actor=actor,
                created_at=created_at,
                payload={
                    "branch": branch,
                    "old_head_version_id": expected_old_head,
                    "new_head_version_id": new_head,
                    "reason": reason,
                },
            )

    def list_branch_events(self, branch: str, limit: int = 20) -> list[BranchEvent]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM branch_events
                WHERE branch = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (branch, limit),
            ).fetchall()
        return [_branch_event_from_row(row) for row in rows]

    def update_review_state(
        self,
        version_id: str,
        expected_old_review_state: str,
        new_review_state: str,
        actor: str,
        created_at: str,
        reason: str,
    ) -> None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT review_state, retention_state
                FROM versions
                WHERE id = ?
                """,
                (version_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Version not found: {version_id}")

            old_review_state = row["review_state"]
            old_retention_state = row["retention_state"]
            if old_review_state != expected_old_review_state:
                raise ValueError(f"Version review state changed: {version_id}")

            conn.execute(
                """
                UPDATE versions
                SET review_state = ?
                WHERE id = ? AND review_state = ?
                """,
                (new_review_state, version_id, expected_old_review_state),
            )
            conn.execute(
                """
                INSERT INTO lifecycle_events(
                    version_id, old_review_state, new_review_state,
                    old_retention_state, new_retention_state, actor, created_at,
                    reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    version_id,
                    old_review_state,
                    new_review_state,
                    old_retention_state,
                    old_retention_state,
                    actor,
                    created_at,
                    reason,
                ),
            )
            _append_audit_event(
                conn,
                action="promote",
                entity_type="version",
                entity_id=version_id,
                actor=actor,
                created_at=created_at,
                payload={
                    "version_id": version_id,
                    "old_review_state": old_review_state,
                    "new_review_state": new_review_state,
                    "old_retention_state": old_retention_state,
                    "new_retention_state": old_retention_state,
                    "reason": reason,
                },
            )

    def update_retention_state(
        self,
        version_id: str,
        expected_old_retention_state: str,
        new_retention_state: str,
        actor: str,
        created_at: str,
        reason: str,
    ) -> None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT review_state, retention_state
                FROM versions
                WHERE id = ?
                """,
                (version_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Version not found: {version_id}")

            old_review_state = row["review_state"]
            old_retention_state = row["retention_state"]
            if old_retention_state != expected_old_retention_state:
                raise ValueError(f"Version retention state changed: {version_id}")

            conn.execute(
                """
                UPDATE versions
                SET retention_state = ?
                WHERE id = ? AND retention_state = ?
                """,
                (new_retention_state, version_id, expected_old_retention_state),
            )
            conn.execute(
                """
                INSERT INTO lifecycle_events(
                    version_id, old_review_state, new_review_state,
                    old_retention_state, new_retention_state, actor, created_at,
                    reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    version_id,
                    old_review_state,
                    old_review_state,
                    old_retention_state,
                    new_retention_state,
                    actor,
                    created_at,
                    reason,
                ),
            )
            _append_audit_event(
                conn,
                action="degrade",
                entity_type="version",
                entity_id=version_id,
                actor=actor,
                created_at=created_at,
                payload={
                    "version_id": version_id,
                    "review_state": old_review_state,
                    "old_retention_state": old_retention_state,
                    "new_retention_state": new_retention_state,
                    "reason": reason,
                },
            )

    def list_lifecycle_events(
        self,
        version_id: str,
        limit: int = 20,
    ) -> list[LifecycleEvent]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM lifecycle_events
                WHERE version_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (version_id, limit),
            ).fetchall()
        return [_lifecycle_event_from_row(row) for row in rows]

    def list_audit_events(self, limit: int = 20) -> list[AuditEvent]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM audit_events
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [_audit_event_from_row(row) for row in rows]

    def verify_audit_chain(self) -> tuple[int, list[AuditChainIssue]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM audit_events
                ORDER BY id ASC
                """
            ).fetchall()

        issues: list[AuditChainIssue] = []
        previous_hash = ""
        for row in rows:
            event = _audit_event_from_row(row)
            if event.previous_hash != previous_hash:
                issues.append(
                    AuditChainIssue(
                        event_id=event.id,
                        issue="previous_hash mismatch",
                    )
                )
            expected_hash = _audit_hash(
                action=event.action,
                entity_type=event.entity_type,
                entity_id=event.entity_id,
                actor=event.actor,
                created_at=event.created_at,
                payload_json=event.payload_json,
                previous_hash=event.previous_hash,
            )
            if event.event_hash != expected_hash:
                issues.append(
                    AuditChainIssue(
                        event_id=event.id,
                        issue="event_hash mismatch",
                    )
                )
            previous_hash = event.event_hash

        return len(rows), issues

    def storage_summary(self) -> StorageSummary:
        with self.connect() as conn:
            version_row = conn.execute(
                "SELECT COUNT(*) AS count FROM versions"
            ).fetchone()
            ref_row = conn.execute(
                """
                SELECT COUNT(*) AS count, COALESCE(SUM(size), 0) AS bytes
                FROM file_refs
                """
            ).fetchone()
            unique_row = conn.execute(
                """
                SELECT COUNT(*) AS count, COALESCE(SUM(size), 0) AS bytes
                FROM (
                    SELECT cas_hash, MAX(size) AS size
                    FROM file_refs
                    GROUP BY cas_hash
                )
                """
            ).fetchone()
            retention_rows = conn.execute(
                """
                SELECT
                    versions.retention_state AS retention_state,
                    COUNT(DISTINCT versions.id) AS versions,
                    COALESCE(SUM(file_refs.size), 0) AS logical_bytes
                FROM versions
                LEFT JOIN file_refs ON file_refs.version_id = versions.id
                GROUP BY versions.retention_state
                ORDER BY versions.retention_state
                """
            ).fetchall()
            review_rows = conn.execute(
                """
                SELECT
                    versions.review_state AS review_state,
                    COUNT(DISTINCT versions.id) AS versions,
                    COALESCE(SUM(file_refs.size), 0) AS logical_bytes
                FROM versions
                LEFT JOIN file_refs ON file_refs.version_id = versions.id
                GROUP BY versions.review_state
                ORDER BY versions.review_state
                """
            ).fetchall()

        return StorageSummary(
            versions=version_row["count"],
            file_refs=ref_row["count"],
            logical_bytes=ref_row["bytes"],
            unique_referenced_objects=unique_row["count"],
            unique_referenced_bytes=unique_row["bytes"],
            by_review=tuple(
                ReviewStorageSummary(
                    review_state=row["review_state"],
                    versions=row["versions"],
                    logical_bytes=row["logical_bytes"],
                )
                for row in review_rows
            ),
            by_retention=tuple(
                RetentionStorageSummary(
                    retention_state=row["retention_state"],
                    versions=row["versions"],
                    logical_bytes=row["logical_bytes"],
                )
                for row in retention_rows
            ),
        )

    def create_version(
        self,
        record: VersionRecord,
        files: Iterable[FileRef],
    ) -> None:
        file_refs = list(files)
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
                    for item in file_refs
                ],
            )
            conn.execute(
                "UPDATE branches SET head_version_id = ? WHERE name = ?",
                (record.id, record.branch),
            )
            _append_audit_event(
                conn,
                action="commit",
                entity_type="version",
                entity_id=record.id,
                actor=record.author,
                created_at=record.created_at,
                payload={
                    "version_id": record.id,
                    "branch": record.branch,
                    "parent_id": record.parent_id or "",
                    "step": record.step,
                    "message": record.message,
                    "recipe_hash": record.recipe_hash,
                    "manifest_hash": record.manifest_hash,
                    "review_state": record.review_state,
                    "retention_state": record.retention_state,
                    "workspace_id": record.workspace_id,
                    "input_count": sum(1 for item in file_refs if item.role == "input"),
                    "output_count": sum(1 for item in file_refs if item.role == "output"),
                },
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

    def list_all_file_refs(self) -> list[tuple[str, FileRef]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    version_id, role, path, cas_hash, size, semantic_role,
                    format_hint
                FROM file_refs
                ORDER BY version_id, role, path
                """
            ).fetchall()
        return [
            (
                row["version_id"],
                FileRef(
                    role=row["role"],
                    path=row["path"],
                    cas_hash=row["cas_hash"],
                    size=row["size"],
                    semantic_role=row["semantic_role"],
                    format_hint=row["format_hint"],
                ),
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


def _lifecycle_event_from_row(row: sqlite3.Row) -> LifecycleEvent:
    return LifecycleEvent(
        id=row["id"],
        version_id=row["version_id"],
        old_review_state=row["old_review_state"],
        new_review_state=row["new_review_state"],
        old_retention_state=row["old_retention_state"],
        new_retention_state=row["new_retention_state"],
        actor=row["actor"],
        created_at=row["created_at"],
        reason=row["reason"],
    )


def _audit_event_from_row(row: sqlite3.Row) -> AuditEvent:
    return AuditEvent(
        id=row["id"],
        action=row["action"],
        entity_type=row["entity_type"],
        entity_id=row["entity_id"],
        actor=row["actor"],
        created_at=row["created_at"],
        payload_json=row["payload_json"],
        previous_hash=row["previous_hash"],
        event_hash=row["event_hash"],
    )


def _append_audit_event(
    conn: sqlite3.Connection,
    action: str,
    entity_type: str,
    entity_id: str,
    actor: str,
    created_at: str,
    payload: dict[str, object],
) -> None:
    previous = conn.execute(
        "SELECT event_hash FROM audit_events ORDER BY id DESC LIMIT 1"
    ).fetchone()
    previous_hash = "" if previous is None else previous["event_hash"]
    payload_json = _canonical_json(payload)
    event_hash = _audit_hash(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor=actor,
        created_at=created_at,
        payload_json=payload_json,
        previous_hash=previous_hash,
    )
    conn.execute(
        """
        INSERT INTO audit_events(
            action, entity_type, entity_id, actor, created_at, payload_json,
            previous_hash, event_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            action,
            entity_type,
            entity_id,
            actor,
            created_at,
            payload_json,
            previous_hash,
            event_hash,
        ),
    )


def _audit_hash(
    action: str,
    entity_type: str,
    entity_id: str,
    actor: str,
    created_at: str,
    payload_json: str,
    previous_hash: str,
) -> str:
    payload = {
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "actor": actor,
        "created_at": created_at,
        "payload_json": payload_json,
        "previous_hash": previous_hash,
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


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
