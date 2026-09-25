from datetime import datetime, timezone
from pathlib import Path

from groq import Groq

from .config import (
    EDIT_BACKUP_DIRNAME,
    VaultPathError,
    get_groq_model,
    get_vault_root,
    resolve_vault_path,
    to_vault_relative,
)
from .markdown_utils import (
    SectionNotFoundError,
    diff_summary,
    get_section,
    replace_section,
    strip_wrapping_code_fence,
    validate_edit,
)

DEFAULT_MIN_RETAINED_RATIO = 0.85
DEFAULT_SECTION_EDIT_THRESHOLD_BYTES = 12 * 1024


def edit_markdown_with_groq(
    file_path: str,
    edit_instructions: str,
    section_heading: str | None = None,
    dry_run: bool = False,
    min_retained_ratio: float = DEFAULT_MIN_RETAINED_RATIO,
    size_threshold_bytes: int = DEFAULT_SECTION_EDIT_THRESHOLD_BYTES,
) -> dict:
    """
    Edits a markdown note in the vault using Groq, with safeguards against
    accidental content loss.

    Before writing, the model's output is validated against the original:
    it's rejected if it's much shorter than the original, or if it dropped
    wikilinks, embeds, fenced code blocks or frontmatter - unless
    edit_instructions clearly asked for that removal. A timestamped backup
    of the original is written to '.agent-backups/' inside the vault before
    any accepted write.

    Args:
        file_path: Vault-relative path (or bare note name) of the .md file to edit.
        edit_instructions: What Groq should change, add, or fix in the file.
        section_heading: If set, only this section (e.g. '## Setup') is sent
            to Groq and replaced; the rest of the note is left untouched.
            Recommended for notes over size_threshold_bytes.
        dry_run: If True, validates and returns the diff but writes nothing.
        min_retained_ratio: Minimum output/original length ratio allowed
            before the edit is rejected as likely content loss.
        size_threshold_bytes: Notes larger than this get a warning
            suggesting section_heading, when it isn't already set.

    Returns:
        A dict with at least "status" (one of "success", "dry_run",
        "rejected", "error") and "message". Successful/dry-run edits also
        include "diff_summary"; successful edits include "backup_path".
    """
    try:
        resolved = resolve_vault_path(
            file_path if file_path.lower().endswith(".md") else f"{file_path}.md"
        )
    except VaultPathError as e:
        return {"status": "error", "message": str(e)}

    if not resolved.exists() or resolved.suffix != ".md":
        return {"status": "error", "message": f"Markdown file not found at '{file_path}'."}

    relative_path = to_vault_relative(resolved)
    original_content = resolved.read_text(encoding="utf-8")

    target_text = original_content
    if section_heading:
        try:
            target_text = get_section(original_content, section_heading)
        except SectionNotFoundError as e:
            return {
                "status": "error",
                "message": f"Heading '{section_heading}' not found in '{relative_path}'.",
                "available_headings": e.available_headings,
            }

    client = Groq()
    prompt = (
        f"Edit the following markdown according to these instructions: {edit_instructions}\n\n"
        f"ORIGINAL CONTENT:\n{target_text}"
    )

    try:
        response = client.chat.completions.create(
            model=get_groq_model(),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert technical editor. Return ONLY the raw "
                        "updated markdown content. Do not enclose it in markdown "
                        "code blocks. Keep all existing formatting intact unless "
                        "instructed to change it."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
    except Exception as e:
        return {"status": "error", "message": f"Groq failed to edit the file: {e}"}

    updated_target = strip_wrapping_code_fence(response.choices[0].message.content.strip())

    validation = validate_edit(target_text, updated_target, edit_instructions, min_retained_ratio)
    if not validation.ok:
        return {
            "status": "rejected",
            "message": "Edit rejected before writing: " + "; ".join(validation.reasons),
            "file_path": relative_path,
        }

    if section_heading:
        try:
            new_full_content = replace_section(original_content, section_heading, updated_target)
        except SectionNotFoundError:
            return {
                "status": "error",
                "message": f"Heading '{section_heading}' disappeared while editing '{relative_path}'.",
            }
    else:
        new_full_content = updated_target

    summary = diff_summary(original_content, new_full_content)

    warning = None
    if not section_heading and len(original_content.encode("utf-8")) > size_threshold_bytes:
        warning = (
            f"Note is over {size_threshold_bytes // 1024} KB; consider passing "
            "section_heading next time to edit a single section instead of the whole file."
        )

    if dry_run:
        return {
            "status": "dry_run",
            "message": f"Dry run: edit for '{relative_path}' validated but not written.",
            "file_path": relative_path,
            "diff_summary": summary,
            "section_heading": section_heading,
            "warning": warning,
        }

    backup_path = _write_backup(resolved, original_content)
    resolved.write_text(new_full_content, encoding="utf-8")

    return {
        "status": "success",
        "message": f"Success! Groq edited '{relative_path}' based on: '{edit_instructions}'",
        "file_path": relative_path,
        "backup_path": to_vault_relative(backup_path),
        "diff_summary": summary,
        "section_heading": section_heading,
        "warning": warning,
    }


def _write_backup(resolved_path: Path, original_content: str) -> Path:
    vault_root = get_vault_root()
    relative = to_vault_relative(resolved_path)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = vault_root / EDIT_BACKUP_DIRNAME / f"{relative}.{timestamp}.md"
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path.write_text(original_content, encoding="utf-8")
    return backup_path
