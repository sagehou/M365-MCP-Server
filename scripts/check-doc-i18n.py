from __future__ import annotations

from pathlib import Path


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

    if errors:
        print("Documentation i18n check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Documentation i18n check passed for {len(iter_pairs())} bilingual document pairs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
