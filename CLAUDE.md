# Installation & Setup

## 1. Skill Installation

### Option A: Project-Local Use (Recommended for Development)
You can use the skills directly from this repository without global installation.
1.  Open this directory in Claude Code: `claude` (from the root of this repo).
2.  The skills in `.claude/skills/` (red-team, agent-proxy) will be automatically loaded.

### Option B: Global Installation
To use these skills globally across any project:
1.  Create the global skills directory: `mkdir -p ~/.claude/skills`
2.  Copy the skills:
    ```bash
    cp -r .claude/skills/red-team ~/.claude/skills/
    cp -r .claude/skills/agent-proxy ~/.claude/skills/
    ```

### Optional: Claude Reflect (Self-Learning)
You can install `claude-reflect` to capture learnings and update CLAUDE.md automatically.

```bash
# Clone and install claude-reflect
git clone https://github.com/BayramAnnakov/claude-reflect ~/.claude/skills/claude-reflect
# Note: No pip requirements for this skill (uses standard library)
```

## 2. Dependencies
Install Python dependencies (required for red-team and agent-proxy):
```bash
pip install -r .claude/skills/red-team/requirements.txt
pip install -r .claude/skills/agent-proxy/requirements.txt
```

## 3. Browser Automation Setup (Required for Web UIs)

For testing Web UI agents (like ChatGPT, Claude, custom UIs), you must install one of the browser automation skills.

### Option A: dev-browser (Recommended)
This skill provides persistent sessions (cookies/storage), better stealth, and profile management.

**Install via MCP (recommended):**
Check if `dev-browser` is available in your MCP configuration.

**Install manually:**
If you have access to the `dev-browser` repository:
```bash
# Clone and install dev-browser skill
git clone https://github.com/SawyerHood/dev-browser.git ~/.claude/skills/dev-browser
cd ~/.claude/skills/dev-browser
# Follow installation instructions in its README (usually npm install & build)
```

### Option B: playwright-skill (Alternative)
Standard Playwright automation. Use this if `dev-browser` is not available.

```bash
# Clone and install playwright-skill
git clone https://github.com/lackeyjb/playwright-skill.git ~/.claude/skills/playwright-skill
cd ~/.claude/skills/playwright-skill
pip install -r requirements.txt
playwright install chromium
```

# Usage Commands

## Red Team Attack
Test an agent for security vulnerabilities (schema extraction, prompt injection).
- "Test http://localhost:8082 for schema extraction using /red-team"
- "Run a red team attack against https://chat.example.com"

## Agent Proxy
Connect to and chat with an agent manually.
- "Connect to https://gemini.google.com"
- "Ask the agent at http://localhost:8000/v1/chat/completions 'Who are you?'"

# Development Guidelines

- **Code Style**: PEP 8 for Python.
- **Safety**: This is a security tool. Ensure code is safe and intended for authorized testing only.
- **Modifications**: When modifying `transport.py`, ensure compatibility with both `dev-browser` and `playwright-skill` interfaces.

# Backup Instructions
**IMPORTANT**: Every once in a while, when you have made significant changes to this repository (e.g., after completing a task or a logical unit of work), you **MUST** push the changes to GitHub for backup.

Run `git push` to sync with the remote repository.
