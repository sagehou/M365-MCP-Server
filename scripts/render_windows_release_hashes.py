"""Add exact Windows release-asset hashes to GitHub Release notes."""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path


START = "<!-- windows-executable-hashes:start -->"
END = "<!-- windows-executable-hashes:end -->"


def calculate_hashes(binary: Path) -> dict[str, str]:
    digests = {
        "MD5": hashlib.md5(usedforsecurity=False),
        "SHA-1": hashlib.sha1(usedforsecurity=False),
        "SHA-256": hashlib.sha256(),
    }
    with binary.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            for digest in digests.values():
                digest.update(chunk)
    return {name: digest.hexdigest() for name, digest in digests.items()}


def verify_sha256_file(checksum_file: Path, binary: Path, actual: str) -> None:
    records = [line.split() for line in checksum_file.read_text(encoding="ascii").splitlines()]
    matches = [fields for fields in records if len(fields) == 2 and fields[1] == binary.name]
    if (
        len(matches) != 1
        or not re.fullmatch(r"[0-9a-fA-F]{64}", matches[0][0])
        or matches[0][0].lower() != actual
    ):
        raise ValueError("SHA-256 checksum file does not match the exact release asset")


def update_notes(
    notes: str, release_tag: str, executables: list[tuple[Path, dict[str, str]]]
) -> str:
    tables = []
    for binary, hashes in executables:
        tables.extend([
            f"### `{binary.name}`",
            "",
            "| Algorithm | Hash |",
            "| --- | --- |",
            *(f"| {name} | `{value}` |" for name, value in hashes.items()),
            "",
        ])
    section = "\n".join(
        [
            START,
            f"## Windows executable hashes ({release_tag})",
            "",
            *tables,
            END,
        ]
    )
    if notes.count(START) != notes.count(END) or notes.count(START) > 1:
        raise ValueError("Release notes contain malformed Windows hash markers")
    if START in notes:
        before, remainder = notes.split(START, 1)
        _, after = remainder.split(END, 1)
        notes = before.rstrip() + after
    if "\n---\n" in notes:
        body, footer = notes.rsplit("\n---\n", 1)
        return body.rstrip() + "\n\n" + section + "\n\n---\n" + footer
    return notes.rstrip() + "\n\n" + section + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True, action="append")
    parser.add_argument("--sha256-file", type=Path, required=True, action="append")
    parser.add_argument("--notes-in", type=Path, required=True)
    parser.add_argument("--notes-out", type=Path, required=True)
    parser.add_argument("--release-tag", required=True)
    parser.add_argument("--expected-sha256")
    args = parser.parse_args()

    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", args.release_tag):
        parser.error("release tag must be vMAJOR.MINOR.PATCH")
    if len(args.binary) != len(args.sha256_file):
        parser.error("each binary needs its own --sha256-file argument")
    names = [binary.name for binary in args.binary]
    if len(names) != len(set(names)):
        parser.error("duplicate Windows release asset")
    if args.expected_sha256 and len(args.binary) != 1:
        parser.error("--expected-sha256 requires exactly one binary")

    executables = []
    for binary, checksum in zip(args.binary, args.sha256_file, strict=True):
        if not re.fullmatch(r"m365-mcp-windows-(?:x64|local(?:-go)?-(?:amd64|arm64))\.exe", binary.name):
            parser.error("unexpected Windows release asset name")
        hashes = calculate_hashes(binary)
        verify_sha256_file(checksum, binary, hashes["SHA-256"])
        if args.expected_sha256 and hashes["SHA-256"] != args.expected_sha256.lower():
            raise ValueError("Release asset differs from the expected published SHA-256")
        executables.append((binary, hashes))

    notes = args.notes_in.read_text(encoding="utf-8")
    updated = update_notes(notes, args.release_tag, executables)
    args.notes_out.write_text(updated, encoding="utf-8", newline="\n")
    for binary, hashes in executables:
        for name, value in hashes.items():
            print(f"{binary.name} {name}: {value}")


if __name__ == "__main__":
    main()
