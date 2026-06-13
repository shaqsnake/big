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

from .cas import publish_object, stable_copy_to_staging, UnstableFileError
from .config import (
    CONFIG_NAME,
    ensure_repo_dirs,
    find_config,
    resolve_work_root,
    resolve_workspace_context,
    write_main_config,
)
from .metadata import FileRef, SQLiteMetadataRepository, VersionRecord


BRANCH_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


def _repo_from_cwd() -> tuple[object, SQLiteMetadataRepository]:
    try:
        config, _ = find_config(Path.cwd())
    except FileNotFoundError as exc:
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
        return resolve_workspace_context(config, Path.cwd()).default_branch
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


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


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def main() -> None:
    """BIG prototype CLI for EDA artifact snapshots."""


@main.group()
def repo() -> None:
    """Repository administration commands."""


@main.group()
def branch() -> None:
    """Branch metadata commands."""


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
def repo_init(path: Path, repo_id: str, integration: str) -> None:
    """Initialize a prototype BIG repository."""
    root = path.resolve()
    root.mkdir(parents=True, exist_ok=True)
    config_path = root / CONFIG_NAME
    if config_path.exists():
        click.echo(f"BIG repo already initialized: {config_path}")
    else:
        write_main_config(root, repo_id=repo_id, integration=integration)
        click.echo(f"created {config_path}")

    config, _ = find_config(root)
    ensure_repo_dirs(config)
    SQLiteMetadataRepository(config.metadata_db).init_schema()
    click.echo(f"repo: {config.repo_id}")
    click.echo(f"home: {config.home}")
    click.echo(f"metadata: {config.metadata_db}")


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
        workspace_context = resolve_workspace_context(config, cwd)
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
        workspace_context = resolve_workspace_context(config, workspace)
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
            workspace_context = resolve_workspace_context(config, Path.cwd())
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
