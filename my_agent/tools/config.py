import os
import re
from pathlib import Path, PurePosixPath

DEFAULT_VAULT_DIR = "obsidian_vault"
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"
EDIT_BACKUP_DIRNAME = ".agent-backups"
EXCLUDED_DIR_NAMES = {".obsidian", ".trash", EDIT_BACKUP_DIRNAME}

project_root = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv(project_root / ".env")
else:
    env_file = project_root / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"\''))


class VaultPathError(Exception):
    """Raised when a note path/name can't be safely resolved inside the vault."""

    def __init__(self, message: str, candidates: list[str] | None = None):
        super().__init__(message)
        self.candidates = candidates or []


def get_default_vault_path() -> str:
    """Return the configured vault directory without hardcoded machine-specific paths."""
    env_value = os.getenv("OBSIDIAN_VAULT_PATH") or os.getenv("VAULT_PATH")
    if env_value:
        return env_value

    default_path = project_root / DEFAULT_VAULT_DIR
    return str(default_path)


def get_vault_root() -> Path:
    """Return the configured vault directory as an absolute, resolved Path."""
    return Path(get_default_vault_path()).expanduser().resolve()


def get_groq_model() -> str:
    """Return the configured Groq model, falling back to the current default."""
    return os.getenv("GROQ_MODEL") or DEFAULT_GROQ_MODEL


_DRIVE_LETTER_RE = re.compile(r"^[A-Za-z]:[\\/]")


def _looks_absolute(candidate: str) -> bool:
    return (
        PurePosixPath(candidate).is_absolute()
        or candidate.startswith("\\\\")
        or bool(_DRIVE_LETTER_RE.match(candidate))
    )


def resolve_vault_path(relative_path: str) -> Path:
    """Safely resolve a vault-relative path against the configured vault.

    Refuses absolute paths and any path that would resolve outside the
    vault (e.g. via '..' traversal), regardless of whether the target
    exists yet.
    """
    if relative_path is None or not str(relative_path).strip():
        raise VaultPathError("A vault-relative path is required.")

    candidate = str(relative_path).strip().replace("\\", "/")
    if _looks_absolute(candidate):
        raise VaultPathError(
            f"'{relative_path}' must be relative to the vault, not absolute."
        )

    vault_root = get_vault_root()
    full = (vault_root / candidate).resolve()

    try:
        full.relative_to(vault_root)
    except ValueError:
        raise VaultPathError(f"'{relative_path}' resolves outside the vault.")

    return full


def to_vault_relative(path: Path) -> str:
    """Convert an absolute path inside the vault back to a vault-relative posix path."""
    vault_root = get_vault_root()
    return Path(path).resolve().relative_to(vault_root).as_posix()


def _is_excluded_dir(name: str) -> bool:
    return name.startswith(".") or name in EXCLUDED_DIR_NAMES


def iter_markdown_files(root: Path | None = None) -> list[Path]:
    """Recursively list markdown files under `root` (default: vault root).

    Skips hidden folders and the excluded ones (.obsidian, .trash,
    .agent-backups).
    """
    base = root if root is not None else get_vault_root()
    if not base.exists():
        return []

    results = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if not _is_excluded_dir(d)]
        for name in filenames:
            if name.endswith(".md"):
                results.append(Path(dirpath) / name)
    results.sort()
    return results


def resolve_note_reference(reference: str) -> Path:
    """Resolve a vault-relative path OR a bare Obsidian-style note name.

    Wikilinks like [[Explore core data concepts]] use bare names, so this
    accepts either a full vault-relative path (e.g.
    'Folder/Sub/Note.md') or just the note's bare name and searches the
    vault for a unique match.

    Raises VaultPathError if nothing matches, if the path would escape the
    vault, or (with `.candidates` populated) if a bare name matches more
    than one note.
    """
    if reference is None or not str(reference).strip():
        raise VaultPathError("A note path or name is required.")

    ref = str(reference).strip()

    if "/" in ref or ref.lower().endswith(".md"):
        rel = ref if ref.lower().endswith(".md") else f"{ref}.md"
        path = resolve_vault_path(rel)
        if not path.exists() or path.suffix != ".md":
            raise VaultPathError(f"No note found at '{rel}'.")
        return path

    matches = [p for p in iter_markdown_files() if p.stem.lower() == ref.lower()]
    if not matches:
        raise VaultPathError(f"No note named '{reference}' found in the vault.")
    if len(matches) > 1:
        candidates = sorted(to_vault_relative(p) for p in matches)
        raise VaultPathError(
            f"'{reference}' is ambiguous; matches: {', '.join(candidates)}. "
            "Use one of these full paths instead.",
            candidates=candidates,
        )
    return matches[0]
