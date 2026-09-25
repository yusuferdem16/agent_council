import re

from .config import VaultPathError, resolve_note_reference, to_vault_relative
from .markdown_utils import extract_embeds, extract_headings, extract_wikilinks, split_frontmatter


def read_note(file_path: str) -> dict:
    """
    Reads a note from the vault and returns its frontmatter, headings,
    links, embeds, checkbox milestones and raw content.

    Args:
        file_path: A vault-relative path (e.g.
            'Portfolio Project/Azure DP900/Core Data Concepts/Explore core
            data concepts.md') or a bare note name as used in [[wikilinks]].

    Returns:
        A dict of the note's metadata and raw content, or {"error": ...}
        (with "candidates" if the bare name was ambiguous) if it can't be found.
    """
    try:
        path = resolve_note_reference(file_path)
    except VaultPathError as e:
        return {"error": str(e), "candidates": e.candidates}

    content = path.read_text(encoding="utf-8")
    frontmatter_raw, _ = split_frontmatter(content)

    pending_tasks = re.findall(r"- \[\s\] (.*)", content)
    completed_tasks = re.findall(r"- \[[xX]\] (.*)", content)

    return {
        "file_name": path.name,
        "file_path": to_vault_relative(path),
        "frontmatter": frontmatter_raw,
        "headings": extract_headings(content),
        "wikilinks": sorted(extract_wikilinks(content)),
        "embeds": sorted(extract_embeds(content)),
        "completed_milestones": completed_tasks,
        "pending_milestones": pending_tasks,
        "raw_content": content,
    }


# Backwards-compatible alias for the original tool name.
parse_roadmap_markdown = read_note
