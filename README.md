# benchling-agent

An AI agent that writes [Benchling](https://www.benchling.com/) notebook entries using the Claude API. Provide a natural-language prompt via CLI or Discord and the agent drafts the entry content, creates the entry in Benchling, and writes the body directly into the notebook using browser automation.

## Features

- **Claude-powered drafting** — describe what you need and Claude generates a structured notebook entry with headings, bullet lists, bold text, and tables
- **Native Benchling formatting** — content is written into the editor via keyboard automation, producing real Benchling headings, lists, and native table widgets (not pasted HTML)
- **Browser automation** — uses Playwright to drive Chrome; OAuth sessions are persisted so you only log in once
- **CLI and Discord interfaces** — run commands locally or from a Discord channel
- **Configurable defaults** — set a default folder so you don't need to supply IDs on every command

## How It Works

1. You provide a prompt describing the entry (e.g. *"Document today's PCR amplification results for samples A1–A3"*)
2. Claude generates a **title** and **markdown body** in a single API call
3. The agent creates a new entry in Benchling via the API, with the title prefixed by today's date (`yyyy.mm.dd - Title`)
4. Playwright opens the entry in Chrome and types the content into Benchling's editor:
   - **Headings** are inserted via `/Header 1`, `/Header 2`, `/Subheader 1` slash commands
   - **Bold text** is toggled with `Cmd/Ctrl+B`
   - **Bullet lists** are toggled via the toolbar button, with `Tab`/`Shift+Tab` for nesting
   - **Tables** are inserted as native Benchling table widgets: columns are added and renamed via the context menu, rows are added via the add-rows UI, and cell data is pasted as TSV from the clipboard
5. The Discord bot replies with a clickable link to the entry; the CLI prints the URL

## Quickstart

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager
- Google Chrome (for browser automation)
- API keys for [Anthropic](https://console.anthropic.com/) and [Benchling](https://docs.benchling.com/docs/getting-started)

### Installation

```bash
git clone https://github.com/phtevenn/benchling-agent.git
cd benchling-agent
uv sync
```

### Configuration

Copy the example env file and fill in your keys:

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude |
| `BENCHLING_API_URL` | Your Benchling tenant URL (e.g. `https://acme.benchling.com`) |
| `BENCHLING_API_KEY` | Benchling API key |
| `DISCORD_BOT_TOKEN` | Discord bot token (only needed for the Discord interface) |

Set your default Benchling folder so you don't need to pass a folder ID on every write:

```bash
uv run benchling-agent configure --folder "My Folder Name"
```

### Browser Login

The agent writes entry bodies via browser automation. You need to log in once so the session can be saved:

```bash
uv run benchling-agent login
```

This opens Chrome, navigates to your Benchling tenant, and waits for you to complete OAuth/SSO login. The session cookies are saved to `~/.benchling-agent/browser-state.json` and reused on subsequent runs.

## Usage

### CLI

```bash
# Write a Benchling entry
uv run benchling-agent write -p "Document PCR amplification of samples A1-A3 using Q5 polymerase"

# Write with an explicit entry name
uv run benchling-agent write -p "LPS pilot results" --name "LPS Pilot Time Course"

# Research a topic
uv run benchling-agent research -q "Best practices for CRISPR guide RNA design"

# Set default folder
uv run benchling-agent configure --folder "Stephen Yu"

# Browser login
uv run benchling-agent login
```

### Discord Bot

Start the bot:

```bash
uv run benchling-agent discord
```

Then in any channel the bot can see:

```
!write Document today's PCR experiment with Q5 polymerase for samples A1-A3
!research What are the recommended storage conditions for mRNA vaccines?
!configure My Folder Name
```

The `!write` command replies with a link to the created entry. The `!research` command replies with Claude's summary directly in Discord.

## Architecture

```
src/benchling_agent/
├── config.py               # Settings from env vars (pydantic-settings)
├── user_config.py          # Persistent user prefs (~/.benchling-agent/config.json)
├── agent.py                # Core orchestrator: routes write/research actions
├── clients/
│   ├── claude.py           # Anthropic API: drafts entry title + markdown body
│   ├── benchling.py        # Benchling SDK: creates entries, lists folders
│   ├── browser.py          # Playwright: writes content into Benchling's editor
│   └── content_parser.py   # Converts markdown → sequence of editor actions
└── interfaces/
    ├── cli.py              # Click CLI (write, research, configure, login, discord)
    └── discord_bot.py      # Discord bot (!write, !research, !configure)
```

### Content Pipeline

```
User prompt
    → Claude API (markdown output)
    → content_parser (markdown → EditorAction list)
    → BenchlingBrowser (executes actions via Playwright keyboard/toolbar/clipboard)
    → Benchling entry with native formatting
```

The `content_parser` module translates markdown into a flat list of `EditorAction` objects, each representing one block: a heading, paragraph, bullet item, table, or blank line. `BenchlingBrowser._execute_actions` walks this list and drives the editor accordingly.

## Development

```bash
# Install with dev dependencies
uv sync --group dev

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=benchling_agent

# Lint
uv run ruff check src/ tests/
```

## License

MIT
