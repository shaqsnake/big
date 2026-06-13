from __future__ import annotations

import os
import re
from pathlib import Path

from click.testing import CliRunner

from big.cas import object_path
from big.cli import main
from big.config import find_config
from big.metadata import SQLiteMetadataRepository


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_repo_init_commit_log_show_and_diff(tmp_path: Path) -> None:
    runner = CliRunner()
    repo_root = tmp_path / "data" / "DemoChip"
    workspace = repo_root / "user" / "alice" / "APR"
    _write(workspace / "inputs" / "top.v", "module top; endmodule\n")
    _write(workspace / "scripts" / "place.tcl", "place_design\n")
    _write(workspace / "outputs" / "top.def", "VERSION 5.8 ;\n")
    _write(workspace / "reports" / "place.rpt", "wns 0.01\n")

    init_result = runner.invoke(
        main, ["repo", "init", str(repo_root), "--repo-id", "DemoChip"]
    )
    assert init_result.exit_code == 0, init_result.output
    assert (repo_root / "big.toml").exists()
    assert (repo_root / ".big" / "cas" / "objects").exists()

    old_cwd = Path.cwd()
    try:
        os.chdir(repo_root)
        root_status = runner.invoke(main, ["status"])
        assert root_status.exit_code == 0, root_status.output
        assert "repo: DemoChip" in root_status.output
        assert "integration: 2d" in root_status.output
        assert "work_root: default" in root_status.output
        assert "workspace: -" in root_status.output
        assert "context_error:" in root_status.output

        os.chdir(workspace)
        first = runner.invoke(
            main,
            [
                "commit",
                "--step",
                "place",
                "--inputs",
                "inputs/**;scripts/**",
                "--outputs",
                "outputs/**;reports/**",
                "--message",
                "initial place snapshot",
            ],
        )
        assert first.exit_code == 0, first.output
        first_version = re.search(r"version: (v[0-9a-f]+)", first.output)
        assert first_version
        assert "branch: workspace/default/alice/APR" in first.output
        assert "workspace: user/alice/APR" in first.output

        status = runner.invoke(main, ["status"])
        assert status.exit_code == 0, status.output
        assert "repo: DemoChip" in status.output
        assert "workspace: user/alice/APR" in status.output
        assert "user: alice" in status.output
        assert "flow: APR" in status.output
        assert "default_ref: workspace/default/alice/APR" in status.output
        assert f"head: {first_version.group(1)}" in status.output
        assert "head_step: place" in status.output
        assert "head_message: initial place snapshot" in status.output

        log = runner.invoke(main, ["log"])
        assert log.exit_code == 0, log.output
        assert first_version.group(1) in log.output

        branch_create = runner.invoke(main, ["branch", "create", "feature/place"])
        assert branch_create.exit_code == 0, branch_create.output
        assert "branch: feature/place" in branch_create.output
        assert f"head: {first_version.group(1)}" in branch_create.output
        assert "source_ref: workspace/default/alice/APR" in branch_create.output

        branch_from_version = runner.invoke(
            main,
            [
                "branch",
                "create",
                "feature/from-version",
                "--from",
                first_version.group(1),
            ],
        )
        assert branch_from_version.exit_code == 0, branch_from_version.output
        assert "branch: feature/from-version" in branch_from_version.output
        assert f"source_ref: {first_version.group(1)}" in branch_from_version.output

        branch_show = runner.invoke(main, ["branch", "show", "feature/place"])
        assert branch_show.exit_code == 0, branch_show.output
        assert "branch: feature/place" in branch_show.output
        assert "kind: named" in branch_show.output
        assert f"head: {first_version.group(1)}" in branch_show.output
        assert "source_ref: workspace/default/alice/APR" in branch_show.output
        assert "head_step: place" in branch_show.output
        assert "head_workspace: user/alice/APR" in branch_show.output
        assert "head_message: initial place snapshot" in branch_show.output

        workspace_ref_show = runner.invoke(
            main, ["branch", "show", "workspace/default/alice/APR"]
        )
        assert workspace_ref_show.exit_code == 0, workspace_ref_show.output
        assert "branch: workspace/default/alice/APR" in workspace_ref_show.output
        assert "kind: workspace" in workspace_ref_show.output
        assert f"head: {first_version.group(1)}" in workspace_ref_show.output

        branch_list = runner.invoke(main, ["branch", "list"])
        assert branch_list.exit_code == 0, branch_list.output
        assert f"named feature/place {first_version.group(1)}" in branch_list.output
        assert f"named feature/from-version {first_version.group(1)}" in branch_list.output
        assert "workspace workspace/default/alice/APR" not in branch_list.output

        branch_list_all = runner.invoke(main, ["branch", "list", "--all"])
        assert branch_list_all.exit_code == 0, branch_list_all.output
        assert "workspace workspace/default/alice/APR" in branch_list_all.output

        named_branch_log = runner.invoke(main, ["log", "feature/place"])
        assert named_branch_log.exit_code == 0, named_branch_log.output
        assert first_version.group(1) in named_branch_log.output

        show = runner.invoke(main, ["show", first_version.group(1), "--full"])
        assert show.exit_code == 0, show.output
        assert "inputs: 2" in show.output
        assert "outputs: 2" in show.output
        assert "workspace: user/alice/APR" in show.output
        assert "inputs/top.v" in show.output

        verify = runner.invoke(main, ["verify", first_version.group(1)])
        assert verify.exit_code == 0, verify.output
        assert f"version: {first_version.group(1)}" in verify.output
        assert "files: 4" in verify.output
        assert "integrity: ok" in verify.output

        stats = runner.invoke(main, ["repo", "stats"])
        assert stats.exit_code == 0, stats.output
        assert "repo: DemoChip" in stats.output
        assert "versions: 1" in stats.output
        assert "file_refs: 4" in stats.output
        assert "unique_referenced_objects: 4" in stats.output
        assert "cas_objects: 4" in stats.output
        assert "dedupe_ratio: 1.00x" in stats.output
        assert "resident: versions=1" in stats.output

        _write(workspace / "inputs" / "top.v", "module top; wire a; endmodule\n")
        _write(workspace / "outputs" / "top.def", "VERSION 5.8 ;\nCOMPONENTS 1 ;\n")
        second = runner.invoke(
            main,
            [
                "commit",
                "--step",
                "place",
                "--inputs",
                "inputs/**",
                "--inputs",
                "scripts/**",
                "--outputs",
                "outputs/**",
                "--outputs",
                "reports/**",
                "--message",
                "modified place snapshot",
            ],
        )
        assert second.exit_code == 0, second.output
        second_version = re.search(r"version: (v[0-9a-f]+)", second.output)
        assert second_version

        diff = runner.invoke(
            main,
            ["diff", first_version.group(1), second_version.group(1), "--verbose"],
        )
        assert diff.exit_code == 0, diff.output
        assert "recipe_hash: changed" in diff.output
        assert "~ input inputs/top.v" in diff.output
        assert "~ output outputs/top.def" in diff.output

        reset = runner.invoke(
            main,
            [
                "reset",
                first_version.group(1),
                "--message",
                "rollback to initial place",
            ],
        )
        assert reset.exit_code == 0, reset.output
        assert "branch: workspace/default/alice/APR" in reset.output
        assert f"old_head: {second_version.group(1)}" in reset.output
        assert f"new_head: {first_version.group(1)}" in reset.output
        assert "reset: moved" in reset.output
        assert "workspace_files: unchanged" in reset.output
        assert "wire a" in (workspace / "inputs" / "top.v").read_text(encoding="utf-8")

        reset_log = runner.invoke(main, ["log"])
        assert reset_log.exit_code == 0, reset_log.output
        assert first_version.group(1) in reset_log.output
        assert second_version.group(1) not in reset_log.output

        reset_status = runner.invoke(main, ["status"])
        assert reset_status.exit_code == 0, reset_status.output
        assert f"head: {first_version.group(1)}" in reset_status.output

        noop_reset = runner.invoke(main, ["reset", first_version.group(1)])
        assert noop_reset.exit_code == 0, noop_reset.output
        assert "reset: no-op" in noop_reset.output

        config, _ = find_config(workspace)
        events = SQLiteMetadataRepository(config.metadata_db).list_branch_events(
            "workspace/default/alice/APR"
        )
        assert len(events) == 1
        assert events[0].old_head_version_id == second_version.group(1)
        assert events[0].new_head_version_id == first_version.group(1)
        assert events[0].reason == "rollback to initial place"

        branch_events = runner.invoke(main, ["branch", "events"])
        assert branch_events.exit_code == 0, branch_events.output
        assert "reset workspace/default/alice/APR" in branch_events.output
        assert f"{second_version.group(1)}->{first_version.group(1)}" in branch_events.output
        assert "rollback to initial place" in branch_events.output

        named_branch_events = runner.invoke(main, ["branch", "events", "feature/place"])
        assert named_branch_events.exit_code == 0, named_branch_events.output
        assert "No branch events on feature/place." in named_branch_events.output
    finally:
        os.chdir(old_cwd)


