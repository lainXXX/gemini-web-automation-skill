# Gemini Web Automation

[中文](README.md)

A Python runtime for interacting with [Gemini](https://gemini.google.com/app) through browser automation — send prompts, upload images, switch models, and retrieve replies, all returned as structured JSON.

Built for AI Agent integration (Claude Code, etc.), also usable as a standalone CLI tool.

## Features

- **Session persistence** — Log in once, reuse the browser profile across runs
- **Warm/Cold start** — Connect to an existing Chrome via CDP first, auto-launch a new instance if needed
- **Model management** — Auto-detect, switch, and verify models and thinking levels (standard/extended)
- **Image attachments** — Paste images into conversations
- **Structured JSON output** — `ok`, `contract`, `reply`, `error.code`, `next_action`
- **Health check** — Quick runtime status without starting a conversation
- **Proxy support** — HTTP, HTTPS, SOCKS5

## Requirements

- Python 3.9+
- Google Chrome, Chromium, or Microsoft Edge
- A Google account with access to [Gemini](https://gemini.google.com)
- (For users in China) A proxy that can reach Google services

## Quick Start

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/gemini-web-automation.git
cd gemini-web-automation

# 2. Configure
cp .env.example .env
# Edit .env — users in China must set PROXY_SERVER

# 3. Install dependencies and log in
python scripts/bootstrap.py

# 4. Start chatting
python scripts/chat.py "Hello, Gemini!"
```

`bootstrap.py` launches Chrome and opens the Gemini login page. Log in manually and you're ready to go.

## Usage

### CLI

```bash
# Send a message
python scripts/chat.py "Explain quantum computing"

# Attach an image
python scripts/chat.py "What's in this photo?" -a photo.jpg

# Health check
python scripts/chat.py --health

# Keep browser window visible
python scripts/chat.py --headed "Hello"

# Dry-run (test model switching only, no conversation)
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

| Error Code | Description |
|---|---|
| `LOGIN_REQUIRED` | Not logged in — run `bootstrap.py` |
| `ENV_NOT_FOUND` | `.env` missing — copy from `.env.example` |
| `PROXY_REQUIRED` | Cannot reach Gemini — check proxy |
| `MODEL_MISMATCH` | Requested model unavailable |
| `STREAM_TIMEOUT` | AI reply timed out |

## Configuration

See `.env.example` for details:

| Variable | Default | Description |
|---|---|---|
| `CHROME_PATH` | Auto-detect | Chrome executable path |
| `USER_DATA_DIR` | `./userdata` | Browser profile directory for login persistence |
| `REMOTE_DEBUGGING_PORT` | `9222` | CDP port |
| `PROXY_SERVER` | — | Proxy for Google access (required in China) |
| `MODEL_NAME` | `Pro` | Default model (Pro, Flash, Flash-Lite) |
| `THINKING_LEVEL` | `extended` | Thinking level (extended, standard) |

## How It Works

```
chat.py
  │
  ├── 1. Environment check (.env, network, proxy)
  ├── 2. Connect to Chrome (CDP warm start → cold start fallback)
  ├── 3. Ensure Gemini page (reuse existing tab or open new one)
  ├── 4. Ensure model (switch to desired model/thinking level if needed)
  ├── 5. Send prompt (optionally with image attachment)
  └── 6. Stream reply (wait for stability → return JSON)
```

The runtime reuses Chrome's user data directory, so login state persists across runs. Cold start (launching a new Chrome) only happens when no existing Chrome instance has the correct profile.

## Project Structure

```
├── scripts/
│   ├── chat.py          # Main runtime — the only entry point for daily use
│   └── bootstrap.py     # One-time setup: login wizard
├── references/
│   ├── architecture.md  # Design decisions
│   ├── gemini.md        # Page interaction selectors and patterns
│   └── maintenance.md   # Troubleshooting and anti-patterns
├── .env.example         # Configuration template
├── CHANGELOG.md
└── SKILL.md             # Agent integration guide
```

## License

MIT
