from my_agent.tools import edit_groq


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content):
        self._content = content

    def create(self, **kwargs):
        return _FakeResponse(self._content)


class _FakeChat:
    def __init__(self, content):
        self.completions = _FakeCompletions(content)


class _FakeGroqClient:
    def __init__(self, content):
        self.chat = _FakeChat(content)


def _patch_groq(monkeypatch, content):
    monkeypatch.setattr(edit_groq, "Groq", lambda *a, **k: _FakeGroqClient(content))


def test_truncated_output_is_rejected_and_original_untouched(vault, monkeypatch):
    note_path = vault / "Relational data.md"
    original = note_path.read_text(encoding="utf-8")

    _patch_groq(monkeypatch, "# gone")

    result = edit_groq.edit_markdown_with_groq("Relational data.md", "improve the wording")

    assert result["status"] == "rejected"
    assert note_path.read_text(encoding="utf-8") == original
    assert not (vault / ".agent-backups").exists()


def test_valid_output_is_written_and_backup_created(vault, monkeypatch):
    note_path = vault / "Relational data.md"
    original = note_path.read_text(encoding="utf-8")
    updated_content = original + "\n\n## Extra\n\nSome extra detail was added here.\n"

    _patch_groq(monkeypatch, updated_content)

    result = edit_groq.edit_markdown_with_groq("Relational data.md", "expand the note")

    assert result["status"] == "success"
    # The tool strips the raw model output before writing (same as the original code).
    assert note_path.read_text(encoding="utf-8") == updated_content.strip()

    backup_path = vault / result["backup_path"]
    assert backup_path.exists()
    assert backup_path.read_text(encoding="utf-8") == original


def test_dry_run_does_not_write(vault, monkeypatch):
    note_path = vault / "Relational data.md"
    original = note_path.read_text(encoding="utf-8")
    updated_content = original + "\n\n## Extra\n\nSome extra detail was added here.\n"

    _patch_groq(monkeypatch, updated_content)

    result = edit_groq.edit_markdown_with_groq(
        "Relational data.md", "expand the note", dry_run=True
    )

    assert result["status"] == "dry_run"
    assert "diff_summary" in result
    assert note_path.read_text(encoding="utf-8") == original
    assert not (vault / ".agent-backups").exists()


def test_wrapping_code_fence_is_stripped_before_writing(vault, monkeypatch):
    note_path = vault / "Relational data.md"
    original = note_path.read_text(encoding="utf-8")
    updated_content = original + "\n\n## Extra\n\nSome extra detail was added here.\n"
    fenced_response = f"```markdown\n{updated_content}\n```"

    _patch_groq(monkeypatch, fenced_response)

    result = edit_groq.edit_markdown_with_groq("Relational data.md", "expand the note")

    assert result["status"] == "success"
    written = note_path.read_text(encoding="utf-8")
    assert not written.startswith("```")
    assert "## Extra" in written


def test_section_heading_edits_only_that_section(vault, monkeypatch):
    note_path = (
        vault
        / "Portfolio Project"
        / "Azure DP900"
        / "Core Data Concepts"
        / "Explore core data concepts.md"
    )
    original = note_path.read_text(encoding="utf-8")

    replacement_section = (
        "## Core concepts\n\n"
        "Rewritten core concepts section, still linking [[Relational data]] "
        "and embedding ![[diagram.png]].\n\n"
        "- [ ] Study cosmos db\n"
        "- [x] Study relational data\n\n"
        "```python\nprint(\"hello world\")\n```\n"
    )
    _patch_groq(monkeypatch, replacement_section)

    result = edit_groq.edit_markdown_with_groq(
        "Portfolio Project/Azure DP900/Core Data Concepts/Explore core data concepts.md",
        "reword this section",
        section_heading="## Core concepts",
    )

    assert result["status"] == "success"
    written = note_path.read_text(encoding="utf-8")
    assert "Rewritten core concepts section" in written
    # Everything outside the targeted section should be untouched.
    assert "## Related notes" in written
    assert "[[Home]]" in written
    assert original.split("## Core concepts")[0] == written.split("## Core concepts")[0]