def test_commit_rejects_missing_inputs(tmp_path: Path) -> None:
    runner = CliRunner()
    repo_root = tmp_path / "data" / "DemoChip"
    workspace = repo_root / "user" / "alice" / "APR"
    _write(workspace / "outputs" / "top.def", "VERSION 5.8 ;\n")
    assert runner.invoke(
        main, ["repo", "init", str(repo_root), "--repo-id", "DemoChip"]
    ).exit_code == 0

    old_cwd = Path.cwd()
    try:
        os.chdir(workspace)
        result = runner.invoke(
            main,
            [
                "commit",
                "--step",
                "place",
                "--inputs",
                "missing/**",
                "--outputs",
                "outputs/**",
            ],
        )
        assert result.exit_code != 0
        assert "No input files matched" in result.output
    finally:
        os.chdir(old_cwd)


def test_default_workspace_histories_are_isolated_by_user_and_flow(
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    repo_root = tmp_path / "data" / "DemoChip"
    alice_workspace = repo_root / "user" / "alice" / "APR"
    shaq_workspace = repo_root / "user" / "shaqsnake" / "APR"
    for workspace, net_name in (
        (alice_workspace, "alice_net"),
        (shaq_workspace, "shaq_net"),
    ):
        _write(
            workspace / "inputs" / "top.v",
            f"module top; wire {net_name}; endmodule\n",
        )
        _write(workspace / "scripts" / "place.tcl", "place_design\n")
        _write(workspace / "outputs" / "top.def", "VERSION 5.8 ;\n")
        _write(workspace / "reports" / "place.rpt", "wns 0.01\n")

    assert runner.invoke(
        main, ["repo", "init", str(repo_root), "--repo-id", "DemoChip"]
    ).exit_code == 0

    old_cwd = Path.cwd()
    try:
        os.chdir(alice_workspace)
        alice_commit = runner.invoke(
            main,
            [
                "commit",
                "--step",
                "place",
                "--inputs",
                "inputs/**;scripts/**",
                "--outputs",
                "outputs/**;reports/**",
                "--message",
                "alice snapshot",
            ],
        )
        assert alice_commit.exit_code == 0, alice_commit.output
        alice_version = re.search(r"version: (v[0-9a-f]+)", alice_commit.output)
        assert alice_version
        assert "branch: workspace/default/alice/APR" in alice_commit.output

        os.chdir(shaq_workspace)
        shaq_commit = runner.invoke(
            main,
            [
                "commit",
                "--step",
                "place",
                "--inputs",
                "inputs/**;scripts/**",
                "--outputs",
                "outputs/**;reports/**",
                "--message",
                "shaqsnake snapshot",
            ],
        )
        assert shaq_commit.exit_code == 0, shaq_commit.output
        shaq_version = re.search(r"version: (v[0-9a-f]+)", shaq_commit.output)
        assert shaq_version
        assert "branch: workspace/default/shaqsnake/APR" in shaq_commit.output

        shaq_log = runner.invoke(main, ["log"])
        assert shaq_log.exit_code == 0, shaq_log.output
        assert shaq_version.group(1) in shaq_log.output
        assert alice_version.group(1) not in shaq_log.output

        os.chdir(alice_workspace)
        alice_log = runner.invoke(main, ["log"])
        assert alice_log.exit_code == 0, alice_log.output
        assert alice_version.group(1) in alice_log.output
        assert shaq_version.group(1) not in alice_log.output

        main_log = runner.invoke(main, ["log", "main"])
        assert main_log.exit_code == 0, main_log.output
        assert "No versions visible on branch main." in main_log.output

        os.chdir(shaq_workspace)
        cross_reset = runner.invoke(main, ["reset", alice_version.group(1)])
        assert cross_reset.exit_code != 0
        assert "not an ancestor of the current ref head" in cross_reset.output
        shaq_status = runner.invoke(main, ["status"])
        assert shaq_status.exit_code == 0, shaq_status.output
        assert f"head: {shaq_version.group(1)}" in shaq_status.output
    finally:
        os.chdir(old_cwd)


def test_repo_init_supports_3dic_pointer_work_roots(tmp_path: Path) -> None:
    runner = CliRunner()
    data_root = tmp_path / "data"
    main_root = data_root / "DemoChip_3D"
    top_root = data_root / "DemoChip_Top"
    bottom_root = data_root / "DemoChip_Bottom"
    mix_root = data_root / "DemoChip_MIX"

    init = runner.invoke(
        main,
        [
            "repo",
            "init",
            str(main_root),
            "--repo-id",
            "DemoChip",
            "--integration",
            "3d",
            "--work-root",
            f"3d={main_root}",
            "--work-root",
            f"top={top_root}",
            "--work-root",
            f"bottom={bottom_root}",
            "--work-root",
            f"mix={mix_root}",
        ],
    )
    assert init.exit_code == 0, init.output
    assert "work_roots: 4" in init.output
    assert (main_root / "big.toml").exists()
    assert (main_root / ".big" / "metadata").exists()
    assert (top_root / "big.toml").exists()
    assert (bottom_root / "big.toml").exists()
    assert (mix_root / "big.toml").exists()
    assert not (top_root / ".big").exists()
    assert "work_root_id = \"top\"" in (top_root / "big.toml").read_text(
        encoding="utf-8"
    )

    top_workspace = top_root / "user" / "alice" / "APR"
    _write(top_workspace / "inputs" / "top.v", "module top; endmodule\n")
    _write(top_workspace / "outputs" / "top.def", "VERSION 5.8 ;\n")

    old_cwd = Path.cwd()
    try:
        os.chdir(top_workspace)
        status = runner.invoke(main, ["status"])
        assert status.exit_code == 0, status.output
        assert "repo: DemoChip" in status.output
        assert "integration: 3d" in status.output
        assert f"home: {main_root.resolve()}" in status.output
        assert f"work_root: top {top_root.resolve()}" in status.output
        assert "workspace: user/alice/APR" in status.output
        assert "default_ref: workspace/top/alice/APR" in status.output

        commit = runner.invoke(
            main,
            [
                "commit",
                "--step",
                "place",
                "--inputs",
                "inputs/**",
                "--outputs",
                "outputs/**",
            ],
        )
        assert commit.exit_code == 0, commit.output
        assert "branch: workspace/top/alice/APR" in commit.output
        assert (main_root / ".big" / "cas" / "objects").exists()
        assert not (top_root / ".big").exists()
    finally:
        os.chdir(old_cwd)


def test_branch_show_rejects_unknown_ref(tmp_path: Path) -> None:
    runner = CliRunner()
    repo_root = tmp_path / "data" / "DemoChip"
    workspace = repo_root / "user" / "alice" / "APR"
    workspace.mkdir(parents=True)
    assert runner.invoke(
        main, ["repo", "init", str(repo_root), "--repo-id", "DemoChip"]
    ).exit_code == 0

    old_cwd = Path.cwd()
    try:
        os.chdir(workspace)
        result = runner.invoke(main, ["branch", "show", "feature/missing"])
        assert result.exit_code != 0
        assert "Branch/ref not found: feature/missing" in result.output
    finally:
        os.chdir(old_cwd)


def test_verify_reports_missing_cas_object(tmp_path: Path) -> None:
    runner = CliRunner()
    repo_root = tmp_path / "data" / "DemoChip"
    workspace = repo_root / "user" / "alice" / "APR"
    _write(workspace / "inputs" / "top.v", "module top; endmodule\n")
    _write(workspace / "outputs" / "top.def", "VERSION 5.8 ;\n")
    assert runner.invoke(
        main, ["repo", "init", str(repo_root), "--repo-id", "DemoChip"]
    ).exit_code == 0

    old_cwd = Path.cwd()
    try:
        os.chdir(workspace)
        commit = runner.invoke(
            main,
            [
                "commit",
                "--step",
                "place",
                "--inputs",
                "inputs/**",
                "--outputs",
                "outputs/**",
            ],
        )
        assert commit.exit_code == 0, commit.output
        version = re.search(r"version: (v[0-9a-f]+)", commit.output)
        assert version

        config, _ = find_config(workspace)
        metadata = SQLiteMetadataRepository(config.metadata_db)
        refs = metadata.get_file_refs(version.group(1))
        missing_object = object_path(config.cas_dir, refs[0].cas_hash)
        missing_object.chmod(0o666)
        missing_object.unlink()

        verify = runner.invoke(main, ["verify", version.group(1), "--full"])
        assert verify.exit_code != 0
        assert "integrity: failed" in verify.output
        assert "missing: 1" in verify.output
        assert "missing " in verify.output
        assert "CAS integrity verification failed" in verify.output
    finally:
        os.chdir(old_cwd)
