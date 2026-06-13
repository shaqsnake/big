from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import shutil
import stat


@dataclass(frozen=True)
class CapturedFile:
    source: Path
    staged: Path
    cas_hash: str
    size: int
    mtime_ns: int


class UnstableFileError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_copy_to_staging(source: Path, staging_path: Path) -> CapturedFile:
    before = source.stat()
    staging_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, staging_path)
    after = source.stat()
    if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
        raise UnstableFileError(f"Source changed during capture: {source}")
    return CapturedFile(
        source=source,
        staged=staging_path,
        cas_hash=sha256_file(staging_path),
        size=after.st_size,
        mtime_ns=after.st_mtime_ns,
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
