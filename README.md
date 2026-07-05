# Gemini Web Automation

A Python runtime that automates [Gemini](https://gemini.google.com/app) through the browser — send prompts, upload images, switch models, and collect replies via a structured JSON API.

Designed for integration with AI agents (Claude Code, etc.) but usable as a standalone CLI tool.

## Features

- **Session persistence** — login once, reuse the browser profile across runs
- **Warm/Cold start** — connects to running Chrome via CDP when available, auto-launches otherwise
- **Model management** — discover, switch, and verify models + thinking levels (standard/extended)
- **Image attachment** — paste images into conversations
- **Structured JSON output** — `ok`, `contract`, `reply`, `error.code`, `next_action`
- **Health check** — quick runtime status without conversation
- **Proxy support** — HTTP, HTTPS, SOCKS5

## Prerequisites

- Python 3.9+
- Google Chrome, Chromium, or Microsoft Edge
- A Google account with access to [Gemini](https://gemini.google.com)
- (China users) A proxy that can reach Google services

## Quick Start

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/gemini-web-automation.git
cd gemini-web-automation

# 2. Configure
cp .env.example .env
# Edit .env — set PROXY_SERVER if needed

# 3. Install dependencies & login
python scripts/bootstrap.py

# 4. Chat
python scripts/chat.py "Hello, Gemini!"
```

`bootstrap.py` opens Chrome, you log into Google manually, then you're ready.

## Usage

### CLI

```bash
# Send a message
python scripts/chat.py "Explain quantum computing"

# With image attachment
python scripts/chat.py "What's in this image?" -a photo.jpg

# Health check
python scripts/chat.py --health

# Keep browser visible
python scripts/chat.py --headed "Hello"

# Model dry-run (no message sent)
python scripts/chat.py --dry-run "test"
```

### JSON Response Format

```json
{
  "protocol": "gemini-runtime-api",
  "api_version": "1.3",
  "request_id": "20260705-175528-5e03",
  "contract": {
    "expected": {"model": "Pro", "thinking": "extended"},
    "actual": {"model": "Pro", "thinking": "extended"}
  },
  "ok": true,
  "reply": "Hello! How can I help you today?"
}
```

On error:

```json
{
  "ok": false,
  "error": {"code": "LOGIN_REQUIRED"},
  "next_action": "RUN_BOOTSTRAP"
}
```

| Error Code | Meaning |
|---|---|
| `LOGIN_REQUIRED` | Not logged in — run `bootstrap.py` |
| `ENV_NOT_FOUND` | `.env` missing — copy from `.env.example` |
| `PROXY_REQUIRED` | Cannot reach Gemini — check proxy |
| `MODEL_MISMATCH` | Expected model not available |
| `STREAM_TIMEOUT` | AI response timed out |

## Configuration

See `.env.example` for all options:

| Variable | Default | Description |
|---|---|---|
| `CHROME_PATH` | auto-detect | Chrome executable path |
| `USER_DATA_DIR` | `./userdata` | Browser profile for login persistence |
| `REMOTE_DEBUGGING_PORT` | `9222` | CDP port |
| `PROXY_SERVER` | — | Proxy for Google access (China users: required) |
| `MODEL_NAME` | `Pro` | Default model family (Pro, Flash, Flash-Lite) |
| `THINKING_LEVEL` | `extended` | Thinking mode (extended, standard) |

## How It Works

```
chat.py
  │
  ├── 1. Environment check (.env, network, proxy)
  ├── 2. Connect to Chrome (CDP warm start → cold launch fallback)
  ├── 3. Ensure Gemini page (reuse existing tab or create new)
  ├── 4. Ensure model (switch to expected model/thinking level if needed)
  ├── 5. Send prompt (+ images if attached)
  └── 6. Stream reply (wait for stability → return JSON)
```

The runtime reuses Chrome's user data directory, so login state persists across runs. Cold start (launching a new Chrome) only happens when no existing Chrome instance with the correct profile is found.

## Project Structure

```
├── scripts/
│   ├── chat.py          # Main runtime — the only entry point for daily use
│   └── bootstrap.py     # One-time setup: login wizard
├── references/
│   ├── architecture.md  # Design decisions
│   ├── gemini.md        # Page interaction selectors & patterns
│   └── maintenance.md   # Troubleshooting & anti-patterns
├── .env.example         # Configuration template
├── CHANGELOG.md
└── SKILL.md             # Agent integration instructions
```

## License

MIT
