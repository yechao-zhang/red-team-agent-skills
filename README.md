# Red Team Agent

Turn your Claude Code into a Red Team Agent!!!

A collection of Claude Code skills for AI agent red team research, adversarial testing, and agent-to-agent communication.

## Overview

Red Team Agent provides tools to interact with, test, and evaluate AI agents from various platforms. It enables Claude Code to act as a proxy user, automating conversations with target AI agents for security research and evaluation purposes.

## Skills

| Skill | Description | Status |
|-------|-------------|--------|
| [red-team](./.claude/skills/red-team/) | Automated red team testing using adaptive nested delegation attacks | ✅ Ready |
| [agent-proxy](./.claude/skills/agent-proxy/) | Auto-discover and communicate with any AI agent via URL | ✅ Ready |
| [claude-reflect](https://github.com/BayramAnnakov/claude-reflect) | Self-learning system that captures corrections and syncs them to CLAUDE.md and SKILL.md | 📦 Optional |
| [dev-browser](https://github.com/SawyerHood/dev-browser) | Persistent browser automation (Recommended for Web UIs) | 📦 External Dependency |
| [playwright-skill](https://github.com/lackeyjb/playwright-skill) | Generic browser automation (Alternative) | 📦 External Dependency |

## Architecture

The `red-team` skill orchestrates attacks by delegating communication to specialized transport skills (`agent-proxy` or `dev-browser`), which then interact with the target agent.

```
┌─────────────┐
│ Claude Code │
└──────┬──────┘
       │ 1. Invokes
┌──────▼───────┐
│   red-team   │
│    skill     │
└──────┬───────┘
       │
       │ 2. Selects Transport (via transport.py)
       ▼
┌──────────────┐    ┌─────────────┐
│ agent-proxy  │    │ dev-browser │
│    skill     │    │    skill    │
└──────┬───────┘    └──────┬──────┘
       │                   │
       │ 3. API            │ 3. Browser
       ▼                   ▼
┌─────────────────────────────────┐
│          Target Agent           │
└─────────────────────────────────┘
```

## Installation & Setup

You can use these skills directly within this project or install them globally.

### 1. Clone Repository
```bash
git clone https://github.com/anthropics/red-team-agent.git
cd red-team-agent
```

### 2. Install Dependencies
Install the Python requirements for the included skills.

```bash
pip install -r .claude/skills/red-team/requirements.txt
pip install -r .claude/skills/agent-proxy/requirements.txt
```

### 3. Usage Options

#### Option A: Project-Local Use (Recommended)
Run Claude Code directly from this directory. The skills will be automatically loaded.

```bash
# From the red-team-agent directory
claude
```

#### Option B: Global Installation
To use these skills globally across any project, copy them to your local configuration directory.

```bash
mkdir -p ~/.claude/skills
cp -r .claude/skills/red-team ~/.claude/skills/
cp -r .claude/skills/agent-proxy ~/.claude/skills/
```

### 4. Setup Browser Automation (Required for Web UIs)
For testing Web UI agents (like ChatGPT, Claude, custom UIs), you need a browser automation skill.

**Option A: dev-browser (Recommended)**
Provides persistent sessions, better stealth, and profile management.
```bash
# Clone and install dev-browser skill
git clone https://github.com/SawyerHood/dev-browser.git ~/.claude/skills/dev-browser
cd ~/.claude/skills/dev-browser
# Follow installation instructions in its README
```

**Option B: playwright-skill (Alternative)**
Standard Playwright automation.
```bash
# Clone and install playwright-skill
git clone https://github.com/lackeyjb/playwright-skill.git ~/.claude/skills/playwright-skill
cd ~/.claude/skills/playwright-skill
pip install -r requirements.txt
playwright install chromium
```

### 5. Setup Self-Learning (Optional)
Install `claude-reflect` to capture corrections and automatically update CLAUDE.md.

```bash
git clone https://github.com/BayramAnnakov/claude-reflect ~/.claude/skills/claude-reflect
# No pip requirements
```

## Usage

### 1. Red Team Attack
Run an automated red team attack against a target agent. This automatically detects if the target is an API or Web UI and uses the appropriate transport.

```
User: Test http://localhost:8082 for schema extraction using /red-team
```

The `red-team` skill will:
1. Auto-detect the target type (Web UI, API, WebSocket, etc.)
2. Deploy a subagent to orchestrate the attack
3. Use adaptive nested delegation ("Russian Doll" attack) to extract internal schemas
4. Optimize payloads based on responses

### 2. Agent Proxy
Interact with an agent manually for exploration.

```
User: Connect to https://gemini.google.com and ask "What is 1+1?"

Claude Code: [Uses agent-proxy skill to automate browser/API, send message, get response]
```

### 3. Self-Learning (Reflect)
If installed, review captured corrections:

```
User: /reflect
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

### Handling Persistent Logins (SSO/Google)

This toolchain supports persistent sessions for web agents that require login (like Google SSO).

1. **Persistent Profiles**: The `dev-browser` skill saves user data (cookies, storage) in `~/.claude/skills/dev-browser/profiles/`.
2. **Stealth Mode**: The browser is patched to avoid simple bot detection mechanisms.
3. **Manual Login Workflow**:
   - If automated login fails (e.g., "This browser is not secure"), stop the tool.
   - Run the browser in headed mode: `cd ~/.claude/skills/dev-browser && ./server.sh`
   - Manually log in to the target site.
   - Close the browser. Future automated runs will reuse this logged-in session.

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
├── CLAUDE.md                 # Project context and developer guide
├── .claude/skills/
│   ├── agent-proxy/          # Agent communication skill
│   │   ├── SKILL.md
│   │   └── scripts/
│   └── red-team/             # Red team testing skill
│       ├── SKILL.md
│       └── scripts/
└── docs/
    └── [documentation...]
```

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting PRs.

## License

MIT License - See [LICENSE](./LICENSE) for details.

## Disclaimer

This project is intended for authorized security testing and research purposes only. Users are responsible for ensuring they have proper authorization before testing any systems. The authors are not responsible for misuse of these tools.
