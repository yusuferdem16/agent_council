from pathlib import Path

from .config import resolve_directory_path


def file_linker(target_filename: str, link_filename: str, directory_path: str | None = None) -> str:
    """
    Appends an Obsidian-style link (e.g., [[Linked File]]) to the end of an existing markdown file.
    Use this tool to connect related notes together.

    Args:
        target_filename: The name of the file to modify (e.g., 'main_note.md').
        link_filename: The name of the file to link to.
        directory_path: Optional folder containing the target file. If omitted, uses the configured vault path.

    Returns:
        A success message or an error string if the target file doesn't exist.
    """
    if not target_filename.endswith('.md'):
        target_filename += '.md'

    clean_link = link_filename[:-3] if link_filename.endswith('.md') else link_filename
    resolved_directory = resolve_directory_path(directory_path)
    target_path = Path(resolved_directory) / target_filename

    if not target_path.exists() or not target_path.is_file():
        return f"Error: Target file '{target_filename}' not found in '{resolved_directory}'. Create it first."

    try:
        with open(target_path, 'a', encoding='utf-8') as f:
            f.write(f"\n\n[[{clean_link}]]\n")

        return f"Success: Added link [[{clean_link}]] to the bottom of '{target_filename}'."

    except Exception as e:
        return f"Error linking file: {str(e)}"