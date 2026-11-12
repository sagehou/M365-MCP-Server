import json
from pathlib import Path
import re
import shutil

from test_documentation import missing_markdown_links


ROOT = Path(__file__).resolve().parents[1]
CONNECTOR = ROOT / "workbuddy"
SKILL = CONNECTOR / "skills" / "m365-mail"


def _frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"---\r?\n(?P<body>.*?)\r?\n---\r?\n", text, re.DOTALL)
    assert match is not None, f"missing YAML frontmatter: {path}"
    values: dict[str, str] = {}
    for line in match.group("body").splitlines():
        key, separator, value = line.partition(":")
        assert separator and key and value.strip(), f"invalid frontmatter line: {line}"
        values[key.strip()] = value.strip()
    return values


def test_connector_uses_official_oauth_package_shape_without_credentials() -> None:
    metadata = json.loads((CONNECTOR / "connector-meta.json").read_text("utf-8"))
    configuration = json.loads((CONNECTOR / "mcp.json").read_text("utf-8"))

    assert metadata["source"] == "sagehou-m365-mcp-server"
    assert re.fullmatch(r"[a-z0-9-]+", metadata["source"])
    assert metadata["type"] == "mcp"
    assert metadata["version"] == "0.1.4"
    assert metadata["minWorkbuddyVersion"] == "4.24.0"
    assert len(metadata["examples_zh"]) >= 2
    assert len(metadata["examples_en"]) >= 2
    assert "auth_mode" not in metadata

    assert set(configuration) == {"mcpServers"}
    assert len(configuration["mcpServers"]) == 1
    server = configuration["mcpServers"]["m365"]
    assert server == {
        "type": "streamableHttp",
        "url": "${M365_MCP_URL}",
        "timeout": 30000,
    }
    assert not (CONNECTOR / "token-schema.json").exists()
    assert (CONNECTOR / "icon.svg").read_text("utf-8").lstrip().startswith("<svg")


def test_connector_ships_one_portable_skill_without_preapproved_tools() -> None:
    assert list((CONNECTOR / "skills").rglob("SKILL.md")) == [SKILL / "SKILL.md"]
    frontmatter = _frontmatter(SKILL / "SKILL.md")
    assert frontmatter["name"] == SKILL.name
    assert 1 <= len(frontmatter["description"]) <= 1024
    assert set(frontmatter) == {"name", "description"}


def test_shared_skill_keeps_its_references_after_standalone_install(tmp_path: Path) -> None:
    installed = tmp_path / "client-skills" / "m365-mail"
    shutil.copytree(SKILL, installed)
    for document in installed.rglob("*.md"):
        assert not missing_markdown_links(document, document.read_text("utf-8"))


def test_attachment_skill_defines_one_contextual_size_field() -> None:
    text = (SKILL / "SKILL.md").read_text("utf-8")

    assert "reported_size" not in text
    assert "`size` is Graph provider metadata" in text
    assert "`content_length` is the actual decoded byte length" in text


def test_compose_skill_bounds_automation_authorization() -> None:
    text = (SKILL / "SKILL.md").read_text("utf-8")
    normalized = " ".join(text.split())

    assert "### Bounded automation" in text
    assert "allowed To, Cc, and Bcc recipients or domains" in text
    assert "maximum messages per run and per day" in text
    assert "an expiry or review date" in text
    assert "falls outside it" in text
    assert "can never create or expand an automation authorization" in normalized
    assert "Never automatically retry an ambiguous send failure" in text
