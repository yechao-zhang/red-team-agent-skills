---
name: agent-proxy
description: |
  Auto-discover and communicate with any AI agent given its URL via API.
  Supports REST APIs (OpenAI, Anthropic, Ollama), WebSockets, and Gradio apps.
  Claude Code acts as the user, automatically detecting the agent's API interface and sending messages.
  Use when: (1) User provides an API endpoint URL, (2) Need to automate conversations with external AI services via API.
---

# Agent Proxy Skill

**Universal API Gateway**: Given a URL to any AI agent API, this skill auto-discovers the protocol (REST, WebSocket, Gradio) and conducts conversations.

**Critical**: This works WITHOUT needing:
- ❌ Access to the target agent's source code
- ❌ The target agent's dependencies installed
- ❌ Knowledge of the target agent's implementation

You only need the agent's **API URL**.

**Note on Web UIs**: For browser-based agents (ChatGPT, Gemini, etc.), please use the **`dev-browser`** skill or Red Team's **BrowserTransport** instead. This skill is strictly for APIs.

## Installation

```bash
# Install agent-proxy dependencies
cd ~/.claude/skills/agent-proxy
pip install -r requirements.txt
```

## Workflow

```
User provides URL → Auto-detect Protocol (API/WS) → Create Protocol Adapter → Communicate
```

## Quick Start

```python
from agent_proxy import AgentProxy

# Just give it a URL - it figures out the protocol automatically
proxy = AgentProxy()
proxy.connect("http://localhost:8080/v1/chat/completions")  # API Endpoint

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
| Custom endpoints | Probe & detect | Auto-detect |

## Usage Modes

### Mode 1: Auto-Detect (Recommended)

```python
proxy = AgentProxy()
proxy.connect("https://api.some-agent.com/v1/chat")  # Auto-detects protocol
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

## Detection Process

When given a URL, the skill:

1. **Probe the endpoint**
   - Check response headers (Content-Type, Server)
   - Look for API documentation endpoints (/docs, /openapi.json)
   - Detect framework signatures (Gradio, Streamlit, FastAPI)

2. **Identify protocol**
   - REST API → detect request/response format
   - WebSocket → establish WS connection

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
