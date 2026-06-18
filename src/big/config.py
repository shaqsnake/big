from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


CONFIG_NAME = "big.toml"


@dataclass(frozen=True)
class WorkRoot:
    id: str
    path: Path
    role: str = "default"


@dataclass(frozen=True)
class AclTemplate:
    name: str
    owner_group: str
    read_groups: tuple[str, ...] = ()
    write_groups: tuple[str, ...] = ()


@dataclass(frozen=True)
class RepoConfig:
    repo_id: str
    integration: str
    home: Path
    work_roots: tuple[WorkRoot, ...]
    admin_groups: tuple[str, ...] = ()
    acl_templates: tuple[AclTemplate, ...] = ()
    acl_validate_groups: bool = False
    step_success_marker: str = ""
    capture_settle_ms: int = 0

    @property
    def big_dir(self) -> Path:
        return self.home / ".big"

    @property
    def metadata_db(self) -> Path:
        return self.big_dir / "metadata" / "big.sqlite3"

    @property
    def cas_dir(self) -> Path:
        return self.big_dir / "cas" / "objects"

    @property
    def staging_dir(self) -> Path:
        return self.big_dir / "staging"


@dataclass(frozen=True)
class WorkspaceContext:
    work_root: WorkRoot
    user: str
    flow: str
    workspace_path: Path
    workspace_id: str
    default_branch: str


def _posix(path: Path) -> str:
    return path.resolve().as_posix()


def write_main_config(
    root: Path,
    repo_id: str,
    integration: str = "2d",
    work_roots: tuple[WorkRoot, ...] | None = None,
) -> Path:
    config_path = root / CONFIG_NAME
    work_roots = work_roots or (WorkRoot(id="default", path=root),)
    text = (
        "[repo]\n"
        f"id = \"{repo_id}\"\n"
        f"integration = \"{integration}\"\n"
        f"home = \"{_posix(root)}\"\n"
    )
    for item in work_roots:
        text += (
            "\n"
            "[[work_roots]]\n"
            f"id = \"{item.id}\"\n"
            f"role = \"{item.role}\"\n"
            f"path = \"{_posix(item.path)}\"\n"
        )
    config_path.write_text(text, encoding="utf-8")
    return config_path


def write_pointer_config(
    root: Path,
    repo_id: str,
    integration: str,
    home: Path,
    work_root_id: str,
) -> Path:
    config_path = root / CONFIG_NAME
    text = (
        "[repo]\n"
        f"id = \"{repo_id}\"\n"
        f"integration = \"{integration}\"\n"
        f"home = \"{_posix(home)}\"\n"
        f"work_root_id = \"{work_root_id}\"\n"
    )
    config_path.write_text(text, encoding="utf-8")
    return config_path


def _string_tuple(values: object, field_name: str) -> tuple[str, ...]:
    if values is None:
        return ()
    if not isinstance(values, list):
        raise ValueError(f"ACL template {field_name} must be a list")
    return tuple(str(item).strip() for item in values if str(item).strip())


def _load_acl_templates(data: dict[str, object]) -> tuple[AclTemplate, ...]:
    raw_templates = data.get("acl_templates", [])
    if raw_templates is None:
        return ()
    if not isinstance(raw_templates, list):
        raise ValueError("acl_templates must be declared with [[acl_templates]]")

    templates: list[AclTemplate] = []
    seen: set[str] = set()
    for raw in raw_templates:
        if not isinstance(raw, dict):
            raise ValueError("ACL template entry must be a table")
        name = str(raw.get("name", "")).strip()
        if not name or any(item.isspace() for item in name):
            raise ValueError("ACL template name must be non-empty without spaces")
        if name in seen:
            raise ValueError(f"Duplicate ACL template: {name}")
        owner_group = str(raw.get("owner_group", "")).strip()
        if not owner_group:
            raise ValueError(f"ACL template {name} requires owner_group")
        templates.append(
            AclTemplate(
                name=name,
                owner_group=owner_group,
                read_groups=_string_tuple(raw.get("read_groups", []), "read_groups"),
                write_groups=_string_tuple(
                    raw.get("write_groups", []),
                    "write_groups",
                ),
            )
        )
        seen.add(name)
    return tuple(templates)


def _load_acl_validate_groups(data: dict[str, object]) -> bool:
    raw_acl = data.get("acl", {})
    if raw_acl is None:
        return False
    if not isinstance(raw_acl, dict):
        raise ValueError("acl must be declared with [acl]")
    value = raw_acl.get("validate_groups", False)
    if not isinstance(value, bool):
        raise ValueError("acl.validate_groups must be true or false")
    return value


