from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import getpass
import glob
import hashlib
import json
from pathlib import Path
import re
import shutil
import uuid

import click

from .cas import (
    object_path,
    publish_object,
    sha256_file,
    stable_copy_to_staging,
    UnstableFileError,
)
from .config import (
    CONFIG_NAME,
    ensure_repo_dirs,
    find_config,
    RepoConfig,
    resolve_work_root,
    resolve_workspace_context,
    WorkspaceContext,
    WorkRoot,
    write_main_config,
    write_pointer_config,
)
from .metadata import FileRef, SQLiteMetadataRepository, VersionRecord


BRANCH_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
REVIEW_STATES = ("Exploring", "Candidate", "Pinned", "Golden")
REVIEW_STATE_ORDER = {state: index for index, state in enumerate(REVIEW_STATES)}
RETENTION_STATES = ("resident", "recipe_only", "archived", "missing")


def _repo_from_cwd() -> tuple[object, SQLiteMetadataRepository]:
    try:
        config, _ = find_config(Path.cwd())
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    ensure_repo_dirs(config)
    repo = SQLiteMetadataRepository(config.metadata_db)
    repo.init_schema()
    return config, repo


def _short_hash(value: str, length: int = 12) -> str:
    return value[:length]


def _json_hash(payload: object) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _format_hint(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    return suffix or "raw"


def _canonical_review_state(value: str) -> str:
    for state in REVIEW_STATES:
        if value.lower() == state.lower():
            return state
    choices = ", ".join(REVIEW_STATES)
    raise click.ClickException(
        f"Unknown review state: {value}; expected one of {choices}"
    )


def _canonical_retention_state(value: str) -> str:
    for state in RETENTION_STATES:
        if value.lower() == state.lower():
            return state
    choices = ", ".join(RETENTION_STATES)
    raise click.ClickException(
        f"Unknown retention state: {value}; expected one of {choices}"
    )


def _semantic_role(role: str, path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".tcl", ".sdc", ".yaml", ".yml", ".json", ".runset"}:
        return "script_or_config" if role == "input" else "tool_output"
    if suffix in {".v", ".sv", ".vg", ".lef", ".def", ".lib"}:
        return "eda_design_file"
    if suffix in {".rpt", ".log"}:
        return "report_or_log"
    return role


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _expand_pattern_args(patterns: tuple[str, ...]) -> list[str]:
    expanded: list[str] = []
    for value in patterns:
        for part in value.replace(",", ";").split(";"):
            pattern = part.strip()
            if pattern:
                expanded.append(pattern)
    return expanded


def _resolve_patterns(patterns: tuple[str, ...], workspace: Path, label: str) -> list[Path]:
    files: list[Path] = []
    missing: list[str] = []
    expanded_patterns = _expand_pattern_args(patterns)
    if not expanded_patterns:
        raise click.ClickException(f"No {label} patterns were provided")

    for pattern in expanded_patterns:
        pattern_path = Path(pattern)
        if pattern_path.is_absolute():
            matches = [Path(item) for item in glob.glob(str(pattern_path), recursive=True)]
        else:
            matches = [Path(item) for item in glob.glob(str(workspace / pattern), recursive=True)]
        matched_files = sorted(path.resolve() for path in matches if path.is_file())
        if not matched_files:
            missing.append(pattern)
        files.extend(matched_files)

    if missing:
        raise click.ClickException(
            f"No {label} files matched: " + ", ".join(sorted(missing))
        )

    unique = sorted(set(files))
    outside = [path for path in unique if workspace.resolve() not in path.parents and path != workspace.resolve()]
    if outside:
        raise click.ClickException(
            f"{label} files must be under the current workspace: {outside[0]}"
        )
    return unique


def _capture_files(
    role: str,
    files: list[Path],
    workspace: Path,
    staging_root: Path,
    cas_root: Path,
) -> list[FileRef]:
    refs: list[FileRef] = []
    for source in files:
        rel_path = source.relative_to(workspace).as_posix()
        staged_path = staging_root / role / rel_path
        try:
            captured = stable_copy_to_staging(source, staged_path)
        except UnstableFileError as exc:
            raise click.ClickException(str(exc)) from exc
        publish_object(cas_root, captured.staged, captured.cas_hash)
        refs.append(
            FileRef(
                role=role,
                path=rel_path,
                cas_hash=captured.cas_hash,
                size=captured.size,
                semantic_role=_semantic_role(role, source),
                format_hint=_format_hint(source),
            )
        )
    return refs


def _validate_branch_name(branch_name: str) -> None:
    if branch_name == "main" or branch_name.startswith("workspace/"):
        raise click.ClickException(f"Reserved branch name: {branch_name}")
    if (
        not BRANCH_NAME_RE.match(branch_name)
        or branch_name.endswith("/")
        or "//" in branch_name
    ):
        raise click.ClickException(f"Invalid branch name: {branch_name}")


def _current_workspace_branch(config: object) -> str:
    try:
        return _resolve_cli_workspace_context(config, Path.cwd()).default_branch
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


def _resolve_checkout_workspace_context(
    config: RepoConfig,
    path: Path,
) -> WorkspaceContext | None:
    resolved = path.resolve()
    start = resolved if resolved.is_dir() else resolved.parent
    try:
        work_root = resolve_work_root(config, start)
    except ValueError:
        return None

    for candidate in (start, *start.parents):
        if candidate != work_root.path and work_root.path not in candidate.parents:
            break
        marker_path = candidate / ".big-checkout.json"
        if not marker_path.exists():
            continue

        try:
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise click.ClickException(f"Invalid checkout marker: {marker_path}") from exc

        if (
            marker.get("schema") != 1
            or marker.get("repo_id") != config.repo_id
            or marker.get("materialization") not in {"copy", "partial"}
        ):
            raise click.ClickException(f"Checkout marker does not match repo: {marker_path}")

        target_path = Path(marker.get("target_path", "")).resolve()
        if target_path != candidate.resolve():
            raise click.ClickException(f"Checkout marker target mismatch: {marker_path}")

        work_root_id = str(marker.get("work_root_id", work_root.id))
        marker_work_root = next(
            (item for item in config.work_roots if item.id == work_root_id),
            work_root,
        )
        user = str(marker.get("user", ""))
        flow = str(marker.get("flow", ""))
        branch = str(marker.get("branch", ""))
        version = str(marker.get("version", ""))
        if not user or not flow or not branch or not version:
            raise click.ClickException(f"Checkout marker is incomplete: {marker_path}")

        return WorkspaceContext(
            work_root=marker_work_root,
            user=user,
            flow=flow,
            workspace_path=candidate.resolve(),
            workspace_id=(
                f"checkout/{marker_work_root.id}/{user}/{flow}/"
                f"{branch}@{version}"
            ),
            default_branch=branch,
        )
    return None


def _resolve_cli_workspace_context(config: RepoConfig, path: Path) -> WorkspaceContext:
    checkout_context = _resolve_checkout_workspace_context(config, path)
    if checkout_context is not None:
        return checkout_context
    return resolve_workspace_context(config, path)


def _resolve_source_ref(
    metadata: SQLiteMetadataRepository,
    source_ref: str,
) -> tuple[str, str]:
    branch = metadata.get_branch(source_ref)
    if branch is not None:
        if branch.head_version_id is None:
            raise click.ClickException(f"Source branch has no head version: {source_ref}")
        return source_ref, branch.head_version_id

    version = metadata.get_version(source_ref)
    if version is None:
        raise click.ClickException(f"Source ref not found or ambiguous: {source_ref}")
    return version.id, version.id


def _is_ancestor_version(
    metadata: SQLiteMetadataRepository,
    head_version_id: str,
    target_version_id: str,
) -> bool:
    current_id: str | None = head_version_id
    visited: set[str] = set()
    while current_id is not None and current_id not in visited:
        if current_id == target_version_id:
            return True
        visited.add(current_id)
        current = metadata.get_version(current_id)
        if current is None:
            return False
        current_id = current.parent_id
    return False


def _safe_path_token(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "__", value).strip("._-") or "unnamed"


def _checkout_target_path(
    workspace_context: WorkspaceContext,
    branch_name: str,
    version_id: str,
) -> Path:
    return (
        workspace_context.work_root.path
        / "user"
        / workspace_context.user
        / ".big-checkouts"
        / workspace_context.flow
        / _safe_path_token(branch_name)
        / version_id
    )


def _dedupe_checkout_refs(refs: list[FileRef]) -> list[FileRef]:
    by_path: dict[str, FileRef] = {}
    for ref in refs:
        existing = by_path.get(ref.path)
        if existing is None:
            by_path[ref.path] = ref
            continue
        if existing.cas_hash != ref.cas_hash or existing.size != ref.size:
            raise click.ClickException(
                f"Version contains conflicting FileRefs for path: {ref.path}"
            )
    return [by_path[path] for path in sorted(by_path)]


def _checkout_destination(root: Path, rel_path: str) -> Path:
    path = Path(rel_path)
    if path.is_absolute() or ".." in path.parts:
        raise click.ClickException(f"Unsafe FileRef path in manifest: {rel_path}")
    return root / path


def _checkout_marker_matches(
    target_path: Path,
    repo_id: str,
    branch_name: str,
    version_id: str,
    materialization_kind: str,
) -> bool:
    marker_path = target_path / ".big-checkout.json"
    if not marker_path.exists():
        return False
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        marker.get("schema") == 1
        and marker.get("repo_id") == repo_id
        and marker.get("branch") == branch_name
        and marker.get("version") == version_id
        and marker.get("materialization") == materialization_kind
    )


