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
class RepoConfig:
    repo_id: str
    integration: str
    home: Path
    work_roots: tuple[WorkRoot, ...]

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
