# Gemini Web Automation

[中文](README.md) | <https://github.com/lainXXX/gemini-web-automation-skill>

A Python runtime for browser-automated [Gemini](https://gemini.google.com/app) access, designed for AI Agent integration.

## About

Your everyday models (DeepSeek V4 Flash, Doubao, GLM, Qwen, Kimi) are fast and cheap — but when it comes to truly hard problems, they fall short. Deep brainstorming, technical design, architecture planning, detailed specification writing — these tasks demand **Gemini 2.5 Pro with extended thinking**.

This project bridges that gap.

It lets any AI Agent (Claude Code, etc.) call upon Gemini's strongest capabilities when the task is too hard for the daily driver. Keep using your cheap model for routine work; hand the tough problems to Gemini.

## What It's For

- **Brainstorming & Solution Design** — Let Gemini Pro's deep thinking decompose complex problems and produce high-quality solutions
- **Writing Specs & Plans** — Technical proposals, PRDs, architecture documents — Gemini's extended thinking excels at structured output
- **Multimodal Assistance** — Your model doesn't have vision? Let Gemini (default 3.5 Flash) analyze images, screenshots, and UI for you
- **Any task that needs "real thinking"** — The kind of depth your daily model can't deliver

## Features

- **Session persistence** — Log in once, reuse the browser profile across runs
- **Warm/Cold start** — Connect to an existing Chrome via CDP first, auto-launch a new instance if needed
- **Model management** — Auto-detect, switch, and verify models and thinking levels (standard/extended)
- **Image attachments** — Paste images into conversations
- **Structured JSON output** — `ok`, `contract`, `reply`, `error.code`, `next_action`
- **Health check** — Quick runtime status without starting a conversation
- **Proxy support** — HTTP, HTTPS, SOCKS5

## Quick Start

```bash
# 1. Clone
git clone https://github.com/lainXXX/gemini-web-automation-skill.git
cd gemini-web-automation-skill

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

### Agent Integration (Claude Code example)

Declare the skill in your SKILL.md or CLAUDE.md so your agent knows when to use it:

```yaml
- Routine work: handled by my default model
- Hard tasks (brainstorming, solution design, specs, plans):
  1. Call gemini-web-automation-skill
  2. Use Gemini's response as reference to continue working
```

Default configuration: **Gemini 2.5 Pro + extended thinking** for tough problems; **3.5 Flash** as a multimodal assistant (for models without vision capabilities).

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