def _copy_checkout_refs(cas_root: Path, refs: list[FileRef], target_root: Path) -> None:
    for ref in refs:
        source = object_path(cas_root, ref.cas_hash)
        if not source.exists():
            raise click.ClickException(
                f"Missing CAS object for {ref.role} {ref.path}: "
                f"{_short_hash(ref.cas_hash)}"
            )
        actual_size = source.stat().st_size
        if actual_size != ref.size:
            raise click.ClickException(
                f"CAS object size mismatch for {ref.role} {ref.path}: "
                f"{ref.size}->{actual_size}"
            )
        actual_hash = sha256_file(source)
        if actual_hash != ref.cas_hash:
            raise click.ClickException(
                f"CAS object hash mismatch for {ref.role} {ref.path}: "
                f"{_short_hash(ref.cas_hash)}->{_short_hash(actual_hash)}"
            )

        destination = _checkout_destination(target_root, ref.path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        destination.chmod(0o644)


def _materialize_checkout(
    config: object,
    workspace_context: WorkspaceContext,
    branch_name: str,
    version_id: str,
    target_path: Path,
    refs: list[FileRef],
    materialization_kind: str,
    omitted_outputs: int = 0,
) -> str:
    if target_path.exists():
        if not target_path.is_dir():
            raise click.ClickException(
                f"Checkout target already exists and is not a directory: {target_path}"
            )
        if _checkout_marker_matches(
            target_path,
            repo_id=config.repo_id,
            branch_name=branch_name,
            version_id=version_id,
            materialization_kind=materialization_kind,
        ):
            return "reused"
        raise click.ClickException(
            f"Checkout target already exists and is not reusable: {target_path}"
        )

    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.parent / f".{target_path.name}.tmp-{uuid.uuid4().hex}"
    total_bytes = sum(ref.size for ref in refs)
    marker = {
        "schema": 1,
        "repo_id": config.repo_id,
        "branch": branch_name,
        "version": version_id,
        "materialization": materialization_kind,
        "source_workspace": str(workspace_context.workspace_path),
        "target_path": str(target_path),
        "work_root_id": workspace_context.work_root.id,
        "user": workspace_context.user,
        "flow": workspace_context.flow,
        "files": len(refs),
        "bytes": total_bytes,
        "omitted_outputs": omitted_outputs,
        "created_at": _utc_now(),
    }

    try:
        temp_path.mkdir()
        _copy_checkout_refs(config.cas_dir, refs, temp_path)
        (temp_path / ".big-checkout.json").write_text(
            json.dumps(marker, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        shutil.move(str(temp_path), str(target_path))
    except click.ClickException:
        shutil.rmtree(temp_path, ignore_errors=True)
        raise
    except OSError as exc:
        shutil.rmtree(temp_path, ignore_errors=True)
        raise click.ClickException(f"Failed to materialize checkout: {exc}") from exc
    if materialization_kind == "copy":
        return "copied"
    return materialization_kind


def _workspace_state_path(workspace_path: Path) -> Path:
    return workspace_path / ".big-workspace.json"


def _read_workspace_generation(workspace_path: Path, repo_id: str) -> int:
    state_path = _workspace_state_path(workspace_path)
    if not state_path.exists():
        return 0
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise click.ClickException(f"Invalid workspace state marker: {state_path}") from exc
    if state.get("schema") != 1 or state.get("repo_id") != repo_id:
        raise click.ClickException(f"Workspace state marker does not match repo: {state_path}")
    try:
        return int(state.get("generation", 0))
    except (TypeError, ValueError) as exc:
        raise click.ClickException(f"Invalid workspace generation: {state_path}") from exc


def _write_workspace_state(
    workspace_path: Path,
    repo_id: str,
    branch_name: str,
    workspace_id: str,
    generation: int,
    restored_from: str,
    journal_id: str,
    actor: str,
    restored_at: str,
) -> None:
    state = {
        "schema": 1,
        "repo_id": repo_id,
        "branch": branch_name,
        "workspace_id": workspace_id,
        "generation": generation,
        "restored_from": restored_from,
        "restore_journal_id": journal_id,
        "restored_at": restored_at,
        "actor": actor,
    }
    _workspace_state_path(workspace_path).write_text(
        json.dumps(state, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _workspace_internal_path(rel_path: str) -> bool:
    parts = Path(rel_path).parts
    return (
        rel_path in {".big-checkout.json", ".big-workspace.json"}
        or any(part.startswith(".big-restore-") for part in parts)
    )


def _workspace_file_paths(workspace_path: Path) -> set[str]:
    files: set[str] = set()
    if not workspace_path.exists():
        return files
    for path in workspace_path.rglob("*"):
        if not path.is_file():
            continue
        rel_path = path.relative_to(workspace_path).as_posix()
        if _workspace_internal_path(rel_path):
            continue
        files.add(rel_path)
    return files


def _dirty_refs(workspace_path: Path, refs: list[FileRef]) -> list[tuple[str, FileRef]]:
    dirty: list[tuple[str, FileRef]] = []
    for ref in refs:
        destination = _checkout_destination(workspace_path, ref.path)
        if not destination.exists():
            dirty.append(("missing", ref))
            continue
        if destination.stat().st_size != ref.size:
            dirty.append(("modified", ref))
            continue
        if sha256_file(destination) != ref.cas_hash:
            dirty.append(("modified", ref))
    return dirty


def _restore_plan(
    workspace_path: Path,
    current_refs: list[FileRef],
    target_refs: list[FileRef],
) -> dict[str, object]:
    current_by_path = {ref.path: ref for ref in _dedupe_checkout_refs(current_refs)}
    target_by_path = {ref.path: ref for ref in _dedupe_checkout_refs(target_refs)}
    workspace_files = _workspace_file_paths(workspace_path)

    add_paths = sorted(set(target_by_path) - set(current_by_path))
    overwrite_paths = sorted(
        path
        for path in set(target_by_path) & set(current_by_path)
        if (
            target_by_path[path].cas_hash != current_by_path[path].cas_hash
            or target_by_path[path].size != current_by_path[path].size
        )
    )
    keep_paths = sorted(
        path
        for path in set(target_by_path) & set(current_by_path)
        if (
            target_by_path[path].cas_hash == current_by_path[path].cas_hash
            and target_by_path[path].size == current_by_path[path].size
        )
    )
    delete_paths = sorted(workspace_files - set(target_by_path))
    bytes_to_write = sum(target_by_path[path].size for path in add_paths + overwrite_paths)

    return {
        "add_paths": add_paths,
        "overwrite_paths": overwrite_paths,
        "delete_paths": delete_paths,
        "keep_paths": keep_paths,
        "add": len(add_paths),
        "overwrite": len(overwrite_paths),
        "delete": len(delete_paths),
        "keep": len(keep_paths),
        "changed_files": len(add_paths) + len(overwrite_paths) + len(delete_paths),
        "bytes": bytes_to_write,
    }


def _print_dirty_summary(dirty: list[tuple[str, FileRef]]) -> None:
    click.echo("dirty: yes")
    click.echo(f"dirty_files: {len(dirty)}")
    for state, ref in dirty[:10]:
        click.echo(f"  {state} {ref.role} {ref.path}")
    if len(dirty) > 10:
        click.echo(f"  ... {len(dirty) - 10} more")


def _print_restore_plan(
    branch_name: str,
    current_head: str,
    target_version: str,
    workspace_context: WorkspaceContext,
    generation_current: int,
    generation_next: int,
    plan: dict[str, object],
    delete_missing: bool,
    materialization: str,
    journal_id: str | None = None,
) -> None:
    click.echo(f"branch: {branch_name}")
    click.echo(f"current_head: {current_head}")
    click.echo(f"target_version: {target_version}")
    click.echo(f"workspace: {workspace_context.workspace_id}")
    click.echo(f"workspace_path: {workspace_context.workspace_path}")
    click.echo(f"generation_current: {generation_current}")
    click.echo(f"generation_next: {generation_next}")
    click.echo("dirty: no")
    click.echo("active_lease_check: not-implemented")
    click.echo(
        "quiet_state: user-confirmed" if materialization == "restored" else "quiet_state: required"
    )
    click.echo(f"add: {plan['add']}")
    click.echo(f"overwrite: {plan['overwrite']}")
    click.echo(f"delete: {plan['delete']}")
    click.echo(f"keep: {plan['keep']}")
    click.echo(f"changed_files: {plan['changed_files']}")
    click.echo(f"bytes: {plan['bytes']}")
    click.echo(f"delete_missing: {'yes' if delete_missing else 'no'}")
    click.echo(f"journal: {journal_id or 'plan-only'}")
    click.echo(f"materialization: {materialization}")


def _restore_journal_path(config: RepoConfig, journal_id: str) -> Path:
    return config.big_dir / "restore-journals" / f"{journal_id}.json"


def _write_restore_journal(config: RepoConfig, journal: dict[str, object]) -> None:
    path = _restore_journal_path(config, str(journal["journal_id"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(journal, indent=2, sort_keys=True), encoding="utf-8")


def _restore_ref_from_cas(cas_root: Path, workspace_path: Path, ref: FileRef) -> None:
    source = object_path(cas_root, ref.cas_hash)
    if not source.exists():
        raise click.ClickException(
            f"Missing CAS object for {ref.role} {ref.path}: {_short_hash(ref.cas_hash)}"
        )
    if source.stat().st_size != ref.size:
        raise click.ClickException(f"CAS object size mismatch for {ref.role} {ref.path}")
    if sha256_file(source) != ref.cas_hash:
        raise click.ClickException(f"CAS object hash mismatch for {ref.role} {ref.path}")

    destination = _checkout_destination(workspace_path, ref.path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.parent / f".big-restore-{uuid.uuid4().hex}-{destination.name}"
    try:
        shutil.copyfile(source, temp_path)
        if temp_path.stat().st_size != ref.size or sha256_file(temp_path) != ref.cas_hash:
            raise click.ClickException(f"Restored temp file verification failed: {ref.path}")
        if destination.exists():
            destination.chmod(0o644)
        try:
            temp_path.replace(destination)
        except OSError:
            shutil.copyfile(temp_path, destination)
        destination.chmod(0o644)
    finally:
        temp_path.unlink(missing_ok=True)


def _delete_restore_path(workspace_path: Path, rel_path: str) -> None:
    destination = _checkout_destination(workspace_path, rel_path)
    if destination.exists():
        destination.chmod(0o644)
        destination.unlink()


def _parse_work_root(value: str) -> WorkRoot:
    if "=" not in value:
        raise click.BadParameter("Expected id=path")
    root_id, raw_path = value.split("=", 1)
    root_id = root_id.strip()
    raw_path = raw_path.strip()
    if not root_id or not raw_path:
        raise click.BadParameter("Expected non-empty id=path")
    if "/" in root_id or "\\" in root_id:
        raise click.BadParameter("Work root id must not contain path separators")
    return WorkRoot(id=root_id, role=root_id, path=Path(raw_path).resolve())


def _build_work_roots(root: Path, values: tuple[str, ...]) -> tuple[WorkRoot, ...]:
    if not values:
        return (WorkRoot(id="default", role="default", path=root),)
    work_roots = tuple(_parse_work_root(value) for value in values)
    ids = [item.id for item in work_roots]
    if len(ids) != len(set(ids)):
        raise click.ClickException("Duplicate work root id")
    paths = [item.path for item in work_roots]
    if len(paths) != len(set(paths)):
        raise click.ClickException("Duplicate work root path")
    if root not in paths:
        raise click.ClickException("Main repo path must be one registered work root")
    return work_roots


def _shell_init_script(shell: str) -> str:
    return f"""# BIG shell integration for {shell}.
# Load it with:
#   eval "$(big shell-init {shell})"
big() {{
  if [ "$#" -gt 0 ] && [ "$1" = "checkout" ]; then
    local __big_output __big_status __big_target
    __big_output="$(command big "$@" 2>&1)"
    __big_status=$?
    printf '%s\\n' "$__big_output"
    if [ "$__big_status" -eq 0 ] && ! printf '%s\\n' "$__big_output" | grep -q '^materialization: plan-only$'; then
      __big_target="$(printf '%s\\n' "$__big_output" | sed -n 's/^cd: cd -- //p' | tail -n 1)"
      if [ -n "$__big_target" ]; then
        cd -- "$__big_target" || return $?
      fi
    fi
    return "$__big_status"
  fi
  command big "$@"
}}
"""


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def main() -> None:
    """BIG prototype CLI for EDA artifact snapshots."""


@main.group()
def repo() -> None:
    """Repository administration commands."""


@main.group()
def branch() -> None:
    """Branch metadata commands."""


@main.group()
def lifecycle() -> None:
    """Lifecycle metadata commands."""


@main.group()
def audit() -> None:
    """Audit hash-chain commands."""


@repo.command("init")
@click.argument("path", type=click.Path(path_type=Path))
@click.option("--repo-id", required=True, help="Logical BIG repository id.")
@click.option(
    "--integration",
    default="2d",
    show_default=True,
    type=click.Choice(["2d", "3d"]),
    help="Project integration type. 3d is reserved for 3DIC layout roots.",
)
@click.option(
    "--work-root",
    "work_root_values",
    multiple=True,
    help="Registered work root in id=path form. Repeat for 3DIC roots.",
)
def repo_init(
    path: Path,
    repo_id: str,
    integration: str,
    work_root_values: tuple[str, ...],
) -> None:
    """Initialize a prototype BIG repository."""
    root = path.resolve()
    root.mkdir(parents=True, exist_ok=True)

    config_path = root / CONFIG_NAME
    if config_path.exists():
        click.echo(f"BIG repo already initialized: {config_path}")
        config, _ = find_config(root)
        repo_id = config.repo_id
        integration = config.integration
        work_roots = config.work_roots
    else:
        work_roots = _build_work_roots(root, work_root_values)
        for item in work_roots:
            item.path.mkdir(parents=True, exist_ok=True)
        write_main_config(
            root,
            repo_id=repo_id,
            integration=integration,
            work_roots=work_roots,
        )
        click.echo(f"created {config_path}")

    for item in work_roots:
        item.path.mkdir(parents=True, exist_ok=True)

    for item in work_roots:
        if item.path == root:
            continue
        pointer_path = item.path / CONFIG_NAME
        if pointer_path.exists():
            click.echo(f"BIG work root pointer already initialized: {pointer_path}")
        else:
            write_pointer_config(
                item.path,
                repo_id=repo_id,
                integration=integration,
                home=root,
                work_root_id=item.id,
            )
            click.echo(f"created {pointer_path}")

    config, _ = find_config(root)
    ensure_repo_dirs(config)
    SQLiteMetadataRepository(config.metadata_db).init_schema()
    click.echo(f"repo: {config.repo_id}")
    click.echo(f"home: {config.home}")
    click.echo(f"metadata: {config.metadata_db}")
    click.echo(f"work_roots: {len(config.work_roots)}")


@main.command("checkout")
@click.argument("target_ref")
@click.option(
    "--new-branch",
    default=None,
    help="Create a named branch from a version ref before entering its checkout.",
)
@click.option(
    "--plan",
    is_flag=True,
    help="Resolve branch and target path only; do not materialize files.",
)
@click.option(
    "--print-path",
    is_flag=True,
    help="Print only the target path. Combine with --plan for no side effects.",
)
def checkout_cmd(
    target_ref: str,
    new_branch: str | None,
    plan: bool,
    print_path: bool,
) -> None:
    """Checkout a branch into a user-private materialized directory."""
    config, metadata = _repo_from_cwd()
    try:
        workspace_context = _resolve_cli_workspace_context(config, Path.cwd())
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    source_ref = ""
    if new_branch is not None:
        _validate_branch_name(new_branch)
        if metadata.get_branch(new_branch) is not None:
            raise click.ClickException(f"Branch already exists: {new_branch}")
        version = metadata.get_version(target_ref)
        if version is None:
            raise click.ClickException(f"Version not found or ambiguous: {target_ref}")
        branch_name = new_branch
        source_ref = version.id
    else:
        branch_record = metadata.get_branch(target_ref)
        if branch_record is None:
            if metadata.get_version(target_ref) is not None:
                raise click.ClickException(
                    "Version checkout requires --new-branch <branch-name>"
                )
            raise click.ClickException(f"Branch/ref not found: {target_ref}")
        if branch_record.head_version_id is None:
            raise click.ClickException(f"Branch/ref has no head version: {target_ref}")
        version = metadata.get_version(branch_record.head_version_id)
        if version is None:
            raise click.ClickException(
                f"Head version not found: {branch_record.head_version_id}"
            )
        branch_name = branch_record.name

    target_path = _checkout_target_path(
        workspace_context,
        branch_name=branch_name,
        version_id=version.id,
    )
    if target_path == workspace_context.workspace_path:
        raise click.ClickException("Checkout target path matches source workspace")

    if print_path and plan:
        click.echo(target_path)
        return

    all_refs = _dedupe_checkout_refs(metadata.get_file_refs(version.id))
    refs = all_refs
    checkout_scope = "full"
    materialization_kind = "copy"
    omitted_outputs = 0
    if version.retention_state == "recipe_only":
        refs = [ref for ref in all_refs if ref.role == "input"]
        omitted_outputs = sum(1 for ref in all_refs if ref.role == "output")
        checkout_scope = "inputs-only"
        materialization_kind = "partial"
    total_bytes = sum(ref.size for ref in refs)
    materialization = "plan-only"
    if not plan:
        materialization = _materialize_checkout(
            config=config,
            workspace_context=workspace_context,
            branch_name=branch_name,
            version_id=version.id,
            target_path=target_path,
            refs=refs,
            materialization_kind=materialization_kind,
            omitted_outputs=omitted_outputs,
        )
        if new_branch is not None:
            try:
                metadata.create_branch(
                    name=new_branch,
                    head_version_id=version.id,
                    kind="named",
                    created_at=_utc_now(),
                    source_ref=source_ref,
                    source_version_id=version.id,
                    owner=getpass.getuser(),
                )
            except ValueError as exc:
                raise click.ClickException(str(exc)) from exc

    if print_path:
        click.echo(target_path)
        return

    click.echo(f"branch: {branch_name}")
    click.echo(f"version: {version.id}")
    if new_branch is not None:
        click.echo(f"source_ref: {source_ref}")
        click.echo(f"branch_created: {'plan-only' if plan else 'yes'}")
    click.echo(f"source_workspace: {workspace_context.workspace_path}")
    click.echo(f"target_path: {target_path}")
    click.echo(f"retention: {version.retention_state}")
    click.echo(f"checkout_scope: {checkout_scope}")
    if omitted_outputs:
        click.echo(f"omitted_outputs: {omitted_outputs}")
    click.echo(f"files: {len(refs)}")
    click.echo(f"bytes: {total_bytes}")
    click.echo(f"materialization: {materialization}")
    click.echo(f"cd: cd -- {target_path}")


@main.command("shell-init")
@click.argument("shell", type=click.Choice(["bash", "zsh"]))
def shell_init_cmd(shell: str) -> None:
    """Print shell integration for checkout directory switching."""
    click.echo(_shell_init_script(shell), nl=False)


@repo.command("stats")
def repo_stats_cmd() -> None:
    """Show repository storage usage statistics."""
    config, metadata = _repo_from_cwd()
    summary = metadata.storage_summary()
    cas_objects, cas_bytes = _scan_cas_objects(config.cas_dir)
    dedupe_ratio = (
        summary.logical_bytes / summary.unique_referenced_bytes
        if summary.unique_referenced_bytes
        else 1.0
    )

    click.echo(f"repo: {config.repo_id}")
    click.echo(f"versions: {summary.versions}")
    click.echo(f"file_refs: {summary.file_refs}")
    click.echo(f"logical_bytes: {summary.logical_bytes}")
    click.echo(f"unique_referenced_objects: {summary.unique_referenced_objects}")
    click.echo(f"unique_referenced_bytes: {summary.unique_referenced_bytes}")
    click.echo(f"cas_objects: {cas_objects}")
    click.echo(f"cas_bytes: {cas_bytes}")
    click.echo(f"dedupe_ratio: {dedupe_ratio:.2f}x")
    if summary.by_review:
        click.echo("review:")
        for item in summary.by_review:
            click.echo(
                f"  {item.review_state}: "
                f"versions={item.versions} logical_bytes={item.logical_bytes}"
            )
    if summary.by_retention:
        click.echo("retention:")
        for item in summary.by_retention:
            click.echo(
                f"  {item.retention_state}: "
                f"versions={item.versions} logical_bytes={item.logical_bytes}"
            )


@repo.command("verify")
@click.option("--full", "show_full", is_flag=True, help="Show every failed FileRef.")
def repo_verify_cmd(show_full: bool) -> None:
    """Verify every referenced CAS object in the repository."""
    config, metadata = _repo_from_cwd()
    summary = metadata.storage_summary()
    refs = metadata.list_all_file_refs()
    missing, size_mismatch, hash_mismatch = _verify_file_refs(config.cas_dir, refs)
    failures = len(missing) + len(size_mismatch) + len(hash_mismatch)

    click.echo(f"repo: {config.repo_id}")
    click.echo(f"versions: {summary.versions}")
    click.echo(f"file_refs: {len(refs)}")
    click.echo(f"missing: {len(missing)}")
    click.echo(f"size_mismatch: {len(size_mismatch)}")
    click.echo(f"hash_mismatch: {len(hash_mismatch)}")
    click.echo(f"integrity: {'ok' if failures == 0 else 'failed'}")

    if show_full and failures:
        _print_integrity_failures(
            missing,
            size_mismatch,
            hash_mismatch,
            include_version=True,
        )

    if failures:
        raise click.ClickException("Repository CAS integrity verification failed")


def _scan_cas_objects(cas_dir: Path) -> tuple[int, int]:
    if not cas_dir.exists():
        return 0, 0
    count = 0
    total_bytes = 0
    for path in cas_dir.rglob("*"):
        if path.is_file():
            count += 1
            total_bytes += path.stat().st_size
    return count, total_bytes


def _verify_file_refs(
    cas_dir: Path,
    refs: list[tuple[str, FileRef]],
) -> tuple[
    list[tuple[str, FileRef]],
    list[tuple[str, FileRef, int]],
    list[tuple[str, FileRef, str]],
]:
    missing: list[tuple[str, FileRef]] = []
    size_mismatch: list[tuple[str, FileRef, int]] = []
    hash_mismatch: list[tuple[str, FileRef, str]] = []
    for version_id, ref in refs:
        path = object_path(cas_dir, ref.cas_hash)
        if not path.exists():
            missing.append((version_id, ref))
            continue
        actual_size = path.stat().st_size
        if actual_size != ref.size:
            size_mismatch.append((version_id, ref, actual_size))
            continue
        actual_hash = sha256_file(path)
        if actual_hash != ref.cas_hash:
            hash_mismatch.append((version_id, ref, actual_hash))
    return missing, size_mismatch, hash_mismatch


def _print_integrity_failures(
    missing: list[tuple[str, FileRef]],
    size_mismatch: list[tuple[str, FileRef, int]],
    hash_mismatch: list[tuple[str, FileRef, str]],
    include_version: bool,
) -> None:
    for version_id, ref in missing:
        context = f"{version_id} " if include_version else ""
        click.echo(
            f"missing {context}{ref.role} {ref.path} {_short_hash(ref.cas_hash)}"
        )
    for version_id, ref, actual_size in size_mismatch:
        context = f"{version_id} " if include_version else ""
        click.echo(
            f"size_mismatch {context}{ref.role} {ref.path} "
            f"{ref.size}->{actual_size} {_short_hash(ref.cas_hash)}"
        )
    for version_id, ref, actual_hash in hash_mismatch:
        context = f"{version_id} " if include_version else ""
        click.echo(
            f"hash_mismatch {context}{ref.role} {ref.path} "
            f"{_short_hash(ref.cas_hash)}->{_short_hash(actual_hash)}"
        )


@main.command("status")
def status_cmd() -> None:
    """Show current repo and workspace context."""
    cwd = Path.cwd().resolve()
    config, metadata = _repo_from_cwd()
    click.echo(f"repo: {config.repo_id}")
    click.echo(f"integration: {config.integration}")
    click.echo(f"home: {config.home}")
    click.echo(f"cwd: {cwd}")

    try:
        work_root = resolve_work_root(config, cwd)
    except ValueError as exc:
        click.echo("work_root: -")
        click.echo("workspace: -")
        click.echo(f"context_error: {exc}")
        return
    click.echo(f"work_root: {work_root.id} {work_root.path}")

    try:
        workspace_context = _resolve_cli_workspace_context(config, cwd)
    except ValueError as exc:
        click.echo("workspace: -")
        click.echo("default_ref: -")
        click.echo(f"context_error: {exc}")
        return

    default_ref = workspace_context.default_branch
    head = metadata.get_branch_head(default_ref)
    click.echo(f"workspace: {workspace_context.workspace_id}")
    click.echo(f"user: {workspace_context.user}")
    click.echo(f"flow: {workspace_context.flow}")
    click.echo(f"workspace_path: {workspace_context.workspace_path}")
    click.echo(f"default_ref: {default_ref}")
    click.echo(f"head: {head or '-'}")

    if head is None:
        return

    version = metadata.get_version(head)
    if version is None:
        click.echo("head_record: missing")
        return
    click.echo(f"head_step: {version.step}")
    click.echo(f"head_state: [{version.review_state}/{version.retention_state}]")
    if version.message:
        click.echo(f"head_message: {version.message}")
    state_path = _workspace_state_path(workspace_context.workspace_path)
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise click.ClickException(
                f"Invalid workspace state marker: {state_path}"
            ) from exc
        if state.get("schema") == 1 and state.get("repo_id") == config.repo_id:
            click.echo(f"generation: {state.get('generation', 0)}")
            click.echo(f"restored_from: {state.get('restored_from', '-')}")
            click.echo(f"restore_journal: {state.get('restore_journal_id', '-')}")


@main.command("reset")
@click.argument("version")
@click.option("--message", "-m", default="", help="Reason for the branch pointer reset.")
def reset_cmd(version: str, message: str) -> None:
    """Move the current ref head only; does not rewrite workspace files."""
    config, metadata = _repo_from_cwd()
    branch = _current_workspace_branch(config)
    old_head = metadata.get_branch_head(branch)
    if old_head is None:
        raise click.ClickException(f"Current ref has no head version: {branch}")

    target = metadata.get_version(version)
    if target is None:
        raise click.ClickException(f"Version not found or ambiguous: {version}")

    if target.id == old_head:
        click.echo(f"branch: {branch}")
        click.echo(f"old_head: {old_head}")
        click.echo(f"new_head: {target.id}")
        click.echo("reset: no-op")
        click.echo("workspace_files: unchanged")
        return

    if not _is_ancestor_version(metadata, old_head, target.id):
        raise click.ClickException(
            "Target version is not an ancestor of the current ref head; "
            "cross-lineage reset is not supported in this prototype"
        )

    try:
        metadata.reset_branch_head(
            branch=branch,
            expected_old_head=old_head,
            new_head=target.id,
            actor=getpass.getuser(),
            created_at=_utc_now(),
            reason=message,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"branch: {branch}")
    click.echo(f"old_head: {old_head}")
    click.echo(f"new_head: {target.id}")
    click.echo("reset: moved")
    click.echo("workspace_files: unchanged")


@main.command("restore")
@click.argument("version")
@click.option(
    "--in-place",
    "in_place",
    is_flag=True,
    help="Required. Rewrite the current workspace in place.",
)
@click.option(
    "--plan",
    is_flag=True,
    help="Show the restore plan without changing files or metadata.",
)
@click.option(
    "--confirm",
    default="",
    help="Required as RESTORE when executing an in-place restore.",
)
@click.option(
    "--delete-missing",
    is_flag=True,
    help="Allow deletion of files present in the workspace but absent from the target version.",
)
def restore_cmd(
    version: str,
    in_place: bool,
    plan: bool,
    confirm: str,
    delete_missing: bool,
) -> None:
    """Explicitly restore the current workspace to an older version."""
    if not in_place:
        raise click.ClickException("restore requires explicit --in-place")

    config, metadata = _repo_from_cwd()
    try:
        workspace_context = _resolve_cli_workspace_context(config, Path.cwd())
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    branch = workspace_context.default_branch
    current_head = metadata.get_branch_head(branch)
    if current_head is None:
        raise click.ClickException(f"Current ref has no head version: {branch}")

    current = metadata.get_version(current_head)
    if current is None:
        raise click.ClickException(f"Current head record is missing: {current_head}")
    target = metadata.get_version(version)
    if target is None:
        raise click.ClickException(f"Version not found or ambiguous: {version}")
    if target.retention_state != "resident":
        raise click.ClickException(
            "In-place restore currently requires a resident target version"
        )
    if current_head != target.id and not _is_ancestor_version(
        metadata,
        head_version_id=current_head,
        target_version_id=target.id,
    ):
        raise click.ClickException(
            "In-place restore currently supports only the current head or an ancestor"
        )

    current_refs = _dedupe_checkout_refs(metadata.get_file_refs(current.id))
    target_refs = _dedupe_checkout_refs(metadata.get_file_refs(target.id))
    dirty = _dirty_refs(workspace_context.workspace_path, current_refs)
    if dirty:
        _print_dirty_summary(dirty)
        raise click.ClickException(
            "Workspace is dirty; commit, clean, or recreate the workspace before restore"
        )

    restore_plan = _restore_plan(
        workspace_path=workspace_context.workspace_path,
        current_refs=current_refs,
        target_refs=target_refs,
    )
    generation_current = _read_workspace_generation(
        workspace_context.workspace_path,
        config.repo_id,
    )
    generation_next = generation_current + 1

    if plan:
        _print_restore_plan(
            branch_name=branch,
            current_head=current_head,
            target_version=target.id,
            workspace_context=workspace_context,
            generation_current=generation_current,
            generation_next=generation_next,
            plan=restore_plan,
            delete_missing=delete_missing,
            materialization="plan-only",
        )
        return

    if int(restore_plan["delete"]) and not delete_missing:
        _print_restore_plan(
            branch_name=branch,
            current_head=current_head,
            target_version=target.id,
            workspace_context=workspace_context,
            generation_current=generation_current,
            generation_next=generation_next,
            plan=restore_plan,
            delete_missing=delete_missing,
            materialization="blocked",
        )
        raise click.ClickException(
            "Restore would delete files; rerun with --delete-missing after reviewing the plan"
        )
    if confirm != "RESTORE":
        _print_restore_plan(
            branch_name=branch,
            current_head=current_head,
            target_version=target.id,
            workspace_context=workspace_context,
            generation_current=generation_current,
            generation_next=generation_next,
            plan=restore_plan,
            delete_missing=delete_missing,
            materialization="confirmation-required",
        )
        raise click.ClickException("In-place restore requires --confirm RESTORE")

    missing, size_mismatch, hash_mismatch = _verify_file_refs(
        config.cas_dir,
        [(target.id, ref) for ref in target_refs],
    )
    if missing or size_mismatch or hash_mismatch:
        _print_integrity_failures(
            missing,
            size_mismatch,
            hash_mismatch,
            include_version=True,
        )
        raise click.ClickException("Target version CAS integrity verification failed")

    latest_head = metadata.get_branch_head(branch)
    if latest_head != current_head:
        raise click.ClickException(f"Branch head changed before restore: {branch}")

    actor = getpass.getuser()
    started_at = _utc_now()
    journal_id = "r" + uuid.uuid4().hex[:12]
    target_by_path = {ref.path: ref for ref in target_refs}
    operations: list[dict[str, object]] = []
    for op, paths in (
        ("add", restore_plan["add_paths"]),
        ("overwrite", restore_plan["overwrite_paths"]),
        ("delete", restore_plan["delete_paths"]),
    ):
        for rel_path in paths:
            ref = target_by_path.get(str(rel_path))
            operations.append(
                {
                    "op": op,
                    "path": rel_path,
                    "status": "pending",
                    "bytes": 0 if ref is None else ref.size,
                    "cas_hash": "" if ref is None else ref.cas_hash,
                }
            )
    journal: dict[str, object] = {
        "schema": 1,
        "journal_id": journal_id,
        "repo_id": config.repo_id,
        "branch": branch,
        "old_head_version_id": current_head,
        "target_version_id": target.id,
        "workspace_id": workspace_context.workspace_id,
        "workspace_path": str(workspace_context.workspace_path),
        "generation": generation_next,
        "actor": actor,
        "started_at": started_at,
        "finished_at": "",
        "status": "running",
        "plan": {
            "add": restore_plan["add"],
            "overwrite": restore_plan["overwrite"],
            "delete": restore_plan["delete"],
            "keep": restore_plan["keep"],
            "changed_files": restore_plan["changed_files"],
            "bytes": restore_plan["bytes"],
            "delete_missing": delete_missing,
        },
        "operations": operations,
    }
    _write_restore_journal(config, journal)

    try:
        for index, operation in enumerate(operations):
            operation["status"] = "running"
            _write_restore_journal(config, journal)
            op = str(operation["op"])
            rel_path = str(operation["path"])
            if op in {"add", "overwrite"}:
                _restore_ref_from_cas(
                    cas_root=config.cas_dir,
                    workspace_path=workspace_context.workspace_path,
                    ref=target_by_path[rel_path],
                )
            elif op == "delete":
                _delete_restore_path(workspace_context.workspace_path, rel_path)
            operations[index]["status"] = "done"
            _write_restore_journal(config, journal)
    except Exception as exc:
        journal["status"] = "failed"
        journal["finished_at"] = _utc_now()
        journal["error"] = str(exc)
        _write_restore_journal(config, journal)
        raise

    finished_at = _utc_now()
    journal["status"] = "completed"
    journal["finished_at"] = finished_at
    _write_restore_journal(config, journal)

    audit_plan = {
        "add": restore_plan["add"],
        "overwrite": restore_plan["overwrite"],
        "delete": restore_plan["delete"],
        "keep": restore_plan["keep"],
        "changed_files": restore_plan["changed_files"],
        "bytes": restore_plan["bytes"],
        "delete_missing": delete_missing,
    }
    try:
        metadata.record_restore(
            branch=branch,
            expected_old_head=current_head,
            new_head=target.id,
            journal_id=journal_id,
            workspace_id=workspace_context.workspace_id,
            workspace_path=str(workspace_context.workspace_path),
            generation=generation_next,
            actor=actor,
            created_at=finished_at,
            plan=audit_plan,
        )
    except ValueError as exc:
        journal["status"] = "metadata_failed"
        journal["error"] = str(exc)
        _write_restore_journal(config, journal)
        raise click.ClickException(str(exc)) from exc

    _write_workspace_state(
        workspace_path=workspace_context.workspace_path,
        repo_id=config.repo_id,
        branch_name=branch,
        workspace_id=workspace_context.workspace_id,
        generation=generation_next,
        restored_from=target.id,
        journal_id=journal_id,
        actor=actor,
        restored_at=finished_at,
    )
    _print_restore_plan(
        branch_name=branch,
        current_head=current_head,
        target_version=target.id,
        workspace_context=workspace_context,
        generation_current=generation_current,
        generation_next=generation_next,
        plan=restore_plan,
        delete_missing=delete_missing,
        materialization="restored",
        journal_id=journal_id,
    )
    click.echo("restore: completed")
    click.echo(
        "branch_head: "
        + ("unchanged" if current_head == target.id else f"{current_head}->{target.id}")
    )
    click.echo("note: reopen files or restart EDA tools that may cache old content")


@main.command("promote")
@click.argument("version")
@click.option(
    "--to",
    "target_state",
    required=True,
    type=click.Choice(REVIEW_STATES, case_sensitive=False),
    help="Target review state.",
)
@click.option(
    "--message",
    "-m",
    default="",
    help="Reason for the lifecycle transition.",
)
@click.option(
    "--confirm",
    default="",
    help="Required as GOLDEN when promoting to Golden.",
)
def promote_cmd(version: str, target_state: str, message: str, confirm: str) -> None:
    """Promote a version's review state without changing file residency."""
    _, metadata = _repo_from_cwd()
    record = metadata.get_version(version)
    if record is None:
        raise click.ClickException(f"Version not found or ambiguous: {version}")

    target_state = _canonical_review_state(target_state)
    current_rank = REVIEW_STATE_ORDER[record.review_state]
    target_rank = REVIEW_STATE_ORDER[target_state]
    if target_rank < current_rank:
        raise click.ClickException(
            "Review state demotion is not supported in this prototype"
        )

    if target_state == record.review_state:
        click.echo(f"version: {record.id}")
        click.echo(f"old_state: [{record.review_state}/{record.retention_state}]")
        click.echo(f"new_state: [{record.review_state}/{record.retention_state}]")
        click.echo("promote: no-op")
        click.echo("retention: unchanged")
        return

    if target_state == "Golden" and confirm != "GOLDEN":
        raise click.ClickException("Promoting to Golden requires --confirm GOLDEN")

    try:
        metadata.update_review_state(
            version_id=record.id,
            expected_old_review_state=record.review_state,
            new_review_state=target_state,
            actor=getpass.getuser(),
            created_at=_utc_now(),
            reason=message,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"version: {record.id}")
    click.echo(f"old_state: [{record.review_state}/{record.retention_state}]")
    click.echo(f"new_state: [{target_state}/{record.retention_state}]")
    click.echo("promote: moved")
    click.echo("retention: unchanged")
    if target_state == "Candidate":
        click.echo("candidate_outbox: not-implemented")


@lifecycle.command("degrade")
@click.argument("version")
@click.option(
    "--to",
    "target_retention",
    required=True,
    type=click.Choice(["recipe_only"], case_sensitive=False),
    help="Target retention state. The prototype only supports recipe_only.",
)
@click.option(
    "--message",
    "-m",
    default="",
    help="Reason for the retention transition.",
)
@click.option(
    "--confirm",
    default="",
    help="Required as RECIPE_ONLY when degrading to recipe_only.",
)
def lifecycle_degrade_cmd(
    version: str,
    target_retention: str,
    message: str,
    confirm: str,
) -> None:
    """Mark an Exploring version as recipe_only without deleting CAS objects."""
    _, metadata = _repo_from_cwd()
    record = metadata.get_version(version)
    if record is None:
        raise click.ClickException(f"Version not found or ambiguous: {version}")

    target_retention = _canonical_retention_state(target_retention)
    if target_retention != "recipe_only":
        raise click.ClickException("Only recipe_only degradation is supported")
    if record.review_state != "Exploring":
        raise click.ClickException(
            "Only Exploring versions can be degraded to recipe_only in this prototype"
        )
    if record.retention_state == "recipe_only":
        click.echo(f"version: {record.id}")
        click.echo(f"old_state: [{record.review_state}/{record.retention_state}]")
        click.echo(f"new_state: [{record.review_state}/{record.retention_state}]")
        click.echo("degrade: no-op")
        click.echo("physical_gc: not-implemented")
        return
    if record.retention_state != "resident":
        raise click.ClickException(
            "Only resident versions can be degraded to recipe_only in this prototype"
        )
    if confirm != "RECIPE_ONLY":
        raise click.ClickException(
            "Degrading to recipe_only requires --confirm RECIPE_ONLY"
        )

    try:
        metadata.update_retention_state(
            version_id=record.id,
            expected_old_retention_state=record.retention_state,
            new_retention_state=target_retention,
            actor=getpass.getuser(),
            created_at=_utc_now(),
            reason=message,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"version: {record.id}")
    click.echo(f"old_state: [{record.review_state}/{record.retention_state}]")
    click.echo(f"new_state: [{record.review_state}/{target_retention}]")
    click.echo("degrade: moved")
    click.echo("physical_gc: not-implemented")


@lifecycle.command("events")
@click.argument("version")
@click.option("--limit", default=20, show_default=True, type=click.IntRange(min=1))
def lifecycle_events_cmd(version: str, limit: int) -> None:
    """Show lifecycle transition events for a version."""
    _, metadata = _repo_from_cwd()
    record = metadata.get_version(version)
    if record is None:
        raise click.ClickException(f"Version not found or ambiguous: {version}")

    events = metadata.list_lifecycle_events(record.id, limit=limit)
    if not events:
        click.echo(f"No lifecycle events for {record.id}.")
        return

    for item in events:
        reason = item.reason or "-"
        click.echo(
            f"{item.id} {item.version_id} "
            f"{item.old_review_state}->{item.new_review_state} "
            f"{item.old_retention_state}->{item.new_retention_state} "
            f"{item.actor} {item.created_at} {reason}"
        )


@audit.command("log")
@click.option("--limit", default=20, show_default=True, type=click.IntRange(min=1))
@click.option("--full", "show_full", is_flag=True, help="Show audit payload JSON.")
def audit_log_cmd(limit: int, show_full: bool) -> None:
    """Show recent audit hash-chain events."""
    _, metadata = _repo_from_cwd()
    events = metadata.list_audit_events(limit=limit)
    if not events:
        click.echo("No audit events.")
        return

    for item in events:
        previous = _short_hash(item.previous_hash) if item.previous_hash else "-"
        click.echo(
            f"{item.id} {item.action} {item.entity_type} {item.entity_id} "
            f"{item.actor} {item.created_at} "
            f"hash={_short_hash(item.event_hash)} prev={previous}"
        )
        if show_full:
            click.echo(f"  payload: {item.payload_json}")


@audit.command("verify")
@click.option("--full", "show_full", is_flag=True, help="Show every broken event.")
def audit_verify_cmd(show_full: bool) -> None:
    """Verify the audit hash chain."""
    _, metadata = _repo_from_cwd()
    total, issues = metadata.verify_audit_chain()
    click.echo(f"events: {total}")
    click.echo(f"broken: {len(issues)}")
    click.echo(f"integrity: {'ok' if not issues else 'failed'}")

    if show_full and issues:
        for item in issues:
            click.echo(f"broken {item.event_id}: {item.issue}")

    if issues:
        raise click.ClickException("Audit hash-chain verification failed")


@branch.command("create")
@click.argument("branch_name")
@click.option(
    "--from",
    "source_ref",
    default=None,
    help="Source branch/ref or version. Defaults to current workspace ref.",
)
def branch_create_cmd(branch_name: str, source_ref: str | None) -> None:
    """Create a named branch from a source ref."""
    _validate_branch_name(branch_name)
    config, metadata = _repo_from_cwd()
    if metadata.get_branch(branch_name) is not None:
        raise click.ClickException(f"Branch already exists: {branch_name}")

    source_ref = source_ref or _current_workspace_branch(config)
    resolved_source, source_version_id = _resolve_source_ref(metadata, source_ref)
    created_at = _utc_now()
    try:
        metadata.create_branch(
            name=branch_name,
            head_version_id=source_version_id,
            kind="named",
            created_at=created_at,
            source_ref=resolved_source,
            source_version_id=source_version_id,
            owner=getpass.getuser(),
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"branch: {branch_name}")
    click.echo(f"head: {source_version_id}")
    click.echo(f"source_ref: {resolved_source}")
    click.echo(f"kind: named")


@branch.command("list")
@click.option(
    "--all",
    "include_workspace",
    is_flag=True,
    help="Include workspace-private refs.",
)
def branch_list_cmd(include_workspace: bool) -> None:
    """List branches and refs."""
    _, metadata = _repo_from_cwd()
    branches = metadata.list_branches(include_workspace=include_workspace)
    if not branches:
        click.echo("No branches found.")
        return
    for item in branches:
        head = item.head_version_id or "-"
        owner = item.owner or "-"
        source = item.source_ref or "-"
        click.echo(f"{item.kind} {item.name} {head} {owner} {source}")


@branch.command("events")
@click.argument("branch_name", required=False)
@click.option("--limit", default=20, show_default=True, type=click.IntRange(min=1))
def branch_events_cmd(branch_name: str | None, limit: int) -> None:
    """Show branch audit events."""
    config, metadata = _repo_from_cwd()
    branch_name = branch_name or _current_workspace_branch(config)
    if metadata.get_branch(branch_name) is None:
        raise click.ClickException(f"Branch/ref not found: {branch_name}")

    events = metadata.list_branch_events(branch_name, limit=limit)
    if not events:
        click.echo(f"No branch events on {branch_name}.")
        return

    for item in events:
        reason = item.reason or "-"
        click.echo(
            f"{item.id} {item.event_type} {item.branch} "
            f"{item.old_head_version_id}->{item.new_head_version_id} "
            f"{item.actor} {item.created_at} {reason}"
        )


@branch.command("show")
@click.argument("branch_name")
def branch_show_cmd(branch_name: str) -> None:
    """Show branch/ref metadata."""
    _, metadata = _repo_from_cwd()
    record = metadata.get_branch(branch_name)
    if record is None:
        raise click.ClickException(f"Branch/ref not found: {branch_name}")

    head = record.head_version_id or "-"
    click.echo(f"branch: {record.name}")
    click.echo(f"kind: {record.kind}")
    click.echo(f"head: {head}")
    click.echo(f"owner: {record.owner or '-'}")
    click.echo(f"created_at: {record.created_at or '-'}")
    click.echo(f"source_ref: {record.source_ref or '-'}")
    click.echo(f"source_version: {record.source_version_id or '-'}")

    if record.head_version_id is None:
        return

    version = metadata.get_version(record.head_version_id)
    if version is None:
        click.echo("head_record: missing")
        return

    click.echo(f"head_step: {version.step}")
    click.echo(f"head_workspace: {version.workspace_id or '-'}")
    click.echo(f"head_state: [{version.review_state}/{version.retention_state}]")
    if version.message:
        click.echo(f"head_message: {version.message}")


@main.command("commit")
@click.option("--step", required=True, help="EDA step name, for example place.")
@click.option(
    "--inputs",
    "input_patterns",
    multiple=True,
    required=True,
    help="Input glob patterns. Repeat the option or separate patterns with semicolons.",
)
@click.option(
    "--outputs",
    "output_patterns",
    multiple=True,
    required=True,
    help="Output glob patterns. Repeat the option or separate patterns with semicolons.",
)
@click.option("--message", "-m", default="", help="Commit message.")
@click.option(
    "--branch",
    default=None,
    help="Explicit branch/ref. Defaults to the current workspace-private ref.",
)
@click.option("--verbose", is_flag=True, help="Show manifest summary details.")
def commit_cmd(
    step: str,
    input_patterns: tuple[str, ...],
    output_patterns: tuple[str, ...],
    message: str,
    branch: str,
    verbose: bool,
) -> None:
    """Capture inputs/outputs into CAS and create a version manifest."""
    workspace = Path.cwd().resolve()
    config, metadata = _repo_from_cwd()
    try:
        workspace_context = _resolve_cli_workspace_context(config, workspace)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    branch = branch or workspace_context.default_branch
    inputs = _resolve_patterns(input_patterns, workspace, "input")
    outputs = _resolve_patterns(output_patterns, workspace, "output")

    capture_id = uuid.uuid4().hex
    staging_root = config.staging_dir / capture_id
    all_refs = (
        _capture_files("input", inputs, workspace, staging_root, config.cas_dir)
        + _capture_files("output", outputs, workspace, staging_root, config.cas_dir)
    )
    input_refs = [item for item in all_refs if item.role == "input"]

    recipe_hash = _json_hash(
        {
            "schema": 1,
            "step": step,
            "inputs": [
                {"path": item.path, "hash": item.cas_hash}
                for item in sorted(input_refs, key=lambda x: x.path)
            ],
        }
    )
    manifest_hash = _json_hash(
        {
            "schema": 1,
            "repo_id": config.repo_id,
            "branch": branch,
            "workspace_id": workspace_context.workspace_id,
            "step": step,
            "files": [asdict(item) for item in sorted(all_refs, key=lambda x: (x.role, x.path))],
        }
    )
    version_id = "v" + _short_hash(
        _json_hash({"manifest": manifest_hash, "nonce": capture_id})
    )
    parent_id = metadata.get_branch_head(branch)
    record = VersionRecord(
        id=version_id,
        branch=branch,
        parent_id=parent_id,
        step=step,
        message=message,
        author=getpass.getuser(),
        created_at=_utc_now(),
        recipe_hash=recipe_hash,
        manifest_hash=manifest_hash,
        capture_mode="best_effort",
        review_state="Exploring",
        retention_state="resident",
        work_root_id=workspace_context.work_root.id,
        workspace_id=workspace_context.workspace_id,
        user_name=workspace_context.user,
        flow=workspace_context.flow,
    )
    metadata.create_version(record, all_refs)
    shutil.rmtree(staging_root, ignore_errors=True)

    click.echo(f"version: {record.id}")
    click.echo(f"branch: {branch}")
    click.echo(f"workspace: {workspace_context.workspace_id}")
    click.echo(f"step: {step}")
    click.echo(f"inputs: {len(inputs)}")
    click.echo(f"outputs: {len(outputs)}")
    click.echo(f"recipe_hash: {_short_hash(recipe_hash)}")
    click.echo(f"capture_mode: {record.capture_mode}")
    click.echo(f"state: [{record.review_state}/{record.retention_state}]")
    if verbose:
        click.echo(
            f"work_root: {workspace_context.work_root.id} "
            f"{workspace_context.work_root.path}"
        )
        click.echo(f"manifest_hash: {manifest_hash}")


@main.command("log")
@click.argument("branch", required=False)
@click.option("--limit", default=20, show_default=True, type=click.IntRange(min=1))
@click.option("--verbose", is_flag=True)
def log_cmd(branch: str | None, limit: int, verbose: bool) -> None:
    """Show version history for a branch."""
    config, metadata = _repo_from_cwd()
    if branch is None:
        try:
            workspace_context = _resolve_cli_workspace_context(config, Path.cwd())
        except ValueError as exc:
            raise click.ClickException(
                f"{exc}; pass an explicit branch/ref to log"
            ) from exc
        branch = workspace_context.default_branch

    versions = metadata.list_versions(branch, limit=limit)
    if not versions:
        click.echo(f"No versions visible on branch {branch}.")
        return
    for item in versions:
        click.echo(
            f"{item.id} [{item.review_state}/{item.retention_state}] "
            f"{item.branch} {item.step} {item.created_at} {item.message}"
        )
        if verbose:
            click.echo(f"  parent: {item.parent_id or '-'}")
            click.echo(f"  workspace: {item.workspace_id or '-'}")
            click.echo(f"  recipe_hash: {_short_hash(item.recipe_hash)}")
            click.echo(f"  capture_mode: {item.capture_mode}")


@main.command("show")
@click.argument("version")
@click.option("--verbose", is_flag=True)
@click.option("--full", "show_full", is_flag=True)
def show_cmd(version: str, verbose: bool, show_full: bool) -> None:
    """Show a version manifest summary."""
    _, metadata = _repo_from_cwd()
    record = metadata.get_version(version)
    if record is None:
        raise click.ClickException(f"Version not found or ambiguous: {version}")
    refs = metadata.get_file_refs(record.id)
    inputs = [item for item in refs if item.role == "input"]
    outputs = [item for item in refs if item.role == "output"]
    total_size = sum(item.size for item in refs)

    click.echo(f"version: {record.id}")
    click.echo(f"branch: {record.branch}")
    click.echo(f"parent: {record.parent_id or '-'}")
    click.echo(f"step: {record.step}")
    click.echo(f"author: {record.author}")
    click.echo(f"created_at: {record.created_at}")
    if record.workspace_id:
        click.echo(f"workspace: {record.workspace_id}")
    click.echo(f"state: [{record.review_state}/{record.retention_state}]")
    click.echo(f"inputs: {len(inputs)}")
    click.echo(f"outputs: {len(outputs)}")
    click.echo(f"bytes: {total_size}")
    click.echo(f"recipe_hash: {_short_hash(record.recipe_hash)}")
    click.echo(f"manifest_hash: {_short_hash(record.manifest_hash)}")
    click.echo(f"capture_mode: {record.capture_mode}")

    if verbose or show_full:
        by_role = {"input": inputs, "output": outputs}
        for role, items in by_role.items():
            click.echo(f"{role}s:")
            visible = items if show_full else items[:10]
            for ref in visible:
                click.echo(
                    f"  {ref.path} {ref.size} {_short_hash(ref.cas_hash)} "
                    f"{ref.semantic_role}/{ref.format_hint}"
                )
            if not show_full and len(items) > len(visible):
                click.echo(f"  ... {len(items) - len(visible)} more; use --full")


@main.command("lineage")
@click.argument("version")
@click.option("--limit", default=20, show_default=True, type=click.IntRange(min=1))
def lineage_cmd(version: str, limit: int) -> None:
    """Show a version's parent chain."""
    _, metadata = _repo_from_cwd()
    record = metadata.get_version(version)
    if record is None:
        raise click.ClickException(f"Version not found or ambiguous: {version}")

    chain: list[VersionRecord] = []
    current_id: str | None = record.id
    visited: set[str] = set()
    truncated = False
    missing_parent: str | None = None
    cycle_at: str | None = None

    while current_id is not None:
        if current_id in visited:
            cycle_at = current_id
            break
        if len(chain) >= limit:
            truncated = True
            break
        current = metadata.get_version(current_id)
        if current is None:
            missing_parent = current_id
            break
        chain.append(current)
        visited.add(current_id)
        current_id = current.parent_id

    click.echo(f"version: {record.id}")
    click.echo(f"entries: {len(chain)}")
    click.echo(f"truncated: {'yes' if truncated else 'no'}")
    if missing_parent is not None:
        click.echo(f"missing_parent: {missing_parent}")
    if cycle_at is not None:
        click.echo(f"cycle_at: {cycle_at}")
    click.echo("parent_chain:")
    for depth, item in enumerate(chain):
        click.echo(
            f"  {depth} {item.id} parent={item.parent_id or '-'} "
            f"branch={item.branch} step={item.step} "
            f"state=[{item.review_state}/{item.retention_state}]"
        )
        if item.workspace_id:
            click.echo(f"    workspace: {item.workspace_id}")
        if item.message:
            click.echo(f"    message: {item.message}")


@main.command("verify")
@click.argument("version")
@click.option("--full", "show_full", is_flag=True, help="Show every failed FileRef.")
def verify_cmd(version: str, show_full: bool) -> None:
    """Verify that a version's referenced CAS objects are present and intact."""
    config, metadata = _repo_from_cwd()
    record = metadata.get_version(version)
    if record is None:
        raise click.ClickException(f"Version not found or ambiguous: {version}")

    refs = metadata.get_file_refs(record.id)
    missing, size_mismatch, hash_mismatch = _verify_file_refs(
        config.cas_dir,
        [(record.id, ref) for ref in refs],
    )
    failures = len(missing) + len(size_mismatch) + len(hash_mismatch)
    click.echo(f"version: {record.id}")
    click.echo(f"files: {len(refs)}")
    click.echo(f"missing: {len(missing)}")
    click.echo(f"size_mismatch: {len(size_mismatch)}")
    click.echo(f"hash_mismatch: {len(hash_mismatch)}")
    click.echo(f"integrity: {'ok' if failures == 0 else 'failed'}")

    if show_full and failures:
        _print_integrity_failures(
            missing,
            size_mismatch,
            hash_mismatch,
            include_version=False,
        )

    if failures:
        raise click.ClickException("CAS integrity verification failed")


@main.command("diff")
@click.argument("old_version")
@click.argument("new_version")
@click.option("--verbose", is_flag=True)
@click.option("--full", "show_full", is_flag=True)
def diff_cmd(old_version: str, new_version: str, verbose: bool, show_full: bool) -> None:
    """Compare two version manifests."""
    _, metadata = _repo_from_cwd()
    old = metadata.get_version(old_version)
    new = metadata.get_version(new_version)
    if old is None:
        raise click.ClickException(f"Version not found or ambiguous: {old_version}")
    if new is None:
        raise click.ClickException(f"Version not found or ambiguous: {new_version}")

    old_refs = {(ref.role, ref.path): ref for ref in metadata.get_file_refs(old.id)}
    new_refs = {(ref.role, ref.path): ref for ref in metadata.get_file_refs(new.id)}
    added = sorted(set(new_refs) - set(old_refs))
    removed = sorted(set(old_refs) - set(new_refs))
    modified = sorted(
        key
        for key in set(old_refs) & set(new_refs)
        if old_refs[key].cas_hash != new_refs[key].cas_hash
    )

    recipe_status = "unchanged" if old.recipe_hash == new.recipe_hash else "changed"
    click.echo(f"--- {old.id} {old.branch}")
    click.echo(f"+++ {new.id} {new.branch}")
    click.echo(f"recipe_hash: {recipe_status}")
    click.echo(f"added: {len(added)}")
    click.echo(f"removed: {len(removed)}")
    click.echo(f"modified: {len(modified)}")

    if verbose or show_full:
        limit = None if show_full else 20
        _print_diff_entries("+", added, new_refs, limit)
        _print_diff_entries("-", removed, old_refs, limit)
        _print_modified_entries(modified, old_refs, new_refs, limit)


def _print_diff_entries(
    prefix: str,
    keys: list[tuple[str, str]],
    refs: dict[tuple[str, str], FileRef],
    limit: int | None,
) -> None:
    visible = keys if limit is None else keys[:limit]
    for key in visible:
        ref = refs[key]
        click.echo(f"{prefix} {ref.role} {ref.path} {_short_hash(ref.cas_hash)} {ref.size}")
    if limit is not None and len(keys) > limit:
        click.echo(f"... {len(keys) - limit} more; use --full")


def _print_modified_entries(
    keys: list[tuple[str, str]],
    old_refs: dict[tuple[str, str], FileRef],
    new_refs: dict[tuple[str, str], FileRef],
    limit: int | None,
) -> None:
    visible = keys if limit is None else keys[:limit]
    for key in visible:
        old = old_refs[key]
        new = new_refs[key]
        click.echo(
            f"~ {new.role} {new.path} "
            f"{_short_hash(old.cas_hash)}->{_short_hash(new.cas_hash)} "
            f"{old.size}->{new.size}"
        )
    if limit is not None and len(keys) > limit:
        click.echo(f"... {len(keys) - limit} more; use --full")
