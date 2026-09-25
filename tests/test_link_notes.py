from my_agent.tools.config import VaultPathError, resolve_note_reference
from my_agent.tools.link_files import link_notes


def test_link_notes_creates_related_section(vault):
    note_path = vault / "Relational data.md"

    result = link_notes(
        "Relational data.md",
        "Explore core data concepts",
        reason="background reading",
    )

    content = note_path.read_text(encoding="utf-8")
    assert "## Related notes" in content
    assert "[[Explore core data concepts]]" in content
    assert "background reading" in content
    assert "Added link" in result


def test_link_notes_skips_duplicates(vault):
    note_path = vault / "Relational data.md"

    link_notes("Relational data.md", "Explore core data concepts", reason="first pass")
    result = link_notes("Relational data.md", "Explore core data concepts", reason="second pass")

    content = note_path.read_text(encoding="utf-8")
    assert content.count("[[Explore core data concepts]]") == 1
    assert "skipped" in result.lower()


def test_link_notes_bidirectional_links_both_notes(vault):
    source_path = vault / "Relational data.md"
    target_path = (
        vault
        / "Portfolio Project"
        / "Azure DP900"
        / "Core Data Concepts"
        / "Explore core data concepts.md"
    )

    link_notes(
        "Relational data.md",
        "Explore core data concepts",
        reason="see also",
        bidirectional=True,
    )

    source_content = source_path.read_text(encoding="utf-8")
    target_content = target_path.read_text(encoding="utf-8")

    assert "[[Explore core data concepts]]" in source_content
    # The target note already links to "Relational data" once (inside
    # "## Core concepts"), so the reciprocal link should be skipped as a duplicate
    # rather than duplicated under "## Related notes".
    assert target_content.count("[[Relational data]]") == 1


def test_link_notes_uses_disambiguated_path_when_name_is_ambiguous(vault):
    duplicate_dir = vault / "Other Folder"
    duplicate_dir.mkdir()
    (duplicate_dir / "Relational data.md").write_text("# Another relational data note\n", encoding="utf-8")

    # A fresh note with no pre-existing links, so the dedup check can't skip it.
    scratch_note = vault / "Scratch.md"
    scratch_note.write_text("# Scratch\n\nJust a scratch note.\n", encoding="utf-8")

    # The bare name "Relational data" is now ambiguous in the vault (root copy
    # and "Other Folder" copy), so the added link must disambiguate by path.
    result = link_notes(
        "Scratch.md",
        "Other Folder/Relational data.md",
        reason="duplicate name test",
    )

    assert "Added link" in result
    content = scratch_note.read_text(encoding="utf-8")
    assert "[[Other Folder/Relational data|Relational data]]" in content


def test_resolve_note_reference_reports_candidates_for_ambiguous_bare_name(vault):
    duplicate_dir = vault / "Other Folder"
    duplicate_dir.mkdir()
    (duplicate_dir / "Relational data.md").write_text("# Another relational data note\n", encoding="utf-8")

    try:
        resolve_note_reference("Relational data")
        assert False, "expected VaultPathError for an ambiguous bare name"
    except VaultPathError as e:
        assert len(e.candidates) == 2
        assert any("Other Folder" in c for c in e.candidates)


def test_link_notes_errors_on_unresolvable_target(vault):
    result = link_notes("Relational data.md", "Does Not Exist")
    assert result.startswith("Error:")
