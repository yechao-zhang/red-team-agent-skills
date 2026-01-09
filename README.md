# Red Team Agent

A collection of Claude Code skills for AI agent security research, adversarial testing, and agent-to-agent communication.

## Overview

Red Team Agent provides tools to interact with, test, and evaluate AI agents from various platforms. It enables Claude Code to act as a proxy user, automating conversations with target AI agents for security research and evaluation purposes.

## Skills

| Skill | Description | Status |
|-------|-------------|--------|
| [red-team](./skills/red-team/) | Automated red team testing using adaptive nested delegation attacks | ✅ Ready |
| [agent-proxy](./skills/agent-proxy/) | Auto-discover and communicate with any AI agent via URL | ✅ Ready |
| browser-automation | Low-level browser control for web-based agents | 🚧 Integrated in Transport Layer |
| attack-patterns | Common adversarial prompt patterns library | 🚧 Integrated in Red Team |
| conversation-logger | Structured logging for agent interactions | 🚧 Planned |

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│ Claude Code │────▶│  Red Team Agent  │────▶│ Target Agent│
│  (Operator) │◀────│     (Skills)     │◀────│  (Various)  │
└─────────────┘     └──────────────────┘     └─────────────┘
                            │
                    ┌───────┴───────┐
                    │               │
              ┌─────▼─────┐   ┌─────▼─────┐
              │   API     │   │  Browser  │
              │  Adapter  │   │  Adapter  │
              └───────────┘   └───────────┘
```

## Quick Start

### Installation

1. Clone this repository:
```bash
git clone https://github.com/anthropics/red-team-agent.git
cd red-team-agent
```

2. Install skills to Claude Code:
```bash
# Install red-team skill
cp -r skills/red-team ~/.claude/skills/

# Install agent-proxy skill (required for API transport)
cp -r skills/agent-proxy ~/.claude/skills/
```

3. Install dependencies:
```bash
# For agent-proxy and general dependencies
cd ~/.claude/skills/agent-proxy
pip install -r requirements.txt

# For browser automation support
pip install playwright
playwright install chromium
```

### Usage

#### 1. Red Team Attack
Run an automated red team attack against a target agent:

```
User: Test http://localhost:8082 for schema extraction using /red-team
```

The `red-team` skill will:
1. Auto-detect the target type (Web UI, API, WebSocket, etc.)
2. Deploy a subagent to orchestrate the attack
3. Use adaptive nested delegation ("Russian Doll" attack) to extract internal schemas
4. Optimize payloads based on responses

#### 2. Agent Proxy
Interact with an agent manually:

```
User: Connect to https://gemini.google.com and ask "What is 1+1?"

Claude Code: [Uses agent-proxy skill to automate browser, send message, get response]
```

## Supported Target Agents

### API-based Agents
- OpenAI API compatible endpoints
- Anthropic API
- Ollama
- Any REST/WebSocket API

### Web-based Agents
- Google Gemini
- ChatGPT
- Claude.ai
- Poe
- HuggingFace Chat
- Custom web UIs (auto-detection)

## Use Cases

1. **Security Research**: Test AI agents for vulnerabilities, jailbreaks, prompt injections
2. **Agent Evaluation**: Automated testing of agent capabilities and behaviors
3. **Agent-to-Agent Communication**: Build pipelines where agents interact with each other
4. **Red Team Exercises**: Authorized adversarial testing of AI systems

## Important Notes

- **Authorization Required**: Only use these tools on systems you have permission to test
- **Responsible Disclosure**: Report any vulnerabilities found through proper channels
- **Ethical Use**: These tools are for defensive security research and authorized testing only

## Project Structure

```
red-team-agent/
├── README.md
├── skills/
│   ├── agent-proxy/           # Agent communication skill
│   │   ├── SKILL.md          # Skill metadata
│   │   ├── README.md         # Skill documentation
│   │   └── scripts/
│   │       ├── agent_proxy.py
│   │       ├── browser_adapter.py
│   │       ├── detect_agent.py
│   │       └── talk.py
│   └── [future skills...]
└── docs/
    └── [documentation...]
```

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting PRs.

## License

MIT License - See [LICENSE](./LICENSE) for details.

## Disclaimer

This project is intended for authorized security testing and research purposes only. Users are responsible for ensuring they have proper authorization before testing any systems. The authors are not responsible for misuse of these tools.
