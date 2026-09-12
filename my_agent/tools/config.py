import os
from pathlib import Path

DEFAULT_VAULT_DIR = "obsidian_vault"

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


def get_default_vault_path() -> str:
    """Return the configured vault directory without hardcoded machine-specific paths."""
    env_value = os.getenv("OBSIDIAN_VAULT_PATH") or os.getenv("VAULT_PATH")
    if env_value:
        return env_value

    default_path = project_root / DEFAULT_VAULT_DIR
    return str(default_path)


def resolve_directory_path(directory_path: str | None = None) -> str:
    """Use an explicit directory when provided; otherwise fall back to the env-configured vault."""
    if directory_path and directory_path.strip():
        return directory_path
    return get_default_vault_path()
