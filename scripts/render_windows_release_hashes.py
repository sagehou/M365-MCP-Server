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
    fields = checksum_file.read_text(encoding="ascii").strip().split()
    if (
        len(fields) != 2
        or not re.fullmatch(r"[0-9a-fA-F]{64}", fields[0])
        or fields[1] != binary.name
        or fields[0].lower() != actual
    ):
        raise ValueError("SHA-256 checksum file does not match the exact release asset")


def update_notes(notes: str, release_tag: str, binary: Path, hashes: dict[str, str]) -> str:
    section = "\n".join(
        [
            START,
            f"## Windows executable hashes ({release_tag})",
            "",
            f"Exact release asset: `{binary.name}`. For exact-file antivirus allowlisting:",
            "",
            "| Algorithm | Hash |",
            "| --- | --- |",
            *(f"| {name} | `{value}` |" for name, value in hashes.items()),
            "",
            "MD5 and SHA-1 are provided for legacy allowlist forms only; they are not proof of authenticity. "
            "Verify the SHA-256 checksum and GitHub Artifact Attestation for provenance. "
            "A rebuilt or updated executable has different hashes and needs a new allowlist review.",
            END,
        ]
    )
    if notes.count(START) != notes.count(END) or notes.count(START) > 1:
        raise ValueError("Release notes contain malformed Windows hash markers")
    if START in notes:
        before, remainder = notes.split(START, 1)
        _, after = remainder.split(END, 1)
        return before.rstrip() + "\n\n" + section + after
    return notes.rstrip() + "\n\n" + section + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--sha256-file", type=Path, required=True)
    parser.add_argument("--notes-in", type=Path, required=True)
    parser.add_argument("--notes-out", type=Path, required=True)
    parser.add_argument("--release-tag", required=True)
    parser.add_argument("--expected-sha256")
    args = parser.parse_args()

    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", args.release_tag):
        parser.error("release tag must be vMAJOR.MINOR.PATCH")
    if args.binary.name != "m365-mcp-windows-x64.exe":
        parser.error("unexpected Windows release asset name")

    hashes = calculate_hashes(args.binary)
    verify_sha256_file(args.sha256_file, args.binary, hashes["SHA-256"])
    if args.expected_sha256 and hashes["SHA-256"] != args.expected_sha256.lower():
        raise ValueError("Release asset differs from the expected published SHA-256")

    notes = args.notes_in.read_text(encoding="utf-8")
    updated = update_notes(notes, args.release_tag, args.binary, hashes)
    args.notes_out.write_text(updated, encoding="utf-8", newline="\n")
    for name, value in hashes.items():
        print(f"{args.binary.name} {name}: {value}")


if __name__ == "__main__":
    main()
