import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

NOTE_WITH_FRONTMATTER = """---
title: Explore core data concepts
tags: [azure, dp900]
---

# Explore core data concepts

Some intro text about relational and non-relational data concepts.

> [!note]
> This is a callout with a tip inside it.

## Core concepts

- [[Relational data]]
- ![[diagram.png]]

- [ ] Study cosmos db
- [x] Study relational data

```python
print("hello world")
```

## Related notes

[[Home]]
"""

SIMPLE_NOTE = """# Relational data

Relational data is stored in tables with rows and columns, and is queried
with structured query languages like SQL.

## Details

More details about relational data go here, including normalization and
primary/foreign keys.
"""


def _build_vault(root: Path) -> Path:
    vault = root / "vault"
    nested = vault / "Portfolio Project" / "Azure DP900" / "Core Data Concepts"
    nested.mkdir(parents=True)
    (nested / "Explore core data concepts.md").write_text(NOTE_WITH_FRONTMATTER, encoding="utf-8")

    (vault / "Relational data.md").write_text(SIMPLE_NOTE, encoding="utf-8")

    obsidian_dir = vault / ".obsidian"
    obsidian_dir.mkdir()
    (obsidian_dir / "workspace.json").write_text("{}", encoding="utf-8")

    trash_dir = vault / ".trash"
    trash_dir.mkdir()
    (trash_dir / "deleted note.md").write_text("# gone", encoding="utf-8")

    return vault


@pytest.fixture
def vault(tmp_path, monkeypatch):
    """A fake vault with nested folders, frontmatter, wikilinks, embeds,
    a callout, a code fence and excluded folders (.obsidian/, .trash/)."""
    vault_root = _build_vault(tmp_path)
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault_root))
    monkeypatch.delenv("VAULT_PATH", raising=False)
    return vault_root
