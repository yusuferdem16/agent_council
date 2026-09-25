from my_agent.tools.markdown_utils import (
    SectionNotFoundError,
    diff_summary,
    extract_code_fences,
    extract_embeds,
    extract_headings,
    extract_wikilinks,
    find_section,
    get_section,
    instructions_allow_removal,
    replace_section,
    split_frontmatter,
    strip_wrapping_code_fence,
    validate_edit,
)

import pytest

NOTE = """---
title: Sample
---

# Sample

Intro paragraph with a [[Wiki Link]] and an ![[embedded-image.png]].

> [!note]
> A callout.

```python
print("hi")
```

## Section A

Content A.

## Section B

Content B.
"""


def test_split_frontmatter():
    frontmatter, body = split_frontmatter(NOTE)
    assert frontmatter == "title: Sample"
    assert body.startswith("\n# Sample")


def test_split_frontmatter_none_when_missing():
    frontmatter, body = split_frontmatter("# No frontmatter\n")
    assert frontmatter is None
    assert body == "# No frontmatter\n"


def test_extract_headings():
    assert extract_headings(NOTE) == ["# Sample", "## Section A", "## Section B"]


def test_extract_wikilinks_excludes_embeds():
    assert extract_wikilinks(NOTE) == {"Wiki Link"}


def test_extract_embeds():
    assert extract_embeds(NOTE) == {"embedded-image.png"}


def test_extract_code_fences():
    fences = extract_code_fences(NOTE)
    assert len(fences) == 1
    assert 'print("hi")' in fences[0]


def test_strip_wrapping_code_fence_strips_whole_response():
    wrapped = "```markdown\n# Title\n\nBody text\n```"
    assert strip_wrapping_code_fence(wrapped) == "# Title\n\nBody text"


def test_strip_wrapping_code_fence_leaves_internal_fences_alone():
    text = "# Title\n\n```python\nprint(1)\n```\n\nMore text."
    assert strip_wrapping_code_fence(text) == text


def test_instructions_allow_removal():
    assert instructions_allow_removal("Please remove the outdated section")
    assert instructions_allow_removal("Trim this down a lot")
    assert not instructions_allow_removal("Fix the typo in the intro")


def test_validate_edit_rejects_large_truncation():
    original = "word " * 200
    updated = "word " * 5
    result = validate_edit(original, updated, "fix the typo")
    assert not result.ok
    assert any("length" in r for r in result.reasons)


def test_validate_edit_allows_truncation_when_removal_requested():
    original = "word " * 200
    updated = "word " * 5
    result = validate_edit(original, updated, "remove most of this section")
    assert result.ok


def test_validate_edit_rejects_lost_wikilink():
    original = "Intro with [[Important Note]] linked here."
    updated = "Intro rewritten without the link."
    result = validate_edit(original, updated, "improve the wording")
    assert not result.ok
    assert any("wikilink" in r.lower() for r in result.reasons)


def test_validate_edit_rejects_lost_frontmatter():
    original = "---\ntitle: X\n---\n\nBody here with enough text to pass length checks."
    updated = "Body here with enough text to pass length checks, rewritten a bit."
    result = validate_edit(original, updated, "improve the wording")
    assert not result.ok
    assert any("frontmatter" in r.lower() for r in result.reasons)


def test_validate_edit_accepts_a_good_edit():
    original = "# Title\n\nSome [[Link]] and text " * 5
    updated = original + "\n\nAn extra paragraph with more detail added."
    result = validate_edit(original, updated, "expand the note")
    assert result.ok
    assert result.reasons == []


def test_diff_summary_counts_and_headings():
    original = "# Title\n\nLine one.\n\n## Old Section\n\nold content\n"
    updated = "# Title\n\nLine one.\n\n## New Section\n\nnew content\nextra line\n"

    summary = diff_summary(original, updated)

    assert summary["lines_added"] > 0
    assert summary["lines_removed"] > 0
    assert "## New Section" in summary["headings_added"]
    assert "## Old Section" in summary["headings_removed"]


def test_find_and_get_section():
    section = get_section(NOTE, "## Section A")
    assert section.startswith("## Section A")
    assert "Content A." in section
    assert "Section B" not in section


def test_get_section_not_found_lists_available_headings():
    with pytest.raises(SectionNotFoundError) as excinfo:
        get_section(NOTE, "## Nonexistent")
    assert "## Section A" in excinfo.value.available_headings


def test_replace_section_only_touches_that_section():
    updated = replace_section(NOTE, "## Section A", "## Section A\n\nReplaced content.\n")
    assert "Replaced content." in updated
    assert "Content A." not in updated
    assert "Content B." in updated
    assert updated.startswith(NOTE[: NOTE.index("## Section A")])
