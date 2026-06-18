from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
from pathlib import Path

from click.testing import CliRunner

import big.cli as cli_module
from big.cas import object_path
from big.cli import main
from big.config import find_config
from big.metadata import SQLiteMetadataRepository


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_core_help_outputs_examples_without_repo(tmp_path: Path) -> None:
    runner = CliRunner()
    old_cwd = Path.cwd()
    try:
        os.chdir(tmp_path)
        root_help = runner.invoke(main, ["--help"])
        assert root_help.exit_code == 0, root_help.output
        assert "BIG prototype CLI" in root_help.output
        assert "Examples:" in root_help.output
        assert "big repo init /data/DemoChip --repo-id DemoChip" in root_help.output
        assert "big commit --step place" in root_help.output

        init_help = runner.invoke(main, ["repo", "init", "--help"])
        assert init_help.exit_code == 0, init_help.output
        assert "Initialize a prototype BIG repository" in init_help.output
        assert "--integration [2d|3d]" in init_help.output
        assert "--work-root" in init_help.output
        assert "--work-root top=/data/StackChip_Top" in init_help.output

        commit_help = runner.invoke(main, ["commit", "--help"])
        assert commit_help.exit_code == 0, commit_help.output
        assert "--step" in commit_help.output
        assert "--inputs" in commit_help.output
        assert "--outputs" in commit_help.output
        assert "--require-marker" in commit_help.output
        assert "--settle-ms" in commit_help.output
        assert "A separate params role is" in commit_help.output
        assert "future scope." in commit_help.output
        assert not (tmp_path / ".big").exists()
    finally:
        os.chdir(old_cwd)


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

        audit_verify = runner.invoke(main, ["audit", "verify"])
        assert audit_verify.exit_code == 0, audit_verify.output
        assert "events: 1" in audit_verify.output
        assert "integrity: ok" in audit_verify.output

        audit_log = runner.invoke(main, ["audit", "log", "--full"])
        assert audit_log.exit_code == 0, audit_log.output
        assert f"commit version {first_version.group(1)}" in audit_log.output
        assert '"branch":"workspace/default/alice/APR"' in audit_log.output
        assert '"input_count":2' in audit_log.output
        assert '"output_count":2' in audit_log.output

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

        checkout_from_version_plan = runner.invoke(
            main,
            [
                "checkout",
                first_version.group(1),
                "--new-branch",
                "from-v1",
                "--plan",
            ],
        )
        assert checkout_from_version_plan.exit_code == 0, checkout_from_version_plan.output
        assert "branch: from-v1" in checkout_from_version_plan.output
        assert f"version: {first_version.group(1)}" in checkout_from_version_plan.output
        assert f"source_ref: {first_version.group(1)}" in checkout_from_version_plan.output
        assert "branch_created: plan-only" in checkout_from_version_plan.output
        assert "materialization: plan-only" in checkout_from_version_plan.output
        from_v1_target = (
            workspace.parent
            / ".big-checkouts"
            / "APR"
            / "from-v1"
            / first_version.group(1)
        )
        assert f"target_path: {from_v1_target}" in checkout_from_version_plan.output
        assert not from_v1_target.exists()
        from_v1_before_create = runner.invoke(main, ["branch", "show", "from-v1"])
        assert from_v1_before_create.exit_code != 0
        assert "Branch/ref not found: from-v1" in from_v1_before_create.output

        checkout_from_version_print_plan = runner.invoke(
            main,
            [
                "checkout",
                first_version.group(1),
                "--new-branch",
                "from-v1",
                "--plan",
                "--print-path",
            ],
        )
        assert checkout_from_version_print_plan.exit_code == 0
        assert checkout_from_version_print_plan.output.strip() == str(from_v1_target)
        assert not from_v1_target.exists()

        checkout_from_version = runner.invoke(
            main,
            ["checkout", first_version.group(1), "--new-branch", "from-v1"],
        )
        assert checkout_from_version.exit_code == 0, checkout_from_version.output
        assert "branch: from-v1" in checkout_from_version.output
        assert "branch_created: yes" in checkout_from_version.output
        assert "materialization: copied" in checkout_from_version.output
        assert from_v1_target.exists()
        assert (from_v1_target / "inputs" / "top.v").read_text(
            encoding="utf-8"
        ) == "module top; endmodule\n"
        from_v1_show = runner.invoke(main, ["branch", "show", "from-v1"])
        assert from_v1_show.exit_code == 0, from_v1_show.output
        assert "branch: from-v1" in from_v1_show.output
        assert f"head: {first_version.group(1)}" in from_v1_show.output
        assert f"source_ref: {first_version.group(1)}" in from_v1_show.output

        duplicate_new_branch = runner.invoke(
            main,
            ["checkout", first_version.group(1), "--new-branch", "from-v1"],
        )
        assert duplicate_new_branch.exit_code != 0
        assert "Branch already exists: from-v1" in duplicate_new_branch.output

        version_without_branch = runner.invoke(
            main, ["checkout", first_version.group(1)]
        )
        assert version_without_branch.exit_code != 0
        assert "Version checkout requires --new-branch" in version_without_branch.output

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

        checkout_plan = runner.invoke(
            main, ["checkout", "feature/place", "--plan"]
        )
        assert checkout_plan.exit_code == 0, checkout_plan.output
        assert "branch: feature/place" in checkout_plan.output
        assert f"version: {first_version.group(1)}" in checkout_plan.output
        assert "materialization: plan-only" in checkout_plan.output
        assert ".big-checkouts" in checkout_plan.output
        assert "feature__place" in checkout_plan.output
        assert f"/{first_version.group(1)}" in checkout_plan.output.replace("\\", "/")
        expected_target = (
            workspace.parent
            / ".big-checkouts"
            / "APR"
            / "feature__place"
            / first_version.group(1)
        )
        assert f"target_path: {expected_target}" in checkout_plan.output
        assert not expected_target.exists()

        checkout_print_plan = runner.invoke(
            main, ["checkout", "feature/place", "--plan", "--print-path"]
        )
        assert checkout_print_plan.exit_code == 0
        assert checkout_print_plan.output.strip() == str(expected_target)
        assert not expected_target.exists()

        checkout = runner.invoke(main, ["checkout", "feature/place"])
        assert checkout.exit_code == 0, checkout.output
        assert "branch: feature/place" in checkout.output
        assert f"version: {first_version.group(1)}" in checkout.output
        assert "files: 4" in checkout.output
        assert "materialization: copied" in checkout.output
        assert expected_target.exists()
        assert (expected_target / "inputs" / "top.v").read_text(
            encoding="utf-8"
        ) == "module top; endmodule\n"
        assert not (expected_target / "inputs" / "top.v").is_symlink()
        assert (expected_target / "scripts" / "place.tcl").exists()
        assert (expected_target / "outputs" / "top.def").exists()
        assert (expected_target / "reports" / "place.rpt").exists()
        marker = json.loads(
            (expected_target / ".big-checkout.json").read_text(encoding="utf-8")
        )
        assert marker["schema"] == 1
        assert marker["repo_id"] == "DemoChip"
        assert marker["branch"] == "feature/place"
        assert marker["version"] == first_version.group(1)
        assert marker["materialization"] == "copy"

        checkout_again = runner.invoke(main, ["checkout", "feature/place"])
        assert checkout_again.exit_code == 0, checkout_again.output
        assert "materialization: reused" in checkout_again.output

        checkout_print_path = runner.invoke(
            main, ["checkout", "feature/place", "--print-path"]
        )
        assert checkout_print_path.exit_code == 0
        assert checkout_print_path.output.strip() == str(expected_target)
        assert "branch:" not in checkout_print_path.output

        os.chdir(expected_target)
        checkout_status = runner.invoke(main, ["status"])
        assert checkout_status.exit_code == 0, checkout_status.output
        assert "workspace: checkout/default/alice/APR/feature/place@" in checkout_status.output
        assert f"workspace_path: {expected_target}" in checkout_status.output
        assert "default_ref: feature/place" in checkout_status.output
        assert f"head: {first_version.group(1)}" in checkout_status.output

        checkout_log = runner.invoke(main, ["log"])
        assert checkout_log.exit_code == 0, checkout_log.output
        assert first_version.group(1) in checkout_log.output

        os.chdir(workspace)

        branch_list = runner.invoke(main, ["branch", "list"])
        assert branch_list.exit_code == 0, branch_list.output
        assert f"named feature/place {first_version.group(1)}" in branch_list.output
        assert f"named feature/from-version {first_version.group(1)}" in branch_list.output
        assert f"named from-v1 {first_version.group(1)}" in branch_list.output
        assert "workspace workspace/default/alice/APR" not in branch_list.output

        branch_list_all = runner.invoke(main, ["branch", "list", "--all"])
        assert branch_list_all.exit_code == 0, branch_list_all.output
        assert "workspace workspace/default/alice/APR" in branch_list_all.output

        named_branch_log = runner.invoke(main, ["log", "feature/place"])
        assert named_branch_log.exit_code == 0, named_branch_log.output
        assert first_version.group(1) in named_branch_log.output

        show = runner.invoke(main, ["show", first_version.group(1), "--full"])
        assert show.exit_code == 0, show.output
        assert "message: initial place snapshot" in show.output
        assert "inputs: 2" in show.output
        assert "outputs: 2" in show.output
        assert "workspace: user/alice/APR" in show.output
        assert "input_summary:" in show.output
        assert "output_summary:" in show.output
        assert "semantic_roles: eda_design_file=1,script_or_config=1" in show.output
        assert "format_hints: tcl=1,v=1" in show.output
        assert "capture_evidence: available=2 unavailable=0" in show.output
        assert "inputs/top.v" in show.output
        assert "capture_evidence:" in show.output
        assert "before_size=" in show.output
        assert "after_size=" in show.output

        show_default = runner.invoke(main, ["show", first_version.group(1)])
        assert show_default.exit_code == 0, show_default.output
        assert "message: initial place snapshot" in show_default.output
        assert "inputs/top.v" not in show_default.output
        assert "input_summary:" not in show_default.output

        config, _ = find_config(workspace)
        stored_refs = SQLiteMetadataRepository(config.metadata_db).get_file_refs(
            first_version.group(1)
        )
        evidence_payloads = [
            json.loads(ref.capture_evidence_json) for ref in stored_refs
        ]
        assert all(payload["schema"] == 1 for payload in evidence_payloads)
        assert all("source_before" in payload for payload in evidence_payloads)
        assert all("source_after" in payload for payload in evidence_payloads)

        verify = runner.invoke(main, ["verify", first_version.group(1)])
        assert verify.exit_code == 0, verify.output
        assert f"version: {first_version.group(1)}" in verify.output
        assert "files: 4" in verify.output
        assert "integrity: ok" in verify.output

        repo_verify = runner.invoke(main, ["repo", "verify"])
        assert repo_verify.exit_code == 0, repo_verify.output
        assert "repo: DemoChip" in repo_verify.output
        assert "versions: 1" in repo_verify.output
        assert "file_refs: 4" in repo_verify.output
        assert "integrity: ok" in repo_verify.output

        stats = runner.invoke(main, ["repo", "stats"])
        assert stats.exit_code == 0, stats.output
        assert "repo: DemoChip" in stats.output
        assert "versions: 1" in stats.output
        assert "file_refs: 4" in stats.output
        assert "unique_referenced_objects: 4" in stats.output
        assert "cas_objects: 4" in stats.output
        assert "dedupe_ratio: 1.00x" in stats.output
        assert "review:" in stats.output
        assert "Exploring: versions=1" in stats.output
        assert "resident: versions=1" in stats.output

        _write(workspace / "inputs" / "top.v", "module top; wire a; endmodule\n")
        _write(workspace / "scripts" / "place.tcl", "set effort high\nplace_design\n")
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
        assert "manifest_hash: changed" in diff.output
        assert "review_state: unchanged" in diff.output
        assert "retention_state: unchanged" in diff.output
        assert "input_changes: added=0 removed=0 modified=2" in diff.output
        assert "output_changes: added=0 removed=0 modified=1" in diff.output
        assert "~ input inputs/top.v" in diff.output
        assert "~ output outputs/top.def" in diff.output

        lineage = runner.invoke(main, ["lineage", second_version.group(1)])
        assert lineage.exit_code == 0, lineage.output
        assert f"version: {second_version.group(1)}" in lineage.output
        assert "entries: 2" in lineage.output
        assert "truncated: no" in lineage.output
        assert (
            f"0 {second_version.group(1)} parent={first_version.group(1)}"
            in lineage.output
        )
        assert f"1 {first_version.group(1)} parent=-" in lineage.output
        assert "message: modified place snapshot" in lineage.output

        lineage_changes = runner.invoke(
            main,
            ["lineage", second_version.group(1), "--changes", "--verbose"],
        )
        assert lineage_changes.exit_code == 0, lineage_changes.output
        assert "recipe_change: changed" in lineage_changes.output
        assert "input_changes: added=0 removed=0 modified=2" in lineage_changes.output
        assert "high_impact_inputs: 1" in lineage_changes.output
        assert "~ scripts/place.tcl" in lineage_changes.output
        assert "~ inputs/top.v" in lineage_changes.output
        assert "outputs/top.def" not in lineage_changes.output

        limited_lineage = runner.invoke(
            main,
            ["lineage", second_version.group(1), "--limit", "1"],
        )
        assert limited_lineage.exit_code == 0, limited_lineage.output
        assert "entries: 1" in limited_lineage.output
        assert "truncated: yes" in limited_lineage.output
        assert f"1 {first_version.group(1)} parent=-" not in limited_lineage.output

        depth_limited_lineage = runner.invoke(
            main,
            ["lineage", second_version.group(1), "--depth", "1"],
        )
        assert depth_limited_lineage.exit_code == 0, depth_limited_lineage.output
        assert "entries: 1" in depth_limited_lineage.output
        assert "truncated: yes" in depth_limited_lineage.output
        assert f"1 {first_version.group(1)} parent=-" not in depth_limited_lineage.output

        missing_lineage = runner.invoke(main, ["lineage", "v-does-not-exist"])
        assert missing_lineage.exit_code != 0
        assert "Version not found or ambiguous" in missing_lineage.output

        promote = runner.invoke(
            main,
            [
                "promote",
                second_version.group(1),
                "--to",
                "candidate",
                "--message",
                "ready for review",
            ],
        )
        assert promote.exit_code == 0, promote.output
        assert f"version: {second_version.group(1)}" in promote.output
        assert "old_state: [Exploring/resident]" in promote.output
        assert "new_state: [Candidate/resident]" in promote.output
        assert "promote: moved" in promote.output
        assert "retention: unchanged" in promote.output
        assert "candidate_outbox: queued" in promote.output
        outbox_event = re.search(r"outbox_event: (oe[0-9a-f]+)", promote.output)
        assert outbox_event

        promoted_show = runner.invoke(main, ["show", second_version.group(1)])
        assert promoted_show.exit_code == 0, promoted_show.output
        assert "state: [Candidate/resident]" in promoted_show.output

        outbox_list = runner.invoke(main, ["outbox", "list", "--full"])
        assert outbox_list.exit_code == 0, outbox_list.output
        assert outbox_event.group(1) in outbox_list.output
        assert (
            f"artifact.candidate_marked version {second_version.group(1)}"
            in outbox_list.output
        )
        assert "pending" in outbox_list.output
        assert f'"version_id":"{second_version.group(1)}"' in outbox_list.output
        assert '"manifest_hash"' in outbox_list.output

        lifecycle_events = runner.invoke(
            main,
            ["lifecycle", "events", second_version.group(1)],
        )
        assert lifecycle_events.exit_code == 0, lifecycle_events.output
        assert (
            f" {second_version.group(1)} Exploring->Candidate "
            in lifecycle_events.output
        )
        assert "resident->resident" in lifecycle_events.output
        assert "ready for review" in lifecycle_events.output

        noop_promote = runner.invoke(
            main,
            ["promote", second_version.group(1), "--to", "Candidate"],
        )
        assert noop_promote.exit_code == 0, noop_promote.output
        assert "promote: no-op" in noop_promote.output
        outbox_after_noop = runner.invoke(main, ["outbox", "list"])
        assert outbox_after_noop.exit_code == 0, outbox_after_noop.output
        assert outbox_after_noop.output.count("artifact.candidate_marked") == 1

        demote = runner.invoke(
            main,
            ["promote", second_version.group(1), "--to", "Exploring"],
        )
        assert demote.exit_code != 0
        assert "Review state demotion is not supported" in demote.output

        golden_without_confirm = runner.invoke(
            main,
            ["promote", second_version.group(1), "--to", "Golden"],
        )
        assert golden_without_confirm.exit_code != 0
        assert (
            "Promoting to Golden requires --confirm GOLDEN"
            in golden_without_confirm.output
        )

        golden = runner.invoke(
            main,
            [
                "promote",
                second_version.group(1),
                "--to",
                "Golden",
                "--confirm",
                "GOLDEN",
                "--message",
                "tapeout approved",
            ],
        )
        assert golden.exit_code == 0, golden.output
        assert "old_state: [Candidate/resident]" in golden.output
        assert "new_state: [Golden/resident]" in golden.output

        lifecycle_stats = runner.invoke(main, ["repo", "stats"])
        assert lifecycle_stats.exit_code == 0, lifecycle_stats.output
        assert "Exploring: versions=1" in lifecycle_stats.output
        assert "Golden: versions=1" in lifecycle_stats.output
        assert "resident: versions=2" in lifecycle_stats.output

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

        os.chdir(expected_target)
        _write(expected_target / "reports" / "place.rpt", "wns 0.02\n")
        checkout_commit = runner.invoke(
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
                "continue from checkout",
            ],
        )
        assert checkout_commit.exit_code == 0, checkout_commit.output
        checkout_version = re.search(r"version: (v[0-9a-f]+)", checkout_commit.output)
        assert checkout_version
        assert "branch: feature/place" in checkout_commit.output
        assert "workspace: checkout/default/alice/APR/feature/place@" in checkout_commit.output

        checkout_branch_log = runner.invoke(main, ["log"])
        assert checkout_branch_log.exit_code == 0, checkout_branch_log.output
        assert checkout_version.group(1) in checkout_branch_log.output
        assert first_version.group(1) in checkout_branch_log.output

        final_audit_verify = runner.invoke(main, ["audit", "verify"])
        assert final_audit_verify.exit_code == 0, final_audit_verify.output
        assert "integrity: ok" in final_audit_verify.output

        final_audit_log = runner.invoke(main, ["audit", "log", "--limit", "20"])
        assert final_audit_log.exit_code == 0, final_audit_log.output
        assert f"commit version {checkout_version.group(1)}" in final_audit_log.output
        assert f"promote version {second_version.group(1)}" in final_audit_log.output
        assert "reset branch workspace/default/alice/APR" in final_audit_log.output
        assert "create_branch branch feature/place" in final_audit_log.output
    finally:
        os.chdir(old_cwd)


