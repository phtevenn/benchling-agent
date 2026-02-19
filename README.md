# benchling-agent

An AI agent that writes [Benchling](https://www.benchling.com/) notebook entries using the Claude API. Chat through a Discord bot to plan experiments, then finalize and create the entry in Benchling with a single command.

## Features

- **Conversational experiment planning** — discuss objectives, materials, and methods with Claude over multiple messages in Discord; the agent remembers the whole conversation
- **Approval-gated entry creation** — `/finalize` drafts an entry for review; `/confirm` creates it; `/cancel` discards it
- **Structured entry template** — every entry follows a fixed four-section layout: Purpose, Materials, Methods, Results (Results is always left empty for you to fill in)
- **Native Benchling formatting** — content is written into the editor via keyboard automation, producing real Benchling headings, bullet lists, numbered lists, and native table widgets (not pasted HTML)
- **Browser automation** — uses Playwright to drive Chrome; OAuth sessions are persisted so you only log in once
- **CLI interface** — write entries directly from the terminal without Discord

## How It Works

1. Chat with the bot in Discord to describe your experiment — Claude asks clarifying questions and builds context over multiple messages
2. When ready, run `/finalize` — Claude drafts a structured entry (title + body) and posts a preview
3. Review the preview; run `/confirm` to create the entry in Benchling or `/cancel` to go back to chatting
4. The agent creates the entry via the Benchling API, then Playwright types the content into the editor:
   - **Headings** are inserted via `/Header 1`, `/Header 2`, `/Subheader 1` slash commands
   - **Bold text** is toggled with `Cmd/Ctrl+B`
   - **Bullet lists** are entered by typing `- ` (inputrule), with `Tab`/`Shift+Tab` for nesting
   - **Numbered lists** are entered by typing `1. ` (inputrule); subsequent items are auto-numbered
   - **Tables** are inserted as native Benchling table widgets: columns are added and renamed via the context menu, rows are added via the add-rows UI, and cell data is pasted as TSV from the clipboard
5. The bot replies with a clickable link to the created entry

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

### Discord Bot

Start the bot:

```bash
uv run benchling-agent discord
```

**Slash commands:**

| Command | Description |
|---|---|
| `/configure folder:<name>` | Set the default Benchling folder for new entries |
| `/finalize` | Draft a Benchling entry from the current conversation and show a preview |
| `/confirm` | Create the previewed entry in Benchling |
| `/cancel` | Discard the pending draft and resume chatting |
| `/reset` | Clear conversation history and start fresh |

**Workflow example:**

```
You:  We ran an LPS dose-response in PBMCs overnight using the HEK-Blue TNF reporter.
      Doses were 0, 1, 10, 100 ng/mL. Triplicates. OD 655nm readout.

Bot:  Got it. What cell density did you plate at, and how long was the stimulation?

You:  500k cells/mL, 18 hours.

Bot:  Any notable observations before readout?

You:  One well in the 100 ng/mL condition looked cloudy — possible contamination.

You:  /finalize

Bot:  Draft entry preview:
      Title: 2026.02.18 - LPS Dose-Response in PBMCs with HEK-Blue TNF Reporter
      ...

You:  /confirm

Bot:  Entry created: https://acme.benchling.com/...
```

Free-form messages are handled as multi-turn conversation with Claude. Messages starting with `/` are treated as commands.

### CLI

```bash
# Write a Benchling entry directly from a prompt
uv run benchling-agent write -p "Document PCR amplification of samples A1-A3 using Q5 polymerase"

# Write with an explicit entry name
uv run benchling-agent write -p "LPS pilot results" --name "LPS Pilot Time Course"

# Set default folder
uv run benchling-agent configure --folder "Stephen Yu"

# Browser login
uv run benchling-agent login
```

## Architecture

```
src/benchling_agent/
├── config.py               # Settings from env vars (pydantic-settings)
├── user_config.py          # Persistent user prefs (~/.benchling-agent/config.json)
├── agent.py                # Core orchestrator: converse, propose, create entry
├── session.py              # In-memory per-channel conversation state for Discord
├── clients/
│   ├── claude.py           # Anthropic API: multi-turn chat and entry drafting
│   ├── benchling.py        # Benchling SDK: creates entries, lists folders
│   ├── browser.py          # Playwright: writes content into Benchling's editor
│   └── content_parser.py   # Converts markdown → sequence of editor actions
└── interfaces/
    ├── cli.py              # Click CLI (write, configure, login, discord)
    └── discord_bot.py      # Discord bot (slash commands + free-form conversation)
```

### Content Pipeline

```
Conversation history
    → Claude API (structured markdown output)
    → content_parser (markdown → EditorAction list)
    → BenchlingBrowser (executes actions via Playwright keyboard/clipboard)
    → Benchling entry with native formatting
```

The `content_parser` module translates markdown into a flat list of `EditorAction` objects, each representing one block: a heading, paragraph, bullet item, numbered list item, table, or blank line. `BenchlingBrowser._execute_actions` walks this list and drives the editor accordingly.

### Session Management

Each Discord channel gets an independent `ConversationSession` stored in memory. Sessions hold the message history (capped at 50 messages) and any pending draft. Use `/reset` to clear a session when switching between experiments.

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
