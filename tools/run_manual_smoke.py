from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys

try:
    from create_manual_lab import create_manual_lab
except ModuleNotFoundError:
    from tools.create_manual_lab import create_manual_lab


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _safe_reset_manual_lab(root: Path) -> None:
    project_root = _project_root().resolve()
    resolved = root.resolve()
    try:
        relative = resolved.relative_to(project_root)
    except ValueError as exc:
        raise SystemExit(f"Refusing to reset path outside project root: {resolved}") from exc
    if not relative.parts or relative.parts[0] != "manual-lab":
        raise SystemExit(f"Refusing to reset non-manual-lab path: {resolved}")
    if not resolved.exists():
        return
    shutil.rmtree(resolved, onerror=_make_writable_and_retry)


def _make_writable_and_retry(function, path: str, _exc_info) -> None:
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    function(path)


def _run_big(args: list[str], cwd: Path, env: dict[str, str]) -> str:
    command = [sys.executable, "-m", "big", *args]
    display = "python -m big " + " ".join(args)
    print(f"$ {display}  # cwd={cwd}")
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    return result.stdout


def _version_from(output: str) -> str:
    match = re.search(r"^version: (v[0-9a-f]+)$", output, re.MULTILINE)
    if not match:
        raise SystemExit("Smoke command did not print a version id")
    return match.group(1)


def _value_from(output: str, key: str) -> str:
    match = re.search(rf"^{re.escape(key)}: (.+)$", output, re.MULTILINE)
    if not match:
        raise SystemExit(f"Smoke command did not print {key}")
    return match.group(1)


def _expect_contains(output: str, expected: str) -> None:
    if expected not in output:
        raise SystemExit(f"Expected smoke output to contain: {expected}")