def test_lineage_changes_ignore_output_only_commits(tmp_path: Path) -> None:
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
        first = runner.invoke(
            main,
            [
                "commit",
                "--step",
                "place",
                "--inputs",
                "inputs/**",
                "--outputs",
                "outputs/**",
                "--message",
                "base",
            ],
        )
        assert first.exit_code == 0, first.output

        _write(workspace / "outputs" / "top.def", "VERSION 5.8 ;\nCOMPONENTS 1 ;\n")
        second = runner.invoke(
            main,
            [
                "commit",
                "--step",
                "place",
                "--inputs",
                "inputs/**",
                "--outputs",
                "outputs/**",
                "--message",
                "output only",
            ],
        )
        assert second.exit_code == 0, second.output
        second_version = re.search(r"version: (v[0-9a-f]+)", second.output)
        assert second_version

        lineage_changes = runner.invoke(
            main,
            ["lineage", second_version.group(1), "--changes", "--verbose"],
        )
        assert lineage_changes.exit_code == 0, lineage_changes.output
        assert "recipe_change: unchanged" in lineage_changes.output
        assert "input_changes: added=0 removed=0 modified=0" in lineage_changes.output
        assert "outputs/top.def" not in lineage_changes.output
    finally:
        os.chdir(old_cwd)


