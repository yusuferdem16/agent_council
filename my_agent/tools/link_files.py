import re

from .config import VaultPathError, iter_markdown_files, resolve_note_reference, to_vault_relative
from .markdown_utils import extract_headings

RELATED_NOTES_HEADING = "## Related notes"

_WIKILINK_ANY_RE = re.compile(r"\[\[([^\]]+)\]\]")
_NAV_LINE_RE = re.compile(r"^(\s*(\[\[[^\]]+\]\]|\[[^\]]*\]\([^)]*\))\s*)+$")

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with",
    "is", "are", "what", "how", "why", "when", "this", "that", "these",
    "those", "it", "be", "as", "at", "by", "from", "your", "you",
}


def _note_display_name(rel_path: str) -> str:
    return rel_path.rsplit("/", 1)[-1].removesuffix(".md")


def _is_ambiguous(bare_name: str) -> bool:
    matches = [p for p in iter_markdown_files() if p.stem.lower() == bare_name.lower()]
    return len(matches) > 1


def _wikilink_target(rel_path: str, ambiguous: bool) -> str:
    name = _note_display_name(rel_path)
    if ambiguous:
        return f"[[{rel_path.removesuffix('.md')}|{name}]]"
    return f"[[{name}]]"


def _existing_link_targets(content: str) -> set[str]:
    """Bare display names already linked anywhere in the note."""
    targets = set()
    for m in _WIKILINK_ANY_RE.finditer(content):
        raw_target = m.group(1).split("|")[0].split("#")[0].strip()
        targets.add(raw_target.rsplit("/", 1)[-1].lower())
    return targets


def _split_trailing_nav(content: str) -> tuple[str, str]:
    """Split off a trailing line made purely of links (a nav/breadcrumb line)."""
    if not content.endswith("\n"):
        content += "\n"
    lines = content.split("\n")
    idx = len(lines) - 1
    while idx >= 0 and lines[idx] == "":
        idx -= 1
    if idx < 0:
        return content, ""
    last_line = lines[idx]
    if _NAV_LINE_RE.match(last_line.strip()):
        main = "\n".join(lines[:idx]).rstrip("\n") + "\n"
        return main, last_line
    return content, ""


def _ensure_related_section(main_content: str, new_line: str) -> str:
    lines = main_content.split("\n")
    heading_idx = None
    for i, l in enumerate(lines):
        if l.strip().lower() == RELATED_NOTES_HEADING.lower():
            heading_idx = i
            break

    if heading_idx is None:
        base = main_content.rstrip("\n")
        return f"{base}\n\n{RELATED_NOTES_HEADING}\n{new_line}\n"

    insert_at = heading_idx + 1
    while insert_at < len(lines) and lines[insert_at].strip() == "":
        insert_at += 1
    while insert_at < len(lines) and lines[insert_at].strip().startswith("-"):
        insert_at += 1
    lines.insert(insert_at, new_line)
    return "\n".join(lines)


def _link_one_direction(from_path, to_path, reason: str) -> str:
    from_rel = to_vault_relative(from_path)
    to_rel = to_vault_relative(to_path)
    content = from_path.read_text(encoding="utf-8")

    target_name = _note_display_name(to_rel)
    if target_name.lower() in _existing_link_targets(content):
        return f"'{from_rel}' already links to '{target_name}'; skipped."

    link_target = _wikilink_target(to_rel, _is_ambiguous(target_name))
    new_line = f"- {link_target}" + (f" — {reason}" if reason else "")

    main, nav = _split_trailing_nav(content)
    main = _ensure_related_section(main, new_line)

    final_content = main.rstrip("\n") + "\n"
    if nav:
        final_content += "\n" + nav + "\n"

    from_path.write_text(final_content, encoding="utf-8")
    return f"Added link to '{target_name}' in '{from_rel}'."


def link_notes(source: str, target: str, reason: str = "", bidirectional: bool = False) -> str:
    """
    Links one note to another under a '## Related notes' section.

    Adds '- [[Target]] — reason' under a '## Related notes' section in
    the source note, creating the section if it's missing and placing it
    before any trailing navigation line (a line made only of links) if the
    note has one. Skips the link if it's already present anywhere in the
    note. Uses '[[path/Name|Name]]' instead of a bare '[[Name]]' only when
    the target's bare name is ambiguous elsewhere in the vault.

    Args:
        source: Vault-relative path or bare name of the note to add the link to.
        target: Vault-relative path or bare name of the note being linked to.
        reason: Optional short reason appended after an em dash.
        bidirectional: If True, also add a reciprocal link from target back to source.

    Returns:
        A summary of what was added/skipped, or an error message.
    """
    try:
        source_path = resolve_note_reference(source)
        target_path = resolve_note_reference(target)
    except VaultPathError as e:
        return f"Error: {e}"

    results = [_link_one_direction(source_path, target_path, reason)]
    if bidirectional:
        results.append(_link_one_direction(target_path, source_path, reason))

    return " ".join(results)


def suggest_links(note: str, limit: int = 10) -> list[dict]:
    """
    Read-only: suggests notes related to the given note, scored by shared
    headings and key terms. Never writes anything - use link_notes to
    actually add a link once the Orchestrator picks a suggestion.

    Args:
        note: Vault-relative path or bare name of the note to find related notes for.
        limit: Maximum number of suggestions to return.

    Returns:
        A list of {"path", "score", "shared_headings", "shared_terms"}
        dicts, sorted by descending score (empty if nothing is related), or
        a single {"error": ...} item if the note can't be found.
    """
    try:
        note_path = resolve_note_reference(note)
    except VaultPathError as e:
        return [{"error": str(e), "candidates": e.candidates}]

    note_content = note_path.read_text(encoding="utf-8")
    note_headings = {h.lower() for h in extract_headings(note_content)}
    note_terms = _key_terms(note_content)

    suggestions = []
    for other in iter_markdown_files():
        if other.resolve() == note_path.resolve():
            continue
        other_content = other.read_text(encoding="utf-8")
        other_headings = {h.lower() for h in extract_headings(other_content)}
        other_terms = _key_terms(other_content)

        shared_headings = sorted(note_headings & other_headings)
        shared_terms = sorted(note_terms & other_terms)
        score = len(shared_headings) * 3 + len(shared_terms)
        if score > 0:
            suggestions.append({
                "path": to_vault_relative(other),
                "score": score,
                "shared_headings": shared_headings,
                "shared_terms": shared_terms[:10],
            })

    suggestions.sort(key=lambda s: s["score"], reverse=True)
    return suggestions[:limit]


def _key_terms(text: str) -> set[str]:
    words = re.findall(r"[A-Za-z0-9']+", text.lower())
    return {w for w in words if len(w) > 2 and w not in _STOPWORDS}
