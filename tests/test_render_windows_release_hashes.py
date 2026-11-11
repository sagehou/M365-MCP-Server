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


def test_renders_all_editions_before_footer_and_replaces_old_hashes(tmp_path: Path) -> None:
    names = [
        "m365-mcp-windows-local-amd64.exe",
        "m365-mcp-windows-local-go-amd64.exe",
        "m365-mcp-windows-local-go-arm64.exe",
    ]
    binaries = [tmp_path / name for name in names]
    for binary in binaries:
        binary.write_bytes(binary.name.encode())
    checksum = tmp_path / "SHA256SUMS.txt"
    checksum.write_text("".join(
        f"{hashlib.sha256(binary.read_bytes()).hexdigest()}  {binary.name}\n"
        for binary in binaries
    ), encoding="ascii")
    notes = tmp_path / "notes.md"
    notes.write_text(
        "# Release\n\n---\nFooter notice.\n\n"
        "<!-- windows-executable-hashes:start -->\nOld hashes.\n"
        "<!-- windows-executable-hashes:end -->\n",
        encoding="utf-8",
    )
    output = tmp_path / "updated.md"
    extra = [
        argument
        for binary in binaries[1:]
        for argument in ("--binary", str(binary), "--sha256-file", str(checksum))
    ]
    result = run_renderer(binaries[0], checksum, notes, output, *extra)
    assert result.returncode == 0, result.stderr
    body = output.read_text(encoding="utf-8")
    assert "Old hashes." not in body
    assert body.count("<!-- windows-executable-hashes:start -->") == 1
    assert body.endswith("---\nFooter notice.\n")
    for binary in binaries:
        assert f"### `{binary.name}`" in body
        assert hashlib.md5(binary.read_bytes(), usedforsecurity=False).hexdigest() in body
        assert hashlib.sha1(binary.read_bytes(), usedforsecurity=False).hexdigest() in body
        assert hashlib.sha256(binary.read_bytes()).hexdigest() in body

    second = run_renderer(binaries[0], checksum, output, notes, *extra)
    assert second.returncode == 0, second.stderr
    assert notes.read_bytes() == output.read_bytes()


def test_rejects_incorrect_go_hash_before_writing_any_notes(tmp_path: Path) -> None:
    native = tmp_path / "m365-mcp-windows-local-amd64.exe"
    go = tmp_path / "m365-mcp-windows-local-go-amd64.exe"
    native.write_bytes(b"native release")
    go.write_bytes(b"go release")
    checksum = tmp_path / "SHA256SUMS.txt"
    checksum.write_text(
        f"{hashlib.sha256(native.read_bytes()).hexdigest()}  {native.name}\n"
        f"{'0' * 64}  {go.name}\n", encoding="ascii",
    )
    notes = tmp_path / "notes.md"
    notes.write_text("# Release\n", encoding="utf-8")
    output = tmp_path / "output.md"
    result = run_renderer(
        native, checksum, notes, output, "--binary", str(go), "--sha256-file", str(checksum),
    )
    assert result.returncode != 0
    assert "SHA-256 checksum file does not match" in result.stderr
    assert not output.exists()


def test_bilingual_release_contains_identical_hashes_and_one_footer(tmp_path: Path) -> None:
    binaries = [tmp_path / name for name in (
        "m365-mcp-windows-local-amd64.exe",
        "m365-mcp-windows-local-go-amd64.exe",
        "m365-mcp-windows-local-go-arm64.exe",
    )]
    for binary in binaries:
        binary.write_bytes(binary.name.encode())
    checksum = tmp_path / "SHA256SUMS.txt"
    checksum.write_text("".join(
        f"{hashlib.sha256(binary.read_bytes()).hexdigest()}  {binary.name}\n"
        for binary in binaries
    ), encoding="ascii")
    english = tmp_path / "english.md"
    english.write_text(
        "**English** | [简体中文](chinese.md)\n\n# Release\n\nEnglish notes.\n\n"
        "---\n\nEnglish notice. Updated: 2026-11-11.\n", encoding="utf-8",
    )
    chinese = tmp_path / "chinese.md"
    chinese.write_text(
        "[English](english.md) | **简体中文**\n\n# Release\n\n中文说明。\n\n"
        "---\n\n中文声明。更新日期：2026-11-11。\n", encoding="utf-8",
    )
    output = tmp_path / "bilingual.md"
    extra = ["--notes-zh-in", str(chinese)]
    for binary in binaries[1:]:
        extra.extend(("--binary", str(binary), "--sha256-file", str(checksum)))
    result = run_renderer(binaries[0], checksum, english, output, *extra)
    assert result.returncode == 0, result.stderr
    body = output.read_text(encoding="utf-8")
    assert body.startswith("# English\n\n")
    assert "[English](#english)" not in body and "[简体中文](#简体中文)" not in body
    assert "English notes." in body and "中文说明。" in body
    assert "english.md" not in body and "chinese.md" not in body
    assert body.count("| Algorithm | Hash |") == 3
    assert body.count("| 算法 | 哈希 |") == 3
    english_body, chinese_body = body.split("# 简体中文\n", 1)
    for binary in binaries:
        for section in (english_body, chinese_body):
            assert f"### `{binary.name}`" in section
            assert hashlib.md5(binary.read_bytes(), usedforsecurity=False).hexdigest() in section
            assert hashlib.sha1(binary.read_bytes(), usedforsecurity=False).hexdigest() in section
            assert hashlib.sha256(binary.read_bytes()).hexdigest() in section
    assert body.count("\n---\n") == 1
    assert body.count("2026-11-11") == 1
    assert body.endswith(
        "---\n\nEnglish notice.\n\n中文声明。\n\nUpdated / 更新日期：2026-11-11\n"
    )


def test_rejects_bilingual_notes_with_different_update_dates(tmp_path: Path) -> None:
    binary = tmp_path / "m365-mcp-windows-local-go-amd64.exe"
    binary.write_bytes(b"published release")
    checksum = tmp_path / "SHA256SUMS.txt"
    checksum.write_text(
        f"{hashlib.sha256(binary.read_bytes()).hexdigest()}  {binary.name}\n", encoding="ascii",
    )
    english = tmp_path / "english.md"
    english.write_text(
        "English | Chinese\n\n# Release\n\n---\nUpdated: 2026-11-11.\n", encoding="utf-8",
    )
    chinese = tmp_path / "chinese.md"
    chinese.write_text(
        "English | Chinese\n\n# Release\n\n---\n更新日期：2026-11-12。\n", encoding="utf-8",
    )
    output = tmp_path / "bilingual.md"
    result = run_renderer(
        binary, checksum, english, output, "--notes-zh-in", str(chinese),
    )
    assert result.returncode != 0
    assert "English and Chinese update dates differ" in result.stderr
    assert not output.exists()