def test_commit_can_record_cross_branch_consumes_lineage(tmp_path: Path) -> None:
    runner = CliRunner()
    repo_root = tmp_path / "data" / "DemoChip"
    alice_workspace = repo_root / "user" / "alice" / "APR"
    bob_workspace = repo_root / "user" / "bob" / "STA"
    _write(alice_workspace / "inputs" / "top.v", "module top; endmodule\n")
    _write(alice_workspace / "outputs" / "top.def", "VERSION 5.8 ;\n")
    _write(bob_workspace / "inputs" / "constraints.sdc", "create_clock clk\n")
    _write(bob_workspace / "outputs" / "timing.rpt", "wns 0.01\n")
    assert runner.invoke(
        main, ["repo", "init", str(repo_root), "--repo-id", "DemoChip"]
    ).exit_code == 0

    old_cwd = Path.cwd()
    try:
        os.chdir(alice_workspace)
        upstream_commit = runner.invoke(
            main,
            [
                "commit",
                "--step",
                "place",
                "--inputs",
                "inputs/**",
                "--outputs",
                "outputs/**",
                "--message",
                "apr output",
            ],
        )
        assert upstream_commit.exit_code == 0, upstream_commit.output
        upstream_version = re.search(r"version: (v[0-9a-f]+)", upstream_commit.output)
        assert upstream_version

        os.chdir(bob_workspace)
        downstream_commit = runner.invoke(
            main,
            [
                "commit",
                "--step",
                "sta",
                "--inputs",
                "inputs/**",
                "--outputs",
                "outputs/**",
                "--cross-branch-input",
                f"{upstream_version.group(1)}:outputs/top.def",
                "--message",
                "sta consumes apr def",
            ],
        )
        assert downstream_commit.exit_code == 0, downstream_commit.output
        assert "cross_branch_inputs: 1" in downstream_commit.output
        downstream_version = re.search(
            r"version: (v[0-9a-f]+)",
            downstream_commit.output,
        )
        assert downstream_version

        lineage = runner.invoke(main, ["lineage", downstream_version.group(1)])
        assert lineage.exit_code == 0, lineage.output
        assert f"0 {downstream_version.group(1)} parent=-" in lineage.output
        assert "consumes:" in lineage.output
        assert (
            f"- {upstream_version.group(1)} edge=consumes "
            "branch=workspace/default/alice/APR step=place "
            "path=outputs/top.def"
        ) in lineage.output
        assert "branch=workspace/default/bob/STA" in lineage.output

        lineage_full = runner.invoke(
            main, ["lineage", downstream_version.group(1), "--full"]
        )
        assert lineage_full.exit_code == 0, lineage_full.output
        assert "edge_type: target" in lineage_full.output
        assert "author:" in lineage_full.output
        assert "created_at:" in lineage_full.output
        assert "recipe_hash:" in lineage_full.output
        assert "manifest_hash:" in lineage_full.output
        assert "upstream_author:" in lineage_full.output
        assert "evidence_manifest:" in lineage_full.output
        assert "evidence_ref: output outputs/top.def" in lineage_full.output
        assert "evidence_json:" in lineage_full.output

        missing = runner.invoke(
            main,
            [
                "commit",
                "--step",
                "sta",
                "--inputs",
                "inputs/**",
                "--outputs",
                "outputs/**",
                "--cross-branch-input",
                "vdoesnotexist",
            ],
        )
        assert missing.exit_code != 0
        assert (
            "Cross-branch input version not found or ambiguous: vdoesnotexist"
            in missing.output
        )

        config, _ = find_config(bob_workspace)
        metadata = SQLiteMetadataRepository(config.metadata_db)
        edges = metadata.list_upstream_edges(downstream_version.group(1))
        assert len(edges) == 1
        assert edges[0].edge_type == "consumes"
        assert edges[0].upstream_version_id == upstream_version.group(1)

        audit_verify = runner.invoke(main, ["audit", "verify"])
        assert audit_verify.exit_code == 0, audit_verify.output
        assert "events: 2" in audit_verify.output
        assert "integrity: ok" in audit_verify.output
    finally:
        os.chdir(old_cwd)


