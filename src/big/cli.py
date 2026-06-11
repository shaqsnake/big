from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import getpass
import glob
import hashlib
import json
from pathlib import Path
import shutil
import uuid

import click

from .cas import publish_object, stable_copy_to_staging, UnstableFileError
from .config import (
    CONFIG_NAME,
    ensure_repo_dirs,
    find_config,
    resolve_workspace_context,
    write_main_config,
)
from .metadata import FileRef, SQLiteMetadataRepository, VersionRecord


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


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def main() -> None:
    """BIG prototype CLI for EDA artifact snapshots."""


@main.group()
def repo() -> None:
    """Repository administration commands."""


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
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
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
