from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "render_windows_release_hashes.py"


def run_renderer(
    binary: Path, checksum: Path, notes_in: Path, notes_out: Path, *extra: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--binary",
            str(binary),
            "--sha256-file",
            str(checksum),
            "--notes-in",
            str(notes_in),
            "--notes-out",
            str(notes_out),
            "--release-tag",
            "v0.1.0",
            *extra,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_renders_exact_hashes_and_replaces_section_without_duplicates(tmp_path: Path) -> None:
    binary = tmp_path / "m365-mcp-windows-x64.exe"
    binary.write_bytes(b"example release asset")
    checksum = tmp_path / "m365-mcp-windows-x64.exe.sha256"
    sha256 = hashlib.sha256(binary.read_bytes()).hexdigest()
    checksum.write_text(f"{sha256}  {binary.name}", encoding="ascii")
    original = tmp_path / "original.md"
    original.write_text("# Existing release notes\n\nKeep this content.\n", encoding="utf-8")
    updated = tmp_path / "updated.md"

    first = run_renderer(binary, checksum, original, updated, "--expected-sha256", sha256)
    assert first.returncode == 0, first.stderr
    body = updated.read_text(encoding="utf-8")
    assert body.startswith("# Existing release notes\n\nKeep this content.")
    assert body.count("<!-- windows-executable-hashes:start -->") == 1
    assert body.count("<!-- windows-executable-hashes:end -->") == 1
    assert hashlib.md5(binary.read_bytes(), usedforsecurity=False).hexdigest() in body
    assert hashlib.sha1(binary.read_bytes(), usedforsecurity=False).hexdigest() in body
    assert sha256 in body

    rerendered = tmp_path / "rerendered.md"
    second = run_renderer(binary, checksum, updated, rerendered)
    assert second.returncode == 0, second.stderr
    assert rerendered.read_bytes() == updated.read_bytes()


def test_rejects_mismatched_published_binary(tmp_path: Path) -> None:
    binary = tmp_path / "m365-mcp-windows-x64.exe"
    binary.write_bytes(b"different artifact")
    checksum = tmp_path / "m365-mcp-windows-x64.exe.sha256"
    checksum.write_text(f"{'0' * 64}  {binary.name}", encoding="ascii")
    notes = tmp_path / "notes.md"
    notes.write_text("# Release\n", encoding="utf-8")
    output = tmp_path / "output.md"

    result = run_renderer(binary, checksum, notes, output)
    assert result.returncode != 0
    assert "SHA-256 checksum file does not match" in result.stderr
    assert not output.exists()


def test_rejects_changed_asset_even_when_checksum_file_matches(tmp_path: Path) -> None:
    binary = tmp_path / "m365-mcp-windows-x64.exe"
    binary.write_bytes(b"replacement artifact")
    checksum = tmp_path / "m365-mcp-windows-x64.exe.sha256"
    checksum.write_text(
        f"{hashlib.sha256(binary.read_bytes()).hexdigest()}  {binary.name}",
        encoding="ascii",
    )
    notes = tmp_path / "notes.md"
    notes.write_text("# Release\n", encoding="utf-8")
    output = tmp_path / "output.md"

    result = run_renderer(binary, checksum, notes, output, "--expected-sha256", "0" * 64)
    assert result.returncode != 0
    assert "differs from the expected published SHA-256" in result.stderr
    assert not output.exists()