def test_impact_lists_direct_and_recursive_consumes(tmp_path: Path) -> None:
    runner = CliRunner()
    repo_root = tmp_path / "data" / "DemoChip"
    alice_workspace = repo_root / "user" / "alice" / "APR"
    bob_workspace = repo_root / "user" / "bob" / "STA"
    carol_workspace = repo_root / "user" / "carol" / "PV"
    _write(alice_workspace / "inputs" / "top.v", "module top; endmodule\n")
    _write(alice_workspace / "outputs" / "top.def", "VERSION 5.8 ;\n")
    _write(bob_workspace / "inputs" / "constraints.sdc", "create_clock clk\n")
    _write(bob_workspace / "outputs" / "timing.rpt", "wns 0.01\n")
    _write(carol_workspace / "inputs" / "deck.runset", "layout_check\n")
    _write(carol_workspace / "outputs" / "pv.log", "clean\n")
    assert runner.invoke(
        main, ["repo", "init", str(repo_root), "--repo-id", "DemoChip"]
    ).exit_code == 0

    old_cwd = Path.cwd()
    try:
        os.chdir(alice_workspace)
        upstream_commit = runner.invoke(
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
        assert upstream_commit.exit_code == 0, upstream_commit.output
        upstream_version = re.search(r"version: (v[0-9a-f]+)", upstream_commit.output)
        assert upstream_version

        os.chdir(bob_workspace)
        bob_commit = runner.invoke(
            main,
            [
                "commit",
                "--step",
                "sta",
                "--inputs",
                "inputs/**",
                "--outputs",
                "outputs/**",
                "--cross-branch-input",
                f"{upstream_version.group(1)}:outputs/top.def",
            ],
        )
        assert bob_commit.exit_code == 0, bob_commit.output
        bob_version = re.search(r"version: (v[0-9a-f]+)", bob_commit.output)
        assert bob_version

        os.chdir(carol_workspace)
        carol_commit = runner.invoke(
            main,
            [
                "commit",
                "--step",
                "pv",
                "--inputs",
                "inputs/**",
                "--outputs",
                "outputs/**",
                "--cross-branch-input",
                f"{bob_version.group(1)}:outputs/timing.rpt",
            ],
        )
        assert carol_commit.exit_code == 0, carol_commit.output
        carol_version = re.search(r"version: (v[0-9a-f]+)", carol_commit.output)
        assert carol_version

        direct = runner.invoke(main, ["impact", upstream_version.group(1)])
        assert direct.exit_code == 0, direct.output
        assert f"version: {upstream_version.group(1)}" in direct.output
        assert "depth_limit: 1" in direct.output
        assert f"1 {bob_version.group(1)} edge=consumes" in direct.output
        assert f"upstream_branch=workspace/default/alice/APR" in direct.output
        assert f"downstream_branch=workspace/default/bob/STA" in direct.output
        assert carol_version.group(1) not in direct.output
        assert "visible_downstream: 1" in direct.output
        assert "restricted_downstream: 0" in direct.output

        recursive = runner.invoke(
            main,
            ["impact", upstream_version.group(1), "--depth", "2", "--full"],
        )
        assert recursive.exit_code == 0, recursive.output
        assert f"1 {bob_version.group(1)} edge=consumes" in recursive.output
        assert f"2 {carol_version.group(1)} edge=consumes" in recursive.output
        assert "evidence_path: outputs/top.def" in recursive.output
        assert "evidence_path: outputs/timing.rpt" in recursive.output
        assert "evidence_manifest:" in recursive.output
        assert "evidence_ref: output outputs/top.def" in recursive.output
        assert "evidence_ref: output outputs/timing.rpt" in recursive.output
        assert "evidence_json:" in recursive.output
        assert "visible_downstream: 2" in recursive.output

        no_impact = runner.invoke(main, ["impact", carol_version.group(1)])
        assert no_impact.exit_code == 0, no_impact.output
        assert "visible_downstream: 0" in no_impact.output
        assert "restricted_downstream: 0" in no_impact.output
        assert "no visible downstream impact" in no_impact.output

        audit_verify = runner.invoke(main, ["audit", "verify"])
        assert audit_verify.exit_code == 0, audit_verify.output
        assert "events: 3" in audit_verify.output
        assert "integrity: ok" in audit_verify.output
    finally:
        os.chdir(old_cwd)


def test_checkout_include_exclude_materializes_file_subset(tmp_path: Path) -> None:
    runner = CliRunner()
    repo_root = tmp_path / "data" / "DemoChip"
    workspace = repo_root / "user" / "alice" / "APR"
    _write(workspace / "inputs" / "top.v", "module top; endmodule\n")
    _write(workspace / "scripts" / "place.tcl", "place_design\n")
    _write(workspace / "outputs" / "top.def", "VERSION 5.8 ;\n")
    _write(workspace / "reports" / "place.rpt", "wns 0.01\n")
    _write(workspace / "reports" / "timing.rpt", "tns 0.00\n")
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
                "inputs/**;scripts/**",
                "--outputs",
                "outputs/**;reports/**",
                "--message",
                "partial checkout source",
            ],
        )
        assert commit.exit_code == 0, commit.output
        version = re.search(r"version: (v[0-9a-f]+)", commit.output)
        assert version

        branch = runner.invoke(main, ["branch", "create", "feature/partial"])
        assert branch.exit_code == 0, branch.output

        plan = runner.invoke(
            main,
            [
                "checkout",
                "feature/partial",
                "--include",
                "inputs/**;reports/*.rpt",
                "--exclude",
                "reports/place.rpt",
                "--plan",
                "--full",
            ],
        )
        assert plan.exit_code == 0, plan.output
        assert "checkout_scope: partial" in plan.output
        assert "selection: explicit" in plan.output
        assert "include_patterns: inputs/**;reports/*.rpt" in plan.output
        assert "exclude_patterns: reports/place.rpt" in plan.output
        assert "excluded_files: 1" in plan.output
        assert "omitted_files: 3" in plan.output
        assert "files: 2" in plan.output
        assert "materialization: plan-only" in plan.output
        assert "selected_files:" in plan.output
        assert "  input inputs/top.v " in plan.output
        assert "  output reports/timing.rpt " in plan.output
        assert "reports/place.rpt" not in plan.output.split("selected_files:", 1)[1]
        target_match = re.search(r"target_path: (.+)", plan.output)
        assert target_match
        target_path = Path(target_match.group(1))
        assert "__partial__" in target_path.name
        assert not target_path.exists()

        print_path = runner.invoke(
            main,
            [
                "checkout",
                "feature/partial",
                "--include",
                "inputs/**;reports/*.rpt",
                "--exclude",
                "reports/place.rpt",
                "--plan",
                "--print-path",
            ],
        )
        assert print_path.exit_code == 0, print_path.output
        assert print_path.output.strip() == str(target_path)

        checkout = runner.invoke(
            main,
            [
                "checkout",
                "feature/partial",
                "--include",
                "inputs/**;reports/*.rpt",
                "--exclude",
                "reports/place.rpt",
            ],
        )
        assert checkout.exit_code == 0, checkout.output
        assert "materialization: partial" in checkout.output
        assert (target_path / "inputs" / "top.v").exists()
        assert (target_path / "reports" / "timing.rpt").exists()
        assert not (target_path / "reports" / "place.rpt").exists()
        assert not (target_path / "scripts" / "place.tcl").exists()
        assert not (target_path / "outputs" / "top.def").exists()

        marker = json.loads(
            (target_path / ".big-checkout.json").read_text(encoding="utf-8")
        )
        assert marker["materialization"] == "partial"
        assert marker["selection_profile"]["include"] == [
            "inputs/**",
            "reports/*.rpt",
        ]
        assert marker["selection_profile"]["exclude"] == ["reports/place.rpt"]
        assert marker["selection_profile"]["selected_files"] == 2

        checkout_again = runner.invoke(
            main,
            [
                "checkout",
                "feature/partial",
                "--include",
                "inputs/**;reports/*.rpt",
                "--exclude",
                "reports/place.rpt",
            ],
        )
        assert checkout_again.exit_code == 0, checkout_again.output
        assert "materialization: reused" in checkout_again.output

        missing = runner.invoke(
            main,
            ["checkout", "feature/partial", "--include", "missing/**", "--plan"],
        )
        assert missing.exit_code != 0
        assert "No checkout files matched include pattern(s): missing/**" in missing.output
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
        assert "Next step: run `big commit --help`." in result.output
    finally:
        os.chdir(old_cwd)


def test_diff_separates_state_changes_from_manifest_changes(tmp_path: Path) -> None:
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
        first = runner.invoke(
            main,
            [
                "commit",
                "--step",
                "place",
                "--inputs",
                "inputs/**",
                "--outputs",
                "outputs/**",
                "--message",
                "state diff base",
            ],
        )
        assert first.exit_code == 0, first.output
        first_version = re.search(r"version: (v[0-9a-f]+)", first.output)
        assert first_version

        second = runner.invoke(
            main,
            [
                "commit",
                "--step",
                "place",
                "--inputs",
                "inputs/**",
                "--outputs",
                "outputs/**",
                "--message",
                "same manifest candidate",
            ],
        )
        assert second.exit_code == 0, second.output
        second_version = re.search(r"version: (v[0-9a-f]+)", second.output)
        assert second_version

        promote = runner.invoke(
            main,
            ["promote", second_version.group(1), "--to", "Candidate"],
        )
        assert promote.exit_code == 0, promote.output

        diff = runner.invoke(
            main,
            ["diff", first_version.group(1), second_version.group(1)],
        )
        assert diff.exit_code == 0, diff.output
        assert "recipe_hash: unchanged" in diff.output
        assert "manifest_hash: unchanged" in diff.output
        assert "review_state: Exploring->Candidate" in diff.output
        assert "retention_state: unchanged" in diff.output
        assert "added: 0" in diff.output
        assert "removed: 0" in diff.output
        assert "modified: 0" in diff.output
        assert "input_changes: added=0 removed=0 modified=0" in diff.output
        assert "output_changes: added=0 removed=0 modified=0" in diff.output
    finally:
        os.chdir(old_cwd)


def test_audit_verify_detects_tampered_event(tmp_path: Path) -> None:
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
                "--message",
                "audit snapshot",
            ],
        )
        assert commit.exit_code == 0, commit.output

        config, _ = find_config(workspace)
        with sqlite3.connect(config.metadata_db) as conn:
            conn.execute(
                "UPDATE audit_events SET payload_json = ? WHERE id = 1",
                ('{"tampered":true}',),
            )

        verify = runner.invoke(main, ["audit", "verify", "--full"])
        assert verify.exit_code != 0
        assert "integrity: failed" in verify.output
        assert "broken 1: event_hash mismatch" in verify.output
    finally:
        os.chdir(old_cwd)


