from __future__ import annotations

from pathlib import Path

from tools.create_manual_lab import create_manual_lab


def test_create_manual_lab_is_idempotent(tmp_path: Path) -> None:
    root = tmp_path / "manual-lab" / "data" / "WslChip"
    written = create_manual_lab(root)

    assert len(written) == 12
    assert (root / "user" / "alice" / "APR" / "inputs" / "top.v").exists()
    assert (root / "user" / "shaqsnake" / "APR" / "inputs" / "top.v").exists()
    assert (root / "user" / "alice" / "APR" / "scripts" / "place.tcl").exists()
    assert (root / "user" / "alice" / "markers" / "APR" / "place.done").exists()
    assert create_manual_lab(root) == []


def test_create_manual_lab_can_overwrite_known_fixtures(tmp_path: Path) -> None:
    root = tmp_path / "manual-lab" / "data" / "WslChip"
    create_manual_lab(root)
    top = root / "user" / "alice" / "APR" / "inputs" / "top.v"
    top.write_text("changed\n", encoding="utf-8")

    written = create_manual_lab(root, overwrite=True)

    assert len(written) == 12
    assert top.read_text(encoding="utf-8") == "module top;\nendmodule\n"
