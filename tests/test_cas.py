from __future__ import annotations

from pathlib import Path
import stat

from big.cas import object_path, publish_object, sha256_file


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _is_user_writable(path: Path) -> bool:
    return bool(path.stat().st_mode & stat.S_IWUSR)


def test_publish_object_makes_new_cas_object_readonly(tmp_path: Path) -> None:
    staged = tmp_path / "staging" / "top.v"
    _write(staged, "module top; endmodule\n")
    expected_hash = sha256_file(staged)

    published = publish_object(tmp_path / "cas", staged, expected_hash)

    assert published == object_path(tmp_path / "cas", expected_hash)
    assert published.read_text(encoding="utf-8") == "module top; endmodule\n"
    assert not _is_user_writable(published)


def test_publish_object_rehardens_existing_valid_object(tmp_path: Path) -> None:
    first_staged = tmp_path / "staging" / "first.v"
    second_staged = tmp_path / "staging" / "second.v"
    _write(first_staged, "module top; endmodule\n")
    _write(second_staged, "module top; endmodule\n")
    expected_hash = sha256_file(first_staged)

    published = publish_object(tmp_path / "cas", first_staged, expected_hash)
    published.chmod(0o644)
    assert _is_user_writable(published)

    reused = publish_object(tmp_path / "cas", second_staged, expected_hash)

    assert reused == published
    assert not _is_user_writable(reused)