def test_run_creates_and_releases_managed_lease(tmp_path: Path) -> None:
    runner = CliRunner()
    repo_root = tmp_path / "data" / "DemoChip"
    workspace = repo_root / "user" / "alice" / "APR"
    _write(workspace / "inputs" / "top.v", "module top; endmodule\n")
    assert runner.invoke(
        main, ["repo", "init", str(repo_root), "--repo-id", "DemoChip"]
    ).exit_code == 0

    old_cwd = Path.cwd()
    try:
        os.chdir(workspace)
        result = runner.invoke(
            main,
            [
                "run",
                "--",
                sys.executable,
                "-c",
                "print('managed ok')",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "lease: l" in result.output
        assert "branch: workspace/default/alice/APR" in result.output
        assert "workspace: user/alice/APR" in result.output
        assert "managed ok" in result.output
        assert "exit_code: 0" in result.output
        assert "lease_status: released" in result.output
        assert list((repo_root / ".big" / "leases").glob("*.json")) == []
    finally:
        os.chdir(old_cwd)


def test_branch_acl_grant_show_and_inherit(tmp_path: Path) -> None:
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
                "--message",
                "acl base",
            ],
        )
        assert commit.exit_code == 0, commit.output
        commit_version = re.search(r"version: (v[0-9a-f]+)", commit.output)
        assert commit_version

        create = runner.invoke(main, ["branch", "create", "feature/acl"])
        assert create.exit_code == 0, create.output
        assert "acl_source: default-current-identity" in create.output
        owner_group = re.search(r"owner_group: (group:[^\r\n]+)", create.output)
        assert owner_group
        assert f"read_groups: {owner_group.group(1)}" in create.output
        assert f"write_groups: {owner_group.group(1)}" in create.output

        show_effective = runner.invoke(
            main, ["branch", "acl", "show", "feature/acl", "--effective"]
        )
        assert show_effective.exit_code == 0, show_effective.output
        assert f"owner_group: {owner_group.group(1)}" in show_effective.output
        assert "write_implies_read: yes" in show_effective.output
        assert "effective_read: yes" in show_effective.output
        assert "effective_write: yes" in show_effective.output

        outsider_env = {
            "BIG_IDENTITY_USER": "mallory",
            "BIG_IDENTITY_GROUPS": "outsiders",
        }
        denied_show = runner.invoke(
            main, ["branch", "show", "feature/acl"], env=outsider_env
        )
        assert denied_show.exit_code != 0
        assert "Permission denied: read access to branch feature/acl" in denied_show.output

        denied_checkout = runner.invoke(
            main, ["checkout", "feature/acl", "--plan"], env=outsider_env
        )
        assert denied_checkout.exit_code != 0
        assert (
            "Permission denied: read access to branch feature/acl"
            in denied_checkout.output
        )

        outsider_branch_list = runner.invoke(
            main, ["branch", "list"], env=outsider_env
        )
        assert outsider_branch_list.exit_code == 0, outsider_branch_list.output
        assert "main" in outsider_branch_list.output
        assert "feature/acl" not in outsider_branch_list.output
        assert "restricted: 1" in outsider_branch_list.output

        denied_lifecycle_events = runner.invoke(
            main,
            ["lifecycle", "events", commit_version.group(1)],
            env=outsider_env,
        )
        assert denied_lifecycle_events.exit_code != 0
        assert (
            "Permission denied: read access to branch workspace/default/alice/APR"
            in denied_lifecycle_events.output
        )

        missing_permission = runner.invoke(
            main, ["branch", "acl", "grant", "feature/acl", "--group", "apr_team"]
        )
        assert missing_permission.exit_code != 0
        assert "ACL grant requires --read or --write" in missing_permission.output

        grant_read = runner.invoke(
            main,
            [
                "branch",
                "acl",
                "grant",
                "feature/acl",
                "--group",
                "apr_team",
                "--read",
            ],
        )
        assert grant_read.exit_code == 0, grant_read.output
        assert "group: group:apr_team" in grant_read.output
        assert "granted_read: yes" in grant_read.output
        assert "granted_write: no" in grant_read.output
        assert "group:apr_team" in grant_read.output

        apr_read_env = {
            "BIG_IDENTITY_USER": "mallory",
            "BIG_IDENTITY_GROUPS": "apr_team",
        }
        allowed_show = runner.invoke(
            main, ["branch", "show", "feature/acl"], env=apr_read_env
        )
        assert allowed_show.exit_code == 0, allowed_show.output
        assert "branch: feature/acl" in allowed_show.output

        allowed_checkout_plan = runner.invoke(
            main, ["checkout", "feature/acl", "--plan"], env=apr_read_env
        )
        assert allowed_checkout_plan.exit_code == 0, allowed_checkout_plan.output
        assert "materialization: plan-only" in allowed_checkout_plan.output

        denied_acl_grant = runner.invoke(
            main,
            [
                "branch",
                "acl",
                "grant",
                "feature/acl",
                "--group",
                "pv_team",
                "--read",
            ],
            env=apr_read_env,
        )
        assert denied_acl_grant.exit_code != 0
        assert "Permission denied: write access to branch feature/acl" in denied_acl_grant.output

        denied_commit = runner.invoke(
            main,
            [
                "commit",
                "--branch",
                "feature/acl",
                "--step",
                "place",
                "--inputs",
                "inputs/**",
                "--outputs",
                "outputs/**",
                "--message",
                "unauthorized write",
            ],
            env=apr_read_env,
        )
        assert denied_commit.exit_code != 0
        assert "Permission denied: write access to branch feature/acl" in denied_commit.output

        grant_write = runner.invoke(
            main,
            [
                "branch",
                "acl",
                "grant",
                "feature/acl",
                "--group",
                "apr_team",
                "--write",
            ],
        )
        assert grant_write.exit_code == 0, grant_write.output
        assert "granted_read: yes" in grant_write.output
        assert "granted_write: yes" in grant_write.output
        assert "write_groups:" in grant_write.output
        assert "group:apr_team" in grant_write.output

        create_child = runner.invoke(
            main, ["branch", "create", "feature/acl-child", "--from", "feature/acl"]
        )
        assert create_child.exit_code == 0, create_child.output
        assert "acl_source: feature/acl" in create_child.output
        assert "group:apr_team" in create_child.output

        child_acl = runner.invoke(
            main, ["branch", "acl", "show", "feature/acl-child"]
        )
        assert child_acl.exit_code == 0, child_acl.output
        assert f"owner_group: {owner_group.group(1)}" in child_acl.output
        assert "group:apr_team" in child_acl.output

        branch_show = runner.invoke(main, ["branch", "show", "feature/acl-child"])
        assert branch_show.exit_code == 0, branch_show.output
        assert "owner_group:" in branch_show.output
        assert "read_groups:" in branch_show.output
        assert "write_groups:" in branch_show.output

        audit_verify = runner.invoke(main, ["audit", "verify"])
        assert audit_verify.exit_code == 0, audit_verify.output
        assert "events: 5" in audit_verify.output
        assert "integrity: ok" in audit_verify.output
    finally:
        os.chdir(old_cwd)


def test_branch_create_can_apply_acl_template_from_config(tmp_path: Path) -> None:
    runner = CliRunner()
    repo_root = tmp_path / "data" / "DemoChip"
    workspace = repo_root / "user" / "alice" / "APR"
    _write(workspace / "inputs" / "top.v", "module top; endmodule\n")
    _write(workspace / "outputs" / "top.def", "VERSION 5.8 ;\n")
    assert runner.invoke(
        main, ["repo", "init", str(repo_root), "--repo-id", "DemoChip"]
    ).exit_code == 0
    config_path = repo_root / "big.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8")
        + """

[[acl_templates]]
name = "apr"
owner_group = "group:apr_leads"
read_groups = ["group:apr_read"]
write_groups = ["group:apr_write"]

[[acl_templates]]
name = "bad"
owner_group = "apr_leads"
""",
        encoding="utf-8",
    )

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
                "--message",
                "acl template base",
            ],
        )
        assert commit.exit_code == 0, commit.output

        create = runner.invoke(
            main, ["branch", "create", "feature/apr", "--acl-template", "apr"]
        )
        assert create.exit_code == 0, create.output
        assert "acl_source: template:apr" in create.output
        assert "owner_group: group:apr_leads" in create.output
        assert "read_groups: group:apr_read,group:apr_write" in create.output
        assert "write_groups: group:apr_write" in create.output

        apr_read_env = {
            "BIG_IDENTITY_USER": "mallory",
            "BIG_IDENTITY_GROUPS": "apr_read",
        }
        allowed_show = runner.invoke(
            main, ["branch", "show", "feature/apr"], env=apr_read_env
        )
        assert allowed_show.exit_code == 0, allowed_show.output

        denied_commit = runner.invoke(
            main,
            [
                "commit",
                "--branch",
                "feature/apr",
                "--step",
                "place",
                "--inputs",
                "inputs/**",
                "--outputs",
                "outputs/**",
                "--message",
                "read group cannot write",
            ],
            env=apr_read_env,
        )
        assert denied_commit.exit_code != 0
        assert "Permission denied: write access to branch feature/apr" in denied_commit.output

        missing = runner.invoke(
            main, ["branch", "create", "feature/missing", "--acl-template", "missing"]
        )
        assert missing.exit_code != 0
        assert "ACL template not found: missing" in missing.output

        bad = runner.invoke(
            main, ["branch", "create", "feature/bad", "--acl-template", "bad"]
        )
        assert bad.exit_code != 0
        assert "ACL template bad group must use group:<name>: apr_leads" in bad.output

        audit_verify = runner.invoke(main, ["audit", "verify"])
        assert audit_verify.exit_code == 0, audit_verify.output
        assert "events: 2" in audit_verify.output
        assert "integrity: ok" in audit_verify.output
    finally:
        os.chdir(old_cwd)


