import runpy
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check-doc-i18n.py"
missing_markdown_links = runpy.run_path(str(SCRIPT))["missing_markdown_links"]


def test_document_links_resolve_from_their_directory_and_report_missing_targets(
    tmp_path: Path,
) -> None:
    guides = tmp_path / "guides"
    guides.mkdir()
    (tmp_path / "README.md").write_text("# Project\n", encoding="utf-8")
    (guides / "local guide.md").write_text("# Local\n", encoding="utf-8")
    text = "\n".join([
        "[Project](../README.md)",
        "[Local](local%20guide.md#sign-in)",
        "[Missing translation](zh-CN/local.md#sign-in)",
        "[Web](https://example.com/missing.md)",
        "[Section](#sign-in)",
    ])

    assert missing_markdown_links(guides / "server.md", text) == [
        "zh-CN/local.md#sign-in"
    ]
