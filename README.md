# Agent Council

A small multi-agent system, built on [Google's Agent Development Kit (ADK)](https://google.github.io/adk-docs/), that maintains a vault of markdown notes (e.g. an Obsidian vault). Three role-played agents take turns in a loop to plan, edit, and review changes to your notes.

## How it works

`my_agent/agent.py` defines a `LoopAgent` (`root_agent`) made of three sub-agents that run in sequence, up to 3 iterations:

1. **Orchestrator** (`orchestrator`) — a strict "manager" persona. Lists the markdown files in the vault (recursively) and reads the target file, then plans out what needs to change and instructs the Editor. Never edits files itself.
2. **Editor** (`groq_editor`) — a Gollum-esque persona. Sends the note (or just one section) to Groq to rewrite it, and can create new files or link notes together.
3. **Reviewer** (`reviewer`) — an aggressive "critic" persona. Re-reads the file and checks whether it matches what was requested. If it's correct, it calls the `exit_loop` tool to actually end the review; otherwise it sends the Editor back to fix it.

All three agents run on Gemini (`gemini-flash-latest`) via ADK. The actual markdown edits are delegated to Groq's OpenAI-compatible API, so the "editing" LLM is decoupled from the "reasoning" LLMs.

### Safety model

- **Vault-relative paths only.** Every tool resolves paths against the configured vault root and refuses anything that would escape it (absolute paths, `../` traversal). See `resolve_vault_path` / `resolve_note_reference` in `my_agent/tools/config.py`.
- **Edits are validated before they're written.** `edit_markdown_with_groq` rejects a Groq response that looks like it silently dropped content — much shorter than the original, or missing wikilinks/embeds/code fences/frontmatter — unless the edit instructions clearly asked for that removal. Rejected edits never touch the file.
- **Backups.** Every accepted edit writes a timestamped copy of the original to `.agent-backups/` inside the vault before overwriting it. That folder (along with `.obsidian/` and `.trash/`) is excluded from listings.
- **Dry runs.** Pass `dry_run=True` to `edit_markdown_with_groq` to see the diff without writing anything.
- **The loop actually stops.** ADK's `LoopAgent` only stops early when a sub-agent escalates (or `max_iterations` is hit) — a sub-agent's reply merely containing the word "STOP" does nothing. The Reviewer calls ADK's built-in `exit_loop` tool to escalate once it approves.

## Project structure

```
my_agent/
  agent.py                 # Defines the orchestrator/editor/reviewer agents and the LoopAgent
  tools/
    config.py               # Vault path resolution/safety, env vars, loads .env
    markdown_utils.py        # Pure markdown helpers: frontmatter/headings/links, edit validation, diffing, sections
    list_files.py            # list_markdown_files tool (recursive)
    read_markdown.py         # read_note tool (frontmatter/headings/links/checkboxes); parse_roadmap_markdown alias
    create_files.py          # create_markdown_file tool
    edit_groq.py             # edit_markdown_with_groq tool (calls Groq's API, validates + backs up)
    link_files.py             # link_notes and suggest_links tools
  requirements.txt
  requirements-dev.txt      # requirements.txt + pytest, for running the test suite
  .env.example
tests/                      # pytest suite against a temporary fake vault (see Testing, below)
Caddyfile                  # Optional reverse-proxy config for exposing the ADK web UI over HTTPS
```

## Setup

1. **Install dependencies** (Python 3.11+ recommended):

   ```bash
   pip install -r my_agent/requirements.txt
   ```

2. **Configure environment variables.** Copy the example env file and fill in your own values:

   ```bash
   cp my_agent/.env.example my_agent/.env
   ```

   | Variable | Required | Description |
   |---|---|---|
   | `OBSIDIAN_VAULT_PATH` (or `VAULT_PATH`) | No | Absolute path to your markdown vault. Falls back to an `obsidian_vault/` folder in the project root if unset. |
   | `GOOGLE_API_KEY` | Yes | API key for Gemini, used by all three agents via `google-adk`. |
   | `GROQ_API_KEY` | Yes | API key for Groq, used by the editor's `edit_markdown_with_groq` tool. |
   | `GROQ_MODEL` | No | Overrides the Groq model used for edits (default: `openai/gpt-oss-120b`). |

   The `.env` file is loaded automatically by `my_agent/tools/config.py` and is git-ignored.

3. **Run the agent.** ADK looks for a package exposing a `root_agent` (see `my_agent/__init__.py` / `agent.py`), so from the project root you can run either the ADK web UI or the CLI runner:

   ```bash
   adk web       # launches a local web UI to chat with the agent council
   # or
   adk run my_agent
   ```

   Point it at a note in your vault and ask it to update/fix something — the Orchestrator will plan, the Editor will rewrite the file via Groq, and the Reviewer will approve or send it back for another pass (up to 3 loop iterations).

## Testing

```bash
pip install -r my_agent/requirements-dev.txt
pytest
```

The suite in `tests/` builds a temporary fake vault per test (nested folders, frontmatter, wikilinks, embeds, a callout, a code fence) and never touches a real vault. It mocks the Groq client, so no `GROQ_API_KEY` is needed to run it.

## Manual end-to-end run

Always test against a **copy** of a vault, never the real one — `edit_markdown_with_groq` writes in place (with a validated backup, but still).

```bash
cp -r "/path/to/your/real/vault" /tmp/vault-copy
```

Then, from the project root:

```bash
export OBSIDIAN_VAULT_PATH=/tmp/vault-copy
adk web       # or: adk run my_agent
```

Open the web UI, pick `my_agent`, and try something like:
> "Read `<some note>` and expand the intro section, then link it to `<another note>`."

Watch the Editor's reply for the `diff_summary` and `backup_path` it reports, and check `/tmp/vault-copy/.agent-backups/` for the pre-edit copy. If you want to see the safety checks in action without risking a real note, ask it to do a dry run first (`dry_run=True`), or give it a vague instruction that could plausibly make Groq truncate the note (e.g. "rewrite this note") without asking for anything to be removed — if the response comes back much shorter or missing links/code blocks, the Editor should report a `"rejected"` status instead of silently overwriting the note.

### Optional: exposing the web UI

`Caddyfile` contains a sample [Caddy](https://caddyserver.com/) reverse-proxy config that terminates TLS and forwards to `localhost:8003` (the default `adk web` port). It's set up for a specific local IP address — treat it as a template and edit the address/port for your own network before using it.

## Example run

A run in the ADK web UI (`adk web`), asking the agent council to inventory and clean up a real Obsidian vault:

**The Orchestrator scans the vault and hands the Editor its assignment.**
![Orchestrator lists the vault's markdown files](images/01-orchestrator-lists-files.png)

**The Orchestrator issues a precise directive after the Reviewer flags a messy file.**
![Orchestrator gives the Editor a detailed cleanup directive](images/02-orchestrator-directive.png)

**The Editor calls `edit_markdown_with_groq` and reports the result; the Reviewer signs off with `STOP`.**
![Editor applies the edit via Groq and the Reviewer approves](images/03-editor-applies-edit.png)

**A follow-up request in the same session — the Boss issues a new directive.**
![Boss gives a new directive for a follow-up request](images/04-boss-new-directive.png)

**The Editor confirms the change and the loop wraps up.**
![Editor confirms the edit and the council stands down](images/05-editor-confirms-and-wraps-up.png)

## Known limitations / notes

- `read_note` (formerly `parse_roadmap_markdown`, kept as an alias) expects GitHub-style task checkboxes (`- [ ]` / `- [x]`) to extract milestones; other list formats aren't recognized.
- Heading/frontmatter/link parsing in `markdown_utils.py` is regex-based, not a full CommonMark parser — it's good enough for validation and section-editing, but e.g. a `#` inside a fenced code block could be misread as a heading.
- The edit-loss checks (`validate_edit`) skip themselves entirely when the instructions contain a removal-sounding word (e.g. "remove", "trim", "condense") — it's a heuristic, not true intent detection, so it can be too lenient or too strict on unusual phrasing.
- Backups accumulate in `.agent-backups/` with no automatic pruning; clean it up periodically if you edit a lot.
- `LoopAgent` is deprecated in the currently pinned `google-adk` in favor of `Workflow`, which doesn't yet support being nested as an `LlmAgent` sub-agent — this project intentionally keeps `LoopAgent` for now.
