# Agent Council

A small multi-agent system, built on [Google's Agent Development Kit (ADK)](https://google.github.io/adk-docs/), that maintains a vault of markdown notes (e.g. an Obsidian vault). Three role-played agents take turns in a loop to plan, edit, and review changes to your notes.

## How it works

`my_agent/agent.py` defines a `LoopAgent` (`root_agent`) made of three sub-agents that run in sequence, up to 3 iterations:

1. **Orchestrator** (`orchestrator`) — a strict "manager" persona. Lists the markdown files in the vault and reads the target file, then plans out what needs to change and instructs the Editor. Never edits files itself.
2. **Editor** (`groq_editor`) — a Gollum-esque persona. Sends the file content and instructions to Groq (Llama) to actually rewrite the markdown, and can create new files or link files together.
3. **Reviewer** (`reviewer`) — an aggressive "critic" persona. Re-reads the file and checks whether it matches what was requested. If it's correct, it outputs `STOP` to end the loop; otherwise it sends the Editor back to fix it.

All three agents run on Gemini (`gemini-flash-latest`) via ADK. The actual markdown edits are delegated to Groq's OpenAI-compatible API, so the "editing" LLM is decoupled from the "reasoning" LLMs.

## Project structure

```
my_agent/
  agent.py                 # Defines the orchestrator/editor/reviewer agents and the LoopAgent
  tools/
    config.py               # Resolves the vault path from env vars, loads .env
    list_files.py            # list_markdown_files tool
    read_markdown.py         # parse_roadmap_markdown tool (extracts [ ] / [x] checkboxes)
    create_files.py          # create_markdown_file tool
    edit_groq.py             # edit_markdown_with_groq tool (calls Groq's API)
    link_files.py             # file_linker tool (adds [[wiki-links]] between notes)
  requirements.txt
  .env.example
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

   The `.env` file is loaded automatically by `my_agent/tools/config.py` and is git-ignored.

3. **Run the agent.** ADK looks for a package exposing a `root_agent` (see `my_agent/__init__.py` / `agent.py`), so from the project root you can run either the ADK web UI or the CLI runner:

   ```bash
   adk web       # launches a local web UI to chat with the agent council
   # or
   adk run my_agent
   ```

   Point it at a note in your vault and ask it to update/fix something — the Orchestrator will plan, the Editor will rewrite the file via Groq, and the Reviewer will approve or send it back for another pass (up to 3 loop iterations).

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

- `parse_roadmap_markdown` expects GitHub-style task checkboxes (`- [ ]` / `- [x]`) to extract milestones; other list formats aren't recognized.
- The agents' tools take a vault-relative `directory_path`/`filename`, but `parse_roadmap_markdown` expects a full `file_path` — the agent has to combine the vault path and filename itself when reading a specific file.
- `edit_markdown_with_groq` overwrites the target file in place with whatever Groq returns; there's no diff/undo, so keep your vault under version control if you want to review changes.
