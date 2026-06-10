from __future__ import annotations

import os
import re
from pathlib import Path

from click.testing import CliRunner

from big.cli import main


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

        log = runner.invoke(main, ["log"])
        assert log.exit_code == 0, log.output
        assert first_version.group(1) in log.output

        show = runner.invoke(main, ["show", first_version.group(1), "--full"])
        assert show.exit_code == 0, show.output
        assert "inputs: 2" in show.output
        assert "outputs: 2" in show.output
        assert "inputs/top.v" in show.output

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