def test_acl_group_validation_uses_linux_group_resolver(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class FakeGroup:
        def __init__(self, name: str) -> None:
            self.gr_name = name

    class FakeGrp:
        def __init__(self, known_groups: set[str]) -> None:
            self.known_groups = known_groups

        def getgrnam(self, name: str) -> FakeGroup:
            if name not in self.known_groups:
                raise KeyError(name)
            return FakeGroup(name)

        def getgrgid(self, gid: int) -> FakeGroup:
            return FakeGroup("apr_write")

    monkeypatch.setattr(
        cli_module,
        "grp",
        FakeGrp({"apr_leads", "apr_read", "apr_write"}),
    )

    runner = CliRunner()
    repo_root = tmp_path / "data" / "DemoChip"
    workspace = repo_root / "user" / "alice" / "APR"
    _write(workspace / "inputs" / "top.v", "module top; endmodule\n")
    _write(workspace / "outputs" / "top.def", "VERSION 5.8 ;\n")
    assert runner.invoke(
        main, ["repo", "init", str(repo_root), "--repo-id", "DemoChip"]
    ).exit_code == 0
    config_path = repo_root / "big.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8")
        + """

[acl]
validate_groups = true

[[acl_templates]]
name = "apr"
owner_group = "group:apr_leads"
read_groups = ["group:apr_read"]
write_groups = ["group:apr_write"]

[[acl_templates]]
name = "missing"
owner_group = "group:no_such_group"
""",
        encoding="utf-8",
    )

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
                "--message",
                "acl validation base",
            ],
        )
        assert commit.exit_code == 0, commit.output

        create = runner.invoke(
            main, ["branch", "create", "feature/apr", "--acl-template", "apr"]
        )
        assert create.exit_code == 0, create.output
        assert "acl_source: template:apr" in create.output

        missing_template = runner.invoke(
            main, ["branch", "create", "feature/missing", "--acl-template", "missing"]
        )
        assert missing_template.exit_code != 0
        assert (
            "ACL template missing references unresolved Linux group: "
            "group:no_such_group"
        ) in missing_template.output

        missing_grant = runner.invoke(
            main,
            [
                "branch",
                "acl",
                "grant",
                "feature/apr",
                "--group",
                "no_such_group",
                "--read",
            ],
        )
        assert missing_grant.exit_code != 0
        assert "Unresolved Linux group: group:no_such_group" in missing_grant.output

        audit_verify = runner.invoke(main, ["audit", "verify"])
        assert audit_verify.exit_code == 0, audit_verify.output
        assert "events: 2" in audit_verify.output
        assert "integrity: ok" in audit_verify.output
    finally:
        os.chdir(old_cwd)


