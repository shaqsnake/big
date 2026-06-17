from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import shutil
import stat


@dataclass(frozen=True)
class FileStatSnapshot:
    size: int
    mtime_ns: int
    ctime_ns: int
    inode: int
    missing_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class CapturedFile:
    source: Path
    staged: Path
    cas_hash: str
    size: int
    mtime_ns: int
    source_before: FileStatSnapshot
    source_after: FileStatSnapshot


class UnstableFileError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stat_snapshot(stat_result: os.stat_result) -> FileStatSnapshot:
    missing_fields: list[str] = []

    def value(name: str) -> int:
        item = getattr(stat_result, name, None)
        if item is None:
            missing_fields.append(name)
            return 0
        return int(item)

    return FileStatSnapshot(
        size=value("st_size"),
        mtime_ns=value("st_mtime_ns"),
        ctime_ns=value("st_ctime_ns"),
        inode=value("st_ino"),
        missing_fields=tuple(missing_fields),
    )


def stable_copy_to_staging(source: Path, staging_path: Path) -> CapturedFile:
    before = source.stat()
    before_snapshot = _stat_snapshot(before)
    staging_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, staging_path)
    after = source.stat()
    after_snapshot = _stat_snapshot(after)
    if (
        before_snapshot.size != after_snapshot.size
        or before_snapshot.mtime_ns != after_snapshot.mtime_ns
    ):
        raise UnstableFileError(f"Source changed during capture: {source}")
    return CapturedFile(
        source=source,
        staged=staging_path,
        cas_hash=sha256_file(staging_path),
        size=after_snapshot.size,
        mtime_ns=after_snapshot.mtime_ns,
        source_before=before_snapshot,
        source_after=after_snapshot,
    )


def object_path(cas_root: Path, cas_hash: str) -> Path:
    return cas_root / cas_hash[:2] / cas_hash[2:4] / cas_hash


def make_readonly(path: Path) -> None:
    os.chmod(path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)


def publish_object(cas_root: Path, staged: Path, expected_hash: str) -> Path:
    final_path = object_path(cas_root, expected_hash)
    if final_path.exists():
        if sha256_file(final_path) != expected_hash:
            raise RuntimeError(f"Existing CAS object hash mismatch: {final_path}")
        make_readonly(final_path)
        return final_path

    final_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with final_path.open("xb") as target, staged.open("rb") as source:
            shutil.copyfileobj(source, target, length=1024 * 1024)
    except FileExistsError:
        if sha256_file(final_path) != expected_hash:
            raise RuntimeError(f"Existing CAS object hash mismatch: {final_path}")
        make_readonly(final_path)
        return final_path

    actual_hash = sha256_file(final_path)
    if actual_hash != expected_hash:
        final_path.unlink(missing_ok=True)
        raise RuntimeError(f"Published object hash mismatch for {staged}")
    make_readonly(final_path)
    return final_path
