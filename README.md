# benchling-agent

An AI agent that writes [Benchling](https://www.benchling.com/) notebook entries using the Claude API. Accessible via CLI or a Discord bot.

## Features

- **Claude-powered entry writing** — describe what you want and the agent drafts structured Benchling notebook entries
- **Research mode** — ask the agent to look up information before writing
- **CLI interface** — run from your terminal
- **Discord bot** — interact from a Discord channel
- **Extensible** — designed so new capabilities can be added easily

## Quickstart

### Prerequisites

- Python ≥ 3.13
- [uv](https://docs.astral.sh/uv/) package manager
- API keys for Anthropic (Claude) and Benchling

### Installation

```bash
# Clone and install
git clone https://github.com/syugateway/benchling-agent.git
cd benchling-agent
uv sync

# Configure
cp .env.example .env
# Edit .env with your API keys
```

### Usage

#### CLI

```bash
# Write a Benchling entry
uv run benchling-agent write --prompt "Document today's PCR experiment results..."

# Research mode
uv run benchling-agent research --query "What are best practices for CRISPR guide RNA design?"
```

#### Discord Bot

```bash
uv run benchling-agent discord
```

Then in Discord: `!write Document today's PCR experiment...`

## Development

```bash
# Install dev dependencies
uv sync --group dev

# Run tests
uv run pytest

# Lint
uv run ruff check src/ tests/
```

## Architecture

```
src/benchling_agent/
├── config.py               # Settings (env vars via pydantic-settings)
├── agent.py                # Core orchestrator
├── clients/
│   ├── claude.py           # Anthropic/Claude API wrapper
│   └── benchling.py        # Benchling API wrapper
└── interfaces/
    ├── cli.py              # Click CLI
    └── discord_bot.py      # Discord bot
```

## License

MIT