def test_restore_in_place_rewrites_clean_workspace_with_journal(
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    repo_root = tmp_path / "data" / "DemoChip"
    workspace = repo_root / "user" / "alice" / "APR"
    top_v1 = "module top; endmodule\n"
    def_v1 = "VERSION 5.8 ;\n"
    top_v2 = "module top; wire a; endmodule\n"
    def_v2 = "VERSION 5.8 ;\nCOMPONENTS 1 ;\n"
    _write(workspace / "inputs" / "top.v", top_v1)
    _write(workspace / "scripts" / "place.tcl", "place_design\n")
    _write(workspace / "outputs" / "top.def", def_v1)
    _write(workspace / "reports" / "place.rpt", "wns 0.01\n")
    assert runner.invoke(
        main, ["repo", "init", str(repo_root), "--repo-id", "DemoChip"]
    ).exit_code == 0

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
                "restore base",
            ],
        )
        assert first.exit_code == 0, first.output
        first_version = re.search(r"version: (v[0-9a-f]+)", first.output)
        assert first_version

        _write(workspace / "inputs" / "top.v", top_v2)
        _write(workspace / "outputs" / "top.def", def_v2)
        second = runner.invoke(
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
                "restore modified",
            ],
        )
        assert second.exit_code == 0, second.output
        second_version = re.search(r"version: (v[0-9a-f]+)", second.output)
        assert second_version

        missing_flag = runner.invoke(main, ["restore", first_version.group(1)])
        assert missing_flag.exit_code != 0
        assert "restore requires explicit --in-place" in missing_flag.output

        plan = runner.invoke(
            main, ["restore", first_version.group(1), "--in-place", "--plan"]
        )
        assert plan.exit_code == 0, plan.output
        assert f"current_head: {second_version.group(1)}" in plan.output
        assert f"target_version: {first_version.group(1)}" in plan.output
        assert "generation_current: 0" in plan.output
        assert "generation_next: 1" in plan.output
        assert "dirty: no" in plan.output
        assert "active_lease_check: ok" in plan.output
        assert "quiet_state: required" in plan.output
        assert "add: 0" in plan.output
        assert "overwrite: 2" in plan.output
        assert "delete: 0" in plan.output
        assert "keep: 2" in plan.output
        assert "changed_files: 2" in plan.output
        assert "journal: plan-only" in plan.output
        assert "materialization: plan-only" in plan.output
        assert (workspace / "inputs" / "top.v").read_text(encoding="utf-8") == top_v2

        lease_dir = repo_root / ".big" / "leases"
        lease_dir.mkdir(parents=True, exist_ok=True)
        active_lease = {
            "schema": 1,
            "lease_id": "ltestactive",
            "repo_id": "DemoChip",
            "branch": "workspace/default/alice/APR",
            "workspace_id": "user/alice/APR",
            "workspace_path": str(workspace),
            "actor": "alice",
            "host": "test-host",
            "child_pid": 12345,
            "command": ["pds_innovus", "place"],
            "started_at": "2026-06-14T00:00:00+00:00",
            "status": "active",
        }
        (lease_dir / "ltestactive.json").write_text(
            json.dumps(active_lease, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        blocked_by_lease = runner.invoke(
            main, ["restore", first_version.group(1), "--in-place", "--plan"]
        )
        assert blocked_by_lease.exit_code != 0
        assert "active_lease_check: failed" in blocked_by_lease.output
        assert "active_leases: 1" in blocked_by_lease.output
        assert "ltestactive" in blocked_by_lease.output
        assert "command=pds_innovus place" in blocked_by_lease.output
        assert "Active managed lease exists" in blocked_by_lease.output
        (lease_dir / "ltestactive.json").unlink()

        no_confirm = runner.invoke(
            main, ["restore", first_version.group(1), "--in-place"]
        )
        assert no_confirm.exit_code != 0
        assert "materialization: confirmation-required" in no_confirm.output
        assert "requires --confirm RESTORE" in no_confirm.output

        _write(workspace / "inputs" / "top.v", "module top; wire dirty; endmodule\n")
        dirty = runner.invoke(
            main,
            [
                "restore",
                first_version.group(1),
                "--in-place",
                "--confirm",
                "RESTORE",
            ],
        )
        assert dirty.exit_code != 0
        assert "dirty: yes" in dirty.output
        assert "modified input inputs/top.v" in dirty.output
        _write(workspace / "inputs" / "top.v", top_v2)

        restored = runner.invoke(
            main,
            [
                "restore",
                first_version.group(1),
                "--in-place",
                "--confirm",
                "RESTORE",
            ],
        )
        assert restored.exit_code == 0, restored.output
        assert "materialization: restored" in restored.output
        assert "restore: completed" in restored.output
        assert (
            f"branch_head: {second_version.group(1)}->{first_version.group(1)}"
            in restored.output
        )
        journal = re.search(r"journal: (r[0-9a-f]+)", restored.output)
        assert journal
        assert (workspace / "inputs" / "top.v").read_text(encoding="utf-8") == top_v1
        assert (workspace / "outputs" / "top.def").read_text(encoding="utf-8") == def_v1

        state = json.loads(
            (workspace / ".big-workspace.json").read_text(encoding="utf-8")
        )
        assert state["generation"] == 1
        assert state["restored_from"] == first_version.group(1)
        assert state["restore_journal_id"] == journal.group(1)

        journal_path = (
            repo_root / ".big" / "restore-journals" / f"{journal.group(1)}.json"
        )
        journal_data = json.loads(journal_path.read_text(encoding="utf-8"))
        assert journal_data["status"] == "completed"
        assert journal_data["target_version_id"] == first_version.group(1)
        assert len(journal_data["operations"]) == 2
        assert {item["status"] for item in journal_data["operations"]} == {"done"}

        status = runner.invoke(main, ["status"])
        assert status.exit_code == 0, status.output
        assert f"head: {first_version.group(1)}" in status.output
        assert "generation: 1" in status.output
        assert f"restored_from: {first_version.group(1)}" in status.output
        assert f"restore_journal: {journal.group(1)}" in status.output

        _write(workspace / "reports" / "place.rpt", "wns 0.02\n")
        post_restore_commit = runner.invoke(
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
                "continue after restore",
            ],
        )
        assert post_restore_commit.exit_code == 0, post_restore_commit.output
        post_restore_version = re.search(
            r"version: (v[0-9a-f]+)", post_restore_commit.output
        )
        assert post_restore_version
        assert f"restored_from: {first_version.group(1)}" in post_restore_commit.output
        assert f"restore_journal: {journal.group(1)}" in post_restore_commit.output
        assert "workspace_generation: 1" in post_restore_commit.output

        config, _ = find_config(workspace)
        post_record = SQLiteMetadataRepository(config.metadata_db).get_version(
            post_restore_version.group(1)
        )
        assert post_record is not None
        assert post_record.parent_id == first_version.group(1)
        assert post_record.derived_from_version_id == first_version.group(1)
        assert post_record.restored_from_version_id == first_version.group(1)
        assert post_record.restore_journal_id == journal.group(1)
        assert post_record.workspace_generation == 1

        post_show = runner.invoke(main, ["show", post_restore_version.group(1)])
        assert post_show.exit_code == 0, post_show.output
        assert f"derived_from: {first_version.group(1)}" in post_show.output
        assert f"restored_from: {first_version.group(1)}" in post_show.output
        assert f"restore_journal: {journal.group(1)}" in post_show.output
        assert "workspace_generation: 1" in post_show.output

        status_after_commit = runner.invoke(main, ["status"])
        assert status_after_commit.exit_code == 0, status_after_commit.output
        assert f"head: {post_restore_version.group(1)}" in status_after_commit.output
        assert f"head_restored_from: {first_version.group(1)}" in status_after_commit.output
        assert f"head_restore_journal: {journal.group(1)}" in status_after_commit.output

        branch_show = runner.invoke(main, ["branch", "show", "workspace/default/alice/APR"])
        assert branch_show.exit_code == 0, branch_show.output
        assert f"head_restored_from: {first_version.group(1)}" in branch_show.output
        assert f"head_restore_journal: {journal.group(1)}" in branch_show.output

        log = runner.invoke(main, ["log"])
        assert log.exit_code == 0, log.output
        assert post_restore_version.group(1) in log.output
        assert first_version.group(1) in log.output
        assert second_version.group(1) not in log.output

        log_verbose = runner.invoke(main, ["log", "--verbose"])
        assert log_verbose.exit_code == 0, log_verbose.output
        assert f"  derived_from: {first_version.group(1)}" in log_verbose.output
        assert f"  restored_from: {first_version.group(1)}" in log_verbose.output
        assert f"  restore_journal: {journal.group(1)}" in log_verbose.output

        lineage = runner.invoke(main, ["lineage", post_restore_version.group(1)])
        assert lineage.exit_code == 0, lineage.output
        assert f"derived_from: {first_version.group(1)}" in lineage.output
        assert f"restored_from: {first_version.group(1)}" in lineage.output
        assert f"restore_journal: {journal.group(1)}" in lineage.output

        branch_events = runner.invoke(main, ["branch", "events"])
        assert branch_events.exit_code == 0, branch_events.output
        assert "restore workspace/default/alice/APR" in branch_events.output
        assert (
            f"{second_version.group(1)}->{first_version.group(1)}"
            in branch_events.output
        )

        audit_verify = runner.invoke(main, ["audit", "verify"])
        assert audit_verify.exit_code == 0, audit_verify.output
        assert "events: 4" in audit_verify.output
        assert "integrity: ok" in audit_verify.output

        audit_log = runner.invoke(main, ["audit", "log", "--limit", "5", "--full"])
        assert audit_log.exit_code == 0, audit_log.output
        assert f"commit version {post_restore_version.group(1)}" in audit_log.output
        assert "restore workspace user/alice/APR" in audit_log.output
        assert f'"restored_from_version_id":"{first_version.group(1)}"' in audit_log.output
        assert f'"restore_journal_id":"{journal.group(1)}"' in audit_log.output
    finally:
        os.chdir(old_cwd)


def test_recipe_only_checkout_materializes_inputs_only(tmp_path: Path) -> None:
    runner = CliRunner()
    repo_root = tmp_path / "data" / "DemoChip"
    workspace = repo_root / "user" / "alice" / "APR"
    _write(workspace / "inputs" / "top.v", "module top; endmodule\n")
    _write(workspace / "scripts" / "place.tcl", "place_design\n")
    _write(workspace / "outputs" / "top.def", "VERSION 5.8 ;\n")
    _write(workspace / "reports" / "place.rpt", "wns 0.01\n")
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
                "inputs/**;scripts/**",
                "--outputs",
                "outputs/**;reports/**",
                "--message",
                "recipe-only snapshot",
            ],
        )
        assert commit.exit_code == 0, commit.output
        version = re.search(r"version: (v[0-9a-f]+)", commit.output)
        assert version

        missing_confirm = runner.invoke(
            main, ["lifecycle", "degrade", version.group(1), "--to", "recipe_only"]
        )
        assert missing_confirm.exit_code != 0
        assert "requires --confirm RECIPE_ONLY" in missing_confirm.output

        degrade = runner.invoke(
            main,
            [
                "lifecycle",
                "degrade",
                version.group(1),
                "--to",
                "recipe_only",
                "--confirm",
                "RECIPE_ONLY",
                "--gc-outputs",
                "--message",
                "retire outputs",
            ],
        )
        assert degrade.exit_code == 0, degrade.output
        assert "old_state: [Exploring/resident]" in degrade.output
        assert "new_state: [Exploring/recipe_only]" in degrade.output
        assert "degrade: moved" in degrade.output
        assert "physical_gc: reclaimed" in degrade.output
        assert "gc_candidates: 2" in degrade.output
        assert "gc_objects: 2" in degrade.output
        assert "gc_skipped_shared: 0" in degrade.output

        show = runner.invoke(main, ["show", version.group(1)])
        assert show.exit_code == 0, show.output
        assert "state: [Exploring/recipe_only]" in show.output

        verify = runner.invoke(main, ["verify", version.group(1)])
        assert verify.exit_code == 0, verify.output
        assert "required_files: 2" in verify.output
        assert "optional_outputs: 2" in verify.output
        assert "reclaimed_outputs: 2" in verify.output
        assert "integrity: ok" in verify.output

        repo_verify = runner.invoke(main, ["repo", "verify"])
        assert repo_verify.exit_code == 0, repo_verify.output
        assert "required_file_refs: 2" in repo_verify.output
        assert "optional_outputs: 2" in repo_verify.output
        assert "reclaimed_outputs: 2" in repo_verify.output
        assert "integrity: ok" in repo_verify.output

        lifecycle_events = runner.invoke(
            main, ["lifecycle", "events", version.group(1)]
        )
        assert lifecycle_events.exit_code == 0, lifecycle_events.output
        assert "Exploring->Exploring" in lifecycle_events.output
        assert "resident->recipe_only" in lifecycle_events.output
        assert "retire outputs" in lifecycle_events.output

        branch = runner.invoke(main, ["branch", "create", "recipe/only"])
        assert branch.exit_code == 0, branch.output
        assert "branch: recipe/only" in branch.output

        plan = runner.invoke(main, ["checkout", "recipe/only", "--plan"])
        assert plan.exit_code == 0, plan.output
        assert "retention: recipe_only" in plan.output
        assert "checkout_scope: inputs-only" in plan.output
        assert "omitted_outputs: 2" in plan.output
        assert "files: 2" in plan.output
        assert "materialization: plan-only" in plan.output
        target_path = (
            workspace.parent
            / ".big-checkouts"
            / "APR"
            / "recipe__only"
            / version.group(1)
        )
        assert f"target_path: {target_path}" in plan.output
        assert not target_path.exists()

        checkout = runner.invoke(main, ["checkout", "recipe/only"])
        assert checkout.exit_code == 0, checkout.output
        assert "retention: recipe_only" in checkout.output
        assert "checkout_scope: inputs-only" in checkout.output
        assert "omitted_outputs: 2" in checkout.output
        assert "files: 2" in checkout.output
        assert "materialization: partial" in checkout.output
        assert (target_path / "inputs" / "top.v").exists()
        assert (target_path / "scripts" / "place.tcl").exists()
        assert not (target_path / "outputs" / "top.def").exists()
        assert not (target_path / "reports" / "place.rpt").exists()
        marker = json.loads(
            (target_path / ".big-checkout.json").read_text(encoding="utf-8")
        )
        assert marker["materialization"] == "partial"
        assert marker["omitted_outputs"] == 2
        assert marker["files"] == 2

        checkout_again = runner.invoke(main, ["checkout", "recipe/only"])
        assert checkout_again.exit_code == 0, checkout_again.output
        assert "materialization: reused" in checkout_again.output

        os.chdir(target_path)
        status = runner.invoke(main, ["status"])
        assert status.exit_code == 0, status.output
        assert "default_ref: recipe/only" in status.output
        assert f"head: {version.group(1)}" in status.output
        assert "head_state: [Exploring/recipe_only]" in status.output

        audit_verify = runner.invoke(main, ["audit", "verify"])
        assert audit_verify.exit_code == 0, audit_verify.output
        assert "events: 3" in audit_verify.output
        assert "integrity: ok" in audit_verify.output

        audit_log = runner.invoke(main, ["audit", "log", "--limit", "5"])
        assert audit_log.exit_code == 0, audit_log.output
        assert f"degrade version {version.group(1)}" in audit_log.output
        assert "create_branch branch recipe/only" in audit_log.output
    finally:
        os.chdir(old_cwd)


