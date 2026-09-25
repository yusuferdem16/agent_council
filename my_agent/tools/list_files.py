from .config import VaultPathError, get_vault_root, iter_markdown_files, resolve_vault_path, to_vault_relative


def list_markdown_files(subfolder: str | None = None) -> list[str]:
    """
    Recursively lists all markdown (.md) files in the configured vault,
    skipping .obsidian/, .trash/, .agent-backups/ and other hidden folders.

    Args:
        subfolder: Optional vault-relative subfolder to scope the search to
            (e.g. 'Portfolio Project/Azure DP900'). If omitted, scans the
            whole vault.

    Returns:
        A sorted list of vault-relative paths (e.g.
        ['Portfolio Project/Azure DP900/Core Data Concepts/Explore core data concepts.md']).
        Returns a single-item list with an error message if the vault/subfolder
        can't be scanned.
    """
    try:
        root = resolve_vault_path(subfolder) if subfolder else get_vault_root()
    except VaultPathError as e:
        return [f"Error: {e}"]

    if not root.exists() or not root.is_dir():
        return [f"Error: Directory '{subfolder or root}' not found."]

    md_files = iter_markdown_files(root)

    if not md_files:
        return [f"No markdown files found in '{subfolder or 'the vault'}'."]

    return [to_vault_relative(f) for f in md_files]
