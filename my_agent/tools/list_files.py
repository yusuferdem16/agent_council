from pathlib import Path

from .config import resolve_directory_path


def list_markdown_files(directory_path: str | None = None) -> list[str]:
    """
    Lists all markdown (.md) files available in the specified directory.
    Use this tool to find out what files exist before attempting to read or edit them.

    Args:
        directory_path: Optional folder to scan. If omitted, uses the environment-configured vault path.

    Returns:
        A list of filenames (e.g., ['docker_microservices.md', 'api_workflow.md']).
        Returns an error message string if the directory does not exist.
    """
    resolved_path = resolve_directory_path(directory_path)
    path = Path(resolved_path)

    if not path.exists() or not path.is_dir():
        return [f"Error: Directory '{resolved_path}' not found."]

    md_files = [f.name for f in path.glob('*.md')]

    if not md_files:
        return [f"No markdown files found in this directory: {resolved_path}"]

    return md_files