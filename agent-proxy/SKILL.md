---
name: agent-proxy
description: |
  Auto-discover and communicate with any AI agent given its URL. Claude Code acts as the user,
  automatically detecting the agent's interface (Web UI, REST API, WebSocket, etc.) and sending
  messages on behalf of the user. Use when: (1) User provides a URL to an AI agent/chatbot,
  (2) Need to automate conversations with external AI services, (3) Testing or evaluating agents,
  (4) Building agent-to-agent communication pipelines. Supports local and remote agents.
---

# Agent Proxy Skill

**Black-box agent communication**: Given a URL to any AI agent, this skill auto-discovers how to communicate with it and conducts conversations on the user's behalf.

**Critical**: This works WITHOUT needing:
- ❌ Access to the target agent's source code
- ❌ The target agent's dependencies installed
- ❌ Knowledge of the target agent's implementation

You only need the agent's **URL**.

## Installation

```bash
# Install agent-proxy dependencies
cd ~/.claude/skills/agent-proxy
pip install -r requirements.txt

# Optional: For browser automation (ChatGPT, Gemini, Claude, etc.):
playwright install chromium
```

## Workflow

```
User provides URL → Auto-detect Protocol → Create Protocol Adapter → Communicate (black-box)
```

## Quick Start

```python
from agent_proxy import AgentProxy

# Just give it a URL - it figures out the protocol automatically
proxy = AgentProxy()
proxy.connect("http://localhost:8080/chat")  # ANY agent URL

# Now Claude Code speaks AS the user
response = proxy.say("Hello, I need help with Python")
response = proxy.say("Can you show me an example?")

# Get full conversation
print(proxy.history)
proxy.close()
```

## Supported Agent Types (Auto-detected)

The skill auto-detects these communication patterns:

| URL Pattern | Detection | Method |
|-------------|-----------|--------|
| `*/v1/chat/completions` | OpenAI-compatible API | POST JSON |
| `*/v1/messages` | Anthropic API | POST JSON |
| `*/api/chat`, `*/api/generate` | Ollama/LLM APIs | POST JSON |
| `*/api/sessions`, `*/api/ws` | REST+WebSocket API | REST + WebSocket |
| `ws://`, `wss://` | WebSocket | WS messages |
| Gradio apps | Gradio API | gradio_client |
| Streamlit apps | Streamlit | HTTP/WS |
| HTML with chat input | Web UI | Browser automation |
| Custom endpoints | Probe & detect | Auto-detect |

### Web UI Support (Browser Automation)

These popular chat UIs are automatically detected and accessed via Playwright:

- **Google Gemini** (gemini.google.com)
- **ChatGPT** (chat.openai.com, chatgpt.com)
- **Claude** (claude.ai)
- **Poe** (poe.com)
- **HuggingFace Chat** (huggingface.co/chat)
- **Perplexity** (perplexity.ai)
- **Microsoft Copilot** (copilot.microsoft.com)

Requirements for Web UI:
```bash
pip install playwright
playwright install chromium
```

## Usage Modes

### Mode 1: Auto-Detect (Recommended)

```python
proxy = AgentProxy()
proxy.connect("https://some-agent.com/chat")  # Auto-detects protocol
response = proxy.say("Hello!")
```

### Mode 2: With Hints

```python
proxy = AgentProxy()
proxy.connect("https://api.example.com/v1/chat", hints={
    "type": "openai",  # Force OpenAI format
    "api_key": "sk-...",
    "model": "gpt-4"
})
```

### Mode 3: Web UI Automation

```python
proxy = AgentProxy()
proxy.connect("https://gemini.google.com", hints={
    "user_data_dir": "~/.gemini-profile"  # Save login state
})

# Auto-detects if already logged in
status = proxy.wait_for_login()  # Returns immediately if logged in

response = proxy.say("What is 1+1?")
```

Command line:
```bash
# First time: Opens browser, waits for login, saves to profile
python talk.py --url "https://gemini.google.com" --user-data-dir ~/.gemini-profile -m "Hello!"

# Next time: Auto-detects login, runs headless (no browser window)
python talk.py --url "https://gemini.google.com" --user-data-dir ~/.gemini-profile -m "1+1=?"

# Force show browser window even with saved profile
python talk.py --url "https://gemini.google.com" --user-data-dir ~/.gemini-profile --no-headless -i
```

**Login State Persistence:**
- First run with `--user-data-dir`: Opens browser for manual login
- Subsequent runs: Auto-detects saved login, runs in headless mode
- No need to login again unless session expires

## Detection Process

When given a URL, the skill:

1. **Probe the endpoint**
   - Check response headers (Content-Type, Server)
   - Look for API documentation endpoints (/docs, /openapi.json)
   - Detect framework signatures (Gradio, Streamlit, FastAPI)

2. **Identify protocol**
   - REST API → detect request/response format
   - WebSocket → establish WS connection
   - Web UI → identify input elements

3. **Create appropriate adapter**
   - Configure authentication if needed
   - Set up message format
   - Handle streaming responses

## For Claude Code Usage

When the user gives you an agent URL:

1. Run `scripts/detect_agent.py <url>` to analyze it
2. Use the detected config with `AgentProxy`
3. Conduct the conversation as the user

Example workflow:
```bash
# Step 1: Detect
python scripts/detect_agent.py "http://localhost:8080"

# Output: Detected OpenAI-compatible API at /v1/chat/completions
# Config: {"type": "openai_api", "endpoint": "...", "model": "..."}

# Step 2: Use
python scripts/talk.py --url "http://localhost:8080" --message "Hello!"
```

## Handling Authentication

If the agent requires authentication:

```python
proxy.connect("https://api.example.com/chat", hints={
    "auth": {
        "type": "bearer",  # or "api_key", "basic", "header"
        "token": "your-token"
    }
})
```

## Output

All conversations are logged:

```json
{
  "agent_url": "http://localhost:8080",
  "detected_type": "openai_api",
  "turns": [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi! How can I help?"}
  ]
}
```
