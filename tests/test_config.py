import pytest

from my_agent.tools.config import VaultPathError, resolve_vault_path
from my_agent.tools.create_files import create_markdown_file
from my_agent.tools.list_files import list_markdown_files


def test_list_markdown_files_is_recursive(vault):
    files = list_markdown_files()

    assert "Relational data.md" in files
    assert (
        "Portfolio Project/Azure DP900/Core Data Concepts/Explore core data concepts.md"
        in files
    )


def test_list_markdown_files_skips_excluded_and_hidden_folders(vault):
    files = list_markdown_files()

    assert not any(".obsidian" in f for f in files)
    assert not any(".trash" in f for f in files)
    assert not any("deleted note" in f for f in files)


def test_list_markdown_files_skips_backup_folder(vault):
    backup_dir = vault / ".agent-backups" / "Relational data.md.20260101T000000Z.md"
    backup_dir.parent.mkdir(parents=True)
    backup_dir.write_text("# old backup", encoding="utf-8")

    files = list_markdown_files()

    assert not any(".agent-backups" in f for f in files)


def test_list_markdown_files_subfolder_scoping(vault):
    files = list_markdown_files(subfolder="Portfolio Project/Azure DP900")

    assert len(files) == 1
    assert files[0].endswith("Explore core data concepts.md")


def test_resolve_vault_path_allows_internal_dotdot(vault):
    # '..' that stays inside the vault should resolve fine.
    resolved = resolve_vault_path(
        "Portfolio Project/Azure DP900/Core Data Concepts/../Core Data Concepts/"
        "Explore core data concepts.md"
    )
    assert resolved.exists()


@pytest.mark.parametrize(
    "traversal_path",
    [
        "../outside.md",
        "../../etc/passwd",
        "Portfolio Project/../../outside.md",
    ],
)
def test_resolve_vault_path_rejects_traversal(vault, traversal_path):
    with pytest.raises(VaultPathError):
        resolve_vault_path(traversal_path)


def test_resolve_vault_path_rejects_absolute_paths(vault):
    with pytest.raises(VaultPathError):
        resolve_vault_path("/etc/passwd")


def test_create_markdown_file_rejects_traversal(vault):
    result = create_markdown_file("../escape.md", "malicious content")

    assert result.startswith("Error:")
    assert not (vault.parent / "escape.md").exists()


def test_create_markdown_file_supports_nested_subfolders(vault):
    result = create_markdown_file("New Folder/Sub Folder/New note.md", "# Hello")

    assert result.startswith("Success:")
    assert (vault / "New Folder" / "Sub Folder" / "New note.md").read_text(
        encoding="utf-8"
    ) == "# Hello"
