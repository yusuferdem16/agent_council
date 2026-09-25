from my_agent.tools.read_markdown import parse_roadmap_markdown, read_note


def test_read_note_by_full_vault_relative_path(vault):
    result = read_note(
        "Portfolio Project/Azure DP900/Core Data Concepts/Explore core data concepts.md"
    )

    assert result["frontmatter"].startswith("title: Explore core data concepts")
    assert "## Core concepts" in result["headings"]
    assert "Relational data" in result["wikilinks"]
    assert "diagram.png" in result["embeds"]
    assert result["completed_milestones"] == ["Study relational data"]
    assert result["pending_milestones"] == ["Study cosmos db"]


def test_read_note_by_bare_wikilink_name(vault):
    result = read_note("Explore core data concepts")
    assert result["file_path"].endswith("Explore core data concepts.md")


def test_read_note_missing_file_returns_error(vault):
    result = read_note("Does Not Exist.md")
    assert "error" in result


def test_parse_roadmap_markdown_alias_still_works(vault):
    assert parse_roadmap_markdown is read_note
    result = parse_roadmap_markdown("Relational data.md")
    assert result["file_name"] == "Relational data.md"
