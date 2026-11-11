from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
ZH_ROOT = DOCS / "zh-CN"


def iter_pairs() -> list[tuple[Path, Path]]:
    pairs: list[tuple[Path, Path]] = [(ROOT / "README.md", ROOT / "README.zh-CN.md")]
    for english in sorted(DOCS.rglob("*.md")):
        relative = english.relative_to(DOCS)
        if relative.parts and relative.parts[0] == "zh-CN":
            continue
        pairs.append((english, ZH_ROOT / relative))
    return pairs


def missing_markdown_links(document: Path, text: str) -> list[str]:
    missing = []
    for target in re.findall(r"\]\(([^)\s]+)\)", text):
        url = urlsplit(target)
        if url.scheme or url.netloc:
            continue
        path = unquote(url.path)
        if path.endswith(".md") and not (document.parent / path).is_file():
            missing.append(target)
    return missing


def main() -> int:
    errors: list[str] = []
    for english, chinese in iter_pairs():
        if not chinese.exists():
            errors.append(f"missing Chinese translation: {chinese.relative_to(ROOT)}")
            continue

        english_text = english.read_text(encoding="utf-8")
        chinese_text = chinese.read_text(encoding="utf-8")
        if "简体中文" not in english_text:
            errors.append(f"missing Chinese language link: {english.relative_to(ROOT)}")
        if "English" not in chinese_text:
            errors.append(f"missing English language link: {chinese.relative_to(ROOT)}")

        for document, text in ((english, english_text), (chinese, chinese_text)):
            for target in missing_markdown_links(document, text):
                errors.append(
                    f"broken documentation link: {document.relative_to(ROOT)} -> {target}"
                )

    if errors:
        print("Documentation check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Documentation check passed for {len(iter_pairs())} bilingual pairs and their links.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
