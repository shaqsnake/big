from __future__ import annotations

import argparse
from pathlib import Path


USERS = ("alice", "shaqsnake")

FIXTURE_TEMPLATES = {
    "user/{user}/APR/inputs/top.v": "module top;\nendmodule\n",
    "user/{user}/APR/inputs/floorplan.def": (
        "VERSION 5.8 ;\n"
        "DESIGN top ;\n"
        "END DESIGN\n"
    ),
    "user/{user}/APR/scripts/place.tcl": (
        "read_verilog inputs/top.v\n"
        "place_design\n"
    ),
    "user/{user}/APR/outputs/top_placed.def": (
        "VERSION 5.8 ;\n"
        "DESIGN top ;\n"
        "END DESIGN\n"
    ),
    "user/{user}/APR/reports/place.rpt": "WNS 0.01\nTNS 0.00\n",
}


def create_manual_lab(root: Path, overwrite: bool = False) -> list[Path]:
    written: list[Path] = []
    for user in USERS:
        for rel_path_template, content in FIXTURE_TEMPLATES.items():
            target = root / rel_path_template.format(user=user)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and not overwrite:
                continue
            target.write_text(content, encoding="utf-8")
            written.append(target)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a small EDA-like workspace for BIG manual testing."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("manual-lab/data/WslChip"),
        help="Project root to populate. Default: manual-lab/data/WslChip",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite known fixture files. Existing .big metadata is not removed.",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    written = create_manual_lab(root, overwrite=args.overwrite)
    workspace = root / "user" / "alice" / "APR"
    print(f"manual lab root: {root}")
    print(f"workspace: {workspace}")
    print(f"fixture files written: {len(written)}")


if __name__ == "__main__":
    main()