def run_smoke(root: Path, repo_id: str, reset: bool) -> None:
    project_root = _project_root()
    root = root.resolve()
    if reset:
        _safe_reset_manual_lab(root)
    create_manual_lab(root, overwrite=True)

    env = os.environ.copy()
    src_path = str(project_root / "src")
    env["PYTHONPATH"] = (
        src_path
        if not env.get("PYTHONPATH")
        else src_path + os.pathsep + env["PYTHONPATH"]
    )

    alice_workspace = root / "user" / "alice" / "APR"
    shaq_workspace = root / "user" / "shaqsnake" / "APR"

    _run_big(["repo", "init", str(root), "--repo-id", repo_id], project_root, env)

    alice_status = _run_big(["status"], alice_workspace, env)
    _expect_contains(alice_status, "default_ref: workspace/default/alice/APR")

    shell_init = _run_big(["shell-init", "bash"], alice_workspace, env)
    _expect_contains(shell_init, 'eval "$(big shell-init bash)"')
    _expect_contains(shell_init, "big() {")
    _expect_contains(shell_init, "grep -q '^materialization: plan-only$'")

    alice_commit = _run_big(
        [
            "commit",
            "--step",
            "place",
            "--inputs",
            "inputs/**;scripts/**",
            "--outputs",
            "outputs/**;reports/**",
            "--message",
            "alice smoke snapshot",
        ],
        alice_workspace,
        env,
    )
    alice_version = _version_from(alice_commit)
    _expect_contains(alice_commit, "branch: workspace/default/alice/APR")

    _run_big(["branch", "create", "feature/place"], alice_workspace, env)

    checkout_plan = _run_big(["checkout", "feature/place", "--plan"], alice_workspace, env)
    _expect_contains(checkout_plan, f"version: {alice_version}")
    _expect_contains(checkout_plan, "materialization: plan-only")
    target_path = Path(_value_from(checkout_plan, "target_path"))
    if target_path.exists():
        raise SystemExit(f"Plan-only checkout unexpectedly created: {target_path}")

    checkout_print_plan = _run_big(
        ["checkout", "feature/place", "--plan", "--print-path"],
        alice_workspace,
        env,
    )
    if checkout_print_plan.strip() != str(target_path):
        raise SystemExit("Checkout --print-path plan output did not match target path")
    if target_path.exists():
        raise SystemExit(f"Print-path plan unexpectedly created: {target_path}")

    checkout = _run_big(["checkout", "feature/place"], alice_workspace, env)
    _expect_contains(checkout, "materialization: copied")
    _expect_contains(checkout, "files: 5")
    target_path = Path(_value_from(checkout, "target_path"))
    expected_copy = target_path / "inputs" / "top.v"
    if expected_copy.read_text(encoding="utf-8") != "module top;\nendmodule\n":
        raise SystemExit(f"Checkout copy content mismatch: {expected_copy}")
    if not (target_path / ".big-checkout.json").exists():
        raise SystemExit(f"Checkout marker is missing: {target_path}")

    checkout_status = _run_big(["status"], target_path, env)
    _expect_contains(checkout_status, "default_ref: feature/place")
    _expect_contains(checkout_status, "workspace: checkout/default/alice/APR/feature/place@")
    _expect_contains(checkout_status, f"head: {alice_version}")

    checkout_log = _run_big(["log"], target_path, env)
    _expect_contains(checkout_log, alice_version)

    checkout_print_path = _run_big(
        ["checkout", "feature/place", "--print-path"],
        alice_workspace,
        env,
    )
    if checkout_print_path.strip() != str(target_path):
        raise SystemExit("Checkout --print-path output did not match materialized path")

    historical_plan = _run_big(
        ["checkout", alice_version, "--new-branch", "from-v1", "--plan"],
        alice_workspace,
        env,
    )
    _expect_contains(historical_plan, "branch: from-v1")
    _expect_contains(historical_plan, "branch_created: plan-only")
    _expect_contains(historical_plan, "materialization: plan-only")
    from_v1_path = Path(_value_from(historical_plan, "target_path"))
    if from_v1_path.exists():
        raise SystemExit(f"Plan-only historical checkout unexpectedly created: {from_v1_path}")

    historical_checkout = _run_big(
        ["checkout", alice_version, "--new-branch", "from-v1"],
        alice_workspace,
        env,
    )
    _expect_contains(historical_checkout, "branch: from-v1")
    _expect_contains(historical_checkout, "branch_created: yes")
    _expect_contains(historical_checkout, "materialization: copied")
    if not (from_v1_path / ".big-checkout.json").exists():
        raise SystemExit(f"Historical checkout marker is missing: {from_v1_path}")
    from_v1_status = _run_big(["status"], from_v1_path, env)
    _expect_contains(from_v1_status, "default_ref: from-v1")
    _expect_contains(from_v1_status, f"head: {alice_version}")

    checkout_again = _run_big(["checkout", "feature/place"], alice_workspace, env)
    _expect_contains(checkout_again, "materialization: reused")

    shaq_commit = _run_big(
        [
            "commit",
            "--step",
            "place",
            "--inputs",
            "inputs/**;scripts/**",
            "--outputs",
            "outputs/**;reports/**",
            "--message",
            "shaqsnake smoke snapshot",
        ],
        shaq_workspace,
        env,
    )
    shaq_version = _version_from(shaq_commit)
    _expect_contains(shaq_commit, "branch: workspace/default/shaqsnake/APR")

    shaq_log = _run_big(["log"], shaq_workspace, env)
    _expect_contains(shaq_log, shaq_version)
    if alice_version in shaq_log:
        raise SystemExit("shaqsnake workspace log contains alice version")

    main_log = _run_big(["log", "main"], alice_workspace, env)
    _expect_contains(main_log, "No versions visible on branch main.")

    repo_verify = _run_big(["repo", "verify"], alice_workspace, env)
    _expect_contains(repo_verify, "versions: 2")
    _expect_contains(repo_verify, "file_refs: 10")
    _expect_contains(repo_verify, "integrity: ok")

    stats = _run_big(["repo", "stats"], alice_workspace, env)
    _expect_contains(stats, "versions: 2")
    _expect_contains(stats, "file_refs: 10")
    _expect_contains(stats, "unique_referenced_objects: 4")
    _expect_contains(stats, "cas_objects: 4")
    print("manual smoke: ok")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the BIG WSL/Linux manual smoke scenario."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("manual-lab/data/WslChip"),
        help="Manual lab project root. Default: manual-lab/data/WslChip",
    )
    parser.add_argument(
        "--repo-id",
        default="WslChip",
        help="Logical repo id for the smoke scenario.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete the target root first. Only paths under manual-lab/ are allowed.",
    )
    args = parser.parse_args()
    run_smoke(args.root, repo_id=args.repo_id, reset=args.reset)


if __name__ == "__main__":
    main()
