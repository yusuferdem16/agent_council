"""Pure markdown helpers: frontmatter/heading/link parsing, edit-loss
validation, diff summaries and section-level editing. No filesystem access
here on purpose, so this stays easy to unit test directly.
"""

import difflib
import re
from dataclasses import dataclass, field


class SectionNotFoundError(Exception):
    """Raised when a requested `section_heading` doesn't exist in a note."""

    def __init__(self, message: str, available_headings: list[str] | None = None):
        super().__init__(message)
        self.available_headings = available_headings or []


_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---[ \t]*\n?", re.DOTALL)
_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$", re.MULTILINE)
_EMBED_RE = re.compile(r"!\[\[([^\]|#]+)")
_WIKILINK_RE = re.compile(r"(?<!!)\[\[([^\]|#]+)")
_CODE_FENCE_RE = re.compile(r"^```[^\n]*\n(.*?)^```[ \t]*$", re.MULTILINE | re.DOTALL)


def split_frontmatter(text: str) -> tuple[str | None, str]:
    """Split leading YAML frontmatter (between --- markers) from the body.

    Returns (frontmatter_raw, body). frontmatter_raw is None if the note
    doesn't start with a frontmatter block.
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return None, text
    return match.group(1), text[match.end():]


def extract_headings(text: str) -> list[str]:
    """Return every heading line (e.g. '## Related notes'), in document order."""
    return [f"{m.group(1)} {m.group(2).strip()}" for m in _HEADING_RE.finditer(text)]


def list_headings_with_levels(text: str) -> list[str]:
    return extract_headings(text)


def extract_wikilinks(text: str) -> set[str]:
    """Return the set of [[wikilink]] targets (embeds excluded)."""
    return {m.group(1).strip() for m in _WIKILINK_RE.finditer(text)}


def extract_embeds(text: str) -> set[str]:
    """Return the set of ![[embed]] targets."""
    return {m.group(1).strip() for m in _EMBED_RE.finditer(text)}


def extract_code_fences(text: str) -> list[str]:
    """Return the contents of every fenced code block (```...```)."""
    return [m.group(1) for m in _CODE_FENCE_RE.finditer(text)]


def strip_wrapping_code_fence(text: str) -> str:
    """Strip a single ``` fence that wraps the model's entire response.

    Only strips when the *whole* response is one fence (first line opens
    it, last line is a bare closing fence) - fences that are part of the
    actual note content are left alone.
    """
    stripped = text.strip()
    if not stripped.startswith("```"):
        return text

    lines = stripped.splitlines()
    if len(lines) < 2 or lines[-1].strip() != "```":
        return text

    return "\n".join(lines[1:-1])


_REMOVAL_KEYWORDS = (
    "remove",
    "delete",
    "strip out",
    "drop",
    "trim",
    "shorten",
    "condense",
    "prune",
    "clean up",
    "cut down",
    "de-duplicate",
    "dedupe",
)


def instructions_allow_removal(instructions: str) -> bool:
    """Heuristic: does the edit request explicitly ask to remove content?"""
    text = (instructions or "").lower()
    return any(keyword in text for keyword in _REMOVAL_KEYWORDS)


@dataclass
class EditValidationResult:
    ok: bool
    reasons: list[str] = field(default_factory=list)


def validate_edit(
    original: str,
    updated: str,
    instructions: str,
    min_retained_ratio: float = 0.85,
) -> EditValidationResult:
    """Check a proposed edit for signs of accidental content loss.

    Skips the loss checks when `instructions` explicitly asks to remove
    content (see `instructions_allow_removal`).
    """
    reasons: list[str] = []

    if not updated.strip():
        return EditValidationResult(ok=False, reasons=["The edit produced empty content."])

    allow_removal = instructions_allow_removal(instructions)

    if not allow_removal:
        if original and (len(updated) / len(original)) < min_retained_ratio:
            ratio = len(updated) / len(original)
            reasons.append(
                f"Output is only {ratio:.0%} of the original length "
                f"(below the {min_retained_ratio:.0%} threshold) and the "
                "instructions didn't ask to remove content."
            )

        missing_links = extract_wikilinks(original) - extract_wikilinks(updated)
        if missing_links:
            reasons.append(f"Lost wikilink(s): {', '.join(sorted(missing_links))}")

        missing_embeds = extract_embeds(original) - extract_embeds(updated)
        if missing_embeds:
            reasons.append(f"Lost embed(s): {', '.join(sorted(missing_embeds))}")

        orig_fence_count = len(extract_code_fences(original))
        updated_fence_count = len(extract_code_fences(updated))
        if updated_fence_count < orig_fence_count:
            reasons.append(
                f"Lost {orig_fence_count - updated_fence_count} fenced code block(s)."
            )

        orig_frontmatter, _ = split_frontmatter(original)
        updated_frontmatter, _ = split_frontmatter(updated)
        if orig_frontmatter and not updated_frontmatter:
            reasons.append("Lost the YAML frontmatter block.")

    return EditValidationResult(ok=not reasons, reasons=reasons)


def diff_summary(original: str, updated: str, max_diff_lines: int = 40) -> dict:
    """Summarize a change: lines added/removed, changed headings, and a
    short unified diff for a reviewer to skim."""
    diff_lines = list(
        difflib.unified_diff(
            original.splitlines(),
            updated.splitlines(),
            fromfile="original",
            tofile="updated",
            lineterm="",
            n=2,
        )
    )
    lines_added = sum(1 for l in diff_lines if l.startswith("+") and not l.startswith("+++"))
    lines_removed = sum(1 for l in diff_lines if l.startswith("-") and not l.startswith("---"))

    original_headings = set(extract_headings(original))
    updated_headings = set(extract_headings(updated))

    truncated = diff_lines[:max_diff_lines]
    if len(diff_lines) > max_diff_lines:
        truncated.append(f"... ({len(diff_lines) - max_diff_lines} more diff lines omitted)")

    return {
        "lines_added": lines_added,
        "lines_removed": lines_removed,
        "headings_added": sorted(updated_headings - original_headings),
        "headings_removed": sorted(original_headings - updated_headings),
        "unified_diff": "\n".join(truncated),
    }


def find_section(text: str, heading: str) -> tuple[int, int, int] | None:
    """Find a heading's section span: (start_offset, end_offset, level).

    The section runs from the heading (inclusive) to the next heading of
    the same or higher level (exclusive), or the end of the text.
    """
    matches = list(_HEADING_RE.finditer(text))
    target = heading.strip().lstrip("#").strip().lower()

    for i, m in enumerate(matches):
        level = len(m.group(1))
        if m.group(2).strip().lower() == target:
            start = m.start()
            end = len(text)
            for nxt in matches[i + 1:]:
                if len(nxt.group(1)) <= level:
                    end = nxt.start()
                    break
            return start, end, level
    return None


def get_section(text: str, heading: str) -> str:
    """Return the text of a single section, or raise SectionNotFoundError."""
    found = find_section(text, heading)
    if found is None:
        raise SectionNotFoundError(
            f"Heading '{heading}' not found.",
            available_headings=list_headings_with_levels(text),
        )
    start, end, _ = found
    return text[start:end]


def replace_section(text: str, heading: str, new_section_text: str) -> str:
    """Replace a single section's text in place, keeping the rest of the note untouched."""
    found = find_section(text, heading)
    if found is None:
        raise SectionNotFoundError(
            f"Heading '{heading}' not found.",
            available_headings=list_headings_with_levels(text),
        )
    start, end, _ = found
    replacement = new_section_text.rstrip("\n") + "\n"
    return text[:start] + replacement + text[end:]