def test_commit_require_marker_checks_configured_success_marker(
    tmp_path: Path,
) -> None:
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
        missing_config = runner.invoke(
            main,
            [
                "commit",
                "--step",
                "place",
                "--inputs",
                "inputs/**",
                "--outputs",
                "outputs/**",
                "--require-marker",
            ],
        )
        assert missing_config.exit_code != 0
        assert "No step success marker configured" in missing_config.output

        config_path = repo_root / "big.toml"
        config_path.write_text(
            config_path.read_text(encoding="utf-8")
            + '\n[step_markers]\nsuccess = "../markers/{flow}/{step}.done"\n',
            encoding="utf-8",
        )

        missing_marker = runner.invoke(
            main,
            [
                "commit",
                "--step",
                "place",
                "--inputs",
                "inputs/**",
                "--outputs",
                "outputs/**",
                "--require-marker",
            ],
        )
        assert missing_marker.exit_code != 0
        assert "configured step success marker not found" in missing_marker.output
        marker_path = repo_root / "user" / "alice" / "markers" / "APR" / "place.done"
        assert str(marker_path) in missing_marker.output

        _write(marker_path, "ok\n")
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
                "--require-marker",
            ],
        )
        assert commit.exit_code == 0, commit.output
        assert "success_marker: found" in commit.output
        assert (
            f"success_marker_path: {marker_path}"
            in commit.output
        )
        assert "capture_mode: best_effort" in commit.output

        log = runner.invoke(main, ["log"])
        assert log.exit_code == 0, log.output
        assert len(re.findall(r"^v[0-9a-f]+ ", log.output, re.MULTILINE)) == 1
    finally:
        os.chdir(old_cwd)


def test_commit_settle_window_rejects_changed_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runner = CliRunner()
    repo_root = tmp_path / "data" / "DemoChip"
    workspace = repo_root / "user" / "alice" / "APR"
    _write(workspace / "inputs" / "top.v", "module top; endmodule\n")
    _write(workspace / "outputs" / "top.def", "VERSION 5.8 ;\n")
    assert runner.invoke(
        main, ["repo", "init", str(repo_root), "--repo-id", "DemoChip"]
    ).exit_code == 0
    config_path = repo_root / "big.toml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8")
        + "\n[capture]\nsettle_ms = 25\n",
        encoding="utf-8",
    )

    old_cwd = Path.cwd()
    try:
        os.chdir(workspace)

        def mutate_during_settle(_seconds: float) -> None:
            _write(
                workspace / "inputs" / "top.v",
                "module top; wire changed; endmodule\n",
            )

        monkeypatch.setattr(cli_module.time, "sleep", mutate_during_settle)
        changed = runner.invoke(
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
        assert changed.exit_code != 0
        assert "Files changed during settle window (25 ms)" in changed.output
        assert "inputs/top.v" in changed.output
        assert "size" in changed.output

        monkeypatch.setattr(cli_module.time, "sleep", lambda _seconds: None)
        stable = runner.invoke(
            main,
            [
                "commit",
                "--step",
                "place",
                "--inputs",
                "inputs/**",
                "--outputs",
                "outputs/**",
                "--settle-ms",
                "1",
            ],
        )
        assert stable.exit_code == 0, stable.output
        assert "settle_ms: 1" in stable.output
        assert "capture_mode: best_effort" in stable.output

        log = runner.invoke(main, ["log"])
        assert log.exit_code == 0, log.output
        assert len(re.findall(r"^v[0-9a-f]+ ", log.output, re.MULTILINE)) == 1
    finally:
        os.chdir(old_cwd)


def test_shell_init_outputs_checkout_wrapper() -> None:
    runner = CliRunner()
    for shell in ("bash", "zsh"):
        result = runner.invoke(main, ["shell-init", shell])
        assert result.exit_code == 0, result.output
        assert f'eval "$(big shell-init {shell})"' in result.output
        assert "big() {" in result.output
        assert 'command big "$@"' in result.output
        assert "grep -q '^materialization: plan-only$'" in result.output
        assert "sed -n 's/^cd: cd -- //p'" in result.output
        assert 'cd -- "$__big_target"' in result.output


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


def test_commit_records_branch_source_as_derived_from(tmp_path: Path) -> None:
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
        base = runner.invoke(
            main,
            [
                "commit",
                "--step",
                "place",
                "--inputs",
                "inputs/**",
                "--outputs",
                "outputs/**",
                "--message",
                "base source",
            ],
        )
        assert base.exit_code == 0, base.output
        base_version = re.search(r"version: (v[0-9a-f]+)", base.output)
        assert base_version

        branch = runner.invoke(
            main,
            [
                "branch",
                "create",
                "experiment/from-v1",
                "--from",
                base_version.group(1),
            ],
        )
        assert branch.exit_code == 0, branch.output

        _write(workspace / "outputs" / "top.def", "VERSION 5.8 ;\nCOMPONENTS 1 ;\n")
        derived = runner.invoke(
            main,
            [
                "commit",
                "--branch",
                "experiment/from-v1",
                "--step",
                "place",
                "--inputs",
                "inputs/**",
                "--outputs",
                "outputs/**",
                "--message",
                "branch derived snapshot",
            ],
        )
        assert derived.exit_code == 0, derived.output
        derived_version = re.search(r"version: (v[0-9a-f]+)", derived.output)
        assert derived_version
        assert f"derived_from: {base_version.group(1)}" in derived.output

        config, _ = find_config(workspace)
        record = SQLiteMetadataRepository(config.metadata_db).get_version(
            derived_version.group(1)
        )
        assert record is not None
        assert record.parent_id == base_version.group(1)
        assert record.derived_from_version_id == base_version.group(1)
        assert record.restored_from_version_id == ""

        show = runner.invoke(main, ["show", derived_version.group(1)])
        assert show.exit_code == 0, show.output
        assert f"derived_from: {base_version.group(1)}" in show.output

        lineage = runner.invoke(main, ["lineage", derived_version.group(1)])
        assert lineage.exit_code == 0, lineage.output
        assert f"derived_from: {base_version.group(1)}" in lineage.output
        assert "restored_from:" not in lineage.output
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

        repo_verify = runner.invoke(main, ["repo", "verify", "--full"])
        assert repo_verify.exit_code != 0
        assert "repo: DemoChip" in repo_verify.output
        assert "versions: 1" in repo_verify.output
        assert "file_refs: 2" in repo_verify.output
        assert "integrity: failed" in repo_verify.output
        assert f"missing {version.group(1)} " in repo_verify.output
        assert "Repository CAS integrity verification failed" in repo_verify.output
    finally:
        os.chdir(old_cwd)


def test_recipe_only_verify_checks_existing_optional_outputs(tmp_path: Path) -> None:
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

        degrade = runner.invoke(
            main,
            [
                "lifecycle",
                "degrade",
                version.group(1),
                "--to",
                "recipe_only",
                "--confirm",
                "RECIPE_ONLY",
            ],
        )
        assert degrade.exit_code == 0, degrade.output
        assert "physical_gc: skipped" in degrade.output

        config, _ = find_config(workspace)
        metadata = SQLiteMetadataRepository(config.metadata_db)
        refs = metadata.get_file_refs(version.group(1))
        output_ref = next(ref for ref in refs if ref.role == "output")
        output_object = object_path(config.cas_dir, output_ref.cas_hash)
        output_object.chmod(0o666)
        output_object.write_text("corrupt optional output\n", encoding="utf-8")

        verify = runner.invoke(main, ["verify", version.group(1), "--full"])
        assert verify.exit_code != 0
        assert "optional_outputs: 1" in verify.output
        assert "reclaimed_outputs: 0" in verify.output
        assert "size_mismatch: 1" in verify.output
        assert "integrity: failed" in verify.output
        assert "CAS integrity verification failed" in verify.output

        repo_verify = runner.invoke(main, ["repo", "verify", "--full"])
        assert repo_verify.exit_code != 0
        assert "optional_outputs: 1" in repo_verify.output
        assert "reclaimed_outputs: 0" in repo_verify.output
        assert "size_mismatch: 1" in repo_verify.output
        assert "integrity: failed" in repo_verify.output
        assert "Repository CAS integrity verification failed" in repo_verify.output
    finally:
        os.chdir(old_cwd)
