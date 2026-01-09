# Agent Proxy Skill

Auto-discover and communicate with any AI agent given its URL. Claude Code acts as the user, automatically detecting the agent's interface and sending messages on behalf of the user.

## Features

- **Auto-Detection**: Automatically identifies agent type (API, WebSocket, Web UI)
- **Multi-Protocol Support**: REST API, WebSocket, Gradio, Streamlit, Browser automation
- **Smart Completion Detection**: Intelligently waits for agent to finish responding
- **Login Persistence**: Saves browser sessions for web-based agents
- **Anti-Detection**: Bypasses bot detection for web automation

## Supported Agent Types

### API-based Agents

| Type | URL Pattern | Protocol |
|------|-------------|----------|
| OpenAI API | `*/v1/chat/completions` | POST JSON |
| Anthropic API | `*/v1/messages` | POST JSON |
| Ollama | `*/api/chat`, `*/api/generate` | POST JSON |
| WebSocket | `ws://`, `wss://` | WebSocket |
| Gradio | Gradio apps | gradio_client |

### Web-based Agents (Browser Automation)

| Agent | URL | Status |
|-------|-----|--------|
| Google Gemini | gemini.google.com | ✅ Tested |
| ChatGPT | chat.openai.com | ✅ Supported |
| Claude | claude.ai | ✅ Supported |
| Poe | poe.com | ✅ Supported |
| HuggingFace Chat | huggingface.co/chat | ✅ Supported |
| Unknown UIs | Any URL | 🔍 Auto-detect |

## Installation

### 1. Copy skill to Claude Code

```bash
cp -r skills/agent-proxy ~/.claude/skills/
```

### 2. Install dependencies

```bash
# For API-based agents
pip install requests

# For web-based agents
pip install playwright
playwright install chromium
```

## Usage

### Command Line

```bash
cd ~/.claude/skills/agent-proxy/scripts

# API-based agent (Ollama)
python talk.py --url http://localhost:11434 -m "Hello!"

# Web-based agent (Gemini) - first time login
python browser_adapter.py "https://gemini.google.com" --user-data-dir ~/.gemini-profile -m "Hello!"

# Web-based agent - with saved login
python browser_adapter.py "https://gemini.google.com" --user-data-dir ~/.gemini-profile -m "What is AI?"
```

### Python API

```python
from agent_proxy import AgentProxy

# API-based agent
proxy = AgentProxy()
proxy.connect("http://localhost:11434")
response = proxy.say("Hello!")
print(response)
proxy.close()

# Web-based agent
from browser_adapter import WebUIProxy

proxy = WebUIProxy()
proxy.connect("https://gemini.google.com", user_data_dir="~/.gemini-profile")
proxy.wait_for_login()  # Wait for manual login if needed
response = proxy.say("What is 1+1?")
print(response)
proxy.close()
```

## How It Works

### Detection Flow

```
URL Input
    │
    ▼
┌─────────────────────┐
│  Check URL Pattern  │──► OpenAI/Anthropic/Ollama API
└─────────────────────┘
    │ Unknown
    ▼
┌─────────────────────┐
│   Probe Endpoint    │──► JSON API / WebSocket
└─────────────────────┘
    │ HTML Response
    ▼
┌─────────────────────┐
│  Check Known UIs    │──► Gemini/ChatGPT/Claude config
└─────────────────────┘
    │ Unknown
    ▼
┌─────────────────────┐
│  Auto-Detect UI     │──► Find input/button/response elements
└─────────────────────┘
```

### Smart Completion Detection

The skill uses multiple signals to determine when an agent has finished responding:

1. **Text Stability**: Response text unchanged for 2+ seconds
2. **Button State**: Send button re-enabled
3. **Loading Indicators**: Spinners/typing indicators disappeared

```python
Completion = (TextStable AND ButtonReady) OR
             (TextStable AND NoLoadingIndicator) OR
             (TextStable for 3+ seconds)
```

## Configuration

### Browser Adapter Options

```python
proxy.connect(url, {
    "headless": False,           # Show browser window
    "user_data_dir": "~/.profile", # Save login state
    "use_chrome": True,          # Use system Chrome (vs Chromium)
    "input_selector": "...",     # Override input element
    "submit_selector": "...",    # Override submit button
    "response_selector": "...",  # Override response element
})
```

### Adding Support for New Web UIs

Edit `browser_adapter.py` and add to `KNOWN_WEB_UIS`:

```python
"my_agent": WebUIConfig(
    name="My Agent",
    url_pattern=r"myagent\.com",
    input_selector='textarea[placeholder="Message"]',
    submit_selector='button[type="submit"]',
    response_selector='.assistant-message',
    wait_for_response='.assistant-message',
    login_required=True,
    extra_wait=2.0,
),
```

## Files

| File | Description |
|------|-------------|
| `SKILL.md` | Skill metadata for Claude Code |
| `agent_proxy.py` | Main proxy class for API-based agents |
| `browser_adapter.py` | Browser automation for web-based agents |
| `detect_agent.py` | Agent type detection logic |
| `talk.py` | CLI interface |

## Troubleshooting

### "Browser not secure" error from Google

Google detects Playwright's Chromium. Solution: Use system Chrome with anti-detection:

```python
# Already enabled by default
config = {"use_chrome": True}
```

### Empty response from web agent

The response selector may not match. Debug with:

```python
# Take screenshot to see page state
proxy.screenshot("/tmp/debug.png")

# Check available elements
elements = proxy.page.query_selector_all("*")
```

### Login not persisting

Ensure you're using `user_data_dir`:

```bash
python browser_adapter.py "https://..." --user-data-dir ~/.my-profile
```

## License

MIT License