def _load_admin_groups(data: dict[str, object]) -> tuple[str, ...]:
    raw_admin = data.get("admin", {})
    if raw_admin is None:
        return ()
    if not isinstance(raw_admin, dict):
        raise ValueError("admin must be declared with [admin]")
    groups = raw_admin.get("groups", [])
    if groups is None:
        return ()
    if not isinstance(groups, list):
        raise ValueError("admin.groups must be a list")
    return tuple(str(item).strip() for item in groups if str(item).strip())


def _load_step_success_marker(data: dict[str, object]) -> str:
    raw_markers = data.get("step_markers", {})
    if raw_markers is None:
        return ""
    if not isinstance(raw_markers, dict):
        raise ValueError("step_markers must be declared with [step_markers]")
    return str(raw_markers.get("success", "")).strip()


def _load_capture_settle_ms(data: dict[str, object]) -> int:
    raw_capture = data.get("capture", {})
    if raw_capture is None:
        return 0
    if not isinstance(raw_capture, dict):
        raise ValueError("capture must be declared with [capture]")
    value = raw_capture.get("settle_ms", 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("capture.settle_ms must be a non-negative integer")
    return value


def load_config(config_path: Path) -> RepoConfig:
    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    repo = data["repo"]
    home = Path(repo["home"]).resolve()
    if "work_root_id" in repo and not data.get("work_roots"):
        main_config_path = home / CONFIG_NAME
        if main_config_path.resolve() == config_path.resolve():
            raise ValueError(f"Pointer config cannot point to itself: {config_path}")
        config = load_config(main_config_path)
        if config.repo_id != str(repo["id"]):
            raise ValueError(f"Pointer repo id mismatch: {config_path}")
        if config.integration != str(repo.get("integration", config.integration)):
            raise ValueError(f"Pointer integration mismatch: {config_path}")
        work_root_id = str(repo["work_root_id"])
        if work_root_id not in {item.id for item in config.work_roots}:
            raise ValueError(f"Pointer work root not registered: {work_root_id}")
        return config

    work_roots = tuple(
        WorkRoot(
            id=str(item["id"]),
            role=str(item.get("role", item["id"])),
            path=Path(item["path"]).resolve(),
        )
        for item in data.get("work_roots", [])
    )
    if not work_roots:
        work_roots = (WorkRoot(id="default", path=home),)
    return RepoConfig(
        repo_id=str(repo["id"]),
        integration=str(repo.get("integration", "2d")),
        home=home,
        work_roots=work_roots,
        admin_groups=_load_admin_groups(data),
        acl_templates=_load_acl_templates(data),
        acl_validate_groups=_load_acl_validate_groups(data),
        step_success_marker=_load_step_success_marker(data),
        capture_settle_ms=_load_capture_settle_ms(data),
    )


def find_config(start: Path) -> tuple[RepoConfig, Path]:
    current = start.resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        config_path = candidate / CONFIG_NAME
        if config_path.exists():
            return load_config(config_path), config_path
    raise FileNotFoundError(f"No {CONFIG_NAME} found from {start}")


def ensure_repo_dirs(config: RepoConfig) -> None:
    for path in (
        config.big_dir,
        config.cas_dir,
        config.big_dir / "metadata",
        config.staging_dir,
        config.big_dir / "locks",
        config.big_dir / "leases",
        config.big_dir / "restore-journals",
    ):
        path.mkdir(parents=True, exist_ok=True)


def resolve_work_root(config: RepoConfig, path: Path) -> WorkRoot:
    resolved = path.resolve()
    matches = [
        root
        for root in config.work_roots
        if resolved == root.path or root.path in resolved.parents
    ]
    if not matches:
        raise ValueError(f"{path} is not under any registered work root")
    return max(matches, key=lambda item: len(item.path.parts))


def resolve_workspace_context(config: RepoConfig, path: Path) -> WorkspaceContext:
    resolved = path.resolve()
    work_root = resolve_work_root(config, resolved)
    relative_parts = resolved.relative_to(work_root.path).parts
    if len(relative_parts) < 3 or relative_parts[0] != "user":
        raise ValueError(
            "Current path must be under user/<username>/<flow> in a registered work root"
        )

    user = relative_parts[1]
    flow = relative_parts[2]
    workspace_path = work_root.path / "user" / user / flow
    workspace_id = f"user/{user}/{flow}"
    default_branch = f"workspace/{work_root.id}/{user}/{flow}"
    return WorkspaceContext(
        work_root=work_root,
        user=user,
        flow=flow,
        workspace_path=workspace_path,
        workspace_id=workspace_id,
        default_branch=default_branch,
    )
